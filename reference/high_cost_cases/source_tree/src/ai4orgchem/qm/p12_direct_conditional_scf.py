"""Scalable fixed-geometry source-2011 conditional RKS for P12.

This module combines the independently validated direct J/K decomposition
with the source h/S/F interfragment-pi masks.  It does not optimize geometry
and does not assemble a CESE verdict.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from .p09_ao_classification import (
    apply_interfragment_pi_matrix_mask,
    interfragment_pi_delete_mask,
)
from .p09_conditional_scf import (
    closed_shell_idempotency_residual,
    generalized_commutator,
)
from .p09_eri_mask import AODescriptor
from .p12_direct_source2011 import (
    density_block_residual,
    direct_source2011_restricted_jk,
    project_planar_localized_density,
)


def _evaluate_density(
    *,
    mean_field: Any,
    density: np.ndarray,
    masked_hcore: np.ndarray,
    masked_overlap: np.ndarray,
    physical_overlap: np.ndarray,
    descriptors: Sequence[AODescriptor],
    exact_exchange_fraction: float,
) -> dict[str, Any]:
    molecule = mean_field.mol
    grid_electrons, semilocal_xc_energy, xc_potential = mean_field._numint.nr_rks(
        molecule,
        mean_field.grids,
        mean_field.xc,
        density,
        hermi=1,
        max_memory=mean_field.max_memory,
    )
    coulomb, exchange, jk_metadata = direct_source2011_restricted_jk(
        mean_field,
        density,
        descriptors,
    )
    raw_fock = (
        masked_hcore
        + coulomb
        - 0.5 * exact_exchange_fraction * exchange
        + np.asarray(xc_potential, dtype=float)
    )
    fock = apply_interfragment_pi_matrix_mask(raw_fock, descriptors)
    one_electron = float(np.einsum("pq,qp->", masked_hcore, density, optimize=True))
    coulomb_energy = 0.5 * float(np.einsum("pq,qp->", coulomb, density, optimize=True))
    exchange_energy = -0.25 * exact_exchange_fraction * float(
        np.einsum("pq,qp->", exchange, density, optimize=True)
    )
    electronic_energy = (
        one_electron + coulomb_energy + exchange_energy + float(semilocal_xc_energy)
    )
    return {
        "fock": fock,
        "raw_fock": raw_fock,
        "coulomb_matrix": coulomb,
        "exchange_matrix": exchange,
        "xc_potential": np.asarray(xc_potential, dtype=float),
        "grid_electron_count": float(grid_electrons),
        "masked_metric_electron_count": float(
            np.einsum("pq,qp->", masked_overlap, density, optimize=True)
        ),
        "physical_metric_electron_count": float(
            np.einsum("pq,qp->", physical_overlap, density, optimize=True)
        ),
        "one_electron_energy": one_electron,
        "coulomb_energy": coulomb_energy,
        "exact_exchange_energy": exchange_energy,
        "semilocal_xc_energy": float(semilocal_xc_energy),
        "electronic_energy": electronic_energy,
        "total_energy": electronic_energy + float(molecule.energy_nuc()),
        "jk_metadata": jk_metadata,
    }


def run_p12_direct_conditional_rks(
    mean_field: Any,
    descriptors: Sequence[AODescriptor],
    *,
    initial_density: np.ndarray,
    maximum_cycles: int = 150,
    density_tolerance: float = 2.0e-8,
    energy_tolerance: float = 1.0e-10,
    diis_start_cycle: int = 2,
    diis_space: int = 10,
    damping_cycles: int = 3,
    damping: float = 0.20,
    cycle_callback: Callable[[dict[str, float]], None] | None = None,
) -> dict[str, Any]:
    """Converge a source-2011 localized conditional state without full ERIs."""

    from pyscf import lib, scf

    molecule = mean_field.mol
    physical_overlap = np.asarray(mean_field.get_ovlp(), dtype=float)
    physical_hcore = np.asarray(mean_field.get_hcore(), dtype=float)
    masked_overlap = apply_interfragment_pi_matrix_mask(physical_overlap, descriptors)
    masked_hcore = apply_interfragment_pi_matrix_mask(physical_hcore, descriptors)
    overlap_eigenvalues = np.linalg.eigvalsh(masked_overlap)
    if float(np.min(overlap_eigenvalues)) <= 0.0:
        raise ValueError("P12 masked AO overlap is not positive definite")

    omega, alpha, hybrid = mean_field._numint.rsh_and_hybrid_coeff(
        mean_field.xc, spin=molecule.spin
    )
    if abs(float(omega)) > 1.0e-14 or abs(float(alpha) - float(hybrid)) > 1.0e-14:
        raise ValueError("P12 direct conditional RKS supports only a global hybrid")
    exact_exchange_fraction = float(hybrid)
    if getattr(mean_field.grids, "coords", None) is None:
        mean_field.grids.build(with_non0tab=True)

    density = project_planar_localized_density(initial_density, descriptors)
    fock_diis = lib.diis.DIIS()
    fock_diis.space = int(diis_space)
    history: list[dict[str, float]] = []
    previous_energy: float | None = None
    converged = False
    final_coefficients: np.ndarray | None = None
    final_energies: np.ndarray | None = None
    final_occupations: np.ndarray | None = None

    for cycle in range(1, int(maximum_cycles) + 1):
        evaluated = _evaluate_density(
            mean_field=mean_field,
            density=density,
            masked_hcore=masked_hcore,
            masked_overlap=masked_overlap,
            physical_overlap=physical_overlap,
            descriptors=descriptors,
            exact_exchange_fraction=exact_exchange_fraction,
        )
        fock = np.asarray(evaluated["fock"], dtype=float)
        commutator = generalized_commutator(fock, density, masked_overlap)
        diagonalization_fock = (
            np.asarray(fock_diis.update(fock, xerr=commutator), dtype=float)
            if cycle >= int(diis_start_cycle)
            else fock
        )
        orbital_energies, coefficients = scf.hf.eig(diagonalization_fock, masked_overlap)
        occupations = mean_field.get_occ(orbital_energies, coefficients)
        candidate = np.asarray(mean_field.make_rdm1(coefficients, occupations), dtype=float)
        candidate = 0.5 * (candidate + candidate.T)
        candidate_block_residual = density_block_residual(candidate, descriptors)
        if candidate_block_residual > 1.0e-10:
            raise RuntimeError(
                "P12 conditional eigensolution left the planar localized density blocks: "
                f"{candidate_block_residual:.3e}"
            )
        candidate = project_planar_localized_density(candidate, descriptors)
        updated_density = (
            (1.0 - damping) * candidate + damping * density
            if cycle <= int(damping_cycles) and 0.0 < damping < 1.0
            else candidate
        )
        updated_density = 0.5 * (updated_density + updated_density.T)

        density_residual = float(
            np.linalg.norm(candidate - density, ord="fro")
            / max(np.linalg.norm(candidate, ord="fro"), 1.0)
        )
        energy_change = (
            abs(float(evaluated["total_energy"]) - previous_energy)
            if previous_energy is not None
            else float("inf")
        )
        history_item = {
            "cycle": float(cycle),
            "total_energy_hartree": float(evaluated["total_energy"]),
            "energy_change_hartree": energy_change,
            "density_residual": density_residual,
            "commutator_frobenius_norm": float(np.linalg.norm(commutator, ord="fro")),
            "density_block_residual": candidate_block_residual,
            "masked_metric_electron_count": float(evaluated["masked_metric_electron_count"]),
            "physical_metric_electron_count": float(
                evaluated["physical_metric_electron_count"]
            ),
        }
        history.append(history_item)
        if cycle_callback is not None:
            cycle_callback(dict(history_item))
        final_coefficients = coefficients
        final_energies = orbital_energies
        final_occupations = occupations
        if density_residual <= density_tolerance and energy_change <= energy_tolerance:
            density = candidate
            converged = True
            break
        previous_energy = float(evaluated["total_energy"])
        density = updated_density

    if final_coefficients is None or final_energies is None or final_occupations is None:
        raise RuntimeError("P12 conditional RKS did not execute")

    final = _evaluate_density(
        mean_field=mean_field,
        density=density,
        masked_hcore=masked_hcore,
        masked_overlap=masked_overlap,
        physical_overlap=physical_overlap,
        descriptors=descriptors,
        exact_exchange_fraction=exact_exchange_fraction,
    )
    final_fock = np.asarray(final["fock"], dtype=float)
    final_commutator = generalized_commutator(final_fock, density, masked_overlap)
    matrix_delete_mask = interfragment_pi_delete_mask(descriptors)
    occupied = np.flatnonzero(np.asarray(final_occupations) > 0.0)
    virtual = np.flatnonzero(np.asarray(final_occupations) == 0.0)
    occupied_virtual_gap = (
        float(np.min(final_energies[virtual]) - np.max(final_energies[occupied]))
        if occupied.size and virtual.size
        else float("nan")
    )
    component_sum = (
        float(final["one_electron_energy"])
        + float(final["coulomb_energy"])
        + float(final["exact_exchange_energy"])
        + float(final["semilocal_xc_energy"])
        + float(molecule.energy_nuc())
    )
    return {
        "converged": converged,
        "cycles": len(history),
        "density": density,
        "mo_coefficients": final_coefficients,
        "mo_energies_hartree": final_energies,
        "mo_occupations": final_occupations,
        "total_energy_hartree": float(final["total_energy"]),
        "electronic_energy_hartree": float(final["electronic_energy"]),
        "nuclear_repulsion_hartree": float(molecule.energy_nuc()),
        "one_electron_energy_hartree": float(final["one_electron_energy"]),
        "coulomb_energy_hartree": float(final["coulomb_energy"]),
        "exact_exchange_energy_hartree": float(final["exact_exchange_energy"]),
        "semilocal_xc_energy_hartree": float(final["semilocal_xc_energy"]),
        "energy_component_closure_residual_hartree": abs(
            component_sum - float(final["total_energy"])
        ),
        "grid_electron_count": float(final["grid_electron_count"]),
        "masked_metric_electron_count": float(final["masked_metric_electron_count"]),
        "physical_metric_electron_count": float(final["physical_metric_electron_count"]),
        "masked_overlap_minimum_eigenvalue": float(np.min(overlap_eigenvalues)),
        "masked_overlap_condition_number": float(np.linalg.cond(masked_overlap)),
        "masked_overlap_cross_pi_max_abs": float(
            np.max(np.abs(masked_overlap[matrix_delete_mask]), initial=0.0)
        ),
        "conditional_fock_cross_pi_max_abs": float(
            np.max(np.abs(final_fock[matrix_delete_mask]), initial=0.0)
        ),
        "exact_exchange_fraction": exact_exchange_fraction,
        "one_electron_matrix_masked": True,
        "final_density_block_residual": density_block_residual(density, descriptors),
        "final_commutator_frobenius_norm": float(np.linalg.norm(final_commutator, ord="fro")),
        "closed_shell_idempotency_relative_residual": closed_shell_idempotency_residual(
            density, masked_overlap
        ),
        "occupied_virtual_gap_hartree": occupied_virtual_gap,
        "jk_metadata": final["jk_metadata"],
        "history": history,
    }
