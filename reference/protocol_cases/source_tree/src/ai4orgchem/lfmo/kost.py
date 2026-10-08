"""Independent two-orbital algebra corresponding to the public Kost equations."""

from __future__ import annotations

from typing import Any

import numpy as np


def _column(value: np.ndarray, name: str) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if array.ndim == 1:
        array = array[:, None]
    if array.ndim != 2 or array.shape[1] != 1 or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be one finite coefficient column")
    return array


def _metric(value: np.ndarray, dimension: int) -> np.ndarray:
    metric = np.asarray(value, dtype=float)
    if metric.shape != (dimension, dimension) or not np.all(np.isfinite(metric)):
        raise ValueError("metric must be a finite square matrix matching the coefficients")
    scale = max(float(np.linalg.norm(metric, ord=np.inf)), 1.0)
    if float(np.linalg.norm(metric - metric.T, ord=np.inf) / scale) > 1.0e-12:
        raise ValueError("metric must be symmetric")
    metric = 0.5 * (metric + metric.T)
    try:
        np.linalg.cholesky(metric)
    except np.linalg.LinAlgError as exc:
        raise ValueError("metric must be positive definite") from exc
    return metric


def rotate_to_fixed_probe(
    target: np.ndarray,
    auxiliary: np.ndarray,
    probe: np.ndarray,
    metric: np.ndarray,
    *,
    zero_tolerance: float = 1.0e-14,
) -> dict[str, Any]:
    """Rotate two fragment orbitals so the auxiliary is orthogonal to a fixed probe.

    With ``a=<target|probe>`` and ``b=<auxiliary|probe>``, the branch-complete
    angle ``atan2(-b, a)`` implements Eqs. 3-9/3-10 and gives a nonnegative
    maximum target overlap and zero auxiliary overlap.
    """

    target_column = _column(target, "target")
    auxiliary_column = _column(auxiliary, "auxiliary")
    probe_column = _column(probe, "probe")
    if not (
        target_column.shape[0]
        == auxiliary_column.shape[0]
        == probe_column.shape[0]
    ):
        raise ValueError("target, auxiliary, and probe must share an AO dimension")
    overlap = _metric(metric, target_column.shape[0])
    pair = np.column_stack((target_column[:, 0], auxiliary_column[:, 0]))
    if np.linalg.matrix_rank(pair) != 2:
        raise ValueError("target and auxiliary must be linearly independent")

    target_overlap = float((target_column.T @ overlap @ probe_column)[0, 0])
    auxiliary_overlap = float((auxiliary_column.T @ overlap @ probe_column)[0, 0])
    overlap_norm = float(np.hypot(target_overlap, auxiliary_overlap))
    if overlap_norm <= zero_tolerance:
        raise ValueError("both probe overlaps are zero; the maximizing target is undefined")

    angle = float(np.arctan2(-auxiliary_overlap, target_overlap))
    cosine = float(np.cos(angle))
    sine = float(np.sin(angle))
    transform = np.array([[cosine, sine], [-sine, cosine]], dtype=float)
    rotated = pair @ transform
    rotated_target = rotated[:, [0]]
    rotated_auxiliary = rotated[:, [1]]
    achieved_target = float((rotated_target.T @ overlap @ probe_column)[0, 0])
    achieved_auxiliary = float((rotated_auxiliary.T @ overlap @ probe_column)[0, 0])
    reconstructed = rotated @ transform.T

    initial_gram = pair.T @ overlap @ pair
    rotated_gram = rotated.T @ overlap @ rotated
    expected_rotated_gram = transform.T @ initial_gram @ transform
    coefficient_scale = max(float(np.linalg.norm(pair, ord="fro")), 1.0)
    gram_scale = max(float(np.linalg.norm(rotated_gram, ord="fro")), 1.0)
    # Derivative of (a cos(beta)-b sin(beta))^2 at the selected angle.
    stationary_derivative = 2.0 * achieved_target * (-achieved_auxiliary)
    return {
        "angle_radians": angle,
        "angle_degrees": float(np.degrees(angle)),
        "cosine": cosine,
        "sine": sine,
        "transform": transform,
        "rotated_target": rotated_target,
        "rotated_auxiliary": rotated_auxiliary,
        "initial_target_overlap": target_overlap,
        "initial_auxiliary_overlap": auxiliary_overlap,
        "overlap_vector_norm": overlap_norm,
        "achieved_target_overlap": achieved_target,
        "achieved_auxiliary_overlap": achieved_auxiliary,
        "target_maximum_residual": abs(achieved_target - overlap_norm),
        "off_target_overlap_residual": abs(achieved_auxiliary),
        "stationary_derivative_residual": abs(stationary_derivative),
        "transform_orthogonality_residual": float(
            np.linalg.norm(transform.T @ transform - np.eye(2), ord="fro")
        ),
        "reconstruction_residual": float(
            np.linalg.norm(reconstructed - pair, ord="fro") / coefficient_scale
        ),
        "metric_covariance_residual": float(
            np.linalg.norm(rotated_gram - expected_rotated_gram, ord="fro") / gram_scale
        ),
        "initial_gram": initial_gram,
        "rotated_gram": rotated_gram,
    }


