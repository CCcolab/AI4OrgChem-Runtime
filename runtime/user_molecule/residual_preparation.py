"""Read-only mapping of one fixed pilot request to prepared cached data.

This module never builds a molecular engine or calls SCF, integrals, grids or
XC. Cached molecule queries and existing ordinary records bind preparation
identities. They do not independently authenticate the engine or approve a
method, resource budget, research interpretation or production Compute.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
from numbers import Real
from pathlib import Path
import re

import numpy as np

from reference.user_molecule import classify
from .input import geometry_path, parse_xyz, read_request, strict_json
from .preflight import verify_source
from .residual_bridge import (BridgeRefusal, SCIENCE_BASELINE_COMMIT, SCIENCE_COMMIT,
                              array_identity, descriptor_identity)


PROFILE_ID = "pilot-b3lypg-sto3g-grid2-v1"
FIXTURE_ID = "ethene-planar-technical-v1"
REQUEST_NORMALIZED_SHA256 = "46a9f72bcf346e3be353d98291d8873a957675329f907ffd8271ca72df61bbab"
XYZ_SHA256 = "69f55725834dfa8419dfc6019ae56dd564f9a0ae18ec28e706245b785bfac80d"
PROFILE_BYTE_SHA256 = {
    "18bd594a8b606ef2c90db4390243155031035cd98fbe72dfc2e9367aeadce2e9",
    "c3359c80f2b292c14875335b8e14a22e37f35858581402b0b47e0f20c6884f45"}
PROFILE_CANONICAL_SHA256 = "5c78ef8e741b255421a465895524cdb7aa208ef90751a1524eff9c7f88e5d537"
COORDINATE_CONVERSION_GUARD_ANGSTROM = 1e-12
_ARRAY_KEYS = ("density", "hcore", "overlap", "eri", "grid_coords", "grid_weights")


def _fail(reason, detail):
    raise BridgeRefusal(reason, detail)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _hash(value):
    return hashlib.sha256(value).hexdigest()


def _scalar(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or not np.isfinite(value):
        _fail("PREPARATION_SCALAR_MISSING_OR_INVALID", name + " must be an existing finite real scalar")
    return float(value)


def restore_legacy_basis_representation(*, context, ordinary_record):
    """Explicit fixed-C/H dict-order compatibility, never a basis-value repair.

    The historical identity used repr(mol._basis), which includes dictionary
    insertion order. Restore that order only if one of the two exact typed-value
    representations hashes to the old identity and all other metadata agrees.
    Keep old records untouched; freeze atom/AO/native engine arrays before/after.
    """
    mol = context.mol
    recorded = ordinary_record["metadata"]
    actual = context.metadata
    basis = mol._basis
    if not isinstance(basis, dict) or set(basis) != {"C", "H"}:
        _fail("LEGACY_BASIS_SCOPE_REFUSED", "Only the fixed two-element C/H cache is supported")
    before_repr = repr(basis)
    before_sha = _hash(before_repr.encode("utf-8"))
    expected_sha = recorded.get("basis_expansion_sha256")
    if actual.get("basis_expansion_sha256") != before_sha:
        _fail("LEGACY_BASIS_CACHE_METADATA_REFUSED", "Builder metadata must describe the actual cached representation")
    other = {key: value for key, value in actual.items() if key != "basis_expansion_sha256"}
    expected_other = {key: value for key, value in recorded.items() if key != "basis_expansion_sha256"}
    if other != expected_other:
        _fail("LEGACY_BASIS_OTHER_METADATA_REFUSED", "Only a basis representation hash difference may be restored")
    representations = []
    for order in (("C", "H"), ("H", "C")):
        reordered = {key: basis[key] for key in order}
        text = repr(reordered)
        representations.append({"order": list(order), "repr": text,
                                "sha256": _hash(text.encode("utf-8"))})
    matching = [row for row in representations if row["sha256"] == expected_sha]
    if len(matching) != 1:
        _fail("LEGACY_BASIS_IDENTITY_NOT_REPRODUCED", "Neither exact C/H key order reproduces the historical hash")
    def typed(value):
        if isinstance(value, np.ndarray):
            _fail("LEGACY_BASIS_VALUE_REFUSED", "Legacy repr may truncate arrays; basis values must have a complete scalar/list/tuple representation")
        if isinstance(value, dict):
            return ["dict", [[key, typed(value[key])] for key in sorted(value)]]
        if isinstance(value, (list, tuple)):
            return [type(value).__name__, [typed(child) for child in value]]
        if isinstance(value, (str, bool, int, float, np.integer, np.floating)) or value is None:
            if isinstance(value, (float, np.floating)) and not np.isfinite(value):
                _fail("LEGACY_BASIS_VALUE_REFUSED", "Basis scalar values must be finite")
            return [type(value).__module__+"."+type(value).__qualname__, repr(value)]
        _fail("LEGACY_BASIS_VALUE_REFUSED", "Unsupported cached value type")
    fingerprint = _hash(_canonical(typed(basis)))
    def cache_snapshot():
        native = {}
        for name in ("_atm", "_bas", "_env"):
            if hasattr(mol, name):
                array = np.asarray(getattr(mol, name))
                native[name] = {"dtype": array.dtype.str, "shape": list(array.shape),
                                "sha256": _hash(array.tobytes(order="C"))}
        return {"native_arrays": native,
                "coordinates_angstrom": array_identity(mol.atom_coords(unit="Angstrom")),
                "ao_labels": [list(label) for label in mol.ao_labels(fmt=False)]}
    caches = cache_snapshot()
    selected = matching[0]
    restored = {key: basis[key] for key in selected["order"]}
    if _hash(_canonical(typed(restored))) != fingerprint or any(restored[key] is not basis[key] for key in basis):
        _fail("LEGACY_BASIS_VALUE_CHANGED", "Reordering must preserve exact typed values and child objects")
    mol._basis = restored
    context.metadata = copy.deepcopy(actual)
    context.metadata["basis_expansion_sha256"] = _hash(repr(mol._basis).encode("utf-8"))
    if cache_snapshot() != caches or context.metadata != recorded:
        _fail("LEGACY_BASIS_NATIVE_CACHE_CHANGED", "Native engine arrays/AOs/atoms or restored metadata differ")
    return {"status": "PASS_EXACT_LEGACY_BASIS_REPRESENTATION",
            "representation_changed": before_sha != expected_sha,
            "before_repr": before_repr, "before_sha256": before_sha,
            "matched_repr": selected["repr"], "matched_sha256": selected["sha256"],
            "tested_representations": representations, "typed_value_sha256": fingerprint,
            "native_cache_before_and_after": caches, "basis_values_changed": False,
            "old_record_changed": False, "new_scientific_calls": 0,
            "scope": "EXACT_FIXED_CH_DICTIONARY_ORDER_ONLY_NOT_BASIS_REPAIR_OR_AUTHENTICATION"}


def _verify_input_bundle(bundle, profile):
    try:
        request = strict_json(bundle["request_bytes"])
        atoms = parse_xyz(bundle["xyz_bytes"])
        canonical = _canonical(request)
        if (request != bundle["request"] or atoms != bundle["atoms"] or
                _hash(bundle["request_bytes"]) != bundle["request_sha256"] or
                _hash(bundle["xyz_bytes"]) != bundle["xyz_sha256"] or
                _hash(canonical) != bundle["normalized_sha256"] or
                canonical != bundle["normalized_bytes"]):
            _fail("PREPARATION_INPUT_IDENTITY_MISMATCH", "Prepared bundle differs from its original request or XYZ bytes")
        if (bundle["normalized_sha256"] != REQUEST_NORMALIZED_SHA256 or
                bundle["xyz_sha256"] != XYZ_SHA256 or
                request["calculation_profile"] != PROFILE_ID):
            _fail("PREPARATION_FIXTURE_SCOPE_BLOCKED", "Only the registered, unchanged pilot ethene request is admitted")
        if profile.get("id") != PROFILE_ID or _hash(_canonical(profile)) != PROFILE_CANONICAL_SHA256:
            _fail("PREPARATION_PROFILE_MISMATCH", "Use the exact existing disabled pilot profile")
        if profile.get("compute_enabled") is not False or profile.get("method_scope_approval") is not None:
            _fail("PREPARATION_PROFILE_MISMATCH", "Preparation cannot activate or approve a service profile")
        expected_mapping = [{"index_1based": i, "index_0based": i-1, "element": atom[0],
            "coordinates_angstrom": atom[1], "pi_group": "A" if i == 1 else "B" if i == 2 else None}
            for i, atom in enumerate(atoms, 1)]
        if bundle["atom_mapping"] != expected_mapping:
            _fail("PREPARATION_ATOM_MAPPING_MISMATCH", "The input's atom numbering or group mapping changed")
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, BridgeRefusal):
            raise
        _fail("PREPARATION_INPUT_INCOMPLETE", str(error))


def load_preparation_input(*, runtime_root, request_path):
    """Reuse strict local schema/path handling, then restrict to one fixture."""
    root = Path(runtime_root).resolve()
    schema = strict_json((root / "schemas/user-molecule-request-v1.json").read_bytes())
    bundle = read_request(request_path, schema)
    profile_path = root / "profiles/user-molecule" / (bundle["request"]["calculation_profile"]+".json")
    raw = profile_path.read_bytes()
    if _hash(raw) not in PROFILE_BYTE_SHA256:
        _fail("PREPARATION_PROFILE_MISMATCH", "Profile bytes do not match this pilot file's verified LF/CRLF identities")
    profile = strict_json(raw)
    _verify_input_bundle(bundle, profile)
    return {"bundle": bundle, "profile": profile, "profile_path": profile_path,
            "request_path": Path(request_path).resolve(),
            "geometry_path": geometry_path(request_path, bundle["request"]["geometry_file"]),
            "profile_sha256": _hash(raw), "fixture_id": FIXTURE_ID,
            "scientific_execution": "NOT_EXECUTED", "production_activation": False}


def verify_prepared_mapping(*, bundle, context, arrays, ordinary_record, profile):
    """Check cached atom/AO/configuration/array correspondence, without evaluation.

    ``context`` follows the existing reference MolecularContext shape. Only
    atom_symbol(s), atom_coords(unit='Angstrom') and ao_labels(fmt=False) are
    queried; these must be cached reads in the supplied context.
    """
    _verify_input_bundle(bundle, profile)
    try:
        metadata = ordinary_record["metadata"]
        if context.profile != profile or context.metadata != metadata:
            _fail("PREPARATION_CONTEXT_RECORD_MISMATCH", "Context profile/metadata must belong to this one ordinary record")
        mol, mf = context.mol, context.mean_field
        if mf.mol is not mol:
            _fail("PREPARATION_ENGINE_CONTEXT_MISMATCH", "Prepared mean_field does not refer to the same cached molecule")
        atoms = bundle["atoms"]
        coordinates = np.asarray([atom[1] for atom in atoms], dtype=float)
        symbols = [atom[0] for atom in atoms]
        electrons = sum(6 if element == "C" else 1 for element in symbols)
        if (type(mol.natm) is not int or mol.natm != len(atoms) or
                type(mol.nelectron) is not int or mol.nelectron != electrons or electrons != 16 or
                type(mol.charge) is not int or mol.charge != 0 or
                type(mol.spin) is not int or mol.spin != 0 or mol.cart is not False or
                mol.symmetry is not False or mol.basis != profile["basis"] or mol.ecp != {}):
            _fail("PREPARATION_MOLECULE_CONFIGURATION_MISMATCH", "Cached neutral spherical singlet/basis/electron configuration differs")
        cached_symbols = list(mol.atom_symbols()) if callable(getattr(mol, "atom_symbols", None)) else [mol.atom_symbol(i) for i in range(mol.natm)]
        if cached_symbols != symbols:
            _fail("PREPARATION_ATOM_ORDER_MISMATCH", "Cached atom elements or order differ from the original XYZ")
        cached_coordinates = np.asarray(mol.atom_coords(unit="Angstrom"))
        if (cached_coordinates.dtype.kind not in "iuf" or cached_coordinates.shape != coordinates.shape or
                not np.isfinite(cached_coordinates).all() or
                float(np.max(np.abs(cached_coordinates-coordinates))) > COORDINATE_CONVERSION_GUARD_ANGSTROM):
            _fail("PREPARATION_COORDINATE_MAPPING_MISMATCH", "Cached Angstrom coordinates differ; no rotation, fit, reorder or unit inference is permitted")
        if float(np.max(np.abs(cached_coordinates[:, 2]))) > 1e-8:
            _fail("PREPARATION_XY_ORIENTATION_MISMATCH", "Original fixed xy orientation must be retained")
        expected_molecule = {"basis": profile["basis"], "unit": "Angstrom", "charge": 0,
            "spin": 0, "cart": False, "symmetry": False, "ecp": {}}
        groups = {group["id"]: group["carbon_atom_indices_1based"] for group in bundle["request"]["fragments"]}
        expected_metadata = {"nao": 14, "electron_count": 16, "atom_coordinates_angstrom": coordinates.tolist(),
            "atom_elements": symbols, "fragments_1based": groups, "atom_order_preserved": True,
            "coordinate_reorientation": False, "molecule_effective": expected_molecule,
            "basis_expansion_sha256": _hash(repr(mol._basis).encode("utf-8")),
            "profile_id": profile["id"], "profile_canonical_sha256": _hash(_canonical(profile)),
            "dependencies": profile["expected_dependencies"], "threads": 1,
            "xc_effective": {"xc": profile["xc"], "omega": 0.0, "alpha": .2, "hybrid": .2},
            "ordinary_effective": profile["ordinary"],
            "grid_effective": dict(profile["grid"], small_rho_cutoff=0, nlc="")}
        for name, expected in expected_metadata.items():
            if name not in metadata or metadata[name] != expected:
                _fail("PREPARATION_RECORDED_METADATA_MISMATCH", "Ordinary-record metadata differs or is missing: " + name)
        if mf.xc != profile["xc"] or mf.small_rho_cutoff != 0 or mf.nlc != "":
            _fail("PREPARATION_XC_SETTINGS_MISMATCH", "Cached XC or original-grid cutoff/NLC settings differ")
        for name, value in profile["ordinary"].items():
            actual = getattr(mf, "max_memory" if name == "max_memory_mb" else name)
            if actual != value:
                _fail("PREPARATION_ORDINARY_SETTINGS_MISMATCH", "Cached ordinary setting differs: " + name)
        from pyscf.dft import gen_grid, radi
        for name, expected in (("prune", gen_grid.nwchem_prune), ("radi_method", radi.treutler),
                               ("radii_adjust", radi.treutler_atomic_radii_adjust),
                               ("becke_scheme", gen_grid.original_becke)):
            if getattr(mf.grids, name) is not expected:
                _fail("PREPARATION_GRID_SETTINGS_MISMATCH", "Cached grid algorithm differs: " + name)
        if (mf.grids.level != profile["grid"]["level"] or mf.grids.alignment != 8 or
                mf.grids.atom_grid != {} or not np.array_equal(mf.grids.atomic_radii, radi.BRAGG_RADII)):
            _fail("PREPARATION_GRID_SETTINGS_MISMATCH", "Cached grid level/radii/alignment/atom_grid differs")
        raw_labels = list(mol.ao_labels(fmt=False))
        labels = []
        for label in raw_labels:
            if (len(label) != 4 or isinstance(label[0], (bool, np.bool_)) or
                    not isinstance(label[0], (int, np.integer)) or
                    not 0 <= int(label[0]) < len(symbols) or label[1] != symbols[int(label[0])]):
                _fail("PREPARATION_AO_LABEL_MISMATCH", "Cached AO center/element mapping is invalid")
            labels.append([int(label[0]), *label[1:]])
        if len(labels) != 14 or labels != metadata["ao_labels"]:
            _fail("PREPARATION_AO_LABEL_MISMATCH", "Cached AO labels differ from the ordinary record")
        classified = classify(labels, cached_coordinates, groups)
        descriptor_data = [{"kind": ao.kind, "fragment": ao.group} for ao in classified]
        cached_descriptor_data = [{"kind": ao.kind, "fragment": ao.group} for ao in context.aos]
        if descriptor_data != metadata["ao_descriptors"] or descriptor_data != cached_descriptor_data:
            _fail("PREPARATION_AO_GROUP_MISMATCH", "Cached AO parity/atom-group mapping differs from the request")
        identities = {}
        for name in _ARRAY_KEYS:
            actual = array_identity(arrays[name])
            expected_shape = [14]*4 if name == "eri" else [14, 14] if name in {"density", "hcore", "overlap"} else None
            if expected_shape is not None and actual["shape"] != expected_shape:
                _fail("PREPARATION_ARRAY_DIMENSION_MISMATCH", "Prepared array dimensions differ: " + name)
            if actual != ordinary_record["array_identities"][name]:
                _fail("PREPARATION_ARRAY_IDENTITY_MISMATCH", "Prepared array bytes differ from the ordinary record: " + name)
            identities[name] = actual
        grid_coords, grid_weights = np.asarray(arrays["grid_coords"]), np.asarray(arrays["grid_weights"])
        if (grid_coords.ndim != 2 or grid_coords.shape[1] != 3 or grid_weights.shape != (len(grid_coords),) or
                array_identity(mf.grids.coords) != identities["grid_coords"] or
                array_identity(mf.grids.weights) != identities["grid_weights"] or
                ordinary_record["grid_identity"] != {"coords": identities["grid_coords"], "weights": identities["grid_weights"]}):
            _fail("PREPARATION_GRID_MAPPING_MISMATCH", "Frozen grid arrays, engine cache and ordinary record do not match")
        if ordinary_record["grid_points"] != len(grid_weights):
            _fail("PREPARATION_GRID_MAPPING_MISMATCH", "Recorded grid point count differs")
        if ordinary_record.get("converged") is not True or not ordinary_record.get("qualification_tests") or any(
                value is not True for value in ordinary_record["qualification_tests"].values()):
            _fail("PREPARATION_ORDINARY_RECORD_UNQUALIFIED", "An explicitly qualified existing ordinary record is required, without re-executing it")
        components = ordinary_record["components_hartree"]
        component_names = ("one_electron", "coulomb", "exact_exchange", "semilocal_xc", "nuclear_repulsion")
        numbers = [_scalar(components[name], name) for name in component_names]
        total = _scalar(ordinary_record["total_energy_hartree"], "Recorded ordinary total energy")
        if abs(sum(numbers)-total) > profile["thresholds"]["energy_closure_hartree"]:
            _fail("PREPARATION_ORDINARY_ENERGY_CLOSURE_MISMATCH", "The existing ordinary record's five components and returned energy do not close")
        receipt = {"schema_version": 1, "status": "PASS_CACHED_MAPPING_ONLY", "fixture_id": FIXTURE_ID,
            "request_sha256": bundle["request_sha256"], "normalized_request_sha256": bundle["normalized_sha256"],
            "geometry_sha256": bundle["xyz_sha256"], "profile_canonical_sha256": _hash(_canonical(profile)),
            "atom_mapping": copy.deepcopy(bundle["atom_mapping"]), "ao_labels": labels,
            "ao_descriptors": descriptor_data, "array_identities": identities,
            "ordinary_record_canonical_sha256": _hash(_canonical(ordinary_record)),
            "metadata_canonical_sha256": _hash(_canonical(metadata)),
            "basis_expansion_sha256": metadata["basis_expansion_sha256"],
            "nuclear_repulsion_hartree": numbers[-1], "nuclear_repulsion_source": "ordinary_record.components_hartree.nuclear_repulsion",
            "coordinate_conversion_guard_angstrom": COORDINATE_CONVERSION_GUARD_ANGSTROM,
            "engine_coordinate_reorientation": False, "engine_atom_reordering": False,
            "ordinary_qualification": "EXISTING_RECORDED_STATUS_NOT_REEXECUTED_OR_AUTHENTICATED",
            "identity_evidence_kind": "LOCAL_CACHED_MAPPING_NOT_ENGINE_AUTHENTICATION",
            "scientific_execution": "NOT_EXECUTED", "production_activation": False,
            "molecular_acceptance": "NOT_EXECUTED", "research_acceptance": "NOT_ACCEPTED",
            "comparison_available": False, "deltas": None}
        _canonical(receipt)
        return receipt
    except (KeyError, AttributeError, TypeError, ValueError, OverflowError) as error:
        if isinstance(error, BridgeRefusal):
            raise
        _fail("PREPARATION_MAPPING_INCOMPLETE_OR_INVALID", type(error).__name__+": "+str(error))


def create_bridge_contract(*, runtime_root, science_root, prepared_input, context,
                           arrays, ordinary_record, runtime_test_commit, image_id,
                           image_build_commit, execution_kind, initialization_policy,
                           ordinary_record_path, ordinary_arrays_path,
                           maximum_evaluations=201):
    """Assemble a freshly rechecked preparation contract; never run a bridge."""
    if execution_kind not in {"ENGINEERING_FAKE", "PREPARED_MOLECULAR_DIAGNOSTIC"}:
        _fail("PREPARATION_EXECUTION_KIND_INVALID", "Explicit fake or future prepared-diagnostic identity required; this API never executes either")
    if initialization_policy not in {"FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0", "REQUIRE_EXISTING_MASKED_PROJECTOR"}:
        _fail("PREPARATION_INITIALIZATION_POLICY_REQUIRED", "Explicit candidate initialization policy required")
    if type(maximum_evaluations) is not int or not 2 <= maximum_evaluations <= 201:
        _fail("PREPARATION_INVALID_EVALUATION_BUDGET", "Global callback budget must be an integer in [2,201]")
    for name, value, pattern in (("runtime_test_commit", runtime_test_commit, r"[0-9a-f]{40}"),
                               ("image_id", image_id, r"sha256:[0-9a-f]{64}"),
                               ("image_build_commit", image_build_commit, r"[0-9a-f]{40}")):
        if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
            _fail("PREPARATION_INVALID_EXECUTION_IDENTITY", name + " is malformed or missing")
    root, science = Path(runtime_root).resolve(), Path(science_root).resolve()
    bundle, profile = prepared_input["bundle"], prepared_input["profile"]
    profile_path = Path(prepared_input["profile_path"]).resolve()
    if profile_path != root / "profiles/user-molecule" / (PROFILE_ID+".json"):
        _fail("PREPARATION_PROFILE_PATH_MISMATCH", "Prepared profile path differs from the frozen runtime file")
    raw_profile = profile_path.read_bytes()
    if _hash(raw_profile) not in PROFILE_BYTE_SHA256 or strict_json(raw_profile) != profile:
        _fail("PREPARATION_PROFILE_MISMATCH", "Prepared profile differs from its current frozen bytes")
    receipt = verify_prepared_mapping(bundle=bundle, context=context, arrays=arrays,
        ordinary_record=ordinary_record, profile=profile)
    provenance = {}
    for name, path, expected in (("request", prepared_input["request_path"], bundle["request_bytes"]),
                                 ("geometry", prepared_input["geometry_path"], bundle["xyz_bytes"])):
        path = Path(path).resolve()
        raw = path.read_bytes()
        if raw != expected:
            _fail("PREPARATION_SOURCE_FILE_CHANGED", "Original input source bytes changed: " + name)
        provenance[name] = {"path": str(path), "size_bytes": len(raw), "sha256": _hash(raw)}
    record_path, archive_path = Path(ordinary_record_path).resolve(), Path(ordinary_arrays_path).resolve()
    record_bytes = record_path.read_bytes()
    if strict_json(record_bytes) != ordinary_record:
        _fail("PREPARATION_RECORD_SOURCE_MISMATCH", "Supplied ordinary record is not this complete JSON source")
    archive_bytes = archive_path.read_bytes()
    with np.load(io.BytesIO(archive_bytes), allow_pickle=False) as archive:
        for name in _ARRAY_KEYS:
            if name not in archive.files or array_identity(archive[name]) != receipt["array_identities"][name]:
                _fail("PREPARATION_ARRAY_ARCHIVE_SOURCE_MISMATCH", "Ordinary NPZ source member differs or is missing: " + name)
    provenance["ordinary_record"] = {"path": str(record_path), "size_bytes": len(record_bytes), "sha256": _hash(record_bytes)}
    provenance["ordinary_arrays"] = {"path": str(archive_path), "size_bytes": len(archive_bytes), "sha256": _hash(archive_bytes),
        "verified_members": list(_ARRAY_KEYS), "unused_members": "NOT_READ_NOT_VERIFIED"}
    lock = verify_source(root, science)
    if lock.get("source_commit") != SCIENCE_COMMIT or lock.get("baseline_commit") != SCIENCE_BASELINE_COMMIT:
        _fail("PREPARATION_SOURCE_LOCK_MISMATCH", "Frozen science baseline/adapter identities differ")
    from ai4orgchem.qm.p09_eri_mask import AODescriptor
    descriptors = tuple(AODescriptor(ao.kind, ao.group) for ao in context.aos)
    ids = receipt["array_identities"]
    contract = {"science_commit": SCIENCE_COMMIT, "science_baseline_commit": SCIENCE_BASELINE_COMMIT,
        "runtime_test_commit": runtime_test_commit, "image_id": image_id, "image_build_commit": image_build_commit,
        "request_sha256": bundle["request_sha256"], "profile_sha256": _hash(raw_profile),
        "condition_rules_sha256": lock["condition_rules_sha256"],
        "source_manifest_sha256": _hash((root / "locks/source-user-molecule-files.sha256.json").read_bytes()),
        "array_identities": {"physical_overlap": ids["overlap"], "physical_hcore": ids["hcore"],
            "physical_eri": ids["eri"], "ordinary_density": ids["density"],
            "grid_coords": ids["grid_coords"], "grid_weights": ids["grid_weights"]},
        "descriptors_sha256": descriptor_identity(descriptors),
        "nuclear_repulsion_hartree": receipt["nuclear_repulsion_hartree"],
        "execution_kind": execution_kind, "initialization_policy": initialization_policy,
        "maximum_evaluations": maximum_evaluations,
        "preparation_receipt_canonical_sha256": _hash(_canonical(receipt)),
        "source_provenance": provenance,
        "source_provenance_kind": "LOCAL_FILE_BYTE_BINDING_NOT_AUTHENTICATION",
        "preparation_scope": "FIXED_PILOT_ETHENE_CACHED_METADATA_ONLY",
        "scientific_execution_authorized": False,
        "scientific_process_budget_status": "NOT_FROZEN_BY_PREPARATION"}
    kwargs = {"runtime_root": root, "science_root": science, "mean_field": context.mean_field,
        "physical_overlap": arrays["overlap"], "physical_hcore": arrays["hcore"], "physical_eri": arrays["eri"],
        "ordinary_density": arrays["density"], "descriptors": descriptors, "request_bytes": bundle["request_bytes"],
        "profile_path": profile_path, "contract": contract,
        "nuclear_repulsion": receipt["nuclear_repulsion_hartree"], "exact_exchange_fraction": .2}
    return {"contract": contract, "mapping_receipt": receipt, "bridge_kwargs": kwargs,
            "scientific_execution": "NOT_EXECUTED", "scientific_execution_authorized": False,
            "production_activation": False}
