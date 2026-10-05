"""Verify/extract an unpublished local git archive. No network and no sibling import."""
import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path, PurePosixPath


def fetch(archive, destination, root=None):
    root=Path(root) if root else Path(__file__).resolve().parents[1]
    lock=json.loads((root/'locks/source.user-molecule.lock.json').read_text())
    if lock['acquisition_method']!='local_git_archive' or not re.fullmatch('[0-9a-f]{40}',lock['source_commit']):
        raise ValueError('invalid acquisition identity')
    archive=Path(archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=lock['source_archive_sha256']:
        raise ValueError('scientific archive hash mismatch')
    destination=Path(destination)
    if destination.exists():
        raise ValueError('destination must be new')
    expected=json.loads((root/'locks/source-user-molecule-files.sha256.json').read_text())
    prefix='AI4OrgChem-'+lock['source_commit']+'/'
    seen=set()
    with tarfile.open(archive,'r:') as bundle:
        members=bundle.getmembers()
        for member in members:
            if member.name==prefix[:-1] and member.isdir():
                continue
            if not member.name.startswith(prefix) or not (member.isfile() or member.isdir()):
                raise ValueError('archive member type/prefix rejected')
            name=member.name[len(prefix):]
            path=PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name:
                raise ValueError('archive traversal rejected')
            if member.isfile():
                if name in seen or name not in expected:
                    raise ValueError('duplicate/unknown member')
                if hashlib.sha256(bundle.extractfile(member).read()).hexdigest()!=expected[name]:
                    raise ValueError('archive file hash mismatch: '+name)
                seen.add(name)
        if seen!=set(expected):
            raise ValueError('archive file set mismatch')
        destination.mkdir(parents=True)
        for member in members:
            if not member.isfile():
                continue
            name=member.name[len(prefix):]
            target=destination/name
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(bundle.extractfile(member).read())


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('archive');parser.add_argument('destination')
    args=parser.parse_args();fetch(args.archive,args.destination)
