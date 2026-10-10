"""Retained supervision of one fixed optimisation state; conservative admission."""
from pathlib import Path
import argparse, datetime, hashlib, importlib.util, json, os, re, shutil, stat, subprocess, sys, time, uuid
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from runtime.high_cost_cases import SOURCE_LOCK,DEPENDENCY_LOCK,PROFILE,read_json,save,digest,unit,units,limits,validate_contract
from runtime.high_cost_cases.resources import host_memory,admission
sys.path.insert(0,str(ROOT/'scripts'))
from runtime_host_safety import recover_created_container,confirmed_absence,HostSafetyError
LABEL='ai4orgchem.high-cost.execution-id'
spec=importlib.util.spec_from_file_location('_preserved_batch2_path_helpers',ROOT/'scripts/run-protocol-case.py')
helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)
validate_directory=helpers.validate_directory

# This exception covers only final host evidence collection. The worker keeps
# the original 107-file scientific/source lock and immutable image identity.
HOST_LAUNCHER_LOCK=ROOT/'locks/high-cost-host-launcher.json'
HOST_LAUNCHER_FILES=frozenset(['scripts/run-high-cost-case.py','tests/test_high_cost_supervisor.py'])
BASE_SOURCE_SHA256='d8ee6bb0b7880db0f6d40dd38d93b633e1400ff6995f4e56e07042fddd6e7322'
BASE_IMAGE_ID='sha256:18dcd1da2e634cf6ab8d49a7281ca853c0a393e140ac95c6ec00448a3fc934bc'

def _base_host_sources(record):
    if digest(SOURCE_LOCK)!=BASE_SOURCE_SHA256 or record.get('source_sha256')!=BASE_SOURCE_SHA256 or record.get('image_id')!=BASE_IMAGE_ID:
        raise ValueError('Frozen host/worker base source or image differs')
    source=read_json(SOURCE_LOCK);rows=source.get('files')
    if not isinstance(rows,list) or len(rows)!=107:raise ValueError('Original 107-file source lock required')
    paths={}
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'path','sha256','size'}:raise ValueError('Original source file fields differ')
        name=row['path'];rel=Path(name)
        if not isinstance(name,str) or rel.is_absolute() or '..' in rel.parts or ':' in name or '\\' in name or name in paths or not re.fullmatch('[0-9a-f]{64}',str(row['sha256'])):
            raise ValueError('Unsafe or duplicate base source path/hash')
        if type(row['size']) is not int or row['size']<0:raise ValueError('Invalid base source size')
        paths[name]=row
    if not HOST_LAUNCHER_FILES<=set(paths):raise ValueError('The two fixed host paths are absent from base source')
    return paths

def _verify_host_files(base,overrides):
    for name,row in base.items():
        path=ROOT/name
        expected=overrides[name]['sha256'] if name in overrides else row['sha256']
        if path.is_symlink() or not path.is_file() or digest(path)!=expected:
            raise ValueError('Host source byte identity differs: '+name)

def make_host_launcher_lock(record=None):
    record=record or read_json(ROOT/'validation/high-cost-cases/candidate-image.json')
    base=_base_host_sources(record)
    files={name:{'base_sha256':base[name]['sha256'],'sha256':digest(ROOT/name)} for name in sorted(HOST_LAUNCHER_FILES)}
    _verify_host_files(base,files)
    return {'schema':'high-cost-host-launcher-v1','scope':'HOST_FINAL_EVIDENCE_ONLY',
            'base_source_sha256':BASE_SOURCE_SHA256,'image_id':BASE_IMAGE_ID,'files':files}

