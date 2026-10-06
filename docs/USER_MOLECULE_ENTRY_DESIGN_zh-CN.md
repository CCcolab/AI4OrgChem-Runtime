# 用户分子计算入口：独立设计与验收合同

当前流程覆盖说明（2026-10-06）：用户已明确取消外部专家咨询、回复及签署前置（CANCELLED_BY_USER）。按 [内部定义与验证](USER_MOLECULE_INTERNAL_VALIDATION_zh-CN.md) 推进；下文原设计/历史状态保留，不再作为等待外部意见的条件。既有数值/资源门槛、失败和发布边界仍有效。

设计日期：2026-10-05；评审修订版 DRAFT-3。状态：DESIGN_ONLY / NOT_IMPLEMENTED；D0=PENDING_REVIEW。本文定义新增服务，不表示现有镜像、七个任务或登记案例已经支持用户分子。编写本文未进行新科学计算、镜像构建、平台升级或公开发布。

2026-10-05 优先级调整 COLAB-ADDENDUM-2：保留 [Colab 用户入口与专项验收](USER_MOLECULE_COLAB_ENTRY_zh-CN.md)作为后续可选入口；首版以本地 Docker 和启动器完成用户分子流程，不要求专业用户会用 Notebook。Colab 的 CB0—CB3/NB01—NB12 暂缓，不是本地 D0—D3 的前置条件或验收阻塞；未来启用时仍须独立实测，不能继承 Docker 验收。DRAFT-3 与 COLAB-ADDENDUM-1 已交付原包保留不变，当前优先级修订尚未提交。

2026-10-05 应用增补 LOCAL-MOLECULE-DETAILS-1：正式纳入 C06“面向化学键微观研究的电子耦合与条件态能量分析”，配套 [本地实施细则](USER_MOLECULE_IMPLEMENTATION_DETAILS_zh-CN.md)。C06 复用 C01—C03，增加研究用途和解释审查，不新增算法、登记 task、夹具数量或科学范围。实验测量、键级/密度分析和键解离能仍须另行设计。

2026-10-05 TECHNICAL-PLAN-1：用户已批准进入工程实施，工程范围 APPROVED_FOR_IMPLEMENTATION；D0 的科学复审/方法参数未决仍逐项保留，不自动变成研究准入。首批可推进 W01 基线与 W02/D1 检查实现，完整架构/接口/监督/构建和步骤见 [技术方案](USER_MOLECULE_TECHNICAL_PLAN_zh-CN.md)。本轮方案交付未实现新服务或执行新科学任务。

配套：[用户计算场景与边界](USER_MOLECULE_ENTRY_SCENARIOS_zh-CN.md)、[外部评审任务书](USER_MOLECULE_EXTERNAL_REVIEW_zh-CN.md)、[评审意见模板](templates/USER_MOLECULE_REVIEW_RESPONSE_zh-CN.md)。本版处理外部 R1—R6 意见并补入 [条件态操作性定义与参考合同](USER_MOLECULE_CONDITION_DEFINITION_zh-CN.md)、[已有方法对照](USER_MOLECULE_METHOD_COMPARISON_zh-CN.md)、[生态复用与字段映射](USER_MOLECULE_ECOSYSTEM_REUSE_zh-CN.md)。处理状态见 [修订摘要](USER_MOLECULE_DRAFT3_REVIEW_RESPONSE_zh-CN.md)：文档修订不等于外部复审、方法准入或运行验收通过。

## 1. 服务目标与首版边界

专业用户提交自己的分子坐标和片段划分，在同一个固定几何上计算普通闭壳层 RKS 态与登记规则定义的条件态，并获得能量差、账本和数值资格。不要求先阅读原著背景、P01—P14 全部材料或手工核对版本哈希。用户必须理解与自己计算有关的条件态定义、片段划分和比较量。

首版拟开放服务为“固定几何两片段条件态能量比较”。对象为经过独立验证的适用范围内、xy 平面的中性闭壳层 C/H 分子；两个片段由用户明确指定。此范围是待验证的候选边界，不是已经成立的科学适用性声明，也不意味着范围内每个分子必然收敛。未通过方法审查与分子验收前，仅供受控开发测试，不作为研究就绪服务。

首版不提供：任意元素、离子、开壳层、多于两个片段、非平面体系、周期边界、激发态、任意泛函/基组、范围分离泛函、结构优化、频率、扫描、批量调度、自动化学分片、自动投影/旋转几何、自动科学分类、生产/训练标签或检查点恢复。普通单点计算如需作为独立通用服务，另列需求，不能借条件态入口隐含扩张。

重要区别：新增比较使用同一个用户几何 R：

`ΔE_same_geometry = E(ordinary @ R) − E(conditional @ R)`。

能量原值为 Eh，转换后为 kcal/mol。它不同于 P14 的 G@source-G − PLG@source-PLG，也不同于各自优化几何的端点。默认只称“指定条件态能量差”；没有额外科学依据，不能称为实测相互作用能、唯一共轭能或普遍芳香性判据。用户分片变化会改变所定义的问题，不应自动选择最接近预期数值的分片。

