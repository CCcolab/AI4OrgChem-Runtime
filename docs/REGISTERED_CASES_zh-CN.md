# 固定案例专业使用指南

本入口让用户在本地执行三个已登记的固定案例：重算发表表值统计、检查图规则与能量账本，或运行一次固定乙烯的占据表示控制。它不接收任意用户分子。

2026-10-08：三个固定任务已通过本地Docker候选的限定范围验收，镜像内96项工程测试全部通过。详见[实际验收报告](REGISTERED_CASES_ACCEPTANCE_20261008_zh-CN.md)。P02/P13不产生新量子计算；P01只验证固定乙烯同态占据表示控制。通用用户分子Compute仍BLOCKED。

## 1. 选择任务

| 你的目的 | Task ID | 本次实际执行 | 主要结果与限制 |
|---|---|---|---|
| 检查固定UV表值拟合及晶体对的结构方向 | `p02-statistics` | 从冻结表值重新拟合两条参考线，核对10个目标条目的分组和一个预定结构对 | 系数、R²、RMSE、残差、扭转角与C–N键差；原PDF/CIF验证 **NOT_EXECUTED**，不补缺失不确定度或计算p值 |
| 检查GL筛选、Kekulé候选和冻结能量恒等式 | `p13-graph-ledger` | 对2—7环并苯独立枚举完美匹配，由真实RDKit核对分子式，重算固定ESE/CESE账本并进行候选筛选 | 图计数、分子式、筛选结果和账本残差；Frozen-table lane，不产生新量子能量，也不复现历史优化 |
| 区分轨道表示变化与电子态变化 | `p01-orbital-density` | 固定平面乙烯的一次RHF/6-31G(d)，再各一次Boys和Pipek–Mezey占据旋转 | CH₂支持熵及占据空间、AO密度、电子数、RHF能量不变性残差；小范围控制，不是完整P01认证或不同条件态的能量比较 |

所有任务沿用各自冻结的数学定义和阈值。表值、几何、基组、分片或容差不能通过本入口替换；修改它们需要另立登记合同。

## 2. 准备本地运行条件

1. 在本轮隔离runtime工作区打开PowerShell，进入目录 `D:\AI4Science\ai4orgchem-runtime-workspaces\user-molecule\runtime`。
2. 使用已有的Python 3.12+和可运行的本地Docker引擎。启动器兼容PowerShell 5.1，负责选择已有Python，不自动安装依赖。
3. 使用本轮登记候选镜像及其本地身份记录 `validation/registered-cases/candidate-image.json`。启动器默认选取其中的不可变image ID；缺记录、来源不匹配或镜像不一致时应拒绝执行。本机已具备登记镜像；没有公开下载地址。其他电脑仅取得Git/ZIP，不能据此假定同一镜像已安装。
4. 输出放在独立运行根目录，例如 `D:\AI4Science\ai4orgchem-runtime-runs\registered`。不要选择原科研项目、runtime源码或science缓存目录作为输出。

本机验收显式使用 `C:\Program Files\Docker\Docker\resources\bin\docker.exe`，以及现有 `C:\Users\chenx\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`。若终端找不到工具，在下列命令末尾增加 `-DockerExecutable 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'` 和 `-PythonExecutable '<现有Python完整路径>'`。启动器不会修改PATH或全局PowerShell执行策略。

Git源码或ZIP包含程序和来源材料，不等于已准备好科学计算环境。构建依赖版本及wheel哈希已锁定；新增RDKit/Pillow及随包库的完整许可证/对应源码审查尚未闭合。候选用于本地固定任务，镜像分发 **BLOCKED**。构建配方复用本机既有r3基础镜像，不是任意电脑上可直接安装的完整软件包。

## 3. 执行一个固定任务

按目的选择一条命令。每次只启动一个任务，启动器建立新运行目录并保留日志。也可通过统一本地入口选择命题：

```powershell
.\scripts\start-local-runtime.ps1 -Action Run -Proposition P02 -OutputRoot D:\AI4Science\ai4orgchem-runtime-runs\registered
```

