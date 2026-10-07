# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Xiao Chen.
"""Bounded single-start root candidate with typed native-adapter admission V1.

Derived from reference/occupied_space_root_candidate.py under the repository
Apache-2.0 license/NOTICE. Equations, masked metric, residual merit, chart
geometry, pinned three-point derivatives and original endpoint gates remain.
This version explicitly changes chart scheduling to one chart/two objectives.
It does not relabel old engineering records or implement callback-return state.
The old fake-only candidate is unchanged. This separate entry accepts only a
fixed synthetic evaluator, or the separately validated source-bound evaluator.
Source execution still requires a distinct explicit grant and real outer guards.
"""
from __future__ import annotations

import hashlib
import json
import math
import struct
import time

import numpy as np
from scipy import __version__ as scipy_version
from scipy.linalg import eigh, expm
from scipy.optimize import least_squares
from scipy.optimize._numdiff import approx_derivative

from . import residual_candidate as original


REFERENCE_ID = 'TYPED_SINGLE_START_OCCUPIED_SPACE_ROOT_NATIVE_CANDIDATE_V1'
TRUE_OPERATOR = original.TRUE_OPERATOR
THRESHOLDS = dict(original.THRESHOLDS)
COMPONENTS = original.COMPONENTS
POLICIES = frozenset(('REQUIRE_EXISTING_MASKED_PROJECTOR',))
ReferenceRefusal = original.ReferenceRefusal
real_array = original.real_array
real_scalar = original.real_scalar
density_id = original.density_id
TAIL_SLOTS = 2
DERIVATIVE_POLICY = 'PINNED_SCIPY_PRIVATE_APPROX_DERIVATIVE_THREE_POINT_V1'
REQUIRED_SCIPY_VERSION = '1.18.0'
SOURCE_EXECUTION_KIND = 'SOURCE_NATIVE_DIAGNOSTIC'
ENGINEERING_EXECUTION_KIND = 'ENGINEERING_SIMULATED_NATIVE'
EXECUTION_KINDS = frozenset((ENGINEERING_EXECUTION_KIND, SOURCE_EXECUTION_KIND))
SOURCE_INTERFACE_IMPLEMENTED = True
SOURCE_EXECUTION_AUTHORIZED_BY_THIS_MODULE = False
SELECTED_INITIAL_DENSITY_ID = '6b0d501aba96ac5c53ca633491e105d7c5dab13836350bd6d7350437f91bd7c0'
ENGINEERING_SIMULATED_CALLBACK_COUNTS = {'entered': 0, 'completed': 0, 'failed': 0}
COUNTS = ('masked_metric_electron_count', 'physical_metric_electron_count', 'grid_electron_count')
OPTIONAL_MATRICES = ('J', 'K', 'Vxc', 'V', 'coulomb_matrix', 'exchange_matrix',
                    'semilocal_potential', 'xc_potential')


def _source_fingerprint(value):
    array = np.asarray(value)
    return (array.shape, array.dtype.str, hashlib.sha256(array.tobytes(order='C')).hexdigest())


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


