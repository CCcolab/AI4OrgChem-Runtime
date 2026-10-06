# 用户分子服务：当前实施文档入口

最新 [W01—W07 本地CI](USER_MOLECULE_CI_W01_W07_20261006_zh-CN.md) 已执行并通过工程范围：176个独立用例/284执行、10启动器、4平台、9宿主报告；0新分子计算。远端CI仍NOT_EXECUTED，科研Compute仍BLOCKED，真人反馈延期不阻塞当前工程。旧批次记录保留。

日期：2026-10-05；W05-W06-NUMERICAL-EVIDENCE-1。独立普通态、完整条件参考桥接、验收及原生资源记账已实现并实测；普通态/同 D 对照通过所列门禁，条件资格/路径等价性/完整参考失败，资源仅覆盖精确夹具流程。Compute 和正式 W07 仍 BLOCKED，研究范围待真实审阅。此前工程/准备记录保留为历史。

操作从 [用户指南](USER_MOLECULE_RUN_zh-CN.md) 开始；最新身份、范围与缺口见 [求解器 v2 实测](USER_MOLECULE_SOLVER_V2_zh-CN.md)，其 122 项工程测试通过、单例条件数值失败。此前 [数值审查](USER_MOLECULE_W05_W06_NUMERICAL_REVIEW_zh-CN.md)、[W05 准备](USER_MOLECULE_W05_PREPARATION_zh-CN.md) 与 [W01—W04 交付](USER_MOLECULE_W01_W04_DELIVERY_zh-CN.md) 为历史批次，不冒充当前状态。

2026-10-06 [W07 三步工程试用](USER_MOLECULE_W07_ENGINEERING_TRIAL_zh-CN.md) 已提供自有输入准备、Check、报告导出与反馈路径；既有乙烯夹具的工程演示保留；真人反馈按用户要求 DEFERRED_BY_USER，未来可选，不阻塞当前工程验收。四问咨询按用户指示延后，待扩展齐备后集中征询；方法状态保持未审，正式 W07/Compute 仍 BLOCKED。

最新 [W07 模拟自测](USER_MOLECULE_W07_SELFTEST_zh-CN.md) 已实际通过9个启动器、6个保护/历史失败判读和12个宿主 parser 场景；8个新容器均删除，输出保留，0新科学计算。模拟自测仅完成已列工程范围，科研 W07/Compute 门禁不变。

W07 源码与存量证据候选已补齐新服务支持/来源/备份范围；两类样例搬移及 Git 源码重建后的只读报告通过，591 个科学源码文件匹配来源锁。实际条目见 [交付登记](../validation/user-molecule/w07-delivery-20261006.json)；包不含镜像或依赖，不代表完整环境恢复或 r3 许可分发审查闭合。

2026-10-06 最新增补为 [存量方法审阅](USER_MOLECULE_METHOD_REVIEW_20261006_zh-CN.md)与 [下一版求解设计](USER_MOLECULE_SOLVER_NEXT_DESIGN_zh-CN.md)：只读定位保存初始谱的8/9占据边界、占据跳变与能量—算子判据；新增科学进程为0。方法责任审阅未签署，新策略 DESIGN_ONLY，Compute/W07仍BLOCKED。

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
| [求解器 v2 实测及前置条件](USER_MOLECULE_SOLVER_V2_zh-CN.md) | 严格真实端态停止、两个同 D 收缩路径、122 项工程 PASS 和唯一分子 FAIL；当前记录 |
| [SCF/研究范围审阅入口](USER_MOLECULE_SCF_REVIEW_REQUEST_zh-CN.md) | 依据原始失败提出具体科学审阅问题，不代签批准 |
| [存量方法审阅（2026-10-06）](USER_MOLECULE_METHOD_REVIEW_20261006_zh-CN.md) | 精确保存谱定位、100周期历史、允许变化/导数判据；0新增科学计算 |
| [下一版求解与验收前置](USER_MOLECULE_SOLVER_NEXT_DESIGN_zh-CN.md) | 具体方法决策与保留原方程的残差求解提案；DESIGN_ONLY |
| [MDR-001 方法决定记录](USER_MOLECULE_METHOD_DECISIONS_001_zh-CN.md) | 入口四问：方法责任人定义、外部一致性核查及分歧；DRAFT/PENDING，不自动批准或重审P01—P14 |
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
| [外部评审任务书](USER_MOLECULE_EXTERNAL_REVIEW_zh-CN.md) | 待审问题和科学证据要求 |
| [评审反馈模板](templates/USER_MOLECULE_REVIEW_RESPONSE_zh-CN.md) | 结构化记录审阅结论与缺口 |
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
