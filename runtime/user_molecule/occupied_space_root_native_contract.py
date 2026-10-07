"""Independent, default-gated source-native root execution declarations.

The retained parent is an unchanged false preparation contract. Caller-supplied
future grants are scope/identity declarations, not publisher authentication;
this module reserves no budget, launches nothing and imports no science library.
"""
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

from . import occupied_space_root_contract as parent_contract
from .input import strict_json


SCHEMA = 'occupied-space-root-native-execution-contract-v1'
NATIVE_MODE = 'SOURCE_NATIVE_DIAGNOSTIC'
SIMULATED_MODE = 'ENGINEERING_SIMULATED_NATIVE'
PATH_ID = parent_contract.PATH_ID
INITIAL_DENSITY_ID = parent_contract.INITIAL_DENSITY_ID
PARENT_RAW_SHA256 = '9cb736eeda4aa2bde34e2fd80e750bc94a467741876d93472fb2065c6288c9fb'
EXECUTION_SCOPE = 'ONE_SOURCE_NATIVE_ROOT_DIAGNOSTIC_ONLY_NOT_COMPUTE_OR_METHOD_APPROVAL'
PREPARATION_SCOPE = 'IMPLEMENTATION_AND_ZERO_F_PREPARATION_ONLY'
GRANT_SCHEMA = 'occupied-space-root-native-direct-grant-v1'
REQUIRED_SOURCE_FILES = parent_contract.REQUIRED_SOURCE_FILES | frozenset((
    # Close only this candidate's local import/dynamic-helper dependencies.
    # Third-party implementations remain pinned by distributions and image ID.
    'reference/__init__.py',
    'reference/ordinary_molecule.py',
    'reference/residual_seed_v2.py',
    'reference/seed_v2.py',
    'reference/user_molecule_v2.py',
    'runtime/__init__.py',
    'runtime/distribution.py',
    'runtime/resources.py',
    'runtime/user_molecule/__init__.py',
    'runtime/user_molecule/input.py',
    'runtime/user_molecule/preflight.py',
    'runtime/user_molecule/records.py',
    'runtime/user_molecule/research.py',
    'runtime/user_molecule/residual_candidate.py',
    'runtime/user_molecule/residual_execution_contract.py',
    'runtime/user_molecule/residual_seed_execution_contract.py',
    'runtime/user_molecule/residual_seed_v2.py',
    'runtime/user_molecule/seed_v2.py',
    'runtime/user_molecule/occupied_space_root_native_contract.py',
    'runtime/user_molecule/root_native_accounting.py',
    'runtime/user_molecule/root_native_binding.py',
    'reference/occupied_space_root_native_candidate.py',
    'scripts/ci-guard-budget-recording.py',
    'scripts/ci-guard-root-native.py',
    'scripts/ci-guard-seed-v2.py',
    'scripts/diagnose-user-molecule-occupation-response-worker.py',
    'scripts/diagnose-user-molecule-seed-v2-worker.py',
    'scripts/diagnose-user-molecule-seed-v2.py',
    'scripts/diagnose-user-molecule-root-native.py',
    'scripts/diagnose-user-molecule-root-native-worker.py'))
SOLVER_PARAMETERS = copy.deepcopy(parent_contract.SOLVER_PARAMETERS)
PROCESS_CONTRACT = copy.deepcopy(parent_contract.PROCESS_CONTRACT)
PROCESS_CONTRACT['scope'] = 'CANDIDATE_HARD_LIMITS_NOT_AUTOMATIC_AUTHORIZATION_OR_RESERVATION'
FAMILY_POLICY = {'policy_id': 'ONE_START_ONE_PATH_SOURCE_NATIVE_ROOT_V1',
    'maximum_scientific_processes': 1, 'automatic_retry': False,
    'refund_failed_slots': False, 'refill_or_tail_after_budget_refusal': False,
    'identity_excludes_batch_and_output_location': True,
    'persistent_family_attempt_registry_required': True,
    'registry_scope': 'FIXED_DIAGNOSTIC_PARENT_NOT_EACH_OUTPUT_DIRECTORY',
    'old_budgets': '12_9_603_CLOSED_NOT_REOPENABLE'}
