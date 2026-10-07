"""P13 stdlib graph/ledger and honest-refusal tests; no QM/RDKit substitute."""
from __future__ import annotations

import ast
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.registered_cases import p13


class RegisteredP13Tests(unittest.TestCase):
    def test_preserved_source_byte_identity_and_untracked_provenance(self):
        source = p13.verify_sources()
        self.assertEqual(hashlib.sha256(source["driver_bytes"]).hexdigest(), p13.DRIVER_SHA256)
        self.assertEqual(hashlib.sha256(source["protocol_bytes"]).hexdigest(), p13.PROTOCOL_SHA256)
        self.assertFalse(source["metadata"]["driver_is_public_baseline_driver"])
        self.assertEqual(source["metadata"]["captured_repository_head"], "ffde7b5a53800010f2bc326b812b3e5b4526d56c")
        self.assertTrue(all(item["tracked_at_capture"] is False and item["git_blob_at_head"] is None
                            for item in source["metadata"]["files"]))

    def test_fixed_acene_atom_and_edge_counts(self):
        for rings in range(2, 8):
            with self.subTest(rings=rings):
                graph = p13.build_linear_acene(rings)
                self.assertEqual(len(graph["coordinates"]), 4 * rings + 2)
                self.assertEqual(len(graph["edges"]), 5 * rings + 1)
                self.assertEqual(len(graph["ring_edges"]), rings)

    def test_matching_and_gl_qualified_counts_all_six_fixed_graphs(self):
        for rings in range(2, 8):
            graph = p13.build_linear_acene(rings)
            matchings = p13.enumerate_perfect_matchings(len(graph["coordinates"]), graph["edges"])
            qualified = [matching for matching in matchings if
                sum(len(matching & ring) == 3 for ring in graph["ring_edges"])
                == len(matching & graph["generalized_fusion_edges"]) + 1]
            self.assertEqual(len(matchings), rings + 1)
            self.assertEqual(len(qualified), rings - 1)

    def test_matchings_cover_every_vertex_once_and_only_actual_edges(self):
        graph = p13.build_linear_acene(7)
        matchings = p13.enumerate_perfect_matchings(len(graph["coordinates"]), graph["edges"])
        for matching in matchings:
            endpoints = [atom for bond in matching for atom in bond]
            self.assertEqual(sorted(endpoints), list(range(30)))
            self.assertTrue(matching <= graph["edges"])
        self.assertEqual(len({frozenset(matching) for matching in matchings}), len(matchings))

    def test_gl_filter_rejects_two_endpoint_candidates(self):
        graph = p13.build_linear_acene(2)
        matchings = p13.enumerate_perfect_matchings(10, graph["edges"])
        qualification = [sum(len(m & ring) == 3 for ring in graph["ring_edges"])
            == len(m & graph["generalized_fusion_edges"]) + 1 for m in matchings]
        self.assertEqual(qualification.count(False), 2)
        self.assertEqual(qualification.count(True), 1)

    def test_fixed_ring_count_refuses_arbitrary_geometry_scope(self):
        for invalid in (0, 1, 8, True, 2.0, "2"):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, "FIXED_RING_COUNTS"):
                p13.build_linear_acene(invalid)

    def test_ledger_arithmetic_and_original_row_unchanged(self):
        row = {"delta_EA": -9.4, "sum_delta_EAm": 55.8, "sum_delta_EnAm": -3.2,
               "ESE": -65.2, "CESE": -62.0, "label": "GL5:6"}
        before = dict(row)
        result = p13.recompute_ledger(row)
        self.assertAlmostEqual(result["calculated_ESE"], -65.2)
        self.assertAlmostEqual(result["calculated_CESE"], -62.0)
        self.assertLessEqual(abs(result["ESE_residual"]), 0.15)
        self.assertLessEqual(abs(result["CESE_residual"]), 0.15)
        self.assertEqual(row, before)

    def test_corrupted_published_ledger_is_outside_unchanged_tolerance(self):
        result = p13.recompute_ledger({"delta_EA": 3.2, "sum_delta_EAm": 164.3,
            "sum_delta_EnAm": -19.9, "ESE": -161.1, "CESE": -140.2})
        self.assertLessEqual(abs(result["ESE_residual"]), 0.15)
        self.assertGreater(abs(result["CESE_residual"]), 0.15)

    def test_original_math_body_is_exact_ast_before_failure_transport(self):
        source = p13.verify_sources()
        # Compile only: no function called and no fake RDKit formula returned.
        function, extraction = p13._mathematics(source["driver_bytes"], None, None)
        original = p13._functions(source["driver_bytes"])["run"]
        original_math = []
        for statement in original.body[1:]:
            if isinstance(statement, ast.If):
                break
            original_math.append(statement)
        expected = hashlib.sha256(ast.dump(ast.Module(body=original_math, type_ignores=[]),
            include_attributes=False).encode()).hexdigest()
        self.assertEqual(extraction["retained_math_ast_sha256"], expected)
        self.assertEqual(extraction["retained_original_run_line_range"], [218, 300])
        self.assertEqual(function.__name__, "reconstruct_fixed_mathematics")
        self.assertFalse(extraction["math_expressions_modified"])

    def test_original_all_fifteen_check_names_and_thresholds_retained(self):
        source = p13.verify_sources()
        original = p13._functions(source["driver_bytes"])["run"]
        checks = next(stmt.value for stmt in original.body if isinstance(stmt, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "checks" for target in stmt.targets))
        self.assertEqual(tuple(key.value for key in checks.keys), p13.ACCEPTANCE_NAMES)
        self.assertEqual(len(p13.ACCEPTANCE_NAMES), 15)
        text = source["protocol_bytes"].decode()
        self.assertIn("rounded_energy_identity_tolerance_kcal_mol: 0.15", text)
        self.assertIn("rounded_per_pi_tolerance_kcal_mol_electron: 0.06", text)
        self.assertIn("benzene_CESE_per_pi_absolute_reference: 6.5", text)

    def test_authentic_formula_helper_has_no_formula_fallback(self):
        helper = p13._functions(p13.verify_sources()["driver_bytes"])["rdkit_formula"]
        calls = {ast.unparse(node.func) for node in ast.walk(helper) if isinstance(node, ast.Call)}
        self.assertTrue({"Chem.RWMol", "Chem.Atom", "Chem.SanitizeMol",
            "rdMolDescriptors.CalcMolFormula"} <= calls)
        self.assertEqual(p13.REQUIRED_RDKIT_VERSION, "2026.03.4")

    def test_missing_dependency_retains_blocked_not_executed_receipt(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "new"
            with patch.object(p13, "_dependencies", side_effect=p13.P13Blocked("P13_REQUIRED_DEPENDENCIES_MISSING: rdkit")):
                record = p13.run(output)
            self.assertEqual(record["status"], "BLOCKED")
            self.assertEqual(record["acceptance_checks"], {})
            self.assertEqual(record["acceptance_execution_status"], "NOT_EXECUTED")
            self.assertEqual(record["new_quantum_calls"], 0)
            self.assertIsNone(record["source_pdf_sha256"])
            self.assertNotIn("graph_enumeration", record)
            self.assertEqual(json.loads((output / "case-result.json").read_text(encoding="utf-8")), record)
            self.assertIn("NOT_REAUTHENTICATED", (output / "case-report.md").read_text(encoding="utf-8"))

    def test_source_tamper_retains_blocked_receipt_and_does_not_repair_source(self):
        with tempfile.TemporaryDirectory() as root:
            reference = Path(root) / "reference"
            reference.mkdir()
            for name in (p13.DRIVER_NAME, p13.PROTOCOL_NAME, "SOURCE_METADATA.json"):
                (reference / name).write_bytes((p13.REFERENCE_DIR / name).read_bytes())
            tampered = (reference / p13.PROTOCOL_NAME).read_bytes() + b"\n"
            (reference / p13.PROTOCOL_NAME).write_bytes(tampered)
            with patch.object(p13, "REFERENCE_DIR", reference):
                record = p13.run(Path(root) / "output")
            self.assertEqual(record["status"], "BLOCKED")
            self.assertIn("SOURCE_HASH_MISMATCH", record["error"])
            self.assertEqual((reference / p13.PROTOCOL_NAME).read_bytes(), tampered)

    def test_nonempty_output_refused_without_overwrite(self):
        with tempfile.TemporaryDirectory() as root:
            marker = Path(root) / "keep.txt"
            marker.write_bytes(b"keep")
            with self.assertRaisesRegex(ValueError, "EMPTY_DIRECTORY"):
                p13.run(Path(root))
            self.assertEqual(marker.read_bytes(), b"keep")

    def test_existing_empty_output_is_admitted(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.object(p13, "_dependencies", side_effect=p13.P13Blocked("missing dependency")):
                record = p13.run(Path(root))
            self.assertEqual(record["status"], "BLOCKED")
            self.assertEqual({p.name for p in Path(root).iterdir()}, {"case-result.json", "case-report.md"})

    def test_reference_directory_cannot_be_output(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_LOCATION"):
            p13.run(p13.REFERENCE_DIR)

    def test_runtime_repository_child_cannot_be_output(self):
        forbidden = p13.RUNTIME_ROOT / "p13-never-create-output"
        with self.assertRaisesRegex(ValueError, "SOURCE_LOCATION"):
            p13.run(forbidden)
        self.assertFalse(forbidden.exists())

    def test_original_development_repository_child_cannot_be_output(self):
        forbidden = p13.ORIGINAL_DEVELOPMENT_DIR / "p13-never-create-output"
        with self.assertRaisesRegex(ValueError, "SOURCE_LOCATION"):
            p13.run(forbidden)
        self.assertFalse(forbidden.exists())

    def test_driver_full_module_cli_pdf_git_never_executed(self):
        source = p13.verify_sources()
        helpers = p13._compile_helpers(source["driver_bytes"], p13.PURE_HELPERS)
        self.assertNotIn("ROOT", helpers)
        for excluded in ("main", "git_commit", "sha256", "run", "subprocess", "yaml", "Chem"):
            self.assertNotIn(excluded, helpers)


if __name__ == "__main__":
    unittest.main()
