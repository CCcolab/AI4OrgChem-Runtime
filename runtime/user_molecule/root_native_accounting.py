"""Durable single-path callback/NR accounting, without scientific execution.

This layer records delegate dispatch. The caller's source-binding factory must
check actual molecule/grid/XC/density objects and validate the returned operator.
Neither a mode string nor a callback-slot count authenticates a molecular F.
"""
from __future__ import annotations

from collections.abc import Mapping
import copy
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import threading

from .acceptance_resources import _atomic_write, _canonical
from .residual_budget import ConditionalCallbackBudget


PATH_ID = "independent_reference"
LIMIT = 201
MODES = frozenset(("ENGINEERING_SIMULATED_NATIVE", "SOURCE_NATIVE_DIAGNOSTIC"))
PHASES = frozenset(("CURRENT_INITIAL", "OPTIMIZER_BASE", "FD_SAMPLE",
                    "FINAL_RETURNED_DENSITY", "FINAL_RAW_AUFBAU_DENSITY_RECHECK"))
GROUP_STATUSES = frozenset(("ADMITTED", "STARTED", "COMPLETED",
                           "REFUSED_PARTIAL_NO_RETRY", "REFUSED_ZERO_CALLBACKS"))


class NativeAccountingError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CallbackToken:
    slot_id: int
    path_id: str
    density_id: str
    phase: str


def _sha(value, name):
    if not isinstance(value, str) or re.fullmatch("[0-9a-f]{64}", value) is None:
        raise NativeAccountingError(name + " must be a full lowercase SHA-256")
    return value


def _integer(value, name, low=0, high=LIMIT):
    if type(value) is not int or not low <= value <= high:
        raise NativeAccountingError(name + " must be an exact bounded integer")
    return value


def _plain(value):
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if isinstance(value, Mapping) and all(type(key) is str for key in value):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    raise NativeAccountingError("Finite, plain JSON metadata is required")


def _append_jsonl(path, value):
    raw = _canonical(value) + b"\n"
    with Path(path).open("ab") as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())


