"""Prepare-only entry and selected saved-array checks, no scientific calls."""
import ast
import copy
import importlib.util
from pathlib import Path
from unittest import mock
import unittest

import numpy as np

from runtime.user_molecule.occupation_response import density_id
from runtime.user_molecule.occupied_space_seeds import array_identity


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT/'scripts/diagnose-user-molecule-occupied-space-root-worker.py'
SPEC = importlib.util.spec_from_file_location('occupied_space_root_preparation_worker', PATH)
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)


class OccupiedSpaceRootWorkerTests(unittest.TestCase):
    def fixture(self):
        d = np.diag([2., 2., 0., 0.])
        did = density_id(d)
        rows = [{'seed_index': i, 'angle_rad': angle, 'density': d.copy(), 'density_id': did}
            for i, angle in enumerate((-.25, -.1, .1, .25), 1)]
        return {'seeds': rows}, {'seed_index': 2, 'angle_rad': -.1,
            'density_id': did, 'array_identity': array_identity(d)}, did

    def test_selected_output_is_exact_saved_bytes_owned_and_readonly(self):
        family, declared, did = self.fixture()
        original = family['seeds'][1]['density'].copy()
        with mock.patch.object(worker, 'SELECTED_DENSITY_ID', did):
            selected = worker.select_saved_initial(family, declared)
        np.testing.assert_array_equal(selected, original)
        self.assertFalse(selected.flags.writeable)
        self.assertFalse(np.shares_memory(selected, family['seeds'][1]['density']))
        family['seeds'][1]['density'][:] = 777
        np.testing.assert_array_equal(selected, original)

    def test_wrong_index_angle_or_domain_identity_cannot_select_another_point(self):
        family, declared, did = self.fixture()
        with mock.patch.object(worker, 'SELECTED_DENSITY_ID', did):
            for changed in ({'seed_index': 1}, {'angle_rad': .1}, {'density_id': 'e'*64}):
                with self.subTest(changed=changed), self.assertRaises(ValueError):
                    worker.select_saved_initial(family, dict(declared, **changed))
            altered = copy.deepcopy(family); altered['seeds'][1]['density'][0, 0] = 1.9
            with self.assertRaises(ValueError): worker.select_saved_initial(altered, declared)

    def test_incomplete_family_saved_row_or_actual_array_metadata_is_refused(self):
        family, declared, did = self.fixture()
        with mock.patch.object(worker, 'SELECTED_DENSITY_ID', did):
            short = copy.deepcopy(family); short['seeds'].pop()
            wrongrow = copy.deepcopy(family); wrongrow['seeds'][1]['angle_rad'] = -.25
            for altered in (short, wrongrow):
                with self.assertRaises(ValueError): worker.select_saved_initial(altered, declared)
            for field, value in (('shape', [3, 3]), ('dtype', '>f8'), ('sha256', 'e'*64)):
                changed = copy.deepcopy(declared); changed['array_identity'][field] = value
                with self.subTest(field=field), self.assertRaises(ValueError): worker.select_saved_initial(family, changed)

    def test_missing_prepare_only_is_rejected_before_contract_or_scientific_worker(self):
        with mock.patch('sys.argv', ['root-preparation-worker']), mock.patch.object(worker, 'preparation_worker') as run:
            with self.assertRaisesRegex(ValueError, 'only --prepare-only'):
                worker.main()
            run.assert_not_called()

    def test_worker_has_no_live_budget_or_evaluation_dispatch(self):
        # This is a bounded absence check for the deployed CLI, not a numerical
        # proof. Future live orchestration must replace this explicit contract.
        tree = ast.parse(PATH.read_text(encoding='utf-8'))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        self.assertFalse(any(isinstance(node.func, ast.Attribute) and node.func.attr in ('evaluate', 'run') for node in calls))
        self.assertFalse(any(isinstance(node.func, ast.Name) and node.func.id in
            ('ConditionalCallbackBudget', 'solve_occupied_space_root_candidate') for node in calls))


if __name__ == '__main__':
    unittest.main()
