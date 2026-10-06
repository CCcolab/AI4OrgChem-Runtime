"""Standard-library contract/admission tests; no reservation or scientific work.

The historical proposal supplies frozen inputs. Every authorization and live
counter below is a local test fixture, never an actual execution receipt.
"""
import copy
import hashlib
import json
from pathlib import Path
import unittest

from runtime.user_molecule import residual_execution_contract as execution


ROOT = Path(__file__).resolve().parents[1]
PROPOSAL_PATH = ROOT / "validation/user-molecule/residual-diagnostic/contract-v1.json"
PROFILE_PATH = ROOT / "profiles/user-molecule/pilot-b3lypg-sto3g-grid2-v1.json"
MANIFEST_PATH = ROOT / "locks/source-user-molecule-files.sha256.json"
GIB = 1024 ** 3


def byte_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def independent_json_sha(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def contract_fixture():
    proposal = json.loads(PROPOSAL_PATH.read_bytes())
    process_keys = ("memory_limit_mib", "threads", "swap_allowed",
                    "maximum_scientific_processes", "process_wall_seconds",
                    "batch_wall_seconds", "candidate_callbacks_per_path",
                    "conditional_callback_slots_total", "serial_paths",
                    "automatic_retry")
    return {
        "schema_version": "residual-live-execution-contract-v1",
        "scientific_execution_authorized": True,
        "production_activation": False,
        "method_approval": False,
        "authorization_basis": {"source": "DIRECT_USER_MESSAGE",
                                "message": "请继续下一步实施准入和诊断"},
        "batch_id": "stdlib-execution-contract-fixture-never-reserved",
        "runtime_test_commit": "a1" * 20,
        "science_commit": proposal["science_commit"],
        "science_baseline_commit": proposal["science_baseline_commit"],
        "image_id": proposal["image_id"],
        "image_build_runtime_commit": proposal["image_build_runtime_commit"],
        "prior_proposal_sha256": byte_sha(PROPOSAL_PATH),
        "profile_sha256": byte_sha(PROFILE_PATH),
        "source_manifest_sha256": byte_sha(MANIFEST_PATH),
        "expected_dependencies": {"pyscf": "2.14.0", "numpy": "2.5.1", "scipy": "1.18.0"},
        "dependencies_sha256": independent_json_sha(
            {"pyscf": "2.14.0", "numpy": "2.5.1", "scipy": "1.18.0"}),
        "process_contract": {key: proposal["scientific_process_contract_proposal"][key]
                             for key in process_keys},
        "fixture": copy.deepcopy(proposal["fixture"]),
        "ordinary_origin": copy.deepcopy(proposal["ordinary_origin"]),
        "initialization": copy.deepcopy(proposal["initialization"]),
        "paths": copy.deepcopy(proposal["paths"]),
        "comparisons": copy.deepcopy(proposal["comparisons"]),
        "scope_limits": copy.deepcopy(proposal["scope_limits"]),
        "solver_parameters": {"maximum_iterations": 8, "maximum_backtracks": 8,
                              "finite_difference_step": 1e-5, "trust_radius": .25},
        "admission": {"minimum_host_free_bytes": 2 * GIB,
                      "minimum_vm_available_bytes": 2 * GIB,
                      "host_receipt_sha256": "b2" * 32},
    }


def cgroup_fixture(version="CGROUP_V1"):
    return {
        "source": version,
        "memory_limit_bytes": GIB,
        "memory_limit_unbounded": False,
        "memory_swap_limit_bytes": 0,
        "memory_swap_limit_unbounded": False,
        "memory_current_bytes": 64 * 1024 ** 2,
        "cpu_quota_us": 100000,
        "cpu_period_us": 100000,
        "cpu_limit_unbounded": False,
        "memory_events": ({"limit_failures": 0, "under_oom": 0, "oom_kill": None}
                          if version == "CGROUP_V1" else {"oom": 0, "oom_kill": 0}),
    }


class ResidualExecutionContractTests(unittest.TestCase):
    def setUp(self):
        self.contract = contract_fixture()

    def refuse(self, mutate):
        value = copy.deepcopy(self.contract)
        mutate(value)
        with self.assertRaises(execution.ExecutionContractError):
            execution.validate_execution_contract(value)

    def admission(self, observation=None, available=2 * GIB):
        return execution.pre_functional_admission(
            cgroup_fixture() if observation is None else observation,
            available, self.contract)

    def test_authorized_fixture_keeps_method_and_production_disabled_without_mutation(self):
        before = copy.deepcopy(self.contract)
        checked = execution.validate_execution_contract(self.contract)
        self.assertEqual(checked, before)
        self.assertEqual(self.contract, before)
        self.assertIs(checked["scientific_execution_authorized"], True)
        self.assertIs(checked["production_activation"], False)
        self.assertIs(checked["method_approval"], False)

    def test_engineering_proposal_is_preserved_and_not_reinterpreted_as_authorized(self):
        before = PROPOSAL_PATH.read_bytes()
        proposal = json.loads(before)
        self.assertEqual(proposal["persistent_accounting"]["real_scientific_reservation_this_round"],
                         "NOT_CREATED")
        self.assertEqual(proposal["scientific_process_contract_proposal"]["real_execution_authorization"],
                         "NOT_GRANTED_BY_THIS_ENGINEERING_CONTRACT")
        with self.assertRaises(execution.ExecutionContractError):
            execution.validate_execution_contract(proposal)
        self.assertEqual(PROPOSAL_PATH.read_bytes(), before)

    def test_explicit_direct_authorization_and_closed_production_flags_are_required(self):
        for field, bad in (("scientific_execution_authorized", False),
                           ("scientific_execution_authorized", 1),
                           ("production_activation", True), ("production_activation", 0),
                           ("method_approval", True), ("method_approval", 0)):
            with self.subTest(field=field, bad=bad):
                self.refuse(lambda value: value.__setitem__(field, bad))
        for field, bad in (("source", "ENGINEERING_RECORD"), ("message", "继续工程准备")):
            with self.subTest(field=field):
                self.refuse(lambda value: value["authorization_basis"].__setitem__(field, bad))

    def test_fixed_science_image_and_complete_old_cache_identities_are_required(self):
        for field in ("science_commit", "science_baseline_commit", "image_build_runtime_commit"):
            with self.subTest(field=field):
                self.refuse(lambda value: value.__setitem__(field, "f0" * 20))
        self.refuse(lambda value: value.__setitem__("image_id", "sha256:" + "f0" * 32))
        for name in ("record", "arrays"):
            with self.subTest(name=name):
                self.refuse(lambda value: value["ordinary_origin"][name].__setitem__("sha256", "f0" * 32))
        self.refuse(lambda value: value["ordinary_origin"]["common_density_identity"].__setitem__(
            "sha256", "f0" * 32))
        self.refuse(lambda value: value["ordinary_origin"].__setitem__("record_file", "ordinary-tested.json"))
        self.refuse(lambda value: value["ordinary_origin"].__setitem__("arrays_file", "common-D0.npy"))

    def test_dependency_and_malformed_execution_identities_are_rejected(self):
        self.refuse(lambda value: value["expected_dependencies"].__setitem__("pyscf", "different"))
        self.refuse(lambda value: value.__setitem__("dependencies_sha256", "f0" * 32))
        for field in ("runtime_test_commit", "prior_proposal_sha256", "profile_sha256",
                      "source_manifest_sha256"):
            with self.subTest(field=field):
                self.refuse(lambda value: value.__setitem__(field, "short"))
        self.refuse(lambda value: value["admission"].__setitem__("host_receipt_sha256", "short"))

    def test_process_limits_cannot_expand_or_retry(self):
        bad_limits = {"memory_limit_mib": 2048, "threads": 2, "swap_allowed": True,
                      "maximum_scientific_processes": 2, "process_wall_seconds": 901,
                      "batch_wall_seconds": 1800, "candidate_callbacks_per_path": 202,
                      "conditional_callback_slots_total": 604, "serial_paths": False,
                      "automatic_retry": True}
        for key, bad in bad_limits.items():
            with self.subTest(key=key):
                self.refuse(lambda value: value["process_contract"].__setitem__(key, bad))

    def test_integer_limits_cannot_be_floats_or_boolean_equivalents(self):
        for section, field, bad in (("process_contract", "threads", True),
                                   ("process_contract", "memory_limit_mib", 1024.0),
                                   ("process_contract", "swap_allowed", 0),
                                   ("fixture", "electron_count", 16.0),
                                   ("fixture", "nao", 14.0),
                                   ("solver_parameters", "maximum_iterations", 8.0),
                                   ("solver_parameters", "maximum_backtracks", True)):
            with self.subTest(section=section, field=field):
                self.refuse(lambda value: value[section].__setitem__(field, bad))

    def test_fixed_initialization_and_serial_path_choices_cannot_change(self):
        self.refuse(lambda value: value["initialization"].__setitem__("policy", "REQUIRE_EXISTING_MASKED_PROJECTOR"))
        self.refuse(lambda value: value["initialization"].__setitem__("initial_gap_minimum_hartree", 0.))
        self.refuse(lambda value: value["paths"].reverse())
        self.refuse(lambda value: value["paths"][0].__setitem__("eri_mode", "INPLACE_OWNED"))
        self.refuse(lambda value: value["paths"][1].__setitem__("optimize_eri_contractions", True))
        self.refuse(lambda value: value["paths"][2].__setitem__("callback_slots", 201.0))

    def test_solver_strategy_parameters_are_frozen(self):
        for field, bad in (("maximum_iterations", 9), ("maximum_backtracks", 9),
                           ("finite_difference_step", 1e-4), ("trust_radius", .5),
                           ("finite_difference_step", float("nan"))):
            with self.subTest(field=field):
                self.refuse(lambda value: value["solver_parameters"].__setitem__(field, bad))

    def test_original_comparison_tolerances_cannot_be_relaxed(self):
        comparisons = self.contract["comparisons"]
        for field, original in comparisons.items():
            if isinstance(original, (int, float)):
                with self.subTest(field=field):
                    self.refuse(lambda value: value["comparisons"].__setitem__(field, original * 10))
        for field, original in comparisons["T05_same_density"].items():
            with self.subTest(field="T05_same_density." + field):
                changed = original * 10 if original else 1e-12
                self.refuse(lambda value: value["comparisons"]["T05_same_density"].__setitem__(field, changed))
        self.refuse(lambda value: value["comparisons"]["T05_same_density"].__setitem__(
            "mask_max_abs", False))

    def test_host_and_vm_floors_are_independent_fixed_two_gib_guards(self):
        for field in ("minimum_host_free_bytes", "minimum_vm_available_bytes"):
            for bad in (GIB, 3 * GIB, float(2 * GIB), True):
                with self.subTest(field=field, bad=bad):
                    self.refuse(lambda value: value["admission"].__setitem__(field, bad))
        self.assertEqual(self.admission(available=2 * GIB)["status"],
                         "ADMITTED_FOR_BOUNDED_DIAGNOSTIC_START")
        blocked = self.admission(available=2 * GIB - 1)
        self.assertEqual(blocked["status"], "BLOCKED")
        self.assertIn("VM_AVAILABLE_BELOW_REQUIRED_2GIB_OR_UNKNOWN", blocked["reasons"])

    def test_v1_missing_oom_kill_history_allows_start_but_never_final_qualification(self):
        result = self.admission()
        self.assertEqual(result["status"], "ADMITTED_FOR_BOUNDED_DIAGNOSTIC_START")
        self.assertEqual(result["oom_kill_history"], "UNKNOWN_PENDING_COMPLETED_INSPECT")
        self.assertEqual(result["resource_qualification"], "NOT_YET_FINAL")
        self.assertIs(result["production_activation"], False)
        self.assertIs(result["method_approval"], False)

    def test_v2_clear_native_events_still_require_final_resource_receipt(self):
        result = self.admission(cgroup_fixture("CGROUP_V2"))
        self.assertEqual(result["status"], "ADMITTED_FOR_BOUNDED_DIAGNOSTIC_START")
        self.assertEqual(result["oom_kill_history"], "NATIVE_COUNTER_RECORDED")
        self.assertEqual(result["resource_qualification"], "NOT_YET_FINAL")

    def test_actual_memory_swap_cpu_and_current_memory_are_checked_before_f(self):
        for field, bad in (("source", "DOCKER_FLAGS_ONLY"),
                           ("memory_limit_bytes", 256 * 1024 ** 2),
                           ("memory_limit_unbounded", True),
                           ("memory_swap_limit_bytes", GIB),
                           ("memory_swap_limit_unbounded", True),
                           ("memory_current_bytes", GIB),
                           ("memory_current_bytes", -1),
                           ("cpu_quota_us", 200000), ("cpu_quota_us", 0),
                           ("cpu_period_us", 0), ("cpu_limit_unbounded", True)):
            with self.subTest(field=field, bad=bad):
                sample = cgroup_fixture()
                sample[field] = bad
                self.assertEqual(self.admission(sample)["status"], "BLOCKED")

    def test_live_integer_counters_do_not_accept_bool_or_float_zero(self):
        for field, bad in (("memory_limit_bytes", float(GIB)),
                           ("memory_swap_limit_bytes", False),
                           ("memory_swap_limit_bytes", 0.0),
                           ("memory_current_bytes", False),
                           ("cpu_quota_us", True), ("cpu_period_us", True)):
            with self.subTest(field=field, bad=bad):
                sample = cgroup_fixture()
                sample[field] = bad
                self.assertEqual(self.admission(sample)["status"], "BLOCKED")
        for bad in (True, float(2 * GIB), None):
            with self.subTest(vm_available=bad):
                self.assertEqual(self.admission(available=bad)["status"], "BLOCKED")

    def test_oom_and_unknown_or_boolean_event_counters_block_start(self):
        for version, keys in (("CGROUP_V1", ("limit_failures", "under_oom", "oom_kill")),
                              ("CGROUP_V2", ("oom", "oom_kill"))):
            for field in keys:
                for bad in (1, False, 0.0):
                    with self.subTest(version=version, field=field, bad=bad):
                        sample = cgroup_fixture(version)
                        sample["memory_events"][field] = bad
                        self.assertEqual(self.admission(sample)["status"], "BLOCKED")
        for version in ("CGROUP_V1", "CGROUP_V2"):
            sample = cgroup_fixture(version)
            sample["memory_events"] = None
            self.assertEqual(self.admission(sample)["status"], "BLOCKED")

    def test_execution_identity_binds_new_receipt_to_exact_old_cache_without_activation(self):
        digest = independent_json_sha(self.contract)
        result = execution.execution_identity(self.contract, digest)
        self.assertEqual(result["mode"], "LIVE_CONDITIONAL_DIAGNOSTIC")
        self.assertEqual(result["execution_contract_sha256"], digest)
        self.assertEqual(result["ordinary_record_sha256"], self.contract["ordinary_origin"]["record"]["sha256"])
        self.assertEqual(result["ordinary_arrays_sha256"], self.contract["ordinary_origin"]["arrays"]["sha256"])
        self.assertEqual(result["runtime_test_commit"], self.contract["runtime_test_commit"])
        with self.assertRaises(execution.ExecutionContractError):
            execution.execution_identity(self.contract, "short")

    def test_proposal_bytes_and_definitions_are_bound_without_rewriting_history(self):
        raw=PROPOSAL_PATH.read_bytes()
        self.assertTrue(execution.validate_proposal_binding(self.contract,raw))
        with self.assertRaises(execution.ExecutionContractError):
            execution.validate_proposal_binding(self.contract,raw+b'\n')
        altered=copy.deepcopy(self.contract)
        altered['ordinary_origin']['array_identities']['hcore']['sha256']='f0'*32
        with self.assertRaises(execution.ExecutionContractError):
            execution.validate_proposal_binding(altered,raw)

    def test_native_cgroup_read_errors_refuse_before_f(self):
        sample=cgroup_fixture();sample['errors']=[{'file':'cpu.max','message':'missing'}]
        self.assertEqual(self.admission(sample)['status'],'BLOCKED')


if __name__ == "__main__":
    unittest.main()
