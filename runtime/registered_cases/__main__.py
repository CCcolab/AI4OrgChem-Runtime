"""Audited container worker. PASS requires case, identity, guard and resource evidence."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import importlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import time
from . import ROOT, TASKS, DEPENDENCY_LOCK, digest, strict_load, verify_source, source_snapshot_sha256, validate_contract, validate_case_result

def save(path, value):
    raw=(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode('utf-8')
    temporary=path.with_suffix(path.suffix+'.tmp')
    with temporary.open('xb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)

def dependencies():
    lock=strict_load(DEPENDENCY_LOCK)
    actual={name:metadata.version(name) for name in lock['packages']}
    if actual!=lock['packages'] or platform.python_version()!=lock['python_version']:
        raise ValueError('Installed dependencies differ from the fixed local candidate')
    return {'status':'PASS','python_version':platform.python_version(),'packages':actual}

def resource_observation(phase):
    from runtime.user_molecule.acceptance_resources import collect_cgroup
    value=collect_cgroup(phase=phase)
    reasons=[]
    if value.get('status')!='COMPLETE':reasons.append('Incomplete cgroup evidence')
    if value.get('memory_limit_bytes')!=1073741824:reasons.append('Memory limit differs')
    if value.get('memory_swap_limit_bytes')!=0:reasons.append('Swap allowance differs')
    quota,period=value.get('cpu_quota_us'),value.get('cpu_period_us')
    if type(quota) is not int or type(period) is not int or quota!=period:reasons.append('CPU quota differs')
    if os.getuid()!=10001 or os.getgid()!=10001:reasons.append('Non-root identity differs')
    readonly={str(p):bool(os.statvfs(p).f_flag & os.ST_RDONLY) for p in (ROOT,Path('/opt/ai4orgchem'),Path('/opt/venv'),Path('/task-contract.json'))}
    if not all(readonly.values()):reasons.append('Source/dependencies/contract must be read-only')
    interfaces=sorted(p.name for p in Path('/sys/class/net').iterdir())
    if interfaces!=['lo']:reasons.append('Only loopback is permitted')
    threads={key:os.environ.get(key) for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')}
    if any(v!='1' for v in threads.values()):reasons.append('Thread environment differs')
    value.update({'registered_status':'PASS' if not reasons else 'BLOCKED','registered_reasons':reasons,
                  'uid':os.getuid(),'gid':os.getgid(),'source_readonly':readonly,'network_interfaces':interfaces,'thread_environment':threads})
    return value

def main(argv=None):
    parser=argparse.ArgumentParser(description='Only frozen P02, P13 and ethene P01 controls')
    parser.add_argument('--task',choices=TASKS,required=True)
    parser.add_argument('--contract',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args(argv)
    output=args.output_dir.resolve()
    if output!=Path('/output') or not output.is_dir() or any(output.iterdir()):
        parser.error('Fresh container /output is required')
    receipt={'schema':'registered-case-worker-v1','task':args.task,'status':'BLOCKED','worker_exit_code':2,
             'observed_at_utc':datetime.now(timezone.utc).isoformat(),'general_user_compute':'BLOCKED',
             'external_review_required':False,'automatic_retry':False,'resume':False,
             'actual_scf_kernel_calls':None,'actual_boys_kernel_calls':None,'actual_pipek_mezey_kernel_calls':None,
             'new_conditional_NR_calls':None}
    guard=None;controller=None;exit_code=2
    try:
        contract=strict_load(args.contract);spec=validate_contract(contract)
        if contract['task']!=args.task:raise ValueError('Task and contract differ')
        receipt.update({key:contract[key] for key in ('execution_id','runtime_commit','source_snapshot_sha256','dependency_lock_sha256','scientific_execution_authorized')})
        receipt['contract_sha256']=digest(args.contract)
        verify_source()
        if source_snapshot_sha256()!=contract['source_snapshot_sha256'] or digest(DEPENDENCY_LOCK)!=contract['dependency_lock_sha256']:
            raise ValueError('Execution source/dependency lock differs')
        for key,env in (('runtime_commit','AI4ORGCHEM_RUNTIME_COMMIT'),('source_snapshot_sha256','AI4ORGCHEM_REGISTERED_SOURCE_SHA256'),('dependency_lock_sha256','AI4ORGCHEM_REGISTERED_DEPENDENCY_SHA256')):
            if contract[key]!=os.environ.get(env):raise ValueError('Image build identity differs: '+key)
        receipt['source_check']='PASS';receipt['dependency_evidence']=dependencies();receipt['dependency_check']='PASS'
        start=resource_observation('start');save(output/'resource-start.json',start)
        if start['registered_status']!='PASS':raise ValueError('Resource/platform preflight failed')
        receipt['resource_check']='PASS'
        from runtime.user_molecule.root_native_lifecycle import StopController
        from .native_guard import RegisteredNativeGuard
        controller=StopController(deadline_epoch=contract['stop_deadline_epoch'])
        with controller.installed():
            controller.checkpoint('REGISTERED_WORKER_PRE_DISPATCH')
            with RegisteredNativeGuard(args.task,stop_checkpoint=controller.checkpoint) as guard:
                case_dir=output/'case';case_dir.mkdir()
                adapter=importlib.import_module('runtime.registered_cases.'+spec['module'])
                result=adapter.run(case_dir,authorization=contract) if args.task=='p01-orbital-density' else adapter.run(case_dir)
                validate_case_result(result,contract)
                controller.checkpoint('REGISTERED_WORKER_POST_DISPATCH')
                guard_receipt=guard.snapshot()
                save(output/'guard-receipt.json',guard_receipt)
                if guard_receipt.get('status')!='PASS':raise ValueError('Native guard failed')
                counts=guard_receipt['counts']
                for key,name in (('actual_scf_kernel_calls','scf_kernel'),('actual_boys_kernel_calls','boys_kernel'),('actual_pipek_mezey_kernel_calls','pipek_mezey_kernel')):
                    receipt[key]=counts[name]
                receipt['new_conditional_NR_calls']=counts['conditional_NR'];receipt['guard_check']='PASS'
                expected=1 if args.task=='p01-orbital-density' else 0
                if any(receipt[k]!=expected for k in ('actual_scf_kernel_calls','actual_boys_kernel_calls','actual_pipek_mezey_kernel_calls')) or receipt['new_conditional_NR_calls']!=0:
                    raise ValueError('Scientific call evidence differs from fixed task')
                expected_status='P01_FIXED_CONTROL_PASSED' if expected else 'PASS'
                if result.get('status')!=expected_status:raise ValueError('Case did not qualify: '+str(result.get('status')))
        closed_guard=guard.snapshot()
        save(output/'guard-receipt.json',closed_guard)
        if closed_guard.get('status')!='PASS' or closed_guard.get('restored_attributes_intact') is not True:
            raise ValueError('Native guard restoration did not close cleanly')
        verify_source();dependencies()
        end=resource_observation('end');save(output/'resource-end.json',end)
        if end['registered_status']!='PASS':raise ValueError('Resource evidence at closure failed')
        for name,key in (('case-result.json','case_result_sha256'),('case-report.md','case_report_sha256')):
            receipt[key]=digest(output/'case'/name)
        receipt['guard_receipt_sha256']=digest(output/'guard-receipt.json')
        receipt['persistence_check']='PASS';receipt['status']='PASS_SCOPED_FIXED_CASE';exit_code=0
    except BaseException as error:
        receipt['error']={'type':type(error).__name__,'message':str(error)}
        if guard is not None:
            # A failed or killed call is not an observed zero; retain the guard's actual ledger.
            snapshot=guard.snapshot();save(output/'guard-receipt.json',snapshot)
            receipt['guard_check']=snapshot.get('status')
            counts=snapshot.get('counts',{})
            for key,name in (('actual_scf_kernel_calls','scf_kernel'),('actual_boys_kernel_calls','boys_kernel'),('actual_pipek_mezey_kernel_calls','pipek_mezey_kernel'),('new_conditional_NR_calls','conditional_NR')):receipt[key]=counts.get(name)
        receipt['status']='NOT_QUALIFIED' if guard is not None else 'BLOCKED'
    if controller is not None:receipt['stop_controller']=controller.snapshot()
    receipt['worker_exit_code']=exit_code;receipt['finished_epoch']=time.time()
    output_hashes={str(path.relative_to(output)).replace('\\','/'):digest(path) for path in output.rglob('*') if path.is_file()}
    save(output/'run-manifest.json',{'schema':'registered-case-run-manifest-v1','task':args.task,'execution_id':receipt.get('execution_id'),
                                  'runtime_commit':receipt.get('runtime_commit'),'output_sha256':output_hashes})
    receipt['run_manifest_sha256']=digest(output/'run-manifest.json')
    save(output/'worker-receipt.json',receipt)
    print(json.dumps({'status':receipt['status'],'task':args.task,'worker_exit_code':exit_code}))
    return exit_code

if __name__=='__main__':raise SystemExit(main())
