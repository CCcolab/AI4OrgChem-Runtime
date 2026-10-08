"""Validate a CH3/reference-H open-shell coefficient pair without Kost or SCF coupling."""

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

from ai4orgchem.lfmo.subspaces import subspace_leakage


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs" / "qm" / "one_cut_ch3_reference_h_v0.1.yaml"


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


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def canonical_geometry(atoms: list[list[Any]]) -> str:
    return "\n".join(
        f"{symbol} {float(x):.10f} {float(y):.10f} {float(z):.10f}"
        for symbol, x, y, z in atoms
    )


def reference_h_position(
    fragment_atoms: list[list[Any]], cut_geometry: dict[str, Any]
) -> np.ndarray:
    origin_row = fragment_atoms[int(cut_geometry["origin_fragment_atom_index"])]
    origin = np.asarray(origin_row[1:], dtype=float)
    direction = np.asarray(cut_geometry["direction"], dtype=float)
    norm = float(np.linalg.norm(direction))
    if not np.isfinite(norm) or norm <= 0.0:
        raise ValueError("cut direction must be a finite nonzero vector")
    direction = direction / norm
    distance = float(cut_geometry["reference_hydrogen_distance_angstrom"])
    return origin + distance * direction


def normalized_residual(numerator: np.ndarray, denominator: np.ndarray) -> float:
    return float(
        np.linalg.norm(numerator, ord="fro")
        / max(float(np.linalg.norm(denominator, ord="fro")), 1.0)
    )


def run_fragment_uhf(
    atoms: list[list[Any]], settings: dict[str, Any], singly_window: list[float]
) -> dict[str, Any]:
    from pyscf import gto, scf
    from pyscf.mcscf.addons import make_natural_orbitals

    molecule = gto.M(
        atom=canonical_geometry(atoms),
        basis=settings["basis"],
        charge=int(settings["charge"]),
        spin=int(settings["multiplicity"]) - 1,
        unit="Angstrom",
        symmetry=False,
        verbose=0,
    )
    cycles: list[int] = []

    def record_cycle(environment: dict[str, Any]) -> None:
        cycles.append(int(environment.get("cycle", len(cycles))) + 1)

    mean_field = scf.UHF(molecule)
    mean_field.conv_tol = float(settings["convergence_tolerance"])
    mean_field.max_cycle = int(settings["max_cycles"])
    mean_field.init_guess = str(settings["initial_guess"])
    mean_field.callback = record_cycle
    mean_field.kernel()

    natural_occupations, natural_coefficients = make_natural_orbitals(mean_field)
    lower, upper = map(float, singly_window)
    candidates = [
        int(index)
        for index, occupation in enumerate(natural_occupations)
        if lower <= float(occupation) <= upper
    ]
    somo = natural_coefficients[:, candidates] if len(candidates) == 1 else None
    alpha_occupations, beta_occupations = mean_field.mo_occ
    alpha_count = int(np.count_nonzero(alpha_occupations > 0.5))
    beta_count = int(np.count_nonzero(beta_occupations > 0.5))
    spin_square, effective_multiplicity = map(float, mean_field.spin_square())
    return {
        "molecule": molecule,
        "overlap": mean_field.get_ovlp(),
        "converged": bool(mean_field.converged),
        "cycles": max(cycles, default=0),
        "alpha_electrons": alpha_count,
        "beta_electrons": beta_count,
        "spin_square": spin_square,
        "spin_contamination": max(0.0, spin_square - 0.75),
        "effective_multiplicity": effective_multiplicity,
        "natural_occupations": natural_occupations,
        "natural_coefficients": natural_coefficients,
        "candidate_indices": candidates,
        "somo": somo,
    }


def ao_indices_for_atoms(molecule: Any, atom_indices: list[int]) -> list[int]:
    slices = molecule.aoslice_by_atom()
    indices: list[int] = []
    for atom_index in atom_indices:
        start, stop = map(int, slices[int(atom_index), 2:4])
        indices.extend(range(start, stop))
    return indices


def parity_indices(molecule: Any) -> tuple[list[int], list[int]]:
    odd_components = {"z", "xz", "yz"}
    even: list[int] = []
    odd: list[int] = []
    for index, label in enumerate(molecule.ao_labels(fmt=False)):
        component = str(label[3]).lower().replace(" ", "")
        (odd if component in odd_components else even).append(index)
    return even, odd


def selector(size: int, indices: list[int]) -> np.ndarray:
    return np.eye(size)[:, indices]


