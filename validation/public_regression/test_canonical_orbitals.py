import copy,json,tempfile,unittest
from pathlib import Path
import numpy as np
from review_tools.canonical_orbitals import review_arrays


def sample():
    return {'overlap':np.eye(2),'canonical_coefficients':np.eye(2),
      'orbital_energies_hartree':np.array([-1.,1.]),'occupations':np.array([2.,0.]),
      'fock':np.diag([-1.,1.]),'density':np.diag([2.,0.])}


class CanonicalQualification(unittest.TestCase):
    def check(self,data):return review_arrays(data,electron_count=2)
    def test_complete_valid_arrays(self):
        r=self.check(sample());self.assertTrue(r['full_orbital_qualification']['qualified'])
        self.assertEqual(r['wavefunction_stability']['status'],'NOT_EXECUTED')
        self.assertEqual(r['endpoint_numerical_qualification']['status'],'NOT_REEVALUATED_BY_ORBITAL_REVIEW')
    def test_corrupt_virtual_rejected_while_old_endpoint_passes(self):
        from runtime.molecular_service.engine import orbital_density_diagnostics
        a=sample();a['canonical_coefficients'][:,1]=[7.,7.]
        old=orbital_density_diagnostics(overlap=a['overlap'],density=a['density'],
          coefficients=a['canonical_coefficients'],occupations=a['occupations'],
          orbital_energies=a['orbital_energies_hartree'],fock=a['fock'],hcore=a['fock'],
          veff=np.zeros((2,2)),electron_count=2,nuclear_energy=0.,total_energy=-2.,scf_converged=True)
        self.assertTrue(old['numerically_qualified'])
        r=self.check(a)['full_orbital_qualification'];self.assertFalse(r['qualified'])
        self.assertAlmostEqual(r['residuals']['full_orthonormality_frobenius'],97.50384607704715)
        self.assertEqual(r['residuals']['generalized_eigen_frobenius_hartree'],14)
    def test_missing_fock_not_pass(self):
        a=sample();del a['fock'];r=self.check(a)['full_orbital_qualification']
        self.assertEqual(r['status'],'NOT_EXECUTED_MISSING_ARRAYS');self.assertFalse(r['qualified'])
    def test_nonfinite_rejected(self):
        a=sample();a['canonical_coefficients'][1,1]=np.nan
        self.assertFalse(self.check(a)['full_orbital_qualification']['qualified'])
    def test_rectangular_space_rejected(self):
        a=sample();a['canonical_coefficients']=np.ones((2,1))
        self.assertFalse(self.check(a)['full_orbital_qualification']['qualified'])
    def test_wrong_energy_column_rejected(self):
        a=sample();a['orbital_energies_hartree']=np.array([1.,-1.])
        self.assertFalse(self.check(a)['full_orbital_qualification']['qualified'])
    def test_wrong_occupations_rejected(self):
        a=sample();a['occupations']=np.array([0.,2.])
        self.assertFalse(self.check(a)['full_orbital_qualification']['qualified'])
    def test_complex_phase_is_valid(self):
        a=sample();a['canonical_coefficients']=np.diag([1j,-1j])
        self.assertTrue(self.check(a)['full_orbital_qualification']['qualified'])
    def test_nonpositive_metric_rejected(self):
        a=sample();a['overlap'][0,0]=-1
        self.assertFalse(self.check(a)['full_orbital_qualification']['qualified'])
    def test_density_mismatch_rejected(self):
        a=sample();a['density']=np.diag([0.,2.])
        self.assertFalse(self.check(a)['full_orbital_qualification']['qualified'])
    def test_fractional_occupation_not_closed_shell_policy(self):
        a=sample();a['occupations']=np.array([1.,1.])
        self.assertFalse(self.check(a)['full_orbital_qualification']['qualified'])
    def test_absolute_orthogonality_limit_is_enforced(self):
        a=sample();a['canonical_coefficients'][1,1]+=1e-6
        self.assertFalse(self.check(a)['full_orbital_qualification']['checks']['full_orthonormality'])
    def test_wrong_electron_count_not_pass(self):
        self.assertFalse(review_arrays(sample(),electron_count=4)['full_orbital_qualification']['qualified'])
    def test_nonhermitian_fock_rejected(self):
        a=sample();a['fock'][0,1]=.1
        self.assertFalse(self.check(a)['full_orbital_qualification']['qualified'])
