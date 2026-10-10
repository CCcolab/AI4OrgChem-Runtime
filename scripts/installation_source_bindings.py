"""Exact installation overlays; frozen scientific catalogs stay intact.

This module is an engineering source contract, not a scientific protocol. The
replacement bytes are explicitly reviewed Runtime bytes. A different launcher,
an extra path or any scientific row change requires a new reviewed contract.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path


CATALOGS = {'molecular-service': {'path': 'locks/molecular-service-source.json',
                       'count': 20,
                       'sha256': '0f1370a8ef1c5e1a8c7b58f310dc6ad2faa0c08e568e19b01cf8e02d7eff29ab',
                       'overrides': {'scripts/run-molecular-service.py': {'base_sha256': '65e32480170402618f31fef2730c7cd156fe393b2eb3c4766b7dc185a8509ad8',
                                                                          'sha256': 'a24f8bdf0fca7e0d46c45751c5dc7502ee5ffb4d915b4b0fd8d18712169ceaf9'},
                                     'container/Dockerfile.molecular-service': {'base_sha256': '56abdb82ad54e48035a9c761ae0b0c2afd51787e8e822c272c61c3b15226f1df',
                                                                                'sha256': '198187dd266f6306ddd9acc2aa5102bdf11f59b291233a0f8f027c6b50735e14'},
                                     'container/Dockerfile.molecular-service.dockerignore': {'base_sha256': '0af439893ff9db5ff4c733f086e225ab1e0c48fe3eadf990ee47669f53c33846',
                                                                                             'sha256': '29bcd667373e878767a64af94922cd086b6df6c4e7a13e793cc612af5eec82d9'}}},
 'registered-cases': {'path': 'locks/registered-cases-source.json',
                      'count': 37,
                      'sha256': '1bc64c322920671b9fe2335b13ea639619e960648422e7eb984c4001f2a481ca',
                      'overrides': {'scripts/run-registered-case.py': {'base_sha256': 'd84fdb1e41c862d0fa8515bac942439bf74907f8d8d470ba7b4b4d1688b5f6d8',
                                                                       'sha256': '8f1bb5f96f6a9b983ea8f12326bc2891736ecbdd2b58873445282bd1a5a7eda1'},
                                    'container/Dockerfile.registered-cases': {'base_sha256': '99133bbe25d8c7ea0bbbffa754c2284b628e1e1eef193b92eef09ce7d20a6dda',
                                                                              'sha256': '0047acc67bbc768883001e1e4c1dd65b65e5dd9880c1cc3bce712aea8b72addb'},
                                    'container/Dockerfile.registered-cases.dockerignore': {'base_sha256': '4b861b312205ec5423dff2528ee4f5bc3aed772056411a1550c80a2bedd925d6',
                                                                                           'sha256': '41143dcd163a7e3063e2c112288c0f610635c2b8b8bf5925e82439300927c407'}}},
 'protocol-cases': {'path': 'locks/protocol-cases-source.json',
                    'count': 118,
                    'sha256': '20708a08ecfa4d74327dd9d5689b20e4faecbbcdb271d962e798616dfc5baa6d',
                    'overrides': {'configs/protocol-cases-v1.json': {'base_sha256': '64abfaa9090e72b893458f1fc261b9f0cc4efce9d95458997b9077a95da0d4a4',
                                                                     'sha256': 'f88cc182bcaa9e57e44e8bab5410ac3efa24f3e2d1cec54053144b1d6c890c54'},
                                  'scripts/run-protocol-case.py': {'base_sha256': 'bd38db248ae016bf4919e0eee4570363458ec0f7e540cd70c8577fed6a1247dd',
                                                                   'sha256': 'cbeaaa362af88cfd6529d1785fb336c63f3c8bb514cec6945543f8d49ca0273b'},
                                  'container/Dockerfile.protocol-cases': {'base_sha256': '85b01a69ddf578436f58480b58d8f6e14fee38aabd3671cce6cf16bf870e6a7b',
                                                                          'sha256': 'cc0dd03c7dcfa5d626fe60fc15a0a719f251ae54dd0957f14c9cbe8fab35f90b'},
                                  'container/Dockerfile.protocol-cases.dockerignore': {'base_sha256': '9765b72f62c70a4bfc866135f0df4f57aa3df163bae24abaf8c411bd19f84dab',
                                                                                       'sha256': 'dd45d4d42c95477ff0891751f2ac500afff7956323b8c917513e7c559a71ea83'},
                                  'scripts/ci-protocol-cases.py': {'base_sha256': 'ca4bf93cfec216a33542d3aafe5896840cde3ac13b287bcf5b12a4703a66e87d',
                                                                   'sha256': '86a427aeb0bcc2375c3967bc93fdcae1bc079b85d838e856a2cde183794ebfd2'}}},
 'high-cost-cases': {'path': 'locks/high-cost-source.json',
                     'count': 107,
                     'sha256': 'd8ee6bb0b7880db0f6d40dd38d93b633e1400ff6995f4e56e07042fddd6e7322',
                     'overrides': {'configs/high-cost-cases-v1.json': {'base_sha256': '0fa3a9205eaec088f704bfc4139c15a01ec5a3b684300f37015b7aa464282308',
                                                                       'sha256': '92186233f5d6dc1b44034ace1701e278316c317fbe25fc1a398de48a7585befd'},
                                   'scripts/prepare-high-cost-cases.py': {'base_sha256': '30d274473790e223622383013665a8c99946a1147d260d329724fb2a444677cd',
                                                                          'sha256': 'adedb227b5096fa6de7247bff66aa0f37f6047c78d14a815d5ea3301dff32294'},
                                   'scripts/run-protocol-case.py': {'base_sha256': 'bd38db248ae016bf4919e0eee4570363458ec0f7e540cd70c8577fed6a1247dd',
                                                                    'sha256': 'cbeaaa362af88cfd6529d1785fb336c63f3c8bb514cec6945543f8d49ca0273b'},
                                   'scripts/run-high-cost-case.py': {'base_sha256': '76fa7c77f9d4ef61fc60c95b809fcd30ee16b70d9639445461f78694432eca55',
                                                                     'sha256': '55c5306ba2ee493e521e533c05d39f5be8870de40dff7da6040680fedaeda607'},
                                   'container/Dockerfile.high-cost': {'base_sha256': '1a3221bdc9c34f4d732f0c86e7d7933a83c377daa0787b274fd56edc5143ad2e',
                                                                      'sha256': 'b8a4d5701c8d49efe6c3532cf508cb8551656c5ee7c13ad76ec057f6ec53ad79'},
                                   'container/Dockerfile.high-cost.dockerignore': {'base_sha256': '5f4dd295d257001f5fa82aaff06ac1ab981e5388c88a40feaaf83632d45a1856',
                                                                                   'sha256': 'f93c7d57be359763911872bf69f6f8606d19993961b724882ad97a3e206d64af'},
                                   'scripts/ci-high-cost-cases.py': {'base_sha256': '005cdb60065757692168903694b918812bca306f30180659bd73e9b5e32b7551',
                                                                     'sha256': '2e0942f1c38b138ac4d3b9e23b917815243f1734653a9b6618c8bb0db62aa48d'}}}}

KIND = 'REVIEWED_PUBLIC_PAYLOAD_WITH_LOCAL_TESTS_V4'

# Exact exclusions from the preserved catalogs; no scientific path may be omitted.
EXCLUDED_TESTS = {
    'molecular-service': (),
    'registered-cases': (),
    'protocol-cases': (
        'tests/test_protocol_cases_guard.py', 'tests/test_protocol_cases_p03_p06.py',
        'tests/test_protocol_cases_p07_p08.py', 'tests/test_protocol_cases_p09_p10.py',
        'tests/test_protocol_cases_reporting.py'),
    'high-cost-cases': (
        'tests/test_high_cost_assembly.py', 'tests/test_high_cost_budget.py',
        'tests/test_high_cost_contract.py', 'tests/test_high_cost_guard.py',
        'tests/test_high_cost_p11.py', 'tests/test_high_cost_p12.py',
        'tests/test_high_cost_supervisor.py'),
}


def excluded_rows(family, original):
    names = EXCLUDED_TESTS[family]
    if set(names) != {name for name in original if name.startswith('tests/')}:
        raise ValueError('Exact local-only test path inventory required')
    return {name: original[name] for name in names}


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
    excluded = excluded_rows(family, original)
    overrides = {}
    for name, row in original.items():
        if name in excluded:
            continue
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
        for name in excluded:
            del derived['files'][name]
        for name, row in overrides.items():
            derived['files'][name] = row['sha256']
    else:
        derived['files'] = [row for row in derived['files'] if row['path'] not in excluded]
        for row in derived['files']:
            if row['path'] in overrides:
                row.update(sha256=overrides[row['path']]['sha256'], size=overrides[row['path']]['size'])
    raw = (json.dumps(derived, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode('utf-8')
    binding = {'kind': KIND, 'baseline_sha256': spec['sha256'], 'source_sha256': digest(raw),
               'baseline_file_count': spec['count'], 'file_count': spec['count']-len(excluded),
               'unchanged_rows': spec['count']-len(excluded)-len(overrides),
               'excluded_test_rows': excluded, 'host_overrides': overrides}
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
    expected_keys = {'kind', 'baseline_sha256', 'source_sha256', 'file_count', 'unchanged_rows',
                     'host_overrides', 'baseline_file_count', 'excluded_test_rows'}
    if not isinstance(binding, dict) or set(binding) != expected_keys:
        raise ValueError('Closed installation source binding required')
    fixed = {'kind': KIND, 'baseline_sha256': spec['sha256'], 'source_sha256': source_sha256,
             'baseline_file_count': spec['count'], 'file_count': spec['count']-len(EXCLUDED_TESTS[family]),
             'unchanged_rows': spec['count']-len(EXCLUDED_TESTS[family])-len(spec['overrides'])}
    if any(type(binding[k]) is not type(v) or binding[k] != v for k, v in fixed.items()):
        raise ValueError('Installation source baseline/scope differs')
    root = Path(__file__).resolve().parents[1]
    baseline = root/baseline_path(family)
    if not baseline.is_file():
        baseline = root/spec['path']
    baseline_bytes = baseline.read_bytes()
    if digest(baseline_bytes) != spec['sha256']:
        raise ValueError('Original source catalog identity required')
    original = rows(json.loads(baseline_bytes))
    if binding['excluded_test_rows'] != excluded_rows(family, original):
        raise ValueError('Exact excluded test identities required')
    if not isinstance(binding['host_overrides'], dict) or set(binding['host_overrides']) != set(spec['overrides']):
        raise ValueError('Only the reviewed host paths may be rebound')
    for name, allowed in spec['overrides'].items():
        row = binding['host_overrides'][name]
        if (not isinstance(row, dict) or set(row) != {'base_sha256', 'sha256', 'size'}
                or any(row[k] != v for k, v in allowed.items())
                or type(row['size']) is not int or row['size'] < 0):
            raise ValueError('Exact reviewed host identity required: '+name)
