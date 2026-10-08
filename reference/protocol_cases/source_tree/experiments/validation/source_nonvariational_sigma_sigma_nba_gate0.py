"""Replicate the source-defined parent-NBA PDSI/FUL sigma-sigma direction."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import numpy as np

from ai4orgchem.lfmo.conditional_scf import grouped_generalized_eigh
from ai4orgchem.lfmo.state_masks import block_mask
from experiments.validation.chapter5_pi_sigma_reconstruction_gate0 import (
    HARTREE_TO_KCAL_MOL,
    canonical_digest,
    density_in_working_basis,
)
from experiments.validation.chapter5_three_effect_reconstruction_gate0 import (
    assembled_energy,
    maximum_cross_group_density,
    run_source_state,
)
from experiments.validation.dsi2_divinyl_imine_source_shaped_gate0 import (
    build_source_fragment,
)
from experiments.validation.dsi2_divinyl_imine_torsion_continuation_gate0 import (
    rotate_about_axis,
)
from experiments.validation.dsi_fud_initial_density_reproducibility_gate0 import (
    resolve_state_config,
)
from experiments.validation.dsi_lfmo_n_state_specific_reconstruction_gate0 import (
    build_fragment_states_generic,
)
from experiments.validation.one_cut_ch3_reference_h_gate0 import (
    ao_indices_for_atoms,
)
from experiments.validation.one_cut_conditional_scf_gate0 import (
    ROOT,
    git_commit,
    json_safe,
    load_yaml,
)
from experiments.validation.two_cut_ch2_four_column_gate0 import canonical_geometry


DEFAULT_CONFIG = (
    ROOT / "configs" / "qm" / "source_nonvariational_sigma_sigma_nba_v0.1.yaml"
)
DEFAULT_OUTPUT = (
    ROOT
    / "artifacts"
    / "raw"
    / "source_nonvariational_sigma_sigma_nba_2026-08-14.json"
)
DEFAULT_MARKDOWN = (
    ROOT
    / "docs"
    / "reports"
    / "gate0_source_nonvariational_sigma_sigma_nba_2026-08-14.md"
)


def maximum_deleted_block_norm(
    matrix: np.ndarray, group_sizes: list[int]
) -> float:
    cross_mask = 1.0 - block_mask(group_sizes)
    return float(np.linalg.norm(np.asarray(matrix, dtype=float) * cross_mask, ord="fro"))


def state_diagnostics(
    molecule: Any,
    overlap: np.ndarray,
    state: dict[str, Any],
    roots: list[int],
    labels: list[str],
) -> dict[str, Any]:
    from pyscf import scf

    density = np.asarray(state["_final_density"], dtype=float)
    basis = np.asarray(state["working_basis"], dtype=float)
    group_sizes = [int(value) for value in state["group_sizes"]]
    mean_field = scf.RHF(molecule)
    mean_field.verbose = 0
    hcore = np.asarray(mean_field.get_hcore(), dtype=float)
    fock_ao = hcore + np.asarray(mean_field.get_veff(molecule, density), dtype=float)
    metric = basis.T @ overlap @ basis
    fock = basis.T @ fock_ao @ basis
    grouped = grouped_generalized_eigh(fock, metric, group_sizes)
    offsets = np.cumsum([0, *group_sizes])
    spectra = {
        label: grouped["energies"][offsets[index] : offsets[index + 1]].tolist()
        for index, label in enumerate(labels)
    }
    cut_label = "cut_sigma_all"
    cut_index = labels.index(cut_label)
    cut_energies = spectra[cut_label]
    cut_roots = int(roots[cut_index])
    _, density_reconstruction = density_in_working_basis(basis, density)
    source_energy = float(state["experimental_conditional_scf_energy_hartree"])
    return {
        "converged": bool(state["converged"]),
        "cycles": int(state["cycles"]),
        "energy_hartree": source_energy,
        "assembled_energy_hartree": assembled_energy(molecule, density),
        "energy_assembly_residual_hartree": abs(
            assembled_energy(molecule, density) - source_energy
        ),
        "electron_trace": float(state["electron_trace"]),
        "density_fixed_point_residual": float(
            state["final_density_fixed_point_residual"]
        ),
        "physical_metric_idempotency_residual": float(
            state["density_physical_metric_idempotency_residual"]
        ),
        "density_reconstruction_residual": float(density_reconstruction),
        "maximum_source_cross_group_density_norm": maximum_cross_group_density(state),
        "deleted_overlap_block_norm_before_mask": maximum_deleted_block_norm(
            metric, group_sizes
        ),
        "deleted_fock_block_norm_before_mask_hartree": maximum_deleted_block_norm(
            fock, group_sizes
        ),
        "masked_overlap_cross_block_norm": maximum_deleted_block_norm(
            np.asarray(grouped["masked_metric"], dtype=float), group_sizes
        ),
        "masked_fock_cross_block_norm_hartree": maximum_deleted_block_norm(
            np.asarray(grouped["masked_fock"], dtype=float), group_sizes
        ),
        "group_sizes": group_sizes,
        "occupied_roots": [int(value) for value in roots],
        "group_labels": labels,
        "group_orbital_energies_hartree": spectra,
        "cut_sigma_group_size": len(cut_energies),
        "cut_sigma_occupied_roots": cut_roots,
        "cut_sigma_occupied_orbital_energies_hartree": cut_energies[:cut_roots],
        "cut_sigma_vacant_orbital_energies_hartree": cut_energies[cut_roots:],
    }


def source_partitions_close(definitions: dict[str, tuple[list[list[int]], list[int]]]) -> bool:
    ful_groups, ful_roots = definitions["FUL"]
    pdsi_groups, pdsi_roots = definitions["PDSI"]
    return bool(
        len(ful_groups) == 5
        and len(pdsi_groups) == 4
        and ful_groups[:2] == pdsi_groups[:2]
        and [index for group in ful_groups[2:4] for index in group]
        == pdsi_groups[2]
        and ful_groups[4] == pdsi_groups[3]
        and ful_roots[:2] == pdsi_roots[:2]
        and sum(ful_roots[2:4]) == pdsi_roots[2]
        and ful_roots[4] == pdsi_roots[3]
    )


def build_ful2_internal(
    config: dict[str, Any],
    source_type_references: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Construct the source FUL-2 (2F-2S) LFMO basis for fragments A and B+C."""

    from pyscf import gto

    fragment_order = ("A", "P")
    fragment_states = build_fragment_states_generic(config)
    source_type_references = source_type_references or {}
    source_fragments: dict[str, dict[str, Any]] = {}
    for fragment_id in fragment_order:
        try:
            source_fragments[fragment_id] = build_source_fragment(
                config,
                fragment_id,
                fragment_states[fragment_id],
                type_reference=source_type_references.get(fragment_id),
            )
        except RuntimeError as exc:
            raise RuntimeError(f"fragment {fragment_id}: {exc}") from exc
    electronic = config["electronic_structure"]
    parent = gto.M(
        atom=canonical_geometry(config["geometry"]["atoms"]),
        basis=str(electronic["basis"]),
        charge=int(electronic["charge"]),
        spin=int(electronic["spin"]),
        unit="Angstrom",
        symmetry=False,
        verbose=0,
    )
    overlap = parent.intor_symmetric("int1e_ovlp")
    embedded: dict[str, np.ndarray] = {}
    for fragment_id in fragment_order:
        atom_indices = [
            int(value)
            for value in config["primitive_fragments"][fragment_id]["atom_indices"]
        ]
        rows = ao_indices_for_atoms(parent, atom_indices)
        local = np.asarray(source_fragments[fragment_id]["coefficients"], dtype=float)
        block = np.zeros((parent.nao_nr(), local.shape[1]))
        block[np.ix_(rows, range(local.shape[1]))] = local
        embedded[fragment_id] = block

    pi_parts: list[np.ndarray] = []
    sigma_parts: list[np.ndarray] = []
    column_types: list[str] = []
    column_fragments: list[str] = []
    column_roles: list[str] = []
    for orbital_type, destination in (("pi", pi_parts), ("sigma", sigma_parts)):
        for fragment_id in fragment_order:
            indices = [
                index
                for index, value in enumerate(source_fragments[fragment_id]["types"])
                if value == orbital_type
            ]
            destination.append(embedded[fragment_id][:, indices])
            column_types.extend([orbital_type] * len(indices))
            column_fragments.extend([fragment_id] * len(indices))
            column_roles.extend(
                source_fragments[fragment_id]["roles"][index] for index in indices
            )
    working_basis = np.column_stack((*pi_parts, *sigma_parts))
    if working_basis.shape != (parent.nao_nr(), parent.nao_nr()):
        raise RuntimeError("FUL-2 LFMO basis must be square")
    if int(np.linalg.matrix_rank(working_basis)) != parent.nao_nr():
        raise RuntimeError("FUL-2 LFMO basis must be full rank")
    return {
        "molecule": parent,
        "overlap": overlap,
        "working_basis": working_basis,
        "column_types": column_types,
        "column_fragments": column_fragments,
        "column_roles": column_roles,
        "bonded_sigma_occupied_roots_by_fragment": {
            fragment_id: int(
                source_fragments[fragment_id]["bonded_sigma_occupied_roots"]
            )
            for fragment_id in fragment_order
        },
        "bonded_pi_occupied_roots_by_fragment": {
            fragment_id: int(
                source_fragments[fragment_id]["bonded_pi_occupied_roots"]
            )
            for fragment_id in fragment_order
        },
        "cut_single_count_by_fragment": {
            fragment_id: int(source_fragments[fragment_id]["cut_single_count"])
            for fragment_id in fragment_order
        },
        "fragment_checks": {
            fragment_id: {
                "uhf_converged": bool(fragment_states[fragment_id]["converged"]),
                "cut_somo_count_matches": len(
                    fragment_states[fragment_id]["candidate_indices"]
                )
                == int(
                    config["primitive_fragments"][fragment_id]["expected_cut_somos"]
                ),
                "conditional_scf_converged": bool(
                    source_fragments[fragment_id]["conditional_converged"]
                ),
                "no_mixed_orbitals": int(
                    source_fragments[fragment_id]["mixed_count"]
                )
                == 0,
                "reflection_residual_within_tolerance": float(
                    source_fragments[fragment_id]["maximum_reflection_residual"]
                )
                <= float(
                    config["acceptance"].get(
                        "maximum_accepted_reflection_residual",
                        config["acceptance"].get(
                            "reflection_block_closure_tolerance", 1.0e-8
                        ),
                    )
                ),
            }
            for fragment_id in fragment_order
        },
        "fragment_reflection_residuals": {
            fragment_id: float(
                source_fragments[fragment_id]["maximum_reflection_residual"]
            )
            for fragment_id in fragment_order
        },
        "fragment_type_tracking_minimum_singular_values": {
            fragment_id: float(
                source_fragments[fragment_id]["type_tracking_minimum_singular_value"]
            )
            for fragment_id in fragment_order
        },
        "fragment_mixed_counts": {
            fragment_id: int(source_fragments[fragment_id]["mixed_count"])
            for fragment_id in fragment_order
        },
        "source_type_references": {
            fragment_id: source_fragments[fragment_id]["_type_reference"]
            for fragment_id in fragment_order
        },
    }


