"""Fresh zero-F preparation or one bounded twelve-call response diagnostic.

Default preparation creates no scientific callback allowance.  --execute
requires the recorded four-density zero-F readiness from identical tested source bytes.
Neither mode builds an image, retries a batch, enables Compute or publishes.
"""
import argparse
import copy
import datetime
import hashlib
import importlib.util
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
sys.path.insert(0, str(ROOT))
from runtime.user_molecule.acceptance_resources import Budget, identity_digest, qualify_exact_fixture
from runtime.user_molecule.residual_budget import reserve_single_process
from runtime.user_molecule.occupied_space_response_contract import (
    minimal_template, validate_execution_contract, validate_seed_binding, execution_identity)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as target:
        target.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def host_memory():
    spec = importlib.util.spec_from_file_location('retained_response_host_helpers', ROOT / 'scripts/diagnose-user-molecule-seed-v2.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.host_memory()


def build_contract(source, commit, seed_dir, execute):
    proposal_path = source / 'validation/user-molecule/occupied-space/response-proposal-v1.json'
    origin = copy.deepcopy(json.loads((source / 'validation/user-molecule/residual-diagnostic/contract-v1.json').read_bytes())['ordinary_origin'])
    cache = Path(origin['source_directory']).resolve()
    cache_record = json.loads((cache / origin['record_file']).read_bytes())
    for name in ('mo_coefficients', 'mo_occupations'):
        origin['array_identities'][name] = copy.deepcopy(cache_record['array_identities'][name])
    for kind in ('record', 'arrays'):
        path = cache / origin[kind + '_file']
        if path.stat().st_size != origin[kind]['size_bytes'] or sha(path) != origin[kind]['sha256']:
            raise ValueError('Frozen complete ordinary cache bytes differ: ' + kind)
    source_raw = (seed_dir / 'SOURCE.json').read_bytes()
    record_raw = (seed_dir / 'prepared-seed-family.json').read_bytes()
    arrays_raw = (seed_dir / 'prepared-seed-family.npz').read_bytes()
    contract = minimal_template(origin, source_size_bytes=len(source_raw),
        seed_record_size_bytes=len(record_raw), seed_arrays_size_bytes=len(arrays_raw))
    profile = source / 'profiles/user-molecule/pilot-b3lypg-sto3g-grid2-v1.json'
    canonical_profile = json.dumps(json.loads(profile.read_bytes()), sort_keys=True,
        separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
    contract.update(batch_id='occupied-space-response-' + uuid.uuid4().hex, created_utc=utc(),
        runtime_test_commit=commit, scientific_execution_authorized=bool(execute),
        profile_sha256=sha(profile), profile_executed_raw_sha256=sha(profile),
        profile_canonical_sha256=hashlib.sha256(canonical_profile).hexdigest(),
        source_manifest_sha256=sha(source / 'locks/source-user-molecule-files.sha256.json'),
        prior_proposal_sha256=sha(proposal_path))
    for name in contract['source_file_sha256']:
        contract['source_file_sha256'][name] = sha(source / name)
    validate_execution_contract(contract)
    # The source-array archive is also bound before reserving any process.
    source_record = json.loads(source_raw)
    source_archive = seed_dir / source_record['archive']['file']
    if source_record['archive']['file'] != 'source-arrays.npz' or source_archive.stat().st_size != source_record['archive']['size_bytes'] or sha(source_archive) != source_record['archive']['sha256']:
        raise ValueError('Actual source D/S/anchor archive differs from its frozen source record')
    validate_seed_binding(contract, source_raw, record_raw, arrays_raw, source_arrays_bytes=source_archive.read_bytes())
    return contract, cache


def verify_readiness(directory, contract):
    receipt_path = directory / 'seed-readiness.json'
    value = json.loads(receipt_path.read_bytes())
    origin = contract['seed_binding']
    if (value['status'] != 'PASS_ACTUAL_CACHED_OCCUPIED_SPACE_PREPARATION_ONLY'
            or value['runtime_test_commit'] != contract['runtime_test_commit']
            or value['source_file_sha256'] != contract['source_file_sha256']
            or value['seed_input_source_sha256'] != origin['source_record']['sha256']
            or value['seed_input_record_sha256'] != origin['seed_record']['sha256']
            or value['seed_input_archive_sha256'] != origin['seed_arrays']['sha256']
            or value['ordered_seed_density_ids'] != origin['seed_density_ids']
            or value['source_metric_matches_all_three_paths'] is not True
            or type(value['real_F_NR_SCF_grid_integral_calls']) is not int
            or value['real_F_NR_SCF_grid_integral_calls'] != 0 or value['scientific_budget'] is not None
            or value['scientific_callback_reservation_created'] is not False
            or value['scientific_execution'] != 'NOT_EXECUTED' or value['Compute'] is not False
            or value['method_approval'] is not False
            or value['forbidden_attempts'] or value['changed_guard_bindings']):
        raise ValueError('Actual zero-F preparation did not pass for identical tested source/input')
    expected_counter_keys = {'nr_rks_attempts', 'nr_rks_completed', 'nr_rks_failed',
        'energy_nuc_attempts', 'energy_nuc_completed', 'energy_nuc_failed'}
    if (set(value['native_counts']) != set(contract['paths'])
            or any(set(row) != expected_counter_keys for row in value['native_counts'].values())
            or any(type(number) is not int or number != 0 for row in value['native_counts'].values() for number in row.values())):
        raise ValueError('Zero-F readiness contains native calls')
    parent = directory.parent
    execute_path, prior_path, inspect_path = parent / 'EXECUTION.json', parent / 'execution-contract.json', parent / 'container-inspect.json'
    prior = json.loads(prior_path.read_bytes())
    validate_execution_contract(prior)
    actual = json.loads(execute_path.read_bytes())
    inspect = json.loads(inspect_path.read_bytes())
    flags = inspect['HostConfig']
    readonly = {mount['Destination'] for mount in inspect['Mounts'] if mount['RW'] is False}
    if (prior['scientific_execution_authorized'] is not False
            or prior['runtime_test_commit'] != contract['runtime_test_commit']
            or prior['source_file_sha256'] != contract['source_file_sha256']
            or prior['seed_binding'] != contract['seed_binding']
            or value['contract_sha256'] != sha(prior_path)
            or actual['status'] != 'EXECUTED_WITHIN_DECLARED_SCOPE'
            or actual['mode'] != 'ZERO_F_PREPARATION'
            or actual['container_removed'] is not True or actual['platform_flags_verified'] is not True
            or actual['container_exit_code'] != 0 or actual['oom_killed'] is not False
            or inspect['State']['Running'] is not False or inspect['State']['ExitCode'] != 0
            or inspect['State']['OOMKilled'] is not False
            or inspect['Id'] != actual['container_id'] or inspect['Image'] != contract['image_id']
            or inspect['Config']['User'] != '10001:10001'
            or flags['ReadonlyRootfs'] is not True or flags['NetworkMode'] != 'none'
            or flags['Memory'] != 1073741824 or flags['MemorySwap'] != 1073741824 or flags['NanoCpus'] != 1000000000
            or not {'/workspace', '/saved-ordinary', '/seed-input', '/execution-contract.json'} <= readonly):
        raise ValueError('Zero-F readiness is not backed by the matching completed, isolated and removed preparation container')
    return {'receipt': str(receipt_path), 'sha256': sha(receipt_path),
        'preparation_execution_sha256': sha(execute_path), 'preparation_contract_sha256': sha(prior_path),
        'preparation_container_inspect_sha256': sha(inspect_path),
        'scope': 'ACTUAL_CACHED_PREPARATION_ONLY_NOT_ENDPOINT_OR_AUTHENTICATION'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--seed-input-dir', type=Path, required=True)
    parser.add_argument('--readiness-dir', type=Path)
    parser.add_argument('--execute', action='store_true', help='One new twelve-call diagnostic after zero-F readiness; no SCF')
    parser.add_argument('--docker', default=r'C:\Program Files\Docker\Docker\resources\bin\docker.exe')
    args = parser.parse_args()
    output, seed_dir = args.output_root.resolve(), args.seed_input_dir.resolve()
    if output.exists() or output == ROOT or output.is_relative_to(ROOT) or output.is_relative_to(seed_dir):
        raise ValueError('Fresh external output root required; no overwrite of source or old probe evidence')
    def git(*values):
        return subprocess.check_output(['git', *values], cwd=ROOT)
    if git('status', '--porcelain').strip():
        raise ValueError('Clean committed runtime required')
    commit = git('rev-parse', 'HEAD').decode().strip()
    output.mkdir(parents=True)
    commands = []
    def docker(*values, timeout=15):
        result = subprocess.run([args.docker, *values], capture_output=True, timeout=timeout)
        commands.append({'arguments': [args.docker, *values], 'exit_code': result.returncode,
                         'observed_at_utc': utc(), 'stderr': result.stderr.decode('utf-8', errors='replace')})
        if result.returncode:
            raise RuntimeError(commands[-1]['stderr'])
        return result.stdout
    candidate = json.loads((ROOT / 'validation/user-molecule/candidate-image.json').read_bytes())
    image = json.loads(docker('image', 'inspect', candidate['image_id']))[0]
    labels = image['Config']['Labels']
    if (image['Id'] != candidate['image_id'] or labels['org.opencontainers.image.revision'] != candidate['runtime_build_commit']
            or labels['ai4orgchem.source.commit'] != candidate['science_commit']):
        raise ValueError('Existing immutable image lineage differs')
    save(output / 'image-inspect.json', image)
    save(output / 'engine-version.json', json.loads(docker('version', '--format', '{{json .Server}}')))
    info = json.loads(docker('info', '--format', '{{json .}}'))
    save(output / 'engine-resources.json', {key: info.get(key) for key in ('MemTotal', 'NCPU', 'ContainersRunning', 'CgroupVersion', 'KernelVersion')})
    host = host_memory()
    save(output / 'host-admission.json', host)
    if host['status'] != 'ADMITTED_HOST_ONLY' or info['MemTotal'] < 2147483648 or info['ContainersRunning']:
        save(output / 'admission.json', {'status': 'NOT_EXECUTED_DUE_TO_HOST_OR_ENGINE_ADMISSION', 'new_F': 0})
        save(output / 'commands.json', commands)
        return 20
    archive = output / 'runtime-source.tar'
    subprocess.run(['git', 'archive', '--format=tar', '-o', str(archive), commit], cwd=ROOT, check=True)
    source = output / 'runtime-source'
    source.mkdir()
    with tarfile.open(archive) as saved:
        saved.extractall(source, filter='data')
    verified = []
    for name in git('ls-tree', '-r', '--name-only', commit).decode().splitlines():
        blob, actual = git('show', commit + ':' + name), (source / name).read_bytes()
        transformation = 'EXACT_GIT_BLOB'
        if actual != blob:
            if not name.endswith('.ps1') or actual != blob.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'):
                raise ValueError('Source export differs from Git blob: ' + name)
            transformation = 'EXACT_LF_TO_CRLF_PS1_EXPORT'
        verified.append({'path': name, 'git_blob_sha256': hashlib.sha256(blob).hexdigest(),
                         'export_sha256': sha(source / name), 'verification': transformation})
    save(output / 'source-export-verification.json', {'commit': commit, 'file_count': len(verified), 'files': verified})
    contract, cache = build_contract(source, commit, seed_dir, args.execute)
    if args.execute:
        if args.readiness_dir is None:
            raise ValueError('--execute requires an actual zero-F readiness directory')
        save(output / 'readiness-source-binding.json', verify_readiness(args.readiness_dir.resolve(), contract))
    contract_path = output / 'execution-contract.json'
    save(contract_path, contract)
    identity = execution_identity(contract, sha(contract_path))
    save(output / 'source-identity.json', dict(identity, source_archive_sha256=sha(archive),
        worker_sha256=sha(source / 'scripts/diagnose-user-molecule-occupied-space-response-worker.py')))
    budget = Budget(output / ('SCIENTIFIC_WALL_BUDGET.json' if args.execute else 'ENGINEERING_WALL_BUDGET.json'),
        contract['batch_id'], total_seconds=120, max_process_seconds=120, memory_limit_mib=1024, threads=1)
    save(output / 'WALL_RESERVATION.json', reserve_single_process(budget, run_id='single-response-process', identity=identity))
    leaf = output / 'output'
    leaf.mkdir()
    token, cid, completed = uuid.uuid4().hex, None, None
    started = time.monotonic()
    execution = {'status': 'RUNNING', 'started_at_utc': utc(), 'identity': identity,
        'mode': 'SCIENTIFIC_OCCUPIED_SPACE_SINGLE_RESPONSE' if args.execute else 'ZERO_F_PREPARATION',
        'automatic_retry': False, 'container_removed': False, 'wall_limit_seconds': 120,
        'stop_deadline_seconds': 95, 'cleanup_headroom_seconds': 25,
        'max_new_scientific_F_calls': 12 if args.execute else 0}
    settled = None
    try:
        launch = ['create', '--read-only', '--network', 'none', '--memory', '1024m', '--memory-swap', '1024m', '--cpus', '1',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--user', '10001:10001',
            '--label', 'ai4orgchem.occupied-space-response=' + token, '--tmpfs', '/tmp:rw,nosuid,nodev,size=67108864,mode=1777',
            '--mount', f'type=bind,source={source},target=/workspace,readonly',
            '--mount', f'type=bind,source={leaf},target=/output',
            '--mount', f'type=bind,source={cache},target=/saved-ordinary,readonly',
            '--mount', f'type=bind,source={seed_dir},target=/seed-input,readonly',
            '--mount', f'type=bind,source={contract_path},target=/execution-contract.json,readonly',
            '--workdir', '/workspace', '-e', 'PYTHONDONTWRITEBYTECODE=1', '-e', 'OMP_NUM_THREADS=1',
            '-e', 'OPENBLAS_NUM_THREADS=1', '-e', 'MKL_NUM_THREADS=1', '-e', 'AI4ORGCHEM_SOURCE_ROOT=/opt/ai4orgchem',
            '-e', 'AI4ORGCHEM_RUNTIME_TEST_COMMIT=' + commit, '-e', 'AI4ORGCHEM_IMAGE_ID=' + candidate['image_id'],
            '-e', 'AI4ORGCHEM_IMAGE_BUILD_COMMIT=' + candidate['runtime_build_commit'], '--entrypoint', 'python',
            candidate['image_id'], '-B', '/workspace/scripts/diagnose-user-molecule-occupied-space-response-worker.py']
        if not args.execute:
            launch.append('--prepare-only')
        save(output / 'launch-command.json', [args.docker, *launch])
        cid = docker(*launch).decode().strip()
        if re.fullmatch('[0-9a-f]{64}', cid) is None:
            raise ValueError('Invalid owned response container ID')
        execution['container_id'] = cid
        docker('start', cid)
        next_progress = 0
        while True:
            actual = json.loads(docker('inspect', cid))[0]
            if actual['Config']['Labels'].get('ai4orgchem.occupied-space-response') != token:
                raise ValueError('Response ownership mismatch')
            if not actual['State']['Running']:
                break
            elapsed = time.monotonic() - started
            if elapsed > 95:
                docker('stop', '--time', '2', cid)
                execution['termination_reason'] = 'WALL_STOP_NO_RETRY'
                break
            if elapsed >= next_progress:
                print(json.dumps({'phase': execution['mode'], 'elapsed_seconds': elapsed}), flush=True)
                next_progress = elapsed + 20
            time.sleep(.25)
        completed = json.loads(docker('inspect', cid))[0]
        save(output / 'container-inspect.json', completed)
        flags = completed['HostConfig']
        readonly = {mount['Destination'] for mount in completed['Mounts'] if mount['RW'] is False}
        safe = (completed['Image'] == candidate['image_id'] and completed['Config']['User'] == '10001:10001'
            and flags['ReadonlyRootfs'] and flags['NetworkMode'] == 'none'
            and flags['Memory'] == flags['MemorySwap'] == 1073741824 and flags['NanoCpus'] == 1000000000
            and {'/workspace', '/saved-ordinary', '/seed-input', '/execution-contract.json'} <= readonly)
        execution.update(container_exit_code=completed['State']['ExitCode'], oom_killed=completed['State']['OOMKilled'],
                         platform_flags_verified=safe)
        expected = leaf / ('response-summary.json' if args.execute else 'seed-readiness.json')
        execution['expected_result_available'] = expected.exists()
        execution['status'] = 'EXECUTED_WITHIN_DECLARED_SCOPE' if safe and expected.exists() and completed['State']['ExitCode'] == 0 and not completed['State']['OOMKilled'] else 'FAILED_OR_REFUSED_NO_RETRY'
    except BaseException as error:
        execution.update(status='FAILED_NO_RETRY', exception_type=type(error).__name__, error=str(error))
    finally:
        try:
            if cid:
                actual = json.loads(docker('inspect', cid))[0]
                if actual['Config']['Labels'].get('ai4orgchem.occupied-space-response') != token:
                    raise ValueError('Cleanup ownership mismatch')
                if actual['State']['Running']:
                    docker('stop', '--time', '2', cid)
                completed = json.loads(docker('inspect', cid))[0]
                if not (output / 'container-inspect.json').exists():
                    save(output / 'container-inspect.json', completed)
                logs = subprocess.run([args.docker, 'logs', cid], capture_output=True, timeout=10)
                (output / 'stdout.log').write_bytes(logs.stdout)
                (output / 'stderr.log').write_bytes(logs.stderr)
                execution['logs_exit_code'] = logs.returncode
                execution['container_removed'] = docker('rm', cid).decode().strip() == cid
        finally:
            execution['wall_through_cleanup_seconds'] = time.monotonic() - started
            if cid is None or execution['container_removed']:
                settled = budget.settle('single-response-process', execution['wall_through_cleanup_seconds'], execution['status'],
                    {'container_removed': execution['container_removed'], 'container_exit_code': None if completed is None else completed['State']['ExitCode']})
            else:
                settled = budget.snapshot()
                execution['status'] = 'CLEANUP_UNRESOLVED_FULL_RESERVATION_NO_RETRY'
            if settled['over_budget']:
                execution['status'] = 'FAILED_WALL_BUDGET_NO_RETRY'
            save(output / 'WALL_SETTLEMENT.json', settled)
            save(output / 'EXECUTION.json', execution)
            save(output / 'commands.json', commands)
    if completed is not None:
        rows = [json.loads(line)['cgroup'] for line in (leaf / 'resources.jsonl').read_text().splitlines()] if (leaf / 'resources.jsonl').exists() else []
        external = {'source': 'DOCKER_INSPECT', 'container_id': cid, 'oom_killed': completed['State']['OOMKilled'],
            'evidence_sha256': sha(output / 'container-inspect.json'), 'state_finished_at': completed['State']['FinishedAt'],
            'resource_identity_sha256': identity_digest(identity)}
        resource = qualify_exact_fixture(identity, 14, rows, memory_limit_mib=1024, threads=1, external_oom_evidence=external)
        if not execution['container_removed'] or execution.get('logs_exit_code') != 0 or settled['over_budget']:
            resource['status'] = 'BLOCKED'
            resource['reasons'].append('CLEANUP_LOG_COLLECTION_OR_WALL_FAILED')
        save(output / 'resource-qualification.json', resource)
        save(output / 'output-retention.json', {'container_removed': execution['container_removed'],
            'retained_files': sum(path.is_file() for path in leaf.rglob('*')), 'output_directory': str(leaf)})
    print(json.dumps(execution, ensure_ascii=False), flush=True)
    return 0 if execution['status'] == 'EXECUTED_WITHIN_DECLARED_SCOPE' else 1


if __name__ == '__main__':
    raise SystemExit(main())
