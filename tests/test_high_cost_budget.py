"""Third-batch accounting witnesses; no workers or scientific imports."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from runtime.high_cost_cases import budget


class HighCostBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="high-cost-budget-fake-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "budget.json"
        self.units = ["P11A-furan-G", "P11B-benzene-G", "P12-N16-GE-g01-g02"]
        self.identity = {"profile_sha256": "a" * 64, "source_sha256": "b" * 64,
                         "dependencies_sha256": "c" * 64, "image_id": "sha256:" + "d" * 64}
        self.resources = {"hard_wall_seconds": 100, "soft_wall_seconds": 80,
                          "memory_bytes": 8 * 1024 ** 3, "cpus": 8, "threads": 8}

    def create(self, ceiling=200):
        return budget.new_budget(self.path, self.units, self.identity["profile_sha256"],
                                 self.identity["source_sha256"], self.identity["dependencies_sha256"], ceiling)

    def reserve(self, unit=None, execution="execution-1", identity=None, resources=None):
        return budget.reserve(self.path, unit or self.units[0], resources or self.resources,
                              identity or self.identity, execution)

    def test_reopening_identical_batch_preserves_bytes_and_spent_charge(self):
        self.create(); self.reserve()
        budget.settle(self.path, "execution-1", 61.25, True, "FAILED_WORKER_PROCESS")
        before = self.path.read_bytes()
        value = self.create()
        self.assertEqual(value["charged_seconds"], 61.25)
        self.assertEqual(value["remaining_seconds"], 138.75)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(value["automatic_retry"])
        self.assertFalse(value["resume"])
        self.assertFalse(value["batch2_budget_reused"])

    def test_batch2_file_refused_without_rewrite(self):
        original = b'{"schema":"protocol-case-batch2-budget-v1","ceiling_seconds":6300,"attempts":{}}\n'
        self.path.write_bytes(original)
        with self.assertRaises(budget.BudgetError):
            self.create()
        self.assertEqual(self.path.read_bytes(), original)
        with self.assertRaises(budget.BudgetError):
            self.reserve()
        self.assertEqual(self.path.read_bytes(), original)

    def test_changed_profile_source_dependency_units_or_ceiling_cannot_reset(self):
        self.create(); before = self.path.read_bytes()
        variants = [(self.units, "e" * 64, "b" * 64, "c" * 64, 200),
                    (self.units, "a" * 64, "e" * 64, "c" * 64, 200),
                    (self.units, "a" * 64, "b" * 64, "e" * 64, 200),
                    (self.units[:1], "a" * 64, "b" * 64, "c" * 64, 200),
                    (self.units, "a" * 64, "b" * 64, "c" * 64, 201)]
        for args in variants:
            with self.subTest(args=args), self.assertRaises(budget.BudgetError):
                budget.new_budget(self.path, *args)
        self.assertEqual(self.path.read_bytes(), before)

    def test_reservation_charges_full_hard_wall_and_binds_identity(self):
        self.create(); identity = {**self.identity, "unit_id": self.units[0], "operator_id": "ordinary_rks"}
        context = self.reserve(identity=identity)
        self.assertEqual(context["reserved_seconds"], 100)
        self.assertEqual(len(context["reservation_token"]), 32)
        value = self.create()
        self.assertEqual(value["charged_seconds"], 100)
        self.assertEqual(value["unresolved_units"], [self.units[0]])
        identity["operator_id"] = "source2011"
        self.assertEqual(value["attempts"][self.units[0]]["identity"]["operator_id"], "ordinary_rks")

    def test_uncertain_cleanup_keeps_full_charge_and_blocks_following_state(self):
        self.create(); self.reserve()
        value = budget.settle(self.path, "execution-1", 9.5, False, "FAILED_UNKNOWN_CLEANUP")
        row = value["attempts"][self.units[0]]
        self.assertEqual(row["state"], "RESERVED")
        self.assertEqual(row["charged_seconds"], 100)
        self.assertEqual(row["observed_charged_seconds"], 9.5)
        with self.assertRaises(budget.BudgetError):
            self.reserve(self.units[1], "execution-2")
        value = budget.settle(self.path, "execution-1", 12.5, True, "FAILED_INTERRUPTED")
        self.assertEqual(value["charged_seconds"], 12.5)
        self.assertEqual(value["unresolved_units"], [])

    def test_failed_and_interrupted_states_cannot_retry_or_resume(self):
        self.create(); self.reserve()
        budget.settle(self.path, "execution-1", 10, True, "FAILED_INTERRUPTED")
        with self.assertRaises(budget.BudgetError):
            self.reserve(execution="execution-2")
        with self.assertRaises(budget.BudgetError):
            budget.settle(self.path, "execution-1", 0, True, "PASS")

    def test_insufficient_budget_blocks_before_second_reservation(self):
        self.create(150); self.reserve()
        budget.settle(self.path, "execution-1", 60, True, "PASS")
        before = self.path.read_bytes()
        with self.assertRaises(budget.BudgetError):
            self.reserve(self.units[1], "execution-2")
        self.assertEqual(self.path.read_bytes(), before)

    def test_unknown_state_and_different_batch_identity_are_refused(self):
        self.create()
        with self.assertRaises(budget.BudgetError):
            self.reserve("P12-arbitrary-user-state")
        for field in ("profile_sha256", "source_sha256", "dependencies_sha256"):
            with self.subTest(field=field), self.assertRaises(budget.BudgetError):
                self.reserve(identity={**self.identity, field: "f" * 64})
        with self.assertRaises(budget.BudgetError):
            self.reserve(identity={**self.identity, "unit_id": self.units[1]})

    def test_duplicate_execution_cannot_be_used_for_another_state(self):
        self.create(); self.reserve()
        budget.settle(self.path, "execution-1", 1, True, "PASS")
        with self.assertRaises(budget.BudgetError):
            self.reserve(self.units[1], "execution-1")

    def test_crash_reopen_does_not_release_reservation(self):
        self.create(); self.reserve()
        value = self.create()
        self.assertEqual(value["charged_seconds"], 100)
        with self.assertRaises(budget.BudgetError):
            self.reserve(self.units[1], "execution-after-crash")

    def test_overrun_is_charged_in_full_and_prevents_next_launch(self):
        self.create(); self.reserve()
        value = budget.settle(self.path, "execution-1", 250, True, "FAILED_HARD_WALL_EXCEEDED")
        self.assertEqual(value["charged_seconds"], 250)
        self.assertTrue(value["over_budget"])
        self.assertEqual(value["remaining_seconds"], 0)
        with self.assertRaises(budget.BudgetError):
            self.reserve(self.units[1], "execution-2")

    def test_os_lock_refuses_concurrent_mutation(self):
        self.create()
        with budget._lock(self.path.with_name(self.path.name + ".lock")):
            with self.assertRaises(budget.BudgetError):
                self.reserve()
        self.assertEqual(self.create()["attempts"], {})

    def test_tampered_or_extended_closed_ledger_is_not_reset(self):
        self.create()
        value = json.loads(self.path.read_text())
        value["ceiling_seconds"] += 1
        self.path.write_text(json.dumps(value), encoding="utf-8")
        before = self.path.read_bytes()
        with self.assertRaises(budget.BudgetError):
            self.create()
        self.assertEqual(self.path.read_bytes(), before)
        value["unexpected"] = "field"
        self.path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(budget.BudgetError):
            self.reserve()

    def test_invalid_observations_do_not_erase_charge(self):
        self.create(); self.reserve(); before = self.path.read_bytes()
        for charge in (True, -1, float("nan"), float("inf")):
            with self.subTest(charge=charge), self.assertRaises(budget.BudgetError):
                budget.settle(self.path, "execution-1", charge, True, "FAILED")
        with self.assertRaises(budget.BudgetError):
            budget.settle(self.path, "execution-1", 1, 1, "FAILED")
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
