"""Scalable exact-J/K kernel for planar source-2011 conditional states.

This module does not construct P12 molecular geometries or scientific labels.
It implements the R1 engine-equivalence candidate only.  The derivation relies
on a density that is block diagonal in ``sigma + localized pi fragments``.
Under that precondition, the source Figure 8-4 mask changes retained J/K blocks
only through the particular interfragment exchange family X14.  The physical
direct J/K build is therefore corrected with one direct exchange build per pi
fragment, without materializing the four-index AO ERI tensor.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from .p09_ao_classification import interfragment_pi_delete_mask
from .p09_eri_mask import AODescriptor


def _pi_fragment_indices(
    descriptors: Sequence[AODescriptor],
) -> dict[Any, np.ndarray]:
    fragments: dict[Any, list[int]] = {}
    for index, descriptor in enumerate(descriptors):
        if descriptor.kind == "pi":
            fragments.setdefault(descriptor.fragment, []).append(index)
    if not fragments:
        raise ValueError("at least one localized pi fragment is required")
    return {
        fragment: np.asarray(indices, dtype=int)
        for fragment, indices in fragments.items()
    }


def density_block_residual(
    density: np.ndarray, descriptors: Sequence[AODescriptor]
) -> float:
    """Return max forbidden density element for planar localized states.

    Allowed blocks are sigma/sigma and same-fragment pi/pi.  Planar reflection
    symmetry makes sigma/pi blocks zero; the conditional matrix mask makes
    different-fragment pi/pi blocks zero.
    """

    values = np.asarray(density, dtype=float)
    size = len(descriptors)
    if values.shape != (size, size):
        raise ValueError("density dimensions must match AO descriptors")
    allowed = np.zeros((size, size), dtype=bool)
    for i, left in enumerate(descriptors):
        for j, right in enumerate(descriptors):
            allowed[i, j] = (
                left.kind == right.kind == "sigma"
                or (
                    left.kind == right.kind == "pi"
                    and left.fragment == right.fragment
                )
            )
    return float(np.max(np.abs(values[~allowed]), initial=0.0))


def project_planar_localized_density(
    density: np.ndarray, descriptors: Sequence[AODescriptor]
) -> np.ndarray:
    """Project an AO density onto sigma and same-fragment pi blocks."""

    values = np.asarray(density, dtype=float)
    size = len(descriptors)
    if values.shape != (size, size):
        raise ValueError("density dimensions must match AO descriptors")
    result = np.zeros_like(values)
    sigma = np.asarray(
        [i for i, item in enumerate(descriptors) if item.kind == "sigma"],
        dtype=int,
    )
    if sigma.size:
        result[np.ix_(sigma, sigma)] = values[np.ix_(sigma, sigma)]
    for indices in _pi_fragment_indices(descriptors).values():
        result[np.ix_(indices, indices)] = values[np.ix_(indices, indices)]
    return 0.5 * (result + result.T)


def direct_source2011_restricted_jk(
    mean_field: Any,
    density: np.ndarray,
    descriptors: Sequence[AODescriptor],
    *,
    block_tolerance: float = 1.0e-12,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Return source-2011 masked J/K on retained planar density blocks.

    The returned matrices are suitable for forming a conditional Fock matrix,
    after applying the usual interfragment-pi two-index mask.  Cross-fragment
    pi output blocks are explicitly zeroed because the conditional Fock mask
    removes them independently of the ERI rule.
    """

    from pyscf.scf import jk

    dm = np.asarray(density, dtype=float)
    size = len(descriptors)
    if dm.shape != (size, size):
        raise ValueError("density dimensions must match AO descriptors")
    residual = density_block_residual(dm, descriptors)
    if residual > float(block_tolerance):
        raise ValueError(
            "direct source-2011 J/K requires a planar block-diagonal density; "
            f"observed residual {residual:.3e}"
        )

    molecule = mean_field.mol
    physical_j, physical_k = jk.get_jk(
        molecule,
        (dm, dm),
        scripts=("ijkl,lk->ij", "ijkl,jk->il"),
        aosym="s8",
        hermi=1,
        verbose=0,
    )
    physical_j = np.asarray(physical_j, dtype=float)
    physical_k = np.asarray(physical_k, dtype=float)

    fragments = _pi_fragment_indices(descriptors)
    fragment_names = tuple(fragments)
    fragment_densities: list[np.ndarray] = []
    for fragment in fragment_names:
        indices = fragments[fragment]
        block = np.zeros_like(dm)
        block[np.ix_(indices, indices)] = dm[np.ix_(indices, indices)]
        fragment_densities.append(block)

    scripts = ["ijkl,jk->il"] * len(fragment_densities)
    fragment_k = jk.get_jk(
        molecule,
        fragment_densities,
        scripts=scripts,
        aosym="s8",
        hermi=1,
        verbose=0,
    )
    fragment_k_values = np.asarray(fragment_k, dtype=float)
    if fragment_k_values.ndim == 2:
        fragment_k_values = fragment_k_values[None, :, :]

    deleted_k = np.zeros_like(physical_k)
    for q_position, q_fragment in enumerate(fragment_names):
        contribution = fragment_k_values[q_position]
        for p_fragment, p_indices in fragments.items():
            if p_fragment == q_fragment:
                continue
            deleted_k[np.ix_(p_indices, p_indices)] += contribution[
                np.ix_(p_indices, p_indices)
            ]

    source_j = physical_j.copy()
    source_k = physical_k - deleted_k
    cross_pi = interfragment_pi_delete_mask(descriptors)
    source_j[cross_pi] = 0.0
    source_k[cross_pi] = 0.0
    return source_j, source_k, {
        "implementation": "direct_JK_plus_exact_X14_fragment_exchange_subtraction",
        "density_block_residual": residual,
        "pi_fragment_count": len(fragment_names),
        "full_four_index_eri_materialized": False,
        "density_fitting_used": False,
        "deleted_exchange_frobenius_norm": float(np.linalg.norm(deleted_k)),
    }
