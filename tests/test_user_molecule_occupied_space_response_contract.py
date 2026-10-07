"""Stdlib declaration and saved-byte tests; no environment or scientific work."""
from contextlib import ExitStack
import copy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from runtime.user_molecule import occupied_space_response_contract as execution


def ordinary_origin_fixture():
    arrays = {name: {'shape': shape, 'dtype': '<f8', 'order': 'C', 'sha256': digest}
              for name, (shape, digest) in execution.immutable.FROZEN_ARRAYS.items()}
    return {'kind': 'REUSE_PRIOR_FULL_INDEPENDENT_ORDINARY_REFERENCE',
        'record_file': 'ordinary-reference.json', 'arrays_file': 'ordinary-reference.npz',
        'record': {'size_bytes': 11741, 'sha256': 'b0a9fd8a2487d725668823b75966176e98eb25551f40b9f177b485141ecb9663'},
        'arrays': {'size_bytes': 1728678, 'sha256': '2a0318c42ee47001e2774ea6b4fec8317b1887c744a2720e71033a75b18f6051'},
        'common_density_identity': copy.deepcopy(arrays['density']), 'array_identities': arrays,
        'nuclear_repulsion_hartree': 33.23272494899829}


def contract_fixture(*, authorized=False):
    value = execution.minimal_template(ordinary_origin_fixture())
    value.update(batch_id='occupied-space-contract-test-new', runtime_test_commit='ab'*20,
        source_manifest_sha256='ac'*32, prior_proposal_sha256='ad'*32,
        source_file_sha256={name: 'ae'*32 for name in execution.REQUIRED_SOURCE_FILES},
        scientific_execution_authorized=authorized)
    return value


def _sha(raw): return hashlib.sha256(raw).hexdigest()


def _npy(payload, shape, dtype='<f8'):
    header = repr({'descr': dtype, 'fortran_order': False, 'shape': tuple(shape)}).encode('ascii')
    header += b' '*((64-(10+len(header)+1)%64)%64)+b'\n'
    return b'\x93NUMPY\x01\x00'+struct.pack('<H', len(header))+header+payload


def _archive(rows, size):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, (raw, shape, dtype) in rows.items(): archive.writestr(name+'.npy', _npy(raw, shape, dtype))
    raw = buffer.getvalue()
    if len(raw) > size: raise AssertionError('Synthetic fixture exceeds fixed archive size')
    return raw+b'\0'*(size-len(raw))


def _json_bytes(value, size):
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(raw) > size: raise AssertionError('Synthetic fixture exceeds fixed JSON size')
    return raw+b' '*(size-len(raw))


