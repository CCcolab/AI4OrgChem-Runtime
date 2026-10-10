"""Selected locked-file byte review, never a scientific validator or runner.

The registry references the original 28511f3 source. No source tree is guessed,
downloaded, imported or executed. Missing files remain explicitly unverified.
"""
import copy
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat

ROOT = Path(__file__).resolve().parents[2]
SOURCE_COMMIT = '28511f3d84fa65707a107cde1e8121a7b4334ecb'
SOURCE_LOCK_SHA = 'd40413b83446f33d51b95f3c3f392193e9a728cee611c45e87bfb28daedc5fa5'
FILE_LOCK_SHA = '352c23adc331e6228abf77fdab1e5c2fac09c9b20b91ad8fb60a4aea38f2a2cc'
SCOPE = 'LOCAL_READ_ONLY_SELECTED_LOCKED_EVIDENCE_BYTES_NOT_SCIENTIFIC_REVALIDATION'
P14_TASKS = ('p14-smoke', 'p14-equivalence', 'p14-fixed', 'p14-optimize', 'p14-classify')
P14_PROGRAMS = ('run_p14_benzotricyclobutadiene_smoke.py',
                'validate_p14_memory_controlled_conditional_scf.py',
                'run_p14_benzotricyclobutadiene_source_level_fixed_geometry.py',
                'run_p14_benzotricyclobutadiene_production_optimization.py',
                'classify_p14_strained_aromatic_pi_distortivity.py')
MAX_VIEW_BYTES = 4 * 1024 * 1024


class CatalogError(ValueError):
    """Invalid ID, unsafe path or inconsistent local registry; CLI exit40."""


class _LegacyNonfiniteJSON(CatalogError):
    """A frozen historical format limitation; never a numeric replacement."""


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(raw, *, _allow_legacy_tokens=False):
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise CatalogError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    def constant(value):
        if _allow_legacy_tokens:
            return None  # Grammar-only check; this parsed value is never exported.
        raise _LegacyNonfiniteJSON('Nonfinite JSON value: ' + value)
    def floating(value):
        result = float(value)
        if not math.isfinite(result):
            if _allow_legacy_tokens:
                return None
            raise _LegacyNonfiniteJSON('Nonfinite JSON numeric token: ' + value)
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant, parse_float=floating)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CatalogError('Invalid UTF-8 JSON evidence') from exc


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def _relative(value):
    if (not isinstance(value, str) or not value or '\\' in value or ':' in value
            or '\0' in value or PurePosixPath(value).is_absolute()
            or any(part in ('', '.', '..') for part in value.split('/'))):
        raise CatalogError('Canonical relative POSIX evidence path required')
    return value


def _no_reparse(path):
    """Check every existing ancestor before resolution; also reject junctions."""
    path = Path(os.path.abspath(os.fspath(path)))
    for part in reversed((path, *path.parents)):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if (stat.S_ISLNK(info.st_mode)
                or getattr(info, 'st_file_attributes', 0) & 0x400
                or (hasattr(part, 'is_junction') and part.is_junction())):
            raise CatalogError('Symbolic link/reparse reference refused: ' + str(part))
    return path


def _file_path(root, relative):
    root = _no_reparse(root)
    candidate = _no_reparse(root / _relative(relative))
    if not candidate.is_relative_to(root):
        raise CatalogError('Evidence path escapes the explicit source directory')
    return candidate


