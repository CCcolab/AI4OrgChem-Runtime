"""Narrow metadata-only fallback for the frozen source Git reporter.

The scientific source bytes and subprocess module remain untouched. A worker
without a git executable records the reporter's existing ``unavailable``
sentinel, and the actual source-assets lock remains the scientific identity.
"""
from __future__ import annotations

import ast
import functools
import hashlib
import inspect
import json
from pathlib import Path
import sys
from types import ModuleType
from typing import Any


_REPORTER_MODULE = "experiments.validation.one_cut_conditional_scf_gate0"
_REPORTER_RELATIVE = "experiments/validation/one_cut_conditional_scf_gate0.py"
_LOCK_PATH = Path(__file__).resolve().parents[2] / "locks/protocol-cases-scientific-assets.json"
_STATE: dict[str, Any] | None = None


def _source_module(module: Any, root: Path) -> bool:
    if not isinstance(module, ModuleType):
        return False
    filename = vars(module).get("__file__")
    if not isinstance(filename, str):
        return False
    return Path(filename).resolve().is_relative_to(root)


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ValueError("Duplicate source-lock field: " + key)
        result[key] = value
    return result


def _identity(root: Path) -> dict[str, Any]:
    source = root / _REPORTER_RELATIVE
    if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(root):
        raise ValueError("Canonical Git reporter must be a regular source-tree asset")
    source_bytes = source.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    lock_bytes = Path(_LOCK_PATH).read_bytes()
    lock = json.loads(lock_bytes.decode("utf-8-sig"), object_pairs_hook=_pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite lock value: " + value)))
    expected = "reference/protocol_cases/source_tree/" + _REPORTER_RELATIVE
    entries = [row for row in lock["files"] if row["path"] == expected]
    if len(entries) != 1 or entries[0]["sha256"] != source_sha or entries[0]["size"] != len(source_bytes):
        raise ValueError("Canonical reporter bytes do not match the actual source-assets lock")
    blob = hashlib.sha1(b"blob " + str(len(source_bytes)).encode("ascii") + b"\0" + source_bytes).hexdigest()
    if entries[0]["captured_git_blob"] != blob:
        raise ValueError("Canonical reporter Git blob does not match source-assets lock")
    tree = ast.parse(source_bytes.decode("utf-8-sig"), filename=str(source))
    definitions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "git_commit"]
    if len(definitions) != 1:
        raise ValueError("Exactly one canonical Git reporter definition is required")
    # The original reporter returns this sentinel when Git exists but rev-parse
    # fails. This adapter extends only the missing-executable reporting case.
    fallback_values = [node.orelse.value for node in ast.walk(definitions[0])
                       if isinstance(node, ast.IfExp) and isinstance(node.orelse, ast.Constant)]
    if fallback_values != ["unavailable"]:
        raise ValueError("The original Git reporter fallback has changed")
    return {
        "source_assets_lock_path": "locks/protocol-cases-scientific-assets.json",
        "source_assets_lock_sha256": hashlib.sha256(lock_bytes).hexdigest(),
        "original_reporter": {
            "module": _REPORTER_MODULE, "name": "git_commit",
            "source_asset_path": expected, "source_file_sha256": source_sha,
            "source_file_size": len(source_bytes), "source_file_git_blob": blob,
            "registered_source_path": entries[0].get("source_path"),
            "registered_provenance": entries[0].get("provenance"),
            "fallback_sentinel": "unavailable",
        },
        "source_context_heads": sorted({row["source_context_head"] for row in lock["files"]
                                        if row.get("source_context_head") is not None}),
        "source_context_heads_role": "BACKGROUND_ONLY_NOT_A_GIT_SHA_REPLACEMENT_FOR_CAPTURED_FILES",
    }


