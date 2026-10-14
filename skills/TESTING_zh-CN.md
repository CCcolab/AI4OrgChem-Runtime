# 本地限定测试与证据范围

[技能目录](README_zh-CN.md) · [English](TESTING.md) · [机器摘要](../validation/skills/test-summary.json)

RHF保留水分子6-31G(d)/STO-3G两次历史运行，每次一次SCF；当前指令在其后修订，不能把旧运行当成当前每个指令分支已实测。其余原10项106个场景、新增4项64个场景符合预设预期。反例正确拒绝或明确未执行不等于分子计算成功。

| Skill | Scoped scenarios | Evidence type |
| --- | ---: | --- |
| `rhf-single-point` | 2 historical RHF runs | Historical single-point outputs; later instruction revision |
| `table-fitting-residuals` | 13 | Maintainer-generated limited workflows, including negative cases |
| `orbital-localization-density` | 12 | Maintainer-generated limited workflows, including negative cases |
| `molecular-graph-energy-ledger` | 12 | Maintainer-generated limited workflows, including negative cases |
| `same-hamiltonian-path-closure` | 10 | Maintainer-generated limited workflows, including negative cases |
| `nonorthogonal-subspace` | 10 | Maintainer-generated limited workflows, including negative cases |
| `partition-mask-audit` | 9 | Maintainer-generated limited workflows, including negative cases |
| `reflection-parity` | 9 | Maintainer-generated limited workflows, including negative cases |
| `fragment-working-basis` | 9 | Maintainer-generated limited workflows, including negative cases |
| `nuclear-repulsion-response` | 11 | Maintainer-generated limited workflows, including negative cases |
| `scan-energy-curvature` | 11 | Maintainer-generated limited workflows, including negative cases |
| `fixed-protocol-energy-review` | 18 | Maintainer-generated limited workflows, including negative cases |
| `constrained-optimization-response` | 13 | Maintainer-generated limited workflows, including negative cases |
| `multistate-size-comparison` | 16 | Maintainer-generated limited workflows, including negative cases |
| `runtime-usage-assistant` | 17 | Maintainer-generated limited workflows, including negative cases |

测试由维护者Codex会话读完整指令后生成并执行，不是独立Agent盲测。10项包括解析数值、RDKit、保存数组和基于保存占据波函数的Boys/PM各一次，无新SCF。新增4项包括解析二次函数的真实SciPy优化、保存P14标量账本/优化报告和RHF数组复核，以及生产预算、组装、输入解析器和CLI轻量探针；未新增分子优化、积分或Docker运行。

公开机器摘要提供原本地摘要与载荷清单哈希，原请求、测试程序、数组和日志保持本地归档，不随本模块分发，因此摘要不足以独立复现全部170项。所测指令哈希与当前分发哈希分别列出；Runtime使用助手在测试后仅将已撤下平台的名字改为“未验收平台”的通用限制，原测试快照保留。规则、阈值和执行范围未变，不宣称该文字修订后重新跑过工作流。

限定Windows数学/RDKit及既有Linux后端记录不证明全部平台。尚未覆盖新的条件SCF、真实约束分子优化、完整P11/P12多态、真实四父分类、全新引擎安装/生命周期、波函数稳定性和完整轨道资格。新镜像/协议/输入不继承旧Runtime资格；本模块测试没有进入当前公开GitHub Actions jobs。

本次公开整理只核查格式、哈希、安全复制和链接，不重算、不修改旧v0.1.0标签或Release。
