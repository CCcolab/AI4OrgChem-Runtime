"""Independent, standard-library contract for a nine-call response diagnostic.

Declaration validation and byte binding are not authorization, seed approval,
or a molecular calculation.  A supervisor must separately require an explicit
authorized receipt, validate actual cached arrays/source bytes and native limits,
and reserve a fresh journal before any callback.  Historical seed contracts and
budgets are neither projected nor reopened here.
"""
import ast
import copy
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import struct
import zipfile

from . import residual_execution_contract as retained
from .input import strict_json


SCHEMA = "occupation-single-f-response-execution-v1"
EXECUTION_KIND = "PREPARED_SINGLE_F_RESPONSE_DIAGNOSTIC"
AUTHORIZATION_MESSAGE = "请继续"
ExecutionContractError = retained.ExecutionContractError
SCIENCE, BASELINE = retained.SCIENCE, retained.BASELINE
IMAGE, IMAGE_BUILD = retained.IMAGE, retained.IMAGE_BUILD
DEPENDENCIES = copy.deepcopy(retained.DEPENDENCIES)
NUMERICAL_COMPARISONS = copy.deepcopy(retained.NUMERICAL_COMPARISONS)
canonical_sha = retained.canonical_sha
SOURCE_EXECUTION = "60d76deeb468fdd2dc2c444b7cf60d95a9dd9290"
SOURCE_DELIVERY = "afdde3dab6a31feb500dcc8f3b910ed429c6eeba"
REVIEW_SHA256 = "def1c3618a437fe192888906297379483377906ebb06289565540fb149ca537a"
ARRAYS_SHA256 = "be26e3e60fea689798cf9c2b590888bc36ace453c69149367596950384ea1d0c"
OLD_SOURCE_MANIFEST = "548e3ba94177eaa6e894623519b6c3abe9fa860686049242221bbf0174ebd797"
PATHS = ("production_copy", "production_owned", "independent_reference")
PROBES = ("AO_ANCHOR_A", "AO_ANCHOR_B", "AO_ANCHOR_SYMMETRIC_SUM")
WITNESSES = ("anchor_A_AO4", "anchor_B_AO9", "anchor_symmetric_AplusB")
PROCESS_CONTRACT = {
    "scientific_processes": 1, "wall_seconds_through_cleanup": 120,
    "hard_memory_bytes": 1073741824, "maximum_cpus": 1, "swap_bytes": 0,
    "density_probes": 3, "paths_per_probe": 3,
    "total_true_F_or_NR_calls_maximum": 9, "SCF_iterations": 0,
    "new_ordinary_SCF_grid_full_integrals": 0, "final_tail_calls": 0,
    "automatic_retry": False, "refund_failed_slots": False,
    "budget_expansion_or_refill": False, "non_root": True, "offline": True,
    "read_only_source_root_and_cache": True}
FINAL_THRESHOLDS = {
    "commutator_frobenius": 1e-5, "electron_count_abs": 1e-7,
    "idempotency_relative": 1e-7, "energy_closure_hartree": 1e-9,
    "mask_max_abs": 1e-12, "mapped_density_relative": 2e-8,
    "mapped_density_absolute_frobenius": 2e-8,
    "final_non_diis_gap_minimum_hartree": 1e-6,
    "returned_density_energy_recheck_hartree": 1e-9,
    "mapped_density_energy_recheck_hartree": 1e-9}
ARRAY_THRESHOLDS = {
    "masked_electrons_abs": 1e-7, "DSD_2D_relative": 1e-7,
    "white_trace_abs": 1e-10, "white_idempotency_abs_frobenius": 1e-10,
    "production_reconstruction_relative": 1e-10}
REQUIRED_SOURCE_FILES = frozenset((
    "runtime/user_molecule/occupation_response.py",
    "runtime/user_molecule/occupation_response_contract.py",
    "scripts/diagnose-user-molecule-occupation-response-worker.py",
    "runtime/user_molecule/residual_seed_preparation.py",
    "runtime/user_molecule/residual_preparation.py",
    "runtime/user_molecule/residual_bridge.py",
    "runtime/user_molecule/residual_budget.py",
    "runtime/user_molecule/acceptance_resources.py",
    "runtime/user_molecule/solver_candidate.py",
    "reference/residual_molecule.py", "reference/user_molecule.py"))