首批需求包括：指定片段的条件态能量对照、分片定义敏感性、用户提供的两个平面几何响应对照、同条件记录复现及方法实现诊断。各场景的输入、输出、禁止结论和 A01—A18 验收映射见场景文件。多分片定义或多几何研究由用户逐次提交单点请求并手工比较，首版不增加自动扫描或批量任务。

这些能力另以 C06 化学键微观研究专题组织：用户可以考察指定电子耦合条件的全分子能量响应及定义/几何依赖，不能将输出自动分配为某一根键的唯一能量。简报说明研究问题、分片、模型量和资格；条件能量解释仍受 A01 范围审阅，不使用“化学键微观测量”作为现有服务名称。

“符合 C/H、单重态和平面格式”不是方法适用性证明。现有 AO 分类是基函数奇偶性，不识别实际杂化、占据 π 体系或局域化学键；不应把任意平面含碳分子自动归为适用体系。首批方法域以明确片段问题的平面不饱和 C/H 体系为审查候选，允许范围由 A01 确认。对新用户问题，默认 method_applicability=NOT_REVIEWED；用户确认意图也不能代替方法审查。

## 2. 源码审查依据与分工

审查对象为 locks/source.lock.json 的科学提交 `28511f3d84fa65707a107cde1e8121a7b4334ecb`；runtime 基线 `0288eb8455a85c2082142dbdc62b7c018adb2e56`。下列路径相对于固定科学包根目录，本轮从独立固定归档读取，未修改原项目工作区。

| 事实 | 固定源码位置 | 对设计的影响 |
|---|---|---|
| 用 z 反射奇偶性区分 σ/π，要求 max\|z\|≤1e-8 Å | software/src/ai4orgchem/qm/p09_ao_classification.py：classify_planar_pyscf_aos | 首版明确要求 xy 平面，不静默投影非平面坐标 |
| 仅支持 s、p、球谐 d AO 标签；π AO 必须有片段归属 | 同文件：z_reflection_parity | 禁止未知 AO 和不完整/重复分片；不把 AO 映射与化学适用性混同 |
| 条件态屏蔽跨片段 π 的 h、S、F，并使用十五类 ERI 规则 | p09_conditional_scf.py；p09_energy_assembly.py；configs/qm/p09_exchange_integral_classes_v0.1.yaml | 用户要确认具体操作；不能只写“删除相互作用” |
| 闭壳层占据和 DSD=2D 资格检查；屏蔽 S 非正定直接拒绝 | p09_conditional_scf.py：run_p09_conditional_rks | 首版中性、单重态、偶数电子；数值病态必须失败，不私自正则化 |
| 只接受全局杂化，不接受范围分离 | 同文件：rsh_and_hybrid_coeff 检查 | 方法只走已登记 profile，不接自由 XC 字符串 |
| 完整四指标 ERI 张量；受控模式原位屏蔽仍为 O(nAO^4) 存储 | 同文件；p09_energy_assembly.py | 新体系必须按实际 nAO 预估，不能继承 C12H6 单次峰值保证 |
| P14 固定几何脚本写死 charge=0、spin=0 与碳 0—11 分片 | software/scripts/run_p14_benzotricyclobutadiene_source_level_fixed_geometry.py | 不把用户输入塞入原 P14 脚本；新增独立科学适配器 |

拟复用 PySCF、NumPy/SciPy 和上游条件核；新增的分子输入适配、状态账本和方法适用性属于科学扩展，应在原项目独立分支审查。runtime 负责路径、资源、容器、输出与身份。若需改变核函数、占据规则或数值判据，应单独科学变更审查；禁止 runtime 构建时暗改上游。科学扩展接受后，runtime 才另建新的来源锁和候选镜像，旧锁、旧镜像与七任务验收保留。

条件核按全体系 get_occ 填占据，没有显式逐组固定电子数或跨组 π 密度清零操作。能量、S/F 操作、允许密度与变分关系、末次 gap 的算子来源在配套操作性定义中逐项说明。当前仅定义条件固定点算法，variational_status=NOT_ESTABLISHED，稳定性分析 NOT_EXECUTED；既不宣称已证明变分成立，也不把待证明关系当作已发现算法错误。

## 3. 用户流程

首版主入口为本地 Docker 配合启动器/命令。交付可填写的请求模板及简短操作指南，用户按提示填坐标文件、两片段和允许的配置，再执行“检查/计算”；具体新入口命令在 D1 实现时冻结，现有七任务启动器不冒充已支持用户分子。用户无需学习 Notebook 或先经 Colab 准备请求。

1. 准备一个 XYZ 文件（明确 Å、固定几何）和一份计算请求 JSON。
2. 指定电荷/自旋、两个片段的碳原子编号、计算配置及资源上限。
3. 执行“检查”：展示分子组成、电子数、平面偏差、分片摘要、预计资源、方法条件和支持/拒绝原因；检查不执行 SCF，也不分配完整 ERI。
4. 确认这就是要比较的条件态，执行“计算”；只有检查合格且资源足够才开始。
5. 查看简短结果：两态能量、能量差、收敛、资格和警告；需要时展开账本、数值诊断与日志。
6. 使用原始结果/简短报告开展研究；溯源信息自动记录，技术合同按需展开。

