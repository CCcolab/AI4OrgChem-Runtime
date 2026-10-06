"""Independent analytical array tests, not molecular or research acceptance.

Expected projectors, spectra and invariants below are hand-defined.  We share
NumPy/SciPy with the candidate, but do not use its endpoint helper to construct
expected answers and do not call a molecular engine, grids or ERI generation.
"""
import ast
import math
from pathlib import Path
import unittest

import numpy as np

from runtime.user_molecule import residual_candidate as candidate


TRUE_SOURCE = 'TRUE_CONDITIONAL_AT_REQUESTED_DENSITY'
FROZEN_THRESHOLDS = {
    'commutator_frobenius': 1e-5,
    'electron_count_abs': 1e-7,
    'idempotency_relative': 1e-7,
    'energy_closure_hartree': 1e-9,
    'mask_max_abs': 1e-12,
    'mapped_density_relative': 2e-8,
    'final_non_diis_gap_minimum_hartree': 1e-6,
}


def projector(theta):
    vector = np.array([math.cos(theta), math.sin(theta)])
    return 2.0 * np.outer(vector, vector)


class ArrayEvaluator:
    """Recorded exact-density callback, with an explicit test-only functional."""
    def __init__(self, kind='constant', *, half=None, mutation=None):
        self.kind = kind
        self.half = np.eye(2) if half is None else half
        self.mutation = mutation
        self.calls = []

    def __call__(self, density):
        snapshot = density.copy()
        identity = candidate.density_id(snapshot)
        self.calls.append({'density': snapshot, 'density_id': identity})
        orthogonal = self.half @ snapshot @ self.half
        if isinstance(self.kind, str) and self.kind == 'picard_unstable':
            population = 0.5 * orthogonal[0, 0]
            diagonal = 4.0 * (population - 0.5)
            fock = np.array([[diagonal, 1.0], [1.0, -diagonal]])
            # E=.5*(D11-D22)^2 + 2*D12 has this F as its derivative
            # on the trace-two manifold; it is an analytical test functional.
            one = float(2.0 * orthogonal[0, 1])
            coulomb = float(0.5 * (orthogonal[0, 0] - orthogonal[1, 1])**2)
        elif isinstance(self.kind, str) and self.kind == 'no_qualified_root':
            population = 0.5 * orthogonal[0, 0]
            fock = np.diag([population - 0.5, 0.5 - population])
            one, coulomb = 0.0, 0.0
        else:
            fock = np.asarray(self.kind, dtype=float) if not isinstance(self.kind, str) else np.diag([-1.0, 1.0])
            one, coulomb = float(np.sum(fock * orthogonal.T)), 0.0
        value = {
            'density_id': identity,
            'operator_source': TRUE_SOURCE,
            'fock': self.half @ fock @ self.half,
            'total_energy': float(one + coulomb),
            'one_electron_energy': one,
            'coulomb_energy': coulomb,
            'exact_exchange_energy': 0.0,
            'semilocal_xc_energy': 0.0,
            'nuclear_repulsion': 0.0,
        }
        if self.mutation is not None:
            self.mutation(density, value, len(self.calls))
        return value


