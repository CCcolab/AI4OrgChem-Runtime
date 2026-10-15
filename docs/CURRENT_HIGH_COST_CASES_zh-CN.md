# 当前高成本固定体系服务

本页提供固定多态优化与环状体系尺寸／状态比较的安装与使用说明。任务使用登记对象与协议，不接收自己的XYZ；自己的分子应使用[普通RHF入口](CURRENT_MOLECULAR_SINGLE_POINT_zh-CN.md)。

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

仅登记 `high-cost-cases`。读取本次构建标签，输出登记目录必须不存在；已有记录保留。登记保存和校验身份，不启动计算；新镜像不继承旧科学PASS。本文修订没有执行下面的构建或计算。

```powershell
Set-Location 'D:\chem-work\runtime-install\runtime'
$installed = Get-Content ..\built-image.json -Raw | ConvertFrom-Json
python -B .\scripts\register-installation.py --service high-cost-cases --image $installed.local_tag --output-dir ..\installations\high-cost-cases
```

本家族新安装通过精确派生来源合同核对原107条基线、七份本地测试排除和允许的工程字节覆盖，安装载荷为100条；旧候选仍保留原107条路径，不机械降低来源门槛。

## 3. 先看状态清单和已有账本

先查看注册状态，按任务选择账本：

```powershell
python -B .\scripts\list-high-cost-cases.py
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\high-cost-cases\installation-record.json --task P11 --mode ledger --output-root ..\runs\p11-ledger-new
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\high-cost-cases\installation-record.json --task P12 --mode ledger --output-root ..\runs\p12-ledger-new
```

P11 17态、P12 61态合计78个登记单元。只有旧镜像苯G和N12-G两个先导有数值验收，其余76态及新安装镜像的科学重放不继承 PASS。

## 4. 单状态预检和新预算

preflight 按状态清单选择一个尚未执行的真实 Unit，使用 `--task P11` 或 `--task P12`、`--mode preflight` 和 `--unit`；不重做已通过态的资源探针。本轮不安排 preflight 或 live 实跑。

live 除同一 `--installation-record` 外，要求 `--mode live`、一个真实 `--unit`、独立 `--budget`、全新 `--output-root`。前序依赖以 `--inputs` 传入本轮合格 output 映射；P11A 按 G→GL→GE，P12 GL/GE 依赖本轮 G，N16 GE 另需本轮 GL。用 create-high-cost-budget.py 创建预算，不手写、复用或清空。单态一次，失败也计费，无重试、无恢复。

未知 create、rm、所属资源探针状态会保留隔离锁；预算保持 RESERVED，不能以一次查询无容器或尚无 ID 结算。只有确认所有所属操作闭合并释放自己的锁，才允许结算。不得手动删锁绕过未知状态。

资源、数值及依赖合同以 [冻结配置](../configs/high-cost-cases-v1.json) 和 [历史科学边界](PROTOCOL_CASES_BATCH3_zh-CN.public.md) 为准。本轮不降低内存、线程或容差。保存 host、worker、guard、资源、预算与 manifest，scratch 是保留中间文件，不冒充最终科学结果。

历史“相对 CESE 2.103137%”的分母是两类能量差加权组装项之和的绝对值；它是登记边界指标，不是相对于原著数字的百分比误差。完整组装尚未建立。L4 可以保存检查点，但不支持断点恢复。

旧 start-high-cost-case.ps1 与旧 candidate-image 仅适用于它自己的历史环境。

## 5. 单状态操作示例（不是自动计算清单）

以下选择未作为旧先导验收的 `P11A-furan-G`，没有前序态依赖。应先确认本次实际选择与资源合同，再分别执行预检、预算创建和live；不是要求重跑已通过的苯G或N12-G。预算文件必须全新，43200秒是这一态的12小时上限，不是预计耗时。

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\high-cost-cases\installation-record.json --task P11 --mode preflight --unit P11A-furan-G --output-root ..\runs\p11-furan-g-preflight-new
python -B .\scripts\create-high-cost-budget.py --unit P11A-furan-G --ceiling-seconds 43200 --output D:\chem-work\p11-furan-budget-new.json
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\high-cost-cases\installation-record.json --task P11 --mode live --unit P11A-furan-G --budget D:\chem-work\p11-furan-budget-new.json --output-root ..\runs\p11-furan-g-live-new
```

有前序依赖的态还需 `--inputs` JSON。例如furan-GL需要本轮furan-G的**实际output子目录**，不是顶层输出根或历史冻结结果：

```json
{"P11A-furan-G": "D:/chem-work/runtime-install/runs/p11-furan-g-live-new/ACTUAL_RUN_ID/output"}
```

`ACTUAL_RUN_ID`须替换为终端返回的真实目录；GL另建包含真实GL unit的预算，再在其live命令增加 `--inputs D:\chem-work\p11-gl-inputs.json`。映射的键必须恰好匹配配置dependencies，父输出必须已通过且确认容器清理，并与当前来源、profile、依赖和镜像身份匹配。N16 GE等多父态须列全，不能用先导PASS补缺。ledger/preflight不传科学前序输入；未完成前序就停在账本/预检。

## 6. 资源、结果与失败处理

| 模式 | CPU／线程 | 内存 | scratch | 硬限 |
| --- | ---: | ---: | ---: | --- |
| ledger／preflight | 1 | 1GiB | 1GiB | 180秒 |
| P11单态live | 8 | 8GiB | 20GiB | 12小时 |
| P12单态live | 16 | 14GiB | 20GiB | 12小时、最多80几何步 |

读取终端返回目录中的 `output/result.json`、`output/worker-receipt.json`、`output/guard-receipt.json`、`output/run-manifest.json`、宿主记录和预算；按[专业服务矩阵](CURRENT_PROFESSIONAL_SERVICES_zh-CN.md)判断本态checks、方法和身份。保留实际存在的optimized.xyz、轨迹及中间文件；不要求所有状态共享同一轨迹格式。资源不足就记录拒绝，不改内存门槛或科学容差。旧已通过P12不因本轮文档检查重新准入。单态通过不等于全多态组装通过，L4无resume。

N16 两种百分比的公式、分母与舍入来源见 [P12 比较量说明](P12_COMPARISON_METRICS_zh-CN.md)。历史结果与验收身份保持不变。
