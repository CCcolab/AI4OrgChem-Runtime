"""Exact seed-v2 diagnostic identity and admission contract, standard library.

The actual initialization is MASKED_METRIC_OCCUPIED_SUBSPACE_SEED_V2. A private
validation projection reuses the old fixture/resource/comparison checks only;
it is never an execution record or approval under the old FIRST_RAW policy.
New seed/readiness file hashes are declarations here. The supervisor must
verify their actual bytes, source files, cancellation record and readiness
body before reserving or launching the one bounded scientific process.
"""
import copy
import hashlib
import json
import math
from pathlib import Path, PurePosixPath

from . import residual_execution_contract as retained
from .input import strict_json


SCHEMA = "residual-seed-v2-live-execution-contract-v1"
POLICY = "MASKED_METRIC_OCCUPIED_SUBSPACE_SEED_V2"
AUTHORIZATION_MESSAGE = "请继续，可以进入新计算吗"
ExecutionContractError = retained.ExecutionContractError
SCIENCE, BASELINE = retained.SCIENCE, retained.BASELINE
IMAGE, IMAGE_BUILD = retained.IMAGE, retained.IMAGE_BUILD
DEPENDENCIES = retained.DEPENDENCIES
NUMERICAL_COMPARISONS = retained.NUMERICAL_COMPARISONS
PATHS = retained.PATHS
canonical_sha = retained.canonical_sha
REQUIRED_SEED_SOURCE_FILES = frozenset((
    "runtime/user_molecule/seed_v2.py", "reference/seed_v2.py",
    "runtime/user_molecule/residual_seed_v2.py", "reference/residual_seed_v2.py"))
FROZEN_MO_COEFFICIENTS_SHA256 = "c4ebf474d3dc13e14bd08bbaaff09797805da345877b220b6dc9a5ecea0ba42e"
FROZEN_MO_OCCUPATIONS_SHA256 = "425b2c4fbffb758896a2c8bb66fe2387cf784b2911147d2d48a195ee29a5bb9e"


