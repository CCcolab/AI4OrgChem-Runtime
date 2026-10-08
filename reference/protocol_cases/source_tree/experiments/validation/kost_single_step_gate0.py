"""Apply one public-equation Kost rotation to the passed CH3/reference-H prototype."""

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
except ImportError:  # pragma: no cover - scientific execution is Linux/WSL.
    resource = None

from ai4orgchem.lfmo.kost import rotate_to_fixed_probe
from experiments.validation.one_cut_ch3_reference_h_gate0 import (
    ao_indices_for_atoms,
    canonical_geometry,
    load_yaml,
    reference_h_position,
    run_fragment_uhf,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs" / "qm" / "kost_rotation_v0.1.yaml"


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


def normalized_residual(numerator: np.ndarray, denominator: np.ndarray) -> float:
    return float(
        np.linalg.norm(numerator, ord="fro")
        / max(float(np.linalg.norm(denominator, ord="fro")), 1.0)
    )


def build_input_spaces(config: dict[str, Any]) -> dict[str, Any]:
    from pyscf import gto

    pair_config = load_yaml(ROOT / config["input_pair_config"])
    fragment_config = load_yaml(ROOT / pair_config["fragment_reference_config"])
    fragment_atoms = fragment_config["geometry"]["atoms"]
    fragment_settings = {
        **fragment_config["electronic_structure"],
        **fragment_config["scf"],
    }
    reference_position = reference_h_position(fragment_atoms, pair_config["cut_geometry"])
    reference_atoms = [["H", *reference_position.tolist()]]
    reference_settings = pair_config["reference_hydrogen"]
    singly_window = pair_config["orbital_selection"]["singly_occupied_window"]
    fragment = run_fragment_uhf(fragment_atoms, fragment_settings, singly_window)
    reference = run_fragment_uhf(reference_atoms, reference_settings, singly_window)
    if len(fragment["candidate_indices"]) != 1 or len(reference["candidate_indices"]) != 1:
        raise RuntimeError("the passed unique CH3/reference-H SOMO pair was not reproduced")

    composite_atoms = [*fragment_atoms, *reference_atoms]
    composite = gto.M(
        atom=canonical_geometry(composite_atoms),
        basis=fragment_settings["basis"],
        charge=0,
        spin=0,
        unit="Angstrom",
        symmetry=False,
        verbose=0,
    )
    overlap = composite.intor_symmetric("int1e_ovlp")
    fragment_indices = ao_indices_for_atoms(
        composite, pair_config["embedding"]["fragment_atom_indices"]
    )
    reference_indices = ao_indices_for_atoms(
        composite, pair_config["embedding"]["reference_hydrogen_atom_indices"]
    )
    fragment_coefficients = np.zeros(
        (composite.nao_nr(), fragment["natural_coefficients"].shape[1])
    )
    fragment_coefficients[fragment_indices, :] = fragment["natural_coefficients"]
    probe = np.zeros((composite.nao_nr(), 1))
    probe[reference_indices, :] = reference["somo"]
    return {
        "pair_config": pair_config,
        "fragment_config": fragment_config,
        "fragment": fragment,
        "reference": reference,
        "composite": composite,
        "composite_atoms": composite_atoms,
        "overlap": overlap,
        "fragment_indices": fragment_indices,
        "reference_indices": reference_indices,
        "fragment_coefficients": fragment_coefficients,
        "probe": probe,
    }


def select_auxiliary(
    fragment_coefficients: np.ndarray,
    probe: np.ndarray,
    metric: np.ndarray,
    target_index: int,
) -> dict[str, Any]:
    overlaps = fragment_coefficients.T @ metric @ probe
    eligible = [index for index in range(fragment_coefficients.shape[1]) if index != target_index]
    auxiliary_index = max(eligible, key=lambda index: (abs(float(overlaps[index, 0])), -index))
    ranked = sorted(
        (
            {"index": int(index), "signed_overlap": float(overlaps[index, 0]), "absolute_overlap": abs(float(overlaps[index, 0]))}
            for index in eligible
        ),
        key=lambda item: (-item["absolute_overlap"], item["index"]),
    )
    return {
        "target_index": int(target_index),
        "auxiliary_index": int(auxiliary_index),
        "target_signed_overlap": float(overlaps[target_index, 0]),
        "auxiliary_signed_overlap": float(overlaps[auxiliary_index, 0]),
        "ranked_auxiliary_overlaps": ranked,
    }


def phase_audit(
    target: np.ndarray,
    auxiliary: np.ndarray,
    probe: np.ndarray,
    metric: np.ndarray,
) -> dict[str, float]:
    reference = rotate_to_fixed_probe(target, auxiliary, probe, metric)
    reference_eigenvalues = np.linalg.eigvalsh(reference["rotated_gram"])
    reference_condition = float(np.linalg.cond(reference["rotated_gram"]))
    target_errors: list[float] = []
    off_target_residuals: list[float] = []
    eigenvalue_errors: list[float] = []
    condition_errors: list[float] = []
    reconstruction_residuals: list[float] = []
    for target_sign in (-1.0, 1.0):
        for auxiliary_sign in (-1.0, 1.0):
            for probe_sign in (-1.0, 1.0):
                result = rotate_to_fixed_probe(
                    target_sign * target,
                    auxiliary_sign * auxiliary,
                    probe_sign * probe,
                    metric,
                )
                target_errors.append(
                    abs(abs(result["achieved_target_overlap"]) - abs(reference["achieved_target_overlap"]))
                )
                off_target_residuals.append(result["off_target_overlap_residual"])
                eigenvalue_errors.append(
                    float(
                        np.max(
                            np.abs(
                                np.linalg.eigvalsh(result["rotated_gram"])
                                - reference_eigenvalues
                            )
                        )
                    )
                )
                condition_errors.append(
                    abs(float(np.linalg.cond(result["rotated_gram"])) - reference_condition)
                )
                reconstruction_residuals.append(result["reconstruction_residual"])
    return {
        "maximum_target_magnitude_error": max(target_errors),
        "maximum_off_target_overlap_residual": max(off_target_residuals),
        "maximum_gram_eigenvalue_error": max(eigenvalue_errors),
        "maximum_gram_condition_error": max(condition_errors),
        "maximum_reconstruction_residual": max(reconstruction_residuals),
    }


def run_experiment(config: dict[str, Any]) -> dict[str, Any]:
    from pyscf import __version__ as pyscf_version

    started = time.perf_counter()
    spaces = build_input_spaces(config)
    fragment = spaces["fragment"]
    target_index = int(fragment["candidate_indices"][0])
    selection = select_auxiliary(
        spaces["fragment_coefficients"], spaces["probe"], spaces["overlap"], target_index
    )
    target = spaces["fragment_coefficients"][:, [target_index]]
    auxiliary = spaces["fragment_coefficients"][:, [selection["auxiliary_index"]]]
    result = rotate_to_fixed_probe(target, auxiliary, spaces["probe"], spaces["overlap"])
    phase = phase_audit(target, auxiliary, spaces["probe"], spaces["overlap"])
    rotated_pair = np.column_stack(
        (result["rotated_target"][:, 0], result["rotated_auxiliary"][:, 0])
    )
    outside = np.ones(rotated_pair.shape[0], dtype=bool)
    outside[spaces["fragment_indices"]] = False
    outside_support_max = float(np.max(np.abs(rotated_pair[outside, :])))
    initial_gram_eigenvalues = np.linalg.eigvalsh(result["initial_gram"])
    rotated_gram_eigenvalues = np.linalg.eigvalsh(result["rotated_gram"])
    gram_eigenvalue_residual = float(
        np.max(np.abs(initial_gram_eigenvalues - rotated_gram_eigenvalues))
    )
    tolerance = config["acceptance"]
    checks = {
        "passed_pair_reproduced": fragment["converged"]
        and spaces["reference"]["converged"]
        and len(fragment["candidate_indices"]) == 1
        and len(spaces["reference"]["candidate_indices"]) == 1,
        "auxiliary_selection_nonzero": abs(selection["auxiliary_signed_overlap"]) > 1.0e-14,
        "off_target_overlap_cancelled": result["off_target_overlap_residual"]
        <= float(tolerance["off_target_overlap_tolerance"]),
        "target_overlap_maximized": result["target_maximum_residual"]
        <= float(tolerance["target_maximum_residual_tolerance"]),
        "stationary_condition": result["stationary_derivative_residual"]
        <= float(tolerance["stationary_condition_tolerance"]),
        "coefficient_reconstruction": result["reconstruction_residual"]
        <= float(tolerance["reconstruction_residual_tolerance"]),
        "metric_covariance": result["metric_covariance_residual"]
        <= float(tolerance["metric_preservation_tolerance"]),
        "gram_spectrum_preserved": gram_eigenvalue_residual
        <= float(tolerance["metric_preservation_tolerance"]),
        "strict_fragment_support_preserved": outside_support_max <= 1.0e-10,
        "phase_invariance": max(phase.values())
        <= float(tolerance["phase_invariance_tolerance"]),
        "single_step_only": config["rotation"]["iteration_enabled"] is False,
        "no_production_labels": config["production_labels_allowed"] is False,
    }
    peak_rss_mib = (
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
        if resource is not None
        else float("nan")
    )
    return {
        "schema": "ai4orgchem-kost-single-step/1.0",
        "date": date.today().isoformat(),
        "classification": "non-production public-equation algebra validation",
        "disposition": "PASS" if all(checks.values()) else "QUARANTINE",
        "checks": checks,
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pyscf": pyscf_version,
            "platform": platform.platform(),
        },
        "input": {
            "fragment_natural_occupations": fragment["natural_occupations"].tolist(),
            "selection": selection,
            "fixed_probe": "reference_hydrogen_natural_somo",
            "composite_geometry": canonical_geometry(spaces["composite_atoms"]),
        },
        "rotation": {
            "angle_radians": result["angle_radians"],
            "angle_degrees": result["angle_degrees"],
            "cosine": result["cosine"],
            "sine": result["sine"],
            "transform": result["transform"].tolist(),
            "initial_target_overlap": result["initial_target_overlap"],
            "initial_auxiliary_overlap": result["initial_auxiliary_overlap"],
            "overlap_vector_norm": result["overlap_vector_norm"],
            "achieved_target_overlap": result["achieved_target_overlap"],
            "achieved_auxiliary_overlap": result["achieved_auxiliary_overlap"],
            "target_maximum_residual": result["target_maximum_residual"],
            "off_target_overlap_residual": result["off_target_overlap_residual"],
            "stationary_derivative_residual": result["stationary_derivative_residual"],
            "transform_orthogonality_residual": result[
                "transform_orthogonality_residual"
            ],
            "reconstruction_residual": result["reconstruction_residual"],
            "metric_covariance_residual": result["metric_covariance_residual"],
            "initial_gram": result["initial_gram"].tolist(),
            "rotated_gram": result["rotated_gram"].tolist(),
            "gram_eigenvalue_residual": gram_eigenvalue_residual,
            "outside_fragment_support_max": outside_support_max,
        },
        "phase_audit": phase,
        "provenance": {
            "rotation_protocol_id": config["rotation_protocol_id"],
            "parent_protocol": config["parent_protocol"],
            "input_pair_config": config["input_pair_config"],
            "specification": config["specification"],
            "source_equations": config["source_equations"],
            "config_hash": sha256_text(json.dumps(config, ensure_ascii=False, sort_keys=True)),
            "input_geometry_hash": sha256_text(canonical_geometry(spaces["composite_atoms"])),
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
            "single_rotation_only": True,
            "iterative_kost_loops_run": False,
            "composite_scf_run": False,
            "conditional_fragment_scf_run": False,
            "dsi_fud_run": False,
            "scientific_energy_labels_generated": False,
            "prohibited_operations": config["prohibited_operations"],
        },
    }