FROZEN_ARRAYS = {
    "density": ([14, 14], "9dc813178f17be82f7c231c7b9d0a0494e8d4bcd2acea05ac2605bf3bf268f8a"),
    "hcore": ([14, 14], "b626383143be0295b58aee4d7f553398f0df0cb54af8541e0795056525faaa1a"),
    "overlap": ([14, 14], "957372152a6fab1b90f084598f010f73aa8c09ce5ec3a1c383c6195a23732d78"),
    "eri": ([14, 14, 14, 14], "793d3d8ad2a02c43186c6e038229a4219507058486c1d433dae3a0bb97301ca6"),
    "grid_coords": ([43904, 3], "ec697731d0429ecf2bd11defd2fd75414286ba950e8b0afc6aea012890e9aad7"),
    "grid_weights": ([43904], "2b97965e448ea3d57aabfff3b51c2d2f1aa2c27c026444bc21bb608ef6452d68"),
    "mo_coefficients": ([14, 14], "c4ebf474d3dc13e14bd08bbaaff09797805da345877b220b6dc9a5ecea0ba42e"),
    "mo_occupations": ([14], "425b2c4fbffb758896a2c8bb66fe2387cf784b2911147d2d48a195ee29a5bb9e")}
SOURCE_F = {"shape": [14, 14], "dtype": "<f8", "finite": True,
    "sha256": "0ab3fdaaddc622384ab24716f1427b77a921a9e7f28f003afe88c0d5b2f54ec3"}
SOURCE_S = {"shape": [14, 14], "dtype": "<f8", "finite": True,
    "sha256": "b8b3f020e5ee76c663283aa3dc105d4e0b1e37edad07787515f5712fe85f68dd"}
FIXTURE = {"id": "ethene-planar-technical-v1",
    "request_path": "examples/user-molecule/w05-candidates/ethene-planar-technical-v1/request-pilot.json",
    "normalized_request_sha256": "46a9f72bcf346e3be353d98291d8873a957675329f907ffd8271ca72df61bbab",
    "xyz_sha256": "69f55725834dfa8419dfc6019ae56dd564f9a0ae18ec28e706245b785bfac80d",
    "profile_id": "pilot-b3lypg-sto3g-grid2-v1", "coordinate_unit": "angstrom",
    "orientation": "fixed xy; no reorientation/reordering",
    "mapping_coordinate_conversion_guard_angstrom": 1e-12, "nao": 14,
    "electron_count": 16, "rotation_variables": 48}


def _fail(message):
    raise ExecutionContractError("Occupation response contract: " + message)