def support_max(coefficients: np.ndarray, allowed: list[int]) -> float:
    outside = np.ones(coefficients.shape[0], dtype=bool)
    outside[allowed] = False
    return float(np.max(np.abs(coefficients[outside, :]))) if np.any(outside) else 0.0


def metric_diagnostics(metric: np.ndarray) -> dict[str, Any]:
    symmetric = 0.5 * (metric + metric.T)
    eigenvalues = np.linalg.eigvalsh(symmetric)
    return {
        "matrix": symmetric.tolist(),
        "rank": int(np.linalg.matrix_rank(symmetric)),
        "minimum_eigenvalue": float(eigenvalues[0]),
        "maximum_eigenvalue": float(eigenvalues[-1]),
        "condition_number": float(np.linalg.cond(symmetric)),
        "positive_definite": bool(eigenvalues[0] > 0.0),
        "normalization_residual_max": float(np.max(np.abs(np.diag(symmetric) - 1.0))),
        "signed_cross_overlap": float(symmetric[0, 1]),
        "absolute_cross_overlap": abs(float(symmetric[0, 1])),
    }


def phase_invariance(pair: np.ndarray, overlap: np.ndarray) -> dict[str, float]:
    reference_metric = pair.T @ overlap @ pair
    reference_eigenvalues = np.linalg.eigvalsh(reference_metric)
    reference_condition = float(np.linalg.cond(reference_metric))
    reference_abs_overlap = abs(float(reference_metric[0, 1]))
    eigenvalue_errors: list[float] = []
    condition_errors: list[float] = []
    overlap_errors: list[float] = []
    for first_sign, second_sign in ((-1.0, 1.0), (1.0, -1.0), (-1.0, -1.0)):
        changed = pair @ np.diag([first_sign, second_sign])
        metric = changed.T @ overlap @ changed
        eigenvalue_errors.append(float(np.max(np.abs(np.linalg.eigvalsh(metric) - reference_eigenvalues))))
        condition_errors.append(abs(float(np.linalg.cond(metric)) - reference_condition))
        overlap_errors.append(abs(abs(float(metric[0, 1])) - reference_abs_overlap))
    return {
        "maximum_eigenvalue_error": max(eigenvalue_errors),
        "maximum_condition_number_error": max(condition_errors),
        "maximum_absolute_overlap_error": max(overlap_errors),
    }