Colab 后续可把同一流程组织为交互 Notebook，调用共同适配器，不复制科学算法。当前先完成本地 D1 检查、D2 技术计算与 D3 研究候选验收；这些阶段均不依赖 Colab。未来恢复 Colab 开发时，其检查须基于 D1，技术计算须 D2 及独立 Colab 实测；研究功能仍须 D3。

输入检查合格不等于化学方法适用于该问题。服务卡必须提供一段条件态定义和范围，用户确认其分片意图；不能要求阅读全部上游文档，也不能省略有意义的科学选择。

拟新增检查动作与计算动作分别登记（具体命令语法待实现冻结）：检查可解释输入和合同，但不输出分子数值结果；计算必须引用该输入快照、profile 及规则的同一合同哈希。提供简短条件态确认，不要求背景文档签读。首版展示两片段原子编号清单及坐标预览方式，不自动判定用户想研究的化学作用。

检查回执逐原子给出 1-based 编号、元素、Å 坐标和碳 A/B 归属，绑定快照/profile/规则/范围记录哈希。compute 只使用其冻结输入。格式合法的不同分片是另一模型请求，不能自动判断它违背用户意图；回执用于确认，成对夹具用于验证映射语义。先展示原子表，图形工具可选，不要求新建通用分子编辑器。

## 4. 输入合同（拟定 v1）

只接收一个标准 XYZ 文件与严格 JSON 对象，不接收 Python、任意 shell、可执行配置或 JSON 内嵌外部下载指令。首版不接 SMILES/SDF，避免把结构生成、质子化与构象选择隐含进固定几何服务。

以下为请求结构示例，不是可直接运行的已实现命令；编号仅示意四碳体系的用户选择，不是对该分片的科学推荐。

```json
{
  "schema_version": 1,
  "service": "user-molecule-fixed",
  "geometry_file": "molecule.xyz",
  "coordinate_unit": "angstrom",
  "charge": 0,
  "multiplicity": 1,
  "research_question": "比较给定两片段的指定条件态能量差",
  "condition_definition_acknowledged": true,
  "fragments": [
    {"id": "A", "carbon_atom_indices_1based": [1, 2]},
    {"id": "B", "carbon_atom_indices_1based": [3, 4]}
  ],
  "condition_profile": "cross-fragment-pi-2011-v1",
  "calculation_profile": "research-b3lypg-631gd-grid3-v1",
  "resources": {
    "threads": 4,
    "memory_limit_mib": 4096,
    "wall_time_limit_seconds": 600
  }
}
```

示例预算不是实测充分资源；示例 research profile 也尚未获准启用。schema/profile ID 均是拟定标识。实现应给出 schema 文件与小型教学坐标样例，并区分教学样例、内部夹具和经过科学验证的对象。

### 4.1 校验规则

- JSON UTF-8、无重复键、无 NaN/Infinity，拒绝未知字段、错误类型与过大文件；不得静默忽略参数或恢复默认值。原请求原字节与解析后的规范化请求分别留存哈希。
- research_question 为有长度上限的文本备注，不参与计算选参；condition_definition_acknowledged 为布尔值，必须 true 才进入计算。该确认只表明用户理解同几何 h/S/F 与 ERI 删除定义，不是方法适用性审核通过。
- XYZ 原子数与记录数相符，仅 C/H；有限坐标、明确 Å；拒绝截断、多结构文件、错误单位、重叠/零距离。近碰撞拒绝阈值及规模上限需预先登记后验收，不能用未经验证的数值“修复”坐标。
- 原子编号以 XYZ 第一条原子为 1。每个碳恰好属于 A 或 B，各片段非空；重复、缺失、越界或氢编号拒绝。首版氢仅有 s AO，按 σ 处理，不强制加入 π 片段。不得自动重排原子或推断化学键归属。
- charge=0、multiplicity=1、正偶数电子、PySCF spin=0；其他输入返回 UNSUPPORTED，不默默改成受支持值。
- 直接输入 xy 平面，max\|z\|≤1e-8 Å，与既有分类器一致。即使任意取向的分子几何上共面，首版也应解释如何由用户显式定向后另交新文件，不自动旋转或投影。
- 创建低成本 Mole 对象检查 AO 标签和 nAO；球谐、无 ECP；禁止 f/g 或无法识别的标签。实际 AO 映射显示可查看，但不让用户逐 AO 手工填写。
- `geometry_file` 必须在请求输入目录内，拒绝绝对路径、.. 逃逸、符号链接/重解析点逃逸和共享盘 URI；锁定读到的副本，防止检查与计算之间输入改变。

### 4.2 配置与研究资格

