"""Evidence lineage rejection tests: a new batch cannot erase old failures."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from runtime.user_molecule.solver_contract import verify_previous_evidence


class SolverLineageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = self.root/'result.json'
        self.payload.write_bytes(b'{"status":"FAIL"}\n')
        self.budget = {'runs':{'case':{'state':'SETTLED','observed_wall_seconds':3.5,
            'identity':{'mode':'SEQUENTIAL_ACCEPTANCE_BUNDLE_V1'}}}}
        self.save_budget()
        manifest = {'files':[{'path':'result.json','size_bytes':self.payload.stat().st_size,
            'sha256':hashlib.sha256(self.payload.read_bytes()).hexdigest()}]}
        (self.root/'FINAL_DELIVERY_MANIFEST.json').write_text(json.dumps(manifest),encoding='utf-8')
        self.contract = {'prior_evidence':{'evidence_root':str(self.root),
            'previous_scientific_attempts':1,
            'previous_manifest_sha256':self.digest('FINAL_DELIVERY_MANIFEST.json'),
            'previous_budget_sha256':self.digest('budget.json')}}

    def digest(self,name):
        return hashlib.sha256((self.root/name).read_bytes()).hexdigest()

    def save_budget(self):
        encoded = json.dumps(self.budget,sort_keys=True,separators=(',', ':'),ensure_ascii=False,allow_nan=False).encode()
        (self.root/'budget.json').write_text(json.dumps({**self.budget,
            'integrity_sha256':hashlib.sha256(encoded).hexdigest()}),encoding='utf-8')

    def test_unchanged_failed_history_can_be_referenced(self):
        result = verify_previous_evidence(self.contract)
        self.assertEqual(result['prior_scientific_attempts'],1)
        self.assertEqual(result['prior_consumed_seconds'],3.5)

    def test_failed_output_cannot_be_replaced(self):
        self.payload.write_bytes(b'{"status":"PASS"}\n')
        with self.assertRaisesRegex(ValueError,'payload changed'):
            verify_previous_evidence(self.contract)

    def test_prior_budget_cannot_be_reset(self):
        self.budget['runs'] = {}
        self.save_budget()
        with self.assertRaisesRegex(ValueError,'evidence changed'):
            verify_previous_evidence(self.contract)

    def test_unknown_termination_blocks_new_batch(self):
        self.budget['runs']['case']['state'] = 'RESERVED'
        self.save_budget()
        self.contract['prior_evidence']['previous_budget_sha256'] = self.digest('budget.json')
        with self.assertRaisesRegex(ValueError,'termination unresolved'):
            verify_previous_evidence(self.contract)

    def test_inconsistent_attempt_count_rejected(self):
        self.contract['prior_evidence']['previous_scientific_attempts'] = 2
        with self.assertRaisesRegex(ValueError,'attempt count'):
            verify_previous_evidence(self.contract)

    def test_bad_integrity_rejected_even_with_matching_file_hash(self):
        data = json.loads((self.root/'budget.json').read_text())
        data['runs']['case']['observed_wall_seconds'] = 0
        (self.root/'budget.json').write_text(json.dumps(data),encoding='utf-8')
        self.contract['prior_evidence']['previous_budget_sha256'] = self.digest('budget.json')
        with self.assertRaisesRegex(ValueError,'integrity mismatch'):
            verify_previous_evidence(self.contract)


if __name__ == '__main__':
    unittest.main()
