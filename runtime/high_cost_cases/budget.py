"""Durable accounting for the closed, local third-batch state allowlist.

No launch, retry, resume, budget reset, or second-batch migration is provided.
An unresolved container keeps its full reservation charged.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import uuid

SCHEMA = "high-cost-batch3-budget-v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/+-]{0,191}\Z")
_BINDINGS = ("profile_sha256", "source_sha256", "dependencies_sha256")
_TOP = {"schema", "batch_id", "units", *_BINDINGS, "ceiling_seconds",
        "attempts", "automatic_retry", "resume", "batch2_budget_reused",
        "created_utc", "updated_utc", "integrity_sha256"}


class BudgetError(ValueError):
    pass


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _identifier(value, label):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise BudgetError("Invalid bounded " + label)
    return value


def _positive(value, label):
    if type(value) is not int or value <= 0:
        raise BudgetError(label + " must be a positive integer")
    return value


def _seconds(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise BudgetError("Charged seconds must be finite and nonnegative")
    return float(value)


def _hash(value, label):
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise BudgetError("Full lowercase SHA-256 required: " + label)
    return value


def _path(path):
    result = Path(path).absolute()
    for item in (result, *result.parents):
        if item.is_symlink():
            raise BudgetError("Budget ancestry must not be a symlink")
        if item.exists():
            attributes = getattr(item.lstat(), "st_file_attributes", 0)
            if attributes & 1024:
                raise BudgetError("Budget ancestry must not be a reparse point")
    return result


@contextmanager
def _lock(path):
    """One nonblocking OS lock; never remove another process' lock file."""
    path = _path(path)
    with path.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0"); stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise BudgetError("Another process holds this third-batch budget") from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _write(path, value):
    value["updated_utc"] = _utc()
    value.pop("integrity_sha256", None)
    value["integrity_sha256"] = hashlib.sha256(_canonical(value)).hexdigest()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".",
                                         suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(_canonical(value) + b"\n")
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _read(path):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 16 * 1024 * 1024:
        raise BudgetError("Existing third-batch budget is missing, unsafe or oversized")
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise BudgetError("Duplicate ledger key: " + key)
            result[key] = value
        return result
    def constant(value):
        raise BudgetError("Nonfinite ledger value: " + value)
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                           parse_constant=constant)
        _canonical(value)
    except (OSError, ValueError, TypeError) as error:
        raise BudgetError("Existing budget is invalid; it was not reset") from error
    if not isinstance(value, dict) or value.get("schema") != SCHEMA or set(value) != _TOP:
        raise BudgetError("Only the closed third-batch schema is accepted; no migration/reset")
    unsigned = dict(value); checksum = unsigned.pop("integrity_sha256")
    if checksum != hashlib.sha256(_canonical(unsigned)).hexdigest():
        raise BudgetError("Third-batch budget integrity differs")
    _identifier(value["batch_id"], "batch ID")
    for key in _BINDINGS:
        _hash(value[key], key)
    _positive(value["ceiling_seconds"], "ceiling_seconds")
    units = value["units"]
    if not isinstance(units, list) or not units or units != sorted(set(units)):
        raise BudgetError("A unique frozen third-batch unit allowlist is required")
    for unit in units:
        _identifier(unit, "unit ID")
    if any(value[key] is not False for key in ("automatic_retry", "resume", "batch2_budget_reused")):
        raise BudgetError("Retry, resume and old-budget reuse are forbidden")
    if not isinstance(value["attempts"], dict):
        raise BudgetError("Invalid third-batch attempts")
    executions = set()
    for unit, row in value["attempts"].items():
        if unit not in units or not isinstance(row, dict):
            raise BudgetError("Attempt is outside the frozen state allowlist")
        required = {"unit_id", "execution_id", "reservation_token", "reserved_seconds",
                    "resources", "identity", "identity_sha256", "state", "charged_seconds",
                    "reserved_utc", "container_removed", "worker_status"}
        optional = {"settled_utc", "observed_charged_seconds", "last_observed_utc"}
        if not required <= set(row) or set(row) - required - optional:
            raise BudgetError("Closed attempt record required")
        if row["unit_id"] != unit:
            raise BudgetError("Attempt unit identity differs")
        execution = _identifier(row["execution_id"], "execution ID")
        if execution in executions:
            raise BudgetError("Execution identity reused across states")
        executions.add(execution)
        if not isinstance(row["reservation_token"], str) or not re.fullmatch(r"[0-9a-f]{32}", row["reservation_token"]):
            raise BudgetError("Full reservation token required")
        reserved = _positive(row["reserved_seconds"], "reserved_seconds")
        if not isinstance(row["resources"], dict) or row["resources"].get("hard_wall_seconds") != reserved or type(row["resources"].get("hard_wall_seconds")) is not int:
            raise BudgetError("Reserved wall differs from the recorded resource contract")
        _validate_identity(row["identity"], value, unit)
        if row["identity_sha256"] != hashlib.sha256(_canonical(row["identity"])).hexdigest():
            raise BudgetError("Attempt identity hash differs")
        charge = _seconds(row["charged_seconds"])
        if row["state"] == "RESERVED":
            if charge != reserved or row["container_removed"] is True:
                raise BudgetError("An unresolved reservation must remain fully charged")
        elif row["state"] == "SETTLED":
            if row["container_removed"] is not True or "settled_utc" not in row:
                raise BudgetError("Settled attempt requires confirmed container removal")
        else:
            raise BudgetError("Unknown third-batch attempt state")
        if not isinstance(row["worker_status"], str) or not 1 <= len(row["worker_status"]) <= 256:
            raise BudgetError("Explicit bounded worker status required")
    return value


