"""Prepared-data bridge for the isolated residual engineering candidate.

The caller supplies already frozen integrals, grids and ordinary density.
Nothing here builds a molecule, integral, grid, ordinary SCF or public service.
Identity checks bind local bytes and environment declarations; they do not
authenticate a molecular engine or approve its scientific interpretation.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import inspect
import json
import math
from numbers import Real
import os
from pathlib import Path
import re
import time

import numpy as np
from scipy.linalg import eigh

from . import residual_candidate
from .input import strict_json
from .preflight import verify_source


SCIENCE_COMMIT = "cc7437901119e71ef7945a12813c021c383e7648"
SCIENCE_BASELINE_COMMIT = "28511f3d84fa65707a107cde1e8121a7b4334ecb"
INITIALIZATION_GAP_MINIMUM_HARTREE = 1e-6
BRIDGE_ID = "P09_PREPARED_RESIDUAL_BRIDGE_ENGINEERING_V1"
_POLICIES = {"REQUIRE_EXISTING_MASKED_PROJECTOR",
             "FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0"}
_PROFILES = {"pilot-b3lypg-sto3g-grid2-v1.json",
             "research-b3lypg-631gd-grid3-v1.json"}
_PROFILE_BYTE_IDENTITIES = {
    "pilot-b3lypg-sto3g-grid2-v1.json": {
        "18bd594a8b606ef2c90db4390243155031035cd98fbe72dfc2e9367aeadce2e9",
        "c3359c80f2b292c14875335b8e14a22e37f35858581402b0b47e0f20c6884f45"},
    "research-b3lypg-631gd-grid3-v1.json": {
        "65839a55949e196b79d03fdd8f7b7da81ff3d36eb1a6d68d84766dce7caf62b9",
        "257b7578569584e46b2eef4fd48a5fbc965e87b5f7d9a989433f3a187a590f8d"},
}
_COMPONENTS = ("one_electron_energy", "coulomb_energy", "exact_exchange_energy",
               "semilocal_xc_energy", "nuclear_repulsion")


class BridgeRefusal(ValueError):
    def __init__(self, reason, detail):
        self.reason, self.detail = reason, detail
        super().__init__(detail)


def _refuse(reason, detail):
    raise BridgeRefusal(reason, detail)


def _array(value, name):
    raw = np.asarray(value)
    if raw.dtype.kind not in "iuf" or not raw.size:
        _refuse("INVALID_REAL_ARRAY", name + " must be a nonempty real nonboolean array")
    checked = np.asarray(raw, dtype=np.float64)
    if not np.isfinite(checked).all():
        _refuse("NONFINITE_ARRAY", name + " must be finite")
    return checked


def array_identity(value):
    """Shape plus SHA of canonical C-order little-endian binary64 bytes.

    This follows the existing independent-reference array format, distinct
    from residual_candidate.density_id's domain-separated density hash.
    """
    array = np.ascontiguousarray(_array(value, "Array"), dtype="<f8")
    return {"shape": list(array.shape), "dtype": "<f8", "order": "C",
            "sha256": hashlib.sha256(array.tobytes(order="C")).hexdigest()}


def descriptor_identity(descriptors):
    items = []
    for descriptor in tuple(descriptors):
        kind, fragment = getattr(descriptor, "kind", None), getattr(descriptor, "fragment", None)
        if (not isinstance(kind, str) or kind not in {"sigma", "pi"} or
                (kind == "sigma" and fragment is not None) or
                (kind == "pi" and (not isinstance(fragment, str) or fragment not in {"A", "B"}))):
            _refuse("INVALID_DESCRIPTOR", "Use source sigma or pi-A/pi-B AO descriptors")
        items.append({"kind": kind, "fragment": fragment})
    if not items:
        _refuse("INVALID_DESCRIPTOR", "At least one AO descriptor required")
    encoded = json.dumps(items, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _scalar(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or not math.isfinite(value):
        _refuse("INVALID_FINITE_SCALAR", name + " must be a finite real nonboolean scalar")
    return float(value)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class PreparedResidualBridge:
    """Single-use, budgeted bridge bound to explicit prepared-data identities.

    ENGINEERING_FAKE means the caller's nr_rks is a deterministic test double;
    PREPARED_MOLECULAR_DIAGNOSTIC still requires a separately authorized,
    resource-bounded external process. Neither activates production Compute.
    """
    def __init__(self, *, runtime_root, science_root, mean_field,
                 physical_overlap, physical_hcore, physical_eri, ordinary_density,
                 descriptors, request_bytes, profile_path, contract,
                 nuclear_repulsion, exact_exchange_fraction=0.2,
                 eri_mode="COPY_MASK", optimize_eri_contractions=True):
        self.runtime_root, self.science_root = Path(runtime_root).resolve(), Path(science_root).resolve()
        self.mean_field = mean_field
        self.contract = copy.deepcopy(contract)
        self.ledger, self._operators = [], {}
        self._used = False
        self._settled = False
        if not isinstance(contract, dict):
            _refuse("INVALID_CONTRACT", "Explicit dictionary contract required")
        try:
            self._contract_identity = json.dumps(self.contract, sort_keys=True, separators=(",", ":"), allow_nan=False)
        except (ValueError, TypeError) as error:
            _refuse("INVALID_CONTRACT", "Identity contract must be finite JSON data: " + str(error))
        self.execution_kind = contract.get("execution_kind")
        if self.execution_kind not in {"ENGINEERING_FAKE", "PREPARED_MOLECULAR_DIAGNOSTIC"}:
            _refuse("INVALID_EXECUTION_KIND", "Explicit fake or prepared diagnostic execution kind required")
        self.initialization_policy = contract.get("initialization_policy")
        if self.initialization_policy not in _POLICIES:
            _refuse("INITIALIZATION_POLICY_REQUIRED", "No implicit initialization policy is allowed")
        self.limit = contract.get("maximum_evaluations")
        if type(self.limit) is not int or not 2 <= self.limit <= 201:
            _refuse("INVALID_EVALUATION_BUDGET", "Global callback budget must be an integer in [2, 201]")
        if type(optimize_eri_contractions) is not bool or eri_mode not in {"COPY_MASK", "INPLACE_OWNED"}:
            _refuse("INVALID_ERI_MODE", "Use COPY_MASK or INPLACE_OWNED and an explicit boolean optimize flag")
        self.eri_mode, self.optimize = eri_mode, optimize_eri_contractions
        self.nuclear = _scalar(nuclear_repulsion, "Nuclear repulsion")
        cached_nuclear = _scalar(contract.get("nuclear_repulsion_hartree"), "Frozen ordinary-record nuclear repulsion")
        if abs(cached_nuclear-self.nuclear) > 1e-9:
            _refuse("NUCLEAR_REPULSION_MISMATCH", "Supplied nuclear repulsion differs from the frozen ordinary-record value")
        self.hybrid = _scalar(exact_exchange_fraction, "Exact-exchange fraction")
        if self.hybrid != 0.2:
            _refuse("HYBRID_PROFILE_MISMATCH", "Locked B3LYPG requires the supplied exact-exchange fraction 0.2")
        if not isinstance(request_bytes, bytes):
            _refuse("REQUEST_BYTES_REQUIRED", "Original request bytes required")
        self.request_bytes = request_bytes
        self.profile_path = Path(profile_path).resolve()
        permitted = self.runtime_root / "profiles/user-molecule"
        if self.profile_path.parent != permitted or self.profile_path.name not in _PROFILES:
            _refuse("PROFILE_PATH_UNSUPPORTED", "Use one of the two existing locked profile paths")
        if _sha(self.profile_path) not in _PROFILE_BYTE_IDENTITIES[self.profile_path.name]:
            _refuse("PROFILE_BYTES_NOT_FROZEN", "Profile must match one of this file's separately verified LF/CRLF frozen identities")
        self.rules_path = self.science_root / "configs/qm/p09_exchange_integral_classes_v0.1.yaml"
        self.manifest_path = self.runtime_root / "locks/source-user-molecule-files.sha256.json"
        self.lock_path = self.runtime_root / "locks/source.user-molecule.lock.json"
        try:
            lock = verify_source(self.runtime_root, self.science_root)
            self.source_manifest = strict_json(self.manifest_path.read_bytes())
            self.profile = strict_json(self.profile_path.read_bytes())
            self.source_lock_sha256 = _sha(self.lock_path)
        except (ValueError, OSError) as error:
            _refuse("SOURCE_OR_PROFILE_REFUSED", str(error))
        for name, expected in (("science_commit", SCIENCE_COMMIT),
                               ("science_baseline_commit", SCIENCE_BASELINE_COMMIT)):
            if contract.get(name) != expected:
                _refuse("SOURCE_COMMIT_MISMATCH", name + " must retain the frozen identity")
        if lock.get("source_commit") != SCIENCE_COMMIT or lock.get("baseline_commit") != SCIENCE_BASELINE_COMMIT:
            _refuse("SOURCE_COMMIT_MISMATCH", "Actual source lock is not the frozen adapter/baseline")
        for name, pattern, environment in (
                ("runtime_test_commit", r"[0-9a-f]{40}", "AI4ORGCHEM_RUNTIME_TEST_COMMIT"),
                ("image_id", r"sha256:[0-9a-f]{64}", "AI4ORGCHEM_IMAGE_ID"),
                ("image_build_commit", r"[0-9a-f]{40}", "AI4ORGCHEM_IMAGE_BUILD_COMMIT")):
            value = contract.get(name)
            if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
                _refuse("INVALID_EXECUTION_IDENTITY", name + " is missing or malformed")
            if os.environ.get(environment) != value:
                _refuse("EXECUTION_IDENTITY_MISMATCH", environment + " differs or is unavailable")
        self._environment = {key: os.environ[key] for key in
            ("AI4ORGCHEM_RUNTIME_TEST_COMMIT", "AI4ORGCHEM_IMAGE_ID", "AI4ORGCHEM_IMAGE_BUILD_COMMIT")}
        for name, actual in (("request_sha256", hashlib.sha256(request_bytes).hexdigest()),
                             ("profile_sha256", _sha(self.profile_path)),
                             ("condition_rules_sha256", _sha(self.rules_path)),
                             ("source_manifest_sha256", _sha(self.manifest_path))):
            if contract.get(name) != actual:
                _refuse("IDENTITY_HASH_MISMATCH", name + " differs from actual prepared bytes")
        if contract["condition_rules_sha256"] != lock.get("condition_rules_sha256"):
            _refuse("RULE_LOCK_MISMATCH", "Rule bytes must match the scientific source lock")
        if self.profile.get("compute_enabled") is not False or self.profile.get("xc") != "B3LYPG":
            _refuse("PROFILE_STATE_MISMATCH", "The locked B3LYPG production profile must remain disabled")
        try:
            dependencies = {name: importlib.metadata.version(name) for name in ("pyscf", "numpy", "scipy")}
        except importlib.metadata.PackageNotFoundError as error:
            _refuse("DEPENDENCY_VERSION_UNAVAILABLE", str(error))
        if dependencies != self.profile.get("expected_dependencies"):
            _refuse("DEPENDENCY_VERSION_MISMATCH", "Actual dependencies differ from the frozen profile")
        self.dependencies = dependencies
        self.descriptors = tuple(descriptors)
        if descriptor_identity(self.descriptors) != contract.get("descriptors_sha256"):
            _refuse("DESCRIPTOR_IDENTITY_MISMATCH", "AO descriptor identities differ")
        self.n = len(self.descriptors)
        molecule = mean_field.mol
        self.electrons = molecule.nelectron
        if (type(self.electrons) is not int or self.electrons < 2 or self.electrons % 2 or
                self.electrons >= 2*self.n or molecule.spin != 0 or molecule.cart is not False):
            _refuse("UNSUPPORTED_OCCUPATION", "Require spherical global closed-shell 2/0 occupation with a virtual orbital")
        if (self.electrons//2)*(self.n-self.electrons//2) > residual_candidate.MAXIMUM_ROTATION_VARIABLES:
            _refuse("ROTATION_DIMENSION_UNSUPPORTED", "This engineering candidate permits at most 64 occupied-virtual variables")
        self._caller_arrays = {"physical_overlap": physical_overlap, "physical_hcore": physical_hcore,
                               "physical_eri": physical_eri, "ordinary_density": ordinary_density}
        self._caller_identities = {}
        self.arrays = {}
        identities = contract.get("array_identities", {})
        for name, supplied in self._caller_arrays.items():
            value = _array(supplied, name)
            expected_shape = (self.n,)*4 if name == "physical_eri" else (self.n, self.n)
            if value.shape != expected_shape:
                _refuse("ARRAY_DIMENSION_MISMATCH", name + " dimensions differ from the AO descriptors")
            actual = array_identity(value)
            if actual != identities.get(name):
                _refuse("ARRAY_IDENTITY_MISMATCH", name + " differs from the contract")
            self._caller_identities[name] = actual
            self.arrays[name] = value.copy()
        for name in ("physical_overlap", "physical_hcore", "ordinary_density"):
            if not np.allclose(self.arrays[name], self.arrays[name].T, rtol=0, atol=1e-12):
                _refuse("NONSYMMETRIC_MATRIX", name + " must be symmetric")
        eri = self.arrays["physical_eri"]
        for axes in ((1, 0, 2, 3), (0, 1, 3, 2), (2, 3, 0, 1)):
            if not np.allclose(eri, eri.transpose(axes), rtol=0, atol=1e-12):
                _refuse("ERI_SYMMETRY_MISMATCH", "Prepared real ERI must retain chemist permutation symmetry")
        self._grid_identities = {}
        for name in ("coords", "weights"):
            value = getattr(mean_field.grids, name, None)
            actual = array_identity(value)
            if actual != identities.get("grid_"+name):
                _refuse("GRID_IDENTITY_MISMATCH", "Prepared grid " + name + " differs")
            self._grid_identities[name] = actual
        coords, weights = np.asarray(mean_field.grids.coords), np.asarray(mean_field.grids.weights)
        if coords.ndim != 2 or coords.shape[1] != 3 or weights.shape != (len(coords),):
            _refuse("GRID_DIMENSION_MISMATCH", "Frozen grid requires matching (npoint,3) coordinates and weights")
        if (mean_field.xc != self.profile["xc"] or
                mean_field.max_memory != self.profile["ordinary"]["max_memory_mb"] or
                mean_field.grids.level != self.profile["grid"]["level"]):
            _refuse("MEAN_FIELD_PROFILE_MISMATCH", "Prepared XC, grid level or max_memory differs from the locked profile")
        self._settings_snapshot = self._settings()
        if self.execution_kind == "PREPARED_MOLECULAR_DIAGNOSTIC":
            required = ("charge", "basis", "_atom")
            if any(not hasattr(molecule, name) for name in required):
                _refuse("MOLECULAR_METADATA_UNVERIFIED", "Prepared molecular diagnostics require cached charge/basis/atom geometry metadata")
            if molecule.charge != 0 or molecule.basis != self.profile["basis"]:
                _refuse("MOLECULAR_METADATA_MISMATCH", "Cached molecular charge/basis differs from the locked neutral profile")
            for name in ("prune", "radi_method", "radii_adjust", "atomic_radii", "becke_scheme", "alignment", "atom_grid"):
                if not hasattr(mean_field.grids, name):
                    _refuse("MOLECULAR_METADATA_UNVERIFIED", "Prepared molecular grid settings missing: " + name)
            from pyscf.dft import gen_grid, radi
            for name, expected in (("prune", gen_grid.nwchem_prune), ("radi_method", radi.treutler),
                                   ("radii_adjust", radi.treutler_atomic_radii_adjust),
                                   ("becke_scheme", gen_grid.original_becke)):
                if getattr(mean_field.grids, name) is not expected:
                    _refuse("MOLECULAR_GRID_PROFILE_MISMATCH", "Actual grid algorithm differs from locked profile: " + name)
            if (not np.array_equal(mean_field.grids.atomic_radii, radi.BRAGG_RADII) or
                    mean_field.grids.alignment != 8 or mean_field.grids.atom_grid != {}):
                _refuse("MOLECULAR_GRID_PROFILE_MISMATCH", "Actual radii, alignment or atom_grid differ from locked profile")
        # Import only the supplied, fully checked source. Imported modules may
        # already be cached, so their actual file paths/bytes are checked too.
        from ai4orgchem.qm import p09_conditional_scf, p09_ao_classification, p09_energy_assembly, p09_eri_mask
        self._modules = (p09_conditional_scf, p09_ao_classification, p09_energy_assembly, p09_eri_mask)
        self._module_paths = []
        for module in self._modules:
            path = Path(inspect.getfile(module)).resolve()
            if not path.is_relative_to(self.science_root):
                _refuse("LOADED_SOURCE_PATH_MISMATCH", "Loaded source module is outside the supplied frozen tree")
            relative = path.relative_to(self.science_root).as_posix()
            if self.source_manifest.get(relative) != _sha(path):
                _refuse("LOADED_SOURCE_BYTE_MISMATCH", "Loaded source module bytes differ: " + relative)
            self._module_paths.append(path)
        self._source_evaluate = p09_conditional_scf._evaluate_density
        self._source_evaluate_id = self._source_evaluate
        self._source_bindings = ((p09_conditional_scf, "restricted_jk", p09_conditional_scf.restricted_jk),
            (p09_conditional_scf, "apply_interfragment_pi_matrix_mask", p09_conditional_scf.apply_interfragment_pi_matrix_mask),
            (p09_ao_classification, "interfragment_pi_delete_mask", p09_ao_classification.interfragment_pi_delete_mask))
        import yaml
        self.entries = yaml.safe_load(self.rules_path.read_bytes())["exchange_integral_classes"]
        if [entry.get("id") for entry in self.entries] != [f"X{i:02d}" for i in range(1, 16)]:
            _refuse("RULE_CLASSES_MISMATCH", "Exactly fifteen frozen ordered ERI classes required")
        self.mask = p09_ao_classification.interfragment_pi_delete_mask(self.descriptors)
        self.overlap = p09_ao_classification.apply_interfragment_pi_matrix_mask(self.arrays["physical_overlap"], self.descriptors)
        self.hcore = p09_ao_classification.apply_interfragment_pi_matrix_mask(self.arrays["physical_hcore"], self.descriptors)
        if float(np.linalg.eigvalsh(self.overlap).min()) <= 0:
            _refuse("MASKED_OVERLAP_NOT_POSITIVE", "No masked metric repair is permitted")
        if self.eri_mode == "INPLACE_OWNED":
            self.masked_eri = self.arrays["physical_eri"].copy()
            self.deleted_eri_count = p09_energy_assembly.apply_eri_tensor_mask_inplace_by_category(
                self.masked_eri, self.descriptors, self.entries)
        else:
            self.masked_eri, deleted = p09_energy_assembly.apply_eri_tensor_mask(
                self.arrays["physical_eri"], self.descriptors, self.entries)
            self.deleted_eri_count = int(np.count_nonzero(deleted))
        for array in (*self.arrays.values(), self.overlap, self.hcore, self.masked_eri, self.mask):
            array.setflags(write=False)
        self._owned_identities = {name: array_identity(value) for name, value in self.arrays.items()}
        self._owned_identities.update({"masked_overlap": array_identity(self.overlap),
            "masked_hcore": array_identity(self.hcore), "masked_eri": array_identity(self.masked_eri)})
        self._mask_identity = hashlib.sha256(self.mask.tobytes()).hexdigest()
        self._entries_identity = json.dumps(self.entries, sort_keys=True, separators=(",", ":"), allow_nan=False)
        self._bridge_settings = (self.nuclear, self.hybrid, self.optimize, self.electrons, self.n,
                                 self.eri_mode, self.execution_kind, self.initialization_policy, self.limit)
        self._assert_frozen()

    def _settings(self):
        mf, mol, grids = self.mean_field, self.mean_field.mol, self.mean_field.grids
        values = {"xc": mf.xc, "max_memory": mf.max_memory, "spin": mol.spin,
                  "cart": mol.cart, "nelectron": mol.nelectron,
                  "nr_rks": mf._numint.nr_rks, "energy_nuc": mol.energy_nuc}
        for name in ("charge", "basis", "_atom", "_basis", "ecp", "symmetry"):
            if hasattr(mol, name):
                values["mol_"+name] = copy.deepcopy(getattr(mol, name))
        for name in ("level", "prune", "radi_method", "radii_adjust", "atomic_radii",
                     "becke_scheme", "alignment", "atom_grid"):
            if hasattr(grids, name):
                value = getattr(grids, name)
                values["grid_"+name] = array_identity(value) if isinstance(value, np.ndarray) else copy.deepcopy(value)
        return values

    def _assert_frozen(self):
        if json.dumps(self.contract, sort_keys=True, separators=(",", ":"), allow_nan=False) != self._contract_identity:
            _refuse("CONTRACT_CHANGED", "The prepared execution/identity contract changed")
        if hashlib.sha256(self.request_bytes).hexdigest() != self.contract["request_sha256"]:
            _refuse("REQUEST_BYTES_CHANGED", "The prepared request bytes changed")
        for key, value in self._environment.items():
            if os.environ.get(key) != value:
                _refuse("EXECUTION_IDENTITY_CHANGED", "Execution environment binding changed: " + key)
        for path, field in ((self.profile_path, "profile_sha256"), (self.rules_path, "condition_rules_sha256"),
                            (self.manifest_path, "source_manifest_sha256")):
            if _sha(path) != self.contract[field]:
                _refuse("FROZEN_BYTES_CHANGED", "Frozen file changed: " + str(path))
        if _sha(self.lock_path) != self.source_lock_sha256:
            _refuse("FROZEN_BYTES_CHANGED", "Scientific source lock changed")
        # Retain the exact frozen file set, including unseen helper modules.
        try:
            verify_source(self.runtime_root, self.science_root)
        except (ValueError, OSError) as error:
            _refuse("FROZEN_SOURCE_CHANGED", str(error))
        for name, value in self._caller_arrays.items():
            if array_identity(value) != self._caller_identities[name]:
                _refuse("CALLER_ARRAY_CHANGED", "Caller-owned prepared array changed: " + name)
        for name, identity in self._grid_identities.items():
            if array_identity(getattr(self.mean_field.grids, name, None)) != identity:
                _refuse("FROZEN_GRID_CHANGED", "Original grid changed: " + name)
        if self._settings() != self._settings_snapshot:
            _refuse("FROZEN_SETTINGS_CHANGED", "Prepared mean-field/grid settings or evaluator changed")
        if descriptor_identity(self.descriptors) != self.contract["descriptors_sha256"]:
            _refuse("DESCRIPTORS_CHANGED", "AO descriptors changed")
        if (self._modules[0]._evaluate_density is not self._source_evaluate_id or
                self._source_evaluate is not self._source_evaluate_id):
            _refuse("SOURCE_EVALUATOR_CHANGED", "Loaded frozen evaluator was replaced")
        for module, name, function in self._source_bindings:
            if getattr(module, name) is not function:
                _refuse("SOURCE_HELPER_CHANGED", "Loaded frozen source helper was replaced: " + name)
        if (self.nuclear, self.hybrid, self.optimize, self.electrons, self.n, self.eri_mode,
                self.execution_kind, self.initialization_policy, self.limit) != self._bridge_settings:
            _refuse("BRIDGE_SETTINGS_CHANGED", "Prepared bridge configuration changed")
        if hashlib.sha256(self.mask.tobytes()).hexdigest() != self._mask_identity:
            _refuse("OWNED_MASK_CHANGED", "Prepared matrix deletion mask changed")
        if json.dumps(self.entries, sort_keys=True, separators=(",", ":"), allow_nan=False) != self._entries_identity:
            _refuse("RULE_ENTRIES_CHANGED", "Prepared frozen rule entries changed")
        for name, value in self.arrays.items():
            if array_identity(value) != self._owned_identities[name]:
                _refuse("OWNED_ARRAY_CHANGED", "Bridge-owned prepared array changed: " + name)
        for name, value in (("masked_overlap", self.overlap), ("masked_hcore", self.hcore),
                            ("masked_eri", self.masked_eri)):
            if array_identity(value) != self._owned_identities[name]:
                _refuse("OWNED_ARRAY_CHANGED", "Bridge-owned mask output changed: " + name)

    def evaluate(self, density, phase="SOLVER_CALLBACK"):
        """One accounted frozen-operator call; failures consume their attempt."""
        if self._settled:
            _refuse("BRIDGE_ALREADY_SETTLED", "A settled run cannot acquire unregistered additional evaluations")
        if len(self.ledger) >= self.limit:
            _refuse("EVALUATION_BUDGET_EXHAUSTED", "No callback invoked beyond the global hard ceiling")
        self._assert_frozen()
        argument = _array(density, "Requested density").copy()
        if argument.shape != (self.n, self.n) or not np.allclose(argument, argument.T, rtol=0, atol=1e-12):
            _refuse("INVALID_REQUESTED_DENSITY", "Requested density must be a same-size symmetric real matrix")
        identity = residual_candidate.density_id(argument)
        row = {"global_evaluation_count": len(self.ledger)+1, "phase": phase,
               "density_id": identity, "status": "STARTED", "execution_kind": self.execution_kind,
               "source_callback_attempted": True}
        self.ledger.append(row)
        started = time.monotonic()
        try:
            value = self._source_evaluate(mean_field=self.mean_field, density=argument,
                masked_hcore=self.hcore, masked_overlap=self.overlap,
                physical_overlap=self.arrays["physical_overlap"], masked_eri=self.masked_eri,
                descriptors=self.descriptors, exact_exchange_fraction=self.hybrid,
                optimize_eri_contractions=self.optimize)
            if residual_candidate.density_id(argument) != identity:
                _refuse("REQUESTED_DENSITY_MODIFIED", "Frozen evaluator modified the density argument")
            self._assert_frozen()
            if not isinstance(value, dict):
                _refuse("INVALID_EVALUATOR_RESULT", "Frozen evaluator must return its energy/component dictionary")
            value = dict(value)
            fock = _array(value.get("fock"), "Conditional Fock").copy()
            if fock.shape != argument.shape or not np.allclose(fock, fock.T, rtol=0, atol=1e-12):
                _refuse("INVALID_CONDITIONAL_FOCK", "True conditional Fock dimensions or symmetry differ")
            if float(np.max(np.abs(fock[self.mask]), initial=0)) > 1e-12:
                _refuse("CONDITIONAL_FOCK_MASK_FAILED", "Frozen conditional Fock violates its original deletion mask")
            value["nuclear_repulsion"] = self.nuclear
            for name in (*_COMPONENTS, "total_energy", "electronic_energy", "grid_electron_count",
                         "masked_metric_electron_count", "physical_metric_electron_count"):
                value[name] = _scalar(value.get(name), name)
            closure = abs(sum(value[name] for name in _COMPONENTS)-value["total_energy"])
            if closure > 1e-9 or abs(value["electronic_energy"]+self.nuclear-value["total_energy"]) > 1e-9:
                _refuse("ENERGY_COMPONENT_CLOSURE_FAILED", "Returned frozen energy fails the original five-component closure")
            fock_id = residual_candidate.density_id(fock)
            previous = self._operators.get(identity)
            row.update(fock_id=fock_id, previous_same_density_fock_id=previous,
                       same_density_operator_reproducible=None if previous is None else previous == fock_id)
            if previous is not None and previous != fock_id:
                _refuse("NONREPRODUCIBLE_SAME_DENSITY_OPERATOR", "The same density returned different true-F bytes")
            self._operators[identity] = fock_id
            value.update(fock=fock, density_id=identity, operator_source=residual_candidate.OPERATOR_SOURCE)
            row.update(status="VALIDATED", total_energy_hartree=value["total_energy"],
                       energy_component_closure_hartree=closure,
                       operator_source=residual_candidate.OPERATOR_SOURCE)
            return value
        except BridgeRefusal as error:
            row.update(status="REFUSED", reason=error.reason, detail=error.detail)
            try:
                self._assert_frozen()
            except Exception as mutation:
                row["post_failure_frozen_state_refusal"] = {
                    "reason": getattr(mutation, "reason", type(mutation).__name__),
                    "detail": str(mutation)}
            raise
        except Exception as error:
            row.update(status="REFUSED", reason="FROZEN_EVALUATOR_FAILED",
                       exception_type=type(error).__name__, detail=str(error))
            try:
                self._assert_frozen()
            except Exception as mutation:
                row["post_failure_frozen_state_refusal"] = {
                    "reason": getattr(mutation, "reason", type(mutation).__name__),
                    "detail": str(mutation)}
            raise BridgeRefusal("FROZEN_EVALUATOR_FAILED", type(error).__name__+": "+str(error)) from error
        finally:
            row["elapsed_seconds"] = time.monotonic()-started

    def _projector_metrics(self, density):
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            values, vectors = np.linalg.eigh(self.overlap)
            half = (vectors*np.sqrt(values)) @ vectors.T
            p = .5*half @ density @ half
            result = {"density_id": residual_candidate.density_id(density),
                "masked_metric_electron_count": float(np.trace(self.overlap @ density)),
                "projector_trace": float(np.trace(p)),
                "projector_idempotency_frobenius": float(np.linalg.norm(p @ p-p)),
                "physical_metric_electron_count": float(np.trace(self.arrays["physical_overlap"] @ density))}
        if not np.isfinite([result[key] for key in result if key != "density_id"]).all():
            _refuse("NONFINITE_INITIALIZATION_METRICS", "Masked initialization diagnostics must be finite")
        return result

    def run(self, *, maximum_iterations=8, finite_difference_step=1e-5,
            trust_radius=0.25, maximum_backtracks=8):
        """Single attempt including initialization and solver's remaining budget."""
        if self._used:
            _refuse("BRIDGE_ALREADY_USED", "No automatic retry or budget reset is permitted")
        self._used = True
        initialized = {"policy": self.initialization_policy,
                       "ordinary_density_id": residual_candidate.density_id(self.arrays["ordinary_density"]),
                       "gap_minimum_hartree": INITIALIZATION_GAP_MINIMUM_HARTREE,
                       "status": "NOT_EXECUTED", "evaluation_count_before": len(self.ledger)}
        solved, failure, reason = None, None, "NOT_EXECUTED"
        try:
            for name, value in (("maximum_iterations", maximum_iterations),
                                ("maximum_backtracks", maximum_backtracks)):
                if type(value) is not int or not 1 <= value <= 100:
                    _refuse("INVALID_SOLVER_CONFIGURATION", name + " must be an integer in [1, 100]")
            fd = _scalar(finite_difference_step, "Finite-difference step")
            radius = _scalar(trust_radius, "Trust radius")
            if not 0 < fd <= radius <= 1:
                _refuse("INVALID_SOLVER_CONFIGURATION", "Require 0 < finite_difference_step <= trust_radius <= 1")
            self._assert_frozen()
            d0 = self.arrays["ordinary_density"].copy()
            initialized["ordinary_density_metrics"] = self._projector_metrics(d0)
            if self.initialization_policy == "REQUIRE_EXISTING_MASKED_PROJECTOR":
                metrics = initialized["ordinary_density_metrics"]
                if (metrics["projector_idempotency_frobenius"] > 1e-10 or
                        abs(metrics["projector_trace"]-self.electrons/2) > 1e-10):
                    _refuse("INITIAL_DENSITY_NOT_MASKED_PROJECTOR", "Ordinary density is not on the masked 2/0 manifold; no projection allowed")
                initial = d0
                initialized["raw_aufbau_spectrum_hartree"] = None
                initialized["raw_aufbau_gap_hartree"] = None
            else:
                evaluated = self.evaluate(d0, "INITIALIZE_AT_ORDINARY_D0")
                spectrum, coefficients = eigh(evaluated["fock"], self.overlap, check_finite=True)
                occupied = self.electrons//2
                gap = float(spectrum[occupied]-spectrum[occupied-1])
                initialized.update(raw_aufbau_spectrum_hartree=spectrum.tolist(), raw_aufbau_gap_hartree=gap,
                                   raw_aufbau_fock_id=residual_candidate.density_id(evaluated["fock"]),
                                   raw_aufbau_spectrum_identity=array_identity(spectrum))
                if not np.isfinite(spectrum).all() or not np.isfinite(coefficients).all() or not np.isfinite(gap):
                    _refuse("NONFINITE_INITIAL_AUFBAU", "Raw initialization eigensystem must be finite")
                if gap < INITIALIZATION_GAP_MINIMUM_HARTREE:
                    _refuse("ROOT_AMBIGUOUS_INITIALIZATION", "Initial raw global Aufbau boundary fails the fixed engineering admission gap")
                initial = 2*coefficients[:, :occupied] @ coefficients[:, :occupied].T
                initial = (initial+initial.T)*.5
            initialized.update(status="PREPARED_ENGINEERING_INITIALIZATION",
                initial_density_id=residual_candidate.density_id(initial),
                initial_density_metrics=self._projector_metrics(initial),
                evaluation_count_after=len(self.ledger),
                ordinary_density_preserved=array_identity(self._caller_arrays["ordinary_density"]) == self._caller_identities["ordinary_density"])
            remaining = self.limit-len(self.ledger)
            if remaining < 1:
                _refuse("EVALUATION_BUDGET_EXHAUSTED", "Initialization exhausted the entire global budget")
            solver_offset = len(self.ledger)
            solved = residual_candidate.solve_residual_candidate(initial_density=initial,
                overlap=self.overlap, electrons=self.electrons, evaluate=self.evaluate,
                maximum_iterations=maximum_iterations, maximum_evaluations=remaining,
                finite_difference_step=finite_difference_step, trust_radius=trust_radius,
                maximum_backtracks=maximum_backtracks, matrix_delete_mask=self.mask)
            for index, inner in enumerate(solved["evaluation_ledger"]):
                if solver_offset+index < len(self.ledger):
                    self.ledger[solver_offset+index]["solver_evaluation_count"] = inner["evaluation_count"]
                    self.ledger[solver_offset+index]["solver_phase"] = inner["phase"]
            reason = solved["stop_reason"]
            self._assert_frozen()
        except BridgeRefusal as error:
            reason, failure = error.reason, {"reason": error.reason, "detail": error.detail}
            if initialized["status"] == "NOT_EXECUTED":
                initialized["status"] = "REFUSED"
        except (ValueError, TypeError, OSError, np.linalg.LinAlgError, FloatingPointError, OverflowError) as error:
            reason, failure = "INITIALIZATION_OR_SOLVER_REFUSED", {
                "reason": "INITIALIZATION_OR_SOLVER_REFUSED", "exception_type": type(error).__name__, "detail": str(error)}
            if initialized["status"] == "NOT_EXECUTED":
                initialized["status"] = "REFUSED"
        finally:
            self._settled = True
        initialized["evaluation_count_after"] = initialized.get("evaluation_count_after", len(self.ledger))
        real_attempts = len(self.ledger) if self.execution_kind == "PREPARED_MOLECULAR_DIAGNOSTIC" else 0
        last_refusal = next((copy.deepcopy(row) for row in reversed(self.ledger) if row["status"] == "REFUSED"), None)
        return {"bridge_id": BRIDGE_ID, "status": "ENGINEERING_CANDIDATE", "stop_reason": reason,
                "failure": failure, "last_bridge_refusal": last_refusal, "execution_kind": self.execution_kind,
                "identity_contract": copy.deepcopy(self.contract), "initialization": initialized,
                "solver_result": solved, "bridge_ledger": copy.deepcopy(self.ledger),
                "global_evaluation_count": len(self.ledger), "global_evaluation_limit": self.limit,
                "eri_mode": self.eri_mode, "optimize_eri_contractions": self.optimize,
                "deleted_eri_count": self.deleted_eri_count, "total_eri_count": self.n**4,
                "identity_evidence_kind": "LOCAL_BYTES_AND_ENVIRONMENT_DECLARATIONS_NOT_AUTHENTICATION",
                "real_molecular_operator_attempts": real_attempts,
                "molecular_execution": "EXECUTED_DIAGNOSTIC_UNQUALIFIED" if real_attempts else "NOT_EXECUTED",
                "molecular_metadata_status": "BOUND_CACHED_METADATA_NOT_AUTHENTICATED" if self.execution_kind == "PREPARED_MOLECULAR_DIAGNOSTIC" else "TEST_DOUBLE_NOT_MOLECULAR_EVIDENCE",
                "production_activation": False, "molecular_acceptance": "NOT_EXECUTED",
                "research_acceptance": "NOT_ACCEPTED", "method_review_status": "PENDING_REAL_REVIEW",
                "comparison_available": False, "deltas": None, "delta_hartree": None, "delta_kcal_mol": None}
