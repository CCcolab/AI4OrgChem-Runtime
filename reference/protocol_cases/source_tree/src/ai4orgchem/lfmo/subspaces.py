"""Nonorthogonal subspace algebra for LFMO invariant diagnostics."""

from __future__ import annotations

from typing import Any

import numpy as np


SYMMETRY_RELATIVE_TOLERANCE = 1.0e-12
SUBSPACE_CONDITION_LIMIT = 1.0e8


def _validated_metric(metric: np.ndarray) -> np.ndarray:
    value = np.asarray(metric, dtype=float)
    if value.ndim != 2 or value.shape[0] == 0 or value.shape[0] != value.shape[1]:
        raise ValueError("metric must be a nonempty square matrix")
    scale = max(float(np.linalg.norm(value, ord=np.inf)), 1.0)
    residual = float(np.linalg.norm(value - value.T, ord=np.inf) / scale)
    if residual > SYMMETRY_RELATIVE_TOLERANCE:
        raise ValueError("metric must be symmetric")
    value = 0.5 * (value + value.T)
    try:
        np.linalg.cholesky(value)
    except np.linalg.LinAlgError as exc:
        raise ValueError("metric must be positive definite") from exc
    return value


def _validated_coefficients(coefficients: np.ndarray, ao_dimension: int) -> np.ndarray:
    value = np.asarray(coefficients, dtype=float)
    if value.ndim != 2 or value.shape[0] != ao_dimension or value.shape[1] == 0:
        raise ValueError("coefficients must have shape (n_ao, n_subspace) with n_subspace > 0")
    if not np.all(np.isfinite(value)):
        raise ValueError("coefficients must be finite")
    return value


def subspace_gram(metric: np.ndarray, coefficients: np.ndarray) -> np.ndarray:
    """Return ``C.T @ S @ C`` after validating an SPD AO metric."""

    overlap = _validated_metric(metric)
    basis = _validated_coefficients(coefficients, overlap.shape[0])
    gram = basis.T @ overlap @ basis
    gram = 0.5 * (gram + gram.T)
    try:
        np.linalg.cholesky(gram)
    except np.linalg.LinAlgError as exc:
        raise ValueError("subspace coefficients must be linearly independent in the metric") from exc
    condition = float(np.linalg.cond(gram))
    if not np.isfinite(condition) or condition > SUBSPACE_CONDITION_LIMIT:
        raise ValueError("subspace Gram matrix exceeds the provisional condition limit")
    return gram


def metric_projector(metric: np.ndarray, coefficients: np.ndarray) -> np.ndarray:
    """Return the AO coefficient-space S-orthogonal projector.

    For full-column-rank ``C`` and SPD ``S``, this is
    ``P_C = C (C.T S C)^-1 C.T S``.  ``solve`` is used instead of forming an
    explicit inverse.  The result need not be Euclidean symmetric; it obeys
    ``P_C.T S = S P_C``.
    """

    overlap = _validated_metric(metric)
    basis = _validated_coefficients(coefficients, overlap.shape[0])
    gram = subspace_gram(overlap, basis)
    dual_rows = np.linalg.solve(gram, basis.T @ overlap)
    return basis @ dual_rows


def projector_diagnostics(metric: np.ndarray, coefficients: np.ndarray) -> dict[str, Any]:
    """Return normalized idempotency and metric-self-adjointness diagnostics."""

    overlap = _validated_metric(metric)
    basis = _validated_coefficients(coefficients, overlap.shape[0])
    projector = metric_projector(overlap, basis)
    scale = max(float(np.linalg.norm(projector, ord="fro")), 1.0)
    metric_scale = max(float(np.linalg.norm(overlap @ projector, ord="fro")), 1.0)
    return {
        "ao_dimension": int(overlap.shape[0]),
        "subspace_dimension": int(basis.shape[1]),
        "rank": int(np.linalg.matrix_rank(projector)),
        "trace": float(np.trace(projector)),
        "idempotency_residual": float(
            np.linalg.norm(projector @ projector - projector, ord="fro") / scale
        ),
        "metric_self_adjoint_residual": float(
            np.linalg.norm(projector.T @ overlap - overlap @ projector, ord="fro")
            / metric_scale
        ),
        "euclidean_symmetry_residual": float(
            np.linalg.norm(projector - projector.T, ord="fro") / scale
        ),
        "gram_condition_number": float(np.linalg.cond(basis.T @ overlap @ basis)),
    }


def subspace_leakage(
    metric: np.ndarray,
    candidate_coefficients: np.ndarray,
    forbidden_coefficients: np.ndarray,
) -> float:
    """Return average candidate-subspace weight inside a forbidden subspace.

    The dimensionless scalar is

    ``L(C -> B) = Tr[(C.T S C)^-1 C.T S P_B C] / dim(C)``.

    It is invariant to any nonsingular column transformation of either ``C``
    or ``B``.  For an S-orthogonal pair it is zero; for a candidate wholly
    contained in the forbidden subspace it is one.  This is a subspace measure,
    not a Mulliken or Loewdin population.
    """

    overlap = _validated_metric(metric)
    candidate = _validated_coefficients(candidate_coefficients, overlap.shape[0])
    forbidden = _validated_coefficients(forbidden_coefficients, overlap.shape[0])
    candidate_gram = subspace_gram(overlap, candidate)
    forbidden_projector = metric_projector(overlap, forbidden)
    projected_gram = candidate.T @ overlap @ forbidden_projector @ candidate
    weight = float(
        np.trace(np.linalg.solve(candidate_gram, projected_gram)) / candidate.shape[1]
    )
    tolerance = 64.0 * np.finfo(float).eps
    if -tolerance <= weight < 0.0:
        return 0.0
    if 1.0 < weight <= 1.0 + tolerance:
        return 1.0
    if not np.isfinite(weight) or weight < 0.0 or weight > 1.0:
        raise ValueError("leakage left the [0, 1] interval")
    return weight
