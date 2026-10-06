"""Prepared bridge array/failure tests; ENGINEERING_FAKE, never molecular SCF.

The frozen P09 density evaluator and locked fifteen rules are exercised with
tiny supplied arrays and a fake nr_rks.  Kernels, integrals and grid creation
are forbidden.  Numerical expectations use independent scalar contractions.
"""
import hashlib
import importlib
import itertools
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import yaml

from runtime.user_molecule import residual_bridge as bridge


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('AI4ORGCHEM_SOURCE_ROOT',
              os.environ.get('AI4ORGCHEM_SOURCE', '/opt/ai4orgchem')))
PROFILE = ROOT/'profiles/user-molecule/pilot-b3lypg-sto3g-grid2-v1.json'
RULES = SOURCE/'configs/qm/p09_exchange_integral_classes_v0.1.yaml'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def array_witness(value):
    """Hand-coded wire identity; do not construct expected data with bridge."""
    encoded = np.ascontiguousarray(value, dtype='<f8')
    return {'shape': list(encoded.shape), 'dtype': '<f8', 'order': 'C',
            'sha256': sha(encoded.tobytes(order='C'))}


def descriptors_witness(descriptors):
    values = [{'kind': item.kind, 'fragment': item.fragment} for item in descriptors]
    return sha(json.dumps(values, sort_keys=True, separators=(',', ':'),
                          ensure_ascii=False, allow_nan=False).encode('utf-8'))


def forbidden(*args, **kwargs):
    raise AssertionError('Molecular kernel, integral generation or grid build invoked')


class FakeNumInt:
    def __init__(self, potential, xc_energy=0.0):
        self.potential, self.xc_energy = potential.copy(), xc_energy
        self.calls, self.mutation = [], None

    def rsh_and_hybrid_coeff(self, xc, spin=0):
        return 0.0, 0.2, 0.2

    def nr_rks(self, molecule, grids, xc, density, **kwargs):
        self.calls.append(density.copy())
        if self.mutation is not None:
            self.mutation(density, grids, len(self.calls))
        return float(np.trace(density)), self.xc_energy, self.potential.copy()


def scalar_deleted(quartet, entries):
    """Literal eightfold/token binding oracle independent of P09 helpers."""
    left, right = tuple(quartet[:2]), tuple(quartet[2:])
    permutations = {a+b for a in (left, left[::-1]) for b in (right, right[::-1])}
    permutations |= {b+a for a in (left, left[::-1]) for b in (right, right[::-1])}
    for entry in entries:
        predicate = entry['index_predicate']
        tokens = predicate['bra']+predicate['ket']
        for ordered in permutations:
            bound, valid = {}, True
            for token, (kind, fragment) in zip(tokens, ordered):
                if token == 'sigma':
                    valid &= kind == 'sigma'
                elif kind != 'pi':
                    valid = False
                else:
                    variable = token[3:]
                    valid &= variable not in bound or bound[variable] == fragment
                    bound[variable] = fragment
            constraints = predicate.get('constraints', [])
            for name, a, b in (('P_not_equal_Q', 'P', 'Q'), ('S_not_equal_T', 'S', 'T')):
                if name in constraints and a in bound and b in bound:
                    valid &= bound[a] != bound[b]
            if {'S_in_P_or_Q', 'T_in_P_or_Q'} & set(constraints):
                pair = {bound.get('S'), bound.get('T')}
                valid &= None not in pair and len(pair) == 2
                valid &= all(bound[a] in pair for a in ('P', 'Q') if a in bound)
                if 'P' in bound and 'Q' in bound:
                    valid &= {bound['P'], bound['Q']} == pair
            if valid:
                return True
    return False


class PreparedBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        paths = patch.object(sys, 'path', [str(SOURCE/'software/src'), *sys.path])
        paths.start()
        cls.addClassCleanup(paths.stop)
        cls.AO = importlib.import_module('ai4orgchem.qm.p09_eri_mask').AODescriptor
        cls.entries = yaml.safe_load(RULES.read_bytes())['exchange_integral_classes']
        cls.source_lock = json.loads((ROOT/'locks/source.user-molecule.lock.json').read_text(encoding='utf-8'))

    def setUp(self):
        # These fallback bindings explicitly identify a fake worker, not the
        # existing Docker image or its scientific/build acceptance identity.
        bindings = {
            'AI4ORGCHEM_RUNTIME_TEST_COMMIT': os.environ.get('AI4ORGCHEM_RUNTIME_TEST_COMMIT', 'a1'*20),
            'AI4ORGCHEM_IMAGE_ID': os.environ.get('AI4ORGCHEM_IMAGE_ID', 'sha256:'+'b2'*32),
            'AI4ORGCHEM_IMAGE_BUILD_COMMIT': os.environ.get('AI4ORGCHEM_IMAGE_BUILD_COMMIT', 'c3'*20),
        }
        self.bindings = bindings
        environment = patch.dict(os.environ, bindings)
        environment.start()
        self.addCleanup(environment.stop)

    def fixture(self, *, mixed=False, policy='REQUIRE_EXISTING_MASKED_PROJECTOR', budget=201):
        if mixed:
            descriptors = (self.AO('sigma'), self.AO('pi', 'A'), self.AO('pi', 'B'))
            overlap = np.array([[1.0, .05, .02], [.05, 1.1, .15], [.02, .15, .9]])
            hcore = np.array([[-.9, .2, .13], [.2, .5, .19], [.13, .19, .8]])
            factors = (np.array([[.3,.1,.2],[.1,.4,.25],[.2,.25,.35]]),
                       np.array([[.1,.07,.03],[.07,.2,.09],[.03,.09,.15]]))
            eri = sum(np.einsum('pq,rs->pqrs', item, item) for item in factors)
            masked_overlap = overlap.copy(); masked_overlap[1,2] = masked_overlap[2,1] = 0.0
            vector = np.array([1.0, .25, -.15])
            density = 2*np.outer(vector, vector)/float(vector@masked_overlap@vector)
            potential = np.array([[.1,.03,.04],[.03,.12,.05],[.04,.05,.15]])
            nuclear, xc_energy = 1.2, -.3
        else:
            descriptors = (self.AO('sigma'), self.AO('sigma'))
            overlap, hcore = np.eye(2), np.diag([-1.0, 1.0])
            eri, density, potential = np.zeros((2,)*4), np.diag([2.0, 0.0]), np.zeros((2,2))
            nuclear, xc_energy = 0.0, 0.0
        numint = FakeNumInt(potential, xc_energy)
        grids = SimpleNamespace(coords=np.array([[0.,0.,0.],[.2,.1,-.1]]),
                                weights=np.array([.1,.2]), level=2, build=forbidden)
        nuclear_calls = []
        def cached_nuclear():
            nuclear_calls.append(nuclear)
            return nuclear
        molecule = SimpleNamespace(nelectron=2, spin=0, cart=False, energy_nuc=cached_nuclear,
                                   nuclear_calls=nuclear_calls,
                                   intor=forbidden, kernel=forbidden)
        mean_field = SimpleNamespace(mol=molecule, grids=grids, _numint=numint,
            xc='B3LYPG', max_memory=512, kernel=forbidden, get_hcore=forbidden, get_ovlp=forbidden)
        request = json.dumps({'profile_id': 'pilot-b3lypg-sto3g-grid2-v1',
            'charge': 0, 'multiplicity': 1, 'execution_kind': 'ENGINEERING_FAKE'},
            sort_keys=True).encode('utf-8')
        arrays = {'physical_overlap': overlap, 'physical_hcore': hcore, 'physical_eri': eri,
                  'ordinary_density': density, 'grid_coords': grids.coords, 'grid_weights': grids.weights}
        contract = {
            'science_commit': self.source_lock['source_commit'],
            'science_baseline_commit': self.source_lock['baseline_commit'],
            'runtime_test_commit': self.bindings['AI4ORGCHEM_RUNTIME_TEST_COMMIT'],
            'image_id': self.bindings['AI4ORGCHEM_IMAGE_ID'],
            'image_build_commit': self.bindings['AI4ORGCHEM_IMAGE_BUILD_COMMIT'],
            'request_sha256': sha(request), 'profile_sha256': sha(PROFILE.read_bytes()),
            'condition_rules_sha256': sha(RULES.read_bytes()),
            'source_manifest_sha256': sha((ROOT/'locks/source-user-molecule-files.sha256.json').read_bytes()),
            'array_identities': {key: array_witness(value) for key, value in arrays.items()},
            'descriptors_sha256': descriptors_witness(descriptors), 'execution_kind': 'ENGINEERING_FAKE',
            'initialization_policy': policy, 'maximum_evaluations': budget,
            'nuclear_repulsion_hartree': nuclear,
        }
        kwargs = dict(runtime_root=ROOT, science_root=SOURCE, mean_field=mean_field,
            physical_overlap=overlap, physical_hcore=hcore, physical_eri=eri,
            ordinary_density=density, descriptors=descriptors, request_bytes=request,
            profile_path=PROFILE, contract=contract, nuclear_repulsion=nuclear,
            exact_exchange_fraction=.2, eri_mode='COPY_MASK', optimize_eri_contractions=True)
        return kwargs, numint, arrays

    def assert_closed(self, result):
        self.assertFalse(result['production_activation'])
        self.assertFalse(result['comparison_available'])
        self.assertIsNone(result['deltas'])
        self.assertEqual(result['research_acceptance'], 'NOT_ACCEPTED')
        self.assertEqual(result['molecular_acceptance'], 'NOT_EXECUTED')
        self.assertEqual(result['global_evaluation_count'], len(result['bridge_ledger']))
        self.assertLessEqual(result['global_evaluation_count'], result['global_evaluation_limit'])
        for index, row in enumerate(result['bridge_ledger'], 1):
            self.assertEqual(row['global_evaluation_count'], index)
            self.assertRegex(row['density_id'], r'^[0-9a-f]{64}$')
            self.assertIn(row['status'], ('VALIDATED', 'REFUSED'))

    def test_fifteen_rules_and_scalar_jk_five_energy_in_both_storage_modes(self):
        self.assertEqual({e['id'] for e in self.entries}, {f'X{i:02d}' for i in range(1,16)})
        kwargs, _, arrays = self.fixture(mixed=True)
        original = {name: value.copy() for name, value in arrays.items()}
        descriptors = [('sigma',None), ('pi','A'), ('pi','B')]
        eri = arrays['physical_eri'].copy()
        for indices in itertools.product(range(3), repeat=4):
            if scalar_deleted(tuple(descriptors[i] for i in indices), self.entries):
                eri[indices] = 0.0
        d = arrays['ordinary_density']
        j, k = np.zeros((3,3)), np.zeros((3,3))
        for p,q,r,s in itertools.product(range(3), repeat=4):
            j[p,q] += eri[p,q,r,s]*d[r,s]
            k[p,q] += eri[p,r,q,s]*d[r,s]
        h = arrays['physical_hcore'].copy(); h[1,2] = h[2,1] = 0.0
        f = h+j-.1*k+kwargs['mean_field']._numint.potential
        f[1,2] = f[2,1] = 0.0
        expected = {'one_electron_energy': float(np.sum(h*d.T)),
                    'coulomb_energy': .5*float(np.sum(j*d.T)),
                    'exact_exchange_energy': -.05*float(np.sum(k*d.T)),
                    'semilocal_xc_energy': -.3, 'nuclear_repulsion': 1.2}
        for mode, optimize in (('COPY_MASK', True), ('INPLACE_OWNED', False)):
            with self.subTest(mode=mode):
                kwargs['eri_mode'], kwargs['optimize_eri_contractions'] = mode, optimize
                prepared = bridge.PreparedResidualBridge(**kwargs)
                actual = prepared.evaluate(d)
                np.testing.assert_allclose(actual['fock'], f, rtol=0, atol=2e-15)
                np.testing.assert_allclose(actual['coulomb_matrix'], j, rtol=0, atol=2e-15)
                np.testing.assert_allclose(actual['exchange_matrix'], k, rtol=0, atol=2e-15)
                for key, value in expected.items():
                    self.assertAlmostEqual(actual[key], value, places=14)
                self.assertAlmostEqual(actual['total_energy'], sum(expected.values()), places=14)
                self.assertEqual(actual['operator_source'], 'TRUE_CONDITIONAL_AT_REQUESTED_DENSITY')
                self.assertRegex(actual['density_id'], r'^[0-9a-f]{64}$')
        for name, value in arrays.items():
            np.testing.assert_array_equal(value, original[name])

    def test_preserved_projector_uses_three_frozen_evaluations(self):
        kwargs, numint, arrays = self.fixture()
        prepared = bridge.PreparedResidualBridge(**kwargs)
        self.assertEqual(kwargs['mean_field'].mol.nuclear_calls, [])
        result = prepared.run()
        self.assert_closed(result)
        self.assertTrue(result['solver_result']['engine_qualified'])
        self.assertEqual(result['global_evaluation_count'], 3)
        self.assertEqual(len(numint.calls), 3)
        self.assertEqual(len(kwargs['mean_field'].mol.nuclear_calls), 3)
        np.testing.assert_array_equal(result['solver_result']['density'], arrays['ordinary_density'])

    def test_first_raw_initialization_is_separately_counted(self):
        kwargs, numint, arrays = self.fixture(policy='FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0')
        arrays['ordinary_density'][:] = np.eye(2)
        kwargs['contract']['array_identities']['ordinary_density'] = array_witness(arrays['ordinary_density'])
        result = bridge.PreparedResidualBridge(**kwargs).run()
        self.assert_closed(result)
        self.assertTrue(result['solver_result']['engine_qualified'])
        self.assertEqual(result['global_evaluation_count'], 4)
        self.assertEqual(len(numint.calls), 4)
        self.assertEqual(result['bridge_ledger'][0]['phase'], 'INITIALIZE_AT_ORDINARY_D0')
        self.assertEqual(result['initialization']['raw_aufbau_spectrum_hartree'], [-1.0, 1.0])
        self.assertEqual(result['initialization']['raw_aufbau_gap_hartree'], 2.0)
        self.assertRegex(result['initialization']['raw_aufbau_fock_id'], r'^[0-9a-f]{64}$')
        self.assertEqual(result['initialization']['raw_aufbau_spectrum_identity'],
                         array_witness(np.array([-1.0,1.0])))
        self.assertNotEqual(result['initialization']['ordinary_density_id'],
                            result['initialization']['initial_density_id'])
        np.testing.assert_array_equal(result['solver_result']['density'], np.diag([2.0,0.0]))
        np.testing.assert_array_equal(arrays['ordinary_density'], np.eye(2))

    def test_first_raw_initialization_uses_dense_masked_metric(self):
        kwargs, numint, arrays = self.fixture(policy='FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0')
        arrays['physical_overlap'][:] = [[1.0,.2],[.2,1.0]]
        arrays['physical_hcore'][:] = [[0.0,1.0],[1.0,0.0]]
        arrays['ordinary_density'][:] = np.eye(2)
        for name in ('physical_overlap','physical_hcore','ordinary_density'):
            kwargs['contract']['array_identities'][name] = array_witness(arrays[name])
        result = bridge.PreparedResidualBridge(**kwargs).run()
        self.assert_closed(result)
        self.assertTrue(result['solver_result']['engine_qualified'])
        self.assertEqual(result['global_evaluation_count'], 4)
        expected = np.array([[1.0,-1.0],[-1.0,1.0]])/.8
        d, s = result['solver_result']['density'], arrays['physical_overlap']
        np.testing.assert_allclose(d, expected, rtol=0, atol=2e-15)
        self.assertAlmostEqual(float(np.trace(s@d)), 2.0, places=13)
        self.assertLess(np.linalg.norm(d@s@d-2*d), 2e-14)
        self.assertNotEqual(result['initialization']['ordinary_density_id'],
                            result['initialization']['initial_density_id'])
        np.testing.assert_array_equal(arrays['ordinary_density'], np.eye(2))

    def test_first_initialization_does_not_hide_its_budget_cost(self):
        kwargs, numint, _ = self.fixture(policy='FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0', budget=3)
        result = bridge.PreparedResidualBridge(**kwargs).run()
        self.assert_closed(result)
        self.assertFalse(result['solver_result']['engine_qualified'])
        self.assertLessEqual(len(numint.calls), 3)

    def test_preserve_policy_rejects_nonprojector_without_xc(self):
        kwargs, numint, arrays = self.fixture()
        arrays['ordinary_density'][:] = np.eye(2)
        kwargs['contract']['array_identities']['ordinary_density'] = array_witness(arrays['ordinary_density'])
        result = bridge.PreparedResidualBridge(**kwargs).run()
        self.assert_closed(result)
        self.assertEqual(result['stop_reason'], 'INITIAL_DENSITY_NOT_MASKED_PROJECTOR')
        self.assertEqual(result['global_evaluation_count'], 0)
        self.assertEqual(numint.calls, [])
        self.assertIsNone(result['solver_result'])
        np.testing.assert_array_equal(arrays['ordinary_density'], np.eye(2))

    def test_first_raw_exact_and_near_degenerate_boundaries_refuse(self):
        for gap in (0.0, 5e-7):
            with self.subTest(gap=gap):
                kwargs, numint, arrays = self.fixture(policy='FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0')
                arrays['physical_hcore'][:] = np.diag([0.0, gap])
                kwargs['contract']['array_identities']['physical_hcore'] = array_witness(arrays['physical_hcore'])
                result = bridge.PreparedResidualBridge(**kwargs).run()
                self.assert_closed(result)
                self.assertEqual(result['stop_reason'], 'ROOT_AMBIGUOUS_INITIALIZATION')
                self.assertEqual(result['global_evaluation_count'], 1)
                self.assertEqual(len(numint.calls), 1)
                self.assertIsNone(result['solver_result'])
                self.assertEqual(result['initialization']['raw_aufbau_spectrum_hartree'], [0.0, gap])
                self.assertEqual(result['initialization']['raw_aufbau_gap_hartree'], gap)
                self.assertRegex(result['initialization']['raw_aufbau_fock_id'], r'^[0-9a-f]{64}$')
                self.assertEqual(result['initialization']['raw_aufbau_spectrum_identity'],
                                 array_witness(np.array([0.0,gap])))

    def test_bridge_run_cannot_reuse_a_settled_budget(self):
        kwargs, numint, _ = self.fixture()
        prepared = bridge.PreparedResidualBridge(**kwargs)
        prepared.run(); count = len(numint.calls)
        with self.assertRaises(bridge.BridgeRefusal):
            prepared.run()
        with self.assertRaises(bridge.BridgeRefusal) as caught:
            prepared.evaluate(kwargs['ordinary_density'])
        self.assertEqual(caught.exception.reason, 'BRIDGE_ALREADY_SETTLED')
        self.assertEqual(len(numint.calls), count)

    def test_invalid_solver_settings_reject_first_policy_before_xc(self):
        for settings in ({'maximum_iterations':True}, {'maximum_iterations':0},
                         {'finite_difference_step':True}, {'finite_difference_step':float('nan')},
                         {'finite_difference_step':.5,'trust_radius':.25},
                         {'maximum_backtracks':False}):
            with self.subTest(settings=settings):
                kwargs, numint, _ = self.fixture(policy='FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0')
                result = bridge.PreparedResidualBridge(**kwargs).run(**settings)
                self.assert_closed(result)
                self.assertIsNotNone(result['failure'])
                self.assertEqual(result['global_evaluation_count'], 0)
                self.assertEqual(numint.calls, [])

    def test_huge_finite_initial_density_refuses_before_xc(self):
        kwargs, numint, arrays = self.fixture()
        arrays['ordinary_density'][:] = np.diag([1e308,1e308])
        kwargs['contract']['array_identities']['ordinary_density'] = array_witness(arrays['ordinary_density'])
        prepared = bridge.PreparedResidualBridge(**kwargs)
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            result = prepared.run()
        self.assert_closed(result)
        self.assertIsNotNone(result['failure'])
        self.assertEqual(result['global_evaluation_count'], 0)
        self.assertEqual(numint.calls, [])

    def test_direct_evaluations_cannot_overrun_or_reset_global_budget(self):
        kwargs, numint, arrays = self.fixture(budget=2)
        prepared = bridge.PreparedResidualBridge(**kwargs)
        prepared.evaluate(arrays['ordinary_density'])
        prepared.evaluate(arrays['ordinary_density'])
        with self.assertRaises(bridge.BridgeRefusal) as caught:
            prepared.evaluate(arrays['ordinary_density'])
        self.assertEqual(caught.exception.reason, 'EVALUATION_BUDGET_EXHAUSTED')
        self.assertEqual(len(numint.calls), 2)
        result = prepared.run()
        self.assert_closed(result)
        self.assertEqual(result['global_evaluation_count'], 2)
        self.assertEqual(len(numint.calls), 2)

    def test_contract_identity_mismatches_refuse_before_xc(self):
        for field in ('science_commit','science_baseline_commit','runtime_test_commit','image_id',
                      'image_build_commit','request_sha256','profile_sha256',
                      'condition_rules_sha256','source_manifest_sha256','descriptors_sha256'):
            with self.subTest(field=field):
                kwargs, numint, _ = self.fixture()
                kwargs['contract'][field] = '0'*64
                with self.assertRaises(bridge.BridgeRefusal):
                    bridge.PreparedResidualBridge(**kwargs)
                self.assertEqual(numint.calls, [])

    def test_array_identity_mismatch_refuses_before_xc(self):
        kwargs, numint, _ = self.fixture()
        kwargs['contract']['array_identities']['physical_eri']['sha256'] = '0'*64
        with self.assertRaises(bridge.BridgeRefusal):
            bridge.PreparedResidualBridge(**kwargs)
        self.assertEqual(numint.calls, [])

    def test_bad_inputs_never_cast_complex_or_bool_to_real(self):
        for name, value in (('physical_overlap',np.eye(2,dtype=complex)),
                            ('ordinary_density',np.eye(2,dtype=bool)),
                            ('physical_hcore',np.full((2,2),np.nan)),
                            ('nuclear_repulsion',True), ('exact_exchange_fraction',True)):
            with self.subTest(name=name):
                kwargs, numint, _ = self.fixture(); kwargs[name] = value
                with self.assertRaises(bridge.BridgeRefusal):
                    bridge.PreparedResidualBridge(**kwargs)
                self.assertEqual(numint.calls, [])

    def test_nuclear_cache_mismatch_refuses_before_xc(self):
        kwargs, numint, _ = self.fixture(); kwargs['nuclear_repulsion'] = 1.0
        with self.assertRaises(bridge.BridgeRefusal):
            bridge.PreparedResidualBridge(**kwargs)
        self.assertEqual(numint.calls, [])
        self.assertEqual(kwargs['mean_field'].mol.nuclear_calls, [])

    def test_actual_nuclear_mismatch_is_counted_frozen_energy_closure_failure(self):
        kwargs, numint, _ = self.fixture()
        molecule = kwargs['mean_field'].mol
        def wrong_nuclear():
            molecule.nuclear_calls.append(1.1)
            return 1.1
        molecule.energy_nuc = wrong_nuclear
        prepared = bridge.PreparedResidualBridge(**kwargs)
        self.assertEqual(molecule.nuclear_calls, [])
        result = prepared.run()
        self.assert_closed(result)
        self.assertEqual(len(numint.calls), 1)
        self.assertEqual(len(molecule.nuclear_calls), 1)
        self.assertEqual(result['global_evaluation_count'], 1)
        self.assertEqual(result['bridge_ledger'][0]['reason'], 'ENERGY_COMPONENT_CLOSURE_FAILED')
        self.assertFalse(result['solver_result']['engine_qualified'])

    def test_grid_mutation_is_rejected_and_counted(self):
        kwargs, numint, _ = self.fixture()
        numint.mutation = lambda density, grids, count: grids.weights.__setitem__(0, .9)
        result = bridge.PreparedResidualBridge(**kwargs).run()
        self.assert_closed(result)
        self.assertTrue(result['failure'] or result['solver_result']['failure'])
        self.assertEqual(result['global_evaluation_count'], 1)
        self.assertEqual(result['bridge_ledger'][0]['status'], 'REFUSED')

    def test_grid_changed_before_evaluation_consumes_no_xc_attempt(self):
        kwargs, numint, arrays = self.fixture()
        prepared = bridge.PreparedResidualBridge(**kwargs)
        kwargs['mean_field'].grids.coords[0,0] = .9
        with self.assertRaises(bridge.BridgeRefusal) as caught:
            prepared.evaluate(arrays['ordinary_density'])
        self.assertEqual(caught.exception.reason, 'FROZEN_GRID_CHANGED')
        self.assertEqual(prepared.ledger, [])
        self.assertEqual(numint.calls, [])

    def test_xc_failure_is_counted_once_and_never_retried(self):
        kwargs, numint, _ = self.fixture()
        def failing(density, grids, count):
            raise RuntimeError('ENGINEERING_FAKE controlled XC failure')
        numint.mutation = failing
        result = bridge.PreparedResidualBridge(**kwargs).run()
        self.assert_closed(result)
        self.assertEqual(result['global_evaluation_count'], 1)
        self.assertEqual(len(numint.calls), 1)
        self.assertTrue(result['failure'] or result['solver_result']['failure'])

    def test_same_density_changed_fock_with_same_energy_is_refused(self):
        kwargs, numint, _ = self.fixture()
        def change_operator(density, grids, count):
            if count == 2:
                numint.potential[1,1] = .1
        numint.mutation = change_operator
        result = bridge.PreparedResidualBridge(**kwargs).run()
        self.assert_closed(result)
        self.assertFalse(result['solver_result']['engine_qualified'])
        self.assertEqual(result['bridge_ledger'][-1]['reason'], 'NONREPRODUCIBLE_SAME_DENSITY_OPERATOR')
        self.assertFalse(result['bridge_ledger'][-1]['same_density_operator_reproducible'])
        self.assertNotEqual(result['bridge_ledger'][-1]['fock_id'],
                            result['bridge_ledger'][-1]['previous_same_density_fock_id'])

    def test_production_profiles_remain_disabled(self):
        for name in ('pilot-b3lypg-sto3g-grid2-v1.json','research-b3lypg-631gd-grid3-v1.json'):
            value = json.loads((ROOT/'profiles/user-molecule'/name).read_text(encoding='utf-8'))
            self.assertIs(value['compute_enabled'], False)
            self.assertIsNone(value['resource_model'])


if __name__ == '__main__':
    unittest.main()
