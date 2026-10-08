"""Bounded P07 frozen-ledger and P08 GL(2014) endpoint adapters.

The original scientific GL module is imported without alteration.  P07 never
starts a quantum calculation; P08 live is one ordinary RKS initial density and
one GL calculation at a saved endpoint, not a geometry optimization.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np

HARTREE_TO_KCAL_PER_MOL = 627.5094740631
GL_SOURCE_SHA256 = "617d5dc861b380345488800f47201624dcdd5b2cb232d0952fec198ff7df23c5"
P07_RAW = "artifacts/raw/source_optimized_three_effect_reconstruction_nba_2026-08-14.json"
P07_CONFIG = "configs/qm/p07_same_hamiltonian_path_audit_v0.2.yaml"
P07_STATE_CONFIG = "configs/qm/source_optimized_three_effect_reconstruction_nba_v0.1.yaml"
P07_INTEGRATED = "data/processed/p07_lfmo_core_integrated_mechanism_v0.1.json"
P07_AUDIT = "data/processed/p07_same_hamiltonian_path_audit_v0.2.json"
P07_FORMAL_VERDICT = "P07_CONSISTENT_WITH_INDEPENDENT_SAME_HAMILTONIAN_PATH_AUDIT"
P08_CONFIG = "configs/qm/p08_butadiene_gl2014_v0.1.yaml"
P08_SOURCE_CONFIG = "configs/data/p08_butadiene_source_freeze_v0.1.yaml"
P08_RESULT = "data/processed/p08_butadiene_gl2014_evidence_v0.1.json"
P08_HYDROGENATION = "data/processed/p08_hydrogenation_reference_evidence_v0.1.json"
_PREPARED: dict[str, dict[str, Any]] = {}


def assets() -> list[str]:
    """Original-repository-relative byte closure; no licensed PDF is copied."""
    return [
        P07_CONFIG, P07_STATE_CONFIG,
        "configs/data/p07_lfmo_core_integrated_mechanism_v0.1.yaml",
        P07_RAW, P07_AUDIT,
        P07_INTEGRATED, "scripts/generate_p07_same_hamiltonian_path_audit.py",
        "scripts/validate_p07_same_hamiltonian_path_audit.py",
        P08_SOURCE_CONFIG, P08_CONFIG, P08_HYDROGENATION, P08_RESULT,
        "runs/validation/p08_butadiene_gl2014_independent_initial_density_confirmation_v0.1.json",
        "scripts/confirm_p08_gl2014_final_state.py",
        "scripts/run_p08_butadiene_gl2014.py",
        "scripts/generate_p08_hydrogenation_reference_evidence.py",
        "src/ai4orgchem/__init__.py", "src/ai4orgchem/lfmo/__init__.py",
        "src/ai4orgchem/lfmo/gl2014.py", "src/ai4orgchem/lfmo/state_masks.py",
        "src/ai4orgchem/lfmo/kost.py", "src/ai4orgchem/lfmo/subspaces.py",
        "src/ai4orgchem/lfmo/working_basis.py", "src/ai4orgchem/lfmo/reflection.py",
        "src/ai4orgchem/lfmo/conditional_scf.py",
    ]


def _case(case: str) -> None:
    if case not in {"P07", "P08"}:
        raise ValueError("Only P07 and P08 belong to this adapter")


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise ValueError(name + " must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(name + " must be finite")
    return number


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def _finite_tree(value: Any, path: tuple[Any, ...] = (), notes: list | None = None) -> Any:
    """Only the original first-cycle unset energy-change diagnostic may be null."""
    if isinstance(value, dict):
        return {key: _finite_tree(item, path + (key,), notes) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite_tree(item, path + (index,), notes) for index, item in enumerate(value)]
    if isinstance(value, np.ndarray):
        return _finite_tree(value.tolist(), path, notes)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (np.integer, np.floating)):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        if value == float("inf") and path[-3:] == ("history", 0, "energy_change_hartree"):
            if notes is not None:
                notes.append({"path": "/" + "/".join(map(str, path)),
                              "original": "Infinity", "replacement": None,
                              "reason": "NO_PREVIOUS_ENERGY_AT_INITIAL_CYCLE_DIAGNOSTIC"})
            return None
        raise ValueError("Non-finite scientific/source field: /" + "/".join(map(str, path)))
    return value


def _json(root: Path, relative: str) -> tuple[dict, list]:
    notes: list = []
    data = json.loads((root / relative).read_text(encoding="utf-8"), object_pairs_hook=_pairs)
    data = _finite_tree(data, notes=notes)
    if not isinstance(data, dict):
        raise ValueError("Source JSON must be a mapping")
    return data, notes


def _yaml(root: Path, relative: str) -> dict:
    import yaml
    data = yaml.safe_load((root / relative).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Source YAML must be a mapping")
    return _finite_tree(data)


def _identity(root: Path, relatives: list[str]) -> dict[str, str]:
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in relatives}


def _p07_configs(root: Path) -> tuple[dict, dict]:
    config, state = _yaml(root, P07_CONFIG), _yaml(root, P07_STATE_CONFIG)
    if config.get("experiment_id") != "p07-same-hamiltonian-path-audit/0.2":
        raise ValueError("Wrong frozen P07 path protocol")
    expected = {"closure_tolerance_hartree": 1e-9,
                "minimum_naive_residual_hartree": 0.30,
                "minimum_bridge_magnitude_hartree": 0.30,
                "zero_angle_pi_sigma_tolerance_hartree": 1e-9}
    for name, value in expected.items():
        if _number(config["acceptance"][name], name) != value:
            raise ValueError("P07 original threshold changed: " + name)
    if config["acceptance"]["required_angles_degrees"] != [0.0, 17.0]:
        raise ValueError("P07 frozen two-point scope changed")
    if config["boundaries"].get("new_qm_calculation") is not False:
        raise ValueError("P07 must remain zero new QM")
    for name, value in {"density_fixed_point_tolerance": 1e-8,
                        "electron_trace_tolerance": 1e-6,
                        "source_cross_block_tolerance": 1e-8,
                        "energy_assembly_tolerance_hartree": 1e-9}.items():
        if _number(state["acceptance"][name], name) != value:
            raise ValueError("P07 original state threshold changed: " + name)
    return config, state


def _p07_ledger(root: Path) -> dict:
    config, state_config = _p07_configs(root)
    raw, notes = _json(root, P07_RAW)
    integrated, integrated_notes = _json(root, P07_INTEGRATED)
    formal, formal_notes = _json(root, P07_AUDIT)
    if (formal.get("verdict") != P07_FORMAL_VERDICT or formal.get("technical_pass") is not True
            or formal.get("proposition_id") != "P07"
            or formal.get("experiment_id") != "p07-same-hamiltonian-path-audit/0.2"
            or formal.get("evidence_identity") != "INDEPENDENT_COMPUTATIONAL_AUDIT_PLUS_DERIVED_SYNTHESIS"
            or formal.get("counts_as_independent_computational_audit") is not True):
        raise ValueError("P07 formal saved same-Hamiltonian audit identity failed")
    if formal.get("scope") != config["frozen_scope"] or set(formal["points"]) != {"0.0", "17.0"}:
        raise ValueError("P07 formal saved scope changed")
    if not all(value is True for value in formal["global_checks"].values()):
        raise ValueError("P07 formal saved global check failed")
    for name in ("new_qm_calculation", "additional_molecules", "additional_angles", "basis_scan",
                 "cross_protocol_energy_sum", "universal_mechanistic_law", "production_label", "ai_training"):
        if formal["boundaries"].get(name) is not False:
            raise ValueError("P07 formal saved boundary changed: " + name)
    provenance = formal["provenance"]
    bound_source_hashes = _identity(root, [P07_CONFIG, P07_RAW, P07_STATE_CONFIG])
    for field, hash_field, relative in (
        ("config", "config_sha256", P07_CONFIG),
        ("input_artifact", "input_artifact_sha256", P07_RAW),
        ("input_protocol", "input_protocol_sha256", P07_STATE_CONFIG),
    ):
        if provenance.get(field) != relative or provenance.get(hash_field) != bound_source_hashes[relative]:
            raise ValueError("P07 formal audit source binding failed: " + relative)
    if provenance.get("supplementary_derived_synthesis") != P07_INTEGRATED:
        raise ValueError("P07 supplementary derived-context path changed")
    derived_sha = _identity(root, [P07_INTEGRATED])[P07_INTEGRATED]
    historical_derived_sha = provenance["supplementary_derived_synthesis_sha256"]
    derived_binding = "EXACT_HISTORICAL_DERIVED_CONTEXT_BYTES"
    if derived_sha != historical_derived_sha:
        # The public frozen copy adds two explicit DERIVED annotations. Preserve
        # them, and prove the older supplementary bytes by removing ONLY those
        # annotations and using the original generator's serialization.
        if integrated.get("evidence_state") != "DERIVED" or integrated.get("counts_as_independent_validation") is not False:
            raise ValueError("P07 supplementary-context historical hash differs")
        legacy = dict(integrated)
        legacy.pop("evidence_state")
        legacy.pop("counts_as_independent_validation")
        reconstructed = (json.dumps(legacy, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
        if hashlib.sha256(reconstructed).hexdigest() != historical_derived_sha:
            raise ValueError("P07 public derived annotation compatibility not established")
        derived_binding = "PUBLIC_DERIVED_ANNOTATIONS_WITH_EXACT_RECONSTRUCTED_HISTORICAL_BYTES"
    if set(raw["points"]) != {"0.0", "17.0"}:
        raise ValueError("P07 raw angle set changed")
    points, checks = {}, {}
    for angle in ("0.0", "17.0"):
        point = raw["points"][angle]
        if point.get("technical_pass") is not True or not all(v is True for v in point["checks"].values()):
            raise ValueError("P07 saved state technical check failed")
        if point["ground"].get("converged") is not True:
            raise ValueError("P07 saved ordinary ground state failed")
        states = point["states"]
        if set(states) != {"FUL", "PDSI", "DSI2", "FUD"}:
            raise ValueError("P07 frozen state coverage changed")
        energies = {"G": _number(point["ground"]["energy_hartree"], "G energy")}
        for name, row in states.items():
            if row.get("converged") is not True:
                raise ValueError("P07 saved state did not converge: " + name)
            for field, threshold in (
                ("density_fixed_point_residual", "density_fixed_point_tolerance"),
                ("energy_assembly_residual_hartree", "energy_assembly_tolerance_hartree"),
                ("maximum_source_cross_group_density_norm", "source_cross_block_tolerance"),
            ):
                value = _number(row[field], field)
                if value < 0 or value > state_config["acceptance"][threshold]:
                    raise ValueError("P07 saved state residual rejected: " + field)
            if abs(_number(row["electron_trace"], "electron trace") -
                   _number(point["expected_electrons"], "expected electrons")) > 1e-6:
                raise ValueError("P07 saved electron trace failed")
            energies[name] = _number(row["energy_hartree"], name + " energy")
        pi_sigma = energies["G"] - energies["FUD"]
        pi_pi = energies["FUD"] - energies["DSI2"]
        sigma_subterm = energies["PDSI"] - energies["FUL"]
        bridge = energies["DSI2"] - energies["PDSI"]
        total = energies["G"] - energies["FUL"]
        naive = pi_sigma + pi_pi + sigma_subterm
        complete = pi_sigma + pi_pi + (energies["DSI2"] - energies["FUL"])
        closure = naive + bridge - total
        point_checks = {
            "saved_state_checks_pass": True,
            "naive_three_terms_do_not_close": abs(naive - total) >= 0.30,
            "bridge_is_material": abs(bridge) >= 0.30,
            "four_term_path_closes": abs(closure) <= 1e-9,
            "path_complete_three_terms_close": abs(complete - total) <= 1e-9,
            "sigma_subterm_positive": sigma_subterm > 0,
        }
        checks.update({angle + ":" + key: value for key, value in point_checks.items()})
        points[angle] = {"energies_hartree": energies,
                         "pi_sigma_hartree": pi_sigma, "pi_pi_hartree": pi_pi,
                         "sigma_subterm_hartree": sigma_subterm,
                         "bridge_hartree": bridge, "requested_total_hartree": total,
                         "naive_sum_hartree": naive,
                         "naive_residual_hartree": naive - total,
                         "four_term_residual_hartree": closure,
                         "path_complete_residual_hartree": complete - total,
                         "checks": point_checks,
                         "historical_source_state_checks": point["checks"]}
    checks["zero_angle_pi_sigma_control"] = abs(points["0.0"]["pi_sigma_hartree"]) <= 1e-9
    checks["seventeen_degree_pi_sigma_positive"] = points["17.0"]["pi_sigma_hartree"] > 0
    checks["raw_same_hamiltonian"] = raw["boundaries"].get("same_rhf_sto3g_hamiltonian_for_all_states") is True
    checks["raw_same_geometry_per_angle"] = raw["boundaries"].get("same_geometry_within_each_state_family") is True
    if not all(checks.values()):
        raise ValueError("P07 fresh frozen-ledger arithmetic failed")
    comparisons = {}
    for angle, point in points.items():
        saved = formal["points"][angle]
        if not all(value is True for value in saved["checks"].values()):
            raise ValueError("P07 formal saved point check failed: " + angle)
        naive_saved = saved["naive_three_terms_hartree"]
        complete_saved = saved["path_complete_three_terms_hartree"]
        energies = point["energies_hartree"]
        sigma_total = energies["DSI2"] - energies["FUL"]
        pairs = {
            "pi_sigma": (point["pi_sigma_hartree"], naive_saved["pi_sigma_E_G_minus_E_FUD"]),
            "pi_pi": (point["pi_pi_hartree"], naive_saved["pi_pi_E_FUD_minus_E_DSI2"]),
            "sigma_subterm": (point["sigma_subterm_hartree"], naive_saved["sigma_sigma_subterm_E_PDSI_minus_E_FUL"]),
            "naive_sum": (point["naive_sum_hartree"], naive_saved["sum"]),
            "naive_residual": (point["naive_residual_hartree"], naive_saved["closure_residual_vs_E_G_minus_E_FUL"]),
            "bridge": (point["bridge_hartree"], saved["required_bridge_hartree"]["value"]),
            "four_term_sum": (point["naive_sum_hartree"] + point["bridge_hartree"], saved["four_term_state_path_hartree"]["sum"]),
            "four_term_residual": (point["four_term_residual_hartree"], saved["four_term_state_path_hartree"]["closure_residual_vs_E_G_minus_E_FUL"]),
            "complete_pi_sigma": (point["pi_sigma_hartree"], complete_saved["pi_sigma_E_G_minus_E_FUD"]),
            "complete_pi_pi": (point["pi_pi_hartree"], complete_saved["pi_pi_E_FUD_minus_E_DSI2"]),
            "sigma_total": (sigma_total, complete_saved["sigma_total_E_DSI2_minus_E_FUL"]),
            "complete_sum": (point["pi_sigma_hartree"] + point["pi_pi_hartree"] + sigma_total, complete_saved["sum"]),
            "complete_residual": (point["path_complete_residual_hartree"], complete_saved["closure_residual_vs_E_G_minus_E_FUL"]),
            "requested_total": (point["requested_total_hartree"], saved["requested_total_E_G_minus_E_FUL_hartree"]),
            "sigma_bridge_identity_residual": (sigma_total - (point["bridge_hartree"] + point["sigma_subterm_hartree"]), saved["sigma_total_identity_residual_hartree"]),
        }
        residuals = {name: abs(_number(current, name) - _number(old, "saved " + name))
                     for name, (current, old) in pairs.items()}
        if any(value > 1e-9 for value in residuals.values()):
            raise ValueError("P07 fresh math differs from the formal saved audit: " + angle)
        comparisons[angle] = residuals
    checks["formal_saved_audit_reproduced_from_bound_raw_states"] = True
    return {"case": "P07", "mode": "ledger", "status": "PASS",
            "scope_status": "PASS_SCOPED_P07_FROZEN_STATE_PATH_RECALCULATION", "failed_checks": [],
            "protocol_id": config["experiment_id"], "scientific_call_count": 0,
            "points": points, "checks": checks,
            "formal_saved_verdict": formal["verdict"],
            "formal_saved_evidence_identity": formal["evidence_identity"],
            "formal_saved_counts_as_independent_computational_audit": True,
            "formal_audit_comparison_residuals_hartree": comparisons,
            "source_files_sha256": _identity(root, [P07_CONFIG, P07_STATE_CONFIG, P07_RAW, P07_AUDIT, P07_INTEGRATED]),
            "source_diagnostic_normalization": notes + integrated_notes + formal_notes,
            "derived_context": {
                "identity": "DERIVED_SAVED_MATRIX_NOT_NEW_INDEPENDENT_QM",
                "counts_as_independent_validation": False,
                "saved_verdict": integrated["verdict"],
                "current_sha256": derived_sha,
                "historical_supplementary_sha256": historical_derived_sha,
                "historical_byte_binding": derived_binding,
                "P04_point_count": integrated["argument_matrix"]["P04"]["point_count"],
                "P05_point_count": integrated["argument_matrix"]["P05"]["point_count"],
                "P06_point_count": integrated["argument_matrix"]["P06"]["point_count"],
                "matrix_scope": "SAVED_TWO_ANGLE_P05_NOT_LATER_SEVEN_ANGLE_INTEGRATION",
                "full_target_source_validator_rerun": "NOT_EXECUTED"},
            "scope": {"new_qm_calculation": False, "cross_protocol_energy_sum": False,
                      "new_optimization": False, "production_label": False,
                      "training_eligible": False, "universal_mechanistic_law": False}}


def _p08_config(root: Path) -> dict:
    config = _yaml(root, P08_CONFIG)
    if config.get("protocol_id") != "p08-butadiene-gl2014-independent/0.1":
        raise ValueError("Wrong P08 frozen scientific protocol")
    expected = {"source_method": "B3LYP", "pyscf_xc": "B3LYPG", "basis": "6-31G(d)",
                "grid_level": 3, "scf_convergence_tolerance": 1e-10, "scf_max_cycles": 180}
    if config["electronic_structure"] != expected:
        raise ValueError("P08 original method/basis/grid/SCF settings changed")
    options = {"maximum_cycles": 160, "density_tolerance": 2e-8,
               "energy_tolerance_hartree": 1e-10, "density_diis_start_cycle": 3,
               "density_diis_space": 10, "damping": 0.20}
    if config["gl2014_conditional_scf"] != options:
        raise ValueError("P08 original GL settings changed")
    system = config["system"]
    if (system["charge"], system["spin"], system["unit"], system["formula"]) != (0, 0, "Angstrom", "C4H6"):
        raise ValueError("P08 frozen molecular scope changed")
    if system["carbon_fragment_left_atoms"] != [0, 1] or system["carbon_fragment_right_atoms"] != [2, 3]:
        raise ValueError("P08 pi fragment atom mapping changed")
    if config["acceptance"]["modified_metric_electron_tolerance"] != 1e-7:
        raise ValueError("P08 modified-metric electron threshold changed")
    return config


def _distance(atoms: list, first: int = 1, second: int = 2) -> float:
    xyz = np.asarray([row[1:4] for row in atoms], dtype=float)
    if xyz.shape != (10, 3) or not np.isfinite(xyz).all():
        raise ValueError("P08 endpoint requires ten finite atom coordinates")
    if [row[0] for row in atoms] != ["C"] * 4 + ["H"] * 6:
        raise ValueError("P08 frozen atom order changed")
    return float(np.linalg.norm(xyz[first] - xyz[second]))


def _p08_ledger(root: Path) -> dict:
    config = _p08_config(root)
    source = _yaml(root, P08_SOURCE_CONFIG)
    result, notes = _json(root, P08_RESULT)
    stored_b, b_notes = _json(root, P08_HYDROGENATION)
    if source["protocol_id"] != "p08-butadiene-three-part/0.1":
        raise ValueError("Wrong P08 three-part source protocol")
    tolerance = _number(source["decision_rules"]["sign_tolerance_kcal_per_mol"], "P08-B sign tolerance")
    if tolerance != 0.15:
        raise ValueError("P08-B original sign tolerance changed")
    heats = source["subtargets"]["P08_B"]["hydrogenation_enthalpies"]
    if heats != {"trans_1_3_butadiene": -57.1, "1_butene": -30.3,
                 "cis_2_butene": -28.6, "trans_2_butene": -27.6}:
        raise ValueError("P08-B frozen source table changed")
    refs = []
    for name, expected in (("1_butene", -3.5), ("cis_2_butene", -0.1), ("trans_2_butene", 1.9)):
        value = 2 * _number(heats[name], "reference heat") - _number(heats["trans_1_3_butadiene"], "butadiene heat")
        error = abs(value - expected)
        if error > 1e-12:
            raise ValueError("P08-B printed table arithmetic failed")
        refs.append({"reference": name, "delta_E_reference_kcal_per_mol": value,
                     "classification": "destabilizing" if value > tolerance else
                                       "stabilizing" if value < -tolerance else "near_zero",
                     "absolute_table_reproduction_error_kcal_per_mol": error})
    if stored_b["verdict"] != "P08_HYDROGENATION_REFERENCE_SIGN_IS_NOT_UNIQUE":
        raise ValueError("Wrong stored P08-B verdict")
    required = {"optimizer_reports_success", "optimizer_gradient_max_within_tolerance",
                "no_active_parameter_bound", "final_gl_scf_converged", "one_occupied_pi_per_fragment",
                "no_mixed_occupied_pi", "modified_metric_electron_count_closes", "delta_EA_positive",
                "r23_G_greater_than_r23_GL", "source_energy_value_within_comparison_tolerance",
                "source_r23_GL_within_comparison_tolerance", "p08_b_hydrogenation_reference_subtarget_complete"}
    if set(result["checks"]) != required | {"ai_training_started"} or not all(result["checks"][key] is True for key in required):
        raise ValueError("P08 saved final evidence check failed")
    if result["checks"]["ai_training_started"] is not False:
        raise ValueError("P08 scientific evidence does not authorize training")
    ground, gl = result["ground_geometry"], result["gl2014_geometry"]
    energy_difference = _number(ground["single_point"]["total_energy_hartree"], "G energy") - _number(gl["total_energy_hartree"], "GL energy")
    bond_difference = _distance(ground["atoms"]) - _distance(gl["atoms"])
    decision = result["energy_and_geometry_decision"]
    arithmetic_checks = {
        "three_hydrogenation_classes": {row["classification"] for row in refs} == {"stabilizing", "near_zero", "destabilizing"},
        "saved_G_GL_energy_difference_reassembled": abs(energy_difference - _number(decision["delta_EA_hartree"], "stored delta EA")) <= 1e-12,
        "saved_energy_unit_conversion": abs(energy_difference * HARTREE_TO_KCAL_PER_MOL - _number(decision["delta_EA_kcal_per_mol"], "stored kcal")) <= 1e-10,
        "saved_central_bond_difference_reassembled": abs(bond_difference - _number(decision["delta_r23_G_minus_GL_angstrom"], "stored bond difference")) <= 1e-12,
        "saved_GL_endpoint_xy": max(abs(_number(row[3], "z coordinate")) for row in gl["atoms"]) <= 1e-12,
        "saved_required_checks_pass": True,
    }
    if not all(arithmetic_checks.values()):
        raise ValueError("P08 frozen-ledger arithmetic failed")
    return {"case": "P08", "mode": "ledger", "status": "PASS",
            "scope_status": "PASS_SCOPED_P08_FROZEN_LEDGER_RECALCULATION", "failed_checks": [],
            "protocol_id": config["protocol_id"], "scientific_call_count": 0,
            "hydrogenation_reference_recalculation": refs, "checks": arithmetic_checks,
            "historical_optimization_result": {
                "delta_EA_hartree": energy_difference,
                "delta_EA_kcal_per_mol": energy_difference * HARTREE_TO_KCAL_PER_MOL,
                "delta_r23_G_minus_GL_angstrom": bond_difference,
                "saved_verdict": result["verdict"], "checks": result["checks"],
                "optimization_reexecuted": False},
            "source_pdf_authentication": "NOT_EXECUTED_LOCKED_TABLE_REPLAY_ONLY",
            "historical_source_pdf_sha256": stored_b["source"]["verified_sha256"],
            "source_diagnostic_normalization": notes + b_notes,
            "source_files_sha256": _identity(root, [P08_CONFIG, P08_SOURCE_CONFIG, P08_RESULT, P08_HYDROGENATION]),
            "scope": {"new_qm_calculation": False, "new_optimization": False,
                      "cross_protocol_energy_sum": False, "production_label": False,
                      "training_eligible": False, "universal_conjugation_law": False}}


def ledger(case: str, root: Path) -> dict:
    _case(case)
    root = Path(root)
    value = _p07_ledger(root) if case == "P07" else _p08_ledger(root)
    json.dumps(value, allow_nan=False)
    return value


def prepare(case: str, root: Path) -> None:
    """Load once before the caller installs its held dispatch guard."""
    _case(case)
    if case == "P07":
        return
    root = Path(root).resolve()
    for directory in (root / "src", root / "experiments/validation"):
        text = str(directory)
        if text not in sys.path:
            sys.path.insert(0, text)
    from pyscf import dft, gto, lib
    module = importlib.import_module("ai4orgchem.lfmo.gl2014")
    expected = root / "src/ai4orgchem/lfmo/gl2014.py"
    if Path(module.__file__).resolve() != expected.resolve():
        raise ValueError("P08 scientific module is outside the supplied source snapshot")
    if hashlib.sha256(expected.read_bytes()).hexdigest() != GL_SOURCE_SHA256:
        raise ValueError("P08 original GL scientific source bytes changed")
    _PREPARED[str(root)] = {"gto": gto, "dft": dft, "lib": lib, "gl": module}


def _endpoint(root: Path) -> tuple[dict, dict, list]:
    config = _p08_config(root)
    evidence, notes = _json(root, P08_RESULT)
    endpoint = evidence["gl2014_geometry"]
    _distance(endpoint["atoms"])
    if max(abs(float(row[3])) for row in endpoint["atoms"]) > 1e-12:
        raise ValueError("P08 fixed GL endpoint must retain its xy orientation")
    encoded = json.dumps(endpoint["atoms"], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if hashlib.sha256(encoded).hexdigest().upper() != endpoint["geometry_sha256"]:
        raise ValueError("P08 fixed endpoint geometry hash changed")
    return config, endpoint, notes


def preflight(case: str, root: Path) -> dict:
    _case(case)
    if case == "P07":
        return {"case": case, "status": "PASS", "scope_status": "PASS_P07_LEDGER_ONLY_PREFLIGHT",
                "live_allowed": False, "expected_scientific_entries": {},
                "scope": "FROZEN_TWO_ANGLE_LEDGER_ONLY_NO_AO_OR_QM"}
    root = Path(root).resolve()
    config, endpoint, notes = _endpoint(root)
    prepared = _PREPARED.get(str(root))
    if prepared is None:
        from pyscf import gto
    else:
        gto = prepared["gto"]
    molecule = gto.M(atom=endpoint["atoms"], basis=config["electronic_structure"]["basis"],
                     charge=0, spin=0, unit="Angstrom", symmetry=False, verbose=0)
    if molecule.nao_nr() != 68 or molecule.nelectron != 30:
        raise ValueError("P08 actual backend AO/electron scope does not match the frozen profile")
    return {"case": case, "status": "PASS", "scope_status": "PASS_P08_FIXED_ENDPOINT_AO_PREFLIGHT",
            "actual_nao": int(molecule.nao_nr()), "actual_electrons": int(molecule.nelectron),
            "live_allowed": True, "geometry_sha256": endpoint["geometry_sha256"],
            "expected_scientific_entries": {"ordinary_RKS_kernel": 1, "run_gl2014_scf": 1},
            "scf_kernel_calls_in_preflight": 0,
            "source_diagnostic_normalization": notes,
            "scope": "SAVED_GL_ENDPOINT_NOT_OPTIMIZATION_OR_FULL_P08_REPLAY"}


def live(case: str, root: Path) -> dict:
    _case(case)
    if case == "P07":
        raise ValueError("P07 protocol forbids a new live quantum calculation")
    root = Path(root).resolve()
    prepared = _PREPARED.get(str(root))
    if prepared is None:
        raise ValueError("Call prepare before installing the held native guard")
    config, endpoint, notes = _endpoint(root)
    prepared["lib"].num_threads(2)
    molecule = prepared["gto"].M(atom=endpoint["atoms"], basis="6-31G(d)", charge=0,
                                 spin=0, unit="Angstrom", symmetry=False, verbose=0)
    if molecule.nao_nr() != 68 or molecule.nelectron != 30:
        raise ValueError("P08 actual AO scope changed after preflight")

    def mean_field():
        value = prepared["dft"].RKS(molecule)
        value.verbose = 0
        value.xc = "B3LYPG"
        value.grids.level = 3
        value.conv_tol = 1e-10
        value.max_cycle = 180
        value.max_memory = 2048
        return value

    ordinary = mean_field()
    ordinary_energy = _number(ordinary.kernel(), "ordinary RKS energy")
    if ordinary.converged is not True:
        raise ValueError("P08 ordinary fixed-GL-endpoint RKS did not converge")
    initial_density = np.asarray(ordinary.make_rdm1(), dtype=float)
    if not np.isfinite(initial_density).all():
        raise ValueError("P08 ordinary seed density is non-finite")
    options = config["gl2014_conditional_scf"]
    gl = prepared["gl"].run_gl2014_scf(
        mean_field(), config["system"]["carbon_fragment_left_atoms"],
        config["system"]["carbon_fragment_right_atoms"], initial_density=initial_density,
        maximum_cycles=options["maximum_cycles"], density_tolerance=options["density_tolerance"],
        energy_tolerance=options["energy_tolerance_hartree"],
        density_diis_start_cycle=options["density_diis_start_cycle"],
        density_diis_space=options["density_diis_space"], damping=options["damping"])
    live_notes: list = []
    safe = _finite_tree(gl, notes=live_notes)
    final_energy = _number(safe["total_energy_hartree"], "GL energy")
    energy_error = abs(final_energy - _number(endpoint["total_energy_hartree"], "frozen GL energy"))
    audit = safe["occupied_pi_audit"]
    last = safe["history"][-1]
    checks = {
        "ordinary_initial_density_converged": True,
        "conditional_state_converged": safe["converged"] is True,
        "energy_reproduced_within_original_1e_minus_9_hartree": energy_error <= 1e-9,
        "one_occupied_pi_per_fragment": audit["left_occupied_pi_count"] == 1 and audit["right_occupied_pi_count"] == 1,
        "no_mixed_occupied_pi": audit["mixed_occupied_pi_count"] == 0,
        "modified_metric_electron_count_closes": abs(_number(safe["modified_metric_electron_count"], "modified electrons") - 30) <= 1e-7,
        "original_density_residual_gate": _number(last["density_residual"], "GL final density residual") <= 2e-8,
        "original_energy_change_gate": _number(last["energy_change_hartree"], "GL final energy change") <= 1e-10,
        "modified_overlap_positive": _number(safe["modified_overlap_minimum_eigenvalue"], "overlap minimum eigenvalue") > 0,
    }
    passed = all(checks.values())
    output = {"case": "P08", "mode": "live",
              "status": "PASS" if passed else "NOT_QUALIFIED",
              "scope_status": "PASS_SCOPED_P08_FIXED_GL_ENDPOINT" if passed else "FAIL_P08_FIXED_GL_ENDPOINT_CHECKS",
              "failed_checks": [name for name, accepted in checks.items() if not accepted],
              "protocol_id": config["protocol_id"], "checks": checks,
              "geometry_sha256": endpoint["geometry_sha256"], "actual_nao": 68,
              "ordinary_RKS_at_GL_geometry_energy_hartree": ordinary_energy,
              "frozen_GL_energy_hartree": endpoint["total_energy_hartree"],
              "recomputed_GL_energy_hartree": final_energy,
              "absolute_GL_energy_error_hartree": energy_error,
              "conditional_cycles": safe["cycles"],
              "modified_metric_electron_count": safe["modified_metric_electron_count"],
              "physical_metric_electron_count": safe["physical_metric_electron_count"],
              "occupied_pi_audit": audit, "GL_history": safe["history"],
              "source_diagnostic_normalization": notes,
              "live_diagnostic_normalization": live_notes,
              "source_files_sha256": _identity(root, [P08_CONFIG, P08_RESULT, "src/ai4orgchem/lfmo/gl2014.py"]),
              "scientific_entry_budget": {"ordinary_RKS_kernel": 1, "run_gl2014_scf": 1},
              "counter_scope": "DISPATCH_COUNTS_SUPPLIED_BY_OWNED_HELD_GUARD_NOT_THIS_DRIVER",
              "resource_settings": {"pyscf_threads": 2, "pyscf_max_memory_MB": 2048},
              "scope": {"new_optimization": False, "full_P08_replay": False,
                        "same_implementation_initial_density_check": True,
                        "second_program_replication": False, "new_P08_scientific_verdict": False,
                        "ordinary_general_compute_or_old_conditional_compute_enablement": False,
                        "production_label": False, "training_eligible": False}}
    json.dumps(output, allow_nan=False)
    return output