def verify_source(record=None):
    record=record or read_json(ROOT/'validation/high-cost-cases/candidate-image.json')
    base=_base_host_sources(record);registered=record.get('host_launcher_lock_sha256')
    if registered is None:
        _verify_host_files(base,{})
        return {'schema':'high-cost-host-launcher-identity-v1','scope':'BASELINE_NO_OVERLAY',
                'base_source_sha256':BASE_SOURCE_SHA256,'image_id':BASE_IMAGE_ID,'host_launcher_lock_sha256':None}
    if not re.fullmatch('[0-9a-f]{64}',str(registered)) or digest(HOST_LAUNCHER_LOCK)!=registered:
        raise ValueError('Registered host launcher lock SHA differs')
    overlay=read_json(HOST_LAUNCHER_LOCK)
    if set(overlay)!={'schema','scope','base_source_sha256','image_id','files'} or overlay['schema']!='high-cost-host-launcher-v1' or overlay['scope']!='HOST_FINAL_EVIDENCE_ONLY':
        raise ValueError('Closed final-evidence-only host launcher lock required')
    if overlay['base_source_sha256']!=BASE_SOURCE_SHA256 or overlay['image_id']!=BASE_IMAGE_ID:
        raise ValueError('Host launcher lock base source/image binding differs')
    files=overlay['files']
    if not isinstance(files,dict) or set(files)!=HOST_LAUNCHER_FILES:
        raise ValueError('Only the two frozen host file overrides are allowed')
    for name,row in files.items():
        if not isinstance(row,dict) or set(row)!={'base_sha256','sha256'} or row['base_sha256']!=base[name]['sha256'] or not re.fullmatch('[0-9a-f]{64}',str(row['sha256'])):
            raise ValueError('Host file override base/hash differs')
    _verify_host_files(base,files)
    return {'schema':'high-cost-host-launcher-identity-v1','scope':overlay['scope'],
            'base_source_sha256':BASE_SOURCE_SHA256,'image_id':BASE_IMAGE_ID,
            'host_launcher_lock_sha256':registered,'files':files}

class DockerJournal:
    def __init__(self,exe,run):self.exe=exe;self.run=run;self.deadline=None
    def __call__(self,*args,timeout=15,allow_failure=False,phase='COMMAND'):
        if self.deadline is not None:
            timeout=min(timeout,self.deadline-time.monotonic())
        if timeout<=0:raise TimeoutError('Host hard deadline exhausted')
        start=time.monotonic();row={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'arguments':[self.exe,*map(str,args)],'phase':phase,'timeout_seconds':timeout}
        try:
            result=subprocess.run(row['arguments'],capture_output=True,timeout=timeout)
            row.update(exit_code=result.returncode,duration_seconds=time.monotonic()-start)
            if phase!='POLL':
                idx=uuid.uuid4().hex
                (self.run/(idx+'.stdout')).write_bytes(result.stdout);(self.run/(idx+'.stderr')).write_bytes(result.stderr)
                row.update(stdout=idx+'.stdout',stderr=idx+'.stderr')
            if result.returncode and not allow_failure:raise RuntimeError('Docker failed: '+result.stderr.decode('utf-8','replace')[:800])
            return result
        except BaseException as e:row.update(error=type(e).__name__+': '+str(e));raise
        finally:
            with (self.run/'commands.jsonl').open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush()
def one(result):
    data=json.loads(result.stdout)
    if not isinstance(data,list) or len(data)!=1:raise ValueError('Single immutable inspection required')
    return data[0]
def image_check(data,record):
    if data.get('Id')!=record['image_id'] or data.get('Os')!='linux' or data.get('Architecture')!='amd64':raise ValueError('Image/platform differs')
    labels=data.get('Config',{}).get('Labels') or {}
    expected={'ai4orgchem.high-cost.schema':'high-cost-cases-v1','ai4orgchem.high-cost.runtime-commit':record['runtime_build_commit'],'ai4orgchem.high-cost.source-sha256':record['source_sha256'],'ai4orgchem.high-cost.dependency-sha256':record['dependencies_sha256'],'ai4orgchem.high-cost.profile-sha256':record['profile_sha256'],'ai4orgchem.high-cost.base-image-id':record['base_image_id']}
    if any(labels.get(k)!=v for k,v in expected.items()):raise ValueError('Immutable image labels differ')
    for key,path in [('source_sha256',SOURCE_LOCK),('dependencies_sha256',DEPENDENCY_LOCK),('profile_sha256',PROFILE)]:
        if digest(path)!=record[key]:raise ValueError('Host/record locks differ')
def ownership(d,c,cid):
    if d.get('Id')!=cid or d.get('Image')!=c['image_id'] or (d.get('Config',{}).get('Labels') or {}).get(LABEL)!=c['execution_id']:raise ValueError('Owned container identity differs')