def validate_seed_readiness(receipt):
    """Recheck the measured zero-functional preparation receipt, stdlib only.

    PASS flags do not substitute for finite measurements and unchanged
    thresholds.  The caller must separately verify this receipt's exact bytes,
    the declared source files, input cache and actually used seed arrays.
    This check does not qualify an endpoint or authorize a scientific process.
    """
    def fail(message):
        raise ExecutionContractError("Seed readiness: " + message)

    def finite_number(value, name):
        if type(value) not in (int, float) or not math.isfinite(value):
            fail(name + " must be finite nonboolean numeric data")
        return value

    def zero(value, name):
        if type(value) is not int or value != 0:
            fail(name + " must be the integer zero, not a truthy/falsy surrogate")

    def rows(value, name, mandatory=None):
        if not isinstance(value, dict) or not value:
            fail(name + " requires nonempty measured checks")
        mandatory = mandatory or {}
        if not set(mandatory) <= set(value):
            fail(name + " is missing required admission measurements")
        for key, row in value.items():
            if not isinstance(key, str) or not isinstance(row, dict):
                fail(name + " contains an invalid check row")
            flags = [row[field] for field in ("passed", "pass") if field in row]
            if not flags or any(flag is not True for flag in flags):
                fail(name + "." + key + " must explicitly pass with a boolean flag")
            values = [row[field] for field in ("value", "observed") if field in row]
            if not values:
                fail(name + "." + key + " is missing its measured value")
            for measured in values:
                finite_number(measured, name + "." + key)
            if any(measured != values[0] for measured in values[1:]):
                fail(name + "." + key + " has conflicting measured values")
            actual = values[0]
            if "threshold" not in row:
                if not key.endswith("_positive_definite") or actual <= 0:
                    fail(name + "." + key + " must measure a strictly positive minimum eigenvalue")
                if key in mandatory:
                    fail(name + "." + key + " is missing its frozen threshold")
                continue
            threshold = finite_number(row["threshold"], name + "." + key + ".threshold")
            comparison = row.get("comparison", "<=")
            if comparison not in ("<=", ">"):
                fail(name + "." + key + " has an unsupported comparison")
            if threshold < 0 or (comparison == "<=" and actual < 0):
                fail(name + "." + key + " must use nonnegative residuals and thresholds")
            if not (actual <= threshold if comparison == "<=" else actual > threshold):
                fail(name + "." + key + " measurement fails its declared inequality")
            if key in mandatory and (threshold != mandatory[key] or comparison != "<="):
                fail(name + "." + key + " differs from the frozen admission threshold")
            if key.endswith("_condition_number") and (threshold != 1e6 or comparison != "<=" or actual < 1):
                fail(name + "." + key + " differs from the seed condition-number contract")
            if key.endswith("_minimum_eigenvalue") and (threshold != 0 or comparison != ">"):
                fail(name + "." + key + " must retain strict positive definiteness")

    try:
        if not isinstance(receipt, dict) or receipt["schema_version"] != "seed-v2-cached-readiness-v1":
            fail("unknown receipt schema")
        if receipt["status"] != "PASS_SEED_V2_CACHED_PREPARATION_ONLY" or receipt["policy"] != POLICY:
            fail("the actual V2 cached preparation did not pass")
        zero(receipt["new_functional_calls"], "new_functional_calls")
        forbidden = receipt["forbidden_operation_counts"]
        if not isinstance(forbidden, dict) or set(forbidden) != {"SCF", "GRID", "INTEGRAL", "NR_RKS"}:
            fail("all guarded operation counters are required")
        for key, value in forbidden.items():
            zero(value, "forbidden_operation_counts." + key)
        if receipt["three_used_seeds_byte_identical"] is not True:
            fail("three path seeds must be byte-identical")
        difference = finite_number(receipt["reference_constructed_to_common_seed_relative_frobenius"], "reference seed difference")
        threshold = finite_number(receipt["reference_difference_threshold"], "reference seed difference threshold")
        if threshold != 1e-10 or not 0 <= difference <= threshold:
            fail("independent seed agreement must satisfy the unchanged 1e-10 relative gate")
        if receipt["reference_difference_denominator"] != "max(||commonseed||F,1)":
            fail("independent seed agreement uses the wrong denominator")
        retained._sha(receipt["runtime_test_commit"], "seed readiness runtime commit", 40)
        sources = receipt["source_file_sha256"]
        if not isinstance(sources, dict) or not REQUIRED_SEED_SOURCE_FILES <= set(sources):
            fail("both seed and adapter source-file identities are required")
        for path, digest in sources.items():
            if (not isinstance(path, str) or not path or "\\" in path
                    or PurePosixPath(path).is_absolute() or ":" in path
                    or any(part in {"", ".", ".."} for part in path.split("/"))):
                fail("source-file paths must be canonical relative POSIX paths")
            retained._sha(digest, "seed readiness source file " + path)
        if receipt["scientific_execution"] != "NOT_EXECUTED" or receipt["production_activation"] is not False:
            fail("preparation cannot claim scientific execution or production activation")
        if (receipt["final_endpoint_gates"] != "UNCHANGED_NOT_EXECUTED"
                or receipt["research_acceptance"] != "NOT_ACCEPTED" or receipt["deltas"] is not None):
            fail("preparation cannot grant endpoint, research or comparison qualification")
        if finite_number(receipt["final_gap_minimum_hartree"], "final gap threshold") != 1e-6:
            fail("the original final positive-gap threshold must remain unchanged")
        if receipt["initial_gap_qualification"] != "NOT_APPLICABLE_TO_SEED; FIRST_F_GAP_DIAGNOSTIC_ONLY":
            fail("the seed does not qualify an initial F gap")
        for name in ("scientific_approval", "method_approval", "input_arrays_mutated", "repairs_performed"):
            if name in receipt and receipt[name] is not False:
                fail(name + " must be boolean false when declared")
        paths = receipt["receipts"]
        if not isinstance(paths, dict) or set(paths) != {"production_copy", "production_owned", "independent_reference"}:
            fail("all three actual seed receipts are required")
        production_required = {"whitened_trace": 1e-10, "whitened_idempotency": 1e-10,
                               "production_density_reconstruction": 1e-10}
        reference_required = {"white_projector_trace": 1e-10, "white_projector_idempotency": 1e-10}
        for name, path_receipt in paths.items():
            if not isinstance(path_receipt, dict) or path_receipt["policy_id"] != POLICY:
                fail(name + " requires an actual matching V2 receipt")
            zero(path_receipt["functional_calls"], name + ".functional_calls")
            if path_receipt["scientific_approval"] is not False:
                fail(name + " cannot claim scientific approval")
            rows(path_receipt["definition_checks"], name + ".definition_checks")
            shared = path_receipt["shared_seed_admission"]
            if name == "independent_reference":
                if path_receipt["status"] != "PASS_ARRAY_SEED_AND_REFERENCE_ENTRY_ONLY" or path_receipt["input_arrays_mutated"] is not False:
                    fail("independent reference must pass without mutating parent arrays")
                rows(path_receipt["solver_entry_checks"], name + ".solver_entry_checks", reference_required)
                if not isinstance(shared, dict) or shared["status"] != "PASS_ARRAY_REFERENCE_ENTRY_ONLY":
                    fail("the reference must admit the actually shared seed")
                zero(shared["functional_calls"], name + ".shared.functional_calls")
                rows(shared["checks"], name + ".shared.checks",
                     {**reference_required, "independent_seed_agreement": 1e-10})
            else:
                if (path_receipt["status"] != "ADMITTED_SEED_ONLY"
                        or path_receipt["definition_status"] != "PASS_SEED_DEFINITION"
                        or path_receipt["solver_admission_status"] != "PASS_PRODUCTION_SEED_ADMISSION"
                        or path_receipt["production_activation"] is not False
                        or path_receipt["repairs_performed"] is not False):
                    fail(name + " must be preparation-only with no repairs")
                rows(path_receipt["solver_admission_checks"], name + ".solver_admission_checks", production_required)
                if not isinstance(shared, dict):
                    fail(name + " shared-seed admission must be explicit")
                if shared["status"] == "NOT_APPLICABLE_LOCAL_SEED_USED":
                    continue
                if shared["status"] != "PASS_SHARED_SEED_PRODUCTION_ADMISSION":
                    fail(name + " shared seed did not pass its production entry checks")
                zero(shared["functional_calls"], name + ".shared.functional_calls")
                if shared["repairs_performed"] is not False:
                    fail(name + " cannot repair the shared seed")
                rows(shared["checks"], name + ".shared.checks",
                     {**production_required, "local_seed_agreement": 1e-10})
        json.dumps(receipt, allow_nan=False)
        return receipt
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        if isinstance(error, ExecutionContractError):
            raise
        raise ExecutionContractError("Incomplete or invalid seed readiness: " + str(error)) from error


