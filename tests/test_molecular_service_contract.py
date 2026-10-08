"""Closed ordinary-task contract tests; no engine or source-lock dependency."""

import copy
import json
from pathlib import Path
import tempfile
import time
import unittest

from runtime.molecular_service import (
    PROFILE_ID, PROFILE_PATH, PROTOCOL_ID, TASK, digest, strict_load,
    validate_case_result, validate_contract,
)


def contract_value():
    now = time.time()
    return {"schema": "molecular-service-execution-v1", "task": TASK,
            "profile_id": PROFILE_ID, "protocol_id": PROTOCOL_ID,
            "scientific_execution_authorized": True, "runtime_commit": "a" * 40,
            "source_snapshot_sha256": "b" * 64, "dependency_lock_sha256": "c" * 64,
            "profile_sha256": digest(PROFILE_PATH), "request_sha256": "d" * 64,
            "structure_sha256": "e" * 64, "input_manifest_sha256": "f" * 64,
            "execution_id": "1" * 32, "memory_limit_bytes": 1073741824, "threads": 1,
            "maximum_processes": 1, "wall_time_limit_seconds": 120, "stop_after_seconds": 100,
            "started_epoch": now, "stop_deadline_epoch": now + 100, "hard_deadline_epoch": now + 120,
            "scf_kernel_call_limit": 1, "boys_kernel_call_limit": 0, "pipek_mezey_kernel_call_limit": 0}


def result_value(contract):
    return {"schema": "molecular-single-point-result-v1",
            **{key: contract[key] for key in ("task", "profile_id", "protocol_id", "execution_id",
                                             "request_sha256", "structure_sha256", "profile_sha256")},
            "status": "NUMERICALLY_QUALIFIED_ORDINARY_RHF", "execution_kind": "PINNED_PYSCF_ORDINARY_RHF",
            "scientific_qualified": True, "numerically_qualified": True, "operations_closed": True,
            "method": "RHF", "basis": "6-31G(d)", "stability_status": "NOT_EXECUTED",
            "stability": "NOT_EXECUTED", "conditional_scf_executed": False,
            "execution_identity": copy.deepcopy(contract),
            "diagnostics": {"numerically_qualified": True,
                            "checks": {key: True for key in (
                                "scf_converged", "closed_shell_occupations", "electron_number",
                                "occupied_orthonormality", "whitened_projector_idempotency",
                                "density_reconstruction", "energy_ledger_closure",
                                "whitened_fock_projector_commutator", "finite_arrays_and_energy",
                                "symmetric_ao_matrices", "ordinary_fock_equals_hcore_plus_veff",
                                "package_energy_ledger_closure")}}}