CALLBACK_POLICY = {'initial': 'CURRENT_INITIAL', 'objective': 'OPTIMIZER_BASE',
    'finite_difference': 'FD_SAMPLE', 'returned_tail': 'FINAL_RETURNED_DENSITY',
    'mapped_tail': 'FINAL_RAW_AUFBAU_DENSITY_RECHECK',
    'charge_before_callback': True, 'source_NR_separately_observed': True,
    'mapped_tail_requires_original_returned_gate': True,
    'no_historical_F_as_current_or_tail': True}
ExecutionContractError = parent_contract.ExecutionContractError
canonical_sha = parent_contract.canonical_sha


def _fail(message): raise ExecutionContractError('Root-native contract: '+message)


def _same(actual, expected, label):
    parent_contract._equal(actual, expected, label)


def _sha(value, label, length=64):
    parent_contract._sha(value, label, length)


def contract_family_sha256(contract):
    """One candidate family; changing a batch/output does not create permission."""
    parent = contract['parent_preparation_contract']
    return canonical_sha({'schema_version': SCHEMA, 'native_mode': NATIVE_MODE,
        'parent_preparation_contract_sha256': contract['parent_preparation_contract_sha256'],
        'parent_preparation_contract_canonical_sha256': canonical_sha(parent),
        'runtime_test_commit': contract['runtime_test_commit'],
        'source_file_sha256': contract['source_file_sha256'],
        'single_path': contract['single_path'], 'initial_density': contract['initial_density'],
        'solver_parameters': contract['solver_parameters'], 'process_contract': contract['process_contract'],
        'callback_policy': contract['callback_policy'], 'family_policy': contract['family_policy']})


def minimal_template(parent):
    """A false candidate declaration; no grant or scientific reservation."""
    parent_contract.validate_execution_contract(parent)
    value = {'schema_version': SCHEMA, 'native_mode': NATIVE_MODE,
        'parent_preparation_contract': copy.deepcopy(parent),
        'parent_preparation_contract_sha256': PARENT_RAW_SHA256,
        'parent_preparation_contract_canonical_sha256': canonical_sha(parent),
        'runtime_test_commit': '0'*40,
        'source_file_sha256': {name: '0'*64 for name in sorted(REQUIRED_SOURCE_FILES)},
        'batch_id': 'root-native-template-not-reserved', 'single_path': PATH_ID,
        'initial_density': copy.deepcopy(parent['initial_density']),
        'solver_parameters': copy.deepcopy(SOLVER_PARAMETERS),
        'process_contract': copy.deepcopy(PROCESS_CONTRACT),
        'family_policy': copy.deepcopy(FAMILY_POLICY), 'callback_policy': copy.deepcopy(CALLBACK_POLICY),
        'authorization_scope': PREPARATION_SCOPE, 'scientific_execution_authorized': False,
        'local_cli_execute_requested': False, 'execution_grant': None,
        'scientific_budget_reserved': False, 'budget_reservation': None,
        'production_activation': False, 'scientific_approval': False, 'method_approval': False,
        'external_review_required': False, 'external_review_status': 'CANCELLED_BY_USER',
        'Compute': False, 'research_delta_hartree': None,
        'identity_and_grant_are_not_publisher_authentication': True}
    value['contract_family_sha256'] = contract_family_sha256(value)
    return value


