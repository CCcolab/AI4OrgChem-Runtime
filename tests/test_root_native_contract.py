"""Stdlib declaration proofs; future grants here are synthetic, never real authorization."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from runtime.user_molecule import occupied_space_root_native_contract as native


def parent_fixture():
    old = native.parent_contract
    arrays = {name: {'shape': shape, 'dtype': '<f8', 'order': 'C', 'sha256': digest}
              for name, (shape, digest) in old.retained.immutable.FROZEN_ARRAYS.items()}
    origin = {'kind': 'REUSE_PRIOR_FULL_INDEPENDENT_ORDINARY_REFERENCE',
        'record_file': 'ordinary-reference.json', 'arrays_file': 'ordinary-reference.npz',
        'record': {'size_bytes':11741, 'sha256':'b0a9fd8a2487d725668823b75966176e98eb25551f40b9f177b485141ecb9663'},
        'arrays': {'size_bytes':1728678, 'sha256':'2a0318c42ee47001e2774ea6b4fec8317b1887c744a2720e71033a75b18f6051'},
        'common_density_identity':copy.deepcopy(arrays['density']), 'array_identities':arrays,
        'nuclear_repulsion_hartree':33.23272494899829}
    value = old.minimal_template(origin)
    value.update(runtime_test_commit='ab'*20, batch_id='synthetic-parent-no-scientific-permission',
        source_manifest_sha256='ac'*32, prior_proposal_sha256='ad'*32,
        source_file_sha256={name:'ae'*32 for name in old.REQUIRED_SOURCE_FILES})
    return value


def contract_fixture():
    value = native.minimal_template(parent_fixture())
    value.update(runtime_test_commit='bc'*20,
        source_file_sha256={name:'bd'*32 for name in native.REQUIRED_SOURCE_FILES})
    value['contract_family_sha256'] = native.contract_family_sha256(value)
    return value


def synthetic_future_grant(value):
    """Test-local shape only; not saved, offered as a real grant or used by an engine."""
    return {'schema_version':native.GRANT_SCHEMA, 'source':'DIRECT_USER_MESSAGE',
        'intent':'EXECUTE_ONE_SPECIFIED_SOURCE_NATIVE_ROOT_DIAGNOSTIC', 'scope':native.EXECUTION_SCOPE,
        'contract_family_sha256':value['contract_family_sha256'], 'local_cli_execute_requested':True,
        'maximum_scientific_processes':1, 'allowed_path':native.PATH_ID,
        'allowed_initial_density_id':native.INITIAL_DENSITY_ID,
        'max_true_F_or_NR_calls':201, 'max_wall_seconds_through_cleanup':300,
        'grant_id':'TEST_FIXTURE_ONLY_NOT_REAL_AUTHORIZATION',
        'direct_user_message':'结构测试专用：允许执行一次 SOURCE_NATIVE_DIAGNOSTIC，上限201次F/NR和300秒。'}


def future_fixture():
    value = contract_fixture(); grant = synthetic_future_grant(value)
    value.update(scientific_execution_authorized=True, local_cli_execute_requested=True,
                 authorization_scope=native.EXECUTION_SCOPE, execution_grant=grant)
    return value, copy.deepcopy(grant)


class RootNativeContractTests(unittest.TestCase):
    def setUp(self): self.value = contract_fixture()

    def refuse(self, mutation):
        value = copy.deepcopy(self.value); mutation(value)
        with self.assertRaises(native.ExecutionContractError): native.validate_execution_contract(value)

    def test_template_keeps_original_false_parent_and_no_grant_no_reservation_no_compute(self):
        before = copy.deepcopy(self.value)
        self.assertIs(native.validate_execution_contract(self.value), self.value)
        self.assertEqual(self.value, before)
        self.assertEqual(self.value['parent_preparation_contract'], parent_fixture())
        for key in ('scientific_execution_authorized','scientific_budget_reserved','Compute','method_approval'):
            self.assertIs(self.value[key], False)
        self.assertIsNone(self.value['execution_grant']); self.assertIsNone(self.value['budget_reservation'])

    def test_old_contract_old_schema_and_old_parent_true_flip_are_refused(self):
        with self.assertRaises(native.ExecutionContractError): native.validate_execution_contract(parent_fixture())
        self.refuse(lambda value:value.__setitem__('schema_version', native.parent_contract.SCHEMA))
        self.refuse(lambda value:value['parent_preparation_contract'].__setitem__('scientific_execution_authorized',True))
        self.refuse(lambda value:value.__setitem__('native_mode',native.parent_contract.EXECUTION_KIND))

    def test_bare_true_flip_or_cli_flag_cannot_promote_inactive_template(self):
        self.refuse(lambda value:value.__setitem__('scientific_execution_authorized',True))
        with self.assertRaises(native.ExecutionContractError):
            native.validate_execution_contract(self.value, local_cli_execute_requested=True)
        with self.assertRaises(native.ExecutionContractError):
            native.validate_execution_contract(self.value, explicit_grant=synthetic_future_grant(self.value))

    def test_future_declaration_requires_independently_passed_matching_grant_and_cli_true(self):
        value, grant = future_fixture()
        for options in ({}, {'explicit_grant':grant}, {'local_cli_execute_requested':True}):
            with self.assertRaises(native.ExecutionContractError): native.validate_execution_contract(value, **options)
        before = copy.deepcopy(value)
        self.assertIs(native.validate_execution_contract(value, explicit_grant=grant, local_cli_execute_requested=True), value)
        self.assertEqual(value, before)
        self.assertIs(value['scientific_budget_reserved'], False)

    def test_general_continue_wrong_authority_family_budget_or_scope_is_not_a_grant(self):
        for key, wrong in (('direct_user_message','请继续下一步'), ('source','DOCUMENT'),
                           ('contract_family_sha256','ff'*32), ('max_true_F_or_NR_calls',202),
                           ('max_wall_seconds_through_cleanup',301), ('scope','ARBITRARY_MOLECULE_COMPUTE')):
            value, grant = future_fixture(); value['execution_grant'][key] = wrong
            with self.assertRaises(native.ExecutionContractError):
                native.validate_execution_contract(value, explicit_grant=value['execution_grant'], local_cli_execute_requested=True)

    def test_exact_booleans_and_no_reservation_or_approval_claim_are_enforced(self):
        for key in ('scientific_execution_authorized','local_cli_execute_requested','scientific_budget_reserved',
                    'production_activation','scientific_approval','method_approval','external_review_required','Compute'):
            self.refuse(lambda value:value.__setitem__(key,0))
        self.refuse(lambda value:value.__setitem__('budget_reservation',{'reserved':True}))
        self.refuse(lambda value:value.__setitem__('external_review_status','REQUIRED'))

    def test_single_initial_path_solver_quota_wall_memory_and_tail_policies_are_exact(self):
        self.refuse(lambda value:value.__setitem__('single_path','production_copy'))
        for section in ('solver_parameters','process_contract','family_policy','callback_policy'):
            for key, original in self.value[section].items():
                bad = not original if type(original) is bool else original+1 if type(original) in (int,float) else 'OTHER'
                self.refuse(lambda value:value[section].__setitem__(key,bad))
        self.refuse(lambda value:value['initial_density'].__setitem__('seed_index',1))
        self.refuse(lambda value:value['initial_density'].__setitem__('angle_rad',.1))

    def test_old_science_cache_threshold_and_raw_canonical_profile_bindings_stay_frozen(self):
        for section in ('final_thresholds','array_admission_thresholds'):
            key = next(iter(self.value['parent_preparation_contract'][section]))
            self.refuse(lambda value:value['parent_preparation_contract'][section].__setitem__(key,1.))
        self.refuse(lambda value:value['parent_preparation_contract'].__setitem__('science_commit','1'*40))
        self.refuse(lambda value:value['parent_preparation_contract'].__setitem__('profile_sha256',
                    native.parent_contract.retained.PROFILE_CANONICAL_SHA256))
        self.refuse(lambda value:value['parent_preparation_contract']['ordinary_origin']['array_identities'].pop('mo_coefficients'))

    def test_new_and_retained_code_digests_are_complete_strict_relative_and_distinct_from_parent(self):
        self.assertNotEqual(self.value['runtime_test_commit'], self.value['parent_preparation_contract']['runtime_test_commit'])
        for name in native.REQUIRED_SOURCE_FILES: self.refuse(lambda value:value['source_file_sha256'].pop(name))
        for name in ('../outside.py','/root/file.py','a//b.py','C:/file.py','a\\b.py'):
            self.refuse(lambda value:value['source_file_sha256'].__setitem__(name,'ef'*32))
        self.refuse(lambda value:value.__setitem__('runtime_test_commit','short'))

    def test_source_lock_contains_candidate_local_import_and_dynamic_helper_closure(self):
        """Inspect local source only; neither import helpers nor traverse third-party code."""
        root = Path(__file__).resolve().parents[1]
        seen, pending = set(), list(native.REQUIRED_SOURCE_FILES)
        def include(name):
            if (root/name).is_file() and name not in seen:
                pending.append(name)
        def module(name):
            path = name.replace('.', '/')+'.py'
            if not (root/path).is_file():
                return
            include(path)
            for count in range(1, len(path.split('/'))):
                include('/'.join(path.split('/')[:count])+'/__init__.py')
        while pending:
            name = pending.pop()
            if name in seen:
                continue
            seen.add(name)
            tree = ast.parse((root/name).read_text(encoding='utf-8-sig'))
            package = name[:-3].replace('/', '.')
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    base = ('.'.join(package.split('.')[:-node.level]+([node.module] if node.module else []))
                            if node.level else node.module or '')
                    module(base)
                    for alias in node.names:
                        module(base+'.'+alias.name)
                elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
                      and node.value.endswith('.py') and '/' in node.value):
                    include(node.value)
        self.assertEqual(seen-native.REQUIRED_SOURCE_FILES, set(),
                         'Unbound candidate local import or dynamic script dependency')

    def test_family_does_not_change_with_batch_output_or_grant_but_binds_new_code(self):
        changed = copy.deepcopy(self.value); changed['batch_id'] = 'another-output-does-not-authorize-retry'
        self.assertEqual(native.contract_family_sha256(changed), self.value['contract_family_sha256'])
        native.validate_execution_contract(changed)
        future, _ = future_fixture()
        self.assertEqual(native.contract_family_sha256(future), self.value['contract_family_sha256'])
        changed['runtime_test_commit'] = 'de'*20
        self.assertNotEqual(native.contract_family_sha256(changed), self.value['contract_family_sha256'])
        with self.assertRaises(native.ExecutionContractError): native.validate_execution_contract(changed)

    def test_unresolved_code_placeholders_cannot_receive_future_execute_context(self):
        value = native.minimal_template(parent_fixture())
        grant = synthetic_future_grant(value)
        value.update(scientific_execution_authorized=True,local_cli_execute_requested=True,
                     execution_grant=grant,authorization_scope=native.EXECUTION_SCOPE)
        with self.assertRaises(native.ExecutionContractError):
            native.validate_execution_contract(value,explicit_grant=grant,local_cli_execute_requested=True)

    def test_raw_parent_bytes_are_separate_from_canonical_content_and_old_parent_is_not_relabelled(self):
        parent = parent_fixture(); raw = (json.dumps(parent,indent=4)+'\n').encode()
        with tempfile.TemporaryDirectory() as directory, patch.object(native,'PARENT_RAW_SHA256',hashlib.sha256(raw).hexdigest()):
            value = native.minimal_template(parent); path = Path(directory)/'contract.json'
            path.write_bytes(json.dumps(value).encode())
            self.assertEqual(native.load_execution_contract(path,parent_preparation_contract_bytes=raw),value)
            self.assertNotEqual(native.canonical_sha(parent), value['parent_preparation_contract_sha256'])
            compact = json.dumps(parent,separators=(',',':')).encode()
            with self.assertRaises(native.ExecutionContractError):
                native.load_execution_contract(path,parent_preparation_contract_bytes=compact)
            self.assertIs(parent['scientific_execution_authorized'],False)

    def test_actual_parent_tamper_or_embedded_content_mismatch_is_refused(self):
        parent = parent_fixture(); raw = json.dumps(parent,indent=4).encode()
        with patch.object(native,'PARENT_RAW_SHA256',hashlib.sha256(raw).hexdigest()):
            value = native.minimal_template(parent)
            with self.assertRaises(native.ExecutionContractError): native._bind_parent_bytes(value,raw+b' ')
            value['parent_preparation_contract']['runtime_test_commit'] = 'ef'*20
            value['parent_preparation_contract_canonical_sha256'] = native.canonical_sha(value['parent_preparation_contract'])
            with self.assertRaises(native.ExecutionContractError): native._bind_parent_bytes(value,raw)

    def test_all_six_input_bytes_are_mandatory_before_old_validation_delegation(self):
        parent = parent_fixture(); raw = json.dumps(parent,indent=4).encode()
        with patch.object(native,'PARENT_RAW_SHA256',hashlib.sha256(raw).hexdigest()):
            value = native.minimal_template(parent)
            with patch.object(native.parent_contract,'validate_input_binding') as delegated:
                with self.assertRaises(native.ExecutionContractError):
                    native.validate_input_binding(value,b'source',b'seed',b'npz',
                        parent_preparation_contract_bytes=raw,source_arrays_bytes=None,
                        history_record_bytes=b'history',mdr_bytes=b'mdr')
                delegated.assert_not_called()

    def test_input_delegation_preserves_original_false_parent_and_the_six_requested_byte_arguments(self):
        # This test checks routing only, not the retained six real input files.
        parent = parent_fixture(); raw = json.dumps(parent,indent=4).encode()
        with patch.object(native,'PARENT_RAW_SHA256',hashlib.sha256(raw).hexdigest()):
            value = native.minimal_template(parent)
            with patch.object(native.parent_contract,'validate_input_binding',
                return_value={'status':'TEST_DOUBLE_DELEGATION_ONLY_NOT_ACTUAL_INPUT_ACCEPTANCE'}) as delegated:
                result = native.validate_input_binding(value,b'source',b'seed',b'npz',
                    parent_preparation_contract_bytes=raw,source_arrays_bytes=b'source-npz',
                    history_record_bytes=b'history',mdr_bytes=b'mdr')
                delegated.assert_called_once_with(parent,b'source',b'seed',b'npz',
                    source_arrays_bytes=b'source-npz',history_record_bytes=b'history',mdr_bytes=b'mdr')
                self.assertIs(result['root_or_method_approval'],False)
                self.assertIs(result['scientific_budget_reserved'],False)

    def test_false_identity_cannot_open_native_journal_even_with_a_native_mode_label(self):
        identity = native.execution_identity(self.value,'ef'*32)
        self.assertEqual(identity['mode'],native.NATIVE_MODE)
        self.assertIs(identity['scientific_execution_authorized'],False)
        with self.assertRaises(native.ExecutionContractError):
            native.validate_native_journal_identity(identity,execution_kind=native.NATIVE_MODE,
                initial_density_id=native.INITIAL_DENSITY_ID,contract=self.value)

    def test_simulated_journal_never_admits_true_auth_grant_or_old_execution_kinds(self):
        identity = {'mode':native.SIMULATED_MODE,'execution_kind':native.SIMULATED_MODE,
                    'scientific_execution_authorized':False}
        receipt = native.validate_native_journal_identity(identity,execution_kind=native.SIMULATED_MODE,initial_density_id='aa'*32)
        self.assertIs(receipt['scientific_execution_authorized'],False)
        for key, bad in (('scientific_execution_authorized',True),('scientific_execution_authorized',0),
                         ('execution_grant',{'grant':'fake-real'}),('scientific_budget_reserved',True),
                         ('local_cli_execute_requested',True),('mode',native.parent_contract.EXECUTION_KIND)):
            changed = copy.deepcopy(identity); changed[key] = bad
            with self.assertRaises(native.ExecutionContractError):
                native.validate_native_journal_identity(changed,execution_kind=native.SIMULATED_MODE,initial_density_id='aa'*32)

    def test_future_journal_identity_requires_captured_contract_grant_and_complete_matching_fields(self):
        value, grant = future_fixture()
        options = {'explicit_grant':grant,'local_cli_execute_requested':True}
        identity = native.execution_identity(value,'ef'*32,**options)
        receipt = native.validate_native_journal_identity(identity,execution_kind=native.NATIVE_MODE,
            initial_density_id=native.INITIAL_DENSITY_ID,contract=value,**options)
        self.assertEqual(receipt['contract_family_sha256'],value['contract_family_sha256'])
        for key, bad in (('batch_id','foreign'),('profile_sha256','ee'*32),('total_limit',202)):
            changed = copy.deepcopy(identity); changed[key] = bad
            with self.assertRaises(native.ExecutionContractError):
                native.validate_native_journal_identity(changed,execution_kind=native.NATIVE_MODE,
                    initial_density_id=native.INITIAL_DENSITY_ID,contract=value,**options)


if __name__=='__main__': unittest.main()
