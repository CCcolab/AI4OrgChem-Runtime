"""Isolated engineering TRF reference with whole-Jacobian budget admission.

No molecular entry point imports this candidate.  Its evaluator, target and
endpoint arithmetic are the unchanged independent-reference contract.  The
new work is explicit finite-difference accounting and immutable matched
snapshots; it does not select a different occupied state or accepted return.
"""
from __future__ import annotations

import hashlib
import math
import struct
import time

import numpy as np
from scipy import __version__ as scipy_version
from scipy.linalg import eigh, expm
from scipy.optimize import least_squares
from scipy.optimize._numdiff import approx_derivative

from . import residual_candidate as original


REFERENCE_ID = 'INDEPENDENT_BUDGETED_ORBITAL_TRF_ENGINEERING_CANDIDATE_V1'
TRUE_OPERATOR = original.TRUE_OPERATOR
THRESHOLDS = dict(original.THRESHOLDS)
COMPONENTS = original.COMPONENTS
POLICIES = frozenset(original.POLICIES)
ReferenceRefusal = original.ReferenceRefusal
real_array = original.real_array
real_scalar = original.real_scalar
density_id = original.density_id
TAIL_SLOTS = 2
DERIVATIVE_POLICY = 'PINNED_SCIPY_PRIVATE_APPROX_DERIVATIVE_THREE_POINT_V1'
REQUIRED_SCIPY_VERSION = '1.18.0'


class FrozenRecord(dict):
    """A JSON-compatible mapping whose saved entries cannot be rewritten."""

    def _refuse(self, *args, **kwargs):
        raise TypeError('Saved engineering snapshot is immutable')

    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = _refuse
    __ior__ = _refuse


def _frozen_array(value):
    array = np.ascontiguousarray(value, dtype=np.float64)
    # Immutable backing bytes also prevent setflags(write=True), unlike a
    # writable owning array on which only the writeable flag was cleared.
    return np.frombuffer(array.tobytes(), dtype=np.float64).reshape(array.shape)


