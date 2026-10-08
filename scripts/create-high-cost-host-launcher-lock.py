"""Freeze only the final-evidence host patch; do not replace the worker lock."""
from pathlib import Path
import importlib.util
import json

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('high_cost_host_lock_generator',ROOT/'scripts/run-high-cost-case.py')
host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
value=host.make_host_launcher_lock()
path=host.HOST_LAUNCHER_LOCK
if path.exists() and host.read_json(path)!=value:
    raise SystemExit('Existing host launcher lock differs; review before replacement')
if not path.exists():host.save(path,value)
print(json.dumps({'path':str(path),'host_launcher_lock_sha256':host.digest(path),
                  'base_source_sha256':value['base_source_sha256'],'image_id':value['image_id'],
                  'scope':value['scope']},sort_keys=True))
