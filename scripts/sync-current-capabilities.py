"""Export one capability registry to README and the standalone user guide.

Only explicit marker blocks are generated. The homepage purpose, commands,
scientific templates and original YouMind package are not rewritten.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
START = '<!-- CURRENT_CAPABILITIES_START -->'
END = '<!-- CURRENT_CAPABILITIES_END -->'


def replace_block(text, block, *, before=None):
    if START in text:
        if text.count(START) != 1 or text.count(END) != 1:
            raise ValueError('Exactly one current capability block required')
        return re.sub(re.escape(START)+r'.*?'+re.escape(END), lambda _: block, text, flags=re.S)
    if not before or before not in text:
        raise ValueError('Current capability insertion anchor missing')
    return text.replace(before, block+'\n\n'+before, 1)


def targets(root=ROOT):
    raw = (root/'configs/runtime-capabilities-v2.json').read_bytes()
    registry = json.loads(raw)
    if registry.get('schema_version') != 'runtime-capabilities-v2' or registry.get('declaration_grants_execution_authorization') is not False:
        raise ValueError('Current non-authorizing registry required')
    ci = registry['ci']
    sha = hashlib.sha256(raw).hexdigest()
    result = {'docs/runtime-guide/capabilities-v2.json': raw}
    for name, zh in [('README.md', False), ('README_zh-CN.md', True)]:
        text = (root/name).read_text(encoding='utf-8')
        body = ('当前服务的输入、方法、实际验收、成本及解释范围见[专业服务矩阵](docs/CURRENT_PROFESSIONAL_SERVICES_zh-CN.md)，'
                '机器可读声明见[当前能力表](configs/runtime-capabilities-v2.json)。'
                if zh else 'See the [current professional service matrix](docs/en/CURRENT_PROFESSIONAL_SERVICES.md) for inputs, methods, recorded acceptance, cost and interpretation; the [current capability registry](configs/runtime-capabilities-v2.json) is the machine-readable declaration.')
        scope = (f"已记录的工程验证基线：[{ci['commit'][:8]} 的 {ci['successful_jobs']} 个 CI job 成功]({ci['url']})。{ci['scope_zh']} [CI 回执与交付范围](docs/DELIVERY_SYNC_20261015_zh-CN.md)。15 个 Skill 是 v0.1.0 之后的源码增补，旧 Release 资产和指南 ZIP 不自动包含。"
                 if zh else f"Recorded engineering baseline: [{ci['successful_jobs']} jobs succeeded for {ci['commit'][:8]}]({ci['url']}). {ci['scope']} See the [CI receipt and delivery scope](docs/en/DELIVERY_SYNC_20261015.md). The 15 Skills are a post-v0.1.0 source supplement; old Release assets and guide ZIP do not automatically include them.")
        block = START+'\n'+body+'\n\n'+scope+'\n'+END
        anchor = '## 使用与环境准备' if zh else '## Usage and environment setup'
        # Keep the generated note above the existing technical disclosure.
        if anchor not in text:
            anchor = '<details>'
        result[name] = replace_block(text, block, before=anchor).encode('utf-8')
    page = (root/'docs/index.html').read_text(encoding='utf-8')
    def link(path, label):
        return ('<a href="https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/'
                +html.escape(path,quote=True)+'" target="_blank" rel="noopener noreferrer">'
                +html.escape(label,quote=False)+'</a>')
    def service_links(row):
        paths = []
        for key in ('schema', 'case_config'):
            if isinstance(row['input'].get(key),str):
                paths.append(link(row['input'][key],'输入合同'))
        for evidence in row['evidence']:
            paths.append(link(evidence['path'],'协议与判读' if evidence['path'].endswith('.md') else '保存结果'))
        entry = ('runtime/cli.py' if row['id']=='p14-fixed-tasks' else
                 next((item['path'] for item in row['evidence'] if item['path'].endswith('.md')),
                      'docs/CURRENT_PROFESSIONAL_SERVICES_zh-CN.md')
                 if row['id'] in ('user-compute','root-native-diagnostic') else
                 'scripts/run-installed-runtime.py')
        paths.append(link(entry,'执行边界与入口'))
        return ' · '.join(paths)
    rows = ''.join('<tr><td>'+html.escape(row['name'], quote=False)+'</td><td>'+html.escape(row['scope'], quote=False)+'</td><td>'+html.escape(row['qualification']['numerical'], quote=False)+'</td><td>'+service_links(row)+'</td></tr>' for row in registry['capabilities'])
    block = (START+'<details id="current-service-registry"><summary>当前服务范围与验证依据</summary>'
             '<p>按研究问题选择模块；具体输入、结果字段、成本及允许解释见'
             '<a href="https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/CURRENT_PROFESSIONAL_SERVICES_zh-CN.md" target="_blank" rel="noopener noreferrer">当前专业服务矩阵</a>。'
             '本表引用统一能力登记，不授予计算权限，也不将历史验收转移到新安装。</p>'
             f'<p><a href="{html.escape(ci["url"])}" target="_blank" rel="noopener noreferrer">已记录工程基线 {ci["commit"][:8]} 的 {ci["successful_jobs"]} 个 CI job 成功</a>。{html.escape(ci["scope_zh"])} '
             +link('docs/DELIVERY_SYNC_20261015_zh-CN.md','CI 回执与交付范围')+'。15 个 Skill 属于发布后的源码增补，旧 Release 资产与指南 ZIP 不自动包含。</p>'
             '<div class="table-scroll"><table><thead><tr><th>服务</th><th>输入与方法范围</th><th>已有数值验收</th><th>输入、协议、结果与入口</th></tr></thead><tbody>'+rows+'</tbody></table></div>'
             '<p><a href="https://cccolab.github.io/AI4OrgChem-Runtime/runtime-guide/capabilities-v2.json" target="_blank" rel="noopener noreferrer">下载同源能力表 JSON</a>；'
             '<a href="https://github.com/CCcolab/AI4OrgChem-Runtime/tree/main/evidence/numerical-witnesses" target="_blank" rel="noopener noreferrer">最小数值见证与只读复核</a>。'
             f'声明文件 SHA-256：<code>{sha}</code>。</p></details>'+END)
    page = replace_block(page, block, before='<h3>常见问题</h3>')
    # These are active statements, not quoted historical evidence. Preserve all
    # original delivery records and the collapsed historical table separately.
    page = page.replace('Actions NOT_EXECUTED，分发BLOCKED，源码待确认，Colab deferred，expert CANCELLED_BY_USER。',
                        '当前源码与静态指南已公开；CI记录及范围见统一能力表，镜像分发仍受限制，Colab暂缓，外部咨询已取消。')
    page = page.replace('Runtime本地工程候选未公开发布；任意用户分子的旧条件态比较 Compute BLOCKED；',
                        'Runtime源码与静态指南已公开；任意用户分子的旧条件态比较 Compute BLOCKED；')
    result['docs/index.html'] = page.encode('utf-8')
    if (root/'docs/runtime-guide/current/docs/index.html').exists():
        result['docs/runtime-guide/current/docs/index.html'] = result['docs/index.html']
    english = root/'docs/en/index.html'
    if english.exists():
        text = english.read_text(encoding='utf-8')
        block = (START+'<section class="note" id="current-service-registry"><h2>Version and verification records</h2>'
                 f'<p>Recorded engineering CI baseline: <a href="{html.escape(ci["url"])}">{ci["successful_jobs"]} jobs at {ci["commit"][:8]}</a>. '
                 f'{html.escape(ci["scope"])} '
                 '<a href="https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/en/DELIVERY_SYNC_20261015.md">CI receipt and delivery scope</a>.</p>'
                 '<p><a href="https://github.com/CCcolab/AI4OrgChem-Runtime/tree/main/skills">15 instruction Skills</a> were added after v0.1.0. '
                 'The original Release assets and guide ZIP do not automatically contain them. '
                 'P11/P12 have 78 registered units with two accepted historical pilots; user conditional Compute remains closed.</p>'
                 '<p><a href="https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/configs/runtime-capabilities-v2.json">Capability registry</a> · '
                 '<a href="https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/en/P12_COMPARISON_METRICS.md">P12 comparison metrics</a></p></section>'+END)
        result['docs/en/index.html'] = replace_block(text, block, before='<footer>').encode('utf-8')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='Regenerate explicitly owned blocks; default checks only')
    args = parser.parse_args(argv)
    changed = []
    for name, raw in targets().items():
        path = ROOT/name
        if not path.exists() or path.read_bytes() != raw:
            changed.append(name)
            if args.write:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
    print(json.dumps({'status': 'SYNCHRONIZED' if args.write or not changed else 'DRIFT',
                      'generated_files': changed}, ensure_ascii=False))
    return 0 if args.write or not changed else 1


if __name__ == '__main__':
    raise SystemExit(main())
