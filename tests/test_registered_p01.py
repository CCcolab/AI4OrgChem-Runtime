"""Array/fixed fake-PySCF API tests only; no real PySCF, molecule, NR or container."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
from runtime.registered_cases import p01


def authorization():
    return {'schema': 'registered-case-execution-v1', 'task': p01.TASK, 'protocol_id': p01.PROTOCOL_ID,
        'scientific_execution_authorized': True, 'scf_kernel_call_limit': 1, 'boys_kernel_call_limit': 1,
        'pipek_mezey_kernel_call_limit': 1, 'maximum_processes': 1, 'threads': 1,
        'memory_limit_bytes': 1073741824, 'wall_time_limit_seconds': 120, 'stop_after_seconds': 100,
        'p01_protocol_sha256': p01.PROTOCOL_SHA256, 'runtime_commit': 'ab' * 20,
        'source_snapshot_sha256': 'cd' * 32, 'execution_id': 'ef' * 16}


class ToyEngine:
    def __init__(self, fault=None, converged=True, localize=True):
        self.calls = {'scf': 0, 'boys': 0, 'pm': 0, 'energy': 0, 'threads': []}
        self.fault = fault; self.localize = localize
        self.local = np.eye(16)[:, [0, 1, 2, 3, 4, 5, 6, 7]]
        rotation = np.block([[np.eye(4), np.eye(4)], [np.eye(4), -np.eye(4)]]) / np.sqrt(2)
        self.occupied = self.local @ rotation
        self.mf = SimpleNamespace(mo_coeff=np.column_stack((self.occupied, np.eye(16)[:, 8:])),
            mo_occ=np.array([2.] * 8 + [0.] * 8), converged=converged, cycles=3,
            kernel=self.kernel, get_ovlp=lambda: np.eye(16), energy_tot=self.energy)
        self.mol = SimpleNamespace(nelectron=16, energy_nuc=lambda: 1.,
            aoslice_by_atom=lambda: np.array([[0, 0, 0, 4], [0, 0, 4, 8], [0, 0, 8, 10],
                [0, 0, 10, 12], [0, 0, 12, 14], [0, 0, 14, 16]]))
        self.api = {'gto': SimpleNamespace(M=self.build), 'lib': SimpleNamespace(num_threads=self.calls['threads'].append),
            'scf': SimpleNamespace(RHF=lambda mol: self.mf), 'lo': SimpleNamespace(Boys=self.boys, PM=self.pm),
            'version': 'ENGINEERING_FAKE_NOT_PYSCF'}

    def build(self, **kwargs):
        if kwargs['atom'] != [(r[0], tuple(r[1:])) for r in p01.GEOMETRY]: raise AssertionError('Geometry changed')
        if (kwargs['basis'], kwargs['unit'], kwargs['charge'], kwargs['spin'], kwargs['symmetry']) != ('6-31G(d)', 'Angstrom', 0, 0, False):
            raise AssertionError('Method inputs changed')
        return self.mol

    def kernel(self):
        self.calls['scf'] += 1
        if self.fault == 'scf': raise RuntimeError('toy scf fault')
        return -10.

    def energy(self, *, dm):
        self.calls['energy'] += 1
        return -10. + .1 * (np.trace(dm) - 16.)

    def localizer(self, name, mol, occupied):
        if not np.array_equal(occupied, self.occupied): raise AssertionError('Canonical occupied changed')
        def kernel():
            self.calls[name] += 1
            if self.fault == name: raise RuntimeError('toy ' + name + ' fault')
            return (self.local if self.localize else self.occupied).copy()
        obj = SimpleNamespace(kernel=kernel)
        setattr(self, name + '_solver', obj)
        return obj

    def boys(self, mol, occupied): return self.localizer('boys', mol, occupied)
    def pm(self, mol, occupied): return self.localizer('pm', mol, occupied)


class RegisteredP01Tests(unittest.TestCase):
    def fake_run(self, output, toy=None, auth=None):
        toy = toy or ToyEngine()
        result = p01._execute(output, authorization=auth or authorization(),
            engine_factory=lambda: toy.api, execution_kind='ENGINEERING_FAKE')
        return result, toy

    def test_frozen_source_includes_raw_protocol_untracked_driver_and_notices(self):
        meta = p01.verify_frozen_source()
        sources = {row['path']: row for row in meta['sources']}
        self.assertEqual(len(sources), 8)
        self.assertEqual(sources[p01.PROTOCOL_PATH]['sha256'], p01.PROTOCOL_SHA256)
        self.assertFalse(sources[p01.PROTOCOL_PATH]['origin_tracked'])
        self.assertIsNone(sources[p01.PROTOCOL_PATH]['origin_head_git_blob'])
        self.assertIn('LICENSE', sources); self.assertIn('NOTICE', sources)
        self.assertFalse(meta['original_program_code_used'])

    def test_scope_identity_limits_and_exact_boolean_rejected_before_engine(self):
        for key, invalid in [('scientific_execution_authorized', 1), ('scientific_execution_authorized', False),
            ('task', 'p01-general'), ('scf_kernel_call_limit', 2), ('threads', 4), ('maximum_processes', 2),
            ('wall_time_limit_seconds', 300), ('runtime_commit', 'UNKNOWN'),
            ('source_snapshot_sha256', ''), ('execution_id', 'reuse'), ('p01_protocol_sha256', '00' * 32)]:
            with self.subTest(key=key, invalid=invalid), tempfile.TemporaryDirectory() as tmp:
                auth = authorization(); auth[key] = invalid
                factory = unittest.mock.Mock()
                with self.assertRaises(ValueError):
                    p01._execute(Path(tmp) / 'new', authorization=auth, engine_factory=factory, execution_kind='ENGINEERING_FAKE')
                factory.assert_not_called(); self.assertFalse((Path(tmp) / 'new').exists())

    def test_deadline_is_finite_future_and_never_extended(self):
        for deadline in (True, float('nan'), 10., 201.):
            with self.subTest(deadline=deadline), patch.object(p01.time, 'time', return_value=100.):
                auth = authorization(); auth['stop_deadline_epoch'] = deadline
                with self.assertRaises(ValueError): p01.validate_authorization(auth)
        with patch.object(p01.time, 'time', return_value=100.):
            auth = authorization(); auth['stop_deadline_epoch'] = 199.
            self.assertEqual(p01.validate_authorization(auth)[1], 199.)

    def test_nonorthogonal_metric_rotation_invariants_entropy_and_immutability(self):
        overlap = np.array([[2., .25], [.25, 1.]])
        local = p01.symmetric_matrix_power(overlap, -.5)
        rotation = np.array([[1., 1.], [1., -1.]]) / np.sqrt(2)
        canonical = local @ rotation
        originals = [x.copy() for x in (overlap, local, canonical)]
        groups = {'left_ch2': np.array([0]), 'right_ch2': np.array([1])}
        energy = lambda density: float(np.einsum('ij,ji->', density, overlap))
        a = p01.representation_diagnostics('canonical', canonical, canonical, overlap, groups, 4., energy)
        b = p01.representation_diagnostics('boys', local, canonical, overlap, groups, 4., energy)
        c = p01.representation_diagnostics('pipek_mezey', -local, canonical, overlap, groups, 4., energy)
        findings, changes, qualified = p01.assess_representations([a, b, c], scf_converged=True)
        self.assertTrue(qualified); self.assertAlmostEqual(a['mean_binary_support_entropy'], 1.)
        self.assertAlmostEqual(b['mean_binary_support_entropy'], 0.); self.assertLess(changes['boys'], -.99)
        self.assertTrue(findings['ao_density_invariant'])
        for actual, original in zip((overlap, local, canonical), originals): np.testing.assert_array_equal(actual, original)

    def test_changed_occupied_space_fails_original_density_and_unitarity_gates(self):
        canonical = np.eye(3)[:, :2]
        changed = np.eye(3)[:, [0, 2]]
        groups = {'left_ch2': np.array([0]), 'right_ch2': np.array([1, 2])}
        a = p01.representation_diagnostics('canonical', canonical, canonical, np.eye(3), groups, 4., lambda d: np.trace(d))
        b = p01.representation_diagnostics('boys', changed, canonical, np.eye(3), groups, 4., lambda d: np.trace(d))
        c = dict(b, name='pipek_mezey')
        finding, _, qualified = p01.assess_representations([a, b, c], scf_converged=True)
        self.assertFalse(qualified); self.assertFalse(finding['ao_density_invariant'])
        self.assertFalse(finding['all_representations_span_same_occupied_subspace'])

    def test_invalid_metric_partition_and_nonfinite_energy_refused(self):
        group = {'left_ch2': np.array([0]), 'right_ch2': np.array([1])}
        for matrix in (np.array([[1., 2.], [2., 1.]]), np.array([[1., .1], [0., 1.]]), np.array([[np.nan, 0.], [0., 1.]])):
            with self.subTest(matrix=matrix), self.assertRaises(ValueError): p01.symmetric_matrix_power(matrix, .5)
        with self.assertRaises(ValueError):
            p01.representation_diagnostics('canonical', np.eye(2), np.eye(2), np.eye(2),
                {'left_ch2': np.array([0]), 'right_ch2': np.array([0])}, 4., lambda d: 4.)
        for energy in (True, float('nan'), float('inf')):
            with self.subTest(energy=energy), self.assertRaises(ValueError):
                p01.representation_diagnostics('canonical', np.eye(2), np.eye(2), np.eye(2), group, 4., lambda d: energy)
        with self.assertRaises(ValueError):
            p01.representation_diagnostics('canonical', np.eye(2, dtype=complex), np.eye(2), np.eye(2), group, 4., lambda d: 4.)

    def test_original_threshold_values_preserved_and_immutable(self):
        self.assertEqual(dict(p01.TOLERANCES), {'density_relative_frobenius': 1e-9, 'electron_number': 1e-8,
            'total_energy_hartree': 1e-9, 'occupied_unitarity_frobenius': 1e-8, 'minimum_entropy_change': 1e-4})
        with self.assertRaises(TypeError): p01.TOLERANCES['total_energy_hartree'] = 1.

    def test_one_scf_and_one_of_each_localizer_with_complete_fake_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, toy = self.fake_run(Path(tmp) / 'case')
            self.assertEqual(result['status'], 'ENGINEERING_FAKE_P01_FIXED_CONTROL_PASSED')
            self.assertFalse(result['scientific_qualified']); self.assertFalse(result['Compute'])
            self.assertIsNone(result['native_NR_count']); self.assertIsNone(result['delta_energy_research'])
            self.assertEqual(toy.calls, {'scf': 1, 'boys': 1, 'pm': 1, 'energy': 3, 'threads': [1]})
            self.assertEqual((toy.mf.conv_tol, toy.mf.max_cycle), (1e-12, 100))
            self.assertEqual((toy.boys_solver.conv_tol, toy.boys_solver.max_cycle), (1e-10, 200))
            self.assertEqual((toy.pm_solver.conv_tol, toy.pm_solver.max_cycle), (1e-10, 200))
            self.assertTrue(result['operations_closed'])
            for row in result['operation_ledger']['operations'].values():
                self.assertEqual((row['charged'], row['entered'], row['returned'], row['failed']), (1, 1, 1, 0))
            for name in ('case-result.json', 'case-report.md', 'operation-ledger.json', 'occupied-representations.npz'):
                self.assertTrue((Path(tmp) / 'case' / name).exists())
            numpy_bool_result, _ = self.fake_run(Path(tmp) / 'numpy-bool-case', ToyEngine(converged=np.bool_(True)))
            self.assertTrue(numpy_bool_result['scf']['converged'])

    def test_scf_exception_is_charged_closed_and_stops_localization(self):
        with tempfile.TemporaryDirectory() as tmp:
            toy = ToyEngine(fault='scf'); output = Path(tmp) / 'case'
            with self.assertRaisesRegex(RuntimeError, 'toy scf fault'): self.fake_run(output, toy)
            result = json.loads((output / 'case-result.json').read_text())
            ledger = result['operation_ledger']
            self.assertEqual(ledger['status'], 'CLOSED')
            self.assertEqual(ledger['operations']['scf_kernel']['failed'], 1)
            self.assertEqual(ledger['operations']['boys_kernel']['charged'], 0)
            self.assertEqual(toy.calls['pm'], 0)

    def test_nonconverged_rhf_does_not_enter_localizers(self):
        with tempfile.TemporaryDirectory() as tmp:
            toy = ToyEngine(converged=False); output = Path(tmp) / 'case'
            with self.assertRaisesRegex(RuntimeError, 'did not converge'): self.fake_run(output, toy)
            record = json.loads((output / 'case-result.json').read_text())
            self.assertFalse(record['scientific_qualified']); self.assertEqual(toy.calls['scf'], 1)
            self.assertEqual(toy.calls['boys'], 0); self.assertEqual(toy.calls['pm'], 0)

    def test_boys_failure_charged_without_pm_or_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            toy = ToyEngine(fault='boys'); output = Path(tmp) / 'case'
            with self.assertRaisesRegex(RuntimeError, 'toy boys fault'): self.fake_run(output, toy)
            result = json.loads((output / 'case-result.json').read_text())
            self.assertEqual(result['operation_ledger']['operations']['boys_kernel']['failed'], 1)
            self.assertEqual(toy.calls['boys'], 1); self.assertEqual(toy.calls['pm'], 0)

    def test_pm_failure_after_two_successful_operations_is_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            toy = ToyEngine(fault='pm'); output = Path(tmp) / 'case'
            with self.assertRaisesRegex(RuntimeError, 'toy pm fault'): self.fake_run(output, toy)
            result = json.loads((output / 'case-result.json').read_text())
            self.assertEqual(result['operation_ledger']['operations']['pipek_mezey_kernel']['failed'], 1)
            self.assertEqual(toy.calls['energy'], 0); self.assertTrue(result['operations_closed'])

    def test_existing_case_output_refuses_second_engine_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'case'; _, toy = self.fake_run(output)
            with self.assertRaisesRegex(ValueError, 'no resume'): self.fake_run(output, toy)
            self.assertEqual(toy.calls['scf'], 1)

    def test_after_scf_cooperative_stop_cannot_enter_boys(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'case'; toy = ToyEngine()
            def check(deadline, phase):
                if phase == 'AFTER_SCF': raise TimeoutError('toy stop after native delegate returned')
            with patch.object(p01, '_checkpoint', side_effect=check), self.assertRaises(TimeoutError): self.fake_run(output, toy)
            result = json.loads((output / 'case-result.json').read_text())
            self.assertEqual(toy.calls['scf'], 1); self.assertEqual(toy.calls['boys'], 0)
            self.assertTrue(result['operations_closed']); self.assertFalse(result['scientific_qualified'])

    def test_no_entropy_change_is_not_qualified_without_lowering_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, toy = self.fake_run(Path(tmp) / 'case', ToyEngine(localize=False))
            self.assertEqual(result['status'], 'ENGINEERING_FAKE_P01_FIXED_CONTROL_NOT_QUALIFIED')
            self.assertFalse(result['findings']['orbital_fragment_support_changes'])
            self.assertEqual(toy.calls['scf'], 1)

    def test_intent_write_failure_refuses_delegate_preserves_failed_charge(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'case'; toy = ToyEngine(); real_save = p01._save; counts = [0]
            def failing_save(path, record):
                counts[0] += 1
                if counts[0] == 2: raise OSError('toy durable intent write failure')
                return real_save(path, record)
            with patch.object(p01, '_save', side_effect=failing_save), self.assertRaises(OSError): self.fake_run(output, toy)
            record = json.loads((output / 'case-result.json').read_text())
            row = record['operation_ledger']['operations']['scf_kernel']
            self.assertEqual((row['charged'], row['entered'], row['returned'], row['failed']), (1, 0, 0, 1))
            self.assertEqual(toy.calls['scf'], 0); self.assertFalse(record['scientific_qualified'])


if __name__ == '__main__': unittest.main()
