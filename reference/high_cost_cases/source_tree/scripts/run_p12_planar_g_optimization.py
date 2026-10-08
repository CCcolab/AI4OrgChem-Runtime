"""Optimize one ordinary planar [N]annulene G state for P12-R2.

This runner performs only the source geometry-level ordinary ground-state
optimization.  It does not construct GL/GE states and cannot change the P12
classification by itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import yaml

try:
    from scripts.p12_n16_execution_contract import load_protocol, require_authorized_state, sha256
except ModuleNotFoundError:
    from p12_n16_execution_contract import load_protocol, require_authorized_state, sha256

try:
    from scripts.prepare_p12_planar_configuration_seeds import point_in_polygon
except ModuleNotFoundError:  # direct ``python scripts/...`` execution
    from prepare_p12_planar_configuration_seeds import point_in_polygon


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "configs/qm/p12_source2011_planar_cese_recalculation_v0.1.yaml"
SEED_MANIFEST = ROOT / "data/inputs/p12_source2011_planar_seeds_v0.1/manifest.json"
OUTPUT_DIR = ROOT / "data/processed/p12_source2011_planar_g_optimized_v0.1"
REPORT_DIR = ROOT / "docs/reports/p12_source2011_planar_g_optimized_v0.1"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_xyz(path: Path) -> list[list[Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    count = int(lines[0])
    atoms = []
    for line in lines[2 : 2 + count]:
        fields = line.split()
        atoms.append([fields[0], *[float(value) for value in fields[1:4]]])
    if len(atoms) != count:
        raise ValueError(f"incomplete XYZ file: {path}")
    return atoms


def atoms_from_molecule(molecule: Any) -> list[list[Any]]:
    coordinates = np.asarray(molecule.atom_coords(unit="Angstrom"), dtype=float)
    return [
        [molecule.atom_symbol(index), *[float(value) for value in coordinates[index]]]
        for index in range(molecule.natm)
    ]


def write_xyz(path: Path, atoms: list[list[Any]], comment: str) -> None:
    lines = [str(len(atoms)), comment]
    for element, x_value, y_value, z_value in atoms:
        lines.append(f"{element:2s} {x_value: .12f} {y_value: .12f} {z_value: .12f}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_molecule(atoms: list[list[Any]], protocol: dict[str, Any]) -> Any:
    from pyscf import gto

    contract = protocol["geometry_contract"]
    return gto.M(
        atom=atoms,
        basis=contract["basis"],
        charge=int(contract["charge"]),
        spin=int(contract["multiplicity"]) - 1,
        unit="Angstrom",
        cart=False,
        symmetry=False,
        verbose=0,
        max_memory=12000,
    )


def build_mean_field(molecule: Any, protocol: dict[str, Any]) -> Any:
    from pyscf import dft

    geometry = protocol["geometry_contract"]
    energy = protocol["energy_contract"]
    mean_field = dft.RKS(molecule)
    mean_field.xc = geometry["method"]
    mean_field.grids.level = int(energy["grid_level"])
    mean_field.conv_tol = float(energy["scf_tolerance_hartree"])
    mean_field.max_cycle = int(energy["maximum_scf_cycles"])
    mean_field.max_memory = 12000
    mean_field.diis_space = 10
    mean_field.diis_start_cycle = 1
    mean_field.verbose = 0
    return mean_field


def geometry_summary(molecule: Any, n_carbon: int, expected_inner: list[int]) -> dict[str, Any]:
    coordinates = np.asarray(molecule.atom_coords(unit="Angstrom"), dtype=float)
    carbons = coordinates[:n_carbon, :2]
    hydrogens = coordinates[n_carbon:, :2]
    observed_inner = [
        index for index, hydrogen in enumerate(hydrogens) if point_in_polygon(hydrogen, carbons)
    ]
    ring_bonds = [
        float(np.linalg.norm(coordinates[(index + 1) % n_carbon] - coordinates[index]))
        for index in range(n_carbon)
    ]
    ccc_angles = []
    for index in range(n_carbon):
        left = coordinates[(index - 1) % n_carbon] - coordinates[index]
        right = coordinates[(index + 1) % n_carbon] - coordinates[index]
        cosine = float(np.dot(left, right) / (np.linalg.norm(left) * np.linalg.norm(right)))
        ccc_angles.append(float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0)))))
    return {
        "maximum_absolute_z_angstrom": float(np.max(np.abs(coordinates[:, 2]))),
        "observed_inner_hydrogen_carbon_indices_zero_based": observed_inner,
        "expected_inner_hydrogen_carbon_indices_zero_based": expected_inner,
        "configuration_identity_preserved": observed_inner == expected_inner,
        "ring_bonds_angstrom": ring_bonds,
        "minimum_ring_bond_angstrom": min(ring_bonds),
        "maximum_ring_bond_angstrom": max(ring_bonds),
        "CCC_angles_degree": ccc_angles,
        "minimum_CCC_angle_degree": min(ccc_angles),
        "maximum_CCC_angle_degree": max(ccc_angles),
    }


def resolve_repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def run_one(
    n_carbon: int,
    maxsteps: int,
    resume: bool,
    force: bool,
    protocol_path: str | Path = PROTOCOL,
    n16_execute: bool = False,
) -> dict[str, Any]:
    protocol_path = resolve_repo_path(protocol_path)
    protocol, n16_contract = load_protocol(protocol_path)
    require_authorized_state(protocol, n16_contract, n_carbon, "G", None)
    if n16_contract is not None and (
        not n16_execute or force or not 1 <= maxsteps <= 80
        or os.environ.get("AI4ORGCHEM_N16_QUEUE_CONTRACT_SHA256") != sha256(protocol_path)
    ):
        raise ValueError("N16 requires the bounded queue, explicit --n16-execute, no --force, and 1..80 maxsteps")
    from pyscf.geomopt import geometric_solver
    output_contract = protocol.get("output_contract", {})
    seed_manifest = resolve_repo_path(
        output_contract.get("seed_manifest", SEED_MANIFEST)
    )
    output_dir = resolve_repo_path(
        output_contract.get("ordinary_g_directory", OUTPUT_DIR)
    )
    report_dir = resolve_repo_path(
        output_contract.get("ordinary_g_report_directory", REPORT_DIR)
    )
    manifest = json.loads(seed_manifest.read_text(encoding="utf-8"))
    record = next(item for item in manifest["records"] if int(item["N"]) == n_carbon)
    result_path = output_dir / f"N{n_carbon}_G.json"
    if result_path.exists() and not force:
        existing = json.loads(result_path.read_text(encoding="utf-8"))
        if existing.get("pass"):
            if existing.get("protocol_id") != protocol["protocol_id"] or existing.get("N") != n_carbon:
                raise RuntimeError("existing G result belongs to another protocol/system")
            print(json.dumps({"status": "already_complete", "path": str(result_path)}, indent=2))
            return existing

    latest_xyz = output_dir / f"N{n_carbon}_G_latest.xyz"
    seed_path = ROOT / record["path"]
    start_path = latest_xyz if resume and latest_xyz.exists() else seed_path
    atoms = read_xyz(start_path)
    molecule = build_molecule(atoms, protocol)
    mean_field = build_mean_field(molecule, protocol)
    initial_energy = float(mean_field.kernel())
    if not mean_field.converged:
        raise RuntimeError(f"N={n_carbon} initial ordinary RKS did not converge")

    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    progress_path = output_dir / f"N{n_carbon}_G_progress.json"
    trajectory: list[dict[str, Any]] = []

    def callback(environment: dict[str, Any]) -> None:
        current_molecule = environment["mol"]
        gradients = np.asarray(environment["gradients"], dtype=float)
        current_atoms = atoms_from_molecule(current_molecule)
        write_xyz(latest_xyz, current_atoms, f"N={n_carbon} P12-R2 latest planar G checkpoint")
        item = {
            "cycle": int(environment["self"].cycle),
            "energy_hartree": float(environment["energy"]),
            "gradient_rms_hartree_per_bohr": float(np.sqrt(np.mean(gradients * gradients))),
            "gradient_max_hartree_per_bohr": float(np.max(np.linalg.norm(gradients, axis=1))),
            "maximum_absolute_z_angstrom": float(
                np.max(np.abs(np.asarray(current_molecule.atom_coords(unit="Angstrom"))[:, 2]))
            ),
        }
        trajectory.append(item)
        write_json(
            progress_path,
            {
                "N": n_carbon,
                "configuration": record["configuration"],
                "start_path": start_path.relative_to(ROOT).as_posix(),
                "hard_constraint": "all_atom_z_equals_zero",
                "trajectory": trajectory,
            },
        )
        print(json.dumps(item), flush=True)

    constraints_path = ROOT / record["constraint_path"]
    expected_constraint = f"$freeze\nz 1-{2 * n_carbon}\n"
    if constraints_path.read_text(encoding="utf-8") != expected_constraint:
        raise RuntimeError(f"planar constraint mismatch: {constraints_path}")
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

    final_mean_field = build_mean_field(optimized_molecule, protocol)
    final_energy = float(final_mean_field.kernel())
    final_gradient = np.asarray(final_mean_field.nuc_grad_method().kernel(), dtype=float)
    final_atoms = atoms_from_molecule(optimized_molecule)
    final_xyz = output_dir / f"N{n_carbon}_G_optimized.xyz"
    write_xyz(final_xyz, final_atoms, f"N={n_carbon} P12-R2 planar G optimized")
    geometry = geometry_summary(optimized_molecule, n_carbon, record["inner_hydrogen_carbon_indices_zero_based"])
    payload = {
        "schema_version": 1,
        "protocol_id": protocol["protocol_id"],
        "protocol_path": protocol_path.relative_to(ROOT).as_posix(),
        "gate": "P12-R2 ordinary planar G optimization",
        "N": n_carbon,
        "configuration": record["configuration"],
        "method": f"{protocol['geometry_contract']['method']}/{protocol['geometry_contract']['basis']}",
        "density_fitting": False,
        "spherical_basis": True,
        "optimizer": "geomeTRIC_with_PySCF_analytic_RKS_gradient",
        "geometry_constraint": f"all atomic z coordinates frozen, atoms 1-{2 * n_carbon}",
        "start_path": start_path.relative_to(ROOT).as_posix(),
        "start_sha256": hashlib.sha256(start_path.read_bytes()).hexdigest(),
        "optimizer_converged": bool(converged),
        "initial_scf_converged": True,
        "final_scf_converged": bool(final_mean_field.converged),
        "initial_energy_hartree": initial_energy,
        "final_energy_hartree": final_energy,
        "energy_lowering_hartree": final_energy - initial_energy,
        "final_gradient_rms_hartree_per_bohr_all_components": float(
            np.sqrt(np.mean(final_gradient * final_gradient))
        ),
        "final_in_plane_gradient_rms_hartree_per_bohr": float(
            np.sqrt(np.mean(final_gradient[:, :2] * final_gradient[:, :2]))
        ),
        "final_maximum_absolute_z_gradient_hartree_per_bohr": float(
            np.max(np.abs(final_gradient[:, 2]))
        ),
        "geometry": geometry,
        "optimized_xyz": final_xyz.relative_to(ROOT).as_posix(),
        "trajectory": trajectory,
        "source_program_code_used": False,
        "scientific_classification_allowed": False,
    }
    payload["pass"] = bool(
        converged
        and final_mean_field.converged
        and geometry["maximum_absolute_z_angstrom"] <= 1.0e-8
        and geometry["configuration_identity_preserved"]
    )
    write_json(result_path, payload)
    report_path = report_dir / f"N{n_carbon}_G.md"
    report_path.write_text(
        "\n".join(
            [
                f"# P12-R2：{record['configuration']} 全平面普通态优化",
                "",
                f"- 门禁：`{'PASS' if payload['pass'] else 'FAIL'}`",
                f"- 方法：`{payload['method']}`，无密度拟合",
                f"- 优化收敛：`{payload['optimizer_converged']}`",
                f"- 最终能量：`{final_energy:.12f} Eh`",
                f"- 最大 |z|：`{geometry['maximum_absolute_z_angstrom']:.3e} Å`",
                f"- 内氢构型保持：`{geometry['configuration_identity_preserved']}`",
                "",
                "本结果仅完成普通G态几何门禁，不生成CESE，也不允许改变P12分类。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps({"pass": payload["pass"], "result": str(result_path)}, indent=2))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--N", type=int, choices=(12, 14, 16, 18, 20, 22), required=True)
    parser.add_argument("--maxsteps", type=int, default=80)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--protocol", default=str(PROTOCOL))
    parser.add_argument("--n16-execute", action="store_true")
    args = parser.parse_args()
    result = run_one(args.N, args.maxsteps, args.resume, args.force, args.protocol, args.n16_execute)
    return 0 if result.get("pass") else 2


if __name__ == "__main__":
    raise SystemExit(main())
