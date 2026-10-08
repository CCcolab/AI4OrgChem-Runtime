"""Frozen P03--P06 ledger replay and one original-protocol point per case.

No old main function, optimizer, output writer or multi-angle runner is called.
The caller supplies a separately hash-locked, read-only source tree and owns
authorization, native guards, resource limits and writing returned records.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np


_CODE = (
    "scripts/__init__.py",
    "scripts/run_p03_parent_nba_relaxed_pes.py",
    "scripts/run_target_c_source_native_reporting_basis_direct_response.py",
    "experiments/validation/chapter5_pi_sigma_reconstruction_gate0.py",
    "experiments/validation/chapter5_three_effect_reconstruction_gate0.py",
    "experiments/validation/dsi2_divinyl_imine_source_shaped_gate0.py",
    "experiments/validation/dsi2_divinyl_imine_torsion_continuation_gate0.py",
    "experiments/validation/dsi_fud_initial_density_reproducibility_gate0.py",
    "experiments/validation/dsi_lfmo_n_state_specific_reconstruction_gate0.py",
    "experiments/validation/kost_single_step_gate0.py",
    "experiments/validation/kost_vacant_loop_gate0.py",
    "experiments/validation/one_cut_ch3_reference_h_gate0.py",
    "experiments/validation/one_cut_conditional_scf_gate0.py",
    "experiments/validation/source_nonvariational_pi_sigma_nba_gate0.py",
    "experiments/validation/source_nonvariational_sigma_sigma_nba_gate0.py",
    "experiments/validation/source_optimized_dual_density_nba_gate0.py",
    "experiments/validation/source_optimized_physical_direct_response_nba_gate0.py",
    "experiments/validation/source_optimized_table_5_15_pi_sigma_nba_gate0.py",
    "experiments/validation/source_optimized_three_effect_reconstruction_nba_gate0.py",
    "experiments/validation/source_table_5_19_independent_assembly_gate0.py",
    "experiments/validation/two_cut_ch2_four_column_gate0.py",
    "experiments/validation/two_cut_ch2_uhf_gate0.py",
    "src/ai4orgchem/__init__.py",
    "src/ai4orgchem/lfmo/__init__.py",
    "src/ai4orgchem/lfmo/conditional_scf.py",
    "src/ai4orgchem/lfmo/kost.py",
    "src/ai4orgchem/lfmo/reflection.py",
    "src/ai4orgchem/lfmo/state_masks.py",
    "src/ai4orgchem/lfmo/subspaces.py",
)
_CONFIG = (
    "configs/qm/p03_parent_nba_relaxed_pes_v0.1.yaml",
    "configs/qm/geometries/source_nba_b3lypg_6311gdp_0_17_v0.1.json",
    "configs/qm/target_c_source_native_reporting_basis_direct_response_v0.1.yaml",
    "configs/qm/dsi3_diphenyl_source_metric_v0.1.yaml",
    "configs/qm/fud_diphenyl_source_metric_v0.1.yaml",
    "configs/qm/dsi2_diphenyl_imine_source_shaped_v0.1.yaml",
    "configs/qm/fud_diphenyl_imine_source_shaped_v0.1.yaml",
    "configs/qm/p05_target_a_seven_angle_continuation_v0.2.yaml",
    "configs/qm/source_table_5_15_fixed_twist_pi_sigma_nba_v1.0.yaml",
    "configs/qm/source_table_5_19_independent_assembly_v1.0.yaml",
    "configs/qm/source_nonvariational_sigma_sigma_nba_v0.1.yaml",
    "configs/qm/source_geometry_matched_sigma_sigma_nba_v0.1.yaml",
    "configs/qm/protocol_v0.5.yaml",
    "configs/data/target_c_tested_domain_scientific_conclusion_v0.1.yaml",
    "configs/data/target_a_table_5_15_scoped_scientific_conclusion_v0.1.yaml",
    "configs/data/target_b_table_5_19_scoped_scientific_conclusion_v0.1.yaml",
    "configs/resources/local_wsl.yaml",
)
P03_EVIDENCE = "data/processed/p03_parent_nba_relaxed_pes_evidence_v0.1.json"
P04_LABELS = "data/processed/target_c_tested_domain_scientific_labels_v0.1.jsonl"
P05_EVIDENCE = "artifacts/raw/p05_target_a_seven_angle_continuation_2026-09-08.json"
P05_ANCHOR = "artifacts/raw/source_table_5_15_fixed_twist_pi_sigma_nba_2026-08-15.json"
P06_EVIDENCE = "artifacts/raw/source_table_5_19_independent_assembly_2026-08-15.json"
_DATA = (
    P03_EVIDENCE, P04_LABELS, P05_EVIDENCE, P05_ANCHOR, P06_EVIDENCE,
    "artifacts/raw/target_c_source_proxy_geometry_window_2026-08-16.json",
    "artifacts/raw/target_c_source_proxy_phenyl_vinyl_check_2026-08-16.json",
    "artifacts/raw/target_c_source_proxy_cross_family_2026-08-16.json",
    "artifacts/raw/target_c_source_native_reporting_basis_direct_response_2026-08-16.json",
    "artifacts/raw/source_metric_diphenyl_diagnostic_energy_2026-08-15.json",
    "artifacts/raw/source_metric_diphenyl_diagnostic_energy_17_2026-08-15.json",
)
_PROTOCOL = {
    "P03": "p03-parent-nba-relaxed-pes/0.1",
    "P04": "lfmo-sigma-pi/0.5-target-c-scoped-release",
    "P05": "source-equivalent-reconstruction/table-5-15-seven-angle-continuation/0.2",
    "P06": "lfmo-sigma-pi/p06-target-b-table-5-19-scoped-release/0.1",
}
_LIVE_SCRIPT = {
    "P03": "scripts/run_p03_parent_nba_relaxed_pes.py",
    "P04": "scripts/run_target_c_source_native_reporting_basis_direct_response.py",
    "P05": "experiments/validation/source_optimized_table_5_15_pi_sigma_nba_gate0.py",
    "P06": "experiments/validation/source_table_5_19_independent_assembly_gate0.py",
}
_PREPARED: dict[tuple[str, str], Any] = {}
_ACTIVE_ROOT: Path | None = None


def assets() -> list[str]:
    """Explicit source/ROOT-read closure, captured by the caller without edits."""
    return sorted(set((*_CODE, *_CONFIG, *_DATA)))


def _case(case: str) -> str:
    if case not in _PROTOCOL:
        raise ValueError("Only frozen P03, P04, P05 and P06 cases are allowed")
    return case


def _path(root: Path, relative: str) -> Path:
    root = Path(root).resolve()
    path = root / relative
    if path.resolve().parent != root and root not in path.resolve().parents:
        raise ValueError("Source input escapes the supplied source tree")
    if path.is_symlink() or not path.is_file():
        raise ValueError("Source asset must be a regular file: " + relative)
    return path


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in items:
        if key in out:
            raise ValueError("Duplicate JSON key: " + key)
        out[key] = value
    return out


def _loads(text: str) -> Any:
    def bad_constant(value: str) -> None:
        raise ValueError("Nonfinite JSON token: " + value)
    value = json.loads(text, object_pairs_hook=_pairs, parse_constant=bad_constant)
    json.dumps(value, allow_nan=False)
    return value


def _read(root: Path, relative: str) -> Any:
    return _loads(_path(root, relative).read_text(encoding="utf-8-sig"))


def _sha(root: Path, relative: str) -> str:
    return hashlib.sha256(_path(root, relative).read_bytes()).hexdigest()


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise ValueError(name + " must be a real finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(name + " must be finite")
    return number


def _all_true(value: Any) -> bool:
    return isinstance(value, dict) and bool(value) and all(v is True for v in value.values())


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return _safe(value.tolist())
    if isinstance(value, np.generic):
        return _safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Nonfinite scientific result cannot be qualified")
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise ValueError("Unexpected nonserializable scientific result: " + type(value).__name__)


def _counts(case: str) -> dict[str, Any]:
    # Reference-H UHF is included. Custom group fixed points are not kernels.
    caps = {
        "P03": (0, 0, 1, 0, 0, 0),
        "P04": (14, 6, 0, 2, 14, 0),
        "P05": (7, 3, 1, 2, 7, 0),
        "P06": (4, 2, 0, 2, 4, 0),
    }
    uhf, masked, ordinary, fixed, fallback, opt = caps[_case(case)]
    return {
        "kind": "STATIC_MAXIMUM_CAPS_NOT_OBSERVED_CALL_COUNTS",
        "uhf_kernel": uhf, "masked_rhf_kernel": masked,
        "ordinary_rhf_or_rks_kernel": ordinary,
        "scf_kernel_without_newton": uhf + masked + ordinary,
        "newton_kernel_maximum_if_original_uhf_fails": fallback,
        "group_projector_fixed_point": fixed,
        "group_fixed_point_maximum_cycles_per_call": 200 if fixed else 0,
        "geometry_optimizer": opt, "boys_kernel": 0, "pipek_mezey_kernel": 0,
        "kost_bound_per_source_fragment": {
            "maximum_cycles": 3, "maximum_macro_cycles": 12,
            "occupied_maximum_sweeps": 8,
        } if case != "P03" else None,
    }


def _result(case: str, mode: str, records: list[dict[str, Any]],
            checks: dict[str, bool], sources: list[dict[str, Any]],
            limitations: list[str]) -> dict[str, Any]:
    value = {
        "case": _case(case), "mode": mode, "protocol_id": _PROTOCOL[case],
        "records": records, "checks": checks,
        "technical_pass": bool(checks) and all(v is True for v in checks.values()),
        "scopes": {
            "frozen_case_only": True, "new_user_conditional_compute_enabled": False,
            "production_labels_allowed": False, "training_eligible": False,
            "historical_outputs_rewritten": False, "original_main_called": False,
        },
        "source_artifacts": sources, "limitations": limitations,
        "live_operation_caps": _counts(case),
    }
    value["failed_checks"] = sorted(k for k, v in checks.items() if v is not True)
    value["status"] = "PASS" if value["technical_pass"] else "NOT_QUALIFIED"
    value["expected_scfs"] = _counts(case)["scf_kernel_without_newton"] if mode == "ONE_FROZEN_ORIGINAL_PROTOCOL_POINT" else 0
    value["expected_group_fixed_points"] = _counts(case)["group_projector_fixed_point"] if mode == "ONE_FROZEN_ORIGINAL_PROTOCOL_POINT" else 0
    return _safe(value)


def _source(root: Path, relative: str) -> dict[str, Any]:
    return {"path": relative, "sha256": _sha(root, relative)}


def _ledger_p03(root: Path) -> dict[str, Any]:
    evidence = _read(root, P03_EVIDENCE)
    points = evidence["points"]
    expected = ["0.0", "20.0", "40.0", "60.0"]
    if set(points) != set(expected):
        raise ValueError("Frozen P03 four-angle coverage changed")
    records = []
    checks: dict[str, bool] = {}
    for angle in expected:
        point = points[angle]
        geo, energy = point["geometry"], point["energies"]
        total = _number(energy["total_energy_hartree"], "E")
        electronic = _number(energy["electronic_energy_hartree"], "Ee")
        nuclear = _number(energy["nuclear_repulsion_hartree"], "EN")
        residual = abs(total - electronic - nuclear)
        checks[angle + ":energy_identity"] = residual <= 1e-9
        checks[angle + ":saved_scf_converged"] = energy["scf_converged"] is True
        checks[angle + ":saved_optimizer_converged"] = geo["optimizer_converged"] is True
        checks[angle + ":twist"] = abs(_number(geo["achieved_twist_degrees"], "twist") - float(angle)) <= .08
        checks[angle + ":requested_twist"] = _number(geo["requested_twist_degrees"], "requested twist") == float(angle)
        records.append({"angle_degrees": float(angle), "total_energy_hartree": total,
                        "electronic_energy_hartree": electronic,
                        "nuclear_repulsion_hartree": nuclear,
                        "energy_closure_residual_hartree": residual,
                        "geometry_sha256": geo["geometry_sha256"]})
    minimum_index = int(np.argmin([r["total_energy_hartree"] for r in records]))
    checks["sampled_total_minimum_not_at_boundary"] = minimum_index not in (0, 3)
    checks["at_least_two_lower_branch_intervals"] = minimum_index >= 2
    checks["historical_sampled_minimum_40_degrees"] = float(expected[minimum_index]) == 40.
    intervals = []
    for index in range(1, minimum_index + 1):
        before, after = records[index - 1], records[index]
        dt = after["total_energy_hartree"] - before["total_energy_hartree"]
        de = after["electronic_energy_hartree"] - before["electronic_energy_hartree"]
        dn = after["nuclear_repulsion_hartree"] - before["nuclear_repulsion_hartree"]
        name = f"{expected[index-1]}->{expected[index]}"
        checks[name + ":electronic_drives"] = de < -1e-7
        checks[name + ":nuclear_opposes"] = dn > 1e-7
        checks[name + ":total_decreases"] = dt < -1e-7
        checks[name + ":identity"] = abs(dt - de - dn) <= 1e-9
        intervals.append({"from_angle_degrees": float(expected[index - 1]),
                          "to_angle_degrees": float(expected[index]),
                          "delta_total_hartree": dt, "delta_electronic_hartree": de,
                          "delta_nuclear_hartree": dn,
                          "energy_closure_residual_hartree": abs(dt - de - dn)})
    checks["frozen_saved_verdict"] = evidence["analysis"]["verdict"] == "P03_MINIMAL_PARENT_NBA_DIRECTION_SUPPORTED"
    result = _result("P03", "FROZEN_FOUR_POINT_LEDGER_REPLAY", records, checks,
                     [_source(root, P03_EVIDENCE)],
                     ["Saved optimization and SCF flags are historical evidence, not new execution.",
                      "The new live check covers only the frozen planar RKS single point.",
                      "No relaxed scan, universal NBA law or LFMO component attribution."])
    result["lower_branch_intervals"] = intervals
    return result


def _ledger_p04(root: Path) -> dict[str, Any]:
    rows = [_loads(line) for line in _path(root, P04_LABELS).read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if len(rows) != 33:
        raise ValueError("Exactly 33 P04 component records are required")
    expected_points = {("diphenyl_imine", a) for a in (0., 5., 10., 15., 17., 20., 25., 30.)} | {
        ("phenyl_vinyl_imine", 0.), ("phenyl_vinyl_imine", 17.), ("divinyl_imine", 0.)}
    components = {"pi_pi_direct", "orbital_response_total", "source_endpoint_E_FUD_minus_E_DSI3"}
    points: dict[tuple[str, float], dict[str, dict[str, Any]]] = {}
    identities = set()
    checks: dict[str, bool] = {}
    sources = {_source(root, P04_LABELS)["path"]: _source(root, P04_LABELS)}
    for row in rows:
        identity = row["record_id"]
        if identity in identities:
            raise ValueError("Repeated P04 record identity")
        identities.add(identity)
        key = (row["family_id"], _number(row["angle_degrees"], "angle"))
        component = row["component"]
        if key not in expected_points or component not in components or component in points.get(key, {}):
            raise ValueError("P04 coverage or component identity changed")
        _number(row["value"], "component value")
        points.setdefault(key, {})[component] = row
        name = identity + ":"
        checks[name + "nonproduction"] = row["production_label"] is False and row["training_eligible"] is False and row["universal_all_molecules_law"] is False
        checks[name + "method"] = row["method"] == "RHF" and row["basis"].lower() == "6-31g(d)" and row["unit"] == "hartree"
        relative = row["source_artifact"]
        sources.setdefault(relative, _source(root, relative))
        checks[name + "source_hash"] = sources[relative]["sha256"] == row["source_artifact_sha256"]
        for field in ("geometry_hash", "lfmo_basis_hash", "dsi3_state_config_sha256", "fud_state_config_sha256", "fragment_state_contract_sha256"):
            value = row[field]
            checks[name + field] = isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())
    if set(points) != expected_points:
        raise ValueError("The 11 valid P04 points are required, including the counterexample")
    records = []
    raw_cache: dict[str, Any] = {}
    for key in sorted(points):
        part = points[key]
        if set(part) != components:
            raise ValueError("Each P04 point needs exactly three components")
        direct = _number(part["pi_pi_direct"]["value"], "direct")
        response = _number(part["orbital_response_total"]["value"], "response")
        endpoint = _number(part["source_endpoint_E_FUD_minus_E_DSI3"]["value"], "endpoint")
        family, angle = key
        name = f"{family}:{angle:.1f}"
        checks[name + ":closure"] = abs(direct + response - endpoint) <= 1e-9
        checks[name + ":positive_endpoint"] = endpoint > 1e-8
        raw_path = part["pi_pi_direct"]["source_artifact"]
        raw = raw_cache.setdefault(raw_path, _read(root, raw_path))
        raw_key = f"{angle:.1f}" if family == "diphenyl_imine" else name
        if raw_key not in raw["points"]:
            # The two-family dedicated artifact uses bare angle keys.
            raw_key = f"{angle:.1f}"
        point = raw["points"][raw_key]
        bucket = point["source_local_three_bucket_view"]
        checks[name + ":raw_components_match"] = (
            abs(_number(bucket["pi_pi_direct_change_hartree"], "raw direct") - direct) <= 1e-12
            and abs(_number(bucket["orbital_response_total_hartree"], "raw response") - response) <= 1e-12
            and abs(_number(point["transition"]["endpoint_hartree"], "raw endpoint") - endpoint) <= 1e-12)
        checks[name + ":saved_technical_checks"] = point["technical_pass"] is True and _all_true(point["checks"])
        records.append({"family_id": family, "angle_degrees": angle,
                        "pi_pi_direct_hartree": direct, "orbital_response_hartree": response,
                        "endpoint_E_FUD_minus_E_DSI3_hartree": endpoint,
                        "closure_residual_hartree": abs(direct + response - endpoint),
                        "geometry_hash": part["pi_pi_direct"]["geometry_hash"],
                        "lfmo_basis_hash": part["pi_pi_direct"]["lfmo_basis_hash"]})
    checks["retained_negative_direct_term_counterexample"] = _number(points[("divinyl_imine", 0.)]["pi_pi_direct"]["value"], "counterexample") < -1e-8
    return _result("P04", "FROZEN_ELEVEN_POINT_THREE_COMPONENT_LEDGER_REPLAY", records, checks,
                   list(sources.values()),
                   ["Divinyl imine 17 degrees is excluded for a non-square LFMO basis; no value is imputed.",
                    "Positive endpoints do not imply a universally positive direct pi-pi term.",
                    "Existing source-defined nonvariational states; no new molecule or general conditional Compute."])


def _p05_checks(point: dict[str, Any], angle: str) -> tuple[dict[str, bool], dict[str, Any]]:
    c = point["components"]
    ground = _number(point["ground_energy_hartree"], "ground energy")
    fud = _number(point["fud_energy_hartree"], "FUD energy")
    direct = _number(c["direct_total_hartree"], "direct")
    response = _number(c["pi_response_hartree"], "pi response") + _number(c["sigma_response_hartree"], "sigma response")
    endpoint = _number(c["endpoint_hartree"], "endpoint")
    checks = {
        "saved_checks": _all_true(point["checks"]) and point["technical_pass"] is True,
        "ground_converged": point["ground_converged"] is True,
        "fud_converged": point["fud_converged"] is True,
        "state_difference": abs(ground - fud - endpoint) <= 1e-9,
        "direct_response_identity": abs(direct + response - endpoint) <= 1e-9,
        "density_fixed_point": 0. <= _number(point["density_fixed_point_residual"], "density residual") <= 1e-8,
        "electron_trace": abs(_number(point["electron_trace"], "electron trace") - 96.) <= 1e-6,
        "fixed_roots": point["roots"] == [7, 41],
        "fixed_group_dimensions": point["group_sizes"] == [56, 162],
        "sign": abs(endpoint) <= 1e-8 if angle == "0.0" else endpoint > 1e-8,
    }
    # Re-evaluate the original saved measured gates, rather than trusting flags.
    for field, tolerance in (
        ("source_cross_group_density_norm", 1e-8),
        ("masked_overlap_cross_block_norm", 1e-8),
        ("masked_fock_cross_block_norm_hartree", 1e-8),
        ("pyscf_vs_explicit_energy_residual_hartree", 1e-9),
        ("pyscf_vs_assembled_helper_residual_hartree", 1e-9),
        ("equation_closure_residual_hartree", 1e-9),
        ("sigma_response_category_closure_residual_hartree", 1e-9),
        ("sigma_response_electronic_split_residual_hartree", 1e-9),
    ):
        checks[field] = 0. <= _number(c[field], field) <= tolerance
    return checks, {"angle_degrees": float(angle), "ground_energy_hartree": ground,
                    "fud_energy_hartree": fud, "direct_total_hartree": direct,
                    "orbital_response_hartree": response,
                    "endpoint_E_G_minus_E_FUD_hartree": endpoint,
                    "closure_residual_hartree": abs(direct + response - endpoint),
                    "lfmo_basis_hash": point["lfmo_basis_hash"]}


def _ledger_p05(root: Path) -> dict[str, Any]:
    data = _read(root, P05_EVIDENCE)
    anchor = _read(root, P05_ANCHOR)
    angles = ["0.0", "5.0", "10.0", "17.0", "25.0", "35.0", "45.0"]
    if set(data["points"]) != set(angles):
        raise ValueError("P05 seven-angle coverage changed")
    checks = {"saved_seven_angle_checks": _all_true(data["checks"]),
              "saved_scientific_verdict": data["scientific_verdict"] == "P05_CONSISTENT_WITH_MULTI_ANGLE_SUPPORT"}
    records = []
    for angle in angles:
        per, record = _p05_checks(data["points"][angle], angle)
        checks.update({angle + ":" + key: value for key, value in per.items()})
        records.append(record)
    for angle in ("0.0", "17.0"):
        checks[angle + ":frozen_anchor_endpoint"] = abs(
            _number(data["points"][angle]["components"]["endpoint_hartree"], "saved endpoint")
            - _number(anchor["points"][angle]["components"]["endpoint_hartree"], "anchor endpoint")) <= 1e-12
    return _result("P05", "FROZEN_SEVEN_ANGLE_LEDGER_REPLAY", records, checks,
                   [_source(root, P05_EVIDENCE), _source(root, P05_ANCHOR)],
                   ["Zero degrees remains indeterminate within 1e-8 Eh.",
                    "Only the frozen same-parent rigid-twist nonvariational G/FUD ledger is supported.",
                    "New live execution is a single 17-degree point, not seven fresh points."])


def _p06_checks(point: dict[str, Any], angle: str) -> tuple[dict[str, bool], dict[str, Any]]:
    states = point["states"]
    checks = {"source_partition": point["source_partition_contract_closes"] is True,
              "shared_basis": point["shared_lfmo_basis_within_geometry"] is True}
    definitions = {"FUL": ([6, 8, 28, 37, 2], [3, 4, 17, 23, 1]),
                   "PDSI": ([6, 8, 65, 2], [3, 4, 40, 1])}
    for name, row in states.items():
        if name not in definitions:
            raise ValueError("Only FUL and PDSI states are accepted")
        independent = _number(row["independent_energy_hartree"], "independent energy")
        pipeline = _number(row["pipeline_energy_hartree"], "pipeline energy")
        checks[name + ":converged"] = row["converged"] is True
        checks[name + ":assembly"] = abs(independent - pipeline) <= 1e-9
        checks[name + ":electron_trace"] = abs(_number(row["electron_trace"], "electron trace") - 96.) <= 1e-6
        checks[name + ":density_fixed_point"] = 0. <= _number(row["density_fixed_point_residual"], "density residual") <= 1e-8
        checks[name + ":groups_and_roots"] = row["group_sizes"] == definitions[name][0] and row["occupied_roots"] == definitions[name][1]
    if set(states) != set(definitions):
        raise ValueError("Both P06 states are required")
    endpoint = _number(states["PDSI"]["independent_energy_hartree"], "PDSI energy") - _number(states["FUL"]["independent_energy_hartree"], "FUL energy")
    pipeline_endpoint = _number(states["PDSI"]["pipeline_energy_hartree"], "pipeline PDSI") - _number(states["FUL"]["pipeline_energy_hartree"], "pipeline FUL")
    printed = {"0.0": .06891, "17.0": .06504}[angle]
    checks["positive_endpoint"] = endpoint > 1e-8
    checks["printed_endpoint_absolute_tolerance"] = abs(endpoint - printed) <= .010
    checks["independent_endpoint_assembly"] = abs(endpoint - pipeline_endpoint) <= 1e-9
    checks["saved_endpoint_matches_recomputed"] = abs(endpoint - _number(point["independent_endpoint_hartree"], "saved endpoint")) <= 1e-9
    return checks, {"angle_degrees": float(angle), "geometry_sha256": point["geometry_sha256"],
                    "states": deepcopy(states), "endpoint_E_PDSI_minus_E_FUL_hartree": endpoint,
                    "printed_endpoint_hartree": printed,
                    "source_absolute_error_hartree": abs(endpoint - printed),
                    "energy_assembly_residual_hartree": abs(endpoint - pipeline_endpoint)}


def _ledger_p06(root: Path) -> dict[str, Any]:
    data = _read(root, P06_EVIDENCE)
    if set(data["points"]) != {"0.0", "17.0"}:
        raise ValueError("Frozen P06 two-angle coverage changed")
    records, checks = [], {"saved_technical_checks": _all_true(data["technical_checks"]),
                           "saved_direction_checks": _all_true(data["direction_checks"])}
    for angle in ("0.0", "17.0"):
        per, record = _p06_checks(data["points"][angle], angle)
        records.append(record)
        checks.update({angle + ":" + key: value for key, value in per.items()})
    checks["endpoint_decreases_from_0_to_17"] = records[1]["endpoint_E_PDSI_minus_E_FUL_hartree"] < records[0]["endpoint_E_PDSI_minus_E_FUL_hartree"]
    result = _result("P06", "FROZEN_TWO_POINT_INDEPENDENT_ENERGY_LEDGER_REPLAY", records, checks,
                     [_source(root, P06_EVIDENCE)],
                     ["Source-defined nonvariational FUL-2/PDSI is not classical steric energy.",
                      "Physical AO-metric idempotency is reported, not retroactively imposed as a source-density gate.",
                      "Historical Python/PySCF/NumPy exact-version check is replay evidence; new live environment is recorded separately.",
                      "No fresh geometry optimization, additional angle or cross-protocol energy sum."])
    result["historical_environment"] = deepcopy(data["environment_manifest"]["environment"])
    return result


def ledger(case: str, root: Path) -> dict[str, Any]:
    """Pure JSON/NumPy replay; does not import PySCF or original drivers."""
    return {"P03": _ledger_p03, "P04": _ledger_p04,
            "P05": _ledger_p05, "P06": _ledger_p06}[_case(case)](Path(root))


def _yaml(root: Path, relative: str) -> dict[str, Any]:
    import yaml
    value = yaml.safe_load(_path(root, relative).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("Scientific config must be a mapping")
    return value


def prepare(case: str, root: Path) -> None:
    """Load the immutable live module closure once, before the native guard."""
    global _ACTIVE_ROOT
    case, root = _case(case), Path(root).resolve()
    if _ACTIVE_ROOT is not None and _ACTIVE_ROOT != root:
        raise ValueError("A worker cannot mix scientific source trees")
    if (case, str(root)) in _PREPARED:
        return
    for relative in ("src", "experiments/validation", ""):
        path = str(root / relative)
        if path not in sys.path:
            sys.path.insert(0, path)
    # Imported aliases are deliberately retained for the caller's guard scan.
    path = _path(root, _LIVE_SCRIPT[case])
    name = "_protocol_cases_source_" + case.lower()
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load frozen scientific driver")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    if Path(module.ROOT).resolve() != root:
        raise RuntimeError("Scientific driver ROOT does not match source tree")
    # Refuse an already-imported original helper tree rather than retargeting it.
    for key, helper in tuple(sys.modules.items()):
        if key.startswith("experiments.validation.") and hasattr(helper, "ROOT"):
            if Path(helper.ROOT).resolve() != root:
                raise RuntimeError("Scientific import escaped the immutable source tree")
    _PREPARED[(case, str(root))] = module
    _ACTIVE_ROOT = root


def _module(case: str, root: Path) -> Any:
    key = (_case(case), str(Path(root).resolve()))
    if key not in _PREPARED:
        raise RuntimeError("prepare(case, root) must complete before entering the scientific guard")
    return _PREPARED[key]


def _live_inputs(case: str, root: Path) -> tuple[list[list[Any]], str, str, dict[str, Any]]:
    if case == "P03":
        master = _yaml(root, _CONFIG[0])
        geometry = _read(root, master["molecule"]["geometry_artifact"])["points"]["0.0"]
        if geometry["geometry_sha256"] != master["molecule"]["expected_geometry_sha256"]:
            raise ValueError("Frozen P03 planar geometry identity changed")
        return deepcopy(geometry["atoms"]), "B3LYPG", "6-311g(d,p)", master
    if case == "P04":
        master = _yaml(root, "configs/qm/target_c_source_native_reporting_basis_direct_response_v0.1.yaml")
        from experiments.validation import dsi_fud_initial_density_reproducibility_gate0 as resolver
        config = resolver.resolve_state_config(root / master["dsi3_config"])
        return deepcopy(config["geometry"]["atoms"]), "RHF", "6-31g(d)", master
    if case == "P05":
        master = _yaml(root, "configs/qm/source_table_5_15_fixed_twist_pi_sigma_nba_v1.0.yaml")
        geometry = _read(root, P05_ANCHOR)["geometry"]
        return deepcopy(geometry["points"]["17.0"]["atoms"]), "RHF", "6-31g(d)", master
    master = _yaml(root, "configs/qm/source_table_5_19_independent_assembly_v1.0.yaml")
    geometry = _read(root, master["geometry_artifact"])["points"]["0.0"]
    return deepcopy(geometry["atoms"]), "RHF", "sto-3g", master


def preflight(case: str, root: Path) -> dict[str, Any]:
    """Build a molecule and AO count only; no SCF, optimizer or localizer."""
    case, root = _case(case), Path(root).resolve()
    prepare(case, root)
    atoms, method, basis, master = _live_inputs(case, root)
    from pyscf import gto
    mol = gto.M(atom=atoms, basis=basis, charge=0, spin=0,
                unit="Angstrom", symmetry=False, verbose=0)
    naive_full_eri = int(mol.nao_nr()) ** 4 * 8
    checks = {"fixed_parent_25_atoms": len(atoms) == 25,
              "fixed_parent_96_electrons": mol.nelectron == 96,
              "closed_shell": mol.spin == 0,
              "actual_ao_count_matches_protocol": mol.nao_nr() == {"P03": 318, "P04": 218, "P05": 218, "P06": 81}[case],
              "finite_coordinates": bool(np.isfinite(mol.atom_coords()).all())}
    if case == "P03":
        checks["fixed_method_and_grid"] = master["optimization"]["method"] == "B3LYPG" and master["optimization"]["grid_level"] == 3
    result = _result(case, "MOLECULE_BUILD_ONLY_PREFLIGHT", [{"angle_degrees": 17. if case == "P05" else 0.,
                     "atom_count": len(atoms), "electron_count": int(mol.nelectron),
                     "ao_count": int(mol.nao_nr()), "method": method, "basis": basis,
                     "naive_full_eri_bytes": naive_full_eri}], checks, [],
                     ["Naive full ERI estimate is a caution, not the actual get_jk/get_veff allocation.",
                      "Preflight does not guarantee convergence or compliance with the external wall/RSS cap."])
    result["scientific_kernel_calls"] = 0
    return result


def live(case: str, root: Path) -> dict[str, Any]:
    """Execute exactly one frozen point under the caller's installed guard."""
    case, root = _case(case), Path(root).resolve()
    module = _module(case, root)
    atoms, method, basis, master = _live_inputs(case, root)
    if case == "P03":
        point = module.single_point(atoms, deepcopy(master["optimization"]))
        original = _read(root, P03_EVIDENCE)["points"]["0.0"]["energies"]
        record = dict(point)
        record.update({"angle_degrees": 0., "method": method, "basis": basis,
                       "source_total_energy_difference_hartree": _number(point["total_energy_hartree"], "E") - _number(original["total_energy_hartree"], "source E")})
        checks = {"rks_converged": point["scf_converged"] is True,
                  "energy_identity": abs(_number(point["total_energy_hartree"], "E") - _number(point["electronic_energy_hartree"], "Ee") - _number(point["nuclear_repulsion_hartree"], "EN")) <= 1e-9}
        limitation = "A frozen planar single point does not reproduce the original relaxed four-point optimization."
    elif case == "P04":
        # Original reference comparison is retained and reads locked diagnostics.
        point = module.run_point(master, atoms, "0.0", require_source_reference=True)
        record = _safe(point)
        checks = deepcopy(point["checks"])
        checks["original_technical_pass"] = point["technical_pass"] is True
        checks["positive_endpoint_scoped_sign"] = _number(point["transition"]["endpoint_hartree"], "endpoint") > 1e-8
        limitation = "Only frozen diphenyl imine 0 degrees is freshly solved; the 11-point panel remains a separate historical ledger."
    elif case == "P05":
        geometry = _read(root, P05_ANCHOR)["geometry"]
        point = module.run_point_from_geometry(master, {"optimized_geometry_lfmo_interface": master["lfmo_interface"]}, geometry, "17.0")
        checks, record = _p05_checks(point, "17.0")
        record["original_point"] = _safe(point)
        checks["original_printed_component_tolerance"] = point["source_comparison"]["within_declared_tolerance"] is True
        limitation = "One original 17-degree G/FUD point is freshly solved; there is no new seven-angle scan."
    else:
        source_master = _yaml(root, master["source_sigma_sigma_config"])
        geometry_master = _yaml(root, master["geometry_config"])
        geometry = _read(root, master["geometry_artifact"])["points"]["0.0"]
        point = module.run_point(master, source_master, geometry_master, geometry, "0.0")
        checks, record = _p06_checks(point, "0.0")
        record["original_point"] = _safe(point)
        limitation = "One original 0-degree FUL-2/PDSI point is freshly solved; no source-geometry optimization or second-angle solve."
    result = _result(case, "ONE_FROZEN_ORIGINAL_PROTOCOL_POINT", [record], checks, [],
                     [limitation, "Numerical convergence is distinct from variational stability and a universal scientific law.",
                      "Historical and new execution identities/environments must be reported separately.",
                      "No user conditional Compute, new production label or cross-protocol sum is enabled."])
    result["method"] = method
    result["basis"] = basis
    return result
