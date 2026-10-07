"""Fixed pure-array native-adapter candidate tests; require outer native guards.

No source engine is instantiated or executed here. Pinned SciPy1.18 is tested
by the root agent's guarded engineering process, never installed by this file.
"""
import ast
import hashlib
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
from reference import occupied_space_root_native_candidate as candidate
from reference import residual_candidate as original


def initial(theta=0.):
    occupied = np.eye(14)[:, :8].copy()
    occupied[0, 0], occupied[8, 0] = math.cos(theta), math.sin(theta)
    return 2*occupied@occupied.T


def one_j_driver(fun, start, *, jac, **_options):
    fun(start); jac(start)
    return SimpleNamespace(x=start.copy(), status=0, nfev=1, njev=1, message='Fixed one-J test driver')


class RootNativeCandidateTests(unittest.TestCase):
    def solve(self, *, evaluator=None, density=None, hook=None, mask=None, **options):
        density = initial() if density is None else density
        evaluator = evaluator or candidate.SyntheticRootEvaluator(expected_initial_density_id=candidate.density_id(density))
        original_bytes = density.tobytes()
        result = candidate.solve_occupied_space_root_native_candidate(density=density, overlap=np.eye(14),
            electrons=16, evaluate=evaluator, matrix_delete_mask=mask,
            expected_initial_density_id=candidate.density_id(density), admission_hook=hook, **options)
        self.assertEqual(density.tobytes(), original_bytes)
        self.assertEqual(result['execution_kind'], candidate.ENGINEERING_EXECUTION_KIND)
        self.assertFalse(result['scientific_execution_authorized'])
        self.assertFalse(result['source_execution_authorized_by_this_module'])
        self.assertFalse(result['compute_enabled']); self.assertFalse(result['production_activation'])
        self.assertIsNone(result['delta_hartree']); self.assertIsNone(result['native_execution_counts'])
        self.assertEqual(result['parameters']['thresholds'], original.THRESHOLDS)
        self.assertEqual(result['evaluation_count'], len(result['evaluation_ledger']))
        self.assertEqual(result['evaluation_count'], evaluator.snapshot()['simulated_callback_counts']['entered'])
        self.assertLessEqual(result['evaluation_count'], 201)
        return result, evaluator

    def test_exact_closed_evaluator_types_and_explicit_false_are_required(self):
        class FakePrepared:
            def __call__(self, *_args):
                raise AssertionError('Not entered')
        class FakeSyntheticSubclass(candidate.SyntheticRootEvaluator):
            pass
        for evaluator, auth in [(FakePrepared(), False), (lambda *_: {}, False),
                                 (FakeSyntheticSubclass(), False), (candidate.SyntheticRootEvaluator(), True),
                                 (candidate.SyntheticRootEvaluator(), 1)]:
            with self.subTest(kind=type(evaluator).__name__, auth=auth), self.assertRaises(ValueError):
                candidate.solve_occupied_space_root_native_candidate(density=initial(), overlap=np.eye(14),
                    electrons=16, evaluate=evaluator, scientific_execution_authorized=auth)

    def test_source_mode_without_authorization_refuses_before_import_charge_or_callback(self):
        evaluator = candidate.SyntheticRootEvaluator()
        for auth in [False, None, 0, 'true']:
            with self.subTest(auth=auth), self.assertRaises(ValueError):
                candidate.solve_occupied_space_root_native_candidate(density=initial(), overlap=np.eye(14),
                    electrons=16, evaluate=evaluator, execution_kind=candidate.SOURCE_EXECUTION_KIND,
                    scientific_execution_authorized=auth)
        self.assertEqual(evaluator.snapshot()['simulated_callback_counts']['entered'], 0)

    def test_source_mode_true_cannot_accept_matching_synthetic_metadata(self):
        evaluator = candidate.SyntheticRootEvaluator(expected_initial_density_id=candidate.SELECTED_INITIAL_DENSITY_ID)
        with self.assertRaises(ValueError):
            candidate.solve_occupied_space_root_native_candidate(density=initial(), overlap=np.eye(14),
                electrons=16, evaluate=evaluator, execution_kind=candidate.SOURCE_EXECUTION_KIND,
                scientific_execution_authorized=True, expected_initial_density_id=candidate.SELECTED_INITIAL_DENSITY_ID)
        self.assertEqual(evaluator.snapshot()['simulated_callback_counts']['entered'], 0)

    def test_fixed_configuration_and_14_16_48_dimensions_refuse_without_callbacks(self):
        for options in [{'maximum_evaluations':200}, {'maximum_charts':2}, {'chart_max_nfev':8},
                        {'finite_difference_step':2e-5}, {'trust_radius':.5},
                        {'maximum_evaluations':True}, {'initialization_policy':'FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0'}]:
            evaluator = candidate.SyntheticRootEvaluator()
            with self.subTest(options=options), self.assertRaises(ValueError):
                candidate.solve_occupied_space_root_native_candidate(density=initial(), overlap=np.eye(14),
                    electrons=16, evaluate=evaluator, **options)
            self.assertEqual(evaluator.snapshot()['simulated_callback_counts']['entered'], 0)
        for n, electrons in [(2,2), (14,14)]:
            with self.subTest(n=n,electrons=electrons), self.assertRaises(ValueError):
                candidate.solve_occupied_space_root_native_candidate(density=np.diag([2.]*(electrons//2)+[0.]*(n-electrons//2)),
                    overlap=np.eye(n), electrons=electrons, evaluate=candidate.SyntheticRootEvaluator())

    def test_nonprojector_wrong_initial_identity_and_nonpinned_scipy_are_zero_callback_refusals(self):
        for density, expected in [(initial()+.001*np.eye(14),None), (initial(),'0'*64)]:
            evaluator=candidate.SyntheticRootEvaluator()
            with self.subTest(expected=expected), self.assertRaises(ValueError):
                candidate.solve_occupied_space_root_native_candidate(density=density,overlap=np.eye(14),electrons=16,
                    evaluate=evaluator,expected_initial_density_id=expected)
            self.assertEqual(evaluator.snapshot()['simulated_callback_counts']['entered'],0)
        with patch.object(candidate,'scipy_version','unaccepted'), self.assertRaises(ValueError):
            self.solve()

    def test_qualified_synthetic_endpoint_still_has_two_separate_original_tail_calls(self):
        events=[]
        result,evaluator=self.solve(hook=lambda row:events.append(dict(row)))
        self.assertTrue(result['engine_qualified'])
        self.assertTrue(result['endpoint_gate']['qualified']); self.assertTrue(result['mapped_endpoint_gate']['qualified'])
        self.assertEqual([row['phase'] for row in result['evaluation_ledger']],
            ['CURRENT_INITIAL','FINAL_RETURNED_DENSITY','FINAL_RAW_AUFBAU_DENSITY_RECHECK'])
        self.assertEqual(result['tail_execution']['actual_callbacks'],2)
        self.assertEqual([row['status'] for row in events],['ADMITTED','STARTED','COMPLETED'])
        self.assertTrue(all(row['group_id']==1 and row['planned_callbacks']==2 for row in events))
        self.assertEqual(events[-1]['actual_callbacks'],2)
        contexts=evaluator.snapshot()['simulated_callback_records']
        self.assertIsNone(contexts[0]['context']['admission_group_id'])
        self.assertEqual(contexts[1]['context']['admission_group_id'],1)
        self.assertEqual(contexts[2]['context']['admission_group_id'],1)
        self.assertEqual(result['numeric_instrumentation_status'],'SIMULATED_NON_MOLECULAR_REQUIRES_OUTER_14_NATIVE_GUARDS')

    def test_whole_dense_96_group_and_explicit_fd_contexts_are_persisted(self):
        events=[]
        with patch.object(candidate,'least_squares',one_j_driver):
            result,evaluator=self.solve(evaluator=candidate.SyntheticRootEvaluator('noncommuting'),
                hook=lambda row:events.append(dict(row)))
        jac=[row for row in events if row['kind']=='COMPLETE_JACOBIAN']
        self.assertEqual([row['status'] for row in jac],['ADMITTED','STARTED','COMPLETED'])
        self.assertEqual(jac[-1]['planned_callbacks'],96); self.assertEqual(jac[-1]['actual_callbacks'],96)
        self.assertEqual(jac[-1]['tail_callbacks_reserved'],2)
        fd=[row for row in evaluator.snapshot()['simulated_callback_records'] if row['phase']=='FD_SAMPLE']
        self.assertEqual(len(fd),96)
        self.assertEqual([row['context']['fd_sample'] for row in fd],list(range(1,97)))
        self.assertTrue(all(row['context']['admission_group_id']==jac[0]['group_id'] for row in fd))
        self.assertTrue(all(row['context']['base_density_id']==jac[0]['base_density_id'] for row in fd))
        self.assertFalse(result['engine_qualified'])

    def test_whole_group_exact_boundary_passes_and_one_short_makes_zero_fd_calls(self):
        for extra,before,admitted in [(102,103,True),(103,104,False)]:
            def driver(fun,start,*,jac,**_options):
                for _ in range(extra):fun(start)
                jac(start)
                return SimpleNamespace(x=start.copy(),status=0,nfev=extra,njev=1,message='Hard budget fixture')
            events=[]
            with self.subTest(extra=extra),patch.object(candidate,'least_squares',driver):
                result,evaluator=self.solve(evaluator=candidate.SyntheticRootEvaluator('noncommuting'),
                    hook=lambda row:events.append(dict(row)))
                group=next(row for row in events if row['kind']=='COMPLETE_JACOBIAN')
                self.assertEqual(group['call_count_before'],before);self.assertEqual(group['admitted'],admitted)
                fd=[row for row in evaluator.snapshot()['simulated_callback_records'] if row['phase']=='FD_SAMPLE']
                self.assertEqual(len(fd),96 if admitted else 0)
                if not admitted:
                    self.assertEqual(result['stop_reason'],'JACOBIAN_BUDGET_ADMISSION_REFUSED')
                    self.assertEqual(result['tail_execution']['actual_callbacks'],0)
                    self.assertEqual(group['status'],'REFUSED_ZERO_CALLBACKS')

    def test_partial_jacobian_failure_is_charged_stops_and_retains_formal_density(self):
        events=[]
        with patch.object(candidate,'least_squares',one_j_driver):
            result,evaluator=self.solve(evaluator=candidate.SyntheticRootEvaluator('noncommuting',fault='callback_failure',fault_at=5),
                hook=lambda row:events.append(dict(row)))
        group=[row for row in events if row['kind']=='COMPLETE_JACOBIAN'][-1]
        self.assertEqual(group['status'],'REFUSED_PARTIAL_NO_RETRY')
        self.assertEqual(group['actual_callbacks'],3);self.assertEqual(group['unexecuted_planned_callbacks'],93)
        self.assertEqual(result['evaluation_count'],5);self.assertEqual(result['tail_execution']['actual_callbacks'],0)
        np.testing.assert_array_equal(result['returned_density']['density'],initial())
        self.assertEqual(evaluator.snapshot()['simulated_callback_counts'],{'entered':5,'completed':4,'failed':1})

    def test_hook_refusal_at_started_group_closes_it_without_fd_or_tail(self):
        events=[]
        def hook(row):
            events.append(dict(row))
            if row['kind']=='COMPLETE_JACOBIAN' and row['status']=='STARTED':
                raise OSError('Registered persistence failure')
        with patch.object(candidate,'least_squares',one_j_driver):
            result,evaluator=self.solve(evaluator=candidate.SyntheticRootEvaluator('noncommuting'),hook=hook)
        self.assertEqual(result['stop_reason'],'ADMISSION_HOOK_REFUSED')
        self.assertEqual(result['evaluation_count'],2);self.assertEqual(result['tail_execution']['actual_callbacks'],0)
        self.assertEqual(events[-1]['status'],'REFUSED_PARTIAL_NO_RETRY')
        self.assertEqual(events[-1]['actual_callbacks'],0)

    def test_admission_hook_cannot_mutate_normal_or_base_dict_bypass_rows(self):
        for bypass in [False,True]:
            def hook(row):
                if bypass:dict.__setitem__(row,'planned_callbacks',999)
                else:row['planned_callbacks']=999
            with self.subTest(bypass=bypass):
                result,_=self.solve(hook=hook)
                self.assertIn(result['stop_reason'],['ADMISSION_HOOK_REFUSED','ADMISSION_HOOK_MUTATED_ROW'])
                self.assertEqual(result['evaluation_count'],1);self.assertFalse(result['engine_qualified'])
                self.assertEqual(result['budget_admissions'][0]['planned_callbacks'],2)

    def test_matching_fake_identity_labels_cannot_hide_invalid_wire_fields(self):
        for fault in ['wrong_density_id','wrong_operator_source','projection_mismatch','nonsymmetric_raw',
                      'electronic_closure','masked_count','missing_raw','missing_grid_count','nonfinite_component','mutate_density']:
            with self.subTest(fault=fault):
                result,_=self.solve(evaluator=candidate.SyntheticRootEvaluator(fault=fault,fault_at=1))
                self.assertEqual(result['evaluation_count'],1);self.assertFalse(result['engine_qualified'])
                self.assertEqual(result['tail_execution']['actual_callbacks'],0)
                self.assertNotEqual(result['evaluation_ledger'][0]['status'],'VALIDATED')

    def test_same_density_complete_ledger_changes_refuse_even_with_same_f_and_total(self):
        mask=np.zeros((14,14),dtype=bool);mask[4,9]=mask[9,4]=True
        for fault in ['component_repeat','grid_count_repeat','deleted_raw_repeat']:
            with self.subTest(fault=fault):
                result,_=self.solve(evaluator=candidate.SyntheticRootEvaluator(fault=fault),mask=mask)
                self.assertEqual(result['stop_reason'],'NONREPRODUCIBLE_SAME_DENSITY_OPERATOR')
                self.assertEqual(result['evaluation_count'],2);self.assertFalse(result['engine_qualified'])

    def test_immutable_snapshots_bind_full_operator_and_do_not_infer_native_counts(self):
        result,_=self.solve()
        snapshot=result['snapshot_registry']['evaluation-1']
        self.assertEqual(snapshot['operator_id'],candidate.operator_id(snapshot['density_id'],snapshot['fock'],snapshot['raw_fock'],
            snapshot['total_energy'],snapshot['components'],snapshot['electronic_energy'],snapshot['electron_counts']))
        with self.assertRaises(TypeError):snapshot['components']['coulomb_energy']=1.
        with self.assertRaises(ValueError):snapshot['density'].setflags(write=True)
        self.assertIsNone(result['native_execution_counts']);self.assertIsNone(result['native_accounting_snapshot'])
        self.assertEqual(snapshot['operator_evidence_kind'],'SIMULATED_CALLBACK_NOT_MOLECULAR_F')

    def test_low_gap_and_failed_returned_gate_do_not_run_mapped_tail(self):
        result,_=self.solve(evaluator=candidate.SyntheticRootEvaluator('degenerate'))
        self.assertFalse(result['engine_qualified']);self.assertFalse(result['endpoint_gate']['checks']['raw_gap'])
        self.assertIsNone(result['mapped_endpoint_gate']);self.assertEqual(result['tail_execution']['actual_callbacks'],1)

    def test_mapped_original_gate_and_energy_tolerance_are_kept(self):
        for fault in ['mapped_density_bad_operator','mapped_energy_shift']:
            with self.subTest(fault=fault):
                result,_=self.solve(evaluator=candidate.SyntheticRootEvaluator(fault=fault),density=initial(5e-10))
                self.assertTrue(result['endpoint_gate']['qualified']);self.assertFalse(result['engine_qualified'])
                self.assertEqual(result['tail_execution']['actual_callbacks'],2)
                self.assertEqual(result['stop_reason'],'FINAL_RAW_AUFBAU_RECHECK_FAILED')
                if fault=='mapped_energy_shift':
                    self.assertTrue(result['mapped_endpoint_gate']['qualified'])
                    self.assertGreater(result['endpoint_gate']['mapped_density_energy_change_hartree'],1e-9)
                else:self.assertFalse(result['mapped_endpoint_gate']['qualified'])

    def test_real_pinned_scipy_two_objectives_never_exceeds_197_simulated_callbacks(self):
        events=[]
        result,_=self.solve(evaluator=candidate.SyntheticRootEvaluator('noncommuting'),hook=lambda row:events.append(dict(row)))
        self.assertLessEqual(result['evaluation_count'],197)
        groups=[row for row in events if row['kind']=='COMPLETE_JACOBIAN' and row['status']=='COMPLETED']
        self.assertLessEqual(len(groups),2)
        self.assertTrue(all(row['actual_callbacks']==96 for row in groups))
        self.assertLessEqual(result['scipy_result']['nfev'],2)
        self.assertEqual(result['parameters']['formal_return_policy'],
            'LAST_NORMALLY_RETURNED_STRICTLY_IMPROVING_CHART_NOT_BEST_OR_INTERNAL_UNRETURNED_ITERATE')

    def test_missing_completed_base_has_no_uncharged_replacement_evaluation(self):
        def driver(fun,start,*,jac,**_options):
            jac(start)
        with patch.object(candidate,'least_squares',driver):
            result,_=self.solve(evaluator=candidate.SyntheticRootEvaluator('noncommuting'))
        self.assertEqual(result['stop_reason'],'JACOBIAN_BASE_SNAPSHOT_MISSING')
        self.assertEqual(result['evaluation_count'],1);self.assertEqual(result['tail_execution']['actual_callbacks'],0)

    def test_original_qualify_and_derivative_functions_are_reused_no_science_imports(self):
        path=Path(candidate.__file__)
        tree=ast.parse(path.read_bytes())
        calls=[node for node in ast.walk(tree) if isinstance(node,ast.Call)]
        self.assertTrue(any(isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name)
            and node.func.value.id=='original' and node.func.attr=='qualify' for node in calls))
        self.assertTrue(any(isinstance(node.func,ast.Name) and node.func.id=='approx_derivative' for node in calls))
        self.assertFalse(any(isinstance(node,ast.ImportFrom) and (node.module or '').startswith('ai4orgchem') for node in ast.walk(tree)))
        self.assertIn('source-bound',path.read_text(encoding='utf-8'))

    def engineering_accounting(self, *, scenario='diagonal', fault=None, fault_at=2):
        from runtime.user_molecule.residual_budget import ConditionalCallbackBudget
        from runtime.user_molecule.root_native_accounting import RootNativeAccounting
        temporary=tempfile.TemporaryDirectory(prefix='root-native-synthetic-ledger-')
        self.addCleanup(temporary.cleanup)
        root=Path(temporary.name)
        digest=lambda value:hashlib.sha256(value.encode()).hexdigest()
        identity={'mode':candidate.ENGINEERING_EXECUTION_KIND,'execution_kind':candidate.ENGINEERING_EXECUTION_KIND,
            'scientific_execution_authorized':False,'geometry_sha256':digest('SYNTHETIC14_NOT_MOLECULE'),
            'profile_sha256':digest('SYNTHETIC_ONLY'),'dependencies_sha256':digest('PINNED_ARRAY_TESTS'),
            'initial_density_id':candidate.density_id(initial())}
        book=ConditionalCallbackBudget(path=root/'callbacks.json',batch_id='candidate-engineering',identity=identity,
            path_limits={'independent_reference':201},total_limit=201)
        accounting=RootNativeAccounting(root/'accounting',book)
        evaluator=candidate.SyntheticRootEvaluator(scenario,fault=fault,fault_at=fault_at,
            expected_initial_density_id=identity['initial_density_id'],accounting=accounting)
        return evaluator,accounting,book

    def test_durable_engineering_book_matches_qualified_two_tails_without_source_nr_claim(self):
        evaluator,accounting,book=self.engineering_accounting()
        result,_=self.solve(evaluator=evaluator)
        self.assertTrue(result['engine_qualified'])
        final=accounting.close(result['stop_reason'])
        self.assertEqual(final['callback_slots'],{'charged':3,'pending':0,'succeeded':3,'failed':0,'limit':201})
        self.assertEqual(final['engineering_simulated_native_counts'],{'entered':3,'completed':3,'failed':0})
        self.assertIsNone(final['source_native_dispatch_counts']['entered'])
        self.assertIsNone(result['native_execution_counts'])
        self.assertEqual(book.snapshot()['charged_slots'],result['evaluation_count'])

    def test_durable_97_remaining_slots_refuse_whole_96_plus_two_group_before_fd(self):
        evaluator,accounting,book=self.engineering_accounting(scenario='noncommuting')
        def driver(fun,start,*,jac,**_options):
            for _ in range(103):fun(start)
            jac(start)
        with patch.object(candidate,'least_squares',driver):
            result,_=self.solve(evaluator=evaluator,hook=accounting.record_admission)
        final=accounting.close(result['stop_reason'])
        self.assertEqual(result['stop_reason'],'JACOBIAN_BUDGET_ADMISSION_REFUSED')
        self.assertEqual(book.snapshot()['charged_slots'],104)
        self.assertEqual(final['admission_groups'][1]['row']['status'],'REFUSED_ZERO_CALLBACKS')
        self.assertEqual(final['admission_groups'][1]['slots'],[])
        self.assertEqual(result['tail_execution']['actual_callbacks'],0)

    def test_durable_partial_failure_keeps_failed_simulated_nr_and_no_tail(self):
        evaluator,accounting,book=self.engineering_accounting(scenario='noncommuting',fault='callback_failure',fault_at=5)
        with patch.object(candidate,'least_squares',one_j_driver):
            result,_=self.solve(evaluator=evaluator)
        final=accounting.close(result['stop_reason'])
        self.assertEqual(final['callback_slots']['charged'],5);self.assertEqual(final['callback_slots']['failed'],1)
        self.assertEqual(final['engineering_simulated_native_counts'],{'entered':5,'completed':4,'failed':1})
        self.assertIsNone(final['source_native_dispatch_counts']['failed'])
        self.assertEqual(final['admission_groups'][1]['row']['status'],'REFUSED_PARTIAL_NO_RETRY')
        self.assertEqual(final['admission_groups'][1]['row']['actual_callbacks'],3)
        self.assertEqual(result['tail_execution']['actual_callbacks'],0)

    def test_durable_gap_failure_has_only_one_returned_tail_and_stays_unqualified(self):
        evaluator,accounting,book=self.engineering_accounting(scenario='degenerate')
        result,_=self.solve(evaluator=evaluator)
        final=accounting.close(result['stop_reason'])
        self.assertFalse(result['engine_qualified'])
        self.assertEqual(final['callback_slots']['charged'],2)
        self.assertEqual(final['admission_groups'][1]['row']['actual_callbacks'],1)
        self.assertEqual(result['tail_execution']['actual_callbacks'],1)


if __name__=='__main__':unittest.main()
