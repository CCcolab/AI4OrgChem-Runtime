"""Explicit toy module bindings; these tests never import or execute PySCF."""
from __future__ import annotations
from types import SimpleNamespace
import unittest

from runtime.registered_cases.native_guard import RegisteredNativeGuard, RegisteredNativeGuardError


def modules():
    observations = []
    hf = SimpleNamespace()
    boys = SimpleNamespace()
    pipek = SimpleNamespace()
    def hf_kernel(instance, *args, **kwargs):
        observations.append('ordinary_hf_delegate')
        return -1.
    def lo_kernel(instance, *args, **kwargs):
        observations.append('localization_delegate')
        return 'occupied-space'
    hf.kernel = hf_kernel; boys.kernel = lo_kernel; pipek.kernel = lo_kernel
    class SCF:
        def kernel(self):
            if getattr(self, 'before', None): self.before()
            if getattr(self, 'fault', None): raise self.fault
            return self.scf()
        def scf(self): return hf.kernel(self)
    class RHF(SCF): pass
    class UHF(SCF): pass
    class ROHF(SCF): pass
    class RKS(RHF): pass
    class UKS(UHF): pass
    class ROKS(ROHF): pass
    class Mole:
        def intor(self): observations.append('ordinary_integral'); return 1
        def intor_by_shell(self): observations.append('ordinary_shell_integral'); return 1
        def energy_nuc(self): observations.append('ordinary_nuclear_energy'); return 1
    class Grids:
        def build(self): observations.append('grid'); return 1
    class NumInt:
        def nr_rks(self): observations.append('nr_rks'); return 1
        def nr_uks(self): observations.append('nr_uks'); return 1
    class Boys:
        def kernel(self):
            if getattr(self, 'fault', None): raise self.fault
            return boys.kernel(self)
    class PipekMezey(Boys): pass
    hf.SCF = SCF; hf.RHF = RHF; boys.Boys = Boys; pipek.PipekMezey = PipekMezey
    mapping = {'hf': hf, 'uhf': SimpleNamespace(UHF=UHF, kernel=hf_kernel),
        'rohf': SimpleNamespace(ROHF=ROHF, kernel=hf_kernel), 'rks': SimpleNamespace(RKS=RKS),
        'uks': SimpleNamespace(UKS=UKS), 'roks': SimpleNamespace(ROKS=ROKS),
        'gto': SimpleNamespace(Mole=Mole), 'gen_grid': SimpleNamespace(Grids=Grids),
        'numint': SimpleNamespace(NumInt=NumInt, nr_rks=lambda: observations.append('global_nr_rks'),
            nr_uks=lambda: observations.append('global_nr_uks')), 'boys': boys, 'pipek': pipek}
    return mapping, observations