def _catalog(runtime_root=ROOT):
    root = _no_reparse(runtime_root)
    lock_raw = _file_path(root, 'locks/source.lock.json').read_bytes()
    files_raw = _file_path(root, 'locks/source-files.sha256.json').read_bytes()
    registry_raw = _file_path(root, 'configs/propositions-v1.json').read_bytes()
    source, files, registry = _json(lock_raw), _json(files_raw), _json(registry_raw)
    if (_sha(_canonical(source)) != SOURCE_LOCK_SHA
            or _sha(_canonical(files)) != FILE_LOCK_SHA
            or source.get('source_commit') != SOURCE_COMMIT or len(files) != 588):
        raise CatalogError('Frozen original source lock identity differs')
    if (registry.get('schema_version') != 'proposition-catalog-v1'
            or registry.get('source_commit') != SOURCE_COMMIT
            or registry.get('source_lock_canonical_sha256') != SOURCE_LOCK_SHA
            or registry.get('source_file_lock_canonical_sha256') != FILE_LOCK_SHA
            or registry.get('source_file_lock_count') != 588
            or registry.get('scope') != SCOPE
            or registry.get('online_required') is not False
            or registry.get('default_source_directory') is not None):
        raise CatalogError('Registry scope/source identity differs')
    cases = registry.get('cases')
    if (not isinstance(cases, list) or [case.get('id') for case in cases]
            != ['P%02d' % i for i in range(1, 15)]):
        raise CatalogError('Exactly ordered P01--P14 registry entries required')
    for case in cases:
        if (case.get('capability') != 'READ_FROZEN_EVIDENCE_ONLY'
                or case.get('calculation') != 'NOT_EXECUTED'
                or case.get('constraints', {}).get('arithmetic_validation') != 'NOT_EXECUTED'
                or case.get('constraints', {}).get('new_scientific_verdict') != 'NOT_GENERATED'):
            raise CatalogError('Registry must not grant computation or science acceptance')
        tasks = case.get('runtime_task_references', [])
        if case['id'] == 'P14':
            if [row.get('task') for row in tasks] != list(P14_TASKS):
                raise CatalogError('P14 task references differ from the five-task whitelist')
            if [row.get('script_path') for row in tasks] != ['software/scripts/' + name for name in P14_PROGRAMS]:
                raise CatalogError('P14 references must use the original five registered programs')
        elif tasks:
            raise CatalogError('This reader has no general proposition execution dispatch')
        if any(row.get('execution') != 'NOT_STARTED_BY_THIS_READER' for row in tasks):
            raise CatalogError('Task references cannot execute')
    if [item['id'] for item in cases[10]['items']] != ['P11-A', 'P11-B']:
        raise CatalogError('P11 must preserve its two distinct evidence items')
    if [item['id'] for item in cases[11]['items']] != ['N12', 'N14', 'N16']:
        raise CatalogError('P12 must preserve its three same-basis evidence points')
    for assets in [registry['common_assets'], *(case['assets'] for case in cases)]:
        if not assets or len({row['path'] for row in assets}) != len(assets):
            raise CatalogError('Unique, nonempty selected asset list required')
        for row in assets:
            path = _relative(row.get('path'))
            if path not in files or row.get('sha256') != files[path]:
                raise CatalogError('Evidence reference is not in the frozen source file lock')
            if not all(isinstance(row.get(key), str) and row[key] for key in ('role', 'item', 'relation')):
                raise CatalogError('Explicit asset role/item/current-or-history relation required')
    histories = {
        'P05': ('result.jsonl', 'HISTORICAL_ANCHOR'),
        'P11': ('substituent-fixed-geometry-audit-result.json', 'HISTORICAL_SUPERSEDED_DIAGNOSTIC'),
        'P12': ('result-v0.3.1-historical.json', 'HISTORICAL_NOT_CURRENT_CLASSIFICATION')}
    for proposition, (filename, relation) in histories.items():
        case = next(row for row in cases if row['id'] == proposition)
        selected = [row for row in case['assets'] if row['path'] == 'evidence/P01-P14/' + proposition + '/' + filename]
        if len(selected) != 1 or selected[0]['relation'] != relation:
            raise CatalogError('Frozen historical material cannot be relabeled as current evidence')
    identities = {'registry_sha256': _sha(registry_raw),
                  'source_lock_raw_sha256': _sha(lock_raw),
                  'source_file_lock_raw_sha256': _sha(files_raw),
                  'source_lock_canonical_sha256': SOURCE_LOCK_SHA,
                  'source_file_lock_canonical_sha256': FILE_LOCK_SHA}
    return registry, files, identities


def _select(registry, proposition_id):
    if not isinstance(proposition_id, str) or re.fullmatch(r'P(?:0[1-9]|1[0-4])', proposition_id) is None:
        raise CatalogError('Unknown proposition ID; expected exact P01--P14')
    return next(case for case in registry['cases'] if case['id'] == proposition_id)


