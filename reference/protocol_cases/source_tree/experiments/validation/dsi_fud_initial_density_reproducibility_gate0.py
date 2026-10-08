"""Check same-state DSI/FUD reproducibility from one alternative initial density."""

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


DEFAULT_CONFIG = ROOT / "configs" / "qm" / "dsi_fud_initial_density_reproducibility_v0.1.yaml"
DEFAULT_OUTPUT = ROOT / "artifacts" / "raw" / "dsi_fud_initial_density_reproducibility_2026-08-14.json"
DEFAULT_MARKDOWN = ROOT / "docs" / "reports" / "gate0_dsi_fud_initial_density_reproducibility_2026-08-14.md"


def resolve_state_config(path: Path) -> dict[str, Any]:
    wrapper = load_yaml(path.resolve())
    if "base_config" not in wrapper:
        return wrapper
    base = load_yaml((ROOT / str(wrapper["base_config"])).resolve())
    base["experiment_id"] = str(wrapper["experiment_id"])
    base["status"] = str(wrapper["status"])
    base["production_labels_allowed"] = bool(wrapper["production_labels_allowed"])
    state_key = str(wrapper["active_masked_state"])
    base["active_masked_state"] = state_key
    merged_state = dict(base.get(state_key, {}))
    merged_state.update(dict(wrapper[state_key]))
    base[state_key] = merged_state
    return base


def occupied_groups(internal: dict[str, Any]) -> list[np.ndarray]:
    coefficients = np.asarray(internal["coefficients"], dtype=float)
    sizes = [int(value) for value in internal["group_sizes"]]
    roots = [int(value) for value in internal["roots"]]
    offsets = np.cumsum([0, *sizes])
    return [
        coefficients[:, offsets[group] : offsets[group] + count]
        for group, count in enumerate(roots)
    ]


def compare_same_state(baseline: dict[str, Any], alternative: dict[str, Any]) -> dict[str, Any]:
    overlap = np.asarray(baseline["overlap"], dtype=float)
    baseline_groups = occupied_groups(baseline)
    alternative_groups = occupied_groups(alternative)
    group_minima = [
        float(np.min(np.linalg.svd(left.T @ overlap @ right, compute_uv=False)))
        for left, right in zip(baseline_groups, alternative_groups, strict=True)
    ]
    baseline_all = np.column_stack(baseline_groups)
    alternative_all = np.column_stack(alternative_groups)
    baseline_all = baseline_all @ inverse_sqrt(baseline_all.T @ overlap @ baseline_all)
    alternative_all = alternative_all @ inverse_sqrt(alternative_all.T @ overlap @ alternative_all)
    total_minimum = float(
        np.min(np.linalg.svd(baseline_all.T @ overlap @ alternative_all, compute_uv=False))
    )
    density_baseline = np.asarray(baseline["density"], dtype=float)
    density_alternative = np.asarray(alternative["density"], dtype=float)
    density_residual = float(
        np.linalg.norm(density_alternative - density_baseline, ord="fro")
        / max(float(np.linalg.norm(density_baseline, ord="fro")), 1.0)
    )
    return {
        "same_state_energy_absolute_difference_hartree": abs(
            float(alternative["diagnostic_energy_hartree"])
            - float(baseline["diagnostic_energy_hartree"])
        ),
        "same_state_density_relative_residual": density_residual,
        "group_occupied_subspace_minimum_singular_values": group_minima,
        "total_occupied_subspace_minimum_singular_value": total_minimum,
        "minimum_occupied_subspace_singular_value": min([*group_minima, total_minimum]),
    }


def run(config: dict[str, Any]) -> dict[str, Any]:
    baseline_guess = str(config["initial_density"]["baseline"])
    alternative_guess = str(config["initial_density"]["alternative"])
    acceptance = config["acceptance"]
    states: dict[str, Any] = {}
    for state_id, relative_path in config["states"].items():
        state_config = resolve_state_config(ROOT / str(relative_path))
        point_reports: dict[str, Any] = {}
        internals: dict[str, Any] = {}
        for label, guess in (("baseline", baseline_guess), ("alternative", alternative_guess)):
            point_config = deepcopy(state_config)
            point_config["experiment_id"] = f"{config['experiment_id']}/{state_id.lower()}-{label}-{guess}"
            point_config["conditional_scf"]["initial_guess"] = guess
            point = full_stage(point_config, return_internal=True)
            internals[label] = point.pop("_internal")
            slug = state_id.lower().replace("-", "")
            point_reports[label] = {
                "initial_density": guess,
                "disposition": point["disposition"],
                "checks": point["checks"],
                "state": point[slug],
            }
        comparison = compare_same_state(internals["baseline"], internals["alternative"])
        checks = {
            "both_runs_pass": all(point["disposition"] == "PASS" for point in point_reports.values()),
            "same_state_energy_reproduced": comparison["same_state_energy_absolute_difference_hartree"]
            <= float(acceptance["same_state_energy_absolute_difference_hartree"]),
            "same_state_density_reproduced": comparison["same_state_density_relative_residual"]
            <= float(acceptance["same_state_density_relative_residual"]),
            "occupied_subspace_reproduced": comparison["minimum_occupied_subspace_singular_value"]
            >= float(acceptance["occupied_subspace_minimum_singular_value"]),
        }
        states[state_id] = {
            "disposition": "PASS" if all(checks.values()) else "QUARANTINE",
            "checks": checks,
            "runs": point_reports,
            "same_state_comparison": comparison,
        }
    boundary_checks = {
        "same_geometry": config["boundaries"]["geometry_change_enabled"] is False,
        "same_state_definitions": config["boundaries"]["state_definition_change_enabled"] is False,
        "same_lfmo_construction": config["boundaries"]["lfmo_reconstruction_change_enabled"] is False,
        "no_inter_state_energy_difference": config["boundaries"]["inter_state_energy_difference_enabled"] is False,
        "no_stabilization_interpretation": config["boundaries"]["stabilization_interpretation_enabled"] is False,
        "no_energy_label": config["boundaries"]["energy_label_enabled"] is False,
    }
    disposition = "PASS" if all(
        [*(state["disposition"] == "PASS" for state in states.values()), *boundary_checks.values()]
    ) else "QUARANTINE"
    return {
        "experiment_id": config["experiment_id"],
        "stage": "same_state_initial_density_reproducibility",
        "disposition": disposition,
        "initial_density": config["initial_density"],
        "acceptance": acceptance,
        "states": states,
        "boundary_checks": boundary_checks,
        "boundaries": config["boundaries"],
        "provenance": {"git_commit": git_commit()},
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Gate 0 DSI/FUD initial-density reproducibility control", "",
        f"- Disposition: **{report['disposition']}**",
        f"- Initial densities: `{report['initial_density']['baseline']}` vs `{report['initial_density']['alternative']}`",
        "- Comparisons: same-state only; no inter-state energy difference or interpretation", "",
        "| State | Result | |dE| (Eh) | Density residual | Min occupied overlap |",
        "|---|---:|---:|---:|---:|",
    ]
    for state_id, state in report["states"].items():
        value = state["same_state_comparison"]
        lines.append(
            f"| {state_id} | {state['disposition']} | "
            f"{value['same_state_energy_absolute_difference_hartree']:.3e} | "
            f"{value['same_state_density_relative_residual']:.3e} | "
            f"{value['minimum_occupied_subspace_singular_value']:.6f} |"
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
