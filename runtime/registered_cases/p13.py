"""Fixed P13 frozen-table reconstruction and independent graph/RDKit checks.

Derived from the AI4OrgChem project-authored P13 driver (Apache-2.0).
The preserved driver is a working-tree source, not a driver in public baseline
28511f3.  Its mathematical AST is reused; its CLI, Git and PDF reads are not.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_DIR = RUNTIME_ROOT / "reference" / "registered_cases" / "p13"
ORIGINAL_DEVELOPMENT_DIR = Path(r"D:\AI4Science\AI4OrgChem").absolute()
DRIVER_NAME = "run_p13_polycyclic_benzenoid.py"
PROTOCOL_NAME = "p13_polycyclic_benzenoid_source_freeze_v0.1.yaml"
DRIVER_SHA256 = "a731fcbd2f3415f81edc2060625067596b5b4365b16c11f3623c98aeb241173c"
PROTOCOL_SHA256 = "b3a657137ec42bed5163287426f35a1f1b50da446e9593444a07a237d4e97a13"
METADATA_SHA256 = "2cf9f14c55dd3fbea23a2aadb90397c3e9fab6089139fc68d478a01ae6e02268"
REQUIRED_RDKIT_VERSION = "2026.03.4"
SCOPE = "FROZEN_P13_TABLE_AND_INDEPENDENT_ACENE_GRAPH_RDKIT_FORMULA"
PURE_HELPERS = ("edge", "build_linear_acene", "enumerate_perfect_matchings", "recompute_ledger")
FULL_HELPERS = PURE_HELPERS + ("rdkit_formula", "enumerate_acene")
ACCEPTANCE_NAMES = (
    "published_ESE_identities_close", "published_CESE_identities_close",
    "source_selected_acene_candidates_obey_filtered_energy_rule",
    "acene_CESE_per_pi_matches_printed_values",
    "acene_absolute_CESE_per_pi_decreases_with_size",
    "all_scoped_CESE_per_pi_below_benzene_reference",
    "all_scoped_adjacent_increment_sums_destabilizing",
    "independent_graph_kekule_counts_match",
    "independent_graph_GL_qualified_counts_match", "independent_RDKit_formulas_match",
    "holdout_detects_energy_rule_without_GL_filter_failure",
    "holdout_source_selection_is_highest_energy_after_GL_filter",
    "historical_quantum_program_not_claimed", "production_label_disabled",
    "AI_training_disabled",
)


class P13Blocked(ValueError):
    """An input identity or required authentic dependency is unavailable."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_regular(path: Path) -> bytes:
    if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        raise P13Blocked(f"P13_SOURCE_LINK_REFUSED: {path.name}")
    if not path.is_file():
        raise P13Blocked(f"P13_SOURCE_MISSING: {path.name}")
    return path.read_bytes()


def verify_sources() -> dict[str, Any]:
    """Check only the bundled fixed sources; never resolve the PDF reference."""
    for directory in (REFERENCE_DIR, *REFERENCE_DIR.parents):
        if directory.is_symlink() or (hasattr(directory, "is_junction") and directory.is_junction()):
            raise P13Blocked("P13_SOURCE_ANCESTOR_LINK_REFUSED")
    declarations = {
        DRIVER_NAME: (DRIVER_SHA256, 14962),
        PROTOCOL_NAME: (PROTOCOL_SHA256, 7268),
        "SOURCE_METADATA.json": (METADATA_SHA256, None),
    }
    payloads: dict[str, bytes] = {}
    for name, (expected_hash, expected_size) in declarations.items():
        raw = _read_regular(REFERENCE_DIR / name)
        if _sha(raw) != expected_hash or (expected_size is not None and len(raw) != expected_size):
            raise P13Blocked(f"P13_SOURCE_HASH_MISMATCH: {name}")
        payloads[name] = raw
    metadata = json.loads(payloads["SOURCE_METADATA.json"])
    if (metadata["driver_is_public_baseline_driver"] is not False
            or metadata["primary_pdf"]["actual_sha256"] is not None
            or metadata["primary_pdf"]["status"] != "NOT_REAUTHENTICATED"):
        raise P13Blocked("P13_SOURCE_SCOPE_MISMATCH")
    return {"driver_bytes": payloads[DRIVER_NAME], "protocol_bytes": payloads[PROTOCOL_NAME],
            "metadata": metadata, "source_sha256": {name: _sha(raw) for name, raw in payloads.items()}}