def list_propositions(*, runtime_root=ROOT):
    registry, _, identities = _catalog(runtime_root)
    return {'schema_version': 'proposition-list-v1', 'scope': SCOPE,
            'source_commit': SOURCE_COMMIT, 'source_status': 'NOT_VERIFIED',
            'scientific_validation': 'NOT_EXECUTED', 'identities': identities,
            'cases': [{key: copy.deepcopy(case[key]) for key in
                       ('id', 'title', 'evidence_identity', 'capability', 'items', 'runtime_task_references')}
                      for case in registry['cases']]}


def _view(raw, suffix, *, allow_locked_legacy_nonfinite=False):
    if len(raw) > MAX_VIEW_BYTES:
        raise CatalogError('Selected evidence exceeds the bounded reader size')
    if suffix in ('.json', '.jsonl'):
        try:
            if suffix == '.json':
                return 'json', _json(raw)
            return 'jsonl', [_json(line) for line in raw.splitlines() if line.strip()]
        except _LegacyNonfiniteJSON:
            if not allow_locked_legacy_nonfinite:
                raise
            # Check the entire old grammar/duplicate keys, but discard the parse.
            # Retain the original UTF-8 text with Infinity/NaN exactly as recorded.
            for line in ([raw] if suffix == '.json' else [line for line in raw.splitlines() if line.strip()]):
                _json(line, _allow_legacy_tokens=True)
            return 'legacy-' + suffix[1:] + '-text', raw.decode('utf-8')
    try:
        return 'text', raw.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise CatalogError('Selected document is not UTF-8 text') from exc


def _inspect_assets(source_dir, assets, *, include_content):
    """Trusted registry rows only. Status describes bytes, never scientific truth."""
    root = None if source_dir is None else _no_reparse(source_dir)
    if root is not None and root.exists() and not root.is_dir():
        raise CatalogError('Explicit source must be a directory')
    rows, verified_bytes = [], {}
    for spec in assets:
        row = {**copy.deepcopy(spec), 'status': 'MISSING', 'size_bytes': None,
               'actual_sha256': None, 'content_kind': None, 'content': None}
        if root is None:
            row['reason'] = 'EXPLICIT_LOCAL_SOURCE_REQUIRED'
        else:
            path = _file_path(root, spec['path'])
            if not path.exists():
                row['reason'] = 'LOCAL_FILE_MISSING'
            elif not path.is_file():
                raise CatalogError('Registered evidence is not a regular file: ' + spec['path'])
            else:
                raw = path.read_bytes()
                row.update(size_bytes=len(raw), actual_sha256=_sha(raw))
                if row['actual_sha256'] != spec['sha256']:
                    row.update(status='NOT_VERIFIED', reason='LOCKED_BYTES_MISMATCH')
                else:
                    row.update(status='VERIFIED_LOCKED_BYTES', reason=None)
                    verified_bytes[spec['path']] = raw
                    if include_content and spec['role'] != 'program-reference':
                        row['content_kind'], row['content'] = _view(raw, path.suffix, allow_locked_legacy_nonfinite=True)
                        if row['content_kind'].startswith('legacy-'):
                            row['content_parse_limitation'] = 'LOCK_MATCHED_NONFINITE_LEGACY_JSON_RETAINED_AS_EXACT_TEXT_NOT_NORMALIZED_OR_ARITHMETICALLY_VALIDATED'
        rows.append(row)
    if any(row['status'] == 'NOT_VERIFIED' for row in rows):
        status, code = 'NOT_VERIFIED', 40
    elif any(row['status'] == 'MISSING' for row in rows):
        status, code = 'MISSING', 20
    else:
        status, code = 'VERIFIED_LOCKED_BYTES', 0
    return root, rows, verified_bytes, status, code


def show_proposition(proposition_id, *, source_dir=None, runtime_root=ROOT, include_content=True):
    registry, _, identities = _catalog(runtime_root)
    case = _select(registry, proposition_id)
    assets = [*registry['common_assets'], *case['assets']]
    root, rows, _, status, code = _inspect_assets(source_dir, assets, include_content=include_content)
    return {'schema_version': 'proposition-review-v1', 'proposition_id': proposition_id,
            'scope': SCOPE, 'source_commit': SOURCE_COMMIT,
            'source_commit_identity_scope': 'SELECTED_FILES_MATCH_EXPECTED_COMMIT_LOCK_NOT_GIT_CHECKOUT_AUTHENTICATION',
            'source_directory': None if root is None else str(root),
            'status': status, 'exit_code': code, 'selected_file_count': len(rows),
            'verified_file_count': sum(row['status'] == 'VERIFIED_LOCKED_BYTES' for row in rows),
            'identities': identities, 'catalog_entry': copy.deepcopy(case), 'files': rows,
            'scientific_validation': 'NOT_EXECUTED', 'scientific_recomputation': 'NOT_EXECUTED',
            'new_scientific_verdict': None, 'runtime_task_execution': 'NOT_EXECUTED',
            'full_source_tree_verified': False,
            'statement_origin': 'FROZEN_DECLARATIONS_REFERENCED_FROM_ORIGINAL_PROJECT',
            'boundary': 'Byte matching and reading old declarations do not reproduce their arithmetic or certify their scientific conclusions.'}


