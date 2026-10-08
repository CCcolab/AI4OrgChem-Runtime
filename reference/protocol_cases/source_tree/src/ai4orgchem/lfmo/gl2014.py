"""Independent source-aligned GL(2014) conditional-state helpers.

The implementation follows the three public conditions stated for the
butadiene GL(2014) geometry: mask cross-fragment pi-AO Fock and overlap
elements, remove cross-fragment exact-exchange integrals, and evaluate
geometry changes from the resulting corrected energy.  It does not use or
translate the monograph's program code.
"""

from __future__ import annotations

from typing import Any, Iterable

import numpy as np


def pi_ao_indices(molecule: Any, atom_indices: Iterable[int]) -> np.ndarray:
    """Return odd-under-xy-reflection AOs on the selected atoms.

    P08 keeps every geometry in the xy plane.  For spherical Gaussian bases,
    pz, dxz and dyz functions are the pi AOs under reflection through that
    plane.  The label-based rule deliberately includes polarization d AOs.
    """

    atoms = {int(value) for value in atom_indices}
    selected: list[int] = []
    for index, label in enumerate(molecule.ao_labels(fmt=False)):
        atom = int(label[0])
        if atom not in atoms:
            continue
        text = "".join(str(value).lower().replace(" ", "") for value in label[2:])
        if "pz" in text or "dxz" in text or "dyz" in text:
            selected.append(index)
    if not selected:
        raise ValueError("no pi AOs were identified for the selected fragment")
    return np.asarray(selected, dtype=int)


def zero_cross_blocks(matrix: np.ndarray, left: np.ndarray, right: np.ndarray) -> np.ndarray:
    """Return a symmetric copy with the selected left-right blocks zeroed."""

    result = np.asarray(matrix, dtype=float).copy()
    result[np.ix_(left, right)] = 0.0
    result[np.ix_(right, left)] = 0.0
    return 0.5 * (result + result.T)


def cross_fragment_exchange(
    mean_field: Any,
    density: np.ndarray,
    left: np.ndarray,
    right: np.ndarray,
) -> np.ndarray:
    """Build the exact-exchange matrix terms coupling the two pi fragments."""

    dm = np.asarray(density, dtype=float)
    dm_left = np.zeros_like(dm)
    dm_right = np.zeros_like(dm)
    dm_left[np.ix_(left, left)] = dm[np.ix_(left, left)]
    dm_right[np.ix_(right, right)] = dm[np.ix_(right, right)]
    _, exchange_from_left = mean_field.get_jk(
        mean_field.mol, dm_left, hermi=1, with_j=False, with_k=True
    )
    _, exchange_from_right = mean_field.get_jk(
        mean_field.mol, dm_right, hermi=1, with_j=False, with_k=True
    )
    cross = np.zeros_like(dm)
    cross[np.ix_(left, left)] = np.asarray(exchange_from_right)[np.ix_(left, left)]
    cross[np.ix_(right, right)] = np.asarray(exchange_from_left)[np.ix_(right, right)]
    return 0.5 * (cross + cross.T)


def hybrid_coefficient(mean_field: Any) -> float:
    """Return and validate the global exact-exchange fraction."""

    omega, alpha, hybrid = mean_field._numint.rsh_and_hybrid_coeff(
        mean_field.xc, spin=mean_field.mol.spin
    )
    if abs(float(omega)) > 1.0e-14 or abs(float(alpha) - float(hybrid)) > 1.0e-14:
        raise ValueError("P08 GL(2014) v0.1 supports only global hybrid functionals")
    return float(hybrid)


def gl2014_energy(
    mean_field: Any,
    density: np.ndarray,
    hcore: np.ndarray,
    left: np.ndarray,
    right: np.ndarray,
) -> tuple[float, float, np.ndarray, np.ndarray]:
    """Return corrected GL energy, correction, physical veff and cross K."""

    dm = np.asarray(density, dtype=float)
    veff = mean_field.get_veff(mean_field.mol, dm)
    normal_total = float(mean_field.energy_tot(dm, h1e=hcore, vhf=veff))
    cross_k = cross_fragment_exchange(mean_field, dm, left, right)
    correction = 0.25 * hybrid_coefficient(mean_field) * float(
        np.einsum("ij,ji->", dm, cross_k, optimize=True)
    )
    return normal_total + correction, correction, np.asarray(veff), cross_k


def occupied_pi_audit(
    coefficients: np.ndarray,
    occupations: np.ndarray,
    modified_overlap: np.ndarray,
    left: np.ndarray,
    right: np.ndarray,
) -> dict[str, Any]:
    """Audit occupied pi localization in the masked metric."""

    occupied = np.asarray(coefficients)[:, np.asarray(occupations) > 0.0]
    rows: list[dict[str, float | str | int]] = []
    left_count = 0
    right_count = 0
    mixed_count = 0
    for index in range(occupied.shape[1]):
        vector = occupied[:, index]
        left_weight = float(vector[left] @ modified_overlap[np.ix_(left, left)] @ vector[left])
        right_weight = float(vector[right] @ modified_overlap[np.ix_(right, right)] @ vector[right])
        pi_weight = left_weight + right_weight
        if pi_weight < 0.5:
            role = "sigma"
        elif left_weight >= 0.95 * pi_weight:
            role = "pi_left"
            left_count += 1
        elif right_weight >= 0.95 * pi_weight:
            role = "pi_right"
            right_count += 1
        else:
            role = "pi_mixed"
            mixed_count += 1
        rows.append(
            {
                "occupied_index": index,
                "left_pi_weight": left_weight,
                "right_pi_weight": right_weight,
                "total_pi_weight": pi_weight,
                "role": role,
            }
        )
    return {
        "left_occupied_pi_count": left_count,
        "right_occupied_pi_count": right_count,
        "mixed_occupied_pi_count": mixed_count,
        "orbitals": rows,
    }


