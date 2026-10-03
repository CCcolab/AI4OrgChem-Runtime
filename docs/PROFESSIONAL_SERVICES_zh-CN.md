# 专业复核服务与模块对应表

日期：2026-10-03。本轮补充文档与手工复核模板，计算接口仍为七个任务。科学来源固定为 AI4OrgChem `28511f3d84fa65707a107cde1e8121a7b4334ecb`（v0.3.2），runtime 文档基线为 `2460eef`。本文不新增计算能力或科学判据。

入口：[三类用户路径](USER_PATHS_zh-CN.md)、[结果判读](REVIEW_RESULTS_zh-CN.md)、[已有运行示例](examples/P14_REVIEW_20261002_zh-CN.md)、[复核模板](templates/REVIEW_REPORT_zh-CN.md)、[反馈模板](templates/FEEDBACK_zh-CN.md)。实际使用参数见 [RUN](RUN_zh-CN.md)。

## 固定来源与字段约定

下列上游路径均相对于[固定科学提交](https://github.com/CCcolab/AI4OrgChem/tree/28511f3d84fa65707a107cde1e8121a7b4334ecb)，并由 [588 文件来源锁](../locks/source-files.sha256.json)核对。`P` 指 `configs/qm/p14_strained_aromatic_pi_distortivity_v0.1.yaml`；`X` 指 `configs/qm/p09_exchange_integral_classes_v0.1.yaml`。P 的协议 ID 为 `p14-strained-aromatic-pi-distortivity/0.1`。脚本路径前缀为 `software/scripts/`；数值核心前缀为 `software/src/ai4orgchem/qm/`。

[精确来源索引](examples/professional-source-index.json)提供上述协议、代码、测试及 P01—P14 原始卡片/协议/报告的固定提交链接和文件 SHA-256，包含 P12 三份账本。索引由本地锁定归档逐文件核对，不依赖浮动 main。

字段使用点路径：`manifest.*` 为运行目录的 `run-manifest.json`，`result.*` 为同目录 `result.json`。L0/L1 没有统一分子 `result.json`，读取日志和 manifest。字段可用性已核对已有原始记录；缺失时记 unavailable，来源不明记 UNKNOWN，未运行记 NOT_EXECUTED，不填成零。

所有任务共有实际身份字段：`manifest.run_id/task/source_commit/runtime_commit/runtime_code_sha256/image_id/image_digest/dependency_lock_sha256/dependencies/input_sha256/commands/output_sha256`；共有执行字段：`status/process_exit_code/runtime_exit_code/numerical_qualification/scientific_comparison/wall_time_seconds`。镜像构建提交与当前宿主启动器/文档提交另列，不能互相替代。源码中的历史 `result.runtime_provenance` 不能覆盖实际 manifest。

## S1—S6 与七个任务

| 模块 → task | 固定协议/证据 | 实际代码入口 | 测试或核验依据 | 实际输出字段 |
|---|---|---|---|---|
| S1 → `evidence` | `evidence/P01-P14/README_zh-CN.md`；各项 data-card/protocol/report/result；P12 三份同协议账本；P、X | validate_public_evidence.py、validate_p12_evidence.py、validate_evidence_navigation.py、validate_p14_evidence.py | 四个验证器的真实日志；不是新 QM 复算 | manifest 执行字段、`commands/output_sha256`；00—03 stdout/stderr；无统一 result |
| S2 → `core-tests` | X、P.state_contract | 三份 `software/tests/test_p09_conditional_scf.py`、test_p09_energy_assembly.py、test_p09_eri_mask.py，由 pytest 执行 | 下表列出直接测试与未直接覆盖处；既有日志 11 tests | manifest 执行字段、00-stdout.log/00-stderr.log；无分子能量账本 |
| S3 → `p14-smoke` | P.smoke_gate；公开 source-proxy 输入 | run_p14_benzotricyclobutadiene_smoke.py；p09_conditional_scf.py | `result.acceptance_checks` 与 P.smoke_gate.acceptance | `smoke_gate_verdict`、ordinary_G、ordinary_at_PLG、conditional_PLG、technical_endpoint_kcal_mol、G_geometry、PLG_geometry |
| S3 → `p14-equivalence` | P.smoke_gate、X；STO-3G PLG | validate_p14_memory_controlled_conditional_scf.py；p09_energy_assembly.py 两种 ERI 屏蔽路径 | 脚本 acceptance_checks：能量 ≤1e-10 Eh、密度 Frobenius ≤1e-9 等；不推广高级基组 | `verdict`、`reference`、`memory_controlled`、`differences`、`acceptance_checks` |
| S4 → `p14-fixed` | P.production_calculation、source_anchors_B3LYP_6_31G_star | run_p14_benzotricyclobutadiene_source_level_fixed_geometry.py | `acceptance_checks`、P 数值门禁；分类残差另由上游分类器判断 | `anchor_gate_verdict`、method、geometry_contract、ordinary_G、ordinary_at_PLG、conditional_PLG、fixed_geometry_endpoint_kcal_mol、source_comparison |
| S5 → `p14-optimize` | P.production_calculation.geometry_optimizer | run_p14_benzotricyclobutadiene_production_optimization.py | `acceptance_checks`、优化终止原因、梯度与边界、P 登记参数 | `production_gate_verdict`、G_state、PLG_state、G_optimizer、PLG_optimizer、optimized_G_geometry、optimized_PLG_geometry、d_delta_r_GP_angstrom、optimized_endpoint_kcal_mol |
| S6 → `p14-classify` | P.final_classification；四份合格分阶段结果 | classify_p14_strained_aromatic_pi_distortivity.py；runtime/classify.py 仅路径适配；runtime/cli.py validated_input | `decision_checks/optimization_eligibility_checks`；tests/test_classifier_adapter.py、tests/test_runtime.py 是封装保护测试，非新科学判据 | `decision_verdict/classification/scope/quantitative_evidence/limitations`；manifest.parent_runs；result.evidence_sha256 |

runtime 的对应入口为 [cli.py](../runtime/cli.py)，三份上游测试不是完整物理有效性证明。高级任务的 acceptance_checks 是该次运行门禁，也不等于覆盖全部科学代码的单元测试。

## S2 规则—代码—测试对应与覆盖边界

| 登记规则 | 固定代码 | 直接测试/实际检查 | 边界 |
|---|---|---|---|
| 平面 AO σ/π 身份与片段 A/B | p09_ao_classification.py：classify_planar_pyscf_aos、z_reflection_parity；P.system.fragments_zero_based | L2 的 AO/78 电子记录；test_p09_eri_mask.py 校验 AODescriptor 与跨片段谓词 | 三份 L1 未直接逐项测试 PySCF AO 分类器，不能宣称完整 AO 覆盖 |
| 跨片段 π Fock/overlap 删除 | p09_ao_classification.py：apply_interfragment_pi_matrix_mask | test_p09_energy_assembly.py：test_conditional_fock_and_metric_cross_pi_blocks_are_zero；L2/L3 的 conditional_PLG 屏蔽残差 | 单元测试矩阵与真实分子资格分别报告 |
| 15 类交换 ERI、八重对称及允许项 | X；p09_eri_mask.py：should_delete_eri；p09_energy_assembly.py：build_eri_delete_mask、apply_eri_tensor_mask | test_p09_eri_mask.py 五项测试，包括十五类 witness、八重对称、允许项、同片段及非法描述符；test_p09_energy_assembly.py 的 vectorized/scalar 与零值测试 | L1 使用测试张量；内存受控单张量路径还需 S3 等价性记录 |
| 能量分量组装与闭合 | p09_energy_assembly.py：assemble_restricted_hybrid_energy；p09_conditional_scf.py：_evaluate_density | test_energy_components_match_independent_manual_loops；运行 conditional_PLG 或 PLG_state.energy_component_closure_residual_hartree | 普通态未输出的分项不补造 |
| 广义对易子与闭壳层幂等性 | p09_conditional_scf.py：generalized_commutator、closed_shell_idempotency_residual | test_p09_conditional_scf.py 两项测试；运行 final_commutator_frobenius_norm、closed_shell_idempotency_relative_residual | toy matrix 测试通过不能代替分子收敛 |
| 电子数、SCF 收敛 | p09_conditional_scf.py；P 数值门禁 | 运行 converged、masked_metric_electron_count、physical_metric_electron_count 与 acceptance_checks | 三份 L1 没有独立的完整分子电子数测试 |

## 专业服务卡片

### S1 协议与范围查阅

- 输入：固定来源、证据索引与各项协议；生态：Markdown/YAML/JSON，阅读无需容器或 GPU。
- 输出：证据类型表、方法合同及比较量；判读：十四项“一致”是各自受测范围内的结论。
- 限制：不包含原著全文；P12 仅查阅 N12/N14/N16 同协议材料，不新增运行 task。
- 验收：技术声明能定位到固定来源；无证据项标明未知。

| 命题 | 登记证据类型与范围（来自固定 evidence 导航） |
|---|---|
| P01 | 同态占据空间变换，密度/RHF 能量不变的操作性检查 |
| P02 | 单个公开晶体对结构—光谱关联；无重做 CIF 精修或因果认证 |
| P03 | parent-NBA 四个固定扭角松弛 PES 点；非连续极小值 |
| P04 | 十二个尝试点中十一项合格 source-proxy 端点的符号规律 |
| P05 | 同一源表路径七角度账本，六个非零正端点及零控制 |
| P06 | 同分子两个 PDSI/FUL 条件态端点；非跨分子定律 |
| P07 | 同 Hamiltonian 五态路径审计及 P04—P06 综合 |
| P08 | GL(2014) 独立代码 source-aligned 重建；非历史程序身份复刻 |
| P09 | 登记 ADE/ESE 结果与方法跨度；CIPSI 路径未完全收敛 |
| P10 | 冻结键交替坐标的电子/核排斥分量账本；非孤立因果证明 |
| P11 | furan LDE 与取代苯受限平面状态优化；旧固定几何失败保留 |
| P12 | N12/N14/N16 同比较量独立复算账本；未扩至 N18/N20/N22 |
| P13 | 图枚举与公开能量账本；非全部候选独立 QM 重优化 |
| P14 | 单个 C12H6 source-proxy、平面 D3h 五参数 B3LYPG/6-31G(d) 复算 |

### P14 共用方法合同（S3—S6）

对象 C12H6，电荷 0、单重态、气相，78 电子；片段 A 为 0—5、B 为 6—11 号碳。几何由公开描述符五参数重建，不是原著历史完整坐标。普通 G 为无屏蔽 RKS，条件 PLG 删除跨片段 π Fock/overlap 块与登记 2011 交换类。`method: B3LYP` 是协议名称，实际 `pyscf_xc: B3LYPG`；不能改用默认 B3LYP。

固定端点为 E(G@source-G) − E(PLG@source-PLG)，优化端点为 E(G@optimized-G) − E(PLG@optimized-PLG)，由 Eh 转为 kcal/mol。普通态 @PLG 是诊断参照，不替代上述条件 PLG。结构响应 dΔr(GP)=Δr(G)−Δr(PLG)，Δr=rendo−rexo，单位 Å。参照来源和公式见 P、固定几何脚本和分类器；输入哈希同时记录协议、X 与两份公开 xyz。

### S3 运行资格与实现等价性

- 输入：锁定协议与 source-proxy；生态：固定 Linux/amd64 CPU、PySCF/NumPy/SciPy；两任务分别运行。
- 输出：两份 manifest/result/report/log；判读：STO-3G、grid 2 的技术资格与直接/内存受控实现差异。
- 限制：不是 B3LYPG/6-31G(d) 等价性证明，也不是科学定判值。
- 验收：smoke_gate_verdict 与 equivalence.verdict 分别 PASS，检查实际受测字段及输入/依赖身份。线程默认 8，不是硬 CPU 配额。

### S4 固定几何复算

- 输入：登记 G/PLG source-proxy；生态：B3LYPG/6-31G(d)、grid 3，固定 C-H=1.080 Å；有效可用内存至少 13000 MiB。
- 输出：能量账本、资格、source_comparison、残差与身份；判读：自身 anchor 门禁、原著参照与冻结参照分开。
- 限制：原著总能量偏差不意味着端点同等偏差；缺失普通态能量分量记 unavailable。
- 验收：原资格检查 PASS；最终比较由 S6 判定。历史峰值不能替代启动预检。

### S5 结构响应复算

- 输入：P 登记五参数、边界与初值；生态：同高级方法/网格，SciPy L-BFGS-B，有效可用内存至少 13 GiB；同锁根管理的计算串行。
- 输出：G/PLG geometry、state、optimizer、dΔr、端点、已写检查点；判读：梯度、活动边界、终止原因和数值资格逐项检查。
- 限制：仅平面 D3h 五参数子空间；没有全笛卡尔优化、频率/全局最低点证明。检查点不支持 resume；真实停止后的保留验收 NOT_EXECUTED。
- 验收：production_gate_verdict 及登记检查均合格；残差另外报告。旧 Docker L3 54.37 秒、L4 21.20 分钟、约 8.60 GiB 只是特定主机观测，详见示例。

### S6 联合分类与复核交付

- 输入：四个完整兼容运行目录，不接受冻结 JSON 替代；生态：固定环境与未修改上游分类器。
- 输出：分类原记录、父 run_id/result SHA-256、四层判读及手工复核报告。
- 判读：原分类进程退出 0 不保证联合门禁 PASS；`consistent` 只限登记案例与容差。
- 限制：Windows 启动器要求四目录位于同一个 OutputRoot 下；不支持自动搬运、更改 manifest 或跨根路径。缺一项时只写部分报告，不伪造分类。
- 验收：来源/依赖/输入、输出哈希、协议、task、状态及父关系匹配；遵守 [结果判读](REVIEW_RESULTS_zh-CN.md)。本轮没有实现自动汇总/导出，也没有第八个 task。

## 平台与公开边界

本地 Docker 指定候选七任务已有记录；独立 WSL2 指定候选仅 L0—L2/等价性通过，高级任务与联合分类未执行。WSLc BLOCKED / NOT_EXECUTED，WSL 升级和实机验收暂停。CI 静态审查完成，运行 NOT_EXECUTED。严格断网仅覆盖 L0—L2、等价性与指定探针，L3/L4 严格断网未执行。

源码公开另行确认；镜像分发 BLOCKED，剩余原生库对应来源和通知提供事项见 [公开边界](PUBLICATION_BOUNDARIES_zh-CN.md)、[来源审查](../validation/source-materials-final-review.json)。文档增补不改变既有验收身份，也未消除这些阻塞。
