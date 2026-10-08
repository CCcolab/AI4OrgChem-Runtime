"""Pure finite-array and fake-engine tests; no PySCF or scientific execution."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from runtime.molecular_service import engine


def profile():
    return {'profile_id': engine.PROFILE_ID, 'protocol_id': engine.PROTOCOL_ID,
        'engine': {'program': 'pyscf', 'method': 'RHF', 'basis': '6-31G(d)',
            'symmetry': False, 'conv_tol': 1e-12, 'conv_tol_grad': 1e-8,
            'max_cycle': 100, 'max_memory_mb': 768, 'max_ao': 80,
            'scf_kernel_call_limit': 1},
        'tolerances': {'commutator_whitened_frobenius_max': 1e-7,
            'electron_count_abs_max': 1e-8, 'occupied_orthonormality_frobenius_max': 1e-8,
            'projector_idempotency_frobenius_max': 1e-8,
            'density_reconstruction_relative_frobenius_max': 1e-9,
            'energy_closure_abs_hartree_max': 1e-9,
            'overlap_eigenvalue_min': 1e-10, 'overlap_condition_number_max': 1e10,
            'matrix_symmetry_abs_max': 1e-10}}


def bundle():
    return {'molecule': {'symbols': ['H', 'H'], 'geometry_angstrom': [[0., 0., 0.], [0., 0., .74]],
        'charge': 0, 'multiplicity': 1, 'electron_count': 2, 'atom_count': 2, 'coordinate_unit': 'angstrom'},
        'request': {'task': 'single-point', 'method': 'RHF', 'basis': '6-31G(d)'},
        'atoms': [{'index_1based': 1, 'index_0based': 0, 'symbol': 'H', 'xyz_angstrom': [0., 0., 0.]},
                  {'index_1based': 2, 'index_0based': 1, 'symbol': 'H', 'xyz_angstrom': [0., 0., .74]}],
        'request_sha256': 'a1' * 32, 'structure_sha256': 'b2' * 32,
        'profile_sha256': 'c3' * 32, 'normalized_sha256': 'd4' * 32}


def contract():
    return {'schema': 'molecular-service-execution-v1', 'task': 'single-point',
        'profile_id': engine.PROFILE_ID, 'protocol_id': engine.PROTOCOL_ID,
        'scientific_execution_authorized': True, 'scf_kernel_call_limit': 1,
        'boys_kernel_call_limit': 0, 'pipek_mezey_kernel_call_limit': 0,
        'maximum_processes': 1, 'threads': 1, 'memory_limit_bytes': 1073741824,
        'wall_time_limit_seconds': 120, 'stop_after_seconds': 100,
        'stop_deadline_epoch': time.time() + 99,
        'runtime_commit': 'ab' * 20, 'source_snapshot_sha256': 'cd' * 32,
        'dependency_lock_sha256': 'ef' * 32, 'execution_id': '12' * 16}


def arrays():
    return {'overlap': np.eye(2), 'density': np.diag([2., 0.]), 'coefficients': np.eye(2),
        'occupations': np.array([2., 0.]), 'orbital_energies': np.array([-.8, -.4]),
        'fock': np.diag([-.8, -.4]), 'hcore': np.diag([-1., -.5]),
        'veff': np.diag([.2, .1]), 'electron_count': 2, 'nuclear_energy': .7,
        'total_energy': -1.1, 'scf_converged': True}


class FakeEngine:
    def __init__(self, *, converged=True, fail_kernel=False, nao=2, overlap=None):
        self.calls = {'scf': 0, 'energy_elec': 0, 'threads': []}
        self.received_build = None
        self.fail_kernel = fail_kernel
        self.output = None
        self.endpoint = arrays()
        self.mf = SimpleNamespace(mo_coeff=np.eye(2), mo_occ=np.array([2., 0.]),
            mo_energy=np.array([-.8, -.4]), converged=converged, cycles=2,
            kernel=self.kernel, get_ovlp=lambda: np.eye(2) if overlap is None else overlap,
            make_rdm1=lambda: self.endpoint['density'].copy(),
            get_hcore=lambda: self.endpoint['hcore'].copy(),
            get_veff=lambda mol, dm: self.endpoint['veff'].copy(),
            energy_elec=self.energy)
        self.mol = SimpleNamespace(nelectron=2, nao_nr=lambda: nao, energy_nuc=lambda: .7,
            ao_labels=lambda: ['0 H 1s', '1 H 1s'],
            aoslice_by_atom=lambda: np.array([[0, 1, 0, 1], [1, 2, 1, 2]]))
        self.api = {'gto': SimpleNamespace(M=self.build),
            'lib': SimpleNamespace(num_threads=self.calls['threads'].append),
            'scf': SimpleNamespace(RHF=lambda mol: self.mf), 'version': 'ENGINEERING_FAKE_NOT_PYSCF'}

    def build(self, **kwargs):
        self.received_build = copy.deepcopy(kwargs)
        return self.mol

    def kernel(self):
        self.calls['scf'] += 1
        if self.output is not None:
            ledger = json.loads((self.output / 'operation-ledger.json').read_text(encoding='utf-8'))
            if ledger['operations']['scf_kernel']['charged'] != 1:
                raise AssertionError('The SCF charge was not durable before native dispatch')
        if self.fail_kernel:
            raise RuntimeError('engineering fixture kernel failure')
        self.mf.callback({'cycle': 0})
        return self.endpoint['total_energy']

    def energy(self, *, dm, h1e, vhf):
        self.calls['energy_elec'] += 1
        e1 = float(np.einsum('ij,ji->', dm, h1e))
        e2 = .5 * float(np.einsum('ij,ji->', dm, vhf))
        return e1 + e2, e2

class MolecularEngineTests(unittest.TestCase):
    def run_fake(self, output, fake=None, **kwargs):
        fake = fake or FakeEngine()
        fake.output = output
        checkpoints = []
        result = engine.compute(kwargs.get('bundle', bundle()), kwargs.get('profile', profile()), output,
            checkpoint=kwargs.get('checkpoint', checkpoints.append),
            execution_contract=kwargs.get('contract', contract()), engine_factory=lambda: fake.api)
        return result, fake, checkpoints

    def test_ordinary_endpoint_has_separate_numeric_gates_and_observed_gap(self):
        result = engine.orbital_density_diagnostics(**arrays())
        self.assertTrue(result['numerically_qualified'])
        self.assertAlmostEqual(result['energy_ledger']['one_electron'], -2.)
        self.assertAlmostEqual(result['energy_ledger']['two_electron_coulomb_exchange'], .2)
        self.assertAlmostEqual(result['energy_ledger']['scf_total'], -1.1)
        self.assertAlmostEqual(result['orbital_summary']['homo_lumo_gap_hartree'], .4)
        self.assertFalse(result['orbital_summary']['gap_acceptance_gate'])
        self.assertEqual(result['orbital_summary']['stability'], 'NOT_EXECUTED')

    def test_nondegenerate_and_zero_gap_are_observations_without_conditional_gate(self):
        for energies in ([0., 0.], [1., -1.]):
            with self.subTest(energies=energies):
                data = arrays(); data['orbital_energies'] = np.array(energies)
                result = engine.orbital_density_diagnostics(**data)
                self.assertTrue(result['numerically_qualified'])
                self.assertFalse(result['orbital_summary']['gap_acceptance_gate'])

    def test_nonorthogonal_metric_checks_are_coordinate_consistent(self):
        overlap = np.array([[2., .3, .1], [.3, 1.2, .2], [.1, .2, .9]])
        half, inverse_half, _ = engine.overlap_metric(overlap)
        q, _ = np.linalg.qr(np.array([[1., 2., 3.], [2., -1., .5], [1., 1., -1.]]))
        coeff = inverse_half @ q
        energies = np.array([-1.2, -.4, .7])
        fock = half @ (q * energies) @ q.T @ half
        hcore, veff = .5 * fock, .5 * fock
        density = 2 * coeff[:, :1] @ coeff[:, :1].T
        data = {'overlap': overlap, 'density': density, 'coefficients': coeff,
            'occupations': np.array([2., 0., 0.]), 'orbital_energies': energies,
            'fock': fock, 'hcore': hcore, 'veff': veff, 'electron_count': 2,
            'nuclear_energy': .7, 'total_energy': -1.1, 'scf_converged': True}
        unchanged = {key: value.copy() for key, value in data.items() if isinstance(value, np.ndarray)}
        result = engine.orbital_density_diagnostics(**data)
        self.assertTrue(result['numerically_qualified'])
        self.assertLess(result['residuals']['whitened_fock_projector_commutator_frobenius_hartree'], 1e-12)
        for key, old in unchanged.items():
            np.testing.assert_array_equal(data[key], old)

    def test_unconverged_endpoint_cannot_qualify_even_when_all_arrays_are_good(self):
        data = arrays(); data['scf_converged'] = False
        result = engine.orbital_density_diagnostics(**data)
        self.assertFalse(result['numerically_qualified'])
        self.assertFalse(result['checks']['scf_converged'])
        self.assertTrue(result['checks']['energy_ledger_closure'])

    def test_density_electron_and_projector_gates_do_not_get_hidden_by_convergence(self):
        data = arrays(); data['density'] = np.diag([1.9, .1])
        result = engine.orbital_density_diagnostics(**data)
        self.assertFalse(result['numerically_qualified'])
        self.assertTrue(result['checks']['electron_number'])
        self.assertFalse(result['checks']['density_reconstruction'])
        self.assertFalse(result['checks']['whitened_projector_idempotency'])

    def test_energy_closure_and_occupied_fock_commutator_are_independent(self):
        data = arrays(); data['total_energy'] += 1e-5
        result = engine.orbital_density_diagnostics(**data)
        self.assertFalse(result['checks']['energy_ledger_closure'])
        self.assertTrue(result['checks']['whitened_fock_projector_commutator'])
        data = arrays(); data['veff'][0, 1] = data['veff'][1, 0] = 1e-3
        data['fock'] = data['hcore'] + data['veff']
        result = engine.orbital_density_diagnostics(**data)
        self.assertTrue(result['checks']['energy_ledger_closure'])
        self.assertFalse(result['checks']['whitened_fock_projector_commutator'])

    def test_nonfinite_complex_asymmetric_and_singular_arrays_are_rejected(self):
        for key, invalid in (('density', np.diag([np.nan, 0.])),
                             ('fock', np.eye(2, dtype=complex)),
                             ('overlap', np.array([[1., .3], [0., 1.]])),
                             ('overlap', np.diag([1., 1e-12]))):
            with self.subTest(key=key):
                data = arrays(); data[key] = invalid
                with self.assertRaises(ValueError):
                    engine.orbital_density_diagnostics(**data)

    def test_wrong_occupation_density_and_energy_are_refused_independently(self):
        data = arrays(); data['occupations'] = np.array([1., 1.])
        result = engine.orbital_density_diagnostics(**data)
        self.assertFalse(result['checks']['closed_shell_occupations'])
        self.assertFalse(result['numerically_qualified'])
        data = arrays(); data['total_energy'] = float('inf')
        with self.assertRaises(ValueError): engine.orbital_density_diagnostics(**data)

    def test_authorization_profile_and_input_rejected_before_engine_or_output(self):
        for key, bad in (('scientific_execution_authorized', False), ('scientific_execution_authorized', 1),
                         ('scf_kernel_call_limit', 2), ('boys_kernel_call_limit', 1),
                         ('threads', 2), ('runtime_commit', 'UNKNOWN')):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temporary:
                auth = contract(); auth[key] = bad
                factory = Mock()
                path = Path(temporary) / 'calculation'
                with self.assertRaises(ValueError):
                    engine.compute(bundle(), profile(), path, checkpoint=lambda p: None,
                        execution_contract=auth, engine_factory=factory)
                factory.assert_not_called(); self.assertFalse(path.exists())
        for section, key, bad in (('engine', 'conv_tol', 1e-8), ('engine', 'basis', 'STO-3G'),
                                  ('tolerances', 'energy_closure_abs_hartree_max', 1e-3)):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temporary:
                candidate = profile(); candidate[section][key] = bad
                factory = Mock()
                with self.assertRaises(ValueError):
                    engine.compute(bundle(), candidate, Path(temporary) / 'calculation', checkpoint=lambda p: None,
                        execution_contract=contract(), engine_factory=factory)
                factory.assert_not_called()

    def test_deadline_must_be_future_finite_and_not_extended(self):
        for deadline in (True, float('nan'), 99., 201.):
            with self.subTest(deadline=deadline), patch.object(engine.time, 'time', return_value=100.):
                candidate = contract(); candidate['stop_deadline_epoch'] = deadline
                with self.assertRaises(ValueError): engine.validate_execution_contract(candidate)

    def test_true_three_dimensional_coordinates_are_not_planarized(self):
        candidate = bundle(); candidate['molecule']['geometry_angstrom'] = [[1., 2., 3.], [1.5, 2.5, 3.5]]
        for row, xyz in zip(candidate['atoms'], candidate['molecule']['geometry_angstrom']):
            row['xyz_angstrom'] = xyz.copy()
        with tempfile.TemporaryDirectory() as temporary:
            result, fake, _ = self.run_fake(Path(temporary) / 'calculation', bundle=candidate)
            self.assertEqual(fake.received_build['atom'], [('H', (1., 2., 3.)), ('H', (1.5, 2.5, 3.5))])
            self.assertEqual(fake.received_build['unit'], 'Angstrom')
            self.assertFalse(result['scientific_qualified'])

    def test_actual_input_bundle_and_frozen_profile_connect_without_scientific_import(self):
        from runtime.molecular_service.input import parse_request
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); request = root / 'request.json'; structure = root / 'molecule.xyz'
            structure.write_text('2\nengineering H2 fixture\nH 0 0 0\nH 0 0 0.74\n', encoding='utf-8')
            request.write_text(json.dumps({'schema': 'molecular-single-point-v1', 'task': 'single-point',
                'profile': engine.PROFILE_ID, 'structure': {'file': 'molecule.xyz', 'format': 'xyz', 'unit': 'angstrom'},
                'charge': 0, 'multiplicity': 1, 'method': 'RHF', 'basis': '6-31G(d)'}), encoding='utf-8')
            checked = parse_request(request)
            output = root / 'calculation'; fake = FakeEngine(); fake.output = output
            with patch.object(engine, '_load_engine', side_effect=AssertionError('Real PySCF import is forbidden in this test')):
                result = engine.compute(checked, checked['profile'], output, checkpoint=lambda phase: None,
                    execution_contract=contract(), engine_factory=lambda: fake.api)
            self.assertEqual(result['structure_sha256'], checked['structure_sha256'])
            self.assertEqual(result['profile_sha256'], checked['profile_sha256'])
            self.assertTrue(result['numerically_qualified']); self.assertFalse(result['scientific_qualified'])

    def test_one_durable_scf_charge_complete_exports_and_fake_never_qualifies_science(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'calculation'
            result, fake, checkpoints = self.run_fake(output)
            self.assertEqual(result['status'], 'ENGINEERING_FAKE_NUMERICALLY_QUALIFIED_ORDINARY_RHF')
            self.assertTrue(result['numerically_qualified']); self.assertFalse(result['scientific_qualified'])
            self.assertTrue(result['operations_closed']); self.assertIsNone(result['actual_native_call_counts'])
            self.assertEqual(fake.calls, {'scf': 1, 'energy_elec': 1, 'threads': [1]})
            self.assertEqual(fake.mf.conv_tol, 1e-12); self.assertEqual(fake.mf.conv_tol_grad, 1e-8)
            self.assertEqual(fake.mf.max_cycle, 100); self.assertEqual(fake.mf.max_memory, 768)
            self.assertIsNone(fake.mf.chkfile)
            self.assertIn('SCF_ITERATION_1', checkpoints)
            self.assertEqual(result['operation_ledger']['operations']['scf_kernel']['charged'], 1)
            self.assertEqual(result['operation_ledger']['operations']['scf_kernel']['returned'], 1)
            self.assertEqual(result['operation_ledger']['status'], 'CLOSED')
            with np.load(output / 'orbitals-density.npz', allow_pickle=False) as arrays_out:
                self.assertEqual(set(arrays_out.files), {'overlap', 'density', 'canonical_coefficients',
                    'orbital_energies_hartree', 'occupations', 'fock', 'hcore', 'veff'})
                np.testing.assert_array_equal(arrays_out['density'], np.diag([2., 0.]))
            persisted = json.loads((output / 'result.json').read_text(encoding='utf-8'))
            self.assertEqual(persisted['request_sha256'], bundle()['request_sha256'])
            self.assertEqual(persisted['atoms'], bundle()['atoms'])
            self.assertEqual(persisted['atom_ao_slices'][1]['ao_start_0based'], 1)
            self.assertIn('工程模拟', (output / 'report.md').read_text(encoding='utf-8'))

    def test_native_failure_is_charged_closed_preserved_and_never_retried(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'calculation'; fake = FakeEngine(fail_kernel=True); fake.output = output
            with self.assertRaisesRegex(RuntimeError, 'fixture kernel failure'):
                self.run_fake(output, fake)
            persisted = json.loads((output / 'result.json').read_text(encoding='utf-8'))
            self.assertEqual(fake.calls['scf'], 1); self.assertFalse(persisted['scientific_qualified'])
            row = persisted['operation_ledger']['operations']['scf_kernel']
            self.assertEqual((row['charged'], row['entered'], row['returned'], row['failed']), (1, 1, 0, 1))
            with self.assertRaises(ValueError): self.run_fake(output, fake)
            self.assertEqual(fake.calls['scf'], 1)

    def test_resource_or_metric_refusal_occurs_before_scf(self):
        for fake in (FakeEngine(nao=81), FakeEngine(overlap=np.diag([1., 1e-12]))):
            with self.subTest(fake=fake), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / 'calculation'
                with self.assertRaises(ValueError): self.run_fake(output, fake)
                self.assertEqual(fake.calls['scf'], 0)
                persisted = json.loads((output / 'result.json').read_text(encoding='utf-8'))
                self.assertFalse(persisted['numerically_qualified'])
                self.assertEqual(persisted['operation_ledger']['operations']['scf_kernel']['charged'], 0)

    def test_original_ao_atom_mapping_cannot_be_incomplete_or_overlapping(self):
        for slices in (np.array([[0, 1, 0, 1], [1, 2, 0, 1]]),
                       np.array([[0, 1, 0, 1]]),
                       np.array([[0., 1., 0., 1.], [1., 2., 1., 2.]])):
            with self.subTest(slices=slices), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / 'calculation'; fake = FakeEngine()
                fake.mol.aoslice_by_atom = lambda: slices
                with self.assertRaises(ValueError): self.run_fake(output, fake)
                persisted = json.loads((output / 'result.json').read_text(encoding='utf-8'))
                self.assertFalse(persisted['scientific_qualified'])
                self.assertEqual(fake.calls['scf'], 1)

    def test_occupied_columns_and_coordinates_have_independent_checks(self):
        data = arrays(); data['coefficients'][0, 0] = 1.01
        result = engine.orbital_density_diagnostics(**data)
        self.assertFalse(result['checks']['occupied_orthonormality'])
        self.assertFalse(result['checks']['density_reconstruction'])
        for key, value in (('coordinate_unit', 'bohr'), ('atom_count', 3), ('charge', True),
                           ('geometry_angstrom', [[10001., 0., 0.], [10002., 0., 0.]])):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temporary:
                candidate = bundle(); candidate['molecule'][key] = value
                factory = Mock()
                with self.assertRaises(ValueError):
                    engine.compute(candidate, profile(), Path(temporary) / 'calculation',
                        checkpoint=lambda p: None, execution_contract=contract(), engine_factory=factory)
                factory.assert_not_called()

    def test_result_atom_mapping_cannot_disagree_with_computed_geometry(self):
        for key, value in (('symbol', 'O'), ('index_0based', 1), ('index_1based', True),
                           ('xyz_angstrom', [1., 0., 0.])):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temporary:
                candidate = bundle(); candidate['atoms'][0][key] = value
                factory = Mock()
                with self.assertRaises(ValueError):
                    engine.compute(candidate, profile(), Path(temporary) / 'calculation', checkpoint=lambda p: None,
                        execution_contract=contract(), engine_factory=factory)
                factory.assert_not_called()

    def test_cooperative_stop_in_scf_callback_is_not_success(self):
        def checkpoint(phase):
            if phase.startswith('SCF_ITERATION_'):
                raise TimeoutError('engineering callback stop')
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'calculation'; fake = FakeEngine()
            with self.assertRaisesRegex(TimeoutError, 'callback stop'):
                self.run_fake(output, fake, checkpoint=checkpoint)
            persisted = json.loads((output / 'result.json').read_text(encoding='utf-8'))
            self.assertFalse(persisted['scientific_qualified'])
            self.assertEqual(fake.calls['scf'], 1); self.assertEqual(fake.calls['energy_elec'], 0)
            self.assertEqual(persisted['operation_ledger']['operations']['scf_kernel']['failed'], 1)

    def test_unconverged_scf_retains_arrays_and_does_not_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, fake, _ = self.run_fake(Path(temporary) / 'calculation', FakeEngine(converged=False))
            self.assertEqual(result['status'], 'ENGINEERING_FAKE_ORDINARY_RHF_NOT_QUALIFIED')
            self.assertFalse(result['scientific_qualified']); self.assertFalse(result['numerically_qualified'])
            self.assertEqual(fake.calls['scf'], 1)


if __name__ == '__main__':
    unittest.main()
