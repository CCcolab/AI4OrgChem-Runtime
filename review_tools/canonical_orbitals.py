"""Additional canonical-MO checks on arrays only; never run an SCF solver."""
from __future__ import annotations
import hashlib,json,math
from pathlib import Path
import numpy as np

POLICY_PATH=Path(__file__).with_name('canonical_mo_policy_v1.json')
POLICY=json.loads(POLICY_PATH.read_bytes())
REQUIRED=('overlap','canonical_coefficients','orbital_energies_hartree','occupations','fock')


def review_arrays(arrays, *, electron_count):
    report={'schema':'canonical-mo-array-review-v1',
      'policy_sha256':hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest(),
      'policy':POLICY,'endpoint_numerical_qualification':{'status':'NOT_REEVALUATED_BY_ORBITAL_REVIEW'},
      'wavefunction_stability':{'status':'NOT_EXECUTED','qualified':False},
      'production_gate_modified':False,'scientific_backend_calls':0}
    missing=[key for key in REQUIRED if key not in arrays]
    if missing:
        report['full_orbital_qualification']={'status':'NOT_EXECUTED_MISSING_ARRAYS','qualified':False,'missing':missing}
        return report
    try:
        if type(electron_count) is not int or electron_count<2 or electron_count%2:
            raise ValueError('Explicit positive even electron count required')
        values={}
        for key in REQUIRED+('density',):
            if key not in arrays:continue
            a=np.asarray(arrays[key])
            if a.dtype.kind not in 'fciu' or not np.isfinite(a).all():
                raise ValueError('Finite numeric array required: '+key)
            if key in ('occupations','orbital_energies_hartree') and np.iscomplexobj(a):
                raise ValueError('Real occupations and orbital energies required')
            values[key]=a.astype(np.complex128 if np.iscomplexobj(a) else np.float64)
        s,c,eps,occ,f=(values[k] for k in REQUIRED)
        if s.ndim!=2 or s.shape[0]<1 or s.shape[0]!=s.shape[1]:
            raise ValueError('Overlap must be a nonempty square matrix')
        n=len(s)
        if c.shape!=(n,n) or f.shape!=(n,n) or eps.shape!=(n,) or occ.shape!=(n,):
            raise ValueError('Complete square MO space and aligned vectors required')
        if 'density' in values and values['density'].shape!=(n,n):
            raise ValueError('Density shape differs from AO space')
        sym_s=float(np.linalg.norm(s-s.conj().T,'fro'))
        sym_f=float(np.linalg.norm(f-f.conj().T,'fro'))
        if max(sym_s,sym_f)>POLICY['hermitian_frobenius_absolute_max']:
            raise ValueError('Overlap/Fock must be Hermitian')
        eig,u=np.linalg.eigh(s)
        if eig[0]<POLICY['minimum_overlap_eigenvalue'] or eig[-1]/eig[0]>POLICY['maximum_overlap_condition_number']:
            raise ValueError('Overlap outside declared positive/condition limit')
        half=(u*np.sqrt(eig))@u.conj().T
        inverse=(u*(1/np.sqrt(eig)))@u.conj().T
        cw=half@c;fw=inverse@f@inverse
        orth=float(np.linalg.norm(c.conj().T@s@c-np.eye(n),'fro'))
        equation=float(np.linalg.norm(f@c-s@(c*eps),'fro'))
        product=fw@cw
        whitened=float(np.linalg.norm(product-cw*eps,'fro'))
        scale=max(float(np.linalg.norm(product,'fro')),float(np.linalg.norm(cw,'fro')))
        if scale<=0:raise ValueError('Nonzero orbital normalization required')
        relative=whitened/scale
        occupation_valid=bool(np.all((occ==0)|(occ==2)) and float(occ.sum())==electron_count)
        nocc=electron_count//2
        if nocc>n:raise ValueError('Electron count exceeds full MO space')
        aufbau=bool(np.array_equal(occ,np.array([2.]*nocc+[0.]*(n-nocc))))
        sorted_eps=bool(np.all(np.diff(eps)>=-POLICY['energy_sort_absolute_hartree_max']))
        residuals={'full_orthonormality_frobenius':orth,'generalized_eigen_frobenius_hartree':equation,
          'whitened_eigen_relative':relative,'whitened_eigen_frobenius_hartree':whitened,
          'overlap_hermitian_frobenius':sym_s,'fock_hermitian_frobenius':sym_f}
        checks={'full_orthonormality':orth<=POLICY['orthonormality_frobenius_absolute_max'],
          'generalized_eigen_equation':equation<=POLICY['generalized_eigen_frobenius_hartree_max'],
          'whitened_relative_eigen_equation':relative<=POLICY['whitened_eigen_relative_max'],
          'occupation_electron_count':occupation_valid,'occupation_energy_column_alignment':aufbau and sorted_eps}
        if 'density' in values:
            d=values['density'];reconstructed=(c*occ)@c.conj().T
            density_error=float(np.linalg.norm(d-reconstructed,'fro'))/max(float(np.linalg.norm(d,'fro')),np.finfo(float).tiny)
            residuals['density_reconstruction_relative']=density_error
            checks['density_corresponds_to_occupied_columns']=density_error<=POLICY['density_reconstruction_relative_max']
        if not all(math.isfinite(x) for x in residuals.values()):
            raise ValueError('Nonfinite derived residual; input scale cannot be reviewed')
        ok=all(checks.values())
        report['full_orbital_qualification']={'status':'PASS_SAVED_ARRAYS_ONLY' if ok else 'REJECTED',
          'qualified':ok,'checks':checks,'residuals':residuals,
          'density_correspondence':'CHECKED' if 'density' in values else 'NOT_EXECUTED_MISSING_DENSITY',
          'scope':'Complete canonical arrays at the supplied geometry/operator only; no SCF, method, stability or new-installation acceptance.'}
    except (ValueError,TypeError,np.linalg.LinAlgError) as exc:
        report['full_orbital_qualification']={'status':'REJECTED_INPUT','qualified':False,'reason':str(exc)}
    return report
