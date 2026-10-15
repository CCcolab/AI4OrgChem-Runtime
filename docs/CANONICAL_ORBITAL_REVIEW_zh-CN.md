# 完整 canonical MO 的附加只读审查

新工具不修改 `runtime/molecular_service/engine.py`、旧端点门槛、来源锁或历史结果，也不自动接入任何生产启动器。它只审查已保存数组。

宿主只需已有 Python 和 NumPy；缺依赖时说明缺口，不自动安装或转入容器计算。

```console
python -B scripts/review-canonical-orbitals.py --npz evidence/numerical-witnesses/ordinary-water/orbitals-density.npz --electron-count 10 --output /path/to/new-orbital-review
```

将输出路径替换为全新目录；已有目录拒绝且不追加记录。NPZ 使用 `allow_pickle=False`，数组字段为 `overlap`、`canonical_coefficients`、`orbital_energies_hartree`、`occupations`、`fock`，可附 `density`。缺必要数组、维度/有限性异常或超阈值都不能得到完整轨道 PASS。

版本化策略见 [canonical_mo_policy_v1.json](../review_tools/canonical_mo_policy_v1.json)。输出同时列 `endpoint_numerical_qualification`（未由本工具重验）、`full_orbital_qualification` 和 `wavefunction_stability`（未执行）。正交性为完整 `||C†SC−I||F` 无量纲绝对残差；本征方程为完整 `||FC−SCε||F`（Eh），另列白化相对残差。完整阈值、归一化分母、单位和工程依据均随结果保存，不使用默认相对容差。

本策略要求闭壳层 2/0 占据、电子数、轨道能排序与列索引相容；近简并只按明确的排序容差处理，不借本工具更改旧占据或能隙规则。它不是适用于任意电子态的新科学协议。通过仅表明输入数组满足该附加策略，不能升级旧软件门槛、方法适用性、稳定性或新环境验收。

公开回归含“占据列及密度正确、虚轨道为 [7,7]”的反例：旧 v1 数值标志仍为 True，新完整轨道审查必须拒绝。保留旧行为使历史记录可解释，不将旧 PASS 静默重新计算。退出 0 仅为附加保存数组 PASS；拒绝或未执行返回 2。
