# P03—P10 第二批来源与科学范围静态核查

日期：2026-10-08。本文是本地候选的来源与范围核查，不是全部科学计算、平台或分发验收报告。候选构建上下文为 `0ee566397844d9885d50ca2a2d5ae5b974f19425`（`0ee5663`）；本轮受限实测已经由主执行流程串行启动，实际运行身份、退出码、数值、资源和日志仍待主执行流程核验。后续文档提交不能冒充这一镜像构建提交。

## 1. 来源锁及核对结果

本批在独立 Runtime 中增加 `runtime/protocol_cases/`，原科学源码复制到 `reference/protocol_cases/source_tree/` 并保持路径。来源清单为 [protocol-cases-scientific-assets.json](../locks/protocol-cases-scientific-assets.json)，SHA-256：

`46b6307760534fc9b4677bea7b984134f29ce969a071fbd06a64d65f8cfc9660`。

静态核对了清单全部 **95 项、1,380,511 字节**：目标文件大小、SHA-256、Git blob 身份均与清单匹配；95 项也与登记的实际来源文件逐字节匹配。没有改写被复制的科学源码、协议或原始证据。

| 登记来源 | 数量 | 身份含义 |
|---|---:|---|
| 原科研工作树只读字节 `ORIGINAL_READ_ONLY_WORKTREE_BYTES` | 89 | 上下文 HEAD 为 `ffde7b5a53800010f2bc326b812b3e5b4526d56c`；每个文件另有自身字节和 blob 身份 |
| 隔离冻结科学树 `FROZEN_PUBLIC_SCIENCE_BYTES` | 5 | `cc7437901119e71ef7945a12813c021c383e7648` 中的 P09 QM 包初始化及四个科学模块 |
| 隔离冻结派生证据 `FROZEN_PUBLIC_DERIVED_EVIDENCE` | 1 | 同一冻结树的 P07 旧综合摘要，保留派生证据身份 |

95 项包括 43 个 Python 文件、24 个 YAML、25 个 JSON、1 个 JSONL 和 `LICENSE`／`NOTICE`。登记为 tracked 的有54项，untracked的有41项。此次选取的 tracked 文件的登记 HEAD blob 与捕获 blob 相同；这不表示原工作区整体干净，也不表示41个未跟踪文件属于该 HEAD。清单明确保存 `head_is_context_not_claim_all_files_at_head: true`，不得将原工作树所有载荷统一归属于一个已提交版本。

原科研仓库 `D:\AI4Science\AI4OrgChem` 保持只读，不切换、重置、清理或覆盖其修改和未跟踪文件。原 Runtime 工作区、此前提交、来源锁及历史失败账本也不由本批覆盖。源码公开范围与是否纳入新增的原科研工作树材料，仍需另行确认。

## 2. P09 为什么采用冻结科学模块

P09 使用来源锁登记的 `software/src/ai4orgchem/qm/` 冻结版本，而不是把原科研工作树最新功能全部带入。具体比较如下：

| 文件 | 冻结版本与原工作树关系 | 本批解释 |
|---|---|---|
| `p09_conditional_scf.py` | 冻结 SHA `33c7eeeb19bcdbc1d21fa30aa32694ca333b859a9cdc22caaad8ed064060d0ab`；原工作树另有 `mask_one_electron_matrix` 可选分支 | 冻结版本始终屏蔽 h；原工作树默认参数也是 True。本批遵守原 P09 的 h/S/F 与十五类 ERI 定义，不启用后来增加的 F/S-only 分支 |
| `p09_ao_classification.py` | 冻结 SHA `7cf6212e9ff4ae97e4239c1e35a0a8d72b89c68d88d49953c2a26a2b1d0f8842`；原工作树另有 f 壳层分类 | 本批固定6-31G(d)，只使用 s/p/d。不能把受测范围一致表述成全部基组或所有版本等价 |
| `p09_energy_assembly.py` | 原工作树与冻结版本逐字节相同 | 保留既有能量组装 |
| `p09_eri_mask.py` | 原工作树与冻结版本逐字节相同 | 保留既有十五类规则 |

`gl2014.py` 原工作树与冻结科学树也逐字节相同，SHA 为 `617d5dc861b380345488800f47201624dcdd5b2cb232d0952fec198ff7df23c5`。本批没有新写求解策略或更改科学规则。P09 的 `memory_controlled_eri=True` 使用既有内存控制路径；它仍须通过原数值门槛及运行资源检查，不凭“内存优化”声明数值已验收。

## 3. P07 强审核与旧综合摘要分别保留

P07 的正式同 Hamiltonian 审核和旧综合摘要用途不同：

