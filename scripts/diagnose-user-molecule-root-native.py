"""Default zero-F preparation supervisor; future native execution needs a grant.

No grant is generated here. Scientific declarations remain unreserved; an
actual wall reservation and a fixed family-attempt record are separate evidence.
"""
from __future__ import annotations
import argparse
import copy
import datetime
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from runtime.distribution import prepare_runtime_source
from runtime.user_molecule.acceptance_resources import Budget, qualify_exact_fixture, identity_digest
from runtime.user_molecule.residual_budget import reserve_single_process
from runtime.user_molecule.input import strict_json
from runtime.user_molecule import occupied_space_root_native_contract as protocol

OLD_STAGE = Path('D:/AI4Science/ai4orgchem-runtime-deliveries/20261007-user-molecule-occupied-space-root')
REGISTRY_BASE = Path('D:/AI4Science/ai4orgchem-runtime-deliveries/ROOT_NATIVE_ATTEMPT_REGISTRY')
LABEL = 'ai4orgchem.root-native-attempt'
GUARDS = frozenset(('SCF.kernel','SCF.scf','hf.kernel','RHF.kernel','UHF.kernel','ROHF.kernel',
    'RKS.kernel','UKS.kernel','ROKS.kernel','Grids.build','Mole.intor','Mole.intor_by_shell','Mole.energy_nuc',
    'unbound NumInt.nr_rks','module numint.nr_rks','old production solve','old production iterate',
    'old production SCF driver','old reference solve','old budgeted solve','old fake-only root',
    'source SCF driver','source direct F shortcut','public SciPy shortcut','public Jacobian shortcut'))
PREPARE_GUARDS = GUARDS | frozenset(('new native root solve','new native TRF alias','new native Jacobian alias','prepared reference evaluate'))


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
        stream.flush(); os.fsync(stream.fileno())
def same(actual, expected, label):
    if json.dumps(actual, sort_keys=True, allow_nan=False) != json.dumps(expected, sort_keys=True, allow_nan=False):
        raise ValueError('Verified value differs: '+label)


def host_memory():
    spec = importlib.util.spec_from_file_location('native_host_memory', ROOT/'scripts/diagnose-user-molecule-seed-v2.py')
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    return helper.host_memory()


def export_source(output):
    """Local fresh clone avoids legacy worktree CRLF without changing ROOT."""
    env=dict(os.environ,GIT_OPTIONAL_LOCKS='0')
    def git(*args):
        result=subprocess.run(['git','-c','core.fsmonitor=false',*args],capture_output=True,timeout=60,env=env)
        if result.returncode: raise ValueError('Local source Git operation refused: '+result.stderr.decode('utf-8','replace'))
        return result.stdout
    if git('-C',str(ROOT),'status','--porcelain=v1','--untracked-files=all').strip():
        raise ValueError('Clean committed source required')
    expected=git('-C',str(ROOT),'rev-parse','HEAD').decode().strip()
    clone=Path(output)/'source-git-clone'
    git('-c','core.autocrlf=false','clone','--no-hardlinks','--',str(ROOT),str(clone))
    if git('-C',str(ROOT),'rev-parse','HEAD').decode().strip()!=expected:
        raise ValueError('Original source HEAD changed during local clone')
    return prepare_runtime_source(clone,Path(output)/'runtime-source',expected_commit=expected)


