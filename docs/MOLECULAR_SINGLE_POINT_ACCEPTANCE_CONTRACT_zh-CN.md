# 用户分子普通单点首版验收合同

2026-10-08，合同0.1。任务 `single-point`，profile `rhf-631gd-small-v1`，协议 `ORDINARY_MOLECULAR_SINGLE_POINT_V0.1`。本合同对应用户授权的“用户 XYZ → 普通单点 → 轨道／AO密度 → 本地报告与导出”，与旧条件态比较的科研规则及执行预算分开。

本文建立时：候选代码和宿主测试已形成；容器工程验收、真实分子执行和同版本 PySCF 直接调用对照均 **NOT_EXECUTED**。本文冻结目标及门槛，不提供尚未发生的 PASS。该建立时状态保留为执行前事实；2026-10-08实际验收已完成，未改变下列门槛与8次SCF总预算。实际完成状态、代码提交、镜像 ID、原始证据和失败在[本轮验收报告](MOLECULAR_SINGLE_POINT_ACCEPTANCE_20261008_zh-CN.md)及[机器状态](../validation/molecular-service/deployment-20261008.json)中登记。

## 1. 输入与支持范围

| 项目 | 首版合同 |
|---|---|
| 请求 | [molecular-single-point-v1.json](../schemas/molecular-single-point-v1.json)；拒绝未知和重复 JSON 键及非有限值 |
| 结构 | 单份严格 XYZ；显式 Å；首行数量、注释和原子行完整，不接收额外结构 |
| 元素、电荷、自旋 | H/C/N/O，charge=0，multiplicity=1，正偶电子数 |
| 规模 | 1—20原子；实际 PySCF AO 数≤80，超过者在 SCF 前拒绝 |
| 几何 | 三维允许，无专有片段和 xy 定向要求；每个坐标分量绝对值≤10000 Å，两核距离≥0.5 Å |
| 几何处理 | 不加氢、不旋转／居中、不重排、不优化、不转换未声明单位；保留原始字节与原子映射 |
| 文件 | 请求和 XYZ 直接位于同一受控真实目录；XYZ 仅 basename；拒绝逃逸、symlink 和 reparse／junction |
| profile | [rhf-631gd-small-v1.json](../profiles/molecular-service/rhf-631gd-small-v1.json)；关键字段集合、值和类型固定，不静默换 profile |

输入准入只说明格式、首版范围和工程几何检查通过。它不认证化学合理性、键连接、稳定构型或研究结论。输入阶段不调用 PySCF，不猜测 AO 数；实际 AO 与电子数由引擎最后复核。

## 2. 方法及单任务资源合同

复用锁定版本的 PySCF 普通闭壳层 RHF/6-31G(d)，`symmetry=False`；`conv_tol=1e-12`、`conv_tol_grad=1e-8`、`max_cycle=100`、`max_memory=768 MB`。不复用项目特有的 h/S/F 或 ERI 条件屏蔽，不运行 DFT、开壳层、局域化、优化、密度网格或条件 NR。

每个独立任务使用1 CPU、1线程、1进程、1 GiB cgroup内存上限，无额外交换额度；受控执行硬期限120秒，软停止100秒，期限不能延长。核调用预算是 **1次普通 RHF SCF、0次 Boys、0次 Pipek–Mezey、0次条件 NR**，每次原生 dispatch 前后保留守卫检查。普通 RHF 所需积分、J/K及端点能量求值属于本方法必需操作，不能因此声明“全部量子操作为零”。

不自动重试、退款、恢复旧目录或改方法。操作账本中的持久预调用 STARTED 是预算意图记录；崩溃时它不能独立证明 native 已进入。实际进入和返回的计数需与持有的 guard 回执分开记录。原生 C 扩展不能保证立即响应软停止；强杀、OOM或未闭合计数保留未知或失败，不产生合格结果。

## 3. 普通态数值验收

进入 SCF 前，重叠矩阵须有限且对称，最小本征值≥`1e-10`、条件数≤`1e10`。超出支持范围时拒绝，不裁剪 AO、不调整基组、不移动核或放宽门槛。

同一端点的独立检查使用 `D=2 C_occ C_occ^T`，`P=S^(1/2) D S^(1/2)/2`，`F~=S^(-1/2) F S^(-1/2)`。十二个验收键全部存在且均为逻辑 true，才允许 `NUMERICALLY_QUALIFIED_ORDINARY_RHF`：

| 验收键 | 冻结条件 |
|---|---|
| `scf_converged` | PySCF 明确报告收敛 |
| `closed_shell_occupations` | 占据只为0或2， occupied数量与电子数一致 |
| `electron_number` | `abs(Tr(D S)-N) ≤ 1e-8` |
| `occupied_orthonormality` | `‖C_occ^T S C_occ-I‖_F ≤ 1e-8` |
| `whitened_projector_idempotency` | `‖P²-P‖_F ≤ 1e-8` |
| `density_reconstruction` | AO密度重构相对 Frobenius残差≤`1e-9` |
| `energy_ledger_closure` | `Tr(D h)+0.5 Tr(D V_HF)+E_nuc` 与SCF总能量差≤`1e-9 Eh` |
| `whitened_fock_projector_commutator` | `‖F~P-PF~‖_F ≤ 1e-7 Eh` |
| `finite_arrays_and_energy` | 所有必需数组和能量均为有限实数，形状符合原AO规模 |
| `symmetric_ao_matrices` | 密度、Fock、hcore、V_HF各自最大对称性差≤`1e-10`，使用各数组原生单位 |
| `ordinary_fock_equals_hcore_plus_veff` | Fock与hcore+V_HF的最大绝对差≤`1e-10 Eh` |
| `package_energy_ledger_closure` | 同一端点PySCF电子能与两电子项核对的最大绝对差≤`1e-9 Eh` |

