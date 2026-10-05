"""Analytical/toy reference checks only: no molecules, SCF engine, grid or ERI engine."""
import ast
import itertools
import json
import os
from pathlib import Path
import unittest

import numpy as np
from reference import user_molecule as ref

ROOT = Path(__file__).resolve().parents[1]
SIGMA, A, B = ref.AO('sigma'), ref.AO('pi', 'A'), ref.AO('pi', 'B')


class ReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('AI4ORGCHEM_SOURCE', '/opt/ai4orgchem'))
        cls.rule_path = source / 'configs/qm/p09_exchange_integral_classes_v0.1.yaml'
        cls.rule_sha = json.loads((ROOT/'locks/source.user-molecule.lock.json').read_text())['condition_rules_sha256']
        cls.entries = ref.load_rules(cls.rule_path, cls.rule_sha)
        cls.settings = dict(maximum_cycles=8, density_tolerance=1e-12, energy_tolerance=1e-12,
            diis_start_cycle=2, diis_space=3, damping_cycles=0, damping=0.2, memory_controlled_eri=True)

    def test_reference_has_no_production_import_or_function_call(self):
        tree = ast.parse(Path(ref.__file__).read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [node.module or ''] if isinstance(node, ast.ImportFrom) else [n.name for n in node.names]
                self.assertFalse(any(name.startswith('ai4orgchem') for name in names), names)
        self.assertNotIn('run_p09_conditional_rks', Path(ref.__file__).read_text())

    def test_exact_rule_identity_required(self):
        with self.assertRaisesRegex(ValueError, 'Rule bytes'):
            ref.load_rules(self.rule_path, '0'*64)

    def test_all_fifteen_ordered_witnesses(self):
        witnesses = [(SIGMA,SIGMA,A,B), (SIGMA,SIGMA,A,B), (A,A,A,B), (A,A,A,B),
            (A,A,A,B), (B,B,A,B), (B,B,A,B), (B,A,B,B), (SIGMA,A,SIGMA,B),
            (SIGMA,B,SIGMA,A), (A,B,SIGMA,SIGMA), (A,B,A,A), (A,B,B,B), (A,B,A,B), (A,B,A,B)]
        for entry, quartet in zip(self.entries, witnesses):
            with self.subTest(entry=entry['id']):
                self.assertTrue(ref.ordered_matches(quartet, entry['index_predicate']))
                self.assertIn(entry['id'], ref.deleted_classes(quartet, self.entries))

    def test_eightfold_closure_and_allowed_integrals(self):
        for quartet in itertools.product((SIGMA, A, B), repeat=4):
            expected = ref.deleted_classes(quartet, self.entries)
            for permuted in ref.permutations(quartet):
                self.assertEqual(expected, ref.deleted_classes(permuted, self.entries))
        for allowed in ((SIGMA,)*4, (A,)*4, (A,A,B,B), (SIGMA,A,SIGMA,A)):
            self.assertFalse(ref.deleted_classes(allowed, self.entries))

    def test_exact_matrix_mask_and_no_source_mutation(self):
        source = np.arange(9.).reshape(3,3)
        original = source.copy()
        actual = ref.project(source, (SIGMA,A,B))
        expected = original.copy(); expected[1,2] = expected[2,1] = 0
        np.testing.assert_array_equal(actual, expected)
        np.testing.assert_array_equal(source, original)

    def test_all_scalar_mask_decisions_and_internal_single_group_control(self):
        raw = np.ones((3,)*4)
        actual, count = ref.mask_integrals(raw, (SIGMA,A,B), self.entries)
        expected = np.ones_like(raw)
        for idx in itertools.product(range(3), repeat=4):
            if ref.deleted_classes(tuple((SIGMA,A,B)[i] for i in idx), self.entries):
                expected[idx] = 0
        np.testing.assert_array_equal(actual, expected)
        self.assertEqual(count, int(np.count_nonzero(expected == 0)))
        np.testing.assert_array_equal(raw, np.ones_like(raw))
        control, count = ref.mask_integrals(raw, (SIGMA,A,A), self.entries)
        np.testing.assert_array_equal(control, raw); self.assertEqual(count, 0)

    def test_non_diagonal_same_density_jk_and_hand_ledger(self):
        eri = np.arange(16.).reshape((2,)*4) / 10
        d = np.array([[1.0,0.25],[0.25,0.5]])
        j, k = ref.scalar_jk(d, eri)
        # Independently enumerated decimal values; asymmetric tensor is intentional
        # for index sensitivity in this contraction-only mathematical witness.
        np.testing.assert_allclose(j, [[.225,1.025],[1.825,2.625]], atol=1e-15, rtol=0)
        np.testing.assert_allclose(k, [[.375,.775],[1.975,2.375]], atol=1e-15, rtol=0)
        h = np.diag([-1.0,0.5]); s = np.eye(2)
        actual = ref.evaluate(d,h,s,s,eri,(SIGMA,SIGMA),.2,1.5,
                              lambda dm: (float(np.trace(dm)), -.3, np.diag([.1,.2])))
        np.testing.assert_allclose(actual['J'], j, atol=1e-15, rtol=0)
        np.testing.assert_allclose(actual['K'], k, atol=1e-15, rtol=0)
        self.assertAlmostEqual(actual['components_hartree']['one_electron'], -.75)
        self.assertAlmostEqual(actual['components_hartree']['coulomb'], 1.125)
        self.assertAlmostEqual(actual['components_hartree']['exact_exchange'], -.1125)
        self.assertAlmostEqual(actual['total_energy_hartree'], 1.4625)

    def run_toy(self, **changes):
        kwargs = dict(density=np.diag([2.,0.]), h=np.diag([-1.,1.]), overlap=np.eye(2),
            eri=np.zeros((2,)*4), aos=(A,B), entries=self.entries, electrons=2,
            hybrid=.2, nuclear=0., xc=lambda dm:(float(np.trace(dm)),0.,np.zeros((2,2))),
            settings=self.settings.copy())
        kwargs.update(changes)
        return ref.fixed_point(**kwargs)

    def test_analytical_complete_iteration_global_occupation_and_final_metrics(self):
        result = self.run_toy()
        self.assertTrue(result['converged']); self.assertEqual(result['cycles'], 2)
        self.assertEqual(result['total_energy_hartree'], -2.)
        np.testing.assert_array_equal(result['mo_occupations'], [2.,0.])
        self.assertEqual(result['masked_metric_electron_count'], 2.)
        self.assertEqual(result['final_commutator_frobenius_norm'], 0.)
        self.assertEqual(result['closed_shell_idempotency_relative_residual'], 0.)
        self.assertIsNone(result['history'][0]['energy_change_hartree'])
        self.assertEqual(result['occupied_virtual_gap_hartree'], 2.)
        self.assertEqual(result['gap_operator_source'], 'LAST_DIAGONALIZATION_POSSIBLY_DIIS')
        self.assertEqual(result['final_operator_source'], 'RECOMPUTED_AT_RETURNED_DENSITY_NO_DIIS')
        self.assertEqual(result['molecular_acceptance'], 'NOT_EXECUTED')

    def test_failure_nonfinite_nonpositive_metric_and_iteration_limit(self):
        with self.assertRaisesRegex(ValueError, 'not positive'):
            self.run_toy(overlap=np.diag([-1.,1.]))
        with self.assertRaisesRegex(ValueError, 'Nonfinite'):
            self.run_toy(xc=lambda dm:(2.,float('nan'),np.zeros((2,2))))
        settings = self.settings.copy(); settings['maximum_cycles'] = 1
        result = self.run_toy(settings=settings)
        self.assertFalse(result['converged'])
        self.assertEqual(result['variational_status'], 'NOT_ESTABLISHED')

    def test_complete_iteration_nonorthogonal_metric_and_nonzero_interactions(self):
        metric=np.array([[1.,.2],[.2,1.]])
        result=self.run_toy(overlap=metric,aos=(SIGMA,SIGMA))
        self.assertTrue(result['converged'])
        self.assertAlmostEqual(result['total_energy_hartree'], -2/np.sqrt(.96), places=12)
        self.assertAlmostEqual(result['masked_metric_electron_count'],2.,places=12)
        self.assertLess(result['closed_shell_idempotency_relative_residual'],1e-12)
        self.assertLess(result['final_commutator_frobenius_norm'],1e-12)
        eri=np.zeros((2,)*4); eri[0,0,0,0]=.4; eri[1,1,1,1]=.3
        result=self.run_toy(h=np.diag([-2.,.5]),eri=eri,nuclear=1.)
        self.assertTrue(result['converged'])
        self.assertAlmostEqual(result['components_hartree']['one_electron'],-4.)
        self.assertAlmostEqual(result['components_hartree']['coulomb'],.8)
        self.assertAlmostEqual(result['components_hartree']['exact_exchange'],-.08)
        self.assertAlmostEqual(result['total_energy_hartree'],-2.28)
        self.assertAlmostEqual(result['Fcond'][0,0],-1.28)
        self.assertEqual(result['masked_metric_electron_count'],2.)

    def test_global_full_occupancy_gap_undefined(self):
        result = self.run_toy(electrons=4, density=2*np.eye(2))
        self.assertIsNone(result['occupied_virtual_gap_hartree'])
        self.assertEqual(result['masked_metric_electron_count'], 4.)

    def test_independent_diis_affine_and_singular_fallback(self):
        diis = ref.Pulay(3)
        np.testing.assert_array_equal(diis.update(np.eye(2), np.ones((2,2))), np.eye(2))
        actual = diis.update(3*np.eye(2), np.ones((2,2)))
        self.assertEqual(diis.fallbacks, 1)
        np.testing.assert_allclose(actual, 2*np.eye(2), atol=1e-14)

    def test_rename_and_paired_permutation_preserve_model(self):
        aos, eri, h, d = (SIGMA,A,B), np.ones((3,)*4), np.diag([-2.,-1.,1.]), np.diag([2.,2.,0.])
        st = np.eye(3)
        masked, count = ref.mask_integrals(eri, aos, self.entries)
        swapped = tuple(ref.AO(a.kind, {'A':'B','B':'A'}.get(a.group)) for a in aos)
        mask2, count2 = ref.mask_integrals(eri, swapped, self.entries)
        np.testing.assert_array_equal(masked, mask2); self.assertEqual(count, count2)
        p = np.array([2,0,1])
        mask3, count3 = ref.mask_integrals(eri[np.ix_(p,p,p,p)], tuple(aos[i] for i in p), self.entries)
        self.assertEqual(count, count3)
        np.testing.assert_array_equal(mask3, masked[np.ix_(p,p,p,p)])

    def test_independent_ao_classification_spd_orientation_and_mapping(self):
        labels = [(0,'C','1s',''), (0,'C','2p','z'), (1,'C','3d','xz'), (1,'C','3d','yz'), (1,'C','3d','z^2')]
        coords = [[0,0,0],[1,0,0]]
        self.assertEqual(ref.classify(labels, coords, {'A':[1],'B':[2]}), (SIGMA,A,B,B,SIGMA))
        with self.assertRaisesRegex(ValueError, 'xy plane'):
            ref.classify(labels, [[0,0,.1],[1,0,0]], {'A':[1],'B':[2]})
        with self.assertRaisesRegex(ValueError, 'Unassigned'):
            ref.classify(labels, coords, {'A':[1]})

    def test_limits_before_large_array_copy(self):
        with self.assertRaisesRegex(ValueError, '1..40'):
            ref.mask_integrals(None, (SIGMA,)*41, self.entries)
        with self.assertRaisesRegex(ValueError, 'two pi groups'):
            ref.mask_integrals(np.zeros((3,)*4), (A,B,ref.AO('pi','C')), self.entries)


if __name__ == '__main__':
    unittest.main()
