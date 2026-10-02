"""Fetch version-matching upstream sources; no claim of wheel build identity."""
import argparse
import json
from pathlib import Path
import hashlib
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    targets = {
        'libxc-7.0.0.tar.gz': 'https://gitlab.com/libxc/libxc/-/archive/7.0.0/libxc-7.0.0.tar.gz',
        'hdf5-2.0.0.tar.gz': 'https://codeload.github.com/HDFGroup/hdf5/tar.gz/refs/tags/hdf5_2.0.0',
        'Python-3.12.13.tar.xz': 'https://www.python.org/ftp/python/3.12.13/Python-3.12.13.tar.xz',
        'h5py-3.16.0-git.tar.gz': 'https://codeload.github.com/h5py/h5py/tar.gz/refs/tags/3.16.0',
    }
    results = []
    for name, url in targets.items():
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'ai4orgchem-runtime-source-review'})
            with urllib.request.urlopen(request, timeout=90) as response:
                if 'text/html' in response.headers.get('Content-Type', ''):
                    raise ValueError('HTML instead of source archive')
                data = response.read()
            (args.output / name).write_bytes(data)
            results.append({'path': name, 'url': url, 'sha256': hashlib.sha256(data).hexdigest(),
                            'bytes': len(data), 'status': 'ACQUIRED', 'hash_anchor': 'Observed official HTTPS download; not independently signed',
                            'binary_build_correspondence': 'UNKNOWN'})
        except Exception as error:
            results.append({'path': name, 'url': url, 'status': 'NOT_ACQUIRED', 'error': str(error)})
        print(name, results[-1]['status'], flush=True)
    (args.output / 'native-source-candidates.json').write_text(json.dumps(results, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
