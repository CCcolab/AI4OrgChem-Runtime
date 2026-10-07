"""Engineering and fixed-statistics checks; no PySCF, PDF or old result input."""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from runtime.registered_cases import p02


def table_fixture():
    """Explicit input values, not a copy of a frozen numerical result."""
    reference = {
        "aromatic_1_3_m": {
            "points": [{"N": n, "selected_wavelength_angstrom": wavelength} for n, wavelength in ((3, 2510), (4, 2800), (5, 3400))],
            "monograph_figure_equation": {"intercept": 9.03372, "slope": -7.92576, "printed_cc": 0.889},
        },
        "polyenal_1_4_n": {
            "points": [{"N": n, "selected_wavelength_angstrom": wavelength} for n, wavelength in ((2, 2040), (3, 2830), (4, 3615), (5, 4215))],
            "monograph_figure_equation": {"intercept": 9.8472, "slope": -9.9477, "printed_cc": 9.847},
        },
    }
    rows = []
    for m, n, bands in ((0, 0, [2360]), (0, 1, [3050]), (0, 2, [3780]), (1, 0, [2780]), (1, 1, [3140, 2840]), (1, 2, [3900]), (2, 0, [3400]), (2, 1, [3180]), (2, 2, [4100, 3620]), (2, 3, [4480])):
        row = {"id": f"1-1-({m},{n})", "m": m, "n": n, "wavelengths_angstrom": bands,
               "monograph_group": "dual_competition" if m == n and m > 0 else ("aromatic_predominant" if m > n or (m == 0 and n == 0) else "polyenal_predominant")}
        if (m, n) == (1, 1):
            row["peak_roles"] = {"polyenal": 3140, "aromatic": 2840}
        if (m, n) == (2, 2):
            row["peak_roles"] = {"polyenal": 4100, "aromatic": 3620}
        rows.append(row)
    return {
        "protocol_id": "P02_STRUCTURE_UV_SOURCE_FREEZE_V0.1", "proposition_id": "P02",
        "source": {"doi": "10.6084/m9.figshare.27261243.v1", "sha256": "07AADF5E25967616C4076C8B732EBB17E9E179F31C6546B6EB06D46E96D4A85D", "table": "Table 1-1", "printed_pages": list(range(6, 18))},
        "uv_reference_series": reference, "uv_target_series": rows,
        "structural_pair": {"stronger_aromatic_participation": "1-1-(1,1)", "weaker_aromatic_participation": "1-1-(1,2)",
            "values": {"1-1-(1,1)": {"twist_angle_degree": 33.6, "c_n_bond_angstrom": 1.430}, "1-1-(1,2)": {"twist_angle_degree": 31.4, "c_n_bond_angstrom": 1.423}},
            "traditional_direction_prediction": {"twist_delta_stronger_minus_weaker": "negative", "c_n_delta_stronger_minus_weaker": "negative"}, "source_tier": "published_value_reanalysis_without_raw_cif"},
        "tolerances": {"coefficient_absolute": 0.05, "direction_zero": 1.0e-12, "wavelength_transcription_angstrom": 0.0},
    }


