"""Run the frozen P11-B cyanobenzene Figure-7 energy reconstruction."""

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
DEFAULT_PROTOCOL = ROOT / "configs/qm/p11_substituted_benzene_effect_v0.1.yaml"
DEFAULT_OUTPUT = ROOT / "data/processed/p11_cyanobenzene_effect_v0.1.json"
DEFAULT_REPORT = ROOT / "docs/reports/p11_cyanobenzene_effect_2026-08-21.md"
HARTREE_TO_KCAL_PER_MOL = 627.5094740631


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _angle(first: np.ndarray, center: np.ndarray, third: np.ndarray) -> float:
    left = first - center
    right = third - center
    cosine = float(np.dot(left, right) / (np.linalg.norm(left) * np.linalg.norm(right)))
    return float(np.arccos(np.clip(cosine, -1.0, 1.0)))


def reconstruct_ring(target_lengths: list[float]) -> tuple[np.ndarray, dict[str, Any]]:
    """Fit a planar convex ring to six source bond lengths with minimal angle distortion."""

    from scipy.optimize import least_squares

    target = np.asarray(target_lengths, dtype=float)
    if target.shape != (6,):
        raise ValueError("cyanobenzene ring requires six target bond lengths")
    mean = float(np.mean(target))
    initial = np.asarray(
        [
            [0.0, 0.0],
            [target[0], 0.0],
            [1.5 * mean, -np.sqrt(3.0) * mean / 2.0],
            [mean, -np.sqrt(3.0) * mean],
            [0.0, -np.sqrt(3.0) * mean],
            [-0.5 * mean, -np.sqrt(3.0) * mean / 2.0],
        ],
        dtype=float,
    )

    def coordinates(variables: np.ndarray) -> np.ndarray:
        ring = initial.copy()
        ring[2:] = np.asarray(variables, dtype=float).reshape(4, 2)
        return ring

    def residuals(variables: np.ndarray) -> np.ndarray:
        ring = coordinates(variables)
        bonds = np.asarray(
            [np.linalg.norm(ring[(index + 1) % 6] - ring[index]) for index in range(6)]
        )
        angles = np.asarray(
            [
                _angle(ring[(index - 1) % 6], ring[index], ring[(index + 1) % 6])
                for index in range(6)
            ]
        )
        return np.concatenate(
            [
                (bonds - target) / 1.0e-5,
                (angles - 2.0 * np.pi / 3.0) / 0.05,
            ]
        )

    result = least_squares(
        residuals,
        initial[2:].reshape(-1),
        method="trf",
        ftol=1.0e-14,
        xtol=1.0e-14,
        gtol=1.0e-14,
        max_nfev=5000,
    )
    ring = coordinates(result.x)
    ring -= np.mean(ring, axis=0)
    fitted = np.asarray(
        [np.linalg.norm(ring[(index + 1) % 6] - ring[index]) for index in range(6)]
    )
    angles = np.asarray(
        [
            _angle(ring[(index - 1) % 6], ring[index], ring[(index + 1) % 6])
            for index in range(6)
        ]
    )
    metadata = {
        "solver_success": bool(result.success),
        "solver_message": str(result.message),
        "target_ring_bonds_angstrom": target.tolist(),
        "fitted_ring_bonds_angstrom": fitted.tolist(),
        "maximum_ring_bond_error_angstrom": float(np.max(np.abs(fitted - target))),
        "ring_angles_degrees": np.degrees(angles).tolist(),
        "maximum_angle_deviation_degrees": float(
            np.max(np.abs(np.degrees(angles) - 120.0))
        ),
    }
    return ring, metadata


def outward_bisector(ring: np.ndarray, index: int) -> np.ndarray:
    center = ring[index]
    previous = ring[(index - 1) % 6] - center
    following = ring[(index + 1) % 6] - center
    inward = previous / np.linalg.norm(previous) + following / np.linalg.norm(following)
    outward = -inward / np.linalg.norm(inward)
    return outward


