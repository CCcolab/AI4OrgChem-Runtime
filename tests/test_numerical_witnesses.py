"""Saved-array verification and corrupt/mismatched evidence refusal; no engines."""
import contextlib
import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('numerical_witness_audit', REPOSITORY/'scripts/audit-numerical-witnesses.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
np = audit.np
PACKAGE = REPOSITORY/'evidence/numerical-witnesses'


def write_json(path, record):
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


@contextlib.contextmanager
def package_copy():
    with tempfile.TemporaryDirectory() as directory:
        package = Path(directory)/'package'
        shutil.copytree(PACKAGE, package)
        yield package


def rehash_entry(package, entry):
    path = package/entry['path']
    entry.update(size_bytes=path.stat().st_size, sha256=audit.sha256(path))


def change_snapshot(package, change):
    manifest = audit.strict_json(package/'manifest.json')
    witness = manifest['witnesses']['conditional-ethene-v2']
    path = package/witness['files']['record']['path']
    snapshot = audit.strict_json(path)
    change(snapshot)
    write_json(path, snapshot)
    rehash_entry(package, witness['files']['record'])
    write_json(package/'manifest.json', manifest)


def changed_conditional_array(package, name, change):
    """Refresh declared hashes too, so tests reach semantic consistency checks."""
    manifest = audit.strict_json(package/'manifest.json')
    witness = manifest['witnesses']['conditional-ethene-v2']
    path = package/witness['files']['arrays']['path']
    with np.load(path, allow_pickle=False) as archive:
        arrays = {key: archive[key].copy() for key in archive.files}
    change(arrays[name])
    np.savez_compressed(path, **arrays)
    new_hash = audit.member_sha256(arrays[name])
    witness['array_members'][name]['sha256'] = new_hash
    witness['array_members'][name]['source']['original_member_sha256'] = new_hash
    rehash_entry(package, witness['files']['arrays'])
    record_path = package/witness['files']['record']['path']
    record = audit.strict_json(record_path)
    record['arrays'] = witness['array_members']
    if name == 'density':
        record['returned_density_binding']['result_density_member_sha256'] = new_hash
        record['returned_density_binding']['evaluation_requested_density_member_sha256'] = new_hash
    write_json(record_path, record)
    rehash_entry(package, witness['files']['record'])
    write_json(package/'manifest.json', manifest)


class NumericalWitnessTests(unittest.TestCase):
    def test_real_saved_arrays_pass_and_audit_is_read_only(self):
        before = {p.relative_to(PACKAGE).as_posix(): audit.sha256(p) for p in PACKAGE.rglob('*') if p.is_file()}
        result = audit.audit_package(PACKAGE)
        after = {p.relative_to(PACKAGE).as_posix(): audit.sha256(p) for p in PACKAGE.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(result['audit_status'], 'PASS_READ_ONLY_NUMPY_AUDIT')
        self.assertAlmostEqual(result['witnesses']['ordinary-water']['electron_number'], 10., places=10)
        conditional = result['witnesses']['conditional-ethene-v2']
        self.assertEqual(conditional['endpoint_qualification'], 'REJECTED')
        self.assertFalse(conditional['numpy_array_diagnostic']['checks']['raw_gap_numpy'])
        self.assertFalse(conditional['numpy_array_diagnostic']['exact_scipy_subspace_reproduction_claimed'])
        self.assertEqual(conditional['electron_counts']['grid_status'], 'NOT_RECOMPUTED_NO_GRID_PAYLOAD')
        self.assertTrue(all(count == 0 for count in result['new_scientific_calls'].values()))

    def test_corrupt_npz_bytes_are_rejected(self):
        with package_copy() as package:
            path = package/'conditional-ethene-v2/returned-endpoint.npz'
            data = bytearray(path.read_bytes())
            data[-20] ^= 1
            path.write_bytes(data)
            with self.assertRaisesRegex(ValueError, 'Payload SHA-256 mismatch'):
                audit.audit_package(package)

    def test_rehashed_density_mismatch_is_rejected_by_identity(self):
        with package_copy() as package:
            changed_conditional_array(package, 'density', lambda array: array.__setitem__((0, 0), array[0, 0]+.01))
            with self.assertRaisesRegex(ValueError, 'true evaluation identity mismatch'):
                audit.audit_package(package)

    def test_wrong_true_evaluation_density_id_is_rejected(self):
        with package_copy() as package:
            change_snapshot(package, lambda record: record['returned_density_binding'].__setitem__('requested_density_id', '0'*64))
            with self.assertRaisesRegex(ValueError, 'true evaluation identity mismatch'):
                audit.audit_package(package)

    def test_rehashed_energy_mismatch_is_rejected(self):
        with package_copy() as package:
            change_snapshot(package, lambda record: record['energy_ledger'].__setitem__('total_energy', record['energy_ledger']['total_energy']+.001))
            with self.assertRaisesRegex(ValueError, 'Conditional total ledger'):
                audit.audit_package(package)

    def test_rehashed_operator_mismatch_is_rejected(self):
        with package_copy() as package:
            changed_conditional_array(package, 'coulomb', lambda array: array.__setitem__((0, 0), array[0, 0]+.01))
            with self.assertRaisesRegex(ValueError, 'raw_G_assembly'):
                audit.audit_package(package)

    def test_original_ordinary_energy_mismatch_is_rejected(self):
        record = audit.strict_json(PACKAGE/'ordinary-water/result.json')
        with np.load(PACKAGE/'ordinary-water/orbitals-density.npz', allow_pickle=False) as archive:
            arrays = {key: archive[key] for key in archive.files}
        record['total_energy_hartree'] += .001
        with self.assertRaisesRegex(ValueError, 'Ordinary energy closure'):
            audit.audit_ordinary(record, arrays)

    def test_recursive_descriptors_reject_shape_dtype_and_member_hash(self):
        manifest = audit.strict_json(PACKAGE/'manifest.json')
        descriptor = manifest['witnesses']['conditional-ethene-v2']['array_members']['density']
        with np.load(PACKAGE/'conditional-ethene-v2/returned-endpoint.npz', allow_pickle=False) as archive:
            for key, bad_value in [('shape', [13, 14]), ('dtype', '<f4'), ('sha256', '0'*64)]:
                with self.subTest(field=key):
                    bad = copy.deepcopy(descriptor)
                    bad[key] = bad_value
                    with self.assertRaises(ValueError):
                        audit.decode_arrays({'nested': [{'density': bad}]}, archive)

    def test_object_arrays_cannot_be_unpickled(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'object.npz'
            np.savez(path, object=np.array([{'unexpected': 'object'}], dtype=object))
            with np.load(path, allow_pickle=False) as archive:
                with self.assertRaisesRegex(ValueError, 'Object arrays cannot be loaded'):
                    audit.decode_arrays({'npz_member': 'object', 'shape': [1], 'dtype': '|O', 'sha256': '0'*64}, archive)

    def test_scientific_imports_are_refused(self):
        with audit.numerical_only_imports():
            for name in audit.FORBIDDEN_IMPORTS:
                with self.subTest(module=name):
                    with self.assertRaisesRegex(ImportError, 'forbids'):
                        __import__(name)

    def test_duplicate_json_and_nonfinite_values_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'bad.json'
            for value in ('{"value":1,"value":2}', '{"value":NaN}', '{"nested":[1e400]}'):
                with self.subTest(value=value):
                    path.write_text(value, encoding='utf-8')
                    with self.assertRaises(ValueError):
                        audit.strict_json(path)

    def test_parent_binding_corruption_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = audit.strict_json(PACKAGE/'manifest.json')
            for entry in manifest['public_parent_records']:
                target = root/entry['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(REPOSITORY/entry['path'], target)
            path = root/manifest['public_parent_records'][0]['path']
            path.write_bytes(path.read_bytes()+b' ')
            with self.assertRaisesRegex(ValueError, 'Payload size mismatch'):
                audit.audit_package(PACKAGE, root)

    def test_payload_path_escape_is_rejected(self):
        with package_copy() as package:
            manifest = audit.strict_json(package/'manifest.json')
            manifest['witnesses']['ordinary-water']['files']['arrays']['path'] = '../escaped.npz'
            write_json(package/'manifest.json', manifest)
            with self.assertRaisesRegex(ValueError, 'escapes package'):
                audit.audit_package(package)


if __name__ == '__main__':
    unittest.main()
