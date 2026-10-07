"""Independent stdlib identity contract for twelve occupied-space responses.

This module binds retained bytes and declarations, not a solver, authorization
authority, resource qualification or scientific method. Actual NumPy recipe
and cache admission, one-use durable budgets and native guards are separate.
No historical nine-call or V2 execution schema is projected or reopened.
"""
import ast
import copy
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import struct
import zipfile

from . import occupation_response_contract as immutable
from .input import strict_json

SCHEMA = 'occupied-space-single-f-response-execution-v1'
EXECUTION_KIND = 'PREPARED_OCCUPIED_SPACE_SINGLE_RESPONSE_DIAGNOSTIC'
AUTHORIZATION_MESSAGE = '请继续下一步'
DIAGNOSTIC_SCOPE = 'FOUR_FIXED_OCCUPIED_SPACE_DENSITIES_SINGLE_F_ONLY_NOT_SCF'
POLICY = 'MASKED_GLOBAL_OCCUPIED_VIRTUAL_ANCHOR_ROTATION_DIAGNOSTIC_V1'
ExecutionContractError = immutable.ExecutionContractError
SCIENCE, BASELINE = immutable.SCIENCE, immutable.BASELINE
IMAGE, IMAGE_BUILD = immutable.IMAGE, immutable.IMAGE_BUILD
DEPENDENCIES = copy.deepcopy(immutable.DEPENDENCIES)
FIXTURE = copy.deepcopy(immutable.FIXTURE)
FINAL_THRESHOLDS = copy.deepcopy(immutable.FINAL_THRESHOLDS)
COMPARISONS = copy.deepcopy(immutable.NUMERICAL_COMPARISONS)
canonical_sha = immutable.canonical_sha
PROFILE_CANONICAL_SHA256 = '5c78ef8e741b255421a465895524cdb7aa208ef90751a1524eff9c7f88e5d537'
PROFILE_EXECUTED_RAW_SHA256 = '18bd594a8b606ef2c90db4390243155031035cd98fbe72dfc2e9367aeadce2e9'
SOURCE_SHA256 = 'f3e9be814ee844606bdb6bd13980007ba11d9965d70cd167e2521e980483646b'
SOURCE_ARRAYS_SHA256 = '4a0cdf07d6007aa16234dcb6dd55f3f587fd74322c1e67244afc9ab736e046da'
SEED_RECORD_SHA256 = 'a165633039bb3f3b250e872595e39510749a9003a412247cb1e9e315c003a961'
SEED_ARRAYS_SHA256 = 'f5da3ad1de1e1cea561408fe43ef93099c0ffbdcd8faba11eef8142d39b450fa'
PREPARATION_COMMIT = '029cd557f2a858051a4f98d34cadc981b932346c'
BASE_DENSITY_ID = 'bde824cc2957779325a8f8c2fb53fb626970c55b757285a1da4a69fdb92b4faf'
ANGLES = (-.25, -.1, .1, .25)
PATHS = ('production_copy', 'production_owned', 'independent_reference')
SEED_DENSITY_IDS = (
    '987b007d2d30c295efcdacffcdfb17ef47d89617c8db80cb30f23455a5dfe521',
    '6b0d501aba96ac5c53ca633491e105d7c5dab13836350bd6d7350437f91bd7c0',
    'd8be75fe06f0827aaa1214c8b83156bf596cf80a12407fc489e43dfbe9d94218',
    'cfc94a243ea486db1e49b142c407529f9389919ddb5fae2282c489a214fb90e3')
SEED_ARRAY_SHA256 = (
    '033d31fb863bc8e38882b1b272ff3042ec456dbbfee318fda9ef1f2705c67948',
    'd1a6206219fcbbb8863ccc95d5cc0644f817f3b234fedd662689fde0c5c8828c',
    '574f07352a33b63da496b743bb8016c3e770b3d33f8e61d6d9a9fc88fce26b49',
    '32c51caf3ca3b58029d256008153fe487e4d34a20bd5f7477bfca940120ca8b6')
PROCESS_CONTRACT = {**copy.deepcopy(immutable.PROCESS_CONTRACT),
    'density_probes': 4, 'total_true_F_or_NR_calls_maximum': 12}
