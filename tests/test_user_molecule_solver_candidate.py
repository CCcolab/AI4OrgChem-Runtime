"""Pure-array candidate-stop counterexamples; no molecule, grid or SCF engine."""
import unittest
import numpy as np

from runtime.user_molecule.solver_candidate import (
    ENDPOINT_THRESHOLDS, endpoint_gate, iterate_candidate,
)


class RawDiis:
    def __init__(self, space):
        self.space = space

    def update(self, fock, xerr):
        return fock.copy()


class FrozenBadDiis(RawDiis):
    def update(self, fock, xerr):
        return np.diag([-1., 1.])


def constant_evaluator(fock, energy=0.):
    def evaluate(density):
        return {'fock': fock.copy(), 'total_energy': float(energy),
            'one_electron_energy': float(energy), 'coulomb_energy': 0.,
            'exact_exchange_energy': 0., 'semilocal_xc_energy': 0.,
            'nuclear_repulsion': 0., 'physical_metric_electron_count': float(np.trace(density))}
    return evaluate


class EndpointTests(unittest.TestCase):
    def gate(self, **overrides):
        values = dict(density=np.diag([2., 0.]), fock=np.diag([-1., 1.]),
            overlap=np.eye(2), electrons=2, energy_closure_hartree=0.)
        values.update(overrides)
        return endpoint_gate(**values)

    def test_true_stationary_aufbau_endpoint_passes(self):
        gate = self.gate()
        self.assertTrue(gate['qualified'])
        self.assertTrue(all(gate['checks'].values()))
        np.testing.assert_array_equal(gate['mapped_density'], np.diag([2., 0.]))
        self.assertEqual(gate['final_non_diis_gap_hartree'], 2.)

    def test_small_diis_step_is_not_a_true_endpoint(self):
        gate = self.gate(fock=np.array([[-1., .3], [.3, 1.]]))
        self.assertFalse(gate['qualified'])
        self.assertFalse(gate['checks']['commutator'])
        self.assertFalse(gate['checks']['mapped_density'])

    def test_commuting_excited_determinant_must_fail_raw_aufbau(self):
        gate = self.gate(fock=np.diag([1., -1.]))
        for key in ('commutator', 'electron_count', 'idempotency', 'energy_closure', 'raw_gap'):
            self.assertTrue(gate['checks'][key], key)
        self.assertFalse(gate['checks']['mapped_density'])
        self.assertFalse(gate['qualified'])

    def test_nonfinite_or_nonsymmetric_endpoint_never_passes(self):
        for kwargs in (dict(fock=np.array([[np.nan,0],[0,1]])),
                       dict(energy_closure_hartree=float('inf')),
                       dict(fock=np.array([[-1.,.1],[0.,1.]]))):
            with self.subTest(kwargs=kwargs):
                self.assertFalse(self.gate(**kwargs)['qualified'])

    def test_metric_positive_and_mask_electron_idempotency_are_required(self):
        self.assertFalse(self.gate(overlap=np.diag([-1., 1.]))['qualified'])
        wrong_electrons = self.gate(density=np.diag([1., 0.]))
        self.assertFalse(wrong_electrons['checks']['electron_count'])
        self.assertFalse(wrong_electrons['checks']['idempotency'])
        for kwargs, key in ((dict(overlap_mask_max_abs=2e-12), 'overlap_mask'),
                            (dict(fock_mask_max_abs=2e-12), 'fock_mask'),
                            (dict(energy_closure_hartree=2e-9), 'energy_closure')):
            gate = self.gate(**kwargs)
            self.assertFalse(gate['checks'][key])
            self.assertFalse(gate['qualified'])

    def test_gap_ambiguity_and_no_virtual_orbital_are_explicit(self):
        degenerate = self.gate(fock=np.zeros((2, 2)))
        self.assertFalse(degenerate['qualified'])
        self.assertIn('ROOT_AMBIGUOUS', degenerate['reasons'])
        full = self.gate(density=2*np.eye(2), electrons=4)
        self.assertIsNone(full['final_non_diis_gap_hartree'])
        self.assertFalse(full['qualified'])
        self.assertIn('NO_VIRTUAL_ORBITAL_RAW_GAP_UNDEFINED', full['reasons'])

    def test_mapped_density_is_relative_and_mo_sign_independent(self):
        # Generalized metric normalization: this density is exactly 2 Cocc Cocc.T.
        s = np.diag([.5, 2.])
        gate = self.gate(density=np.diag([4., 0.]), overlap=s)
        self.assertTrue(gate['qualified'])
        self.assertLess(gate['mapped_density_relative_residual'], 1e-15)

    def test_thresholds_cannot_be_mutated(self):
        with self.assertRaises(TypeError):
            ENDPOINT_THRESHOLDS['commutator_frobenius'] = 1.


