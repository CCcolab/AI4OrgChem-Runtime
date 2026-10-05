"""Bounded analytical regression: no molecular engine, grids or ERI generation."""
import ast
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
from reference import user_molecule as v1
from reference import user_molecule_v2 as ref


class FrozenIncorrectPulay:
    """DIIS plateau counterexample: returns the old occupied diagonal subspace."""
    def __init__(self, space):
        self.space, self.errors, self.fallbacks = space, [], 0

    def update(self, fock, error):
        self.errors.append(error.ravel().copy())
        self.errors = self.errors[-self.space:]
        return np.diag([-1.0, 1.0])


class ReferenceV2Tests(unittest.TestCase):
    def run_toy(self, **changes):
        settings = dict(maximum_cycles=8, density_tolerance=2e-8, energy_tolerance=1e-9,
                        diis_start_cycle=2, diis_space=8, damping_cycles=2,
                        damping=0.2, memory_controlled_eri=True)
        args = dict(density=np.diag([2.0, 0.0]), h=np.diag([-1.0, 1.0]),
                    overlap=np.eye(2), eri=np.zeros((2,) * 4),
                    aos=(v1.AO('sigma'),) * 2, entries=(), electrons=2,
                    hybrid=0.2, nuclear=0.0,
                    xc=lambda dm: (float(np.trace(dm)), 0.0, np.zeros((2, 2))),
                    settings=settings)
        args.update(changes)
        return ref.fixed_point(**args)

    def test_analytical_qualified_endpoint_and_v1_compatible_arrays(self):
        phases = []
        result = self.run_toy(progress=phases.append)
        self.assertTrue(result['converged'])
        self.assertEqual(result['cycles'], 2)
        self.assertTrue(all(result['qualification_tests'].values()))
        self.assertEqual(result['stopping_reason'], 'QUALIFIED_REAL_F_FIXED_POINT')
        self.assertEqual(result['functional_evaluation_count'], 5)
        self.assertEqual(len(phases), 5)
        self.assertEqual(result['solver_candidate_status'], 'NOT_ACCEPTED')
        self.assertEqual(result['research_acceptance'], 'NOT_ACCEPTED')
        self.assertEqual(result['molecular_acceptance'], 'NOT_EXECUTED')
        self.assertEqual(result['final_raw_aufbau_density_relative_residual'], 0.0)
        self.assertEqual(result['gap_operator_source'], ref.FINAL_OPERATOR)
        self.assertTrue(result['mo_density_matches_returned'])
        for key in ('density', 'Fraw', 'Fcond', 'J', 'K', 'Vxc', 'masked_overlap',
                    'masked_hcore', 'masked_eri', 'mo_coefficients',
                    'mo_energies_hartree', 'mo_occupations'):
            self.assertIn(key, result)
        np.testing.assert_array_equal(result['density'], result['raw_aufbau_density'])

    def test_false_diis_plateau_cannot_claim_convergence(self):
        potential = np.array([[0.0, 0.2], [0.2, 0.0]])
        settings = dict(maximum_cycles=2, density_tolerance=2e-8, energy_tolerance=1e-9,
                        diis_start_cycle=1, diis_space=8, damping_cycles=2,
                        damping=0.2, memory_controlled_eri=True)
        with patch.object(v1, 'Pulay', FrozenIncorrectPulay):
            result = self.run_toy(settings=settings,
                                  xc=lambda dm: (2.0, 0.0, potential))
        self.assertFalse(result['converged'])
        self.assertTrue(result['history'][1]['legacy_small_step_plateau'])
        self.assertFalse(result['history'][1]['candidate_endpoint_qualified'])
        self.assertFalse(result['qualification_tests']['commutator'])
        self.assertFalse(result['qualification_tests']['raw_aufbau_density'])
        self.assertEqual(result['plateau_reset_count'], 1)
        self.assertEqual(result['pending_raw_f_cycles'], 2)
        self.assertFalse(result['mo_density_matches_returned'])
        self.assertEqual(result['mo_density_role'], 'FINAL_RAW_AUFBAU_MAP_DIAGNOSTIC')
        np.testing.assert_array_equal(result['last_diagonalization_mo_energies_hartree'], [-1.0, 1.0])
        self.assertGreater(result['final_non_diis_gap_hartree'], 2.0)

    def test_unqualified_plateau_schedules_two_raw_cycles(self):
        potential = np.array([[0.0, 0.2], [0.2, 0.0]])
        settings = dict(maximum_cycles=4, density_tolerance=2e-8, energy_tolerance=1e-9,
                        diis_start_cycle=1, diis_space=8, damping_cycles=2,
                        damping=0.2, memory_controlled_eri=True)
        with patch.object(v1, 'Pulay', FrozenIncorrectPulay):
            result = self.run_toy(settings=settings,
                                  xc=lambda dm: (2.0, 0.0, potential))
        self.assertEqual(result['history'][2]['diagonalized_operator_source'], 'RAW_F_AFTER_UNQUALIFIED_PLATEAU')
        self.assertEqual(result['history'][3]['diagonalized_operator_source'], 'RAW_F_AFTER_UNQUALIFIED_PLATEAU')
        self.assertEqual(result['history'][2]['diis_gram']['vectors'], 0)
        self.assertLessEqual(result['functional_evaluation_count'], 9)

    def test_maximum_cycles_does_not_override_qualification_or_legacy_step(self):
        settings = dict(maximum_cycles=1, density_tolerance=2e-8, energy_tolerance=1e-9,
                        diis_start_cycle=2, diis_space=8, damping_cycles=2,
                        damping=0.2, memory_controlled_eri=True)
        result = self.run_toy(settings=settings)
        self.assertFalse(result['converged'])
        self.assertTrue(result['qualification_tests']['commutator'])
        self.assertFalse(result['qualification_tests']['converged'])
        self.assertEqual(result['functional_evaluation_count'], 3)

    def test_non_aufbau_stationary_density_is_not_a_qualified_endpoint(self):
        # A diagonal excited occupancy commutes with F but is not its raw Aufbau map.
        evaluated = v1.evaluate(np.diag([0.0, 2.0]), np.diag([-1.0, 1.0]), np.eye(2),
                                np.eye(2), np.zeros((2,) * 4), (v1.AO('sigma'),) * 2,
                                0.2, 0.0, lambda dm: (2.0, 0.0, np.zeros((2, 2))))
        metrics, tests, *_ = ref._endpoint(evaluated, np.eye(2), np.diag([-1.0, 1.0]),
                                          (v1.AO('sigma'),) * 2, 2, 2e-8)
        self.assertTrue(tests['commutator'])
        self.assertTrue(tests['idempotency'])
        self.assertFalse(tests['raw_aufbau_density'])
        self.assertGreater(metrics['final_raw_aufbau_density_relative_residual'], 1.0)

    def test_degenerate_and_no_virtual_spectra_are_not_comparable(self):
        degenerate = self.run_toy(h=np.zeros((2, 2)))
        self.assertFalse(degenerate['converged'])
        self.assertFalse(degenerate['qualification_tests']['final_non_diis_gap'])
        self.assertEqual(degenerate['final_non_diis_gap_hartree'], 0.0)
        self.assertEqual(degenerate['state_comparability'], 'ROOT_AMBIGUOUS')
        full = self.run_toy(electrons=4, density=2 * np.eye(2))
        self.assertFalse(full['converged'])
        self.assertIsNone(full['final_non_diis_gap_hartree'])
        self.assertEqual(full['undefined_diagnostics'][0]['reason'], 'NO_VIRTUAL_ORBITALS')

    def test_nonfinite_and_bad_metric_are_rejected_without_repair(self):
        with self.assertRaisesRegex(ValueError, 'Nonfinite'):
            self.run_toy(xc=lambda dm: (2.0, float('nan'), np.zeros((2, 2))))
        with self.assertRaisesRegex(ValueError, 'Invalid XC'):
            self.run_toy(xc=lambda dm: (2.0, 0.0, np.full((2, 2), float('nan'))))
        with self.assertRaisesRegex(ValueError, 'not positive'):
            self.run_toy(overlap=np.diag([-1.0, 1.0]))

    def test_final_recheck_rejects_nonreproducible_energy_callback(self):
        calls = []
        def changing_xc(dm):
            calls.append(True)
            return 2.0, (1.0 if len(calls) == 5 else 0.0), np.zeros((2, 2))
        result = self.run_toy(xc=changing_xc)
        self.assertEqual(len(calls), 5)
        self.assertFalse(result['converged'])
        self.assertFalse(result['qualification_tests']['final_energy_recheck'])
        self.assertEqual(result['stopping_reason'], 'FINAL_RECHECK_FAILED')
        self.assertTrue(result['qualification_tests']['commutator'])
        self.assertTrue(result['qualification_tests']['energy_closure'])

    def test_current_to_candidate_energy_change_uses_existing_tolerance(self):
        # Tiny density steps need not imply a tiny value from an arbitrary
        # supplied energy functional. This is a contract regression, not a model.
        potential = np.array([[0.0, 1e-8], [1e-8, 0.0]])
        def sharp_xc(dm):
            return 2.0, 1e8 * float(dm[0, 1]), potential
        result = self.run_toy(xc=sharp_xc)
        first = result['history'][0]
        self.assertLess(first['density_residual'], 2e-8)
        self.assertGreater(first['candidate_energy_change_hartree'], 1e-9)
        self.assertFalse(first['candidate_qualification_tests']['candidate_energy_change'])

    def test_invalid_settings_and_progress_callback_rejected(self):
        with self.assertRaisesRegex(ValueError, 'complete frozen'):
            self.run_toy(settings={'maximum_cycles': 2})
        with self.assertRaisesRegex(ValueError, 'Progress'):
            self.run_toy(progress='not a callback')

    def test_api_rejects_more_cycles_or_relaxed_scientific_thresholds(self):
        frozen = dict(maximum_cycles=8, density_tolerance=2e-8, energy_tolerance=1e-9,
                      diis_start_cycle=2, diis_space=8, damping_cycles=2,
                      damping=0.2, memory_controlled_eri=True)
        for name, value in (('maximum_cycles', 101), ('density_tolerance', 2.1e-8),
                            ('energy_tolerance', 1.1e-9)):
            with self.subTest(setting=name), self.assertRaisesRegex(ValueError, 'frozen'):
                self.run_toy(settings=dict(frozen, **{name: value}))
        strict = self.run_toy(settings=dict(frozen, density_tolerance=1e-12,
                                            energy_tolerance=1e-12))
        self.assertTrue(strict['converged'])

    def test_nonorthogonal_returned_state_uses_masked_metric(self):
        result = self.run_toy(overlap=np.array([[1.0, 0.2], [0.2, 1.0]]))
        self.assertTrue(result['converged'])
        self.assertAlmostEqual(result['masked_metric_electron_count'], 2.0, places=12)
        self.assertLess(result['final_raw_aufbau_density_relative_residual'], 2e-8)
        self.assertLess(result['final_commutator_frobenius_norm'], 1e-12)

    def test_reference_v2_has_no_production_import_and_keeps_v1_untouched(self):
        source = Path(ref.__file__).read_text(encoding='utf-8')
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                self.assertFalse((node.module or '').startswith('ai4orgchem'))
            elif isinstance(node, ast.Import):
                self.assertFalse(any(name.name.startswith('ai4orgchem') for name in node.names))
        self.assertNotIn('run_p09_conditional_rks', source)
        self.assertIn('NOT_ACCEPTED', source)


if __name__ == '__main__':
    unittest.main()
