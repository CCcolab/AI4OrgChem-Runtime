# 最小分子准备、独立参考与持久化预算

2026-10-06。本轮补齐固定 pilot 乙烯的准备映射、独立残差参考和持久化资源记账。**97 个唯一用例形成按版本核对的通过覆盖**，其中 72 项新增、25 项既有资源回归；它们来自三份源码版本的实际记录，不是一次 97 项完整 CI。真实 PySCF 缓存对象与既有普通态记录的映射通过；新的普通/条件 SCF、积分、格点、真实 XC 和核能求值均为 0。机器记录见 [本轮验收](../validation/user-molecule/preparation-reference-20261006.public.json)。

## 准备入口已补齐什么

[residual_preparation.py](../runtime/user_molecule/residual_preparation.py) 复用严格 request/schema/XYZ 读取，首批只允许已登记的 `ethene-planar-technical-v1`、pilot STO-3G/B3LYPG/grid2 设置，14 AO、16 电子。它没有放开任意用户分子，生产 Compute 开关仍为 false。

准备层核对原子顺序、元素、显式 Angstrom 坐标和固定 xy 定向，允许单位往返的工程误差仅 1e-12 Å；不旋转、拟合、平移或重排。还核对完整基组表示、实际 AO 标签与独立奇偶/分片分类、普通设置、grid 算法与数组、以及同一完整 ordinary JSON/NPZ 的六个成员。

共同 D0 选自旧 `ordinary-reference.json`／`ordinary-reference.npz`，密度数组哈希为 `9dc813178f17be82f7c231c7b9d0a0494e8d4bcd2acea05ac2605bf3bf268f8a`。旧 `common-D0.npy` 来自生产普通态路径，不能直接配上独立参考的元数据；标量版 `ordinary-tested.json` 也不能代替完整记录。核排斥能从同一记录的 `components_hartree.nuclear_repulsion` 读取，值为 33.23272494899829 Eh，不重新调用核能函数。

本轮实际创建了钉版本 PySCF 的分子/配置缓存，载入原有 density、hcore、overlap、ERI、grid coords/weights。**读取了保存的 ERI，没有生成新 ERI**。整个进程禁止 SCF、积分、grid build、nr_rks 和真实 Mole.energy_nuc；没有构造或运行真实生产桥。验收证明缓存、原子/AO/基组、设置和记录对应，不能独立认证旧数组的物理正确性。

## 旧基组表示的受限兼容

旧普通态元数据用 `sha256(repr(mol._basis))` 记录基组，C/H 顶层字典顺序也会影响摘要。第四次实际核查中，仅此字段不同：新建表示哈希 `397234c7…`，旧记录为 `beb6928d…`。

新增显式 `restore_legacy_basis_representation`，只枚举固定 C/H 两种顺序。完整 repr 必须有且仅有一项精确恢复旧哈希；所有其他 metadata 必须相同。完整标量/list/tuple 内容、子对象、native `_atm/_bas/_env`、坐标和 AO 标签前后均须不变。会截断的数组 repr、内容改变、其他差异或未命中旧哈希都拒绝。只重排顶层字典，并从实际对象重新计算该字段；旧记录不修改。

实际旧哈希被精确恢复，两种同值顺序也作了受控核对。这是 **legacy representation compatibility**，不是修改数值基组、放宽科学容差、重新验收基组来源或认证引擎。第三次只保存了 metadata 不一致的拒绝，没有保存具体差异，不能追溯宣称第三次已观察到同一原因。

## 独立参考已实现及其限制

[reference/residual_candidate.py](../reference/residual_candidate.py) 使用 SciPy TRF、三点数值 Jacobian 和局部轨道图重定位。它独立实现初始化、迭代、预算和资格判读，不调用生产求解器/gate，也不导入 runtime 或 ai4orgchem。[reference/residual_molecule.py](../reference/residual_molecule.py) 复用已有独立数组 mask/J-K/能量实现和原格点 XC 闭包，提供完整 prepared-data 适配；不自动跑普通态或生成积分。

初始化必须显式指定，初始 2/0 流形、首次 raw 全局 Aufbau 和近简并拒绝同属候选工程定义。真正 nr_rks、差分、试步、失败以及返回/映射密度重查全部纳入每路径 ≤201 次上限，不能用 SciPy 的 nfev 代替真实回调数。结清后不可再 run 或 evaluate。原子/基组/单位缓存、原数组、格点和方法设置在回调前后冻结。

参考共享 PySCF 原始积分、XC 和 NumPy/SciPy；这部分没有独立验证。不同策略不要求轨迹、MO 符号或 SciPy 终止文案相同；各端态必须先通过原 commutator、电子数、幂等、mask、闭合、raw-Aufbau 与 gap 门槛，再核对密度/占据态和能量。旧 T05、T06、P12/P13 阈值完整保留在 [候选合同](../validation/user-molecule/residual-diagnostic/contract-v1.public.json)。