class ResidualCandidateTests(unittest.TestCase):
    def run_array(self, evaluator=None, *, initial=None, overlap=None, **settings):
        evaluator = evaluator or ArrayEvaluator()
        initial = np.diag([2.0, 0.0]) if initial is None else initial
        overlap = np.eye(2) if overlap is None else overlap
        preserved_density, preserved_metric = initial.copy(), overlap.copy()
        result = candidate.solve_residual_candidate(
            initial_density=initial, overlap=overlap, electrons=2,
            evaluate=evaluator, **settings)
        np.testing.assert_array_equal(initial, preserved_density)
        np.testing.assert_array_equal(overlap, preserved_metric)
        self.assertFalse(result['production_activation'])
        self.assertEqual(result['research_acceptance'], 'NOT_ACCEPTED')
        self.assertEqual(result['molecular_acceptance'], 'NOT_EXECUTED')
        self.assertFalse(result['comparison_available'])
        self.assertIsNone(result['deltas'])
        self.assertIsNone(result['delta_hartree'])
        self.assertIsNone(result['delta_kcal_mol'])
        self.assertEqual(result['parameters']['endpoint_thresholds'], FROZEN_THRESHOLDS)
        self.assertEqual(result['evaluation_count'], len(evaluator.calls))
        self.assertEqual(result['evaluation_count'], len(result['evaluation_ledger']))
        self.assertLessEqual(result['evaluation_count'], settings.get('maximum_evaluations', 201))
        for index, (actual, row) in enumerate(zip(evaluator.calls, result['evaluation_ledger']), 1):
            self.assertEqual(row['evaluation_count'], index)
            self.assertEqual(row['density_id'], actual['density_id'])
            self.assertIn(row['status'], ('VALIDATED', 'REFUSED'))
            self.assertGreaterEqual(row['elapsed_seconds'], 0.0)
            requested = actual['density']
            # Every finite-difference and rejected trial remains a genuine
            # closed-shell projector, rather than fractional density mixing.
            self.assertAlmostEqual(float(np.trace(overlap @ requested)), 2.0, places=11)
            self.assertLess(np.linalg.norm(requested @ overlap @ requested - 2*requested), 1e-10)
        return result, evaluator

    def assert_root(self, result, expected, overlap, expected_fock, gap):
        self.assertTrue(result['engine_qualified'])
        self.assertTrue(result['converged'])
        self.assertEqual(result['stop_reason'], 'QUALIFIED_TRUE_ARRAY_ENDPOINT')
        self.assertIsNone(result['failure'])
        np.testing.assert_allclose(result['density'], expected, rtol=0, atol=2e-8)
        d = result['density']
        self.assertLess(np.linalg.norm(expected_fock @ d @ overlap - overlap @ d @ expected_fock), 1e-5)
        self.assertAlmostEqual(float(np.trace(overlap @ d)), 2.0, places=11)
        self.assertLess(np.linalg.norm(d @ overlap @ d - 2*d), 1e-10)
        gate = result['endpoint_gate']
        self.assertTrue(gate['qualified'])
        self.assertTrue(all(gate['checks'].values()))
        self.assertLessEqual(gate['mapped_density_relative_residual'], 2e-8)
        self.assertAlmostEqual(gate['final_non_diis_gap_hartree'], gap, places=7)
        self.assertLessEqual(gate['returned_density_energy_recheck_hartree'], 1e-9)
        self.assertLessEqual(gate['mapped_density_energy_change_hartree'], 1e-9)
        self.assertTrue(gate['mapped_density_recheck_qualified'])

    def test_constant_nondiagonal_operator_has_closed_form_ground_projector(self):
        fock = np.array([[-1.0, 0.3], [0.3, 1.0]])
        radius = math.sqrt(1.09)
        expected = np.eye(2) - fock / radius
        result, evaluator = self.run_array(ArrayEvaluator(fock))
        self.assert_root(result, expected, np.eye(2), fock, 2*radius)
        self.assertEqual(result['evaluation_ledger'][-2]['phase'], 'FINAL_RETURNED_DENSITY')
        self.assertEqual(result['evaluation_ledger'][-1]['phase'], 'FINAL_RAW_AUFBAU_DENSITY_RECHECK')
        self.assertGreater(len(evaluator.calls), 3)

    def test_residual_solves_known_root_with_locally_unstable_picard_map(self):
        # At theta=-pi/4, the exact Picard angle derivative is -2, while
        # the orbital residual has a simple nonzero derivative.  Plain
        # fixed-point iteration is locally unstable; this is not a molecule.
        expected = np.array([[1.0, -1.0], [-1.0, 1.0]])
        result, _ = self.run_array(ArrayEvaluator('picard_unstable'), initial=projector(-0.6))
        self.assert_root(result, expected, np.eye(2), np.array([[0.0, 1.0], [1.0, 0.0]]), 2.0)
        self.assertLessEqual(result['iterations'], 8)
        phases = [row['phase'] for row in result['evaluation_ledger']]
        self.assertTrue(any(phase.startswith('FD_PLUS_') for phase in phases))
        self.assertTrue(any(phase.startswith('FD_MINUS_') for phase in phases))
        self.assertTrue(any(phase.startswith('CANDIDATE_') for phase in phases))
        for row in result['history']:
            self.assertEqual(row['jacobian_rank'], 1)
            self.assertEqual(row['damped_system_rank'], 1)
            self.assertTrue(row['accepted'])
            trial = row['trial_steps'][-1]
            self.assertLess(trial['residual_norm'], row['current_residual_norm'])
            self.assertLessEqual(trial['step_norm'], 0.25 + 1e-14)

    def test_same_root_in_dense_nonorthogonal_masked_metric(self):
        overlap = np.array([[1.0, 0.2], [0.2, 1.0]])
        half = np.array([[(math.sqrt(1.2)+math.sqrt(0.8))/2,
                          (math.sqrt(1.2)-math.sqrt(0.8))/2],
                         [(math.sqrt(1.2)-math.sqrt(0.8))/2,
                          (math.sqrt(1.2)+math.sqrt(0.8))/2]])
        inverse_half = np.array([[(1/math.sqrt(1.2)+1/math.sqrt(0.8))/2,
                                  (1/math.sqrt(1.2)-1/math.sqrt(0.8))/2],
                                 [(1/math.sqrt(1.2)-1/math.sqrt(0.8))/2,
                                  (1/math.sqrt(1.2)+1/math.sqrt(0.8))/2]])
        initial = inverse_half @ projector(-0.6) @ inverse_half
        expected = np.array([[1.0, -1.0], [-1.0, 1.0]]) / 0.8
        fock = half @ np.array([[0.0, 1.0], [1.0, 0.0]]) @ half
        result, _ = self.run_array(ArrayEvaluator('picard_unstable', half=half), initial=initial, overlap=overlap)
        self.assert_root(result, expected, overlap, fock, 2.0)

    def test_commuting_excited_projector_fails_true_aufbau_gate(self):
        initial = np.diag([0.0, 2.0])
        result, _ = self.run_array(initial=initial)
        self.assertFalse(result['engine_qualified'])
        self.assertEqual(result['stop_reason'], 'STATIONARY_ENDPOINT_FAILED_ORIGINAL_GATES')
        np.testing.assert_array_equal(result['density'], initial)
        gate = result['endpoint_gate']
        self.assertTrue(gate['checks']['commutator'])
        self.assertTrue(gate['checks']['idempotency'])
        self.assertTrue(gate['checks']['raw_gap'])
        self.assertFalse(gate['checks']['mapped_density'])
        self.assertAlmostEqual(gate['mapped_density_relative_residual'], math.sqrt(2), places=12)
        self.assertEqual(result['iterations'], 0)

    def test_zero_gap_stationary_projector_is_refused(self):
        result, _ = self.run_array(ArrayEvaluator(np.zeros((2, 2))))
        self.assertFalse(result['engine_qualified'])
        self.assertTrue(result['endpoint_gate']['checks']['commutator'])
        self.assertFalse(result['endpoint_gate']['checks']['raw_gap'])
        self.assertEqual(result['endpoint_gate']['final_non_diis_gap_hartree'], 0.0)

    def test_original_positive_gap_boundary_is_not_relaxed(self):
        below = float(np.nextafter(1e-6, 0.0))
        refused, _ = self.run_array(ArrayEvaluator(np.diag([0.0, below])))
        self.assertFalse(refused['engine_qualified'])
        self.assertFalse(refused['endpoint_gate']['checks']['raw_gap'])
        accepted, _ = self.run_array(ArrayEvaluator(np.diag([0.0, 1e-6])))
        self.assertTrue(accepted['engine_qualified'])
        self.assertEqual(accepted['endpoint_gate']['final_non_diis_gap_hartree'], 1e-6)

    def test_analytical_no_qualified_root_is_not_repaired_by_altering_occupations(self):
        # Nondegenerate diagonal F requires a pure basis projector, but each
        # basis projector maps to the other.  Equal populations make F=0 and
        # gap=0.  Thus no projector meets the original positive-gap contract.
        for initial in (np.diag([2.0, 0.0]), np.diag([0.0, 2.0]), projector(-0.6)):
            with self.subTest(initial=initial.tolist()):
                result, _ = self.run_array(ArrayEvaluator('no_qualified_root'), initial=initial)
                self.assertFalse(result['engine_qualified'])
                self.assertFalse(result['converged'])
                self.assertFalse(result['endpoint_gate']['qualified'])

    def test_all_actual_callbacks_and_final_rechecks_are_counted(self):
        result, evaluator = self.run_array(ArrayEvaluator('picard_unstable'), initial=projector(-0.6))
        ledger = result['evaluation_ledger']
        self.assertEqual(result['evaluation_count'], 1 + 3*result['iterations'] + 2)
        self.assertTrue(all(row['status'] == 'VALIDATED' for row in ledger))
        self.assertEqual(ledger[-2]['density_id'], candidate.density_id(result['density']))
        for row, actual in zip(ledger, evaluator.calls):
            self.assertEqual(row['returned_density_id'], actual['density_id'])
            self.assertEqual(row['operator_source'], TRUE_SOURCE)
            self.assertRegex(row['fock_id'], r'^[0-9a-f]{64}$')
        for step in result['history']:
            self.assertEqual(step['evaluation_count_after'] - step['evaluation_count_before'], 3)

    def test_hard_evaluation_ceiling_never_invokes_callback_after_exhaustion(self):
        for ceiling in (1, 2, 3, 5):
            with self.subTest(ceiling=ceiling):
                result, evaluator = self.run_array(ArrayEvaluator('picard_unstable'), initial=projector(-0.6),
                                                   maximum_evaluations=ceiling)
                self.assertFalse(result['engine_qualified'])
                self.assertLessEqual(len(evaluator.calls), ceiling)
                self.assertIn('BUDGET', result['stop_reason'])
                self.assertFalse(any(row['phase'].startswith('FD_') for row in result['evaluation_ledger']))

    def test_iteration_budget_cannot_grant_unqualified_endpoint(self):
        result, _ = self.run_array(ArrayEvaluator('picard_unstable'), initial=projector(-0.6), maximum_iterations=1)
        self.assertEqual(result['iterations'], 1)
        self.assertFalse(result['engine_qualified'])
        self.assertEqual(result['stop_reason'], 'MAXIMUM_ITERATIONS_EXHAUSTED')
        self.assertGreater(result['endpoint_gate']['mapped_density_relative_residual'], 2e-8)

    def test_rejected_backtracks_are_retained_and_counted_before_final_return(self):
        known = {}
        def reject_new_trials(dm, value, calls):
            identity = value['density_id']
            if calls <= 3:
                known[identity] = value['fock'].copy()
            elif identity in known:
                value['fock'] = known[identity].copy()
            else:
                occupied = dm[:, 0] / np.linalg.norm(dm[:, 0])
                virtual = np.array([-occupied[1], occupied[0]])
                value['fock'] = 100.0 * (np.outer(occupied, virtual) + np.outer(virtual, occupied))
        evaluator = ArrayEvaluator('picard_unstable', mutation=reject_new_trials)
        result, _ = self.run_array(evaluator, initial=projector(-0.6), maximum_backtracks=3)
        self.assertFalse(result['engine_qualified'])
        self.assertEqual(result['stop_reason'], 'RESIDUAL_BACKTRACKS_EXHAUSTED')
        self.assertEqual(result['evaluation_count'], 7)
        self.assertEqual(len(result['history']), 1)
        row = result['history'][0]
        self.assertFalse(row['accepted'])
        self.assertEqual(len(row['trial_steps']), 3)
        self.assertEqual([trial['evaluation_count'] for trial in row['trial_steps']], [4, 5, 6])
        for trial in row['trial_steps']:
            self.assertFalse(trial['accepted'])
            self.assertAlmostEqual(trial['residual_norm'], 100.0, places=10)
        self.assertEqual(result['evaluation_ledger'][-1]['phase'], 'FINAL_RETURNED_DENSITY')
        self.assertEqual(result['evaluation_ledger'][-1]['density_id'], evaluator.calls[0]['density_id'])

    def test_residual_improvement_does_not_require_reported_energy_descent(self):
        # Deliberately decouple an energy diagnostic from the orbital residual
        # in this interface counterexample; this is not a molecular functional
        # or an assertion that its energy has the reported F as derivative.
        def increasing_energy(dm, value, calls):
            value['total_energy'] = float(-3.0 * dm[0, 0])
            value['one_electron_energy'] = value['total_energy']
            value['coulomb_energy'] = 0.0
        result, _ = self.run_array(ArrayEvaluator('picard_unstable', mutation=increasing_energy),
                                   initial=projector(-0.6))
        first = result['history'][0]
        self.assertTrue(first['accepted'])
        trial = first['trial_steps'][0]
        self.assertLess(trial['residual_norm'], first['current_residual_norm'])
        self.assertGreater(result['evaluation_ledger'][trial['evaluation_count']-1]['total_energy_hartree'],
                           result['evaluation_ledger'][0]['total_energy_hartree'])

    def test_density_identity_is_canonical_and_sensitive_to_actual_bytes(self):
        density = np.array([[1.0, -1.0], [-1.0, 1.0]])
        identity = candidate.density_id(density)
        self.assertRegex(identity, r'^[0-9a-f]{64}$')
        self.assertEqual(identity, candidate.density_id(np.asfortranarray(density)))
        self.assertEqual(identity, candidate.density_id(density.astype('>f8')))
        changed = density.copy()
        changed[0, 0] = np.nextafter(changed[0, 0], 2.0)
        self.assertNotEqual(identity, candidate.density_id(changed))

    def test_density_id_or_operator_provenance_mismatch_is_refused(self):
        for field, bad in (('density_id', '0'*64), ('operator_source', 'DIIS_EXTRAPOLATED_OPERATOR')):
            with self.subTest(field=field):
                def change(dm, value, calls, field=field, bad=bad):
                    value[field] = bad
                result, evaluator = self.run_array(ArrayEvaluator(mutation=change))
                self.assertFalse(result['engine_qualified'])
                self.assertEqual(result['stop_reason'], 'EVALUATOR_REFUSED')
                self.assertEqual(len(evaluator.calls), 1)
                self.assertEqual(result['evaluation_ledger'][0]['status'], 'REFUSED')
                self.assertIn('provenance mismatch', result['failure']['detail'])

    def test_evaluator_cannot_mutate_requested_density(self):
        def change(dm, value, calls):
            dm[0, 0] += 1.0
        initial = np.diag([2.0, 0.0])
        result, _ = self.run_array(ArrayEvaluator(mutation=change), initial=initial)
        self.assertFalse(result['engine_qualified'])
        self.assertEqual(result['stop_reason'], 'EVALUATOR_REFUSED')
        self.assertIn('modified', result['failure']['detail'])
        np.testing.assert_array_equal(result['density'], initial)

    def test_nonfinite_boolean_and_missing_energy_fields_are_refused(self):
        for field, bad in (('total_energy', float('nan')), ('coulomb_energy', float('inf')),
                           ('semilocal_xc_energy', True), ('nuclear_repulsion', None)):
            with self.subTest(field=field):
                def change(dm, value, calls, field=field, bad=bad):
                    if bad is None:
                        del value[field]
                    else:
                        value[field] = bad
                result, evaluator = self.run_array(ArrayEvaluator(mutation=change))
                self.assertFalse(result['engine_qualified'])
                self.assertEqual(result['evaluation_count'], 1)
                self.assertEqual(len(evaluator.calls), 1)
                self.assertEqual(result['stop_reason'], 'EVALUATOR_REFUSED')

    def test_malformed_true_fock_is_refused_before_qualification(self):
        for fock in (np.full((2, 2), float('nan')), np.zeros((3, 3)),
                     np.array([[0.0, 0.2], [0.0, 1.0]])):
            with self.subTest(fock=fock.tolist()):
                def change(dm, value, calls, fock=fock):
                    value['fock'] = fock
                result, _ = self.run_array(ArrayEvaluator(mutation=change))
                self.assertFalse(result['engine_qualified'])
                self.assertEqual(result['stop_reason'], 'EVALUATOR_REFUSED')
                self.assertEqual(result['evaluation_ledger'][0]['status'], 'REFUSED')

    def test_callback_exception_is_recorded_and_counted_without_retry(self):
        evaluator = ArrayEvaluator()
        def explode(dm, value, calls):
            raise RuntimeError('Explicit synthetic callback failure')
        evaluator.mutation = explode
        result, _ = self.run_array(evaluator)
        self.assertFalse(result['engine_qualified'])
        self.assertEqual(result['evaluation_count'], 1)
        self.assertEqual(result['evaluation_ledger'][0]['exception_type'], 'RuntimeError')
        self.assertIn('Explicit synthetic', result['failure']['detail'])

    def test_energy_ledger_closure_is_required_even_for_exact_aufbau_density(self):
        def inconsistent(dm, value, calls):
            value['total_energy'] += 0.01
        result, _ = self.run_array(ArrayEvaluator(mutation=inconsistent))
        self.assertFalse(result['engine_qualified'])
        gate = result['endpoint_gate']
        self.assertTrue(gate['checks']['commutator'])
        self.assertTrue(gate['checks']['mapped_density'])
        self.assertFalse(gate['checks']['energy_closure'])
        self.assertAlmostEqual(gate['energy_component_closure_residual_hartree'], 0.01, places=12)

    def test_same_returned_density_energy_must_be_reproducible(self):
        def unstable(dm, value, calls):
            shift = 1e-4 * (calls-1)
            value['total_energy'] += shift
            value['one_electron_energy'] += shift
        result, evaluator = self.run_array(ArrayEvaluator(mutation=unstable))
        self.assertFalse(result['engine_qualified'])
        self.assertEqual(result['stop_reason'], 'FINAL_RETURNED_DENSITY_ENERGY_RECHECK_FAILED')
        self.assertEqual(len(evaluator.calls), 2)
        self.assertTrue(result['endpoint_gate']['checks']['energy_closure'])
        self.assertAlmostEqual(result['endpoint_gate']['returned_density_energy_recheck_hartree'], 1e-4, places=12)
        self.assertEqual(evaluator.calls[0]['density_id'], evaluator.calls[1]['density_id'])

    def test_same_density_changed_true_operator_is_refused_even_with_constant_energy(self):
        def changed(dm, value, calls):
            value['total_energy'] = 0.0
            value['one_electron_energy'] = 0.0
            if calls == 2:
                value['fock'] = np.diag([-2.0, 2.0])
        result, evaluator = self.run_array(ArrayEvaluator(mutation=changed))
        self.assertFalse(result['engine_qualified'])
        self.assertEqual(result['stop_reason'], 'NONREPRODUCIBLE_SAME_DENSITY_OPERATOR')
        self.assertEqual(result['evaluation_count'], 2)
        self.assertEqual(evaluator.calls[0]['density_id'], evaluator.calls[1]['density_id'])
        ledger = result['evaluation_ledger']
        self.assertEqual(ledger[0]['total_energy_hartree'], 0.0)
        self.assertNotEqual(ledger[0]['fock_id'], ledger[1]['fock_id'])
        self.assertEqual(ledger[1]['previous_same_density_fock_id'], ledger[0]['fock_id'])
        self.assertEqual(ledger[1]['status'], 'REFUSED')
        self.assertFalse(ledger[1]['same_density_operator_reproducible'])
        self.assertIn('operator', result['failure']['detail'].lower())

    def test_raw_aufbau_diagnostic_recheck_cannot_change_fock_and_still_pass(self):
        def changed(dm, value, calls):
            if calls == 3:
                value['fock'] = np.diag([1.0, -1.0])
        initial = projector(1e-10)
        result, evaluator = self.run_array(ArrayEvaluator(mutation=changed), initial=initial)
        self.assertFalse(result['engine_qualified'])
        self.assertEqual(result['stop_reason'], 'FINAL_RAW_AUFBAU_RECHECK_FAILED')
        self.assertEqual(len(evaluator.calls), 3)
        self.assertTrue(result['endpoint_gate']['qualified'])
        self.assertFalse(result['mapped_endpoint_gate']['checks']['mapped_density'])
        self.assertNotEqual(evaluator.calls[1]['density_id'], evaluator.calls[2]['density_id'])
        np.testing.assert_array_equal(result['density'], initial)

    def test_declared_zero_matrix_mask_passes_but_nonzero_fock_mask_refuses(self):
        mask = np.array([[False, True], [True, False]])
        accepted, _ = self.run_array(matrix_delete_mask=mask)
        self.assertTrue(accepted['engine_qualified'])
        fock = np.array([[-1.0, 0.2], [0.2, 1.0]])
        expected = np.eye(2) - fock/math.sqrt(1.04)
        refused, _ = self.run_array(ArrayEvaluator(fock), initial=expected, matrix_delete_mask=mask)
        self.assertFalse(refused['engine_qualified'])
        self.assertTrue(refused['endpoint_gate']['checks']['mapped_density'])
        self.assertFalse(refused['endpoint_gate']['checks']['fock_mask'])

    def test_nonzero_masked_overlap_entry_refuses_original_gate(self):
        mask = np.array([[True, False], [False, False]])
        result, _ = self.run_array(matrix_delete_mask=mask)
        self.assertFalse(result['engine_qualified'])
        self.assertFalse(result['endpoint_gate']['checks']['overlap_mask'])

    def test_invalid_configuration_is_rejected_before_any_callback(self):
        changes = ({'maximum_iterations': True}, {'maximum_iterations': 0},
                   {'maximum_iterations': 101}, {'maximum_evaluations': True},
                   {'maximum_evaluations': 202}, {'maximum_evaluations': 1.5},
                   {'maximum_backtracks': True}, {'maximum_backtracks': 0},
                   {'finite_difference_step': True}, {'finite_difference_step': 0.0},
                   {'finite_difference_step': float('nan')}, {'trust_radius': True},
                   {'trust_radius': 0.0}, {'trust_radius': float('inf')},
                   {'trust_radius': 1.1}, {'finite_difference_step': 0.3, 'trust_radius': 0.2},
                   {'electrons': True}, {'electrons': 1}, {'electrons': 4},
                   {'evaluate': 'not_callable'},
                   {'matrix_delete_mask': np.zeros((2, 2), dtype=int)},
                   {'matrix_delete_mask': np.zeros((3, 3), dtype=bool)},
                   {'matrix_delete_mask': np.array([[False, True], [False, False]])})
        for change in changes:
            with self.subTest(change=change):
                evaluator = ArrayEvaluator()
                args = dict(initial_density=np.diag([2.0, 0.0]), overlap=np.eye(2), electrons=2, evaluate=evaluator)
                args.update(change)
                with self.assertRaises(ValueError):
                    candidate.solve_residual_candidate(**args)
                self.assertEqual(evaluator.calls, [])

    def test_nonmanifold_initial_density_and_bad_metric_are_not_repaired(self):
        inputs = ((np.diag([1.0, 1.0]), np.eye(2)),
                  (np.diag([2.0, 0.1]), np.eye(2)),
                  (np.diag([2.0, 0.0]), np.diag([-1.0, 1.0])),
                  (np.diag([2.0, 0.0]), np.zeros((2, 2))),
                  (np.array([[2.0, 0.1], [0.0, 0.0]]), np.eye(2)),
                  (np.array([[True, False], [False, False]]), np.eye(2)),
                  (np.diag([2.0, 0.0]).astype(complex), np.eye(2)),
                  (np.diag([2.0, 0.0]), np.eye(2, dtype=bool)),
                  (np.diag([2.0, 0.0]), np.eye(2, dtype=complex)),
                  (np.full((2, 2), float('nan')), np.eye(2)),
                  (np.diag([2.0, 0.0]), np.eye(3)))
        for initial, overlap in inputs:
            with self.subTest(initial=initial.tolist(), overlap=overlap.tolist()):
                evaluator = ArrayEvaluator()
                with self.assertRaises(ValueError):
                    candidate.solve_residual_candidate(initial_density=initial, overlap=overlap,
                                                       electrons=2, evaluate=evaluator)
                self.assertEqual(evaluator.calls, [])

    def test_rotation_dimension_limit_is_engineering_only_and_enforced_before_callback(self):
        initial = np.diag([2.0]*9 + [0.0]*9)
        evaluator = ArrayEvaluator()
        with self.assertRaisesRegex(ValueError, '64'):
            candidate.solve_residual_candidate(initial_density=initial, overlap=np.eye(18), electrons=18,
                                               evaluate=evaluator)
        self.assertEqual(evaluator.calls, [])

    def test_candidate_has_no_molecular_adapter_import_or_compute_activation(self):
        tree = ast.parse(Path(candidate.__file__).read_text(encoding='utf-8'))
        forbidden = ('pyscf', 'ai4orgchem', 'rdkit', 'reference', 'runtime.user_molecule.__main__')
        for node in ast.walk(tree):
            names = [name.name for name in node.names] if isinstance(node, ast.Import) else [node.module or ''] if isinstance(node, ast.ImportFrom) else []
            self.assertFalse(any(any(name == prefix or name.startswith(prefix+'.') for prefix in forbidden) for name in names))


if __name__ == '__main__':
    unittest.main()
