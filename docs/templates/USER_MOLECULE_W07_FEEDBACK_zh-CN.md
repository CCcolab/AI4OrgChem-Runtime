# W07 工程试用反馈模板

2026-10-06 / W07-ENGINEERING-PREPARATION-1。按 [三步指南](../USER_MOLECULE_W07_ENGINEERING_TRIAL_zh-CN.md) 手工填写并保存新副本。本轮已完成工程人员的 Check→Report→导出演示，机器证据见指南；该演示不代替真实专业用户验收。以下所有真实用户填空继续保持 PENDING，空白不代表完成或批准。本轮仅保存本地反馈。

## 输入确认

| 项目 | 实际填写 |
|---|---|
| 填写人、操作人、日期 | PENDING |
| 使用方式：本人独立操作 / 工程人员演示 / 其他 | PENDING；不得将工程演示记成真实专业用户验收 |
| 输入类型：默认工程夹具 / 自有已确认 XYZ | PENDING |
| request.json 实际路径、SHA-256 | PENDING |
| XYZ 实际路径、SHA-256、来源说明 | PENDING；不杜撰来源或使用未确认分子 |
| 固定几何；仅 C/H；中性闭壳层；angstrom；xy 平面 | PENDING；逐项由使用者确认 |
| 原子总数；原子编号依据 | PENDING；从 XYZ 原子行 1 起，不自动重排/加氢 |
| A 碳编号；B 碳编号；确认人及确认日期 | PENDING；每个碳恰好一次、两组非空，不包含氢 |
| condition_definition_acknowledged；condition_profile | PENDING；确认登记的两组碳 π 条件规则，输入确认不代表方法批准 |
| calculation_profile；threads / memory_limit_mib / wall_time_limit_seconds | PENDING |
| 研究问题及本轮工程目的 | PENDING；本轮无可用科研能量差 |

默认演示的已核对事实仅供比对：`examples/user-molecule/w05-candidates/ethene-planar-technical-v1/request-pilot.json` 引用同目录 `molecule.xyz`；6 原子，A=`[1]`、B=`[2]`，pilot / 1 线程 / 512 MiB / 60 秒。该事实不代填“实际使用”或自有 XYZ 确认。

## 每步实际记录

退出码填写真实整数；未执行填 NOT_EXECUTED，无法确定填 UNKNOWN，不用预期码补齐。可用性填写“可用/受阻/未执行”并给证据；问题填写原错误与触发步骤。

| 步骤 | 实际命令或日志文件 | 实际宿主进程退出码 | 可用性 | 问题及证据 |
|---|---|---|---|---|
| 1 输入确认与请求准备 | PENDING | PENDING | PENDING | PENDING |
| 2 Docker 候选 Check | PENDING | PENDING | PENDING | PENDING |
| 3 基础 Report | PENDING | PENDING | PENDING | PENDING |
| 3 高级 Report（已有 Python） | PENDING | PENDING | PENDING | PENDING |
| 3 fresh 外部目录导出 | PENDING | PENDING | PENDING | PENDING |

- 本次实际单次 `$run` 目录、run_id 与来源（自己的 Check / 已有记录）：PENDING；不以工程人员演示记录代填自己的操作。
- fresh 导出目录及其位于源运行目录之外的确认：PENDING。
- 操作系统、已有 PowerShell/Python/Docker 版本与实际可执行路径：PENDING；未用工具写 NOT_EXECUTED。
- 宿主启动器/Report 源码提交与 SHA-256：PENDING。
- 本地 image_id、镜像构建 runtime_commit、science_commit、数值测试 runtime_commit：分别填写 PENDING 或 UNKNOWN；既有 r3 未重建，身份不可混写。
- 最小证据：`preflight.json`、`host-execution.json`、`run-manifest.json`、`report.md`、`report-summary.json`（若导出）、必要日志，附实际文件名和 SHA-256：PENDING。

## 报告原状态与差值

从实际源记录和高级导出的 JSON 原样摘录；保留原始标签与高级判读，不用历史缓存理由或 UNKNOWN 代替当前数值验收、推送或发布状态。宿主与容器码分别记录；高级退出 0 不构成 `sciencePass`，基础退出 0 不证明关键快照完整。

| 字段 / 证据位置 | 原样摘录 |
|---|---|
| Check `input_status`、`compute_eligible` 与原因 | PENDING |
| `report_exit_code`（本次高级读取/导出） | PENDING |
| `original_exit_code`、`original_exit_code_source` | PENDING |
| `host_service_exit_code` | PENDING；缺失保留 null/UNKNOWN |
| `container_exit_code` | PENDING；缺失保留 null/UNKNOWN |
| `host_exit_code` | PENDING；缺失保留 null/UNKNOWN |
| `host-execution.json.status`、`termination_reason`、`oom_killed` | PENDING；保留宿主原状态与实际终止原因 |
| `record_integrity`、`record_integrity_scope`、缺失/证据问题 | PENDING |
| `raw_statuses`、`raw_state_labels` | PENDING；旧标签不构成新资格 |
| `execution_status`、`scientific_execution_status` | PENDING |
| `numerical_status`、`method_status`、`research_status` | PENDING |
| `comparison_available` | PENDING；本轮 Check/失败记录的比较不可用 |
| `delta_hartree`、`delta_kcal_mol` | PENDING；比较不可用时两项均保持 null，不能由失败能量补算 |
| `failed_metric_ids`、`reasons`、`qualification_reasons` | PENDING |

## 使用者反馈

以下内容由实际使用者填写；工程人员可记录操作事实，不能代填真实用户评语。

- 能否按 1、2、3 完成操作，受阻的具体步骤：PENDING。
- 是否能找到并确认 A/B 的碳编号、输入映射与 profile：PENDING。
- 是否理解同一几何的比较方向 `Eordinary−Econditional`、当前比较不可用与 null 的含义：PENDING。
- 是否能区分输入合法、Report 读取成功、数值资格与方法/研究批准：PENDING。
- 最难理解的文字或错误、原文和希望的改进：PENDING。
- 其他实际反馈、反馈人及日期：PENDING。
- 本次工程操作反馈结论及证据：PENDING；不填写完整科研用户验收通过。

## 未执行与未关闭事项

| 事项 | 本轮保留状态 |
|---|---|
| 自有分子试用与真实专业用户独立操作反馈 | PENDING；工程人员已完成的演示不代替用户填写或验收 |
| 新 Compute、SCF、格点或完整 ERI；重建镜像 | NOT_EXECUTED；本轮工程试用不执行 |
| W05/W06 新数值验收或失败状态提升 | NOT_EXECUTED；保存的真数值失败继续保留 |
| 正式 W07 科研用户验收、两个合格研究体系与研究范围批准 | BLOCKED；本模板属于 A14 类工程准备 |
| 方法四问咨询 / MDR-001 真实方法审阅批准 | DEFERRED / 仍未真实审阅批准；材料齐全后再征询 |
| WSLc / 远端 CI / Colab | BLOCKED/暂停 / NOT_EXECUTED / DEFERRED |
| 镜像分发、源码公开、推送、正式标签与 Release | BLOCKED 或继续暂停；不由反馈隐式授权 |
| 原 L4 恢复 | UNSUPPORTED；可保存检查点，不可 resume |

填写完成不自动关闭门禁，也不自动发送反馈。
