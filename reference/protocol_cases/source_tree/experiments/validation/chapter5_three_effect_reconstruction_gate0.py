"""Test whether the Chapter 5 pi-pi, pi-sigma and sigma-sigma effects close one cycle."""

from __future__ import annotations

import argparse
from copy import deepcopy
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


DEFAULT_CONFIG = ROOT / "configs" / "qm" / "chapter5_three_effect_reconstruction_v0.1.yaml"
DEFAULT_OUTPUT = ROOT / "artifacts" / "raw" / "chapter5_three_effect_reconstruction_2026-08-14.json"
DEFAULT_MARKDOWN = ROOT / "docs" / "reports" / "gate0_chapter5_three_effect_reconstruction_2026-08-14.md"


def partition_columns(
    types: list[str], fragments: list[str], roles: list[str], mode: str
) -> list[list[int]]:
    def select(*, orbital_type: str, fragment: str | None = None, role: str | None = None) -> list[int]:
        return [
            index
            for index, (kind, owner, column_role) in enumerate(
                zip(types, fragments, roles, strict=True)
            )
            if kind == orbital_type
            and (fragment is None or owner == fragment)
            and (role is None or column_role == role)
        ]

    pi = {fragment: select(orbital_type="pi", fragment=fragment) for fragment in ("A", "B", "C")}
    bonded_sigma = {
        fragment: select(orbital_type="sigma", fragment=fragment, role="bonded")
        for fragment in ("A", "B", "C")
    }
    cut = select(orbital_type="sigma", role="cut_single")
    if mode == "FUD":
        return [[*pi["A"], *pi["B"], *pi["C"]], [
            *bonded_sigma["A"], *[index for index in select(orbital_type="sigma") if index not in {
                *bonded_sigma["A"], *bonded_sigma["B"], *bonded_sigma["C"]
            }], *bonded_sigma["B"], *bonded_sigma["C"]
        ]]
    if mode == "DSI3":
        return [pi["A"], pi["B"], pi["C"], select(orbital_type="sigma")]
    if mode == "FUL":
        return [pi["A"], pi["B"], pi["C"], bonded_sigma["A"], bonded_sigma["B"], bonded_sigma["C"], cut]
    if mode == "PDSI":
        return [pi["A"], pi["B"], pi["C"], [
            *bonded_sigma["A"], *bonded_sigma["B"], *bonded_sigma["C"]
        ], cut]
    raise ValueError(f"unsupported state partition: {mode}")


def run_source_state(
    config: dict[str, Any], molecule: Any, overlap: np.ndarray,
    original_basis: np.ndarray, column_groups: list[list[int]], roots: list[int],
    density_reconstruction: str = "source_block_metric_group_projector",
) -> dict[str, Any]:
    order = [index for group in column_groups for index in group]
    if sorted(order) != list(range(original_basis.shape[1])):
        raise ValueError("state groups must partition every LFMO column exactly once")
    working_basis = original_basis[:, order]
    group_sizes = [len(group) for group in column_groups]
    state_config = deepcopy(config)
    state_config["fud_state"]["density_reconstruction"] = density_reconstruction
    result = run_projector_fixed_point_scf(
        state_config,
        {
            "spaces": {"composite": molecule, "overlap": overlap},
            "working_basis": working_basis,
            "group_sizes": group_sizes,
        },
        roots,
    )
    result["working_basis"] = working_basis
    result["group_sizes"] = group_sizes
    result["order"] = order
    return result


def assembled_energy(molecule: Any, density: np.ndarray) -> float:
    from pyscf import scf

    mean_field = scf.RHF(molecule)
    mean_field.verbose = 0
    hcore = np.asarray(mean_field.get_hcore(), dtype=float)
    fock = hcore + np.asarray(mean_field.get_veff(molecule, density), dtype=float)
    return 0.5 * float(np.einsum("ij,ji->", hcore + fock, density)) + float(molecule.energy_nuc())


def maximum_cross_group_density(state: dict[str, Any]) -> float:
    density, _ = density_in_working_basis(
        np.asarray(state["working_basis"], dtype=float),
        np.asarray(state["_final_density"], dtype=float),
    )
    offsets = np.cumsum([0, *state["group_sizes"]])
    return max(
        (
            float(
                np.linalg.norm(
                    density[
                        offsets[left] : offsets[left + 1],
                        offsets[right] : offsets[right + 1],
                    ],
                    ord="fro",
                )
            )
            for left in range(len(state["group_sizes"]))
            for right in range(left + 1, len(state["group_sizes"]))
        ),
        default=0.0,
    )


def symmetric_lowdin_basis(basis: np.ndarray, overlap: np.ndarray) -> np.ndarray:
    metric = basis.T @ overlap @ basis
    values, vectors = np.linalg.eigh(0.5 * (metric + metric.T))
    if float(np.min(values)) <= 0.0:
        raise ValueError("LFMO metric must be positive definite")
    inverse_sqrt = vectors @ np.diag(values ** -0.5) @ vectors.T
    orthogonal = basis @ inverse_sqrt
    residual = np.linalg.norm(
        orthogonal.T @ overlap @ orthogonal - np.eye(orthogonal.shape[1]),
        ord="fro",
    )
    if float(residual) > 1.0e-9:
        raise RuntimeError("symmetric Lowdin orthogonalization did not converge")
    return orthogonal


def state_cycle(
    ground_energy: float, energies: dict[str, float]
) -> dict[str, Any]:
    effects = {
        "pi_pi": energies["FUD"] - energies["DSI3"],
        "pi_sigma": ground_energy - energies["FUD"],
        "sigma_sigma": energies["PDSI"] - energies["FUL"],
    }
    three_sum = sum(effects.values())
    requested_total = ground_energy - energies["FUL"]
    bridge = energies["DSI3"] - energies["PDSI"]
    corrected_sum = three_sum + bridge
    return {
        "effects_hartree": effects,
        "three_effect_sum_hartree": three_sum,
        "requested_total_hartree": requested_total,
        "bridge_hartree": bridge,
        "corrected_sum_hartree": corrected_sum,
        "three_effect_closure_hartree": abs(three_sum - requested_total),
        "four_term_closure_hartree": abs(corrected_sum - requested_total),
    }


