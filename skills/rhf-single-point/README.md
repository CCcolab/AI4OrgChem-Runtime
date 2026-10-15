# RHF single-point assistant

[Skills catalog](../README.md) · [Install and invoke](../USAGE.md) · [Local test scope](../TESTING.md) · [中文使用说明](#中文使用说明)

[Public installation guide](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/skills/USAGE.md) · [公开安装指南](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/skills/USAGE_zh-CN.md) · [License](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/LICENSE)

Instruction entry: [SKILL.md](SKILL.md). The scientific instructions are in Chinese; this page provides an English entry and the original portable Chinese usage guide. This folder includes no execution engine or bundled analysis program.

1. Copy this folder into the skill location supported by your Agent, or ask it to read the complete SKILL.md. Cloning the repository's `skills/` directory does not automatically install it in Codex.
2. Supply actual input files, units, index/atom mapping, the selected protocol/method and the operation you want: prepare, execute, or interpret saved results.
3. Use an existing compatible backend and an explicit budget for execution. Write to a new output directory. If a backend or essential definition is missing, deliver preparation material and identify what was not executed.

```text
Use $rhf-single-point.
Input and protocol: replace with my actual files, definitions, units and method.
First check applicability and prepare the required inputs or review the saved results.
Do not install software, rebuild images, upload data or start a new calculation in this request.
Save reports to a new directory; keep failures and unexecuted checks explicit.
```

Standalone analysis or another backend's preparation range does not extend Runtime's registered services. Fixed objects and conditional rules remain specific to their protocols. Read [testing and limitations](../TESTING.md) before interpreting a test PASS as scientific qualification.

## 中文使用说明

为用户指定分子准备或执行适用的闭壳层RHF单点，解读真实输出及复核轨道、AO密度与能量。

本页提供用户自己的数据与通用计算环境的调用说明。Skill是指令文件，不是已安装的计算引擎或可直接执行的Python程序。

## 1. 准备通用环境

1. 取得本目录的`SKILL.md`和README。按目标Agent支持的目录或加载方式使用；Codex安装和其他Agent用法见[通用调用指南](../USAGE_zh-CN.md)。
2. 选择已有Python环境或实际计算后端，确认Agent能访问输入、输出和该环境。先检查依赖，不自动安装、升级或改全局配置。
3. 本任务依赖：真实计算需要可用量子化学后端。可选PySCF，或有许可且输入格式明确的Gaussian/ORCA；只准备输入时不要求当场运行后端。矩阵复核可用NumPy。
4. 在自己的工作目录准备输入；所有输出使用新的目录，不覆盖原数据。

下面是已有环境的导入检查，不是计算命令。在当前所选环境执行；如果命令名是python3或需要解释器绝对路径，请相应替换：

此处命令仅用于选择PySCF的情形。选择Gaussian/ORCA时按实际软件检查版本与许可，并让Agent准备其原生输入和真实启动命令；不要求为此安装PySCF或编造Python封装。

```sh
python -c "import sys, pyscf; print(sys.executable, pyscf.__version__)"
```

若选择PySCF做真实计算/局域化，按[PySCF官方安装平台说明](https://pyscf.org/user/install.html)使用兼容Linux、macOS或WSL环境；官方不支持原生Windows PySCF。NumPy数组复核可在兼容Windows Python中开展。这是后端的平台条件，不要求修改本机WSL或重装环境。

## 2. 准备输入示例

在工作目录保存为`molecule.xyz`：

```xyz
3
synthetic water; Angstrom; charge 0; multiplicity 1
O 0.000000 0.000000 0.000000
H 0.000000 0.757000 0.586000
H 0.000000 -0.757000 0.586000
```

该XYZ是合成示例，原子顺序O/H/H、单位Å。此次示例明确选择RHF/6-31G(d)、电荷0、多重度1、无ECP；用户使用其他分子时重新指定适用参数。

示例只是明确交换约定，不是Runtime强制schema。请替换为自己的完整数据并说明单位、索引、方法和来源；不要从截图补猜数据。复数矩阵可采用实部/虚部两数组或可读取的NPZ，但必须说明存储约定。

## 3. 在Agent中调用

下面是Codex请求模板。其他Agent请先让它读取本技能的完整SKILL.md，再使用同样的任务说明；不要假定所有平台识别`$技能名`。

```text
使用 $rhf-single-point。
输入：<我的工作目录>/molecule.xyz。
采用RHF/6-31G(d)，电荷0、多重度1、单位Å、无ECP。保持坐标和原子顺序。先检查电子数、基组和后端，再生成一次单点程序；不优化或扫描。
优先使用我现有的兼容环境，缺参数先指出，科学方法不能静默更换。
请先检查输入，再生成完整run_analysis.py，约定--input读取上述文件、--output指定新的结果目录。
记录输入、设置、软件版本、真实日志和未执行项；正式输入拒绝不得只依赖assert。
已有输出目录应拒绝；执行异常、未收敛或本次要求的数值检查失败返回非零退出码。
本次先生成程序，不运行计算；我确认输入、参数和预算后，再明确要求执行一次。
```

如希望Agent直接执行，将最后一行改为“已有后端可用且预算明确时执行一次，不自动重试”，并填明本次预算。真实单点先填写线程、软件内存、时间上限、迭代与收敛设置；需要硬限额时指定实际强制机制。

## 4. 在计算环境运行生成的程序

**run_analysis.py需要先由Agent按本次请求生成，本Skill目录没有随包提供该程序。** 核对输入、参数与程序语法，使用Agent交付的真实命令；只有生成程序已实现上述--input/--output约定时，才按以下示例执行：

如果交付的是Gaussian/ORCA原生输入，则改用Agent核对过的该软件命令，不执行下面的Python示例。

```sh
python -B run_analysis.py --input molecule.xyz --output results/run-001
```

请在自己的工作目录运行；已有`results/run-001`时改为新的目录名。替换实际Python命令与路径，含空格路径加引号。`--input`/`--output`是此处要求生成程序实现的接口，不是直接运行SKILL.md的参数。

Jupyter用户可让Agent生成Notebook单元格，但应显式指定输入和新输出目录；单元格执行才是实际计算。仅能聊天或读取文件、无法运行后端时，交付程序并标记NOT_EXECUTED，不编造结果。

## 5. 查看结果与边界

总能与电子/核项、SCF状态、电子数、软件与资源、S/C/占据/D及可取得的hcore和F或veff、实际残差和日志。

偶数电子与单重态只是RHF适用性的必要条件；SCF收敛不证明稳定基态。密度不是实验实空间密度，轨道能差不是激发能。

检查应用退出状态、真实日志及缺失项；输入拒绝或数值检查失败不得改称成功。软件内存设置不等于硬配额，能否强制限时/限内存取决于实际执行机制。各平台支持范围以真实运行记录为准，不把下面的测试成功迁移到所有环境。

## 测试范围 / Test scope

2026-10-14本地记录：两份已有水分子单点运行记录（指令后续修订另列）。反例的正确拒绝也计作符合预期；保存结果重算、解析模型、工程探针和真实量化调用分别报告。公开交付只有[限定测试摘要](../../validation/skills/test-summary.json)和[范围说明](../TESTING_zh-CN.md)，不含全部原始运行载荷，不能据此独立复现全部测试。未认证所有输入、其他平台或完整科学功能。

Additional saved-array canonical-MO review: [English](../../docs/en/CANONICAL_ORBITAL_REVIEW.md) · [中文](../../docs/CANONICAL_ORBITAL_REVIEW_zh-CN.md). The current instruction has deterministic input/failure examples, not a newly executed RHF endpoint.
