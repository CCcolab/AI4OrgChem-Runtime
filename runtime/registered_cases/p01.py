"""Fixed ethene occupied-representation control, adapted from the frozen P01 driver.

One ordinary RHF solution and one Boys/PM occupied rotation each. This is not
conditional SCF, a complete P01 re-certification, or the user-molecule Compute API.
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

TASK = 'p01-orbital-density'
PROTOCOL_ID = 'P01_ETHENE_OCCUPIED_GAUGE_CONTROL_V0.1'
PROTOCOL_SHA256 = 'd137c04a22fd221129f7a1e62fcafa6928e7ddee1493082ca40158a3c230ac47'
ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / 'reference/registered_cases/p01'
PROTOCOL_PATH = 'configs/qm/p01_ethene_orbital_density_control_v0.1.yaml'
GEOMETRY = (('C', -.6695, 0., 0.), ('C', .6695, 0., 0.),
            ('H', -1.2321, .9289, 0.), ('H', -1.2321, -.9289, 0.),
            ('H', 1.2321, .9289, 0.), ('H', 1.2321, -.9289, 0.))
TOLERANCES = MappingProxyType({'density_relative_frobenius': 1e-9, 'electron_number': 1e-8,
              'total_energy_hartree': 1e-9, 'occupied_unitarity_frobenius': 1e-8,
              'minimum_entropy_change': 1e-4})
OPERATIONS = ('scf_kernel', 'boys_kernel', 'pipek_mezey_kernel')


def _save(path, value):
    data = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True,
                       allow_nan=False) + '\n').encode('utf-8')
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('wb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def _finite(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise ValueError(name + ' must be a real finite scalar')
    result = float(value)
    if not math.isfinite(result): raise ValueError(name + ' must be finite')
    return result


def _array(value, name, shape=None):
    raw = np.asarray(value)
    if raw.dtype.kind not in 'fiu' or raw.ndim != 2:
        raise ValueError(name + ' must be a real matrix')
    result = np.array(raw, dtype=np.float64, copy=True)
    if (shape is not None and result.shape != shape) or not np.isfinite(result).all():
        raise ValueError(name + ' has an invalid shape or nonfinite entries')
    return result


def _array_sha(value):
    array = np.ascontiguousarray(value, dtype='<f8')
    return hashlib.sha256(b'p01-fixed-array-v1\0' + str(array.shape).encode('ascii') + b'\0' + array.tobytes()).hexdigest()


def validate_authorization(authorization):
    if not isinstance(authorization, dict): raise ValueError('Explicit execution scope is required')
    fixed = {'schema': 'registered-case-execution-v1', 'task': TASK, 'protocol_id': PROTOCOL_ID,
             'scientific_execution_authorized': True, 'scf_kernel_call_limit': 1,
             'boys_kernel_call_limit': 1, 'pipek_mezey_kernel_call_limit': 1,
             'maximum_processes': 1, 'threads': 1, 'memory_limit_bytes': 1073741824,
             'wall_time_limit_seconds': 120, 'stop_after_seconds': 100,
             'p01_protocol_sha256': PROTOCOL_SHA256}
    for key, value in fixed.items():
        if type(authorization.get(key)) is not type(value) or authorization.get(key) != value:
            raise ValueError('Execution scope mismatch: ' + key)
    for key, length in (('runtime_commit', 40), ('source_snapshot_sha256', 64), ('execution_id', 32)):
        if not isinstance(authorization.get(key), str) or not re.fullmatch('[0-9a-f]{' + str(length) + '}', authorization[key]):
            raise ValueError('Explicit identity required: ' + key)
    now = time.time()
    deadline = _finite(authorization.get('stop_deadline_epoch', now + 100), 'stop_deadline_epoch')
    if deadline <= now or deadline > now + 100:
        raise ValueError('Stop deadline must be a future non-extended 100-second bound')
    return copy.deepcopy(authorization), deadline


def verify_frozen_source():
    manifest = json.loads((SOURCE_ROOT / 'SOURCE_METADATA.json').read_text(encoding='utf-8'))
    if manifest.get('protocol_id') != PROTOCOL_ID:
        raise ValueError('Frozen source protocol identity differs')
    for item in manifest['sources']:
        path = SOURCE_ROOT / item['path']
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Frozen source bytes differ: ' + item['path'])
    if hashlib.sha256((SOURCE_ROOT / PROTOCOL_PATH).read_bytes()).hexdigest() != PROTOCOL_SHA256:
        raise ValueError('Frozen protocol differs from the execution contract')
    return manifest


def symmetric_matrix_power(matrix, power):
    matrix = _array(matrix, 'overlap')
    if matrix.shape[0] != matrix.shape[1] or not np.allclose(matrix, matrix.T, rtol=0, atol=1e-12):
        raise ValueError('AO overlap must be a real symmetric square matrix')
    eigenvalues, eigenvectors = np.linalg.eigh(matrix)
    if float(np.min(eigenvalues)) <= 0:
        raise ValueError('AO overlap matrix is not positive definite')
    return (eigenvectors * np.power(eigenvalues, power)) @ eigenvectors.T


def representation_diagnostics(name, coefficients, canonical_occupied, overlap, group_indices,
                               reference_energy, energy_function):
    """Pure-array original P01 diagnostics; energy_function never runs a new SCF."""
    canonical = _array(canonical_occupied, 'canonical occupied')
    coefficients = _array(coefficients, name + ' occupied', canonical.shape)
    overlap = _array(overlap, 'overlap', (canonical.shape[0], canonical.shape[0]))
    overlap_half = symmetric_matrix_power(overlap, .5)
    if canonical.shape[1] < 1: raise ValueError('Occupied space cannot be empty')
    groups = []
    for group in ('left_ch2', 'right_ch2'):
        raw = np.asarray(group_indices[group])
        if raw.ndim != 1 or raw.dtype.kind not in 'iu' or raw.size < 1:
            raise ValueError('Explicit nonempty AO groups required')
        groups.append(np.array(raw, dtype=np.int64, copy=True))
    combined = np.concatenate(groups)
    if len(combined) != canonical.shape[0] or sorted(combined.tolist()) != list(range(canonical.shape[0])):
        raise ValueError('AO groups must partition the whole original AO order')
    rotation = canonical.T @ overlap @ coefficients
    unitary = float(np.linalg.norm(rotation.T @ rotation - np.eye(coefficients.shape[1]), ord='fro'))
    reference_density = 2 * canonical @ canonical.T
    density = 2 * coefficients @ coefficients.T
    absolute = float(np.linalg.norm(density - reference_density, ord='fro'))
    reference_norm = float(np.linalg.norm(reference_density, ord='fro'))
    if reference_norm <= 0: raise ValueError('Reference density cannot vanish')
    reference_electrons = float(np.einsum('ij,ji->', reference_density, overlap))
    electrons = float(np.einsum('ij,ji->', density, overlap))
    energy = _finite(energy_function(density.copy()), 'RHF total energy')
    reference_energy = _finite(reference_energy, 'canonical RHF energy')
    lowdin = overlap_half @ coefficients
    support = []
    for index in range(coefficients.shape[1]):
        vector = lowdin[:, index]
        weights = np.array([np.sum(np.square(vector[group])) for group in groups], dtype=np.float64)
        total = float(np.sum(weights))
        if total <= 0: raise ValueError('An orbital has zero support')
        weights /= total
        positive = weights[weights > 1e-15]
        entropy = float(-np.sum(positive * np.log2(positive)))
        support.append({'occupied_orbital_index': index, 'left_ch2_weight': float(weights[0]),
                        'right_ch2_weight': float(weights[1]), 'binary_support_entropy': entropy})
    entropies = [row['binary_support_entropy'] for row in support]
    return {'name': name, 'occupied_orbital_count': coefficients.shape[1],
            'occupied_subspace_unitarity_residual': unitary,
            'density_frobenius_residual_from_canonical': absolute,
            'density_relative_frobenius_residual_from_canonical': absolute / reference_norm,
            'electron_number': electrons,
            'electron_number_residual_from_canonical': abs(electrons - reference_electrons),
            'rhf_total_energy_hartree': energy,
            'energy_residual_from_canonical_hartree': abs(energy - reference_energy),
            'mean_binary_support_entropy': float(np.mean(entropies)),
            'minimum_binary_support_entropy': min(entropies), 'maximum_binary_support_entropy': max(entropies),
            'orbital_support': support,
            'coefficient_sha256': _array_sha(coefficients), 'density_sha256': _array_sha(density)}


def assess_representations(representations, *, scf_converged):
    if [row['name'] for row in representations] != ['canonical', 'boys', 'pipek_mezey']:
        raise ValueError('Exactly canonical/Boys/Pipek-Mezey are required in order')
    if type(scf_converged) is not bool: raise ValueError('Exact SCF convergence boolean required')
    changes = {row['name']: row['mean_binary_support_entropy'] - representations[0]['mean_binary_support_entropy']
               for row in representations[1:]}
    fields = {'all_representations_span_same_occupied_subspace': ('occupied_subspace_unitarity_residual', 'occupied_unitarity_frobenius'),
              'ao_density_invariant': ('density_relative_frobenius_residual_from_canonical', 'density_relative_frobenius'),
              'electron_number_invariant': ('electron_number_residual_from_canonical', 'electron_number'),
              'rhf_energy_invariant': ('energy_residual_from_canonical_hartree', 'total_energy_hartree')}
    findings = {'scf_converged': scf_converged}
    for name, (field, threshold) in fields.items():
        findings[name] = max(_finite(row[field], field) for row in representations) <= TOLERANCES[threshold]
    findings['orbital_fragment_support_changes'] = max(abs(_finite(x, 'entropy change')) for x in changes.values()) >= TOLERANCES['minimum_entropy_change']
    findings['same_state_orbital_representation_is_not_electron_state_delocalization'] = True
    findings['chemical_stabilization_label_authorized'] = False
    qualified = all(value for key, value in findings.items() if key != 'chemical_stabilization_label_authorized')
    return findings, changes, qualified


class _OperationLedger:
    def __init__(self, output, authorization):
        self.path = output / 'operation-ledger.json'
        self.value = {'schema': 'p01-single-serial-operation-ledger-v1', 'execution_id': authorization['execution_id'],
                      'task': TASK, 'status': 'OPEN', 'automatic_retry': False, 'refund': False,
                      'entry_evidence': 'STARTED_IS_DURABLE_PRE_INVOKE_INTENT_NOT_CRASH_PROOF_OF_ENTRY',
                      'operations': {name: {'limit': 1, 'charged': 0, 'entered': 0, 'returned': 0,
                                            'failed': 0, 'status': 'NOT_EXECUTED'} for name in OPERATIONS}, 'events': []}
        self.failed = False
        self.persist()

    def persist(self): _save(self.path, self.value)

    def call(self, name, callback):
        row = self.value['operations'][name]
        if self.failed or self.value['status'] != 'OPEN' or row['charged']:
            raise RuntimeError('Charged operation cannot be retried')
        row['charged'] = 1; row['status'] = 'PENDING'
        self.value['events'].append({'event': name.upper() + '_STARTED', 'charged': True})
        try:
            self.persist()
        except BaseException:
            self.failed = True
            row['failed'] = 1; row['status'] = 'FAILED'
            row['error'] = 'Durable pre-invoke intent publication failed; delegate not entered'
            raise
        row['entered'] = 1
        try:
            result = callback()
        except BaseException as error:
            row['failed'] = 1; row['status'] = 'FAILED'; self.failed = True
            row['error'] = type(error).__name__ + ': ' + str(error)
            self.value['events'].append({'event': name.upper() + '_CLOSED', 'status': 'FAILED'})
            self.persist(); raise
        row['returned'] = 1; row['status'] = 'SUCCEEDED'
        self.value['events'].append({'event': name.upper() + '_CLOSED', 'status': 'SUCCEEDED'})
        self.persist()
        return result

    def close(self, reason):
        self.value['status'] = 'CLOSED'; self.value['closure_reason'] = reason
        self.persist()


def _load_engine():
    from pyscf import gto, lib, lo, scf
    import pyscf
    return {'gto': gto, 'lib': lib, 'lo': lo, 'scf': scf, 'version': pyscf.__version__}


def _checkpoint(deadline, phase):
    if time.time() >= deadline: raise TimeoutError('P01 cooperative deadline reached: ' + phase)


def _report(result):
    lines = ['# P01 固定乙烯占据表示控制', '', '- 状态：' + result['status'],
             '- 仅一次普通 RHF/6-31G(d)；Boys/PM 是同占据空间表示变换。',
             '- 不执行条件 SCF，不产生稳定化/去稳定化标签，不重新开放用户 Compute。',
             '- 本结果不是原项目全部 P01 证据或原著程序的重新认证。',
             '- 软截止为合作检查，不能即时中断正在执行的 C 扩展。', '']
    if result.get('representations'):
        lines += ['| 表示 | 平均 CH2 支持熵 | 密度相对残差 | 电子数残差 | 能量残差/Eh | 占据酉性残差 |',
                  '| --- | ---: | ---: | ---: | ---: | ---: |']
        for row in result['representations']:
            lines.append('| ' + row['name'] + ' | ' + ' | '.join(f'{row[key]:.12g}' for key in
                ('mean_binary_support_entropy', 'density_relative_frobenius_residual_from_canonical',
                 'electron_number_residual_from_canonical', 'energy_residual_from_canonical_hartree',
                 'occupied_subspace_unitarity_residual')) + ' |')
    if result.get('error'): lines += ['', '- 失败：' + result['error']]
    return '\n'.join(lines) + '\n'


def _execute(output_dir, *, authorization, engine_factory, execution_kind):
    authorization, deadline = validate_authorization(authorization)
    sources = verify_frozen_source()
    output = Path(output_dir)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('A fresh empty case output directory is required; no resume')
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'EXECUTION_ID.json').open('x', encoding='utf-8') as stream:
        json.dump({'execution_id': authorization['execution_id'], 'task': TASK}, stream)
        stream.flush(); os.fsync(stream.fileno())
    result = {'schema': 'registered-p01-occupied-representation-control-v1', 'task': TASK,
              'protocol_id': PROTOCOL_ID, 'execution_kind': execution_kind, 'status': 'NOT_EXECUTED',
              'scientific_scope': 'ONE_FIXED_ETHENE_OCCUPIED_REPRESENTATION_CONTROL_ONLY',
              'scientific_qualified': False, 'Compute': False, 'user_molecule_compute_enabled': False,
              'chemical_stabilization_label_authorized': False, 'delta_energy_research': None,
              'authorization': authorization, 'source_metadata': sources,
              'implementation': 'RUNTIME_ADAPTER_OF_FROZEN_WORKTREE_P01_DRIVER_NOT_ORIGINAL_PROGRAM',
              'geometry_angstrom': [list(row) for row in GEOMETRY], 'charge': 0, 'spin': 0,
              'method': 'RHF', 'basis': '6-31G(d)', 'symmetry': False, 'tolerances': dict(TOLERANCES),
              'resource_override': {'frozen_protocol_threads': 4, 'execution_threads': 1,
                                    'changes_scientific_thresholds': False},
              'native_NR_count': None, 'native_NR_count_evidence': 'NOT_OBSERVED_BY_CASE_DRIVER',
              'operations_closed': False}
    ledger = None
    try:
        ledger = _OperationLedger(output, authorization)
        _checkpoint(deadline, 'BEFORE_ENGINE_IMPORT')
        engine = engine_factory()
        engine['lib'].num_threads(1)
        mol = engine['gto'].M(atom=[(row[0], tuple(row[1:])) for row in GEOMETRY], unit='Angstrom',
                              charge=0, spin=0, basis='6-31G(d)', symmetry=False, verbose=0)
        if int(mol.nelectron) != 16: raise ValueError('Fixed ethene must have sixteen electrons')
        mf = engine['scf'].RHF(mol)
        mf.conv_tol = 1e-12; mf.max_cycle = 100; mf.max_memory = 768
        _checkpoint(deadline, 'BEFORE_SCF')
        canonical_energy = _finite(ledger.call('scf_kernel', mf.kernel), 'canonical RHF energy')
        _checkpoint(deadline, 'AFTER_SCF')
        if not isinstance(mf.converged, (bool, np.bool_)) or not bool(mf.converged):
            raise RuntimeError('Fixed ethene ordinary RHF did not converge')
        all_coeff = _array(mf.mo_coeff, 'RHF coefficients')
        occupation = np.asarray(mf.mo_occ)
        if (occupation.ndim != 1 or occupation.shape[0] != all_coeff.shape[1]
                or not np.isfinite(occupation).all() or np.count_nonzero(occupation == 2) != 8
                or not np.all((occupation == 0) | (occupation == 2))):
            raise ValueError('Fixed global RHF occupation must be eight doubly occupied orbitals')
        occupied = all_coeff[:, occupation > 0].copy()
        overlap = _array(mf.get_ovlp(), 'AO overlap', (occupied.shape[0], occupied.shape[0]))
        symmetric_matrix_power(overlap, .5)
        representations = {'canonical': occupied}
        for label, operation, factory in (('boys', 'boys_kernel', engine['lo'].Boys),
                                           ('pipek_mezey', 'pipek_mezey_kernel', engine['lo'].PM)):
            _checkpoint(deadline, 'BEFORE_' + operation.upper())
            localizer = factory(mol, occupied.copy())
            localizer.conv_tol = 1e-10; localizer.max_cycle = 200
            representations[label] = _array(ledger.call(operation, localizer.kernel), label + ' coefficients', occupied.shape)
            _checkpoint(deadline, 'AFTER_' + operation.upper())
        slices = np.asarray(mol.aoslice_by_atom())
        if slices.shape != (6, 4): raise ValueError('Fixed six-atom AO slices are required')
        groups = {name: np.concatenate([np.arange(int(slices[index, 2]), int(slices[index, 3])) for index in atoms])
                  for name, atoms in (('left_ch2', (0, 2, 3)), ('right_ch2', (1, 4, 5)))}
        rows = []
        for name, coefficients in representations.items():
            _checkpoint(deadline, 'BEFORE_ENERGY_' + name.upper())
            rows.append(representation_diagnostics(name, coefficients, occupied, overlap, groups,
                canonical_energy, lambda density: mf.energy_tot(dm=density)))
            _checkpoint(deadline, 'AFTER_ENERGY_' + name.upper())
        findings, changes, qualified = assess_representations(rows, scf_converged=True)
        result.update(representations=rows, findings=findings, entropy_change_from_canonical=changes,
            scf={'converged': True, 'cycles': int(getattr(mf, 'cycles', -1)),
                 'total_energy_hartree': canonical_energy, 'electron_number': rows[0]['electron_number'],
                 'nuclear_repulsion_hartree': _finite(mol.energy_nuc(), 'nuclear energy'),
                 'basis_function_count': occupied.shape[0], 'occupied_orbital_count': 8},
            software={'pyscf': engine['version'], 'numpy': np.__version__},
            density_energy_function_evaluations=3,
            fragment_support_definition='symmetric_lowdin_ao_group_population',
            orbital_support_entropy='binary_shannon_entropy_base_2')
        arrays = {'overlap': overlap, **{name + '_occupied': value for name, value in representations.items()},
                  **{name + '_density': 2 * value @ value.T for name, value in representations.items()}}
        np.savez(output / 'occupied-representations.npz', **arrays)
        result['array_artifact_sha256'] = hashlib.sha256((output / 'occupied-representations.npz').read_bytes()).hexdigest()
        result['control_qualified'] = qualified
        result['scientific_qualified'] = qualified and execution_kind == 'REGISTERED_FIXED_P01_QM_CONTROL'
        result['status'] = ('P01_FIXED_CONTROL_PASSED' if qualified else 'P01_FIXED_CONTROL_NOT_QUALIFIED')
        if execution_kind == 'ENGINEERING_FAKE': result['status'] = 'ENGINEERING_FAKE_' + result['status']
        _checkpoint(deadline, 'BEFORE_FINAL_PUBLICATION')
    except BaseException as error:
        result.update(status='P01_FIXED_CONTROL_FAILED', scientific_qualified=False,
                      error=type(error).__name__ + ': ' + str(error))
        raise
    finally:
        if ledger is not None:
            try:
                ledger.close(result['status']); result['operation_ledger'] = copy.deepcopy(ledger.value)
                result['operations_closed'] = True
            except BaseException as error:
                result.update(status='P01_CLOSURE_UNKNOWN', scientific_qualified=False,
                              closure_error=type(error).__name__ + ': ' + str(error))
                _save(output / 'case-result.json', result)
                raise
        _save(output / 'case-result.json', result)
        (output / 'case-report.md').write_text(_report(result), encoding='utf-8', newline='\n')
    return result


def run(output_dir: Path, *, authorization: dict) -> dict:
    """Authorized one-process case. Host supplies separate ownership and resource proof."""
    return _execute(output_dir, authorization=authorization, engine_factory=_load_engine,
                    execution_kind='REGISTERED_FIXED_P01_QM_CONTROL')
