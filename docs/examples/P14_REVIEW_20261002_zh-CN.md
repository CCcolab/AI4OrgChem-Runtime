# 已有 Docker 验收记录的专业复核示例

整理日期：2026-10-03；计算日期：2026-10-02。本文读取既有原始记录，不运行新计算，也不重新分类。[字段摘录与完整 manifest](P14_REVIEW_20261002.json)保留实际命令、依赖、输入/输出哈希与本地原路径；[固定源码引用索引](professional-source-index.json)列出协议、脚本、测试、证据卡及 SHA-256。摘要不能替代原始运行目录。

## 范围、身份与环境

- 科学 source：`28511f3d84fa65707a107cde1e8121a7b4334ecb`，v0.3.2。
- 镜像构建 runtime：`f30b2906794d14f9030daab779c0d6a7cd4bd6f7`。
- 本地 image ID：`sha256:ddc45b1fe500ed3d5ed30520eb4e49f3969cb69f02121f28e2ff851f7a724f54`。历史 manifest.image_digest 同值，原样留存；没有据此声明远端 registry manifest 已验证或公开镜像可下载。
- 本轮文档基线：`2460eef636be9a143d3bbb81daf8f66fc7e70959`，与构建身份分开。
- 宿主启动器历史文件身份见 [provenance-review](../../validation/provenance-review.json)：start-runtime.ps1 最后修改 b515c1d；run-wslc.ps1 最后修改 c2cc502。各次运行当时宿主 Git HEAD 未单独留存，UNKNOWN；不能用这些文件身份冒充逐运行提交证明。
- 平台：指定本地 Docker / Linux x86_64 CPU；主机 Intel Core Ultra 9 185H，16 物理核、22 逻辑处理器；请求线程 8。实际依赖、锁及每次命令见 JSON 的 manifest；8 线程不等于硬 CPU 配额。
- 方法合同：C12H6、0 电荷、单重态、78 电子、气相；source-proxy 几何；S3 为 STO-3G/grid 2，S4/S5 为 B3LYPG/6-31G(d)/grid 3；G 无屏蔽，PLG 按登记条件态规则。
- S4 的 C-H 固定代理 1.080 Å；S5 五参数顺序为 rendo、rexo、rside、router、rCH，仅平面 D3h。参照和规则以固定协议为准。

## 运行清单与四层状态

下列七项是最终 Docker 验收集合。执行 status 均为 PASS，process_exit_code/runtime_exit_code 均为 0。L0/L1 无分子 result.json，资格为 NOT_APPLICABLE。

| task | run_id | 数值资格 | 科学比较 |
|---|---|---|---|
| evidence | 20261002T111546Z-evidence-eb8faa387218 | NOT_APPLICABLE | 不新增判定 |
| core-tests | 20261002T111548Z-core-tests-1651766c39cd | 原测试 11 passed | 不新增判定 |
| p14-smoke | 20261002T111549Z-p14-smoke-611ad4389dee | smoke_gate PASS | 非科学定判值 |
| p14-equivalence | 20261002T111600Z-p14-equivalence-a83e2e3a8f2f | verdict PASS | STO-3G 受测实现等价性 |
| p14-fixed | 20261002T123033Z-p14-fixed-d621c0cfab97 | anchor_gate PASS | 本 task 不独立分类 |
| p14-optimize | 20261002T123346Z-p14-optimize-d7f348003891 | production_gate PASS | 本 task 不独立分类 |
| p14-classify | 20261002T144015Z-p14-classify-675fab20a66f | decision_verdict PASS | consistent，限登记案例 |

分类实际采用另一份 smoke 父运行 `20261002T115757Z-p14-smoke-5edcc0ade184`，并非表中的 L2 验收 smoke。两份均保留；父关系未被改写。

## 固定几何能量账本与资格

字段来自 p14-fixed.result。普通 G 总能量 −460.6207689426276 Eh；条件 PLG 总能量 −460.72767872187546 Eh。普通 @PLG 为独立诊断记录，值及状态在 JSON 中，不能替代条件态。

| 条件 PLG 分量/残差 | 值 | 单位/判读 |
|---|---|---|
| one_electron_energy_hartree | −1781.0910286224855 | Eh |
| coulomb_energy_hartree | 802.3411811963462 | Eh |
| exact_exchange_energy_hartree | −12.888113202511162 | Eh |
| semilocal_xc_energy_hartree | −54.57057989390052 | Eh |
| nuclear_repulsion_hartree | 585.4808618006755 | Eh |
| total_energy_hartree | −460.72767872187546 | Eh |
| energy_component_closure_residual_hartree | 0.0 | Eh；按原字段，不额外推断精度 |
| final_commutator_frobenius_norm | 3.2107519868034144e-8 | 原登记数值检查 |
| closed_shell_idempotency_relative_residual | 3.361294944237049e-15 | 相对残差 |
| masked/physical_metric_electron_count | 78.0 / 78.0 | 电子；网格积分电子数另列，不混用 |