def state_definitions_from_ful2(
    internal: dict[str, Any],
) -> dict[str, tuple[list[list[int]], list[int]]]:
    types = list(internal["column_types"])
    fragments = list(internal["column_fragments"])
    roles = list(internal["column_roles"])

    def select(kind: str, owner: str | None = None, role: str | None = None) -> list[int]:
        return [
            index
            for index, (value, fragment, column_role) in enumerate(
                zip(types, fragments, roles, strict=True)
            )
            if value == kind
            and (owner is None or fragment == owner)
            and (role is None or column_role == role)
        ]

    pi = {fragment: select("pi", fragment) for fragment in ("A", "P")}
    bonded_sigma = {
        fragment: select("sigma", fragment, "bonded") for fragment in ("A", "P")
    }
    cut = select("sigma", role="cut_single")
    pi_roots = internal["bonded_pi_occupied_roots_by_fragment"]
    sigma_roots = internal["bonded_sigma_occupied_roots_by_fragment"]
    cut_roots = sum(internal["cut_single_count_by_fragment"].values()) // 2
    return {
        "FUL": (
            [pi["A"], pi["P"], bonded_sigma["A"], bonded_sigma["P"], cut],
            [
                int(pi_roots["A"]),
                int(pi_roots["P"]),
                int(sigma_roots["A"]),
                int(sigma_roots["P"]),
                int(cut_roots),
            ],
        ),
        "PDSI": (
            [
                pi["A"],
                pi["P"],
                [*bonded_sigma["A"], *bonded_sigma["P"]],
                cut,
            ],
            [
                int(pi_roots["A"]),
                int(pi_roots["P"]),
                int(sigma_roots["A"] + sigma_roots["P"]),
                int(cut_roots),
            ],
        ),
    }


