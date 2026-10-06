"""Durable conditional-callback slots for a bounded acceptance batch.

Reuse the existing wall-budget locking/integrity primitives. This journal does
not launch processes, enforce cgroups, approve science, or enable Compute.
Charge before entering a callback; failed/crashed slots are never refunded.
The actual scientific-source attempts must also be reported by each evaluator.
"""
import copy
import hashlib
import json
from pathlib import Path
import re

from .acceptance_resources import (ResourceError, Budget, _atomic_write, _canonical,
                                  _lock, _name, _strict_load, _utc, identity_digest)


class CallbackBudgetError(ResourceError):
    pass


def reserve_single_process(budget, *, run_id, identity):
    """Atomically reserve one child; an existing attempt forbids any retry.

    Apply the existing Budget format/limits without changing historical code.
    An actual supervisor must still enforce those limits and settle wall time
    through termination and output collection. This reservation is not approval.
    """
    if not isinstance(budget, Budget):
        raise CallbackBudgetError('An existing durable wall Budget is required')
    _name(run_id,'run_id')
    digest = identity_digest(identity)
    identity = json.loads(_canonical(identity))
    with _lock(budget.lock_path):
        data = budget._load()
        if data['runs']:
            raise CallbackBudgetError('This diagnostic batch already attempted its one process; no automatic retry')
        timeout = budget.limits['max_process_seconds']
        if timeout > budget._snapshot(data)['remaining_seconds']:
            raise CallbackBudgetError('Insufficient fresh wall reservation')
        row = {'run_id':run_id,'state':'RESERVED','reserved_seconds':timeout,
            'identity':identity,'identity_sha256':digest,'reserved_at_utc':_utc(),
            'launch_policy':'ONE_PROCESS_NO_AUTOMATIC_RETRY'}
        data['runs'][run_id] = row
        budget._save(data)
        return copy.deepcopy(row)


def _sha(value, name):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise CallbackBudgetError(name+' must be a lowercase SHA-256')
    return value


