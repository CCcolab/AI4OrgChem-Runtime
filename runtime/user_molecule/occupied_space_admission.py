"""Fake-only twelve-callback admission for four fixed occupied-space seeds.

This module cannot run a molecular mode.  It makes the bounded fake interface
reviewable; native execution counts require a separately installed engineering
guard.  It does not authorize a later real worker, scientific budget or solve.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading

import numpy as np

from .acceptance_resources import _lock
from .residual_budget import ConditionalCallbackBudget, CallbackBudgetError
from .occupation_response import (PATH_NAMES, density_id, _matrix,
    _admit_density, _checked_snapshot, _freeze)
from .occupied_space_seeds import (POLICY_ID, array_identity, _anchor,
    prepare_occupied_space_seeds)


REQUIRED_ANGLES = (-.25, -.1, .1, .25)
FAMILY_ROLE = 'NEW_GLOBAL_OCCUPIED_VIRTUAL_INITIALIZATION_DIAGNOSTIC_NOT_V2_ORDINARY_SPACE_PRESERVATION'
SNAPSHOT_ROLE = 'SINGLE_F_ENGINEERING_SEED_ADMISSION'
ENGINEERING_FAKE_CALLBACK_COUNTS = {'entered': 0, 'completed': 0, 'failed': 0}
_USED_PREPARATIONS = {}
_CLAIM_LOCK = threading.Lock()


def _jsonable(value):
    if isinstance(value, np.ndarray):
        array = np.ascontiguousarray(value)
        return {'array_shape': list(array.shape), 'array_dtype': array.dtype.str,
            'array_raw_sha256': hashlib.sha256(array.tobytes(order='C')).hexdigest()}
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError('Prepared record must use string dictionary keys')
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def _digest(value):
    encoded = json.dumps(_jsonable(value), sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _identity_equal(left, right):
    # FrozenRecord stores shape sequences as tuples; JSON stores lists.
    return _digest(left) == _digest(right)


def _array_owners(value, path=()):
    if isinstance(value, np.ndarray):
        return [(path, value)]
    if isinstance(value, dict):
        return [item for key, member in sorted(value.items()) for item in _array_owners(member, path+(key,))]
    if isinstance(value, (list, tuple)):
        return [item for index, member in enumerate(value) for item in _array_owners(member, path+(index,))]
    return []


def _claim_once(prepared):
    with _CLAIM_LOCK:
        if id(prepared) in _USED_PREPARATIONS:
            raise ValueError('The same prepared family object is single-use; no fresh-journal retry')
        # Keep a strong reference so object-ID reuse cannot masquerade as retry.
        # This is a process-local fake marker, not durable authentication.
        _USED_PREPARATIONS[id(prepared)] = prepared


def _preflight(prepared, overlap, electrons, matrix_delete_mask):
    if (not isinstance(prepared, dict) or prepared.get('policy_id') != POLICY_ID
            or prepared.get('status') != 'PREPARED_PURE_ARRAY_NEW_INITIALIZATION_DIAGNOSTIC_CANDIDATE'):
        raise ValueError('Require the isolated occupied-space preparation family, not a prior nine-probe record')
    if tuple(prepared.get('angles_rad', ())) != REQUIRED_ANGLES:
        raise ValueError('Exactly four explicit ordered angles (-0.25,-0.1,0.1,0.25) are required')
    if any(type(prepared.get(key)) is not bool or prepared[key] for key in (
            'scientific_execution_authorized', 'scientific_approval', 'production_activation',
            'compute_enabled', 'engine_qualified', 'research_qualified', 'new_final_occupation_rule',
            'ordinary_occupied_space_preservation_claim', 'repairs_performed')):
        raise ValueError('Prepared family must preserve explicit unqualified, unauthorized diagnostic scope')
    if type(prepared.get('functional_calls')) is not int or prepared['functional_calls'] != 0:
        raise ValueError('Prepared family must report zero functional calls')
    s = _matrix(overlap, 'Masked overlap')
    if type(electrons) is not int or electrons < 2 or electrons % 2 or electrons >= 2*len(s):
        raise ValueError('Explicit global closed-shell electron count with a virtual orbital required')
    mask = np.asarray(matrix_delete_mask)
    if mask.dtype.kind != 'b' or mask.shape != s.shape or not np.array_equal(mask, mask.T):
        raise ValueError('Require a symmetric same-size boolean matrix deletion mask')
    mask = mask.copy()
    if float(np.max(np.abs(s[mask]), initial=0)) > 1e-12:
        raise ValueError('Masked overlap fails the unchanged matrix deletion rule')
    source = prepared.get('source')
    if not isinstance(source, dict) or source.get('electrons') != electrons or source.get('occupied_rank') != electrons//2:
        raise ValueError('Prepared source electron/rank declarations differ')
    source_id = source.get('density_id')
    if (not isinstance(source_id, str) or re.fullmatch('[0-9a-f]{64}', source_id) is None
            or source_id != source.get('expected_density_id')):
        raise ValueError('Prepared source density identity/declaration mismatch')
    if not _identity_equal(source.get('masked_overlap_identity'), array_identity(s)):
        raise ValueError('Prepared source masked-overlap identity differs from actual S')
    source_density = source.get('density_identity')
    if (not isinstance(source_density, dict) or tuple(source_density.get('shape', ())) != s.shape
            or source_density.get('dtype') != '<f8' or source_density.get('order') != 'C'
            or not isinstance(source_density.get('sha256'), str)
            or re.fullmatch('[0-9a-f]{64}', source_density['sha256']) is None):
        raise ValueError('Prepared source density array identity is incomplete or dimensionally incompatible')
    base_d = _matrix(prepared.get('source_density'), 'Prepared source D bytes', s.shape)
    base_s = _matrix(prepared.get('source_masked_overlap'), 'Prepared source S bytes', s.shape)
    if density_id(base_d) != source_id or not _identity_equal(array_identity(base_d), source_density):
        raise ValueError('Prepared source D bytes do not match their domain/array identities')
    if (not _identity_equal(array_identity(base_s), source['masked_overlap_identity'])
            or not _identity_equal(array_identity(base_s), array_identity(s))):
        raise ValueError('Prepared source S bytes do not match their identities or actual overlap')
    for field, identity_name in (('source_occupied_anchor', 'occupied_anchor_identity'),
                                 ('source_virtual_anchor', 'virtual_anchor_identity')):
        anchor = _anchor(prepared.get(field), field, len(s))
        if not _identity_equal(array_identity(anchor), source.get(identity_name)):
            raise ValueError('Prepared source anchor bytes do not match their explicit identities')
    sw, sv = np.linalg.eigh(s)
    if sw.min() <= 0:
        raise ValueError('Masked metric must remain positive definite without repair')
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        half, inverse = (sv*np.sqrt(sw))@sv.T, (sv/np.sqrt(sw))@sv.T
    if not all(np.isfinite(a).all() for a in (half, inverse)):
        raise ValueError('Masked whitening must remain finite')
    base_admission = _admit_density(base_d, s, electrons, half, inverse)
    family = prepared.get('seeds')
    if not isinstance(family, (list, tuple)) or len(family) != 4:
        raise ValueError('Exactly four prepared seed records are required')
    densities, admissions, identities = [], [], []
    for index, (row, angle) in enumerate(zip(family, REQUIRED_ANGLES), 1):
        if (not isinstance(row, dict) or type(row.get('seed_index')) is not int
                or row['seed_index'] != index or isinstance(row.get('angle_rad'), (bool, np.bool_))
                or row.get('angle_rad') != angle):
            raise ValueError('Prepared seed index/angle mapping differs from the explicit contract')
        if any(row.get(key) is not None for key in ('F_at_new_density', 'energy', 'operator_id')):
            raise ValueError('A prepared seed cannot carry claimed prior F/energy/operator observations')
        if row.get('molecular_evaluation') != 'NOT_EXECUTED' or row.get('endpoint_acceptance') != 'NOT_EXECUTED':
            raise ValueError('Prepared seed cannot claim prior scientific evaluation or acceptance')
        d = _matrix(row.get('density'), 'Prepared seed density', s.shape)
        actual_id = density_id(d)
        if actual_id != row.get('density_id') or not _identity_equal(row.get('density_identity'), array_identity(d)):
            raise ValueError('Prepared seed density bytes differ from their explicit identities')
        admissions.append(_admit_density(d, s, electrons, half, inverse))
        densities.append(d)
        identities.append(actual_id)
    if len(set(identities)) != 4:
        raise ValueError('The four fixed seeds must have distinct density identities')
    # Recompute the declared pure recipe for verification only.  Never replace
    # an input D with the freshly generated value, project it, or repair it.
    regenerated = prepare_occupied_space_seeds(density=base_d, masked_overlap=base_s,
        occupied_anchor=prepared['source_occupied_anchor'],
        virtual_anchor=prepared['source_virtual_anchor'], angles=REQUIRED_ANGLES,
        electrons=electrons, expected_density_id=source_id,
        expected_overlap_identity=array_identity(base_s) if source.get('expected_overlap_identity_supplied') is True else None)
    actual_recipe_digest, expected_recipe_digest = _digest(prepared), _digest(regenerated)
    if actual_recipe_digest != expected_recipe_digest:
        raise ValueError('Prepared seed densities or saved derived records do not match the exact source/anchor/angle recipe')
    return s, mask, tuple(densities), tuple(admissions), tuple(identities), base_admission, expected_recipe_digest


def run_seed_admission_fake(*, prepared_seeds, callbacks, overlap, electrons,
                           matrix_delete_mask, journal, execution_kind='ENGINEERING_FAKE'):
    """One fake-only four-seed/three-path attempt, without retry or tail calls.

    Every D is validated before the first charged callback.  Preflight errors
    raise and close an admitted fresh book.  Invalid returned data or callback
    exceptions consume FAILED slots and stop the batch.  A preparation object
    is single-use for this Python process, independently of durable journal
    refusal; that marker is not an authentication or cross-process ledger.
    """
    if not isinstance(journal, ConditionalCallbackBudget):
        raise ValueError('A durable ConditionalCallbackBudget is required')
    with _lock(journal.path.with_name(journal.path.name+'.occupied-admission.lock')):
        fresh = journal.snapshot()
        if (fresh['path_limits'] != {name: 4 for name in PATH_NAMES} or fresh['total_limit'] != 12
                or fresh['charged_slots'] != 0 or any(row['state'] != 'OPEN' for row in fresh['paths'].values())):
            raise CallbackBudgetError('Require a fresh empty OPEN four-per-path/twelve-total journal; no reset')
        reason, failure = 'SINGLE_F_ENGINEERING_SEED_ADMISSION_PREFLIGHT_REFUSED', None
        snapshots, counts, admissions, ids = [], {'entered': 0, 'completed': 0, 'failed': 0}, (), ()
        base_admission = None
        recipe_digest = None
        try:
            if execution_kind != 'ENGINEERING_FAKE':
                raise ValueError('Only ENGINEERING_FAKE is supported; no real or former nine-probe mode is admitted')
            _claim_once(prepared_seeds)
            if (not isinstance(callbacks, dict) or set(callbacks) != set(PATH_NAMES)
                    or not all(callable(callbacks[name]) for name in PATH_NAMES)):
                raise ValueError('Require exactly the three fixed callback paths')
            s, mask, densities, admissions, ids, base_admission, recipe_digest = _preflight(prepared_seeds, overlap, electrons, matrix_delete_mask)
            owner_id = _digest(prepared_seeds)
            array_owners = _array_owners(prepared_seeds)
            input_ids = (_digest(np.asarray(overlap)), _digest(np.asarray(matrix_delete_mask)))
            bound_callbacks = {name: callbacks[name] for name in PATH_NAMES}

            def assert_frozen():
                if _digest(prepared_seeds) != owner_id:
                    raise ValueError('Caller changed the prepared seed-family owner record or bytes')
                current_owners = _array_owners(prepared_seeds)
                if (len(current_owners) != len(array_owners) or
                        any(path != previous_path or array is not previous_array
                            for (path, array), (previous_path, previous_array) in zip(current_owners, array_owners))):
                    raise ValueError('Caller replaced a prepared seed-family source/output array owner reference')
                if (_digest(np.asarray(overlap)), _digest(np.asarray(matrix_delete_mask))) != input_ids:
                    raise ValueError('Caller changed frozen overlap or matrix deletion mask bytes')
                if set(callbacks) != set(PATH_NAMES) or any(callbacks[name] is not bound_callbacks[name] for name in PATH_NAMES):
                    raise ValueError('Caller changed admitted callback paths')

            reason = 'SINGLE_F_ENGINEERING_SEED_ADMISSION_COMPLETE'
            for index, (d, angle, did) in enumerate(zip(densities, REQUIRED_ANGLES, ids), 1):
                for path in PATH_NAMES:
                    try:
                        assert_frozen()
                    except Exception as error:
                        reason = 'SINGLE_F_ENGINEERING_SEED_ADMISSION_REFUSED'
                        failure = {'exception_type': type(error).__name__, 'detail': str(error),
                            'seed_index': index, 'path_name': path, 'callback_entered': False}
                        break
                    phase = 'SINGLE_F_ENGINEERING_SEED_'+str(index)
                    slot = journal.charge(path, did, phase)
                    argument = d.copy()
                    try:
                        counts['entered'] += 1
                        ENGINEERING_FAKE_CALLBACK_COUNTS['entered'] += 1
                        try:
                            value = callbacks[path](argument, phase)
                        except BaseException:
                            counts['failed'] += 1
                            ENGINEERING_FAKE_CALLBACK_COUNTS['failed'] += 1
                            raise
                        counts['completed'] += 1
                        ENGINEERING_FAKE_CALLBACK_COUNTS['completed'] += 1
                        if density_id(argument) != did:
                            raise ValueError('Callback mutated its requested seed density argument')
                        assert_frozen()
                        raw = _checked_snapshot(value, d, s, electrons, mask,
                            probe_name='OCCUPIED_SPACE_SEED_'+str(index), path_name=path, slot_id=slot['slot_id'])
                        saved = _freeze(dict(raw, role=SNAPSHOT_ROLE, source_family_role=FAMILY_ROLE,
                            seed_index=index, angle_rad=angle, execution_kind='ENGINEERING_FAKE',
                            operator_evidence_kind='SYNTHETIC_CALLBACK_DECLARATION_NOT_MOLECULAR_F',
                            complete_endpoint_acceptance='NOT_EXECUTED'))
                        journal.finish(slot['slot_id'], status='SUCCEEDED', operator_id=saved['operator_id'])
                        snapshots.append(saved)
                    except BaseException as error:
                        journal.finish(slot['slot_id'], status='FAILED', detail=(type(error).__name__+': '+str(error))[:2048])
                        reason = 'SINGLE_F_ENGINEERING_SEED_ADMISSION_REFUSED'
                        failure = {'exception_type': type(error).__name__, 'detail': str(error),
                            'seed_index': index, 'path_name': path, 'slot_id': slot['slot_id'], 'callback_entered': True}
                        if not isinstance(error, Exception): raise
                        break
                if failure is not None: break
        except BaseException:
            if reason == 'SINGLE_F_ENGINEERING_SEED_ADMISSION_COMPLETE':
                reason = 'SINGLE_F_ENGINEERING_SEED_ADMISSION_REFUSED'
            raise
        finally:
            for path, row in journal.snapshot()['paths'].items():
                if row['state'] == 'OPEN': journal.close_path(path, reason)
        settled = journal.snapshot()
        return _freeze({'admission_id': 'FAKE_ONLY_OCCUPIED_SPACE_TWELVE_CALLBACK_ADMISSION_V1',
            'status': reason, 'stop_reason': reason, 'failure': failure, 'execution_kind': 'ENGINEERING_FAKE',
            'source_family_role': FAMILY_ROLE, 'required_angles_rad': REQUIRED_ANGLES,
            'seed_density_ids': ids, 'seed_admissions': admissions,
            'source_admission': base_admission,
            'source_array_validation': {'base_density_domain_and_array_identities_verified': base_admission is not None,
                'base_masked_overlap_and_anchor_bytes_verified': base_admission is not None,
                'scope': 'ACTUAL_LOCAL_SOURCE_ARRAY_BYTES_NOT_AUTHENTICATION'},
            'recipe_validation': {'status': 'PASS_EXACT_RECOMPUTED_LOCAL_ARRAY_RECIPE' if recipe_digest is not None else 'NOT_EXECUTED',
                'expected_prepared_family_canonical_sha256': recipe_digest,
                'numpy_version': np.__version__, 'input_densities_replaced_or_repaired': False,
                'scope': 'SOURCE_ARRAY_ANCHOR_ANGLE_AND_DERIVED_RECORD_CORRESPONDENCE_NOT_AUTHENTICATION'},
            'snapshots': tuple(snapshots), 'callback_ledger': settled['slots'], 'journal': settled,
            'callback_accounting': {'precharged_slots': settled['charged_slots'], **counts,
                'counter_kind': 'WRAPPER_ENTRIES_NOT_NATIVE_F_OR_NR_OBSERVATIONS',
                'refunds': 0, 'automatic_retries': 0, 'tail_callbacks': 0},
            'engineering_fake_callback_counts': dict(counts),
            'native_execution_counts': {'status': 'UNOBSERVED_ENGINEERING_GUARD_REQUIRED', 'true_F': None, 'nr_rks': None},
            'prepared_object_claim_scope': 'PROCESS_LOCAL_SINGLE_USE_NOT_DURABLE_AUTHENTICATION',
            'identity_evidence_kind': 'LOCAL_BYTES_AND_DECLARATIONS_NOT_AUTHENTICATION',
            'engine_qualified': False, 'research_qualified': False, 'compute_enabled': False,
            'production_activation': False, 'scientific_execution_authorized': False, 'scientific_approval': False,
            'root_acceptance': 'NOT_EXECUTED', 'complete_endpoint_acceptance': 'NOT_EXECUTED',
            'comparison_available': False, 'delta_hartree': None, 'delta_kcal_mol': None, 'deltas': None,
            'comparison_status': {'full_T05': 'NOT_EXECUTED', 'UM-P12': 'NOT_EXECUTED',
                'UM-P13': 'NOT_EXECUTED', 'T06': 'NOT_EXECUTED'},
            'solver_iterations': 0, 'jacobian_evaluations': 0,
            'ordinary_occupied_space_preservation_claim': False, 'new_final_occupation_rule': False})
