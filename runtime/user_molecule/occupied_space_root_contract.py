"""Inert single-start root-candidate contract and retained-input byte checks.

The current direct-user request authorizes implementation and zero-F preparation
only. This version rejects scientific authorization and creates no allowance.
201 callbacks/300 seconds are proposed bounds, not a reservation. Any future
root execution requires a separately authorized version; old budgets stay shut.
"""
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

from . import occupied_space_response_contract as retained
from .input import strict_json

SCHEMA = 'occupied-space-single-start-root-candidate-contract-v1'
EXECUTION_KIND = 'PREPARED_OCCUPIED_SPACE_ROOT_DIAGNOSTIC'
AUTHORIZATION_MESSAGE = '请继续下一步'
AUTHORIZATION_SCOPE = 'IMPLEMENTATION_AND_ZERO_F_PREPARATION_ONLY; FUTURE_ROOT_EXECUTION_REQUIRES_SEPARATE_DIRECT_AUTHORIZATION'
ExecutionContractError = retained.ExecutionContractError
INITIAL_DENSITY_ID = retained.SEED_DENSITY_IDS[1]
INITIAL_ARRAY_SHA256 = retained.SEED_ARRAY_SHA256[1]
INITIALIZATION_POLICY = retained.POLICY
PATH_ID = 'independent_reference'
PRIMARY_PATH = 'CACHED_INDEPENDENT_EQUATIONS_WITH_PINNED_PYSCF_XC'
SCIENCE, BASELINE = retained.SCIENCE, retained.BASELINE
IMAGE, IMAGE_BUILD = retained.IMAGE, retained.IMAGE_BUILD
DEPENDENCIES = copy.deepcopy(retained.DEPENDENCIES)
_equal, _sha = retained._equal, retained._sha
canonical_sha = retained.canonical_sha
SOLVER_PARAMETERS = {'maximum_charts': 1, 'chart_max_nfev': 2, 'maximum_evaluations': 201,
    'finite_difference_step': 1e-5, 'trust_radius': .25, 'occupied_virtual_variables': 48,
    'F_callbacks_per_complete_Jacobian': 96, 'maximum_complete_Jacobians': 2,
    'tail_callbacks_reserved': 2, 'maximum_normal_callback_cost': 197,
    'derivative_policy': 'PINNED_SCIPY_PRIVATE_APPROX_DERIVATIVE_THREE_POINT_V1',
    'required_scipy_version': '1.18.0',
    'returned_density_policy': 'LAST_COMPLETE_ACCEPTED_CHART_NEVER_BEST_SAMPLE_OR_BASE_SUBSTITUTION',
    'automatic_tail_after_budget_refusal': False}
PROCESS_CONTRACT = {'scientific_processes': 1, 'wall_seconds_through_cleanup': 300,
    'stop_deadline_seconds': 275, 'cleanup_headroom_seconds': 25,
    'hard_memory_bytes': 1073741824, 'maximum_cpus': 1, 'swap_bytes': 0,
    'initial_densities': 1, 'paths_per_initial_density': 1,
    'total_true_F_or_NR_calls_maximum': 201, 'maximum_nuclear_energy_calls': 0,
    'new_ordinary_SCF_grid_full_integrals': 0, 'automatic_retry': False,
    'refund_failed_slots': False, 'budget_expansion_or_refill': False,
    'non_root': True, 'offline': True, 'read_only_source_root_and_cache': True,
    'scope': 'PROPOSED_LIMITS_NOT_SCIENTIFIC_RESERVATION_OR_RESOURCE_APPROVAL'}
MDR_SHA256 = '63a799f3c105bdec16a01c5e01d80d47c3984648e3de3211af6a334846f6813a'
HISTORY_SHA256 = 'b476ddc8dd1e5f57912787aed1a09d44f3ec1bde2d9e8e6be719a123ed181cc9'
HISTORICAL_OPERATOR_ID = '763a07945225e13fa90d089deee04b9e2f4af53592a32640175fea978d97e839'
HISTORICAL_GAP = 0.00010264070787703583
REQUIRED_SOURCE_FILES = retained.REQUIRED_SOURCE_FILES | frozenset((
    'runtime/user_molecule/occupied_space_root_contract.py',
    'reference/occupied_space_root_candidate.py',
    'reference/residual_budgeted_candidate.py', 'reference/residual_candidate.py',
    'scripts/diagnose-user-molecule-occupied-space-root.py',
    'scripts/diagnose-user-molecule-occupied-space-root-worker.py'))