def _functions(driver: bytes) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(driver.decode("utf-8"), filename=DRIVER_NAME)
    return {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}


def _compile_helpers(driver: bytes, names: tuple[str, ...], **bindings: Any) -> dict[str, Any]:
    functions = _functions(driver)
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        *[copy.deepcopy(functions[name]) for name in names],
    ], type_ignores=[])
    namespace: dict[str, Any] = {"math": math, "Counter": Counter, "Any": Any, **bindings}
    exec(compile(ast.fix_missing_locations(module), "<locked-p13-helper-ast>", "exec"), namespace)
    return namespace


def build_linear_acene(ring_count: int) -> dict[str, Any]:
    """Expose the preserved pure graph constructor for stdlib verification."""
    if type(ring_count) is not int or ring_count not in (2, 3, 4, 5, 6, 7):
        raise ValueError("P13_FIXED_RING_COUNTS_ONLY")
    source = verify_sources()
    return _compile_helpers(source["driver_bytes"], PURE_HELPERS)["build_linear_acene"](ring_count)


def enumerate_perfect_matchings(atom_count: int, edges: set[tuple[int, int]]) -> list[set[tuple[int, int]]]:
    source = verify_sources()
    return _compile_helpers(source["driver_bytes"], PURE_HELPERS)["enumerate_perfect_matchings"](atom_count, edges)


def recompute_ledger(row: dict[str, Any]) -> dict[str, Any]:
    source = verify_sources()
    return _compile_helpers(source["driver_bytes"], PURE_HELPERS)["recompute_ledger"](row)


def _mathematics(driver: bytes, chem: Any, descriptors: Any) -> tuple[Any, dict[str, Any]]:
    """Extract original run's math, replacing only I/O and failure transport.

    The first YAML read, trailing failure raise, PDF read and return/Git call
    are omitted. All intervening mathematical expressions and checks are
    copied without edits. There is no formula fallback or arbitrary callback.
    """
    original = _functions(driver)["run"]
    body: list[ast.stmt] = []
    for statement in original.body[1:]:
        if isinstance(statement, ast.If):
            # Original sole if raises after computing all 15 checks.
            if not isinstance(statement.body[0], ast.Assign) or not any(
                    isinstance(node, ast.Raise) for node in ast.walk(statement)):
                raise P13Blocked("P13_MATH_EXTRACTION_FAILURE_BLOCK_CHANGED")
            break
        body.append(copy.deepcopy(statement))
    if not body or not isinstance(body[-1], ast.Assign) or not any(
            isinstance(target, ast.Name) and target.id == "checks" for target in body[-1].targets):
        raise P13Blocked("P13_MATH_EXTRACTION_CHECKS_NOT_FINAL")
    final = ast.parse("return {\n"
        "'candidate_rows': candidate_rows, 'anchor_rows': anchor_rows, 'holdout_rows': holdout_rows,\n"
        "'holdout_global_energy_max': holdout_global_max['label'],\n"
        "'holdout_filtered_energy_max': holdout_qualified_max['label'],\n"
        "'graph_enumeration': graph_enumeration, 'acceptance_checks': checks,\n"
        "'tolerances': {'rounded_energy_identity_tolerance_kcal_mol': tolerance,\n"
        "'rounded_per_pi_tolerance_kcal_mol_electron': per_pi_tolerance,\n"
        "'benzene_CESE_per_pi_absolute_reference': benzene_reference}}\n").body[0]
    derived = ast.FunctionDef(name="reconstruct_fixed_mathematics",
        args=ast.arguments(posonlyargs=[], args=[ast.arg(arg="protocol")], kwonlyargs=[], kw_defaults=[], defaults=[]),
        body=body + [final], decorator_list=[])
    namespace = _compile_helpers(driver, FULL_HELPERS, Chem=chem, rdMolDescriptors=descriptors)
    module = ast.Module(body=[derived], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), "<locked-p13-run-mathematics-ast>", "exec"), namespace)
    extraction = {"method": "LOCKED_SOURCE_AST_MATH_BODY_WITH_IO_REMOVED",
        "retained_original_run_line_range": [body[0].lineno, body[-1].end_lineno],
        "retained_math_ast_sha256": _sha(ast.dump(ast.Module(body=body, type_ignores=[]), include_attributes=False).encode()),
        "helper_names": list(FULL_HELPERS), "math_expressions_modified": False,
        "removed": ["YAML file read (fixed bundled bytes loaded by adapter)",
                    "failure raise (checks retained in FAIL receipt)", "Git subprocess", "PDF path/read", "original CLI/output defaults"]}
    return namespace[derived.name], extraction