def build_contract(source, commit, inputs, parent_path, *, grant=None, execute=False):
    if type(execute) is not bool or execute != (grant is not None):
        raise ValueError('Separate execute request and explicit grant must be paired')
    parent_raw = Path(parent_path).read_bytes()
    if hashlib.sha256(parent_raw).hexdigest() != protocol.PARENT_RAW_SHA256:
        raise ValueError('Exact retained false parent bytes required')
    parent = strict_json(parent_raw)
    value = protocol.minimal_template(parent)
    value.update(runtime_test_commit=commit, batch_id='root-native-'+uuid.uuid4().hex,
        source_file_sha256={name: sha(Path(source)/name) for name in protocol.REQUIRED_SOURCE_FILES})
    value['contract_family_sha256'] = protocol.contract_family_sha256(value)
    if execute:
        value.update(scientific_execution_authorized=True, local_cli_execute_requested=True,
            authorization_scope=protocol.EXECUTION_SCOPE, execution_grant=copy.deepcopy(grant))
    opts = {'explicit_grant': grant, 'local_cli_execute_requested': execute}
    protocol.validate_execution_contract(value, **opts)
    names = ('SOURCE.json','prepared-seed-family.json','prepared-seed-family.npz','source-arrays.npz','parent-response-result.json','MDR-007.json')
    raw = {name: (Path(inputs)/name).read_bytes() for name in names}
    protocol.validate_input_binding(value, raw['SOURCE.json'], raw['prepared-seed-family.json'], raw['prepared-seed-family.npz'],
        parent_preparation_contract_bytes=parent_raw, source_arrays_bytes=raw['source-arrays.npz'],
        history_record_bytes=raw['parent-response-result.json'], mdr_bytes=raw['MDR-007.json'], **opts)
    origin = parent['ordinary_origin']; cache = Path(origin['source_directory']).resolve()
    for kind in ('record','arrays'):
        file = cache/origin[kind+'_file']
        if file.stat().st_size != origin[kind]['size_bytes'] or sha(file) != origin[kind]['sha256']:
            raise ValueError('Complete frozen ordinary cache differs: '+kind)
    return value, cache, parent_raw


def verify_guards(receipt, *, prepare):
    key = 'changed_guards' if prepare else 'changed_bindings'
    same(receipt[key], [], key); same(receipt['forbidden_attempts'], [], 'forbidden attempts')
    guards = receipt['guarded_operations']
    wanted = PREPARE_GUARDS if prepare else GUARDS
    if type(guards) is not list or any(type(name) is not str for name in guards) or len(guards) != len(set(guards)) or set(guards) != wanted:
        raise ValueError('Exact worker guard bindings required')


def verify_native_readiness(receipt, contract, contract_sha):
    protocol.validate_execution_contract(contract)
    if not isinstance(receipt, dict): raise ValueError('Readiness object required')
    expected = {'status':'PASS_GATED_SOURCE_NATIVE_INPUT_PREPARATION_ONLY', 'contract_sha256':contract_sha,
        'runtime_test_commit':contract['runtime_test_commit'], 'parent_contract_sha256':protocol.PARENT_RAW_SHA256,
        'contract_family_sha256':contract['contract_family_sha256'], 'selected_density_id':contract['initial_density']['density_id'],
        'selected_seed_index':2, 'selected_angle_rad':-.1, 'four_seed_recipe_verified':True,
        'source_file_sha256':contract['source_file_sha256'], 'actual_native_NR_calls':0,
        'new_scientific_budget':None, 'root_solve':'NOT_EXECUTED', 'Compute':False}
    for key, value in expected.items(): same(receipt[key], value, key)
    if type(receipt['actual_native_NR_calls']) is not int: raise ValueError('Observed integer zero required')
    verify_guards(receipt, prepare=True)
    return True


