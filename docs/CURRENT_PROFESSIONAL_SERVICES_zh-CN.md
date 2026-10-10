# 当前专业计算与复核服务矩阵

更新：2026-10-10；审阅基线 Runtime `86e29b47`。用户按研究目的、输入和本行允许解释选择服务。当前声明统一登记在 [能力注册表 v2](../configs/runtime-capabilities-v2.json)，可运行 `python -B scripts/local-runtime-capabilities.py` 查看。各次验收属于记录中的源码、镜像和输入；新安装须登记自己的镜像并产生自己的运行证据。能力表不替代运行时准入或授权。

项目的目的，是让专业用户在明确的方法、输入和资源范围内运行计算，并核对代码、输入、结果和解释之间的联系。普通分子入口与固定案例承担不同用途：普通 RHF 接受用户 XYZ；其余案例重放登记对象和协议，不接受任意换分子。原项目的独立实现、Runtime 协议重放、共享 PySCF 库的包装对照分别报告。

## 来源与实际身份

安装科学来源为冻结提交 [`28511f3d`](https://github.com/CCcolab/AI4OrgChem/tree/28511f3d84fa65707a107cde1e8121a7b4334ecb) 的 [588 份基线锁](../locks/source-files.sha256.json)，加上 [3 份已捕获适配文件](../assets/science-install-overlay/cc743790)；合计 591 份由 [安装来源锁](../locks/source.installation.lock.json)核对。参考原项目 `02ea458` 是评审上下文，不替换冻结基线。P03—P12 的驱动和工作树来源另按各模块来源锁披露，不能全部标成冻结提交。详见 [安装来源](SCIENCE_INSTALL_SOURCE_20261009_zh-CN.md)。

能力注册表逐模块列出 input/profile/protocol/source/build/image/accepted_runs/evidence 及工程、数值、科学三个范围。`build.historical_image_build_runtime_commit` 是历史镜像构建身份；宿主启动器改动与新安装身份单独登记。公开 NPZ 或摘要的哈希也不能代替完整运行的输入、依赖、manifest、资源、调用审计及清理回执。

## 普通分子与入门示例

下表每行列出八项选择依据；字段都是实际文件中的字段，不要求各模块共享一个结果 schema。普通输入 schema 为 `molecular-single-point-v1`，固定案例配置为 `registered-fixed-cases-v1`。

| 模块与指南 | 输入 | 方法与约束 | 比较量 | 实际验收 | 结果字段／文件 | 成本边界 | 允许解释 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [自己的分子 RHF 单点](MOLECULAR_SINGLE_POINT_zh-CN.public.md) | XYZ；H/C/N/O、中性闭壳层单重态；≤20 原子，实际 AO≤80；[请求 schema](../schemas/molecular-single-point-v1.json) | `rhf-631gd-small-v1`，RHF/6-31G(d)，保留用户给定几何 | 总能量；轨道能级；AO 自旋求和密度；`Tr(DS)`；能量与矩阵闭合残差 | [四分子正式运行＋四次同版本 PySCF 对照](../validation/molecular-service/deployment-20261008.public.json)；12 项数值门禁；稳定性未执行 | `output/calculation/result.json` 的 `energy_ledger`、`orbital_summary`、`checks`、`residuals`；`orbitals-density.npz`；host/worker receipts | 1 CPU/线程、1 GiB；120 秒硬限、100 秒软停；一次 RHF kernel，最多100轮 | 教学、指定几何基线、包装一致性；SCF 收敛和门禁通过不证明波函数稳定极小值；HOMO-LUMO gap 为诊断，未作为此服务门槛 |
| [表值统计 P02](REGISTERED_CASES_zh-CN.md) | 固定公开表值；不能换用户数据后沿用资格 | 冻结表值统计、无量子计算 | 结构—光谱统计量、冻结参照残差 | [固定任务本地 Docker 记录](../validation/registered-cases/deployment-20261008.public.json) | `output/case/case-result.json`、`acceptance_checks`、数值统计与来源；host/worker/guard receipts | 1 CPU/线程、1 GiB、120 秒；零 SCF | 检查该表的统计重算；没有重新认证 PDF/CIF、精修或因果关系 |
| [图规则与账本 P13](REGISTERED_CASES_zh-CN.md) | 固定分子图与保存能量 | 原图枚举/RDKit 规则、账本算术 | 图属性、公式规则、保存能量的差值与恒等式 | [固定任务本地 Docker 记录](../validation/registered-cases/deployment-20261008.public.json) | `output/case/case-result.json` 的图/账本记录与 `acceptance_checks`；来源和执行回执 | 同固定示例资源；零新 QM | 复核登记图与账本；未对所有候选开展独立 QM 重优化 |
| [轨道与密度 P01](REGISTERED_CASES_zh-CN.md) | 固定乙烯及片段划分 | RHF/6-31G(d)，一次 Boys、一次 Pipek-Mezey 占据旋转 | 同一占据空间的 AO 密度、电子数、RHF 能量与轨道片段支撑变化 | [一个固定乙烯控制](../validation/registered-cases/deployment-20261008.public.json)；SCF/Boys/PM 各一次 | `output/case/case-result.json` 的 `representations/findings/control_qualified`、density/coefficients 哈希；`occupied-representations.npz` | 同固定示例资源；三次登记 kernel | 轨道表示可改变、同一电子态密度与能量不变；不据此赋予化学稳定化能标签 |

## 专题协议 P03—P10

入口与执行参数见 [专题指南](PROTOCOL_CASES_BATCH2_zh-CN.public.md)。配置 [protocol-cases-v1.json](../configs/protocol-cases-v1.json) 保留历史候选状态；当前实测范围以 [batch2-verification.json](../validation/protocol-cases/batch2-verification.public.json) 和能力注册表为准，不回写历史配置。所有项目可复核保存账本；preflight 仅检查登记对象，不能保证数值收敛。P07 无 live。

ledger/preflight 为 1 CPU/线程、1 GiB、120 秒；live 为2 CPU/线程、4 GiB、900秒（840秒开始停止），每项一次、串行且无自动重试，七项独立批次总预留上限6300秒。P04/P05 的原封装失败记录保留，与修复后成功运行分列；P03 通过运行使用较早镜像，不能改标为当前统一候选镜像。具体身份在注册表的 accepted_runs 中逐项列出。

| 模块 | 输入 | 方法与约束 | 比较量 | 实际验收 | 结果字段（`output/case-result.json`） | 成本边界 | 允许解释 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P03 扭转路径 | 冻结 parent-NBA 四角账本；live 固定一端点 | 登记 B3LYPG/6-311G(d,p)、grid3；live 固定几何，不新优化 | 总能量、电子能、核排斥；角间差值与闭合 | 保存四点算术＋一个固定端点 live 通过 | `records[].total_energy_hartree/electronic_energy_hartree/nuclear_repulsion_hartree`、`checks` | 上述 batch2 预算；一次 RKS | 登记采样路径的分量与方向；不证明连续 PES 极小值或孤立因果 |
| P04 双状态直接响应 | 冻结十一点账本；live 固定原协议点 | RHF/6-31G(d) 与源固定点/参考氢；保持源分区 | π–π 直接项＋轨道响应＝E(FUD)−E(DSI3) | 十一点账本及修复后单点 live 通过；旧负直接项反例保留 | ledger的 `records[].pi_pi_direct_hartree/orbital_response_hartree/endpoint_E_FUD_minus_E_DSI3_hartree/closure_residual_hartree`；live的 `records[].transition/source_local_three_bucket_view` | 上述预算；参考氢 UHF/UHF1e 分账 | 同协议端点分解；直接项单独的符号不是普适稳定化定律 |
| P05 π–σ 条件能量 | 冻结七角账本；live 固定17° | 源七角续接上下文，RHF/6-31G(d)，固定几何分组算子 | 直接项＋响应＝E(G)−E(FUD) | 七角账本及修复后单点 live 通过 | `records[].ground_energy_hartree/fud_energy_hartree/direct_total_hartree/orbital_response_hartree/endpoint_E_G_minus_E_FUD_hartree` | 上述预算；源固定点调用另计 | 登记条件功能式的操作性能差；不扩展为用户任意条件态 |
| P06 双片段能量组装 | 固定0°/17°账本；live 固定0° | RHF/STO-3G，源 PDSI/FUL 分区与占据根，独立能量算术 | E(PDSI)−E(FUL)，pipeline/独立组装残差与原印值误差 | 两点账本及单点 live 通过；历史完整runner精确NumPy版本核查未执行 | `records[].states/endpoint_E_PDSI_minus_E_FUL_hartree/energy_assembly_residual_hartree/source_absolute_error_hartree` | 上述预算；原两状态调用受审计 | 同分子同协议条件端点；跨分子定律未建立 |
| P07 同 Hamiltonian 闭合 | 固定0°/17°五态账本 | 保存 RHF/STO-3G 同 Hamiltonian、每角同几何；只读算术 | π–σ、π–π、σ子项、桥项与总端点闭合 | 账本重算通过；无新 AO/SCF/live | `points` 中 `pi_sigma_hartree/pi_pi_hartree/sigma_subterm_hartree/bridge_hartree/requested_total_hartree/four_term_residual_hartree` | ledger资源；零科学调用 | 检查路径分解与双计数；综合摘要属于 DERIVED，不是新独立计算 |
| P08 丁二烯 GL | 固定丁二烯 GL 几何/保存初值与热化学参照账本 | B3LYPG/6-31G(d)、grid3，GL2014 登记方法；固定端点 live；不新优化 | GL重算能量与保存值；ordinary@GL；氢化参照算术 | 保存账本＋固定 GL live 通过；同实现初值对照；原书PDF认证未执行 | `recomputed_GL_energy_hartree/absolute_GL_energy_error_hartree/modified_metric_electron_count/physical_metric_electron_count/GL_history` | 上述预算；一次 ordinary RKS＋一次GL固定点 | 保存端点一致性；不称第二程序独立复现，不称完整P08复算 |
| P09 环丁二烯条件态诊断 | 固定 CBD 几何；历史CBD/苯账本 | 登记普通/条件 RKS、h/S/F路径；固定几何，无优化 | 两态总能量、electron/commutator/idempotency、保存重算残差 | 固定几何 smoke与一次稳定性调用通过；各门禁以实际记录为准 | `ordinary_G_like_state/conditional_DSI_state/fixed_geometry_diagnostic_difference_hartree/historical_rerun_comparison/original_smoke_checks` | 上述预算；普通/条件各一次，stability一次 | 固定几何诊断差；不是最终优化 VDE/ADE 或苯ESE；条件固定点不证明能量驻定 |
| P10 苯电子/核排斥扫描 | 冻结五个BLA几何与保存G/GL账本 | 普通 B3LYPG/6-31G(d) 扫描，保持坐标 | 总/电子/核排斥分量、BLA差值与二次曲率 | 五点普通 RKS live通过，保存G/GL复用单独披露 | `result.ordinary_RKS_BLA_scan.points/quadratic_curvatures_hartree_per_angstrom2`、`result.acceptance_checks` 与外层 `checks` | 上述预算；五次普通RKS | 登记坐标扫描下的分量趋势；不将核排斥单独解释为实验因果 |

## 高成本 P11/P12 与 P14

| 模块与指南 | 输入 | 方法与约束 | 比较量 | 实际验收 | 结果字段／文件 | 成本边界 | 允许解释 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [P11 固定多态](PROTOCOL_CASES_BATCH3_zh-CN.public.md) | 17态：furan4、benzene3、cyanobenzene10；live一次选择一个Unit；前序须本轮合格输出 | B3LYPG/6-31g(d)、grid3；furan源h/F/S规则无ERI删除、约束参数优化；苯/取代苯源2007 F/S规则、保留物理hcore与ERI、全平面优化 | 单态总能、几何与梯度；完整集合才可讨论登记LDE/ESE/CE/IE组装 | [只有P11B-benzene-G一态](../validation/high-cost-cases/deployment-verification.public.json)过源门禁；旧host manifest失败与补充证据分列；余16态未执行 | `output/result.json` 的 `checks/unit_id/runtime_protocol_id`；`p11-state.json/density.npy/optimized.xyz`；optimizer/state字段 | live8 CPU/线程、8GiB、20GiB scratch、12小时/态；ledger/preflight1CPU、1GiB、180秒 | 当前单态的源门禁；独立AO电子数/幂等/分项闭合审计有覆盖缺口，不能冒充完整多态验收 |
| [P12 固定多态](PROTOCOL_CASES_BATCH3_zh-CN.public.md) | N12/N14/N16 共61态（8/23/30）；GL/GE需本轮G，N16 GE还需本轮GL | B3LYPG/6-311g(2df,p)，源2011算子，全平面；N12控制态不进入加权和 | 单态能量/几何；完整G/GL/GE组与对称控制通过后才组装CESE | [只有P12-N12-G一态](../validation/high-cost-cases/p12-n12-g-pilot-verification.public.json)通过；余60态和新CESE未执行 | `output/result.json` 的 `checks/unit_id` 与source/dependency/profile/image身份；source result、trajectory、optimized XYZ与worker manifest | live16CPU/线程、14GiB、20GiB scratch、12小时/态；最多80几何步；ledger/preflight同P11 | 单态资格；注册61态不是61态验收；对称控制阈值和权重不变 |
| [P14 七任务及S1—S6](PROFESSIONAL_SERVICES_zh-CN.public.md) | 固定C12H6 source-proxy、平面D3h五参数；classify须四个兼容父运行目录 | 低级STO-3G技术门禁；高级B3LYPG/6-31G(d)、grid3；PLG登记跨片段π与2011交换类屏蔽 | E(G)−E(PLG)；dΔr(GP)；直接/内存受控差异；原著与冻结参照残差分列 | [历史Docker七任务](../validation/final-delivery-status.public.json)、[固定](../validation/l3-summary.public.json)、[优化](../validation/l4-summary.public.json)、[联合分类](../validation/classification-summary.public.json)有记录 | `acceptance_checks/anchor_gate_verdict/production_gate_verdict/decision_verdict`；G/PLG state与optimizer；`parent_runs/evidence_sha256/quantitative_evidence` | 高级有效内存至少13GiB；默认8线程不等于硬CPU配额；既有54.37秒/21.20分钟是观测，不是成本承诺 | 该source-proxy、子空间与比较容差内的分类；无全笛卡尔/频率/全局最低点证明；L4有检查点但不能resume；L3/L4严格断网未验收 |

P11/P12共注册78态，两个先导态的验收不迁移到其余76态、当前宿主改动或新构建镜像。独立 AO／分项审计缺口属于覆盖待办；本表不将新增诊断提升为当前科学 gate，也不改变旧 gate。需要强化覆盖时另提测试或新协议版本。

## 条件态研究诊断与电子数／能量边界

用户分子条件态 V2 已实现并真实诊断。[V2保存样本](USER_MOLECULE_SEED_V2_DIAGNOSTIC_20261007_zh-CN.public.md)的对易残差虽小，但gap约10⁻¹⁵ Eh、映射残差约0.43仍不合格。[后续原生root诊断](USER_MOLECULE_ROOT_NATIVE_DIAGNOSTIC_20261007_zh-CN.public.md)发生139次完成NR、138次成功callback和一次截止失败，未正常返回root、未完成tails和正式闭合。另有 [154项合作停止工程回归与零native实例](USER_MOLECULE_NATIVE_SHUTDOWN_ENGINEERING_20261007_zh-CN.md)，只提供所列工程证据。历史 [零F准备](USER_MOLECULE_OCCUPIED_SPACE_ROOT_PREPARATION_20261007_zh-CN.md)保持原样，不能覆盖后来真实执行。

条件 Compute 当前仍关闭，依据是合格端点及完整参考、研究范围和资源验收尚未闭合。诊断不提供用户科研能差，不证明合格根不存在，也不自动推翻P01—P14。外部专家咨询已由用户取消，本次评审报告为技术输入，不作为外部专家批准或新增咨询gate。

同一份条件态报告须并列三种电子数及其实际定义，未知项不填零：

| 诊断量 | 定义／真实字段 | 已保存V2样本 | 解释 |
| --- | --- | ---: | --- |
| 屏蔽度量电子数 | `Tr(S̃D)`；`masked_metric_electron_count`（部分协议叫`modified_metric_electron_count`） | 约16 | 条件度量下的计数，不替代原AO电子数 |
| 原AO度量电子数 | `Tr(SD)`；`physical_metric_electron_count` | 16.4745364598 | 同一D在物理重叠S下的计数 |
| 原AO／网格积分电子数 | 按该快照的数值积分字段；`grid_electron_count`或原样本声明的对应字段 | 16.4745373392 | 准备阶段未建网格时应为NOT_EXECUTED；积分误差与度量差异分别报告 |

上述数值来自 [存量矩阵内部分析](USER_MOLECULE_SEED_V2_INTERNAL_ANALYSIS_20261007_zh-CN.md)，不推广到其他样本。原AO矩阵表示的是指定基组和坐标下的密度；它不是实验微观测量。条件能量须列出 h/F/S/ERI 屏蔽规则、能量功能式、密度/占据度量及单电子、Coulomb、exact exchange、semilocal XC、核排斥与闭合残差；不能直接叫物理键能。固定点、能量驻定性和稳定极小值分别判断。本样本尚未显示明显切向能量导数失配，不能将它写成失败唯一原因。

专业报告使用 [当前通用复核模板](templates/CURRENT_SERVICE_REVIEW_zh-CN.md)，P14四父报告继续使用 [历史S1—S6模板](templates/REVIEW_REPORT_zh-CN.public.md)。执行、数值门槛、科学比较和研究解释四层分列；缺项写UNKNOWN/unavailable/NOT_EXECUTED并链接实际依据。

## 当前交付范围