def _array_identity(value, name, shape, expected_sha=None):
    if not isinstance(value, dict) or set(value) != {"shape", "dtype", "order", "sha256"}:
        raise ExecutionContractError(name + " requires the canonical four-field array identity")
    dimensions = value["shape"]
    if (not isinstance(dimensions, list) or any(type(item) is not int for item in dimensions)
            or dimensions != shape or value["dtype"] != "<f8" or value["order"] != "C"):
        raise ExecutionContractError(name + " dimensions/dtype/order differ from the exact frozen fixture")
    retained._sha(value["sha256"], name + ".sha256")
    if expected_sha is not None and value["sha256"] != expected_sha:
        raise ExecutionContractError(name + " differs from the full frozen ordinary record")


def _validation_projection(value):
    """Private immutable invariant reuse, never return this as actual policy.

    Seed authorization/policy is checked before this projection is used. The
    substituted old strings satisfy a retained validator's legacy schema; only
    its unchanged science, fixture, paths, resource and numeric invariants are
    reused. No old scientific budget or initialization admission is invoked.
    """
    projected = copy.deepcopy(value)
    projected["schema_version"] = "residual-live-execution-contract-v1"
    projected["authorization_basis"] = {"source": "DIRECT_USER_MESSAGE",
        "message": "请继续下一步实施准入和诊断"}
    projected["initialization"] = {"policy": "FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0",
                                    "initial_gap_minimum_hartree": 1e-6}
    return projected