能量单位为 Hartree，结构单位为 Å。HOMO／LUMO 能隙是观察值，不是本轮合格门槛。波函数稳定性 `stability` 和 `stability_status` 均为 **NOT_EXECUTED**；普通收敛及数值残差不自动构成稳定性或能量极小态结论。

## 4. 输出、身份与完整运行验收

主要输出为 `output/calculation/report.md`、`result.json`、`orbitals-density.npz` 和 `operation-ledger.json`。NPZ保存原 AO 顺序下的 S、D、canonical系数、轨道能级、占据、F、hcore与V_HF；结果保留 AO标签和逐原子 AO／shell映射。这里输出 AO密度矩阵，不宣称已生成网格密度、等值面或实验微观测量。

完整运行必须独立核对：

1. 原请求、XYZ、profile、只读输入快照 manifest及来源／依赖锁哈希，完整镜像 ID、构建代码提交、当前启动器身份和执行 ID对应。
2. 闭合执行合同所有字段、类型、单任务资源、期限及调用预算；结果内完整合同与执行合同一致。
3. 非root UID、只读源码和输入、网络关闭、内存／CPU／交换／进程限制及开始／结束资源记录。
4. 实际保护绑定、恢复状态和原生调用计数：普通 SCF返回1，Boys／PM／条件 NR均0，没有被禁止调用或篡改。
5. 输出、报告、guard及run-manifest哈希对应，worker退出0；主机再次核查容器退出及OOM状态。
6. 按执行ID验证容器所有权后删除，宿主输出继续存在且哈希复核通过。

数值合格、worker完整验收和host最终验收分开登记。缺少最终资源、guard、输出或容器清理证据时，不能用已有能量值或退出0替代 PASS。失败／拒绝记录保留实际命令与错误；不删除历史或使用旧成功结果补当前失败。

## 5. 本轮真实执行预算与验证路径

本轮拟冻结四个小分子示例：水、三维甲烷、三维氨、乙烯。确切输入字节、请求及方法身份由执行前的来源／输入记录固定。它们覆盖H/C/N/O及非平面用户结构；不自动推广为所有满足格式的分子都必然收敛。

| 路径 | 数量与预算 | 验证目的 |
|---|---|---|
| 正式普通单点入口 | 4个分子，各1次普通RHF kernel；串行 | 输入、封装、数值资格、资源、守卫及输出闭合 |
| 同版本PySCF直接调用 | 同4个分子，各1次普通RHF kernel；串行 | 同一库、同几何／电荷／自旋／方法／基组／收敛设置的包装一致性对照 |
| 实际AO超限拒绝 | 1个输入，0次SCF kernel | engine实际AO数超过80时须在SCF前拒绝并保留记录 |

本轮总上限为 **8次普通 RHF kernel**；不自动重算或重新分配失败预算。直接调用对照复用同一成熟计算库，属于包装一致性验证，**不构成独立科学引擎、方法等价或实验精度认证**。同几何、方法、基组、单位、收敛设置和profile下，直接对照的必需比较门槛冻结为：

| 比较量 | 容差 |
|---|---|
| 总能量绝对差 | ≤`1e-9 Eh` |
| AO密度相对Frobenius差 | ≤`1e-9` |
| 电子数绝对差 | ≤`1e-8` |
| 重叠矩阵S最大绝对差 | ≤`1e-12` |

逐列MO系数不作为比较要求，因为轨道符号与简并空间表示并不唯一。排序轨道能级可额外观察绝对差是否≤`1e-8 Eh`，但它不是首版必需接受项。执行授权记录须保存这些冻结比较量，不因失败放宽。

宿主和镜像内工程测试使用明确fake／禁止科学dispatch路径，不计入这8次真实预算，也不能把fake运行记成科学PASS。Windows不能创建真实symlink测试fixture时应标SKIP，并在Linux候选镜像补执行，不能以mock测试替代真实fixture记录。

旧原生条件核账本、既有失败记录和固定案例预算原样保留。本轮不用旧科研预算，不重新执行专著全部计算，不恢复条件态或WSLc验收。

## 6. 状态边界与后续扩展

本合同通过实际验收后，只开放本profile内的用户自选分子普通单点与所列轨道／AO密度导出。离子、开壳层、DFT、其他元素、局域化、几何优化、扫描、网格可视化或性质预测分别属于后续待办，不因底层库有接口而宣称已部署。

旧用户条件态 Compute继续 **BLOCKED**。WSLc升级／实机验收暂停，GitHub CI **NOT_EXECUTED**，镜像分发 **BLOCKED**，源码公开另行确认；不恢复外部专家咨询，不公开推送或发布。既有研究和固定案例交付的身份与结论不因新增普通入口而重写。
