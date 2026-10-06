"""Persist guarded synthetic budget/snapshot examples; no molecular evaluator."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('budget_guard_tools',ROOT/'scripts/ci-guard-budget-recording.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)


def save(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def main():
    attempted=[];bindings=guard.install_guards(attempted)
    import numpy as np
    from reference import residual_budgeted_candidate as solver
    output=Path('/output');assert not (output/'demo-summary.json').exists()
    counts={}
    def evaluator(name,kind):
        counts[name]={'entered':0,'completed':0,'failed':0}
        def fake(dm):
            counts[name]['entered']+=1
            try:
                if kind=='large':
                    f=np.diag(np.arange(len(dm),dtype=float));f[0,8]=f[8,0]=1.
                    one,coulomb=float(np.sum(f*dm.T)),0.
                else:
                    z=4*(dm[0,0]/2-.5);f=np.array([[z,1.],[1.,-z]])
                    one,coulomb=float(2*dm[0,1]),float(.5*(dm[0,0]-dm[1,1])**2)
                value={'density_id':solver.density_id(dm),'operator_source':solver.TRUE_OPERATOR,
                    'fock':f,'total_energy':one+coulomb,'one_electron_energy':one,'coulomb_energy':coulomb,
                    'exact_exchange_energy':0.,'semilocal_xc_energy':0.,'nuclear_repulsion':0.}
            except BaseException:
                counts[name]['failed']+=1;raise
            counts[name]['completed']+=1;return value
        return fake
    def one_group(fun,start,*,jac,**options):
        fun(start);jac(start)
        return SimpleNamespace(x=start.copy(),status=1,nfev=1,njev=1,message='Controlled synthetic single-J driver')
    def refused_followup(fun,start,*,jac,**options):
        fun(start);jac(start);fun(np.array([.02]))
        raise AssertionError('Budget must reject the new objective before entering the evaluator')
    def pack(directory,result):
        arrays={}
        def visit(value,trail='root'):
            if isinstance(value,np.ndarray):
                key='array_'+str(len(arrays));a=value.copy();arrays[key]=a
                assert np.isfinite(a).all()
                return {'npz_member':key,'shape':list(a.shape),'dtype':a.dtype.str,
                    'sha256':hashlib.sha256(a.tobytes(order='C')).hexdigest(),'finite':True,'record_path':trail}
            if isinstance(value,np.generic):return visit(value.item(),trail)
            if isinstance(value,dict):return {str(k):visit(v,trail+'.'+str(k)) for k,v in value.items()}
            if isinstance(value,(tuple,list)):return [visit(v,trail+'['+str(i)+']') for i,v in enumerate(value)]
            return value
        encoded=visit(result);archive=directory/'snapshots.npz'
        with archive.open('xb') as stream:np.savez_compressed(stream,**arrays)
        encoded['raw_array_archive']={'file':archive.name,'size_bytes':archive.stat().st_size,
            'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
        save(directory/'result.json',encoded)
        # Verify persisted archive and every member, including snapshot roles.
        with np.load(archive,allow_pickle=False) as loaded:
            for key,a in arrays.items():assert np.array_equal(loaded[key],a)
        return {'archive_members_verified':len(arrays),'result_sha256':hashlib.sha256((directory/'result.json').read_bytes()).hexdigest(),
                'archive_sha256':encoded['raw_array_archive']['sha256']}
    cases=[]
    for name,limit,kind,driver in (
            ('insufficient_whole_J_48vars',99,'large',one_group),
            ('admitted_whole_J_48vars',100,'large',one_group),
            ('budget_returned_seed_vs_best_sample',6,'unstable',refused_followup)):
        directory=output/name;directory.mkdir()
        if kind=='large':dm=np.diag([2.]*8+[0.]*6);electrons=16
        else:
            vector=np.array([np.cos(-.6),np.sin(-.6)]);dm=2*np.outer(vector,vector);electrons=2
        with patch.object(solver,'least_squares',side_effect=driver):
            result=solver.solve_budgeted_candidate(density=dm,overlap=np.eye(len(dm)),electrons=electrons,
                evaluate=evaluator(name,kind),initialization_policy='REQUIRE_EXISTING_MASKED_PROJECTOR',
                maximum_evaluations=limit,maximum_iterations=1)
        assert not result['engine_qualified'] and result['delta_hartree'] is None and not result['production_activation']
        assert counts[name]['entered']==counts[name]['completed']==result['evaluation_count']
        assert counts[name]['failed']==0
        if limit==99:
            assert result['evaluation_count']==2 and result['budget_admissions'][0]['actual_callbacks']==0
            assert result['budget_admissions'][0]['required_callbacks']==96
        elif limit==100:
            assert result['evaluation_count']==99 and result['budget_admissions'][0]['actual_callbacks']==96
        else:
            assert result['evaluation_count']==4 and result['returned_density']['density_id']==solver.density_id(dm)
            assert result['best_any_sample']['density_id']!=solver.density_id(dm)
            assert result['endpoint_gate'] is None
        archived=pack(directory,result)
        cases.append({'case':name,'kind':'SYNTHETIC_ARRAYS_NO_MOLECULE_OR_GEOMETRY',
            'driver':'CONTROLLED_SINGLE_CHART_INTERFACE_NOT_A_MOLECULAR_OPTIMIZATION',
            'stop_reason':result['stop_reason'],'callback_limit':limit,'fake_callback_counts':counts[name],
            'jacobian_admissions':[dict(row) for row in result['budget_admissions']],
            'tail_execution':dict(result['tail_execution']),'archive_verification':archived,
            'snapshot_role_ids':{key:None if result[key] is None else result[key].get('snapshot_id',result[key].get('matched_snapshot_id'))
                for key in ('optimizer_base','best_base','best_any_sample','last_complete_jacobian_base','returned_density')},
            'scientific_qualification':'NOT_GRANTED','delta_hartree':None})
    changed=[label for owner,attribute,callback,label in bindings if getattr(owner,attribute) is not callback]
    assert not attempted and not changed
    record={'schema_version':'budget-recording-synthetic-demo-v1','status':'PASS_ENGINEERING_EXPORT_ONLY',
        'cases':cases,'guarded_operations':[b[3] for b in bindings],'forbidden_operation_attempts':attempted,
        'guard_bindings_changed':changed,'native_scientific_callbacks':{'entered':0,'completed':0,'failed':0},
        'new_molecular_F_calls':0,'new_scientific_budget':None,'compute_enabled':False,
        'private_scipy_api_version':solver.scipy_version,'old_scientific_records_modified':False}
    save(output/'demo-summary.json',record)
    print(json.dumps({'status':record['status'],'cases':len(cases),'fake_callbacks':[c['fake_callback_counts']['entered'] for c in cases],
        'real_scientific_calls':0}),flush=True)


if __name__=='__main__':main()
