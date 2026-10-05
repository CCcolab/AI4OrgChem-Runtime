# 用户分子 W05：验收准备与实际检查

2026-10-05 / W05-PREPARATION-1。W05 的输入、配置身份、判据登记、独立参考设计和候选预算已整理；数值验收仍 NOT_EXECUTED，Compute 仍 BLOCKED。本轮没有 SCF、优化、能量或研究分类结果。不能把本页的准备完成称为 W05 完成。

后续 [本地 CI 增补](USER_MOLECULE_CI_20261005_zh-CN.md) 已验证受测工程/准备合同；下述准备批原始记录不覆盖，科学验收及远端 GitHub Actions 状态仍未执行。

后续 [W06 工程记录](USER_MOLECULE_W06_ENGINEERING_zh-CN.md) 已实现部分共享的独立数组参考、资格判读与短简报候选。本页以下及 w05 JSON 保留准备时事实；普通独立驱动、完整分子验收驱动、资源/数值与方法范围仍未闭合，Compute 继续关闭。

## 1. 已完成的低成本检查

| 候选输入 | 两个碳 π 组（XYZ 从 1 编号） | STO-3G / grid 2 nAO | 6-31G(d) / grid 3 nAO | 实际结果 |
|---|---|---:|---:|---|
| ethene-planar-technical-v1，C2H4 | A=[1]；B=[2] | 14 | 36 | 两次 Check 均退出 0；资格 false |
| butadiene-p08-G-fixed-v1，C4H6 | A=[1,2]；B=[3,4] | 26 | 68 | 两次 Check 均退出 0；资格 false |

四次检查均使用 1 CPU、1 线程、512 MiB 硬限额与相同总 memory-swap、60 秒限时、非 root、只读输入/软件及 network=none。容器删除后宿主输出保留；命令、退出码、输出清单与哈希已核对。[检查索引](../validation/user-molecule/w05/inspect-review.json) 指向实际运行目录。Check 的 512 MiB 是本轮元数据检查限额，不代表科学计算所需内存已确认。

另用四碳元数据夹具检查 research 配置：56 nAO，16 个 π AO，其中 8 个 d π AO 为 xz/yz。SCF、grid build、完整/逐壳 ERI 调用均设守卫，未触发。这证明本次受测基组的分类与有效设置可检查，不证明 SCF 正确、资源足够或 research 合格。

## 2. 输入来源与用途

乙烯坐标由明确的测试参数构造：C—C 1.34 Å、C—H 1.09 Å、H—C—C 120°。它是固定解析几何，不是实验数据、优化端点或文献参考；将两个碳分成 π 组只是技术控制，不据此称条件能量差为键能。

丁二烯只复用固定上游 `evidence/P01-P14/P08/result.json` 的 `/ground_geometry/atoms`，并核对调用脚本中的 Å 单位。XYZ 保留原子顺序、浮点坐标与约 1e-14 Å 的 z 值，未旋转、投影或优化。原 P08/GL2014 能量和分类不能作为本次 P09 条件定义的 expected。它不是新获得的几何；是否满足合同“至少两个新体系”的要求须由 B01 核对，必要时另选第二体系，不能自动记为达标。

候选字节、来源 SHA、原子映射和四份请求已保存于 [夹具登记](../validation/user-molecule/w05/candidate-fixtures.json) 与 [候选输入目录](../examples/user-molecule/w05-candidates/README_zh-CN.md)。固定文件字节不等于批准科学适用性。全部 expected_energies 为 null。

## 3. 运行身份与配置审阅

| 对象 | 固定身份 |
|---|---|
| 本轮宿主启动器/准备基线 | `55726d4ee0f76dee5065f47fc5f55824b0083db3` |
| 实际镜像构建 runtime | `5098775c9cf40468ab92712447a3e5c7b1361a63` |
| 科学包及适配器 | `cc7437901119e71ef7945a12813c021c383e7648` |
| 实际候选镜像 | `sha256:24f46f33264924e5d3d3bec386298585267c6f30d6e6a0cd0a6486ecf45db93d` |

本次新增文档提交不作为镜像构建身份，也不作为此前四次 Check 执行代码身份。旧 W01—W04 记录完整保留；其中 research inspect 未执行是当时的历史状态，当前增补证据在 w05 子目录。

[配置登记](../validation/user-molecule/w05/profile-register.json) 同时保存宿主原始快照、Git blob、构建归档和实际镜像 profile SHA。两份 JSON 分别逐字节确认 host CRLF→Git/build LF 后相等，并通过实际 preflight 验证镜像哈希；设置未改。禁止把不同字节的哈希混成同一身份。

新快照目录内的 `.gitattributes` 仅将这两份快照标为不做 text 转换，以保持登记的 CRLF 原始字节可在归档/检出后校验；生产 profiles 和原有根目录规则不变。

两个 v1 profile 均为 B3LYPG、闭壳层、Å、球谐 AO；无 ECP、密度拟合、溶剂、额外色散或未登记 NLC。普通态初猜、DIIS、阻尼、积分设置、网格剪枝和有效 XC 系数已记录；PySCF 2.14.0、NumPy 2.5.1、SciPy 1.18.0 继续固定。PySCF max_memory=512 MB 是库设置，不能当作整个容器的硬上限。配置快照保存全部候选设置；数值适用性仍待审。

## 4. 判据与缺口

[19 项判据登记](../validation/user-molecule/w05/criteria-register.json) 记录公式、单位、来源、实现位置与状态：

