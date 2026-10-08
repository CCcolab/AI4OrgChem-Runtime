"""Pure ledger/contract tests; no PySCF, source driver or kernel execution."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from runtime.protocol_cases import p03_p06 as cases


class ProtocolLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="protocol-ledger-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, allow_nan=False), encoding="utf-8")
        return path

    def p03(self):
        totals, nuclei = [-10., -11., -12., -11.], [10., 11., 12., 13.]
        value = {"analysis": {"verdict": "P03_MINIMAL_PARENT_NBA_DIRECTION_SUPPORTED"}, "points": {}}
        for index, angle in enumerate(("0.0", "20.0", "40.0", "60.0")):
            value["points"][angle] = {
                "geometry": {"geometry_sha256": "a" * 64, "optimizer_converged": True,
                             "achieved_twist_degrees": float(angle), "requested_twist_degrees": float(angle)},
                "energies": {"scf_converged": True, "total_energy_hartree": totals[index],
                             "electronic_energy_hartree": totals[index] - nuclei[index],
                             "nuclear_repulsion_hartree": nuclei[index]}}
        self.write(cases.P03_EVIDENCE, value)
        return value

    def p05(self):
        points = {}
        for angle in ("0.0", "5.0", "10.0", "17.0", "25.0", "35.0", "45.0"):
            endpoint = 0. if angle == "0.0" else float(angle) / 1000.
            point = {
                "ground_energy_hartree": -500. + endpoint, "fud_energy_hartree": -500.,
                "ground_converged": True, "fud_converged": True, "technical_pass": True,
                "checks": {"saved": True}, "density_fixed_point_residual": 1e-9,
                "electron_trace": 96., "roots": [7, 41], "group_sizes": [56, 162],
                "lfmo_basis_hash": "b" * 64,
                "components": {"direct_total_hartree": 2 * endpoint,
                               "pi_response_hartree": -endpoint,
                               "sigma_response_hartree": 0., "endpoint_hartree": endpoint}}
            for field in ("source_cross_group_density_norm", "masked_overlap_cross_block_norm",
                          "masked_fock_cross_block_norm_hartree", "pyscf_vs_explicit_energy_residual_hartree",
                          "pyscf_vs_assembled_helper_residual_hartree", "equation_closure_residual_hartree",
                          "sigma_response_category_closure_residual_hartree", "sigma_response_electronic_split_residual_hartree"):
                point["components"][field] = 0.
            points[angle] = point
        value = {"checks": {"saved": True}, "scientific_verdict": "P05_CONSISTENT_WITH_MULTI_ANGLE_SUPPORT", "points": points}
        self.write(cases.P05_EVIDENCE, value)
        self.write(cases.P05_ANCHOR, {"points": {a: deepcopy(points[a]) for a in ("0.0", "17.0")}})
        return value

    def p06(self):
        value = {"technical_checks": {"saved": True}, "direction_checks": {"saved": True},
                 "environment_manifest": {"environment": {"numpy_runtime": "historical-version"}}, "points": {}}
        for angle, endpoint in (("0.0", .068), ("17.0", .063)):
            states = {}
            for name, groups, roots, energy in (
                ("FUL", [6, 8, 28, 37, 2], [3, 4, 17, 23, 1], -500.),
                ("PDSI", [6, 8, 65, 2], [3, 4, 40, 1], -500. + endpoint)):
                states[name] = {"converged": True, "pipeline_energy_hartree": energy,
                                "independent_energy_hartree": energy, "electron_trace": 96.,
                                "density_fixed_point_residual": 1e-9,
                                "physical_metric_idempotency_residual": .07,
                                "group_sizes": groups, "occupied_roots": roots}
            value["points"][angle] = {"states": states, "source_partition_contract_closes": True,
                                      "shared_lfmo_basis_within_geometry": True,
                                      "independent_endpoint_hartree": endpoint,
                                      "geometry_sha256": "c" * 64}
        self.write(cases.P06_EVIDENCE, value)
        return value

    def p04(self):
        keys = [("diphenyl_imine", a) for a in (0., 5., 10., 15., 17., 20., 25., 30.)] + [
            ("phenyl_vinyl_imine", 0.), ("phenyl_vinyl_imine", 17.), ("divinyl_imine", 0.)]
        source = "artifacts/raw/test-source.json"
        raw = {"points": {}}
        for family, angle in keys:
            direct = -.01 if family == "divinyl_imine" else .01
            endpoint = .06
            raw_key = f"{angle:.1f}" if family == "diphenyl_imine" else f"{family}:{angle:.1f}"
            raw["points"][raw_key] = {
                "technical_pass": True, "checks": {"saved": True},
                "source_local_three_bucket_view": {"pi_pi_direct_change_hartree": direct,
                                                    "orbital_response_total_hartree": endpoint - direct},
                "transition": {"endpoint_hartree": endpoint}}
        file = self.write(source, raw)
        digest = hashlib.sha256(file.read_bytes()).hexdigest()
        rows = []
        for family, angle in keys:
            direct = -.01 if family == "divinyl_imine" else .01
            for component, value in (("pi_pi_direct", direct), ("orbital_response_total", .06 - direct),
                                     ("source_endpoint_E_FUD_minus_E_DSI3", .06)):
                row = {"record_id": f"{family}:{angle}:{component}", "family_id": family,
                       "angle_degrees": angle, "component": component, "value": value,
                       "production_label": False, "training_eligible": False,
                       "universal_all_molecules_law": False, "method": "RHF", "basis": "6-31g(d)",
                       "unit": "hartree", "source_artifact": source, "source_artifact_sha256": digest}
                for field in ("geometry_hash", "lfmo_basis_hash", "dsi3_state_config_sha256",
                              "fud_state_config_sha256", "fragment_state_contract_sha256"):
                    row[field] = "a" * 64
                rows.append(row)
        path = self.root / cases.P04_LABELS
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        return rows

    def update_rows(self, rows):
        (self.root / cases.P04_LABELS).write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    def test_assets_are_explicit_unique_relative_paths(self):
        values = cases.assets()
        self.assertEqual(values, sorted(set(values)))
        self.assertTrue(all(not Path(p).is_absolute() and ".." not in Path(p).parts for p in values))
        self.assertIn("artifacts/raw/source_metric_diphenyl_diagnostic_energy_2026-08-15.json", values)
        self.assertIn("experiments/validation/one_cut_conditional_scf_gate0.py", values)

    def test_all_four_pure_ledgers_pass_without_scientific_import(self):
        self.p03(); self.p04(); self.p05(); self.p06()
        before = set(sys.modules)
        for case, count in (("P03", 4), ("P04", 11), ("P05", 7), ("P06", 2)):
            result = cases.ledger(case, self.root)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(len(result["records"]), count)
            self.assertEqual(result["expected_scfs"], 0)
            json.dumps(result, allow_nan=False)
        self.assertFalse(any(m.startswith(("pyscf", "experiments.validation")) for m in set(sys.modules) - before))

    def test_unknown_case_is_rejected(self):
        with self.assertRaises(ValueError): cases.ledger("P01", self.root)

    def test_p03_missing_angle_is_rejected(self):
        value = self.p03(); del value["points"]["60.0"]; self.write(cases.P03_EVIDENCE, value)
        with self.assertRaises(ValueError): cases.ledger("P03", self.root)

    def test_p03_identity_is_recomputed_not_trusted(self):
        value = self.p03(); value["points"]["20.0"]["energies"]["electronic_energy_hartree"] += .01
        self.write(cases.P03_EVIDENCE, value)
        result = cases.ledger("P03", self.root)
        self.assertEqual(result["status"], "NOT_QUALIFIED")
        self.assertIn("20.0:energy_identity", result["failed_checks"])

    def test_p03_optimizer_flag_requires_boolean(self):
        value = self.p03(); value["points"]["0.0"]["geometry"]["optimizer_converged"] = 1
        self.write(cases.P03_EVIDENCE, value)
        self.assertEqual(cases.ledger("P03", self.root)["status"], "NOT_QUALIFIED")

    def test_p03_direction_is_recomputed(self):
        value = self.p03(); value["points"]["20.0"]["energies"].update(
            {"total_energy_hartree": -9., "electronic_energy_hartree": -20., "nuclear_repulsion_hartree": 11.})
        self.write(cases.P03_EVIDENCE, value)
        result = cases.ledger("P03", self.root)
        self.assertEqual(result["status"], "NOT_QUALIFIED")
        self.assertIn("0.0->20.0:total_decreases", result["failed_checks"])

    def test_nonfinite_json_is_rejected(self):
        file = self.write(cases.P03_EVIDENCE, {})
        file.write_text('{"value": NaN}', encoding="utf-8")
        with self.assertRaises(ValueError): cases.ledger("P03", self.root)

    def test_duplicate_json_key_is_rejected(self):
        file = self.write(cases.P03_EVIDENCE, {})
        file.write_text('{"points": {}, "points": {}}', encoding="utf-8")
        with self.assertRaises(ValueError): cases.ledger("P03", self.root)

    def test_p04_missing_counterexample_rejects_coverage(self):
        rows = self.p04(); self.update_rows(rows[:-3])
        with self.assertRaises(ValueError): cases.ledger("P04", self.root)

    def test_p04_duplicate_component_is_rejected(self):
        rows = self.p04(); rows[-1] = deepcopy(rows[0]); self.update_rows(rows)
        with self.assertRaises(ValueError): cases.ledger("P04", self.root)

    def test_p04_source_hash_mismatch_is_not_qualified(self):
        rows = self.p04(); rows[0]["source_artifact_sha256"] = "f" * 64; self.update_rows(rows)
        self.assertEqual(cases.ledger("P04", self.root)["status"], "NOT_QUALIFIED")

    def test_p04_false_universal_flag_is_required(self):
        rows = self.p04(); rows[0]["universal_all_molecules_law"] = True; self.update_rows(rows)
        self.assertEqual(cases.ledger("P04", self.root)["status"], "NOT_QUALIFIED")

    def test_p04_component_closure_is_recomputed(self):
        rows = self.p04(); rows[0]["value"] += .001; self.update_rows(rows)
        result = cases.ledger("P04", self.root)
        self.assertEqual(result["status"], "NOT_QUALIFIED")
        self.assertIn("diphenyl_imine:0.0:closure", result["failed_checks"])

    def test_p04_no_universal_positive_direct_claim(self):
        self.p04(); result = cases.ledger("P04", self.root)
        self.assertTrue(result["checks"]["retained_negative_direct_term_counterexample"])
        self.assertFalse(result["scopes"]["production_labels_allowed"])

    def test_p05_anchor_mismatch_is_not_qualified(self):
        self.p05(); anchor = cases._read(self.root, cases.P05_ANCHOR)
        anchor["points"]["17.0"]["components"]["endpoint_hartree"] += 2e-12
        self.write(cases.P05_ANCHOR, anchor)
        self.assertIn("17.0:frozen_anchor_endpoint", cases.ledger("P05", self.root)["failed_checks"])

    def test_p05_zero_degree_indeterminate_is_retained(self):
        value = self.p05(); value["points"]["0.0"]["components"]["endpoint_hartree"] = 2e-8
        self.write(cases.P05_EVIDENCE, value)
        self.assertIn("0.0:sign", cases.ledger("P05", self.root)["failed_checks"])

    def test_p05_measured_density_gate_is_not_just_saved_flag(self):
        value = self.p05(); value["points"]["17.0"]["density_fixed_point_residual"] = 2e-8
        self.write(cases.P05_EVIDENCE, value)
        self.assertIn("17.0:density_fixed_point", cases.ledger("P05", self.root)["failed_checks"])

    def test_p05_mask_measurement_gate(self):
        value = self.p05(); value["points"]["17.0"]["components"]["masked_overlap_cross_block_norm"] = 2e-8
        self.write(cases.P05_EVIDENCE, value)
        self.assertIn("17.0:masked_overlap_cross_block_norm", cases.ledger("P05", self.root)["failed_checks"])

    def test_p05_roots_are_frozen(self):
        value = self.p05(); value["points"]["17.0"]["roots"] = [8, 40]
        self.write(cases.P05_EVIDENCE, value)
        self.assertIn("17.0:fixed_roots", cases.ledger("P05", self.root)["failed_checks"])

    def test_p06_idempotency_is_reported_not_newly_imposed(self):
        self.p06(); result = cases.ledger("P06", self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["records"][0]["states"]["FUL"]["physical_metric_idempotency_residual"], .07)

    def test_p06_energy_assembly_is_recomputed(self):
        value = self.p06(); value["points"]["0.0"]["states"]["FUL"]["pipeline_energy_hartree"] += 1e-7
        self.write(cases.P06_EVIDENCE, value)
        self.assertIn("0.0:FUL:assembly", cases.ledger("P06", self.root)["failed_checks"])

    def test_p06_occupation_change_is_rejected(self):
        value = self.p06(); value["points"]["0.0"]["states"]["FUL"]["occupied_roots"][-1] = 2
        self.write(cases.P06_EVIDENCE, value)
        self.assertIn("0.0:FUL:groups_and_roots", cases.ledger("P06", self.root)["failed_checks"])

    def test_p06_old_version_record_is_separate(self):
        self.p06(); result = cases.ledger("P06", self.root)
        self.assertEqual(result["historical_environment"]["numpy_runtime"], "historical-version")
        self.assertEqual(result["status"], "PASS")

    def test_live_cannot_lazily_reload_after_guard(self):
        with patch.dict(cases._PREPARED, {}, clear=True):
            with self.assertRaises(RuntimeError): cases.live("P04", self.root)

    def test_native_caps_include_reference_h_and_masked_scf(self):
        self.assertEqual(cases._counts("P04")["scf_kernel_without_newton"], 20)
        self.assertEqual(cases._counts("P05")["scf_kernel_without_newton"], 11)
        self.assertEqual(cases._counts("P06")["scf_kernel_without_newton"], 6)
        self.assertEqual(cases._counts("P04")["group_projector_fixed_point"], 2)
        self.assertEqual(cases._counts("P06")["newton_kernel_maximum_if_original_uhf_fails"], 4)

    def test_guard_caps_are_not_observed_counts(self):
        self.p03(); result = cases.ledger("P03", self.root)
        self.assertEqual(result["expected_scfs"], 0)
        self.assertEqual(result["live_operation_caps"]["kind"], "STATIC_MAXIMUM_CAPS_NOT_OBSERVED_CALL_COUNTS")

    def test_input_path_cannot_escape(self):
        with self.assertRaises(ValueError): cases._path(self.root, "../escape.json")

    def test_bool_cannot_be_reported_as_numeric_energy(self):
        value = self.p03(); value["points"]["0.0"]["energies"]["total_energy_hartree"] = True
        self.write(cases.P03_EVIDENCE, value)
        with self.assertRaises(ValueError): cases.ledger("P03", self.root)


if __name__ == "__main__":
    unittest.main()
