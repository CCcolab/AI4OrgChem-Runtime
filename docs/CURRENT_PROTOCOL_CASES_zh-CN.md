# 当前专题协议使用指南

本页提供固定扭转路径、条件能量、闭合与结构响应专题的安装与使用说明。任务使用登记对象与协议，不接收自己的XYZ；自己的分子应使用[普通RHF入口](CURRENT_MOLECULAR_SINGLE_POINT_zh-CN.md)。

## 1. 首次准备共用 Runtime 环境

本模块共用[统一Runtime源码与Docker环境](SOURCE_INSTALLATION_zh-CN.md)，没有单独的模块安装包。已有该安装的built-image.json时跳到第2步；已有本服务installation-record.json时直接选择并运行任务。不要重复构建、覆盖登记或要求全部模块一起运行。

首次需要已有Git、Python3.12+、Docker Linux/amd64引擎及构建网络；计算/容器内账本运行时也需要Docker可用。下面各目标目录应全新，在Windows PowerShell执行；专用源码ZIP、下载校验和Linux输出权限条件见统一安装页。

```powershell
git clone --branch main https://github.com/CCcolab/AI4OrgChem-Runtime.git D:\chem-work\runtime-source
Set-Location 'D:\chem-work\runtime-source'
git rev-parse HEAD
python -B .\scripts\install-local-runtime.py prepare --destination D:\chem-work\runtime-install
python -B .\scripts\install-local-runtime.py build --destination D:\chem-work\runtime-install
```

上面从 `runtime-source` 准备并构建；后续工作目录是 `runtime-install\runtime`，并不是下载源码目录。built-image.json位于runtime-install根目录，installations和runs位于该runtime目录的同级。失败时先查安装日志，不进入计算或更改科学规则。

## 2. 只登记所选服务（首次一次）

仅登记 `protocol-cases`。读取本次构建标签，输出登记目录必须不存在；已有记录保留。登记保存和校验身份，不启动计算；新镜像不继承旧科学PASS。本文修订没有执行下面的构建或计算。

```powershell
Set-Location 'D:\chem-work\runtime-install\runtime'
$installed = Get-Content ..\built-image.json -Raw | ConvertFrom-Json
python -B .\scripts\register-installation.py --service protocol-cases --image $installed.local_tag --output-dir ..\installations\protocol-cases
```

## 3. 选择专题和运行模式

用 `python -B .\scripts\list-protocol-cases.py` 查看任务；按计算名称选择，下表P编号只用于真实命令。每项的方法不同，不把它们全部当成普通RHF。

| 计算模块 | --task | live范围 |
| --- | --- | --- |
| 扭转构型端点与能量账本 | P03 | 冻结几何一个普通DFT点 |
| π–π直接项与轨道响应 | P04 | 固定DSI3/FUD点 |
| π–σ条件能量比较 | P05 | 固定17° G/FUD |
| 片段条件能量组装 | P06 | 固定0° PDSI/FUL |
| 同Hamiltonian账本闭合 | P07 | 不提供live |
| 丁二烯局域端点与参照 | P08 | 冻结GL几何，不优化 |
| 环丁二烯条件态诊断 | P09 | 固定几何，不优化 |
| 苯键长交替与能量响应 | P10 | 五个固定普通DFT点 |

| 模式 | 含义 |
| --- | --- |
| ledger | 已有账本算术复核，不做新SCF |
| preflight | 登记输入／AO／资源核查，不做SCF，不保证收敛 |
| live | 执行本项允许的新计算；需独立新预算 |

选择固定 P03—P10 协议对象。所有输入、方法、比较量及结果字段见 [当前专业矩阵](CURRENT_PROFESSIONAL_SERVICES_zh-CN.md)，原协议及实际运行身份见 [历史专题材料](PROTOCOL_CASES_BATCH2_zh-CN.public.md)。

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P07 --mode ledger --output-root ..\runs\p07-ledger-new
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P03 --mode preflight --output-root ..\runs\p03-preflight-new
```

ledger/preflight 均要求匹配镜像、来源、资源及输出目录；不授予收敛或科学资格。P07 不支持 live。其他七个 live 任务各一次、需独立新批次预算，未知创建／清理必须保留 RESERVED 与隔离锁，不自动重试或解锁。

## 4. 新计算：先建立预算，再执行live

以下只是尚未执行对象的参数形式，须先按历史协议材料准备本轮预算，不能覆盖或重用旧预算；已有通过记录不安排重跑：

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P03 --mode live --budget D:\chem-work\batch-budget-new.json --output-root ..\runs\p03-live-new
```

首次新批次可将以下合同保存为新的UTF-8无BOM JSON，再把实际路径传给 `--budget`。不得清空、覆盖或复用旧预算；预算记账不是科学方法批准。

```json
{
  "schema": "protocol-case-batch2-budget-v1",
  "ceiling_seconds": 6300,
  "one_attempt_per_case": true,
  "scientific_cases": [
    "P03",
    "P04",
    "P05",
    "P06",
    "P08",
    "P09",
    "P10"
  ],
  "attempts": {},
  "old_root_budget_reused": false,
  "budget_is_accounting_not_method_approval": true
}
```

## 5. 读取结果与执行记录

资源：ledger/preflight 1 CPU/线程、1 GiB、120 秒；live 2 CPU/线程、4 GiB、900 秒硬限、840 秒软停，无额外 swap。保存 `output/case-result.json`、`guard-receipt.json`、资源记录、host-execution 和整目录 manifest。固定协议结果不等于独立引擎认证。

旧 start-protocol-case.ps1 只用于原候选环境，不是本页新安装入口。

每次实际运行目录中先读取 `output/case-result.json`：确认task、mode、输入对象和本次checks，再按[专业矩阵](CURRENT_PROFESSIONAL_SERVICES_zh-CN.md)读取各项比较字段。`output/guard-receipt.json`、`output/worker-receipt.json`、`output/run-manifest.json`及宿主执行记录一起保存。没有统一自动report.md时直接阅读JSON，不把ledger/preflight结果称为live计算通过。未知创建／清理、预算未闭合或失败都保留，不删锁重试。
