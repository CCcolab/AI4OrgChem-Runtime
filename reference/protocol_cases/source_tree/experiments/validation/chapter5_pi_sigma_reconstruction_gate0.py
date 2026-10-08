"""Validate Chapter 5 equations 5-12 to 5-16 at one nonplanar geometry."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from ai4orgchem.lfmo.conditional_scf import (
    grouped_nonorthogonal_closed_shell_density,
)
from experiments.validation.dsi2_divinyl_imine_source_shaped_gate0 import (
    full_stage,
    run_projector_fixed_point_scf,
)
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
from experiments.validation.two_cut_ch2_four_column_gate0 import canonical_geometry


DEFAULT_CONFIG = ROOT / "configs" / "qm" / "chapter5_pi_sigma_reconstruction_v0.1.yaml"
DEFAULT_OUTPUT = ROOT / "artifacts" / "raw" / "chapter5_pi_sigma_reconstruction_2026-08-14.json"
DEFAULT_MARKDOWN = ROOT / "docs" / "reports" / "gate0_chapter5_pi_sigma_reconstruction_2026-08-14.md"
HARTREE_TO_KCAL_MOL = 627.5094740631


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def run_ground_state(config: dict[str, Any]) -> dict[str, Any]:
    from pyscf import gto, scf

    electronic = config["electronic_structure"]
    molecule = gto.M(
        atom=canonical_geometry(config["geometry"]["atoms"]),
        basis=str(electronic["basis"]),
        charge=int(electronic["charge"]),
        spin=int(electronic["spin"]),
        unit="Angstrom",
        symmetry=False,
        verbose=0,
    )
    mean_field = scf.RHF(molecule)
    mean_field.conv_tol = float(config["conditional_scf"]["convergence_tolerance"])
    mean_field.max_cycle = int(config["conditional_scf"]["max_cycles"])
    mean_field.init_guess = str(config["conditional_scf"]["initial_guess"])
    mean_field.verbose = 0
    energy = float(mean_field.kernel())
    density = np.asarray(mean_field.make_rdm1(), dtype=float)
    hcore = np.asarray(mean_field.get_hcore(), dtype=float)
    fock = hcore + np.asarray(mean_field.get_veff(molecule, density), dtype=float)
    return {
        "molecule": molecule,
        "mean_field": mean_field,
        "density": density,
        "hcore": hcore,
        "fock": fock,
        "energy": energy,
        "converged": bool(mean_field.converged),
    }


def density_in_working_basis(
    working_basis: np.ndarray, density_ao: np.ndarray
) -> tuple[np.ndarray, float]:
    inverse = np.linalg.inv(working_basis)
    density_lfmo = inverse @ density_ao @ inverse.T
    reconstructed = working_basis @ density_lfmo @ working_basis.T
    residual = float(
        np.linalg.norm(reconstructed - density_ao, ord="fro")
        / max(float(np.linalg.norm(density_ao, ord="fro")), 1.0)
    )
    return density_lfmo, residual


def block_energy(
    hcore: np.ndarray,
    fock: np.ndarray,
    density: np.ndarray,
    rows: list[int],
    columns: list[int],
    factor: float,
) -> float:
    matrix = hcore + fock
    return float(
        factor
        * np.einsum(
            "ij,ji->",
            matrix[np.ix_(rows, columns)],
            density[np.ix_(columns, rows)],
        )
    )


def run(master: dict[str, Any]) -> dict[str, Any]:
    fud_config = resolve_state_config(ROOT / str(master["fud_config"]))
    planar = full_stage(fud_config, return_internal=True)
    planar_internal = planar.pop("_internal")
    torsion = master["torsion"]
    twisted_config = deepcopy(fud_config)
    twisted_config["experiment_id"] = f"{master['experiment_id']}/fud"
    twisted_config["geometry"]["atoms"] = rotate_about_axis(
        fud_config["geometry"]["atoms"],
        [int(value) for value in torsion["axis_atom_indices"]],
        [int(value) for value in torsion["rotating_atom_indices"]],
        float(torsion["angle_degrees"]),
    )
    fud = full_stage(
        twisted_config,
        return_internal=True,
        source_type_references=planar_internal["source_type_references"],
        occupied_root_reference=planar_internal,
    )
    fud_internal = fud.pop("_internal")
    ground = run_ground_state(twisted_config)
    molecule = fud_internal["molecule"]
    overlap = np.asarray(fud_internal["overlap"], dtype=float)
    working_basis = np.asarray(fud_internal["working_basis"], dtype=float)
    group_sizes = [int(value) for value in fud_internal["group_sizes"]]
    roots = [int(value) for value in fud_internal["roots"]]
    physical_coefficients = np.asarray(fud_internal["coefficients"], dtype=float)
    offsets = np.cumsum([0, *group_sizes])
    root_reference_occupied = [
        physical_coefficients[:, offsets[group] : offsets[group] + count]
        for group, count in enumerate(roots)
    ]
    source_config = deepcopy(twisted_config)
    source_config["fud_state"]["density_reconstruction"] = (
        "source_block_metric_group_projector"
    )
    source_initial_density = grouped_nonorthogonal_closed_shell_density(
        physical_coefficients, overlap, group_sizes, roots
    )
    source_fud = run_projector_fixed_point_scf(
        source_config,
        {
            "spaces": {"composite": molecule, "overlap": overlap},
            "working_basis": working_basis,
            "group_sizes": group_sizes,
            "initial_density": source_initial_density,
            "root_reference_occupied": root_reference_occupied,
            "root_reference_overlap": overlap,
        },
        roots,
    )
    types = list(fud_internal["column_types"])
    fragments = list(fud_internal["column_fragments"])
    if len(types) != working_basis.shape[1] or len(fragments) != working_basis.shape[1]:
        raise ValueError("LFMO column metadata is incomplete")

    hcore_ao = np.asarray(ground["hcore"], dtype=float)
    ground_fock_ao = np.asarray(ground["fock"], dtype=float)
    fud_density_ao = np.asarray(source_fud["_final_density"], dtype=float)
    fud_mean_field = ground["mean_field"].__class__(molecule)
    fud_mean_field.verbose = 0
    fud_fock_ao = hcore_ao + np.asarray(
        fud_mean_field.get_veff(molecule, fud_density_ao), dtype=float
    )
    hcore = working_basis.T @ hcore_ao @ working_basis
    ground_fock = working_basis.T @ ground_fock_ao @ working_basis
    fud_fock = working_basis.T @ fud_fock_ao @ working_basis
    ground_density, ground_density_residual = density_in_working_basis(
        working_basis, ground["density"]
    )
    fud_density, fud_density_residual = density_in_working_basis(
        working_basis, fud_density_ao
    )

    pi_indices = [index for index, value in enumerate(types) if value == "pi"]
    sigma_indices = [index for index, value in enumerate(types) if value == "sigma"]
    fragment_ids = sorted(set(fragments))
    direct_terms: dict[str, dict[str, float]] = {}
    for pi_fragment in fragment_ids:
        direct_terms[pi_fragment] = {}
        pi_fragment_indices = [
            index
            for index in pi_indices
            if fragments[index] == pi_fragment
        ]
        for sigma_fragment in fragment_ids:
            sigma_fragment_indices = [
                index
                for index in sigma_indices
                if fragments[index] == sigma_fragment
            ]
            direct_terms[pi_fragment][sigma_fragment] = block_energy(
                hcore,
                ground_fock,
                ground_density,
                pi_fragment_indices,
                sigma_fragment_indices,
                1.0,
            )
    direct_intra = sum(
        direct_terms[fragment][fragment] for fragment in fragment_ids
    )
    direct_inter = sum(
        direct_terms[pi_fragment][sigma_fragment]
        for pi_fragment in fragment_ids
        for sigma_fragment in fragment_ids
        if pi_fragment != sigma_fragment
    )
    delta_pi = block_energy(
        hcore, ground_fock, ground_density, pi_indices, pi_indices, 0.5
    ) - block_energy(hcore, fud_fock, fud_density, pi_indices, pi_indices, 0.5)
    delta_sigma = block_energy(
        hcore, ground_fock, ground_density, sigma_indices, sigma_indices, 0.5
    ) - block_energy(
        hcore, fud_fock, fud_density, sigma_indices, sigma_indices, 0.5
    )
    component_sum = direct_intra + direct_inter + delta_pi + delta_sigma
    source_fud_energy = float(source_fud["experimental_conditional_scf_energy_hartree"])
    endpoint = float(ground["energy"] - source_fud_energy)
    closure_residual = abs(component_sum - endpoint)
    fud_cross_density = float(
        np.linalg.norm(fud_density[np.ix_(pi_indices, sigma_indices)], ord="fro")
    )
    ground_energy_assembled = 0.5 * float(
        np.einsum("ij,ji->", hcore_ao + ground_fock_ao, ground["density"])
    ) + float(molecule.energy_nuc())
    fud_energy_assembled = 0.5 * float(
        np.einsum("ij,ji->", hcore_ao + fud_fock_ao, fud_density_ao)
    ) + float(molecule.energy_nuc())
    acceptance = master["acceptance"]
    checks = {
        "planar_reference_pass": planar["disposition"] == "PASS",
        "twisted_fud_pass": fud["disposition"] == "PASS",
        "source_block_fud_scf_converged": bool(source_fud["converged"]),
        "source_block_fud_electron_trace": abs(
            float(source_fud["electron_trace"])
            - int(twisted_config["electronic_structure"]["expected_electrons"])
        ) <= float(twisted_config["acceptance"]["electron_trace_tolerance"]),
        "ground_scf_converged": bool(ground["converged"]),
        "working_basis_square_full_rank": working_basis.shape[0]
        == working_basis.shape[1]
        == np.linalg.matrix_rank(working_basis),
        "ground_density_basis_reconstruction": ground_density_residual
        <= float(acceptance["density_basis_reconstruction_tolerance"]),
        "fud_density_basis_reconstruction": fud_density_residual
        <= float(acceptance["density_basis_reconstruction_tolerance"]),
        "fud_pi_sigma_density_zero": fud_cross_density
        <= float(acceptance["constrained_pi_sigma_density_tolerance"]),
        "ground_energy_assembly": abs(ground_energy_assembled - ground["energy"])
        <= float(acceptance["energy_assembly_tolerance_hartree"]),
        "fud_energy_assembly": abs(
            fud_energy_assembled - source_fud_energy
        )
        <= float(acceptance["energy_assembly_tolerance_hartree"]),
        "equations_5_12_to_5_16_close": closure_residual
        <= float(acceptance["component_reconstruction_tolerance_hartree"]),
        "nonzero_nonplanar_effect": abs(endpoint)
        >= float(acceptance["nonzero_effect_floor_hartree"]),
        "no_sigma_sigma": not bool(master["boundaries"]["sigma_sigma_enabled"]),
        "no_production_label": not bool(
            master["boundaries"]["production_labels_allowed"]
        ),
    }
    components = {
        "direct_intrafragment_pi_sigma": direct_intra,
        "direct_interfragment_pi_sigma": direct_inter,
        "pi_subsystem_response": delta_pi,
        "sigma_subsystem_response": delta_sigma,
        "sum": component_sum,
    }
    algebraic_pass = all(checks.values())
    physical_magnitude_screen_pass = abs(endpoint) <= float(
        acceptance["physical_endpoint_magnitude_limit_hartree"]
    )
    disposition = (
        "PASS"
        if algebraic_pass and physical_magnitude_screen_pass
        else "ALGEBRAIC_PASS_PHYSICAL_QUARANTINE"
        if algebraic_pass
        else "QUARANTINE"
    )
    return {
        "experiment_id": master["experiment_id"],
        "protocol": master["protocol"],
        "disposition": disposition,
        "algebraic_reconstruction_pass": algebraic_pass,
        "physical_magnitude_screen_pass": physical_magnitude_screen_pass,
        "angle_degrees": float(torsion["angle_degrees"]),
        "state_energies_hartree": {
            "G": float(ground["energy"]),
            "FUD_source_block_metric": source_fud_energy,
            "FUD_physical_projector_diagnostic": float(
                fud_internal["diagnostic_energy_hartree"]
            ),
        },
        "state_difference": {
            "expression": "E_G-E_FUD",
            "hartree": endpoint,
            "kcal_mol": endpoint * HARTREE_TO_KCAL_MOL,
        },
        "components_hartree": components,
        "components_kcal_mol": {
            key: value * HARTREE_TO_KCAL_MOL for key, value in components.items()
        },
        "direct_fragment_matrix_hartree": direct_terms,
        "closure_residual_hartree": closure_residual,
        "density_diagnostics": {
            "ground_basis_reconstruction": ground_density_residual,
            "fud_basis_reconstruction": fud_density_residual,
            "fud_pi_sigma_cross_block_norm": fud_cross_density,
            "fud_physical_metric_idempotency_residual": float(
                source_fud["density_physical_metric_idempotency_residual"]
            ),
            "fud_density_fixed_point_residual": float(
                source_fud["final_density_fixed_point_residual"]
            ),
        },
        "checks": checks,
        "source": {
            "pdf_sha256": "07AADF5E25967616C4076C8B732EBB17E9E179F31C6546B6EB06D46E96D4A85D",
            "pdf_pages": [79, 80],
            "printed_pages": [138, 139, 140, 141],
            "equations": ["5-12", "5-13", "5-14", "5-15", "5-16"],
        },
        "provenance": {
            "git_commit": git_commit(),
            "config_sha256": canonical_digest(master),
        },
        "boundaries": master["boundaries"],
    }


def render_markdown(report: dict[str, Any]) -> str:
    components = report["components_kcal_mol"]
    lines = [
        "# Gate 0 Chapter 5 pi-sigma reconstruction",
        "",
        f"- Disposition: **{report['disposition']}**",
        f"- Algebraic reconstruction: `{report['algebraic_reconstruction_pass']}`",
        f"- Physical magnitude screen: `{report['physical_magnitude_screen_pass']}`",
        f"- Geometry: `{report['angle_degrees']:.1f}` degrees",
        f"- E_G-E_FUD: `{report['state_difference']['kcal_mol']:.9f} kcal/mol`",
        f"- Closure residual: `{report['closure_residual_hartree']:.3e} Eh`",
        "",
        "| Chapter 5 term | kcal/mol |",
        "|---|---:|",
        f"| Direct intrafragment pi-sigma (5-14) | {components['direct_intrafragment_pi_sigma']:.9f} |",
        f"| Direct interfragment pi-sigma (5-13) | {components['direct_interfragment_pi_sigma']:.9f} |",
        f"| Pi subsystem response (5-15) | {components['pi_subsystem_response']:.9f} |",
        f"| Sigma subsystem response (5-16) | {components['sigma_subsystem_response']:.9f} |",
        f"| Sum (5-12) | {components['sum']:.9f} |",
        "",
        "This is a nonproduction reconstruction on one project geometry.",
        "Sigma-sigma/PDSI/FUL is not included in this report.",
        "",
    ]
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
        f"{report['disposition']}: E_G-E_FUD="
        f"{report['state_difference']['kcal_mol']:.9f} kcal/mol, "
        f"closure={report['closure_residual_hartree']:.3e} Eh"
    )
    return 0 if report["algebraic_reconstruction_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
