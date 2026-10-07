"""Four fixed occupied-space densities, one F observation per three paths.

This isolated adapter permits an explicitly authorized prepared diagnostic or
an engineering fake.  It performs no SCF, state selection, optimization, tail
recheck, root search or scientific approval.  The worker must independently
report native F/NR attempts; callback slots never establish those counters.
"""
from __future__ import annotations

import threading

import numpy as np

from .acceptance_resources import _lock
from .residual_budget import ConditionalCallbackBudget, CallbackBudgetError
from .occupation_response import (PATH_NAMES, SAME_D_THRESHOLDS, COMPONENTS,
    density_id, _checked_snapshot, _freeze)
from .occupied_space_admission import (REQUIRED_ANGLES, FAMILY_ROLE,
    _preflight, _digest, _array_owners)


LIVE_EXECUTION_KIND = 'PREPARED_OCCUPIED_SPACE_SINGLE_RESPONSE_DIAGNOSTIC'
EXECUTION_KINDS = frozenset(('ENGINEERING_FAKE', LIVE_EXECUTION_KIND))
ENGINEERING_FAKE_CALLBACK_COUNTS = {'entered': 0, 'completed': 0, 'failed': 0}
PREPARED_WRAPPER_CALLBACK_COUNTS = {'entered': 0, 'completed': 0, 'failed': 0}
_USED_RESPONSE_PREPARATIONS = {}
_CLAIM_LOCK = threading.Lock()


def _claim_once(prepared):
    with _CLAIM_LOCK:
        if id(prepared) in _USED_RESPONSE_PREPARATIONS:
            raise ValueError('The same response-preparation object is single-use; no fresh-book retry')
        # Retain the object so recycled Python IDs cannot create false matches.
        _USED_RESPONSE_PREPARATIONS[id(prepared)] = prepared


def preflight_occupied_space_response(*, prepared_seeds, overlap, electrons, matrix_delete_mask):
    """Verify the complete fixed recipe with arrays only, without a journal.

    Public worker readiness interface.  Reuse the previous strict seven-return
    verification, including actual source bytes, four output IDs, whole-family
    regeneration, and all unchanged density admission thresholds.  The fresh
    regenerated values are verification witnesses and never replace input D.
    """
    s, mask, densities, admissions, ids, source_admission, recipe_digest = _preflight(
        prepared_seeds, overlap, electrons, matrix_delete_mask)
    return _freeze({'status': 'PASS_STRICT_OCCUPIED_SPACE_RESPONSE_READINESS',
        'overlap': s, 'matrix_delete_mask': mask, 'density_copies': densities,
        'density_ids': ids, 'seed_admissions': admissions, 'source_admission': source_admission,
        'prepared_family_canonical_sha256': recipe_digest, 'required_angles_rad': REQUIRED_ANGLES,
        'functional_calls': 0, 'repairs_performed': False,
        'scientific_execution_authorized': False, 'scientific_approval': False,
        'engine_qualified': False, 'research_qualified': False, 'compute_enabled': False})


def _same_density_comparisons(snapshots):
    rows = []
    for index, angle in enumerate(REQUIRED_ANGLES, 1):
        group = {row['path_name']: row for row in snapshots if row['seed_index'] == index}
        if set(group) != set(PATH_NAMES):
            continue
        left = group['production_copy']
        for path in PATH_NAMES[1:]:
            right, checks = group[path], {}
            if left['density_id'] != right['density_id']:
                raise ValueError('Same-D comparison contains unmatched density identities')
            for field in ('fock', 'raw_fock'):
                with np.errstate(over='raise', invalid='raise', divide='raise'):
                    difference = left[field]-right[field]
                    maximum = float(np.max(np.abs(difference)))
                    norm = float(np.linalg.norm(difference))
                checks[field] = {'max_abs': maximum, 'frobenius': norm,
                    'pass': maximum <= SAME_D_THRESHOLDS['matrix_max_abs'] and norm <= SAME_D_THRESHOLDS['matrix_frobenius']}
            for field in COMPONENTS:
                observed = abs(left['components'][field]-right['components'][field])
                checks[field] = {'abs_difference_hartree': observed,
                    'pass': observed <= SAME_D_THRESHOLDS['component_hartree']}
            for field, threshold in (('total_energy', 'total_energy_hartree'),
                                      ('grid_electron_count', 'grid_electron_count_abs')):
                observed = abs(left[field]-right[field])
                checks[field] = {'abs_difference': observed, 'pass': observed <= SAME_D_THRESHOLDS[threshold]}
            rows.append({'seed_index': index, 'angle_rad': angle,
                'density_id': left['density_id'], 'left_path': 'production_copy', 'right_path': path,
                'execution_kind': left['execution_kind'], 'checks': checks,
                'status': 'PASS_SINGLE_D_OPERATOR_AND_ENERGY_SUBSET' if all(row['pass'] for row in checks.values()) else 'FAIL_SINGLE_D_OPERATOR_AND_ENERGY_SUBSET',
                'thresholds': dict(SAME_D_THRESHOLDS),
                'full_T05': 'NOT_EXECUTED', 'root_acceptance': 'NOT_EXECUTED',
                'complete_endpoint_acceptance': 'NOT_EXECUTED',
                'UM-P12': 'NOT_EXECUTED', 'UM-P13': 'NOT_EXECUTED', 'T06': 'NOT_EXECUTED'})
    return tuple(rows)


