"""Fixed single-response adapter engineering tests; callbacks are synthetic.

The nominal LIVE declaration test reads the real retained seed arrays but
calls test doubles under the outer engineering guard.  It is wiring evidence,
not a molecular execution or a native-counter certificate.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

import numpy as np

from runtime.user_molecule import occupied_space_response as response
from runtime.user_molecule.occupied_space_seeds import prepare_occupied_space_seeds, array_identity
from runtime.user_molecule.occupation_response import density_id, OPERATOR_SOURCE, PATH_NAMES
from runtime.user_molecule.residual_budget import ConditionalCallbackBudget, CallbackBudgetError


def thaw(value):
    if isinstance(value, np.ndarray): return value.copy()
    if isinstance(value, dict): return {key: thaw(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)): return [thaw(item) for item in value]
    return value


class OccupiedSpaceResponseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.s, self.mask = np.eye(4), np.zeros((4, 4), dtype=bool)
        self.electrons, self.sequence, self.calls = 4, 0, []

    def family(self):
        d = np.diag([2., 2., 0., 0.])
        return prepare_occupied_space_seeds(density=d, masked_overlap=self.s, electrons=4,
            occupied_anchor=np.array([0., 1., 0., 0.]), virtual_anchor=np.array([0., 0., 1., 0.]),
            angles=list(response.REQUIRED_ANGLES), expected_density_id=density_id(d),
            expected_overlap_identity=array_identity(self.s))

    def retained_family(self):
        from runtime.user_molecule import occupied_space_response_contract as contract
        folder = Path(os.environ.get('AI4ORGCHEM_OCCUPIED_RESPONSE_INPUT_DIR',
            os.environ.get('AI4ORGCHEM_OCCUPIED_SEED_INPUT_DIR', '/seed-input')))
        record_raw = (folder/'prepared-seed-family.json').read_bytes()
        archive_raw = (folder/'prepared-seed-family.npz').read_bytes()
        self.assertEqual(hashlib.sha256(record_raw).hexdigest(), contract.SEED_RECORD_SHA256)
        self.assertEqual(hashlib.sha256(archive_raw).hexdigest(), contract.SEED_ARRAYS_SHA256)
        record = json.loads(record_raw)
        with np.load(folder/'prepared-seed-family.npz', allow_pickle=False) as archive:
            def decode(value):
                if isinstance(value, dict) and 'npz_member' in value:
                    array = archive[value['npz_member']].copy()
                    self.assertEqual(list(array.shape), value['shape'])
                    self.assertEqual(array.dtype.str, value['dtype'])
                    self.assertTrue(np.isfinite(array).all())
                    self.assertEqual(hashlib.sha256(array.tobytes()).hexdigest(), value['sha256'])
                    return array
                if isinstance(value, dict): return {key: decode(item) for key, item in value.items()}
                if isinstance(value, list): return [decode(item) for item in value]
                return value
            family = decode({key: value for key, value in record.items() if key != 'raw_array_archive'})
        source = json.loads((folder/'SOURCE.json').read_bytes())
        raw = (folder/'source-arrays.npz').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), contract.SOURCE_ARRAYS_SHA256)
        with np.load(folder/'source-arrays.npz', allow_pickle=False) as archive:
            self.mask = archive['matrix_delete_mask'].copy()
        self.assertEqual(self.mask.dtype.kind, 'b')
        self.assertEqual(hashlib.sha256(self.mask.tobytes()).hexdigest(), source['arrays']['matrix_delete_mask']['sha256'])
        self.s = family['source_masked_overlap'].copy()
        self.electrons = 16
        return family

    def identity(self, *, live=False):
        if not live:
            return {'mode': 'ENGINEERING_FAKE', 'geometry_sha256': 'a'*64,
                'profile_sha256': 'b'*64, 'dependencies_sha256': 'c'*64}
        from runtime.user_molecule import occupied_space_response_contract as execution
        from test_user_molecule_occupied_space_response_contract import contract_fixture
        return execution.execution_identity(contract_fixture(authorized=True), 'af'*32)

    def book(self, identity=None, **changes):
        self.sequence += 1
        identity = self.identity() if identity is None else copy.deepcopy(identity)
        args = dict(path=Path(self.directory.name)/('response-'+str(self.sequence)+'.json'),
            batch_id=identity.get('batch_id', 'fake-response-'+str(self.sequence)), identity=identity,
            path_limits={name: 4 for name in PATH_NAMES}, total_limit=12)
        args.update(changes)
        return ConditionalCallbackBudget(**args)

    def value(self, d):
        f = np.diag(np.linspace(-.8, .7, len(d)))
        one = float(np.trace(d))
        count = float(np.trace(self.s@d))
        return {'density_id': density_id(d), 'operator_source': OPERATOR_SOURCE,
            'fock': f, 'raw_fock': f.copy(), 'one_electron_energy': one,
            'coulomb_energy': 0., 'exact_exchange_energy': 0., 'semilocal_xc_energy': 0.,
            'nuclear_repulsion': .1, 'total_energy': one+.1, 'electronic_energy': one,
            'masked_metric_electron_count': count, 'physical_metric_electron_count': count+.05,
            'grid_electron_count': count+.06}

    def callbacks(self, transform=None):
        result = {}
        for path in PATH_NAMES:
            def callback(d, phase, path=path):
                self.calls.append((path, phase, density_id(d)))
                value = self.value(d)
                return value if transform is None else transform(path, d, phase, value)
            result[path] = callback
        return result

    def run_fake(self, **changes):
        args = dict(prepared_seeds=self.family(), callbacks=self.callbacks(), overlap=self.s,
            electrons=self.electrons, matrix_delete_mask=self.mask, journal=self.book())
        args.update(changes)
        return response.run_occupied_space_response(**args)

    def test_public_readiness_is_zero_f_no_journal_and_returns_independent_fixed_array_copies(self):
        family = self.family()
        before = dict(response.ENGINEERING_FAKE_CALLBACK_COUNTS)
        ready = response.preflight_occupied_space_response(prepared_seeds=family,
            overlap=self.s, electrons=4, matrix_delete_mask=self.mask)
        self.assertEqual(ready['status'], 'PASS_STRICT_OCCUPIED_SPACE_RESPONSE_READINESS')
        self.assertEqual(len(ready['density_copies']), 4)
        self.assertEqual(ready['density_ids'], tuple(row['density_id'] for row in family['seeds']))
        self.assertEqual(ready['functional_calls'], 0)
        self.assertFalse(ready['scientific_execution_authorized'])
        for copy_d, row in zip(ready['density_copies'], family['seeds']):
            self.assertFalse(np.shares_memory(copy_d, row['density']))
            with self.assertRaises(ValueError): copy_d.setflags(write=True)
        self.assertEqual(response.ENGINEERING_FAKE_CALLBACK_COUNTS, before)
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])
        self.assertEqual(self.calls, [])

    def test_complete_fake_batch_orders_twelve_calls_and_eight_limited_same_density_comparisons(self):
        family = self.family()
        result = self.run_fake(prepared_seeds=family)
        expected = [(path, 'SINGLE_F_OCCUPIED_SPACE_RESPONSE_SEED_'+str(index), row['density_id'])
            for index, row in enumerate(family['seeds'], 1) for path in PATH_NAMES]
        self.assertEqual(self.calls, expected)
        self.assertEqual(result['status'], 'OCCUPIED_SPACE_SINGLE_F_RESPONSE_DIAGNOSTIC_COMPLETE')
        self.assertEqual(result['callback_accounting']['precharged_slots'], 12)
        self.assertEqual(result['callback_accounting']['entered'], 12)
        self.assertEqual(result['callback_accounting']['completed'], 12)
        self.assertEqual(result['callback_accounting']['failed'], 0)
        self.assertEqual(result['journal']['pending_slots'], 0)
        self.assertTrue(all(row['status'] == 'SUCCEEDED' for row in result['callback_ledger']))
        self.assertTrue(all(row['state'] == 'CLOSED' for row in result['journal']['paths'].values()))
        self.assertEqual(len(result['snapshots']), 12)
        self.assertEqual(len(result['single_density_comparisons']), 8)
        self.assertEqual(result['single_density_comparison_status'], 'PASS_SINGLE_D_OPERATOR_AND_ENERGY_SUBSET')
        self.assertTrue(all(row['thresholds'] == response.SAME_D_THRESHOLDS for row in result['single_density_comparisons']))
        self.assertFalse(result['engine_qualified']); self.assertFalse(result['compute_enabled'])
        self.assertIsNone(result['delta_hartree'])

    def test_live_declaration_uses_exact_retained_family_identity_but_never_infers_native_execution_from_slots(self):
        family = self.retained_family()
        book = self.book(identity=self.identity(live=True))
        fake_before = dict(response.ENGINEERING_FAKE_CALLBACK_COUNTS)
        live_before = dict(response.PREPARED_WRAPPER_CALLBACK_COUNTS)
        result = response.run_occupied_space_response(prepared_seeds=family, callbacks=self.callbacks(),
            overlap=self.s, electrons=16, matrix_delete_mask=self.mask, journal=book,
            execution_kind=response.LIVE_EXECUTION_KIND, scientific_execution_authorized=True)
        self.assertEqual(result['status'], 'OCCUPIED_SPACE_SINGLE_F_RESPONSE_DIAGNOSTIC_COMPLETE')
        self.assertEqual(response.ENGINEERING_FAKE_CALLBACK_COUNTS, fake_before)
        self.assertEqual({key: response.PREPARED_WRAPPER_CALLBACK_COUNTS[key]-live_before[key] for key in live_before},
            {'entered': 12, 'completed': 12, 'failed': 0})
        self.assertIsNone(result['engineering_fake_callback_counts'])
        self.assertEqual(result['native_execution_counts'], {'status': 'UNOBSERVED_WORKER_NATIVE_COUNTERS_REQUIRED',
            'true_F': None, 'nr_rks': None})
        self.assertTrue(result['scientific_execution_authorized'])
        self.assertFalse(result['scientific_approval']); self.assertFalse(result['compute_enabled'])
        for row in result['snapshots']:
            self.assertEqual(row['execution_kind'], response.LIVE_EXECUTION_KIND)
            self.assertEqual(row['operator_evidence_kind'], 'PREPARED_CALLBACK_DECLARATION_REQUIRES_WORKER_NATIVE_EXECUTION_EVIDENCE')
            self.assertEqual(row['operator_source'], OPERATOR_SOURCE)
            self.assertFalse(row['single_point_diagnostics']['full_endpoint_qualified'])
        self.assertTrue(all(row['full_T05'] == 'NOT_EXECUTED' for row in result['single_density_comparisons']))

    def test_unknown_modes_false_live_or_truthy_authorizations_refuse_and_close_before_callback(self):
        for changes in ({'execution_kind': 'PREPARED_MOLECULAR_DIAGNOSTIC'}, {'execution_kind': []},
                        {'execution_kind': response.LIVE_EXECUTION_KIND}, {'scientific_execution_authorized': True},
                        {'scientific_execution_authorized': 1}, {'scientific_execution_authorized': np.bool_(False)},
                        {'execution_kind': response.LIVE_EXECUTION_KIND, 'scientific_execution_authorized': 1}):
            with self.subTest(changes=changes):
                book = self.book()
                with self.assertRaises(ValueError): self.run_fake(journal=book, **changes)
                self.assertEqual(book.snapshot()['charged_slots'], 0)
                self.assertTrue(all(row['state'] == 'CLOSED' for row in book.snapshot()['paths'].values()))
        self.assertEqual(self.calls, [])

    def test_live_scope_source_or_batch_identity_substitution_refuses_before_any_callback(self):
        family = self.retained_family()
        correct = self.identity(live=True)
        for changes in ({'mode': 'ENGINEERING_FAKE'}, {'diagnostic_scope': 'SCF'},
                        {'scientific_execution_authorized': False}, {'seed_arrays_sha256': 'b'*64},
                        {'seed_density_ids': ['a'*64]*4}, {'runtime_test_commit': 'short'}):
            with self.subTest(changes=changes):
                identity = dict(correct, **changes)
                book = self.book(identity=identity)
                with self.assertRaises(ValueError):
                    response.run_occupied_space_response(prepared_seeds=thaw(family), callbacks=self.callbacks(),
                        overlap=self.s, electrons=16, matrix_delete_mask=self.mask, journal=book,
                        execution_kind=response.LIVE_EXECUTION_KIND, scientific_execution_authorized=True)
                self.assertEqual(book.snapshot()['charged_slots'], 0)
                self.assertTrue(all(row['state'] == 'CLOSED' for row in book.snapshot()['paths'].values()))
        book = self.book(identity=correct, batch_id='another-valid-batch')
        with self.assertRaisesRegex(ValueError, 'batch must match'):
            response.run_occupied_space_response(prepared_seeds=thaw(family), callbacks=self.callbacks(),
                overlap=self.s, electrons=16, matrix_delete_mask=self.mask, journal=book,
                execution_kind=response.LIVE_EXECUTION_KIND, scientific_execution_authorized=True)
        self.assertEqual(book.snapshot()['charged_slots'], 0)
        self.assertEqual(self.calls, [])

    def test_fake_identity_may_not_carry_live_kind_or_truthy_authorization(self):
        for changes in ({'mode': response.LIVE_EXECUTION_KIND}, {'execution_kind': response.LIVE_EXECUTION_KIND},
                        {'scientific_execution_authorized': True}, {'scientific_execution_authorized': 0}):
            with self.subTest(changes=changes):
                book = self.book(identity=dict(self.identity(), **changes))
                with self.assertRaises(ValueError): self.run_fake(journal=book)
                self.assertEqual(book.snapshot()['charged_slots'], 0)
        self.assertEqual(self.calls, [])

    def test_fourth_invalid_or_synced_recipe_forgery_is_rejected_before_first_callback(self):
        for kind in ('fourth_fractional', 'swapped', 'forged_source_bytes', 'changed_anchor_with_hash'):
            with self.subTest(kind=kind):
                family = thaw(self.family())
                if kind == 'fourth_fractional':
                    d = np.diag([2., 1., 1., 0.])
                    family['seeds'][3].update(density=d, density_id=density_id(d), density_identity=array_identity(d))
                elif kind == 'swapped':
                    left, right = family['seeds'][:2]
                    for key in ('density', 'density_id', 'density_identity'): left[key], right[key] = right[key], left[key]
                elif kind == 'forged_source_bytes': family['source_density'][0, 0] += .01
                else:
                    a = np.array([1., 0., 0., 0.])
                    family['source_occupied_anchor'] = a; family['source']['occupied_anchor_identity'] = array_identity(a)
                book = self.book()
                with self.assertRaises(ValueError): self.run_fake(prepared_seeds=family, journal=book)
                self.assertEqual(book.snapshot()['charged_slots'], 0)
                self.assertTrue(all(row['state'] == 'CLOSED' for row in book.snapshot()['paths'].values()))
        self.assertEqual(self.calls, [])

    def test_exact_twelve_limits_and_fresh_open_empty_journal_are_mandatory(self):
        for changes in ({'total_limit': 11}, {'path_limits': {name: 3 for name in PATH_NAMES}, 'total_limit': 9}):
            with self.subTest(changes=changes), self.assertRaises(CallbackBudgetError): self.run_fake(journal=self.book(**changes))
        for kind in ('pending', 'closed'):
            book = self.book()
            if kind == 'pending': book.charge(PATH_NAMES[0], 'a'*64, 'OLD')
            else: book.close_path(PATH_NAMES[0], 'OLD')
            before = book.path.read_bytes()
            with self.assertRaises(CallbackBudgetError): self.run_fake(journal=book)
            self.assertEqual(book.path.read_bytes(), before)
        self.assertEqual(self.calls, [])

    def test_callback_exception_is_charged_failed_stops_all_paths_without_retry_refund_or_tail(self):
        def failure(path, d, phase, value):
            if path == 'production_owned': raise RuntimeError('intentional synthetic failure')
            return value
        result = self.run_fake(callbacks=self.callbacks(failure))
        self.assertEqual(len(self.calls), 2)
        self.assertEqual([row['status'] for row in result['callback_ledger']], ['SUCCEEDED', 'FAILED'])
        self.assertEqual(result['callback_accounting']['entered'], 2)
        self.assertEqual(result['callback_accounting']['completed'], 1)
        self.assertEqual(result['callback_accounting']['failed'], 1)
        self.assertEqual(result['callback_accounting']['refunds'], 0)
        self.assertEqual(result['callback_accounting']['automatic_retries'], 0)
        self.assertEqual(result['callback_accounting']['tail_callbacks'], 0)
        self.assertEqual(result['journal']['pending_slots'], 0)
        self.assertTrue(all(row['state'] == 'CLOSED' for row in result['journal']['paths'].values()))
        self.assertEqual(len(result['snapshots']), 1)
        self.assertEqual(result['single_density_comparisons'], ())

    def test_keyboard_interrupt_is_charged_closed_and_propagated(self):
        book, callbacks = self.book(), self.callbacks()
        def interrupt(d, phase): raise KeyboardInterrupt()
        callbacks['production_copy'] = interrupt
        with self.assertRaises(KeyboardInterrupt): self.run_fake(journal=book, callbacks=callbacks)
        self.assertEqual(book.snapshot()['charged_slots'], 1)
        self.assertEqual(book.snapshot()['failed_slots'], 1)
        self.assertEqual(book.snapshot()['pending_slots'], 0)
        self.assertTrue(all(row['state'] == 'CLOSED' for row in book.snapshot()['paths'].values()))

    def test_same_prepared_object_cannot_reopen_with_fresh_book_and_completed_book_cannot_retry(self):
        family, book = self.family(), self.book()
        self.run_fake(prepared_seeds=family, journal=book)
        call_count = len(self.calls)
        new_book = self.book()
        with self.assertRaisesRegex(ValueError, 'same response-preparation object'):
            self.run_fake(prepared_seeds=family, journal=new_book)
        self.assertEqual(new_book.snapshot()['charged_slots'], 0)
        self.assertTrue(all(row['state'] == 'CLOSED' for row in new_book.snapshot()['paths'].values()))
        with self.assertRaises(CallbackBudgetError): self.run_fake(journal=book)
        self.assertEqual(len(self.calls), call_count)

    def test_saved_snapshot_and_receipts_are_immutable_and_later_callback_buffers_are_detached(self):
        shared = {}
        def reuse(path, d, phase, value): shared.update(value); return shared
        result = self.run_fake(callbacks=self.callbacks(reuse))
        saved = result['snapshots'][0]; f, d = saved['fock'].copy(), saved['density'].copy()
        shared['fock'][:] = 999; shared['raw_fock'][:] = 888
        np.testing.assert_array_equal(saved['fock'], f); np.testing.assert_array_equal(saved['density'], d)
        with self.assertRaises(ValueError): saved['fock'].setflags(write=True)
        with self.assertRaises(TypeError): saved['components']['nuclear_repulsion'] = 999
        with self.assertRaises(TypeError): result['callback_ledger'][0]['status'] = 'FAILED'
        self.assertEqual(saved['execution_kind'], 'ENGINEERING_FAKE')
        self.assertEqual(saved['operator_evidence_kind'], 'SYNTHETIC_CALLBACK_DECLARATION_NOT_MOLECULAR_F')

    def test_prepared_input_callback_argument_path_and_journal_configuration_mutations_stop_charged(self):
        for kind in ('requested_d', 'future_d', 'source_owner', 'overlap', 'mask', 'callback', 'journal'):
            with self.subTest(kind=kind):
                self.s, self.mask = np.eye(4), np.zeros((4, 4), dtype=bool)
                family, book = thaw(self.family()), self.book()
                callbacks = self.callbacks()
                def mutate(d, phase):
                    value = self.value(d)
                    if kind == 'requested_d': d[0, 0] += .01
                    elif kind == 'future_d': family['seeds'][3]['density'][0, 0] += .01
                    elif kind == 'source_owner': family['source_density'] = family['source_density'].copy()
                    elif kind == 'overlap': self.s[0, 0] += .01
                    elif kind == 'mask': self.mask[0, 0] = True
                    elif kind == 'callback': callbacks['production_owned'] = lambda dm, ph: self.value(dm)
                    else: book.identity['profile_sha256'] = 'e'*64
                    return value
                callbacks['production_copy'] = mutate
                result = self.run_fake(prepared_seeds=family, journal=book, callbacks=callbacks)
                self.assertEqual(result['callback_accounting']['precharged_slots'], 1)
                self.assertEqual(result['journal']['failed_slots'], 1)
                self.assertEqual(result['journal']['pending_slots'], 0)
                self.assertTrue(all(row['state'] == 'CLOSED' for row in result['journal']['paths'].values()))
                self.assertEqual(result['snapshots'], ())

    def test_wrong_wire_nonfinite_masked_f_raw_g_scalar_and_ledger_closure_fail_without_tail(self):
        for change in ({'density_id': 'b'*64}, {'operator_source': 'DIIS'},
                       {'fock': np.full((4, 4), np.nan)}, {'raw_fock': np.eye(4)},
                       {'total_energy': True}, {'grid_electron_count': float('inf')},
                       {'electronic_energy': 999.}, {'one_electron_energy': 999.},
                       {'masked_metric_electron_count': 999.}):
            with self.subTest(change=change):
                result = self.run_fake(callbacks=self.callbacks(lambda p, d, phase, value: dict(value, **change)))
                self.assertEqual(result['journal']['charged_slots'], 1)
                self.assertEqual(result['journal']['failed_slots'], 1)
                self.assertEqual(result['callback_accounting']['completed'], 1)
                self.assertEqual(result['callback_accounting']['failed'], 0)
                self.assertEqual(result['snapshots'], ())

    def test_diagnostic_gate_failure_preserves_valid_observations_and_same_d_mismatch_is_only_subset_failure(self):
        def disagree(path, d, phase, value):
            if path == 'independent_reference':
                f = value['fock'].copy(); f[0, 0] += 1e-8
                value.update(fock=f, raw_fock=f.copy())
            return value
        result = self.run_fake(callbacks=self.callbacks(disagree))
        self.assertEqual(result['status'], 'OCCUPIED_SPACE_SINGLE_F_RESPONSE_DIAGNOSTIC_COMPLETE')
        self.assertEqual(len(result['snapshots']), 12)
        self.assertTrue(any(not row['single_point_diagnostics']['qualified'] for row in result['snapshots']))
        self.assertEqual(result['single_density_comparison_status'], 'FAIL_SINGLE_D_OPERATOR_AND_ENERGY_SUBSET')
        self.assertEqual(sum(row['status'].startswith('FAIL_') for row in result['single_density_comparisons']), 4)
        self.assertFalse(result['engine_qualified']); self.assertFalse(result['research_qualified'])
        self.assertIsNone(result['delta_hartree'])
        self.assertEqual(result['comparison_status'], dict.fromkeys(('full_T05', 'UM-P12', 'UM-P13', 'T06'), 'NOT_EXECUTED'))


if __name__ == '__main__': unittest.main()
