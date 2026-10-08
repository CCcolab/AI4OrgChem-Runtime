"""Validate the P07 same-Hamiltonian state-path audit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "data/processed/p07_same_hamiltonian_path_audit_v0.2.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate() -> dict:
    data = json.loads(RESULT.read_text(encoding="utf-8"))
    require(data["technical_pass"] is True, "P07 path audit is not technically passing")
    require(
        data["verdict"] == "P07_CONSISTENT_WITH_INDEPENDENT_SAME_HAMILTONIAN_PATH_AUDIT",
        "unexpected P07 verdict",
    )
    require(
        data["evidence_identity"] == "INDEPENDENT_COMPUTATIONAL_AUDIT_PLUS_DERIVED_SYNTHESIS",
        "unexpected P07 evidence identity",
    )
    require(data["counts_as_independent_computational_audit"] is True, "independent audit flag missing")
    require(set(data["points"]) == {"0.0", "17.0"}, "frozen angle set changed")
    for key, point in data["points"].items():
        require(all(point["checks"].values()), f"failed point check at {key}")
        naive_residual = abs(
            point["naive_three_terms_hartree"]["closure_residual_vs_E_G_minus_E_FUL"]
        )
        require(naive_residual >= 0.30, f"naive residual unexpectedly small at {key}")
        require(
            abs(point["four_term_state_path_hartree"]["closure_residual_vs_E_G_minus_E_FUL"])
            <= 1.0e-9,
            f"four-term path does not close at {key}",
        )
        require(
            abs(point["path_complete_three_terms_hartree"]["closure_residual_vs_E_G_minus_E_FUL"])
            <= 1.0e-9,
            f"path-complete three terms do not close at {key}",
        )
    require(all(data["global_checks"].values()), "a global P07 path-audit check failed")
    require(data["boundaries"]["new_qm_calculation"] is False, "unexpected new QM scope")
    require(data["boundaries"]["cross_protocol_energy_sum"] is False, "cross-protocol sum enabled")
    return {
        "verdict": "PASS_P07_SAME_HAMILTONIAN_PATH_AUDIT",
        "scientific_verdict": data["verdict"],
        "angles": len(data["points"]),
        "maximum_naive_residual_hartree": max(
            abs(point["naive_three_terms_hartree"]["closure_residual_vs_E_G_minus_E_FUL"])
            for point in data["points"].values()
        ),
        "maximum_path_complete_residual_hartree": max(
            abs(point["path_complete_three_terms_hartree"]["closure_residual_vs_E_G_minus_E_FUL"])
            for point in data["points"].values()
        ),
        "result_sha256": hashlib.sha256(RESULT.read_bytes()).hexdigest(),
    }


def main() -> int:
    print(json.dumps(validate(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
