import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from runtime.registered_cases import strict_load, validate_contract, verify_source

def fixture(task='p02-statistics'):
    quantum=task=='p01-orbital-density'
    return {'schema':'registered-case-execution-v1','task':task,
        'protocol_id':{'p02-statistics':'P02_STRUCTURE_UV_SOURCE_FREEZE_V0.1','p13-graph-ledger':'p13-polycyclic-benzenoid/0.1','p01-orbital-density':'P01_ETHENE_OCCUPIED_GAUGE_CONTROL_V0.1'}[task],
        'scientific_execution_authorized':quantum,'runtime_commit':'a'*40,'source_snapshot_sha256':'b'*64,
        'dependency_lock_sha256':'c'*64,'execution_id':'d'*32,'memory_limit_bytes':1073741824,
        'threads':1,'maximum_processes':1,'wall_time_limit_seconds':120,'stop_after_seconds':100,
        'started_epoch':1000.,'stop_deadline_epoch':1100.,'hard_deadline_epoch':1120.,
        'scf_kernel_call_limit':int(quantum),'boys_kernel_call_limit':int(quantum),'pipek_mezey_kernel_call_limit':int(quantum),
        **({'p01_protocol_sha256':'d137c04a22fd221129f7a1e62fcafa6928e7ddee1493082ca40158a3c230ac47'} if quantum else {})}

class ContractTests(unittest.TestCase):
    def test_fixed_tasks_only(self):
        for task in ('p02-statistics','p13-graph-ledger','p01-orbital-density'):
            self.assertIn('module',validate_contract(fixture(task)))
    def test_cannot_promote_pure_task_to_quantum(self):
        value=fixture();value['scientific_execution_authorized']=True
        with self.assertRaises(ValueError):validate_contract(value)
    def test_fixed_geometry_and_resource_inputs_cannot_be_overridden(self):
        for name,value in [('xyz','arbitrary'),('threads',4),('maximum_processes',2),('scf_kernel_call_limit',2),('memory_limit_bytes',True),('stop_deadline_epoch',1101.),('hard_deadline_epoch',1121.)]:
            item=fixture('p01-orbital-density');item[name]=value
            with self.subTest(name=name),self.assertRaises(ValueError):validate_contract(item)
    def test_false_is_not_zero(self):
        item=fixture();item['scf_kernel_call_limit']=False
        with self.assertRaises(ValueError):validate_contract(item)
    def test_p01_protocol_must_match(self):
        item=fixture('p01-orbital-density');item['p01_protocol_sha256']='e'*64
        with self.assertRaises(ValueError):validate_contract(item)
    def test_duplicate_or_nonfinite_json_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            file=Path(temporary)/'input.json'
            for text in ('{"a":1,"a":2}','{"a":NaN}'):
                file.write_text(text)
                with self.assertRaises(ValueError):strict_load(file)
    def test_source_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'program.py').write_text('wrong bytes')
            lock=root/'lock.json';lock.write_text(json.dumps({'schema':'registered-case-source-v1','files':{'program.py':'f'*64}}))
            with patch('runtime.registered_cases.ROOT',root),patch('runtime.registered_cases.SOURCE_LOCK',lock),self.assertRaises(ValueError):verify_source()

if __name__=='__main__':unittest.main()