def verify_native_final(summary, accounting, callbacks, guards, contract, contract_sha, *, result_record=None):
    """A successful diagnostic can remain an unqualified endpoint."""
    if contract['scientific_execution_authorized'] is not True: raise ValueError('False contract cannot certify native execution')
    same(summary['status'], 'EXECUTED_SINGLE_PATH_ROOT_DIAGNOSTIC_ONLY', 'native summary')
    for key, value in (('Compute',False),('method_approval',False),('automatic_retry',False),
                       ('research_delta_hartree',None),('independent_production_equivalence','NOT_EXECUTED')):
        same(summary[key], value, key)
    if type(summary['endpoint_qualified']) is not bool or type(summary['stop_reason']) is not str:
        raise ValueError('Explicit endpoint/stop semantics required')
    if not isinstance(result_record, dict): raise ValueError('Actual source-derived result record required, including unqualified results')
    same(result_record['execution_kind'],'SOURCE_NATIVE_DIAGNOSTIC','result source kind')
    same(result_record['status'],'SOURCE_BOUND_ROOT_DIAGNOSTIC_CANDIDATE','result source role')
    same(result_record['scientific_execution_authorized'],True,'result authorization')
    same(result_record['engine_qualified'],summary['endpoint_qualified'],'result endpoint predicate')
    same(result_record['stop_reason'],summary['stop_reason'],'result stop reason')
    same(result_record['evaluator_execution_snapshot']['binding_validated'],True,'source binding validation')
    same(result_record['evaluator_execution_snapshot']['execution_kind'],'SOURCE_NATIVE_DIAGNOSTIC','evaluator source kind')
    same(accounting['execution_kind'], 'SOURCE_NATIVE_DIAGNOSTIC', 'native accounting mode')
    same(accounting['scientific_execution_authorized'], True, 'accounting authorization')
    same(accounting['closed'], True, 'accounting closure'); same(accounting['persistence_intact'], True, 'persistent receipts')
    if accounting['status'] not in ('CLOSED','CLOSED_FAILED_NO_RETRY'): raise ValueError('Complete terminal accounting required')
    slots = callbacks['slots']; limits = {protocol.PATH_ID:201}
    same(callbacks['path_limits'], limits, 'callback limits'); same(callbacks['total_limit'], 201, 'total callbacks')
    expected_identity = protocol.execution_identity(contract, contract_sha, explicit_grant=contract['execution_grant'], local_cli_execute_requested=True)
    same(callbacks['identity'], expected_identity, 'durable callback identity')
    if callbacks['paths'][protocol.PATH_ID]['state'] != 'CLOSED' or not 1 <= len(slots) <= 201:
        raise ValueError('One closed charged path required')
    counts = accounting['callback_slots']; same(counts['charged'], len(slots), 'charged slots')
    for index, row in enumerate(slots, 1):
        if type(row['slot_id']) is not int or row['slot_id'] != index or row['path_id'] != protocol.PATH_ID or row['status'] not in ('SUCCEEDED','FAILED'):
            raise ValueError('Closed ordered callback records required')
    same(counts['pending'], 0, 'pending slots')
    same(counts['succeeded'], sum(row['status']=='SUCCEEDED' for row in slots), 'successful slots')
    same(counts['failed'], sum(row['status']=='FAILED' for row in slots), 'failed slots')
    nr = accounting['nr_dispatch_counts']; source = accounting['source_native_dispatch_counts']
    for name in ('entered','completed','failed'):
        if type(nr[name]) is not int or not 0 <= nr[name] <= len(slots): raise ValueError('Observed native integer count required')
        same(source[name], nr[name], 'source dispatch '+name)
    if nr['completed'] + nr['failed'] != nr['entered'] or nr['completed'] < counts['succeeded']:
        raise ValueError('Native completion/failure counts do not close')
    same(summary['source_NR_counts'], source, 'summary NR counts'); same(summary['callback_slots'], counts, 'summary callback slots')
    own = accounting['slots']; same(len(own), len(slots), 'owned slot count')
    for saved, charged in zip(own, slots):
        for key in ('slot_id','path_id','density_id','phase','status','operator_id'):
            same(saved[key], charged[key], 'owned callback '+key)
        if saved['status']=='SUCCEEDED' and (saved['nr_entered'],saved['nr_completed'],saved['nr_failed']) != (1,1,0):
            raise ValueError('A successful operator needs one completed native dispatch')
    for name in ('entered','completed','failed'):
        same(nr[name], sum(row['nr_'+name] for row in own), 'per-slot native '+name)
    for group in accounting['admission_groups'].values():
        row = group['row']
        if row['status'] not in ('COMPLETED','REFUSED_PARTIAL_NO_RETRY','REFUSED_ZERO_CALLBACKS'):
            raise ValueError('No unresolved optimizer admission may certify a result')
        same(row['actual_callbacks'], len(group['slots']), 'actual group charge')
        if row['status']=='COMPLETED' and (row['actual_callbacks'] != 96 if row['kind']=='COMPLETE_JACOBIAN' else row['actual_callbacks'] not in (1,2)):
            raise ValueError('Explicit Jacobian/tail closure required')
    same(result_record['evaluation_count'],len(slots),'candidate callback count')
    for key in ('callback_slots','nr_dispatch_counts','identity_sha256'):
        same(result_record['native_accounting_snapshot'][key],accounting[key],'candidate accounting '+key)
    if summary['endpoint_qualified']:
        if type(result_record['engine_qualified']) is not bool: raise ValueError('Exact engine predicate required')
        gate, mapped = result_record['endpoint_gate'], result_record['mapped_endpoint_gate']
        if not isinstance(gate,dict) or not isinstance(mapped,dict) or gate.get('qualified') is not True or mapped.get('qualified') is not True:
            raise ValueError('Both original endpoint gates are required')
        for key in ('returned_density_energy_recheck_hartree','mapped_density_energy_change_hartree'):
            energy=gate.get(key)
            if type(energy) not in (int,float) or not math.isfinite(energy) or not 0<=energy<=1e-9:
                raise ValueError('Original energy recheck threshold required: '+key)
        returned=result_record['returned_density']; registry=result_record['snapshot_registry']
        tails={phase:[row for row in slots if row['phase']==phase and row['status']=='SUCCEEDED'] for phase in
               ('FINAL_RETURNED_DENSITY','FINAL_RAW_AUFBAU_DENSITY_RECHECK')}
        if any(len(rows)!=1 for rows in tails.values()): raise ValueError('Two actually successful original tail phases required')
        for phase, rows in tails.items():
            row=rows[0]; snapshot=registry.get('evaluation-'+str(row['slot_id']))
            if not isinstance(snapshot,dict): raise ValueError('Matched tail snapshot absent')
            for key in ('density_id','operator_id','phase'): same(snapshot[key],row[key],'tail snapshot '+key)
        if tails['FINAL_RETURNED_DENSITY'][0]['density_id']!=returned['density_id']:
            raise ValueError('Returned tail evaluated another density')
        selected=registry.get(returned['matched_snapshot_id'])
        if not isinstance(selected,dict) or selected['density_id']!=returned['density_id'] or selected['operator_id']!=returned['matched_operator_id']:
            raise ValueError('Returned density/operator snapshot identity differs')
    verify_guards(guards, prepare=False)
    for key in ('new_ordinary_SCF_grid_full_integrals','nuclear_repulsion_calls'):
        same(guards[key], 0, key)
        if type(guards[key]) is not int: raise ValueError('Actual integer zero required')
    return True


