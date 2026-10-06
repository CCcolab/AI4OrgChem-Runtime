"""Prepared independent reference tests with original-grid XC test doubles."""
import ast
import hashlib
import itertools
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest

import numpy as np

from reference import residual_molecule as prepared
from reference import user_molecule as equations
from reference.ordinary_molecule import MolecularContext, ReferenceResult


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('AI4ORGCHEM_SOURCE_ROOT',os.environ.get('AI4ORGCHEM_SOURCE','/opt/ai4orgchem')))
RULES = SOURCE/'configs/qm/p09_exchange_integral_classes_v0.1.yaml'


def wire_identity(array):
    encoded = np.ascontiguousarray(array,dtype='<f8')
    return {'shape':list(encoded.shape),'dtype':'<f8','order':'C',
            'sha256':hashlib.sha256(encoded.tobytes()).hexdigest()}


def forbidden(*args,**kwargs):
    raise AssertionError('Independent prepared reference called kernel/integral/gridbuild/energy_nuc')


class RawXCTestDouble:
    def __init__(self,potential,energy):
        self.potential,self.energy,self.calls,self.mutation = potential.copy(),energy,[],None

    def rsh_and_hybrid_coeff(self,xc,spin=0):
        return 0.,.2,.2

    def nr_rks(self,mol,grids,xc,density,**kwargs):
        self.calls.append(density.copy())
        if self.mutation:
            self.mutation(density,grids,len(self.calls))
        return float(np.trace(density)),self.energy,self.potential.copy()


