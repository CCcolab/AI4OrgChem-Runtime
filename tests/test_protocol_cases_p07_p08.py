"""Pure frozen-ledger and refusal tests; no quantum backend is executed."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from runtime.protocol_cases import p07_p08 as adapter


def write(root: Path, name: str, value) -> None:
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value), encoding="utf-8")


def fake_yaml(root: Path, name: str):
    # The fixtures are JSON, which is a YAML subset. This makes these pure
    # arithmetic tests independent of the host having a scientific environment.
    return json.loads((root / name).read_text(encoding="utf-8"))


def p07_fixture(root: Path) -> None:
    scope = {"molecule": "diphenyl_imine_parent_nba", "geometry_points_degrees": [0.0, 17.0],
             "electronic_structure_method": "RHF", "basis": "sto-3g",
             "state_path": ["FUL", "PDSI", "DSI2", "FUD", "G"],
             "same_geometry_within_each_angle": True, "same_hamiltonian_for_all_states": True}
    write(root, adapter.P07_CONFIG, {
        "experiment_id": "p07-same-hamiltonian-path-audit/0.2",
        "frozen_scope": scope,
        "acceptance": {"closure_tolerance_hartree": 1e-9,
                       "minimum_naive_residual_hartree": .30,
                       "minimum_bridge_magnitude_hartree": .30,
                       "zero_angle_pi_sigma_tolerance_hartree": 1e-9,
                       "required_angles_degrees": [0.0, 17.0]},
        "boundaries": {"new_qm_calculation": False}})
    write(root, adapter.P07_STATE_CONFIG, {
        "acceptance": {"density_fixed_point_tolerance": 1e-8,
                       "electron_trace_tolerance": 1e-6,
                       "source_cross_block_tolerance": 1e-8,
                       "energy_assembly_tolerance_hartree": 1e-9}})
    points = {}
    for angle in ("0.0", "17.0"):
        energy = {"FUL": -10.0, "PDSI": -9.93, "DSI2": -10.27,
                  "FUD": -10.26}
        states = {name: {"energy_hartree": value, "converged": True,
                         "density_fixed_point_residual": 2e-9,
                         "energy_assembly_residual_hartree": 1e-12,
                         "maximum_source_cross_group_density_norm": 1e-15,
                         "electron_trace": 96.0} for name, value in energy.items()}
        points[angle] = {
            "technical_pass": True, "checks": {"all_source_states_converged": True},
            "expected_electrons": 96,
            "ground": {"converged": True,
                       "energy_hartree": -10.26 if angle == "0.0" else -10.24},
            "states": states,
            "cycle": {"requested_total_hartree": 999999.0}}
    write(root, adapter.P07_RAW, {
        "points": points,
        "boundaries": {"same_rhf_sto3g_hamiltonian_for_all_states": True,
                       "same_geometry_within_each_state_family": True}})
    write(root, adapter.P07_INTEGRATED, {
        "verdict": "P07_SCOPED_MULTI_COMPONENT_MECHANISM_SUPPORTED_WITHOUT_CROSS_PROTOCOL_ENERGY_SUM",
        "argument_matrix": {"P04": {"point_count": 11},
                            "P05": {"point_count": 2},
                            "P06": {"point_count": 2}}})
    audit_points = {}
    for angle, point in points.items():
        energies = {name: state["energy_hartree"] for name, state in point["states"].items()}
        energies["G"] = point["ground"]["energy_hartree"]
        ps, pp = energies["G"] - energies["FUD"], energies["FUD"] - energies["DSI2"]
        ss, bridge = energies["PDSI"] - energies["FUL"], energies["DSI2"] - energies["PDSI"]
        total, sigma_total = energies["G"] - energies["FUL"], energies["DSI2"] - energies["FUL"]
        naive_sum, complete_sum = ps + pp + ss, ps + pp + sigma_total
        audit_points[angle] = {
            "naive_three_terms_hartree": {"pi_sigma_E_G_minus_E_FUD": ps,
                "pi_pi_E_FUD_minus_E_DSI2": pp, "sigma_sigma_subterm_E_PDSI_minus_E_FUL": ss,
                "sum": naive_sum, "closure_residual_vs_E_G_minus_E_FUL": naive_sum - total},
            "required_bridge_hartree": {"value": bridge},
            "four_term_state_path_hartree": {"sum": naive_sum + bridge,
                "closure_residual_vs_E_G_minus_E_FUL": naive_sum + bridge - total},
            "path_complete_three_terms_hartree": {"pi_sigma_E_G_minus_E_FUD": ps,
                "pi_pi_E_FUD_minus_E_DSI2": pp, "sigma_total_E_DSI2_minus_E_FUL": sigma_total,
                "sum": complete_sum, "closure_residual_vs_E_G_minus_E_FUL": complete_sum - total},
            "requested_total_E_G_minus_E_FUL_hartree": total,
            "sigma_total_identity_residual_hartree": sigma_total - (bridge + ss),
            "checks": {"source_technical_pass": True, "four_term_path_closes": True}}
    write(root, adapter.P07_AUDIT, {
        "experiment_id": "p07-same-hamiltonian-path-audit/0.2", "proposition_id": "P07",
        "verdict": adapter.P07_FORMAL_VERDICT, "technical_pass": True,
        "evidence_identity": "INDEPENDENT_COMPUTATIONAL_AUDIT_PLUS_DERIVED_SYNTHESIS",
        "counts_as_independent_computational_audit": True,
        "scope": scope, "points": audit_points, "global_checks": {"source_same_hamiltonian": True},
        "boundaries": dict.fromkeys(("new_qm_calculation", "additional_molecules", "additional_angles",
            "basis_scan", "cross_protocol_energy_sum", "universal_mechanistic_law", "production_label", "ai_training"), False),
        "provenance": {"config": adapter.P07_CONFIG, "input_artifact": adapter.P07_RAW,
                       "input_protocol": adapter.P07_STATE_CONFIG,
                       "supplementary_derived_synthesis": adapter.P07_INTEGRATED}})
    refresh_p07_fixture_hashes(root)


def refresh_p07_fixture_hashes(root: Path) -> None:
    value = json.loads((root / adapter.P07_AUDIT).read_text())
    for field in ("config", "input_artifact", "input_protocol", "supplementary_derived_synthesis"):
        name = value["provenance"][field]
        value["provenance"][field + "_sha256"] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    write(root, adapter.P07_AUDIT, value)


def p08_fixture(root: Path) -> None:
    config = {
        "protocol_id": "p08-butadiene-gl2014-independent/0.1",
        "system": {"charge": 0, "spin": 0, "unit": "Angstrom", "formula": "C4H6",
                   "carbon_fragment_left_atoms": [0, 1],
                   "carbon_fragment_right_atoms": [2, 3]},
        "electronic_structure": {"source_method": "B3LYP", "pyscf_xc": "B3LYPG",
                                 "basis": "6-31G(d)", "grid_level": 3,
                                 "scf_convergence_tolerance": 1e-10, "scf_max_cycles": 180},
        "gl2014_conditional_scf": {"maximum_cycles": 160, "density_tolerance": 2e-8,
                                  "energy_tolerance_hartree": 1e-10,
                                  "density_diis_start_cycle": 3,
                                  "density_diis_space": 10, "damping": .20},
        "acceptance": {"modified_metric_electron_tolerance": 1e-7}}
    write(root, adapter.P08_CONFIG, config)
    write(root, adapter.P08_SOURCE_CONFIG, {
        "protocol_id": "p08-butadiene-three-part/0.1",
        "decision_rules": {"sign_tolerance_kcal_per_mol": .15},
        "subtargets": {"P08_B": {"hydrogenation_enthalpies": {
            "trans_1_3_butadiene": -57.1, "1_butene": -30.3,
            "cis_2_butene": -28.6, "trans_2_butene": -27.6}}}})
    atoms = [["C", -1.4, 1.1, 0.0], ["C", -.7, 0.0, 0.0],
             ["C", .7, 0.0, 0.0], ["C", 1.4, -1.1, 0.0],
             ["H", -.9, 2.1, 0.0], ["H", -2.5, 1.1, 0.0],
             ["H", -1.2, -.96, 0.0], ["H", 1.2, .96, 0.0],
             ["H", 2.5, -1.1, 0.0], ["H", .9, -2.1, 0.0]]
    ground = deepcopy(atoms)
    ground[1][1], ground[2][1] = -.73, .73
    required = (
        "optimizer_reports_success", "optimizer_gradient_max_within_tolerance",
        "no_active_parameter_bound", "final_gl_scf_converged", "one_occupied_pi_per_fragment",
        "no_mixed_occupied_pi", "modified_metric_electron_count_closes", "delta_EA_positive",
        "r23_G_greater_than_r23_GL", "source_energy_value_within_comparison_tolerance",
        "source_r23_GL_within_comparison_tolerance", "p08_b_hydrogenation_reference_subtarget_complete")
    checks = {name: True for name in required}
    checks["ai_training_started"] = False
    delta_energy = -155.98 - -155.99
    delta_bond = 1.46 - 1.4
    geometry_hash = hashlib.sha256(json.dumps(atoms, ensure_ascii=False,
                                            separators=(",", ":")).encode()).hexdigest().upper()
    write(root, adapter.P08_RESULT, {
        "verdict": "P08_SCOPED_BUTADIENE_PROPOSITION_SUPPORTED",
        "checks": checks,
        "ground_geometry": {"atoms": ground, "single_point": {"total_energy_hartree": -155.98}},
        "gl2014_geometry": {"atoms": atoms, "total_energy_hartree": -155.99,
                            "geometry_sha256": geometry_hash,
                            "history": [{"energy_change_hartree": float("inf")} ]},
        "energy_and_geometry_decision": {
            "delta_EA_hartree": delta_energy,
            "delta_EA_kcal_per_mol": delta_energy * adapter.HARTREE_TO_KCAL_PER_MOL,
            "delta_r23_G_minus_GL_angstrom": delta_bond}})
    write(root, adapter.P08_HYDROGENATION, {
        "verdict": "P08_HYDROGENATION_REFERENCE_SIGN_IS_NOT_UNIQUE",
        "source": {"verified_sha256": "07AADF5E25967616C4076C8B732EBB17E9E179F31C6546B6EB06D46E96D4A85D"}})


class P07P08LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        p07_fixture(self.root)
        p08_fixture(self.root)
        self.yaml_patch = patch.object(adapter, "_yaml", side_effect=fake_yaml)
        self.yaml_patch.start()
        self.addCleanup(self.yaml_patch.stop)

    def mutate(self, name, change):
        value = json.loads((self.root / name).read_text())
        change(value)
        write(self.root, name, value)
        if name in (adapter.P07_RAW, adapter.P07_CONFIG, adapter.P07_STATE_CONFIG):
            # Mutated engineering fixtures retain their own synthetic provenance
            # so individual numerical gates, rather than byte-binding alone, run.
            refresh_p07_fixture_hashes(self.root)

    def test_p07_fresh_path_uses_raw_states_not_saved_cycle(self):
        result = adapter.ledger("P07", self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["scientific_call_count"], 0)
        self.assertAlmostEqual(result["points"]["0.0"]["requested_total_hartree"], -.26)
        self.assertAlmostEqual(result["points"]["0.0"]["naive_residual_hartree"], .34)
        self.assertLessEqual(abs(result["points"]["17.0"]["four_term_residual_hartree"]), 1e-9)
        self.assertEqual(result["formal_saved_verdict"], adapter.P07_FORMAL_VERDICT)
        self.assertFalse(result["derived_context"]["counts_as_independent_validation"])
        self.assertEqual(result["derived_context"]["P05_point_count"], 2)
        self.assertTrue(result["formal_saved_counts_as_independent_computational_audit"])

    def test_p07_strong_audit_raw_hash_is_checked(self):
        path = self.root / adapter.P07_RAW
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "source binding"):
            adapter.ledger("P07", self.root)

    def test_p07_formal_verdict_cannot_fall_back_to_weak_derived_context(self):
        self.mutate(adapter.P07_AUDIT, lambda data: data.update(
            verdict="P07_SCOPED_MULTI_COMPONENT_MECHANISM_SUPPORTED_WITHOUT_CROSS_PROTOCOL_ENERGY_SUM"))
        with self.assertRaisesRegex(ValueError, "formal saved.*identity"):
            adapter.ledger("P07", self.root)

    def test_p07_strong_saved_math_must_match_fresh_raw_state_math(self):
        self.mutate(adapter.P07_AUDIT, lambda data: data["points"]["0.0"]["naive_three_terms_hartree"].update(
            pi_pi_E_FUD_minus_E_DSI2=.01001))
        with self.assertRaisesRegex(ValueError, "fresh math differs"):
            adapter.ledger("P07", self.root)

    def test_p07_public_derived_annotations_prove_older_supplementary_bytes(self):
        legacy = json.loads((self.root / adapter.P07_INTEGRATED).read_text())
        original = (json.dumps(legacy, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()
        (self.root / adapter.P07_INTEGRATED).write_bytes(original)
        refresh_p07_fixture_hashes(self.root)
        annotated = dict(legacy, evidence_state="DERIVED", counts_as_independent_validation=False)
        (self.root / adapter.P07_INTEGRATED).write_text(
            json.dumps(annotated, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        result = adapter.ledger("P07", self.root)
        self.assertEqual(result["derived_context"]["historical_byte_binding"],
                         "PUBLIC_DERIVED_ANNOTATIONS_WITH_EXACT_RECONSTRUCTED_HISTORICAL_BYTES")
        self.assertEqual(result["derived_context"]["historical_supplementary_sha256"], hashlib.sha256(original).hexdigest())

    def test_p07_requires_original_state_residual_gate(self):
        self.mutate(adapter.P07_RAW, lambda data: data["points"]["0.0"]["states"]["FUL"].update(
            density_fixed_point_residual=1.01e-8))
        with self.assertRaisesRegex(ValueError, "residual rejected"):
            adapter.ledger("P07", self.root)

    def test_p07_saved_false_check_is_not_promoted(self):
        self.mutate(adapter.P07_RAW, lambda data: data["points"]["0.0"]["checks"].update(
            all_source_states_converged=False))
        with self.assertRaisesRegex(ValueError, "technical check failed"):
            adapter.ledger("P07", self.root)

    def test_p07_threshold_cannot_be_relaxed(self):
        self.mutate(adapter.P07_CONFIG, lambda data: data["acceptance"].update(
            closure_tolerance_hartree=1e-6))
        with self.assertRaisesRegex(ValueError, "threshold changed"):
            adapter.ledger("P07", self.root)

    def test_p07_live_and_unsupported_case_are_refused(self):
        with self.assertRaisesRegex(ValueError, "forbids"):
            adapter.live("P07", self.root)
        with self.assertRaises(ValueError):
            adapter.ledger("P14", self.root)
        self.assertFalse(adapter.preflight("P07", self.root)["live_allowed"])

    def test_p08_all_three_reference_classes_and_scope(self):
        result = adapter.ledger("P08", self.root)
        rows = result["hydrogenation_reference_recalculation"]
        self.assertEqual([r["classification"] for r in rows],
                         ["stabilizing", "near_zero", "destabilizing"])
        self.assertAlmostEqual(rows[0]["delta_E_reference_kcal_per_mol"], -3.5)
        self.assertEqual(result["source_pdf_authentication"], "NOT_EXECUTED_LOCKED_TABLE_REPLAY_ONLY")
        self.assertFalse(result["historical_optimization_result"]["optimization_reexecuted"])
        self.assertEqual(result["scientific_call_count"], 0)
        json.dumps(result, allow_nan=False)

    def test_p08_first_cycle_infinity_diagnostic_is_null_and_registered(self):
        value, notes = adapter._json(self.root, adapter.P08_RESULT)
        self.assertIsNone(value["gl2014_geometry"]["history"][0]["energy_change_hartree"])
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["original"], "Infinity")
        self.assertEqual(len(adapter.ledger("P08", self.root)["source_diagnostic_normalization"]), 1)

    def test_nonfinite_scientific_energy_cannot_be_sanitized(self):
        self.mutate(adapter.P08_RESULT, lambda data: data["gl2014_geometry"].update(
            total_energy_hartree=float("nan")))
        with self.assertRaisesRegex(ValueError, "Non-finite scientific"):
            adapter.ledger("P08", self.root)

    def test_later_cycle_infinity_diagnostic_is_rejected(self):
        self.mutate(adapter.P08_RESULT, lambda data: data["gl2014_geometry"]["history"].append(
            {"energy_change_hartree": float("inf")}))
        with self.assertRaisesRegex(ValueError, "Non-finite scientific"):
            adapter.ledger("P08", self.root)

    def test_p08_incompatible_method_or_fragment_mapping_rejected(self):
        self.mutate(adapter.P08_CONFIG, lambda data: data["system"].update(
            carbon_fragment_left_atoms=[0, 2]))
        with self.assertRaisesRegex(ValueError, "mapping changed"):
            adapter.ledger("P08", self.root)

    def test_p08_stale_historical_energy_identity_rejected(self):
        self.mutate(adapter.P08_RESULT, lambda data: data["energy_and_geometry_decision"].update(
            delta_EA_hartree=.01001))
        with self.assertRaisesRegex(ValueError, "arithmetic failed"):
            adapter.ledger("P08", self.root)

    def test_endpoint_atom_order_and_geometry_hash_are_bound(self):
        config, endpoint, _ = adapter._endpoint(self.root)
        self.assertEqual(config["electronic_structure"]["pyscf_xc"], "B3LYPG")
        self.assertEqual(endpoint["atoms"][0][0], "C")
        self.mutate(adapter.P08_RESULT, lambda data: data["gl2014_geometry"]["atoms"][0].__setitem__(1, -1.41))
        with self.assertRaisesRegex(ValueError, "hash changed"):
            adapter._endpoint(self.root)

    def test_live_requires_prepare_before_guard_installation(self):
        with self.assertRaisesRegex(ValueError, "prepare"):
            adapter.live("P08", self.root)

    def test_duplicate_json_and_nonfinite_unrecognized_diagnostic_rejected(self):
        target = self.root / adapter.P08_RESULT
        target.write_text('{"energy": 1, "energy": 2}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate JSON"):
            adapter._json(self.root, adapter.P08_RESULT)
        with self.assertRaisesRegex(ValueError, "Non-finite scientific"):
            adapter._finite_tree({"diagnostic": float("inf")}, notes=[])

    def test_asset_paths_stay_inside_project_and_pdf_not_distributed(self):
        paths = adapter.assets()
        self.assertEqual(len(paths), len(set(paths)))
        self.assertTrue(all(not Path(path).is_absolute() and ".." not in Path(path).parts for path in paths))
        self.assertFalse(any(path.lower().endswith(".pdf") for path in paths))
        self.assertIn("src/ai4orgchem/lfmo/gl2014.py", paths)


if __name__ == "__main__":
    unittest.main()
