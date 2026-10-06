"""Frozen cache/seed adapter tests using tiny array XC test doubles only."""
import ast
import hashlib
import os
from pathlib import Path
from types import SimpleNamespace
import unittest

import numpy as np

from reference import residual_candidate as solver
from reference import residual_seed_v2 as adapter
from reference import user_molecule as equations
from reference.ordinary_molecule import MolecularContext, ReferenceResult
from reference.residual_molecule import array_identity


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('AI4ORGCHEM_SOURCE_ROOT', os.environ.get('AI4ORGCHEM_SOURCE', '/opt/ai4orgchem')))
RULES = SOURCE/'configs/qm/p09_exchange_integral_classes_v0.1.yaml'


def forbidden(*args, **kwargs):
    raise AssertionError('Array adapter test called molecular construction/integral/grid/SCF')


class FakeXC:
    def __init__(self, nao):
        self.calls, self.nao, self.mutation = [], nao, None

    def rsh_and_hybrid_coeff(self, xc, spin=0):
        return 0., .2, .2

    def nr_rks(self, mol, grids, xc, density, **kwargs):
        self.calls.append(density.copy())
        if self.mutation:
            self.mutation()
        return float(np.trace(density)), 0., np.zeros((self.nao, self.nao))


class IndependentResidualSeedV2Tests(unittest.TestCase):
    def fixture(self, changed_seed=True, nao=2):
        if changed_seed:
            s = np.array([[1., .2], [.2, 1.]])
            coefficients = np.column_stack((np.ones(2)/np.sqrt(2.4), np.array([1., -1.])/np.sqrt(1.6)))
            occupations = np.array([2., 0.]); occupied = 1
            aos = (equations.AO('pi', 'A'), equations.AO('pi', 'B'))
        else:
            s, coefficients = np.eye(nao), np.eye(nao)
            occupied = 2 if nao == 3 else 1
            occupations = np.array([2.]*occupied+[0.]*(nao-occupied))
            aos = (equations.AO('sigma'),)*nao
        d0 = 2*coefficients[:, :occupied]@coefficients[:, :occupied].T
        raw = FakeXC(nao)
        grids = SimpleNamespace(coords=np.zeros((1, 3)), weights=np.ones(1), level=2, build=forbidden)
        mol = SimpleNamespace(nelectron=2*occupied, spin=0, cart=False,
                              intor=forbidden, energy_nuc=forbidden, kernel=forbidden)
        mf = SimpleNamespace(mol=mol, grids=grids, _numint=raw, xc='B3LYPG', max_memory=512,
                             kernel=forbidden, get_hcore=forbidden, get_ovlp=forbidden)
        h = np.diag([-1., 1.] if nao == 2 else [-1., -.5, 1.])
        arrays = {'density': d0, 'overlap': s, 'hcore': h, 'eri': np.zeros((nao,)*4),
                  'grid_coords': grids.coords.copy(), 'grid_weights': grids.weights.copy(),
                  'mo_coefficients': coefficients, 'mo_occupations': occupations}
        import json
        profile = json.loads((ROOT/'profiles/user-molecule/pilot-b3lypg-sto3g-grid2-v1.json').read_text(encoding='utf-8'))
        context = MolecularContext(mol, mf, aos, {'engine': 'ENGINEERING_FAKE'}, profile)
        record = {'converged': True, 'qualification_tests': {'test_double_only': True},
                  'components_hartree': {'nuclear_repulsion': 0.},
                  'array_identities': {key: array_identity(value) for key, value in arrays.items()}}
        return ReferenceResult(record, arrays, context), raw

    def construct(self, ordinary, **options):
        return adapter.PreparedResidualSeedReferenceV2(ordinary=ordinary, rule_path=RULES,
            expected_sha256=hashlib.sha256(RULES.read_bytes()).hexdigest(), **options)

    def test_constructs_real_seed_without_callback_or_cache_mutation(self):
        ordinary, raw = self.fixture()
        saved = {key: array.copy() for key, array in ordinary.arrays.items()}
        runner = self.construct(ordinary)
        np.testing.assert_allclose(runner.seed_density, np.ones((2, 2)), rtol=0, atol=1e-14)
        self.assertNotEqual(solver.density_id(runner.seed_density), solver.density_id(ordinary.arrays['density']))
        self.assertEqual(raw.calls, [])
        self.assertEqual(runner.seed_receipt['production_density_reconstruction'],
                         'NOT_IMPLEMENTED_IN_EXISTING_REFERENCE_ENTRY')
        for key, array in saved.items():
            np.testing.assert_array_equal(ordinary.arrays[key], array)

    def test_actual_v2_policy_and_parent_identity_survive_lower_solver(self):
        ordinary, raw = self.fixture()
        runner = self.construct(ordinary)
        result = runner.run(maximum_iterations=1)
        initialization = result['initialization']
        self.assertEqual(initialization['policy'], adapter.POLICY_ID)
        self.assertEqual(initialization['lower_solver_policy'], adapter.LOWER_POLICY)
        self.assertEqual(initialization['ordinary_density_id'], solver.density_id(ordinary.arrays['density']))
        self.assertEqual(initialization['lower_solver_density_argument_id'], solver.density_id(runner.seed_density))
        self.assertEqual(result['seed_receipt']['actual_reference_entry_execution'],
                         'EXECUTED_UNCHANGED_LOW_LEVEL_FRAME_CHECKS')
        self.assertEqual(initialization['seed_receipt']['actual_reference_entry_execution'],
                         'EXECUTED_UNCHANGED_LOW_LEVEL_FRAME_CHECKS')
        self.assertEqual(runner.seed_receipt['actual_reference_entry_execution'], 'NOT_EXECUTED_BEFORE_RUN')
        self.assertNotEqual(initialization['ordinary_density_id'], initialization['seed_density_id'])
        np.testing.assert_array_equal(raw.calls[0], runner.seed_density)
        self.assertEqual(result['phase_mapping_status'], 'COMPLETE')
        self.assertEqual(len(raw.calls), result['global_evaluation_count'])
        self.assertEqual([row['phase'] for row in result['prepared_evaluation_ledger']],
                         [row['phase'] for row in result['evaluation_ledger']])
        self.assertTrue(result['prepared_budget_settled'])
        self.assertFalse(result['production_activation'])
        self.assertEqual(result['molecular_execution'], 'NOT_EXECUTED_ENGINEERING_FAKE')
        self.assertIsNotNone(result['last_evaluation'])
        self.assertIsNotNone(result['last_snapshot'])

    def test_shared_exact_seed_rechecks_and_uses_same_bytes(self):
        ordinary, raw = self.fixture()
        independent = self.construct(ordinary)
        shared = independent.seed_density.copy()
        runner = self.construct(ordinary, shared_seed_density=shared)
        checks = runner.seed_receipt['shared_seed_admission']['checks']
        self.assertEqual(set(checks), {'symmetry', 'independent_seed_agreement',
                                      'white_projector_trace', 'white_projector_idempotency'})
        self.assertTrue(all(value['passed'] for value in checks.values()))
        np.testing.assert_array_equal(runner.seed_density, shared)
        runner.evaluate(runner.seed_density)
        np.testing.assert_array_equal(raw.calls[0], shared)

    def test_shared_wrong_seed_refused_before_callback(self):
        ordinary, raw = self.fixture()
        with self.assertRaises(ValueError) as caught:
            self.construct(ordinary, shared_seed_density=ordinary.arrays['density'])
        self.assertEqual(caught.exception.reason, 'SHARED_SEED_INDEPENDENT_SEED_AGREEMENT_FAILED')
        self.assertEqual(raw.calls, [])

    def test_shared_white_count_stricter_than_seed_agreement(self):
        ordinary, raw = self.fixture(changed_seed=False, nao=3)
        shared = ordinary.arrays['density']*(1.+9e-11)
        with self.assertRaises(ValueError) as caught:
            self.construct(ordinary, shared_seed_density=shared)
        self.assertEqual(caught.exception.reason, 'SHARED_SEED_WHITE_PROJECTOR_TRACE_FAILED')
        self.assertTrue(caught.exception.receipt['shared_seed_admission']['checks']['independent_seed_agreement']['passed'])
        self.assertEqual(raw.calls, [])

    def test_missing_or_mismatched_mo_cache_identity_refused(self):
        for key in adapter.MO_KEYS:
            ordinary, raw = self.fixture()
            del ordinary.record['array_identities'][key]
            with self.assertRaises(ValueError): self.construct(ordinary)
            self.assertEqual(raw.calls, [])
            ordinary, raw = self.fixture(); ordinary.arrays[key].flat[0] += .001
            with self.assertRaises(ValueError) as caught: self.construct(ordinary)
            self.assertEqual(caught.exception.reason, 'FROZEN_CACHED_MO_MISMATCH')
            self.assertEqual(raw.calls, [])

    def test_caller_mo_mutation_before_and_during_callback_refused(self):
        ordinary, raw = self.fixture(); runner = self.construct(ordinary)
        ordinary.arrays['mo_coefficients'][0, 0] += .01
        with self.assertRaises(ValueError) as caught: runner.evaluate(runner.seed_density)
        self.assertEqual(caught.exception.reason, 'FROZEN_CACHED_MO_CHANGED')
        self.assertEqual(raw.calls, []); self.assertEqual(runner.ledger, [])
        ordinary, raw = self.fixture(); runner = self.construct(ordinary)
        raw.mutation = lambda: ordinary.arrays['mo_occupations'].__setitem__(0, 1.)
        result = runner.run(maximum_iterations=1)
        self.assertFalse(result['engine_qualified'])
        self.assertEqual(result['global_evaluation_count'], 1)
        self.assertEqual(result['prepared_evaluation_ledger'][0]['reason'], 'FROZEN_CACHED_MO_CHANGED')
        self.assertTrue(result['prepared_budget_settled'])

    def test_shared_caller_and_owned_seed_mutations_refused(self):
        ordinary, raw = self.fixture(); shared = self.construct(ordinary).seed_density.copy()
        runner = self.construct(ordinary, shared_seed_density=shared)
        shared[0, 0] += .01
        with self.assertRaises(ValueError) as caught: runner.evaluate(runner.seed_density)
        self.assertEqual(caught.exception.reason, 'FROZEN_SHARED_SEED_CHANGED')
        self.assertEqual(raw.calls, [])
        for field in ('seed_density', 'reference_seed_density', 'seed_coefficients'):
            ordinary, raw = self.fixture(); runner = self.construct(ordinary)
            value = getattr(runner, field); value.setflags(write=True); value.flat[0] += .01
            with self.assertRaises(ValueError) as caught: runner.evaluate(runner.seed_density)
            self.assertEqual(caught.exception.reason, 'FROZEN_V2_SEED_CHANGED')
            self.assertEqual(raw.calls, [])

    def test_no_retry_or_post_settlement_callback(self):
        ordinary, raw = self.fixture(changed_seed=False); runner = self.construct(ordinary)
        result = runner.run()
        self.assertTrue(result['engine_qualified']); self.assertEqual(len(raw.calls), 3)
        count = len(raw.calls)
        with self.assertRaises(ValueError): runner.run()
        with self.assertRaises(ValueError): runner.evaluate(runner.seed_density)
        self.assertEqual(len(raw.calls), count)

    def test_direct_probe_and_run_share_one_budget_and_snapshots(self):
        ordinary, raw = self.fixture(changed_seed=False); runner = self.construct(ordinary, maximum_evaluations=4)
        runner.evaluate(runner.seed_density)
        result = runner.run()
        self.assertEqual(result['global_evaluation_count'], 4)
        self.assertEqual(result['evaluation_limit'], 3)
        self.assertEqual(result['prepared_evaluation_ledger'][0]['phase'], 'DRIVER_DIRECT_CALLBACK')
        self.assertEqual(result['last_snapshot']['requested_density_id'], solver.density_id(result['density']))

    def test_unsupported_policy_and_changed_receipt_refused(self):
        ordinary, raw = self.fixture()
        with self.assertRaises(ValueError): self.construct(ordinary, initialization_policy=adapter.LOWER_POLICY)
        self.assertEqual(raw.calls, [])
        runner = self.construct(ordinary); runner.seed_receipt['scientific_approval'] = True
        with self.assertRaises(ValueError) as caught: runner.run()
        self.assertEqual(caught.exception.reason, 'FROZEN_V2_SEED_CHANGED')
        self.assertEqual(raw.calls, []); self.assertTrue(runner._settled)

    def test_no_production_or_molecular_construction_import(self):
        source = Path(adapter.__file__).read_text(encoding='utf-8')
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [node.module or ''] if isinstance(node, ast.ImportFrom) else [item.name for item in node.names]
                self.assertFalse(any(name.startswith(('runtime', 'ai4orgchem', 'pyscf')) for name in names), names)
        for forbidden_call in ('nr_rks(', 'get_hcore(', 'get_ovlp(', '.kernel(', 'intor(', '.build('):
            self.assertNotIn(forbidden_call, source)


if __name__ == '__main__':
    unittest.main()
