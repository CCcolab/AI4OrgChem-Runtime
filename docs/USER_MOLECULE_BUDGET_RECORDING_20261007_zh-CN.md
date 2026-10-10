# 独立参考预算感知与匹配诊断记录：工程交付

2026-10-07。新工程候选已实现，122项专项模拟测试通过（31项新测试、91项相关回归），三个可检查的模拟示例已保存并核验JSON/NPZ。**真实分子F、SCF、网格、积分、新科学进程均为0；Compute仍BLOCKED。** 这项改进解决记录和预算准入问题，不把先前数值失败改为通过。

## 改动及入口

新增`reference/residual_budgeted_candidate.py::solve_budgeted_candidate`和明确的`PreparedBudgetedSeedReference`。后者只接受ENGINEERING_FAKE，真实诊断类型在第一次回调前拒绝；旧独立求解器、旧V2科学适配器及live worker未切换，科学源码、目标条件态、占据及原最终门槛保持。

每份完整Jacobian在首个差分前预检2×变量数成本及两槽尾检余量；48变量需96个回调。基点残差来自已收费且匹配坐标的snapshot，不隐藏额外F。固定SciPy1.18.0的私有`approx_derivative`复用原3-point相对步长、零坐标fallback和边界单侧规则，串行、无稀疏分组；版本不符在F前拒绝。更换SciPy须另做兼容核查，不能假定私有API稳定。

预算拒绝后默认不动保留尾槽。仅正常结束且尾检准入时，按原门槛重新求返回D及必要的Aufbau映射D；每次回调先记账，失败不退款、不补齐或自动重试。返回D仍是最后完整改善的chart（没有完整chart则仍为seed），不拿best或最后差分点替换。

## 匹配快照与证据拒绝

已区分完整F基点、差分样本、最佳基点、最佳任意诊断样本、最后完整Jacobian对应基点、正式返回D及最后调用。COMPLETE_OPTIMIZER_BASE指完整F(base)/残差，不能当作完整Jacobian。每份snapshot保存D/F、五项能量、总能量及求值编号，通过密度ID、F-ID和operator-ID绑定；数组使用只读bytes背板，后续调用或缓冲修改不改写旧snapshot。

prepared账本同步Jac组、chart和差分编号并核对D/F身份。数量或身份映射异常时，保留lower数值gate和停止原因作为原证据，但候选整体未合格，给出ADAPTER_PHASE_ACCOUNTING_MAPPING_REFUSED。这样不会同时报PARTIAL映射与整体合格。

## 已执行的工程验证

| 项目 | 结果 |
| --- | --- |
| 新lower预算/步骤/快照/原门槛测试 | 19项PASS |
| 新prepared种子/冻结/身份映射/真实类型拒绝测试 | 12项PASS |
| 相关原参考、种子、账本及合同回归 | 91项PASS |
| 测试总量 | 122个独立ID，8组，无skip/重复/失败 |
| 实际科学操作guard | 13项绑定完整，无触发 |
| 真NR/科学回调 | entered/completed/failed均0 |

模拟evaluator计数为entered199/completed196/failed3，三次是测试预期的受控异常；另一层FakeXC为27/27/0。它们是不同层的模拟计数，不相加冒充真实NR，也不从testsRun推算。guard禁止所有测试期间的真实SCF、grid、intor、nr_rks；合成数据位于tmpfs，源码只读。

单元受测提交`1a1c0c261141f02058669f710ef402d906695c1c`；模拟导出提交`d5eeb6bc6388cddbc896bde2766d91d4644a14c9`只增补导出脚本，候选实现与测试源码逐字节相同。两次均复用现有镜像sha256:24f46f33264924e5d3d3bec386298585267c6f30d6e6a0cd0a6486ecf45db93d，没有重建镜像。

## 三个保存示例

示例是合成矩阵与受控单chart接口，**不含分子、几何或真实乙烯重演，也不是完整TRF科学优化验收**：

| 示例 | 预算/实际模拟回调 | 记录行为 |
| --- | --- | --- |
| 48变量，整组J余量不足 | 99 / 2 | 记录96计划、0差分实际、匹配基点身份；无尾检 |
| 48变量，恰可容纳整组J | 100 / 99 | 96差分完成；原返回门禁未合格，尾检实际1次 |
| 预算停止，best与返回seed分离 | 6 / 4 | best/最后差分保留，返回仍seed，正式gate为空 |

每个示例的完整snapshot registry和账本已导出result.json/snapshots.npz；在导出后和宿主分别核验整档、所有成员字节、D/F身份、五项能量与operator-ID。机器审查记录列出示例绝对路径，不需要补求F。

## 资源、状态与边界

两个工程容器均非root、离线、只读源码、512MiB、1CPU、零swap，独立工程壁钟预算各120秒，实际连日志及删除约9.656/9.406秒；退出0、日志与输出保存，容器删除。本轮没有科学预算或分子缓存挂载，不以模拟耗用推广真实分子资源。

完整W01—W07本地CI本轮未重跑，远端Actions仍NOT_EXECUTED；原全量CI与此前239项专项记录保留。旧591次真实诊断及其占据映射/正能隙失败、参考空最终gate原样保留；本改进没有真实分子结果，科研δ为空。内部方法问题和一般用户Compute准入尚未解决。


[工程机器记录](../validation/user-molecule/budget-recording-20261007.public.json)提供测试、示例、身份及文件hash；[候选合同0.2](../validation/user-molecule/residual-diagnostic/budget-recording-candidate-v1.public.json)记录实施状态，原设计字节单独保留。下一步应针对既有近简并占据证据继续内部方法/服务范围设计；不自动进行新的分子计算，不把新工程候选接入现有科学worker。
