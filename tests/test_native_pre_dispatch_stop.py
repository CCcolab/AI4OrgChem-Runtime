"""Requests during a durable intent never become actual native entry counts."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from runtime.user_molecule.residual_budget import ConditionalCallbackBudget
from runtime.user_molecule.root_native_accounting import RootNativeAccounting


class NativePreDispatchStopTests(unittest.TestCase):
    def test_stop_after_intent_write_prevents_delegate_preserves_charge_and_real_zero_counts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            journal=ConditionalCallbackBudget(path=root/'budget.json',batch_id='pre-dispatch-stop',
                identity={'mode':'ENGINEERING_SIMULATED_NATIVE','execution_kind':'ENGINEERING_SIMULATED_NATIVE',
                    'scientific_execution_authorized':False,'initial_density_id':'a'*64,
                    'geometry_sha256':'b'*64,'profile_sha256':'c'*64,'dependencies_sha256':'d'*64},
                path_limits={'independent_reference':201},total_limit=201)
            account=RootNativeAccounting(root/'accounting',journal)
            token=account.begin_callback('a'*64,'CURRENT_INITIAL')
            binding={'slot_id':1,'path_id':'independent_reference','density_id':'a'*64,'phase':'CURRENT_INITIAL'}
            callback=Mock();check=Mock(side_effect=RuntimeError('stop received while intent persisted'))
            with self.assertRaisesRegex(RuntimeError,'stop received'):
                account.native_nr(token,callback,context_binding=binding,pre_dispatch_check=check)
            callback.assert_not_called();check.assert_called_once_with()
            account.fail_callback(token,RuntimeError('stopped before delegate'))
            final=account.close('PRE_DISPATCH_STOP_NO_RETRY')
            self.assertEqual(final['nr_dispatch_counts'],{'entered':0,'completed':0,'failed':0})
            self.assertEqual(final['callback_slots']['charged'],1)
            self.assertEqual(final['callback_slots']['failed'],1)
            self.assertTrue(final['closed']);self.assertTrue(final['persistence_intact'])
            rows=[json.loads(line) for line in (root/'accounting/native-events.jsonl').read_text().splitlines()]
            self.assertEqual([row['event'] for row in rows],['NR_ENTERED','NR_REFUSED_BEFORE_DISPATCH'])
            self.assertFalse(rows[-1]['observed_dispatch_entered'])
            self.assertIsNone(final['source_native_dispatch_counts']['entered'])
            with self.assertRaises(ValueError):account.begin_callback('b'*64,'OPTIMIZER_BASE')

    def test_check_after_actual_intent_fsync_sees_signal_without_asynchronous_exception(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);stopped=[]
            journal=ConditionalCallbackBudget(path=root/'budget.json',batch_id='intent-order',
                identity={'mode':'ENGINEERING_SIMULATED_NATIVE','scientific_execution_authorized':False,
                    'geometry_sha256':'b'*64,'profile_sha256':'c'*64,'dependencies_sha256':'d'*64},
                path_limits={'independent_reference':201},total_limit=201)
            account=RootNativeAccounting(root/'accounting',journal)
            token=account.begin_callback('a'*64,'CURRENT_INITIAL')
            original=account._event
            def event(kind,*args,**kwargs):
                value=original(kind,*args,**kwargs)
                if kind=='NR_ENTERED':stopped.append(True)
                return value
            def check():
                self.assertTrue(stopped)
                raise RuntimeError('cooperative check only')
            callback=Mock()
            with patch.object(account,'_event',side_effect=event),self.assertRaisesRegex(RuntimeError,'cooperative'):
                account.native_nr(token,callback,context_binding={'slot_id':1,'path_id':'independent_reference',
                    'density_id':'a'*64,'phase':'CURRENT_INITIAL'},pre_dispatch_check=check)
            callback.assert_not_called()
            account.fail_callback(token,RuntimeError('stop'))
            self.assertEqual(account.close('STOP')['nr_dispatch_counts']['entered'],0)


if __name__=='__main__':unittest.main()
