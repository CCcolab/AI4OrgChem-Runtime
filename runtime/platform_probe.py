"""Small, offline container acceptance probe; no scientific calculations."""
import argparse
import json
import os
import uuid
from pathlib import Path

from runtime.cli import save, verify_source
from runtime.resources import memory_snapshot

parser = argparse.ArgumentParser()
parser.add_argument('--readonly-file', type=Path)
args = parser.parse_args()
checks = {'non_root': os.getuid() == 10001}
for name in ('/opt/ai4orgchem/evidence/P01-P14/P14/result.json', '/opt/ai4orgchem/software/pyproject.toml'):
    try:
        with open(name, 'r+b'):
            pass
        checks['readonly:' + name] = False
    except PermissionError:
        checks['readonly:' + name] = True
verify_source(Path('/opt/ai4orgchem'))
checks['source_hashes'] = True
if args.readonly_file:
    checks['readonly_mount_readable'] = args.readonly_file.read_text() == 'ai4orgchem-readonly-probe'
    try:
        with args.readonly_file.open('r+b'):
            pass
        checks['readonly_mount'] = False
    except (PermissionError, OSError):
        checks['readonly_mount'] = True
record = {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks, 'memory': memory_snapshot()}
output = Path('/work') / ('platform-probe-' + uuid.uuid4().hex + '.json')
save(output, record)
print(json.dumps({'output': str(output), **record}))
raise SystemExit(0 if record['status'] == 'PASS' else 1)
