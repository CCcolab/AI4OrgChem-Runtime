import unittest
import numpy as np
from runtime.user_molecule.acceptance_metrics import finite_scalar


class ScalarRecordTests(unittest.TestCase):
    def test_engine_numpy_real_scalars_keep_zero_and_signed_residuals(self):
        for value in (np.float64(0),np.float32(-1.25),np.int64(7),np.int32(0),0.,-2):
            self.assertEqual(finite_scalar(value),float(value))
        # Exact same nuclear energies previously caused a false T05 failure.
        self.assertEqual(finite_scalar(abs(33.2-np.float64(33.2))),0.)

    def test_nonfinite_bool_complex_and_array_cannot_be_metric_values(self):
        for value in (True,False,np.bool_(True),float('nan'),np.float64('inf'),
                      1j,np.array([0.]),np.array(0.),None,'0'):
            self.assertIsNone(finite_scalar(value))


if __name__=='__main__':
    unittest.main()