def _validate_grant(grant, family):
    if not isinstance(grant, dict): _fail('explicit future direct-user grant required')
    expected = {'schema_version': GRANT_SCHEMA, 'source': 'DIRECT_USER_MESSAGE',
        'intent': 'EXECUTE_ONE_SPECIFIED_SOURCE_NATIVE_ROOT_DIAGNOSTIC',
        'scope': EXECUTION_SCOPE, 'contract_family_sha256': family,
        'local_cli_execute_requested': True, 'maximum_scientific_processes': 1,
        'allowed_path': PATH_ID, 'allowed_initial_density_id': INITIAL_DENSITY_ID,
        'max_true_F_or_NR_calls': 201, 'max_wall_seconds_through_cleanup': 300}
    if set(grant) != set(expected) | {'grant_id', 'direct_user_message'}: _fail('exact grant fields required')
    for key, value in expected.items(): _same(grant[key], value, 'grant '+key)
    if not isinstance(grant['grant_id'], str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', grant['grant_id']) is None:
        _fail('bounded explicit grant ID required')
    message = grant['direct_user_message']
    if not isinstance(message, str) or not 1 <= len(message) <= 4096: _fail('explicit bounded direct-user message required')
    lower = message.lower()
    if (not any(token in lower for token in ('允许执行', '授权执行', 'authorize execution', 'authorise execution'))
            or not any(token in lower for token in ('source_native_diagnostic', 'native根诊断', '原生根诊断'))
            or '201' not in message or '300' not in message):
        _fail('general continue is not an explicit one-root 201-call/300-second execution grant')


def validate_execution_contract(contract, *, explicit_grant=None, local_cli_execute_requested=False):
    """Validate declarations; True additionally needs explicit caller context.

Metadata validation alone never observes native F, reserves quota, authenticates
the user, or substitutes for source-byte/context binding and family admission.
"""
    try:
        if not isinstance(contract, dict): _fail('mapping required')
        expected = minimal_template(contract['parent_preparation_contract'])
        if set(contract) != set(expected): _fail('exact new schema fields required; old contracts are not admitted')
        dynamic = {'runtime_test_commit', 'source_file_sha256', 'batch_id', 'contract_family_sha256',
                   'scientific_execution_authorized', 'local_cli_execute_requested', 'execution_grant', 'authorization_scope'}
        for key in set(expected)-dynamic: _same(contract[key], expected[key], key)
        _same(contract['parent_preparation_contract_sha256'], PARENT_RAW_SHA256, 'retained actual parent bytes SHA')
        _same(contract['parent_preparation_contract_canonical_sha256'], canonical_sha(contract['parent_preparation_contract']), 'parent parsed-content identity')
        _sha(contract['runtime_test_commit'], 'new runtime_test_commit', 40)
        sources = contract['source_file_sha256']
        if not isinstance(sources, dict) or not REQUIRED_SOURCE_FILES <= set(sources): _fail('all critical old/new source digests required')
        for path, digest in sources.items():
            if (not isinstance(path, str) or not path or ':' in path or '\\' in path or PurePosixPath(path).is_absolute()
                    or any(part in ('', '.', '..') for part in path.split('/'))): _fail('canonical relative source paths required')
            _sha(digest, 'source '+path)
        if not isinstance(contract['batch_id'], str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', contract['batch_id']) is None:
            _fail('bounded fresh batch ID required')
        family = contract_family_sha256(contract)
        _same(contract['contract_family_sha256'], family, 'contract family')
        for key in ('scientific_execution_authorized', 'local_cli_execute_requested'):
            if type(contract[key]) is not bool: _fail('exact boolean '+key+' required')
        if type(local_cli_execute_requested) is not bool: _fail('exact caller CLI boolean required')
        if contract['scientific_execution_authorized'] is False:
            _same(contract['authorization_scope'], PREPARATION_SCOPE, 'inactive scope')
            _same(contract['execution_grant'], None, 'inactive grant')
            _same(contract['local_cli_execute_requested'], False, 'inactive CLI request')
            if explicit_grant is not None or local_cli_execute_requested is not False:
                _fail('inactive contract cannot be promoted by caller flags')
        else:
            _same(contract['authorization_scope'], EXECUTION_SCOPE, 'future diagnostic scope')
            _same(contract['local_cli_execute_requested'], True, 'future CLI request')
            if explicit_grant is None or local_cli_execute_requested is not True:
                _fail('future native execution requires independent explicit caller grant and execute request')
            _validate_grant(contract['execution_grant'], family)
            _same(explicit_grant, contract['execution_grant'], 'caller grant binding')
            if contract['runtime_test_commit'] == '0'*40 or any(value == '0'*64 for value in sources.values()):
                _fail('future grant cannot execute unresolved source placeholders')
        json.dumps(contract, allow_nan=False)
        return contract
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        if isinstance(error, ExecutionContractError): raise
        raise ExecutionContractError('Incomplete root-native declaration: '+str(error)) from error


def _bind_parent_bytes(contract, raw):
    if type(raw) is not bytes or hashlib.sha256(raw).hexdigest() != PARENT_RAW_SHA256:
        _fail('actual original false-parent JSON bytes required; canonical re-encoding is not its raw SHA')
    parsed = parent_contract.validate_execution_contract(strict_json(raw))
    _same(parsed, contract['parent_preparation_contract'], 'actual false-parent parsed contract')
    _same(canonical_sha(parsed), contract['parent_preparation_contract_canonical_sha256'], 'actual parent content digest')
    return parsed


def load_execution_contract(path, *, parent_preparation_contract_bytes, explicit_grant=None, local_cli_execute_requested=False):
    value = validate_execution_contract(strict_json(Path(path).read_bytes()), explicit_grant=explicit_grant,
                                        local_cli_execute_requested=local_cli_execute_requested)
    _bind_parent_bytes(value, parent_preparation_contract_bytes)
    return value


def validate_input_binding(contract, source_bytes, seed_record_bytes, seed_arrays_bytes, *,
        parent_preparation_contract_bytes, source_arrays_bytes, history_record_bytes, mdr_bytes,
        explicit_grant=None, local_cli_execute_requested=False):
    validate_execution_contract(contract, explicit_grant=explicit_grant,
                                local_cli_execute_requested=local_cli_execute_requested)
    if any(type(raw) is not bytes for raw in (source_bytes, seed_record_bytes, seed_arrays_bytes,
            source_arrays_bytes, history_record_bytes, mdr_bytes)):
        _fail('all six retained input files must be actual bytes; partial bindings are refused')
    parent = _bind_parent_bytes(contract, parent_preparation_contract_bytes)
    result = parent_contract.validate_input_binding(parent, source_bytes, seed_record_bytes, seed_arrays_bytes,
        source_arrays_bytes=source_arrays_bytes, history_record_bytes=history_record_bytes, mdr_bytes=mdr_bytes)
    return {'status': 'PASS_RETAINED_NATIVE_ROOT_INPUT_BYTES_ONLY',
            'parent_preparation_contract_sha256': PARENT_RAW_SHA256,
            'parent_preparation_contract_canonical_sha256': canonical_sha(parent),
            'contract_family_sha256': contract['contract_family_sha256'], 'parent_binding': result,
            'source_arrays_required': True, 'actual_numpy_recipe': 'NOT_EXECUTED_FACTORY_MUST_VERIFY',
            'scientific_budget_reserved': False, 'budget_reservation': None,
            'root_or_method_approval': False}


def execution_identity(contract, contract_sha256, *, explicit_grant=None, local_cli_execute_requested=False):
    validate_execution_contract(contract, explicit_grant=explicit_grant,
                                local_cli_execute_requested=local_cli_execute_requested)
    _sha(contract_sha256, 'native execution contract SHA')
    parent = contract['parent_preparation_contract']
    origin, seed = parent['ordinary_origin'], parent['seed_binding']
    return {'mode': NATIVE_MODE, 'execution_kind': NATIVE_MODE,
        'scientific_execution_authorized': contract['scientific_execution_authorized'],
        'authorization_scope': contract['authorization_scope'],
        'local_cli_execute_requested': contract['local_cli_execute_requested'],
        'execution_grant': copy.deepcopy(contract['execution_grant']),
        'contract_family_sha256': contract['contract_family_sha256'], 'batch_id': contract['batch_id'],
        'execution_contract_sha256': contract_sha256,
        'parent_preparation_contract_sha256': PARENT_RAW_SHA256,
        'parent_preparation_contract_canonical_sha256': contract['parent_preparation_contract_canonical_sha256'],
        'runtime_test_commit': contract['runtime_test_commit'],
        'source_file_identity_sha256': canonical_sha(contract['source_file_sha256']),
        **{key: parent[key] for key in ('science_commit', 'science_baseline_commit', 'image_id',
            'image_build_runtime_commit', 'source_manifest_sha256', 'profile_sha256',
            'profile_canonical_sha256', 'profile_executed_raw_sha256', 'dependencies_sha256')},
        'geometry_sha256': parent['fixture']['xyz_sha256'], 'path_id': PATH_ID,
        'initial_density_id': INITIAL_DENSITY_ID, 'initial_seed_index': 2, 'initial_angle_rad': -.1,
        'path_limits': {PATH_ID: 201}, 'total_limit': 201,
        'ordinary_record_sha256': origin['record']['sha256'], 'ordinary_arrays_sha256': origin['arrays']['sha256'],
        'source_input_sha256': seed['source_record']['sha256'], 'source_arrays_sha256': seed['source_arrays']['sha256'],
        'seed_record_sha256': seed['seed_record']['sha256'], 'seed_arrays_sha256': seed['seed_arrays']['sha256'],
        'scientific_budget_reserved': False, 'budget_reservation': None,
        'native_execution_observed': 'NOT_PROVEN_BY_DECLARATION_OR_SLOT_COUNT'}


def validate_native_journal_identity(identity, *, execution_kind, initial_density_id,
        contract=None, explicit_grant=None, local_cli_execute_requested=False):
    if not isinstance(identity, dict): _fail('explicit journal identity required')
    _sha(initial_density_id, 'initial density ID')
    if execution_kind == SIMULATED_MODE:
        _same(identity.get('mode'), SIMULATED_MODE, 'simulated mode')
        _same(identity.get('execution_kind'), SIMULATED_MODE, 'simulated execution kind')
        _same(identity.get('scientific_execution_authorized'), False, 'simulated authorization')
        for key in ('scientific_budget_reserved', 'scientific_approval', 'Compute', 'local_cli_execute_requested'):
            _same(identity.get(key, False), False, 'simulated '+key)
        for key in ('execution_grant', 'budget_reservation'):
            _same(identity.get(key), None, 'simulated '+key)
        if explicit_grant is not None or local_cli_execute_requested is not False: _fail('simulated identity cannot carry real execute context')
        if 'initial_density_id' in identity: _same(identity['initial_density_id'], initial_density_id, 'simulated initial density')
        return {'status': 'PASS_SIMULATED_IDENTITY_ONLY', 'scientific_execution_authorized': False,
                'native_execution_observed': 'NOT_PROVEN_BY_IDENTITY'}
    if execution_kind != NATIVE_MODE or contract is None: _fail('new native mode and captured contract required; old modes refused')
    if contract.get('scientific_execution_authorized') is not True: _fail('false preparation identity cannot open a native journal')
    expected = execution_identity(contract, identity.get('execution_contract_sha256'),
        explicit_grant=explicit_grant, local_cli_execute_requested=local_cli_execute_requested)
    _same(identity, expected, 'complete native journal binding')
    _same(initial_density_id, INITIAL_DENSITY_ID, 'native selected initial density')
    return {'status': 'PASS_FUTURE_NATIVE_DECLARATION_IDENTITY_ONLY',
            'contract_family_sha256': expected['contract_family_sha256'],
            'scientific_execution_authorized': True, 'native_execution_observed': 'NOT_PROVEN_BY_IDENTITY'}
