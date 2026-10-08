"""Optimize one P12 source-2011 planar GL or GE conditional state.

This runner is state-specific and checkpointed.  It does not assemble CESE or
change the public P12 classification; those actions remain gated by R4/R5.
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

from ai4orgchem.qm.p09_ao_classification import classify_planar_pyscf_aos
from ai4orgchem.qm.p12_direct_source2011 import project_planar_localized_density
from ai4orgchem.qm.p12_source2011_rks import Source2011DirectConditionalRKS

try:
    from scripts.run_p12_planar_g_optimization import (
        atoms_from_molecule,
        geometry_summary,
        read_xyz,
        resolve_repo_path,
        write_json,
        write_xyz,
    )
except ModuleNotFoundError:
    from run_p12_planar_g_optimization import (
        atoms_from_molecule,
        geometry_summary,
        read_xyz,
        resolve_repo_path,
        write_json,
        write_xyz,
    )


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "configs/qm/p12_source2011_planar_cese_recalculation_v0.1.yaml"
SEED_MANIFEST = ROOT / "data/inputs/p12_source2011_planar_seeds_v0.1/manifest.json"
G_DIR = ROOT / "data/processed/p12_source2011_planar_g_optimized_v0.1"
OUTPUT_DIR = ROOT / "data/processed/p12_source2011_planar_source_states_v0.1"
REPORT_DIR = ROOT / "docs/reports/p12_source2011_planar_source_states_v0.1"


def build_molecule(atoms: list[list[Any]], basis: str, maximum_memory: int = 12000) -> Any:
    from pyscf import gto

    return gto.M(
        atom=atoms,
        basis=basis,
        charge=0,
        spin=0,
        unit="Angstrom",
        cart=False,
        symmetry=False,
        verbose=0,
        max_memory=maximum_memory,
    )


def fragment_map(n_carbon: int, pair: tuple[int, int] | None) -> dict[int, str]:
    groups = [f"DB{index + 1:02d}" for index in range(n_carbon // 2)]
    if pair is not None:
        left, right = pair
        if left == right or min(pair) < 0 or max(pair) >= len(groups):
            raise ValueError("GE pair indices must name two different pi groups")
        merged = f"GE{min(pair) + 1:02d}_{max(pair) + 1:02d}"
        groups[left] = merged
        groups[right] = merged
    mapping: dict[int, str] = {}
    for carbon_index in range(n_carbon):
        label = groups[carbon_index // 2]
        mapping[carbon_index] = label
        mapping[n_carbon + carbon_index] = label
    return mapping


def build_ordinary(molecule: Any, method: str, grid_level: int, tolerance: float) -> Any:
    from pyscf import dft

    mean_field = dft.RKS(molecule)
    mean_field.xc = method
    mean_field.grids.level = grid_level
    mean_field.conv_tol = tolerance
    mean_field.max_cycle = 150
    mean_field.max_memory = 12000
    mean_field.diis_space = 10
    mean_field.verbose = 0
    return mean_field


def build_conditional(
    molecule: Any,
    mapping: dict[int, str],
    method: str,
    grid_level: int,
    tolerance: float,
) -> tuple[Any, tuple[Any, ...]]:
    descriptors = classify_planar_pyscf_aos(molecule, mapping)
    mean_field = Source2011DirectConditionalRKS.build(molecule, descriptors)
    mean_field.xc = method
    mean_field.grids.level = grid_level
    mean_field.conv_tol = tolerance
    mean_field.max_cycle = 150
    mean_field.max_memory = 12000
    mean_field.diis_space = 10
    mean_field.diis_start_cycle = 1
    mean_field.verbose = 0
    return mean_field, descriptors


def converge_from_ordinary(
    molecule: Any,
    mapping: dict[int, str],
    method: str,
    grid_level: int,
    tolerance: float,
) -> tuple[Any, np.ndarray]:
    ordinary = build_ordinary(molecule, method, grid_level, tolerance)
    ordinary.kernel()
    if not ordinary.converged:
        raise RuntimeError("ordinary starting RKS did not converge")
    conditional, descriptors = build_conditional(
        molecule, mapping, method, grid_level, tolerance
    )
    initial_density = project_planar_localized_density(
        ordinary.make_rdm1(), descriptors
    )
    conditional.kernel(dm0=initial_density)
    if not conditional.converged:
        raise RuntimeError("source-2011 conditional RKS did not converge")
    return conditional, np.asarray(conditional.make_rdm1(), dtype=float)


def state_id(n_carbon: int, pair: tuple[int, int] | None) -> str:
    if pair is None:
        return f"N{n_carbon}_GL"
    return f"N{n_carbon}_GE_g{pair[0] + 1:02d}_g{pair[1] + 1:02d}"


def run_one(
    n_carbon: int,
    pair: tuple[int, int] | None,
    maxsteps: int,
    resume: bool,
    force: bool,
    protocol_path: str | Path = PROTOCOL,
    n16_execute: bool = False,
) -> dict[str, Any]:
    protocol_path = resolve_repo_path(protocol_path)
    protocol, n16_contract = load_protocol(protocol_path)
    require_authorized_state(protocol, n16_contract, n_carbon, "GL" if pair is None else "GE", pair)
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
    g_dir = resolve_repo_path(
        output_contract.get("ordinary_g_directory", G_DIR)
    )
    output_dir = resolve_repo_path(
        output_contract.get("conditional_state_directory", OUTPUT_DIR)
    )
    report_dir = resolve_repo_path(
        output_contract.get("conditional_state_report_directory", REPORT_DIR)
    )
    manifest = json.loads(seed_manifest.read_text(encoding="utf-8"))
    record = next(item for item in manifest["records"] if int(item["N"]) == n_carbon)
    g_result = json.loads((g_dir / f"N{n_carbon}_G.json").read_text(encoding="utf-8"))
    if not g_result.get("pass"):
        raise RuntimeError(f"N={n_carbon} R2 G state has not passed")
    if n16_contract is not None and (
        g_result.get("protocol_id") != protocol["protocol_id"]
        or g_result.get("N") != 16
        or g_result.get("configuration") != "[16]-5555"
        or g_result.get("method") != "B3LYPG/6-311g(2df,p)"
    ):
        raise RuntimeError("N16 G state does not belong to the same-basis N16 contract")

    identifier = state_id(n_carbon, pair)
    result_path = output_dir / f"{identifier}.json"
    if result_path.exists() and not force:
        existing = json.loads(result_path.read_text(encoding="utf-8"))
        if existing.get("pass"):
            if existing.get("protocol_id") != protocol["protocol_id"] or existing.get("N") != n_carbon or existing.get("pair_zero_based") != (list(pair) if pair is not None else None):
                raise RuntimeError("existing conditional result belongs to another protocol/system/pair")
            print(json.dumps({"status": "already_complete", "path": str(result_path)}))
            return existing

    latest_xyz = output_dir / f"{identifier}_latest.xyz"
    g_xyz = ROOT / g_result["optimized_xyz"]
    start_path = latest_xyz if resume and latest_xyz.exists() else g_xyz
    atoms = read_xyz(start_path)
    mapping = fragment_map(n_carbon, pair)
    geometry_contract = protocol["geometry_contract"]
    energy_contract = protocol["energy_contract"]
    molecule = build_molecule(atoms, geometry_contract["basis"])
    conditional, _density = converge_from_ordinary(
        molecule,
        mapping,
        geometry_contract["method"],
        int(energy_contract["grid_level"]),
        float(energy_contract["scf_tolerance_hartree"]),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    progress_path = output_dir / f"{identifier}_progress.json"
    trajectory: list[dict[str, Any]] = []

    def callback(environment: dict[str, Any]) -> None:
        current_molecule = environment["mol"]
        gradients = np.asarray(environment["gradients"], dtype=float)
        write_xyz(
            latest_xyz,
            atoms_from_molecule(current_molecule),
            f"{identifier} P12 source-2011 latest planar checkpoint",
        )
        item = {
            "cycle": int(environment["self"].cycle),
            "energy_hartree": float(environment["energy"]),
            "gradient_rms_hartree_per_bohr": float(np.sqrt(np.mean(gradients * gradients))),
            "gradient_max_hartree_per_bohr": float(
                np.max(np.linalg.norm(gradients, axis=1))
            ),
            "maximum_absolute_z_angstrom": float(
                np.max(
                    np.abs(
                        np.asarray(current_molecule.atom_coords(unit="Angstrom"))[:, 2]
                    )
                )
            ),
        }
        trajectory.append(item)
        write_json(
            progress_path,
            {
                "state_id": identifier,
                "N": n_carbon,
                "configuration": record["configuration"],
                "state": "GL" if pair is None else "GE",
                "pair_zero_based": list(pair) if pair is not None else None,
                "start_path": start_path.relative_to(ROOT).as_posix(),
                "hard_constraint": "all_atom_z_equals_zero",
                "trajectory": trajectory,
            },
        )
        print(json.dumps(item), flush=True)

    constraints_path = ROOT / record["constraint_path"]
    converged, optimized_molecule = geometric_solver.kernel(
        conditional,
        constraints=str(constraints_path),
        callback=callback,
        maxsteps=maxsteps,
        convergence_energy=1.0e-6,
        convergence_grms=3.0e-4,
        convergence_gmax=4.5e-4,
        convergence_drms=1.2e-3,
        convergence_dmax=1.8e-3,
    )

    final_geometry_mf, geometry_density = converge_from_ordinary(
        optimized_molecule,
        mapping,
        geometry_contract["method"],
        int(energy_contract["grid_level"]),
        float(energy_contract["scf_tolerance_hartree"]),
    )
    final_gradient = np.asarray(final_geometry_mf.nuc_grad_method().kernel(), dtype=float)
    final_xyz = output_dir / f"{identifier}_optimized.xyz"
    write_xyz(final_xyz, atoms_from_molecule(optimized_molecule), f"{identifier} optimized")

    energy_molecule = build_molecule(
        atoms_from_molecule(optimized_molecule), energy_contract["basis"]
    )
    final_energy_mf, energy_density = converge_from_ordinary(
        energy_molecule,
        mapping,
        energy_contract["method"],
        int(energy_contract["grid_level"]),
        float(energy_contract["scf_tolerance_hartree"]),
    )
    geometry = geometry_summary(
        optimized_molecule,
        n_carbon,
        record["inner_hydrogen_carbon_indices_zero_based"],
    )
    density_path = output_dir / f"{identifier}_densities.npz"
    np.savez_compressed(
        density_path,
        geometry_basis_density=geometry_density,
        energy_basis_density=energy_density,
    )
    cyclic_distance = None
    if pair is not None:
        group_count = n_carbon // 2
        difference = abs(pair[1] - pair[0])
        cyclic_distance = min(difference, group_count - difference)
    payload = {
        "schema_version": 1,
        "protocol_id": protocol["protocol_id"],
        "protocol_path": protocol_path.relative_to(ROOT).as_posix(),
        "gate": "P12-R3/R4 source-2011 planar state optimization",
        "state_id": identifier,
        "N": n_carbon,
        "configuration": record["configuration"],
        "state": "GL" if pair is None else "GE",
        "pair_zero_based": list(pair) if pair is not None else None,
        "pair_one_based": [value + 1 for value in pair] if pair is not None else None,
        "pair_cyclic_group_distance": cyclic_distance,
        "pair_class": (
            None if pair is None else "adjacent" if cyclic_distance == 1 else "nonadjacent"
        ),
        "geometry_method": f"{geometry_contract['method']}/{geometry_contract['basis']}",
        "energy_method": f"{energy_contract['method']}/{energy_contract['basis']}",
        "source_operator": "2011_h_S_F_masks_plus_complete_15_class_exchange_rule",
        "optimizer": "geomeTRIC_with_validated_source2011_analytic_gradient",
        "optimizer_converged": bool(converged),
        "geometry_scf_converged": bool(final_geometry_mf.converged),
        "energy_scf_converged": bool(final_energy_mf.converged),
        "final_geometry_energy_hartree": float(final_geometry_mf.e_tot),
        "final_energy_hartree": float(final_energy_mf.e_tot),
        "final_in_plane_gradient_rms_hartree_per_bohr": float(
            np.sqrt(np.mean(final_gradient[:, :2] * final_gradient[:, :2]))
        ),
        "maximum_absolute_z_gradient_hartree_per_bohr": float(
            np.max(np.abs(final_gradient[:, 2]))
        ),
        "geometry": geometry,
        "optimized_xyz": final_xyz.relative_to(ROOT).as_posix(),
        "density_archive": density_path.relative_to(ROOT).as_posix(),
        "start_path": start_path.relative_to(ROOT).as_posix(),
        "start_sha256": hashlib.sha256(start_path.read_bytes()).hexdigest(),
        "trajectory": trajectory,
        "density_fitting_used": False,
        "source_program_code_used": False,
        "fit_to_published_values": False,
        "CESE_assembled": False,
        "classification_change_allowed": False,
    }
    payload["pass"] = bool(
        converged
        and final_geometry_mf.converged
        and final_energy_mf.converged
        and geometry["maximum_absolute_z_angstrom"] <= 1.0e-8
        and geometry["configuration_identity_preserved"]
    )
    write_json(result_path, payload)
    (report_dir / f"{identifier}.md").write_text(
        "\n".join(
            [
                f"# {identifier}: P12 source-2011 planar state",
                "",
                f"- Gate: `{'PASS' if payload['pass'] else 'FAIL'}`",
                f"- Configuration: `{record['configuration']}`",
                f"- State: `{'GL' if pair is None else 'GE'}`",
                f"- Final energy: `{payload['final_energy_hartree']:.12f} Eh`",
                f"- Maximum |z|: `{geometry['maximum_absolute_z_angstrom']:.3e} A`",
                "",
                "This state result does not assemble CESE or change the public P12 classification.",
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
    parser.add_argument("--state", choices=("GL", "GE"), required=True)
    parser.add_argument("--pair", nargs=2, type=int, metavar=("GROUP_A", "GROUP_B"))
    parser.add_argument("--maxsteps", type=int, default=80)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--protocol", default=str(PROTOCOL))
    parser.add_argument("--n16-execute", action="store_true")
    args = parser.parse_args()
    if args.state == "GL" and args.pair is not None:
        parser.error("--pair is not allowed for GL")
    if args.state == "GE" and args.pair is None:
        parser.error("--pair is required for GE")
    pair = tuple(args.pair) if args.pair is not None else None
    result = run_one(
        args.N, pair, args.maxsteps, args.resume, args.force, args.protocol, args.n16_execute
    )
    return 0 if result.get("pass") else 2


if __name__ == "__main__":
    raise SystemExit(main())