def binding_fixture():
    """Synthetic orthogonal-metric rotation bytes, with test-local trust anchors.

    These are never the retained molecular files or a grant to execute them.
    Both contracts and tests explicitly replace only local pinned byte anchors.
    """
    n = 14
    matrix = lambda values: b''.join(struct.pack('<d', number) for number in values)
    eye = matrix([float(i == j) for i in range(n) for j in range(n)])
    occ = [float(i in (4, 9)) for i in range(n)]
    vir = [float(i in (2, 7)) for i in range(n)]
    u = [number/math.sqrt(2) for number in occ]
    v = [number/math.sqrt(2) for number in vir]
    p = [[float(i == j and i in (0, 1, 3, 5, 6, 8, 10))+.5*occ[i]*occ[j]
          for j in range(n)] for i in range(n)]
    base = matrix([2*p[i][j] for i in range(n) for j in range(n)])
    ids, hashes, seeds, references, arrays = [], [], [], {}, {}
    def reference(member, payload, shape, source_field):
        references[member] = (payload, shape, '<f8')
        return {'npz_member': member, 'source_field': source_field, 'shape': shape,
                'dtype': '<f8', 'finite': True, 'sha256': _sha(payload)}
    record = {'policy_id': execution.POLICY, 'status': 'PREPARED_PURE_ARRAY_NEW_INITIALIZATION_DIAGNOSTIC_CANDIDATE',
        'source_density': reference('array_0000', base, [n, n], 'root.source_density'),
        'source_masked_overlap': reference('array_0001', eye, [n, n], 'root.source_masked_overlap'),
        'source_occupied_anchor': reference('array_0002', matrix(occ), [n], 'root.source_occupied_anchor'),
        'source_virtual_anchor': reference('array_0003', matrix(vir), [n], 'root.source_virtual_anchor'),
        'directions': {'occupied_white_direction': reference('array_0004', matrix(u), [n], 'root.directions.occupied_white_direction'),
            'virtual_white_direction': reference('array_0005', matrix(v), [n], 'root.directions.virtual_white_direction')},
        'source': {'density_id': '', 'expected_density_id': '', 'electrons': 16, 'occupied_rank': 8},
        'angles_rad': list(execution.ANGLES), 'seeds': seeds,
        'functional_calls': 0, 'solver_iterations': 0, 'molecular_evaluation': 'NOT_EXECUTED',
        'endpoint_acceptance': 'NOT_EXECUTED', 'F_at_new_density': None, 'energy': None,
        'operator_id': None, 'delta_hartree': None, 'scientific_execution_authorized': False,
        'scientific_approval': False, 'production_activation': False, 'compute_enabled': False,
        'engine_qualified': False, 'research_qualified': False, 'repairs_performed': False,
        'ordinary_occupied_space_preservation_claim': False, 'new_final_occupation_rule': False,
        'array_admission_thresholds': dict(execution.ARRAY_THRESHOLDS)}
    for index, angle in enumerate(execution.ANGLES, 1):
        t = [math.cos(angle)*left+math.sin(angle)*right for left, right in zip(u, v)]
        raw = matrix([2*(p[i][j]-u[i]*u[j]+t[i]*t[j]) for i in range(n) for j in range(n)])
        did = _sha(b'AI4OrgChem-density-v1\0'+struct.pack('<QQ', n, n)+raw)
        ids.append(did); hashes.append(_sha(raw))
        seeds.append({'seed_index': index, 'angle_rad': angle, 'density_id': did,
            'density': reference('array_'+str(index+5).zfill(4), raw, [n, n], 'root.seeds.'+str(index-1)+'.density'),
            'density_identity': {'shape': [n, n], 'dtype': '<f8', 'order': 'C', 'sha256': _sha(raw)},
            'F_at_new_density': None, 'energy': None, 'operator_id': None,
            'molecular_evaluation': 'NOT_EXECUTED', 'endpoint_acceptance': 'NOT_EXECUTED',
            'engine_qualified': False, 'research_qualified': False})
    npz = _archive(references, 12398)
    record['raw_array_archive'] = {'file': 'prepared-seed-family.npz', 'size_bytes': 12398, 'sha256': _sha(npz)}
    base_id = _sha(b'AI4OrgChem-density-v1\0'+struct.pack('<QQ', n, n)+base)
    record['source']['density_id'] = record['source']['expected_density_id'] = base_id
    source_arrays = {'base_density': (base, [n, n], '<f8'), 'masked_overlap': (eye, [n, n], '<f8'),
        'physical_overlap': (eye, [n, n], '<f8'), 'matrix_delete_mask': (b'\0'*(n*n), [n, n], '|b1'),
        'occupied_anchor': (matrix(occ), [n], '<f8'), 'virtual_anchor': (matrix(vir), [n], '<f8')}
    for name, (raw, shape, dtype) in source_arrays.items(): arrays[name] = {'shape': shape, 'dtype': dtype, 'sha256': _sha(raw)}
    source_npz = _archive(source_arrays, 6716)
    source = {'schema_version': 'occupied-space-source-input-v1', 'status': 'VERIFIED_RETAINED_BYTES_ONLY',
        'base_density_id': base_id, 'base_status': 'UNQUALIFIED_SINGLE_POINT_NOT_ORDINARY_V2_SEED',
        'recipe': copy.deepcopy(execution.RECIPE), 'new_F_SCF_NR_grid_integral_calls': 0,
        'scientific_budget': None, 'Compute': False,
        'source_mapping': {'profile_sha256': execution.PROFILE_CANONICAL_SHA256,
            'geometry_sha256': execution.FIXTURE['xyz_sha256']}, 'arrays': arrays,
        'archive': {'file': 'source-arrays.npz', 'sha256': _sha(source_npz), 'size_bytes': 6716}}
    source_raw, record_raw = _json_bytes(source, 7852), _json_bytes(record, 13624)
    anchors = {'SOURCE_SHA256': _sha(source_raw), 'SOURCE_ARRAYS_SHA256': _sha(source_npz),
        'SEED_RECORD_SHA256': _sha(record_raw), 'SEED_ARRAYS_SHA256': _sha(npz),
        'BASE_DENSITY_ID': base_id, 'SEED_DENSITY_IDS': tuple(ids), 'SEED_ARRAY_SHA256': tuple(hashes)}
    return source_raw, record_raw, npz, source_npz, anchors


