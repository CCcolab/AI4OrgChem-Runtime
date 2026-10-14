# Runtime usage assistant

[Skills catalog](../README.md) · [Install and invoke](../USAGE.md) · [Local test scope](../TESTING.md) · [中文使用说明](#中文使用说明)

[Public installation guide](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/skills/USAGE.md) · [公开安装指南](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/skills/USAGE_zh-CN.md) · [License](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/LICENSE)

Instruction entry: [SKILL.md](SKILL.md). The scientific instructions are in Chinese; this page provides an English entry and the original portable Chinese usage guide. This folder includes no execution engine or bundled analysis program.

1. Copy this folder into the skill location supported by your Agent, or ask it to read the complete SKILL.md. Cloning the repository's `skills/` directory does not automatically install it in Codex.
2. Supply actual input files, units, index/atom mapping, the selected protocol/method and the operation you want: prepare, execute, or interpret saved results.
3. Use an existing compatible backend and an explicit budget for execution. Write to a new output directory. If a backend or essential definition is missing, deliver preparation material and identify what was not executed.

```text
Use $runtime-usage-assistant.
Input and protocol: replace with my actual files, definitions, units and method.
First check applicability and prepare the required inputs or review the saved results.
Do not install software, rebuild images, upload data or start a new calculation in this request.
Save reports to a new directory; keep failures and unexecuted checks explicit.
```

Standalone analysis or another backend's preparation range does not extend Runtime's registered services. Fixed objects and conditional rules remain specific to their protocols. Read [testing and limitations](../TESTING.md) before interpreting a test PASS as scientific qualification.

## 中文使用说明

按实际研究目的选择可用服务，检查输入/安装身份，准备真实命令并引导结果判读；不要求用户先理解P编号。

## 通用环境调用

本目录的SKILL.md是指令，不携带计算引擎或运行脚本。加载方式见[通用调用指南](../USAGE_zh-CN.md)。Codex可用`$runtime-usage-assistant`；其他Agent按自身机制读取完整SKILL.md。仅Python终端须先取得生成的程序，不能执行Markdown。

输入：研究目的，实际Runtime源码/安装目录，结构或表格或已有结果；用户选择“准备”“执行”或“判读”。仅提供本任务所需材料。

环境：能力查询、清单、CLI帮助和输入解析仅需兼容Python及已有Runtime源码。运行服务另外需要对应Docker环境及安装记录；P14独立路径另需真实PowerShell版本及镜像。WSL Python可用不等于Docker服务可用。

将下列路径和参数说明替换为真实内容，不直接执行占位符：

```text
使用 $runtime-usage-assistant（Runtime 使用助手）。
我的目标：填写研究问题及希望获得的结果。
Runtime源码/安装目录：填写实际路径；输入或结果：填写路径。
请选择当前实际支持的服务，检查必要输入和已有环境，准备一套一致的运行命令。
本次只准备或只读判读，不安装、构建、启动计算或上传数据。
区分共用服务安装记录与P14独立镜像；输出到新目录。
```

如需执行，另在请求中明确实际后端与线程、内存、时间/调用预算及新目录；只使用当前已有工具。没有后端则交付可保存的输入或程序并标NOT_EXECUTED，不自动安装或重建。结果分别给执行状态、数值残差/容差及允许解释，不能用退出0或文件存在代替资格。

## 测试范围 / Test scope

2026-10-14本地记录：17个限定流程场景符合预设预期。反例的正确拒绝也计作符合预期；保存结果重算、解析模型、工程探针和真实量化调用分别报告。公开交付只有[限定测试摘要](../../validation/skills/test-summary.json)和[范围说明](../TESTING_zh-CN.md)，不含全部原始运行载荷，不能据此独立复现全部测试。未认证所有输入、其他平台或完整科学功能。
