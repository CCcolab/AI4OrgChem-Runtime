"""One-cut pre-conditional-SCF working-basis assembly and audits."""

from __future__ import annotations

from typing import Any

import numpy as np

from .state_masks import metric_diagnostics


def classify_reflection_weight(
    pi_weight: float, *, tolerance: float = 1.0e-8
) -> str:
    """Classify a measured local reflection weight without guessing mixed cases."""

    value = float(pi_weight)
    if not np.isfinite(value) or value < -tolerance or value > 1.0 + tolerance:
        raise ValueError("pi_weight must lie in [0, 1] within tolerance")
    if value <= tolerance:
        return "sigma"
    if value >= 1.0 - tolerance:
        return "pi"
    return "mixed"


def one_cut_column_metadata(
    ch3_occupations: np.ndarray,
    *,
    target_index: int,
    occupied_indices: list[int],
    vacant_indices: list[int],
    ch3_pi_weights_before: np.ndarray,
    ch3_pi_weights_after: np.ndarray,
    reference_occupations: np.ndarray,
    reference_somo_index: int,
    symmetry_tolerance: float = 1.0e-8,
) -> list[dict[str, Any]]:
    """Return deterministic metadata in target/occupied/vacant/reference order."""

    ch3_occ = np.asarray(ch3_occupations, dtype=float)
    before = np.asarray(ch3_pi_weights_before, dtype=float)
    after = np.asarray(ch3_pi_weights_after, dtype=float)
    reference_occ = np.asarray(reference_occupations, dtype=float)
    if ch3_occ.ndim != 1 or before.shape != ch3_occ.shape or after.shape != ch3_occ.shape:
        raise ValueError("CH3 occupations and parity weights must be matching vectors")
    ordered_ch3 = [int(target_index), *map(int, occupied_indices), *map(int, vacant_indices)]
    if sorted(ordered_ch3) != list(range(ch3_occ.size)):
        raise ValueError("target/occupied/vacant indices must partition every CH3 orbital")
    if reference_occ.ndim != 1 or not (0 <= int(reference_somo_index) < reference_occ.size):
        raise ValueError("reference occupations or SOMO index are invalid")
    reference_order = [int(reference_somo_index), *[index for index in range(reference_occ.size) if index != int(reference_somo_index)]]

    records: list[dict[str, Any]] = []
    occupied_set = set(map(int, occupied_indices))
    vacant_set = set(map(int, vacant_indices))
    for source_index in ordered_ch3:
        if source_index == int(target_index):
            role = "cut_single"
            occupancy_class = "singly_occupied_fragment_reference"
        elif source_index in occupied_set:
            role = "fragment_occupied"
            occupancy_class = "doubly_occupied_fragment_reference"
        elif source_index in vacant_set:
            role = "fragment_vacant"
            occupancy_class = "vacant_fragment_reference"
        else:  # pragma: no cover - partition validation above makes this unreachable.
            raise RuntimeError("unclassified CH3 orbital")
        records.append(
            {
                "column": len(records),
                "owner_fragment": "CH3",
                "source_orbital_index": source_index,
                "orbital_role": role,
                "occupancy_class": occupancy_class,
                "reference_natural_occupation": float(ch3_occ[source_index]),
                "symmetry_scope": "CH3_local_xy_reflection",
                "pi_weight_before_kost": float(before[source_index]),
                "pi_weight_after_kost": float(after[source_index]),
                "symmetry_type_before_kost": classify_reflection_weight(
                    before[source_index], tolerance=symmetry_tolerance
                ),
                "symmetry_type_after_kost": classify_reflection_weight(
                    after[source_index], tolerance=symmetry_tolerance
                ),
            }
        )
    for source_index in reference_order:
        is_somo = source_index == int(reference_somo_index)
        records.append(
            {
                "column": len(records),
                "owner_fragment": "reference_H",
                "source_orbital_index": source_index,
                "orbital_role": "reference_single" if is_somo else "reference_vacant",
                "occupancy_class": (
                    "singly_occupied_reference_fragment"
                    if is_somo
                    else "vacant_reference_fragment"
                ),
                "reference_natural_occupation": float(reference_occ[source_index]),
                "symmetry_scope": "reference_H_s_only_not_global_sigma_pi",
                "pi_weight_before_kost": None,
                "pi_weight_after_kost": None,
                "symmetry_type_before_kost": "reference_s",
                "symmetry_type_after_kost": "reference_s",
            }
        )
    return records


