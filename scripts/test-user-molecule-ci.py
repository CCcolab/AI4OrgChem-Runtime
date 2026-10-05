"""Bounded local Windows/Docker CI. Reuse a pinned image; never enable scientific Compute."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import time
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--legacy-source', type=Path, required=True)
    parser.add_argument('--wheels', type=Path, required=True)
    parser.add_argument('--powershell7', type=Path, required=True)
    options = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = options.output_root.resolve()
    if output == root or root in output.parents or output.exists():
        raise ValueError('Use a new evidence directory outside the repository')
    for path in (options.legacy_source, options.wheels, options.powershell7):
        if not path.exists():
            raise FileNotFoundError(path)
    output.mkdir(parents=True)
    load = lambda path: json.loads(path.read_text(encoding='utf-8'))
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    def save(path, value):
        path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode('utf-8'))
    git = lambda *args: subprocess.check_output(['git', *args], cwd=root).decode('utf-8').strip()
    if git('status', '--porcelain'):
        raise ValueError('CI requires a clean committed runtime')
    image = load(root/'validation/user-molecule/candidate-image.json')['image_id']
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
        raise ValueError('An immutable candidate image ID is required')
    rows = []
    baseline = {'runtime_test_commit': git('rev-parse', 'HEAD'), 'image_id': image,
        'working_files_sha256': {name: sha(root/name) for name in git('ls-files').splitlines()},
        'scientific_scf': 'NOT_EXECUTED', 'github_actions': 'NOT_EXECUTED', 'build': 'NOT_EXECUTED'}
    save(output/'BASELINE.json', baseline)
    archive = output/'runtime-test-source.tar'
    subprocess.run(['git', 'archive', '--format=tar', '-o', str(archive), baseline['runtime_test_commit']], cwd=root, check=True)
    exported_root = output/'runtime-test-source'
    exported_root.mkdir()
    with tarfile.open(archive) as source:
        source.extractall(exported_root, filter='data')
    save(output/'test-source.json', {'runtime_test_commit': baseline['runtime_test_commit'],
        'archive_sha256': sha(archive), 'test_mount': str(exported_root),
        'scope': 'Clean Git export including declared per-file EOL attributes; no image rebuild'})
    def docker(*args):
        result = subprocess.run(['docker', *args], capture_output=True, timeout=20)
        if result.returncode:
            raise RuntimeError(result.stderr.decode('utf-8', errors='replace'))
        return result.stdout.decode('utf-8')
    inspect_image = json.loads(docker('image', 'inspect', image))[0]
    save(output/'image-inspect.json', inspect_image)
    save(output/'docker-version.json', json.loads(docker('version', '--format', '{{json .Server}}')))
    science_lock = load(root/'locks/source.user-molecule.lock.json')
    assert inspect_image['Config']['Labels']['ai4orgchem.source.commit'] == science_lock['source_commit']
    for name, expected in load(root/'locks/source-files.sha256.json').items():
        assert sha(options.legacy_source/name) == expected, name

    def record(row):
        rows.append(row)
        save(output/'progress.json', {'tests': rows, 'science_scf': 'NOT_EXECUTED'})
        print(row['name']+': '+row['status'], flush=True)

    def container(name, tail, extra=(), seconds=120):
        directory = output/name
        directory.mkdir()
        token = uuid.uuid4().hex
        arguments = ['create', '--read-only', '--network', 'none', '--memory', '512m',
            '--memory-swap', '512m', '--cpus', '1', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--user', '10001:10001',
            '--label', 'ai4orgchem.local-ci.run-id='+token,
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=67108864,mode=1777',
            '--mount', f'type=bind,source={exported_root},target=/workspace,readonly',
            '--mount', f'type=bind,source={directory},target=/output', '--workdir', '/workspace',
            '-e', 'OMP_NUM_THREADS=1', '-e', 'OPENBLAS_NUM_THREADS=1',
            '-e', 'USER_MOLECULE_PROFILE=/workspace/profiles/user-molecule/pilot-b3lypg-sto3g-grid2-v1.json',
            '-e', 'AI4ORGCHEM_IMAGE_ID='+image, *extra, '--entrypoint', 'python', image, *tail]
        row = {'name': name, 'command': ['docker', *arguments], 'status': 'RUNNING', 'container_removed': False}
        save(directory/'execution.json', row)
        cid = None
        try:
            cid = docker(*arguments).strip()
            assert re.fullmatch('[0-9a-f]{64}', cid)
            row['container_id'] = cid
            docker('start', cid)
            start = time.monotonic()
            while True:
                actual = json.loads(docker('inspect', cid))[0]
                assert actual['Config']['Labels']['ai4orgchem.local-ci.run-id'] == token
                if not actual['State']['Running']:
                    break
                if time.monotonic()-start > seconds:
                    row['termination_reason'] = 'TIMEOUT'
                    docker('stop', '--time', '2', cid)
                    raise TimeoutError(name)
                time.sleep(0.25)
            save(directory/'container-inspect.json', actual)
            row['container_exit_code'] = actual['State']['ExitCode']
            row['elapsed_seconds'] = time.monotonic()-start
            assert actual['Config']['User'] == '10001:10001'
            assert actual['HostConfig']['NetworkMode'] == 'none'
            assert actual['HostConfig']['ReadonlyRootfs'] is True
            assert actual['HostConfig']['Memory'] == actual['HostConfig']['MemorySwap'] == 536870912
            assert actual['State']['ExitCode'] == 0 and not actual['State']['OOMKilled'], name
            row['status'] = 'PASS'
        except Exception as exc:
            row['status'] = 'FAIL'
            row['error'] = str(exc)
            raise
        finally:
            if cid:
                actual = json.loads(docker('inspect', cid))[0]
                assert actual['Config']['Labels']['ai4orgchem.local-ci.run-id'] == token
                if actual['State']['Running']:
                    docker('stop', '--time', '2', cid)
                logs = subprocess.run(['docker', 'logs', cid], capture_output=True, timeout=20)
                (directory/'stdout.log').write_bytes(logs.stdout)
                (directory/'stderr.log').write_bytes(logs.stderr)
                docker('rm', cid)
                row['container_removed'] = True
            save(directory/'execution.json', row)
            record(row)

    minimal = """import subprocess,sys,venv