def run_point(config: dict[str, Any], internal: dict[str, Any]) -> dict[str, Any]:
    molecule = internal["molecule"]
    overlap = np.asarray(internal["overlap"], dtype=float)
    basis = np.asarray(internal["working_basis"], dtype=float)
    definitions = state_definitions_from_ful2(internal)
    labels = {
        "FUL": [
            "pi_A",
            "pi_B_plus_C",
            "bonded_sigma_A",
            "bonded_sigma_B_plus_C",
            "cut_sigma_all",
        ],
        "PDSI": [
            "pi_A",
            "pi_B_plus_C",
            "bonded_sigma_all",
            "cut_sigma_all",
        ],
    }
    states: dict[str, dict[str, Any]] = {}
    diagnostics: dict[str, dict[str, Any]] = {}
    for name in ("FUL", "PDSI"):
        groups, roots = definitions[name]
        states[name] = run_source_state(
            config,
            molecule,
            overlap,
            basis,
            groups,
            roots,
            density_reconstruction="source_block_metric_group_projector",
        )
        diagnostics[name] = state_diagnostics(
            molecule, overlap, states[name], roots, labels[name]
        )
    endpoint = diagnostics["PDSI"]["energy_hartree"] - diagnostics["FUL"][
        "energy_hartree"
    ]
    assembled_endpoint = diagnostics["PDSI"][
        "assembled_energy_hartree"
    ] - diagnostics["FUL"]["assembled_energy_hartree"]
    return {
        "states": diagnostics,
        "endpoint_expression": "E_PDSI-E_FUL",
        "endpoint_hartree": endpoint,
        "endpoint_kcal_mol": endpoint * HARTREE_TO_KCAL_MOL,
        "assembled_endpoint_hartree": assembled_endpoint,
        "endpoint_assembly_closure_residual_hartree": abs(
            endpoint - assembled_endpoint
        ),
        "source_partition_contract_closes": source_partitions_close(definitions),
        "source_fragment_contracts_close": all(
            all(checks.values()) for checks in internal["fragment_checks"].values()
        ),
        "fragment_checks": internal["fragment_checks"],
        "fragment_reflection_residuals": internal["fragment_reflection_residuals"],
        "shared_lfmo_basis_within_geometry": bool(
            states["FUL"]["order"] == states["PDSI"]["order"]
            and np.array_equal(
                states["FUL"]["working_basis"], states["PDSI"]["working_basis"]
            )
        ),
    }


