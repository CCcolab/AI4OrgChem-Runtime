"""Reconstruct the frozen P13 PBH ledger and independently enumerate acene Kekule graphs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from rdkit import Chem
from rdkit.Chem import rdMolDescriptors


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = ROOT / "configs/data/p13_polycyclic_benzenoid_source_freeze_v0.1.yaml"
DEFAULT_OUTPUT = ROOT / "data/processed/p13_polycyclic_benzenoid_v0.1.json"
DEFAULT_REPORT = ROOT / "docs/reports/p13_polycyclic_benzenoid_2026-08-22.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def edge(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def build_linear_acene(ring_count: int) -> dict[str, Any]:
    coordinate_to_atom: dict[tuple[float, float], int] = {}
    coordinates: list[tuple[float, float]] = []
    rings: list[list[int]] = []
    edges: set[tuple[int, int]] = set()
    for ring_index in range(ring_count):
        center_x = math.sqrt(3.0) * ring_index
        vertices: list[int] = []
        for k in range(6):
            angle = math.radians(30.0 + 60.0 * k)
            key = (round(center_x + math.cos(angle), 8), round(math.sin(angle), 8))
            if key not in coordinate_to_atom:
                coordinate_to_atom[key] = len(coordinates)
                coordinates.append(key)
            vertices.append(coordinate_to_atom[key])
        rings.append(vertices)
        for k in range(6):
            edges.add(edge(vertices[k], vertices[(k + 1) % 6]))
    ring_edges = [
        {edge(vertices[k], vertices[(k + 1) % 6]) for k in range(6)}
        for vertices in rings
    ]
    generalized_fusion_edges = {
        candidate
        for candidate in edges
        if abs(coordinates[candidate[0]][0] - coordinates[candidate[1]][0]) < 1.0e-7
    }
    return {
        "coordinates": coordinates,
        "edges": edges,
        "ring_edges": ring_edges,
        "generalized_fusion_edges": generalized_fusion_edges,
    }


def enumerate_perfect_matchings(
    atom_count: int, edges: set[tuple[int, int]]
) -> list[set[tuple[int, int]]]:
    adjacency = {atom: set() for atom in range(atom_count)}
    for left, right in edges:
        adjacency[left].add(right)
        adjacency[right].add(left)
    output: list[set[tuple[int, int]]] = []

    def visit(unmatched: frozenset[int], chosen: set[tuple[int, int]]) -> None:
        if not unmatched:
            output.append(set(chosen))
            return
        atom = min(unmatched, key=lambda item: len(adjacency[item] & unmatched))
        for neighbor in sorted(adjacency[atom] & unmatched):
            bond = edge(atom, neighbor)
            visit(unmatched - {atom, neighbor}, chosen | {bond})

    visit(frozenset(range(atom_count)), set())
    return output


def rdkit_formula(
    atom_count: int,
    edges: set[tuple[int, int]],
    matching: set[tuple[int, int]],
) -> str:
    editable = Chem.RWMol()
    for _ in range(atom_count):
        editable.AddAtom(Chem.Atom("C"))
    for left, right in sorted(edges):
        bond_type = Chem.BondType.DOUBLE if (left, right) in matching else Chem.BondType.SINGLE
        editable.AddBond(left, right, bond_type)
    molecule = editable.GetMol()
    Chem.SanitizeMol(molecule)
    return rdMolDescriptors.CalcMolFormula(molecule)


def enumerate_acene(ring_count: int) -> dict[str, Any]:
    graph = build_linear_acene(ring_count)
    atom_count = len(graph["coordinates"])
    matchings = enumerate_perfect_matchings(atom_count, graph["edges"])
    records = []
    for matching in matchings:
        n_db = len(matching & graph["generalized_fusion_edges"])
        n_gl = sum(len(matching & ring) == 3 for ring in graph["ring_edges"])
        records.append(
            {
                "N_db": n_db,
                "N_GL": n_gl,
                "qualified": n_gl == n_db + 1,
            }
        )
    return {
        "ring_count": ring_count,
        "atom_count": atom_count,
        "formula": rdkit_formula(atom_count, graph["edges"], matchings[0]),
        "kekule_count": len(matchings),
        "qualified_count": sum(record["qualified"] for record in records),
        "N_db_distribution": dict(sorted(Counter(record["N_db"] for record in records).items())),
        "N_GL_distribution": dict(sorted(Counter(record["N_GL"] for record in records).items())),
        "all_qualified_obey_rule": all(
            record["N_GL"] == record["N_db"] + 1
            for record in records
            if record["qualified"]
        ),
    }


def recompute_ledger(row: dict[str, Any]) -> dict[str, Any]:
    calculated_ese = float(row["delta_EA"]) - float(row["sum_delta_EAm"])
    calculated_cese = calculated_ese - float(row["sum_delta_EnAm"])
    return {
        **row,
        "calculated_ESE": calculated_ese,
        "ESE_residual": calculated_ese - float(row["ESE"]),
        "calculated_CESE": calculated_cese,
        "CESE_residual": calculated_cese - float(row["CESE"]),
    }


def render_report(record: dict[str, Any]) -> str:
    lines = [
        "# P13多环苯系烃范围化论证报告",
        "",
        f"- 协议：`{record['protocol_id']}`",
        "- 原著程序代码：未使用。",
        "- 历史限制几何优化：未宣称复现。",
        "- 独立通道：项目自编写完美匹配枚举器加RDKit分子式校验。",
        "",
        "## 独立Kekulé图枚举",
        "",
        "| 并苯环数 | 分子式 | Kekulé候选数 | GL合格候选数 |",
        "|---:|---|---:|---:|",
    ]
    for item in record["graph_enumeration"]:
        lines.append(
            f"| {item['ring_count']} | `{item['formula']}` | {item['kekule_count']} | {item['qualified_count']} |"
        )
    lines.extend(
        [
            "",
            "独立枚举得到Kekulé候选数为环数加1；去掉两个不满足GL六元组条件的端点型候选后，合格数为环数减1。",
            "",
            "## 能量账本与规则冲突留出",
            "",
            f"- Table 7-1候选账本行数：{len(record['candidate_rows'])}；所有ESE/CESE恒等式均在印刷精度内闭合。",
            "- 萘至并六苯的源选定候选均满足GL规则，并且在合格候选内具有最高分子能量。",
            "- `7-6-(4:0)`中，全体候选的最高能量结构具有N_GL=5、N_db=3，违反GL规则；过滤后原著选定的N_GL=4候选成为合格集合中的最高能量结构。",
            "- 这证明能量规则不能脱离GL六元组规则单独使用。",
            "",
            "## 范围化结论",
            "",
            "- 公开数值支持局域增量账本、CESE/π尺寸趋势和规则层级的内部一致性。",
            "- 独立图枚举支持GL候选筛选的组合拓扑基础。",
            "- 由于没有重新执行原著2007限制几何优化，具体ESE/CESE数值仍属于源数值重构，而不是独立量化复现。",
            "",
            f"最终判定：`{record['scientific_verdict']}`。",
            "",
            "最准确表述是：**在已测试的GL规则层级与公开PBH能量账本范围内，P13与原著一致。未执行全部历史限制几何优化仅作为证据层级说明。**",
            "",
            "本结果不是生产标签，不进入AI训练。",
            "",
            "## 自动检查",
            "",
        ]
    )
    for name, passed in record["acceptance_checks"].items():
        lines.append(f"- `{'PASS' if passed else 'FAIL'}` {name}")
    lines.append("")
    return "\n".join(lines)


def run(protocol_path: Path) -> dict[str, Any]:
    protocol = yaml.safe_load(protocol_path.read_text(encoding="utf-8"))
    tolerance = float(protocol["acceptance"]["rounded_energy_identity_tolerance_kcal_mol"])
    per_pi_tolerance = float(protocol["acceptance"]["rounded_per_pi_tolerance_kcal_mol_electron"])

    candidate_rows: list[dict[str, Any]] = []
    source_selection_checks = []
    for molecule in protocol["acene_candidate_panel"]:
        candidates = [recompute_ledger(dict(row)) for row in molecule["candidates"]]
        for candidate in candidates:
            candidate_rows.append({"molecule": molecule["molecule"], **candidate})
        selected = [row for row in candidates if row["selected"]]
        qualified = [
            row
            for row in candidates
            if int(row["N_GL"]) == int(molecule["generalized_N_db"]) + 1
        ]
        source_selection_checks.append(
            len(selected) == 1
            and selected[0] in qualified
            and selected[0]["E_GL_hartree"] == max(row["E_GL_hartree"] for row in qualified)
        )

    anchor_rows = [recompute_ledger(dict(row)) for row in protocol["cross_topology_anchors"]]
    holdout = protocol["holdout_rule_conflict"]
    holdout_rows = [recompute_ledger(dict(row)) for row in holdout["candidates"]]
    holdout_global_max = max(holdout_rows, key=lambda row: row["E_GL_hartree"])
    holdout_qualified = [
        row for row in holdout_rows if int(row["N_GL"]) == int(holdout["N_db"]) + 1
    ]
    holdout_qualified_max = max(holdout_qualified, key=lambda row: row["E_GL_hartree"])
    holdout_selected = [row for row in holdout_rows if row["source_selected"]]

    graph_enumeration = [
        enumerate_acene(int(ring_count))
        for ring_count in protocol["independent_graph_lane"]["ring_counts"]
    ]
    expected_formulas = {
        int(row["ring_count"]): row["formula"]
        for row in protocol["acene_candidate_panel"]
    }
    expected_formulas[7] = "C30H18"

    trend = protocol["acene_trend_panel"]
    absolute_cese_per_pi = [abs(float(row["CESE_per_pi"])) for row in trend]
    benzene_reference = float(protocol["acceptance"]["benzene_CESE_per_pi_absolute_reference"])
    all_ledgers = candidate_rows + anchor_rows + holdout_rows
    checks = {
        "published_ESE_identities_close": all(abs(row["ESE_residual"]) <= tolerance for row in all_ledgers),
        "published_CESE_identities_close": all(abs(row["CESE_residual"]) <= tolerance for row in all_ledgers),
        "source_selected_acene_candidates_obey_filtered_energy_rule": all(source_selection_checks),
        "acene_CESE_per_pi_matches_printed_values": all(
            abs(float(row["CESE"]) / int(row["pi_electrons"]) - float(row["CESE_per_pi"])) <= per_pi_tolerance
            for row in trend
        ),
        "acene_absolute_CESE_per_pi_decreases_with_size": all(
            left > right for left, right in zip(absolute_cese_per_pi, absolute_cese_per_pi[1:])
        ),
        "all_scoped_CESE_per_pi_below_benzene_reference": all(
            abs(float(row["CESE_per_pi"])) < benzene_reference
            for row in trend + protocol["cross_topology_anchors"]
        ),
        "all_scoped_adjacent_increment_sums_destabilizing": all(
            float(row["sum_delta_EAm"]) > 0.0 for row in all_ledgers
        ),
        "independent_graph_kekule_counts_match": all(
            item["kekule_count"] == item["ring_count"] + 1 for item in graph_enumeration
        ),
        "independent_graph_GL_qualified_counts_match": all(
            item["qualified_count"] == item["ring_count"] - 1 for item in graph_enumeration
        ),
        "independent_RDKit_formulas_match": all(
            item["formula"] == expected_formulas[item["ring_count"]] for item in graph_enumeration
        ),
        "holdout_detects_energy_rule_without_GL_filter_failure": (
            int(holdout_global_max["N_GL"]) != int(holdout["N_db"]) + 1
        ),
        "holdout_source_selection_is_highest_energy_after_GL_filter": (
            len(holdout_selected) == 1
            and holdout_selected[0]["label"] == holdout_qualified_max["label"]
        ),
        "historical_quantum_program_not_claimed": protocol["historical_quantum_program_reproduced"] is False,
        "production_label_disabled": protocol["production_labels_allowed"] is False,
        "AI_training_disabled": protocol["ai_training_allowed"] is False,
    }
    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise RuntimeError(f"P13 acceptance failed: {failed}")

    source_pdf = ROOT / protocol["source"]["local_reference"]
    return {
        "schema_version": 1,
        "protocol_id": protocol["protocol_id"],
        "proposition_id": "P13",
        "generated_date": "2026-08-22",
        "implementation": protocol["independent_graph_lane"]["implementation"],
        "rdkit_version": Chem.rdBase.rdkitVersion,
        "original_program_code_used": False,
        "historical_quantum_program_reproduced": False,
        "git_commit_at_generation": git_commit(),
        "source_pdf_sha256": sha256(source_pdf),
        "candidate_rows": candidate_rows,
        "anchor_rows": anchor_rows,
        "holdout_rows": holdout_rows,
        "holdout_global_energy_max": holdout_global_max["label"],
        "holdout_filtered_energy_max": holdout_qualified_max["label"],
        "graph_enumeration": graph_enumeration,
        "scientific_verdict": protocol["final_verdict_contract"]["verdict"],
        "relation_to_monograph": protocol["final_verdict_contract"]["relation_to_monograph"],
        "acceptance_checks": checks,
        "production_label": False,
        "training_eligible": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    arguments = parser.parse_args()
    record = run(arguments.protocol)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(render_report(record), encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": "PASS_P13_POLYCYCLIC_BENZENOID_RECONSTRUCTION",
                "scientific_verdict": record["scientific_verdict"],
                "graph_systems": len(record["graph_enumeration"]),
                "production_label": False,
                "training_eligible": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
