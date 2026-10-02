"""Map installed vendor notices/code to acquired exact parent source distributions."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    raw = json.loads(args.evidence.read_text(encoding='utf-8-sig'))
    acquisition = json.loads((args.sources / 'source-acquisition.json').read_text(encoding='utf-8'))
    archives = {}
    for parent in ['pip', 'setuptools']:
        entry = next(p for p in acquisition['python'] if p['name'] == parent)
        with tarfile.open(args.sources / entry['files'][0]['path']) as archive:
            archives[parent] = {}
            for member in archive.getmembers():
                if not member.isfile() or '/' not in member.name:
                    continue
                relative = member.name.split('/', 1)[1]
                if relative.startswith('src/'):
                    relative = relative[4:]
                archives[parent][relative] = archive.extractfile(member).read()
    comparisons = []
    for path, digest in raw['python_source_hashes'].items():
        relative = path.split('/site-packages/', 1)[1]
        parent = relative.split('/')[0]
        data = archives[parent].get(relative)
        comparisons.append({'path': path, 'sha256': digest,
                            'status': 'MATCH' if data is not None and hashlib.sha256(data).hexdigest() == digest
                            else ('MISMATCH' if data is not None else 'NOT_IN_PARENT_SDIST')})
    supplemental = {}
    components = raw['components']
    for component in components:
        if component['parent'] != 'pip':
            continue
        name = component['name'].lower().replace('-', '_')
        directory = 'pkg_resources' if name == 'setuptools' else name
        files = []
        for relative, data in archives['pip'].items():
            basename = relative.rsplit('/', 1)[-1]
            if (relative.startswith('pip/_vendor/' + directory + '/') or
                    relative == 'pip/_vendor/' + directory + '.LICENSE') and (basename.upper().startswith(('LICENSE', 'COPYING', 'NOTICE', 'AUTHORS', 'COPYRIGHT')) or basename.upper().endswith('.LICENSE')):
                target = args.output / 'pip-parent-sdist' / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                files.append(str(target.relative_to(args.output)).replace('\\', '/'))
                supplemental[files[-1]] = {'sha256': hashlib.sha256(data).hexdigest(),
                                         'source': 'pip 25.0.1 hash-verified sdist', 'text': data.decode('utf-8', errors='replace')}
        component['supplemental_notice_files'] = files
        component['source_notice_status'] = 'MATCHING_PARENT_SDIST_NOTICE_FOUND' if files else 'UNKNOWN'
    for component in components:
        prefix = component['environment'] + '/' + component['parent'] + '/_vendor/'
        module = component['name'].lower().replace('-', '_')
        if component['parent'] == 'pip' and module == 'setuptools':
            module = 'pkg_resources'
        selected = [c for c in comparisons if c['path'].startswith(prefix + module + '/')
                    or c['path'] == prefix + module + '.py']
        component['python_source_comparison'] = {'files': len(selected), 'matched': sum(c['status']=='MATCH' for c in selected),
                                                 'not_matched': [c for c in selected if c['status']!='MATCH']}
        component['obligations'] = 'Retain complete original notices; preserve applicable source terms; parent sources supplied locally, public retrieval not enabled'
    result = {'components': components, 'actual_image_notices': raw['notices'],
              'supplemental_notices': supplemental, 'source_comparisons': comparisons,
              'source_summary': {'files': len(comparisons), 'matched': sum(c['status']=='MATCH' for c in comparisons),
                                 'unmatched': sum(c['status']!='MATCH' for c in comparisons)},
              'scope': 'Installed Python source hashes and original notices; not static/native code certification'}
    (args.output / 'vendor-source-mapping.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'components': len(components), 'supplemental_notices': len(supplemental), **result['source_summary']}))


if __name__ == '__main__':
    main()
