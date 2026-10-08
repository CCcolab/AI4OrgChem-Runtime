"""P09/P10 contracts and pure arithmetic; no scientific kernel is executed."""
from __future__ import annotations

import copy
import importlib
import itertools
import json
import math
from pathlib import Path
import re
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np

from runtime.protocol_cases import p09_p10 as adapter


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reference/protocol_cases/source_tree"


def protocol(case="P10"):
    settings = {"pyscf_xc": "B3LYPG", "basis": "6-31g(d)", "grid_level": 3,
                "charge": 0, "multiplicity": 1, "scf_tolerance_hartree": 1.0e-10}
    if case == "P09":
        settings["max_scf_cycles"] = 100
        return {"protocol_id": adapter.P09, "p09_qm_execution_allowed": False,
                "p09_qm_execution_scope": "none_p09_complete", "electronic_structure": settings,
                "smoke_gate": {"conditional_scf": {"maximum_cycles": 100, "density_tolerance": 2.0e-8,
                    "energy_tolerance_hartree": 1.0e-10, "diis_start_cycle": 2, "diis_space": 8,
                    "damping_cycles": 2, "damping": 0.20}}}
    settings.update(maximum_scf_cycles=100, delta_angstrom=[0.0, 0.01, 0.02, 0.04, 0.06])
    return {"protocol_id": adapter.P10, "physical_scan": settings,
        "acceptance": {"energy_identity_hartree": 1.0e-10, "g_anchor_energy_hartree": 1.0e-6,
            "nuclear_formula_hartree": 1.0e-10, "nuclear_symmetry_hartree": 1.0e-10,
            "strict_direction_tolerance_hartree": 1.0e-8}}


