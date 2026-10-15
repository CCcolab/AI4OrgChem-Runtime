# 2026-10-15 独立复核后回修记录

本轮只处理 R01 文档清单和 R02 非正交泄漏率示例。上一轮 `18007dc` 的 79 项记录、科学结果、来源锁和运行身份原字节保留。历史 170 项记录与摘要字段不改写；当前汇总仅追加新回归索引，旧汇总完整字节留在旧提交和旧包中。本轮不新增量化计算，不启动 Docker/WSL，不推送或发布。

## R01：当前文档快照的内部清单

在原项目干净文档副本上先复现原发布完整性失败：退出码 1，四份 P12 文档哈希失配。审阅并运行既有 `software/scripts/refresh_release_snapshot.py`，仅修改 `manifests/FILE_INVENTORY.md` 与 `manifests/sha256-manifest.json`。所有日志放在仓库外，未递归进入清单。

刷新后，发布完整性、P12、公共证据、P14 和导航五个只读验证器均退出 0。相对原项目 `02ea458` 的累计差异为**四份文档加两份生成清单，共六个文件**；“只有四份文档变化”仅适用于旧的 `968167c`。本轮未修改科学数据、公式、阈值、分类或旧 tag/Release。

## R02：平方范数比例和零向量

公开示例现在按 `r†Sr / (v†Sv)` 返回无量纲平方范数比例，不再把未归一化残差当作泄漏率。零向量明确拒绝并返回不可定义说明。

支持单个一维向量 `v:(n,)`，`S:(n,n)` 与 `B:(n,k), k>=1`；不处理列批量或自动聚合。使用复数共轭，先缩放，再 Cholesky 白化及 SVD 投影，避免非零向量仅因绝对幅度极小或极大而下溢/溢出。秩亏、零子空间和近似舍弃阈值均有明确策略；度量病态、非有限或维度不符则拒绝。策略在[版本化文件](../review_tools/nonorthogonal_leakage_policy_v1.json)，实现为[公开示例](../review_tools/skill_examples.py)，不是生产科学门槛。

七个复核探针的结果：单位/正缩放/负缩放/复数缩放/非单位度量均为 1，混合方向为 0.5，零向量拒绝。另加入极端非零缩放、复 Hermitian 度量、基列缩放、零/全子空间、维度、有限性、病态度量、秩亏和失败记录检查。

原 79 项加 17 项新回归，本次共 **96 项通过，跳过 0**。测试发现现在同时要求四个模块及策略登记的 17 项，缺失任一不能 PASS。首次沙箱运行遇到临时目录权限错误，保留失败记录；相同源码在获准的沙箱外运行通过，没有降低检查要求。

## 记录和边界

- [本次机器状态](../validation/review-corrections-20261015/status.json)
- [96 项新结果](../validation/review-corrections-20261015/public-regression-result.json)及[逐项日志](../validation/review-corrections-20261015/public-regression.log)
- [七个探针修正前后](../validation/review-corrections-20261015/leakage-probes.json)
- [内部清单修正前后及五项验证](../validation/review-corrections-20261015/science-manifest-validation.json)

上述是维护者本地回修和复验，待第三方确认，不表述为全部整改独立验收通过。真实 RHF、独立 Agent 行为、远端 CI 和全新安装继续各自未执行。条件态 Compute、完整波函数稳定性及其他未验收能力没有改变；L4 仍不能恢复运行。两项修正不涉及用户 Skill 安装目录，15 份 SKILL.md 指令未改。