| 分类 | 登记内容 | 状态 |
|---|---|---|
| P01—P05 | 普通态 1e-9 Eh、原生轨道梯度约 3.1623e-5、最多 100 cycles；条件密度 2e-8、能量 1e-9 Eh | 沿用候选；新体系数值验收未执行 |
| P06—P11 | 电子数 1e-7、闭合 1e-9 Eh、对易子 1e-5、幂等性 1e-7、禁块 1e-12、S̃ 最小特征值严格 >0 | 原核/适配器有检查；未获推广资格 |
| P12—P13 | 两存储路径 ΔE≤1e-10 Eh、密度 Frobenius≤1e-9 | A07 原有候选；验收驱动尚未实现 |
| T01—T03 | 近碰撞、S̃ 条件数上限、小 gap/简并策略与 gap 算子来源 | null；通用拒绝门禁或所需记录尚缺 |
| T04—T06 | 独立普通态、固定 D 逐算子/分量、完整条件参考的逐字段容差 | null；参考尚未实现 |

密度收敛使用 `||Dcandidate-D||F/max(||Dcandidate||F,1)`；幂等性使用 `||DSD-2D||F/max(||D||F,1)`。普通态采用 S，条件态采用 S̃。P02 是 PySCF 轨道梯度约定，不是核坐标梯度。现有 gap 来自最后对角化，可能使用 DIIS F；不能称为最终重建 F 的能隙。首轮未定义能量变化须为 null+reason，不能补零。

T01/T02/T03 的保留字段即使填数字也不会自动形成已验证门禁。开启前必须实现、测试并记录。结果中 metric_id、公式/阈值版本、required/diagnostic、operator_source 等完整合同字段也仍待补齐。当前不修改科学方程、占据策略或容差。

方法来源见 [来源索引](../validation/user-molecule/w05/source-index.json)。[PySCF 分子文档](https://pyscf.org/user/gto.html) 用于核对单位/基组 API；[NumPy cond](https://numpy.org/doc/stable/reference/generated/numpy.linalg.cond.html) 定义条件数，不提供本项目拒绝阈值。[PySCF 稳定性说明](https://pyscf.org/user/scf.html#stability-analysis) 支持区分收敛与稳定性；本项目 stability 仍 NOT_EXECUTED。

## 5. 独立参考与预算提案

[参考设计](../validation/user-molecule/w05/reference-plan.json) 分为 R01 普通 RKS 独立驱动、R02 toy/固定 D 的逐算子与五分量对照、R03 两生产存储路径、R04 小规模完整独立条件固定点、R05 映射/组互换/失败控制。参考可读取固定十五类 YAML 作为数据，禁止调用被测 AO 分类、ERI 屏蔽、能量与条件核作为数值预言机。共享 PySCF 原始积分/XC和线性代数库的盲区必须报告。旧回归测试与两存储路径一致均不替代完整独立参考。

BLW、ALMO、NBO、cDFT 属于科学解释对照路径，不作为同定义数值等价门禁，本轮未新增这些工具或外部计算。

[资源提案](../validation/user-molecule/w05/resource-budget-proposal.json) 延续既定候选上限：标量参考≤40 nAO/1线程，普通与路径比较≤80 nAO/最多2线程；单进程≤4 GiB、900秒；单批子进程累计≤7200秒，串行并沿用共同锁。它是待审的上限提案，不是运行授权、预计耗时或充分资源证明。

首批提案仅 pilot、两夹具：2 个独立普通态进程、2 个单张量两态进程、2 个参考复制两态进程、2 个固定 D 参考进程；最后两进程各≤600秒，其他各≤900秒，合计预算6600秒，余量600秒。失败、重试、校准均计入同一批累计，禁止用重启重置计时。research 科学批次需另行审阅，不能顺延第二份7200秒额度。

`8*nAO^4` 是一张 float64 ERI 下界；复制模式两张 float64 加 bool 张量仅为 `17*nAO^4` 的张量存储下界，均不是完整峰值。需实际测量 cgroup峰值、RSS、格点、阶段、临时量与 tmpfs，再验证边界或限定到原样受测夹具；资源模型、最大 Compute nAO 仍 null。research 丁二烯68 nAO 超出标量参考40上限；乙烯36 nAO可作小参考候选，不自动提高上限。[Docker 资源说明](https://docs.docker.com/engine/containers/resource_constraints/) 用于核对硬限额和 swap 语义，不能替代峰值实测。

## 6. 下一阶段出口

用 [决策单](templates/USER_MOLECULE_W05_DECISIONS_zh-CN.md) 处理 B01—B07，批准的科学范围和预算写入可追溯记录。先完成独立参考/验收驱动与缺失门禁、冻结逐字段容差、共同初始 D 生成方式、有效 profile 与代码身份，再执行预算内 pilot 数值/资源验收。采用新的 acceptance-only 身份，不翻转生产 v1 的 compute_enabled。

W05 数值门禁和资源包络闭合后，W06 仍需能量—算子—占据解释、完整独立参考及有限研究范围批准；变分性 NOT_ESTABLISHED，不能将条件差宣称为普适键能、实验微观测量或任意分子服务。

WSLc BLOCKED/暂停，Colab DEFERRED，CI 实跑 NOT_EXECUTED，镜像分发 BLOCKED；未推送、打正式标签或发布。本轮不重建镜像、不重复旧 L3/L4，不升级 WSL；原 L4 可保存检查点但不支持恢复。
