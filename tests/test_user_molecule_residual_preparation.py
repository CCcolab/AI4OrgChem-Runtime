"""Cached preparation contract tests; no molecule/SCF/grid/integral evaluation.

The molecule, density, integrals and ordinary record are explicit test doubles.
Real library grid configuration objects are reused solely as fixed settings.
The tests do not borrow the historical ordinary calculation's numeric identity.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

import numpy as np
from pyscf.dft import gen_grid, radi

from reference.user_molecule import AO
from runtime.user_molecule import residual_preparation as preparation
from runtime.user_molecule.input import InputError
from runtime.user_molecule.residual_bridge import BridgeRefusal, array_identity


ROOT = Path(__file__).resolve().parents[1]
SCIENCE = Path(os.environ.get("AI4ORGCHEM_SOURCE_ROOT", os.environ.get("AI4ORGCHEM_SOURCE", "/opt/ai4orgchem")))
EXAMPLE = ROOT / "examples/user-molecule/w05-candidates/ethene-planar-technical-v1"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha(value):
    return hashlib.sha256(value).hexdigest()


class CachedMolecule:
    """Only the three explicitly allowed query APIs read cached data."""
    def __init__(self, atoms):
        self.natm, self.nelectron, self.charge, self.spin = 6, 16, 0, 0
        self.cart, self.symmetry, self.basis, self.ecp = False, False, "sto-3g", {}
        self._basis = {"C": "SYNTHETIC_TEST_BASIS_METADATA", "H": "SYNTHETIC_TEST_METADATA"}
        self.symbols = [atom[0] for atom in atoms]
        self.coordinates = np.asarray([atom[1] for atom in atoms], dtype=float)
        self.labels = [(center, "C", orbital, component) for center in (0, 1)
            for orbital, component in (("1s", ""), ("2s", ""), ("2p", "x"), ("2p", "y"), ("2p", "z"))]
        self.labels += [(center, "H", "1s", "") for center in range(2, 6)]
        self.cached_reads = []
        self.forbidden_calls = 0

    def atom_symbols(self):
        self.cached_reads.append("atom_symbols")
        return list(self.symbols)

    def atom_coords(self, unit):
        if unit != "Angstrom":
            raise AssertionError("Explicit Angstrom query required")
        self.cached_reads.append("atom_coords:Angstrom")
        return self.coordinates.copy()

    def ao_labels(self, fmt):
        if fmt is not False:
            raise AssertionError("Raw AO labels required")
        self.cached_reads.append("ao_labels:False")
        return list(self.labels)

    def forbidden(self, *args, **kwargs):
        self.forbidden_calls += 1
        raise AssertionError("A scientific or uncached query was called")

    energy_nuc = intor = kernel = forbidden


class ResidualPreparationTests(unittest.TestCase):
    def setUp(self):
        self.prepared = preparation.load_preparation_input(runtime_root=ROOT, request_path=EXAMPLE / "request-pilot.json")
        self.bundle, self.profile = self.prepared["bundle"], self.prepared["profile"]
        self.mol = CachedMolecule(self.bundle["atoms"])
        self.arrays = {"density": np.diag([2.0]*8+[0.0]*6), "hcore": np.eye(14),
            "overlap": np.eye(14), "eri": np.zeros((14,)*4),
            "grid_coords": np.array([[0., 0., 0.], [.1, .2, .3]]), "grid_weights": np.array([1., .5])}
        grids = SimpleNamespace(coords=self.arrays["grid_coords"], weights=self.arrays["grid_weights"],
            level=2, prune=gen_grid.nwchem_prune, radi_method=radi.treutler,
            radii_adjust=radi.treutler_atomic_radii_adjust, atomic_radii=radi.BRAGG_RADII,
            becke_scheme=gen_grid.original_becke, alignment=8, atom_grid={}, build=self.mol.forbidden)
        self.mf = SimpleNamespace(mol=self.mol, grids=grids, xc="B3LYPG", small_rho_cutoff=0, nlc="",
            kernel=self.mol.forbidden, get_ovlp=self.mol.forbidden, get_hcore=self.mol.forbidden,
            _numint=SimpleNamespace(nr_rks=self.mol.forbidden, rsh_and_hybrid_coeff=self.mol.forbidden))
        for name, value in self.profile["ordinary"].items():
            setattr(self.mf, "max_memory" if name == "max_memory_mb" else name, copy.deepcopy(value))
        aos = tuple(AO("pi", "A") if index == 4 else AO("pi", "B") if index == 9 else AO("sigma") for index in range(14))
        descriptors = [{"kind": ao.kind, "fragment": ao.group} for ao in aos]
        metadata = {"nao": 14, "electron_count": 16, "ao_labels": [list(label) for label in self.mol.labels],
            "ao_descriptors": descriptors, "atom_coordinates_angstrom": self.mol.coordinates.tolist(),
            "atom_elements": self.mol.symbols, "fragments_1based": {"A": [1], "B": [2]},
            "atom_order_preserved": True, "coordinate_reorientation": False,
            "molecule_effective": {"basis": "sto-3g", "unit": "Angstrom", "charge": 0, "spin": 0,
                "cart": False, "symmetry": False, "ecp": {}},
            "basis_expansion_sha256": sha(repr(self.mol._basis).encode("utf-8")),
            "dependencies": self.profile["expected_dependencies"], "threads": 1,
            "xc_effective": {"xc": "B3LYPG", "omega": 0.0, "alpha": .2, "hybrid": .2},
            "ordinary_effective": copy.deepcopy(self.profile["ordinary"]),
            "grid_effective": dict(self.profile["grid"], small_rho_cutoff=0, nlc=""),
            "profile_id": self.profile["id"], "profile_canonical_sha256": sha(canonical(self.profile))}
        self.context = SimpleNamespace(mol=self.mol, mean_field=self.mf, aos=aos, metadata=metadata, profile=self.profile)
        self.record = {"metadata": metadata, "array_identities": {name: array_identity(value) for name, value in self.arrays.items()},
            "grid_identity": {"coords": array_identity(grids.coords), "weights": array_identity(grids.weights)}, "grid_points": 2,
            "converged": True, "qualification_tests": {"converged": True, "finite": True},
            "components_hartree": {"one_electron": 1., "coulomb": 2., "exact_exchange": -.2,
                "semilocal_xc": -.3, "nuclear_repulsion": 1.2}, "total_energy_hartree": 3.7,
            "test_record_kind": "ENGINEERING_SYNTHETIC_NOT_HISTORICAL_CALCULATION"}

    def verify(self):
        return preparation.verify_prepared_mapping(bundle=self.bundle, context=self.context,
            arrays=self.arrays, ordinary_record=self.record, profile=self.profile)

    def assert_refused(self, reason=None):
        with self.assertRaises(BridgeRefusal) as raised:
            self.verify()
        if reason is not None:
            self.assertEqual(raised.exception.reason, reason)
        self.assertEqual(self.mol.forbidden_calls, 0)

    def test_matching_cached_mapping_binds_each_array_and_no_scientific_query(self):
        before = {name: array_identity(value) for name, value in self.arrays.items()}
        receipt = self.verify()
        self.assertEqual(receipt["status"], "PASS_CACHED_MAPPING_ONLY")
        self.assertEqual(receipt["array_identities"], before)
        self.assertEqual(receipt["ao_descriptors"][4], {"kind": "pi", "fragment": "A"})
        self.assertEqual(receipt["ao_descriptors"][9], {"kind": "pi", "fragment": "B"})
        self.assertEqual(receipt["nuclear_repulsion_source"], "ordinary_record.components_hartree.nuclear_repulsion")
        self.assertEqual(self.mol.cached_reads, ["atom_symbols", "atom_coords:Angstrom", "ao_labels:False"])
        self.assertEqual({name: array_identity(value) for name, value in self.arrays.items()}, before)
        self.assertEqual(self.mol.forbidden_calls, 0)
        self.assertFalse(receipt["production_activation"])
        self.assertFalse(receipt["comparison_available"])
        self.assertEqual(receipt["molecular_acceptance"], "NOT_EXECUTED")

    def test_loader_accepts_same_bytes_in_chinese_spaced_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "输入 中文 空格"
            directory.mkdir()
            (directory / "request.json").write_bytes(self.bundle["request_bytes"])
            (directory / "molecule.xyz").write_bytes(self.bundle["xyz_bytes"])
            result = preparation.load_preparation_input(runtime_root=ROOT, request_path=directory / "request.json")
            self.assertEqual(result["bundle"]["normalized_sha256"], preparation.REQUEST_NORMALIZED_SHA256)

    def test_other_request_scope_is_refused(self):
        changed = copy.deepcopy(self.bundle["request"])
        changed["research_question"] = "New user request is outside this exact pilot fixture"
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "request.json").write_bytes(canonical(changed))
            (directory / "molecule.xyz").write_bytes(self.bundle["xyz_bytes"])
            with self.assertRaises(BridgeRefusal) as raised:
                preparation.load_preparation_input(runtime_root=ROOT, request_path=directory / "request.json")
            self.assertEqual(raised.exception.reason, "PREPARATION_FIXTURE_SCOPE_BLOCKED")

    def test_loader_reuses_path_escape_refusal(self):
        changed = copy.deepcopy(self.bundle["request"])
        changed["geometry_file"] = "../molecule.xyz"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "request.json"
            path.write_bytes(canonical(changed))
            with self.assertRaises(InputError):
                preparation.load_preparation_input(runtime_root=ROOT, request_path=path)

    def test_loader_reuses_duplicate_json_key_refusal(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "request.json"
            path.write_bytes(b'{"charge":0,"charge":0}')
            with self.assertRaises(InputError):
                preparation.load_preparation_input(runtime_root=ROOT, request_path=path)

    def test_stale_bundle_numbering_is_refused(self):
        self.bundle["atom_mapping"][0]["index_0based"] = 1
        self.assert_refused("PREPARATION_ATOM_MAPPING_MISMATCH")

    def test_cached_element_and_order_mismatch_is_refused(self):
        self.mol.symbols[0], self.mol.symbols[2] = self.mol.symbols[2], self.mol.symbols[0]
        self.assert_refused("PREPARATION_ATOM_ORDER_MISMATCH")

    def test_cached_angstrom_query_returning_bohr_is_refused(self):
        self.mol.coordinates *= 1.8897261254578281
        self.assert_refused("PREPARATION_COORDINATE_MAPPING_MISMATCH")

    def test_cached_coordinate_rotation_is_refused(self):
        self.mol.coordinates = self.mol.coordinates @ np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]])
        self.assert_refused("PREPARATION_COORDINATE_MAPPING_MISMATCH")

    def test_cached_coordinate_translation_is_refused(self):
        self.mol.coordinates[:, 0] += .1
        self.assert_refused("PREPARATION_COORDINATE_MAPPING_MISMATCH")

    def test_cached_atom_reordering_is_refused(self):
        self.mol.coordinates[[0, 1]] = self.mol.coordinates[[1, 0]]
        self.assert_refused("PREPARATION_COORDINATE_MAPPING_MISMATCH")

    def test_cached_geometry_conversion_guard_is_fixed(self):
        self.mol.coordinates[0, 0] += 5e-13
        self.assertEqual(self.verify()["coordinate_conversion_guard_angstrom"], 1e-12)
        self.mol.coordinates[0, 0] += 2e-12
        self.assert_refused("PREPARATION_COORDINATE_MAPPING_MISMATCH")

    def test_cached_molecular_configuration_mismatches_are_refused(self):
        for name, wrong in (("natm", 5), ("nelectron", 14), ("charge", 1), ("spin", 2),
                            ("cart", True), ("symmetry", True), ("basis", "6-31g(d)"), ("ecp", {"C": "bad"})):
            original = getattr(self.mol, name)
            with self.subTest(setting=name):
                setattr(self.mol, name, wrong)
                self.assert_refused("PREPARATION_MOLECULE_CONFIGURATION_MISMATCH")
                setattr(self.mol, name, original)

    def test_basis_expansion_hash_cannot_be_replaced_by_basis_name(self):
        self.mol._basis["C"] = "ALTERED_EXPANSION_SAME_NAME"
        self.assert_refused("PREPARATION_RECORDED_METADATA_MISMATCH")

    def test_cached_ao_labels_and_group_identity_are_checked(self):
        self.mol.labels[4], self.mol.labels[9] = self.mol.labels[9], self.mol.labels[4]
        self.assert_refused("PREPARATION_AO_LABEL_MISMATCH")

    def test_cached_ao_group_is_checked_independently_of_labels(self):
        aos = list(self.context.aos)
        aos[4] = AO("pi", "B")
        self.context.aos = tuple(aos)
        self.assert_refused("PREPARATION_AO_GROUP_MISMATCH")

    def test_ordinary_settings_and_xc_are_checked(self):
        self.mf.max_memory = 1024
        self.assert_refused("PREPARATION_ORDINARY_SETTINGS_MISMATCH")
        self.mf.max_memory = 512
        self.mf.xc = "PBE"
        self.assert_refused("PREPARATION_XC_SETTINGS_MISMATCH")

    def test_grid_algorithm_and_array_identity_are_checked(self):
        self.mf.grids.prune = lambda *args: None
        self.assert_refused("PREPARATION_GRID_SETTINGS_MISMATCH")
        self.mf.grids.prune = gen_grid.nwchem_prune
        self.arrays["grid_weights"][0] += .1
        self.assert_refused("PREPARATION_ARRAY_IDENTITY_MISMATCH")

    def test_ordinary_density_cannot_be_mixed_with_another_record(self):
        self.arrays["density"][0, 0] += 1e-10
        self.assert_refused("PREPARATION_ARRAY_IDENTITY_MISMATCH")

    def test_incomplete_ordinary_record_is_refused(self):
        del self.record["metadata"]["basis_expansion_sha256"]
        self.assert_refused("PREPARATION_RECORDED_METADATA_MISMATCH")

    def test_recorded_failure_or_missing_nuclear_cache_is_refused(self):
        self.record["qualification_tests"]["finite"] = False
        self.assert_refused("PREPARATION_ORDINARY_RECORD_UNQUALIFIED")
        self.record["qualification_tests"]["finite"] = True
        del self.record["components_hartree"]["nuclear_repulsion"]
        self.assert_refused("PREPARATION_MAPPING_INCOMPLETE_OR_INVALID")

    def test_existing_record_energy_closure_is_checked_without_evaluation(self):
        self.record["total_energy_hartree"] += .1
        self.assert_refused("PREPARATION_ORDINARY_ENERGY_CLOSURE_MISMATCH")

    def test_creating_bridge_contract_binds_raw_provenance_and_does_not_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            record_path, array_path = Path(temporary) / "ordinary.json", Path(temporary) / "ordinary.npz"
            record_path.write_bytes(canonical(self.record))
            np.savez(array_path, **self.arrays)
            result = preparation.create_bridge_contract(runtime_root=ROOT, science_root=SCIENCE,
                prepared_input=self.prepared, context=self.context, arrays=self.arrays, ordinary_record=self.record,
                runtime_test_commit="a1"*20, image_id="sha256:"+"b2"*32, image_build_commit="c3"*20,
                execution_kind="ENGINEERING_FAKE", initialization_policy="FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0",
                ordinary_record_path=record_path, ordinary_arrays_path=array_path, maximum_evaluations=201)
            self.assertEqual(result["contract"]["nuclear_repulsion_hartree"], 1.2)
            self.assertEqual(result["contract"]["array_identities"]["ordinary_density"], array_identity(self.arrays["density"]))
            self.assertEqual(result["contract"]["source_provenance"]["ordinary_record"]["sha256"], sha(record_path.read_bytes()))
            self.assertEqual(result["contract"]["preparation_scope"], "FIXED_PILOT_ETHENE_CACHED_METADATA_ONLY")
            self.assertFalse(result["contract"]["scientific_execution_authorized"])
            self.assertEqual(self.mol.forbidden_calls, 0)

    def test_real_molecular_execution_is_not_opened_by_preparation(self):
        with self.assertRaises(BridgeRefusal) as raised:
            preparation.create_bridge_contract(runtime_root=ROOT, science_root=SCIENCE,
                prepared_input=self.prepared, context=self.context, arrays=self.arrays, ordinary_record=self.record,
                runtime_test_commit="a1"*20, image_id="sha256:"+"b2"*32, image_build_commit="c3"*20,
                execution_kind="PUBLIC_COMPUTE", initialization_policy="FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0",
                ordinary_record_path="unused", ordinary_arrays_path="unused")
        self.assertEqual(raised.exception.reason, "PREPARATION_EXECUTION_KIND_INVALID")
        self.assertEqual(self.mol.forbidden_calls, 0)

    def test_raw_ordinary_record_source_cannot_be_mixed_with_another_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            record_path, array_path = Path(temporary) / "ordinary.json", Path(temporary) / "ordinary.npz"
            other = copy.deepcopy(self.record)
            other["test_record_kind"] = "A_DIFFERENT_JSON_SOURCE"
            record_path.write_bytes(canonical(other))
            np.savez(array_path, **self.arrays)
            with self.assertRaises(BridgeRefusal) as raised:
                preparation.create_bridge_contract(runtime_root=ROOT, science_root=SCIENCE,
                    prepared_input=self.prepared, context=self.context, arrays=self.arrays, ordinary_record=self.record,
                    runtime_test_commit="a1"*20, image_id="sha256:"+"b2"*32, image_build_commit="c3"*20,
                    execution_kind="ENGINEERING_FAKE", initialization_policy="REQUIRE_EXISTING_MASKED_PROJECTOR",
                    ordinary_record_path=record_path, ordinary_arrays_path=array_path)
            self.assertEqual(raised.exception.reason, "PREPARATION_RECORD_SOURCE_MISMATCH")
        self.assertEqual(self.mol.forbidden_calls, 0)

    def test_npz_source_cannot_supply_common_density_from_a_different_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            record_path, array_path = Path(temporary) / "ordinary.json", Path(temporary) / "ordinary.npz"
            record_path.write_bytes(canonical(self.record))
            other = {name: value.copy() for name, value in self.arrays.items()}
            other["density"][0, 0] += 1e-10
            np.savez(array_path, **other)
            with self.assertRaises(BridgeRefusal) as raised:
                preparation.create_bridge_contract(runtime_root=ROOT, science_root=SCIENCE,
                    prepared_input=self.prepared, context=self.context, arrays=self.arrays, ordinary_record=self.record,
                    runtime_test_commit="a1"*20, image_id="sha256:"+"b2"*32, image_build_commit="c3"*20,
                    execution_kind="ENGINEERING_FAKE", initialization_policy="REQUIRE_EXISTING_MASKED_PROJECTOR",
                    ordinary_record_path=record_path, ordinary_arrays_path=array_path)
            self.assertEqual(raised.exception.reason, "PREPARATION_ARRAY_ARCHIVE_SOURCE_MISMATCH")
        self.assertEqual(self.mol.forbidden_calls, 0)
