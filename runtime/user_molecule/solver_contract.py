"""Read-only lineage checks for the bounded solver-v2 diagnostic batch."""
import hashlib
import json
import math
from pathlib import Path


def verify_previous_evidence(contract):
    """Refuse a fresh candidate run if prior failed evidence or budget changed."""
    prior = contract['prior_evidence']
    root = Path(prior['evidence_root'])
    for name, field in (('FINAL_DELIVERY_MANIFEST.json', 'previous_manifest_sha256'),
                        ('budget.json', 'previous_budget_sha256')):
        if hashlib.sha256((root/name).read_bytes()).hexdigest() != prior[field]:
            raise ValueError('Prior evidence changed: '+name)
    budget = json.loads((root/'budget.json').read_text(encoding='utf-8'))
    integrity = budget.pop('integrity_sha256')
    encoded = json.dumps(budget,sort_keys=True,separators=(',', ':'),ensure_ascii=False,allow_nan=False).encode('utf-8')
    if hashlib.sha256(encoded).hexdigest() != integrity:
        raise ValueError('Prior budget integrity mismatch')
    runs = list(budget['runs'].values())
    if any(r['state'] != 'SETTLED' for r in runs):
        raise ValueError('Prior process termination unresolved')
    scientific = [r for r in runs if r['identity']['mode'] != 'GUARDED_UNIT_TESTS']
    if len(scientific) != prior['previous_scientific_attempts']:
        raise ValueError('Prior scientific attempt count differs')
    for run in runs:
        value = run['observed_wall_seconds']
        if type(value) not in (int,float) or not math.isfinite(value) or value < 0:
            raise ValueError('Invalid prior wall accounting')
    files = json.loads((root/'FINAL_DELIVERY_MANIFEST.json').read_text(encoding='utf-8'))['files']
    for item in files:
        path = root/item['path']
        if path.stat().st_size != item['size_bytes'] or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Prior delivery payload changed: '+item['path'])
    return {'status':'PASS_PRIOR_EVIDENCE_UNCHANGED', 'prior_runs':len(runs),
            'prior_scientific_attempts':len(scientific), 'verified_files':len(files),
            'prior_consumed_seconds':math.fsum(r['observed_wall_seconds'] for r in runs),
            'prior_manifest_sha256':prior['previous_manifest_sha256'],
            'prior_budget_sha256':prior['previous_budget_sha256']}