将P02替换为P13或P01，范围仍是下列固定任务。P14沿用原运行指南；其余命题未增加计算入口。

```powershell
.\scripts\start-registered-case.ps1 -Task p02-statistics -OutputRoot D:\AI4Science\ai4orgchem-runtime-runs\registered
```

```powershell
.\scripts\start-registered-case.ps1 -Task p13-graph-ledger -OutputRoot D:\AI4Science\ai4orgchem-runtime-runs\registered
```

```powershell
.\scripts\start-registered-case.ps1 -Task p01-orbital-density -OutputRoot D:\AI4Science\ai4orgchem-runtime-runs\registered
```

找不到合适Python时，可以给同一命令增加 `-PythonExecutable`，指向本机已有Python 3.12+的完整路径；不要安装或替换原科研环境来绕过准入。`-Image`也只能填写已登记的完整image ID，不能用随意标签替换。

每次运行的资源合同为 **1 CPU、1 GiB内存、120秒总墙钟、100秒软停止**，不增加交换额度。时间数值是上限，不是保证完成时间。P01的普通SCF、Boys、PM kernel各至多调用一次；内部原算法的迭代限额保持冻结协议。没有自动重试、继续旧目录或恢复运行。

软停止先请求结束；正在执行的C扩展未必立即响应。超时、强杀或缺少最终回执不能记为PASS。先保留错误和未知计数，确认原因后才能另行决定是否提交新任务；不要复用本次预算或修改科学阈值。

## 4. 找到结果

终端最后输出 `records`，指向本次新运行目录。先看其中的 `host-execution.json` 和 `host-run-manifest.json`，确认任务、退出码、实际镜像身份、执行范围及容器清理情况。

主要计算材料位于运行目录的 `output` 下：

- `case/case-report.md`：先读这一份范围化报告。
- `case/case-result.json`：数值、验收检查及来源声明。
- `run-manifest.json`、`worker-receipt.json`、`guard-receipt.json`：本次输入输出摘要、来源/平台核查及实际保护记录。
- P01另保留操作账本和 `occupied-representations.npz`，用于核对每次表示的系数与密度。

三个适配器统一保存 `case-report.md`。底层数值结果和父入口的完整验收状态分别记录。

## 5. 判读结果

**P02**：检查两条拟合线系数是否在原0.05容差内，以及预定晶体对两个方向检查是否通过。这只说明所列冻结表值的统计和规则相容；没有重新测量光谱、读取原PDF或精修CIF，也不证明扭曲的因果来源。

**P13**：检查15项原验收、6组图计数、真实RDKit分子式和ESE/CESE残差。源表的最高能量候选需要先经过GL过滤，不能把全体候选的最高能量直接当成合格选择。原PDF为 **NOT_REAUTHENTICATED**，实际PDF SHA为null；声明来源和真实读取身份分别记录。当前账本没有新量子计算调用。

**P01**：先确认普通RHF收敛，再看占据子空间、密度、电子数和能量不变性检查，同时观察支持熵变化。Boys/PM旋转改变单轨道表示，不代表得到不同电子态；这里的能量残差用于同态不变性，不是研究性的稳定化能差。只要任何原门槛失败，控制结果就不合格，不能靠放宽容差补成PASS。

成功只覆盖本次固定任务。失败、BLOCKED、NOT_EXECUTED和缺失最终回执需要分别报告；程序退出0也不能替代完整证据检查。三个固定任务不解除用户分子入口的 **Compute BLOCKED**。

## 6. 保存与反馈

保留整个本次运行目录。反馈时提供Task ID、`records`路径、最终状态/退出码、镜像ID、runtime执行提交、报告与对应错误日志。无需先上传原著PDF、检查点或原科研项目。

本次新增部署的身份、分发限制和实测记录入口见 [部署边界](REGISTERED_CASES_DEPLOYMENT_BOUNDARIES_zh-CN.md)。既有P14七任务继续沿用 [分层运行合同](RUN_zh-CN.md)；L4可保存检查点，但**不支持恢复运行**。
