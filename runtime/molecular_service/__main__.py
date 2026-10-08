"""Controlled ordinary single-point worker for user XYZ within one profile."""
from __future__ import annotations
import argparse,json,os,time
from importlib import metadata
from pathlib import Path
import platform
from . import ROOT,TASK,DEPENDENCY_LOCK,digest,strict_load,verify_source,source_snapshot_sha256,validate_contract,validate_case_result,verify_calculation_artifacts

def save(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    with temporary.open('xb') as stream:
        stream.write((json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode('utf-8'))
        stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)
def dependencies():
    lock=strict_load(DEPENDENCY_LOCK);actual={key:metadata.version(key) for key in lock['packages']}
    if actual!=lock['packages'] or platform.python_version()!=lock['python_version']:raise ValueError('Installed dependency identity differs')
    return {'status':'PASS','python_version':platform.python_version(),'packages':actual}
def resource_observation(phase):
    from runtime.registered_cases.__main__ import resource_observation as collect
    value=collect(phase)
    value['source_readonly']['/input']=bool(os.statvfs('/input').f_flag & os.ST_RDONLY)
    if not value['source_readonly']['/input']:
        value['registered_status']='BLOCKED';value['registered_reasons'].append('Input must be read-only')
    return value
def input_bundle(request,contract):
    from .input import parse_request
    if request!=Path('/input/request.json'):raise ValueError('Only the readonly input snapshot is allowed')
    manifest_path=Path('/input/INPUT_MANIFEST.json')
    manifest=strict_load(manifest_path)
    if digest(manifest_path)!=contract['input_manifest_sha256'] or manifest.get('schema')!='molecular-service-input-snapshot-v1':
        raise ValueError('Input manifest identity differs')
    bundle=parse_request(request,input_root=Path('/input'))
    for key in ('request_sha256','structure_sha256','profile_sha256'):
        if bundle[key]!=contract[key] or manifest.get(key)!=contract[key]:raise ValueError('Input hash differs: '+key)
    if manifest.get('task')!=TASK or manifest.get('request_file')!='request.json' or manifest.get('structure_file')!=bundle['request']['structure']['file']:
        raise ValueError('Input manifest task/files differ')
    actual=sorted(p.name for p in Path('/input').iterdir())
    expected=sorted(['request.json','INPUT_MANIFEST.json',bundle['request']['structure']['file']])
    if actual!=expected:raise ValueError('Unexpected files in input snapshot')
    return bundle

def main(argv=None):
    parser=argparse.ArgumentParser(description='User molecule ordinary RHF single point; explicit supported profile')
    parser.add_argument('--task',choices=[TASK],required=True);parser.add_argument('--request',type=Path,required=True)
    parser.add_argument('--contract',type=Path,required=True);parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args(argv);output=args.output_dir.resolve()
    if output!=Path('/output') or not output.is_dir() or any(output.iterdir()):parser.error('Fresh /output required')
    receipt={'schema':'molecular-service-worker-v1','task':TASK,'status':'BLOCKED','worker_exit_code':2,
       'automatic_retry':False,'resume':False,'conditional_user_compute':'BLOCKED',
       'actual_scf_kernel_calls':None,'actual_boys_kernel_calls':None,'actual_pipek_mezey_kernel_calls':None,'new_conditional_NR_calls':None}
    guard=None;controller=None;code=2
    try:
        contract=strict_load(args.contract);profile=validate_contract(contract)
        receipt.update({key:contract[key] for key in ('execution_id','runtime_commit','source_snapshot_sha256',
             'dependency_lock_sha256','profile_sha256','request_sha256','structure_sha256','input_manifest_sha256','scientific_execution_authorized')})
        receipt['contract_sha256']=digest(args.contract)
        verify_source()
        if source_snapshot_sha256()!=contract['source_snapshot_sha256'] or digest(DEPENDENCY_LOCK)!=contract['dependency_lock_sha256']:raise ValueError('Execution source/dependency lock differs')
        for key,env in (('runtime_commit','AI4ORGCHEM_RUNTIME_COMMIT'),('source_snapshot_sha256','AI4ORGCHEM_MOLECULAR_SOURCE_SHA256'),('dependency_lock_sha256','AI4ORGCHEM_MOLECULAR_DEPENDENCY_SHA256')):
            if contract[key]!=os.environ.get(env):raise ValueError('Image build identity differs: '+key)
        receipt['source_check']='PASS';receipt['dependency_evidence']=dependencies();receipt['dependency_check']='PASS'
        bundle=input_bundle(args.request,contract);receipt['input_check']='PASS'
        start=resource_observation('start');save(output/'resource-start.json',start)
        if start['registered_status']!='PASS':raise ValueError('Resource/platform preflight failed')
        receipt['resource_check']='PASS'
        from runtime.user_molecule.root_native_lifecycle import StopController
        from .native_guard import MolecularNativeGuard
        controller=StopController(deadline_epoch=contract['stop_deadline_epoch'])
        with controller.installed():
            controller.checkpoint('MOLECULAR_PRE_DISPATCH')
            with MolecularNativeGuard(stop_checkpoint=controller.checkpoint) as guard:
                calculation=output/'calculation';calculation.mkdir()
                from .engine import compute
                result=compute(bundle,profile,calculation,checkpoint=controller.checkpoint,execution_contract=contract)
                validate_case_result(result,contract)
                verify_calculation_artifacts(calculation,result)
                controller.checkpoint('MOLECULAR_POST_DISPATCH')
        observed=guard.snapshot();save(output/'guard-receipt.json',observed)
        if observed.get('status')!='PASS' or observed.get('restored_attributes_intact') is not True or observed.get('engine_kind')!='PINNED_PYSCF_MODULES' or observed.get('held_at_close') is not True or observed.get('closed') is not True or observed.get('forbidden_attempts')!=[] or observed.get('changed_guards')!=[]:
            raise ValueError('Native guard did not close with pinned engine evidence')
        counts=observed['counts'];expected={'scf_kernel':1,'boys_kernel':0,'pipek_mezey_kernel':0,'conditional_NR':0}
        if set(counts)!=set(expected) or any(type(counts[key]) is not int or counts[key]!=value for key,value in expected.items()) or any(observed['call_outcomes'][key]!={'returned':value,'failed':0} for key,value in list(expected.items())[:3]):raise ValueError('Observed native call outcomes differ')
        for key,name in (('actual_scf_kernel_calls','scf_kernel'),('actual_boys_kernel_calls','boys_kernel'),('actual_pipek_mezey_kernel_calls','pipek_mezey_kernel'),('new_conditional_NR_calls','conditional_NR')):receipt[key]=counts[name]
        receipt['guard_check']='PASS'
        verify_source();dependencies();input_bundle(args.request,contract)
        end=resource_observation('end');save(output/'resource-end.json',end)
        if end['registered_status']!='PASS':raise ValueError('Resource closure differs')
        for filename,key in (('result.json','result_sha256'),('report.md','report_sha256')):receipt[key]=digest(calculation/filename)
        receipt['guard_receipt_sha256']=digest(output/'guard-receipt.json');receipt['persistence_check']='PASS'
        receipt['status']='PASS_SCOPED_MOLECULAR_SINGLE_POINT';code=0
    except BaseException as error:
        receipt['error']={'type':type(error).__name__,'message':str(error)}
        if guard is not None:
            observed=guard.snapshot();save(output/'guard-receipt.json',observed)
            receipt['guard_check']=observed.get('status')
            counts=observed.get('counts',{})
            for key,name in (('actual_scf_kernel_calls','scf_kernel'),('actual_boys_kernel_calls','boys_kernel'),('actual_pipek_mezey_kernel_calls','pipek_mezey_kernel'),('new_conditional_NR_calls','conditional_NR')):receipt[key]=counts.get(name)
        receipt['status']='NOT_QUALIFIED' if guard is not None else 'BLOCKED'
        # Do not omit available end-resource evidence after a numerical refusal.
        try:save(output/'resource-end.json',resource_observation('failure-end'))
        except BaseException:pass
    if controller is not None:receipt['stop_controller']=controller.snapshot()
    receipt['worker_exit_code']=code;receipt['finished_epoch']=time.time()
    output_hashes={p.relative_to(output).as_posix():digest(p) for p in output.rglob('*') if p.is_file()}
    save(output/'run-manifest.json',{'schema':'molecular-service-run-manifest-v1','task':TASK,'execution_id':receipt.get('execution_id'),
        'runtime_commit':receipt.get('runtime_commit'),'output_sha256':output_hashes})
    receipt['run_manifest_sha256']=digest(output/'run-manifest.json');save(output/'worker-receipt.json',receipt)
    print(json.dumps({'status':receipt['status'],'task':TASK,'worker_exit_code':code}));return code

if __name__=='__main__':raise SystemExit(main())
