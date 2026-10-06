"""Independent TRF residual reference; shared SciPy, no production helpers.

Local orbital charts are reanchored after each bounded least-squares solve.
The merit function is the true-F occupied--virtual residual, not the energy.
Every numerical-Jacobian callback is counted independently of SciPy's nfev.
"""
from __future__ import annotations

import hashlib
import math
from numbers import Real
import struct
import time

import numpy as np
from scipy.linalg import eigh, expm
from scipy.optimize import least_squares


REFERENCE_ID = 'INDEPENDENT_ORBITAL_TRF_RESIDUAL_REFERENCE_V1'
TRUE_OPERATOR = 'TRUE_CONDITIONAL_AT_REQUESTED_DENSITY'
THRESHOLDS = {'commutator_frobenius': 1e-5, 'electron_count_abs': 1e-7,
    'idempotency_relative': 1e-7, 'energy_closure_hartree': 1e-9,
    'mask_max_abs': 1e-12, 'mapped_density_relative': 2e-8,
    'mapped_density_absolute': 2e-8, 'final_non_diis_gap_minimum_hartree': 1e-6}
COMPONENTS = ('one_electron_energy', 'coulomb_energy', 'exact_exchange_energy',
              'semilocal_xc_energy', 'nuclear_repulsion')
POLICIES = {'REQUIRE_EXISTING_MASKED_PROJECTOR', 'FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0'}


class ReferenceRefusal(ValueError):
    def __init__(self, reason, detail):
        self.reason, self.detail = reason, detail
        super().__init__(detail)


def real_array(value, name='Array'):
    array = np.asarray(value)
    if array.dtype.kind not in 'iuf' or not array.size or not np.isfinite(array).all():
        raise ValueError(name+' must be a finite real nonboolean array')
    return np.asarray(array, dtype=np.float64)


def real_scalar(value, name='Scalar'):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(name+' must be finite, real and nonboolean')
    return float(value)


def density_id(density):
    array = real_array(density, 'Density')
    if array.ndim != 2 or array.shape[0] != array.shape[1]:
        raise ValueError('Density must be a square matrix')
    encoded = np.ascontiguousarray(array, dtype='<f8')
    payload = b'AI4OrgChem-density-v1\0'+struct.pack('<QQ', *encoded.shape)+encoded.tobytes(order='C')
    return hashlib.sha256(payload).hexdigest()


def qualify(density, fock, metric, electrons, energy, components, mask):
    """Independent true-operator acceptance arithmetic, not method approval."""
    spectrum, orbitals = eigh(fock, metric, check_finite=True)
    occupied = electrons//2
    mapped = 2*orbitals[:, :occupied]@orbitals[:, :occupied].T
    mapped = (mapped+mapped.T)/2
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        metrics = {
            'final_commutator_frobenius_norm': float(np.linalg.norm(fock@density@metric-metric@density@fock)),
            'masked_metric_electron_count': float(np.sum(metric*density.T)),
            'closed_shell_idempotency_relative_residual': float(np.linalg.norm(density@metric@density-2*density)/max(np.linalg.norm(density),1.)),
            'energy_component_closure_residual_hartree': abs(sum(components)-energy),
            'mapped_density_relative_residual': float(np.linalg.norm(mapped-density)/max(np.linalg.norm(mapped),1.)),
            'raw_map_absolute_frobenius': float(np.linalg.norm(mapped-density)),
            'final_non_diis_gap_hartree': float(spectrum[occupied]-spectrum[occupied-1]),
            'overlap_mask_max_abs': float(np.max(np.abs(metric[mask]),initial=0)),
            'fock_mask_max_abs': float(np.max(np.abs(fock[mask]),initial=0)),
        }
    if not np.isfinite(list(metrics.values())).all() or not np.isfinite(mapped).all():
        raise ReferenceRefusal('NONFINITE_ENDPOINT', 'Independent endpoint diagnostics are not finite')
    checks = {
        'commutator': metrics['final_commutator_frobenius_norm'] <= 1e-5,
        'electron_count': abs(metrics['masked_metric_electron_count']-electrons) <= 1e-7,
        'idempotency': metrics['closed_shell_idempotency_relative_residual'] <= 1e-7,
        'energy_closure': metrics['energy_component_closure_residual_hartree'] <= 1e-9,
        'mapped_density': metrics['mapped_density_relative_residual'] <= 2e-8,
        'absolute_raw_map': metrics['raw_map_absolute_frobenius'] <= 2e-8,
        'raw_gap': metrics['final_non_diis_gap_hartree'] >= 1e-6,
        'overlap_mask': metrics['overlap_mask_max_abs'] <= 1e-12,
        'fock_mask': metrics['fock_mask_max_abs'] <= 1e-12,
    }
    return dict(metrics, checks=checks, qualified=all(checks.values()),
                reasons=[name.upper()+'_FAILED' for name, valid in checks.items() if not valid]), mapped


