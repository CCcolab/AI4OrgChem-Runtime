"""Compare source-block and physical-metric densities on optimized NBA states."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from experiments.validation.chapter5_pi_sigma_reconstruction_gate0 import (
    canonical_digest,
    run_ground_state,
)
from experiments.validation.chapter5_three_effect_reconstruction_gate0 import (
    assembled_energy,
    maximum_cross_group_density,
    run_source_state,
)
from experiments.validation.one_cut_conditional_scf_gate0 import (
    ROOT,
    git_commit,
    json_safe,
    load_yaml,
)
from experiments.validation.source_nonvariational_sigma_sigma_nba_gate0 import (
    build_ful2_internal,
)
from experiments.validation.source_optimized_three_effect_reconstruction_nba_gate0 import (
    configured_parent,
    state_cycle,
    state_definitions,
)


DEFAULT_CONFIG = ROOT / "configs" / "qm" / "source_optimized_dual_density_nba_v0.1.yaml"
DEFAULT_OUTPUT = ROOT / "artifacts" / "raw" / "source_optimized_dual_density_nba_2026-08-14.json"
DEFAULT_CHECKPOINT = ROOT / "artifacts" / "checkpoints" / "source_optimized_dual_density_nba_2026-08-14.json"
DEFAULT_MARKDOWN = ROOT / "docs" / "reports" / "gate0_source_optimized_dual_density_nba_2026-08-14.md"


def sign_class(value: float, tolerance: float) -> str:
    if value > tolerance:
        return "positive"
    if value < -tolerance:
        return "negative"
    return "zero"


def state_diagnostics(
    molecule: Any, state: dict[str, Any], roots: list[int]
) -> dict[str, Any]:
    density = np.asarray(state["_final_density"], dtype=float)
    energy = float(state["experimental_conditional_scf_energy_hartree"])
    return {
        "energy_hartree": energy,
        "converged": bool(state["converged"]),
        "cycles": int(state["cycles"]),
        "electron_trace": float(state["electron_trace"]),
        "density_fixed_point_residual": float(state["final_density_fixed_point_residual"]),
        "physical_metric_idempotency_residual": float(
            state["density_physical_metric_idempotency_residual"]
        ),
        "minimum_root_subspace_singular_value": float(
            state["minimum_root_subspace_singular_value"]
        ),
        "maximum_generalized_residual": float(state["maximum_generalized_residual"]),
        "maximum_cross_group_density_norm": maximum_cross_group_density(state),
        "energy_assembly_residual_hartree": abs(
            assembled_energy(molecule, density) - energy
        ),
        "group_sizes": [int(value) for value in state["group_sizes"]],
        "occupied_roots": [int(value) for value in roots],
        "column_order": [int(value) for value in state["order"]],
    }


def mode_checks(
    mode: str, states: dict[str, dict[str, Any]], ground_energy: float,
    cycle: dict[str, Any], expected_electrons: int, master: dict[str, Any],
) -> dict[str, bool]:
    acceptance = master["acceptance"]
    checks = {
        "all_states_converged": all(bool(state["converged"]) for state in states.values()),
        "density_fixed_points": all(
            float(state["density_fixed_point_residual"])
            <= float(acceptance["density_fixed_point_tolerance"])
            for state in states.values()
        ),
        "electron_traces": all(
            abs(float(state["electron_trace"]) - expected_electrons)
            <= float(acceptance["electron_trace_tolerance"])
            for state in states.values()
        ),
        "energy_assemblies_close": all(
            float(state["energy_assembly_residual_hartree"])
            <= float(acceptance["energy_assembly_tolerance_hartree"])
            for state in states.values()
        ),
        "four_term_path_closes": float(cycle["four_term_closure_residual_hartree"])
        <= float(acceptance["state_path_closure_tolerance_hartree"]),
        "root_subspace_continuity": all(
            float(state["minimum_root_subspace_singular_value"])
            >= float(acceptance["root_subspace_minimum_singular_value"])
            for state in states.values()
        ),
        "generalized_eigen_residuals": all(
            float(state["maximum_generalized_residual"])
            <= float(acceptance["generalized_eigen_residual_tolerance"])
            for state in states.values()
        ),
    }
    if mode == "source":
        checks["source_coordinate_cross_group_density_zero"] = all(
            float(state["maximum_cross_group_density_norm"])
            <= float(acceptance["source_cross_block_tolerance"])
            for state in states.values()
        )
    if mode == "physical":
        checks.update(
            {
                "physical_metric_idempotency": all(
                    float(state["physical_metric_idempotency_residual"])
                    <= float(acceptance["physical_idempotency_tolerance"])
                    for state in states.values()
                ),
                "ground_is_variational_minimum": all(
                    float(state["energy_hartree"]) >= ground_energy
                    - float(acceptance["variational_ordering_tolerance_hartree"])
                    for state in states.values()
                ),
                "all_release_steps_are_nonpositive": all(
                    float(value)
                    <= float(acceptance["variational_ordering_tolerance_hartree"])
                    for value in (
                        *cycle["effects_hartree"].values(),
                        cycle["bridge_hartree"],
                    )
                ),
            }
        )
    return checks


def run_point(
    master: dict[str, Any], source_master: dict[str, Any],
    geometry_master: dict[str, Any],
    atoms: list[list[Any]], angle: str,
) -> dict[str, Any]:
    config = configured_parent(source_master, geometry_master, atoms)
    config["experiment_id"] = f"{master['experiment_id']}/{angle}"
    internal = build_ful2_internal(config)
    definitions = state_definitions(internal)
    molecule = internal["molecule"]
    overlap = np.asarray(internal["overlap"], dtype=float)
    basis = np.asarray(internal["working_basis"], dtype=float)
    ground = run_ground_state(config)
    ground_energy = float(ground["energy"])
    mode_results: dict[str, Any] = {}
    final_densities: dict[str, dict[str, np.ndarray]] = {}
    tolerance = float(master["acceptance"]["sign_classification_tolerance_hartree"])
    for mode in ("source", "physical"):
        construction = str(master["density_constructions"][mode])
        state_rows: dict[str, dict[str, Any]] = {}
        energies: dict[str, float] = {}
        final_densities[mode] = {}
        for name in ("FUD", "DSI2", "FUL", "PDSI"):
            groups, roots = definitions[name]
            state = run_source_state(
                config,
                molecule,
                overlap,
                basis,
                groups,
                roots,
                density_reconstruction=construction,
            )
            state_rows[name] = state_diagnostics(molecule, state, roots)
            energies[name] = float(state_rows[name]["energy_hartree"])
            final_densities[mode][name] = np.asarray(
                state["_final_density"], dtype=float
            )
        cycle = state_cycle(ground_energy, energies)
        mode_results[mode] = {
            "density_construction": construction,
            "states": state_rows,
            "cycle": cycle,
            "effect_signs": {
                name: sign_class(float(value), tolerance)
                for name, value in cycle["effects_hartree"].items()
            },
        }
        mode_results[mode]["effect_signs"]["bridge"] = sign_class(
            float(cycle["bridge_hartree"]), tolerance
        )
        mode_results[mode]["checks"] = mode_checks(
            mode,
            state_rows,
            ground_energy,
            cycle,
            int(config["electronic_structure"]["expected_electrons"]),
            master,
        )
        mode_results[mode]["technical_pass"] = bool(
            all(mode_results[mode]["checks"].values())
        )

    comparisons: dict[str, Any] = {}
    for name in ("FUD", "DSI2", "FUL", "PDSI"):
        source_density = final_densities["source"][name]
        physical_density = final_densities["physical"][name]
        comparisons[name] = {
            "physical_minus_source_energy_hartree": (
                mode_results["physical"]["states"][name]["energy_hartree"]
                - mode_results["source"]["states"][name]["energy_hartree"]
            ),
            "density_relative_frobenius_difference": float(
                np.linalg.norm(physical_density - source_density, ord="fro")
                / max(float(np.linalg.norm(source_density, ord="fro")), 1.0)
            ),
            "source_idempotency_residual": mode_results["source"]["states"][name][
                "physical_metric_idempotency_residual"
            ],
            "physical_idempotency_residual": mode_results["physical"]["states"][name][
                "physical_metric_idempotency_residual"
            ],
        }
    source_nonidempotency_observed = any(
        float(value["source_idempotency_residual"])
        > float(master["acceptance"]["source_nonidempotency_detection_floor"])
        for value in comparisons.values()
    )
    signs_preserved = mode_results["source"]["effect_signs"] == mode_results[
        "physical"
    ]["effect_signs"]
    return {
        "angle_degrees": float(angle),
        "ground_energy_hartree": ground_energy,
        "ground_converged": bool(ground["converged"]),
        "lfmo_dimension": int(basis.shape[1]),
        "fragment_reflection_residuals": internal["fragment_reflection_residuals"],
        "modes": mode_results,
        "state_comparisons": comparisons,
        "source_nonidempotency_observed": source_nonidempotency_observed,
        "effect_signs_preserved": signs_preserved,
        "technical_pass": bool(
            ground["converged"]
            and mode_results["source"]["technical_pass"]
            and mode_results["physical"]["technical_pass"]
            and source_nonidempotency_observed
        ),
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(json_safe(value), indent=2, sort_keys=True), encoding="utf-8"
    )


def run(master: dict[str, Any], checkpoint_path: Path) -> dict[str, Any]:
    reconstruction = load_yaml(ROOT / str(master["reconstruction_config"]))
    source_master = load_yaml(ROOT / str(reconstruction["source_sigma_sigma_config"]))
    geometry_master = load_yaml(ROOT / str(reconstruction["source_geometry_config"]))
    geometry = json.loads(
        (ROOT / str(reconstruction["geometry_artifact"])).read_text(encoding="utf-8")
    )
    checkpoint = {
        "experiment_id": master["experiment_id"],
        "config_sha256": canonical_digest(master),
        "points": {},
    }
    if checkpoint_path.exists():
        candidate = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if (
            candidate.get("experiment_id") == master["experiment_id"]
            and candidate.get("config_sha256") == checkpoint["config_sha256"]
        ):
            checkpoint = candidate
    for angle in ("0.0", "17.0"):
        if angle not in checkpoint["points"]:
            checkpoint["points"][angle] = run_point(
                master,
                source_master,
                geometry_master,
                geometry["points"][angle]["atoms"],
                angle,
            )
            write_json(checkpoint_path, checkpoint)
    points = checkpoint["points"]
    technical_pass = all(bool(point["technical_pass"]) for point in points.values())
    signs_preserved = all(
        bool(point["effect_signs_preserved"]) for point in points.values()
    )
    physical_all_nonpositive = all(
        all(
            sign in {"negative", "zero"}
            for sign in point["modes"]["physical"]["effect_signs"].values()
        )
        for point in points.values()
    )
    torsion_deltas: dict[str, Any] = {}
    for mode in ("source", "physical"):
        zero = points["0.0"]["modes"][mode]["cycle"]
        twisted = points["17.0"]["modes"][mode]["cycle"]
        torsion_deltas[mode] = {
            "effects_hartree": {
                name: float(twisted["effects_hartree"][name])
                - float(zero["effects_hartree"][name])
                for name in ("pi_pi", "pi_sigma", "sigma_sigma")
            },
            "bridge_hartree": float(twisted["bridge_hartree"])
            - float(zero["bridge_hartree"]),
            "requested_total_hartree": float(twisted["requested_total_hartree"])
            - float(zero["requested_total_hartree"]),
        }
    disposition = (
        "PHYSICAL_PROJECTOR_PASS_SOURCE_SIGNS_NOT_PRESERVED"
        if technical_pass and physical_all_nonpositive and not signs_preserved
        else (
            "PHYSICAL_PROJECTOR_PASS_SOURCE_SIGNS_PRESERVED"
            if technical_pass and signs_preserved
            else "DUAL_DENSITY_VALIDATION_INCOMPLETE"
        )
    )
    return {
        "experiment_id": master["experiment_id"],
        "protocol": master["protocol"],
        "disposition": disposition,
        "technical_pass": technical_pass,
        "effect_signs_preserved_at_both_angles": signs_preserved,
        "physical_effects_all_nonpositive": physical_all_nonpositive,
        "torsion_deltas_17_minus_0": torsion_deltas,
        "points": points,
        "label_decision": {
            "source_stabilization_destabilization_label_allowed": False,
            "physical_variational_state_difference_label_allowed": technical_pass,
            "production_label_allowed": False,
        },
        "boundaries": master["boundaries"],
        "provenance": {
            "git_commit": git_commit(),
            "config_sha256": canonical_digest(master),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Gate 0 optimized NBA dual-density validation",
        "",
        f"- Disposition: **{report['disposition']}**",
        f"- Technical pass: `{report['technical_pass']}`",
        f"- Source signs preserved at both angles: `{report['effect_signs_preserved_at_both_angles']}`",
        f"- Physical effects all nonpositive: `{report['physical_effects_all_nonpositive']}`",
        "",
    ]
    for angle in ("0.0", "17.0"):
        point = report["points"][angle]
        lines.extend([f"## {angle} degrees", ""])
        lines.extend(
            [
                "| Effect | Source Eh | Source sign | Physical Eh | Physical sign |",
                "|---|---:|---|---:|---|",
            ]
        )
        for name in ("pi_pi", "pi_sigma", "sigma_sigma"):
            source_value = point["modes"]["source"]["cycle"]["effects_hartree"][name]
            physical_value = point["modes"]["physical"]["cycle"]["effects_hartree"][name]
            lines.append(
                f"| {name} | {source_value:.12f} | "
                f"{point['modes']['source']['effect_signs'][name]} | "
                f"{physical_value:.12f} | "
                f"{point['modes']['physical']['effect_signs'][name]} |"
            )
        source_bridge = point["modes"]["source"]["cycle"]["bridge_hartree"]
        physical_bridge = point["modes"]["physical"]["cycle"]["bridge_hartree"]
        lines.append(
            f"| bridge | {source_bridge:.12f} | "
            f"{point['modes']['source']['effect_signs']['bridge']} | "
            f"{physical_bridge:.12f} | "
            f"{point['modes']['physical']['effect_signs']['bridge']} |"
        )
        lines.extend(
            [
                "",
                "| State | Source idempotency | Physical idempotency | Physical-source energy (Eh) | Density relative difference |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for name in ("FUD", "DSI2", "FUL", "PDSI"):
            value = point["state_comparisons"][name]
            lines.append(
                f"| {name} | {value['source_idempotency_residual']:.6e} | "
                f"{value['physical_idempotency_residual']:.6e} | "
                f"{value['physical_minus_source_energy_hartree']:.12f} | "
                f"{value['density_relative_frobenius_difference']:.6e} |"
            )
        lines.extend(["", f"- Effect signs preserved: `{point['effect_signs_preserved']}`", ""])
    lines.extend(
        [
            "## Torsion deltas: 17 minus 0 degrees",
            "",
            "| Quantity | Source Eh | Physical Eh |",
            "|---|---:|---:|",
        ]
    )
    source_delta = report["torsion_deltas_17_minus_0"]["source"]
    physical_delta = report["torsion_deltas_17_minus_0"]["physical"]
    for name in ("pi_pi", "pi_sigma", "sigma_sigma"):
        lines.append(
            f"| {name} | {source_delta['effects_hartree'][name]:.12f} | "
            f"{physical_delta['effects_hartree'][name]:.12f} |"
        )
    for name, key in (("bridge", "bridge_hartree"), ("total", "requested_total_hartree")):
        lines.append(
            f"| {name} | {source_delta[key]:.12f} | {physical_delta[key]:.12f} |"
        )
    lines.extend(
        [
            "",
            "## Label boundary",
            "",
            "Source-block values remain nonvariational diagnostics and their positive signs are not preserved by the physical projector. Physical-projector state differences are classified as nested variational lowering from releasing constraints, not as source-equivalent stabilization or destabilization energies. Neither branch is released as a production label.",
            "",
        ]
    )
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
    write_json(args.output, report)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(
        f"{report['disposition']}: technical={report['technical_pass']}, "
        f"signs_preserved={report['effect_signs_preserved_at_both_angles']}"
    )
    return 0 if report["technical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