def _fail(message):
    raise ExecutionContractError('Occupied-space root candidate: '+message)


def minimal_template(ordinary_origin):
    """No-file-read inactive candidate, never a live 201-slot authorization."""
    inherited = retained.minimal_template(ordinary_origin)
    inherited.update(schema_version=SCHEMA, execution_kind=EXECUTION_KIND,
        diagnostic_scope='ONE_INITIAL_DENSITY_ONE_PRIMARY_PATH_ROOT_CANDIDATE_NOT_COMPUTE',
        authorization_scope=AUTHORIZATION_SCOPE, scientific_execution_authorized=False,
        scientific_budget_reserved=False, batch_id='occupied-space-root-template-not-reserved',
        initialization_policy=INITIALIZATION_POLICY, paths=[PATH_ID],
        primary_path=PRIMARY_PATH, path_callback_limits={PATH_ID: 201},
        process_contract=copy.deepcopy(PROCESS_CONTRACT), solver_parameters=copy.deepcopy(SOLVER_PARAMETERS),
        source_file_sha256={name: '0'*64 for name in sorted(REQUIRED_SOURCE_FILES)},
        initial_density={'seed_index': 2, 'angle_rad': -.1, 'density_id': INITIAL_DENSITY_ID,
            'array_identity': {'shape': [14, 14], 'dtype': '<f8', 'order': 'C', 'sha256': INITIAL_ARRAY_SHA256},
            'selection_scope': 'TECHNICAL_INITIAL_VALUE_NOT_SCIENTIFIC_STATE_APPROVAL',
            'lower_policy': 'REQUIRE_EXISTING_MASKED_PROJECTOR', 'ordinary_space_preservation_claim': False,
            'CURRENT_INITIAL_F_required_from_new_budget': True, 'old_F_or_energy_reused_as_new': False},
        parent_evidence={'mdr_file': 'MDR-007.json', 'history_file': 'parent-response-result.json',
            'mdr_record': {'size_bytes': 2258, 'sha256': MDR_SHA256},
            'history_record': {'size_bytes': 120062, 'sha256': HISTORY_SHA256},
            'execution_runtime_commit': '63dc6f64a683682fbdcbfc0debcece4f6c40d3c6',
            'historical_operator_id': HISTORICAL_OPERATOR_ID, 'historical_initial_gap_hartree': HISTORICAL_GAP,
            'scope': 'OLD_SINGLE_POINT_ONLY_NOT_NEW_SOLVER_F_CURRENT_OR_TAIL',
            'qualified_endpoint': False, 'old_budgets': '12_9_603_CLOSED_NOT_REOPENABLE'},
        future_live_execution='NOT_AUTHORIZED_IN_THIS_CONTRACT_VERSION', Compute=False,
        research_delta_hartree=None)
    return inherited


