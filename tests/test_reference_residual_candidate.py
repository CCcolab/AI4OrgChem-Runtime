"""Independent-reference analytical arrays; no molecule or production import."""
import ast
import hashlib
import math
from pathlib import Path
import struct
import unittest

import numpy as np

from reference import residual_candidate as ref


def identity(dm):
    encoded = np.ascontiguousarray(dm,dtype='<f8')
    return hashlib.sha256(b'AI4OrgChem-density-v1\0'+struct.pack('<QQ',*encoded.shape)+encoded.tobytes()).hexdigest()


def projector(theta):
    v = np.array([math.cos(theta),math.sin(theta)])
    return 2*np.outer(v,v)


class Evaluator:
    def __init__(self,kind='constant',half=None,mutate=None):
        self.kind,self.half,self.mutate = kind,np.eye(2) if half is None else half,mutate
        self.calls = []

    def __call__(self,dm):
        self.calls.append(dm.copy())
        orthogonal = self.half@dm@self.half
        if self.kind == 'unstable':
            z = 4*(orthogonal[0,0]/2-.5)
            f = np.array([[z,1.],[1.,-z]])
            one,coulomb = float(2*orthogonal[0,1]),float(.5*(orthogonal[0,0]-orthogonal[1,1])**2)
        elif self.kind == 'no_root':
            z = orthogonal[0,0]/2-.5
            f = np.diag([z,-z]); one,coulomb = 0.,0.
        elif self.kind == 'far':
            f = np.array([[0.,1.],[1.,0.]]); one,coulomb = float(np.sum(f*orthogonal.T)),0.
        elif self.kind == 'degenerate':
            f = np.diag([0.,5e-7]); one,coulomb = 0.,0.
        else:
            f = np.diag([-1.,1.]); one,coulomb = float(np.sum(f*orthogonal.T)),0.
        value = {'density_id':identity(dm),'operator_source':'TRUE_CONDITIONAL_AT_REQUESTED_DENSITY',
            'fock':self.half@f@self.half,'total_energy':one+coulomb,'one_electron_energy':one,
            'coulomb_energy':coulomb,'exact_exchange_energy':0.,'semilocal_xc_energy':0.,'nuclear_repulsion':0.}
        if self.mutate:
            self.mutate(dm,value,len(self.calls))
        return value


