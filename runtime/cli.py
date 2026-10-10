"""Traceable task execution with explicit outputs and no frozen-result fallback."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from runtime.resources import memory_snapshot, require_memory, thread_limit

ROOT = Path(__file__).resolve().parents[1]
TASKS = {
    'evidence': None, 'core-tests': None,
    'p14-smoke': ('run_p14_benzotricyclobutadiene_smoke.py', 'smoke_gate_verdict'),
    'p14-equivalence': ('validate_p14_memory_controlled_conditional_scf.py', 'verdict'),
    'p14-fixed': ('run_p14_benzotricyclobutadiene_source_level_fixed_geometry.py', 'anchor_gate_verdict'),
    'p14-optimize': ('run_p14_benzotricyclobutadiene_production_optimization.py', 'production_gate_verdict'),
    'p14-classify': ('classify_p14_strained_aromatic_pi_distortivity.py', 'decision_verdict'),
}
PROTOCOL = 'configs/qm/p14_strained_aromatic_pi_distortivity_v0.1.yaml'
CLASSES = 'configs/qm/p09_exchange_integral_classes_v0.1.yaml'
PUBLIC_INPUTS = ['evidence/P01-P14/P14/inputs/source_proxy_G.xyz', 'evidence/P01-P14/P14/inputs/source_proxy_PLG.xyz']
# A completed child process can still fail the task's required scientific gate.
QUALIFICATION_EXIT_CODE = 4


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'duplicate JSON key {key}')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique)


def save(path, record):
    temporary = Path(str(path) + '.tmp')
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    temporary.replace(path)


def dependencies():
    return {r['name']: importlib.metadata.version(r['name']) for r in load(ROOT / 'locks/wheels.lock.json')['wheels']}


def runtime_snapshot():
    rows = {}
    for directory in ('runtime', 'scripts', 'container', 'locks'):
        for path in sorted((ROOT / directory).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                rows[path.relative_to(ROOT).as_posix()] = digest(path)
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def verify_source(source):
    expected = load(ROOT / 'locks/source-files.sha256.json')
    actual = {p.relative_to(source).as_posix(): p for p in source.rglob('*') if p.is_file() and '.git' not in p.relative_to(source).parts}
    if set(actual) != set(expected):
        raise ValueError('source file set differs from fixed archive (including unwanted caches)')
    for name, value in expected.items():
        if digest(actual[name]) != value:
            raise ValueError(f'source file hash mismatch: {name}')
    return expected


@contextlib.contextmanager
def host_lock(root):
    if root is None:
        raise ValueError('high-memory task requires a shared --lock-root; use the same root across this host')
    import fcntl
    root.mkdir(parents=True, exist_ok=True)
    with (root / 'quantum.lock').open('a+') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('another runtime quantum task holds the shared host lock') from None
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def validated_input(run, task, identity, inputs, versions):
    run = run.resolve()
    manifest = load(run / 'run-manifest.json')
    if manifest.get('task') != task or manifest.get('status') != 'PASS' or manifest.get('process_exit_code') != 0:
        raise ValueError(f'{task}: input run did not pass')
    for key, expected in [('source_commit', identity), ('input_sha256', inputs), ('dependencies', versions)]:
        if manifest.get(key) != expected:
            raise ValueError(f'{task}: incompatible {key}')
    result = run / 'result.json'
    if manifest.get('output_sha256', {}).get('result.json') != digest(result):
        raise ValueError(f'{task}: result hash mismatch')
    record = load(result)
    if record.get('protocol_id') != 'p14-strained-aromatic-pi-distortivity/0.1' or record.get('proposition_id') != 'P14':
        raise ValueError(f'{task}: incompatible scientific protocol')
    return result, manifest['run_id']


def commands(args, run, identity, inputs, versions):
    scripts = args.source / 'software/scripts'
    if args.task == 'evidence':
        return [[sys.executable, str(scripts / name)] for name in (
            'validate_public_evidence.py', 'validate_p12_evidence.py',
            'validate_evidence_navigation.py', 'validate_p14_evidence.py')], []
    if args.task == 'core-tests':
        return [[sys.executable, '-m', 'pytest', '-p', 'no:cacheprovider', '--import-mode=importlib',
                 *[str(args.source / 'software/tests' / f'test_p09_{part}.py') for part in ('conditional_scf', 'energy_assembly', 'eri_mask')]]], []
    base = [sys.executable, str(scripts / TASKS[args.task][0]), '--protocol', str(args.source / PROTOCOL),
            '--output', str(run / 'result.json'), '--report', str(run / 'report.md')]
    parents = []
    if args.task == 'p14-classify':
        view = run / 'classifier-view'
        view.mkdir()
        for name in ('configs', 'evidence'):
            (view / name).symlink_to(args.source / name, target_is_directory=True)
        staged = []
        for option, task, input_run in [('smoke', 'p14-smoke', args.smoke_run),
                                      ('optimization', 'p14-optimize', args.optimization_run),
                                      ('equivalence', 'p14-equivalence', args.equivalence_run),
                                      ('source-level', 'p14-fixed', args.source_level_run)]:
            if input_run is None:
                raise ValueError(f'classifier requires --{option}-run; frozen defaults are forbidden')
            result, run_id = validated_input(input_run, task, identity, inputs, versions)
            target = view / f'{option}.json'
            shutil.copyfile(result, target)
            staged.extend([f'--{option}', str(target)])
            parents.append({'task': task, 'run_id': run_id, 'sha256': digest(target)})
        base = [sys.executable, str(ROOT / 'runtime/classify.py'), '--source', str(args.source),
                '--view', str(view), *base[2:], *staged]
    else:
        base.extend(['--classes', str(args.source / CLASSES)])
        if args.task in ('p14-fixed', 'p14-optimize'):
            base.extend(['--checkpoint', str(run / 'checkpoint.json')])
    return [base], parents


def execute(command, env, work, run, index):
    with (run / f'{index:02d}-stdout.log').open('wb') as out, (run / f'{index:02d}-stderr.log').open('wb') as err:
        child = subprocess.Popen(command, env=env, cwd=work, stdout=out, stderr=err, start_new_session=True)
        try:
            return child.wait()
        except (KeyboardInterrupt, SystemExit):
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
            raise


def run_task(args):
    if platform.system() != 'Linux':
        raise ValueError('task execution requires Linux; Windows uses the PowerShell launcher')
    args.source = args.source.resolve()
    args.output_root = args.output_root.resolve()
    if args.output_root.is_relative_to(args.source) or args.source.is_relative_to(args.output_root):
        raise ValueError('output and source directories must be separate')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + args.task + '-' + uuid.uuid4().hex[:12]
    run = args.output_root / run_id
    run.mkdir(parents=True, exist_ok=False)
    identity = load(ROOT / 'locks/source.lock.json')['source_commit']
    record = {'schema_version': 1, 'run_id': run_id, 'task': args.task, 'source_commit': identity,
              'runtime_commit': os.environ.get('AI4ORGCHEM_RUNTIME_COMMIT', 'UNKNOWN'),
              'runtime_code_sha256': runtime_snapshot(),
              'image_digest': os.environ.get('AI4ORGCHEM_IMAGE_DIGEST', 'UNKNOWN'),
              'image_id': os.environ.get('AI4ORGCHEM_IMAGE_ID', 'UNKNOWN'),
              'platform': platform.system() + '/' + platform.machine(), 'python': platform.python_version(),
              'status': 'RUNNING', 'process_exit_code': 'UNKNOWN', 'subprocess_exit_code': 'UNKNOWN',
              'numerical_qualification': 'NOT_APPLICABLE',
              'scientific_comparison': 'NOT_APPLICABLE', 'started_utc': datetime.now(timezone.utc).isoformat(),
              'output_sha256': {}, 'commands': [], 'resource_peak': 'UNKNOWN'}
    manifest = run / 'run-manifest.json'
    save(manifest, record)
    started = time.perf_counter()
    code = 2
    try:
        versions = dependencies()
        for wheel in load(ROOT / 'locks/wheels.lock.json')['wheels']:
            if versions[wheel['name']] != wheel['version']:
                raise ValueError(f"dependency version mismatch: {wheel['name']}")
        if sys.version_info[:2] != (3, 12):
            raise ValueError('requires Python 3.12')
        hashes = verify_source(args.source)
        inputs = {name: hashes[name] for name in [PROTOCOL, CLASSES, *PUBLIC_INPUTS]}
        threads = thread_limit(args.threads)
        record.update(dependencies=versions, input_sha256=inputs, threads=threads,
                      dependency_lock_sha256=digest(ROOT / 'locks/requirements-linux-amd64.txt'),
                      memory=memory_snapshot(), source_readonly=not os.access(args.source / 'evidence', os.W_OK))
        require_memory(args.task, record['memory'])
        command_list, parents = commands(args, run, identity, inputs, versions)
        record.update(commands=command_list, parent_runs=parents)
        save(manifest, record)
        env = os.environ.copy()
        for name in ('PYTEST_ADDOPTS', 'PYTEST_PLUGINS', 'PYTHONSTARTUP'):
            env.pop(name, None)
        env.update(PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(args.source / 'software/src'))
        for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS'):
            env[name] = str(threads)
        env['OMP_MAX_ACTIVE_LEVELS'] = '1'
        # Scratch remains on Linux, while checkpoint/output args are persistent.
        with tempfile.TemporaryDirectory(prefix='ai4orgchem-') as work:
            env.update(TMPDIR=work, PYSCF_TMPDIR=work, HOME=work, XDG_CACHE_HOME=work)
            lock = host_lock(args.lock_root) if args.task in ('p14-smoke', 'p14-equivalence', 'p14-fixed', 'p14-optimize') else contextlib.nullcontext()
            with lock:
                code = 0
                for index, command in enumerate(command_list):
                    code = execute(command, env, work, run, index)
                    if code != 0:
                        break
        record['process_exit_code'] = code
        record['subprocess_exit_code'] = code
        record['status'] = 'PASS' if code == 0 else 'FAIL'
        task_definition = TASKS[args.task]
        if task_definition is not None:
            # A missing result or gate cannot satisfy a scientific task. Tasks
            # without a gate (evidence/core-tests) retain NOT_APPLICABLE.
            gate = 'UNKNOWN'
            if (run / 'result.json').exists():
                result = load(run / 'result.json')
                gate = result.get(task_definition[1], 'UNKNOWN')
                record['scientific_comparison'] = result.get('classification', 'NOT_APPLICABLE')
                record['quantitative_evidence'] = result.get('quantitative_evidence', {})
                if 'peak_rss_mib' in result:
                    record['resource_peak'] = {'peak_rss_mib': result['peak_rss_mib']}
            record['numerical_qualification'] = gate
            if code == 0 and gate != 'PASS':
                record['status'] = 'FAIL'
                code = QUALIFICATION_EXIT_CODE
        if verify_source(args.source) != hashes:
            raise ValueError('source changed during execution')
    except MemoryError as exc:
        record.update(status='BLOCKED', error=str(exc))
        code = 3
    except (KeyboardInterrupt, SystemExit) as exc:
        record.update(status='FAIL', error='interrupted; persistent checkpoint retained if already written')
        code = exc.code if isinstance(exc, SystemExit) and isinstance(exc.code, int) else 130
    except Exception as exc:
        record.update(status='FAIL', error=str(exc))
        code = 2
    finally:
        record['wall_time_seconds'] = time.perf_counter() - started
        record['finished_utc'] = datetime.now(timezone.utc).isoformat()
        record['runtime_exit_code'] = code
        record['output_sha256'] = {p.relative_to(run).as_posix(): digest(p) for p in run.rglob('*')
                                   if p.is_file() and p != manifest and 'classifier-view' not in p.relative_to(run).parts}
        save(manifest, record)
    print(json.dumps({'run_id': run_id, 'status': record['status'], 'manifest': str(manifest), 'runtime_exit_code': code}))
    return code


def main():
    parser = argparse.ArgumentParser(prog='runtime')
    sub = parser.add_subparsers(dest='action', required=True)
    run = sub.add_parser('run')
    run.add_argument('task', choices=TASKS)
    run.add_argument('--source', type=Path, default=Path('/opt/ai4orgchem'))
    run.add_argument('--output-root', type=Path, default=Path('/work'))
    run.add_argument('--threads', type=int, default=8)
    run.add_argument('--lock-root', type=Path)
    for key in ('smoke', 'optimization', 'equivalence', 'source-level'):
        run.add_argument(f'--{key}-run', type=Path)
    args = parser.parse_args()
    def terminate(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, terminate)
    return run_task(args)


if __name__ == '__main__':
    raise SystemExit(main())
