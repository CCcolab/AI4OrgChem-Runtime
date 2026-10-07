"""Cooperative-stop tests using stdlib and toy delegates; no molecular calls."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import signal
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from runtime.user_molecule.root_native_lifecycle import StopController,CooperativeStopRequested


class RootNativeLifecycleTests(unittest.TestCase):
    def worker(self):
        path=Path(__file__).resolve().parents[1]/'scripts/diagnose-user-molecule-root-native-worker.py'
        spec=importlib.util.spec_from_file_location('lifecycle_worker_test_only',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

    def test_signal_handler_records_without_clock_io_or_exception(self):
        controller=StopController(clock=lambda:(_ for _ in ()).throw(AssertionError('handler cannot use clock')))
        controller._signal_handler(signal.SIGTERM,None)
        self.assertTrue(controller.snapshot()['stop_requested'])
        self.assertEqual(controller.snapshot()['stop_reason'],'SIGTERM')
        self.assertEqual(controller.snapshot()['native_execution_counts'],'NOT_OBSERVED_BY_STOP_CONTROLLER')
        with self.assertRaises(CooperativeStopRequested):controller.checkpoint('AFTER_DURABLE_WRITE')

    def test_signal_during_atomic_write_does_not_break_or_partially_replace_it(self):
        controller=StopController()
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);target=root/'state.json';target.write_text('{"state":"old"}')
            pending=root/'pending.json'
            with pending.open('wb') as stream:
                stream.write(b'{"state":')
                controller._signal_handler(signal.SIGINT,None)
                stream.write(b'"complete"}');stream.flush();os.fsync(stream.fileno())
            os.replace(pending,target)
            self.assertEqual(json.loads(target.read_bytes()),{'state':'complete'})
            with self.assertRaises(CooperativeStopRequested):controller.checkpoint('AFTER_ATOMIC_REPLACE')

    def test_installed_restores_both_original_handlers_after_failure(self):
        originals={signal.SIGTERM:object(),signal.SIGINT:object()};active=dict(originals)
        def setter(number,handler):old=active[number];active[number]=handler;return old
        controller=StopController()
        with patch.object(signal,'getsignal',side_effect=lambda number:active[number]),patch.object(signal,'signal',side_effect=setter):
            with self.assertRaisesRegex(RuntimeError,'body failed'):
                with controller.installed():
                    self.assertTrue(controller.snapshot()['handlers_installed'])
                    active[signal.SIGTERM](signal.SIGTERM,None)
                    raise RuntimeError('body failed')
        self.assertEqual(active,originals);self.assertFalse(controller.snapshot()['handlers_installed'])

    def test_partial_install_failure_restores_already_installed_handler(self):
        originals={signal.SIGTERM:object(),signal.SIGINT:object()};active=dict(originals);failed=[False]
        def setter(number,handler):
            if number==signal.SIGINT and handler is not originals[number] and not failed[0]:
                failed[0]=True;raise ValueError('toy install failure')
            old=active[number];active[number]=handler;return old
        with patch.object(signal,'getsignal',side_effect=lambda number:active[number]),patch.object(signal,'signal',side_effect=setter):
            with self.assertRaises(ValueError):
                with StopController().installed():self.fail('body cannot run')
        self.assertEqual(active,originals)

    def test_absolute_deadline_stops_at_boundary_and_cannot_be_extended(self):
        values=iter((274.0,275.0));controller=StopController(deadline_epoch=275,clock=lambda:next(values))
        controller.checkpoint('BEFORE_OBSERVE')
        with self.assertRaises(CooperativeStopRequested):controller.checkpoint('AFTER_OBSERVE')
        self.assertEqual(controller.snapshot()['stop_reason'],'HOST_STOP_DEADLINE_REACHED')
        with self.assertRaises(ValueError):controller.arm_deadline(300)

    def test_invalid_deadlines_and_signal_metadata_are_refused(self):
        for value in (True,0,-1,float('nan'),float('inf'),'275'):
            with self.subTest(value=value),self.assertRaises(ValueError):StopController(deadline_epoch=value)
        with self.assertRaises(ValueError):StopController().request_stop('stop',signal_number=True)

    def test_first_stop_reason_is_preserved_and_snapshot_is_owned(self):
        controller=StopController();controller.request_stop('FIRST');controller.request_stop('SECOND')
        receipt=controller.snapshot();receipt['stop_reason']='caller mutation'
        self.assertEqual(controller.snapshot()['stop_reason'],'FIRST')
        with self.assertRaises(CooperativeStopRequested) as captured:controller.checkpoint('SAFE_BOUNDARY')
        self.assertEqual(captured.exception.receipt['checkpoint_phase'],'SAFE_BOUNDARY')

    def toy_accounting(self,root):
        from runtime.user_molecule.residual_budget import ConditionalCallbackBudget
        from runtime.user_molecule.root_native_accounting import RootNativeAccounting
        journal=ConditionalCallbackBudget(path=root/'callbacks.json',batch_id='shutdown-toy',
            identity={'mode':'ENGINEERING_SIMULATED_NATIVE','execution_kind':'ENGINEERING_SIMULATED_NATIVE',
                'scientific_execution_authorized':False,'geometry_sha256':'a'*64,'profile_sha256':'b'*64,'dependencies_sha256':'c'*64},
            path_limits={'independent_reference':201},total_limit=201)
        return journal,RootNativeAccounting(root/'accounting',journal)

    def test_stop_after_delegate_entry_preserves_completed_nr_but_fails_unmatched_slot(self):
        worker=self.worker();controller=StopController()
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);journal,account=self.toy_accounting(root)
            token=account.begin_callback('d'*64,'CURRENT_INITIAL')
            def delegate():controller._signal_handler(signal.SIGTERM,None);return 'toy NR complete'
            account.native_nr(token,delegate,context_binding={'slot_id':token.slot_id,'path_id':token.path_id,
                'density_id':token.density_id,'phase':token.phase})
            with self.assertRaises(CooperativeStopRequested):controller.checkpoint('AFTER_OBSERVE_TOY_NR')
            reference=SimpleNamespace(_used=False,_settled=False)
            worker.close_active_initialization(root,journal=journal,accounting=account,reference=reference,reason='COOPERATIVE_STOP_NO_RETRY')
            worker.save(root/'guard-status.json',{'forbidden_attempts':[],'changed_bindings':[]})
            receipt=worker.publish_shutdown_receipt(root,controller,journal=journal,accounting=account,reference=reference)
            self.assertEqual(receipt['status'],'COOPERATIVE_STOP_VISIBLE_HANDLES_CLOSED')
            self.assertTrue(receipt['guard_receipt_present'] and receipt['guards_held'])
            self.assertTrue(receipt['accounting_closed'] and receipt['accounting_persistence_intact'])
            self.assertEqual(receipt['accounting_snapshot']['nr_dispatch_counts'],{'entered':1,'completed':1,'failed':0})
            self.assertEqual(receipt['journal_snapshot']['failed_slots'],1)
            self.assertIsNone(receipt['source_native_counts']['entered'])
            self.assertTrue(reference._settled)

    def test_no_handles_shutdown_does_not_create_science_allowance_or_invent_counts(self):
        worker=self.worker();controller=StopController();controller.request_stop('PREPARE_ONLY_STOP')
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);receipt=worker.publish_shutdown_receipt(root,controller)
            self.assertFalse(receipt['journal_created']);self.assertFalse(receipt['accounting_created'])
            self.assertIsNone(receipt['source_native_counts']);self.assertIsNone(receipt['journal_snapshot'])
            self.assertFalse((root/'callbacks.json').exists())

    def test_unreadable_journal_or_cleanup_failure_stays_unknown(self):
        worker=self.worker();controller=StopController();controller.request_stop('STOP')
        broken=SimpleNamespace(snapshot=lambda:(_ for _ in ()).throw(OSError('toy read failure')))
        with tempfile.TemporaryDirectory() as temporary:
            receipt=worker.publish_shutdown_receipt(Path(temporary),controller,journal=broken,cleanup_error=RuntimeError('close failed'))
            self.assertEqual(receipt['status'],'SHUTDOWN_UNKNOWN_NOT_QUALIFIED')
            self.assertIsNone(receipt['source_native_counts']);self.assertTrue(receipt['errors'])

    def test_worker_checks_before_after_observe_and_installs_handlers_around_main(self):
        worker=self.worker();tree=ast.parse(Path(worker.__file__).read_text())
        run=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='run_worker')
        observe=next(node for node in run.body if isinstance(node,ast.FunctionDef) and node.name=='observe')
        checks=[node for node in ast.walk(observe) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='checkpoint']
        self.assertEqual(len(checks),2)
        body=ast.unparse(observe);self.assertLess(body.index('BEFORE_OBSERVE_'),body.index('collect_cgroup'))
        self.assertGreater(body.index('AFTER_OBSERVE_'),body.index('resource_reasons'))
        main=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='main')
        self.assertTrue(any(isinstance(node,ast.With) and 'installed()' in ast.unparse(node) for node in main.body))


if __name__=='__main__':unittest.main()