def claim_family_attempt(contract, *, registry_base=None):
    """One immutable claim per family, independent of batch/output directory."""
    if contract['scientific_execution_authorized'] is not True: raise ValueError('Preparation must not claim a native attempt')
    protocol.validate_execution_contract(contract,explicit_grant=contract['execution_grant'],local_cli_execute_requested=True)
    base = REGISTRY_BASE if registry_base is None else Path(registry_base)
    if base.resolve() != REGISTRY_BASE.resolve(): raise ValueError('Fixed global attempt registry required')
    base.mkdir(parents=True, exist_ok=True)
    path = base/(contract['contract_family_sha256']+'.first-attempt.json')
    save(path, {'schema':'root-native-family-first-attempt-v1', 'contract_family_sha256':contract['contract_family_sha256'],
        'runtime_test_commit':contract['runtime_test_commit'], 'batch_id':contract['batch_id'], 'claimed_at_utc':utc(),
        'state':'ATTEMPT_CLAIMED_BEFORE_RESERVATION_OR_CREATE_NO_RETRY', 'automatic_retry':False})
    return path


def verify_container_security(value, image_id, token, *, execute=False):
    config, host = value['Config'], value['HostConfig']
    required = {'/workspace','/saved-ordinary','/seed-input','/native-contract.json','/parent-contract.json'}
    if execute: required.add('/execution-grant.json')
    readonly = {mount['Destination'] for mount in value['Mounts'] if mount['RW'] is False}
    if (value['Image'] != image_id or config['Labels'].get(LABEL) != token or config['User'] != '10001:10001'
        or host['ReadonlyRootfs'] is not True or host['NetworkMode'] != 'none'
        or type(host['Memory']) is not int or host['Memory'] != 1073741824 or host['MemorySwap'] != host['Memory']
        or host['NanoCpus'] != 1000000000 or not required <= readonly
        or 'ALL' not in host['CapDrop'] or not any(str(option).startswith('no-new-privileges') for option in host['SecurityOpt'])):
        raise ValueError('Owned non-root offline read-only resource-constrained container required')
    if any(mount['RW'] is not False for mount in value['Mounts'] if mount['Destination'] in required):
        raise ValueError('Protected mount appears writable')
    return True


