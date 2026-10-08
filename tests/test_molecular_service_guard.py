"""Held ordinary-task operation guards using explicit toy modules, no PySCF."""

import copy
import threading
import unittest

from runtime.molecular_service.native_guard import MolecularNativeGuard
from runtime.registered_cases.native_guard import RegisteredNativeGuardError
from tests.test_registered_case_native_guard import modules


class MolecularServiceGuardTests(unittest.TestCase):
    def test_one_ordinary_rhf_and_integral_delegates_are_permitted(self):
        mapping, observations = modules()
        with MolecularNativeGuard(engine_modules=mapping) as guard:
            self.assertEqual(mapping["hf"].RHF().kernel(), -1.0)
            mapping["gto"].Mole().intor()
            mapping["gto"].Mole().intor_by_shell()
            mapping["gto"].Mole().energy_nuc()
        receipt = guard.snapshot()
        self.assertEqual(receipt["schema"], "molecular-service-native-guard-v1")
        self.assertEqual(receipt["task"], "single-point")
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["counts"], {"scf_kernel": 1, "boys_kernel": 0, "pipek_mezey_kernel": 0, "conditional_NR": 0})
        self.assertEqual(receipt["call_outcomes"]["scf_kernel"], {"returned": 1, "failed": 0})
        self.assertTrue(receipt["restored_attributes_intact"])
        self.assertFalse(receipt["all_quantum_calls_zero_claim"])
        self.assertFalse(receipt["p01_ordinary_integral_JK_energy_calls_allowed_not_individually_counted"])
        self.assertTrue(receipt["ordinary_integral_JK_energy_calls_allowed_not_individually_counted"])
        self.assertEqual(receipt["engine_kind"], "ENGINEERING_FAKE_MODULES")
        self.assertEqual(observations.count("ordinary_hf_delegate"), 1)

    def test_empty_guard_is_observed_zero_and_not_a_scientific_success(self):
        mapping, observations = modules()
        with MolecularNativeGuard(engine_modules=mapping) as guard:
            self.assertEqual(guard.snapshot()["counts"]["scf_kernel"], 0)
        receipt = guard.snapshot()
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["counts"]["scf_kernel"], 0)
        self.assertEqual(receipt["engine_kind"], "ENGINEERING_FAKE_MODULES")
        self.assertNotIn("scientific_qualified", receipt)
        self.assertFalse(observations)

    def test_localization_grid_nr_dft_open_shell_and_aliases_are_denied(self):
        factories = [lambda m: m["boys"].Boys().kernel(), lambda m: m["pipek"].PipekMezey().kernel(),
                     lambda m: m["boys"].kernel(m["boys"].Boys()), lambda m: m["pipek"].kernel(m["pipek"].PipekMezey()),
                     lambda m: m["gen_grid"].Grids().build(), lambda m: m["numint"].NumInt().nr_rks(),
                     lambda m: m["numint"].nr_rks(), lambda m: m["numint"].NumInt().nr_uks(),
                     lambda m: m["numint"].nr_uks(), lambda m: m["rks"].RKS().kernel(),
                     lambda m: m["uks"].UKS().kernel(), lambda m: m["roks"].ROKS().kernel(),
                     lambda m: m["uhf"].UHF().kernel(), lambda m: m["rohf"].ROHF().kernel(),
                     lambda m: m["uhf"].kernel(m["uhf"].UHF()), lambda m: m["hf"].SCF().kernel(),
                     lambda m: m["hf"].RHF().scf(), lambda m: m["hf"].kernel(m["hf"].RHF())]
        for index, factory in enumerate(factories):
            with self.subTest(entry=index):
                mapping, observations = modules()
                with MolecularNativeGuard(engine_modules=mapping) as guard:
                    with self.assertRaises(RegisteredNativeGuardError):
                        factory(mapping)
                receipt = guard.snapshot()
                self.assertEqual(receipt["status"], "FAIL")
                self.assertEqual(len(receipt["forbidden_attempts"]), 1)
                self.assertTrue(all(value == 0 for value in receipt["counts"].values()))
                self.assertFalse(observations)
                self.assertTrue(receipt["restored_attributes_intact"])

    def test_second_rhf_never_delegates_or_refunds_first_call(self):
        mapping, observations = modules()
        with MolecularNativeGuard(engine_modules=mapping) as guard:
            mapping["hf"].RHF().kernel()
            with self.assertRaises(RegisteredNativeGuardError):
                mapping["hf"].RHF().kernel()
        receipt = guard.snapshot()
        self.assertEqual(receipt["counts"]["scf_kernel"], 1)
        self.assertEqual(receipt["call_outcomes"]["scf_kernel"], {"returned": 1, "failed": 0})
        self.assertEqual(observations, ["ordinary_hf_delegate"])
        self.assertEqual(receipt["status"], "FAIL")

    def test_failed_kernel_is_charged_and_restore_does_not_claim_convergence(self):
        mapping, observations = modules()
        original = mapping["hf"].RHF.kernel
        with self.assertRaises(KeyboardInterrupt):
            with MolecularNativeGuard(engine_modules=mapping) as guard:
                instance = mapping["hf"].RHF()
                instance.fault = KeyboardInterrupt("engineering fault before fake delegate")
                instance.kernel()
        receipt = guard.snapshot()
        self.assertEqual(receipt["counts"]["scf_kernel"], 1)
        self.assertEqual(receipt["call_outcomes"]["scf_kernel"], {"returned": 0, "failed": 1})
        self.assertTrue(receipt["restored_attributes_intact"])
        self.assertIs(mapping["hf"].RHF.kernel, original)
        self.assertFalse(observations)
        self.assertNotIn("scientific_qualified", receipt)

    def test_guard_tamper_refuses_allowed_operation_and_restores_original(self):
        mapping, observations = modules()
        original = mapping["numint"].nr_rks
        with MolecularNativeGuard(engine_modules=mapping) as guard:
            mapping["numint"].nr_rks = lambda: "unheld"
            with self.assertRaises(RegisteredNativeGuardError):
                mapping["hf"].RHF().kernel()
        receipt = guard.snapshot()
        self.assertIn("numint.nr_rks", receipt["changed_guards"])
        self.assertEqual(receipt["status"], "FAIL")
        self.assertEqual(receipt["counts"]["scf_kernel"], 0)
        self.assertIs(mapping["numint"].nr_rks, original)
        self.assertFalse(observations)

    def test_stop_callback_tamper_cannot_replace_owned_checkpoint(self):
        mapping, observations = modules()
        with MolecularNativeGuard(engine_modules=mapping, stop_checkpoint=lambda phase: None) as guard:
            guard.stop_checkpoint = lambda phase: None
            with self.assertRaises(RegisteredNativeGuardError):
                mapping["hf"].RHF().kernel()
        self.assertIn("stop_checkpoint", guard.snapshot()["changed_guards"])
        self.assertEqual(guard.snapshot()["counts"]["scf_kernel"], 0)
        self.assertFalse(observations)

    def test_cooperative_stop_before_dispatch_charges_zero(self):
        mapping, observations = modules()
        phases = []
        def checkpoint(phase):
            phases.append(phase)
            raise TimeoutError("pre-dispatch cooperative stop")
        with MolecularNativeGuard(engine_modules=mapping, stop_checkpoint=checkpoint) as guard:
            with self.assertRaises(TimeoutError):
                mapping["hf"].RHF().kernel()
        self.assertEqual(guard.snapshot()["counts"]["scf_kernel"], 0)
        self.assertFalse(observations)
        self.assertEqual(phases, ["BEFORE_REGISTERED_SCF_KERNEL"])

    def test_cooperative_stop_after_return_keeps_observed_returned_call(self):
        mapping, observations = modules()
        def checkpoint(phase):
            if phase.startswith("AFTER_"):
                raise TimeoutError("post-return cooperative stop")
        with MolecularNativeGuard(engine_modules=mapping, stop_checkpoint=checkpoint) as guard:
            with self.assertRaises(TimeoutError):
                mapping["hf"].RHF().kernel()
        self.assertEqual(guard.snapshot()["counts"]["scf_kernel"], 1)
        self.assertEqual(guard.snapshot()["call_outcomes"]["scf_kernel"], {"returned": 1, "failed": 0})
        self.assertEqual(observations, ["ordinary_hf_delegate"])

    def test_inherited_bindings_restore_without_leaving_overrides(self):
        mapping, observations = modules()
        original = mapping["hf"].SCF.kernel
        self.assertNotIn("kernel", vars(mapping["hf"].RHF))
        self.assertNotIn("kernel", vars(mapping["pipek"].PipekMezey))
        with MolecularNativeGuard(engine_modules=mapping):
            self.assertIn("kernel", vars(mapping["hf"].RHF))
            self.assertIn("kernel", vars(mapping["pipek"].PipekMezey))
            mapping["hf"].RHF().kernel()
        self.assertNotIn("kernel", vars(mapping["hf"].RHF))
        self.assertNotIn("kernel", vars(mapping["pipek"].PipekMezey))
        self.assertIs(mapping["hf"].RHF.kernel, original)

    def test_closed_receipt_is_sealed_and_returned_mutation_does_not_change_it(self):
        mapping, observations = modules()
        with MolecularNativeGuard(engine_modules=mapping) as guard:
            retained = mapping["hf"].RHF.kernel
            mapping["hf"].RHF().kernel()
        original = guard.snapshot()
        altered = guard.snapshot()
        altered["counts"]["scf_kernel"] = 0
        altered["forbidden_attempts"].append({"fake": True})
        self.assertEqual(guard.snapshot(), original)
        with self.assertRaises(RegisteredNativeGuardError):
            retained(mapping["hf"].RHF())
        self.assertEqual(guard.snapshot(), original)
        self.assertEqual(observations, ["ordinary_hf_delegate"])

    def test_counts_public_view_cannot_be_rewritten(self):
        mapping, observations = modules()
        with MolecularNativeGuard(engine_modules=mapping) as guard:
            with self.assertRaises(TypeError):
                guard.counts["scf_kernel"] = 0
            mapping["hf"].RHF().kernel()
        self.assertEqual(guard.snapshot()["counts"]["scf_kernel"], 1)

    def test_foreign_thread_cannot_consume_owned_scf_allowance(self):
        mapping, observations = modules()
        errors = []
        with MolecularNativeGuard(engine_modules=mapping) as guard:
            def run_foreign():
                try:
                    mapping["hf"].RHF().kernel()
                except BaseException as error:
                    errors.append(error)
            thread = threading.Thread(target=run_foreign)
            thread.start()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RegisteredNativeGuardError)
        self.assertEqual(guard.snapshot()["counts"]["scf_kernel"], 0)
        self.assertEqual(guard.snapshot()["status"], "FAIL")
        self.assertFalse(observations)

    def test_guard_is_one_use_and_nested_guard_is_refused(self):
        mapping, observations = modules()
        outer = MolecularNativeGuard(engine_modules=mapping)
        with outer:
            with self.assertRaises(ValueError):
                with MolecularNativeGuard(engine_modules=mapping):
                    self.fail("nested guard entered")
            mapping["hf"].RHF().kernel()
        with self.assertRaises(ValueError):
            with outer:
                self.fail("reused guard entered")
        self.assertEqual(observations, ["ordinary_hf_delegate"])


if __name__ == "__main__":
    unittest.main()
