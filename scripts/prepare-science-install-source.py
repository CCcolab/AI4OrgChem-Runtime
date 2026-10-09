#!/usr/bin/env python3
"""Rebuild the pinned science file tree from a public baseline and retained files.

This prepares source bytes only. It does not import scientific modules, install
dependencies, reconstruct a Git commit object, or transfer historical acceptance.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile
import tempfile
import urllib.request

MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_SOURCE_BYTES = 64 * 1024 * 1024
JSON_PATHS = ('locks/source.lock.json', 'locks/source.user-molecule.lock.json',
              'locks/source-files.sha256.json', 'locks/source-user-molecule-files.sha256.json')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical_digest(value):
    return digest(json.dumps(value, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=False).encode('utf-8'))


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_bytes(), object_pairs_hook=_pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def safe_name(name):
    path = PurePosixPath(name)
    if (not isinstance(name, str) or not name or path.is_absolute() or
            any(part in ('', '.', '..') for part in name.split('/')) or
            '\\' in name or ':' in name or '\x00' in name):
        raise ValueError('unsafe source path')
    return name


def _no_links(path):
    path = Path(path).absolute()
    for item in (path, *path.parents):
        if item.is_symlink() or (hasattr(item, 'is_junction') and item.is_junction()):
            raise ValueError('linked path rejected: ' + str(item))


def load_config(root=None):
    root = Path(root) if root else Path(__file__).resolve().parents[1]
    lock = read_json(root / 'locks/source.installation.lock.json')
    if (lock.get('schema_version') != 1 or
            lock.get('acquisition_method') != 'public_baseline_plus_retained_overlay' or
            lock.get('archive_matches_historical_bytes') is not False):
        raise ValueError('invalid installation source identity')
    pins = lock.get('pinned_json_canonical_sha256', {})
    if set(pins) != set(JSON_PATHS):
        raise ValueError('installation JSON pin set mismatch')
    materials = {name: read_json(root / name) for name in JSON_PATHS}
    for name, value in materials.items():
        if canonical_digest(value) != pins[name]:
            raise ValueError('installation JSON pin mismatch: ' + name)
    base_lock, historical, base_files, files = (materials[name] for name in JSON_PATHS)
    for commit in (lock.get('source_commit'), lock.get('baseline_commit')):
        if not isinstance(commit, str) or not re.fullmatch('[0-9a-f]{40}', commit):
            raise ValueError('invalid source commit')
    url = ('https://codeload.github.com/CCcolab/AI4OrgChem/tar.gz/' + lock['baseline_commit'])
    if (lock['source_repository'] != 'https://github.com/CCcolab/AI4OrgChem' or
            lock['baseline_archive_url'] != url or base_lock['source_archive_url'] != url or
            lock['baseline_commit'] != base_lock['source_commit'] or
            lock['baseline_archive_sha256'] != base_lock['source_archive_sha256'] or
            lock['source_commit'] != historical['source_commit'] or
            lock['baseline_commit'] != historical['baseline_commit'] or
            lock['historical_archive_sha256'] != historical['source_archive_sha256'] or
            lock['source_archive_sha256'] == lock['historical_archive_sha256'] or
            lock['archive_prefix'] != 'AI4OrgChem-' + lock['source_commit'] + '/'):
        raise ValueError('baseline/historical/new archive binding mismatch')
    if (type(lock['source_file_count']) is not int or len(files) != lock['source_file_count'] or
            type(lock['baseline_file_count']) is not int or len(base_files) != lock['baseline_file_count']):
        raise ValueError('source file count mismatch')
    for name, sha in files.items():
        safe_name(name)
        if not re.fullmatch('[0-9a-f]{64}', sha):
            raise ValueError('invalid file digest')
    if any(files.get(name) != sha for name, sha in base_files.items()):
        raise ValueError('frozen baseline files changed')
    overlay = lock['overlay']
    if (len({row['path'] for row in overlay}) != len(overlay) or
            {row['path'] for row in overlay} != set(files) - set(base_files)):
        raise ValueError('overlay file set mismatch')
    for row in overlay:
        if (row['sha256'] != files[row['path']] or type(row['size_bytes']) is not int or
                row['size_bytes'] < 0 or row['retained_path'] !=
                'assets/science-install-overlay/' + lock['source_commit'][:8] + '/' + row['path']):
            raise ValueError('overlay binding mismatch')
    rules = 'configs/qm/p09_exchange_integral_classes_v0.1.yaml'
    if files.get(rules) != lock['condition_rules_sha256'] or files.get(rules) != historical['condition_rules_sha256']:
        raise ValueError('frozen condition rules mismatch')
    return root, lock, base_files, files


def read_archive(raw, prefix, expected, mode):
    if len(raw) > MAX_ARCHIVE_BYTES:
        raise ValueError('source archive size limit exceeded')
    result = {}
    size = 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode=mode) as bundle:
        for member in bundle.getmembers():
            if member.name == prefix[:-1] and member.isdir():
                continue
            if not member.name.startswith(prefix) or not (member.isfile() or member.isdir()):
                raise ValueError('archive member type/prefix rejected')
            name = safe_name(member.name[len(prefix):].rstrip('/') if member.isdir()
                             else member.name[len(prefix):])
            if member.isdir():
                continue
            if name in result or name not in expected or member.size < 0:
                raise ValueError('duplicate/unknown archive member')
            size += member.size
            if size > MAX_SOURCE_BYTES:
                raise ValueError('unpacked source size limit exceeded')
            value = bundle.extractfile(member).read()
            if digest(value) != expected[name]:
                raise ValueError('archive file hash mismatch: ' + name)
            result[name] = value
    if set(result) != set(expected):
        raise ValueError('archive file set mismatch')
    return result


def canonical_archive(files, prefix):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:', format=tarfile.PAX_FORMAT) as bundle:
        for name, value in sorted(files.items()):
            safe_name(name)
            member = tarfile.TarInfo(prefix + name)
            member.size = len(value)
            member.mode = 0o644
            member.uid = member.gid = member.mtime = 0
            member.uname = member.gname = ''
            bundle.addfile(member, io.BytesIO(value))
    return output.getvalue()


def _fresh_target(target):
    target = Path(target).absolute()
    _no_links(target)
    if target.exists():
        raise ValueError('destination must be new')
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _receipt(lock, status, archive_sha256):
    return {'schema_version': 1, 'status': status, 'source_commit': lock['source_commit'],
            'baseline_commit': lock['baseline_commit'], 'archive_sha256': archive_sha256,
            'archive_size_bytes': lock['source_archive_size_bytes'],
            'source_file_count': lock['source_file_count'],
            'source_tree_canonical_sha256': lock['pinned_json_canonical_sha256'][JSON_PATHS[-1]],
            'installation_source_lock_canonical_sha256': canonical_digest(lock),
            'historical_archive_sha256': lock['historical_archive_sha256'],
            'archive_matches_historical_bytes': False,
            'scientific_execution': 'NOT_EXECUTED', 'historical_acceptance_transferred': False}


def prepare(output, baseline_archive=None, root=None):
    root, lock, base_files, expected = load_config(root)
    target = _fresh_target(output)
    if baseline_archive is None:
        request = urllib.request.Request(lock['baseline_archive_url'], headers={'User-Agent': 'AI4OrgChem-Runtime-source-preparation'})
        with urllib.request.urlopen(request, timeout=120) as response:
            baseline = response.read(MAX_ARCHIVE_BYTES + 1)
        acquisition = 'PINNED_PUBLIC_GITHUB_DOWNLOAD'
    else:
        baseline = Path(baseline_archive).read_bytes()
        acquisition = 'SUPPLIED_PINNED_PUBLIC_BASELINE_ARCHIVE'
    if digest(baseline) != lock['baseline_archive_sha256']:
        raise ValueError('public baseline archive hash mismatch')
    files = read_archive(baseline, 'AI4OrgChem-' + lock['baseline_commit'] + '/', base_files, 'r:gz')
    for row in lock['overlay']:
        path = root / row['retained_path']
        _no_links(path)
        raw = path.read_bytes()
        if len(raw) != row['size_bytes'] or digest(raw) != row['sha256']:
            raise ValueError('retained overlay hash/size mismatch: ' + row['path'])
        files[row['path']] = raw
    if {name: digest(raw) for name, raw in files.items()} != expected:
        raise ValueError('reconstructed source file manifest mismatch')
    archive = canonical_archive(files, lock['archive_prefix'])
    if digest(archive) != lock['source_archive_sha256'] or len(archive) != lock['source_archive_size_bytes']:
        raise ValueError('reconstructed canonical archive identity mismatch')
    receipt = _receipt(lock, 'PREPARED_RECONSTRUCTED_SOURCE_ONLY', digest(archive))
    receipt.update({'baseline_acquisition': acquisition, 'baseline_archive_sha256': digest(baseline),
                    'baseline_file_count': len(base_files), 'overlay_file_count': len(lock['overlay'])})
    with tempfile.TemporaryDirectory(prefix='.science-install-', dir=target.parent) as temporary:
        stage = Path(temporary) / 'payload'
        stage.mkdir()
        (stage / 'baseline.tar.gz').write_bytes(baseline)
        (stage / 'science.tar').write_bytes(archive)
        (stage / 'science-install-source.receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
        stage.rename(target)
    return receipt


def extract(archive, destination, root=None):
    _, lock, _, expected = load_config(root)
    target = _fresh_target(destination)
    raw = Path(archive).read_bytes()
    if digest(raw) != lock['source_archive_sha256'] or len(raw) != lock['source_archive_size_bytes']:
        raise ValueError('installation science archive hash/size mismatch')
    files = read_archive(raw, lock['archive_prefix'], expected, 'r:')
    with tempfile.TemporaryDirectory(prefix='.science-install-', dir=target.parent) as temporary:
        stage = Path(temporary) / 'payload'
        stage.mkdir()
        for name, value in files.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
        stage.rename(target)
    return _receipt(lock, 'EXTRACTED_RECONSTRUCTED_SOURCE_ONLY', digest(raw))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    prepare_parser = sub.add_parser('prepare')
    prepare_parser.add_argument('--output', required=True)
    prepare_parser.add_argument('--baseline-archive')
    extract_parser = sub.add_parser('extract')
    extract_parser.add_argument('--archive', required=True)
    extract_parser.add_argument('--destination', required=True)
    args = parser.parse_args()
    try:
        result = (prepare(args.output, args.baseline_archive) if args.action == 'prepare'
                  else extract(args.archive, args.destination))
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError) as exc:
        print(json.dumps({'status': 'SCIENCE_SOURCE_PREPARATION_REFUSED', 'error': str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