def audit_one_cut_working_basis(
    initial_ch3: np.ndarray,
    transformed_ch3: np.ndarray,
    ch3_transform: np.ndarray,
    reference: np.ndarray,
    ao_metric: np.ndarray,
    *,
    ch3_ao_indices: list[int],
    reference_ao_indices: list[int],
) -> dict[str, Any]:
    """Assemble and audit the complete CH3 plus reference-H coefficient basis."""

    initial_fragment = np.asarray(initial_ch3, dtype=float)
    current_fragment = np.asarray(transformed_ch3, dtype=float)
    transform = np.asarray(ch3_transform, dtype=float)
    reference_block = np.asarray(reference, dtype=float)
    metric = np.asarray(ao_metric, dtype=float)
    if initial_fragment.ndim != 2 or current_fragment.shape != initial_fragment.shape:
        raise ValueError("initial and transformed CH3 blocks must have matching matrix shapes")
    if transform.shape != (initial_fragment.shape[1], initial_fragment.shape[1]):
        raise ValueError("CH3 transform shape does not match the CH3 orbital count")
    if reference_block.ndim != 2 or reference_block.shape[0] != initial_fragment.shape[0]:
        raise ValueError("reference block must share the composite AO dimension")
    if metric.shape != (initial_fragment.shape[0], initial_fragment.shape[0]):
        raise ValueError("AO metric must match the composite AO dimension")

    initial = np.column_stack((initial_fragment, reference_block))
    current = np.column_stack((current_fragment, reference_block))
    full_transform = np.eye(initial.shape[1])
    full_transform[: transform.shape[0], : transform.shape[1]] = transform
    predicted = initial @ full_transform
    reconstructed = current @ full_transform.T
    initial_metric = initial.T @ metric @ initial
    current_metric = current.T @ metric @ current
    expected_metric = full_transform.T @ initial_metric @ full_transform
    coefficient_scale = max(float(np.linalg.norm(initial, ord="fro")), 1.0)
    metric_scale = max(float(np.linalg.norm(current_metric, ord="fro")), 1.0)

    ch3_outside = np.ones(initial.shape[0], dtype=bool)
    ch3_outside[list(map(int, ch3_ao_indices))] = False
    reference_outside = np.ones(initial.shape[0], dtype=bool)
    reference_outside[list(map(int, reference_ao_indices))] = False
    ch3_support = float(np.max(np.abs(current_fragment[ch3_outside, :])))
    reference_support = float(np.max(np.abs(reference_block[reference_outside, :])))
    diagnostics = metric_diagnostics(current_metric)
    return {
        "initial_coefficients": initial,
        "current_coefficients": current,
        "full_transform": full_transform,
        "initial_metric": initial_metric,
        "current_metric": current_metric,
        "metric_diagnostics": diagnostics,
        "ao_dimension": int(initial.shape[0]),
        "column_count": int(initial.shape[1]),
        "coefficient_rank": int(np.linalg.matrix_rank(current)),
        "square_basis": bool(initial.shape[0] == initial.shape[1]),
        "transform_application_residual": float(
            np.linalg.norm(current - predicted, ord="fro") / coefficient_scale
        ),
        "reconstruction_residual": float(
            np.linalg.norm(reconstructed - initial, ord="fro") / coefficient_scale
        ),
        "full_transform_orthogonality_residual": float(
            np.linalg.norm(full_transform.T @ full_transform - np.eye(full_transform.shape[0]), ord="fro")
        ),
        "metric_covariance_residual": float(
            np.linalg.norm(current_metric - expected_metric, ord="fro") / metric_scale
        ),
        "ch3_outside_support_max": ch3_support,
        "reference_outside_support_max": reference_support,
    }
