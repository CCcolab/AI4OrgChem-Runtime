"""User molecular admission checks; standard library only, zero native calls."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from runtime.molecular_service.input import (
    InputError, MAX_REQUEST_BYTES, MAX_XYZ_BYTES, PROFILE_PATH,
    load_profile, parse_request, parse_xyz, strict_json,
)


ROOT = Path(__file__).resolve().parents[1]
WATER = b"3\nuser water; explicit angstrom\nO 0 0 0\nH 0.758602 0 0.504284\nH -0.758602 0 0.504284\n"
METHANE_3D = b"5\nuser methane, non-planar\nC 0 0 0\nH 0.6276 0.6276 0.6276\nH 0.6276 -0.6276 -0.6276\nH -0.6276 0.6276 -0.6276\nH -0.6276 -0.6276 0.6276\n"
AMMONIA_3D = b"4\nuser ammonia\nN 0 0 0.116\nH 0 0.9377 -0.271\nH 0.8121 -0.4689 -0.271\nH -0.8121 -0.4689 -0.271\n"


def request_value():
    return {"schema": "molecular-single-point-v1", "task": "single-point", "profile": "rhf-631gd-small-v1",
            "structure": {"file": "molecule.xyz", "format": "xyz", "unit": "angstrom"},
            "charge": 0, "multiplicity": 1, "method": "RHF", "basis": "6-31G(d)"}


class MolecularServiceInputTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="普通分子 request ")
        self.root = Path(self.temporary.name)
        self.path = self.root / "request.json"
        self.structure = self.root / "molecule.xyz"
        self.request = request_value()
        self.structure.write_bytes(WATER)
        self.write(self.request)

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, value):
        self.path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def test_user_water_raw_identity_and_no_scientific_claim(self):
        result = parse_request(self.path, input_root=self.root)
        self.assertEqual(result["structure_bytes"], WATER)
        self.assertEqual(result["structure_sha256"], hashlib.sha256(WATER).hexdigest())
        self.assertEqual(result["request_sha256"], hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(result["molecule"]["symbols"], ["O", "H", "H"])
        self.assertEqual(result["atom_count"], 3)
        self.assertEqual(result["electron_count"], 10)
        self.assertEqual(result["geometry_edits"], [])
        self.assertEqual(result["admission_status"], "INPUT_ADMITTED_AO_PREFLIGHT_PENDING")
        self.assertEqual(result["ao_preflight_status"], "NOT_EXECUTED")
        self.assertIsNone(result["ao_count"])
        self.assertFalse(result["scientific_execution_performed"])
        self.assertEqual(result["atoms"][2]["index_1based"], 3)
        self.assertEqual(result["atoms"][2]["index_0based"], 2)

    def test_non_planar_methane_and_nitrogen_ammonia_are_admitted_unchanged(self):
        for geometry, symbols, electrons in ((METHANE_3D, ["C", "H", "H", "H", "H"], 10),
                                             (AMMONIA_3D, ["N", "H", "H", "H"], 10)):
            with self.subTest(symbols=symbols):
                self.structure.write_bytes(geometry)
                result = parse_request(self.path)
                self.assertEqual(result["structure_bytes"], geometry)
                self.assertEqual(result["molecule"]["symbols"], symbols)
                self.assertEqual(result["electron_count"], electrons)
                self.assertTrue(any(row[2] != 0 for row in result["molecule"]["geometry_angstrom"]))

    def test_schema_required_and_additional_keys_match_parser(self):
        schema = json.loads((ROOT / "schemas/molecular-single-point-v1.json").read_text(encoding="utf-8"))
        self.assertEqual(set(schema["required"]), set(self.request))
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["properties"]["structure"]["additionalProperties"])
        for key in self.request:
            changed = copy.deepcopy(self.request)
            del changed[key]
            self.write(changed)
            with self.subTest(missing=key), self.assertRaises(InputError):
                parse_request(self.path)
        for key in ("resources", "fragments", "proposition", "geometry_file", "research_question"):
            changed = copy.deepcopy(self.request)
            changed[key] = {}
            self.write(changed)
            with self.subTest(unknown=key), self.assertRaises(InputError):
                parse_request(self.path)

    def test_unknown_nested_keys_and_wrong_top_level_are_refused(self):
        values = [[], None, True, "request", 1]
        changed = copy.deepcopy(self.request)
        changed["structure"]["origin"] = "external"
        values.append(changed)
        for value in values:
            self.write(value)
            with self.subTest(value=value), self.assertRaises(InputError):
                parse_request(self.path)

    def test_charge_multiplicity_and_method_are_explicit_fixed_scope(self):
        cases = [("charge", True), ("charge", 0.0), ("charge", "0"), ("charge", -1),
                 ("multiplicity", True), ("multiplicity", 1.0), ("multiplicity", 3),
                 ("method", "UHF"), ("method", "rhf"), ("basis", "STO-3G"),
                 ("profile", "other"), ("task", "compute"), ("schema", "user-molecule-request-v1")]
        for key, value in cases:
            changed = copy.deepcopy(self.request)
            changed[key] = value
            self.write(changed)
            with self.subTest(key=key, value=value), self.assertRaises(InputError) as failure:
                parse_request(self.path)
            self.assertEqual(failure.exception.code, "INPUT_SCOPE_REJECTED")

    def test_unit_and_format_are_not_guessed_or_converted(self):
        for key, value in (("unit", "bohr"), ("unit", "Angstrom"), ("unit", 1), ("format", "sdf"), ("format", None)):
            changed = copy.deepcopy(self.request)
            changed["structure"][key] = value
            self.write(changed)
            with self.subTest(key=key, value=value), self.assertRaises(InputError):
                parse_request(self.path)

    def test_duplicate_and_nonfinite_json_even_inside_unknown_fields_are_rejected(self):
        values = [b'{"charge":0,"charge":0}', b'{"structure":{"file":"a","file":"b"}}',
                  b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}', b'{"x":1e999}',
                  b'\xef\xbb\xbf{}', b'\xff', b'[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[1]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]']
        for value in values:
            with self.subTest(value=value), self.assertRaises(InputError):
                strict_json(value)

    def test_path_absolute_escape_uri_windows_device_or_nested_is_refused(self):
        values = ["../molecule.xyz", "sub/molecule.xyz", "sub\\molecule.xyz", "/tmp/molecule.xyz",
                  "C:\\molecule.xyz", "C:molecule.xyz", "https://example/molecule.xyz", "file:input.xyz",
                  "CON.xyz", "com1.xyz", "NUL.x.xyz", "molecule.xyz ", "molecule.xyz.",
                  "*.xyz", "a?.xyz", 'a".xyz', "a\n.xyz", "a\x00.xyz", "x.txt", "", 7]
        for name in values:
            changed = copy.deepcopy(self.request)
            changed["structure"]["file"] = name
            self.write(changed)
            with self.subTest(name=name), self.assertRaises(InputError) as failure:
                parse_request(self.path)
            self.assertEqual(failure.exception.code, "INPUT_PATH_REJECTED")

    def test_missing_file_and_wrong_input_root_are_refused(self):
        self.structure.unlink()
        with self.assertRaises(InputError):
            parse_request(self.path)
        with self.assertRaises(InputError):
            parse_request(self.path, input_root=self.root.parent)

    def test_directory_cannot_replace_regular_xyz_or_request(self):
        self.structure.unlink()
        self.structure.mkdir()
        with self.assertRaises(InputError):
            parse_request(self.path)
        with self.assertRaises(InputError):
            parse_request(self.root)

    def test_request_and_structure_size_limits(self):
        self.path.write_bytes(b" " * (MAX_REQUEST_BYTES + 1))
        with self.assertRaises(InputError) as failure:
            parse_request(self.path)
        self.assertEqual(failure.exception.code, "INPUT_SIZE_REJECTED")
        self.write(self.request)
        self.structure.write_bytes(b" " * (MAX_XYZ_BYTES + 1))
        with self.assertRaises(InputError) as failure:
            parse_request(self.path)
        self.assertEqual(failure.exception.code, "INPUT_SIZE_REJECTED")

    def test_strict_count_comment_atom_rows_and_extra_structure(self):
        values = [b"0\ncomment\n", b"-3\ncomment\n", b"03\ncomment\n", b"3\nO 0 0 0\nH 0 1 0\nH 0 0 1\n",
                  b"3\ncomment\nO 0 0 0\nH 0 1 0\n", WATER + b"H 0 2 1\n",
                  WATER.replace(b"O 0 0 0", b"O 0 0 0 extra"), WATER.replace(b"H 0.758602 0 0.504284", b""),
                  b"2\ncomment\nH 0 0 0\nH 0 0 1\n2\nmore\nH 0 0 0\nH 0 0 1\n"]
        for value in values:
            with self.subTest(value=value), self.assertRaises(InputError):
                parse_xyz(value)

    def test_finite_ascii_decimal_xyz_and_overflow_are_required(self):
        values = [b"nan", b"inf", b"-Infinity", b"1e999", b"1_0", b"0x1", "１".encode("utf-8")]
        for value in values:
            with self.subTest(value=value), self.assertRaises(InputError):
                parse_xyz(WATER.replace(b"0.758602", value))
        with self.assertRaises(InputError):
            parse_xyz(b"2\ncomment\nH 1e308 0 0\nH -1e308 0 0\n")

    def test_finite_coordinate_engineering_bound_is_explicit_and_inclusive(self):
        result = parse_xyz(b"2\ntranslated at bound\nH 10000 0 0\nH 9999.26 0 0\n")
        self.assertEqual(result["atoms"][0]["xyz_angstrom"][0], 10000.0)
        for value in (b"10000.00001", b"-10000.00001", b"1e300"):
            with self.subTest(value=value), self.assertRaises(InputError) as failure:
                parse_xyz(b"2\ncomment\nH " + value + b" 0 0\nH 0 0 0\n")
            self.assertEqual(failure.exception.code, "INPUT_GEOMETRY_REJECTED")

    def test_unreviewed_profile_change_is_not_a_new_supported_scope(self):
        profile, _ = load_profile()
        for section, key, value in (("scope", "max_atoms", 21), ("scope", "charge", 2),
                                    ("engine", "conv_tol", 1e-9), ("engine", "max_ao", 81),
                                    ("resources", "threads", 2), ("tolerances", "electron_count_abs_max", 1e-6)):
            changed = copy.deepcopy(profile)
            changed[section][key] = value
            with self.subTest(section=section, key=key), self.assertRaises(InputError) as failure:
                parse_xyz(WATER, profile=changed)
            self.assertEqual(failure.exception.code, "INPUT_PROFILE_REJECTED")

    def test_elements_even_electrons_and_atom_cap(self):
        for value in (WATER.replace(b"O 0", b"S 0"), WATER.replace(b"O 0", b"o 0"),
                      b"1\nneutral hydrogen\nH 0 0 0\n", b"1\nneutral nitrogen\nN 0 0 0\n",
                      b"21\nexceeds scope\n" + b"C 0 0 0\n" * 21):
            with self.subTest(value=value), self.assertRaises(InputError) as failure:
                parse_xyz(value)
            self.assertEqual(failure.exception.code, "INPUT_SCOPE_REJECTED")
        result = parse_xyz(b"20\nupper atom bound\n" + b"".join(f"C {i} 0 0\n".encode() for i in range(20)))
        self.assertEqual(result["atom_count"], 20)
        self.assertEqual(result["electron_count"], 120)
        self.assertIsNone(result["ao_count"])

    def test_collision_minimum_boundary_is_an_engineering_check(self):
        with self.assertRaises(InputError) as failure:
            parse_xyz(b"2\nclose\nH 0 0 0\nH 0.499999 0 0\n")
        self.assertEqual(failure.exception.code, "INPUT_GEOMETRY_REJECTED")
        at_limit = parse_xyz(b"2\nexplicit boundary\nH 0 0 0\nH 0.5 0 0\n")
        self.assertEqual(at_limit["minimum_distance_angstrom"], 0.5)
        self.assertEqual(at_limit["minimum_distance_atom_indices_1based"], [1, 2])
        with self.assertRaises(InputError):
            parse_xyz(b"2\ncoincident\nH 0 0 0\nH 0 0 0\n")

    def test_ordinary_3d_input_has_no_fragment_or_orientation_requirement(self):
        result = parse_xyz(b"2\nvertical hydrogen\nH 0 0 -0.37\nH 0 0 0.37\n")
        self.assertEqual(result["atoms"][0]["xyz_angstrom"], [0.0, 0.0, -0.37])
        self.assertEqual(result["electron_count"], 2)

    def test_single_carbon_has_explicit_no_pair_distance(self):
        result = parse_xyz(b"1\nneutral carbon singlet input\nC 0 0 0\n")
        self.assertIsNone(result["minimum_distance_angstrom"])
        self.assertIsNone(result["minimum_distance_atom_indices_1based"])

    def test_profile_freezes_budget_and_new_ordinary_targets(self):
        profile, raw = load_profile()
        self.assertEqual(raw, PROFILE_PATH.read_bytes())
        self.assertEqual(profile["engine"]["conv_tol"], 1e-12)
        self.assertEqual(profile["engine"]["conv_tol_grad"], 1e-8)
        self.assertEqual(profile["engine"]["max_memory_mb"], 768)
        self.assertEqual(profile["engine"]["scf_kernel_call_limit"], 1)
        self.assertFalse(profile["engine"]["automatic_retry"])
        self.assertEqual(profile["engine"]["max_ao"], 80)
        self.assertEqual(profile["resources"]["memory_limit_bytes"], 1073741824)
        self.assertEqual(profile["resources"]["wall_time_limit_seconds"], 120)
        self.assertEqual(profile["resources"]["stop_after_seconds"], 100)
        self.assertEqual(profile["resources"]["threads"], 1)
        self.assertEqual(profile["tolerances"]["commutator_whitened_frobenius_max"], 1e-7)

    def test_snapshot_from_returned_bytes_preserves_raw_hash_identity(self):
        first = parse_request(self.path)
        self.structure.write_bytes(METHANE_3D)
        self.path.write_bytes(b"original changed after admission")
        snapshot = self.root / "snapshot"
        snapshot.mkdir()
        (snapshot / "request.json").write_bytes(first["request_bytes"])
        (snapshot / first["structure_file"]).write_bytes(first["structure_bytes"])
        second = parse_request(snapshot / "request.json")
        self.assertEqual(first["request_sha256"], second["request_sha256"])
        self.assertEqual(first["structure_sha256"], second["structure_sha256"])

    def test_read_rejects_changed_file_identity(self):
        actual = Path.lstat
        attempts = {"count": 0}
        def changing(path, *args, **kwargs):
            info = actual(path, *args, **kwargs)
            if path == self.structure:
                attempts["count"] += 1
                if attempts["count"] == 3:
                    self.structure.write_bytes(METHANE_3D)
            return info
        with mock.patch.object(Path, "lstat", changing):
            with self.assertRaises(InputError):
                parse_request(self.path)

    def test_symlink_request_structure_and_root_are_rejected_when_available(self):
        link = self.root / "alias.xyz"
        try:
            link.symlink_to(self.structure)
        except OSError:
            self.skipTest("host does not permit symlink fixture; portable lstat test remains active")
        changed = copy.deepcopy(self.request)
        changed["structure"]["file"] = "alias.xyz"
        self.write(changed)
        with self.assertRaises(InputError):
            parse_request(self.path)
        self.write(self.request)
        request_link = self.root / "alias.json"
        request_link.symlink_to(self.path)
        with self.assertRaises(InputError):
            parse_request(request_link)
        root_link = self.root / "input-link"
        root_link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(InputError):
            parse_request(root_link / "request.json", input_root=root_link)

    def test_reparse_flag_is_rejected_without_windows_symlink_privilege(self):
        actual = Path.lstat
        def reparse(path, *args, **kwargs):
            info = actual(path, *args, **kwargs)
            if path == self.structure:
                class FileInfo:
                    st_mode = info.st_mode
                    st_file_attributes = 0x400
                return FileInfo()
            return info
        with mock.patch.object(Path, "lstat", reparse):
            with self.assertRaises(InputError) as failure:
                parse_request(self.path)
        self.assertEqual(failure.exception.code, "INPUT_PATH_REJECTED")


if __name__ == "__main__":
    unittest.main()
