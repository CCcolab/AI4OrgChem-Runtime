# 最小公开数值见证 / Minimal numerical witnesses

此目录从已有运行提取两个小型数值见证，使读者能用 **Python 标准库＋NumPy** 亲自复核矩阵身份、电子数、幂等性、算子装配、能量账本和 gap。复核不启动 Runtime 容器，不执行 SCF、积分、格点、ERI 收缩或新的 F(D) 回调。它验证保存的数据及判读，不能代替完整科学服务或平台验收。

| 见证 | 原方法与几何 | 提供的数据 | 可以复核的范围 |
|---|---|---|---|
| [ordinary-water](ordinary-water/result.json) | 用户指定水分子几何；普通闭壳层 RHF/6-31G(d) | 原字节 XYZ、request、result、8 成员 NPZ、host manifest、镜像身份 | 10 电子、轨道与密度一致性、白化投影幂等/对易、F=h+Vhf、能量闭合与保存 gap |
| [conditional-ethene-v2](conditional-ethene-v2/snapshot.json) | 保存的乙烯条件诊断；B3LYPG/STO-3G、原 grid level 2、登记跨片段 π 条件 | 返还密度对应的 S̃、h̃、D、F̃、未投影 G、J/K/Vxc、删除 mask，以及精确绑定的原 AO S/h；共 11 个成员 | 返回密度与真实评估身份、条件/原 AO 电子数、幂等/对易、矩阵装配与账本闭合，重现端点拒绝 |

## 只读复核

从仓库根目录执行：

```console
python -B scripts/audit-numerical-witnesses.py
```

审计以 `allow_pickle=False` 读取 NPZ，递归检查成员的 shape、dtype 与 C-order 字节 SHA-256，先核对文件大小和哈希及仓库内公开父记录，再复核数值。导入守卫拒绝 `pyscf`、`ai4orgchem`、`rdkit` 和 `scipy`。已在 NumPy **2.4.6** 实测，原计算使用的版本保留在原 result／来源清单中。

审计退出 **0** 表示保存见证与预期判读一致；条件见证的 `endpoint_qualification` 仍为 **REJECTED**。损坏或错配返回 **2**。这是只读证据复核动作的合同；不能把其退出 0 解释为条件 Compute 合格。负例只修改临时副本，覆盖文件损坏、成员 shape/dtype/hash、重写哈希后的密度/能量/算子错配、父记录错配、路径越界和对象数组拒绝。

## 已保存端点的判读

本次只读观察见 [AUDIT_RESULT_PUBLIC_20261010.json](AUDIT_RESULT_PUBLIC_20261010.json)。不同 NumPy/BLAS 环境可能产生末位差异。占据空间与保存密度的复核不能自动认证全部 canonical／虚轨道资格；当前范围见[普通分子使用指南](../../docs/CURRENT_MOLECULAR_SINGLE_POINT_zh-CN.md)。

| 量 | 原保存值 | 本次 NumPy 复核 |
|---|---:|---:|
| 普通水分子总能量 / Eh | −76.00909910859735 | −76.00909910859733 |
| 条件密度 Tr(S̃D) | 15.999999999999977 | 15.999999999999977 |
| 原 AO 度量 Tr(SD) | 16.47453645981215 | 16.47453645981215 |
| 条件总能量 / Eh | −77.60960002409465 | −77.60960002409465 |
| 条件 gap / Eh | 2.67841304690819×10⁻¹⁵ | 2.831068712794149×10⁻¹⁵ |
| 条件 Aufbau 映射相对残差 | 0.42980285975005655 | 0.4293207349737057 |

原 gap／映射由 **SciPy 广义本征求解**形成；这里用 NumPy 对 S̃ 做对称白化，再对保存 F̃ 求本征值。近简并时选取的占据子空间可能不同，所以两套数字分列；没有声称精确重建原 SciPy 的轨道或映射。保存的 gap 门槛为 `1e-6 Eh`，映射残差门槛为 `2e-8`；本次两项仍失败。对易残差约 `1.889e-9`、幂等相对残差约 `4.478e-15` 的通过不能替代这两项。

矩阵装配复核使用原定义：`G = h̃ + J − 0.1 K + Vxc`，随后在保存 mask 的位置将 G 置零得到 F̃。能量为 `Tr(Dh̃) + 0.5 Tr(DJ) − 0.05 Tr(DK) + E_XC + E_nuc`。`E_XC` 保留已保存的标量；没有重新积分，也没有用 `Tr(DVxc)` 冒充 XC 能量。原格点电子数 `16.47453733917221` 同样仅为保存标量，不在此包中重新积分。

这些结果保留条件功能式与度量的区别。不能把条件能差直接解释为物理键能；失败端点不证明合格根不存在，也不证明驻定、稳定极小态或推翻原项目全部 P01—P14。普通 RHF 见证仅覆盖该指定几何与包装数值一致性；波函数稳定性仍未执行。

## 来源与派生身份

[manifest.json](manifest.json) 逐一登记载荷的来源 bundle、相对路径、原字节哈希、父证据、源／Runtime 提交、镜像身份、成员哈希、派生哈希及缺失项。普通水分子文件为 **ORIGINAL_BYTES**，可与原结果与原 host manifest 的字节哈希直接比较。条件 snapshot／NPZ 为明确标注的 **DERIVED_SELECTED_FIELDS / DERIVED_SELECTED_MEMBERS**；原始结果哈希识别未复制的原件，不是此派生文件的哈希。派生文件不含个人 Windows 绝对路径。

普通见证绑定 [deployment-20261008.json](../../validation/molecular-service/deployment-20261008.public.json) 中的 water result／host manifest。条件见证绑定 [seed-v2-20261007.json](../../validation/user-molecule/seed-v2-20261007.public.json) 的原 result 与原 gate，并核对 [local-runtime-framework-20261007.json](../../validation/local-runtime-framework-20261007.public.json) 中密封交付 manifest 的 SHA-256。原 AO S/h 从 V2 已声明的 ordinary cache 精确字节身份抽取，未生成新积分。

条件包选择 `true_evaluation_at_returned_density`，同时核对 solver 返回密度、评估请求密度、保存密度成员与域分隔 density ID。没有以最后回调、试探密度或相近密度替换它。完整回调历史、ERI、格点、日志和完整容器验收材料不在此最小包内；哈希联系本地字节与已登记声明，不提供引擎真实性认证。

[extract.py](extract.py) 保留提取过程，可接受三个原始证据目录参数 `--water`、`--seed`、`--ordinary-cache` 来重建此子集。它使用相同导入守卫，提取后回验 **13 个原文件**的 SHA-256 未变；不修改原件。默认审计命令不需要这些私人目录。新提取需持有原件，应使用独立 `--package` 输出目录。

English: These are saved-array witnesses, audited with NumPy only. Audit success confirms byte bindings and the recorded interpretation, including rejection of the conditional endpoint. Derived subset hashes are distinct from original source hashes. No SCF, integrals, grids or new F(D) evaluation is performed; stability, method validity, root existence and physical bond energies are not established.

当前三个公开父记录是明确标注的 `.public.json` 摘要，原记录按原字节保存在本地历史归档；manifest 同时登记公开摘要与原件的不同哈希。八个数值载荷保持原字节。公开摘要不是原始执行日志；当前复核仍按原门槛拒绝条件端点，不转移历史验收。

原 test_numerical_witnesses.py 及对应回归记录保留在维护者本地，不属于当前公开 tests 分发。外部读者使用上方已存在的只读审计命令；其成功不授予条件端点资格。
