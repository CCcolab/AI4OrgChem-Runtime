"""Deterministic occupied-space seed tests, NumPy arrays and zero F only."""
import inspect
import unittest
from unittest import mock

import numpy as np

from runtime.user_molecule import occupied_space_seeds as seeds


class OccupiedSpaceSeedTests(unittest.TestCase):
    def setUp(self):
        self.d = np.diag([2., 2., 0., 0.])
        self.s = np.eye(4)
        self.occ = np.array([0., 1., 0., 0.])
        self.vir = np.array([0., 0., 1., 0.])
        self.angles = [.1, -.1, .25, -.25]

    def prepare(self, **changes):
        arguments = dict(density=self.d, masked_overlap=self.s,
            occupied_anchor=self.occ, virtual_anchor=self.vir,
            angles=self.angles, electrons=4, expected_density_id=seeds.density_id(self.d))
        arguments.update(changes)
        return seeds.prepare_occupied_space_seeds(**arguments)

    def test_four_explicit_rotations_follow_projector_formula_and_preserve_strict_manifold(self):
        result = self.prepare()
        self.assertEqual(result['angles_rad'], tuple(self.angles))
        p = .5*self.d
        for row, angle in zip(result['seeds'], self.angles):
            t = np.cos(angle)*self.occ+np.sin(angle)*self.vir
            expected = 2*(p-np.outer(self.occ, self.occ)+np.outer(t, t))
            np.testing.assert_allclose(row['density'], expected, rtol=0, atol=1e-15)
            self.assertEqual(row['density_id'], seeds.density_id(row['density']))
            self.assertAlmostEqual(row['admission']['masked_metric_electron_count'], 4)
            self.assertLessEqual(row['admission']['whitened_absolute_idempotency'], 1e-10)
            self.assertLessEqual(row['admission']['whitened_trace_error'], 1e-10)
            self.assertLessEqual(row['admission']['production_density_reconstruction_relative'], 1e-10)
            self.assertGreaterEqual(row['admission']['whitened_minimum_eigenvalue'], -1e-10)
            self.assertAlmostEqual(row['column_space_change']['whitened_projector_difference_frobenius'],
                np.sqrt(2)*abs(np.sin(angle)), places=14)
            self.assertAlmostEqual(row['column_space_change']['largest_projector_difference_singular_value'],
                abs(np.sin(angle)), places=14)

    def test_nonorthogonal_metric_uses_whitened_anchors_and_density_reconstruction(self):
        a = np.array([[2., .2, 0., .1], [.2, 1.5, .1, 0.], [0., .1, 1.2, .1], [.1, 0., .1, 1.]])
        self.s = a@a.T
        sw, sv = np.linalg.eigh(self.s)
        inverse = (sv/np.sqrt(sw))@sv.T
        half = (sv*np.sqrt(sw))@sv.T
        self.d = inverse@self.d@inverse
        self.occ, self.vir = inverse@self.occ, inverse@self.vir
        result = self.prepare(expected_overlap_identity=seeds.array_identity(self.s))
        for row in result['seeds']:
            white = .5*half@row['density']@half
            np.testing.assert_allclose(white@white, white, rtol=0, atol=1e-14)
            self.assertAlmostEqual(float(np.trace(self.s@row['density'])), 4)
        self.assertLessEqual(result['directions']['occupied_membership_residual'], 1e-10)
        self.assertLessEqual(result['directions']['virtual_membership_residual'], 1e-10)
        self.assertTrue(result['source']['expected_overlap_identity_supplied'])

    def test_global_rotation_can_mix_sigma_pi_and_reports_actual_occupied_space_change(self):
        result = self.prepare()
        positive, negative = result['seeds'][:2]
        self.assertGreater(positive['density'][1, 2], 0)
        self.assertLess(negative['density'][1, 2], 0)
        self.assertLess(positive['density'][1, 1], self.d[1, 1])
        self.assertGreater(positive['density'][2, 2], self.d[2, 2])
        self.assertTrue(positive['column_space_change']['observed_changed'])
        self.assertFalse(positive['column_space_change']['base_occupied_column_space_preserved'])
        self.assertFalse(result['ordinary_occupied_space_preservation_claim'])
        self.assertFalse(result['new_final_occupation_rule'])
        self.assertEqual(positive['density'][0, 0], 2)

    def test_orthogonal_ao_basis_rotation_is_covariant_with_transformed_anchors(self):
        base = self.prepare()
        q, _ = np.linalg.qr(np.array([[1., 2., 3., 1.], [2., 1., 0., 4.],
            [0., 3., 1., 2.], [3., 0., 2., 1.]]))
        d, s = q.T@self.d@q, q.T@self.s@q
        transformed = self.prepare(density=d, masked_overlap=s,
            occupied_anchor=q.T@self.occ, virtual_anchor=q.T@self.vir,
            expected_density_id=seeds.density_id(d))
        for original, rotated in zip(base['seeds'], transformed['seeds']):
            np.testing.assert_allclose(rotated['density'], q.T@original['density']@q, rtol=0, atol=3e-14)

    def test_anchor_sign_conventions_are_explicit_and_double_flip_preserves_densities(self):
        base = self.prepare()
        both = self.prepare(occupied_anchor=-self.occ, virtual_anchor=-self.vir)
        one = self.prepare(occupied_anchor=-self.occ)
        for left, right in zip(base['seeds'], both['seeds']):
            np.testing.assert_array_equal(left['density'], right['density'])
        np.testing.assert_array_equal(one['seeds'][0]['density'], base['seeds'][1]['density'])
        np.testing.assert_array_equal(one['seeds'][2]['density'], base['seeds'][3]['density'])

    def test_positive_anchor_scaling_preserves_directions_but_records_source_identity_and_metric_norm(self):
        base = self.prepare()
        scaled = self.prepare(occupied_anchor=3*self.occ, virtual_anchor=7*self.vir)
        for left, right in zip(base['seeds'], scaled['seeds']):
            np.testing.assert_array_equal(left['density'], right['density'])
        self.assertNotEqual(base['source']['occupied_anchor_identity'], scaled['source']['occupied_anchor_identity'])
        self.assertEqual(scaled['directions']['occupied_anchor_masked_metric_norm'], 3)
        self.assertEqual(scaled['directions']['virtual_anchor_masked_metric_norm'], 7)
        self.assertEqual(scaled['directions']['occupied_projection_fraction_of_metric_anchor'], 1)
        self.assertEqual(scaled['directions']['virtual_projection_fraction_of_metric_anchor'], 1)

    def test_zero_projected_directions_and_invalid_ao_vectors_are_refused(self):
        invalid = ({'occupied_anchor': self.vir}, {'virtual_anchor': self.occ},
            {'occupied_anchor': np.zeros(4)}, {'virtual_anchor': np.zeros(4)},
            {'occupied_anchor': np.ones((4, 1))}, {'virtual_anchor': np.ones(3)},
            {'occupied_anchor': np.full(4, np.nan)}, {'virtual_anchor': np.ones(4, dtype=bool)},
            {'occupied_anchor': np.ones(4, dtype=complex)})
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError): self.prepare(**changes)

    def test_numerically_tiny_projection_fractions_refuse_without_fallback_or_new_final_gate(self):
        for changes in ({'occupied_anchor': self.vir+1e-14*self.occ},
                        {'virtual_anchor': self.occ+1e-14*self.vir}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, 'projection fraction'):
                self.prepare(**changes)
        result = self.prepare(occupied_anchor=3*self.occ, virtual_anchor=7*self.vir)
        self.assertEqual(result['directions']['minimum_projection_fraction_exclusive'], 1e-12)
        self.assertEqual(result['directions']['projection_fraction_role'],
            'NUMERICAL_DIRECTION_ADMISSION_NOT_SCIENTIFIC_FINAL_GATE')
        self.assertFalse(result['new_final_occupation_rule'])

    def test_invalid_metric_dimensions_symmetry_and_spd_are_refused_without_repair(self):
        asymmetric = self.s.copy(); asymmetric[0, 1] = 1e-6
        for value in (np.diag([1., 1., 1., 0.]), np.diag([1., 1., 1., -1.]),
                      np.full((4, 4), np.nan), np.eye(3), asymmetric, np.eye(4, dtype=bool)):
            with self.subTest(value=value), self.assertRaises(ValueError): self.prepare(masked_overlap=value)

    def test_base_fractional_wrong_rank_nonsymmetric_and_nonfinite_densities_are_refused(self):
        asymmetric = self.d.copy(); asymmetric[0, 1] = 1e-6
        for value in (np.diag([2., 1., 1., 0.]), np.diag([2., 2., 2., 0.]),
                      np.diag([2., 2., 2., -2.]), asymmetric):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.prepare(density=value, expected_density_id=seeds.density_id(value))
        for value in (np.full((4, 4), np.nan), np.eye(4, dtype=complex), np.eye(4, dtype=bool)):
            with self.subTest(value=value), self.assertRaises(ValueError): self.prepare(density=value)
        for count in (True, 3, 0, 8, 4.0):
            with self.subTest(count=count), self.assertRaises(ValueError): self.prepare(electrons=count)

    def test_duplicate_boolean_zero_unbounded_nonfinite_and_unordered_angles_are_refused(self):
        for angles in ([], [0.], [-0.], [.1, .1], [.251], [-.251], [True], [np.bool_(True)],
                       [float('nan')], [float('inf')], [.1, -.1, .2, -.2, .25], ['0.1'],
                       {.1, -.1}, np.array([[.1]])):
            with self.subTest(angles=angles), self.assertRaises(ValueError): self.prepare(angles=angles)

    def test_density_and_optional_overlap_identities_must_exactly_match_sources(self):
        for value in ('bad', 'a'*64, 'A'*64, None):
            with self.subTest(value=value), self.assertRaises(ValueError): self.prepare(expected_density_id=value)
        identity = seeds.array_identity(self.s)
        for changes in ({'sha256': 'e'*64}, {'dtype': '>f8'}, {'shape': [3, 3]}, {'order': 'F'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.prepare(expected_overlap_identity=dict(identity, **changes))
        self.assertEqual(self.prepare(expected_overlap_identity=identity)['source']['density_id'], seeds.density_id(self.d))

    def test_output_and_nested_receipts_are_immutable_and_inputs_are_preserved(self):
        original_d, original_s, original_occ, original_vir = self.d.copy(), self.s.copy(), self.occ.copy(), self.vir.copy()
        angles = list(self.angles)
        result = self.prepare()
        np.testing.assert_array_equal(self.d, original_d)
        np.testing.assert_array_equal(self.s, original_s)
        np.testing.assert_array_equal(self.occ, original_occ)
        np.testing.assert_array_equal(self.vir, original_vir)
        self.assertEqual(self.angles, angles)
        first = result['seeds'][0]; saved = first['density'].copy()
        for value in (first['density'], result['directions']['occupied_white_direction'], result['directions']['virtual_white_direction'],
                      result['source_density'], result['source_masked_overlap'], result['source_occupied_anchor'], result['source_virtual_anchor']):
            with self.assertRaises(ValueError): value.setflags(write=True)
        self.assertEqual(seeds.density_id(result['source_density']), result['source']['density_id'])
        np.testing.assert_array_equal(result['source_density'], original_d)
        np.testing.assert_array_equal(result['source_masked_overlap'], original_s)
        np.testing.assert_array_equal(result['source_occupied_anchor'], original_occ)
        np.testing.assert_array_equal(result['source_virtual_anchor'], original_vir)
        with self.assertRaises(TypeError): first['admission']['masked_metric_electron_count'] = 99
        with self.assertRaises(TypeError): result['source']['density_id'] = 'e'*64
        self.d[:] = 999; self.s[:] = 888; self.occ[:] = 777; self.vir[:] = 666
        np.testing.assert_array_equal(first['density'], saved)
        self.assertFalse(np.shares_memory(first['density'], self.d))
        np.testing.assert_array_equal(result['source_density'], original_d)
        np.testing.assert_array_equal(result['source_masked_overlap'], original_s)

    def test_api_has_no_callback_and_records_no_operator_energy_or_acceptance(self):
        parameters = inspect.signature(seeds.prepare_occupied_space_seeds).parameters
        self.assertNotIn('evaluate', parameters); self.assertNotIn('callback', parameters)
        self.assertNotIn('journal', parameters)
        result = self.prepare()
        self.assertEqual(result['functional_calls'], 0)
        self.assertEqual(result['solver_iterations'], 0)
        for key in ('F_at_new_density', 'energy', 'operator_id', 'delta_hartree'): self.assertIsNone(result[key])
        for key in ('scientific_execution_authorized', 'scientific_approval', 'production_activation',
                    'compute_enabled', 'engine_qualified', 'research_qualified', 'repairs_performed'):
            self.assertFalse(result[key])
        self.assertEqual(result['comparison_status'], dict.fromkeys(('UM-P12', 'UM-P13', 'T06'), 'NOT_EXECUTED'))
        for row in result['seeds']:
            self.assertIsNone(row['F_at_new_density']); self.assertIsNone(row['energy']); self.assertIsNone(row['operator_id'])
            self.assertEqual(row['molecular_evaluation'], 'NOT_EXECUTED')
            self.assertEqual(row['endpoint_acceptance'], 'NOT_EXECUTED')

    def test_tiny_explicit_nonzero_angle_has_no_invented_floor_or_qualification(self):
        result = self.prepare(angles=[1e-300])
        self.assertEqual(result['angles_rad'], (1e-300,))
        self.assertIsNone(result['angle_admission']['minimum_absolute_rad'])
        self.assertFalse(result['compute_enabled'])
        self.assertIsNone(result['seeds'][0]['energy'])
        self.assertEqual(result['seeds'][0]['column_space_change']['observed_changed'],
            result['seeds'][0]['column_space_change']['whitened_projector_difference_frobenius'] > 0)

    def test_large_orthogonality_correction_is_refused_despite_base_admission(self):
        # Base passes the original 1e-10 manifold tolerances.  A nearly zero
        # virtual projection pointing along u cannot be "repaired" into v.
        self.d = np.diag([2.-1e-10, 2., 0., 0.])
        self.occ = np.array([1., 0., 0., 0.])
        self.vir = self.occ.copy()
        with self.assertRaisesRegex(ValueError, 'more than allowed orthogonality'):
            self.prepare()

    def test_caller_mutation_during_preparation_is_detected_without_repair(self):
        original = seeds._admit_density
        count = [0]
        def changed(*args, **kwargs):
            count[0] += 1
            if count[0] == 2: self.d[0, 0] = 999
            return original(*args, **kwargs)
        with mock.patch.object(seeds, '_admit_density', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'source D/S/anchor/angle bytes changed'):
                self.prepare()
        self.assertEqual(self.d[0, 0], 999)  # Mutation is exposed, not repaired.


if __name__ == '__main__':
    unittest.main()
