"""Local engineering CI only. Real bounded science is a separate live lane."""
import argparse
import json
from pathlib import Path
import sys
import time
import unittest
import hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from runtime.protocol_cases import verify_source,digest,SOURCE_LOCK,DEPENDENCY_LOCK,save
def main():
    if not (Path(__file__).resolve().parents[1]/'tests').is_dir():
        raise SystemExit('LOCAL_TEST_SUITE_REQUIRED: tests are retained locally and excluded from the public repository; no test PASS is granted.')
    p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    verify_source(); start=time.monotonic();a.report.parent.mkdir(parents=True,exist_ok=True)
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_protocol_cases*.py')
    def leaves(value):
        for item in value:
            if isinstance(item,unittest.TestSuite):yield from leaves(item)
            else:yield item
    planned=[test.id() for test in leaves(suite)]
    required={'test_protocol_cases_guard','test_protocol_cases_p03_p06','test_protocol_cases_p07_p08','test_protocol_cases_p09_p10','test_protocol_cases_reporting'}
    if not planned or not required<={name.split('.')[0] for name in planned} or len(planned)!=len(set(planned)):
        save(a.report,{'status':'INCOMPLETE_DISCOVERY','tests_run':0,'planned_test_ids':planned,'required_groups':sorted(required),'scientific_lane':'NOT_EXECUTED_BY_THIS_RUNNER'})
        return 2
    actual=[]
    class AuditedResult(unittest.TextTestResult):
        def startTest(self,test):actual.append(test.id());super().startTest(test)
    result=unittest.TextTestRunner(verbosity=2,resultclass=AuditedResult).run(suite)
    complete=result.testsRun>0 and result.testsRun==len(planned) and actual==planned
    report={'schema':'protocol-cases-local-engineering-ci-v1','status':'PASS' if complete and result.wasSuccessful() and not result.skipped else 'FAIL_OR_INCOMPLETE',
            'planned_test_ids':planned,'executed_test_ids':actual,'required_groups':sorted(required),
            'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':[{'test':test.id(),'reason':reason} for test,reason in result.skipped],
            'duration_seconds':time.monotonic()-start,'source_lock_sha256':digest(SOURCE_LOCK),'dependency_lock_sha256':digest(DEPENDENCY_LOCK),
            'scientific_lane':'NOT_EXECUTED_BY_THIS_RUNNER','fake_guard_or_mock_live_calls_are_not_scientific_results':True,
            'GitHub_Actions':'NOT_EXECUTED'}
    report['test_source_files']={path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted((ROOT/'tests').glob('test_protocol_cases*.py'))}
    save(a.report,report); return 0 if report['status']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