class OccupiedSpaceResponseContractTests(unittest.TestCase):
    def setUp(self): self.value = contract_fixture()

    def refuse(self, mutation):
        value = copy.deepcopy(self.value); mutation(value)
        with self.assertRaises(execution.ExecutionContractError): execution.validate_execution_contract(value)

    def test_inert_template_validates_without_modification_and_cannot_grant_compute(self):
        before = copy.deepcopy(self.value)
        self.assertIs(execution.validate_execution_contract(self.value), self.value)
        self.assertEqual(self.value, before)
        self.assertIs(self.value['scientific_execution_authorized'], False)
        self.assertIs(execution.validate_execution_contract(contract_fixture(authorized=True))['production_activation'], False)

    def test_new_schema_kind_policy_and_current_user_authority_are_independent(self):
        for key, bad in (('schema_version', execution.immutable.SCHEMA), ('execution_kind', 'ENGINEERING_FAKE'),
            ('initialization_policy', 'MASKED_METRIC_OCCUPIED_SUBSPACE_SEED_V2'), ('diagnostic_scope', 'SCF')):
            self.refuse(lambda value: value.__setitem__(key, bad))
        self.refuse(lambda value: value['authorization_basis'].__setitem__('message', '请继续'))
        self.refuse(lambda value: value['authorization_basis'].__setitem__('source', 'DOCUMENT'))

    def test_boolean_authorization_approval_and_resource_types_are_exact(self):
        for bad in (1, 0, 'True', None): self.refuse(lambda value: value.__setitem__('scientific_execution_authorized', bad))
        for key in ('production_activation', 'scientific_approval', 'method_approval', 'external_review_required'):
            for bad in (0, True): self.refuse(lambda value: value.__setitem__(key, bad))
        self.refuse(lambda value: value['process_contract'].__setitem__('automatic_retry', 0))

    def test_exact_twelve_single_call_process_limits_no_scf_tail_refill_or_retry(self):
        for key, expected in execution.PROCESS_CONTRACT.items():
            bad = not expected if type(expected) is bool else expected+1
            self.refuse(lambda value: value['process_contract'].__setitem__(key, bad))
        self.refuse(lambda value: value['process_contract'].__setitem__('total_true_F_or_NR_calls_maximum', 12.))
        self.refuse(lambda value: value['path_callback_limits'].__setitem__('production_copy', 3))
        self.refuse(lambda value: value['paths'].reverse())

    def test_profile_raw_canonical_and_compatibility_alias_cannot_be_mixed(self):
        self.refuse(lambda value: value.__setitem__('profile_sha256', execution.PROFILE_CANONICAL_SHA256))
        self.refuse(lambda value: value.__setitem__('profile_executed_raw_sha256', execution.PROFILE_CANONICAL_SHA256))
        self.refuse(lambda value: value.__setitem__('profile_canonical_sha256', execution.PROFILE_EXECUTED_RAW_SHA256))

    def test_fixed_deps_image_science_fixture_and_full_cache_remain_pinned(self):
        for key in ('science_commit', 'science_baseline_commit', 'image_id', 'image_build_runtime_commit'):
            self.refuse(lambda value: value.__setitem__(key, 'short'))
        self.refuse(lambda value: value['expected_dependencies'].__setitem__('numpy', 'latest'))
        self.refuse(lambda value: value['fixture'].__setitem__('coordinate_unit', 'bohr'))
        self.refuse(lambda value: value['ordinary_origin']['array_identities'].pop('mo_coefficients'))
        self.refuse(lambda value: value['ordinary_origin']['arrays'].__setitem__('sha256', 'ab'*32))

    def test_all_original_array_final_and_comparison_thresholds_are_unchanged(self):
        for section in ('array_admission_thresholds', 'final_thresholds'):
            for key in self.value[section]: self.refuse(lambda value: value[section].__setitem__(key, 1.))
        self.refuse(lambda value: value['comparisons']['T05_same_density'].__setitem__('matrix_max_abs', 1e-6))

    def test_seed_angle_ids_recipe_raw_archives_and_zero_f_declaration_are_frozen(self):
        for key in ('source_record', 'source_arrays', 'seed_record', 'seed_arrays'):
            self.refuse(lambda value: value['seed_binding'][key].__setitem__('sha256', 'ab'*32))
            self.refuse(lambda value: value['seed_binding'][key].__setitem__('size_bytes', True))
        self.refuse(lambda value: value['seed_binding']['seed_density_ids'].reverse())
        self.refuse(lambda value: value['seed_binding']['recipe']['angles_rad'].reverse())
        self.refuse(lambda value: value['seed_binding']['recipe'].__setitem__('virtual_ao_anchor_0based', [4, 9]))
        self.refuse(lambda value: value['seed_binding'].__setitem__('native_F_preparation_calls', False))

    def test_all_critical_source_paths_are_required_relative_and_hash_bound(self):
        for path in execution.REQUIRED_SOURCE_FILES: self.refuse(lambda value: value['source_file_sha256'].pop(path))
        for path in ('../outside.py', './x.py', '/x.py', 'a//b.py', 'a\\b.py', 'C:/x.py'):
            self.refuse(lambda value: value['source_file_sha256'].__setitem__(path, 'ab'*32))
        self.refuse(lambda value: value['source_file_sha256'].__setitem__('extra.py', 'short'))

    def test_complete_commit_sha_json_load_and_nonfinite_payload_rejections(self):
        self.refuse(lambda value: value.__setitem__('runtime_test_commit', '029cd55'))
        self.refuse(lambda value: value.__setitem__('extra', float('nan')))
        self.refuse(lambda value: value.__setitem__('batch_id', '../old'))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/'contract.json'; target.write_text(json.dumps(self.value), encoding='utf-8')
            self.assertEqual(execution.load_execution_contract(target), self.value)
            target.write_text('{"schema_version":"a","schema_version":"b"}', encoding='utf-8')
            with self.assertRaises(ValueError): execution.load_execution_contract(target)

    def test_live_identity_has_authorization_inputs_profiles_and_separate_new_scope(self):
        identity = execution.execution_identity(contract_fixture(authorized=True), 'af'*32)
        prepared = {'policy_id': execution.POLICY, 'angles_rad': execution.ANGLES,
                    'seeds': [{'density_id': value} for value in execution.SEED_DENSITY_IDS]}
        self.assertTrue(execution.validate_response_journal_identity(identity, prepared_seeds=prepared, execution_kind=execution.EXECUTION_KIND))
        self.assertEqual(identity['profile_sha256'], execution.PROFILE_EXECUTED_RAW_SHA256)
        self.assertEqual(identity['profile_canonical_sha256'], execution.PROFILE_CANONICAL_SHA256)
        self.assertEqual(identity['source_file_identity_sha256'], execution.canonical_sha(self.value['source_file_sha256']))
        json.dumps(identity, allow_nan=False)

    def test_live_identity_false_auth_old_mode_source_or_prepared_ids_refuse(self):
        identity = execution.execution_identity(contract_fixture(authorized=True), 'af'*32)
        prepared = {'policy_id': execution.POLICY, 'angles_rad': execution.ANGLES,
                    'seeds': [{'density_id': value} for value in execution.SEED_DENSITY_IDS]}
        for key, bad in (('scientific_execution_authorized', False), ('scientific_execution_authorized', 1),
            ('mode', execution.immutable.EXECUTION_KIND), ('source_input_sha256', 'ab'*32),
            ('profile_sha256', execution.PROFILE_CANONICAL_SHA256), ('execution_contract_sha256', 'short')):
            invalid = dict(identity, **{key: bad})
            with self.assertRaises(execution.ExecutionContractError):
                execution.validate_response_journal_identity(invalid, prepared_seeds=prepared, execution_kind=execution.EXECUTION_KIND)
        prepared['seeds'][3]['density_id'] = 'ab'*32
        with self.assertRaises(execution.ExecutionContractError):
            execution.validate_response_journal_identity(identity, prepared_seeds=prepared, execution_kind=execution.EXECUTION_KIND)

    def test_fake_identity_explicitly_refuses_live_authorization_or_kind(self):
        self.assertTrue(execution.validate_response_journal_identity({'mode': 'ENGINEERING_FAKE'}, prepared_seeds={}, execution_kind='ENGINEERING_FAKE'))
        for extra in ({'scientific_execution_authorized': True}, {'scientific_execution_authorized': 0}, {'execution_kind': execution.EXECUTION_KIND}):
            with self.assertRaises(execution.ExecutionContractError):
                execution.validate_response_journal_identity({'mode': 'ENGINEERING_FAKE', **extra}, prepared_seeds={}, execution_kind='ENGINEERING_FAKE')


