"""Prepared candidate tests use tiny FakeXC arrays, never a molecular engine."""
import copy
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

import test_reference_residual_seed_v2 as fixtures
from reference import residual_budgeted_seed as adapter
from reference import residual_candidate as retained

ENGINEERING_FAKE_XC_COUNTS = {'entered': 0, 'completed': 0, 'failed': 0}

def fixture(**options):
    helper = fixtures.IndependentResidualSeedV2Tests('test_constructs_real_seed_without_callback_or_cache_mutation')
    ordinary, raw = helper.fixture(**options)
    original = raw.nr_rks
    def counted_fake(*args, **kwargs):
        ENGINEERING_FAKE_XC_COUNTS['entered'] += 1
        try:
            value = original(*args, **kwargs)
        except BaseException:
            ENGINEERING_FAKE_XC_COUNTS['failed'] += 1
            raise
        ENGINEERING_FAKE_XC_COUNTS['completed'] += 1
        return value
    raw.nr_rks = counted_fake
    return ordinary, raw


class BudgetedPreparedSeedTests(unittest.TestCase):
    def construct(self, ordinary, **options):
        return adapter.PreparedBudgetedSeedReference(ordinary=ordinary, rule_path=fixtures.RULES,
            expected_sha256=hashlib.sha256(fixtures.RULES.read_bytes()).hexdigest(), **options)

    def test_explicit_real_diagnostic_kind_rejected_before_any_callback(self):
        ordinary, raw = fixture()
        with self.assertRaises(ValueError):
            self.construct(ordinary, execution_kind='PREPARED_MOLECULAR_DIAGNOSTIC')
        self.assertEqual(raw.calls, [])

    def test_mutated_execution_kind_refused_before_next_callback(self):
        ordinary, raw = fixture(); runner = self.construct(ordinary)
        runner.execution_kind = 'PREPARED_MOLECULAR_DIAGNOSTIC'
        with self.assertRaises(ValueError) as caught: runner.evaluate(runner.seed_density)
        self.assertEqual(caught.exception.reason, 'ENGINEERING_EXECUTION_KIND_CHANGED')
        self.assertEqual(raw.calls, [])
        self.assertEqual(runner.ledger, [])

    def test_qualified_array_case_never_grants_molecular_or_research_compute(self):
        ordinary, raw = fixture(changed_seed=False)
        saved = {k:v.copy() for k,v in ordinary.arrays.items()}
        runner = self.construct(ordinary)
        result = runner.run(maximum_iterations=1)
        self.assertTrue(result['engine_qualified'])
        self.assertEqual(result['reference_adapter_id'], adapter.ADAPTER_ID)
        self.assertEqual(result['initialization']['policy'], adapter.POLICY_ID)
        self.assertEqual(result['initialization']['ordinary_density_id'], retained.density_id(ordinary.arrays['density']))
        self.assertEqual(result['initialization']['lower_solver_density_argument_id'], retained.density_id(runner.seed_density))
        self.assertFalse(result['production_activation'])
        self.assertEqual(result['molecular_acceptance'], 'NOT_EXECUTED')
        self.assertEqual(result['molecular_execution'], 'NOT_EXECUTED_ENGINEERING_FAKE')
        self.assertEqual(result['real_functional_attempt_count'], 0)
        self.assertIsNone(result['delta_hartree'])
        self.assertIsNone(result['new_scientific_budget'])
        self.assertEqual(result['global_evaluation_count'], len(raw.calls))
        self.assertEqual(result['fake_solver_callback_attempts'], result['fake_prepared_callback_attempts'])
        self.assertEqual(result['phase_mapping_status'], 'COMPLETE')
        for k,v in saved.items(): np.testing.assert_array_equal(ordinary.arrays[k],v)

    def test_frozen_seed_parent_and_no_retry_after_run(self):
        ordinary, raw = fixture(); runner = self.construct(ordinary,maximum_evaluations=4)
        d0 = ordinary.arrays['density'].copy(); seed = runner.seed_density.copy()
        result = runner.run(maximum_iterations=1)
        self.assertFalse(result['engine_qualified'])
        self.assertLessEqual(len(raw.calls),4)
        self.assertEqual(result['initialization']['policy'], adapter.POLICY_ID)
        self.assertTrue(result['prepared_budget_settled'])
        np.testing.assert_array_equal(ordinary.arrays['density'], d0)
        np.testing.assert_array_equal(runner.seed_density,seed)
        before = len(raw.calls)
        with self.assertRaises(ValueError): runner.run(maximum_iterations=1)
        with self.assertRaises(ValueError): runner.evaluate(runner.seed_density)
        self.assertEqual(len(raw.calls),before)

    def test_prior_fake_direct_callback_is_not_a_new_solver_allowance(self):
        ordinary, raw = fixture(changed_seed=False); runner = self.construct(ordinary,maximum_evaluations=3)
        runner.evaluate(runner.seed_density)
        result = runner.run(maximum_iterations=1)
        self.assertEqual(result['global_evaluation_limit'],3)
        self.assertLessEqual(result['global_evaluation_count'],3)
        self.assertEqual(result['fake_prepared_callback_attempts'], result['global_evaluation_count']-1)
        self.assertEqual(len(raw.calls),result['global_evaluation_count'])
        self.assertFalse(result['production_activation'])

    def test_caller_mo_mutation_refuses_without_fake_xc(self):
        ordinary, raw = fixture(); runner = self.construct(ordinary)
        ordinary.arrays['mo_occupations'][0] = 1.
        with self.assertRaises(ValueError): runner.run(maximum_iterations=1)
        self.assertEqual(raw.calls, [])
        self.assertTrue(runner._settled)

    def test_mutation_during_fake_callback_consumes_solver_attempt_and_preserves_refusal(self):
        ordinary, raw = fixture(); runner = self.construct(ordinary)
        raw.mutation = lambda: ordinary.arrays['mo_coefficients'].__setitem__((0,0),.123)
        result = runner.run(maximum_iterations=1)
        self.assertFalse(result['engine_qualified'])
        self.assertEqual(len(raw.calls),1)
        self.assertEqual(result['fake_solver_callback_attempts'],1)
        self.assertEqual(result['fake_prepared_callback_attempts'],1)
        self.assertEqual(result['prepared_evaluation_ledger'][0]['reason'],'FROZEN_CACHED_MO_CHANGED')
        self.assertIsNone(result['delta_hartree'])

    def test_shared_seed_used_without_replacing_independent_construction(self):
        ordinary, raw = fixture(); first = self.construct(ordinary)
        shared = first.seed_density.copy(); runner = self.construct(ordinary,shared_seed_density=shared,maximum_evaluations=4)
        result = runner.run(maximum_iterations=1)
        self.assertEqual(result['seed_receipt']['shared_seed_admission']['status'],'PASS_ARRAY_REFERENCE_ENTRY_ONLY')
        self.assertEqual(result['seed_receipt']['actual_reference_entry_execution'],'EXECUTED_UNCHANGED_LOW_LEVEL_FRAME_CHECKS')
        self.assertEqual(runner.seed_receipt['actual_reference_entry_execution'],'NOT_EXECUTED_BEFORE_RUN')
        self.assertEqual(result['used_seed_density_identity'],first.seed_receipt['used_seed_density_identity'])
        self.assertFalse(result['production_activation'])

    def test_qualified_lower_result_with_missing_prepared_mapping_is_refused(self):
        ordinary, raw = fixture(changed_seed=False); runner = self.construct(ordinary)
        solve = adapter.candidate.solve_budgeted_candidate
        def mismatched(**options):
            result = solve(**options)
            self.assertTrue(result['engine_qualified'])
            result['evaluation_ledger'] = result['evaluation_ledger'][:-1]
            return result
        with patch.object(adapter.candidate,'solve_budgeted_candidate',mismatched):
            result = runner.run(maximum_iterations=1)
        self.assertTrue(result['lower_engine_qualified'])
        self.assertFalse(result['engine_qualified'])
        self.assertEqual(result['stop_reason'],'ADAPTER_PHASE_ACCOUNTING_MAPPING_REFUSED')
        self.assertIn('CALLBACK_COUNT_MISMATCH',result['phase_mapping_reasons'])
        self.assertEqual(len(raw.calls),3)
        self.assertIsNone(result['delta_hartree'])

    def test_snapshot_identity_mismatch_cannot_be_qualified_by_adapter(self):
        for key,expected in (('density_id','CALLBACK_DENSITY_ID_MISMATCH'),('fock_id','CALLBACK_FOCK_ID_MISMATCH')):
            ordinary, raw = fixture(changed_seed=False); runner = self.construct(ordinary)
            solve = adapter.candidate.solve_budgeted_candidate
            def mismatched(**options):
                result = solve(**options)
                ledger = [dict(row) for row in result['evaluation_ledger']]
                ledger[0][key] = '11'*32
                result['evaluation_ledger'] = ledger
                return result
            with patch.object(adapter.candidate,'solve_budgeted_candidate',mismatched):
                result = runner.run(maximum_iterations=1)
            self.assertFalse(result['engine_qualified'])
            self.assertIn(expected,result['phase_mapping_reasons'])
            self.assertTrue(result['lower_engine_qualified'])
            self.assertEqual(len(raw.calls),3)

    def test_prepared_ledger_mutation_refuses_without_changing_numeric_gate(self):
        ordinary, raw = fixture(changed_seed=False); runner = self.construct(ordinary)
        raw.mutation = lambda: runner.ledger[-1].__setitem__('density_id','00'*32)
        result = runner.run(maximum_iterations=1)
        self.assertTrue(result['endpoint_gate']['qualified'])
        self.assertTrue(result['lower_engine_qualified'])
        self.assertFalse(result['engine_qualified'])
        self.assertEqual(result['phase_mapping_status'],'PARTIAL_CALLBACK_ACCOUNTING_MAPPING_REFUSED')
        self.assertEqual(len(raw.calls),3)
        self.assertEqual(result['global_evaluation_count'],3)
        self.assertIsNone(result['delta_hartree'])

    def test_completed_jacobian_samples_keep_prepared_group_coordinates(self):
        ordinary, raw = fixture(); runner = self.construct(ordinary,maximum_evaluations=6)
        result = runner.run(maximum_iterations=1)
        fd = [r for r in result['prepared_evaluation_ledger'] if r['phase']=='FD_SAMPLE']
        self.assertEqual(len(fd),2)
        self.assertTrue(all({'jacobian_group','chart','fd_sample','snapshot_id','local_rotation_coordinates'}<=r.keys() for r in fd))
        self.assertEqual([r['fd_sample'] for r in fd],[1,2])
        self.assertEqual(result['phase_mapping_status'],'COMPLETE')
        self.assertEqual(result['global_evaluation_count'],len(raw.calls))


if __name__=='__main__':unittest.main()
