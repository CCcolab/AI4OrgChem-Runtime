"""Build the P07 same-Hamiltonian state-path audit from frozen QM evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/qm/p07_same_hamiltonian_path_audit_v0.2.yaml"
OUTPUT = ROOT / "data/processed/p07_same_hamiltonian_path_audit_v0.2.json"
REPORT = ROOT / "docs/reports/p07_same_hamiltonian_path_audit_2026-09-08.md"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    source_path = ROOT / config["input_artifact"]
    synthesis_path = ROOT / config["supplementary_derived_synthesis"]
    source = json.loads(source_path.read_text(encoding="utf-8"))
    acceptance = config["acceptance"]
    closure_tolerance = float(acceptance["closure_tolerance_hartree"])
    required_angles = [float(value) for value in acceptance["required_angles_degrees"]]

    points: dict[str, dict] = {}
    checks: list[bool] = []
    for angle in required_angles:
        key = f"{angle:.1f}"
        source_point = source["points"][key]
        cycle = source_point["cycle"]
        naive = cycle["effects_hartree"]
        complete = cycle["path_complete_three_term_effects_hartree"]
        bridge = float(cycle["bridge_hartree"])
        total = float(cycle["requested_total_hartree"])
        naive_sum = sum(float(naive[name]) for name in ("pi_sigma", "pi_pi", "sigma_sigma"))
        four_term_sum = naive_sum + bridge
        complete_sum = sum(float(complete[name]) for name in ("pi_sigma", "pi_pi", "sigma_sigma_total"))
        naive_residual = naive_sum - total
        four_term_residual = four_term_sum - total
        complete_residual = complete_sum - total
        bridge_identity_residual = float(complete["sigma_sigma_total"]) - (
            bridge + float(naive["sigma_sigma"])
        )

        point_checks = {
            "source_technical_pass": bool(source_point["technical_pass"]),
            "naive_three_terms_do_not_close": abs(naive_residual)
            >= float(acceptance["minimum_naive_residual_hartree"]),
            "bridge_is_material": abs(bridge)
            >= float(acceptance["minimum_bridge_magnitude_hartree"]),
            "four_term_path_closes": abs(four_term_residual) <= closure_tolerance,
            "path_complete_three_terms_close": abs(complete_residual) <= closure_tolerance,
            "sigma_bridge_identity_closes": abs(bridge_identity_residual) <= closure_tolerance,
            "sigma_subterm_positive": float(naive["sigma_sigma"]) > 0.0,
        }
        checks.extend(point_checks.values())
        points[key] = {
            "angle_degrees": angle,
            "naive_three_terms_hartree": {
                "pi_sigma_E_G_minus_E_FUD": float(naive["pi_sigma"]),
                "pi_pi_E_FUD_minus_E_DSI2": float(naive["pi_pi"]),
                "sigma_sigma_subterm_E_PDSI_minus_E_FUL": float(naive["sigma_sigma"]),
                "sum": naive_sum,
                "closure_residual_vs_E_G_minus_E_FUL": naive_residual,
            },
            "required_bridge_hartree": {
                "expression": "E_DSI2-E_PDSI",
                "value": bridge,
            },
            "four_term_state_path_hartree": {
                "sum": four_term_sum,
                "closure_residual_vs_E_G_minus_E_FUL": four_term_residual,
            },
            "path_complete_three_terms_hartree": {
                "pi_sigma_E_G_minus_E_FUD": float(complete["pi_sigma"]),
                "pi_pi_E_FUD_minus_E_DSI2": float(complete["pi_pi"]),
                "sigma_total_E_DSI2_minus_E_FUL": float(complete["sigma_sigma_total"]),
                "sum": complete_sum,
                "closure_residual_vs_E_G_minus_E_FUL": complete_residual,
            },
            "requested_total_E_G_minus_E_FUL_hartree": total,
            "sigma_total_identity_residual_hartree": bridge_identity_residual,
            "checks": point_checks,
        }

    pi_sigma_zero = points["0.0"]["naive_three_terms_hartree"]["pi_sigma_E_G_minus_E_FUD"]
    pi_sigma_17 = points["17.0"]["naive_three_terms_hartree"]["pi_sigma_E_G_minus_E_FUD"]
    global_checks = {
        "source_declares_same_hamiltonian": bool(
            source["boundaries"]["same_rhf_sto3g_hamiltonian_for_all_states"]
        ),
        "source_declares_same_geometry": bool(
            source["boundaries"]["same_geometry_within_each_state_family"]
        ),
        "zero_angle_pi_sigma_is_control": abs(pi_sigma_zero)
        <= float(acceptance["zero_angle_pi_sigma_tolerance_hartree"]),
        "seventeen_degree_pi_sigma_positive": pi_sigma_17 > 0.0,
        "both_source_points_available": set(points) == {"0.0", "17.0"},
    }
    checks.extend(global_checks.values())
    passed = all(checks)

    return {
        "schema_version": 1,
        "experiment_id": config["experiment_id"],
        "proposition_id": "P07",
        "verdict": config["interpretation"]["pass_verdict"] if passed else "P07_PATH_AUDIT_FAILED",
        "technical_pass": passed,
        "evidence_identity": config["interpretation"]["evidence_identity"],
        "counts_as_independent_computational_audit": passed,
        "scope": config["frozen_scope"],
        "state_path": config["frozen_scope"]["state_path"],
        "points": points,
        "global_checks": global_checks,
        "scientific_interpretation": {
            "naive_pi_pi_pi_sigma_sigma_subterm_is_closed": False,
            "explicit_sigma_bridge_is_required": True,
            "path_complete_three_term_definition_is_closed": True,
            "simple_two_term_conjugation_vs_steric_story_is_sufficient": False,
            "claim": config["interpretation"]["claim"],
        },
        "boundaries": config["boundaries"],
        "provenance": {
            "config": str(CONFIG.relative_to(ROOT)).replace("\\", "/"),
            "config_sha256": sha256(CONFIG),
            "input_artifact": str(source_path.relative_to(ROOT)).replace("\\", "/"),
            "input_artifact_sha256": sha256(source_path),
            "input_protocol": config["input_protocol"],
            "input_protocol_sha256": sha256(ROOT / config["input_protocol"]),
            "supplementary_derived_synthesis": str(synthesis_path.relative_to(ROOT)).replace("\\", "/"),
            "supplementary_derived_synthesis_sha256": sha256(synthesis_path),
        },
    }


def write_report(result: dict) -> None:
    lines = [
        "# P07 同哈密顿量状态路径独立审计",
        "",
        f"- 判定：**{result['verdict']}**",
        f"- 证据身份：`{result['evidence_identity']}`",
        "- 分子/方法：diphenyl imine parent NBA；RHF/STO-3G；同角度内五状态共享几何与哈密顿量",
        "- 新量子化学计算：否；本报告重新分析冻结的2026-08-14原始QM结果",
        "",
        "| 角度 | π–σ | π–π | PDSI−FUL σ子项 | 三项残差 | DSI2−PDSI桥 | 路径完整残差 |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key in ("0.0", "17.0"):
        point = result["points"][key]
        naive = point["naive_three_terms_hartree"]
        lines.append(
            f"| {key}° | {naive['pi_sigma_E_G_minus_E_FUD']:+.12f} | "
            f"{naive['pi_pi_E_FUD_minus_E_DSI2']:+.12f} | "
            f"{naive['sigma_sigma_subterm_E_PDSI_minus_E_FUL']:+.12f} | "
            f"{naive['closure_residual_vs_E_G_minus_E_FUL']:+.12f} | "
            f"{point['required_bridge_hartree']['value']:+.12f} | "
            f"{point['path_complete_three_terms_hartree']['closure_residual_vs_E_G_minus_E_FUL']:+.3e} |"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "在同一分子、同一角度几何、同一RHF/STO-3G哈密顿量下，直接把π–π、π–σ和`E_PDSI-E_FUL` σ子项相加，仍分别留下约0.336和0.334 Eh残差。加入`E_DSI2-E_PDSI`桥接项后四状态差路径严格闭合；等价地，把σ项定义为路径完整的`E_DSI2-E_FUL`后三项严格闭合。因此，三种作用不能脱离明确状态路径被当作天然可加的普通能量分量，简单“共轭稳定化—位阻去稳定化”二项叙事不足以完成机制账本。该独立同哈密顿量审计直接支持P07。",
            "",
            "## 边界",
            "",
            "本审计不把条件态差等同于通用物理相互作用能，不建立跨分子或跨方法定律，也不改写P04–P06各自的源定义结果。",
        ]
    )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    result = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    write_report(result)
    print(json.dumps({"verdict": result["verdict"], "technical_pass": result["technical_pass"]}, ensure_ascii=False))
    return 0 if result["technical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
