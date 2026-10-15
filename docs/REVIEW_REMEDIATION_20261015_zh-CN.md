# 2026-10-15 审核整改与验收记录

本轮按“声明与指标 → 公开最小回归 → 独立轨道审查 → 条件态资格说明”的顺序完成本地修改。Runtime 基线为 `2f9e7f75d9a984429d3b836dcbc50e0dfea3c489`；原项目文档在 `02ea458881872f26be3e03fe8bf2de549f82b2a9` 的独立副本中修订，未改动原科研工作区。两者均未推送。

## 逐项结果

| 项目 | 本轮交付 | 尚未完成或本轮不执行 |
| --- | --- | --- |
| F01 技能验证 | 15 组公开输入、程序、预期值和容差；每组正常例、具体拒绝例、共用记录器缺文件例；按当前指令哈希登记 | 真实 RHF 端到端、独立会话/盲测均未执行，不能把程序回归称为 Agent 验收 |
| F02 条件态资格 | [逐协议能量、算子、度量和允许变化说明](CONDITIONAL_PROTOCOL_QUALIFICATION_zh-CN.md)，配机器来源表 | 新方向导数、积分、条件 SCF、优化和稳定性计算不在本轮范围；没有新增变分或物理解释资格 |
| F03 完整 MO | [独立只读工具](CANONICAL_ORBITAL_REVIEW_zh-CN.md)、明确策略、损坏虚轨道反例及一份保存水分子数组检查 | 未接入冻结 worker；不升级历史 PASS，不宣称波函数稳定或已验收所有历史轨道 |
| F04 公开工程回归 | 公布回归程序与日志，补预算未闭合、缺态、输入准入、零/部分发现拒绝；新增只读 CI job 配置 | 新远端 CI、新环境安装/容器端到端未执行 |
| F05 P12 指标 | [两个百分比的公式与分母](P12_COMPARISON_METRICS_zh-CN.md)，并在独立原项目副本修订 P12 报告、协议和双语矩阵 | 未推送；不重算 N16，不扩展 N18/N20/N22，不改变分类 |
| F06 AI4S 声明 | 核对并保留 M2_scoped、17/3/5 小样本、主动学习混合效果和 PySR 通过/失败 | 不提升 Agent 成熟度，不新增性质/反应预测服务 |
| F07 版本与 CI | 统一生成能力登记、README、中英文网页；最新保存 CI 与本轮未执行状态分开；注明 Skill 是发布后源码增补 | 旧 Release、指南 ZIP 和历史科学身份未回写；新 CI 未运行 |

## 实际执行

公开回归完成 **79 项**，其中 15 个正常 Skill 程序示例、15 个具体拒绝例、15 个共用 I/O 记录器上下文测试、34 个附加数值/工程检查。没有跳过测试。共用记录器测试不代表 15 次真实后端故障，严格 JSON 的注入字段拒绝也不代表 Agent 已通过提示注入评测。

执行命令从相应仓库根目录运行，输出路径替换为全新目录：

```console
python -B scripts/run-public-review-regression.py --output /path/to/new-review-record
python -B scripts/sync-current-capabilities.py
python -B scripts/audit-numerical-witnesses.py
python -B scripts/review-canonical-orbitals.py --npz evidence/numerical-witnesses/ordinary-water/orbitals-density.npz --electron-count 10 --output /path/to/new-mo-review
```

原项目独立副本执行 `software/scripts/validate_p12_evidence.py` 与 `software/scripts/validate_public_evidence.py`，只核对保存数据，均通过。P14 公共验证器在当前工具环境缺少 `jsonschema`，记 **NOT_EXECUTED_MISSING_DEPENDENCY**；未安装依赖，也未修改其历史通过状态。CI 完成源码差异、权限、固定 action 和命令范围的静态审查；当前缺少 YAML 解析器，未声称完成解析器验证或远端执行。

新的完整 MO 工具分别输出端点原资格、完整轨道数组资格和稳定性。保存水分子数组满足附加策略；损坏虚轨道的合成例中，旧端点标志仍为 True，而新数组资格被拒绝。这不是对真实历史轨道错误的认定。旧生产检查和所有来源锁均未修改。

## 证据与保留事项

- [本轮机器状态](../validation/review-20261015/status.json)
- [79 项程序回归结果](../validation/review-20261015/public-regression-result.json)与[逐项日志](../validation/review-20261015/public-regression.log)
- [保存数值见证复核](../validation/review-20261015/saved-witness-audit.json)：条件端点仍被拒绝
- [保存水分子完整 MO 附加审查](../validation/review-20261015/saved-mo-review.json)
- [原项目公开证据验证](../validation/review-20261015/upstream-evidence-validation.json)
- [AI4S 声明核对](../validation/review-20261015/ai4s-claims-check.json)

175 份登记保护文件的原始 SHA-256 均未变化，包括来源锁、计算代码和历史公开结果；15 份 SKILL.md 原字节与旧测试快照字段保留。原项目有修改的科研工作区未切换、重置、清理或覆盖。用户条件态 Compute 仍为 BLOCKED；Runtime P11/P12 仍为 78 个登记态中的两个先导态验收；镜像分发限制保留；L4 不支持恢复运行。

本轮没有新 SCF、积分、网格、F(D)、分子优化或训练调用，也没有启动 Docker/WSL、构建镜像、推送、创建标签或 Release。后续真实计算和平台验收需另行安排，不能从这些本地检查继承 PASS。
