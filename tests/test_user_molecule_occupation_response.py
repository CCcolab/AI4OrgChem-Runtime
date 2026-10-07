"""Prepared single-F orchestration tests; synthetic matrices only."""
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest

import numpy as np

from runtime.user_molecule import occupation_response as response
from runtime.user_molecule.residual_budget import ConditionalCallbackBudget, CallbackBudgetError


class OccupationResponseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.sequence = 0
        self.s = np.eye(4)
        self.mask = np.zeros((4, 4), dtype=bool)
        a, b = np.diag([2., 2., 0., 0.]), np.diag([2., 0., 2., 0.])
        c = np.zeros((4, 4)); c[0, 0] = 2; c[1:3, 1:3] = 1
        self.probes = dict(zip(response.PROBE_NAMES, (a, b, c)))
        self.calls = []

    def book(self, **changes):
        self.sequence += 1
        arguments = dict(path=Path(self.directory.name)/('journal-'+str(self.sequence)+'.json'),
            batch_id='response-fake-'+str(self.sequence), identity={
                'mode': 'ENGINEERING_FAKE_SINGLE_F_RESPONSE',
                'geometry_sha256': hashlib.sha256(b'SYNTHETIC_ARRAY_FIXTURE_NOT_MOLECULE').hexdigest(),
                'profile_sha256': hashlib.sha256(b'SYNTHETIC_FAKE_PROFILE').hexdigest(),
                'dependencies_sha256': hashlib.sha256(b'SYNTHETIC_FAKE_DEPENDENCIES').hexdigest()},
            path_limits={name: 3 for name in response.PATH_NAMES}, total_limit=9)
        arguments.update(changes)
        return ConditionalCallbackBudget(**arguments)

    def value(self, density, **changes):
        value = {'density_id': response.density_id(density), 'operator_source': response.OPERATOR_SOURCE,
            'fock': np.diag([-3., -2., 1., 2.]), 'raw_fock': np.diag([-3., -2., 1., 2.]),
            'one_electron_energy': 1., 'coulomb_energy': 2., 'exact_exchange_energy': -.2,
            'semilocal_xc_energy': -.8, 'nuclear_repulsion': .1,
            'total_energy': 2.1, 'electronic_energy': 2.,
            'masked_metric_electron_count': float(np.trace(self.s@density)),
            'physical_metric_electron_count': 4.05, 'grid_electron_count': 4.06}
        value.update(changes)
        return value

    def callbacks(self, transform=None):
        result = {}
        for path in response.PATH_NAMES:
            def callback(density, phase, path=path):
                self.calls.append((path, phase, response.density_id(density)))
                value = self.value(density)
                return value if transform is None else transform(path, density, phase, value)
            result[path] = callback
        return result

    def run_probe(self, **changes):
        arguments = dict(probes=self.probes, callbacks=self.callbacks(), overlap=self.s,
            electrons=4, matrix_delete_mask=self.mask, journal=self.book())
        arguments.update(changes)
        return response.run_response_probe(**arguments)

    def test_zero_f_preflight_returns_all_metrics_and_independent_readonly_copies(self):
        before = dict(response.ENGINEERING_FAKE_CALLBACK_COUNTS)
        original = {name: value.copy() for name, value in self.probes.items()}
        result = response.preflight_response_probes(probes=self.probes, overlap=self.s,
            electrons=4, matrix_delete_mask=self.mask)
        self.assertEqual(result['status'], 'PASS_PURE_ARRAY_RESPONSE_PROBE_READINESS')
        self.assertEqual(set(result['admissions']), set(response.PROBE_NAMES))
        self.assertEqual(result['functional_calls'], 0)
        self.assertFalse(result['scientific_execution_authorized'])
        self.assertFalse(result['repairs_performed'])
        for name in response.PROBE_NAMES:
            metrics = result['admissions'][name]
            self.assertAlmostEqual(metrics['masked_metric_electron_count'], 4)
            self.assertLessEqual(metrics['whitened_trace_error'], 1e-10)
            self.assertLessEqual(metrics['whitened_absolute_idempotency'], 1e-10)
            self.assertLessEqual(metrics['production_density_reconstruction_relative'], 1e-10)
            self.assertEqual(result['density_ids'][name], response.density_id(original[name]))
            np.testing.assert_array_equal(result['density_copies'][name], original[name])
            self.assertFalse(np.shares_memory(result['density_copies'][name], self.probes[name]))
            with self.assertRaises(ValueError): result['density_copies'][name].setflags(write=True)
        self.assertEqual(result['matrix_delete_mask'].dtype.kind, 'b')
        self.probes['AO_ANCHOR_A'][0, 0] = 999
        np.testing.assert_array_equal(result['density_copies']['AO_ANCHOR_A'], original['AO_ANCHOR_A'])
        self.assertEqual(response.ENGINEERING_FAKE_CALLBACK_COUNTS, before)
        self.assertEqual(self.calls, [])
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    def test_zero_f_preflight_bad_third_probe_refuses_without_input_mutation_or_journal(self):
        self.probes['AO_ANCHOR_SYMMETRIC_SUM'] = np.diag([2., 1., 1., 0.])
        original = {name: value.copy() for name, value in self.probes.items()}
        before = dict(response.ENGINEERING_FAKE_CALLBACK_COUNTS)
        overlap, mask = self.s.copy(), self.mask.copy()
        with self.assertRaises(ValueError):
            response.preflight_response_probes(probes=self.probes, overlap=self.s,
                electrons=4, matrix_delete_mask=self.mask)
        for name, value in original.items(): np.testing.assert_array_equal(self.probes[name], value)
        np.testing.assert_array_equal(self.s, overlap)
        np.testing.assert_array_equal(self.mask, mask)
        self.assertEqual(response.ENGINEERING_FAKE_CALLBACK_COUNTS, before)
        self.assertEqual(self.calls, [])
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    def test_exact_nine_calls_in_probe_then_path_order_and_closed_accounting(self):
        result = self.run_probe()
        expected = [(path, 'SINGLE_F_RESPONSE_'+probe, response.density_id(self.probes[probe]))
            for probe in response.PROBE_NAMES for path in response.PATH_NAMES]
        self.assertEqual(self.calls, expected)
        self.assertEqual(result['status'], 'SINGLE_F_RESPONSE_DIAGNOSTIC_COMPLETE')
        self.assertEqual(len(result['snapshots']), 9)
        self.assertEqual(result['callback_accounting'], dict(precharged_slots=9, entered=9,
            completed=9, failed=0, refunds=0, automatic_retries=0,
            counter_kind='WRAPPER_ENTRIES_NOT_NATIVE_F_OR_NR_OBSERVATIONS'))
        self.assertEqual(result['journal']['path_charged_slots'], {name: 3 for name in response.PATH_NAMES})
        self.assertEqual(result['journal']['pending_slots'], 0)
        self.assertTrue(all(row['status'] == 'SUCCEEDED' for row in result['journal']['slots']))
        self.assertTrue(all(row['state'] == 'CLOSED' for row in result['journal']['paths'].values()))
        self.assertFalse(result['engine_qualified']); self.assertFalse(result['compute_enabled'])
        self.assertIsNone(result['delta_hartree'])
        self.assertEqual(result['comparison_status'], dict.fromkeys(('UM-P12', 'UM-P13', 'T06', 'full_T05'), 'NOT_EXECUTED'))

    def test_old_used_closed_or_repeated_journal_refused_before_any_new_callback(self):
        for state in ('charged', 'closed', 'repeated'):
            with self.subTest(state=state):
                book = self.book()
                if state == 'charged': book.charge(response.PATH_NAMES[0], 'a'*64, 'OLD')
                elif state == 'closed': book.close_path(response.PATH_NAMES[0], 'OLD')
                else: self.run_probe(journal=book)
                before = len(self.calls)
                with self.assertRaises(CallbackBudgetError): self.run_probe(journal=book)
                self.assertEqual(len(self.calls), before)

    def test_nonexact_path_or_total_allowances_refused_without_callback(self):
        for change in ({'total_limit': 8}, {'path_limits': {name: 2 for name in response.PATH_NAMES}, 'total_limit': 6},
                       {'path_limits': {'other': 3}, 'total_limit': 3}):
            with self.subTest(change=change), self.assertRaises(CallbackBudgetError):
                self.run_probe(journal=self.book(**change))
        self.assertEqual(self.calls, [])

    def test_all_densities_validate_before_first_callback_and_preflight_closes_book(self):
        invalid = [np.full((4, 4), np.nan), np.ones((3, 3)), np.eye(4, dtype=complex),
            np.eye(4, dtype=bool), np.diag([2., 1., 1., 0.]), np.diag([2., 2., 2., -2.])]
        asymmetric = np.diag([2., 2., 0., 0.]); asymmetric[0, 1] = 1e-8
        invalid.append(asymmetric)
        for value in invalid:
            with self.subTest(value=value):
                book = self.book()
                probes = dict(self.probes, AO_ANCHOR_SYMMETRIC_SUM=value)
                with self.assertRaises(ValueError): self.run_probe(probes=probes, journal=book)
                self.assertEqual(book.snapshot()['charged_slots'], 0)
                self.assertTrue(all(row['state'] == 'CLOSED' for row in book.snapshot()['paths'].values()))
        self.assertEqual(self.calls, [])

    def test_original_metric_projector_admission_and_distinct_count_measures(self):
        self.s = np.diag([4., 2., 3., 1.])
        inverse = np.diag(1/np.sqrt(np.diag(self.s)))
        self.probes = {name: inverse@density@inverse for name, density in self.probes.items()}
        result = self.run_probe()
        self.assertEqual(result['status'], 'SINGLE_F_RESPONSE_DIAGNOSTIC_COMPLETE')
        for metrics in result['admissions'].values():
            self.assertAlmostEqual(metrics['masked_metric_electron_count'], 4)
            self.assertLessEqual(metrics['whitened_trace_error'], 1e-10)
            self.assertLessEqual(metrics['whitened_absolute_idempotency'], 1e-10)
            self.assertLessEqual(metrics['production_density_reconstruction_relative'], 1e-10)
        first = result['snapshots'][0]
        self.assertEqual(first['physical_metric_electron_count'], 4.05)
        self.assertEqual(first['grid_electron_count'], 4.06)
        bad = dict(self.probes, AO_ANCHOR_B=np.diag([2., 0., 2., 0.]))
        count = len(self.calls)
        with self.assertRaises(ValueError): self.run_probe(probes=bad)
        self.assertEqual(len(self.calls), count)

    def test_overlap_electrons_mask_and_name_preflight_refusals(self):
        for change in ({'overlap': np.diag([1., 1., 1., 0.])}, {'electrons': True}, {'electrons': 3},
                       {'electrons': 8}, {'matrix_delete_mask': np.zeros((4, 4), dtype=int)},
                       {'matrix_delete_mask': np.eye(4, dtype=bool)}, {'probes': {'OTHER': np.eye(4)}},
                       {'callbacks': {'OTHER': lambda d, p: None}}, {'execution_kind': 'PREPARED_MOLECULAR_DIAGNOSTIC'}):
            with self.subTest(change=change), self.assertRaises(ValueError): self.run_probe(**change)
        self.assertEqual(self.calls, [])

    def test_callback_argument_mutation_consumes_one_failed_slot_and_stops_batch(self):
        def mutate(path, density, phase, value):
            density[0, 0] += .01
            return value
        result = self.run_probe(callbacks=self.callbacks(mutate))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(result['journal']['failed_slots'], 1)
        self.assertEqual(result['journal']['charged_slots'], 1)
        self.assertEqual(result['callback_accounting']['completed'], 1)
        self.assertEqual(result['callback_accounting']['failed'], 0)
        self.assertEqual(result['status'], 'SINGLE_F_RESPONSE_DIAGNOSTIC_REFUSED')

    def test_mutation_of_other_frozen_input_or_callback_mapping_is_refused(self):
        for target in ('future_density', 'overlap', 'mask', 'replace_probe', 'replace_callback'):
            with self.subTest(target=target):
                originals = {name: a.copy() for name, a in self.probes.items()}
                self.s, self.mask = np.eye(4), np.zeros((4, 4), dtype=bool)
                callbacks = self.callbacks()
                def mutate(density, phase):
                    if target == 'future_density': self.probes['AO_ANCHOR_B'][0, 0] += .01
                    elif target == 'overlap': self.s[0, 0] += .01
                    elif target == 'mask': self.mask[0, 0] = True
                    elif target == 'replace_probe': self.probes['AO_ANCHOR_B'] = self.probes['AO_ANCHOR_B'].copy()
                    else: callbacks['production_owned'] = lambda d, p: self.value(d)
                    return self.value(density)
                callbacks['production_copy'] = mutate
                result = self.run_probe(callbacks=callbacks)
                self.assertEqual(result['journal']['charged_slots'], 1)
                self.assertEqual(result['journal']['failed_slots'], 1)
                self.probes = originals

    def test_wrong_identity_provenance_nonfinite_and_boolean_results_stop_charged(self):
        changes = [{'density_id': 'b'*64}, {'operator_source': 'DIIS'}, {'fock': np.full((4, 4), np.nan)},
            {'raw_fock': None}, {'density': np.eye(4)}, {'grid_electron_count': float('inf')},
            {'total_energy': True}, {'masked_metric_electron_count': np.bool_(True)},
            {'one_electron_energy': 1j}, {'J': np.ones((3, 3))}]
        for change in changes:
            with self.subTest(change=change):
                result = self.run_probe(callbacks=self.callbacks(lambda p, d, phase, v: dict(v, **change)))
                self.assertEqual(result['journal']['charged_slots'], 1)
                self.assertEqual(result['journal']['failed_slots'], 1)
                self.assertEqual(result['callback_accounting']['completed'], 1)
                self.assertEqual(len(result['snapshots']), 0)

    def test_bad_energy_ledger_and_false_masked_count_are_refused(self):
        for change in ({'one_electron_energy': 1.01}, {'electronic_energy': 2.01},
                       {'masked_metric_electron_count': 4.01}):
            with self.subTest(change=change):
                result = self.run_probe(callbacks=self.callbacks(lambda p, d, phase, v: dict(v, **change)))
                self.assertEqual(result['journal']['failed_slots'], 1)
                self.assertEqual(result['status'], 'SINGLE_F_RESPONSE_DIAGNOSTIC_REFUSED')

    def test_f_mask_and_raw_g_projection_are_checked_without_masking_d(self):
        self.mask[1, 2] = self.mask[2, 1] = True
        g = np.diag([-3., -2., 1., 2.]); g[1, 2] = g[2, 1] = .4
        result = self.run_probe(callbacks=self.callbacks(lambda p, d, phase, v: dict(v, raw_fock=g)))
        self.assertEqual(result['status'], 'SINGLE_F_RESPONSE_DIAGNOSTIC_COMPLETE')
        self.assertEqual(result['snapshots'][6]['density'][1, 2], 1.)
        for change in ({'fock': g}, {'raw_fock': np.diag([-3., -2., 1., 2.1])}):
            with self.subTest(change=change):
                result = self.run_probe(callbacks=self.callbacks(lambda p, d, phase, v: dict(v, **change)))
                self.assertEqual(result['journal']['failed_slots'], 1)

    def test_callback_failure_keeps_prior_slots_and_never_retries_or_completes_batch(self):
        def fail(path, density, phase, value):
            if path == 'production_owned': raise RuntimeError('synthetic failure before native work')
            return value
        result = self.run_probe(callbacks=self.callbacks(fail))
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(result['callback_accounting']['entered'], 2)
        self.assertEqual(result['callback_accounting']['completed'], 1)
        self.assertEqual(result['callback_accounting']['failed'], 1)
        self.assertEqual([row['status'] for row in result['journal']['slots']], ['SUCCEEDED', 'FAILED'])
        self.assertEqual(result['journal']['pending_slots'], 0)
        self.assertEqual(len(result['snapshots']), 1)
        self.assertEqual(result['single_density_comparisons'], ())
        self.assertTrue(all(row['state'] == 'CLOSED' for row in result['journal']['paths'].values()))

    def test_keyboard_interrupt_is_charged_and_paths_closed_then_propagated(self):
        book = self.book()
        def interrupt(density, phase): raise KeyboardInterrupt()
        callbacks = self.callbacks(); callbacks['production_copy'] = interrupt
        with self.assertRaises(KeyboardInterrupt): self.run_probe(callbacks=callbacks, journal=book)
        self.assertEqual(book.snapshot()['failed_slots'], 1)
        self.assertEqual(book.snapshot()['pending_slots'], 0)
        self.assertTrue(all(row['state'] == 'CLOSED' for row in book.snapshot()['paths'].values()))

    def test_snapshot_copies_are_immutable_even_if_callback_reuses_buffers(self):
        shared = self.value(self.probes['AO_ANCHOR_A'])
        def reuse(path, density, phase, value):
            shared.update(value)
            shared['J'] = np.eye(4)
            return shared
        result = self.run_probe(callbacks=self.callbacks(reuse))
        saved = result['snapshots'][0]
        original = saved['fock'].copy()
        shared['fock'][:] = 999
        shared['raw_fock'][:] = 888
        shared['J'][:] = 777
        np.testing.assert_array_equal(saved['fock'], original)
        np.testing.assert_array_equal(saved['optional_matrices']['J'], np.eye(4))
        with self.assertRaises(ValueError): saved['fock'].setflags(write=True)
        with self.assertRaises(ValueError): saved['density'][0, 0] = 0
        with self.assertRaises(TypeError): saved['components']['one_electron_energy'] = 0
        with self.assertRaises(TypeError): saved['density_id'] = 'e'*64

    def test_operator_identity_independently_binds_density_f_g_and_all_energies(self):
        snapshot = self.run_probe()['snapshots'][0]
        raw = (b'AI4OrgChem-single-F-response-operator-v1\0'
            + bytes.fromhex(snapshot['density_id'])+bytes.fromhex(snapshot['fock_id'])
            + bytes.fromhex(snapshot['raw_fock_id'])
            + struct.pack('<6d', snapshot['total_energy'], *(snapshot['components'][name] for name in response.COMPONENTS))
            + response.OPERATOR_SOURCE.encode('ascii'))
        self.assertEqual(snapshot['operator_id'], hashlib.sha256(raw).hexdigest())
        changes = dict(snapshot['components']); changes['nuclear_repulsion'] += .01
        self.assertNotEqual(snapshot['operator_id'], response.operator_id(snapshot['density_id'], snapshot['fock'],
            snapshot['raw_fock'], changes, snapshot['total_energy']))

    def test_same_density_comparison_is_subset_and_mismatch_never_grants_endpoint_equivalence(self):
        def differ(path, density, phase, value):
            if path == 'independent_reference':
                f = value['fock'].copy(); f[0, 0] += 1e-8
                value.update(fock=f, raw_fock=f)
            return value
        result = self.run_probe(callbacks=self.callbacks(differ))
        self.assertEqual(result['status'], 'SINGLE_F_RESPONSE_DIAGNOSTIC_COMPLETE')
        self.assertEqual(len(result['single_density_comparisons']), 6)
        self.assertEqual(sum(row['status'].startswith('FAIL') for row in result['single_density_comparisons']), 3)
        self.assertTrue(all(row['full_T05'] == 'NOT_EXECUTED' for row in result['single_density_comparisons']))
        gate = result['snapshots'][0]['single_point_diagnostics']
        self.assertTrue(gate['qualified'])  # Pure-array single-point predicate only.
        self.assertFalse(gate['full_endpoint_qualified'])
        self.assertEqual(gate['mapped_density_true_operator_recheck'], 'NOT_EXECUTED')
        self.assertFalse(result['engine_qualified']); self.assertFalse(result['comparison_available'])

    def test_fake_counts_are_entries_and_real_declaration_has_unobserved_native_counts(self):
        before = dict(response.ENGINEERING_FAKE_CALLBACK_COUNTS)
        fake = self.run_probe()
        self.assertEqual({name: response.ENGINEERING_FAKE_CALLBACK_COUNTS[name]-before[name] for name in before},
            {'entered': 9, 'completed': 9, 'failed': 0})
        self.assertEqual(fake['native_execution_counts']['true_F'], 0)
        before = dict(response.ENGINEERING_FAKE_CALLBACK_COUNTS)
        real = self.run_probe(execution_kind='PREPARED_SINGLE_F_RESPONSE_DIAGNOSTIC')
        self.assertEqual(response.ENGINEERING_FAKE_CALLBACK_COUNTS, before)
        self.assertIsNone(real['engineering_fake_callback_counts'])
        self.assertEqual(real['native_execution_counts']['status'], 'UNOBSERVED_WORKER_MUST_SUPPLY')
        self.assertIsNone(real['native_execution_counts']['true_F'])
        self.assertIsNone(real['native_execution_counts']['nr_rks'])
        self.assertEqual(real['callback_accounting']['precharged_slots'], 9)
        self.assertEqual(real['solver_iterations'], 0)
        self.assertEqual(real['jacobian_evaluations'], 0)
        self.assertFalse(real['scientific_approval']); self.assertFalse(real['research_qualified'])


if __name__ == '__main__':
    unittest.main()