def validate_execution_contract(value):
    """Validate actual seed-v2 declarations without mutation or file reads.

    A cancelled external review is not method approval. Actual seeded arrays
    and the readiness receipt must still pass byte/body checks in the launch
    supervisor; shape/SHA fields alone never prove A01/A02 or stationarity.
    """
    try:
        if not isinstance(value, dict) or value["schema_version"] != SCHEMA:
            raise ExecutionContractError("Unknown seed-v2 execution contract")
        authorization = value["authorization_basis"]
        if (authorization["source"] != "DIRECT_USER_MESSAGE"
                or authorization["message"] != AUTHORIZATION_MESSAGE):
            raise ExecutionContractError("Explicit current direct-user seed diagnostic instruction required")
        if value["external_review_required"] is not False or value["external_review_status"] != "CANCELLED":
            raise ExecutionContractError("New contract must retain the user's external-review cancellation")
        initial = value["initialization"]
        if initial["policy"] != POLICY or initial["initial_gap_enforced"] is not False:
            raise ExecutionContractError("Actual seed-v2 initialization must not masquerade as an old policy or enforce initial gap")
        gap = initial["final_gap_minimum_hartree"]
        if type(gap) not in (int, float) or gap != 1e-6:
            raise ExecutionContractError("The original final positive-gap threshold must remain exactly 1e-6 Hartree")
        binding = value["seed_binding"]
        if not isinstance(binding, dict) or binding["policy"] != POLICY:
            raise ExecutionContractError("Explicit matching seed provenance required")
        for key in ("record_sha256", "arrays_sha256", "shared_seed_archive_sha256", "readiness_receipt_sha256",
                    "mdr002_record_sha256", "expert_cancellation_receipt_sha256"):
            retained._sha(binding[key], "seed_binding." + key)
        if (binding['record_sha256'] != value['ordinary_origin']['record']['sha256'] or
                binding['arrays_sha256'] != value['ordinary_origin']['arrays']['sha256']):
            raise ExecutionContractError('V2 parent cache identities must equal ordinary_origin')
        retained._sha(binding["implementation_runtime_commit"], "seed implementation runtime commit", 40)
        sources = binding["source_file_sha256"]
        if not isinstance(sources, dict) or not REQUIRED_SEED_SOURCE_FILES <= set(sources):
            raise ExecutionContractError("Both independent seed and adapter implementations require exact source-file hashes")
        for path, digest in sources.items():
            if (not isinstance(path, str) or not path or "\\" in path
                    or PurePosixPath(path).is_absolute() or ":" in path
                    or any(part in {"", ".", ".."} for part in path.split("/"))):
                raise ExecutionContractError("Seed source paths must be canonical relative POSIX paths")
            retained._sha(digest, "seed source file " + path)
        _array_identity(binding["ordinary_D0_identity"], "ordinary_D0_identity", [14, 14],
                        "9dc813178f17be82f7c231c7b9d0a0494e8d4bcd2acea05ac2605bf3bf268f8a")
        if binding["ordinary_D0_identity"] != value["ordinary_origin"]["common_density_identity"]:
            raise ExecutionContractError("Seed parent D0 must be the exact complete ordinary source")
        _array_identity(binding["ordinary_mo_coefficients_identity"], "ordinary_mo_coefficients_identity",
                        [14, 14], FROZEN_MO_COEFFICIENTS_SHA256)
        _array_identity(binding["ordinary_mo_occupations_identity"], "ordinary_mo_occupations_identity",
                        [14], FROZEN_MO_OCCUPATIONS_SHA256)
        _array_identity(binding["seed_density_identity"], "seed_density_identity", [14, 14])
        if binding["seed_density_identity"] == binding["ordinary_D0_identity"]:
            raise ExecutionContractError("This fixed ordinary D0 is not a masked projector; a distinct explicit seed is required")
        retained.validate_execution_contract(_validation_projection(value))
        json.dumps(value, allow_nan=False)
        return value
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, ExecutionContractError):
            raise
        raise ExecutionContractError("Incomplete or invalid exact seed-v2 contract: " + str(error)) from error


