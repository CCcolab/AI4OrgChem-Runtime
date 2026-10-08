"""Held-entry audit tests using entirely synthetic Python module objects.

No real PySCF package, integral, grid, SCF, or scientific source is dispatched.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import threading
from types import ModuleType
import unittest
from unittest.mock import patch

from runtime.protocol_cases import native_guard
from runtime.protocol_cases import read_json


class SyntheticEngine:
    def __init__(self):
        self.calls = []
        self.modules = {}
        def module(name):
            value = ModuleType(name)
            self.modules[name] = value
            return value
        root = module("pyscf")
        scf = module("pyscf.scf")
        hf = module("pyscf.scf.hf")
        uhf = module("pyscf.scf.uhf")
        dft = module("pyscf.dft")
        rks = module("pyscf.dft.rks")
        uks = module("pyscf.dft.uks")
        roks = module("pyscf.dft.roks")
        nr = module("pyscf.dft.numint")
        grid = module("pyscf.dft.gen_grid")
        lo = module("pyscf.lo")
        boys = module("pyscf.lo.boys")
        pipek = module("pyscf.lo.pipek")
        gto = module("pyscf.gto")
        soscf = module("pyscf.soscf")
        newton = module("pyscf.soscf.newton_ah")
        def entry(label):
            def function(*args, **kwargs):
                self.calls.append(label)
                return label
            return function
        class RHF: pass
        class UHF: pass
        class KohnShamDFT: pass
        class RKS(RHF, KohnShamDFT): pass
        class BaseSCF:
            kernel = entry("inherited unsupported SCF")
        class UKS(BaseSCF): pass
        class ROKS(BaseSCF): pass
        class Boys:
            kernel = entry("Boys")
        class PipekMezey:
            kernel = entry("PM")
        class Mole:
            intor = entry("integral")
            intor_by_shell = entry("shell integral")
            energy_nuc = entry("nuclear energy")
        class Grids:
            build = entry("grid")
        RKS.stability = entry("stability")
        hf.RHF, uhf.UHF, rks.RKS, rks.KohnShamDFT = RHF, UHF, RKS, KohnShamDFT
        uks.UKS, roks.ROKS, boys.Boys, pipek.PipekMezey = UKS, ROKS, Boys, PipekMezey
        gto.Mole, grid.Grids = Mole, Grids
        hf.kernel, nr.nr_rks, nr.nr_uks = entry("hf kernel"), entry("RKS grid integral"), entry("UKS grid integral")
        class NumInt:
            nr_rks = nr.nr_rks
            nr_uks = nr.nr_uks
        nr.NumInt = NumInt
        newton.kernel = entry("Newton kernel")
        root.scf, root.dft, root.lo, root.gto, root.soscf = scf, dft, lo, gto, soscf
        scf.hf, scf.uhf = hf, uhf
        dft.numint, dft.gen_grid, dft.rks, dft.uks, dft.roks = nr, grid, rks, uks, roks
        lo.boys, lo.pipek, soscf.newton_ah = boys, pipek, newton
        self.source = module("synthetic_protocol_source")
        self.source.__file__ = "C:/synthetic/reference/protocol_cases/source_tree/src/science.py"
        self.original_custom = entry("GL original")
        self.original_custom.__name__ = "run_gl2014_scf"
        self.source.run_gl2014_scf = self.original_custom
        self.alias = module("synthetic_protocol_driver")
        self.alias.imported_gl = self.original_custom
        self.hf, self.nr, self.rks, self.gto, self.uks = hf, nr, rks, gto, uks


class ProtocolGuardTests(unittest.TestCase):
    def setUp(self):
        self.engine = SyntheticEngine()
        self.original_active = native_guard._ACTIVE
        native_guard._ACTIVE = None
        self.modules_patch = patch.dict(sys.modules, self.engine.modules)
        self.modules_patch.start()
        self.addCleanup(self.modules_patch.stop)
        self.addCleanup(setattr, native_guard, "_ACTIVE", self.original_active)

    def test_one_shared_custom_budget_holds_source_and_driver_aliases(self):
        guard = native_guard.ProtocolGuard("P08", "live")
        with guard:
            self.engine.alias.imported_gl()
            with self.assertRaises(native_guard.GuardError):
                self.engine.source.run_gl2014_scf()
        snapshot = guard.snapshot()
        self.assertEqual(snapshot["counts"]["run_gl2014_scf"], 1)
        self.assertEqual(self.engine.calls, ["GL original"])
        self.assertEqual(snapshot["status"], "FAIL")
        self.assertTrue(snapshot["restored_attributes_intact"])
        self.assertIs(self.engine.alias.imported_gl, self.engine.original_custom)
        self.assertIs(self.engine.source.run_gl2014_scf, self.engine.original_custom)

    def test_synthetic_rks_limit_and_classification(self):
        guard = native_guard.ProtocolGuard("P08", "live")
        with guard:
            self.engine.hf.kernel(self.engine.rks.RKS())
            with self.assertRaises(native_guard.GuardError):
                self.engine.hf.kernel(self.engine.rks.RKS())
        self.assertEqual(guard.snapshot()["counts"], {"scf_RKS": 1})
        self.assertEqual(self.engine.calls, ["hf kernel"])

    def test_ledger_refuses_all_synthetic_integral_and_scf_entries(self):
        guard = native_guard.ProtocolGuard("P07", "ledger")
        with guard:
            for call in (lambda: self.engine.hf.kernel(self.engine.rks.RKS()),
                         lambda: self.engine.gto.Mole().intor("int1e_ovlp")):
                with self.assertRaises(native_guard.GuardError):
                    call()
        self.assertEqual(guard.snapshot()["counts"], {})
        self.assertEqual(self.engine.calls, [])

    def test_original_exception_charges_once_and_restores(self):
        def failure(*args, **kwargs):
            raise RuntimeError("synthetic delegate failure")
        failure.__name__ = "run_gl2014_scf"
        self.engine.source.run_gl2014_scf = failure
        self.engine.alias.imported_gl = failure
        guard = native_guard.ProtocolGuard("P08", "live")
        with self.assertRaisesRegex(RuntimeError, "delegate failure"):
            with guard:
                self.engine.source.run_gl2014_scf()
        audit = guard.snapshot()
        self.assertEqual(audit["counts"]["run_gl2014_scf"], 1)
        self.assertEqual(audit["outcomes"]["run_gl2014_scf"], {"returned": 0, "failed": 1})
        self.assertTrue(audit["restored_attributes_intact"])

    def test_changed_binding_refuses_before_delegate_and_restores(self):
        guard = native_guard.ProtocolGuard("P08", "live")
        with self.assertRaises(native_guard.GuardError):
            with guard:
                held = self.engine.source.run_gl2014_scf
                self.engine.source.run_gl2014_scf = lambda: None
                with self.assertRaises(native_guard.GuardError):
                    held()
        self.assertEqual(self.engine.calls, [])
        self.assertTrue(guard.snapshot()["restored_attributes_intact"])
        self.assertEqual(guard.snapshot()["status"], "FAIL")

    def test_foreign_thread_denial_is_visible_in_final_audit(self):
        errors = []
        guard = native_guard.ProtocolGuard("P08", "live")
        with guard:
            def attempt():
                try:
                    self.engine.source.run_gl2014_scf()
                except Exception as error:
                    errors.append(error)
            thread = threading.Thread(target=attempt)
            thread.start()
            thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], native_guard.GuardError)
        self.assertEqual(self.engine.calls, [])
        self.assertEqual(guard.snapshot()["status"], "FAIL")

    def test_checkpoint_binding_mutation_prevents_original_dispatch(self):
        def checkpoint(phase):
            if phase.startswith("PROTOCOL_BEFORE_"):
                self.engine.source.run_gl2014_scf = lambda: None
        guard = native_guard.ProtocolGuard("P08", "live", checkpoint=checkpoint)
        with self.assertRaises(native_guard.GuardError):
            with guard:
                self.engine.source.run_gl2014_scf()
        self.assertEqual(self.engine.calls, [])
        self.assertEqual(guard.snapshot()["counts"].get("run_gl2014_scf", 0), 0)
        self.assertTrue(guard.snapshot()["restored_attributes_intact"])

    def test_post_checkpoint_exception_does_not_double_charge_outcomes(self):
        def checkpoint(phase):
            if phase.startswith("PROTOCOL_AFTER_"):
                raise RuntimeError("synthetic post checkpoint failure")
        guard = native_guard.ProtocolGuard("P08", "live", checkpoint=checkpoint)
        with self.assertRaisesRegex(RuntimeError, "post checkpoint"):
            with guard:
                self.engine.source.run_gl2014_scf()
        snapshot = guard.snapshot()
        self.assertEqual(snapshot["counts"]["run_gl2014_scf"], 1)
        self.assertEqual(sum(snapshot["outcomes"]["run_gl2014_scf"].values()), 1)
        self.assertTrue(snapshot["restored_attributes_intact"])

    def test_direct_numint_uks_alias_cannot_bypass_denial(self):
        guard = native_guard.ProtocolGuard("P07", "ledger")
        with guard:
            with self.assertRaises(native_guard.GuardError):
                self.engine.nr.NumInt().nr_uks()
        self.assertEqual(self.engine.calls, [])

    def test_inherited_entries_restored_without_new_attributes(self):
        original = self.engine.uks.UKS.kernel
        self.assertNotIn("kernel", vars(self.engine.uks.UKS))
        guard = native_guard.ProtocolGuard("P08", "live")
        with guard:
            self.assertIn("kernel", vars(self.engine.uks.UKS))
        self.assertNotIn("kernel", vars(self.engine.uks.UKS))
        self.assertIs(self.engine.uks.UKS.kernel, original)
        self.assertTrue(guard.snapshot()["restored_attributes_intact"])

    def test_nested_and_reused_contexts_are_refused(self):
        guard = native_guard.ProtocolGuard("P08", "live")
        with guard:
            with self.assertRaises(native_guard.GuardError):
                with native_guard.ProtocolGuard("P08", "live"):
                    pass
        with self.assertRaises(native_guard.GuardError):
            with guard:
                pass

    def test_restore_exception_does_not_leave_global_guard_active(self):
        original = self.engine.original_custom
        class RefuseRestore(ModuleType):
            def __setattr__(instance, name, value):
                if (name == "run_gl2014_scf" and getattr(instance, "refuse_restore", False)
                        and value is original):
                    raise RuntimeError("synthetic attribute restoration failure")
                super().__setattr__(name, value)
        source = RefuseRestore("synthetic_restore_source")
        source.__file__ = self.engine.source.__file__
        source.original = self.engine.original_custom
        source.run_gl2014_scf = source.original
        self.engine.modules[source.__name__] = source
        with patch.dict(sys.modules, {source.__name__: source}):
            guard = native_guard.ProtocolGuard("P08", "live")
            with self.assertRaises(Exception):
                with guard:
                    source.refuse_restore = True
            self.assertIsNone(native_guard._ACTIVE)
            self.assertFalse(guard.active)
            self.assertTrue(guard.closed)
            self.assertIs(self.engine.source.run_gl2014_scf, self.engine.original_custom)


class ProtocolStrictJSONTests(unittest.TestCase):
    def test_overflow_exponent_is_rejected_as_nonfinite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text('{"nested":{"number":1e999}}', encoding="utf-8")
            with self.assertRaises(ValueError):
                read_json(path)

    def test_literals_and_duplicate_keys_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for text in ('{"x":NaN}', '{"x":Infinity}', '{"x":1,"x":2}'):
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    read_json(path)


if __name__ == "__main__":
    unittest.main()
