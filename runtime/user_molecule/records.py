"""Strict atomic records and read-only reporting."""
import hashlib
import json
import os
import uuid
from pathlib import Path
from .input import strict_json


def load(path):
    return strict_json(Path(path).read_bytes())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def manifest(directory, **fields):
    path = Path(directory)
    files = {p.relative_to(path).as_posix(): {'size_bytes': p.stat().st_size, 'sha256': file_hash(p)}
             for p in sorted(path.rglob('*')) if p.is_file() and p.name != 'run-manifest.json' and not p.name.endswith('.tmp')}
    save(path / 'run-manifest.json', {'schema_version': 1, **fields, 'files': files})


def report(record):
    preflight = record.get('preflight', record)
    return '\n'.join(['# 用户分子服务记录', '',
        f"输入状态：{record.get('input_status', preflight.get('input_status', 'UNKNOWN'))}",
        f"执行状态：{record.get('execution_status', 'NOT_EXECUTED')}",
        f"数值资格：{record.get('numerical_status', 'NOT_EXECUTED')}",
        f"研究资格：{record.get('research_status', 'NOT_REVIEWED')}",
        f"比较可用：{record.get('comparison_available', False)}",
        f"差值 Eordinary−Econditional (Eh)：{record.get('delta_hartree')}",
        '', '原因：' + '; '.join(record.get('reasons', preflight.get('reasons', []))),
        '', '结果为指定条件模型的全分子能量响应，不是单键能或实验测量。',
        '新入口尚未完成 W05/W06 的科学及研究验收；原 L4 检查点不支持恢复。', ''])
