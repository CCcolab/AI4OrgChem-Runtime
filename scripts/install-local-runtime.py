"""Source-only local Docker installation, with independently registered identities.

Never resets existing workspaces, installs host dependencies, edits WSL settings,
publishes images, or transfers historical scientific acceptance to a new image.
"""
from pathlib import Path, PurePosixPath
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE_RECEIPT = '.runtime-installation-source.json'
PUBLIC_BASE = 'docker.io/library/python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2'
SERVICES = ('molecular-service', 'registered-cases', 'protocol-cases', 'high-cost-cases')
HOST_OVERRIDES = {'scripts/run-high-cost-case.py', 'tests/test_high_cost_supervisor.py'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as out:
        out.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n')


def read_json(path):
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result: raise ValueError('Duplicate JSON key: '+key)
            result[key] = value
        return result
    return json.loads(Path(path).read_bytes(), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def safe_path(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or any(x in ('', '.', '..') for x in name.split('/')) or ':' in name or '\\' in name:
        raise ValueError('Unsafe source path: '+name)
    return path


def no_links(path):
    for p in (Path(path).absolute(), *Path(path).absolute().parents):
        if p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction()):
            raise ValueError('Linked installation path forbidden')


def new_directory(path):
    path = Path(path).absolute()
    no_links(path)
    if path.exists():
        raise ValueError('Fresh, absent destination required: '+str(path))
    path.mkdir(parents=True)
    return path


def capture(command, cwd=None):
    result = subprocess.run(list(map(str, command)), cwd=cwd, capture_output=True, check=True)
    return result.stdout.decode('utf-8').strip()


def git_object(kind, raw):
    return hashlib.sha1(kind.encode()+b' '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


def verify_git_proof(receipt):
    """Bind every source file to the named Git commit rather than a mutable list."""
    raw = base64.b64decode(receipt['git_commit_base64'], validate=True)
    if git_object('commit', raw) != receipt['runtime_commit']:
        raise ValueError('Git commit object identity mismatch')
    first = raw.split(b'\n', 1)[0]
    if not re.fullmatch(b'tree [0-9a-f]{40}', first):
        raise ValueError('Git commit root tree missing')
    trees = receipt['git_trees_base64']; visited = set(); files = {}
    def walk(oid, prefix='', depth=0):
        if depth > 32 or len(files) > 20000:
            raise ValueError('Oversized Git proof')
        data = base64.b64decode(trees[oid], validate=True)
        if git_object('tree', data) != oid:
            raise ValueError('Git tree object identity mismatch')
        visited.add(oid); pos = 0
        while pos < len(data):
            space = data.index(b' ', pos); nul = data.index(b'\0', space)
            mode = data[pos:space]; name = data[space+1:nul].decode('utf-8')
            child = data[nul+1:nul+21]
            if len(child) != 20 or '/' in name:
                raise ValueError('Invalid Git tree member')
            full = prefix+name; safe_path(full); pos = nul+21
            if mode in (b'40000', b'040000'):
                walk(child.hex(), full+'/', depth+1)
            elif mode in (b'100644', b'100755') and full not in files:
                files[full] = child.hex()
            else:
                raise ValueError('Unsupported or duplicate Git source member')
    walk(first[5:].decode('ascii'))
    if visited != set(trees) or set(files) != set(receipt['files']):
        raise ValueError('Git proof file/tree inventory differs')
    return files


def package_bytes(root):
    root = Path(root)
    commit = capture(['git', '-C', root, 'rev-parse', 'HEAD'])
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('Full runtime commit required')
    subprocess.run(['git', '-C', str(root), 'diff', '--quiet', 'HEAD'], check=True)
    # Read raw Git blobs in one batch. `git archive` can apply export-subst or
    # newline attributes and therefore is not itself a byte identity proof.
    listing_raw = subprocess.run(['git', '-C', str(root), 'ls-tree', '-r', '-z', commit], capture_output=True, check=True).stdout
    entries = []
    for entry in listing_raw.split(b'\0'):
        if not entry: continue
        metadata, name = entry.split(b'\t', 1)
        mode, kind, oid = metadata.split(b' ')
        if kind != b'blob' or mode not in (b'100644', b'100755'):
            raise ValueError('Only regular Git source blobs supported')
        name = name.decode('utf-8'); safe_path(name)
        entries.append((name, oid.decode('ascii')))
    batch = subprocess.run(['git', '-C', str(root), 'cat-file', '--batch'],
                           input=('\n'.join(oid for _,oid in entries)+'\n').encode(),
                           capture_output=True, check=True).stdout
    packed = io.BytesIO(); position = 0
    with zipfile.ZipFile(packed, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, oid in entries:
            end = batch.index(b'\n', position)
            actual_oid, kind, length = batch[position:end].split(b' ')
            if actual_oid.decode()!=oid or kind!=b'blob': raise ValueError('Git blob batch header differs')
            length = int(length); content = batch[end+1:end+1+length]; position=end+length+2
            if len(content)!=length or git_object('blob', content)!=oid: raise ValueError('Git blob batch bytes differ')
            archive.writestr(name, content)
    if position != len(batch): raise ValueError('Unexpected Git blob batch suffix')
    raw = packed.getvalue()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        files = {}
        for item in archive.infolist():
            if item.is_dir():
                continue
            safe_path(item.filename)
            if stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('Linked source member forbidden')
            content = archive.read(item)
            files[item.filename] = {'sha256': hashlib.sha256(content).hexdigest(), 'size': len(content)}
    commit_raw = subprocess.run(['git', '-C', str(root), 'cat-file', 'commit', commit], capture_output=True, check=True).stdout
    trees = {commit_raw.split(b'\n', 1)[0][5:].decode('ascii')}
    listing = capture(['git', '-C', root, 'ls-tree', '-r', '-t', commit])
    for line in listing.splitlines():
        metadata = line.split('\t', 1)[0].split(' ')
        if metadata[1] == 'tree': trees.add(metadata[2])
    proof = {oid: base64.b64encode(subprocess.run(['git', '-C', str(root), 'cat-file', 'tree', oid], capture_output=True, check=True).stdout).decode('ascii') for oid in sorted(trees)}
    receipt = {'schema': 'runtime-installation-source-v1', 'runtime_commit': commit,
               'git_commit_base64': base64.b64encode(commit_raw).decode('ascii'), 'git_trees_base64': proof,
               'files': files, 'scientific_acceptance': 'NOT_INHERITED', 'public_release': False}
    blobs = verify_git_proof(receipt)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if any(git_object('blob', archive.read(name)) != oid for name, oid in blobs.items()):
            raise ValueError('Export differs from Git blob proof')
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as target:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            for name in sorted(files):
                target.writestr(name, archive.read(name))
        target.writestr(SOURCE_RECEIPT, json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2)+'\n')
    return output.getvalue(), receipt


def source_bytes(root):
    root = Path(root)
    if (root / '.git').exists():
        return package_bytes(root)
    receipt = json.loads((root / SOURCE_RECEIPT).read_text(encoding='utf-8'))
    if receipt.get('schema') != 'runtime-installation-source-v1' or not re.fullmatch('[0-9a-f]{40}', receipt.get('runtime_commit', '')):
        raise ValueError('Verified installation source package required outside Git')
    blobs = verify_git_proof(receipt)
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, row in receipt['files'].items():
            safe_path(name)
            path = root / name
            no_links(path)
            if sha(path) != row['sha256'] or path.stat().st_size != row['size'] or git_object('blob', path.read_bytes()) != blobs[name]:
                raise ValueError('Downloaded source bytes differ: '+name)
            archive.writestr(name, path.read_bytes())
        archive.writestr(SOURCE_RECEIPT, (root / SOURCE_RECEIPT).read_bytes())
    return output.getvalue(), receipt


def unpack(raw, target):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if archive.testzip() is not None:
            raise ValueError('Source ZIP CRC failed')
        for item in archive.infolist():
            name = safe_path(item.filename)
            if item.is_dir() or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('Only regular source files allowed')
            path = target / str(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(item))


def logged(command, directory, name, cwd=None):
    command = list(map(str, command))
    for ending in ('.stdout.log', '.stderr.log', '.command.json'):
        if (directory/(name+ending)).exists():
            raise ValueError('Existing attempt records must be preserved: '+name)
    start = time.monotonic()
    print('Running '+name, flush=True)
    with (directory/(name+'.stdout.log')).open('xb') as out, (directory/(name+'.stderr.log')).open('xb') as err:
        process = subprocess.Popen(command, cwd=cwd, stdout=out, stderr=err)
        next_update = start+30
        while process.poll() is None:
            time.sleep(0.25)
            if time.monotonic() >= next_update:
                print(name+': running, '+str(int(time.monotonic()-start))+' seconds', flush=True)
                next_update = time.monotonic()+30
    save(directory/(name+'.command.json'), {'command': command, 'cwd': str(cwd) if cwd else None,
         'exit_code': process.returncode, 'elapsed_seconds': time.monotonic()-start})
    if process.returncode:
        raise RuntimeError(name+' failed; see '+str(directory/(name+'.stderr.log')))


def prepare(args):
    raw, source = source_bytes(ROOT)
    destination = new_directory(args.destination)
    context = destination/'runtime'
    context.mkdir()
    unpack(raw, context)
    (destination/'runtime-source.zip').write_bytes(raw)
    inputs = context/'build-inputs'
    inputs.mkdir()
    if args.science_input_directory:
        science = Path(args.science_input_directory).absolute()
        no_links(science)
    else:
        science = destination/'science-download'
        logged([sys.executable, '-B', context/'scripts/prepare-science-install-source.py', 'prepare', '--output', science], destination, 'source-download')
    expected = json.loads((context/'locks/source.installation.lock.json').read_text(encoding='utf-8'))
    no_links(science/'science.tar')
    no_links(science/'science-install-source.receipt.json')
    if sha(science/'science.tar') != expected['source_archive_sha256']:
        raise ValueError('Installation science archive mismatch')
    science_receipt = read_json(science/'science-install-source.receipt.json')
    source_checks = {'schema_version': 1, 'status': 'PREPARED_RECONSTRUCTED_SOURCE_ONLY',
         'source_commit': expected['source_commit'], 'baseline_commit': expected['baseline_commit'],
         'archive_sha256': expected['source_archive_sha256'], 'archive_size_bytes': expected['source_archive_size_bytes'],
         'source_file_count': expected['source_file_count'],
         'source_tree_canonical_sha256': expected['pinned_json_canonical_sha256']['locks/source-user-molecule-files.sha256.json'],
         'installation_source_lock_canonical_sha256': canonical_sha(expected),
         'historical_archive_sha256': expected['historical_archive_sha256'],
         'archive_matches_historical_bytes': False, 'scientific_execution': 'NOT_EXECUTED',
         'historical_acceptance_transferred': False, 'baseline_archive_sha256': expected['baseline_archive_sha256'],
         'baseline_file_count': expected['baseline_file_count'], 'overlay_file_count': len(expected['overlay'])}
    if set(science_receipt) != set(source_checks)|{'baseline_acquisition'}:
        raise ValueError('Science preparation receipt fields differ')
    if any(type(science_receipt[k]) is not type(v) or science_receipt[k] != v for k, v in source_checks.items()):
        raise ValueError('Science preparation receipt binding differs')
    if science_receipt['baseline_acquisition'] not in ('PINNED_PUBLIC_GITHUB_DOWNLOAD', 'SUPPLIED_PINNED_PUBLIC_BASELINE_ARCHIVE'):
        raise ValueError('Science baseline acquisition unknown')
    shutil.copyfile(science/'science.tar', inputs/'science.tar')
    shutil.copyfile(science/'science-install-source.receipt.json', destination/'science-source.receipt.json')
    if args.dependency_input_directory:
        dependencies = Path(args.dependency_input_directory).absolute()
        no_links(dependencies)
    else:
        dependencies = destination/'dependency-download'
        logged([sys.executable, '-B', context/'scripts/prepare-install-dependencies.py', 'prepare', '--output', dependencies], destination, 'dependency-download')
    lock = json.loads((context/'locks/installation-dependencies.json').read_text(encoding='utf-8'))
    # The dependency preparer validates every public artifact. Copy only locked
    # files; do not import arbitrary wheels from an existing environment.
    copied = inputs/'dependencies'
    copied.mkdir()
    for folder in ('wheels', 'sources'):
        (copied/folder).mkdir()
        for item in sorted((dependencies/folder).iterdir()):
            no_links(item)
            if not item.is_file():
                raise ValueError('Regular dependency artifact required')
            shutil.copyfile(item, copied/folder/item.name)
    # Repeat validation through the public preparation script's offline mode.
    logged([sys.executable, '-B', context/'scripts/prepare-install-dependencies.py', 'verify', '--input', copied], destination, 'dependency-verify')
    baseline = context/'locks/high-cost-source.json'
    baseline_bytes = baseline.read_bytes()
    (context/'locks/high-cost-source.installation-baseline.json').write_bytes(baseline_bytes)
    high = json.loads(baseline_bytes)
    if len(high['files']) != 107:
        raise ValueError('Original 107-file high-cost catalog required')
    for row in high['files']:
        path = context/row['path']
        if row['path'] in HOST_OVERRIDES:
            row['sha256'], row['size'] = sha(path), path.stat().st_size
        elif sha(path) != row['sha256']:
            raise ValueError('Frozen high-cost worker bytes differ: '+row['path'])
    baseline.write_text(json.dumps(high, ensure_ascii=False, sort_keys=True, indent=2)+'\n', encoding='utf-8', newline='\n')
    inventory = {str(p.relative_to(context)).replace('\\','/'): {'sha256': sha(p), 'size': p.stat().st_size}
                 for p in sorted(context.rglob('*')) if p.is_file()}
    save(destination/'installation-context.json', {'schema': 'runtime-installation-context-v1',
         'runtime_commit': source['runtime_commit'], 'runtime_source_zip_sha256': hashlib.sha256(raw).hexdigest(),
         'public_base': PUBLIC_BASE, 'context_files': inventory,
         'historical_scientific_acceptance': 'NOT_INHERITED',
         'high_cost_scientific_replay': 'NOT_EXECUTED', 'wslc': 'BLOCKED', 'image_distribution': 'BLOCKED'})
    print('Prepared '+str(destination), flush=True)


def verify_context(destination):
    destination = Path(destination).absolute()
    no_links(destination)
    receipt = json.loads((destination/'installation-context.json').read_text(encoding='utf-8'))
    context = destination/'runtime'
    for path in context.rglob('*'):
        no_links(path)
    actual = {str(p.relative_to(context)).replace('\\', '/') for p in context.rglob('*') if p.is_file()}
    if actual != set(receipt['context_files']):
        raise ValueError('Prepared installation has extra or missing files')
    for name, row in receipt['context_files'].items():
        safe_path(name)
        path = context/name
        no_links(path)
        if sha(path) != row['sha256'] or path.stat().st_size != row['size']:
            raise ValueError('Prepared installation changed: '+name)
    # A mutable context receipt cannot authorize different source bytes. Derive
    # the allowed context from the original Git-proven source ZIP and fixed locks.
    raw = (destination/'runtime-source.zip').read_bytes()
    if hashlib.sha256(raw).hexdigest() != receipt['runtime_source_zip_sha256']:
        raise ValueError('Installation source ZIP changed')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        proof = json.loads(archive.read(SOURCE_RECEIPT))
        blobs = verify_git_proof(proof)
        if proof['runtime_commit'] != receipt['runtime_commit'] or set(archive.namelist()) != set(blobs)|{SOURCE_RECEIPT}:
            raise ValueError('Installation Git identity/file set changed')
        for name, oid in blobs.items():
            content = archive.read(name)
            if git_object('blob', content) != oid:
                raise ValueError('Source ZIP Git blob mismatch: '+name)
            if name != 'locks/high-cost-source.json' and (context/name).read_bytes() != content:
                raise ValueError('Context is not the declared Git source: '+name)
        if (context/SOURCE_RECEIPT).read_bytes() != archive.read(SOURCE_RECEIPT):
            raise ValueError('Source proof receipt changed')
        old_high = archive.read('locks/high-cost-source.json')
        if (context/'locks/high-cost-source.installation-baseline.json').read_bytes() != old_high:
            raise ValueError('Original high-cost catalog must be preserved exactly')
        high = json.loads(old_high)
        for row in high['files']:
            if row['path'] in HOST_OVERRIDES:
                content = archive.read(row['path'])
                row.update(sha256=hashlib.sha256(content).hexdigest(), size=len(content))
        high_bytes = (json.dumps(high, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode()
        if (context/'locks/high-cost-source.json').read_bytes() != high_bytes:
            raise ValueError('Only the defined high-cost host rebind is allowed')
    dependencies = read_json(context/'locks/installation-dependencies.json')
    extras = {'build-inputs/science.tar', 'locks/high-cost-source.installation-baseline.json'}
    for item in dependencies['artifacts']:
        name = 'build-inputs/dependencies/'+('sources/' if item['packagetype']=='sdist' else 'wheels/')+item['filename']
        extras.add(name)
        path = context/name
        if sha(path) != item['sha256'] or path.stat().st_size != item['size']:
            raise ValueError('Prepared public dependency differs: '+name)
    source = read_json(context/'locks/source.installation.lock.json')
    if sha(context/'build-inputs/science.tar') != source['source_archive_sha256']:
        raise ValueError('Prepared public science archive differs')
    if actual != set(blobs)|{SOURCE_RECEIPT}|extras:
        raise ValueError('Context contains content outside the defined installation transformation')
    return destination, context, receipt


def build(args):
    destination, context, receipt = verify_context(args.destination)
    docker = args.docker
    engine = capture([docker, 'info', '--format', '{{.OSType}}/{{.Architecture}}'])
    if engine not in ('linux/x86_64', 'linux/amd64'):
        raise ValueError('Available Linux amd64 Docker engine required; actual '+engine)
    suffix = receipt['runtime_commit'][:12]
    foundation = 'ai4orgchem-runtime:source-foundation-'+suffix
    candidate = 'ai4orgchem-runtime:source-installation-'+suffix
    logged([docker, 'build', '--platform', 'linux/amd64', '--pull', '--progress=plain', '-f',
         context/'container/Dockerfile.installation-foundation', '--build-arg',
         'SCIENCE_ARCHIVE_SHA256='+sha(context/'build-inputs/science.tar'), '--build-arg',
         'INSTALL_REQUIREMENTS_SHA256='+sha(context/'locks/requirements-installation-linux-amd64.txt'),
         '-t', foundation, context], destination, 'build-foundation')
    base = json.loads(capture([docker, 'image', 'inspect', foundation]))[0]['Id']
    arguments = [docker, 'build', '--platform', 'linux/amd64', '--progress=plain', '-f',
                 context/'container/Dockerfile.installation-runtime', '-t', candidate,
                 '--build-arg', 'BASE_IMAGE='+base, '--build-arg', 'BASE_IMAGE_ID='+base,
                 '--build-arg', 'RUNTIME_COMMIT='+receipt['runtime_commit']]
    for prefix, family in [('MOLECULAR','molecular-service'),('REGISTERED','registered-cases'),('PROTOCOL','protocol-cases'),('HIGH_COST','high-cost')]:
        for field, ending in [('SOURCE','source'),('DEPENDENCY','dependencies')]:
            arguments += ['--build-arg', prefix+'_'+field+'_SHA256='+sha(context/('locks/'+family+'-'+ending+'.json'))]
    arguments += ['--build-arg','HIGH_COST_PROFILE_SHA256='+sha(context/'configs/high-cost-cases-v1.json'),context]
    logged(arguments, destination, 'build-runtime')
    inspection = json.loads(capture([docker, 'image', 'inspect', candidate]))[0]
    save(destination/'built-image.json', {'schema': 'runtime-source-built-image-v1', 'image_id': inspection['Id'],
         'local_tag': candidate, 'base_image_id': base, 'runtime_build_commit': receipt['runtime_commit'],
         'scientific_acceptance': 'NOT_INHERITED', 'wslc': 'BLOCKED', 'image_distribution': 'BLOCKED'})
    print('Built '+inspection['Id']+'. Register each service with scripts/register-installation.py.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    pack = commands.add_parser('package'); pack.add_argument('--output', required=True)
    prep = commands.add_parser('prepare'); prep.add_argument('--destination', required=True)
    prep.add_argument('--science-input-directory'); prep.add_argument('--dependency-input-directory')
    builder = commands.add_parser('build'); builder.add_argument('--destination', required=True); builder.add_argument('--docker', default='docker')
    checker = commands.add_parser('verify-context'); checker.add_argument('--destination', required=True)
    args = parser.parse_args()
    try:
        if args.action == 'package':
            raw, receipt = package_bytes(ROOT)
            target = Path(args.output).absolute(); no_links(target)
            with target.open('xb') as handle: handle.write(raw)
            print(json.dumps({'runtime_commit': receipt['runtime_commit'], 'file_count': len(receipt['files']),
                              'zip_sha256': hashlib.sha256(raw).hexdigest(), 'path': str(target)}))
        elif args.action == 'prepare': prepare(args)
        elif args.action == 'build': build(args)
        else: verify_context(args.destination); print('Prepared context byte verification PASS')
        return 0
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        print(type(exc).__name__+': '+str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