def state_definitions_from_internal(
    internal: dict[str, Any],
) -> dict[str, tuple[list[list[int]], list[int]]]:
    types = list(internal["column_types"])
    fragments = list(internal["column_fragments"])
    roles = list(internal["column_roles"])
    sigma_roots = internal["bonded_sigma_occupied_roots_by_fragment"]
    pi_roots = internal["bonded_pi_occupied_roots_by_fragment"]
    cut_counts = internal["cut_single_count_by_fragment"]
    pi_root_list = [int(pi_roots[fragment]) for fragment in ("A", "B", "C")]
    bonded_sigma_root_list = [
        int(sigma_roots[fragment]) for fragment in ("A", "B", "C")
    ]
    cut_roots = sum(
        int(cut_counts[fragment]) for fragment in ("A", "B", "C")
    ) // 2
    total_sigma_roots = sum(bonded_sigma_root_list) + cut_roots
    return {
        "FUD": (
            partition_columns(types, fragments, roles, "FUD"),
            [sum(pi_root_list), total_sigma_roots],
        ),
        "DSI3": (
            partition_columns(types, fragments, roles, "DSI3"),
            [*pi_root_list, total_sigma_roots],
        ),
        "FUL": (
            partition_columns(types, fragments, roles, "FUL"),
            [*pi_root_list, *bonded_sigma_root_list, cut_roots],
        ),
        "PDSI": (
            partition_columns(types, fragments, roles, "PDSI"),
            [*pi_root_list, sum(bonded_sigma_root_list), cut_roots],
        ),
    }


def ground_partition_diagnostics(
    ground: dict[str, Any], fud_state: dict[str, Any], overlap: np.ndarray
) -> dict[str, Any]:
    basis = np.asarray(fud_state["working_basis"], dtype=float)
    metric_residual = float(
        np.linalg.norm(basis.T @ overlap @ basis - np.eye(basis.shape[1]), ord="fro")
    )
    density_operator = (
        basis.T
        @ overlap
        @ np.asarray(ground["density"], dtype=float)
        @ overlap
        @ basis
    )
    fock = basis.T @ np.asarray(ground["fock"], dtype=float) @ basis
    pi_size = int(fud_state["group_sizes"][0])
    pi = slice(0, pi_size)
    sigma = slice(pi_size, basis.shape[1])
    return {
        "orthonormal_metric_residual": metric_residual,
        "pi_electron_population": float(np.trace(density_operator[pi, pi])),
        "sigma_electron_population": float(np.trace(density_operator[sigma, sigma])),
        "pi_density_eigenvalues_descending": sorted(
            np.linalg.eigvalsh(density_operator[pi, pi]).tolist(), reverse=True
        ),
        "pi_sigma_density_cross_norm": float(
            np.linalg.norm(density_operator[pi, sigma], ord="fro")
        ),
        "pi_sigma_fock_cross_norm_hartree": float(
            np.linalg.norm(fock[pi, sigma], ord="fro")
        ),
    }


def physical_pi_sigma_direct_response_decomposition(
    molecule: Any,
    ground: dict[str, Any],
    fud_state: dict[str, Any],
    original_fragments: list[str],
) -> dict[str, Any]:
    """Decompose E_G-E_FUD without changing the physical RHF Hamiltonian.

    This is the physical-metric counterpart of equations 5-12--5-16.  The
    direct term is evaluated at the ground-state density; the two response
    terms compare the diagonal pi and sigma blocks of G and FUD.  It is an
    energy-component identity, not a second constrained-state endpoint.
    """
    basis = np.asarray(fud_state["working_basis"], dtype=float)
    density_ground, ground_reconstruction = density_in_working_basis(
        basis, np.asarray(ground["density"], dtype=float)
    )
    density_fud_ao = np.asarray(fud_state["_final_density"], dtype=float)
    density_fud, fud_reconstruction = density_in_working_basis(
        basis, density_fud_ao
    )

    hcore_ao = np.asarray(ground["hcore"], dtype=float)
    fock_ground_ao = np.asarray(ground["fock"], dtype=float)
    fud_mean_field = ground["mean_field"].__class__(molecule)
    fud_mean_field.verbose = 0
    fock_fud_ao = hcore_ao + np.asarray(
        fud_mean_field.get_veff(molecule, density_fud_ao), dtype=float
    )
    hcore = basis.T @ hcore_ao @ basis
    fock_ground = basis.T @ fock_ground_ao @ basis
    fock_fud = basis.T @ fock_fud_ao @ basis

    pi_size = int(fud_state["group_sizes"][0])
    pi_indices = list(range(pi_size))
    sigma_indices = list(range(pi_size, basis.shape[1]))
    direct_total = block_energy(
        hcore, fock_ground, density_ground, pi_indices, sigma_indices, 1.0
    )
    direct_one_electron = block_energy(
        hcore, hcore, density_ground, pi_indices, sigma_indices, 1.0
    )
    direct_two_electron = block_energy(
        np.zeros_like(hcore),
        fock_ground - hcore,
        density_ground,
        pi_indices,
        sigma_indices,
        1.0,
    )
    pi_response = block_energy(
        hcore, fock_ground, density_ground, pi_indices, pi_indices, 0.5
    ) - block_energy(
        hcore, fock_fud, density_fud, pi_indices, pi_indices, 0.5
    )
    sigma_response = block_energy(
        hcore, fock_ground, density_ground, sigma_indices, sigma_indices, 0.5
    ) - block_energy(
        hcore, fock_fud, density_fud, sigma_indices, sigma_indices, 0.5
    )
    component_sum = direct_total + pi_response + sigma_response
    endpoint = float(ground["energy"]) - float(
        fud_state["experimental_conditional_scf_energy_hartree"]
    )

    ordered_fragments = [
        original_fragments[index] for index in fud_state["order"]
    ]
    direct_by_fragment_pair: dict[str, float] = {}
    for pi_fragment in ("A", "B", "C"):
        rows = [
            index
            for index in pi_indices
            if ordered_fragments[index] == pi_fragment
        ]
        for sigma_fragment in ("A", "B", "C"):
            columns = [
                index
                for index in sigma_indices
                if ordered_fragments[index] == sigma_fragment
            ]
            direct_by_fragment_pair[f"pi_{pi_fragment}__sigma_{sigma_fragment}"] = (
                block_energy(
                    hcore,
                    fock_ground,
                    density_ground,
                    rows,
                    columns,
                    1.0,
                )
            )
    direct_intrafragment = sum(
        value
        for key, value in direct_by_fragment_pair.items()
        if key[3] == key[-1]
    )
    direct_interfragment = direct_total - direct_intrafragment

    return {
        "method": "same_hamiltonian_physical_metric_direct_plus_response_identity",
        "endpoint_expression": "E_G-E_FUD",
        "endpoint_hartree": endpoint,
        "direct_total_hartree": direct_total,
        "direct_one_electron_hartree": direct_one_electron,
        "direct_two_electron_hartree": direct_two_electron,
        "direct_intrafragment_hartree": direct_intrafragment,
        "direct_interfragment_hartree": direct_interfragment,
        "direct_by_fragment_pair_hartree": direct_by_fragment_pair,
        "pi_response_hartree": pi_response,
        "sigma_response_hartree": sigma_response,
        "component_sum_hartree": component_sum,
        "closure_residual_hartree": abs(component_sum - endpoint),
        "direct_electronic_split_residual_hartree": abs(
            direct_total - direct_one_electron - direct_two_electron
        ),
        "direct_fragment_split_residual_hartree": abs(
            direct_total - direct_intrafragment - direct_interfragment
        ),
        "ground_density_reconstruction_residual": ground_reconstruction,
        "fud_density_reconstruction_residual": fud_reconstruction,
        "fud_pi_sigma_density_cross_norm": float(
            np.linalg.norm(
                density_fud[np.ix_(pi_indices, sigma_indices)], ord="fro"
            )
        ),
        "direct_component_sign": (
            "positive_destabilizing_component"
            if direct_total > 0.0
            else "nonpositive_component"
        ),
        "interpretation": {
            "allowed": "physical-metric direct pi-sigma interaction component",
            "forbidden": "source-equivalent total pi-sigma destabilization energy",
            "hamiltonian_changed": False,
            "production_label_allowed": False,
        },
    }


