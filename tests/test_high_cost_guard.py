"""Synthetic third-batch dispatch witnesses; no real scientific libraries."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import threading
from types import ModuleType
import unittest
from unittest.mock import patch

from runtime.high_cost_cases import native_guard


class SyntheticEngine:
    def __init__(self):
        self.calls, self.modules = [], {}
        def module(name):
            result = ModuleType(name); self.modules[name] = result
            return result
        def entry(label):
            def call(*args, **kwargs):
                self.calls.append(label)
                return label
            return call
        self.root = module("pyscf")
        scf = module("pyscf.scf"); self.hf = module("pyscf.scf.hf"); uhf = module("pyscf.scf.uhf")
        dft = module("pyscf.dft"); self.rks = module("pyscf.dft.rks")
        uks = module("pyscf.dft.uks"); roks = module("pyscf.dft.roks")
        self.nr = module("pyscf.dft.numint"); grid = module("pyscf.dft.gen_grid")
        grad = module("pyscf.grad"); self.rks_grad = module("pyscf.grad.rks"); rhf_grad = module("pyscf.grad.rhf")
        self.gto = module("pyscf.gto")
        geomopt = module("pyscf.geomopt"); self.geometric = module("pyscf.geomopt.geometric_solver")
        scipy = module("scipy"); self.optimize = module("scipy.optimize")
        cc = module("pyscf.cc"); self.posthf = module("pyscf.cc.synthetic")
        df = module("pyscf.df"); self.density_fit = module("pyscf.df.df")
        for name in ("pyscf.mp", "pyscf.ci", "pyscf.mcscf", "pyscf.lo", "pyscf.soscf"):
            module(name)
        engine = self
        class SCF:
            def kernel(instance):
                return engine.hf.kernel(instance)
            scf = kernel
        class RHF(SCF): pass
        class UHF(SCF): pass
        class HF1e(UHF):
            scf = entry("one-electron HF")
        class RKS(RHF):
            def nuc_grad_method(instance):
                return engine.rks_grad.Gradients(instance)
        class UKS(UHF): pass
        class ROKS(RHF): pass
        class GradientsBase:
            def __init__(instance, base):
                instance.base = base
            kernel = entry("gradient terminal")
        class RHFGradients(GradientsBase): pass
        class RKSGradients(RHFGradients): pass
        class Mole:
            build = entry("Mole build")
            intor = entry("integral")
            intor_by_shell = entry("shell integral")
            energy_nuc = entry("nuclear energy")
        class Grids:
            build = entry("grid")
        class DF:
            kernel = entry("density fitting")
        for cls, namespace in ((SCF, "pyscf.scf.hf"), (RHF, "pyscf.scf.hf"),
                               (UHF, "pyscf.scf.uhf"), (HF1e, "pyscf.scf.uhf"),
                               (RKS, "pyscf.dft.rks"), (UKS, "pyscf.dft.uks"),
                               (ROKS, "pyscf.dft.roks"), (GradientsBase, "pyscf.grad.rhf"),
                               (RHFGradients, "pyscf.grad.rhf"), (RKSGradients, "pyscf.grad.rks"),
                               (DF, "pyscf.df.df")):
            cls.__module__ = namespace
        self.hf.SCF, self.hf.RHF, uhf.UHF, uhf.HF1e = SCF, RHF, UHF, HF1e
        self.rks.RKS, uks.UKS, roks.ROKS = RKS, UKS, ROKS
        self.rks_grad.Gradients = RKSGradients
        rhf_grad.Gradients, rhf_grad.GradientsBase = RHFGradients, GradientsBase
        self.gto.Mole, grid.Grids, self.density_fit.DF = Mole, Grids, DF
        self.hf.kernel, uhf._hf1e_scf = entry("SCF terminal"), entry("HF1e helper")
        self.nr.nr_rks, self.nr.nr_uks = entry("RKS numerical integration"), entry("UKS numerical integration")
        class NumInt:
            nr_rks = self.nr.nr_rks
            nr_uks = self.nr.nr_uks
        self.nr.NumInt = NumInt
        self.optimize.minimize = lambda objective, *args, **kwargs: objective()
        self.optimize.least_squares = entry("other optimizer")
        def geometry_kernel(mean_field, *args, **kwargs):
            mean_field.kernel()
            mean_field.nuc_grad_method().kernel()
            return "geometry returned"
        self.geometric.kernel = geometry_kernel
        self.geometric.optimize = entry("geometric alternate entry")
        self.posthf.kernel = entry("postHF")
        self.root.scf, self.root.dft, self.root.grad, self.root.gto = scf, dft, grad, self.gto
        self.root.geomopt, self.root.cc, self.root.df = geomopt, cc, df
        scf.hf, scf.uhf = self.hf, uhf
        dft.rks, dft.uks, dft.roks, dft.numint, dft.gen_grid = self.rks, uks, roks, self.nr, grid
        grad.rks, grad.rhf = self.rks_grad, rhf_grad
        geomopt.geometric_solver, scipy.optimize, cc.synthetic, df.df = self.geometric, self.optimize, self.posthf, self.density_fit
        self.source2007 = self.source_factory(module, "source2007")
        self.source2011 = self.source_factory(module, "source2011")
        self.source_p09 = module("ai4orgchem.qm.p09_conditional_scf")
        self.source_p09.__file__ = "C:/fake/reference/high_cost_cases/source_tree/src/ai4orgchem/qm/p09_conditional_scf.py"
        self.source_p09._nr = self.nr
        exec(compile("def run_p09_conditional_rks(mean_field=None, descriptors=(), *, eri_classes=None, mask_one_electron_matrix=True, **kwargs):\n    return _nr.nr_rks()\n",
                     self.source_p09.__file__, "exec"), self.source_p09.__dict__)
        self.furan = module("synthetic_furan_driver")
        self.furan.__file__ = "C:/fake/reference/high_cost_cases/source_tree/scripts/run_p11_furan_lde.py"
        self.furan.run_p09_conditional_rks = self.source_p09.run_p09_conditional_rks
        exec(compile("def objective():\n    return 'fake objective'\ndef run():\n    return 'fake source driver'\n",
                     self.furan.__file__, "exec"), self.furan.__dict__)
        self.unrelated = module("synthetic_unrelated_source")
        self.unrelated.__file__ = "C:/fake/reference/high_cost_cases/source_tree/scripts/run_unrelated_source.py"
        exec(compile("def run_one():\n    return 'must never return'\n",
                     self.unrelated.__file__, "exec"), self.unrelated.__dict__)
        self.alias = module("synthetic_furan_alias")
        self.alias.imported_conditional = self.source_p09.run_p09_conditional_rks
        self.cyano = module("scripts.run_p11_cyanobenzene_effect")
        self.cyano.__file__ = "C:/fake/reference/high_cost_cases/source_tree/scripts/run_p11_cyanobenzene_effect.py"
        # A deliberately small fake caller with the original call shape. No
        # NumPy, coordinate fitting, PySCF or SciPy implementation is executed.
        code = ("def reconstruct_ring(target_lengths, overrides=None, residual_override=None, initial_override=None):\n"
                "    from scipy.optimize import least_squares\n"
                "    target = target_lengths\n"
                "    initial = [[0., 0.], [1.4, 0.], [2.1, -1.2], [1.4, -2.4], [0., -2.4], [-.7, -1.2]]\n"
                "    def residuals(variables):\n"
                "        return variables\n"
                "    options = dict(method='trf', ftol=1.0e-14, xtol=1.0e-14, gtol=1.0e-14, max_nfev=5000)\n"
                "    options.update(overrides or {})\n"
                "    x0 = [value for row in initial[2:] for value in row] if initial_override is None else initial_override\n"
                "    return least_squares(residuals if residual_override is None else residual_override, x0, **options)\n")
        exec(compile(code, self.cyano.__file__, "exec"), self.cyano.__dict__)

    def source_factory(self, module, operator):
        filename = "p11_source2007_rks" if operator == "source2007" else "p12_source2011_rks"
        factory = "Source2007ConditionalRKS" if operator == "source2007" else "Source2011DirectConditionalRKS"
        result = module("ai4orgchem.qm." + filename)
        result.__file__ = "C:/fake/reference/high_cost_cases/source_tree/src/ai4orgchem/qm/" + filename + ".py"
        result._RKSBase, result._GradBase = self.rks.RKS, self.rks_grad.Gradients
        code = ("class " + factory + ":\n"
                "    @staticmethod\n"
                "    def build(molecule=None, descriptors=()):\n"
                "        class _Gradients(_GradBase):\n"
                "            def get_ovlp(self):\n"
                "                return 'fake source overlap gradient'\n"
                "        class _RKS(_RKSBase):\n"
                "            def get_fock(self):\n"
                "                return 'fake source Fock'\n"
                "            def nuc_grad_method(self):\n"
                "                return _Gradients(self)\n"
                "        return _RKS()\n")
        exec(compile(code, result.__file__, "exec"), result.__dict__)
        result.factory = getattr(result, factory)
        return result


def unit(operator="ordinary_rks", optimizer="geometric", cap=10):
    if operator == "source2011":
        identity = {"id": "P12-N16-GE-g01-g02", "case": "P12"}
    elif operator == "furan_p09" or optimizer == "scipy_minimize":
        identity = {"id": "P11A-furan-GL", "case": "P11", "subcase": "P11-A"}
    else:
        identity = {"id": "P11B-benzene-G", "case": "P11", "subcase": "P11-B"}
    return {**identity, "method_id": "B3LYPG/6-311g(2df,p)", "operator_id": operator,
            "optimizer": optimizer, "caps": dict.fromkeys(("scf", "gradient", "numint", "grids", "conditional"), cap)}


def metadata_unit(case="P11"):
    return {"id": case + "-metadata", "case": case, "operator_id": "ordinary_rks", "optimizer": "none",
            "caps": dict.fromkeys(("scf", "gradient", "numint", "grids", "conditional"), 0)}


def cyano_unit():
    configuration = unit("source2007")
    configuration.update(id="P11B-cyanobenzene-GE1", system="cyanobenzene")
    return configuration


class HighCostGuardTests(unittest.TestCase):
    def setUp(self):
        self.engine = SyntheticEngine()
        self.previous = native_guard._ACTIVE; native_guard._ACTIVE = None
        self.modules = patch.dict(sys.modules, self.engine.modules)
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.addCleanup(setattr, native_guard, "_ACTIVE", self.previous)

    def test_ordinary_optimizer_counts_terminal_scf_and_gradient_once(self):
        guard = native_guard.HighCostGuard(unit(), "live")
        with guard:
            self.engine.geometric.kernel(self.engine.rks.RKS())
        audit = guard.snapshot()
        self.assertEqual(audit["counts"], {"optimizer": 1, "scf": 1, "gradient": 1})
        self.assertEqual(audit["operator_counts"], {"optimizer:ordinary_rks": 1, "scf:ordinary_rks": 1, "gradient:ordinary_rks": 1})
        self.assertEqual(audit["status"], "PASS")
        self.assertTrue(audit["closed"])
        self.assertTrue(audit["restored_attributes_intact"])

    def test_selected_source_type_and_analytic_gradient_are_identified(self):
        for operator, module in (("source2007", self.engine.source2007), ("source2011", self.engine.source2011)):
            with self.subTest(operator=operator):
                guard = native_guard.HighCostGuard(unit(operator), "live")
                with guard:
                    mean_field = module.factory.build()
                    self.engine.rks.RKS().kernel()  # Fixed ordinary initialization.
                    self.engine.geometric.kernel(mean_field)
                audit = guard.snapshot()
                self.assertEqual(audit["counts"]["scf"], 2)
                self.assertEqual(audit["operator_counts"]["scf:" + operator], 1)
                self.assertEqual(audit["operator_counts"]["gradient:" + operator], 1)
                self.assertEqual(audit["status"], "PASS")

    def test_wrong_source_factory_and_wrong_existing_type_are_refused(self):
        wrong = self.engine.source2011.factory.build()
        guard = native_guard.HighCostGuard(unit("source2007"), "live")
        with guard:
            with self.assertRaises(native_guard.GuardError):
                self.engine.source2011.factory.build()
            with self.assertRaises(native_guard.GuardError):
                wrong.kernel()
        self.assertEqual(self.engine.calls, [])
        self.assertEqual(guard.snapshot()["counts"], {})

    def test_gradient_must_match_mean_field_source_type(self):
        first = self.engine.source2007.factory.build()
        wrong_gradient = self.engine.source2011.factory.build().nuc_grad_method()
        wrong_gradient.base = first
        guard = native_guard.HighCostGuard(unit("source2007"), "live")
        with guard:
            with self.assertRaises(native_guard.GuardError):
                wrong_gradient.kernel()
        self.assertEqual(self.engine.calls, [])

    def test_descriptor_attribute_or_arbitrary_rks_subclass_cannot_impersonate_source(self):
        class Spoof(self.engine.rks.RKS): pass
        spoof = Spoof(); spoof.source2007_descriptors = ()
        guard = native_guard.HighCostGuard(unit("source2007"), "live")
        with guard:
            with self.assertRaises(native_guard.GuardError):
                spoof.kernel()
        self.assertEqual(self.engine.calls, [])

    def test_metadata_modes_block_all_scientific_terminals_and_optimizer(self):
        for mode in ("ledger", "preflight"):
            with self.subTest(mode=mode):
                mean_field = self.engine.rks.RKS()
                guard = native_guard.HighCostGuard(unit(), mode)
                with guard:
                    calls = (lambda: mean_field.kernel(), lambda: mean_field.nuc_grad_method().kernel(),
                             lambda: self.engine.nr.NumInt().nr_rks(), lambda: self.engine.gto.Mole().intor(),
                             lambda: self.engine.gto.Mole().intor_by_shell(), lambda: self.engine.gto.Mole().energy_nuc(),
                             lambda: self.engine.geometric.kernel(mean_field), lambda: self.engine.optimize.minimize(self.engine.furan.objective),
                             lambda: self.engine.source_p09.run_p09_conditional_rks())
                    for call in calls:
                        with self.assertRaises(native_guard.GuardError):
                            call()
                    if mode == "preflight":
                        self.engine.gto.Mole().build()
                    else:
                        with self.assertRaises(native_guard.GuardError):
                            self.engine.gto.Mole().build()
                self.assertEqual(guard.snapshot()["counts"], {})
        self.assertEqual(self.engine.calls, ["Mole build"])

    def test_metadata_none_optimizer_still_holds_geometric_terminal(self):
        guard = native_guard.HighCostGuard(metadata_unit(), "preflight")
        with guard:
            with self.assertRaises(native_guard.GuardError):
                self.engine.geometric.kernel(self.engine.rks.RKS())
        self.assertIn("geometric_solver.kernel", guard.snapshot()["held_entries"])
        self.assertEqual(guard.snapshot()["counts"], {})
        self.assertEqual(self.engine.calls, [])

    def test_metadata_imports_missing_solver_before_guard_activation(self):
        sys.modules.pop("pyscf.geomopt.geometric_solver")
        imported = []
        original_import = native_guard.importlib.import_module
        def import_solver(name, *args, **kwargs):
            imported.append(name)
            if name == "pyscf.geomopt.geometric_solver":
                sys.modules[name] = self.engine.geometric
                return self.engine.geometric
            return original_import(name, *args, **kwargs)
        guard = native_guard.HighCostGuard(metadata_unit(), "ledger")
        with patch.object(native_guard.importlib, "import_module", side_effect=import_solver), guard:
            self.assertIn("pyscf.geomopt.geometric_solver", imported)
        self.assertIn("geometric_solver.kernel", guard.snapshot()["held_entries"])

    def test_missing_real_solver_dependency_is_not_a_metadata_fallback(self):
        sys.modules.pop("pyscf.geomopt.geometric_solver")
        def missing(name, *args, **kwargs):
            raise ModuleNotFoundError("fake missing dependency " + name)
        guard = native_guard.HighCostGuard(metadata_unit(), "preflight")
        with patch.object(native_guard.importlib, "import_module", side_effect=missing):
            with self.assertRaisesRegex(native_guard.GuardError, "MODULE_NOT_PREPARED"):
                with guard:
                    pass
        self.assertIsNone(native_guard._ACTIVE)
        self.assertFalse(guard.active)

    def test_p11_metadata_coordinate_reconstruction_has_separate_counts(self):
        for mode in ("ledger", "preflight"):
            with self.subTest(mode=mode):
                guard = native_guard.HighCostGuard(metadata_unit(), mode)
                with guard:
                    for _ in range(10):
                        self.engine.cyano.reconstruct_ring([1.4] * 6)
                audit = guard.snapshot()
                self.assertEqual(audit["counts"], {})
                self.assertEqual(audit["engineering_counts"], {"coordinate_reconstruction": 10})
                self.assertEqual(audit["engineering_caps"], {"coordinate_reconstruction": 64})
                self.assertEqual(audit["engineering_outcomes"]["coordinate_reconstruction"], {"returned": 10, "failed": 0})
                self.assertEqual(audit["status"], "PASS")

    def test_cyano_coordinate_cap_four_is_independent_of_qm_optimizer(self):
        guard = native_guard.HighCostGuard(cyano_unit(), "live")
        with guard:
            for _ in range(4):
                self.engine.cyano.reconstruct_ring([1.4] * 6)
            with self.assertRaises(native_guard.GuardError):
                self.engine.cyano.reconstruct_ring([1.4] * 6)
        self.assertEqual(guard.snapshot()["counts"], {})
        self.assertEqual(guard.snapshot()["engineering_counts"], {"coordinate_reconstruction": 4})
        self.assertEqual(guard.snapshot()["caps"]["optimizer"], 1)

    def test_p11_metadata_coordinate_allowance_stops_at_sixty_four(self):
        guard = native_guard.HighCostGuard(metadata_unit(), "preflight")
        with guard:
            for _ in range(64):
                self.engine.cyano.reconstruct_ring([1.4] * 6)
            with self.assertRaises(native_guard.GuardError):
                self.engine.cyano.reconstruct_ring([1.4] * 6)
        self.assertEqual(guard.snapshot()["engineering_counts"], {"coordinate_reconstruction": 64})
        self.assertEqual(guard.snapshot()["counts"], {})

    def test_coordinate_exception_refuses_furan_benzene_and_p12(self):
        for configuration in (unit("furan_p09", "scipy_minimize"), unit(), unit("source2011"), metadata_unit("P12")):
            with self.subTest(configuration=configuration):
                guard = native_guard.HighCostGuard(configuration, "preflight")
                with guard:
                    with self.assertRaises(native_guard.GuardError):
                        self.engine.cyano.reconstruct_ring([1.4] * 6)
                self.assertEqual(guard.snapshot()["engineering_counts"], {})
        self.assertEqual(self.engine.calls, [])

    def test_coordinate_fit_requires_direct_frozen_caller_and_residual(self):
        guard = native_guard.HighCostGuard(metadata_unit(), "preflight")
        with guard:
            with self.assertRaises(native_guard.GuardError):
                self.engine.optimize.least_squares(lambda x: x, [1.] * 8,
                    method="trf", ftol=1.0e-14, xtol=1.0e-14, gtol=1.0e-14, max_nfev=5000)
            with self.assertRaises(native_guard.GuardError):
                self.engine.cyano.reconstruct_ring([1.4] * 6, residual_override=lambda x: x)
        self.assertEqual(guard.snapshot()["engineering_counts"], {})
        self.assertEqual(self.engine.calls, [])

    def test_coordinate_fitting_cannot_change_original_solver_parameters(self):
        guard = native_guard.HighCostGuard(metadata_unit(), "preflight")
        with guard:
            for change in ({"method": "lm"}, {"max_nfev": 5001}, {"ftol": 1.0e-8},
                           {"gtol": True}, {"jac": "3-point"}):
                with self.subTest(change=change), self.assertRaises(native_guard.GuardError):
                    self.engine.cyano.reconstruct_ring([1.4] * 6, overrides=change)
        self.assertEqual(guard.snapshot()["engineering_counts"], {})
        self.assertEqual(self.engine.calls, [])

    def test_coordinate_fitting_requires_original_finite_initial_shape(self):
        guard = native_guard.HighCostGuard(metadata_unit(), "preflight")
        with guard:
            for initial in ([1.] * 7, [1.] * 8, [float("nan")] * 8):
                with self.subTest(initial=initial), self.assertRaises(native_guard.GuardError):
                    self.engine.cyano.reconstruct_ring([1.4] * 6, initial_override=initial)
            with self.assertRaises(native_guard.GuardError):
                self.engine.cyano.reconstruct_ring([float("nan")] * 6)
        self.assertEqual(guard.snapshot()["engineering_counts"], {})
        self.assertEqual(self.engine.calls, [])

    def test_missing_coordinate_source_is_explicit_and_refused(self):
        sys.modules.pop("scripts.run_p11_cyanobenzene_effect")
        guard = native_guard.HighCostGuard(metadata_unit(), "preflight")
        with guard:
            with self.assertRaises(native_guard.GuardError):
                self.engine.cyano.reconstruct_ring([1.4] * 6)
        self.assertEqual(guard.snapshot()["coordinate_source_status"], "MODULE_NOT_PREPARED")
        self.assertEqual(guard.snapshot()["engineering_counts"], {})

    def test_coordinate_exception_does_not_allow_a_quantum_kernel_in_metadata(self):
        def unexpected(*args, **kwargs):
            self.engine.rks.RKS().kernel()
        self.engine.optimize.least_squares = unexpected
        guard = native_guard.HighCostGuard(metadata_unit(), "preflight")
        with guard:
            with self.assertRaises(native_guard.GuardError):
                self.engine.cyano.reconstruct_ring([1.4] * 6)
        audit = guard.snapshot()
        self.assertEqual(audit["counts"], {})
        self.assertEqual(audit["engineering_counts"], {"coordinate_reconstruction": 1})
        self.assertEqual(audit["engineering_outcomes"]["coordinate_reconstruction"], {"returned": 0, "failed": 1})
        self.assertEqual(self.engine.calls, [])

    def test_generic_hf_df_posthf_uks_and_other_source_are_denied(self):
        guard = native_guard.HighCostGuard(unit(), "live")
        with guard:
            for call in (lambda: self.engine.hf.RHF().kernel(), lambda: self.engine.root.scf.uhf.UHF().kernel(),
                         lambda: self.engine.root.dft.uks.UKS().kernel(), lambda: self.engine.root.dft.roks.ROKS().kernel(),
                         lambda: self.engine.nr.NumInt().nr_uks(), lambda: self.engine.density_fit.DF().kernel(),
                         lambda: self.engine.posthf.kernel(), lambda: self.engine.unrelated.run_one(),
                         lambda: self.engine.furan.run()):
                with self.assertRaises(native_guard.GuardError):
                    call()
        self.assertEqual(self.engine.calls, [])
        self.assertTrue(guard.snapshot()["restored_attributes_intact"])

    def test_furan_custom_source_aliases_share_one_conditional_cap(self):
        configuration = unit("furan_p09", "scipy_minimize")
        configuration["caps"]["conditional"] = 1
        original = self.engine.source_p09.run_p09_conditional_rks
        guard = native_guard.HighCostGuard(configuration, "live")
        with guard:
            self.engine.alias.imported_conditional()
            with self.assertRaises(native_guard.GuardError):
                self.engine.furan.run_p09_conditional_rks()
        audit = guard.snapshot()
        self.assertEqual(audit["counts"], {"conditional": 1, "numint": 1})
        self.assertIs(self.engine.source_p09.run_p09_conditional_rks, original)
        self.assertIs(self.engine.alias.imported_conditional, original)

    def test_furan_custom_cannot_use_source2007_initializer_matrix_rule(self):
        guard = native_guard.HighCostGuard(unit("furan_p09", "scipy_minimize"), "live")
        with guard:
            with self.assertRaises(native_guard.GuardError):
                self.engine.source_p09.run_p09_conditional_rks(eri_classes=[], mask_one_electron_matrix=False)
        self.assertEqual(guard.snapshot()["counts"], {})
        self.assertEqual(self.engine.calls, [])

    def test_one_frozen_furan_optimizer_and_objective_only(self):
        guard = native_guard.HighCostGuard(unit("furan_p09", "scipy_minimize"), "live")
        with guard:
            self.assertEqual(self.engine.optimize.minimize(self.engine.furan.objective), "fake objective")
            with self.assertRaises(native_guard.GuardError):
                self.engine.optimize.minimize(self.engine.furan.objective)
            with self.assertRaises(native_guard.GuardError):
                self.engine.optimize.least_squares(lambda: None)
        self.assertEqual(guard.snapshot()["counts"], {"optimizer": 1})

    def test_only_seven_cyanobenzene_states_accept_one_fixed_gl_initializer(self):
        configuration = unit("source2007")
        configuration["id"] = "P11B-cyanobenzene-GE4"
        configuration["caps"]["conditional"] = 1
        guard = native_guard.HighCostGuard(configuration, "live")
        with guard:
            self.engine.source_p09.run_p09_conditional_rks(eri_classes=[], mask_one_electron_matrix=False)
            with self.assertRaises(native_guard.GuardError):
                self.engine.source_p09.run_p09_conditional_rks(eri_classes=[], mask_one_electron_matrix=False)
        audit = guard.snapshot()
        self.assertEqual(audit["counts"]["conditional"], 1)
        self.assertEqual(audit["operator_counts"]["conditional:SOURCE2007_FIXED_GL_INITIALIZER"], 1)
        for identifier in ("P11B-benzene-GE1", "P11B-cyanobenzene-GL_I", "P11B-cyanobenzene-GE8"):
            configuration["id"] = identifier
            guard = native_guard.HighCostGuard(configuration, "live")
            with guard:
                with self.assertRaises(native_guard.GuardError):
                    self.engine.source_p09.run_p09_conditional_rks(eri_classes=[], mask_one_electron_matrix=False)
            self.assertEqual(guard.snapshot()["counts"], {})

    def test_source2007_initializer_cannot_change_mask_or_exchange_rule(self):
        configuration = unit("source2007")
        configuration["id"] = "P11B-cyanobenzene-GE1"
        guard = native_guard.HighCostGuard(configuration, "live")
        with guard:
            for options in ({"eri_classes": [], "mask_one_electron_matrix": True},
                            {"eri_classes": ["X14"], "mask_one_electron_matrix": False},
                            {"eri_classes": (), "mask_one_electron_matrix": False},
                            {"eri_classes": []}):
                with self.subTest(options=options), self.assertRaises(native_guard.GuardError):
                    self.engine.source_p09.run_p09_conditional_rks(**options)
        self.assertEqual(guard.snapshot()["counts"], {})
        self.assertEqual(self.engine.calls, [])

    def test_source2007_initializer_cannot_run_after_conditional_scf(self):
        configuration = unit("source2007")
        configuration["id"] = "P11B-cyanobenzene-GE7"
        guard = native_guard.HighCostGuard(configuration, "live")
        with guard:
            self.engine.source2007.factory.build().kernel()
            with self.assertRaises(native_guard.GuardError):
                self.engine.source_p09.run_p09_conditional_rks(eri_classes=[], mask_one_electron_matrix=False)
        self.assertEqual(guard.snapshot()["counts"], {"scf": 1})

    def test_unregistered_objective_is_denied_before_optimizer_charge(self):
        guard = native_guard.HighCostGuard(unit("furan_p09", "scipy_minimize"), "live")
        with guard:
            with self.assertRaises(native_guard.GuardError):
                self.engine.optimize.minimize(lambda: "wrong")
        self.assertEqual(guard.snapshot()["counts"], {})

    def test_variable_scf_count_has_cap_but_no_exact_total_requirement(self):
        configuration = unit(cap=2)
        guard = native_guard.HighCostGuard(configuration, "live")
        with guard:
            self.engine.rks.RKS().kernel()
        self.assertEqual(guard.snapshot()["status"], "PASS")
        guard = native_guard.HighCostGuard(configuration, "live")
        with guard:
            self.engine.rks.RKS().kernel(); self.engine.rks.RKS().kernel()
            with self.assertRaises(native_guard.GuardError):
                self.engine.rks.RKS().kernel()
        self.assertEqual(guard.snapshot()["counts"]["scf"], 2)

    def test_original_failure_is_charged_once_and_restored(self):
        def failure(*args, **kwargs):
            raise RuntimeError("fake native terminal failure")
        self.engine.hf.kernel = failure
        guard = native_guard.HighCostGuard(unit(), "live")
        with self.assertRaisesRegex(RuntimeError, "fake native"), guard:
            self.engine.rks.RKS().kernel()
        audit = guard.snapshot()
        self.assertEqual(audit["outcomes"]["scf"], {"returned": 0, "failed": 1})
        self.assertTrue(audit["restored_attributes_intact"])
        self.assertIs(self.engine.hf.kernel, failure)

    def test_pre_dispatch_stop_does_not_charge_or_call_delegate(self):
        def stop(phase):
            self.assertIsInstance(phase, str)
            raise RuntimeError("fake cooperative stop")
        guard = native_guard.HighCostGuard(unit(), "live", checkpoint=stop)
        with self.assertRaisesRegex(RuntimeError, "cooperative stop"), guard:
            self.engine.rks.RKS().kernel()
        self.assertEqual(guard.snapshot()["counts"], {})
        self.assertEqual(self.engine.calls, [])

    def test_post_dispatch_stop_does_not_double_charge_outcome(self):
        def stop(phase):
            if phase == "HIGH_COST_AFTER_hf.kernel":
                raise RuntimeError("fake post dispatch stop")
        guard = native_guard.HighCostGuard(unit(), "live", checkpoint=stop)
        with self.assertRaisesRegex(RuntimeError, "post dispatch"), guard:
            self.engine.rks.RKS().kernel()
        self.assertEqual(guard.snapshot()["outcomes"]["scf"], {"returned": 1, "failed": 0})

    def test_checkpoint_mutation_denies_before_original_and_restores(self):
        original = self.engine.hf.kernel
        def mutate(phase):
            self.engine.hf.kernel = lambda *args: None
        guard = native_guard.HighCostGuard(unit(), "live", checkpoint=mutate)
        with self.assertRaises(native_guard.GuardError), guard:
            self.engine.rks.RKS().kernel()
        self.assertIs(self.engine.hf.kernel, original)
        self.assertEqual(self.engine.calls, [])
        self.assertTrue(guard.snapshot()["restored_attributes_intact"])

    def test_foreign_thread_is_denied_and_does_not_enter_delegate(self):
        errors = []
        guard = native_guard.HighCostGuard(unit(), "live")
        with guard:
            def call():
                try:
                    self.engine.rks.RKS().kernel()
                except native_guard.GuardError as error:
                    errors.append(error)
            thread = threading.Thread(target=call); thread.start(); thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertEqual(self.engine.calls, [])
        self.assertEqual(guard.snapshot()["status"], "FAIL")

    def test_append_journal_preserves_existing_entries(self):
        with tempfile.TemporaryDirectory(prefix="high-cost-guard-fake-") as directory:
            journal = Path(directory) / "events.jsonl"
            journal.write_text('{"existing":true}\n', encoding="utf-8")
            guard = native_guard.HighCostGuard(unit(), "live", journal=journal)
            with guard:
                self.engine.rks.RKS().kernel()
            rows = [json.loads(line) for line in journal.read_text().splitlines()]
            self.assertEqual(rows[0], {"existing": True})
            self.assertEqual(rows[-1]["event"], "GUARD_CLOSED")
            self.assertTrue(any(row.get("entry") == "hf.kernel" for row in rows))

    def test_nested_or_reused_guard_is_refused(self):
        guard = native_guard.HighCostGuard(unit(), "live")
        with guard:
            with self.assertRaises(native_guard.GuardError):
                with native_guard.HighCostGuard(unit(), "live"):
                    pass
        with self.assertRaises(native_guard.GuardError):
            with guard:
                pass


if __name__ == "__main__":
    unittest.main()
