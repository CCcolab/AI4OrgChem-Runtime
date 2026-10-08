"""Follow the accepted DSI-2 occupied subspaces through one bounded torsion step."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import numpy as np

from experiments.validation.dsi2_divinyl_imine_source_shaped_gate0 import full_stage
from experiments.validation.one_cut_conditional_scf_gate0 import ROOT, git_commit, json_safe, load_yaml
from experiments.validation.two_cut_ch2_uhf_gate0 import inverse_sqrt


DEFAULT_CONFIG = ROOT / "configs" / "qm" / "dsi2_divinyl_imine_torsion_continuation_v0.1.yaml"
DEFAULT_OUTPUT = ROOT / "artifacts" / "raw" / "dsi2_divinyl_imine_torsion_continuation_2026-08-14.json"
DEFAULT_MARKDOWN = ROOT / "docs" / "reports" / "gate0_dsi2_divinyl_imine_torsion_continuation_2026-08-14.md"


def rotate_about_axis(
    atoms: list[list[Any]], axis_indices: list[int], rotating_indices: list[int], angle_degrees: float
) -> list[list[Any]]:
    """Rigidly rotate selected atoms about an atom-defined axis."""

    result = deepcopy(atoms)
    origin = np.asarray(atoms[axis_indices[0]][1:], dtype=float)
    endpoint = np.asarray(atoms[axis_indices[1]][1:], dtype=float)
    axis = endpoint - origin
    axis /= np.linalg.norm(axis)
    angle = np.deg2rad(float(angle_degrees))
    cross = np.array(
        [[0.0, -axis[2], axis[1]], [axis[2], 0.0, -axis[0]], [-axis[1], axis[0], 0.0]]
    )
    rotation = np.eye(3) * np.cos(angle) + (1.0 - np.cos(angle)) * np.outer(axis, axis) + np.sin(angle) * cross
    for index in rotating_indices:
        coordinate = np.asarray(atoms[index][1:], dtype=float)
        result[index] = [atoms[index][0], *(origin + rotation @ (coordinate - origin)).tolist()]
    return result


def occupied_groups(internal: dict[str, Any]) -> list[np.ndarray]:
    coefficients = np.asarray(internal["coefficients"], dtype=float)
    sizes = [int(value) for value in internal["group_sizes"]]
    roots = [int(value) for value in internal["roots"]]
    offsets = np.cumsum([0, *sizes])
    return [
        coefficients[:, offsets[group] : offsets[group] + count]
        for group, count in enumerate(roots)
    ]


def cross_geometry_continuity(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    from pyscf import gto

    cross_overlap = gto.intor_cross(
        "int1e_ovlp", previous["molecule"], current["molecule"]
    )
    previous_groups = occupied_groups(previous)
    current_groups = occupied_groups(current)
    group_values = [
        np.linalg.svd(left.T @ cross_overlap @ right, compute_uv=False)
        for left, right in zip(previous_groups, current_groups, strict=True)
    ]
    previous_all = np.column_stack(previous_groups)
    current_all = np.column_stack(current_groups)
    previous_orthonormal = previous_all @ inverse_sqrt(
        previous_all.T @ previous["overlap"] @ previous_all
    )
    current_orthonormal = current_all @ inverse_sqrt(
        current_all.T @ current["overlap"] @ current_all
    )
    total_values = np.linalg.svd(
        previous_orthonormal.T @ cross_overlap @ current_orthonormal,
        compute_uv=False,
    )
    minima = [float(np.min(values)) for values in group_values]
    return {
        "group_minimum_singular_values": minima,
        "total_occupied_minimum_singular_value": float(np.min(total_values)),
        "minimum_singular_value": min([*minima, float(np.min(total_values))]),
    }


def run(config: dict[str, Any]) -> dict[str, Any]:
    base_path = ROOT / str(config["base_config"])
    base = load_yaml(base_path.resolve())
    torsion = config["torsion"]
    angles = [float(value) for value in torsion["angles_degrees"]]
    if len(angles) != 2 or angles[0] != 0.0:
        raise ValueError("bounded Gate 0 continuation requires exactly [0, perturbation]")
    points: list[dict[str, Any]] = []
    internals: list[dict[str, Any]] = []
    for angle in angles:
        point_config = deepcopy(base)
        point_config["experiment_id"] = f"{config['experiment_id']}/torsion-{angle:g}-degree"
        point_config["geometry"]["atoms"] = rotate_about_axis(
            base["geometry"]["atoms"],
            [int(value) for value in torsion["axis_atom_indices"]],
            [int(value) for value in torsion["rotating_atom_indices"]],
            angle,
        )
        point = full_stage(
            point_config,
            return_internal=True,
            source_type_references=(
                None if not internals else internals[-1]["source_type_references"]
            ),
            occupied_root_reference=(None if not internals else internals[-1]),
        )
        internals.append(point.pop("_internal"))
        points.append({"angle_degrees": angle, **point})
    continuity = cross_geometry_continuity(internals[0], internals[1])
    threshold = float(
        config["acceptance"]["cross_geometry_occupied_subspace_minimum_singular_value"]
    )
    checks = {
        "all_points_pass": all(point["disposition"] == "PASS" for point in points),
        "cross_geometry_root_continuity": continuity["minimum_singular_value"] >= threshold,
        "no_dsi3": config["boundaries"]["dsi3_enabled"] is False,
        "no_fud": config["boundaries"]["fud_enabled"] is False,
        "no_energy_difference": config["boundaries"]["energy_difference_enabled"] is False,
        "no_energy_label": config["boundaries"]["dsi_energy_label_enabled"] is False,
    }
    return {
        "experiment_id": config["experiment_id"],
        "stage": "bounded_dsi2_geometry_continuation",
        "disposition": "PASS" if all(checks.values()) else "QUARANTINE",
        "checks": checks,
        "torsion": torsion,
        "cross_geometry_continuity": continuity,
        "points": points,
        "provenance": {"git_commit": git_commit()},
        "boundaries": config["boundaries"],
    }


def render_markdown(report: dict[str, Any]) -> str:
    continuity = report["cross_geometry_continuity"]
    lines = [
        "# Gate 0 DSI-2 divinyl-imine torsion continuation", "",
        f"- Disposition: **{report['disposition']}**",
        "- Geometry path: `0 deg -> 10 deg` about the central N=C axis",
        "- DSI-3 / FUD / energy difference / energy label: not generated", "",
        "| Diagnostic | Value |", "|---|---:|",
        f"| Group occupied-subspace minima | {continuity['group_minimum_singular_values']} |",
        f"| Total occupied-subspace minimum | {continuity['total_occupied_minimum_singular_value']:.6f} |",
        f"| Overall minimum | {continuity['minimum_singular_value']:.6f} |",
    ]
    for point in report["points"]:
        dsi2 = point["dsi2"]
        lines.extend(
            [
                "",
                f"## {point['angle_degrees']:g} degrees", "",
                f"- Point disposition: **{point['disposition']}**",
                f"- SCF cycles: `{dsi2['cycles']}`",
                f"- Density residual: `{dsi2['final_density_fixed_point_residual']:.3e}`",
                f"- Physical idempotency: `{dsi2['physical_density_idempotency_residual']:.3e}`",
                f"- Intra-point root continuity: `{dsi2['minimum_root_subspace_singular_value']:.6f}`",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    report = json_safe(run(load_yaml(args.config.resolve())))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["disposition"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
