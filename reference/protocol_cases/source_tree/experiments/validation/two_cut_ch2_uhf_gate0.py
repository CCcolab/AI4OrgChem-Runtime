"""Run the bounded two-cut CH2 high-spin UHF orbital-generation smoke test."""

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

from ai4orgchem.lfmo.subspaces import metric_projector, projector_diagnostics


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs" / "qm" / "two_cut_ch2_uhf_v0.1.yaml"


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


def normalized_residual(numerator: np.ndarray, denominator: np.ndarray) -> float:
    return float(
        np.linalg.norm(numerator, ord="fro")
        / max(float(np.linalg.norm(denominator, ord="fro")), 1.0)
    )


def ao_indices_for_atoms(molecule: Any, atom_indices: list[int]) -> list[int]:
    slices = molecule.aoslice_by_atom()
    indices: list[int] = []
    for atom_index in atom_indices:
        start, stop = map(int, slices[int(atom_index), 2:4])
        indices.extend(range(start, stop))
    return indices


def reference_atoms(config: dict[str, Any]) -> list[list[Any]]:
    atoms = config["geometry"]["atoms"]
    distance = float(config["geometry"]["reference_hydrogen_distance_angstrom"])
    result: list[list[Any]] = []
    for cut in config["geometry"]["cuts"]:
        origin = np.asarray(
            atoms[int(cut["origin_fragment_atom_index"])][1:], dtype=float
        )
        direction = np.asarray(cut["direction"], dtype=float)
        direction /= np.linalg.norm(direction)
        position = origin + distance * direction
        result.append(["H", *position.tolist()])
    return result


def parity_indices(molecule: Any, odd_components: set[str]) -> tuple[list[int], list[int]]:
    even: list[int] = []
    odd: list[int] = []
    for index, label in enumerate(molecule.ao_labels(fmt=False)):
        component = str(label[3]).lower().replace(" ", "")
        (odd if component in odd_components else even).append(index)
    return even, odd


def inverse_sqrt(matrix: np.ndarray) -> np.ndarray:
    eigenvalues, eigenvectors = np.linalg.eigh(0.5 * (matrix + matrix.T))
    if float(eigenvalues[0]) <= 0.0:
        raise ValueError("projected cut-target anchor metric is not positive definite")
    return (eigenvectors / np.sqrt(eigenvalues)) @ eigenvectors.T


