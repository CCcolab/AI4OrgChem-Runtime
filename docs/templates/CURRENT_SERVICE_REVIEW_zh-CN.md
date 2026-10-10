# 当前专业服务复核模板

这是手工模板，不是验收结果。先从 [当前服务矩阵](../CURRENT_PROFESSIONAL_SERVICES_zh-CN.md)选择模块和允许解释；P14四父分类另附 [原模板](REVIEW_REPORT_zh-CN.md)。不适用、未知、缺失和未执行保留原状态，不自动产生PASS。

## 问题和协议

| 必填项 | 实际值 | 文件／字段依据 |
| --- | --- | --- |
| 模块、task/case/unit、问题与日期 | 待填写 | 能力表仅作导航；选择实际运行 |
| 输入、原子/片段映射、几何、电荷/多重度与哈希 | 待填写 | 原请求、XYZ、只读输入快照 |
| profile/protocol版本与固定来源 | 待填写 | 当前合同、来源锁；冻结baseline与captured adapter分列 |
| 方法/基组/网格、算子、约束与能量功能式 | 待填写 | ordinary/conditional、h/F/S/ERI规则分别列 |
| 比较量、公式、符号、单位和参照状态 | 待填写 | 差值双方同方法/几何/状态兼容性，或明确差异 |
| 实际验收与未覆盖检查 | 待填写 | 原checks、失败项、源与独立审计范围 |
| 成本与预算 | 待填写 | CPU/threads/memory/scratch/wall与实际调用；预留不等于实测 |
| 允许解释及研究范围 | 待填写 | 数值合格、源协议比较、研究解释分开 |

## 身份和证据

| 身份 | 实际值或UNKNOWN | 依据 |
| --- | --- | --- |
| 科学基线、捕获工作树上下文、逐文件SHA | 待填写 | 588baseline＋3adapter或该模块自己的来源锁 |
| 历史/本轮镜像构建runtime提交 | 待填写 | image build记录；不能用当前HEAD代填 |
| 实际宿主启动器身份和当前文档提交 | 待填写 | 独立host身份/哈希 |
| image ID与公开registry digest | 待填写 | 两者分列；无公开digest填UNKNOWN |
| 依赖、安装身份、input/profile/source/result/manifest哈希 | 待填写 | 实际receipts；历史PASS不迁移到新安装 |
| accepted run/execution ID、父任务/Unit依赖 | 待填写 | 只接受该协议要求的完整兼容结果 |
| 可公开取得的见证和完整本地原材料 | 待填写 | 包路径、SHA、重算命令及覆盖范围；摘要不是原始矩阵 |

## 执行、数值与解释

| 层次 | 原状态、字段与依据 | 结论范围 |
| --- | --- | --- |
| 执行 | process/worker/host/runtime退出码、stdout/stderr、守卫和resource receipts、容器删除与输出保留 | 待填写 |
| 数值 | SCF、electron、density/idempotency/commutator、gap/mapping、energy closure、optimizer梯度/边界与checks | 待填写；未运行的审计不补造PASS |
| 科学比较 | 比较量/参照/残差/容差、classification和scope | 待填写；库包装一致性与独立实现分列 |
| 研究解释 | 驻定性、稳定性、方法适用范围和允许结论 | 待填写；固定点不自动等于稳定极小值 |

条件态额外分列 `Tr(S̃D)`、`Tr(SD)`和网格积分电子数，使用该结果的原字段名。能量分列单电子、Coulomb、exact exchange、semilocal XC、核排斥、总能量和闭合残差；普通态没有的字段填unavailable。AO矩阵和条件操作性能差不直接解释为实验测量或键能。

## 失败、缺口与交付

原失败记录、异常终止、尾检缺失、公开见证覆盖缺口和未完成状态：待填写。P11/P12只验收两先导态时不形成完整多态组装；root无正式端点时不形成合格条件能差。L4检查点不支持resume。

源码/静态指南公开、CI实际run/提交/job范围、WSLc暂停、预构建镜像阻塞分别按 [能力注册表](../../configs/runtime-capabilities-v2.json)和实际运行登记填写。报告不新增科学gate、不代填外部专家意见；当前项目内部证据要求仍以原合同为准。
