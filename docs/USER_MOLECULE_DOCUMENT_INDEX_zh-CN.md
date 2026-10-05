# 用户分子服务：当前实施文档入口

日期：2026-10-05；LOCAL-SETUP-1。本页索引当前工作区的最新方案文件。工程范围 APPROVED_FOR_IMPLEMENTATION；目录准备完成，W01 IN_PROGRESS，服务 NOT_IMPLEMENTED。当前文件和历史归档分别保留，不以新索引冒充独立审阅通过。

隔离工程更新 W01—W04：当前分支已新增输入检查、科学适配器、宿主监督和专用候选构建；实际进度和执行证据按 validation/user-molecule 的新记录，操作入口见 [用户指南](USER_MOLECULE_RUN_zh-CN.md)。上述 LOCAL-SETUP-1 和各方案的“未实现”段落保留为编写时历史，新 profile 仍禁用 Compute，未继承旧七任务或研究验收。

## 1. 实施时首先阅读

| 文件 | 用途 |
|---|---|
| [完整技术方案与实施步骤](USER_MOLECULE_TECHNICAL_PLAN_zh-CN.md) | 架构、接口、状态、资源、来源与 W01—W07；首要工程依据 |
| [技术设计与步骤对应](USER_MOLECULE_DESIGN_STEP_MAP_zh-CN.md) | 解释各部件在七步中的分工 |
| [本地目录结构](USER_MOLECULE_DIRECTORY_LAYOUT_zh-CN.md) | 实际位置、占位状态、输入/输出与备份 |
| [设计与验收合同](USER_MOLECULE_ENTRY_DESIGN_zh-CN.md) | 输入与资格合同，A01—A18 最低要求 |
| [本地服务实施细则](USER_MOLECULE_IMPLEMENTATION_DETAILS_zh-CN.md) | D0—D3 阶段出口、职责与科学待办 |
| [专业实施方案](../ai4orgchem-runtime-implementation-plan-professional-revised.md) | 项目定位、现有服务、用户分子主线与 C06 |

这些是工程/审阅材料。未来用户指南将以“提交分子—检查—计算—判读—导出”为主，不要求专业用户先读本表全部文件。

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

本轮最新文档快照位于 `D:\AI4Science\ai4orgchem-runtime-deliveries\20261005-user-molecule-preimplementation-setup\latest\`，按原目录保存；同级 `LATEST_DOCUMENTS_MANIFEST.json` 记录实际大小和 SHA-256。编辑前文件在 before，静态核查在 STATIC_REVIEW.json。快照是本地保存，不是源码发布候选、完整代码备份或可运行安装包。

后续编辑以工作区原路径为主，不修改历史快照；每次需要留存时创建新的版本目录。现有 runtime 提交仍为 `0288eb8`，本轮新增文档、目录占位和准备 JSON 未提交，公开范围继续另行确认。
