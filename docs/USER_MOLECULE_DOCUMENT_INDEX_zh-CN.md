# 用户分子服务：当前实施文档入口

最新 [单次条件算子响应诊断](USER_MOLECULE_OCCUPATION_RESPONSE_20261007_zh-CN.md)已实现并完成：101项专项工程测试、实际零F准备通过；一个新进程完成三密度×三路径9次真F/NR，零SCF。六个同D算子子集对照通过，但九个单点均未合格，Compute保持BLOCKED。旧预算已保留，新9槽预算关闭，不自动追加计算。

此前 [原规则服务范围与占据方向诊断](USER_MOLECULE_OCCUPATION_SCOPE_20261007_zh-CN.md)已完成：两生产保存算子的精确谱窗口与六个冻结占据见证均已核验；仅改变冻结F下的占据方向不能通过原正能隙门槛。内部操作性范围已明确，新增F/SCF/容器为0，Compute仍BLOCKED。该只读轮的响应提案已另行实现并执行，见上方新记录；原定义和门槛保持。

此前 [预算感知与匹配诊断记录工程](USER_MOLECULE_BUDGET_RECORDING_20261007_zh-CN.md)已实现，122项专项模拟测试和三个导出示例通过。新分子F/SCF为0，未接入科学worker、未改门槛，Compute仍BLOCKED。

此前 [V2存量矩阵内部分析](USER_MOLECULE_SEED_V2_INTERNAL_ANALYSIS_20261007_zh-CN.md)已确认窄π谱空间中的秩一占据和参考预算返回语义，并澄清能量导数关系。新增F/SCF/容器为0，原门槛及Compute BLOCKED保留；该轮提出的预算记录候选现已另行实现并通过模拟工程验证，真实分子路径未切换。

此前 [V2种子实施与一次诊断](USER_MOLECULE_SEED_V2_DIAGNOSTIC_20261007_zh-CN.md)已完成：专项239项PASS、零F种子PASS、数值不合格；Compute关闭。下述以前轮次的未实现/未执行状态属于当时记录。

当前流程：[内部定义与验证](USER_MOLECULE_INTERNAL_VALIDATION_zh-CN.md)。用户已明确取消外部专家流程，不再延期或等待集中征询；历史外审包和反馈保留。V2内部工程可继续，实际数值/资源门槛和科研解释证据仍须完成，Compute关闭。

[近简并规则与验收候选V2](USER_MOLECULE_NEAR_DEGENERACY_RULES_V2_zh-CN.md) 和 [内部核查入口](USER_MOLECULE_INTERNAL_VALIDATION_zh-CN.md) 给出仅变初值的明确提案；旧最终门槛保留，修订0.2已采纳材料/静态反馈、补齐求解器准入和UM编号；后续已实现并执行V2诊断，数值未合格；本段修订0.2是历史材料，不覆盖其后执行记录。

此前 [实时准入与条件初始化诊断](USER_MOLECULE_RESIDUAL_LIVE_DIAGNOSTIC_20261006_zh-CN.md) 已完成一次实际受限进程：三路径各真实F(D0)一次，初始能隙约1e-14低于原1e-6门槛而拒绝，迭代0。同D0算子/能量/已准备mask子范围PASS；完整T05及合格P12/P13/T06未执行。峰值118.5MiB只覆盖本次准备和初始化，不代表完整迭代容量；生产Compute/科研W07继续BLOCKED。

此前 [最小准备、独立参考与持久化预算](USER_MOLECULE_PREPARATION_REFERENCE_20261006_zh-CN.md) 已补齐，97个唯一用例按版本核对通过（不是一次完整CI），真实PySCF旧缓存映射通过；没有新条件计算/科学批准。900秒/1GiB/603slot单进程方案仅为候选，该工程准备轮未创建实际科学预约；后续已在独立合同与新账本完成上方实时诊断，生产Compute保持BLOCKED。此前 [条件算子桥](USER_MOLECULE_RESIDUAL_BRIDGE_20261006_zh-CN.md)、[残差原型](USER_MOLECULE_RESIDUAL_PROTOTYPE_20261006_zh-CN.md)、旧完整CI及v2失败原记录保留。