def _journal_configuration(journal):
    return {'path': str(journal.path), 'lock_path': str(journal.lock_path),
        'batch_id': journal.batch_id, 'identity': journal.identity,
        'path_limits': journal.limits, 'total_limit': journal.total_limit}


def run_occupied_space_response(*, prepared_seeds, callbacks, overlap, electrons,
                               matrix_delete_mask, journal, execution_kind='ENGINEERING_FAKE',
                               scientific_execution_authorized=False):
    """Attempt the fixed four-by-three single-F batch once, with precharging.

    A live declaration requires exact boolean authorization plus the dedicated
    execution-identity contract.  It is not scientific method approval.  Every
    prepared input is checked before the first callback.  Callback exceptions
    or invalid returned data charge FAILED and stop the batch.  Original gate
    failures are diagnostic observations, not invalid operator snapshots.
    No refunds, retries, replacement densities or final tail calls occur.
    """
    from .occupied_space_response_contract import validate_response_journal_identity
    if not isinstance(journal, ConditionalCallbackBudget):
        raise ValueError('A durable ConditionalCallbackBudget is required')
    with _lock(journal.path.with_name(journal.path.name+'.occupied-response.lock')):
        fresh = journal.snapshot()
        if (fresh['path_limits'] != {name: 4 for name in PATH_NAMES} or fresh['total_limit'] != 12
                or fresh['charged_slots'] != 0 or any(row['state'] != 'OPEN' for row in fresh['paths'].values())):
            raise CallbackBudgetError('Require a fresh empty OPEN four-per-path/twelve-total journal; no reset')
        # Keep accounting configuration privately bound.  A callback holding
        # the caller's journal may not defeat settlement by editing its config.
        book = ConditionalCallbackBudget(path=journal.path, batch_id=fresh['batch_id'],
            identity=fresh['identity'], path_limits=fresh['path_limits'], total_limit=fresh['total_limit'])
        caller_journal_digest = _digest(_journal_configuration(journal))
        reason, failure = 'OCCUPIED_SPACE_RESPONSE_PREFLIGHT_REFUSED', None
        snapshots, counts = [], {'entered': 0, 'completed': 0, 'failed': 0}
        ready, identity_receipt = None, None
        try:
            if not isinstance(execution_kind, str) or execution_kind not in EXECUTION_KINDS:
                raise ValueError('Unsupported occupied-space response execution kind')
            if type(scientific_execution_authorized) is not bool:
                raise ValueError('Scientific execution authorization must be an exact boolean')
            is_live = execution_kind == LIVE_EXECUTION_KIND
            if scientific_execution_authorized is not is_live:
                raise ValueError('Live responses require explicit authorization; engineering fakes require False')
            _claim_once(prepared_seeds)
            if (not isinstance(callbacks, dict) or set(callbacks) != set(PATH_NAMES)
                    or not all(callable(callbacks[name]) for name in PATH_NAMES)):
                raise ValueError('Require exactly the three fixed callable paths')
            ready = preflight_occupied_space_response(prepared_seeds=prepared_seeds,
                overlap=overlap, electrons=electrons, matrix_delete_mask=matrix_delete_mask)
            if is_live and fresh['batch_id'] != fresh['identity'].get('batch_id'):
                raise ValueError('Live callback journal batch must match the execution-contract identity')
            validated = validate_response_journal_identity(fresh['identity'],
                prepared_seeds=prepared_seeds, execution_kind=execution_kind)
            if validated is not True:
                raise ValueError('Response journal identity helper did not return an explicit validation pass')
            identity_receipt = {'status': 'PASS_EXPLICIT_RESPONSE_JOURNAL_IDENTITY_DECLARATIONS',
                'execution_kind': execution_kind, 'journal_identity_canonical_sha256': _digest(fresh['identity']),
                'batch_id': fresh['batch_id'], 'scope': 'LOCAL_DECLARATIONS_NOT_AUTHENTICATION_OR_METHOD_APPROVAL'}
            owner_digest, array_owners = _digest(prepared_seeds), _array_owners(prepared_seeds)
            caller_input_digests = (_digest(np.asarray(overlap)), _digest(np.asarray(matrix_delete_mask)))
            bound_callbacks = {name: callbacks[name] for name in PATH_NAMES}
            counter_domain = PREPARED_WRAPPER_CALLBACK_COUNTS if is_live else ENGINEERING_FAKE_CALLBACK_COUNTS

            def assert_frozen():
                if _digest(prepared_seeds) != owner_digest:
                    raise ValueError('Caller changed prepared source/output bytes or recipe records')
                current_owners = _array_owners(prepared_seeds)
                if (len(current_owners) != len(array_owners) or any(path != old_path or array is not old_array
                        for (path, array), (old_path, old_array) in zip(current_owners, array_owners))):
                    raise ValueError('Caller replaced a prepared source/output array owner reference')
                if (_digest(np.asarray(overlap)), _digest(np.asarray(matrix_delete_mask))) != caller_input_digests:
                    raise ValueError('Caller changed frozen overlap or matrix mask bytes')
                if set(callbacks) != set(PATH_NAMES) or any(callbacks[name] is not bound_callbacks[name] for name in PATH_NAMES):
                    raise ValueError('Caller changed an admitted callback path')
                if _digest(_journal_configuration(journal)) != caller_journal_digest:
                    raise ValueError('Caller changed the admitted journal configuration')

            reason = 'OCCUPIED_SPACE_SINGLE_F_RESPONSE_DIAGNOSTIC_COMPLETE'
            for index, (d, angle, did) in enumerate(zip(ready['density_copies'], REQUIRED_ANGLES, ready['density_ids']), 1):
                for path in PATH_NAMES:
                    try:
                        assert_frozen()
                    except Exception as error:
                        reason = 'OCCUPIED_SPACE_SINGLE_F_RESPONSE_DIAGNOSTIC_REFUSED'
                        failure = {'exception_type': type(error).__name__, 'detail': str(error),
                            'seed_index': index, 'path_name': path, 'callback_entered': False}
                        break
                    phase = 'SINGLE_F_OCCUPIED_SPACE_RESPONSE_SEED_'+str(index)
                    slot = book.charge(path, did, phase)
                    argument = d.copy()
                    try:
                        counts['entered'] += 1
                        counter_domain['entered'] += 1
                        try:
                            value = callbacks[path](argument, phase)
                        except BaseException:
                            counts['failed'] += 1
                            counter_domain['failed'] += 1
                            raise
                        counts['completed'] += 1
                        counter_domain['completed'] += 1
                        if density_id(argument) != did:
                            raise ValueError('Callback mutated the requested seed density argument')
                        assert_frozen()
                        raw = _checked_snapshot(value, d, ready['overlap'], electrons,
                            ready['matrix_delete_mask'], probe_name='OCCUPIED_SPACE_SEED_'+str(index),
                            path_name=path, slot_id=slot['slot_id'])
                        saved = _freeze(dict(raw, role='SINGLE_F_OCCUPIED_SPACE_RESPONSE_DIAGNOSTIC',
                            source_family_role=FAMILY_ROLE, seed_index=index, angle_rad=angle,
                            execution_kind=execution_kind,
                            operator_evidence_kind='PREPARED_CALLBACK_DECLARATION_REQUIRES_WORKER_NATIVE_EXECUTION_EVIDENCE' if is_live else 'SYNTHETIC_CALLBACK_DECLARATION_NOT_MOLECULAR_F',
                            complete_endpoint_acceptance='NOT_EXECUTED'))
                        book.finish(slot['slot_id'], status='SUCCEEDED', operator_id=saved['operator_id'])
                        snapshots.append(saved)
                    except BaseException as error:
                        book.finish(slot['slot_id'], status='FAILED', detail=(type(error).__name__+': '+str(error))[:2048])
                        reason = 'OCCUPIED_SPACE_SINGLE_F_RESPONSE_DIAGNOSTIC_REFUSED'
                        failure = {'exception_type': type(error).__name__, 'detail': str(error),
                            'seed_index': index, 'path_name': path, 'slot_id': slot['slot_id'], 'callback_entered': True}
                        if not isinstance(error, Exception): raise
                        break
                if failure is not None: break
        except BaseException:
            if reason == 'OCCUPIED_SPACE_SINGLE_F_RESPONSE_DIAGNOSTIC_COMPLETE':
                reason = 'OCCUPIED_SPACE_SINGLE_F_RESPONSE_DIAGNOSTIC_REFUSED'
            raise
        finally:
            for path, row in book.snapshot()['paths'].items():
                if row['state'] == 'OPEN': book.close_path(path, reason)
        settled = book.snapshot()
        comparisons = _same_density_comparisons(snapshots)
        subset_pass = len(comparisons) == 8 and all(row['status'].startswith('PASS_') for row in comparisons)
        return _freeze({'response_id': 'PREPARED_OCCUPIED_SPACE_TWELVE_SINGLE_F_RESPONSES_V1',
            'status': reason, 'stop_reason': reason, 'failure': failure, 'execution_kind': execution_kind,
            'source_family_role': FAMILY_ROLE, 'required_angles_rad': REQUIRED_ANGLES,
            'readiness': ready, 'execution_identity_validation': identity_receipt,
            'snapshots': tuple(snapshots), 'callback_ledger': settled['slots'], 'journal': settled,
            'single_density_comparisons': comparisons,
            'single_density_comparison_status': 'PASS_SINGLE_D_OPERATOR_AND_ENERGY_SUBSET' if subset_pass else ('FAIL_SINGLE_D_OPERATOR_AND_ENERGY_SUBSET' if len(comparisons) == 8 else 'NOT_EXECUTED_COMPLETE_FOUR_SEED_SUBSET'),
            'callback_accounting': {'precharged_slots': settled['charged_slots'], **counts,
                'counter_kind': 'WRAPPER_ENTRIES_NOT_NATIVE_F_OR_NR_OBSERVATIONS',
                'refunds': 0, 'automatic_retries': 0, 'tail_callbacks': 0},
            'engineering_fake_callback_counts': dict(counts) if execution_kind == 'ENGINEERING_FAKE' else None,
            'prepared_wrapper_callback_counts': dict(counts) if execution_kind == LIVE_EXECUTION_KIND else None,
            'native_execution_counts': {'status': 'UNOBSERVED_WORKER_NATIVE_COUNTERS_REQUIRED' if execution_kind == LIVE_EXECUTION_KIND else 'UNOBSERVED_ENGINEERING_GUARD_REQUIRED',
                'true_F': None, 'nr_rks': None},
            'scientific_execution_authorized': scientific_execution_authorized,
            'authorization_scope': 'ONE_FIXED_TWELVE_SINGLE_F_DIAGNOSTIC_NOT_SCF_OR_SCIENTIFIC_APPROVAL' if scientific_execution_authorized else 'ENGINEERING_FAKE_ONLY',
            'prepared_object_claim_scope': 'PROCESS_LOCAL_SINGLE_USE_NOT_DURABLE_AUTHENTICATION',
            'identity_evidence_kind': 'LOCAL_BYTES_AND_DECLARATIONS_NOT_AUTHENTICATION',
            'engine_qualified': False, 'research_qualified': False, 'compute_enabled': False,
            'production_activation': False, 'scientific_approval': False,
            'root_acceptance': 'NOT_EXECUTED', 'complete_endpoint_acceptance': 'NOT_EXECUTED',
            'comparison_available': False, 'delta_hartree': None, 'delta_kcal_mol': None, 'deltas': None,
            'comparison_status': {'full_T05': 'NOT_EXECUTED', 'UM-P12': 'NOT_EXECUTED',
                'UM-P13': 'NOT_EXECUTED', 'T06': 'NOT_EXECUTED'},
            'solver_iterations': 0, 'jacobian_evaluations': 0,
            'ordinary_occupied_space_preservation_claim': False, 'new_final_occupation_rule': False})
