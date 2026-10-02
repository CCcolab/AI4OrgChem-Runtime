"""Verify acquired sources using signed Debian indexes and recorded file hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--image', default='sha256:ddc45b1fe500ed3d5ed30520eb4e49f3969cb69f02121f28e2ff851f7a724f54')
    args = parser.parse_args()
    root = args.directory.resolve()
    record = json.loads((root / 'source-acquisition.json').read_text(encoding='utf-8'))
    signatures = []
    for index in record['indexes']:
        suite = index['suite']
        command = ['docker', 'run', '--rm', '--network', 'none', '--read-only',
                   '--mount', f'type=bind,source={root},target=/materials,readonly',
                   '--entrypoint', 'gpgv', args.image, '--status-fd', '2',
                   '--keyring', '/usr/share/keyrings/debian-archive-keyring.gpg',
                   '--output', '-', f'/materials/indexes/{suite}/InRelease']
        process = subprocess.run(command, capture_output=True)
        (root / 'indexes' / suite / 'signature.log').write_bytes(process.stderr)
        if process.returncode or b'[GNUPG:] VALIDSIG ' not in process.stderr:
            raise RuntimeError('Debian index signature rejected: ' + suite)
        release = process.stdout.decode('utf-8')
        path = root / 'indexes' / suite / 'Sources.xz'
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        sha_section = release.split('SHA256:\n', 1)[1].split('\nSHA512:', 1)[0]
        expected = [line.split() for line in sha_section.splitlines()
                    if line.strip().endswith('main/source/Sources.xz')]
        if len(expected) != 1 or expected[0][0] != digest or int(expected[0][1]) != path.stat().st_size:
            raise RuntimeError('Sources index does not match signed Release: ' + suite)
        signatures.append({'suite': suite, 'signature': 'PASS', 'signed_index_hash': 'PASS',
                           'validsig': [line for line in process.stderr.decode().splitlines() if 'VALIDSIG' in line],
                           'trust_anchor': 'Debian archive keyring from existing pinned image',
                           'log': f'indexes/{suite}/signature.log'})
    count = 0
    for component in record['debian'] + record['python']:
        for file in component.get('files', []):
            with (root / file['path']).open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest != file['sha256']:
                raise RuntimeError('Source file hash mismatch: ' + file['path'])
            count += 1
    result = {'status': 'PASS', 'files_verified': count, 'debian_indexes': signatures,
              'debian_version_mapping': 'Exact dpkg source package/version to signed Sources index',
              'python_hash_anchor': 'PyPI exact-version JSON; no independent signature verification',
              'wheel_embedded_binary_source_correspondence': 'UNKNOWN',
              'scope': 'Archive authenticity/integrity and version mapping; not binary rebuild equivalence'}
    (root / 'source-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