普通 G 的单电子、Coulomb、exact exchange、semilocal XC 分项未输出，unavailable；总电子能量与核排斥在原记录可查。三个态收敛、电子数及全部 12 项 anchor 检查通过；自身资格不等于最终科学分类。

| 量 | 实测 | 参照及有符号残差 |
|---|---|---|
| 固定几何端点 | 67.08689934803395 kcal/mol | 原著 67.08；+0.006899348033954311 kcal/mol |
| G 总能量 | −460.6207689426276 Eh | 原著 −460.6304；+0.009631057372416763 Eh |
| PLG 总能量 | −460.72767872187546 Eh | 原著 −460.7373；+0.009621278124541277 Eh |

这里的正残差绝对值与原有符号数值相同（派生 |实测−参照|）。同协议冻结固定端点约 67.086899 kcal/mol 是另一个参照，不称为原著数值；本表不以四舍五入值伪造完整冻结残差。

## 结构响应与优化端点

| 量 | 实测 | 原著参照；有符号残差 |
|---|---|---|
| Δr(G) | 0.17724028577397366 Å | 原著 0.177 Å |
| Δr(PLG) | 0.005036650109448759 Å | 原著 −0.002 Å |
| dΔr(GP) | 0.1722036356645249 Å | 0.179 Å；−0.006796364335475091 Å |
| 优化端点 | 67.67971905631804 kcal/mol | 67.08；+0.5997190563180368 kcal/mol |

原著残差绝对值分别为 0.006796364335475091 Å 与 0.5997190563180368 kcal/mol（派生取绝对值）。[L4 摘要](../../validation/l4-summary.json)另外列出与同协议完整冻结值的残差：端点 −7.133991175578558e-10 kcal/mol、dΔr +4.003519737949546e-10 Å；这说明特定环境下的重复性，不代表原著相同精度。

G/PLG 最大梯度分别为 0.001462869559316535、0.0011655667251974366 Eh/Å，低于登记 0.002；两者 success=true、active_bounds=[]，终止原因为 gradient_tolerance_satisfied。18 项 production 检查通过。完整五参数几何及状态见 JSON 摘录，不宣称全空间稳定性或频率分析。

L3 原脚本耗时 54.369574647 秒、峰值 8800.86328125 MiB；L4 1272.177734144 秒、8801.19921875 MiB。约 21.20 分钟和 8.60 GiB 是历史单次观测，不能保证未来成本，也不能降低 13000 MiB / 13 GiB 预检。L4 检查点已留存，但不支持 resume。

## 四父来源与联合分类

| 父 task / run_id | result SHA-256 |
|---|---|
| p14-smoke / 20261002T115757Z-p14-smoke-5edcc0ade184 | a05ea503afba62cd147aec5b3030780ff8203dfeae218347af8c0a8ba2fa2771 |
| p14-equivalence / 20261002T111600Z-p14-equivalence-a83e2e3a8f2f | effbc7a24ddaaf6d9b9bae9309430b63fe8333c7457d6bf275ee5bd371bd83d1 |
| p14-fixed / 20261002T123033Z-p14-fixed-d621c0cfab97 | 6408a5317a6f83186dc540069ba1f0308d51721ef87a7a4317e423bf28d03257 |
| p14-optimize / 20261002T123346Z-p14-optimize-d7f348003891 | 0a1e89ed6cbd47f8ae1be768149baa0aeebd9f72bbcbb0d8046d234a8ac66929 |

manifest SHA-256、原路径和分类引用均在 JSON.classification_parents / runs。源码、输入哈希、实际依赖匹配；四父结果哈希同时匹配 manifest.parent_runs 与 result.evidence_sha256。STO-3G 实现能量差 2.2737367544323206e-13 Eh，不能外推高级基组实现等价性。

已有分类为 `consistent`，decision_verdict=PASS，范围为 `benzotricyclobutadiene_10_12_C12H6_frozen_source_proxy_protocol`；原记录 production_label=false、training_eligible=false。没有重算或改写这些值。全部限制见 result.limitations；单个 C12H6 案例不建立十九分子普遍定律。

## 复核结论与未执行事项

本轮只读检查了 588 个来源文件、八个 manifest 及其登记输出、四父哈希和兼容身份，均匹配。该检查证明记录对应与文件完整性，未重新执行 SCF、优化或分类，也不证明对所有代码的安全认证。

已有严格断网验证覆盖 L0—L2、等价性及指定探针；L3/L4 严格断网、真实停止/中断验收 NOT_EXECUTED。WSLc BLOCKED / NOT_EXECUTED，WSL 升级暂停；CI 静态审查完成、运行 NOT_EXECUTED。镜像分发 BLOCKED，源码公开另行确认。本例含本地原路径和环境信息，新增材料的公开范围需另行审阅。
