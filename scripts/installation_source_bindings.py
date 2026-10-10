"""Exact host-only installation overlays; frozen scientific catalogs stay intact.

This module is an engineering source contract, not a scientific protocol. The
replacement bytes are explicitly reviewed Runtime bytes. A different launcher,
an extra path or any scientific row change requires a new reviewed contract.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path


CATALOGS = {
    'molecular-service': {
        'path': 'locks/molecular-service-source.json', 'count': 20,
        'sha256': '0f1370a8ef1c5e1a8c7b58f310dc6ad2faa0c08e568e19b01cf8e02d7eff29ab',
        'overrides': {
            'scripts/run-molecular-service.py': {
                'base_sha256': '65e32480170402618f31fef2730c7cd156fe393b2eb3c4766b7dc185a8509ad8',
                'sha256': 'a24f8bdf0fca7e0d46c45751c5dc7502ee5ffb4d915b4b0fd8d18712169ceaf9'},
        }},
    'registered-cases': {
        'path': 'locks/registered-cases-source.json', 'count': 37,
        'sha256': '1bc64c322920671b9fe2335b13ea639619e960648422e7eb984c4001f2a481ca',
        'overrides': {
            'scripts/run-registered-case.py': {
                'base_sha256': 'd84fdb1e41c862d0fa8515bac942439bf74907f8d8d470ba7b4b4d1688b5f6d8',
                'sha256': '8f1bb5f96f6a9b983ea8f12326bc2891736ecbdd2b58873445282bd1a5a7eda1'},
        }},
    'protocol-cases': {
        'path': 'locks/protocol-cases-source.json', 'count': 118,
        'sha256': '20708a08ecfa4d74327dd9d5689b20e4faecbbcdb271d962e798616dfc5baa6d',
        'overrides': {
            'scripts/run-protocol-case.py': {
                'base_sha256': 'bd38db248ae016bf4919e0eee4570363458ec0f7e540cd70c8577fed6a1247dd',
                'sha256': 'cbeaaa362af88cfd6529d1785fb336c63f3c8bb514cec6945543f8d49ca0273b'},
        }},
    'high-cost-cases': {
        'path': 'locks/high-cost-source.json', 'count': 107,
        'sha256': 'd8ee6bb0b7880db0f6d40dd38d93b633e1400ff6995f4e56e07042fddd6e7322',
        'overrides': {
            'scripts/run-protocol-case.py': {
                'base_sha256': 'bd38db248ae016bf4919e0eee4570363458ec0f7e540cd70c8577fed6a1247dd',
                'sha256': 'cbeaaa362af88cfd6529d1785fb336c63f3c8bb514cec6945543f8d49ca0273b'},
            'scripts/run-high-cost-case.py': {
                'base_sha256': '76fa7c77f9d4ef61fc60c95b809fcd30ee16b70d9639445461f78694432eca55',
                'sha256': '55c5306ba2ee493e521e533c05d39f5be8870de40dff7da6040680fedaeda607'},
            'tests/test_high_cost_supervisor.py': {
                'base_sha256': '923a6d61569ca76f600246d8e230149812c78c8ecc4bfc8a9d053ab43595c229',
                'sha256': '0a478092ac794c5979cde71772b353a06dc4498fcc41fc253cec3f71e4132b66'},
        }},
}
KIND = 'REVIEWED_ENGINEERING_HOST_REBIND_V2'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def baseline_path(family):
    return CATALOGS[family]['path'].replace('.json', '.installation-baseline.json')


def rows(catalog):
    files = catalog['files']
    if isinstance(files, dict):
        return {name: {'sha256': sha} for name, sha in files.items()}
    if not isinstance(files, list) or any(set(row) != {'path', 'sha256', 'size'} for row in files):
        raise ValueError('Closed source catalog rows required')
    result = {row['path']: {'sha256': row['sha256'], 'size': row['size']} for row in files}
    if len(result) != len(files):
        raise ValueError('Duplicate catalog paths')
    return result


def derive(family, baseline_bytes, read_bytes):
    """Return deterministic derived bytes; no arbitrary current-file acceptance."""
    spec = CATALOGS[family]
    if digest(baseline_bytes) != spec['sha256']:
        raise ValueError('Original source catalog byte identity required: '+family)
    catalog = json.loads(baseline_bytes)
    original = rows(catalog)
    if len(original) != spec['count'] or not set(spec['overrides']) <= set(original):
        raise ValueError('Original catalog path set/count differs')
    overrides = {}
    for name, row in original.items():
        raw = read_bytes(name)
        actual = digest(raw)
        allowed = spec['overrides'].get(name)
        if allowed is not None:
            if row['sha256'] != allowed['base_sha256'] or actual != allowed['sha256']:
                raise ValueError('Unreviewed engineering host bytes: '+name)
            overrides[name] = {**allowed, 'size': len(raw)}
        elif actual != row['sha256'] or ('size' in row and len(raw) != row['size']):
            raise ValueError('Frozen scientific/source bytes differ: '+name)
    derived = deepcopy(catalog)
    if isinstance(derived['files'], dict):
        for name, row in overrides.items():
            derived['files'][name] = row['sha256']
    else:
        for row in derived['files']:
            if row['path'] in overrides:
                row.update(sha256=overrides[row['path']]['sha256'], size=overrides[row['path']]['size'])
    raw = (json.dumps(derived, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode('utf-8')
    binding = {'kind': KIND, 'baseline_sha256': spec['sha256'], 'source_sha256': digest(raw),
               'file_count': spec['count'], 'unchanged_rows': spec['count']-len(overrides),
               'host_overrides': overrides}
    return raw, derived, binding


def bind(root, family):
    root = Path(root)
    spec = CATALOGS[family]
    original = (root/baseline_path(family)).read_bytes()
    def read(name):
        target = root/name
        if target.is_symlink() or not target.is_file():
            raise ValueError('Regular installed source file required: '+name)
        return target.read_bytes()
    raw, catalog, binding = derive(family, original, read)
    if (root/spec['path']).read_bytes() != raw:
        raise ValueError('Only the exact reviewed installation transformation is allowed')
    return catalog, binding


def validate_binding(family, binding, source_sha256):
    spec = CATALOGS[family]
    expected_keys = {'kind', 'baseline_sha256', 'source_sha256', 'file_count', 'unchanged_rows', 'host_overrides'}
    if not isinstance(binding, dict) or set(binding) != expected_keys:
        raise ValueError('Closed installation source binding required')
    fixed = {'kind': KIND, 'baseline_sha256': spec['sha256'], 'source_sha256': source_sha256,
             'file_count': spec['count'], 'unchanged_rows': spec['count']-len(spec['overrides'])}
    if any(type(binding[k]) is not type(v) or binding[k] != v for k, v in fixed.items()):
        raise ValueError('Installation source baseline/scope differs')
    if not isinstance(binding['host_overrides'], dict) or set(binding['host_overrides']) != set(spec['overrides']):
        raise ValueError('Only the reviewed host paths may be rebound')
    for name, allowed in spec['overrides'].items():
        row = binding['host_overrides'][name]
        if (not isinstance(row, dict) or set(row) != {'base_sha256', 'sha256', 'size'}
                or any(row[k] != v for k, v in allowed.items())
                or type(row['size']) is not int or row['size'] < 0):
            raise ValueError('Exact reviewed host identity required: '+name)