class RootNativeAccounting:
    """One fresh 201-slot path; no resume, budget refill, engine or SCF calls."""

    def __init__(self, output_dir, journal, *, execution_kind="ENGINEERING_SIMULATED_NATIVE",
                 scientific_execution_authorized=False):
        if not isinstance(journal, ConditionalCallbackBudget):
            raise NativeAccountingError("Explicit ConditionalCallbackBudget required")
        if not isinstance(execution_kind, str) or execution_kind not in MODES or type(scientific_execution_authorized) is not bool:
            raise NativeAccountingError("Explicit accounting mode and exact boolean required")
        wanted = execution_kind == "SOURCE_NATIVE_DIAGNOSTIC"
        if scientific_execution_authorized is not wanted:
            raise NativeAccountingError("Source accounting requires separate explicit authorization; simulation requires False")
        self.journal, self.kind, self.authorized = journal, execution_kind, wanted
        self._identity = _plain(journal.identity)
        self._identity_digest = hashlib.sha256(_canonical(self._identity)).hexdigest()
        self._journal_binding = (journal.path, journal.lock_path, journal.batch_id)
        self._lock = threading.RLock()
        self._rows, self._groups = [], {}
        self._active_token = None
        self._closed = self._failed = self._poisoned = False
        self._stop_reason = None
        self._assert_authorization()
        snapshot = journal.snapshot()
        if (snapshot["charged_slots"] or snapshot["pending_slots"] or snapshot["failed_slots"]
                or set(snapshot["paths"]) != {PATH_ID} or snapshot["paths"][PATH_ID]["state"] != "OPEN"):
            raise NativeAccountingError("A fresh empty OPEN journal is required; no resume/retry")
        self.output = Path(output_dir).absolute()
        if self.output.is_symlink() or (hasattr(self.output, "is_junction") and self.output.is_junction()):
            raise NativeAccountingError("Accounting output cannot be a link")
        if self.output.exists():
            if not self.output.is_dir() or any(self.output.iterdir()):
                raise NativeAccountingError("Fresh empty accounting output required; no resume")
        else:
            self.output.mkdir(parents=False, exist_ok=False)
        self.events = self.output / "native-events.jsonl"
        self.slots = self.output / "callback-slots.jsonl"
        self.admissions = self.output / "admissions.jsonl"
        self.state = self.output / "accounting-state.json"
        with (self.output / "ACCOUNTING_STARTED.json").open("xb") as stream:
            stream.write(_canonical({"schema": "root-native-accounting-v1", "execution_kind": self.kind,
                "identity_sha256": self._identity_digest, "scientific_execution_authorized": self.authorized,
                "resume": False}) + b"\n"); stream.flush(); os.fsync(stream.fileno())
        self._persist()

    def _assert_authorization(self):
        if (self.journal.limits != {PATH_ID: LIMIT} or self.journal.total_limit != LIMIT
                or (self.journal.path, self.journal.lock_path, self.journal.batch_id) != self._journal_binding
                or _plain(self.journal.identity) != self._identity
                or hashlib.sha256(_canonical(self.journal.identity)).hexdigest() != self._identity_digest):
            raise NativeAccountingError("Journal identity/limits changed")
        identity = self._identity
        if (identity.get("mode") != self.kind or identity.get("execution_kind", self.kind) != self.kind
                or type(identity.get("scientific_execution_authorized")) is not bool
                or identity["scientific_execution_authorized"] is not self.authorized):
            raise NativeAccountingError("Journal mode/authorization pairing differs; old root modes cannot authorize this layer")

    def _assert_open(self):
        self._assert_authorization()
        if self._closed or self._failed or self._poisoned:
            raise NativeAccountingError("Accounting stopped; no retry, refill or continuation")
        budget = self._budget_owned()
        return budget

    def _budget_owned(self):
        self._assert_authorization()
        budget = self.journal.snapshot()
        if (budget["charged_slots"] != len(self._rows) or budget["paths"][PATH_ID]["state"] != ("CLOSED" if self._closed else "OPEN")):
            raise NativeAccountingError("Journal was externally charged/closed")
        for actual, owned in zip(budget["slots"], self._rows):
            if any(actual[key] != owned[key] for key in ("slot_id", "path_id", "density_id", "phase", "status")):
                raise NativeAccountingError("Journal slot binding/status changed outside accounting")
            if actual["operator_id"] != (owned["operator_id"] if owned["status"] == "SUCCEEDED" else None):
                raise NativeAccountingError("Journal operator identity changed outside accounting")
        return budget

    def _token_row(self, token):
        self._assert_authorization()
        if self._closed or token is not self._active_token:
            raise NativeAccountingError("Exact active token required; token cannot be reused or forged")
        row = self._rows[-1]
        budget = self._budget_owned()
        if (budget["charged_slots"] != len(self._rows) or budget["paths"][PATH_ID]["state"] != "OPEN"
                or budget["slots"][-1]["status"] != "PENDING"
                or any(budget["slots"][-1][key] != getattr(token, key)
                       for key in ("slot_id", "path_id", "density_id", "phase"))):
            raise NativeAccountingError("Active slot binding/status differs")
        return row

    def _binding(self, token, binding):
        if not isinstance(binding, Mapping):
            raise NativeAccountingError("Explicit native context binding required")
        plain = _plain(binding)
        if (type(plain.get("slot_id")) is not int or any(plain.get(key) != getattr(token, key)
                for key in ("slot_id", "path_id", "density_id", "phase"))):
            raise NativeAccountingError("Native slot/path/D/phase context differs")
        return plain

    def _write(self, path, value):
        try:
            _append_jsonl(path, value)
        except BaseException:
            self._poisoned = self._failed = True
            raise

    def _persist(self):
        try:
            _atomic_write(self.state, self._snapshot_unlocked())
        except BaseException:
            self._poisoned = self._failed = True
            raise

    def _event(self, kind, token, **metadata):
        self._write(self.events, {"event": kind, "execution_kind": self.kind,
            "slot_id": token.slot_id, "path_id": token.path_id, "density_id": token.density_id,
            "phase": token.phase, **metadata})

    def _candidate_context(self, density_id, phase, context, count):
        value = None if context is None else _plain(context)
        grouped = phase in ("FD_SAMPLE", "FINAL_RETURNED_DENSITY", "FINAL_RAW_AUFBAU_DENSITY_RECHECK")
        if value is not None:
            if (not isinstance(value, dict) or type(value.get("evaluation_count")) is not int
                    or value["evaluation_count"] != count + 1 or value.get("density_id") != density_id
                    or value.get("phase") != phase):
                raise NativeAccountingError("Candidate evaluation/D/phase context differs")
        if not grouped:
            if value is not None and value.get("admission_group_id") is not None:
                raise NativeAccountingError("Ungrouped callback cannot borrow a group")
            return value, None
        if value is None or type(value.get("admission_group_id")) is not int:
            raise NativeAccountingError("FD/tail requires an explicit STARTED admission group")
        group_id = value["admission_group_id"]; group = self._groups.get(group_id)
        wanted = "COMPLETE_JACOBIAN" if phase == "FD_SAMPLE" else "FINAL_TAIL"
        if not group or group["row"]["status"] != "STARTED" or group["row"]["kind"] != wanted:
            raise NativeAccountingError("Callback has no matching STARTED admission")
        supplied = group["row"]
        for key in ("base_snapshot_id", "base_density_id", "base_operator_id"):
            if value.get(key) != supplied[key]:
                raise NativeAccountingError("Candidate admission base binding differs: " + key)
        used = len(group["slots"])
        if used >= supplied["planned_callbacks"]:
            raise NativeAccountingError("Admission group callback count exhausted")
        if phase == "FD_SAMPLE":
            if type(value.get("fd_sample")) is not int or value["fd_sample"] != used + 1:
                raise NativeAccountingError("Explicit ordered FD sample identity required")
        elif phase != ("FINAL_RETURNED_DENSITY" if used == 0 else "FINAL_RAW_AUFBAU_DENSITY_RECHECK"):
            raise NativeAccountingError("Tail callback order differs")
        return value, group_id

    def begin_callback(self, density_id, phase, *, candidate_context=None):
        with self._lock:
            budget = self._assert_open()
            if self._active_token is not None:
                raise NativeAccountingError("Only one callback may be active")
            _sha(density_id, "density_id")
            if phase not in PHASES:
                raise NativeAccountingError("Explicit candidate phase required")
            if phase == "CURRENT_INITIAL" and self._rows:
                raise NativeAccountingError("Initial callback cannot be repeated")
            if not self._rows and phase != "CURRENT_INITIAL":
                raise NativeAccountingError("A fresh CURRENT_INITIAL callback must be first")
            if not self._rows and "initial_density_id" in self._identity and self._identity["initial_density_id"] != density_id:
                raise NativeAccountingError("Initial D differs from the journal identity")
            context, group_id = self._candidate_context(density_id, phase, candidate_context, len(self._rows))
            if phase not in ("CURRENT_INITIAL", "FINAL_RETURNED_DENSITY", "FINAL_RAW_AUFBAU_DENSITY_RECHECK") and budget["remaining_slots"] <= 2:
                raise NativeAccountingError("The two original tail slots cannot be borrowed")
            charged = self.journal.charge(PATH_ID, density_id, phase)
            token = CallbackToken(charged["slot_id"], PATH_ID, density_id, phase)
            row = {**charged, "candidate_context": context, "admission_group_id": group_id,
                "evaluator_dispatch_entered": True, "matched_operator_completed": False,
                "nr_entered": 0, "nr_completed": 0, "nr_failed": 0, "native_failure": None}
            self._rows.append(row); self._active_token = token
            if group_id is not None:
                self._groups[group_id]["slots"].append(token.slot_id)
            self._write(self.slots, {"event": "CALLBACK_PRECHARGED", "row": copy.deepcopy(row)})
            self._persist()
            return token

    def native_nr(self, token, callback, *, context_binding):
        with self._lock:
            row = self._token_row(token)
            if self._failed or self._poisoned or row["nr_entered"] or row["native_failure"] is not None:
                raise NativeAccountingError("One native dispatch per slot; no retry")
            try:
                if not callable(callback):
                    raise NativeAccountingError("Native delegate must be callable")
                binding = self._binding(token, context_binding)
            except BaseException as error:
                row["native_failure"] = type(error).__name__ + ": " + str(error)
                self._failed = True
                raise
            # This durable boundary is intent, not proof that the delegate was
            # entered if storage/process failure intervenes. Exact counts below
            # increment only immediately before the delegate invocation.
            self._event("NR_ENTERED", token, context_binding=binding,
                evidence_role="PERSISTED_PRE_INVOKE_DISPATCH_INTENT_NOT_CRASH_PROOF_OF_ENTRY")
            row["nr_entered"] = 1
            try:
                value = callback()
            except BaseException as error:
                row["nr_failed"] = 1; self._failed = True
                row["native_failure"] = (type(error).__name__ + ": " + str(error))[:2048]
                self._event("NR_FAILED", token, detail=row["native_failure"], observed_dispatch_entered=True)
                self._persist()
                raise
            row["nr_completed"] = 1
            self._event("NR_COMPLETED", token, observed_dispatch_entered=True)
            self._persist()
            return value

    def finish_callback(self, token, operator_id, *, context_binding=None):
        with self._lock:
            row = self._token_row(token)
            _sha(operator_id, "operator_id")
            if context_binding is not None:
                self._binding(token, context_binding)
            if self._failed or self._poisoned or (row["nr_entered"], row["nr_completed"], row["nr_failed"]) != (1, 1, 0):
                raise NativeAccountingError("Success requires exactly one completed NR and intact persistence")
            # Save the validated intent before settling the durable budget.
            self._write(self.slots, {"event": "MATCHED_OPERATOR_VALIDATED", "slot_id": token.slot_id,
                "operator_id": operator_id, "factory_operator_validation_required": True})
            row.update(operator_id=operator_id, matched_operator_completed=True)
            # Persist validated PENDING state first. If that write fails, the
            # budget has not been marked successful. Budget settlement is the
            # last fallible write on this successful callback path.
            self._persist()
            try:
                self.journal.finish(token.slot_id, status="SUCCEEDED", operator_id=operator_id)
            except BaseException:
                self._poisoned = self._failed = True
                raise
            row.update(status="SUCCEEDED")
            self._active_token = None
            return copy.deepcopy(row)

    def fail_callback(self, token, error):
        with self._lock:
            row = self._token_row(token)
            detail = (type(error).__name__ + ": " + str(error))[:2048]
            self._failed = True
            self.journal.finish(token.slot_id, status="FAILED", detail=detail)
            row.update(status="FAILED", failure_detail=detail)
            self._active_token = None
            self._write(self.slots, {"event": "CALLBACK_FAILED_NO_REFUND", "slot_id": token.slot_id, "detail": detail})
            self._persist()
            return copy.deepcopy(row)

    def record_admission(self, row):
        """Persist explicit solver-hook groups; never infer them from FD phases."""
        with self._lock:
            self._assert_authorization()
            if self._closed or self._poisoned:
                raise NativeAccountingError("Stopped accounting cannot record a new admission")
            value = _plain(row)
            if not isinstance(value, dict):
                raise NativeAccountingError("Admission must be a plain metadata object")
            group_id = _integer(value.get("group_id"), "group_id", 1)
            kind, status = value.get("kind"), value.get("status")
            if kind not in ("COMPLETE_JACOBIAN", "FINAL_TAIL") or status not in GROUP_STATUSES:
                raise NativeAccountingError("Explicit admission kind/status required")
            planned, reserve = (96, 2) if kind == "COMPLETE_JACOBIAN" else (2, 0)
            if (type(value.get("planned_callbacks")) is not int or value["planned_callbacks"] != planned
                    or type(value.get("tail_callbacks_reserved")) is not int or value["tail_callbacks_reserved"] != reserve
                    or type(value.get("admitted")) is not bool):
                raise NativeAccountingError("Original 96+2/2+0 admission contract required")
            actual = _integer(value.get("actual_callbacks"), "actual_callbacks", 0, planned)
            count = _integer(value.get("call_count_before"), "call_count_before")
            remaining = _integer(value.get("remaining_callbacks"), "remaining_callbacks")
            _sha(value.get("base_density_id"), "base_density_id"); _sha(value.get("base_operator_id"), "base_operator_id")
            if "unexecuted_planned_callbacks" in value:
                _integer(value["unexecuted_planned_callbacks"], "unexecuted_planned_callbacks", 0, planned)
                if value["unexecuted_planned_callbacks"] != planned - actual:
                    raise NativeAccountingError("Unexecuted group count differs")
            for field in ("failure_type", "failure_detail", "stop_reason"):
                if field in value and (not isinstance(value[field], str) or len(value[field]) > 2048):
                    raise NativeAccountingError("Bounded terminal admission detail required")
            if not isinstance(value.get("base_snapshot_id"), str) or not 1 <= len(value["base_snapshot_id"]) <= 128:
                raise NativeAccountingError("Explicit bounded base snapshot identity required")
            old = self._groups.get(group_id)
            if old is None:
                budget = self._assert_open()
                if self._active_token is not None or group_id != len(self._groups) + 1 or status not in ("ADMITTED", "REFUSED_ZERO_CALLBACKS") or actual:
                    raise NativeAccountingError("A fresh ordered admission must precede callbacks")
                if any(group["row"]["status"] in ("ADMITTED", "STARTED") for group in self._groups.values()):
                    raise NativeAccountingError("An earlier group remains unresolved")
                affordable = budget["remaining_slots"] >= planned + reserve
                if (count != budget["charged_slots"] or remaining != budget["remaining_slots"]
                        or value["admitted"] is not affordable or (status == "ADMITTED") is not affordable):
                    raise NativeAccountingError("Whole-group affordability or declared budget differs")
                if not any(item["status"] == "SUCCEEDED" and item["density_id"] == value["base_density_id"]
                           and item["operator_id"] == value["base_operator_id"]
                           and value["base_snapshot_id"] == "evaluation-" + str(item["slot_id"]) for item in self._rows):
                    raise NativeAccountingError("Admission base has no matched successful operator")
                group = {"row": value, "slots": []}
                self._groups[group_id] = group
            else:
                dynamic = {"status", "actual_callbacks", "unexecuted_planned_callbacks", "failure_type", "failure_detail", "stop_reason"}
                invariant = {key: item for key, item in old["row"].items() if key not in dynamic}
                supplied = {key: item for key, item in value.items() if key not in dynamic}
                if invariant != supplied or not ((old["row"]["status"] == "ADMITTED" and status == "STARTED")
                        or (old["row"]["status"] == "STARTED" and status in ("COMPLETED", "REFUSED_PARTIAL_NO_RETRY"))):
                    raise NativeAccountingError("Admission transition/immutable metadata differs")
                if self._active_token is not None or actual != len(old["slots"]):
                    raise NativeAccountingError("Admission must settle exact completed/failed slot counts")
                if status == "STARTED" and actual:
                    raise NativeAccountingError("STARTED cannot claim prior group callbacks")
                if status == "COMPLETED":
                    if (kind == "COMPLETE_JACOBIAN" and actual != 96) or (kind == "FINAL_TAIL" and actual not in (1, 2)):
                        raise NativeAccountingError("Complete Jacobian/tail callback count differs")
                    if self._failed or any(self._rows[index - 1]["status"] != "SUCCEEDED" for index in old["slots"]):
                        raise NativeAccountingError("Failed callbacks cannot complete an admission")
                old["row"] = value
            self._write(self.admissions, value)
            if status in ("REFUSED_PARTIAL_NO_RETRY", "REFUSED_ZERO_CALLBACKS"):
                self._failed = True
            self._persist()
            return copy.deepcopy(value)

    def close(self, reason):
        with self._lock:
            self._assert_authorization()
            if self._closed or not isinstance(reason, str) or not 1 <= len(reason) <= 256:
                raise NativeAccountingError("One bounded stop reason required; no reopen")
            self._budget_owned()
            if self._active_token is not None:
                token = self._active_token; row = self._rows[-1]
                self.journal.finish(token.slot_id, status="FAILED", detail="Closed with unresolved callback; no refund")
                row.update(status="FAILED", failure_detail="CLOSED_UNRESOLVED_CALLBACK_NO_REFUND")
                self._active_token = None; self._failed = True
            if any(group["row"]["status"] in ("ADMITTED", "STARTED") for group in self._groups.values()):
                self._failed = True
            self.journal.close_path(PATH_ID, reason)
            self._closed = True; self._stop_reason = reason
            self._persist()
            return self._snapshot_unlocked()

    def _snapshot_unlocked(self):
        budget = self._budget_owned()
        nr = {name: sum(row["nr_" + name] for row in self._rows) for name in ("entered", "completed", "failed")}
        source = ({"status": "OBSERVED_DISPATCH_EVENTS_FACTORY_BINDING_REQUIRED", **nr} if self.kind == "SOURCE_NATIVE_DIAGNOSTIC"
                  else {"status": "UNOBSERVED_BY_SIMULATED_ACCOUNTING_USE_ENGINEERING_GUARD", "entered": None, "completed": None, "failed": None})
        return {"schema": "root-native-accounting-v1", "execution_kind": self.kind,
            "scientific_execution_authorized": self.authorized, "identity_sha256": self._identity_digest,
            "status": "PERSISTENCE_FAILED_NO_SUCCESS" if self._poisoned else
                ("CLOSED_FAILED_NO_RETRY" if self._closed and self._failed else "CLOSED" if self._closed else "FAILED_NO_RETRY" if self._failed else "OPEN"),
            "closed": self._closed, "stop_reason": self._stop_reason, "persistence_intact": not self._poisoned,
            "callback_slots": {"charged": len(self._rows), "pending": sum(row["status"] == "PENDING" for row in self._rows),
                "succeeded": sum(row["status"] == "SUCCEEDED" for row in self._rows),
                "failed": sum(row["status"] == "FAILED" for row in self._rows), "limit": LIMIT},
            "callback_budget": {key: copy.deepcopy(budget[key]) for key in
                ("charged_slots", "pending_slots", "failed_slots", "path_charged_slots", "remaining_slots", "paths")},
            "evaluator_dispatch": {"entered": len(self._rows), "matched_operator_completed": sum(row["matched_operator_completed"] for row in self._rows),
                "functional_source_entry": "NOT_OBSERVED_BY_THIS_LAYER"},
            "nr_dispatch_counts": nr, "engineering_simulated_native_counts": nr if self.kind == "ENGINEERING_SIMULATED_NATIVE" else None,
            "source_native_dispatch_counts": source,
            "native_evidence_scope": "DELEGATE_DISPATCH_AND_RETURN_NOT_AUTHENTICATION_OF_PYSCF_OR_OPERATOR",
            "dispatch_entry_events": "PRE_INVOKE_INTENT; CRASH_PENDING_DOES_NOT_ESTABLISH_EXACT_NATIVE_ENTRY",
            "slots": copy.deepcopy(self._rows), "admission_groups": copy.deepcopy(self._groups),
            "automatic_retry": False, "refund": False, "Compute": False, "scientific_approval": False}

    def snapshot(self):
        with self._lock:
            self._assert_authorization()
            return self._snapshot_unlocked()