class DockerCommands:
    def __init__(self, executable, output):
        self.executable, self.output, self.commands = str(executable), Path(output), []
        self.hard_deadline_monotonic = None
    def __call__(self, *args, timeout=10):
        if self.hard_deadline_monotonic is not None:
            remaining = self.hard_deadline_monotonic-time.monotonic()
            if remaining <= 0: raise TimeoutError('Hard through-cleanup wall deadline exhausted')
            timeout=min(timeout,remaining)
        number = len(self.commands)+1; command = [self.executable,*map(str,args)]
        row = {'arguments':command,'utc':utc()}; self.commands.append(row)
        try:
            result = subprocess.run(command, capture_output=True, timeout=timeout)
            row['exit_code'] = result.returncode
            (self.output/f'command-{number:03d}.stdout').write_bytes(result.stdout)
            (self.output/f'command-{number:03d}.stderr').write_bytes(result.stderr)
            if result.returncode: raise RuntimeError(result.stderr.decode('utf-8','replace'))
            return result.stdout
        except BaseException as error:
            row.update(error_type=type(error).__name__,error=str(error)); raise


def argument_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root',type=Path,required=True)
    parser.add_argument('--seed-input-dir',type=Path,default=OLD_STAGE/'seed-input')
    parser.add_argument('--parent-contract',type=Path,default=OLD_STAGE/'preparation-a1/candidate-contract.json')
    parser.add_argument('--docker',default=r'C:\Program Files\Docker\Docker\resources\bin\docker.exe')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--prepare-only',action='store_true'); modes.add_argument('--execute',action='store_true')
    parser.add_argument('--grant-file',type=Path)
    return parser