def validate_execution_contract(contract):
    """Validate this implementation-only scope; explicit True is refused."""
    try:
        expected = minimal_template(contract['ordinary_origin'])
        for key in ('schema_version', 'execution_kind', 'diagnostic_scope', 'authorization_scope',
            'scientific_execution_authorized', 'scientific_budget_reserved', 'authorization_basis',
            'production_activation', 'scientific_approval', 'method_approval', 'external_review_required',
            'external_review_status', 'initialization_policy', 'paths', 'primary_path', 'path_callback_limits',
            'process_contract', 'solver_parameters', 'fixture', 'final_thresholds', 'array_admission_thresholds',
            'comparisons', 'initial_density', 'parent_evidence', 'future_live_execution', 'Compute', 'research_delta_hartree',
            'science_commit', 'science_baseline_commit', 'image_id', 'image_build_runtime_commit',
            'profile_sha256', 'profile_canonical_sha256', 'profile_executed_raw_sha256',
            'expected_dependencies', 'dependencies_sha256', 'seed_binding'):
            _equal(contract[key], expected[key], key)
        retained._ordinary(contract['ordinary_origin'])
        if not isinstance(contract['batch_id'], str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', contract['batch_id']) is None:
            _fail('fresh bounded candidate batch identity required')
        _sha(contract['runtime_test_commit'], 'runtime_test_commit', 40)
        for key in ('source_manifest_sha256', 'prior_proposal_sha256'): _sha(contract[key], key)
        sources = contract['source_file_sha256']
        if not isinstance(sources, dict) or not REQUIRED_SOURCE_FILES <= set(sources): _fail('all critical old/new source identities required')
        for path, digest in sources.items():
            if (not isinstance(path, str) or not path or '\\' in path or ':' in path or PurePosixPath(path).is_absolute()
                    or any(part in ('', '.', '..') for part in path.split('/'))): _fail('canonical relative POSIX source paths required')
            _sha(digest, 'source '+path)
        json.dumps(contract, allow_nan=False)
        return contract
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        if isinstance(error, ExecutionContractError): raise
        raise ExecutionContractError('Incomplete root-candidate contract: '+str(error)) from error


def load_execution_contract(path):
    return validate_execution_contract(strict_json(Path(path).read_bytes()))


def execution_identity(contract, contract_sha256):
    validate_execution_contract(contract); _sha(contract_sha256, 'execution_contract_sha256')
    origin, binding = contract['ordinary_origin'], contract['seed_binding']
    return {'mode': EXECUTION_KIND, 'execution_kind': EXECUTION_KIND,
        'authorization_scope': AUTHORIZATION_SCOPE, 'scientific_execution_authorized': False,
        'batch_id': contract['batch_id'], 'execution_contract_sha256': contract_sha256,
        **{key: contract[key] for key in ('runtime_test_commit', 'science_commit', 'science_baseline_commit',
            'image_id', 'image_build_runtime_commit', 'source_manifest_sha256', 'profile_sha256',
            'profile_canonical_sha256', 'profile_executed_raw_sha256', 'dependencies_sha256')},
        'geometry_sha256': contract['fixture']['xyz_sha256'], 'path_id': PATH_ID,
        'initial_density_id': INITIAL_DENSITY_ID, 'initial_seed_index': 2, 'initial_angle_rad': -.1,
        'ordinary_record_sha256': origin['record']['sha256'], 'ordinary_arrays_sha256': origin['arrays']['sha256'],
        'source_input_sha256': binding['source_record']['sha256'], 'source_arrays_sha256': binding['source_arrays']['sha256'],
        'seed_record_sha256': binding['seed_record']['sha256'], 'seed_arrays_sha256': binding['seed_arrays']['sha256'],
        'source_file_identity_sha256': canonical_sha(contract['source_file_sha256']),
        'scientific_budget_reserved': False, 'future_live_execution': 'NOT_AUTHORIZED_IN_THIS_CONTRACT_VERSION'}


def validate_root_journal_identity(identity, *, initial_density_id, execution_kind):
    """Only test-double journals are admitted in this implementation version."""
    if execution_kind != 'ENGINEERING_FAKE': _fail('ROOT_LIVE_EXECUTION_NOT_AUTHORIZED_IN_THIS_CANDIDATE_VERSION')
    if not isinstance(identity, dict): _fail('explicit fake journal identity required')
    _equal(identity.get('mode'), 'ENGINEERING_FAKE', 'fake journal mode')
    _equal(identity.get('execution_kind', 'ENGINEERING_FAKE'), 'ENGINEERING_FAKE', 'fake journal execution kind')
    _equal(identity.get('scientific_execution_authorized', False), False, 'fake authorization')
    _sha(initial_density_id, 'fake initial density ID')
    if 'initial_density_id' in identity: _equal(identity['initial_density_id'], initial_density_id, 'fake initial density binding')
    return True


def _actual(raw, metadata, label):
    if type(raw) is not bytes or len(raw) != metadata['size_bytes'] or hashlib.sha256(raw).hexdigest() != metadata['sha256']:
        _fail('actual retained '+label+' bytes differ')


def validate_seed_binding(contract, source_bytes, seed_record_bytes, seed_arrays_bytes, *, source_arrays_bytes=None):
    """Compose only prior pure-byte helpers, never project a 12-call schema."""
    validate_execution_contract(contract)
    try:
        binding = contract['seed_binding']
        for name, raw in (('source_record', source_bytes), ('seed_record', seed_record_bytes), ('seed_arrays', seed_arrays_bytes)):
            _actual(raw, binding[name], name)
        source, record = strict_json(source_bytes), strict_json(seed_record_bytes)
        _equal(source['recipe'], retained.RECIPE, 'source fixed recipe')
        _equal(source['new_F_SCF_NR_grid_integral_calls'], 0, 'source calls')
        _equal(source['scientific_budget'], None, 'source budget')
        _equal(source['Compute'], False, 'source Compute')
        _equal(source['source_mapping']['profile_sha256'], retained.PROFILE_CANONICAL_SHA256, 'historical canonical profile alias')
        retained._preparation_declarations(record)
        payloads = retained._archive_bytes(seed_arrays_bytes, retained._array_references(record), 10)
        selected = record['seeds'][1]
        _equal(selected['density_id'], INITIAL_DENSITY_ID, 'selected initial D')
        _equal(selected['density_identity'], contract['initial_density']['array_identity'], 'selected initial array identity')
        verified = False
        if source_arrays_bytes is not None:
            _actual(source_arrays_bytes, binding['source_arrays'], 'source arrays')
            retained._archive_bytes(source_arrays_bytes, [dict(row, npz_member=name) for name, row in source['arrays'].items()], 6)
            verified = True
        return {'status': 'PASS_RETAINED_ROOT_INITIAL_INPUT_BYTES_ONLY', 'source_record': source, 'seed_record': record,
            'selected_seed_index': 2, 'selected_initial_density_id': INITIAL_DENSITY_ID,
            'prepared_members_verified': len(payloads), 'source_members_verified': 6 if verified else 0,
            'actual_numpy_recipe': 'NOT_EXECUTED_WORKER_MUST_VERIFY', 'new_true_F_calls': 0,
            'scientific_execution_authorized': False, 'scientific_budget_reserved': False}
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        if isinstance(error, ExecutionContractError): raise
        raise ExecutionContractError('Invalid retained root seed binding: '+str(error)) from error


def validate_input_binding(contract, source_bytes, seed_record_bytes, seed_arrays_bytes, *,
                           source_arrays_bytes=None, history_record_bytes=None, mdr_bytes=None):
    """Historical initial-F proof is explicitly separate from future solve F."""
    result = validate_seed_binding(contract, source_bytes, seed_record_bytes, seed_arrays_bytes,
                                   source_arrays_bytes=source_arrays_bytes)
    evidence = contract['parent_evidence']
    if history_record_bytes is None or mdr_bytes is None: _fail('both preserved method and initial-point records required')
    _actual(history_record_bytes, evidence['history_record'], 'historical twelve-point result')
    _actual(mdr_bytes, evidence['mdr_record'], 'MDR-007')
    history, decision = strict_json(history_record_bytes), strict_json(mdr_bytes)
    _equal(decision['id'], 'MDR-007', 'parent method ID')
    _equal(decision['runtime_source_commit'], evidence['execution_runtime_commit'], 'historical execution source')
    _equal(decision['scientific_method_approval'], False, 'historical method approval')
    _equal(decision['Compute'], False, 'historical Compute')
    rows = [row for row in history['snapshots'] if row['path_name'] == PATH_ID and row['seed_index'] == 2]
    if len(rows) != 1: _fail('unique historical primary-path initial point required')
    row = rows[0]
    _equal(row['density_id'], INITIAL_DENSITY_ID, 'historical initial density')
    _equal(row['angle_rad'], -.1, 'historical initial angle')
    _equal(row['operator_id'], HISTORICAL_OPERATOR_ID, 'historical matched operator')
    _equal(row['single_point_diagnostics']['final_non_diis_gap_hartree'], HISTORICAL_GAP, 'historical initial gap')
    if HISTORICAL_GAP < 1e-6: _fail('historical starting gap does not meet the unchanged threshold')
    return dict(result, historical_initial_point='PASS_BOUND_OLD_EVIDENCE_NOT_A_NEW_SOLVER_EVALUATION',
        historical_operator_id=HISTORICAL_OPERATOR_ID, future_CURRENT_INITIAL_F='REQUIRED_FRESH_CALLBACK_NOT_EXECUTED',
        new_root_budget=None, root_or_method_approval=False)
