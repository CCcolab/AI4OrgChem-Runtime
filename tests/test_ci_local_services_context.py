"""Runner provenance must not confuse local mocks with a real remote workflow."""
from pathlib import Path
import importlib.util
import unittest

path=Path(__file__).resolve().parents[1]/'scripts/ci-unit-local-services.py'
spec=importlib.util.spec_from_file_location('local_services_ci_context',path)
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

class ExecutionContextTests(unittest.TestCase):
    def test_local_does_not_claim_remote_execution(self):
        result=runner.execution_context({'GITHUB_SHA':'local-value'})
        self.assertEqual(result['remote_GitHub_Actions'],'NOT_EXECUTED')
        self.assertEqual(result['execution_context']['platform'],'LOCAL')
        self.assertIsNone(result['execution_context']['commit'])

    def test_identified_actions_keeps_job_scope_and_identity(self):
        environment={'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'example/runtime',
                     'GITHUB_SHA':'a'*40,'GITHUB_RUN_ID':'123','GITHUB_JOB':'local-service-contracts',
                     'GITHUB_RUN_ATTEMPT':'2','GITHUB_WORKFLOW':'Candidate runtime validation'}
        result=runner.execution_context(environment)
        self.assertEqual(result['remote_GitHub_Actions'],'EXECUTED_THIS_JOB_IN_DECLARED_ACTIONS_ENV')
        self.assertEqual(result['execution_context']['run_id'],'123')
        self.assertEqual(result['execution_context']['run_attempt'],'2')
        self.assertIn('NOT_OVERALL_WORKFLOW',result['execution_context']['scope'])
        self.assertIn('NOT_AUTHENTICATION',result['execution_context']['basis'])
        self.assertEqual(environment['GITHUB_ACTIONS'],'true')

    def test_unidentified_actions_is_unknown(self):
        result=runner.execution_context({'GITHUB_ACTIONS':'true','GITHUB_SHA':'a'*40})
        self.assertEqual(result['remote_GitHub_Actions'],'UNKNOWN_UNBOUND_ACTIONS_DECLARATION')
        self.assertFalse(result['execution_context']['actions_identity_present'])

    def test_false_actions_flag_stays_local(self):
        result=runner.execution_context({'GITHUB_ACTIONS':'false','GITHUB_RUN_ID':'123'})
        self.assertEqual(result['remote_GitHub_Actions'],'NOT_EXECUTED')
        self.assertEqual(result['execution_context']['platform'],'LOCAL')

if __name__=='__main__':unittest.main()
