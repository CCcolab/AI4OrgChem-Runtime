"""Pure linear-algebra helpers for non-production LFMO state-mask audits."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


SYMMETRY_RELATIVE_TOLERANCE = 1.0e-12


def block_mask(group_sizes: Sequence[int]) -> np.ndarray:
    """Return a binary block-diagonal mask for ordered orbital groups."""

    sizes = tuple(int(size) for size in group_sizes)
    if not sizes or any(size <= 0 for size in sizes):
        raise ValueError("group sizes must be positive")
    group_ids = np.repeat(np.arange(len(sizes)), sizes)
    return (group_ids[:, None] == group_ids[None, :]).astype(float)


def is_partition_mask(mask: np.ndarray) -> bool:
    """Return whether a binary mask represents disjoint complete index groups.

    A protocol state mask is an equivalence relation: it is reflexive,
    symmetric, and transitive.  Merely checking symmetry and a retained
    diagonal is insufficient because arbitrary Hadamard deletion can make a
    positive-definite metric indefinite.
    """

    value = np.asarray(mask, dtype=float)
    if value.ndim != 2 or value.shape[0] == 0 or value.shape[0] != value.shape[1]:
        return False
    if not np.all(np.isin(value, (0.0, 1.0))):
        return False
    relation = value.astype(bool)
    if not np.array_equal(relation, relation.T):
        return False
    if not np.all(np.diag(relation)):
        return False
    # For an equivalence relation, related indices have identical rows.
    return all(
        np.array_equal(relation[index], relation[partner])
        for index, partner in zip(*np.nonzero(relation), strict=True)
    )


def apply_symmetric_mask(matrix: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Apply a protocol-valid partition mask to one symmetric matrix."""

    value = np.asarray(matrix, dtype=float)
    binary_mask = np.asarray(mask, dtype=float)
    if value.ndim != 2 or value.shape[0] != value.shape[1]:
        raise ValueError("matrix must be square")
    if binary_mask.shape != value.shape:
        raise ValueError("mask shape must match matrix shape")
    scale = max(float(np.linalg.norm(value, ord=np.inf)), 1.0)
    symmetry_residual = float(np.linalg.norm(value - value.T, ord=np.inf) / scale)
    if symmetry_residual > SYMMETRY_RELATIVE_TOLERANCE:
        raise ValueError("matrix must be symmetric")
    if not is_partition_mask(binary_mask):
        raise ValueError("mask must define disjoint complete index groups")
    return value * binary_mask


def metric_diagnostics(metric: np.ndarray) -> dict[str, float | bool | int]:
    """Report positive-definiteness and conditioning of a symmetric metric."""

    value = np.asarray(metric, dtype=float)
    if value.ndim != 2 or value.shape[0] != value.shape[1]:
        raise ValueError("metric must be square")
    scale = max(float(np.linalg.norm(value, ord=np.inf)), 1.0)
    symmetry_residual = float(np.linalg.norm(value - value.T, ord=np.inf) / scale)
    symmetric = bool(symmetry_residual <= SYMMETRY_RELATIVE_TOLERANCE)
    if not symmetric:
        return {
            "dimension": int(value.shape[0]),
            "symmetric": False,
            "symmetry_residual": symmetry_residual,
            "positive_definite": False,
            "full_rank": False,
            "rank": 0,
            "rank_tolerance": float("nan"),
            "minimum_eigenvalue": float("nan"),
            "maximum_eigenvalue": float("nan"),
            "condition_number": float("inf"),
        }
    symmetric_value = 0.5 * (value + value.T)
    eigenvalues = np.linalg.eigvalsh(symmetric_value)
    minimum = float(eigenvalues[0])
    maximum = float(eigenvalues[-1])
    rank_tolerance = float(
        np.finfo(float).eps * value.shape[0] * max(abs(minimum), abs(maximum))
    )
    rank = int(np.count_nonzero(np.abs(eigenvalues) > rank_tolerance))
    try:
        np.linalg.cholesky(symmetric_value)
        positive_definite = True
    except np.linalg.LinAlgError:
        positive_definite = False
    return {
        "dimension": int(value.shape[0]),
        "symmetric": True,
        "symmetry_residual": symmetry_residual,
        "positive_definite": positive_definite,
        "full_rank": rank == value.shape[0],
        "rank": rank,
        "rank_tolerance": rank_tolerance,
        "minimum_eigenvalue": minimum,
        "maximum_eigenvalue": maximum,
        "condition_number": float(maximum / minimum)
        if positive_definite
        else float("inf"),
    }
