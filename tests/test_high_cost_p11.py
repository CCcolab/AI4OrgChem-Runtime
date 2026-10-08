"""P11 registry, arithmetic, artifact and source-wiring tests.

Real molecule preflight is opt-in inside the scientific container. Host tests
use no PySCF kernels and never treat mocked optimizer data as science evidence.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from runtime.high_cost_cases import p11


ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "reference/high_cost_cases/source_tree"
HAS_LEDGER = (CAPTURE / "data/processed/p11_furan_lde_v0.1.json").is_file()


class P11RegistryTests(unittest.TestCase):
    def test_seventeen_states_and_exact_furan_dependencies(self):
        rows = p11.units()
        self.assertEqual(len(rows), 17)
        self.assertEqual(len({row["id"] for row in rows}), 17)
        self.assertEqual([row["state"] for row in rows[:4]], ["G", "GL", "GE1", "GE2"])
        self.assertEqual([row["dependencies"] for row in rows[:4]], [[], ["P11A-furan-G"],
            ["P11A-furan-G", "P11A-furan-GL"], ["P11A-furan-G", "P11A-furan-GL"]])
        self.assertTrue(all(not row["dependencies"] for row in rows[4:]))
        self.assertTrue(all(row["case"] == "P11" and row["pair"] is None for row in rows))
        self.assertIn("h/F/S", rows[1]["method_id"])
        self.assertIn("physical-hcore", rows[5]["method_id"])
        self.assertIn("ordinary-RKS", rows[0]["method_id"])

    def test_registry_returns_fresh_metadata(self):
        p11.units()[1]["dependencies"].append("bad")
        self.assertEqual(p11.units()[1]["dependencies"], ["P11A-furan-G"])
        with self.assertRaises(ValueError):
            p11._unit({"id": "P11A-furan-GL", "state": "G"})
        with self.assertRaises(ValueError):
            p11._unit("P11B-aniline-G")

    def test_explicit_capture_closure_preserves_historical_records(self):
        assets = p11.assets()
        self.assertIsInstance(assets, set)
        self.assertEqual(len(p11._STATE_FILES), 13)
        self.assertTrue(set(p11._STATE_FILES).issubset(assets))
        self.assertTrue({"scripts/__init__.py", "src/ai4orgchem/qm/p09_energy_assembly.py",
            "scripts/run_p11_benzene_2007_anchor.py",
            "configs/qm/p11_benzene_all_atom_planar.constraints",
            "configs/qm/p11_cyanobenzene_all_atom_planar.constraints",
            "data/processed/p11_cyanobenzene_effect_v0.1.json"}.issubset(assets))
        self.assertTrue(all(not Path(path).is_absolute() and ".." not in Path(path).parts for path in assets))
        assets.clear()
        self.assertGreater(len(p11.assets()), 40)

    def test_only_first_history_absent_delta_infinity_is_normalized(self):
        self.assertEqual(p11._normalize({"history": [{"energy_change_hartree": float("inf")}]}),
                         {"history": [{"energy_change_hartree": None}]})
        for value in ({"energy": float("inf")}, {"history": [{"energy_change_hartree": float("nan")}]},
                      {"history": [{}, {"energy_change_hartree": float("inf")}]}):
            with self.assertRaises(ValueError):
                p11._normalize(value)

    def test_prepare_rejects_uncaptured_scientific_root(self):
        with mock.patch.object(p11.importlib, "import_module") as imported:
            with self.assertRaises(ValueError):
                p11.prepare(ROOT)
            imported.assert_not_called()

    def test_prepare_only_imports_captured_helpers_without_geometric(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "reference/high_cost_cases/source_tree"
            for relative in p11.assets():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# Host engineering fixture; no scientific code\n", encoding="utf-8")
            imported = []
            def load(name):
                imported.append(name)
                relative = ("src/" if name.startswith("ai4orgchem") else "") + name.replace(".", "/")
                relative += "/__init__.py" if name in ("ai4orgchem", "ai4orgchem.qm", "scripts") else ".py"
                return SimpleNamespace(__file__=str(root / relative))
            with mock.patch.object(p11.importlib, "import_module", side_effect=load):
                p11.prepare(root)
            self.assertTrue(imported)
            self.assertFalse(any(name.startswith("pyscf") or "geometric" in name for name in imported))
            p11._PREPARED.pop(str(root.resolve()), None)

    def test_source_and_previous_outputs_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root, output = Path(directory) / "source", Path(directory) / "output"
            root.mkdir()
            with self.assertRaises(ValueError):
                p11._output(root, root / "new")
            output.mkdir()
            (output / "p11-state.json").write_text("preserve", encoding="utf-8")
            with self.assertRaises(ValueError):
                p11._output(root, output)
            self.assertEqual((output / "p11-state.json").read_text(), "preserve")


@unittest.skipUnless(HAS_LEDGER, "Captured P11 historical files have not been installed")
class P11HistoricalLedgerTests(unittest.TestCase):
    def test_historical_ledger_recalculates_with_no_science_imports(self):
        with mock.patch.object(p11, "prepare", side_effect=AssertionError("ledger imported science")):
            result = p11.ledger(CAPTURE)
        self.assertEqual(result["status"], "PASS", result.get("failed_checks"))
        self.assertEqual(result["observed_new_scf_kernel_calls"], 0)
        self.assertEqual(result["observed_new_integral_calls"], 0)
        self.assertFalse(result["new_optimization_executed"])
        self.assertFalse(result["new_scientific_conclusion_generated"])
        self.assertAlmostEqual(result["furan"]["LDE_kcal_mol"], -40.851110, places=5)
        self.assertAlmostEqual(result["substituted_benzene"]["inductive_effect_kcal_mol"], 0.490079, places=5)
        self.assertFalse(result["source_start_diagnostic"]["within_registered_threshold"])
        json.dumps(result, allow_nan=False)

    def test_modified_endpoint_cannot_reuse_historical_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            needed = set(p11._STATE_FILES) | {"configs/qm/p11_furan_lde_v0.1.yaml",
                "configs/qm/p11_source2007_planar_recalculation_v0.2.yaml",
                "configs/qm/p11_substituted_benzene_effect_v0.1.yaml",
                "configs/qm/p11_benzene_2007_anchor_v0.1.yaml",
                "data/processed/p11_furan_lde_v0.1.json",
                "data/processed/p11_source2007_planar_recalculation_v0.2.json"}
            for relative in needed:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(CAPTURE / relative, path)
            path = root / "data/processed/p11_furan_lde_v0.1.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            record["GE2"]["state"]["total_energy_hartree"] += 0.001
            path.write_text(json.dumps(record), encoding="utf-8")
            result = p11.ledger(root)
            self.assertEqual(result["status"], "NOT_QUALIFIED")
            self.assertIn("A_LDE_hartree_recomputed", result["failed_checks"])


class P11DependencyAndWiringTests(unittest.TestCase):
    def test_dependencies_require_new_qualified_unit_identity_and_finite_density(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = {"unit_id": "P11A-furan-G", "status": "PASS", "mode": "ledger",
                      "parameters_angstrom": [1.0]*8}
            (root / "p11-state.json").write_text(json.dumps(record), encoding="utf-8")
            np.save(root / "density.npy", np.eye(2), allow_pickle=False)
            with self.assertRaises(ValueError):
                p11._dependency("P11A-furan-G", {"P11A-furan-G": root})
            record["mode"] = "live"
            (root / "p11-state.json").write_text(json.dumps(record), encoding="utf-8")
            parameters, density = p11._dependency("P11A-furan-G", {"P11A-furan-G": root})
            self.assertEqual(parameters.shape, (8,))
            self.assertEqual(density.shape, (2, 2))
            np.save(root / "density.npy", np.full((2, 2), float("nan")), allow_pickle=False)
            with self.assertRaises(ValueError):
                p11._dependency("P11A-furan-G", {"P11A-furan-G": root})

    def test_gl_and_ge2_use_original_bounds_and_correct_seed(self):
        """Test adapter wiring with inert helpers, never call any QM backend."""
        import numpy as np
        g_parameters, gl_parameters = np.arange(8.0), np.arange(8.0)+0.1
        g_density, gl_density = np.eye(2), np.eye(2)*2.0
        protocol = {"geometry": {"conditional_half_windows_angstrom": [0.25]*8}}
        for state in ("GL", "GE2"):
            observed = {}
            def conditional(atoms, fragments, seed, protocol):
                observed["seed"] = seed
                observed["fragments"] = fragments
                return {"converged": True, "total_energy_hartree": -1.0, "density": seed.copy()}
            def optimize(**kwargs):
                observed.update(initial=kwargs["initial"].copy(), bounds=kwargs["bounds"])
                kwargs["evaluator"](kwargs["initial"])
                return SimpleNamespace(x=kwargs["initial"].copy()), []
            helper = SimpleNamespace(build_molecule=lambda atoms, protocol: SimpleNamespace(nao_nr=lambda: 2),
                furan_atoms=lambda parameters: [["O", 0.0, 0.0, 0.0]], conditional_state=conditional,
                optimize_state=optimize, write_json=lambda *args: None, compact_state=lambda raw: {},
                geometry_metrics=lambda atoms: {}, optimizer_record=lambda *args: {})
            def dependency(unit_id, inputs):
                return (g_parameters.copy(), g_density.copy()) if unit_id.endswith("-G") else (gl_parameters.copy(), gl_density.copy())
            with mock.patch.object(p11, "_modules", return_value={"run_p11_furan_lde": helper}), \
                 mock.patch.object(p11, "_protocols", return_value=(protocol, None, None, None)), \
                 mock.patch.object(p11, "_dependency", side_effect=dependency), \
                 mock.patch.object(p11, "_a_state_checks", return_value={"inert_wiring_test": True}), \
                 mock.patch.object(p11, "_save", side_effect=lambda target, unit, result, atoms, density, checkpoint: result):
                p11._live_a(p11._unit("P11A-furan-"+state), "unused", Path("unused"), Path("unused"), {}, lambda event: None)
            expected_initial = g_parameters if state == "GL" else gl_parameters
            expected_seed = g_density if state == "GL" else gl_density
            np.testing.assert_array_equal(observed["initial"], expected_initial)
            np.testing.assert_array_equal(observed["seed"], expected_seed)
            self.assertEqual(observed["bounds"], [(value-0.25, value+0.25) for value in g_parameters])
            self.assertEqual(observed["fragments"], p11._a_fragments(state))

    def test_b_calls_original_single_state_and_reads_observed_density_without_extra_kernel(self):
        import numpy as np
        source = {"optimizer_converged": True, "final_scf_converged": True, "pass": True,
            "geometry": {"maximum_absolute_z_angstrom": 0.0}, "one_electron_matrix_masked": False,
            "optimized_atoms_angstrom": [["C", 0.0, 0.0, 0.0]]}
        mf = SimpleNamespace(make_rdm1=lambda: np.eye(2), kernel=mock.Mock(side_effect=AssertionError("extra SCF")))
        def builder(*args):
            return mf
        runner = SimpleNamespace(ROOT="original", OUTPUT_DIR="original", REPORT_DIR="original",
            write_json=lambda *args: None, _configure=lambda mean_field, template: mean_field,
            build_benzene_mean_field=builder, build_cyanobenzene_mean_field=builder)
        calls = []
        def run_one(system, state, maxsteps):
            calls.append((system, state, maxsteps))
            template = runner.build_benzene_mean_field(None, None)
            runner._configure(mf, template)
            return copy.deepcopy(source)
        runner.run_one = run_one
        saved = []
        with mock.patch.object(p11, "_modules", return_value={"run_p11_source2007_planar_optimization": runner}), \
             mock.patch.object(p11, "_save", side_effect=lambda target, unit, result, atoms, density, checkpoint: saved.append(density) or result):
            result = p11._live_b(p11._unit("P11B-benzene-GL"), "unused", Path("unused"), Path("unused"), lambda event: None)
        self.assertEqual(calls, [("benzene", "GL", 50)])
        self.assertEqual(runner.ROOT, "original")
        self.assertIs(runner.build_benzene_mean_field, builder)
        mf.kernel.assert_not_called()
        np.testing.assert_array_equal(saved[0], np.eye(2))
        self.assertFalse(result["optimized_dependency_seed_substitution"])


@unittest.skipUnless(HAS_LEDGER and os.environ.get("AI4ORGCHEM_HIGH_COST_SCIENTIFIC_TESTS") == "1",
                     "Actual P11 preflight runs only in the opted-in scientific container")
class P11ActualPreflightTests(unittest.TestCase):
    def test_all_registered_molecules_build_without_integrals_scf_or_nuclear_energy(self):
        p11.prepare(CAPTURE)
        from pyscf import gto, dft
        with mock.patch.object(gto.Mole, "intor", side_effect=AssertionError("preflight integral")), \
             mock.patch.object(gto.Mole, "intor_by_shell", side_effect=AssertionError("preflight ERI")), \
             mock.patch.object(gto.Mole, "energy_nuc", side_effect=AssertionError("preflight nuclear energy")), \
             mock.patch.object(dft.rks.RKS, "kernel", side_effect=AssertionError("preflight SCF")):
            for unit in p11.units():
                with self.subTest(unit=unit["id"]):
                    result = p11.preflight(unit, CAPTURE)
                    self.assertEqual(result["status"], "PASS", result.get("failed_checks"))
                    self.assertEqual(result["observed_new_scf_kernel_calls"], 0)
                    self.assertEqual(result["observed_new_integral_calls"], 0)


if __name__ == "__main__":
    unittest.main()
