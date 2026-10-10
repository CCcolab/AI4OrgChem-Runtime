"""Legacy task exit contracts using fake child execution and no scientific calls."""
import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime import cli


NO_RESULT = object()


class QualificationExitTests(unittest.TestCase):
    def run_fixture(self, task, result=NO_RESULT, child_codes=(0,), execute_error=None,
                    memory_error=None):
        """Exercise the real manifest/stdout path while replacing every child call."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            args = argparse.Namespace(task=task, source=source, output_root=root / 'output',
                                      threads=1, lock_root=root / 'locks')
            hashes = {name: 'fixture-sha256' for name in
                      (cli.PROTOCOL, cli.CLASSES, *cli.PUBLIC_INPUTS)}
            versions = {wheel['name']: wheel['version'] for wheel in
                        cli.load(cli.ROOT / 'locks/wheels.lock.json')['wheels']}

            def fake_execute(command, env, work, run, index):
                if execute_error is not None:
                    raise execute_error
                if result is not NO_RESULT:
                    (run / 'result.json').write_text(json.dumps(result), encoding='utf-8')
                return child_codes[index]

            fake_commands = [['mock-child', str(index)] for index in range(len(child_codes))]
            with contextlib.ExitStack() as stack:
                stack.enter_context(mock.patch.object(cli.platform, 'system', return_value='Linux'))
                stack.enter_context(mock.patch.object(cli.sys, 'version_info', (3, 12, 0)))
                stack.enter_context(mock.patch.object(cli, 'runtime_snapshot', return_value='fixture-runtime-sha256'))
                stack.enter_context(mock.patch.object(cli, 'dependencies', return_value=versions))
                stack.enter_context(mock.patch.object(cli, 'verify_source', return_value=hashes))
                stack.enter_context(mock.patch.object(cli, 'thread_limit', return_value=1))
                stack.enter_context(mock.patch.object(cli, 'memory_snapshot',
                                                     return_value={'effective_available_bytes': 2**40}))
                stack.enter_context(mock.patch.object(cli, 'require_memory', side_effect=memory_error))
                stack.enter_context(mock.patch.object(cli, 'commands', return_value=(fake_commands, [])))
                stack.enter_context(mock.patch.object(cli, 'host_lock',
                                                     side_effect=lambda path: contextlib.nullcontext()))
                executed = stack.enter_context(mock.patch.object(cli, 'execute', side_effect=fake_execute))
                output = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                returned = cli.run_task(args)
                summary = json.loads(output.getvalue())
                manifest = cli.load(summary['manifest'])
                for name, expected in manifest['output_sha256'].items():
                    self.assertEqual(cli.digest(Path(summary['manifest']).parent / name), expected)
            self.assertEqual(summary['status'], manifest['status'])
            self.assertEqual(summary['runtime_exit_code'], returned)
            self.assertEqual(manifest['runtime_exit_code'], returned)
            return returned, manifest, executed.call_count

    def assert_outcome(self, returned, manifest, status, child_code, qualification):
        self.assertEqual(manifest['status'], status)
        self.assertEqual(manifest['process_exit_code'], child_code)
        self.assertEqual(manifest['subprocess_exit_code'], child_code)
        self.assertEqual(manifest['numerical_qualification'], qualification)
        self.assertEqual(returned == 0, status == 'PASS')

    def test_each_scientific_task_passes_with_pass_gate(self):
        for task, definition in cli.TASKS.items():
            if definition is None:
                continue
            with self.subTest(task=task):
                returned, manifest, calls = self.run_fixture(task, {definition[1]: 'PASS'})
                self.assert_outcome(returned, manifest, 'PASS', 0, 'PASS')
                self.assertEqual(calls, 1)

    def test_each_scientific_task_rejects_nonpassing_or_missing_gate(self):
        for task, definition in cli.TASKS.items():
            if definition is None:
                continue
            for gate in ('FAIL', 'UNKNOWN', 'PARTIAL_OR_FAIL', None):
                with self.subTest(task=task, gate=gate):
                    result = {} if gate is None else {definition[1]: gate}
                    returned, manifest, calls = self.run_fixture(task, result)
                    self.assertEqual(returned, cli.QUALIFICATION_EXIT_CODE)
                    self.assert_outcome(returned, manifest, 'FAIL', 0,
                                        'UNKNOWN' if gate is None else gate)
                    self.assertEqual(calls, 1)

    def test_each_scientific_task_rejects_missing_result(self):
        for task, definition in cli.TASKS.items():
            if definition is None:
                continue
            with self.subTest(task=task):
                returned, manifest, _ = self.run_fixture(task)
                self.assertEqual(returned, cli.QUALIFICATION_EXIT_CODE)
                self.assert_outcome(returned, manifest, 'FAIL', 0, 'UNKNOWN')

    def test_original_child_failure_is_preserved_even_with_pass_gate(self):
        for gate in ('PASS', 'FAIL', 'UNKNOWN'):
            with self.subTest(gate=gate):
                returned, manifest, _ = self.run_fixture('p14-smoke',
                                                        {'smoke_gate_verdict': gate}, child_codes=(37,))
                self.assertEqual(returned, 37)
                self.assert_outcome(returned, manifest, 'FAIL', 37, gate)

    def test_original_child_failure_is_preserved_without_result(self):
        returned, manifest, _ = self.run_fixture('p14-smoke', child_codes=(37,))
        self.assertEqual(returned, 37)
        self.assert_outcome(returned, manifest, 'FAIL', 37, 'UNKNOWN')

    def test_failed_gate_retains_scientific_fields(self):
        result = {'decision_verdict': 'FAIL', 'classification': 'disagreement',
                  'quantitative_evidence': {'fixture_residual': 0.43}, 'peak_rss_mib': 123}
        returned, manifest, _ = self.run_fixture('p14-classify', result)
        self.assert_outcome(returned, manifest, 'FAIL', 0, 'FAIL')
        self.assertEqual(manifest['scientific_comparison'], 'disagreement')
        self.assertEqual(manifest['quantitative_evidence'], result['quantitative_evidence'])
        self.assertEqual(manifest['resource_peak'], {'peak_rss_mib': 123})

    def test_child_failure_stops_later_commands(self):
        returned, manifest, calls = self.run_fixture('evidence', child_codes=(0, 37, 0))
        self.assertEqual(returned, 37)
        self.assert_outcome(returned, manifest, 'FAIL', 37, 'NOT_APPLICABLE')
        self.assertEqual(calls, 2)

    def test_tasks_without_scientific_gate_follow_child_success(self):
        for task in ('evidence', 'core-tests'):
            for result in (NO_RESULT, {'verdict': 'FAIL'}):
                with self.subTest(task=task, result=result):
                    returned, manifest, _ = self.run_fixture(task, result)
                    self.assertEqual(returned, 0)
                    self.assert_outcome(returned, manifest, 'PASS', 0, 'NOT_APPLICABLE')

    def test_execution_error_retains_existing_runtime_error_code(self):
        returned, manifest, _ = self.run_fixture('p14-smoke', execute_error=ValueError('mock execution error'))
        self.assertEqual(returned, 2)
        self.assert_outcome(returned, manifest, 'FAIL', 'UNKNOWN', 'NOT_APPLICABLE')
        self.assertEqual(manifest['error'], 'mock execution error')

    def test_resource_block_does_not_execute_child(self):
        returned, manifest, calls = self.run_fixture('p14-fixed', memory_error=MemoryError('mock memory block'))
        self.assertEqual(returned, 3)
        self.assertEqual(manifest['status'], 'BLOCKED')
        self.assertEqual(manifest['process_exit_code'], 'UNKNOWN')
        self.assertEqual(manifest['subprocess_exit_code'], 'UNKNOWN')
        self.assertEqual(calls, 0)


if __name__ == '__main__':
    unittest.main()