class P09P10ContractTests(unittest.TestCase):
    def test_closed_source_permission_is_historical_not_mutated(self):
        original = protocol("P09")
        snapshot = copy.deepcopy(original)
        with patch.object(adapter, "_yaml", return_value=original):
            self.assertIs(adapter._protocol("P09", Path("unused")), original)
        self.assertEqual(original, snapshot)
        self.assertFalse(original["p09_qm_execution_allowed"])

    def test_changed_scientific_setting_is_rejected(self):
        for case, container, key, value in (
                ("P09", "electronic_structure", "pyscf_xc", "B3LYP"),
                ("P09", "electronic_structure", "scf_tolerance_hartree", 1e-8),
                ("P10", "physical_scan", "grid_level", 2),
                ("P10", "physical_scan", "basis", "sto-3g"),
                ("P10", "physical_scan", "maximum_scf_cycles", 101)):
            record = protocol(case)
            record[container][key] = value
            with self.subTest(case=case, key=key), patch.object(adapter, "_yaml", return_value=record):
                with self.assertRaises(ValueError):
                    adapter._protocol(case, Path("unused"))

    def test_changed_conditional_setting_is_rejected(self):
        record = protocol("P09")
        record["smoke_gate"]["conditional_scf"]["damping"] = 0.30
        with patch.object(adapter, "_yaml", return_value=record), self.assertRaises(ValueError):
            adapter._protocol("P09", Path("unused"))

    def test_changed_scan_order_is_rejected(self):
        record = protocol()
        record["physical_scan"]["delta_angstrom"] = [0.0, 0.02, 0.01, 0.04, 0.06]
        with patch.object(adapter, "_yaml", return_value=record), self.assertRaises(ValueError):
            adapter._protocol("P10", Path("unused"))

    def test_unknown_case_cannot_authorize_a_molecule_or_task(self):
        for case in ("P11", "p09", "single-point", "../P09", None):
            with self.subTest(case=case), self.assertRaises(ValueError):
                adapter._case(case)

    def test_exact_positive_initial_absent_energy_delta_becomes_null(self):
        record = {"conditional": {"history": [{"energy_change_hartree": math.inf},
                                             {"energy_change_hartree": 0.1}]}}
        changes = []
        normalized = adapter._normalize(record, changes=changes)
        self.assertIsNone(normalized["conditional"]["history"][0]["energy_change_hartree"])
        self.assertEqual(changes, ["conditional/history/0/energy_change_hartree"])
        self.assertEqual(record["conditional"]["history"][0]["energy_change_hartree"], math.inf)
        json.dumps(normalized, allow_nan=False)

    def test_other_nonfinite_values_never_become_null(self):
        for record in ({"energy": math.inf}, {"history": [{"energy_change_hartree": -math.inf}]},
                {"history": [{"energy_change_hartree": math.nan}]},
                {"history": [{"energy_change_hartree": 0.0}, {"energy_change_hartree": math.inf}]}):
            with self.subTest(record=record), self.assertRaises(ValueError):
                adapter._normalize(record)

    def test_source_json_hash_and_original_bytes_are_preserved(self):
        filename = "data/processed/p09_cyclobutadiene_fixed_geometry_smoke_v0.1.json"
        raw = b'{"history":[{"energy_change_hartree": Infinity}]}\r\n'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / filename
            path.parent.mkdir(parents=True)
            path.write_bytes(raw)
            record, evidence = adapter._json(Path(directory), filename)
            self.assertIsNone(record["history"][0]["energy_change_hartree"])
            self.assertTrue(evidence["original_bytes_preserved"])
            self.assertEqual(path.read_bytes(), raw)

    def test_duplicate_json_keys_are_rejected(self):
        filename = "data/processed/p09_cyclobutadiene_fixed_geometry_smoke_v0.1.json"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / filename
            path.parent.mkdir(parents=True)
            path.write_text('{"protocol_id":"good","protocol_id":"other"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                adapter._json(Path(directory), filename)

    def test_source_asset_cannot_escape_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                adapter._file(Path(directory), "../README.md")

    def test_live_requires_prepare_before_held_guard(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            adapter.live("P09", Path(directory))

    def test_failed_scoped_checks_cannot_pass(self):
        result = adapter._finish(adapter._base("P10", "live"), {"converged": True, "identity": False})
        self.assertEqual(result["status"], "NOT_QUALIFIED")
        self.assertEqual(result["failed_checks"], ["identity"])
        self.assertFalse(result["production_label"])
        self.assertFalse(result["historical_scientific_verdict_changed"])

    def test_count_caps_do_not_enable_optimizers_or_user_conditional_compute(self):
        p09, p10 = adapter._base("P09", "live"), adapter._base("P10", "live")
        self.assertEqual(p09["count_caps"]["scf_kernel"], 1)
        self.assertEqual(p09["count_caps"]["conditional_NR"], 101)
        self.assertEqual(p10["count_caps"]["scf_kernel"], 5)
        self.assertEqual(p10["count_caps"]["conditional_NR"], 0)
        for value in (p09, p10):
            self.assertEqual(value["count_caps"]["geometry_optimizer"], 0)
            self.assertEqual(value["legacy_conditional_user_compute"], "BLOCKED")


class P10ArithmeticTests(unittest.TestCase):
    def setUp(self):
        # A non-scientific, exactly controlled quadratic fixture. No PySCF.
        self.helper = types.SimpleNamespace(
            nuclear_repulsion=lambda atoms: 10.0+5.0*float(atoms[0])**2,
            d3h_atoms=lambda mean, delta, ch: [delta], mean_ring_cc_length=lambda atoms: 1.4,
            mean_ch_length=lambda atoms: 1.0)
        self.g = {"protocol_id": adapter.P09, "smoke_gate_verdict": "PASS",
                  "optimized_G_geometry": {"atoms_angstrom": [0.0]},
                  "ordinary_G_state": {"total_energy_hartree": -100.0}}
        self.gl = {"protocol_id": adapter.P09, "calculation_gate_verdict": "PASS",
                   "GL_state": {"total_energy_hartree": -99.0, "nuclear_repulsion_hartree": 12.0,
                                "electronic_energy_hartree": -111.0}}
        self.points = [{"delta_angstrom": delta, "converged": True,
                        "total_energy_hartree": -100.0+2.0*delta**2,
                        "nuclear_repulsion_hartree_pyscf": 10.0+5.0*delta**2}
                       for delta in protocol()["physical_scan"]["delta_angstrom"]]

    def record(self, points=None):
        return adapter._p10_record(protocol(), self.g, self.gl, self.points if points is None else points, self.helper)

    def test_original_seventeen_check_names_are_preserved(self):
        record = self.record()
        self.assertEqual(len(record["acceptance_checks"]), 17)
        self.assertTrue(all(record["acceptance_checks"].values()))
        curvature = record["ordinary_RKS_BLA_scan"]["quadratic_curvatures_hartree_per_angstrom2"]
        self.assertAlmostEqual(curvature["electronic"], -6.0, places=8)
        self.assertAlmostEqual(curvature["nuclear"], 10.0, places=8)
        self.assertAlmostEqual(curvature["total"], 4.0, places=8)

    def test_failed_first_scf_is_not_hidden_by_other_four_points(self):
        points = copy.deepcopy(self.points)
        points[0]["converged"] = False
        self.assertFalse(self.record(points)["acceptance_checks"]["all_scan_SCF_converged"])

    def test_truncated_or_reordered_scan_cannot_qualify(self):
        for points in (self.points[:4], list(reversed(self.points))):
            with self.subTest(points=points), self.assertRaises(ValueError):
                self.record(points)

    def test_ordinary_energy_raises_recompute_direction_instead_of_trusting_saved_flags(self):
        points = copy.deepcopy(self.points)
        points[1]["total_energy_hartree"] += 0.1
        self.assertFalse(self.record(points)["acceptance_checks"]["ordinary_electronic_energy_favors_BLA"])

    def test_nuclear_formula_difference_uses_frozen_tolerance(self):
        points = copy.deepcopy(self.points)
        points[2]["nuclear_repulsion_hartree_pyscf"] += 1e-8
        self.assertFalse(self.record(points)["acceptance_checks"]["independent_nuclear_formula_matches_pyscf"])

    def test_endpoint_energy_nonclosure_is_not_masked_by_historical_pass(self):
        self.gl["GL_state"]["electronic_energy_hartree"] += 1e-8
        self.assertFalse(self.record()["acceptance_checks"]["endpoint_energy_identity_closed"])


class P09LedgerTests(unittest.TestCase):
    def setUp(self):
        self.protocol = protocol("P09")
        self.protocol.update(tolerances={"energy_path_closure_hartree": 1.0e-8,
                                        "quantitative_source_difference_kcal_mol": 5.0},
            blind_comparison_values={"cyclobutadiene_ADE_kcal_mol": 0.2*adapter.KCAL,
                                     "benzene_ESE_kcal_mol": -1.3*adapter.KCAL})
        self.cbd = {"protocol_id": adapter.P09, "G_energy_hartree": -1.0,
            "DSI_at_G_energy_hartree": -1.1, "GL_state": {"total_energy_hartree": -1.2},
            "VDE_hartree": 0.1, "ADE_hartree": 0.2, "ADE_kcal_mol": 0.2*adapter.KCAL,
            "GL_relaxation_from_DSI_hartree": 0.1, "calculation_gate_verdict": "PASS",
            "acceptance_checks": {"fixture": True}, "production_labels_allowed": False,
            "ai_training_allowed": False}
        self.benzene = {"protocol_id": adapter.P09, "G_energy_hartree": -10.0,
            "GL_state": {"total_energy_hartree": -9.0}, "GE1_state": {"total_energy_hartree": -8.9},
            "delta_E_A_hartree": -1.0, "delta_E_A1_hartree": 0.1,
            "ESE_hartree": -1.3, "ESE_kcal_mol": -1.3*adapter.KCAL,
            "calculation_gate_verdict": "PASS", "acceptance_checks": {"fixture": True},
            "production_labels_allowed": False, "ai_training_allowed": False}
        self.conclusion = {"verdict": "P09_SCOPED_PROPOSITION_SUPPORTED",
            "systems": {"cyclobutadiene": {"ADE_kcal_mol": 0.2*adapter.KCAL},
                        "benzene": {"ESE_kcal_mol": -1.3*adapter.KCAL}},
            "production_label": False, "training_eligible": False, "universal_aromaticity_law": False}

    def run_ledger(self):
        with patch.object(adapter, "_protocol", return_value=self.protocol), \
                patch.object(adapter, "_read_records", return_value=({
                    "cbd": self.cbd, "benzene": self.benzene, "conclusion": self.conclusion}, [])), \
                patch.object(adapter, "prepare", side_effect=AssertionError("Ledger must not prepare PySCF")):
            return adapter.ledger("P09", Path("synthetic"))

    def test_ledger_reconstructs_energy_from_states_without_backend(self):
        result = self.run_ledger()
        self.assertEqual(result["status"], "PASS")
        self.assertAlmostEqual(result["cyclobutadiene"]["ADE_hartree"], 0.2)
        self.assertAlmostEqual(result["benzene"]["ESE_hartree"], -1.3)
        self.assertEqual(result["observed_new_scf_kernel_calls"], 0)

    def test_saved_ADE_tamper_fails_even_with_all_historical_gates_true(self):
        self.cbd["ADE_hartree"] += 1e-7
        result = self.run_ledger()
        self.assertEqual(result["status"], "NOT_QUALIFIED")
        self.assertIn("cbd_ADE_recomputed", result["failed_checks"])

    def test_historical_state_energy_tamper_fails(self):
        self.benzene["GE1_state"]["total_energy_hartree"] += 1e-6
        result = self.run_ledger()
        self.assertEqual(result["status"], "NOT_QUALIFIED")
        self.assertIn("benzene_delta_A1_recomputed", result["failed_checks"])

    def test_nonproduction_and_nonuniversal_flags_are_preserved(self):
        self.conclusion["universal_aromaticity_law"] = True
        result = self.run_ledger()
        self.assertEqual(result["status"], "NOT_QUALIFIED")
        self.assertIn("nonproduction_records", result["failed_checks"])


class P09MockedLiveContractTests(unittest.TestCase):
    """Engineering fake only: test post-calculation qualification, never chemistry."""
    def run_mocked(self, historic_delta=0.0):
        p = protocol("P09")
        p["tolerances"] = {"rerun_energy_difference_hartree": 1e-8}
        p["smoke_gate"].update(maximum_memory_mb=6000, initial_atoms=[["C", 0, 0, 0]],
            acceptance={"electron_count_tolerance": 1e-7, "matrix_zero_tolerance": 1e-12,
                        "energy_component_closure_hartree": 1e-10,
                        "commutator_frobenius_tolerance": 1e-6,
                        "idempotency_relative_tolerance": 1e-7})
        ordinary = {"converged": True, "total_energy_hartree": -154.0,
            "physical_metric_electron_count": 28.0,
            "stability": {"internal_stability_checked": True, "internally_stable": False}}
        conditional = {"converged": True, "total_energy_hartree": -155.0,
            "masked_metric_electron_count": 28.0, "masked_overlap_cross_pi_max_abs": 0.0,
            "conditional_fock_cross_pi_max_abs": 0.0, "deleted_eri_count": 10,
            "energy_component_closure_residual_hartree": 0.0, "final_commutator_frobenius_norm": 0.0,
            "closed_shell_idempotency_relative_residual": 0.0, "occupied_virtual_gap_hartree": 0.2,
            "history": [{"energy_change_hartree": math.inf}]}
        mol = types.SimpleNamespace(nelectron=28, charge=0, spin=0)
        helper = types.SimpleNamespace(build_molecule=lambda _: mol, build_mean_field=lambda *_: object(),
            ordinary_state=lambda _: (ordinary, np.eye(1)), compact_conditional=lambda value: value,
            geometry_hash=lambda _: "ENGINEERING_FAKE")
        modules = {"helper": helper, "lib": types.SimpleNamespace(num_threads=lambda _: None),
            "p09_ao_classification": types.SimpleNamespace(classify_planar_pyscf_aos=lambda *_: ()),
            "p09_conditional_scf": types.SimpleNamespace(run_p09_conditional_rks=lambda *a, **kw: conditional)}
        history = {"ordinary_G_like_state": {"total_energy_hartree": -154.0+historic_delta},
                   "conditional_DSI_state": {"total_energy_hartree": -155.0}}
        with patch.object(adapter, "_modules", return_value=modules), \
                patch.object(adapter, "_protocol", return_value=p), \
                patch.object(adapter, "_yaml", return_value={"exchange_integral_classes": [{}]*15}), \
                patch.object(adapter, "_json", return_value=(history, {"fixture": "ENGINEERING_FAKE"})):
            return adapter.live("P09", Path("engineering-fake"))

    def test_rerun_mismatch_cannot_pass_after_twelve_numerical_gates(self):
        result = self.run_mocked(historic_delta=1e-7)
        self.assertEqual(len(result["original_smoke_checks"]), 12)
        self.assertTrue(all(result["original_smoke_checks"].values()))
        self.assertEqual(result["status"], "NOT_QUALIFIED")
        self.assertEqual(result["failed_checks"], ["historical_rerun_comparison"])

    def test_stability_report_is_not_falsely_promoted_to_a_stable_minimum(self):
        result = self.run_mocked()
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["ordinary_G_like_state"]["stability"]["internally_stable"])
        self.assertFalse(result["energy_difference_is_final_VDE_ADE_or_ESE"])
        self.assertIsNone(result["conditional_DSI_state"]["history"][0]["energy_change_hartree"])


class P09FifteenClassMaskTests(unittest.TestCase):
    def test_all_fifteen_reference_inplace_and_scalar_masks_agree(self):
        """Full 15 source classes, tiny symbolic tensor, no integral/backend call."""
        # Import only the two NumPy/scalar modules under a private test package.
        qm = SOURCE / "src/ai4orgchem/qm"
        package_name = "_p09_fifteen_class_fixture"
        package = types.ModuleType(package_name)
        package.__path__ = [str(qm)]
        with patch.dict(sys.modules, {package_name: package}):
            predicate = importlib.import_module(package_name+".p09_eri_mask")
            energy = importlib.import_module(package_name+".p09_energy_assembly")
            raw = (SOURCE / "configs/qm/p09_exchange_integral_classes_v0.1.yaml").read_text(encoding="utf-8")
            # Read the source's fifteen explicit inline predicate records only.
            pattern = r"- id: (X\d\d)[\s\S]*?index_predicate: \{bra: \[([^]]*)\], ket: \[([^]]*)\], constraints: \[([^]]*)\]\}"
            rows = re.findall(pattern, raw)
            self.assertEqual([row[0] for row in rows], [f"X{index:02d}" for index in range(1, 16)])
            entries = [{"id": row[0], "index_predicate": {
                key: [item.strip() for item in value.split(",") if item.strip()]
                for key, value in zip(("bra", "ket", "constraints"), row[1:])}} for row in rows]
            descriptors = (predicate.AODescriptor("sigma"), predicate.AODescriptor("sigma"),
                predicate.AODescriptor("pi", "A"), predicate.AODescriptor("pi", "A"),
                predicate.AODescriptor("pi", "B"), predicate.AODescriptor("pi", "C"))
            size = len(descriptors)
            original = np.arange(1, size**4+1, dtype=float).reshape((size,)*4)
            reference, mask = energy.apply_eri_tensor_mask(original, descriptors, entries)
            inplace = original.copy()
            deleted = energy.apply_eri_tensor_mask_inplace_by_category(inplace, descriptors, entries)
            np.testing.assert_array_equal(reference, inplace)
            self.assertEqual(deleted, int(np.count_nonzero(mask)))
            allowed, denied = 0, 0
            for indices in itertools.product(range(size), repeat=4):
                scalar = predicate.should_delete_eri(tuple(descriptors[index] for index in indices), entries)
                self.assertEqual(bool(mask[indices]), scalar)
                if scalar:
                    denied += 1
                    self.assertEqual(inplace[indices], 0.0)
                else:
                    allowed += 1
                    self.assertEqual(inplace[indices], original[indices])
            self.assertGreater(allowed, 0)
            self.assertGreater(denied, 0)
            np.testing.assert_array_equal(original, np.arange(1, size**4+1, dtype=float).reshape((size,)*4))


if __name__ == "__main__":
    unittest.main()
