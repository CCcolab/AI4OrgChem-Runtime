"""Fake-array BR01--BR06 checks; no molecular SCF/grid/integral/XC calls."""
import ast
import hashlib
import json
import math
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
from scipy.optimize._numdiff import approx_derivative

from reference import residual_budgeted_candidate as candidate
from reference import residual_candidate as original


ENGINEERING_FAKE_CALLBACK_COUNTS = {'entered': 0, 'completed': 0, 'failed': 0}


def identity(dm):
    encoded = np.ascontiguousarray(dm, dtype='<f8')
    return hashlib.sha256(b'AI4OrgChem-density-v1\0'+struct.pack('<QQ', *encoded.shape)
                          +encoded.tobytes()).hexdigest()


def projector(theta):
    vector = np.array([math.cos(theta), math.sin(theta)])
    return 2*np.outer(vector, vector)


class FakeEvaluator:
    """A counted analytical true-F stand-in; not a native molecular callback."""

    def __init__(self, kind='constant', mutate=None, shared_fock=None):
        self.kind, self.mutate, self.shared_fock = kind, mutate, shared_fock
        self.calls = []

    def __call__(self, dm):
        ENGINEERING_FAKE_CALLBACK_COUNTS['entered'] += 1
        self.calls.append(dm.copy())
        try:
            n = len(dm)
            if self.kind == 'unstable':
                z = 4*(dm[0, 0]/2-.5)
                fock = np.array([[z, 1.], [1., -z]])
                one = float(2*dm[0, 1])
                coulomb = float(.5*(dm[0, 0]-dm[1, 1])**2)
            elif self.kind == 'far':
                fock = np.diag(np.arange(n, dtype=float))
                fock[0, 1] = fock[1, 0] = 1.
                fock[0, 0] = fock[1, 1] = 0.
                one, coulomb = float(np.sum(fock*dm.T)), 0.
            elif self.kind == 'large':
                # Fourteen AOs/eight occupied columns -> 48 variables.  A
                # nonzero occupied--virtual coupling forces Jacobian entry.
                fock = np.diag(np.arange(n, dtype=float))
                fock[0, 8] = fock[8, 0] = 1.
                one, coulomb = float(np.sum(fock*dm.T)), 0.
            elif self.kind == 'degenerate':
                fock = np.diag([0., 5e-7])
                one, coulomb = 0., 0.
            else:
                fock = np.diag([-1., 1.])
                one, coulomb = float(np.sum(fock*dm.T)), 0.
            if self.shared_fock is not None:
                self.shared_fock[:] = fock
                fock = self.shared_fock
            value = {'density_id': identity(dm), 'operator_source': candidate.TRUE_OPERATOR,
                'fock': fock, 'total_energy': one+coulomb,
                'one_electron_energy': one, 'coulomb_energy': coulomb,
                'exact_exchange_energy': 0., 'semilocal_xc_energy': 0., 'nuclear_repulsion': 0.}
            if self.mutate is not None:
                self.mutate(dm, value, len(self.calls))
            ENGINEERING_FAKE_CALLBACK_COUNTS['completed'] += 1
            return value
        except Exception:
            ENGINEERING_FAKE_CALLBACK_COUNTS['failed'] += 1
            raise


def one_jacobian_driver(fun, start, *, jac, **options):
    """Finish exactly one completed objective/J pair, without a hidden F."""
    fun(start)
    jac(start)
    return SimpleNamespace(x=start.copy(), status=1, nfev=1, njev=1,
                           message='Controlled one-J engineering driver')