**已验证一个明确算法限制**：取 `F=[[0,1],[1,0]]`、`D=2u(θ)u(θ)ᵀ`，占虚残差为 `cos(2θ)`。θ=0 时残差为 1，而残差平方的一阶导数为 0；TRF 可满足 gtol 后停住。实际记录 nfev=1/njev=1，但回调为 5 次；AO commutator≈2.8284、raw-map 相对残差≈1，原门禁拒绝，不能标合格根。它不证明固定点不存在，也不是乙烯实测反例。另从 θ=-0.1 出发仍超出初始 .25 图范围，验证多图重定位到已知合格 toy 根。

新独立参考已实现并通过假后端/数组对照，**真实分子条件验收 NOT_EXECUTED**。旧 v2 完整分子参考仍是“已实现且执行失败”，不能改写为未执行。

## 持久化预算与具体候选方案

[residual_budget.py](../runtime/user_molecule/residual_budget.py) 复用既有 wall Budget 的锁和完整性格式。单进程预约原子地限制一次尝试，即首次结清 wall=0 也不能再预约。新的回调账本在进入适配器前预收费，失败、崩溃和关闭路径都不退款，重开不能改身份或清零额度。

预收费 slot 是保守资源计数，**不等于实际 F/XC 次数**：例如适配器在来源核查时拒绝，可消耗 slot 而实际 F 次数仍为 0。实际来源尝试由桥/参考分别报告。外部监督器仍须执行 CPU/内存/时间限额；账本不证明授权，也不单独执行 cgroup。

已登记的最小真实诊断候选方案如下，尚未运行或创建其科学预约：

| 项 | 候选合同 |
|---|---|
| 普通态准备 | 复用完整既有缓存，只重建配置/核对，不重算普通 SCF、格点或积分 |
| 执行进程 | 单个串行进程，900 秒、1 GiB、1 CPU、零 swap；不自动重试 |
| 三条路径 | COPY_MASK/优化收缩；INPLACE_OWNED/非优化收缩；独立参考 |
| 条件预算 | 每路径 201，初始化含在内；三路径预收费总上限 603 |
| 科学判读 | 不授予研究范围、变分最小性、唯一根或能量解释；初始歧义可直接拒绝 |

INPLACE_OWNED 仍保留物理 ERI 与自有工作副本，不称为真正整个流程单张量。toy 时间和 512 MiB 工程执行不构成 1 GiB 科学方案资源验收，也不外推到更大基组或一般用户分子。

## 实际测试、失败及版本关系

| 最终采用的覆盖 | 数量 | 实际源码 |
|---|---:|---|
| 准备层 | 26 | eba5b17，旧函数 AST 与最终源码相同 |
| 独立数组/完整 prepared 参考 | 14＋12 | eba5b17，最终 Git blob 相同 |
| 新持久化预算 | 12 | eba5b17，最终 Git blob 相同 |
| 既有资源回归 | 25 | eba5b17，最终 Git blob 相同 |
| 修正后的集成发现/接线 | 4 | faabf22，最终 Git blob 相同 |
| 新基组表示兼容 | 4 | 82436e4 |

三份版本共 97 个唯一用例，选入覆盖均无失败/错误/跳过。实际执行过程完整保留：

1. b02139c：26 项准备通过，13 项参考中一项错误预期失败。后来保留原初态作为拒绝反例，另设多图进展初态；未改算法、门槛或预算。
2. eba5b17：119 次单元执行、93 个唯一用例全部通过，但直接导入另一个 TestCase 导致 26 项重复发现，汇总拒绝；后续缓存核查未执行。不能称完整成功。
3. faabf22：仅重跑受影响集成 4 项，通过；另保存三路径 12 次假 nr_rks／12 slot、0 pending、三路径 closed 的持久化演示。缓存元数据不一致，整轮仍 FAIL；未重跑其余 89 项。
4. 82436e4：仅新增表示兼容 4 项，通过；真实旧缓存映射、受控另一字典顺序和纯数组非根驻点证据通过。新科学调用仍 0。

4 个容器各为 1 CPU、512 MiB、120 秒上限，UID10001、network none、只读 rootfs/源码、独立 output leaf；均删除、输出保留。外部 wall 预约在启动前写入，退出、日志收集及删除后实际结清，总约 58.392 秒；失败时间也计账。原 runtime 桥与科学源保持原字节，不重建镜像。最终代码 82436e4，镜像仍 r3 `24f46f…`、构建 runtime 5098775、science cc743790／基线28511f3，分别登记。

41 个既有产品文件、591 个科学文件、旧失败目录32项，以及此前537/560/288项登记交付保持字节。四份源码导出逐项核对 Git blob，PowerShell 换行转换单列；未登记历史不作新保证。此前176项完整CI没有重跑，远端 Actions仍 NOT_EXECUTED。

## 当前边界与下一步

本轮已补齐准备映射、独立参考及资源记账工程，和具体受限诊断候选合同。下一步才是绑定新的受测源码/实际 image/旧缓存身份，执行实时资源准入，建立新鲜科学预约，再进行单次候选条件诊断；不得把当前工程或缓存结果升级为科研资格。方法定义/外部一致性咨询仍按用户指示延期。


所有初次失败、来源归档、持久化账本、兼容证明和最终核查保存在 `D:\AI4Science\ai4orgchem-runtime-deliveries\20261006-user-molecule-preparation-reference`。
