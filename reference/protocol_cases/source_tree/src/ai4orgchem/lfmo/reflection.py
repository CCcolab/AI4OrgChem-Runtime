"""Deterministic reflection adaptation inside occupation-equivalent blocks."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np


def ao_plane_reflection_operator(molecule: Any, normal: Sequence[float]) -> np.ndarray:
    """Return the AO representation of reflection through a plane normal.

    The atoms are assumed to lie in the reflection plane.  An improper plane
    reflection is represented as inversion, ``(-1)**l`` in each AO shell,
    followed by the corresponding proper rotation supplied by PySCF.
    """

    unit_normal = np.asarray(normal, dtype=float)
    if unit_normal.shape != (3,) or not np.all(np.isfinite(unit_normal)):
        raise ValueError("normal must be a finite three-vector")
    norm = float(np.linalg.norm(unit_normal))
    if norm <= 1.0e-14:
        raise ValueError("normal must be nonzero")
    unit_normal /= norm
    reflection = np.eye(3) - 2.0 * np.outer(unit_normal, unit_normal)
    proper_rotation = -reflection
    rotation = np.asarray(molecule.ao_rotation_matrix(proper_rotation), dtype=float)
    ao_locations = molecule.ao_loc_nr()
    inversion_parity: list[float] = []
    for shell in range(molecule.nbas):
        width = int(ao_locations[shell + 1] - ao_locations[shell])
        inversion_parity.extend([(-1.0) ** int(molecule.bas_angular(shell))] * width)
    return np.diag(inversion_parity) @ rotation


def occupation_blocks(
    occupations: Sequence[float],
    classes: Sequence[str],
    *,
    tolerance: float,
) -> list[list[int]]:
    """Cluster only equal-class orbitals whose full occupation span fits tolerance."""

    values = np.asarray(occupations, dtype=float)
    labels = [str(value) for value in classes]
    if values.ndim != 1 or len(labels) != values.size or values.size == 0:
        raise ValueError("occupations and classes must be nonempty aligned vectors")
    if not np.all(np.isfinite(values)) or tolerance < 0.0:
        raise ValueError("occupations must be finite and tolerance nonnegative")

    blocks: list[list[int]] = []
    for label in dict.fromkeys(labels):
        members = sorted(
            (index for index, item in enumerate(labels) if item == label),
            key=lambda index: (-float(values[index]), index),
        )
        current: list[int] = []
        for index in members:
            candidate = [*current, index]
            candidate_values = values[candidate]
            if current and float(np.max(candidate_values) - np.min(candidate_values)) > tolerance:
                blocks.append(sorted(current))
                current = [index]
            else:
                current = candidate
        if current:
            blocks.append(sorted(current))
    return sorted(blocks, key=lambda block: min(block))


def _metric_orthonormalize(
    candidates: list[np.ndarray], dimension: int, *, tolerance: float
) -> np.ndarray:
    selected: list[np.ndarray] = []
    remaining = [np.asarray(candidate, dtype=float).copy() for candidate in candidates]
    while len(selected) < dimension:
        residuals: list[np.ndarray] = []
        norms: list[float] = []
        for candidate in remaining:
            vector = candidate.copy()
            for basis_vector in selected:
                vector -= basis_vector * float(basis_vector @ vector)
            residuals.append(vector)
            norms.append(float(np.linalg.norm(vector)))
        if not norms:
            break
        pivot = max(range(len(norms)), key=lambda index: (norms[index], -index))
        vector = residuals[pivot]
        norm = norms[pivot]
        if norm <= tolerance:
            break
        vector /= norm
        phase_pivot = int(np.argmax(np.abs(vector)))
        if vector[phase_pivot] < 0.0:
            vector *= -1.0
        selected.append(vector)
        remaining.pop(pivot)
    if len(selected) != dimension:
        raise RuntimeError("AO anchors did not span a reflection eigenspace")
    return np.column_stack(selected)


def _anchored_eigenspace_basis(
    projector: np.ndarray,
    block_coefficients: np.ndarray,
    metric: np.ndarray,
    dimension: int,
    *,
    anchor_tolerance: float,
) -> np.ndarray:
    anchors = block_coefficients.T @ metric
    candidates = [projector @ anchors[:, ao] for ao in range(anchors.shape[1])]
    return _metric_orthonormalize(candidates, dimension, tolerance=anchor_tolerance)


def adapt_reflection_blocks(
    coefficients: np.ndarray,
    metric: np.ndarray,
    parity_signs: Sequence[float] | np.ndarray,
    occupations: Sequence[float],
    classes: Sequence[str],
    *,
    occupation_tolerance: float = 1.0e-8,
    parity_tolerance: float = 1.0e-8,
    anchor_tolerance: float = 1.0e-10,
    classification_policy: str = "exact_closure",
    minimum_absolute_eigenvalue: float = 0.0,
) -> dict[str, Any]:
    """Diagonalize reflection only inside declared occupation-equivalent blocks.

    Degenerate parity eigenspaces are fixed with canonical AO anchors, making the
    resulting physical orbitals independent of input orbital phase, permutation,
    and rotations within an allowed block.
    """

    coeff = np.asarray(coefficients, dtype=float)
    overlap = np.asarray(metric, dtype=float)
    parity = np.asarray(parity_signs, dtype=float)
    occ = np.asarray(occupations, dtype=float)
    if classification_policy not in {"exact_closure", "spectral_sign"}:
        raise ValueError(
            f"unsupported reflection classification policy: {classification_policy}"
        )
    if not 0.0 <= minimum_absolute_eigenvalue <= 1.0:
        raise ValueError("minimum absolute reflection eigenvalue must be in [0, 1]")
    if coeff.ndim != 2 or coeff.shape[0] != overlap.shape[0] or overlap.shape[0] != overlap.shape[1]:
        raise ValueError("coefficient and metric dimensions are incompatible")
    if coeff.shape[1] != occ.size:
        raise ValueError("occupation or parity dimensions are incompatible")
    if parity.ndim == 1:
        if parity.shape != (coeff.shape[0],) or not np.all(np.isin(parity, (-1.0, 1.0))):
            raise ValueError("parity signs must be an AO-sized +/-1 vector")
        reflection = np.diag(parity)
    elif parity.shape == (coeff.shape[0], coeff.shape[0]):
        reflection = parity
    else:
        raise ValueError("reflection operator dimensions are incompatible")

    identity = np.eye(coeff.shape[1])
    orthonormality_before = float(np.linalg.norm(coeff.T @ overlap @ coeff - identity, ord="fro"))
    blocks = occupation_blocks(occ, classes, tolerance=occupation_tolerance)
    adapted = coeff.copy()
    transform = np.eye(coeff.shape[1])
    ledger: list[dict[str, Any]] = []

    for block in blocks:
        block_coeff = coeff[:, block]
        block_metric = 0.5 * (
            block_coeff.T @ overlap @ block_coeff
            + block_coeff.T @ overlap.T @ block_coeff
        )
        metric_values, metric_vectors = np.linalg.eigh(block_metric)
        if float(metric_values[0]) <= anchor_tolerance:
            raise RuntimeError("an occupation block is rank deficient in the AO metric")
        inverse_square_root = (
            metric_vectors
            @ np.diag(metric_values ** -0.5)
            @ metric_vectors.T
        )
        orthonormal_block = block_coeff @ inverse_square_root
        operator = 0.5 * (
            orthonormal_block.T @ overlap @ reflection @ orthonormal_block
            + orthonormal_block.T @ reflection.T @ overlap @ orthonormal_block
        )
        eigenvalues, eigenvectors = np.linalg.eigh(operator)
        sigma_mask = eigenvalues >= 0.0
        pi_mask = ~sigma_mask
        closure_residuals = np.abs(np.abs(eigenvalues) - 1.0)
        if classification_policy == "exact_closure" and np.any(
            closure_residuals > parity_tolerance
        ):
            raise RuntimeError(
                "an occupation block is not closed under reflection: "
                f"maximum residual={float(np.max(closure_residuals)):.12e}, "
                f"eigenvalues={eigenvalues.tolist()}"
            )
        if classification_policy == "spectral_sign" and np.any(
            np.abs(eigenvalues) < minimum_absolute_eigenvalue
        ):
            raise RuntimeError(
                "an occupation block lacks the required reflection spectral gap: "
                f"minimum absolute eigenvalue={float(np.min(np.abs(eigenvalues))):.12e}, "
                f"required={minimum_absolute_eigenvalue:.12e}"
            )
        columns: list[np.ndarray] = []
        parities: list[str] = []
        eigenvalue_order: list[float] = []
        for name, mask, expected in (("sigma", sigma_mask, 1.0), ("pi", pi_mask, -1.0)):
            count = int(np.count_nonzero(mask))
            if count == 0:
                continue
            eigenspace = eigenvectors[:, mask]
            projector = eigenspace @ eigenspace.T
            anchored = _anchored_eigenspace_basis(
                projector,
                orthonormal_block,
                overlap,
                count,
                anchor_tolerance=anchor_tolerance,
            )
            columns.extend(anchored[:, index] for index in range(count))
            parities.extend([name] * count)
            eigenvalue_order.extend([expected] * count)
        local_transform = np.column_stack(columns)
        adapted[:, block] = orthonormal_block @ local_transform
        transform[np.ix_(block, block)] = inverse_square_root @ local_transform
        measured = np.diag(
            adapted[:, block].T @ overlap @ reflection @ adapted[:, block]
        )
        ledger.append(
            {
                "indices": list(block),
                "occupancy_class": str(classes[block[0]]),
                "occupation_minimum": float(np.min(occ[block])),
                "occupation_maximum": float(np.max(occ[block])),
                "occupation_span": float(np.ptp(occ[block])),
                "input_reflection_eigenvalues": eigenvalues.tolist(),
                "classification_policy": classification_policy,
                "adapted_parities": parities,
                "adapted_reflection_expectations": measured.tolist(),
                "maximum_parity_residual": float(
                    np.max(np.abs(measured - np.asarray(eigenvalue_order)))
                ),
            }
        )

    orthonormality_after = float(np.linalg.norm(adapted.T @ overlap @ adapted - identity, ord="fro"))
    full_metric_before = coeff.T @ overlap @ coeff
    full_metric_after = adapted.T @ overlap @ adapted
    projector_before = coeff @ np.linalg.inv(full_metric_before) @ coeff.T @ overlap
    projector_after = adapted @ np.linalg.inv(full_metric_after) @ adapted.T @ overlap
    return {
        "coefficients": adapted,
        "transform": transform,
        "blocks": ledger,
        "orthonormality_before_residual": orthonormality_before,
        "orthonormality_after_residual": orthonormality_after,
        "transform_metric_orthonormality_residual": float(
            np.linalg.norm(transform.T @ full_metric_before @ transform - identity, ord="fro")
        ),
        "coefficient_reconstruction_residual": float(
            np.linalg.norm(adapted - coeff @ transform, ord="fro")
        ),
        "full_subspace_projector_residual": float(
            np.linalg.norm(projector_after - projector_before, ord="fro")
        ),
        "maximum_parity_residual": max(
            (float(block["maximum_parity_residual"]) for block in ledger),
            default=0.0,
        ),
    }