def json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        if math.isnan(value):
            return "NaN"
        return "Infinity" if value > 0.0 else "-Infinity"
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def render_markdown(report: dict[str, Any]) -> str:
    rotation = report["rotation"]
    selection = report["input"]["selection"]
    checks = report["checks"]
    rows = [
        ("Fragment target/auxiliary indices", f"{selection['target_index']} / {selection['auxiliary_index']}", checks["auxiliary_selection_nonzero"]),
        ("Initial target/auxiliary overlaps", f"{rotation['initial_target_overlap']:.12f} / {rotation['initial_auxiliary_overlap']:.12f}", True),
        ("Rotation angle", f"{rotation['angle_degrees']:.10f} deg", True),
        ("Achieved target overlap", f"{rotation['achieved_target_overlap']:.12f}", checks["target_overlap_maximized"]),
        ("Off-target overlap", f"{rotation['achieved_auxiliary_overlap']:.3e}", checks["off_target_overlap_cancelled"]),
        ("Reconstruction residual", f"{rotation['reconstruction_residual']:.3e}", checks["coefficient_reconstruction"]),
        ("Metric covariance residual", f"{rotation['metric_covariance_residual']:.3e}", checks["metric_covariance"]),
        ("Outside-fragment support", f"{rotation['outside_fragment_support_max']:.3e}", checks["strict_fragment_support_preserved"]),
    ]
    lines = [
        "# Gate 0 single-step Kost rotation validation",
        "",
        f"- Date: {report['date']}",
        f"- Disposition: **{report['disposition']}**",
        "- Classification: non-production public-equation algebra evidence",
        "- Iterative Kost loops, composite SCF, and conditional SCF run: no",
        "- Scientific energy label generated: no",
        f"- Runtime: Python `{report['runtime']['python']}`, PySCF `{report['runtime']['pyscf']}`, NumPy `{report['runtime']['numpy']}`",
        "",
        "## Result",
        "",
        "| Diagnostic | Value | Check |",
        "|---|---:|---|",
    ]
    lines.extend(f"| {name} | {value} | {'PASS' if passed else 'FAIL'} |" for name, value, passed in rows)
    lines.extend(
        [
            "",
            "## Equation and phase diagnostics",
            "",
            f"- Overlap-vector norm / analytic maximum: `{rotation['overlap_vector_norm']:.12f}`.",
            f"- Target-maximum residual: `{rotation['target_maximum_residual']:.3e}`.",
            f"- Stationary derivative residual: `{rotation['stationary_derivative_residual']:.3e}`.",
            f"- Transform orthogonality residual: `{rotation['transform_orthogonality_residual']:.3e}`.",
            f"- Gram-spectrum residual: `{rotation['gram_eigenvalue_residual']:.3e}`.",
            f"- Maximum phase-audit residual: `{max(report['phase_audit'].values()):.3e}`.",
            "",
            "## Interpretation boundary",
            "",
            "The public equations keep the reference-H SOMO fixed and rotate two CH3",
            "orbitals. The auxiliary used here is the non-SOMO CH3 natural orbital with",
            "the largest absolute probe overlap. This deterministic one-step prototype",
            "cancels that auxiliary overlap and transfers its magnitude to the target",
            "SOMO exactly within floating-point precision. It validates the two-orbital",
            "algebra only. It does not implement the source's alternating occupied/vacant",
            "loops, conditional SCF, a complete LFMO basis, or an energy decomposition.",
            "",
            "## Provenance and resources",
            "",
            f"- Rotation protocol: `{report['provenance']['rotation_protocol_id']}`.",
            f"- Source equations: `{report['provenance']['source_equations']['equation_ids']}`.",
            f"- Input geometry SHA-256: `{report['provenance']['input_geometry_hash']}`.",
            f"- Config SHA-256: `{report['provenance']['config_hash']}`.",
            f"- Code commit at run: `{report['provenance']['code_commit']}`.",
            f"- Resource profile: `{report['provenance']['resource_profile']}`.",
            f"- Wall time: `{report['resources']['wall_time_seconds']:.6f} s`.",
            f"- Peak RSS: `{report['resources']['peak_rss_mib']:.3f} MiB`.",
            f"- Threads: `{report['resources']['thread_count']}`.",
            "",
        ]
    )
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
        f"{report['disposition']}: target/aux="
        f"{report['input']['selection']['target_index']}/"
        f"{report['input']['selection']['auxiliary_index']} "
        f"initial={report['rotation']['initial_target_overlap']:.12f}/"
        f"{report['rotation']['initial_auxiliary_overlap']:.12f} "
        f"final={report['rotation']['achieved_target_overlap']:.12f}/"
        f"{report['rotation']['achieved_auxiliary_overlap']:.3e}"
    )
    return 0 if report["disposition"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
