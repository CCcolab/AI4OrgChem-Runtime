"""Single-start implementation scope, budget declarations and old-byte proof."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from runtime.user_molecule import occupied_space_root_contract as execution
from test_user_molecule_occupied_space_response_contract import ordinary_origin_fixture


def contract_fixture():
    value = execution.minimal_template(ordinary_origin_fixture())
    value.update(runtime_test_commit='ab'*20, batch_id='root-candidate-test-new',
        source_manifest_sha256='ac'*32, prior_proposal_sha256='ad'*32,
        source_file_sha256={name: 'ae'*32 for name in execution.REQUIRED_SOURCE_FILES})
    return value


class OccupiedSpaceRootContractTests(unittest.TestCase):
    def setUp(self): self.value = contract_fixture()

    def refuse(self, mutation):
        value = copy.deepcopy(self.value); mutation(value)
        with self.assertRaises(execution.ExecutionContractError): execution.validate_execution_contract(value)

    def test_template_is_implementation_only_and_never_reserves_scientific_allowance(self):
        before = copy.deepcopy(self.value)
        self.assertIs(execution.validate_execution_contract(self.value), self.value)
        self.assertEqual(self.value, before)
        self.assertIs(self.value['scientific_execution_authorized'], False)
        self.assertIs(self.value['scientific_budget_reserved'], False)
        self.assertEqual(self.value['future_live_execution'], 'NOT_AUTHORIZED_IN_THIS_CONTRACT_VERSION')

    def test_this_user_message_cannot_be_reinterpreted_as_live_root_authorization(self):
        for key in ('scientific_execution_authorized', 'scientific_budget_reserved', 'production_activation',
                    'scientific_approval', 'method_approval', 'external_review_required', 'Compute'):
            for bad in (True, 0): self.refuse(lambda value: value.__setitem__(key, bad))
        self.refuse(lambda value: value.__setitem__('authorization_scope', 'SCIENCE_APPROVED'))
        self.refuse(lambda value: value['authorization_basis'].__setitem__('source', 'DOCUMENT'))
        self.refuse(lambda value: value['authorization_basis'].__setitem__('message', '请继续'))

    def test_distinct_root_schema_policy_and_one_start_one_path_cannot_expand_or_relabel_v2(self):
        self.refuse(lambda value: value.__setitem__('schema_version', execution.retained.SCHEMA))
        self.refuse(lambda value: value.__setitem__('initialization_policy', 'MASKED_METRIC_OCCUPIED_SUBSPACE_SEED_V2'))
        self.refuse(lambda value: value['paths'].append('production_copy'))
        self.refuse(lambda value: value['path_callback_limits'].__setitem__('production_copy', 201))
        self.refuse(lambda value: value['initial_density'].__setitem__('seed_index', 1))
        self.refuse(lambda value: value['initial_density'].__setitem__('angle_rad', .1))

    def test_all_fixed_root_solver_parameters_and_explicit_return_semantics_are_frozen(self):
        for key, expected in execution.SOLVER_PARAMETERS.items():
            if type(expected) is bool: bad = not expected
            elif type(expected) in (int, float): bad = expected+1
            else: bad = 'OTHER_RETURN_OR_DERIVATIVE_POLICY'
            self.refuse(lambda value: value['solver_parameters'].__setitem__(key, bad))
        self.refuse(lambda value: value['solver_parameters'].__setitem__('maximum_evaluations', 201.))

    def test_201_and_300_second_bounds_are_proposed_exact_values_with_cleanup_and_no_refill(self):
        for key, expected in execution.PROCESS_CONTRACT.items():
            bad = not expected if type(expected) is bool else expected+1 if type(expected) is int else 'APPROVED_RESOURCE'
            self.refuse(lambda value: value['process_contract'].__setitem__(key, bad))
        self.assertEqual(self.value['process_contract']['stop_deadline_seconds']+
                         self.value['process_contract']['cleanup_headroom_seconds'], 300)
        self.refuse(lambda value: value['path_callback_limits'].__setitem__('independent_reference', 202))

    def test_old_history_F_is_never_used_as_current_initial_or_tail_of_new_solve(self):
        self.refuse(lambda value: value['initial_density'].__setitem__('CURRENT_INITIAL_F_required_from_new_budget', False))
        self.refuse(lambda value: value['initial_density'].__setitem__('old_F_or_energy_reused_as_new', True))
        self.refuse(lambda value: value['parent_evidence'].__setitem__('scope', 'INITIAL_F_ALREADY_EVALUATED_FOR_NEW_ROOT'))
        self.refuse(lambda value: value['parent_evidence'].__setitem__('qualified_endpoint', True))
        self.assertEqual(self.value['parent_evidence']['old_budgets'], '12_9_603_CLOSED_NOT_REOPENABLE')

    def test_all_original_final_array_comparison_and_cached_source_identities_are_unchanged(self):
        for section in ('final_thresholds', 'array_admission_thresholds'):
            for key in self.value[section]: self.refuse(lambda value: value[section].__setitem__(key, 1.))
        self.refuse(lambda value: value['ordinary_origin']['array_identities'].pop('mo_coefficients'))
        self.refuse(lambda value: value['expected_dependencies'].__setitem__('scipy', 'latest'))
        self.refuse(lambda value: value.__setitem__('science_commit', 'short'))
        self.refuse(lambda value: value['comparisons']['T05_same_density'].__setitem__('matrix_max_abs', 1e-6))

    def test_profile_raw_and_canonical_are_separate_and_fake_legacy_alias_is_refused(self):
        self.refuse(lambda value: value.__setitem__('profile_sha256', execution.retained.PROFILE_CANONICAL_SHA256))
        self.refuse(lambda value: value.__setitem__('profile_canonical_sha256', execution.retained.PROFILE_EXECUTED_RAW_SHA256))

    def test_all_critical_new_and_retained_source_hashes_paths_commits_are_required(self):
        for name in execution.REQUIRED_SOURCE_FILES: self.refuse(lambda value: value['source_file_sha256'].pop(name))
        for name in ('../outside.py', './x.py', '/root/x.py', 'a//b.py', 'C:/x.py', 'a\\b.py'):
            self.refuse(lambda value: value['source_file_sha256'].__setitem__(name, 'ab'*32))
        self.refuse(lambda value: value.__setitem__('runtime_test_commit', 'short'))
        self.refuse(lambda value: value.__setitem__('batch_id', '../reset-old-budget'))
        self.refuse(lambda value: value.__setitem__('extra', float('nan')))

    def test_execution_identity_exposes_inert_root_scope_and_selected_D_not_parent_four_D_allowance(self):
        identity = execution.execution_identity(self.value, 'af'*32)
        self.assertIs(identity['scientific_execution_authorized'], False)
        self.assertIs(identity['scientific_budget_reserved'], False)
        self.assertEqual(identity['mode'], execution.EXECUTION_KIND)
        self.assertEqual(identity['initial_density_id'], execution.INITIAL_DENSITY_ID)
        self.assertEqual(identity['path_id'], 'independent_reference')
        self.assertNotIn('seed_density_ids', identity)
        json.dumps(identity, allow_nan=False)
        with self.assertRaises(execution.ExecutionContractError): execution.execution_identity(self.value, 'short')

    def test_only_explicit_fake_journal_can_enter_this_candidate_version(self):
        self.assertTrue(execution.validate_root_journal_identity({'mode': 'ENGINEERING_FAKE'},
            initial_density_id=execution.INITIAL_DENSITY_ID, execution_kind='ENGINEERING_FAKE'))
        for kind in (execution.EXECUTION_KIND, execution.retained.EXECUTION_KIND, 'PREPARED_MOLECULAR_DIAGNOSTIC'):
            with self.assertRaises(execution.ExecutionContractError):
                execution.validate_root_journal_identity({'mode': kind, 'scientific_execution_authorized': True},
                    initial_density_id=execution.INITIAL_DENSITY_ID, execution_kind=kind)
        for extra in ({'scientific_execution_authorized': True}, {'execution_kind': execution.EXECUTION_KIND}, {'initial_density_id': 'ff'*32}):
            with self.assertRaises(execution.ExecutionContractError):
                execution.validate_root_journal_identity({'mode': 'ENGINEERING_FAKE', **extra},
                    initial_density_id=execution.INITIAL_DENSITY_ID, execution_kind='ENGINEERING_FAKE')

    def test_strict_json_load_uses_actual_bytes_and_refuses_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'contract.json'; path.write_text(json.dumps(self.value), encoding='utf-8')
            self.assertEqual(execution.load_execution_contract(path), self.value)
            path.write_text('{"schema_version":"a","schema_version":"b"}', encoding='utf-8')
            with self.assertRaises(ValueError): execution.load_execution_contract(path)


class OccupiedSpaceRootSavedInputTests(unittest.TestCase):
    def setUp(self):
        declared = os.environ.get('AI4ORGCHEM_OCCUPIED_ROOT_INPUT_DIR')
        if declared:
            source = seed = evidence = Path(declared)
            mdr_path, history_path = evidence/'MDR-007.json', evidence/'parent-response-result.json'
        else:
            workspace = Path(__file__).resolve().parents[4]
            prior = workspace/'ai4orgchem-runtime-deliveries'/'20261007-user-molecule-occupied-space-response'
            source = seed = prior/'seed-input'
            mdr_path = Path(__file__).resolve().parents[1]/'validation/user-molecule/method-decisions/mdr-007/record.json'
            history_path = prior/'response-a1/output/response-result.json'
        self.inputs = dict(source_bytes=(source/'SOURCE.json').read_bytes(),
            seed_record_bytes=(seed/'prepared-seed-family.json').read_bytes(),
            seed_arrays_bytes=(seed/'prepared-seed-family.npz').read_bytes(),
            source_arrays_bytes=(source/'source-arrays.npz').read_bytes(),
            history_record_bytes=history_path.read_bytes(), mdr_bytes=mdr_path.read_bytes())

    def test_original_six_files_bind_selected_D_and_history_without_new_root_F_or_allowance(self):
        result = execution.validate_input_binding(contract_fixture(), **self.inputs)
        self.assertEqual(result['prepared_members_verified'], 10)
        self.assertEqual(result['source_members_verified'], 6)
        self.assertEqual(result['selected_initial_density_id'], execution.INITIAL_DENSITY_ID)
        self.assertEqual(result['historical_operator_id'], execution.HISTORICAL_OPERATOR_ID)
        self.assertEqual(result['future_CURRENT_INITIAL_F'], 'REQUIRED_FRESH_CALLBACK_NOT_EXECUTED')
        self.assertEqual(result['new_true_F_calls'], 0)
        self.assertIsNone(result['new_root_budget'])

    def test_any_saved_file_tampering_or_missing_historical_evidence_refuses(self):
        for key, raw in self.inputs.items():
            changed = dict(self.inputs, **{key: raw[:-1]+b'x'})
            with self.subTest(key=key), self.assertRaises(execution.ExecutionContractError):
                execution.validate_input_binding(contract_fixture(), **changed)
        for key in ('history_record_bytes', 'mdr_bytes'):
            changed = dict(self.inputs, **{key: None})
            with self.assertRaises(execution.ExecutionContractError): execution.validate_input_binding(contract_fixture(), **changed)


if __name__ == '__main__': unittest.main()
