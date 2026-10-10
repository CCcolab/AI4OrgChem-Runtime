"""Stdlib evidence-reader tests; synthetic records never become science tests."""
import ast
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from runtime.propositions import core
from runtime.propositions.__main__ import main


class PropositionReaderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='proposition-reader-')
        self.base = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)

    def synthetic(self, raw=b'{"classification":"old-scoped","production_label":false}'):
        source = self.base/'source'
        source.mkdir(exist_ok=True)
        path = source/'evidence'/'P01'/'result.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        specs = [{'path': 'evidence/P01/result.json', 'sha256': hashlib.sha256(raw).hexdigest(),
                  'role': 'historical-result', 'item': 'P01', 'relation': 'HISTORICAL_DIAGNOSTIC'}]
        return source, path, specs

    def registry_copy(self):
        root = self.base/'runtime'
        for rel in ('locks/source.lock.json', 'locks/source-files.sha256.json', 'configs/propositions-v1.json'):
            path = root/rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((core.ROOT/rel).read_bytes())
        return root

    def test_catalog_has_exact_14_ids_and_no_general_replay_promise(self):
        result = core.list_propositions()
        self.assertEqual([r['id'] for r in result['cases']], ['P%02d'%i for i in range(1, 15)])
        self.assertTrue(all(r['capability']=='READ_FROZEN_EVIDENCE_ONLY' for r in result['cases']))
        self.assertEqual(result['source_status'], 'NOT_VERIFIED')
        self.assertEqual(result['scientific_validation'], 'NOT_EXECUTED')

    def test_p11_two_distinct_items_and_superseded_fixed_geometry_remain_separate(self):
        result = core.show_proposition('P11', include_content=False)
        self.assertEqual([r['id'] for r in result['catalog_entry']['items']], ['P11-A', 'P11-B'])
        files = result['files']
        self.assertEqual(sum(r['role']=='result' for r in files), 2)
        historical = next(r for r in files if r['path'].endswith('substituent-fixed-geometry-audit-result.json'))
        self.assertEqual(historical['relation'], 'HISTORICAL_SUPERSEDED_DIAGNOSTIC')
        self.assertEqual(sum(r['role']=='state-record' for r in files), 13)

    def test_p12_three_same_basis_ledgers_and_historical_not_current(self):
        result = core.show_proposition('P12', include_content=False)
        ledgers = [r for r in result['files'] if r['role']=='same-basis-ledger']
        self.assertEqual([r['item'] for r in ledgers], ['N12', 'N14', 'N16'])
        historical = next(r for r in result['files'] if r['path'].endswith('result-v0.3.1-historical.json'))
        self.assertEqual(historical['relation'], 'HISTORICAL_NOT_CURRENT_CLASSIFICATION')
        self.assertIsNone(result['new_scientific_verdict'])

    def test_p14_five_task_whitelist_has_no_dispatch_and_checkpoint_no_resume(self):
        result = core.show_proposition('P14', include_content=False)
        tasks = result['catalog_entry']['runtime_task_references']
        self.assertEqual([t['task'] for t in tasks], list(core.P14_TASKS))
        self.assertTrue(all(t['execution']=='NOT_STARTED_BY_THIS_READER' for t in tasks))
        self.assertIn('without resume', tasks[3]['scope'])
        historical = [r for r in result['files'] if r['relation']=='HISTORICAL_TECHNICAL_NOT_SCIENTIFIC_ENDPOINT']
        self.assertEqual(len(historical), 2)

    def test_p05_current_seven_angle_and_p07_audit_assets_are_registered(self):
        p05 = core.show_proposition('P05', include_content=False)['files']
        self.assertEqual(next(r for r in p05 if r['path'].endswith('/result.jsonl'))['relation'], 'HISTORICAL_ANCHOR')
        self.assertTrue(any(r['path'].endswith('/seven-angle-result.json') and r['role']=='current-result' for r in p05))
        p07 = core.show_proposition('P07', include_content=False)['files']
        self.assertTrue(any(r['path'].endswith('/same-hamiltonian-audit-result.json') for r in p07))

    def test_registry_paths_and_hashes_match_pinned_588_file_lock(self):
        registry, files, _ = core._catalog()
        self.assertEqual(len(files), 588)
        for case in registry['cases']:
            for row in case['assets']:
                self.assertEqual(files[row['path']], row['sha256'])
        self.assertEqual(core.SOURCE_COMMIT, '28511f3d84fa65707a107cde1e8121a7b4334ecb')

    def test_missing_explicit_source_never_guesses_cache_or_network(self):
        result = core.show_proposition('P01')
        self.assertEqual(result['status'], 'MISSING')
        self.assertEqual(result['exit_code'], 20)
        self.assertIsNone(result['source_directory'])
        self.assertTrue(all(r['actual_sha256'] is None and r['content'] is None for r in result['files']))
        self.assertFalse(result['full_source_tree_verified'])

    def test_unknown_or_noncanonical_ids_refuse(self):
        for value in ['P00', 'P15', 'p01', 'P1', '../P01', 'P01/result.json', '', None]:
            with self.subTest(value=value), self.assertRaises(core.CatalogError):
                core.show_proposition(value)

    def test_synthetic_old_result_is_read_verbatim_not_new_scientific_verdict(self):
        source, path, specs = self.synthetic()
        before = path.read_bytes()
        _, rows, _, status, code = core._inspect_assets(source, specs, include_content=True)
        self.assertEqual((status, code), ('VERIFIED_LOCKED_BYTES', 0))
        self.assertEqual(rows[0]['content'], {'classification':'old-scoped', 'production_label':False})
        self.assertEqual(rows[0]['relation'], 'HISTORICAL_DIAGNOSTIC')
        self.assertEqual(path.read_bytes(), before)

    def test_modified_bytes_are_not_decoded_and_exit40(self):
        source, path, specs = self.synthetic()
        path.write_bytes(b'changed private text must not be exported')
        _, rows, _, status, code = core._inspect_assets(source, specs, include_content=True)
        self.assertEqual((status, code), ('NOT_VERIFIED', 40))
        self.assertEqual(rows[0]['reason'], 'LOCKED_BYTES_MISMATCH')
        self.assertIsNone(rows[0]['content'])

    def test_missing_selected_file_is_missing_not_arithmetic_failure(self):
        source, path, specs = self.synthetic()
        path.unlink()
        _, rows, _, status, code = core._inspect_assets(source, specs, include_content=True)
        self.assertEqual((status, code), ('MISSING', 20))
        self.assertEqual(rows[0]['reason'], 'LOCAL_FILE_MISSING')

    def test_jsonl_rows_preserve_old_records(self):
        raw = b'{"tag":"old-one"}\n\n{"tag":"old-two"}\n'
        self.assertEqual(core._view(raw, '.jsonl'), ('jsonl', [{'tag':'old-one'}, {'tag':'old-two'}]))

    def test_duplicate_keys_nonfinite_and_invalid_utf8_are_refused(self):
        for raw in [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b'\xff']:
            with self.subTest(raw=raw), self.assertRaises(core.CatalogError):
                core._view(raw, '.json')

    def test_locked_legacy_infinity_is_preserved_as_exact_text_not_repaired(self):
        raw = b'{"old_initial_energy_change":Infinity,"production_label":false}\n'
        source, path, specs = self.synthetic(raw)
        _, rows, _, status, code = core._inspect_assets(source, specs, include_content=True)
        self.assertEqual((status, code), ('VERIFIED_LOCKED_BYTES', 0))
        self.assertEqual(rows[0]['content_kind'], 'legacy-json-text')
        self.assertEqual(rows[0]['content'], raw.decode('utf-8'))
        self.assertIn('NOT_NORMALIZED', rows[0]['content_parse_limitation'])
        self.assertEqual(path.read_bytes(), raw)
        with self.assertRaises(core.CatalogError):
            core._view(b'{"a":Infinity,"a":2}', '.json', allow_locked_legacy_nonfinite=True)

    def test_illegal_reference_paths_are_refused(self):
        for value in ['../secret', '/etc/passwd', 'C:/secret', 'a\\b', 'a//b', './a', 'a/../b', 'a\0b']:
            with self.subTest(value=value), self.assertRaises(core.CatalogError):
                core._file_path(self.base, value)

    def test_symlink_and_windows_reparse_ancestors_are_refused(self):
        source, path, _ = self.synthetic()
        original = Path.lstat
        for mode, attributes in [(stat.S_IFLNK, 0), (stat.S_IFDIR, 0x400)]:
            def altered(item, *args, **kwargs):
                if item == source/'evidence':
                    return SimpleNamespace(st_mode=mode, st_file_attributes=attributes)
                return original(item, *args, **kwargs)
            with self.subTest(mode=mode, attributes=attributes), patch.object(Path, 'lstat', altered), self.assertRaises(core.CatalogError):
                core._file_path(source, 'evidence/P01/result.json')

    def test_registry_path_tampering_cannot_reanchor_source_hash(self):
        root = self.registry_copy()
        path = root/'configs/propositions-v1.json'
        data = json.loads(path.read_bytes())
        data['cases'][0]['assets'][0]['path'] = '../outside.md'
        path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(core.CatalogError):
            core.list_propositions(runtime_root=root)

    def test_source_lock_tampering_is_refused(self):
        root = self.registry_copy()
        path = root/'locks/source-files.sha256.json'
        data = json.loads(path.read_bytes())
        data['evidence/P01-P14/P01/result.json'] = '0'*64
        path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(core.CatalogError):
            core.list_propositions(runtime_root=root)

    def test_p14_program_path_tampering_cannot_leave_the_whitelist(self):
        root = self.registry_copy()
        path = root/'configs/propositions-v1.json'
        data = json.loads(path.read_bytes())
        data['cases'][13]['runtime_task_references'][0]['script_path'] = '../command.ps1'
        path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(core.CatalogError):
            core.list_propositions(runtime_root=root)

    def test_p12_history_cannot_be_relabeled_as_current_evidence(self):
        root = self.registry_copy()
        path = root/'configs/propositions-v1.json'
        data = json.loads(path.read_bytes())
        historical = next(row for row in data['cases'][11]['assets'] if row['path'].endswith('result-v0.3.1-historical.json'))
        historical['relation'] = 'CURRENT'
        path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(core.CatalogError):
            core.list_propositions(runtime_root=root)

    def test_review_missing_source_creates_fresh_external_failure_receipt(self):
        output = self.base/'new-review'
        result = core.review_proposition('P01', output_dir=output)
        saved = json.loads((output/'review.public.json').read_bytes())
        self.assertEqual(saved, result)
        self.assertEqual(result['exit_code'], 20)
        self.assertEqual(result['scientific_validation'], 'NOT_EXECUTED')
        self.assertIsNone(result['new_scientific_verdict'])
        self.assertIn('MISSING', (output/'summary.md').read_text(encoding='utf-8'))

    def test_existing_output_is_never_overwritten(self):
        output = self.base/'prior'
        output.mkdir()
        sentinel = output/'review.public.json'
        sentinel.write_bytes(b'prior')
        with self.assertRaises(core.CatalogError):
            core.review_proposition('P01', output_dir=output)
        self.assertEqual(sentinel.read_bytes(), b'prior')

    def test_review_outputs_inside_source_or_runtime_are_refused(self):
        source, _, _ = self.synthetic()
        root = self.registry_copy()
        for output in [source/'new-review', root/'new-review']:
            with self.subTest(output=str(output)), self.assertRaises(core.CatalogError):
                core.review_proposition('P01', source_dir=source, output_dir=output, runtime_root=root)
            self.assertFalse(output.exists())

    def test_source_changed_between_view_and_export_creates_no_directory(self):
        source, path, specs = self.synthetic()
        result = core.show_proposition('P01', include_content=False)
        result['files'] = [{**specs[0], 'actual_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}]
        path.write_bytes(b'changed during read')
        output = self.base/'unwritten'
        with patch.object(core, 'show_proposition', return_value=result), self.assertRaises(core.CatalogError):
            core.review_proposition('P01', source_dir=source, output_dir=output)
        self.assertFalse(output.exists())

    def test_cli_unknown_id_returns40_without_creation(self):
        output = self.base/'refused'
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = main(['review', 'P15', '--output-dir', str(output), '--json'])
        self.assertEqual(code, 40)
        self.assertFalse(output.exists())

    def test_modules_have_no_science_network_subprocess_or_legacy_cli_import(self):
        prohibited = {'numpy','scipy','pyscf','socket','requests','urllib','http','subprocess'}
        for path in (core.ROOT/'runtime/propositions').glob('*.py'):
            tree = ast.parse(path.read_bytes())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertTrue(all(item.name.split('.')[0] not in prohibited for item in node.names))
                elif isinstance(node, ast.ImportFrom):
                    self.assertNotIn((node.module or '').split('.')[0], prohibited)
                    self.assertNotIn(node.module, ['runtime.cli', 'runtime.user_molecule'])


if __name__ == '__main__':
    unittest.main()