| 拟定 profile | 条件 | 预期用途/启用门槛 |
|---|---|---|
| pilot-b3lypg-sto3g-grid2-v1 | B3LYPG / STO-3G / grid 2，锁定 SCF 与条件态选项 | 低成本输入与实现验证；必须标 TECHNICAL_ONLY，不自动升级为研究结果 |
| research-b3lypg-631gd-grid3-v1 | B3LYPG / 6-31G(d) / grid 3，锁定选项 | 新体系、条件定义及数值资格独立验收后方可启用；当前 NOT_IMPLEMENTED / NOT_VALIDATED |

profile 不接受用户自由修改泛函、基组、网格、门禁、占据或 ERI 类。需要其他条件应申请新 profile 并独立验证。技术 pilot 的通过不能替代 research profile 的验收。

候选 profile 还须显式映射：锁定 PySCF 2.14.0，unit=Å、charge=0、spin=0、cart=false、无 ECP/密度拟合/溶剂/额外色散与未登记 NLC；实际 XC 解析身份/混合系数、基组展开和网格剪枝等留存。条件核候选 maximum_cycles=100、density_tolerance=2e-8、energy_tolerance=1e-9、diis_start_cycle=2、diis_space=8、damping_cycles=2、damping=0.20；memory_controlled_eri 对两个受测模式分别记录。普通态 initial_guess、conv_tol_grad、DIIS/阻尼、max_memory、网格/积分默认与有效值仍需逐项从固定版本核查、冻结，不能仅记软件默认。

### 4.3 方法范围准入记录

范围登记由项目指定的科学方法维护者维护，并留下可识别的领域审阅责任与依据；尚未指定或完成审阅时不生成批准记录。至少包含 scope_id/version/content_sha256、状态、体系家族与研究问题、允许元素/电荷/自旋/几何、π AO/占据与分片限制、profile/规则身份、允许与禁止解释、依据、维护者及审阅责任记录、可机械检查与需人工判断的条件。

请求记录匹配的 scope_id/version/hash 及逐项 matching_reasons。格式有效性独立判断；不能识别的杂化、实际 π 性质或化学意图不伪造自动识别。可重复的范围规则不必人工批准每个输入，但没有可匹配依据保持 NOT_REVIEWED。范围内容变化产生新版本/哈希，不追溯修改旧请求；撤回/禁止项明确记录而不删除历史。

范围批准还须明确条件固定点解释与占据限制。NOT_REVIEWED 只可在另行允许的探索计算中输出 EXPERIMENTAL_METHOD；OUT_OF_SCOPE 拒绝。D1 可生成检查回执，不表示 D2/D3 已就绪或本轮授权新计算。

## 5. 结果合同与专业界面

主要结果只显示用户关心的量：体系/几何、两片段、方法、普通能量、条件能量、same-geometry 能量差、两态收敛及资格、范围与警告。不默认展示原著比较或一致/不一致分类。

输出目录拟包含：

```text
<output-root>/<unique-run-id>/
  input/request.original.json     # 实际请求，原字节
  input/request.normalized.json   # 规范化合同，原子编号转换另记
  input/molecule.xyz              # 实际读到的只读快照
  preflight.json                 # 输入/适用范围/资源结论
  result.json                    # 两态与比较量，严格 JSON
  report.md                      # 简明研究报告
  run-manifest.json               # 身份、命令、输入/输出哈希、退出状态
  stdout.log / stderr.log
```

检查阶段失败也保留 preflight/manifest/错误日志，不伪造 result。部分计算完成时保留各态独立状态；同几何一态失败，delta_energy 写 null、comparison_available=false，不能拿旧结果补齐。

结果字段应包括 `schema_version/service_id/profile_id/geometry_sha256/fragment_definition`，两态独立 `execution_status/converged/energy_total_hartree/electron_counts/numerical_qualification`，条件态能量分量、屏蔽残差、对易子、幂等性、S 特征值与条件数、ERI 模式/删除计数、占据与 gap_operator_source；比较包含公式、Eh 与 kcal/mol、转换常数及其来源。只有两态必须门禁全部通过才标 `comparison_qualification=NUMERICALLY_QUALIFIED`；有限但失败的原始能量只留作诊断，delta_energy=null。数值合格与 QUALIFIED_WITHIN_SCOPE 研究资格分别记录。

普通态能量分项若要新增输出，应使用受测 PySCF 接口并独立验证；首版允许只报告普通态总电子能、核排斥和总能量，缺少分项写 unavailable，不通过总量倒算出不存在的分量。两态共用同一实际几何、profile 和来源。

manifest 自动记录科学适配器与 runtime 的完整提交、依赖锁/版本、profile/schema/规则文件哈希、image ID 与 registry digest 分别记录、实际输入/原子映射、线程、有效内存、资源上限/峰值、网络条件、命令、退出码和输出哈希；未知写 UNKNOWN。禁止写完整环境变量或自动上传。没有研究结果的真实溯源记录，不允许人为生成“可复现”标签。

