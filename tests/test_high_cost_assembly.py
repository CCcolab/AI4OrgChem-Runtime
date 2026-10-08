"""Pure arithmetic/refusal tests with explicitly marked engineering doubles.

No fake row can become accepted science, including when artifact geometry and
all formulas pass. These tests never start a scientific backend or optimizer.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from runtime.high_cost_cases import ASSETS, units
from runtime.high_cost_cases import assembly, p11, p12


HAS_CAPTURE = (ASSETS / "configs/qm/p11_furan_lde_v0.1.yaml").is_file()


def _envelope(unit):
    return {"unit_id": unit["id"], "case": unit["case"], "status": "PASS",
        "execution_mode": "live", "new_optimization_executed": True,
        "runtime_protocol_id": "runtime-high-cost-"+unit["case"].lower()+"/0.1",
        "method_id": unit["method_id"], "operator_id": unit["operator_id"],
        "dependencies": list(unit["dependencies"]), "evidence_identity": "ENGINEERING_FAKE",
        "checks": {"ENGINEERING_FIXTURE_ONLY_NOT_SCIENTIFIC_EVIDENCE": True},
        "source_sha256": "a"*64, "dependencies_sha256": "b"*64,
        "profile_sha256": "c"*64, "image_id": "sha256:"+"d"*64}


def _p11_fake_rows():
    historical = p11._json(ASSETS, "data/processed/p11_furan_lde_v0.1.json")
    rows = {}
    for unit in units():
        if unit["case"] != "P11":
            continue
        row = _envelope(unit)
        if unit["subcase"] == "P11-A":
            row.update(copy.deepcopy(historical[unit["state"]]))
            row["protocol_id"] = p11.A_PROTOCOL
            if unit["state"] != "G":
                row["state"]["one_electron_matrix_masked"] = True
        else:
            name = unit["system"]+"_"+unit["state"]
            row["source_record"] = p11._json(ASSETS, f"data/processed/p11_source2007_planar_optimized_v0.2/{name}.json")
            row["source_record"]["engineering_test_double"] = True
            row["protocol_id"] = p11.B_PROTOCOL
        rows[unit["id"]] = row
    return rows


def _p12_fake_rows():
    rows, ledgers = {}, {n: p12._json(ASSETS, f"data/processed/p12_source2011_same_basis_n{n}_ledger_v0.2.json") for n in (12, 14, 16)}
    for unit in units():
        if unit["case"] != "P12":
            continue
        n = int(unit["system"][1:])
        old = ledgers[n]
        if unit["state"] in ("G", "GL"):
            if n == 16:
                energy = old["ledger_hartree"]["E_"+unit["state"]]
            else:
                audit = old["state_audits"][unit["state"]]
                energy = audit.get("energy_hartree", audit.get("recorded_energy_hartree"))
        elif unit.get("symmetry_control"):
            energy = old["state_audits"]["N12_GE_g03_g04_symmetry_control"]["recorded_energy_hartree"]
        else:
            pair_key = "pair_zero_based" if n == 16 else "representative_zero_based"
            energy = next(row["GE_energy_hartree"] for row in old["pair_rows"] if row[pair_key] == unit["pair"])
        source = {"engineering_test_double": True, "N": n, "configuration": p12.CONFIGURATIONS[n],
            "protocol_id": unit["source_protocol_id"], "pass": True, "optimizer_converged": True,
            "final_energy_hartree": energy, "final_scf_converged": True,
            "geometry_scf_converged": True, "energy_scf_converged": True,
            "method": p12.METHOD, "geometry_method": p12.METHOD, "energy_method": p12.METHOD,
            "pair_zero_based": unit["pair"],
            "geometry": {"configuration_identity_preserved": True, "maximum_absolute_z_angstrom": 0.0}}
        row = _envelope(unit)
        row.update(source_result=source, geometry_optimization_performed=True)
        rows[unit["id"]] = row
    return rows


class AssemblyRefusalTests(unittest.TestCase):
    def test_fixed_whole_case_counts_and_missing_diagnostics(self):
        for case, count in (("P11", 17), ("P12", 61)):
            result = assembly.assemble(case, {})
            self.assertEqual(result["required_unit_count"], count)
            self.assertEqual(result["registered_total_unit_count"], 78)
            self.assertEqual(len(result["missing_units"]), count)
            self.assertEqual(result["status"], "BLOCKED_INCOMPLETE")
            self.assertFalse(result["new_scientific_acceptance"])
            self.assertFalse(result["new_numerical_assembly_accepted"])

    def test_unknown_case_and_extra_unknown_unit_are_rejected(self):
        with self.assertRaises(ValueError):
            assembly.assemble("P11-A", {})
        result = assembly.assemble("P11", {"P11B-aniline-G": {}})
        self.assertEqual(result["unknown_units"], ["P11B-aniline-G"])
        self.assertFalse(result["new_scientific_acceptance"])

    def test_ledger_preflight_and_failed_state_cannot_be_current_live_evidence(self):
        unit = units()[0]
        for altered in ({"execution_mode": "ledger"}, {"execution_mode": "preflight"},
                        {"status": "FAIL"}, {"new_optimization_executed": False}):
            row = _envelope(unit)
            row.update(altered)
            result = assembly.assemble("P11", {unit["id"]: row}, engineering_test=True)
            self.assertIn(unit["id"], result["rejected_units"])
            self.assertFalse(result["new_scientific_acceptance"])

    def test_marked_fake_requires_explicit_engineering_opt_in(self):
        unit = units()[0]
        result = assembly.assemble("P11", {unit["id"]: _envelope(unit)})
        self.assertIn("ENGINEERING_FAKE_NOT_SCIENTIFIC", result["rejected_units"][unit["id"]])
        self.assertEqual(result["scientific_status"], "NOT_EXECUTED")

    def test_nonfinite_rows_and_missing_identity_cannot_pass(self):
        unit = units()[0]
        for changed in ({"source_sha256": None}, {"energy": float("nan")},
                        {"image_id": "mutable:latest"}):
            row = _envelope(unit)
            row.update(changed)
            result = assembly.assemble("P11", {unit["id"]: row}, engineering_test=True)
            self.assertIn(unit["id"], result["rejected_units"])
            json.dumps(result, allow_nan=False)

    def test_method_operator_and_dependency_graph_cannot_be_changed(self):
        unit = units()[1]
        for changed in ({"method_id": "B3LYP/sto-3g"}, {"operator_id": "source2011"},
                        {"dependencies": []}):
            row = _envelope(unit)
            row.update(changed)
            result = assembly.assemble("P11", {unit["id"]: row}, engineering_test=True)
            self.assertIn(unit["id"], result["rejected_units"])


@unittest.skipUnless(HAS_CAPTURE, "Frozen comparison protocols have not been captured")
class AssemblyArithmeticTests(unittest.TestCase):
    def test_p11_formulas_recomputed_but_engineering_rows_never_become_science(self):
        rows = _p11_fake_rows()
        with mock.patch.object(p11, "prepare", side_effect=AssertionError("QM preparation")), \
             mock.patch.object(p12, "prepare", side_effect=AssertionError("QM preparation")):
            result = assembly.assemble("P11", rows, engineering_test=True)
        self.assertEqual(result["status"], "ENGINEERING_ONLY")
        self.assertEqual(result["numerical_status"], "PASS")
        self.assertEqual(result["scientific_status"], "NOT_EXECUTED")
        self.assertFalse(result["new_scientific_acceptance"])
        self.assertFalse(result["new_numerical_assembly_accepted"])
        a, b = result["subcases"]["P11-A"], result["subcases"]["P11-B"]
        self.assertAlmostEqual(a["LDE_kcal_mol"], -40.8511098747703, places=9)
        self.assertAlmostEqual(b["inductive_effect_kcal_mol"], .49007915431465726, places=9)
        self.assertEqual(a["printed_reference_comparison"]["status"], "PASS")
        self.assertEqual(b["printed_reference_comparison"]["status"], "PASS")
        self.assertFalse(b["source_start_diagnostic"]["within_registered_threshold"])
        self.assertFalse(result["external_experimental_validation"])

    def test_four_furan_states_cannot_impersonate_whole_p11(self):
        rows = {key: row for key, row in _p11_fake_rows().items() if key.startswith("P11A-")}
        result = assembly.assemble("P11", rows, engineering_test=True)
        self.assertEqual(result["subcases"]["P11-A"]["numerical_status"], "PASS")
        self.assertEqual(len(result["missing_units"]), 13)
        self.assertEqual(result["status"], "BLOCKED_INCOMPLETE")
        self.assertFalse(result["new_scientific_acceptance"])

    def test_mixed_identity_blocks_whole_assembly(self):
        for field, value in (("source_sha256", "e"*64), ("dependencies_sha256", "e"*64),
                             ("profile_sha256", "e"*64), ("image_id", "sha256:"+"e"*64)):
            rows = _p11_fake_rows()
            rows["P11B-cyanobenzene-GE7"][field] = value
            result = assembly.assemble("P11", rows, engineering_test=True)
            self.assertIn("P11B-cyanobenzene-GE7", result["identity_mismatches"])
            self.assertFalse(result["complete_current_case"])
            self.assertFalse(result["new_scientific_acceptance"])

    def test_source_comparison_difference_is_separate_from_numerical_validity(self):
        rows = _p11_fake_rows()
        rows["P11B-cyanobenzene-G"]["source_record"]["final_energy_hartree"] += .001
        result = assembly.assemble("P11", rows, engineering_test=True)
        b = result["subcases"]["P11-B"]
        self.assertEqual(b["numerical_status"], "PASS")
        self.assertEqual(b["printed_reference_comparison"]["status"], "OUTSIDE_FROZEN_TOLERANCE")
        self.assertFalse(result["new_scientific_acceptance"])

    def test_outer_pass_cannot_hide_a_failed_original_optimizer_or_scf_gate(self):
        rows = _p11_fake_rows()
        rows["P11A-furan-GL"]["optimizer"]["success"] = False
        rows["P11B-benzene-G"]["source_record"]["final_scf_converged"] = False
        result = assembly.assemble("P11", rows, engineering_test=True)
        self.assertEqual(result["subcases"]["P11-A"]["numerical_status"], "NOT_QUALIFIED")
        self.assertEqual(result["subcases"]["P11-B"]["numerical_status"], "NOT_QUALIFIED")
        self.assertFalse(result["new_numerical_assembly_accepted"])

    def test_p12_all61_rows_without_current_xyz_cannot_accept_n12_weighting(self):
        result = assembly.assemble("P12", _p12_fake_rows(), engineering_test=True)
        self.assertTrue(result["complete_current_case"])
        n12 = result["subcases"]["N12"]
        self.assertEqual(n12["N12_weighting"]["status"], "BLOCKED_NOT_VERIFIED")
        self.assertFalse(n12["weighted_ledger_accepted"])
        self.assertEqual(n12["weighted_pair_count"], 15)
        self.assertEqual(len(n12["pair_rows"]), 5)
        self.assertEqual(result["subcases"]["N14"]["weighted_pair_count"], 21)
        self.assertEqual(result["subcases"]["N16"]["weighted_pair_count"], 28)
        self.assertEqual(result["scientific_status"], "NOT_EXECUTED")
        self.assertFalse(result["new_scientific_acceptance"])
        self.assertEqual(result["historical_2011_method_alignment"], "NOT_ESTABLISHED")

    def test_only_one_size_does_not_become_all_p12(self):
        rows = {key: row for key, row in _p12_fake_rows().items() if key.startswith("P12-N14-")}
        result = assembly.assemble("P12", rows, engineering_test=True)
        self.assertEqual(result["subcases"]["N14"]["numerical_status"], "PASS")
        self.assertEqual(len(result["missing_units"]), 38)
        self.assertEqual(result["status"], "BLOCKED_INCOMPLETE")
        self.assertFalse(result["new_scientific_acceptance"])

    def test_n16_zero_relative_cese_denominator_is_not_qualified(self):
        rows = _p12_fake_rows()
        energy = rows["P12-N16-GL"]["source_result"]["final_energy_hartree"]
        for identifier, row in rows.items():
            if identifier.startswith("P12-N16-GE-"):
                row["source_result"]["final_energy_hartree"] = energy
        result = assembly.assemble("P12", rows, engineering_test=True)
        n16 = result["subcases"]["N16"]
        self.assertIsNone(n16["N16_relative_CESE"]["value"])
        self.assertFalse(n16["checks"]["relative_CESE_denominator_nonzero"])
        self.assertEqual(n16["numerical_status"], "NOT_QUALIFIED")

    def test_full78_input_filters_by_fixed_case(self):
        rows = {**_p11_fake_rows(), **_p12_fake_rows()}
        result = assembly.assemble("P11", rows, engineering_test=True)
        self.assertEqual(result["present_unit_count"], 17)
        self.assertEqual(result["unknown_units"], [])
        self.assertEqual(result["status"], "ENGINEERING_ONLY")

    def test_verified_artifact_geometry_gate_stays_engineering_and_control_has_zero_weight(self):
        rows = _p12_fake_rows()
        identifiers = ("P12-N12-GL", "P12-N12-GE-g01-g02", "P12-N12-GE-g03-g04-control")
        with tempfile.TemporaryDirectory() as directory:
            outputs = {}
            for identifier in identifiers:
                output = Path(directory) / identifier
                output.mkdir()
                outputs[identifier] = output
                source = rows[identifier]["source_result"]
                source["optimized_xyz"] = "current.xyz"
                result_path = output / "work/current-source.json"
                result_path.parent.mkdir()
                result_path.write_text(json.dumps(source), encoding="utf-8")
                xyz = output / "work/current.xyz"
                atoms = [[element, radius*math.cos(i*math.pi/6), radius*math.sin(i*math.pi/6), 0.0]
                    for element, radius in (("C", 5.0), ("H", 6.0)) for i in range(12)]
                xyz.write_text("24\nENGINEERING_FAKE C3 geometry\n"+"\n".join(" ".join(map(str, atom)) for atom in atoms)+"\n", encoding="utf-8")
                rows[identifier]["source_result_path"] = "work/current-source.json"
                rows[identifier]["artifacts"] = {"work/current-source.json": hashlib.sha256(result_path.read_bytes()).hexdigest(),
                    "work/current.xyz": hashlib.sha256(xyz.read_bytes()).hexdigest()}
            result = assembly.assemble("P12", rows, output_dirs=outputs, engineering_test=True)
            self.assertEqual(result["subcases"]["N12"]["N12_weighting"]["status"], "PASS")
            self.assertEqual(result["subcases"]["N12"]["N12_weighting"]["control_weight"], 0)
            self.assertEqual(result["status"], "ENGINEERING_ONLY")
            self.assertFalse(result["new_scientific_acceptance"])
            self.assertFalse(result["new_numerical_assembly_accepted"])
            self.assertEqual(result["scientific_status"], "NOT_EXECUTED")
            xyz.write_text(xyz.read_text()+"tampered\n", encoding="utf-8")
            tampered = assembly.assemble("P12", rows, output_dirs=outputs, engineering_test=True)
            self.assertEqual(tampered["subcases"]["N12"]["N12_weighting"]["status"], "BLOCKED_NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
