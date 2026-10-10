"""Public archive-access refusal contracts, never historical-byte acceptance.

The original byte-acceptance suite belongs to the retained local archive. These
tests exercise missing/corrupt explicit archives and prove that the public
distribution neither substitutes current documents nor repairs old materials.
"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from runtime import historical_materials as history


class HistoricalArchiveAccessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def original_source_row(self):
        item = history.MATERIALS[0]
        return {'owner': item['owner'], 'path': item['original_path'],
                'commit': item['source_commit'], 'sha256': item['sha256']}

    def write_mapping(self):
        path = self.root/history.MANIFEST_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(history.expected_mapping(), ensure_ascii=False), encoding='utf-8')
        return path

    def bytes_before(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob('*') if path.is_file()}

    def test_all_default_readers_refuse_before_reading_files(self):
        calls = (lambda: history.load_historical_source_materials(),
                 lambda: history.verify_historical_source_materials(),
                 lambda: history.read_historical_source_material(self.original_source_row()))
        with patch.object(history, '_read', side_effect=AssertionError('Default reader accessed files')):
            for call in calls:
                with self.subTest(call=call), self.assertRaisesRegex(
                        history.HistoricalMaterialError, '^HISTORICAL_MATERIALS_LOCAL_ARCHIVE_ONLY$'):
                    call()

    def test_missing_explicit_archive_is_refused_without_creating_files(self):
        for call in (history.load_historical_source_materials,
                     history.verify_historical_source_materials):
            with self.subTest(call=call), self.assertRaises(history.HistoricalMaterialError):
                call(self.root)
        self.assertEqual(self.bytes_before(), {})

    def test_current_documents_are_not_substituted_for_archive_snapshots(self):
        self.write_mapping()
        for item in history.MATERIALS:
            path = self.root/item['original_path']
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('Current public guidance.\n', encoding='utf-8')
        before = self.bytes_before()
        with self.assertRaises(history.HistoricalMaterialError):
            history.verify_historical_source_materials(self.root)
        self.assertEqual(before, self.bytes_before())
        self.assertTrue(all(not (self.root/item['snapshot_path']).exists()
                            for item in history.MATERIALS))

    def test_corrupt_mapping_or_redirection_is_rejected_without_repair(self):
        path = self.write_mapping()
        for change in (lambda value: value['materials'][0].update(sha256='0'*64),
                       lambda value: value['materials'][0].update(snapshot_path='../../outside.md'),
                       lambda value: value.update(scientific_approval_granted=True)):
            value = history.expected_mapping()
            change(value)
            path.write_text(json.dumps(value), encoding='utf-8')
            before = self.bytes_before()
            with self.subTest(change=change), self.assertRaises(history.HistoricalMaterialError):
                history.verify_historical_source_materials(self.root)
            self.assertEqual(before, self.bytes_before())

    def test_corrupt_index_cannot_be_rebound_by_a_valid_mapping(self):
        self.write_mapping()
        path = self.root/history.SOURCE_INDEX_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'{"local_sources": []}\n')
        before = self.bytes_before()
        with self.assertRaisesRegex(history.HistoricalMaterialError, 'source-index Git blob binding differs'):
            history.verify_historical_source_materials(self.root)
        self.assertEqual(before, self.bytes_before())

    def test_reduced_snapshot_is_not_accepted_as_original_bytes(self):
        self.write_mapping()
        index = self.root/history.SOURCE_INDEX_PATH
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_bytes((history.ROOT/history.SOURCE_INDEX_PATH).read_bytes())
        for item in history.MATERIALS:
            path = self.root/item['snapshot_path']
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'Reduced public description is not the original archive.\n')
        before = self.bytes_before()
        with self.assertRaisesRegex(history.HistoricalMaterialError, 'Historical snapshot bytes differ'):
            history.verify_historical_source_materials(self.root)
        self.assertEqual(before, self.bytes_before())

    def test_linked_archive_component_is_refused_without_following_it(self):
        mapping = self.write_mapping()
        before = self.bytes_before()
        original = Path.is_symlink
        with patch.object(Path, 'is_symlink', lambda path: path == mapping or original(path)):
            with self.assertRaisesRegex(history.HistoricalMaterialError, 'contains a link'):
                history.verify_historical_source_materials(self.root)
        self.assertEqual(before, self.bytes_before())


if __name__ == '__main__':
    unittest.main()