def occupied_kost_loop(
    target: np.ndarray,
    auxiliaries: np.ndarray,
    probe: np.ndarray,
    metric: np.ndarray,
    *,
    auxiliary_labels: list[int] | None = None,
    tolerance: float = 1.0e-10,
    maximum_sweeps: int = 8,
    monotonic_tolerance: float = 1.0e-12,
) -> dict[str, Any]:
    """Sweep occupied auxiliaries using the validated two-orbital kernel.

    The returned cumulative transform ``Q`` obeys ``current = initial @ Q``.
    A nonconverged cap returns normally with ``converged=False`` so callers can
    retain the complete failure history.
    """

    target_column = _column(target, "target")
    probe_column = _column(probe, "probe")
    auxiliary_block = np.asarray(auxiliaries, dtype=float)
    if auxiliary_block.ndim == 1:
        auxiliary_block = auxiliary_block[:, None]
    if (
        auxiliary_block.ndim != 2
        or auxiliary_block.shape[0] != target_column.shape[0]
        or auxiliary_block.shape[1] == 0
        or not np.all(np.isfinite(auxiliary_block))
    ):
        raise ValueError("auxiliaries must be a finite nonempty coefficient block")
    if probe_column.shape[0] != target_column.shape[0]:
        raise ValueError("target, auxiliaries, and probe must share an AO dimension")
    if tolerance < 0.0 or monotonic_tolerance < 0.0 or maximum_sweeps < 0:
        raise ValueError("tolerances and maximum_sweeps must be nonnegative")

    overlap = _metric(metric, target_column.shape[0])
    labels = (
        list(range(auxiliary_block.shape[1]))
        if auxiliary_labels is None
        else [int(value) for value in auxiliary_labels]
    )
    if len(labels) != auxiliary_block.shape[1] or len(set(labels)) != len(labels):
        raise ValueError("auxiliary_labels must be unique and match the auxiliary count")

    initial = np.column_stack((target_column[:, 0], auxiliary_block))
    if np.linalg.matrix_rank(initial) != initial.shape[1]:
        raise ValueError("the occupied block must be linearly independent")
    current = initial.copy()
    cumulative = np.eye(initial.shape[1])
    initial_overlaps = (initial.T @ overlap @ probe_column)[:, 0]
    expected_target_magnitude = float(np.linalg.norm(initial_overlaps))
    history: list[dict[str, Any]] = []
    target_magnitudes = [abs(float(initial_overlaps[0]))]

    sweeps_completed = 0
    for sweep in range(1, maximum_sweeps + 1):
        sweeps_completed = sweep
        rotations_this_sweep = 0
        for position, label in enumerate(labels, start=1):
            before_target = float((current[:, [0]].T @ overlap @ probe_column)[0, 0])
            before_auxiliary = float(
                (current[:, [position]].T @ overlap @ probe_column)[0, 0]
            )
            if abs(before_auxiliary) <= tolerance:
                history.append(
                    {
                        "sweep": sweep,
                        "auxiliary_position": position,
                        "auxiliary_label": label,
                        "applied": False,
                        "before_target_overlap": before_target,
                        "before_auxiliary_overlap": before_auxiliary,
                        "after_target_overlap": before_target,
                        "after_auxiliary_overlap": before_auxiliary,
                        "angle_radians": 0.0,
                    }
                )
                continue

            step = rotate_to_fixed_probe(
                current[:, [0]], current[:, [position]], probe_column, overlap
            )
            embedded = np.eye(initial.shape[1])
            embedded[np.ix_([0, position], [0, position])] = step["transform"]
            current = current @ embedded
            cumulative = cumulative @ embedded
            after_target = float((current[:, [0]].T @ overlap @ probe_column)[0, 0])
            after_auxiliary = float(
                (current[:, [position]].T @ overlap @ probe_column)[0, 0]
            )
            if abs(after_target) + monotonic_tolerance < abs(before_target):
                raise RuntimeError("target overlap magnitude decreased beyond tolerance")
            target_magnitudes.append(abs(after_target))
            rotations_this_sweep += 1
            history.append(
                {
                    "sweep": sweep,
                    "auxiliary_position": position,
                    "auxiliary_label": label,
                    "applied": True,
                    "before_target_overlap": before_target,
                    "before_auxiliary_overlap": before_auxiliary,
                    "after_target_overlap": after_target,
                    "after_auxiliary_overlap": after_auxiliary,
                    "angle_radians": step["angle_radians"],
                }
            )

        final_overlaps = (current.T @ overlap @ probe_column)[:, 0]
        if float(np.max(np.abs(final_overlaps[1:]))) <= tolerance:
            break
        if rotations_this_sweep == 0:
            break

    final_overlaps = (current.T @ overlap @ probe_column)[:, 0]
    maximum_off_target = float(np.max(np.abs(final_overlaps[1:])))
    converged = maximum_off_target <= tolerance
    reconstructed = current @ cumulative.T
    initial_gram = initial.T @ overlap @ initial
    current_gram = current.T @ overlap @ current
    expected_gram = cumulative.T @ initial_gram @ cumulative
    coefficient_scale = max(float(np.linalg.norm(initial, ord="fro")), 1.0)
    gram_scale = max(float(np.linalg.norm(current_gram, ord="fro")), 1.0)
    return {
        "converged": bool(converged),
        "sweeps_completed": sweeps_completed,
        "rotation_count": sum(bool(item["applied"]) for item in history),
        "history": history,
        "auxiliary_labels": labels,
        "initial_block": initial,
        "current_block": current,
        "cumulative_transform": cumulative,
        "initial_overlaps": initial_overlaps,
        "final_overlaps": final_overlaps,
        "maximum_off_target_overlap": maximum_off_target,
        "expected_target_magnitude": expected_target_magnitude,
        "final_target_magnitude": abs(float(final_overlaps[0])),
        "target_maximum_residual": abs(
            abs(float(final_overlaps[0])) - expected_target_magnitude
        ),
        "target_magnitude_history": target_magnitudes,
        "monotonic_minimum_increment": min(
            (
                target_magnitudes[index + 1] - target_magnitudes[index]
                for index in range(len(target_magnitudes) - 1)
            ),
            default=0.0,
        ),
        "reconstruction_residual": float(
            np.linalg.norm(reconstructed - initial, ord="fro") / coefficient_scale
        ),
        "cumulative_orthogonality_residual": float(
            np.linalg.norm(
                cumulative.T @ cumulative - np.eye(cumulative.shape[0]), ord="fro"
            )
        ),
        "metric_covariance_residual": float(
            np.linalg.norm(current_gram - expected_gram, ord="fro") / gram_scale
        ),
        "initial_gram": initial_gram,
        "current_gram": current_gram,
    }


