"""Reanalyse the frozen published UV and X-ray values for proposition P02."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/data/p02_structure_uv_source_freeze_v0.1.yaml"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def regression(points: list[dict[str, Any]]) -> dict[str, Any]:
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


def collect(config: dict[str, Any]) -> dict[str, Any]:
    source_path = ROOT / str(config["source"]["monograph_pdf"])
    actual_hash = sha256_file(source_path)
    if actual_hash != str(config["source"]["sha256"]).upper():
        raise RuntimeError("Public monograph PDF hash does not match the frozen source")

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
        "source_hash_matches": True,
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
    required_true = [
        value
        for key, value in checks.items()
        if key
        not in {
            "raw_cif_independent_refinement_completed",
            "p03_pes_started",
            "p08_butadiene_started",
            "ai_training_started",
        }
    ]
    if not all(required_true):
        raise RuntimeError(f"P02 published-data reanalysis failed: {checks}")

    return {
        "schema_version": 1,
        "protocol_id": config["protocol_id"],
        "proposition_id": "P02",
        "date": str(config["date"]),
        "verdict": "P02_PUBLISHED_DATA_SCOPED_PROPOSITION_SUPPORTED",
        "relation_to_monograph": "consistent_with_original_proposition_in_published_value_scope",
        "p02_complete": True,
        "completion_scope": "published_value_reanalysis_not_raw_crystallographic_refinement",
        "source": {**config["source"], "verified_sha256": actual_hash},
        "external_sources": config["external_sources"],
        "uv_regressions": {"aromatic_1_3_m": aromatic_fit, "polyenal_1_4_n": polyenal_fit},
        "uv_target_rows": target_rows,
        "uv_pair_test": uv_pair,
        "structural_direction_test": structure_test,
        "scientific_conclusion": (
            "Within the frozen published pair, stronger aromatic-branch conjugation participation is accompanied "
            "by a larger twist angle and a longer C-N bond, contradicting the local mandatory-planarization direction."
        ),
        "checks": checks,
        "inclusion_rules": config["inclusion_rules"],
        "exclusion_rules": config["exclusion_rules"],
        "boundaries": config["boundaries"],
        "config": {
            "path": str(DEFAULT_CONFIG.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256_file(DEFAULT_CONFIG),
        },
    }


def render_report(record: dict[str, Any]) -> str:
    aromatic = record["uv_regressions"]["aromatic_1_3_m"]
    polyenal = record["uv_regressions"]["polyenal_1_4_n"]
    uv_pair = record["uv_pair_test"]
    structure = record["structural_direction_test"]
    lines = [
        "# P02 结构与UV公开发表值复分析",
        "",
        f"- 判定：**{record['verdict']}**",
        "- 与原著关系：**在公开发表值范围内一致**",
        "- 完成层级：公开表格与引用结构值复分析；不是原始CIF再精修",
        "",
        "## UV同系线重算",
        "",
        "| 参考系列 | 点数 | 截距 | 斜率 | R² | RMSE | 与Figure公式一致 |",
        "|---|---:|---:|---:|---:|---:|---|",
        f"| `1-3-(m)`芳香支 | {aromatic['point_count']} | {aromatic['intercept']:.8f} | {aromatic['slope']:.8f} | {aromatic['r_squared']:.8f} | {aromatic['rmse']:.8f} | 是 |",
        f"| `1-4-(n)`多烯醛支 | {polyenal['point_count']} | {polyenal['intercept']:.8f} | {polyenal['slope']:.8f} | {polyenal['r_squared']:.8f} | {polyenal['rmse']:.8f} | 是 |",
        "",
        "使用Table 1-1的取整波长重新拟合后，两条线的系数与Figure 1-3/1-4印刷公式绝对差均小于0.05。"
        "多烯醛线印刷的`cc=9.847`超出相关系数允许范围，按明显排印问题处理；独立重算的`R²`为"
        f"`{polyenal['r_squared']:.8f}`。",
        "",
        "## 冻结晶体对的UV排序",
        "",
        f"`1-1-(1,1)`的芳香支峰为`{uv_pair['stronger_aromatic_peak_angstrom']:.0f} Å`，与2-萘基参考峰"
        f"`{uv_pair['naphthyl_reference_peak_angstrom']:.0f} Å`只差`{uv_pair['stronger_aromatic_peak_difference_angstrom']:.0f} Å`。"
        f"`1-1-(1,2)`只有`{uv_pair['weaker_single_peak_angstrom']:.0f} Å`主峰，距芳香支参考`{uv_pair['weaker_difference_from_naphthyl_reference_angstrom']:.0f} Å`，"
        f"距对应多烯醛参考`{uv_pair['weaker_difference_from_polyenal_reference_angstrom']:.0f} Å`。"
        "因此公开UV值支持前者具有更强的2-萘基支参与。",
        "",
        "## 结构方向检验",
        "",
        "| 观测量 | `1-1-(1,1)` | `1-1-(1,2)` | 强减弱差值 | 传统必然平面化预测 | 结果 |",
        "|---|---:|---:|---:|---|---|",
        f"| 扭转角/° | {structure['values']['1-1-(1,1)']['twist_angle_degree']:.1f} | {structure['values']['1-1-(1,2)']['twist_angle_degree']:.1f} | {structure['observed_twist_delta_degree']:+.1f} | `<0` | 相反 |",
        f"| C–N键长/Å | {structure['values']['1-1-(1,1)']['c_n_bond_angstrom']:.3f} | {structure['values']['1-1-(1,2)']['c_n_bond_angstrom']:.3f} | {structure['observed_c_n_bond_delta_angstrom']:+.3f} | `<0` | 相反 |",
        "",
        "两个预先指定的结构观测量均与“更强共轭必须更平面且连接键更短”的方向相反。样本只有一个晶体对，且没有公开标准不确定度，因此不计算无意义的p值。",
        "",
        "## P02范围化结论",
        "",
        "公开发表值复分析支持P02：在该冻结氮桥多烯醛晶体对中，更强的2-萘基支共轭参与可以与更大的扭转角和更长的C–N键同时出现。这反对把“共轭增强必然导致平面化”当作无需检验的充分预测。",
        "",
        "该结论不证明扭曲由哪一能量分量驱动，也不建立跨分子的普遍定律。原始CIF和完整晶体学不确定度未取得，因此不能表述为原始坐标独立再精修；P03的PES与核排斥因果计算仍未启动。",
        "",
    ]
    return "\n".join(lines)


def render_data_card(record: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# P02 structure/UV evidence data card v0.1",
            "",
            f"- Verdict: `{record['verdict']}`",
            "- Scope: published Table 1-1 UV values and cited X-ray pair values",
            "- Target UV compounds: 10",
            "- Structural primary test: one predeclared pair, two directional observables",
            "- Raw CIF refinement: not completed",
            "- Relation to monograph: consistent in published-value scope",
            "- P03/P08/AI started: no",
            "- Production label: no",
            "",
        ]
    )


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
    for key, renderer in (("report", render_report), ("data_card", render_data_card)):
        path = ROOT / str(config["outputs"][key])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(renderer(record), encoding="utf-8", newline="\n")
    evidence = ROOT / str(config["outputs"]["evidence"])
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(
        json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "verdict": record["verdict"],
                "p02_complete": record["p02_complete"],
                "aromatic_r_squared": aromatic["r_squared"] if (aromatic := record["uv_regressions"]["aromatic_1_3_m"]) else None,
                "polyenal_r_squared": record["uv_regressions"]["polyenal_1_4_n"]["r_squared"],
                "opposing_observables": record["structural_direction_test"]["opposing_observable_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
