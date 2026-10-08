"""Read-only offline worker for one bounded, registered scientific protocol."""
from __future__ import annotations
import argparse
from importlib import metadata
import os
from pathlib import Path
import platform
import time
import traceback
from . import (ROOT,ASSETS,SOURCE_LOCK,DEPENDENCY_LOCK,CASE_MODULES,MODES,SCF_CAPS,CUSTOM_CAPS,
               adapter,digest,read_json,save,verify_source,validate_contract)

def resources(contract,phase):
    from runtime.user_molecule.acceptance_resources import collect_cgroup
    value=collect_cgroup(phase=phase); reasons=[]; limits=contract['resources']
    if value.get('status')!='COMPLETE': reasons.append('Incomplete cgroup observation')
    if value.get('memory_limit_bytes')!=limits['memory_bytes']: reasons.append('Memory limit differs')
    if value.get('memory_swap_limit_bytes')!=0: reasons.append('Swap differs')
    if value.get('cpu_quota_us')!=limits['cpus']*value.get('cpu_period_us',0): reasons.append('CPU quota differs')
    if os.getuid()!=10001 or os.getgid()!=10001: reasons.append('Non-root identity differs')
    readonly={str(p):bool(os.statvfs(p).f_flag & os.ST_RDONLY) for p in (ROOT,ASSETS,Path('/opt/venv'),Path('/task-contract.json'))}
    if not all(readonly.values()): reasons.append('Source/dependency/contract writable')
    interfaces=sorted(p.name for p in Path('/sys/class/net').iterdir())
    if interfaces!=['lo']: reasons.append('Network access differs')
    threads={k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')}
    if any(v!=str(limits['threads']) for v in threads.values()): reasons.append('Thread limits differ')
    value.update(status='PASS' if not reasons else 'BLOCKED',reasons=reasons,uid=os.getuid(),gid=os.getgid(),
                 readonly=readonly,interfaces=interfaces,thread_environment=threads)
    return value

def dependency_check():
    expected=read_json(DEPENDENCY_LOCK)
    actual={name:metadata.version(name) for name in expected['packages']}
    if actual!=expected['packages'] or platform.python_version()!=expected['python_version']:
        raise ValueError('Dependency environment differs')
    return {'status':'PASS','packages':actual,'python_version':platform.python_version()}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task',choices=CASE_MODULES,required=True)
    parser.add_argument('--contract',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args(argv); output=args.output_dir
    if output!=Path('/output') or not output.is_dir() or any(output.iterdir()): parser.error('Fresh /output required')
    receipt={'schema':'protocol-case-worker-v1','case':args.task,'status':'BLOCKED','worker_exit_code':2,
             'scientific_counts':None,'automatic_retry':False,'resume':False,'general_conditional_compute':'BLOCKED',
             'external_consultation_required':False,'original_protocol_gate_changed':False}
    guard=None; controller=None; code=2
    try:
        contract=validate_contract(read_json(args.contract)); receipt['contract']=contract
        if contract['case']!=args.task: raise ValueError('Task contract differs')
        for key in ('execution_id','runtime_commit','source_lock_sha256','dependency_lock_sha256','mode'):
            receipt[key]=contract[key]
        receipt['contract_sha256']=digest(args.contract)
        verify_source()
        if digest(SOURCE_LOCK)!=contract['source_lock_sha256'] or digest(DEPENDENCY_LOCK)!=contract['dependency_lock_sha256']:
            raise ValueError('Source/dependency lock differs')
        for key,env in (('runtime_commit','AI4ORGCHEM_PROTOCOL_RUNTIME_COMMIT'),('source_lock_sha256','AI4ORGCHEM_PROTOCOL_SOURCE_SHA256'),
                        ('dependency_lock_sha256','AI4ORGCHEM_PROTOCOL_DEPENDENCY_SHA256')):
            if contract[key]!=os.environ.get(env): raise ValueError('Image build identity differs: '+key)
        receipt['source_check']='PASS'; receipt['dependency_evidence']=dependency_check()
        start=resources(contract,'start'); save(output/'resource-start.json',start)
        if start['status']!='PASS': raise ValueError('Resource preflight failed: '+str(start['reasons']))
        module=adapter(args.task)
        if contract['mode'] in ('live','preflight'): module.prepare(args.task,ASSETS)
        from runtime.user_molecule.root_native_lifecycle import StopController
        from .native_guard import ProtocolGuard
        controller=StopController(deadline_epoch=contract['stop_deadline_epoch'])
        with controller.installed():
            with ProtocolGuard(args.task,contract['mode'],checkpoint=controller.checkpoint,journal=output/'native-events.jsonl') as guard:
                result=getattr(module,contract['mode'])(args.task,ASSETS)
                if result.get('case')!=args.task: raise ValueError('Adapter returned a different fixed case')
                result['execution_mode']=contract['mode']
                result['runtime_protocol_id']='runtime-'+args.task.lower()+'-bounded/0.1'
                save(output/'case-result.json',result)
            audit=guard.snapshot(); save(output/'guard-receipt.json',audit)
            if audit['status']!='PASS' or audit['restored_attributes_intact'] is not True: raise ValueError('Native entry audit failed')
            if contract['mode']=='live':
                expected={**{'scf_'+k:v for k,v in SCF_CAPS[args.task].items()},**CUSTOM_CAPS.get(args.task,{})}
                if args.task=='P09': expected['stability']=1
                if any(audit['counts'].get(k,0)!=v for k,v in expected.items()):
                    raise ValueError('Required science entries not all observed: '+str(expected)+' vs '+str(audit['counts']))
            elif any(audit['counts'].values()): raise ValueError('Metadata/ledger mode entered science kernels')
            if result.get('status')!='PASS': raise ValueError('Scoped numerical checks failed: '+str(result.get('failed_checks',result.get('status'))))
        end=resources(contract,'end'); save(output/'resource-end.json',end)
        if end['status']!='PASS': raise ValueError('Resource closure failed')
        verify_source(); dependency_check()
        receipt.update(status='PASS_SCOPED_PROTOCOL_CASE',scientific_counts=audit['counts'],resource_check='PASS',guard_check='PASS',
                       case_result_sha256=digest(output/'case-result.json'),guard_receipt_sha256=digest(output/'guard-receipt.json'))
        code=0
    except BaseException as error:
        receipt.update(status='NOT_QUALIFIED' if guard is not None else 'BLOCKED',error={'type':type(error).__name__,'message':str(error)})
        (output/'exception.txt').write_text(traceback.format_exc(),encoding='utf-8')
        if guard is not None:
            try:
                audit=guard.snapshot();save(output/'guard-receipt.json',audit);receipt['scientific_counts']=audit['counts']
            except BaseException as secondary: receipt['audit_error']=str(secondary)
        try: save(output/'resource-end.json',resources(contract,'error-end'))
        except BaseException: pass
    if controller is not None: receipt['stop_controller']=controller.snapshot()
    receipt.update(worker_exit_code=code,finished_epoch=time.time())
    hashes={str(p.relative_to(output)).replace('\\','/'):digest(p) for p in output.rglob('*') if p.is_file()}
    save(output/'run-manifest.json',{'schema':'protocol-case-output-v1','execution_id':receipt.get('execution_id'),'files':hashes})
    receipt['run_manifest_sha256']=digest(output/'run-manifest.json');save(output/'worker-receipt.json',receipt)
    print({'case':args.task,'mode':receipt.get('mode'),'status':receipt['status'],'exit_code':code},flush=True)
    return code

if __name__=='__main__': raise SystemExit(main())