class IterationTests(unittest.TestCase):
    def run_toy(self, **overrides):
        values = dict(initial_density=np.diag([2., 0.]), overlap=np.eye(2), electrons=2,
            evaluate=constant_evaluator(np.diag([-1., 1.])), diis_factory=RawDiis,
            maximum_cycles=8, diis_start_cycle=1, damping_cycles=0)
        values.update(overrides)
        return iterate_candidate(**values)

    def test_true_endpoint_needs_energy_history_and_final_recheck(self):
        result = self.run_toy()
        self.assertTrue(result['converged'])
        self.assertEqual(result['cycles'], 2)
        self.assertEqual(result['evaluation_count'], 5)
        self.assertEqual(result['stop_reason'], 'QUALIFIED_TRUE_ENDPOINT')
        self.assertFalse(result['history'][0]['legacy_stop_candidate'])
        self.assertTrue(result['history'][1]['true_stop'])
        self.assertEqual(result['final_energy_recheck_status'], 'EXECUTED')
        self.assertIsNone(result['final_energy_recheck_reason'])
        self.assertTrue(result['qualification_tests']['final_energy_recheck'])
        self.assertEqual(result['gap_operator_source'], 'RECOMPUTED_AT_RETURNED_DENSITY_NO_DIIS')

    def test_false_plateau_clears_diis_and_next_two_cycles_use_raw_f(self):
        result = self.run_toy(evaluate=constant_evaluator(np.array([[-1., .3], [.3, 1.]])),
            diis_factory=FrozenBadDiis)
        history = result['history']
        self.assertTrue(history[1]['legacy_stop_candidate'])
        self.assertFalse(history[1]['endpoint_qualified'])
        self.assertTrue(history[1]['diis_reset'])
        self.assertEqual(history[2]['diagonalization_operator'], 'RAW_F_REFINEMENT')
        self.assertEqual(history[3]['diagonalization_operator'], 'RAW_F_REFINEMENT')
        self.assertEqual(result['diis_reset_count'], 1)
        self.assertTrue(result['converged'])
        self.assertLessEqual(result['evaluation_count'], result['evaluation_limit'])

    def test_cycle_and_evaluation_limits_do_not_fake_convergence(self):
        calls = []
        evaluator = constant_evaluator(np.diag([1., -1.]))
        def tracked(density):
            calls.append(density.copy())
            return evaluator(density)
        result = self.run_toy(evaluate=tracked, diis_factory=FrozenBadDiis, maximum_cycles=2)
        self.assertFalse(result['converged'])
        self.assertEqual(result['cycles'], 2)
        self.assertEqual(result['evaluation_count'], 5)
        self.assertEqual(len(calls), 5)
        self.assertEqual(result['stop_reason'], 'MAXIMUM_CYCLES_EXHAUSTED')
        self.assertEqual(result['research_status'], 'NOT_QUALIFIED')
        self.assertIsNone(result['final_candidate_energy_recheck_hartree'])
        self.assertEqual(result['final_energy_recheck_status'], 'NOT_EXECUTED_NO_QUALIFIED_STOP')
        self.assertEqual(result['final_energy_recheck_reason'], 'NO_QUALIFIED_STOP_CANDIDATE_TO_RECHECK')
        self.assertFalse(result['qualification_tests']['final_energy_recheck'])
        self.assertFalse(result['raw_mo_density_matches_returned_density'])
        np.testing.assert_array_equal(result['density'], np.diag([2., 0.]))
        np.testing.assert_array_equal(result['mapped_density'], np.diag([0., 2.]))
        self.assertFalse(np.array_equal(result['mo_coefficients'], result['last_diagonalization_mo_coefficients']))

    def test_candidate_energy_change_prevents_lagged_energy_false_stop(self):
        count = 0
        evaluator = constant_evaluator(np.diag([-1., 1.]))
        def inconsistent_energy(density):
            nonlocal count
            count += 1
            value = evaluator(density)
            # All current energies stay zero; each candidate's energy is one.
            value['total_energy'] = value['one_electron_energy'] = float(count % 2 == 0)
            return value
        result = self.run_toy(evaluate=inconsistent_energy, maximum_cycles=3)
        self.assertFalse(result['converged'])
        self.assertTrue(result['history'][1]['legacy_stop_candidate'])
        self.assertTrue(result['history'][1]['endpoint_qualified'])
        self.assertFalse(result['history'][1]['true_stop'])
        self.assertEqual(result['history'][1]['candidate_energy_change_hartree'], 1.)

    def test_nonfinite_evaluation_is_explicit_and_unqualified(self):
        result = self.run_toy(evaluate=constant_evaluator(np.diag([-1., 1.]), energy=float('nan')))
        self.assertFalse(result['converged'])
        self.assertEqual(result['stop_reason'], 'NONFINITE_CURRENT_EVALUATION')
        self.assertEqual(result['evaluation_count'], 2)
        self.assertFalse(result['endpoint_gate']['checks']['finite'])

    def test_final_energy_recheck_rejects_stateful_evaluator(self):
        calls = 0
        evaluator = constant_evaluator(np.diag([-1., 1.]))
        def changed_final_energy(density):
            nonlocal calls
            calls += 1
            value = evaluator(density)
            if calls == 5:
                value['total_energy'] = value['one_electron_energy'] = 1.
            return value
        result = self.run_toy(evaluate=changed_final_energy)
        self.assertTrue(result['history'][-1]['true_stop'])
        self.assertFalse(result['converged'])
        self.assertEqual(result['stop_reason'], 'FINAL_RECHECK_FAILED')
        self.assertEqual(result['final_candidate_energy_recheck_hartree'], 1.)
        self.assertEqual(result['final_energy_recheck_status'], 'EXECUTED')
        self.assertIsNone(result['final_energy_recheck_reason'])
        self.assertFalse(result['qualification_tests']['final_energy_recheck'])

    def test_diis_arithmetic_failure_uses_raw_current_and_next_two_cycles(self):
        for failure in (np.linalg.LinAlgError('Singular matrix'),
                        ValueError('Unusable affine DIIS coefficients')):
            with self.subTest(failure=type(failure).__name__):
                class ArithmeticFailure(RawDiis):
                    def update(self, fock, xerr):
                        raise failure
                calls = 0
                evaluator = constant_evaluator(np.diag([-1., 1.]))
                def tracked(density):
                    nonlocal calls
                    calls += 1
                    value = evaluator(density)
                    # Prevent a true stop until both scheduled raw cycles run.
                    energy = float(calls >= 3)
                    value['total_energy'] = value['one_electron_energy'] = energy
                    return value
                result = self.run_toy(evaluate=tracked, diis_factory=ArithmeticFailure)
                history = result['history']
                self.assertEqual(history[0]['diagonalization_operator'], 'RAW_F_DIIS_ARITHMETIC_REFUSAL')
                self.assertEqual(history[0]['diis_update_failure']['message'], str(failure))
                self.assertEqual(history[0]['diis_reset_count'], 1)
                self.assertEqual(history[1]['diagonalization_operator'], 'RAW_F_REFINEMENT')
                self.assertEqual(history[2]['diagonalization_operator'], 'RAW_F_REFINEMENT')
                self.assertEqual(result['diis_arithmetic_reset_count'], 1)
                self.assertEqual(result['plateau_reset_count'], 0)
                self.assertEqual(result['false_stop_count'], 0)
                self.assertEqual(result['evaluation_count'], 7)
                self.assertLessEqual(result['evaluation_count'], result['evaluation_limit'])
                self.assertTrue(result['converged'])  # Raw endpoint, never the arithmetic event, qualifies.
        class InvalidInput(RawDiis):
            def update(self, fock, xerr):
                raise ValueError('Invalid array shape')
        with self.assertRaisesRegex(ValueError, 'Invalid array shape'):
            self.run_toy(diis_factory=InvalidInput)

    def test_invalid_or_relaxed_settings_are_rejected(self):
        for kwargs in (dict(maximum_cycles=101), dict(maximum_cycles=True),
                       dict(density_tolerance=3e-8), dict(energy_tolerance=2e-9),
                       dict(electrons=1), dict(damping=1.), dict(diis_space=0)):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.run_toy(**kwargs)

    def test_progress_and_occupied_subspace_changes_are_recorded(self):
        progress = []
        result = self.run_toy(progress=progress.append)
        self.assertEqual(len(progress), result['cycles'])
        self.assertIsNone(result['history'][0]['occupied_subspace_change_frobenius'])
        self.assertEqual(result['history'][1]['occupied_subspace_change_frobenius'], 0.)
        self.assertEqual(result['history'][1]['raw_mapped_occupied_subspace_change_frobenius'], 0.)


if __name__ == '__main__':
    unittest.main()
