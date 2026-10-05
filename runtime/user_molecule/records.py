"""Strict atomic records and read-only reporting."""
import hashlib
import json
import math
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


def report(record, request=None):
    """User brief without calculation, approval or mutation of raw records.

    Real scope approval is not loaded by this candidate. The assessment module
    is exercised separately; it is not a production opening switch.
    """
    import html
    from .research import assess
    request = request or {}
    preflight = record.get('preflight', record)
    checked_only = 'compute_eligible' in preflight and 'comparison_available' not in record
    qualification = assess(record, request.get('calculation_profile'))
    available = record.get('comparison_available') is True and qualification['research_status'] in ('TECHNICAL_ONLY', 'NOT_REVIEWED')
    ordinary, conditional = record.get('ordinary') or {}, record.get('conditional') or {}
    safe = lambda value: html.escape(str(value)).replace('\r', ' ').replace('\n', ' ')
    show = lambda value: str(value) if type(value) in (int, float) and math.isfinite(value) else '未提供/不可用'
    groups = request.get('fragments') or []
    return '\n'.join(['# 用户分子计算简报', '',
        '研究问题：' + safe(request.get('research_question', '未提供；请查看本次请求快照')),
        '计算对象：固定几何；Å，xy 平面，中性闭壳层 C/H（仅合法输入范围，不代表方法适用）。',
        '碳 π 组：' + ('；'.join(safe(g.get('id')) + '=' + safe(g.get('carbon_atom_indices_1based')) for g in groups) or '未提供'),
        '配置：' + safe(request.get('calculation_profile', 'UNKNOWN')), '',
        '比较定义：同一几何的 Eordinary−Econditional；h/S/F 的跨组 π 块及固定十五类 ERI 按条件规则屏蔽，采用全局闭壳层占据。',
        f"输入状态：{record.get('input_status', preflight.get('input_status', 'UNKNOWN'))}",
        f"执行状态：{record.get('execution_status', 'NOT_EXECUTED')}",
        f"数值资格：{record.get('numerical_status', 'NOT_EXECUTED')}",
        '方法适用性：' + qualification['method_status'],
        '研究资格：' + ('NOT_REVIEWED' if checked_only else qualification['research_status']),
        f"比较可用：{available}",
        '普通态总能量 (Eh)：' + show(ordinary.get('total_energy_hartree')),
        '条件态总能量 (Eh)：' + show(conditional.get('total_energy_hartree')),
        '差值 Eordinary−Econditional (Eh)：' + show(record.get('delta_hartree') if available else None),
        '差值 (kcal/mol)：' + show(record.get('delta_kcal_mol') if available else None),
        '账本闭合残差 (Eh)：普通态 ' + show(ordinary.get('energy_component_closure_residual_hartree')) +
        '；条件态 ' + show(conditional.get('energy_component_closure_residual_hartree')), '',
        '两态原始能量在比较不可用时仅供失败诊断，不能用于研究结论。',
        '原因：' + safe('; '.join(str(r) for r in record.get('reasons', preflight.get('reasons', [])))),
        '资格判读：' + safe('; '.join(qualification['reasons'])),
        '下一步：' + ('完成 W05 判据、参考与资源验收后才能计算。' if checked_only else
                         '先核对失败/未执行原因；研究使用还须有匹配的真实方法审阅和 W06 验收记录。'), '',
        '允许解释：获准范围内指定条件模型的全分子能量响应；改变分片或几何应形成另一个请求并分别审查。',
        '限制：不是单键能、键解离能、实验测量或自动电子密度/键级分析。变分性 NOT_ESTABLISHED；稳定性分析 NOT_EXECUTED。',
        'gap 来源：原适配器若未输出来源字段，标 UNKNOWN；参考候选记录 LAST_DIAGONALIZATION_POSSIBLY_DIIS，不能冒充最终无 DIIS 算子的谱。',
        '证据：完整账本/数值诊断见 result.json；请求快照见 input/；运行/镜像/来源身份见 run-manifest.json。缺失文件表示未生成。',
        '镜像身份：' + safe(record.get('identities', {}).get('image_id', 'UNKNOWN')),
        '科学源码：' + safe(record.get('identities', {}).get('science_commit', 'UNKNOWN')),
        '镜像构建 runtime：' + safe(record.get('identities', {}).get('runtime_build_commit', 'UNKNOWN')),
        '新入口尚未完成 W05/W06 科学及研究验收；原 L4 检查点可以保存，但不支持恢复运行。', ''])