| 材料 | 来源与 SHA-256 | 用途 |
|---|---|---|
| `data/processed/p07_same_hamiltonian_path_audit_v0.2.json` | 原科研该路径与冻结 `evidence/P01-P14/P07/same-hamiltonian-audit-result.json` 字节相同；`ca7fe9125c74b738d9cd2fb678edf61ee927a41e4b6fa9c054899ab2def19789` | 保留正式判定 `P07_CONSISTENT_WITH_INDEPENDENT_SAME_HAMILTONIAN_PATH_AUDIT` 和原独立计算审核身份 |
| `data/processed/p07_lfmo_core_integrated_mechanism_v0.1.json` | 本批映射自冻结 `evidence/P01-P14/P07/result.json`；`b0e24635c8d1e7394ffa09510b5ae8e330f2edf543a385196b35ba06eab296b4` | 旧 derived 综合上下文，明确不算本轮独立计算验证；其中P05为两个历史角度，不冒充后来七角度综合 |

原科研旧综合摘要 SHA 为 `a78551fd1de62c056b2f95962b4efe578a304fe331f74c41fe48610f3a6db304`，与冻结摘要不同。来源锁记录实际映射，不能假称两者字节相同。

当前适配器同时读取强审核和旧上下文：核对强审核的 input artifact／protocol／config哈希绑定，将重新计算的0°和17°路径账本与0.2审核逐项比较，分别输出 `formal_saved_verdict` 和旧综合上下文。原独立审核是既有科学证据；本轮读取和算术重组没有产生第二次独立量子化学结果。

## 4. 本批各项受限范围

入口及机器范围见 [protocol-cases-v1.json](../configs/protocol-cases-v1.json)。用户界面可以按目标命名，P编号保留为协议与证据索引；这些登记案例不改变首批用户自选 XYZ 的普通 RHF 接口。

| 项 | 既有账本重组 | 本批新数值范围 | 明确未执行／未实现 |
|---|---|---|---|
| P03 | 母体NBA 0/20/40/60°总能、电子能、核排斥能及下坡区间 | 已冻结0°优化几何上的一次 B3LYPG/6-311G(d,p)、grid3普通 RKS 单点 | 不重做四点约束优化，不据一个单点重新认证整条优化路径，不作LFMO分量归因 |
| P04 | 十一个有效点、三分量恒等式，保留 divinyl0°负直接项反例 | diphenyl imine0°，两次各自原生 DSI3/FUD 构造和求解；DSI3基仅用于事后密度报告 | 不重跑十一点，不重新求解在另一状态报告基上的FUD，不为 divinyl17°非方LFMO基补值 |
| P05 | 同一parent七角度 G/FUD 账本 | 同一固定parent刚性17°、RHF/6-31G(d)、原 source-defined G/FUD 单点 | 不再计算七角度扫描、不换成优化后Table5-19几何；0°在符号容差内仍为不定 |
| P06 | 冻结0/17° FUL-2/PDSI能量与独立组装 | 冻结0°源几何，RHF/STO-3G、原FUL-2/PDSI及独立J/K组装 | 不重优化，不增加另一新角度，不称经典位阻能 |
| P07 | 同一几何、同一RHF/STO-3G Hamiltonian的0/17°状态路径闭合及强审核比较 | 无新量子化学；只允许账本／预检 | 不开放live模式，不把不同P04/P05/P06协议直接相加 |
| P08 | 三种氢化参照账本与既有G/GL能量、中央键长 | 固定已保存GL端点，一次普通RKS初值＋一次原GL(2014)计算，B3LYPG/6-31G(d) | 不重优化、不作新中央键扫描；同实现初值确认不称第二程序复现 |
| P09 | 既有CBD VDE/ADE及苯ESE账本 | 原固定矩形CBD起始几何的一次普通RKS＋一次原h/S/F、十五类ERI条件计算，B3LYPG/6-31G(d) | 不重算优化G/GL/GE1，不将固定几何差冒充最终VDE/ADE/ESE |
| P10 | 既有G/GL端点及五点BLA账本 | 冻结苯路径δ=0/0.01/0.02/0.04/0.06Å的五次普通B3LYPG/6-31G(d)单点 | 不优化G/GL，不放松几何，不增加分子或基组 |

原协议数值门槛保持：P03能量恒等式`1e-9 Eh`、路径扭转`0.08°`、方向`1e-7 Eh`；P04历史发布账本闭合`1e-9 Eh`、原单点源比较`1e-8 Eh`；P05/P06密度固定点`1e-8`、电子数`1e-6`、能量组装`1e-9 Eh`；P08固定GL端点能量重现`1e-9 Eh`；P09原smoke门槛和历史能量重现`1e-8 Eh`；P10原端点恒等式与核排斥式`1e-10 Eh`、G锚点`1e-6 Eh`及方向`1e-8 Eh`。详细指标仍以被锁定配置和适配器检查为准，不能用这个摘要替代完整合同。

P09历史重现比较已加入总体检查：原smoke指标通过而历史重现不合格时，总体不能标PASS。SCF收敛、固定点残差、波函数稳定性、能量驻定性和历史数值重现是不同问题；P09按原合同报告稳定性检查，不擅自增加“必须稳定”的新科学门槛。

## 5. 独立资源与可观测调用预算

本批不是此前139个原始 native 尝试记录的续跑。新执行预算为：最多七个live案例，每案例最多一次；串行、2 CPU／2线程、4GiB容器内存、软840秒／硬900秒，每批预留墙时上限6300秒，不自动重试或恢复。账本／预检单独使用1 CPU、1GiB、软90／硬120秒；预检只构建分子、确认AO，不运行SCF。

