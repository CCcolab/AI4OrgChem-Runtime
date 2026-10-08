# 第三批 P11/P12：本地多态优化入口

本批提供 **78 个固定状态的独立几何优化入口**：P11 为 17 态；P12 的 N12/N14/N16 分别为 8/23/30 态。每次 `live` 选择一个状态，执行一次新优化。实现是本地部署候选；本轮新高成本科学验收仍待实际运行记录确认，不能由历史账本、预检或工程测试推定通过。

入口使用独立的 `runtime/high_cost_cases`、`locks/high-cost-*.json` 和 `configs/high-cost-cases-v1.json`。原第二批 P03—P10 的源码锁、科学资产、预算和验收结果保持原有身份；原科研目录只读。任意用户分子的条件态 Compute 仍为 `BLOCKED`。

## 选择研究范围

| 范围 | 固定对象与状态 | 数量 | 原科学定义 |
| --- | --- | ---: | --- |
| P11-A | furan：G、GL、GE1、GE2 | 4 | B3LYPG/6-31g(d)，grid 3；源 h/F/S 掩码，无 ERI 删除；约束参数优化 |
| P11-B | benzene：G、GL、GE1；cyanobenzene：G、GL_I、GL_II、GE1—GE7 | 13 | B3LYPG/6-31g(d)，grid 3；源2007 F/S规则，保留物理 hcore 与 ERI，全平面优化 |
| P12 N12 | `[12]-555`：G、GL、5 个 GE 代表及 1 个独立对称控制 | 8 | B3LYPG/6-311g(2df,p)，源2011条件算子，全平面 |
| P12 N14 | `[14]-665`：G、GL、全部21个 GE | 23 | 同基组，7个相邻对及14个非相邻对，每对权重1 |
| P12 N16 | `[16]-5555`：G、GL、全部28个 GE | 30 | 同基组，8个相邻对及20个非相邻对，每对权重1 |

P11-A 的 G→GL→GE1/GE2 使用本轮已验证前序输出。P11-B 各态按源 runner 的固定初始化独立执行。P12 GL 和 GE 使用本轮 G 输出；**N16 GE 还必须提供本轮 GL**，满足 G/GL 结果审阅门禁。所有输入的来源、依赖、profile 和镜像 SHA 必须匹配当前候选，历史 `pass=true` 记录不能替代本轮前序。

N12 的 GE 代表零基组对为 `(0,1)、(0,2)、(0,3)、(0,5)、(1,3)`，每对重数3；控制对为 `(2,3)`，入口 ID 带 `-control`，不进入加权和。只有参考 GL 的 C3 几何及独立控制满足原门槛，才能使用重数：距离矩阵残差不超过 `0.002 Å`，控制能差不超过 `0.02 kcal/mol`。失败时拒绝加权，不自动扩展、改重数或继续组装。当前单态 `live` 不组装新 CESE。

## 先查看账本与预检

在 Runtime 仓库根目录使用现有主机 Python 启动脚本；主机端只负责编排，科学依赖安装在新容器内。可通过 `-PythonExe` 和 `-DockerExe` 指定可执行文件，脚本不会安装或升级宿主科研环境。

```powershell
$PythonExe = 'python'
$DockerExe = 'docker'
$OutputRoot = 'D:\AI4Science\high-cost-case-runs'

& $PythonExe -B .\scripts\list-high-cost-cases.py

.\scripts\start-high-cost-case.ps1 -Task P11 -Mode ledger `
  -OutputRoot $OutputRoot -PythonExe $PythonExe -DockerExe $DockerExe

.\scripts\start-high-cost-case.ps1 -Task P12 -Mode ledger `
  -OutputRoot $OutputRoot -PythonExe $PythonExe -DockerExe $DockerExe

.\scripts\start-high-cost-case.ps1 -Task P12 -Mode preflight `
  -Unit P12-N16-G -OutputRoot $OutputRoot `
  -PythonExe $PythonExe -DockerExe $DockerExe
```