def cyanobenzene_atoms(
    state_geometry: dict[str, Any], geometry_options: dict[str, Any]
) -> tuple[list[list[Any]], dict[str, Any]]:
    ring, metadata = reconstruct_ring([float(value) for value in state_geometry["ring"]])
    cyano_direction = outward_bisector(ring, 0)
    cyano_carbon = ring[0] + float(state_geometry["C1_X"]) * cyano_direction
    nitrogen = cyano_carbon + float(geometry_options["fixed_cyano_CN_angstrom"]) * cyano_direction
    hydrogens = [
        ring[index]
        + float(geometry_options["fixed_CH_angstrom"]) * outward_bisector(ring, index)
        for index in range(1, 6)
    ]
    atoms = [
        *[["C", float(x), float(y), 0.0] for x, y in ring],
        ["C", float(cyano_carbon[0]), float(cyano_carbon[1]), 0.0],
        ["N", float(nitrogen[0]), float(nitrogen[1]), 0.0],
        *[["H", float(x), float(y), 0.0] for x, y in hydrogens],
    ]
    metadata.update(
        {
            "C1_X_target_angstrom": float(state_geometry["C1_X"]),
            "C1_X_fitted_angstrom": float(np.linalg.norm(cyano_carbon - ring[0])),
            "CN_angstrom": float(np.linalg.norm(nitrogen - cyano_carbon)),
            "CH_angstrom": [
                float(np.linalg.norm(hydrogen - ring[index]))
                for index, hydrogen in zip(range(1, 6), hydrogens, strict=True)
            ],
        }
    )
    return atoms, metadata


