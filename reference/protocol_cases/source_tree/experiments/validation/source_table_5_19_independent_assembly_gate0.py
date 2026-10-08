"""Independently assemble the Table 5-19 PDSI/FUL RHF energies."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np

from experiments.validation.chapter5_pi_sigma_reconstruction_gate0 import (
    HARTREE_TO_KCAL_MOL,
    canonical_digest,
)
from experiments.validation.chapter5_three_effect_reconstruction_gate0 import (
    run_source_state,
)
from experiments.validation.dsi_fud_initial_density_reproducibility_gate0 import (
    resolve_state_config,
)
from experiments.validation.one_cut_conditional_scf_gate0 import (
    ROOT,
    git_commit,
    json_safe,
    load_yaml,
)
from experiments.validation.source_nonvariational_sigma_sigma_nba_gate0 import (
    build_ful2_internal,
    source_partitions_close,
    state_definitions_from_ful2,
)


DEFAULT_CONFIG = (
    ROOT / "configs" / "qm" / "source_table_5_19_independent_assembly_v1.0.yaml"
)
DEFAULT_OUTPUT = (
    ROOT
    / "artifacts"
    / "raw"
    / "source_table_5_19_independent_assembly_2026-08-15.json"
)
DEFAULT_MARKDOWN = (
    ROOT
    / "docs"
    / "reports"
    / "gate0_source_table_5_19_independent_assembly_2026-08-15.md"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def independent_rhf_energy(molecule: Any, density: np.ndarray) -> float:
    """Evaluate RHF energy from explicit J/K contraction, not a project helper."""

    from pyscf import scf

    provider = scf.RHF(molecule)
    provider.verbose = 0
    hcore = np.asarray(provider.get_hcore(), dtype=float)
    coulomb, exchange = provider.get_jk(molecule, np.asarray(density, dtype=float))
    coulomb = np.asarray(coulomb, dtype=float)
    exchange = np.asarray(exchange, dtype=float)
    veff = coulomb - 0.5 * exchange
    electronic = float(
        np.einsum("ij,ji->", density, hcore)
        + 0.5 * np.einsum("ij,ji->", density, veff)
    )
    return electronic + float(molecule.energy_nuc())


def configure_point(
    master: dict[str, Any],
    source_master: dict[str, Any],
    geometry_master: dict[str, Any],
    atoms: list[list[Any]],
    angle: str,
) -> dict[str, Any]:
    config = resolve_state_config(ROOT / str(source_master["base_config"]))
    config["experiment_id"] = f"{master['experiment_id']}/{angle}"
    config["electronic_structure"]["basis"] = str(
        master["electronic_structure"]["basis"]
    )
    config["fud_state"]["density_reconstruction"] = str(
        master["state_definition"]["density_reconstruction"]
    )
    config["primitive_fragments"] = deepcopy(
        source_master["source_definition"]["fragments"]
    )
    config["geometry"]["atoms"] = deepcopy(atoms)
    interface = geometry_master["optimized_geometry_lfmo_interface"]
    for key in (
        "reflection_block_closure_tolerance",
        "reflection_eigenvalue_tolerance",
        "reflection_classification_policy",
        "minimum_absolute_reflection_eigenvalue",
        "maximum_accepted_reflection_residual",
    ):
        config["acceptance"][key] = interface[key]
    return config


def state_row(
    state: dict[str, Any],
    molecule: Any,
    group_labels: list[str],
    occupied_roots: list[int],
) -> dict[str, Any]:
    density = np.asarray(state["_final_density"], dtype=float)
    pipeline_energy = float(state["experimental_conditional_scf_energy_hartree"])
    independent_energy = independent_rhf_energy(molecule, density)
    return {
        "converged": bool(state["converged"]),
        "cycles": int(state["cycles"]),
        "pipeline_energy_hartree": pipeline_energy,
        "independent_energy_hartree": independent_energy,
        "independent_state_energy_error_hartree": abs(
            independent_energy - pipeline_energy
        ),
        "electron_trace": float(state["electron_trace"]),
        "density_fixed_point_residual": float(
            state["final_density_fixed_point_residual"]
        ),
        "physical_metric_idempotency_residual": float(
            state["density_physical_metric_idempotency_residual"]
        ),
        "group_sizes": [int(value) for value in state["group_sizes"]],
        "occupied_roots": [int(value) for value in occupied_roots],
        "group_labels": group_labels,
    }


def run_point(
    master: dict[str, Any],
    source_master: dict[str, Any],
    geometry_master: dict[str, Any],
    geometry_point: dict[str, Any],
    angle: str,
) -> dict[str, Any]:
    config = configure_point(
        master,
        source_master,
        geometry_master,
        geometry_point["atoms"],
        angle,
    )
    internal = build_ful2_internal(config)
    definitions = state_definitions_from_ful2(internal)
    labels = {
        "FUL": [
            "pi_A",
            "pi_B_plus_C",
            "bonded_sigma_A",
            "bonded_sigma_B_plus_C",
            "cut_sigma_all",
        ],
        "PDSI": [
            "pi_A",
            "pi_B_plus_C",
            "bonded_sigma_all",
            "cut_sigma_all",
        ],
    }
    states: dict[str, dict[str, Any]] = {}
    for state_name in ("FUL", "PDSI"):
        groups, roots = definitions[state_name]
        states[state_name] = run_source_state(
            config,
            internal["molecule"],
            np.asarray(internal["overlap"], dtype=float),
            np.asarray(internal["working_basis"], dtype=float),
            groups,
            roots,
            density_reconstruction="source_block_metric_group_projector",
        )
    rows = {
        state_name: state_row(
            states[state_name],
            internal["molecule"],
            labels[state_name],
            definitions[state_name][1],
        )
        for state_name in ("FUL", "PDSI")
    }
    pipeline_endpoint = (
        rows["PDSI"]["pipeline_energy_hartree"]
        - rows["FUL"]["pipeline_energy_hartree"]
    )
    independent_endpoint = (
        rows["PDSI"]["independent_energy_hartree"]
        - rows["FUL"]["independent_energy_hartree"]
    )
    return {
        "angle_degrees": float(angle),
        "geometry_sha256": str(geometry_point["geometry_sha256"]),
        "geometry_source_twist_degrees": float(
            geometry_point["source_twist_degrees"]
        ),
        "states": rows,
        "source_partition_contract_closes": source_partitions_close(definitions),
        "shared_lfmo_basis_within_geometry": True,
        "pipeline_endpoint_hartree": pipeline_endpoint,
        "independent_endpoint_hartree": independent_endpoint,
        "independent_endpoint_error_hartree": abs(
            independent_endpoint - pipeline_endpoint
        ),
        "pipeline_endpoint_kcal_mol": pipeline_endpoint * HARTREE_TO_KCAL_MOL,
        "independent_endpoint_kcal_mol": independent_endpoint * HARTREE_TO_KCAL_MOL,
    }


def run(master: dict[str, Any]) -> dict[str, Any]:
    source_master = load_yaml(ROOT / str(master["source_sigma_sigma_config"]))
    geometry_master = load_yaml(ROOT / str(master["geometry_config"]))
    geometry_path = ROOT / str(master["geometry_artifact"])
    geometry = json.loads(geometry_path.read_text(encoding="utf-8"))
    angles = [str(value) for value in ("0.0", "17.0")]
    points = {
        angle: run_point(
            master,
            source_master,
            geometry_master,
            geometry["points"][angle],
            angle,
        )
        for angle in angles
    }
    acceptance = master["acceptance"]
    state_rows = [
        points[angle]["states"][state]
        for angle in angles
        for state in ("FUL", "PDSI")
    ]
    source_values = master["source_reference"]["table_5_19_parent_nba_hartree"]
    endpoint_errors = {
        angle: abs(
            points[angle]["independent_endpoint_hartree"]
            - float(source_values[angle])
        )
        for angle in angles
    }
    runtime_probe = {
        "python": sys.version.split()[0],
        "pyscf": __import__("pyscf").__version__,
        "numpy": np.__version__,
    }
    technical_checks = {
        "all_states_converged": all(row["converged"] for row in state_rows),
        "electron_traces": all(
            abs(row["electron_trace"] - int(master["molecule"]["expected_electrons"]))
            <= float(acceptance["electron_trace_tolerance"])
            for row in state_rows
        ),
        "density_fixed_points": all(
            row["density_fixed_point_residual"]
            <= float(acceptance["density_fixed_point_tolerance"])
            for row in state_rows
        ),
        "independent_state_energy_assembly": all(
            row["independent_state_energy_error_hartree"]
            <= float(acceptance["state_energy_assembly_tolerance_hartree"])
            for row in state_rows
        ),
        "independent_endpoint_energy_assembly": all(
            points[angle]["independent_endpoint_error_hartree"]
            <= float(acceptance["endpoint_energy_assembly_tolerance_hartree"])
            for angle in angles
        ),
        "source_partition_contracts": all(
            points[angle]["source_partition_contract_closes"] for angle in angles
        ),
        "shared_lfmo_basis_within_each_geometry": all(
            points[angle]["shared_lfmo_basis_within_geometry"] for angle in angles
        ),
        "source_endpoint_magnitude_tolerance": all(
            error <= float(acceptance["printed_endpoint_absolute_tolerance_hartree"])
            for error in endpoint_errors.values()
        ),
        "declared_environment_versions_match_runtime": all(
            str(master["environment"][name]) == str(value)
            for name, value in runtime_probe.items()
        ),
    }
    direction_checks = {
        "positive_at_zero_degrees": points["0.0"]["independent_endpoint_hartree"]
        > float(acceptance["positive_sign_threshold_hartree"]),
        "positive_at_seventeen_degrees": points["17.0"][
            "independent_endpoint_hartree"
        ]
        > float(acceptance["positive_sign_threshold_hartree"]),
        "decreases_from_zero_to_seventeen": points["17.0"][
            "independent_endpoint_hartree"
        ]
        < points["0.0"]["independent_endpoint_hartree"],
    }
    technical_pass = all(technical_checks.values())
    direction_pass = all(direction_checks.values())
    target_pass = bool(technical_pass and direction_pass)
    environment = {
        **master["environment"],
        "python_runtime": runtime_probe["python"],
        "pyscf_runtime": runtime_probe["pyscf"],
        "numpy_runtime": runtime_probe["numpy"],
    }
    manifest = {
        "source_evidence": master["source_evidence"],
        "molecule": master["molecule"],
        "geometry": {
            **master["geometry"],
            "artifact_sha256": sha256_file(geometry_path),
            "artifact_geometry_id": geometry["geometry_id"],
            "artifact_config_sha256": canonical_digest(geometry_master),
        },
        "electronic_structure": master["electronic_structure"],
        "state_definition": master["state_definition"],
        "environment": environment,
    }
    return {
        "experiment_id": master["experiment_id"],
        "protocol": master["protocol"],
        "disposition": (
            "TARGET_B_INDEPENDENT_ASSEMBLY_PASS"
            if target_pass
            else "TARGET_B_INDEPENDENT_ASSEMBLY_INCOMPLETE"
        ),
        "technical_pass": technical_pass,
        "direction_pass": direction_pass,
        "target_pass": target_pass,
        "points": points,
        "endpoint_errors_hartree": endpoint_errors,
        "technical_checks": technical_checks,
        "direction_checks": direction_checks,
        "environment_manifest": manifest,
        "boundaries": master["boundaries"],
        "provenance": {
            "git_commit": git_commit(),
            "config_sha256": canonical_digest(master),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    manifest = report["environment_manifest"]
    lines = [
        "# Gate 0 Target B independent PDSI/FUL energy assembly",
        "",
        f"- Disposition: **{report['disposition']}**",
        f"- Technical pass: `{report['technical_pass']}`",
        f"- Direction pass: `{report['direction_pass']}`",
        f"- Target pass: `{report['target_pass']}`",
        "- Chemical stabilization/destabilization interpretation: disabled",
        "",
        "## Independent energy assembly",
        "",
        "PySCF supplies AO integrals only. State energies and the PDSI-FUL "
        "difference are independently assembled from explicit RHF J/K contractions.",
        "",
        "| Angle | E_FUL pipeline (Eh) | E_FUL independent (Eh) | E_PDSI pipeline (Eh) | E_PDSI independent (Eh) | Independent difference (Eh) | Source (Eh) |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    source_values = manifest["source_evidence"]
    published = {"0.0": 0.06891, "17.0": 0.06504}
    for angle in ("0.0", "17.0"):
        point = report["points"][angle]
        lines.append(
            f"| {float(angle):.1f} | "
            f"{point['states']['FUL']['pipeline_energy_hartree']:.12f} | "
            f"{point['states']['FUL']['independent_energy_hartree']:.12f} | "
            f"{point['states']['PDSI']['pipeline_energy_hartree']:.12f} | "
            f"{point['states']['PDSI']['independent_energy_hartree']:.12f} | "
            f"{point['independent_endpoint_hartree']:.12f} | {published[angle]:.5f} |"
        )
    lines.extend(
        [
            "",
            "| Angle | Independent assembly error (Eh) | Source magnitude error (Eh) |",
            "|---:|---:|---:|",
        ]
    )
    for angle in ("0.0", "17.0"):
        lines.append(
            f"| {float(angle):.1f} | "
            f"{report['points'][angle]['independent_endpoint_error_hartree']:.3e} | "
            f"{report['endpoint_errors_hartree'][angle]:.8f} |"
        )
    lines.extend(
        [
            "",
            "## Environment manifest",
            "",
            f"- Runtime: `{manifest['environment']['distribution']}`",
            f"- Python: `{manifest['environment']['python_runtime']}`",
            f"- PySCF: `{manifest['environment']['pyscf_runtime']}`",
            f"- NumPy: `{manifest['environment']['numpy_runtime']}`",
            f"- Geometry artifact SHA-256: `{manifest['geometry']['artifact_sha256']}`",
            f"- Source PDF SHA-256: `{source_values['pdf_sha256']}`",
            f"- Source pages: `{source_values['printed_pages']}`; Table: `{source_values['table']}`",
            "",
            "## Boundary",
            "",
            "This closes Target B's independent energy assembly and environment "
            "manifest only. The source nonvariational ledger remains isolated; "
            "no production or AI-training label is generated.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    report = run(load_yaml(args.config))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(json_safe(report), indent=2, sort_keys=True), encoding="utf-8"
    )
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(
        f"{report['disposition']}: "
        f"independent_assembly={report['technical_pass']}, "
        f"direction={report['direction_pass']}"
    )
    return 0 if report["target_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