class RegisteredCaseNativeGuardTests(unittest.TestCase):
    def test_exact_task_ids_and_callable_stop_only(self):
        for task in ('p02-experimental', 'p13-graph', 'p14', 'P01'):
            with self.subTest(task=task), self.assertRaises(ValueError): RegisteredNativeGuard(task)
        with self.assertRaises(ValueError): RegisteredNativeGuard('p01-orbital-density', stop_checkpoint=True)

    def test_zero_science_tasks_have_held_and_restored_zero_receipt(self):
        for task in ('p02-statistics', 'p13-graph-ledger'):
            with self.subTest(task=task):
                m, observations = modules()
                with RegisteredNativeGuard(task, engine_modules=m) as guard:
                    self.assertEqual(guard.snapshot()['status'], 'PASS')
                    self.assertGreaterEqual(len(guard.snapshot()['guard_operations']), 14)
                receipt = guard.snapshot()
                self.assertEqual(receipt['counts'], dict(scf_kernel=0, boys_kernel=0, pipek_mezey_kernel=0, conditional_NR=0))
                self.assertTrue(receipt['restored_attributes_intact']); self.assertEqual(receipt['status'], 'PASS')
                self.assertFalse(observations)

    def test_zero_science_tasks_deny_every_retained_native_entry(self):
        factories = [lambda m: m['hf'].RHF().kernel(), lambda m: m['hf'].SCF().kernel(),
            lambda m: m['hf'].kernel(m['hf'].RHF()), lambda m: m['uhf'].UHF().kernel(),
            lambda m: m['rohf'].ROHF().kernel(), lambda m: m['rks'].RKS().kernel(),
            lambda m: m['uks'].UKS().kernel(), lambda m: m['roks'].ROKS().kernel(),
            lambda m: m['gto'].Mole().intor(), lambda m: m['gto'].Mole().intor_by_shell(),
            lambda m: m['gto'].Mole().energy_nuc(), lambda m: m['gen_grid'].Grids().build(),
            lambda m: m['numint'].NumInt().nr_rks(), lambda m: m['numint'].nr_rks(),
            lambda m: m['numint'].NumInt().nr_uks(), lambda m: m['numint'].nr_uks(),
            lambda m: m['boys'].Boys().kernel(), lambda m: m['pipek'].PipekMezey().kernel()]
        for task in ('p02-statistics', 'p13-graph-ledger'):
            for index, factory in enumerate(factories):
                with self.subTest(task=task, entry=index):
                    m, observations = modules()
                    with RegisteredNativeGuard(task, engine_modules=m) as guard:
                        with self.assertRaises(RegisteredNativeGuardError): factory(m)
                    receipt = guard.snapshot()
                    self.assertEqual(receipt['status'], 'FAIL'); self.assertEqual(len(receipt['forbidden_attempts']), 1)
                    self.assertTrue(all(count == 0 for count in receipt['counts'].values())); self.assertFalse(observations)

    def test_p01_permits_exact_single_kernels_and_ordinary_integrals(self):
        m, observed = modules()
        with RegisteredNativeGuard('p01-orbital-density', engine_modules=m) as guard:
            self.assertEqual(m['hf'].RHF().kernel(), -1.)
            self.assertEqual(m['boys'].Boys().kernel(), 'occupied-space')
            self.assertEqual(m['pipek'].PipekMezey().kernel(), 'occupied-space')
            m['gto'].Mole().intor(); m['gto'].Mole().intor_by_shell(); m['gto'].Mole().energy_nuc()
        receipt = guard.snapshot()
        self.assertEqual(receipt['status'], 'PASS')
        self.assertEqual(receipt['counts'], dict(scf_kernel=1, boys_kernel=1, pipek_mezey_kernel=1, conditional_NR=0))
        self.assertEqual(observed.count('ordinary_hf_delegate'), 1)
        self.assertTrue(receipt['p01_ordinary_integral_JK_energy_calls_allowed_not_individually_counted'])
        self.assertFalse(receipt['all_quantum_calls_zero_claim'])
        self.assertEqual(receipt['engine_kind'], 'ENGINEERING_FAKE_MODULES')

    def test_second_kernel_refused_without_delegate_or_refund(self):
        for module, klass, counter in (('hf', 'RHF', 'scf_kernel'), ('boys', 'Boys', 'boys_kernel'),
                                      ('pipek', 'PipekMezey', 'pipek_mezey_kernel')):
            with self.subTest(counter=counter):
                m, observations = modules()
                with RegisteredNativeGuard('p01-orbital-density', engine_modules=m) as guard:
                    getattr(m[module], klass)().kernel()
                    with self.assertRaises(RegisteredNativeGuardError): getattr(m[module], klass)().kernel()
                self.assertEqual(guard.snapshot()['counts'][counter], 1)
                self.assertEqual(guard.snapshot()['status'], 'FAIL'); self.assertEqual(len(observations), 1)

    def test_wrong_scf_types_and_dft_grid_nr_refused_for_p01(self):
        factories = [lambda m: m['uhf'].UHF().kernel(), lambda m: m['rohf'].ROHF().kernel(),
            lambda m: m['rks'].RKS().kernel(), lambda m: m['uks'].UKS().kernel(),
            lambda m: m['roks'].ROKS().kernel(), lambda m: m['gen_grid'].Grids().build(),
            lambda m: m['numint'].NumInt().nr_rks(), lambda m: m['numint'].nr_rks(),
            lambda m: m['numint'].NumInt().nr_uks(), lambda m: m['numint'].nr_uks()]
        for index, factory in enumerate(factories):
            with self.subTest(entry=index):
                m, observations = modules()
                with RegisteredNativeGuard('p01-orbital-density', engine_modules=m) as guard:
                    with self.assertRaises(RegisteredNativeGuardError): factory(m)
                self.assertEqual(guard.snapshot()['counts']['conditional_NR'], 0)
                self.assertFalse(observations); self.assertEqual(guard.snapshot()['status'], 'FAIL')

    def test_global_hf_outside_or_wrong_object_inside_rejected(self):
        for inside in (False, True):
            with self.subTest(inside=inside):
                m, observations = modules()
                with RegisteredNativeGuard('p01-orbital-density', engine_modules=m) as guard:
                    instance = m['hf'].RHF()
                    wrong = m['hf'].RHF()
                    if inside: instance.before = lambda: m['hf'].kernel(wrong)
                    with self.assertRaises(RegisteredNativeGuardError):
                        instance.kernel() if inside else m['hf'].kernel(instance)
                self.assertFalse(observations); self.assertEqual(guard.snapshot()['status'], 'FAIL')

    def test_direct_scf_alias_and_localizer_global_alias_are_refused(self):
        for factory in (lambda m: m['hf'].RHF().scf(), lambda m: m['hf'].SCF.scf(m['hf'].RHF()),
                        lambda m: m['boys'].kernel(m['boys'].Boys()),
                        lambda m: m['pipek'].kernel(m['pipek'].PipekMezey()),
                        lambda m: m['uhf'].kernel(m['uhf'].UHF())):
            m, observations = modules()
            with RegisteredNativeGuard('p01-orbital-density', engine_modules=m) as guard:
                with self.assertRaises(RegisteredNativeGuardError): factory(m)
            self.assertFalse(observations); self.assertEqual(guard.snapshot()['status'], 'FAIL')

    def test_subclass_cannot_take_the_exact_rhf_or_boys_allowance(self):
        for key, parent in (('hf', 'RHF'), ('boys', 'Boys')):
            with self.subTest(key=key):
                m, observations = modules()
                subclass = type('UnregisteredSubclass', (getattr(m[key], parent),), {})
                with RegisteredNativeGuard('p01-orbital-density', engine_modules=m) as guard:
                    with self.assertRaises(RegisteredNativeGuardError): subclass().kernel()
                self.assertFalse(observations)

    def test_changed_nr_guard_is_detected_before_allowed_rhf(self):
        m, observations = modules(); original = m['numint'].nr_rks
        with RegisteredNativeGuard('p01-orbital-density', engine_modules=m) as guard:
            m['numint'].nr_rks = lambda: None
            with self.assertRaises(RegisteredNativeGuardError): m['hf'].RHF().kernel()
        receipt = guard.snapshot()
        self.assertIn('numint.nr_rks', receipt['changed_guards']); self.assertEqual(receipt['status'], 'FAIL')
        self.assertIs(m['numint'].nr_rks, original); self.assertFalse(observations)

    def test_inherited_attributes_restored_by_deleting_temporary_overrides(self):
        m, observations = modules()
        original = m['hf'].SCF.kernel
        self.assertNotIn('kernel', vars(m['hf'].RHF)); self.assertNotIn('kernel', vars(m['pipek'].PipekMezey))
        with RegisteredNativeGuard('p01-orbital-density', engine_modules=m):
            self.assertIn('kernel', vars(m['hf'].RHF)); self.assertIn('kernel', vars(m['pipek'].PipekMezey))
            m['hf'].RHF().kernel()
        self.assertNotIn('kernel', vars(m['hf'].RHF)); self.assertNotIn('kernel', vars(m['pipek'].PipekMezey))
        self.assertIs(m['hf'].RHF.kernel, original); self.assertEqual(observations, ['ordinary_hf_delegate'])

    def test_baseexception_propagates_and_originals_restore(self):
        m, observations = modules(); original = m['hf'].SCF.kernel
        with self.assertRaises(KeyboardInterrupt):
            with RegisteredNativeGuard('p01-orbital-density', engine_modules=m) as guard:
                instance = m['hf'].RHF(); instance.fault = KeyboardInterrupt('toy interrupt')
                instance.kernel()
        self.assertEqual(guard.snapshot()['counts']['scf_kernel'], 1)
        self.assertEqual(guard.snapshot()['call_outcomes']['scf_kernel']['failed'], 1)
        self.assertTrue(guard.snapshot()['restored_attributes_intact']); self.assertIs(m['hf'].RHF.kernel, original)

    def test_stop_before_dispatch_has_zero_count_and_no_delegate(self):
        m, observations = modules(); phases = []
        def checkpoint(phase): phases.append(phase); raise TimeoutError('cooperative stop before delegate')
        with RegisteredNativeGuard('p01-orbital-density', engine_modules=m, stop_checkpoint=checkpoint) as guard:
            with self.assertRaises(TimeoutError): m['hf'].RHF().kernel()
        self.assertEqual(guard.snapshot()['counts']['scf_kernel'], 0)
        self.assertEqual(guard.snapshot()['status'], 'PASS'); self.assertFalse(observations)
        self.assertEqual(phases, ['BEFORE_REGISTERED_SCF_KERNEL'])

    def test_stop_after_return_preserves_returned_count_not_native_interruption_claim(self):
        m, observations = modules(); phases = []
        def checkpoint(phase):
            phases.append(phase)
            if phase.startswith('AFTER_'): raise TimeoutError('cooperative stop after delegate return')
        with RegisteredNativeGuard('p01-orbital-density', engine_modules=m, stop_checkpoint=checkpoint) as guard:
            with self.assertRaises(TimeoutError): m['hf'].RHF().kernel()
        self.assertEqual(guard.snapshot()['counts']['scf_kernel'], 1)
        self.assertEqual(guard.snapshot()['call_outcomes']['scf_kernel'], {'returned': 1, 'failed': 0})
        self.assertEqual(observations, ['ordinary_hf_delegate']); self.assertEqual(len(phases), 2)

    def test_stop_callback_identity_cannot_be_replaced(self):
        m, observations = modules()
        with RegisteredNativeGuard('p01-orbital-density', engine_modules=m, stop_checkpoint=lambda phase: None) as guard:
            guard.stop_checkpoint = lambda phase: None
            with self.assertRaises(RegisteredNativeGuardError): m['hf'].RHF().kernel()
        self.assertIn('stop_checkpoint', guard.snapshot()['changed_guards']); self.assertFalse(observations)

    def test_one_use_and_no_nested_guard_context(self):
        m, observations = modules(); guard = RegisteredNativeGuard('p02-statistics', engine_modules=m)
        self.assertEqual(guard.snapshot()['status'], 'NOT_INSTALLED')
        with guard:
            with self.assertRaises(ValueError):
                with RegisteredNativeGuard('p13-graph-ledger', engine_modules=m): pass
        with self.assertRaises(ValueError):
            with guard: pass
        self.assertTrue(guard.snapshot()['restored_attributes_intact'])

    def test_counts_are_readonly_and_closed_snapshot_is_independent_sealed_receipt(self):
        m, observations = modules()
        with RegisteredNativeGuard('p01-orbital-density', engine_modules=m) as guard:
            m['hf'].RHF().kernel()
            with self.assertRaises(TypeError): guard.counts['scf_kernel'] = 0
            with self.assertRaises(AttributeError): guard.counts = {'scf_kernel': 0}
        receipt = guard.snapshot()
        self.assertTrue(receipt['held_at_close']); self.assertTrue(receipt['restored_attributes_intact'])
        receipt['counts']['scf_kernel'] = 999; receipt['guard_operations'].clear()
        self.assertEqual(guard.snapshot()['counts']['scf_kernel'], 1)
        self.assertGreaterEqual(len(guard.snapshot()['guard_operations']), 14)


if __name__ == '__main__': unittest.main()