def _summary(record, *, output_dir=None):
    case = record['catalog_entry']
    lines = ['# ' + case['title'], '',
             '本地冻结证据读取状态：`' + record['status'] + '`。',
             '来源锁提交：`' + SOURCE_COMMIT + '`；只核对所选文件字节。', '',
             '以下是原项目已有范围声明，本次不产生新的科学判定：',
             case['frozen_scope_statement'], '',
             '本入口不执行计算、命题算术验证或 Runtime 任务；不认证整个源码树。', '',
             '| 材料 | 子项 | 记录角色 | 字节状态 |', '|---|---|---|---|']
    for row in record['files']:
        label = row['path']
        if record['source_directory'] and row['status'] == 'VERIFIED_LOCKED_BYTES':
            target = (Path(record['source_directory']) / row['path']).as_posix()
            label = '[' + row['path'].replace(']', '\\]') + '](<' + target + '>)'
        lines.append('| ' + label + ' | ' + row['item'] + ' | ' + row['relation'] + ' | ' + row['status'] + ' |')
    if case['runtime_task_references']:
        lines += ['', 'P14已有任务白名单（仅展示，不启动）：', '']
        lines += ['- `' + row['task'] + '`：' + row['scope'] for row in case['runtime_task_references']]
    legacy = [row['path'] for row in record['files'] if (row['content_kind'] or '').startswith('legacy-')]
    if legacy:
        lines += ['', '以下旧JSON含Infinity等非有限标记，无法按标准JSON数值判读；仅逐字保留文本，本次不作JSON语义或能量审计：', '']
        lines += ['- `' + path + '`' for path in legacy]
    if record['proposition_id'] == 'P11':
        lines += ['', 'P11-A/B分开读取；旧固定几何记录仅作历史审计。']
    if record['proposition_id'] == 'P12':
        lines += ['', 'P12历史结果不作为当前N12/N14/N16三个同基组账本的判定。']
    lines += ['', '公开、平台支持及用户分子 Compute 状态不因本次读取改变。', '']
    return '\n'.join(lines)


def review_proposition(proposition_id, *, source_dir=None, output_dir, runtime_root=ROOT):
    """Export to one fresh external directory; no copies are written into source."""
    output = _no_reparse(output_dir)
    if output.exists():
        raise CatalogError('Output must be a fresh directory; prior records are never overwritten')
    runtime = _no_reparse(runtime_root)
    source = None if source_dir is None else _no_reparse(source_dir)
    for protected in (runtime, source):
        if protected is not None and (output.is_relative_to(protected) or protected.is_relative_to(output)):
            raise CatalogError('Review output must remain outside source and runtime trees')
    record = show_proposition(proposition_id, source_dir=source, runtime_root=runtime)
    # Re-read every observed file before export; hash equality is checked again.
    if source is not None:
        for row in record['files']:
            if row['actual_sha256'] is not None:
                path = _file_path(source, row['path'])
                if not path.is_file() or _sha(path.read_bytes()) != row['actual_sha256']:
                    raise CatalogError('Source changed during read-only review; no export created')
    output.mkdir(parents=True, exist_ok=False)
    record['output_directory'] = str(output)
    observed_count = sum(row['actual_sha256'] is not None for row in record['files'])
    record['observed_selected_file_count'] = observed_count
    record['source_selected_files_unchanged_at_export'] = True if observed_count else None
    record['export_files'] = ['review.public.json', 'summary.md']
    with (output / 'review.public.json').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    with (output / 'summary.md').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(_summary(record, output_dir=output))
    return record