def physical_release_direct_response_decomposition(
    molecule: Any,
    basis: np.ndarray,
    hcore_ao: np.ndarray,
    mean_field_class: Any,
    relaxed_energy: float,
    relaxed_density_ao: np.ndarray,
    restricted_energy: float,
    restricted_density_ao: np.ndarray,
    restricted_groups: list[list[int]],
    group_labels: list[str],
    endpoint_expression: str,
) -> dict[str, Any]:
    """Resolve a nested physical-state release into cross-group and response terms."""
    if len(restricted_groups) != len(group_labels):
        raise ValueError("each restricted group requires one stable label")
    relaxed_density, relaxed_reconstruction = density_in_working_basis(
        basis, relaxed_density_ao
    )
    restricted_density, restricted_reconstruction = density_in_working_basis(
        basis, restricted_density_ao
    )

    def fock_for(density_ao: np.ndarray) -> np.ndarray:
        mean_field = mean_field_class(molecule)
        mean_field.verbose = 0
        fock_ao = hcore_ao + np.asarray(
            mean_field.get_veff(molecule, density_ao), dtype=float
        )
        return basis.T @ fock_ao @ basis

    hcore = basis.T @ hcore_ao @ basis
    relaxed_fock = fock_for(relaxed_density_ao)
    restricted_fock = fock_for(restricted_density_ao)
    zero = np.zeros_like(hcore)
    pair_terms: dict[str, float] = {}
    pair_one_electron: dict[str, float] = {}
    pair_two_electron: dict[str, float] = {}
    for left in range(len(restricted_groups)):
        for right in range(left + 1, len(restricted_groups)):
            label = f"{group_labels[left]}__{group_labels[right]}"
            rows = restricted_groups[left]
            columns = restricted_groups[right]
            pair_terms[label] = block_energy(
                hcore,
                relaxed_fock,
                relaxed_density,
                rows,
                columns,
                1.0,
            )
            pair_one_electron[label] = block_energy(
                hcore,
                hcore,
                relaxed_density,
                rows,
                columns,
                1.0,
            )
            pair_two_electron[label] = block_energy(
                zero,
                relaxed_fock - hcore,
                relaxed_density,
                rows,
                columns,
                1.0,
            )
    response_terms = {
        label: block_energy(
            hcore,
            relaxed_fock,
            relaxed_density,
            group,
            group,
            0.5,
        )
        - block_energy(
            hcore,
            restricted_fock,
            restricted_density,
            group,
            group,
            0.5,
        )
        for label, group in zip(group_labels, restricted_groups, strict=True)
    }
    direct_total = sum(pair_terms.values())
    response_total = sum(response_terms.values())
    endpoint = relaxed_energy - restricted_energy
    cross_density_norm = max(
        (
            float(
                np.linalg.norm(
                    restricted_density[np.ix_(
                        restricted_groups[left], restricted_groups[right]
                    )],
                    ord="fro",
                )
            )
            for left in range(len(restricted_groups))
            for right in range(left + 1, len(restricted_groups))
        ),
        default=0.0,
    )
    return {
        "method": "same_hamiltonian_physical_metric_nested_release_identity",
        "endpoint_expression": endpoint_expression,
        "endpoint_hartree": endpoint,
        "direct_cross_group_hartree": direct_total,
        "response_hartree": response_total,
        "component_sum_hartree": direct_total + response_total,
        "closure_residual_hartree": abs(direct_total + response_total - endpoint),
        "direct_one_electron_hartree": sum(pair_one_electron.values()),
        "direct_two_electron_hartree": sum(pair_two_electron.values()),
        "direct_split_residual_hartree": abs(
            direct_total
            - sum(pair_one_electron.values())
            - sum(pair_two_electron.values())
        ),
        "direct_pair_terms_hartree": pair_terms,
        "response_by_group_hartree": response_terms,
        "restricted_maximum_cross_group_density_norm": cross_density_norm,
        "relaxed_density_reconstruction_residual": relaxed_reconstruction,
        "restricted_density_reconstruction_residual": restricted_reconstruction,
        "direct_component_sign": (
            "positive_destabilizing_component"
            if direct_total > 0.0
            else "nonpositive_component"
        ),
        "production_label_allowed": False,
    }


def torsion_rotation_matrix(
    atoms: list[list[Any]], axis_indices: list[int], angle_degrees: float
) -> np.ndarray:
    origin = np.asarray(atoms[axis_indices[0]][1:], dtype=float)
    endpoint = np.asarray(atoms[axis_indices[1]][1:], dtype=float)
    axis = endpoint - origin
    axis /= np.linalg.norm(axis)
    angle = np.deg2rad(float(angle_degrees))
    cross = np.array(
        [
            [0.0, -axis[2], axis[1]],
            [axis[2], 0.0, -axis[0]],
            [-axis[1], axis[0], 0.0],
        ]
    )
    return (
        np.eye(3) * np.cos(angle)
        + (1.0 - np.cos(angle)) * np.outer(axis, axis)
        + np.sin(angle) * cross
    )


