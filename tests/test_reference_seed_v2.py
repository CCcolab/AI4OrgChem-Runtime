"""Array-only seed oracles and refusals; no molecular or functional calls."""
import ast
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

from reference import seed_v2


class IndependentSeedV2Tests(unittest.TestCase):
    def fixture(self):
        coefficients = np.array([[1., 0., 0.], [0., .5, 0.], [0., 0., 1.]])
        occupations = np.array([2., 2., 0.])
        c0 = coefficients[:, :2]
        return {'density': 2. * c0 @ c0.T,
                'physical_overlap': np.diag([1., 4., 1.]),
                'masked_overlap': np.array([[2., .2, .1], [.2, 3., .15], [.1, .15, 1.2]]),
                'mo_coefficients': coefficients, 'mo_occupations': occupations, 'electrons': 4}

    def refusal(self, inputs):
        with self.assertRaises(seed_v2.SeedV2Error) as caught:
            seed_v2.prepare_seed_v2(**inputs)
        receipt = caught.exception.receipt
        self.assertEqual(receipt['status'], 'REFUSED')
        self.assertEqual(receipt['functional_calls'], 0)
        json.dumps(receipt, allow_nan=False)
        return caught.exception

    def test_closed_form_two_occupied_oracle(self):
        inputs = self.fixture()
        result = seed_v2.prepare_seed_v2(**inputs)
        # B=[[2,.1],[.1,.75]]; analytic 2x2 inverse, independent of solve.
        inverse = np.array([[.75, -.1], [-.1, 2.]]) / 1.49
        c0 = inputs['mo_coefficients'][:, :2]
        expected = 2. * c0 @ inverse @ c0.T
        np.testing.assert_allclose(result['density'], expected, rtol=0, atol=1e-14)
        np.testing.assert_allclose(result['coefficients'].T @ inputs['masked_overlap'] @ result['coefficients'],
                                   np.eye(2), rtol=0, atol=1e-14)
        receipt = result['receipt']
        self.assertEqual(receipt['status'], 'PASS_ARRAY_SEED_AND_REFERENCE_ENTRY_ONLY')
        self.assertTrue(all(item['passed'] for item in receipt['definition_checks'].values()))
        self.assertTrue(all(item['passed'] for item in receipt['solver_entry_checks'].values()))
        self.assertEqual(receipt['production_density_reconstruction'],
                         'NOT_IMPLEMENTED_IN_EXISTING_REFERENCE_ENTRY')
        self.assertFalse(receipt['scientific_approval'])
        self.assertEqual(receipt['final_endpoint_qualification'], 'NOT_EXECUTED')
        json.dumps(receipt, allow_nan=False)

    def test_one_occupied_explicit_normalization_oracle(self):
        c0 = np.array([[.6], [.8]])
        inputs = {'density': 2*c0@c0.T, 'physical_overlap': np.eye(2),
                  'masked_overlap': np.array([[2., .3], [.3, 1.]]),
                  'mo_coefficients': np.array([[.6, -.8], [.8, .6]]),
                  'mo_occupations': np.array([2., 0.]), 'electrons': 2}
        result = seed_v2.prepare_seed_v2(**inputs)
        gram = 2*.6**2 + 2*.3*.6*.8 + .8**2
        np.testing.assert_allclose(result['density'], 2*c0@c0.T/gram, rtol=0, atol=1e-14)

    def test_sign_permutation_and_occupied_rotation_leave_density(self):
        original = self.fixture()
        expected = seed_v2.prepare_seed_v2(**original)['density']
        angle = .73
        rotate = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
        variants = [np.diag([-1., 1.]), np.array([[0., 1.], [1., 0.]]), rotate]
        for change in variants:
            with self.subTest(change=change.tolist()):
                inputs = self.fixture()
                inputs['mo_coefficients'][:, :2] = inputs['mo_coefficients'][:, :2] @ change
                actual = seed_v2.prepare_seed_v2(**inputs)['density']
                np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-14)

    def test_atomic_basis_permutation_covariance(self):
        inputs = self.fixture()
        result = seed_v2.prepare_seed_v2(**inputs)['density']
        permutation = [2, 0, 1]
        for key in ('density', 'physical_overlap', 'masked_overlap'):
            inputs[key] = inputs[key][np.ix_(permutation, permutation)]
        inputs['mo_coefficients'] = inputs['mo_coefficients'][permutation]
        actual = seed_v2.prepare_seed_v2(**inputs)['density']
        np.testing.assert_allclose(actual, result[np.ix_(permutation, permutation)], rtol=0, atol=1e-14)

    def test_inputs_readonly_unchanged_and_output_not_aliased(self):
        inputs = self.fixture()
        snapshots = {key: value.copy() for key, value in inputs.items() if isinstance(value, np.ndarray)}
        for value in inputs.values():
            if isinstance(value, np.ndarray):
                value.setflags(write=False)
        result = seed_v2.prepare_seed_v2(**inputs)
        result['density'][0, 0] = 0.
        result['coefficients'][0, 0] = 0.
        for key, expected in snapshots.items():
            np.testing.assert_array_equal(inputs[key], expected)

    def test_density_reconstruction_refuses_mismatched_cache(self):
        inputs = self.fixture(); inputs['density'][0, 0] += 1e-6
        self.assertEqual(self.refusal(inputs).reason, 'ORDINARY_DENSITY_RECONSTRUCTION_FAILED')

    def test_nonorthonormal_ordinary_coefficients_refused(self):
        inputs = self.fixture(); inputs['mo_coefficients'][0, 0] *= 1.0001
        self.assertEqual(self.refusal(inputs).reason, 'PHYSICAL_OCCUPIED_ORTHOGONALITY_FAILED')

    def test_fractional_or_wrong_count_occupation_refused(self):
        for occupations in ([2., 1., 1.], [2., 0., 0.], [2., 2., 2.]):
            inputs = self.fixture(); inputs['mo_occupations'] = np.array(occupations)
            self.assertEqual(self.refusal(inputs).reason, 'ORDINARY_OCCUPATIONS_NOT_GLOBAL_2_0')

    def test_invalid_closed_shell_counts_refused(self):
        for count in (True, 3, 0, 6, 4., np.int64(4)):
            inputs = self.fixture(); inputs['electrons'] = count
            self.assertEqual(self.refusal(inputs).reason, 'CLOSED_SHELL_OCCUPATION_UNSUPPORTED')

    def test_rotation_dimension_limit_refused(self):
        n = 17
        inputs = {'density': np.diag([2.]*8+[0.]*9), 'physical_overlap': np.eye(n),
                  'masked_overlap': np.eye(n), 'mo_coefficients': np.eye(n),
                  'mo_occupations': np.array([2.]*8+[0.]*9), 'electrons': 16}
        self.assertEqual(self.refusal(inputs).reason, 'ORBITAL_ROTATION_VARIABLES_EXCEED_64')

    def test_nonfinite_nonreal_boolean_and_shape_refusals(self):
        for bad in (np.full((3, 3), np.nan), np.full((3, 3), np.inf),
                    np.eye(3).astype(bool), np.eye(3).astype(complex), np.ones((2, 3))):
            inputs = self.fixture(); inputs['density'] = bad
            self.refusal(inputs)
        inputs = self.fixture(); inputs['mo_coefficients'] = np.ones((3, 2))
        self.assertEqual(self.refusal(inputs).reason, 'ORDINARY_ARRAY_SHAPES_MISMATCH')

    def test_nonsymmetric_inputs_refused_without_repair(self):
        for key in ('density', 'physical_overlap', 'masked_overlap'):
            inputs = self.fixture(); inputs[key][0, 1] += 1e-6
            self.assertEqual(self.refusal(inputs).reason, key.upper()+'_SYMMETRY_FAILED')

    def test_indefinite_or_condition_failed_overlap_refused(self):
        for key in ('physical_overlap', 'masked_overlap'):
            inputs = self.fixture(); inputs[key] = np.diag([1., -1., 1.])
            self.assertEqual(self.refusal(inputs).reason, key.upper()+'_MINIMUM_EIGENVALUE_FAILED')
            inputs = self.fixture(); inputs[key] = np.diag([1., 1e-7, 1.])
            self.assertEqual(self.refusal(inputs).reason, key.upper()+'_CONDITION_NUMBER_FAILED')

    def test_occupied_gram_can_fail_despite_both_metric_limits(self):
        inputs = {'density': np.diag([2., 2e-6, 0.]),
                  'physical_overlap': np.diag([1., 1e6, 1.]),
                  'masked_overlap': np.diag([1e6, 1., 1.]),
                  'mo_coefficients': np.diag([1., 1e-3, 1.]),
                  'mo_occupations': np.array([2., 2., 0.]), 'electrons': 4}
        self.assertEqual(self.refusal(inputs).reason, 'OCCUPIED_GRAM_CONDITION_NUMBER_FAILED')

    def test_strict_whitened_gate_distinct_from_definition_checks(self):
        original = np.linalg.eigh
        def perturbed_whitening(value):
            eigenvalues, vectors = original(value)
            return eigenvalues, vectors * (1.+1e-10)
        with patch.object(np.linalg, 'eigh', side_effect=perturbed_whitening):
            error = self.refusal(self.fixture())
        self.assertEqual(error.reason, 'WHITE_PROJECTOR_TRACE_FAILED')
        self.assertTrue(all(item['passed'] for item in error.receipt['definition_checks'].values()))
        self.assertGreater(error.receipt['solver_entry_checks']['white_projector_trace']['value'], 1e-10)

    def test_independent_module_imports_and_no_functional_entry(self):
        source = Path(seed_v2.__file__).read_text(encoding='utf-8')
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [node.module or ''] if isinstance(node, ast.ImportFrom) else [item.name for item in node.names]
                self.assertFalse(any(name.startswith(('runtime', 'ai4orgchem', 'pyscf', 'reference.')) for name in names), names)
        for forbidden in ('nr_rks(', 'get_hcore(', 'get_ovlp(', '.kernel(', 'pinv(', 'clip('):
            self.assertNotIn(forbidden, source)


if __name__ == '__main__':
    unittest.main()