class SyntheticRootEvaluator:
    """Closed pure-array fixture factory, never a wrapper for user callbacks.

    The supported scenarios and faults are fixed code. There is no callable,
    molecule, prepared engine, native handle or source program constructor.
    Engineering tests still run under the outer fourteen native API guards.
    """
    SCENARIOS = frozenset(('diagonal', 'noncommuting', 'degenerate', 'density_response'))
    FAULTS = frozenset((None, 'wrong_density_id', 'wrong_operator_source', 'projection_mismatch', 'missing_raw', 'missing_grid_count',
        'nonsymmetric_raw', 'electronic_closure', 'masked_count', 'component_repeat',
        'grid_count_repeat', 'deleted_raw_repeat', 'callback_failure', 'mutate_density',
        'nonfinite_component', 'returned_energy_shift', 'mapped_energy_shift', 'mapped_density_bad_operator'))

    def __init__(self, scenario='diagonal', *, fault=None, fault_at=2, expected_initial_density_id=None, accounting=None):
        if scenario not in self.SCENARIOS or fault not in self.FAULTS:
            raise ValueError('A registered pure-array scenario/fault is required')
        if type(fault_at) is not int or fault_at < 1 or fault_at > 201:
            raise ValueError('A fixed positive fault callback index is required')
        if expected_initial_density_id is not None and (not isinstance(expected_initial_density_id, str)
                or len(expected_initial_density_id) != 64):
            raise ValueError('Explicit synthetic initial density identity is invalid')
        if accounting is not None:
            from runtime.user_molecule.root_native_accounting import RootNativeAccounting
            if type(accounting) is not RootNativeAccounting or accounting.kind != ENGINEERING_EXECUTION_KIND or accounting.authorized is not False:
                raise ValueError('Only exact engineering/False RootNativeAccounting may accompany a synthetic fixture')
        self._accounting = accounting
        self.scenario, self.fault, self.fault_at = scenario, fault, fault_at
        self.initial_density_id = expected_initial_density_id
        self._pending = None
        self._rows = []
        self._counts = {'entered': 0, 'completed': 0, 'failed': 0}
        self._first_calls = {}
        self._settings = (scenario, fault, fault_at, expected_initial_density_id, accounting)

    def bind_candidate_callback(self, context):
        if self._pending is not None:
            raise ReferenceRefusal('SYNTHETIC_CONTEXT_NOT_CONSUMED', 'No replacement of pending callback context')
        if (not isinstance(context, FrozenRecord)
                or set(context) != {'evaluation_count', 'density_id', 'phase', 'admission_group_id',
                    'chart', 'fd_sample', 'base_snapshot_id', 'base_density_id', 'base_operator_id'}
                or context['evaluation_count'] != len(self._rows)+1):
            raise ReferenceRefusal('SYNTHETIC_CONTEXT_INVALID', 'Exact immutable callback context required')
        if context['phase'] == 'FD_SAMPLE':
            if (type(context['admission_group_id']) is not int or context['admission_group_id'] < 1
                    or type(context['fd_sample']) is not int or context['fd_sample'] < 1
                    or any(context[key] is None for key in ('base_snapshot_id', 'base_density_id', 'base_operator_id'))):
                raise ReferenceRefusal('SYNTHETIC_FD_CONTEXT_MISSING', 'FD cannot infer its admission group')
        self._pending = context

    def __call__(self, density, phase):
        if self._settings != (self.scenario, self.fault, self.fault_at, self.initial_density_id, self._accounting):
            raise ReferenceRefusal('SYNTHETIC_SETTINGS_CHANGED', 'Fixture settings are fixed for one candidate')
        dm = real_array(density, 'Synthetic D')
        identity = density_id(dm)
        context, self._pending = self._pending, None
        if (context is None or context['density_id'] != identity or context['phase'] != phase
                or dm.shape != (14, 14)):
            raise ReferenceRefusal('SYNTHETIC_REQUEST_CONTEXT_MISMATCH', 'Actual D/phase differs from its context')
        if not self._rows and self.initial_density_id is not None and identity != self.initial_density_id:
            raise ReferenceRefusal('SYNTHETIC_INITIAL_ID_MISMATCH', 'Explicit initial D bytes differ')
        row = {'evaluation_count': len(self._rows)+1, 'density_id': identity, 'phase': phase,
               'context': context, 'status': 'ENTERED'}
        self._rows.append(row)
        self._counts['entered'] += 1
        try:
            index = len(self._rows)
            if self._accounting is None:
                value = self._fixed_value(dm, phase, index, identity)
            else:
                token = self._accounting.begin_callback(identity, phase, candidate_context=context)
                binding = {'slot_id': token.slot_id, 'path_id': token.path_id,
                    'density_id': token.density_id, 'phase': token.phase}
                try:
                    value = self._accounting.native_nr(token,
                        lambda: self._fixed_value(dm, phase, index, identity), context_binding=binding)
                    scalar_components = {key: real_scalar(value[key], key) for key in COMPONENTS}
                    scalar_counts = {key: real_scalar(value[key], key) for key in COUNTS}
                    actual_operator = operator_id(value['density_id'], value['fock'], value['raw_fock'],
                        real_scalar(value['total_energy']), scalar_components,
                        real_scalar(value['electronic_energy']), scalar_counts)
                    self._accounting.finish_callback(token, actual_operator, context_binding=binding)
                except BaseException as error:
                    self._accounting.fail_callback(token, error)
                    raise
            row['status'] = 'RETURNED_SYNTHETIC_WIRE'
            self._counts['completed'] += 1
            return value
        except BaseException:
            row['status'] = 'FAILED_SYNTHETIC_CALLBACK'
            self._counts['failed'] += 1
            raise

    def record_admission(self, row):
        if self._accounting is None:
            raise ReferenceRefusal('SYNTHETIC_ACCOUNTING_REQUIRED', 'No durable accounting was supplied')
        return self._accounting.record_admission(row)

    def _fixed_value(self, dm, phase, index, identity):
        if self.fault == 'callback_failure' and index == self.fault_at:
            raise ArithmeticError('Registered simulated callback failure; no native operation')
        raw = np.diag(np.arange(14, dtype=float))
        if self.scenario == 'noncommuting':
            raw[0, 8] = raw[8, 0] = 1.
        elif self.scenario == 'degenerate':
            raw[8, 8] = 7. + 5e-7
        elif self.scenario == 'density_response':
            raw[0, 8] = raw[8, 0] = float(dm[0, 8])+.2
        one = float(np.sum(raw*dm.T))
        value = {'density_id': identity, 'operator_source': TRUE_OPERATOR,
            'fock': raw.copy(), 'raw_fock': raw.copy(),
            'J': np.zeros((14, 14)), 'K': np.zeros((14, 14)), 'Vxc': np.zeros((14, 14)),
            'total_energy': one, 'electronic_energy': one,
            'one_electron_energy': one, 'coulomb_energy': 0., 'exact_exchange_energy': 0.,
            'semilocal_xc_energy': 0., 'nuclear_repulsion': 0.,
            'masked_metric_electron_count': float(np.trace(dm)),
            'physical_metric_electron_count': float(np.trace(dm))+.05,
            'grid_electron_count': float(np.trace(dm))+.06}
        repeated = identity in self._first_calls
        if index == self.fault_at:
            if self.fault == 'wrong_density_id': value['density_id'] = '0'*64
            elif self.fault == 'wrong_operator_source': value['operator_source'] = 'FALSE_MATCHING_LABEL'
            elif self.fault == 'missing_raw': del value['raw_fock']
            elif self.fault == 'missing_grid_count': del value['grid_electron_count']
            elif self.fault == 'projection_mismatch': value['fock'][0, 0] += .1
            elif self.fault == 'nonsymmetric_raw': value['raw_fock'][0, 1] = .1
            elif self.fault == 'electronic_closure': value['electronic_energy'] += .1
            elif self.fault == 'masked_count': value['masked_metric_electron_count'] += 1.
            elif self.fault == 'mutate_density': dm[0, 0] += .01
            elif self.fault == 'nonfinite_component': value['semilocal_xc_energy'] = math.nan
        if repeated and self.fault == 'component_repeat':
            value['coulomb_energy'] += .01; value['exact_exchange_energy'] -= .01
        if repeated and self.fault == 'grid_count_repeat':
            value['grid_electron_count'] += .01
        if repeated and self.fault == 'deleted_raw_repeat':
            # Used with a mask that removes this symmetric pair; F is unchanged.
            value['raw_fock'][4, 9] = value['raw_fock'][9, 4] = .01
        if self.fault == 'returned_energy_shift' and phase == 'FINAL_RETURNED_DENSITY':
            value['total_energy'] += .01; value['electronic_energy'] += .01
            value['one_electron_energy'] += .01
        if self.fault == 'mapped_energy_shift' and phase == 'FINAL_RAW_AUFBAU_DENSITY_RECHECK':
            value['total_energy'] += .01; value['electronic_energy'] += .01
            value['one_electron_energy'] += .01
        if self.fault == 'mapped_density_bad_operator' and phase == 'FINAL_RAW_AUFBAU_DENSITY_RECHECK':
            value['fock'][0, 8] = value['fock'][8, 0] = .1
            value['raw_fock'] = value['fock'].copy()
        self._first_calls.setdefault(identity, index)

        return value

    def snapshot(self):
        return _freeze({'execution_kind': ENGINEERING_EXECUTION_KIND,
            'scientific_execution_authorized': False, 'initial_density_id': self.initial_density_id,
            'binding_validated': True, 'binding_scope': 'FIXED_SYNTHETIC_FACTORY_NOT_SOURCE_AUTHENTICATION',
            'simulated_callback_counts': dict(self._counts), 'simulated_callback_records': tuple(self._rows),
            'accounting_snapshot': None if self._accounting is None else self._accounting.snapshot(),
            'native_execution_counts': None,
            'numeric_instrumentation_status': 'SIMULATED_NON_MOLECULAR_REQUIRES_OUTER_14_NATIVE_GUARDS',
            'molecular_execution': 'NOT_EXECUTED'})


