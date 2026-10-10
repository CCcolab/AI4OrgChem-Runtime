"""Local engineering CI only. Real bounded science is a separate live lane."""
import argparse
import json
from pathlib import Path
import sys
import time
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from runtime.protocol_cases import verify_source,digest,SOURCE_LOCK,DEPENDENCY_LOCK,save
def main():
    if not (Path(__file__).resolve().parents[1]/'tests').is_dir():
        raise SystemExit('LOCAL_TEST_SUITE_REQUIRED: tests are retained locally and excluded from the public repository; no test PASS is granted.')
    p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    verify_source(); start=time.monotonic()
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_protocol_cases*.py')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report={'schema':'protocol-cases-local-engineering-ci-v1','status':'PASS' if result.wasSuccessful() and not result.skipped else 'FAIL_OR_INCOMPLETE',
            'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':result.skipped,
            'duration_seconds':time.monotonic()-start,'source_lock_sha256':digest(SOURCE_LOCK),'dependency_lock_sha256':digest(DEPENDENCY_LOCK),
            'scientific_lane':'NOT_EXECUTED_BY_THIS_RUNNER','fake_guard_or_mock_live_calls_are_not_scientific_results':True,
            'GitHub_Actions':'NOT_EXECUTED'}
    save(a.report,report); return 0 if report['status']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
