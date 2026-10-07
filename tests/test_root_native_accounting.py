"""Durable accounting tests with toy delegates; no scientific imports/calls."""
import copy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from runtime.user_molecule.residual_budget import ConditionalCallbackBudget
from runtime.user_molecule import root_native_accounting as accounting


def digest(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


class RootNativeAccountingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.identity = {"mode": "ENGINEERING_SIMULATED_NATIVE",
            "execution_kind": "ENGINEERING_SIMULATED_NATIVE", "scientific_execution_authorized": False,
            "geometry_sha256": digest("geometry"), "profile_sha256": digest("profile"),
            "dependencies_sha256": digest("dependencies"), "initial_density_id": digest("initial")}
        self.book = ConditionalCallbackBudget(path=self.root / "callbacks.json", batch_id="toy-accounting",
            identity=self.identity, path_limits={"independent_reference": 201}, total_limit=201)
        self.counter = accounting.RootNativeAccounting(self.root / "accounting", self.book)

    def binding(self, token, **changed):
        return dict(slot_id=token.slot_id, path_id=token.path_id, density_id=token.density_id, phase=token.phase, **changed)

    def complete(self, did, phase, *, context=None):
        token = self.counter.begin_callback(did, phase, candidate_context=context)
        result = self.counter.native_nr(token, lambda: {"toy": True}, context_binding=self.binding(token))
        self.assertEqual(result, {"toy": True})
        self.counter.finish_callback(token, digest("operator-" + did))
        return token

    def initial(self):
        return self.complete(digest("initial"), "CURRENT_INITIAL")

    def admission(self, group_id, *, kind="COMPLETE_JACOBIAN", status="ADMITTED", base=None, actual=0):
        base = self.counter.snapshot()["slots"][-1] if base is None else base
        budget = self.book.snapshot()
        planned, reserve = (96, 2) if kind == "COMPLETE_JACOBIAN" else (2, 0)
        return {"group_id": group_id, "kind": kind, "status": status,
            "planned_callbacks": planned, "tail_callbacks_reserved": reserve, "actual_callbacks": actual,
            "call_count_before": budget["charged_slots"], "remaining_callbacks": budget["remaining_slots"],
            "admitted": budget["remaining_slots"] >= planned + reserve,
            "base_snapshot_id": "evaluation-" + str(base["slot_id"]),
            "base_density_id": base["density_id"], "base_operator_id": base["operator_id"]}

    def context(self, group, did, phase, sample=None):
        result = {"evaluation_count": self.book.snapshot()["charged_slots"] + 1,
            "density_id": did, "phase": phase, "admission_group_id": group["group_id"],
            **{key: group[key] for key in ("base_snapshot_id", "base_density_id", "base_operator_id")}}
        if sample is not None:
            result["fd_sample"] = sample
        return result

    def test_success_separates_slots_delegate_counts_and_unobserved_scientific_counts(self):
        token = self.initial()
        with self.assertRaises(FrozenInstanceError):
            token.phase = "forged"
        final = self.counter.close("engineering complete")
        self.assertEqual(final["status"], "CLOSED")
        self.assertEqual(final["callback_slots"], {"charged": 1, "pending": 0, "succeeded": 1, "failed": 0, "limit": 201})
        self.assertEqual(final["engineering_simulated_native_counts"], {"entered": 1, "completed": 1, "failed": 0})
        self.assertIsNone(final["source_native_dispatch_counts"]["entered"])
        self.assertEqual(final["evaluator_dispatch"]["functional_source_entry"], "NOT_OBSERVED_BY_THIS_LAYER")
        self.assertFalse(final["Compute"])
        events = [json.loads(line)["event"] for line in self.counter.events.read_text().splitlines()]
        self.assertEqual(events, ["NR_ENTERED", "NR_COMPLETED"])
        self.assertEqual(self.book.snapshot()["paths"]["independent_reference"]["state"], "CLOSED")
        final["slots"][0]["density_id"] = "mutated"
        self.assertEqual(self.counter.snapshot()["slots"][0]["density_id"], digest("initial"))

    def test_real_mode_missing_authorization_old_mode_and_bool_integer_refused_before_charge(self):
        for index, kwargs in enumerate((
                {"execution_kind": "SOURCE_NATIVE_DIAGNOSTIC"},
                {"execution_kind": "SOURCE_NATIVE_DIAGNOSTIC", "scientific_execution_authorized": True},
                {"execution_kind": "PREPARED_OCCUPIED_SPACE_ROOT_DIAGNOSTIC"},
                {"scientific_execution_authorized": 0}, {"scientific_execution_authorized": True})):
            with self.subTest(kwargs=kwargs):
                target = self.root / ("refused-" + str(index))
                with self.assertRaises(accounting.NativeAccountingError):
                    accounting.RootNativeAccounting(target, self.book, **kwargs)
                self.assertFalse(target.exists())
        self.assertEqual(self.book.snapshot()["charged_slots"], 0)

    def test_wrong_limits_and_changed_identity_refused(self):
        other = ConditionalCallbackBudget(path=self.root / "other.json", batch_id="wrong-limit",
            identity=self.identity, path_limits={"independent_reference": 200}, total_limit=200)
        with self.assertRaises(accounting.NativeAccountingError):
            accounting.RootNativeAccounting(self.root / "wrong", other)
        self.book.identity["scientific_execution_authorized"] = True
        with self.assertRaises(accounting.NativeAccountingError):
            self.counter.begin_callback(digest("initial"), "CURRENT_INITIAL")
        self.assertEqual(len(json.loads(self.book.path.read_bytes())["slots"]), 0)

    def test_external_charge_or_settlement_cannot_be_reported_as_owned_success(self):
        token = self.counter.begin_callback(digest("initial"), "CURRENT_INITIAL")
        self.book.finish(token.slot_id, status="SUCCEEDED", operator_id=digest("external"))
        with self.assertRaises(accounting.NativeAccountingError):
            self.counter.snapshot()
        with self.assertRaises(accounting.NativeAccountingError):
            self.counter.close("cannot bless external settlement")
        self.assertEqual(self.book.snapshot()["charged_slots"], 1)

    def test_journal_path_or_batch_cannot_be_repointed_to_refill_the_same_accountant(self):
        for field, value in (("path", self.root / "new.json"), ("lock_path", self.root / "new.lock"), ("batch_id", "replacement")):
            with self.subTest(field=field):
                original = getattr(self.book, field)
                setattr(self.book, field, value)
                with self.assertRaises(accounting.NativeAccountingError):
                    self.counter.begin_callback(digest("initial"), "CURRENT_INITIAL")
                setattr(self.book, field, original)
        self.assertEqual(self.book.snapshot()["charged_slots"], 0)

    def test_wrong_native_context_never_enters_delegate_and_cannot_be_retried(self):
        token = self.counter.begin_callback(digest("initial"), "CURRENT_INITIAL")
        called = []
        binding = self.binding(token); binding["density_id"] = digest("wrong")
        with self.assertRaises(accounting.NativeAccountingError):
            self.counter.native_nr(token, lambda: called.append(True), context_binding=binding)
        with self.assertRaises(accounting.NativeAccountingError):
            self.counter.native_nr(token, lambda: called.append(True), context_binding=self.binding(token))
        self.assertEqual(called, [])
        self.counter.fail_callback(token, ValueError("context refused")); self.counter.close("context refused")
        self.assertEqual(self.book.snapshot()["failed_slots"], 1)
        self.assertEqual(self.counter.snapshot()["nr_dispatch_counts"]["entered"], 0)

    def test_duplicate_native_call_forged_token_and_reused_finished_token_refused(self):
        token = self.counter.begin_callback(digest("initial"), "CURRENT_INITIAL")
        forged = accounting.CallbackToken(token.slot_id, token.path_id, token.density_id, token.phase)
        called = []
        with self.assertRaises(accounting.NativeAccountingError):
            self.counter.native_nr(forged, lambda: called.append(True), context_binding=self.binding(forged))
        self.counter.native_nr(token, lambda: called.append(True), context_binding=self.binding(token))
        with self.assertRaises(accounting.NativeAccountingError):
            self.counter.native_nr(token, lambda: called.append(True), context_binding=self.binding(token))
        self.counter.finish_callback(token, digest("operator"))
        with self.assertRaises(accounting.NativeAccountingError):
            self.counter.finish_callback(token, digest("operator"))
        self.assertEqual(called, [True])
        self.assertEqual(self.book.snapshot()["charged_slots"], 1)

    def test_baseexception_charged_failed_no_refund_retry_or_success(self):
        token = self.counter.begin_callback(digest("initial"), "CURRENT_INITIAL")
        def interrupted():
            raise KeyboardInterrupt("toy interruption")
        with self.assertRaises(KeyboardInterrupt) as captured:
            self.counter.native_nr(token, interrupted, context_binding=self.binding(token))
        with self.assertRaises(accounting.NativeAccountingError):
            self.counter.finish_callback(token, digest("operator"))
        self.counter.fail_callback(token, captured.exception)
        with self.assertRaises(accounting.NativeAccountingError):
            self.counter.begin_callback(digest("new"), "OPTIMIZER_BASE")
        final = self.counter.close("interrupted")
        self.assertEqual(final["nr_dispatch_counts"], {"entered": 1, "completed": 0, "failed": 1})
        self.assertEqual(final["callback_slots"]["charged"], final["callback_slots"]["failed"])
        self.assertEqual(final["status"], "CLOSED_FAILED_NO_RETRY")

    def test_missing_nr_cannot_finish_and_close_charges_unresolved_slot(self):
        token = self.counter.begin_callback(digest("initial"), "CURRENT_INITIAL")
        with self.assertRaises(accounting.NativeAccountingError):
            self.counter.finish_callback(token, digest("operator"))
        final = self.counter.close("unresolved callback")
        self.assertEqual(final["callback_slots"]["failed"], 1)
        self.assertEqual(final["nr_dispatch_counts"], {"entered": 0, "completed": 0, "failed": 0})
        with self.assertRaises(accounting.NativeAccountingError):
            self.counter.close("second close")

    def test_pending_crash_output_and_journal_cannot_be_reopened(self):
        self.counter.begin_callback(digest("initial"), "CURRENT_INITIAL")
        before = self.book.path.read_bytes()
        for target in (self.root / "accounting", self.root / "different-output"):
            with self.subTest(target=target):
                with self.assertRaises(accounting.NativeAccountingError):
                    accounting.RootNativeAccounting(target, self.book)
        self.assertEqual(self.book.path.read_bytes(), before)
        self.assertEqual(self.book.snapshot()["pending_slots"], 1)

    def test_entry_event_write_failure_never_dispatches_and_cannot_succeed(self):
        token = self.counter.begin_callback(digest("initial"), "CURRENT_INITIAL")
        called = []
        with mock.patch.object(accounting, "_append_jsonl", side_effect=OSError("toy disk failure")):
            with self.assertRaises(OSError):
                self.counter.native_nr(token, lambda: called.append(True), context_binding=self.binding(token))
        self.assertEqual(called, [])
        with self.assertRaises(accounting.NativeAccountingError):
            self.counter.finish_callback(token, digest("operator"))
        final = self.counter.close("event write failure")
        self.assertFalse(final["persistence_intact"])
        self.assertEqual(final["callback_slots"]["succeeded"], 0)
        self.assertEqual(final["nr_dispatch_counts"]["entered"], 0)

    def test_completion_event_failure_preserves_observed_attempt_without_success(self):
        token = self.counter.begin_callback(digest("initial"), "CURRENT_INITIAL")
        original = accounting._append_jsonl
        def write(path, value):
            if value.get("event") == "NR_COMPLETED":
                raise OSError("completion persistence failure")
            return original(path, value)
        called = []
        with mock.patch.object(accounting, "_append_jsonl", side_effect=write):
            with self.assertRaises(OSError):
                self.counter.native_nr(token, lambda: called.append(True), context_binding=self.binding(token))
        with self.assertRaises(accounting.NativeAccountingError):
            self.counter.finish_callback(token, digest("operator"))
        final = self.counter.close("completion receipt unavailable")
        self.assertEqual(called, [True])
        self.assertEqual(final["nr_dispatch_counts"]["completed"], 1)
        self.assertFalse(final["persistence_intact"])
        self.assertEqual(self.book.snapshot()["failed_slots"], 1)

    def test_finish_state_failure_occurs_before_callback_budget_success(self):
        token = self.counter.begin_callback(digest("initial"), "CURRENT_INITIAL")
        self.counter.native_nr(token, lambda: 42, context_binding=self.binding(token))
        with mock.patch.object(accounting, "_atomic_write", side_effect=OSError("state failure")):
            with self.assertRaises(OSError):
                self.counter.finish_callback(token, digest("operator"))
        self.assertEqual(self.book.snapshot()["slots"][0]["status"], "PENDING")
        final = self.counter.close("state receipt unavailable")
        self.assertEqual(final["callback_slots"]["succeeded"], 0)
        self.assertFalse(final["persistence_intact"])

    def test_exact_jacobian_and_one_callback_tail_groups_are_explicit_not_inferred(self):
        self.initial(); group = self.admission(1)
        self.counter.record_admission(group)
        group = dict(group, status="STARTED"); self.counter.record_admission(group)
        for sample in range(1, 97):
            did = digest("fd-" + str(sample))
            self.complete(did, "FD_SAMPLE", context=self.context(group, did, "FD_SAMPLE", sample))
        completed = dict(group, status="COMPLETED", actual_callbacks=96)
        self.counter.record_admission(completed)
        tail = self.admission(2, kind="FINAL_TAIL")
        self.counter.record_admission(tail)
        tail = dict(tail, status="STARTED"); self.counter.record_admission(tail)
        did = tail["base_density_id"]
        self.complete(did, "FINAL_RETURNED_DENSITY", context=self.context(tail, did, "FINAL_RETURNED_DENSITY"))
        self.counter.record_admission(dict(tail, status="COMPLETED", actual_callbacks=1))
        final = self.counter.close("toy complete groups, no gate qualification")
        self.assertEqual(final["callback_slots"]["charged"], 98)
        self.assertEqual(final["nr_dispatch_counts"]["completed"], 98)
        self.assertEqual(final["admission_groups"][1]["row"]["actual_callbacks"], 96)
        self.assertEqual(final["admission_groups"][2]["row"]["actual_callbacks"], 1)
        self.assertFalse(final["scientific_approval"])

    def test_fd_without_group_wrong_group_or_sample_refused_before_charge(self):
        self.initial()
        with self.assertRaises(accounting.NativeAccountingError):
            self.counter.begin_callback(digest("fd"), "FD_SAMPLE")
        group = self.admission(1); self.counter.record_admission(group)
        context = self.context(group, digest("fd"), "FD_SAMPLE", 1)
        with self.assertRaises(accounting.NativeAccountingError):
            self.counter.begin_callback(digest("fd"), "FD_SAMPLE", candidate_context=context)
        group = dict(group, status="STARTED"); self.counter.record_admission(group)
        for changed in ({"fd_sample": True}, {"admission_group_id": 2}, {"base_operator_id": digest("forged")}, {"evaluation_count": 99}):
            with self.subTest(changed=changed):
                with self.assertRaises(accounting.NativeAccountingError):
                    self.counter.begin_callback(digest("fd"), "FD_SAMPLE", candidate_context={**context, **changed})
        self.assertEqual(self.book.snapshot()["charged_slots"], 1)

    def test_partial_failed_group_cannot_be_relabelled_complete_or_enter_tail(self):
        self.initial(); group = self.admission(1); self.counter.record_admission(group)
        group = dict(group, status="STARTED"); self.counter.record_admission(group)
        did = digest("partial-fd"); token = self.counter.begin_callback(did, "FD_SAMPLE", candidate_context=self.context(group, did, "FD_SAMPLE", 1))
        self.counter.fail_callback(token, ValueError("toy early evaluator refusal before NR"))
        with self.assertRaises(accounting.NativeAccountingError):
            self.counter.record_admission(dict(group, status="COMPLETED", actual_callbacks=96))
        self.counter.record_admission(dict(group, status="REFUSED_PARTIAL_NO_RETRY", actual_callbacks=1))
        with self.assertRaises(accounting.NativeAccountingError):
            self.counter.begin_callback(digest("tail"), "FINAL_RETURNED_DENSITY")
        final = self.counter.close("partial group stops batch")
        self.assertEqual(final["callback_slots"]["charged"], 2)
        self.assertEqual(final["nr_dispatch_counts"]["entered"], 1)

    def test_admission_declared_base_budget_counts_and_transitions_must_match(self):
        self.initial(); original = self.admission(1)
        for changes in ({"planned_callbacks": 95}, {"tail_callbacks_reserved": 0}, {"admitted": 1},
                        {"remaining_callbacks": 201}, {"base_snapshot_id": "evaluation-99"}, {"base_operator_id": digest("forged")}):
            with self.subTest(changes=changes):
                with self.assertRaises(accounting.NativeAccountingError):
                    self.counter.record_admission({**original, **changes})
        self.assertEqual(self.counter.snapshot()["admission_groups"], {})
        self.counter.record_admission(original)
        with self.assertRaises(accounting.NativeAccountingError):
            self.counter.record_admission(dict(original, status="COMPLETED", actual_callbacks=96))
        original["base_density_id"] = "caller mutation"
        self.assertEqual(self.counter.snapshot()["admission_groups"][1]["row"]["base_density_id"], digest("initial"))

    def test_whole_jacobian_affordability_reserves_both_tail_slots_before_any_fd(self):
        self.initial()
        for number in range(103):
            self.complete(digest("budget-objective-" + str(number)), "OPTIMIZER_BASE")
        refused = self.admission(1, status="REFUSED_ZERO_CALLBACKS")
        self.assertEqual(refused["remaining_callbacks"], 97)
        self.assertFalse(refused["admitted"])
        with self.assertRaises(accounting.NativeAccountingError):
            self.counter.record_admission({**refused, "admitted": True, "status": "ADMITTED"})
        self.counter.record_admission(refused)
        with self.assertRaises(accounting.NativeAccountingError):
            self.counter.begin_callback(digest("forbidden-fd"), "FD_SAMPLE")
        final = self.counter.close("97 remaining cannot afford 96+2")
        self.assertEqual(final["callback_slots"]["charged"], 104)
        self.assertEqual(final["nr_dispatch_counts"]["entered"], 104)
        self.assertEqual(final["admission_groups"][1]["slots"], [])

    def test_terminal_partial_group_evidence_retains_exact_unexecuted_count(self):
        self.initial(); group = self.admission(1); self.counter.record_admission(group)
        group = dict(group, status="STARTED"); self.counter.record_admission(group)
        self.counter.record_admission(dict(group, status="REFUSED_PARTIAL_NO_RETRY", actual_callbacks=0,
            unexecuted_planned_callbacks=96, failure_type="ToyPreCallbackRefusal"))
        self.assertEqual(self.counter.snapshot()["admission_groups"][1]["row"]["unexecuted_planned_callbacks"], 96)
        self.assertEqual(self.book.snapshot()["charged_slots"], 1)
        self.counter.close("explicit failed group no native dispatch")


if __name__ == "__main__":
    unittest.main()
