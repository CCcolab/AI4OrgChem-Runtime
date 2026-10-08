"""One immutable high-cost state, or zero-kernel ledger/metadata review."""
import argparse, importlib.metadata as md, os, platform, time, traceback
from pathlib import Path
from . import ROOT,ASSETS,SOURCE_LOCK,DEPENDENCY_LOCK,PROFILE,adapter,units,unit,validate_contract,verify_source,digest,read_json,save

def resources(contract,phase):
    from runtime.user_molecule.acceptance_resources import collect_cgroup
    v=collect_cgroup(phase=phase);r=contract['resources'];reasons=[]
    if v.get('status')!='COMPLETE':reasons.append('CGROUP_UNKNOWN')
    if v.get('memory_limit_bytes')!=r['memory_bytes'] or v.get('memory_swap_limit_bytes')!=0:reasons.append('MEMORY_SWAP_DIFFERS')
    if v.get('cpu_quota_us')!=r['cpus']*v.get('cpu_period_us',0):reasons.append('CPU_DIFFERS')
    if os.getuid()!=10001 or os.getgid()!=10001:reasons.append('ROOT_USER')
    readonly={str(p):bool(os.statvfs(p).f_flag & os.ST_RDONLY) for p in [ROOT,ASSETS,Path('/opt/venv'),Path('/task-contract.json'),Path('/inputs')]}
    if not all(readonly.values()):reasons.append('WRITABLE_PROTECTED_INPUT')
    if sorted(p.name for p in Path('/sys/class/net').iterdir())!=['lo']:reasons.append('NETWORK_AVAILABLE')
    env={k:os.environ.get(k) for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']}
    if any(x!=str(r['threads']) for x in env.values()):reasons.append('THREADS_DIFFER')
    v.update(status='PASS' if not reasons else 'BLOCKED',reasons=reasons,readonly=readonly,thread_environment=env,uid=os.getuid(),interfaces=sorted(p.name for p in Path('/sys/class/net').iterdir()))
    return v
def dependencies():
    expected=read_json(DEPENDENCY_LOCK)
    actual={n:md.version(n) for n in expected['packages']}
    if actual!=expected['packages'] or platform.python_version()!=expected['python_version']:raise ValueError('Exact dependencies differ')
    return {'status':'PASS','packages':actual,'python':platform.python_version()}
def validate_inputs(contract):
    mapping={}
    for identifier,row in contract['inputs'].items():
        if set(row)!={'relative_path','worker_receipt_sha256','result_sha256','source_sha256','dependencies_sha256','profile_sha256','image_id'}:raise ValueError('Closed input receipt fields required')
        rel=Path(row['relative_path'])
        if rel.is_absolute() or '..' in rel.parts or ':' in str(rel) or '\\' in str(rel):raise ValueError('Unsafe dependency path')
        root=Path('/inputs')/rel
        for key in ['source_sha256','dependencies_sha256','profile_sha256','image_id']:
            if row[key]!=contract[key]:raise ValueError('Dependency environment identity differs')
        if digest(root/'worker-receipt.json')!=row['worker_receipt_sha256'] or digest(root/'result.json')!=row['result_sha256']:raise ValueError('Dependency byte receipt differs')
        result=read_json(root/'result.json');receipt=read_json(root/'worker-receipt.json')
        if digest(root/'run-manifest.json')!=receipt.get('run_manifest_sha256') or digest(root/'result.json')!=receipt.get('result_sha256'):raise ValueError('Dependency manifest not bound to completed receipt')
        if result.get('status')!='PASS' or receipt.get('status')!='PASS_SCOPED_HIGH_COST_STATE' or result.get('unit_id',result.get('unit'))!=identifier or receipt.get('unit')!=identifier or receipt.get('mode')!='live':raise ValueError('A fresh completed matching optimisation is required')
        for name,sha in read_json(root/'run-manifest.json')['files'].items():
            q=Path(name)
            if q.is_absolute() or '..' in q.parts or ':' in name or '\\' in name or digest(root/q)!=sha:raise ValueError('Dependency output changed')
        mapping[identifier]=root
    return mapping
def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--contract',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args(argv)
    if a.output_dir!=Path('/output') or not a.output_dir.is_dir() or any(a.output_dir.iterdir()):p.error('Fresh /output only')
    out=a.output_dir;receipt={'schema':'high-cost-worker-v1','status':'BLOCKED','worker_exit_code':40,'resume':False,'automatic_retry':False};guard=None;controller=None;code=40
    try:
        c=validate_contract(read_json(a.contract));receipt.update(contract=c,contract_sha256=digest(a.contract),case=c['case'],unit=c['unit'],mode=c['mode'],execution_id=c['execution_id'])
        verify_source()
        for key,path in [('source_sha256',SOURCE_LOCK),('dependencies_sha256',DEPENDENCY_LOCK),('profile_sha256',PROFILE)]:
            if digest(path)!=c[key]:raise ValueError('Worker source/profile identity differs')
        for key,env in [('runtime_build_commit','AI4ORGCHEM_HIGH_COST_COMMIT'),('source_sha256','AI4ORGCHEM_HIGH_COST_SOURCE_SHA256'),('dependencies_sha256','AI4ORGCHEM_HIGH_COST_DEPENDENCY_SHA256')]:
            if os.environ.get(env)!=c[key]:raise ValueError('Immutable image build identity differs')
        receipt['dependencies']=dependencies();initial=resources(c,'start');save(out/'resource-start.json',initial)
        if initial['status']!='PASS':raise ValueError('Actual container resource admission failed')
        inputs=validate_inputs(c);module=adapter(c['case'])
        module.prepare(ASSETS)
        from pyscf import lib
        receipt['actual_pyscf_threads']=int(lib.num_threads())
        if receipt['actual_pyscf_threads']!=c['resources']['threads']:raise ValueError('Actual PySCF numerical threads differ')
        from runtime.user_molecule.root_native_lifecycle import StopController
        from .native_guard import HighCostGuard
        controller=StopController(deadline_epoch=c['stop_deadline_epoch'])
        selected=unit(c['unit']) if c['unit'] else {'id':c['case']+'-metadata','case':c['case'],'operator_id':'ordinary_rks','optimizer':'none','caps':dict.fromkeys(['scf','gradient','numint','grids','conditional'],0)}
        def checkpoint(event):
            value={'schema':'high-cost-checkpoint-v1','execution_id':c['execution_id'],'unit':c['unit'],'resume_supported':False,'status':'IN_PROGRESS','event':event,'time':time.time()}
            save(out/'checkpoint.json',value)
            controller.checkpoint('HIGH_COST_DURABLE_PROGRESS')
        with controller.installed():
            with HighCostGuard(selected,c['mode'],checkpoint=controller.checkpoint,journal=out/'native-events.jsonl') as guard:
                if c['mode']=='ledger':result=module.ledger(ASSETS)
                elif c['mode']=='preflight':
                    targets=[unit(c['unit'])] if c['unit'] else [u for u in units() if u['case']==c['case']]
                    rows=[module.preflight(u,ASSETS) for u in targets]
                    result={'status':'PASS' if all(r.get('status')=='PASS' for r in rows) else 'FAIL','case':c['case'],'unit':c['unit'],'preflight_results':rows,'no_scf_or_quantum_optimizer_executed':True}
                else:result=module.live(selected,ASSETS,out,inputs,checkpoint)
                result.update(case=c['case'],execution_mode=c['mode'],unit_id=c['unit'],runtime_protocol_id='runtime-high-cost-'+c['case'].lower()+'/0.1',source_sha256=c['source_sha256'],dependencies_sha256=c['dependencies_sha256'],profile_sha256=c['profile_sha256'],image_id=c['image_id'])
                save(out/'result.json',result)
            audit=guard.snapshot();save(out/'guard-receipt.json',audit)
            if audit.get('status')!='PASS' or audit.get('closed') is not True or audit.get('restored_attributes_intact') is not True:raise ValueError('Held entry audit not closed')
            if c['mode']!='live' and any(audit['counts'].values()):raise ValueError('Unexpected kernel in zero-science mode')
            if c['mode']=='live' and audit['counts'].get('optimizer',0)!=1:raise ValueError('Exactly one new optimiser must execute')
            if result.get('status')!='PASS':raise ValueError('Scoped result not qualified')
        final=resources(c,'end');save(out/'resource-end.json',final)
        if final['status']!='PASS':raise ValueError('Resource closure failed')
        verify_source();dependencies()
        receipt.update(status='PASS_SCOPED_HIGH_COST_STATE' if c['mode']=='live' else 'PASS_SCOPED_HIGH_COST_'+c['mode'].upper(),scientific_counts=audit['counts'],result_sha256=digest(out/'result.json'),guard_sha256=digest(out/'guard-receipt.json'));code=0
    except BaseException as e:
        receipt.update(status='NOT_QUALIFIED' if guard else 'BLOCKED',error={'type':type(e).__name__,'message':str(e)})
        (out/'exception.txt').write_text(traceback.format_exc(),encoding='utf-8')
        if guard:
            try:save(out/'guard-receipt.json',guard.snapshot())
            except BaseException as secondary:receipt['audit_error']=str(secondary)
        try:save(out/'resource-end.json',resources(c,'error-end'))
        except BaseException:pass
    if controller:receipt['stop_controller']=controller.snapshot()
    hashes={str(f.relative_to(out)).replace('\\','/'):digest(f) for f in out.rglob('*') if f.is_file() and not f.is_symlink()}
    save(out/'run-manifest.json',{'schema':'high-cost-output-v1','execution_id':receipt.get('execution_id'),'files':hashes})
    receipt.update(worker_exit_code=code,run_manifest_sha256=digest(out/'run-manifest.json'),finished_epoch=time.time());save(out/'worker-receipt.json',receipt)
    print({'status':receipt['status'],'case':receipt.get('case'),'unit':receipt.get('unit'),'exit_code':code},flush=True);return code
if __name__=='__main__':raise SystemExit(main())
