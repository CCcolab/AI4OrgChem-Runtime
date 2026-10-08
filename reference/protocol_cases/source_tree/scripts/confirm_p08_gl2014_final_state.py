"""Confirm the final P08 GL(2014) state from an independent ordinary-RKS density."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import yaml

from ai4orgchem.lfmo.gl2014 import run_gl2014_scf
from scripts.run_p08_butadiene_gl2014 import build_mean_field, build_molecule


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/qm/p08_butadiene_gl2014_v0.1.yaml"
EVIDENCE = ROOT / "data/processed/p08_butadiene_gl2014_evidence_v0.1.json"
OUTPUT = ROOT / "runs/validation/p08_butadiene_gl2014_independent_initial_density_confirmation_v0.1.json"


def main() -> None:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    atoms = evidence["gl2014_geometry"]["atoms"]
    molecule = build_molecule(atoms, config)
    ordinary = build_mean_field(molecule, config)
    ordinary_energy = float(ordinary.kernel())
    if not ordinary.converged:
        raise RuntimeError("independent ordinary RKS initial-density calculation failed")
    initial_density = np.asarray(ordinary.make_rdm1(), dtype=float)
    options = config["gl2014_conditional_scf"]
    result = run_gl2014_scf(
        build_mean_field(molecule, config),
        config["system"]["carbon_fragment_left_atoms"],
        config["system"]["carbon_fragment_right_atoms"],
        initial_density=initial_density,
        maximum_cycles=int(options["maximum_cycles"]),
        density_tolerance=float(options["density_tolerance"]),
        energy_tolerance=float(options["energy_tolerance_hartree"]),
        density_diis_start_cycle=int(options["density_diis_start_cycle"]),
        density_diis_space=int(options["density_diis_space"]),
        damping=float(options["damping"]),
    )
    frozen_energy = float(evidence["gl2014_geometry"]["total_energy_hartree"])
    energy_error = abs(float(result["total_energy_hartree"]) - frozen_energy)
    audit = result["occupied_pi_audit"]
    checks = {
        "ordinary_initial_density_converged": True,
        "conditional_state_converged": bool(result["converged"]),
        "energy_reproduced_within_1e_minus_9_hartree": energy_error <= 1.0e-9,
        "one_occupied_pi_per_fragment": int(audit["left_occupied_pi_count"]) == 1
        and int(audit["right_occupied_pi_count"]) == 1,
        "no_mixed_occupied_pi": int(audit["mixed_occupied_pi_count"]) == 0,
        "modified_metric_electron_count_closes": abs(
            float(result["modified_metric_electron_count"]) - 30.0
        )
        <= float(config["acceptance"]["modified_metric_electron_tolerance"]),
    }
    if not all(checks.values()):
        raise RuntimeError(f"P08 independent-initial-density confirmation failed: {checks}")
    record = {
        "schema_version": 1,
        "protocol_id": config["protocol_id"],
        "proposition_id": "P08",
        "confirmation": "independent_ordinary_RKS_initial_density",
        "verdict": "PASS_P08_GL2014_INDEPENDENT_INITIAL_DENSITY_CONFIRMATION",
        "ordinary_RKS_energy_hartree": ordinary_energy,
        "frozen_GL2014_energy_hartree": frozen_energy,
        "confirmed_GL2014_energy_hartree": float(result["total_energy_hartree"]),
        "absolute_energy_error_hartree": energy_error,
        "conditional_cycles": int(result["cycles"]),
        "modified_metric_electron_count": float(result["modified_metric_electron_count"]),
        "physical_metric_electron_count": float(result["physical_metric_electron_count"]),
        "occupied_pi_audit": audit,
        "checks": checks,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": record["verdict"], "energy_error_hartree": energy_error}, ensure_ascii=False))


if __name__ == "__main__":
    main()