PATH_LIMITS = {name: 4 for name in PATHS}
RECIPE = {'electrons': 16, 'angles_rad': list(ANGLES),
    'occupied_ao_anchor_0based': [4, 9], 'virtual_ao_anchor_0based': [2, 7],
    'selection': 'FIXED_LABEL_BASED_SUM_NO_F_ENERGY_SELECTION_NO_FALLBACK',
    'direction': 'PI_OCCUPIED_TO_SIGMA_VIRTUAL_FOR_THIS_EXACT_FIXTURE'}
ARRAY_THRESHOLDS = {'symmetry_absolute': 1e-12,
    'whitened_trace_absolute': 1e-10, 'whitened_idempotency_absolute': 1e-10,
    'masked_electron_count_absolute': 1e-7, 'production_density_reconstruction_relative': 1e-10,
    'selected_direction_manifold_roundoff': 1e-10,
    'selected_direction_projection_fraction_minimum_exclusive': 1e-12}
REQUIRED_SOURCE_FILES = frozenset((
    'runtime/user_molecule/occupied_space_response.py',
    'runtime/user_molecule/occupied_space_response_contract.py',
    'runtime/user_molecule/occupied_space_seeds.py', 'runtime/user_molecule/occupied_space_admission.py',
    'runtime/user_molecule/occupation_response.py', 'runtime/user_molecule/occupation_response_contract.py',
    'scripts/diagnose-user-molecule-occupied-space-response.py',
    'scripts/diagnose-user-molecule-occupied-space-response-worker.py',
    'runtime/user_molecule/residual_seed_preparation.py', 'runtime/user_molecule/residual_preparation.py',
    'runtime/user_molecule/residual_bridge.py', 'runtime/user_molecule/residual_budget.py',
    'runtime/user_molecule/acceptance_resources.py', 'runtime/user_molecule/solver_candidate.py',
    'reference/residual_molecule.py', 'reference/user_molecule.py'))
_equal = immutable._equal
_array_identity = immutable._array_identity
_sha = immutable.retained._sha


def _fail(message):
    raise ExecutionContractError('Occupied-space response: ' + message)


def _meta(value, name, digest, size):
    immutable._file_metadata(value, name, digest, size)


def _ordinary(origin):
    for key, expected in (('kind', 'REUSE_PRIOR_FULL_INDEPENDENT_ORDINARY_REFERENCE'),
        ('record_file', 'ordinary-reference.json'), ('arrays_file', 'ordinary-reference.npz')):
        _equal(origin[key], expected, 'ordinary.' + key)
    _meta(origin['record'], 'ordinary record', 'b0a9fd8a2487d725668823b75966176e98eb25551f40b9f177b485141ecb9663', 11741)
    _meta(origin['arrays'], 'ordinary arrays', '2a0318c42ee47001e2774ea6b4fec8317b1887c744a2720e71033a75b18f6051', 1728678)
    arrays = origin['array_identities']
    if not isinstance(arrays, dict) or set(arrays) != set(immutable.FROZEN_ARRAYS):
        _fail('all eight full cached ordinary array identities required')
    for key, (shape, digest) in immutable.FROZEN_ARRAYS.items():
        _array_identity(arrays[key], 'ordinary.' + key, shape, digest)
    _equal(origin['common_density_identity'], arrays['density'], 'old common density')
    _equal(origin['nuclear_repulsion_hartree'], 33.23272494899829, 'cached nuclear repulsion')


