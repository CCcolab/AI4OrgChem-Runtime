"""Linux CI public-source installation and file-I/O probes; zero science calls.

This job builds local-only images from the public pinned installation chain.
It registers four identities and checks non-root/read-only/offline execution,
Linux bind permissions, process exit propagation and output persistence. It
does not run any molecular or high-cost worker, or inherit numeric acceptance.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid


ROOT = Path(__file__).resolve().parents[1]


def saved(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as out:
        out.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+'\n')


def run(command, directory, name, *, cwd=None, expected=0, timeout=1800):
    command = list(map(str, command))
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        (directory/(name+'.stdout.log')).write_bytes(exc.stdout or b'')
        (directory/(name+'.stderr.log')).write_bytes(exc.stderr or b'')
        saved(directory/(name+'.command.json'), {'command': command, 'cwd': str(cwd) if cwd else None,
              'exit_code': None, 'status': 'TIMEOUT_IDENTITY_UNKNOWN', 'timeout_seconds': timeout,
              'expected_exit_code': expected})
        raise
    (directory/(name+'.stdout.log')).write_bytes(result.stdout)
    (directory/(name+'.stderr.log')).write_bytes(result.stderr)
    saved(directory/(name+'.command.json'), {'command': command, 'cwd': str(cwd) if cwd else None,
                                           'exit_code': result.returncode, 'expected_exit_code': expected})
    if expected is not None and result.returncode != expected:
        raise ValueError(name+' exit code differs: '+str(result.returncode))
    return result


def docker_probe(image, destination, name, *, writable):
    """Fixed Python stdlib file probe; ownership is rechecked before deletion."""
    cid = None
    owner = 'installation-ci-'+uuid.uuid4().hex
    label = 'ai4orgchem.installation.ci-owner'
    program = """import errno,json,os,pathlib,sys
assert os.geteuid()==10001
try:
 pathlib.Path('/opt/runtime/__ci_forbidden_write').write_text('forbidden')
except OSError as exc:
 if exc.errno not in (errno.EACCES,errno.EPERM,errno.EROFS): raise
else:
 raise RuntimeError('source was writable')
try:
 pathlib.Path('/out/persisted.json').write_text(json.dumps({'uid':os.geteuid(),'science_calls':0}))
except PermissionError:
 print('BIND_PERMISSION_REFUSED'); sys.exit(19)