class OccupiedSpaceResponseByteBindingTests(unittest.TestCase):
    def setUp(self):
        self.source, self.record, self.arrays, self.source_arrays, anchors = binding_fixture()
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        for name, value in anchors.items(): self.stack.enter_context(patch.object(execution, name, value))
        self.value = contract_fixture()

    def bind(self, **kwargs):
        return execution.validate_seed_binding(self.value, kwargs.get('source', self.source),
            kwargs.get('record', self.record), kwargs.get('arrays', self.arrays),
            source_arrays_bytes=kwargs.get('source_arrays', self.source_arrays))

    def test_all_ten_prepared_and_six_source_members_byte_verify_without_recipe_or_f_calls(self):
        before = copy.deepcopy(self.value); result = self.bind()
        self.assertEqual(result['status'], 'PASS_SAVED_SOURCE_SEED_BYTES_ONLY')
        self.assertEqual(result['prepared_array_members_verified'], 10)
        self.assertEqual(result['source_array_members_verified'], 6)
        self.assertEqual(result['actual_numpy_recipe'], 'NOT_EXECUTED_WORKER_MUST_VERIFY')
        self.assertEqual(result['new_true_F_calls'], 0)
        self.assertEqual(self.value, before)
        self.assertIs(result['scientific_execution_authorized'], False)

    def test_optional_source_array_omission_is_explicitly_not_verified(self):
        result = self.bind(source_arrays=None)
        self.assertEqual(result['source_array_members_verified'], 0)
        self.assertEqual(result['source_array_bytes_status'], 'NOT_EXECUTED_WORKER_MUST_VERIFY')

    def test_actual_source_record_seed_record_and_both_archive_byte_tampering_refuses(self):
        for key, raw in (('source', self.source), ('record', self.record), ('arrays', self.arrays), ('source_arrays', self.source_arrays)):
            with self.subTest(key=key), self.assertRaises(execution.ExecutionContractError):
                self.bind(**{key: raw[:-1]+b'x'})
        with self.assertRaises(execution.ExecutionContractError): self.bind(source=bytearray(self.source))

    def test_modified_seed_declaration_is_rejected_even_under_local_test_reanchoring(self):
        record = json.loads(self.record); record['seeds'][0]['energy'] = -10.
        raw = _json_bytes(record, 13624)
        with patch.object(execution, 'SEED_RECORD_SHA256', _sha(raw)):
            self.value['seed_binding']['seed_record']['sha256'] = _sha(raw)
            with self.assertRaises(execution.ExecutionContractError): self.bind(record=raw)

    def test_array_headers_pickle_nonfinite_boolean_payload_and_duplicate_reference_refuse(self):
        zero = b'\0'*(14*14*8)
        self.assertEqual(execution._npy_payload(_npy(zero, [14, 14]), [14, 14], '<f8'), zero)
        for raw in (b'pickle', _npy(zero[:-8], [14, 14]), _npy(zero, [7, 28]),
            _npy(struct.pack('<d', float('inf'))+zero[8:], [14, 14])):
            with self.assertRaises(execution.ExecutionContractError): execution._npy_payload(raw, [14, 14], '<f8')
        with self.assertRaises(execution.ExecutionContractError):
            execution._npy_payload(_npy(b'\2'*196, [14, 14], '|b1'), [14, 14], '|b1')
        duplicate = execution._array_references(json.loads(self.record)); duplicate[1] = duplicate[0]
        with self.assertRaises(execution.ExecutionContractError): execution._archive_bytes(self.arrays, duplicate, 10)


