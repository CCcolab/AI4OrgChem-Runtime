"""Fixed P02 published-table reanalysis; no PDF access or quantum calculation.

The retained untracked development script is provenance material, not an
executable dependency or a blob attributed to the frozen public release.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import stat
from typing import Any

import numpy as np

CASE_ID = "P02"
SCOPE = "FROZEN_PUBLISHED_TABLE_VALUE_REANALYSIS"
REFERENCE_DIRECTORY = Path(__file__).resolve().parents[2] / "reference/registered_cases/p02"
SOURCE_IDENTITIES = {
    "generate_p02_structure_uv_evidence.py": "c4b5a672b5b022fa228f3a7b346ac9b333109bc5dcfe063df64742c22b035c53",
    "p02_structure_uv_source_freeze_v0.1.yaml": "0f7ccd27f4c0a41e6ede1f214aa8b0c9c4232b2b8b5e1e4f452653879a57c0bf",
}
TABLE_CHECK_NAMES = (
    "ten_target_compounds_frozen",
    "all_target_group_rules_consistent",
    "aromatic_reference_line_reproduced",
    "polyenal_reference_line_reproduced",
    "printed_polyenal_cc_is_outside_correlation_range",
    "uv_pair_order_supports_stronger_aromatic_participation_in_1_1_1_1",
    "both_structure_observables_oppose_traditional_direction",
)


def _finite_number(value: Any, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    number = float(value)
    if not math.isfinite(number) or (positive and number <= 0):
        raise ValueError(f"{name} must be finite" + (" and positive" if positive else ""))
    return number


def _nonnegative_integer(value: Any, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def _validate_regression_points(points: Any) -> None:
    if not isinstance(points, list) or len(points) < 3:
        raise ValueError("Reference regression needs at least three frozen points")
    seen = set()
    wavelengths = []
    for point in points:
        if not isinstance(point, dict):
            raise ValueError("Reference point must be a mapping")
        n = point.get("N")
        if type(n) is not int or n <= 0 or n in seen:
            raise ValueError("Reference N must be a distinct positive integer")
        seen.add(n)
        wavelengths.append(_finite_number(point.get("selected_wavelength_angstrom"), "wavelength", positive=True))
    if len(set(wavelengths)) < 2:
        raise ValueError("Reference wavelengths must have nonzero variance")


def validate_table_input(config: Any) -> dict[str, Any]:
    """Validate table shape and retain the original registered tolerances."""
    if not isinstance(config, dict):
        raise ValueError("P02 input must be a mapping")
    data = deepcopy(config)
    if data.get("protocol_id") != "P02_STRUCTURE_UV_SOURCE_FREEZE_V0.1" or data.get("proposition_id") != CASE_ID:
        raise ValueError("Wrong registered P02 protocol")
    tolerances = data.get("tolerances")
    if not isinstance(tolerances, dict) or set(tolerances) != {"coefficient_absolute", "direction_zero", "wavelength_transcription_angstrom"}:
        raise ValueError("Original P02 tolerances required")
    for key, expected in (("coefficient_absolute", 0.05), ("direction_zero", 1.0e-12), ("wavelength_transcription_angstrom", 0.0)):
        if _finite_number(tolerances[key], key) != expected:
            raise ValueError(f"Frozen tolerance changed: {key}")
    series = data.get("uv_reference_series")
    if not isinstance(series, dict) or set(series) != {"aromatic_1_3_m", "polyenal_1_4_n"}:
        raise ValueError("Both registered reference series required")
    for key, count in (("aromatic_1_3_m", 3), ("polyenal_1_4_n", 4)):
        item = series[key]
        _validate_regression_points(item.get("points"))
        if len(item["points"]) != count:
            raise ValueError("Wrong frozen reference point count")
        for field in ("intercept", "slope", "printed_cc"):
            _finite_number(item["monograph_figure_equation"][field], field)
    targets = data.get("uv_target_series")
    if not isinstance(targets, list) or len(targets) != 10:
        raise ValueError("Exactly ten frozen target compounds required")
    ids = set()
    for row in targets:
        m = _nonnegative_integer(row.get("m"), "m")
        n = _nonnegative_integer(row.get("n"), "n")
        identity = row.get("id")
        if identity != f"1-1-({m},{n})" or identity in ids:
            raise ValueError("Target identity must match m/n and be unique")
        ids.add(identity)
        bands = row.get("wavelengths_angstrom")
        if not isinstance(bands, list) or not bands:
            raise ValueError("Target wavelengths required")
        for value in bands:
            _finite_number(value, "target wavelength", positive=True)
        roles = row.get("peak_roles", {})
        if not isinstance(roles, dict):
            raise ValueError("Peak roles must be a mapping")
        for value in roles.values():
            if _finite_number(value, "role wavelength", positive=True) not in bands:
                raise ValueError("Peak role must refer to a retained band")
    pair = data.get("structural_pair")
    if not isinstance(pair, dict) or pair.get("stronger_aromatic_participation") != "1-1-(1,1)" or pair.get("weaker_aromatic_participation") != "1-1-(1,2)":
        raise ValueError("Only the original predeclared structure pair is allowed")
    values = pair.get("values")
    if not isinstance(values, dict) or set(values) != {"1-1-(1,1)", "1-1-(1,2)"}:
        raise ValueError("Both original structural observations required")
    for structure in values.values():
        _finite_number(structure["twist_angle_degree"], "twist angle")
        _finite_number(structure["c_n_bond_angstrom"], "C-N bond", positive=True)
    target = next(row for row in targets if row["id"] == "1-1-(1,1)")
    if "aromatic" not in target.get("peak_roles", {}):
        raise ValueError("The retained stronger-pair aromatic band is required")
    return data


def regression(points: list[dict[str, Any]]) -> dict[str, Any]:
    _validate_regression_points(points)
    return _original_regression(points)


def load_frozen_input() -> tuple[dict[str, Any], dict[str, Any]]:
    """Read only the copied table/configuration and retained provenance files."""
    metadata_path = REFERENCE_DIRECTORY / "SOURCE_METADATA.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if (metadata.get("schema_version") != "registered-p02-source-materials-v1"
            or metadata.get("original_files_are_part_of_frozen_public_release") is not False
            or metadata.get("source_repository_head_is_source_file_commit") is not False
            or metadata.get("source_repository_head_context") != "ffde7b5a53800010f2bc326b812b3e5b4526d56c"
            or metadata.get("frozen_public_evidence_reference_commit") != "28511f3d84fa65707a107cde1e8121a7b4334ecb"):
        raise ValueError("P02 retained-source provenance is invalid")
    observed = {}
    for name, expected in SOURCE_IDENTITIES.items():
        raw = (REFERENCE_DIRECTORY / name).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != expected:
            raise ValueError(f"P02 retained source bytes changed: {name}")
        observed[name] = {"sha256": digest, "size_bytes": len(raw)}
    items = {item["retained_filename"]: item for item in metadata["source_files"]}
    if set(items) != set(SOURCE_IDENTITIES) or len(metadata["source_files"]) != 2:
        raise ValueError("P02 retained source manifest is incomplete")
    for name, actual in observed.items():
        if items[name].get("sha256") != actual["sha256"] or items[name].get("size_bytes") != actual["size_bytes"] or items[name].get("git_tracking") != "UNTRACKED":
            raise ValueError("P02 retained-source metadata does not match bytes")
    import yaml

    config = yaml.safe_load((REFERENCE_DIRECTORY / "p02_structure_uv_source_freeze_v0.1.yaml").read_text(encoding="utf-8"))
    return validate_table_input(config), {"metadata_sha256": hashlib.sha256(metadata_path.read_bytes()).hexdigest(), "retained_files": observed, "source_repository_head_context": metadata["source_repository_head_context"], "source_commit_binding": "UNTRACKED_FILES_NOT_A_BLOB_AT_CONTEXT_HEAD", "frozen_public_evidence_reference_commit": metadata["frozen_public_evidence_reference_commit"]}


def run(output_dir: Path) -> dict[str, Any]:
    """Execute fresh statistics into an existing parent-selected run directory."""
    destination = Path(output_dir)
    if not destination.is_dir() or destination.is_symlink():
        raise ValueError("P02 requires an existing non-symlink output directory")
    for parent in (destination, *destination.parents):
        if parent.exists():
            info = parent.lstat()
            if parent.is_symlink() or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024):
                raise ValueError("P02 output ancestry must not contain symlinks/reparse points")
    resolved = destination.resolve()
    source_root = Path(__file__).resolve().parents[2]
    protected = [source_root, source_root.parent / "science"]
    if os.name == "nt":
        protected.append(Path(r"D:\AI4Science\AI4OrgChem").resolve())
        protected.append(Path(r"D:\AI4Science\ai4orgchem-runtime").resolve())
    if any(resolved == source or resolved.is_relative_to(source) or source.is_relative_to(resolved) for source in protected):
        raise ValueError("P02 output must be outside protected source directories")
    if any(destination.iterdir()):
        raise ValueError("P02 output directory must be fresh and empty")
    outputs = [destination / "case-result.json", destination / "case-report.md"]
    if any(path.exists() or path.is_symlink() for path in outputs):
        raise ValueError("P02 output files must be fresh")
    config, provenance = load_frozen_input()
    record = recompute_table_values(config)
    record["retained_source_provenance"] = provenance
    report = render_report(record)
    text = json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    for path, content in zip(outputs, (text, report)):
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    return record


def render_report(record: dict[str, Any]) -> str:
    lines = ["# P02 fixed published-table reanalysis", "", f"- Status: `{record['status']}`", f"- Scope: `{record['scope']}`", "- Primary source PDF verification: `NOT_EXECUTED`", "- Raw CIF/refinement verification: `NOT_EXECUTED`", "- New quantum calls: `0`", "- Fresh statistics recomputed from retained table input; no saved result is used.", "", "| Reference | Points | Intercept | Slope | R² | RMSE |", "|---|---:|---:|---:|---:|---:|"]
    for name, fit in record["uv_regressions"].items():
        lines.append(f"| {name} | {fit['point_count']} | {fit['intercept']:.8f} | {fit['slope']:.8f} | {fit['r_squared']:.8f} | {fit['rmse']:.8f} |")
    structure = record["structural_direction_test"]
    lines += ["", f"- Stronger-minus-weaker twist: `{structure['observed_twist_delta_degree']:+.12g} degree`", f"- Stronger-minus-weaker C-N bond: `{structure['observed_c_n_bond_delta_angstrom']:+.12g} angstrom`", "- One predeclared crystal pair; no p-value or missing uncertainty is inferred.", "- Numerical agreement is limited to these retained published values; no original coordinates are refined and no universal or causal scientific claim is generated.", "", "## Original table-value acceptance checks", ""]
    lines += [f"- `{key}`: `{value}`" for key, value in record["acceptance_checks"].items()]
    return "\n".join(lines) + "\n"


def _original_regression(points: list[dict[str, Any]]) -> dict[str, Any]:
    x = np.array([0.5 ** (2.0 / float(point["N"])) for point in points], dtype=float)
    y = np.array([1.0e4 / float(point["selected_wavelength_angstrom"]) for point in points], dtype=float)
    design = np.column_stack([np.ones_like(x), x])
    coefficients, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
    fitted = design @ coefficients
    residuals = y - fitted
    ss_res = float(np.sum(np.square(residuals)))
    ss_tot = float(np.sum(np.square(y - np.mean(y))))
    return {
        "point_count": len(points),
        "intercept": float(coefficients[0]),
        "slope": float(coefficients[1]),
        "r_squared": 1.0 - ss_res / ss_tot,
        "rmse": float(np.sqrt(np.mean(np.square(residuals)))),
        "points": [
            {
                "N": int(point["N"]),
                "wavelength_angstrom": float(point["selected_wavelength_angstrom"]),
                "homologous_factor": float(x[index]),
                "frequency_times_1e_minus_4_cm": float(y[index]),
                "residual": float(residuals[index]),
            }
            for index, point in enumerate(points)
        ],
    }


def expected_group(m: int, n: int) -> str:
    if m == n and m > 0:
        return "dual_competition"
    if m > n or (m == 0 and n == 0):
        return "aromatic_predominant"
    return "polyenal_predominant"


def recompute_table_values(config: dict[str, Any]) -> dict[str, Any]:
    config = validate_table_input(config)
    aromatic_config = config["uv_reference_series"]["aromatic_1_3_m"]
    polyenal_config = config["uv_reference_series"]["polyenal_1_4_n"]
    aromatic_fit = regression(aromatic_config["points"])
    polyenal_fit = regression(polyenal_config["points"])
    tolerance = float(config["tolerances"]["coefficient_absolute"])

    for fit, series in ((aromatic_fit, aromatic_config), (polyenal_fit, polyenal_config)):
        printed = series["monograph_figure_equation"]
        fit["monograph_figure_equation"] = printed
        fit["intercept_absolute_difference"] = abs(fit["intercept"] - float(printed["intercept"]))
        fit["slope_absolute_difference"] = abs(fit["slope"] - float(printed["slope"]))
        fit["figure_equation_reproduced_from_rounded_table_values"] = (
            fit["intercept_absolute_difference"] <= tolerance
            and fit["slope_absolute_difference"] <= tolerance
        )

    target_rows: list[dict[str, Any]] = []
    for target in config["uv_target_series"]:
        m = int(target["m"])
        n = int(target["n"])
        expected = expected_group(m, n)
        target_rows.append(
            {
                "id": target["id"],
                "m": m,
                "n": n,
                "wavelengths_angstrom": [float(value) for value in target["wavelengths_angstrom"]],
                "peak_roles": target.get("peak_roles"),
                "declared_group": target["monograph_group"],
                "group_expected_from_m_n_rule": expected,
                "group_rule_consistent": expected == target["monograph_group"],
            }
        )

    target_by_id = {row["id"]: row for row in config["uv_target_series"]}
    stronger_id = config["structural_pair"]["stronger_aromatic_participation"]
    weaker_id = config["structural_pair"]["weaker_aromatic_participation"]
    stronger = target_by_id[stronger_id]
    weaker = target_by_id[weaker_id]
    aromatic_reference_wavelength = float(aromatic_config["points"][1]["selected_wavelength_angstrom"])
    polyenal_reference_wavelength = float(polyenal_config["points"][2]["selected_wavelength_angstrom"])
    stronger_aromatic_peak = float(stronger["peak_roles"]["aromatic"])
    weaker_peak = float(weaker["wavelengths_angstrom"][0])
    uv_pair = {
        "stronger_id": stronger_id,
        "weaker_id": weaker_id,
        "stronger_aromatic_peak_angstrom": stronger_aromatic_peak,
        "naphthyl_reference_peak_angstrom": aromatic_reference_wavelength,
        "stronger_aromatic_peak_difference_angstrom": abs(stronger_aromatic_peak - aromatic_reference_wavelength),
        "stronger_aromatic_peak_relative_difference": abs(stronger_aromatic_peak - aromatic_reference_wavelength)
        / aromatic_reference_wavelength,
        "weaker_single_peak_angstrom": weaker_peak,
        "weaker_difference_from_naphthyl_reference_angstrom": abs(weaker_peak - aromatic_reference_wavelength),
        "weaker_difference_from_polyenal_reference_angstrom": abs(weaker_peak - polyenal_reference_wavelength),
        "weaker_relative_difference_from_naphthyl_reference": abs(weaker_peak - aromatic_reference_wavelength)
        / aromatic_reference_wavelength,
        "weaker_relative_difference_from_polyenal_reference": abs(weaker_peak - polyenal_reference_wavelength)
        / polyenal_reference_wavelength,
        "stronger_has_aromatic_branch_peak_and_weaker_is_polyenal_predominant": (
            stronger["monograph_group"] == "dual_competition"
            and "aromatic" in stronger["peak_roles"]
            and weaker["monograph_group"] == "polyenal_predominant"
        ),
    }

    structural_values = config["structural_pair"]["values"]
    stronger_structure = structural_values[stronger_id]
    weaker_structure = structural_values[weaker_id]
    twist_delta = float(stronger_structure["twist_angle_degree"]) - float(weaker_structure["twist_angle_degree"])
    bond_delta = float(stronger_structure["c_n_bond_angstrom"]) - float(weaker_structure["c_n_bond_angstrom"])
    zero = float(config["tolerances"]["direction_zero"])
    structure_test = {
        "stronger_id": stronger_id,
        "weaker_id": weaker_id,
        "values": structural_values,
        "traditional_prediction": config["structural_pair"]["traditional_direction_prediction"],
        "observed_twist_delta_degree": twist_delta,
        "observed_c_n_bond_delta_angstrom": bond_delta,
        "twist_direction_opposes_traditional_prediction": twist_delta > zero,
        "bond_direction_opposes_traditional_prediction": bond_delta > zero,
        "opposing_observable_count": int(twist_delta > zero) + int(bond_delta > zero),
        "observable_count": 2,
        "inferential_p_value_computed": False,
        "source_tier": config["structural_pair"]["source_tier"],
    }

    checks = {
        "ten_target_compounds_frozen": len(target_rows) == 10,
        "all_target_group_rules_consistent": all(row["group_rule_consistent"] for row in target_rows),
        "aromatic_reference_line_reproduced": aromatic_fit["figure_equation_reproduced_from_rounded_table_values"],
        "polyenal_reference_line_reproduced": polyenal_fit["figure_equation_reproduced_from_rounded_table_values"],
        "printed_polyenal_cc_is_outside_correlation_range": abs(
            float(polyenal_config["monograph_figure_equation"]["printed_cc"])
        ) > 1.0,
        "uv_pair_order_supports_stronger_aromatic_participation_in_1_1_1_1": uv_pair[
            "stronger_has_aromatic_branch_peak_and_weaker_is_polyenal_predominant"
        ],
        "both_structure_observables_oppose_traditional_direction": structure_test["opposing_observable_count"] == 2,
        "raw_cif_independent_refinement_completed": False,
        "p03_pes_started": False,
        "p08_butadiene_started": False,
        "ai_training_started": False,
    }
    acceptance_checks = {key: checks[key] for key in TABLE_CHECK_NAMES}
    passed = all(acceptance_checks.values())
    return {
        "schema_version": "registered-p02-fixed-table-result-v1",
        "case_id": CASE_ID,
        "proposition_id": CASE_ID,
        "protocol_id": config["protocol_id"],
        "status": "PASS" if passed else "FAIL",
        "scope": SCOPE,
        "rule_outcome": "P02_FROZEN_TABLE_VALUE_CHECKS_PASS" if passed else "P02_FROZEN_TABLE_VALUE_CHECKS_FAIL",
        "primary_source_verification": "NOT_EXECUTED",
        "raw_cif_verification": "NOT_EXECUTED",
        "source_pdf_accessed": False,
        "frozen_result_read": False,
        "new_quantum_calls": 0,
        "new_scientific_certification": "NOT_GENERATED",
        "acceptance_checks": acceptance_checks,
        "original_tolerances": config["tolerances"],
        "source_declaration": {
            "doi": config["source"]["doi"],
            "declared_historical_pdf_sha256": config["source"]["sha256"],
            "verification": "NOT_EXECUTED",
            "table": config["source"]["table"],
            "printed_pages": config["source"]["printed_pages"],
        },
        "uv_regressions": {"aromatic_1_3_m": aromatic_fit, "polyenal_1_4_n": polyenal_fit},
        "uv_target_rows": target_rows,
        "uv_pair_test": uv_pair,
        "structural_direction_test": structure_test,
        "limits": [
            "One predeclared crystal pair, two related directional observations; no p-value.",
            "Published frozen values only; original PDF/article/CIF authenticity is not reverified.",
            "No new geometry, quantum, PES, causal attribution, uncertainty inference or universal claim.",
        ],
    }
