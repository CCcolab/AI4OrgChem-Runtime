"""Stdlib protection tests for exhaustive classification and execution receipts."""
from contextlib import redirect_stdout
import copy
import importlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('minimal_user_ci_under_test', ROOT/'scripts/ci-unit-user-molecule.py')
ci = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ci)


class FixedLoader:
    def __init__(self, suite): self.suite, self.calls = suite, 0
    def discover(self, directory, pattern):
        self.calls += 1
        return self.suite


class CiClassificationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.stage = Path(self.temporary.name)

    def fixture_root(self, names=('test_user_molecule_fixture.py',)):
        root = self.stage/'source'
        (root/'tests').mkdir(parents=True)
        (root/'scripts').mkdir()
        (root/'scripts/ci-unit-user-molecule.py').write_text('# synthetic runner identity\n', encoding='utf-8')
        for name in names: (root/'tests'/name).write_text('# synthetic test identity\n', encoding='utf-8')
        entries = tuple(ci._entry(name, 'MINIMAL', 'Synthetic receipt fixture, no imports.',
                                  'scripts/ci-unit-user-molecule.py') for name in names)
        return root, entries

    def test_all_33_existing_files_are_explicitly_classified_once_and_old_minimal_12_are_unchanged(self):
        result = ci.classify_test_files()
        actual = {path.name for path in (ROOT/'tests').glob('test_user_molecule_*.py')}
        names = [row['file'] for row in result['files']]
        self.assertEqual(len(actual), 33)
        self.assertEqual(len(names), len(set(names)), 33)
        self.assertEqual(set(names), actual)
        self.assertEqual(result['category_counts'], {'MINIMAL': 12, 'GUARDED': 12, 'LOCAL_ONLY': 9})
        self.assertEqual(tuple(row['file'] for row in result['files'] if row['category']=='MINIMAL'), ci.MINIMAL_PATTERNS)
        for row in result['files']:
            self.assertEqual(len(row['test_sha256']), 64)
            self.assertEqual(len(row['runner_sha256']), 64)
            if row['category'] != 'MINIMAL':
                self.assertTrue(row['requirements'])
                self.assertEqual(row['execution_here'], 'NOT_EXECUTED_HERE')

    def test_new_actual_file_without_a_classification_is_rejected(self):
        root, entries = self.fixture_root(('test_user_molecule_fixture.py', 'test_user_molecule_new.py'))
        with self.assertRaises(ci.ClassificationError) as error: ci.classify_test_files(root, entries[:1])
        self.assertEqual(error.exception.details['unclassified_files'], ['test_user_molecule_new.py'])

    def test_foreign_or_missing_declared_file_is_rejected(self):
        root, entries = self.fixture_root()
        extra = ci._entry('test_user_molecule_foreign.py', 'MINIMAL', 'Not an actual file.',
                          'scripts/ci-unit-user-molecule.py')
        with self.assertRaises(ci.ClassificationError) as error: ci.classify_test_files(root, entries+(extra,))
        self.assertEqual(error.exception.details['missing_files'], ['test_user_molecule_foreign.py'])

    def test_duplicate_declaration_is_not_silently_collapsed_by_a_set(self):
        root, entries = self.fixture_root()
        with self.assertRaises(ci.ClassificationError) as error: ci.classify_test_files(root, entries+entries)
        self.assertEqual(error.exception.details['duplicate_files'], ['test_user_molecule_fixture.py'])

    def test_bad_category_missing_reason_runner_escape_and_minimal_extra_requirements_are_rejected(self):
        root, entries = self.fixture_root()
        for key, value in (('category','UNCLASSIFIED'), ('reason',' '),
                           ('runner','scripts/../outside.py'), ('requirements',['numpy'])):
            with self.subTest(key=key):
                changed = copy.deepcopy(entries)
                changed[0][key] = value
                with self.assertRaises(ci.ClassificationError): ci.classify_test_files(root, changed)
        changed = copy.deepcopy(entries); changed[0]['extra'] = True
        with self.assertRaises(ci.ClassificationError): ci.classify_test_files(root, changed)

    def test_sealed_positive_integrations_are_explicit_local_only_not_remote_stdlib(self):
        rows = {row['file']:row for row in ci.classify_test_files()['files']}
        for name in ('test_user_molecule_occupation_response_contract.py',
                     'test_user_molecule_occupied_space_response_contract.py',
                     'test_user_molecule_occupied_space_response.py',
                     'test_user_molecule_occupied_space_root_contract.py'):
            self.assertEqual(rows[name]['category'], 'LOCAL_ONLY')
            self.assertTrue(any('sealed' in item for item in rows[name]['requirements']))
            self.assertTrue(rows[name]['runner'].startswith('scripts/ci-guard-'))

    def test_classification_failure_writes_fresh_audit_before_any_discovery(self):
        root, entries = self.fixture_root(('test_user_molecule_fixture.py', 'test_user_molecule_new.py'))
        output, loader = self.stage/'classification-failed', FixedLoader(unittest.TestSuite())
        with self.assertRaises(ci.ClassificationError):
            ci.run_minimal_ci(output, root=root, classifications=entries[:1], loader=loader)
        record = json.loads((output/'summary.json').read_text(encoding='utf-8'))
        self.assertEqual(record['status'], 'FAIL_ENGINEERING_ONLY')
        self.assertEqual(record['classification']['status'], 'FAIL')
        self.assertEqual(record['unit_test_ids'], [])
        self.assertEqual(record['unit_test_total'], 0)
        self.assertEqual(record['guard']['status'], 'NOT_INSTALLED')
        self.assertEqual(loader.calls, 0)

    def test_existing_output_is_preserved_and_source_output_is_forbidden(self):
        root, entries = self.fixture_root()
        output = self.stage/'old-output'; output.mkdir()
        sentinel = output/'summary.json'; sentinel.write_bytes(b'original record')
        for target in (output, root/'output'):
            with self.assertRaises(ValueError): ci.run_minimal_ci(target, root=root, classifications=entries)
        self.assertEqual(sentinel.read_bytes(), b'original record')
        self.assertFalse((root/'output').exists())

    def test_class_setup_failure_does_not_report_planned_test_ids_as_executed(self):
        class BeforeTestsFail(unittest.TestCase):
            @classmethod
            def setUpClass(cls): raise RuntimeError('synthetic class setup failed')
            def test_a(self): pass
            def test_b(self): pass
        root, entries = self.fixture_root()
        output = self.stage/'setup-failed'
        loader = FixedLoader(unittest.defaultTestLoader.loadTestsFromTestCase(BeforeTestsFail))
        with self.assertRaises(RuntimeError): ci.run_minimal_ci(output, root=root, classifications=entries, loader=loader)
        record = json.loads((output/'summary.json').read_text(encoding='utf-8'))
        self.assertEqual(len(record['planned_test_ids']), 2)
        self.assertEqual(record['unit_test_ids'], [])
        self.assertEqual(record['unit_test_total'], 0)
        self.assertEqual(record['groups'][0]['errors'], 1)
        self.assertEqual(record['guard']['status'], 'PASS')

    def test_interrupted_suite_records_only_the_test_that_actually_started(self):
        class Interrupted(unittest.TestCase):
            def test_a_interrupt(self): raise KeyboardInterrupt('synthetic interruption')
            def test_b_not_started(self): pass
        root, entries = self.fixture_root()
        output = self.stage/'interrupted'
        loader = FixedLoader(unittest.defaultTestLoader.loadTestsFromTestCase(Interrupted))
        with self.assertRaises(KeyboardInterrupt): ci.run_minimal_ci(output, root=root, classifications=entries, loader=loader)
        record = json.loads((output/'summary.json').read_text(encoding='utf-8'))
        self.assertEqual(record['status'], 'FAIL_ENGINEERING_ONLY')
        self.assertEqual(len(record['planned_test_ids']), 2)
        self.assertEqual(record['unit_test_total'], 1)
        self.assertEqual(len(record['unit_test_ids']), 1)
        self.assertIn('test_a_interrupt', record['unit_test_ids'][0])
        self.assertEqual(record['groups'][0]['status'], 'INCOMPLETE')

    def test_success_receipt_separates_planned_actual_and_deferred_files(self):
        class Success(unittest.TestCase):
            def test_one(self): self.assertTrue(True)
        root, entries = self.fixture_root()
        output = self.stage/'success'
        loader = FixedLoader(unittest.defaultTestLoader.loadTestsFromTestCase(Success))
        with redirect_stdout(io.StringIO()):
            record = ci.run_minimal_ci(output, root=root, classifications=entries, loader=loader)
        self.assertEqual(record['status'], 'PASS_ENGINEERING_ONLY')
        self.assertEqual(record['unit_test_total'], 1)
        self.assertEqual(record['unit_test_ids'], record['planned_test_ids'])
        self.assertEqual(record['classification']['files'][0]['execution_here'], 'PASS')
        self.assertEqual(record['guard']['status'], 'PASS')

    def test_import_guards_reject_cached_modules_and_detect_removed_binding(self):
        guard = ci.RejectScientificImports()
        original_import, original_module = __import__, importlib.import_module
        guard.install()
        try:
            self.assertEqual(guard.snapshot()['status'], 'PASS')
            with patch.dict(sys.modules, {'numpy':types.ModuleType('numpy')}):
                with self.assertRaises(AssertionError): __import__('numpy')
                with self.assertRaises(AssertionError): importlib.import_module('numpy')
            self.assertEqual(len(guard.attempts), 2)
            self.assertEqual(guard.snapshot()['status'], 'FAIL')
            sys.meta_path.remove(guard)
            self.assertIs(guard.snapshot()['held_bindings']['meta_path_finder'], False)
        finally: guard.close()
        self.assertIs(__import__, original_import)
        self.assertIs(importlib.import_module, original_module)


if __name__ == '__main__': unittest.main()
