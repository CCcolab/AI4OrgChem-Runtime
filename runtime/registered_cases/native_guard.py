"""Owned, enumerated PySCF dispatch guards for three fixed registered cases.

This is a held Python-entry-point audit, not a general sandbox or a proof that
native/C extensions can be interrupted. P01 permits its ordinary RHF integrals,
J/K and energy evaluation; it does not claim all quantum operations are zero.
"""
from __future__ import annotations

import copy
import threading
from types import MappingProxyType


P01_TASK = 'p01-orbital-density'
_TASKS = {P01_TASK, 'p02-statistics', 'p13-graph-ledger'}
_ACTIVE_GUARD = None


class RegisteredNativeGuardError(RuntimeError): pass


def _load_modules():
    from pyscf import gto
    from pyscf.scf import hf, uhf, rohf
    from pyscf.dft import rks, uks, roks, gen_grid, numint
    from pyscf.lo import boys, pipek
    return dict(gto=gto, hf=hf, uhf=uhf, rohf=rohf, rks=rks, uks=uks,
                roks=roks, gen_grid=gen_grid, numint=numint, boys=boys, pipek=pipek)


class RegisteredNativeGuard:
    def __init__(self, task_id, *, engine_modules=None, stop_checkpoint=None):
        if task_id not in _TASKS: raise ValueError('Unknown registered task guard scope')
        if stop_checkpoint is not None and not callable(stop_checkpoint):
            raise ValueError('An explicit callable stop checkpoint is required')
        self.task_id = task_id
        self.stop_checkpoint = self._held_stop = stop_checkpoint
        self._supplied = engine_modules
        self.engine_kind = 'ENGINEERING_FAKE_MODULES' if engine_modules is not None else 'PINNED_PYSCF_MODULES'
        self._counts = {name: 0 for name in ('scf_kernel', 'boys_kernel', 'pipek_mezey_kernel', 'conditional_NR')}
        self._outcomes = {name: {'returned': 0, 'failed': 0} for name in self.counts if name != 'conditional_NR'}
        self._bindings = []; self._forbidden = []; self._changed = []
        self._active = False; self._used = False; self._closed = False
        self._restore_errors = []; self._closing_snapshot = None
        self._sealed_snapshot = None
        self._rhf = self._localizer = None
        self._hf_calls = 0; self._lo_calls = 0
        self._thread = None

    @property
    def counts(self):
        return MappingProxyType(self._counts)

    def _deny(self, label, reason='operation is outside the fixed task scope'):
        self._forbidden.append({'operation': label, 'reason': reason, 'delegate_entered': False})
        raise RegisteredNativeGuardError(label + ': ' + reason)

    def _changed_now(self):
        changed = [row['label'] for row in self._bindings if getattr(row['owner'], row['name'], None) is not row['guard']]
        if self.stop_checkpoint is not self._held_stop: changed.append('stop_checkpoint')
        return changed

    def _held(self):
        changed = self._changed_now()
        for label in changed:
            if label not in self._changed: self._changed.append(label)
        if not self._active or threading.get_ident() != self._thread:
            self._forbidden.append({'operation': 'GUARD_CONTEXT', 'reason': 'inactive or foreign-thread dispatch', 'delegate_entered': False})
        if not self._active or threading.get_ident() != self._thread or changed:
            raise RegisteredNativeGuardError('Guard is inactive, changed, or called from another thread')

    def _check(self, phase):
        self._held()
        if self._held_stop is not None: self._held_stop(phase)
        self._held()

    def _allowed(self, label, counter, exact_class, original):
        def wrapped(instance, *args, **kwargs):
            self._held()
            if (self.task_id != P01_TASK or type(instance) is not exact_class
                    or self.counts[counter] != 0 or self._rhf is not None or self._localizer is not None):
                return self._deny(label, 'only one exact ordinary RHF/Boys/PM dispatch is allowed')
            self._check('BEFORE_REGISTERED_' + counter.upper())
            self._counts[counter] += 1
            if counter == 'scf_kernel': self._rhf = instance; self._hf_calls = 0
            else: self._localizer = instance; self._lo_calls = 0
            try:
                value = original(instance, *args, **kwargs)
                self._outcomes[counter]['returned'] += 1
                self._check('AFTER_REGISTERED_' + counter.upper())
                return value
            except BaseException:
                if self._outcomes[counter]['returned'] == 0: self._outcomes[counter]['failed'] += 1
                raise
            finally:
                if counter == 'scf_kernel': self._rhf = None
                else: self._localizer = None
        return wrapped

    def _forbidden_wrapper(self, label):
        def wrapped(*args, **kwargs):
            self._held()
            return self._deny(label)
        return wrapped

    def _rhf_alias(self, label, original):
        def wrapped(instance, *args, **kwargs):
            self._held()
            if self.task_id != P01_TASK or instance is not self._rhf:
                return self._deny(label, 'RHF .scf alias is available only inside its owned kernel')
            return original(instance, *args, **kwargs)
        return wrapped

    def _hf_kernel(self, label, original):
        def wrapped(instance, *args, **kwargs):
            self._held()
            if self.task_id != P01_TASK or instance is not self._rhf or self._hf_calls != 0:
                return self._deny(label, 'global hf.kernel must belong to the one active exact RHF kernel')
            self._hf_calls += 1
            return original(instance, *args, **kwargs)
        return wrapped

    def _lo_kernel(self, label, original):
        def wrapped(instance, *args, **kwargs):
            self._held()
            if self.task_id != P01_TASK or instance is not self._localizer or self._lo_calls != 0:
                return self._deny(label, 'global localization kernel requires the one owned localizer')
            self._lo_calls += 1
            return original(instance, *args, **kwargs)
        return wrapped

    def _targets(self, modules):
        required = {'gto', 'hf', 'uhf', 'rohf', 'rks', 'uks', 'roks', 'gen_grid', 'numint', 'boys', 'pipek'}
        if not isinstance(modules, dict) or set(modules) != required:
            raise ValueError('An explicit complete module mapping is required')
        m = modules
        targets = [(m['hf'].SCF, 'kernel', 'SCF.kernel', 'deny'),
            (m['hf'], 'kernel', 'hf.kernel', 'hf'),
            (m['hf'].RHF, 'kernel', 'RHF.kernel', 'scf_kernel'),
            (m['uhf'].UHF, 'kernel', 'UHF.kernel', 'deny'),
            (m['rohf'].ROHF, 'kernel', 'ROHF.kernel', 'deny'),
            (m['rks'].RKS, 'kernel', 'RKS.kernel', 'deny'),
            (m['uks'].UKS, 'kernel', 'UKS.kernel', 'deny'),
            (m['roks'].ROKS, 'kernel', 'ROKS.kernel', 'deny'),
            (m['gen_grid'].Grids, 'build', 'Grids.build', 'deny'),
            (m['numint'].NumInt, 'nr_rks', 'NumInt.nr_rks', 'deny'),
            (m['numint'], 'nr_rks', 'numint.nr_rks', 'deny'),
            (m['numint'].NumInt, 'nr_uks', 'NumInt.nr_uks', 'deny'),
            (m['numint'], 'nr_uks', 'numint.nr_uks', 'deny'),
            (m['boys'].Boys, 'kernel', 'Boys.kernel', 'boys_kernel'),
            (m['pipek'].PipekMezey, 'kernel', 'PipekMezey.kernel', 'pipek_mezey_kernel'),
            (m['hf'].SCF, 'scf', 'SCF.scf', 'alias'),
            (m['hf'].RHF, 'scf', 'RHF.scf', 'alias')]
        if self.task_id != P01_TASK:
            targets += [(m['gto'].Mole, 'intor', 'Mole.intor', 'deny'),
                (m['gto'].Mole, 'intor_by_shell', 'Mole.intor_by_shell', 'deny'),
                (m['gto'].Mole, 'energy_nuc', 'Mole.energy_nuc', 'deny')]
        # Pin additional exported low-level aliases when present in this PySCF version.
        for key in ('uhf', 'rohf'):
            if hasattr(m[key], 'kernel'): targets.append((m[key], 'kernel', key + '.kernel', 'deny'))
        for key in ('boys', 'pipek'):
            if hasattr(m[key], 'kernel'): targets.append((m[key], 'kernel', key + '.kernel', 'lo'))
        return targets

    def __enter__(self):
        global _ACTIVE_GUARD
        if self._used or _ACTIVE_GUARD is not None:
            raise ValueError('Guard is one-use; nested or concurrent contexts are refused')
        self._used = True
        modules = _load_modules() if self._supplied is None else self._supplied
        targets = self._targets(modules)
        captured = []
        # Capture every original before changing an ancestor class attribute.
        for owner, name, label, kind in targets:
            original = getattr(owner, name, None)
            if not callable(original): raise ValueError('Required guard API unavailable: ' + label)
            captured.append((owner, name, label, kind, original, name in vars(owner), vars(owner).get(name)))
        self._thread = threading.get_ident(); self._active = True; _ACTIVE_GUARD = self
        try:
            for owner, name, label, kind, original, owned, direct in captured:
                if kind in ('scf_kernel', 'boys_kernel', 'pipek_mezey_kernel'):
                    guard = self._allowed(label, kind, owner, original)
                elif kind == 'hf': guard = self._hf_kernel(label, original)
                elif kind == 'lo': guard = self._lo_kernel(label, original)
                elif kind == 'alias': guard = self._rhf_alias(label, original)
                else: guard = self._forbidden_wrapper(label)
                setattr(owner, name, guard)
                self._bindings.append({'owner': owner, 'name': name, 'label': label, 'original': original,
                                       'owned': owned, 'direct': direct, 'guard': guard})
        except BaseException:
            self._restore(); self._active = False; _ACTIVE_GUARD = None
            raise
        return self

    def _restore(self):
        for row in reversed(self._bindings):
            try:
                if row['owned']: setattr(row['owner'], row['name'], row['direct'])
                else: delattr(row['owner'], row['name'])
            except BaseException as error:
                self._restore_errors.append(row['label'] + ': ' + type(error).__name__ + ': ' + str(error))

    def __exit__(self, exc_type, exc_value, traceback):
        global _ACTIVE_GUARD
        held_at_close = bool(self._bindings) and not self._changed_now()
        self._closing_snapshot = self.snapshot()
        try: self._restore()
        finally:
            self._active = False; self._closed = True; _ACTIVE_GUARD = None
        restored = all((row['name'] in vars(row['owner'])) == row['owned']
            and getattr(row['owner'], row['name'], None) is row['original'] for row in self._bindings)
        self._sealed_snapshot = copy.deepcopy(self._closing_snapshot)
        self._sealed_snapshot.update(active=False, closed=True, restored_attributes_intact=restored,
            held_at_close=held_at_close, restoration_errors=list(self._restore_errors))
        if not restored or self._restore_errors: self._sealed_snapshot['status'] = 'FAIL'
        if self._restore_errors:
            raise RegisteredNativeGuardError('Original attribute restoration failed: ' + '; '.join(self._restore_errors)) from exc_value
        return False

    def snapshot(self):
        if self._closed and self._sealed_snapshot is not None:
            return copy.deepcopy(self._sealed_snapshot)
        if self._active:
            for label in self._changed_now():
                if label not in self._changed: self._changed.append(label)
        restored = None
        if self._closed:
            restored = all((row['name'] in vars(row['owner'])) == row['owned']
                and getattr(row['owner'], row['name'], None) is row['original'] for row in self._bindings)
        good = bool(self._bindings) and (self._active or self._closed) and not self._forbidden and not self._changed and not self._restore_errors and restored is not False
        return {'schema': 'registered-case-native-guard-v1', 'task': self.task_id,
            'status': 'PASS' if good else ('NOT_INSTALLED' if not self._bindings else 'FAIL'),
            'counts': dict(self.counts), 'call_outcomes': copy.deepcopy(self._outcomes),
            'engine_kind': self.engine_kind, 'counter_evidence': 'OBSERVED_OWNED_WRAPPER_DISPATCH_NOT_DRIVER_INTENT_OR_CONVERGENCE',
            'guard_operations': [row['label'] for row in self._bindings],
            'forbidden_attempts': copy.deepcopy(self._forbidden), 'changed_guards': list(self._changed),
            'active': self._active, 'closed': self._closed, 'restored_attributes_intact': restored,
            'restoration_errors': list(self._restore_errors),
            'p01_ordinary_integral_JK_energy_calls_allowed_not_individually_counted': self.task_id == P01_TASK,
            'all_quantum_calls_zero_claim': False,
            'scope': 'ENUMERATED_HELD_PYSCF_PYTHON_ENTRIES_NOT_GENERAL_SANDBOX_OR_C_INTERRUPT_PROOF'}
