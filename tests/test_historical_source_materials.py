"""Portable stdlib protection of two exact W05 historical source bindings."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from runtime import historical_materials as history


class HistoricalSourceMaterialTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.counter = 0

    def fixture(self):
        self.counter += 1
        root = self.base/str(self.counter); root.mkdir()
        for name in (history.MANIFEST_PATH, history.SOURCE_INDEX_PATH,
                     *(row['snapshot_path'] for row in history.MATERIALS)):
            target = root/name; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((history.ROOT/name).read_bytes())
        return root

    def change_manifest(self, root, mutation):
        value = json.loads((root/history.MANIFEST_PATH).read_bytes())
        mutation(value)
        (root/history.MANIFEST_PATH).write_bytes(json.dumps(value, ensure_ascii=False).encode('utf-8'))

    def test_both_real_retained_snapshots_have_exact_original_sha_blob_size_and_index_bindings(self):
        contents = history.load_historical_source_materials()
        receipt = history.verify_historical_source_materials()
        self.assertEqual(receipt['status'], 'PASS_EXACT_HISTORICAL_SOURCE_BYTES_ONLY')
        self.assertEqual(receipt['material_count'], 2)
        for item in history.MATERIALS:
            raw = contents[item['original_path']]
            self.assertEqual(len(raw), item['size_bytes'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), item['sha256'])
            self.assertEqual(history._blob_id(raw), item['git_blob_id'])
        self.assertEqual(receipt['source_index_blob_id'], history.INDEX_BLOB)

    def test_git_free_fixture_ignores_updated_current_docs_without_restoring_old_policy(self):
        root = self.fixture()
        for item in history.MATERIALS:
            current = root/item['original_path']; current.parent.mkdir(parents=True, exist_ok=True)
            current.write_text('Current guidance: consultation CANCELLED_BY_USER.\n', encoding='utf-8')
        before = {item['original_path']:(root/item['original_path']).read_bytes() for item in history.MATERIALS}
        contents = history.load_historical_source_materials(root)
        self.assertFalse((root/'.git').exists())
        self.assertNotEqual(contents, before)
        self.assertEqual(before, {name:(root/name).read_bytes() for name in before})
        receipt = history.verify_historical_source_materials(root)
        self.assertFalse(receipt['current_documents_replaced'])
        self.assertFalse(receipt['scientific_execution_authorized'])
        self.assertFalse(receipt['scientific_approval_granted'])
        self.assertEqual(receipt['current_process_status'], 'EXTERNAL_EXPERT_CONSULTATION_CANCELLED_BY_USER')

    def test_missing_manifest_index_or_snapshot_is_rejected_without_repair(self):
        for name in (history.MANIFEST_PATH, history.SOURCE_INDEX_PATH,
                     *(row['snapshot_path'] for row in history.MATERIALS)):
            with self.subTest(name=name):
                root = self.fixture(); path = root/name; path.unlink()
                with self.assertRaises(history.HistoricalMaterialError): history.verify_historical_source_materials(root)
                self.assertFalse(path.exists())

    def test_snapshot_same_length_tamper_is_rejected(self):
        for item in history.MATERIALS:
            with self.subTest(path=item['original_path']):
                root = self.fixture(); path = root/item['snapshot_path']; raw = path.read_bytes()
                path.write_bytes(bytes([raw[0]^1])+raw[1:])
                with self.assertRaises(history.HistoricalMaterialError): history.load_historical_source_materials(root)

    def test_snapshot_bom_or_eol_transform_is_not_accepted_as_exact_historical_bytes(self):
        for transform in (lambda raw:b'\xef\xbb\xbf'+raw, lambda raw:raw.replace(b'\n', b'\r\n')):
            root = self.fixture(); path = root/history.MATERIALS[0]['snapshot_path']
            path.write_bytes(transform(path.read_bytes()))
            with self.assertRaises(history.HistoricalMaterialError): history.verify_historical_source_materials(root)

    def test_original_path_or_snapshot_redirection_is_rejected(self):
        for key, wrong in (('original_path','docs/OTHER.md'), ('snapshot_path','../../outside.md')):
            root = self.fixture()
            self.change_manifest(root, lambda value:value['materials'][0].__setitem__(key, wrong))
            with self.assertRaises(history.HistoricalMaterialError): history.verify_historical_source_materials(root)

    def test_source_commit_and_git_blob_mismatch_are_rejected(self):
        for key, wrong in (('source_commit','1'*40), ('git_blob_id','2'*40), ('sha256','3'*64)):
            root = self.fixture()
            self.change_manifest(root, lambda value:value['materials'][0].__setitem__(key, wrong))
            with self.assertRaises(history.HistoricalMaterialError): history.verify_historical_source_materials(root)

    def test_mapping_source_index_path_commit_or_object_mismatch_are_rejected(self):
        for key, wrong in (('path','validation/OTHER.json'), ('record_commit','1'*40),
                           ('git_blob_id','2'*40), ('canonical_sha256','3'*64)):
            root = self.fixture()
            self.change_manifest(root, lambda value:value['source_index'].__setitem__(key, wrong))
            with self.assertRaises(history.HistoricalMaterialError): history.verify_historical_source_materials(root)

    def test_old_index_path_commit_or_hash_rebinding_is_rejected(self):
        for key, wrong in (('path','docs/OTHER.md'), ('commit','1'*40), ('sha256','2'*64)):
            root = self.fixture(); path = root/history.SOURCE_INDEX_PATH
            value = json.loads(path.read_bytes()); value['local_sources'][0][key] = wrong
            path.write_bytes(json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8'))
            with self.assertRaises(history.HistoricalMaterialError): history.verify_historical_source_materials(root)

    def test_caller_source_row_cannot_replace_old_owner_path_commit_hash_or_fields(self):
        source = {'owner':'runtime', 'path':history.MATERIALS[0]['original_path'],
                  'commit':history.SOURCE_COMMIT, 'sha256':history.MATERIALS[0]['sha256']}
        expected = history.load_historical_source_materials()[source['path']]
        self.assertEqual(history.read_historical_source_material(source), expected)
        for key, wrong in (('owner','science'), ('path','../outside.md'), ('commit','1'*40),
                           ('sha256','2'*64), ('extra',True)):
            changed = deepcopy(source); changed[key] = wrong
            with self.assertRaises(history.HistoricalMaterialError): history.read_historical_source_material(changed)

    def test_duplicate_json_nonfinite_type_confusion_or_approval_claim_is_rejected(self):
        for raw in (b'{"schema_version":"x","schema_version":"x"}', b'{"value":NaN}'):
            root = self.fixture(); (root/history.MANIFEST_PATH).write_bytes(raw)
            with self.assertRaises(history.HistoricalMaterialError): history.verify_historical_source_materials(root)
        for mutation in (lambda value:value['materials'][0].__setitem__('size_bytes',27759.),
                         lambda value:value.__setitem__('scientific_execution_authorized',True),
                         lambda value:value.__setitem__('scientific_approval_granted',0)):
            root = self.fixture(); self.change_manifest(root, mutation)
            with self.assertRaises(history.HistoricalMaterialError): history.verify_historical_source_materials(root)

    def test_linked_snapshot_or_parent_is_rejected_using_portable_filesystem_probe(self):
        root = self.fixture(); blocked = root/history.MATERIALS[0]['snapshot_path']
        original = Path.is_symlink
        with patch.object(Path, 'is_symlink', lambda path:path==blocked or original(path)):
            with self.assertRaises(history.HistoricalMaterialError): history.verify_historical_source_materials(root)
        blocked = blocked.parent
        with patch.object(Path, 'is_symlink', lambda path:path==blocked or original(path)):
            with self.assertRaises(history.HistoricalMaterialError): history.verify_historical_source_materials(root)


if __name__=='__main__': unittest.main()