def _wrapper(original: Any, metadata: dict[str, Any]) -> Any:
    @functools.wraps(original)
    def report(*args: Any, **kwargs: Any) -> Any:
        metadata["reporter_calls"] += 1
        try:
            result = original(*args, **kwargs)
        except FileNotFoundError as error:
            if error.filename != "git":
                raise
            metadata["fallback_events"].append({
                "exception_type": "FileNotFoundError", "filename": "git",
                "reported_value": "unavailable",
                "reason": "MISSING_GIT_EXECUTABLE_IN_REPORTING_ONLY_PATH",
                "scientific_identity_substituted": False,
            })
            return "unavailable"
        else:
            metadata["reporter_returns_without_fallback"] += 1
            return result
    return report


def apply(root: Path) -> dict[str, Any]:
    """Wrap loaded aliases of one original reporter before entering the guard.

    The returned metadata is deliberately shared: later fallback events appear
    in the final worker report. Repeated application adds newly imported aliases
    without stacking wrappers. A process cannot mix captured source roots.
    """
    global _STATE
    root = Path(root).resolve()
    if _STATE is not None and _STATE["root"] != root:
        raise ValueError("Reporting adapter cannot mix scientific source roots")
    identity = _identity(root)
    if _STATE is None:
        metadata = {
            "schema": "protocol-case-provenance-reporting-v1",
            "source_tree_root": str(root), "status": "NOT_APPLICABLE_NO_LOADED_REPORTER",
            "scope": "REPORTING_ONLY_NO_SCIENTIFIC_PARAMETERS_OR_SUBPROCESS_PATCH",
            "reason": "ONLY_MISSING_GIT_EXECUTABLE_EXTENDS_ORIGINAL_UNAVAILABLE_SENTINEL",
            "scientific_sources_modified": False, "git_sha_fabricated": False,
            "wrapped_aliases": [], "fallback_events": [],
            "reporter_calls": 0, "reporter_returns_without_fallback": 0,
            **identity,
        }
        _STATE = {"root": root, "metadata": metadata, "original": None,
                  "wrapper": None, "bindings": []}
    elif any(_STATE["metadata"][key] != value for key, value in identity.items()):
        raise ValueError("Reporting source identity changed after initial application")
    state, metadata = _STATE, _STATE["metadata"]
    for owner, name in state["bindings"]:
        if vars(owner).get(name) is not state["wrapper"]:
            raise ValueError("A previously installed reporter alias changed")
    canonical = sys.modules.get(_REPORTER_MODULE)
    if canonical is None:
        return metadata
    if not _source_module(canonical, root):
        raise ValueError("Loaded canonical reporter is outside the captured source tree")
    current = vars(canonical).get("git_commit")
    if state["original"] is None:
        if (not inspect.isfunction(current) or current.__name__ != "git_commit"
                or current.__module__ != _REPORTER_MODULE
                or Path(inspect.getsourcefile(current) or "").resolve() != (root / _REPORTER_RELATIVE).resolve()):
            raise ValueError("Canonical reporter function identity differs")
        state["original"] = current
        state["wrapper"] = _wrapper(current, metadata)
    elif current is not state["wrapper"]:
        raise ValueError("Canonical reporter changed after application")
    targets = []
    seen: set[tuple[int, str]] = set()
    for module in tuple(sys.modules.values()):
        if not _source_module(module, root):
            continue
        for name, value in tuple(vars(module).items()):
            if value is state["original"] or value is state["wrapper"]:
                key = (id(module), name)
                if key not in seen:
                    targets.append((module, name))
                    seen.add(key)
    known = {(id(owner), name) for owner, name in state["bindings"]}
    for owner, name in targets:
        if (id(owner), name) not in known:
            setattr(owner, name, state["wrapper"])
            state["bindings"].append((owner, name))
            metadata["wrapped_aliases"].append({"module": owner.__name__, "attribute": name,
                                                "module_source_path": str(Path(owner.__file__).resolve().relative_to(root))})
    metadata["wrapped_aliases"].sort(key=lambda row: (row["module"], row["attribute"]))
    metadata["status"] = "APPLIED_REPORTING_ONLY"
    return metadata