class IndependentResidualTests(unittest.TestCase):
    def solve(self,evaluator=None,density=None,overlap=None,**options):
        evaluator = evaluator or Evaluator()
        density = np.diag([2.,0.]) if density is None else density
        overlap = np.eye(2) if overlap is None else overlap
        original = density.copy()
        options.setdefault('initialization_policy','REQUIRE_EXISTING_MASKED_PROJECTOR')
        result = ref.solve(density=density,overlap=overlap,electrons=2,evaluate=evaluator,**options)
        np.testing.assert_array_equal(density,original)
        self.assertFalse(result['production_activation'])
        self.assertEqual(result['research_acceptance'],'NOT_ACCEPTED')
        self.assertEqual(result['molecular_acceptance'],'NOT_EXECUTED')
        self.assertFalse(result['comparison_available']); self.assertIsNone(result['deltas'])
        self.assertEqual(result['evaluation_count'],len(evaluator.calls))
        self.assertEqual(result['evaluation_count'],len(result['evaluation_ledger']))
        self.assertLessEqual(result['evaluation_count'],options.get('maximum_evaluations',201))
        for index,(call,row) in enumerate(zip(evaluator.calls,result['evaluation_ledger']),1):
            self.assertEqual(row['evaluation_count'],index)
            self.assertEqual(row['density_id'],identity(call))
        return result,evaluator

    def test_reference_implementation_has_no_production_import(self):
        source = Path(ref.__file__).read_text(encoding='utf-8')
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node,(ast.Import,ast.ImportFrom)):
                names = [node.module or ''] if isinstance(node,ast.ImportFrom) else [n.name for n in node.names]
                self.assertFalse(any(n.startswith(('runtime','ai4orgchem')) for n in names),names)
        self.assertNotIn('endpoint_gate(',source)
        self.assertIn('least_squares(',source)

    def test_exact_ground_projector_three_calls_without_optimization(self):
        result,_ = self.solve()
        self.assertTrue(result['engine_qualified'])
        self.assertEqual(result['evaluation_count'],3)
        np.testing.assert_array_equal(result['density'],np.diag([2.,0.]))
        self.assertTrue(all(result['endpoint_gate']['checks'].values()))

    def test_picard_unstable_known_ground_root(self):
        result,_ = self.solve(Evaluator('unstable'),density=projector(-.6))
        self.assertTrue(result['engine_qualified'])
        np.testing.assert_allclose(result['density'],[[1.,-1.],[-1.,1.]],rtol=0,atol=2e-8)
        self.assertAlmostEqual(result['endpoint_gate']['final_non_diis_gap_hartree'],2.,places=7)
        self.assertGreater(result['evaluation_count'],result['scipy_result']['nfev'])
        self.assertTrue(any(row['phase'] == 'SCIPY_TRF_RESIDUAL' for row in result['evaluation_ledger']))

    def test_far_root_requires_reanchoring_beyond_initial_chart(self):
        result,_ = self.solve(Evaluator('far'),density=np.diag([2.,0.]))
        self.assertTrue(result['engine_qualified'])
        np.testing.assert_allclose(result['density'],[[1.,-1.],[-1.,1.]],rtol=0,atol=2e-8)
        self.assertGreaterEqual(len(result['history']),3)

    def test_dense_spd_metric_and_analytical_projector(self):
        s = np.array([[1.,.2],[.2,1.]])
        a,b = math.sqrt(1.2),math.sqrt(.8)
        half = np.array([[(a+b)/2,(a-b)/2],[(a-b)/2,(a+b)/2]])
        inverse = np.array([[(1/a+1/b)/2,(1/a-1/b)/2],[(1/a-1/b)/2,(1/a+1/b)/2]])
        result,evaluator = self.solve(Evaluator('unstable',half),density=inverse@projector(-.6)@inverse,overlap=s)
        self.assertTrue(result['engine_qualified'])
        np.testing.assert_allclose(result['density'],np.array([[1.,-1.],[-1.,1.]])/.8,rtol=0,atol=2e-8)
        for dm in evaluator.calls:
            self.assertAlmostEqual(float(np.trace(s@dm)),2.,places=11)
            self.assertLess(np.linalg.norm(dm@s@dm-2*dm),1e-10)

    def test_commuting_excited_and_no_qualified_root_are_rejected(self):
        for evaluator,density in ((Evaluator(),np.diag([0.,2.])),
                                  (Evaluator('no_root'),projector(-.6))):
            with self.subTest(kind=evaluator.kind):
                result,_ = self.solve(evaluator,density=density)
                self.assertFalse(result['engine_qualified'])

    def test_near_degenerate_first_initialization_refuses_one_call(self):
        result,_ = self.solve(Evaluator('degenerate'),initialization_policy='FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0')
        self.assertFalse(result['engine_qualified']); self.assertEqual(result['evaluation_count'],1)
        self.assertEqual(result['stop_reason'],'ROOT_AMBIGUOUS_INITIALIZATION')

    def test_first_nonprojector_init_is_distinct_counted_and_preserves_d0(self):
        result,_ = self.solve(density=np.eye(2),initialization_policy='FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0')
        self.assertTrue(result['engine_qualified']); self.assertEqual(result['evaluation_count'],4)
        self.assertNotEqual(result['initialization']['ordinary_density_id'],result['initialization']['initial_density_id'])
        np.testing.assert_array_equal(result['density'],np.diag([2.,0.]))

    def test_low_budget_counts_finite_differences_and_never_qualifies(self):
        result,_ = self.solve(Evaluator('unstable'),density=projector(-.6),maximum_evaluations=5)
        self.assertFalse(result['engine_qualified'])
        self.assertEqual(result['stop_reason'],'EVALUATION_BUDGET_EXHAUSTED')

    def test_callback_error_mutation_identity_and_scalar_types_refuse(self):
        def throwing(dm,value,count):
            raise RuntimeError('Controlled reference callback failure')
        for mutate in (throwing,lambda d,v,c:d.__setitem__((0,0),1.),
                       lambda d,v,c:v.__setitem__('density_id','0'*64),
                       lambda d,v,c:v.__setitem__('fock',np.eye(2,dtype=complex)),
                       lambda d,v,c:v.__setitem__('total_energy',True)):
            with self.subTest(mutate=mutate):
                result,_ = self.solve(Evaluator(mutate=mutate))
                self.assertFalse(result['engine_qualified']); self.assertEqual(result['evaluation_count'],1)
                self.assertEqual(result['evaluation_ledger'][0]['status'],'REFUSED')

    def test_same_density_operator_repeat_is_independent_exact_contract(self):
        def mutate(dm,value,count):
            if count == 2:
                value['fock'][1,1] = 2.
        result,_ = self.solve(Evaluator(mutate=mutate))
        self.assertFalse(result['engine_qualified'])
        self.assertEqual(result['stop_reason'],'NONREPRODUCIBLE_SAME_DENSITY_OPERATOR')

    def test_invalid_initial_or_configuration_has_zero_callback(self):
        for options in ({'density':np.eye(2)}, {'density':np.eye(2,dtype=complex)},
                        {'maximum_iterations':True}, {'finite_difference_step':True},
                        {'overlap':np.diag([-1.,1.])}):
            evaluator = Evaluator()
            with self.subTest(options=options),self.assertRaises(ValueError):
                ref.solve(density=options.get('density',np.diag([2.,0.])),
                    overlap=options.get('overlap',np.eye(2)),electrons=2,evaluate=evaluator,
                    initialization_policy='REQUIRE_EXISTING_MASKED_PROJECTOR',
                    **{k:v for k,v in options.items() if k not in ('density','overlap')})
            self.assertEqual(evaluator.calls,[])

    def test_initialization_policy_is_required_before_any_callback(self):
        evaluator = Evaluator()
        with self.assertRaises(TypeError):
            ref.solve(density=np.diag([2.,0.]),overlap=np.eye(2),electrons=2,evaluate=evaluator)
        self.assertEqual(evaluator.calls,[])


if __name__ == '__main__':
    unittest.main()
