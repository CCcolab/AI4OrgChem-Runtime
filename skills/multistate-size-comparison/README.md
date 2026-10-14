# Multistate and size comparisons

[Skills catalog](../README.md) · [Install and invoke](../USAGE.md) · [Local test scope](../TESTING.md) · [中文使用说明](#中文使用说明)

[Public installation guide](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/skills/USAGE.md) · [公开安装指南](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/skills/USAGE_zh-CN.md) · [License](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/LICENSE)

Instruction entry: [SKILL.md](SKILL.md). The scientific instructions are in Chinese; this page provides an English entry and the original portable Chinese usage guide. This folder includes no execution engine or bundled analysis program.

1. Copy this folder into the skill location supported by your Agent, or ask it to read the complete SKILL.md. Cloning the repository's `skills/` directory does not automatically install it in Codex.
2. Supply actual input files, units, index/atom mapping, the selected protocol/method and the operation you want: prepare, execute, or interpret saved results.
3. Use an existing compatible backend and an explicit budget for execution. Write to a new output directory. If a backend or essential definition is missing, deliver preparation material and identify what was not executed.

```text
Use $multistate-size-comparison.
Input and protocol: replace with my actual files, definitions, units and method.
First check applicability and prepare the required inputs or review the saved results.
Do not install software, rebuild images, upload data or start a new calculation in this request.
Save reports to a new directory; keep failures and unexecuted checks explicit.
```

Standalone analysis or another backend's preparation range does not extend Runtime's registered services. Fixed objects and conditional rules remain specific to their protocols. Read [testing and limitations](../TESTING.md) before interpreting a test PASS as scientific qualification.

## 中文使用说明

组织明确的状态与尺寸列表、依赖和资源预算，按集合完整性及资格复核加权比较。

## 通用环境调用

本目录的SKILL.md是指令，不携带计算引擎或运行脚本。加载方式见[通用调用指南](../USAGE_zh-CN.md)。Codex可用`$multistate-size-comparison`；其他Agent按自身机制读取完整SKILL.md。仅Python终端须先取得生成的程序，不能执行Markdown。

输入：唯一状态ID、组成/尺寸、协议/方法/占据、依赖表、真实来源/profile/镜像身份、能量单位、权重及比较定义，实际结果和清理记录。

环境：表格/依赖/账本复核可用Python标准库。采用Runtime时读取已有源码的高成本配置；预算API只写入本次隔离测试目录，不能操作其他科研任务预算。实际高成本运行需要真实引擎与新的授权预算。

将下列路径和参数说明替换为真实内容，不直接执行占位符：

```text
使用 $multistate-size-comparison（多态与尺寸比较）。
状态列表、依赖及比较公式：填写协议文件路径。
已有运行结果：填写实际目录；请先核对身份与逐态资格。
本次只读复核并准备执行顺序，不启动多态计算或资源探针。
缺状态就输出未闭合清单，不插值补能量，不迁移先导态资格。
汇总报告使用新目录；真实计算预算尚未授权。
```

如需执行，另在请求中明确实际后端与线程、内存、时间/调用预算及新目录；只使用当前已有工具。没有后端则交付可保存的输入或程序并标NOT_EXECUTED，不自动安装或重建。结果分别给执行状态、数值残差/容差及允许解释，不能用退出0或文件存在代替资格。

## 测试范围 / Test scope

2026-10-14本地记录：16个限定流程场景符合预设预期。反例的正确拒绝也计作符合预期；保存结果重算、解析模型、工程探针和真实量化调用分别报告。公开交付只有[限定测试摘要](../../validation/skills/test-summary.json)和[范围说明](../TESTING_zh-CN.md)，不含全部原始运行载荷，不能据此独立复现全部测试。未认证所有输入、其他平台或完整科学功能。