class ConditionalCallbackBudget:
    """Single batch, up to three named paths; at most201 slots per path/603 total.

    Reopening the same journal preserves pending and failed charges. Changing
    identity/limits or reopening a closed path cannot create a fresh allowance.
    Files and local declarations are accounting evidence, not authentication.
    """
    def __init__(self, *, path, batch_id, identity, path_limits, total_limit):
        self.path = Path(path).absolute()
        self.batch_id = _name(batch_id, 'batch_id')
        identity_digest(identity)
        self.identity = json.loads(_canonical(identity))
        if not isinstance(path_limits, dict) or not 1 <= len(path_limits) <= 3:
            raise CallbackBudgetError('Require one to three explicit path limits')
        for name, limit in path_limits.items():
            _name(name, 'path_id')
            if type(limit) is not int or not 1 <= limit <= 201:
                raise CallbackBudgetError('Each path limit must be1..201')
        if type(total_limit) is not int or not 1 <= total_limit <= min(603, sum(path_limits.values())):
            raise CallbackBudgetError('Batch callback slots must be1..min(603,sum(path_limits))')
        self.limits = dict(path_limits)
        self.total_limit = total_limit
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.path.with_name(self.path.name+'.lock')
        with _lock(self.lock_path):
            if self.path.exists() or self.path.is_symlink():
                self._load()
            else:
                self._save({'schema_version':'conditional-callback-budget-v1',
                    'batch_id':self.batch_id,'identity':self.identity,
                    'path_limits':self.limits,'total_limit':self.total_limit,
                    'created_at_utc':_utc(),'paths':{name:{'state':'OPEN','stop_reason':None}
                                                  for name in self.limits},'slots':[]})

    def _save(self, data):
        data['updated_at_utc'] = _utc()
        data['integrity_sha256'] = hashlib.sha256(_canonical(data)).hexdigest()
        _atomic_write(self.path, data)

    def _load(self):
        if self.path.is_symlink():
            raise CallbackBudgetError('Callback journal must not be a symlink')
        data = _strict_load(self.path)
        if not isinstance(data, dict):
            raise CallbackBudgetError('Invalid callback journal')
        checksum = data.pop('integrity_sha256', None)
        if checksum != hashlib.sha256(_canonical(data)).hexdigest():
            raise CallbackBudgetError('Callback journal integrity mismatch; not reset')
        if (data.get('schema_version') != 'conditional-callback-budget-v1' or
                data.get('batch_id') != self.batch_id or data.get('identity') != self.identity or
                data.get('path_limits') != self.limits or data.get('total_limit') != self.total_limit):
            raise CallbackBudgetError('Existing identity/limits differ; not reset')
        if not isinstance(data.get('paths'), dict) or set(data['paths']) != set(self.limits):
            raise CallbackBudgetError('Journal path set differs')
        for row in data['paths'].values():
            if not isinstance(row, dict) or row.get('state') not in ('OPEN','CLOSED'):
                raise CallbackBudgetError('Invalid path state')
            if row['state'] == 'CLOSED' and not isinstance(row.get('stop_reason'), str):
                raise CallbackBudgetError('Closed path has no stop reason')
        slots = data.get('slots')
        if not isinstance(slots, list) or len(slots) > self.total_limit:
            raise CallbackBudgetError('Invalid callback slot list')
        counts = {name:0 for name in self.limits}
        for index, row in enumerate(slots, 1):
            if (not isinstance(row, dict) or type(row.get('slot_id')) is not int or
                    row.get('slot_id') != index or row.get('path_id') not in counts):
                raise CallbackBudgetError('Invalid slot identity')
            counts[row['path_id']] += 1
            _sha(row.get('density_id'), 'density_id')
            if row.get('status') not in ('PENDING','SUCCEEDED','FAILED'):
                raise CallbackBudgetError('Invalid slot status')
            if not isinstance(row.get('phase'), str) or not row['phase']:
                raise CallbackBudgetError('Invalid callback phase')
            if row.get('operator_id') is not None:
                _sha(row['operator_id'], 'operator_id')
        if any(counts[name] > limit for name, limit in self.limits.items()):
            raise CallbackBudgetError('Path allowance exceeded')
        return data

    def _snapshot(self, data):
        counts = {name:sum(row['path_id']==name for row in data['slots']) for name in self.limits}
        return {**copy.deepcopy(data),'charged_slots':len(data['slots']),
            'path_charged_slots':counts,'remaining_slots':self.total_limit-len(data['slots']),
            'pending_slots':sum(row['status']=='PENDING' for row in data['slots']),
            'failed_slots':sum(row['status']=='FAILED' for row in data['slots']),
            'counter_kind':'PRECHARGED_CALLBACK_SLOTS_NOT_PROOF_OF_ACTUAL_SOURCE_F_CALLS',
            'production_activation':False,'scientific_approval':False}

    def snapshot(self):
        with _lock(self.lock_path):
            return self._snapshot(self._load())

    def charge(self, path_id, density_id, phase):
        _sha(density_id,'density_id')
        if not isinstance(phase, str) or not 1 <= len(phase) <= 128:
            raise CallbackBudgetError('Explicit bounded phase required')
        with _lock(self.lock_path):
            data = self._load()
            if path_id not in self.limits or data['paths'][path_id]['state'] != 'OPEN':
                raise CallbackBudgetError('Path unknown or closed; no retry/reset')
            count = sum(row['path_id']==path_id for row in data['slots'])
            if count >= self.limits[path_id] or len(data['slots']) >= self.total_limit:
                raise CallbackBudgetError('Conditional callback allowance exhausted')
            row = {'slot_id':len(data['slots'])+1,'path_id':path_id,'density_id':density_id,
                'phase':phase,'status':'PENDING','operator_id':None,'charged_at_utc':_utc()}
            data['slots'].append(row)
            self._save(data)
            return copy.deepcopy(row)

    def finish(self, slot_id, *, status, operator_id=None, detail=None):
        if type(slot_id) is not int or slot_id < 1 or status not in ('SUCCEEDED','FAILED'):
            raise CallbackBudgetError('Explicit pending slot and terminal status required')
        if operator_id is not None: _sha(operator_id,'operator_id')
        if detail is not None and (not isinstance(detail,str) or len(detail)>2048):
            raise CallbackBudgetError('Bounded text detail required')
        with _lock(self.lock_path):
            data = self._load()
            if slot_id > len(data['slots']) or data['slots'][slot_id-1]['status'] != 'PENDING':
                raise CallbackBudgetError('Only a pending slot may finish once')
            row = data['slots'][slot_id-1]
            row.update(status=status,operator_id=operator_id,detail=detail,finished_at_utc=_utc())
            self._save(data)
            return copy.deepcopy(row)

    def close_path(self, path_id, stop_reason):
        if not isinstance(stop_reason,str) or not 1 <= len(stop_reason) <= 256:
            raise CallbackBudgetError('Explicit bounded stop reason required')
        with _lock(self.lock_path):
            data = self._load()
            if path_id not in data['paths'] or data['paths'][path_id]['state'] != 'OPEN':
                raise CallbackBudgetError('Only an open path may close once')
            data['paths'][path_id].update(state='CLOSED',stop_reason=stop_reason,closed_at_utc=_utc())
            self._save(data)
            return self._snapshot(data)

    def accounted_callback(self, path_id, callback, *, density_identity, operator_identity):
        """Wrap an evaluator without changing its operator or numerical rules.

        The wrapper precharges a slot before entry. An early evaluator refusal
        may therefore charge a slot while its actual-source counter stays zero.
        Never identify this conservative slot total with real XC/F executions.
        """
        if not all(callable(value) for value in (callback,density_identity,operator_identity)):
            raise CallbackBudgetError('Evaluator and identity functions must be callable')
        def accounted(density, *args, **kwargs):
            requested = density_identity(density)
            phase = kwargs.get('phase', args[0] if args else 'SOLVER_CALLBACK')
            slot = self.charge(path_id, requested, phase)
            try:
                value = callback(density, *args, **kwargs)
                if density_identity(density) != requested or value.get('density_id') != requested:
                    raise CallbackBudgetError('Evaluator density identity/mutation mismatch')
                self.finish(slot['slot_id'],status='SUCCEEDED',operator_id=operator_identity(value))
                return value
            except BaseException as error:
                self.finish(slot['slot_id'],status='FAILED',detail=(type(error).__name__+': '+str(error))[:2048])
                raise
        return accounted
