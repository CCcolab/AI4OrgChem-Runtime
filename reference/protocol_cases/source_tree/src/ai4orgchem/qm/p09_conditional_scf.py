"""Fixed-geometry conditional RKS kernel for the frozen P09 source protocol."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from .p09_ao_classification import (
    apply_interfragment_pi_matrix_mask,
    interfragment_pi_delete_mask,
)
from .p09_energy_assembly import (
    apply_eri_tensor_mask,
    apply_eri_tensor_mask_inplace_by_category,
    restricted_jk,
)
from .p09_eri_mask import AODescriptor


def generalized_commutator(
    fock: np.ndarray, density: np.ndarray, overlap: np.ndarray
) -> np.ndarray:
    """Return the AO generalized SCF commutator ``F D S - S D F``."""

    return fock @ density @ overlap - overlap @ density @ fock


def closed_shell_idempotency_residual(
    density: np.ndarray, overlap: np.ndarray
) -> float:
    """Return relative ``D S D = 2 D`` residual for a closed-shell density."""

    dm = np.asarray(density, dtype=float)
    residual = dm @ overlap @ dm - 2.0 * dm
    return float(np.linalg.norm(residual, ord="fro") / max(np.linalg.norm(dm, ord="fro"), 1.0))


def _evaluate_density(
    *,
    mean_field: Any,
    density: np.ndarray,
    masked_hcore: np.ndarray,
    masked_overlap: np.ndarray,
    physical_overlap: np.ndarray,
    masked_eri: np.ndarray,
    descriptors: Sequence[AODescriptor],
    exact_exchange_fraction: float,
    optimize_eri_contractions: bool = True,
) -> dict[str, Any]:
    """Evaluate the frozen masked hybrid functional at one density."""

    molecule = mean_field.mol
    grid_electrons, semilocal_xc_energy, xc_potential = mean_field._numint.nr_rks(
        molecule,
        mean_field.grids,
        mean_field.xc,
        density,
        hermi=1,
        max_memory=mean_field.max_memory,
    )
    coulomb, exchange = restricted_jk(
        density, masked_eri, optimize=optimize_eri_contractions
    )
    raw_fock = (
        masked_hcore
        + coulomb
        - 0.5 * exact_exchange_fraction * exchange
        + np.asarray(xc_potential, dtype=float)
    )
    conditional_fock = apply_interfragment_pi_matrix_mask(raw_fock, descriptors)

    one_electron = float(np.einsum("pq,qp->", masked_hcore, density, optimize=True))
    coulomb_energy = 0.5 * float(np.einsum("pq,qp->", coulomb, density, optimize=True))
    exact_exchange_energy = -0.25 * exact_exchange_fraction * float(
        np.einsum("pq,qp->", exchange, density, optimize=True)
    )
    electronic_energy = (
        one_electron
        + coulomb_energy
        + exact_exchange_energy
        + float(semilocal_xc_energy)
    )
    return {
        "fock": conditional_fock,
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
        "exact_exchange_energy": exact_exchange_energy,
        "semilocal_xc_energy": float(semilocal_xc_energy),
        "electronic_energy": electronic_energy,
        "total_energy": electronic_energy + float(molecule.energy_nuc()),
    }


def run_p09_conditional_rks(
    mean_field: Any,
    descriptors: Sequence[AODescriptor],
    source_entries: Sequence[Mapping[str, Any]],
    *,
    initial_density: np.ndarray,
    maximum_cycles: int = 100,
    density_tolerance: float = 2.0e-8,
    energy_tolerance: float = 1.0e-10,
    diis_start_cycle: int = 2,
    diis_space: int = 8,
    damping_cycles: int = 2,
    damping: float = 0.20,
    memory_controlled_eri: bool = False,
) -> dict[str, Any]:
    """Converge the P09 conditional RKS density at one fixed geometry.

    The kernel independently applies the frozen h/S/F cross-fragment pi mask
    and the complete Figure 8-4 ERI mask.  It neither optimizes geometry nor
    compares against the published VDE/ADE values.
    """

    from pyscf import lib, scf

    molecule = mean_field.mol
    physical_overlap = np.asarray(mean_field.get_ovlp(), dtype=float)
    physical_hcore = np.asarray(mean_field.get_hcore(), dtype=float)
    masked_overlap = apply_interfragment_pi_matrix_mask(physical_overlap, descriptors)
    masked_hcore = apply_interfragment_pi_matrix_mask(physical_hcore, descriptors)
    overlap_eigenvalues = np.linalg.eigvalsh(masked_overlap)
    if float(np.min(overlap_eigenvalues)) <= 0.0:
        raise ValueError("P09 masked AO overlap is not positive definite")

    physical_eri = np.asarray(molecule.intor("int2e_sph", aosym="s1"), dtype=float)
    physical_eri_count = int(physical_eri.size)
    if memory_controlled_eri:
        masked_eri = physical_eri
        deleted_eri_count = apply_eri_tensor_mask_inplace_by_category(
            masked_eri, descriptors, source_entries
        )
        eri_storage_mode = "single_tensor_inplace_category_mask"
    else:
        masked_eri, eri_delete_mask = apply_eri_tensor_mask(
            physical_eri, descriptors, source_entries
        )
        deleted_eri_count = int(np.count_nonzero(eri_delete_mask))
        del eri_delete_mask
        eri_storage_mode = "reference_copy_plus_boolean_mask"
    if masked_eri is not physical_eri:
        del physical_eri

    omega, alpha, hybrid = mean_field._numint.rsh_and_hybrid_coeff(
        mean_field.xc, spin=molecule.spin
    )
    if abs(float(omega)) > 1.0e-14 or abs(float(alpha) - float(hybrid)) > 1.0e-14:
        raise ValueError("P09 v0.1 supports only a global hybrid functional")
    exact_exchange_fraction = float(hybrid)

    if getattr(mean_field.grids, "coords", None) is None:
        mean_field.grids.build(with_non0tab=True)

    density = np.asarray(initial_density, dtype=float).copy()
    density = 0.5 * (density + density.T)
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
            masked_eri=masked_eri,
            descriptors=descriptors,
            exact_exchange_fraction=exact_exchange_fraction,
            optimize_eri_contractions=not memory_controlled_eri,
        )
        fock = np.asarray(evaluated["fock"], dtype=float)
        commutator = generalized_commutator(fock, density, masked_overlap)
        if cycle >= int(diis_start_cycle):
            diagonalization_fock = np.asarray(
                fock_diis.update(fock, xerr=commutator), dtype=float
            )
        else:
            diagonalization_fock = fock

        orbital_energies, coefficients = scf.hf.eig(
            diagonalization_fock, masked_overlap
        )
        occupations = mean_field.get_occ(orbital_energies, coefficients)
        candidate = np.asarray(mean_field.make_rdm1(coefficients, occupations), dtype=float)
        candidate = 0.5 * (candidate + candidate.T)
        if cycle <= int(damping_cycles) and 0.0 < damping < 1.0:
            updated_density = (1.0 - damping) * candidate + damping * density
        else:
            updated_density = candidate
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
        history.append(
            {
                "cycle": float(cycle),
                "total_energy_hartree": float(evaluated["total_energy"]),
                "energy_change_hartree": energy_change,
                "density_residual": density_residual,
                "commutator_frobenius_norm": float(
                    np.linalg.norm(commutator, ord="fro")
                ),
                "masked_metric_electron_count": float(
                    evaluated["masked_metric_electron_count"]
                ),
                "physical_metric_electron_count": float(
                    evaluated["physical_metric_electron_count"]
                ),
            }
        )
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
        raise RuntimeError("P09 conditional RKS did not execute")

    final = _evaluate_density(
        mean_field=mean_field,
        density=density,
        masked_hcore=masked_hcore,
        masked_overlap=masked_overlap,
        physical_overlap=physical_overlap,
        masked_eri=masked_eri,
        descriptors=descriptors,
        exact_exchange_fraction=exact_exchange_fraction,
        optimize_eri_contractions=not memory_controlled_eri,
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
        "deleted_eri_count": deleted_eri_count,
        "total_eri_count": physical_eri_count,
        "deleted_eri_fraction": deleted_eri_count / physical_eri_count,
        "eri_storage_mode": eri_storage_mode,
        "exact_exchange_fraction": exact_exchange_fraction,
        "final_commutator_frobenius_norm": float(
            np.linalg.norm(final_commutator, ord="fro")
        ),
        "closed_shell_idempotency_relative_residual": closed_shell_idempotency_residual(
            density, masked_overlap
        ),
        "occupied_virtual_gap_hartree": occupied_virtual_gap,
        "history": history,
    }