`ledger` 复核保存能量的恒等式、权重和历史范围；P12 另复核保存几何的 N12 对称控制。`preflight` 构建真实 Mole/AO、核对构型、原子/电子数及状态映射，不运行积分、SCF、梯度或优化器。省略 `-Unit` 时预检该 Task 的全部固定状态。两种模式都不保证新优化收敛，也不重新认证原 P11/P12 科学命题。

候选镜像登记路径为 `validation/high-cost-cases/candidate-image.json`。启动器核对完整镜像 ID、构建提交、来源锁、依赖锁和资源 profile；本地文件存在不等于镜像已公开可下载。

## 新建独立预算后逐态运行

`live` 必须有一个精确 `-Unit` 和独立第三批预算。下面只演示 N16 G、GL及一个 GE 的三态允许清单；`129600` 秒是三次各12小时的名义封顶，不是预计耗时或自动连续执行授权。完整状态 ID 与 dependencies 以 `list-high-cost-cases.py` 输出为准。

```powershell
$Budget = 'D:\AI4Science\high-cost-case-runs\batch3-n16-three-states.json'

& $PythonExe -B .\scripts\create-high-cost-budget.py `
  --output $Budget --unit P12-N16-G --unit P12-N16-GL `
  --unit P12-N16-GE-g01-g02 --ceiling-seconds 129600

.\scripts\start-high-cost-case.ps1 -Task P12 -Mode live `
  -Unit P12-N16-G -Budget $Budget -OutputRoot $OutputRoot `
  -PythonExe $PythonExe -DockerExe $DockerExe
```

每次启动会创建新运行目录。G 完成并且 `host-execution.json` 通过、已确认所属容器删除后，为 GL 准备一个 UTF-8 **无 BOM** 的 JSON 输入映射，值必须指向该次运行的 **`output` 子目录**，而不是运行目录或历史科研目录：

```json
{
  "P12-N16-G": "D:/AI4Science/high-cost-case-runs/<本轮成功G运行目录>/output"
}
```

将实际路径填入例如 `D:\AI4Science\high-cost-case-runs\inputs-n16-gl.json`，再传给 `-Inputs`：

```powershell
.\scripts\start-high-cost-case.ps1 -Task P12 -Mode live `
  -Unit P12-N16-GL -Budget $Budget `
  -Inputs 'D:\AI4Science\high-cost-case-runs\inputs-n16-gl.json' `
  -OutputRoot $OutputRoot -PythonExe $PythonExe -DockerExe $DockerExe
