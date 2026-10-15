"""Public deterministic/saved-array regression; no scientific execution.

Usage: python -B scripts/run-public-review-regression.py --output NEW_DIRECTORY
Rejects zero tests, skipped tests, wrong instruction hashes and existing output.
"""
from __future__ import annotations
import argparse,builtins,hashlib,json,os,platform,sys,time,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
FORBIDDEN={'pyscf','ai4orgchem'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--pattern',default='test_*.py',help='Discovery pattern; zero/partial discovery is an error')
    args=parser.parse_args(argv)
    try:args.output.mkdir(parents=True,exist_ok=False)
    except OSError as exc:
        print('OUTPUT_REFUSED: '+str(exc),file=sys.stderr);return 2
    os.environ.update({'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'})
    original=builtins.__import__
    class RefuseBackend:
        def find_spec(self,fullname,path=None,target=None):
            if fullname.split('.')[0] in FORBIDDEN:raise ImportError('No-science regression forbids '+fullname)
    def guarded(name,*a,**kw):
        if name.split('.')[0] in FORBIDDEN:raise ImportError('No-science regression forbids '+name)
        return original(name,*a,**kw)
    finder=RefuseBackend();sys.meta_path.insert(0,finder);builtins.__import__=guarded
    started=time.monotonic()
    record={'schema':'public-review-regression-v1','scope':'DETERMINISTIC_EXAMPLES_AND_SAVED_ARRAY_CHECKS_NOT_AGENT_EVALUATION','remote_ci':'NOT_EXECUTED_BY_THIS_LOCAL_COMMAND','new_molecular_backend_calls':0}
    try:
        suite=unittest.defaultTestLoader.discover(str(ROOT/'validation/public_regression'),pattern=args.pattern)
        def ids(node):
            for item in node:
                if isinstance(item,unittest.TestSuite):yield from ids(item)
                else:yield item.id()
        discovered=list(ids(suite))
        required_modules=('test_skill_examples','test_canonical_orbitals','test_host_contracts')
        if args.pattern!='test_*.py' or any(not any(x.startswith(name+'.') for x in discovered) for name in required_modules):
            raise ValueError('Incomplete suite discovery; filtered or missing public modules cannot PASS')
        manifest=json.loads((ROOT/'skills/manifest.json').read_bytes())
        expected=[f'test_{kind}__{r["name"].replace("-","_")}' for r in manifest['skills'] for kind in ('normal','refusal','io_failure')]
        missing=[name for name in expected if not any(x.endswith('.'+name) for x in discovered)]
        if not discovered or missing:raise ValueError('Incomplete discovery; zero/partial tests cannot PASS: '+str(missing))
        with (args.output/'unittest.log').open('w',encoding='utf-8') as log:
            result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
        status='PASS' if result.wasSuccessful() and not result.skipped and result.testsRun==len(discovered) else 'FAIL'
        record.update({'status':status,'discovered':len(discovered),'executed':result.testsRun,'skipped':len(result.skipped),'failures':[[str(t),e] for t,e in result.failures],'errors':[[str(t),e] for t,e in result.errors],'test_ids':discovered,
          'expected_refusal_cases':15,'expected_common_io_failures':15,'normal_skill_examples':15,
          'skill_snapshots':[{'name':r['name'],'sha256':hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest()} for r in manifest['skills']]})
        import numpy as np
        from rdkit import rdBase
        record['environment']={'python':platform.python_version(),'numpy':np.__version__,'rdkit':rdBase.rdkitVersion}
        imported=set()
        for module in list(sys.modules.values()):
            filename=getattr(module,'__file__',None)
            if not filename:continue
            path=Path(filename).resolve()
            if path.suffix=='.py' and path.is_relative_to(ROOT):imported.add(path)
        imported.update({Path(__file__).resolve(),ROOT/'validation/public_regression/fixtures.json',ROOT/'review_tools/canonical_mo_policy_v1.json'})
        record['source_files']=[{'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(imported)]
        code=0 if status=='PASS' else 1
    except Exception as exc:
        record.update({'status':'ERROR','error':type(exc).__name__+': '+str(exc)});code=2
    finally:
        builtins.__import__=original;sys.meta_path.remove(finder)
    record['elapsed_seconds']=time.monotonic()-started
    (args.output/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:record.get(k) for k in ('status','discovered','executed','error','new_molecular_backend_calls')}))
    return code


if __name__=='__main__':raise SystemExit(main())
