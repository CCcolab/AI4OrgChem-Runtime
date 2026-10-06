"""V2 policy integration with frozen-source fake XC; no molecular compute."""
import copy
import importlib
import json
import unittest

import numpy as np

from runtime.user_molecule import residual_seed_v2 as v2
from runtime.user_molecule import seed_v2


fixtures = importlib.import_module("test_user_molecule_residual_bridge")


class ResidualSeedBridgeV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse only the source/fake fixtures.  Importing the module rather
        # than a TestCase binding prevents duplicate unittest discovery.
        fixtures.PreparedBridgeTests.setUpClass()
        cls.addClassCleanup(fixtures.PreparedBridgeTests.doClassCleanups)

    def setUp(self):
        self.fixture_case = fixtures.PreparedBridgeTests(methodName="runTest")
        self.fixture_case.setUp()
        self.addCleanup(self.fixture_case.doCleanups)

    def fixture(self, *, gap=2.0, budget=201):
        kwargs, numint, arrays = self.fixture_case.fixture(budget=budget)
        arrays["physical_hcore"][:] = np.diag([0.0, gap])
        kwargs["contract"]["array_identities"]["physical_hcore"] = fixtures.array_witness(arrays["physical_hcore"])
        coefficients = np.eye(2)
        occupations = np.array([2., 0.])
        extra = {"mo_coefficients": coefficients, "mo_occupations": occupations,
            "frozen_ordinary_mo_identities": {"mo_coefficients": fixtures.array_witness(coefficients),
                                                "mo_occupations": fixtures.array_witness(occupations)}}
        return kwargs, extra, numint, arrays

    def assert_gated(self, result):
        self.assertEqual(result["initialization_policy"], seed_v2.POLICY_ID)
        self.assertFalse(result["production_activation"])
        self.assertFalse(result["comparison_available"])
        self.assertIsNone(result["delta_hartree"])
        self.assertIsNone(result["delta_kcal_mol"])
        self.assertEqual(result["research_acceptance"], "NOT_ACCEPTED")
        self.assertEqual(result["molecular_acceptance"], "NOT_EXECUTED")
        self.assertEqual(result["method_review_status"], v2.METHOD_STATUS)
        self.assertEqual(result["global_evaluation_count"], len(result["bridge_ledger"]))
        self.assertLessEqual(result["global_evaluation_count"], result["global_evaluation_limit"])

    def test_seed_is_admitted_without_any_f_call_and_parent_contract_preserved(self):
        kwargs, extra, numint, arrays = self.fixture()
        contract = copy.deepcopy(kwargs["contract"])
        parent = arrays["ordinary_density"].copy()
        bridge = v2.PreparedResidualSeedBridgeV2(**kwargs, **extra)
        self.assertEqual(numint.calls, [])
        self.assertEqual(bridge.ledger, [])
        self.assertEqual(bridge.contract, contract)
        self.assertEqual(bridge.v2_contract["initialization_policy"], seed_v2.POLICY_ID)
        self.assertEqual(bridge.v2_contract["operator_identity_contract"], contract)
        self.assertFalse(bridge.v2_contract["operator_preparation_policy_is_v2_initialization"])
        np.testing.assert_array_equal(arrays["ordinary_density"], parent)
        self.assertEqual(bridge.seed_receipt["functional_calls"], 0)
        json.dumps(bridge.v2_contract, allow_nan=False)

    def test_qualified_fake_endpoint_has_no_extra_initial_f(self):
        kwargs, extra, numint, arrays = self.fixture()
        result = v2.PreparedResidualSeedBridgeV2(**kwargs, **extra).run()
        self.assert_gated(result)
        self.assertTrue(result["solver_result"]["engine_qualified"])
        self.assertEqual(result["global_evaluation_count"], 3)
        self.assertEqual(len(numint.calls), 3)
        self.assertEqual(result["initialization"]["raw_aufbau_gap_hartree"], 2.)
        self.assertEqual(result["initialization"]["diagnostic_callback_count"], 1)
        self.assertFalse(result["initialization"]["initial_gap_is_admission_or_endpoint_pass"])
        self.assertEqual(result["identity_contract"]["initialization_policy"], seed_v2.POLICY_ID)
        self.assertEqual(result["operator_identity_contract"]["initialization_policy"], "REQUIRE_EXISTING_MASKED_PROJECTOR")
        np.testing.assert_array_equal(arrays["ordinary_density"], np.diag([2., 0.]))

    def test_initial_degenerate_gap_is_diagnostic_and_final_guard_still_refuses(self):
        for gap in (0., 5e-7):
            with self.subTest(gap=gap):
                kwargs, extra, numint, _ = self.fixture(gap=gap)
                result = v2.PreparedResidualSeedBridgeV2(**kwargs, **extra).run()
                self.assert_gated(result)
                self.assertIsNotNone(result["solver_result"])
                self.assertFalse(result["solver_result"]["engine_qualified"])
                self.assertNotEqual(result["stop_reason"], "ROOT_AMBIGUOUS_INITIALIZATION")
                self.assertEqual(result["initialization"]["raw_aufbau_gap_hartree"], gap)
                self.assertEqual(result["initialization"]["final_gap_minimum_hartree"], 1e-6)
                self.assertEqual(len(numint.calls), result["global_evaluation_count"])
                self.assertLessEqual(len(numint.calls), 3)

    def test_mo_metadata_mismatch_refuses_before_f(self):
        kwargs, extra, numint, _ = self.fixture()
        extra["frozen_ordinary_mo_identities"]["mo_coefficients"]["sha256"] = "0"*64
        with self.assertRaises(v2.BridgeRefusal) as caught:
            v2.PreparedResidualSeedBridgeV2(**kwargs, **extra)
        self.assertEqual(caught.exception.reason, "V2_MO_IDENTITY_MISMATCH")
        self.assertEqual(numint.calls, [])

    def test_missing_mo_identity_or_wrong_legacy_policy_refuses_before_f(self):
        for mode in ("missing", "policy"):
            with self.subTest(mode=mode):
                kwargs, extra, numint, _ = self.fixture()
                if mode == "missing":
                    extra["frozen_ordinary_mo_identities"] = {}
                else:
                    kwargs["contract"]["initialization_policy"] = "FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0"
                with self.assertRaises(v2.BridgeRefusal):
                    v2.PreparedResidualSeedBridgeV2(**kwargs, **extra)
                self.assertEqual(numint.calls, [])

    def test_nonorthogonal_parent_mo_refuses_zero_f_even_when_hash_matches(self):
        kwargs, extra, numint, _ = self.fixture()
        extra["mo_coefficients"][0, 0] *= 1.01
        extra["frozen_ordinary_mo_identities"]["mo_coefficients"] = fixtures.array_witness(extra["mo_coefficients"])
        with self.assertRaises(seed_v2.SeedV2Error) as caught:
            v2.PreparedResidualSeedBridgeV2(**kwargs, **extra)
        self.assertEqual(caught.exception.receipt["functional_calls"], 0)
        self.assertEqual(numint.calls, [])

    def test_changed_mo_before_run_refuses_zero_f(self):
        kwargs, extra, numint, _ = self.fixture()
        bridge = v2.PreparedResidualSeedBridgeV2(**kwargs, **extra)
        extra["mo_coefficients"][0, 0] = .9
        result = bridge.run()
        self.assert_gated(result)
        self.assertEqual(result["stop_reason"], "V2_ORDINARY_MO_CHANGED")
        self.assertEqual(numint.calls, [])

    def test_owned_seed_receipt_or_outer_contract_mutation_refuses_zero_f(self):
        for mode in ("seed", "receipt", "contract"):
            with self.subTest(mode=mode):
                kwargs, extra, numint, _ = self.fixture()
                bridge = v2.PreparedResidualSeedBridgeV2(**kwargs, **extra)
                if mode == "seed":
                    bridge.seed_density.setflags(write=True)
                    bridge.seed_density[0, 0] = 1.9
                elif mode == "receipt":
                    bridge.seed_receipt["policy_id"] = "modified"
                else:
                    bridge.v2_contract["initialization_policy"] = "modified"
                result = bridge.run()
                self.assert_gated(result)
                self.assertEqual(numint.calls, [])
                self.assertIsNotNone(result["failure"])

    def test_exact_shared_seed_is_checked_and_callers_are_preserved(self):
        kwargs, extra, numint, arrays = self.fixture()
        shared = np.diag([2., 0.])
        snapshot = shared.copy()
        bridge = v2.PreparedResidualSeedBridgeV2(**kwargs, **extra, shared_seed_density=shared)
        self.assertEqual(numint.calls, [])
        admission = bridge.seed_receipt["shared_seed_admission"]
        self.assertEqual(admission["status"], "PASS_SHARED_SEED_PRODUCTION_ADMISSION")
        self.assertTrue(all(row["pass"] for row in admission["checks"].values()))
        result = bridge.run()
        self.assert_gated(result)
        self.assertTrue(result["identity_contract"]["shared_seed_used"])
        np.testing.assert_array_equal(shared, snapshot)
        np.testing.assert_array_equal(arrays["ordinary_density"], snapshot)

    def test_shared_seed_near_local_seed_must_pass_stricter_absolute_projector_gate(self):
        kwargs, extra, numint, _ = self.fixture()
        # Relative agreement sqrt(2)*1.2e-10/2 passes; the two diagonal
        # contributions give an absolute P trace defect 1.2e-10 and refuse.
        shared = np.diag([2. + 1.2e-10, 1.2e-10])
        with self.assertRaises(v2.BridgeRefusal) as caught:
            v2.PreparedResidualSeedBridgeV2(**kwargs, **extra, shared_seed_density=shared)
        self.assertEqual(caught.exception.reason, "V2_SHARED_SEED_ADMISSION_FAILED")
        self.assertIn("whitened_trace", caught.exception.detail)
        self.assertEqual(numint.calls, [])

    def test_shared_seed_mismatch_and_later_mutation_refuse_zero_f(self):
        kwargs, extra, numint, _ = self.fixture()
        with self.assertRaises(v2.BridgeRefusal):
            v2.PreparedResidualSeedBridgeV2(**kwargs, **extra, shared_seed_density=np.diag([1.9, .1]))
        self.assertEqual(numint.calls, [])
        kwargs, extra, numint, _ = self.fixture()
        shared = np.diag([2., 0.])
        bridge = v2.PreparedResidualSeedBridgeV2(**kwargs, **extra, shared_seed_density=shared)
        shared[0, 0] += .01
        result = bridge.run()
        self.assertEqual(result["stop_reason"], "V2_SHARED_SEED_CALLER_CHANGED")
        self.assertEqual(numint.calls, [])

    def test_mo_change_during_xc_is_one_counted_failure_without_retry(self):
        kwargs, extra, numint, _ = self.fixture()
        numint.mutation = lambda density, grids, count: extra["mo_occupations"].__setitem__(0, 1.)
        result = v2.PreparedResidualSeedBridgeV2(**kwargs, **extra).run()
        self.assert_gated(result)
        self.assertEqual(len(numint.calls), 1)
        self.assertEqual(result["global_evaluation_count"], 1)
        self.assertEqual(result["bridge_ledger"][0]["status"], "REFUSED")
        self.assertEqual(result["bridge_ledger"][0]["reason"], "V2_ORDINARY_MO_CHANGED")

    def test_solver_configuration_refuses_before_f_and_run_is_single_use(self):
        kwargs, extra, numint, _ = self.fixture()
        bridge = v2.PreparedResidualSeedBridgeV2(**kwargs, **extra)
        result = bridge.run(maximum_iterations=True)
        self.assert_gated(result)
        self.assertEqual(result["stop_reason"], "INVALID_SOLVER_CONFIGURATION")
        self.assertEqual(numint.calls, [])
        with self.assertRaises(v2.BridgeRefusal):
            bridge.run()
        with self.assertRaises(v2.BridgeRefusal) as caught:
            bridge.evaluate(bridge.seed_density)
        self.assertEqual(caught.exception.reason, "BRIDGE_ALREADY_SETTLED")

    def test_small_budget_retains_final_gate_failure_and_callback_ceiling(self):
        kwargs, extra, numint, _ = self.fixture(budget=2)
        result = v2.PreparedResidualSeedBridgeV2(**kwargs, **extra).run()
        self.assert_gated(result)
        self.assertFalse(result["solver_result"]["engine_qualified"])
        self.assertEqual(result["global_evaluation_limit"], 2)
        self.assertLessEqual(len(numint.calls), 2)

    def test_both_storage_paths_share_seed_and_retain_configuration(self):
        values = []
        for mode, optimize in (("COPY_MASK", True), ("INPLACE_OWNED", False)):
            kwargs, extra, numint, _ = self.fixture()
            kwargs.update(eri_mode=mode, optimize_eri_contractions=optimize)
            result = v2.PreparedResidualSeedBridgeV2(**kwargs, **extra).run()
            self.assert_gated(result)
            self.assertEqual(result["eri_mode"], mode)
            self.assertEqual(result["optimize_eri_contractions"], optimize)
            self.assertEqual(len(numint.calls), result["global_evaluation_count"])
            values.append(result["initialization"]["initial_density_id"])
        self.assertEqual(values[0], values[1])


if __name__ == "__main__":
    unittest.main()