此前 [W01—W07 本地CI](USER_MOLECULE_CI_W01_W07_20261006_zh-CN.md) 已执行并通过工程范围：176个独立用例/284执行、10启动器、4平台、9宿主报告；0新分子计算。远端CI仍NOT_EXECUTED，科研Compute仍BLOCKED，真人反馈延期不阻塞当前工程。旧批次记录保留。

日期：2026-10-05；W05-W06-NUMERICAL-EVIDENCE-1。独立普通态、完整条件参考桥接、验收及原生资源记账已实现并实测；普通态/同 D 对照通过所列门禁，条件资格/路径等价性/完整参考失败，资源仅覆盖精确夹具流程。Compute 和正式 W07 仍 BLOCKED，研究范围待真实审阅。此前工程/准备记录保留为历史。

操作从 [用户指南](USER_MOLECULE_RUN_zh-CN.md) 开始；最新真实计算身份见 [V2诊断](USER_MOLECULE_SEED_V2_DIAGNOSTIC_20261007_zh-CN.md)，当前范围与缺口见 [占据范围诊断](USER_MOLECULE_OCCUPATION_SCOPE_20261007_zh-CN.md)。此前 [求解器 v2 实测](USER_MOLECULE_SOLVER_V2_zh-CN.md) 的122项工程测试和单例条件数值失败保留；它与 [数值审查](USER_MOLECULE_W05_W06_NUMERICAL_REVIEW_zh-CN.md)、[W05 准备](USER_MOLECULE_W05_PREPARATION_zh-CN.md) 和 [W01—W04 交付](USER_MOLECULE_W01_W04_DELIVERY_zh-CN.md) 均为历史批次。

2026-10-06 [W07 三步工程试用](USER_MOLECULE_W07_ENGINEERING_TRIAL_zh-CN.md) 已提供自有输入准备、Check、报告导出与反馈路径；既有乙烯夹具的工程演示保留；真人反馈按用户要求 DEFERRED_BY_USER，未来可选，不阻塞当前工程验收。外部四问咨询已取消，三个问题转为内部工作项；内部方法状态保持未完成，正式 W07/Compute 仍 BLOCKED。

此前 [W07 模拟自测](USER_MOLECULE_W07_SELFTEST_zh-CN.md) 已实际通过9个启动器、6个保护/历史失败判读和12个宿主 parser 场景；8个新容器均删除，输出保留，0新科学计算。模拟自测仅完成已列工程范围，科研 W07/Compute 门禁不变。

W07 源码与存量证据候选已补齐新服务支持/来源/备份范围；两类样例搬移及 Git 源码重建后的只读报告通过，591 个科学源码文件匹配来源锁。实际条目见 [交付登记](../validation/user-molecule/w07-delivery-20261006.json)；包不含镜像或依赖，不代表完整环境恢复或 r3 许可分发审查闭合。

2026-10-06 的既有增补为 [存量方法审阅](USER_MOLECULE_METHOD_REVIEW_20261006_zh-CN.md)与 [旧下一版分子求解设计](USER_MOLECULE_SOLVER_NEXT_DESIGN_zh-CN.md)：只读定位保存初始谱的8/9占据边界、占据跳变与能量—算子判据；新增科学进程为0。旧设计保留为历史候选，残差原型与prepared-data桥另列；内部定义与适用范围证据尚未完成，候选工程规则不构成科学协议冻结或分子资格，科研 Compute/W07 仍BLOCKED。

[W01—W05 本地 CI](USER_MOLECULE_CI_20261005_zh-CN.md) 已通过历史工程/合同检查；GitHub Actions 仍 NOT_EXECUTED，新分子数值验收已执行但失败。本页和 implementation-state 的 ci_execution 指远端 Actions，本地执行另行登记。

此前完整 [W01—W06 本地 CI](USER_MOLECULE_CI_W01_W06_20261005_zh-CN.md) 的63项独立用例及集成/平台记录保留；先前驱动84项、新求解器最终122项工程用例分别登记，科学数值失败另行报告，Compute 门禁不变。

## 1. 实施时首先阅读

