"""Run the authorized P09 fixed-geometry cyclobutadiene G/DSI smoke."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from ai4orgchem.qm.p09_ao_classification import classify_planar_pyscf_aos
from ai4orgchem.qm.p09_conditional_scf import run_p09_conditional_rks


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = ROOT / "configs/qm/p09_benzene_cyclobutadiene_v0.1.yaml"
DEFAULT_CLASSES = ROOT / "configs/qm/p09_exchange_integral_classes_v0.1.yaml"
DEFAULT_OUTPUT = ROOT / "data/processed/p09_cyclobutadiene_fixed_geometry_smoke_v0.1.json"
DEFAULT_REPORT = ROOT / "docs/reports/p09_cyclobutadiene_fixed_geometry_smoke_2026-08-21.md"
HARTREE_TO_KCAL_PER_MOL = 627.5094740631


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def build_molecule(config: dict[str, Any]) -> Any:
    from pyscf import gto

    atoms = [[row[0], *[float(value) for value in row[1:4]]] for row in config["smoke_gate"]["initial_atoms"]]
    electronic = config["electronic_structure"]
    return gto.M(
        atom=atoms,
        basis=str(electronic["basis"]),
        charge=int(electronic["charge"]),
        spin=int(electronic["multiplicity"]) - 1,
        unit="Angstrom",
        symmetry=False,
        verbose=0,
    )


def build_mean_field(molecule: Any, config: dict[str, Any]) -> Any:
    from pyscf import dft

    electronic = config["electronic_structure"]
    mean_field = dft.RKS(molecule)
    mean_field.verbose = 0
    mean_field.xc = str(electronic["pyscf_xc"])
    mean_field.grids.level = int(electronic["grid_level"])
    mean_field.conv_tol = float(electronic["scf_tolerance_hartree"])
    mean_field.max_cycle = int(electronic["max_scf_cycles"])
    mean_field.max_memory = int(config["smoke_gate"]["maximum_memory_mb"])
    return mean_field


def geometry_hash(molecule: Any) -> str:
    payload = [
        [
            molecule.atom_symbol(index),
            *np.asarray(molecule.atom_coord(index, unit="Angstrom"), dtype=float).tolist(),
        ]
        for index in range(molecule.natm)
    ]
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest().upper()


def ordinary_state(mean_field: Any) -> tuple[dict[str, Any], np.ndarray]:
    energy = float(mean_field.kernel())
    density = np.asarray(mean_field.make_rdm1(), dtype=float)
    stability: dict[str, Any]
    try:
        _internal_orbitals, _external_orbitals, internally_stable, _externally_stable = mean_field.stability(
            internal=True, external=False, verbose=0, return_status=True
        )
        stability = {
            "internal_stability_checked": True,
            "internally_stable": bool(internally_stable),
            "error": None,
        }
    except Exception as error:  # pragma: no cover - backend diagnostic path
        stability = {
            "internal_stability_checked": False,
            "internally_stable": None,
            "error": f"{type(error).__name__}: {error}",
        }
    overlap = np.asarray(mean_field.get_ovlp(), dtype=float)
    occupations = np.asarray(mean_field.mo_occ, dtype=float)
    occupied = np.flatnonzero(occupations > 0.0)
    virtual = np.flatnonzero(occupations == 0.0)
    return {
        "converged": bool(mean_field.converged),
        "cycles": int(getattr(mean_field, "cycles", 0)),
        "total_energy_hartree": energy,
        "nuclear_repulsion_hartree": float(mean_field.mol.energy_nuc()),
        "physical_metric_electron_count": float(
            np.einsum("pq,qp->", overlap, density, optimize=True)
        ),
        "occupied_orbital_count": int(occupied.size),
        "singly_occupied_orbital_count": int(np.count_nonzero(occupations == 1.0)),
        "occupied_virtual_gap_hartree": float(
            np.min(mean_field.mo_energy[virtual]) - np.max(mean_field.mo_energy[occupied])
        ),
        "stability": stability,
    }, density


def compact_conditional(result: dict[str, Any]) -> dict[str, Any]:
    excluded = {"density", "mo_coefficients", "mo_energies_hartree", "mo_occupations"}
    return {key: value for key, value in result.items() if key not in excluded}


def render_report(record: dict[str, Any]) -> str:
    ordinary = record["ordinary_G_like_state"]
    dsi = record["conditional_DSI_state"]
    checks = record["acceptance_checks"]
    lines = [
        "# P09 环丁二烯固定几何 G/DSI 烟雾计算",
        "",
        f"- 协议：`{record['protocol_id']}`",
        f"- 几何 SHA-256：`{record['geometry_sha256']}`",
        "- 方法：`B3LYPG/6-31G(d)`；固定平面矩形起始几何；无几何优化、无数值拟合。",
        f"- 普通 G-like 状态：`{ordinary['total_energy_hartree']:.12f} Eh`，SCF `{'收敛' if ordinary['converged'] else '未收敛'}`。",
        f"- 条件 DSI 状态：`{dsi['total_energy_hartree']:.12f} Eh`，SCF `{'收敛' if dsi['converged'] else '未收敛'}`，{dsi['cycles']} cycles。",
        f"- 固定几何诊断差 E(G-like)-E(DSI)：`{record['fixed_geometry_diagnostic_difference_hartree']:.12f} Eh` / `{record['fixed_geometry_diagnostic_difference_kcal_mol']:.6f} kcal/mol`。",
        "",
        "## 条件态数值账本",
        "",
        "| 量 | 数值 |",
        "|---|---:|",
        f"| 屏蔽度量电子数 | {dsi['masked_metric_electron_count']:.12f} |",
        f"| 物理度量电子数 | {dsi['physical_metric_electron_count']:.12f} |",
        f"| 数值积分电子数 | {dsi['grid_electron_count']:.12f} |",
        f"| 删除 ERI 数 / 总数 | {dsi['deleted_eri_count']} / {dsi['total_eri_count']} |",
        f"| 删除 ERI 比例 | {dsi['deleted_eri_fraction']:.8f} |",
        f"| S 跨片段 π 块最大绝对值 | {dsi['masked_overlap_cross_pi_max_abs']:.3e} |",
        f"| F 跨片段 π 块最大绝对值 | {dsi['conditional_fock_cross_pi_max_abs']:.3e} |",
        f"| 能量分量闭合残差 (Eh) | {dsi['energy_component_closure_residual_hartree']:.3e} |",
        f"| 最终广义对易子 Frobenius 范数 | {dsi['final_commutator_frobenius_norm']:.3e} |",
        f"| 闭壳层幂等残差 | {dsi['closed_shell_idempotency_relative_residual']:.3e} |",
        f"| 条件占据-空轨道能隙 (Eh) | {dsi['occupied_virtual_gap_hartree']:.8f} |",
        "",
        "## 验收",
        "",
        "| 检查项 | 结果 |",
        "|---|---|",
    ]
    for key, value in checks.items():
        lines.append(f"| `{key}` | `{'PASS' if value else 'FAIL'}` |")
    lines.extend(
        [
            "",
            f"烟雾门禁总结果：`{record['smoke_gate_verdict']}`。",
            "",
            "该结果只验证同一固定几何上普通态与源定义条件态能够独立执行并形成闭合账本；它不是环丁二烯最终 VDE/ADE，也不启用稳定化/去稳定化生产标签。",
            "",
        ]
    )
    return "\n".join(lines)


def run(protocol_path: Path, classes_path: Path) -> dict[str, Any]:
    protocol = load_yaml(protocol_path)
    classes = load_yaml(classes_path)
    if protocol["p09_qm_execution_scope"] != "fixed_geometry_no_fit_G_DSI_smoke_only":
        raise RuntimeError("P09 protocol does not authorize this smoke scope")
    if protocol["p09_geometry_optimization_allowed"]:
        raise RuntimeError("P09 smoke must not authorize geometry optimization")

    molecule = build_molecule(protocol)
    mean_field = build_mean_field(molecule, protocol)
    ordinary, ordinary_density = ordinary_state(mean_field)
    if not ordinary["converged"]:
        raise RuntimeError("ordinary fixed-geometry RKS did not converge")

    descriptors = classify_planar_pyscf_aos(
        molecule,
        {0: "A", 1: "A", 2: "B", 3: "B"},
    )
    conditional_options = protocol["smoke_gate"]["conditional_scf"]
    conditional_raw = run_p09_conditional_rks(
        mean_field,
        descriptors,
        classes["exchange_integral_classes"],
        initial_density=ordinary_density,
        maximum_cycles=int(conditional_options["maximum_cycles"]),
        density_tolerance=float(conditional_options["density_tolerance"]),
        energy_tolerance=float(conditional_options["energy_tolerance_hartree"]),
        diis_start_cycle=int(conditional_options["diis_start_cycle"]),
        diis_space=int(conditional_options["diis_space"]),
        damping_cycles=int(conditional_options["damping_cycles"]),
        damping=float(conditional_options["damping"]),
    )
    conditional = compact_conditional(conditional_raw)
    tolerance = protocol["smoke_gate"]["acceptance"]
    expected_electrons = int(molecule.nelectron)
    checks = {
        "ordinary_scf_converged": bool(ordinary["converged"]),
        "conditional_scf_converged": bool(conditional["converged"]),
        "neutral_singlet_and_electron_count": molecule.charge == 0
        and molecule.spin == 0
        and expected_electrons == 28,
        "ordinary_physical_metric_electron_count": abs(
            float(ordinary["physical_metric_electron_count"]) - expected_electrons
        )
        <= float(tolerance["electron_count_tolerance"]),
        "conditional_masked_metric_electron_count": abs(
            float(conditional["masked_metric_electron_count"]) - expected_electrons
        )
        <= float(tolerance["electron_count_tolerance"]),
        "cross_fragment_pi_overlap_zero": float(
            conditional["masked_overlap_cross_pi_max_abs"]
        )
        <= float(tolerance["matrix_zero_tolerance"]),
        "cross_fragment_pi_fock_zero": float(
            conditional["conditional_fock_cross_pi_max_abs"]
        )
        <= float(tolerance["matrix_zero_tolerance"]),
        "fifteen_class_eri_mask_applied": len(classes["exchange_integral_classes"]) == 15
        and int(conditional["deleted_eri_count"]) > 0,
        "independent_energy_components_close": float(
            conditional["energy_component_closure_residual_hartree"]
        )
        <= float(tolerance["energy_component_closure_hartree"]),
        "conditional_commutator_closed": float(
            conditional["final_commutator_frobenius_norm"]
        )
        <= float(tolerance["commutator_frobenius_tolerance"]),
        "conditional_density_idempotent": float(
            conditional["closed_shell_idempotency_relative_residual"]
        )
        <= float(tolerance["idempotency_relative_tolerance"]),
        "wavefunction_stability_reported": ordinary["stability"]["internal_stability_checked"]
        and np.isfinite(float(conditional["occupied_virtual_gap_hartree"])),
    }
    checks = {key: bool(value) for key, value in checks.items()}
    difference = float(ordinary["total_energy_hartree"]) - float(
        conditional["total_energy_hartree"]
    )
    return {
        "schema_version": 1,
        "protocol_id": protocol["protocol_id"],
        "proposition_id": "P09",
        "stage": "fixed_geometry_no_fit_G_DSI_smoke",
        "geometry_role": "source_aligned_planar_rectangular_start_not_historical_cartesian",
        "geometry_sha256": geometry_hash(molecule),
        "geometry_atoms_angstrom": protocol["smoke_gate"]["initial_atoms"],
        "method": {
            "engine": "PySCF",
            "pyscf_xc": protocol["electronic_structure"]["pyscf_xc"],
            "basis": protocol["electronic_structure"]["basis"],
            "grid_level": protocol["electronic_structure"]["grid_level"],
            "original_program_code_used": False,
            "fit_to_blind_values": False,
        },
        "ao_counts": {
            "total": len(descriptors),
            "sigma": sum(item.kind == "sigma" for item in descriptors),
            "pi": sum(item.kind == "pi" for item in descriptors),
            "pi_fragment_A": sum(
                item.kind == "pi" and item.fragment == "A" for item in descriptors
            ),
            "pi_fragment_B": sum(
                item.kind == "pi" and item.fragment == "B" for item in descriptors
            ),
        },
        "ordinary_G_like_state": ordinary,
        "conditional_DSI_state": conditional,
        "fixed_geometry_diagnostic_difference_hartree": difference,
        "fixed_geometry_diagnostic_difference_kcal_mol": difference
        * HARTREE_TO_KCAL_PER_MOL,
        "acceptance_checks": checks,
        "smoke_gate_verdict": "PASS" if all(checks.values()) else "FAIL",
        "scientific_label_status": "disabled_smoke_only",
        "production_labels_allowed": False,
        "ai_training_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--classes", type=Path, default=DEFAULT_CLASSES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    arguments = parser.parse_args()

    record = run(arguments.protocol, arguments.classes)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(render_report(record), encoding="utf-8")
    print(json.dumps({
        "verdict": record["smoke_gate_verdict"],
        "ordinary_energy_hartree": record["ordinary_G_like_state"]["total_energy_hartree"],
        "conditional_energy_hartree": record["conditional_DSI_state"]["total_energy_hartree"],
        "diagnostic_difference_kcal_mol": record["fixed_geometry_diagnostic_difference_kcal_mol"],
        "output": str(arguments.output),
        "report": str(arguments.report),
    }, ensure_ascii=False))
    return 0 if record["smoke_gate_verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
