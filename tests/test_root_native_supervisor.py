"""Supervisor contracts with mocked tools; no Docker/native execution."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from test_root_native_contract import contract_fixture, future_fixture

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/diagnose-user-molecule-root-native.py'
spec=importlib.util.spec_from_file_location('root_native_host_under_test',SCRIPT)
host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)


def readiness(contract, checksum):
    return {'status':'PASS_GATED_SOURCE_NATIVE_INPUT_PREPARATION_ONLY','contract_sha256':checksum,
        'runtime_test_commit':contract['runtime_test_commit'],'parent_contract_sha256':host.protocol.PARENT_RAW_SHA256,
        'contract_family_sha256':contract['contract_family_sha256'],'selected_density_id':contract['initial_density']['density_id'],
        'selected_seed_index':2,'selected_angle_rad':-.1,'four_seed_recipe_verified':True,
        'source_file_sha256':contract['source_file_sha256'],'actual_native_NR_calls':0,'new_scientific_budget':None,
        'root_solve':'NOT_EXECUTED','Compute':False,'guarded_operations':sorted(host.PREPARE_GUARDS),
        'changed_guards':[],'forbidden_attempts':[]}


def final_fixture():
    """Metadata-only future result fixture, never evidence of a molecular F."""
    contract,grant=future_fixture();checksum='af'*32
    did=contract['initial_density']['density_id'];mapped='cd'*32
    rows=[{'slot_id':index,'path_id':'independent_reference','density_id':density,'phase':phase,
        'status':'SUCCEEDED','operator_id':('ae' if index<3 else 'ac')*32}
        for index,(density,phase) in enumerate(((did,'CURRENT_INITIAL'),(did,'FINAL_RETURNED_DENSITY'),
            (mapped,'FINAL_RAW_AUFBAU_DENSITY_RECHECK')),1)]
    counts={'charged':3,'pending':0,'succeeded':3,'failed':0,'limit':201}
    nr={'entered':3,'completed':3,'failed':0}
    source={'status':'OBSERVED_DISPATCH_EVENTS_FACTORY_BINDING_REQUIRED',**nr}
    accounting={'execution_kind':'SOURCE_NATIVE_DIAGNOSTIC','scientific_execution_authorized':True,
        'closed':True,'persistence_intact':True,'status':'CLOSED','callback_slots':counts,
        'nr_dispatch_counts':nr,'source_native_dispatch_counts':source,'identity_sha256':'ba'*32,
        'slots':[{**row,'nr_entered':1,'nr_completed':1,'nr_failed':0} for row in rows],
        'admission_groups':{'1':{'row':{'status':'COMPLETED','kind':'FINAL_TAIL','actual_callbacks':2},'slots':[2,3]}}}
    callbacks={'slots':rows,'path_limits':{'independent_reference':201},'total_limit':201,
        'paths':{'independent_reference':{'state':'CLOSED'}},'identity':host.protocol.execution_identity(contract,checksum,
            explicit_grant=grant,local_cli_execute_requested=True)}
    guards={'guarded_operations':sorted(host.GUARDS),'changed_bindings':[],'forbidden_attempts':[],
        'new_ordinary_SCF_grid_full_integrals':0,'nuclear_repulsion_calls':0}
    summary={'status':'EXECUTED_SINGLE_PATH_ROOT_DIAGNOSTIC_ONLY','Compute':False,'method_approval':False,
        'automatic_retry':False,'research_delta_hartree':None,'independent_production_equivalence':'NOT_EXECUTED',
        'endpoint_qualified':True,'stop_reason':'QUALIFIED_TRUE_ARRAY_ENDPOINT','source_NR_counts':source,'callback_slots':counts}
    registry={'evaluation-'+str(row['slot_id']):{key:row[key] for key in ('density_id','operator_id','phase')} for row in rows}
    result={'execution_kind':'SOURCE_NATIVE_DIAGNOSTIC','status':'SOURCE_BOUND_ROOT_DIAGNOSTIC_CANDIDATE',
        'scientific_execution_authorized':True,'engine_qualified':True,'stop_reason':summary['stop_reason'],
        'evaluator_execution_snapshot':{'binding_validated':True,'execution_kind':'SOURCE_NATIVE_DIAGNOSTIC'},
        'evaluation_count':3,'native_accounting_snapshot':copy.deepcopy(accounting),
        'endpoint_gate':{'qualified':True,'returned_density_energy_recheck_hartree':0.0,'mapped_density_energy_change_hartree':1e-12},
        'mapped_endpoint_gate':{'qualified':True},'snapshot_registry':registry,
        'returned_density':{'density_id':did,'matched_snapshot_id':'evaluation-2','matched_operator_id':rows[1]['operator_id']}}
    return summary,accounting,callbacks,guards,contract,checksum,result


class FakeDocker:
    def __init__(self, executable, output, *, receipt_mutation=None, cleanup_failure=False):
        self.output=Path(output);self.commands=[];self.token=None;self.cid='ab'*32
        self.receipt_mutation=receipt_mutation;self.cleanup_failure=cleanup_failure;self.deleted=False
        self.image=contract_fixture()['parent_preparation_contract']
    def __call__(self,*args,timeout=10):
        self.commands.append({'arguments':list(args)})
        if args[:2]==('image','inspect'):
            return json.dumps([{'Id':self.image['image_id'],'Config':{'Labels':{
                'org.opencontainers.image.revision':self.image['image_build_runtime_commit'],
                'ai4orgchem.source.commit':self.image['science_commit']}}}]).encode()
        if args[0]=='info':return json.dumps({'NCPU':4,'MemTotal':4*1073741824,'ContainersRunning':0}).encode()
        if args[0]=='create':
            self.token=args[args.index('--label')+1].split('=',1)[1]
            cp=json.loads((self.output/'native-contract.json').read_bytes())
            leaf=self.output/'output';value=readiness(cp,host.sha(self.output/'native-contract.json'))
            if self.receipt_mutation:self.receipt_mutation(value)
            (leaf/'native-readiness.json').write_text(json.dumps(value))
            (leaf/'resources.jsonl').write_text(json.dumps({'cgroup':{'toy':'mocked-only'}})+'\n')
            return self.cid.encode()
        if args[0]=='start':return self.cid.encode()
        if args[0]=='inspect':return json.dumps([self.inspection()]).encode()
        if args[0]=='rm':
            if self.cleanup_failure:raise RuntimeError('toy deletion refused')
            self.deleted=True;return self.cid.encode()
        if args[0]=='stop':return self.cid.encode()
        raise AssertionError('Unexpected tool command: '+str(args))
    def inspection(self):
        return {'Image':self.image['image_id'],'Config':{'User':'10001:10001','Labels':{host.LABEL:self.token}},
            'HostConfig':{'ReadonlyRootfs':True,'NetworkMode':'none','Memory':1073741824,'MemorySwap':1073741824,
                'NanoCpus':1000000000,'CapDrop':['ALL'],'SecurityOpt':['no-new-privileges:true']},
            'Mounts':[{'Destination':name,'RW':False} for name in
                ('/workspace','/saved-ordinary','/seed-input','/native-contract.json','/parent-contract.json')],
            'State':{'Running':False,'ExitCode':0,'OOMKilled':False,'FinishedAt':'test-fixture-only'}}


class RootNativeSupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name);self.contract=contract_fixture()
        self.inputs=self.root/'inputs';self.inputs.mkdir();self.cache=self.root/'cache';self.cache.mkdir()
        (self.root/'old-preparation').mkdir()
        self.parent=self.root/'old-preparation/parent.json';self.parent.write_text('{}')
        self.args=host.argument_parser().parse_args(['--output-root',str(self.root/'run'),
            '--seed-input-dir',str(self.inputs),'--parent-contract',str(self.parent),'--docker','NOT_A_REAL_DOCKER'])
    def execute_mock(self, *, mutation=None, cleanup_failure=False, clock=None, resource_status='RESOURCE_CANDIDATE_EXACT_FIXTURE'):
        created=[]
        def factory(executable, output):
            value=FakeDocker(executable,output,receipt_mutation=mutation,cleanup_failure=cleanup_failure);created.append(value);return value
        def export(output):
            (Path(output)/'runtime-source').mkdir()
            return {'runtime_commit':self.contract['runtime_test_commit'],'status':'VERIFIED_PREPARED_SOURCE'}
        with mock.patch.object(host,'DockerCommands',side_effect=factory), \
             mock.patch.object(host,'export_source',side_effect=export), \
             mock.patch.object(host,'build_contract',return_value=(copy.deepcopy(self.contract),self.cache,b'{}')), \
             mock.patch.object(host,'host_memory',return_value={'status':'ADMITTED_HOST_ONLY'}), \
             mock.patch.object(host,'claim_family_attempt',side_effect=AssertionError('prepare cannot claim native family')), \
             mock.patch.object(host,'qualify_exact_fixture',return_value={'status':resource_status}), \
             mock.patch.object(host.subprocess,'run',return_value=subprocess.CompletedProcess([],0,b'kept stdout',b'kept stderr')), \
             mock.patch.object(host.time,'monotonic',side_effect=clock if clock is not None else None,return_value=10):
            result=host.run_supervisor(self.args)
        return result,created[0]
    def test_default_cli_is_prepare_only_and_execute_missing_grant_refuses_before_tools(self):
        self.assertIs(self.args.execute,False)
        self.args.execute=True
        with mock.patch.object(host,'DockerCommands',side_effect=AssertionError('no tools')):
            with self.assertRaises(ValueError):host.run_supervisor(self.args)
        self.assertFalse(self.args.output_root.exists())
    def test_mutually_exclusive_modes_and_grant_on_prepare_are_refused(self):
        with self.assertRaises(SystemExit):
            host.argument_parser().parse_args(['--output-root','toy','--prepare-only','--execute'])
        self.args.grant_file=self.root/'not-used.json'
        with self.assertRaises(ValueError):host.run_supervisor(self.args)
    def test_readiness_rejects_label_only_bool_zero_source_mismatch_and_guard_change(self):
        original=readiness(self.contract,'af'*32)
        self.assertTrue(host.verify_native_readiness(original,self.contract,'af'*32))
        for key,value in (('actual_native_NR_calls',False),('actual_native_NR_calls',0.0),
                ('source_file_sha256',{}),('four_seed_recipe_verified',1),('changed_guards',['lost']),('root_solve','PASS')):
            with self.subTest(key=key,value=value):
                receipt=copy.deepcopy(original);receipt[key]=value
                with self.assertRaises(ValueError):host.verify_native_readiness(receipt,self.contract,'af'*32)
    def test_mocked_prepare_preserves_false_contract_logs_output_and_deletes_owned_container(self):
        result,tool=self.execute_mock()
        self.assertEqual(result,0);self.assertTrue(tool.deleted)
        output=self.args.output_root;value=json.loads((output/'EXECUTION.json').read_bytes())
        self.assertEqual(value['status'],'EXECUTED_ZERO_F_NATIVE_PREPARATION_ONLY')
        self.assertFalse(value['scientific_budget_reserved'])
        self.assertEqual((output/'stdout.log').read_bytes(),b'kept stdout')
        self.assertTrue((output/'output/native-readiness.json').exists())
        self.assertIsNone(json.loads((output/'native-contract.json').read_bytes())['budget_reservation'])
        launch=json.loads((output/'launch-command.json').read_bytes())
        self.assertIn('--prepare-only',launch);self.assertNotIn('--execute',launch)
        self.assertNotIn('--grant-file',launch)
    def test_exit_zero_with_forged_readiness_does_not_pass(self):
        result,tool=self.execute_mock(mutation=lambda value:value.update(actual_native_NR_calls=False))
        self.assertEqual(result,1);self.assertTrue(tool.deleted)
        value=json.loads((self.args.output_root/'EXECUTION.json').read_bytes())
        self.assertEqual(value['status'],'FAILED_NO_RETRY')
        self.assertNotIn('worker_receipts_verified',value)
    def test_cleanup_failure_is_unknown_and_keeps_wall_reservation(self):
        result,tool=self.execute_mock(cleanup_failure=True)
        self.assertEqual(result,1);self.assertFalse(tool.deleted)
        value=json.loads((self.args.output_root/'EXECUTION.json').read_bytes())
        self.assertEqual(value['status'],'CLEANUP_UNKNOWN_NO_RETRY')
        wall=json.loads((self.args.output_root/'WALL_SETTLEMENT.json').read_bytes())
        self.assertEqual(wall['unresolved_reserved_seconds'],120)
    def test_cleanup_time_is_included_and_resource_unknown_cannot_pass(self):
        result,_=self.execute_mock(clock=[0,1,1,121])
        self.assertEqual(result,1)
        value=json.loads((self.args.output_root/'EXECUTION.json').read_bytes())
        self.assertEqual(value['status'],'FAILED_WALL_BUDGET_NO_RETRY')
        self.assertEqual(value['wall_through_cleanup_seconds'],121)
    def test_resource_receipt_blocked_turns_worker_success_into_failure(self):
        result,_=self.execute_mock(resource_status='BLOCKED')
        self.assertEqual(result,1)
        self.assertEqual(json.loads((self.args.output_root/'EXECUTION.json').read_bytes())['status'],'FAILED_RESOURCE_EVIDENCE_NO_RETRY')
    def test_wrong_cleanup_label_cannot_stop_or_delete_another_container(self):
        tool=FakeDocker('unused',self.root);tool.token='expected'
        value=tool.inspection();value['Config']['Labels'][host.LABEL]='other'
        with self.assertRaises(ValueError):host.verify_container_security(value,tool.image['image_id'],'expected')
        self.assertFalse(tool.deleted)
    def test_container_security_rejects_writable_mount_swapping_root_network_and_cpu(self):
        tool=FakeDocker('unused',self.root);tool.token='expected';original=tool.inspection()
        self.assertTrue(host.verify_container_security(original,tool.image['image_id'],'expected'))
        for field,value in (('ReadonlyRootfs',False),('NetworkMode','bridge'),('MemorySwap',2147483648),('NanoCpus',2000000000)):
            with self.subTest(field=field):
                changed=copy.deepcopy(original);changed['HostConfig'][field]=value
                with self.assertRaises(ValueError):host.verify_container_security(changed,tool.image['image_id'],'expected')
        changed=copy.deepcopy(original);changed['Mounts'][0]['RW']=True
        with self.assertRaises(ValueError):host.verify_container_security(changed,tool.image['image_id'],'expected')
    def test_fixed_registry_prevents_second_batch_or_output_attempt_without_real_tools(self):
        value,_=future_fixture();base=self.root/'registry'
        with mock.patch.object(host,'REGISTRY_BASE',base):
            first=host.claim_family_attempt(value)
            changed=copy.deepcopy(value);changed['batch_id']='another-batch-same-family'
            with self.assertRaises(FileExistsError):host.claim_family_attempt(changed)
            with self.assertRaises(ValueError):host.claim_family_attempt(value,registry_base=self.root/'different')
        self.assertTrue(first.exists())
        self.assertEqual(len(list(base.glob('*.json'))),1)
    def test_false_contract_never_creates_attempt_registry(self):
        base=self.root/'registry'
        with mock.patch.object(host,'REGISTRY_BASE',base):
            with self.assertRaises(ValueError):host.claim_family_attempt(self.contract)
        self.assertFalse(base.exists())
    def test_export_uses_local_no_hardlink_clone_before_strict_preparation(self):
        responses=[subprocess.CompletedProcess([],0,b'',b''),subprocess.CompletedProcess([],0,b'ab'*20+b'\n',b''),
                   subprocess.CompletedProcess([],0,b'',b''),subprocess.CompletedProcess([],0,b'ab'*20+b'\n',b'')]
        with mock.patch.object(host.subprocess,'run',side_effect=responses) as run, \
             mock.patch.object(host,'prepare_runtime_source',return_value={'runtime_commit':'ab'*20}) as prepared:
            result=host.export_source(self.root)
        self.assertEqual(result['runtime_commit'],'ab'*20)
        self.assertIn('--no-hardlinks',run.call_args_list[2].args[0])
        self.assertEqual(prepared.call_args.kwargs['expected_commit'],'ab'*20)
        self.assertEqual(prepared.call_args.args[0],self.root/'source-git-clone')
    def test_endpoint_true_requires_two_original_gates_energy_rechecks_and_bound_tail_snapshots(self):
        values=final_fixture()
        self.assertTrue(host.verify_native_final(*values[:6],result_record=values[6]))
        mutations=(lambda r:r.update(mapped_endpoint_gate=None),
            lambda r:r['endpoint_gate'].update(mapped_density_energy_change_hartree=1e-8),
            lambda r:r['endpoint_gate'].update(returned_density_energy_recheck_hartree=False),
            lambda r:r['returned_density'].update(matched_operator_id='fa'*32),
            lambda r:r['snapshot_registry']['evaluation-3'].update(phase='OPTIMIZER_BASE'))
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                packet=copy.deepcopy(values);mutate(packet[6])
                with self.assertRaises(ValueError):host.verify_native_final(*packet[:6],result_record=packet[6])
        with self.assertRaises(ValueError):host.verify_native_final(*values[:6])
    def test_tail_completed_label_or_one_tail_cannot_certify_endpoint_true(self):
        values=list(copy.deepcopy(final_fixture()))
        # A same-density successful callback still cannot substitute for the
        # missing mapped-tail phase merely by changing a group status label.
        values[2]['slots'][2]['phase']='OPTIMIZER_BASE';values[1]['slots'][2]['phase']='OPTIMIZER_BASE'
        values[6]['snapshot_registry']['evaluation-3']['phase']='OPTIMIZER_BASE'
        with self.assertRaises(ValueError):host.verify_native_final(*values[:6],result_record=values[6])
    def test_unqualified_summary_requires_matching_source_result_and_stop_reason(self):
        values=list(copy.deepcopy(final_fixture()))
        values[0].update(endpoint_qualified=False,stop_reason='UNQUALIFIED_ORIGINAL_GATE')
        values[6].update(engine_qualified=False,stop_reason='UNQUALIFIED_ORIGINAL_GATE',mapped_endpoint_gate=None)
        self.assertTrue(host.verify_native_final(*values[:6],result_record=values[6]))
        values[6]['stop_reason']='a different stop'
        with self.assertRaises(ValueError):host.verify_native_final(*values[:6],result_record=values[6])


if __name__=='__main__':unittest.main()
