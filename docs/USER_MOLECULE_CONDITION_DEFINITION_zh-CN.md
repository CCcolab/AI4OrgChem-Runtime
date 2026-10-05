# 用户分子条件态：操作性定义与独立参考合同

日期：2026-10-05；DRAFT-3 / DESIGN_ONLY / NOT_IMPLEMENTED。依据固定科学提交 `28511f3d84fa65707a107cde1e8121a7b4334ecb` 的 P09 源码作静态说明。本页没有完成变分证明、独立实现或新计算。主合同见 [设计与验收](USER_MOLECULE_ENTRY_DESIGN_zh-CN.md)，外部关系见 [已有方法对照](USER_MOLECULE_METHOD_COMPARISON_zh-CN.md)。

## 1. 固定几何、基底与矩阵操作

固定 R、原子顺序、球谐 AO 基组及两个碳组 A/B。源代码按 AO 对 z 反射的奇偶性分类：奇为 π，偶为 σ；这不是占据 π 轨道或化学键识别。σ AO 不归入 π 组。原始重叠、单电子积分和四指标积分分别记 S、h、I。

定义线性操作 P：仅把不同组 π AO 之间的矩阵元置零，其余保留。令 S̃=P(S)、h̃=P(h)。四指标 Ĩ 由锁定十五类删除谓词及八重排列闭包生成；不能用“所有跨组积分归零”代替。S̃ 非正定拒绝，不正则化。

J、K 与源码的 AO 下标约定为：

```text
J[p,q] = sum(r,s) Ĩ[p,q,r,s] D[r,s]
K[p,q] = sum(r,s) Ĩ[p,r,q,s] D[r,s]
```

确切依据：`software/src/ai4orgchem/qm/p09_ao_classification.py`、`p09_energy_assembly.py:restricted_jk`、`p09_conditional_scf.py:_evaluate_density`，以及根目录 `configs/qm/p09_exchange_integral_classes_v0.1.yaml`。精选原文沿用 DRAFT-2 审阅包哈希。

## 2. 报告能量与迭代算子

令 a 为锁定全局杂化精确交换比例，Esl[D]、Vsl[D] 为 PySCF 在原分子 AO 和登记网格上返回的 semilocal XC 能量、势。能量为：

```text
Econd[D;R] = Tr(h̃D) + 1/2 Tr(J[D]D)
             − a/4 Tr(K[D]D) + Esl[D] + Enuc(R)
Fraw[D]   = h̃ + J[D] − a/2 K[D] + Vsl[D]
Fcond[D]  = P(Fraw[D])
```

这是锁定源码的操作性重述。S̃ 用于求解和资格度量；它不直接替代原 AO 上的 XC 密度求值。核排斥使用同一 R，不删除核间项。是否把这些操作解释为特定允许变化集合上的能量驻定问题，仍须审阅，不能由公式外观或账本闭合认定。

## 3. 密度、占据及简并

迭代在 S̃ 度量中解 `Fdiag C = S̃ C ε`；Fdiag 可能是 DIIS 外推后的 Fcond。随后调用全体系 `mean_field.get_occ`，闭壳层候选密度为 `Dcand=C diag(occ) Cᵀ`，occ 按固定 RKS 实现分配。目标电子数为 N，目标候选满足 `Tr(S̃D)=N`、`DS̃D=2D`，实际误差须验收。

现有接口没有逐组固定电子数参数，也没有显式的跨组 π 密度逐项清零步骤。不能从 P(F)、P(S) 或 A/B 名称推断片段电子数守恒或 D 的跨组块必为零。阻尼阶段的混合密度及初始普通态密度不保证满足上述幂等关系；报告不把中间密度当作合格端态。

保留全局填占据原义，不增加逐组填占据、MOM、分数占据、能级移位或其他静默状态选择。简并、小 gap 和参考固定点不一致须记录末次 ε/occ、初始密度、迭代设置及诊断。简并时占据子空间选取可能依实现而变；没有登记处理与覆盖证据的情形保持研究资格未就绪，不能自动把另一固定点归为代码错误。

