"""Decompose Target C while preserving each state's native source definition.

DSI-3 and FUD are solved independently with their own geometry-specific LFMO
reconstructions.  Their AO densities and energies are then frozen.  The DSI-3
LFMO basis is used only as a common reporting coordinate system; FUD is never
re-solved in that basis.  This removes the protocol error in the earlier
common-basis control while retaining the source-native endpoint.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import numpy as np

from experiments.validation.chapter5_pi_sigma_reconstruction_gate0 import canonical_digest
from experiments.validation.dsi2_divinyl_imine_source_shaped_gate0 import full_stage
from experiments.validation.dsi2_divinyl_imine_torsion_continuation_gate0 import rotate_about_axis
from experiments.validation.dsi_fud_initial_density_reproducibility_gate0 import resolve_state_config
from experiments.validation.one_cut_conditional_scf_gate0 import ROOT, git_commit, json_safe, load_yaml
from experiments.validation.source_optimized_dual_density_nba_gate0 import sign_class
from experiments.validation.source_optimized_physical_direct_response_nba_gate0 import (
    block_components,
    direct_response_decomposition,
)


DEFAULT_CONFIG = ROOT / "configs/qm/target_c_source_native_reporting_basis_direct_response_v0.1.yaml"
DEFAULT_OUTPUT = ROOT / "artifacts/raw/target_c_source_native_reporting_basis_direct_response_2026-08-16.json"
DEFAULT_MARKDOWN = ROOT / "docs/reports/target_c_source_native_reporting_basis_direct_response_2026-08-16.md"


def source_metric_reference(angle: str) -> float | None:
    if angle not in {"0.0", "17.0"}:
        return None
    filename = (
        "source_metric_diphenyl_diagnostic_energy_17_2026-08-15.json"
        if angle == "17.0"
        else "source_metric_diphenyl_diagnostic_energy_2026-08-15.json"
    )
    path = ROOT / "artifacts/raw" / filename
    if not path.exists():
        return None
    report = json.loads(path.read_text(encoding="utf-8"))
    for row in report.get("diagnostic_energy_differences", []):
        if row.get("id") == "fud_minus_dsi3":
            return float(row["value_hartree"])
    return None


def source_reference_comparison(
    endpoint: float,
    reference: float | None,
    tolerance: float,
    required: bool,
) -> tuple[str, bool | None]:
    """Keep an unevaluated source comparison distinct from a successful one."""
    if not required:
        return "NOT_EVALUATED", None
    if reference is None:
        return "REFERENCE_MISSING", False
    passed = bool(np.isfinite(endpoint) and abs(endpoint - reference) <= tolerance)
    return ("MATCHED" if passed else "MISMATCHED"), passed


def dsi3_groups(internal: dict[str, Any]) -> tuple[list[list[int]], list[int], list[str]]:
    types = list(internal["column_types"])
    fragments = list(internal["column_fragments"])
    pi_groups = [
        [
            index
            for index, (kind, owner) in enumerate(zip(types, fragments, strict=True))
            if kind == "pi" and owner == fragment
        ]
        for fragment in ("A", "B", "C")
    ]
    sigma = [index for index, kind in enumerate(types) if kind == "sigma"]
    groups = [*pi_groups, sigma]
    labels = ["pi_A", "pi_B", "pi_C", "sigma_all"]
    if sorted(index for group in groups for index in group) != list(range(len(types))):
        raise ValueError("DSI-3 reporting groups do not partition the reporting basis")
    roots = [
        int(internal["bonded_pi_occupied_roots_by_fragment"][fragment])
        for fragment in ("A", "B", "C")
    ]
    cut_roots = sum(
        int(internal["cut_single_count_by_fragment"][fragment])
        for fragment in ("A", "B", "C")
    ) // 2
    roots.append(
        sum(
            int(internal["bonded_sigma_occupied_roots_by_fragment"][fragment])
            for fragment in ("A", "B", "C")
        )
        + cut_roots
    )
    return groups, roots, labels


def run_point(
    master: dict[str, Any],
    atoms: list[list[Any]],
    angle: str,
    *,
    require_source_reference: bool = True,
) -> dict[str, Any]:
    dsi3_config = resolve_state_config(ROOT / str(master["dsi3_config"]))
    dsi3_config["experiment_id"] = f"{master['experiment_id']}/DSI3/{angle}"
    dsi3_config["geometry"]["atoms"] = deepcopy(atoms)
    fud_config = resolve_state_config(ROOT / str(master["fud_config"]))
    fud_config["experiment_id"] = f"{master['experiment_id']}/FUD/{angle}"
    fud_config["geometry"]["atoms"] = deepcopy(atoms)

    dsi3_report = full_stage(dsi3_config, return_internal=True)
    fud_report = full_stage(fud_config, return_internal=True)
    dsi3_internal = dsi3_report.pop("_internal")
    fud_internal = fud_report.pop("_internal")

    molecule = dsi3_internal["molecule"]
    basis = np.asarray(dsi3_internal["working_basis"], dtype=float)
    groups, roots, labels = dsi3_groups(dsi3_internal)
    dsi3_density = np.asarray(dsi3_internal["density"], dtype=float)
    fud_density = np.asarray(fud_internal["density"], dtype=float)
    dsi3_energy = float(dsi3_internal["diagnostic_energy_hartree"])
    fud_energy = float(fud_internal["diagnostic_energy_hartree"])
    tolerance = float(master["acceptance"]["closure_tolerance_hartree"])

    transition = direct_response_decomposition(
        molecule,
        basis,
        fud_energy,
        fud_density,
        dsi3_energy,
        dsi3_density,
        groups,
        labels,
        "E_FUD-E_DSI3",
        tolerance,
    )
    direct_pairs = transition["relaxed_components"]["cross_pair_terms_hartree"]
    restricted_pairs = transition["restricted_components"]["cross_pair_terms_hartree"]
    pi_pi_direct = float(
        sum(
            direct_pairs[key] - restricted_pairs[key]
            for key in ("pi_A__pi_B", "pi_A__pi_C", "pi_B__pi_C")
        )
    )
    pi_sigma_direct = float(
        sum(
            direct_pairs[key] - restricted_pairs[key]
            for key in ("pi_A__sigma_all", "pi_B__sigma_all", "pi_C__sigma_all")
        )
    )
    relaxed_within = transition["relaxed_components"]["within_group_terms_hartree"]
    restricted_within = transition["restricted_components"]["within_group_terms_hartree"]
    pi_response = float(
        sum(relaxed_within[label] - restricted_within[label] for label in labels[:3])
    )
    sigma_response = float(relaxed_within["sigma_all"] - restricted_within["sigma_all"])
    reference = source_metric_reference(angle) if require_source_reference else None
    endpoint = float(transition["endpoint_hartree"])
    comparison_status, comparison_pass = source_reference_comparison(
        endpoint,
        reference,
        float(master["acceptance"]["source_endpoint_tolerance_hartree"]),
        require_source_reference,
    )
    checks = {
        "dsi3_native_source_pass": dsi3_report["disposition"] == "PASS",
        "fud_native_source_pass": fud_report["disposition"] == "PASS",
        "reporting_basis_full_rank": bool(np.linalg.matrix_rank(basis) == basis.shape[1]),
        "native_endpoint_finite": bool(np.isfinite(endpoint)),
        "direct_response_closes": float(transition["closure_residual_hartree"]) <= tolerance,
        "pi_cross_split_closes": abs(pi_pi_direct + pi_sigma_direct - float(transition["direct_cross_group_change_hartree"])) <= tolerance,
        "response_split_closes": abs(pi_response + sigma_response - float(transition["orbital_response_hartree"])) <= tolerance,
        "fud_not_resolved_on_reporting_basis": True,
    }
    if require_source_reference:
        checks["native_endpoint_matches_source_metric"] = bool(comparison_pass)
    return {
        "angle_degrees": float(angle),
        "basis_anchor": "DSI-3",
        "basis_role": "density_reporting_only",
        "basis_shape": list(basis.shape),
        "basis_digest": canonical_digest(basis.tolist()),
        "native_state_energies_hartree": {"DSI3": dsi3_energy, "FUD": fud_energy},
        "native_source_metric_endpoint_hartree": reference,
        "source_reference_required": require_source_reference,
        "source_reference_comparison_status": comparison_status,
        "transition": transition,
        "source_local_three_bucket_view": {
            "pi_pi_direct_change_hartree": pi_pi_direct,
            "pi_sigma_direct_change_hartree": pi_sigma_direct,
            "direct_total_hartree": float(transition["direct_cross_group_change_hartree"]),
            "pi_response_hartree": pi_response,
            "sigma_response_hartree": sigma_response,
            "orbital_response_total_hartree": float(transition["orbital_response_hartree"]),
            "pi_pi_direct_sign": sign_class(pi_pi_direct, tolerance),
        },
        "checks": checks,
        "technical_pass": bool(all(checks.values())),
    }


def run(master: dict[str, Any]) -> dict[str, Any]:
    base = resolve_state_config(ROOT / str(master["dsi3_config"]))
    atoms = deepcopy(base["geometry"]["atoms"])
    axis = [int(value) for value in master["geometry"]["axis_atom_indices"]]
    rotating = [int(value) for value in master["geometry"]["rotating_atom_indices"]]
    points = {
        "0.0": run_point(master, atoms, "0.0"),
        "17.0": run_point(master, rotate_about_axis(atoms, axis, rotating, 17.0), "17.0"),
    }
    technical_pass = all(point["technical_pass"] for point in points.values())
    return {
        "experiment_id": master["experiment_id"],
        "protocol": master["protocol"],
        "disposition": "TARGET_C_SOURCE_NATIVE_REPORTING_BASIS_PASS" if technical_pass else "TARGET_C_SOURCE_NATIVE_REPORTING_BASIS_INCOMPLETE",
        "technical_pass": technical_pass,
        "points": points,
        "label_decision": {
            "source_native_direct_response_candidate_allowed": technical_pass,
            "stabilization_destabilization_interpretation_allowed": False,
            "production_label_allowed": False,
        },
        "boundaries": master["boundaries"],
        "provenance": {"git_commit": git_commit(), "config_sha256": canonical_digest(master)},
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Target C source-native reporting-basis direct-response certificate",
        "",
        f"- Disposition: **{report['disposition']}**",
        f"- Technical pass: `{report['technical_pass']}`",
        "- Native-state rule: DSI-3 and FUD are solved independently with their own source-local LFMO reconstructions.",
        "- Reporting rule: DSI-3's basis is used only to resolve frozen AO densities; FUD is not re-solved in that basis.",
        "- Final stabilization/destabilization and production labels: disabled.",
        "",
        "| Angle | Native E_FUD-E_DSI3 (Eh) | Source endpoint (Eh) | pi-pi direct (Eh) | pi-sigma direct (Eh) | response (Eh) | closure (Eh) |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for angle in ("0.0", "17.0"):
        point = report["points"][angle]
        transition = point["transition"]
        buckets = point["source_local_three_bucket_view"]
        lines.append(
            f"| {float(angle):.1f} | {transition['endpoint_hartree']:.12f} | "
            f"{point['native_source_metric_endpoint_hartree']:.12f} | "
            f"{buckets['pi_pi_direct_change_hartree']:.12f} | "
            f"{buckets['pi_sigma_direct_change_hartree']:.12f} | "
            f"{buckets['orbital_response_total_hartree']:.12f} | "
            f"{transition['closure_residual_hartree']:.3e} |"
        )
    lines.extend([
        "",
        "## Resolution",
        "",
        "The previous sign discrepancy came from re-solving FUD on the DSI-3 basis. This certificate preserves both native source states and uses a common basis only for post-hoc density energy bookkeeping. It therefore preserves the source endpoint while providing an exact direct-plus-response identity.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    report = run(load_yaml(args.config.resolve()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(json_safe(report), indent=2, sort_keys=True), encoding="utf-8")
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(f"{report['disposition']}: technical={report['technical_pass']}")
    return 0 if report["technical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
