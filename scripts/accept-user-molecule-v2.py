"""Host supervisor: clean Git export, bounded offline acceptance-only containers."""
import argparse
import ctypes
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from runtime.user_molecule.records import load,save,file_hash
from runtime.user_molecule.acceptance_resources import Budget,qualify_exact_fixture,identity_digest,_lock
from runtime.user_molecule.solver_contract import verify_previous_evidence


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root',type=Path,required=True)
    parser.add_argument('--batch-ledger',type=Path,required=True)
    parser.add_argument('--tests-only',action='store_true')
    parser.add_argument('--fixture',action='append')
    parser.add_argument('--lock-root',type=Path,default=Path(r'D:\AI4Science\ai4orgchem-runtime-runs\.host-locks'))
    args=parser.parse_args()
    args.lock_root.mkdir(parents=True,exist_ok=True)
    output=args.output_root.resolve()
    if output.exists() or output==ROOT or ROOT in output.parents:
        raise ValueError('Fresh evidence directory outside runtime required')
    git=lambda *a:subprocess.check_output(['git',*a],cwd=ROOT).decode().strip()
    if git('status','--porcelain'):
        raise ValueError('Clean committed runtime required')
    contract_path=ROOT/'validation/user-molecule/solver-v2/acceptance-contract-v2.json'
    contract=load(contract_path)
    prior_check=verify_previous_evidence(contract)
    candidate=load(ROOT/'validation/user-molecule/candidate-image.json')
    image=candidate['image_id']
    if not re.fullmatch('sha256:[0-9a-f]{64}',image):
        raise ValueError('Immutable local image ID required')
    def docker(*arguments):
        result=subprocess.run(['docker',*arguments],capture_output=True,timeout=30)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors='replace'))
        return result.stdout.decode()
    server=json.loads(docker('version','--format','{{json .Server}}'))
    image_inspect=json.loads(docker('image','inspect',image))[0]
    labels=image_inspect['Config']['Labels']
    if labels.get('ai4orgchem.source.commit')!=candidate['science_commit'] or labels.get('org.opencontainers.image.revision')!=candidate['runtime_build_commit']:
        raise ValueError('Image lineage mismatch')
    output.mkdir(parents=True)
    save(output/'prior-evidence-check.json',prior_check)
    admission={'runtime_test_commit':git('rev-parse','HEAD'),'contract_sha256':file_hash(contract_path),
        'actual_process_memory_mib':contract['budget']['memory_mib'],
        'headroom_mib':contract['budget']['available_headroom_mib'],'status':'CHECKING'}
    # Keep ample host headroom; a hard Docker cap is not a reservation of VM RAM.
    host_available=None
    if os.name=='nt':
        class MemoryStatus(ctypes.Structure):
            _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(name,ctypes.c_ulonglong) for name in ('total_phys','avail_phys','total_page','avail_page','total_virtual','avail_virtual','avail_extended')]
        memory=MemoryStatus();memory.length=ctypes.sizeof(memory)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
            raise OSError('Host memory observation unavailable')
        host_available=memory.avail_phys
        admission['host_available_memory_bytes']=host_available
        if not args.tests_only and host_available<(contract['budget']['memory_mib']+contract['budget']['available_headroom_mib'])*1024**2:
            admission.update(status='BLOCKED',reason='HOST_MEMORY_BELOW_BUDGET_PLUS_HEADROOM');save(output/'admission.json',admission)
            raise ValueError('Observed host free memory below frozen budget plus headroom; no automatic host changes')
    engine_info=json.loads(docker('info','--format','{{json .}}'))
    if not args.tests_only and engine_info['MemTotal']<(contract['budget']['memory_mib']+contract['budget']['available_headroom_mib'])*1024**2:
        admission.update(status='BLOCKED',reason='VM_TOTAL_BELOW_BUDGET_PLUS_HEADROOM');save(output/'admission.json',admission)
        raise ValueError('Docker VM total memory below bounded run + headroom')
    admission['status']='PASS_HOST_AND_VM_TOTAL_ONLY';save(output/'admission.json',admission)
    save(output/'docker-server.json',server)
    # Restrict saved engine info to platform/resource fields, avoiding irrelevant host secrets.
    save(output/'engine-resource.json',{key:engine_info.get(key) for key in ('MemTotal','NCPU','CgroupVersion','CgroupDriver','OperatingSystem','KernelVersion')})
    save(output/'image-inspect.json',image_inspect)
    commit=git('rev-parse','HEAD')
    archive=output/'runtime-source.tar'
    subprocess.run(['git','archive','--format=tar','-o',str(archive),commit],cwd=ROOT,check=True)
    export=output/'runtime-source';export.mkdir()
    with tarfile.open(archive) as stream:
        stream.extractall(export,filter='data')
    save(output/'source-identity.json',{'runtime_test_commit':commit,'source_archive_sha256':file_hash(archive),
        'image_id':image,'image_runtime_build_commit':candidate['runtime_build_commit'],'science_commit':candidate['science_commit'],
        'contract_sha256':file_hash(contract_path),'host_available_memory_bytes':host_available,
        'prior_evidence':contract['prior_evidence'], 'solver_strategy':contract['solver_strategy'],
        'scope':'New committed v2 candidate mounted read-only over existing image; frozen science and production profiles unchanged; no rebuilt image'})
    budget=Budget(args.batch_ledger,contract['batch_id'],total_seconds=7200,max_process_seconds=900,memory_limit_mib=1024,threads=1)
    cases=[{'id':'engineering','request':None}] if args.tests_only else contract['fixtures']
    if args.fixture:
        cases=[case for case in cases if case['id'] in args.fixture]
        if set(args.fixture)!=set(case['id'] for case in cases):
            raise ValueError('Unknown acceptance fixture')
    results=[]
    for case in cases:
        if not args.tests_only:
            prior=budget.snapshot()['runs'].values()
            scientific_count=sum(row['identity']['mode']!='GUARDED_UNIT_TESTS' for row in prior)
            if scientific_count>=contract['budget']['maximum_scientific_processes']:
                raise ValueError('Persistent scientific process-count ceiling reached; no automatic retry')
        destination=output/case['id'];destination.mkdir()
        if case['request']:
            request=load(export/case['request'])
            profile_path=export/'profiles/user-molecule'/(request['calculation_profile']+'.json')
            profile=load(profile_path)
            geometry=export/Path(case['request']).parent/request['geometry_file']
            identity={'geometry_sha256':file_hash(geometry),'profile_sha256':file_hash(profile_path),
                'dependencies_sha256':hashlib.sha256(json.dumps(profile['expected_dependencies'],sort_keys=True).encode()).hexdigest(),
                'rules_sha256':load(export/'locks/source.user-molecule.lock.json')['condition_rules_sha256'],
                'mode':'SEQUENTIAL_SOLVER_V2_DIAGNOSTIC','runtime_test_commit':commit,'image_id':image,
                'contract_sha256':file_hash(contract_path)}
            limit=contract['budget']['process_seconds'];memory_mib=contract['budget']['memory_mib']
        else:
            identity={'geometry_sha256':'0'*64,'profile_sha256':file_hash(contract_path),'dependencies_sha256':file_hash(export/'locks/requirements-linux-amd64.txt'),
                'mode':'GUARDED_UNIT_TESTS','runtime_test_commit':commit,'image_id':image}
            limit=120;memory_mib=512
        run_id=output.name+'-'+case['id']
        budget.reserve(run_id,limit,identity)
        token=uuid.uuid4().hex
        arguments=['create','--read-only','--network','none','--memory',str(memory_mib)+'m','--memory-swap',str(memory_mib)+'m','--cpus','1',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--user','10001:10001',
            '--label','ai4orgchem.acceptance-run='+token,
            '--tmpfs','/tmp:rw,nosuid,nodev,size=67108864,mode=1777',
            '--mount',f'type=bind,source={export},target=/workspace,readonly',
            '--mount',f'type=bind,source={destination},target=/output',
            '--mount',f'type=bind,source={args.lock_root.resolve()},target=/locks',
            '--workdir','/workspace','-e','PYTHONPATH=/workspace:/opt/ai4orgchem/software/src',
            '-e','OMP_NUM_THREADS=1','-e','OPENBLAS_NUM_THREADS=1','-e','PYTHONDONTWRITEBYTECODE=1',
            '-e','AI4ORGCHEM_SOURCE=/opt/ai4orgchem','-e','AI4ORGCHEM_RUNTIME_TEST_COMMIT='+commit,
            '-e','AI4ORGCHEM_IMAGE_ID='+image,'--entrypoint','python',image,
            'scripts/accept-user-molecule-v2-worker.py','--output','/output']
        arguments+=['--tests-only'] if args.tests_only else ['--fixture',case['id']]
        execution={'command':['docker',*arguments],'run_id':run_id,'status':'RUNNING','container_removed':False,'timeout_seconds':limit,'identity':identity}
        save(destination/'execution.json',execution)
        cid=None;begin=time.monotonic();reason='UNKNOWN';observation=None
        try:
            cid=docker(*arguments).strip()
            if not re.fullmatch('[0-9a-f]{64}',cid):
                raise ValueError('Invalid container identity')
            execution['container_id']=cid
            docker('start',cid)
            while True:
                inspected=json.loads(docker('inspect',cid))[0]
                if inspected['Config']['Labels'].get('ai4orgchem.acceptance-run')!=token:
                    raise ValueError('Container ownership mismatch')
                if not inspected['State']['Running']:
                    break
                if time.monotonic()-begin>limit:
                    reason='TIMEOUT';docker('kill',cid)
                    inspected=json.loads(docker('inspect',cid))[0]
                    break
                time.sleep(.5)
            save(destination/'container-inspect.json',inspected)
            state=inspected['State'];code=state['ExitCode']
            if state['OOMKilled']:
                reason='OOM'
            elif reason!='TIMEOUT':
                reason='COMPLETED' if code==0 else 'WORKER_FAILED'
            execution.update(container_exit_code=code,oom_killed=state['OOMKilled'],termination_reason=reason)
            if args.tests_only and (destination/'unit-tests.json').exists():
                execution['status']=load(destination/'unit-tests.json')['status']
            elif (destination/'result.json').exists():
                record=load(destination/'result.json');execution['status']=record['status'];observation=record.get('cgroup_final')
                if record.get('nao'):
                    external={'source':'DOCKER_INSPECT','container_id':cid,'oom_killed':state['OOMKilled'],
                        'state_finished_at':state['FinishedAt'],'evidence_sha256':file_hash(destination/'container-inspect.json'),
                        'resource_identity_sha256':identity_digest(identity)}
                    resource=qualify_exact_fixture(identity,record['nao'],[observation],memory_limit_mib=memory_mib,threads=1,external_oom_evidence=external)
                    phases={row['name'] for row in record.get('phases',[])}
                    if not {'PRODUCTION_CONDITIONAL_SINGLE','PRODUCTION_CONDITIONAL_COPY','CONDITIONAL_RECOMPUTE'} <= phases:
                        resource['status']='BLOCKED';resource['reasons'].append('FULL_ACCEPTANCE_BUNDLE_NOT_EXECUTED')
                    save(destination/'resource-candidate.json',resource)
                    execution['resource_status']=resource['status']
            else:
                execution['status']='FAIL_NO_RESULT'
            truth=inspected['HostConfig']['NetworkMode']=='none' and inspected['HostConfig']['ReadonlyRootfs'] and inspected['Config']['User']=='10001:10001'
            if not truth or inspected['HostConfig']['Memory']!=memory_mib*1024**2 or inspected['HostConfig']['MemorySwap']!=memory_mib*1024**2:
                raise ValueError('Observed isolation mismatch')
        except Exception as exc:
            execution.update(status='FAIL_SUPERVISOR',error=type(exc).__name__+': '+str(exc),termination_reason=reason)
        finally:
            cleanup_errors=[];confirmed_stopped=False
            if cid:
                try:
                    inspected=json.loads(docker('inspect',cid))[0]
                    if inspected['Config']['Labels'].get('ai4orgchem.acceptance-run')!=token:
                        raise ValueError('Cleanup ownership mismatch')
                    if inspected['State']['Running']:
                        docker('kill',cid)
                    inspected=json.loads(docker('inspect',cid))[0]
                    confirmed_stopped=not inspected['State']['Running']
                    logs=subprocess.run(['docker','logs',cid],capture_output=True,timeout=30)
                    (destination/'stdout.log').write_bytes(logs.stdout);(destination/'stderr.log').write_bytes(logs.stderr)
                    if confirmed_stopped:
                        docker('rm',cid);execution['container_removed']=True
                except Exception as exc:
                    cleanup_errors.append(type(exc).__name__+': '+str(exc))
            execution['elapsed_seconds']=time.monotonic()-begin
            execution['cleanup_errors']=cleanup_errors
            if confirmed_stopped or cid is None:
                try:
                    budget.settle(run_id,execution['elapsed_seconds'],reason,observation)
                    execution['budget_state']='SETTLED'
                except Exception as exc:
                    cleanup_errors.append('Budget settlement: '+str(exc))
                    execution['budget_state']='RESERVED_UNKNOWN'
            else:
                execution['budget_state']='RESERVED_TERMINATION_UNKNOWN'
                execution['worker_status']=execution['status'];execution['status']='BLOCKED_TERMINATION_UNKNOWN'
            save(destination/'execution.json',execution)
            files={p.relative_to(destination).as_posix():{'sha256':file_hash(p),'size_bytes':p.stat().st_size} for p in destination.rglob('*') if p.is_file() and p.name!='manifest.json'}
            save(destination/'manifest.json',{'files':files,'container_removed':execution['container_removed']})
            results.append(execution)
            print(json.dumps({'fixture':case['id'],'status':execution['status'],'wall_seconds':execution['elapsed_seconds'],'resource_status':execution.get('resource_status')},ensure_ascii=False),flush=True)
        if args.tests_only and execution['status']!='PASS':
            break
        if execution.get('budget_state')!='SETTLED' or not execution['container_removed']:
            break
    save(output/'batch-summary.json',{'runs':results,'budget':budget.snapshot(),'production_activation':False,'method_review_status':'PENDING_REAL_REVIEW'})
    return 0 if all(row['status'] in ('PASS','PASS_ACCEPTANCE_ONLY') for row in results) else 30


if __name__=='__main__':
    # Same default host lock used by the existing PowerShell Compute launcher.
    # A custom lock directory must be shared by every compute entry point.
    index=sys.argv.index('--lock-root')+1 if '--lock-root' in sys.argv else None
    lock_root=Path(sys.argv[index]) if index is not None else Path(r'D:\AI4Science\ai4orgchem-runtime-runs\.host-locks')
    lock_root.mkdir(parents=True,exist_ok=True)
    with _lock(lock_root/'windows-quantum.lock'):
        sys.exit(main())
