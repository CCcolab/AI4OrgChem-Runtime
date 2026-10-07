"""Fake twelve-callback seed-family admission; no molecular workload."""
from pathlib import Path
import tempfile
import unittest

import numpy as np

from runtime.user_molecule import occupied_space_admission as admission
from runtime.user_molecule.occupied_space_seeds import prepare_occupied_space_seeds, array_identity
from runtime.user_molecule.occupation_response import density_id, OPERATOR_SOURCE, PATH_NAMES
from runtime.user_molecule.residual_budget import ConditionalCallbackBudget, CallbackBudgetError


def thaw(value):
    if isinstance(value, np.ndarray): return value.copy()
    if isinstance(value, dict): return {key: thaw(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)): return [thaw(item) for item in value]
    return value


class OccupiedSpaceAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.sequence, self.calls = 0, []
        self.s = np.eye(4)
        self.mask = np.zeros((4, 4), dtype=bool)

    def family(self):
        d = np.diag([2., 2., 0., 0.])
        return prepare_occupied_space_seeds(density=d, masked_overlap=self.s, electrons=4,
            occupied_anchor=np.array([0., 1., 0., 0.]), virtual_anchor=np.array([0., 0., 1., 0.]),
            angles=list(admission.REQUIRED_ANGLES), expected_density_id=density_id(d),
            expected_overlap_identity=array_identity(self.s))

    def book(self, **changes):
        self.sequence += 1
        args = dict(path=Path(self.directory.name)/('fake-admission-'+str(self.sequence)+'.json'),
            batch_id='fake-seed-'+str(self.sequence), identity={'mode': 'ENGINEERING_FAKE',
                'geometry_sha256': 'a'*64, 'profile_sha256': 'b'*64, 'dependencies_sha256': 'c'*64},
            path_limits={name: 4 for name in PATH_NAMES}, total_limit=12)
        args.update(changes)
        return ConditionalCallbackBudget(**args)

    def value(self, d):
        f = np.diag([-3., -2., 1., 2.])
        return {'density_id': density_id(d), 'operator_source': OPERATOR_SOURCE, 'fock': f, 'raw_fock': f.copy(),
            'one_electron_energy': 1., 'coulomb_energy': 2., 'exact_exchange_energy': -.2,
            'semilocal_xc_energy': -.8, 'nuclear_repulsion': .1, 'total_energy': 2.1, 'electronic_energy': 2.,
            'masked_metric_electron_count': float(np.trace(self.s@d)),
            'physical_metric_electron_count': 4.05, 'grid_electron_count': 4.06}

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
            electrons=4, matrix_delete_mask=self.mask, journal=self.book())
        args.update(changes)
        return admission.run_seed_admission_fake(**args)

    def test_twelve_calls_use_seed_outer_path_inner_and_every_charge_is_settled_closed(self):
        family = self.family()
        before = dict(admission.ENGINEERING_FAKE_CALLBACK_COUNTS)
        result = self.run_fake(prepared_seeds=family)
        expected = [(path, 'SINGLE_F_ENGINEERING_SEED_'+str(index), row['density_id'])
            for index, row in enumerate(family['seeds'], 1) for path in PATH_NAMES]
        self.assertEqual(self.calls, expected)
        self.assertEqual(result['status'], 'SINGLE_F_ENGINEERING_SEED_ADMISSION_COMPLETE')
        self.assertEqual(result['callback_accounting']['precharged_slots'], 12)
        self.assertEqual(result['callback_accounting']['entered'], 12)
        self.assertEqual(result['callback_accounting']['completed'], 12)
        self.assertEqual(result['callback_accounting']['failed'], 0)
        self.assertEqual(result['callback_accounting']['refunds'], 0)
        self.assertEqual(result['callback_accounting']['tail_callbacks'], 0)
        self.assertEqual(result['journal']['path_charged_slots'], {name: 4 for name in PATH_NAMES})
        self.assertEqual(result['journal']['pending_slots'], 0)
        self.assertTrue(all(row['status'] == 'SUCCEEDED' for row in result['callback_ledger']))
        self.assertTrue(all(row['state'] == 'CLOSED' for row in result['journal']['paths'].values()))
        self.assertEqual({name: admission.ENGINEERING_FAKE_CALLBACK_COUNTS[name]-before[name] for name in before},
            {'entered': 12, 'completed': 12, 'failed': 0})
        self.assertEqual(len(result['snapshots']), 12)

    def test_invalid_fourth_density_refuses_entire_family_before_first_callback(self):
        family = thaw(self.family())
        bad = np.diag([2., 1., 1., 0.])
        family['seeds'][3].update(density=bad, density_id=density_id(bad), density_identity=array_identity(bad))
        book = self.book()
        with self.assertRaises(ValueError): self.run_fake(prepared_seeds=family, journal=book)
        self.assertEqual(self.calls, [])
        self.assertEqual(book.snapshot()['charged_slots'], 0)
        self.assertTrue(all(row['state'] == 'CLOSED' for row in book.snapshot()['paths'].values()))

    def test_forged_seed_or_source_identity_and_duplicate_density_ids_refuse_before_callback(self):
        for kind in ('seed_id', 'array_id', 'source_id', 'forged_base_digest', 'base_bytes', 'base_overlap_bytes', 'anchor_bytes', 'duplicate'):
            with self.subTest(kind=kind):
                family = thaw(self.family())
                if kind == 'seed_id': family['seeds'][0]['density_id'] = 'a'*64
                elif kind == 'array_id': family['seeds'][0]['density_identity']['sha256'] = 'a'*64
                elif kind == 'source_id': family['source']['expected_density_id'] = 'a'*64
                elif kind == 'forged_base_digest':
                    family['source']['density_id'] = family['source']['expected_density_id'] = 'a'*64
                elif kind == 'base_bytes': family['source_density'] = np.diag([2., 0., 2., 0.])
                elif kind == 'base_overlap_bytes': family['source_masked_overlap'] = 1.01*np.eye(4)
                elif kind == 'anchor_bytes': family['source_occupied_anchor'] = np.array([1., 0., 0., 0.])
                else:
                    source = family['seeds'][0]
                    family['seeds'][3].update(density=source['density'].copy(), density_id=source['density_id'],
                        density_identity=source['density_identity'])
                book = self.book()
                with self.assertRaises(ValueError): self.run_fake(prepared_seeds=family, journal=book)
                self.assertEqual(book.snapshot()['charged_slots'], 0)
        self.assertEqual(self.calls, [])

    def test_changed_overlap_source_and_original_mask_count_rules_refuse_before_callback(self):
        family = self.family()
        changed_s = self.s.copy(); changed_s[0, 0] = 1.01
        for changes in ({'overlap': changed_s}, {'electrons': True}, {'electrons': 2},
                        {'matrix_delete_mask': np.eye(4, dtype=bool)},
                        {'matrix_delete_mask': np.zeros((4, 4), dtype=int)}):
            with self.subTest(changes=changes):
                book = self.book()
                with self.assertRaises(ValueError):
                    self.run_fake(prepared_seeds=thaw(family), journal=book, **changes)
                self.assertEqual(book.snapshot()['charged_slots'], 0)
        self.assertEqual(self.calls, [])

    def test_callback_failure_charges_failed_slot_and_stops_without_tail_retry_or_refund(self):
        def fail(path, d, phase, value):
            if path == 'production_owned': raise RuntimeError('controlled fake callback fault')
            return value
        result = self.run_fake(callbacks=self.callbacks(fail))
        self.assertEqual(result['status'], 'SINGLE_F_ENGINEERING_SEED_ADMISSION_REFUSED')
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(result['callback_accounting']['entered'], 2)
        self.assertEqual(result['callback_accounting']['completed'], 1)
        self.assertEqual(result['callback_accounting']['failed'], 1)
        self.assertEqual(result['callback_accounting']['automatic_retries'], 0)
        self.assertEqual([row['status'] for row in result['callback_ledger']], ['SUCCEEDED', 'FAILED'])
        self.assertEqual(len(result['snapshots']), 1)
        self.assertEqual(result['journal']['pending_slots'], 0)
        self.assertTrue(all(row['state'] == 'CLOSED' for row in result['journal']['paths'].values()))

    def test_same_preparation_object_and_used_journal_cannot_be_reused(self):
        family, book = self.family(), self.book()
        self.run_fake(prepared_seeds=family, journal=book)
        original_calls = len(self.calls)
        fresh = self.book()
        with self.assertRaisesRegex(ValueError, 'same prepared family object'):
            self.run_fake(prepared_seeds=family, journal=fresh)
        self.assertEqual(fresh.snapshot()['charged_slots'], 0)
        self.assertTrue(all(row['state'] == 'CLOSED' for row in fresh.snapshot()['paths'].values()))
        with self.assertRaises(CallbackBudgetError): self.run_fake(journal=book)
        self.assertEqual(len(self.calls), original_calls)

    def test_real_former_nine_probe_mode_wrong_angle_order_or_limits_refuse_first_callback(self):
        for mode in ('PREPARED_SINGLE_F_RESPONSE_DIAGNOSTIC', 'PREPARED_MOLECULAR_DIAGNOSTIC', 'PREPARED_SEED_V2', True):
            with self.subTest(mode=mode), self.assertRaises(ValueError): self.run_fake(execution_kind=mode)
        family = thaw(self.family()); family['angles_rad'] = [.1, -.1, .25, -.25]
        with self.assertRaises(ValueError): self.run_fake(prepared_seeds=family)
        with self.assertRaises(ValueError): self.run_fake(prepared_seeds={'status': 'SINGLE_F_RESPONSE_DIAGNOSTIC_COMPLETE'})
        nine = self.book(path_limits={name: 3 for name in PATH_NAMES}, total_limit=9)
        with self.assertRaises(CallbackBudgetError): self.run_fake(journal=nine)
        self.assertEqual(self.calls, [])

    def test_snapshot_and_input_copies_survive_later_buffer_changes_and_are_immutable(self):
        family = self.family()
        source_id, source_s = family['source']['density_id'], self.s.copy()
        shared = {}
        def reuse(path, d, phase, value):
            shared.update(value)
            return shared
        result = self.run_fake(prepared_seeds=family, callbacks=self.callbacks(reuse))
        saved = result['snapshots'][0]; original_f, original_d = saved['fock'].copy(), saved['density'].copy()
        shared['fock'][:] = 999; shared['raw_fock'][:] = 888
        np.testing.assert_array_equal(saved['fock'], original_f)
        np.testing.assert_array_equal(saved['density'], original_d)
        np.testing.assert_array_equal(self.s, source_s)
        self.assertEqual(family['source']['density_id'], source_id)
        with self.assertRaises(ValueError): saved['fock'].setflags(write=True)
        with self.assertRaises(TypeError): saved['components']['one_electron_energy'] = 0
        with self.assertRaises(TypeError): result['callback_ledger'][0]['status'] = 'FAILED'
        self.assertEqual(saved['role'], admission.SNAPSHOT_ROLE)
        self.assertEqual(saved['execution_kind'], 'ENGINEERING_FAKE')
        self.assertEqual(saved['operator_evidence_kind'], 'SYNTHETIC_CALLBACK_DECLARATION_NOT_MOLECULAR_F')
        self.assertFalse(saved['single_point_diagnostics']['full_endpoint_qualified'])

    def test_exact_recipe_refuses_synced_hash_swaps_other_projectors_and_changed_anchor_or_derived_records(self):
        baseline = self.family()
        verified = admission._preflight(baseline, self.s, 4, self.mask)
        self.assertEqual(verified[-1], admission._digest(baseline))
        for kind in ('swap', 'different_projector', 'anchor_and_identity', 'derived_record'):
            with self.subTest(kind=kind):
                family = thaw(baseline)
                if kind == 'swap':
                    first, second = family['seeds'][:2]
                    for field in ('density', 'density_id', 'density_identity'):
                        first[field], second[field] = second[field], first[field]
                elif kind == 'different_projector':
                    d = np.diag([2., 0., 0., 2.])
                    family['seeds'][0].update(density=d, density_id=density_id(d), density_identity=array_identity(d))
                elif kind == 'anchor_and_identity':
                    a = np.array([1., 0., 0., 0.])
                    family['source_occupied_anchor'] = a
                    family['source']['occupied_anchor_identity'] = array_identity(a)
                else: family['directions']['occupied_projection_norm'] *= 2
                book = self.book()
                with self.assertRaisesRegex(ValueError, 'exact source/anchor/angle recipe'):
                    self.run_fake(prepared_seeds=family, journal=book)
                self.assertEqual(book.snapshot()['charged_slots'], 0)
                self.assertTrue(all(row['state'] == 'CLOSED' for row in book.snapshot()['paths'].values()))
        self.assertEqual(self.calls, [])

    def test_keyboard_interrupt_is_charged_failed_closes_every_path_and_propagates(self):
        book = self.book()
        callbacks = self.callbacks()
        def interrupt(density, phase): raise KeyboardInterrupt()
        callbacks['production_copy'] = interrupt
        before = dict(admission.ENGINEERING_FAKE_CALLBACK_COUNTS)
        with self.assertRaises(KeyboardInterrupt): self.run_fake(callbacks=callbacks, journal=book)
        self.assertEqual(book.snapshot()['charged_slots'], 1)
        self.assertEqual(book.snapshot()['failed_slots'], 1)
        self.assertEqual(book.snapshot()['pending_slots'], 0)
        self.assertTrue(all(row['state'] == 'CLOSED' for row in book.snapshot()['paths'].values()))
        self.assertEqual({key: admission.ENGINEERING_FAKE_CALLBACK_COUNTS[key]-before[key] for key in before},
            {'entered': 1, 'completed': 0, 'failed': 1})

    def test_callback_bad_wire_argument_and_prepared_owner_mutations_are_charged_then_stopped(self):
        for kind in ('argument', 'prepared', 'source_ref', 'overlap', 'mask', 'wrong_id', 'false_energy', 'false_raw_g'):
            with self.subTest(kind=kind):
                self.s, self.mask = np.eye(4), np.zeros((4, 4), dtype=bool)
                family = thaw(self.family())
                def invalid(path, d, phase, value):
                    if kind == 'argument': d[0, 0] += .01
                    elif kind == 'prepared': family['seeds'][3]['density'][0, 0] += .01
                    elif kind == 'source_ref': family['source_density'] = family['source_density'].copy()
                    elif kind == 'overlap': self.s[0, 0] += .01
                    elif kind == 'mask': self.mask[0, 0] = True
                    elif kind == 'wrong_id': value['density_id'] = 'a'*64
                    elif kind == 'false_energy': value['total_energy'] = True
                    else: value['raw_fock'][0, 0] += .1
                    return value
                result = self.run_fake(prepared_seeds=family, callbacks=self.callbacks(invalid))
                self.assertEqual(result['callback_accounting']['precharged_slots'], 1)
                self.assertEqual(result['callback_accounting']['completed'], 1)
                self.assertEqual(result['callback_accounting']['failed'], 0)
                self.assertEqual(result['journal']['failed_slots'], 1)
                self.assertEqual(result['snapshots'], ())

    def test_native_counts_remain_unobserved_and_no_scientific_root_or_delta_is_claimed(self):
        result = self.run_fake()
        self.assertEqual(result['native_execution_counts'], {'status': 'UNOBSERVED_ENGINEERING_GUARD_REQUIRED',
            'true_F': None, 'nr_rks': None})
        self.assertEqual(result['callback_accounting']['counter_kind'], 'WRAPPER_ENTRIES_NOT_NATIVE_F_OR_NR_OBSERVATIONS')
        self.assertFalse(result['engine_qualified']); self.assertFalse(result['research_qualified'])
        self.assertFalse(result['compute_enabled']); self.assertFalse(result['production_activation'])
        self.assertFalse(result['ordinary_occupied_space_preservation_claim'])
        self.assertEqual(result['root_acceptance'], 'NOT_EXECUTED')
        self.assertIsNone(result['delta_hartree'])
        self.assertEqual(result['comparison_status'], dict.fromkeys(('full_T05', 'UM-P12', 'UM-P13', 'T06'), 'NOT_EXECUTED'))


if __name__ == '__main__': unittest.main()