`occupied_virtual_gap_hartree` 源自末次对角化的 ε/occ，Fdiag 可能经过 DIIS；最终 Fcond 在返回 D 上重新求值。必须记录 `gap_operator_source=LAST_DIAGONALIZATION_POSSIBLY_DIIS`。它不代表最终未外推 F 的谱间隙，更不是稳定性证明。额外最终谱诊断若引入，只读求值、单独命名，不替换 D 或原核。

## 4. 允许变化与解释状态

当前能确定的是候选密度的生成过程和条件固定点操作。完整的物理允许轨道/密度集合，特别是投影 P(Fraw) 对哪些轨道变化构成所报能量的驻定条件，尚未建立。

暂采用 `energy_interpretation=CONDITIONAL_FIXED_POINT_FUNCTIONAL`、`variational_status=NOT_ESTABLISHED`、`stability_analysis=NOT_EXECUTED`。这不等于发现算法错误，也不等于已证明其非变分性。两态收敛和残差合格不证明全局基态或稳定极小值。[PySCF 稳定性说明](https://pyscf.org/user/scf.html#stability-analysis)也区分 SCF 收敛与稳定性。

A01/A06 在研究开放前须选择并留下审阅依据：证明允许变化与算子/能量关系，或明确批准仅限操作性固定点解释的范围。若需要改变方程、密度集合或占据，则是新的科学协议；旧核与旧记录保留。未完成此项，不生成研究范围批准记录。

## 5. 每项数值量的度量合同

表中阈值是候选值；只有版本、profile、公式及实际验证冻结后才可用于服务资格。范数均按当前 AO 表示计算，不冒充基底无关可观测量。

| 量 | 定义、度量与单位 | 性质 / 候选标准 |
|---|---|---|
| 普通态 SCF | 固定 PySCF RKS 的 converged 与实际 conv_tol/conv_tol_grad 等 | 必需；conv_tol 候选 1e-9 Eh，完整终止参数仍待冻结 |
| 条件密度变化 | `||Dcand−D||F / max(||Dcand||F,1)` | 必需终止量；2e-8；不是最终对易子残差 |
| 条件能量变化 | 相邻迭代求值能量绝对差，Eh；首轮无定义 | 必需终止量；显式传入 1e-9 Eh，首轮 null+reason |
| 占据电子数 | sum(occ)=N | 必需；固定闭壳层占据与电子数一致 |
| 普通态电子数 | `Tr(SDord)−N`，电子数 | 必需；绝对值候选 1e-7 |
| 条件态电子数 | `Tr(S̃Dcond)−N`，电子数 | 必需；绝对值候选 1e-7 |
| 物理度量条件电子数 | `Tr(SDcond)`，电子数 | 单独诊断；不自动要求等于 N，若作门禁须另审依据/阈值 |
| 网格积分电子数 | nr_rks 返回的积分值，电子数 | 单独积分诊断；不能混用屏蔽度量的 1e-7，若作门禁另登记 |
| 最终对易子 | `||Fcond D S̃−S̃ D Fcond||F`，当前 AO 表示 | 必需；候选 1e-5；Fcond 在最终 D 重算 |
| 闭壳层幂等性 | `||D S̃ D−2D||F / max(||D||F,1)` | 必需；候选 1e-7 |
| S̃ 特征值/条件数 | eigvalsh 最小值；2-范数条件数 | 最小值必须 >0；病态上限 TBD，D2 前冻结 |
| 屏蔽残差 | 禁止块中 S̃、最终 Fcond 的最大绝对元素 | 分别记录量与 AO 单位；候选各 1e-12，不要求 D 同一块为零 |
| 账本闭合 | 五项和与 Econd 的差，Eh | 必需；候选 1e-9，不替代能量—算子关系核查 |
| gap | 末次对角化 occupied/virtual ε 的差，Eh | 诊断；未定义 null+reason；小 gap 判据与动作 TBD |

必须量非有限则 FAIL；诊断未定义则 null+reason。每项还记录 metric_id、formula_version、threshold_version、required、operator_source。`energy_tolerance` 原核默认 1e-10 与候选显式 1e-9 不同，调用时必须传明并形成新 profile 身份，不声称默认等同。

## 6. 两类外部验证及参考谱系

### 路径 I：同一数学定义下的独立实现

用于验证代码。继续复用锁定 PySCF 2.14.0 提供原始 AO 积分/XC，但独立参考不得导入或调用被测 `_evaluate_density`、`restricted_jk`、掩码/谓词辅助或条件 SCF。根据登记规则原文分别写标量删除判定、J/K 收缩、能量账本、S/F 操作、占据及条件迭代；基础 NumPy/SciPy 可共用，依赖共享部分逐项明示。不能声称验证了底层积分/XC。

先在冻结的相同 D 上比较 Ĩ、J/K、Fraw/Fcond 与每个能量分量，再比较完整条件迭代。参考 DIIS 可不同，但初始密度、占据策略、停止量和状态选择须可比。不得只比较总能量或把被测输出当唯一 expected。

| 证据层 | 可验证内容 | 共享盲点 / 当前状态 |
|---|---|---|
| 普通态独立 PySCF 驱动 | 输入适配、常规 RKS 和普通态账本 | 同一积分/XC 库；新体系 NOT_EXECUTED |
| toy/标量 witness | 十五类删除、排列、系数与固定密度账本 | 不验证真实体系完整 SCF；新合同 NOT_EXECUTED |
| 两 ERI 存储路径 | 存储与收缩模式的一致性 | 共享条件 SCF/规则，不能关闭公共核盲点；新体系 NOT_EXECUTED |
| 最小独立条件参考 | 固定密度算子及完整条件固定点 | 明示 PySCF/线代共享；参考 NOT_IMPLEMENTED / NOT_EXECUTED；D3 必需 |
| 允许变化关系核查 | 能量导数与算子在明确变化集合中的关系 | 定义本身待审；无证明或运行证据，不宣称变分成立 |

最小夹具计划：两片段平面乙烯 C2H4（C1/C2 分组）为基础参考候选；仅作为数学实现夹具，不推荐切断双键来获得一般化学作用能。平面 s-trans 丁二烯与第二个小 C/H 体系候选用于 A05/A07；第二体系可选择上述乙烯，也可由审阅指定替代。最终冻结的两个新体系中至少一个做独立完整条件参考，不能用额外不相关 toy 关闭其覆盖。坐标、分片和第二体系仍待方法审阅；分子名称不是冻结输入。每个将开放的 pilot/research profile 均须有基础参考，研究 profile 至少一份独立完整条件参考，并有至少两个新体系的普通态和路径比较覆盖。

候选预算：独立标量参考 nAO≤40、单线程、4 GiB 容器上限、每次 wall-clock≤900 s；普通/路径比较 nAO≤80、最多 2 线程、4 GiB、每次≤900 s；每 profile 最多两份新体系，单轮所有科学进程累计 wall-clock≤7200 s。数值导数检查也计入总预算。上述是待审上限，不是资源充分性实测；按实际 nAO/峰值模型降低规模或登记另轮预算，不能自动上调。

夹具登记必填：XYZ 原字节/规范化几何身份、原子映射、分片、profile 所有实际参数、参考代码身份/共享依赖、比较量/阈值、预期接受或拒绝、状态选择和预算。几何、profile、阈值未冻结或资源未校准则相应运行 BLOCKED。本轮不执行。

### 路径 II：不同成熟方法的科学解释对照

按 [方法对照表](USER_MOLECULE_METHOD_COMPARISON_zh-CN.md)选择适用的 BLW、ALMO、NBO 或 cDFT；SAPT 仅在其分片范围成立时使用。单独登记软件、版本、可用条件、基组/XC/几何、占据、删除/局域化定义、比较目的和预算。

目前仅完成公开资料对照，外部程序对照计算 NOT_EXECUTED。这条路径报告趋势、定义差异和解释限制，不设“数值必须与本项目相等”的通过门槛；数值接近不证明方法等价。其用途与路径 I 的代码验证分别出具结论。A01 的方法关系审阅是必需，外部商业程序或所有方法的实际计算不是首版统一安装要求；具体科学声明需要哪些数值对照由范围审阅登记。