状态分层：`input_status`（ACCEPTED/INVALID/UNSUPPORTED）、`execution_status`（NOT_STARTED/RUNNING/COMPLETED/FAILED/CANCELLED/TIMED_OUT/BLOCKED）、`numerical_qualification`（PASS/FAIL/NOT_EXECUTED）、`comparison_qualification`（NUMERICALLY_QUALIFIED/NOT_AVAILABLE）、`comparison_available`、`method_applicability`（NOT_REVIEWED/APPROVED_WITHIN_SCOPE/OUT_OF_SCOPE）、`research_eligibility`（TECHNICAL_ONLY/EXPERIMENTAL_METHOD/QUALIFIED_WITHIN_SCOPE/NOT_QUALIFIED）。每态执行/数值状态独立，汇总不掩盖部分完成。进程退出 0 不单独代表研究资格。

| 情形 | comparison_available / comparison_qualification | delta_energy | research_eligibility |
|---|---|---|---|
| 输入无效/不支持、OUT_OF_SCOPE、资源 BLOCKED | false / NOT_AVAILABLE | null；检查阶段可无 result | NOT_QUALIFIED |
| 任一态失败、超时、取消、必须量非有限或门禁 FAIL | false / NOT_AVAILABLE | null，保留已完成态诊断 | NOT_QUALIFIED |
| 两态必须门禁 PASS，pilot | true / NUMERICALLY_QUALIFIED | 同几何差值 | TECHNICAL_ONLY |
| 两态必须门禁 PASS，research，NOT_REVIEWED | true / NUMERICALLY_QUALIFIED | 同几何差值 | EXPERIMENTAL_METHOD |
| 两态必须门禁 PASS，research，匹配实际批准范围 | true / NUMERICALLY_QUALIFIED | 同几何差值 | QUALIFIED_WITHIN_SCOPE |

进程正常结束但门禁失败可为 COMPLETED；研究资格仍 NOT_QUALIFIED。pilot 标签不覆盖真实失败。未运行门禁记 NOT_EXECUTED，未知终止原因另记 UNKNOWN，不冒充 SCF 不收敛。输入失败指出字段/原子；资源不足列需求/预算；数值失败列门禁/日志；未审方法列缺失范围依据。不得自动加内存、放宽容差、换分片/方法。

research profile 的数值门禁全部通过但具体问题的方法适用性未审查时，只能标 EXPERIMENTAL_METHOD，不能用 PASS 自动生成 QUALIFIED_WITHIN_SCOPE。后者必须关联方法审阅的范围 ID、版本、依据与责任记录；服务整体通过有限夹具也不能认证所有新分子的科学解释。候选阶段允许此类明确标注的探索性计算；不符合首版格式或已知不适用对象仍直接拒绝。

## 6. 数值合同与资源安全

条件态核与十五类规则保持上游原义，包括 h/S/F 屏蔽；不得为用户体系更易收敛删改某一部分。初始密度取同几何普通 RKS 收敛密度，普通态不合格则不运行条件态。两态均记录实际电子数和 SCF 终止情况。

首批 profile 的候选资格参考已有登记门禁：普通 SCF 能量容差 1e-9 Eh、最多 100 cycles；条件 density_tolerance=2e-8、显式 energy_tolerance=1e-9 Eh、最多 100 cycles；电子数误差 1e-7、能量闭合 1e-9 Eh、对易子 Frobenius 1e-5、闭壳层幂等性相对残差 1e-7、跨 π 屏蔽最大值 1e-12。原条件核 energy_tolerance 默认为 1e-10，不与候选值混用。每项公式、单位、范数/归一化、S/S̃ 度量、必需/诊断、算子来源和阈值版本见配套操作性定义；候选尚未完成推广验收，不按单次结果放宽。

必须检查屏蔽 S 的正定性；病态条件数的拒绝阈值需依据试验先行冻结。不同度量电子数分别输出，不把网格积分电子数误用为占据电子数。资格不通过时不能输出科学 classification，也不自动调用其他方法兜底。

原核在 history 首轮能量变化使用 Infinity，未定义 occupied/virtual gap 时可能返回 NaN；外部结果必须是严格 JSON。适配器对“尚未定义”的诊断量输出 null 并给出 reason，对总能量、资格残差等必须有限的量判失败。原始技术日志可以保留原表示，禁止把 Infinity/NaN 改成零或合格数值。此为序列化适配，不改变 SCF 方程。

资源预检以实际 nAO 为依据。float64 完整 ERI 单张量下界为 `8*nAO^4` 字节，但这不是完整峰值：还需积分缓冲、格点、收缩中间量、密度/矩阵、Python/库开销与安全余量。低成本检查不构造完整 ERI；以实测规模模型估算保守上界，模型/余量/最大 nAO 冻结前禁止开启未限制规模的入口。不能用 PySCF max_memory 当作整个进程硬内存上限。

reference-copy 模型分别计入原/副本 float64 张量、布尔掩码和掩码处理临时量；single-tensor 模型单独登记，仍含积分/XC/收缩开销。峰值函数绑定 ERI 模式、profile/网格和依赖版本，禁止换模式或 XC 后沿用未经核查的校准包络。

按宿主 MemAvailable 与 cgroup 剩余额度中可用最小值检查，未知或不足拒绝；另设容器硬内存/CPU 上限和任务超时。具体 Docker 标志需先核对引擎能力；线程上限不等于 CPU quota。计算遵守同宿主共享锁，锁只保护本 runtime 管理的任务，不承诺阻止其他应用。新服务资源模型独立登记；旧 P14 的 13000 MiB/13 GiB 门禁不修改。