assert sys.version_info[:2]==(3,12)
venv.create('/tmp/input-ci-venv',with_pip=True)
p='/tmp/input-ci-venv/bin/python'
subprocess.run([p,'-m','pip','install','--no-index','--find-links','/ci-wheels','--only-binary=:all:',
 '--require-hashes','-r','locks/requirements-user-molecule-ci.txt'],check=True)
subprocess.run([p,'-m','pip','check'],check=True)
with open('/output/dependencies.txt','w') as stream:
 subprocess.run([p,'-m','pip','freeze'],stdout=stream,check=True)
subprocess.run([p,'-m','unittest','discover','-s','tests','-p','test_user_molecule_*.py','-v'],check=True)
"""
    container('input-resource-w05-contracts', ['-c', minimal],
        ['--mount', f'type=bind,source={options.wheels.resolve()},target=/ci-wheels,readonly'])
    container('scientific-adapter-engineering', ['-m', 'unittest', 'discover',
        '-s', '/opt/ai4orgchem/software/tests', '-p', 'test_user_molecule_adapter.py', '-v'])
    for pattern in ('test_runtime.py', 'test_process.py', 'test_classifier_adapter.py'):
        container('legacy-'+pattern.removesuffix('.py'), ['-m', 'unittest', 'discover', '-s', 'tests', '-p', pattern, '-v'],
            ['--mount', f'type=bind,source={options.legacy_source.resolve()},target=/legacy-source,readonly',
             '-e', 'AI4ORGCHEM_TEST_SOURCE=/legacy-source'])
    container('research-metadata-guard', ['scripts/ci-guard-user-molecule.py'], seconds=60)

    def host(name, command, expected=0):
        log = output/(name+'.log')
        with log.open('wb') as stream:
            actual = subprocess.run(command, cwd=root, stdout=stream, stderr=subprocess.STDOUT, timeout=120)
        row = {'name': name, 'command': command, 'expected_exit_code': expected,
               'actual_exit_code': actual.returncode, 'log': str(log),
               'status': 'PASS' if actual.returncode == expected else 'FAIL'}
        record(row)
        assert actual.returncode == expected, row

    host('powershell-ast-paths', [str(options.powershell7), '-NoProfile', '-File', str(root/'scripts/test-powershell.ps1'),
        '-OutputRoot', str(output/'powershell-paths')])
    host('platform-supervision', [str(options.powershell7), '-NoProfile', '-File', str(root/'scripts/test-user-molecule-platform.ps1'),
        '-OutputRoot', str(output/'platform'), '-Image', image, '-RuntimeRoot', str(root)])
    platform = load(output/'platform/platform-probe-summary.json')
    assert all(x['status'] == 'PASS' for x in platform['probes'])

    bootstrap = output/'bootstrap-wrapper.ps1'
    bootstrap.write_bytes(b"param([string]$RuntimeRoot,[string]$Action,[string]$Image,[string]$Request,[string]$CheckRun,[string]$RunDirectory,[string]$OutputRoot)\n"
        b"$ErrorActionPreference='Stop'; $parameters=@{Action=$Action}\n"
        b"foreach($name in @('Image','Request','CheckRun','RunDirectory','OutputRoot')){$value=Get-Variable -Name $name -ValueOnly;if($value){$parameters[$name]=$value}}\n"
        b"& (Join-Path $RuntimeRoot 'scripts/start-user-molecule.ps1') @parameters\nexit $LASTEXITCODE\n")
    ps51 = str(Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe')
    runs = output/'integration-runs'
    def action(name, action_name, expected, **parameters):
        before = set(runs.iterdir()) if runs.exists() else set()
        command = [ps51, '-NoProfile', '-File', str(bootstrap), '-RuntimeRoot', str(root),
                   '-Action', action_name, '-OutputRoot', str(runs)]
        for key, value in parameters.items():
            command += ['-'+key, str(value)]
        host(name, command, expected)
        fresh = [x for x in (set(runs.iterdir())-before) if x.name != '.inputs'] if runs.exists() else []
        if action_name == 'Report':
            assert not fresh
            return None
        assert len(fresh) == 1
        run = fresh[0]
        record_data = load(run/'host-execution.json')
        assert record_data['service_exit_code'] == expected
        for name, identity in load(run/'run-manifest.json')['files'].items():
            assert sha(run/name) == identity['sha256']
            assert (run/name).stat().st_size == identity['size_bytes']
        if record_data['container_id']:
            assert record_data['container_removed'] and record_data['container_exit_code'] == expected
            limits = record_data['observation']['limits']
            assert limits['network'] == 'none' and limits['readonly_rootfs'] and limits['user'] == '10001:10001'
        return run
    checks = []
    for fixture in load(root/'validation/user-molecule/w05/candidate-fixtures.json')['fixtures']:
        for request in fixture['requests']:
            run = action(fixture['id']+'-'+request['profile_id'], 'Check', 0, Image=image, Request=root/request['path'])
            result = load(run/'preflight.json')
            assert not result['compute_eligible']
            assert result['inspection']['nao'] == request['nao']
            assert not any(result['inspection'][key] for key in ('scf_executed','grid_built','full_eri_allocated'))
            checks.append((root/request['path'], run))
    request, check = checks[0]
    blocked = action('compute-disabled', 'Compute', 20, Image=image, Request=request, CheckRun=check)
    result = load(blocked/'result.json')
    assert result['delta_hartree'] is None and not result['comparison_available']
    assert result['numerical_status'] == 'NOT_EXECUTED'
    before = {str(p.relative_to(check)): sha(p) for p in check.rglob('*') if p.is_file()}
    action('report-read-only', 'Report', 0, RunDirectory=check)
    assert before == {str(p.relative_to(check)): sha(p) for p in check.rglob('*') if p.is_file()}
    inputs = output/'invalid-inputs'
    inputs.mkdir()
    for name, modify, expected in (
        ('unknown-field', lambda q: q.update(unrecognized_option=True), 10),
        ('host-resource-bounds', lambda q: q['resources'].update(threads=3), 10),
        ('path-escape', lambda q: q.update(geometry_file='../molecule.xyz'), 10)):
        directory = inputs/name
        directory.mkdir()
        shutil.copyfile(request.parent/'molecule.xyz', directory/'molecule.xyz')
        value = load(request)
        modify(value)
        save(directory/'request.json', value)
        run = action(name, 'Check', expected, Image=image, Request=directory/'request.json')
        if name != 'unknown-field':
            assert load(run/'host-execution.json')['container_id'] is None
    directory = inputs/'changed-geometry'
    shutil.copytree(request.parent, directory)
    xyz = directory/'molecule.xyz'
    xyz.write_bytes(xyz.read_bytes().replace(b'-0.67', b'-0.68'))
    assert sha(xyz) != sha(request.parent/'molecule.xyz')
    mismatch = action('changed-geometry', 'Compute', 20, Image=image, Request=directory/request.name, CheckRun=check)
    assert 'identity mismatch' in load(mismatch/'error.json')['message']
    counts = {}
    for name in ('input-resource-w05-contracts', 'scientific-adapter-engineering',
                 'legacy-test_runtime', 'legacy-test_process', 'legacy-test_classifier_adapter'):
        logs = (output/name/'stdout.log').read_text()+(output/name/'stderr.log').read_text()
        match = re.search(r'Ran (\d+) tests? in', logs)
        assert match, name
        counts[name] = int(match[1])
    assert not git('status', '--porcelain')
    save(output/'summary.json', {'status': 'LOCAL_CI_ENGINEERING_PASS', 'runtime_test_commit': baseline['runtime_test_commit'],
        'image_id': image, 'runtime_image_build_commit': inspect_image['Config']['Labels']['org.opencontainers.image.revision'],
        'science_commit': science_lock['source_commit'], 'unit_counts': counts, 'unit_test_total': sum(counts.values()),
        'host_integration_actions': 10, 'platform_probes': platform['probes'], 'research_metadata_guard': 'PASS', 'tests': rows,
        'github_actions': 'NOT_EXECUTED', 'new_image_build': 'NOT_EXECUTED', 'scientific_scf': 'NOT_EXECUTED',
        'W05_numerical_acceptance': 'BLOCKED / NOT_EXECUTED', 'production_compute_enabled': False,
        'publication': 'NOT_EXECUTED', 'wslc': 'BLOCKED / NOT_EXECUTED; paused'})
    print('Local CI completed: '+str(output), flush=True)


if __name__ == '__main__':
    main()
