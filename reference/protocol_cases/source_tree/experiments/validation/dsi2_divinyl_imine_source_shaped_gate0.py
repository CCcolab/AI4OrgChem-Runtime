"""Run the source-shaped three-fragment DSI-2 candidate in bounded stages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from ai4orgchem.lfmo.kost import bounded_alternating_kost, bounded_multi_target_kost
from ai4orgchem.lfmo.conditional_scf import (
    fixed_group_occupations, grouped_generalized_eigh,
    grouped_nonorthogonal_closed_shell_density, nonorthogonal_closed_shell_density,
)
from ai4orgchem.lfmo.reflection import (
    adapt_reflection_blocks,
    ao_plane_reflection_operator,
)
from ai4orgchem.lfmo.state_masks import block_mask, metric_diagnostics
from experiments.validation.one_cut_ch3_reference_h_gate0 import ao_indices_for_atoms
from experiments.validation.one_cut_conditional_scf_gate0 import (
    ROOT, git_commit, json_safe, load_yaml, run_conditional_scf,
)
from experiments.validation.two_cut_ch2_four_column_gate0 import canonical_geometry
from experiments.validation.two_cut_ch2_uhf_gate0 import inverse_sqrt


DEFAULT_CONFIG = ROOT / "configs" / "qm" / "dsi2_divinyl_imine_source_shaped_v0.1.yaml"
DEFAULT_OUTPUT = ROOT / "artifacts" / "raw" / "dsi2_divinyl_imine_source_shaped_2026-08-14.json"
DEFAULT_MARKDOWN = ROOT / "docs" / "reports" / "gate0_dsi2_divinyl_imine_source_shaped_2026-08-14.md"


def active_masked_state(config: dict[str, Any]) -> dict[str, Any]:
    """Return the explicitly selected DSI state, retaining DSI-2 compatibility."""

    return config[str(config.get("active_masked_state", "dsi2_state"))]


def fragment_atoms(config: dict[str, Any], fragment_id: str) -> list[list[Any]]:
    atoms = config["geometry"]["atoms"]
    return [atoms[int(index)] for index in config["primitive_fragments"][fragment_id]["atom_indices"]]


def run_fragment_uhf_with_fallback(
    atoms: list[list[Any]], basis: str, charge: int, spin: int, scf_config: dict[str, Any]
) -> dict[str, Any]:
    from pyscf import gto, scf
    from pyscf.mcscf.addons import make_natural_orbitals

    molecule = gto.M(
        atom=canonical_geometry(atoms), basis=basis, charge=charge, spin=spin,
        unit="Angstrom", symmetry=False, verbose=0,
    )
    mean_field = scf.UHF(molecule)
    mean_field.conv_tol = float(scf_config["convergence_tolerance"])
    mean_field.max_cycle = int(scf_config["max_cycles"])
    mean_field.init_guess = str(scf_config["initial_guess"])
    mean_field.verbose = 0
    mean_field.kernel()
    fallback_used = False
    if not mean_field.converged:
        fallback_used = True
        density = mean_field.make_rdm1()
        second_order = mean_field.newton()
        second_order.conv_tol = mean_field.conv_tol
        second_order.max_cycle = mean_field.max_cycle
        second_order.verbose = 0
        second_order.kernel(dm0=density)
        mean_field = second_order
    occupations, coefficients = make_natural_orbitals(mean_field)
    return {
        "molecule": molecule,
        "converged": bool(mean_field.converged),
        "fallback_used": fallback_used,
        "occupations": occupations,
        "coefficients": coefficients,
    }


def build_fragment_states(config: dict[str, Any]) -> dict[str, Any]:
    electronic = config["electronic_structure"]
    scf_config = config["fragment_scf"]
    lower, upper = map(float, scf_config["singly_occupied_window"])
    states: dict[str, Any] = {}
    for fragment_id in ("A", "B", "C"):
        fragment = config["primitive_fragments"][fragment_id]
        state = run_fragment_uhf_with_fallback(
            fragment_atoms(config, fragment_id),
            str(electronic["basis"]),
            int(fragment["charge"]),
            int(fragment["spin"]),
            scf_config,
        )
        candidates = [
            int(index) for index, value in enumerate(state["occupations"])
            if lower <= float(value) <= upper
        ]
        states[fragment_id] = {
            **state,
            "candidate_indices": candidates,
            "expected_cut_somos": int(fragment["expected_cut_somos"]),
        }
    return states


def fragment_stage(config: dict[str, Any]) -> dict[str, Any]:
    states = build_fragment_states(config)
    checks = {
        f"fragment_{fragment_id}_scf_converged": bool(state["converged"])
        for fragment_id, state in states.items()
    }
    checks.update(
        {
            f"fragment_{fragment_id}_cut_somo_count": len(state["candidate_indices"])
            == state["expected_cut_somos"]
            for fragment_id, state in states.items()
        }
    )
    return {
        "experiment_id": config["experiment_id"],
        "stage": "fragment_uhf_natural_orbitals",
        "disposition": "PASS" if all(checks.values()) else "QUARANTINE",
        "checks": checks,
        "fragments": {
            fragment_id: {
                "formula": config["primitive_fragments"][fragment_id]["formula"],
                "electron_count": int(state["molecule"].nelectron),
                "natural_occupations": np.asarray(state["occupations"]).tolist(),
                "candidate_indices": state["candidate_indices"],
                "second_order_fallback_used": bool(state["fallback_used"]),
            }
            for fragment_id, state in states.items()
        },
        "boundaries": {
            "kost_run": False,
            "conditional_fragment_scf_run": False,
            "dsi2_masked_scf_run": False,
            "energy_label_generated": False,
        },
    }


def reference_positions(config: dict[str, Any], fragment_id: str) -> list[list[Any]]:
    atoms = config["geometry"]["atoms"]
    fragment = config["primitive_fragments"][fragment_id]
    distance = float(config["reference_hydrogen_distance_angstrom"])
    result: list[list[Any]] = []
    for cut_index, partner_index in zip(
        fragment["cut_atom_indices"], fragment["external_partner_indices"], strict=True
    ):
        origin = np.asarray(atoms[int(cut_index)][1:], dtype=float)
        partner = np.asarray(atoms[int(partner_index)][1:], dtype=float)
        direction = partner - origin
        direction /= np.linalg.norm(direction)
        result.append(["H", *(origin + distance * direction).tolist()])
    return result


def build_source_fragment(
    config: dict[str, Any], fragment_id: str, state: dict[str, Any],
    type_reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from pyscf import gto

    fragment_config = config["primitive_fragments"][fragment_id]
    atoms = fragment_atoms(config, fragment_id)
    references = reference_positions(config, fragment_id)
    composite = gto.M(
        atom=canonical_geometry([*atoms, *references]),
        basis=str(config["electronic_structure"]["basis"]),
        charge=0,
        spin=0,
        unit="Angstrom",
        symmetry=False,
        verbose=0,
    )
    overlap = composite.intor_symmetric("int1e_ovlp")
    fragment_rows = ao_indices_for_atoms(composite, list(range(len(atoms))))
    reference_rows = [
        ao_indices_for_atoms(composite, [len(atoms) + index])
        for index in range(len(references))
    ]
    reference_states = [
        run_fragment_uhf_with_fallback(
            [reference], str(config["electronic_structure"]["basis"]), 0, 1,
            config["fragment_scf"],
        )
        for reference in references
    ]
    lower, upper = map(float, config["fragment_scf"]["singly_occupied_window"])
    reference_somos = [
        next(
            int(index) for index, value in enumerate(reference["occupations"])
            if lower <= float(value) <= upper
        )
        for reference in reference_states
    ]

    occupations = np.asarray(state["occupations"], dtype=float)
    candidates = list(state["candidate_indices"])
    occupied = [
        index for index, value in enumerate(occupations)
        if index not in candidates and float(value) > 1.5
    ]
    vacant = [
        index for index, value in enumerate(occupations)
        if index not in candidates and float(value) < 0.5
    ]
    classes = [
        "cut" if index in candidates else "occupied" if index in occupied else "vacant"
        for index in range(len(occupations))
    ]
    coordinates = np.asarray(state["molecule"].atom_coords(unit="Angstrom"), dtype=float)
    _, _, axes = np.linalg.svd(coordinates - np.mean(coordinates, axis=0))
    plane_normal = axes[-1]
    reflection = ao_plane_reflection_operator(state["molecule"], plane_normal)
    # When a typed reference subspace is supplied, reflection is only a local
    # orbital-gauge preconditioner. Final sigma/pi types come from the metric
    # cross-geometry transport below; do not reject the target geometry for a
    # local reflection residual that the reference transport is meant to avoid.
    has_type_reference = type_reference is not None
    adaptation = adapt_reflection_blocks(
        state["coefficients"], state["molecule"].intor_symmetric("int1e_ovlp"),
        reflection, occupations, classes,
        parity_tolerance=float(
            config["acceptance"].get("reflection_block_closure_tolerance", 1.0e-8)
        ),
        classification_policy=(
            "spectral_sign"
            if has_type_reference
            else str(
                config["acceptance"].get(
                    "reflection_classification_policy", "exact_closure"
                )
            )
        ),
        minimum_absolute_eigenvalue=float(
            0.0
            if has_type_reference
            else config["acceptance"].get(
                "minimum_absolute_reflection_eigenvalue", 0.0
            )
        ),
    )
    parity_by_source: dict[int, str] = {}
    for block in adaptation["blocks"]:
        parity_by_source.update(
            {
                int(index): str(parity)
                for index, parity in zip(
                    block["indices"], block["adapted_parities"], strict=True
                )
            }
        )
    if any(parity_by_source[index] != "sigma" for index in candidates):
        raise RuntimeError(f"fragment {fragment_id} cut SOMO is not sigma")

    fragment_coefficients = np.zeros((composite.nao_nr(), len(occupations)))
    fragment_coefficients[fragment_rows, :] = adaptation["coefficients"]
    probes = np.zeros((composite.nao_nr(), len(references)))
    reference_vacants: list[np.ndarray] = []
    for column, (rows, reference, somo) in enumerate(
        zip(reference_rows, reference_states, reference_somos, strict=True)
    ):
        probes[np.ix_(rows, [column])] = reference["coefficients"][:, [somo]]
        for vacant_index in range(reference["coefficients"].shape[1]):
            if vacant_index == somo:
                continue
            embedded_vacant = np.zeros((composite.nao_nr(), 1))
            embedded_vacant[rows, :] = reference["coefficients"][:, [vacant_index]]
            reference_vacants.append(embedded_vacant)

    raw_targets = fragment_coefficients[:, candidates]
    if len(candidates) == 1:
        targets = raw_targets.copy()
        if float((targets.T @ overlap @ probes)[0, 0]) < 0.0:
            targets *= -1.0
        scheduler = bounded_alternating_kost(
            targets[:, [0]], fragment_coefficients[:, occupied],
            fragment_coefficients[:, vacant], probes[:, [0]], overlap,
            occupied_labels=occupied, vacant_labels=vacant,
            tolerance=float(config["kost"]["tolerance"]),
            maximum_cycles=int(config["kost"]["maximum_cycles"]),
            occupied_maximum_sweeps=int(config["kost"]["occupied_maximum_sweeps"]),
            monotonic_tolerance=float(config["kost"]["monotonic_tolerance"]),
        )
        current = scheduler["current_block"]
        localized_targets = current[:, :1]
        b_ov = current[:, 1:]
        kost_residual = max(
            float(scheduler["maximum_occupied_probe_overlap"]),
            float(scheduler["maximum_vacant_probe_overlap"]),
        )
        kost_quiescent = bool(scheduler["scheduler_quiescent"])
    else:
        projected = raw_targets @ (raw_targets.T @ overlap @ probes)
        targets = projected @ inverse_sqrt(projected.T @ overlap @ projected)
        cross = targets.T @ overlap @ probes
        for index in range(len(candidates)):
            if cross[index, index] < 0.0:
                targets[:, index] *= -1.0
        scheduler = bounded_multi_target_kost(
            targets, fragment_coefficients[:, occupied], fragment_coefficients[:, vacant],
            probes, overlap,
            tolerance=float(config["kost"]["tolerance"]),
            maximum_macro_cycles=int(config["kost"]["maximum_macro_cycles"]),
            single_target_maximum_cycles=int(config["kost"]["maximum_cycles"]),
            occupied_maximum_sweeps=int(config["kost"]["occupied_maximum_sweeps"]),
            monotonic_tolerance=float(config["kost"]["monotonic_tolerance"]),
        )
        current = scheduler["current_block"]
        localized_targets = current[:, : len(candidates)]
        b_ov = current[:, len(candidates) :]
        kost_residual = float(scheduler["maximum_auxiliary_probe_overlap"])
        kost_quiescent = bool(scheduler["scheduler_quiescent"])

    local_b_ov = b_ov[fragment_rows, :]
    local_overlap = state["molecule"].intor_symmetric("int1e_ovlp")
    tracking_minimum = 1.0
    if type_reference is None:
        restricted = local_b_ov.T @ local_overlap @ reflection @ local_b_ov
        eigenvalues, eigenvectors = np.linalg.eigh(0.5 * (restricted + restricted.T))
        reflection_eigenvalues = eigenvalues.tolist()
        policy = str(
            config["acceptance"].get(
                "reflection_classification_policy", "exact_closure"
            )
        )
        if policy == "spectral_sign":
            minimum = float(
                config["acceptance"]["minimum_absolute_reflection_eigenvalue"]
            )
            sigma = np.where(eigenvalues >= minimum)[0].tolist()
            pi = np.where(eigenvalues <= -minimum)[0].tolist()
        else:
            tolerance = float(config["acceptance"]["reflection_eigenvalue_tolerance"])
            sigma = np.where(np.abs(eigenvalues - 1.0) <= tolerance)[0].tolist()
            pi = np.where(np.abs(eigenvalues + 1.0) <= tolerance)[0].tolist()
        mixed = [index for index in range(len(eigenvalues)) if index not in {*sigma, *pi}]
        order = [*sigma, *pi, *mixed]
        compressed_b_ov = b_ov @ eigenvectors[:, order]
    else:
        from pyscf import gto

        current_whitener = inverse_sqrt(local_b_ov.T @ local_overlap @ local_b_ov)
        current_orthonormal = local_b_ov @ current_whitener
        reference_coefficients = np.asarray(type_reference["coefficients"], dtype=float)
        reference_types = list(type_reference["types"])
        reference_pi = reference_coefficients[:, [
            index for index, value in enumerate(reference_types) if value == "pi"
        ]]
        reference_metric = type_reference["molecule"].intor_symmetric("int1e_ovlp")
        reference_pi = reference_pi @ inverse_sqrt(
            reference_pi.T @ reference_metric @ reference_pi
        )
        cross_overlap = gto.intor_cross(
            "int1e_ovlp", type_reference["molecule"], state["molecule"]
        )
        _, singular_values, right_vectors_t = np.linalg.svd(
            reference_pi.T @ cross_overlap @ current_orthonormal,
            full_matrices=True,
        )
        pi_count = reference_pi.shape[1]
        right_vectors = right_vectors_t.T
        sigma_count = current_orthonormal.shape[1] - pi_count
        transform = current_whitener @ np.column_stack(
            (right_vectors[:, pi_count:], right_vectors[:, :pi_count])
        )
        compressed_b_ov = b_ov @ transform
        sigma = list(range(sigma_count))
        pi = list(range(sigma_count, sigma_count + pi_count))
        mixed = []
        reflection_eigenvalues = []
        tracking_minimum = float(np.min(singular_values))
    cut_columns: list[np.ndarray] = []
    for index in range(len(candidates)):
        cut_columns.extend((localized_targets[:, [index]], probes[:, [index]]))
    raw_sizes = [len(sigma), len(pi), len(mixed), 2 * len(candidates), *([1] * len(reference_vacants))]
    raw_roots = [
        sum(parity_by_source[index] == "sigma" for index in occupied),
        sum(parity_by_source[index] == "pi" for index in occupied),
        0,
        len(candidates),
        *([0] * len(reference_vacants)),
    ]
    group_sizes = [size for size in raw_sizes if size > 0]
    group_roots = [root for size, root in zip(raw_sizes, raw_roots, strict=True) if size > 0]
    working_basis = np.column_stack(
        (compressed_b_ov, *cut_columns, *reference_vacants)
    )
    if working_basis.shape != (composite.nao_nr(), composite.nao_nr()):
        raise RuntimeError(f"fragment {fragment_id} conditional basis is not square")
    inputs = {
        "spaces": {"composite": composite, "overlap": overlap},
        "working_basis": working_basis,
        "group_sizes": group_sizes,
    }
    run_config = {
        "conditional_blocks": {
            "group_sizes": group_sizes,
            "fixed_doubly_occupied_roots": group_roots,
        },
        "scf": config["conditional_scf"],
    }
    conditional = run_conditional_scf(run_config, inputs)
    b_width = b_ov.shape[1]
    optimized_b_ov = conditional["mean_field"].mo_coeff[:, :b_width]
    final_full = np.column_stack((optimized_b_ov, localized_targets))
    final_local = final_full[fragment_rows, :]
    types = ["sigma"] * len(sigma) + ["pi"] * len(pi) + ["mixed"] * len(mixed)
    types.extend(["sigma"] * len(candidates))
    roles = ["bonded"] * b_width + ["cut_single"] * len(candidates)
    post_kost_reflection_residual = (
        float(np.max(np.abs(np.abs(np.asarray(reflection_eigenvalues)) - 1.0)))
        if reflection_eigenvalues
        else 0.0
    )
    maximum_reflection_residual = max(
        float(adaptation["maximum_parity_residual"]),
        post_kost_reflection_residual,
    )
    return {
        "fragment_id": fragment_id,
        "coefficients": final_local,
        "types": types,
        "roles": roles,
        "bonded_sigma_occupied_roots": int(raw_roots[0]),
        "bonded_pi_occupied_roots": int(raw_roots[1]),
        "cut_single_count": len(candidates),
        "kost_quiescent": kost_quiescent,
        "kost_residual": kost_residual,
        "conditional_converged": bool(conditional["converged"]),
        "conditional_cycles": int(conditional["cycles"]),
        "electron_trace": float(conditional["electron_trace"]),
        "expected_electrons": int(composite.nelectron),
        "idempotency": float(conditional["density_physical_metric_idempotency_residual"]),
        "root_continuity": float(conditional["minimum_root_subspace_singular_value"]),
        "mixed_count": len(mixed),
        "post_kost_reflection_eigenvalues": reflection_eigenvalues,
        "maximum_reflection_residual": maximum_reflection_residual,
        "type_tracking_minimum_singular_value": tracking_minimum,
        "group_sizes": group_sizes,
        "group_roots": group_roots,
        "_type_reference": {
            "molecule": state["molecule"],
            "coefficients": final_local[:, :b_width],
            "types": types[:b_width],
        },
    }


def run_projector_fixed_point_scf(
    config: dict[str, Any], inputs: dict[str, Any], roots: list[int]
) -> dict[str, Any]:
    from pyscf import lib, scf

    molecule = inputs["spaces"]["composite"]
    overlap = inputs["spaces"]["overlap"]
    working_basis = inputs["working_basis"]
    group_sizes = inputs["group_sizes"]
    state_config = active_masked_state(config)
    occupations = fixed_group_occupations(group_sizes, roots)
    mask = block_mask(group_sizes)
    working_metric = working_basis.T @ overlap @ working_basis
    masked_metric = working_metric * mask
    mean_field = scf.RHF(molecule)
    mean_field.verbose = 0
    hcore = mean_field.get_hcore()
    if "initial_density" in inputs:
        density = np.asarray(inputs["initial_density"], dtype=float).copy()
    else:
        density = np.asarray(
            mean_field.get_init_guess(
                key=str(config["conditional_scf"]["initial_guess"])
            ),
            dtype=float,
        ).copy()
    density_diis = lib.diis.DIIS()
    density_diis.space = int(state_config["density_diis_space"])
    density_diis_enabled = bool(state_config.get("density_diis_enabled", True))
    diis_start = int(state_config["density_diis_start_cycle"])
    maximum_cycles = int(state_config["density_max_cycles"])
    density_tolerance = float(state_config["density_fixed_point_tolerance"])
    energy_tolerance = float(config["conditional_scf"]["convergence_tolerance"])
    previous_energy: float | None = None
    external_references = inputs.get("root_reference_occupied")
    external_overlap = inputs.get("root_reference_overlap")
    previous_occupied: list[np.ndarray | None] = (
        [np.asarray(value, dtype=float).copy() for value in external_references]
        if external_references is not None
        else [None] * len(group_sizes)
    )
    previous_metrics: list[np.ndarray] = [
        np.asarray(external_overlap, dtype=float) if external_overlap is not None else overlap
        for _ in group_sizes
    ]
    offsets = np.cumsum([0, *group_sizes])
    history: list[dict[str, float]] = []
    minimum_root_continuity = 1.0
    maximum_generalized_residual = 0.0
    converged = False
    final_coefficients: np.ndarray | None = None

    for cycle in range(1, maximum_cycles + 1):
        veff = mean_field.get_veff(molecule, density)
        physical_fock = hcore + veff
        result = grouped_generalized_eigh(
            working_basis.T @ physical_fock @ working_basis,
            working_metric,
            group_sizes,
        )
        coefficients = working_basis @ result["transform"]
        for group, count in enumerate(roots):
            if count == 0:
                continue
            start, stop = offsets[group], offsets[group + 1]
            candidates = coefficients[:, start:stop].copy()
            reference = previous_occupied[group]
            if reference is None:
                continue
            cross = reference.T @ previous_metrics[group] @ candidates
            scores = np.sum(np.abs(cross) ** 2, axis=0)
            selected = sorted(
                range(candidates.shape[1]), key=lambda index: (-float(scores[index]), index)
            )[:count]
            remaining = [index for index in range(candidates.shape[1]) if index not in selected]
            coefficients[:, start:stop] = candidates[:, [*selected, *remaining]]
        density_reconstruction = str(state_config["density_reconstruction"])
        if density_reconstruction == "physical_metric_nonorthogonal_occupied_projector":
            candidate = nonorthogonal_closed_shell_density(
                coefficients, overlap, occupations
            )
        elif density_reconstruction == "source_block_metric_group_projector":
            candidate = grouped_nonorthogonal_closed_shell_density(
                coefficients, overlap, group_sizes, roots
            )
        else:
            raise ValueError(
                f"unsupported density reconstruction: {density_reconstruction}"
            )
        candidate_veff = mean_field.get_veff(molecule, candidate)
        energy = float(mean_field.energy_tot(candidate, hcore, candidate_veff))
        density_residual = float(
            np.linalg.norm(candidate - density, ord="fro")
            / max(float(np.linalg.norm(candidate, ord="fro")), 1.0)
        )
        energy_change = (
            abs(energy - previous_energy) if previous_energy is not None else float("inf")
        )
        for group, count in enumerate(roots):
            if count == 0:
                continue
            occupied = coefficients[:, offsets[group] : offsets[group] + count]
            previous = previous_occupied[group]
            if previous is not None:
                singular_values = np.linalg.svd(
                    previous.T @ previous_metrics[group] @ occupied, compute_uv=False
                )
                minimum_root_continuity = min(
                    minimum_root_continuity, float(np.min(singular_values))
                )
            previous_occupied[group] = occupied.copy()
            previous_metrics[group] = overlap
        maximum_generalized_residual = max(
            maximum_generalized_residual,
            float(result["maximum_block_generalized_residual"]),
        )
        history.append(
            {
                "cycle": float(cycle), "energy": energy,
                "energy_change": energy_change,
                "density_fixed_point_residual": density_residual,
            }
        )
        final_coefficients = coefficients
        if density_residual <= density_tolerance and energy_change <= energy_tolerance:
            density = candidate
            converged = True
            break
        residual_matrix = candidate - density
        density = (
            density_diis.update(candidate, xerr=residual_matrix)
            if density_diis_enabled and cycle >= diis_start
            else candidate
        )
        density = 0.5 * (density + density.T)
        previous_energy = energy

    if final_coefficients is None:
        raise RuntimeError("density fixed-point solver did not execute")
    electron_trace = float(np.einsum("ij,ji->", density, overlap))
    idempotency = float(
        np.linalg.norm(density @ overlap @ density - 2.0 * density, ord="fro")
        / max(float(np.linalg.norm(density, ord="fro")), 1.0)
    )
    return {
        "converged": converged,
        "cycles": len(history),
        "experimental_conditional_scf_energy_hartree": history[-1]["energy"],
        "electron_trace": electron_trace,
        "density_physical_metric_idempotency_residual": idempotency,
        "minimum_root_subspace_singular_value": minimum_root_continuity,
        "maximum_generalized_residual": maximum_generalized_residual,
        "final_conditional_commutator_residual": float("nan"),
        "final_density_fixed_point_residual": history[-1]["density_fixed_point_residual"],
        "final_energy_change": history[-1]["energy_change"],
        "density_reconstruction": state_config["density_reconstruction"],
        "solver": state_config["solver"],
        "density_diis_enabled": density_diis_enabled,
        "history": history,
        "_final_coefficients": final_coefficients,
        "_final_density": density,
    }


def full_stage(
    config: dict[str, Any], *, return_internal: bool = False,
    source_type_references: dict[str, dict[str, Any]] | None = None,
    occupied_root_reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from pyscf import gto

    states = build_fragment_states(config)
    source_fragments = {
        fragment_id: build_source_fragment(
            config, fragment_id, state,
            None if source_type_references is None else source_type_references[fragment_id],
        )
        for fragment_id, state in states.items()
    }
    electronic = config["electronic_structure"]
    parent = gto.M(
        atom=canonical_geometry(config["geometry"]["atoms"]),
        basis=str(electronic["basis"]), charge=int(electronic["charge"]),
        spin=int(electronic["spin"]), unit="Angstrom", symmetry=False, verbose=0,
    )
    overlap = parent.intor_symmetric("int1e_ovlp")
    embedded_by_fragment: dict[str, np.ndarray] = {}
    for fragment_id, result in source_fragments.items():
        rows = ao_indices_for_atoms(
            parent, [int(value) for value in config["primitive_fragments"][fragment_id]["atom_indices"]]
        )
        embedded = np.zeros((parent.nao_nr(), result["coefficients"].shape[1]))
        embedded[np.ix_(rows, range(result["coefficients"].shape[1]))] = result["coefficients"]
        embedded_by_fragment[fragment_id] = embedded

    pi_by_fragment = {
        fragment_id: embedded_by_fragment[fragment_id][:, [
            index for index, value in enumerate(source_fragments[fragment_id]["types"])
            if value == "pi"
        ]]
        for fragment_id in ("A", "B", "C")
    }
    pi_labels_by_fragment = {
        fragment_id: [fragment_id] * pi_by_fragment[fragment_id].shape[1]
        for fragment_id in ("A", "B", "C")
    }
    sigma_parts = [
        embedded_by_fragment[fragment_id][:, [
            index for index, value in enumerate(source_fragments[fragment_id]["types"])
            if value == "sigma"
        ]]
        for fragment_id in ("A", "B", "C")
    ]
    sigma_role_parts = [
        [
            source_fragments[fragment_id]["roles"][index]
            for index, value in enumerate(source_fragments[fragment_id]["types"])
            if value == "sigma"
        ]
        for fragment_id in ("A", "B", "C")
    ]
    sigma_all = np.column_stack(tuple(sigma_parts))
    sigma_fragment_labels = [
        fragment_id
        for fragment_id, part in zip(("A", "B", "C"), sigma_parts, strict=True)
        for _ in range(part.shape[1])
    ]
    state_config = active_masked_state(config)
    pi_superfragments = list(state_config["pi_superfragments"])
    if pi_superfragments == ["A", "B_plus_C"]:
        pi_groups = [pi_by_fragment["A"], np.column_stack((pi_by_fragment["B"], pi_by_fragment["C"]))]
        pi_fragment_label_groups = [
            pi_labels_by_fragment["A"],
            [*pi_labels_by_fragment["B"], *pi_labels_by_fragment["C"]],
        ]
    elif pi_superfragments == ["A", "B", "C"]:
        pi_groups = [pi_by_fragment[fragment_id] for fragment_id in ("A", "B", "C")]
        pi_fragment_label_groups = [
            pi_labels_by_fragment[fragment_id] for fragment_id in ("A", "B", "C")
        ]
    elif pi_superfragments == ["molecule"]:
        pi_groups = [np.column_stack(tuple(pi_by_fragment[fragment_id] for fragment_id in ("A", "B", "C")))]
        pi_fragment_label_groups = [[
            *pi_labels_by_fragment["A"],
            *pi_labels_by_fragment["B"],
            *pi_labels_by_fragment["C"],
        ]]
    else:
        raise ValueError(f"unsupported pi superfragment partition: {pi_superfragments}")
    group_transform = str(config.get("state_invariance_group_transform", "identity"))
    if group_transform == "reverse_with_alternating_phase":
        transformed_groups: list[np.ndarray] = []
        for group in [*pi_groups, sigma_all]:
            transformed = group[:, ::-1].copy()
            transformed *= np.where(np.arange(transformed.shape[1]) % 2 == 0, 1.0, -1.0)
            transformed_groups.append(transformed)
        pi_groups = transformed_groups[:-1]
        sigma_all = transformed_groups[-1]
        pi_fragment_label_groups = [
            list(reversed(labels)) for labels in pi_fragment_label_groups
        ]
        sigma_fragment_labels = list(reversed(sigma_fragment_labels))
    elif group_transform != "identity":
        raise ValueError(f"unsupported state-invariance group transform: {group_transform}")
    working_basis = np.column_stack((*pi_groups, sigma_all))
    group_sizes = [group.shape[1] for group in pi_groups] + [sigma_all.shape[1]]
    roots = [int(value) for value in state_config["fixed_doubly_occupied_roots"]]
    state_id = str(state_config.get("id", "DSI-2"))
    state_slug = state_id.lower().replace("-", "")
    inputs = {
        "spaces": {"composite": parent, "overlap": overlap},
        "working_basis": working_basis,
        "group_sizes": group_sizes,
    }
    if occupied_root_reference is not None:
        reference_sizes = [int(value) for value in occupied_root_reference["group_sizes"]]
        reference_roots = [int(value) for value in occupied_root_reference["roots"]]
        if reference_sizes != group_sizes or reference_roots != roots:
            raise ValueError("occupied-root reference state dimensions do not match")
        reference_coefficients = np.asarray(occupied_root_reference["coefficients"], dtype=float)
        reference_offsets = np.cumsum([0, *reference_sizes])
        reference_occupied = [
            reference_coefficients[
                :, reference_offsets[group] : reference_offsets[group] + count
            ]
            for group, count in enumerate(reference_roots)
        ]
        cross_overlap = gto.intor_cross(
            "int1e_ovlp", occupied_root_reference["molecule"], parent
        )
        inputs["root_reference_occupied"] = reference_occupied
        inputs["root_reference_overlap"] = cross_overlap
        projected_occupied = [
            np.linalg.solve(overlap, cross_overlap.T @ coefficients)
            for coefficients in reference_occupied
            if coefficients.shape[1] > 0
        ]
        projected_all = np.column_stack(tuple(projected_occupied))
        inputs["initial_density"] = nonorthogonal_closed_shell_density(
            projected_all,
            overlap,
            np.full(projected_all.shape[1], 2.0),
        )
    run_config = {
        "conditional_blocks": {
            "group_sizes": group_sizes,
            "fixed_doubly_occupied_roots": roots,
        },
        "scf": {
            **config["conditional_scf"],
            "density_reconstruction": state_config["density_reconstruction"],
        },
    }
    rank = int(np.linalg.matrix_rank(working_basis))
    conditional = (
        run_projector_fixed_point_scf(config, inputs, roots)
        if str(state_config.get("solver", "")).startswith("density_fixed_point")
        else run_conditional_scf(run_config, inputs)
    )
    masked_metric = (working_basis.T @ overlap @ working_basis) * block_mask(group_sizes)
    metric = metric_diagnostics(masked_metric)
    acceptance = config["acceptance"]
    require_physical_idempotency = bool(
        state_config.get("physical_density_idempotency_required", True)
    )
    fragment_checks = {
        fragment_id: bool(
            result["kost_quiescent"]
            and result["conditional_converged"]
            and result["idempotency"] <= float(acceptance["physical_density_idempotency_tolerance"])
            and result["mixed_count"] == 0
        )
        for fragment_id, result in source_fragments.items()
    }
    checks = {
        "source_fragments": all(fragment_checks.values()),
        "global_basis_square_full_rank": working_basis.shape == (parent.nao_nr(), parent.nao_nr()) and rank == parent.nao_nr(),
        "masked_metric_spd": bool(metric["positive_definite"]),
        f"{state_slug}_scf_converged": bool(conditional["converged"]),
        "electron_trace": abs(float(conditional["electron_trace"]) - int(electronic["expected_electrons"])) <= float(acceptance["electron_trace_tolerance"]),
        "physical_density_idempotency": (
            not require_physical_idempotency
            or float(conditional["density_physical_metric_idempotency_residual"])
            <= float(acceptance["physical_density_idempotency_tolerance"])
        ),
        "root_continuity": float(conditional["minimum_root_subspace_singular_value"]) >= float(acceptance["root_subspace_minimum_singular_value"]),
        "density_fixed_point_residual": float(conditional["final_density_fixed_point_residual"]) <= float(state_config["density_fixed_point_tolerance"]),
        "energy_change": float(conditional["final_energy_change"]) <= float(config["conditional_scf"]["convergence_tolerance"]),
        "generalized_eigen_residual": float(conditional["maximum_generalized_residual"]) <= float(acceptance["generalized_eigen_residual_tolerance"]),
        "masked_metric_conditioned": float(metric["condition_number"]) <= float(acceptance["metric_condition_number_limit"]),
        "no_energy_label": state_config["energy_label_enabled"] is False,
    }
    state_result = {
        "state_id": state_id,
        "pi_superfragments": pi_superfragments,
        "state_invariance_group_transform": group_transform,
        "group_sizes": group_sizes,
        "fixed_doubly_occupied_roots": roots,
        "basis_shape": list(working_basis.shape),
        "basis_rank": rank,
        "masked_metric": metric,
        "scf_converged": bool(conditional["converged"]),
        "cycles": int(conditional["cycles"]),
        "electron_trace": float(conditional["electron_trace"]),
        "physical_density_idempotency_residual": float(conditional["density_physical_metric_idempotency_residual"]),
        "physical_density_idempotency_required": require_physical_idempotency,
        "minimum_root_subspace_singular_value": float(conditional["minimum_root_subspace_singular_value"]),
        "final_conditional_commutator_residual": float(conditional["final_conditional_commutator_residual"]),
        "solver": conditional.get("solver", "roothaan_conditional_scf"),
        "final_density_fixed_point_residual": conditional.get("final_density_fixed_point_residual"),
        "final_energy_change": conditional.get("final_energy_change"),
        "maximum_generalized_residual": conditional.get("maximum_generalized_residual"),
    }
    report = {
        "experiment_id": config["experiment_id"],
        "stage": f"source_shaped_fragment_to_{state_slug}_masked_scf",
        "disposition": "PASS" if all(checks.values()) else "QUARANTINE",
        "checks": checks,
        "fragment_checks": fragment_checks,
        "fragments": {
            fragment_id: {
                key: value for key, value in result.items()
                if key not in {"coefficients", "types", "_type_reference"}
            }
            for fragment_id, result in source_fragments.items()
        },
        state_slug: state_result,
        "provenance": {"git_commit": git_commit()},
        "boundaries": {
            "diagnostic_energy_computed": True,
            f"{state_slug}_energy_label_generated": False,
            "stabilization_interpretation_generated": False,
            "production_lfmo_claimed": False,
        },
    }
    if return_internal:
        report["_internal"] = {
            "molecule": parent,
            "overlap": overlap,
            "coefficients": conditional["_final_coefficients"],
            "density": conditional["_final_density"],
            "diagnostic_energy_hartree": conditional["experimental_conditional_scf_energy_hartree"],
            "group_sizes": group_sizes,
            "roots": roots,
            "working_basis": working_basis,
            "column_types": [
                *("pi" for group in pi_groups for _ in range(group.shape[1])),
                *("sigma" for _ in range(sigma_all.shape[1])),
            ],
            "column_fragments": [
                *(label for labels in pi_fragment_label_groups for label in labels),
                *sigma_fragment_labels,
            ],
            "column_roles": [
                *("bonded" for group in pi_groups for _ in range(group.shape[1])),
                *(role for roles in sigma_role_parts for role in roles),
            ],
            "bonded_sigma_occupied_roots_by_fragment": {
                fragment_id: int(result["bonded_sigma_occupied_roots"])
                for fragment_id, result in source_fragments.items()
            },
            "bonded_pi_occupied_roots_by_fragment": {
                fragment_id: int(result["bonded_pi_occupied_roots"])
                for fragment_id, result in source_fragments.items()
            },
            "cut_single_count_by_fragment": {
                fragment_id: int(result["cut_single_count"])
                for fragment_id, result in source_fragments.items()
            },
            "source_type_references": {
                fragment_id: result["_type_reference"]
                for fragment_id, result in source_fragments.items()
            },
        }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    failed = [name for name, value in report["checks"].items() if not value]
    dsi2 = report["dsi2"]
    lines = [
        "# Gate 0 source-shaped imine DSI-2 candidate", "",
        f"- Disposition: **{report['disposition']}**",
        f"- Failed checks: `{failed}`",
        "- DSI-2 energy/stabilization label: not generated", "",
        "| Diagnostic | Value |", "|---|---:|",
        f"| DSI-2 groups / occupied roots | {dsi2['group_sizes']} / {dsi2['fixed_doubly_occupied_roots']} |",
        f"| Global LFMO shape / rank | {dsi2['basis_shape']} / {dsi2['basis_rank']} |",
        f"| SCF converged / cycles | {dsi2['scf_converged']} / {dsi2['cycles']} |",
        f"| Electron trace | {dsi2['electron_trace']:.12f} |",
        f"| Physical-density idempotency | {dsi2['physical_density_idempotency_residual']:.3e} |",
        f"| Density fixed-point residual | {dsi2['final_density_fixed_point_residual']:.3e} |",
        f"| Final energy change (Eh) | {dsi2['final_energy_change']:.3e} |",
        f"| Root continuity | {dsi2['minimum_root_subspace_singular_value']:.6f} |",
        f"| Masked metric condition | {dsi2['masked_metric']['condition_number']:.6f} |", "",
        "## Fragment calculations", "",
    ]
    for fragment_id, value in report["fragments"].items():
        lines.append(
            f"- {fragment_id}: KOST `{value['kost_residual']:.3e}`, conditional cycles "
            f"`{value['conditional_cycles']}`, idempotency `{value['idempotency']:.3e}`, "
            f"groups `{value['group_sizes']}` / roots `{value['group_roots']}`."
        )
    lines.extend(["", "The diagnostic SCF value is retained internally without a DSI-2 or", "stabilization/destabilization label.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--stage", choices=("fragment", "full"), default="full")
    args = parser.parse_args()
    config = load_yaml(args.config.resolve())
    report = json_safe(
        fragment_stage(config) if args.stage == "fragment" else full_stage(config)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.stage == "full":
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
        print(
            f"{report['disposition']}: fragments={report['fragment_checks']} "
            f"SCF={report['dsi2']['scf_converged']} "
            f"idempotency={report['dsi2']['physical_density_idempotency_residual']:.3e}"
        )
    else:
        counts = {
            key: len(value["candidate_indices"]) for key, value in report["fragments"].items()
        }
        print(f"{report['disposition']}: cut_SOMOs={counts}")
    return 0 if report["disposition"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