def atomic_normal_pi_sigma_basis(
    molecule: Any,
    overlap: np.ndarray,
    normal_by_atom: dict[int, np.ndarray],
) -> np.ndarray:
    labels = molecule.ao_labels()
    raw_columns: list[np.ndarray] = []
    for atom_index, normal in normal_by_atom.items():
        column = np.zeros(molecule.nao_nr(), dtype=float)
        found: dict[str, int] = {}
        for ao_index, label in enumerate(labels):
            fields = str(label).split()
            if int(fields[0]) != int(atom_index):
                continue
            orbital = fields[-1].lower()
            for component in ("x", "y", "z"):
                if orbital.endswith(f"p{component}"):
                    found[component] = ao_index
        if set(found) != {"x", "y", "z"}:
            raise RuntimeError(
                f"atom {atom_index} does not have one STO-3G p shell: {found}"
            )
        unit_normal = np.asarray(normal, dtype=float)
        unit_normal /= np.linalg.norm(unit_normal)
        for component, value in zip(("x", "y", "z"), unit_normal, strict=True):
            column[found[component]] = float(value)
        raw_columns.append(column)
    raw_pi = np.column_stack(raw_columns)
    pi_metric = raw_pi.T @ overlap @ raw_pi
    values, vectors = np.linalg.eigh(0.5 * (pi_metric + pi_metric.T))
    pi = raw_pi @ vectors @ np.diag(values ** -0.5) @ vectors.T

    metric_values, metric_vectors = np.linalg.eigh(0.5 * (overlap + overlap.T))
    sqrt_metric = metric_vectors @ np.diag(metric_values ** 0.5) @ metric_vectors.T
    inverse_sqrt_metric = (
        metric_vectors @ np.diag(metric_values ** -0.5) @ metric_vectors.T
    )
    euclidean_pi = sqrt_metric @ pi
    _, _, right_vectors_t = np.linalg.svd(euclidean_pi.T, full_matrices=True)
    sigma = inverse_sqrt_metric @ right_vectors_t.T[:, pi.shape[1] :]
    basis = np.column_stack((pi, sigma))
    residual = float(
        np.linalg.norm(basis.T @ overlap @ basis - np.eye(basis.shape[1]), ord="fro")
    )
    if residual > 1.0e-9:
        raise RuntimeError("atomic-normal pi/sigma basis is not metric orthonormal")
    return basis


def atomic_pi_with_lfmo_sigma_basis(
    atomic_basis: np.ndarray,
    lfmo_basis: np.ndarray,
    overlap: np.ndarray,
    pi_size: int,
) -> np.ndarray:
    pi = np.asarray(atomic_basis[:, :pi_size], dtype=float)
    sigma_seed = np.asarray(lfmo_basis[:, pi_size:], dtype=float)
    projected_sigma = sigma_seed - pi @ (pi.T @ overlap @ sigma_seed)
    sigma_metric = projected_sigma.T @ overlap @ projected_sigma
    values, vectors = np.linalg.eigh(0.5 * (sigma_metric + sigma_metric.T))
    if float(np.min(values)) <= 1.0e-12:
        raise RuntimeError("LFMO sigma seeds do not span the atomic-pi complement")
    sigma = projected_sigma @ vectors @ np.diag(values ** -0.5) @ vectors.T
    combined = np.column_stack((pi, sigma))
    residual = float(
        np.linalg.norm(
            combined.T @ overlap @ combined - np.eye(combined.shape[1]),
            ord="fro",
        )
    )
    if residual > 1.0e-9:
        raise RuntimeError("atomic-pi/LFMO-sigma basis is not metric orthonormal")
    return combined


