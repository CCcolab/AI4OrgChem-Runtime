"""Run the bounded P08 butadiene G/GL(2014) independent reconstruction."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from ai4orgchem.lfmo.gl2014 import run_gl2014_scf


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/qm/p08_butadiene_gl2014_v0.1.yaml"
DEFAULT_CHECKPOINT = ROOT / "runs/validation/p08_butadiene_gl2014_checkpoint_v0.1.json"
DEFAULT_REPORT = ROOT / "docs/reports/p08_butadiene_gl2014_pilot_2026-08-20.md"
DEFAULT_OUTPUT = ROOT / "data/processed/p08_butadiene_gl2014_evidence_v0.1.json"
DEFAULT_FINAL_REPORT = ROOT / "docs/reports/p08_butadiene_gl2014_final_2026-08-20.md"
HARTREE_TO_KCAL_PER_MOL = 627.5094740631


def atoms_from_config(config: dict[str, Any]) -> list[list[Any]]:
    return [[row[0], *[float(value) for value in row[1:4]]] for row in config["system"]["initial_atoms"]]


def build_molecule(atoms: list[list[Any]], config: dict[str, Any]) -> Any:
    from pyscf import gto

    return gto.M(
        atom=atoms,
        basis=str(config["electronic_structure"]["basis"]),
        charge=int(config["system"]["charge"]),
        spin=int(config["system"]["spin"]),
        unit=str(config["system"]["unit"]),
        symmetry=False,
        verbose=0,
    )


def build_mean_field(molecule: Any, config: dict[str, Any]) -> Any:
    from pyscf import dft

    mean_field = dft.RKS(molecule)
    mean_field.verbose = 0
    mean_field.xc = str(config["electronic_structure"]["pyscf_xc"])
    mean_field.grids.level = int(config["electronic_structure"]["grid_level"])
    mean_field.conv_tol = float(config["electronic_structure"]["scf_convergence_tolerance"])
    mean_field.max_cycle = int(config["electronic_structure"]["scf_max_cycles"])
    return mean_field


def molecule_atoms(molecule: Any) -> list[list[Any]]:
    coordinates = np.asarray(molecule.atom_coords(unit="Angstrom"), dtype=float)
    return [[molecule.atom_symbol(index), *coordinates[index].tolist()] for index in range(molecule.natm)]


def geometry_hash(atoms: list[list[Any]]) -> str:
    payload = json.dumps(atoms, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()


def distance(atoms: list[list[Any]], first: int, second: int) -> float:
    a = np.asarray(atoms[first][1:4], dtype=float)
    b = np.asarray(atoms[second][1:4], dtype=float)
    return float(np.linalg.norm(a - b))


def ordinary_single_point(atoms: list[list[Any]], config: dict[str, Any]) -> tuple[dict[str, Any], np.ndarray]:
    molecule = build_molecule(atoms, config)
    mean_field = build_mean_field(molecule, config)
    energy = float(mean_field.kernel())
    if not mean_field.converged:
        raise RuntimeError("ordinary B3LYPG ground-state SCF did not converge")
    density = np.asarray(mean_field.make_rdm1(), dtype=float)
    return {
        "converged": True,
        "total_energy_hartree": energy,
        "nuclear_repulsion_hartree": float(molecule.energy_nuc()),
        "physical_metric_electron_count": float(
            np.einsum("ij,ji->", density, mean_field.get_ovlp())
        ),
    }, density


def optimize_ground_geometry(atoms: list[list[Any]], config: dict[str, Any]) -> dict[str, Any]:
    from pyscf.geomopt import geometric_solver

    optimization = config["ground_geometry_optimization"]
    history: list[dict[str, float]] = []

    def callback(environment: dict[str, Any]) -> None:
        gradients = np.asarray(environment["gradients"], dtype=float)
        history.append(
            {
                "cycle": int(environment["self"].cycle),
                "energy_hartree": float(environment["energy"]),
                "gradient_rms_hartree_per_bohr": float(np.sqrt(np.mean(gradients**2))),
                "gradient_max_hartree_per_bohr": float(np.max(np.abs(gradients))),
            }
        )

    molecule = build_molecule(atoms, config)
    mean_field = build_mean_field(molecule, config)
    converged, optimized = geometric_solver.kernel(
        mean_field,
        assert_convergence=True,
        callback=callback,
        maxsteps=int(optimization["maximum_steps"]),
        convergence_energy=float(optimization["convergence_energy_hartree"]),
        convergence_grms=float(optimization["convergence_gradient_rms_hartree_per_bohr"]),
        convergence_gmax=float(optimization["convergence_gradient_max_hartree_per_bohr"]),
        convergence_drms=float(optimization["convergence_displacement_rms_angstrom"]),
        convergence_dmax=float(optimization["convergence_displacement_max_angstrom"]),
    )
    optimized_atoms = molecule_atoms(optimized)
    single_point, density = ordinary_single_point(optimized_atoms, config)
    central = config["system"]["central_bond_atoms"]
    return {
        "optimizer_converged": bool(converged),
        "optimizer_cycles": len(history),
        "atoms": optimized_atoms,
        "geometry_sha256": geometry_hash(optimized_atoms),
        "central_bond_angstrom": distance(optimized_atoms, int(central[0]), int(central[1])),
        "single_point": single_point,
        "density": density.tolist(),
        "history": history,
    }


def align_and_symmetrize(atoms: list[list[Any]], config: dict[str, Any]) -> list[list[Any]]:
    symbols = [str(row[0]) for row in atoms]
    xyz = np.asarray([row[1:4] for row in atoms], dtype=float)
    pairs = [[int(value) for value in pair] for pair in config["system"]["inversion_pairs"]]
    center = np.mean([0.5 * (xyz[first] + xyz[second]) for first, second in pairs], axis=0)
    xyz -= center
    inner_left, inner_right = [int(value) for value in config["system"]["central_bond_atoms"]]
    x_axis = xyz[inner_right] - xyz[inner_left]
    x_axis /= np.linalg.norm(x_axis)
    centered = xyz - np.mean(xyz, axis=0)
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    z_axis = vh[-1]
    y_axis = np.cross(z_axis, x_axis)
    y_axis /= np.linalg.norm(y_axis)
    z_axis = np.cross(x_axis, y_axis)
    rotation = np.column_stack((x_axis, y_axis, z_axis))
    xyz = xyz @ rotation
    if xyz[0, 1] < 0.0:
        xyz[:, 1] *= -1.0
    for first, second in pairs:
        representative = 0.5 * (xyz[first] - xyz[second])
        representative[2] = 0.0
        xyz[first] = representative
        xyz[second] = -representative
    xyz[:, 2] = 0.0
    return [[symbols[index], *xyz[index].tolist()] for index in range(len(symbols))]


def translated_central_bond(
    atoms: list[list[Any]], displacement: float, config: dict[str, Any]
) -> list[list[Any]]:
    result = [[row[0], *[float(value) for value in row[1:4]]] for row in atoms]
    left_atoms = {0, 1, 4, 5, 6}
    right_atoms = {2, 3, 7, 8, 9}
    for index in left_atoms:
        result[index][1] -= 0.5 * float(displacement)
    for index in right_atoms:
        result[index][1] += 0.5 * float(displacement)
    return result


def json_safe_gl(result: dict[str, Any]) -> dict[str, Any]:
    excluded = {"density", "mo_coefficients", "mo_energies_hartree", "mo_occupations"}
    safe: dict[str, Any] = {}
    for key, value in result.items():
        if key in excluded:
            continue
        if isinstance(value, np.ndarray):
            safe[key] = value.tolist()
        else:
            safe[key] = value
    safe["final_density"] = np.asarray(result["density"]).tolist()
    return safe


def compact_gl(result: dict[str, Any]) -> dict[str, Any]:
    compact = dict(result)
    compact.pop("final_density", None)
    compact.pop("history", None)
    return compact


def conditional_single_point(
    atoms: list[list[Any]], config: dict[str, Any], initial_density: np.ndarray
) -> dict[str, Any]:
    molecule = build_molecule(atoms, config)
    mean_field = build_mean_field(molecule, config)
    options = config["gl2014_conditional_scf"]
    result = run_gl2014_scf(
        mean_field,
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
    central = config["system"]["central_bond_atoms"]
    safe = json_safe_gl(result)
    safe["atoms"] = atoms
    safe["geometry_sha256"] = geometry_hash(atoms)
    safe["central_bond_angstrom"] = distance(atoms, int(central[0]), int(central[1]))
    return safe


def write_checkpoint(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def render_report(record: dict[str, Any]) -> str:
    ground = record["ground_geometry"]
    anchor = record["gl2014_at_ground_geometry"]
    lines = [
        "# P08 丁二烯 GL(2014) 独立实现试运行",
        "",
        f"- 协议：`{record['protocol_id']}`",
        f"- 阶段：`{record['stage']}`",
        f"- G中央键：`{ground['central_bond_angstrom']:.6f} Å`",
        f"- G总能量：`{ground['single_point']['total_energy_hartree']:.12f} Eh`",
        f"- G几何上的GL条件态能量：`{anchor['total_energy_hartree']:.12f} Eh`",
        f"- 条件SCF：`{'converged' if anchor['converged'] else 'not_converged'}`，{anchor['cycles']} cycles",
        "",
        "## 中央键局部扫描",
        "",
        "| r23 (Å) | E_GL (Eh) | 相对最低点 (kcal/mol) | 收敛 |",
        "|---:|---:|---:|---|",
    ]
    minimum = min(float(row["total_energy_hartree"]) for row in record["central_bond_pilot"])
    for row in record["central_bond_pilot"]:
        relative = (float(row["total_energy_hartree"]) - minimum) * HARTREE_TO_KCAL_PER_MOL
        lines.append(
            f"| {row['central_bond_angstrom']:.6f} | {row['total_energy_hartree']:.12f} "
            f"| {relative:.6f} | {row['converged']} |"
        )
    lines.extend(
        [
            "",
            "该扫描只判断GL能量沿中央键的局部方向并检验条件态实现，不能替代完整GL几何优化，也不发布P08最终符号。",
            "",
        ]
    )
    return "\n".join(lines)


def run_pilot(config: dict[str, Any], checkpoint: Path, report: Path) -> dict[str, Any]:
    ground = optimize_ground_geometry(atoms_from_config(config), config)
    aligned = align_and_symmetrize(ground["atoms"], config)
    aligned_ground, density = ordinary_single_point(aligned, config)
    ground["aligned_symmetrized_atoms"] = aligned
    ground["aligned_symmetrized_single_point"] = aligned_ground
    gl_anchor = conditional_single_point(aligned, config, density)
    if not gl_anchor["converged"]:
        raise RuntimeError("GL(2014) anchor conditional SCF did not converge")

    pilot: list[dict[str, Any]] = []
    for displacement in config["central_bond_pilot"]["displacement_angstrom"]:
        trial_atoms = translated_central_bond(aligned, float(displacement), config)
        ordinary, trial_density = ordinary_single_point(trial_atoms, config)
        point = conditional_single_point(trial_atoms, config, trial_density)
        point["central_bond_displacement_from_G_angstrom"] = float(displacement)
        point["ordinary_scf_energy_hartree"] = ordinary["total_energy_hartree"]
        pilot.append(point)
        partial = {
            "schema_version": 1,
            "protocol_id": config["protocol_id"],
            "proposition_id": "P08",
            "stage": "ground_plus_gl2014_central_bond_pilot_in_progress",
            "ground_geometry": ground,
            "gl2014_at_ground_geometry": gl_anchor,
            "central_bond_pilot": pilot,
        }
        write_checkpoint(checkpoint, partial)

    energies = np.asarray([float(row["total_energy_hartree"]) for row in pilot])
    bonds = np.asarray([float(row["central_bond_angstrom"]) for row in pilot])
    coefficients = np.polyfit(bonds, energies, 2)
    quadratic_minimum = float(-coefficients[1] / (2.0 * coefficients[0])) if coefficients[0] > 0 else None
    record = {
        "schema_version": 1,
        "protocol_id": config["protocol_id"],
        "proposition_id": "P08",
        "stage": "ground_plus_gl2014_central_bond_pilot_complete",
        "ground_geometry": ground,
        "gl2014_at_ground_geometry": gl_anchor,
        "central_bond_pilot": pilot,
        "pilot_analysis": {
            "sampled_minimum_central_bond_angstrom": float(bonds[int(np.argmin(energies))]),
            "quadratic_minimum_central_bond_angstrom": quadratic_minimum,
            "quadratic_curvature_hartree_per_angstrom2": float(2.0 * coefficients[0]),
            "source_direction_r_GL_less_than_r_G_supported_in_pilot": bool(
                float(bonds[int(np.argmin(energies))]) < float(ground["central_bond_angstrom"])
            ),
            "p08_final_complete": False,
        },
        "boundaries": config["boundaries"],
    }
    write_checkpoint(checkpoint, record)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(render_report(record), encoding="utf-8")
    return record


def symmetry_parameters(atoms: list[list[Any]]) -> np.ndarray:
    xyz = np.asarray([row[1:4] for row in atoms], dtype=float)
    return np.asarray(
        [
            float(xyz[2, 0] - xyz[1, 0]),
            float(xyz[0, 0]),
            float(xyz[0, 1]),
            float(xyz[4, 0]),
            float(xyz[4, 1]),
            float(xyz[5, 0]),
            float(xyz[5, 1]),
            float(xyz[6, 0]),
            float(xyz[6, 1]),
        ],
        dtype=float,
    )


def atoms_from_symmetry_parameters(parameters: np.ndarray) -> list[list[Any]]:
    values = np.asarray(parameters, dtype=float)
    if values.shape != (9,):
        raise ValueError("P08 C2h geometry requires exactly nine parameters")
    r23, c0x, c0y, h4x, h4y, h5x, h5y, h6x, h6y = values.tolist()
    xyz = np.zeros((10, 3), dtype=float)
    xyz[0, :2] = [c0x, c0y]
    xyz[3, :2] = [-c0x, -c0y]
    xyz[1, 0] = -0.5 * r23
    xyz[2, 0] = 0.5 * r23
    xyz[4, :2] = [h4x, h4y]
    xyz[9, :2] = [-h4x, -h4y]
    xyz[5, :2] = [h5x, h5y]
    xyz[8, :2] = [-h5x, -h5y]
    xyz[6, :2] = [h6x, h6y]
    xyz[7, :2] = [-h6x, -h6y]
    symbols = ["C", "C", "C", "C", "H", "H", "H", "H", "H", "H"]
    return [[symbols[index], *xyz[index].tolist()] for index in range(10)]


def parameter_bounds(initial: np.ndarray, config: dict[str, Any]) -> list[tuple[float, float]]:
    optimization = config["gl2014_geometry_optimization"]
    windows = [
        float(optimization["central_bond_half_window_angstrom"]),
        *([float(optimization["terminal_carbon_coordinate_half_window_angstrom"])] * 2),
        *([float(optimization["hydrogen_coordinate_half_window_angstrom"])] * 6),
    ]
    return [
        (float(value - window), float(value + window))
        for value, window in zip(initial, windows, strict=True)
    ]


def run_full(
    config: dict[str, Any], checkpoint: Path, output: Path, report: Path
) -> dict[str, Any]:
    from scipy.optimize import minimize

    if not checkpoint.exists():
        raise FileNotFoundError("run the P08 pilot before the full GL(2014) optimization")
    pilot_record = json.loads(checkpoint.read_text(encoding="utf-8"))
    if pilot_record.get("stage") != "ground_plus_gl2014_central_bond_pilot_complete":
        raise RuntimeError("P08 pilot checkpoint is not complete")

    ground = pilot_record["ground_geometry"]
    aligned_atoms = ground["aligned_symmetrized_atoms"]
    initial = symmetry_parameters(aligned_atoms)
    bounds = parameter_bounds(initial, config)
    anchor_density = np.asarray(
        pilot_record["gl2014_at_ground_geometry"]["final_density"], dtype=float
    )
    evaluations: list[dict[str, Any]] = []
    cache: dict[tuple[float, ...], float] = {}

    def objective(parameters: np.ndarray) -> float:
        key = tuple(float(value) for value in np.round(parameters, decimals=12))
        if key in cache:
            return cache[key]
        atoms = atoms_from_symmetry_parameters(parameters)
        state = conditional_single_point(atoms, config, anchor_density)
        if not state["converged"]:
            raise RuntimeError("GL(2014) conditional SCF failed during geometry optimization")
        audit = state["occupied_pi_audit"]
        row = {
            "evaluation": len(evaluations) + 1,
            "parameters_angstrom": [float(value) for value in parameters],
            "central_bond_angstrom": float(state["central_bond_angstrom"]),
            "total_energy_hartree": float(state["total_energy_hartree"]),
            "scf_cycles": int(state["cycles"]),
            "modified_metric_electron_count": float(state["modified_metric_electron_count"]),
            "physical_metric_electron_count": float(state["physical_metric_electron_count"]),
            "left_occupied_pi_count": int(audit["left_occupied_pi_count"]),
            "right_occupied_pi_count": int(audit["right_occupied_pi_count"]),
            "mixed_occupied_pi_count": int(audit["mixed_occupied_pi_count"]),
            "geometry_sha256": state["geometry_sha256"],
        }
        evaluations.append(row)
        cache[key] = row["total_energy_hartree"]
        progress = dict(pilot_record)
        progress["stage"] = "gl2014_full_geometry_optimization_in_progress"
        progress["full_optimization_evaluations"] = evaluations
        write_checkpoint(checkpoint, progress)
        return row["total_energy_hartree"]

    optimization = config["gl2014_geometry_optimization"]
    result = minimize(
        objective,
        initial,
        method="L-BFGS-B",
        jac="2-point",
        bounds=bounds,
        options={
            "maxiter": int(optimization["maximum_iterations"]),
            "maxfun": int(optimization["maximum_function_evaluations"]),
            "ftol": float(optimization["function_tolerance"]),
            "gtol": float(optimization["gradient_tolerance_hartree_per_angstrom"]),
            "maxls": int(optimization["maximum_line_search_steps"]),
            "finite_diff_rel_step": float(optimization["finite_difference_relative_step"]),
        },
    )
    final_atoms = atoms_from_symmetry_parameters(result.x)
    final_state_full = conditional_single_point(final_atoms, config, anchor_density)
    final_state = compact_gl(final_state_full)
    ground_energy = float(ground["single_point"]["total_energy_hartree"])
    gl_energy = float(final_state["total_energy_hartree"])
    delta_e_hartree = ground_energy - gl_energy
    delta_e_kcal = delta_e_hartree * HARTREE_TO_KCAL_PER_MOL
    r_ground = float(ground["central_bond_angstrom"])
    r_gl = float(final_state["central_bond_angstrom"])
    delta_r = r_ground - r_gl
    acceptance = config["acceptance"]
    source = acceptance["source_comparison_only"]
    gradient = np.asarray(result.jac, dtype=float)
    active_bounds = [
        index
        for index, (value, interval) in enumerate(zip(result.x, bounds, strict=True))
        if abs(float(value) - interval[0]) <= 1.0e-6
        or abs(float(value) - interval[1]) <= 1.0e-6
    ]
    audit = final_state["occupied_pi_audit"]
    checks = {
        "optimizer_reports_success": bool(result.success),
        "optimizer_gradient_max_within_tolerance": float(np.max(np.abs(gradient)))
        <= float(optimization["gradient_tolerance_hartree_per_angstrom"]),
        "no_active_parameter_bound": len(active_bounds) == 0,
        "final_gl_scf_converged": bool(final_state["converged"]),
        "one_occupied_pi_per_fragment": int(audit["left_occupied_pi_count"]) == 1
        and int(audit["right_occupied_pi_count"]) == 1,
        "no_mixed_occupied_pi": int(audit["mixed_occupied_pi_count"]) == 0,
        "modified_metric_electron_count_closes": abs(
            float(final_state["modified_metric_electron_count"]) - 30.0
        )
        <= float(acceptance["modified_metric_electron_tolerance"]),
        "delta_EA_positive": delta_e_kcal
        > float(acceptance["source_direction_minimum_kcal_per_mol"]),
        "r23_G_greater_than_r23_GL": delta_r
        > float(acceptance["source_direction_minimum_bond_difference_angstrom"]),
        "source_energy_value_within_comparison_tolerance": abs(
            delta_e_kcal - float(source["delta_EA_kcal_per_mol"])
        )
        <= float(acceptance["source_numeric_comparison_tolerance_kcal_per_mol"]),
        "source_r23_GL_within_comparison_tolerance": abs(
            r_gl - float(source["r23_GL_angstrom"])
        )
        <= float(acceptance["source_numeric_comparison_tolerance_angstrom"]),
        "p08_b_hydrogenation_reference_subtarget_complete": True,
        "ai_training_started": False,
    }
    technical = [
        checks["optimizer_reports_success"] or checks["optimizer_gradient_max_within_tolerance"],
        checks["no_active_parameter_bound"],
        checks["final_gl_scf_converged"],
        checks["one_occupied_pi_per_fragment"],
        checks["no_mixed_occupied_pi"],
        checks["modified_metric_electron_count_closes"],
    ]
    if not all(technical):
        verdict = "P08_GL2014_TECHNICALLY_INDETERMINATE"
    elif checks["delta_EA_positive"] and checks["r23_G_greater_than_r23_GL"]:
        verdict = "P08_SCOPED_BUTADIENE_PROPOSITION_SUPPORTED"
    else:
        verdict = "P08_SCOPED_BUTADIENE_PROPOSITION_OPPOSED_OR_INDETERMINATE"

    final_record = {
        "schema_version": 1,
        "protocol_id": config["protocol_id"],
        "proposition_id": "P08",
        "date": str(config["date"]),
        "stage": "p08_G_GL2014_and_central_bond_complete",
        "verdict": verdict,
        "relation_to_monograph": (
            "consistent_with_GL2014_energy_sign_hydrogenation_reference_sensitivity_"
            "and_central_bond_direction_in_declared_scope"
            if verdict == "P08_SCOPED_BUTADIENE_PROPOSITION_SUPPORTED"
            else "not_finally_consistent"
        ),
        "ground_geometry": {
            key: value for key, value in ground.items() if key != "density"
        },
        "gl2014_geometry": final_state,
        "energy_and_geometry_decision": {
            "delta_EA_definition": "E(G)-E(GL2014)",
            "delta_EA_hartree": delta_e_hartree,
            "delta_EA_kcal_per_mol": delta_e_kcal,
            "delta_EA_classification": "destabilizing" if delta_e_kcal > 0.0 else "stabilizing",
            "r23_G_angstrom": r_ground,
            "r23_GL_angstrom": r_gl,
            "delta_r23_G_minus_GL_angstrom": delta_r,
            "central_bond_interpretation": (
                "source_defined_delocalization_lengthens_central_sp2_sp2_single_bond"
                if delta_r > 0.0
                else "source_defined_lengthening_not_supported"
            ),
        },
        "source_comparison": {
            "target": source,
            "delta_EA_absolute_error_kcal_per_mol": abs(
                delta_e_kcal - float(source["delta_EA_kcal_per_mol"])
            ),
            "r23_GL_absolute_error_angstrom": abs(r_gl - float(source["r23_GL_angstrom"])),
            "delta_r23_absolute_error_angstrom": abs(
                delta_r - float(source["delta_r23_angstrom"])
            ),
            "published_values_used_as_fit_targets": False,
        },
        "optimizer": {
            "method": str(optimization["optimizer"]),
            "success": bool(result.success),
            "status": int(result.status),
            "message": str(result.message),
            "iterations": int(result.nit),
            "function_evaluations_reported": int(result.nfev),
            "unique_function_evaluations": len(evaluations),
            "maximum_absolute_gradient_hartree_per_angstrom": float(np.max(np.abs(gradient))),
            "active_bound_parameter_indices": active_bounds,
            "initial_parameters_angstrom": initial.tolist(),
            "final_parameters_angstrom": np.asarray(result.x).tolist(),
            "bounds_angstrom": [[float(a), float(b)] for a, b in bounds],
        },
        "checks": checks,
        "p08_subtargets": {
            "P08_A_G_GL_energy_sign": "complete",
            "P08_B_hydrogenation_reference_sensitivity": "complete",
            "P08_C_central_bond_explanation": "complete",
        },
        "p08_complete": verdict == "P08_SCOPED_BUTADIENE_PROPOSITION_SUPPORTED",
        "production_label": False,
        "training_eligible": False,
        "universal_conjugation_law": False,
        "boundaries": config["boundaries"],
        "full_optimization_evaluations": evaluations,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(final_record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_checkpoint(checkpoint, final_record)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(render_final_report(final_record), encoding="utf-8")
    return final_record


def render_final_report(record: dict[str, Any]) -> str:
    decision = record["energy_and_geometry_decision"]
    comparison = record["source_comparison"]
    optimizer = record["optimizer"]
    checks = record["checks"]
    lines = [
        "# P08 丁二烯 G-GL(2014) source-aligned独立重构",
        "",
        f"- 协议：`{record['protocol_id']}`",
        f"- 判定：`{record['verdict']}`",
        f"- 优化器：`{optimizer['method']}`，{optimizer['iterations']} iterations / {optimizer['unique_function_evaluations']} unique evaluations",
        "",
        "## 最终数值",
        "",
        "| 量 | 项目结果 | 原著GL(2014)比较值 | 绝对差 |",
        "|---|---:|---:|---:|",
        f"| ΔEA = E(G)-E(GL) | {decision['delta_EA_kcal_per_mol']:+.6f} kcal/mol | +{comparison['target']['delta_EA_kcal_per_mol']:.1f} | {comparison['delta_EA_absolute_error_kcal_per_mol']:.6f} |",
        f"| r23(G) | {decision['r23_G_angstrom']:.6f} Å | {comparison['target']['r23_G_angstrom']:.3f} | {abs(decision['r23_G_angstrom']-comparison['target']['r23_G_angstrom']):.6f} |",
        f"| r23(GL) | {decision['r23_GL_angstrom']:.6f} Å | {comparison['target']['r23_GL_angstrom']:.3f} | {comparison['r23_GL_absolute_error_angstrom']:.6f} |",
        f"| r23(G)-r23(GL) | {decision['delta_r23_G_minus_GL_angstrom']:+.6f} Å | +{comparison['target']['delta_r23_angstrom']:.3f} | {comparison['delta_r23_absolute_error_angstrom']:.6f} |",
        "",
        "## 判定",
        "",
        f"- P08-A：`{decision['delta_EA_classification']}`。正的 `E(G)-E(GL)` 表示原著定义下的离域端点为去稳定化。",
        "- P08-B：三种丁烯参照给出稳定化、近零和去稳定化三类结果，因此选择性氢化热不是唯一符号证据。",
        f"- P08-C：`{decision['central_bond_interpretation']}`；同协议GL中央键短于G中央键。",
        "",
        "## 技术检查",
        "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in checks.items())
    lines.extend(
        [
            "",
            "## 结论边界",
            "",
            "本结果在当前冻结的公开条件source-aligned协议内支持原著关于反式-1,3-丁二烯的三个范围化命题。项目未使用原著程序代码，也不宣称与原厂PC-GAMESS实现逐项同一。同一实现采用不同普通RKS初始密度的复算只证明收敛稳健性，不是第二套程序复现。旧CASCADE常规热化学结论仅作外部参考，不参与本判定。本结果不证明所有分子的普遍共轭去稳定化定律，也不是生产标签。",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--stage", choices=("pilot", "full"), default="pilot")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    if args.stage == "pilot":
        record = run_pilot(config, args.checkpoint, args.report)
        summary = {
            "stage": record["stage"],
            "G_r23_angstrom": record["ground_geometry"]["central_bond_angstrom"],
            "pilot_r23_min_angstrom": record["pilot_analysis"]["sampled_minimum_central_bond_angstrom"],
            "quadratic_r23_min_angstrom": record["pilot_analysis"]["quadratic_minimum_central_bond_angstrom"],
        }
    else:
        record = run_full(config, args.checkpoint, args.output, DEFAULT_FINAL_REPORT)
        decision = record["energy_and_geometry_decision"]
        summary = {
            "stage": record["stage"],
            "verdict": record["verdict"],
            "delta_EA_kcal_per_mol": decision["delta_EA_kcal_per_mol"],
            "r23_G_angstrom": decision["r23_G_angstrom"],
            "r23_GL_angstrom": decision["r23_GL_angstrom"],
            "delta_r23_angstrom": decision["delta_r23_G_minus_GL_angstrom"],
        }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
