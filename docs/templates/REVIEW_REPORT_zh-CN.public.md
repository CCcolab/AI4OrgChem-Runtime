> 当前公开阅读节选。原始历史材料已按原字节保存在本地归档；本文件不是原件，不能用于原始哈希验收，也不把旧验收转移至当前代码。
> 原件 Git 提交：eb65b4586c83637569f6359814338c1292948861；SHA-256：97ff5a058188c3b7714cfdc673a0c22c83ebf9b9c61580d261ed7af544c6e4d4。

# 专业复核报告模板（手工填写）

本模板保留P14/S1—S6历史字段和四父关系。普通分子、固定示例、专题与高成本模块请先使用 [当前通用复核模板](CURRENT_SERVICE_REVIEW_zh-CN.md)和 [当前专业服务矩阵](../CURRENT_PROFESSIONAL_SERVICES_zh-CN.md)。下文的历史CI/公开状态仅供原记录判读，当前状态按能力注册表填写。

模板不是实际验收记录。保留不适用/未知项，删除占位说明后交付；不得由模板自动产生 PASS。参考 [判读指南](../REVIEW_RESULTS_zh-CN.public.md)。

## 范围与问题

- 报告日期、作者/复核者、待核问题：待填写。
- proposition / protocol_id / scope：待填写（P14 登记 C12H6、平面 D3h 五参数 source-proxy）。
- 比较量、符号、单位、参照态、电子状态、几何来源、方法/基组/网格与约束：待填写。
- 判据的固定协议/代码链接：待填写；未覆盖问题：待填写。

## 身份与材料

| 项目 | 实际值或 UNKNOWN | 依据文件/字段 |
|---|---|---|
| 科学源码完整 SHA、tag | 待填写 | source.lock / manifest.source_commit |
| 镜像构建 runtime SHA | 待填写 | manifest.runtime_commit / image labels 记录 |
| 宿主启动器、文档提交 | 待填写 | 独立记录；未留存则 UNKNOWN |
| image ID / registry digest（分别列） | 待填写 | image_id / image_digest 原值及身份说明 |
| 依赖版本、依赖锁摘要、runtime 快照摘要 | 待填写 | dependencies / dependency_lock_sha256 / runtime_code_sha256 |
| 平台、CPU、线程、内存、时长、断网条件 | 待填写 | 实际记录；未实测项 NOT_EXECUTED |
| 协议、输入与输出哈希、原路径或副本路径 | 待填写 | input_sha256 / output_sha256 |

## 四层结果

| task / run_id | 执行 status / 子程序与 runtime 退出码 | 数值资格及失败检查 | 比较量、参照、有符号/绝对残差与单位 | 科学分类及范围 |
|---|---|---|---|---|
| evidence | 待填写 | NOT_APPLICABLE 或实际状态 | 完整性日志；无分子账本 | 不新增分类 |
| core-tests | 待填写 | 原 pytest 日志、失败位置 | 受测规则与覆盖缺口 | 不新增分类 |
| p14-smoke | 待填写 | 待填写 | 技术端点；非科学定判值 | NOT_APPLICABLE |
| p14-equivalence | 待填写 | 待填写 | 能量/密度/ERI/分量差异，STO-3G | NOT_APPLICABLE |
| p14-fixed | 待填写 | 待填写 | 能量账本；原著与冻结参照分列 | 此任务不独立分类 |
| p14-optimize | 待填写 | 待填写 | 结构、梯度、边界、端点及 dΔr | 此任务不独立分类 |
| p14-classify | 待填写或 NOT_EXECUTED | decision_verdict / checks | quantitative_evidence | classification / scope / limitations |

条件态账本分列单电子、Coulomb、exact exchange、semilocal XC、核排斥、总能量及闭合残差；普通态不存在的分项写 unavailable。列电子数、收敛、对易子、幂等性。优化附 G/PLG 的 termination_reason、梯度、active_bounds 和几何参数。

## 四父关系与完整性

| 父 task | run_id | result SHA-256 | manifest SHA-256 | 与分类引用匹配/缺失 |
|---|---|---|---|---|
| p14-smoke | 待填写 | 待填写 | 待填写 | 待填写 |
| p14-equivalence | 待填写 | 待填写 | 待填写 | 待填写 |
| p14-fixed | 待填写 | 待填写 | 待填写 | 待填写 |
| p14-optimize | 待填写 | 待填写 | 待填写 | 待填写 |

分类 run_id、manifest/result 哈希及实际命令：待填写。源码、输入、依赖、协议兼容性检查及失败项：待填写。缺少任何父结果时只形成部分报告，不补填分类。

## 限制、失败与交付

- 实际分类原文、数值资格、参照差异与结论边界：待填写，不扩大至普遍理论。
- 历史元数据与实际身份的区别、旧失败/未知/未执行记录：待填写。
- 检查点状态：待填写；**L4 不支持恢复运行**；真实中断验收 NOT_EXECUTED，除非另有真实证据。
- production_label / training_eligible：保留原值，不授予新资格。
- 材料索引、哈希、复核意见及未解决问题：待填写。
- 公开边界：源码公开另行确认，镜像分发 BLOCKED；报告不授权上传或发布。