class OccupiedSpaceRetainedByteIntegrationTests(unittest.TestCase):
    def test_retained_four_files_verify_all_sixteen_members_under_original_trust_anchors(self):
        """Mandatory saved-byte integration: missing mounted evidence fails."""
        declared = os.environ.get('AI4ORGCHEM_OCCUPIED_RESPONSE_INPUT_DIR')
        if declared:
            source_directory = seed_directory = Path(declared)
        else:
            # Local checkout companion delivery; portable container runs must
            # provide the read-only environment mount explicitly.
            retained = Path(__file__).resolve().parents[4]/'ai4orgchem-runtime-deliveries'/'20261007-user-molecule-occupied-space-admission'
            source_directory, seed_directory = retained/'seed-input', retained/'engineering-a2'/'output'
        result = execution.validate_seed_binding(contract_fixture(),
            (source_directory/'SOURCE.json').read_bytes(),
            (seed_directory/'prepared-seed-family.json').read_bytes(),
            (seed_directory/'prepared-seed-family.npz').read_bytes(),
            source_arrays_bytes=(source_directory/'source-arrays.npz').read_bytes())
        self.assertEqual(result['prepared_array_members_verified'], 10)
        self.assertEqual(result['source_array_members_verified'], 6)
        self.assertEqual([row['density_id'] for row in result['seed_record']['seeds']], list(execution.SEED_DENSITY_IDS))
        self.assertEqual(result['actual_numpy_recipe'], 'NOT_EXECUTED_WORKER_MUST_VERIFY')
        self.assertEqual(result['new_true_F_calls'], 0)


if __name__ == '__main__': unittest.main()
