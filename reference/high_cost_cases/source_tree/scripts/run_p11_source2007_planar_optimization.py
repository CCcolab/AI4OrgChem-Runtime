"""Run one source-2007 P11-B state with a hard all-atom planar constraint.

Each invocation optimizes exactly one state.  Outputs are state-specific and
resume-safe; the historical P11-B records are never overwritten.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from ai4orgchem.qm.p09_ao_classification import classify_planar_pyscf_aos
from ai4orgchem.qm.p11_source2007_rks import Source2007ConditionalRKS
from scripts.run_p11_benzene_2007_anchor import (
    build_mean_field as build_benzene_mean_field,
    build_molecule as build_benzene_molecule,
    chain_ring,
    ordinary_state as benzene_ordinary_state,
    regular_benzene,
)
from scripts.run_p11_cyanobenzene_effect import (
    build_mean_field as build_cyanobenzene_mean_field,
    build_molecule as build_cyanobenzene_molecule,
    conditional_state as cyanobenzene_conditional_state,
    cyanobenzene_atoms,
    ordinary_state as cyanobenzene_ordinary_state,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
CYANO_PROTOCOL = ROOT / "configs/qm/p11_substituted_benzene_effect_v0.1.yaml"
BENZENE_PROTOCOL = ROOT / "configs/qm/p11_benzene_2007_anchor_v0.1.yaml"
OUTPUT_DIR = ROOT / "data/processed/p11_source2007_planar_optimized_v0.2"
REPORT_DIR = ROOT / "docs/reports/p11_source2007_planar_optimized_v0.2"
CYANO_CONSTRAINTS = ROOT / "configs/qm/p11_cyanobenzene_all_atom_planar.constraints"
BENZENE_CONSTRAINTS = ROOT / "configs/qm/p11_benzene_all_atom_planar.constraints"

CYANO_FRAGMENT_MAPS = {
    "G": None,
    "GL_I": {0: "A", 1: "A", 2: "B", 3: "B", 4: "C", 5: "C", 6: "A", 7: "A"},
    "GE1": {0: "AB", 1: "AB", 2: "AB", 3: "AB", 4: "C", 5: "C", 6: "AB", 7: "AB"},
    "GE2": {0: "AC", 1: "AC", 2: "B", 3: "B", 4: "AC", 5: "AC", 6: "AC", 7: "AC"},
    "GE3": {0: "A", 1: "A", 2: "BC", 3: "BC", 4: "BC", 5: "BC", 6: "A", 7: "A"},
    "GL_II": {0: "A", 1: "A", 2: "B", 3: "B", 4: "C", 5: "C", 6: "X", 7: "X"},
    "GE4": {0: "AB", 1: "AB", 2: "AB", 3: "AB", 4: "C", 5: "C", 6: "X", 7: "X"},
    "GE5": {0: "AC", 1: "AC", 2: "B", 3: "B", 4: "AC", 5: "AC", 6: "X", 7: "X"},
    "GE6": {0: "A", 1: "A", 2: "BC", 3: "BC", 4: "BC", 5: "BC", 6: "X", 7: "X"},
    "GE7": {0: "R", 1: "R", 2: "R", 3: "R", 4: "R", 5: "R", 6: "X", 7: "X"},
}
BENZENE_FRAGMENT_MAPS = {
    "G": None,
    "GL": {0: "A", 1: "A", 2: "B", 3: "B", 4: "C", 5: "C"},
    "GE1": {0: "A", 1: "A", 2: "BC", 3: "BC", 4: "BC", 5: "BC"},
}


def _configure(mean_field: Any, template: Any) -> Any:
    mean_field.xc = template.xc
    mean_field.grids.level = template.grids.level
    mean_field.conv_tol = template.conv_tol
    mean_field.max_cycle = template.max_cycle
    mean_field.max_memory = template.max_memory
    mean_field.diis_start_cycle = 2
    mean_field.diis_space = 8
    mean_field.damp = 0.20
    mean_field.verbose = 0
    return mean_field


def _atoms_from_molecule(molecule: Any) -> list[list[Any]]:
    coordinates = np.asarray(molecule.atom_coords(unit="Angstrom"), dtype=float)
    return [
        [molecule.atom_symbol(index), *[float(value) for value in coordinates[index]]]
        for index in range(molecule.natm)
    ]


def _geometry_summary(molecule: Any, system: str) -> dict[str, Any]:
    coordinates = np.asarray(molecule.atom_coords(unit="Angstrom"), dtype=float)
    ring = coordinates[:6]
    summary: dict[str, Any] = {
        "maximum_absolute_z_angstrom": float(np.max(np.abs(coordinates[:, 2]))),
        "ring_bonds_angstrom": [
            float(np.linalg.norm(ring[(index + 1) % 6] - ring[index]))
            for index in range(6)
        ],
    }
    if system == "cyanobenzene":
        summary["C1_C7_angstrom"] = float(np.linalg.norm(coordinates[6] - coordinates[0]))
        summary["C7_N8_angstrom"] = float(np.linalg.norm(coordinates[7] - coordinates[6]))
        summary["CH_angstrom"] = [
            float(np.linalg.norm(coordinates[8 + offset] - coordinates[1 + offset]))
            for offset in range(5)
        ]
    else:
        summary["CH_angstrom"] = [
            float(np.linalg.norm(coordinates[6 + index] - coordinates[index]))
            for index in range(6)
        ]
    return summary


def _prepare_cyanobenzene(state: str) -> tuple[dict[str, Any], list[list[Any]], dict[int, str] | None, np.ndarray]:
    protocol = yaml.safe_load(CYANO_PROTOCOL.read_text(encoding="utf-8"))
    options = protocol["geometry"]
    atoms, _ = cyanobenzene_atoms(options["states"][state], options)
    g_atoms, _ = cyanobenzene_atoms(options["states"]["G"], options)
    g = cyanobenzene_ordinary_state(g_atoms, protocol)
    if not g["converged"]:
        raise RuntimeError("cyanobenzene G state failed before optimization")
    initial_density = np.asarray(g["density"], dtype=float)
    if state in {"GE1", "GE2", "GE3"}:
        gl_atoms, _ = cyanobenzene_atoms(options["states"]["GL_I"], options)
        gl = cyanobenzene_conditional_state(
            gl_atoms,
            CYANO_FRAGMENT_MAPS["GL_I"],
            initial_density,
            protocol,
            mask_one_electron_matrix=False,
        )
        if not gl["converged"]:
            raise RuntimeError("cyanobenzene GL_I seed failed before optimization")
        initial_density = np.asarray(gl["density"], dtype=float)
    elif state in {"GE4", "GE5", "GE6", "GE7"}:
        gl_atoms, _ = cyanobenzene_atoms(options["states"]["GL_II"], options)
        gl = cyanobenzene_conditional_state(
            gl_atoms,
            CYANO_FRAGMENT_MAPS["GL_II"],
            initial_density,
            protocol,
            mask_one_electron_matrix=False,
        )
        if not gl["converged"]:
            raise RuntimeError("cyanobenzene GL_II seed failed before optimization")
        initial_density = np.asarray(gl["density"], dtype=float)
    return protocol, atoms, CYANO_FRAGMENT_MAPS[state], initial_density


def _prepare_benzene(state: str) -> tuple[dict[str, Any], list[list[Any]], dict[int, str] | None, np.ndarray]:
    protocol = yaml.safe_load(BENZENE_PROTOCOL.read_text(encoding="utf-8"))
    geometry = protocol["geometry"]
    g_atoms = regular_benzene(
        float(geometry["G"]["regular_CC_angstrom"]),
        float(geometry["G"]["common_CH_angstrom"]),
    )
    if state == "G":
        atoms = g_atoms
    elif state == "GL":
        atoms, _ = chain_ring(
            geometry["GL"]["chain_CC_angstrom"],
            geometry["GL"]["chain_angles_degrees"],
            geometry["GL"]["CH_angstrom"],
        )
    else:
        atoms, _ = chain_ring(
            geometry["GE1"]["chain_CC_angstrom"],
            geometry["GE1"]["chain_angles_degrees"],
            geometry["GE1"]["CH_angstrom"],
        )
    g = benzene_ordinary_state(g_atoms, protocol)
    if not g["converged"]:
        raise RuntimeError("benzene G state failed before optimization")
    initial_density = np.asarray(g["density"], dtype=float)
    if state == "GE1":
        gl_atoms, _ = chain_ring(
            geometry["GL"]["chain_CC_angstrom"],
            geometry["GL"]["chain_angles_degrees"],
            geometry["GL"]["CH_angstrom"],
        )
        gl_molecule = build_benzene_molecule(gl_atoms, protocol)
        gl_descriptors = classify_planar_pyscf_aos(gl_molecule, BENZENE_FRAGMENT_MAPS["GL"])
        gl_mean_field = _configure(
            Source2007ConditionalRKS.build(gl_molecule, gl_descriptors),
            build_benzene_mean_field(gl_molecule, protocol),
        )
        gl_mean_field.kernel(dm0=initial_density)
        if not gl_mean_field.converged:
            raise RuntimeError("benzene GL seed failed before optimization")
        initial_density = np.asarray(gl_mean_field.make_rdm1(), dtype=float)
    return protocol, atoms, BENZENE_FRAGMENT_MAPS[state], initial_density


def run_one(system: str, state: str, maxsteps: int) -> dict[str, Any]:
    from pyscf.geomopt import geometric_solver

    if system == "cyanobenzene":
        protocol, atoms, fragment_map, initial_density = _prepare_cyanobenzene(state)
        build_molecule = build_cyanobenzene_molecule
        build_template = build_cyanobenzene_mean_field
    else:
        protocol, atoms, fragment_map, initial_density = _prepare_benzene(state)
        build_molecule = build_benzene_molecule
        build_template = build_benzene_mean_field

    molecule = build_molecule(atoms, protocol)
    if fragment_map is None:
        mean_field = build_template(molecule, protocol)
        mean_field.verbose = 0
    else:
        descriptors = classify_planar_pyscf_aos(molecule, fragment_map)
        mean_field = _configure(
            Source2007ConditionalRKS.build(molecule, descriptors),
            build_template(molecule, protocol),
        )
    initial_energy = float(mean_field.kernel(dm0=initial_density))
    if not mean_field.converged:
        raise RuntimeError(f"{system} {state} initial conditional SCF did not converge")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    progress_path = OUTPUT_DIR / f"{system}_{state}_progress.json"
    trajectory: list[dict[str, Any]] = []

    def callback(environment: dict[str, Any]) -> None:
        mol = environment["mol"]
        gradients = np.asarray(environment["gradients"], dtype=float)
        item = {
            "cycle": int(environment["self"].cycle),
            "energy_hartree": float(environment["energy"]),
            "gradient_rms_hartree_per_bohr": float(np.sqrt(np.mean(gradients * gradients))),
            "gradient_max_hartree_per_bohr": float(np.max(np.linalg.norm(gradients, axis=1))),
            "maximum_absolute_z_angstrom": float(
                np.max(np.abs(np.asarray(mol.atom_coords(unit="Angstrom"))[:, 2]))
            ),
        }
        trajectory.append(item)
        write_json(
            progress_path,
            {
                "system": system,
                "state": state,
                "hard_constraint": "all_atom_z_equals_zero",
                "trajectory": trajectory,
            },
        )
        print(json.dumps(item, ensure_ascii=False), flush=True)

    constraints_path = CYANO_CONSTRAINTS if system == "cyanobenzene" else BENZENE_CONSTRAINTS
    expected_constraint = f"$freeze\nz 1-{molecule.natm}\n"
    if constraints_path.read_text(encoding="utf-8") != expected_constraint:
        raise RuntimeError(f"planar constraint file mismatch: {constraints_path}")
    converged, optimized_molecule = geometric_solver.kernel(
        mean_field,
        constraints=str(constraints_path),
        callback=callback,
        maxsteps=maxsteps,
        convergence_energy=1.0e-6,
        convergence_grms=3.0e-4,
        convergence_gmax=4.5e-4,
        convergence_drms=1.2e-3,
        convergence_dmax=1.8e-3,
    )

    if fragment_map is None:
        final_mean_field = build_template(optimized_molecule, protocol)
        final_mean_field.verbose = 0
    else:
        final_descriptors = classify_planar_pyscf_aos(optimized_molecule, fragment_map)
        final_mean_field = _configure(
            Source2007ConditionalRKS.build(optimized_molecule, final_descriptors),
            build_template(optimized_molecule, protocol),
        )
    final_energy = float(final_mean_field.kernel())
    final_gradient = np.asarray(final_mean_field.nuc_grad_method().kernel(), dtype=float)
    record = {
        "schema_version": 1,
        "protocol_role": "P11-B_source_2007_restricted_geometry_recalculation",
        "system": system,
        "state": state,
        "method": "B3LYP/6-31G(d)",
        "conditional_semantics": (
            "ordinary_RKS" if fragment_map is None
            else "interfragment_pi_Fock_and_overlap_zeroed_each_SCF_iteration"
        ),
        "one_electron_matrix_masked": False,
        "geometry_constraint": {
            "type": "hard_cartesian_freeze",
            "expression": f"z 1-{optimized_molecule.natm}",
            "plane": "xy",
        },
        "optimizer": "geomeTRIC_with_analytic_conditional_RKS_gradient",
        "optimizer_converged": bool(converged),
        "initial_energy_hartree": initial_energy,
        "final_energy_hartree": final_energy,
        "energy_lowering_hartree": final_energy - initial_energy,
        "final_scf_converged": bool(final_mean_field.converged),
        "final_gradient_rms_hartree_per_bohr": float(np.sqrt(np.mean(final_gradient * final_gradient))),
        "final_gradient_max_hartree_per_bohr": float(np.max(np.linalg.norm(final_gradient, axis=1))),
        "final_maximum_absolute_z_gradient_hartree_per_bohr": float(np.max(np.abs(final_gradient[:, 2]))),
        "initial_atoms_angstrom": atoms,
        "optimized_atoms_angstrom": _atoms_from_molecule(optimized_molecule),
        "geometry": _geometry_summary(optimized_molecule, system),
        "trajectory": trajectory,
        "scientific_classification_allowed": False,
        "pass": bool(
            converged
            and final_mean_field.converged
            and _geometry_summary(optimized_molecule, system)["maximum_absolute_z_angstrom"] <= 1.0e-10
        ),
    }
    output_path = OUTPUT_DIR / f"{system}_{state}.json"
    write_json(output_path, record)
    report_path = REPORT_DIR / f"{system}_{state}.md"
    report_path.write_text(
        "\n".join(
            [
                f"# P11-B 2007全平面受限优化：{system} {state}",
                "",
                f"- 优化收敛：`{record['optimizer_converged']}`",
                f"- 初始能量：`{initial_energy:.12f} Eh`",
                f"- 最终能量：`{final_energy:.12f} Eh`",
                f"- 最大 |z|：`{record['geometry']['maximum_absolute_z_angstrom']:.3e} Å`",
                f"- 最终梯度RMS：`{record['final_gradient_rms_hartree_per_bohr']:.3e} Eh/Bohr`",
                f"- 状态门禁：`{'PASS' if record['pass'] else 'FAIL'}`",
                "",
                "本文件仅是单态优化结果；须全部八态完成后方可组装P11-B诱导项。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", choices=("benzene", "cyanobenzene"), required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--maxsteps", type=int, default=50)
    args = parser.parse_args()
    allowed = BENZENE_FRAGMENT_MAPS if args.system == "benzene" else CYANO_FRAGMENT_MAPS
    if args.state not in allowed:
        parser.error(f"state must be one of: {', '.join(allowed)}")
    record = run_one(args.system, args.state, args.maxsteps)
    print(
        json.dumps(
            {
                "system": args.system,
                "state": args.state,
                "pass": record["pass"],
                "final_energy_hartree": record["final_energy_hartree"],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0 if record["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