def build_molecule(atoms: list[list[Any]], protocol: dict[str, Any]) -> Any:
    from pyscf import gto

    electronic = protocol["electronic_structure"]
    system = protocol["system"]
    return gto.M(
        atom=atoms,
        basis=str(electronic["basis"]),
        charge=int(system["charge"]),
        spin=int(system["multiplicity"]) - 1,
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


def compact_state(state: dict[str, Any]) -> dict[str, Any]:
    excluded = {"density", "mo_coefficients", "mo_energies_hartree", "mo_occupations"}
    return {key: value for key, value in state.items() if key not in excluded}


def conditional_checks(
    prefix: str, state: dict[str, Any], protocol: dict[str, Any]
) -> dict[str, bool]:
    acceptance = protocol["acceptance"]
    return {
        f"{prefix}_SCF_converged": bool(state["converged"]),
        f"{prefix}_54_electrons": abs(
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
        "# P11-B 氰基苯共轭/诱导效应分离计算报告",
        "",
        f"- 协议：`{record['protocol_id']}`",
        "- 几何：作者Figure 7重原子键长source proxy；不宣称历史Cartesian坐标身份。",
        "- 状态：source-2007 Fock/one-electron/overlap屏蔽；无ERI删除。",
        "",
        "| 量 | kcal/mol |",
        "|---|---:|",
        f"| ESE(SB) | {record['ESE_SB_kcal_mol']:+.6f} |",
        f"| ESE(Ph) | {record['ESE_Ph_kcal_mol']:+.6f} |",
        f"| CE=ESE(SB)-ESE(Ph) | {record['conjugative_effect_kcal_mol']:+.6f} |",
        "",
        "`IE=ESE(Ph)-ESE(benzene)`由独立验证器在结果封存后引入同一2007来源的苯锚点计算。",
        "",
        "## 计算门禁",
        "",
        f"- 结果：`{record['calculation_gate_verdict']}`",
        f"- 通过项：`{sum(record['acceptance_checks'].values())}/{len(record['acceptance_checks'])}`",
        "",
    ]
    return "\n".join(lines)


def run(
    protocol_path: Path, *, mask_one_electron_matrix: bool = True
) -> dict[str, Any]:
    protocol = yaml.safe_load(protocol_path.read_text(encoding="utf-8"))
    if protocol["execution"]["scope"] != "single_cyanobenzene_figure7_source_geometry_energy_reconstruction_only":
        raise RuntimeError("P11-B protocol does not authorize the frozen cyanobenzene path")

    geometry_options = protocol["geometry"]
    state_atoms: dict[str, list[list[Any]]] = {}
    geometry_records: dict[str, dict[str, Any]] = {}
    for state_name, state_geometry in geometry_options["states"].items():
        atoms, metadata = cyanobenzene_atoms(state_geometry, geometry_options)
        state_atoms[state_name] = atoms
        geometry_records[state_name] = {"atoms_angstrom": atoms, **metadata}

    g_raw = ordinary_state(state_atoms["G"], protocol)
    if not g_raw["converged"]:
        raise RuntimeError("cyanobenzene ordinary G state did not converge")
    g_density = np.asarray(g_raw["density"], dtype=float)
    g_state = compact_state(g_raw)

    fragment_maps = {
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

    raw_states: dict[str, dict[str, Any]] = {}
    gl_i_raw = conditional_state(
        state_atoms["GL_I"], fragment_maps["GL_I"], g_density, protocol,
        mask_one_electron_matrix=mask_one_electron_matrix,
    )
    if not gl_i_raw["converged"]:
        raise RuntimeError("cyanobenzene GL-I state did not converge")
    raw_states["GL_I"] = gl_i_raw
    gl_i_density = np.asarray(gl_i_raw["density"], dtype=float)
    for state_name in ("GE1", "GE2", "GE3"):
        raw_states[state_name] = conditional_state(
            state_atoms[state_name], fragment_maps[state_name], gl_i_density, protocol,
            mask_one_electron_matrix=mask_one_electron_matrix,
        )
        if not raw_states[state_name]["converged"]:
            raise RuntimeError(f"cyanobenzene {state_name} state did not converge")

    gl_ii_raw = conditional_state(
        state_atoms["GL_II"], fragment_maps["GL_II"], g_density, protocol,
        mask_one_electron_matrix=mask_one_electron_matrix,
    )
    if not gl_ii_raw["converged"]:
        raise RuntimeError("cyanobenzene GL-II state did not converge")
    raw_states["GL_II"] = gl_ii_raw
    gl_ii_density = np.asarray(gl_ii_raw["density"], dtype=float)
    for state_name in ("GE4", "GE5", "GE6", "GE7"):
        raw_states[state_name] = conditional_state(
            state_atoms[state_name], fragment_maps[state_name], gl_ii_density, protocol,
            mask_one_electron_matrix=mask_one_electron_matrix,
        )
        if not raw_states[state_name]["converged"]:
            raise RuntimeError(f"cyanobenzene {state_name} state did not converge")

    states = {name: compact_state(value) for name, value in raw_states.items()}
    energies = {"G": float(g_state["total_energy_hartree"])}
    energies.update({name: float(value["total_energy_hartree"]) for name, value in states.items()})

    delta_ea = energies["G"] - energies["GL_I"]
    sb_increments = {name: energies[name] - energies["GL_I"] for name in ("GE1", "GE2", "GE3")}
    ese_sb = delta_ea - sum(sb_increments.values())
    ph_increments = {name: energies[name] - energies["GL_II"] for name in ("GE4", "GE5", "GE6", "GE7")}
    ese_ph = ph_increments["GE7"] - sum(ph_increments[name] for name in ("GE4", "GE5", "GE6"))
    conjugative_effect = ese_sb - ese_ph

    tolerance = protocol["acceptance"]
    direction = float(tolerance["strict_direction_tolerance_hartree"])
    checks: dict[str, bool] = {
        "G_SCF_converged": bool(g_state["converged"]),
        "all_geometry_solvers_succeeded": all(
            bool(record["solver_success"]) for record in geometry_records.values()
        ),
        "all_ring_bonds_reconstructed": max(
            float(record["maximum_ring_bond_error_angstrom"])
            for record in geometry_records.values()
        )
        <= float(geometry_options["ring_bond_fit_tolerance_angstrom"]),
    }
    for name, state in states.items():
        checks.update(conditional_checks(name, state, protocol))
    checks.update(
        {
            "delta_EA_negative": delta_ea < -direction,
            "all_SB_local_increments_positive": all(value > direction for value in sb_increments.values()),
            "ESE_SB_negative": ese_sb < -direction,
            "GE4_GE5_GE6_positive": all(ph_increments[name] > direction for name in ("GE4", "GE5", "GE6")),
            "delta_EA7_negative": ph_increments["GE7"] < -direction,
            "ESE_Ph_negative": ese_ph < -direction,
            "conjugative_effect_positive": conjugative_effect > direction,
            "ESE_SB_identity_closed": abs(
                ese_sb - (energies["G"] - (energies["GL_I"] + sum(sb_increments.values())))
            )
            <= float(tolerance["energy_identity_hartree"]),
            "ESE_Ph_identity_closed": abs(
                ese_ph
                - (
                    energies["GE7"]
                    - (
                        energies["GL_II"]
                        + sum(ph_increments[name] for name in ("GE4", "GE5", "GE6"))
                    )
                )
            )
            <= float(tolerance["energy_identity_hartree"]),
        }
    )

    record = {
        "schema_version": 1,
        "protocol_id": protocol["protocol_id"],
        "proposition_id": "P11",
        "subtarget": "P11-B_substituent_effect_separation",
        "stage": "cyanobenzene_figure7_source_geometry_energy_reconstruction",
        "geometry_disposition": protocol["system"]["geometry_role"],
        "implementation_semantics": protocol["state_contract"]["implementation_semantics"],
        "one_electron_matrix_masked": bool(mask_one_electron_matrix),
        "geometries": geometry_records,
        "G_state": g_state,
        "conditional_states": states,
        "energies_hartree": energies,
        "delta_EA_hartree": delta_ea,
        "delta_EA_kcal_mol": delta_ea * HARTREE_TO_KCAL_PER_MOL,
        "SB_local_increments_hartree": sb_increments,
        "SB_local_increments_kcal_mol": {
            name: value * HARTREE_TO_KCAL_PER_MOL for name, value in sb_increments.items()
        },
        "ESE_SB_hartree": ese_sb,
        "ESE_SB_kcal_mol": ese_sb * HARTREE_TO_KCAL_PER_MOL,
        "Ph_increments_hartree": ph_increments,
        "Ph_increments_kcal_mol": {
            name: value * HARTREE_TO_KCAL_PER_MOL for name, value in ph_increments.items()
        },
        "ESE_Ph_hartree": ese_ph,
        "ESE_Ph_kcal_mol": ese_ph * HARTREE_TO_KCAL_PER_MOL,
        "conjugative_effect_hartree": conjugative_effect,
        "conjugative_effect_kcal_mol": conjugative_effect * HARTREE_TO_KCAL_PER_MOL,
        "inductive_effect_status": "sealed_pending_same_2007_source_benzene_anchor_validator",
        "source_value_comparison_status": "sealed_pending_post_calculation_validator",
        "acceptance_checks": checks,
        "calculation_gate_verdict": "PASS" if all(checks.values()) else "FAIL",
        "production_label": False,
        "training_eligible": False,
        "universal_substituent_law": False,
    }
    return record


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
                "ESE_SB_kcal_mol": record["ESE_SB_kcal_mol"],
                "ESE_Ph_kcal_mol": record["ESE_Ph_kcal_mol"],
                "conjugative_effect_kcal_mol": record["conjugative_effect_kcal_mol"],
                "output": str(arguments.output.resolve()),
                "report": str(arguments.report.resolve()),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0 if record["calculation_gate_verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