def load_execution_contract(path):
    return validate_execution_contract(strict_json(Path(path).read_bytes()))


def validate_proposal_binding(contract, proposal_raw):
    """Bind old proposal bytes/invariants while keeping its old policy intact.

    Initialization intentionally differs. This function neither runs the old
    FIRST_RAW policy nor reopens any historical process or callback budget.
    """
    validate_execution_contract(contract)
    if not isinstance(proposal_raw, bytes) or hashlib.sha256(proposal_raw).hexdigest() != contract["prior_proposal_sha256"]:
        raise ExecutionContractError("Historical proposal exact bytes differ")
    proposal = strict_json(proposal_raw)
    for key in ("fixture", "ordinary_origin", "paths", "comparisons", "scope_limits"):
        if contract[key] != proposal[key]:
            raise ExecutionContractError("Frozen historical invariant differs: " + key)
    if (proposal["initialization"]["policy"] != "FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0"
            or proposal["initialization"]["initial_gap_minimum_hartree"] != 1e-6):
        raise ExecutionContractError("Expected unchanged historical FIRST_RAW proposal")
    return True


def execution_identity(contract, contract_sha256):
    validate_execution_contract(contract)
    retained._sha(contract_sha256, "execution_contract_sha256")
    result = retained.execution_identity(_validation_projection(contract), contract_sha256)
    binding = contract["seed_binding"]
    result.update(mode="LIVE_CONDITIONAL_SEED_V2_DIAGNOSTIC", initialization_policy=POLICY,
        seed_parent_ordinary_record_sha256=binding["record_sha256"], seed_parent_ordinary_arrays_sha256=binding["arrays_sha256"],
        shared_seed_archive_sha256=binding["shared_seed_archive_sha256"],
        seed_readiness_receipt_sha256=binding["readiness_receipt_sha256"],
        seed_implementation_runtime_commit=binding["implementation_runtime_commit"],
        seed_source_files_sha256=canonical_sha(binding["source_file_sha256"]),
        seed_source_file_sha256=copy.deepcopy(binding["source_file_sha256"]),
        ordinary_D0_identity=copy.deepcopy(binding["ordinary_D0_identity"]),
        ordinary_mo_coefficients_identity=copy.deepcopy(binding["ordinary_mo_coefficients_identity"]),
        ordinary_mo_occupations_identity=copy.deepcopy(binding["ordinary_mo_occupations_identity"]),
        seed_density_identity=copy.deepcopy(binding["seed_density_identity"]),
        mdr002_record_sha256=binding["mdr002_record_sha256"],
        expert_cancellation_receipt_sha256=binding["expert_cancellation_receipt_sha256"],
        external_review_status="CANCELLED", external_review_required=False,
        production_activation=False, method_approval=False)
    return result


def pre_functional_admission(observation, vm_available_bytes, contract):
    """Reuse unchanged observed hard limits, after new seed declarations pass."""
    validate_execution_contract(contract)
    result = retained.pre_functional_admission(observation, vm_available_bytes,
                                               _validation_projection(contract))
    result.update(initialization_policy=POLICY, execution_contract_schema=SCHEMA,
                  external_review_status="CANCELLED", external_review_required=False,
                  seed_readiness_body_status="MUST_BE_VERIFIED_BY_SUPERVISOR_BEFORE_LAUNCH",
                  initial_gap_enforced=False, final_gap_minimum_hartree=1e-6)
    return result
