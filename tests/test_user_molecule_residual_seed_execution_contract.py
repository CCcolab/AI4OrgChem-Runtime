"""Standard-library exact seed policy/provenance rejection tests, no science."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from runtime.user_molecule import residual_execution_contract as previous
from runtime.user_molecule import residual_seed_execution_contract as execution
from test_user_molecule_residual_execution_contract import (
    PROPOSAL_PATH, contract_fixture as old_fixture, cgroup_fixture, GIB)


def array_identity(shape, digest):
    return {"shape": shape, "dtype": "<f8", "order": "C", "sha256": digest}


def contract_fixture():
    value = old_fixture()
    value.update(schema_version=execution.SCHEMA,
        authorization_basis={"source": "DIRECT_USER_MESSAGE", "message": execution.AUTHORIZATION_MESSAGE},
        external_review_status="CANCELLED", external_review_required=False)
    value["initialization"] = {"policy": execution.POLICY, "initial_gap_enforced": False,
                               "final_gap_minimum_hartree": 1e-6}
    value["seed_binding"] = {
        "policy": execution.POLICY, "record_sha256": value['ordinary_origin']['record']['sha256'],
        "arrays_sha256": value['ordinary_origin']['arrays']['sha256'],
        "shared_seed_archive_sha256": "90" * 32,
        "readiness_receipt_sha256": "30" * 32, "implementation_runtime_commit": "40" * 20,
        "source_file_sha256": {path: "50" * 32 for path in execution.REQUIRED_SEED_SOURCE_FILES},
        "mdr002_record_sha256": "60" * 32, "expert_cancellation_receipt_sha256": "70" * 32,
        "ordinary_D0_identity": copy.deepcopy(value["ordinary_origin"]["common_density_identity"]),
        "ordinary_mo_coefficients_identity": array_identity([14, 14], execution.FROZEN_MO_COEFFICIENTS_SHA256),
        "ordinary_mo_occupations_identity": array_identity([14], execution.FROZEN_MO_OCCUPATIONS_SHA256),
        "seed_density_identity": array_identity([14, 14], "80" * 32)}
    return value


def readiness_fixture():
    """Measured-format evidence only; no imported array test case or engine."""
    def row(value=1e-14, threshold=1e-10, *, reference=False, comparison="<="):
        return {"value" if reference else "observed": value, "threshold": threshold,
                "passed" if reference else "pass": True, "comparison": comparison}
    production = {"policy_id": execution.POLICY, "status": "ADMITTED_SEED_ONLY",
        "definition_status": "PASS_SEED_DEFINITION", "solver_admission_status": "PASS_PRODUCTION_SEED_ADMISSION",
        "functional_calls": 0, "scientific_approval": False, "production_activation": False,
        "repairs_performed": False,
        "definition_checks": {
            "ordinary_density_reconstruction": row(),
            "physical_overlap_positive_definite": {"observed": .2, "pass": True},
            "masked_overlap_condition_number": row(10., 1e6)},
        "solver_admission_checks": {name: row() for name in
            ("whitened_trace", "whitened_idempotency", "production_density_reconstruction")},
        "shared_seed_admission": {"status": "NOT_APPLICABLE_LOCAL_SEED_USED"}}
    reference = {"policy_id": execution.POLICY, "status": "PASS_ARRAY_SEED_AND_REFERENCE_ENTRY_ONLY",
        "functional_calls": 0, "scientific_approval": False, "input_arrays_mutated": False,
        "definition_checks": {"seed_electron_count": row(1e-14, 1e-7, reference=True),
                              "occupied_gram_minimum_eigenvalue": row(.2, 0., reference=True, comparison=">")},
        "solver_entry_checks": {name: row(reference=True) for name in
            ("white_projector_trace", "white_projector_idempotency")},
        "shared_seed_admission": {"status": "PASS_ARRAY_REFERENCE_ENTRY_ONLY", "functional_calls": 0,
            "checks": {name: row(reference=True) for name in
                ("white_projector_trace", "white_projector_idempotency", "independent_seed_agreement")}}}
    return {"schema_version": "seed-v2-cached-readiness-v1", "status": "PASS_SEED_V2_CACHED_PREPARATION_ONLY",
        "policy": execution.POLICY, "runtime_test_commit": "ab"*20,
        "new_functional_calls": 0,
        "forbidden_operation_counts": {name: 0 for name in ("SCF", "GRID", "INTEGRAL", "NR_RKS")},
        "three_used_seeds_byte_identical": True,
        "reference_constructed_to_common_seed_relative_frobenius": 1e-14,
        "reference_difference_threshold": 1e-10, "reference_difference_denominator": "max(||commonseed||F,1)",
        "source_file_sha256": {name: "cd"*32 for name in execution.REQUIRED_SEED_SOURCE_FILES},
        "scientific_execution": "NOT_EXECUTED", "production_activation": False,
        "final_endpoint_gates": "UNCHANGED_NOT_EXECUTED", "research_acceptance": "NOT_ACCEPTED", "deltas": None,
        "initial_gap_qualification": "NOT_APPLICABLE_TO_SEED; FIRST_F_GAP_DIAGNOSTIC_ONLY",
        "final_gap_minimum_hartree": 1e-6,
        "receipts": {"production_copy": copy.deepcopy(production), "production_owned": copy.deepcopy(production),
                     "independent_reference": reference}}


class SeedReadinessBodyTests(unittest.TestCase):
    def refuse(self, mutation):
        value = readiness_fixture()
        mutation(value)
        with self.assertRaises(execution.ExecutionContractError):
            execution.validate_seed_readiness(value)

    def test_measured_readiness_is_returned_without_mutation_or_scientific_qualification(self):
        value = readiness_fixture()
        before = copy.deepcopy(value)
        self.assertIs(execution.validate_seed_readiness(value), value)
        self.assertEqual(value, before)
        self.assertEqual(value["scientific_execution"], "NOT_EXECUTED")
        self.assertIs(value["production_activation"], False)

    def test_functional_and_guard_counters_are_exact_integers_not_boolean_zero(self):
        for bad in (False, True, 0., -1, 1, None):
            self.refuse(lambda value: value.__setitem__("new_functional_calls", bad))
            self.refuse(lambda value: value["forbidden_operation_counts"].__setitem__("NR_RKS", bad))
            self.refuse(lambda value: value["receipts"]["production_owned"].__setitem__("functional_calls", bad))
            self.refuse(lambda value: value["receipts"]["independent_reference"]["shared_seed_admission"].__setitem__("functional_calls", bad))
        self.refuse(lambda value: value["forbidden_operation_counts"].pop("SCF"))

    def test_zero_functional_flags_cannot_grant_research_or_hide_mutation(self):
        for key, bad in (("production_activation", 0), ("production_activation", True),
                         ("scientific_execution", "EXECUTED"), ("research_acceptance", "PASS"),
                         ("final_endpoint_gates", "PASS"), ("deltas", {}), ("final_gap_minimum_hartree", 1e-7)):
            self.refuse(lambda value: value.__setitem__(key, bad))
        for key in ("repairs_performed", "scientific_approval", "method_approval", "input_arrays_mutated"):
            self.refuse(lambda value: value.__setitem__(key, 0))
            self.refuse(lambda value: value.__setitem__(key, True))
        self.refuse(lambda value: value["receipts"]["independent_reference"].__setitem__("input_arrays_mutated", 0))

    def test_same_seed_and_reference_equivalence_need_actual_finite_measurements(self):
        for bad in (1, False, None):
            self.refuse(lambda value: value.__setitem__("three_used_seeds_byte_identical", bad))
        for bad in (True, -1e-14, 2e-10, float("nan"), float("inf")):
            self.refuse(lambda value: value.__setitem__("reference_constructed_to_common_seed_relative_frobenius", bad))
        for bad in (True, 1e-9, 0):
            self.refuse(lambda value: value.__setitem__("reference_difference_threshold", bad))
        self.refuse(lambda value: value.__setitem__("reference_difference_denominator", "relative to arbitrary density"))

    def test_actual_policy_sources_and_commit_cannot_be_omitted_or_malformed(self):
        self.refuse(lambda value: value.__setitem__("policy", "FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0"))
        self.refuse(lambda value: value.__setitem__("runtime_test_commit", "short"))
        self.refuse(lambda value: value.__setitem__("source_file_sha256", {}))
        self.refuse(lambda value: value["source_file_sha256"].__setitem__("../outside.py", "ab"*32))
        self.refuse(lambda value: value["source_file_sha256"].__setitem__("reference/seed_v2.py", "short"))
        self.refuse(lambda value: value["receipts"]["production_copy"].__setitem__("policy_id", "other"))
        self.refuse(lambda value: value["receipts"].pop("production_owned"))

    def test_pass_flags_do_not_replace_measured_definition_values(self):
        for bad in (True, None, float("nan"), float("inf"), 1e-6, -1):
            self.refuse(lambda value: value["receipts"]["production_copy"]["definition_checks"]
                ["ordinary_density_reconstruction"].__setitem__("observed", bad))
        for bad in (1, False, None):
            self.refuse(lambda value: value["receipts"]["production_copy"]["definition_checks"]
                ["ordinary_density_reconstruction"].__setitem__("pass", bad))
        self.refuse(lambda value: value["receipts"]["production_copy"].__setitem__("definition_checks", {}))
        self.refuse(lambda value: value["receipts"]["production_copy"]["definition_checks"]
            ["ordinary_density_reconstruction"].__setitem__("value", 1e-9))

    def test_positive_definiteness_is_remeasured_for_both_check_formats(self):
        for bad in (0, -.1, True):
            self.refuse(lambda value: value["receipts"]["production_copy"]["definition_checks"]
                ["physical_overlap_positive_definite"].__setitem__("observed", bad))
            self.refuse(lambda value: value["receipts"]["independent_reference"]["definition_checks"]
                ["occupied_gram_minimum_eigenvalue"].__setitem__("value", bad))
        self.refuse(lambda value: value["receipts"]["independent_reference"]["definition_checks"]
            ["occupied_gram_minimum_eigenvalue"].__setitem__("comparison", "<="))
        self.refuse(lambda value: value["receipts"]["production_copy"]["definition_checks"]
            ["masked_overlap_condition_number"].__setitem__("threshold", 1e7))

    def test_production_entry_requires_all_three_original_absolute_gates(self):
        for name in ("whitened_trace", "whitened_idempotency", "production_density_reconstruction"):
            self.refuse(lambda value: value["receipts"]["production_owned"]["solver_admission_checks"].pop(name))
            self.refuse(lambda value: value["receipts"]["production_owned"]["solver_admission_checks"][name].__setitem__("threshold", 1e-7))
            self.refuse(lambda value: value["receipts"]["production_owned"]["solver_admission_checks"][name].__setitem__("observed", 2e-10))
            self.refuse(lambda value: value["receipts"]["production_owned"]["solver_admission_checks"][name].__setitem__("comparison", ">"))
        self.refuse(lambda value: value["receipts"]["production_copy"].__setitem__("definition_status", "PASS"))
        self.refuse(lambda value: value["receipts"]["production_copy"].__setitem__("solver_admission_status", "NOT_EXECUTED"))

    def test_reference_entry_and_actual_shared_seed_all_require_old_gates(self):
        for name in ("white_projector_trace", "white_projector_idempotency"):
            self.refuse(lambda value: value["receipts"]["independent_reference"]["solver_entry_checks"].pop(name))
            self.refuse(lambda value: value["receipts"]["independent_reference"]["solver_entry_checks"][name].__setitem__("threshold", 1e-7))
        for name in ("white_projector_trace", "white_projector_idempotency", "independent_seed_agreement"):
            self.refuse(lambda value: value["receipts"]["independent_reference"]["shared_seed_admission"]["checks"].pop(name))
            self.refuse(lambda value: value["receipts"]["independent_reference"]["shared_seed_admission"]["checks"][name].__setitem__("value", 2e-10))
        self.refuse(lambda value: value["receipts"]["independent_reference"]["shared_seed_admission"].__setitem__("status", "NOT_REQUESTED"))

    def test_local_production_seed_exception_does_not_skip_actual_shared_checks(self):
        value = readiness_fixture()
        shared = {"status": "PASS_SHARED_SEED_PRODUCTION_ADMISSION", "functional_calls": 0,
                  "repairs_performed": False,
                  "checks": copy.deepcopy(value["receipts"]["production_copy"]["solver_admission_checks"])}
        shared["checks"]["local_seed_agreement"] = {"observed": 1e-14, "threshold": 1e-10, "pass": True}
        value["receipts"]["production_copy"]["shared_seed_admission"] = shared
        execution.validate_seed_readiness(value)
        shared["checks"]["whitened_idempotency"]["observed"] = 2e-10
        with self.assertRaises(execution.ExecutionContractError):
            execution.validate_seed_readiness(value)
        self.refuse(lambda value: value["receipts"]["production_owned"]["shared_seed_admission"].__setitem__("status", "REFUSED"))

    def test_extra_nonfinite_payload_and_incomplete_receipts_refuse(self):
        self.refuse(lambda value: value.__setitem__("extra", float("inf")))
        self.refuse(lambda value: value.__setitem__("schema_version", "old"))
        self.refuse(lambda value: value.pop("receipts"))
        self.refuse(lambda value: value.__setitem__("receipts", []))


class ResidualSeedExecutionContractTests(unittest.TestCase):
    def setUp(self):
        self.contract = contract_fixture()

    def refuse(self, mutation):
        value = copy.deepcopy(self.contract)
        mutation(value)
        with self.assertRaises(execution.ExecutionContractError):
            execution.validate_execution_contract(value)

    def test_actual_policy_schema_and_user_message_are_new_and_input_is_not_mutated(self):
        before = copy.deepcopy(self.contract)
        checked = execution.validate_execution_contract(self.contract)
        self.assertIs(checked, self.contract)
        self.assertEqual(checked, before)
        self.assertEqual(checked["initialization"]["policy"], execution.POLICY)
        self.assertNotEqual(checked["schema_version"], old_fixture()["schema_version"])
        with self.assertRaises(execution.ExecutionContractError):
            execution.validate_execution_contract(old_fixture())
        with self.assertRaises(previous.ExecutionContractError):
            previous.validate_execution_contract(self.contract)
        self.assertEqual(self.contract, before)

    def test_old_authorization_or_initialization_cannot_approve_new_seed(self):
        for policy in ("FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0", "REQUIRE_EXISTING_MASKED_PROJECTOR"):
            self.refuse(lambda value: value["initialization"].__setitem__("policy", policy))
            self.refuse(lambda value: value["seed_binding"].__setitem__("policy", policy))
        for key, changed in (("source", "HISTORICAL_PROPOSAL"), ("message", "请继续下一步实施准入和诊断")):
            self.refuse(lambda value: value["authorization_basis"].__setitem__(key, changed))

    def test_initial_gap_is_diagnostic_but_final_gap_cannot_change(self):
        for bad in (True, 0, None):
            self.refuse(lambda value: value["initialization"].__setitem__("initial_gap_enforced", bad))
        for bad in (0, 1e-7, 1e-5, True, float("nan")):
            self.refuse(lambda value: value["initialization"].__setitem__("final_gap_minimum_hartree", bad))

    def test_external_cancellation_does_not_become_method_or_production_approval(self):
        self.refuse(lambda value: value.__setitem__("external_review_required", True))
        self.refuse(lambda value: value.__setitem__("external_review_required", 0))
        self.refuse(lambda value: value.__setitem__("external_review_status", "APPROVED"))
        self.refuse(lambda value: value.__setitem__("method_approval", True))
        self.refuse(lambda value: value.__setitem__("production_activation", True))

    def test_all_seed_files_receipts_and_commit_are_complete_hashes(self):
        for key in ("record_sha256", "arrays_sha256", "shared_seed_archive_sha256", "readiness_receipt_sha256",
                    "mdr002_record_sha256", "expert_cancellation_receipt_sha256", "implementation_runtime_commit"):
            self.refuse(lambda value: value["seed_binding"].__setitem__(key, "short"))
            self.refuse(lambda value: value["seed_binding"].pop(key))
        self.refuse(lambda value: value["seed_binding"].__setitem__("source_file_sha256", {}))
        for path in execution.REQUIRED_SEED_SOURCE_FILES:
            self.refuse(lambda value: value["seed_binding"]["source_file_sha256"].pop(path))
            self.refuse(lambda value: value["seed_binding"]["source_file_sha256"].__setitem__(path, "short"))

    def test_source_file_paths_must_stay_canonical_relative(self):
        for path in ("../other.py", "/root.py", "D:/outside.py", "runtime\\seed.py",
                     "runtime//seed.py", "runtime/./seed.py"):
            self.refuse(lambda value: value["seed_binding"]["source_file_sha256"].__setitem__(path, "ab" * 32))

    def test_d0_and_mo_provenance_must_be_the_full_old_ordinary_source(self):
        for key in ("ordinary_D0_identity", "ordinary_mo_coefficients_identity", "ordinary_mo_occupations_identity"):
            self.refuse(lambda value: value["seed_binding"][key].__setitem__("sha256", "ee" * 32))
            self.refuse(lambda value: value["seed_binding"].pop(key))
        self.refuse(lambda value: value["ordinary_origin"]["common_density_identity"].__setitem__("sha256", "ee" * 32))
        self.refuse(lambda value: value["seed_binding"].__setitem__("seed_density_identity",
                    copy.deepcopy(value["seed_binding"]["ordinary_D0_identity"])))

    def test_array_shape_dtype_order_and_exact_typed_dimensions_cannot_change(self):
        for key in ("ordinary_D0_identity", "ordinary_mo_coefficients_identity",
                    "ordinary_mo_occupations_identity", "seed_density_identity"):
            for field, bad in (("shape", [14.0, 14]), ("shape", [True]), ("dtype", ">f8"), ("order", "F")):
                self.refuse(lambda value: value["seed_binding"][key].__setitem__(field, bad))
        self.refuse(lambda value: value["seed_binding"]["seed_density_identity"].__setitem__("guess", True))

    def test_resource_path_solver_and_comparison_invariants_remain_frozen(self):
        for field, bad in (("memory_limit_mib", 2048), ("threads", 2), ("swap_allowed", True),
                           ("maximum_scientific_processes", 2), ("process_wall_seconds", 901),
                           ("batch_wall_seconds", 1800), ("candidate_callbacks_per_path", 202),
                           ("conditional_callback_slots_total", 604), ("serial_paths", False), ("automatic_retry", True)):
            self.refuse(lambda value: value["process_contract"].__setitem__(field, bad))
        self.refuse(lambda value: value["paths"].reverse())
        self.refuse(lambda value: value["paths"][1].__setitem__("optimize_eri_contractions", True))
        self.refuse(lambda value: value["solver_parameters"].__setitem__("trust_radius", .5))
        self.refuse(lambda value: value["comparisons"].__setitem__("P12_energy_difference_hartree", 1e-9))
        self.refuse(lambda value: value["comparisons"]["T05_same_density"].__setitem__("matrix_frobenius", 1e-8))

    def test_old_proposal_bytes_and_invariants_are_bound_but_its_policy_is_preserved(self):
        raw = PROPOSAL_PATH.read_bytes()
        old = json.loads(raw)
        self.assertNotEqual(old["initialization"], self.contract["initialization"])
        self.assertTrue(execution.validate_proposal_binding(self.contract, raw))
        self.assertEqual(PROPOSAL_PATH.read_bytes(), raw)
        with self.assertRaises(execution.ExecutionContractError):
            execution.validate_proposal_binding(self.contract, raw + b"\n")
        for key in ("fixture", "ordinary_origin", "paths", "comparisons", "scope_limits"):
            modified = copy.deepcopy(self.contract)
            if key == "scope_limits":
                modified[key]["research_w07"] = "PASS"
            elif key == "ordinary_origin":
                modified[key]["array_identities"]["hcore"]["sha256"] = "ee" * 32
            elif key == "fixture":
                modified[key]["orientation"] = "reoriented"
            elif key == "paths":
                modified[key][0]["new_note"] = "different"
            else:
                modified[key]["acceptance"] = "ignore same-root"
            with self.assertRaises(execution.ExecutionContractError):
                execution.validate_proposal_binding(modified, raw)

    def test_identity_never_exports_private_legacy_policy_or_drops_seed_binding(self):
        actual = execution.execution_identity(self.contract, "ab" * 32)
        self.assertEqual(actual["mode"], "LIVE_CONDITIONAL_SEED_V2_DIAGNOSTIC")
        self.assertEqual(actual["initialization_policy"], execution.POLICY)
        self.assertEqual(actual["seed_density_identity"], self.contract["seed_binding"]["seed_density_identity"])
        self.assertEqual(actual["ordinary_D0_identity"], self.contract["seed_binding"]["ordinary_D0_identity"])
        self.assertEqual(actual["seed_readiness_receipt_sha256"], self.contract["seed_binding"]["readiness_receipt_sha256"])
        self.assertEqual(actual["shared_seed_archive_sha256"], self.contract["seed_binding"]["shared_seed_archive_sha256"])
        self.assertEqual(actual["seed_implementation_runtime_commit"], self.contract["seed_binding"]["implementation_runtime_commit"])
        self.assertEqual(actual["seed_source_file_sha256"], self.contract["seed_binding"]["source_file_sha256"])
        self.assertIs(actual["external_review_required"], False)
        self.assertIs(actual["method_approval"], False)
        self.assertIs(actual["production_activation"], False)
        with self.assertRaises(execution.ExecutionContractError):
            execution.execution_identity(self.contract, "short")

    def test_parent_cache_aliases_cannot_declare_another_ordinary_source(self):
        for key in ('record_sha256', 'arrays_sha256'):
            changed = copy.deepcopy(self.contract)
            changed['seed_binding'][key] = '11' * 32
            with self.assertRaises(execution.ExecutionContractError):
                execution.validate_execution_contract(changed)

    def test_native_admission_reuses_actual_limits_without_claiming_seed_or_final_qualification(self):
        actual = execution.pre_functional_admission(cgroup_fixture(), 2 * GIB, self.contract)
        self.assertEqual(actual["status"], "ADMITTED_FOR_BOUNDED_DIAGNOSTIC_START")
        self.assertEqual(actual["initialization_policy"], execution.POLICY)
        self.assertEqual(actual["resource_qualification"], "NOT_YET_FINAL")
        self.assertIn("MUST_BE_VERIFIED_BY_SUPERVISOR", actual["seed_readiness_body_status"])
        for field, bad in (("memory_limit_bytes", 2 * GIB), ("memory_swap_limit_bytes", GIB),
                           ("cpu_quota_us", 200000), ("source", "REQUESTED_FLAGS")):
            sample = cgroup_fixture(); sample[field] = bad
            self.assertEqual(execution.pre_functional_admission(sample, 2 * GIB, self.contract)["status"], "BLOCKED")
        self.assertEqual(execution.pre_functional_admission(cgroup_fixture(), GIB, self.contract)["status"], "BLOCKED")

    def test_file_load_strict_json_does_not_authenticate_declared_seed_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "new-contract.json"
            path.write_text(json.dumps(self.contract), encoding="utf-8")
            self.assertEqual(execution.load_execution_contract(path), self.contract)
            path.write_text('{"schema_version":"x","schema_version":"y"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                execution.load_execution_contract(path)


if __name__ == "__main__":
    unittest.main()