用户输入只读挂载、软件源码只读、非 root、计算断网；输出独立持久挂载。每次新目录，拒绝覆盖旧目录。超时/取消仅停止自己启动的容器/进程组，保留已写输出并标失败阶段，不终止原科研进程。首版没有检查点恢复；未来若加检查点，也不能自动声称支持恢复。

effective available memory、用户硬限额与资源模型分别记录：必须同时满足可用额度和请求限额，预检只反映当时快照，不能保证竞争进程不会抢占。检查动作也有时长/文件大小/原子数硬限制；若 nAO 估算所需配置未冻结，拒绝计算，不假装资源已合格。

检查先限制字节/原子数，再在受限子进程内创建 Mole/估算 nAO；不把未知成本工作放入无限制宿主解析路径。CPU quota、memory/swap 策略、wall-clock 起点、有效余量及 bytes/MiB 单位写入回执，检查与计算分别限时。

宿主启动器或不受计算进程同一限额杀死的监督端在启动前创建 run ID/初始 manifest，并持久记录实际容器 ID。计算进程/容器 OOM、超时或取消后，监督端记录 exit code、引擎 OOM 标志、终止原因、各阶段状态、已写文件哈希与未完成项；原因无法取得写 UNKNOWN。不能要求被杀死的进程自己完成最终 manifest，也不凭退出码猜测 OOM。取消只针对保存的容器 ID/自己进程组。

### 6.1 待冻结参数登记

| 参数/判据 | 当前依据/状态 | 冻结门槛 |
|---|---|---|
| xy 平面误差 1e-8 Å；两 profile 方法/基组/grid | 复用固定实现/协议，拟定而未验证推广 | D0 确认；D2/D3 分别数值验收 |
| 最大请求字节、原子数/nAO、文本长度；检查超时 | TBD，不能空白进入可用入口 | D1 前固定并通过边界拒绝测试 |
| 近碰撞距离、屏蔽 S 条件数上限 | TBD；S 最小特征值必须 >0 已来自核 | 审阅依据先登记，D2 前冻结并测试；不以结果不收敛临时放宽 |
| 普通态独立参考、单片段控制、重排的比较阈值 | TBD；A07 两路径能量/密度阈值已有候选值 | 首次数值验收前固定；未达标调查原因 |
| 能量转换常数 | 拟沿用固定 smoke 脚本 HARTREE_TO_KCAL_PER_MOL=627.5094740631；精确值及来源须进入 profile/result | D0 确认，D2 验证符号和转换一致 |
| profile 全部 SCF/DIIS/damping/积分内存选项 | 需完整映射，不仅记录几项容差；上游函数默认与调用参数可能不同 | D0 保存候选完整配置；D2/D3 固定版本及哈希 |
| ERI 内存模型、额外峰值/余量、最大受测 nAO、用户限额与超时范围 | TBD，按实测包络登记；不能只用 8*nAO^4 | D1 可拒绝所有未定资源计算；D3 前全部冻结并验证 |
| 简并/小 gap 判据、占据诊断和能量—算子解释 | 全局 get_occ、末次对角化 gap、variational_status 未建立；不是已发现错误 | D0 审阅操作性合同；D2 登记诊断策略，D3 批准有限解释范围 |
| 最小独立条件参考、两个新体系、每 profile 的预算/阈值 | 候选谱系与规模/时间上限见参考合同；坐标及第二体系 TBD | D0 审阅策略/预算；D2 基础参考；D3 每研究 profile 的完整参考必需 |
| 方法范围记录与可检查匹配 | 合同已定义，实际范围和责任未批准 | D0 审阅合同；D3 批准记录/匹配证据，不人工伪填 |

TBD 不是实现者自由裁量的生产默认。D0 可在有明确冻结步骤的资源校准计划下批准受控原型开发，但不能宣称所有数值合同已闭合或启动未授权计算。

## 7. 独立验收矩阵

下表全部是待执行验收，不是已有 PASS。发布门槛分为输入/工程通过与研究能力通过，不能以低成本技术测试替代真实数值验收。