class IndependentPreparedTests(unittest.TestCase):
    def fixture(self,mixed=False):
        n = 3 if mixed else 2
        h = np.array([[-1.,.12,.07],[.12,.5,.1],[.07,.1,.9]]) if mixed else np.diag([-1.,1.])
        s = np.eye(n)
        factor = np.array([[.3,.1,.2],[.1,.4,.25],[.2,.25,.35]]) if mixed else np.zeros((n,n))
        eri = np.einsum('pq,rs->pqrs',factor,factor)
        density = np.zeros((n,n)); density[0,0] = 2.
        potential = np.array([[.1,.03,.04],[.03,.12,.05],[.04,.05,.15]]) if mixed else np.zeros((n,n))
        raw = RawXCTestDouble(potential,-.3 if mixed else 0.)
        grids = SimpleNamespace(coords=np.array([[0.,0.,0.],[.2,.1,-.1]]),weights=np.array([.1,.2]),level=2,build=forbidden)
        mol = SimpleNamespace(nelectron=2,spin=0,cart=False,energy_nuc=forbidden,intor=forbidden,kernel=forbidden)
        mf = SimpleNamespace(mol=mol,grids=grids,_numint=raw,xc='B3LYPG',max_memory=512,
                             kernel=forbidden,get_hcore=forbidden,get_ovlp=forbidden)
        aos = (equations.AO('sigma'),equations.AO('pi','A'),equations.AO('pi','B')) if mixed else (equations.AO('sigma'),)*2
        arrays = {'density':density,'hcore':h,'overlap':s,'eri':eri,'grid_coords':grids.coords.copy(),'grid_weights':grids.weights.copy()}
        profile = json.loads((ROOT/'profiles/user-molecule/pilot-b3lypg-sto3g-grid2-v1.json').read_text(encoding='utf-8'))
        context = MolecularContext(mol,mf,aos,{'test_engine':'ENGINEERING_FAKE','raw_integrals':'SUPPLIED_TINY_ARRAYS'},profile)
        record = {'converged':True,'qualification_tests':{'test_double_only':True},
                  'components_hartree':{'nuclear_repulsion':1.2 if mixed else 0.},
                  'array_identities':{name:wire_identity(value) for name,value in arrays.items()}}
        ordinary = ReferenceResult(record,arrays,context)
        return ordinary,raw

    def construct(self,ordinary,**options):
        options.setdefault('initialization_policy','REQUIRE_EXISTING_MASKED_PROJECTOR')
        return prepared.PreparedResidualReference(ordinary=ordinary,rule_path=RULES,
            expected_sha256=hashlib.sha256(RULES.read_bytes()).hexdigest(),**options)

    def test_no_production_import_and_no_molecular_construction(self):
        text = Path(prepared.__file__).read_text(encoding='utf-8')
        for node in ast.walk(ast.parse(text)):
            if isinstance(node,(ast.Import,ast.ImportFrom)):
                names = [node.module or ''] if isinstance(node,ast.ImportFrom) else [n.name for n in node.names]
                self.assertFalse(any(n.startswith(('runtime','ai4orgchem')) for n in names),names)
        self.assertNotIn('run_ordinary(',text)
        self.assertNotIn('.energy_nuc(',text)

    def test_fifteen_rule_masks_jk_and_five_component_operator_by_scalar_oracle(self):
        ordinary,raw = self.fixture(mixed=True)
        runner = self.construct(ordinary)
        d = np.array([[1.3,.2,-.1],[.2,.4,.05],[-.1,.05,.3]])
        original = {name:array.copy() for name,array in ordinary.arrays.items()}
        e = ordinary.arrays['eri'].copy()
        # Literal sigma/A/B oracle: mixed sigma-sigma/piA-piB quartets and
        # four-pi mixed quartets except (AA|BB)/(BB|AA) are source-deleted.
        for p,q,r,s in itertools.product(range(3),repeat=4):
            indices = (p,q,r,s); sigma = indices.count(0)
            mixed = 1 in indices and 2 in indices
            allowed_direct_pi = p == q and r == s and p != r
            if mixed and (sigma == 2 or (sigma == 0 and not allowed_direct_pi)):
                e[indices] = 0.
        j,k = np.zeros((3,3)),np.zeros((3,3))
        for p,q,r,s in itertools.product(range(3),repeat=4):
            j[p,q] += e[p,q,r,s]*d[r,s]
            k[p,q] += e[p,r,q,s]*d[r,s]
        h = ordinary.arrays['hcore'].copy(); h[1,2] = h[2,1] = 0.
        f = h+j-.1*k+raw.potential; f[1,2] = f[2,1] = 0.
        actual = runner.evaluate(d)
        np.testing.assert_allclose(actual['fock'],f,rtol=0,atol=2e-15)
        np.testing.assert_allclose(runner.last_evaluation['J'],j,rtol=0,atol=2e-15)
        np.testing.assert_allclose(runner.last_evaluation['K'],k,rtol=0,atol=2e-15)
        expected = {'one_electron_energy':float(np.sum(h*d.T)),
            'coulomb_energy':.5*float(np.sum(j*d.T)),'exact_exchange_energy':-.05*float(np.sum(k*d.T)),
            'semilocal_xc_energy':-.3,'nuclear_repulsion':1.2}
        for key,value in expected.items():
            self.assertAlmostEqual(actual[key],value,places=14)
        self.assertAlmostEqual(actual['total_energy'],sum(expected.values()),places=14)
        self.assertEqual(len(raw.calls),1)
        for key,array in ordinary.arrays.items():
            np.testing.assert_array_equal(array,original[key])

    def test_prepared_root_has_three_calls_and_never_claims_molecular_acceptance(self):
        ordinary,raw = self.fixture()
        result = self.construct(ordinary).run()
        self.assertTrue(result['engine_qualified']); self.assertEqual(result['global_evaluation_count'],3)
        self.assertEqual(len(raw.calls),3)
        self.assertFalse(result['production_activation']); self.assertFalse(result['comparison_available'])
        self.assertEqual(result['research_acceptance'],'NOT_ACCEPTED')
        self.assertEqual(result['molecular_acceptance'],'NOT_EXECUTED')
        self.assertEqual(result['molecular_execution'],'NOT_EXECUTED_ENGINEERING_FAKE')
        self.assertIsNone(result['deltas'])
        self.assertTrue(result['prepared_budget_settled'])
        self.assertEqual(result['phase_mapping_status'],'COMPLETE')
        self.assertEqual([row['phase'] for row in result['prepared_evaluation_ledger']],
                         [row['phase'] for row in result['evaluation_ledger']])
        np.testing.assert_array_equal(result['last_snapshot']['Fcond'],np.diag([-1.,1.]))
        self.assertEqual(result['real_functional_attempt_count'],0)

    def test_first_nonprojector_initialization_uses_same_original_d0_and_four_calls(self):
        ordinary,raw = self.fixture()
        ordinary.arrays['density'][:] = np.eye(2)
        ordinary.record['array_identities']['density'] = wire_identity(ordinary.arrays['density'])
        result = self.construct(ordinary,initialization_policy='FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0').run()
        self.assertTrue(result['engine_qualified']); self.assertEqual(result['global_evaluation_count'],4)
        self.assertEqual(len(raw.calls),4)
        np.testing.assert_array_equal(ordinary.arrays['density'],np.eye(2))
        np.testing.assert_array_equal(result['density'],np.diag([2.,0.]))

    def test_array_or_rule_identity_mismatch_before_raw_xc(self):
        ordinary,raw = self.fixture(); ordinary.arrays['hcore'][0,0] = -2.
        with self.assertRaises(ValueError):
            self.construct(ordinary)
        self.assertEqual(raw.calls,[])
        ordinary,raw = self.fixture()
        with self.assertRaises(ValueError):
            prepared.PreparedResidualReference(ordinary=ordinary,rule_path=RULES,expected_sha256='0'*64,
                initialization_policy='REQUIRE_EXISTING_MASKED_PROJECTOR')
        self.assertEqual(raw.calls,[])

    def test_changed_grid_rejects_before_call_and_inside_call_is_counted(self):
        ordinary,raw = self.fixture(); runner = self.construct(ordinary)
        ordinary.context.mean_field.grids.weights[0] = .8
        with self.assertRaises(ValueError):
            runner.evaluate(ordinary.arrays['density'])
        self.assertEqual(raw.calls,[]); self.assertEqual(runner.ledger,[])
        ordinary,raw = self.fixture(); runner = self.construct(ordinary)
        raw.mutation = lambda d,g,c:g.weights.__setitem__(0,.8)
        result = runner.run()
        self.assertFalse(result['engine_qualified']); self.assertEqual(len(raw.calls),1)
        self.assertEqual(result['global_evaluation_count'],1)
        self.assertEqual(result['prepared_evaluation_ledger'][0]['status'],'REFUSED')

    def test_raw_xc_boolean_complex_mutation_and_failure_are_refused(self):
        def throwing(d,g,c):
            raise RuntimeError('Controlled independent raw XC failure')
        for kind in ('boolean_energy','complex_potential','mutation','throwing'):
            with self.subTest(kind=kind):
                ordinary,raw = self.fixture(); runner = self.construct(ordinary)
                if kind == 'boolean_energy': raw.energy = True
                elif kind == 'complex_potential': raw.potential = raw.potential.astype(complex)
                elif kind == 'mutation': raw.mutation = lambda d,g,c:d.__setitem__((0,0),1.)
                else: raw.mutation = throwing
                result = runner.run()
                self.assertFalse(result['engine_qualified']); self.assertEqual(len(raw.calls),1)
                self.assertEqual(result['global_evaluation_count'],1)

    def test_mutable_true_f_same_energy_and_single_use_budget(self):
        ordinary,raw = self.fixture(); runner = self.construct(ordinary)
        raw.mutation = lambda d,g,c:raw.potential.__setitem__((1,1),.1) if c == 2 else None
        result = runner.run()
        self.assertFalse(result['engine_qualified'])
        self.assertEqual(result['prepared_evaluation_ledger'][-1]['reason'],'NONREPRODUCIBLE_SAME_DENSITY_OPERATOR')
        count = len(raw.calls)
        with self.assertRaises(ValueError): runner.run()
        self.assertEqual(len(raw.calls),count)

    def test_settled_run_rejects_direct_callback_without_extra_xc(self):
        ordinary,raw = self.fixture(); runner = self.construct(ordinary)
        runner.run(); count = len(raw.calls)
        with self.assertRaises(ValueError) as caught:
            runner.evaluate(ordinary.arrays['density'])
        self.assertEqual(caught.exception.reason,'REFERENCE_BUDGET_SETTLED')
        self.assertEqual(len(raw.calls),count)

    def test_missing_policy_and_invalid_first_configuration_have_zero_xc(self):
        ordinary,raw = self.fixture()
        with self.assertRaises(TypeError):
            prepared.PreparedResidualReference(ordinary=ordinary,rule_path=RULES,
                expected_sha256=hashlib.sha256(RULES.read_bytes()).hexdigest())
        self.assertEqual(raw.calls,[])
        runner = self.construct(ordinary,initialization_policy='FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0')
        with self.assertRaises(ValueError):
            runner.run(maximum_iterations=True)
        self.assertEqual(raw.calls,[])
        with self.assertRaises(ValueError):
            runner.evaluate(ordinary.arrays['density'])
        self.assertEqual(raw.calls,[])

    def test_changed_cached_molecular_fields_refuse_before_raw_xc(self):
        for field,before,after in (('charge',0,1),
                                   ('_atom',[('C',np.array([0.,0.,0.]))],[('C',np.array([.1,0.,0.]))]),
                                   ('_basis',{'C':[[0,[1.,.5]]]},{'C':[[0,[1.,.6]]]})):
            with self.subTest(field=field):
                ordinary,raw = self.fixture()
                setattr(ordinary.context.mol,field,before)
                runner = self.construct(ordinary)
                setattr(ordinary.context.mol,field,after)
                with self.assertRaises(ValueError):
                    runner.evaluate(ordinary.arrays['density'])
                self.assertEqual(raw.calls,[]); self.assertEqual(runner.ledger,[])

    def test_raw_xc_cached_geometry_mutation_is_refused_and_counted(self):
        ordinary,raw = self.fixture()
        ordinary.context.mol._atom = [('C',np.array([0.,0.,0.]))]
        runner = self.construct(ordinary)
        raw.mutation = lambda d,g,c:ordinary.context.mol._atom[0][1].__setitem__(0,.1)
        result = runner.run()
        self.assertFalse(result['engine_qualified'])
        self.assertEqual(result['global_evaluation_count'],1)
        self.assertEqual(len(raw.calls),1)
        self.assertEqual(result['prepared_evaluation_ledger'][0]['reason'],'FROZEN_SETTINGS_CHANGED')


if __name__ == '__main__':
    unittest.main()
