"""Calculate the same-engine source-2007 benzene ESE anchor for P11-B."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from ai4orgchem.qm.p09_ao_classification import classify_planar_pyscf_aos
from ai4orgchem.qm.p09_conditional_scf import run_p09_conditional_rks


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = ROOT / "configs/qm/p11_benzene_2007_anchor_v0.1.yaml"
DEFAULT_OUTPUT = ROOT / "data/processed/p11_benzene_2007_anchor_v0.1.json"
DEFAULT_REPORT = ROOT / "docs/reports/p11_benzene_2007_anchor_2026-08-22.md"
HARTREE_TO_KCAL_PER_MOL = 627.5094740631


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def regular_benzene(CC: float, CH: float) -> list[list[Any]]:
    angles = np.arange(6, dtype=float) * np.pi / 3.0
    carbons = np.column_stack((CC * np.cos(angles), CC * np.sin(angles)))
    hydrogens = np.column_stack(((CC + CH) * np.cos(angles), (CC + CH) * np.sin(angles)))
    return [
        *[["C", float(x), float(y), 0.0] for x, y in carbons],
        *[["H", float(x), float(y), 0.0] for x, y in hydrogens],
    ]


def chain_ring(
    chain_lengths: list[float], chain_angles_degrees: list[float], CH_lengths: list[float]
) -> tuple[list[list[Any]], dict[str, Any]]:
    lengths = np.asarray(chain_lengths, dtype=float)
    angles = np.radians(np.asarray(chain_angles_degrees, dtype=float))
    if lengths.shape != (5,) or angles.shape != (4,):
        raise ValueError("benzene Z-matrix chain requires five lengths and four angles")
    ring = np.zeros((6, 2), dtype=float)
    ring[1] = [lengths[0], 0.0]
    direction = 0.0
    for atom_index in range(2, 6):
        direction -= np.pi - angles[atom_index - 2]
        ring[atom_index] = ring[atom_index - 1] + lengths[atom_index - 1] * np.asarray(
            [np.cos(direction), np.sin(direction)]
        )
    ring -= np.mean(ring, axis=0)

    hydrogens = []
    for index, distance in enumerate(CH_lengths):
        previous = ring[(index - 1) % 6] - ring[index]
        following = ring[(index + 1) % 6] - ring[index]
        inward = previous / np.linalg.norm(previous) + following / np.linalg.norm(following)
        outward = -inward / np.linalg.norm(inward)
        hydrogens.append(ring[index] + float(distance) * outward)
    atoms = [
        *[["C", float(x), float(y), 0.0] for x, y in ring],
        *[["H", float(x), float(y), 0.0] for x, y in hydrogens],
    ]
    ring_bonds = [
        float(np.linalg.norm(ring[(index + 1) % 6] - ring[index])) for index in range(6)
    ]
    return atoms, {
        "ring_bonds_angstrom": ring_bonds,
        "closure_C6_C1_angstrom": ring_bonds[-1],
        "CH_angstrom": [
            float(np.linalg.norm(hydrogens[index] - ring[index])) for index in range(6)
        ],
    }


def build_molecule(atoms: list[list[Any]], protocol: dict[str, Any]) -> Any:
    from pyscf import gto

    options = protocol["electronic_structure"]
    return gto.M(
        atom=atoms,
        basis=str(options["basis"]),
        charge=int(options["charge"]),
        spin=int(options["multiplicity"]) - 1,
        unit="Angstrom",
        symmetry=False,
        verbose=0,
    )


def build_mean_field(molecule: Any, protocol: dict[str, Any]) -> Any:
    from pyscf import dft

    options = protocol["electronic_structure"]
    mean_field = dft.RKS(molecule)
    mean_field.verbose = 0
    mean_field.xc = str(options["pyscf_xc"])
    mean_field.grids.level = int(options["grid_level"])
    mean_field.conv_tol = float(options["scf_tolerance_hartree"])
    mean_field.max_cycle = int(options["maximum_scf_cycles"])
    mean_field.max_memory = int(options["maximum_memory_mb"])
    return mean_field


def ordinary_state(atoms: list[list[Any]], protocol: dict[str, Any]) -> dict[str, Any]:
    molecule = build_molecule(atoms, protocol)
    mean_field = build_mean_field(molecule, protocol)
    energy = float(mean_field.kernel())
    return {
        "converged": bool(mean_field.converged),
        "total_energy_hartree": energy,
        "electronic_energy_hartree": energy - float(molecule.energy_nuc()),
        "nuclear_repulsion_hartree": float(molecule.energy_nuc()),
        "density": np.asarray(mean_field.make_rdm1(), dtype=float),
    }


def conditional_state(
    atoms: list[list[Any]],
    fragment_map: dict[int, str],
    initial_density: np.ndarray,
    protocol: dict[str, Any],
    *,
    mask_one_electron_matrix: bool = True,
) -> dict[str, Any]:
    molecule = build_molecule(atoms, protocol)
    mean_field = build_mean_field(molecule, protocol)
    descriptors = classify_planar_pyscf_aos(molecule, fragment_map)
    options = protocol["conditional_scf"]
    return run_p09_conditional_rks(
        mean_field,
        descriptors,
        [],
        initial_density=initial_density,
        maximum_cycles=int(options["maximum_cycles"]),
        density_tolerance=float(options["density_tolerance"]),
        energy_tolerance=float(options["energy_tolerance_hartree"]),
        diis_start_cycle=int(options["diis_start_cycle"]),
        diis_space=int(options["diis_space"]),
        damping_cycles=int(options["damping_cycles"]),
        damping=float(options["damping"]),
        mask_one_electron_matrix=mask_one_electron_matrix,
    )


def compact(state: dict[str, Any]) -> dict[str, Any]:
    excluded = {"density", "mo_coefficients", "mo_energies_hartree", "mo_occupations"}
    return {key: value for key, value in state.items() if key not in excluded}


def run(
    protocol_path: Path, *, mask_one_electron_matrix: bool = True
) -> dict[str, Any]:
    protocol = yaml.safe_load(protocol_path.read_text(encoding="utf-8"))
    if protocol["execution"]["scope"] != "single_benzene_G_GL_GE1_source_2007_anchor_only":
        raise RuntimeError("P11 benzene anchor scope is not authorized")
    geometry = protocol["geometry"]
    g_atoms = regular_benzene(
        float(geometry["G"]["regular_CC_angstrom"]), float(geometry["G"]["common_CH_angstrom"])
    )
    gl_atoms, gl_geometry = chain_ring(
        geometry["GL"]["chain_CC_angstrom"],
        geometry["GL"]["chain_angles_degrees"],
        geometry["GL"]["CH_angstrom"],
    )
    ge1_atoms, ge1_geometry = chain_ring(
        geometry["GE1"]["chain_CC_angstrom"],
        geometry["GE1"]["chain_angles_degrees"],
        geometry["GE1"]["CH_angstrom"],
    )

    g_raw = ordinary_state(g_atoms, protocol)
    if not g_raw["converged"]:
        raise RuntimeError("source-2007 benzene G did not converge")
    g_density = np.asarray(g_raw["density"], dtype=float)
    gl_map = {0: "A", 1: "A", 2: "B", 3: "B", 4: "C", 5: "C"}
    ge1_map = {0: "A", 1: "A", 2: "BC", 3: "BC", 4: "BC", 5: "BC"}
    gl_raw = conditional_state(
        gl_atoms,
        gl_map,
        g_density,
        protocol,
        mask_one_electron_matrix=mask_one_electron_matrix,
    )
    if not gl_raw["converged"]:
        raise RuntimeError("source-2007 benzene GL did not converge")
    gl_density = np.asarray(gl_raw["density"], dtype=float)
    ge1_raw = conditional_state(
        ge1_atoms,
        ge1_map,
        gl_density,
        protocol,
        mask_one_electron_matrix=mask_one_electron_matrix,
    )
    if not ge1_raw["converged"]:
        raise RuntimeError("source-2007 benzene GE1 did not converge")

    g_state, gl_state, ge1_state = compact(g_raw), compact(gl_raw), compact(ge1_raw)
    g_energy = float(g_state["total_energy_hartree"])
    gl_energy = float(gl_state["total_energy_hartree"])
    ge1_energy = float(ge1_state["total_energy_hartree"])
    delta_ea = g_energy - gl_energy
    delta_ea1 = ge1_energy - gl_energy
    ese = delta_ea - 3.0 * delta_ea1

    acceptance = protocol["acceptance"]
    direction = float(acceptance["strict_direction_tolerance_hartree"])
    checks = {
        "G_converged": bool(g_state["converged"]),
        "GL_converged": bool(gl_state["converged"]),
        "GE1_converged": bool(ge1_state["converged"]),
        "GL_42_electrons": abs(float(gl_state["masked_metric_electron_count"]) - 42.0)
        <= float(acceptance["electron_count_tolerance"]),
        "GE1_42_electrons": abs(float(ge1_state["masked_metric_electron_count"]) - 42.0)
        <= float(acceptance["electron_count_tolerance"]),
        "GL_cross_pi_zero": float(gl_state["conditional_fock_cross_pi_max_abs"])
        <= float(acceptance["matrix_zero_tolerance"]),
        "GE1_cross_pi_zero": float(ge1_state["conditional_fock_cross_pi_max_abs"])
        <= float(acceptance["matrix_zero_tolerance"]),
        "GL_no_ERI_deletion": int(gl_state["deleted_eri_count"]) == 0,
        "GE1_no_ERI_deletion": int(ge1_state["deleted_eri_count"]) == 0,
        "delta_EA_negative": delta_ea < -direction,
        "delta_EA1_positive": delta_ea1 > direction,
        "ESE_negative": ese < -direction,
    }
    return {
        "schema_version": 1,
        "protocol_id": protocol["protocol_id"],
        "proposition_id": "P11",
        "subtarget": "P11-B_same_engine_benzene_anchor",
        "implementation_semantics": protocol["state_contract"]["implementation_semantics"],
        "one_electron_matrix_masked": bool(mask_one_electron_matrix),
        "G": {"atoms_angstrom": g_atoms, "state": g_state},
        "GL": {"atoms_angstrom": gl_atoms, "geometry": gl_geometry, "state": gl_state},
        "GE1": {"atoms_angstrom": ge1_atoms, "geometry": ge1_geometry, "state": ge1_state},
        "delta_EA_hartree": delta_ea,
        "delta_EA_kcal_mol": delta_ea * HARTREE_TO_KCAL_PER_MOL,
        "delta_EA1_hartree": delta_ea1,
        "delta_EA1_kcal_mol": delta_ea1 * HARTREE_TO_KCAL_PER_MOL,
        "ESE_benzene_hartree": ese,
        "ESE_benzene_kcal_mol": ese * HARTREE_TO_KCAL_PER_MOL,
        "acceptance_checks": checks,
        "calculation_gate_verdict": "PASS" if all(checks.values()) else "FAIL",
        "production_label": False,
        "training_eligible": False,
    }


def render_report(record: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# P11-B source-2007 苯锚点",
            "",
            f"- 协议：`{record['protocol_id']}`",
            f"- ΔEA：`{record['delta_EA_kcal_mol']:+.6f} kcal/mol`",
            f"- ΔEA1：`{record['delta_EA1_kcal_mol']:+.6f} kcal/mol`",
            f"- ESE(benzene)：`{record['ESE_benzene_kcal_mol']:+.6f} kcal/mol`",
            f"- 计算门禁：`{record['calculation_gate_verdict']}`",
            "",
            "该锚点只用于P11-B同实现诱导项，不替换或重开P09结论。",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    arguments = parser.parse_args()
    record = run(arguments.protocol.resolve())
    write_json(arguments.output.resolve(), record)
    arguments.report.resolve().parent.mkdir(parents=True, exist_ok=True)
    arguments.report.resolve().write_text(render_report(record), encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": record["calculation_gate_verdict"],
                "ESE_benzene_kcal_mol": record["ESE_benzene_kcal_mol"],
                "output": str(arguments.output.resolve()),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0 if record["calculation_gate_verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