def _dependencies() -> tuple[Any, Any, Any, dict[str, str]]:
    modules: dict[str, Any] = {}
    missing: list[str] = []
    for name in ("yaml", "rdkit.Chem", "rdkit.Chem.rdMolDescriptors"):
        try:
            modules[name] = importlib.import_module(name)
        except ImportError:
            missing.append(name)
    if missing:
        raise P13Blocked("P13_REQUIRED_DEPENDENCIES_MISSING: " + ", ".join(missing))
    chem = modules["rdkit.Chem"]
    actual_rdkit = str(chem.rdBase.rdkitVersion)
    if actual_rdkit != REQUIRED_RDKIT_VERSION:
        raise P13Blocked(f"P13_RDKIT_VERSION_MISMATCH: expected {REQUIRED_RDKIT_VERSION}, actual {actual_rdkit}")
    return modules["yaml"], chem, modules["rdkit.Chem.rdMolDescriptors"], {
        "rdkit": actual_rdkit, "PyYAML": str(modules["yaml"].__version__)}


def _admit_output(output_dir: Path) -> Path:
    path = Path(output_dir).absolute()
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink() or (hasattr(ancestor, "is_junction") and ancestor.is_junction()):
            raise ValueError("P13_OUTPUT_LINK_REFUSED")
    for protected in (REFERENCE_DIR, RUNTIME_ROOT, ORIGINAL_DEVELOPMENT_DIR):
        if path == protected or protected in path.parents or path in protected.parents:
            raise ValueError("P13_OUTPUT_SOURCE_LOCATION_REFUSED")
    if path.exists():
        if not path.is_dir() or any(path.iterdir()):
            raise ValueError("P13_OUTPUT_MUST_BE_EMPTY_DIRECTORY")
    else:
        path.mkdir(parents=False)
    return path


def _report(record: dict[str, Any]) -> str:
    lines = ["# P13 固定表值与图规则复算", "", f"状态：`{record['status']}`。",
        f"范围：`{record['scope']}`；不是用户任意分子入口。",
        "", "本入口重算冻结 YAML 中的 ESE/CESE 账本、候选筛选与并苯图的完美匹配；分子式检查要求真实 RDKit。",
        "原2007量子程序与限制几何优化未复现；新增量子计算调用为0。",
        "主PDF：`NOT_REAUTHENTICATED`，实际PDF SHA-256为null。本次没有读取或重新认证原著正文。",
        "原驱动和YAML来自开发树未跟踪字节；记录捕获HEAD不代表该HEAD包含这些文件。", ""]
    if record.get("error"):
        lines.extend([f"拒绝/失败原因：{record['error']}", ""])
    if "graph_enumeration" in record:
        lines.extend(["| 环数 | RDKit分子式 | Kekulé数 | GL合格数 |", "|---:|---|---:|---:|"])
        for row in record["graph_enumeration"]:
            lines.append(f"| {row['ring_count']} | {row['formula']} | {row['kekule_count']} | {row['qualified_count']} |")
        lines.extend(["", f"冻结表候选/跨拓扑/留出行数：{len(record['candidate_rows'])}/{len(record['anchor_rows'])}/{len(record['holdout_rows'])}。",
            f"留出最高能量候选：{record['holdout_global_energy_max']}；GL过滤后：{record['holdout_filtered_energy_max']}。",
            "", "判读限定于所列冻结账本和规则层级，不认证全部PBH、历史优化或训练标签。", ""])
    lines.append(f"原15项检查执行状态：`{record['acceptance_execution_status']}`。")
    for name, passed in record["acceptance_checks"].items():
        lines.append(f"- `{'PASS' if passed else 'FAIL'}` {name}")
    lines.extend(["", "生产标签和AI训练资格均为false。", ""])
    return "\n".join(lines)


