"""Linear-algebra kernel for non-production conditional fragment SCF."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from .state_masks import apply_symmetric_mask, block_mask, metric_diagnostics


def generalized_symmetric_eigh(
    fock: np.ndarray, metric: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Solve a real symmetric generalized eigenproblem using Cholesky reduction."""

    f = np.asarray(fock, dtype=float)
    s = np.asarray(metric, dtype=float)
    if f.shape != s.shape or f.ndim != 2 or f.shape[0] != f.shape[1]:
        raise ValueError("fock and metric must be matching square matrices")
    diagnostics = metric_diagnostics(s)
    if not diagnostics["positive_definite"]:
        raise ValueError("metric must be symmetric positive definite")
    lower = np.linalg.cholesky(0.5 * (s + s.T))
    inverse_lower = np.linalg.solve(lower, np.eye(lower.shape[0]))
    orthogonal_fock = inverse_lower @ (0.5 * (f + f.T)) @ inverse_lower.T
    energies, vectors = np.linalg.eigh(orthogonal_fock)
    coefficients = inverse_lower.T @ vectors
    return energies, coefficients


def grouped_generalized_eigh(
    fock: np.ndarray,
    metric: np.ndarray,
    group_sizes: Sequence[int],
) -> dict[str, Any]:
    """Apply the source-shaped partition mask and solve each retained block."""

    sizes = [int(value) for value in group_sizes]
    mask = block_mask(sizes)
    masked_fock = apply_symmetric_mask(fock, mask)
    masked_metric = apply_symmetric_mask(metric, mask)
    energies: list[np.ndarray] = []
    transform = np.zeros_like(masked_fock)
    offset = 0
    block_residuals: list[float] = []
    for size in sizes:
        region = slice(offset, offset + size)
        block_energies, block_vectors = generalized_symmetric_eigh(
            masked_fock[region, region], masked_metric[region, region]
        )
        energies.append(block_energies)
        transform[region, region] = block_vectors
        residual = (
            masked_fock[region, region] @ block_vectors
            - masked_metric[region, region]
            @ block_vectors
            @ np.diag(block_energies)
        )
        block_residuals.append(
            float(
                np.linalg.norm(residual, ord="fro")
                / max(float(np.linalg.norm(masked_fock[region, region], ord="fro")), 1.0)
            )
        )
        offset += size
    return {
        "energies": np.concatenate(energies),
        "transform": transform,
        "mask": mask,
        "masked_fock": masked_fock,
        "masked_metric": masked_metric,
        "metric_diagnostics": metric_diagnostics(masked_metric),
        "maximum_block_generalized_residual": max(block_residuals, default=0.0),
    }


def fixed_group_occupations(
    group_sizes: Sequence[int], occupied_counts: Sequence[int]
) -> np.ndarray:
    """Return a closed-shell occupation vector with fixed roots per group."""

    sizes = [int(value) for value in group_sizes]
    counts = [int(value) for value in occupied_counts]
    if len(sizes) != len(counts) or any(
        size <= 0 or count < 0 or count > size
        for size, count in zip(sizes, counts, strict=True)
    ):
        raise ValueError("occupied counts must fit the corresponding positive groups")
    occupations = np.zeros(sum(sizes), dtype=float)
    offset = 0
    for size, count in zip(sizes, counts, strict=True):
        occupations[offset : offset + count] = 2.0
        offset += size
    return occupations


def nonorthogonal_closed_shell_density(
    coefficients: np.ndarray, metric: np.ndarray, occupations: np.ndarray
) -> np.ndarray:
    """Build an idempotent AO density from nonorthogonal occupied orbitals."""

    coeff = np.asarray(coefficients, dtype=float)
    overlap = np.asarray(metric, dtype=float)
    occ = np.asarray(occupations, dtype=float)
    if coeff.ndim != 2 or overlap.shape != (coeff.shape[0], coeff.shape[0]):
        raise ValueError("coefficient and AO-metric dimensions are incompatible")
    if occ.shape != (coeff.shape[1],) or not np.all(np.isin(occ, (0.0, 2.0))):
        raise ValueError("only closed-shell 0/2 occupations are supported")
    occupied = coeff[:, occ > 0.0]
    if occupied.shape[1] == 0:
        return np.zeros_like(overlap)
    occupied_metric = occupied.T @ overlap @ occupied
    if not metric_diagnostics(occupied_metric)["positive_definite"]:
        raise ValueError("occupied physical metric must be positive definite")
    return 2.0 * occupied @ np.linalg.inv(occupied_metric) @ occupied.T


def grouped_nonorthogonal_closed_shell_density(
    coefficients: np.ndarray,
    metric: np.ndarray,
    group_sizes: Sequence[int],
    occupied_counts: Sequence[int],
) -> np.ndarray:
    """Build the sum of group-local projectors in the unmasked AO metric.

    Unlike :func:`nonorthogonal_closed_shell_density`, this routine does not
    orthogonalize occupied orbitals belonging to different masked groups.  It
    therefore preserves an exactly block-diagonal coefficient density in the
    supplied grouped working basis, as required by the Chapter 5 FUD algebra.
    The resulting AO density is not generally idempotent in the full physical
    metric and must not be presented as an ordinary variational RHF density.
    """

    coeff = np.asarray(coefficients, dtype=float)
    overlap = np.asarray(metric, dtype=float)
    sizes = [int(value) for value in group_sizes]
    counts = [int(value) for value in occupied_counts]
    fixed_group_occupations(sizes, counts)  # validates dimensions/counts
    if coeff.ndim != 2 or overlap.shape != (coeff.shape[0], coeff.shape[0]):
        raise ValueError("coefficient and AO-metric dimensions are incompatible")
    if coeff.shape[1] != sum(sizes):
        raise ValueError("group sizes must span all coefficient columns")
    density = np.zeros_like(overlap)
    offset = 0
    for size, count in zip(sizes, counts, strict=True):
        group = coeff[:, offset : offset + size]
        occupied = group[:, :count]
        if count:
            occupied_metric = occupied.T @ overlap @ occupied
            if not metric_diagnostics(occupied_metric)["positive_definite"]:
                raise ValueError("occupied group metric must be positive definite")
            density += 2.0 * occupied @ np.linalg.inv(occupied_metric) @ occupied.T
        offset += size
    return density
