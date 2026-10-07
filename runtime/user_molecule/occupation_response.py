"""Nine single-F observations, without a solver or endpoint acceptance.

The three AO-anchored densities must already be prepared.  This module does
not create a seed, repair a density, construct grids/integrals, select a state,
or iterate SCF.  A durable callback slot is charged before each invocation;
slots are accounting and never evidence of native F/NR executions.
"""
from __future__ import annotations

import hashlib
import math
from numbers import Real
import struct

import numpy as np

from .acceptance_resources import _lock
from .residual_budget import ConditionalCallbackBudget, CallbackBudgetError


PROBE_NAMES = ('AO_ANCHOR_A', 'AO_ANCHOR_B', 'AO_ANCHOR_SYMMETRIC_SUM')
PATH_NAMES = ('production_copy', 'production_owned', 'independent_reference')
EXECUTION_KINDS = frozenset(('ENGINEERING_FAKE', 'PREPARED_SINGLE_F_RESPONSE_DIAGNOSTIC'))
OPERATOR_SOURCE = 'TRUE_CONDITIONAL_AT_REQUESTED_DENSITY'
COMPONENTS = ('one_electron_energy', 'coulomb_energy', 'exact_exchange_energy',
              'semilocal_xc_energy', 'nuclear_repulsion')
# Copied unchanged from MDR-004's existing T05_same_density contract.  These
# comparisons only cover the explicitly available single-D operator subset.
SAME_D_THRESHOLDS = {'matrix_max_abs': 1e-10, 'matrix_frobenius': 1e-9,
    'component_hartree': 1e-9, 'total_energy_hartree': 1e-9,
    'grid_electron_count_abs': 1e-9}
ENGINEERING_FAKE_CALLBACK_COUNTS = {'entered': 0, 'completed': 0, 'failed': 0}


class FrozenRecord(dict):
    """JSON-compatible immutable saved evidence, including nested arrays."""
    def _refuse(self, *args, **kwargs):
        raise TypeError('Saved single-F response evidence is immutable')
    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = _refuse
    __ior__ = _refuse


