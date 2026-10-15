# 化学计算与复核 Skill 模块

[English](README.md) · [安装与调用](USAGE_zh-CN.md) · [测试范围](TESTING_zh-CN.md) · [Runtime首页](../README_zh-CN.md)

按自己的输入和研究目标选择下列15个技能。它们指导Agent准备计算、检查真实数据、判读结果和组织复核证据，不自带计算引擎、Docker镜像或在线计算服务。独立分析可使用用户已有环境，无须先安装整个Runtime。

仓库根目录`skills/`是维护和分发源码；用户按需安装到Agent支持的位置。它与`runtime/`计算代码、`scripts/`启动器及`docs/`静态指南分开。

| 技能 | Codex调用名 | 来源类别 |
| --- | --- | --- |
| [RHF 单点计算助手](./rhf-single-point/README.md) | `$rhf-single-point` | 个人Skill适配 |
| [表格拟合与残差分析](./table-fitting-residuals/README.md) | `$table-fitting-residuals` | 个人Skill适配 |
| [轨道局域化与密度不变性验证](./orbital-localization-density/README.md) | `$orbital-localization-density` | 个人Skill适配 |
| [分子图匹配与能量账本复核](./molecular-graph-energy-ledger/README.md) | `$molecular-graph-energy-ledger` | 个人Skill适配 |
| [同哈密顿量路径闭合核对](./same-hamiltonian-path-closure/README.md) | `$same-hamiltonian-path-closure` | 个人Skill适配 |
| [非正交子空间投影与泄漏分析](./nonorthogonal-subspace/README.md) | `$nonorthogonal-subspace` | 个人Skill适配 |
| [矩阵分区掩码与正定性检查](./partition-mask-audit/README.md) | `$partition-mask-audit` | 个人Skill适配 |
| [镜面对称轨道适配与奇偶性分析](./reflection-parity/README.md) | `$reflection-parity` | 个人Skill适配 |
| [片段工作基组装与一致性审计](./fragment-working-basis/README.md) | `$fragment-working-basis` | 个人Skill适配 |
| [核排斥能与几何响应分析](./nuclear-repulsion-response/README.md) | `$nuclear-repulsion-response` | 个人Skill适配 |
| [几何扫描能量分解与曲率分析](./scan-energy-curvature/README.md) | `$scan-energy-curvature` | 个人Skill适配 |
| [固定协议条件态与能量复核](./fixed-protocol-energy-review/README.md) | `$fixed-protocol-energy-review` | 本地流程增补 |
| [约束优化与结构响应](./constrained-optimization-response/README.md) | `$constrained-optimization-response` | 本地流程增补 |
| [多态与尺寸比较](./multistate-size-comparison/README.md) | `$multistate-size-comparison` | 本地流程增补 |
| [Runtime 使用助手](./runtime-usage-assistant/README.md) | `$runtime-usage-assistant` | 本地流程增补 |

## 分发与边界

每个目录含`SKILL.md`与中英使用说明`README.md`，不强制agents/assets/references。前11项由维护者在YouMind创建的个人指令适配而来，后4项为本地新增；SKILL正文仍为中文。署名见[AUTHORS](../AUTHORS.md)，许可见[LICENSE](../LICENSE)与[NOTICE](../NOTICE)，入口身份见[manifest](manifest.json)。

本地记录包括两份历史水分子RHF运行、其余10项的106个限定场景，以及新增4项的64个限定场景；不是独立Agent盲测或全部科学功能认证。本次仅整理公开材料，没有重算。

这是v0.1.0之后的源码增补。取得包含skills/的分支或提交；旧v0.1.0标签/Release附件、网页指南ZIP不会自动包含这些文件。本次不新增版本号、标签、镜像或Release。

公开维护补充：[最小程序回归](../validation/public_regression/README.md) · [完整 MO 附加审查](../docs/CANONICAL_ORBITAL_REVIEW_zh-CN.md)。仅执行工程/合成数据检查，未补跑当前 RHF；历史测试不转为新版本 Agent 验收。15 个 Skill 属于 v0.1.0 后源码增补，旧 Release 资产及指南 ZIP 不自动包含。