| 文件 | 用途 |
|---|---|
| [完整技术方案与实施步骤](USER_MOLECULE_TECHNICAL_PLAN_zh-CN.md) | 架构、接口、状态、资源、来源与 W01—W07；首要工程依据 |
| [技术设计与步骤对应](USER_MOLECULE_DESIGN_STEP_MAP_zh-CN.md) | 解释各部件在七步中的分工 |
| [本地目录结构](USER_MOLECULE_DIRECTORY_LAYOUT_zh-CN.md) | 实际位置、占位状态、输入/输出与备份 |
| [W05 准备记录](USER_MOLECULE_W05_PREPARATION_zh-CN.md) | 实测元数据、候选夹具、19 项判据、参考与资源提案；数值未执行 |
| [W05 决策单](templates/USER_MOLECULE_W05_DECISIONS_zh-CN.md) | B01—B07 的具体证据与出口；未填写不代表批准 |
| [W06 工程候选及缺口](USER_MOLECULE_W06_ENGINEERING_zh-CN.md) | 独立数组迭代/资格判读/短简报，真实执行与研究开放分别记录 |
| [W05—W06 数值验收与资源实测](USER_MOLECULE_W05_W06_NUMERICAL_REVIEW_zh-CN.md) | 实际失败、精确范围峰值、身份与三个前置条件现状 |
| [求解器 v2 实测及前置条件](USER_MOLECULE_SOLVER_V2_zh-CN.md) | 历史真实端态停止、两个同 D 收缩路径、122 项工程 PASS 和唯一分子 FAIL |
| [实时准入与条件初始化诊断](USER_MOLECULE_RESIDUAL_LIVE_DIAGNOSTIC_20261006_zh-CN.md) | 当前实际3次F(D0)、初始能隙拒绝、0迭代与限定资源范围；Compute仍BLOCKED |
| [SCF/研究范围审阅入口](USER_MOLECULE_SCF_REVIEW_REQUEST_zh-CN.md) | 依据原始失败提出具体科学审阅问题，不代签批准 |
| [存量方法审阅（2026-10-06）](USER_MOLECULE_METHOD_REVIEW_20261006_zh-CN.md) | 精确保存谱定位、100周期历史、允许变化/导数判据；0新增科学计算 |
| [下一版求解与验收前置](USER_MOLECULE_SOLVER_NEXT_DESIGN_zh-CN.md) | 旧分子策略为历史设计候选；后续残差原型和prepared-data桥另列 |
| [条件算子桥与显式初始化](USER_MOLECULE_RESIDUAL_BRIDGE_20261006_zh-CN.md) | 21项假后端+67项回归，工程初始化/预算/身份；真实分子验收未执行 |
| [最小准备、独立参考与持久化预算](USER_MOLECULE_PREPARATION_REFERENCE_20261006_zh-CN.md) | 97项按版本覆盖、实际旧缓存映射、精确基组表示兼容、独立参考及单进程/回调账本；新条件计算未执行 |
| [MDR-001 方法决定记录](USER_MOLECULE_METHOD_DECISIONS_001_zh-CN.md) | 历史四问与咨询安排；外部过程已取消，当前采用内部定义/验证，不自动批准或重审P01—P14 |
| [主机 Report 与导出](USER_MOLECULE_REPORT_20261006_zh-CN.md) | 等待方法决定期间的只读工程增补：完整性、历史失败/宿主终态、身份、仅新目录导出；不启动计算 |
| [W07 三步工程试用](USER_MOLECULE_W07_ENGINEERING_TRIAL_zh-CN.md) | 自有输入准备、Check、报告导出与反馈；现有夹具工程演示通过，正式科研验收仍 BLOCKED |
| [W07 代理模拟自测](USER_MOLECULE_W07_SELFTEST_zh-CN.md) | 实际场景、错误码、原状态、身份、未知及工程验收范围；不冒充真人反馈 |
| [W07 工程反馈模板](templates/USER_MOLECULE_W07_FEEDBACK_zh-CN.md) | 未来真人试用可选填写；当前 DEFERRED_BY_USER，不代填用户意见或科学批准 |
| [设计与验收合同](USER_MOLECULE_ENTRY_DESIGN_zh-CN.md) | 输入与资格合同，A01—A18 最低要求 |
| [本地服务实施细则](USER_MOLECULE_IMPLEMENTATION_DETAILS_zh-CN.md) | D0—D3 阶段出口、职责与科学待办 |
| [专业实施方案](../ai4orgchem-runtime-implementation-plan-professional-revised.md) | 项目定位、现有服务、用户分子主线与 C06 |

