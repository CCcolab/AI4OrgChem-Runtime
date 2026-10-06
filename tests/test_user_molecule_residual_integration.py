"""Prepared mapping -> two bridges -> independent reference -> durable slots.

Uses explicitly synthetic14-AO ethene-shaped arrays and a fake XC callback.
Cached metadata, source mapping and output records are exercised; no molecule
SCF, integral generation, grid build, real XC or research result is produced.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

import numpy as np

from reference.ordinary_molecule import ReferenceResult
from reference.residual_molecule import PreparedResidualReference
from runtime.user_molecule.residual_bridge import PreparedResidualBridge, array_identity
from runtime.user_molecule.residual_candidate import density_id
from runtime.user_molecule.residual_budget import ConditionalCallbackBudget, CallbackBudgetError
from runtime.user_molecule.residual_preparation import create_bridge_contract
from test_user_molecule_residual_preparation import ResidualPreparationTests, ROOT, SCIENCE


class FakeXC:
    def __init__(self):self.calls=0
    def rsh_and_hybrid_coeff(self,*args,**kwargs):return 0.,.2,.2
    def nr_rks(self,mol,grids,xc,density,**kwargs):
        self.calls+=1
        return float(np.trace(density)),0.,np.zeros_like(density)


class JournaledBridge(PreparedResidualBridge):
    """Test integration without modifying the underlying bridge/operator."""
    def attach(self,journal,path_id):
        self.accounted=journal.accounted_callback(path_id,super().evaluate,
            density_identity=density_id,operator_identity=lambda value:density_id(value['fock']))
        return self
    def evaluate(self,density,phase='SOLVER_CALLBACK'):
        return self.accounted(density,phase=phase)


class JournaledReference(PreparedResidualReference):
    def attach(self,journal,path_id):
        self.accounted=journal.accounted_callback(path_id,super().evaluate,
            density_identity=density_id,operator_identity=lambda value:density_id(value['fock']))
        return self
    def evaluate(self,density):return self.accounted(density)


class ResidualIntegrationTests(unittest.TestCase):
    def setUp(self):
        fixture=ResidualPreparationTests()
        fixture.setUp()
        self.fixture=fixture
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name)
        self.xc=FakeXC();fixture.mf._numint=self.xc
        fixture.mol.energy_nuc=lambda:1.2
        fixture.arrays['hcore']=np.diag(list(range(-8,0))+list(range(1,7))).astype(float)
        fixture.record['array_identities']={name:array_identity(value) for name,value in fixture.arrays.items()}
        fixture.record['components_hartree']={'one_electron':-72.,'coulomb':0.,'exact_exchange':0.,
            'semilocal_xc':0.,'nuclear_repulsion':1.2}
        fixture.record['total_energy_hartree']=-70.8
        self.ordinary=ReferenceResult(fixture.record,fixture.arrays,fixture.context)
        self.ids={'geometry_sha256':fixture.bundle['xyz_sha256'],
            'profile_sha256':fixture.prepared['profile_sha256'],
            'dependencies_sha256':hashlib.sha256(json.dumps(fixture.profile['expected_dependencies'],
                sort_keys=True,separators=(',',':')).encode()).hexdigest(),'mode':'ENGINEERING_FAKE'}
        self.journal=ConditionalCallbackBudget(path=self.root/'callbacks.json',batch_id='synthetic-ethene',
            identity=self.ids,path_limits={'production_copy':201,'production_owned':201,'independent_reference':201},total_limit=603)

    def prepared(self,maximum_evaluations=201):
        fixture=self.fixture
        record_path=self.root/'ordinary-fake.json';archive_path=self.root/'ordinary-fake.npz'
        record_path.write_text(json.dumps(fixture.record,allow_nan=False),encoding='utf-8')
        np.savez(archive_path,**fixture.arrays)
        return create_bridge_contract(runtime_root=ROOT,science_root=SCIENCE,prepared_input=fixture.prepared,
            context=fixture.context,arrays=fixture.arrays,ordinary_record=fixture.record,
            runtime_test_commit=os.environ.get('AI4ORGCHEM_RUNTIME_TEST_COMMIT','a1'*20),
            image_id=os.environ.get('AI4ORGCHEM_IMAGE_ID','sha256:'+'b2'*32),
            image_build_commit=os.environ.get('AI4ORGCHEM_IMAGE_BUILD_COMMIT','c3'*20),
            execution_kind='ENGINEERING_FAKE',initialization_policy='FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0',
            maximum_evaluations=maximum_evaluations,ordinary_record_path=record_path,ordinary_arrays_path=archive_path)

    def reference(self,limit=201):
        return JournaledReference(ordinary=self.ordinary,
            rule_path=SCIENCE/'configs/qm/p09_exchange_integral_classes_v0.1.yaml',
            expected_sha256='324c2e7988be48ed8898a5e9b04a87d40386ca8a8f7eb603d9a697d3ac6a6ee2',
            initialization_policy='FIRST_RAW_GLOBAL_AUFBAU_AT_ORDINARY_D0',
            maximum_evaluations=limit,execution_kind='ENGINEERING_FAKE').attach(self.journal,'independent_reference')

    def test_same_density_full_operator_and_components_match_independent_reference(self):
        fixture=self.fixture
        factor=np.arange(196,dtype=float).reshape(14,14);factor=(factor+factor.T)/2000
        fixture.arrays['eri']=np.einsum('pq,rs->pqrs',factor,factor)
        fixture.record['array_identities']['eri']=array_identity(fixture.arrays['eri'])
        before={name:array_identity(value) for name,value in fixture.arrays.items()}
        prepared=self.prepared();reference=self.reference()
        target=fixture.arrays['density']
        independent=reference.evaluate(target)
        raw=reference.last_evaluation
        for path,mode,optimize in (('production_copy','COPY_MASK',True),('production_owned','INPLACE_OWNED',False)):
            tested=JournaledBridge(**prepared['bridge_kwargs'],eri_mode=mode,
                optimize_eri_contractions=optimize).attach(self.journal,path)
            value=tested.evaluate(target,phase='SAME_DENSITY_WITNESS')
            for key,other in (('fock','Fcond'),('raw_fock','Fraw'),('coulomb_matrix','J'),
                              ('exchange_matrix','K'),('xc_potential','Vxc')):
                np.testing.assert_allclose(value[key],raw[other],rtol=0,atol=1e-10)
                self.assertLessEqual(float(np.linalg.norm(value[key]-raw[other])),1e-9)
            for key in ('total_energy','one_electron_energy','coulomb_energy','exact_exchange_energy',
                        'semilocal_xc_energy','nuclear_repulsion'):
                self.assertLessEqual(abs(value[key]-independent[key]),1e-9)
            self.assertEqual(tested.deleted_eri_count,reference.deleted)
            np.testing.assert_array_equal(tested.masked_eri,reference.masked_eri)
            self.assertLessEqual(abs(value['grid_electron_count']-raw['grid_electron_count']),1e-9)
        self.assertEqual(self.journal.snapshot()['charged_slots'],3)
        self.assertEqual({name:array_identity(value) for name,value in fixture.arrays.items()},before)

    def test_all_three_paths_use_same_d0_and_qualify_toy_without_research_promotion(self):
        prepared=self.prepared();outputs=[]
        for path,mode,optimize in (('production_copy','COPY_MASK',True),('production_owned','INPLACE_OWNED',False)):
            tested=JournaledBridge(**prepared['bridge_kwargs'],eri_mode=mode,
                optimize_eri_contractions=optimize).attach(self.journal,path)
            result=tested.run();self.assertTrue(result['solver_result']['engine_qualified'])
            self.assertFalse(result['comparison_available']);self.assertIsNone(result['delta_hartree'])
            self.assertEqual(result['initialization']['ordinary_density_id'],density_id(self.fixture.arrays['density']))
            self.journal.close_path(path,result['stop_reason'])
            outputs.append(result['solver_result']['density'])
        reference=self.reference();result=reference.run()
        self.assertTrue(result['engine_qualified']);self.assertEqual(result['real_functional_attempt_count'],0)
        self.assertFalse(result['comparison_available']);self.assertIsNone(result['delta_hartree'])
        self.journal.close_path('independent_reference',result['stop_reason']);outputs.append(result['density'])
        for value in outputs:np.testing.assert_allclose(value,self.fixture.arrays['density'],rtol=0,atol=1e-9)
        snapshot=self.journal.snapshot()
        self.assertEqual(snapshot['charged_slots'],self.xc.calls)
        self.assertEqual(snapshot['path_charged_slots'],dict.fromkeys(snapshot['paths'],4))
        self.assertEqual(snapshot['charged_slots'],12)
        self.assertEqual(snapshot['pending_slots'],0)
        self.assertTrue(all(row['state']=='CLOSED' for row in snapshot['paths'].values()))

    def test_lost_callback_charge_cannot_be_retried_after_reopening(self):
        lost=self.journal.charge('production_copy',density_id(self.fixture.arrays['density']),'INITIALIZE_AT_ORDINARY_D0')
        self.journal.close_path('production_copy','SIMULATED_PROCESS_LOST')
        reopened=ConditionalCallbackBudget(path=self.root/'callbacks.json',batch_id='synthetic-ethene',
            identity=self.ids,path_limits={'production_copy':201,'production_owned':201,'independent_reference':201},total_limit=603)
        with self.assertRaises(CallbackBudgetError):
            reopened.charge('production_copy',lost['density_id'],'RETRY')
        self.assertEqual(reopened.snapshot()['pending_slots'],1);self.assertEqual(self.xc.calls,0)

    def test_shared_journal_exhaustion_prevents_any_further_operator_entry(self):
        journal=ConditionalCallbackBudget(path=self.root/'tight.json',batch_id='tight',identity=self.ids,
            path_limits={'production_copy':1},total_limit=1)
        prepared=self.prepared()
        tested=JournaledBridge(**prepared['bridge_kwargs']).attach(journal,'production_copy')
        result=tested.run()
        self.assertFalse(result['solver_result']['engine_qualified'])
        self.assertEqual(self.xc.calls,1)
        self.assertEqual(journal.snapshot()['charged_slots'],1)
        self.assertEqual(result['global_evaluation_count'],1)


if __name__=='__main__':unittest.main()
