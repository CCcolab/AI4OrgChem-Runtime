"""Production API probes on temporary synthetic records; no worker launch."""
from pathlib import Path
import hashlib,json,subprocess,sys,tempfile,unittest

ROOT=Path(__file__).resolve().parents[2]


class HostContracts(unittest.TestCase):
    def test_unknown_cleanup_holds_budget_and_blocks_concurrency(self):
        from runtime.high_cost_cases import budget
        identity={k:'a'*64 for k in ('profile_sha256','source_sha256','dependencies_sha256')}
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'synthetic-budget.json'
            budget.new_budget(p,['A','B'],*identity.values(),200)
            budget.reserve(p,'A',{'hard_wall_seconds':100},identity,'synthetic-A')
            result=budget.settle(p,'synthetic-A',2,False,'UNKNOWN_CLEANUP_ENGINEERING_FIXTURE')
            self.assertEqual(result['charged_seconds'],100)
            self.assertEqual(result['unresolved_units'],['A'])
            with self.assertRaisesRegex(budget.BudgetError,'unresolved'):
                budget.reserve(p,'B',{'hard_wall_seconds':50},identity,'synthetic-B')
            with self.assertRaisesRegex(budget.BudgetError,'resetting'):
                budget.new_budget(p,['A','B'],*identity.values(),300)

    def test_confirmed_cleanup_settles_once_only(self):
        from runtime.high_cost_cases import budget
        identity={k:'b'*64 for k in ('profile_sha256','source_sha256','dependencies_sha256')}
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'synthetic-budget.json'
            budget.new_budget(p,['A'],*identity.values(),100)
            budget.reserve(p,'A',{'hard_wall_seconds':100},identity,'synthetic-A')
            result=budget.settle(p,'synthetic-A',2,True,'ENGINEERING_FIXTURE_COMPLETE')
            self.assertEqual(result['charged_seconds'],2)
            with self.assertRaises(budget.BudgetError):budget.settle(p,'synthetic-A',2,True,'duplicate')

    def test_empty_p11_assembly_does_not_pass(self):
        from runtime.high_cost_cases.assembly import assemble
        r=assemble('P11',{})
        self.assertEqual((r['required_unit_count'],r['status']),(17,'BLOCKED_INCOMPLETE'))
        self.assertFalse(r['new_scientific_acceptance'])

    def test_empty_p12_assembly_does_not_pass(self):
        from runtime.high_cost_cases.assembly import assemble
        r=assemble('P12',{})
        self.assertEqual((r['required_unit_count'],r['status']),(61,'BLOCKED_INCOMPLETE'))
        self.assertFalse(r['new_numerical_assembly_accepted'])

    def test_zero_test_discovery_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'zero'
            r=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/run-public-review-regression.py'),
                '--output',str(p),'--pattern','no_public_tests_*.py'],capture_output=True,text=True,timeout=20)
            self.assertEqual(r.returncode,2)
            self.assertEqual(json.loads((p/'result.json').read_text('utf-8'))['status'],'ERROR')

    def test_orbital_cli_missing_input_records_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'new'
            r=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/review-canonical-orbitals.py'),
                '--npz',str(Path(tmp)/'absent.npz'),'--electron-count','2','--output',str(p)],
                capture_output=True,text=True,timeout=20)
            self.assertEqual(r.returncode,2)
            self.assertFalse(json.loads((p/'review.json').read_text('utf-8'))['full_orbital_qualification']['qualified'])

    def test_filtered_partial_discovery_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'partial'
            r=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/run-public-review-regression.py'),
                '--output',str(p),'--pattern','test_skill_examples.py'],capture_output=True,text=True,timeout=20)
            self.assertEqual(r.returncode,2)
            self.assertEqual(json.loads((p/'result.json').read_text('utf-8'))['status'],'ERROR')

    def test_orbital_cli_existing_output_is_not_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'sentinel').write_bytes(b'original')
            r=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/review-canonical-orbitals.py'),
                '--npz',str(p/'absent.npz'),'--electron-count','2','--output',str(p)],
                capture_output=True,text=True,timeout=20)
            self.assertEqual(r.returncode,2)
            self.assertEqual({x.name for x in p.iterdir()},{'sentinel'})

    def test_worker_source_lock_still_matches_original_engine(self):
        d=json.loads((ROOT/'locks/molecular-service-source.json').read_bytes())
        name='runtime/molecular_service/engine.py'
        self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),d['files'][name])

    def test_foreign_input_cannot_authorize_compute(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('_capabilities_contract',ROOT/'scripts/local-runtime-capabilities.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        d=json.loads((ROOT/'configs/runtime-capabilities-v2.json').read_bytes())
        d['declaration_grants_execution_authorization']=True
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'injected.json';p.write_text(json.dumps(d),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'cannot grant'):m.load_capabilities(p)
