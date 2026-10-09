import importlib.util
import json
import math
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
from ai4orgchem.qm.user_molecule_adapter import inspect, strict_value, compute, metrics_qualified


class AdapterEngineeringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        profile_path=Path(os.environ.get('USER_MOLECULE_PROFILE', '/opt/runtime/profiles/user-molecule/pilot-b3lypg-sto3g-grid2-v1.json'))
        cls.profile=json.loads(profile_path.read_text())
        cls.request={'resources':{'threads':1},'fragments':[{'id':'A','carbon_atom_indices_1based':[1,2]}, {'id':'B','carbon_atom_indices_1based':[3,4]}]}
        cls.atoms=[['C',[-2.,0.,0.]],['C',[-.7,0.,0.]],['C',[.7,0.,0.]],['C',[2.,0.,0.]]]

    def test_inspect_does_not_run_scf_grid_or_full_eri(self):
        from pyscf import gto, scf, dft
        original=gto.Mole.intor
        def guarded(mol,name,*args,**kwargs):
            if name.startswith('int2e'):
                self.fail('Inspect allocated electron-repulsion integrals')
            return original(mol,name,*args,**kwargs)
        with patch.object(gto.Mole,'intor',guarded), patch('pyscf.scf.hf.kernel',side_effect=AssertionError('SCF forbidden')), patch.object(dft.gen_grid.Grids,'build',side_effect=AssertionError('Grid forbidden')):
            result=inspect(self.request,self.atoms,self.profile)
        self.assertEqual(result['nao'],20)
        self.assertEqual(result['electron_count'],24)
        self.assertEqual({x['fragment'] for x in result['ao_descriptors'] if x['kind']=='pi'}, {'A','B'})
        self.assertFalse(result['scf_executed'])
        self.assertEqual(result['dependencies'],self.profile['expected_dependencies'])

    def test_compute_disabled_before_allocating_science(self):
        with self.assertRaisesRegex(RuntimeError,'blocked'):
            compute(self.request,self.atoms,self.profile)

    def test_nonfinite_diagnostics_have_reason_not_zero(self):
        reasons=[]
        value=strict_value({'history':[{'energy_change_hartree':math.inf}],'gap':math.nan},reasons)
        self.assertIsNone(value['history'][0]['energy_change_hartree'])
        self.assertIsNone(value['gap'])
        self.assertEqual(len(reasons),2)
        json.dumps(value,allow_nan=False)

    def test_required_nonfinite_energy_fails_gate(self):
        values={'converged':True,'total_energy_hartree':math.nan,'physical_metric_electron_count':24.,
                'final_commutator_frobenius_norm':0.,'closed_shell_idempotency_relative_residual':0.,'energy_component_closure_residual_hartree':0.}
        self.assertFalse(all(metrics_qualified(values,24,self.profile,False).values()))

if __name__=='__main__':
    unittest.main()
