"""One bounded ordinary molecular RHF calculation and AO/orbital export.

PySCF supplies the ordinary SCF implementation.  This module does not construct
conditional operators, use density grids, localize orbitals, or establish SCF
stability.  Injected engines are engineering fixtures and cannot qualify science.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
from types import MappingProxyType

import numpy as np

TASK = 'single-point'
PROFILE_ID = 'rhf-631gd-small-v1'
PROTOCOL_ID = 'ORDINARY_MOLECULAR_SINGLE_POINT_V0.1'
TOLERANCES = MappingProxyType({
    'electron_number_absolute': 1e-8,
    'occupied_orthonormality_frobenius': 1e-8,
    'whitened_projector_idempotency_frobenius': 1e-8,
    'density_reconstruction_relative_frobenius': 1e-9,
    'energy_ledger_closure_hartree': 1e-9,
    'whitened_fock_projector_commutator_frobenius_hartree': 1e-7,
    'minimum_overlap_eigenvalue': 1e-10,
    'maximum_overlap_condition_number': 1e10,
    'matrix_symmetry_absolute': 1e-10,
})
ROOT = Path(__file__).resolve().parents[2]


def _save(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    data = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True,
                       allow_nan=False) + '\n').encode('utf-8')
    with temporary.open('wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _real(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise ValueError(name + ' must be a finite real scalar')
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(name + ' must be finite')
    return value


def _array(value, name, shape=None, ndim=2):
    raw = np.asarray(value)
    if raw.dtype.kind not in 'fiu' or raw.ndim != ndim:
        raise ValueError(name + ' must be a real array with the declared dimension')
    result = np.array(raw, dtype=np.float64, copy=True)
    if (shape is not None and result.shape != shape) or not np.isfinite(result).all():
        raise ValueError(name + ' has an invalid shape or nonfinite values')
    return result


def overlap_metric(overlap):
    """Return the original AO metric powers without modifying/dropping AO rows."""
    overlap = _array(overlap, 'AO overlap')
    if overlap.shape[0] != overlap.shape[1] or overlap.shape[0] < 1:
        raise ValueError('AO overlap must be a nonempty square matrix')
    asymmetry = float(np.max(np.abs(overlap - overlap.T)))
    if asymmetry > TOLERANCES['matrix_symmetry_absolute']:
        raise ValueError('AO overlap is not symmetric within the fixed tolerance')
    values, vectors = np.linalg.eigh(overlap)
    minimum, maximum = float(values[0]), float(values[-1])
    if minimum < TOLERANCES['minimum_overlap_eigenvalue']:
        raise ValueError('AO overlap minimum eigenvalue is below the fixed support limit')
    condition = maximum / minimum
    if not math.isfinite(condition) or condition > TOLERANCES['maximum_overlap_condition_number']:
        raise ValueError('AO overlap condition number exceeds the fixed support limit')
    half = (vectors * np.sqrt(values)) @ vectors.T
    inverse_half = (vectors * (1 / np.sqrt(values))) @ vectors.T
    return half, inverse_half, {'minimum_eigenvalue': minimum,
        'maximum_eigenvalue': maximum, 'condition_number': condition,
        'symmetry_max_absolute': asymmetry}


def orbital_density_diagnostics(*, overlap, density, coefficients, occupations,
                                orbital_energies, fock, hcore, veff,
                                electron_count, nuclear_energy, total_energy,
                                scf_converged):
    """Independent finite-array checks of one ordinary RHF endpoint.

    P is the occupied projector in the symmetric orthonormal AO representation:
    P = S^(1/2) D S^(1/2) / 2.  The Fock commutator uses the same representation.
    The HOMO/LUMO gap is an observation, never the conditional-state gap gate.
    """
    overlap = _array(overlap, 'AO overlap')
    nao = overlap.shape[0]
    half, inverse_half, metric = overlap_metric(overlap)
    shape = (nao, nao)
    density = _array(density, 'AO density', shape)
    coefficients = _array(coefficients, 'canonical MO coefficients', shape)
    occupations = _array(occupations, 'MO occupations', (nao,), ndim=1)
    orbital_energies = _array(orbital_energies, 'MO energies', (nao,), ndim=1)
    fock = _array(fock, 'unextrapolated ordinary RHF Fock', shape)
    hcore = _array(hcore, 'core Hamiltonian', shape)
    veff = _array(veff, 'ordinary RHF mean field', shape)
    if type(electron_count) is not int or electron_count < 2 or electron_count % 2:
        raise ValueError('A positive even closed-shell electron count is required')
    if not isinstance(scf_converged, (bool, np.bool_)):
        raise ValueError('SCF convergence must be a logical scalar')
    nuclear_energy = _real(nuclear_energy, 'nuclear repulsion energy')
    total_energy = _real(total_energy, 'SCF total energy')
    occupied = occupations == 2
    virtual = occupations == 0
    occupation_valid = bool(np.all(occupied | virtual) and np.count_nonzero(occupied) * 2 == electron_count)
    occupied_coefficients = coefficients[:, occupied]
    reconstructed = 2 * occupied_coefficients @ occupied_coefficients.T
    occupied_orthonormality = float(np.linalg.norm(
        occupied_coefficients.T @ overlap @ occupied_coefficients - np.eye(np.count_nonzero(occupied)), 'fro'))
    density_norm = float(np.linalg.norm(density, 'fro'))
    reconstruction_relative = float(np.linalg.norm(density - reconstructed, 'fro')) / max(density_norm, np.finfo(float).tiny)
    projector = .5 * half @ density @ half
    idempotency = float(np.linalg.norm(projector @ projector - projector, 'fro'))
    whitened_fock = inverse_half @ fock @ inverse_half
    commutator = float(np.linalg.norm(whitened_fock @ projector - projector @ whitened_fock, 'fro'))
    electrons = float(np.einsum('ij,ji->', density, overlap))
    electron_error = abs(electrons - electron_count)
    one_electron = float(np.einsum('ij,ji->', density, hcore))
    two_electron = .5 * float(np.einsum('ij,ji->', density, veff))
    reconstructed_energy = one_electron + two_electron + nuclear_energy
    closure = abs(reconstructed_energy - total_energy)
    symmetry = {name: float(np.max(np.abs(array - array.T))) for name, array in
                (('density', density), ('fock', fock), ('hcore', hcore), ('veff', veff))}
    fock_closure = float(np.max(np.abs(fock - hcore - veff)))
    generalized_eigen = float(np.linalg.norm(
        fock @ coefficients - overlap @ (coefficients * orbital_energies), 'fro'))
    homo = float(np.max(orbital_energies[occupied])) if np.any(occupied) else None
    lumo = float(np.min(orbital_energies[virtual])) if np.any(virtual) else None
    gap = lumo - homo if homo is not None and lumo is not None else None
    checks = {
        'scf_converged': bool(scf_converged),
        'closed_shell_occupations': occupation_valid,
        'electron_number': electron_error <= TOLERANCES['electron_number_absolute'],
        'occupied_orthonormality': occupied_orthonormality <= TOLERANCES['occupied_orthonormality_frobenius'],
        'whitened_projector_idempotency': idempotency <= TOLERANCES['whitened_projector_idempotency_frobenius'],
        'density_reconstruction': reconstruction_relative <= TOLERANCES['density_reconstruction_relative_frobenius'],
        'energy_ledger_closure': closure <= TOLERANCES['energy_ledger_closure_hartree'],
        'whitened_fock_projector_commutator': commutator <= TOLERANCES['whitened_fock_projector_commutator_frobenius_hartree'],
        'finite_arrays_and_energy': True,
        'symmetric_ao_matrices': max(symmetry.values()) <= TOLERANCES['matrix_symmetry_absolute'],
        'ordinary_fock_equals_hcore_plus_veff': fock_closure <= TOLERANCES['matrix_symmetry_absolute'],
    }
    return {'checks': checks, 'numerically_qualified': all(checks.values()),
        'metric': metric,
        'residuals': {'electron_number_absolute': electron_error,
            'occupied_orthonormality_frobenius': occupied_orthonormality,
            'whitened_projector_idempotency_frobenius': idempotency,
            'density_reconstruction_relative_frobenius': reconstruction_relative,
            'energy_ledger_closure_hartree': closure,
            'whitened_fock_projector_commutator_frobenius_hartree': commutator,
            'generalized_mo_eigen_equation_frobenius_hartree': generalized_eigen,
            'matrix_symmetry_max_absolute': symmetry,
            'ordinary_fock_closure_max_absolute_hartree': fock_closure},
        'electron_number': electrons,
        'energy_ledger': {'unit': 'hartree', 'one_electron': one_electron,
            'two_electron_coulomb_exchange': two_electron, 'electronic': one_electron + two_electron,
            'nuclear_repulsion': nuclear_energy, 'reconstructed_total': reconstructed_energy,
            'scf_total': total_energy, 'closure_absolute': closure,
            'definition': 'Tr(D hcore) + 0.5 Tr(D Vhf) + nuclear_repulsion'},
        'orbital_summary': {'occupied_orbital_count': int(np.count_nonzero(occupied)),
            'virtual_orbital_count': int(np.count_nonzero(virtual)),
            'homo_energy_hartree': homo, 'lumo_energy_hartree': lumo,
            'homo_lumo_gap_hartree': gap, 'gap_acceptance_gate': False,
            'stability': 'NOT_EXECUTED', 'localization': 'NOT_EXECUTED'}}


def validate_execution_contract(contract):
    if not isinstance(contract, dict):
        raise ValueError('An explicit molecular execution contract is required')
    fixed = {'schema': 'molecular-service-execution-v1', 'task': TASK,
        'profile_id': PROFILE_ID, 'protocol_id': PROTOCOL_ID,
        'scientific_execution_authorized': True, 'scf_kernel_call_limit': 1,
        'boys_kernel_call_limit': 0, 'pipek_mezey_kernel_call_limit': 0,
        'maximum_processes': 1, 'threads': 1, 'memory_limit_bytes': 1073741824,
        'wall_time_limit_seconds': 120, 'stop_after_seconds': 100}
    for key, expected in fixed.items():
        if type(contract.get(key)) is not type(expected) or contract.get(key) != expected:
            raise ValueError('Molecular execution scope mismatch: ' + key)
    for key, length in (('runtime_commit', 40), ('source_snapshot_sha256', 64),
                        ('dependency_lock_sha256', 64), ('execution_id', 32)):
        if not isinstance(contract.get(key), str) or not re.fullmatch('[0-9a-f]{' + str(length) + '}', contract[key]):
            raise ValueError('An explicit execution identity is required: ' + key)
    now = time.time()
    deadline = _real(contract.get('stop_deadline_epoch'), 'stop deadline')
    if deadline <= now or deadline > now + 100:
        raise ValueError('The stop deadline must be future and cannot extend the 100-second budget')
    return copy.deepcopy(contract), deadline


def _validate_profile(profile):
    if not isinstance(profile, dict):
        raise ValueError('A fixed molecular profile is required')
    identifier = profile.get('profile_id', profile.get('id'))
    if identifier != PROFILE_ID:
        raise ValueError('Unsupported molecular profile')
    settings = profile.get('engine', {})
    fixed = {'program': 'pyscf', 'method': 'RHF', 'basis': '6-31G(d)', 'symmetry': False,
             'conv_tol': 1e-12, 'conv_tol_grad': 1e-8, 'max_cycle': 100,
             'max_memory_mb': 768, 'max_ao': 80, 'scf_kernel_call_limit': 1}
    for key, expected in fixed.items():
        if type(settings.get(key)) is not type(expected) or settings.get(key) != expected:
            raise ValueError('Fixed ordinary RHF profile mismatch: ' + key)
    fixed_tolerances = {
        'commutator_whitened_frobenius_max': 1e-7,
        'electron_count_abs_max': 1e-8,
        'occupied_orthonormality_frobenius_max': 1e-8,
        'projector_idempotency_frobenius_max': 1e-8,
        'density_reconstruction_relative_frobenius_max': 1e-9,
        'energy_closure_abs_hartree_max': 1e-9,
        'overlap_eigenvalue_min': 1e-10,
        'overlap_condition_number_max': 1e10,
        'matrix_symmetry_abs_max': 1e-10,
    }
    for key, expected in fixed_tolerances.items():
        value = profile.get('tolerances', {}).get(key)
        if type(value) is not float or value != expected:
            raise ValueError('Fixed ordinary RHF acceptance tolerance differs: ' + key)
    if profile.get('protocol_id') != PROTOCOL_ID:
        raise ValueError('The fixed ordinary RHF protocol identity differs')
    return settings


def _validate_bundle(bundle):
    if not isinstance(bundle, dict) or not isinstance(bundle.get('molecule'), dict):
        raise ValueError('A checked molecular bundle is required')
    molecule = copy.deepcopy(bundle['molecule'])
    symbols = molecule.get('symbols')
    coordinates = molecule.get('geometry_angstrom')
    if not isinstance(symbols, list) or not 1 <= len(symbols) <= 20 or any(symbol not in ('H', 'C', 'N', 'O') for symbol in symbols):
        raise ValueError('Only one to twenty H/C/N/O atoms are supported')
    geometry = _array(coordinates, 'molecular coordinates in angstrom', (len(symbols), 3))
    if molecule.get('coordinate_unit') != 'angstrom' or molecule.get('atom_count') != len(symbols):
        raise ValueError('The checked molecule must retain its explicit atom count and angstrom coordinates')
    if float(np.max(np.abs(geometry))) > 10000:
        raise ValueError('Absolute coordinates exceed the fixed 10000 angstrom support bound')
    atom_rows = bundle.get('atoms')
    if not isinstance(atom_rows, list) or len(atom_rows) != len(symbols):
        raise ValueError('The original input atom mapping must be complete')
    for index, (row, symbol, coordinates) in enumerate(zip(atom_rows, symbols, geometry)):
        if (not isinstance(row, dict) or row.get('symbol') != symbol
                or type(row.get('index_0based')) is not int or row['index_0based'] != index
                or type(row.get('index_1based')) is not int or row['index_1based'] != index + 1
                or not np.array_equal(_array(row.get('xyz_angstrom'), 'mapped atom coordinates', (3,), ndim=1), coordinates)):
            raise ValueError('The original atom mapping differs from the checked molecular geometry')
    if type(molecule.get('charge')) is not int or molecule['charge'] != 0:
        raise ValueError('The first ordinary molecular profile supports neutral molecules')
    if type(molecule.get('multiplicity')) is not int or molecule['multiplicity'] != 1:
        raise ValueError('The first ordinary molecular profile supports singlets')
    nuclear_charge = {'H': 1, 'C': 6, 'N': 7, 'O': 8}
    electrons = sum(nuclear_charge[symbol] for symbol in symbols)
    if type(molecule.get('electron_count')) is not int or molecule['electron_count'] != electrons or electrons % 2 or electrons < 2:
        raise ValueError('Checked electron count must be a positive even neutral count')
    for i in range(len(symbols)):
        for j in range(i):
            if float(np.linalg.norm(geometry[i] - geometry[j])) < .5:
                raise ValueError('Inter-nuclear distance is below the supported 0.5 angstrom limit')
    for key in ('request_sha256', 'structure_sha256', 'profile_sha256', 'normalized_sha256'):
        if not isinstance(bundle.get(key), str) or not re.fullmatch('[0-9a-f]{64}', bundle[key]):
            raise ValueError('A checked input identity is required: ' + key)
    return molecule, [(symbol, tuple(map(float, row))) for symbol, row in zip(symbols, geometry)]


class _OperationLedger:
    def __init__(self, path, contract):
        self.path = Path(path)
        self.value = {'schema': 'molecular-single-point-operation-ledger-v1',
            'execution_id': contract['execution_id'], 'task': TASK, 'status': 'OPEN',
            'automatic_retry': False, 'refund': False,
            'entry_evidence': 'STARTED_IS_DURABLE_PRE_INVOKE_INTENT_NOT_CRASH_PROOF_OF_ENTRY',
            'operations': {'scf_kernel': {'limit': 1, 'charged': 0, 'entered': 0,
                'returned': 0, 'failed': 0, 'status': 'NOT_EXECUTED'}}, 'events': []}
        self.persist()

    def persist(self):
        _save(self.path, self.value)

    def call_scf(self, callback):
        row = self.value['operations']['scf_kernel']
        if row['charged'] != 0 or self.value['status'] != 'OPEN':
            raise RuntimeError('A charged ordinary SCF operation cannot be retried')
        row.update(charged=1, status='PENDING')
        self.value['events'].append({'event': 'SCF_KERNEL_STARTED', 'charged': True})
        try:
            self.persist()
        except BaseException:
            row.update(status='FAILED', failed=1)
            raise
        row['entered'] = 1
        try:
            result = callback()
        except BaseException as error:
            row.update(status='FAILED', failed=1, error=type(error).__name__ + ': ' + str(error))
            self.value['events'].append({'event': 'SCF_KERNEL_CLOSED', 'status': 'FAILED'})
            self.persist()
            raise
        row.update(status='SUCCEEDED', returned=1)
        self.value['events'].append({'event': 'SCF_KERNEL_CLOSED', 'status': 'SUCCEEDED'})
        self.persist()
        return result

    def close(self, reason):
        self.value.update(status='CLOSED', closure_reason=reason)
        self.persist()


def _load_engine():
    from pyscf import gto, lib, scf
    import pyscf
    return {'gto': gto, 'lib': lib, 'scf': scf, 'version': pyscf.__version__}


def _report(result):
    lines = ['# 用户分子普通单点与轨道／密度结果', '',
        '- 状态：' + result['status'],
        '- 方法：普通闭壳层 RHF / 6-31G(d)，固定用户核坐标。',
        '- 轨道与密度采用原始 AO 顺序；坐标为 Å，能量与轨道能量为 Hartree。',
        '- 本次不执行局域化、几何优化、条件态比较或稳定性分析。',
        '- SCF 收敛及数值资格不证明该解是稳定极小态。',
        '- HOMO/LUMO 能隙仅作观察，未沿用条件态正能隙门槛。',
        '- 电子密度输出为 AO 密度矩阵，不是网格密度或实验测量。', '']
    if result.get('execution_kind') == 'ENGINEERING_FAKE':
        lines += ['- 工程模拟结果，无真实科学验收资格。', '']
    if 'diagnostics' in result:
        diagnostics = result['diagnostics']
        lines += ['| 能量账本 | Hartree |', '| --- | ---: |']
        for key, label in (('one_electron', '单电子'), ('two_electron_coulomb_exchange', '双电子 Coulomb/Exchange'),
                           ('nuclear_repulsion', '核排斥'), ('scf_total', 'SCF 总能量'), ('closure_absolute', '账本闭合残差')):
            lines.append('| ' + label + ' | ' + f"{diagnostics['energy_ledger'][key]:.14g}" + ' |')
        lines += ['', '| 独立数值检查 | 结果 |', '| --- | --- |']
        lines += ['| ' + name + ' | ' + ('PASS' if passed else 'FAIL') + ' |' for name, passed in diagnostics['checks'].items()]
        lines += ['', '- HOMO/LUMO 能隙 / Hartree：' + str(diagnostics['orbital_summary']['homo_lumo_gap_hartree'])]
    if result.get('error'):
        lines += ['', '- 终止原因：' + result['error']]
    return '\n'.join(lines) + '\n'


def compute(bundle, profile, output_dir, *, checkpoint, execution_contract, engine_factory=None):
    """Compute exactly one approved ordinary RHF endpoint; never silently retry.

    The caller supplies the held native-entry guard, source/dependency/resource
    checks and external hard deadline.  These are separate from numeric checks.
    """
    if not callable(checkpoint):
        raise ValueError('A held cooperative checkpoint callback is required')
    contract, deadline = validate_execution_contract(execution_contract)
    settings = _validate_profile(profile)
    molecule, atoms = _validate_bundle(bundle)
    output = Path(output_dir).resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError('Molecular outputs must be outside the runtime source')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('A fresh empty molecular output directory is required; no resume')
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'EXECUTION_ID.json').open('x', encoding='utf-8') as stream:
        json.dump({'execution_id': contract['execution_id'], 'task': TASK}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    execution_kind = 'ENGINEERING_FAKE' if engine_factory is not None else 'PINNED_PYSCF_ORDINARY_RHF'
    result = {'schema': 'molecular-single-point-result-v1', 'task': TASK, 'profile_id': PROFILE_ID,
        'protocol_id': PROTOCOL_ID, 'status': 'NOT_EXECUTED', 'execution_kind': execution_kind,
        'scientific_qualified': False, 'numerically_qualified': False,
        'scope': 'SUPPORTED_USER_XYZ_ORDINARY_CLOSED_SHELL_RHF_SINGLE_POINT',
        'method': 'RHF', 'basis': '6-31G(d)', 'molecule': molecule,
        'request': copy.deepcopy(bundle.get('request')),
        'atoms': copy.deepcopy(bundle.get('atoms')),
        'execution_id': contract['execution_id'],
        **{key: bundle[key] for key in ('request_sha256', 'structure_sha256', 'profile_sha256', 'normalized_sha256')},
        'input_identity': {key: bundle[key] for key in ('request_sha256', 'structure_sha256', 'profile_sha256', 'normalized_sha256')},
        'execution_identity': contract, 'settings': copy.deepcopy(settings),
        'tolerances': dict(TOLERANCES), 'operations_closed': False,
        'conditional_state_compute': 'BLOCKED', 'conditional_scf_executed': False,
        'stability': 'NOT_EXECUTED', 'stability_status': 'NOT_EXECUTED',
        'localization': 'NOT_EXECUTED',
        'grid_density': 'NOT_EXECUTED', 'scientific_classification': None,
        'requested_calls': {'scf_kernel': 1, 'boys_kernel': 0, 'pipek_mezey_kernel': 0},
        'actual_native_call_counts': None,
        'native_count_evidence': 'EXTERNAL_HELD_GUARD_RECEIPT_REQUIRED',
        'density_semantics': 'SPIN_SUMMED_AO_DENSITY_IN_ORIGINAL_AO_ORDER',
        'units': {'geometry': 'angstrom', 'energy': 'hartree', 'orbital_energy': 'hartree',
            'density': 'spin-summed AO density matrix'},
        'index_convention': {'matrix_ao_rows_and_columns': 'zero-based original PySCF AO order',
            'molecular_orbital_arrays': 'zero-based returned PySCF MO order',
            'atom_ao_slices': 'zero-based atoms; half-open AO/shell intervals'}}
    ledger = None

    def checked(phase):
        if time.time() >= deadline:
            raise TimeoutError('Ordinary molecular cooperative deadline reached: ' + phase)
        checkpoint(phase)
        if time.time() >= deadline:
            raise TimeoutError('Ordinary molecular cooperative deadline reached after checkpoint: ' + phase)

    try:
        ledger = _OperationLedger(output / 'operation-ledger.json', contract)
        checked('BEFORE_ENGINE_IMPORT')
        engine = (engine_factory or _load_engine)()
        engine['lib'].num_threads(1)
        mol = engine['gto'].M(atom=atoms, unit='Angstrom', charge=0, spin=0,
                             basis='6-31G(d)', symmetry=False, verbose=0)
        if int(mol.nelectron) != molecule['electron_count']:
            raise ValueError('PySCF electron count differs from the checked input')
        nao = int(mol.nao_nr())
        if nao < molecule['electron_count'] // 2 or nao > 80:
            raise ValueError('Actual AO count is outside the fixed ordinary profile')
        mf = engine['scf'].RHF(mol)
        mf.conv_tol = 1e-12
        mf.conv_tol_grad = 1e-8
        mf.max_cycle = 100
        mf.max_memory = 768
        mf.chkfile = None
        mf.callback = lambda env: checked('SCF_ITERATION_' + str(int(env.get('cycle', -1)) + 1))
        checked('BEFORE_OVERLAP_PRECHECK')
        overlap = _array(mf.get_ovlp(), 'AO overlap', (nao, nao))
        _, _, precheck_metric = overlap_metric(overlap)
        result['ao_precheck'] = {'basis_function_count': nao, 'metric': precheck_metric}
        checked('BEFORE_SCF')
        energy = _real(ledger.call_scf(mf.kernel), 'SCF kernel total energy')
        checked('AFTER_SCF')
        coefficients = _array(mf.mo_coeff, 'canonical MO coefficients', (nao, nao))
        occupations = _array(mf.mo_occ, 'MO occupations', (nao,), ndim=1)
        orbital_energies = _array(mf.mo_energy, 'MO energies', (nao,), ndim=1)
        checked('BEFORE_ENDPOINT_ANALYSIS')
        density = _array(mf.make_rdm1(), 'spin-summed AO density', (nao, nao))
        hcore = _array(mf.get_hcore(), 'core Hamiltonian', (nao, nao))
        veff = _array(mf.get_veff(mol, density), 'ordinary RHF mean field', (nao, nao))
        fock = hcore + veff
        nuclear_energy = _real(mol.energy_nuc(), 'nuclear repulsion energy')
        diagnostics = orbital_density_diagnostics(overlap=overlap, density=density,
            coefficients=coefficients, occupations=occupations, orbital_energies=orbital_energies,
            fock=fock, hcore=hcore, veff=veff, electron_count=molecule['electron_count'],
            nuclear_energy=nuclear_energy, total_energy=energy, scf_converged=mf.converged)
        electronic, two_electron = mf.energy_elec(dm=density, h1e=hcore, vhf=veff)
        electronic = _real(electronic, 'PySCF electronic energy')
        two_electron = _real(two_electron, 'PySCF two-electron energy')
        package_energy_error = abs(electronic + nuclear_energy - energy)
        package_two_error = abs(two_electron - diagnostics['energy_ledger']['two_electron_coulomb_exchange'])
        diagnostics['residuals']['package_electronic_energy_closure_hartree'] = package_energy_error
        diagnostics['residuals']['package_two_electron_energy_closure_hartree'] = package_two_error
        diagnostics['checks']['package_energy_ledger_closure'] = max(package_energy_error, package_two_error) <= TOLERANCES['energy_ledger_closure_hartree']
        diagnostics['numerically_qualified'] = all(diagnostics['checks'].values())
        ao_labels = mol.ao_labels()
        if not isinstance(ao_labels, list) or len(ao_labels) != nao or not all(isinstance(label, str) for label in ao_labels):
            raise ValueError('The original-order AO labels are incomplete')
        raw_slices = np.asarray(mol.aoslice_by_atom())
        if raw_slices.dtype.kind not in 'iu' or raw_slices.shape != (len(atoms), 4):
            raise ValueError('Original-order integer AO slices are required for every atom')
        ao_slices = np.array(raw_slices, dtype=np.int64, copy=True)
        covered_aos = []
        atom_slices = []
        for index, row in enumerate(ao_slices):
            shell_start, shell_stop, ao_start, ao_stop = map(int, row)
            if not (0 <= shell_start <= shell_stop and 0 <= ao_start <= ao_stop <= nao):
                raise ValueError('An original atom AO/shell slice is invalid')
            covered_aos.extend(range(ao_start, ao_stop))
            atom_slices.append({'atom_index_0based': index, 'symbol': atoms[index][0],
                'shell_start_0based': shell_start, 'shell_stop_exclusive': shell_stop,
                'ao_start_0based': ao_start, 'ao_stop_exclusive': ao_stop})
        if covered_aos != list(range(nao)):
            raise ValueError('Atom AO slices must cover the original AO order exactly once')
        checked('AFTER_ENDPOINT_ANALYSIS')
        arrays = {'overlap': overlap, 'density': density, 'canonical_coefficients': coefficients,
            'orbital_energies_hartree': orbital_energies, 'occupations': occupations,
            'fock': fock, 'hcore': hcore, 'veff': veff}
        np.savez(output / 'orbitals-density.npz', **arrays)
        qualified = diagnostics['numerically_qualified']
        result.update(diagnostics=diagnostics, total_energy_hartree=energy,
            ao_labels=ao_labels, atom_ao_slices=atom_slices, orbital_energies_hartree=orbital_energies.tolist(),
            occupations=occupations.tolist(), basis_function_count=nao,
            scf={'converged': bool(mf.converged), 'cycles': int(getattr(mf, 'cycles', -1))},
            software={'pyscf': engine['version'], 'numpy': np.__version__},
            array_artifact_sha256=hashlib.sha256((output / 'orbitals-density.npz').read_bytes()).hexdigest(),
            endpoint_energy_function_evaluations=1,
            numerically_qualified=qualified, scientific_qualified=qualified and execution_kind != 'ENGINEERING_FAKE',
            status='NUMERICALLY_QUALIFIED_ORDINARY_RHF' if qualified else 'ORDINARY_RHF_NOT_QUALIFIED')
        if execution_kind == 'ENGINEERING_FAKE':
            result['status'] = 'ENGINEERING_FAKE_' + result['status']
        checked('BEFORE_RESULT_PUBLICATION')
    except BaseException as error:
        result.update(status='ORDINARY_RHF_FAILED', scientific_qualified=False,
            numerically_qualified=False, error=type(error).__name__ + ': ' + str(error))
        if execution_kind == 'ENGINEERING_FAKE':
            result['status'] = 'ENGINEERING_FAKE_' + result['status']
        raise
    finally:
        if ledger is not None:
            try:
                ledger.close(result['status'])
                result['operation_ledger'] = copy.deepcopy(ledger.value)
                result['operations_closed'] = True
            except BaseException as error:
                result.update(status='ORDINARY_RHF_CLOSURE_UNKNOWN', scientific_qualified=False,
                    numerically_qualified=False, closure_error=type(error).__name__ + ': ' + str(error))
                _save(output / 'result.json', result)
                raise
        _save(output / 'result.json', result)
        (output / 'report.md').write_text(_report(result), encoding='utf-8', newline='\n')
    return result