| ID | 测试及证据 | 必须满足的验收条件 |
|---|---|---|
| A01 科学适用性 | 操作性定义、BLW/ALMO/NBO/cDFT 对照与 SAPT 边界、实际方法范围记录 | 解释允许变化、全局占据与能量—算子关系；范围 ID/版本/责任/匹配依据可查；未建立变分性不宣称极小值，方法对照不等于等价 |
| A02 输入正常路径 | 小型两片段教学样例及规范化快照 | 电荷/自旋、单位、1-based 编号、实际 AO 片段映射可复查；检查不运行 SCF/完整 ERI |
| A03 输入拒绝 | 截断 XYZ、重复 JSON 键、NaN、错误单位、越界/重复/缺失分片、非 C/H、开壳层、非平面、未知 profile、超规模 | 每项在重计算前明确拒绝；保留错误与输入身份；不修正、不默认降级、不污染旧输出 |
| A04 路径与身份 | 中文/空格、..、绝对路径、符号链接/重解析点、检查后替换输入 | 正常路径工作；逃逸与变化拒绝；实际计算快照哈希匹配检查合同 |
| A05 普通态对照 | 不同形状的至少两个小 C/H 体系；独立最小 PySCF RKS 驱动、相同几何/profile | 收敛、电子数和能量符合预先冻结比较阈值；参考代码不复用被测 wrapper；比较结果与账本留存 |
| A06 条件态算子 | 独立标量规则、十五类/八重对称、同一 D 的独立 J/K/能量/S/F；允许变化关系核查 | 不调用被测掩码/收缩/能量核，逐分量对照；关系证明或明确批准的固定点解释留存；toy 不替代完整条件参考 |
| A07 条件态实现等价性 | 至少两个小新体系的两存储路径，加每研究 profile 至少一个最小独立完整条件 SCF | 路径比较候选能量≤1e-10 Eh、密度 Frobenius≤1e-9、删除计数相同；独立参考阈值另冻结，先矩阵/分量后固定点，记录共享 PySCF/状态选择；无独立覆盖不开研究 profile |
| A08 控制与不变量 | 内部单片段控制；A/B 重命名；成对重排+同步映射；非法及合法不同分片 | 零删除/重命名/同步映射按冻结标准；非法映射拒绝；合法不同分片获得不同模型身份；错误意图仅在受控夹具可判断，不承诺任意输入自动识别 |
| A09 数值资格/失败 | 按公式/度量/必需性检查 S、占据、简并/gap、两态收敛、电子数/闭合等 | 记录阈值版本、S/S̃、gap 算子来源与未执行稳定性；真实失败不输出 NUMERICALLY_QUALIFIED 差值；未定义诊断 null+reason |
| A10 分量及比较量 | 核对同几何两态、转换常数、手工账本及报告 | 符号 Eordinary−Econditional 与公式一致；分量闭合；正/负值忠实报告，不配普遍物理标签 |
| A11 资源模型 | 按实际 nAO、两 ERI 模式/profile 的多规模测试；受限检查子进程 | 冻结字节/原子/nAO/检查时长、模式峰值/余量和最大受测规模；未校准计算 BLOCKED；范围内模型覆盖峰值，检查不分配完整 ERI |
| A12 隔离与持久性 | 实际非 root、只读输入/源码、--network none、容器删除后核对输出 | 各项真实验证；不能仅用 Dockerfile 静态值或旧 P14 记录代替新入口验收 |
| A13 取消与限额 | 小预算真实超时、取消、内存拒绝/容器限额触发；监督端落盘 | 只停止保存的容器/进程组；不压满宿主/WSL VM；计算被杀后监督端仍保留身份/分态/文件/退出/OOM 标志，未知原因写 UNKNOWN；不宣称 resume |
| A14 易用性 | 专业用户用教学输入独立完成一次检查→计算→读结果 | 不读背景全集或手工对 hash 即能操作；能正确说出两片段、同几何比较和资格；错误信息可定位问题 |
| A15 回归与溯源 | 保留七任务 task ID；旧源码/锁不变；新结果哈希、image 身份与新提交映射 | 旧候选不被冒充新能力；已有运行只读核对，无需重跑旧 L3/L4；受影响低成本自动测试实际执行后报告结果 |
| A16 交付声明 | docs、README、schema、profile、候选支持矩阵、样例结果及日志 | 设计/实现/验证/平台分别记录，未知不补写；源码公开与镜像分发单独授权，WSLc 与 CI 状态不借机改 PASS |
| A17 严格 JSON 与状态机 | 真值表、分态状态、Infinity/NaN/必需非有限、范围记录与失败监督；选用标准适配的状态往返 | 比较资格与研究资格分别准确；部分失败 null 差值；pilot 不覆盖失败，NOT_REVIEWED 不获研究资格；未定义 null+reason；OOM/UNKNOWN 不丢失 |
| A18 场景可解释性 | C01—C05 及复用它们的 C06 研究专题、跨请求条件清单、失败动作与真实专业用户 | 明确分片/几何/复现的身份条件；哈希不自动证明原子对应；代码验证与方法解释分开；C06 模型量不冒充单键能或实验测量；不读背景全集能判读，未审模型不外推 |

### 7.1 新体系与数值参考的选择

拟从手工准备并审查的平面乙烯控制、平面 s-trans 丁二烯、第二个独立平面 C/H 双片段小体系开始；它们是试验候选，不是已验证支持对象，也不保证分片模型对每个研究问题适用。第二新体系及具体分片由方法审阅确认；必要时选择小型三双键链，但不以分子名称代替几何/分片身份。

每份夹具冻结坐标、charge/spin、分片、profile、预期接受/拒绝、独立参考方式和数值容差，再运行验证。参考不得用被测程序刚产生的结果直接作为唯一 expected；普通态用独立 PySCF 驱动，条件算子用独立标量与 toy checks，真实分子两实现比较。冻结数值必须在通过资格后产生，保留生成证据。P14 是既有回归锚点，不是新功能独立验证的替代。

