"""Explicitly capture third-batch science bytes; original checkouts remain read only."""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess, sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from runtime.high_cost_cases import ASSETS,CASE_MODULES,adapter,digest,save,units,limits
def git(origin,*args):
    r=subprocess.run(['git',*args],cwd=origin,capture_output=True,timeout=60)
    if r.returncode:raise RuntimeError(r.stderr.decode('utf-8','replace'))
    return r.stdout
def capture(origin):
    files=set().union(*(adapter(c).assets() for c in CASE_MODULES));files.add('LICENSE')
    if (origin/'NOTICE').is_file():files.add('NOTICE')
    head=git(origin,'rev-parse','HEAD').decode().strip();rows=[]
    for name in sorted(files):
        p=origin/name
        if not p.is_file() or p.is_symlink():raise ValueError('Missing or unsafe source '+name)
        q=ASSETS/name;q.parent.mkdir(parents=True,exist_ok=True)
        if q.exists() and q.read_bytes()!=p.read_bytes():raise ValueError('Existing frozen capture differs '+name)
        shutil.copyfile(p,q)
        tracked=subprocess.run(['git','ls-files','--error-unmatch','--',name],cwd=origin,capture_output=True).returncode==0
        head_blob=None
        if tracked:
            r=subprocess.run(['git','rev-parse','HEAD:'+name],cwd=origin,capture_output=True)
            if r.returncode==0:head_blob=r.stdout.decode().strip()
        raw=q.read_bytes();blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        rows.append({'path':str(q.relative_to(ROOT)).replace('\\','/'),'source_path':name,'source_repository':str(origin),'source_context_head':head,'tracked':tracked,'head_blob':head_blob,'captured_git_blob':blob,'head_blob_equals_capture':blob==head_blob if head_blob else None,'size':len(raw),'sha256':digest(q),'provenance':'ORIGINAL_READ_ONLY_WORKTREE_BYTE_CAPTURE_NOT_ALL_FILES_AT_HEAD'})
    save(ROOT/'locks/high-cost-scientific-assets.json',{'schema':'high-cost-scientific-assets-v1','files':rows,'scope':'EXPLICIT_CLOSED_CAPTURE','original_workspaces_read_only':True})
    profile=write_profile()
    print(json.dumps({'assets':len(rows),'units':len(profile['units'])}))
def write_profile():
    profile={'schema':'high-cost-cases-v1','units':units(),'resource_profiles':{c:{m:limits(c,m) for m in ['ledger','preflight','live']} for c in CASE_MODULES},'general_user_conditional_compute':'BLOCKED','automatic_retry':False,'resume':False,'scientific_thresholds_changed':False,'WSLc':'BLOCKED_PAUSED','distribution':'BLOCKED_LOCAL_ONLY'}
    save(ROOT/'configs/high-cost-cases-v1.json',profile)
    return profile
def lock():
    paths=[]
    for folder in ['runtime/high_cost_cases','reference/high_cost_cases/source_tree']:
        paths.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    paths.extend((ROOT/'tests').glob('test_high_cost*.py'))
    for rel in ['configs/high-cost-cases-v1.json','locks/high-cost-scientific-assets.json','locks/high-cost-dependencies.json','scripts/run-high-cost-case.py','scripts/start-high-cost-case.ps1','scripts/list-high-cost-cases.py','scripts/prepare-high-cost-cases.py','scripts/ci-high-cost-cases.py','scripts/create-high-cost-budget.py','scripts/assemble-high-cost-results.py','container/Dockerfile.high-cost','container/Dockerfile.high-cost.dockerignore','container/Dockerfile.high-cost-dependencies','runtime/user_molecule/root_native_lifecycle.py','runtime/user_molecule/acceptance_resources.py','scripts/run-protocol-case.py']:
        paths.append(ROOT/rel)
    rows=[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':digest(p),'size':p.stat().st_size} for p in sorted(set(paths))]
    save(ROOT/'locks/high-cost-source.json',{'schema':'high-cost-source-v1','files':rows,'second_batch_files_unchanged':True})
    print(json.dumps({'locked':len(rows),'sha256':digest(ROOT/'locks/high-cost-source.json')}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['capture','profile','lock']);p.add_argument('--original',type=Path,default=Path(r'D:\AI4Science\AI4OrgChem'));a=p.parse_args()
    if a.action=='capture':capture(a.original)
    elif a.action=='profile':print(json.dumps({'units':len(write_profile()['units'])}))
    else:lock()
