"""Fetch and verify a commit-addressed archive without a sibling checkout."""
import argparse
import hashlib
import json
import tarfile
import urllib.request
from pathlib import Path


def fetch(destination, archive=None):
    root = Path(__file__).resolve().parents[1]
    lock = json.loads((root / 'locks/source.lock.json').read_text())
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('destination already exists; use a fresh directory')
    if archive is None:
        data = urllib.request.urlopen(lock['source_archive_url'], timeout=120).read()
    else:
        data = Path(archive).read_bytes()
    if hashlib.sha256(data).hexdigest() != lock['source_archive_sha256']:
        raise ValueError('source archive hash mismatch')
    import io
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as bundle:
        prefix = f"AI4OrgChem-{lock['source_commit']}/"
        members = bundle.getmembers()
        for member in members:
            if member.name == prefix.rstrip('/') and member.isdir():
                continue
            if not member.name.startswith(prefix) or not (member.isfile() or member.isdir()):
                raise ValueError('unexpected archive member')
            relative = Path(member.name[len(prefix):])
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('archive path escape')
        destination.mkdir(parents=True)
        for member in members:
            if member.name == prefix.rstrip('/'):
                continue
            relative = member.name[len(prefix):]
            if not relative:
                continue
            target = destination / relative
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(bundle.extractfile(member).read())
    print(json.dumps({'source_commit': lock['source_commit'], 'archive_sha256': lock['source_archive_sha256']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('destination')
    parser.add_argument('--archive')
    args = parser.parse_args()
    fetch(args.destination, args.archive)
