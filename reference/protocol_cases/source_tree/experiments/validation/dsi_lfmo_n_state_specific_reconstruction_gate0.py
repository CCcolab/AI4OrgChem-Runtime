"""Construct state-specific LFMO-n candidates without evaluating state energies."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from ai4orgchem.lfmo.state_masks import metric_diagnostics
from experiments.validation.dsi2_divinyl_imine_source_shaped_gate0 import (
    build_source_fragment,
    fragment_atoms,
    run_fragment_uhf_with_fallback,
)
from experiments.validation.one_cut_ch3_reference_h_gate0 import ao_indices_for_atoms
from experiments.validation.one_cut_conditional_scf_gate0 import (
    ROOT,
    git_commit,
    json_safe,
    load_yaml,
)
from experiments.validation.two_cut_ch2_four_column_gate0 import canonical_geometry


DEFAULT_CONFIG = ROOT / "configs" / "qm" / "dsi_lfmo_n_state_specific_reconstruction_v0.1.yaml"
DEFAULT_OUTPUT = ROOT / "artifacts" / "raw" / "dsi_lfmo_n_state_specific_reconstruction_2026-08-14.json"
DEFAULT_MARKDOWN = ROOT / "docs" / "reports" / "gate0_dsi_lfmo_n_state_specific_reconstruction_2026-08-14.md"


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def coefficient_digest(coefficients: np.ndarray) -> str:
    canonical = np.ascontiguousarray(np.asarray(coefficients, dtype="<f8"))
    return hashlib.sha256(canonical.tobytes()).hexdigest()


def unique_cut_bonds(fragments: dict[str, dict[str, Any]]) -> list[list[int]]:
    bonds: set[tuple[int, int]] = set()
    for fragment in fragments.values():
        for atom, partner in zip(
            fragment["cut_atom_indices"],
            fragment["external_partner_indices"],
            strict=True,
        ):
            bonds.add(tuple(sorted((int(atom), int(partner)))))
    return [list(pair) for pair in sorted(bonds)]


def resolve_state_config(master: dict[str, Any], state_id: str) -> dict[str, Any]:
    base = load_yaml(ROOT / str(master["base_config"]))
    state = master["states"][state_id]
    resolved = copy.deepcopy(base)
    resolved["experiment_id"] = f"{master['experiment_id']}:{state_id}"
    resolved["primitive_fragments"] = copy.deepcopy(state["fragments"])
    return resolved


def build_fragment_states_generic(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    electronic = config["electronic_structure"]
    scf_config = config["fragment_scf"]
    lower, upper = map(float, scf_config["singly_occupied_window"])
    states: dict[str, dict[str, Any]] = {}
    for fragment_id, fragment in config["primitive_fragments"].items():
        state = run_fragment_uhf_with_fallback(
            fragment_atoms(config, fragment_id),
            str(electronic["basis"]),
            int(fragment["charge"]),
            int(fragment["spin"]),
            scf_config,
        )
        candidates = [
            int(index)
            for index, occupation in enumerate(state["occupations"])
            if lower <= float(occupation) <= upper
        ]
        states[fragment_id] = {
            **state,
            "candidate_indices": candidates,
            "expected_cut_somos": int(fragment["expected_cut_somos"]),
        }
    return states


def construct_state(master: dict[str, Any], state_id: str) -> tuple[dict[str, Any], np.ndarray]:
    from pyscf import gto

    state_spec = master["states"][state_id]
    config = resolve_state_config(master, state_id)
    fragment_states = build_fragment_states_generic(config)
    source_fragments = {
        fragment_id: build_source_fragment(config, fragment_id, fragment_states[fragment_id])
        for fragment_id in config["primitive_fragments"]
    }
    electronic = config["electronic_structure"]
    parent = gto.M(
        atom=canonical_geometry(config["geometry"]["atoms"]),
        basis=str(electronic["basis"]),
        charge=int(electronic["charge"]),
        spin=int(electronic["spin"]),
        unit="Angstrom",
        symmetry=False,
        verbose=0,
    )
    overlap = parent.intor_symmetric("int1e_ovlp")
    embedded: dict[str, np.ndarray] = {}
    support_residuals: dict[str, float] = {}
    for fragment_id, result in source_fragments.items():
        atom_indices = [
            int(value)
            for value in config["primitive_fragments"][fragment_id]["atom_indices"]
        ]
        rows = ao_indices_for_atoms(parent, atom_indices)
        block = np.zeros((parent.nao_nr(), result["coefficients"].shape[1]))
        block[np.ix_(rows, range(result["coefficients"].shape[1]))] = result[
            "coefficients"
        ]
        outside = np.ones(parent.nao_nr(), dtype=bool)
        outside[rows] = False
        support_residuals[fragment_id] = float(
            np.max(np.abs(block[outside, :])) if np.any(outside) else 0.0
        )
        embedded[fragment_id] = block

    pi_groups = [
        embedded[fragment_id][
            :,
            [
                index
                for index, orbital_type in enumerate(source_fragments[fragment_id]["types"])
                if orbital_type == "pi"
            ],
        ]
        for fragment_id in state_spec["fragments"]
    ]
    sigma_groups = [
        embedded[fragment_id][
            :,
            [
                index
                for index, orbital_type in enumerate(source_fragments[fragment_id]["types"])
                if orbital_type == "sigma"
            ],
        ]
        for fragment_id in state_spec["fragments"]
    ]
    sigma_all = np.column_stack(tuple(sigma_groups))
    working_basis = np.column_stack((*pi_groups, sigma_all))
    metric = metric_diagnostics(working_basis.T @ overlap @ working_basis)
    rank = int(np.linalg.matrix_rank(working_basis))
    cut_bonds = unique_cut_bonds(state_spec["fragments"])
    cut_somos = sum(
        len(fragment_states[fragment_id]["candidate_indices"])
        for fragment_id in state_spec["fragments"]
    )
    fragment_electrons = {
        fragment_id: int(fragment_states[fragment_id]["molecule"].nelectron)
        for fragment_id in state_spec["fragments"]
    }
    fragment_checks = {
        fragment_id: {
            "uhf_converged": bool(fragment_states[fragment_id]["converged"]),
            "electron_count_matches": fragment_electrons[fragment_id]
            == int(fragment["expected_electrons"]),
            "cut_somo_count_matches": len(
                fragment_states[fragment_id]["candidate_indices"]
            )
            == int(fragment["expected_cut_somos"]),
            "kost_quiescent": bool(source_fragments[fragment_id]["kost_quiescent"]),
            "conditional_scf_converged": bool(
                source_fragments[fragment_id]["conditional_converged"]
            ),
            "physical_density_idempotent": float(
                source_fragments[fragment_id]["idempotency"]
            )
            <= float(master["acceptance"]["physical_density_idempotency_tolerance"]),
            "no_mixed_orbitals": int(source_fragments[fragment_id]["mixed_count"]) == 0,
            "strict_fragment_support": support_residuals[fragment_id]
            <= float(master["acceptance"]["coefficient_support_tolerance"]),
        }
        for fragment_id, fragment in state_spec["fragments"].items()
    }
    checks = {
        "all_fragment_checks": all(
            all(values.values()) for values in fragment_checks.values()
        ),
        "fragment_electrons_close_parent": sum(fragment_electrons.values())
        == int(parent.nelectron),
        "cut_bonds_match_state_contract": cut_bonds
        == [[int(item) for item in pair] for pair in state_spec["expected_unique_cut_bonds"]],
        "cut_somo_ledger_matches": cut_somos == int(state_spec["expected_cut_somos"]),
        "basis_square_full_rank": working_basis.shape
        == (parent.nao_nr(), parent.nao_nr())
        and rank == parent.nao_nr(),
        "metric_spd": bool(metric["positive_definite"]),
        "metric_conditioned": float(metric["condition_number"])
        <= float(master["acceptance"]["metric_condition_number_limit"]),
        "no_state_energy_computed": not bool(master["boundaries"]["diagnostic_energy_enabled"]),
        "no_source_label": not bool(master["boundaries"]["source_energy_label_enabled"]),
    }
    state_report = {
        "state_id": state_id,
        "lfmo_n": int(state_spec["lfmo_n"]),
        "fragment_order": list(state_spec["fragments"]),
        "fragment_map_sha256": canonical_digest(state_spec["fragments"]),
        "basis_sha256": coefficient_digest(working_basis),
        "basis_shape": list(working_basis.shape),
        "basis_rank": rank,
        "pi_group_sizes": [int(group.shape[1]) for group in pi_groups],
        "sigma_group_size": int(sigma_all.shape[1]),
        "fragment_electrons": fragment_electrons,
        "total_fragment_electrons": int(sum(fragment_electrons.values())),
        "parent_electrons": int(parent.nelectron),
        "unique_cut_bonds": cut_bonds,
        "cut_somo_count": int(cut_somos),
        "support_residuals": support_residuals,
        "metric": metric,
        "fragment_checks": fragment_checks,
        "checks": checks,
        "disposition": "PASS" if all(checks.values()) else "QUARANTINE",
        "fragments": {
            fragment_id: {
                "natural_somo_indices": fragment_states[fragment_id]["candidate_indices"],
                "natural_somo_occupations": [
                    float(fragment_states[fragment_id]["occupations"][index])
                    for index in fragment_states[fragment_id]["candidate_indices"]
                ],
                "conditional_cycles": int(source_fragments[fragment_id]["conditional_cycles"]),
                "kost_residual": float(source_fragments[fragment_id]["kost_residual"]),
                "idempotency": float(source_fragments[fragment_id]["idempotency"]),
                "type_counts": {
                    orbital_type: int(source_fragments[fragment_id]["types"].count(orbital_type))
                    for orbital_type in ("sigma", "pi", "mixed")
                },
            }
            for fragment_id in state_spec["fragments"]
        },
    }
    return state_report, working_basis


def run(master: dict[str, Any]) -> dict[str, Any]:
    state_reports: dict[str, dict[str, Any]] = {}
    bases: dict[str, np.ndarray] = {}
    for state_id in ("DSI-3", "DSI-2"):
        state_reports[state_id], bases[state_id] = construct_state(master, state_id)
    basis_hashes_differ = (
        state_reports["DSI-3"]["basis_sha256"]
        != state_reports["DSI-2"]["basis_sha256"]
    )
    dsi3_cut_bonds = {tuple(pair) for pair in state_reports["DSI-3"]["unique_cut_bonds"]}
    dsi2_cut_bonds = {tuple(pair) for pair in state_reports["DSI-2"]["unique_cut_bonds"]}
    internalized = sorted(dsi3_cut_bonds - dsi2_cut_bonds)
    cross_checks = {
        "both_state_reconstructions_pass": all(
            state_reports[state]["disposition"] == "PASS"
            for state in ("DSI-3", "DSI-2")
        ),
        "state_basis_hashes_differ": basis_hashes_differ,
        "bc_cut_internalized": internalized == [(3, 4)],
        "two_cut_somos_removed_by_merge": state_reports["DSI-3"]["cut_somo_count"]
        - state_reports["DSI-2"]["cut_somo_count"]
        == 2,
        "same_parent_electron_count": state_reports["DSI-3"]["parent_electrons"]
        == state_reports["DSI-2"]["parent_electrons"]
        == 44,
        "no_energy_calculation": not bool(master["boundaries"]["energy_difference_enabled"]),
    }
    return {
        "experiment_id": master["experiment_id"],
        "protocol": master["protocol"],
        "disposition": "PASS"
        if all(cross_checks.values())
        else "QUARANTINE",
        "states": state_reports,
        "cross_state": {
            "checks": cross_checks,
            "internalized_cut_bonds": [list(pair) for pair in internalized],
            "cut_somo_change": state_reports["DSI-2"]["cut_somo_count"]
            - state_reports["DSI-3"]["cut_somo_count"],
            "basis_hashes_differ": basis_hashes_differ,
            "basis_matrix_frobenius_difference": float(
                np.linalg.norm(bases["DSI-2"] - bases["DSI-3"], ord="fro")
            ),
        },
        "provenance": {
            "git_commit": git_commit(),
            "config_sha256": canonical_digest(master),
        },
        "boundaries": master["boundaries"],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Gate 0 state-specific LFMO-n reconstruction",
        "",
        f"- Disposition: **{report['disposition']}**",
        f"- Protocol: `{report['protocol']}`",
        "- State energies and scientific labels: not computed",
        "",
        "| State | Fragments | LFMO-n | Electrons | Cut bonds | Cut SOMOs | Basis/rank | Pi groups | Sigma |",
        "|---|---|---:|---:|---|---:|---|---|---:|",
    ]
    for state_id in ("DSI-3", "DSI-2"):
        state = report["states"][state_id]
        lines.append(
            "| "
            + " | ".join(
                [
                    state_id,
                    "/".join(state["fragment_order"]),
                    str(state["lfmo_n"]),
                    str(state["total_fragment_electrons"]),
                    str(state["unique_cut_bonds"]),
                    str(state["cut_somo_count"]),
                    f"{state['basis_shape']}/{state['basis_rank']}",
                    str(state["pi_group_sizes"]),
                    str(state["sigma_group_size"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Cross-state result",
            "",
            f"- Internalized cut bond: `{report['cross_state']['internalized_cut_bonds']}`.",
            f"- Cut-SOMO change DSI-3 -> DSI-2: `{report['cross_state']['cut_somo_change']}`.",
            f"- Independent basis hashes: `{report['cross_state']['basis_hashes_differ']}`.",
            "",
        ]
    )
    for state_id in ("DSI-3", "DSI-2"):
        state = report["states"][state_id]
        lines.extend(
            [
                f"## {state_id}",
                "",
                f"- Fragment-map SHA-256: `{state['fragment_map_sha256']}`.",
                f"- Basis SHA-256: `{state['basis_sha256']}`.",
                f"- Metric condition number: `{state['metric']['condition_number']:.6f}`.",
                f"- Maximum support residual: `{max(state['support_residuals'].values()):.3e}`.",
                "",
            ]
        )
    lines.extend(
        [
            "This closes only state-specific basis and electron-ledger construction.",
            "It does not authorize DSI energies, Chapter 5 components, or production labels.",
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
    master = load_yaml(args.config)
    report = run(master)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(json_safe(report), indent=2, sort_keys=True), encoding="utf-8"
    )
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(
        f"{report['disposition']}: "
        f"cut_somos={report['states']['DSI-3']['cut_somo_count']}->"
        f"{report['states']['DSI-2']['cut_somo_count']}"
    )
    return 0 if report["disposition"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
