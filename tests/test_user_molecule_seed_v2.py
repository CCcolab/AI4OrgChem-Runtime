"""Analytical seed checks; no molecular engine or operator evaluation."""
import ast
import json
from pathlib import Path
import unittest
from unittest import mock

import numpy as np

from runtime.user_molecule import seed_v2


def fixture():
    return {"density": np.diag([2.0, 2.0, 0.0, 0.0]),
            "physical_overlap": np.eye(4),
            "masked_overlap": np.array([[1.2, .2, 0, 0], [.2, .8, 0, 0],
                                        [0, 0, 1.1, .1], [0, 0, .1, .9]]),
            "mo_coefficients": np.eye(4),
            "mo_occupations": np.array([2.0, 2.0, 0.0, 0.0]),
            "electrons": 4}


class SeedV2Tests(unittest.TestCase):
    def refuse(self, values, text=None):
        before = {key: value.copy() for key, value in values.items() if isinstance(value, np.ndarray)}
        with self.assertRaises(seed_v2.SeedV2Error) as caught:
            seed_v2.prepare_seed_v2(**values)
        receipt = caught.exception.receipt
        self.assertEqual(receipt["status"], "REFUSED")
        self.assertEqual(receipt["functional_calls"], 0)
        self.assertFalse(receipt["repairs_performed"])
        self.assertFalse(receipt["production_activation"])
        json.dumps(receipt, allow_nan=False)
        if text:
            self.assertIn(text, str(caught.exception))
        for key, value in before.items():
            np.testing.assert_array_equal(values[key], value)
        return receipt

    def test_analytic_two_occupied_seed_matches_inverse_gram(self):
        values = fixture()
        result = seed_v2.prepare_seed_v2(**values)
        # Inverse of the hand-specified occupied 2x2 Gram, determinant .92.
        expected = np.zeros((4, 4))
        expected[:2, :2] = (2.0 / .92) * np.array([[.8, -.2], [-.2, 1.2]])
        np.testing.assert_allclose(result["density"], expected, rtol=0, atol=2e-14)
        np.testing.assert_allclose(result["coefficients"].T @ values["masked_overlap"] @ result["coefficients"],
                                   np.eye(2), rtol=0, atol=2e-14)
        receipt = result["receipt"]
        self.assertEqual(receipt["policy_id"], seed_v2.POLICY_ID)
        self.assertEqual(receipt["status"], "ADMITTED_SEED_ONLY")
        self.assertEqual(receipt["endpoint_qualification"], "NOT_EXECUTED")
        self.assertFalse(receipt["scientific_approval"])
        self.assertFalse(receipt["production_activation"])
        json.dumps(receipt, allow_nan=False)

    def test_definition_and_original_solver_admission_are_separate(self):
        receipt = seed_v2.prepare_seed_v2(**fixture())["receipt"]
        definition = receipt["definition_checks"]
        admission = receipt["solver_admission_checks"]
        self.assertEqual(definition["seed_masked_electron_count"]["threshold"], 1e-7)
        self.assertEqual(admission["whitened_trace"]["threshold"], 1e-10)
        self.assertEqual(admission["whitened_idempotency"]["threshold"], 1e-10)
        self.assertIn("absolute", admission["whitened_idempotency"]["metric"])
        self.assertNotIn("denominator", admission["whitened_trace"])
        self.assertNotIn("denominator", admission["whitened_idempotency"])
        self.assertGreaterEqual(definition["seed_masked_idempotency"]["denominator"], 1)
        self.assertIn("production_density_reconstruction", admission)
        self.assertTrue(all(row["pass"] for row in definition.values()))
        self.assertTrue(all(row["pass"] for row in admission.values()))

    def test_physical_count_is_distinct_and_grid_is_not_evaluated(self):
        receipt = seed_v2.prepare_seed_v2(**fixture())["receipt"]
        diagnostic = receipt["diagnostics"]
        self.assertAlmostEqual(diagnostic["masked_seed_electron_count"], 4.0, places=13)
        self.assertAlmostEqual(diagnostic["physical_seed_electron_count"], 4.0 / .92, places=13)
        self.assertIsNone(diagnostic["grid_seed_electron_count"])
        self.assertEqual(receipt["functional_calls"], 0)

    def test_inputs_readonly_and_independent_output_buffers(self):
        values = fixture()
        before = {key: value.copy() for key, value in values.items() if isinstance(value, np.ndarray)}
        for value in values.values():
            if isinstance(value, np.ndarray):
                value.setflags(write=False)
        result = seed_v2.prepare_seed_v2(**values)
        self.assertFalse(result["density"].flags.writeable)
        self.assertFalse(result["coefficients"].flags.writeable)
        for key, value in before.items():
            np.testing.assert_array_equal(values[key], value)
            self.assertFalse(np.shares_memory(values[key], result["density"]))
            self.assertFalse(np.shares_memory(values[key], result["coefficients"]))

    def test_occupied_sign_permutation_and_orthogonal_rotation_keep_seed(self):
        original = seed_v2.prepare_seed_v2(**fixture())["density"]
        transforms = [np.diag([-1.0, 1.0]), np.array([[0., 1.], [1., 0.]]),
                      np.array([[.6, -.8], [.8, .6]])]
        for transform in transforms:
            with self.subTest(transform=transform.tolist()):
                values = fixture()
                values["mo_coefficients"][:, :2] = values["mo_coefficients"][:, :2] @ transform
                transformed = seed_v2.prepare_seed_v2(**values)["density"]
                np.testing.assert_allclose(transformed, original, rtol=0, atol=2e-14)

    def test_general_invertible_basis_invariance_is_not_parent_approval(self):
        values = fixture()
        expected = seed_v2.prepare_seed_v2(**values)["density"]
        c0 = values["mo_coefficients"][:, :2]
        changed = c0 @ np.array([[2.0, .3], [.1, .8]])
        gram = changed.T @ values["masked_overlap"] @ changed
        algebraic = 2.0 * changed @ np.linalg.solve(gram, changed.T)
        np.testing.assert_allclose(algebraic, expected, rtol=0, atol=2e-14)
        values["mo_coefficients"][:, :2] = changed
        self.refuse(values, "ordinary_occupied_physical_orthonormality")

    def test_noncontiguous_occupied_columns_are_selected_from_exact_occupations(self):
        values = fixture()
        permutation = [2, 0, 3, 1]
        values["mo_coefficients"] = values["mo_coefficients"][:, permutation]
        values["mo_occupations"] = values["mo_occupations"][permutation]
        result = seed_v2.prepare_seed_v2(**values)
        np.testing.assert_allclose(result["density"], seed_v2.prepare_seed_v2(**fixture())["density"], atol=2e-14)

    def test_nonidentity_physical_metric_uses_ordinary_normalized_space(self):
        values = fixture()
        values["physical_overlap"] = np.diag([4.0, .25, 2.0, .5])
        values["mo_coefficients"] = np.diag([.5, 2.0, 1 / np.sqrt(2), np.sqrt(2)])
        values["density"] = np.diag([.5, 8.0, 0.0, 0.0])
        result = seed_v2.prepare_seed_v2(**values)
        # The occupied column space is unchanged; its nonorthogonal basis
        # normalization cancels from the same masked-metric formula.
        np.testing.assert_allclose(result["density"], seed_v2.prepare_seed_v2(**fixture())["density"], atol=2e-14)

    def test_nonfinite_or_nonreal_inputs_refuse_finitely_without_callbacks(self):
        replacements = [np.nan, np.inf, -np.inf, 1 + 1j, "invalid", True]
        for replacement in replacements:
            with self.subTest(value=str(replacement)):
                values = fixture()
                if isinstance(replacement, (complex, str, bool)):
                    values["masked_overlap"] = np.full((4, 4), replacement)
                else:
                    values["masked_overlap"][0, 0] = replacement
                self.refuse(values)

    def test_missing_dimensions_and_incomplete_mo_cache_refuse(self):
        changes = [("density", np.zeros((3, 4))), ("physical_overlap", np.eye(3)),
                   ("masked_overlap", np.eye(3)), ("mo_coefficients", np.eye(4)[:, :2]),
                   ("mo_occupations", np.array([2.0, 2.0]))]
        for key, value in changes:
            with self.subTest(key=key):
                values = fixture()
                values[key] = value
                self.refuse(values)

    def test_fractional_wrong_count_and_boolean_electron_inputs_refuse(self):
        for occupations in ([1., 1., 1., 1.], [2., 0., 0., 0.], [2., 2., 2., 0.], [2., 2.000000001, 0., 0.]):
            with self.subTest(occupations=occupations):
                values = fixture()
                values["mo_occupations"] = np.array(occupations)
                self.refuse(values, "exact global closed-shell")
        for electrons in (True, 0, 3, 8, 4.0, np.int64(4)):
            with self.subTest(electrons=str(electrons)):
                values = fixture()
                values["electrons"] = electrons
                self.refuse(values, "integer positive closed-shell")

    def test_density_and_metric_asymmetry_refuse_without_symmetrization(self):
        for key in ("density", "physical_overlap", "masked_overlap"):
            with self.subTest(key=key):
                values = fixture()
                values[key][0, 1] += 1e-7
                self.refuse(values, "symmetry")

    def test_parent_orthonormality_and_density_reconstruction_refuse(self):
        values = fixture()
        values["mo_coefficients"][0, 0] = 1.01
        self.refuse(values, "ordinary_occupied_physical_orthonormality")
        values = fixture()
        values["density"][0, 0] += 1e-6
        self.refuse(values, "ordinary_density_reconstruction")

    def test_nonpositive_metrics_and_metric_condition_ceiling_refuse(self):
        for key in ("physical_overlap", "masked_overlap"):
            for eigenvalue in (0., -.1, 1e-8):
                with self.subTest(key=key, eigenvalue=eigenvalue):
                    values = fixture()
                    values[key] = np.diag([eigenvalue, 1., 1., 1.])
                    self.refuse(values, "positive definite" if eigenvalue <= 0 else "condition_number")

    def test_occupied_gram_condition_is_independently_checked(self):
        values = fixture()
        values["physical_overlap"] = np.diag([1e-3, 1e3, 1., 1.])
        values["masked_overlap"] = np.diag([1e3, 1e-3, 1., 1.])
        values["mo_coefficients"] = np.diag([np.sqrt(1e3), np.sqrt(1e-3), 1., 1.])
        values["density"] = np.diag([2e3, 2e-3, 0., 0.])
        receipt = self.refuse(values, "occupied_masked_gram_condition_number")
        self.assertTrue(receipt["definition_checks"]["physical_overlap_condition_number"]["pass"])
        self.assertTrue(receipt["definition_checks"]["masked_overlap_condition_number"]["pass"])

    def test_rotation_variable_ceiling_refuses_before_seed_or_callbacks(self):
        n, occupied = 18, 9
        values = {"density": np.diag([2.] * occupied + [0.] * (n - occupied)),
                  "physical_overlap": np.eye(n), "masked_overlap": np.eye(n),
                  "mo_coefficients": np.eye(n), "mo_occupations": np.array([2.] * occupied + [0.] * (n - occupied)),
                  "electrons": 2 * occupied}
        self.refuse(values, "ceiling of 64")

    def test_numerical_failure_has_strict_json_receipt_and_no_repair(self):
        with mock.patch.object(seed_v2.np.linalg, "eigh", side_effect=np.linalg.LinAlgError("synthetic failure")):
            receipt = self.refuse(fixture(), "LinAlgError")
        self.assertEqual(receipt["functional_calls"], 0)

    def test_array_module_has_no_engine_or_solver_import(self):
        path = Path(seed_v2.__file__)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        self.assertFalse(any(name.startswith(("pyscf", "science", "ai4orgchem", "reference", "runtime.")) for name in imports))


if __name__ == "__main__":
    unittest.main()
