"""Independent analytic normalization oracles; no quantum backend calls."""
from pathlib import Path
import tempfile, unittest
import numpy as np
from review_tools.skill_examples import evaluate, run_fixture


class LeakageExamples(unittest.TestCase):
    def result(self, v, s=None, b=None):
        return evaluate('nonorthogonal-subspace', {
            'S': np.eye(2) if s is None else s,
            'B': [[1], [0]] if b is None else b, 'v': v})

    def ratio(self, v, expected, **kwargs):
        self.assertAlmostEqual(self.result(v, **kwargs)['squared_leakage'], expected, places=12)

    def test_unit_vector(self): self.ratio([0, 1], 1.)
    def test_scaled_positive(self): self.ratio([0, 2], 1.)
    def test_scaled_negative(self): self.ratio([0, -3], 1.)
    def test_complex_scalar(self): self.ratio([0, 2j], 1.)
    def test_nonunit_metric(self): self.ratio([0, 1], 1., s=np.diag([1., 4.]))
    def test_mixed_direction(self): self.ratio([2, 2], .5)

    def test_zero_vector_refused(self):
        with self.assertRaisesRegex(ValueError, 'zero vector.*undefined'):
            self.result([0, 0])

    def test_extreme_nonzero_scaling_invariant(self):
        for alpha in (1e-320, 1e-300, 1e300, -3., 2j, 1e-300j, 1e300j):
            with self.subTest(alpha=alpha): self.ratio(alpha*np.array([2., 2.]), .5)

    def test_complex_hermitian_metric(self):
        # Schur complement: (3-|i|^2/2)/3 = 5/6 for the second-axis vector.
        self.ratio([0, 2j], 5/6, s=np.array([[2, 1j], [-1j, 3]]))

    def test_basis_column_scaling_invariant(self):
        for alpha in (1e-300, 1e300, -2j):
            with self.subTest(alpha=alpha): self.ratio([2, 2], .5, b=alpha*np.array([[1.], [0.]]))

    def test_zero_basis(self):
        result=self.result([2, 2], b=np.zeros((2, 1)))
        self.assertEqual(result, {'rank': 0, 'squared_leakage': 1.})

    def test_full_subspace(self): self.ratio([2, 2j], 0., b=np.eye(2))

    def test_shape_refusals(self):
        for changes in ({'v': [[0], [1]]}, {'v': [[0, 1]]}, {'v': [0, 1, 2]},
                        {'B': [1, 0]}, {'B': np.zeros((3, 1))}, {'B': np.zeros((2, 0))},
                        {'S': np.zeros((0, 0))}):
            data={'S': np.eye(2), 'B': [[1], [0]], 'v': [0, 1]};data.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                evaluate('nonorthogonal-subspace', data)

    def test_nonfinite_refusals(self):
        for key, value in (('v', [0, np.nan]), ('v', [0, np.inf]),
                           ('B', [[np.inf], [0]]), ('S', [[1, 0], [0, np.nan]])):
            data={'S': np.eye(2), 'B': [[1], [0]], 'v': [0, 1]};data[key]=value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'finite'):
                evaluate('nonorthogonal-subspace', data)

    def test_ill_conditioned_metric_refused(self):
        with self.assertRaisesRegex(ValueError, 'metric condition'):
            self.result([0, 1], s=np.diag([1., 1e13]))

    def test_rank_deficient_basis(self):
        result=self.result([2, 2], b=[[1, 2, 0], [0, 0, 0]])
        self.assertEqual(result['rank'], 1)
        self.assertAlmostEqual(result['squared_leakage'], .5)

    def test_zero_vector_is_recorded_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, result=run_fixture('nonorthogonal-subspace',
                {'S': np.eye(2), 'B': [[1], [0]], 'v': [0, 0]}, Path(tmp)/'new')
            self.assertEqual((code, result['status']), (2, 'EXPECTED_REFUSAL'))
            self.assertIn('undefined', result['message'])