def _freeze(value):
    if isinstance(value, np.ndarray):
        array = np.ascontiguousarray(value)
        return np.frombuffer(array.tobytes(), dtype=array.dtype).reshape(array.shape)
    if isinstance(value, dict):
        return FrozenRecord({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _matrix(value, name, shape=None):
    raw = np.asarray(value)
    if raw.dtype.kind not in 'iuf' or raw.ndim != 2 or not raw.shape[0] or raw.shape[0] != raw.shape[1]:
        raise ValueError(name+' must be a real nonempty square matrix')
    result = np.asarray(raw, dtype=np.float64).copy()
    if (shape is not None and result.shape != shape) or not np.isfinite(result).all():
        raise ValueError(name+' has invalid dimensions or nonfinite entries')
    if not np.allclose(result, result.T, rtol=0, atol=1e-12):
        raise ValueError(name+' must satisfy absolute symmetry <=1e-12')
    return result


def _scalar(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(name+' must be a finite real scalar, not boolean')
    return float(value)


def density_id(value):
    """Existing density-v1 canonical binary64 identity; not a new science rule."""
    raw = np.asarray(value)
    if raw.dtype.kind not in 'iuf' or raw.ndim != 2 or raw.shape[0] != raw.shape[1] or not raw.size:
        raise ValueError('Identity requires a real nonempty square matrix')
    array = np.ascontiguousarray(raw, dtype='<f8')
    if not np.isfinite(array).all():
        raise ValueError('Identity requires finite entries')
    header = b'AI4OrgChem-density-v1\0'+struct.pack('<QQ', *array.shape)
    return hashlib.sha256(header+array.tobytes(order='C')).hexdigest()


def _input_id(value):
    array = np.asarray(value)
    return (array.shape, array.dtype.str, hashlib.sha256(array.tobytes(order='C')).hexdigest())


def operator_id(requested_density_id, fock, raw_fock, components, total_energy):
    """Bind D/F/G and all five energies in an explicit response-v1 domain."""
    payload = (b'AI4OrgChem-single-F-response-operator-v1\0'
        + bytes.fromhex(requested_density_id)+bytes.fromhex(density_id(fock))
        + bytes.fromhex(density_id(raw_fock))
        + struct.pack('<6d', total_energy, *(components[name] for name in COMPONENTS))
        + OPERATOR_SOURCE.encode('ascii'))
    return hashlib.sha256(payload).hexdigest()


def _admit_density(density, overlap, electrons, half, inverse):
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        projector = .5*half @ density @ half
        values, vectors = np.linalg.eigh(projector)
        trace_error = abs(float(np.trace(projector))-electrons//2)
        idempotency = float(np.linalg.norm(projector@projector-projector))
        count = float(np.trace(overlap@density))
        occupied = vectors[:, np.argsort(values)[::-1]][:, :electrons//2]
        reconstructed = 2*inverse @ occupied @ occupied.T @ inverse.T
        reconstruction = float(np.linalg.norm(reconstructed-density)/max(np.linalg.norm(density), 1.0))
    measured = (trace_error, idempotency, count, reconstruction, *values)
    if not np.isfinite(measured).all() or not np.isfinite(projector).all():
        raise ValueError('Masked projector admission is nonfinite')
    if values.min() < -1e-10 or trace_error > 1e-10 or idempotency > 1e-10:
        raise ValueError('Density fails PSD/rank-N/2 whitened trace or absolute idempotency admission')
    if abs(count-electrons) > 1e-7 or reconstruction > 1e-10:
        raise ValueError('Density fails original masked electron count or production reconstruction admission')
    return {'masked_metric_electron_count': count, 'whitened_trace_error': trace_error,
        'whitened_absolute_idempotency': idempotency,
        'whitened_minimum_eigenvalue': float(values.min()),
        'production_density_reconstruction_relative': reconstruction,
        'repairs_performed': False}


def preflight_response_probes(*, probes, overlap, electrons, matrix_delete_mask):
    """Pure-array readiness for all three prepared probes, without callbacks.

    No journal is created and no callback parameter is accepted.  Return owned
    immutable copies of D/S/mask plus each unchanged admission check.  These
    algebraic checks are readiness evidence, never an execution authorization,
    native-call observation, scientific approval, or endpoint qualification.
    """
    if not isinstance(probes, dict) or set(probes) != set(PROBE_NAMES):
        raise ValueError('Exactly the three fixed AO-anchored probes are required')
    s = _matrix(overlap, 'Masked overlap')
    if type(electrons) is not int or electrons < 2 or electrons % 2 or electrons >= 2*len(s):
        raise ValueError('Global integer closed-shell occupancy with a virtual orbital required')
    mask = np.asarray(matrix_delete_mask)
    if mask.dtype.kind != 'b' or mask.shape != s.shape or not np.array_equal(mask, mask.T):
        raise ValueError('A same-size symmetric boolean deletion mask is required')
    if float(np.max(np.abs(s[mask]), initial=0)) > 1e-12:
        raise ValueError('Masked overlap violates the unchanged deletion mask')
    mask = mask.copy()
    sw, sv = np.linalg.eigh(s)
    if sw.min() <= 0:
        raise ValueError('Masked metric must be positive definite without repair')
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        half, inverse = (sv*np.sqrt(sw))@sv.T, (sv/np.sqrt(sw))@sv.T
    if not all(np.isfinite(a).all() for a in (half, inverse)):
        raise ValueError('Masked metric whitening must be finite')
    density_copies, admissions = {}, {}
    for probe in PROBE_NAMES:
        density_copies[probe] = _matrix(probes[probe], probe, s.shape)
        admissions[probe] = _admit_density(density_copies[probe], s, electrons, half, inverse)
    return _freeze({'status': 'PASS_PURE_ARRAY_RESPONSE_PROBE_READINESS',
        'admissions': admissions, 'density_copies': density_copies,
        'density_ids': {name: density_id(value) for name, value in density_copies.items()},
        'overlap': s, 'matrix_delete_mask': mask,
        'functional_calls': 0, 'repairs_performed': False,
        'scientific_execution_authorized': False, 'engine_qualified': False,
        'compute_enabled': False})


def _checked_snapshot(value, density, overlap, electrons, mask, *, probe_name, path_name, slot_id):
    from .solver_candidate import endpoint_gate
    if not isinstance(value, dict):
        raise ValueError('Callback must return its matched operator/energy dictionary')
    requested = density_id(density)
    if value.get('density_id') != requested or value.get('operator_source') != OPERATOR_SOURCE:
        raise ValueError('Callback density identity or true-operator provenance mismatch')
    if 'density' in value and density_id(_matrix(value['density'], 'Returned D', density.shape)) != requested:
        raise ValueError('Returned density bytes do not match requested D')
    fock = _matrix(value.get('fock'), 'True conditional F', density.shape)
    raw_fock = _matrix(value.get('raw_fock'), 'Unprojected G', density.shape)
    if float(np.max(np.abs(fock[mask]), initial=0)) > 1e-12:
        raise ValueError('True conditional F violates the unchanged matrix deletion mask')
    projected = raw_fock.copy()
    projected[mask] = 0.0
    if float(np.max(np.abs(projected-fock), initial=0)) > 1e-12:
        raise ValueError('F is inconsistent with Pmask(G)')
    components = {name: _scalar(value.get(name), name) for name in COMPONENTS}
    total = _scalar(value.get('total_energy'), 'total_energy')
    electronic = _scalar(value.get('electronic_energy'), 'electronic_energy')
    counts = {name: _scalar(value.get(name), name) for name in (
        'masked_metric_electron_count', 'physical_metric_electron_count', 'grid_electron_count')}
    closure = abs(sum(components.values())-total)
    if closure > 1e-9 or abs(electronic+components['nuclear_repulsion']-total) > 1e-9:
        raise ValueError('Callback energy components fail unchanged closure <=1e-9 Eh')
    if abs(counts['masked_metric_electron_count']-float(np.trace(overlap@density))) > 1e-7:
        raise ValueError('Callback masked electron count does not match the requested D/S')
    optional = {}
    for name in ('coulomb_matrix', 'exchange_matrix', 'semilocal_potential', 'xc_potential', 'J', 'K', 'V', 'Vxc'):
        if name in value:
            optional[name] = _matrix(value[name], name, density.shape)
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        gate = endpoint_gate(density=density, fock=fock, overlap=overlap,
            electrons=electrons, energy_closure_hartree=closure,
            overlap_mask_max_abs=float(np.max(np.abs(overlap[mask]), initial=0)),
            fock_mask_max_abs=float(np.max(np.abs(fock[mask]), initial=0)))
        mapped = gate['mapped_density']
        absolute_map = None if mapped is None else float(np.linalg.norm(mapped-density))
    gate.update(single_point_only=True, full_endpoint_qualified=False,
        raw_map_absolute_frobenius=absolute_map,
        raw_map_absolute_check=absolute_map is not None and absolute_map <= 2e-8,
        returned_density_energy_recheck='NOT_EXECUTED',
        mapped_density_true_operator_recheck='NOT_EXECUTED',
        endpoint_acceptance='NOT_EXECUTED_MISSING_SEPARATE_RETURNED_AND_MAPPED_RECHECKS')
    return _freeze({'probe_name': probe_name, 'path_name': path_name, 'slot_id': slot_id,
        'density': density, 'density_id': requested, 'fock': fock, 'raw_fock': raw_fock,
        'fock_id': density_id(fock), 'raw_fock_id': density_id(raw_fock),
        'operator_source': OPERATOR_SOURCE,
        'operator_id': operator_id(requested, fock, raw_fock, components, total),
        'components': components, 'total_energy': total, 'electronic_energy': electronic,
        **counts, 'energy_component_closure_hartree': closure,
        'optional_matrices': optional, 'single_point_diagnostics': gate,
        'engine_qualified': False, 'research_qualified': False})


def _comparisons(snapshots):
    results = []
    for probe in PROBE_NAMES:
        group = {row['path_name']: row for row in snapshots if row['probe_name'] == probe}
        if set(group) != set(PATH_NAMES):
            continue
        base = group['production_copy']
        for path in PATH_NAMES[1:]:
            other, checks = group[path], {}
            for field in ('fock', 'raw_fock'):
                difference = base[field]-other[field]
                maximum, norm = float(np.max(np.abs(difference))), float(np.linalg.norm(difference))
                checks[field] = {'max_abs': maximum, 'frobenius': norm,
                    'pass': maximum <= SAME_D_THRESHOLDS['matrix_max_abs'] and norm <= SAME_D_THRESHOLDS['matrix_frobenius']}
            for name in COMPONENTS:
                observed = abs(base['components'][name]-other['components'][name])
                checks[name] = {'abs_difference': observed, 'pass': observed <= SAME_D_THRESHOLDS['component_hartree']}
            for name, limit in (('total_energy', 'total_energy_hartree'),
                                ('grid_electron_count', 'grid_electron_count_abs')):
                observed = abs(base[name]-other[name])
                checks[name] = {'abs_difference': observed, 'pass': observed <= SAME_D_THRESHOLDS[limit]}
            results.append(_freeze({'probe_name': probe, 'left_path': 'production_copy',
                'right_path': path, 'density_id': base['density_id'], 'checks': checks,
                'status': 'PASS_SINGLE_D_OPERATOR_SUBSET' if all(row['pass'] for row in checks.values()) else 'FAIL_SINGLE_D_OPERATOR_SUBSET',
                'thresholds': dict(SAME_D_THRESHOLDS), 'full_T05': 'NOT_EXECUTED',
                'qualified_endpoint_equivalence': 'NOT_EXECUTED',
                'UM-P12': 'NOT_EXECUTED', 'UM-P13': 'NOT_EXECUTED', 'T06': 'NOT_EXECUTED'}))
    return tuple(results)


def run_response_probe(*, probes, callbacks, overlap, electrons,
                       matrix_delete_mask, journal, execution_kind='ENGINEERING_FAKE'):
    """Invoke three fixed prepared densities through three fixed paths once.

    Preflight failures raise before F.  An admitted fresh journal is always
    closed, including on preflight refusal.  Callback failures or invalid
    returned data consume one FAILED slot and stop the entire batch.  No
    retry, tail evaluation, solver, Jac, optimization or new seed is allowed.
    The real execution kind is only a declaration; a worker must separately
    supply observed native counters and resource/identity evidence.
    """
    if not isinstance(journal, ConditionalCallbackBudget):
        raise ValueError('A durable ConditionalCallbackBudget is required')
    # Separate admission lock: journal.charge/finish retain their own existing
    # locks; this prevents two orchestrators admitting the same empty book.
    with _lock(journal.path.with_name(journal.path.name+'.response.lock')):
        fresh = journal.snapshot()
        if (fresh['path_limits'] != {name: 3 for name in PATH_NAMES} or
                fresh['total_limit'] != 9 or fresh['charged_slots'] != 0 or
                any(row['state'] != 'OPEN' for row in fresh['paths'].values())):
            raise CallbackBudgetError('Require a new empty OPEN three-path journal with exactly3/9 slots; no retry/reset')
        snapshots, failure, admissions = [], None, {}
        reason, counts = 'PREFLIGHT_REFUSED', {'entered': 0, 'completed': 0, 'failed': 0}
        try:
            if execution_kind not in EXECUTION_KINDS:
                raise ValueError('Explicit supported execution_kind required')
            if (not isinstance(callbacks, dict) or set(callbacks) != set(PATH_NAMES)
                    or not all(callable(callbacks[name]) for name in PATH_NAMES)):
                raise ValueError('Exactly the three fixed callable operator paths are required')
            prepared = preflight_response_probes(probes=probes, overlap=overlap,
                electrons=electrons, matrix_delete_mask=matrix_delete_mask)
            s, mask = prepared['overlap'], prepared['matrix_delete_mask']
            density_copies, admissions = prepared['density_copies'], prepared['admissions']
            # Originals and the full fixed-name mappings remain bound, rather
            # than only checking the one D argument submitted to a callback.
            caller_arrays = {'overlap': overlap, 'matrix_delete_mask': matrix_delete_mask, **probes}
            frozen_ids = {name: _input_id(value) for name, value in caller_arrays.items()}
            callback_ids = {name: callbacks[name] for name in PATH_NAMES}
            original_probe_arrays = {name: probes[name] for name in PROBE_NAMES}

            def assert_frozen():
                if set(probes) != set(PROBE_NAMES) or set(callbacks) != set(PATH_NAMES):
                    raise ValueError('Caller changed fixed probe/path mapping')
                if any(callbacks[name] is not callback_ids[name] for name in PATH_NAMES):
                    raise ValueError('Caller replaced an admitted callback')
                if any(probes[name] is not original_probe_arrays[name] for name in PROBE_NAMES):
                    raise ValueError('Caller replaced an admitted density')
                if any(_input_id(value) != frozen_ids[name] for name, value in caller_arrays.items()):
                    raise ValueError('Caller changed frozen D/S/mask bytes')

            reason = 'SINGLE_F_RESPONSE_DIAGNOSTIC_COMPLETE'
            for probe in PROBE_NAMES:
                for path in PATH_NAMES:
                    try:
                        assert_frozen()
                    except Exception as error:
                        failure = {'exception_type': type(error).__name__, 'detail': str(error),
                            'probe_name': probe, 'path_name': path, 'callback_entered': False}
                        reason = 'SINGLE_F_RESPONSE_DIAGNOSTIC_REFUSED'
                        break
                    argument = density_copies[probe].copy()
                    requested = density_id(argument)
                    phase = 'SINGLE_F_RESPONSE_'+probe
                    slot = journal.charge(path, requested, phase)
                    try:
                        counts['entered'] += 1
                        if execution_kind == 'ENGINEERING_FAKE':
                            ENGINEERING_FAKE_CALLBACK_COUNTS['entered'] += 1
                        try:
                            value = callbacks[path](argument, phase)
                        except BaseException:
                            counts['failed'] += 1
                            if execution_kind == 'ENGINEERING_FAKE':
                                ENGINEERING_FAKE_CALLBACK_COUNTS['failed'] += 1
                            raise
                        counts['completed'] += 1
                        if execution_kind == 'ENGINEERING_FAKE':
                            ENGINEERING_FAKE_CALLBACK_COUNTS['completed'] += 1
                        if density_id(argument) != requested:
                            raise ValueError('Callback modified its requested D argument')
                        assert_frozen()
                        saved = _checked_snapshot(value, density_copies[probe], s, electrons,
                            mask, probe_name=probe, path_name=path, slot_id=slot['slot_id'])
                        journal.finish(slot['slot_id'], status='SUCCEEDED', operator_id=saved['operator_id'])
                        snapshots.append(saved)
                    except BaseException as error:
                        journal.finish(slot['slot_id'], status='FAILED', detail=(type(error).__name__+': '+str(error))[:2048])
                        reason = 'SINGLE_F_RESPONSE_DIAGNOSTIC_REFUSED'
                        failure = {'exception_type': type(error).__name__, 'detail': str(error),
                            'probe_name': probe, 'path_name': path, 'slot_id': slot['slot_id'],
                            'callback_entered': True}
                        if not isinstance(error, Exception):
                            raise
                        break
                if failure is not None:
                    break
        except BaseException:
            if reason == 'SINGLE_F_RESPONSE_DIAGNOSTIC_COMPLETE':
                reason = 'SINGLE_F_RESPONSE_DIAGNOSTIC_REFUSED'
            raise
        finally:
            for path, row in journal.snapshot()['paths'].items():
                if row['state'] == 'OPEN':
                    journal.close_path(path, reason)
        return {'probe_id': 'AO_ANCHORED_SINGLE_F_RESPONSE_DIAGNOSTIC_V1',
            'status': reason, 'stop_reason': reason, 'failure': failure,
            'execution_kind': execution_kind, 'probe_order': PROBE_NAMES, 'path_order': PATH_NAMES,
            'admissions': _freeze(admissions), 'snapshots': tuple(snapshots),
            'single_density_comparisons': _comparisons(snapshots),
            'callback_accounting': {'precharged_slots': journal.snapshot()['charged_slots'],
                **counts, 'refunds': 0, 'automatic_retries': 0,
                'counter_kind': 'WRAPPER_ENTRIES_NOT_NATIVE_F_OR_NR_OBSERVATIONS'},
            'engineering_fake_callback_counts': dict(counts) if execution_kind == 'ENGINEERING_FAKE' else None,
            'native_execution_counts': {'status': 'NOT_EXECUTED_ENGINEERING_SCOPE' if execution_kind == 'ENGINEERING_FAKE' else 'UNOBSERVED_WORKER_MUST_SUPPLY',
                'true_F': 0 if execution_kind == 'ENGINEERING_FAKE' else None,
                'nr_rks': 0 if execution_kind == 'ENGINEERING_FAKE' else None},
            'journal': journal.snapshot(), 'engine_qualified': False, 'research_qualified': False,
            'research_acceptance': 'NOT_ACCEPTED', 'compute_enabled': False,
            'production_activation': False, 'scientific_approval': False,
            'comparison_available': False, 'deltas': None, 'delta_hartree': None,
            'delta_kcal_mol': None, 'comparison_status': {'UM-P12': 'NOT_EXECUTED',
                'UM-P13': 'NOT_EXECUTED', 'T06': 'NOT_EXECUTED', 'full_T05': 'NOT_EXECUTED'},
            'solver_iterations': 0, 'jacobian_evaluations': 0, 'seed_policy_changes': 0,
            'external_review_status': 'CANCELLED_BY_USER',
            'variational_status': 'NOT_ESTABLISHED'}
