"""P12 source gates, fresh execution routing and arithmetic; no QM kernels."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from runtime.high_cost_cases import p12

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reference/high_cost_cases/source_tree"


class P12RegistryTests(unittest.TestCase):
    def test_sixty_one_separate_optimization_units_cover_fixed_domain(self):
        rows = p12.units()
        self.assertEqual(len(rows), 61)
        self.assertEqual(len({row["id"] for row in rows}), 61)
        self.assertEqual([sum(row["system"] == f"N{n}" for row in rows) for n in (12, 14, 16)], [8, 23, 30])
        self.assertTrue(all(row["geometry_optimization"] and row["max_geometry_steps"] == 80 for row in rows))
        self.assertTrue(all(row["method_id"] == p12.METHOD for row in rows))

    def test_n12_control_is_independent_and_has_no_ledger_weight(self):
        rows = [row for row in p12.units() if row["system"] == "N12" and row["state"] == "GE"]
        representatives = [row for row in rows if not row["symmetry_control"]]
        control = [row for row in rows if row["symmetry_control"]]
        self.assertEqual([row["pair"] for row in representatives], [[0, 1], [0, 2], [0, 3], [0, 5], [1, 3]])
        self.assertEqual(sum(row["multiplicity"] for row in representatives), 15)
        self.assertEqual(control[0]["id"], "P12-N12-GE-g03-g04-control")
        self.assertEqual(control[0]["multiplicity"], 0)

    def test_n16_requires_current_g_and_gl_before_every_ge(self):
        rows = [row for row in p12.units() if row["system"] == "N16" and row["state"] == "GE"]
        self.assertEqual(len(rows), 28)
        self.assertTrue(all(row["dependencies"] == ["P12-N16-G", "P12-N16-GL"] for row in rows))
        self.assertTrue(all(row["multiplicity"] == 1 for row in rows))

    def test_changed_state_pair_method_and_dependencies_are_rejected(self):
        original = p12._unit("P12-N16-GE-g01-g02")
        for key, value in (("pair", [0, 2]), ("method_id", "B3LYP/sto-3g"),
                           ("dependencies", ["P12-N16-G"]), ("source_protocol_id", p12.BASE_PROTOCOL)):
            altered = {**original, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                p12._unit(altered)
        for unit in ("P12-N18-G", "P12-N16-GE-g08-g09", "../P12-N12-G"):
            with self.subTest(unit=unit), self.assertRaises(ValueError):
                p12._unit(unit)

    def test_protected_original_scientific_root_cannot_be_executed(self):
        with self.assertRaises(ValueError):
            p12.prepare(Path("D:/AI4Science/AI4OrgChem"))

    def test_duplicate_and_nonfinite_json_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.json"
            for text in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'):
                path.write_text(text, encoding="utf-8")
                with self.subTest(text=text), self.assertRaises(ValueError):
                    p12._json_file(path)


class P12FrozenEvidenceTests(unittest.TestCase):
    def test_source_read_closure_is_complete(self):
        self.assertTrue(SOURCE.is_dir(), "Capture the P12 frozen asset closure before acceptance")
        for relative in p12.assets():
            with self.subTest(asset=relative):
                self.assertTrue(p12._file(SOURCE, relative).is_file())

    def test_original_base_and_n16_hash_binding_remain_intact(self):
        base, n16 = p12._contracts(SOURCE)
        self.assertEqual(n16["base_protocol_sha256"], p12._sha(SOURCE / p12.BASE))
        self.assertEqual(base["energy_contract"]["scf_tolerance_hartree"], 1e-10)
        self.assertEqual(n16["pair_plan"]["total_pair_count"], 28)

    def test_three_historical_ledgers_keep_numeric_difference_and_scope(self):
        result = p12.ledger(SOURCE)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["new_scientific_acceptance"])
        self.assertFalse(result["quantum_calculation_performed"])
        self.assertFalse(result["geometry_optimization_performed"])
        self.assertFalse(result["classification_change_allowed"])
        self.assertEqual(result["historical_2011_method_alignment"], "NOT_ESTABLISHED")
        for row in result["systems"]:
            self.assertTrue(all(row["checks"].values()))
            self.assertNotEqual(row["numeric_difference"]["CESE_kcal_mol"], 0)
            self.assertFalse(row["exact_numeric_reproduction_claimed"])

    def test_tampered_weight_and_energy_do_not_pass_historical_arithmetic(self):
        read_json = p12._json
        for alteration in ("weight", "energy"):
            def tamper(root, relative, alteration=alteration):
                data = copy.deepcopy(read_json(root, relative))
                if relative.endswith("same_basis_n14_ledger_v0.2.json"):
                    key = "multiplicity" if alteration == "weight" else "GE_energy_hartree"
                    data["pair_rows"][0][key] += 1
                return data
            with self.subTest(alteration=alteration), patch.object(p12, "_json", side_effect=tamper), self.assertRaises(ValueError):
                p12.ledger(SOURCE)

    def test_tampered_disclosed_difference_is_reported_as_failed_check(self):
        read_json = p12._json
        def tamper(root, relative):
            data = copy.deepcopy(read_json(root, relative))
            if relative.endswith("same_basis_n16_ledger_v0.2.json"):
                data["recalculation_minus_source"]["CESE_kcal_mol"] = 0.0
            return data
        with patch.object(p12, "_json", side_effect=tamper):
            self.assertEqual(p12.ledger(SOURCE)["status"], "FAIL")


class P12RoutingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.source = self.home / "reference/high_cost_cases/source_tree"
        for relative in p12.assets():
            target = self.source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p12._file(SOURCE, relative), target)

    def test_import_only_preparation_does_not_require_pyscf(self):
        with patch.dict("sys.modules", {"pyscf": None}):
            modules = p12.prepare(self.source)
        self.assertIn("g", modules)
        self.assertEqual(modules["g"].ROOT, self.source)

    def test_preflight_never_calls_optimizer_or_conditional_solver(self):
        modules = p12.prepare(self.source)
        class Molecule:
            natm = 24
            nelectron = 84
            def nao_nr(self):
                return 432
        with patch.object(modules["g"], "build_molecule", return_value=Molecule()), \
             patch.object(modules["g"], "geometry_summary", return_value={"configuration_identity_preserved": True, "maximum_absolute_z_angstrom": 0.0}), \
             patch.object(modules["classification"], "classify_planar_pyscf_aos", return_value=[None]*432), \
             patch.object(modules["g"], "run_one", side_effect=AssertionError("optimizer called")), \
             patch.object(modules["conditional"], "converge_from_ordinary", side_effect=AssertionError("SCF called")):
            result = p12.preflight("P12-N12-G", self.source)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["integrals_evaluated"])
        self.assertFalse(result["scf_performed"])

    def test_n16_live_dispatch_keeps_frozen_gates_and_restores_source_globals(self):
        modules = p12.prepare(self.source)
        output = self.home / "new-output"
        source_hashes = {relative: p12._sha(self.source / relative) for relative in p12.assets()}
        events = []
        def engineering_fake(n, **options):
            self.assertEqual(n, 16)
            self.assertEqual(options["maxsteps"], 80)
            self.assertFalse(options["resume"])
            self.assertFalse(options["force"])
            self.assertTrue(options["n16_execute"])
            protocol, contract = modules["contract"].load_protocol(options["protocol_path"])
            self.assertIsNotNone(contract)
            modules["contract"].require_authorized_state(protocol, contract, 16, "G", None)
            work = modules["g"].ROOT
            relative_xyz = p12.G_DIR + "/N16_G_optimized.xyz"
            xyz = work / relative_xyz
            xyz.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(work / p12.SEEDS / p12.SEED_NAMES[16], xyz)
            record = {"protocol_id": protocol["protocol_id"], "N": 16, "configuration": "[16]-5555",
                      "method": p12.METHOD, "pass": True, "optimizer_converged": True,
                      "final_scf_converged": True, "optimized_xyz": relative_xyz,
                      "geometry": {"configuration_identity_preserved": True, "maximum_absolute_z_angstrom": 0.0},
                      "trajectory": [{"cycle": 1}], "engineering_test_double": True}
            modules["g"].write_json(work / p12.G_DIR / "N16_G.json", record)
            return record
        with patch.object(modules["g"], "run_one", side_effect=engineering_fake):
            result = p12.live("P12-N16-G", self.source, output, {}, events.append)
        self.assertEqual(result["status"], "PASS")  # dispatch engineering only
        self.assertTrue(result["source_result"]["engineering_test_double"])
        self.assertEqual(result["evidence_identity"], "ENGINEERING_FAKE")
        self.assertFalse(result["quantum_calculation_performed"])
        self.assertFalse(result["geometry_optimization_performed"])
        self.assertEqual(modules["g"].ROOT, self.source)
        self.assertEqual(modules["contract"].N16_CONTRACT, self.source / p12.N16_CONTRACT)
        self.assertTrue(events)
        self.assertEqual(source_hashes, {relative: p12._sha(self.source / relative) for relative in p12.assets()})
        self.assertEqual((output / "work" / p12.BASE).read_bytes(), (self.source / p12.BASE).read_bytes())
        self.assertEqual((output / "work" / p12.N16_CONTRACT).read_bytes(), (self.source / p12.N16_CONTRACT).read_bytes())
        with self.assertRaises(ValueError):
            p12.live("P12-N16-G", self.source, output, {}, events.append)

    def test_ge_rejects_missing_gl_before_work_or_solver(self):
        output = self.home / "missing-review"
        with self.assertRaises(ValueError):
            p12.live("P12-N16-GE-g01-g02", self.source, output, {"P12-N16-G": self.home / "g"}, lambda _: None)
        self.assertFalse(output.exists())

    def test_historical_source_is_never_a_current_run_dependency(self):
        with self.assertRaises(ValueError):
            p12._dependency("P12-N12-G", self.source, self.source / p12.G_DIR)

    def test_callback_and_fresh_output_are_required(self):
        with self.assertRaises(ValueError):
            p12.live("P12-N12-G", self.source, self.home / "output", {}, None)
        with self.assertRaises(ValueError):
            p12.live("P12-N12-G", self.source, self.source / "output", {}, lambda _: None)


if __name__ == "__main__":
    unittest.main()
