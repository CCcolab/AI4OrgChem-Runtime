"""Local engineering tests; no new SCF or optimisation executed by this runner."""
from pathlib import Path
import argparse,json,sys,time,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from runtime.high_cost_cases import save
def main():
    if not (Path(__file__).resolve().parents[1]/'tests').is_dir():
        raise SystemExit('LOCAL_TEST_SUITE_REQUIRED: tests are retained locally and excluded from the public repository; no test PASS is granted.')
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('Fresh CI output directory required')
    a.output.mkdir(parents=True);start=time.monotonic()
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_high_cost*.py')
    with (a.output/'unittest.log').open('w',encoding='utf-8') as stream:r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    value={'schema':'high-cost-local-engineering-ci-v1','status':'PASS' if r.wasSuccessful() else 'FAIL','tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skipped':[reason for _,reason in r.skipped],'duration_seconds':time.monotonic()-start,'scientific_lane':'NOT_EXECUTED_BY_THIS_RUNNER','GitHub_Actions':'NOT_EXECUTED'}
    save(a.output/'ci-result.json',value);print(json.dumps(value));return 0 if r.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