def run(master: dict[str, Any]) -> dict[str, Any]:
    base = resolve_state_config(ROOT / str(master["fud_config"]))
    base["electronic_structure"]["basis"] = str(master["electronic_structure"]["basis"])
    planar = full_stage(base, return_internal=True)
    planar_internal = planar.pop("_internal")
    twisted = deepcopy(base)
    torsion = master["torsion"]
    twisted["geometry"]["atoms"] = rotate_about_axis(
        base["geometry"]["atoms"],
        [int(value) for value in torsion["axis_atom_indices"]],
        [int(value) for value in torsion["rotating_atom_indices"]],
        float(torsion["angle_degrees"]),
    )
    scaffold = full_stage(
        twisted,
        return_internal=True,
        source_type_references=planar_internal["source_type_references"],
        occupied_root_reference=planar_internal,
    )
    internal = scaffold.pop("_internal")
    molecule = internal["molecule"]
    overlap = np.asarray(internal["overlap"], dtype=float)
    basis = np.asarray(internal["working_basis"], dtype=float)
    definitions = state_definitions_from_internal(internal)
    states = {
        name: run_source_state(twisted, molecule, overlap, basis, groups, roots)
        for name, (groups, roots) in definitions.items()
    }
    ground = run_ground_state(twisted)
    energies = {"G": float(ground["energy"])}
    energies.update({
        name: float(state["experimental_conditional_scf_energy_hartree"])
        for name, state in states.items()
    })
    cycle = state_cycle(energies["G"], energies)
    effects = cycle["effects_hartree"]
    three_sum = float(cycle["three_effect_sum_hartree"])
    requested_total = float(cycle["requested_total_hartree"])
    bridge = float(cycle["bridge_hartree"])
    corrected_sum = float(cycle["corrected_sum_hartree"])

    orthogonal_basis = symmetric_lowdin_basis(basis, overlap)
    orthogonal_states = {
        name: run_source_state(
            twisted, molecule, overlap, orthogonal_basis, groups, roots
        )
        for name, (groups, roots) in definitions.items()
    }
    orthogonal_energies = {
        name: float(state["experimental_conditional_scf_energy_hartree"])
        for name, state in orthogonal_states.items()
    }
    orthogonal_cycle = state_cycle(energies["G"], orthogonal_energies)

    local_plane_scaffold = full_stage(twisted, return_internal=True)
    local_plane_internal = local_plane_scaffold.pop("_internal")
    local_plane_overlap = np.asarray(local_plane_internal["overlap"], dtype=float)
    local_plane_basis = symmetric_lowdin_basis(
        np.asarray(local_plane_internal["working_basis"], dtype=float),
        local_plane_overlap,
    )
    local_plane_definitions = state_definitions_from_internal(local_plane_internal)
    local_plane_states = {
        name: run_source_state(
            twisted,
            local_plane_internal["molecule"],
            local_plane_overlap,
            local_plane_basis,
            groups,
            roots,
        )
        for name, (groups, roots) in local_plane_definitions.items()
    }
    local_plane_energies = {
        name: float(state["experimental_conditional_scf_energy_hartree"])
        for name, state in local_plane_states.items()
    }
    local_plane_cycle = state_cycle(energies["G"], local_plane_energies)

    rotation = torsion_rotation_matrix(
        base["geometry"]["atoms"],
        [int(value) for value in torsion["axis_atom_indices"]],
        float(torsion["angle_degrees"]),
    )
    global_normal = np.array([0.0, 0.0, 1.0])
    atom_normals = {
        0: rotation @ global_normal,
        1: rotation @ global_normal,
        2: global_normal,
        3: global_normal,
        4: global_normal,
        5: global_normal,
    }
    atomic_basis = atomic_normal_pi_sigma_basis(molecule, overlap, atom_normals)
    atomic_fud = run_source_state(
        twisted,
        molecule,
        overlap,
        atomic_basis,
        [list(range(6)), list(range(6, molecule.nao_nr()))],
        [3, 19],
    )
    atomic_fud_energy = float(
        atomic_fud["experimental_conditional_scf_energy_hartree"]
    )
    hybrid_basis = atomic_pi_with_lfmo_sigma_basis(
        atomic_basis, basis, overlap, 6
    )
    hybrid_states = {
        name: run_source_state(
            twisted, molecule, overlap, hybrid_basis, groups, roots
        )
        for name, (groups, roots) in definitions.items()
    }
    hybrid_energies = {
        name: float(state["experimental_conditional_scf_energy_hartree"])
        for name, state in hybrid_states.items()
    }
    hybrid_cycle = state_cycle(energies["G"], hybrid_energies)
    physical_pi_sigma_components = physical_pi_sigma_direct_response_decomposition(
        molecule,
        ground,
        hybrid_states["FUD"],
        list(internal["column_fragments"]),
    )
    release_specs = {
        "pi_pi": {
            "relaxed": "FUD",
            "restricted": "DSI3",
            "groups": definitions["DSI3"][0],
            "labels": ["pi_A", "pi_B", "pi_C", "sigma_all"],
            "expression": "E_FUD-E_DSI3",
        },
        "sigma_sigma": {
            "relaxed": "PDSI",
            "restricted": "FUL",
            "groups": definitions["FUL"][0],
            "labels": [
                "pi_A",
                "pi_B",
                "pi_C",
                "bonded_sigma_A",
                "bonded_sigma_B",
                "bonded_sigma_C",
                "cut_sigma",
            ],
            "expression": "E_PDSI-E_FUL",
        },
    }
    physical_release_components = {
        "pi_sigma": physical_release_direct_response_decomposition(
            molecule,
            hybrid_basis,
            np.asarray(ground["hcore"], dtype=float),
            ground["mean_field"].__class__,
            float(ground["energy"]),
            np.asarray(ground["density"], dtype=float),
            hybrid_energies["FUD"],
            np.asarray(hybrid_states["FUD"]["_final_density"], dtype=float),
            definitions["FUD"][0],
            ["pi_all", "sigma_all"],
            "E_G-E_FUD",
        )
    }
    for effect, spec in release_specs.items():
        relaxed_name = str(spec["relaxed"])
        restricted_name = str(spec["restricted"])
        physical_release_components[effect] = (
            physical_release_direct_response_decomposition(
                molecule,
                hybrid_basis,
                np.asarray(ground["hcore"], dtype=float),
                ground["mean_field"].__class__,
                hybrid_energies[relaxed_name],
                np.asarray(
                    hybrid_states[relaxed_name]["_final_density"], dtype=float
                ),
                hybrid_energies[restricted_name],
                np.asarray(
                    hybrid_states[restricted_name]["_final_density"], dtype=float
                ),
                spec["groups"],
                spec["labels"],
                str(spec["expression"]),
            )
        )
    hybrid_physical_projector_states = {
        name: run_source_state(
            twisted,
            molecule,
            overlap,
            hybrid_basis,
            groups,
            roots,
            density_reconstruction=(
                "physical_metric_nonorthogonal_occupied_projector"
            ),
        )
        for name, (groups, roots) in definitions.items()
    }
    hybrid_dual_density_differences = {
        name: {
            "energy_hartree": abs(
                float(state["experimental_conditional_scf_energy_hartree"])
                - hybrid_energies[name]
            ),
            "density_relative_frobenius": float(
                np.linalg.norm(
                    np.asarray(state["_final_density"], dtype=float)
                    - np.asarray(hybrid_states[name]["_final_density"], dtype=float),
                    ord="fro",
                )
                / max(
                    float(
                        np.linalg.norm(
                            hybrid_states[name]["_final_density"], ord="fro"
                        )
                    ),
                    1.0,
                )
            ),
        }
        for name, state in hybrid_physical_projector_states.items()
    }

    # Independently apply equations 5-12--5-16 to the STO-3G FUD state.
    fud = states["FUD"]
    fud_basis = np.asarray(fud["working_basis"], dtype=float)
    fud_density_ao = np.asarray(fud["_final_density"], dtype=float)
    ground_density, _ = density_in_working_basis(fud_basis, ground["density"])
    fud_density, _ = density_in_working_basis(fud_basis, fud_density_ao)
    hcore_ao = np.asarray(ground["hcore"], dtype=float)
    fud_mean_field = ground["mean_field"].__class__(molecule)
    fud_mean_field.verbose = 0
    fud_fock_ao = hcore_ao + np.asarray(fud_mean_field.get_veff(molecule, fud_density_ao), dtype=float)
    hcore = fud_basis.T @ hcore_ao @ fud_basis
    ground_fock = fud_basis.T @ np.asarray(ground["fock"], dtype=float) @ fud_basis
    fud_fock = fud_basis.T @ fud_fock_ao @ fud_basis
    pi_indices = list(range(fud["group_sizes"][0]))
    sigma_indices = list(range(fud["group_sizes"][0], sum(fud["group_sizes"])))
    direct = block_energy(hcore, ground_fock, ground_density, pi_indices, sigma_indices, 1.0)
    pi_response = block_energy(hcore, ground_fock, ground_density, pi_indices, pi_indices, 0.5) - block_energy(hcore, fud_fock, fud_density, pi_indices, pi_indices, 0.5)
    sigma_response = block_energy(hcore, ground_fock, ground_density, sigma_indices, sigma_indices, 0.5) - block_energy(hcore, fud_fock, fud_density, sigma_indices, sigma_indices, 0.5)
    pi_sigma_equation_sum = direct + pi_response + sigma_response

    acceptance = master["acceptance"]
    state_checks = {
        name: {
            "converged": bool(state["converged"]),
            "density_fixed_point": float(state["final_density_fixed_point_residual"]) <= float(acceptance["state_scf_density_tolerance"]),
            "electron_trace": abs(float(state["electron_trace"]) - int(twisted["electronic_structure"]["expected_electrons"])) <= float(acceptance["electron_trace_tolerance"]),
            "energy_assembly": abs(assembled_energy(molecule, np.asarray(state["_final_density"])) - energies[name]) <= float(acceptance["state_energy_assembly_tolerance_hartree"]),
            "masked_cross_group_density_zero": maximum_cross_group_density(state) <= float(acceptance["source_cross_block_tolerance"]),
        }
        for name, state in states.items()
    }
    pi_sigma_closure = abs(pi_sigma_equation_sum - effects["pi_sigma"])
    three_effect_closure = float(cycle["three_effect_closure_hartree"])
    corrected_closure = float(cycle["four_term_closure_hartree"])
    bridge_zero = abs(bridge) <= float(acceptance["bridge_zero_tolerance_hartree"])
    physical_magnitude_ok = all(
        abs(value) <= float(acceptance["physical_endpoint_magnitude_limit_hartree"])
        for value in effects.values()
    )
    hybrid_ground_diagnostics = ground_partition_diagnostics(
        ground, hybrid_states["FUD"], overlap
    )
    hybrid_pi_eigenvalues = hybrid_ground_diagnostics[
        "pi_density_eigenvalues_descending"
    ]
    hybrid_checks = {
        "all_states_converged": all(
            bool(state["converged"]) for state in hybrid_states.values()
        ),
        "density_fixed_points": all(
            float(state["final_density_fixed_point_residual"])
            <= float(acceptance["state_scf_density_tolerance"])
            for state in hybrid_states.values()
        ),
        "physical_metric_idempotency": all(
            float(state["density_physical_metric_idempotency_residual"])
            <= float(acceptance["physical_density_idempotency_tolerance"])
            for state in hybrid_states.values()
        ),
        "masked_cross_group_density_zero": all(
            maximum_cross_group_density(state)
            <= float(acceptance["source_cross_block_tolerance"])
            for state in hybrid_states.values()
        ),
        "state_energy_assembly": all(
            abs(
                assembled_energy(molecule, np.asarray(state["_final_density"]))
                - hybrid_energies[name]
            )
            <= float(acceptance["state_energy_assembly_tolerance_hartree"])
            for name, state in hybrid_states.items()
        ),
        "three_target_components_in_chemical_scale": all(
            abs(value)
            <= float(acceptance["physical_component_magnitude_limit_hartree"])
            for value in hybrid_cycle["effects_hartree"].values()
        ),
        "pi_population": abs(
            float(hybrid_ground_diagnostics["pi_electron_population"])
            - float(acceptance["pi_population_target"])
        )
        <= float(acceptance["pi_population_tolerance"]),
        "three_occupied_pi_eigenvalues": min(hybrid_pi_eigenvalues[:3])
        >= float(acceptance["occupied_pi_eigenvalue_floor"]),
        "three_vacant_pi_eigenvalues": max(hybrid_pi_eigenvalues[3:])
        <= float(acceptance["vacant_pi_eigenvalue_ceiling"]),
        "four_term_state_path_closure": float(
            hybrid_cycle["four_term_closure_hartree"]
        )
        <= float(acceptance["three_effect_total_closure_tolerance_hartree"]),
        "dual_density_energy_equivalence": max(
            value["energy_hartree"]
            for value in hybrid_dual_density_differences.values()
        )
        <= float(acceptance["state_energy_assembly_tolerance_hartree"]),
        "dual_density_matrix_equivalence": max(
            value["density_relative_frobenius"]
            for value in hybrid_dual_density_differences.values()
        )
        <= float(acceptance["physical_density_idempotency_tolerance"]),
        "pi_sigma_direct_response_closure": float(
            physical_pi_sigma_components["closure_residual_hartree"]
        )
        <= float(acceptance["physical_component_closure_tolerance_hartree"]),
        "pi_sigma_direct_electronic_split": float(
            physical_pi_sigma_components[
                "direct_electronic_split_residual_hartree"
            ]
        )
        <= float(acceptance["physical_component_closure_tolerance_hartree"]),
        "pi_sigma_direct_fragment_split": float(
            physical_pi_sigma_components[
                "direct_fragment_split_residual_hartree"
            ]
        )
        <= float(acceptance["physical_component_closure_tolerance_hartree"]),
        "all_three_release_component_identities": all(
            float(component["closure_residual_hartree"])
            <= float(acceptance["physical_component_closure_tolerance_hartree"])
            and float(component["direct_split_residual_hartree"])
            <= float(acceptance["physical_component_closure_tolerance_hartree"])
            for component in physical_release_components.values()
        ),
    }
    physical_scale_resolution_pass = all(hybrid_checks.values())
    calculation_complete = bool(ground["converged"]) and all(
        all(checks.values()) for checks in state_checks.values()
    ) and pi_sigma_closure <= float(acceptance["pi_sigma_equation_closure_tolerance_hartree"])
    three_effects_reconstruct = bridge_zero and three_effect_closure <= float(acceptance["three_effect_total_closure_tolerance_hartree"])
    four_term_path_reconstructs = corrected_closure <= float(
        acceptance["three_effect_total_closure_tolerance_hartree"]
    )
    if physical_scale_resolution_pass:
        disposition = "PHYSICAL_METRIC_CANDIDATE_PASS_SOURCE_DEFINITION_QUARANTINE"
    elif calculation_complete and four_term_path_reconstructs:
        disposition = (
            "FOUR_TERM_ALGEBRAIC_PASS"
            if physical_magnitude_ok
            else "FOUR_TERM_ALGEBRAIC_PASS_PHYSICAL_QUARANTINE"
        )
    else:
        disposition = "DIAGNOSTIC_INCOMPLETE_QUARANTINE"
    return {
        "experiment_id": master["experiment_id"],
        "protocol": master["protocol"],
        "disposition": disposition,
        "calculation_complete": calculation_complete,
        "three_effects_reconstruct_requested_total": three_effects_reconstruct,
        "four_term_state_path_reconstructs_requested_total": four_term_path_reconstructs,
        "physical_magnitude_screen_pass": physical_magnitude_ok,
        "physical_scale_resolution_pass": physical_scale_resolution_pass,
        "angle_degrees": float(torsion["angle_degrees"]),
        "basis": str(master["electronic_structure"]["basis"]),
        "state_energies_hartree": energies,
        "effects_hartree": effects,
        "effects_kcal_mol": {key: value * HARTREE_TO_KCAL_MOL for key, value in effects.items()},
        "requested_total": {"expression": "E_G-E_FUL", "hartree": requested_total, "kcal_mol": requested_total * HARTREE_TO_KCAL_MOL},
        "three_effect_sum_hartree": three_sum,
        "bridge": {"expression": "E_DSI3-E_PDSI", "hartree": bridge, "kcal_mol": bridge * HARTREE_TO_KCAL_MOL},
        "bridge_interpretation": {
            "name": "bonded_sigma_to_cut_single_sigma_coupling",
            "status": "state-path bridge inferred from the source state definitions",
            "DSI3": "bonded sigma and cut-single sigma belong to one delocalized sigma system",
            "PDSI": "bonded sigma and cut-single sigma are separate masked systems",
        },
        "corrected_sum_hartree": corrected_sum,
        "closures_hartree": {
            "pi_sigma_equations_5_12_to_5_16": pi_sigma_closure,
            "three_effect_sum_to_E_G_minus_E_FUL": three_effect_closure,
            "three_effect_plus_bridge_to_E_G_minus_E_FUL": corrected_closure,
        },
        "pi_sigma_equation_components_hartree": {
            "direct_total": direct,
            "pi_response": pi_response,
            "sigma_response": sigma_response,
            "sum": pi_sigma_equation_sum,
        },
        "state_checks": state_checks,
        "state_definitions": {
            name: {"group_sizes": state["group_sizes"], "roots": roots}
            for (name, (_, roots)), state in zip(definitions.items(), states.values(), strict=True)
        },
        "density_idempotency_diagnostics": {
            name: float(state["density_physical_metric_idempotency_residual"])
            for name, state in states.items()
        },
        "maximum_cross_group_density_norm": {
            name: maximum_cross_group_density(state) for name, state in states.items()
        },
        "physical_projector_scaffold_diagnostic": {
            "disposition": scaffold["disposition"],
            "FUD_energy_hartree": float(internal["diagnostic_energy_hartree"]),
        },
        "symmetric_lowdin_control": {
            "status": "parameter_free_physical_metric_control",
            "state_energies_hartree": orthogonal_energies,
            **orthogonal_cycle,
            "effects_kcal_mol": {
                key: value * HARTREE_TO_KCAL_MOL
                for key, value in orthogonal_cycle["effects_hartree"].items()
            },
            "density_idempotency_diagnostics": {
                name: float(state["density_physical_metric_idempotency_residual"])
                for name, state in orthogonal_states.items()
            },
            "maximum_cross_group_density_norm": {
                name: maximum_cross_group_density(state)
                for name, state in orthogonal_states.items()
            },
        },
        "local_plane_reflection_lowdin_control": {
            "status": "parameter_free_local_fragment_plane_control",
            "scaffold_disposition": local_plane_scaffold["disposition"],
            "scaffold_failed_checks": [
                name
                for name, passed in local_plane_scaffold["checks"].items()
                if not passed
            ],
            "fragment_post_kost_reflection_eigenvalues": {
                fragment: local_plane_scaffold["fragments"][fragment][
                    "post_kost_reflection_eigenvalues"
                ]
                for fragment in ("A", "B", "C")
            },
            "column_type_counts_by_fragment": {
                fragment: {
                    orbital_type: sum(
                        owner == fragment and kind == orbital_type
                        for owner, kind in zip(
                            local_plane_internal["column_fragments"],
                            local_plane_internal["column_types"],
                            strict=True,
                        )
                    )
                    for orbital_type in ("pi", "sigma", "mixed")
                }
                for fragment in ("A", "B", "C")
            },
            "state_energies_hartree": local_plane_energies,
            **local_plane_cycle,
            "effects_kcal_mol": {
                key: value * HARTREE_TO_KCAL_MOL
                for key, value in local_plane_cycle["effects_hartree"].items()
            },
            "density_idempotency_diagnostics": {
                name: float(state["density_physical_metric_idempotency_residual"])
                for name, state in local_plane_states.items()
            },
            "ground_partition_diagnostics": ground_partition_diagnostics(
                ground, local_plane_states["FUD"], local_plane_overlap
            ),
        },
        "atomic_normal_pi_sigma_fud_control": {
            "status": "parameter_free_sto3g_atomic_normal_subspace_control",
            "state_energy_hartree": atomic_fud_energy,
            "E_G_minus_E_FUD_hartree": energies["G"] - atomic_fud_energy,
            "E_G_minus_E_FUD_kcal_mol": (
                energies["G"] - atomic_fud_energy
            ) * HARTREE_TO_KCAL_MOL,
            "density_physical_metric_idempotency_residual": float(
                atomic_fud["density_physical_metric_idempotency_residual"]
            ),
            "ground_partition_diagnostics": ground_partition_diagnostics(
                ground, atomic_fud, overlap
            ),
        },
        "atomic_pi_lfmo_sigma_state_family": {
            "status": "parameter_free_physical_metric_candidate",
            "checks": hybrid_checks,
            "state_energies_hartree": hybrid_energies,
            **hybrid_cycle,
            "effects_kcal_mol": {
                key: value * HARTREE_TO_KCAL_MOL
                for key, value in hybrid_cycle["effects_hartree"].items()
            },
            "density_idempotency_diagnostics": {
                name: float(state["density_physical_metric_idempotency_residual"])
                for name, state in hybrid_states.items()
            },
            "dual_density_reconstruction_differences": (
                hybrid_dual_density_differences
            ),
            "maximum_cross_group_density_norm": {
                name: maximum_cross_group_density(state)
                for name, state in hybrid_states.items()
            },
            "ground_partition_diagnostics": hybrid_ground_diagnostics,
            "pi_sigma_direct_response_decomposition": (
                physical_pi_sigma_components
            ),
            "three_effect_release_decompositions": physical_release_components,
            "interpretation_boundary": {
                "variational_sign": "E_G-E_constrained is nonpositive for a physical idempotent RHF determinant",
                "source_destabilization_sign_reproduced": False,
                "production_label_allowed": False,
            },
        },
        "source": {
            "pdf_sha256": "07AADF5E25967616C4076C8B732EBB17E9E179F31C6546B6EB06D46E96D4A85D",
            "pi_sigma_equations": ["5-12", "5-13", "5-14", "5-15", "5-16"],
            "sigma_sigma_expression": "E_PDSI-E_FUL",
            "printed_pages": [138, 139, 140, 141, 143, 144, 145, 146, 147],
        },
        "provenance": {"git_commit": git_commit(), "config_sha256": canonical_digest(master)},
        "boundaries": master["boundaries"],
    }


