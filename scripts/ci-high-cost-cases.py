"""Local engineering tests; no new SCF or optimisation executed by this runner."""
from pathlib import Path
import argparse,json,sys,time,unittest,os,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from runtime.high_cost_cases import save
def main():
    if not (Path(__file__).resolve().parents[1]/'tests').is_dir():
        raise SystemExit('LOCAL_TEST_SUITE_REQUIRED: tests are retained locally and excluded from the public repository; no test PASS is granted.')
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('Fresh CI output directory required')
    if os.environ.get('AI4ORGCHEM_HIGH_COST_SCIENTIFIC_TESTS') not in (None,'','0'):
        raise ValueError('Scientific opt-in is incompatible with engineering CI')
    a.output.mkdir(parents=True);start=time.monotonic()
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_high_cost*.py')
    def leaves(value):
        for item in value:
            if isinstance(item,unittest.TestSuite):yield from leaves(item)
            else:yield item
    planned=[test.id() for test in leaves(suite)]
    sources={path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted((ROOT/'tests').glob('test_high_cost*.py'))}
    required={'test_high_cost_assembly','test_high_cost_budget','test_high_cost_contract','test_high_cost_guard','test_high_cost_p11','test_high_cost_p12','test_high_cost_supervisor'}
    if not planned or not required<={name.split('.')[0] for name in planned} or len(planned)!=len(set(planned)):
        save(a.output/'ci-result.json',{'status':'INCOMPLETE_DISCOVERY','tests_run':0,'planned_test_ids':planned,'required_groups':sorted(required),'scientific_lane':'NOT_EXECUTED_BY_THIS_RUNNER'})
        return 2
    actual=[]
    class AuditedResult(unittest.TextTestResult):
        def startTest(self,test):actual.append(test.id());super().startTest(test)
    with (a.output/'unittest.log').open('w',encoding='utf-8') as stream:r=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=AuditedResult).run(suite)
    complete=r.testsRun>len(r.skipped) and r.testsRun==len(planned) and actual==planned
    passed=complete and r.wasSuccessful() and not r.skipped
    value={'schema':'high-cost-local-engineering-ci-v1','status':'PASS' if passed else 'FAIL_OR_INCOMPLETE','tests_run':r.testsRun,'planned_test_ids':planned,'executed_test_ids':actual,'required_groups':sorted(required),'failures':len(r.failures),'errors':len(r.errors),'skipped':[reason for _,reason in r.skipped],'duration_seconds':time.monotonic()-start,'scientific_lane':'NOT_EXECUTED_BY_THIS_RUNNER','GitHub_Actions':'NOT_EXECUTED'}
    value['test_source_files']=sources
    save(a.output/'ci-result.json',value);print(json.dumps(value));return 0 if passed else 1
if __name__=='__main__':raise SystemExit(main())
