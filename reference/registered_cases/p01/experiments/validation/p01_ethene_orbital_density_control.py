"""P01 actual-QM control: orbital localization may change without changing the state.

The calculation is intentionally bounded to one ethene RHF/6-31G(d) wavefunction.
Canonical, Boys, and Pipek-Mezey occupied orbitals are compared as gauges of the
same occupied subspace.  No stabilization/destabilization label is produced.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from pyscf import gto, lib, lo, scf


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs/qm/p01_ethene_orbital_density_control_v0.1.yaml"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def symmetric_matrix_power(matrix: np.ndarray, power: float) -> np.ndarray:
    eigenvalues, eigenvectors = np.linalg.eigh(matrix)
    if float(np.min(eigenvalues)) <= 0.0:
        raise ValueError("AO overlap matrix is not positive definite")
    return (eigenvectors * np.power(eigenvalues, power)) @ eigenvectors.T


def atom_ao_indices(mol: gto.Mole, atom_ids: list[int]) -> np.ndarray:
    slices = mol.aoslice_by_atom()
    blocks = [np.arange(int(slices[index, 2]), int(slices[index, 3])) for index in atom_ids]
    return np.concatenate(blocks)


def binary_entropy(weights: np.ndarray) -> float:
    positive = weights[weights > 1.0e-15]
    return float(-np.sum(positive * np.log2(positive)))


def representation_diagnostics(
    name: str,
    coefficients: np.ndarray,
    canonical_occupied: np.ndarray,
    overlap: np.ndarray,
    overlap_half: np.ndarray,
    group_indices: dict[str, np.ndarray],
    reference_density: np.ndarray,
    reference_energy: float,
    reference_electrons: float,
    mean_field: scf.hf.RHF,
) -> dict[str, Any]:
    metric_rotation = canonical_occupied.T @ overlap @ coefficients
    unitary_residual = float(
        np.linalg.norm(metric_rotation.T @ metric_rotation - np.eye(coefficients.shape[1]), ord="fro")
    )
    density = 2.0 * coefficients @ coefficients.T
    density_residual = float(np.linalg.norm(density - reference_density, ord="fro"))
    density_relative_residual = density_residual / float(np.linalg.norm(reference_density, ord="fro"))
    electron_number = float(np.einsum("ij,ji->", density, overlap))
    total_energy = float(mean_field.energy_tot(dm=density))

    lowdin_coefficients = overlap_half @ coefficients
    orbital_support: list[dict[str, Any]] = []
    entropies: list[float] = []
    for orbital_index in range(coefficients.shape[1]):
        vector = lowdin_coefficients[:, orbital_index]
        weights = np.array(
            [float(np.sum(np.square(vector[group_indices[group]]))) for group in ("left_ch2", "right_ch2")]
        )
        weights /= float(np.sum(weights))
        entropy = binary_entropy(weights)
        entropies.append(entropy)
        orbital_support.append(
            {
                "occupied_orbital_index": orbital_index,
                "left_ch2_weight": float(weights[0]),
                "right_ch2_weight": float(weights[1]),
                "binary_support_entropy": entropy,
            }
        )

    return {
        "name": name,
        "occupied_orbital_count": int(coefficients.shape[1]),
        "occupied_subspace_unitarity_residual": unitary_residual,
        "density_frobenius_residual_from_canonical": density_residual,
        "density_relative_frobenius_residual_from_canonical": density_relative_residual,
        "electron_number": electron_number,
        "electron_number_residual_from_canonical": abs(electron_number - reference_electrons),
        "rhf_total_energy_hartree": total_energy,
        "energy_residual_from_canonical_hartree": abs(total_energy - reference_energy),
        "mean_binary_support_entropy": float(np.mean(entropies)),
        "minimum_binary_support_entropy": float(np.min(entropies)),
        "maximum_binary_support_entropy": float(np.max(entropies)),
        "orbital_support": orbital_support,
    }


def build_molecule(config: dict[str, Any]) -> gto.Mole:
    system = config["system"]
    qc = config["quantum_chemistry"]
    atom = [(row[0], tuple(float(value) for value in row[1:])) for row in system["geometry"]]
    return gto.M(
        atom=atom,
        unit=system["unit"],
        charge=int(system["charge"]),
        spin=int(system["spin"]),
        basis=qc["basis"],
        symmetry=bool(qc["symmetry"]),
        verbose=0,
    )


def collect(config: dict[str, Any]) -> dict[str, Any]:
    qc = config["quantum_chemistry"]
    lib.num_threads(int(qc["threads"]))
    mol = build_molecule(config)
    mean_field = scf.RHF(mol)
    mean_field.conv_tol = float(qc["scf_conv_tol"])
    mean_field.max_cycle = int(qc["scf_max_cycle"])
    canonical_energy = float(mean_field.kernel())
    if not mean_field.converged:
        raise RuntimeError("Ethene RHF calculation did not converge")

    occupied = mean_field.mo_coeff[:, mean_field.mo_occ > 0.0]
    overlap = mean_field.get_ovlp()
    overlap_half = symmetric_matrix_power(overlap, 0.5)
    reference_density = 2.0 * occupied @ occupied.T
    reference_electrons = float(np.einsum("ij,ji->", reference_density, overlap))

    boys_solver = lo.Boys(mol, occupied)
    boys_solver.conv_tol = float(qc["localization_conv_tol"])
    boys_solver.max_cycle = int(qc["localization_max_cycle"])
    boys_occupied = boys_solver.kernel()

    pm_solver = lo.PM(mol, occupied)
    pm_solver.conv_tol = float(qc["localization_conv_tol"])
    pm_solver.max_cycle = int(qc["localization_max_cycle"])
    pm_occupied = pm_solver.kernel()

    fragments = config["system"]["fragments"]
    group_indices = {
        "left_ch2": atom_ao_indices(mol, [int(index) for index in fragments["left_ch2_atoms"]]),
        "right_ch2": atom_ao_indices(mol, [int(index) for index in fragments["right_ch2_atoms"]]),
    }
    representations = [
        representation_diagnostics(
            "canonical",
            occupied,
            occupied,
            overlap,
            overlap_half,
            group_indices,
            reference_density,
            canonical_energy,
            reference_electrons,
            mean_field,
        ),
        representation_diagnostics(
            "boys",
            boys_occupied,
            occupied,
            overlap,
            overlap_half,
            group_indices,
            reference_density,
            canonical_energy,
            reference_electrons,
            mean_field,
        ),
        representation_diagnostics(
            "pipek_mezey",
            pm_occupied,
            occupied,
            overlap,
            overlap_half,
            group_indices,
            reference_density,
            canonical_energy,
            reference_electrons,
            mean_field,
        ),
    ]

    tolerances = config["tolerances"]
    canonical_entropy = representations[0]["mean_binary_support_entropy"]
    entropy_changes = {
        item["name"]: item["mean_binary_support_entropy"] - canonical_entropy for item in representations[1:]
    }
    findings = {
        "scf_converged": bool(mean_field.converged),
        "all_representations_span_same_occupied_subspace": max(
            item["occupied_subspace_unitarity_residual"] for item in representations
        ) <= float(tolerances["occupied_unitarity_frobenius"]),
        "ao_density_invariant": max(
            item["density_relative_frobenius_residual_from_canonical"] for item in representations
        ) <= float(tolerances["density_relative_frobenius"]),
        "electron_number_invariant": max(
            item["electron_number_residual_from_canonical"] for item in representations
        ) <= float(tolerances["electron_number"]),
        "rhf_energy_invariant": max(
            item["energy_residual_from_canonical_hartree"] for item in representations
        ) <= float(tolerances["total_energy_hartree"]),
        "orbital_fragment_support_changes": max(abs(value) for value in entropy_changes.values())
        >= float(tolerances["minimum_entropy_change"]),
        "same_state_orbital_representation_is_not_electron_state_delocalization": True,
        "chemical_stabilization_label_authorized": False,
    }
    required = [value for key, value in findings.items() if key != "chemical_stabilization_label_authorized"]
    if not all(required):
        raise RuntimeError(f"P01 ethene occupied-gauge control failed: {findings}")

    inputs: dict[str, Any] = {}
    for name, relative in config["inputs"].items():
        path = ROOT / str(relative)
        inputs[name] = {"path": str(relative), "sha256": sha256_file(path)}
    return {
        "schema_version": 1,
        "protocol_id": config["protocol_id"],
        "proposition_id": "P01",
        "date": str(config["date"]),
        "verdict": "P01_ACTUAL_OCCUPIED_GAUGE_CONTROL_PASSED",
        "software": {"pyscf": __import__("pyscf").__version__, "numpy": np.__version__},
        "system": config["system"],
        "quantum_chemistry": qc,
        "scf": {
            "converged": bool(mean_field.converged),
            "cycles": int(getattr(mean_field, "cycles", -1)),
            "total_energy_hartree": canonical_energy,
            "nuclear_repulsion_hartree": float(mol.energy_nuc()),
            "electron_number": reference_electrons,
            "basis_function_count": int(mol.nao_nr()),
            "occupied_orbital_count": int(occupied.shape[1]),
        },
        "fragment_support_definition": config["diagnostics"]["fragment_support"],
        "representations": representations,
        "entropy_change_from_canonical": entropy_changes,
        "findings": findings,
        "inputs": inputs,
        "tolerances": tolerances,
        "boundaries": config["boundaries"],
    }


def render_report(record: dict[str, Any]) -> str:
    lines = [
        "# P01 乙烯 canonical/Boys/Pipek–Mezey 同密度实算",
        "",
        f"- 判定：**{record['verdict']}**",
        "- 体系：固定平面乙烯，RHF/6-31G(d)，气相",
        f"- SCF总能量：`{record['scf']['total_energy_hartree']:.12f} Eh`",
        f"- 电子数：`{record['scf']['electron_number']:.12f}`",
        "",
        "| 轨道表示 | 平均左右CH2支持熵 | 密度相对残差 | 电子数残差 | RHF能量残差/Eh | 占据子空间酉性残差 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in record["representations"]:
        lines.append(
            f"| {item['name']} | {item['mean_binary_support_entropy']:.12f} | "
            f"{item['density_relative_frobenius_residual_from_canonical']:.3e} | "
            f"{item['electron_number_residual_from_canonical']:.3e} | "
            f"{item['energy_residual_from_canonical_hartree']:.3e} | "
            f"{item['occupied_subspace_unitarity_residual']:.3e} |"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "Boys与Pipek–Mezey改变了各占据轨道在左右CH2片段上的支持分布，但重构AO密度、电子数、占据子空间和RHF能量保持不变。因此，单轨道图像的局域/离域变化不能单独证明电子态发生局域/离域变化。该实算支持P01的概念区分。",
            "",
            "本对照只检验同一电子态内的轨道规范自由度；它不比较不同受限电子态，也不产生稳定化/去稳定化能量标签。P01最终结论还需把此结果与既有LFMO命名受限态证据作一次明示映射。",
            "",
            "## 严格边界",
            "",
            "- 未启动P02、P03或P08；未修改第一期冻结结果。",
            "- 未安装NBO/BLW等软件，未扫描几何、基组或分子。",
            "- 未启动AI训练或生产标签。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    record = collect(config)
    record["config"] = {
        "path": str(config_path.relative_to(ROOT)).replace("\\", "/"),
        "sha256": sha256_file(config_path),
    }
    evidence_path = ROOT / str(config["outputs"]["evidence"])
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    report_path = ROOT / str(config["outputs"]["report"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(record), encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "verdict": record["verdict"],
                "energy_hartree": record["scf"]["total_energy_hartree"],
                "entropy_change_from_canonical": record["entropy_change_from_canonical"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
