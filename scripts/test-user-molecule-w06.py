"""Bounded W06 engineering tests using a clean Git export and the existing image."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile
import time
import uuid


def main():
    if not (Path(__file__).resolve().parents[1]/'tests').is_dir():
        raise SystemExit('LOCAL_TEST_SUITE_REQUIRED: tests are retained locally and excluded from the public repository; no test PASS is granted.')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root',type=Path,required=True)
    parser.add_argument('--legacy-source',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    output=args.output_root.resolve()
    if output.exists() or output==root or root in output.parents:
        raise ValueError('New evidence directory outside runtime required')
    if not args.legacy_source.is_dir():
        raise ValueError('Frozen legacy source checkout required')
    def git(*arguments):
        return subprocess.check_output(['git',*arguments],cwd=root).decode().strip()
    if git('status','--porcelain'):
        raise ValueError('Clean committed runtime required')
    output.mkdir(parents=True)
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    def save(path,value):
        path.write_bytes((json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())
    def docker(*arguments):
        command=['docker',*arguments]
        result=subprocess.run(command,capture_output=True,timeout=20)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors='replace'))
        return result.stdout.decode()
    candidate=json.loads((root/'validation/user-molecule/candidate-image.json').read_text())
    image=candidate['image_id']
    if not re.fullmatch('sha256:[0-9a-f]{64}',image):
        raise ValueError('Immutable image ID required')
    inspected=json.loads(docker('image','inspect',image))[0]
    assert inspected['Config']['Labels']['ai4orgchem.source.commit']==candidate['science_commit']
    assert inspected['Config']['Labels']['org.opencontainers.image.revision']==candidate['runtime_build_commit']
    save(output/'image-inspect.json',inspected)
    save(output/'docker-server.json',json.loads(docker('version','--format','{{json .Server}}')))
    commit=git('rev-parse','HEAD')
    archive=output/'runtime-test-source.tar'
    subprocess.run(['git','archive','--format=tar','-o',str(archive),commit],cwd=root,check=True)
    export=output/'runtime-test-source'; export.mkdir()
    with tarfile.open(archive) as source:
        source.extractall(export,filter='data')
    save(output/'test-source.json',{'runtime_test_commit':commit,'source_archive_sha256':sha(archive),
        'image_id':image,'image_runtime_build_commit':candidate['runtime_build_commit'],
        'image_science_commit':candidate['science_commit'],
        'scope':'New clean source mounted read-only over old image; not a rebuilt W06 image',
        'molecular_runs':'NOT_EXECUTED','image_build':'NOT_EXECUTED','github_actions':'NOT_EXECUTED'})
    token=uuid.uuid4().hex
    arguments=['create','--read-only','--network','none','--memory','512m','--memory-swap','512m',
        '--cpus','1','--cap-drop','ALL','--security-opt','no-new-privileges','--user','10001:10001',
        '--label','ai4orgchem.w06.engineering-run='+token,
        '--tmpfs','/tmp:rw,nosuid,nodev,size=67108864,mode=1777',
        '--mount',f'type=bind,source={export},target=/workspace,readonly',
        '--mount',f'type=bind,source={output},target=/output',
        '--mount',f'type=bind,source={args.legacy_source.resolve()},target=/legacy-source,readonly',
        '--workdir','/workspace','-e','OMP_NUM_THREADS=1','-e','OPENBLAS_NUM_THREADS=1',
        '-e','AI4ORGCHEM_TEST_SOURCE=/legacy-source','-e','AI4ORGCHEM_IMAGE_ID='+image,
        '--entrypoint','python',image,'scripts/ci-guard-w06.py']
    row={'command':['docker',*arguments],'status':'RUNNING','container_removed':False,
         'wall_seconds_limit':120,'molecular_scf':'NOT_EXECUTED'}
    save(output/'execution.json',row)
    cid=None
    try:
        cid=docker(*arguments).strip()
        if not re.fullmatch('[0-9a-f]{64}',cid):
            raise ValueError('Invalid container identity')
        row['container_id']=cid
        docker('start',cid); start=time.monotonic()
        while True:
            actual=json.loads(docker('inspect',cid))[0]
            assert actual['Config']['Labels']['ai4orgchem.w06.engineering-run']==token
            if not actual['State']['Running']:
                break
            if time.monotonic()-start>120:
                row['termination_reason']='TIMEOUT'; docker('stop','--time','2',cid)
                raise TimeoutError('W06 engineering tests')
            time.sleep(.25)
        save(output/'container-inspect.json',actual)
        row['elapsed_seconds']=time.monotonic()-start
        row['container_exit_code']=actual['State']['ExitCode']
        assert actual['State']['ExitCode']==0 and not actual['State']['OOMKilled']
        assert actual['Config']['User']=='10001:10001'
        assert actual['HostConfig']['NetworkMode']=='none' and actual['HostConfig']['ReadonlyRootfs']
        assert actual['HostConfig']['Memory']==actual['HostConfig']['MemorySwap']==536870912
        tests=json.loads((output/'w06-engineering-tests.json').read_text())
        assert tests['status']=='PASS_ENGINEERING_ONLY'
        row['status']='PASS_ENGINEERING_ONLY'
    except Exception as exc:
        row['status']='FAIL'; row['error']=str(exc)
        raise
    finally:
        if cid:
            actual=json.loads(docker('inspect',cid))[0]
            assert actual['Config']['Labels']['ai4orgchem.w06.engineering-run']==token
            if actual['State']['Running']:
                docker('stop','--time','2',cid)
            logs=subprocess.run(['docker','logs',cid],capture_output=True,timeout=20)
            (output/'stdout.log').write_bytes(logs.stdout); (output/'stderr.log').write_bytes(logs.stderr)
            docker('rm',cid); row['container_removed']=True
        save(output/'execution.json',row)
        print(json.dumps(row,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