class BudgetedReferenceTests(unittest.TestCase):
    def solve(self, evaluator=None, density=None, overlap=None, electrons=2, **options):
        evaluator = evaluator or FakeEvaluator()
        density = np.diag([2., 0.]) if density is None else density
        overlap = np.eye(len(density)) if overlap is None else overlap
        before = density.copy()
        options.setdefault('initialization_policy', 'REQUIRE_EXISTING_MASKED_PROJECTOR')
        result = candidate.solve_budgeted_candidate(density=density, overlap=overlap,
            electrons=electrons, evaluate=evaluator, **options)
        np.testing.assert_array_equal(before, density)
        self.assertEqual(result['status'], 'ENGINEERING_ONLY')
        self.assertEqual(result['evaluation_count'], len(evaluator.calls))
        self.assertEqual(result['evaluation_count'], len(result['evaluation_ledger']))
        self.assertLessEqual(result['evaluation_count'], options.get('maximum_evaluations', 201))
        self.assertFalse(result['production_activation'])
        self.assertFalse(result['compute_enabled'])
        self.assertEqual(result['research_acceptance'], 'NOT_ACCEPTED')
        self.assertEqual(result['molecular_acceptance'], 'NOT_EXECUTED')
        self.assertEqual(result['method_review_status'], 'CANCELLED_INTERNAL_PENDING')
        self.assertFalse(result['comparison_available'])
        for key in ('deltas', 'delta_hartree', 'delta_kcal_mol'):
            self.assertIsNone(result[key])
        self.assertEqual(set(result['comparison_status'].values()), {'NOT_ACCEPTED'})
        self.assertEqual(result['parameters']['thresholds'], original.THRESHOLDS)
        self.assertEqual(result['accounting']['refunds'], 0)
        self.assertEqual(result['accounting']['automatic_retries'], 0)
        self.assertTrue(result['accounting']['closed'])
        for index, (dm, row) in enumerate(zip(evaluator.calls, result['evaluation_ledger']), 1):
            self.assertEqual(row['evaluation_count'], index)
            self.assertEqual(row['density_id'], identity(dm))
            self.assertTrue(row['precharged'])
            self.assertTrue(row['callback_entered'])
            self.assertEqual(row['native_molecular_execution'], 'NOT_AUTHORIZED')
        return result, evaluator

    def test_BR01_48_variables_reject_before_96_FD_calls_when_one_slot_short(self):
        d0 = np.diag([2.]*8+[0.]*6)
        with patch.object(candidate, 'least_squares', side_effect=one_jacobian_driver):
            result, _ = self.solve(FakeEvaluator('large'), density=d0, electrons=16,
                                   maximum_evaluations=99)
        self.assertEqual(result['evaluation_count'], 2)
        self.assertEqual(result['stop_reason'], 'JACOBIAN_BUDGET_ADMISSION_REFUSED')
        group = result['budget_admissions'][0]
        self.assertEqual(group['required_callbacks'], 96)
        self.assertEqual(group['remaining_callbacks'], 97)
        self.assertEqual(group['tail_callbacks_reserved'], 2)
        self.assertFalse(group['admitted'])
        self.assertEqual(group['actual_callbacks'], 0)
        self.assertEqual(group['variable_count'], 48)
        self.assertEqual(group['planned_callbacks'], 96)
        self.assertEqual(group['chart'], 1)
        self.assertEqual(group['base_snapshot_id'], result['optimizer_base']['snapshot_id'])
        self.assertEqual(group['base_density_id'], result['optimizer_base']['density_id'])
        self.assertEqual(group['base_operator_id'], result['optimizer_base']['operator_id'])
        self.assertEqual(group['derivative_policy'], candidate.DERIVATIVE_POLICY)
        self.assertEqual(result['fd_samples'], ())
        self.assertIsNone(result['last_complete_jacobian_base'])
        self.assertEqual(result['tail_execution']['status'], 'NOT_EXECUTED')
        self.assertIsNone(result['endpoint_gate'])
        np.testing.assert_array_equal(result['density'], d0)

    def test_BR01_48_variables_exact_boundary_completes_96_call_group(self):
        d0 = np.diag([2.]*8+[0.]*6)
        with patch.object(candidate, 'least_squares', side_effect=one_jacobian_driver):
            result, _ = self.solve(FakeEvaluator('large'), density=d0, electrons=16,
                                   maximum_evaluations=100)
        group = result['budget_admissions'][0]
        self.assertEqual(group['required_callbacks'], 96)
        self.assertEqual(group['remaining_callbacks'], 98)
        self.assertEqual(group['actual_callbacks'], 96)
        self.assertEqual(group['status'], 'COMPLETED')
        self.assertEqual(group['unexecuted_planned_callbacks'], 0)
        self.assertEqual(len(result['fd_samples']), 96)
        self.assertEqual(result['evaluation_count'], 99)
        self.assertEqual(result['tail_execution']['actual_callbacks'], 1)
        self.assertEqual(result['accounting']['remaining_unused_callbacks'], 1)
        self.assertFalse(result['engine_qualified'])

    def test_BR01_one_variable_boundary_and_no_partial_second_J(self):
        def driver(fun, start, *, jac, **options):
            fun(start)
            jac(start)
            point = np.array([.01])
            fun(point)
            jac(point)
            self.fail('An insufficient second full J must not complete')
        with patch.object(candidate, 'least_squares', side_effect=driver):
            result, _ = self.solve(FakeEvaluator('unstable'), density=projector(-.6),
                                   maximum_evaluations=7)
        self.assertEqual(result['evaluation_count'], 5)
        self.assertEqual(len(result['budget_admissions']), 2)
        self.assertEqual(result['budget_admissions'][0]['actual_callbacks'], 2)
        self.assertEqual(result['budget_admissions'][1]['actual_callbacks'], 0)
        self.assertEqual(result['budget_admissions'][1]['remaining_callbacks'], 2)
        self.assertEqual(result['stop_reason'], 'JACOBIAN_BUDGET_ADMISSION_REFUSED')
        self.assertEqual(result['tail_execution']['actual_callbacks'], 0)
        self.assertNotEqual(result['optimizer_base']['snapshot_id'],
                            result['last_complete_jacobian_base']['snapshot_id'])

    def test_BR02_budget_exception_preserves_seed_not_best_sample_or_last_F(self):
        seed = projector(-.6)
        def driver(fun, start, *, jac, **options):
            fun(start)
            jac(start)
            fun(np.array([.02]))
            self.fail('A new objective must not borrow the two tail slots')
        with patch.object(candidate, 'least_squares', side_effect=driver):
            result, _ = self.solve(FakeEvaluator('unstable'), density=seed,
                                   maximum_evaluations=6)
        self.assertEqual(result['evaluation_count'], 4)
        self.assertEqual(result['stop_reason'], 'EVALUATION_BUDGET_EXHAUSTED')
        np.testing.assert_array_equal(result['density'], seed)
        self.assertEqual(result['returned_density']['density_id'], identity(seed))
        self.assertNotEqual(result['best_any_sample']['density_id'], identity(seed))
        self.assertNotEqual(result['last_call']['density_id'], identity(seed))
        self.assertFalse(result['returned_density']['final_gate_evaluated'])
        self.assertIsNone(result['endpoint_gate'])
        self.assertEqual(result['tail_execution']['status'], 'NOT_EXECUTED')
        self.assertEqual(result['accounting']['remaining_unused_callbacks'], 2)

    def test_BR02_snapshots_bind_D_F_energy_and_are_immutable(self):
        shared = np.zeros((2, 2))
        evaluator = FakeEvaluator('unstable', shared_fock=shared)
        with patch.object(candidate, 'least_squares', side_effect=one_jacobian_driver):
            result, _ = self.solve(evaluator, density=projector(-.6), maximum_evaluations=6)
        saved = result['snapshot_registry']['evaluation-1']
        fock_before, density_before = saved['fock'].copy(), saved['density'].copy()
        shared[:] = 99
        np.testing.assert_array_equal(saved['fock'], fock_before)
        np.testing.assert_array_equal(saved['density'], density_before)
        for snapshot in result['snapshot_registry'].values():
            self.assertEqual(snapshot['density_id'], identity(snapshot['density']))
            self.assertEqual(snapshot['fock_id'], identity(snapshot['fock']))
            self.assertEqual(snapshot['operator_id'], candidate.operator_id(
                snapshot['density_id'], snapshot['fock'], snapshot['total_energy'], snapshot['components']))
            self.assertFalse(snapshot['density'].flags.writeable)
            self.assertFalse(snapshot['fock'].flags.writeable)
        with self.assertRaises(TypeError):
            saved['phase'] = 'AMENDED'
        with self.assertRaises(TypeError):
            saved['components']['nuclear_repulsion'] = 99.
        with self.assertRaises(ValueError):
            saved['density'].setflags(write=True)
        with self.assertRaises(ValueError):
            saved['fock'][0, 0] = 99.
        json.dumps(saved, default=lambda value: value.tolist(), allow_nan=False)

    def test_BR03_failure_before_J_is_charged_and_never_retried(self):
        for failure_at in (1, 2):
            def fail(dm, value, count):
                if count == failure_at:
                    raise RuntimeError('Controlled fake callback failure before J')
            with self.subTest(failure_at=failure_at), patch.object(candidate, 'least_squares', side_effect=one_jacobian_driver):
                result, _ = self.solve(FakeEvaluator('unstable', mutate=fail),
                                       density=projector(-.6), maximum_evaluations=6)
            self.assertEqual(result['evaluation_count'], failure_at)
            self.assertEqual(result['accounting']['callback_failed'], 1)
            self.assertEqual(result['accounting']['callback_completed'], failure_at-1)
            self.assertEqual(result['budget_admissions'], ())
            self.assertEqual(result['last_call']['status'], 'REFUSED')
            self.assertEqual(result['tail_execution']['actual_callbacks'], 0)

    def test_BR03_failure_inside_J_retains_failed_charge_and_last_validated(self):
        def fail(dm, value, count):
            if count == 3:
                raise RuntimeError('Controlled failure in admitted J')
        with patch.object(candidate, 'least_squares', side_effect=one_jacobian_driver):
            result, _ = self.solve(FakeEvaluator('unstable', mutate=fail),
                                   density=projector(-.6), maximum_evaluations=6)
        self.assertEqual(result['evaluation_count'], 3)
        self.assertEqual(result['accounting']['precharged_callbacks'], 3)
        self.assertEqual(result['accounting']['callback_entered'], 3)
        self.assertEqual(result['accounting']['callback_completed'], 2)
        self.assertEqual(result['accounting']['callback_failed'], 1)
        group = result['budget_admissions'][0]
        self.assertEqual(group['actual_callbacks'], 1)
        self.assertEqual(group['unexecuted_planned_callbacks'], 1)
        self.assertEqual(group['status'], 'REFUSED_PARTIAL_NO_RETRY')
        self.assertEqual(result['last_call']['evaluation_count'], 3)
        self.assertEqual(result['last_validated_snapshot']['evaluation_count'], 2)
        self.assertIsNone(result['last_call']['matched_snapshot_id'])
        self.assertIsNone(result['last_complete_jacobian_base'])
        self.assertEqual(result['tail_execution']['status'], 'NOT_EXECUTED')

    def test_BR04_initial_qualified_endpoint_requires_two_actual_tail_calls(self):
        result, _ = self.solve(maximum_evaluations=3)
        self.assertTrue(result['engine_qualified'])
        self.assertEqual(result['evaluation_count'], 3)
        self.assertEqual(result['tail_execution']['actual_callbacks'], 2)
        self.assertTrue(result['endpoint_gate']['qualified'])
        self.assertTrue(result['mapped_endpoint_gate']['qualified'])
        self.assertEqual([row['phase'] for row in result['evaluation_ledger']],
            ['CURRENT_INITIAL', 'FINAL_RETURNED_DENSITY', 'FINAL_RAW_AUFBAU_DENSITY_RECHECK'])

    def test_BR04_insufficient_final_tail_has_zero_callback_refusal(self):
        result, _ = self.solve(maximum_evaluations=2)
        self.assertEqual(result['evaluation_count'], 1)
        self.assertEqual(result['stop_reason'], 'FINAL_TAIL_BUDGET_ADMISSION_REFUSED')
        self.assertIsNone(result['endpoint_gate'])
        self.assertIsNone(result['mapped_endpoint_gate'])
        self.assertEqual(result['tail_execution']['status'], 'NOT_EXECUTED')
        self.assertEqual(result['budget_admissions'][0]['actual_callbacks'], 0)

    def test_BR04_returned_energy_recheck_keeps_original_tolerance(self):
        def changed_energy(dm, value, count):
            if count == 2:
                value['one_electron_energy'] += 2e-9
                value['total_energy'] += 2e-9
        result, _ = self.solve(FakeEvaluator(mutate=changed_energy))
        self.assertFalse(result['engine_qualified'])
        self.assertEqual(result['stop_reason'], 'FINAL_RETURNED_DENSITY_ENERGY_RECHECK_FAILED')
        self.assertEqual(result['evaluation_count'], 2)
        self.assertIsNone(result['mapped_endpoint_gate'])

    def test_BR04_mapped_endpoint_runs_all_original_gates(self):
        def changed_closure(dm, value, count):
            if count == 3:
                value['total_energy'] += 2e-9
        result, _ = self.solve(FakeEvaluator(mutate=changed_closure))
        self.assertFalse(result['engine_qualified'])
        self.assertEqual(result['evaluation_count'], 3)
        self.assertEqual(result['stop_reason'], 'FINAL_RAW_AUFBAU_RECHECK_FAILED')
        self.assertFalse(result['mapped_endpoint_gate']['checks']['energy_closure'])

    def test_BR05_nonfinite_density_mutation_and_identity_mismatch_are_charged(self):
        cases = (
            ('nonfinite', lambda dm, value: value['fock'].__setitem__((0, 0), np.inf)),
            ('mutation', lambda dm, value: dm.__setitem__((0, 0), dm[0, 0]+.1)),
            ('identity', lambda dm, value: value.__setitem__('density_id', '0'*64)),
            ('source', lambda dm, value: value.__setitem__('operator_source', 'EXTRAPOLATED_F')),
        )
        for label, change in cases:
            def mutate(dm, value, count):
                if count == 3:
                    change(dm, value)
            with self.subTest(label=label), patch.object(candidate, 'least_squares', side_effect=one_jacobian_driver):
                result, _ = self.solve(FakeEvaluator('unstable', mutate=mutate),
                                       density=projector(-.6), maximum_evaluations=6)
            self.assertEqual(result['evaluation_count'], 3)
            self.assertEqual(result['accounting']['callback_completed'], 3)
            self.assertEqual(result['accounting']['validated_callbacks'], 2)
            self.assertEqual(result['evaluation_ledger'][-1]['status'], 'REFUSED')
            self.assertEqual(result['budget_admissions'][0]['actual_callbacks'], 1)
            self.assertEqual(result['tail_execution']['status'], 'NOT_EXECUTED')
            self.assertIsNone(result['endpoint_gate'])

    def test_BR05_missing_completed_base_has_zero_free_F(self):
        def driver(fun, start, *, jac, **options):
            fun(start)
            jac(np.array([.01]))
            self.fail('Missing base cache must refuse before a callback')
        with patch.object(candidate, 'least_squares', side_effect=driver):
            result, _ = self.solve(FakeEvaluator('unstable'), density=projector(-.6))
        self.assertEqual(result['stop_reason'], 'JACOBIAN_BASE_SNAPSHOT_MISSING')
        self.assertEqual(result['evaluation_count'], 2)
        self.assertEqual(result['budget_admissions'], ())
        self.assertEqual(result['fd_samples'], ())

    def test_BR05_three_point_zero_relative_and_bound_steps_match_pinned_library(self):
        for point in (0., .1, -.1, .25, -.25):
            desired = np.array([point])
            def driver(fun, start, *, jac, **options):
                fun(desired)
                jac(desired)
                return SimpleNamespace(x=desired.copy(), status=1, nfev=1, njev=1, message='Bound-step probe')
            with self.subTest(point=point), patch.object(candidate, 'least_squares', side_effect=driver):
                result, _ = self.solve(FakeEvaluator('far'), density=projector(-.1),
                                       maximum_evaluations=6, maximum_iterations=1)
            recorded = [np.asarray(row['local_rotation_coordinates'])
                        for row in result['evaluation_ledger'] if row['phase'] == 'FD_SAMPLE']
            expected = []
            def polynomial(z):
                expected.append(z.copy())
                return np.array([z[0]**3+z[0]])
            approx_derivative(polynomial, desired, method='3-point', rel_step=1e-5,
                bounds=(-.25, .25), f0=np.array([point**3+point]), workers=1)
            self.assertEqual(len(recorded), 2)
            self.assertEqual(len(expected), 2)
            for observed, wanted in zip(recorded, expected):
                np.testing.assert_array_equal(observed, wanted)
            if point == 0:
                self.assertAlmostEqual(abs(recorded[0][0]), np.finfo(float).eps**(1/3), places=20)

    def test_BR05_invalid_config_and_nonpinned_helper_have_zero_callbacks(self):
        for options in ({'density': np.eye(2)}, {'maximum_iterations': True},
                        {'maximum_evaluations': 202}, {'maximum_evaluations': 0},
                        {'finite_difference_step': True}, {'overlap': np.diag([-1., 1.])}):
            evaluator = FakeEvaluator()
            with self.subTest(options=options), self.assertRaises(ValueError):
                candidate.solve_budgeted_candidate(density=options.get('density', np.diag([2., 0.])),
                    overlap=options.get('overlap', np.eye(2)), electrons=2, evaluate=evaluator,
                    initialization_policy='REQUIRE_EXISTING_MASKED_PROJECTOR',
                    **{key: value for key, value in options.items() if key not in ('density', 'overlap')})
            self.assertEqual(evaluator.calls, [])
        evaluator = FakeEvaluator()
        with patch.object(candidate, 'scipy_version', '0.0.0'), self.assertRaises(ValueError):
            candidate.solve_budgeted_candidate(density=np.diag([2., 0.]), overlap=np.eye(2),
                electrons=2, evaluate=evaluator, initialization_policy='REQUIRE_EXISTING_MASKED_PROJECTOR')
        self.assertEqual(evaluator.calls, [])

    def test_BR06_true_array_root_can_qualify_engineering_only(self):
        result, _ = self.solve(FakeEvaluator('unstable'), density=projector(-.6))
        self.assertTrue(result['engine_qualified'])
        np.testing.assert_allclose(result['density'], [[1., -1.], [-1., 1.]], rtol=0, atol=2e-8)
        self.assertTrue(result['mapped_endpoint_gate']['qualified'])
        self.assertFalse(result['compute_enabled'])
        self.assertTrue(all(group['actual_callbacks'] == group['required_callbacks']
                            for group in result['budget_admissions'] if group['kind'] == 'COMPLETE_JACOBIAN'))

    def test_BR06_original_gap_and_init_policy_still_refuse(self):
        result, _ = self.solve(FakeEvaluator('degenerate'),
            initialization_policy='FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0')
        self.assertEqual(result['evaluation_count'], 1)
        self.assertEqual(result['stop_reason'], 'ROOT_AMBIGUOUS_INITIALIZATION')
        self.assertFalse(result['engine_qualified'])
        self.assertIsNone(result['endpoint_gate'])

    def test_BR06_same_density_nonreproducible_operator_is_not_relaxed(self):
        def change(dm, value, count):
            if count == 2:
                value['fock'][1, 1] += .1
        result, _ = self.solve(FakeEvaluator(mutate=change))
        self.assertEqual(result['evaluation_count'], 2)
        self.assertEqual(result['stop_reason'], 'NONREPRODUCIBLE_SAME_DENSITY_OPERATOR')
        self.assertFalse(result['engine_qualified'])

    def test_BR06_candidate_has_no_production_import_or_cli_registration(self):
        source = Path(candidate.__file__).read_text(encoding='utf-8')
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [node.module or ''] if isinstance(node, ast.ImportFrom) else [alias.name for alias in node.names]
                self.assertFalse(any(name.startswith(('runtime', 'ai4orgchem', 'pyscf', 'science')) for name in names), names)
        self.assertIn('original.qualify(', source)
        self.assertNotIn("jac='3-point'", source)
        self.assertIn('approx_derivative(', source)
        self.assertEqual(candidate.THRESHOLDS, original.THRESHOLDS)
        self.assertEqual(candidate.POLICIES, original.POLICIES)
        self.assertEqual(candidate.REQUIRED_SCIPY_VERSION, '1.18.0')


if __name__ == '__main__':
    unittest.main()
