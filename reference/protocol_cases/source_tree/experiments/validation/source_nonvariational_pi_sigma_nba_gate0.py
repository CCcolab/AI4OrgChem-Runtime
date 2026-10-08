"""Replicate the Chapter 5 pi-sigma sign in an isolated source-definition ledger."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import numpy as np

from ai4orgchem.lfmo.state_masks import apply_symmetric_mask, block_mask
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
    state_definitions_from_internal,
)
from experiments.validation.dsi2_divinyl_imine_source_shaped_gate0 import full_stage
from experiments.validation.dsi2_divinyl_imine_torsion_continuation_gate0 import (
    rotate_about_axis,
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


DEFAULT_CONFIG = ROOT / "configs" / "qm" / "source_nonvariational_pi_sigma_nba_v0.1.yaml"
DEFAULT_OUTPUT = ROOT / "artifacts" / "raw" / "source_nonvariational_pi_sigma_nba_2026-08-14.json"
DEFAULT_MARKDOWN = ROOT / "docs" / "reports" / "gate0_source_nonvariational_pi_sigma_nba_2026-08-14.md"


def source_pi_sigma_components(
    molecule: Any,
    ground: dict[str, Any],
    fud_state: dict[str, Any],
    original_fragments: list[str],
    original_roles: list[str],
) -> dict[str, Any]:
    basis = np.asarray(fud_state["working_basis"], dtype=float)
    density_ground, ground_reconstruction = density_in_working_basis(
        basis, np.asarray(ground["density"], dtype=float)
    )
    density_fud_ao = np.asarray(fud_state["_final_density"], dtype=float)
    density_fud, fud_reconstruction = density_in_working_basis(
        basis, density_fud_ao
    )
    hcore_ao = np.asarray(ground["hcore"], dtype=float)
    mean_field = ground["mean_field"].__class__(molecule)
    mean_field.verbose = 0
    fock_fud_ao = hcore_ao + np.asarray(
        mean_field.get_veff(molecule, density_fud_ao), dtype=float
    )
    hcore = basis.T @ hcore_ao @ basis
    fock_ground = basis.T @ np.asarray(ground["fock"], dtype=float) @ basis
    fock_fud = basis.T @ fock_fud_ao @ basis
    pi_size = int(fud_state["group_sizes"][0])
    pi = list(range(pi_size))
    sigma = list(range(pi_size, basis.shape[1]))

    direct = block_energy(hcore, fock_ground, density_ground, pi, sigma, 1.0)
    pi_response = block_energy(
        hcore, fock_ground, density_ground, pi, pi, 0.5
    ) - block_energy(hcore, fock_fud, density_fud, pi, pi, 0.5)
    sigma_response = block_energy(
        hcore, fock_ground, density_ground, sigma, sigma, 0.5
    ) - block_energy(hcore, fock_fud, density_fud, sigma, sigma, 0.5)
    endpoint = float(ground["energy"]) - float(
        fud_state["experimental_conditional_scf_energy_hartree"]
    )
    ordered_fragments = [
        original_fragments[index] for index in fud_state["order"]
    ]
    ordered_roles = [original_roles[index] for index in fud_state["order"]]
    direct_pairs: dict[str, float] = {}
    direct_intrafragment = 0.0
    for pi_fragment in ("A", "B", "C"):
        rows = [index for index in pi if ordered_fragments[index] == pi_fragment]
        for sigma_fragment in ("A", "B", "C"):
            columns = [
                index
                for index in sigma
                if ordered_fragments[index] == sigma_fragment
            ]
            value = block_energy(
                hcore, fock_ground, density_ground, rows, columns, 1.0
            )
            direct_pairs[f"pi_{pi_fragment}__sigma_{sigma_fragment}"] = value
            if pi_fragment == sigma_fragment:
                direct_intrafragment += value
    component_sum = direct + pi_response + sigma_response

    sigma_categories: dict[str, list[int]] = {}
    for index in sigma:
        role = ordered_roles[index]
        fragment = ordered_fragments[index]
        label = (
            f"bonded_sigma_{fragment}"
            if role == "bonded"
            else f"cut_sigma_{fragment}"
        )
        sigma_categories.setdefault(label, []).append(index)
    sigma_category_order = [
        label
        for role in ("bonded_sigma", "cut_sigma")
        for fragment in ("A", "B", "C")
        if (label := f"{role}_{fragment}") in sigma_categories
    ]
    sigma_response_by_pair: dict[str, float] = {}
    sigma_one_electron_by_pair: dict[str, float] = {}
    sigma_two_electron_by_pair: dict[str, float] = {}
    zero = np.zeros_like(hcore)
    for left, left_label in enumerate(sigma_category_order):
        left_indices = sigma_categories[left_label]
        for right in range(left, len(sigma_category_order)):
            right_label = sigma_category_order[right]
            right_indices = sigma_categories[right_label]
            factor = 0.5 if left == right else 1.0
            pair_label = f"{left_label}__{right_label}"
            sigma_response_by_pair[pair_label] = block_energy(
                hcore,
                fock_ground,
                density_ground,
                left_indices,
                right_indices,
                factor,
            ) - block_energy(
                hcore,
                fock_fud,
                density_fud,
                left_indices,
                right_indices,
                factor,
            )
            sigma_one_electron_by_pair[pair_label] = block_energy(
                hcore,
                hcore,
                density_ground,
                left_indices,
                right_indices,
                factor,
            ) - block_energy(
                hcore,
                hcore,
                density_fud,
                left_indices,
                right_indices,
                factor,
            )
            sigma_two_electron_by_pair[pair_label] = block_energy(
                zero,
                fock_ground - hcore,
                density_ground,
                left_indices,
                right_indices,
                factor,
            ) - block_energy(
                zero,
                fock_fud - hcore,
                density_fud,
                left_indices,
                right_indices,
                factor,
            )

    def role_pair(label: str) -> str:
        left, right = label.split("__", 1)
        left_role = "cut" if left.startswith("cut_") else "bonded"
        right_role = "cut" if right.startswith("cut_") else "bonded"
        return "__".join(sorted((left_role, right_role)))

    sigma_response_by_role_pair: dict[str, float] = {}
    for label, value in sigma_response_by_pair.items():
        key = role_pair(label)
        sigma_response_by_role_pair[key] = (
            sigma_response_by_role_pair.get(key, 0.0) + value
        )
    sigma_one_electron_total = sum(sigma_one_electron_by_pair.values())
    sigma_two_electron_total = sum(sigma_two_electron_by_pair.values())
    offsets = np.cumsum([0, *fud_state["group_sizes"]])
    source_cross_density = max(
        (
            float(
                np.linalg.norm(
                    density_fud[
                        offsets[left] : offsets[left + 1],
                        offsets[right] : offsets[right + 1],
                    ],
                    ord="fro",
                )
            )
            for left in range(len(fud_state["group_sizes"]))
            for right in range(left + 1, len(fud_state["group_sizes"]))
        ),
        default=0.0,
    )
    metric = basis.T @ molecule.intor_symmetric("int1e_ovlp") @ basis
    mask = block_mask(fud_state["group_sizes"])
    masked_metric = apply_symmetric_mask(metric, mask)
    masked_fock = apply_symmetric_mask(fock_fud, mask)
    cross_mask = 1.0 - mask
    explicit_energy = 0.5 * float(
        np.einsum("ij,ji->", hcore_ao + fock_fud_ao, density_fud_ao)
    ) + float(molecule.energy_nuc())
    return {
        "endpoint_expression": "E_G-E_FUD",
        "endpoint_hartree": endpoint,
        "endpoint_kcal_mol": endpoint * HARTREE_TO_KCAL_MOL,
        "direct_total_hartree": direct,
        "direct_intrafragment_hartree": direct_intrafragment,
        "direct_interfragment_hartree": direct - direct_intrafragment,
        "direct_by_fragment_pair_hartree": direct_pairs,
        "pi_response_hartree": pi_response,
        "sigma_response_hartree": sigma_response,
        "sigma_response_by_category_pair_hartree": sigma_response_by_pair,
        "sigma_response_by_role_pair_hartree": sigma_response_by_role_pair,
        "sigma_response_one_electron_hartree": sigma_one_electron_total,
        "sigma_response_two_electron_hartree": sigma_two_electron_total,
        "sigma_response_category_closure_residual_hartree": abs(
            sum(sigma_response_by_pair.values()) - sigma_response
        ),
        "sigma_response_electronic_split_residual_hartree": abs(
            sigma_one_electron_total + sigma_two_electron_total - sigma_response
        ),
        "component_sum_hartree": component_sum,
        "equation_closure_residual_hartree": abs(component_sum - endpoint),
        "source_density_physical_idempotency_residual": float(
            fud_state["density_physical_metric_idempotency_residual"]
        ),
        "source_cross_group_density_norm": source_cross_density,
        "masked_overlap_cross_block_norm": float(
            np.linalg.norm(masked_metric * cross_mask, ord="fro")
        ),
        "masked_fock_cross_block_norm_hartree": float(
            np.linalg.norm(masked_fock * cross_mask, ord="fro")
        ),
        "ground_density_reconstruction_residual": ground_reconstruction,
        "fud_density_reconstruction_residual": fud_reconstruction,
        "pyscf_vs_explicit_energy_residual_hartree": abs(
            explicit_energy
            - float(fud_state["experimental_conditional_scf_energy_hartree"])
        ),
        "pyscf_vs_assembled_helper_residual_hartree": abs(
            assembled_energy(molecule, density_fud_ao)
            - float(fud_state["experimental_conditional_scf_energy_hartree"])
        ),
        "interpretation": {
            "ledger": "source_nonvariational_definition",
            "physical_variational_energy": False,
            "production_label_allowed": False,
        },
    }


def run_point(
    config: dict[str, Any],
    internal: dict[str, Any],
) -> dict[str, Any]:
    molecule = internal["molecule"]
    overlap = np.asarray(internal["overlap"], dtype=float)
    basis = np.asarray(internal["working_basis"], dtype=float)
    definitions = state_definitions_from_internal(internal)
    groups, roots = definitions["FUD"]
    fud = run_source_state(config, molecule, overlap, basis, groups, roots)
    ground = run_ground_state(config)
    components = source_pi_sigma_components(
        molecule,
        ground,
        fud,
        list(internal["column_fragments"]),
        list(internal["column_roles"]),
    )
    return {
        "ground_converged": bool(ground["converged"]),
        "fud_converged": bool(fud["converged"]),
        "ground_energy_hartree": float(ground["energy"]),
        "fud_energy_hartree": float(
            fud["experimental_conditional_scf_energy_hartree"]
        ),
        "electron_trace": float(fud["electron_trace"]),
        "density_fixed_point_residual": float(
            fud["final_density_fixed_point_residual"]
        ),
        "group_sizes": list(fud["group_sizes"]),
        "roots": list(roots),
        "components": components,
    }


def run(master: dict[str, Any]) -> dict[str, Any]:
    base = resolve_state_config(ROOT / str(master["base_config"]))
    base["electronic_structure"]["basis"] = str(
        master["electronic_structure"]["basis"]
    )
    base["fud_state"]["density_reconstruction"] = str(
        master["source_definition"]["density_reconstruction"]
    )
    planar_scaffold = full_stage(base, return_internal=True)
    planar_internal = planar_scaffold.pop("_internal")
    planar = run_point(base, planar_internal)

    torsion = master["torsion"]
    twisted_config = deepcopy(base)
    twisted_config["geometry"]["atoms"] = rotate_about_axis(
        base["geometry"]["atoms"],
        [int(value) for value in torsion["axis_atom_indices"]],
        [int(value) for value in torsion["rotating_atom_indices"]],
        float(torsion["angle_degrees"]),
    )
    # The source constructs an LFMO basis independently at each geometry.  Do
    # not import the project's earlier planar-to-twisted continuation rule into
    # this source-definition ledger.
    twisted_scaffold = full_stage(twisted_config, return_internal=True)
    twisted_internal = twisted_scaffold.pop("_internal")
    twisted = run_point(twisted_config, twisted_internal)

    acceptance = master["acceptance"]
    expected_electrons = int(base["electronic_structure"]["expected_electrons"])
    checks = {
        "both_ground_states_converged": bool(
            planar["ground_converged"] and twisted["ground_converged"]
        ),
        "both_fud_states_converged": bool(
            planar["fud_converged"] and twisted["fud_converged"]
        ),
        "density_fixed_points": all(
            float(point["density_fixed_point_residual"])
            <= float(acceptance["density_fixed_point_tolerance"])
            for point in (planar, twisted)
        ),
        "electron_traces": all(
            abs(float(point["electron_trace"]) - expected_electrons)
            <= float(acceptance["electron_trace_tolerance"])
            for point in (planar, twisted)
        ),
        "source_cross_group_density_zero": all(
            float(point["components"]["source_cross_group_density_norm"])
            <= float(acceptance["source_cross_block_tolerance"])
            for point in (planar, twisted)
        ),
        "fock_and_overlap_cross_blocks_deleted": all(
            float(point["components"]["masked_overlap_cross_block_norm"])
            <= float(acceptance["source_cross_block_tolerance"])
            and float(
                point["components"]["masked_fock_cross_block_norm_hartree"]
            )
            <= float(acceptance["source_cross_block_tolerance"])
            for point in (planar, twisted)
        ),
        "independent_energy_assemblies": all(
            max(
                float(
                    point["components"][
                        "pyscf_vs_explicit_energy_residual_hartree"
                    ]
                ),
                float(
                    point["components"][
                        "pyscf_vs_assembled_helper_residual_hartree"
                    ]
                ),
            )
            <= float(acceptance["energy_assembly_tolerance_hartree"])
            for point in (planar, twisted)
        ),
        "equations_5_12_to_5_16_close": all(
            float(point["components"]["equation_closure_residual_hartree"])
            <= float(acceptance["equation_closure_tolerance_hartree"])
            for point in (planar, twisted)
        ),
        "sigma_response_suballocation_closes": all(
            max(
                float(
                    point["components"][
                        "sigma_response_category_closure_residual_hartree"
                    ]
                ),
                float(
                    point["components"][
                        "sigma_response_electronic_split_residual_hartree"
                    ]
                ),
            )
            <= float(acceptance["equation_closure_tolerance_hartree"])
            for point in (planar, twisted)
        ),
        "source_positive_sign_at_17_degrees": float(
            twisted["components"]["endpoint_hartree"]
        )
        > float(acceptance["positive_sign_threshold_hartree"]),
    }
    sign_reproduced = bool(checks["source_positive_sign_at_17_degrees"])
    twisted_components = twisted["components"]
    source_component_sign_checks = {
        "direct_intrafragment_negative": float(
            twisted_components["direct_intrafragment_hartree"]
        )
        < 0.0,
        "direct_interfragment_positive": float(
            twisted_components["direct_interfragment_hartree"]
        )
        > 0.0,
        "pi_response_negative": float(twisted_components["pi_response_hartree"])
        < 0.0,
        "sigma_response_negative": float(
            twisted_components["sigma_response_hartree"]
        )
        < 0.0,
    }
    source_component_pattern_reproduced = all(
        source_component_sign_checks.values()
    )
    component_pattern_required = bool(
        acceptance.get("require_source_component_sign_pattern", False)
    )
    technical_checks = {
        key: value
        for key, value in checks.items()
        if key != "source_positive_sign_at_17_degrees"
    }
    technical_pass = all(technical_checks.values())
    target_pass = bool(
        technical_pass
        and sign_reproduced
        and (
            source_component_pattern_reproduced
            or not component_pattern_required
        )
    )
    disposition = (
        "SOURCE_COMPONENT_SIGN_PATTERN_REPRODUCED_NONVARIATIONAL_QUARANTINE"
        if technical_pass and sign_reproduced and source_component_pattern_reproduced
        else (
            "SOURCE_POSITIVE_SIGN_REPRODUCED_COMPONENT_PATTERN_PENDING"
            if technical_pass and sign_reproduced
            else (
                "SOURCE_DEFINITION_TECHNICAL_PASS_SIGN_NOT_REPRODUCED"
                if technical_pass
                else "SOURCE_DEFINITION_TECHNICAL_INCOMPLETE"
            )
        )
    )
    return {
        "experiment_id": master["experiment_id"],
        "protocol": master["protocol"],
        "disposition": disposition,
        "source_positive_sign_reproduced": sign_reproduced,
        "source_component_pattern_reproduced": (
            source_component_pattern_reproduced
        ),
        "source_component_pattern_required": component_pattern_required,
        "target_pass": target_pass,
        "source_component_sign_checks": source_component_sign_checks,
        "technical_pass": technical_pass,
        "basis": str(master["electronic_structure"]["basis"]),
        "angle_degrees": float(torsion["angle_degrees"]),
        "planar": planar,
        "twisted": twisted,
        "change_from_planar_hartree": float(
            twisted["components"]["endpoint_hartree"]
            - planar["components"]["endpoint_hartree"]
        ),
        "checks": checks,
        "source": {
            "quantity": "Delta E^(pi-sigma)(theta)=E^G(theta)-E^FUD(theta)",
            "printed_pages": [138, 139, 140, 141],
            "equations": ["5-12", "5-13", "5-14", "5-15", "5-16"],
            "published_17_degree_rhf_6_31g_star_hartree": 0.00775,
            "published_17_degree_components_hartree": {
                "direct_intrafragment": -0.00010,
                "direct_interfragment": 0.06397,
                "pi_response": -0.05011,
                "sigma_response": -0.00604,
            },
            "magnitude_comparison_allowed": False,
        },
        "boundaries": master["boundaries"],
        "provenance": {
            "git_commit": git_commit(),
            "config_sha256": canonical_digest(master),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    component_boundary = (
        "All four component directions now agree with source Table 5-15: "
        "the intra-fragment direct term is negative, the inter-fragment direct "
        "term is positive, and both pi and sigma responses are negative. "
        "Magnitude equivalence is not claimed because the project geometry is "
        "idealized."
        if report["source_component_pattern_reproduced"]
        else (
            f"The current idealized {report['basis']} calculation reproduces "
            "the source signs of the intra-fragment direct term (negative), "
            "inter-fragment direct term (positive), and pi response (negative). "
            "The sigma response remains positive here but is negative in source "
            "Table 5-15. Therefore only the positive total sign, not the full "
            "source component allocation, is reproduced."
        )
    )
    lines = [
        "# Gate 0 source-nonvariational NBA pi-sigma sign replication",
        "",
        f"- Disposition: **{report['disposition']}**",
        f"- Technical checks pass: `{report['technical_pass']}`",
        f"- Declared source target pass: `{report['target_pass']}`",
        f"- Positive source sign reproduced: `{report['source_positive_sign_reproduced']}`",
        f"- Source component sign pattern reproduced: `{report['source_component_pattern_reproduced']}`",
        f"- Basis: `{report['basis']}`",
        "- Ledger: `source_nonvariational_definition`",
        "",
        "| Angle | E_G (Eh) | E_FUD (Eh) | E_G-E_FUD (Eh) | kcal/mol | Equation closure (Eh) |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for angle, key in ((0.0, "planar"), (report["angle_degrees"], "twisted")):
        point = report[key]
        component = point["components"]
        lines.append(
            f"| {angle:.1f} | {point['ground_energy_hartree']:.12f} | "
            f"{point['fud_energy_hartree']:.12f} | "
            f"{component['endpoint_hartree']:.12f} | "
            f"{component['endpoint_kcal_mol']:.6f} | "
            f"{component['equation_closure_residual_hartree']:.3e} |"
        )
    twisted = report["twisted"]["components"]
    lines.extend(
        [
            "",
            "## 17-degree component decomposition",
            "",
            "| Component | Eh | kcal/mol |",
            "|---|---:|---:|",
            f"| Direct pi-sigma | {twisted['direct_total_hartree']:.12f} | {twisted['direct_total_hartree'] * HARTREE_TO_KCAL_MOL:.6f} |",
            f"| Pi response | {twisted['pi_response_hartree']:.12f} | {twisted['pi_response_hartree'] * HARTREE_TO_KCAL_MOL:.6f} |",
            f"| Sigma response | {twisted['sigma_response_hartree']:.12f} | {twisted['sigma_response_hartree'] * HARTREE_TO_KCAL_MOL:.6f} |",
            f"| Sum | {twisted['component_sum_hartree']:.12f} | {twisted['component_sum_hartree'] * HARTREE_TO_KCAL_MOL:.6f} |",
            "",
            "## Sigma-response localization",
            "",
            f"- One-electron sigma response: `{twisted['sigma_response_one_electron_hartree'] * HARTREE_TO_KCAL_MOL:.6f} kcal/mol`.",
            f"- Two-electron sigma response: `{twisted['sigma_response_two_electron_hartree'] * HARTREE_TO_KCAL_MOL:.6f} kcal/mol`.",
            f"- Bonded/bonded contribution: `{twisted['sigma_response_by_role_pair_hartree'].get('bonded__bonded', 0.0) * HARTREE_TO_KCAL_MOL:.6f} kcal/mol`.",
            f"- Bonded/cut contribution: `{twisted['sigma_response_by_role_pair_hartree'].get('bonded__cut', 0.0) * HARTREE_TO_KCAL_MOL:.6f} kcal/mol`.",
            f"- Cut/cut contribution: `{twisted['sigma_response_by_role_pair_hartree'].get('cut__cut', 0.0) * HARTREE_TO_KCAL_MOL:.6f} kcal/mol`.",
            "",
            "## Component-pattern boundary",
            "",
            component_boundary,
            "",
            "## Boundary",
            "",
            "This is an explicitly nonvariational source-definition result. It is not mixed with the physical response ledger, is not a source-equivalent magnitude claim, and is not a production or AI-training label.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    report = run(load_yaml(args.config))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(json_safe(report), indent=2, sort_keys=True), encoding="utf-8"
    )
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(
        f"{report['disposition']}: sign={report['source_positive_sign_reproduced']}, "
        f"E_G-E_FUD={report['twisted']['components']['endpoint_hartree']:.12f} Eh"
    )
    return 0 if report["target_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
