"""Run the passed occupied loop followed by one vacant Kost sweep."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import time
from typing import Any

import numpy as np
import yaml

try:
    import resource
except ImportError:  # pragma: no cover
    resource = None

from ai4orgchem.lfmo.kost import occupied_then_vacant_kost
from experiments.validation.kost_single_step_gate0 import build_input_spaces
from experiments.validation.one_cut_ch3_reference_h_gate0 import canonical_geometry


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs" / "qm" / "kost_vacant_loop_v0.1.yaml"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def git_commit() -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def occupation_partition(
    occupations: np.ndarray,
    target_window: list[float],
    occupied_window: list[float],
    vacant_window: list[float],
) -> tuple[int, list[int], list[int]]:
    windows = [tuple(map(float, window)) for window in (target_window, occupied_window, vacant_window)]
    memberships: list[list[int]] = []
    for lower, upper in windows:
        memberships.append(
            [int(index) for index, value in enumerate(occupations) if lower <= float(value) <= upper]
        )
    targets, occupied, vacant = memberships
    if len(targets) != 1:
        raise ValueError("occupation metadata does not define exactly one target")
    flattened = [*targets, *occupied, *vacant]
    if len(flattened) != len(set(flattened)):
        raise ValueError("occupation windows overlap")
    if sorted(flattened) != list(range(len(occupations))):
        raise ValueError("occupation windows do not classify every orbital")
    if not occupied or not vacant:
        raise ValueError("occupation metadata defines an empty occupied or vacant block")
    return targets[0], occupied, vacant


def run_combined(
    target: np.ndarray,
    occupied: np.ndarray,
    vacant: np.ndarray,
    probe: np.ndarray,
    metric: np.ndarray,
    occupied_labels: list[int],
    vacant_labels: list[int],
    config: dict[str, Any],
    *,
    vacant_sweeps: int = 1,
) -> dict[str, Any]:
    return occupied_then_vacant_kost(
        target,
        occupied,
        vacant,
        probe,
        metric,
        occupied_labels=occupied_labels,
        vacant_labels=vacant_labels,
        tolerance=float(config["convergence"]["off_target_overlap_tolerance"]),
        occupied_maximum_sweeps=int(config["convergence"]["occupied_maximum_sweeps"]),
        vacant_sweeps=vacant_sweeps,
        monotonic_tolerance=float(config["acceptance"]["monotonic_tolerance"]),
    )


def invariance_audit(
    target: np.ndarray,
    occupied: np.ndarray,
    vacant: np.ndarray,
    probe: np.ndarray,
    metric: np.ndarray,
    occupied_labels: list[int],
    vacant_labels: list[int],
    config: dict[str, Any],
) -> dict[str, float]:
    reference = run_combined(
        target, occupied, vacant, probe, metric, occupied_labels, vacant_labels, config
    )
    reference_target = reference["current_block"][:, [0]]
    reference_projector = reference_target @ reference_target.T
    reference_eigenvalues = np.linalg.eigvalsh(reference["current_gram"])

    occupied_permutation = list(reversed(range(occupied.shape[1])))
    vacant_permutation = list(reversed(range(vacant.shape[1])))
    permuted = run_combined(
        target,
        occupied[:, occupied_permutation],
        vacant[:, vacant_permutation],
        probe,
        metric,
        [occupied_labels[index] for index in occupied_permutation],
        [vacant_labels[index] for index in vacant_permutation],
        config,
    )
    permuted_target = permuted["current_block"][:, [0]]
    occupied_signs = np.array([(-1.0 if index % 2 == 0 else 1.0) for index in occupied_labels])
    vacant_signs = np.array([(-1.0 if index % 2 == 0 else 1.0) for index in vacant_labels])
    phase_changed = run_combined(
        -target,
        occupied * occupied_signs,
        vacant * vacant_signs,
        -probe,
        metric,
        occupied_labels,
        vacant_labels,
        config,
    )
    return {
        "permutation_target_projector_residual": float(
            np.linalg.norm(permuted_target @ permuted_target.T - reference_projector, ord="fro")
        ),
        "permutation_target_magnitude_error": abs(
            permuted["final_target_magnitude"] - reference["final_target_magnitude"]
        ),
        "phase_target_magnitude_error": abs(
            phase_changed["final_target_magnitude"] - reference["final_target_magnitude"]
        ),
        "phase_gram_eigenvalue_error": float(
            np.max(np.abs(np.linalg.eigvalsh(phase_changed["current_gram"]) - reference_eigenvalues))
        ),
        "maximum_variant_vacant_overlap": max(
            permuted["maximum_vacant_off_target_overlap"],
            phase_changed["maximum_vacant_off_target_overlap"],
        ),
    }


def run_experiment(config: dict[str, Any]) -> dict[str, Any]:
    from pyscf import __version__ as pyscf_version

    started = time.perf_counter()
    rotation_config = yaml.safe_load((ROOT / config["rotation_config"]).read_text(encoding="utf-8"))
    spaces = build_input_spaces(rotation_config)
    occupations = spaces["fragment"]["natural_occupations"]
    membership = config["membership"]
    target_index, occupied_indices, vacant_indices = occupation_partition(
        occupations,
        membership["target_occupation_window"],
        membership["occupied_auxiliary_window"],
        membership["vacant_auxiliary_window"],
    )
    coefficients = spaces["fragment_coefficients"]
    target = coefficients[:, [target_index]]
    occupied = coefficients[:, occupied_indices]
    vacant = coefficients[:, vacant_indices]
    result = run_combined(
        target, occupied, vacant, spaces["probe"], spaces["overlap"],
        occupied_indices, vacant_indices, config,
    )
    invariance = invariance_audit(
        target, occupied, vacant, spaces["probe"], spaces["overlap"],
        occupied_indices, vacant_indices, config,
    )
    failure_control = run_combined(
        target, occupied, vacant, spaces["probe"], spaces["overlap"],
        occupied_indices, vacant_indices, config, vacant_sweeps=0,
    )
    outside = np.ones(result["current_block"].shape[0], dtype=bool)
    outside[spaces["fragment_indices"]] = False
    outside_support_max = float(np.max(np.abs(result["current_block"][outside, :])))
    acceptance = config["acceptance"]
    tolerance = float(config["convergence"]["off_target_overlap_tolerance"])
    invariant_limit = float(acceptance["phase_permutation_invariance_tolerance"])
    invariant_residuals = [
        value for key, value in invariance.items() if key != "maximum_variant_vacant_overlap"
    ]
    checks = {
        "membership_partitioned_from_occupations": target_index == 4
        and occupied_indices == [0, 1, 2, 3]
        and vacant_indices == list(range(5, len(occupations))),
        "occupied_stage_converged": result["occupied_result"]["converged"],
        "single_vacant_sweep_converged": result["vacant_converged"],
        "all_vacant_probe_overlaps": result["maximum_vacant_off_target_overlap"] <= tolerance,
        "target_monotonic": result["monotonic_minimum_increment"] >= -float(acceptance["monotonic_tolerance"]),
        "full_target_maximum": result["full_target_maximum_residual"] <= float(acceptance["target_maximum_residual_tolerance"]),
        "combined_reconstruction": result["reconstruction_residual"] <= float(acceptance["reconstruction_residual_tolerance"]),
        "combined_orthogonality": result["cumulative_orthogonality_residual"] <= float(acceptance["cumulative_orthogonality_tolerance"]),
        "metric_covariance": result["metric_covariance_residual"] <= float(acceptance["metric_covariance_tolerance"]),
        "strict_fragment_support": outside_support_max <= float(acceptance["coefficient_support_tolerance"]),
        "occupied_columns_unchanged_during_vacant": result["occupied_coefficient_feedback_residual"] <= float(acceptance["unchanged_occupied_coefficients_tolerance"]),
        "phase_permutation_invariance": max(invariant_residuals) <= invariant_limit,
        "phase_permutation_variants_converged": invariance["maximum_variant_vacant_overlap"] <= tolerance,
        "zero_vacant_sweep_failure_retained": not failure_control["vacant_converged"]
        and failure_control["vacant_sweeps_completed"] == 0
        and failure_control["vacant_rotation_count"] == 0,
        "single_vacant_sweep_only": config["schedule"]["vacant_sweeps"] == 1
        and config["schedule"]["occupied_repair_after_vacant"] is False
        and config["schedule"]["alternating_joint_convergence"] is False,
        "no_production_labels": config["production_labels_allowed"] is False,
    }
    peak_rss_mib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0 if resource is not None else float("nan")
    return {
        "schema": "ai4orgchem-kost-vacant-loop/1.0",
        "date": date.today().isoformat(),
        "classification": "non-production single-vacant-sweep validation",
        "disposition": "PASS" if all(checks.values()) else "QUARANTINE",
        "checks": checks,
        "runtime": {"python": platform.python_version(), "numpy": np.__version__, "pyscf": pyscf_version, "platform": platform.platform()},
        "membership": {
            "natural_occupations": occupations.tolist(),
            "target_index": target_index,
            "occupied_auxiliary_indices": occupied_indices,
            "vacant_auxiliary_indices": vacant_indices,
            "ordering": membership["ordering"],
        },
        "combined_loop": {
            "occupied_sweeps": result["occupied_result"]["sweeps_completed"],
            "occupied_rotations": result["occupied_result"]["rotation_count"],
            "occupied_maximum_probe_overlap": result["occupied_result"]["maximum_off_target_overlap"],
            "vacant_sweeps": result["vacant_sweeps_completed"],
            "vacant_rotations": result["vacant_rotation_count"],
            "vacant_history": result["vacant_history"],
            "initial_full_overlaps": result["initial_full_overlaps"].tolist(),
            "final_full_overlaps": result["final_full_overlaps"].tolist(),
            "maximum_vacant_off_target_overlap": result["maximum_vacant_off_target_overlap"],
            "expected_full_target_magnitude": result["expected_full_target_magnitude"],
            "final_target_magnitude": result["final_target_magnitude"],
            "full_target_maximum_residual": result["full_target_maximum_residual"],
            "target_magnitude_history": result["target_magnitude_history"],
            "monotonic_minimum_increment": result["monotonic_minimum_increment"],
            "cumulative_transform": result["cumulative_transform"].tolist(),
            "reconstruction_residual": result["reconstruction_residual"],
            "cumulative_orthogonality_residual": result["cumulative_orthogonality_residual"],
            "metric_covariance_residual": result["metric_covariance_residual"],
            "outside_fragment_support_max": outside_support_max,
        },
        "feedback": {
            "occupied_probe_overlaps_before_vacant": result["occupied_probe_overlaps_before_vacant"].tolist(),
            "occupied_probe_overlaps_after_vacant": result["occupied_probe_overlaps_after_vacant"].tolist(),
            "occupied_probe_maximum_before_vacant": result["occupied_probe_maximum_before_vacant"],
            "occupied_probe_maximum_after_vacant": result["occupied_probe_maximum_after_vacant"],
            "occupied_probe_feedback_maximum_change": result["occupied_probe_feedback_maximum_change"],
            "occupied_probe_reintroduced_above_tolerance": result["occupied_probe_reintroduced_above_tolerance"],
            "target_occupied_metric_overlaps_before_vacant": result["target_occupied_metric_overlaps_before_vacant"].tolist(),
            "target_occupied_metric_overlaps_after_vacant": result["target_occupied_metric_overlaps_after_vacant"].tolist(),
            "target_occupied_metric_feedback_maximum_change": result["target_occupied_metric_feedback_maximum_change"],
            "target_occupied_metric_reintroduced_above_tolerance": bool(
                np.max(np.abs(result["target_occupied_metric_overlaps_after_vacant"])) > tolerance
            ),
            "occupied_coefficient_feedback_residual": result["occupied_coefficient_feedback_residual"],
            "occupied_repair_run": False,
        },
        "invariance_audit": invariance,
        "failure_control": {
            "vacant_sweeps": 0,
            "vacant_converged": failure_control["vacant_converged"],
            "vacant_rotation_count": failure_control["vacant_rotation_count"],
            "maximum_vacant_off_target_overlap": failure_control["maximum_vacant_off_target_overlap"],
        },
        "provenance": {
            "loop_protocol_id": config["loop_protocol_id"],
            "parent_occupied_protocol": config["parent_occupied_protocol"],
            "specification": config["specification"],
            "config_hash": sha256_text(json.dumps(config, ensure_ascii=False, sort_keys=True)),
            "input_geometry_hash": sha256_text(canonical_geometry(spaces["composite_atoms"])),
            "membership_hash": sha256_text(json.dumps({"target": target_index, "occupied": occupied_indices, "vacant": vacant_indices}, sort_keys=True)),
            "code_commit": git_commit(),
            "resource_profile": spaces["pair_config"]["resources"]["profile"],
        },
        "resources": {
            "wall_time_seconds": time.perf_counter() - started,
            "peak_rss_mib": peak_rss_mib,
            "thread_count": int(os.environ.get("OMP_NUM_THREADS", "1")),
            "output_bytes": 0,
        },
        "boundaries": {
            "occupied_loop_run": True,
            "single_vacant_sweep_run": True,
            "occupied_repair_run": False,
            "alternating_loops_run": False,
            "second_cut_loop_run": False,
            "composite_scf_run": False,
            "conditional_fragment_scf_run": False,
            "dsi_fud_run": False,
            "scientific_energy_labels_generated": False,
            "prohibited_operations": config["prohibited_operations"],
        },
    }


def json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return "NaN" if math.isnan(value) else ("Infinity" if value > 0 else "-Infinity")
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def render_markdown(report: dict[str, Any]) -> str:
    loop = report["combined_loop"]
    feedback = report["feedback"]
    membership = report["membership"]
    lines = [
        "# Gate 0 single-vacant-sweep Kost validation", "",
        f"- Date: {report['date']}",
        f"- Disposition: **{report['disposition']}**",
        "- Classification: non-production occupied-then-one-vacant-sweep evidence",
        "- Occupied repair, joint alternation, and conditional SCF run: no",
        "- Scientific energy label generated: no",
        f"- Runtime: Python `{report['runtime']['python']}`, PySCF `{report['runtime']['pyscf']}`, NumPy `{report['runtime']['numpy']}`", "",
        "## Result", "",
        "| Diagnostic | Value | Check |", "|---|---:|---|",
        f"| Target / occupied / vacant | {membership['target_index']} / {membership['occupied_auxiliary_indices']} / {membership['vacant_auxiliary_indices']} | {'PASS' if report['checks']['membership_partitioned_from_occupations'] else 'FAIL'} |",
        f"| Occupied sweeps / rotations | {loop['occupied_sweeps']} / {loop['occupied_rotations']} | {'PASS' if report['checks']['occupied_stage_converged'] else 'FAIL'} |",
        f"| Vacant sweeps / rotations | {loop['vacant_sweeps']} / {loop['vacant_rotations']} | {'PASS' if report['checks']['single_vacant_sweep_converged'] else 'FAIL'} |",
        f"| Final target magnitude | {loop['final_target_magnitude']:.12f} | {'PASS' if report['checks']['full_target_maximum'] else 'FAIL'} |",
        f"| Maximum vacant probe overlap | {loop['maximum_vacant_off_target_overlap']:.3e} | {'PASS' if report['checks']['all_vacant_probe_overlaps'] else 'FAIL'} |",
        f"| Full-block reconstruction | {loop['reconstruction_residual']:.3e} | {'PASS' if report['checks']['combined_reconstruction'] else 'FAIL'} |",
        f"| Outside-fragment support | {loop['outside_fragment_support_max']:.3e} | {'PASS' if report['checks']['strict_fragment_support'] else 'FAIL'} |", "",
        "## Feedback measured after the vacant sweep", "",
        f"- Occupied-probe maximum before/after: `{feedback['occupied_probe_maximum_before_vacant']:.3e}` / `{feedback['occupied_probe_maximum_after_vacant']:.3e}`.",
        f"- Occupied-probe maximum change: `{feedback['occupied_probe_feedback_maximum_change']:.3e}`; reintroduced above `1e-10`: `{feedback['occupied_probe_reintroduced_above_tolerance']}`.",
        f"- Target-occupied metric maximum change: `{feedback['target_occupied_metric_feedback_maximum_change']:.3e}`; final value above `1e-10`: `{feedback['target_occupied_metric_reintroduced_above_tolerance']}`.",
        f"- Occupied coefficient change: `{feedback['occupied_coefficient_feedback_residual']:.3e}`.",
        "- No occupied repair or return sweep was run.", "",
        "## Cumulative and invariance diagnostics", "",
        f"- Target-magnitude history: `{[round(value, 12) for value in loop['target_magnitude_history']]}`.",
        f"- Cumulative orthogonality residual: `{loop['cumulative_orthogonality_residual']:.3e}`.",
        f"- Metric covariance residual: `{loop['metric_covariance_residual']:.3e}`.",
        f"- Maximum phase/permutation invariant residual: `{max(value for key, value in report['invariance_audit'].items() if key != 'maximum_variant_vacant_overlap'):.3e}`.",
        f"- Maximum variant vacant overlap: `{report['invariance_audit']['maximum_variant_vacant_overlap']:.3e}`.",
        f"- Zero-vacant-sweep control converged: `{report['failure_control']['vacant_converged']}`; retained maximum vacant overlap `{report['failure_control']['maximum_vacant_off_target_overlap']:.6f}`.", "",
        "## Interpretation boundary", "",
        "This experiment validates one vacant sweep only. Whether full alternation",
        "is required is decided from the measured feedback for this prototype; no",
        "return occupied sweep was run. The result is not a complete source-derived",
        "LFMO basis, conditional SCF state, DSI/FUD energy, or production label.", "",
        "## Provenance and resources", "",
        f"- Loop protocol: `{report['provenance']['loop_protocol_id']}`.",
        f"- Input geometry SHA-256: `{report['provenance']['input_geometry_hash']}`.",
        f"- Membership SHA-256: `{report['provenance']['membership_hash']}`.",
        f"- Config SHA-256: `{report['provenance']['config_hash']}`.",
        f"- Code commit at run: `{report['provenance']['code_commit']}`.",
        f"- Resource profile: `{report['provenance']['resource_profile']}`.",
        f"- Wall time: `{report['resources']['wall_time_seconds']:.6f} s`.",
        f"- Peak RSS: `{report['resources']['peak_rss_mib']:.3f} MiB`.",
        f"- Threads: `{report['resources']['thread_count']}`.", "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    report = run_experiment(config)
    serialized = ""
    for _ in range(3):
        serialized = json.dumps(json_safe(report), ensure_ascii=False, indent=2) + "\n"
        report["resources"]["output_bytes"] = len(serialized.encode("utf-8"))
    serialized = json.dumps(json_safe(report), ensure_ascii=False, indent=2) + "\n"
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(serialized, encoding="utf-8", newline="\n")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    print(
        f"{report['disposition']}: target={report['membership']['target_index']} "
        f"vacant={report['membership']['vacant_auxiliary_indices']} "
        f"rotations={report['combined_loop']['vacant_rotations']} "
        f"max_vacant={report['combined_loop']['maximum_vacant_off_target_overlap']:.3e} "
        f"metric_feedback={report['feedback']['target_occupied_metric_feedback_maximum_change']:.3e}"
    )
    return 0 if report["disposition"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