```

N16 GE 的输入 JSON 必须同时列出 `P12-N16-G` 和 `P12-N16-GL`，分别指向本轮已成功、清理闭合的输出目录；启动命令将 `-Unit` 改为 `P12-N16-GE-g01-g02` 并使用该 JSON。前序文件在验证哈希后复制为只读 `/inputs` 快照；缺前序、字节改变、环境身份不同或清理未闭合都会拒绝。

预算由 `create-high-cost-budget.py --output … --unit … --unit … --ceiling-seconds …` 生成，不手工改写。开始前为一态预留完整硬墙时，结束后连同清理耗时结算；失败也计费。每态一次，无自动重试；已有预算不能清空、扩大清单或重置。未确认容器删除的状态保留全额预留，并拒绝后续并发启动。预算不复用第二批或更早的 OPEN 账本，也不证明科学方法已获批准。

## 资源与耗时

| 模式 | 内存硬限 | CPU / 线程 | 软停止 / 硬墙时 | 可用 scratch 要求 |
| --- | ---: | ---: | ---: | ---: |
| P11 live | 8 GiB | 8 / 8 | 43080 / 43200秒 | 20 GiB |
| P12 live | 14 GiB | 16 / 16 | 43080 / 43200秒 | 20 GiB |
| ledger / preflight | 1 GiB | 1 / 1 | 120 / 180秒 | 1 GiB |

资源准入还要求余量：Docker engine/guest 内存比任务硬限多1 GiB；live 主机可用内存比硬限多2 GiB，metadata 多512 MiB；输出所在磁盘比 scratch 要求多1 GiB。P12 保留源 PySCF `max_memory=12000` 设置，该设置不等于容器14 GiB硬限或实测峰值。

这类优化通常跨小时乃至多天。历史 N14 在16线程下 GE 完成间隔约3.25—5.41小时；历史 N16 监督事件中后19个 GE 的完整子进程墙时共约84.38小时，平均4.44小时，范围3.49—5.25小时。这些是旧环境记录，不能作为本候选的完工预测或新验收耗时。12小时单态封顶也不保证收敛。

资源未知或不足时返回 `BLOCKED_RESOURCE_UNKNOWN` / `BLOCKED_RESOURCE_CAPACITY`；保留准入记录，不提高 WSL 配置、停止其他进程或下调科学门槛。存在 `validation/high-cost-cases/admission-pause.json` 时拒绝新 live 预留。检查点保存已经产生的进度和坐标，**不支持恢复运行**；启动器和适配器禁止 `resume`、`force` 及复用历史 `already_complete` 结果。

## 查阅结果与来源

一次运行的主机记录包括 `host-execution.json`、`host-run-manifest.json`、`admission.json`、镜像/容器检查、启动命令、`commands.jsonl` 和容器 stdout/stderr。`output` 下保留 `result.json`、`worker-receipt.json`、`guard-receipt.json`、`native-events.jsonl`、起止资源记录、`run-manifest.json`，以及 live 的检查点和科学产物。失败或中断的记录也保留。

P11 live 保存 `p11-state.json`、`optimized.xyz`、`density.npy` 和源进度；P12 保存 `source-routing-review.json`、原 runner 状态 JSON、优化 XYZ、进度及条件态 density NPZ。P12 普通 G 的原 runner 不保存密度 NPZ，不能声称每个 G 都有密度归档。结果登记原协议与独立 runtime ID、方法、精确前序范围、source/dependencies/profile/image SHA。成功需同时满足源数值门禁、真实入口计数、资源核验、输出哈希及所属容器删除后证据复核；单一 `result.status=PASS` 不够。

第三批来源合同固定76份显式文件捕获（含许可/署名），实际字节清单见 `locks/high-cost-scientific-assets.json`。每份文件登记来源工作树上下文 HEAD、tracked 状态、HEAD blob、捕获 blob及SHA；来源包含 dirty 工作树材料，**不能把全部捕获文件说成来自同一个 HEAD**。原项目与旧 runtime 不作为可写执行目录。geomeTRIC `1.1.1` 及补充依赖仅安装到新本地容器，不升级原 WSL/宿主科研环境。

P12 的范围是 N12/N14/N16 受测三点，不是完整六点。旧同基组 CESE 分别为 `+2.887010、−15.947079、−0.339527 kcal/mol`，对应原著印刷值 `+2.59、−16.28、−0.65`；数值差异继续披露，不能声明逐数字复现。历史 N16 相对 CESE 为约2.103137%，原10%起点门槛保持；历史2011实现对齐仍 `NOT_ESTABLISHED`，电子态连续性不由现有 runner 证明。单态新优化不会自动组装完整新账本、改变分类、扩至N18/N20/N22或生成训练标签。

本轮最终状态须由 root 按实际镜像、CI、metadata 与逐态记录填入 `PROTOCOL_CASES_BATCH3_ACCEPTANCE_zh-CN.md`。当前不宣称新的78态全部或任何一态已通过高成本科学验收。WSLc 继续 `BLOCKED_PAUSED`；GitHub Actions 为 `NOT_EXECUTED`；公开镜像分发为 `BLOCKED_LOCAL_ONLY`，没有公开推送、标签或 Release。