| 项 | 普通／片段／masked SCF kernel静态上限（不含Newton） | 原UHF Newton后备最大数 | 自定义母体求解入口 |
|---|---:|---:|---|
| P03 | RKS1 | 0 | 无 |
| P04 | UHF14＋masked RHF6 | 14 | 密度投影固定点2 |
| P05 | UHF7＋masked RHF3＋普通RHF1 | 7 | 密度投影固定点2 |
| P06 | UHF4＋masked RHF2 | 4 | 密度投影固定点2 |
| P07 | 0 | 0 | 无 |
| P08 | RKS1 | 0 | GL(2014)1 |
| P09 | RKS1，另稳定性检查1 | 0 | P09条件RKS1 |
| P10 | RKS5 | 0 | 无 |

P04—P06已计入cut reference H的UHF以及片段masked RHF；自定义母体迭代另计，不能仅观察普通SCF kernel。P08 GL最多160cycles，每cycle两个数值积分调用、末端另一次，单独预算321次NR；P09条件最多100cycles加末端评估，预算101次NR。KOST保留原bounded矩阵迭代，不称Boys/PM局域化调用。

这些是静态上限和准入预算，不是已经观测到的次数。held guard记录受监控Python入口、拒绝、返回和恢复；它不声称覆盖所有C/native操作。真实峰值RSS、时长、容器环境、只读挂载、离线状态、退出码和删除容器后的输出保留，必须由实际运行记录核验。

NBA各路径静态AO范围约为318／218／81，超首批用户RHF的20原子、80AO profile。本批使用独立登记合同。P09 CBD64AO的完整四阶ERI约128MiB并走既有原位分类屏蔽；P10是普通RKS，不能把它误称同样展开条件ERI。P09/P10原`max_memory=6000MB`是软件建议值，高于4GiB cgroup；实际硬上限由容器控制，预检不保证峰值内存或收敛。P08将软件`max_memory`设为2048MB并登记这一资源适配。

## 6. 科学门禁、环境及未执行状态

原科研 `configs/project.yaml` 仍为 Gate0 in_progress，`production_labels_allowed=false`。本批用户授权是限定的本地接入与受限复算；它没有修改原Gate、冻结P01—P14结论或生产训练标签。

依赖复用见 [protocol-cases-dependencies.json](../locks/protocol-cases-dependencies.json)：Python3.12.13、PySCF2.14.0、NumPy2.5.1及已有锁定环境，不新增安装。P06历史完整驱动曾要求NumPy2.5.2精确相等；本批只调用原单点函数，历史环境记录单独保留，不将旧完整环境门槛称作已通过。

本批使用新 `runtime-p03-bounded/0.1` 至 `runtime-p10-bounded/0.1` 运行合同，同时保存原科学协议context。原科研已关闭的调度flag保留为历史源字节，不回写为新执行授权。通用的任意用户分子条件态Compute继续BLOCKED；首批普通RHF支持范围与这些封闭案例各自独立。没有在线计算、通用优化、属性预测、反应预测或机器学习训练功能被本批启用。

本文写入时，真实新运行结果仍待主执行流程核验，不以静态核查标科学PASS。WSLc继续BLOCKED／NOT_EXECUTED且暂停，WSL升级／全局配置／重启不在本轮范围。GitHub CI执行状态保持原记录，不能把本地CI叫作GitHub已执行。本轮没有推送、镜像分发、正式标签或Release。

## 7. 许可证材料与未闭合事项

实际源包保留 [上游LICENSE](../reference/protocol_cases/source_tree/LICENSE) 和 [上游NOTICE](../reference/protocol_cases/source_tree/NOTICE)，两者原字节及所有捕获源码正文均未改写。因此已有版权、署名、源注释和许可材料未因封装被剥除；这不是对全部第三方依赖或历史作者身份的重新认证。

上游NOTICE说明项目自有代码／文档及第三方许可分别适用，保留Zhong-Heng Yu著作的科学来源署名和其报告的CC BY4.0。未复制著作完整PDF、原历史程序或新下载第三方软件。已抽取表值、协议与研究输出的公开范围及来源署名，仍须与最终拟公开文件一起确认；本地来源锁不自动授予公开权限。

镜像分发继续BLOCKED。既有 [第三方材料说明](../compliance/README.md) 和 [来源闭合审查](../validation/source-materials-final-review.json) 仍保留GCC运行库确切源码／patch、NumPy/PySCF BLAS构建来源、SciPy OpenBLAS开发提交、HDF5/libaec/libsz构建来源、XCFun实际补丁应用以及通知／对应源码交付等未闭合项。该历史审查针对其登记镜像，不冒充本批候选的逐组件重新验收；复用相同依赖也不能宣称这些阻塞自动消失。

本轮没有建设通用合规平台。新增来源锁、静态核查、隔离复制与已有许可材料用于支撑当前本地候选的审阅；实际数值结论、最终候选身份以及是否公开，分别依赖后续主执行核验和用户授权。
