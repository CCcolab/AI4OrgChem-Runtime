"""Decompose four optimized-NBA physical releases into direct and response terms."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from experiments.validation.chapter5_pi_sigma_reconstruction_gate0 import (
    HARTREE_TO_KCAL_MOL,
    block_energy,
    canonical_digest,
    density_in_working_basis,
    run_ground_state,
)
from experiments.validation.chapter5_three_effect_reconstruction_gate0 import (
    assembled_energy,
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
from experiments.validation.source_optimized_dual_density_nba_gate0 import (
    sign_class,
    state_diagnostics,
)
from experiments.validation.source_optimized_three_effect_reconstruction_nba_gate0 import (
    configured_parent,
    state_cycle,
    state_definitions,
)


DEFAULT_CONFIG = ROOT / "configs" / "qm" / "source_optimized_physical_direct_response_nba_v0.1.yaml"
DEFAULT_OUTPUT = ROOT / "artifacts" / "raw" / "source_optimized_physical_direct_response_nba_2026-08-14.json"
DEFAULT_CHECKPOINT = ROOT / "artifacts" / "checkpoints" / "source_optimized_physical_direct_response_nba_2026-08-14.json"
DEFAULT_MARKDOWN = ROOT / "docs" / "reports" / "gate0_source_optimized_physical_direct_response_nba_2026-08-14.md"
PHYSICAL_DENSITY = "physical_metric_nonorthogonal_occupied_projector"


def validate_partition(groups: list[list[int]], dimension: int) -> None:
    flattened = [index for group in groups for index in group]
    if any(not group for group in groups):
        raise ValueError("direct-response groups must be nonempty")
    if sorted(flattened) != list(range(dimension)):
        raise ValueError("direct-response groups must partition the LFMO basis")


def block_components(
    molecule: Any,
    basis: np.ndarray,
    density_ao: np.ndarray,
    groups: list[list[int]],
    labels: list[str],
) -> dict[str, Any]:
    """Resolve one physical density into exact cross- and within-group energies."""
    if len(groups) != len(labels):
        raise ValueError("each group requires one stable label")
    validate_partition(groups, basis.shape[1])
    density, reconstruction = density_in_working_basis(basis, density_ao)

    from pyscf import scf

    mean_field = scf.RHF(molecule)
    mean_field.verbose = 0
    hcore_ao = np.asarray(mean_field.get_hcore(), dtype=float)
    effective_ao = np.asarray(mean_field.get_veff(molecule, density_ao), dtype=float)
    hcore = basis.T @ hcore_ao @ basis
    effective = basis.T @ effective_ao @ basis
    fock = hcore + effective
    zero = np.zeros_like(hcore)

    cross_pairs: dict[str, float] = {}
    cross_one_electron: dict[str, float] = {}
    cross_two_electron: dict[str, float] = {}
    for left in range(len(groups)):
        for right in range(left + 1, len(groups)):
            key = f"{labels[left]}__{labels[right]}"
            rows, columns = groups[left], groups[right]
            cross_pairs[key] = block_energy(
                hcore, fock, density, rows, columns, 1.0
            )
            cross_one_electron[key] = block_energy(
                hcore, hcore, density, rows, columns, 1.0
            )
            cross_two_electron[key] = block_energy(
                zero, effective, density, rows, columns, 1.0
            )

    within_groups = {
        label: block_energy(hcore, fock, density, group, group, 0.5)
        for label, group in zip(labels, groups, strict=True)
    }
    cross = float(sum(cross_pairs.values()))
    within = float(sum(within_groups.values()))
    electronic = cross + within
    assembled = assembled_energy(molecule, density_ao)
    return {
        "cross_group_hartree": cross,
        "within_group_hartree": within,
        "electronic_energy_hartree": electronic,
        "total_energy_hartree": assembled,
        "cross_pair_terms_hartree": cross_pairs,
        "within_group_terms_hartree": within_groups,
        "cross_one_electron_hartree": float(sum(cross_one_electron.values())),
        "cross_two_electron_hartree": float(sum(cross_two_electron.values())),
        "cross_one_electron_by_pair_hartree": cross_one_electron,
        "cross_two_electron_by_pair_hartree": cross_two_electron,
        "density_reconstruction_residual": reconstruction,
        "block_energy_assembly_residual_hartree": abs(
            electronic + float(molecule.energy_nuc()) - assembled
        ),
        "cross_split_residual_hartree": abs(
            cross
            - float(sum(cross_one_electron.values()))
            - float(sum(cross_two_electron.values()))
        ),
    }


def direct_response_decomposition(
    molecule: Any,
    basis: np.ndarray,
    relaxed_energy: float,
    relaxed_density_ao: np.ndarray,
    restricted_energy: float,
    restricted_density_ao: np.ndarray,
    restricted_groups: list[list[int]],
    group_labels: list[str],
    endpoint_expression: str,
    sign_tolerance: float,
) -> dict[str, Any]:
    """Apply an exact two-term identity to one nested physical-state release.

    In a nonorthogonal LFMO basis the restricted physical projector generally
    has metric-induced cross-group coordinate density.  Consequently the net
    direct term is C(relaxed)-C(restricted), not C(relaxed) alone.  The orbital
    response term is W(relaxed)-W(restricted), where W is the within-group
    electronic energy.  Nuclear repulsion cancels at fixed geometry.
    """
    relaxed = block_components(
        molecule, basis, relaxed_density_ao, restricted_groups, group_labels
    )
    restricted = block_components(
        molecule, basis, restricted_density_ao, restricted_groups, group_labels
    )
    direct = float(relaxed["cross_group_hartree"] - restricted["cross_group_hartree"])
    response = float(
        relaxed["within_group_hartree"] - restricted["within_group_hartree"]
    )
    endpoint = float(relaxed_energy - restricted_energy)
    component_sum = direct + response
    direct_one = float(
        relaxed["cross_one_electron_hartree"]
        - restricted["cross_one_electron_hartree"]
    )
    direct_two = float(
        relaxed["cross_two_electron_hartree"]
        - restricted["cross_two_electron_hartree"]
    )
    positive_direct_masked = bool(
        direct > sign_tolerance
        and endpoint < -sign_tolerance
        and response < -direct - sign_tolerance
    )
    return {
        "method": "physical_nonorthogonal_cross_change_plus_within_response_identity",
        "endpoint_expression": endpoint_expression,
        "endpoint_hartree": endpoint,
        "direct_cross_group_change_hartree": direct,
        "orbital_response_hartree": response,
        "component_sum_hartree": component_sum,
        "closure_residual_hartree": abs(component_sum - endpoint),
        "direct_one_electron_change_hartree": direct_one,
        "direct_two_electron_change_hartree": direct_two,
        "direct_split_residual_hartree": abs(direct - direct_one - direct_two),
        "relaxed_cross_group_hartree": relaxed["cross_group_hartree"],
        "restricted_cross_group_baseline_hartree": restricted["cross_group_hartree"],
        "relaxed_within_group_hartree": relaxed["within_group_hartree"],
        "restricted_within_group_hartree": restricted["within_group_hartree"],
        "direct_sign": sign_class(direct, sign_tolerance),
        "response_sign": sign_class(response, sign_tolerance),
        "endpoint_sign": sign_class(endpoint, sign_tolerance),
        "positive_direct_masked_by_response": positive_direct_masked,
        "relaxed_components": relaxed,
        "restricted_components": restricted,
        "interpretation": {
            "allowed": "physical LFMO cross-group component change and within-group orbital response",
            "forbidden": "source-equivalent stabilization or destabilization production label",
            "restricted_cross_baseline_subtracted": True,
            "production_label_allowed": False,
        },
    }


def transition_specs(
    definitions: dict[str, tuple[list[list[int]], list[int]]]
) -> dict[str, dict[str, Any]]:
    return {
        "pi_sigma": {
            "relaxed": "G",
            "restricted": "FUD",
            "groups": definitions["FUD"][0],
            "labels": ["pi_all", "sigma_all"],
            "expression": "E_G-E_FUD",
        },
        "pi_pi": {
            "relaxed": "FUD",
            "restricted": "DSI2",
            "groups": definitions["DSI2"][0],
            "labels": ["pi_A", "pi_P", "sigma_all"],
            "expression": "E_FUD-E_DSI2",
        },
        "bridge": {
            "relaxed": "DSI2",
            "restricted": "PDSI",
            "groups": definitions["PDSI"][0],
            "labels": ["pi_A", "pi_P", "bonded_sigma_all", "cut_sigma_all"],
            "expression": "E_DSI2-E_PDSI",
        },
        "sigma_sigma": {
            "relaxed": "PDSI",
            "restricted": "FUL",
            "groups": definitions["FUL"][0],
            "labels": [
                "pi_A", "pi_P", "bonded_sigma_A", "bonded_sigma_P", "cut_sigma_all"
            ],
            "expression": "E_PDSI-E_FUL",
        },
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

    ground = run_ground_state(config)
    densities: dict[str, np.ndarray] = {"G": np.asarray(ground["density"], dtype=float)}
    energies: dict[str, float] = {"G": float(ground["energy"])}
    states: dict[str, dict[str, Any]] = {}
    for name in ("FUD", "DSI2", "PDSI", "FUL"):
        groups, roots = definitions[name]
        state = run_source_state(
            config, molecule, overlap, basis, groups, roots,
            density_reconstruction=PHYSICAL_DENSITY,
        )
        densities[name] = np.asarray(state["_final_density"], dtype=float)
        energies[name] = float(state["experimental_conditional_scf_energy_hartree"])
        states[name] = state_diagnostics(molecule, state, roots)

    tolerance = float(master["acceptance"]["sign_classification_tolerance_hartree"])
    transitions = {}
    for name, spec in transition_specs(definitions).items():
        transitions[name] = direct_response_decomposition(
            molecule,
            basis,
            energies[str(spec["relaxed"])],
            densities[str(spec["relaxed"])],
            energies[str(spec["restricted"])],
            densities[str(spec["restricted"])],
            spec["groups"],
            spec["labels"],
            str(spec["expression"]),
            tolerance,
        )

    cycle = state_cycle(float(ground["energy"]), {
        name: energies[name] for name in ("FUD", "DSI2", "PDSI", "FUL")
    })
    acceptance = master["acceptance"]
    checks = {
        "ground_converged": bool(ground["converged"]),
        "all_states_converged": all(bool(state["converged"]) for state in states.values()),
        "density_fixed_points": all(
            float(state["density_fixed_point_residual"])
            <= float(acceptance["density_fixed_point_tolerance"])
            for state in states.values()
        ),
        "electron_traces": all(
            abs(float(state["electron_trace"]) - int(config["electronic_structure"]["expected_electrons"]))
            <= float(acceptance["electron_trace_tolerance"])
            for state in states.values()
        ),
        "physical_metric_idempotency": all(
            float(state["physical_metric_idempotency_residual"])
            <= float(acceptance["physical_idempotency_tolerance"])
            for state in states.values()
        ),
        "state_energy_assemblies_close": all(
            float(state["energy_assembly_residual_hartree"])
            <= float(acceptance["energy_assembly_tolerance_hartree"])
            for state in states.values()
        ),
        "all_transition_identities_close": all(
            float(value["closure_residual_hartree"])
            <= float(acceptance["transition_closure_tolerance_hartree"])
            for value in transitions.values()
        ),
        "all_block_energy_assemblies_close": all(
            max(
                float(value[side]["block_energy_assembly_residual_hartree"])
                for side in ("relaxed_components", "restricted_components")
            ) <= float(acceptance["block_energy_assembly_tolerance_hartree"])
            for value in transitions.values()
        ),
        "all_direct_splits_close": all(
            float(value["direct_split_residual_hartree"])
            <= float(acceptance["direct_split_tolerance_hartree"])
            for value in transitions.values()
        ),
        "all_release_endpoints_nonpositive": all(
            float(value["endpoint_hartree"])
            <= float(acceptance["variational_ordering_tolerance_hartree"])
            for value in transitions.values()
        ),
        "four_term_state_path_closes": float(cycle["four_term_closure_residual_hartree"])
        <= float(acceptance["state_path_closure_tolerance_hartree"]),
    }
    return {
        "angle_degrees": float(angle),
        "lfmo_dimension": int(basis.shape[1]),
        "ground_energy_hartree": float(ground["energy"]),
        "states": states,
        "transitions": transitions,
        "cycle": cycle,
        "checks": checks,
        "technical_pass": bool(all(checks.values())),
        "positive_direct_masked_transitions": [
            name for name, value in transitions.items()
            if bool(value["positive_direct_masked_by_response"])
        ],
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(value), indent=2, sort_keys=True), encoding="utf-8")


def run(master: dict[str, Any], checkpoint_path: Path) -> dict[str, Any]:
    dual = load_yaml(ROOT / str(master["dual_density_config"]))
    reconstruction = load_yaml(ROOT / str(dual["reconstruction_config"]))
    source_master = load_yaml(ROOT / str(reconstruction["source_sigma_sigma_config"]))
    geometry_master = load_yaml(ROOT / str(reconstruction["source_geometry_config"]))
    geometry = json.loads((ROOT / str(reconstruction["geometry_artifact"])).read_text(encoding="utf-8"))
    if [float(value) for value in master["angles_degrees"]] != [0.0, 17.0]:
        raise ValueError("only the fixed 0 and 17 degree points are authorized")
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
            checkpoint["points"][angle] = run_point(
                master, source_master, geometry_master,
                geometry["points"][angle]["atoms"], angle,
            )
            write_json(checkpoint_path, checkpoint)
    points = checkpoint["points"]
    technical_pass = all(bool(point["technical_pass"]) for point in points.values())
    masked = {
        angle: list(point["positive_direct_masked_transitions"])
        for angle, point in points.items()
    }
    any_masked = any(masked.values())
    tolerance = float(master["acceptance"]["sign_classification_tolerance_hartree"])
    nonzero_transitions = [
        value
        for point in points.values()
        for value in point["transitions"].values()
        if abs(float(value["endpoint_hartree"])) > tolerance
    ]
    all_nonzero_direct_changes_negative = bool(nonzero_transitions) and all(
        float(value["direct_cross_group_change_hartree"]) < -tolerance
        for value in nonzero_transitions
    )
    all_nonzero_responses_positive = bool(nonzero_transitions) and all(
        float(value["orbital_response_hartree"]) > tolerance
        for value in nonzero_transitions
    )
    disposition = (
        "PHYSICAL_DIRECT_RESPONSE_PASS_POSITIVE_DIRECT_MASKING_OBSERVED"
        if technical_pass and any_masked
        else (
            "PHYSICAL_DIRECT_RESPONSE_PASS_NO_POSITIVE_DIRECT_MASKING"
            if technical_pass else "PHYSICAL_DIRECT_RESPONSE_INCOMPLETE"
        )
    )
    return {
        "experiment_id": master["experiment_id"],
        "protocol": master["protocol"],
        "disposition": disposition,
        "technical_pass": technical_pass,
        "positive_direct_masking_observed": any_masked,
        "all_nonzero_direct_changes_negative": all_nonzero_direct_changes_negative,
        "all_nonzero_responses_positive": all_nonzero_responses_positive,
        "masked_transitions_by_angle": masked,
        "points": points,
        "label_decision": {
            "physical_component_interpretation_allowed": technical_pass,
            "stabilization_destabilization_production_label_allowed": False,
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
        "# Gate 0 optimized NBA physical direct-response decomposition",
        "",
        f"- Disposition: **{report['disposition']}**",
        f"- Technical pass: `{report['technical_pass']}`",
        f"- Positive direct masking observed: `{report['positive_direct_masking_observed']}`",
        f"- All nonzero direct changes negative: `{report['all_nonzero_direct_changes_negative']}`",
        f"- All nonzero responses positive: `{report['all_nonzero_responses_positive']}`",
        "",
        "The exact physical identity is `endpoint = [C(relaxed)-C(restricted)] + [W(relaxed)-W(restricted)]`. C is the cross-group electronic component and W is the within-group component in one shared LFMO coordinate basis. Subtracting the restricted cross baseline is mandatory for a nonorthogonal physical projector.",
        "",
    ]
    for angle in ("0.0", "17.0"):
        point = report["points"][angle]
        lines.extend([
            f"## {angle} degrees", "",
            "| Transition | Direct change (Eh) | Response (Eh) | Endpoint (Eh) | Masked? | Closure (Eh) |",
            "|---|---:|---:|---:|---|---:|",
        ])
        for name in ("pi_sigma", "pi_pi", "bridge", "sigma_sigma"):
            value = point["transitions"][name]
            lines.append(
                f"| {name} | {value['direct_cross_group_change_hartree']:.12f} | "
                f"{value['orbital_response_hartree']:.12f} | {value['endpoint_hartree']:.12f} | "
                f"{value['positive_direct_masked_by_response']} | {value['closure_residual_hartree']:.3e} |"
            )
        lines.extend(["", "Cross-group baselines:", "", "| Transition | C(relaxed) | C(restricted) | One-electron direct change | Two-electron direct change |", "|---|---:|---:|---:|---:|"])
        for name in ("pi_sigma", "pi_pi", "bridge", "sigma_sigma"):
            value = point["transitions"][name]
            lines.append(
                f"| {name} | {value['relaxed_cross_group_hartree']:.12f} | "
                f"{value['restricted_cross_group_baseline_hartree']:.12f} | "
                f"{value['direct_one_electron_change_hartree']:.12f} | "
                f"{value['direct_two_electron_change_hartree']:.12f} |"
            )
        lines.extend(["", f"- Masked transitions: `{', '.join(point['positive_direct_masked_transitions']) or 'none'}`", ""])
    lines.extend([
        "## Observed physical pattern", "",
        "No positive net direct change is hidden by a negative response. Every nonzero transition instead has a negative cross-group direct change and a positive within-group response penalty. Thus orbital response partially cancels the direct lowering. A positive relaxed cross component alone is not evidence of positive direct activation because the nonorthogonal restricted-state cross baseline must first be subtracted.", "",
        "## Interpretation boundary", "",
        "A positive net direct change with a negative endpoint and a more-negative response demonstrates masking at the physical component level. It does not by itself establish the source-defined total conjugative destabilization claim. All values remain nonproduction diagnostics.", "",
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
    write_json(args.output, report)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(
        f"{report['disposition']}: technical={report['technical_pass']}, "
        f"masked={report['positive_direct_masking_observed']}"
    )
    return 0 if report["technical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
