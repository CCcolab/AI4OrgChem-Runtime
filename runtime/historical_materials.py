"""Exact local W05 archive bytes, not public policy or scientific approval.

Only the two explicitly audited documents are supported. No Git, engines,
scientific libraries, repairs, or network operations are invoked at runtime.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_ARCHIVE_ONLY = 'HISTORICAL_MATERIALS_LOCAL_ARCHIVE_ONLY'
HISTORY_DIR = 'validation/user-molecule/w05/historical-source-materials'
MANIFEST_PATH = HISTORY_DIR + '/mapping.json'
SOURCE_INDEX_PATH = 'validation/user-molecule/w05/source-index.json'
SOURCE_COMMIT = '55726d4ee0f76dee5065f47fc5f55824b0083db3'
INDEX_COMMIT = 'a54f4222277df857d3fe3be993d687a88fa3a806'
INDEX_BLOB = '48cb8fc9a922498edbc9d6f853331e90d91b0f6a'
INDEX_CANONICAL_SHA256 = '11ab9a3a1b789a662964cc03ae17ff57d7b61befa1454a9f4532b3f36ac9a327'
PROCESS_UPDATE_COMMIT = '03acd478974d24766aa578fb173a2ffdc95a2cfe'
MATERIALS = (
    {'owner': 'runtime', 'original_path': 'docs/USER_MOLECULE_TECHNICAL_PLAN_zh-CN.md',
     'source_commit': SOURCE_COMMIT, 'git_blob_id': '54fc8dbddf224f26ab8cca09b5ba56cc952e6c60',
     'sha256': '6c0fa47cb0e8acac602ebb3c4c1a2268b5b3cb80ad0d443e5c39922d85b310a6',
     'size_bytes': 27759,
     'snapshot_path': HISTORY_DIR + '/USER_MOLECULE_TECHNICAL_PLAN_55726d4_zh-CN.md',
     'byte_policy': 'EXACT_ORIGINAL_GIT_BLOB_BYTES_NO_TRANSFORMATION'},
    {'owner': 'runtime', 'original_path': 'docs/USER_MOLECULE_ENTRY_DESIGN_zh-CN.md',
     'source_commit': SOURCE_COMMIT, 'git_blob_id': 'd83c59ebe87228f514032c810b07b4bbe44e61ba',
     'sha256': 'f531d6d08f0275ee2639f622b52243a7ba59bc878d4676ee01016d6fa5052bd6',
     'size_bytes': 38058,
     'snapshot_path': HISTORY_DIR + '/USER_MOLECULE_ENTRY_DESIGN_55726d4_zh-CN.md',
     'byte_policy': 'EXACT_ORIGINAL_GIT_BLOB_BYTES_NO_TRANSFORMATION'},
)


class HistoricalMaterialError(ValueError):
    """A historical material or its fixed source/index binding is invalid."""


def expected_mapping():
    return {'schema_version': 'w05-historical-runtime-source-materials-v1',
            'status': 'HISTORICAL_SOURCE_SNAPSHOT_NOT_CURRENT_OPERATIONAL_GUIDANCE',
            'scope': 'W05_REVIEW_SOURCE_MATERIAL_INTEGRITY_ONLY',
            'source_commit': SOURCE_COMMIT,
            'source_index': {'path': SOURCE_INDEX_PATH, 'record_commit': INDEX_COMMIT,
                             'git_blob_id': INDEX_BLOB, 'canonical_sha256': INDEX_CANONICAL_SHA256,
                             'byte_policy': 'EXACT_INDEX_GIT_BLOB_OR_CRLF_TO_LF'},
            'later_process_update': {'commit': PROCESS_UPDATE_COMMIT,
                                     'status': 'EXTERNAL_EXPERT_CONSULTATION_CANCELLED_BY_USER',
                                     'current_guidance': 'docs/USER_MOLECULE_INTERNAL_VALIDATION_zh-CN.md'},
            'scientific_execution_authorized': False,
            'scientific_approval_granted': False,
            'materials': deepcopy(list(MATERIALS))}


def _blob_id(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode('ascii') + b'\0' + raw).hexdigest()


def _load(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise HistoricalMaterialError('Duplicate historical JSON key: ' + key)
            result[key] = value
        return result
    def invalid(value): raise HistoricalMaterialError('Nonfinite historical JSON value: ' + value)
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=unique, parse_constant=invalid)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HistoricalMaterialError('Invalid historical JSON') from error


def _exact(actual, expected):
    if type(actual) is not type(expected): return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(_exact(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(_exact(a, b) for a, b in zip(actual, expected))
    return actual == expected


def _read(root, relative):
    path = root / relative
    cursor = path
    while cursor != root:
        if cursor.is_symlink() or (hasattr(cursor, 'is_junction') and cursor.is_junction()):
            raise HistoricalMaterialError('Historical input contains a link: ' + relative)
        cursor = cursor.parent
    if not path.is_file(): raise HistoricalMaterialError('Historical input missing: ' + relative)
    if path.stat().st_size > 1024 * 1024: raise HistoricalMaterialError('Historical input exceeds byte limit')
    return path.read_bytes()


def _verified(runtime_root):
    root = Path(runtime_root).resolve(strict=True)
    manifest = _load(_read(root, MANIFEST_PATH))
    if not _exact(manifest, expected_mapping()):
        raise HistoricalMaterialError('Historical path/commit/blob/index mapping differs from fixed binding')
    index_raw = _read(root, SOURCE_INDEX_PATH)
    # This known JSON record allows its exact Git bytes or only CRLF checkout conversion.
    if INDEX_BLOB not in {_blob_id(index_raw), _blob_id(index_raw.replace(b'\r\n', b'\n'))}:
        raise HistoricalMaterialError('Historical source-index Git blob binding differs')
    index = _load(index_raw)
    canonical = json.dumps(index, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    if hashlib.sha256(canonical).hexdigest() != INDEX_CANONICAL_SHA256:
        raise HistoricalMaterialError('Historical source-index content binding differs')
    source_rows = index.get('local_sources')
    if not isinstance(source_rows, list): raise HistoricalMaterialError('Historical source index has no source rows')
    contents, evidence = {}, []
    for item in MATERIALS:
        expected_source = {'owner': item['owner'], 'path': item['original_path'],
                           'commit': item['source_commit'], 'sha256': item['sha256']}
        matched = [row for row in source_rows if isinstance(row, dict) and row.get('path') == item['original_path']]
        if len(matched) != 1 or not _exact(matched[0], expected_source):
            raise HistoricalMaterialError('Historical source row binding differs: ' + item['original_path'])
        raw = _read(root, item['snapshot_path'])
        if (len(raw) != item['size_bytes'] or hashlib.sha256(raw).hexdigest() != item['sha256']
                or _blob_id(raw) != item['git_blob_id']):
            raise HistoricalMaterialError('Historical snapshot bytes differ: ' + item['original_path'])
        contents[item['original_path']] = raw
        evidence.append(deepcopy(item))
    receipt = {'status': 'PASS_EXACT_HISTORICAL_SOURCE_BYTES_ONLY', 'material_count': len(evidence),
               'materials': evidence, 'source_index_blob_id': INDEX_BLOB,
               'source_index_canonical_sha256': INDEX_CANONICAL_SHA256,
               'scientific_execution_authorized': False, 'scientific_approval_granted': False,
               'current_documents_replaced': False,
               'current_process_status': 'EXTERNAL_EXPERT_CONSULTATION_CANCELLED_BY_USER'}
    return contents, receipt


def _require_archive(runtime_root):
    if runtime_root is None:
        raise HistoricalMaterialError(LOCAL_ARCHIVE_ONLY)
    return runtime_root


def load_historical_source_materials(runtime_root=None):
    """Verify explicit local archive bytes; never guess a public-tree fallback."""
    runtime_root = _require_archive(runtime_root)
    return _verified(runtime_root)[0]


def verify_historical_source_materials(runtime_root=None):
    """Return a JSON-safe integrity receipt, never a scientific approval."""
    runtime_root = _require_archive(runtime_root)
    return _verified(runtime_root)[1]


def read_historical_source_material(source, *, runtime_root=None):
    """Read only an exact old source-index row; caller cannot redirect its path."""
    runtime_root = _require_archive(runtime_root)
    matches = [item for item in MATERIALS if isinstance(source, dict) and source.get('path') == item['original_path']]
    if len(matches) != 1: raise HistoricalMaterialError('Unsupported historical source row')
    item = matches[0]
    expected = {'owner': item['owner'], 'path': item['original_path'], 'commit': SOURCE_COMMIT, 'sha256': item['sha256']}
    if not _exact(source, expected): raise HistoricalMaterialError('Caller source row binding differs')
    return load_historical_source_materials(runtime_root)[item['original_path']]