def validate_execution_contract(contract):
    """Validate declarations; an authorized boolean never substitutes authority."""
    try:
        if not isinstance(contract, dict): _fail('explicit contract dictionary required')
        _equal(contract['schema_version'], SCHEMA, 'independent schema')
        _equal(contract['execution_kind'], EXECUTION_KIND, 'live execution kind')
        _equal(contract['diagnostic_scope'], DIAGNOSTIC_SCOPE, 'diagnostic scope')
        _equal(contract['initialization_policy'], POLICY, 'initialization policy')
        if type(contract['scientific_execution_authorized']) is not bool:
            _fail('authorization is an explicit boolean; templates remain false')
        _equal(contract['authorization_basis'], {'source': 'DIRECT_USER_MESSAGE', 'message': AUTHORIZATION_MESSAGE}, 'authorization basis')
        for key in ('production_activation', 'scientific_approval', 'method_approval', 'external_review_required'):
            _equal(contract[key], False, key)
        _equal(contract['external_review_status'], 'CANCELLED_BY_USER', 'external review')
        if not isinstance(contract['batch_id'], str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', contract['batch_id']) is None:
            _fail('bounded fresh batch identity required')
        _sha(contract['runtime_test_commit'], 'runtime_test_commit', 40)
        for key, expected in (('science_commit', SCIENCE), ('science_baseline_commit', BASELINE),
            ('image_id', IMAGE), ('image_build_runtime_commit', IMAGE_BUILD),
            ('profile_canonical_sha256', PROFILE_CANONICAL_SHA256),
            ('profile_executed_raw_sha256', PROFILE_EXECUTED_RAW_SHA256),
            ('profile_sha256', PROFILE_EXECUTED_RAW_SHA256),
            ('dependencies_sha256', canonical_sha(DEPENDENCIES))):
            _equal(contract[key], expected, key)
        for key in ('source_manifest_sha256', 'prior_proposal_sha256'): _sha(contract[key], key)
        _equal(contract['expected_dependencies'], DEPENDENCIES, 'dependencies')
        _equal(contract['fixture'], FIXTURE, 'fixed fixture')
        _equal(contract['process_contract'], PROCESS_CONTRACT, 'process limits')
        _equal(contract['path_callback_limits'], PATH_LIMITS, 'four slots each')
        _equal(contract['paths'], list(PATHS), 'fixed path order')
        _equal(contract['final_thresholds'], FINAL_THRESHOLDS, 'all original final thresholds')
        _equal(contract['array_admission_thresholds'], ARRAY_THRESHOLDS, 'unchanged array admission')
        _equal(contract['comparisons'], COMPARISONS, 'unchanged comparisons')
        _ordinary(contract['ordinary_origin'])
        sources = contract['source_file_sha256']
        if not isinstance(sources, dict) or not REQUIRED_SOURCE_FILES <= set(sources):
            _fail('all real worker and retained source identities required')
        for path, digest in sources.items():
            if (not isinstance(path, str) or not path or '\\' in path or ':' in path
                    or PurePosixPath(path).is_absolute() or any(part in {'', '.', '..'} for part in path.split('/'))):
                _fail('canonical relative POSIX source paths required')
            _sha(digest, 'source file ' + path)
        binding = contract['seed_binding']
        for key, digest, size in (('source_record', SOURCE_SHA256, 7852),
            ('source_arrays', SOURCE_ARRAYS_SHA256, 6716), ('seed_record', SEED_RECORD_SHA256, 13624),
            ('seed_arrays', SEED_ARRAYS_SHA256, 12398)):
            _meta(binding[key], key, digest, size)
        for key, expected in (('source_record_file', 'SOURCE.json'), ('source_arrays_file', 'source-arrays.npz'),
            ('seed_record_file', 'prepared-seed-family.json'), ('seed_arrays_file', 'prepared-seed-family.npz'),
            ('preparation_runtime_commit', PREPARATION_COMMIT), ('base_density_id', BASE_DENSITY_ID),
            ('recipe', RECIPE), ('seed_density_ids', list(SEED_DENSITY_IDS)),
            ('seed_array_sha256', list(SEED_ARRAY_SHA256)), ('native_F_preparation_calls', 0),
            ('endpoint_acceptance', 'NOT_EXECUTED'), ('recipe_preflight', 'REQUIRED_ACTUAL_NUMPY_BEFORE_CALLBACK')):
            _equal(binding[key], expected, 'seed_binding.' + key)
        json.dumps(contract, allow_nan=False)
        return contract
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        if isinstance(error, ExecutionContractError): raise
        raise ExecutionContractError('Incomplete occupied-space response contract: ' + str(error)) from error


def load_execution_contract(path):
    return validate_execution_contract(strict_json(Path(path).read_bytes()))


def minimal_template(ordinary_origin, *, source_size_bytes=7852, seed_record_size_bytes=13624,
                     seed_arrays_size_bytes=12398):
    """Inert no-file-read declaration, for the supervisor to fill and bind."""
    return {'schema_version': SCHEMA, 'execution_kind': EXECUTION_KIND,
        'diagnostic_scope': DIAGNOSTIC_SCOPE, 'initialization_policy': POLICY,
        'batch_id': 'occupied-space-response-template-not-reserved',
        'scientific_execution_authorized': False,
        'authorization_basis': {'source': 'DIRECT_USER_MESSAGE', 'message': AUTHORIZATION_MESSAGE},
        'production_activation': False, 'scientific_approval': False, 'method_approval': False,
        'external_review_required': False, 'external_review_status': 'CANCELLED_BY_USER',
        'runtime_test_commit': '0'*40, 'science_commit': SCIENCE, 'science_baseline_commit': BASELINE,
        'image_id': IMAGE, 'image_build_runtime_commit': IMAGE_BUILD,
        'profile_sha256': PROFILE_EXECUTED_RAW_SHA256, 'profile_canonical_sha256': PROFILE_CANONICAL_SHA256,
        'profile_executed_raw_sha256': PROFILE_EXECUTED_RAW_SHA256,
        'expected_dependencies': copy.deepcopy(DEPENDENCIES), 'dependencies_sha256': canonical_sha(DEPENDENCIES),
        'source_manifest_sha256': '0'*64, 'prior_proposal_sha256': '0'*64,
        'source_file_sha256': {path: '0'*64 for path in sorted(REQUIRED_SOURCE_FILES)},
        'fixture': copy.deepcopy(FIXTURE), 'ordinary_origin': copy.deepcopy(ordinary_origin),
        'process_contract': copy.deepcopy(PROCESS_CONTRACT), 'path_callback_limits': dict(PATH_LIMITS),
        'paths': list(PATHS), 'comparisons': copy.deepcopy(COMPARISONS),
        'final_thresholds': copy.deepcopy(FINAL_THRESHOLDS), 'array_admission_thresholds': dict(ARRAY_THRESHOLDS),
        'seed_binding': {'source_record_file': 'SOURCE.json', 'source_arrays_file': 'source-arrays.npz',
            'seed_record_file': 'prepared-seed-family.json', 'seed_arrays_file': 'prepared-seed-family.npz',
            'source_record': {'size_bytes': source_size_bytes, 'sha256': SOURCE_SHA256},
            'source_arrays': {'size_bytes': 6716, 'sha256': SOURCE_ARRAYS_SHA256},
            'seed_record': {'size_bytes': seed_record_size_bytes, 'sha256': SEED_RECORD_SHA256},
            'seed_arrays': {'size_bytes': seed_arrays_size_bytes, 'sha256': SEED_ARRAYS_SHA256},
            'preparation_runtime_commit': PREPARATION_COMMIT, 'base_density_id': BASE_DENSITY_ID,
            'recipe': copy.deepcopy(RECIPE), 'seed_density_ids': list(SEED_DENSITY_IDS),
            'seed_array_sha256': list(SEED_ARRAY_SHA256), 'native_F_preparation_calls': 0,
            'endpoint_acceptance': 'NOT_EXECUTED', 'recipe_preflight': 'REQUIRED_ACTUAL_NUMPY_BEFORE_CALLBACK'}}


def execution_identity(contract, contract_sha256):
    validate_execution_contract(contract); _sha(contract_sha256, 'execution_contract_sha256')
    binding = contract['seed_binding']
    return {'mode': EXECUTION_KIND, 'execution_kind': EXECUTION_KIND,
        'diagnostic_scope': DIAGNOSTIC_SCOPE, 'scientific_execution_authorized': contract['scientific_execution_authorized'],
        'batch_id': contract['batch_id'], 'execution_contract_sha256': contract_sha256,
        **{key: contract[key] for key in ('runtime_test_commit', 'science_commit', 'science_baseline_commit',
            'image_id', 'image_build_runtime_commit', 'source_manifest_sha256', 'profile_sha256',
            'profile_canonical_sha256', 'profile_executed_raw_sha256', 'dependencies_sha256')},
        'geometry_sha256': contract['fixture']['xyz_sha256'],
        'ordinary_record_sha256': contract['ordinary_origin']['record']['sha256'],
        'ordinary_arrays_sha256': contract['ordinary_origin']['arrays']['sha256'],
        'source_input_sha256': binding['source_record']['sha256'],
        'source_arrays_sha256': binding['source_arrays']['sha256'],
        'seed_record_sha256': binding['seed_record']['sha256'],
        'seed_arrays_sha256': binding['seed_arrays']['sha256'],
        'seed_density_ids': list(SEED_DENSITY_IDS), 'fixed_angles_rad': list(ANGLES),
        'source_file_identity_sha256': canonical_sha(contract['source_file_sha256'])}


def validate_response_journal_identity(identity, *, prepared_seeds, execution_kind):
    """Adapter pre-entry declaration check; never authenticates user permission."""
    try:
        if not isinstance(identity, dict): _fail('journal identity dictionary required')
        if execution_kind == 'ENGINEERING_FAKE':
            _equal(identity.get('mode'), 'ENGINEERING_FAKE', 'fake journal mode')
            _equal(identity.get('execution_kind', 'ENGINEERING_FAKE'), 'ENGINEERING_FAKE', 'fake identity kind')
            _equal(identity.get('scientific_execution_authorized', False), False, 'fake authorization')
            return True
        if execution_kind != EXECUTION_KIND: _fail('unsupported diagnostic mode')
        for key, expected in (('mode', EXECUTION_KIND), ('execution_kind', EXECUTION_KIND),
            ('diagnostic_scope', DIAGNOSTIC_SCOPE), ('scientific_execution_authorized', True),
            ('science_commit', SCIENCE), ('science_baseline_commit', BASELINE), ('image_id', IMAGE),
            ('image_build_runtime_commit', IMAGE_BUILD), ('geometry_sha256', FIXTURE['xyz_sha256']),
            ('dependencies_sha256', canonical_sha(DEPENDENCIES)),
            ('profile_sha256', PROFILE_EXECUTED_RAW_SHA256), ('profile_executed_raw_sha256', PROFILE_EXECUTED_RAW_SHA256),
            ('profile_canonical_sha256', PROFILE_CANONICAL_SHA256), ('source_input_sha256', SOURCE_SHA256),
            ('source_arrays_sha256', SOURCE_ARRAYS_SHA256), ('seed_record_sha256', SEED_RECORD_SHA256),
            ('seed_arrays_sha256', SEED_ARRAYS_SHA256), ('seed_density_ids', list(SEED_DENSITY_IDS)),
            ('fixed_angles_rad', list(ANGLES))):
            _equal(identity[key], expected, 'journal.' + key)
        _sha(identity['runtime_test_commit'], 'journal runtime_test_commit', 40)
        for key in ('execution_contract_sha256', 'source_manifest_sha256', 'source_file_identity_sha256'):
            _sha(identity[key], 'journal.' + key)
        _equal(identity['ordinary_record_sha256'], 'b0a9fd8a2487d725668823b75966176e98eb25551f40b9f177b485141ecb9663', 'journal ordinary record')
        _equal(identity['ordinary_arrays_sha256'], '2a0318c42ee47001e2774ea6b4fec8317b1887c744a2720e71033a75b18f6051', 'journal ordinary arrays')
        _equal(list(prepared_seeds['angles_rad']), list(ANGLES), 'actual prepared angles')
        _equal([row['density_id'] for row in prepared_seeds['seeds']], list(SEED_DENSITY_IDS), 'actual prepared IDs')
        _equal(prepared_seeds['policy_id'], POLICY, 'actual preparation policy')
        json.dumps(identity, allow_nan=False)
        return True
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        if isinstance(error, ExecutionContractError): raise
        raise ExecutionContractError('Invalid response journal identity: ' + str(error)) from error


def _array_references(value):
    if isinstance(value, dict):
        if 'npz_member' in value: return [value]
        return [row for member in value.values() for row in _array_references(member)]
    if isinstance(value, list): return [row for member in value for row in _array_references(member)]
    return []


def _npy_payload(raw, shape, dtype):
    if raw[:6] != b'\x93NUMPY' or len(raw) < 10: _fail('NPY header missing')
    version = tuple(raw[6:8])
    if version == (1, 0): start, length = 10, struct.unpack('<H', raw[8:10])[0]
    elif version in ((2, 0), (3, 0)) and len(raw) >= 12: start, length = 12, struct.unpack('<I', raw[8:12])[0]
    else: _fail('unsupported NPY version')
    if not 0 < length <= 4096 or start+length > len(raw): _fail('NPY header bound/truncation failure')
    header = ast.literal_eval(raw[start:start+length].decode('utf-8' if version == (3, 0) else 'latin1').strip())
    if (not isinstance(header, dict) or set(header) != {'descr', 'fortran_order', 'shape'}
            or header['descr'] != dtype or header['fortran_order'] is not False
            or type(header['shape']) is not tuple or header['shape'] != tuple(shape)
            or any(type(item) is not int for item in header['shape'])): _fail('NPY shape/dtype/C-order differs')
    payload = raw[start+length:]
    width = 8 if dtype == '<f8' else 1
    if dtype not in ('<f8', '|b1') or len(payload) != math.prod(shape)*width: _fail('NPY payload size/type differs')
    if dtype == '<f8' and any(not math.isfinite(row[0]) for row in struct.iter_unpack('<d', payload)):
        _fail('nonfinite saved array payload')
    if dtype == '|b1' and any(number not in (0, 1) for number in payload): _fail('noncanonical boolean mask payload')
    return payload


def _archive_bytes(raw, references, expected_count):
    metadata = {row['npz_member']: row for row in references}
    if len(references) != expected_count or len(metadata) != expected_count: _fail('exact unique array references required')
    payloads = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if len(names) != expected_count or len(set(names)) != expected_count or set(names) != {name+'.npy' for name in metadata}:
            _fail('NPZ exact unique member set differs')
        for member, row in metadata.items():
            if '/' in member or '\\' in member or ':' in member or member in ('.', '..'): _fail('unsafe member name')
            shape, dtype = row['shape'], row['dtype']
            if not isinstance(shape, list) or shape not in ([14], [14, 14]) or any(type(item) is not int for item in shape):
                _fail('only exact fixed vector/matrix shapes allowed')
            _sha(row['sha256'], 'saved member SHA')
            if 'finite' in row and row['finite'] is not True: _fail('saved member finite flag must be true')
            info = archive.getinfo(member+'.npy')
            if info.file_size > 196*8+4108: _fail('oversized fixed array member')
            payload = _npy_payload(archive.read(info), shape, dtype)
            if hashlib.sha256(payload).hexdigest() != row['sha256']: _fail('actual saved member SHA differs')
            payloads[member] = payload
    return payloads


def _preparation_declarations(record):
    for key, expected in (('policy_id', POLICY), ('status', 'PREPARED_PURE_ARRAY_NEW_INITIALIZATION_DIAGNOSTIC_CANDIDATE'),
        ('angles_rad', list(ANGLES)), ('functional_calls', 0), ('solver_iterations', 0),
        ('molecular_evaluation', 'NOT_EXECUTED'), ('endpoint_acceptance', 'NOT_EXECUTED'),
        ('F_at_new_density', None), ('energy', None), ('operator_id', None), ('delta_hartree', None),
        ('scientific_execution_authorized', False), ('scientific_approval', False), ('production_activation', False),
        ('compute_enabled', False), ('engine_qualified', False), ('research_qualified', False),
        ('repairs_performed', False), ('ordinary_occupied_space_preservation_claim', False),
        ('new_final_occupation_rule', False), ('array_admission_thresholds', ARRAY_THRESHOLDS)):
        _equal(record[key], expected, 'saved preparation.'+key)
    _equal(record['source']['density_id'], BASE_DENSITY_ID, 'source density ID')
    _equal(record['source']['expected_density_id'], BASE_DENSITY_ID, 'expected source density ID')
    _equal(record['source']['electrons'], 16, 'saved electron count')
    _equal(record['source']['occupied_rank'], 8, 'saved rank')
    if not isinstance(record['seeds'], list) or len(record['seeds']) != 4: _fail('four saved seeds required')
    for index, (row, angle, did, digest) in enumerate(zip(record['seeds'], ANGLES, SEED_DENSITY_IDS, SEED_ARRAY_SHA256), 1):
        for key, expected in (('seed_index', index), ('angle_rad', angle), ('density_id', did),
            ('F_at_new_density', None), ('energy', None), ('operator_id', None),
            ('molecular_evaluation', 'NOT_EXECUTED'), ('endpoint_acceptance', 'NOT_EXECUTED'),
            ('engine_qualified', False), ('research_qualified', False)):
            _equal(row[key], expected, 'saved seed.'+key)
        _array_identity(row['density_identity'], 'saved seed array', [14, 14], digest)
        _equal(row['density']['sha256'], digest, 'saved seed member SHA')


def validate_seed_binding(contract, source_bytes, seed_record_bytes, seed_arrays_bytes, *, source_arrays_bytes=None):
    """Verify retained source/seed bytes and metadata, without NumPy recipe work.

    Optional source-array bytes allow all six linked source members to be
    verified here. If omitted the receipt explicitly leaves them to worker
    admission; no matrix algebra or scientific callback runs in either case.
    """
    validate_execution_contract(contract)
    try:
        binding = contract['seed_binding']
        for key, raw in (('source_record', source_bytes), ('seed_record', seed_record_bytes), ('seed_arrays', seed_arrays_bytes)):
            if type(raw) is not bytes or len(raw) != binding[key]['size_bytes'] or hashlib.sha256(raw).hexdigest() != binding[key]['sha256']:
                _fail('actual retained '+key+' bytes differ')
        source, record = strict_json(source_bytes), strict_json(seed_record_bytes)
        for key, expected in (('schema_version', 'occupied-space-source-input-v1'), ('status', 'VERIFIED_RETAINED_BYTES_ONLY'),
            ('base_density_id', BASE_DENSITY_ID), ('base_status', 'UNQUALIFIED_SINGLE_POINT_NOT_ORDINARY_V2_SEED'),
            ('recipe', RECIPE), ('new_F_SCF_NR_grid_integral_calls', 0), ('scientific_budget', None), ('Compute', False)):
            _equal(source[key], expected, 'saved source.'+key)
        _equal(source['source_mapping']['profile_sha256'], PROFILE_CANONICAL_SHA256, 'historical canonical alias')
        _equal(source['source_mapping']['geometry_sha256'], FIXTURE['xyz_sha256'], 'source geometry')
        _equal(source['archive']['sha256'], SOURCE_ARRAYS_SHA256, 'source archive SHA')
        _equal(source['archive']['size_bytes'], 6716, 'source archive size')
        _preparation_declarations(record)
        _equal(record['raw_array_archive']['sha256'], SEED_ARRAYS_SHA256, 'saved seed archive SHA')
        _equal(record['raw_array_archive']['size_bytes'], 12398, 'saved seed archive size')
        payloads = _archive_bytes(seed_arrays_bytes, _array_references(record), 10)
        for row in record['seeds']:
            payload = payloads[row['density']['npz_member']]
            did = hashlib.sha256(b'AI4OrgChem-density-v1\0'+struct.pack('<QQ', 14, 14)+payload).hexdigest()
            _equal(did, row['density_id'], 'actual saved seed domain ID')
        source_verified = False
        if source_arrays_bytes is not None:
            meta = binding['source_arrays']
            if type(source_arrays_bytes) is not bytes or len(source_arrays_bytes) != meta['size_bytes'] or hashlib.sha256(source_arrays_bytes).hexdigest() != meta['sha256']:
                _fail('actual source archive bytes differ')
            _archive_bytes(source_arrays_bytes, [dict(row, npz_member=name) for name, row in source['arrays'].items()], 6)
            source_verified = True
        return {'status': 'PASS_SAVED_SOURCE_SEED_BYTES_ONLY', 'seed_record': record, 'source_record': source,
            'prepared_array_members_verified': 10, 'source_array_members_verified': 6 if source_verified else 0,
            'source_array_bytes_status': 'PASS' if source_verified else 'NOT_EXECUTED_WORKER_MUST_VERIFY',
            'actual_numpy_recipe': 'NOT_EXECUTED_WORKER_MUST_VERIFY', 'new_true_F_calls': 0,
            'scientific_execution_authorized': contract['scientific_execution_authorized'], 'production_activation': False}
    except (KeyError, TypeError, ValueError, OverflowError, zipfile.BadZipFile, UnicodeError, SyntaxError, struct.error) as error:
        if isinstance(error, ExecutionContractError): raise
        raise ExecutionContractError('Invalid retained occupied-space seed binding: '+str(error)) from error
