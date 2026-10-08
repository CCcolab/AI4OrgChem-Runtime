"""Audit the fixed two-cut [t1,t2,h1,h2] nonorthogonal container."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import time
from typing import Any

import numpy as np

try:
    import resource
except ImportError:  # pragma: no cover
    resource = None

from ai4orgchem.lfmo.subspaces import projector_diagnostics
from experiments.validation.two_cut_ch2_uhf_gate0 import (
    ROOT,
    ao_indices_for_atoms,
    canonical_geometry,
    inverse_sqrt,
    load_yaml,
    reference_atoms,
)


DEFAULT_CONFIG = ROOT / "configs" / "qm" / "two_cut_ch2_four_column_v0.1.yaml"


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


def run_uhf_natural_orbitals(
    atoms: list[list[Any]], basis: str, charge: int, spin: int, scf_config: dict[str, Any]
) -> dict[str, Any]:
    from pyscf import gto, scf
    from pyscf.mcscf.addons import make_natural_orbitals

    molecule = gto.M(
        atom=canonical_geometry(atoms),
        basis=basis,
        charge=charge,
        spin=spin,
        unit="Angstrom",
        symmetry=False,
        verbose=0,
    )
    mean_field = scf.UHF(molecule)
    mean_field.conv_tol = float(scf_config["convergence_tolerance"])
    mean_field.max_cycle = int(scf_config["max_cycles"])
    mean_field.init_guess = str(scf_config["initial_guess"])
    mean_field.kernel()
    occupations, coefficients = make_natural_orbitals(mean_field)
    return {
        "molecule": molecule,
        "converged": bool(mean_field.converged),
        "occupations": occupations,
        "coefficients": coefficients,
    }


def reconstruct_container(config: dict[str, Any]) -> dict[str, Any]:
    from pyscf import gto

    smoke = load_yaml(ROOT / config["parent_smoke_config"])
    atoms = smoke["geometry"]["atoms"]
    refs = reference_atoms(smoke)
    electronic = smoke["electronic_structure"]
    scf_config = smoke["scf"]
    lower, upper = map(float, smoke["orbital_selection"]["singly_occupied_window"])

    fragment = run_uhf_natural_orbitals(
        atoms,
        str(electronic["basis"]),
        int(electronic["charge"]),
        int(electronic["multiplicity"]) - 1,
        scf_config,
    )
    candidate_indices = [
        int(index)
        for index, occupation in enumerate(fragment["occupations"])
        if lower <= float(occupation) <= upper
    ]
    if len(candidate_indices) != 2:
        raise RuntimeError("frozen CH2 smoke did not reproduce two natural SOMOs")
    target_local = fragment["coefficients"][:, candidate_indices]

    reference_states = [
        run_uhf_natural_orbitals(
            [atom], str(electronic["basis"]), 0, 1, scf_config
        )
        for atom in refs
    ]
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
    overlap = composite.intor_symmetric("int1e_ovlp")
    fragment_atoms = list(range(len(atoms)))
    reference_atoms_indices = list(range(len(atoms), len(composite_atoms)))
    fragment_ao = ao_indices_for_atoms(composite, fragment_atoms)
    reference_ao = [
        ao_indices_for_atoms(composite, [atom_index])
        for atom_index in reference_atoms_indices
    ]

    targets = np.zeros((composite.nao_nr(), 2))
    targets[fragment_ao, :] = target_local
    probes = np.zeros((composite.nao_nr(), 2))
    for column, (indices, state) in enumerate(
        zip(reference_ao, reference_states, strict=True)
    ):
        ref_index = int(np.argmin(np.abs(state["occupations"] - 1.0)))
        probes[np.ix_(indices, [column])] = state["coefficients"][:, [ref_index]]

    cross = targets.T @ overlap @ probes
    projected = targets @ cross
    assigned = projected @ inverse_sqrt(projected.T @ overlap @ projected)
    assigned_cross = assigned.T @ overlap @ probes
    for index in range(2):
        if assigned_cross[index, index] < 0.0:
            assigned[:, index] *= -1.0
    container = np.column_stack((assigned, probes))
    return {
        "smoke": smoke,
        "fragment": fragment,
        "references": reference_states,
        "composite": composite,
        "composite_atoms": composite_atoms,
        "overlap": overlap,
        "container": container,
        "fragment_ao": fragment_ao,
        "reference_ao": reference_ao,
        "candidate_indices": candidate_indices,
    }


def phase_covariance(container: np.ndarray, overlap: np.ndarray) -> dict[str, float]:
    metric = container.T @ overlap @ container
    eigenvalues = np.linalg.eigvalsh(metric)
    condition = float(np.linalg.cond(metric))
    maximum_eigenvalue_error = 0.0
    maximum_condition_error = 0.0
    maximum_absolute_metric_error = 0.0
    for signs in itertools.product((-1.0, 1.0), repeat=4):
        changed = container @ np.diag(signs)
        changed_metric = changed.T @ overlap @ changed
        maximum_eigenvalue_error = max(
            maximum_eigenvalue_error,
            float(np.max(np.abs(np.linalg.eigvalsh(changed_metric) - eigenvalues))),
        )
        maximum_condition_error = max(
            maximum_condition_error, abs(float(np.linalg.cond(changed_metric)) - condition)
        )
        maximum_absolute_metric_error = max(
            maximum_absolute_metric_error,
            float(np.max(np.abs(np.abs(changed_metric) - np.abs(metric)))),
        )
    return {
        "maximum_eigenvalue_error": maximum_eigenvalue_error,
        "maximum_condition_number_error": maximum_condition_error,
        "maximum_absolute_metric_error": maximum_absolute_metric_error,
    }


def permutation_covariance(
    container: np.ndarray, overlap: np.ndarray
) -> dict[str, float]:
    metric = container.T @ overlap @ container
    projector = projector_diagnostics(overlap, container)
    maximum_metric_error = 0.0
    maximum_projector_residual_change = 0.0
    for permutation in ((1, 0, 3, 2), (2, 3, 0, 1), (3, 1, 2, 0)):
        changed = container[:, permutation]
        changed_metric = changed.T @ overlap @ changed
        expected = metric[np.ix_(permutation, permutation)]
        maximum_metric_error = max(
            maximum_metric_error, float(np.max(np.abs(changed_metric - expected)))
        )
        changed_projector = projector_diagnostics(overlap, changed)
        maximum_projector_residual_change = max(
            maximum_projector_residual_change,
            abs(
                changed_projector["idempotency_residual"]
                - projector["idempotency_residual"]
            ),
        )
    return {
        "maximum_metric_covariance_error": maximum_metric_error,
        "maximum_projector_residual_change": maximum_projector_residual_change,
    }


def run_audit(config: dict[str, Any]) -> dict[str, Any]:
    from pyscf import __version__ as pyscf_version

    started = time.perf_counter()
    inputs = reconstruct_container(config)
    overlap = inputs["overlap"]
    container = inputs["container"]
    metric = container.T @ overlap @ container
    metric = 0.5 * (metric + metric.T)
    eigenvalues = np.linalg.eigvalsh(metric)
    condition = float(np.linalg.cond(metric))
    rank = int(np.linalg.matrix_rank(metric))
    normalization = float(np.max(np.abs(np.diag(metric) - 1.0)))
    target_probe = metric[:2, 2:]
    pair_overlaps = [abs(float(target_probe[0, 0])), abs(float(target_probe[1, 1]))]
    off_pair_overlaps = [abs(float(target_probe[0, 1])), abs(float(target_probe[1, 0]))]
    margins = [
        pair_overlaps[index] - off_pair_overlaps[index] for index in range(2)
    ]

    support_residuals: dict[str, float] = {}
    supports = [inputs["fragment_ao"], inputs["fragment_ao"], *inputs["reference_ao"]]
    for index, allowed in enumerate(supports):
        outside = np.ones(container.shape[0], dtype=bool)
        outside[allowed] = False
        support_residuals[config["container"]["ordered_columns"][index]] = float(
            np.max(np.abs(container[outside, index]))
        )
    phase = phase_covariance(container, overlap)
    permutation = permutation_covariance(container, overlap)
    covariance_maximum = max([*phase.values(), *permutation.values()])
    acceptance = config["acceptance"]
    checks = {
        "isolated_states_reproduced": bool(
            inputs["fragment"]["converged"]
            and all(state["converged"] for state in inputs["references"])
            and len(inputs["candidate_indices"]) == 2
        ),
        "immutable_cut_mapping": min(margins)
        >= float(acceptance["minimum_cut_assignment_margin"]),
        "strict_separate_support": max(support_residuals.values())
        <= float(acceptance["coefficient_support_tolerance"]),
        "normalized": normalization
        <= float(acceptance["normalization_residual_tolerance"]),
        "full_rank_spd": rank == int(acceptance["expected_rank"])
        and float(eigenvalues[0]) > 0.0,
        "conditioned": condition <= float(acceptance["metric_condition_number_limit"]),
        "phase_permutation_covariance": covariance_maximum
        <= float(acceptance["covariance_tolerance"]),
        "pair_overlap_nonzero": min(pair_overlaps)
        >= float(acceptance["minimum_absolute_pair_overlap"]),
        "no_post_smoke_rotation": config["container"]["post_smoke_orbital_rotation"]
        is False,
        "no_production_labels": config["production_labels_allowed"] is False,
    }
    peak_rss_mib = (
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
        if resource is not None
        else float("nan")
    )
    return {
        "schema": "ai4orgchem-two-cut-four-column/1.0",
        "date": date.today().isoformat(),
        "classification": "non-production coefficient/overlap container audit",
        "disposition": "PASS" if all(checks.values()) else "QUARANTINE",
        "checks": checks,
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pyscf": pyscf_version,
            "platform": platform.platform(),
        },
        "container": {
            "ordered_columns": config["container"]["ordered_columns"],
            "shape": list(container.shape),
            "coefficient_hash": hashlib.sha256(
                np.asarray(container, dtype="<f8").tobytes()
            ).hexdigest(),
            "post_smoke_orbital_rotation": False,
        },
        "metric": {
            "matrix": metric.tolist(),
            "rank": rank,
            "minimum_eigenvalue": float(eigenvalues[0]),
            "maximum_eigenvalue": float(eigenvalues[-1]),
            "condition_number": condition,
            "normalization_residual_maximum": normalization,
            "projector": projector_diagnostics(overlap, container),
        },
        "cut_mapping": {
            "cut_ids": [cut["id"] for cut in inputs["smoke"]["geometry"]["cuts"]],
            "target_probe_overlap_matrix": target_probe.tolist(),
            "pair_absolute_overlaps": pair_overlaps,
            "off_pair_absolute_overlaps": off_pair_overlaps,
            "assignment_margins": margins,
        },
        "overlap_ledger": {
            "target_target": float(metric[0, 1]),
            "reference_reference": float(metric[2, 3]),
            "target_reference": target_probe.tolist(),
        },
        "support": {
            "column_residuals": support_residuals,
            "maximum_outside_declared_support": max(support_residuals.values()),
        },
        "covariance": {"phase": phase, "permutation": permutation},
        "provenance": {
            "experiment_id": config["experiment_id"],
            "parent_smoke_config": config["parent_smoke_config"],
            "geometry_hash": sha256_text(
                canonical_geometry(inputs["smoke"]["geometry"]["atoms"])
            ),
            "cut_map_hash": sha256_text(
                json.dumps(inputs["smoke"]["geometry"]["cuts"], sort_keys=True)
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
            "isolated_state_reconstruction_only": True,
            "post_smoke_orbital_rotation_run": False,
            "composite_scf_run": False,
            "conditional_fragment_scf_run": False,
            "energy_generated": False,
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
            "# Gate 0 two-cut four-column container audit",
            "",
            f"- Date: {report['date']}",
            f"- Disposition: **{report['disposition']}**",
            f"- Columns: `{report['container']['ordered_columns']}`",
            "- Orbital rotation / composite SCF / energy: not run",
            "",
            "| Diagnostic | Value | Check |",
            "|---|---:|---|",
            f"| Metric rank / minimum eigenvalue | {report['metric']['rank']} / {report['metric']['minimum_eigenvalue']:.6e} | {'PASS' if checks['full_rank_spd'] else 'FAIL'} |",
            f"| Metric condition number | {report['metric']['condition_number']:.6f} | {'PASS' if checks['conditioned'] else 'FAIL'} |",
            f"| Normalization residual | {report['metric']['normalization_residual_maximum']:.3e} | {'PASS' if checks['normalized'] else 'FAIL'} |",
            f"| Minimum cut-assignment margin | {min(report['cut_mapping']['assignment_margins']):.6e} | {'PASS' if checks['immutable_cut_mapping'] else 'FAIL'} |",
            f"| Maximum support residual | {report['support']['maximum_outside_declared_support']:.3e} | {'PASS' if checks['strict_separate_support'] else 'FAIL'} |",
            f"| Maximum covariance error | {max([*report['covariance']['phase'].values(), *report['covariance']['permutation'].values()]):.3e} | {'PASS' if checks['phase_permutation_covariance'] else 'FAIL'} |",
            "",
            "## Overlap ledger",
            "",
            f"- Four-column metric: `{report['metric']['matrix']}`",
            f"- Pair absolute overlaps: `{report['cut_mapping']['pair_absolute_overlaps']}`",
            f"- Off-pair absolute overlaps: `{report['cut_mapping']['off_pair_absolute_overlaps']}`",
            f"- Target-target / reference-reference: `{report['overlap_ledger']['target_target']:.12f}` / `{report['overlap_ledger']['reference_reference']:.12f}`",
            "",
            "## Boundary",
            "",
            "The composite geometry was used only for AO overlap integrals. No orbital",
            "was rotated after reconstructing the accepted smoke gauge; no determinant,",
            "SCF, occupation, energy, LFMO component, DSI, or FUD label was generated.",
            "",
            "## Provenance",
            "",
            f"- Coefficient SHA-256: `{report['container']['coefficient_hash']}`",
            f"- Geometry SHA-256: `{report['provenance']['geometry_hash']}`",
            f"- Cut-map SHA-256: `{report['provenance']['cut_map_hash']}`",
            f"- Config SHA-256: `{report['provenance']['config_hash']}`",
            f"- Code commit at run: `{report['provenance']['code_commit']}`",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()
    report = json_safe(run_audit(load_yaml(args.config)))
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(
        f"{report['disposition']}: rank={report['metric']['rank']} "
        f"min_eig={report['metric']['minimum_eigenvalue']:.6e} "
        f"condition={report['metric']['condition_number']:.6f} "
        f"assignment_margin={min(report['cut_mapping']['assignment_margins']):.6e}"
    )
    return 0 if report["disposition"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
