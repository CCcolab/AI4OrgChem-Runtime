"""Run the bounded P10 benzene nuclear-repulsion decomposition and BLA scan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = ROOT / "configs/qm/p10_benzene_nuclear_repulsion_v0.1.yaml"
DEFAULT_OUTPUT = ROOT / "data/processed/p10_benzene_nuclear_repulsion_v0.1.json"
DEFAULT_REPORT = ROOT / "docs/reports/p10_benzene_nuclear_repulsion_2026-08-21.md"
# Keep the independent Coulomb sum on the same CODATA conversion used by PySCF.
# The prior trailing-digit mismatch produced a uniform ~6.5e-9 Eh offset at the
# benzene nuclear-energy scale and was unrelated to the scientific decomposition.
ANGSTROM_PER_BOHR = 0.52917721092
HARTREE_TO_KCAL_PER_MOL = 627.5094740631
ATOMIC_NUMBERS = {"H": 1, "C": 6}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def nuclear_repulsion(atoms: list[list[Any]]) -> float:
    xyz_bohr = np.asarray([row[1:4] for row in atoms], dtype=float) / ANGSTROM_PER_BOHR
    charges = np.asarray([ATOMIC_NUMBERS[str(row[0])] for row in atoms], dtype=float)
    energy = 0.0
    for first in range(len(atoms)):
        for second in range(first):
            distance = float(np.linalg.norm(xyz_bohr[first] - xyz_bohr[second]))
            energy += float(charges[first] * charges[second] / distance)
    return energy


def mean_ch_length(atoms: list[list[Any]]) -> float:
    xyz = np.asarray([row[1:4] for row in atoms], dtype=float)
    return float(np.mean(np.linalg.norm(xyz[6:12] - xyz[0:6], axis=1)))


def mean_ring_cc_length(atoms: list[list[Any]]) -> float:
    xyz = np.asarray([row[1:4] for row in atoms[:6]], dtype=float)
    return float(
        np.mean(
            [np.linalg.norm(xyz[index] - xyz[(index + 1) % 6]) for index in range(6)]
        )
    )


def d3h_atoms(mean_cc: float, delta: float, ch_length: float) -> list[list[Any]]:
    edge_lengths = [mean_cc - delta, mean_cc + delta] * 3
    edge_angles = np.deg2rad([120.0, 180.0, 240.0, 300.0, 0.0, 60.0])
    carbons = np.zeros((6, 2), dtype=float)
    for index in range(5):
        carbons[index + 1] = carbons[index] + edge_lengths[index] * np.asarray(
            [np.cos(edge_angles[index]), np.sin(edge_angles[index])]
        )
    closure = carbons[5] + edge_lengths[5] * np.asarray(
        [np.cos(edge_angles[5]), np.sin(edge_angles[5])]
    )
    if float(np.linalg.norm(closure - carbons[0])) > 1.0e-10:
        raise ValueError("alternating D3h hexagon did not close")
    carbons -= np.mean(carbons, axis=0)
    radial = carbons / np.linalg.norm(carbons, axis=1)[:, None]
    hydrogens = carbons + ch_length * radial
    return [
        *[["C", float(x), float(y), 0.0] for x, y in carbons],
        *[["H", float(x), float(y), 0.0] for x, y in hydrogens],
    ]


def ordinary_rks(atoms: list[list[Any]], protocol: dict[str, Any]) -> dict[str, Any]:
    from pyscf import dft, gto

    scan = protocol["physical_scan"]
    molecule = gto.M(
        atom=atoms,
        basis=str(scan["basis"]),
        charge=int(scan["charge"]),
        spin=int(scan["multiplicity"]) - 1,
        unit="Angstrom",
        symmetry=False,
        verbose=0,
    )
    mean_field = dft.RKS(molecule)
    mean_field.verbose = 0
    mean_field.xc = str(scan["pyscf_xc"])
    mean_field.grids.level = int(scan["grid_level"])
    mean_field.conv_tol = float(scan["scf_tolerance_hartree"])
    mean_field.max_cycle = int(scan["maximum_scf_cycles"])
    mean_field.max_memory = int(scan["maximum_memory_mb"])
    total = float(mean_field.kernel())
    nuclear_pyscf = float(molecule.energy_nuc())
    return {
        "converged": bool(mean_field.converged),
        "total_energy_hartree": total,
        "electronic_energy_hartree": total - nuclear_pyscf,
        "nuclear_repulsion_hartree_pyscf": nuclear_pyscf,
        "scf_cycles": len(mean_field.scf_summary) if hasattr(mean_field, "scf_summary") else None,
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def render_report(record: dict[str, Any]) -> str:
    endpoint = record["source_aligned_endpoint_decomposition"]
    curvature = record["ordinary_RKS_BLA_scan"]["quadratic_curvatures_hartree_per_angstrom2"]
    lines = [
        "# P10 苯D6h与核排斥最小化计算报告",
        "",
        f"- 协议：`{record['protocol_id']}`",
        f"- 计算门禁：`{record['calculation_gate_verdict']}`",
        "- 范围：单一苯G/GL端点与固定平均键长的D3h键长交替坐标。",
        "",
        "## G/GL端点分解",
        "",
        "| 分量 | Eh | kcal/mol | 原著方向 |",
        "|---|---:|---:|---|",
        f"| ΔEe | {endpoint['delta_electronic_hartree']:+.12f} | {endpoint['delta_electronic_kcal_mol']:+.6f} | `>0` |",
        f"| ΔEN | {endpoint['delta_nuclear_hartree']:+.12f} | {endpoint['delta_nuclear_kcal_mol']:+.6f} | `<0` |",
        f"| ΔE | {endpoint['delta_total_hartree']:+.12f} | {endpoint['delta_total_kcal_mol']:+.6f} | `<0` |",
        "",
        "## 普通RKS键长交替扫描",
        "",
        "| δ (Å) | ΔEe (kcal/mol) | ΔEN (kcal/mol) | ΔE (kcal/mol) |",
        "|---:|---:|---:|---:|",
    ]
    for row in record["ordinary_RKS_BLA_scan"]["points"]:
        lines.append(
            f"| {row['delta_angstrom']:.3f} | {row['delta_electronic_kcal_mol']:+.6f} | "
            f"{row['delta_nuclear_kcal_mol']:+.6f} | {row['delta_total_kcal_mol']:+.6f} |"
        )
    lines.extend(
        [
            "",
            "二阶曲率（Eh/Å²）：",
            "",
            f"- 电子：`{curvature['electronic']:+.9f}`；核排斥：`{curvature['nuclear']:+.9f}`；总能量：`{curvature['total']:+.9f}`。",
            "",
            "## 验收",
            "",
            "| 检查项 | 结果 |",
            "|---|---|",
        ]
    )
    for name, passed in record["acceptance_checks"].items():
        lines.append(f"| `{name}` | `{'PASS' if passed else 'FAIL'}` |")
    lines.extend(
        [
            "",
            "该结果只判定冻结键长交替坐标上的能量因果关系，不宣称核排斥脱离电子结构而独立产生D6h几何。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    protocol_path = args.protocol.resolve()
    output_path = args.output.resolve()
    report_path = args.report.resolve()
    protocol = yaml.safe_load(protocol_path.read_text(encoding="utf-8"))
    if protocol["execution"]["scope"] != "single_benzene_endpoint_decomposition_and_five_point_BLA_scan_only":
        raise RuntimeError("P10 execution scope is not the frozen single-benzene path")

    g_path = ROOT / protocol["p09_frozen_inputs"]["G"]
    gl_path = ROOT / protocol["p09_frozen_inputs"]["GL"]
    g_record = load_json(g_path)
    gl_record = load_json(gl_path)
    if g_record["protocol_id"] != gl_record["protocol_id"]:
        raise RuntimeError("P09 G and GL evidence do not share one protocol")

    g_atoms = g_record["optimized_G_geometry"]["atoms_angstrom"]
    g_total = float(g_record["ordinary_G_state"]["total_energy_hartree"])
    g_nuclear = nuclear_repulsion(g_atoms)
    g_electronic = g_total - g_nuclear
    gl_state = gl_record["GL_state"]
    gl_total = float(gl_state["total_energy_hartree"])
    gl_nuclear = float(gl_state["nuclear_repulsion_hartree"])
    gl_electronic = float(gl_state["electronic_energy_hartree"])
    delta_electronic = g_electronic - gl_electronic
    delta_nuclear = g_nuclear - gl_nuclear
    delta_total = g_total - gl_total
    endpoint_closure = delta_total - delta_electronic - delta_nuclear

    mean_cc = mean_ring_cc_length(g_atoms)
    ch_length = mean_ch_length(g_atoms)
    points: list[dict[str, Any]] = []
    for delta in [float(value) for value in protocol["physical_scan"]["delta_angstrom"]]:
        atoms = d3h_atoms(mean_cc, delta, ch_length)
        state = ordinary_rks(atoms, protocol)
        nuclear_formula = nuclear_repulsion(atoms)
        row = {
            "delta_angstrom": delta,
            "ra_angstrom": mean_cc - delta,
            "rb_angstrom": mean_cc + delta,
            **state,
            "nuclear_repulsion_hartree_formula": nuclear_formula,
            "nuclear_formula_minus_pyscf_hartree": nuclear_formula
            - float(state["nuclear_repulsion_hartree_pyscf"]),
        }
        points.append(row)
        print(json.dumps({"stage": "P10_BLA", **row}, ensure_ascii=False), flush=True)

    anchor = points[0]
    for row in points:
        row["delta_total_hartree"] = float(row["total_energy_hartree"]) - float(
            anchor["total_energy_hartree"]
        )
        row["delta_electronic_hartree"] = float(row["electronic_energy_hartree"]) - float(
            anchor["electronic_energy_hartree"]
        )
        row["delta_nuclear_hartree"] = float(
            row["nuclear_repulsion_hartree_formula"]
        ) - float(anchor["nuclear_repulsion_hartree_formula"])
        for component in ("total", "electronic", "nuclear"):
            row[f"delta_{component}_kcal_mol"] = (
                float(row[f"delta_{component}_hartree"]) * HARTREE_TO_KCAL_PER_MOL
            )

    x = np.square(np.asarray([row["delta_angstrom"] for row in points], dtype=float))
    curvatures: dict[str, float] = {}
    for component in ("electronic", "nuclear", "total"):
        y = np.asarray([row[f"delta_{component}_hartree"] for row in points], dtype=float)
        slope = float(np.polyfit(x, y, 1)[0])
        curvatures[component] = 2.0 * slope

    nuclear_symmetry_errors = []
    for delta in [float(value) for value in protocol["physical_scan"]["delta_angstrom"] if float(value) > 0.0]:
        plus = nuclear_repulsion(d3h_atoms(mean_cc, delta, ch_length))
        minus = nuclear_repulsion(d3h_atoms(mean_cc, -delta, ch_length))
        nuclear_symmetry_errors.append(abs(plus - minus))

    tolerance = protocol["acceptance"]
    direction_tol = float(tolerance["strict_direction_tolerance_hartree"])
    distorted = points[1:]
    checks = {
        "p09_G_gate_passed": g_record["smoke_gate_verdict"] == "PASS",
        "p09_GL_gate_passed": gl_record["calculation_gate_verdict"] == "PASS",
        "endpoint_energy_identity_closed": abs(endpoint_closure)
        <= float(tolerance["energy_identity_hartree"]),
        "endpoint_delta_Ee_positive": delta_electronic > direction_tol,
        "endpoint_delta_EN_negative": delta_nuclear < -direction_tol,
        "endpoint_nuclear_change_predominates": abs(delta_nuclear)
        > delta_electronic,
        "all_scan_SCF_converged": all(bool(row["converged"]) for row in points),
        "delta_zero_matches_p09_G": abs(float(anchor["total_energy_hartree"]) - g_total)
        <= float(tolerance["g_anchor_energy_hartree"]),
        "independent_nuclear_formula_matches_pyscf": max(
            abs(float(row["nuclear_formula_minus_pyscf_hartree"])) for row in points
        )
        <= float(tolerance["nuclear_formula_hartree"]),
        "nuclear_energy_minimum_at_equal_bonds": all(
            float(row["delta_nuclear_hartree"]) > direction_tol for row in distorted
        ),
        "ordinary_electronic_energy_favors_BLA": all(
            float(row["delta_electronic_hartree"]) < -direction_tol for row in distorted
        ),
        "nuclear_penalty_exceeds_electronic_lowering": all(
            float(row["delta_nuclear_hartree"])
            > abs(float(row["delta_electronic_hartree"]))
            for row in distorted
        ),
        "ordinary_total_energy_minimum_at_equal_bonds": all(
            float(row["delta_total_hartree"]) > direction_tol for row in distorted
        ),
        "electronic_curvature_negative": curvatures["electronic"] < 0.0,
        "nuclear_curvature_positive": curvatures["nuclear"] > 0.0,
        "total_curvature_positive": curvatures["total"] > 0.0,
        "nuclear_path_even_in_delta": max(nuclear_symmetry_errors, default=0.0)
        <= float(tolerance["nuclear_symmetry_hartree"]),
    }
    verdict = "PASS" if all(checks.values()) else "FAIL"
    record = {
        "schema_version": 1,
        "protocol_id": protocol["protocol_id"],
        "proposition_id": "P10",
        "stage": "benzene_D6h_nuclear_repulsion_decomposition",
        "source_aligned_endpoint_decomposition": {
            "G_total_energy_hartree": g_total,
            "G_electronic_energy_hartree": g_electronic,
            "G_nuclear_repulsion_hartree": g_nuclear,
            "GL_total_energy_hartree": gl_total,
            "GL_electronic_energy_hartree": gl_electronic,
            "GL_nuclear_repulsion_hartree": gl_nuclear,
            "delta_electronic_hartree": delta_electronic,
            "delta_electronic_kcal_mol": delta_electronic * HARTREE_TO_KCAL_PER_MOL,
            "delta_nuclear_hartree": delta_nuclear,
            "delta_nuclear_kcal_mol": delta_nuclear * HARTREE_TO_KCAL_PER_MOL,
            "delta_total_hartree": delta_total,
            "delta_total_kcal_mol": delta_total * HARTREE_TO_KCAL_PER_MOL,
            "identity_residual_hartree": endpoint_closure,
        },
        "ordinary_RKS_BLA_scan": {
            "mean_CC_angstrom": mean_cc,
            "fixed_CH_angstrom": ch_length,
            "points": points,
            "quadratic_curvatures_hartree_per_angstrom2": curvatures,
            "maximum_nuclear_plus_minus_symmetry_error_hartree": max(
                nuclear_symmetry_errors, default=0.0
            ),
        },
        "acceptance_checks": checks,
        "calculation_gate_verdict": verdict,
        "scientific_interpretation_status": "pending_final_validator",
        "production_label": False,
        "training_eligible": False,
        "universal_benzene_symmetry_law": False,
    }
    write_json(output_path, record)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(record), encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": verdict,
                "delta_Ee_kcal_mol": endpoint["delta_electronic_kcal_mol"]
                if (endpoint := record["source_aligned_endpoint_decomposition"])
                else None,
                "delta_EN_kcal_mol": endpoint["delta_nuclear_kcal_mol"],
                "delta_E_kcal_mol": endpoint["delta_total_kcal_mol"],
                "curvatures_hartree_per_angstrom2": curvatures,
                "output": str(output_path),
                "report": str(report_path),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
