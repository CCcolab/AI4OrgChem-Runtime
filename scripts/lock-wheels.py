"""Record exact downloaded linux/amd64 CPython 3.12 wheels and hashes."""
import argparse
import hashlib
import json
import zipfile
from email.parser import BytesParser
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('wheelhouse', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
rows = []
for wheel in sorted(args.wheelhouse.glob('*.whl')):
    with zipfile.ZipFile(wheel) as bundle:
        metadata = next(n for n in bundle.namelist() if n.endswith('.dist-info/METADATA'))
        info = BytesParser().parsebytes(bundle.read(metadata))
    rows.append({'name': info['Name'], 'version': info['Version'], 'filename': wheel.name,
                 'sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(),
                 'requires_dist': info.get_all('Requires-Dist', []),
                 'license': info.get('License-Expression') or info.get('License') or 'UNKNOWN'})
if not rows:
    raise SystemExit('no wheels found')
names = [r['name'].lower().replace('_', '-') for r in rows]
if len(names) != len(set(names)):
    raise SystemExit('duplicate package wheels; use a clean wheelhouse')
text = '# linux/amd64 CPython 3.12 candidate; downloaded wheels hashed\n'
text += ''.join(f"{r['name']}=={r['version']} --hash=sha256:{r['sha256']}\n" for r in rows)
(root / 'locks/requirements-linux-amd64.txt').write_text(text, encoding='utf-8', newline='\n')
(root / 'locks/wheels.lock.json').write_text(json.dumps({'platform': 'linux/amd64', 'python': '3.12',
    'package_source': 'https://pypi.org/simple', 'environment_identity': 'new_candidate', 'wheels': rows}, indent=2)+'\n', newline='\n')
print(f'locked {len(rows)} wheels')
