"""Acquire sources for this runtime inventory, without claiming binary equivalence."""
import argparse
import concurrent.futures
import hashlib
import json
import lzma
from pathlib import Path
import urllib.parse
import urllib.request


def fetch(url, path, expected=None):
    if path.exists() and expected and hashlib.sha256(path.read_bytes()).hexdigest() == expected:
        return expected
    request = urllib.request.Request(url, headers={'User-Agent': 'ai4orgchem-runtime-source-review'})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()
        if 'text/html' in response.headers.get('Content-Type', ''):
            raise ValueError('HTML instead of source material')
    digest = hashlib.sha256(data).hexdigest()
    if expected and digest != expected:
        raise ValueError('SHA256 mismatch: ' + url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return digest


def paragraphs(text):
    for block in text.split('\n\n'):
        record = {}
        key = None
        for line in block.splitlines():
            if line.startswith(' ') and key:
                record[key] += '\n' + line.strip()
            elif ': ' in line:
                key, value = line.split(': ', 1)
                record[key] = value
            elif line.endswith(':'):
                key = line[:-1]
                record[key] = ''
        if record:
            yield record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    requirements = json.loads((root / 'validation/license-materials-manifest.json').read_text(encoding='utf-8-sig'))['debian_source_requirements']
    targets = {(r['package'], r['version']): r for r in requirements}
    matched = {}
    indexes, failures, results = [], [], []
    for base, suite in [('https://deb.debian.org/debian', 'bookworm'),
                        ('https://deb.debian.org/debian', 'bookworm-updates'),
                        ('https://security.debian.org/debian-security', 'bookworm-security')]:
        try:
            local = output / 'indexes' / suite
            release_url = f'{base}/dists/{suite}/InRelease'
            release_hash = fetch(release_url, local / 'InRelease')
            url = f'{base}/dists/{suite}/main/source/Sources.xz'
            digest = fetch(url, local / 'Sources.xz')
            indexes.append({'suite': suite, 'url': url, 'sha256': digest,
                            'inrelease_sha256': release_hash, 'signature': 'NOT_VERIFIED'})
            for record in paragraphs(lzma.decompress((local / 'Sources.xz').read_bytes()).decode()):
                key = record.get('Package'), record.get('Version')
                if key in targets:
                    matched[key] = (base, record, suite)
        except Exception as error:
            failures.append({'scope': suite, 'error': str(error)})
    def acquire(item):
        key, requirement = item
        if key not in matched:
            return {**requirement, 'status': 'NOT_FOUND_IN_CURRENT_INDEX',
                    'next_step': 'retrieve exact historical source from Debian snapshot; do not substitute a newer version'}
        base, record, suite = matched[key]
        files = []
        try:
            for line in record['Checksums-Sha256'].splitlines():
                if not line.strip():
                    continue
                digest, size, name = line.split()
                if '/' in name or '\\' in name or name in {'.', '..'}:
                    raise ValueError('Invalid archive filename')
                url = base + '/' + record['Directory'] + '/' + name
                relative = 'debian/' + key[0] + '/' + urllib.parse.quote(key[1], safe='') + '/' + name
                actual = fetch(url, output / relative, digest)
                if (output / relative).stat().st_size != int(size):
                    raise ValueError('Source size mismatch')
                files.append({'path': relative, 'url': url, 'sha256': actual, 'bytes': int(size)})
            return {**requirement, 'status': 'ACQUIRED_INDEX_HASH_VERIFIED', 'suite': suite,
                    'files': files, 'binary_build_correspondence': 'UNKNOWN', 'signature': 'NOT_VERIFIED'}
        except Exception as error:
            return {**requirement, 'status': 'INCOMPLETE', 'files': files, 'error': str(error)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(acquire, targets.items()):
            results.append(result)
            print('Debian', result['package'], result['status'], flush=True)
    wheels = json.loads((root / 'locks/wheels.lock.json').read_text(encoding='utf-8-sig'))['wheels']
    python_sources = []
    for wheel in wheels + [{'name': 'pip', 'version': '25.0.1'}]:
        name, version = wheel['name'], wheel['version']
        try:
            url = f'https://pypi.org/pypi/{name}/{version}/json'
            metadata_path = output / 'pypi' / name / 'metadata.json'
            fetch(url, metadata_path)
            metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
            sdists = [f for f in metadata['urls'] if f['packagetype'] == 'sdist']
            if not sdists:
                raise ValueError('No source distribution for exact version')
            files = []
            for source in sdists:
                relative = 'pypi/' + name + '/' + source['filename']
                digest = fetch(source['url'], output / relative, source['digests']['sha256'])
                files.append({'path': relative, 'url': source['url'], 'sha256': digest})
            python_sources.append({'name': name, 'version': version, 'status': 'SDIST_ACQUIRED',
                                   'files': files, 'wheel_binary_correspondence': 'UNKNOWN'})
        except Exception as error:
            python_sources.append({'name': name, 'version': version, 'status': 'NOT_ACQUIRED', 'error': str(error)})
        print('PyPI', name, python_sources[-1]['status'], flush=True)
    result = {'schema_version': 1, 'indexes': indexes, 'index_failures': failures,
              'debian': results, 'python': python_sources,
              'binary_build_correspondence': 'UNKNOWN', 'public_image_distribution': 'BLOCKED',
              'scope': 'Exact source-version acquisitions; no scientific runs, rebuild or release'}
    (output / 'source-acquisition.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'debian_acquired': sum(r['status']=='ACQUIRED_INDEX_HASH_VERIFIED' for r in results),
                      'debian_required': len(results), 'python_acquired': sum(r['status']=='SDIST_ACQUIRED' for r in python_sources)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
