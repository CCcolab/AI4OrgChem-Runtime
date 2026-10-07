"""Validate the frozen P01 ethene occupied-gauge calculation artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE = ROOT / "artifacts/raw/p01_ethene_orbital_density_control_2026-08-20.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    args = parser.parse_args()
    evidence = json.loads(args.evidence.resolve().read_text(encoding="utf-8"))
    assert evidence["protocol_id"] == "P01_ETHENE_OCCUPIED_GAUGE_CONTROL_V0.1"
    assert evidence["proposition_id"] == "P01"
    assert evidence["verdict"] == "P01_ACTUAL_OCCUPIED_GAUGE_CONTROL_PASSED"
    assert evidence["scf"]["converged"] is True
    assert [item["name"] for item in evidence["representations"]] == ["canonical", "boys", "pipek_mezey"]
    required_true = {
        "scf_converged",
        "all_representations_span_same_occupied_subspace",
        "ao_density_invariant",
        "electron_number_invariant",
        "rhf_energy_invariant",
        "orbital_fragment_support_changes",
        "same_state_orbital_representation_is_not_electron_state_delocalization",
    }
    assert all(evidence["findings"][key] is True for key in required_true)
    assert evidence["findings"]["chemical_stabilization_label_authorized"] is False
    for source in evidence["inputs"].values():
        assert sha256_file(ROOT / source["path"]) == source["sha256"]
    config = evidence["config"]
    assert sha256_file(ROOT / config["path"]) == config["sha256"]
    summary = {
        "verdict": evidence["verdict"],
        "max_density_relative_residual": max(
            item["density_relative_frobenius_residual_from_canonical"] for item in evidence["representations"]
        ),
        "max_energy_residual_hartree": max(
            item["energy_residual_from_canonical_hartree"] for item in evidence["representations"]
        ),
        "entropy_change_from_canonical": evidence["entropy_change_from_canonical"],
        "p02_p03_p08_started": False,
    }
    print("PASS_P01_ETHENE_OCCUPIED_GAUGE_CONTROL")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
