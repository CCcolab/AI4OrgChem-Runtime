"""Saved-family loader checks; no worker main or scientific native callback."""
import copy
import hashlib
import importlib.util
import io
from pathlib import Path
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('occupied_space_worker_loader',
    ROOT/'scripts/diagnose-user-molecule-occupied-space-response-worker.py')
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)


class OccupiedSpaceWorkerLoaderTests(unittest.TestCase):
    def fixture(self):
        arrays = {'array_'+str(i): np.full((2, 2), float(i)) for i in range(10)}
        record = {'arrays': [{'npz_member': name, 'shape': list(array.shape), 'dtype': array.dtype.str,
            'sha256': hashlib.sha256(array.tobytes()).hexdigest()} for name, array in arrays.items()],
            'raw_array_archive': {'file': 'saved.npz'}, 'F_at_new_density': None}
        return record, arrays

    @staticmethod
    def archive(arrays):
        stream = io.BytesIO()
        np.savez(stream, **arrays)
        return stream.getvalue()

    def test_restores_exact_saved_arrays_readonly_and_discards_only_archive_metadata(self):
        record, arrays = self.fixture()
        saved = worker.load_saved_family(record, self.archive(arrays))
        self.assertNotIn('raw_array_archive', saved)
        self.assertIsNone(saved['F_at_new_density'])
        for restored, original in zip(saved['arrays'], arrays.values()):
            np.testing.assert_array_equal(restored, original)
            self.assertFalse(restored.flags.writeable)
            self.assertFalse(np.shares_memory(restored, original))

    def test_changed_payload_or_declared_shape_and_dtype_are_refused(self):
        baseline, arrays = self.fixture()
        for field, replacement in (('shape', [4, 1]), ('dtype', '>f8'), ('sha256', 'e'*64)):
            record = copy.deepcopy(baseline)
            record['arrays'][0][field] = replacement
            with self.subTest(field=field), self.assertRaises(ValueError):
                worker.load_saved_family(record, self.archive(arrays))
        arrays['array_0'][0, 0] = 999
        with self.assertRaises(ValueError): worker.load_saved_family(baseline, self.archive(arrays))

    def test_missing_unused_or_reused_npy_members_are_refused(self):
        record, arrays = self.fixture()
        missing = dict(arrays); missing.pop('array_0')
        unused = dict(arrays, extra=np.zeros((2, 2)))
        repeated = copy.deepcopy(record); repeated['arrays'][1] = copy.deepcopy(repeated['arrays'][0])
        for metadata, payload in ((record, missing), (record, unused), (repeated, arrays)):
            with self.subTest(members=len(payload)), self.assertRaises(ValueError):
                worker.load_saved_family(metadata, self.archive(payload))

    def test_nonfinite_integer_object_and_big_endian_payloads_are_refused(self):
        record, baseline = self.fixture()
        for value in (np.full((2, 2), np.nan), np.zeros((2, 2), dtype=int),
                      np.zeros((2, 2), dtype=object), np.zeros((2, 2), dtype='>f8')):
            arrays = dict(baseline, array_0=value)
            with self.subTest(dtype=value.dtype), self.assertRaises(ValueError):
                worker.load_saved_family(record, self.archive(arrays))


class OccupiedSpaceWorkerPlatformTests(unittest.TestCase):
    def fixture(self):
        rows = ['1 0 0:1 / / ro - overlay overlay ro',
            '2 1 0:2 / /workspace ro - 9p source ro',
            '3 1 0:3 / /saved-ordinary ro - 9p cache ro',
            '4 1 0:4 / /seed-input ro - 9p seeds ro',
            '5 1 0:5 / /execution-contract.json ro - 9p contract ro']
        return dict(roots={'root_filesystem': '/', 'runtime_source': '/workspace',
            'science_source': '/opt/ai4orgchem', 'ordinary_cache': '/saved-ordinary',
            'seed_input': '/seed-input', 'execution_contract': '/execution-contract.json'},
            mountinfo_text='\n'.join(rows),
            ipv4_route_text='Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT\n',
            ipv6_interfaces_text='00000000000000000000000000000001 01 80 10 80 lo\n', euid=10001, egid=10001)

    def test_actual_mount_fixture_and_loopback_only_snapshot_pass_without_scientific_calls(self):
        result = worker.platform_preflight(**self.fixture())
        self.assertEqual(result['status'], 'PASS_ACTUAL_PLATFORM_PREFLIGHT')
        self.assertEqual(result['read_only_paths']['science_source']['mount_point'], '/')
        self.assertEqual(result['read_only_paths']['runtime_source']['mount_point'], '/workspace')
        self.assertEqual(result['new_scientific_calls'], 0)
        self.assertFalse(result['scientific_callback_journal_created'])

    def test_root_or_wrong_group_is_refused_before_scientific_entry(self):
        for change in ({'euid': 0}, {'egid': 0}, {'euid': True}):
            fixture = dict(self.fixture(), **change)
            with self.subTest(change=change):
                result = worker.platform_preflight(**fixture)
                self.assertEqual(result['status'], 'BLOCKED_PLATFORM_PREFLIGHT')
                self.assertEqual(result['new_scientific_calls'], 0)

    def test_longest_rw_bind_refuses_even_when_parent_root_is_ro(self):
        fixture = self.fixture()
        fixture['mountinfo_text'] = fixture['mountinfo_text'].replace(
            '4 1 0:4 / /seed-input ro - 9p seeds ro', '4 1 0:4 / /seed-input rw - 9p seeds rw')
        result = worker.platform_preflight(**fixture)
        self.assertEqual(result['status'], 'BLOCKED_PLATFORM_PREFLIGHT')
        self.assertIn('ACTUAL_READONLY_MOUNT_REFUSED_SEED_INPUT', result['reasons'])
        ambiguous = self.fixture()
        ambiguous['mountinfo_text'] += '\n6 1 0:6 / /seed-input rw - 9p seeds rw'
        result = worker.platform_preflight(**ambiguous)
        self.assertEqual(result['status'], 'BLOCKED_PLATFORM_PREFLIGHT')
        self.assertIn('ACTUAL_READONLY_MOUNT_AMBIGUOUS_SEED_INPUT', result['reasons'])

    def test_nonloopback_ipv4_route_or_ipv6_interface_is_refused(self):
        for name, row in (('ipv4_route_text', 'eth0 00000000 0100000A 0003 0 0 0 00000000 0 0 0\n'),
                          ('ipv6_interfaces_text', 'fe800000000000000000000000000001 02 40 20 80 eth0\n')):
            fixture = self.fixture(); fixture[name] += row
            with self.subTest(view=name):
                result = worker.platform_preflight(**fixture)
                self.assertEqual(result['status'], 'BLOCKED_PLATFORM_PREFLIGHT')
                self.assertTrue(any('NONLOOPBACK' in reason for reason in result['reasons']))

    def test_unknown_mount_or_malformed_route_view_cannot_become_a_pass(self):
        for change in ({'mountinfo_text': ''}, {'mountinfo_text': 'not a mountinfo row'},
                       {'ipv4_route_text': ''}, {'ipv6_interfaces_text': 'invalid IPv6 row'}):
            with self.subTest(change=change):
                result = worker.platform_preflight(**dict(self.fixture(), **change))
                self.assertEqual(result['status'], 'BLOCKED_PLATFORM_PREFLIGHT')
                self.assertFalse(result['scientific_callback_journal_created'])


if __name__ == '__main__':
    unittest.main()
