"""Reconstruct Chapter 5 Table 5-15 on source-optimized NBA geometries."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from experiments.validation.chapter5_pi_sigma_reconstruction_gate0 import (
    HARTREE_TO_KCAL_MOL,
    canonical_digest,
)
from experiments.validation.dsi2_divinyl_imine_source_shaped_gate0 import full_stage
from experiments.validation.one_cut_conditional_scf_gate0 import (
    ROOT,
    git_commit,
    json_safe,
    load_yaml,
)
from experiments.validation.source_nonvariational_pi_sigma_nba_gate0 import (
    run_point,
)
from experiments.validation.dsi_fud_initial_density_reproducibility_gate0 import (
    resolve_state_config,
)


DEFAULT_CONFIG = ROOT / "configs" / "qm" / "source_optimized_table_5_15_pi_sigma_nba_v1.0.yaml"
DEFAULT_OUTPUT = ROOT / "artifacts" / "raw" / "source_optimized_table_5_15_pi_sigma_nba_2026-08-15.json"
DEFAULT_CHECKPOINT = ROOT / "artifacts" / "checkpoints" / "source_optimized_table_5_15_pi_sigma_nba_2026-08-15.json"
DEFAULT_MARKDOWN = ROOT / "docs" / "reports" / "gate0_source_optimized_table_5_15_pi_sigma_nba_2026-08-15.md"


def configure_point(
    master: dict[str, Any], geometry_master: dict[str, Any],
    geometry: dict[str, Any], angle: str,
) -> dict[str, Any]:
    config = resolve_state_config(ROOT / str(master["base_config"]))
    config["experiment_id"] = f"{master['experiment_id']}/{angle}"
    config["electronic_structure"]["basis"] = str(
        master["electronic_structure"]["basis"]
    )
    config["geometry"]["atoms"] = deepcopy(geometry["points"][angle]["atoms"])
    config["fud_state"]["density_reconstruction"] = str(
        master["source_definition"]["density_reconstruction"]
    )
    interface = geometry_master["optimized_geometry_lfmo_interface"]
    for key in (
        "reflection_block_closure_tolerance",
        "reflection_eigenvalue_tolerance",
        "reflection_classification_policy",
        "minimum_absolute_reflection_eigenvalue",
        "maximum_accepted_reflection_residual",
    ):
        config["acceptance"][key] = interface[key]
    return config


def compare_to_source(
    point: dict[str, Any], master: dict[str, Any], angle: str,
) -> dict[str, Any]:
    component = point["components"]
    reference = master["source_reference"]["published_components_17_degree_hartree"]
    if angle != "17.0":
        return {
            "reference_available": False,
            "reference_note": "no printed Table 5-15 component reference is available at this angle",
        }
    values = {
        "direct_intrafragment": float(component["direct_intrafragment_hartree"]),
        "direct_interfragment": float(component["direct_interfragment_hartree"]),
        "pi_response": float(component["pi_response_hartree"]),
        "sigma_response": float(component["sigma_response_hartree"]),
        "total": float(component["endpoint_hartree"]),
    }
    expected = {**reference, "total": float(master["source_reference"]["published_total_17_degree_hartree"])}
    errors = {name: abs(values[name] - float(expected[name])) for name in values}
    tolerance = float(master["acceptance"]["printed_component_absolute_tolerance_hartree"])
    return {
        "reference_available": True,
        "calculated_hartree": values,
        "published_hartree": expected,
        "absolute_error_hartree": errors,
        "within_declared_tolerance": all(value <= tolerance for value in errors.values()),
        "tolerance_hartree": tolerance,
    }


def point_checks(point: dict[str, Any], master: dict[str, Any]) -> dict[str, bool]:
    acceptance = master["acceptance"]
    component = point["components"]
    return {
        "ground_converged": bool(point["ground_converged"]),
        "fud_converged": bool(point["fud_converged"]),
        "density_fixed_point": float(point["density_fixed_point_residual"]) <= float(acceptance["density_fixed_point_tolerance"]),
        "electron_trace": abs(float(point["electron_trace"]) - int(point["expected_electrons"])) <= float(acceptance["electron_trace_tolerance"]),
        "source_cross_group_density_zero": float(component["source_cross_group_density_norm"]) <= float(acceptance["source_cross_block_tolerance"]),
        "fock_and_overlap_cross_blocks_deleted": (
            float(component["masked_overlap_cross_block_norm"]) <= float(acceptance["source_cross_block_tolerance"])
            and float(component["masked_fock_cross_block_norm_hartree"]) <= float(acceptance["source_cross_block_tolerance"])
        ),
        "independent_energy_assemblies": max(
            float(component["pyscf_vs_explicit_energy_residual_hartree"]),
            float(component["pyscf_vs_assembled_helper_residual_hartree"]),
        ) <= float(acceptance["energy_assembly_tolerance_hartree"]),
        "equations_5_12_to_5_16_close": float(component["equation_closure_residual_hartree"]) <= float(acceptance["equation_closure_tolerance_hartree"]),
        "sigma_response_suballocation_closes": max(
            float(component["sigma_response_category_closure_residual_hartree"]),
            float(component["sigma_response_electronic_split_residual_hartree"]),
        ) <= float(acceptance["equation_closure_tolerance_hartree"]),
    }


def run_point_from_geometry(
    master: dict[str, Any], geometry_master: dict[str, Any],
    geometry: dict[str, Any], angle: str,
) -> dict[str, Any]:
    config = configure_point(master, geometry_master, geometry, angle)
    scaffold = full_stage(config, return_internal=True)
    internal = scaffold.pop("_internal")
    point = run_point(config, internal)
    point["angle_degrees"] = float(angle)
    point["expected_electrons"] = int(config["electronic_structure"]["expected_electrons"])
    point["geometry_id"] = geometry["geometry_id"]
    point["lfmo_basis_hash"] = canonical_digest(internal["working_basis"].tolist())
    point["checks"] = point_checks(point, master)
    point["technical_pass"] = bool(all(point["checks"].values()))
    point["source_comparison"] = compare_to_source(point, master, angle)
    return point


def run(master: dict[str, Any], checkpoint_path: Path) -> dict[str, Any]:
    geometry_master = load_yaml(ROOT / str(master["geometry_config"]))
    geometry = json.loads((ROOT / str(master["geometry_artifact"])).read_text(encoding="utf-8"))
    if [float(value) for value in master["angles_degrees"]] != [0.0, 17.0]:
        raise ValueError("only source-optimized 0 and 17 degree points are authorized")
    checkpoint = {
        "experiment_id": master["experiment_id"],
        "config_sha256": canonical_digest(master),
        "points": {},
    }
    if checkpoint_path.exists():
        candidate = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if candidate.get("experiment_id") == checkpoint["experiment_id"] and candidate.get("config_sha256") == checkpoint["config_sha256"]:
            checkpoint = candidate
    for angle in ("0.0", "17.0"):
        if angle not in checkpoint["points"]:
            checkpoint["points"][angle] = run_point_from_geometry(
                master, geometry_master, geometry, angle
            )
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            checkpoint_path.write_text(json.dumps(json_safe(checkpoint), indent=2, sort_keys=True), encoding="utf-8")
    points = checkpoint["points"]
    technical_pass = all(bool(point["technical_pass"]) for point in points.values())
    source_signs = points["17.0"]["components"]
    sign_checks = {
        "positive_total": float(source_signs["endpoint_hartree"]) > 0.0,
        "direct_intrafragment_negative": float(source_signs["direct_intrafragment_hartree"]) < 0.0,
        "direct_interfragment_positive": float(source_signs["direct_interfragment_hartree"]) > 0.0,
        "pi_response_negative": float(source_signs["pi_response_hartree"]) < 0.0,
        "sigma_response_negative": float(source_signs["sigma_response_hartree"]) < 0.0,
    }
    source_comparison_pass = bool(points["17.0"]["source_comparison"]["within_declared_tolerance"])
    sign_pattern_pass = bool(all(sign_checks.values()))
    target_pass = bool(technical_pass and source_comparison_pass and sign_pattern_pass)
    return {
        "experiment_id": master["experiment_id"],
        "protocol": master["protocol"],
        "disposition": "SOURCE_OPTIMIZED_TABLE_5_15_SE2_PASS" if target_pass else "SOURCE_OPTIMIZED_TABLE_5_15_INCOMPLETE",
        "technical_pass": technical_pass,
        "source_comparison_pass": source_comparison_pass,
        "source_component_sign_pattern_pass": sign_pattern_pass,
        "target_pass": target_pass,
        "source_component_sign_checks": sign_checks,
        "points": points,
        "boundaries": master["boundaries"],
        "provenance": {
            "git_commit": git_commit(),
            "config_sha256": canonical_digest(master),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Gate 0 source-optimized Table 5-15 pi-sigma reconstruction",
        "",
        f"- Disposition: **{report['disposition']}**",
        f"- Technical pass: `{report['technical_pass']}`",
        f"- Source comparison pass: `{report['source_comparison_pass']}`",
        f"- Component sign pattern pass: `{report['source_component_sign_pattern_pass']}`",
        "- Ledger: `source_nonvariational_definition`",
        "- Environment: source-optimized NBA, RHF/6-31G*",
        "",
        "The source density, nonorthogonal LFMO metric, simultaneous Fock/overlap mask, and Equations 5-12 through 5-16 are retained. Physical-projector density is disabled.",
        "",
        "| Angle | E_G (Eh) | E_FUD (Eh) | E_G-E_FUD (Eh) | kcal/mol | Equation closure (Eh) |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for angle in ("0.0", "17.0"):
        point = report["points"][angle]
        component = point["components"]
        lines.append(
            f"| {float(angle):.1f} | {point['ground_energy_hartree']:.12f} | "
            f"{point['fud_energy_hartree']:.12f} | {component['endpoint_hartree']:.12f} | "
            f"{component['endpoint_kcal_mol']:.6f} | {component['equation_closure_residual_hartree']:.3e} |"
        )
    component = report["points"]["17.0"]["components"]
    comparison = report["points"]["17.0"]["source_comparison"]
    lines.extend([
        "",
        "## 17-degree Table 5-15 comparison",
        "",
        "| Component | Calculated (Eh) | Published (Eh) | Absolute error (Eh) |",
        "|---|---:|---:|---:|",
    ])
    names = [
        ("direct_intrafragment", "direct_intrafragment_hartree"),
        ("direct_interfragment", "direct_interfragment_hartree"),
        ("pi_response", "pi_response_hartree"),
        ("sigma_response", "sigma_response_hartree"),
        ("total", "endpoint_hartree"),
    ]
    for label, key in names:
        lines.append(
            f"| {label} | {comparison['calculated_hartree'][label]:.12f} | "
            f"{comparison['published_hartree'][label]:.12f} | "
            f"{comparison['absolute_error_hartree'][label]:.6f} |"
        )
    lines.extend([
        "",
        "## Sign pattern",
        "",
    ])
    for name, value in report["source_component_sign_checks"].items():
        lines.append(f"- `{name}`: `{value}`")
    lines.extend([
        "",
        "## Boundary",
        "",
        "This is a source-equivalent reconstruction ledger and remains nonproduction. It does not assert historical code identity, does not use physical-projector density, and does not authorize AI labels.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    master = load_yaml(args.config)
    report = run(master, args.checkpoint)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(json_safe(report), indent=2, sort_keys=True), encoding="utf-8")
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(
        f"{report['disposition']}: technical={report['technical_pass']}, "
        f"source_comparison={report['source_comparison_pass']}"
    )
    return 0 if report["target_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