def occupied_then_vacant_kost(
    target: np.ndarray,
    occupied_auxiliaries: np.ndarray,
    vacant_auxiliaries: np.ndarray,
    probe: np.ndarray,
    metric: np.ndarray,
    *,
    occupied_labels: list[int] | None = None,
    vacant_labels: list[int] | None = None,
    tolerance: float = 1.0e-10,
    occupied_maximum_sweeps: int = 8,
    vacant_sweeps: int = 1,
    monotonic_tolerance: float = 1.0e-12,
) -> dict[str, Any]:
    """Run the passed occupied loop followed by zero or one vacant sweep.

    The full column order is ``[target, occupied..., vacant...]`` and the
    returned transform ``Q`` obeys ``current = initial @ Q``.  A vacant step
    rotates only the current target and one vacant column.  Occupied-probe
    overlaps and target-occupied metric overlaps are measured before and after
    the vacant sweep; they are never silently repaired here.
    """

    if vacant_sweeps not in (0, 1):
        raise ValueError("vacant_sweeps must be zero or one in this validation rung")
    target_column = _column(target, "target")
    probe_column = _column(probe, "probe")
    occupied = np.asarray(occupied_auxiliaries, dtype=float)
    vacant = np.asarray(vacant_auxiliaries, dtype=float)
    if occupied.ndim == 1:
        occupied = occupied[:, None]
    if vacant.ndim == 1:
        vacant = vacant[:, None]
    for block, name in ((occupied, "occupied_auxiliaries"), (vacant, "vacant_auxiliaries")):
        if (
            block.ndim != 2
            or block.shape[0] != target_column.shape[0]
            or block.shape[1] == 0
            or not np.all(np.isfinite(block))
        ):
            raise ValueError(f"{name} must be a finite nonempty coefficient block")
    if probe_column.shape[0] != target_column.shape[0]:
        raise ValueError("target, auxiliary blocks, and probe must share an AO dimension")
    if tolerance < 0.0 or monotonic_tolerance < 0.0:
        raise ValueError("tolerances must be nonnegative")

    overlap = _metric(metric, target_column.shape[0])
    occupied_names = (
        list(range(occupied.shape[1]))
        if occupied_labels is None
        else [int(value) for value in occupied_labels]
    )
    vacant_names = (
        list(range(vacant.shape[1]))
        if vacant_labels is None
        else [int(value) for value in vacant_labels]
    )
    if len(occupied_names) != occupied.shape[1] or len(set(occupied_names)) != len(occupied_names):
        raise ValueError("occupied_labels must be unique and match the occupied count")
    if len(vacant_names) != vacant.shape[1] or len(set(vacant_names)) != len(vacant_names):
        raise ValueError("vacant_labels must be unique and match the vacant count")
    if set(occupied_names) & set(vacant_names):
        raise ValueError("occupied and vacant labels must be disjoint")

    initial = np.column_stack((target_column[:, 0], occupied, vacant))
    if np.linalg.matrix_rank(initial) != initial.shape[1]:
        raise ValueError("the combined target/occupied/vacant block must be linearly independent")
    occupied_result = occupied_kost_loop(
        target_column,
        occupied,
        probe_column,
        overlap,
        auxiliary_labels=occupied_names,
        tolerance=tolerance,
        maximum_sweeps=occupied_maximum_sweeps,
        monotonic_tolerance=monotonic_tolerance,
    )
    occupied_width = 1 + occupied.shape[1]
    cumulative = np.eye(initial.shape[1])
    cumulative[:occupied_width, :occupied_width] = occupied_result["cumulative_transform"]
    current = initial @ cumulative

    occupied_probe_before = (current[:, 1:occupied_width].T @ overlap @ probe_column)[:, 0]
    target_occupied_before = (
        current[:, [0]].T @ overlap @ current[:, 1:occupied_width]
    )[0]
    occupied_coefficients_before = current[:, 1:occupied_width].copy()
    initial_full_overlaps = (initial.T @ overlap @ probe_column)[:, 0]
    vacant_history: list[dict[str, Any]] = []
    target_magnitudes = [abs(float((current[:, [0]].T @ overlap @ probe_column)[0, 0]))]

    vacant_start = occupied_width
    if vacant_sweeps == 1:
        for position, label in enumerate(vacant_names, start=vacant_start):
            before_target = float((current[:, [0]].T @ overlap @ probe_column)[0, 0])
            before_auxiliary = float(
                (current[:, [position]].T @ overlap @ probe_column)[0, 0]
            )
            if abs(before_auxiliary) <= tolerance:
                vacant_history.append(
                    {
                        "sweep": 1,
                        "auxiliary_position": position,
                        "auxiliary_label": label,
                        "applied": False,
                        "before_target_overlap": before_target,
                        "before_auxiliary_overlap": before_auxiliary,
                        "after_target_overlap": before_target,
                        "after_auxiliary_overlap": before_auxiliary,
                        "angle_radians": 0.0,
                    }
                )
                continue
            step = rotate_to_fixed_probe(
                current[:, [0]], current[:, [position]], probe_column, overlap
            )
            embedded = np.eye(initial.shape[1])
            embedded[np.ix_([0, position], [0, position])] = step["transform"]
            current = current @ embedded
            cumulative = cumulative @ embedded
            after_target = float((current[:, [0]].T @ overlap @ probe_column)[0, 0])
            after_auxiliary = float(
                (current[:, [position]].T @ overlap @ probe_column)[0, 0]
            )
            if abs(after_target) + monotonic_tolerance < abs(before_target):
                raise RuntimeError("target overlap magnitude decreased beyond tolerance")
            target_magnitudes.append(abs(after_target))
            vacant_history.append(
                {
                    "sweep": 1,
                    "auxiliary_position": position,
                    "auxiliary_label": label,
                    "applied": True,
                    "before_target_overlap": before_target,
                    "before_auxiliary_overlap": before_auxiliary,
                    "after_target_overlap": after_target,
                    "after_auxiliary_overlap": after_auxiliary,
                    "angle_radians": step["angle_radians"],
                }
            )

    final_full_overlaps = (current.T @ overlap @ probe_column)[:, 0]
    occupied_probe_after = final_full_overlaps[1:occupied_width]
    vacant_probe_after = final_full_overlaps[vacant_start:]
    target_occupied_after = (
        current[:, [0]].T @ overlap @ current[:, 1:occupied_width]
    )[0]
    occupied_coefficients_after = current[:, 1:occupied_width]
    reconstructed = current @ cumulative.T
    initial_gram = initial.T @ overlap @ initial
    current_gram = current.T @ overlap @ current
    expected_gram = cumulative.T @ initial_gram @ cumulative
    coefficient_scale = max(float(np.linalg.norm(initial, ord="fro")), 1.0)
    gram_scale = max(float(np.linalg.norm(current_gram, ord="fro")), 1.0)
    vacant_maximum = float(np.max(np.abs(vacant_probe_after)))
    occupied_maximum_before = float(np.max(np.abs(occupied_probe_before)))
    occupied_maximum_after = float(np.max(np.abs(occupied_probe_after)))
    return {
        "occupied_result": occupied_result,
        "vacant_converged": vacant_maximum <= tolerance,
        "vacant_sweeps_completed": vacant_sweeps,
        "vacant_rotation_count": sum(bool(item["applied"]) for item in vacant_history),
        "vacant_history": vacant_history,
        "occupied_labels": occupied_names,
        "vacant_labels": vacant_names,
        "initial_block": initial,
        "current_block": current,
        "cumulative_transform": cumulative,
        "initial_full_overlaps": initial_full_overlaps,
        "final_full_overlaps": final_full_overlaps,
        "maximum_vacant_off_target_overlap": vacant_maximum,
        "expected_full_target_magnitude": float(np.linalg.norm(initial_full_overlaps)),
        "final_target_magnitude": abs(float(final_full_overlaps[0])),
        "full_target_maximum_residual": abs(
            abs(float(final_full_overlaps[0])) - float(np.linalg.norm(initial_full_overlaps))
        ),
        "target_magnitude_history": target_magnitudes,
        "monotonic_minimum_increment": min(
            (
                target_magnitudes[index + 1] - target_magnitudes[index]
                for index in range(len(target_magnitudes) - 1)
            ),
            default=0.0,
        ),
        "occupied_probe_overlaps_before_vacant": occupied_probe_before,
        "occupied_probe_overlaps_after_vacant": occupied_probe_after,
        "occupied_probe_maximum_before_vacant": occupied_maximum_before,
        "occupied_probe_maximum_after_vacant": occupied_maximum_after,
        "occupied_probe_feedback_maximum_change": float(
            np.max(np.abs(occupied_probe_after - occupied_probe_before))
        ),
        "occupied_probe_reintroduced_above_tolerance": bool(
            occupied_maximum_after > tolerance
        ),
        "target_occupied_metric_overlaps_before_vacant": target_occupied_before,
        "target_occupied_metric_overlaps_after_vacant": target_occupied_after,
        "target_occupied_metric_feedback_maximum_change": float(
            np.max(np.abs(target_occupied_after - target_occupied_before))
        ),
        "occupied_coefficient_feedback_residual": float(
            np.linalg.norm(
                occupied_coefficients_after - occupied_coefficients_before, ord="fro"
            )
        ),
        "reconstruction_residual": float(
            np.linalg.norm(reconstructed - initial, ord="fro") / coefficient_scale
        ),
        "cumulative_orthogonality_residual": float(
            np.linalg.norm(
                cumulative.T @ cumulative - np.eye(cumulative.shape[0]), ord="fro"
            )
        ),
        "metric_covariance_residual": float(
            np.linalg.norm(current_gram - expected_gram, ord="fro") / gram_scale
        ),
        "initial_gram": initial_gram,
        "current_gram": current_gram,
    }


