"""Prepare the single-start root candidate with zero F; no execution option.

This supervisor cannot launch a real root search or reserve scientific callback
slots. It copies committed source into an offline, non-root, read-only container
and verifies the retained input/cache and implementation-only contract.
"""
import argparse
import copy
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from runtime.user_molecule.acceptance_resources import Budget, identity_digest, qualify_exact_fixture
from runtime.user_molecule.residual_budget import reserve_single_process
from runtime.user_molecule.occupied_space_root_contract import (
    minimal_template, validate_execution_contract, validate_input_binding, execution_identity)
from runtime.user_molecule.input import strict_json


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as f:f.write(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()


def host_memory():
    spec=importlib.util.spec_from_file_location('retained_root_host_memory',ROOT/'scripts/diagnose-user-molecule-seed-v2.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    return helper.host_memory()


def build_contract(source,commit,inputs):
    origin=copy.deepcopy(json.loads((source/'validation/user-molecule/residual-diagnostic/contract-v1.json').read_bytes())['ordinary_origin'])
    cache=Path(origin['source_directory']).resolve();record=json.loads((cache/origin['record_file']).read_bytes())
    for name in ('mo_coefficients','mo_occupations'):origin['array_identities'][name]=copy.deepcopy(record['array_identities'][name])
    for kind in ('record','arrays'):
        p=cache/origin[kind+'_file']
        if p.stat().st_size!=origin[kind]['size_bytes'] or sha(p)!=origin[kind]['sha256']:
            raise ValueError('Frozen complete ordinary cache differs: '+kind)
    contract=minimal_template(origin)
    profile=source/'profiles/user-molecule/pilot-b3lypg-sto3g-grid2-v1.json'
    canonical=json.dumps(json.loads(profile.read_bytes()),sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
    contract.update(batch_id='occupied-root-preparation-'+uuid.uuid4().hex,created_utc=utc(),
        runtime_test_commit=commit,profile_sha256=sha(profile),profile_executed_raw_sha256=sha(profile),
        profile_canonical_sha256=hashlib.sha256(canonical).hexdigest(),
        source_manifest_sha256=sha(source/'locks/source-user-molecule-files.sha256.json'),
        prior_proposal_sha256=sha(source/'validation/user-molecule/occupied-space/root-search-proposal-v1.json'))
    for name in contract['source_file_sha256']:contract['source_file_sha256'][name]=sha(source/name)
    validate_execution_contract(contract)
    validate_input_binding(contract,(inputs/'SOURCE.json').read_bytes(),
        (inputs/'prepared-seed-family.json').read_bytes(),(inputs/'prepared-seed-family.npz').read_bytes(),
        source_arrays_bytes=(inputs/'source-arrays.npz').read_bytes(),
        history_record_bytes=(inputs/'parent-response-result.json').read_bytes(),mdr_bytes=(inputs/'MDR-007.json').read_bytes())
    if contract['scientific_execution_authorized'] is not False or contract['scientific_budget_reserved'] is not False:
        raise ValueError('This supervisor permits only the inactive preparation contract')
    return contract,cache


def argument_parser():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root',type=Path,required=True)
    parser.add_argument('--seed-input-dir',type=Path,required=True)
    parser.add_argument('--prepare-only',action='store_true',required=True)
    parser.add_argument('--docker',default=r'C:\Program Files\Docker\Docker\resources\bin\docker.exe')
    return parser


def verify_root_readiness(receipt, contract, contract_sha):
    """A process exit or status label alone cannot certify zero-F preparation."""
    validate_execution_contract(contract)
    if not isinstance(receipt, dict):raise ValueError('Complete preparation receipt required')
    binding, initial, history = contract['seed_binding'], contract['initial_density'], contract['parent_evidence']
    expected = {
        'status':'PASS_ACTUAL_CACHED_OCCUPIED_SPACE_ROOT_PREPARATION_ONLY',
        'runtime_test_commit':contract['runtime_test_commit'], 'contract_sha256':contract_sha,
        'source_file_sha256':contract['source_file_sha256'],
        'seed_input_source_sha256':binding['source_record']['sha256'],
        'seed_input_record_sha256':binding['seed_record']['sha256'],
        'seed_input_archive_sha256':binding['seed_arrays']['sha256'],
        'history_record_sha256':history['history_record']['sha256'],
        'mdr_record_sha256':history['mdr_record']['sha256'],
        'ordered_seed_density_ids':binding['seed_density_ids'],
        'selected_seed_index':initial['seed_index'], 'selected_angle_rad':initial['angle_rad'],
        'selected_density_id':initial['density_id'], 'selected_array_identity':initial['array_identity'],
        'source_bindings':{'source_record_sha256':binding['source_record']['sha256'],
            'source_arrays_sha256':binding['source_arrays']['sha256'],
            'seed_record_sha256':binding['seed_record']['sha256'], 'seed_arrays_sha256':binding['seed_arrays']['sha256'],
            'history_record_sha256':history['history_record']['sha256'], 'mdr_record_sha256':history['mdr_record']['sha256']},
        'root_solve':'NOT_EXECUTED', 'CURRENT_F':'NOT_EXECUTED',
        'actual_live_root_runner':'NOT_IMPLEMENTED_IN_THIS_PREPARE_ONLY_VERSION', 'scientific_execution':'NOT_EXECUTED'}
    for key, value in expected.items():
        # JSON representation also distinguishes False/0 and 2/2.0.
        if json.dumps(receipt[key],sort_keys=True,allow_nan=False)!=json.dumps(value,sort_keys=True,allow_nan=False):
            raise ValueError('Preparation receipt differs: '+key)
    for key in ('real_F_NR_SCF_grid_integral_calls','nuclear_repulsion_calls','prepared_callback_ledger_entries','new_true_F_NR_calls'):
        if type(receipt[key])is not int or receipt[key]!=0:raise ValueError('Observed integer zero required: '+key)
    for key in ('scientific_callback_reservation_created','scientific_execution_authorized','solver_evaluated','Compute','method_approval'):
        if receipt[key]is not False:raise ValueError('Inactive preparation flag required: '+key)
    for key in ('all_four_recipe_verified','source_metric_matches_reference'):
        if receipt[key]is not True:raise ValueError('Actual input verification required: '+key)
    for key in ('native_budget','scientific_budget'):
        if receipt[key]is not None:raise ValueError('No scientific allowance permitted: '+key)
    for key in ('forbidden_attempts','changed_guard_bindings'):
        if type(receipt[key])is not list or receipt[key]:raise ValueError('Held preparation guards required: '+key)
    guards=receipt['guarded_operations']
    required={'SCF.kernel','Grids.build','Mole.intor','Mole.intor_by_shell','Mole.energy_nuc',
        'NumInt.nr_rks','numint.nr_rks','SciPy TRF','SciPy private Jacobian',
        'prepared reference.evaluate','new root candidate solve'}
    if (type(guards)is not list or any(type(label)is not str for label in guards)
            or len(guards)!=34 or len(set(guards))!=34 or not required<=set(guards)):
        raise ValueError('All 34 distinct preparation guards required')
    return True


def main():
    args=argument_parser().parse_args();output=args.output_root.resolve();inputs=args.seed_input_dir.resolve()
    if output.exists() or output.is_relative_to(ROOT) or output.is_relative_to(inputs):
        raise ValueError('Fresh external evidence directory required')
    def git(*values):return subprocess.check_output(['git',*values],cwd=ROOT)
    if git('status','--porcelain').strip():raise ValueError('Clean committed source required')
    commit=git('rev-parse','HEAD').decode().strip();output.mkdir(parents=True);commands=[]
    def docker(*values,timeout=15):
        result=subprocess.run([args.docker,*values],capture_output=True,timeout=timeout)
        commands.append({'arguments':[args.docker,*values],'exit_code':result.returncode,'utc':utc(),
            'stderr':result.stderr.decode('utf-8',errors='replace')})
        if result.returncode:raise RuntimeError(commands[-1]['stderr'])
        return result.stdout
    image=json.loads((ROOT/'validation/user-molecule/candidate-image.json').read_bytes())
    actual_image=json.loads(docker('image','inspect',image['image_id']))[0]
    labels=actual_image['Config']['Labels']
    if (actual_image['Id']!=image['image_id'] or labels['org.opencontainers.image.revision']!=image['runtime_build_commit']
            or labels['ai4orgchem.source.commit']!=image['science_commit']):raise ValueError('Existing image lineage differs')
    save(output/'image-inspect.json',actual_image)
    save(output/'engine-version.json',json.loads(docker('version','--format','{{json .Server}}')))
    info=json.loads(docker('info','--format','{{json .}}'))
    save(output/'engine-resources.json',{key:info.get(key) for key in ('MemTotal','NCPU','ContainersRunning','CgroupVersion','KernelVersion')})
    host=host_memory();save(output/'host-admission.json',host)
    if host['status']!='ADMITTED_HOST_ONLY' or info['MemTotal']<2147483648 or info['ContainersRunning']:
        save(output/'admission.json',{'status':'NOT_EXECUTED_RESOURCE_ADMISSION','new_true_F':0,'scientific_budget':None})
        save(output/'commands.json',commands);return 20
    archive=output/'runtime-source.tar'
    subprocess.run(['git','archive','--format=tar','-o',str(archive),commit],cwd=ROOT,check=True)
    source=output/'runtime-source';source.mkdir()
    with tarfile.open(archive) as stream:stream.extractall(source,filter='data')
    verified=[]
    for name in git('ls-tree','-r','--name-only',commit).decode().splitlines():
        blob=git('show',commit+':'+name);actual=(source/name).read_bytes();mode='EXACT_GIT_BLOB'
        if actual!=blob:
            if not name.endswith('.ps1') or actual!=blob.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'):
                raise ValueError('Export differs from committed blob: '+name)
            mode='EXACT_LF_TO_CRLF_PS1_EXPORT'
        verified.append({'path':name,'git_blob_sha256':hashlib.sha256(blob).hexdigest(),'export_sha256':sha(source/name),'verification':mode})
    save(output/'source-export-verification.json',{'commit':commit,'files':verified})
    contract,cache=build_contract(source,commit,inputs);cp=output/'candidate-contract.json';save(cp,contract)
    identity=execution_identity(contract,sha(cp));save(output/'source-identity.json',dict(identity,source_archive_sha256=sha(archive)))
    # Only an engineering wall reservation exists. Proposed201/300 root limits remain inert metadata.
    budget=Budget(output/'ENGINEERING_WALL_BUDGET.json',contract['batch_id'],total_seconds=120,max_process_seconds=120,memory_limit_mib=1024,threads=1)
    save(output/'WALL_RESERVATION.json',reserve_single_process(budget,run_id='zero-F-preparation',identity=identity))
    leaf=output/'output';leaf.mkdir();token=uuid.uuid4().hex;cid=None;completed=None;settled=None
    started=time.monotonic()
    execution={'status':'RUNNING','mode':'ZERO_F_ROOT_CANDIDATE_PREPARATION','identity':identity,
        'runtime_test_commit':commit,'scientific_budget_reserved':False,'new_true_F_NR_calls':None,
        'container_removed':False,'automatic_retry':False,'wall_limit_seconds':120}
    try:
        command=['create','--read-only','--network','none','--memory','1024m','--memory-swap','1024m','--cpus','1',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--user','10001:10001',
            '--label','ai4orgchem.root-preparation='+token,'--tmpfs','/tmp:rw,nosuid,nodev,size=67108864,mode=1777',
            '--mount',f'type=bind,source={source},target=/workspace,readonly',
            '--mount',f'type=bind,source={leaf},target=/output',
            '--mount',f'type=bind,source={cache},target=/saved-ordinary,readonly',
            '--mount',f'type=bind,source={inputs},target=/seed-input,readonly',
            '--mount',f'type=bind,source={cp},target=/candidate-contract.json,readonly',
            '--workdir','/workspace','-e','PYTHONDONTWRITEBYTECODE=1','-e','OMP_NUM_THREADS=1',
            '-e','OPENBLAS_NUM_THREADS=1','-e','MKL_NUM_THREADS=1','-e','AI4ORGCHEM_SOURCE_ROOT=/opt/ai4orgchem',
            '-e','AI4ORGCHEM_RUNTIME_TEST_COMMIT='+commit,'-e','AI4ORGCHEM_IMAGE_ID='+image['image_id'],
            '-e','AI4ORGCHEM_IMAGE_BUILD_COMMIT='+image['runtime_build_commit'],'--entrypoint','python',image['image_id'],
            '-B','/workspace/scripts/diagnose-user-molecule-occupied-space-root-worker.py','--prepare-only']
        save(output/'launch-command.json',[args.docker,*command]);cid=docker(*command).decode().strip()
        if re.fullmatch('[0-9a-f]{64}',cid) is None:raise ValueError('Invalid owned container ID')
        execution['container_id']=cid;docker('start',cid)
        while True:
            inspected=json.loads(docker('inspect',cid))[0]
            if inspected['Config']['Labels'].get('ai4orgchem.root-preparation')!=token:raise ValueError('Container ownership differs')
            if not inspected['State']['Running']:break
            if time.monotonic()-started>95:
                docker('stop','--time','2',cid);execution['termination_reason']='WALL_STOP_NO_RETRY';break
            time.sleep(.25)
        completed=json.loads(docker('inspect',cid))[0];flags=completed['HostConfig']
        readonly={m['Destination'] for m in completed['Mounts'] if m['RW'] is False}
        safe=(completed['Image']==image['image_id'] and completed['Config']['User']=='10001:10001'
            and flags['ReadonlyRootfs'] and flags['NetworkMode']=='none' and flags['Memory']==flags['MemorySwap']==1073741824
            and flags['NanoCpus']==1000000000 and {'/workspace','/saved-ordinary','/seed-input','/candidate-contract.json'}<=readonly)
        expected=leaf/'root-readiness.json'
        execution.update(container_exit_code=completed['State']['ExitCode'],oom_killed=completed['State']['OOMKilled'],platform_flags_verified=safe)
        good=safe and expected.exists() and completed['State']['ExitCode']==0 and not completed['State']['OOMKilled']
        execution['status']='EXECUTED_ZERO_F_PREPARATION_ONLY' if good else 'FAILED_OR_REFUSED_NO_RETRY'
        if good:
            receipt=strict_json(expected.read_bytes())
            execution['worker_receipt_verified']=verify_root_readiness(receipt,contract,sha(cp))
            execution['worker_receipt_sha256']=sha(expected)
            execution['new_true_F_NR_calls']=0
    except BaseException as error:
        execution.update(status='FAILED_NO_RETRY',error_type=type(error).__name__,error=str(error))
    finally:
        try:
            if cid:
                inspected=json.loads(docker('inspect',cid))[0]
                if inspected['Config']['Labels'].get('ai4orgchem.root-preparation')!=token:raise ValueError('Cleanup ownership differs')
                if inspected['State']['Running']:docker('stop','--time','2',cid)
                completed=json.loads(docker('inspect',cid))[0];save(output/'container-inspect.json',completed)
                logs=subprocess.run([args.docker,'logs',cid],capture_output=True,timeout=10)
                (output/'stdout.log').write_bytes(logs.stdout);(output/'stderr.log').write_bytes(logs.stderr)
                execution['logs_exit_code']=logs.returncode;execution['container_removed']=docker('rm',cid).decode().strip()==cid
        finally:
            execution['wall_through_cleanup_seconds']=time.monotonic()-started
            if cid is None or execution['container_removed']:
                settled=budget.settle('zero-F-preparation',execution['wall_through_cleanup_seconds'],execution['status'],
                    {'container_removed':execution['container_removed']})
            else:settled=budget.snapshot();execution['status']='CLEANUP_UNRESOLVED_NO_RETRY'
            if settled['over_budget']:execution['status']='FAILED_WALL_BUDGET_NO_RETRY'
            save(output/'WALL_SETTLEMENT.json',settled);save(output/'EXECUTION.json',execution);save(output/'commands.json',commands)
    if completed is not None:
        rows=[json.loads(line)['cgroup'] for line in (leaf/'resources.jsonl').read_text().splitlines()] if (leaf/'resources.jsonl').exists() else []
        external={'source':'DOCKER_INSPECT','container_id':cid,'oom_killed':completed['State']['OOMKilled'],
            'evidence_sha256':sha(output/'container-inspect.json'),'state_finished_at':completed['State']['FinishedAt'],
            'resource_identity_sha256':identity_digest(identity)}
        qualification=qualify_exact_fixture(identity,14,rows,memory_limit_mib=1024,threads=1,external_oom_evidence=external)
        qualification['qualification_scope']='ZERO_F_PREPARATION_ONLY_NOT_REAL_ROOT_RESOURCE_APPROVAL'
        save(output/'resource-qualification.json',qualification)
        save(output/'output-retention.json',{'container_removed':execution['container_removed'],'retained_files':sum(p.is_file() for p in leaf.rglob('*'))})
    print(json.dumps(execution,ensure_ascii=False),flush=True)
    return 0 if execution['status']=='EXECUTED_ZERO_F_PREPARATION_ONLY' and execution['container_removed'] else 1


if __name__=='__main__':raise SystemExit(main())