def render_markdown(report: dict[str, Any]) -> str:
    candidate = report["atomic_pi_lfmo_sigma_state_family"]
    direct_response = candidate["pi_sigma_direct_response_decomposition"]
    releases = candidate["three_effect_release_decompositions"]
    dual_density = candidate["dual_density_reconstruction_differences"]
    maximum_dual_energy = max(
        value["energy_hartree"] for value in dual_density.values()
    )
    maximum_dual_density = max(
        value["density_relative_frobenius"] for value in dual_density.values()
    )
    lines = [
        "# Gate 0 Chapter 5 three-effect reconstruction", "",
        f"- Disposition: **{report['disposition']}**",
        f"- Calculation complete: `{report['calculation_complete']}`",
        f"- Physical-scale resolution: `{report['physical_scale_resolution_pass']}`",
        f"- Three effects alone reconstruct E_G-E_FUL: `{report['three_effects_reconstruct_requested_total']}`",
        f"- Four-term state path reconstructs E_G-E_FUL: `{report['four_term_state_path_reconstructs_requested_total']}`",
        "",
        "## Physical-metric candidate", "",
        "| Effect | Expression | Eh | kcal/mol |", "|---|---|---:|---:|",
    ]
    expressions = {"pi_pi": "E_FUD-E_DSI3", "pi_sigma": "E_G-E_FUD", "sigma_sigma": "E_PDSI-E_FUL"}
    for key, value in candidate["effects_hartree"].items():
        lines.append(
            f"| {key} | {expressions[key]} | {value:.12f} | "
            f"{candidate['effects_kcal_mol'][key]:.6f} |"
        )
    lines.extend([
        "",
        f"- Bridge E_DSI3-E_PDSI: `{candidate['bridge_hartree']:.12f} Eh`",
        f"- Four-term closure residual: `{candidate['four_term_closure_hartree']:.3e} Eh`",
        "- Bridge meaning: coupling the bonded-sigma and cut-single-sigma systems; it includes restoration of the cut covalent bonds.",
        "- All physical-candidate densities are idempotent in the original AO metric.",
        f"- Dual density-construction maximum energy difference: `{maximum_dual_energy:.3e} Eh`.",
        f"- Dual density-construction maximum relative density difference: `{maximum_dual_density:.3e}`.",
        "- Variational boundary: E_G-E_constrained is nonpositive and cannot reproduce a nonvariational destabilization sign.",
        "",
        "## Alternative same-Hamiltonian pi-sigma route", "",
        "| Component | Eh | kcal/mol |", "|---|---:|---:|",
        f"| Direct pi-sigma | {direct_response['direct_total_hartree']:.12f} | {direct_response['direct_total_hartree'] * HARTREE_TO_KCAL_MOL:.6f} |",
        f"| Pi response | {direct_response['pi_response_hartree']:.12f} | {direct_response['pi_response_hartree'] * HARTREE_TO_KCAL_MOL:.6f} |",
        f"| Sigma response | {direct_response['sigma_response_hartree']:.12f} | {direct_response['sigma_response_hartree'] * HARTREE_TO_KCAL_MOL:.6f} |",
        f"| Component sum | {direct_response['component_sum_hartree']:.12f} | {direct_response['component_sum_hartree'] * HARTREE_TO_KCAL_MOL:.6f} |",
        f"| E_G-E_FUD | {direct_response['endpoint_hartree']:.12f} | {direct_response['endpoint_hartree'] * HARTREE_TO_KCAL_MOL:.6f} |",
        "",
        f"- Direct-component sign: `{direct_response['direct_component_sign']}`.",
        f"- Direct one-electron part: `{direct_response['direct_one_electron_hartree'] * HARTREE_TO_KCAL_MOL:.6f} kcal/mol`.",
        f"- Direct two-electron part: `{direct_response['direct_two_electron_hartree'] * HARTREE_TO_KCAL_MOL:.6f} kcal/mol`.",
        f"- Direct intra-fragment part: `{direct_response['direct_intrafragment_hartree'] * HARTREE_TO_KCAL_MOL:.6f} kcal/mol`.",
        f"- Direct inter-fragment part: `{direct_response['direct_interfragment_hartree'] * HARTREE_TO_KCAL_MOL:.6f} kcal/mol`.",
        f"- Identity closure residual: `{direct_response['closure_residual_hartree']:.3e} Eh`.",
        "- This route keeps the RHF Hamiltonian fixed. A positive direct component may be called directly destabilizing only at component level; it is not the source total destabilization label.",
        "",
        "## Unified physical release decomposition", "",
        "| Effect | Direct cross-group | Group response | Endpoint | Closure (Eh) |", "|---|---:|---:|---:|---:|",
    ])
    for effect in ("pi_pi", "pi_sigma", "sigma_sigma"):
        release = releases[effect]
        lines.append(
            f"| {effect} | {release['direct_cross_group_hartree'] * HARTREE_TO_KCAL_MOL:.6f} | "
            f"{release['response_hartree'] * HARTREE_TO_KCAL_MOL:.6f} | "
            f"{release['endpoint_hartree'] * HARTREE_TO_KCAL_MOL:.6f} | "
            f"{release['closure_residual_hartree']:.3e} |"
        )
    lines.extend([
        "",
        "Positive entries are physical energy components, not source-equivalent total destabilization labels.",
        "ADR-0014 classifies a positive response total only as an induced_subsystem_response_penalty.",
        "",
        "## Source-metric equation branch", "",
        f"- Physical magnitude screen: `{report['physical_magnitude_screen_pass']}`",
        f"- Pi-sigma equations 5-12 to 5-16 closure: `{report['closures_hartree']['pi_sigma_equations_5_12_to_5_16']:.3e} Eh`",
        "- The source-metric branch remains quarantined because its constrained density is not idempotent in the original AO metric and its energy scale is excessive.",
        "",
        "## Route decision", "",
        "No further physical endpoint sign search is authorized for this fixed cut. Exact replication of a positive source total must remain an explicitly nonvariational source-definition branch.",
        "",
        "All values are nonproduction diagnostics. No stabilization label is generated.", "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    report = run(load_yaml(args.config))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(json_safe(report), indent=2, sort_keys=True), encoding="utf-8")
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(
        f"{report['disposition']}: three_effects_reconstruct="
        f"{report['three_effects_reconstruct_requested_total']}, "
        f"bridge={report['bridge']['hartree']:.6e} Eh"
    )
    return 0 if report["calculation_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