def bounded_alternating_kost(
    target: np.ndarray,
    occupied_auxiliaries: np.ndarray,
    vacant_auxiliaries: np.ndarray,
    probe: np.ndarray,
    metric: np.ndarray,
    *,
    occupied_labels: list[int] | None = None,
    vacant_labels: list[int] | None = None,
    tolerance: float = 1.0e-10,
    maximum_cycles: int = 3,
    occupied_maximum_sweeps: int = 8,
    monotonic_tolerance: float = 1.0e-12,
) -> dict[str, Any]:
    """Run bounded occupied/vacant cycles with a measured return trigger.

    Each cycle runs the passed occupied loop and exactly one vacant sweep.  A
    return edge is requested only when the vacant sweep changes any
    target--occupied AO-metric overlap by more than ``tolerance``.  The trigger
    is incremental: it detects feedback caused by that vacant sub-loop and does
    not claim that the next occupied sub-loop repairs the metric coupling.
    """

    if maximum_cycles < 0:
        raise ValueError("maximum_cycles must be nonnegative")
    target_column = _column(target, "target")
    probe_column = _column(probe, "probe")
    occupied = np.asarray(occupied_auxiliaries, dtype=float)
    vacant = np.asarray(vacant_auxiliaries, dtype=float)
    if occupied.ndim == 1:
        occupied = occupied[:, None]
    if vacant.ndim == 1:
        vacant = vacant[:, None]
    for block, name in (
        (occupied, "occupied_auxiliaries"),
        (vacant, "vacant_auxiliaries"),
    ):
        if (
            block.ndim != 2
            or block.shape[0] != target_column.shape[0]
            or block.shape[1] == 0
            or not np.all(np.isfinite(block))
        ):
            raise ValueError(f"{name} must be a finite nonempty coefficient block")
    if probe_column.shape[0] != target_column.shape[0]:
        raise ValueError("target, auxiliary blocks, and probe must share an AO dimension")
    if tolerance < 0.0 or monotonic_tolerance < 0.0:
        raise ValueError("tolerances must be nonnegative")

    overlap = _metric(metric, target_column.shape[0])
    occupied_names = (
        list(range(occupied.shape[1]))
        if occupied_labels is None
        else [int(value) for value in occupied_labels]
    )
    vacant_names = (
        list(range(vacant.shape[1]))
        if vacant_labels is None
        else [int(value) for value in vacant_labels]
    )
    if len(occupied_names) != occupied.shape[1] or len(set(occupied_names)) != len(occupied_names):
        raise ValueError("occupied_labels must be unique and match the occupied count")
    if len(vacant_names) != vacant.shape[1] or len(set(vacant_names)) != len(vacant_names):
        raise ValueError("vacant_labels must be unique and match the vacant count")
    if set(occupied_names) & set(vacant_names):
        raise ValueError("occupied and vacant labels must be disjoint")

    initial = np.column_stack((target_column[:, 0], occupied, vacant))
    if np.linalg.matrix_rank(initial) != initial.shape[1]:
        raise ValueError("the combined target/occupied/vacant block must be linearly independent")
    occupied_width = 1 + occupied.shape[1]
    occupied_positions = list(range(occupied_width))
    vacant_positions = [0, *range(occupied_width, initial.shape[1])]
    current = initial.copy()
    cumulative = np.eye(initial.shape[1])
    history: list[dict[str, Any]] = []
    return_edge_count = 0
    converged = False
    cap_exhausted = maximum_cycles == 0

    for cycle in range(1, maximum_cycles + 1):
        occupied_result = occupied_kost_loop(
            current[:, [0]],
            current[:, 1:occupied_width],
            probe_column,
            overlap,
            auxiliary_labels=occupied_names,
            tolerance=tolerance,
            maximum_sweeps=occupied_maximum_sweeps,
            monotonic_tolerance=monotonic_tolerance,
        )
        occupied_embedded = np.eye(initial.shape[1])
        occupied_embedded[np.ix_(occupied_positions, occupied_positions)] = occupied_result[
            "cumulative_transform"
        ]
        current = current @ occupied_embedded
        cumulative = cumulative @ occupied_embedded
        vacant_metric_feedback_before = (
            current[:, [0]].T @ overlap @ current[:, occupied_width:]
        )[0]

        vacant_result = occupied_kost_loop(
            current[:, [0]],
            current[:, occupied_width:],
            probe_column,
            overlap,
            auxiliary_labels=vacant_names,
            tolerance=tolerance,
            maximum_sweeps=1,
            monotonic_tolerance=monotonic_tolerance,
        )
        vacant_embedded = np.eye(initial.shape[1])
        vacant_embedded[np.ix_(vacant_positions, vacant_positions)] = vacant_result[
            "cumulative_transform"
        ]
        target_occupied_before = (
            current[:, [0]].T @ overlap @ current[:, 1:occupied_width]
        )[0]
        current = current @ vacant_embedded
        cumulative = cumulative @ vacant_embedded
        target_occupied_after = (
            current[:, [0]].T @ overlap @ current[:, 1:occupied_width]
        )[0]
        occupied_feedback = float(
            np.max(np.abs(target_occupied_after - target_occupied_before))
        )
        vacant_metric_feedback_after = (
            current[:, [0]].T @ overlap @ current[:, occupied_width:]
        )[0]
        vacant_feedback = float(
            np.max(np.abs(vacant_metric_feedback_after - vacant_metric_feedback_before))
        )
        full_probe_overlaps = (current.T @ overlap @ probe_column)[:, 0]
        maximum_occupied_probe = float(
            np.max(np.abs(full_probe_overlaps[1:occupied_width]))
        )
        maximum_vacant_probe = float(
            np.max(np.abs(full_probe_overlaps[occupied_width:]))
        )
        return_required = occupied_feedback > tolerance
        history.append(
            {
                "cycle": cycle,
                "occupied_sweeps": occupied_result["sweeps_completed"],
                "occupied_rotations": occupied_result["rotation_count"],
                "vacant_sweeps": vacant_result["sweeps_completed"],
                "vacant_rotations": vacant_result["rotation_count"],
                "maximum_occupied_probe_overlap": maximum_occupied_probe,
                "maximum_vacant_probe_overlap": maximum_vacant_probe,
                "target_occupied_feedback": occupied_feedback,
                "target_vacant_feedback": vacant_feedback,
                "return_required": bool(return_required),
            }
        )
        if not return_required:
            converged = (
                maximum_occupied_probe <= tolerance
                and maximum_vacant_probe <= tolerance
            )
            break
        if cycle < maximum_cycles:
            return_edge_count += 1
        else:
            cap_exhausted = True

    final_probe_overlaps = (current.T @ overlap @ probe_column)[:, 0]
    reconstructed = current @ cumulative.T
    initial_gram = initial.T @ overlap @ initial
    current_gram = current.T @ overlap @ current
    expected_gram = cumulative.T @ initial_gram @ cumulative
    coefficient_scale = max(float(np.linalg.norm(initial, ord="fro")), 1.0)
    gram_scale = max(float(np.linalg.norm(current_gram, ord="fro")), 1.0)
    maximum_occupied_probe = float(
        np.max(np.abs(final_probe_overlaps[1:occupied_width]))
    )
    maximum_vacant_probe = float(
        np.max(np.abs(final_probe_overlaps[occupied_width:]))
    )
    final_target_occupied = (
        current[:, [0]].T @ overlap @ current[:, 1:occupied_width]
    )[0]
    return {
        "converged": bool(converged),
        "scheduler_quiescent": bool(converged),
        "joint_physical_convergence_claimed": False,
        "cap_exhausted": bool(cap_exhausted),
        "cycles_completed": len(history),
        "return_edge_count": return_edge_count,
        "history": history,
        "occupied_labels": occupied_names,
        "vacant_labels": vacant_names,
        "initial_block": initial,
        "current_block": current,
        "cumulative_transform": cumulative,
        "initial_probe_overlaps": (initial.T @ overlap @ probe_column)[:, 0],
        "final_probe_overlaps": final_probe_overlaps,
        "maximum_occupied_probe_overlap": maximum_occupied_probe,
        "maximum_vacant_probe_overlap": maximum_vacant_probe,
        "final_target_magnitude": abs(float(final_probe_overlaps[0])),
        "maximum_observed_occupied_feedback": max(
            (float(item["target_occupied_feedback"]) for item in history),
            default=float("nan"),
        ),
        "maximum_observed_vacant_feedback": max(
            (float(item["target_vacant_feedback"]) for item in history),
            default=float("nan"),
        ),
        "final_target_occupied_metric_overlaps": final_target_occupied,
        "final_maximum_target_occupied_metric_overlap": float(
            np.max(np.abs(final_target_occupied))
        ),
        "reconstruction_residual": float(
            np.linalg.norm(reconstructed - initial, ord="fro") / coefficient_scale
        ),
        "cumulative_orthogonality_residual": float(
            np.linalg.norm(
                cumulative.T @ cumulative - np.eye(cumulative.shape[0]), ord="fro"
            )
        ),
        "metric_covariance_residual": float(
            np.linalg.norm(current_gram - expected_gram, ord="fro") / gram_scale
        ),
        "initial_gram": initial_gram,
        "current_gram": current_gram,
    }


