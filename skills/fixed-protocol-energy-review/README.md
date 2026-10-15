# Fixed-protocol conditional-state energy review

[Skills catalog](../README.md) · [Install and invoke](../USAGE.md) · [Local test scope](../TESTING.md) · [中文使用说明](#中文使用说明)

[Public installation guide](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/skills/USAGE.md) · [公开安装指南](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/skills/USAGE_zh-CN.md) · [License](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/LICENSE)

Instruction entry: [SKILL.md](SKILL.md). The scientific instructions are in Chinese; this page provides an English entry and the original portable Chinese usage guide. This folder includes no execution engine or bundled analysis program.

1. Copy this folder into the skill location supported by your Agent, or ask it to read the complete SKILL.md. Cloning the repository's `skills/` directory does not automatically install it in Codex.
2. Supply actual input files, units, index/atom mapping, the selected protocol/method and the operation you want: prepare, execute, or interpret saved results.
3. Use an existing compatible backend and an explicit budget for execution. Write to a new output directory. If a backend or essential definition is missing, deliver preparation material and identify what was not executed.

```text
Use $fixed-protocol-energy-review.
Input and protocol: replace with my actual files, definitions, units and method.
First check applicability and prepare the required inputs or review the saved results.
Do not install software, rebuild images, upload data or start a new calculation in this request.
Save reports to a new directory; keep failures and unexecuted checks explicit.
```

Standalone analysis or another backend's preparation range does not extend Runtime's registered services. Fixed objects and conditional rules remain specific to their protocols. Read [testing and limitations](../TESTING.md) before interpreting a test PASS as scientific qualification.

## 中文使用说明

按用户明确的固定体系与条件规则，复核能量账本、度量、端点及父结果身份；不开放任意用户分子的条件态计算。

## 通用环境调用

本目录的SKILL.md是指令，不携带计算引擎或运行脚本。加载方式见[通用调用指南](../USAGE_zh-CN.md)。Codex可用`$fixed-protocol-energy-review`；其他Agent按自身机制读取完整SKILL.md。仅Python终端须先取得生成的程序，不能执行Markdown。

输入：实际协议及版本、分子/片段/AO映射、方法与占据规则、真实能量分项或矩阵、容差来源与结果身份。只有报告时可以判读已知字段，缺数组不称独立矩阵验证。

环境：只读账本用Python标准库即可；数组复核使用现有NumPy。新科学计算需选定后端，若采用Runtime固定服务则按相应安装及镜像合同执行。

将下列路径和参数说明替换为真实内容，不直接执行占位符：

```text
使用 $fixed-protocol-energy-review（固定协议条件态与能量复核）。
请读取我提供的协议文件和已有结果目录，复核普通态与条件态的能量分项、电子数度量、实际门槛和身份对应。
协议/结果路径：填写实际路径。
本次只读复核，不新增计算、不安装或构建；输出保存到新的目录。
缺分项、矩阵或父记录如实标记，不用历史PASS补缺。
```

如需执行，另在请求中明确实际后端与线程、内存、时间/调用预算及新目录；只使用当前已有工具。没有后端则交付可保存的输入或程序并标NOT_EXECUTED，不自动安装或重建。结果分别给执行状态、数值残差/容差及允许解释，不能用退出0或文件存在代替资格。

## 测试范围 / Test scope

2026-10-14本地记录：18个限定流程场景符合预设预期。反例的正确拒绝也计作符合预期；保存结果重算、解析模型、工程探针和真实量化调用分别报告。公开交付只有[限定测试摘要](../../validation/skills/test-summary.json)和[范围说明](../TESTING_zh-CN.md)，不含全部原始运行载荷，不能据此独立复现全部测试。未认证所有输入、其他平台或完整科学功能。

Runtime-specific protocol qualification: [中文](../../docs/CONDITIONAL_PROTOCOL_QUALIFICATION_zh-CN.md) · [English](../../docs/en/CONDITIONAL_PROTOCOL_QUALIFICATION.md). Existing instruction bytes and historical test identities are unchanged.