def operator_id(dm_id, fock, raw_fock, energy, components, electronic_energy, counts):
    """Bind requested D, true F, actual G and the entire scalar ledger."""
    payload = (b'AI4OrgChem-occupied-space-root-native-operator-v1\0'
               + bytes.fromhex(dm_id) + bytes.fromhex(density_id(fock))
               + bytes.fromhex(density_id(raw_fock))
               + struct.pack('<10d', energy, electronic_energy,
                             *(components[key] for key in COMPONENTS),
                             *(counts[key] for key in COUNTS))
               + TRUE_OPERATOR.encode('ascii'))
    return hashlib.sha256(payload).hexdigest()

def solve_occupied_space_root_native_candidate(*, density, overlap, electrons, evaluate,
          initialization_policy='REQUIRE_EXISTING_MASKED_PROJECTOR',
          maximum_evaluations=201, maximum_charts=1, chart_max_nfev=2,
          finite_difference_step=1e-5, trust_radius=.25, matrix_delete_mask=None,
          execution_kind=ENGINEERING_EXECUTION_KIND, scientific_execution_authorized=False,
          expected_initial_density_id=None, admission_hook=None):
    """A bounded new initialization diagnostic, without new scientific rules.

    Only a normally returned, strictly improving SciPy chart updates formal D.
    Best samples, objective bases and internal accepted-but-unreturned iterations
    never replace it. Budget/Jacobian refusal has no automatic tail evaluations.
    Default one chart and two objectives fit up to two dense 96-call Jacobians
    plus separately charged eligible original tail checks under the hard201 cap.
    Source mode requires the separately authorized typed adapter; this module grants no execution permission.
    """
    if not isinstance(execution_kind, str) or execution_kind not in EXECUTION_KINDS:
        raise ValueError('Explicit supported occupied-space root execution kind required')
    if type(scientific_execution_authorized) is not bool:
        raise ValueError('Scientific execution authorization must be an exact boolean')
    if execution_kind == SOURCE_EXECUTION_KIND:
        if scientific_execution_authorized is not True:
            raise ReferenceRefusal('SOURCE_ROOT_EXPLICIT_AUTHORIZATION_REQUIRED',
                'A false/inert contract cannot enter source-native root execution')
        from runtime.user_molecule.root_native_binding import SourceBoundRootEvaluator
        if type(evaluate) is not SourceBoundRootEvaluator:
            raise ReferenceRefusal('SOURCE_ROOT_BOUND_EVALUATOR_REQUIRED',
                'Only the separately validated source-bound object is accepted')
        binding = evaluate.snapshot()
        if (binding.get('execution_kind') != SOURCE_EXECUTION_KIND
                or binding.get('scientific_execution_authorized') is not True
                or binding.get('binding_validated') is not True
                or binding.get('initial_density_id') != SELECTED_INITIAL_DENSITY_ID):
            raise ReferenceRefusal('SOURCE_ROOT_BINDING_NOT_VALIDATED', 'Source evaluator admission differs')
        fixed_hook = evaluate.record_admission
        if admission_hook is not None and (getattr(admission_hook, '__self__', None) is not evaluate
                or getattr(admission_hook, '__func__', None) is not SourceBoundRootEvaluator.record_admission):
            raise ReferenceRefusal('SOURCE_ROOT_ADMISSION_HOOK_NOT_BOUND', 'The same source object must persist all admissions')
        admission_hook = fixed_hook
        if expected_initial_density_id != SELECTED_INITIAL_DENSITY_ID:
            raise ReferenceRefusal('SOURCE_ROOT_INITIAL_ID_REQUIRED', 'The exact separately saved seed2 identity is mandatory')
    else:
        if scientific_execution_authorized is not False or type(evaluate) is not SyntheticRootEvaluator:
            raise ReferenceRefusal('SIMULATED_ROOT_FIXED_EVALUATOR_REQUIRED',
                'Only the fixed pure-array factory with explicit False is accepted; no real engine or arbitrary callable')
        if admission_hook is not None and not callable(admission_hook):
            raise ValueError('Explicit callable engineering admission hook required')
        if evaluate._accounting is not None:
            if admission_hook is None:
                admission_hook = evaluate.record_admission
            elif (getattr(admission_hook, '__self__', None) not in (evaluate, evaluate._accounting)):
                raise ValueError('Engineering persistence hook must belong to the same evaluator/accounting')

    if scipy_version != REQUIRED_SCIPY_VERSION:
        raise ValueError('Occupied-space derivative helper requires pinned SciPy '+REQUIRED_SCIPY_VERSION)
    if initialization_policy not in POLICIES or not callable(evaluate):
        raise ValueError('Explicit supported initialization policy and evaluator required')
    for name, value, expected in (('maximum_evaluations', maximum_evaluations, 201),
                                 ('maximum_charts', maximum_charts, 1),
                                 ('chart_max_nfev', chart_max_nfev, 2)):
        if type(value) is not int or value != expected:
            raise ValueError(name+' must equal the fixed single-start value '+str(expected))
    finite_difference_step = real_scalar(finite_difference_step, 'Finite difference step')
    trust_radius = real_scalar(trust_radius, 'TRF local chart radius')
    if finite_difference_step != 1e-5 or trust_radius != .25:
        raise ValueError('Fixed finite_difference_step=1e-5 and trust_radius=.25 required')
    d0 = real_array(density, 'Initial density').copy()
    s = real_array(overlap, 'Masked overlap').copy()
    if (d0.ndim != 2 or d0.shape[0] != d0.shape[1] or s.shape != d0.shape
            or any(not np.allclose(a, a.T, rtol=0, atol=1e-12) for a in (d0, s))):
        raise ValueError('Same-size symmetric density and overlap matrices required')
    initial_id = density_id(d0)
    if expected_initial_density_id is not None and (not isinstance(expected_initial_density_id, str) or expected_initial_density_id != initial_id):
        raise ValueError('Explicit initial density identity differs; no V2 or raw-Aufbau replacement is permitted')
    n = len(d0)
    if type(electrons) is not int or electrons < 2 or electrons % 2 or electrons >= 2*n:
        raise ValueError('Global integer closed-shell occupation and a virtual orbital required')
    occupied, k = electrons//2, (electrons//2)*(n-electrons//2)
    if n != 14 or electrons != 16 or occupied != 8 or k != 48:
        raise ValueError('This single-start candidate is fixed to14AO/16electrons/48variables')
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

    source_callers = {'density': density, 'overlap': overlap}
    if matrix_delete_mask is not None:
        source_callers['matrix_delete_mask'] = matrix_delete_mask
    source_fingerprints = {name: _source_fingerprint(value) for name, value in source_callers.items()}

    def assert_sources_frozen():
        if any(_source_fingerprint(value) != source_fingerprints[name] for name, value in source_callers.items()):
            raise ReferenceRefusal('CALLER_SOURCE_ARRAY_MUTATED', 'Caller-owned initial D/S/mask bytes changed; no repair or retry')

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
    initialized = {'policy': initialization_policy, 'explicit_initial_density_id': initial_id,
        'ordinary_density_id': None, 'ordinary_density_is_this_initialization': False,
        'v2_seed_operation': 'NOT_EXECUTED', 'initial_density_projected_or_replaced': False,
        'status': 'NOT_EXECUTED'}
    current, scipy_summary = None, None
    optimizer_base = best_base = best_any = last_call = last_validated = None
    last_complete_jacobian_base = None
    tail = {'reserved_callbacks': TAIL_SLOTS, 'status': 'NOT_EXECUTED',
            'automatic_after_budget_refusal': False, 'actual_callbacks': 0}

    def emit_admission(row):
        if admission_hook is None:
            return
        captured = _freeze(row)
        before = hashlib.sha256(json.dumps(captured, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        try:
            admission_hook(captured)
        except BaseException as error:
            raise ReferenceRefusal('ADMISSION_HOOK_REFUSED', type(error).__name__+': '+str(error)) from error
        after = hashlib.sha256(json.dumps(captured, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        if after != before:
            raise ReferenceRefusal('ADMISSION_HOOK_MUTATED_ROW', 'Admission persistence cannot modify its immutable event')

    def admission(kind, cost, reserve=TAIL_SLOTS, context=None):
        remaining = maximum_evaluations-len(ledger)
        row = {'group_id': len(admissions)+1, 'kind': kind, 'chart': 1, 'planned_callbacks': cost,
               'coordinate_count': 48, 'unexecuted_planned_callbacks': cost,
               'call_count_before': len(ledger), 'required_callbacks': cost,
               'tail_callbacks_reserved': reserve, 'remaining_callbacks': remaining,
               'admitted': remaining >= cost+reserve, 'actual_callbacks': 0,
               'status': 'ADMITTED' if remaining >= cost+reserve else 'REFUSED_ZERO_CALLBACKS'}
        row.update(context or {})
        admissions.append(row)
        emit_admission(row)
        if not row['admitted']:
            refusal = 'JACOBIAN_BUDGET_ADMISSION_REFUSED' if kind == 'COMPLETE_JACOBIAN' else 'FINAL_TAIL_BUDGET_ADMISSION_REFUSED'
            raise ReferenceRefusal(refusal, 'Complete '+kind+' requires '+str(cost)+' callbacks and '+str(reserve)+' tail slots; no callback was made after refusal')
        return row

    def frozen_call(dm, phase, coordinates=None, reserve=0, detail=None):
        nonlocal last_call, last_validated
        if len(ledger) >= maximum_evaluations-reserve:
            raise ReferenceRefusal('EVALUATION_BUDGET_EXHAUSTED', 'Every actual callback, including failed finite differences, consumes the hard budget')
        assert_sources_frozen()
        argument = dm.copy()
        identity = density_id(argument)
        row = {'evaluation_count': len(ledger)+1, 'phase': phase, 'density_id': identity,
               'status': 'STARTED', 'precharged': True, 'callback_entered': False,
               'callback_completed': False, 'callback_failed': False,
               'execution_kind': execution_kind,
               'native_molecular_execution': 'REQUIRES_EVALUATOR_NATIVE_SNAPSHOT' if execution_kind == SOURCE_EXECUTION_KIND else 'SIMULATED_NOT_MOLECULAR'}
        if coordinates is not None:
            row['local_rotation_coordinates'] = np.asarray(coordinates).tolist()
        if detail is not None:
            row.update(detail)
        ledger.append(row)
        last_call = {'evaluation_count': len(ledger), 'phase': phase, 'density_id': identity,
                     'density': _frozen_array(argument), 'status': 'STARTED', 'matched_snapshot_id': None}
        started = time.monotonic()
        try:
            callback_context = {'evaluation_count': len(ledger), 'density_id': identity, 'phase': phase,
                'admission_group_id': None, 'chart': None, 'fd_sample': None,
                'base_snapshot_id': None, 'base_density_id': None, 'base_operator_id': None}
            callback_context.update(detail or {})
            evaluate.bind_candidate_callback(_freeze(callback_context))
            row['callback_entered'] = True
            if execution_kind == ENGINEERING_EXECUTION_KIND:
                ENGINEERING_SIMULATED_CALLBACK_COUNTS['entered'] += 1
            try:
                value = evaluate(argument, phase)
            except BaseException:
                if execution_kind == ENGINEERING_EXECUTION_KIND:
                    ENGINEERING_SIMULATED_CALLBACK_COUNTS['failed'] += 1
                raise
            row['callback_completed'] = True
            if execution_kind == ENGINEERING_EXECUTION_KIND:
                ENGINEERING_SIMULATED_CALLBACK_COUNTS['completed'] += 1
            assert_sources_frozen()
            if density_id(argument) != identity:
                raise ReferenceRefusal('REQUESTED_DENSITY_MODIFIED', 'Evaluator modified its requested density')
            if (not isinstance(value, dict) or value.get('density_id') != identity
                    or value.get('operator_source') != TRUE_OPERATOR):
                raise ReferenceRefusal('EVALUATOR_IDENTITY_MISMATCH', 'Evaluator must bind true F to the exact requested density')
            fock = real_array(value.get('fock'), 'True F').copy()
            if fock.shape != dm.shape or not np.allclose(fock, fock.T, rtol=0, atol=1e-12):
                raise ValueError('True F dimensions or symmetry differ')
            raw_fock = real_array(value.get('raw_fock'), 'Actual unprojected G').copy()
            if raw_fock.shape != dm.shape or not np.allclose(raw_fock, raw_fock.T, rtol=0, atol=1e-12):
                raise ValueError('Actual G dimensions or symmetry differ')
            projected = raw_fock.copy()
            projected[mask] = 0.0
            if np.max(np.abs(fock[mask]), initial=0) > 1e-12 or np.max(np.abs(projected-fock), initial=0) > 1e-12:
                raise ValueError('Callback F does not match the unchanged Pmask(G) rule')
            checked = {'fock': fock, 'raw_fock': raw_fock,
                       'density_id': identity, 'operator_source': TRUE_OPERATOR}
            for key in ('total_energy', 'electronic_energy', *COMPONENTS, *COUNTS):
                checked[key] = real_scalar(value.get(key), key)
            if abs(checked['electronic_energy']+checked['nuclear_repulsion']-checked['total_energy']) > 1e-9:
                raise ValueError('Electronic/nuclear/total ledger mismatch')
            if abs(checked['masked_metric_electron_count']-float(np.trace(s@dm))) > 1e-7:
                raise ValueError('Declared masked electron count does not match requested D/S')
            optional_matrices = {}
            for key in OPTIONAL_MATRICES:
                if key in value:
                    matrix = real_array(value[key], key).copy()
                    if matrix.shape != dm.shape or not np.allclose(matrix, matrix.T, rtol=0, atol=1e-12):
                        raise ValueError('Optional matrix dimensions or symmetry differ: '+key)
                    optional_matrices[key] = matrix
            fock_id = density_id(fock)
            components = {key: checked[key] for key in COMPONENTS}
            electron_counts = {key: checked[key] for key in COUNTS}
            matched_id = operator_id(identity, fock, raw_fock, checked['total_energy'],
                components, checked['electronic_energy'], electron_counts)
            prior = operators.get(identity)
            row.update(fock_id=fock_id, previous_same_density_operator_id=prior,
                       same_density_operator_reproducible=None if prior is None else matched_id == prior)
            if prior is not None and matched_id != prior:
                raise ReferenceRefusal('NONREPRODUCIBLE_SAME_DENSITY_OPERATOR', 'Same density returned different F/G/energy/component/count ledger bytes')
            operators[identity] = matched_id
            snapshot_id = 'evaluation-'+str(len(ledger))
            snapshot = _freeze({'snapshot_id': snapshot_id, 'evaluation_count': len(ledger),
                'phase': phase, 'density': dm.copy(), 'density_id': identity, 'fock': fock,
                'fock_id': fock_id, 'raw_fock': raw_fock, 'raw_fock_id': density_id(raw_fock),
                'operator_id': matched_id, 'operator_source': TRUE_OPERATOR,
                'execution_kind': execution_kind,
                'operator_evidence_kind': 'SOURCE_BOUND_CALLBACK_REQUIRES_NATIVE_COUNTERS' if execution_kind == SOURCE_EXECUTION_KIND else 'SIMULATED_CALLBACK_NOT_MOLECULAR_F',
                'total_energy': checked['total_energy'], 'electronic_energy': checked['electronic_energy'],
                'components': components, 'electron_counts': electron_counts, 'optional_matrices': optional_matrices,
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
                        'density': snapshot['density'], 'fock': snapshot['fock'], 'raw_fock': snapshot['raw_fock'],
                        'total_energy': snapshot['total_energy'], 'electronic_energy': snapshot['electronic_energy'],
                        'components': snapshot['components'], 'electron_counts': snapshot['electron_counts']})

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
        u = initial_frame
        initialized.update(status='PREPARED_EXPLICIT_OCCUPIED_SPACE_INITIALIZATION_NO_V2', initial_density_id=density_id(d))
        current = frozen_call(d, 'CURRENT_INITIAL')
        for chart in range(maximum_charts):
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
                    emit_admission(group)
                    def fd_objective(point):
                        return sample(point, 'FD_SAMPLE', {'admission_group_id': group['group_id'], 'chart': chart+1,
                                      'fd_sample': len(ledger)-before+1,
                                      'base_snapshot_id': group['base_snapshot_id'],
                                      'base_density_id': group['base_density_id'],
                                      'base_operator_id': group['base_operator_id']})[3]
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
                    emit_admission(group)

            optimized = least_squares(objective, np.zeros(k), method='trf', jac=jacobian,
                bounds=(-trust_radius*np.ones(k), trust_radius*np.ones(k)), x_scale=trust_radius,
                ftol=1e-13, xtol=1e-13, gtol=1e-13, max_nfev=chart_max_nfev)
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
        tail_group = admission('FINAL_TAIL', TAIL_SLOTS, reserve=0, context={
            'base_snapshot_id': current['snapshot_id'], 'base_density_id': current['density_id'],
            'base_operator_id': snapshots[current['snapshot_id']]['operator_id']})
        before = len(ledger)
        tail['status'] = 'ENTERED_WITH_SEPARATE_CALLBACKS'
        tail_group['status'] = 'STARTED'
        tail_context = {'admission_group_id': tail_group['group_id'], 'chart': 1, 'fd_sample': None,
            'base_snapshot_id': tail_group['base_snapshot_id'], 'base_density_id': tail_group['base_density_id'],
            'base_operator_id': tail_group['base_operator_id']}
        try:
            emit_admission(tail_group)
            final = frozen_call(d, 'FINAL_RETURNED_DENSITY', detail=tail_context)
            gate, mapped = assess(d, final)
            gate['returned_density_energy_recheck_hartree'] = abs(final['total_energy']-current['total_energy'])
            if gate['qualified'] and gate['returned_density_energy_recheck_hartree'] <= 1e-9:
                rechecked = frozen_call(mapped, 'FINAL_RAW_AUFBAU_DENSITY_RECHECK', detail=tail_context)
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
            tail_group['status'] = 'REFUSED_PARTIAL_NO_RETRY'
            raise
        finally:
            tail['actual_callbacks'] = tail_group['actual_callbacks'] = len(ledger)-before
            tail_group['unexecuted_planned_callbacks'] = TAIL_SLOTS-tail_group['actual_callbacks']
            emit_admission(tail_group)
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
    evaluator_snapshot = evaluate.snapshot()
    return _freeze({'reference_id': REFERENCE_ID, 'status': 'SOURCE_BOUND_ROOT_DIAGNOSTIC_CANDIDATE' if execution_kind == SOURCE_EXECUTION_KIND else 'SIMULATED_NATIVE_ROOT_CANDIDATE_ENGINEERING_ONLY',
        'execution_kind': execution_kind, 'scientific_execution_authorized': scientific_execution_authorized,
        'authorization_scope': 'SEPARATELY_VALIDATED_SOURCE_DIAGNOSTIC_ONLY' if execution_kind == SOURCE_EXECUTION_KIND else 'SIMULATED_ENGINEERING_ONLY_NO_MOLECULAR_EXECUTION',
        'source_execution_authorized_by_this_module': False,
        'engine_qualification_scope': 'SOURCE_BOUND_ORIGINAL_GATES_REQUIRE_NATIVE_EVIDENCE' if execution_kind == SOURCE_EXECUTION_KIND else 'SIMULATED_ARRAY_ORIGINAL_GATES_NOT_MOLECULAR_ACCEPTANCE',
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
            'native_molecular_callbacks': 'READ_EVALUATOR_SNAPSHOT_NOT_INFERRED_FROM_SLOTS'},
        'evaluator_execution_snapshot': evaluator_snapshot,
        'native_accounting_snapshot': evaluator_snapshot.get('accounting_snapshot'),
        'native_execution_counts': evaluator_snapshot.get('native_execution_counts'),
        'numeric_instrumentation_status': evaluator_snapshot.get('numeric_instrumentation_status', 'UNOBSERVED'),
        'candidate_callback_counts_not_native_counts': {'entered': sum(row['callback_entered'] for row in ledger),
            'completed': sum(row['callback_completed'] for row in ledger),
            'failed': sum(row['callback_failed'] for row in ledger)},
        'parameters': {'maximum_charts': maximum_charts, 'chart_max_nfev': chart_max_nfev,
            'historical_budgeted_core_chart_max_nfev': 8,
            'initialization_policy': initialization_policy,
            'maximum_evaluations': maximum_evaluations,
            'maximum_default_complete_Jacobians': 2,
            'default_callback_upper_bound_with_two_J_and_two_tails': 197,
            'default_callback_bound_scope': 'PINNED_N14_ELECTRONS16_VARIABLES48_DEFAULT_CHART1_NFEV2_ONLY',
            'rotation_variables': k, 'complete_jacobian_callback_cost': 2*k,
            'scheduler_callback_upper_bound': 1+maximum_charts*chart_max_nfev*(1+2*k)+TAIL_SLOTS,
            'formal_return_policy': 'LAST_NORMALLY_RETURNED_STRICTLY_IMPROVING_CHART_NOT_BEST_OR_INTERNAL_UNRETURNED_ITERATE',
            'trial_density_roundoff_symmetrization': 'SAME_SINGLE_AVERAGE_AS_OLD_CHART_NO_MANIFOLD_REPAIR',
            'scipy_callback_return_strategy': 'NOT_IMPLEMENTED',
            'local_component_bound': trust_radius,
            'finite_difference_relative_step': finite_difference_step,
            'derivative_policy': DERIVATIVE_POLICY, 'scipy_private_api_version': scipy_version,
            'tail_callbacks_reserved': TAIL_SLOTS, 'thresholds': dict(THRESHOLDS)},
        'production_activation': False, 'compute_enabled': False,
        'research_acceptance': 'NOT_ACCEPTED', 'molecular_acceptance': 'NOT_ACCEPTED',
        'comparison_available': False, 'deltas': None, 'delta_hartree': None,
        'delta_kcal_mol': None, 'variational_status': 'NOT_ESTABLISHED',
        'comparison_status': {'UM-P12': 'NOT_EXECUTED', 'UM-P13': 'NOT_EXECUTED', 'T06': 'NOT_EXECUTED'},
        'shared_dependencies': ['NUMPY', 'SCIPY'],
        'method_review_status': 'CANCELLED_INTERNAL_PENDING'})