def bounded_multi_target_kost(
    targets: np.ndarray,
    occupied_auxiliaries: np.ndarray,
    vacant_auxiliaries: np.ndarray,
    probes: np.ndarray,
    metric: np.ndarray,
    *,
    tolerance: float = 1.0e-10,
    maximum_macro_cycles: int = 12,
    single_target_maximum_cycles: int = 3,
    occupied_maximum_sweeps: int = 8,
    monotonic_tolerance: float = 1.0e-12,
) -> dict[str, Any]:
    """Alternate the accepted one-target KOST scheduler over fixed cut IDs.

    The column order is ``targets, occupied auxiliaries, vacant auxiliaries``.
    A target is never mixed with another target; each local update only rotates
    that target against the shared auxiliary columns.  Macro iteration stops
    when every auxiliary is orthogonal, in the physical AO metric, to every
    fixed reference probe.
    """

    target_block = np.asarray(targets, dtype=float)
    probe_block = np.asarray(probes, dtype=float)
    occupied = np.asarray(occupied_auxiliaries, dtype=float)
    vacant = np.asarray(vacant_auxiliaries, dtype=float)
    if target_block.ndim != 2 or target_block.shape[1] < 2:
        raise ValueError("targets must contain at least two columns")
    if probe_block.shape != target_block.shape:
        raise ValueError("probes must have the same shape as targets")
    if occupied.ndim != 2 or vacant.ndim != 2:
        raise ValueError("auxiliary blocks must be matrices")
    if occupied.shape[0] != target_block.shape[0] or vacant.shape[0] != target_block.shape[0]:
        raise ValueError("targets and auxiliaries must share an AO dimension")
    if maximum_macro_cycles < 0:
        raise ValueError("maximum_macro_cycles must be nonnegative")

    overlap = _metric(metric, target_block.shape[0])
    initial = np.column_stack((target_block, occupied, vacant))
    if np.linalg.matrix_rank(initial) != initial.shape[1]:
        raise ValueError("the combined target/auxiliary block must be linearly independent")
    target_count = target_block.shape[1]
    occupied_positions = list(range(target_count, target_count + occupied.shape[1]))
    vacant_positions = list(range(target_count + occupied.shape[1], initial.shape[1]))
    current = initial.copy()
    cumulative = np.eye(initial.shape[1])
    history: list[dict[str, Any]] = []
    converged = False

    for macro_cycle in range(1, maximum_macro_cycles + 1):
        target_updates: list[dict[str, Any]] = []
        for target_index in range(target_count):
            positions = [target_index, *occupied_positions, *vacant_positions]
            update = bounded_alternating_kost(
                current[:, [target_index]],
                current[:, occupied_positions],
                current[:, vacant_positions],
                probe_block[:, [target_index]],
                overlap,
                occupied_labels=list(range(occupied.shape[1])),
                vacant_labels=list(
                    range(occupied.shape[1], occupied.shape[1] + vacant.shape[1])
                ),
                tolerance=tolerance,
                maximum_cycles=single_target_maximum_cycles,
                occupied_maximum_sweeps=occupied_maximum_sweeps,
                monotonic_tolerance=monotonic_tolerance,
            )
            embedded = np.eye(initial.shape[1])
            embedded[np.ix_(positions, positions)] = update["cumulative_transform"]
            current = current @ embedded
            cumulative = cumulative @ embedded
            target_updates.append(
                {
                    "target_index": target_index,
                    "cycles_completed": update["cycles_completed"],
                    "scheduler_quiescent": update["scheduler_quiescent"],
                }
            )

        auxiliary_positions = [*occupied_positions, *vacant_positions]
        auxiliary_probe = current[:, auxiliary_positions].T @ overlap @ probe_block
        maximum_auxiliary_probe = float(np.max(np.abs(auxiliary_probe)))
        history.append(
            {
                "macro_cycle": macro_cycle,
                "maximum_auxiliary_probe_overlap": maximum_auxiliary_probe,
                "target_updates": target_updates,
            }
        )
        if maximum_auxiliary_probe <= tolerance:
            converged = True
            break

    auxiliary_positions = [*occupied_positions, *vacant_positions]
    final_auxiliary_probe = current[:, auxiliary_positions].T @ overlap @ probe_block
    gram = current.T @ overlap @ current
    initial_gram = initial.T @ overlap @ initial
    expected_gram = cumulative.T @ initial_gram @ cumulative
    return {
        "converged": converged,
        "scheduler_quiescent": converged,
        "cap_exhausted": not converged,
        "macro_cycles_completed": len(history),
        "history": history,
        "current_block": current,
        "cumulative_transform": cumulative,
        "target_count": target_count,
        "occupied_count": occupied.shape[1],
        "vacant_count": vacant.shape[1],
        "final_auxiliary_probe_overlaps": final_auxiliary_probe,
        "maximum_auxiliary_probe_overlap": float(
            np.max(np.abs(final_auxiliary_probe))
        ),
        "target_probe_overlap_matrix": current[:, :target_count].T @ overlap @ probe_block,
        "metric_covariance_residual": float(
            np.linalg.norm(gram - expected_gram, ord="fro")
            / max(float(np.linalg.norm(gram, ord="fro")), 1.0)
        ),
        "orthonormality_residual": float(
            np.linalg.norm(gram - np.eye(gram.shape[0]), ord="fro")
        ),
    }
