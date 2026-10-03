# 结果判读与复核材料整理

先从 [服务对应表](PROFESSIONAL_SERVICES_zh-CN.md)确定 task 和科学层级，再阅读原始 manifest、result、report 与日志。S1/S2 不应被要求提交不存在的分子 result.json。报告使用 [模板](templates/REVIEW_REPORT_zh-CN.md)，示例见 [已有 Docker 记录](examples/P14_REVIEW_20261002_zh-CN.md)。

## 四层判读

| 层 | 读取内容 | 可以说明 | 不可替代 |
|---|---|---|---|
| 执行与完整性 | manifest.status、process_exit_code、runtime_exit_code、output_sha256、身份 | 特定任务如何结束、原文件是否匹配 | 科学数值资格 |
| 数值资格 | numerical_qualification、task 专属 gate、acceptance_checks、电子数/收敛/残差 | 登记数值检查是否通过 | 原著比较或方法普遍有效性 |
| 数值比较 | source_comparison、differences、quantitative_evidence，明确参照及单位 | 固定/优化端点或结构响应偏差 | 科学分类及其范围 |
| 科学分类 | classification、decision_verdict、decision_checks、scope、limitations | 登记 C12H6 案例内联合判定 | 任意分子或全部芳香性理论 |

runtime status 与子程序退出码分别保留。原进程退出 0 但 gate 非 PASS 时，runtime 可以 status=FAIL、runtime_exit_code=0；只看退出码会误判。`scientific_comparison=NOT_APPLICABLE` 是未在该任务分类，不是科学失败。L0/L1 的 numerical_qualification 通常 NOT_APPLICABLE。UNKNOWN、unavailable、NOT_EXECUTED、BLOCKED、FAIL 不能互换。

## 账本与参照

固定几何普通 G、普通 @PLG 的 `total_energy_hartree` 与条件 PLG 的能量应分别列出。条件态输出 `one_electron_energy_hartree/coulomb_energy_hartree/exact_exchange_energy_hartree/semilocal_xc_energy_hartree/nuclear_repulsion_hartree/total_energy_hartree` 及闭合残差；普通态未输出的分项不推算补填。

数值残差先报告原字段的有符号值；绝对值如由人工计算，标“派生值”并附公式 |实际−参照|。原著端点 67.08 kcal/mol 与冻结固定几何端点约 67.086899 kcal/mol 是不同参照。原著 dΔr=0.179 Å 与冻结优化响应约 0.172204 Å 同样不同。与冻结记录吻合只说明同协议重复性。

P.final_classification 登记能量比较容差 5.0 kcal/mol、键长响应容差 0.03 Å、PLG 近等键阈值 0.015 Å；它们不替代 SCF 或实现等价性阈值。方法、基组、网格与容差必须来自锁定协议/代码，不按期望结论调整。

## 来源、父关系与历史记录

1. 记录实际 source_commit、镜像内 runtime_commit、本地 image_id、manifest 中 image_digest 原值、实际依赖与锁哈希。宿主启动器提交另外列；没有记录写 UNKNOWN。
2. image ID 是本地配置身份；registry manifest digest 是不同身份。旧摘要字段名 image_digest 或 RepoDigests 的值不足以证明已发布远端镜像。示例原样保存历史字段，不将其当作公开下载地址。
3. 对每份原始文件核对 manifest.output_sha256。四父结果还须与分类 manifest.parent_runs 和 result.evidence_sha256 一致。父 manifest 与分类 manifest 也各自留存 SHA-256。
4. `result.runtime_provenance/source_calculation_git_commit` 可能是上游冻结历史元数据。实际本轮执行以 manifest 为准；原字段留存并注记，不覆盖原输出。
5. 历史阶段摘要中的“L4 未执行”是该阶段当时状态。最终联合分类以 classification-summary 与其原始运行为准。保留旧记录，不改写旧状态为最终状态。

## 失败、不完整或缺失材料

| 情形 | 报告处理 |
|---|---|
| L0/L1 失败 | 保留失败日志与位置，停止科学解释；不补写 PASS |
| 内存不足或来源不匹配 | 写 BLOCKED/FAIL 的实际状态、错误与资源；不降阈值 |
| L4 仅检查点、缺最终 result | 写部分完成，列已知 stage；不支持恢复，也不得进入联合分类 |
| 缺父 manifest / 哈希不符 / 依赖不兼容 | 该集合不能组成合格分类输入，不用冻结结果补缺 |
| 原分类记录为 partial/disagreement | 原样报告 classification、decision_verdict、失败检查；不能用退出 0 写成一致 |
| 未做平台、断网、中断或 CI 实测 | 写 NOT_EXECUTED；平台阻塞原因另列 |

## 手工交付布局

```text
review/summary.md                 # 按模板填写；与原始结果分开
review/source-references.md       # 来源、镜像、宿主身份与固定引用
runs/<run-id>/                   # manifest、原结果/报告、日志、适用检查点
```

可留本地原路径引用；若移交复核副本，保留完整文件与 manifest，记录副本位置并重新核对哈希，不覆盖原目录。分类运行仍遵循 RUN 的 OutputRoot 约束。报告本身不改变科学结论，不自动上传。`review/index.json`、自动汇总、跨目录复制和独立普通 Python 分类接口均未实现。

完整复核报告应包含失败/未知记录，生产标签和训练资格不得被手工报告改为 true。发布前另审隐私与授权；镜像分发阻塞、WSLc 暂停及 CI 未执行继续保留。
