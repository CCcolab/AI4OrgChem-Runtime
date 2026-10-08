"""Read-only N16 execution contract and authorization checks; no QM imports."""

from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
N16_CONTRACT_ID = "p12-source2011-same-basis-n16-execution/0.1"
N16_CONTRACT = ROOT / "configs/qm/p12_source2011_same_basis_n16_execution_v0.1.yaml"
BASE_PROTOCOL_ID = "p12-source2011-planar-cese-recalculation/0.2"


def repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def all_pairs() -> list[tuple[int, int]]:
    return list(itertools.combinations(range(8), 2))


def load_protocol(value: str | Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Return frozen base plus optional N16-only overlay, with hash binding."""
    path = repo_path(value)
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if document.get("protocol_id") != N16_CONTRACT_ID:
        return document, None
    if path.resolve() != N16_CONTRACT.resolve():
        raise ValueError("N16 contract must use its frozen repository path")
    base_path = repo_path(document["base_protocol"])
    if sha256(base_path) != document["base_protocol_sha256"]:
        raise ValueError("N16 base protocol SHA-256 mismatch")
    base = yaml.safe_load(base_path.read_text(encoding="utf-8"))
    if base.get("protocol_id") != BASE_PROTOCOL_ID:
        raise ValueError("N16 base protocol identity mismatch")
    if base["authorization_scope"] != {
        "authorized_systems": [12, 14],
        "authorized_states": ["G", "GL", "GE"],
        "stop_after": "N14_ledger_and_quality_review",
        "N16_or_larger_automatic_execution": False,
        "classification_change_before_six_point_completion_forbidden": True,
    }:
        raise ValueError("N16 requires the unchanged N12/N14 authorization boundary")
    scope = document["scope"]
    if not (
        document["status"] == "static_preflight_ready_manual_execution_only"
        and scope["estimand_identity"] == "independent_same_basis_source2011_candidate_not_historical_2011_replica"
        and scope["source_program_code_used"] is False
        and scope["system"] == 16
        and scope["configuration"] == "[16]-5555"
        and scope["states"] == ["G", "GL", "GE"]
        and scope["geometry_and_energy_method"] == "B3LYPG/6-311g(2df,p)"
        and scope["fully_planar"] is True
        and scope["historical_2011_method_alignment"] == "NOT_ESTABLISHED"
        and scope["classification_change_allowed"] is False
        and scope["N18_or_larger_automatic_execution"] is False
        and scope["electronic_state_continuity"] == "NOT_PROVEN_BY_CURRENT_RUNNER"
        and scope["state_acceptance"] == "planar_inner_h_topology_and_SCF_convergence_required"
    ):
        raise ValueError("N16 scope/method/publication boundary mismatch")
    geometry, energy = base["geometry_contract"], base["energy_contract"]
    if not (
        geometry["method"] == energy["method"] == "B3LYPG"
        and geometry["basis"] == energy["basis"] == "6-311g(2df,p)"
        and geometry["dimensionality"] == "fully_planar"
        and geometry["hard_constraint"] == "all_atomic_z_coordinates_equal_zero_throughout_optimization"
        and geometry["charge"] == energy.get("charge", geometry["charge"]) == 0
        and geometry["multiplicity"] == energy.get("multiplicity", geometry["multiplicity"]) == 1
    ):
        raise ValueError("N16 requires same-basis fully planar G/GL/GE")
    plan = document["pair_plan"]
    pairs = all_pairs()
    adjacent = sum(min(b - a, 8 - (b - a)) == 1 for a, b in pairs)
    if not (
        plan["selection"] == "exhaustive_all_28_no_symmetry_weighting"
        and plan["localized_pi_group_count"] == 8
        and plan["total_pair_count"] == len(pairs) == 28
        and plan["adjacent_pair_count"] == adjacent == 8
        and plan["nonadjacent_pair_count"] == len(pairs) - adjacent == 20
        and plan["pair_order"] == "lexicographic_zero_based"
        and plan["pair_multiplicity"] == 1
    ):
        raise ValueError("N16 complete GE pair contract mismatch")
    controls = document["execution_controls"]
    if not (
        controls["explicit_execute_flag_required"] is True
        and controls["default_new_optimizations_per_invocation"] == 1
        and controls["maximum_new_optimizations_per_invocation"] == 1
        and controls["ge_requires_separate_explicit_approval_after_g_gl"] is True
        and 1 <= controls["maximum_threads"] <= 16
        and controls["memory_limit_mib_per_state"] == 12000
        and 0 < controls["maximum_hours_per_state"] <= 12
        and 0 < controls["maximum_geometry_steps_per_state"] <= 80
        and controls["checkpoint_resume"] is True
        and controls["force_overwrite_allowed"] is False
        and controls["duplicate_queue_allowed"] is False
        and controls["failure_action"] == "STOP_FAILED_CLOSED"
    ):
        raise ValueError("N16 resource/stop contract mismatch")
    if document["outputs"]["no_automatic_ledger_or_classification"] is not True:
        raise ValueError("N16 cannot auto-assemble or reclassify")
    return {**base, "protocol_id": N16_CONTRACT_ID}, document


def require_authorized_state(
    protocol: dict[str, Any], contract: dict[str, Any] | None,
    n_carbon: int, state: str, pair: tuple[int, int] | None,
) -> None:
    """Reject out-of-scope N16 and malformed GE pairs before any QM call."""
    if contract is None:
        if protocol.get("protocol_id") == BASE_PROTOCOL_ID:
            scope = protocol["authorization_scope"]
            if n_carbon not in scope["authorized_systems"] or state not in scope["authorized_states"]:
                raise ValueError(f"N{n_carbon} {state} not authorized by v0.2 base protocol")
        return
    if n_carbon != 16 or state not in ("G", "GL", "GE"):
        raise ValueError("N16 contract does not authorize another system/state")
    if (state == "GE" and pair not in all_pairs()) or (state != "GE" and pair is not None):
        raise ValueError("N16 GE must use one of 28 unique zero-based pairs")


def preflight(value: str | Path = N16_CONTRACT) -> dict[str, Any]:
    protocol, contract = load_protocol(value)
    if contract is None:
        raise ValueError("N16 preflight requires N16-specific contract")
    manifest_path = repo_path(protocol["output_contract"]["seed_manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = next(row for row in manifest["records"] if row["N"] == 16)
    if not (
        record["configuration"] == "[16]-5555"
        and record["inner_hydrogen_carbon_indices_zero_based"] == [0, 4, 8, 12]
        and record["inner_hydrogen_topology_verified"] is True
        and record["maximum_absolute_z_angstrom"] == 0.0
    ):
        raise ValueError("N16 source-selected planar seed identity mismatch")
    seed = repo_path(record["path"])
    constraint = repo_path(record["constraint_path"])
    if sha256(seed) != record["sha256"] or sha256(constraint) != record["constraint_sha256"]:
        raise ValueError("N16 seed/constraint hash mismatch")
    xyz_lines = seed.read_text(encoding="utf-8").splitlines()
    if len(xyz_lines) != 34 or xyz_lines[0].strip() != "32":
        raise ValueError("N16 seed must contain exactly 32 atoms")
    symbols = [line.split()[0] for line in xyz_lines[2:]]
    if symbols != ["C"] * 16 + ["H"] * 16:
        raise ValueError("N16 seed atom order is not 16 C followed by 16 H")
    if any(len(line.split()) != 4 or abs(float(line.split()[3])) > 1e-8 for line in xyz_lines[2:]):
        raise ValueError("N16 seed is not fully planar")
    if constraint.read_text(encoding="utf-8") != "$freeze\nz 1-32\n":
        raise ValueError("N16 planarity constraint mismatch")
    if not (contract["outputs"]["status"].startswith("data/processed/p12_source2011_same_basis_planar_states_v0.2/")
            and contract["outputs"]["lock"].startswith("runs/p12_source2011_same_basis_v0.2/")):
        raise ValueError("N16 output paths outside isolated v0.2 workspace")
    return {
        "gate": "READY_FOR_EXPLICIT_N16_EXECUTION",
        "protocol_id": contract["protocol_id"],
        "contract_sha256": sha256(repo_path(value)),
        "base_protocol_sha256": contract["base_protocol_sha256"],
        "configuration": record["configuration"],
        "charge": 0,
        "multiplicity": 1,
        "atom_count": 32,
        "seed_sha256": record["sha256"],
        "constraint_sha256": record["constraint_sha256"],
        "GE_pair_count": len(all_pairs()),
        "adjacent_pair_count": 8,
        "nonadjacent_pair_count": 20,
        "historical_2011_method_alignment": "NOT_ESTABLISHED",
        "quantum_calculation_performed": False,
    }
