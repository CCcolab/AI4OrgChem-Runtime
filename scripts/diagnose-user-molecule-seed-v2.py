"""Fresh admission and exactly one offline conditional diagnostic process.

This acceptance-only supervisor reuses the existing r3 image and full ordinary
cache. It cannot activate Compute, change profiles, rebuild, retry or publish.
"""
import argparse
import copy
import ctypes
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from runtime.user_molecule.acceptance_resources import Budget,identity_digest,qualify_exact_fixture
from runtime.user_molecule.residual_budget import reserve_single_process
from runtime.user_molecule.residual_seed_execution_contract import (
    canonical_sha,execution_identity,validate_execution_contract,validate_proposal_binding,validate_seed_readiness)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()


def host_memory():
    if os.name!='nt':raise ValueError('This host admission supervisor requires Windows; other platforms unqualified')
    class Status(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[
            (name,ctypes.c_ulonglong) for name in ('total_phys','avail_phys','total_page','avail_page','total_virtual','avail_virtual','avail_extended')]
    status=Status();status.length=ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError('GlobalMemoryStatusEx failed')
    return {'source':'Windows GlobalMemoryStatusEx','observed_at_utc':utc(),
        'total_physical_bytes':status.total_phys,'available_physical_bytes':status.avail_phys,
        'logical_cpu_count':os.cpu_count(),'minimum_available_bytes':2147483648,
        'status':'ADMITTED_HOST_ONLY' if status.avail_phys>=2147483648 else 'BLOCKED_HOST_MEMORY'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed-readiness-dir', type=Path, required=True)
    parser.add_argument('--output-root',type=Path,required=True)
    parser.add_argument('--docker',default=r'C:\Program Files\Docker\Docker\resources\bin\docker.exe')
    parser.add_argument('--admission-only',action='store_true',help='No scientific reservation or conditional callback')
    args=parser.parse_args()
    output=args.output_root.resolve()
    if output.exists() or output==ROOT or ROOT in output.parents:raise ValueError('Fresh external evidence root required')
    def git(*arguments):return subprocess.check_output(['git',*arguments],cwd=ROOT)
    if git('status','--porcelain').strip():raise ValueError('Clean committed runtime required')
    commit=git('rev-parse','HEAD').decode().strip()
    output.mkdir(parents=True)
    commands=[]
    def docker(*arguments,timeout=15):
        result=subprocess.run([args.docker,*arguments],capture_output=True,timeout=timeout)
        commands.append({'arguments':[args.docker,*arguments],'exit_code':result.returncode,
            'observed_at_utc':utc(),'stderr':result.stderr.decode('utf-8',errors='replace')})
        if result.returncode:raise RuntimeError(commands[-1]['stderr'])
        return result.stdout
    candidate=json.loads((ROOT/'validation/user-molecule/candidate-image.json').read_bytes())
    image=json.loads(docker('image','inspect',candidate['image_id']))[0]
    labels=image['Config']['Labels']
    if image['Id']!=candidate['image_id'] or labels['org.opencontainers.image.revision']!=candidate['runtime_build_commit'] or labels['ai4orgchem.source.commit']!=candidate['science_commit']:
        raise ValueError('Immutable existing image lineage differs')
    save(output/'image-inspect.json',image)
    save(output/'engine-version.json',json.loads(docker('version','--format','{{json .Server}}')))
    info=json.loads(docker('info','--format','{{json .}}'))
    save(output/'engine-resources.json',{key:info.get(key) for key in ('MemTotal','NCPU','CgroupVersion','CgroupDriver','OperatingSystem','KernelVersion','ContainersRunning')})
    initial_host=host_memory();save(output/'host-admission-initial.json',initial_host)
    if initial_host['status']!='ADMITTED_HOST_ONLY' or info['MemTotal']<2147483648 or info['ContainersRunning']:
        save(output/'admission.json',{'status':'NOT_EXECUTED_DUE_TO_RESOURCE_ADMISSION',
            'reason':'HOST_VM_TOTAL_OR_COMPETING_CONTAINER_ADMISSION_REFUSED','new_conditional_calls':0})
        save(output/'commands.json',commands);return 20
    archive=output/'runtime-source.tar'
    subprocess.run(['git','archive','--format=tar','-o',str(archive),commit],cwd=ROOT,check=True)
    source=output/'runtime-source';source.mkdir()
    with tarfile.open(archive) as stream:stream.extractall(source,filter='data')
    paths=git('ls-tree','-r','--name-only',commit).decode().splitlines();verified=[]
    for name in paths:
        blob=git('show',commit+':'+name);actual=(source/name).read_bytes()
        transform='EXACT_GIT_BLOB'
        if actual!=blob:
            if not name.endswith('.ps1') or actual!=blob.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'):
                raise ValueError('Git export bytes mismatch: '+name)
            transform='EXACT_LF_TO_CRLF_PS1_EXPORT'
        verified.append({'path':name,'git_blob_sha256':hashlib.sha256(blob).hexdigest(),
            'export_sha256':sha(source/name),'verification':transform})
    save(output/'source-export-verification.json',{'commit':commit,'file_count':len(verified),'files':verified})
    proposal_path=source/'validation/user-molecule/residual-diagnostic/contract-v1.json'
    proposal_raw=proposal_path.read_bytes();proposal=json.loads(proposal_raw)
    cache=Path(proposal['ordinary_origin']['source_directory']).resolve()
    cache_verified=[]
    for kind in ('record','arrays'):
        path=cache/proposal['ordinary_origin'][kind+'_file'];expected=proposal['ordinary_origin'][kind]
        if path.stat().st_size!=expected['size_bytes'] or sha(path)!=expected['sha256']:
            raise ValueError('Full ordinary cache differs: '+str(path))
        cache_verified.append({'path':str(path),**expected})
    save(output/'ordinary-cache-verification.json',cache_verified)
    readiness_dir=args.seed_readiness_dir.resolve()
    readiness_path=readiness_dir/'seed-readiness.json'
    readiness=json.loads(readiness_path.read_bytes())
    validate_seed_readiness(readiness)
    if (readiness['status']!='PASS_SEED_V2_CACHED_PREPARATION_ONLY' or
            readiness['new_functional_calls']!=0 or readiness['three_used_seeds_byte_identical'] is not True or
            readiness['reference_constructed_to_common_seed_relative_frobenius']>1e-10 or
            any(readiness['forbidden_operation_counts'].values())):
        raise ValueError('Guarded seed readiness did not pass')
    for name,expected in readiness['source_file_sha256'].items():
        if sha(source/name)!=expected:raise ValueError('Tested seed source differs: '+name)
    save(output/'seed-readiness-source-binding.json',{'receipt_sha256':sha(readiness_path),
        'tested_runtime_commit':readiness['runtime_test_commit'],'executed_runtime_commit':commit,
        'source_byte_match':True,'source_file_sha256':readiness['source_file_sha256']})
    probe_output=output/'admission-probe';probe_output.mkdir()
    probe_code="import json,os;from pathlib import Path;from runtime.user_molecule.acceptance_resources import collect_cgroup;v=int(next(x for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')).split()[1])*1024;print(json.dumps({'uid':os.getuid(),'vm_available_bytes':v,'cgroup':collect_cgroup(phase='ADMISSION_PROBE'),'new_scientific_calls':0},allow_nan=False))"
    token=uuid.uuid4().hex;cid=None;probe_started=time.monotonic()
    try:
        cid=docker('create','--read-only','--network','none','--memory','256m','--memory-swap','256m','--cpus','1',
            '--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges',
            '--label','ai4orgchem.residual-admission='+token,'--mount',f'type=bind,source={source},target=/workspace,readonly',
            '--workdir','/workspace','-e','PYTHONDONTWRITEBYTECODE=1','--entrypoint','python',candidate['image_id'],'-B','-c',probe_code).decode().strip()
        if not re.fullmatch('[0-9a-f]{64}',cid):raise ValueError('Invalid owned probe container ID')
        docker('start',cid)
        while True:
            actual=json.loads(docker('inspect',cid))[0]
            if actual['Config']['Labels'].get('ai4orgchem.residual-admission')!=token:raise ValueError('Probe ownership mismatch')
            if not actual['State']['Running']:break
            if time.monotonic()-probe_started>25:raise TimeoutError('Metadata-only probe exceeded25s')
            time.sleep(.25)
        save(probe_output/'container-inspect.json',actual)
        logs=subprocess.run([args.docker,'logs',cid],capture_output=True,timeout=10)
        (probe_output/'stdout.log').write_bytes(logs.stdout);(probe_output/'stderr.log').write_bytes(logs.stderr)
        if logs.returncode or actual['State']['ExitCode']!=0 or actual['State']['OOMKilled']:raise ValueError('Admission metadata probe failed')
        probe=json.loads(logs.stdout);save(probe_output/'observation.json',probe)
    finally:
        if cid:
            actual=json.loads(docker('inspect',cid))[0]
            if actual['Config']['Labels'].get('ai4orgchem.residual-admission')!=token:raise ValueError('Probe cleanup ownership mismatch')
            if actual['State']['Running']:docker('stop','--time','2',cid)
            removal=docker('rm',cid)
            save(probe_output/'removal.json',{'container_id':cid,'removed':removal.decode().strip()==cid,'scientific_calls':0})
    host=host_memory();save(output/'host-admission.json',host)
    if host['status']!='ADMITTED_HOST_ONLY' or probe['uid']!=10001 or probe['vm_available_bytes']<2147483648:
        save(output/'admission.json',{'status':'NOT_EXECUTED_DUE_TO_RESOURCE_ADMISSION','host':host,'probe':probe,'new_conditional_calls':0})
        save(output/'commands.json',commands);return 20
    save(output/'admission.json',{'status':'ADMITTED_HOST_AND_VM_ONLY','host':host,'probe':probe,
        'actual_scientific_cgroup_admission':'REQUIRED_INSIDE_THE_1024_MIB_PROCESS_BEFORE_ANY_F',
        'new_ordinary_scf_grid_integral_calls':0})
    if args.admission_only:
        save(output/'commands.json',commands);print('ADMISSION_ONLY_NO_SCIENTIFIC_RESERVATION',flush=True);return 0
    profile=source/'profiles/user-molecule/pilot-b3lypg-sto3g-grid2-v1.json'
    dependencies=json.loads(profile.read_bytes())['expected_dependencies']
    contract={key:copy.deepcopy(proposal[key]) for key in ('fixture','ordinary_origin','initialization','paths','comparisons','scope_limits')}
    contract.update(schema_version='residual-seed-v2-live-execution-contract-v1',batch_id='seed-v2-live-'+uuid.uuid4().hex,
        created_utc=utc(),runtime_test_commit=commit,science_commit=proposal['science_commit'],science_baseline_commit=proposal['science_baseline_commit'],
        image_id=candidate['image_id'],image_build_runtime_commit=candidate['runtime_build_commit'],
        profile_sha256=sha(profile),source_manifest_sha256=sha(source/'locks/source-user-molecule-files.sha256.json'),
        prior_proposal_sha256=sha(proposal_path),expected_dependencies=dependencies,dependencies_sha256=canonical_sha(dependencies),
        scientific_execution_authorized=True,production_activation=False,method_approval=False,
        authorization_basis={'source':'DIRECT_USER_MESSAGE','message':'请继续，可以进入新计算吗',
            'scope':'ONE_FIXED_PILOT_CONDITIONAL_DIAGNOSTIC_REUSING_ORDINARY_CACHE_NO_RETRY'},
        method_review_status='EXTERNAL_REVIEW_CANCELLED_BY_USER_INTERNAL_METHOD_VALIDATION_PENDING',
        process_contract={'memory_limit_mib':1024,'threads':1,'swap_allowed':False,'maximum_scientific_processes':1,
            'batch_wall_seconds':900,'process_wall_seconds':900,'serial_paths':True,'automatic_retry':False,
            'candidate_callbacks_per_path':201,'conditional_callback_slots_total':603},
        solver_parameters={'maximum_iterations':8,'finite_difference_step':1e-5,'trust_radius':.25,'maximum_backtracks':8},
        admission={'minimum_host_free_bytes':2147483648,'minimum_vm_available_bytes':2147483648,'host_receipt_sha256':sha(output/'host-admission.json')})
    contract['external_review_status']='CANCELLED'
    contract['external_review_required']=False
    contract['initialization']={'policy':'MASKED_METRIC_OCCUPIED_SUBSPACE_SEED_V2',
        'initial_gap_enforced':False,'final_gap_minimum_hartree':1e-6}
    contract['seed_binding']={key:copy.deepcopy(readiness[key]) for key in
        ('ordinary_D0_identity','ordinary_mo_coefficients_identity','ordinary_mo_occupations_identity','seed_density_identity')}
    contract['seed_binding'].update(policy=contract['initialization']['policy'],
        record_sha256=proposal['ordinary_origin']['record']['sha256'],arrays_sha256=proposal['ordinary_origin']['arrays']['sha256'],
        readiness_receipt_sha256=sha(readiness_path),implementation_runtime_commit=readiness['runtime_test_commit'],
        shared_seed_archive_sha256=sha(readiness_dir/'shared-seed.npz'),
        source_file_sha256=readiness['source_file_sha256'],
        mdr002_record_sha256=sha(source/'validation/user-molecule/method-decisions/mdr-002/record.json'),
        expert_cancellation_receipt_sha256=sha(source/'validation/user-molecule/method-decisions/mdr-002/external-review-cancellation.json'))
    validate_execution_contract(contract);validate_proposal_binding(contract,proposal_raw)
    contract_path=output/'execution-contract.json';save(contract_path,contract)
    identity=execution_identity(contract,sha(contract_path))
    save(output/'source-identity.json',dict(identity,source_archive_sha256=sha(archive),worker_sha256=sha(source/'scripts/diagnose-user-molecule-seed-v2-worker.py'),
        supervisor_sha256=sha(source/'scripts/diagnose-user-molecule-seed-v2.py')))
    budget=Budget(output/'SCIENTIFIC_WALL_BUDGET.json',contract['batch_id'],total_seconds=900,max_process_seconds=900,memory_limit_mib=1024,threads=1)
    save(output/'WALL_RESERVATION.json',reserve_single_process(budget,run_id='three-serial-paths',identity=identity))
    leaf=output/'output';leaf.mkdir();token=uuid.uuid4().hex;cid=None;started=time.monotonic()
    execution={'status':'RUNNING','started_at_utc':utc(),'identity':identity,'automatic_retry':False,'container_removed':False,
        'wall_reservation_before_launch':True,'wall_limit_seconds':900,'stop_deadline_seconds':840,'cleanup_headroom_seconds':60}
    completed=None
    try:
        launch=['create','--read-only','--network','none','--memory','1024m','--memory-swap','1024m','--cpus','1',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--user','10001:10001',
            '--label','ai4orgchem.residual-live='+token,'--tmpfs','/tmp:rw,nosuid,nodev,size=67108864,mode=1777',
            '--mount',f'type=bind,source={source},target=/workspace,readonly','--mount',f'type=bind,source={leaf},target=/output',
            '--mount',f'type=bind,source={cache},target=/saved-ordinary,readonly','--mount',f'type=bind,source={contract_path},target=/execution-contract.json,readonly',
            '--mount',f'type=bind,source={readiness_dir},target=/seed-readiness,readonly',
            '--workdir','/workspace','-e','PYTHONDONTWRITEBYTECODE=1','-e','OMP_NUM_THREADS=1','-e','OPENBLAS_NUM_THREADS=1',
            '-e','MKL_NUM_THREADS=1','-e','AI4ORGCHEM_SOURCE_ROOT=/opt/ai4orgchem',
            '-e','AI4ORGCHEM_RUNTIME_TEST_COMMIT='+commit,'-e','AI4ORGCHEM_IMAGE_ID='+candidate['image_id'],
            '-e','AI4ORGCHEM_IMAGE_BUILD_COMMIT='+candidate['runtime_build_commit'],'--entrypoint','python',candidate['image_id'],
            '-B','/workspace/scripts/diagnose-user-molecule-seed-v2-worker.py']
        save(output/'launch-command.json',[args.docker,*launch])
        cid=docker(*launch).decode().strip()
        if not re.fullmatch('[0-9a-f]{64}',cid):raise ValueError('Invalid scientific container ID')
        execution['container_id']=cid;docker('start',cid);next_progress=0
        while True:
            actual=json.loads(docker('inspect',cid))[0]
            if actual['Config']['Labels'].get('ai4orgchem.residual-live')!=token:raise ValueError('Scientific container ownership mismatch')
            if not actual['State']['Running']:break
            elapsed=time.monotonic()-started
            if elapsed>840:
                docker('stop','--time','2',cid);execution['termination_reason']='WALL_DEADLINE_NO_RETRY';break
            if elapsed>=next_progress:
                print(json.dumps({'phase':'SCIENTIFIC_DIAGNOSTIC_RUNNING','elapsed_seconds':elapsed}),flush=True);next_progress=elapsed+20
            time.sleep(.5)
        completed=json.loads(docker('inspect',cid))[0]
        save(output/'container-inspect.json',completed)
        execution['container_exit_code']=completed['State']['ExitCode'];execution['oom_killed']=completed['State']['OOMKilled']
        flags=completed['HostConfig']
        readonly_destinations={mount['Destination'] for mount in completed['Mounts'] if mount['RW'] is False}
        safe=(completed['Image']==candidate['image_id'] and completed['Config']['User']=='10001:10001' and flags['ReadonlyRootfs'] and flags['NetworkMode']=='none'
            and flags['Memory']==flags['MemorySwap']==1073741824 and flags['NanoCpus']==1000000000
            and {'/workspace','/saved-ordinary','/execution-contract.json','/seed-readiness'}<=readonly_destinations)
        execution['platform_flags_verified']=safe
        worker_record=leaf/'diagnostic-result.json'
        result=json.loads(worker_record.read_bytes()) if worker_record.exists() else None
        execution['diagnostic_record_available']=result is not None
        execution['status']='EXECUTED_DIAGNOSTIC_PENDING_RESOURCE_QUALIFICATION' if safe and completed['State']['ExitCode']==0 and not execution['oom_killed'] and result else 'DIAGNOSTIC_FAILED_OR_RESOURCE_REFUSED'
        execution['worker_execution_status']=None if result is None else result['execution_status']
    except BaseException as error:
        execution.update(status='FAILED_NO_RETRY',exception_type=type(error).__name__,error=str(error))
    finally:
        try:
            if cid:
                actual=json.loads(docker('inspect',cid))[0]
                if actual['Config']['Labels'].get('ai4orgchem.residual-live')!=token:raise ValueError('Scientific cleanup ownership mismatch')
                if actual['State']['Running']:docker('stop','--time','2',cid)
                completed=json.loads(docker('inspect',cid))[0]
                if not (output/'container-inspect.json').exists():save(output/'container-inspect.json',completed)
                logs=subprocess.run([args.docker,'logs',cid],capture_output=True,timeout=10)
                (output/'stdout.log').write_bytes(logs.stdout);(output/'stderr.log').write_bytes(logs.stderr)
                execution['logs_exit_code']=logs.returncode
                removal=docker('rm',cid);execution['container_removed']=removal.decode().strip()==cid
                save(output/'container-removal.json',{'container_id':cid,'removed':execution['container_removed'],'ownership_label':token})
        except BaseException as cleanup_error:
            execution.update(status='CLEANUP_UNRESOLVED_NO_RETRY',cleanup_exception=type(cleanup_error).__name__,cleanup_error=str(cleanup_error))
        finally:
            wall=time.monotonic()-started;execution['observed_wall_through_collection_and_removal_seconds']=wall
            confirmed_termination=completed is not None and completed['State']['Running'] is False and execution['container_removed']
            if confirmed_termination:
                settled=budget.settle('three-serial-paths',wall,execution.get('termination_reason',execution['status']),
                    {'container_removed':True,'container_exit_code':completed['State']['ExitCode']})
            else:
                settled=budget.snapshot();execution['status']='CLEANUP_UNRESOLVED_FULL_900S_RESERVED_NO_RETRY'
            save(output/'WALL_SETTLEMENT.json',settled)
            if settled['over_budget']:execution['status']='FAILED_WALL_BUDGET_NO_RETRY'
            save(output/'EXECUTION.json',execution);save(output/'commands.json',commands)
    if completed is not None:
        observations=[json.loads(line)['cgroup'] for line in (leaf/'resources.jsonl').read_text().splitlines()] if (leaf/'resources.jsonl').exists() else []
        external={'source':'DOCKER_INSPECT','container_id':cid,'oom_killed':completed['State']['OOMKilled'],
            'evidence_sha256':sha(output/'container-inspect.json'),'state_finished_at':completed['State']['FinishedAt'],
            'resource_identity_sha256':identity_digest(identity)}
        qualification=qualify_exact_fixture(identity,14,observations,memory_limit_mib=1024,threads=1,external_oom_evidence=external)
        if not execution['container_removed'] or execution.get('logs_exit_code')!=0 or settled['over_budget']:
            qualification['status']='BLOCKED';qualification['reasons'].append('CLEANUP_LOG_COLLECTION_OR_WALL_FAILED')
        save(output/'resource-qualification.json',qualification)
        save(output/'output-retention.json',{'container_removed':execution['container_removed'],
            'retained_file_count':sum(path.is_file() for path in leaf.rglob('*')),'output_directory':str(leaf)})
    print(json.dumps(execution,ensure_ascii=False),flush=True)
    return 0 if execution['status']=='EXECUTED_DIAGNOSTIC_PENDING_RESOURCE_QUALIFICATION' else 1


if __name__=='__main__':raise SystemExit(main())