def _freeze(value):
    if isinstance(value, np.ndarray):
        return _frozen_array(value)
    if isinstance(value, dict):
        return FrozenRecord({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    return value


def operator_id(dm_id, fock, energy, components):
    """Bind requested D, true F and the complete energy ledger together."""
    fock_id = density_id(fock)
    payload = (b'AI4OrgChem-matched-reference-operator-v1\0'
               + bytes.fromhex(dm_id) + bytes.fromhex(fock_id)
               + struct.pack('<6d', energy, *(components[key] for key in COMPONENTS))
               + TRUE_OPERATOR.encode('ascii'))
    return hashlib.sha256(payload).hexdigest()


def solve_budgeted_candidate(*, density, overlap, electrons, evaluate,
          initialization_policy, maximum_evaluations=201, maximum_iterations=8,
          finite_difference_step=1e-5, trust_radius=.25, matrix_delete_mask=None):
    """Run fake-array engineering only; all true-F callbacks are precharged.

    A refused/incomplete Jacobian never automatically consumes the two tail
    slots.  COMPLETE_OPTIMIZER_BASE means a completed charged F(base) and its
    residual, not a completed Jacobian; last_complete_jacobian_base is separate.
    Returned D remains the last completely accepted chart (the initial
    seed when no chart completes).  Neither best base nor best FD sample is
    substituted as the return.  Original final gates remain mandatory.
    """
    if scipy_version != REQUIRED_SCIPY_VERSION:
        raise ValueError('Engineering derivative helper requires pinned SciPy '+REQUIRED_SCIPY_VERSION)
    if initialization_policy not in POLICIES or not callable(evaluate):
        raise ValueError('Explicit supported initialization policy and evaluator required')
    for name, value, ceiling in (('maximum_evaluations', maximum_evaluations, 201),
                                 ('maximum_iterations', maximum_iterations, 100)):
        if type(value) is not int or not 1 <= value <= ceiling:
            raise ValueError(name+' must be a bounded integer')
    finite_difference_step = real_scalar(finite_difference_step, 'Finite difference step')
    trust_radius = real_scalar(trust_radius, 'TRF local chart radius')
    if not 0 < finite_difference_step <= trust_radius <= 1:
        raise ValueError('Require 0 < finite_difference_step <= trust_radius <= 1')
    d0 = real_array(density, 'Initial density').copy()
    s = real_array(overlap, 'Masked overlap').copy()
    if (d0.ndim != 2 or d0.shape[0] != d0.shape[1] or s.shape != d0.shape
            or any(not np.allclose(a, a.T, rtol=0, atol=1e-12) for a in (d0, s))):
        raise ValueError('Same-size symmetric density and overlap matrices required')
    n = len(d0)
    if type(electrons) is not int or electrons < 2 or electrons % 2 or electrons >= 2*n:
        raise ValueError('Global integer closed-shell occupation and a virtual orbital required')
    occupied, k = electrons//2, (electrons//2)*(n-electrons//2)
    if k > 64:
        raise ValueError('Reference is limited to 64 occupied--virtual variables')
    sw, sv = np.linalg.eigh(s)
    if sw.min() <= 0:
        raise ValueError('Masked overlap must be positive definite; no repair allowed')
    try:
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            x, half = (sv/np.sqrt(sw))@sv.T, (sv*np.sqrt(sw))@sv.T
    except FloatingPointError as error:
        raise ValueError('Metric whitening overflowed') from error
    if not all(np.isfinite(value).all() for value in (x, half)):
        raise ValueError('Metric whitening must be finite')
    mask = np.zeros(d0.shape, dtype=bool) if matrix_delete_mask is None else np.asarray(matrix_delete_mask).copy()
    if mask.dtype.kind != 'b' or mask.shape != d0.shape or not np.array_equal(mask, mask.T):
        raise ValueError('Symmetric same-size boolean mask required')

    def frame(dm):
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            p = .5*half@dm@half
            defect, count = float(np.linalg.norm(p@p-p)), float(np.trace(p))
        if not np.isfinite(p).all() or not math.isfinite(defect) or defect > 1e-10 or abs(count-occupied) > 1e-10:
            raise ValueError('Initial density is not the existing masked 2/0 projector; no projection allowed')
        _, coefficients = np.linalg.eigh((p+p.T)/2)
        return coefficients[:, ::-1]

    d = d0.copy()
    if initialization_policy == 'REQUIRE_EXISTING_MASKED_PROJECTOR':
        try:
            initial_frame = frame(d)
        except FloatingPointError as error:
            raise ValueError('Initial projector diagnostics overflowed') from error
    ledger, operators, history, admissions, snapshots, fd_samples = [], {}, [], [], {}, []
    reason, failure, qualified, gate, mapped_gate = 'MAXIMUM_CHARTS_EXHAUSTED', None, False, None, None
    initialized = {'policy': initialization_policy, 'ordinary_density_id': density_id(d0), 'status': 'NOT_EXECUTED'}
    current, scipy_summary = None, None
    optimizer_base = best_base = best_any = last_call = last_validated = None
    last_complete_jacobian_base = None
    tail = {'reserved_callbacks': TAIL_SLOTS, 'status': 'NOT_EXECUTED',
            'automatic_after_budget_refusal': False, 'actual_callbacks': 0}

    def admission(kind, cost, reserve=TAIL_SLOTS, context=None):
        remaining = maximum_evaluations-len(ledger)
        row = {'kind': kind, 'call_count_before': len(ledger), 'required_callbacks': cost,
               'tail_callbacks_reserved': reserve, 'remaining_callbacks': remaining,
               'admitted': remaining >= cost+reserve, 'actual_callbacks': 0,
               'status': 'ADMITTED' if remaining >= cost+reserve else 'REFUSED_ZERO_CALLBACKS'}
        row.update(context or {})
        admissions.append(row)
        if not row['admitted']:
            refusal = 'JACOBIAN_BUDGET_ADMISSION_REFUSED' if kind == 'COMPLETE_JACOBIAN' else 'FINAL_TAIL_BUDGET_ADMISSION_REFUSED'
            raise ReferenceRefusal(refusal, 'Complete '+kind+' requires '+str(cost)+' callbacks and '+str(reserve)+' tail slots; no callback was made after refusal')
        return row

    def frozen_call(dm, phase, coordinates=None, reserve=0, detail=None):
        nonlocal last_call, last_validated
        if len(ledger) >= maximum_evaluations-reserve:
            raise ReferenceRefusal('EVALUATION_BUDGET_EXHAUSTED', 'Every actual callback, including failed finite differences, consumes the hard budget')
        argument = dm.copy()
        identity = density_id(argument)
        row = {'evaluation_count': len(ledger)+1, 'phase': phase, 'density_id': identity,
               'status': 'STARTED', 'precharged': True, 'callback_entered': False,
               'callback_completed': False, 'callback_failed': False,
               'execution_kind': 'ENGINEERING_EVALUATOR_CALLBACK',
               'native_molecular_execution': 'NOT_AUTHORIZED'}
        if coordinates is not None:
            row['local_rotation_coordinates'] = np.asarray(coordinates).tolist()
        if detail is not None:
            row.update(detail)
        ledger.append(row)
        last_call = {'evaluation_count': len(ledger), 'phase': phase, 'density_id': identity,
                     'density': _frozen_array(argument), 'status': 'STARTED', 'matched_snapshot_id': None}
        started = time.monotonic()
        try:
            row['callback_entered'] = True
            value = evaluate(argument)
            row['callback_completed'] = True
            if density_id(argument) != identity:
                raise ReferenceRefusal('REQUESTED_DENSITY_MODIFIED', 'Evaluator modified its requested density')
            if (not isinstance(value, dict) or value.get('density_id') != identity
                    or value.get('operator_source') != TRUE_OPERATOR):
                raise ReferenceRefusal('EVALUATOR_IDENTITY_MISMATCH', 'Evaluator must bind true F to the exact requested density')
            fock = real_array(value.get('fock'), 'True F').copy()
            if fock.shape != dm.shape or not np.allclose(fock, fock.T, rtol=0, atol=1e-12):
                raise ValueError('True F dimensions or symmetry differ')
            checked = {'fock': fock, 'density_id': identity, 'operator_source': TRUE_OPERATOR}
            for key in ('total_energy', *COMPONENTS):
                checked[key] = real_scalar(value.get(key), key)
            fock_id = density_id(fock)
            prior = operators.get(identity)
            row.update(fock_id=fock_id, previous_same_density_fock_id=prior,
                       same_density_operator_reproducible=None if prior is None else fock_id == prior)
            if prior is not None and fock_id != prior:
                raise ReferenceRefusal('NONREPRODUCIBLE_SAME_DENSITY_OPERATOR', 'Same density returned different true-F bytes')
            operators[identity] = fock_id
            components = {key: checked[key] for key in COMPONENTS}
            matched_id = operator_id(identity, fock, checked['total_energy'], components)
            snapshot_id = 'evaluation-'+str(len(ledger))
            snapshot = _freeze({'snapshot_id': snapshot_id, 'evaluation_count': len(ledger),
                'phase': phase, 'density': dm.copy(), 'density_id': identity, 'fock': fock,
                'fock_id': fock_id, 'operator_id': matched_id, 'operator_source': TRUE_OPERATOR,
                'total_energy': checked['total_energy'], 'components': components,
                'coordinates': None if coordinates is None else np.asarray(coordinates).copy()})
            snapshots[snapshot_id] = snapshot
            checked['snapshot_id'] = snapshot_id
            row.update(status='VALIDATED', operator_source=TRUE_OPERATOR, operator_id=matched_id,
                       snapshot_id=snapshot_id, total_energy_hartree=checked['total_energy'])
            last_validated = snapshot
            last_call.update(status='VALIDATED', matched_snapshot_id=snapshot_id)
            return checked
        except ReferenceRefusal as error:
            row.update(status='REFUSED', reason=error.reason, detail=error.detail)
            last_call.update(status='REFUSED', reason=error.reason)
            raise
        except Exception as error:
            row.update(status='REFUSED', reason='EVALUATOR_REFUSED', detail=type(error).__name__+': '+str(error))
            last_call.update(status='REFUSED', reason='EVALUATOR_REFUSED')
            raise ReferenceRefusal('EVALUATOR_REFUSED', row['detail']) from error
        finally:
            row['callback_failed'] = not row['callback_completed']
            row['elapsed_seconds'] = time.monotonic()-started

    def assess(dm, value):
        return original.qualify(dm, value['fock'], s, electrons, value['total_energy'],
                                [value[key] for key in COMPONENTS], mask)

    def residual(coefficients, value):
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            transformed = x.T@value['fock']@x
            r = (coefficients[:, occupied:].T@transformed@coefficients[:, :occupied]).ravel()
        if not np.isfinite(r).all():
            raise ReferenceRefusal('NONFINITE_RESIDUAL', 'Whitened independent residual is nonfinite')
        return r

    def role(snapshot, norm, name):
        return _freeze({'role': name, 'snapshot_id': snapshot['snapshot_id'],
                        'density_id': snapshot['density_id'], 'operator_id': snapshot['operator_id'],
                        'evaluation_count': snapshot['evaluation_count'], 'residual_norm': norm,
                        'density': snapshot['density'], 'fock': snapshot['fock'],
                        'total_energy': snapshot['total_energy'], 'components': snapshot['components']})

    def track_sample(value, norm, is_base):
        nonlocal optimizer_base, best_base, best_any
        snapshot = snapshots[value['snapshot_id']]
        if is_base:
            optimizer_base = role(snapshot, norm, 'COMPLETE_OPTIMIZER_BASE')
            if best_base is None or norm < best_base['residual_norm']:
                best_base = role(snapshot, norm, 'BEST_COMPLETE_OPTIMIZER_BASE_DIAGNOSTIC')
        else:
            fd_samples.append(role(snapshot, norm, 'FINITE_DIFFERENCE_SAMPLE'))
        if best_any is None or norm < best_any['residual_norm']:
            best_any = role(snapshot, norm, 'BEST_EVALUATED_SAMPLE_DIAGNOSTIC_NEVER_REPLACES_RETURNED_DENSITY')

    try:
        if initialization_policy == 'FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0':
            initial = frozen_call(d0, 'INITIALIZE_AT_ORDINARY_D0')
            spectrum, orbitals = eigh(initial['fock'], s, check_finite=True)
            gap = float(spectrum[occupied]-spectrum[occupied-1])
            initialized.update(raw_aufbau_spectrum_hartree=spectrum.tolist(), raw_aufbau_gap_hartree=gap,
                               raw_aufbau_fock_id=density_id(initial['fock']))
            if not np.isfinite(spectrum).all() or not np.isfinite(orbitals).all() or not math.isfinite(gap):
                raise ReferenceRefusal('NONFINITE_INITIALIZATION', 'Initial raw generalized eigensystem is not finite')
            if gap < 1e-6:
                initialized.update(status='REFUSED', reason='ROOT_AMBIGUOUS_INITIALIZATION')
                raise ReferenceRefusal('ROOT_AMBIGUOUS_INITIALIZATION', 'Unchanged initial gap admission failed')
            d = 2*orbitals[:, :occupied]@orbitals[:, :occupied].T
            d = (d+d.T)/2
            initial_frame = frame(d)
        u = initial_frame
        initialized.update(status='PREPARED_ENGINEERING_INITIALIZATION', initial_density_id=density_id(d))
        current = frozen_call(d, 'CURRENT_INITIAL')
        for chart in range(maximum_iterations):
            current_gate, _ = assess(d, current)
            r0 = residual(u, current)
            norm0 = float(np.linalg.norm(r0))
            if current_gate['qualified']:
                reason = 'QUALIFIED_CURRENT_CANDIDATE'
                break
            if norm0 <= 1e-12:
                reason = 'STATIONARY_ENDPOINT_FAILED_ORIGINAL_GATES'
                break
            origin, cache = u.copy(), {}

            def sample(z, phase, detail=None):
                generator = np.zeros((n, n))
                block = np.asarray(z).reshape(n-occupied, occupied)
                generator[occupied:, :occupied], generator[:occupied, occupied:] = block, -block.T
                with np.errstate(over='raise', invalid='raise', divide='raise'):
                    trial_frame = origin@expm(generator)
                    trial = 2*x@trial_frame[:, :occupied]@trial_frame[:, :occupied].T@x.T
                trial = (trial+trial.T)/2
                value = frozen_call(trial, phase, z, reserve=TAIL_SLOTS, detail=detail)
                r = residual(trial_frame, value)
                norm = float(np.linalg.norm(r))
                track_sample(value, norm, phase == 'OPTIMIZER_BASE')
                return trial_frame, trial, value, r

            def objective(z):
                item = sample(z, 'OPTIMIZER_BASE')
                cache[tuple(z)] = item
                return item[3]

            def jacobian(z):
                nonlocal last_complete_jacobian_base
                key = tuple(z)
                if key not in cache:
                    raise ReferenceRefusal('JACOBIAN_BASE_SNAPSHOT_MISSING', 'No completed objective exists at this exact base; no uncharged replacement F is allowed')
                base_snapshot = snapshots[cache[key][2]['snapshot_id']]
                group = admission('COMPLETE_JACOBIAN', 2*k, context={
                    'chart': chart+1, 'base_snapshot_id': base_snapshot['snapshot_id'],
                    'base_density_id': base_snapshot['density_id'],
                    'base_operator_id': base_snapshot['operator_id'],
                    'derivative_policy': DERIVATIVE_POLICY,
                    'coordinate_count': k, 'variable_count': k, 'planned_callbacks': 2*k,
                    'scipy_version': scipy_version, 'method': '3-point', 'workers': 1,
                    'uses_completed_base_f0': True, 'uses_sparsity': False,
                    'relative_step': finite_difference_step,
                    'lower_bound': -trust_radius, 'upper_bound': trust_radius})
                before = len(ledger)
                group['status'] = 'STARTED'
                try:
                    def fd_objective(point):
                        return sample(point, 'FD_SAMPLE', {'jacobian_group': len(admissions),
                                      'chart': chart+1, 'fd_sample': len(ledger)-before+1})[3]
                    # Reuse the pinned mature numerical-derivative helper.  f0
                    # is the already charged completed objective; workers=1
                    # and a dense Jacobian make the exact group cost 2*k.
                    jac = np.asarray(approx_derivative(fd_objective, np.asarray(z),
                        method='3-point', rel_step=finite_difference_step,
                        f0=cache[key][3].copy(), bounds=(-trust_radius, trust_radius),
                        sparsity=None, workers=1), dtype=float).reshape(k, k)
                    if len(ledger)-before != 2*k:
                        raise ReferenceRefusal('JACOBIAN_CALL_COST_MISMATCH', 'Pinned dense three-point group did not consume exactly 2*nvar callbacks')
                    if not np.isfinite(jac).all():
                        raise ReferenceRefusal('NONFINITE_JACOBIAN', 'Independent numerical Jacobian is not finite')
                    last_complete_jacobian_base = role(snapshots[cache[key][2]['snapshot_id']],
                        float(np.linalg.norm(cache[key][3])), 'LAST_COMPLETE_JACOBIAN_BASE')
                    group['status'] = 'COMPLETED'
                    return jac
                except Exception as error:
                    group.update(status='REFUSED_PARTIAL_NO_RETRY', failure_type=type(error).__name__)
                    raise
                finally:
                    group['actual_callbacks'] = len(ledger)-before
                    group['unexecuted_planned_callbacks'] = 2*k-group['actual_callbacks']

            optimized = least_squares(objective, np.zeros(k), method='trf', jac=jacobian,
                bounds=(-trust_radius*np.ones(k), trust_radius*np.ones(k)), x_scale=trust_radius,
                ftol=1e-13, xtol=1e-13, gtol=1e-13, max_nfev=8)
            scipy_summary = {'status': int(optimized.status), 'nfev': int(optimized.nfev),
                'njev': int(optimized.njev or 0), 'message': str(optimized.message),
                'accounting': 'evaluation_ledger counts all actual callbacks; callable Jacobian admission covers each complete 2*nvar group'}
            target = tuple(optimized.x)
            if target not in cache:
                # Old reference may request an uncached result; this is an
                # explicit charged objective and cannot borrow the tail slots.
                objective(optimized.x)
            next_u, next_d, next_value, next_r = cache[target]
            norm1 = float(np.linalg.norm(next_r))
            history.append({'chart': chart+1, 'before_density_id': density_id(d),
                'returned_density_id': density_id(next_d), 'before_residual_norm': norm0,
                'after_residual_norm': norm1, 'local_coordinates': optimized.x.tolist(),
                'scipy_result': scipy_summary, 'evaluation_count': len(ledger)})
            if not norm1 < norm0:
                reason = 'NO_RESIDUAL_IMPROVEMENT'
                break
            u, d, current = next_u, next_d, next_value
        tail_group = admission('FINAL_TAIL', TAIL_SLOTS, reserve=0)
        before = len(ledger)
        tail['status'] = 'ENTERED_WITH_SEPARATE_CALLBACKS'
        try:
            final = frozen_call(d, 'FINAL_RETURNED_DENSITY')
            gate, mapped = assess(d, final)
            gate['returned_density_energy_recheck_hartree'] = abs(final['total_energy']-current['total_energy'])
            if gate['qualified'] and gate['returned_density_energy_recheck_hartree'] <= 1e-9:
                rechecked = frozen_call(mapped, 'FINAL_RAW_AUFBAU_DENSITY_RECHECK')
                mapped_gate, _ = assess(mapped, rechecked)
                gate['mapped_density_energy_change_hartree'] = abs(rechecked['total_energy']-final['total_energy'])
                qualified = bool(mapped_gate['qualified'] and gate['mapped_density_energy_change_hartree'] <= 1e-9)
                reason = 'QUALIFIED_TRUE_ARRAY_ENDPOINT' if qualified else 'FINAL_RAW_AUFBAU_RECHECK_FAILED'
            elif gate['qualified']:
                reason = 'FINAL_RETURNED_DENSITY_ENERGY_RECHECK_FAILED'
            elif reason == 'QUALIFIED_CURRENT_CANDIDATE':
                reason = 'FINAL_ENDPOINT_FAILED_ORIGINAL_GATES'
            tail['status'] = 'COMPLETED_ORIGINAL_GATES'
            tail_group['status'] = 'COMPLETED'
        except Exception:
            tail['status'] = 'FAILED_NO_RETRY'
            tail_group['status'] = 'FAILED_NO_RETRY'
            raise
        finally:
            tail['actual_callbacks'] = tail_group['actual_callbacks'] = len(ledger)-before
    except ReferenceRefusal as error:
        reason, failure = error.reason, {'reason': error.reason, 'detail': error.detail}
    except (ValueError, np.linalg.LinAlgError, FloatingPointError, OverflowError) as error:
        reason, failure = 'NUMERICAL_REFUSAL', {'exception_type': type(error).__name__, 'detail': str(error)}

    returned_id = density_id(d)
    matched = [snapshot for snapshot in snapshots.values() if snapshot['density_id'] == returned_id]
    returned = _freeze({'role': 'LAST_COMPLETE_ACCEPTED_CHART_DENSITY_NEVER_BEST_SUBSTITUTION',
        'density': d, 'density_id': returned_id,
        'matched_snapshot_id': matched[-1]['snapshot_id'] if matched else None,
        'matched_operator_id': matched[-1]['operator_id'] if matched else None,
        'final_gate_evaluated': gate is not None})
    return {'reference_id': REFERENCE_ID, 'status': 'ENGINEERING_ONLY',
        'engine_qualified': qualified, 'converged': qualified, 'density': d.copy(),
        'stop_reason': reason, 'failure': failure, 'endpoint_gate': gate,
        'mapped_endpoint_gate': mapped_gate, 'initialization': initialized,
        'history': history, 'scipy_result': scipy_summary,
        'best_sample': best_any, 'best_base': best_base, 'best_any_sample': best_any,
        'optimizer_base': optimizer_base, 'last_complete_jacobian_base': last_complete_jacobian_base,
        'fd_samples': tuple(fd_samples),
        'returned_density': returned, 'last_call': _freeze(last_call),
        'last_validated_snapshot': last_validated,
        'snapshot_registry': FrozenRecord(snapshots),
        'budget_admissions': tuple(_freeze(item) for item in admissions),
        'tail_execution': _freeze(tail),
        'evaluation_ledger': tuple(_freeze(row) for row in ledger),
        'evaluation_count': len(ledger), 'evaluation_limit': maximum_evaluations,
        'accounting': {'precharged_callbacks': len(ledger),
            'callback_entered': sum(row['callback_entered'] for row in ledger),
            'callback_completed': sum(row['callback_completed'] for row in ledger),
            'callback_failed': sum(row['callback_failed'] for row in ledger),
            'validated_callbacks': sum(row['status'] == 'VALIDATED' for row in ledger),
            'remaining_unused_callbacks': maximum_evaluations-len(ledger),
            'refunds': 0, 'automatic_retries': 0, 'closed': True,
            'native_molecular_callbacks': 'NOT_EXECUTED_ENGINEERING_SCOPE'},
        'parameters': {'maximum_charts': maximum_iterations,
            'local_component_bound': trust_radius,
            'finite_difference_relative_step': finite_difference_step,
            'derivative_policy': DERIVATIVE_POLICY, 'scipy_private_api_version': scipy_version,
            'tail_callbacks_reserved': TAIL_SLOTS, 'thresholds': dict(THRESHOLDS)},
        'production_activation': False, 'compute_enabled': False,
        'research_acceptance': 'NOT_ACCEPTED', 'molecular_acceptance': 'NOT_EXECUTED',
        'comparison_available': False, 'deltas': None, 'delta_hartree': None,
        'delta_kcal_mol': None, 'variational_status': 'NOT_ESTABLISHED',
        'comparison_status': {'UM-P12': 'NOT_ACCEPTED', 'UM-P13': 'NOT_ACCEPTED', 'T06': 'NOT_ACCEPTED'},
        'shared_dependencies': ['NUMPY', 'SCIPY'],
        'method_review_status': 'CANCELLED_INTERNAL_PENDING'}
