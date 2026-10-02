"""Verify local archives without extracting or modifying Docker/WSL."""
import argparse
import hashlib
import json
import re
import tarfile
import zipfile
from pathlib import Path

def stream_hash(stream):
    h = hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        h.update(chunk)
    return h.hexdigest()

def verify(root):
    manifest_path = root / 'backup-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    expected = re.search(r'\b[0-9a-fA-F]{64}\b', (root / 'backup-manifest.sha256.txt').read_text(encoding='utf-8-sig')).group().lower()
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == expected, 'manifest hash mismatch'
    for file in manifest['files']:
        with (root / file['name']).open('rb') as stream:
            assert stream_hash(stream) == file['sha256'], file['name']
    records = json.loads((root / 'run-files.sha256.json').read_text(encoding='utf-8-sig'))
    prefix = Path(manifest['runs_root']).name + '/'
    # Path parsing is host dependent: backup runs_root is a Windows path.
    prefix = manifest['runs_root'].replace('\\', '/').rstrip('/').split('/')[-1] + '/'
    with zipfile.ZipFile(root / 'runs.zip') as archive:
        assert len(archive.infolist()) == len(records)
        for file in records:
            with archive.open(prefix + file['path']) as stream:
                assert stream_hash(stream) == file['sha256'], file['path']
    with zipfile.ZipFile(root / 'runtime-source.zip') as archive:
        assert archive.testzip() is None
    blobs = 0
    with tarfile.open(root / 'candidate-image.tar') as archive:
        for file in archive:
            if file.isfile() and '/blobs/sha256/' in '/' + file.name:
                with archive.extractfile(file) as stream:
                    assert stream_hash(stream) == file.name.rsplit('/', 1)[-1], file.name
                blobs += 1
    assert blobs, 'no content-addressed image blobs found'
    return {'status': 'PASS', 'files': len(manifest['files']), 'run_files': len(records),
            'image_blobs': blobs, 'image_id': manifest['image_id'],
            'scope': 'Archive content integrity; no engine reload or environment restoration performed'}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    print(json.dumps(verify(parser.parse_args().directory), ensure_ascii=False))
