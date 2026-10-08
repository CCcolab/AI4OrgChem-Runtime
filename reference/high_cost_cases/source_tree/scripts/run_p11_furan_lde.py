"""Run the frozen P11-A single-furan 2007-semantics LDE calculation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np
import yaml

from ai4orgchem.qm.p09_ao_classification import classify_planar_pyscf_aos
from ai4orgchem.qm.p09_conditional_scf import run_p09_conditional_rks


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = ROOT / "configs/qm/p11_furan_lde_v0.1.yaml"
DEFAULT_CHECKPOINT = ROOT / "runs/validation/p11_furan_lde_checkpoint_v0.1.json"
DEFAULT_OUTPUT = ROOT / "data/processed/p11_furan_lde_v0.1.json"
DEFAULT_REPORT = ROOT / "docs/reports/p11_furan_lde_2026-08-21.md"
HARTREE_TO_KCAL_PER_MOL = 627.5094740631


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def furan_atoms(parameters: np.ndarray) -> list[list[Any]]:
    """Build planar C2v furan with O fixed at the coordinate origin."""

    xa, ya, xb, yb, xha, yha, xhb, yhb = np.asarray(
        parameters, dtype=float
    ).tolist()
    return [
        ["O", 0.0, 0.0, 0.0],
        ["C", -xa, ya, 0.0],
        ["C", -xb, yb, 0.0],
        ["C", xb, yb, 0.0],
        ["C", xa, ya, 0.0],
        ["H", -xha, yha, 0.0],
        ["H", -xhb, yhb, 0.0],
        ["H", xhb, yhb, 0.0],
        ["H", xha, yha, 0.0],
    ]


def geometry_metrics(atoms: list[list[Any]]) -> dict[str, float]:
    xyz = np.asarray([row[1:4] for row in atoms], dtype=float)

    def distance(first: int, second: int) -> float:
        return float(np.linalg.norm(xyz[first] - xyz[second]))

    return {
        "O1_C2": distance(0, 1),
        "C2_C3": distance(1, 2),
        "C3_C4": distance(2, 3),
        "C4_C5": distance(3, 4),
        "C5_O1": distance(4, 0),
        "C2_H2": distance(1, 5),
        "C3_H3": distance(2, 6),
        "C4_H4": distance(3, 7),
        "C5_H5": distance(4, 8),
    }


def build_molecule(atoms: list[list[Any]], protocol: dict[str, Any]) -> Any:
    from pyscf import gto

    electronic = protocol["electronic_structure"]
    return gto.M(
        atom=atoms,
        basis=str(electronic["basis"]),
        charge=int(electronic["charge"]),
        spin=int(electronic["multiplicity"]) - 1,
        unit="Angstrom",
        symmetry=False,
        verbose=0,
    )


def build_mean_field(molecule: Any, protocol: dict[str, Any]) -> Any:
    from pyscf import dft

    electronic = protocol["electronic_structure"]
    mean_field = dft.RKS(molecule)
    mean_field.verbose = 0
    mean_field.xc = str(electronic["pyscf_xc"])
    mean_field.grids.level = int(electronic["grid_level"])
    mean_field.conv_tol = float(electronic["scf_tolerance_hartree"])
    mean_field.max_cycle = int(electronic["maximum_scf_cycles"])
    mean_field.max_memory = int(electronic["maximum_memory_mb"])
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
) -> dict[str, Any]:
    molecule = build_molecule(atoms, protocol)
    mean_field = build_mean_field(molecule, protocol)
    descriptors = classify_planar_pyscf_aos(molecule, fragment_map)
    options = protocol["conditional_scf"]
    # Empty ERI deletion classes implement the source-2007 branch: only the
    # interfragment pi Fock/one-electron/overlap blocks are suppressed.
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
    )


def compact_state(state: dict[str, Any]) -> dict[str, Any]:
    excluded = {"density", "mo_coefficients", "mo_energies_hartree", "mo_occupations"}
    return {key: value for key, value in state.items() if key not in excluded}


def optimize_state(
    *,
    name: str,
    initial: np.ndarray,
    bounds: list[tuple[float, float]],
    evaluator: Callable[[np.ndarray], dict[str, Any]],
    protocol: dict[str, Any],
    checkpoint: Path,
) -> tuple[Any, list[dict[str, Any]]]:
    from scipy.optimize import minimize

    options = protocol["optimizer"]
    evaluations: list[dict[str, Any]] = []
    cache: dict[tuple[float, ...], float] = {}

    def objective(parameters: np.ndarray) -> float:
        key = tuple(float(value) for value in np.round(parameters, decimals=12))
        if key in cache:
            return cache[key]
        state = evaluator(parameters)
        if not bool(state["converged"]):
            raise RuntimeError(f"{name} SCF failed during geometry optimization")
        row = {
            "evaluation": len(evaluations) + 1,
            "parameters_angstrom": [float(value) for value in parameters],
            "energy_hartree": float(state["total_energy_hartree"]),
            "scf_cycles": int(state.get("cycles", 0)),
        }
        evaluations.append(row)
        cache[key] = row["energy_hartree"]
        write_json(
            checkpoint,
            {
                "schema_version": 1,
                "protocol_id": protocol["protocol_id"],
                "stage": f"furan_{name}_optimization_in_progress",
                "evaluations": evaluations,
            },
        )
        print(json.dumps({"stage": name, **row}, ensure_ascii=False), flush=True)
        return row["energy_hartree"]

    result = minimize(
        objective,
        initial,
        method="L-BFGS-B",
        jac=str(options["finite_difference_scheme"]),
        bounds=bounds,
        options={
            "maxiter": int(options["maximum_iterations"]),
            "maxfun": int(options["maximum_function_evaluations"]),
            "ftol": float(options["function_tolerance"]),
            "gtol": float(options["gradient_tolerance_hartree_per_angstrom"]),
            "maxls": int(options["maximum_line_search_steps"]),
            "finite_diff_rel_step": float(options["finite_difference_relative_step"]),
        },
    )
    return result, evaluations


def optimizer_record(
    result: Any, bounds: list[tuple[float, float]], evaluations: list[dict[str, Any]]
) -> dict[str, Any]:
    parameters = np.asarray(result.x, dtype=float)
    gradient = np.asarray(result.jac, dtype=float)
    active_bounds = [
        index
        for index, (value, interval) in enumerate(zip(parameters, bounds, strict=True))
        if abs(float(value) - interval[0]) <= 1.0e-6
        or abs(float(value) - interval[1]) <= 1.0e-6
    ]
    return {
        "success": bool(result.success),
        "status": int(result.status),
        "message": str(result.message),
        "iterations": int(result.nit),
        "function_evaluations": int(result.nfev),
        "gradient_hartree_per_angstrom": gradient.tolist(),
        "gradient_max_abs_hartree_per_angstrom": float(np.max(np.abs(gradient))),
        "active_bounds": active_bounds,
        "bounds_angstrom": bounds,
        "evaluations": evaluations,
    }


def conditional_checks(
    prefix: str, state: dict[str, Any], protocol: dict[str, Any]
) -> dict[str, bool]:
    acceptance = protocol["acceptance"]
    return {
        f"{prefix}_SCF_converged": bool(state["converged"]),
        f"{prefix}_36_electrons": abs(
            float(state["masked_metric_electron_count"])
            - float(acceptance["electron_count"])
        )
        <= float(acceptance["electron_count_tolerance"]),
        f"{prefix}_cross_pi_overlap_zero": float(
            state["masked_overlap_cross_pi_max_abs"]
        )
        <= float(acceptance["matrix_zero_tolerance"]),
        f"{prefix}_cross_pi_fock_zero": float(
            state["conditional_fock_cross_pi_max_abs"]
        )
        <= float(acceptance["matrix_zero_tolerance"]),
        f"{prefix}_components_close": float(
            state["energy_component_closure_residual_hartree"]
        )
        <= float(acceptance["energy_component_closure_hartree"]),
        f"{prefix}_commutator_closed": float(
            state["final_commutator_frobenius_norm"]
        )
        <= float(acceptance["commutator_frobenius_tolerance"]),
        f"{prefix}_density_idempotent": float(
            state["closed_shell_idempotency_relative_residual"]
        )
        <= float(acceptance["idempotency_relative_tolerance"]),
        f"{prefix}_2007_branch_has_no_ERI_deletion": int(state["deleted_eri_count"])
        == 0,
    }


def render_report(record: dict[str, Any]) -> str:
    lines = [
        "# P11-A 呋喃LDE计算报告",
        "",
        f"- 协议：`{record['protocol_id']}`",
        "- 状态：普通G及source-2007 GL/GE1/GE2；GE3由C2v对称等价于GE2。",
        f"- ΔEA：`{record['delta_EA_kcal_mol']:+.6f} kcal/mol`。",
        f"- ΔEA1：`{record['delta_EA1_kcal_mol']:+.6f} kcal/mol`。",
        f"- ΔEA2=ΔEA3：`{record['delta_EA2_kcal_mol']:+.6f} kcal/mol`。",
        f"- ΣΔEAm：`{record['sum_delta_EAm_kcal_mol']:+.6f} kcal/mol`。",
        f"- LDE：`{record['LDE_kcal_mol']:+.6f} kcal/mol`。",
        "",
        "## 验收",
        "",
        "| 检查项 | 结果 |",
        "|---|---|",
    ]
    for name, passed in record["acceptance_checks"].items():
        lines.append(f"| `{name}` | `{'PASS' if passed else 'FAIL'}` |")
    lines.extend(
        [
            "",
            f"计算门禁：`{record['calculation_gate_verdict']}`。",
            "",
            "公开−39.3 kcal/mol只在本原始结果封存后由独立验证器比较。该差值按原著后期定义称LDE，不生成苯型ESE标签。",
            "",
        ]
    )
    return "\n".join(lines)


def run(protocol_path: Path, checkpoint: Path) -> dict[str, Any]:
    protocol = yaml.safe_load(protocol_path.read_text(encoding="utf-8"))
    if protocol["execution"]["scope"] != "single_furan_G_GL_GE1_GE2_2007_LDE_only":
        raise RuntimeError("P11-A protocol does not authorize the frozen furan path")

    initial = np.asarray(protocol["geometry"]["initial_parameters_angstrom"], dtype=float)
    initial_bounds = [
        (float(interval[0]), float(interval[1]))
        for interval in protocol["geometry"]["initial_bounds_angstrom"]
    ]

    g_result, g_evaluations = optimize_state(
        name="G",
        initial=initial,
        bounds=initial_bounds,
        evaluator=lambda parameters: ordinary_state(furan_atoms(parameters), protocol),
        protocol=protocol,
        checkpoint=checkpoint,
    )
    g_parameters = np.asarray(g_result.x, dtype=float)
    g_atoms = furan_atoms(g_parameters)
    g_state_raw = ordinary_state(g_atoms, protocol)
    if not g_state_raw["converged"]:
        raise RuntimeError("final furan G state did not converge")
    g_density = np.asarray(g_state_raw["density"], dtype=float)
    g_state = compact_state(g_state_raw)
    g_optimizer = optimizer_record(g_result, initial_bounds, g_evaluations)

    half_windows = np.asarray(
        protocol["geometry"]["conditional_half_windows_angstrom"], dtype=float
    )
    conditional_bounds = [
        (float(value - window), float(value + window))
        for value, window in zip(g_parameters, half_windows, strict=True)
    ]
    gl_fragments = {0: "O", 1: "A", 2: "A", 3: "B", 4: "B"}
    ge1_fragments = {0: "O", 1: "AB", 2: "AB", 3: "AB", 4: "AB"}
    ge2_fragments = {0: "OA", 1: "OA", 2: "OA", 3: "B", 4: "B"}

    gl_result, gl_evaluations = optimize_state(
        name="GL",
        initial=g_parameters,
        bounds=conditional_bounds,
        evaluator=lambda parameters: conditional_state(
            furan_atoms(parameters), gl_fragments, g_density, protocol
        ),
        protocol=protocol,
        checkpoint=checkpoint,
    )
    gl_parameters = np.asarray(gl_result.x, dtype=float)
    gl_atoms = furan_atoms(gl_parameters)
    gl_state_raw = conditional_state(gl_atoms, gl_fragments, g_density, protocol)
    if not gl_state_raw["converged"]:
        raise RuntimeError("final furan GL state did not converge")
    gl_density = np.asarray(gl_state_raw["density"], dtype=float)
    gl_state = compact_state(gl_state_raw)
    gl_optimizer = optimizer_record(gl_result, conditional_bounds, gl_evaluations)

    ge1_result, ge1_evaluations = optimize_state(
        name="GE1",
        initial=gl_parameters,
        bounds=conditional_bounds,
        evaluator=lambda parameters: conditional_state(
            furan_atoms(parameters), ge1_fragments, gl_density, protocol
        ),
        protocol=protocol,
        checkpoint=checkpoint,
    )
    ge1_parameters = np.asarray(ge1_result.x, dtype=float)
    ge1_atoms = furan_atoms(ge1_parameters)
    ge1_state_raw = conditional_state(ge1_atoms, ge1_fragments, gl_density, protocol)
    if not ge1_state_raw["converged"]:
        raise RuntimeError("final furan GE1 state did not converge")
    ge1_state = compact_state(ge1_state_raw)
    ge1_optimizer = optimizer_record(ge1_result, conditional_bounds, ge1_evaluations)

    ge2_result, ge2_evaluations = optimize_state(
        name="GE2",
        initial=gl_parameters,
        bounds=conditional_bounds,
        evaluator=lambda parameters: conditional_state(
            furan_atoms(parameters), ge2_fragments, gl_density, protocol
        ),
        protocol=protocol,
        checkpoint=checkpoint,
    )
    ge2_parameters = np.asarray(ge2_result.x, dtype=float)
    ge2_atoms = furan_atoms(ge2_parameters)
    ge2_state_raw = conditional_state(ge2_atoms, ge2_fragments, gl_density, protocol)
    if not ge2_state_raw["converged"]:
        raise RuntimeError("final furan GE2 state did not converge")
    ge2_state = compact_state(ge2_state_raw)
    ge2_optimizer = optimizer_record(ge2_result, conditional_bounds, ge2_evaluations)

    g_energy = float(g_state["total_energy_hartree"])
    gl_energy = float(gl_state["total_energy_hartree"])
    ge1_energy = float(ge1_state["total_energy_hartree"])
    ge2_energy = float(ge2_state["total_energy_hartree"])
    delta_ea = g_energy - gl_energy
    delta_ea1 = ge1_energy - gl_energy
    delta_ea2 = ge2_energy - gl_energy
    increment_sum = delta_ea1 + 2.0 * delta_ea2
    lde = delta_ea - increment_sum

    optimizer_threshold = float(
        protocol["optimizer"]["gradient_tolerance_hartree_per_angstrom"]
    )
    direction_tolerance = float(
        protocol["acceptance"]["strict_direction_tolerance_hartree"]
    )
    optimizers = {
        "G": g_optimizer,
        "GL": gl_optimizer,
        "GE1": ge1_optimizer,
        "GE2": ge2_optimizer,
    }
    checks: dict[str, bool] = {}
    for name, optimizer in optimizers.items():
        checks[f"{name}_optimizer_success"] = bool(optimizer["success"])
        checks[f"{name}_gradient_within_tolerance"] = (
            float(optimizer["gradient_max_abs_hartree_per_angstrom"])
            <= optimizer_threshold
        )
        checks[f"{name}_no_active_bound"] = len(optimizer["active_bounds"]) == 0
    checks["G_SCF_converged"] = bool(g_state["converged"])
    checks.update(conditional_checks("GL", gl_state, protocol))
    checks.update(conditional_checks("GE1", ge1_state, protocol))
    checks.update(conditional_checks("GE2", ge2_state, protocol))
    checks.update(
        {
            "delta_EA_positive": delta_ea > direction_tolerance,
            "delta_EA1_positive": delta_ea1 > direction_tolerance,
            "delta_EA2_positive": delta_ea2 > direction_tolerance,
            "sum_increments_exceeds_delta_EA": increment_sum
            > delta_ea + direction_tolerance,
            "LDE_negative": lde < -direction_tolerance,
            "LDE_identity_closes": abs(lde - (g_energy - (gl_energy + increment_sum)))
            <= float(protocol["acceptance"]["energy_identity_hartree"]),
        }
    )

    record = {
        "schema_version": 1,
        "protocol_id": protocol["protocol_id"],
        "proposition_id": "P11",
        "subtarget": "P11-A_furan_LDE",
        "stage": "furan_G_GL_GE1_GE2_2007_LDE",
        "implementation_semantics": protocol["state_contract"][
            "implementation_semantics"
        ],
        "G": {
            "parameters_angstrom": g_parameters.tolist(),
            "atoms_angstrom": g_atoms,
            "geometry_metrics_angstrom": geometry_metrics(g_atoms),
            "state": g_state,
            "optimizer": g_optimizer,
        },
        "GL": {
            "parameters_angstrom": gl_parameters.tolist(),
            "atoms_angstrom": gl_atoms,
            "geometry_metrics_angstrom": geometry_metrics(gl_atoms),
            "state": gl_state,
            "optimizer": gl_optimizer,
        },
        "GE1": {
            "parameters_angstrom": ge1_parameters.tolist(),
            "atoms_angstrom": ge1_atoms,
            "geometry_metrics_angstrom": geometry_metrics(ge1_atoms),
            "state": ge1_state,
            "optimizer": ge1_optimizer,
            "permitted_interaction": "A_B",
        },
        "GE2": {
            "parameters_angstrom": ge2_parameters.tolist(),
            "atoms_angstrom": ge2_atoms,
            "geometry_metrics_angstrom": geometry_metrics(ge2_atoms),
            "state": ge2_state,
            "optimizer": ge2_optimizer,
            "permitted_interaction": "O_A",
            "multiplicity": 2,
        },
        "delta_EA_hartree": delta_ea,
        "delta_EA_kcal_mol": delta_ea * HARTREE_TO_KCAL_PER_MOL,
        "delta_EA1_hartree": delta_ea1,
        "delta_EA1_kcal_mol": delta_ea1 * HARTREE_TO_KCAL_PER_MOL,
        "delta_EA2_hartree": delta_ea2,
        "delta_EA2_kcal_mol": delta_ea2 * HARTREE_TO_KCAL_PER_MOL,
        "sum_delta_EAm_hartree": increment_sum,
        "sum_delta_EAm_kcal_mol": increment_sum * HARTREE_TO_KCAL_PER_MOL,
        "LDE_hartree": lde,
        "LDE_kcal_mol": lde * HARTREE_TO_KCAL_PER_MOL,
        "source_value_comparison_status": "sealed_pending_post_calculation_validator",
        "acceptance_checks": checks,
        "calculation_gate_verdict": "PASS" if all(checks.values()) else "FAIL",
        "aromatic_ESE_label": False,
        "production_label": False,
        "training_eligible": False,
    }
    write_json(checkpoint, record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    record = run(args.protocol.resolve(), args.checkpoint.resolve())
    write_json(args.output.resolve(), record)
    args.report.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.report.resolve().write_text(render_report(record), encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": record["calculation_gate_verdict"],
                "delta_EA_kcal_mol": record["delta_EA_kcal_mol"],
                "delta_EA1_kcal_mol": record["delta_EA1_kcal_mol"],
                "delta_EA2_kcal_mol": record["delta_EA2_kcal_mol"],
                "sum_delta_EAm_kcal_mol": record["sum_delta_EAm_kcal_mol"],
                "LDE_kcal_mol": record["LDE_kcal_mol"],
                "output": str(args.output.resolve()),
                "report": str(args.report.resolve()),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0 if record["calculation_gate_verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