def run(output_dir: Path) -> dict[str, Any]:
    """Run the one registered fixed case; save PASS/BLOCKED/FAIL receipts."""
    output = _admit_output(output_dir)
    record: dict[str, Any] = {"schema_version": 1, "case_id": "P13", "proposition_id": "P13",
        "protocol_id": "p13-polycyclic-benzenoid/0.1", "status": "BLOCKED", "scope": SCOPE,
        "execution_lane": "FROZEN_TABLE_RECONSTRUCTION_PLUS_INDEPENDENT_GRAPH_RDKIT",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "new_quantum_calls": 0, "historical_quantum_program_reproduced": False,
        "original_monograph_program_code_used": False, "production_label": False, "training_eligible": False,
        "primary_pdf_status": "NOT_REAUTHENTICATED", "source_pdf_sha256": None,
        "source_pdf_declared_historical_sha256": None, "source_pdf_declared_hash_status": "NOT_SUPPLIED_BY_FROZEN_PROTOCOL",
        "source_pdf_reference": "10.6084/m9.figshare.27261243",
        "source_pdf_declared_reference": {
            "local_reference": "artifacts/reference_sources/Questioning_Fundamental_Principles_of_Organic_Chemistry_2024.pdf",
            "doi": "10.6084/m9.figshare.27261243", "status": "DECLARATION_ONLY_NOT_OPENED"},
        "acceptance_checks": {}, "acceptance_execution_status": "NOT_EXECUTED",
        "adapter_sha256": _sha(Path(__file__).read_bytes())}
    try:
        source = verify_sources()
        record["source_identity"] = source["metadata"]
        record["verified_source_sha256"] = source["source_sha256"]
        yaml, chem, descriptors, versions = _dependencies()
        protocol = yaml.safe_load(source["protocol_bytes"].decode("utf-8"))
        if not isinstance(protocol, dict) or protocol.get("protocol_id") != record["protocol_id"]:
            raise P13Blocked("P13_FIXED_PROTOCOL_IDENTITY_MISMATCH")
        record["source_reference_from_frozen_protocol"] = copy.deepcopy(protocol["source"])
        mathematics, extraction = _mathematics(source["driver_bytes"], chem, descriptors)
        computed = mathematics(protocol)
        if tuple(computed["acceptance_checks"]) != ACCEPTANCE_NAMES or any(
                type(value) is not bool for value in computed["acceptance_checks"].values()):
            raise P13Blocked("P13_ACCEPTANCE_CONTRACT_MISMATCH")
        record.update(computed)
        record.update({"dependency_versions": versions, "mathematics_extraction": extraction,
            "rdkit_formula_method": "PRESERVED_RWMOL_SANITIZE_CALCMOLFORMULA",
            "formula_fallback_used": False, "acceptance_execution_status": "EXECUTED",
            "registered_scientific_verdict": protocol["final_verdict_contract"]["verdict"],
            "relation_to_monograph": protocol["final_verdict_contract"]["relation_to_monograph"]})
        record["status"] = "PASS" if all(record["acceptance_checks"].values()) else "FAIL"
        if record["status"] == "FAIL":
            record["error"] = "P13_ACCEPTANCE_FAILED: " + ", ".join(name for name, passed in record["acceptance_checks"].items() if not passed)
    except P13Blocked as exc:
        record["error"] = str(exc)
    except Exception as exc:
        # Unexpected native/parser/runtime failures are preserved and cannot PASS.
        record["status"] = "FAIL"
        record["error"] = f"P13_EXECUTION_ERROR: {type(exc).__name__}: {exc}"
    with (output / "case-result.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    with (output / "case-report.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(_report(record))
    return record
