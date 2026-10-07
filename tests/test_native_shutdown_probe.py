"""Portable probe protections; no Docker, actual signals or scientific imports."""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from runtime.user_molecule.root_native_lifecycle import StopController
from runtime.user_molecule.residual_budget import ConditionalCallbackBudget
from runtime.user_molecule.root_native_accounting import RootNativeAccounting

SCRIPT = Path(__file__).resolve().parents[1]/'scripts/probe-user-molecule-native-shutdown-worker.py'
SPEC = importlib.util.spec_from_file_location('shutdown_probe_under_test', SCRIPT)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class NativeShutdownProbeTests(unittest.TestCase):
    def test_cli_requires_fixed_scenario_and_has_no_execute_or_grant_route(self):
        for name in ('before-charge', 'during-delegate', 'ignore-signal'):
            args = probe.argument_parser().parse_args(['--scenario', name])
            self.assertEqual(args.scenario, name)
        for arguments in ([], ['--scenario', 'actual-molecule'], ['--scenario', 'before-charge', '--execute'],
                          ['--scenario', 'before-charge', '--grant-file', 'anything.json']):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                probe.argument_parser().parse_args(arguments)

    def test_wait_consumes_recorded_request_and_times_out_without_async_raise(self):
        controller = StopController()
        controller.request_stop('TEST_REQUEST_ONLY_NOT_AN_ACTUAL_SIGNAL')
        with mock.patch.object(probe.time, 'sleep') as sleeper:
            probe.wait_for_signal(controller)
            sleeper.assert_not_called()
        controller = StopController()
        with mock.patch.object(probe.time, 'monotonic', side_effect=[0., 12.]), \
             mock.patch.object(probe.time, 'sleep') as sleeper:
            with self.assertRaises(TimeoutError):
                probe.wait_for_signal(controller)
            sleeper.assert_not_called()
        self.assertIs(controller.snapshot()['stop_requested'], False)

    def test_guard_record_requires_exact_held_set_and_keeps_unknown_on_failures(self):
        # Pure owner doubles validate record semantics; not evidence of held PySCF APIs.
        rows = []
        for label in sorted(probe.EXPECTED_GUARDS):
            guard = lambda: None
            rows.append((SimpleNamespace(operation=guard), 'operation', guard, label))
        record = probe.guard_snapshot(rows, [])
        self.assertEqual(record['actual_native_NR_calls'], 0)
        self.assertIsNone(probe.guard_snapshot(rows[:-1], [])['actual_native_NR_calls'])
        self.assertIsNone(probe.guard_snapshot(rows, ['FORBIDDEN_TEST_DOUBLE_ATTEMPT'])['actual_native_NR_calls'])
        self.assertIsNone(probe.guard_snapshot(rows+[rows[0]], [])['actual_native_NR_calls'])
        rows[0][0].operation = lambda: None
        self.assertIsNone(probe.guard_snapshot(rows, [])['actual_native_NR_calls'])

    def test_json_publication_is_complete_new_only_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'READY.json'
            probe.save(path, {'scientific_execution_authorized': False, 'fixed': 0})
            original = path.read_bytes()
            self.assertEqual(json.loads(original), {'scientific_execution_authorized': False, 'fixed': 0})
            self.assertFalse(path.with_name(path.name+'.pending').exists())
            with self.assertRaises(FileExistsError):
                probe.save(path, {'replaced': True})
            self.assertEqual(path.read_bytes(), original)

    def test_existing_output_is_refused_before_helpers_or_source_input_read(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory); existing = output/'retained.txt'
            existing.write_bytes(b'preserve me')
            args = argparse.Namespace(scenario='before-charge', output_dir=output)
            with mock.patch.object(probe, 'load_module', side_effect=AssertionError('No helper admission')) as loader:
                with self.assertRaises(ValueError):
                    probe.run_probe(args)
                loader.assert_not_called()
            self.assertEqual(existing.read_bytes(), b'preserve me')

    def test_actual_stdlib_toy_identity_journal_and_accounting_close_without_native_source_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); did = hashlib.sha256(b'fixed synthetic D, no molecule').hexdigest()
            identity = probe.toy_identity(batch='portable-probe-test', scenario='during-delegate',
                source={probe.SOURCE_FILES[0]: 'ab'*32},
                versions={'pyscf': 'TEST_DECLARATION', 'numpy': 'NOT_IMPORTED', 'scipy': 'NOT_IMPORTED'}, density_id=did)
            journal = ConditionalCallbackBudget(path=root/'callbacks.json', batch_id=identity['batch_id'],
                identity=identity, path_limits={'independent_reference': 201}, total_limit=201)
            counter = RootNativeAccounting(root/'accounting', journal, execution_kind=probe.MODE,
                scientific_execution_authorized=False)
            token = counter.begin_callback(did, 'CURRENT_INITIAL')
            binding = {'slot_id': token.slot_id, 'density_id': did,
                'path_id': 'independent_reference', 'phase': 'CURRENT_INITIAL'}
            self.assertEqual(counter.native_nr(token, lambda: 0.0, context_binding=binding), 0.0)
            counter.fail_callback(token, RuntimeError('synthetic post-return stop; no actual signal'))
            final = counter.close('PORTABLE_ENGINEERING_CLOSE_NO_SCIENCE')
            self.assertEqual(final['callback_slots'], {'charged': 1, 'pending': 0, 'succeeded': 0, 'failed': 1, 'limit': 201})
            self.assertEqual(final['engineering_simulated_native_counts'], {'entered': 1, 'completed': 1, 'failed': 0})
            self.assertIs(final['closed'], True); self.assertIs(final['persistence_intact'], True)
            self.assertEqual(journal.snapshot()['paths']['independent_reference']['state'], 'CLOSED')
            self.assertTrue(all(final['source_native_dispatch_counts'][key] is None for key in ('entered', 'completed', 'failed')))
            self.assertIs(identity['scientific_execution_authorized'], False)
            self.assertIsNone(identity['execution_grant'])


if __name__ == '__main__':
    unittest.main()
