"""Reconstruct the NBA source total from pi-pi, pi-sigma and sigma-sigma paths."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import numpy as np

from experiments.validation.chapter5_pi_sigma_reconstruction_gate0 import (
    HARTREE_TO_KCAL_MOL,
    canonical_digest,
    run_ground_state,
)
from experiments.validation.chapter5_three_effect_reconstruction_gate0 import (
    assembled_energy,
    maximum_cross_group_density,
    run_source_state,
)
from experiments.validation.dsi_fud_initial_density_reproducibility_gate0 import (
    resolve_state_config,
)
from experiments.validation.one_cut_conditional_scf_gate0 import (
    ROOT,
    git_commit,
    json_safe,
    load_yaml,
)
from experiments.validation.source_nonvariational_sigma_sigma_nba_gate0 import (
    build_ful2_internal,
    state_definitions_from_ful2,
)


DEFAULT_CONFIG = (
    ROOT
    / "configs"
    / "qm"
    / "source_optimized_three_effect_reconstruction_nba_v0.1.yaml"
)
DEFAULT_OUTPUT = (
    ROOT
    / "artifacts"
    / "raw"
    / "source_optimized_three_effect_reconstruction_nba_2026-08-14.json"
)
DEFAULT_CHECKPOINT = (
    ROOT
    / "artifacts"
    / "checkpoints"
    / "source_optimized_three_effect_reconstruction_nba_2026-08-14.json"
)
DEFAULT_MARKDOWN = (
    ROOT
    / "docs"
    / "reports"
    / "gate0_source_optimized_three_effect_reconstruction_nba_2026-08-14.md"
)


def state_cycle(ground_energy: float, energies: dict[str, float]) -> dict[str, Any]:
    effects = {
        "pi_pi": energies["FUD"] - energies["DSI2"],
        "pi_sigma": ground_energy - energies["FUD"],
        "sigma_sigma": energies["PDSI"] - energies["FUL"],
    }
    requested_total = ground_energy - energies["FUL"]
    three_effect_sum = sum(effects.values())
    bridge = energies["DSI2"] - energies["PDSI"]
    four_term_sum = three_effect_sum + bridge
    path_complete_effects = {
        "pi_pi": energies["FUD"] - energies["DSI2"],
        "pi_sigma": ground_energy - energies["FUD"],
        "sigma_sigma_total": energies["DSI2"] - energies["FUL"],
    }
    path_complete_three_term_sum = sum(path_complete_effects.values())
    return {
        "effects_hartree": effects,
        "path_complete_three_term_effects_hartree": path_complete_effects,
        "requested_total_hartree": requested_total,
        "three_effect_sum_hartree": three_effect_sum,
        "bridge_hartree": bridge,
        "four_term_sum_hartree": four_term_sum,
        "path_complete_three_term_sum_hartree": path_complete_three_term_sum,
        "three_effect_closure_residual_hartree": abs(
            three_effect_sum - requested_total
        ),
        "four_term_closure_residual_hartree": abs(
            four_term_sum - requested_total
        ),
        "path_complete_three_term_closure_residual_hartree": abs(
            path_complete_three_term_sum - requested_total
        ),
    }


def state_definitions(
    internal: dict[str, Any],
) -> dict[str, tuple[list[list[int]], list[int]]]:
    source = state_definitions_from_ful2(internal)
    types = list(internal["column_types"])
    fragments = list(internal["column_fragments"])
    pi = {
        fragment: [
            index
            for index, (kind, owner) in enumerate(zip(types, fragments, strict=True))
            if kind == "pi" and owner == fragment
        ]
        for fragment in ("A", "P")
    }
    sigma = [index for index, kind in enumerate(types) if kind == "sigma"]
    pi_roots = internal["bonded_pi_occupied_roots_by_fragment"]
    sigma_roots = internal["bonded_sigma_occupied_roots_by_fragment"]
    cut_roots = sum(internal["cut_single_count_by_fragment"].values()) // 2
    total_sigma_roots = sum(int(value) for value in sigma_roots.values()) + cut_roots
    return {
        "G": ([], []),
        "FUD": (
            [[*pi["A"], *pi["P"]], sigma],
            [sum(int(value) for value in pi_roots.values()), total_sigma_roots],
        ),
        "DSI2": (
            [pi["A"], pi["P"], sigma],
            [int(pi_roots["A"]), int(pi_roots["P"]), total_sigma_roots],
        ),
        "FUL": source["FUL"],
        "PDSI": source["PDSI"],
    }


def configured_parent(
    source_master: dict[str, Any], geometry_master: dict[str, Any], atoms: list[list[Any]]
) -> dict[str, Any]:
    base = resolve_state_config(ROOT / str(source_master["base_config"]))
    base["electronic_structure"]["basis"] = str(
        source_master["electronic_structure"]["basis"]
    )
    base["fud_state"]["density_reconstruction"] = str(
        source_master["source_definition"]["density_reconstruction"]
    )
    base["primitive_fragments"] = deepcopy(
        source_master["source_definition"]["fragments"]
    )
    interface = geometry_master["optimized_geometry_lfmo_interface"]
    for key in (
        "reflection_block_closure_tolerance",
        "reflection_eigenvalue_tolerance",
        "reflection_classification_policy",
        "minimum_absolute_reflection_eigenvalue",
        "maximum_accepted_reflection_residual",
    ):
        base["acceptance"][key] = interface[key]
    base["geometry"]["atoms"] = deepcopy(atoms)
    return base


def source_state_diagnostics(
    molecule: Any, state: dict[str, Any], roots: list[int]
) -> dict[str, Any]:
    density = np.asarray(state["_final_density"], dtype=float)
    energy = float(state["experimental_conditional_scf_energy_hartree"])
    return {
        "energy_hartree": energy,
        "converged": bool(state["converged"]),
        "cycles": int(state["cycles"]),
        "electron_trace": float(state["electron_trace"]),
        "density_fixed_point_residual": float(
            state["final_density_fixed_point_residual"]
        ),
        "physical_metric_idempotency_residual": float(
            state["density_physical_metric_idempotency_residual"]
        ),
        "maximum_source_cross_group_density_norm": maximum_cross_group_density(state),
        "energy_assembly_residual_hartree": abs(
            assembled_energy(molecule, density) - energy
        ),
        "group_sizes": [int(value) for value in state["group_sizes"]],
        "occupied_roots": [int(value) for value in roots],
        "column_order": [int(value) for value in state["order"]],
    }


def point_checks(
    point: dict[str, Any], master: dict[str, Any], angle: str
) -> dict[str, bool]:
    acceptance = master["acceptance"]
    states = point["states"]
    sigma_expected = float(master["accepted_sigma_sigma_endpoints_hartree"][angle])
    return {
        "ground_converged": bool(point["ground"]["converged"]),
        "all_source_states_converged": all(
            bool(state["converged"]) for state in states.values()
        ),
        "density_fixed_points": all(
            float(state["density_fixed_point_residual"])
            <= float(acceptance["density_fixed_point_tolerance"])
            for state in states.values()
        ),
        "electron_traces": all(
            abs(float(state["electron_trace"]) - float(point["expected_electrons"]))
            <= float(acceptance["electron_trace_tolerance"])
            for state in states.values()
        ),
        "source_cross_blocks_zero": all(
            float(state["maximum_source_cross_group_density_norm"])
            <= float(acceptance["source_cross_block_tolerance"])
            for state in states.values()
        ),
        "energy_assemblies_close": all(
            float(state["energy_assembly_residual_hartree"])
            <= float(acceptance["energy_assembly_tolerance_hartree"])
            for state in states.values()
        ),
        "all_states_partition_same_lfmo_columns": all(
            sorted(state["column_order"]) == list(range(point["lfmo_dimension"]))
            for state in states.values()
        ),
        "sigma_sigma_reproduces_accepted_endpoint": abs(
            float(point["cycle"]["effects_hartree"]["sigma_sigma"])
            - sigma_expected
        )
        <= float(acceptance["sigma_sigma_reproduction_tolerance_hartree"]),
        "four_term_state_path_closes": float(
            point["cycle"]["four_term_closure_residual_hartree"]
        )
        <= float(acceptance["state_path_closure_tolerance_hartree"]),
    }


def run_point(
    master: dict[str, Any], source_master: dict[str, Any],
    geometry_master: dict[str, Any], atoms: list[list[Any]], angle: str,
) -> dict[str, Any]:
    config = configured_parent(source_master, geometry_master, atoms)
    config["experiment_id"] = f"{master['experiment_id']}/{angle}"
    internal = build_ful2_internal(config)
    definitions = state_definitions(internal)
    molecule = internal["molecule"]
    overlap = np.asarray(internal["overlap"], dtype=float)
    basis = np.asarray(internal["working_basis"], dtype=float)
    source_states: dict[str, dict[str, Any]] = {}
    diagnostics: dict[str, dict[str, Any]] = {}
    for name in ("FUD", "DSI2", "FUL", "PDSI"):
        groups, roots = definitions[name]
        state = run_source_state(config, molecule, overlap, basis, groups, roots)
        source_states[name] = state
        diagnostics[name] = source_state_diagnostics(molecule, state, roots)
    ground = run_ground_state(config)
    energies = {name: float(value["energy_hartree"]) for name, value in diagnostics.items()}
    cycle = state_cycle(float(ground["energy"]), energies)
    point = {
        "angle_degrees": float(angle),
        "expected_electrons": int(config["electronic_structure"]["expected_electrons"]),
        "lfmo_dimension": int(basis.shape[1]),
        "fragment_reflection_residuals": internal["fragment_reflection_residuals"],
        "fragment_checks": internal["fragment_checks"],
        "ground": {
            "energy_hartree": float(ground["energy"]),
            "converged": bool(ground["converged"]),
        },
        "states": diagnostics,
        "cycle": cycle,
    }
    point["checks"] = point_checks(point, master, angle)
    point["technical_pass"] = bool(all(point["checks"].values()))
    point["three_effects_reconstruct"] = bool(
        cycle["three_effect_closure_residual_hartree"]
        <= float(master["acceptance"]["state_path_closure_tolerance_hartree"])
    )
    point["bridge_is_zero"] = bool(
        abs(cycle["bridge_hartree"])
        <= float(master["acceptance"]["bridge_zero_tolerance_hartree"])
    )
    return point


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(json_safe(value), indent=2, sort_keys=True), encoding="utf-8"
    )


def run(master: dict[str, Any], checkpoint_path: Path) -> dict[str, Any]:
    source_master = load_yaml(ROOT / str(master["source_sigma_sigma_config"]))
    geometry_master = load_yaml(ROOT / str(master["source_geometry_config"]))
    geometry = json.loads(
        (ROOT / str(master["geometry_artifact"])).read_text(encoding="utf-8")
    )
    angles = [float(value) for value in master["angles_degrees"]]
    if angles != [0.0, 17.0]:
        raise ValueError("only the fixed 0 and 17 degree points are authorized")
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
    three_effects_reconstruct = all(
        bool(point["three_effects_reconstruct"]) for point in points.values()
    )
    four_term_paths_reconstruct = all(
        point["cycle"]["four_term_closure_residual_hartree"]
        <= float(master["acceptance"]["state_path_closure_tolerance_hartree"])
        for point in points.values()
    )
    path_complete_three_term_reconstruct = all(
        point["cycle"]["path_complete_three_term_closure_residual_hartree"]
        <= float(master["acceptance"]["state_path_closure_tolerance_hartree"])
        for point in points.values()
    )
    disposition = (
        "THREE_EFFECT_SOURCE_TABLE_PATH_PASS"
        if technical_pass and three_effects_reconstruct
        else (
            "PATH_COMPLETE_THREE_TERM_PASS_SIGMA_BRIDGE_ASSIGNED"
            if technical_pass and path_complete_three_term_reconstruct
            else (
                "FOUR_TERM_SAME_HAMILTONIAN_PATH_PASS_BRIDGE_REQUIRED"
                if technical_pass and four_term_paths_reconstruct
                else "SAME_HAMILTONIAN_RECONSTRUCTION_INCOMPLETE"
            )
        )
    )
    return {
        "experiment_id": master["experiment_id"],
        "protocol": master["protocol"],
        "disposition": disposition,
        "technical_pass": technical_pass,
        "three_effects_reconstruct_at_both_angles": three_effects_reconstruct,
        "four_term_paths_reconstruct_at_both_angles": four_term_paths_reconstruct,
        "path_complete_three_term_reconstructs_at_both_angles": path_complete_three_term_reconstruct,
        "points": points,
        "state_path": ["FUL", "PDSI", "DSI2", "FUD", "G"],
        "state_differences": master["state_differences"],
        "boundaries": master["boundaries"],
        "provenance": {
            "git_commit": git_commit(),
            "config_sha256": canonical_digest(master),
            "geometry_artifact": master["geometry_artifact"],
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Gate 0 source-optimized NBA three-effect reconstruction",
        "",
        f"- Disposition: **{report['disposition']}**",
        f"- Technical pass: `{report['technical_pass']}`",
        f"- Three effects reconstruct at both angles: `{report['three_effects_reconstruct_at_both_angles']}`",
        f"- Four-term state path reconstructs at both angles: `{report['four_term_paths_reconstruct_at_both_angles']}`",
        f"- Path-complete three-term reconstruction at both angles: `{report['path_complete_three_term_reconstructs_at_both_angles']}`",
        "- Common Hamiltonian: `RHF/STO-3G`",
        "- State path: `FUL -> PDSI -> DSI2 -> FUD -> G`",
        "",
    ]
    for angle in ("0.0", "17.0"):
        point = report["points"][angle]
        cycle = point["cycle"]
        lines.extend(
            [
                f"## {angle} degrees",
                "",
                "| Quantity | Eh | kcal/mol |",
                "|---|---:|---:|",
            ]
        )
        for name in ("pi_pi", "pi_sigma", "sigma_sigma"):
            value = float(cycle["effects_hartree"][name])
            lines.append(f"| {name} | {value:.12f} | {value * HARTREE_TO_KCAL_MOL:.6f} |")
        lines.append(
            "| sigma_sigma_total (includes sigma bridge) | "
            f"{cycle['path_complete_three_term_effects_hartree']['sigma_sigma_total']:.12f} | "
            f"{cycle['path_complete_three_term_effects_hartree']['sigma_sigma_total'] * HARTREE_TO_KCAL_MOL:.6f} |"
        )
        for name, key in (
            ("three-effect sum", "three_effect_sum_hartree"),
            ("bridge E_DSI2-E_PDSI", "bridge_hartree"),
            ("four-term sum", "four_term_sum_hartree"),
            ("path-complete three-term sum", "path_complete_three_term_sum_hartree"),
            ("requested total E_G-E_FUL", "requested_total_hartree"),
        ):
            value = float(cycle[key])
            lines.append(f"| {name} | {value:.12f} | {value * HARTREE_TO_KCAL_MOL:.6f} |")
        lines.extend(
            [
                "",
                f"- Three-effect closure residual: `{cycle['three_effect_closure_residual_hartree']:.3e} Eh`",
                f"- Four-term closure residual: `{cycle['four_term_closure_residual_hartree']:.3e} Eh`",
                f"- Path-complete three-term closure residual: `{cycle['path_complete_three_term_closure_residual_hartree']:.3e} Eh`",
                f"- Bridge is zero: `{point['bridge_is_zero']}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Boundary",
            "",
            "All states at a given angle use one optimized geometry, one RHF/STO-3G Hamiltonian, and one geometry-specific LFMO basis. The source ledger remains nonvariational and no stabilization label is generated.",
            "",
            "The three named effects are not a complete decomposition of `E_G-E_FUL`: `DSI2` has one coupled sigma system, while `PDSI` keeps bonded sigma and cut-single sigma as separate systems. Their nonzero difference is the required sigma bridge that restores the cut covalent-bond coupling.",
            "An exact path-complete three-term decomposition is available by assigning the sigma-only bridge `E_DSI2-E_PDSI` to `sigma_sigma_total = E_DSI2-E_FUL`. The Table 5-19 subterm `E_PDSI-E_FUL` remains separately identifiable.",
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
        f"{report['disposition']}: "
        f"three={report['three_effects_reconstruct_at_both_angles']}, "
        f"four={report['four_term_paths_reconstruct_at_both_angles']}"
    )
    return 0 if report["technical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