def run_supervisor(args):
    if type(args.execute) is not bool: raise ValueError('Exact execute boolean required')
    execute = args.execute
    if execute != (args.grant_file is not None): raise ValueError('Execute needs a separate explicit grant; preparation cannot receive one')
    output, inputs, parent_path = args.output_root.resolve(), args.seed_input_dir.resolve(), args.parent_contract.resolve()
    if output.exists() or any(output.is_relative_to(path) for path in (ROOT,inputs,parent_path.parent,REGISTRY_BASE)):
        raise ValueError('Fresh external evidence directory required')
    grant = strict_json(args.grant_file.read_bytes()) if execute else None
    output.mkdir(parents=True); docker = DockerCommands(args.docker, output)
    execution = {'status':'NOT_EXECUTED','execute_requested':execute,'scientific_budget_reserved':False,
        'scientific_budget_declaration_is_not_reservation':True, 'automatic_retry':False,'container_removed':False,
        'Compute':False,'new_source_native_NR_calls':None}
    cid = completed = budget = identity = None; started = None; create_attempted = False
    token = uuid.uuid4().hex; duration, stop_at = (300,275) if execute else (120,95)
    try:
        source = output/'runtime-source'
        prepared = export_source(output); commit = prepared['runtime_commit']
        save(output/'source-export-verification.json',prepared)
        contract, cache, parent_raw = build_contract(source,commit,inputs,parent_path,grant=grant,execute=execute)
        cp = output/'native-contract.json'; pp = output/'parent-contract.json'
        save(cp,contract); pp.write_bytes(parent_raw)
        if execute: (output/'execution-grant.json').write_bytes(args.grant_file.read_bytes())
        identity = protocol.execution_identity(contract,sha(cp),explicit_grant=grant,local_cli_execute_requested=execute)
        save(output/'source-identity.json',identity)
        image = strict_json((ROOT/'validation/user-molecule/candidate-image.json').read_bytes())
        actual = json.loads(docker('image','inspect',image['image_id']))[0]
        labels = actual['Config']['Labels']; parent = contract['parent_preparation_contract']
        if actual['Id'] != parent['image_id'] or labels['org.opencontainers.image.revision'] != parent['image_build_runtime_commit'] or labels['ai4orgchem.source.commit'] != parent['science_commit']:
            raise ValueError('Retained r3 image identity differs')
        save(output/'image-inspect.json',actual)
        info = json.loads(docker('info','--format','{{json .}}')); save(output/'engine-resources.json',info)
        host = host_memory(); save(output/'host-admission.json',host)
        if (host['status'] != 'ADMITTED_HOST_ONLY' or type(info.get('NCPU')) is not int or info['NCPU'] < 1
                or type(info.get('MemTotal')) is not int or info['MemTotal'] < 2147483648 or info['ContainersRunning'] != 0):
            execution['status']='NOT_EXECUTED_RESOURCE_ADMISSION'; return 20
        if execute:
            claim = claim_family_attempt(contract); save(output/'family-attempt-claim.json',strict_json(claim.read_bytes()))
        budget = Budget(output/('NATIVE_WALL_BUDGET.json' if execute else 'ENGINEERING_WALL_BUDGET.json'),contract['batch_id'],
            total_seconds=duration,max_process_seconds=duration,memory_limit_mib=1024,threads=1)
        save(output/'WALL_RESERVATION.json',reserve_single_process(budget,run_id='one-process',identity=identity))
        leaf=output/'output'; leaf.mkdir()
        command=['create','--read-only','--network','none','--memory','1024m','--memory-swap','1024m','--cpus','1',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--user','10001:10001','--label',LABEL+'='+token,
            '--tmpfs','/tmp:rw,nosuid,nodev,size=67108864,mode=1777',
            '--mount',f'type=bind,source={source},target=/workspace,readonly',
            '--mount',f'type=bind,source={cache},target=/saved-ordinary,readonly',
            '--mount',f'type=bind,source={inputs},target=/seed-input,readonly',
            '--mount',f'type=bind,source={cp},target=/native-contract.json,readonly',
            '--mount',f'type=bind,source={pp},target=/parent-contract.json,readonly',
            '--mount',f'type=bind,source={leaf},target=/output','--workdir','/workspace',
            '-e','PYTHONDONTWRITEBYTECODE=1','-e','OMP_NUM_THREADS=1','-e','OPENBLAS_NUM_THREADS=1','-e','MKL_NUM_THREADS=1',
            '-e','AI4ORGCHEM_RUNTIME_TEST_COMMIT='+commit,'-e','AI4ORGCHEM_IMAGE_ID='+parent['image_id'],
            '-e','AI4ORGCHEM_IMAGE_BUILD_COMMIT='+parent['image_build_runtime_commit']]
        if execute: command+=['--mount',f'type=bind,source={output/"execution-grant.json"},target=/execution-grant.json,readonly']
        started=time.monotonic(); deadline=time.time()+stop_at
        docker.hard_deadline_monotonic=started+duration
        command+=['--entrypoint','python',parent['image_id'],'-B','/workspace/scripts/diagnose-user-molecule-root-native-worker.py',
            '--execute' if execute else '--prepare-only']
        if execute: command+=['--grant-file','/execution-grant.json','--stop-deadline-epoch',str(deadline)]
        save(output/'launch-command.json',[args.docker,*command]); create_attempted=True
        cid=docker(*command,timeout=15).decode().strip()
        if re.fullmatch('[0-9a-f]{64}',cid) is None: raise ValueError('Complete owned container ID required')
        execution.update(container_id=cid,status='RUNNING'); docker('start',cid)
        while True:
            inspected=json.loads(docker('inspect',cid))[0]
            verify_container_security(inspected,parent['image_id'],token,execute=execute)
            if inspected['State']['Running'] is not True: break
            if time.monotonic()-started >= stop_at:
                docker('stop','--time','2',cid,timeout=8); execution['wall_stop_requested']=True; break
            time.sleep(.25)
        completed=json.loads(docker('inspect',cid))[0]
        verify_container_security(completed,parent['image_id'],token,execute=execute)
        execution.update(container_exit_code=completed['State']['ExitCode'],oom_killed=completed['State']['OOMKilled'])
        if type(completed['State']['ExitCode']) is not int or completed['State']['ExitCode'] != 0 or completed['State']['OOMKilled'] is not False or completed['State']['Running'] is not False or execution.get('wall_stop_requested'):
            raise ValueError('Worker failed/stopped; no retry')
        if execute:
            verify_native_final(strict_json((leaf/'native-summary.json').read_bytes()),strict_json((leaf/'native-accounting-final.json').read_bytes()),
                strict_json((leaf/'callbacks.json').read_bytes()),strict_json((leaf/'guard-status.json').read_bytes()),contract,sha(cp),
                result_record=strict_json((leaf/'native-root-result.json').read_bytes()))
            execution['status']='EXECUTED_SOURCE_NATIVE_DIAGNOSTIC_ONLY'
            execution['new_source_native_NR_calls']=strict_json((leaf/'native-accounting-final.json').read_bytes())['nr_dispatch_counts']['entered']
        else:
            verify_native_readiness(strict_json((leaf/'native-readiness.json').read_bytes()),contract,sha(cp))
            execution.update(status='EXECUTED_ZERO_F_NATIVE_PREPARATION_ONLY',new_source_native_NR_calls=0)
        execution['worker_receipts_verified']=True
    except BaseException as error:
        execution.update(status='FAILED_NO_RETRY',error_type=type(error).__name__,error=str(error))
    finally:
        try:
            if cid:
                inspected=json.loads(docker('inspect',cid))[0]
                # Always validate ownership before stopping or deleting.
                if inspected['Config']['Labels'].get(LABEL) != token or inspected['Image'] != identity['image_id']:
                    raise ValueError('Cleanup ownership/image differs')
                if inspected['State']['Running']: docker('stop','--time','2',cid,timeout=8)
                completed=json.loads(docker('inspect',cid))[0]; save(output/'container-inspect.json',completed)
                remaining=started+duration-time.monotonic()
                if remaining<=0: raise TimeoutError('No cleanup time remains for log preservation')
                logs = subprocess.run([args.docker,'logs',cid],capture_output=True,timeout=min(8,remaining))
                (output/'stdout.log').write_bytes(logs.stdout); (output/'stderr.log').write_bytes(logs.stderr)
                if logs.returncode: raise ValueError('Container log preservation failed')
                execution['container_removed']=docker('rm',cid,timeout=8).decode().strip()==cid
                if not execution['container_removed']: raise ValueError('Deletion receipt differs')
            elif create_attempted:
                execution['status']='CLEANUP_UNKNOWN_NO_RETRY'
                execution['cleanup_error']='Create may have reached daemon; no owned CID returned'
        except BaseException as error:
            execution.update(status='CLEANUP_UNKNOWN_NO_RETRY',cleanup_error=type(error).__name__+': '+str(error))
        finally:
            if started is not None:
                elapsed=time.monotonic()-started; execution['wall_through_cleanup_seconds']=elapsed
                settled=(budget.settle('one-process',elapsed,execution['status'],{'container_removed':execution['container_removed']})
                    if execution['container_removed'] else budget.snapshot())
                save(output/'WALL_SETTLEMENT.json',settled)
                if elapsed>duration or settled['over_budget']: execution['status']='FAILED_WALL_BUDGET_NO_RETRY'
            if completed is not None and identity is not None and (output/'container-inspect.json').exists():
                try:
                    rows=[strict_json(line.encode())['cgroup'] for line in (output/'output/resources.jsonl').read_text().splitlines()]
                    observation={'source':'DOCKER_INSPECT','container_id':cid,'oom_killed':completed['State']['OOMKilled'],
                        'evidence_sha256':sha(output/'container-inspect.json'),'state_finished_at':completed['State']['FinishedAt'],
                        'resource_identity_sha256':identity_digest(identity)}
                    qualified=qualify_exact_fixture(identity,14,rows,memory_limit_mib=1024,threads=1,external_oom_evidence=observation)
                    qualified['qualification_scope']='SOURCE_NATIVE_DIAGNOSTIC_PROCESS' if execute else 'ZERO_F_PREPARATION_ONLY_NOT_ROOT_CAPACITY_APPROVAL'
                    save(output/'resource-qualification.json',qualified)
                    execution['resource_observation_status']=qualified['status']
                    if qualified['status'] != 'RESOURCE_CANDIDATE_EXACT_FIXTURE' and execution['status'].startswith('EXECUTED_'):
                        execution['status']='FAILED_RESOURCE_EVIDENCE_NO_RETRY'
                except BaseException as error:
                    execution['resource_observation_status']='UNKNOWN'
                    execution['resource_error']=type(error).__name__+': '+str(error)
                    if execution['status'].startswith('EXECUTED_'): execution['status']='FAILED_RESOURCE_EVIDENCE_NO_RETRY'
            save(output/'EXECUTION.json',execution); save(output/'commands.json',docker.commands)
    print(json.dumps(execution,ensure_ascii=False),flush=True)
    return 0 if execution['status'] in ('EXECUTED_ZERO_F_NATIVE_PREPARATION_ONLY','EXECUTED_SOURCE_NATIVE_DIAGNOSTIC_ONLY') and execution['container_removed'] else 1


def main(): return run_supervisor(argument_parser().parse_args())
if __name__=='__main__': raise SystemExit(main())