class RegisteredP02Tests(unittest.TestCase):
    def test_reference_fits_match_independent_centered_sum_ols(self):
        for series in table_fixture()["uv_reference_series"].values():
            points = series["points"]
            x = [0.5 ** (2 / point["N"]) for point in points]
            y = [10000 / point["selected_wavelength_angstrom"] for point in points]
            xmean, ymean = sum(x) / len(x), sum(y) / len(y)
            slope = sum((a - xmean) * (b - ymean) for a, b in zip(x, y)) / sum((a - xmean) ** 2 for a in x)
            intercept = ymean - slope * xmean
            actual = p02.regression(points)
            self.assertAlmostEqual(actual["slope"], slope, places=11)
            self.assertAlmostEqual(actual["intercept"], intercept, places=11)
            self.assertTrue(0 < actual["r_squared"] <= 1)

    def test_exact_affine_spectrum_closes(self):
        points = [{"N": n, "selected_wavelength_angstrom": 10000 / (10 - 8 * 0.5 ** (2 / n))} for n in (2, 3, 4, 5)]
        result = p02.regression(points)
        self.assertAlmostEqual(result["intercept"], 10, places=11)
        self.assertAlmostEqual(result["slope"], -8, places=11)
        self.assertLess(result["rmse"], 1e-12)

    def test_frozen_table_gates_and_bounded_source_claim(self):
        result = p02.recompute_table_values(table_fixture())
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(set(result["acceptance_checks"]), set(p02.TABLE_CHECK_NAMES))
        self.assertTrue(all(result["acceptance_checks"].values()))
        self.assertNotIn("source_hash_matches", result["acceptance_checks"])
        self.assertEqual(result["primary_source_verification"], "NOT_EXECUTED")
        self.assertFalse(result["source_pdf_accessed"])
        self.assertFalse(result["frozen_result_read"])
        self.assertEqual(result["new_quantum_calls"], 0)
        self.assertNotIn("verified_sha256", result["source_declaration"])
        self.assertFalse(result["structural_direction_test"]["inferential_p_value_computed"])
        self.assertAlmostEqual(result["structural_direction_test"]["observed_twist_delta_degree"], 2.2)
        self.assertAlmostEqual(result["structural_direction_test"]["observed_c_n_bond_delta_angstrom"], 0.007)

    def test_table_calculation_does_not_mutate_input(self):
        source = table_fixture()
        before = deepcopy(source)
        p02.recompute_table_values(source)
        self.assertEqual(source, before)

    def test_opposite_structure_direction_is_failure_not_forced_success(self):
        config = table_fixture()
        config["structural_pair"]["values"]["1-1-(1,1)"]["twist_angle_degree"] = 30.0
        result = p02.recompute_table_values(config)
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(result["acceptance_checks"]["both_structure_observables_oppose_traditional_direction"])

    def test_reference_equation_disagreement_fails_original_gate(self):
        config = table_fixture()
        config["uv_reference_series"]["aromatic_1_3_m"]["monograph_figure_equation"]["intercept"] = 0.0
        result = p02.recompute_table_values(config)
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(result["acceptance_checks"]["aromatic_reference_line_reproduced"])

    def test_bad_numbers_and_singular_reference_are_rejected(self):
        points = table_fixture()["uv_reference_series"]["aromatic_1_3_m"]["points"]
        for invalid in (0, -1, math.inf, math.nan, True, "2510"):
            with self.subTest(invalid=invalid):
                changed = deepcopy(points)
                changed[0]["selected_wavelength_angstrom"] = invalid
                with self.assertRaises(ValueError):
                    p02.regression(changed)
        for field, invalid in (("N", True), ("N", 3.5), ("N", 0)):
            changed = deepcopy(points)
            changed[0][field] = invalid
            with self.assertRaises(ValueError):
                p02.regression(changed)
        changed = deepcopy(points)
        changed[1]["N"] = changed[0]["N"]
        with self.assertRaises(ValueError):
            p02.regression(changed)
        for row in changed:
            row["N"] = 2 + changed.index(row)
            row["selected_wavelength_angstrom"] = 2500
        with self.assertRaises(ValueError):
            p02.regression(changed)

    def test_changed_tolerances_are_rejected(self):
        for field, value in (("coefficient_absolute", 0.1), ("direction_zero", 0), ("wavelength_transcription_angstrom", True)):
            config = table_fixture()
            config["tolerances"][field] = value
            with self.assertRaises(ValueError):
                p02.recompute_table_values(config)

    def test_wrong_pair_duplicate_identity_and_role_are_rejected(self):
        edits = [lambda c: c["structural_pair"].update(stronger_aromatic_participation="1-1-(2,2)"),
                 lambda c: c["uv_target_series"].__setitem__(0, deepcopy(c["uv_target_series"][1])),
                 lambda c: c["uv_target_series"][4]["peak_roles"].update(aromatic=9999),
                 lambda c: c["uv_target_series"][0].update(m=True)]
        for edit in edits:
            config = table_fixture()
            edit(config)
            with self.assertRaises(ValueError):
                p02.recompute_table_values(config)

    def test_formula_copy_matches_retained_original_ast(self):
        original_source = (p02.REFERENCE_DIRECTORY / "generate_p02_structure_uv_evidence.py").read_text(encoding="utf-8")
        actual_source = Path(p02.__file__).read_text(encoding="utf-8")
        original = {n.name: n for n in ast.parse(original_source).body if isinstance(n, ast.FunctionDef)}
        actual = {n.name: n for n in ast.parse(actual_source).body if isinstance(n, ast.FunctionDef)}
        copied = deepcopy(original["regression"])
        copied.name = "_original_regression"
        self.assertEqual(ast.dump(copied, include_attributes=False), ast.dump(actual["_original_regression"], include_attributes=False))
        self.assertEqual(ast.dump(original["expected_group"], include_attributes=False), ast.dump(actual["expected_group"], include_attributes=False))

    def test_retained_original_bytes_and_untracked_provenance(self):
        metadata = json.loads((p02.REFERENCE_DIRECTORY / "SOURCE_METADATA.json").read_text(encoding="utf-8"))
        self.assertFalse(metadata["original_files_are_part_of_frozen_public_release"])
        self.assertFalse(metadata["source_repository_head_is_source_file_commit"])
        self.assertEqual(len(metadata["source_files"]), 2)
        for item in metadata["source_files"]:
            raw = (p02.REFERENCE_DIRECTORY / item["retained_filename"]).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), item["sha256"])
            self.assertEqual(len(raw), item["size_bytes"])
            self.assertEqual(item["git_tracking"], "UNTRACKED")

    def test_byte_tamper_rejected_before_yaml_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for name in (*p02.SOURCE_IDENTITIES, "SOURCE_METADATA.json"):
                (directory / name).write_bytes((p02.REFERENCE_DIRECTORY / name).read_bytes())
            source = directory / "p02_structure_uv_source_freeze_v0.1.yaml"
            source.write_bytes(source.read_bytes() + b"\n")
            with patch.object(p02, "REFERENCE_DIRECTORY", directory):
                with self.assertRaisesRegex(ValueError, "source bytes changed"):
                    p02.load_frozen_input()

    def test_fresh_outputs_and_failure_report_are_honest(self):
        config = table_fixture()
        config["structural_pair"]["values"]["1-1-(1,1)"]["c_n_bond_angstrom"] = 1.0
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            with patch.object(p02, "load_frozen_input", return_value=(config, {"test_fixture_only": True})):
                result = p02.run(directory)
                self.assertEqual(result["status"], "FAIL")
                stored = json.loads((directory / "case-result.json").read_text(encoding="utf-8"))
                self.assertEqual(stored["status"], "FAIL")
                report = (directory / "case-report.md").read_text(encoding="utf-8")
                self.assertIn("`FAIL`", report)
                self.assertIn("NOT_EXECUTED", report)
                before = (directory / "case-result.json").read_bytes()
                with self.assertRaisesRegex(ValueError, "fresh"):
                    p02.run(directory)
                self.assertEqual((directory / "case-result.json").read_bytes(), before)

    def test_nonempty_or_source_output_directory_is_rejected_before_input_read(self):
        with patch.object(p02, "load_frozen_input", side_effect=AssertionError("Input must not be loaded")):
            with self.assertRaisesRegex(ValueError, "protected"):
                p02.run(Path(p02.__file__).resolve().parents[2])
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp)
                (path / "unrelated.txt").write_text("keep", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "fresh and empty"):
                    p02.run(path)
                self.assertEqual((path / "unrelated.txt").read_text(encoding="utf-8"), "keep")

    def test_real_retained_yaml_matches_explicit_table_fixture_if_dependency_available(self):
        if importlib.util.find_spec("yaml") is None:
            self.skipTest("Host has no PyYAML; mandatory real-YAML integration belongs to pinned container run")
        actual, provenance = p02.load_frozen_input()
        fixture = table_fixture()
        self.assertEqual(actual["uv_target_series"], fixture["uv_target_series"])
        for key in fixture["uv_reference_series"]:
            self.assertEqual(actual["uv_reference_series"][key]["monograph_figure_equation"], fixture["uv_reference_series"][key]["monograph_figure_equation"])
            for actual_row, fixture_row in zip(actual["uv_reference_series"][key]["points"], fixture["uv_reference_series"][key]["points"]):
                self.assertEqual(actual_row["N"], fixture_row["N"])
                self.assertEqual(actual_row["selected_wavelength_angstrom"], fixture_row["selected_wavelength_angstrom"])
        self.assertEqual(p02.recompute_table_values(actual)["status"], "PASS")
        self.assertEqual(set(provenance["retained_files"]), set(p02.SOURCE_IDENTITIES))


if __name__ == "__main__":
    unittest.main()