print('BIND_WRITABLE'); sys.exit(23)
"""
    command = ['docker', 'create', '--name', owner, '--label', label+'='+owner,
               '--network', 'none', '--read-only', '--user', '10001:10001',
               '--memory', '134217728', '--memory-swap', '134217728', '--cpus', '1',
               '--pids-limit', '64', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
               '--mount', 'type=bind,source='+str(destination)+',target=/out',
               '--entrypoint', '/opt/venv/bin/python', image, '-B', '-c', program]
    try:
        result = run(command, destination.parent, name+'-create', timeout=30)
        cid = result.stdout.decode('ascii').strip()
        if len(cid) != 64 or any(c not in '0123456789abcdef' for c in cid):
            raise ValueError('Complete probe container ID required')
        run(['docker', 'start', '--attach', cid], destination.parent, name+'-start',
            expected=23 if writable else 19, timeout=30)
        inspection = json.loads(run(['docker', 'inspect', cid], destination.parent, name+'-inspect', timeout=15).stdout)[0]
        host = inspection['HostConfig']
        if inspection['Config']['User'] != '10001:10001' or host['NetworkMode'] != 'none' or not host['ReadonlyRootfs']:
            raise ValueError('Probe confinement differs')
        if inspection['State']['Running'] or inspection['State']['ExitCode'] != (23 if writable else 19):
            raise ValueError('Actual probe process exit differs')
    finally:
        inspect_command = ['docker', 'inspect', cid or owner]
        try:
            inspected = subprocess.run(inspect_command, capture_output=True, timeout=15)
        except subprocess.TimeoutExpired as exc:
            (destination.parent/(name+'-cleanup-inspect.stdout.log')).write_bytes(exc.stdout or b'')
            (destination.parent/(name+'-cleanup-inspect.stderr.log')).write_bytes(exc.stderr or b'')
            saved(destination.parent/(name+'-cleanup-inspect.command.json'), {'command': inspect_command,
                  'exit_code': None, 'status': 'TIMEOUT_IDENTITY_UNKNOWN'})
            raise
        (destination.parent/(name+'-cleanup-inspect.stdout.log')).write_bytes(inspected.stdout)
        (destination.parent/(name+'-cleanup-inspect.stderr.log')).write_bytes(inspected.stderr)
        saved(destination.parent/(name+'-cleanup-inspect.command.json'), {'command': inspect_command,
              'exit_code': inspected.returncode})
        if inspected.returncode == 0:
            rows = json.loads(inspected.stdout)
            if len(rows) != 1 or rows[0]['Image'] != image or rows[0]['Config'].get('Labels', {}).get(label) != owner:
                raise ValueError('Probe cleanup ownership differs')
            owned = rows[0]['Id']
            run(['docker', 'rm', '--force', owned], destination.parent, name+'-remove', timeout=15)
            absent = run(['docker', 'inspect', owned], destination.parent, name+'-absent', expected=1, timeout=15)
            if not any(s in absent.stderr.decode('utf-8', 'replace').lower() for s in ('no such object', 'no such container')):
                raise ValueError('Probe deletion unconfirmed')
        elif inspected.returncode != 1 or not any(s in inspected.stderr.decode('utf-8', 'replace').lower() for s in ('no such object', 'no such container')):
            raise ValueError('Probe container absence unknown')
    if writable:
        result = json.loads((destination/'persisted.json').read_bytes())
        if result != {'uid': 10001, 'science_calls': 0}:
            raise ValueError('Output changed or missing after deletion')
    elif (destination/'persisted.json').exists():
        raise ValueError('Unwritable negative probe wrote an output')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output_root.absolute()
    if output.exists() or output.is_symlink():
        parser.error('Fresh output directory required')
    if sys.platform != 'linux' or os.environ.get('GITHUB_ACTIONS') != 'true':
        parser.error('This controlled Linux installation probe is for GitHub Actions')
    output.mkdir(parents=True)
    report = {'schema': 'public-installation-engineering-ci-v2', 'status': 'FAIL_ENGINEERING',
              'scope': 'PINNED_PUBLIC_SOURCE_INSTALLATION_AND_STDLIB_IO_ONLY',
              'runtime_commit': os.environ.get('GITHUB_SHA'), 'run_id': os.environ.get('GITHUB_RUN_ID'),
              'run_attempt': os.environ.get('GITHUB_RUN_ATTEMPT'), 'scientific_calls': 0,
              'scientific_acceptance': 'NOT_INHERITED', 'wslc': 'NOT_EXECUTED',
              'registry_push': False, 'release_publication': False}
    try:
        install = output/'installation'
        run([sys.executable, '-B', ROOT/'scripts/install-local-runtime.py', 'prepare', '--destination', install],
            output, 'prepare-public-source', timeout=600)
        run([sys.executable, '-B', ROOT/'scripts/install-local-runtime.py', 'verify-context', '--destination', install],
            output, 'verify-context', timeout=120)
        run([sys.executable, '-B', ROOT/'scripts/install-local-runtime.py', 'build', '--destination', install],
            output, 'build-public-installation', timeout=1200)
        built = json.loads((install/'built-image.json').read_bytes())
        report['built_image'] = built
        context = install/'runtime'
        for service in ('molecular-service', 'registered-cases', 'protocol-cases', 'high-cost-cases'):
            run([sys.executable, '-B', context/'scripts/register-installation.py', '--service', service,
                 '--image', built['local_tag'], '--output-dir', output/('identity-'+service)],
                output, 'register-'+service, cwd=context, timeout=300)
        denied = output/'linux-output-uid1000-0755'
        allowed = output/'linux-output-uid10001'
        denied.mkdir(mode=0o755)
        allowed.mkdir(mode=0o755)
        run(['sudo', 'chown', '1000:1000', denied], output, 'negative-directory-owner', timeout=30)
        helper_spec = importlib.util.spec_from_file_location('ci_actual_host_safety', context/'scripts/runtime_host_safety.py')
        helper = importlib.util.module_from_spec(helper_spec); helper_spec.loader.exec_module(helper)
        class ProbeJournal:
            count = 0
            def __call__(self, *arguments, timeout=10, allow_failure=False):
                self.count += 1
                return run(['docker', *arguments], output, 'actual-host-probe-'+str(self.count),
                           expected=None if allow_failure else 0, timeout=timeout)
        journal = ProbeJournal()
        try:
            helper.probe_output_writable(journal, image_id=built['image_id'], output_path=denied,
                 token=uuid.uuid4().hex, label_key='ai4orgchem.ci.output-probe', timeout=10,
                 python_executable='/opt/venv/bin/python')
        except helper.HostSafetyError as exc:
            if exc.cleanup_unknown:
                raise ValueError('Actual denied-directory probe cleanup was not confirmed') from exc
            report['actual_host_directory_negative'] = 'REFUSED_BEFORE_ANY_SCIENTIFIC_WORKER'
        else:
            raise ValueError('Actual host helper accepted an unwritable Linux directory')
        docker_probe(built['image_id'], denied, 'denied-output', writable=False)
        # This fresh CI directory is explicitly owned by the non-root worker;
        # no chmod 777, existing outputs or system-wide configuration is changed.
        run(['sudo', 'chown', '10001:10001', allowed], output, 'positive-directory-owner', timeout=30)
        helper.probe_output_writable(journal, image_id=built['image_id'], output_path=allowed,
             token=uuid.uuid4().hex, label_key='ai4orgchem.ci.output-probe', timeout=10,
             python_executable='/opt/venv/bin/python')
        report['actual_host_directory_positive'] = 'PASS_ZERO_SCIENCE_FILE_IO'
        docker_probe(built['image_id'], allowed, 'writable-output', writable=True)
        report['status'] = 'PASS_ENGINEERING'
        report['checks'] = ['public_pinned_source_prepare', 'git_proven_context', 'local_only_build',
                            'four_registered_service_identities', 'uid10001', 'source_readonly',
                            'network_none', 'linux_permission_negative_and_positive',
                            'nonzero_process_exit', 'owned_container_removal', 'output_after_removal']
        return 0
    except Exception as exc:
        report['error'] = type(exc).__name__+': '+str(exc)
        print(report['error'], file=sys.stderr)
        return 1
    finally:
        # Input archives and Docker build context are reconstructible, not CI
        # evidence attachments. Upload only receipts/identity/probe/build logs.
        for path in sorted(output.rglob('*')):
            if path.is_file() and path.name.endswith('.log'):
                report.setdefault('logs', {})[str(path.relative_to(output))] = hashlib.sha256(path.read_bytes()).hexdigest()
        saved(output/'result.json', report)


if __name__ == '__main__':
    raise SystemExit(main())
