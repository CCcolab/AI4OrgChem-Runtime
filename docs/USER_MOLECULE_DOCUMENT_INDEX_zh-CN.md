# 用户分子服务：当前实施文档入口

日期：2026-10-05；W05-PREPARATION-1。本页指向隔离分支的实际实现与方案。W01—W04 工程候选保留；W05 已完成两份候选输入、两 profile 的四次 Check、research 守卫 inspect、判据与预算登记，但参考实现与数值验收未执行。Compute 仍 BLOCKED；未继承旧七任务或研究资格。

操作从 [用户指南](USER_MOLECULE_RUN_zh-CN.md) 开始；当前实际身份、范围与缺口见 [W05 准备](USER_MOLECULE_W05_PREPARATION_zh-CN.md)，此前构建和监督见历史 [W01—W04 交付](USER_MOLECULE_W01_W04_DELIVERY_zh-CN.md)。LOCAL-SETUP-1、TECHNICAL-PLAN-1 和旧交付的描述为编写时状态。工程/准备交付不代表独立科学审阅通过。

[W01—W05 本地 CI](USER_MOLECULE_CI_20261005_zh-CN.md) 已通过受测工程/合同检查；GitHub Actions 与 W05 数值验收仍 NOT_EXECUTED。本页和 implementation-state 的 ci_execution 指远端 Actions，本地执行另行登记。

## 1. 实施时首先阅读

| 文件 | 用途 |
|---|---|
| [完整技术方案与实施步骤](USER_MOLECULE_TECHNICAL_PLAN_zh-CN.md) | 架构、接口、状态、资源、来源与 W01—W07；首要工程依据 |
| [技术设计与步骤对应](USER_MOLECULE_DESIGN_STEP_MAP_zh-CN.md) | 解释各部件在七步中的分工 |
| [本地目录结构](USER_MOLECULE_DIRECTORY_LAYOUT_zh-CN.md) | 实际位置、占位状态、输入/输出与备份 |
| [W05 准备记录](USER_MOLECULE_W05_PREPARATION_zh-CN.md) | 实测元数据、候选夹具、19 项判据、参考与资源提案；数值未执行 |
| [W05 决策单](templates/USER_MOLECULE_W05_DECISIONS_zh-CN.md) | B01—B07 的具体证据与出口；未填写不代表批准 |
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