def _validate_identity(identity, ledger, unit):
    if not isinstance(identity, dict):
        raise BudgetError("A finite JSON execution identity is required")
    for key in _BINDINGS:
        if _hash(identity.get(key), key) != ledger[key]:
            raise BudgetError("Execution differs from this batch identity: " + key)
    if "unit_id" in identity and identity["unit_id"] != unit:
        raise BudgetError("Execution unit identity differs")
    _canonical(identity)


def _snapshot(value):
    result = json.loads(_canonical(value))
    result["charged_seconds"] = math.fsum(row["charged_seconds"] for row in value["attempts"].values())
    result["remaining_seconds"] = max(0.0, value["ceiling_seconds"] - result["charged_seconds"])
    result["unresolved_units"] = sorted(unit for unit, row in value["attempts"].items() if row["state"] == "RESERVED")
    result["over_budget"] = result["charged_seconds"] > value["ceiling_seconds"]
    return result


def new_budget(path, units, profile_sha256, source_sha256, dependencies_sha256, ceiling_seconds):
    """Create once, or reopen only the exact same frozen batch identity."""
    path = _path(path)
    if not isinstance(units, (list, tuple)) or not units or len(set(units)) != len(units):
        raise BudgetError("A nonempty unique unit ID list is required")
    units = sorted(_identifier(unit, "unit ID") for unit in units)
    bindings = dict(zip(_BINDINGS, (profile_sha256, source_sha256, dependencies_sha256)))
    for key, value in bindings.items():
        _hash(value, key)
    _positive(ceiling_seconds, "ceiling_seconds")
    frozen = {"units": units, **bindings, "ceiling_seconds": ceiling_seconds}
    batch_id = "batch3-" + hashlib.sha256(_canonical(frozen)).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock(path.with_name(path.name + ".lock")):
        if path.exists() or path.is_symlink():
            value = _read(path)
            if value["batch_id"] != batch_id or any(value[key] != wanted for key, wanted in frozen.items()):
                raise BudgetError("Existing batch identity differs; resetting is forbidden")
        else:
            value = {"schema": SCHEMA, "batch_id": batch_id, **frozen, "attempts": {},
                     "automatic_retry": False, "resume": False, "batch2_budget_reused": False,
                     "created_utc": _utc()}
            _write(path, value)
        return _snapshot(value)


def reserve(path, unit, resources, identity, execution_id):
    """Reserve one state's entire hard wall before launching any worker."""
    path = _path(path); _identifier(unit, "unit ID"); _identifier(execution_id, "execution ID")
    if not isinstance(resources, dict):
        raise BudgetError("A fixed resource contract is required")
    reserved = _positive(resources.get("hard_wall_seconds"), "hard_wall_seconds")
    resources = json.loads(_canonical(resources)); identity = json.loads(_canonical(identity))
    with _lock(path.with_name(path.name + ".lock")):
        value = _read(path)
        if unit not in value["units"]:
            raise BudgetError("Unit is outside the frozen third-batch allowlist")
        _validate_identity(identity, value, unit)
        if unit in value["attempts"]:
            raise BudgetError("This state already has an attempt; retry/resume forbidden")
        if any(row["execution_id"] == execution_id for row in value["attempts"].values()):
            raise BudgetError("Execution identity already exists")
        snapshot = _snapshot(value)
        if snapshot["unresolved_units"]:
            raise BudgetError("An unresolved third-batch state remains; concurrent launch refused")
        if reserved > snapshot["remaining_seconds"]:
            raise BudgetError("Insufficient independent third-batch wall budget")
        token = uuid.uuid4().hex
        row = {"unit_id": unit, "execution_id": execution_id, "reservation_token": token,
               "reserved_seconds": reserved, "resources": resources, "identity": identity,
               "identity_sha256": hashlib.sha256(_canonical(identity)).hexdigest(),
               "state": "RESERVED", "charged_seconds": reserved, "reserved_utc": _utc(),
               "container_removed": False, "worker_status": "NOT_EXECUTED_RESERVED"}
        value["attempts"][unit] = row
        _write(path, value)
        return {key: row[key] for key in ("reservation_token", "execution_id", "unit_id", "reserved_seconds", "identity_sha256")}


def settle(path, execution_id, charged_seconds, container_removed, worker_status):
    """Charge failures too; uncertain cleanup leaves the full reservation held."""
    path = _path(path); _identifier(execution_id, "execution ID"); charged = _seconds(charged_seconds)
    if type(container_removed) is not bool:
        raise BudgetError("Container removal must be a boolean observation")
    if not isinstance(worker_status, str) or not 1 <= len(worker_status) <= 256:
        raise BudgetError("Explicit bounded worker status required")
    with _lock(path.with_name(path.name + ".lock")):
        value = _read(path)
        rows = [row for row in value["attempts"].values() if row["execution_id"] == execution_id]
        if len(rows) != 1 or rows[0]["state"] != "RESERVED":
            raise BudgetError("Only one outstanding execution can be settled, once")
        row = rows[0]
        row.update(worker_status=worker_status, observed_charged_seconds=charged, last_observed_utc=_utc())
        if container_removed:
            row.update(state="SETTLED", charged_seconds=charged, container_removed=True, settled_utc=_utc())
        _write(path, value)
        return _snapshot(value)
