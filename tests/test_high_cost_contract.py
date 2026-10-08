import importlib.util,unittest
from pathlib import Path
from runtime.high_cost_cases import units,unit,limits,validate_contract
from runtime.high_cost_cases.resources import admission
class Contracts(unittest.TestCase):
    def contract(self,mode='live',identifier='P12-N12-G'):
        r=limits('P12',mode)
        return {'schema':'high-cost-state-execution-v1','case':'P12','mode':mode,'unit':identifier,'execution_id':'a'*32,'image_id':'sha256:'+'b'*64,'runtime_build_commit':'c'*40,'source_sha256':'d'*64,'dependencies_sha256':'e'*64,'profile_sha256':'f'*64,'resources':r,'started_epoch':100.,'stop_deadline_epoch':100.+r['soft_wall_seconds'],'hard_deadline_epoch':100.+r['hard_wall_seconds'],'inputs':{}}
    def test_closed_registry_sizes(self):
        rows=units();self.assertEqual(len(rows),78)
        self.assertEqual(sum(r['case']=='P11' for r in rows),17)
        self.assertEqual(sum(r['system']=='N12' for r in rows),8)
        self.assertEqual(sum(r['system']=='N14' for r in rows),23)
        self.assertEqual(sum(r['system']=='N16' for r in rows),30)
    def test_metadata_contract_does_not_need_prior_live(self):
        c=self.contract('preflight');c['unit']=None;validate_contract(c)
    def test_state_method_is_not_arbitrary_user_input(self):
        with self.assertRaises(ValueError):unit('my-own-molecule')
        c=self.contract();c['method']='B3LYP'
        with self.assertRaises(ValueError):validate_contract(c)
    def test_wrong_case_and_dependencies_refused(self):
        c=self.contract();c['case']='P11'
        with self.assertRaises(ValueError):validate_contract(c)
        c=self.contract(identifier='P12-N16-GL')
        with self.assertRaises(ValueError):validate_contract(c)
    def test_resource_or_deadline_change_refused(self):
        c=self.contract();c['resources']['memory_bytes']=4*1024**3
        with self.assertRaises(ValueError):validate_contract(c)
        c=self.contract();c['hard_deadline_epoch']+=1
        with self.assertRaises(ValueError):validate_contract(c)
    def test_live_low_memory_admission_refuses(self):
        r=limits('P12','live');v=admission(r,{'NCPU':22,'MemTotal':16*1024**3},{'available_bytes':14*1024**3},{'available_bytes':int(1.2*1024**3)},100*1024**3)
        self.assertTrue(v['status'].startswith('BLOCKED'))
        self.assertIn('HOST_AVAILABLE_MEMORY_PLUS_RESERVE_TOO_SMALL',v['reasons'])
    def test_unknown_capacity_not_pass(self):
        v=admission(limits('P11','live'),{}, {},{},0)
        self.assertEqual(v['status'],'BLOCKED_RESOURCE_UNKNOWN')
    def test_p11_seed_exception_has_bounded_scope(self):
        self.assertEqual(unit('P11B-cyanobenzene-GE7')['caps']['conditional'],1)
        self.assertEqual(unit('P11B-cyanobenzene-GL_II')['caps']['conditional'],0)
        self.assertEqual(unit('P11B-benzene-GE1')['caps']['conditional'],0)
if __name__=='__main__':unittest.main()
