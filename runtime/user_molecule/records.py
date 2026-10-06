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


def report(record, request=None, *, summary=None):
    """User brief without calculation, approval or mutation of raw records.

    Real scope approval is not loaded by this candidate. The assessment module
    is exercised separately; it is not a production opening switch.
    """
    import html
    from .research import assess
    request = request or {}
    preflight = record.get('preflight', record)
    checked_only = ('compute_eligible' in preflight and 'comparison_available' not in record
                    if summary is None else summary['checked_only'])
    qualification = ({'method_status': summary['method_status'], 'research_status': summary['research_status'],
                      'reasons': summary['qualification_reasons']} if summary is not None else
                     {'method_status': 'NOT_REVIEWED', 'research_status': 'NOT_REVIEWED',
                      'reasons': ['NUMERICAL_COMPARISON_NOT_EXECUTED']} if checked_only else
                     assess(record, request.get('calculation_profile')))
    available = (record.get('comparison_available') is True and
                 qualification['research_status'] in ('TECHNICAL_ONLY', 'NOT_REVIEWED')
                 if summary is None else summary['comparison_available'])
    ordinary, conditional = record.get('ordinary') or {}, record.get('conditional') or {}
    safe = lambda value: html.escape(str(value)).replace('\r', ' ').replace('\n', ' ')
    def show(value):
        try:
            return str(value) if type(value) in (int, float) and math.isfinite(value) else '未提供/不可用'
        except OverflowError:
            return '未提供/不可用'
    groups = request.get('fragments') or []
    statuses = summary or record
    identities = statuses.get('identities') or {}
    unknown = lambda value: 'UNKNOWN' if value is None or value == '' else safe(value)
    diagnostics = (summary or {}).get('state_diagnostics') or {'ordinary': ordinary, 'conditional': conditional}
    gap_sources = '；'.join(safe(name) + ' ' + unknown(state.get('gap_operator_source'))
                           for name, state in diagnostics.items()) or 'UNKNOWN'
    eligibility = statuses.get('compute_eligible', preflight.get('compute_eligible'))
    extra = []
    if summary is not None:
        extra = ['记录完整性：' + summary['record_integrity'] + '（仅本地 manifest 与文件字节匹配；不代表科学或方法批准）。',
                 '科学执行：' + summary['scientific_execution_status'],
                 '原运行退出码：' + unknown(summary['original_exit_code']) +
                 '；来源 ' + unknown(summary['original_exit_code_source']),
                 '原始状态标签：' + safe('; '.join(key + '=' + str(value)
                     for key, value in summary['raw_statuses'].items() if value is not None)),
                 '未通过的已记录判据：' + safe('; '.join(summary['failed_metric_ids']) or '未提供'),
                 '状态原始标签（不构成资格）：' + safe('; '.join(name + '=' + str(labels)
                     for name, labels in summary['raw_state_labels'].items() if labels) or '未提供'),
                 '证据问题：' + safe('; '.join(summary['evidence_issues']) or '未发现本地清单字节不一致'),
                 '缺失证据：' + safe('; '.join(summary['missing_files']) or '未记录缺失'),
                 '预期未生成证据：' + safe('; '.join(summary['expected_absence']) or '无')]
        if summary['state_diagnostics']:
            extra.extend(['', '保存的状态诊断（比较不可用时仅供失败诊断，不构成资格）：', '',
                          '| 状态 | 能量 (Eh) | 收敛标签 | commutator | raw map 残差 | occupied-virtual gap (Eh) | final non-DIIS gap (Eh) |',
                          '| --- | --- | --- | --- | --- | --- | --- |'])
            for name, state in summary['state_diagnostics'].items():
                fields = [safe(name), show(state.get('total_energy_hartree')), unknown(state.get('converged')),
                          show(state.get('final_commutator_frobenius_norm')),
                          show(state.get('mapped_density_relative_residual', state.get('final_raw_aufbau_density_relative_residual'))),
                          show(state.get('occupied_virtual_gap_hartree')), show(state.get('final_non_diis_gap_hartree'))]
                extra.append('| ' + ' | '.join(value.replace('|', '&#124;') for value in fields) + ' |')
    return '\n'.join(['# 用户分子计算简报', '',
        '研究问题：' + safe(request.get('research_question',
            '未提供；本次未生成规范请求快照' if summary and summary['expected_absence'] else
            '未提供；请求快照缺失或未记录')),
        '接口限定输入范围：固定几何；Å，xy 平面，中性闭壳层 C/H（未替代本次输入检查，不代表方法适用）。',
        '碳 π 组：' + ('；'.join(safe(g.get('id')) + '=' + safe(g.get('carbon_atom_indices_1based')) for g in groups) or '未提供'),
        '配置：' + safe(request.get('calculation_profile', 'UNKNOWN')), '',
        '记录的比较方向：同一几何的 Eordinary−Econditional；条件态、占据规则及能量解释须完成方法审阅。',
        '输入状态：' + safe(statuses.get('input_status', preflight.get('input_status', 'UNKNOWN'))),
        '执行状态：' + safe(statuses.get('execution_status', 'NOT_EXECUTED')),
        '数值资格：' + safe(statuses.get('numerical_status', 'NOT_EXECUTED')),
        'Compute 资格：' + unknown(eligibility) + '（该次记录；不代表当前开放许可）。',
        '方法适用性：' + (summary['method_status'] if summary else qualification['method_status']),
        '研究资格：' + (summary['research_status'] if summary else qualification['research_status']),
        f"比较可用：{available}",
        '普通态总能量 (Eh)：' + show(ordinary.get('total_energy_hartree')),
        '条件态总能量 (Eh)：' + show(conditional.get('total_energy_hartree')),
        '差值 Eordinary−Econditional (Eh)：' + show(statuses.get('delta_hartree') if available else None),
        '差值 (kcal/mol)：' + show(statuses.get('delta_kcal_mol') if available else None),
        '账本闭合残差 (Eh)：普通态 ' + show(ordinary.get('energy_component_closure_residual_hartree')) +
        '；条件态 ' + show(conditional.get('energy_component_closure_residual_hartree')), '',
        '两态原始能量在比较不可用时仅供失败诊断，不能用于研究结论。',
        '判读保存的该次记录；历史 blocked 理由保留原标签，不自动作为当前验收进展。',
        '原因：' + safe('; '.join(str(r) for r in statuses.get('reasons', preflight.get('reasons', [])))),
        '资格判读：' + safe('; '.join((summary or {}).get('qualification_reasons', qualification['reasons']))),
        '下一步：' + ('完成 W05 判据、参考与资源验收后才能计算。' if checked_only else
                         '先核对失败/未执行原因；研究使用还须有匹配的真实方法审阅和 W06 验收记录。'), '',
        '能量解释：当前简报不加载方法批准；研究使用需要匹配的真实方法审阅。',
        '限制：不是单键能、键解离能、实验测量或自动电子密度/键级分析。变分性 NOT_ESTABLISHED；稳定性分析 NOT_EXECUTED。',
        'gap 来源（记录字段）：' + gap_sources,
        '证据：本目录的 result/preflight/error、请求快照和 manifest；目录报告列明完整性与缺失。',
        '镜像身份：' + unknown(identities.get('image_id')),
        '科学源码：' + unknown(identities.get('science_commit')),
        '镜像构建 runtime：' + unknown(identities.get('runtime_build_commit')),
        '本次测试 runtime：' + unknown(identities.get('runtime_test_commit')),
        *extra,
        '新入口尚未完成 W05/W06 科学及研究验收；原 L4 检查点可以保存，但不支持恢复运行。', ''])