class MolecularServiceContractTests(unittest.TestCase):
    def test_exact_first_profile_contract_returns_actual_profile(self):
        contract = contract_value()
        profile = validate_contract(contract)
        self.assertEqual(profile["id"], PROFILE_ID)
        self.assertEqual(profile["protocol_id"], PROTOCOL_ID)
        self.assertEqual(profile["resources"]["memory_limit_bytes"], contract["memory_limit_bytes"])

    def test_contract_is_closed_to_missing_extra_and_wrong_object(self):
        baseline = contract_value()
        for key in baseline:
            changed = copy.deepcopy(baseline)
            del changed[key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                validate_contract(changed)
        for key in ("molecule", "method", "basis", "geometry_file", "fragments", "resume", "resources"):
            changed = copy.deepcopy(baseline)
            changed[key] = None
            with self.subTest(extra=key), self.assertRaises(ValueError):
                validate_contract(changed)
        for value in (None, [], True, "single-point"):
            with self.subTest(object=value), self.assertRaises(ValueError):
                validate_contract(value)

    def test_task_profile_protocol_and_science_authorization_cannot_be_changed(self):
        cases = [("task", "user-compute"), ("task", "p01-orbital-density"),
                 ("profile_id", "unreviewed-DFT"), ("protocol_id", "CONDITIONAL_STATE"),
                 ("schema", "registered-case-execution-v1"),
                 ("scientific_execution_authorized", False), ("scientific_execution_authorized", 1)]
        for key, value in cases:
            changed = contract_value()
            changed[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_contract(changed)

    def test_resource_or_call_budget_cannot_be_expanded_or_retyped(self):
        fields = ("memory_limit_bytes", "threads", "maximum_processes", "wall_time_limit_seconds",
                  "stop_after_seconds", "scf_kernel_call_limit", "boys_kernel_call_limit", "pipek_mezey_kernel_call_limit")
        for key in fields:
            for value in (True, 1.0, str(contract_value()[key]), contract_value()[key] + 1):
                changed = contract_value()
                changed[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    validate_contract(changed)

    def test_identity_values_are_complete_lowercase_hex(self):
        fields = ("runtime_commit", "execution_id", "source_snapshot_sha256", "dependency_lock_sha256",
                  "profile_sha256", "request_sha256", "structure_sha256", "input_manifest_sha256")
        for key in fields:
            correct = contract_value()[key]
            for value in (None, 123, correct[:-1], correct + "a", "g" * len(correct), "A" * len(correct)):
                changed = contract_value()
                changed[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    validate_contract(changed)

    def test_actual_profile_hash_must_match_but_input_hashes_are_bound_by_worker(self):
        changed = contract_value()
        changed["profile_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            validate_contract(changed)
        # Contract syntax cannot authenticate user bytes. The worker compares
        # these identities against the RO manifest and parsed request later.
        changed = contract_value()
        changed["request_sha256"] = "0" * 64
        validate_contract(changed)

    def test_epoch_booleans_nan_infinity_and_strings_are_refused(self):
        for key in ("started_epoch", "stop_deadline_epoch", "hard_deadline_epoch"):
            for value in (True, None, "100", float("nan"), float("inf"), float("-inf")):
                changed = contract_value()
                changed[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    validate_contract(changed)

    def test_relative_soft_or_hard_deadline_cannot_be_changed(self):
        for key in ("stop_deadline_epoch", "hard_deadline_epoch"):
            for difference in (-1, 1, 100):
                changed = contract_value()
                changed[key] += difference
                with self.subTest(key=key, difference=difference), self.assertRaises(ValueError):
                    validate_contract(changed)
        changed = contract_value()
        changed["stop_after_seconds"] = 101
        changed["stop_deadline_epoch"] = changed["started_epoch"] + 101
        with self.assertRaises(ValueError):
            validate_contract(changed)

    def test_json_duplicate_keys_and_symbolic_nonfinite_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "contract.json"
            for payload in (b'{"task":"single-point","task":"other"}', b'{"x":NaN}', b'{"x":Infinity}'):
                path.write_bytes(payload)
                with self.subTest(payload=payload), self.assertRaises(ValueError):
                    strict_load(path)

    def test_valid_result_has_same_input_and_execution_identity(self):
        contract = contract_value()
        result = result_value(contract)
        self.assertIs(validate_case_result(result, contract), result)

    def test_result_top_level_identity_mismatch_is_rejected(self):
        contract = contract_value()
        for key in ("task", "profile_id", "protocol_id", "execution_id", "request_sha256", "structure_sha256", "profile_sha256"):
            for missing in (False, True):
                result = result_value(contract)
                if missing:
                    del result[key]
                else:
                    result[key] = "wrong"
                with self.subTest(key=key, missing=missing), self.assertRaises(ValueError):
                    validate_case_result(result, contract)

    def test_result_full_image_source_budget_identity_is_bound(self):
        contract = contract_value()
        for key in contract:
            result = result_value(contract)
            result["execution_identity"][key] = None
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_case_result(result, contract)
        result = result_value(contract)
        del result["execution_identity"]
        with self.assertRaises(ValueError):
            validate_case_result(result, contract)

    def test_result_status_or_boolean_claim_cannot_promote_failure(self):
        contract = contract_value()
        cases = [("schema", "other-result"), ("status", "PASS"), ("status", "ORDINARY_RHF_NOT_QUALIFIED"),
                 ("status", "ENGINEERING_FAKE_NUMERICALLY_QUALIFIED_ORDINARY_RHF"),
                 ("scientific_qualified", False), ("scientific_qualified", 1),
                 ("numerically_qualified", False), ("operations_closed", False),
                 ("conditional_scf_executed", True), ("execution_kind", "ENGINEERING_FAKE"),
                 ("method", "DFT"), ("basis", "STO-3G")]
        for key, value in cases:
            result = result_value(contract)
            result[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_case_result(result, contract)

    def test_numeric_checks_must_close_with_true_boolean_gates(self):
        contract = contract_value()
        for diagnostics in (None, {}, {"numerically_qualified": False, "checks": {"scf_converged": True}},
                            {"numerically_qualified": True, "checks": {}},
                            {"numerically_qualified": True, "checks": {"scf_converged": False}},
                            {"numerically_qualified": True, "checks": {"scf_converged": 1}}):
            result = result_value(contract)
            result["diagnostics"] = diagnostics
            with self.subTest(diagnostics=diagnostics), self.assertRaises(ValueError):
                validate_case_result(result, contract)
        for gate in result_value(contract)["diagnostics"]["checks"]:
            for change in ("missing", False, 1):
                result = result_value(contract)
                if change == "missing":
                    del result["diagnostics"]["checks"][gate]
                else:
                    result["diagnostics"]["checks"][gate] = change
                with self.subTest(gate=gate, change=change), self.assertRaises(ValueError):
                    validate_case_result(result, contract)

    def test_convergence_cannot_claim_stability_or_local_minimum(self):
        contract = contract_value()
        for value in (None, True, "PASS", "STABLE", "LOCAL_MINIMUM", "CONFIRMED"):
            for key in ("stability_status", "stability"):
                result = result_value(contract)
                result[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    validate_case_result(result, contract)

    def test_nested_execution_contract_keeps_strict_boolean_and_integer_types(self):
        contract = contract_value()
        # These replacements compare equal under ordinary Python dict equality.
        # They must still fail the closed contract's strict type validation.
        for key, value in (("scientific_execution_authorized", 1), ("threads", True),
                           ("scf_kernel_call_limit", 1.0), ("boys_kernel_call_limit", False)):
            result = result_value(contract)
            result["execution_identity"][key] = value
            self.assertEqual(result["execution_identity"], contract)
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_case_result(result, contract)


if __name__ == "__main__":
    unittest.main()