def solve(*, density, overlap, electrons, evaluate,
          initialization_policy,
          maximum_evaluations=201, maximum_iterations=8,
          finite_difference_step=1e-5, trust_radius=.25, matrix_delete_mask=None):
    """Bounded independent reference; invalid initial/configuration raises.

    Algorithmic failures return a truthful rejection and retain the candidate
    density. The reference shares linear algebra with the tested implementation
    but independently implements iteration, initialization, gates and accounting.
    """
    if initialization_policy not in POLICIES or not callable(evaluate):
        raise ValueError('Explicit supported initialization policy and evaluator required')
    for name, value, ceiling in (('maximum_evaluations',maximum_evaluations,201),
                                 ('maximum_iterations',maximum_iterations,100)):
        if type(value) is not int or not 1 <= value <= ceiling:
            raise ValueError(name+' must be a bounded integer')
    finite_difference_step = real_scalar(finite_difference_step, 'Finite difference step')
    trust_radius = real_scalar(trust_radius, 'TRF local chart radius')
    if not 0 < finite_difference_step <= trust_radius <= 1:
        raise ValueError('Require 0 < finite_difference_step <= trust_radius <= 1')
    d0, s = real_array(density,'Initial density').copy(), real_array(overlap,'Masked overlap').copy()
    if (d0.ndim != 2 or d0.shape[0] != d0.shape[1] or s.shape != d0.shape or
            any(not np.allclose(a,a.T,rtol=0,atol=1e-12) for a in (d0,s))):
        raise ValueError('Same-size symmetric density and overlap matrices required')
    n = len(d0)
    if type(electrons) is not int or electrons < 2 or electrons%2 or electrons >= 2*n:
        raise ValueError('Global integer closed-shell occupation and a virtual orbital required')
    occupied, k = electrons//2, (electrons//2)*(n-electrons//2)
    if k > 64:
        raise ValueError('Reference is limited to 64 occupied--virtual variables')
    sw, sv = np.linalg.eigh(s)
    if sw.min() <= 0:
        raise ValueError('Masked overlap must be positive definite; no repair allowed')
    try:
        with np.errstate(over='raise',invalid='raise',divide='raise'):
            x, half = (sv/np.sqrt(sw))@sv.T, (sv*np.sqrt(sw))@sv.T
    except FloatingPointError as error:
        raise ValueError('Metric whitening overflowed') from error
    if not all(np.isfinite(value).all() for value in (x,half)):
        raise ValueError('Metric whitening must be finite')
    mask = np.zeros(d0.shape,dtype=bool) if matrix_delete_mask is None else np.asarray(matrix_delete_mask).copy()
    if mask.dtype.kind != 'b' or mask.shape != d0.shape or not np.array_equal(mask,mask.T):
        raise ValueError('Symmetric same-size boolean mask required')

    def frame(dm):
        with np.errstate(over='raise',invalid='raise',divide='raise'):
            p = .5*half@dm@half
            defect = float(np.linalg.norm(p@p-p))
            count = float(np.trace(p))
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
    ledger, operators, history = [], {}, []
    reason, failure, qualified, gate, mapped_gate = 'MAXIMUM_CHARTS_EXHAUSTED',None,False,None,None
    initialized = {'policy':initialization_policy,'ordinary_density_id':density_id(d0),'status':'NOT_EXECUTED'}
    current = None
    scipy_summary = None
    best_sample = None

    def call(dm, phase, coordinates=None, reserve=0):
        if len(ledger) >= maximum_evaluations-reserve:
            raise ReferenceRefusal('EVALUATION_BUDGET_EXHAUSTED','Every actual callback, including SciPy finite differences, consumes the hard budget')
        argument = dm.copy(); identity = density_id(argument)
        row = {'evaluation_count':len(ledger)+1,'phase':phase,'density_id':identity,'status':'STARTED'}
        if coordinates is not None:
            row['local_rotation_coordinates'] = np.asarray(coordinates).tolist()
        ledger.append(row); started = time.monotonic()
        try:
            value = evaluate(argument)
            if density_id(argument) != identity:
                raise ReferenceRefusal('REQUESTED_DENSITY_MODIFIED','Evaluator modified its requested density')
            if (not isinstance(value,dict) or value.get('density_id') != identity or
                    value.get('operator_source') != TRUE_OPERATOR):
                raise ReferenceRefusal('EVALUATOR_IDENTITY_MISMATCH','Evaluator must bind true F to the exact requested density')
            fock = real_array(value.get('fock'),'True F').copy()
            if fock.shape != dm.shape or not np.allclose(fock,fock.T,rtol=0,atol=1e-12):
                raise ValueError('True F dimensions or symmetry differ')
            checked = {'fock':fock,'density_id':identity,'operator_source':TRUE_OPERATOR}
            for key in ('total_energy',*COMPONENTS):
                checked[key] = real_scalar(value.get(key),key)
            fock_id = density_id(fock); prior = operators.get(identity)
            row.update(fock_id=fock_id,previous_same_density_fock_id=prior,
                       same_density_operator_reproducible=None if prior is None else fock_id == prior)
            if prior is not None and fock_id != prior:
                raise ReferenceRefusal('NONREPRODUCIBLE_SAME_DENSITY_OPERATOR','Same density returned different true-F bytes')
            operators[identity] = fock_id
            row.update(status='VALIDATED',operator_source=TRUE_OPERATOR,total_energy_hartree=checked['total_energy'])
            return checked
        except ReferenceRefusal as error:
            row.update(status='REFUSED',reason=error.reason,detail=error.detail); raise
        except Exception as error:
            row.update(status='REFUSED',reason='EVALUATOR_REFUSED',detail=type(error).__name__+': '+str(error))
            raise ReferenceRefusal('EVALUATOR_REFUSED',row['detail']) from error
        finally:
            row['elapsed_seconds'] = time.monotonic()-started

    def assess(dm,value):
        return qualify(dm,value['fock'],s,electrons,value['total_energy'],
                       [value[key] for key in COMPONENTS],mask)

    def residual(coefficients,value):
        with np.errstate(over='raise',invalid='raise',divide='raise'):
            transformed = x.T@value['fock']@x
            r = (coefficients[:,occupied:].T@transformed@coefficients[:,:occupied]).ravel()
        if not np.isfinite(r).all():
            raise ReferenceRefusal('NONFINITE_RESIDUAL','Whitened independent residual is nonfinite')
        return r

    try:
        if initialization_policy == 'FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0':
            initial = call(d0,'INITIALIZE_AT_ORDINARY_D0')
            spectrum, orbitals = eigh(initial['fock'],s,check_finite=True)
            gap = float(spectrum[occupied]-spectrum[occupied-1])
            initialized.update(raw_aufbau_spectrum_hartree=spectrum.tolist(),raw_aufbau_gap_hartree=gap,
                               raw_aufbau_fock_id=density_id(initial['fock']))
            if not np.isfinite(spectrum).all() or not np.isfinite(orbitals).all() or not math.isfinite(gap):
                raise ReferenceRefusal('NONFINITE_INITIALIZATION','Initial raw generalized eigensystem is not finite')
            if gap < 1e-6:
                initialized.update(status='REFUSED',reason='ROOT_AMBIGUOUS_INITIALIZATION')
                raise ReferenceRefusal('ROOT_AMBIGUOUS_INITIALIZATION','Unchanged initial gap admission failed')
            d = 2*orbitals[:,:occupied]@orbitals[:,:occupied].T; d = (d+d.T)/2
            initial_frame = frame(d)
        u = initial_frame
        initialized.update(status='PREPARED_ENGINEERING_INITIALIZATION',initial_density_id=density_id(d))
        current = call(d,'CURRENT_INITIAL')
        for chart in range(maximum_iterations):
            current_gate, _ = assess(d,current)
            r0 = residual(u,current); norm0 = float(np.linalg.norm(r0))
            if current_gate['qualified']:
                reason = 'QUALIFIED_CURRENT_CANDIDATE'; break
            if norm0 <= 1e-12:
                reason = 'STATIONARY_ENDPOINT_FAILED_ORIGINAL_GATES'; break
            origin = u.copy(); cache = {}
            def objective(z):
                nonlocal best_sample
                generator = np.zeros((n,n)); block = z.reshape(n-occupied,occupied)
                generator[occupied:,:occupied], generator[:occupied,occupied:] = block,-block.T
                with np.errstate(over='raise',invalid='raise',divide='raise'):
                    trial_frame = origin@expm(generator)
                    trial = 2*x@trial_frame[:,:occupied]@trial_frame[:,:occupied].T@x.T
                trial = (trial+trial.T)/2
                value = call(trial,'SCIPY_TRF_RESIDUAL',z,reserve=2)
                r = residual(trial_frame,value)
                cache[tuple(z)] = (trial_frame,trial,value,r)
                norm = float(np.linalg.norm(r))
                if best_sample is None or norm < best_sample['residual_norm']:
                    best_sample = {'density':trial.copy(),'density_id':density_id(trial),
                        'residual_norm':norm,'evaluation_count':len(ledger),
                        'role':'EVALUATED_SAMPLE_DIAGNOSTIC_NEVER_A_REPLACEMENT_RETURNED_DENSITY'}
                return r
            optimized = least_squares(objective,np.zeros(k),method='trf',jac='3-point',
                bounds=(-trust_radius*np.ones(k),trust_radius*np.ones(k)),x_scale=trust_radius,
                diff_step=finite_difference_step,ftol=1e-13,xtol=1e-13,gtol=1e-13,max_nfev=8)
            scipy_summary = {'status':int(optimized.status),'nfev':int(optimized.nfev),
                'njev':int(optimized.njev or 0),'message':str(optimized.message),
                'accounting':'SciPy nfev excludes some numerical Jacobian calls; evaluation_ledger is authoritative'}
            target = tuple(optimized.x)
            if target not in cache:
                objective(optimized.x)
            next_u,next_d,next_value,next_r = cache[target]
            norm1 = float(np.linalg.norm(next_r))
            history.append({'chart':chart+1,'before_density_id':density_id(d),
                'returned_density_id':density_id(next_d),'before_residual_norm':norm0,
                'after_residual_norm':norm1,'local_coordinates':optimized.x.tolist(),
                'scipy_result':scipy_summary,'evaluation_count':len(ledger)})
            if not norm1 < norm0:
                reason = 'NO_RESIDUAL_IMPROVEMENT'; break
            u,d,current = next_u,next_d,next_value
        final = call(d,'FINAL_RETURNED_DENSITY')
        gate,mapped = assess(d,final)
        gate['returned_density_energy_recheck_hartree'] = abs(final['total_energy']-current['total_energy'])
        if gate['qualified'] and gate['returned_density_energy_recheck_hartree'] <= 1e-9:
            rechecked = call(mapped,'FINAL_RAW_AUFBAU_DENSITY_RECHECK')
            mapped_gate,_ = assess(mapped,rechecked)
            gate['mapped_density_energy_change_hartree'] = abs(rechecked['total_energy']-final['total_energy'])
            qualified = bool(mapped_gate['qualified'] and gate['mapped_density_energy_change_hartree'] <= 1e-9)
            reason = 'QUALIFIED_TRUE_ARRAY_ENDPOINT' if qualified else 'FINAL_RAW_AUFBAU_RECHECK_FAILED'
        elif gate['qualified']:
            reason = 'FINAL_RETURNED_DENSITY_ENERGY_RECHECK_FAILED'
        elif reason == 'QUALIFIED_CURRENT_CANDIDATE':
            reason = 'FINAL_ENDPOINT_FAILED_ORIGINAL_GATES'
    except ReferenceRefusal as error:
        reason,failure = error.reason,{'reason':error.reason,'detail':error.detail}
    except (ValueError,np.linalg.LinAlgError,FloatingPointError,OverflowError) as error:
        reason,failure = 'NUMERICAL_REFUSAL',{'exception_type':type(error).__name__,'detail':str(error)}
    return {'reference_id':REFERENCE_ID,'status':'INDEPENDENT_ENGINEERING_REFERENCE',
        'engine_qualified':qualified,'converged':qualified,'density':d,'stop_reason':reason,
        'failure':failure,'endpoint_gate':gate,'mapped_endpoint_gate':mapped_gate,
        'initialization':initialized,'history':history,'scipy_result':scipy_summary,'best_sample':best_sample,
        'evaluation_ledger':ledger,'evaluation_count':len(ledger),'evaluation_limit':maximum_evaluations,
        'parameters':{'maximum_charts':maximum_iterations,'local_component_bound':trust_radius,
            'finite_difference_relative_step':finite_difference_step,'thresholds':dict(THRESHOLDS)},
        'production_activation':False,'research_acceptance':'NOT_ACCEPTED',
        'molecular_acceptance':'NOT_EXECUTED','comparison_available':False,'deltas':None,
        'delta_hartree':None,'delta_kcal_mol':None,'variational_status':'NOT_ESTABLISHED',
        'shared_dependencies':['NUMPY','SCIPY'],'method_review_status':'PENDING_REAL_REVIEW'}