def run(master: dict[str, Any]) -> dict[str, Any]:
    base = resolve_state_config(ROOT / str(master["base_config"]))
    base["electronic_structure"]["basis"] = str(
        master["electronic_structure"]["basis"]
    )
    base["fud_state"]["density_reconstruction"] = str(
        master["source_definition"]["density_reconstruction"]
    )
    base["primitive_fragments"] = deepcopy(master["source_definition"]["fragments"])

    planar_internal = build_ful2_internal(base)
    planar = run_point(base, planar_internal)

    torsion = master["torsion"]
    twisted_config = deepcopy(base)
    twisted_config["geometry"]["atoms"] = rotate_about_axis(
        base["geometry"]["atoms"],
        [int(value) for value in torsion["axis_atom_indices"]],
        [int(value) for value in torsion["rotating_atom_indices"]],
        float(torsion["angle_degrees"]),
    )
    twisted_internal = build_ful2_internal(twisted_config)
    twisted = run_point(twisted_config, twisted_internal)

    acceptance = master["acceptance"]
    expected_electrons = int(base["electronic_structure"]["expected_electrons"])
    points = (planar, twisted)
    state_rows = [point["states"][state] for point in points for state in ("FUL", "PDSI")]
    ful_rows = [point["states"]["FUL"] for point in points]
    technical_checks = {
        "all_states_converged": all(row["converged"] for row in state_rows),
        "density_fixed_points": all(
            row["density_fixed_point_residual"]
            <= float(acceptance["density_fixed_point_tolerance"])
            for row in state_rows
        ),
        "electron_traces": all(
            abs(row["electron_trace"] - expected_electrons)
            <= float(acceptance["electron_trace_tolerance"])
            for row in state_rows
        ),
        "source_cross_group_density_zero": all(
            row["maximum_source_cross_group_density_norm"]
            <= float(acceptance["source_cross_block_tolerance"])
            for row in state_rows
        ),
        "fock_and_overlap_cross_blocks_deleted": all(
            max(
                row["masked_overlap_cross_block_norm"],
                row["masked_fock_cross_block_norm_hartree"],
            )
            <= float(acceptance["source_cross_block_tolerance"])
            for row in state_rows
        ),
        "state_and_endpoint_energy_assemblies": all(
            row["energy_assembly_residual_hartree"]
            <= float(acceptance["energy_assembly_tolerance_hartree"])
            for row in state_rows
        )
        and all(
            point["endpoint_assembly_closure_residual_hartree"]
            <= float(acceptance["energy_assembly_tolerance_hartree"])
            for point in points
        ),
        "source_partition_contracts": all(
            point["source_partition_contract_closes"] for point in points
        ),
        "source_fragment_contracts": all(
            point["source_fragment_contracts_close"] for point in points
        ),
        "shared_lfmo_basis_within_each_geometry": all(
            point["shared_lfmo_basis_within_geometry"] for point in points
        ),
        "ful_cut_sigma_occupation_matches_ful2_2f_2s": all(
            row["cut_sigma_group_size"]
            == int(master["source_definition"]["cut_sigma_group_size"])
            and row["cut_sigma_occupied_roots"]
            == int(master["source_definition"]["cut_sigma_occupied_roots"])
            for row in ful_rows
        ),
        "ful_cut_sigma_vacant_orbitals_positive": all(
            row["cut_sigma_vacant_orbital_energies_hartree"]
            and min(row["cut_sigma_vacant_orbital_energies_hartree"])
            > float(acceptance["ful_vacant_cut_orbital_energy_floor_hartree"])
            for row in ful_rows
        ),
    }
    source_direction_checks = {
        "positive_at_zero_degrees": planar["endpoint_hartree"]
        > float(acceptance["positive_sign_threshold_hartree"]),
        "positive_at_seventeen_degrees": twisted["endpoint_hartree"]
        > float(acceptance["positive_sign_threshold_hartree"]),
        "decreases_from_zero_to_seventeen": twisted["endpoint_hartree"]
        < planar["endpoint_hartree"],
    }
    technical_pass = all(technical_checks.values())
    source_direction_reproduced = all(source_direction_checks.values())
    target_pass = bool(technical_pass and source_direction_reproduced)
    disposition = (
        "SOURCE_SIGMA_SIGMA_DIRECTION_REPRODUCED_NONVARIATIONAL_QUARANTINE"
        if target_pass
        else (
            "SOURCE_SIGMA_SIGMA_TECHNICAL_PASS_DIRECTION_PENDING"
            if technical_pass
            else "SOURCE_SIGMA_SIGMA_TECHNICAL_INCOMPLETE"
        )
    )
    return {
        "experiment_id": master["experiment_id"],
        "protocol": master["protocol"],
        "disposition": disposition,
        "technical_pass": technical_pass,
        "source_direction_reproduced": source_direction_reproduced,
        "target_pass": target_pass,
        "basis": str(master["electronic_structure"]["basis"]),
        "angle_degrees": float(torsion["angle_degrees"]),
        "planar": planar,
        "twisted": twisted,
        "change_from_planar_hartree": twisted["endpoint_hartree"]
        - planar["endpoint_hartree"],
        "technical_checks": technical_checks,
        "source_direction_checks": source_direction_checks,
        "source": {
            "quantity": "Delta E^(sigma-sigma)(theta)=E_PDSI(theta)-E_FUL(theta)",
            "source_variant": "FUL-2/2F-2S",
            "printed_pages": [144, 145, 146, 147, 148, 149, 150, 151],
            "figure": "5-11",
            "scheme": "5-5",
            "table": "5-19",
            "published_parent_nba_hartree": {"0.0": 0.06891, "17.0": 0.06504},
            "magnitude_comparison_allowed": False,
        },
        "boundaries": master["boundaries"],
        "provenance": {
            "git_commit": git_commit(),
            "config_sha256": canonical_digest(master),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    state_rows = [
        report[point]["states"][state]
        for point in ("planar", "twisted")
        for state in ("FUL", "PDSI")
    ]
    maximum_idempotency = max(
        row["physical_metric_idempotency_residual"] for row in state_rows
    )
    maximum_assembly = max(
        row["energy_assembly_residual_hartree"] for row in state_rows
    )
    lines = [
        "# Gate 0 source-nonvariational NBA PDSI/FUL sigma-sigma validation",
        "",
        f"- Disposition: **{report['disposition']}**",
        f"- Technical checks pass: `{report['technical_pass']}`",
        f"- Source direction reproduced: `{report['source_direction_reproduced']}`",
        f"- Declared source target pass: `{report['target_pass']}`",
        f"- Basis: `{report['basis']}`",
        "- Ledger: `source_nonvariational_definition`",
        "",
        "| Angle | E_FUL (Eh) | E_PDSI (Eh) | E_PDSI-E_FUL (Eh) | kcal/mol | Source Table 5-19 (Eh) |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    published = report["source"]["published_parent_nba_hartree"]
    for angle, key in ((0.0, "planar"), (report["angle_degrees"], "twisted")):
        point = report[key]
        lines.append(
            f"| {angle:.1f} | {point['states']['FUL']['energy_hartree']:.12f} | "
            f"{point['states']['PDSI']['energy_hartree']:.12f} | "
            f"{point['endpoint_hartree']:.12f} | "
            f"{point['endpoint_kcal_mol']:.6f} | {published[f'{angle:.1f}']:.5f} |"
        )
    lines.extend(
        [
            "",
            "## Source-state contract",
            "",
            "- Source variant: `FUL-2 / 2F-2S`, matching Table 5-19.",
            "- FUL groups: `pi_A | pi_(B+C) | bonded_sigma_A | bonded_sigma_(B+C) | cut_sigma_all`.",
            "- PDSI groups: `pi_A | pi_(B+C) | bonded_sigma_all | cut_sigma_all`.",
            "- The only FUL-to-PDSI release is merging bonded-sigma A and B+C; pi groups and the two-column cut-sigma block are unchanged.",
            "- FUL cut-sigma occupation is one occupied root in two orbitals at both geometries.",
            f"- Minimum FUL vacant cut-sigma orbital energy at 0 degrees: `{min(report['planar']['states']['FUL']['cut_sigma_vacant_orbital_energies_hartree']):.8f} Eh`.",
            f"- Minimum FUL vacant cut-sigma orbital energy at 17 degrees: `{min(report['twisted']['states']['FUL']['cut_sigma_vacant_orbital_energies_hartree']):.8f} Eh`.",
            f"- Maximum state-energy assembly residual: `{maximum_assembly:.3e} Eh`.",
            f"- Maximum physical-metric idempotency residual of the source densities: `{maximum_idempotency:.3e}`.",
            "",
            "## Magnitude boundary",
            "",
            f"- Difference from source Table 5-19 at 0 degrees: `{report['planar']['endpoint_hartree'] - report['source']['published_parent_nba_hartree']['0.0']:+.8f} Eh`.",
            f"- Difference from source Table 5-19 at 17 degrees: `{report['twisted']['endpoint_hartree'] - report['source']['published_parent_nba_hartree']['17.0']:+.8f} Eh`.",
            "- These differences are reported diagnostically only; the project uses an idealized geometry rather than the source optimized geometry series.",
            "",
            "## Boundary",
            "",
            "This validates only the source-defined PDSI/FUL sigma-sigma direction on the existing idealized parent NBA at two fixed points. The nonvariational source ledger remains isolated; the physical response ledger is unchanged; magnitude equivalence, cross-basis total reconstruction, production labels, AI-training labels, molecule expansion, and scans remain disabled.",
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
        f"{report['disposition']}: "
        f"E_PDSI-E_FUL(0)={report['planar']['endpoint_hartree']:.12f} Eh, "
        f"E_PDSI-E_FUL(17)={report['twisted']['endpoint_hartree']:.12f} Eh"
    )
    return 0 if report["target_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