def run_calculation(config: dict[str, Any]) -> dict[str, Any]:
    from pyscf import __version__ as pyscf_version
    from pyscf import gto, scf
    from pyscf.mcscf.addons import make_natural_orbitals

    started = time.perf_counter()
    atoms = config["geometry"]["atoms"]
    electronic = config["electronic_structure"]
    scf_config = config["scf"]
    selection = config["orbital_selection"]
    acceptance = config["acceptance"]
    fragment = gto.M(
        atom=canonical_geometry(atoms),
        basis=electronic["basis"],
        charge=int(electronic["charge"]),
        spin=int(electronic["multiplicity"]) - 1,
        unit=config["geometry"]["unit"],
        symmetry=False,
        verbose=0,
    )
    cycles: list[int] = []

    def record_cycle(environment: dict[str, Any]) -> None:
        cycles.append(int(environment.get("cycle", len(cycles))) + 1)

    mean_field = scf.UHF(fragment)
    mean_field.conv_tol = float(scf_config["convergence_tolerance"])
    mean_field.max_cycle = int(scf_config["max_cycles"])
    mean_field.init_guess = str(scf_config["initial_guess"])
    mean_field.callback = record_cycle
    energy = float(mean_field.kernel())

    overlap = mean_field.get_ovlp()
    density_alpha, density_beta = mean_field.make_rdm1()
    density_total = density_alpha + density_beta
    density_spin = density_alpha - density_beta
    alpha_coefficients, beta_coefficients = mean_field.mo_coeff
    alpha_count = int(np.count_nonzero(mean_field.mo_occ[0] > 0.5))
    beta_count = int(np.count_nonzero(mean_field.mo_occ[1] > 0.5))
    natural_occupations, natural_coefficients = make_natural_orbitals(mean_field)
    lower, upper = map(float, selection["singly_occupied_window"])
    candidate_indices = [
        int(index)
        for index, occupation in enumerate(natural_occupations)
        if lower <= float(occupation) <= upper
    ]
    if len(candidate_indices) != int(selection["required_candidates"]):
        target_local = natural_coefficients[
            :, np.argsort(np.abs(natural_occupations - 1.0))[:2]
        ]
    else:
        target_local = natural_coefficients[:, candidate_indices]

    refs = reference_atoms(config)
    reference_states: list[dict[str, Any]] = []
    for atom in refs:
        ref_mol = gto.M(
            atom=canonical_geometry([atom]),
            basis=electronic["basis"],
            charge=0,
            spin=1,
            unit="Angstrom",
            symmetry=False,
            verbose=0,
        )
        ref_mf = scf.UHF(ref_mol)
        ref_mf.conv_tol = float(scf_config["convergence_tolerance"])
        ref_mf.max_cycle = int(scf_config["max_cycles"])
        ref_mf.init_guess = str(scf_config["initial_guess"])
        ref_mf.kernel()
        ref_occ, ref_coeff = make_natural_orbitals(ref_mf)
        ref_index = int(np.argmin(np.abs(ref_occ - 1.0)))
        reference_states.append(
            {
                "molecule": ref_mol,
                "converged": bool(ref_mf.converged),
                "somo": ref_coeff[:, [ref_index]],
                "shell_angular_momenta": [
                    int(ref_mol.bas_angular(shell)) for shell in range(ref_mol.nbas)
                ],
            }
        )

    composite_atoms = [*atoms, *refs]
    composite = gto.M(
        atom=canonical_geometry(composite_atoms),
        basis=electronic["basis"],
        charge=0,
        spin=0,
        unit="Angstrom",
        symmetry=False,
        verbose=0,
    )
    composite_overlap = composite.intor_symmetric("int1e_ovlp")
    fragment_atom_indices = list(range(len(atoms)))
    reference_atom_indices = list(range(len(atoms), len(composite_atoms)))
    fragment_ao = ao_indices_for_atoms(composite, fragment_atom_indices)
    target_embedded = np.zeros((composite.nao_nr(), 2))
    target_embedded[fragment_ao, :] = target_local
    probes = np.zeros((composite.nao_nr(), 2))
    reference_ao: list[list[int]] = []
    for column, (atom_index, state) in enumerate(
        zip(reference_atom_indices, reference_states, strict=True)
    ):
        indices = ao_indices_for_atoms(composite, [atom_index])
        reference_ao.append(indices)
        probes[np.ix_(indices, [column])] = state["somo"]

    cross_before = target_embedded.T @ composite_overlap @ probes
    projected_anchors = target_embedded @ cross_before
    anchor_metric = projected_anchors.T @ composite_overlap @ projected_anchors
    assigned_targets = projected_anchors @ inverse_sqrt(anchor_metric)
    cross_assigned = assigned_targets.T @ composite_overlap @ probes
    for index in range(2):
        if cross_assigned[index, index] < 0.0:
            assigned_targets[:, index] *= -1.0
    cross_assigned = assigned_targets.T @ composite_overlap @ probes
    assignment_margins = [
        abs(float(cross_assigned[index, index]))
        - abs(float(cross_assigned[1 - index, index]))
        for index in range(2)
    ]

    odd_components = {
        str(value).lower() for value in config["classification"]["odd_ao_components"]
    }
    even_local, odd_local = parity_indices(fragment, odd_components)
    even_embedded = np.zeros((composite.nao_nr(), len(even_local)))
    odd_embedded = np.zeros((composite.nao_nr(), len(odd_local)))
    even_embedded[np.ix_(fragment_ao, range(len(even_local)))] = np.eye(
        fragment.nao_nr()
    )[:, even_local]
    odd_embedded[np.ix_(fragment_ao, range(len(odd_local)))] = np.eye(
        fragment.nao_nr()
    )[:, odd_local]
    p_target = metric_projector(composite_overlap, assigned_targets)
    p_sigma = metric_projector(composite_overlap, even_embedded)
    p_pi = metric_projector(composite_overlap, odd_embedded)
    sigma_dimension = float(np.trace(p_target @ p_sigma))
    pi_dimension = float(np.trace(p_target @ p_pi))
    target_pi_weights = [
        float(
            (
                assigned_targets[:, [index]].T
                @ composite_overlap
                @ p_pi
                @ assigned_targets[:, [index]]
            )[0, 0]
        )
        for index in range(2)
    ]

    spin_square, effective_multiplicity = map(float, mean_field.spin_square())
    spin_contamination = max(
        0.0, spin_square - float(electronic["exact_spin_square"])
    )
    total_trace = float(np.trace(density_total @ overlap))
    spin_trace = float(np.trace(density_spin @ overlap))
    identity = np.eye(fragment.nao_nr())
    alpha_orthonormality = normalized_residual(
        alpha_coefficients.T @ overlap @ alpha_coefficients - identity, identity
    )
    beta_orthonormality = normalized_residual(
        beta_coefficients.T @ overlap @ beta_coefficients - identity, identity
    )
    natural_orthonormality = normalized_residual(
        natural_coefficients.T @ overlap @ natural_coefficients - identity, identity
    )
    ao_condition = float(np.linalg.cond(overlap))
    outside_support = float(
        np.max(np.abs(assigned_targets[np.asarray(reference_ao).ravel(), :]))
    )
    assignment_margin = min(assignment_margins)
    expected_sigma = int(
        config["classification"]["target_subspace_expected_sigma_dimension"]
    )
    expected_pi = int(
        config["classification"]["target_subspace_expected_pi_dimension"]
    )
    trace_tolerance = float(acceptance["electron_trace_tolerance"])
    checks = {
        "scf_converged": bool(mean_field.converged),
        "electron_count": fragment.nelectron == int(electronic["expected_electrons"]),
        "alpha_beta_counts": alpha_count == int(electronic["expected_alpha_electrons"])
        and beta_count == int(electronic["expected_beta_electrons"]),
        "density_traces": abs(total_trace - fragment.nelectron) <= trace_tolerance
        and abs(spin_trace - fragment.spin) <= trace_tolerance,
        "ao_metric": ao_condition
        <= float(acceptance["metric_condition_number_limit"]),
        "orbital_orthonormality": max(
            alpha_orthonormality, beta_orthonormality, natural_orthonormality
        )
        <= float(acceptance["orthonormality_residual_tolerance"]),
        "spin_contamination": spin_contamination
        <= float(acceptance["maximum_spin_contamination"]),
        "two_natural_singly_occupied": len(candidate_indices)
        == int(selection["required_candidates"]),
        "reference_h_states": all(state["converged"] for state in reference_states),
        "reference_h_s_only": all(
            angular == 0
            for state in reference_states
            for angular in state["shell_angular_momenta"]
        ),
        "cut_assignment": assignment_margin
        >= float(acceptance["minimum_cut_assignment_margin"]),
        "strict_fragment_support": outside_support
        <= float(acceptance["coefficient_support_tolerance"]),
        "target_subspace_reflection": abs(sigma_dimension - expected_sigma)
        <= float(acceptance["reflection_dimension_tolerance"])
        and abs(pi_dimension - expected_pi)
        <= float(acceptance["reflection_dimension_tolerance"]),
        "target_projector": projector_diagnostics(
            composite_overlap, assigned_targets
        )["idempotency_residual"]
        <= float(acceptance["projector_residual_tolerance"]),
        "no_production_labels": config["production_labels_allowed"] is False,
    }

    peak_rss_mib = (
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
        if resource is not None
        else float("nan")
    )
    return {
        "schema": "ai4orgchem-two-cut-ch2-uhf/1.0",
        "date": date.today().isoformat(),
        "classification": "non-production two-cut orbital-generation smoke",
        "disposition": "PASS" if all(checks.values()) else "QUARANTINE",
        "checks": checks,
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pyscf": pyscf_version,
            "platform": platform.platform(),
        },
        "input": {
            "fragment_geometry": canonical_geometry(atoms),
            "reference_h_geometry": canonical_geometry(refs),
            "cut_ids": [cut["id"] for cut in config["geometry"]["cuts"]],
            "method": electronic["method"],
            "basis": electronic["basis"],
            "charge": int(electronic["charge"]),
            "multiplicity": int(electronic["multiplicity"]),
        },
        "electrons": {
            "total": fragment.nelectron,
            "alpha": alpha_count,
            "beta": beta_count,
            "density_trace_total": total_trace,
            "density_trace_spin": spin_trace,
        },
        "scf": {
            "converged": bool(mean_field.converged),
            "cycles": max(cycles, default=0),
            "total_energy_hartree_diagnostic_only": energy,
        },
        "spin": {
            "spin_square": spin_square,
            "exact_triplet_spin_square": float(electronic["exact_spin_square"]),
            "spin_contamination": spin_contamination,
            "effective_multiplicity": effective_multiplicity,
        },
        "natural_orbitals": {
            "occupations": natural_occupations.tolist(),
            "singly_occupied_window": [lower, upper],
            "candidate_indices": candidate_indices,
            "candidate_count": len(candidate_indices),
        },
        "cut_assignment": {
            "gauge": selection["target_gauge"],
            "target_probe_overlap_before": cross_before.tolist(),
            "assigned_target_probe_overlap": cross_assigned.tolist(),
            "assignment_margins": assignment_margins,
            "minimum_margin": assignment_margin,
            "target_pi_weights_by_cut_id": target_pi_weights,
            "kost_rotation_run": False,
        },
        "reflection": {
            "plane": config["classification"]["reflection_plane"],
            "target_subspace_sigma_dimension": sigma_dimension,
            "target_subspace_pi_dimension": pi_dimension,
        },
        "metric": {
            "ao_overlap_condition_number": ao_condition,
            "alpha_mo_orthonormality_residual": alpha_orthonormality,
            "beta_mo_orthonormality_residual": beta_orthonormality,
            "natural_orbital_orthonormality_residual": natural_orthonormality,
            "target_projector": projector_diagnostics(
                composite_overlap, assigned_targets
            ),
            "assigned_target_orthonormality_residual": normalized_residual(
                assigned_targets.T @ composite_overlap @ assigned_targets - np.eye(2),
                np.eye(2),
            ),
        },
        "support": {
            "declared_fragment": "CH2",
            "fragment_ao_indices": fragment_ao,
            "reference_h_ao_indices": reference_ao,
            "outside_fragment_coefficient_max": outside_support,
        },
        "provenance": {
            "calculation_id": config["calculation_id"],
            "parent_fragment_protocol": config["parent_fragment_protocol"],
            "state_config": config["state_config"],
            "geometry_hash": sha256_text(canonical_geometry(atoms)),
            "cut_map_hash": sha256_text(
                json.dumps(config["geometry"]["cuts"], sort_keys=True)
            ),
            "config_hash": sha256_text(json.dumps(config, sort_keys=True)),
            "code_commit": git_commit(),
            "resource_profile": config["resources"]["profile"],
        },
        "resources": {
            "wall_time_seconds": time.perf_counter() - started,
            "peak_rss_mib": peak_rss_mib,
            "thread_count": int(os.environ.get("OMP_NUM_THREADS", "1")),
        },
        "boundaries": {
            "orbital_generation_only": True,
            "kost_rotation_run": False,
            "conditional_fragment_scf_run": False,
            "broken_symmetry_singlet_run": False,
            "dsi_fud_run": False,
            "production_labels_generated": False,
            "prohibited_outputs": config["prohibited_outputs"],
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
    checks = report["checks"]
    return "\n".join(
        [
            "# Gate 0 two-cut CH2 high-spin UHF smoke",
            "",
            f"- Date: {report['date']}",
            f"- Disposition: **{report['disposition']}**",
            "- Role: orbital generation only; no physical triplet-ground-state claim",
            "- Kost / conditional SCF / DSI-FUD: not run",
            "",
            "| Diagnostic | Value | Check |",
            "|---|---:|---|",
            f"| Electrons | {report['electrons']['total']} ({report['electrons']['alpha']} alpha / {report['electrons']['beta']} beta) | {'PASS' if checks['electron_count'] and checks['alpha_beta_counts'] else 'FAIL'} |",
            f"| SCF convergence | {report['scf']['converged']} in {report['scf']['cycles']} cycles | {'PASS' if checks['scf_converged'] else 'FAIL'} |",
            f"| `<S^2>` / contamination | {report['spin']['spin_square']:.10f} / {report['spin']['spin_contamination']:.3e} | {'PASS' if checks['spin_contamination'] else 'FAIL'} |",
            f"| Natural singly occupied count | {report['natural_orbitals']['candidate_count']} | {'PASS' if checks['two_natural_singly_occupied'] else 'FAIL'} |",
            f"| Minimum cut assignment margin | {report['cut_assignment']['minimum_margin']:.6e} | {'PASS' if checks['cut_assignment'] else 'FAIL'} |",
            f"| Target sigma / pi dimensions | {report['reflection']['target_subspace_sigma_dimension']:.8f} / {report['reflection']['target_subspace_pi_dimension']:.8f} | {'PASS' if checks['target_subspace_reflection'] else 'FAIL'} |",
            f"| AO-overlap condition number | {report['metric']['ao_overlap_condition_number']:.6f} | {'PASS' if checks['ao_metric'] else 'FAIL'} |",
            f"| Maximum orbital orthonormality residual | {max(report['metric']['alpha_mo_orthonormality_residual'], report['metric']['beta_mo_orthonormality_residual'], report['metric']['natural_orbital_orthonormality_residual']):.3e} | {'PASS' if checks['orbital_orthonormality'] else 'FAIL'} |",
            f"| Outside-fragment coefficient max | {report['support']['outside_fragment_coefficient_max']:.3e} | {'PASS' if checks['strict_fragment_support'] else 'FAIL'} |",
            "",
            "## Cut-target assignment",
            "",
            f"- Cut IDs: `{report['input']['cut_ids']}`",
            f"- Natural occupations: `{[round(value, 10) for value in report['natural_orbitals']['occupations']]}`",
            f"- Candidate indices: `{report['natural_orbitals']['candidate_indices']}`",
            f"- Assigned target/probe overlap: `{report['cut_assignment']['assigned_target_probe_overlap']}`",
            f"- Assigned target pi weights: `{report['cut_assignment']['target_pi_weights_by_cut_id']}`",
            "",
            "## Boundary",
            "",
            "The triplet determinant and its diagnostic total energy are retained only",
            "to validate the two-cut orbital-generation state. This run does not assign",
            "a physical fragment ground state and does not generate LFMO energy, DSI,",
            "FUD, conjugation, stabilization, or spin-coupling labels.",
            "",
            "## Provenance",
            "",
            f"- Geometry SHA-256: `{report['provenance']['geometry_hash']}`",
            f"- Cut-map SHA-256: `{report['provenance']['cut_map_hash']}`",
            f"- Config SHA-256: `{report['provenance']['config_hash']}`",
            f"- Code commit at run: `{report['provenance']['code_commit']}`",
            f"- Runtime: Python `{report['runtime']['python']}`, PySCF `{report['runtime']['pyscf']}`, NumPy `{report['runtime']['numpy']}`",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()
    config = load_yaml(args.config)
    report = json_safe(run_calculation(config))
    serialized = json.dumps(report, indent=2) + "\n"
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(serialized, encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(
        f"{report['disposition']}: electrons={report['electrons']['total']} "
        f"alpha/beta={report['electrons']['alpha']}/{report['electrons']['beta']} "
        f"converged={report['scf']['converged']} S2={report['spin']['spin_square']:.10f} "
        f"natural_singly_occupied={report['natural_orbitals']['candidate_count']} "
        f"assignment_margin={report['cut_assignment']['minimum_margin']:.6e}"
    )
    return 0 if report["disposition"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
