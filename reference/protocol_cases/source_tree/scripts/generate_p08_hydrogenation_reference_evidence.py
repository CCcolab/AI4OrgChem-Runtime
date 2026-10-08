"""Generate the deterministic P08 hydrogenation-reference sensitivity record."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/data/p08_butadiene_source_freeze_v0.1.yaml"
DEFAULT_OUTPUT = ROOT / "data/processed/p08_hydrogenation_reference_evidence_v0.1.json"
DEFAULT_REPORT = ROOT / "docs/reports/p08_hydrogenation_reference_reanalysis_2026-08-20.md"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def classify(value: float, tolerance: float) -> str:
    if value > tolerance:
        return "destabilizing"
    if value < -tolerance:
        return "stabilizing"
    return "near_zero"


def collect(config: dict[str, Any]) -> dict[str, Any]:
    source_path = ROOT / str(config["source"]["monograph_pdf"])
    actual_hash = sha256_file(source_path)
    expected_hash = str(config["source"]["sha256"]).upper()
    if actual_hash != expected_hash:
        raise RuntimeError("P08 public monograph PDF hash does not match the frozen source")

    subtarget = config["subtargets"]["P08_B"]
    values = subtarget["hydrogenation_enthalpies"]
    butadiene = float(values["trans_1_3_butadiene"])
    tolerance = float(config["decision_rules"]["sign_tolerance_kcal_per_mol"])
    expected = subtarget["expected_results"]

    results: list[dict[str, Any]] = []
    for reference in ("1_butene", "cis_2_butene", "trans_2_butene"):
        reference_heat = float(values[reference])
        conjugation_proxy = 2.0 * reference_heat - butadiene
        expected_value = float(expected[reference])
        results.append(
            {
                "reference": reference,
                "reference_hydrogenation_enthalpy_kcal_per_mol": reference_heat,
                "butadiene_hydrogenation_enthalpy_kcal_per_mol": butadiene,
                "delta_E_reference_kcal_per_mol": conjugation_proxy,
                "expected_kcal_per_mol": expected_value,
                "absolute_reproduction_error_kcal_per_mol": abs(conjugation_proxy - expected_value),
                "classification": classify(conjugation_proxy, tolerance),
            }
        )

    classes = sorted({row["classification"] for row in results})
    checks = {
        "source_hash_matches": True,
        "all_three_references_recomputed": len(results) == 3,
        "all_printed_values_reproduced": all(
            row["absolute_reproduction_error_kcal_per_mol"] <= 1.0e-12 for row in results
        ),
        "reference_choice_changes_classification": len(classes) > 1,
        "stabilizing_near_zero_and_destabilizing_all_present": set(classes)
        == {"destabilizing", "near_zero", "stabilizing"},
        "p08_a_independent_G_GL_calculation_complete": False,
        "p08_c_central_bond_calculation_complete": False,
        "p08_final_complete": False,
        "ai_training_started": False,
    }
    required = [
        checks["source_hash_matches"],
        checks["all_three_references_recomputed"],
        checks["all_printed_values_reproduced"],
        checks["reference_choice_changes_classification"],
        checks["stabilizing_near_zero_and_destabilizing_all_present"],
    ]
    if not all(required):
        raise RuntimeError(f"P08 hydrogenation-reference reanalysis failed: {checks}")

    return {
        "schema_version": 1,
        "protocol_id": config["protocol_id"],
        "proposition_id": "P08",
        "subtarget_id": "P08_B",
        "date": str(config["date"]),
        "verdict": "P08_HYDROGENATION_REFERENCE_SIGN_IS_NOT_UNIQUE",
        "relation_to_monograph": "consistent_with_figure_6_I_reference_sensitivity_claim",
        "subtarget_complete": True,
        "p08_complete": False,
        "formula": subtarget["formula"],
        "units": subtarget["units"],
        "sign_tolerance_kcal_per_mol": tolerance,
        "results": results,
        "observed_classifications": classes,
        "scientific_conclusion": (
            "The same experimental butadiene hydrogenation enthalpy yields stabilizing, near-zero, "
            "or destabilizing proxy values when the butene reference is changed; selective "
            "hydrogenation heat is therefore not a unique standalone sign test."
        ),
        "source": {**config["source"], "verified_sha256": actual_hash},
        "method_resolved_source_targets": config["subtargets"]["P08_A"],
        "checks": checks,
        "boundaries": config["boundaries"],
        "config": {
            "path": str(DEFAULT_CONFIG.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256_file(DEFAULT_CONFIG),
        },
    }


def render_report(record: dict[str, Any]) -> str:
    lines = [
        "# P08 选择性氢化热参照敏感性复算",
        "",
        f"- 协议：`{record['protocol_id']}`",
        f"- 子任务：`{record['subtarget_id']}`",
        f"- 判定：`{record['verdict']}`",
        "- P08总状态：进行中；本报告只关闭 P08-B",
        "",
        "## 确定性复算",
        "",
        "统一公式：`ΔE_ref = 2 ΔH_hyd(ref-butene) - ΔH_hyd(butadiene)`。",
        "",
        "| 丁烯参照 | ΔH(ref) | ΔH(丁二烯) | ΔE_ref (kcal/mol) | 分类 |",
        "|---|---:|---:|---:|---|",
    ]
    labels = {
        "1_butene": "1-丁烯",
        "cis_2_butene": "顺-2-丁烯",
        "trans_2_butene": "反-2-丁烯",
    }
    classes = {
        "stabilizing": "稳定化",
        "near_zero": "近零",
        "destabilizing": "去稳定化",
    }
    for row in record["results"]:
        lines.append(
            f"| {labels[row['reference']]} | {row['reference_hydrogenation_enthalpy_kcal_per_mol']:.1f} "
            f"| {row['butadiene_hydrogenation_enthalpy_kcal_per_mol']:.1f} "
            f"| {row['delta_E_reference_kcal_per_mol']:+.1f} | {classes[row['classification']]} |"
        )
    lines.extend(
        [
            "",
            "## 当前结论",
            "",
            "同一丁二烯实验氢化焓在更换丁烯参照后同时得到负值、近零和正值。因此，选择性氢化热的符号依赖参照选择，不能单独作为丁二烯共轭必然稳定化或必然去稳定化的唯一证据。该结果与原著 Figure 6-I 的限定命题一致。",
            "",
            "这还不是 P08 的最终能量符号。下一步必须按冻结的 GL(2014) 条件态，在 B3LYP/6-31G(d) 下独立计算 `E(G)-E(GL)`，并同时比较 `r23(G)-r23(GL)`。",
            "",
            "## 边界",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in record["boundaries"])
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    record = collect(config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(render_report(record), encoding="utf-8")
    print(json.dumps({"verdict": record["verdict"], "records": len(record["results"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()

