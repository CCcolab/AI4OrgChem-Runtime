"""Synthetic state/receipt tests, not real reviewer approval or scientific results."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from runtime.user_molecule.research import assess, BINDINGS
from runtime.user_molecule.records import report


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.record = {'input_status':'VALID','execution_status':'COMPLETED',
            'numerical_status':'NUMERICALLY_QUALIFIED','research_status':'QUALIFIED_WITHIN_SCOPE',
            'comparison_available':True,'delta_hartree':-.5,'delta_kcal_mol':-313.75473703155,
            'ordinary':{'converged':True,'total_energy_hartree':-2.},
            'conditional':{'converged':True,'total_energy_hartree':-1.5},
            'ordinary_tests':{'energy':True},'conditional_tests':{'energy':True},
            'identities':{key:'synthetic-unit-test-only-'+key for key in BINDINGS},'reasons':[]}
        self.request = {'research_question':'合成测试', 'calculation_profile':'research-b3lypg-631gd-grid3-v1',
                        'fragments':[{'id':'A','carbon_atom_indices_1based':[1]},{'id':'B','carbon_atom_indices_1based':[2]}]}

    def test_no_real_scopes_registered(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads((root/'validation/user-molecule/w06/research-scope-registry.json').read_text())
        self.assertEqual(registry['scopes'], []); self.assertIsNone(registry['reviewer'])
        self.assertFalse(registry['production_activation'])

    def test_bare_qualified_string_cannot_approve_research(self):
        result = assess(self.record, self.request['calculation_profile'])
        self.assertEqual(result['research_status'], 'NOT_REVIEWED')
        self.assertEqual(result['method_status'], 'NOT_REVIEWED')

    def test_pilot_success_is_technical_only(self):
        self.assertEqual(assess(self.record,'pilot-b3lypg-sto3g-grid2-v1')['research_status'], 'TECHNICAL_ONLY')

    def test_required_failure_partial_state_nonfinite_and_empty_tests(self):
        for state in ('ordinary','conditional'):
            for mutation in ('convergence','tests','nonfinite','missing'):
                value = copy.deepcopy(self.record)
                if mutation == 'convergence': value[state]['converged'] = False
                if mutation == 'tests': value[state+'_tests'] = {}
                if mutation == 'nonfinite': value[state]['total_energy_hartree'] = float('nan')
                if mutation == 'missing': del value[state]
                with self.subTest(state=state,mutation=mutation):
                    self.assertEqual(assess(value,'pilot-b3lypg-sto3g-grid2-v1')['research_status'], 'NOT_QUALIFIED')
                    brief = report(value, self.request)
                    self.assertIn('比较可用：False', brief)
                    self.assertIn('差值 Eordinary−Econditional (Eh)：未提供/不可用', brief)

    def test_failed_or_blocked_execution_and_wrong_energy_identity(self):
        for status in ('FAILED','BLOCKED','NOT_EXECUTED'):
            value = copy.deepcopy(self.record); value['execution_status'] = status
            self.assertEqual(assess(value,self.request['calculation_profile'])['research_status'],'NOT_QUALIFIED')
        value = copy.deepcopy(self.record); value['delta_hartree'] = .5
        self.assertEqual(assess(value,self.request['calculation_profile'])['research_status'],'NOT_QUALIFIED')
        value = copy.deepcopy(self.record); value['delta_kcal_mol'] = -.5
        self.assertEqual(assess(value,self.request['calculation_profile'])['research_status'],'NOT_QUALIFIED')
        self.assertEqual(assess(self.record,'pilot-unregistered')['research_status'],'NOT_QUALIFIED')

    def synthetic_registry(self, root):
        bindings = self.record['identities']
        scope = {'scope_id':'SYNTHETIC_UNIT_TEST_ONLY','scope_version':'1',
                 'profile_id':self.request['calculation_profile'],'bindings':bindings}
        for key in ('method_review','acceptance','complete_reference','resource_review'):
            value = {'purpose':key,'status':'PASS','profile_id':scope['profile_id'],'bindings':bindings}
            if key == 'method_review':
                value.update(reviewer='SYNTHETIC UNIT TEST',responsibility='TEST ONLY',approved_at='TEST ONLY',
                    allowed_interpretation='TEST ONLY',interpretation_id='CONDITIONAL_FIXED_POINT_FUNCTIONAL')
            if key == 'acceptance':
                value.update(criteria={f'A{i:02d}':'PASS' for i in range(1,19)},new_systems=['synthetic1','synthetic2'])
            if key == 'complete_reference':
                value.update(independent_core_import_audit='PASS',numerical_execution='PASS',
                             threshold_version='TEST ONLY',reference_commit='TEST ONLY')
            if key == 'resource_review':
                value.update(request_nao=2,tested_maximum_nao=2,peak_calibration='PASS',bounded_budget_authorized=True)
            path = root/(key+'.json'); raw = json.dumps(value,sort_keys=True).encode()
            path.write_bytes(raw); scope[key] = {'path':path.name,'sha256':hashlib.sha256(raw).hexdigest()}
        return {'scopes':[scope]}

    def test_exact_scope_receipts_and_no_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); registry = self.synthetic_registry(root)
            before = copy.deepcopy((self.record,registry))
            result = assess(self.record,self.request['calculation_profile'],registry,root)
            self.assertEqual(result['research_status'],'QUALIFIED_WITHIN_SCOPE')
            self.assertEqual(result['scope_id'],'SYNTHETIC_UNIT_TEST_ONLY')
            self.assertEqual((self.record,registry), before)
            # The production-candidate report deliberately never loads these receipts.
            self.assertIn('研究资格：NOT_REVIEWED', report(self.record,self.request))

    def test_changed_each_identity_never_inherits_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); registry=self.synthetic_registry(root)
            for key in BINDINGS:
                value=copy.deepcopy(self.record); value['identities'][key]='CHANGED'
                with self.subTest(key=key):
                    self.assertEqual(assess(value,self.request['calculation_profile'],registry,root)['research_status'],'NOT_REVIEWED')

    def test_tampered_missing_ambiguous_or_escaped_receipt_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); registry=self.synthetic_registry(root)
            for mode in ('tampered','missing','escaped','ambiguous'):
                test=copy.deepcopy(registry)
                if mode=='tampered': test['scopes'][0]['acceptance']['sha256']='0'*64
                if mode=='missing': del test['scopes'][0]['complete_reference']
                if mode=='escaped': test['scopes'][0]['acceptance']['path']='../outside.json'
                if mode=='ambiguous': test['scopes'].append(copy.deepcopy(test['scopes'][0]))
                with self.subTest(mode=mode):
                    self.assertNotEqual(assess(self.record,self.request['calculation_profile'],test,root)['research_status'],'QUALIFIED_WITHIN_SCOPE')

    def test_missing_actual_reference_or_budget_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for key, field, value in (('complete_reference','numerical_execution','NOT_EXECUTED'),
                ('resource_review','bounded_budget_authorized',False),('acceptance','new_systems',['same','same'])):
                registry=self.synthetic_registry(root); path=root/registry['scopes'][0][key]['path']
                receipt=json.loads(path.read_text()); receipt[field]=value
                raw=json.dumps(receipt).encode(); path.write_bytes(raw)
                registry['scopes'][0][key]['sha256']=hashlib.sha256(raw).hexdigest()
                self.assertNotEqual(assess(self.record,self.request['calculation_profile'],registry,root)['research_status'],'QUALIFIED_WITHIN_SCOPE')

    def test_brief_request_check_sign_limits_and_no_html_injection(self):
        self.request['research_question']='<script>bad</script>\n# arbitrary heading'
        brief=report(self.record,self.request)
        self.assertNotIn('<script>',brief)
        self.assertNotIn('\n# arbitrary',brief)
        self.assertIn('A=[1]',brief); self.assertIn('B=[2]',brief)
        self.assertIn('Eordinary−Econditional',brief); self.assertIn('-0.5',brief)
        self.assertIn('不是单键能',brief); self.assertIn('不支持恢复运行',brief)
        self.assertIn('NOT_ESTABLISHED',brief)
        check=report({'input_status':'VALID','compute_eligible':False,'reasons':['BLOCKED']},self.request)
        self.assertIn('研究资格：NOT_REVIEWED',check); self.assertIn('比较可用：False',check)


if __name__ == '__main__':
    unittest.main()
