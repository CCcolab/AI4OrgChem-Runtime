"""One authorized, resource-bounded three-path conditional diagnostic.

Reuse the complete frozen ordinary reference record/arrays. Build cached engine
metadata only, then allow original-grid XC and the unchanged conditional F
inside precharged callback slots. This never enables a production profile,
approves a method, retries a path, or reports an unqualified research delta.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path
import sys
import time
import traceback


PATH_IDS = ("production_copy", "production_owned", "independent_reference")
ARRAY_KEYS = ("density", "overlap", "hcore", "eri", "grid_coords", "grid_weights", "mo_coefficients", "mo_occupations")
MIB = 1024**2


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+"\n").encode("utf-8")


def save(path, value):
    """New records only; old outputs or prior attempts are never overwritten."""
    with Path(path).open("xb") as stream:
        stream.write(encode(value))
        stream.flush()
        os.fsync(stream.fileno())


def vm_memory():
    try:
        raw = Path("/proc/meminfo").read_text(encoding="ascii")
        rows = {line.split(":", 1)[0]: line.split(":", 1)[1].split() for line in raw.splitlines() if ":" in line}
        value = rows["MemAvailable"]
        if len(value) != 2 or value[1] != "kB" or not value[0].isdigit():
            raise ValueError("MemAvailable must be an explicit kB counter")
        return {"source": "/proc/meminfo:MemAvailable", "available_bytes": int(value[0])*1024,
                "status": "OBSERVED", "scope": "LINUX_VM_NOT_CONTAINER_CGROUP"}
    except (OSError, KeyError, ValueError) as error:
        return {"source": "/proc/meminfo:MemAvailable", "available_bytes": None,
                "status": "UNKNOWN", "error": type(error).__name__+": "+str(error)}


def resource_reasons(sample):
    """Observe actual native hard limits, without substituting requested flags."""
    reasons = []
    if sample.get("source") not in {"CGROUP_V1", "CGROUP_V2"} or sample.get("errors"):
        reasons.append("NATIVE_CGROUP_UNKNOWN_OR_ERRORS")
    if sample.get("memory_limit_unbounded") is not False or sample.get("memory_limit_bytes") != 1024*MIB:
        reasons.append("HARD_1024_MIB_LIMIT_NOT_CONFIRMED")
    if sample.get("memory_swap_limit_unbounded") is not False or sample.get("memory_swap_limit_bytes") != 0:
        reasons.append("ZERO_SWAP_NOT_CONFIRMED")
    quota, period = sample.get("cpu_quota_us"), sample.get("cpu_period_us")
    if (sample.get("cpu_limit_unbounded") is not False or type(quota) is not int or type(period) is not int
            or quota <= 0 or period <= 0 or quota > period):
        reasons.append("AT_MOST_ONE_CPU_QUOTA_NOT_CONFIRMED")
    for name in ("memory_current_bytes", "memory_peak_bytes"):
        if type(sample.get(name)) is not int or sample[name] < 0:
            reasons.append(name.upper()+"_UNKNOWN")
    events = sample.get("memory_events")
    if sample.get("source") == "CGROUP_V1":
        if not isinstance(events, dict) or any(type(events.get(key)) is not int for key in ("limit_failures", "under_oom")):
            reasons.append("V1_LIMIT_OR_CURRENT_OOM_COUNTER_UNKNOWN")
        elif events["limit_failures"] or events["under_oom"] or events.get("oom_kill", 0):
            reasons.append("V1_LIMIT_FAILURE_OR_OOM_OBSERVED")
    elif not isinstance(events, dict) or any(type(events.get(key)) is not int for key in ("oom", "oom_kill")):
        reasons.append("V2_OOM_COUNTER_UNKNOWN")
    elif events["oom"] or events["oom_kill"]:
        reasons.append("V2_OOM_OBSERVED")
    return reasons


def pack_record(directory, name, value):
    """Keep raw arrays in NPZ and explicit nonfinite diagnostics in strict JSON."""
    import numpy as np
    arrays, undefined = {}, []
    def visit(item, trail="root"):
        if isinstance(item, np.ndarray):
            key = "array_"+str(len(arrays))
            arrays[key] = item.copy()
            raw = np.ascontiguousarray(item).tobytes(order="C")
            finite = bool(np.isfinite(item).all()) if item.dtype.kind in "iufc" else None
            return {"npz_member": key, "shape": list(item.shape), "dtype": item.dtype.str,
                    "sha256": sha(raw), "finite": finite, "record_path": trail}
        if isinstance(item, np.generic):
            return visit(item.item(), trail)
        if isinstance(item, float) and not math.isfinite(item):
            undefined.append({"field": trail, "reason": "NONFINITE_OBSERVED", "raw_representation": repr(item)})
            return None
        if isinstance(item, dict):
            return {str(key): visit(child, trail+"."+str(key)) for key, child in item.items()}
        if isinstance(item, (list, tuple)):
            return [visit(child, trail+"["+str(index)+"]") for index, child in enumerate(item)]
        if item is None or isinstance(item, (str, int, bool, float)):
            return item
        raise TypeError("Unsupported output type at "+trail+": "+type(item).__name__)
    record = visit(value)
    if arrays:
        archive = directory/(name+".npz")
        with archive.open("xb") as stream:
            np.savez_compressed(stream, **arrays)
        record["raw_array_archive"] = {"file": archive.name, "size_bytes": archive.stat().st_size,
                                       "sha256": sha(archive.read_bytes())}
    record["nonfinite_fields"] = undefined
    save(directory/(name+".json"), record)


def scientific_worker(args, output, contract, contract_sha):
    from runtime.user_molecule.acceptance_resources import collect_cgroup
    from runtime.user_molecule.residual_seed_execution_contract import (
        execution_identity, pre_functional_admission, validate_proposal_binding, validate_seed_readiness)
    observations = []
    def observe(phase):
        sample = {"phase": phase, "elapsed_seconds": time.monotonic()-started,
                  "cgroup": collect_cgroup(phase=phase), "vm_memory": vm_memory()}
        observations.append(sample)
        with (output/"resources.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(sample, allow_nan=False)+"\n")
            stream.flush()
            os.fsync(stream.fileno())
        print(json.dumps({"phase": phase, "elapsed_seconds": sample["elapsed_seconds"]}), flush=True)
        return sample
    started = time.monotonic()
    start = observe("START")
    reasons = resource_reasons(start["cgroup"])
    available = start["vm_memory"]["available_bytes"]
    admission = pre_functional_admission(start["cgroup"], available, contract)
    reasons.extend(admission["reasons"])
    save(output/"resource-admission.json", admission)
    if reasons:
        save(output/"diagnostic-result.json", {"execution_status": "BLOCKED_RESOURCE_ADMISSION", "reasons": reasons,
            "scientific_execution": "NOT_EXECUTED_DUE_TO_RESOURCE_ADMISSION",
            "new_real_conditional_callbacks": 0, "new_ordinary_scf_grid_integral_calls": 0,
            "scientific_execution_authorized": True, "execution_contract_sha256": contract_sha,
            "production_activation": False, "comparison_available": False, "deltas": None,
            "method_review_status": contract["method_review_status"]})
        return 20

    import numpy as np
    from pyscf import dft, gto, scf
    actual_dependencies = {name: importlib.metadata.version(name) for name in ("pyscf", "numpy", "scipy")}
    loaded_versions = {name: getattr(importlib.import_module(name), "__version__", None)
                       for name in ("pyscf", "numpy", "scipy")}
    save(output/"dependency-identity.json", {"expected_dependencies": contract["expected_dependencies"],
        "actual_distribution_versions": actual_dependencies, "loaded_module_versions": loaded_versions,
        "scope": "LOCAL_DISTRIBUTION_AND_LOADED_VERSION_BINDING_NOT_EXTERNAL_AUTHENTICATION"})
    if actual_dependencies != contract["expected_dependencies"] or loaded_versions != contract["expected_dependencies"]:
        raise ValueError("Actual imported dependencies differ from the frozen execution contract; no conditional callbacks allowed")
    from reference.ordinary_molecule import build, ReferenceResult
    from reference.residual_seed_v2 import PreparedResidualSeedReferenceV2 as PreparedResidualReference
    from runtime.user_molecule.residual_bridge import array_identity
    from runtime.user_molecule.residual_seed_v2 import PreparedResidualSeedBridgeV2 as PreparedResidualBridge
    from runtime.user_molecule.residual_candidate import density_id
    from runtime.user_molecule.residual_budget import ConditionalCallbackBudget
    from runtime.user_molecule.residual_preparation import (
        load_preparation_input, restore_legacy_basis_representation, create_bridge_contract)
    from runtime.user_molecule.preflight import verify_source

    forbidden_counts = {"SCF_KERNEL": 0, "GRID_BUILD": 0, "INTEGRAL": 0, "GET_HCORE": 0, "GET_OVLP": 0,
                        "NUCLEAR_IN_METADATA_BUILD": 0}
    def forbid(kind):
        def prohibited(*unused, **unused_kw):
            forbidden_counts[kind] += 1
            raise RuntimeError("Forbidden new scientific preparation operation: "+kind)
        return prohibited
    scf.hf.SCF.kernel = forbid("SCF_KERNEL")
    scf.hf.SCF.scf = forbid("SCF_KERNEL")
    scf.hf.kernel = forbid("SCF_KERNEL")
    dft.gen_grid.Grids.build = forbid("GRID_BUILD")
    gto.Mole.intor = forbid("INTEGRAL")
    gto.Mole.intor_by_shell = forbid("INTEGRAL")

    root, science = args.runtime_root.resolve(), args.science_root.resolve()
    proposal_raw = (root/"validation/user-molecule/residual-diagnostic/contract-v1.json").read_bytes()
    validate_proposal_binding(contract, proposal_raw)
    lock = verify_source(root, science)
    if (lock["source_commit"] != contract["science_commit"] or
            lock["baseline_commit"] != contract["science_baseline_commit"]):
        raise ValueError("Frozen science identities differ from execution contract")
    if sha((root/"locks/source-user-molecule-files.sha256.json").read_bytes()) != contract["source_manifest_sha256"]:
        raise ValueError("Scientific source manifest bytes differ")
    fixture = contract["fixture"]
    prepared_input = load_preparation_input(runtime_root=root, request_path=root/fixture["request_path"])
    if (prepared_input["bundle"]["normalized_sha256"] != fixture["normalized_request_sha256"] or
            prepared_input["bundle"]["xyz_sha256"] != fixture["xyz_sha256"] or
            prepared_input["profile_sha256"] != contract["profile_sha256"]):
        raise ValueError("Request/geometry/profile bytes differ from execution contract")
    origin = contract["ordinary_origin"]
    record_path, arrays_path = args.ordinary_dir/origin["record_file"], args.ordinary_dir/origin["arrays_file"]
    from runtime.user_molecule.input import strict_json
    record_raw, arrays_raw = record_path.read_bytes(), arrays_path.read_bytes()
    for raw, expected, name in ((record_raw, origin["record"], "ordinary JSON"), (arrays_raw, origin["arrays"], "ordinary NPZ")):
        if len(raw) != expected["size_bytes"] or sha(raw) != expected["sha256"]:
            raise ValueError(name+" bytes differ; prior evidence cannot be substituted")
    record = strict_json(record_raw)
    with np.load(io.BytesIO(arrays_raw), allow_pickle=False) as archive:
        arrays = {key: archive[key].copy() for key in ARRAY_KEYS}
    for key in ARRAY_KEYS:
        identity = array_identity(arrays[key])
        expected_identity = origin["array_identities"].get(key, contract["seed_binding"].get("ordinary_"+key+"_identity"))
        if identity != expected_identity or identity != record["array_identities"][key]:
            raise ValueError("Old ordinary array identity differs: "+key)
        arrays[key].setflags(write=False)
    if record["components_hartree"]["nuclear_repulsion"] != origin["nuclear_repulsion_hartree"]:
        raise ValueError("Cached nuclear repulsion differs from the complete ordinary record")
    original_class_nuc = gto.Mole.energy_nuc
    gto.Mole.energy_nuc = forbid("NUCLEAR_IN_METADATA_BUILD")
    try:
        context = build(prepared_input["bundle"]["request"], prepared_input["bundle"]["atoms"], prepared_input["profile"])
    finally:
        gto.Mole.energy_nuc = original_class_nuc
    basis_receipt = restore_legacy_basis_representation(context=context, ordinary_record=record)
    save(output/"legacy-basis-representation.json", basis_receipt)
    context.mean_field.grids.coords, context.mean_field.grids.weights = arrays["grid_coords"], arrays["grid_weights"]
    context.mean_field.get_hcore, context.mean_field.get_ovlp = forbid("GET_HCORE"), forbid("GET_OVLP")
    context.mean_field.kernel, context.mean_field.scf = forbid("SCF_KERNEL"), forbid("SCF_KERNEL")
    counts = {name: {"nr_rks_attempts": 0, "nr_rks_completed": 0, "nr_rks_failed": 0, "energy_nuc_attempts": 0} for name in PATH_IDS}
    active = {"path": None, "in_callback": False}
    original_nr = context.mean_field._numint.nr_rks
    original_nuc = context.mol.energy_nuc
    def native_event(kind, path, detail=None):
        event = {"kind": kind, "path": path, "elapsed_seconds": time.monotonic()-started,
                 "counts": copy.deepcopy(counts), "detail": detail,
                 "counter_scope": "ENTERED_INSTRUMENTED_NATIVE_WRAPPER_BEFORE_RAW_INVOCATION_COMPLETION_RECORDED_SEPARATELY"}
        with (output/"native-callbacks.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, allow_nan=False)+"\n")
            stream.flush()
            os.fsync(stream.fileno())
    def counted_nr(*nr_args, **nr_kw):
        path = active["path"]
        if path not in counts or not active["in_callback"]:
            raise RuntimeError("Original-grid XC attempted outside a precharged path callback")
        counts[path]["nr_rks_attempts"] += 1
        native_event("NR_RKS_ENTERED", path)
        try:
            value = original_nr(*nr_args, **nr_kw)
        except BaseException as error:
            counts[path]["nr_rks_failed"] += 1
            native_event("NR_RKS_FAILED", path, type(error).__name__+": "+str(error))
            raise
        counts[path]["nr_rks_completed"] += 1
        native_event("NR_RKS_COMPLETED", path)
        return value
    def counted_nuc(*nuc_args, **nuc_kw):
        path = active["path"]
        if path not in ("production_copy", "production_owned") or not active["in_callback"]:
            raise RuntimeError("Nuclear energy attempted outside the budgeted source conditional callback")
        counts[path]["energy_nuc_attempts"] += 1
        native_event("ENERGY_NUC_ENTERED", path)
        return original_nuc(*nuc_args, **nuc_kw)
    context.mean_field._numint.nr_rks, context.mol.energy_nuc = counted_nr, counted_nuc
    prepared = create_bridge_contract(runtime_root=root, science_root=science, prepared_input=prepared_input,
        context=context, arrays=arrays, ordinary_record=record, runtime_test_commit=contract["runtime_test_commit"],
        image_id=contract["image_id"], image_build_commit=contract["image_build_runtime_commit"],
        execution_kind="PREPARED_MOLECULAR_DIAGNOSTIC", initialization_policy="REQUIRE_EXISTING_MASKED_PROJECTOR",
        ordinary_record_path=record_path, ordinary_arrays_path=arrays_path, maximum_evaluations=201)
    seed_binding = contract["seed_binding"]
    readiness_raw = (args.seed_readiness_dir/"seed-readiness.json").read_bytes()
    readiness = strict_json(readiness_raw)
    validate_seed_readiness(readiness)
    if (sha(readiness_raw) != seed_binding["readiness_receipt_sha256"] or
            readiness["status"] != "PASS_SEED_V2_CACHED_PREPARATION_ONLY" or
            readiness["new_functional_calls"] != 0 or readiness["three_used_seeds_byte_identical"] is not True):
        raise ValueError("Readiness receipt is missing, changed or not qualified")
    for name, expected in seed_binding["source_file_sha256"].items():
        if sha((root/name).read_bytes()) != expected or readiness["source_file_sha256"].get(name) != expected:
            raise ValueError("Tested V2 source bytes differ: "+name)
    for relative, key in (("validation/user-molecule/method-decisions/mdr-002/record.json", "mdr002_record_sha256"),
            ("validation/user-molecule/method-decisions/mdr-002/external-review-cancellation.json", "expert_cancellation_receipt_sha256")):
        if sha((root/relative).read_bytes()) != seed_binding[key]:
            raise ValueError("Internal policy/cancellation receipt differs")
    if sha((args.seed_readiness_dir/"shared-seed.npz").read_bytes()) != seed_binding["shared_seed_archive_sha256"]:
        raise ValueError("Common seed NPZ archive identity differs")
    with np.load(args.seed_readiness_dir/"shared-seed.npz", allow_pickle=False) as archive:
        shared_seed = archive["density"].copy()
    if array_identity(shared_seed) != seed_binding["seed_density_identity"]:
        raise ValueError("Common seed bytes differ from the frozen fresh execution contract")
    shared_seed.setflags(write=False)
    prepared["bridge_kwargs"].update(mo_coefficients=arrays["mo_coefficients"], mo_occupations=arrays["mo_occupations"],
        frozen_ordinary_mo_identities={key: record["array_identities"][key] for key in ("mo_coefficients", "mo_occupations")},
        shared_seed_density=shared_seed)
    save(output/"seed-readiness-binding.json", {"receipt_sha256": sha(readiness_raw),
        "used_seed_identity": array_identity(shared_seed), "policy": contract["initialization"]["policy"],
        "ordinary_density_preserved": True, "zero_functional_preparation": True})
    # Keep the factory's lack of authorization intact. This separately hashed
    # user-authorized execution contract supplies the bounded diagnostic grant.
    save(output/"preparation-contract.json", prepared["contract"])
    save(output/"prepared-mapping.json", prepared["mapping_receipt"])
    save(output/"execution-authorization-receipt.json", {"execution_contract_sha256": contract_sha,
        "authorization_basis": contract["authorization_basis"], "scientific_execution_authorized": True,
        "authorization_scope": "ONE_BOUNDED_CONDITIONAL_DIAGNOSTIC_PROCESS_NOT_METHOD_OR_PRODUCTION_APPROVAL",
        "preparation_authorization": "NOT_GRANTED_BY_PREPARATION", "process_contract": contract["process_contract"]})
    journal_identity = execution_identity(contract, contract_sha)
    journal = ConditionalCallbackBudget(path=output/"callbacks.json", batch_id=contract["batch_id"],
        identity=journal_identity, path_limits={name: 201 for name in PATH_IDS}, total_limit=603)
    save(output/"callback-budget-identity.json", journal_identity)
    prepared_observation = observe("PREPARED")
    if resource_reasons(prepared_observation["cgroup"]):
        raise RuntimeError("Native limits/events no longer satisfy admission after cached preparation")

    class JournaledBridge(PreparedResidualBridge):
        def attach(self, path_id):
            self.captured, self.capture_by_density = [], {}
            def base(density, phase="SOLVER_CALLBACK"):
                active["in_callback"] = True
                try:
                    value = super(JournaledBridge, self).evaluate(density, phase=phase)
                finally:
                    active["in_callback"] = False
                snapshot = {"requested_density_id": value["density_id"], "requested_density": density.copy(),
                    "phase": phase, "value": copy.deepcopy(value)}
                self.captured.append(snapshot)
                self.capture_by_density[value["density_id"]] = snapshot
                return value
            self.accounted = journal.accounted_callback(path_id, base, density_identity=density_id,
                operator_identity=lambda value: density_id(value["fock"]))
            return self
        def evaluate(self, density, phase="SOLVER_CALLBACK"):
            return self.accounted(density, phase=phase)

    class JournaledReference(PreparedResidualReference):
        def attach(self, path_id):
            self.captured, self.capture_by_density = [], {}
            def base(density):
                active["in_callback"] = True
                try:
                    value = super(JournaledReference, self).evaluate(density)
                finally:
                    active["in_callback"] = False
                raw = self.last_evaluation
                snapshot = {"requested_density_id": value["density_id"], "requested_density": density.copy(),
                    "phase": "REFERENCE_CALLBACK_PHASE_FROM_RESULT_LEDGER", "value": copy.deepcopy(dict(value,
                        raw_fock=raw["Fraw"], coulomb_matrix=raw["J"], exchange_matrix=raw["K"],
                        xc_potential=raw["Vxc"], grid_electron_count=raw["grid_electron_count"],
                        masked_metric_electron_count=raw["masked_metric_electron_count"],
                        physical_metric_electron_count=raw["physical_metric_electron_count"]))}
                self.captured.append(snapshot)
                self.capture_by_density[value["density_id"]] = snapshot
                return value
            self.accounted = journal.accounted_callback(path_id, base, density_identity=density_id,
                operator_identity=lambda value: density_id(value["fock"]))
            return self
        def evaluate(self, density):
            return self.accounted(density)

    raw_results, evidence = {}, {}
    solver_settings = contract["solver_parameters"]
    for path_spec in contract["paths"]:
        path_id = path_spec["id"]
        active["path"] = path_id
        before = observe(path_id+"_BEFORE")
        if resource_reasons(before["cgroup"]):
            raise RuntimeError("Native resource limits/events refuse the next diagnostic path")
        path_output = output/path_id
        path_output.mkdir()
        if path_id == "independent_reference":
            engine = JournaledReference(ordinary=ReferenceResult(record, arrays, context),
                rule_path=science/"configs/qm/p09_exchange_integral_classes_v0.1.yaml",
                expected_sha256=lock["condition_rules_sha256"], initialization_policy=contract["initialization"]["policy"],
                maximum_evaluations=201, execution_kind="PREPARED_MOLECULAR_DIAGNOSTIC", shared_seed_density=shared_seed).attach(path_id)
            result = engine.run(maximum_iterations=solver_settings["maximum_iterations"],
                finite_difference_step=solver_settings["finite_difference_step"], trust_radius=solver_settings["trust_radius"])
            solver_result = result
        else:
            engine = JournaledBridge(**prepared["bridge_kwargs"], eri_mode=path_spec["eri_mode"],
                optimize_eri_contractions=path_spec["optimize_eri_contractions"]).attach(path_id)
            result = engine.run(maximum_iterations=solver_settings["maximum_iterations"],
                finite_difference_step=solver_settings["finite_difference_step"], trust_radius=solver_settings["trust_radius"],
                maximum_backtracks=solver_settings["maximum_backtracks"])
            solver_result = result.get("solver_result")
        returned_density = solver_result.get("density") if isinstance(solver_result, dict) else None
        returned_id = density_id(returned_density) if returned_density is not None else None
        returned_snapshot = engine.capture_by_density.get(returned_id)
        captures = {"initial_at_seed_density": engine.captured[0] if engine.captured else None,
            "returned_density_id": returned_id, "returned_density": returned_density,
            "true_evaluation_at_returned_density": returned_snapshot,
            "returned_density_evaluation_status": "RECORDED_MATCHING_DENSITY_ID" if returned_snapshot is not None else "NOT_AVAILABLE_NO_EXTRA_RECOMPUTATION",
            "last_evaluated_snapshot": engine.captured[-1] if engine.captured else None,
            "last_evaluation_is_returned_density": bool(returned_id is not None and engine.captured and engine.captured[-1]["requested_density_id"] == returned_id),
            "role": "LAST_CALLBACK_CAN_BE_MAPPED_OR_TRIAL_DENSITY_NOT_RETURNED_DENSITY",
            "captured_successful_callbacks": len(engine.captured), "actual_native_calls": dict(counts[path_id]),
            "masked_overlap": engine.overlap.copy(), "masked_hcore": engine.hcore.copy(),
            "masked_eri": engine.masked_eri.copy(), "matrix_mask": engine.mask.copy(),
            "deleted_eri_count": engine.deleted if path_id == "independent_reference" else engine.deleted_eri_count}
        journal.close_path(path_id, result["stop_reason"])
        journal_snapshot = journal.snapshot()
        if (result["global_evaluation_count"] > 201 or counts[path_id]["nr_rks_attempts"] > 201 or
                journal_snapshot["path_charged_slots"][path_id] > 201 or any(forbidden_counts.values())):
            raise RuntimeError("Scientific guard/callback budget invariant failed")
        pack_record(path_output, "result", result)
        pack_record(path_output, "evaluations", captures)
        after = observe(path_id+"_AFTER")
        raw_results[path_id], evidence[path_id] = result, captures
        save(path_output/"accounting.json", {"source_callback_attempts": result["global_evaluation_count"],
            "native_calls": counts[path_id], "precharged_slots": journal_snapshot["path_charged_slots"][path_id],
            "precharge_kind": "CONSERVATIVE_PRECALL_SLOTS_NOT_ACTUAL_XC_ATTEMPT_COUNT",
            "forbidden_new_preparation_calls": dict(forbidden_counts), "before": before, "after": after})
        if resource_reasons(after["cgroup"]):
            raise RuntimeError("Native resource limit failures/OOM/errors observed after a path")
        del engine

    active["path"] = None
    comparisons = compare_without_callbacks(raw_results, evidence, contract["comparisons"])
    final = observe("END")
    if resource_reasons(final["cgroup"]):
        raise RuntimeError("Native resource limit failures/OOM/errors observed at final collection")
    snapshot = journal.snapshot()
    for key in ARRAY_KEYS:
        expected_identity = origin["array_identities"].get(key, seed_binding.get("ordinary_"+key+"_identity"))
        if array_identity(arrays[key]) != expected_identity:
            raise RuntimeError("The frozen old ordinary array changed: "+key)
    if record_path.read_bytes() != record_raw or arrays_path.read_bytes() != arrays_raw:
        raise RuntimeError("The mounted old ordinary evidence changed")
    if snapshot["pending_slots"] or snapshot["charged_slots"] > 603 or any(forbidden_counts.values()):
        raise RuntimeError("Final accounting/forbidden-operation invariant failed")
    save(output/"diagnostic-result.json", {"execution_status": "COMPLETED_DIAGNOSTIC", "execution_contract_sha256": contract_sha,
        "scientific_execution": "EXECUTED_DIAGNOSTIC_UNQUALIFIED",
        "scientific_execution_authorized": True, "preparation_authorization": "NOT_GRANTED_BY_PREPARATION",
        "paths": {name: {"stop_reason": raw_results[name]["stop_reason"],
            "engine_qualified": bool((raw_results[name].get("solver_result") or raw_results[name]).get("engine_qualified", False)),
            "actual_native_calls": counts[name], "source_callback_attempts": raw_results[name]["global_evaluation_count"],
            "precharged_slots": snapshot["path_charged_slots"][name]} for name in PATH_IDS},
        "new_ordinary_scf_grid_integral_calls": sum(forbidden_counts.values()), "forbidden_operation_counts": forbidden_counts,
        "callback_budget": snapshot, "comparisons": comparisons, "resources_final": final,
        "resource_acceptance": "PENDING_HOST_COMPLETED_CONTAINER_INSPECT_AND_EXACT_SCOPE_REVIEW",
        "method_review_status": contract["method_review_status"], "research_status": "NOT_QUALIFIED",
        "production_activation": False, "comparison_available": False, "deltas": None,
        "delta_hartree": None, "delta_kcal_mol": None,
        "shared_dependency_limits": ["RAW_INTEGRALS", "ORIGINAL_GRID_XC", "NUMPY", "SCIPY"],
        "scope": "ONE_FIXED_PILOT_DIAGNOSTIC_NOT_PRODUCTION_OR_GENERAL_MOLECULE_SUPPORT"})
    return 0


def compare_without_callbacks(results, evidence, thresholds):
    """Reuse already-budgeted snapshots; never call an operator for comparison."""
    import numpy as np
    matrix_keys = ("fock", "raw_fock", "coulomb_matrix", "exchange_matrix", "xc_potential")
    component_keys = ("one_electron_energy", "coulomb_energy", "exact_exchange_energy", "semilocal_xc_energy", "nuclear_repulsion")
    initial = {name: evidence[name]["initial_at_seed_density"] for name in PATH_IDS}
    t05 = {"status": "NOT_EXECUTED_MISSING_SAME_DENSITY_EVALUATION",
           "full_T05": "NOT_EXECUTED_COMPLETE_MASK_ZERO_ITEMS",
           "scope": "INITIAL_F_DSEED_OPERATOR_ENERGY_PREPARED_MASK_EQUIVALENCE_SUBSET_NOT_QUALIFIED_CONDITIONAL_ENDPOINT"}
    if all(initial.values()) and len({initial[name]["requested_density_id"] for name in PATH_IDS}) == 1:
        rows = []
        reference = initial["independent_reference"]["value"]
        for name in ("production_copy", "production_owned"):
            value = initial[name]["value"]
            matrices = {key: {"max_abs": float(np.max(np.abs(value[key]-reference[key]))),
                             "frobenius": float(np.linalg.norm(value[key]-reference[key]))} for key in matrix_keys}
            components = {key: abs(float(value[key])-float(reference[key])) for key in component_keys}
            total = abs(float(value["total_energy"])-float(reference["total_energy"]))
            grid = abs(float(value["grid_electron_count"])-float(reference["grid_electron_count"]))
            limit = thresholds["T05_same_density"]
            masks = {key: float(np.max(np.abs(evidence[name][key]-evidence["independent_reference"][key])))
                     for key in ("masked_overlap", "masked_hcore", "masked_eri")}
            masks["conditional_fock_deleted_blocks_max_abs"] = float(np.max(
                np.abs(value["fock"][evidence[name]["matrix_mask"]]), initial=0))
            deletion_equal = evidence[name]["deleted_eri_count"] == evidence["independent_reference"]["deleted_eri_count"]
            passed = (all(row["max_abs"] <= limit["matrix_max_abs"] and row["frobenius"] <= limit["matrix_frobenius"] for row in matrices.values())
                      and all(row <= limit["component_hartree"] for row in components.values())
                      and total <= limit["total_energy_hartree"] and grid <= limit["grid_electron_count_abs"]
                      and all(row <= limit["mask_max_abs"] for row in masks.values()) and deletion_equal)
            rows.append({"path": name, "matrices": matrices, "component_abs_hartree": components,
                         "mask_max_abs": masks, "deleted_eri_count_equal": deletion_equal,
                         "total_energy_abs_hartree": total, "grid_electrons_abs": grid, "pass_original_tolerance": passed})
        subset_pass = all(row["pass_original_tolerance"] for row in rows)
        t05.update(status="PASS_SCOPED_OPERATOR_ENERGY_MASK_EQUIVALENCE_SUBSET" if subset_pass else "FAIL_SCOPED_OPERATOR_ENERGY_MASK_EQUIVALENCE_SUBSET",
                   T05_operator_energy_subset="PASS" if subset_pass else "FAIL", rows=rows,
                   density_id=initial["independent_reference"]["requested_density_id"])
    solvers = {name: results[name].get("solver_result") if "solver_result" in results[name] else results[name] for name in PATH_IDS}
    qualified = all(isinstance(solvers[name], dict) and solvers[name].get("engine_qualified") is True for name in PATH_IDS)
    terminal = {"status": "NOT_EXECUTED_UNQUALIFIED_ENDPOINTS", "P12": "NOT_EXECUTED", "P13": "NOT_EXECUTED", "T06": "NOT_EXECUTED"}
    raw_differences = []
    for left, right in (("production_copy", "production_owned"), ("production_copy", "independent_reference"),
                        ("production_owned", "independent_reference")):
        row = {"left": left, "right": right, "role": "RAW_CODE_DIAGNOSTIC_NOT_SCIENTIFIC_ACCEPTANCE"}
        dl, dr = evidence[left]["returned_density"], evidence[right]["returned_density"]
        sl, sr = evidence[left]["true_evaluation_at_returned_density"], evidence[right]["true_evaluation_at_returned_density"]
        row["density_frobenius"] = float(np.linalg.norm(dl-dr)) if dl is not None and dr is not None else None
        row["energy_abs_hartree"] = abs(sl["value"]["total_energy"]-sr["value"]["total_energy"]) if sl is not None and sr is not None else None
        row["fock_frobenius"] = float(np.linalg.norm(sl["value"]["fock"]-sr["value"]["fock"])) if sl is not None and sr is not None else None
        row["missing_value_reason"] = None if all(row[key] is not None for key in ("density_frobenius", "energy_abs_hartree", "fock_frobenius")) else "NO_MATCHING_RETURNED_DENSITY_SNAPSHOT_WITHIN_BUDGET"
        raw_differences.append(row)
    if qualified and all(evidence[name]["true_evaluation_at_returned_density"] is not None for name in PATH_IDS):
        values = {name: evidence[name]["true_evaluation_at_returned_density"]["value"] for name in PATH_IDS}
        densities = {name: solvers[name]["density"] for name in PATH_IDS}
        density_pair = float(np.linalg.norm(densities["production_copy"]-densities["production_owned"]))
        energy_pair = abs(values["production_copy"]["total_energy"]-values["production_owned"]["total_energy"])
        reference_rows = []
        for name in ("production_copy", "production_owned"):
            row = {"path": name, "density_frobenius": float(np.linalg.norm(densities[name]-densities["independent_reference"])),
                   "fock_frobenius": float(np.linalg.norm(values[name]["fock"]-values["independent_reference"]["fock"])),
                   "energy_abs_hartree": abs(values[name]["total_energy"]-values["independent_reference"]["total_energy"]),
                   "component_abs_hartree": {key: abs(values[name][key]-values["independent_reference"][key]) for key in component_keys}}
            row["pass_original_tolerance"] = (row["density_frobenius"] <= thresholds["T06_density_frobenius"] and
                row["fock_frobenius"] <= thresholds["T06_fock_frobenius"] and row["energy_abs_hartree"] <= thresholds["T06_total_energy_hartree"] and
                all(value <= thresholds["T06_component_hartree"] for value in row["component_abs_hartree"].values()))
            reference_rows.append(row)
        comparable = density_pair <= thresholds["P13_density_difference_frobenius"] and all(row["density_frobenius"] <= thresholds["T06_density_frobenius"] for row in reference_rows)
        terminal.update(status="EXECUTED_QUALIFIED_CODE_ENDPOINT_COMPARISON" if comparable else "ROOTS_NOT_COMPARABLE",
            raw_production_energy_difference_hartree=energy_pair, raw_production_density_difference_frobenius=density_pair,
            independent_rows=reference_rows,
            P12=("PASS" if energy_pair <= thresholds["P12_energy_difference_hartree"] else "FAIL") if comparable else "NOT_EXECUTED_ROOTS_NOT_COMPARABLE",
            P13="PASS" if comparable else "NOT_EXECUTED_ROOTS_NOT_COMPARABLE",
            T06=("PASS" if all(row["pass_original_tolerance"] for row in reference_rows) else "FAIL") if comparable else "NOT_EXECUTED_ROOTS_NOT_COMPARABLE")
    return {"T05_initial_same_density": t05, "terminal_endpoints": terminal,
            "raw_endpoint_differences": raw_differences, "research_classification": "NOT_GRANTED", "extra_operator_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-readiness-dir", type=Path, default=Path("/seed-readiness"))
    parser.add_argument("--contract", type=Path, default=Path("/execution-contract.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("/output"))
    parser.add_argument("--ordinary-dir", type=Path, default=Path("/saved-ordinary"))
    parser.add_argument("--runtime-root", type=Path, default=Path("/workspace"))
    parser.add_argument("--science-root", type=Path, default=Path("/opt/ai4orgchem"))
    args = parser.parse_args()
    sys.path.insert(0, str(args.runtime_root.resolve()))
    sys.path.insert(0, str(args.science_root.resolve()/"software/src"))
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any((output/name).exists() for name in ("WORKER_STARTED.json", "callbacks.json", "diagnostic-result.json", "resources.jsonl")):
        raise ValueError("Fresh output leaf required; no retry, overwrite or budget reset")
    from runtime.user_molecule.residual_seed_execution_contract import load_execution_contract
    contract = load_execution_contract(args.contract)
    contract_raw = args.contract.read_bytes()
    contract_sha = sha(contract_raw)
    for key, environment in (("runtime_test_commit", "AI4ORGCHEM_RUNTIME_TEST_COMMIT"), ("image_id", "AI4ORGCHEM_IMAGE_ID"),
                             ("image_build_runtime_commit", "AI4ORGCHEM_IMAGE_BUILD_COMMIT")):
        if os.environ.get(environment) != contract[key]:
            raise ValueError("Execution contract environment binding differs: "+key)
    save(output/"WORKER_STARTED.json", {"pid": os.getpid(), "contract_sha256": contract_sha,
        "runtime_test_commit": contract["runtime_test_commit"], "execution_kind": "LIVE_CONDITIONAL_SEED_V2_DIAGNOSTIC",
        "authorized_scope": contract["authorization_basis"], "automatic_retry": False})
    try:
        return scientific_worker(args, output, contract, contract_sha)
    except BaseException as error:
        try:
            from runtime.user_molecule.acceptance_resources import collect_cgroup
            save(output/"fatal-resource-end.json", {"cgroup": collect_cgroup(phase="FATAL_END"), "vm_memory": vm_memory()})
        except Exception:
            traceback.print_exc()
        save(output/"worker-fatal-error.json", {"exception_type": type(error).__name__, "message": str(error),
            "traceback": traceback.format_exc(), "status": "FATAL_NOT_QUALIFIED",
            "production_activation": False, "comparison_available": False, "deltas": None})
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
