"""Pure-array root-candidate scheduling and provenance, no molecular job."""
import ast
import hashlib
import math
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
from scipy.optimize._numdiff import approx_derivative

from reference import occupied_space_root_candidate as candidate
from reference import residual_candidate as original


def projector(theta):
    vector = np.array([math.cos(theta), math.sin(theta)])
    return 2*np.outer(vector, vector)


class FakeEvaluator:
    """Analytical F/G ledger; callbacks are not native molecular operations."""
    def __init__(self, kind='constant', mutate=None, shared=None):
        self.kind, self.mutate, self.shared = kind, mutate, shared
        self.calls, self.phases = [], []

    def __call__(self, dm, phase):
        self.calls.append(dm.copy()); self.phases.append(phase)
        n = len(dm)
        if self.kind == 'large':
            fock = np.diag(np.arange(n, dtype=float)); fock[0, 8] = fock[8, 0] = 1.
            one, coulomb = float(np.sum(fock*dm.T)), 0.
        elif self.kind == 'unstable':
            z = 4*(dm[0, 0]/2-.5)
            fock = np.array([[z, 1.], [1., -z]])
            one = float(2*dm[0, 1]); coulomb = float(.5*(dm[0, 0]-dm[1, 1])**2)
        elif self.kind == 'degenerate':
            fock = np.diag([0., 5e-7]); one, coulomb = 0., 0.
        else:
            fock = np.diag([-1., 1.]); one, coulomb = float(np.sum(fock*dm.T)), 0.
        raw = fock.copy()
        if self.shared is not None:
            self.shared[:] = fock
            fock = self.shared
        total = one+coulomb
        value = {'density_id': candidate.density_id(dm), 'operator_source': candidate.TRUE_OPERATOR,
            'fock': fock, 'raw_fock': raw, 'J': np.zeros((n, n)), 'K': np.zeros((n, n)), 'Vxc': np.zeros((n, n)),
            'total_energy': total, 'electronic_energy': total, 'one_electron_energy': one,
            'coulomb_energy': coulomb, 'exact_exchange_energy': 0., 'semilocal_xc_energy': 0., 'nuclear_repulsion': 0.,
            'masked_metric_electron_count': float(np.trace(dm)),
            'physical_metric_electron_count': float(np.trace(dm))+.05,
            'grid_electron_count': float(np.trace(dm))+.06}
        if self.mutate is not None: self.mutate(dm, value, len(self.calls))
        return value


def one_j_driver(fun, start, *, jac, **options):
    fun(start); jac(start)
    return SimpleNamespace(x=start.copy(), status=0, nfev=1, njev=1, message='Controlled one-J test')