def run_gl2014_scf(
    mean_field: Any,
    fragment_left_atoms: Iterable[int],
    fragment_right_atoms: Iterable[int],
    *,
    initial_density: np.ndarray | None = None,
    maximum_cycles: int = 160,
    density_tolerance: float = 2.0e-8,
    energy_tolerance: float = 1.0e-10,
    density_diis_start_cycle: int = 3,
    density_diis_space: int = 10,
    damping: float = 0.20,
) -> dict[str, Any]:
    """Converge the planar butadiene GL(2014) conditional density."""

    from pyscf import lib, scf

    molecule = mean_field.mol
    physical_overlap = np.asarray(mean_field.get_ovlp(), dtype=float)
    hcore = np.asarray(mean_field.get_hcore(), dtype=float)
    left = pi_ao_indices(molecule, fragment_left_atoms)
    right = pi_ao_indices(molecule, fragment_right_atoms)
    modified_overlap = zero_cross_blocks(physical_overlap, left, right)
    overlap_eigenvalues = np.linalg.eigvalsh(modified_overlap)
    if float(np.min(overlap_eigenvalues)) <= 0.0:
        raise ValueError("GL(2014) modified AO overlap is not positive definite")

    if initial_density is None:
        density = np.asarray(mean_field.get_init_guess(key="minao"), dtype=float)
    else:
        density = np.asarray(initial_density, dtype=float).copy()
    density = 0.5 * (density + density.T)

    density_diis = lib.diis.DIIS()
    density_diis.space = int(density_diis_space)
    hybrid = hybrid_coefficient(mean_field)
    history: list[dict[str, float]] = []
    previous_energy: float | None = None
    converged = False
    final_coefficients: np.ndarray | None = None
    final_occupations: np.ndarray | None = None
    final_energies: np.ndarray | None = None
    final_correction = float("nan")

    for cycle in range(1, int(maximum_cycles) + 1):
        veff = mean_field.get_veff(molecule, density)
        cross_k = cross_fragment_exchange(mean_field, density, left, right)
        physical_fock = hcore + np.asarray(veff) + 0.5 * hybrid * cross_k
        modified_fock = zero_cross_blocks(physical_fock, left, right)
        orbital_energies, coefficients = scf.hf.eig(modified_fock, modified_overlap)
        occupations = mean_field.get_occ(orbital_energies, coefficients)
        candidate = np.asarray(mean_field.make_rdm1(coefficients, occupations), dtype=float)
        candidate = 0.5 * (candidate + candidate.T)
        energy, correction, _, _ = gl2014_energy(
            mean_field, candidate, hcore, left, right
        )
        density_residual = float(
            np.linalg.norm(candidate - density, ord="fro")
            / max(float(np.linalg.norm(candidate, ord="fro")), 1.0)
        )
        energy_change = (
            abs(energy - previous_energy) if previous_energy is not None else float("inf")
        )
        history.append(
            {
                "cycle": float(cycle),
                "energy_hartree": energy,
                "energy_change_hartree": energy_change,
                "density_residual": density_residual,
            }
        )
        final_coefficients = coefficients
        final_occupations = occupations
        final_energies = orbital_energies
        final_correction = correction
        if density_residual <= density_tolerance and energy_change <= energy_tolerance:
            density = candidate
            converged = True
            break

        error = candidate - density
        if cycle >= int(density_diis_start_cycle):
            updated = density_diis.update(candidate, xerr=error)
        else:
            updated = (1.0 - damping) * candidate + damping * density
        density = 0.5 * (np.asarray(updated) + np.asarray(updated).T)
        previous_energy = energy

    if final_coefficients is None or final_occupations is None or final_energies is None:
        raise RuntimeError("GL(2014) conditional SCF did not execute")

    final_energy, final_correction, _, final_cross_k = gl2014_energy(
        mean_field, density, hcore, left, right
    )
    modified_electrons = float(np.einsum("ij,ji->", density, modified_overlap))
    physical_electrons = float(np.einsum("ij,ji->", density, physical_overlap))
    audit = occupied_pi_audit(
        final_coefficients, final_occupations, modified_overlap, left, right
    )
    return {
        "converged": converged,
        "cycles": len(history),
        "total_energy_hartree": final_energy,
        "removed_exchange_energy_correction_hartree": final_correction,
        "density": density,
        "mo_coefficients": final_coefficients,
        "mo_energies_hartree": final_energies,
        "mo_occupations": final_occupations,
        "left_pi_ao_indices": left,
        "right_pi_ao_indices": right,
        "left_pi_ao_count": int(left.size),
        "right_pi_ao_count": int(right.size),
        "modified_overlap_minimum_eigenvalue": float(np.min(overlap_eigenvalues)),
        "modified_overlap_condition_number": float(np.linalg.cond(modified_overlap)),
        "modified_metric_electron_count": modified_electrons,
        "physical_metric_electron_count": physical_electrons,
        "cross_exchange_matrix_frobenius_norm": float(np.linalg.norm(final_cross_k, ord="fro")),
        "hybrid_exact_exchange_fraction": hybrid,
        "occupied_pi_audit": audit,
        "history": history,
    }

