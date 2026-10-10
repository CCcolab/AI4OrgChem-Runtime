> 当前公开阅读节选。原始历史材料已按原字节保存在本地归档；本文件不是原件，不能用于原始哈希验收，也不把旧验收转移至当前代码。
> 原件 Git 提交：eb65b4586c83637569f6359814338c1292948861；SHA-256：35c178562dcf971596e1e0a82b36c1065079bee003bda098e533051d6e74411d。

# 第二批协议计算入口：本地受限复核

本批提供八个固定协议入口，优先按研究用途选择。P03—P10 是来源索引，不能据此推断八项都采用普通 RHF，也不能替代首批任意用户小分子的普通 RHF 单点服务。

| 研究用途 | 来源索引 | 已有记录复算（ledger） | 本批允许的新计算（live） |
| --- | --- | --- | --- |
| 约束扭转路径与能量账本 | P03 | 四个已优化端点的能量与方向 | 冻结 0° 几何的一个 B3LYPG/6-311G(d,p) 单点 |
| 两种条件态的直接项与轨道响应 | P04 | 十一个有效点及负直接项反例 | diphenyl imine 0°，原 DSI3/FUD 各自求解 |
| π–σ 条件能量比较 | P05 | 七角度同母体账本 | 原定义 17° G/FUD 一个点 |
| 双片段条件态的独立能量组装 | P06 | 0°/17° FUL-2/PDSI 账本 | 0° 一个点，原 RHF/STO-3G 定义 |
| 同 Hamiltonian 路径闭合 | P07 | 五态账本、桥接项及闭合 | 无新量子计算 |
| 丁二烯 GL 端点与参照敏感性 | P08 | 氢化热表值、历史优化账本 | 冻结 GL 几何，一次普通 RKS 加一次原 GL 核 |
| 环丁二烯固定几何条件态诊断 | P09 | 保存的 VDE/ADE/ESE 账本 | G-like RKS、稳定性诊断及 DSI 固定几何条件核 |
| 苯核排斥与键长交替响应 | P10 | 核公式、端点分解和五点旧账本 | δ=0/0.01/0.02/0.04/0.06 Å 五个普通 RKS 单点 |

不进行几何优化、不增加原协议角度、不把不同协议的 Hartree 差值相加。P08 的新固定几何能差不是重新优化的 ΔEA；P09 的固定几何诊断不是最终 VDE/ADE/ESE。任意用户分子的条件态 Compute 仍为 BLOCKED，首批普通 RHF 小分子服务另有已验证范围。

## 本机使用

1. 在 Runtime 仓库根目录执行 `python scripts/list-protocol-cases.py`，按研究用途选择入口。
2. 先运行保存结果的算术复核：`python scripts/run-protocol-case.py --task P03 --mode ledger --output-root D:\AI4Science\protocol-case-runs`。
3. 进行真实 AO/电子数预检：将上一步的 `--mode ledger` 改为 `--mode preflight`。这一步不运行 SCF，不保证收敛。
4. 新计算须使用新建的独立批次预算文件，再以 `--mode live --budget <batch-budget.json>` 执行。P07 没有 live 模式。已保留的本次验收预算和记录不得清空或复用为新批次。
5. 查看每次新目录里的 `host-execution.json`、`output/case-result.json`、`output/guard-receipt.json` 和资源记录。成功必须同时通过数值、来源、实际入口审计及容器删除后输出保留检查。

初次运行 live，可在输出目录旁新建 UTF-8 **无 BOM** 的 `batch-budget.json`，填写以下最小合同；已有预算文件不得清空后重用。随后把该文件的绝对路径传给 `--budget`。

```json
{
  "schema": "protocol-case-batch2-budget-v1",
  "ceiling_seconds": 6300,
  "one_attempt_per_case": true,
  "scientific_cases": ["P03", "P04", "P05", "P06", "P08", "P09", "P10"],
  "attempts": {},
  "old_root_budget_reused": false,
  "budget_is_accounting_not_method_approval": true
}
```

示例：`python scripts/run-protocol-case.py --task P08 --mode live --output-root D:\AI4Science\protocol-case-runs --budget D:\AI4Science\batch-budget.json`。只有当前记录的本地候选镜像可启动；选择入口不会改变固定科学输入或算法。主机建议使用 Python 3.12；容器内部 Python 与依赖版本按锁核验。

PowerShell 5.1 可使用 `scripts/start-protocol-case.ps1`，参数为 `-Task`、`-Mode`、`-OutputRoot`、可选 `-Budget`、`-PythonExe`、`-DockerExe`。Python 和 Docker 必须可访问；本机候选镜像身份登记于 `validation/protocol-cases/candidate-image.json`。安装路径与公开镜像分发是另外的工作，本文不宣称镜像已公开可下载。

live 预算固定为每项最多 900 秒（840 秒开始停止），4 GiB、2 CPU、2 线程、无 swap，七项总预留上限 6300 秒，串行、每项一次。ledger/preflight 使用 1 GiB、1 CPU、1 线程、120 秒。预算是拒绝和记账边界，不是预计耗时或收敛保证。已占用的预算不得自动重置；失败保留实际原因，不调容差或科学参数后自动重跑。

参考氢采用 PySCF 的单电子 UHF1e 专用终端，单独观测并与普通 UHF/RHF 分账。P04 的 20 次入口为 6 UHF＋8 UHF1e＋6 masked RHF；P05 的 11 次为 3 UHF＋4 UHF1e＋4 RHF；P06 的 6 次为 2 UHF＋2 UHF1e＋2 masked RHF。自定义母体固定点、GL 和 P09 条件积分也分别审计，不能仅以 `hf.kernel` 计数推断全部调用。若存在 `validation/protocol-cases/native-admission-pause.json`，启动器在创建新预算预留或容器之前拒绝新计算；这不改变已经启动任务的科学协议。

## 来源和解释

来源材料逐文件捕获，记录 SHA-256、Git blob、tracked/untracked 与上下文提交；原科研工作树没有作为可变依赖。部分驱动来自原科研工作树，不能把所有文件冒充为公开 science 的冻结提交。P09 条件核采用公开冻结的 h/S/F 默认路径；原工作树后续的 F/S-only 候选未启用。GL 核及 P09 受测 s/p/d 范围与各自来源逐项登记，不声称不同源码版本对所有体系等价。

P04/P05 的原来源报告函数调用 `git`；本地容器的捕获源码树没有 Git 工作树。适配器只在该报告函数缺少 `git` 可执行文件时返回原有 `unavailable`，登记来源锁、报告函数字节及 fallback 事件；不会把背景 HEAD 冒充捕获源码的提交，也不修改科学源码或全局 subprocess。首次因这一封装缺口退出的两个运行保留；修复后的独立受限合同继承全部先前已计费墙时，总上限仍为 6300 秒，不重新计算已通过项目。

P06 新环境使用本地候选依赖锁；原完整 runner 的历史精确 NumPy 版本检查没有在本次单点模式中运行，也未标为通过。P07 综合摘要属于 DERIVED，独立同 Hamiltonian 账本审计另行记录。P08 的原书 PDF 不随包携带，其实时认证为 NOT_EXECUTED；锁定表值的算术复算可独立开展。

保持原方法和阈值，保存旧失败记录。收敛、固定点、稳定性、能量解释及原命题分类是不同事项。此次工程和有限复算不构成对所有分子、所有科学结论或实验精度的认证。


实际结果以 `validation/protocol-cases/batch2-verification.public.json` 及交付目录中的原始运行记录为准；没有实际执行记录的项目保持 NOT_EXECUTED。