def run_experiment(config: dict[str, Any]) -> dict[str, Any]:
    from pyscf import __version__ as pyscf_version
    from pyscf import gto

    started = time.perf_counter()
    fragment_config_path = ROOT / config["fragment_reference_config"]
    fragment_config = load_yaml(fragment_config_path)
    fragment_atoms = fragment_config["geometry"]["atoms"]
    fragment_settings = {
        **fragment_config["electronic_structure"],
        **fragment_config["scf"],
    }
    reference_position = reference_h_position(fragment_atoms, config["cut_geometry"])
    reference_atoms = [["H", *reference_position.tolist()]]
    reference_settings = config["reference_hydrogen"]
    singly_window = config["orbital_selection"]["singly_occupied_window"]

    fragment = run_fragment_uhf(fragment_atoms, fragment_settings, singly_window)
    reference = run_fragment_uhf(reference_atoms, reference_settings, singly_window)
    if fragment["somo"] is None or reference["somo"] is None:
        raise RuntimeError("unique fragment/reference-H natural SOMO pairing was not available")

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
    composite_overlap = composite.intor_symmetric("int1e_ovlp")
    fragment_ao_indices = ao_indices_for_atoms(
        composite, config["embedding"]["fragment_atom_indices"]
    )
    reference_ao_indices = ao_indices_for_atoms(
        composite, config["embedding"]["reference_hydrogen_atom_indices"]
    )
    if len(fragment_ao_indices) != fragment["molecule"].nao_nr():
        raise RuntimeError("fragment AO ordering is incompatible with the composite container")
    if len(reference_ao_indices) != reference["molecule"].nao_nr():
        raise RuntimeError("reference-H AO ordering is incompatible with the composite container")

    fragment_embedded = np.zeros((composite.nao_nr(), 1))
    reference_embedded = np.zeros((composite.nao_nr(), 1))
    fragment_embedded[fragment_ao_indices, :] = fragment["somo"]
    reference_embedded[reference_ao_indices, :] = reference["somo"]
    pair = np.column_stack((fragment_embedded[:, 0], reference_embedded[:, 0]))
    pair_metric = pair.T @ composite_overlap @ pair
    pair_diagnostics = metric_diagnostics(pair_metric)
    phase = phase_invariance(pair, composite_overlap)

    fragment_principal = composite_overlap[np.ix_(fragment_ao_indices, fragment_ao_indices)]
    reference_principal = composite_overlap[np.ix_(reference_ao_indices, reference_ao_indices)]
    fragment_principal_residual = normalized_residual(
        fragment_principal - fragment["overlap"], fragment["overlap"]
    )
    reference_principal_residual = normalized_residual(
        reference_principal - reference["overlap"], reference["overlap"]
    )

    even_indices, odd_indices = parity_indices(fragment["molecule"])
    fragment_sigma_leakage = subspace_leakage(
        fragment["overlap"], fragment["somo"], selector(fragment["molecule"].nao_nr(), even_indices)
    )
    fragment_pi_weight = subspace_leakage(
        fragment["overlap"], fragment["somo"], selector(fragment["molecule"].nao_nr(), odd_indices)
    )
    reference_shell_angular_momenta = [
        int(reference["molecule"].bas_angular(shell))
        for shell in range(reference["molecule"].nbas)
    ]
    acceptance = config["acceptance"]
    expected_candidates = int(config["orbital_selection"]["required_candidates_per_fragment"])
    support_fragment = support_max(fragment_embedded, fragment_ao_indices)
    support_reference = support_max(reference_embedded, reference_ao_indices)
    checks = {
        "fragment_reference_reused": sha256_text(canonical_geometry(fragment_atoms))
        == sha256_text(canonical_geometry(fragment_config["geometry"]["atoms"])),
        "fragment_scf_converged": fragment["converged"],
        "reference_h_scf_converged": reference["converged"],
        "fragment_state": fragment["alpha_electrons"] == 5 and fragment["beta_electrons"] == 4,
        "reference_h_state": reference["alpha_electrons"] == 1 and reference["beta_electrons"] == 0,
        "unique_pairing": len(fragment["candidate_indices"]) == expected_candidates
        and len(reference["candidate_indices"]) == expected_candidates,
        "reference_h_s_only": all(value == 0 for value in reference_shell_angular_momenta),
        "strict_separate_ao_support": max(support_fragment, support_reference)
        <= float(acceptance["coefficient_support_tolerance"]),
        "principal_overlap_embedding": max(
            fragment_principal_residual, reference_principal_residual
        )
        <= float(acceptance["principal_overlap_residual_tolerance"]),
        "pair_metric_full_rank": pair_diagnostics["rank"] == 2
        and pair_diagnostics["positive_definite"],
        "pair_metric_conditioned": pair_diagnostics["condition_number"]
        <= float(acceptance["metric_condition_number_limit"]),
        "pair_normalized": pair_diagnostics["normalization_residual_max"]
        <= float(acceptance["normalization_residual_tolerance"]),
        "pair_overlap_nonzero": pair_diagnostics["absolute_cross_overlap"]
        >= float(acceptance["minimum_absolute_pair_overlap"]),
        "phase_invariant": max(phase.values())
        <= float(acceptance["phase_invariance_tolerance"]),
        "fragment_pi_parity": fragment_sigma_leakage
        <= float(acceptance["ch3_sigma_leakage_tolerance"])
        and abs(fragment_pi_weight - 1.0)
        <= float(acceptance["ch3_sigma_leakage_tolerance"]),
        "spin_contamination": max(
            fragment["spin_contamination"], reference["spin_contamination"]
        )
        <= float(acceptance["maximum_spin_contamination"]),
        "no_production_labels": config["production_labels_allowed"] is False,
    }

    fragment_map = {
        "fragment_atom_indices": config["embedding"]["fragment_atom_indices"],
        "reference_hydrogen_atom_indices": config["embedding"]["reference_hydrogen_atom_indices"],
        "fragment_ao_indices": fragment_ao_indices,
        "reference_hydrogen_ao_indices": reference_ao_indices,
    }
    peak_rss_mib = (
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
        if resource is not None
        else float("nan")
    )
    return {
        "schema": "ai4orgchem-one-cut-ch3-reference-h/1.0",
        "date": date.today().isoformat(),
        "classification": "non-production coefficient/overlap validation",
        "disposition": "PASS" if all(checks.values()) else "QUARANTINE",
        "checks": checks,
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pyscf": pyscf_version,
            "platform": platform.platform(),
        },
        "geometry": {
            "fragment": canonical_geometry(fragment_atoms),
            "reference_hydrogen": canonical_geometry(reference_atoms),
            "composite_ao_container": canonical_geometry(composite_atoms),
            "cut_direction": config["cut_geometry"]["direction"],
            "reference_hydrogen_distance_angstrom": float(
                config["cut_geometry"]["reference_hydrogen_distance_angstrom"]
            ),
        },
        "fragment_states": {
            "ch3": {
                "electrons": fragment["molecule"].nelectron,
                "alpha": fragment["alpha_electrons"],
                "beta": fragment["beta_electrons"],
                "converged": fragment["converged"],
                "cycles": fragment["cycles"],
                "spin_square": fragment["spin_square"],
                "spin_contamination": fragment["spin_contamination"],
                "natural_occupations": fragment["natural_occupations"].tolist(),
                "somo_candidate_indices": fragment["candidate_indices"],
            },
            "reference_hydrogen": {
                "electrons": reference["molecule"].nelectron,
                "alpha": reference["alpha_electrons"],
                "beta": reference["beta_electrons"],
                "converged": reference["converged"],
                "cycles": reference["cycles"],
                "spin_square": reference["spin_square"],
                "spin_contamination": reference["spin_contamination"],
                "natural_occupations": reference["natural_occupations"].tolist(),
                "somo_candidate_indices": reference["candidate_indices"],
                "basis_shell_angular_momenta": reference_shell_angular_momenta,
            },
        },
        "fragment_map": fragment_map,
        "support": {
            "fragment_outside_support_max": support_fragment,
            "reference_h_outside_support_max": support_reference,
            "fragment_principal_overlap_residual": fragment_principal_residual,
            "reference_h_principal_overlap_residual": reference_principal_residual,
        },
        "pairing": {
            "rule": "exactly_one_spin_summed_natural_orbital_in_0.9_to_1.1_per_side",
            "ambiguous": not checks["unique_pairing"],
            "pair_metric": pair_diagnostics,
            "phase_invariance": phase,
        },
        "parity": {
            "ch3_local_plane": "xy",
            "ch3_somo_sigma_leakage": fragment_sigma_leakage,
            "ch3_somo_pi_weight": fragment_pi_weight,
            "reference_h_basis_s_only": checks["reference_h_s_only"],
            "global_pair_parity_assigned": False,
            "reason": "off-plane reference H is not mapped onto itself by xy reflection",
        },
        "provenance": {
            "experiment_id": config["experiment_id"],
            "parent_fragment_protocol": config["parent_fragment_protocol"],
            "fragment_reference_config": config["fragment_reference_config"],
            "fragment_geometry_hash": sha256_text(canonical_geometry(fragment_atoms)),
            "composite_geometry_hash": sha256_text(canonical_geometry(composite_atoms)),
            "fragment_map_hash": sha256_text(json.dumps(fragment_map, sort_keys=True)),
            "config_hash": sha256_text(json.dumps(config, ensure_ascii=False, sort_keys=True)),
            "code_commit": git_commit(),
            "resource_profile": config["resources"]["profile"],
        },
        "resources": {
            "wall_time_seconds": time.perf_counter() - started,
            "peak_rss_mib": peak_rss_mib,
            "thread_count": int(os.environ.get("OMP_NUM_THREADS", "1")),
            "output_bytes": 0,
        },
        "boundaries": {
            "composite_scf_run": False,
            "kost_rotation_run": False,
            "conditional_fragment_scf_run": False,
            "two_cut_fragment_run": False,
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
    pair = report["pairing"]["pair_metric"]
    phase = report["pairing"]["phase_invariance"]
    ch3 = report["fragment_states"]["ch3"]
    hydrogen = report["fragment_states"]["reference_hydrogen"]
    checks = report["checks"]
    rows = [
        ("CH3 UHF", f"{ch3['alpha']} alpha / {ch3['beta']} beta; S2={ch3['spin_square']:.10f}", checks["fragment_scf_converged"] and checks["fragment_state"]),
        ("Reference-H UHF", f"{hydrogen['alpha']} alpha / {hydrogen['beta']} beta; S2={hydrogen['spin_square']:.10f}", checks["reference_h_scf_converged"] and checks["reference_h_state"]),
        ("Unique SOMO pair", f"CH3={ch3['somo_candidate_indices']}; H={hydrogen['somo_candidate_indices']}", checks["unique_pairing"]),
        ("Strict separate AO support", f"max={max(report['support']['fragment_outside_support_max'], report['support']['reference_h_outside_support_max']):.3e}", checks["strict_separate_ao_support"]),
        ("Absolute pair overlap", f"{pair['absolute_cross_overlap']:.12f}", checks["pair_overlap_nonzero"]),
        ("Pair metric rank/condition", f"{pair['rank']} / {pair['condition_number']:.6g}", checks["pair_metric_full_rank"] and checks["pair_metric_conditioned"]),
        ("CH3 SOMO pi weight", f"{report['parity']['ch3_somo_pi_weight']:.12f}", checks["fragment_pi_parity"]),
        ("Reference-H basis", f"l={hydrogen['basis_shell_angular_momenta']}", checks["reference_h_s_only"]),
    ]
    lines = [
        "# Gate 0 CH3/reference-H coefficient-pair validation",
        "",
        f"- Date: {report['date']}",
        f"- Disposition: **{report['disposition']}**",
        "- Classification: non-production coefficient/overlap evidence",
        "- Composite SCF, Kost rotation, and conditional SCF run: no",
        "- Scientific energy label generated: no",
        f"- Runtime: Python `{report['runtime']['python']}`, PySCF `{report['runtime']['pyscf']}`, NumPy `{report['runtime']['numpy']}`",
        "",
        "## Result",
        "",
        "| Diagnostic | Value | Check |",
        "|---|---:|---|",
    ]
    lines.extend(
        f"| {name} | {value} | {'PASS' if passed else 'FAIL'} |"
        for name, value, passed in rows
    )
    lines.extend(
        [
            "",
            "## Geometry and fragment map",
            "",
            f"- Reference H distance: `{report['geometry']['reference_hydrogen_distance_angstrom']:.2f} angstrom` along `{report['geometry']['cut_direction']}`.",
            f"- CH3 atom/AO indices: `{report['fragment_map']['fragment_atom_indices']}` / `{report['fragment_map']['fragment_ao_indices']}`.",
            f"- Reference-H atom/AO indices: `{report['fragment_map']['reference_hydrogen_atom_indices']}` / `{report['fragment_map']['reference_hydrogen_ao_indices']}`.",
            f"- Fragment principal-overlap residual: `{report['support']['fragment_principal_overlap_residual']:.3e}`.",
            f"- Reference-H principal-overlap residual: `{report['support']['reference_h_principal_overlap_residual']:.3e}`.",
            "",
            "## Nonorthogonal pair diagnostics",
            "",
            f"- Pair metric: `{pair['matrix']}`.",
            f"- Eigenvalue interval: `[{pair['minimum_eigenvalue']:.12f}, {pair['maximum_eigenvalue']:.12f}]`.",
            f"- Signed/absolute cross overlap: `{pair['signed_cross_overlap']:.12f}` / `{pair['absolute_cross_overlap']:.12f}`.",
            f"- Phase-flip maximum eigenvalue error: `{phase['maximum_eigenvalue_error']:.3e}`.",
            f"- Phase-flip maximum condition-number error: `{phase['maximum_condition_number_error']:.3e}`.",
            f"- Phase-flip maximum absolute-overlap error: `{phase['maximum_absolute_overlap_error']:.3e}`.",
            "",
            "## Interpretation boundary",
            "",
            "The two isolated doublet calculations provide exactly one natural SOMO",
            "per side, so this single-pair prototype has no root-selection ambiguity.",
            "Their coefficients are embedded without global orthogonalization and retain",
            "exactly separate AO support. The composite molecule is used only to evaluate",
            "the AO overlap metric; no composite determinant or energy was calculated.",
            "CH3 local pi parity is well-defined. No global xy-reflection parity is",
            "assigned to the pair because the off-plane reference H is not invariant",
            "under that reflection. Passing this rung does not validate Kost rotations,",
            "conditional SCF, a complete LFMO basis, or an energy decomposition.",
            "",
            "## Provenance and resources",
            "",
            f"- Experiment: `{report['provenance']['experiment_id']}`.",
            f"- Fragment geometry SHA-256: `{report['provenance']['fragment_geometry_hash']}`.",
            f"- Composite geometry SHA-256: `{report['provenance']['composite_geometry_hash']}`.",
            f"- Fragment-map SHA-256: `{report['provenance']['fragment_map_hash']}`.",
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
    config = load_yaml(args.config)
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
    pair = report["pairing"]["pair_metric"]
    print(
        f"{report['disposition']}: candidates="
        f"{report['fragment_states']['ch3']['somo_candidate_indices']}/"
        f"{report['fragment_states']['reference_hydrogen']['somo_candidate_indices']} "
        f"abs_overlap={pair['absolute_cross_overlap']:.12f} "
        f"rank={pair['rank']} condition={pair['condition_number']:.6g}"
    )
    return 0 if report["disposition"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
