"""Collect notices from audited image evidence; fetch official supplemental materials.

This does not certify corresponding-source completeness or change the image.
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fetch', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    evidence = json.loads(args.evidence.read_text(encoding='utf-8-sig'))
    records = []
    for name, value in sorted(evidence['license_texts'].items()):
        relative = 'image-notices/' + name.lstrip('/')
        data = value['text'].encode('utf-8')
        target = args.output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        records.append({'path': relative, 'sha256': hashlib.sha256(data).hexdigest(),
                        'origin': name, 'evidence_sha256': value['sha256'],
                        'scope': 'text extracted from audited image; not original binary bytes'})
    requests = {
        'pyscf-CMakeLists.txt': 'https://raw.githubusercontent.com/pyscf/pyscf/v2.14.0/pyscf/lib/CMakeLists.txt',
        'pyscf-libxcfun.patch': 'https://raw.githubusercontent.com/pyscf/pyscf/v2.14.0/pyscf/lib/libxcfun.patch',
        'xcfun-LICENSE.md': 'https://raw.githubusercontent.com/dftlibs/xcfun/a89b783497d4fe146b477ac7a053303ce4189e9a/LICENSE.md',
        'xcfun-source.tar.gz': 'https://codeload.github.com/dftlibs/xcfun/tar.gz/a89b783497d4fe146b477ac7a053303ce4189e9a',
        'libcint-LICENSE': 'https://raw.githubusercontent.com/sunqm/libcint/v6.1.3/LICENSE',
        'libcint-source.tar.gz': 'https://codeload.github.com/sunqm/libcint/tar.gz/refs/tags/v6.1.3',
        'hdf5-LICENSE': 'https://raw.githubusercontent.com/HDFGroup/hdf5/hdf5_2.0.0/LICENSE',
        'libxc-COPYING': 'https://gitlab.com/libxc/libxc/-/raw/7.0.0/COPYING',
    }
    failures = []
    if args.fetch:
        for name, url in requests.items():
            try:
                request = urllib.request.Request(url, headers={'User-Agent': 'ai4orgchem-runtime-license-review'})
                with urllib.request.urlopen(request, timeout=45) as response:
                    data = response.read()
                    if 'text/html' in response.headers.get('Content-Type', ''):
                        raise ValueError('HTML response is not accepted as license/source material')
                relative = 'upstream/' + name
                target = args.output / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                records.append({'path': relative, 'sha256': hashlib.sha256(data).hexdigest(),
                                'origin': url, 'scope': 'upstream recipe/version candidate; binary correspondence UNKNOWN'})
            except Exception as error:
                failures.append({'origin': url, 'error': str(error), 'status': 'NOT_ACQUIRED'})
    sources = {}
    for component in evidence['components']:
        if component.get('kind') == 'debian':
            package, version = component['source_package']
            sources.setdefault((package, version), []).append(component['name'])
    manifest = {'schema_version': 1, 'image_id': 'sha256:ddc45b1fe500ed3d5ed30520eb4e49f3969cb69f02121f28e2ff851f7a724f54',
                'input_sha256': hashlib.sha256(args.evidence.read_bytes()).hexdigest(),
                'corresponding_source_complete': False, 'public_release_readiness': 'BLOCKED',
                'files': records, 'fetch_failures': failures,
                'debian_source_requirements': [{'package': p, 'version': v, 'binary_packages': names,
                    'status': 'NOT_ACQUIRED', 'required': 'exact .dsc, original tarballs, Debian patches and build materials; verify archive checksums'}
                    for (p, v), names in sorted(sources.items())]}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with zipfile.ZipFile(args.output / 'third-party-materials.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for entry in records:
            archive.write(args.output / entry['path'], entry['path'])
        archive.write(args.output / 'manifest.json', 'manifest.json')
    with zipfile.ZipFile(args.output / 'third-party-materials.zip') as archive:
        for entry in records:
            if hashlib.sha256(archive.read(entry['path'])).hexdigest() != entry['sha256']:
                raise RuntimeError('Archive hash mismatch: ' + entry['path'])
    print(json.dumps({'files': len(records), 'fetch_failures': failures, 'source_requirements': len(sources),
                      'zip_integrity': 'PASS', 'corresponding_source_complete': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
