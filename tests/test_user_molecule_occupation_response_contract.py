"""Portable stdlib declaration/byte-binding tests; no scientific callbacks."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from runtime.user_molecule import occupation_response_contract as execution


def ordinary_origin_fixture():
    identities = {name: {"shape": shape, "dtype": "<f8", "order": "C", "sha256": digest}
                  for name, (shape, digest) in execution.FROZEN_ARRAYS.items()}
    return {"kind": "REUSE_PRIOR_FULL_INDEPENDENT_ORDINARY_REFERENCE",
        "record_file": "ordinary-reference.json", "arrays_file": "ordinary-reference.npz",
        "record": {"size_bytes": 11741, "sha256": "b0a9fd8a2487d725668823b75966176e98eb25551f40b9f177b485141ecb9663"},
        "arrays": {"size_bytes": 1728678, "sha256": "2a0318c42ee47001e2774ea6b4fec8317b1887c744a2720e71033a75b18f6051"},
        "array_identities": identities, "common_density_identity": copy.deepcopy(identities["density"]),
        "nuclear_repulsion_hartree": 33.23272494899829}


def array_check_fixture():
    """Synthetic measured-format rows, not claims about a real molecule."""
    return {"status": "PASS_NUMERICAL_ARRAY_IDENTITIES_ONLY",
        "observations": {"rank_of_white_projector_numpy": 8,
            "white_eigenvalues": [0.] * 6 + [1.] * 8, "masked_metric_electrons": 16.,
            "masked_metric_electrons_abs_error": 0., "closed_shell_DSD_minus_2D_frobenius": 0.,
            "closed_shell_DSD_minus_2D_relative": 0., "white_projector_trace": 8.,
            "white_trace_abs_error": 0., "white_idempotency_absolute_frobenius": 0.,
            "production_density_reconstruction_relative_frobenius": 0.,
            "density_symmetry_max_abs": 0., "half_inverse_identity_frobenius": 0.},
        "checks": {name: True for name in ("rank", "masked_electrons", "DSD_2D_relative",
            "white_trace", "white_idempotency", "production_reconstruction", "density_symmetry")},
        "thresholds": copy.deepcopy(execution.ARRAY_THRESHOLDS),
        "actual_solver_admission": "NOT_EXECUTED", "executable_seed": False,
        "initialization_policy_is_changed": False}


def npy_fixture(payload, shape=(14, 14), dtype="<f8", fortran=False):
    header = repr({"descr": dtype, "fortran_order": fortran, "shape": shape}).encode("latin1")
    header += b" " * ((64 - ((10 + len(header) + 1) % 64)) % 64) + b"\n"
    return b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header + payload


def synthetic_review_archive():
    """70 byte-only fixtures. Trust-anchor substitution is test-local only."""
    stream = io.BytesIO()
    members, witnesses = {}, []
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, witness_name in enumerate(execution.WITNESSES):
            payload = b"".join(struct.pack("<d", float(index + 1) if row == column and row < 8 else 0.)
                               for row in range(14) for column in range(14))
            member = "production_copy__witness__" + witness_name + "__density_NO_F_NO_ENERGY"
            metadata = {"shape": [14, 14], "dtype": "<f8", "sha256": hashlib.sha256(payload).hexdigest(), "finite": True}
            members[member] = metadata
            archive.writestr(member + ".npy", npy_fixture(payload))
            witnesses.append({"name": witness_name,
                "density_id": hashlib.sha256(b"AI4OrgChem-density-v1\0" + struct.pack("<QQ", 14, 14) + payload).hexdigest(),
                "array_members": {"density_NO_F_NO_ENERGY": member},
                "numerical_array_checks": array_check_fixture(),
                "F_at_this_new_density": "NOT_EXECUTED", "energy_at_this_new_density": None,
                "new_matched_operator_id": None, "new_energy_binding": None,
                "scientific_qualification": "NOT_GRANTED"})
        for index in range(67):
            member = "synthetic_member_" + str(index)
            payload = struct.pack("<d", float(index)) * 5
            members[member] = {"shape": [5], "dtype": "<f8", "sha256": hashlib.sha256(payload).hexdigest(), "finite": True}
            archive.writestr(member + ".npy", npy_fixture(payload, (5,)))
    archive_bytes = stream.getvalue()
    if len(archive_bytes) >= 49568:
        raise AssertionError("synthetic archive unexpectedly exceeds fixed test bound")
    archive_bytes += b"\0" * (49568 - len(archive_bytes))
    review = {"schema_version": "frozen-occupation-scope-review-v1",
        "status": "READONLY_SAVED_MATRIX_SCOPE_ANALYSIS_COMPLETE",
        "source_execution_commit": execution.SOURCE_EXECUTION, "source_delivery_commit": execution.SOURCE_DELIVERY,
        "source_image_id": execution.IMAGE, "prior_manifest_sha256": execution.OLD_SOURCE_MANIFEST,
        "new_true_molecular_F_calls": 0, "new_SCF_calls": 0, "new_NR_grid_integral_calls": 0,
        "new_scientific_processes": 0, "scientific_budget": None, "old_budget_reopened": False,
        "scientific_thresholds_changed": False, "Compute": False,
        "paths": [{"path": "production_copy", "original_fock_identity": copy.deepcopy(execution.SOURCE_F),
            "original_masked_overlap_identity": copy.deepcopy(execution.SOURCE_S),
            "original_true_snapshot_density_binding_verified": True, "occupation_witnesses": witnesses}],
        "array_archive": {"member_count": 70, "members": members, "size_bytes": 49568,
            "sha256": hashlib.sha256(archive_bytes).hexdigest()}}
    return review, archive_bytes


def contract_fixture(review=None, *, review_size_bytes=123):
    if review is None:
        review, _ = synthetic_review_archive()
    value = execution.minimal_template(ordinary_origin_fixture(), review, review_size_bytes=review_size_bytes)
    value.update(runtime_test_commit="ab" * 20, batch_id="occupation-response-test-fresh",
        source_manifest_sha256="ac" * 32, profile_sha256="ad" * 32, prior_proposal_sha256="ae" * 32,
        source_file_sha256={name: "af" * 32 for name in execution.REQUIRED_SOURCE_FILES})
    return value


class OccupationResponseContractTests(unittest.TestCase):
    def setUp(self):
        self.value = contract_fixture()

    def refuse(self, mutation):
        value = copy.deepcopy(self.value)
        mutation(value)
        with self.assertRaises(execution.ExecutionContractError):
            execution.validate_execution_contract(value)

    def test_template_is_inert_and_validation_does_not_mutate_or_authorize(self):
        before = copy.deepcopy(self.value)
        self.assertIs(execution.validate_execution_contract(self.value), self.value)
        self.assertEqual(self.value, before)
        self.assertIs(self.value["scientific_execution_authorized"], False)
        self.assertIs(self.value["production_activation"], False)
        self.value["scientific_execution_authorized"] = True
        self.assertIs(execution.validate_execution_contract(self.value), self.value)

    def test_execution_kind_and_authority_cannot_masquerade_as_fake_or_seed(self):
        for mode in ("ENGINEERING_FAKE", "PREPARED_MOLECULAR_DIAGNOSTIC", "MASKED_METRIC_OCCUPIED_SUBSPACE_SEED_V2"):
            self.refuse(lambda value: value.__setitem__("execution_kind", mode))
        self.refuse(lambda value: value.__setitem__("schema_version", "residual-seed-v2-live-execution-contract-v1"))
        self.refuse(lambda value: value["authorization_basis"].__setitem__("source", "DOCUMENT"))
        self.refuse(lambda value: value["authorization_basis"].__setitem__("message", "old message"))

    def test_authorization_approval_and_resource_boolean_types_are_exact(self):
        for bad in (0, 1, None, "true"):
            self.refuse(lambda value: value.__setitem__("scientific_execution_authorized", bad))
        for key in ("production_activation", "scientific_approval", "method_approval", "external_review_required"):
            for bad in (0, True):
                self.refuse(lambda value: value.__setitem__(key, bad))
        self.refuse(lambda value: value["process_contract"].__setitem__("automatic_retry", 0))

    def test_process_contract_is_exactly_nine_single_calls_no_tail_refund_retry(self):
        for key, bad in (("scientific_processes", 2), ("wall_seconds_through_cleanup", 121),
            ("hard_memory_bytes", 1073741825), ("maximum_cpus", 2), ("swap_bytes", 1),
            ("density_probes", 4), ("paths_per_probe", 4), ("total_true_F_or_NR_calls_maximum", 10),
            ("SCF_iterations", 1), ("new_ordinary_SCF_grid_full_integrals", 1), ("final_tail_calls", 1),
            ("automatic_retry", True), ("refund_failed_slots", True), ("budget_expansion_or_refill", True),
            ("non_root", False), ("offline", False), ("read_only_source_root_and_cache", False)):
            self.refuse(lambda value: value["process_contract"].__setitem__(key, bad))
        self.refuse(lambda value: value["process_contract"].__setitem__("total_true_F_or_NR_calls_maximum", 9.))
        self.refuse(lambda value: value["process_contract"].__setitem__("extra_slots", 1))

    def test_batch_ids_and_immutable_source_commits_are_complete(self):
        for batch in ("", "../escape", "a" * 129, "20261007-seed-v2-a1", "residual-live-20261006-a1"):
            self.refuse(lambda value: value.__setitem__("batch_id", batch))
        for key in ("runtime_test_commit", "science_commit", "science_baseline_commit", "image_id", "image_build_runtime_commit"):
            self.refuse(lambda value: value.__setitem__(key, "short"))
        for key in ("profile_sha256", "source_manifest_sha256", "prior_proposal_sha256", "dependencies_sha256"):
            self.refuse(lambda value: value.__setitem__(key, "A" * 64))

    def test_frozen_dependencies_and_fixed_geometry_cannot_be_substituted(self):
        self.refuse(lambda value: value["expected_dependencies"].__setitem__("scipy", "latest"))
        self.refuse(lambda value: value["fixture"].__setitem__("coordinate_unit", "bohr"))
        self.refuse(lambda value: value["fixture"].__setitem__("nao", True))
        self.refuse(lambda value: value["fixture"].__setitem__("xyz_sha256", "ff" * 32))

    def test_original_final_and_comparison_thresholds_remain_unchanged(self):
        for key in execution.FINAL_THRESHOLDS:
            self.refuse(lambda value: value["final_thresholds"].__setitem__(key, 1.))
        self.refuse(lambda value: value["comparisons"]["T05_same_density"].__setitem__("matrix_max_abs", 1e-6))
        self.refuse(lambda value: value["comparisons"].__setitem__("P12_energy_difference_hartree", True))

    def test_full_ordinary_cache_requires_eight_exact_array_and_file_identities(self):
        for key in execution.FROZEN_ARRAYS:
            self.refuse(lambda value: value["ordinary_origin"]["array_identities"].pop(key))
            self.refuse(lambda value: value["ordinary_origin"]["array_identities"][key].__setitem__("sha256", "ff" * 32))
        self.refuse(lambda value: value["ordinary_origin"]["record"].__setitem__("size_bytes", True))
        self.refuse(lambda value: value["ordinary_origin"]["arrays"].__setitem__("sha256", "ff" * 32))
        self.refuse(lambda value: value["ordinary_origin"]["common_density_identity"].__setitem__("order", "F"))

    def test_source_paths_require_mandatory_files_hashes_and_no_traversal(self):
        for name in execution.REQUIRED_SOURCE_FILES:
            self.refuse(lambda value: value["source_file_sha256"].pop(name))
        for name in ("../outside.py", "a/../b.py", "./x.py", "a//b.py", "/root/x.py", "C:/x.py", "a\\b.py"):
            self.refuse(lambda value: value["source_file_sha256"].__setitem__(name, "ff" * 32))
        self.refuse(lambda value: value["source_file_sha256"].__setitem__("extra.py", "short"))

    def test_three_path_probe_order_names_and_ancestry_are_exact(self):
        self.refuse(lambda value: value["paths"].reverse())
        self.refuse(lambda value: value["probe_origin"]["probes"].reverse())
        self.refuse(lambda value: value["probe_origin"]["probes"].append(copy.deepcopy(value["probe_origin"]["probes"][0])))
        for key in ("source_execution_commit", "source_delivery_commit", "source_manifest_sha256"):
            self.refuse(lambda value: value["probe_origin"].__setitem__(key, "ff" * 20))
        self.refuse(lambda value: value["probe_origin"].__setitem__("source_path", "production_owned"))
        self.refuse(lambda value: value["probe_origin"]["source_fock_identity"].__setitem__("finite", 1))

    def test_probe_shapes_dtype_density_hash_and_no_old_F_energy_seed_claim(self):
        for key, bad in (("F_at_this_new_density", "EXECUTED"), ("energy_at_this_new_density", 0.),
            ("new_matched_operator_id", "ff" * 32), ("new_energy_binding", {}),
            ("executable_seed", True), ("scientific_qualification", "PASS"), ("density_id", "short")):
            self.refuse(lambda value: value["probe_origin"]["probes"][0].__setitem__(key, bad))
        self.refuse(lambda value: value["probe_origin"]["probes"][0]["array_identity"].__setitem__("shape", [14, True]))
        self.refuse(lambda value: value["probe_origin"]["probes"][0]["array_identity"].__setitem__("dtype", "|O"))

    def test_measured_array_checks_cannot_be_replaced_with_truthy_PASS(self):
        for bad in (False, 1, "PASS"):
            self.refuse(lambda value: value["probe_origin"]["probes"][0]["array_checks"]["checks"].__setitem__("rank", bad))
        for key in execution.ARRAY_THRESHOLDS:
            self.refuse(lambda value: value["probe_origin"]["probes"][0]["array_checks"]["thresholds"].__setitem__(key, 1e-3))
        self.refuse(lambda value: value["probe_origin"]["probes"][0]["array_checks"]["observations"].pop("white_trace_abs_error"))

    def test_array_observations_must_be_finite_and_satisfy_original_entry(self):
        observations = "observations"
        for key, bad in (("white_trace_abs_error", 2e-10), ("white_idempotency_absolute_frobenius", 2e-10),
            ("production_density_reconstruction_relative_frobenius", 2e-10),
            ("masked_metric_electrons_abs_error", 2e-7), ("density_symmetry_max_abs", 2e-12),
            ("rank_of_white_projector_numpy", True), ("masked_metric_electrons", 15.),
            ("white_projector_trace", 7.), ("half_inverse_identity_frobenius", float("nan"))):
            self.refuse(lambda value: value["probe_origin"]["probes"][0]["array_checks"][observations].__setitem__(key, bad))
        self.refuse(lambda value: value["probe_origin"]["probes"][0]["array_checks"][observations]["white_eigenvalues"].__setitem__(0, float("inf")))

    def test_strict_load_rejects_duplicate_json_and_nonfinite_extra_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "contract.json"
            target.write_text(json.dumps(self.value), encoding="utf-8")
            self.assertEqual(execution.load_execution_contract(target), self.value)
            target.write_text('{"schema_version":"a","schema_version":"b"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                execution.load_execution_contract(target)
        self.refuse(lambda value: value.__setitem__("extra", float("nan")))

    def test_execution_identity_is_separate_and_contains_all_probe_and_source_ids(self):
        identity = execution.execution_identity(self.value, "bc" * 32)
        self.assertEqual(identity["mode"], execution.EXECUTION_KIND)
        self.assertEqual(identity["batch_id"], self.value["batch_id"])
        self.assertEqual(set(identity["probe_density_ids"]), set(execution.PROBES))
        self.assertEqual(identity["ordinary_record_sha256"], self.value["ordinary_origin"]["record"]["sha256"])
        with self.assertRaises(execution.ExecutionContractError):
            execution.execution_identity(self.value, "short")


class OccupationResponseBindingTests(unittest.TestCase):
    def setUp(self):
        self.review, self.archive = synthetic_review_archive()
        self.review_raw = json.dumps(self.review, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.value = contract_fixture(self.review, review_size_bytes=len(self.review_raw))
        self.review_digest = hashlib.sha256(self.review_raw).hexdigest()
        self.archive_digest = hashlib.sha256(self.archive).hexdigest()
        self.value["probe_origin"]["review"]["sha256"] = self.review_digest
        self.value["probe_origin"]["arrays"]["sha256"] = self.archive_digest

    def synthetic_binding(self, contract=None, review_raw=None, archive=None):
        with patch.object(execution, "REVIEW_SHA256", self.review_digest), patch.object(execution, "ARRAYS_SHA256", self.archive_digest):
            return execution.validate_probe_binding(contract or self.value,
                self.review_raw if review_raw is None else review_raw, self.archive if archive is None else archive)

    def test_actual_sealed_bytes_when_mounted_or_explicit_synthetic_trust_anchor_only(self):
        directory = os.environ.get("AI4ORGCHEM_OCCUPATION_PROBE_INPUT_DIR")
        if directory:
            root = Path(directory)
            raw = (root / "frozen-occupation-review.json").read_bytes()
            archive = (root / "frozen-occupation-witnesses.npz").read_bytes()
            review = json.loads(raw)
            value = contract_fixture(review, review_size_bytes=len(raw))
            before = copy.deepcopy(value)
            result = execution.validate_probe_binding(value, raw, archive)
            self.assertEqual(value, before)
            self.assertEqual([item["density_id"] for item in result["probes"]], [
                "2103b26b9c349a5ab9953e4cc72fdd49fd3e997bf723f73979eaef866c675240",
                "c621616cf4bb9edddc9b94a1c6baf5b17958f27df80e73f04894fd6153c0a208",
                "bde824cc2957779325a8f8c2fb53fb626970c55b757285a1da4a69fdb92b4faf"])
        else:
            result = self.synthetic_binding()
        self.assertEqual(result["status"], "PASS_SAVED_PROBE_BYTES_ONLY")
        self.assertEqual(result["array_members_verified"], 70)
        self.assertEqual(len(result["probes"]), 3)
        self.assertEqual(result["new_true_F_calls"], 0)
        self.assertIs(result["production_activation"], False)

    def test_sealed_byte_hashes_cannot_be_redeclared_to_accept_modified_review_or_archive(self):
        with self.assertRaises(execution.ExecutionContractError):
            self.synthetic_binding(review_raw=self.review_raw + b" ")
        with self.assertRaises(execution.ExecutionContractError):
            self.synthetic_binding(archive=self.archive[:-1] + b"x")
        value = copy.deepcopy(self.value)
        value["probe_origin"]["review"]["sha256"] = "ff" * 32
        with self.assertRaises(execution.ExecutionContractError):
            self.synthetic_binding(contract=value)

    def test_contract_claims_must_match_sealed_witness_body_not_user_declaration(self):
        for mutation in (
            lambda value: value["probe_origin"]["probes"][0].__setitem__("density_id", "ff" * 32),
            lambda value: value["probe_origin"]["probes"][0]["array_identity"].__setitem__("sha256", "ff" * 32),
            lambda value: value["probe_origin"]["probes"][0]["array_checks"]["observations"].__setitem__("white_trace_abs_error", 1e-15)):
            value = copy.deepcopy(self.value)
            mutation(value)
            with self.assertRaises(execution.ExecutionContractError):
                self.synthetic_binding(contract=value)

    def test_npy_header_payload_validation_refuses_pickle_fortran_wrongshape_and_nonfinite(self):
        payload = b"\0" * (14 * 14 * 8)
        self.assertEqual(execution._npy_bytes(npy_fixture(payload)), payload)
        for raw in (b"pickle", npy_fixture(payload, dtype="|O"), npy_fixture(payload, fortran=True),
            npy_fixture(payload, (7, 28)), npy_fixture(payload[:-8]),
            npy_fixture(struct.pack("<d", float("nan")) + payload[8:])):
            with self.assertRaises(execution.ExecutionContractError):
                execution._npy_bytes(raw)

    def test_binding_returns_independent_probe_copy_and_never_authorizes_process(self):
        before = copy.deepcopy(self.value)
        result = self.synthetic_binding()
        result["probes"][0]["array_checks"]["checks"]["rank"] = False
        self.assertEqual(self.value, before)
        self.assertIs(result["scientific_execution_authorized"], False)


if __name__ == "__main__":
    unittest.main()