def verify_container(d,c,cid,paths):
    ownership(d,c,cid);h=d['HostConfig'];cfg=d['Config'];r=c['resources']
    if cfg.get('User')!='10001:10001' or h.get('Privileged') is not False or h.get('ReadonlyRootfs') is not True:raise ValueError('Container user/filesystem differs')
    for k,v in {'Memory':r['memory_bytes'],'MemorySwap':r['memory_bytes'],'NanoCpus':r['cpus']*1000000000,'NetworkMode':'none','PidsLimit':256}.items():
        if h.get(k)!=v:raise ValueError('Actual resource/network differs '+k)
    if 'ALL' not in (h.get('CapDrop') or []) or h.get('CapAdd') or h.get('Devices') or h.get('DeviceRequests'):raise ValueError('Capabilities/devices differ')
    if not any(x in (h.get('SecurityOpt') or []) for x in ['no-new-privileges','no-new-privileges=true','no-new-privileges:true']):raise ValueError('No-new-privileges absent')
    expected=['-B','-m','runtime.high_cost_cases','--contract','/task-contract.json','--output-dir','/output']
    if cfg.get('Entrypoint')!=['/opt/venv/bin/python'] or cfg.get('Cmd')!=expected:raise ValueError('Worker command differs')
    mounts=d.get('Mounts',[])
    if len(mounts)!=4 or {m['Destination'] for m in mounts}!=set(paths):raise ValueError('Only four named mounts allowed')
    for m in mounts:
        p,rw=paths[m['Destination']];actual=m.get('Source','').replace('\\','/');want=str(p).replace('\\','/')
        forms={want.casefold()}
        if os.name=='nt' and re.match('^[A-Za-z]:/',want):
            suffix='/'+want[0].lower()+want[2:];forms|={('/run/desktop/mnt/host'+suffix).casefold(),('/host_mnt'+suffix).casefold()}
        if actual.casefold() not in forms or m.get('Type')!='bind' or m.get('RW') is not rw:raise ValueError('Mount identity/RW differs')
    threads={k: str(r['threads']) for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']}
    env=dict(x.split('=',1) for x in cfg.get('Env',[]) if '=' in x)
    if any(env.get(k)!=v for k,v in threads.items()):raise ValueError('Thread environment differs')
def snapshot_inputs(mapping,run,record,selected):
    wanted=set(selected.get('dependencies',[])) if selected else set()
    if not isinstance(mapping,dict) or set(mapping)!=wanted:raise ValueError('Exact current-run dependencies required')
    records={};target=run/'inputs';target.mkdir()
    for identifier,path in mapping.items():
        source=validate_directory(Path(path));r=read_json(source/'worker-receipt.json');result=read_json(source/'result.json')
        for p in source.rglob('*'):
            info=p.lstat()
            if p.is_symlink() or getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',1024):raise ValueError('Linked dependency files or ancestry forbidden')
        host=read_json(source.parent/'host-execution.json')
        if r.get('status')!='PASS_SCOPED_HIGH_COST_STATE' or r.get('unit')!=identifier or r.get('mode')!='live' or host.get('status')!='PASS_SCOPED_HIGH_COST_LIVE' or host.get('container_removed') is not True:raise ValueError('A completed fresh state with owned cleanup required')
        for key in ['source_sha256','dependencies_sha256','profile_sha256','image_id']:
            if result.get(key)!=record[key]:raise ValueError('Dependency method/environment differs')
        manifest=read_json(source/'run-manifest.json')
        for name,sha in manifest['files'].items():
            rel=Path(name)
            if rel.is_absolute() or '..' in rel.parts or ':' in name or '\\' in name or digest(source/rel)!=sha:raise ValueError('Dependency output hash/path differs')
        if digest(source/'run-manifest.json')!=r.get('run_manifest_sha256') or digest(source/'result.json')!=r.get('result_sha256'):raise ValueError('Dependency receipt differs')
        dest=target/identifier;shutil.copytree(source,dest,symlinks=False)
        for f in dest.rglob('*'):
            if f.is_symlink():raise ValueError('Symlink dependency snapshot forbidden')
        copied_receipt=read_json(dest/'worker-receipt.json')
        if digest(dest/'run-manifest.json')!=copied_receipt.get('run_manifest_sha256') or digest(dest/'result.json')!=copied_receipt.get('result_sha256'):raise ValueError('Dependency changed during snapshot copy')
        for name,sha in read_json(dest/'run-manifest.json')['files'].items():
            rel=Path(name)
            if rel.is_absolute() or '..' in rel.parts or ':' in name or '\\' in name or digest(dest/rel)!=sha:raise ValueError('Copied dependency manifest/file linkage differs')
        records[identifier]={'relative_path':identifier,'worker_receipt_sha256':digest(dest/'worker-receipt.json'),'result_sha256':digest(dest/'result.json'),**{k:record[k] for k in ['source_sha256','dependencies_sha256','profile_sha256','image_id']}}
    return records
def verify_outputs(out,c):
    r=read_json(out/'worker-receipt.json');g=read_json(out/'guard-receipt.json');v=read_json(out/'result.json');m=read_json(out/'run-manifest.json')
    expected='PASS_SCOPED_HIGH_COST_STATE' if c['mode']=='live' else 'PASS_SCOPED_HIGH_COST_'+c['mode'].upper()
    contract_sha=hashlib.sha256((json.dumps(c,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode('utf-8')).hexdigest()
    if r.get('status')!=expected or r.get('worker_exit_code')!=0 or r.get('contract')!=c or r.get('contract_sha256')!=contract_sha or v.get('status')!='PASS':raise ValueError('Worker scoped result differs')
    if (out/'task-contract.json').exists():raise ValueError('Unexpected duplicated task-contract output')
    if g.get('status')!='PASS' or g.get('closed') is not True or g.get('restored_attributes_intact') is not True or g.get('denied') or g.get('changed'):raise ValueError('Entry guard not closed')
    if c['mode']!='live' and any(g['counts'].values()):raise ValueError('Kernels in ledger/preflight')
    if c['mode']=='live' and g['counts'].get('optimizer',0)!=1:raise ValueError('Exactly one optimisation required')
    for k,val in g['counts'].items():
        if type(val) is not int or val<0 or val>g['caps'].get(k,0):raise ValueError('Dispatch cap differs')
        if g.get('outcomes',{}).get(k)!={'returned':val,'failed':0}:raise ValueError('Dispatch not all returned')
    required={'result.json','guard-receipt.json','native-events.jsonl','resource-start.json','resource-end.json'}
    if not required<=set(m['files']):raise ValueError('Output manifest incomplete')
    for name,sha in m['files'].items():
        rel=Path(name)
        if rel.is_absolute() or '..' in rel.parts or ':' in name or '\\' in name or digest(out/rel)!=sha:raise ValueError('Output changed/unsafe')
    for filename in ['resource-start.json','resource-end.json']:
        if read_json(out/filename).get('status')!='PASS':raise ValueError('Actual resources incomplete')
    for field,file in [('result_sha256','result.json'),('guard_sha256','guard-receipt.json'),('run_manifest_sha256','run-manifest.json')]:
        if r.get(field)!=digest(out/file):raise ValueError('Receipt hash differs')
    return {'status':'PASS','worker_receipt_sha256':digest(out/'worker-receipt.json'),'result_sha256':digest(out/'result.json'),'counts':g['counts']}
def run(args):
    host_launcher=verify_source();root=validate_directory(args.output_root);root.mkdir(parents=True,exist_ok=True)
    identifier=uuid.uuid4().hex;run=root/(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+(args.unit or args.task)+'-'+identifier);run.mkdir()
    out=run/'output';out.mkdir();scratch=run/'scratch';scratch.mkdir();(run/'contract').mkdir()
    lock=root/'.high-cost-active.lock';locked=False;cid=None;docker=DockerJournal(args.docker_executable,run);start=None;reservation=None;code=40;c=None;create_attempted=False;quarantine=False
    creation_name='high-cost-state-'+identifier
    probe_name='high-cost-resource-probe-'+identifier;probe_attempted=False;probe_command_completed=False
    e={'schema':'high-cost-host-v1','execution_id':identifier,'case':args.task,'unit':args.unit,'mode':args.mode,'status':'NOT_EXECUTED','container_removed':False,'worker_started':False,'automatic_retry':False,'resume_supported':False,'host_launcher':host_launcher}
    try:
        with lock.open('x',encoding='utf-8') as f:json.dump({'execution_id':identifier},f)
        locked=True
        selected=unit(args.unit) if args.unit else None
        if args.mode=='live' and selected is None:raise ValueError('One explicit optimisation unit required')
        if selected and selected['case']!=args.task:raise ValueError('Case/unit differs')
        record=read_json(ROOT/'validation/high-cost-cases/candidate-image.json')
        image=one(docker('image','inspect',record['image_id']));image_check(image,record);save(run/'image-inspect.json',image)
        engine=json.loads(docker('info','--format','{{json .}}').stdout)
        probe_attempted=True
        probe=docker('run','--rm','--name',probe_name,'--label',LABEL+'=probe-'+identifier,'--network','none','--read-only','--user','10001:10001','--memory','134217728','--memory-swap','134217728','--cpus','1','--cap-drop','ALL','--security-opt','no-new-privileges','--entrypoint','/opt/venv/bin/python',record['image_id'],'-B','-c',"import json;d={l.split(':')[0]:int(l.split()[1])*1024 for l in open('/proc/meminfo')};print(json.dumps({'available_bytes':d['MemAvailable'],'total_bytes':d['MemTotal']}))")
        probe_command_completed=True
        resource=limits(args.task,args.mode);guest=json.loads(probe.stdout);host=host_memory()
        admit=admission(resource,{'NCPU':engine.get('NCPU'),'MemTotal':engine.get('MemTotal')},guest,host,shutil.disk_usage(root).free,live=args.mode=='live');save(run/'admission.json',admit);e['admission']=admit
        if admit['status']!='PASS':e['status']=admit['status'];raise ValueError('Resource admission refused: '+','.join(admit['reasons']))
        mapping=read_json(args.inputs) if args.inputs else {};dependencies=snapshot_inputs(mapping,run,record,selected if args.mode=='live' else None)
        if args.mode=='live':
            if args.budget is None:raise ValueError('An independent durable third-batch budget is required')
            if (ROOT/'validation/high-cost-cases/admission-pause.json').exists():raise ValueError('New high-cost launches paused; no reservation')
            validate_directory(args.budget.parent)
            from runtime.high_cost_cases.budget import reserve
            reservation=reserve(args.budget,args.unit,resource,{'profile_sha256':record['profile_sha256'],'source_sha256':record['source_sha256'],'dependencies_sha256':record['dependencies_sha256'],'image_id':record['image_id'],'method_id':selected['method_id']},identifier)
        now=time.time();start=time.monotonic();docker.deadline=start+resource['hard_wall_seconds']
        c={'schema':'high-cost-state-execution-v1','case':args.task,'mode':args.mode,'unit':args.unit,'execution_id':identifier,'image_id':record['image_id'],'runtime_build_commit':record['runtime_build_commit'],'source_sha256':record['source_sha256'],'dependencies_sha256':record['dependencies_sha256'],'profile_sha256':record['profile_sha256'],'resources':resource,'started_epoch':now,'stop_deadline_epoch':now+resource['soft_wall_seconds'],'hard_deadline_epoch':now+resource['hard_wall_seconds'],'inputs':dependencies}
        validate_contract(c);contract=run/'contract/task-contract.json';save(contract,c);e.update(contract=c,image_id=c['image_id'],status='ADMITTED')
        paths={'/task-contract.json':(contract,False),'/output':(out,True),'/inputs':(run/'inputs',False),'/scratch':(scratch,True)}
        cmd=['create','--name',creation_name,'--label',LABEL+'='+identifier,'--network','none','--read-only','--user','10001:10001','--cpus',str(resource['cpus']),'--memory',str(resource['memory_bytes']),'--memory-swap',str(resource['memory_bytes']),'--pids-limit','256','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp:rw,nosuid,nodev,size=268435456','--env','TMPDIR=/scratch']
        for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:cmd+=['--env',k+'='+str(resource['threads'])]
        cmd+=['--env','PYTHONDONTWRITEBYTECODE=1']
        for dest,(path,rw) in paths.items():cmd+=['--mount','type=bind,source='+str(path)+',target='+dest+('' if rw else ',readonly')]
        cmd+=['--entrypoint','/opt/venv/bin/python',c['image_id'],'-B','-m','runtime.high_cost_cases','--contract','/task-contract.json','--output-dir','/output'];save(run/'launch-command.json',[args.docker_executable,*cmd])
        save(run/'create-intent.json',{'name':creation_name,'image_id':record['image_id'],'label_key':LABEL,'token':identifier})
        create_attempted=True;cid=docker(*cmd).stdout.decode().strip()
        if not re.fullmatch('[0-9a-f]{64}',cid):raise ValueError('Full created container ID required')
        e.update(container_id=cid,status='RUNNING');created=one(docker('inspect',cid));verify_container(created,c,cid,paths);save(run/'container-created.json',created)
        docker('start',cid);e['worker_started']=True
        while True:
            state=one(docker('inspect',cid,phase='POLL'));verify_container(state,c,cid,paths)
            save(run/'container-last.json',state)
            if state['State']['Running'] is False:break
            if time.monotonic()>=start+resource['soft_wall_seconds']:
                e['stop_requested']=True
                usable=docker.deadline-time.monotonic()-45
                if usable<=5:raise TimeoutError('No safe cleanup window remains')
                grace=min(60,max(0,int(usable)-5));docker('stop','--time',str(grace),cid,timeout=min(65,usable));break
            time.sleep(min(5,max(0,start+resource['soft_wall_seconds']-time.monotonic())))
        final=one(docker('inspect',cid,timeout=5));verify_container(final,c,cid,paths);save(run/'container-finished.json',final)
        e.update(container_exit_code=final['State'].get('ExitCode'),oom_killed=final['State'].get('OOMKilled'))
        if e.get('stop_requested') or final['State'].get('OOMKilled') is not False or final['State'].get('ExitCode')!=0:raise RuntimeError('Worker incomplete/failed; retained as not qualified')
        e['evidence_review']=verify_outputs(out,c);code=0;e['status']='PASS_PENDING_CLEANUP'
    except BaseException as error:
        e['error']={'type':type(error).__name__,'message':str(error)}
        if not str(e['status']).startswith('BLOCKED_RESOURCE'):e['status']='REFUSED_OR_NOT_QUALIFIED'
        code=50 if isinstance(error,(TimeoutError,subprocess.TimeoutExpired,KeyboardInterrupt)) else 40
    finally:
        if create_attempted and (not cid or not re.fullmatch('[0-9a-f]{64}',cid)):
            try:
                cid=recover_created_container(docker,name=creation_name,image_id=record['image_id'],label_key=LABEL,token=identifier)
                e.update(container_id=cid,create_recovery='OWNED_ID_RECOVERED' if cid else 'ABSENT_NOW_CREATE_COMPLETION_UNKNOWN')
                if cid is None:quarantine=True;e['status']='FAILED_OR_UNKNOWN_CLEANUP'
            except BaseException as error:
                cid=None;quarantine=True;e.update(unknown_creation_error=str(error),status='FAILED_OR_UNKNOWN_CLEANUP',create_recovery='UNKNOWN_QUARANTINED')
        if cid:
            try:
                current=one(docker('inspect',cid,timeout=5));ownership(current,c,cid)
                if current['State'].get('Running'):
                    e['forced_stop_on_error']=True;docker('stop','--time','30',cid,timeout=35)
                logs=docker('logs',cid,timeout=10,allow_failure=True);(run/'container.stdout').write_bytes(logs.stdout);(run/'container.stderr').write_bytes(logs.stderr)
                e['logs_collected']=logs.returncode==0
                if not e['logs_collected']:raise ValueError('Container logs not closed')
                docker('rm',cid,timeout=10)
                absent=docker('inspect',cid,timeout=5,allow_failure=True)
                if not confirmed_absence(absent,cid):raise ValueError('Removal unconfirmed')
                e['container_removed']=True
                if code==0:
                    after=verify_outputs(out,c)
                    if after!=e['evidence_review']:raise ValueError('Output changed after deletion')
                    e['post_removal_evidence_review']=after;e['status']='PASS_SCOPED_HIGH_COST_'+args.mode.upper()
            except BaseException as error:quarantine=True;e.update(cleanup_error=type(error).__name__+': '+str(error),status='FAILED_OR_UNKNOWN_CLEANUP');code=50
        if probe_attempted:
            try:
                old_deadline=docker.deadline;docker.deadline=None
                inspected=docker('inspect',probe_name,timeout=5,allow_failure=True)
                if inspected.returncode==0:
                    data=one(inspected)
                    if data.get('Image')!=record['image_id'] or data.get('Name')!='/'+probe_name or not re.fullmatch('[0-9a-f]{64}',str(data.get('Id'))) or (data.get('Config',{}).get('Labels') or {}).get(LABEL)!='probe-'+identifier:raise ValueError('Probe ownership differs')
                    docker('rm','--force',data['Id'],timeout=5)
                    absent=docker('inspect',data['Id'],timeout=5,allow_failure=True)
                    if not confirmed_absence(absent,data['Id']):raise ValueError('Probe removal unconfirmed')
                elif not confirmed_absence(inspected,probe_name) or not probe_command_completed:raise ValueError('Probe absence cannot close an unfinished run/create request')
                e['owned_capacity_probe_closed']=True;docker.deadline=old_deadline
            except BaseException as error:quarantine=True;e['probe_cleanup_error']=str(error);e.update(status='FAILED_OR_UNKNOWN_PROBE_CLEANUP',host_exit_code=40);code=40
            finally:docker.deadline=old_deadline
        if locked and not quarantine:
            try:
                if read_json(lock).get('execution_id')!=identifier:raise ValueError('Active lock ownership differs')
                lock.unlink();e['owned_lock_released']=True
            except BaseException as error:e.update(status='FAILED_LOCK_CLEANUP',host_exit_code=40,lock_cleanup_error=str(error));code=40
        elif locked:
            e.update(owned_lock_released=False,owned_lock_retained='UNCONFIRMED_CONTAINER_STATE',quarantine_lock=str(lock))
        e.update(creation_attempted=create_attempted,cleanup_closed=not quarantine and (not create_attempted or e['container_removed'] is True))
        # Close every owned Docker operation before hashing the journal and its
        # stdout/stderr files. Probe cleanup also appends to commands.jsonl.
        # Scratch is retained but excluded from scientific output hashes.
        hashes={str(f.relative_to(run)).replace('\\','/'):digest(f) for f in run.rglob('*') if f.is_file() and not f.is_symlink() and scratch not in f.parents}
        elapsed=time.monotonic()-start if start else 0
        if start and elapsed>c['resources']['hard_wall_seconds']:e['status']='FAILED_HARD_WALL_EXCEEDED';code=50
        e.update(host_exit_code=code,through_cleanup_wall_seconds=elapsed,ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        if reservation:
            try:
                from runtime.high_cost_cases.budget import settle
                e['budget']=settle(args.budget,identifier,elapsed,e['cleanup_closed'] and e.get('owned_lock_released') is True,e['status'])
            except BaseException as error:e['budget_error']=str(error);code=40;e.update(host_exit_code=code,status='FAILED_BUDGET_CLOSURE')
        save(run/'host-execution.json',e)
        hashes['host-execution.json']=digest(run/'host-execution.json')
        save(run/'host-run-manifest.json',{'schema':'high-cost-host-output-v1','execution_id':identifier,'status':e['status'],'files':hashes,'scratch':'RETAINED_INTERMEDIATE_NOT_HASHED_AS_SCIENTIFIC_OUTPUT','wall_scope':'THROUGH_OWNED_SCIENTIFIC_CLEANUP_AND_EVIDENCE_HASH_COLLECTION_EXCLUDES_FINAL_RECEIPT_SERIALIZATION'})
    return code,run,e
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--task',choices=['P11','P12'],required=True);p.add_argument('--mode',choices=['ledger','preflight','live'],required=True);p.add_argument('--unit');p.add_argument('--output-root',type=Path,required=True);p.add_argument('--budget',type=Path);p.add_argument('--inputs',type=Path);p.add_argument('--docker-executable',default='docker');a=p.parse_args(argv)
    try:code,root,e=run(a)
    except Exception as error:print(json.dumps({'status':'REFUSED_BEFORE_LAUNCH','error':str(error)}));return 40
    print(json.dumps({'status':e['status'],'exit_code':code,'records':str(root)},ensure_ascii=False));return code
if __name__=='__main__':raise SystemExit(main())