两条 ERI 路径共享 SCF 核、XC 和部分规则，吻合只证明路径一致性。最小独立条件态参考正式纳入 A06/A07 和 D3 门槛，不再作为可选待讨论事项；基础参考用于 D2，每个拟开放研究 profile 至少一份完整独立条件 SCF。独立 J/K、账本、掩码/S/F、占据及迭代不得调用被测辅助。共享 PySCF 积分/XC 的边界、夹具与预算候选见参考合同。

同数学定义独立实现用于代码验证；不同 BLW/ALMO/NBO/cDFT 等用于方法解释。两条路径单独登记和报告，不能用外部能量接近代替方程等价，也不要求统一安装所有外部程序。方法比较审阅必需；具体外部计算由范围声明决定并单独登记预算。

能量差在不同分片之间变化不是失败本身；报告必须把分片作为模型条件。验收不预设所有 ΔE 为正或与原著一致。模型适用性无法确认时，该案例保留为技术试验，而非面向研究的支持对象。

### 7.2 阶段出口

- D0 设计就绪：R1—R6、方法/生态对照、范围记录、状态真值表、候选完整 profile、参考策略/预算及映射语义完成审阅；当前 PENDING_REVIEW，不能作者自签关闭。
- D1 检查入口就绪：schema/错误码/快照与字节/原子/nAO/检查限时冻结；A02—A04 与 A11 检查部分实际通过；未定计算资源 BLOCKED，不要求先完成研究计算。
- D2 pilot 可试用：pilot 参数/阈值、普通态与条件算子基础独立参考、数值/失败/监督/隔离及 A17 实际通过；仅 TECHNICAL_ONLY，失败仍 NOT_QUALIFIED。
- D3 研究候选可用：实际范围与占据/能量解释审阅、研究 profile、两个新体系、每 profile 的最小独立完整条件参考、已校准规模和 A01—A18 按适用项实际通过；独立参考不能以 N/A 省略。范围未审请求只按另行允许的探索资格。
- D4 后续公开：另行审阅完整历史、披露、许可证和分发义务并获得授权；本项目现有镜像分发阻塞不因 D3 自动解除。

## 8. 实施顺序与当前未决项

本轮优先级为本地专业用户流程；Colab/Notebook 暂缓，作为后续增强。A01—A18 按本地首版声明验收，NB01—NB12 不纳入本地阶段出口；没有 Notebook 不构成本地服务缺陷。共同适配器、方法范围、独立参考和本地工程验收仍是必须项，不能随入口暂缓而省略。

具体文件职责、步骤和证据按 [本地实施细则](USER_MOLECULE_IMPLEMENTATION_DETAILS_zh-CN.md)落实；C06 是应用层增补，其实现/资格按同一 D0—D3 出口管理，不因研究名称增加默认计算或提前关闭 D0。

1. 先审设计和方法适用范围，冻结首批体系、条件 profile、错误语义与资源预算。
2. 原项目科学扩展独立分支实现输入适配/普通态与条件态账本，尽量复用未修改核；runtime 独立实现检查/执行封装。现有七任务不变，新 service ID 与版本单独登记。
3. 先做纯解析/路径/拒绝和 toy tests，再实施小体系 pilot 数值验收；运行授权需明确覆盖新体系及预算。本次设计请求不启动这些计算。
4. pilot 合格后验证研究 profile、实际容器隔离/限额/取消与专业用户操作；失败调查原因，不更改科学规则换取 PASS。
5. 来源锁与候选镜像按新科学提交独立建立，在新候选上执行必要验收，不覆盖旧镜像，不重复旧高成本计算。
6. 生成简明用户指南和真实样例，报告实际支持范围、失败和未知；再分别评估公开源码与镜像分发。

研究入口开放前必须闭合：两片段方法范围与能量—算子/占据解释、第二新体系/分片、schema/profile 实现、每研究 profile 的最小独立条件参考、病态/近碰撞/规模阈值、分模式资源/监督与参考证据。实现各阶段验收矩阵分别列“合同冻结/实现完成/实际通过/未执行”，N/A 须有范围理由；不能沿用 P14 PASS 消除。

结构优化属于后续独立增强，不是首版欠账；自动非平面处理、异元素/离子/开壳层、多片段、用户自由方法和批量服务同样另行设计。现有 L4 checkpoint 无 resume 的限制持续保留。

## 9. 与现有交付的关系

`2460eef` 保留为此前源码候选，`0288eb8` 保留为专业复核文档增补候选。既有本地 Docker 七任务验证、WSL2 限定范围、WSLc BLOCKED / NOT_EXECUTED、CI 运行 NOT_EXECUTED、镜像分发 BLOCKED 均不变。S1—S6 作为高级审查依据保留，新的主入口以用户研究问题、输入与结果组织，不要求用户完成文档核对流程。

本设计文件尚未实现、未纳入上述候选提交或已确认公开范围。本轮不创建科学实现提交，不启动 WSL 升级/WSLc 验收、CI 或公开推送。