def _equal(actual, expected, name):
    """JSON equality with strict boolean/integer distinction, recursive."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            _fail(name + " fields differ")
        for key, value in expected.items():
            _equal(actual[key], value, name + "." + key)
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            _fail(name + " dimensions/items differ")
        for index, value in enumerate(expected):
            _equal(actual[index], value, name + "." + str(index))
    elif type(expected) in (int, bool):
        if type(actual) is not type(expected) or actual != expected:
            _fail(name + " value/type differs")
    elif isinstance(expected, float):
        if type(actual) not in (int, float) or not math.isfinite(actual) or actual != expected:
            _fail(name + " finite frozen number differs")
    elif type(actual) is not type(expected) or actual != expected:
        _fail(name + " value/type differs")


def _finite(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        _fail(name + " must be finite nonboolean numeric data")
    return value


def _file_metadata(value, name, expected_sha, expected_size=None):
    if not isinstance(value, dict) or set(value) != {"size_bytes", "sha256"}:
        _fail(name + " requires exact size and SHA-256 fields")
    retained._sha(value["sha256"], name)
    if value["sha256"] != expected_sha or type(value["size_bytes"]) is not int or value["size_bytes"] <= 0:
        _fail(name + " frozen identity differs")
    if expected_size is not None and value["size_bytes"] != expected_size:
        _fail(name + " frozen size differs")


def _array_identity(value, name, shape, digest=None):
    if not isinstance(value, dict) or set(value) != {"shape", "dtype", "order", "sha256"}:
        _fail(name + " requires four canonical array fields")
    _equal(value["shape"], shape, name + ".shape")
    if value["dtype"] != "<f8" or value["order"] != "C":
        _fail(name + " requires little-endian binary64 C order")
    retained._sha(value["sha256"], name + ".sha256")
    if digest is not None and value["sha256"] != digest:
        _fail(name + " frozen array bytes differ")


def _array_checks(value):
    if value["status"] != "PASS_NUMERICAL_ARRAY_IDENTITIES_ONLY":
        _fail("witness pure-array checks did not pass")
    _equal(value["thresholds"], ARRAY_THRESHOLDS, "array thresholds")
    _equal(value["checks"], {name: True for name in (
        "rank", "masked_electrons", "DSD_2D_relative", "white_trace",
        "white_idempotency", "production_reconstruction", "density_symmetry")}, "array check flags")
    observations = value["observations"]
    required = {"rank_of_white_projector_numpy", "white_eigenvalues", "masked_metric_electrons",
        "masked_metric_electrons_abs_error", "closed_shell_DSD_minus_2D_frobenius",
        "closed_shell_DSD_minus_2D_relative", "white_projector_trace", "white_trace_abs_error",
        "white_idempotency_absolute_frobenius", "production_density_reconstruction_relative_frobenius",
        "density_symmetry_max_abs", "half_inverse_identity_frobenius"}
    if not isinstance(observations, dict) or set(observations) != required:
        _fail("all measured witness array observations are required")
    _equal(observations["rank_of_white_projector_numpy"], 8, "occupied rank")
    eigenvalues = observations["white_eigenvalues"]
    if not isinstance(eigenvalues, list) or len(eigenvalues) != 14:
        _fail("fourteen measured white eigenvalues required")
    for number in eigenvalues:
        _finite(number, "white eigenvalue")
    for key in required - {"white_eigenvalues", "rank_of_white_projector_numpy"}:
        _finite(observations[key], key)
    for key, threshold in (("masked_metric_electrons_abs_error", 1e-7),
        ("closed_shell_DSD_minus_2D_relative", 1e-7), ("white_trace_abs_error", 1e-10),
        ("white_idempotency_absolute_frobenius", 1e-10),
        ("production_density_reconstruction_relative_frobenius", 1e-10),
        ("density_symmetry_max_abs", 1e-12)):
        if not 0 <= observations[key] <= threshold:
            _fail(key + " fails unchanged array admission")
    if abs(observations["masked_metric_electrons"] - 16) > 1e-7 or abs(observations["white_projector_trace"] - 8) > 1e-10:
        _fail("measured masked count/white trace do not match closed-shell occupation")
    if any(number < -1e-10 or number > 1 + 1e-10 for number in eigenvalues):
        _fail("measured white projector spectrum is not admissible")
    for name, expected in (("actual_solver_admission", "NOT_EXECUTED"),
        ("executable_seed", False), ("initialization_policy_is_changed", False)):
        _equal(value[name], expected, name)


def validate_execution_contract(value):
    """Validate declarations only; False authorization templates remain inert."""
    try:
        if not isinstance(value, dict) or value["schema_version"] != SCHEMA or value["execution_kind"] != EXECUTION_KIND:
            _fail("unknown independent response schema or execution kind")
        if type(value["scientific_execution_authorized"]) is not bool:
            _fail("authorization must be an explicit boolean declaration")
        _equal(value["authorization_basis"], {"source": "DIRECT_USER_MESSAGE", "message": AUTHORIZATION_MESSAGE}, "authorization basis")
        for key in ("production_activation", "scientific_approval", "method_approval", "external_review_required"):
            _equal(value[key], False, key)
        _equal(value["external_review_status"], "CANCELLED_BY_USER", "external review status")
        if not isinstance(value["batch_id"], str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value["batch_id"]) is None:
            _fail("bounded fresh batch identity required")
        if value["batch_id"] in ("20261007-seed-v2-a1", "residual-live-20261006-a1"):
            _fail("historical batch may not be reopened")
        retained._sha(value["runtime_test_commit"], "runtime_test_commit", 40)
        for key, expected in (("science_commit", SCIENCE), ("science_baseline_commit", BASELINE),
                             ("image_id", IMAGE), ("image_build_runtime_commit", IMAGE_BUILD)):
            _equal(value[key], expected, key)
        for key in ("source_manifest_sha256", "profile_sha256", "prior_proposal_sha256", "dependencies_sha256"):
            retained._sha(value[key], key)
        _equal(value["expected_dependencies"], DEPENDENCIES, "dependencies")
        _equal(value["dependencies_sha256"], canonical_sha(DEPENDENCIES), "dependencies SHA")
        _equal(value["process_contract"], PROCESS_CONTRACT, "process contract")
        _equal(value["fixture"], FIXTURE, "fixed fixture")
        _equal(value["final_thresholds"], FINAL_THRESHOLDS, "original final thresholds")
        for key, expected in NUMERICAL_COMPARISONS.items():
            _equal(value["comparisons"][key], expected, "comparison." + key)
        _equal(value["paths"], list(PATHS), "three serial paths")
        origin = value["ordinary_origin"]
        for key, expected in (("kind", "REUSE_PRIOR_FULL_INDEPENDENT_ORDINARY_REFERENCE"),
            ("record_file", "ordinary-reference.json"), ("arrays_file", "ordinary-reference.npz")):
            _equal(origin[key], expected, "ordinary_origin." + key)
        _file_metadata(origin["record"], "ordinary record", "b0a9fd8a2487d725668823b75966176e98eb25551f40b9f177b485141ecb9663", 11741)
        _file_metadata(origin["arrays"], "ordinary arrays", "2a0318c42ee47001e2774ea6b4fec8317b1887c744a2720e71033a75b18f6051", 1728678)
        arrays = origin["array_identities"]
        if not isinstance(arrays, dict) or set(arrays) != set(FROZEN_ARRAYS):
            _fail("full old ordinary cache requires all eight array identities")
        for key, (shape, digest) in FROZEN_ARRAYS.items():
            _array_identity(arrays[key], "ordinary." + key, shape, digest)
        _equal(origin["common_density_identity"], arrays["density"], "old common density")
        _equal(origin["nuclear_repulsion_hartree"], 33.23272494899829, "cached nuclear repulsion")
        sources = value["source_file_sha256"]
        if not isinstance(sources, dict) or not REQUIRED_SOURCE_FILES <= set(sources):
            _fail("all diagnostic and retained implementation source identities are required")
        for path, digest in sources.items():
            if (not isinstance(path, str) or not path or "\\" in path or ":" in path
                    or PurePosixPath(path).is_absolute() or any(part in {"", ".", ".."} for part in path.split("/"))):
                _fail("source files require canonical relative POSIX paths")
            retained._sha(digest, "source file " + path)
        probe_origin = value["probe_origin"]
        _equal(probe_origin["review_file"], "frozen-occupation-review.json", "review file")
        _equal(probe_origin["arrays_file"], "frozen-occupation-witnesses.npz", "probe archive file")
        _file_metadata(probe_origin["review"], "sealed review", REVIEW_SHA256)
        _file_metadata(probe_origin["arrays"], "sealed probe archive", ARRAYS_SHA256, 49568)
        for key, expected in (("source_execution_commit", SOURCE_EXECUTION),
            ("source_delivery_commit", SOURCE_DELIVERY), ("source_manifest_sha256", OLD_SOURCE_MANIFEST),
            ("source_path", "production_copy"), ("source_fock_identity", SOURCE_F),
            ("source_masked_overlap_identity", SOURCE_S)):
            _equal(probe_origin[key], expected, "probe_origin." + key)
        probes = probe_origin["probes"]
        if not isinstance(probes, list) or len(probes) != 3:
            _fail("three exact probe bindings required")
        for probe, name, witness in zip(probes, PROBES, WITNESSES):
            _equal(probe["name"], name, "probe name")
            _equal(probe["witness_name"], witness, "witness name")
            _equal(probe["member"], "production_copy__witness__" + witness + "__density_NO_F_NO_ENERGY", "density archive member")
            retained._sha(probe["density_id"], "probe density identity")
            _array_identity(probe["array_identity"], "probe array", [14, 14])
            _array_checks(probe["array_checks"])
            for key, expected in (("F_at_this_new_density", "NOT_EXECUTED"), ("energy_at_this_new_density", None),
                ("new_matched_operator_id", None), ("new_energy_binding", None),
                ("executable_seed", False), ("scientific_qualification", "NOT_GRANTED")):
                _equal(probe[key], expected, "probe." + key)
        json.dumps(value, allow_nan=False)
        return value
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        if isinstance(error, ExecutionContractError):
            raise
        raise ExecutionContractError("Incomplete or invalid occupation response contract: " + str(error)) from error


def load_execution_contract(path):
    return validate_execution_contract(strict_json(Path(path).read_bytes()))


def execution_identity(contract, contract_sha256):
    """Identity declaration for a separate journal, not budget admission."""
    validate_execution_contract(contract)
    retained._sha(contract_sha256, "execution_contract_sha256")
    return {"mode": EXECUTION_KIND, "execution_kind": EXECUTION_KIND,
        "batch_id": contract["batch_id"], "execution_contract_sha256": contract_sha256,
        **{key: contract[key] for key in ("runtime_test_commit", "science_commit",
            "science_baseline_commit", "image_id", "image_build_runtime_commit", "source_manifest_sha256",
            "profile_sha256", "dependencies_sha256")},
        "geometry_sha256": contract["fixture"]["xyz_sha256"],
        "ordinary_record_sha256": contract["ordinary_origin"]["record"]["sha256"],
        "ordinary_arrays_sha256": contract["ordinary_origin"]["arrays"]["sha256"],
        "probe_review_sha256": contract["probe_origin"]["review"]["sha256"],
        "probe_arrays_sha256": contract["probe_origin"]["arrays"]["sha256"],
        "probe_density_ids": {item["name"]: item["density_id"] for item in contract["probe_origin"]["probes"]}}


def _npy_bytes(raw, expected_shape=(14, 14)):
    """Parse the safe fixed binary64 matrix header without NumPy or pickle."""
    if raw[:6] != b"\x93NUMPY" or len(raw) < 10:
        _fail("NPY magic/header missing")
    version = tuple(raw[6:8])
    if version == (1, 0):
        start, header_size = 10, struct.unpack("<H", raw[8:10])[0]
    elif version in ((2, 0), (3, 0)) and len(raw) >= 12:
        start, header_size = 12, struct.unpack("<I", raw[8:12])[0]
    else:
        _fail("unsupported NPY header version")
    if not 0 < header_size <= 4096 or start + header_size > len(raw):
        _fail("truncated or oversized NPY header")
    header = ast.literal_eval(raw[start:start + header_size].decode("utf-8" if version == (3, 0) else "latin1").strip())
    if not isinstance(header, dict) or set(header) != {"descr", "fortran_order", "shape"}:
        _fail("NPY matrix header fields differ")
    if (header["descr"] != "<f8" or header["fortran_order"] is not False
            or type(header["shape"]) is not tuple or header["shape"] != expected_shape
            or any(type(x) is not int or x <= 0 for x in header["shape"])):
        _fail("NPY requires exact little-endian C-order binary64 shape")
    payload = raw[start + header_size:]
    if len(payload) != math.prod(expected_shape) * 8:
        _fail("NPY payload size differs")
    # Finiteness alone is a byte-level check; PSD and metric algebra belong to
    # the actual NumPy preparation path and never follow from this header.
    if any(not math.isfinite(number[0]) for number in struct.iter_unpack("<d", payload)):
        _fail("probe payload contains nonfinite values")
    return payload


def validate_probe_binding(contract, review_bytes, npz_bytes):
    """Bind exact sealed review/body and selected NPZ bytes, no array algebra."""
    validate_execution_contract(contract)
    try:
        origin = contract["probe_origin"]
        for name, raw in (("review", review_bytes), ("arrays", npz_bytes)):
            if type(raw) is not bytes or len(raw) != origin[name]["size_bytes"] or hashlib.sha256(raw).hexdigest() != origin[name]["sha256"]:
                _fail("actual sealed " + name + " bytes differ")
        review = strict_json(review_bytes)
        for key, expected in (("schema_version", "frozen-occupation-scope-review-v1"),
            ("status", "READONLY_SAVED_MATRIX_SCOPE_ANALYSIS_COMPLETE"),
            ("source_execution_commit", SOURCE_EXECUTION), ("source_delivery_commit", SOURCE_DELIVERY),
            ("source_image_id", IMAGE), ("prior_manifest_sha256", OLD_SOURCE_MANIFEST),
            ("new_true_molecular_F_calls", 0), ("new_SCF_calls", 0), ("new_NR_grid_integral_calls", 0),
            ("new_scientific_processes", 0), ("scientific_budget", None),
            ("old_budget_reopened", False), ("scientific_thresholds_changed", False), ("Compute", False)):
            _equal(review[key], expected, "sealed review." + key)
        paths = [item for item in review["paths"] if item["path"] == "production_copy"]
        if len(paths) != 1:
            _fail("unique production_copy witness ancestry required")
        path = paths[0]
        _equal(path["original_fock_identity"], SOURCE_F, "review original F")
        _equal(path["original_masked_overlap_identity"], SOURCE_S, "review original masked S")
        _equal(path["original_true_snapshot_density_binding_verified"], True, "review original snapshot binding")
        archive_meta = review["array_archive"]
        _equal(archive_meta["sha256"], origin["arrays"]["sha256"], "review archive SHA")
        _equal(archive_meta["size_bytes"], origin["arrays"]["size_bytes"], "review archive size")
        with zipfile.ZipFile(io.BytesIO(npz_bytes)) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or len(names) != archive_meta["member_count"]:
                _fail("NPZ duplicate members or count mismatch")
            expected_names = {name + ".npy" for name in archive_meta["members"]}
            if set(names) != expected_names or any("/" in name or "\\" in name for name in names):
                _fail("NPZ exact sealed member set differs")
            payloads = {}
            for member, metadata in archive_meta["members"].items():
                shape = metadata["shape"]
                if (not isinstance(shape, list) or not 1 <= len(shape) <= 2
                        or any(type(item) is not int or not 1 <= item <= 14 for item in shape)
                        or metadata["dtype"] != "<f8" or metadata["finite"] is not True):
                    _fail("invalid sealed archive member metadata")
                retained._sha(metadata["sha256"], "sealed archive member SHA")
                info = archive.getinfo(member + ".npy")
                if info.file_size > math.prod(shape) * 8 + 4108:
                    _fail("archive member exceeds fixed header/payload bound")
                payload = _npy_bytes(archive.read(info), tuple(shape))
                if hashlib.sha256(payload).hexdigest() != metadata["sha256"]:
                    _fail("actual archive member payload SHA differs")
                payloads[member] = payload
            for probe in origin["probes"]:
                matches = [item for item in path["occupation_witnesses"] if item["name"] == probe["witness_name"]]
                if len(matches) != 1:
                    _fail("unique sealed witness required")
                witness = matches[0]
                _equal(witness["density_id"], probe["density_id"], "sealed density id")
                _equal(witness["numerical_array_checks"], probe["array_checks"], "sealed measured array checks")
                _equal(witness["array_members"]["density_NO_F_NO_ENERGY"], probe["member"], "sealed density member")
                for key in ("F_at_this_new_density", "energy_at_this_new_density", "new_matched_operator_id", "new_energy_binding", "scientific_qualification"):
                    _equal(witness[key], probe[key], "sealed witness." + key)
                metadata = archive_meta["members"][probe["member"]]
                expected_meta = {key: probe["array_identity"][key] for key in ("shape", "dtype", "sha256")}
                expected_meta["finite"] = True
                _equal(metadata, expected_meta, "sealed member identity")
                payload = payloads[probe["member"]]
                if hashlib.sha256(payload).hexdigest() != probe["array_identity"]["sha256"]:
                    _fail("actual probe array payload SHA differs")
                identity = hashlib.sha256(b"AI4OrgChem-density-v1\0" + struct.pack("<QQ", 14, 14) + payload).hexdigest()
                if identity != probe["density_id"]:
                    _fail("actual shape-prefixed density identity differs")
        return {"status": "PASS_SAVED_PROBE_BYTES_ONLY", "array_members_verified": len(names),
                "probes": copy.deepcopy(origin["probes"]), "new_true_F_calls": 0,
                "scientific_execution_authorized": contract["scientific_execution_authorized"],
                "production_activation": False}
    except (KeyError, TypeError, ValueError, OverflowError, zipfile.BadZipFile, UnicodeError, SyntaxError, struct.error) as error:
        if isinstance(error, ExecutionContractError):
            raise
        raise ExecutionContractError("Invalid sealed probe binding: " + str(error)) from error


def minimal_template(ordinary_origin, review, *, review_size_bytes):
    """Return an inert declaration template populated from retained metadata.

    Runtime/source/profile/proposal hashes are placeholders for the supervisor
    to fill; this function reads no files and never authorizes/reserves work.
    Review input still requires validate_probe_binding against its sealed bytes.
    """
    path = next(item for item in review["paths"] if item["path"] == "production_copy")
    probes = []
    for name, witness_name in zip(PROBES, WITNESSES):
        witness = next(item for item in path["occupation_witnesses"] if item["name"] == witness_name)
        member = witness["array_members"]["density_NO_F_NO_ENERGY"]
        metadata = review["array_archive"]["members"][member]
        probes.append({"name": name, "witness_name": witness_name, "member": member,
            "density_id": witness["density_id"], "array_identity": {
                "shape": metadata["shape"], "dtype": metadata["dtype"], "order": "C", "sha256": metadata["sha256"]},
            "array_checks": copy.deepcopy(witness["numerical_array_checks"]),
            "F_at_this_new_density": "NOT_EXECUTED", "energy_at_this_new_density": None,
            "new_matched_operator_id": None, "new_energy_binding": None,
            "executable_seed": False, "scientific_qualification": "NOT_GRANTED"})
    return {"schema_version": SCHEMA, "execution_kind": EXECUTION_KIND,
        "batch_id": "response-diagnostic-template-not-reserved",
        "scientific_execution_authorized": False,
        "authorization_basis": {"source": "DIRECT_USER_MESSAGE", "message": AUTHORIZATION_MESSAGE},
        "production_activation": False, "scientific_approval": False, "method_approval": False,
        "external_review_required": False, "external_review_status": "CANCELLED_BY_USER",
        "runtime_test_commit": "0" * 40, "science_commit": SCIENCE, "science_baseline_commit": BASELINE,
        "image_id": IMAGE, "image_build_runtime_commit": IMAGE_BUILD,
        "expected_dependencies": copy.deepcopy(DEPENDENCIES), "dependencies_sha256": canonical_sha(DEPENDENCIES),
        "source_manifest_sha256": "0" * 64, "profile_sha256": "0" * 64, "prior_proposal_sha256": "0" * 64,
        "source_file_sha256": {name: "0" * 64 for name in sorted(REQUIRED_SOURCE_FILES)},
        "process_contract": copy.deepcopy(PROCESS_CONTRACT), "fixture": copy.deepcopy(FIXTURE),
        "final_thresholds": copy.deepcopy(FINAL_THRESHOLDS), "comparisons": copy.deepcopy(NUMERICAL_COMPARISONS),
        "ordinary_origin": copy.deepcopy(ordinary_origin), "paths": list(PATHS),
        "probe_origin": {"review_file": "frozen-occupation-review.json",
            "review": {"size_bytes": review_size_bytes, "sha256": REVIEW_SHA256},
            "arrays_file": "frozen-occupation-witnesses.npz",
            "arrays": {"size_bytes": 49568, "sha256": ARRAYS_SHA256},
            "source_execution_commit": SOURCE_EXECUTION, "source_delivery_commit": SOURCE_DELIVERY,
            "source_manifest_sha256": OLD_SOURCE_MANIFEST, "source_path": "production_copy",
            "source_fock_identity": copy.deepcopy(SOURCE_F),
            "source_masked_overlap_identity": copy.deepcopy(SOURCE_S), "probes": probes}}
