"""Durable callback-slot tests with standard-library fake callbacks only."""
import json
from pathlib import Path
import tempfile
import unittest

from runtime.user_molecule.residual_budget import (ConditionalCallbackBudget, CallbackBudgetError,
                                                 reserve_single_process)
from runtime.user_molecule.acceptance_resources import Budget, BudgetBusy, _lock

IDENTITY = {'geometry_sha256':'a'*64,'profile_sha256':'b'*64,
    'dependencies_sha256':'c'*64,'mode':'ENGINEERING_FAKE','runtime_test_commit':'d'*40}
DID, FID = '1'*64, '2'*64


class CallbackBudgetTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)/'callbacks.json'

    def budget(self, **changes):
        arguments = {'path':self.path,'batch_id':'residual-engineering-test','identity':IDENTITY,
                     'path_limits':{'copy':2,'reference':2},'total_limit':3}
        arguments.update(changes)
        return ConditionalCallbackBudget(**arguments)

    def test_pending_and_failed_slots_survive_reopen_without_refund(self):
        book = self.budget()
        first=book.charge('copy',DID,'INITIALIZE_AT_ORDINARY_D0')
        book.finish(first['slot_id'],status='FAILED',detail='fake failure')
        book.charge('copy',DID,'FD_PLUS')
        snapshot=self.budget().snapshot()
        self.assertEqual(snapshot['charged_slots'],2)
        self.assertEqual(snapshot['pending_slots'],1)
        self.assertEqual(snapshot['failed_slots'],1)
        with self.assertRaises(CallbackBudgetError):
            self.budget().charge('copy',DID,'CURRENT')
        self.assertEqual(self.budget().snapshot()['charged_slots'],2)

    def test_one_process_policy_survives_zero_wall_settlement_and_reopen(self):
        path=Path(self.directory.name)/'wall.json'
        book=Budget(path,'one-process-test',total_seconds=20,max_process_seconds=10,
                    memory_limit_mib=512,threads=1)
        first=reserve_single_process(book,run_id='first',identity=IDENTITY)
        self.assertEqual(first['reserved_seconds'],10)
        self.assertEqual(book.snapshot()['unresolved_reserved_seconds'],10)
        book.settle('first',0,'FAKE_EARLY_REFUSAL')
        again=Budget(path,'one-process-test',total_seconds=20,max_process_seconds=10,
                     memory_limit_mib=512,threads=1)
        with self.assertRaises(CallbackBudgetError):
            reserve_single_process(again,run_id='second',identity=IDENTITY)
        self.assertEqual(len(again.snapshot()['runs']),1)

    def test_total_limit_is_shared_across_paths(self):
        book=self.budget()
        book.charge('copy',DID,'CURRENT');book.charge('copy',DID,'FINAL')
        book.charge('reference',DID,'CURRENT')
        with self.assertRaises(CallbackBudgetError): book.charge('reference',DID,'FINAL')
        self.assertEqual(book.snapshot()['remaining_slots'],0)

    def test_identity_batch_or_limits_cannot_reset_existing_journal(self):
        self.budget().charge('copy',DID,'CURRENT');before=self.path.read_bytes()
        for change in ({'batch_id':'another'}, {'total_limit':2}, {'path_limits':{'copy':1,'reference':2}},
                       {'identity':dict(IDENTITY,runtime_test_commit='e'*40)}):
            with self.subTest(change=change), self.assertRaises(CallbackBudgetError): self.budget(**change)
            self.assertEqual(self.path.read_bytes(),before)

    def test_accounted_callback_exhaustion_never_enters_evaluator(self):
        calls=[];book=self.budget()
        def callback(density, phase='SOLVER_CALLBACK'):
            calls.append(phase)
            return {'density_id':DID,'fock':'fake'}
        invoke=book.accounted_callback('copy',callback,density_identity=lambda _:DID,
                                      operator_identity=lambda _:FID)
        invoke('fake',phase='INITIALIZE_AT_ORDINARY_D0');invoke('fake',phase='FINAL')
        with self.assertRaises(CallbackBudgetError):invoke('fake')
        self.assertEqual(calls,['INITIALIZE_AT_ORDINARY_D0','FINAL'])
        snapshot=book.snapshot()
        self.assertEqual([row['operator_id'] for row in snapshot['slots']],[FID,FID])
        self.assertFalse(snapshot['scientific_approval']);self.assertFalse(snapshot['production_activation'])

    def test_callback_failure_and_keyboard_interrupt_are_charged(self):
        book=self.budget()
        for error in (RuntimeError('fake fault'),KeyboardInterrupt()):
            def failing(density):raise error
            invoke=book.accounted_callback('copy',failing,density_identity=lambda _:DID,
                                          operator_identity=lambda _:FID)
            with self.assertRaises(type(error)):invoke('fake')
        snapshot=book.snapshot()
        self.assertEqual(snapshot['failed_slots'],2);self.assertEqual(snapshot['pending_slots'],0)
        self.assertEqual(snapshot['charged_slots'],2)

    def test_callback_density_mutation_and_wrong_identity_are_refused(self):
        book=self.budget()
        density=[DID]
        def mutate(d):d[0]='3'*64;return {'density_id':DID}
        invoke=book.accounted_callback('copy',mutate,density_identity=lambda d:d[0],operator_identity=lambda _:FID)
        with self.assertRaises(CallbackBudgetError):invoke(density)
        bad=book.accounted_callback('reference',lambda d:{'density_id':'4'*64},
            density_identity=lambda d:DID,operator_identity=lambda _:FID)
        with self.assertRaises(CallbackBudgetError):bad('fake')
        self.assertEqual(book.snapshot()['failed_slots'],2)

    def test_closed_paths_and_finished_slots_are_single_use(self):
        book=self.budget();slot=book.charge('copy',DID,'CURRENT')
        book.finish(slot['slot_id'],status='SUCCEEDED',operator_id=FID)
        with self.assertRaises(CallbackBudgetError):book.finish(slot['slot_id'],status='FAILED')
        book.close_path('copy','ENGINEERING_TEST_DONE')
        with self.assertRaises(CallbackBudgetError):self.budget().charge('copy',DID,'RETRY')
        with self.assertRaises(CallbackBudgetError):book.close_path('copy','RETRY')

    def test_pending_slots_remain_charged_when_path_closes_after_crash(self):
        book=self.budget();book.charge('copy',DID,'CURRENT')
        book.close_path('copy','PROCESS_LOST_PENDING_CHARGE_RETAINED')
        snapshot=self.budget().snapshot()
        self.assertEqual(snapshot['pending_slots'],1)
        self.assertEqual(snapshot['charged_slots'],1)
        self.assertEqual(snapshot['remaining_slots'],2)

    def test_tampered_file_is_refused_and_not_overwritten(self):
        self.budget();data=json.loads(self.path.read_text())
        data['total_limit']=600;self.path.write_text(json.dumps(data));before=self.path.read_bytes()
        with self.assertRaises(ValueError):self.budget()
        self.assertEqual(self.path.read_bytes(),before)

    def test_nonblocking_lock_refuses_concurrent_writer(self):
        book=self.budget()
        with _lock(book.lock_path):
            with self.assertRaises(BudgetBusy):self.budget().charge('copy',DID,'CURRENT')

    def test_invalid_limits_and_ids_are_rejected_without_charging(self):
        for change in ({'total_limit':True},{'path_limits':{'copy':202}},{'path_limits':{'copy':False}},
                       {'path_limits':{}},{'path_limits':{'a':1,'b':1,'c':1,'d':1}}):
            with self.subTest(change=change),self.assertRaises(ValueError):self.budget(**change)
        book=self.budget()
        for path,density,phase in (('copy','bad','CURRENT'),('unknown',DID,'CURRENT'),('copy',DID,'')):
            with self.subTest(path=path,density=density,phase=phase),self.assertRaises(ValueError):
                book.charge(path,density,phase)
        self.assertEqual(book.snapshot()['charged_slots'],0)


if __name__=='__main__':unittest.main()
