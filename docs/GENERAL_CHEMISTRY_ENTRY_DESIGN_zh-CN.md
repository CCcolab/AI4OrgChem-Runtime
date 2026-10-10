# 面向用户分子的本地化学计算入口设计

2026-10-08，定位修订0.2。Runtime按用户研究操作组织，用户无需先理解专著P01—P14。首批“自己的XYZ → 普通RHF单点 → canonical轨道/AO密度 → 本地报告”已实现并完成限定范围验收；优化、扫描等扩展仍分开登记。此前0.1设计保存在Git历史，不改写旧固定案例身份或科学结论。

## 1. 用户路径与现有范围

**准备自己的分子 → 选择受支持任务与方法 → 输入和资源准入 → 本地执行 → 查看并保存记录**。普通计算无需专有两片段、xy定向、条件态确认或P编号。[四步指南](MOLECULAR_SINGLE_POINT_zh-CN.public.md)为当前主要操作入口，[首版合同](MOLECULAR_SINGLE_POINT_ACCEPTANCE_CONTRACT_zh-CN.md)给出完整门槛。

“通用”指用户可提交支持范围内的自选结构，逐profile扩大任务；不表示所有元素、方法、分子规模均已支持。当前profile为 `rhf-631gd-small-v1`：H/C/N/O、中性单重态、正偶电子、1—20原子、实际AO≤80、严格XYZ/Å、RHF/6-31G(d)。三维非平面结构可用，输入原字节、原子顺序和坐标保持。几何检查不是化学合理性认证。

| 用户功能 | 已交付或待办 | 用户获得的结果与边界 |
|---|---|---|
| 普通分子输入与资源准入 | 已实现/测试；4个真实小分子和实际AO超限拒绝已执行 | 格式/方法/profile检查，原子映射；超限SCF前拒绝；不是独立原子连接或几何认证 |
| 普通单点能量 | 首版RHF本地Docker验收通过 | 能量账本、SCF状态、12项数值检查、单位和运行身份；用户可用自己的合格XYZ |
| canonical轨道与AO密度导出 | 随合格普通单点已实现/验收 | 轨道能级、系数、占据、S与自旋求和AO密度；无网格、等值面和用户局域化 |
| 分子图和常用描述符 | 通用输入/服务待实施 | RDKit固定图示例已通过；不等于任意SMILES/SDF图服务 |
| 通用几何优化 | NOT_IMPLEMENTED / NOT_EXECUTED | 需独立优化器、导数、端点和资源验收；旧固定P14优化记录不转移 |
| 扫描、批量比较、DFT、开壳层等 | 后续独立待办 | 各自冻结支持范围、预算和验收，不静默扩展当前profile |

化学键与电子结构研究是能量、轨道、密度和结构分析的应用场景。计算输出及方法近似不能宣称实验微观测量，也不自动产生化学稳定化分类。

## 2. 请求、实现与独立资格

新请求 [molecular-single-point-v1](../schemas/molecular-single-point-v1.json) 和 `runtime.molecular_service` 不复用旧条件态请求中的片段/定向/屏蔽规则。启动器为 [start-molecular-service.ps1](../scripts/start-molecular-service.ps1)，与原Check/Report/固定Run入口并存。任务 `single-point` 的canonical轨道和AO密度是绑定同一合格端点的输出，没有单独开放 `orbital-density` 或 `molecule-properties` 命令。

普通SCF直接复用锁定PySCF，Runtime负责输入、资源、调用预算、输出资格和身份核查；不另造普通SCF算法。单任务1CPU/1线程/1GiB、100秒软停止/120秒硬期限、至多1次RHF kernel，没有自动重试、方法切换或恢复。原生C扩展停止能力和缺失尾检必须按实际状态记录。

状态分别登记：

- **普通单点**：`PASS_LOCAL_ORDINARY_USER_MOLECULE_SERVICE_RHF_PROFILE_ONLY`。
- **旧用户分子条件态比较**：`BLOCKED`，原规则、固定点/占据/正能隙门槛、失败记录与139次OPEN账本保留。
- **其他计算扩展**：分别实施验收。底层库有接口不等于Runtime已提供服务。

旧 `compute_enabled=false` 继续用于关闭条件态Compute；新能力登记使用独立 `ordinary_single_point_enabled=true`，不打开旧路径。

## 3. 成熟生态与当前复用

普通闭壳层RHF采用PySCF；DFT和开壳层需后续profile与真实验收。[PySCF SCF文档](https://pyscf.org/user/scf.html)

固定图示例复用RDKit；通用图任务将另查键阶、氢、价态和立体信息，XYZ不提供可靠连接与键阶。[RDKit文档](https://www.rdkit.org/docs/GettingStartedInPython.html)

几何优化器依赖与许可、导数和端点尚未部署，不沿用历史Docker通过结论。[PySCF优化接口](https://pyscf.org/user/geomopt.html)

QCSchema字段适配仍为后续增强。首版保持项目JSON与明确单位/原子映射，不部署云调度、服务器、训练或预测平台。局域化和网格可视化分别另立合同，不追加本轮工作。

## 4. 本轮实施和验收对应

| 步骤 | 交付及实测 |
|---|---|
| 冻结输入/任务合同 | schema、profile、依赖和20项关键源码锁；拒绝未知键、单位/路径/规模越界 |
| 单点适配 | 仅普通RHF；持久一槽调用账本、持有的原生守卫和资源记录；条件NR/局域化调用为0 |
| 数值/导出 | 12项数值检查、能量账本、AO映射及NPZ/报告哈希与结果绑定 |
| 小体系实测 | 水、三维甲烷、三维氨、乙烯各1次正式RHF＋各1次同库直接RHF，共8次；4组必要比较均通过 |
| 完整运行 | 非root、只读源码/输入、断网、资源、退出码、容器删除及输出保留通过；实际AO112>80在SCF前拒绝 |

镜像内114个独立工程用例通过、0skip、0科学调用；宿主97个新服务用例中96通过、1真实symlink夹具未执行，该项已在Linux候选补执行。直接调用使用同版本PySCF，只验证包装一致性，不是独立科学引擎认证。SCF收敛及数值资格不证明稳定极小态；波函数稳定性为NOT_EXECUTED。原失败启动和退出码观察更正保留在[实际验收报告](MOLECULAR_SINGLE_POINT_ACCEPTANCE_20261008_zh-CN.md)。

## 5. 交付、发布与历史材料

`35a1817`固定案例交付和镜像保留；新普通候选基于干净 `1f139aa` 构建，实际宿主运行身份为 `a3f6ec7`，完整镜像ID和结果哈希见[机器状态](../validation/molecular-service/deployment-20261008.public.json)。后续文档提交与构建/受测身份分开，不冒充镜像重建。

P01—P14继续作为示例、验证及来源详情，不是新普通服务的必读目录。Git/项目ZIP是源码材料，不含Docker镜像和完整依赖安装环境。本机已具备受测候选，不等于其他机器仅下载源码即可运行。
