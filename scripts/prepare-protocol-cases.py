"""Capture an explicit scientific byte closure; never clean or execute origins."""
from __future__ import annotations
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from runtime.protocol_cases import CASE_MODULES,ASSETS,digest,save

def git(origin,*args):
    p=subprocess.run(['git',*args],cwd=origin,capture_output=True,timeout=60)
    if p.returncode: raise RuntimeError(p.stderr.decode('utf-8','replace'))
    return p.stdout

def capture(original,public):
    files=set()
    for name in set(CASE_MODULES.values()):
        files.update(importlib.import_module('runtime.protocol_cases.'+name).assets())
    files.update(('LICENSE','NOTICE'))
    records=[]
    for relative in sorted(files):
        source=original/relative; provenance='ORIGINAL_READ_ONLY_WORKTREE_BYTES'
        if relative.startswith('src/ai4orgchem/qm/'):
            source=public/'software'/relative; provenance='FROZEN_PUBLIC_SCIENCE_BYTES'
        if relative=='data/processed/p07_lfmo_core_integrated_mechanism_v0.1.json':
            # Public form explicitly declares derived/non-independent evidence.
            alternate=public/'evidence/P01-P14/P07/result.json'
            if alternate.is_file(): source=alternate;provenance='FROZEN_PUBLIC_DERIVED_EVIDENCE'
        if not source.is_file():
            if relative=='NOTICE': continue
            raise ValueError('Missing explicit source asset: '+str(source))
        target=ASSETS/relative; target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists() and target.read_bytes()!=source.read_bytes() and relative!='data/processed/p07_lfmo_core_integrated_mechanism_v0.1.json':
            raise ValueError('Existing capture differs: '+relative)
        shutil.copyfile(source,target)
        origin=public if source.is_relative_to(public) else original
        origin_relative=str(source.relative_to(origin)).replace('\\','/')
        tracked=subprocess.run(['git','ls-files','--error-unmatch','--',origin_relative],cwd=origin,capture_output=True).returncode==0
        blob=None
        if tracked:
            result=subprocess.run(['git','rev-parse','HEAD:'+origin_relative],cwd=origin,capture_output=True)
            if result.returncode==0: blob=result.stdout.decode().strip()
        records.append({'path':str(target.relative_to(ROOT)).replace('\\','/'),'sha256':digest(target),'size':target.stat().st_size,
                        'source_repository':str(origin),'source_path':origin_relative,'source_context_head':git(origin,'rev-parse','HEAD').decode().strip(),
                        'tracked':tracked,'head_blob':blob,'captured_git_blob':hashlib.sha1(b'blob '+str(target.stat().st_size).encode()+b'\0'+target.read_bytes()).hexdigest(),
                        'provenance':provenance,'head_is_context_not_claim_all_files_at_head':True})
    (ROOT/'locks').mkdir(exist_ok=True)
    save(ROOT/'locks/protocol-cases-scientific-assets.json',{'schema':'protocol-case-assets-v1','files':records,
        'scope':'EXPLICIT_BYTE_CAPTURE_NOT_DIRTY_REPOSITORY_AS_DEPENDENCY','scientific_sources_unmodified':True})
    print(json.dumps({'captured_assets':len(records),'bytes':sum(r['size'] for r in records)}))

def lock():
    paths=[]
    for folder in ('runtime/protocol_cases','reference/protocol_cases/source_tree'):
        paths += [p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    paths += list((ROOT/'tests').glob('test_protocol_cases*.py'))
    for name in ('configs/protocol-cases-v1.json','locks/protocol-cases-scientific-assets.json',
                 'locks/protocol-cases-dependencies.json','scripts/run-protocol-case.py','scripts/start-protocol-case.ps1',
                 'container/Dockerfile.protocol-cases','container/Dockerfile.protocol-cases.dockerignore',
                 'scripts/ci-protocol-cases.py','scripts/list-protocol-cases.py',
                 'runtime/user_molecule/root_native_lifecycle.py','runtime/user_molecule/acceptance_resources.py'):
        paths.append(ROOT/name)
    rows=[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':digest(p),'size':p.stat().st_size} for p in sorted(set(paths))]
    save(ROOT/'locks/protocol-cases-source.json',{'schema':'protocol-case-runtime-source-v1','files':rows,
                                               'previous_profiles_and_locks_unchanged':True})
    print(json.dumps({'locked_files':len(rows),'lock_sha256':digest(ROOT/'locks/protocol-cases-source.json')}))

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=('capture','lock'))
    p.add_argument('--original',type=Path,default=Path(r'D:\AI4Science\AI4OrgChem'))
    p.add_argument('--public',type=Path,default=ROOT.parent/'science');a=p.parse_args()
    capture(a.original,a.public) if a.action=='capture' else lock()
if __name__=='__main__':main()
