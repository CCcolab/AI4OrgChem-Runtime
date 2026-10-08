"""Run the bounded P03 relaxed fixed-torsion PES for parent NBA."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/qm/p03_parent_nba_relaxed_pes_v0.1.yaml"
HARTREE_TO_KCAL_MOL = 627.5094740631


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def digest(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def geometry_digest(atoms: list[list[Any]]) -> str:
    return hashlib.sha256(
        json.dumps(atoms, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def coordinates(atoms: list[list[Any]]) -> np.ndarray:
    return np.asarray([atom[1:] for atom in atoms], dtype=float)


def molecule_to_atoms(molecule: Any) -> list[list[Any]]:
    xyz = molecule.atom_coords(unit="Angstrom")
    return [
        [molecule.atom_pure_symbol(index), *xyz[index].tolist()]
        for index in range(molecule.natm)
    ]


def signed_dihedral_degrees(xyz: np.ndarray, indices: list[int]) -> float:
    points = np.asarray(xyz, dtype=float)[indices]
    b0 = points[0] - points[1]
    b1 = points[2] - points[1]
    b2 = points[3] - points[2]
    b1 /= np.linalg.norm(b1)
    v = b0 - np.dot(b0, b1) * b1
    w = b2 - np.dot(b2, b1) * b1
    angle = float(
        np.degrees(np.arctan2(np.dot(np.cross(b1, v), w), np.dot(v, w)))
    )
    return -180.0 if abs(angle - 180.0) < 1.0e-10 else angle


def source_twist_degrees(xyz: np.ndarray, indices: list[int]) -> float:
    dihedral = abs(signed_dihedral_degrees(xyz, indices))
    return float(min(dihedral, abs(180.0 - dihedral)))


def rotate_about_axis(
    atoms: list[list[Any]],
    axis_indices: list[int],
    rotating_indices: list[int],
    angle_degrees: float,
) -> list[list[Any]]:
    result = deepcopy(atoms)
    origin = np.asarray(atoms[axis_indices[0]][1:], dtype=float)
    endpoint = np.asarray(atoms[axis_indices[1]][1:], dtype=float)
    axis = endpoint - origin
    axis /= np.linalg.norm(axis)
    angle = np.deg2rad(float(angle_degrees))
    cross = np.array(
        [
            [0.0, -axis[2], axis[1]],
            [axis[2], 0.0, -axis[0]],
            [-axis[1], axis[0], 0.0],
        ]
    )
    rotation = (
        np.eye(3) * np.cos(angle)
        + (1.0 - np.cos(angle)) * np.outer(axis, axis)
        + np.sin(angle) * cross
    )
    for index in rotating_indices:
        point = np.asarray(atoms[index][1:], dtype=float)
        result[index] = [
            atoms[index][0],
            *(origin + rotation @ (point - origin)).tolist(),
        ]
    return result


def build_mean_field(atoms: list[list[Any]], config: dict[str, Any]) -> Any:
    from pyscf import dft, gto

    molecule = gto.M(
        atom=atoms,
        basis=str(config["basis"]),
        charge=0,
        spin=0,
        unit="Angstrom",
        symmetry=False,
        verbose=0,
    )
    mean_field = dft.RKS(molecule)
    mean_field.verbose = 0
    mean_field.xc = str(config["method"])
    mean_field.conv_tol = float(config["scf_convergence_tolerance"])
    mean_field.max_cycle = int(config["scf_max_cycles"])
    mean_field.grids.level = int(config["grid_level"])
    return mean_field


def constraint_text(indices: list[int], signed_target: float) -> str:
    one_based = [index + 1 for index in indices]
    return (
        "$set\n"
        f"dihedral {' '.join(str(value) for value in one_based)} "
        f"{signed_target:.10f}\n"
        "$end\n"
    )


def optimize_point(
    atoms: list[list[Any]], requested_twist: float, config: dict[str, Any]
) -> dict[str, Any]:
    from pyscf.geomopt import geometric_solver

    indices = [int(value) for value in config["constrained_dihedral_atom_indices"]]
    signed_target = signed_dihedral_degrees(coordinates(atoms), indices)
    history: list[dict[str, Any]] = []

    def callback(environment: dict[str, Any]) -> None:
        gradients = np.asarray(environment["gradients"], dtype=float)
        current_atoms = molecule_to_atoms(environment["mol"])
        xyz = coordinates(current_atoms)
        history.append(
            {
                "cycle": int(environment["self"].cycle),
                "total_energy_hartree": float(environment["energy"]),
                "gradient_rms_hartree_per_bohr": float(
                    np.sqrt(np.mean(gradients**2))
                ),
                "gradient_max_hartree_per_bohr": float(np.max(np.abs(gradients))),
                "source_twist_degrees": source_twist_degrees(xyz, indices),
                "signed_dihedral_degrees": signed_dihedral_degrees(xyz, indices),
            }
        )

    constraint_path: str | None = None
    scratch = os.environ.get("AI4ORGCHEM_SCRATCH") or os.environ.get("TMPDIR")
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".constraints",
            prefix="ai4orgchem-p03-",
            dir=scratch,
            delete=False,
            encoding="utf-8",
        ) as stream:
            stream.write(constraint_text(indices, signed_target))
            constraint_path = stream.name
        mean_field = build_mean_field(atoms, config)
        converged, optimized_molecule = geometric_solver.kernel(
            mean_field,
            assert_convergence=True,
            constraints=constraint_path,
            callback=callback,
            maxsteps=int(config["optimizer_max_steps"]),
            convergence_energy=float(config["convergence_energy_hartree"]),
            convergence_grms=float(
                config["convergence_gradient_rms_hartree_per_bohr"]
            ),
            convergence_gmax=float(
                config["convergence_gradient_max_hartree_per_bohr"]
            ),
            convergence_drms=float(
                config["convergence_displacement_rms_angstrom"]
            ),
            convergence_dmax=float(
                config["convergence_displacement_max_angstrom"]
            ),
        )
    finally:
        if constraint_path and os.path.exists(constraint_path):
            os.unlink(constraint_path)

    optimized_atoms = molecule_to_atoms(optimized_molecule)
    achieved = source_twist_degrees(coordinates(optimized_atoms), indices)
    return {
        "requested_twist_degrees": float(requested_twist),
        "target_signed_dihedral_degrees": signed_target,
        "achieved_twist_degrees": achieved,
        "achieved_signed_dihedral_degrees": signed_dihedral_degrees(
            coordinates(optimized_atoms), indices
        ),
        "optimizer_converged": bool(converged),
        "optimizer_cycles": len(history),
        "geometry_sha256": geometry_digest(optimized_atoms),
        "atoms": optimized_atoms,
        "history": history,
    }


def single_point(atoms: list[list[Any]], config: dict[str, Any]) -> dict[str, Any]:
    mean_field = build_mean_field(atoms, config)
    total = float(mean_field.kernel())
    nuclear = float(mean_field.mol.energy_nuc())
    electronic = total - nuclear
    return {
        "scf_converged": bool(mean_field.converged),
        "total_energy_hartree": total,
        "electronic_energy_hartree": electronic,
        "nuclear_repulsion_hartree": nuclear,
        "energy_closure_residual_hartree": abs(total - (electronic + nuclear)),
    }


def fit_quadratic(angles: list[float], values: list[float]) -> dict[str, float | None]:
    a, b, c = [float(value) for value in np.polyfit(angles, values, 2)]
    predicted = np.polyval([a, b, c], angles)
    residuals = np.asarray(values) - predicted
    ss_res = float(np.sum(residuals**2))
    ss_tot = float(np.sum((np.asarray(values) - np.mean(values)) ** 2))
    return {
        "quadratic": a,
        "linear": b,
        "intercept": c,
        "second_derivative_hartree_per_degree2": 2.0 * a,
        "stationary_angle_degrees": (-b / (2.0 * a)) if abs(a) > 1.0e-16 else None,
        "r_squared": 1.0 - ss_res / ss_tot if ss_tot > 0.0 else 1.0,
        "rmse_hartree": float(np.sqrt(np.mean(residuals**2))),
    }


def analyze(master: dict[str, Any], points: dict[str, Any]) -> dict[str, Any]:
    angles = [float(value) for value in master["optimization"]["angles_degrees"]]
    ordered = [points[f"{angle:.1f}"] for angle in angles]
    totals = [float(point["energies"]["total_energy_hartree"]) for point in ordered]
    electronics = [
        float(point["energies"]["electronic_energy_hartree"]) for point in ordered
    ]
    nuclear = [
        float(point["energies"]["nuclear_repulsion_hartree"]) for point in ordered
    ]
    minimum_index = int(np.argmin(totals))
    minimum_angle = angles[minimum_index]
    tolerance = float(master["acceptance"]["direction_tolerance_hartree"])
    segments: list[dict[str, Any]] = []
    for index in range(1, minimum_index + 1):
        delta_total = totals[index] - totals[index - 1]
        delta_electronic = electronics[index] - electronics[index - 1]
        delta_nuclear = nuclear[index] - nuclear[index - 1]
        segments.append(
            {
                "from_angle_degrees": angles[index - 1],
                "to_angle_degrees": angles[index],
                "delta_total_hartree": delta_total,
                "delta_electronic_hartree": delta_electronic,
                "delta_nuclear_hartree": delta_nuclear,
                "electronic_drives_twist": delta_electronic < -tolerance,
                "nuclear_opposes_twist": delta_nuclear > tolerance,
                "total_favors_twist": delta_total < -tolerance,
                "energy_identity_residual_hartree": abs(
                    delta_total - (delta_electronic + delta_nuclear)
                ),
            }
        )
    acceptance = master["acceptance"]
    twist_tolerance = float(acceptance["twist_tolerance_degrees"])
    closure_tolerance = float(acceptance["energy_closure_tolerance_hartree"])
    checks = {
        "all_scf_converged": all(
            bool(point["energies"]["scf_converged"]) for point in ordered
        ),
        "all_optimizations_converged": all(
            bool(point["geometry"]["optimizer_converged"]) for point in ordered
        ),
        "all_twists_within_tolerance": all(
            abs(
                float(point["geometry"]["achieved_twist_degrees"])
                - float(point["geometry"]["requested_twist_degrees"])
            )
            <= twist_tolerance
            for point in ordered
        ),
        "all_energy_identities_close": all(
            float(point["energies"]["energy_closure_residual_hartree"])
            <= closure_tolerance
            for point in ordered
        ),
        "sampled_total_minimum_not_at_boundary": minimum_index not in (0, len(angles) - 1),
        "enough_lower_branch_segments": len(segments)
        >= int(acceptance["minimum_supported_lower_segments"]),
    }
    technical_pass = all(checks.values())
    direction_checks = {
        "electronic_decreases_on_lower_branch": bool(segments)
        and all(segment["electronic_drives_twist"] for segment in segments),
        "nuclear_repulsion_increases_on_lower_branch": bool(segments)
        and all(segment["nuclear_opposes_twist"] for segment in segments),
        "total_energy_decreases_on_lower_branch": bool(segments)
        and all(segment["total_favors_twist"] for segment in segments),
    }
    direction_pass = technical_pass and all(direction_checks.values())
    consistently_opposite = technical_pass and bool(segments) and all(
        segment["delta_electronic_hartree"] > tolerance
        and segment["delta_nuclear_hartree"] < -tolerance
        for segment in segments
    )
    if direction_pass:
        verdict = "P03_MINIMAL_PARENT_NBA_DIRECTION_SUPPORTED"
    elif consistently_opposite:
        verdict = "P03_MINIMAL_PARENT_NBA_DIRECTION_OPPOSED"
    else:
        verdict = "P03_MINIMAL_PARENT_NBA_DIRECTION_INDETERMINATE"
    baseline = ordered[0]["energies"]
    relative_points = []
    for point in ordered:
        energy = point["energies"]
        relative_points.append(
            {
                "angle_degrees": float(point["geometry"]["achieved_twist_degrees"]),
                "delta_total_hartree": float(energy["total_energy_hartree"])
                - float(baseline["total_energy_hartree"]),
                "delta_electronic_hartree": float(energy["electronic_energy_hartree"])
                - float(baseline["electronic_energy_hartree"]),
                "delta_nuclear_hartree": float(energy["nuclear_repulsion_hartree"])
                - float(baseline["nuclear_repulsion_hartree"]),
            }
        )
    return {
        "verdict": verdict,
        "p03_complete": bool(direction_pass or consistently_opposite),
        "technical_pass": technical_pass,
        "direction_pass": direction_pass,
        "sampled_total_minimum_angle_degrees": minimum_angle,
        "checks": checks,
        "direction_checks": direction_checks,
        "lower_branch_segments": segments,
        "relative_points": relative_points,
        "quadratic_fits": {
            "total": fit_quadratic(angles, totals),
            "electronic": fit_quadratic(angles, electronics),
            "nuclear_repulsion": fit_quadratic(angles, nuclear),
        },
        "scope": "single_parent_nba_source_aligned_relaxed_fixed_torsion_path",
        "universal_nba_claim": False,
        "lfmo_component_attribution": False,
    }


def render_report(evidence: dict[str, Any]) -> str:
    analysis = evidence["analysis"]
    points = evidence["points"]
    lines = [
        "# P03 parent NBA电子能—核排斥能 relaxed PES",
        "",
        f"- 判定：**{analysis['verdict']}**",
        f"- 技术通过：`{analysis['technical_pass']}`",
        f"- 方向门禁通过：`{analysis['direction_pass']}`",
        f"- 采样总能量最低点：`{analysis['sampled_total_minimum_angle_degrees']:.1f}°`",
        "- 范围：单一parent NBA，B3LYP/6-311G(d,p)，0°/20°/40°/60°",
        "",
        "## 同几何能量账本",
        "",
        "| 角度/° | E/Eh | Ee/Eh | EN/Eh | ΔE/kcal mol⁻¹ | ΔEe/Eh | ΔEN/Eh |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    relative = {row["angle_degrees"]: row for row in analysis["relative_points"]}
    for key in sorted(points, key=float):
        point = points[key]
        energy = point["energies"]
        angle = float(point["geometry"]["achieved_twist_degrees"])
        row = min(relative.values(), key=lambda value: abs(value["angle_degrees"] - angle))
        lines.append(
            f"| {angle:.5f} | {energy['total_energy_hartree']:.12f} | "
            f"{energy['electronic_energy_hartree']:.12f} | "
            f"{energy['nuclear_repulsion_hartree']:.12f} | "
            f"{row['delta_total_hartree'] * HARTREE_TO_KCAL_MOL:+.6f} | "
            f"{row['delta_electronic_hartree']:+.9f} | "
            f"{row['delta_nuclear_hartree']:+.9f} |"
        )
    lines.extend(
        [
            "",
            "## 平面态到最低点的方向检验",
            "",
            "| 区间/° | ΔEe/Eh | ΔEN/Eh | ΔE/Eh | 电子驱动 | 核排斥阻碍 | 总能量下降 |",
            "|---|---:|---:|---:|---|---|---|",
        ]
    )
    for segment in analysis["lower_branch_segments"]:
        lines.append(
            f"| {segment['from_angle_degrees']:.0f}→{segment['to_angle_degrees']:.0f} | "
            f"{segment['delta_electronic_hartree']:+.9f} | "
            f"{segment['delta_nuclear_hartree']:+.9f} | "
            f"{segment['delta_total_hartree']:+.9f} | "
            f"{'是' if segment['electronic_drives_twist'] else '否'} | "
            f"{'是' if segment['nuclear_opposes_twist'] else '否'} | "
            f"{'是' if segment['total_favors_twist'] else '否'} |"
        )
    fits = analysis["quadratic_fits"]
    lines.extend(
        [
            "",
            "## 二次拟合（描述性）",
            "",
            "| 能量 | 二阶导数/Eh deg⁻² | 驻点/° | R² |",
            "|---|---:|---:|---:|",
        ]
    )
    for name, label in (("total", "E"), ("electronic", "Ee"), ("nuclear_repulsion", "EN")):
        fit = fits[name]
        stationary = fit["stationary_angle_degrees"]
        lines.append(
            f"| {label} | {fit['second_derivative_hartree_per_degree2']:+.9e} | "
            f"{stationary:.3f} | {fit['r_squared']:.8f} |"
        )
    lines.extend(
        [
            "",
            "## 结论边界",
            "",
            "本结果只判定parent NBA这一条source-aligned relaxed fixed-torsion路径。它不把总电子能趋势归因于某个LFMO分量，不等同于历史Gaussian 98内部坐标约束的逐字节复现，也不外推为全部NBA类物种的普遍定律。P08和AI训练未启动。",
            "",
        ]
    )
    return "\n".join(lines)


def render_data_card(evidence: dict[str, Any]) -> str:
    analysis = evidence["analysis"]
    return "\n".join(
        [
            "# P03 parent NBA relaxed PES data card v0.1",
            "",
            f"- Verdict: `{analysis['verdict']}`",
            f"- P03 complete: `{analysis['p03_complete']}`",
            "- Molecule: parent N-benzylideneaniline only",
            "- Method: B3LYPG/6-311G(d,p)",
            "- Angles: 0, 20, 40, 60 degrees",
            "- Labels: total energy, electronic energy, nuclear repulsion",
            "- LFMO component attribution: no",
            "- Universal NBA claim: no",
            "- P08/AI/production labels: not started",
            "",
        ]
    )


def run(master: dict[str, Any], config_path: Path) -> dict[str, Any]:
    geometry_path = ROOT / str(master["molecule"]["geometry_artifact"])
    geometry_artifact = json.loads(geometry_path.read_text(encoding="utf-8"))
    initial_key = str(master["molecule"]["initial_point_key"])
    initial = geometry_artifact["points"][initial_key]
    if initial["geometry_sha256"] != master["molecule"]["expected_geometry_sha256"]:
        raise RuntimeError("frozen planar geometry hash mismatch")
    output_paths = {
        name: ROOT / str(value) for name, value in master["outputs"].items()
    }
    checkpoint_path = output_paths["checkpoint"]
    if checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if checkpoint.get("config_sha256") != digest(master):
            raise RuntimeError("checkpoint config hash mismatch")
    else:
        checkpoint = {
            "schema_version": 1,
            "experiment_id": master["experiment_id"],
            "config": str(config_path.relative_to(ROOT)),
            "config_sha256": digest(master),
            "points": {},
        }
    points = checkpoint["points"]
    optimization = master["optimization"]
    angles = [float(value) for value in optimization["angles_degrees"]]
    previous_atoms: list[list[Any]] | None = None
    previous_angle = 0.0
    for index, angle in enumerate(angles):
        key = f"{angle:.1f}"
        if key in points:
            previous_atoms = points[key]["geometry"]["atoms"]
            previous_angle = angle
            print(f"P03_REUSE angle={angle:.1f}", flush=True)
            continue
        if index == 0:
            atoms = deepcopy(initial["atoms"])
            geometry = {
                "requested_twist_degrees": angle,
                "target_signed_dihedral_degrees": signed_dihedral_degrees(
                    coordinates(atoms),
                    [int(v) for v in optimization["constrained_dihedral_atom_indices"]],
                ),
                "achieved_twist_degrees": source_twist_degrees(
                    coordinates(atoms),
                    [int(v) for v in optimization["constrained_dihedral_atom_indices"]],
                ),
                "achieved_signed_dihedral_degrees": signed_dihedral_degrees(
                    coordinates(atoms),
                    [int(v) for v in optimization["constrained_dihedral_atom_indices"]],
                ),
                "optimizer_converged": True,
                "optimizer_cycles": 0,
                "geometry_sha256": initial["geometry_sha256"],
                "atoms": atoms,
                "history": [],
                "geometry_role": "reused_frozen_planar_optimized_endpoint",
            }
        else:
            if previous_atoms is None:
                raise RuntimeError("sequential continuation has no previous geometry")
            rotated = rotate_about_axis(
                previous_atoms,
                [int(v) for v in optimization["rotation_axis_atom_indices"]],
                [int(v) for v in optimization["rotating_atom_indices"]],
                angle - previous_angle,
            )
            print(f"P03_OPTIMIZE angle={angle:.1f}", flush=True)
            geometry = optimize_point(rotated, angle, optimization)
            geometry["geometry_role"] = "relaxed_fixed_torsion_optimized_point"
        print(f"P03_SINGLE_POINT angle={angle:.1f}", flush=True)
        energy = single_point(geometry["atoms"], optimization)
        points[key] = {"geometry": geometry, "energies": energy}
        write_json(checkpoint_path, checkpoint)
        previous_atoms = geometry["atoms"]
        previous_angle = angle
        print(
            f"P03_POINT_DONE angle={angle:.1f} E={energy['total_energy_hartree']:.12f} "
            f"Ee={energy['electronic_energy_hartree']:.12f} "
            f"EN={energy['nuclear_repulsion_hartree']:.12f}",
            flush=True,
        )
    analysis = analyze(master, points)
    evidence = {
        "schema_version": 1,
        "experiment_id": master["experiment_id"],
        "proposition_id": "P03",
        "config": str(config_path.relative_to(ROOT)),
        "config_sha256": digest(master),
        "points": points,
        "analysis": analysis,
        "boundaries": master["boundaries"],
        "source_geometry_sha256": initial["geometry_sha256"],
    }
    write_json(output_paths["evidence"], evidence)
    output_paths["report"].parent.mkdir(parents=True, exist_ok=True)
    output_paths["report"].write_text(render_report(evidence), encoding="utf-8")
    output_paths["data_card"].parent.mkdir(parents=True, exist_ok=True)
    output_paths["data_card"].write_text(render_data_card(evidence), encoding="utf-8")
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config_path = args.config.resolve()
    master = read_yaml(config_path)
    evidence = run(master, config_path)
    analysis = evidence["analysis"]
    print(
        json.dumps(
            {
                "verdict": analysis["verdict"],
                "p03_complete": analysis["p03_complete"],
                "technical_pass": analysis["technical_pass"],
                "direction_pass": analysis["direction_pass"],
                "sampled_total_minimum_angle_degrees": analysis[
                    "sampled_total_minimum_angle_degrees"
                ],
            },
            sort_keys=True,
        )
    )
    return 0 if analysis["p03_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
