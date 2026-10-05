"""Array witnesses and fake-engine plumbing, never real molecular SCF/ERI."""
import ast
import copy
import json
import os
from pathlib import Path
import types
import unittest
from unittest.mock import patch

import numpy as np

from reference import ordinary_molecule as reference

ROOT = Path(__file__).resolve().parents[1]


class FakeGrid:
    def __init__(self):
        self.coords = None
        self.weights = None
        self.calls = []

    def build(self, **kwargs):
        self.calls.append(kwargs)
        self.coords = np.array([[0., 0., 0.], [1., 0., 0.]])
        self.weights = np.ones(2)


class FakeMolecule:
    """Two-AO analytical model, deliberately not a chemical molecule."""
    nelectron, cart, spin = 2, False, 0

    def __init__(self, **kwargs):
        self.configuration = kwargs
        self._basis = {"C": [[1, [1., 1.]]]}
        self.integral_calls = []

    def nao_nr(self):
        return 2

    def ao_labels(self, fmt=False):
        return [(0, "C", "2p", "z"), (1, "C", "2p", "z")]

    def intor(self, name, **kwargs):
        self.integral_calls.append((name, kwargs))
        return {"int1e_ovlp_sph": np.eye(2), "int1e_kin_sph": np.diag([-1., 1.]),
            "int1e_nuc_sph": np.zeros((2, 2)), "int2e_sph": np.zeros((2,) * 4)}[name].copy()

    def energy_nuc(self):
        return 0.


class FakeMeanField:
    def __init__(self, molecule):
        self.mol = molecule
        self.grids = FakeGrid()
        self._numint = types.SimpleNamespace(
            rsh_and_hybrid_coeff=lambda xc, spin: (0., .2, .2),
            nr_rks=lambda mol, grids, xc, density, **kwargs: (float(np.trace(density)), 0., np.zeros((2, 2))))
        self.converged, self.cycles = True, 2
        self.mo_coeff, self.mo_energy, self.mo_occ = np.eye(2), np.array([-1., 1.]), np.array([2., 0.])
        self.kernel_calls = 0

    def kernel(self):
        self.kernel_calls += 1
        self.callback({"cycle": 0, "e_tot": -2., "norm_gorb": 0., "norm_ddm": 0.})
        return -2.

    def make_rdm1(self):
        return np.diag([2., 0.])


def fake_modules():
    gen_grid = types.SimpleNamespace(nwchem_prune=object(), original_becke=object())
    radi = types.SimpleNamespace(treutler=object(), treutler_atomic_radii_adjust=object(), BRAGG_RADII=np.ones(120))
    dft = types.SimpleNamespace(RKS=FakeMeanField, gen_grid=gen_grid, radi=radi)
    module = types.SimpleNamespace(dft=dft, gto=types.SimpleNamespace(M=FakeMolecule),
                                   lib=types.SimpleNamespace(num_threads=lambda count: None))
    return {"pyscf": module, "pyscf.dft": dft}


class OrdinaryReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = json.loads((ROOT / "profiles/user-molecule/pilot-b3lypg-sto3g-grid2-v1.json").read_text())
        cls.request = {"charge": 0, "multiplicity": 1, "coordinate_unit": "angstrom",
            "resources": {"threads": 1}, "fragments": [
                {"id": "A", "carbon_atom_indices_1based": [1]},
                {"id": "B", "carbon_atom_indices_1based": [2]}]}
        cls.atoms = [["C", [0., 0., 0.]], ["C", [1.3, 0., 0.]]]
        cls.source = Path(os.environ.get("AI4ORGCHEM_SOURCE", "/opt/ai4orgchem"))
        cls.rules = cls.source / "configs/qm/p09_exchange_integral_classes_v0.1.yaml"
        cls.rule_hash = json.loads((ROOT / "locks/source.user-molecule.lock.json").read_text())["condition_rules_sha256"]

    def run_fake(self, **kwargs):
        with patch.dict("sys.modules", fake_modules()), patch.object(reference.importlib.metadata, "version",
                side_effect=self.profile["expected_dependencies"].__getitem__):
            return reference.run_ordinary(self.request, self.atoms, self.profile, **kwargs)

    def test_no_production_import_or_helper_calls(self):
        source = Path(reference.__file__).read_text()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [node.module or ""] if isinstance(node, ast.ImportFrom) else [name.name for name in node.names]
                self.assertFalse(any(name.startswith("ai4orgchem") for name in names))
        for forbidden in ("run_p09_conditional_rks", "restricted_jk", "_evaluate_density", "user_molecule_adapter"):
            self.assertNotIn(forbidden, source)

    def test_ordinary_energy_coefficients_and_no_conditional_projection(self):
        d = np.array([[1., .25], [.25, .5]])
        eri = np.arange(16.).reshape((2,) * 4) / 10
        result = reference.ordinary_evaluate(d, np.diag([-1., .5]), np.eye(2), eri, .2, 1.5,
                                             lambda dm: (float(np.trace(dm)), -.3, np.diag([.1, .2])))
        np.testing.assert_allclose(result["J"], [[.225, 1.025], [1.825, 2.625]], atol=1e-15, rtol=0)
        np.testing.assert_allclose(result["K"], [[.375, .775], [1.975, 2.375]], atol=1e-15, rtol=0)
        self.assertAlmostEqual(result["components_hartree"]["one_electron"], -.75)
        self.assertAlmostEqual(result["components_hartree"]["coulomb"], 1.125)
        self.assertAlmostEqual(result["components_hartree"]["exact_exchange"], -.1125)
        self.assertAlmostEqual(result["total_energy_hartree"], 1.4625)
        self.assertNotEqual(result["Fraw"][0, 1], 0.)
        np.testing.assert_array_equal(d, [[1., .25], [.25, .5]])

    def test_invalid_functional_arrays_and_nonfinite_xc_rejected(self):
        values = dict(density=np.eye(2), hcore=np.eye(2), overlap=np.eye(2), eri=np.zeros((2,) * 4),
                      hybrid=.2, nuclear=0., xc=lambda dm: (2., 0., np.zeros((2, 2))))
        for key, bad in (("eri", np.zeros((2, 2))), ("density", np.full((2, 2), np.nan)),
                         ("hybrid", 2.), ("xc", lambda dm: (2., float("nan"), np.zeros((2, 2))))):
            with self.subTest(key=key), self.assertRaises(ValueError):
                reference.ordinary_evaluate(**dict(values, **{key: bad}))

    def test_build_freezes_explicit_configuration_without_grid_or_scf(self):
        with patch.dict("sys.modules", fake_modules()), patch.object(reference.importlib.metadata, "version",
                side_effect=self.profile["expected_dependencies"].__getitem__):
            context = reference.build(self.request, self.atoms, self.profile)
        self.assertEqual(context.mean_field.kernel_calls, 0)
        self.assertEqual(context.mean_field.grids.calls, [])
        self.assertEqual(context.mol.integral_calls, [])
        self.assertEqual(context.mol.configuration["unit"], "Angstrom")
        self.assertFalse(context.mol.configuration["cart"])
        self.assertFalse(context.mol.configuration["symmetry"])
        self.assertEqual(context.mol.configuration["ecp"], {})
        self.assertEqual(context.metadata["ordinary_effective"], self.profile["ordinary"])
        self.assertEqual(context.metadata["ao_descriptors"], [{"kind": "pi", "fragment": "A"}, {"kind": "pi", "fragment": "B"}])
        self.assertEqual(context.metadata["scientific_scope_approval"], "NOT_GRANTED")
        self.assertFalse(self.profile["compute_enabled"])

    def test_unsupported_grid_units_mapping_threads_and_orientation_fail_before_build(self):
        modifications = [({"coordinate_unit": "bohr"}, None, None), ({"charge": False}, None, None),
            ({"resources": {"threads": 2}}, None, None),
            ({"fragments": [{"id": "A", "carbon_atom_indices_1based": [1]}, {"id": "B", "carbon_atom_indices_1based": [1]}]}, None, None),
            ({}, [["C", [0., 0., .1]], ["C", [1., 0., 0.]]], None),
            ({}, None, {"grid": dict(self.profile["grid"], prune="other")}),
            ({}, None, {"ordinary": dict(self.profile["ordinary"], conv_tol=float("nan"))})]
        for request_change, atoms, profile_change in modifications:
            with self.subTest(change=(request_change, profile_change)), self.assertRaises(ValueError):
                reference.build(dict(self.request, **request_change), self.atoms if atoms is None else atoms,
                                dict(self.profile, **(profile_change or {})))

    def test_dependency_and_nao_cap_rejected_before_any_grid_or_integral(self):
        with patch.dict("sys.modules", fake_modules()), patch.object(reference.importlib.metadata, "version", return_value="0"):
            with self.assertRaisesRegex(ValueError, "dependencies"):
                reference.build(self.request, self.atoms, self.profile)
        with patch.dict("sys.modules", fake_modules()), patch.object(reference.importlib.metadata, "version",
                side_effect=self.profile["expected_dependencies"].__getitem__), patch.object(FakeMolecule, "nao_nr", return_value=41):
            with self.assertRaisesRegex(ValueError, "before ERI"):
                reference.build(self.request, self.atoms, self.profile)

    def test_fake_engine_ordinary_recomputes_metrics_and_separates_json_arrays(self):
        phases = []
        result = self.run_fake(progress=phases.append)
        self.assertEqual(phases, ["GRID_BUILD", "ORDINARY_SCF", "RAW_INTEGRALS", "ORDINARY_RECOMPUTE"])
        self.assertEqual(result.context.mean_field.grids.calls, [{"with_non0tab": True}])
        self.assertEqual(result.record["total_energy_hartree"], -2.)
        self.assertEqual(result.record["independent_functional_energy_hartree"], -2.)
        self.assertTrue(all(result.record["qualification_tests"].values()))
        self.assertEqual(result.record["final_non_diis_gap_hartree"], 2.)
        self.assertEqual(result.record["final_operator_source"], reference.FINAL_OPERATOR)
        self.assertEqual(result.record["variational_status"], "NOT_ESTABLISHED")
        self.assertEqual(result.record["stability_analysis"], "NOT_EXECUTED")
        self.assertEqual(result.record["research_status"], "NOT_QUALIFIED")
        self.assertEqual(result.record["grid_points"], 2)
        json.dumps(result.record, allow_nan=False)
        self.assertTrue(all(isinstance(value, np.ndarray) for value in result.arrays.values()))
        np.testing.assert_array_equal(result.arrays["density"], np.diag([2., 0.]))

    def test_array_identity_canonical_order_and_finite_requirement(self):
        array = np.arange(6.).reshape(2, 3)
        self.assertEqual(reference.array_identity(array), reference.array_identity(np.asfortranarray(array)))
        self.assertNotEqual(reference.array_identity(array), reference.array_identity(array + 1))
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            reference.array_identity(np.array([float("inf")]))

    def test_conditional_bridge_analytical_fixed_point_and_frozen_initial_density(self):
        ordinary = self.run_fake()
        phases = []
        result = reference.run_conditional(ordinary, self.rules, self.rule_hash, progress=phases.append)
        self.assertEqual(phases, ["CONDITIONAL_REFERENCE", "CONDITIONAL_RECOMPUTE"])
        self.assertTrue(result.record["converged"])
        self.assertEqual(result.record["total_energy_hartree"], -2.)
        self.assertEqual(result.record["final_non_diis_gap_hartree"], 2.)
        self.assertEqual(result.record["gap_operator_source"], "LAST_DIAGONALIZATION_POSSIBLY_DIIS")
        self.assertEqual(result.record["molecular_acceptance"], "PENDING_ACCEPTANCE_EVALUATION")
        self.assertEqual(result.record["research_status"], "NOT_QUALIFIED")
        self.assertEqual(result.record["initial_density_identity"], ordinary.record["array_identities"]["density"])
        self.assertEqual(result.record["masked_overlap_cross_pi_max_abs"], 0.)
        self.assertEqual(result.record["conditional_fock_cross_pi_max_abs"], 0.)
        self.assertTrue(all(result.record["qualification_tests"].values()))
        self.assertEqual(result.record["metric_metadata"]["conditional_fock_cross_pi_max_abs"]["operator_source"], reference.FINAL_OPERATOR)
        self.assertFalse(result.record["metric_metadata"]["occupied_virtual_gap_hartree"]["required"])
        json.dumps(result.record, allow_nan=False)
        ordinary.arrays["eri"][0, 0, 0, 0] = .1
        with self.assertRaisesRegex(ValueError, "Frozen ordinary array changed: eri"):
            reference.run_conditional(ordinary, self.rules, self.rule_hash)

    def test_ordinary_nonconvergence_recorded_without_research_approval(self):
        with patch.object(FakeMeanField, "kernel", lambda mf: (setattr(mf, "converged", False) or -2.)):
            result = self.run_fake()
        self.assertFalse(result.record["converged"])
        self.assertFalse(result.record["qualification_tests"]["converged"])
        self.assertEqual(result.record["research_status"], "NOT_QUALIFIED")


if __name__ == "__main__":
    unittest.main()