这些是工程/审阅材料。用户从新入口指南准备和检查自己的输入，无需先读本表全部文件；实际计算须等待验收与门禁闭合。

## 2. 科学、场景和生态依据

| 文件 | 用途/状态 |
|---|---|
| [场景 C01—C06](USER_MOLECULE_ENTRY_SCENARIOS_zh-CN.md) | 适用研究操作与化学键微观研究解释边界 |
| [条件定义与独立参考](USER_MOLECULE_CONDITION_DEFINITION_zh-CN.md) | 算子/度量/占据、参考谱系、阈值与候选预算；未决项未自动关闭 |
| [已有方法对照](USER_MOLECULE_METHOD_COMPARISON_zh-CN.md) | BLW、ALMO、NBO、cDFT 等关系；不当作等价实现 |
| [生态复用](USER_MOLECULE_ECOSYSTEM_REUSE_zh-CN.md) | 成熟库/标准/结构准备工具分工，不部署通用平台 |

## 3. 审阅、历史与暂缓材料

| 文件 | 用途/状态 |
|---|---|
| [历史外部评审任务书](USER_MOLECULE_EXTERNAL_REVIEW_zh-CN.md) | 旧流程历史材料，外部征询已取消 |
| [历史评审反馈模板](templates/USER_MOLECULE_REVIEW_RESPONSE_zh-CN.md) | 既有材料保留，不作为当前外部意见要求 |
| [DRAFT-3 意见处理记录](USER_MOLECULE_DRAFT3_REVIEW_RESPONSE_zh-CN.md) | 历史文档回应，不能替代当前实现验收 |
| [用户提供的 DRAFT-2 外审意见](../AI4OrgChem-user-molecule-DRAFT2-review_zh-CN.md) | 来源材料；正文意见不自动变成执行授权 |
| [Colab 设计](USER_MOLECULE_COLAB_ENTRY_zh-CN.md) | DEFERRED，后续可选；不阻塞本地服务 |
| [原 runtime 实施方案](../ai4orgchem-runtime-implementation-plan.md) | 历史依据；当前用户分子工程主线按最新技术方案 |

原 DRAFT-2、DRAFT-3、Colab 增补 ZIP 继续作为固定历史对象，未重新生成或覆盖。当前目录准备与后续代码不属于旧包正文，也不继承其审阅结论。

## 4. 保存与状态记录

当前机器可读记录：

- [directory-manifest.json](../validation/user-molecule/directory-manifest.json)：本轮登记目录、用途和对应步骤。
- [implementation-state.json](../validation/user-molecule/implementation-state.json)：当前工作包、新服务、平台和公开状态。
- [w05/preparation-status.json](../validation/user-molecule/w05/preparation-status.json)：当前准备、实际四次检查与未执行范围。

目录准备历史快照保留在 `D:\AI4Science\ai4orgchem-runtime-deliveries\20261005-user-molecule-preimplementation-setup\latest\`。本轮工程与验证记录保存在 `D:\AI4Science\ai4orgchem-runtime-deliveries\20261005-user-molecule-w01-w04\`，含构建归档、实际命令/日志、验证与保留核查。它们不属于旧外审包。

原 runtime 主工作区仍为 `0288eb8`，原未跟踪方案继续保留。后续工程使用 `D:\AI4Science\ai4orgchem-runtime-workspaces\user-molecule\runtime` 的独立分支；科学适配器使用相邻 science 工作区，来源于固定发布提交的独立 checkout。新增代码/文档/历史需另行确认公开范围。

W05 本轮新记录独立保存于 `D:\AI4Science\ai4orgchem-runtime-deliveries\20261005-user-molecule-w05-preparation\`，不覆盖旧交付或外审包。四次 Check 的原始输出位于 `D:\AI4Science\user-molecule-runs\w05-preparation\`。