class OccupiedSpaceRootCandidateTests(unittest.TestCase):
    def solve(self, evaluator=None, density=None, electrons=2, **options):
        evaluator = evaluator or FakeEvaluator()
        density = np.diag([2., 0.]) if density is None else density
        before = density.copy()
        result = candidate.solve_occupied_space_root_candidate(density=density, overlap=np.eye(len(density)),
            electrons=electrons, evaluate=evaluator, **options)
        np.testing.assert_array_equal(density, before)
        self.assertEqual(result['status'], 'OCCUPIED_SPACE_ROOT_DIAGNOSTIC_CANDIDATE_ENGINEERING_ONLY')
        self.assertEqual(result['evaluation_count'], len(evaluator.calls))
        self.assertEqual(result['evaluation_count'], len(result['evaluation_ledger']))
        self.assertLessEqual(result['evaluation_count'], options.get('maximum_evaluations', 201))
        self.assertEqual(result['native_execution_counts'], {'status': 'UNOBSERVED_ENGINEERING_GUARD_REQUIRED',
            'true_F': None, 'nr_rks': None})
        self.assertFalse(result['production_activation']); self.assertFalse(result['scientific_execution_authorized'])
        self.assertFalse(result['compute_enabled']); self.assertIsNone(result['delta_hartree'])
        self.assertEqual(result['parameters']['thresholds'], original.THRESHOLDS)
        self.assertEqual(result['accounting']['refunds'], 0)
        self.assertEqual(result['accounting']['automatic_retries'], 0)
        self.assertTrue(result['accounting']['closed'])
        for index, row in enumerate(result['evaluation_ledger'], 1):
            self.assertEqual(row['evaluation_count'], index)
            self.assertTrue(row['precharged'])
            self.assertEqual(row['phase'], evaluator.phases[index-1])
            self.assertEqual(row['density_id'], candidate.density_id(evaluator.calls[index-1]))
        return result, evaluator

    def test_live_interface_and_truthy_fake_authorization_refuse_before_first_callback(self):
        for authorization in (False, True):
            evaluator = FakeEvaluator()
            with self.subTest(authorization=authorization), self.assertRaisesRegex(candidate.ReferenceRefusal,
                    'Current scope is implementation and zero-F preparation only'):
                candidate.solve_occupied_space_root_candidate(density=np.diag([2., 0.]), overlap=np.eye(2),
                    electrons=2, evaluate=evaluator, execution_kind=candidate.LIVE_EXECUTION_KIND,
                    scientific_execution_authorized=authorization)
            self.assertEqual(evaluator.calls, [])
        for options in ({'scientific_execution_authorized': True}, {'scientific_execution_authorized': 1},
                        {'scientific_execution_authorized': np.bool_(False)}, {'execution_kind': 'PREPARED_MOLECULAR_DIAGNOSTIC'}):
            evaluator = FakeEvaluator()
            with self.subTest(options=options), self.assertRaises(ValueError):
                candidate.solve_occupied_space_root_candidate(density=np.diag([2., 0.]), overlap=np.eye(2),
                    electrons=2, evaluate=evaluator, **options)
            self.assertEqual(evaluator.calls, [])

    def test_pinned_real_scipy_one_chart_two_objectives_completes_at_most_two_large_jacobians_and_197_calls(self):
        d = np.diag([2.]*8+[0.]*6)
        before = dict(candidate.ENGINEERING_FAKE_CALLBACK_COUNTS)
        result, _ = self.solve(FakeEvaluator('large'), density=d, electrons=16)
        groups = [row for row in result['budget_admissions'] if row['kind'] == 'COMPLETE_JACOBIAN']
        self.assertEqual(result['parameters']['maximum_charts'], 1)
        self.assertEqual(result['parameters']['chart_max_nfev'], 2)
        self.assertEqual(result['parameters']['historical_budgeted_core_chart_max_nfev'], 8)
        self.assertEqual(len(groups), 2)
        self.assertTrue(all(row['status'] == 'COMPLETED' and row['actual_callbacks'] == 96 for row in groups))
        self.assertLessEqual(result['evaluation_count'], 197)
        self.assertEqual(result['scipy_result']['nfev'], 2)
        self.assertEqual(result['scipy_result']['njev'], 2)
        self.assertEqual(len(result['history']), 1)
        self.assertLess(result['history'][0]['after_residual_norm'], result['history'][0]['before_residual_norm'])
        self.assertNotEqual(result['returned_density']['density_id'], candidate.density_id(d))
        self.assertTrue(result['returned_density']['final_gate_evaluated'])
        self.assertIn(result['tail_execution']['actual_callbacks'], (1, 2))
        delta = {key: candidate.ENGINEERING_FAKE_CALLBACK_COUNTS[key]-before[key] for key in before}
        self.assertEqual(delta, {'entered': result['evaluation_count'], 'completed': result['evaluation_count'], 'failed': 0})

    def test_large_whole_jacobian_requires_all_96_callbacks_and_two_separate_tail_slots(self):
        d = np.diag([2.]*8+[0.]*6)
        for budget, expected_fd in ((99, 0), (100, 96)):
            with self.subTest(budget=budget), patch.object(candidate, 'least_squares', side_effect=one_j_driver):
                result, _ = self.solve(FakeEvaluator('large'), density=d, electrons=16, maximum_evaluations=budget)
            group = result['budget_admissions'][0]
            self.assertEqual(group['required_callbacks'], 96)
            self.assertEqual(group['tail_callbacks_reserved'], 2)
            self.assertEqual(group['actual_callbacks'], expected_fd)
            self.assertEqual(group['base_density_id'], result['optimizer_base']['density_id'])
            if budget == 99:
                self.assertEqual(result['evaluation_count'], 2)
                self.assertEqual(result['stop_reason'], 'JACOBIAN_BUDGET_ADMISSION_REFUSED')
                self.assertIsNone(result['endpoint_gate'])
                self.assertEqual(result['tail_execution']['actual_callbacks'], 0)
            else:
                self.assertEqual(result['evaluation_count'], 99)
                self.assertEqual(result['tail_execution']['actual_callbacks'], 1)

    def test_budget_refusal_preserves_last_normal_chart_not_best_sample_or_last_objective(self):
        initial = projector(-.6)
        def driver(fun, start, *, jac, **options):
            fun(start); jac(start)
            fun(np.array([.02]))
            self.fail('Reserved tail allowance may not be borrowed by another objective')
        with patch.object(candidate, 'least_squares', side_effect=driver):
            result, _ = self.solve(FakeEvaluator('unstable'), density=initial, maximum_evaluations=6)
        np.testing.assert_array_equal(result['density'], initial)
        self.assertEqual(result['history'], ())
        self.assertEqual(result['stop_reason'], 'EVALUATION_BUDGET_EXHAUSTED')
        self.assertIsNone(result['scipy_result'])
        self.assertIsNone(result['endpoint_gate']); self.assertIsNone(result['mapped_endpoint_gate'])
        self.assertEqual(result['tail_execution']['status'], 'NOT_EXECUTED')
        self.assertNotEqual(result['last_call']['density_id'], candidate.density_id(initial))
        self.assertEqual(result['returned_density']['density_id'], candidate.density_id(initial))

    def test_f_failure_inside_admitted_jacobian_is_charged_partial_and_never_retried(self):
        def failure(d, value, count):
            if count == 3: raise RuntimeError('Controlled fake FD failure')
        with patch.object(candidate, 'least_squares', side_effect=one_j_driver):
            result, _ = self.solve(FakeEvaluator('unstable', mutate=failure), density=projector(-.6), maximum_evaluations=6)
        self.assertEqual(result['evaluation_count'], 3)
        self.assertEqual(result['accounting']['callback_failed'], 1)
        self.assertEqual(result['budget_admissions'][0]['actual_callbacks'], 1)
        self.assertEqual(result['budget_admissions'][0]['unexecuted_planned_callbacks'], 1)
        self.assertEqual(result['last_validated_snapshot']['evaluation_count'], 2)
        self.assertEqual(result['last_call']['status'], 'REFUSED')
        self.assertEqual(result['tail_execution']['actual_callbacks'], 0)

    def test_snapshots_bind_actual_d_f_g_all_energy_and_count_fields_and_are_immutable(self):
        shared = np.zeros((2, 2))
        with patch.object(candidate, 'least_squares', side_effect=one_j_driver):
            result, _ = self.solve(FakeEvaluator('unstable', shared=shared), density=projector(-.6), maximum_evaluations=6)
        saved = result['snapshot_registry']['evaluation-1']
        f, g, d = saved['fock'].copy(), saved['raw_fock'].copy(), saved['density'].copy()
        shared[:] = 999
        np.testing.assert_array_equal(saved['fock'], f); np.testing.assert_array_equal(saved['raw_fock'], g)
        np.testing.assert_array_equal(saved['density'], d)
        for row in result['snapshot_registry'].values():
            raw = (b'AI4OrgChem-occupied-space-root-operator-v1\0'+bytes.fromhex(row['density_id'])
                +bytes.fromhex(row['fock_id'])+bytes.fromhex(row['raw_fock_id'])
                +struct.pack('<10d', row['total_energy'], row['electronic_energy'],
                    *(row['components'][key] for key in candidate.COMPONENTS),
                    *(row['electron_counts'][key] for key in candidate.COUNTS))
                +candidate.TRUE_OPERATOR.encode('ascii'))
            self.assertEqual(row['operator_id'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(set(row['optional_matrices']), {'J', 'K', 'Vxc'})
            self.assertEqual(row['execution_kind'], 'ENGINEERING_FAKE')
            self.assertEqual(row['operator_evidence_kind'], 'SYNTHETIC_CALLBACK_DECLARATION_NOT_MOLECULAR_F')
        with self.assertRaises(ValueError): saved['raw_fock'].setflags(write=True)
        with self.assertRaises(TypeError): saved['components']['nuclear_repulsion'] = 999
        with self.assertRaises(TypeError): result['parameters']['maximum_evaluations'] = 999
        with self.assertRaises(ValueError): result['density'][0, 0] = 999

    def test_original_qualified_pure_array_endpoint_requires_both_separately_charged_tail_evaluations(self):
        result, evaluator = self.solve(maximum_evaluations=3)
        self.assertTrue(result['engine_qualified'])
        self.assertEqual(result['evaluation_count'], 3)
        self.assertEqual(evaluator.phases, ['CURRENT_INITIAL', 'FINAL_RETURNED_DENSITY', 'FINAL_RAW_AUFBAU_DENSITY_RECHECK'])
        self.assertTrue(result['endpoint_gate']['qualified']); self.assertTrue(result['mapped_endpoint_gate']['qualified'])
        self.assertEqual(result['tail_execution']['actual_callbacks'], 2)
        self.assertEqual(result['engine_qualification_scope'], 'PURE_ARRAY_ORIGINAL_FINAL_GATES_NOT_MOLECULAR_ACCEPTANCE')
        self.assertEqual(result['molecular_acceptance'], 'NOT_ACCEPTED')
        self.assertFalse(result['compute_enabled'])

    def test_insufficient_tail_refuses_before_any_tail_callback_and_old_gap_stays_required(self):
        result, _ = self.solve(maximum_evaluations=2)
        self.assertEqual(result['evaluation_count'], 1)
        self.assertEqual(result['stop_reason'], 'FINAL_TAIL_BUDGET_ADMISSION_REFUSED')
        self.assertIsNone(result['endpoint_gate'])
        self.assertEqual(result['tail_execution']['actual_callbacks'], 0)
        result, _ = self.solve(FakeEvaluator('degenerate'), maximum_evaluations=3)
        self.assertFalse(result['engine_qualified'])
        self.assertFalse(result['endpoint_gate']['checks']['raw_gap'])
        self.assertIsNone(result['mapped_endpoint_gate'])

    def test_returned_energy_recheck_and_mapped_full_old_gates_are_not_relaxed(self):
        def changed_return(d, value, count):
            if count == 2:
                value['one_electron_energy'] += 2e-9
                value['electronic_energy'] += 2e-9
                value['total_energy'] += 2e-9
        result, _ = self.solve(FakeEvaluator(mutate=changed_return))
        self.assertEqual(result['stop_reason'], 'FINAL_RETURNED_DENSITY_ENERGY_RECHECK_FAILED')
        self.assertFalse(result['engine_qualified']); self.assertIsNone(result['mapped_endpoint_gate'])
        def changed_mapped(d, value, count):
            if count == 3:
                value['total_energy'] += 2e-9
                value['electronic_energy'] += 2e-9
        result, _ = self.solve(FakeEvaluator(mutate=changed_mapped))
        self.assertEqual(result['evaluation_count'], 3)
        self.assertEqual(result['stop_reason'], 'FINAL_RAW_AUFBAU_RECHECK_FAILED')
        self.assertFalse(result['mapped_endpoint_gate']['checks']['energy_closure'])

    def test_invalid_raw_g_scalar_counts_density_mutation_and_provenance_are_charged_refusals(self):
        changes = (
            lambda d, v: v.update(raw_fock=np.full((2, 2), np.nan)),
            lambda d, v: v.update(raw_fock=np.eye(2)),
            lambda d, v: v.update(electronic_energy=True),
            lambda d, v: v.update(masked_metric_electron_count=999.),
            lambda d, v: v.update(physical_metric_electron_count=float('inf')),
            lambda d, v: v.update(density_id='a'*64),
            lambda d, v: v.update(operator_source='DIIS'),
            lambda d, v: d.__setitem__((0, 0), d[0, 0]+.01),
        )
        for change in changes:
            def mutate(d, value, count): change(d, value)
            with self.subTest(change=change):
                result, _ = self.solve(FakeEvaluator(mutate=mutate))
                self.assertEqual(result['evaluation_count'], 1)
                self.assertEqual(result['accounting']['callback_completed'], 1)
                self.assertEqual(result['accounting']['validated_callbacks'], 0)
                self.assertEqual(result['snapshot_registry'], {})
                self.assertIsNone(result['endpoint_gate'])

    def test_source_initialization_bytes_are_frozen_and_explicit_initial_id_never_uses_v2(self):
        d = np.diag([2., 0.])
        def mutate(argument, value, count): d[0, 0] += .01
        result = candidate.solve_occupied_space_root_candidate(density=d, overlap=np.eye(2), electrons=2,
            evaluate=FakeEvaluator(mutate=mutate), expected_initial_density_id=candidate.density_id(d))
        self.assertEqual(result['stop_reason'], 'CALLER_SOURCE_ARRAY_MUTATED')
        self.assertEqual(result['evaluation_count'], 1)
        self.assertFalse(result['initialization']['ordinary_density_is_this_initialization'])
        self.assertEqual(result['initialization']['v2_seed_operation'], 'NOT_EXECUTED')
        self.assertFalse(result['initialization']['initial_density_projected_or_replaced'])
        evaluator = FakeEvaluator()
        with self.assertRaises(ValueError):
            candidate.solve_occupied_space_root_candidate(density=np.diag([2., 0.]), overlap=np.eye(2), electrons=2,
                evaluate=evaluator, expected_initial_density_id='a'*64)
        self.assertEqual(evaluator.calls, [])

    def test_missing_completed_jacobian_base_has_no_hidden_or_free_callback(self):
        def driver(fun, start, *, jac, **options):
            fun(start); jac(np.array([.01]))
            self.fail('A missing exact base must refuse')
        with patch.object(candidate, 'least_squares', side_effect=driver):
            result, _ = self.solve(FakeEvaluator('unstable'), density=projector(-.6))
        self.assertEqual(result['stop_reason'], 'JACOBIAN_BASE_SNAPSHOT_MISSING')
        self.assertEqual(result['evaluation_count'], 2)
        self.assertEqual(result['budget_admissions'], ())
        self.assertEqual(result['fd_samples'], ())

    def test_pinned_three_point_zero_nonzero_and_bound_steps_keep_old_library_rules(self):
        for point in (0., .1, -.1, .25, -.25):
            z = np.array([point])
            def driver(fun, start, *, jac, **options):
                self.assertEqual(options['max_nfev'], 2)
                self.assertNotIn('callback', options)
                fun(z); jac(z)
                return SimpleNamespace(x=z.copy(), status=0, nfev=1, njev=1, message='Controlled pinned step test')
            with self.subTest(point=point), patch.object(candidate, 'least_squares', side_effect=driver):
                result, _ = self.solve(FakeEvaluator('unstable'), density=projector(-.6), maximum_evaluations=6)
            observed = [np.asarray(row['local_rotation_coordinates']) for row in result['evaluation_ledger'] if row['phase'] == 'FD_SAMPLE']
            expected = []
            def polynomial(point_array): expected.append(point_array.copy()); return point_array+point_array**3
            approx_derivative(polynomial, z, method='3-point', rel_step=1e-5, f0=z+z**3,
                bounds=(-.25, .25), sparsity=None, workers=1)
            self.assertEqual(len(observed), 2)
            for left, right in zip(observed, expected): np.testing.assert_array_equal(left, right)

    def test_invalid_configuration_nonmanifold_and_nonpinned_version_have_zero_callbacks(self):
        for options in ({'maximum_evaluations': 202}, {'maximum_evaluations': True}, {'maximum_charts': 0},
                        {'chart_max_nfev': 0}, {'chart_max_nfev': 9}, {'finite_difference_step': True},
                        {'initialization_policy': 'FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0'}):
            evaluator = FakeEvaluator()
            with self.subTest(options=options), self.assertRaises(ValueError):
                candidate.solve_occupied_space_root_candidate(density=np.diag([2., 0.]), overlap=np.eye(2),
                    electrons=2, evaluate=evaluator, **options)
            self.assertEqual(evaluator.calls, [])
        evaluator = FakeEvaluator()
        with patch.object(candidate, 'scipy_version', '0.0.0'), self.assertRaises(ValueError):
            candidate.solve_occupied_space_root_candidate(density=np.diag([2., 0.]), overlap=np.eye(2), electrons=2, evaluate=evaluator)
        self.assertEqual(evaluator.calls, [])
        with self.assertRaises(ValueError):
            candidate.solve_occupied_space_root_candidate(density=np.eye(2), overlap=np.eye(2), electrons=2, evaluate=evaluator)
        self.assertEqual(evaluator.calls, [])

    def test_raw_g_is_only_recorded_and_original_projected_f_controls_residual_and_final_gates(self):
        source = Path(candidate.__file__).read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn('original.qualify(', source)
        self.assertIn("transformed = x.T@value['fock']@x", source)
        self.assertNotIn("transformed = x.T@value['raw_fock']@x", source)
        self.assertIn('max_nfev=chart_max_nfev', source)
        self.assertNotIn('callback=', source)
        self.assertEqual(candidate.THRESHOLDS, original.THRESHOLDS)
        self.assertFalse(candidate.LIVE_EXECUTION_IMPLEMENTED)
        self.assertEqual(candidate.SELECTED_INITIAL_DENSITY_ID,
            '6b0d501aba96ac5c53ca633491e105d7c5dab13836350bd6d7350437f91bd7c0')


if __name__ == '__main__': unittest.main()
