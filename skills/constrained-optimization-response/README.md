# Constrained optimization and structural response

[Skills catalog](../README.md) · [Install and invoke](../USAGE.md) · [Local test scope](../TESTING.md) · [中文使用说明](#中文使用说明)

[Public installation guide](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/skills/USAGE.md) · [公开安装指南](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/skills/USAGE_zh-CN.md) · [License](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/LICENSE)

Instruction entry: [SKILL.md](SKILL.md). The scientific instructions are in Chinese; this page provides an English entry and the original portable Chinese usage guide. This folder includes no execution engine or bundled analysis program.

1. Copy this folder into the skill location supported by your Agent, or ask it to read the complete SKILL.md. Cloning the repository's `skills/` directory does not automatically install it in Codex.
2. Supply actual input files, units, index/atom mapping, the selected protocol/method and the operation you want: prepare, execute, or interpret saved results.
3. Use an existing compatible backend and an explicit budget for execution. Write to a new output directory. If a backend or essential definition is missing, deliver preparation material and identify what was not executed.

```text
Use $constrained-optimization-response.
Input and protocol: replace with my actual files, definitions, units and method.
First check applicability and prepare the required inputs or review the saved results.
Do not install software, rebuild images, upload data or start a new calculation in this request.
Save reports to a new directory; keep failures and unexecuted checks explicit.
```

Standalone analysis or another backend's preparation range does not extend Runtime's registered services. Fixed objects and conditional rules remain specific to their protocols. Read [testing and limitations](../TESTING.md) before interpreting a test PASS as scientific qualification.

## 中文使用说明

准备或复核有明确约束的优化，区分允许方向梯度、约束外梯度、电子态资格、优化终止与结构响应。

## 通用环境调用

本目录的SKILL.md是指令，不携带计算引擎或运行脚本。加载方式见[通用调用指南](../USAGE_zh-CN.md)。Codex可用`$constrained-optimization-response`；其他Agent按自身机制读取完整SKILL.md。仅Python终端须先取得生成的程序，不能执行Markdown。

输入：结构、坐标单位与原子映射；方法/基组/电荷/自旋；约束及自由度、梯度/参数映射、优化阈值和预算，或已有轨迹/端点记录。

环境：读取已有日志不需要量化引擎。解析模型可用现有NumPy/SciPy；分子优化需已有、接口明确且支持所选约束的真实后端。通用方案不等于Runtime新增通用优化服务。

将下列路径和参数说明替换为真实内容，不直接执行占位符：

```text
使用 $constrained-optimization-response（约束优化与结构响应）。
结构文件：填写实际路径；方法/基组、电荷、多重度：填写已选参数。
约束：填写冻结原子或参数化自由度；单位：填写。
请先检查约束和能量/梯度的一致性，准备完整输入及运行命令。
本次不执行分子优化。资源预算另行明确；使用新的输出目录。
已有结果只读判读，区分电子态合格、优化收敛及完整稳定性。
```

如需执行，另在请求中明确实际后端与线程、内存、时间/调用预算及新目录；只使用当前已有工具。没有后端则交付可保存的输入或程序并标NOT_EXECUTED，不自动安装或重建。结果分别给执行状态、数值残差/容差及允许解释，不能用退出0或文件存在代替资格。

## 测试范围 / Test scope

2026-10-14本地记录：13个限定流程场景符合预设预期。反例的正确拒绝也计作符合预期；保存结果重算、解析模型、工程探针和真实量化调用分别报告。公开交付只有[限定测试摘要](../../validation/skills/test-summary.json)和[范围说明](../TESTING_zh-CN.md)，不含全部原始运行载荷，不能据此独立复现全部测试。未认证所有输入、其他平台或完整科学功能。
