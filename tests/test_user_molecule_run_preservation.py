"""CLI run-directory preservation, using only synthetic records and stdlib.

Set AI4ORGCHEM_PRESERVATION_TEST_STAGE to keep all temporary fixtures beneath
an engineering delivery directory. No existing run or scientific engine is used.
"""
import builtins
from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from runtime.user_molecule import __main__ as cli
from runtime.user_molecule.records import manifest


TEST_STAGE = Path(os.environ.get(
    'AI4ORGCHEM_PRESERVATION_TEST_STAGE',
    str(Path(tempfile.gettempdir()) / 'ai4orgchem-run-preservation-tests')))


@contextmanager
def reject_scientific_imports():
    """Make accidental science imports fail even when modules are installed."""
    original_import = builtins.__import__
    attempts = []

    def guarded_import(name, *args, **kwargs):
        if name.split('.')[0] in ('ai4orgchem', 'pyscf', 'numpy'):
            attempts.append(name)
            raise AssertionError('Scientific import attempted: ' + name)
        return original_import(name, *args, **kwargs)

    with patch('builtins.__import__', side_effect=guarded_import):
        yield attempts


class RunPreservationTests(unittest.TestCase):
    def setUp(self):
        self.stage = (TEST_STAGE / 'temporary-runs').resolve()
        self.stage.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(
            prefix='run-preservation-', dir=self.stage)
        self.root = Path(self.temporary.name).resolve()
        self.assertNotEqual(self.root, self.stage)
        self.assertTrue(self.root.is_relative_to(self.stage))
        self.addCleanup(self.cleanup_temporary)
        self.request = self.root / 'invalid request.json'
        # strict_json fails before jsonschema or any scientific dependency.
        self.request.write_bytes(b'{"broken":')

    def cleanup_temporary(self):
        target = Path(self.temporary.name).resolve()
        if target == self.stage or not target.is_relative_to(self.stage):
            raise AssertionError('Temporary cleanup target escaped its test stage')
        self.temporary.cleanup()

    @staticmethod
    def seed(directory, entries):
        directory.mkdir(parents=True, exist_ok=True)
        for relative, contents in entries.items():
            path = directory / relative
            if contents is None:
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(contents)

    @staticmethod
    def snapshot(directory):
        """Include empty directories, names, and exact bytes, not just hashes."""
        return {
            path.relative_to(directory).as_posix():
                ('directory', None) if path.is_dir() else ('file', path.read_bytes())
            for path in sorted(directory.rglob('*'))
        }

    @staticmethod
    def invoke(*arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, 'argv', ['runtime.user_molecule', *map(str, arguments)]), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            code = cli.main()
        return code, stdout.getvalue(), stderr.getvalue()

    @contextmanager
    def forbid_input_and_science(self):
        original_load = cli.load
        schema_reads = []
        schemas = (cli.ROOT / 'schemas').resolve()

        def guarded_load(path):
            if Path(path).resolve().is_relative_to(schemas):
                schema_reads.append(str(path))
                raise AssertionError('Input schema read before run-directory refusal')
            return original_load(path)

        with ExitStack() as stack:
            guards = [stack.enter_context(patch.object(
                cli, name, side_effect=AssertionError(name + ' must not run')))
                for name in ('read_request', 'verify_source', 'identity',
                             'observations', 'validate')]
            stack.enter_context(patch.object(cli, 'load', side_effect=guarded_load))
            imports = stack.enter_context(reject_scientific_imports())
            yield
            for guard in guards:
                guard.assert_not_called()
            self.assertEqual(schema_reads, [])
            self.assertEqual(imports, [])

    def assert_refused_without_mutation(self, directory, action):
        before = self.snapshot(directory)
        arguments = [action, '--request', self.request, '--output-dir', directory]
        if action == 'compute':
            arguments += ['--check-run', self.root / 'unavailable prior check']
        with self.forbid_input_and_science():
            code, _, stderr = self.invoke(*arguments)
        self.assertEqual(code, 40)
        self.assertTrue(stderr.strip(), 'Refusal should explain why the run was rejected')
        self.assertEqual(self.snapshot(directory), before)

    def test_completed_check_retry_preserves_original_evidence(self):
        directory = self.root / 'old check'
        self.seed(directory, {
            'preflight.json': b'{"input_status":"VALID","compute_eligible":false}\r\n',
            'report.md': '# original check report\r\n原始证据\r\n'.encode('utf-8'),
            'input/request.original.json': b'{ "original": true }\r\n',
            'input/request.normalized.json': b'{"original":true}',
            'input/molecule.xyz': b'1\noriginal geometry\nC 0 0 0\n',
            'runtime-progress.json': b'{"stage":"INPUT_CHECK_COMPLETED"}\n',
            'run-manifest.json': b'{ "historical_receipt": "retain exact bytes" }\n',
            'diagnostics/empty': None,
            'diagnostics/original.bin': b'\x00\xffunchanged\r\n',
        })
        for action in ('check', 'compute'):
            with self.subTest(action=action):
                self.assert_refused_without_mutation(directory, action)

    def test_individual_service_records_prevent_reuse(self):
        fixtures = {
            'preflight-only': {'preflight.json': b'{ "original": "preflight" }\n'},
            'result-only': {'result.json': b'{ "original": "result" }\r\n'},
            'error-only': {'error.json': b'{ "original": "failure" }\r\n'},
            'report-only': {'report.md': '原始简报\r\n'.encode('utf-8')},
            'empty-input': {'input': None},
            'input-only': {'input/request.original.json': b'original request\r\n'},
            'run-manifest-only': {'run-manifest.json': b'{"original":"manifest"}\n'},
            'progress-only': {'runtime-progress.json': b'{"stage":"FAILED"}\n'},
            'acceptance-manifest-only': {'manifest.json': b'{"original":"acceptance"}\n'},
        }
        for fixture, entries in fixtures.items():
            for action in ('check', 'compute'):
                with self.subTest(fixture=fixture, action=action):
                    directory = self.root / fixture / action
                    self.seed(directory, {
                        **entries, 'original logs/空目录': None,
                        'original logs/stderr.log': b'original diagnostic\r\n',
                    })
                    self.assert_refused_without_mutation(directory, action)

    def test_finished_host_log_only_runs_prevent_reuse(self):
        hosts = [
            {'status': 'FAILED'}, {'status': 'BLOCKED'}, {'status': 'COMPLETED'},
            {'status': 'RUNNING', 'finished_utc': '2000-01-01T00:00:00+00:00'},
        ]
        for index, host in enumerate(hosts):
            for action in ('check', 'compute'):
                with self.subTest(host=host, action=action):
                    directory = self.root / ('host-' + str(index)) / action
                    self.seed(directory, {
                        'host-execution.json': json.dumps(host).encode('utf-8'),
                        'execution.json': b'{"supervisor":"historical fixture"}\n',
                        'docker-stderr.log': b'container never started\r\n',
                    })
                    self.assert_refused_without_mutation(directory, action)

    def assert_new_input_failure(self, directory):
        with reject_scientific_imports() as imports, \
                patch.object(cli, 'verify_source') as source:
            code, _, stderr = self.invoke(
                'check', '--request', self.request, '--output-dir', directory)
        self.assertEqual(code, 10)
        self.assertEqual(imports, [])
        source.assert_not_called()
        self.assertIn('invalid UTF-8 JSON', stderr)
        error = json.loads((directory / 'error.json').read_text(encoding='utf-8'))
        self.assertEqual(error['error_type'], 'InputError')
        self.assertEqual(error['exit_code'], 10)
        self.assertIn('invalid UTF-8 JSON', error['message'])
        receipt = json.loads((directory / 'run-manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(receipt['action'], 'check')
        self.assertEqual(receipt['execution_status'], 'FAILED')
        self.assertEqual(receipt['numerical_status'], 'NOT_EXECUTED')
        self.assertEqual(receipt['exit_code'], 10)
        self.assertIn('runtime-progress.json', receipt['files'])
        self.assertIn('error.json', receipt['files'])
        for relative, identity in receipt['files'].items():
            raw = (directory / relative).read_bytes()
            self.assertEqual(identity['size_bytes'], len(raw), relative)
            self.assertEqual(identity['sha256'], hashlib.sha256(raw).hexdigest(), relative)
        self.assertFalse((directory / 'result.json').exists())
        return error

    def test_new_run_input_failure_retains_diagnostic_and_failed_manifest(self):
        directory = self.root / 'new run'
        self.assertFalse(directory.exists())
        self.assert_new_input_failure(directory)
        self.assert_refused_without_mutation(directory, 'check')

    def test_initial_supervision_records_allow_first_run_and_are_preserved(self):
        for status in ('CREATED', 'RUNNING'):
            with self.subTest(status=status):
                directory = self.root / ('initial ' + status)
                self.seed(directory, {
                    'host-execution.json': json.dumps({
                        'status': status, 'finished_utc': None,
                        'container_id': None}).encode('utf-8'),
                    'execution.json': b'{"supervisor":"initial fixture"}\n',
                    'docker-stderr.log': b'',
                    'supervisor/empty': None,
                })
                before = self.snapshot(directory)
                self.assert_new_input_failure(directory)
                after = self.snapshot(directory)
                for relative, original in before.items():
                    self.assertEqual(after[relative], original, relative)

    def test_failed_first_progress_write_does_not_create_failure_records(self):
        directory = self.root / 'write failure'
        self.seed(directory, {'execution.json': b'{"supervisor":"initial"}\n'})
        before = self.snapshot(directory)
        with self.forbid_input_and_science(), \
                patch.object(cli, 'save', side_effect=OSError('synthetic progress write failure')) as save, \
                patch.object(cli, 'manifest') as create_manifest:
            code, _, stderr = self.invoke(
                'check', '--request', self.request, '--output-dir', directory)
        self.assertEqual(code, 40)
        self.assertIn('synthetic progress write failure', stderr)
        save.assert_called_once()
        self.assertEqual(Path(save.call_args.args[0]), directory / 'runtime-progress.json')
        create_manifest.assert_not_called()
        self.assertEqual(self.snapshot(directory), before)

    def test_report_of_early_input_failure_is_successful_and_read_only(self):
        directory = self.root / 'input failure for report'
        error = self.assert_new_input_failure(directory)
        before = self.snapshot(directory)
        with self.forbid_input_and_science(), \
                patch.object(cli, 'save', side_effect=AssertionError('Report tried to save')) as save, \
                patch.object(cli, 'manifest', side_effect=AssertionError('Report tried to manifest')) as create_manifest:
            code, stdout, _ = self.invoke('report', '--run-directory', directory)
        # Parsing failed before a request snapshot was possible. The manifest
        # nevertheless accounts for every record this run actually produced.
        self.assertEqual(code, 0)
        self.assertIn(error['message'], stdout)
        self.assertIn('记录完整性：MATCHED', stdout)
        self.assertIn('执行状态：FAILED', stdout)
        self.assertIn('原运行退出码：10', stdout)
        self.assertIn('本次未生成规范请求快照', stdout)
        self.assertTrue(stdout.strip())
        save.assert_not_called()
        create_manifest.assert_not_called()
        self.assertEqual(self.snapshot(directory), before)

    def test_report_of_complete_failed_run_is_successful_and_read_only(self):
        directory = self.root / 'complete failed run for report'
        message = 'Synthetic post-input failure; preservation fixture only'
        self.seed(directory, {
            'error.json': json.dumps({'error_type': 'InputError',
                                     'message': message, 'exit_code': 11}).encode('utf-8'),
            'input/request.normalized.json': json.dumps({
                'research_question': 'Failed run preservation test',
                'calculation_profile': 'pilot-b3lypg-sto3g-grid2-v1',
                'fragments': []}).encode('utf-8'),
            'runtime-progress.json': b'{"stage":"INPUT_CHECK","scf_executed":false}\n',
            'report.md': b'Original failure report.\r\n',
        })
        manifest(directory, action='check', execution_status='FAILED',
                 numerical_status='NOT_EXECUTED', exit_code=11)
        before = self.snapshot(directory)
        with self.forbid_input_and_science(), \
                patch.object(cli, 'save', side_effect=AssertionError('Report tried to save')) as save, \
                patch.object(cli, 'manifest', side_effect=AssertionError('Report tried to manifest')) as create_manifest:
            code, stdout, _ = self.invoke('report', '--run-directory', directory)
        self.assertEqual(code, 0)
        self.assertIn(message, stdout)
        self.assertIn('Failed run preservation test', stdout)
        save.assert_not_called()
        create_manifest.assert_not_called()
        self.assertEqual(self.snapshot(directory), before)

    def test_report_of_check_receipt_preserves_input_and_old_report(self):
        directory = self.root / 'check receipt for report'
        self.seed(directory, {
            'preflight.json': json.dumps({
                'schema_version': 1, 'input_status': 'VALID', 'compute_eligible': False,
                'method_status': 'NOT_REVIEWED', 'reasons': ['SYNTHETIC_CHECK_ONLY'],
                'inspection': {}, 'resources': {}, 'identities': {},
                'atom_mapping': []}).encode('utf-8'),
            'input/request.normalized.json': json.dumps({
                'research_question': 'Preservation test question',
                'calculation_profile': 'pilot-b3lypg-sto3g-grid2-v1',
                'fragments': []}).encode('utf-8'),
            'report.md': b'Old saved report must retain its exact bytes.\r\n',
            'runtime-progress.json': b'{"stage":"INPUT_CHECK_COMPLETED","scf_executed":false}\n',
        })
        manifest(directory, action='check', input_status='VALID',
                 execution_status='COMPLETED', numerical_status='NOT_EXECUTED')
        before = self.snapshot(directory)
        with self.forbid_input_and_science(), \
                patch.object(cli, 'save', side_effect=AssertionError('Report tried to save')) as save, \
                patch.object(cli, 'manifest', side_effect=AssertionError('Report tried to manifest')) as create_manifest:
            code, stdout, _ = self.invoke('report', '--run-directory', directory)
        self.assertEqual(code, 0)
        self.assertIn('Preservation test question', stdout)
        save.assert_not_called()
        create_manifest.assert_not_called()
        self.assertEqual(self.snapshot(directory), before)

    def test_unverified_report_only_directory_is_diagnostic_and_unchanged(self):
        directory = self.root / 'unverified report only'
        self.seed(directory, {'report.md': b'Historical report-only evidence.\r\n'})
        before = self.snapshot(directory)
        with self.forbid_input_and_science():
            code, stdout, stderr = self.invoke('report', '--run-directory', directory)
        self.assertEqual(code, 40)
        self.assertTrue((stdout + stderr).strip(),
                        'Unverified evidence should still produce diagnostics')
        self.assertEqual(self.snapshot(directory), before)


if __name__ == '__main__':
    unittest.main()
