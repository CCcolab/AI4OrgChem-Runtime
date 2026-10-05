# 用户分子计算服务：完整技术方案与实施步骤

后续实施状态：W01—W04 工程候选和低成本检查已实际形成；本文 TECHNICAL-PLAN-1 描述设计当时的状态与合同，当前实现、镜像和未完成事项按 [交付记录](USER_MOLECULE_W01_W04_DELIVERY_zh-CN.md) 与 [用户指南](USER_MOLECULE_RUN_zh-CN.md)。新分子 SCF、W05/W06 及研究资格仍未执行或批准。

日期：2026-10-05；TECHNICAL-PLAN-1。用户已明确同意进入实施阶段，工程范围准入记为 APPROVED_FOR_IMPLEMENTATION；新服务仍 NOT_IMPLEMENTED，新增构建/计算/验收 NOT_EXECUTED。科学方法复审、完整 profile、资源校准和研究范围批准保持各自状态，不能用工程批准代替科学资格。

本轮交付技术方案，后续按下述步骤实施；本轮未执行新代码、镜像构建或分子计算。依据：[专业实施方案](../ai4orgchem-runtime-implementation-plan-professional-revised.md)、[设计与 A01—A18](USER_MOLECULE_ENTRY_DESIGN_zh-CN.md)、[本地实施细则](USER_MOLECULE_IMPLEMENTATION_DETAILS_zh-CN.md)、[C01—C06](USER_MOLECULE_ENTRY_SCENARIOS_zh-CN.md)、[条件核与参考合同](USER_MOLECULE_CONDITION_DEFINITION_zh-CN.md)。接口、目录和错误码为拟实现合同，实际代码尚不存在。

后续准备记录 LOCAL-SETUP-1（2026-10-05）：用户要求先建立本地目录并保存最新文档；已建立目录占位，实际路径见 [目录说明](USER_MOLECULE_DIRECTORY_LAYOUT_zh-CN.md)，技术分工见 [步骤对应表](USER_MOLECULE_DESIGN_STEP_MAP_zh-CN.md)，当前材料见 [文档索引](USER_MOLECULE_DOCUMENT_INDEX_zh-CN.md)。W01 仍 IN_PROGRESS，隔离 Git 工作区尚未创建，W02—W07 未启动；占位文件不等于新服务实现。

## 1. 首版产品与边界

交付本地 Docker CPU 服务：XYZ + 严格请求 JSON → 检查回执 → 普通 RKS/指定条件态 → 同几何差值与资格 → 简报、JSON、日志和身份账本。Windows 通过 PowerShell 启动器操作，无需安装宿主 PySCF、学习 Notebook 或先读原著全集。

对象限定为受审范围内 xy 平面的中性闭壳层 C/H、两个碳 π 组及固定 profile。C06“面向化学键微观研究的电子耦合与条件态能量分析”复用 C01—C03；核心量为 `Eordinary(R)−Econditional(R)`，不是某根键的唯一能量或实验测量值。研究用途不自动放宽体系范围。

首版不实现：自由泛函/基组、杂原子/离子/开壳层/非平面/多片段、结构生成、通用优化/频率、键级/密度分析、键解离过程、实验成像、扫描/批量、多用户服务器、在线模型调用或恢复计算。Colab、WSLc/WSL 升级及公开发布继续暂缓；L4 可保存检查点但不支持恢复的限制保留。

## 2. 基线和实际代码调查

| 项目 | 当前采用的身份/事实 | 新服务的处理 |
|---|---|---|
| runtime | 0288eb8455a85c2082142dbdc62b7c018adb2e56 | 新实现独立分支/提交；保留 2460eef 与 0288eb8 和所有未跟踪文件 |
| 科学来源 | 28511f3d84fa65707a107cde1e8121a7b4334ecb，v0.3.2 | 隔离科学分支增加适配器/参考；固定核文件保留；新提交不是 v0.3.2 |
| 基础镜像 | 当前 Dockerfile 为 python:3.12.13-slim-bookworm，摘要固定 | 沿用已锁基础，不迁移系统或升级依赖；新候选另有 image ID |
| 数值依赖 | 当前锁：PySCF 2.14.0、NumPy 2.5.1、SciPy 1.18.0；jsonschema 4.26.0、pytest 8.4.2 已在锁内 | 优先复用现有包，无需为输入校验新增整套平台 |
| 旧任务入口 | runtime/cli.py 的 TASKS 固定七项，entrypoint.sh 调用它 | 增加独立 user_molecule 模块入口，不改旧 task ID 或科学比较 |
| 旧源码校验 | verify_source 按现有 source-files.sha256.json 核对完整文件集合 | 新服务使用独立来源锁/清单；不把旧锁覆盖成新能力 |
| 旧启动器 | run-wslc.ps1 需要 PS 7.3；start-runtime.ps1 从 PS 5.1 找已有 PS 7 | 新启动器复用这一引导方式与路径处理；不自动安装/修改全局配置 |
| 旧资源模块 | memory_snapshot 已处理内存 cgroup 层级；thread_limit 处理 affinity 与 cpu.max | 复用内存逻辑，补 CPU 层级/配额与新峰值模型；旧函数不冒充新资源验收 |

以上来自本轮本地静态读取，未探测当前 Docker 是否运行，也未执行科学库。新候选只宣称它实际受测的新服务范围；旧七任务继续引用旧候选，不能因共享文件就称它们在新镜像全部通过。

## 3. 架构与职责

```text
专业用户：XYZ + request.json
             │
Windows PowerShell 5.1 引导 → 已有 PowerShell 7.3+ 宿主监督端
             │  原文件/路径检查、唯一 ID、镜像身份、生命周期/取消、故障落盘
             ▼
新 Docker 候选（非 root、只读、断网、硬限额）
  runtime.user_molecule
     ├─ 严格输入/版本/profile 校验、只读快照
     ├─ 低成本 AO/nAO 检查、资源及方法范围回执
     ├─ 科学适配器（固定 PySCF + 未改条件核）
     └─ 数值/研究资格、原始结果、简报和进度
             │
宿主输出卷 ← 阶段结果/日志 ← 宿主最终 manifest 与校验清单
```

宿主监督者在计算容器的 OOM 域外。计算容器只负责自己的科学输出与阶段进度，不承担被杀后必然写完最终记录的责任。内核、输入合同、执行合同与研究资格分别维护；不把 runtime 变成通用量子化学引擎或 Agent 云服务。

科学适配器置于科学仓库隔离分支，明确调用固定核；runtime 只负责解析、执行和记录。独立参考采用不同实现，不能调用被测 JK、掩码、能量辅助和条件 SCF；共享 PySCF 积分/XC 和 NumPy/SciPy 的边界如实记录。同定义实现比较与 BLW/ALMO/NBO/cDFT 方法解释分开。

## 4. 拟新增文件与复用关系

路径是建议实现布局，尚未创建这些代码文件；可合并职责相近的小模块，实际路径在第一批工程提交冻结。

LOCAL-SETUP-1 已按上述布局预建相关目录；schemas 等未来文件仍不存在，scripts/container/locks 复用已有目录。输入、运行输出、隔离工作区和文档快照分别存于仓库外；具体位置以目录说明和 directory-manifest.json 为准。

| 仓库 / 路径 | 职责 | 关键约束 |
|---|---|---|
| 科学：software/src/ai4orgchem/qm/user_molecule_adapter.py | inspect/compute：Mole、普通态、条件态调用和原始科学结果 | 不复制核、不藏默认值、不读任意可执行配置 |
| 科学：software/tests/test_user_molecule_adapter.py | 输入映射、普通态、控制、不变量与结果映射 | 新测试不替代原核测试 |
| 科学：software/tests/reference_user_molecule/ | 标量、固定密度、完整条件参考及冻结输入 | 禁止导入被测实现；参考范围/预算分别登记 |
| runtime：runtime/user_molecule/__main__.py | check/compute/report CLI | 与旧 runtime.cli 七任务分离 |
| runtime：input.py / preflight.py / records.py（上述包内） | 严格解析、快照、资源/范围回执、结果校验/状态/报告 | 计算资格和研究资格分开；不复写旧结果 |
| runtime：schemas/user-molecule-request-v1.json、result-v1.json、preflight-v1.json | 明确字段、类型、限制与版本 | additionalProperties=false；重复键/NaN 在解析层拒绝 |
| runtime：profiles/user-molecule/*.json | pilot/research 全参数、阈值与启用状态 | 固定数学配置；未知字段不忽略、不静默降级 |
| runtime：scripts/start-user-molecule.ps1 / run-user-molecule.ps1 | PS 5.1 引导、PS 7 宿主监督和 Docker 调用 | 参数数组传递；独立 ID；检查/计算/阅读；不自动安装 |
| runtime：container/Dockerfile.user-molecule | 新服务专用候选 | 固定基础、依赖和新科学归档；不覆盖旧镜像 |
| runtime：locks/source.user-molecule.lock.json、source-user-molecule-files.sha256.json | 科学基线/新提交/归档及文件身份 | 旧 source.lock.json 保留，不捏造新标签 |
| runtime：examples/user-molecule/、tests/test_user_molecule_*.py | 模板、小型夹具、解析/状态/进程/溯源用例 | 不写伪 expected 能量；教学与研究夹具区分 |
| runtime：validation/user-molecule/、docs/USER_MOLECULE_RUN_zh-CN.md | 实际证据和最短用户指南 | 没有真实记录仍 NOT_EXECUTED；当前本方案不生成这些验收结果 |

不立即增加 RDKit/QCElemental/QCEngine/ASE 或数据库依赖。QCSchema 保留候选对应表，BSE 用于实际基组来源核对；科学 π 组不冒充覆盖全部原子的标准 fragments。

## 5. 输入、快照和 profile

请求沿用已审设计字段，示例仅展示未来格式，当前不能运行；四碳编号不是科学推荐：

```json
{
  "schema_version": 1,
  "service": "user-molecule-fixed",
  "geometry_file": "molecule.xyz",
  "coordinate_unit": "angstrom",
  "charge": 0,
  "multiplicity": 1,
  "research_question": "考察指定分片条件下的电子耦合模型响应",
  "condition_definition_acknowledged": true,
  "fragments": [
    {"id": "A", "carbon_atom_indices_1based": [1, 2]},
    {"id": "B", "carbon_atom_indices_1based": [3, 4]}
  ],
  "condition_profile": "cross-fragment-pi-2011-v1",
  "calculation_profile": "pilot-b3lypg-sto3g-grid2-v1",
  "resources": {"threads": 2, "memory_limit_mib": 4096, "wall_time_limit_seconds": 900}
}
```

JSON 解析拒绝重复键、NaN/Infinity、未知字段和错误类型；整数不接布尔替代。XYZ 精确匹配原子数，仅 C/H、有限 Å 坐标，拒绝重叠/截断/多结构。每个碳恰属于 A/B，各组非空，不接受氢编号。明确 spin=0 与 multiplicity=1 的转换，不加氢、不重排、旋转或投影。research_question 仅为有界文字，不影响数学选参，也不执行代码或触发大模型。

工程文件上限可先以请求 256 KiB、XYZ 4 MiB、原子数 128、备注 512 字符作为候选，在 D1 配置文件冻结并测试；这些是解析防护，不是受支持分子规模。计算 nAO/近碰撞/病态阈值仍按科学与资源合同冻结，不用文件上限证明适用性。

输入目录内读几何，拒绝绝对路径、..、URI、符号链接/重解析点逃逸。宿主先固定文件副本并限定挂载，再由容器严格解析；原字节/规范化请求分别哈希，原子 1→0 映射明确记录。检查后原文件或快照/profile/规则/来源变化，compute 拒绝旧回执并要求重新 check。

profile 必填：Python/库身份、基组展开/球谐/无 ECP、XC 解析/混合系数、网格及剪枝、普通 initial guess/conv_tol/conv_tol_grad/DIIS/阻尼/max_cycle/max_memory、条件全部参数、ERI 模式、每项门禁公式/单位/阈值版本、单位转换常数与适用范围。未核对实际值写未冻结，计算不开启，不能只填“PySCF 默认”。

pilot 候选为 B3LYPG/STO-3G/grid2，研究候选为 B3LYPG/6-31G(d)/grid3。条件候选参数沿用合同：max_cycles=100、density_tol=2e-8、显式 energy_tol=1e-9 Eh、DIIS start=2/space=8、damping_cycles=2/damping=0.20；原核 energy_tol 默认 1e-10，必须显式传明。完整有效参数仍待冻结，不在本轮宣称 profile 已可用。

## 6. 检查和科学计算流水线

**check：**文件/严格 schema/坐标和分片 → 固定快照 → 在受限 inspect 子进程创建 Mole、核对 AO 标签和 nAO → 范围状态/资源模型/配置启用判断 → preflight、原子表和 manifest。inspect 不调用 SCF、网格积分或 int2e，不分配完整 ERI；超规模在分配前拒绝。D1 可先做纯解析，真实 AO 检查须在目标依赖环境运行后才算完成。

**compute：**复核回执身份/镜像/依赖/原文件 → 重查当时可用资源并获得本 runtime 锁 → 固定几何普通 RKS → 必需资格检查 → 以合格普通密度作为条件初始 D → run_p09_conditional_rks → 最终度量/账本/两态资格 → 差值/简报/阶段记录。普通态不合格不进入条件态；不拿其他几何或历史能量补齐。

静态源码已确认的结果映射如下，具体字段结构在 result schema 实现时冻结：

| 固定条件核返回字段 | 服务用途 | 注意事项 |
|---|---|---|
| converged、cycles、history | 收敛和迭代诊断 | 首轮未定义能量变化用 null+reason，不能把 Infinity 变成零 |
| total_energy_hartree | 条件总能量 | 同几何比较；有限并不代表门禁合格 |
| one_electron_energy_hartree、coulomb_energy_hartree、exact_exchange_energy_hartree、semilocal_xc_energy_hartree、nuclear_repulsion_hartree | 五项账本 | 保留核字段，不编造普通态缺失分项 |
| energy_component_closure_residual_hartree | 闭合资格 | 不替代能量—算子解释 |
| masked_metric_electron_count / physical_metric_electron_count / grid_electron_count | 三种不同度量 | S̃ 下必需量与原 S/网格诊断分别判断 |
| final_commutator_frobenius_norm、closed_shell_idempotency_relative_residual | 数值门禁 | 最终 D 与重算 F 来源记录清楚 |
| masked_overlap_minimum_eigenvalue、masked_overlap_condition_number、masked_overlap_cross_pi_max_abs、conditional_fock_cross_pi_max_abs | 病态/屏蔽检查 | 非正定拒绝，不私自正则化 |
| deleted_eri_count、eri_storage_mode、occupied_virtual_gap_hartree | 删除范围、模式、gap 诊断 | gap 是末次对角化值，不是最终 F 稳定性证明；未定义 null+reason |

NumPy 矩阵不能直接塞入 JSON；默认面向用户输出标量、有限列表和必要摘要，不把 density 当已验证的化学密度图。参考验收需要的矩阵按独立工件/哈希留存，范围和大小登记，不默认向外分发。

数值门禁沿用 A09：电子数候选 1e-7、闭合 1e-9 Eh、对易子 Frobenius 1e-5、幂等性相对残差 1e-7、禁止 S/F 块 max_abs 1e-12，实际生效前须版本冻结。比较 Eh/kcal/mol 和正负号、转换常数均记录。PySCF 文档也区分 [SCF 收敛与稳定性分析](https://pyscf.org/user/scf.html#stability-analysis)，本服务不把收敛等同稳定基态。

## 7. 状态机、退出码与数据工件

继续使用设计合同的 input/execution/numerical/comparison/method/research 分层状态。成功退出、数值资格和研究资格不能合并。pilot 数值合格只可 TECHNICAL_ONLY；research 必须匹配实际批准范围才能 QUALIFIED_WITHIN_SCOPE；未知范围仅在获准探索条件下为 EXPERIMENTAL_METHOD。任一态必需门禁失败：comparison_available=false、delta=null、NOT_QUALIFIED。

拟定新服务退出码，不改变旧七任务：0 正常且本动作要求满足；10 输入无效；11 不支持；20 配置未启用/资源或运行资格阻塞；30 数值门禁失败；40 执行/来源/引擎错误；50 超时；60 取消。check 可以保留有效回执同时报告 compute 不具备资格，输出字段逐项说明。实际科学子进程、Docker 命令和容器退出码分别记录；容器尚未启动/终态未知时写 null+reason，不能填 0。进程完成但门禁 FAIL 可为 execution=COMPLETED、服务退出码 30。

```text
<OutputRoot>/<唯一 check/run ID>/
  input/request.original.json / request.normalized.json / molecule.xyz
  preflight.json
  runtime-progress.json        # 容器内分态/阶段原子更新
  result.json / report.md      # 实际产生才存在
  stdout.log / stderr.log
  host-execution.json          # 容器外监督的启动/退出/OOM/限额记录
  run-manifest.json            # 宿主汇总真实身份/各态/已存在文件及哈希
```

计算 run 引用 check run ID 和回执/快照哈希，不复写检查目录。JSON 用 UTF-8、allow_nan=false、同目录临时文件原子替换；记录有大小限制，未完成文件不标完整。request/result/profile/schema/规则、科学/runtime/启动器提交或文件身份、依赖、image ID/digest、实际参数、内存/线程/时间/网络及退出状态均可追溯。未知有 reason，不记录完整环境变量或认证信息。

## 8. Docker 和宿主监督

新宿主启动器先保存唯一 run ID、请求身份、镜像 immutable ID 和启动意图，再执行 docker create/start/attach/wait/inspect/logs。保存 container ID，等待真实终态后读 ExitCode/OOMKilled/错误与日志，最终落盘 manifest 和输出清单。验收/故障候选不默认 --rm，以免提前失去 inspect；完成收集后只清理本次明确 ID。取消或超时先 stop 本次 ID，必要时 kill 同一 ID，不枚举并杀其他容器或 vmmemWSL。

拟定运行配置：固定 image ID、非 root UID 10001、--read-only、--network none、--cap-drop ALL、--security-opt no-new-privileges；输入/profile/规则只读挂载，输出与共享锁为指定持久目录；PySCF scratch 使用有界临时位置。临时空间若用 tmpfs，须计入内存峰值，不把它当免费空间；容量及写权限实际验证。

内存使用明确的 --memory；候选禁用 swap 时 --memory-swap 与它同值，实际内核支持/生效仍需验证。CPU 用 --cpus 和已冻结线程环境/PySCF 线程值分别限制；线程数不能替代配额。以上依据 [Docker 资源限制文档](https://docs.docker.com/engine/containers/resource_constraints/)，不是本机已经生效的证明。运行选项与挂载语义以 [Docker run 官方接口](https://docs.docker.com/reference/cli/docker/container/run/)为准。

复用 memory_snapshot 的有效余量，在新封装补 CPU cgroup 层级及 fractional quota 信息；无法核对控制器、限额、可用余量时 compute BLOCKED，不改系统来绕过。ERI 单张量 8nAO^4 只是下限，分别校准复制/原位两模式与网格/中间矩阵/临时空间/解释器的峰值和安全余量。

资源校准/科学参考沿用候选上限：参考 nAO≤40、1 线程、4 GiB、每次≤900 s；普通/两路径 nAO≤80、最多 2 线程、4 GiB、每次≤900 s；单轮全部新科学进程累计≤7200 s。所有数值导数及参考过程计入预算。实际资源充分性未验证；预算不够缩小受审样例或另行登记，不能自动上调或放宽数值判据。

宿主监督失败、Docker 服务断开或电脑异常时也不承诺完整终态；留存最后确认的进度和 UNKNOWN 终止原因。容器 OOM 与普通 Python MemoryError、数值不收敛分别报告。检查回执不是资源预留，compute 启动前再检查；共享锁只串行本 runtime 管理的任务。

## 9. PowerShell 和命令合同

拟定容器入口为 `python -m runtime.user_molecule check|compute|report ...`，新 Dockerfile 直接指向这个模块，旧 entrypoint 不改。Windows 用 start-user-molecule.ps1 从 PS 5.1 调用已有 PS 7.3+ 的 run-user-molecule.ps1。Check/Compute 默认 Docker，WSLc 不作为选项。Report 只读已存在记录，不能重算或补写科学结果。

下面是将来实现完成后的使用形式，脚本尚不存在，请勿现在执行；镜像必须是新候选实际 ID，不是旧镜像标签：

```powershell
# $candidateImageId 须取自新镜像的实际构建/inspect 记录。
.\scripts\start-user-molecule.ps1 -Action Check -Image $candidateImageId `
  -Request .\input\request.json -OutputRoot D:\AI4Science\user-molecule-runs

# $checkRun 为刚生成的完整检查目录；同时核对原 Request，变化时重新检查。
.\scripts\start-user-molecule.ps1 -Action Compute -Image $candidateImageId `
  -Request .\input\request.json -CheckRun $checkRun `
  -OutputRoot D:\AI4Science\user-molecule-runs

.\scripts\start-user-molecule.ps1 -Action Report -RunDirectory $computeRun
```

resources 只从请求中读取，避免命令行与 JSON 有两套数值；宿主仅核对和执行批准限额，不静默替换请求。路径和参数用数组传递，不拼 shell 指令；原子编号/研究备注不能进入可执行文本。输出显示动作、状态、原因和结果目录，失败返回明确退出码且保留交互终端。用户不手工对哈希，系统记录即可。

## 10. 新科学来源、构建和身份链

新适配器在科学仓库独立工作区提交，再从该完整本地提交 git archive 形成固定归档，记录 SHA-256/文件清单。新 runtime 候选也从提交导出的干净上下文构建；已存在未跟踪方案保留，不被无差别加入科学或公开范围。

新科学提交尚未公开时，采用显式 local_git_archive 模式：构建输入为受检本地归档，不伪造不存在的 codeload URL，不为构建先推送。获取器验证归档和成员路径/文件哈希，拒绝路径逃逸；保存构建输入以便本地复建。后续若公开再增加远端获取模式，仍固定完整提交/哈希。

新 Dockerfile 复用固定基础和 requirements 的 --require-hashes、离线安装/pip check，读取专用科学锁。镜像 label 分别记录 runtime/scientific commit、schema/profile/依赖锁身份，科学 tag 未建立则空值+原因，不能把新提交标 v0.3.2。新服务校验新文件清单；旧七任务/旧来源锁和旧镜像保留。首次新候选实际运行只验证所执行范围，不宣称全部旧任务在新镜像 PASS。

身份链为：用户原字节/规范化快照 → schema/profile/条件规则 → 科学适配器新提交及基线 → runtime 构建提交 → image ID（registry digest 另记）→ 当前启动器身份 → check/run/父记录 → 实际输出哈希。构建后文档提交和启动器修订不能冒充镜像构建提交。科学分支改了核或规则则另走科学变更审查，不以封装修复隐藏。

## 11. 实施工作包和完成定义

| 工作包 / 次序 | 具体工作 | 完成定义 / 证据 |
|---|---|---|
| W01 基线与实施登记 | 保存未提交文件/旧候选；登记用户工程准入、独立工作区、待审科学项 | 基线/文件清单、工作区身份；没有覆盖或改写旧记录 |
| W02 请求与低成本检查 | schema/严格 parser/模板/路径/原子表/规范化/状态；先纯解析，再目标环境 inspect | A02—A04 与 A11 检查部分实际通过；无 SCF/完整 ERI；近碰撞等未定项冻结后才完整退出 D1 |
| W03 科学 inspect/适配器 | 在科学独立分支实现 Mole/AO/普通态/条件调用/输出；显式完整参数 | 代码审阅、同几何/映射/原始返回量核对；没有改核换取收敛 |
| W04 宿主监督/新候选 | 新来源锁/干净构建；PS5.1 引导、硬限额/生命周期/日志与 manifest | 构建身份、非 root/只读/网络/限额/故障/容器删除后输出实证 |
| W05 独立基础参考与 pilot | toy/固定 D 分量、独立普通 RKS、存储路径、不变量、资格和状态 | D2 必需参考及数值通过；仅 TECHNICAL_ONLY；受控测试驱动可调用未开放候选，记录 acceptance 用途，不向用户冒充就绪服务 |
| W06 完整参考与研究域 | 至少两个冻结新体系；每研究 profile 完整独立条件参考；方法范围与 C06 解释复审 | A01—A18 适用项、范围批准/责任及资源受测规模，D3 出口可核对 |
| W07 用户交付与备份 | 最短指南、真实样例、失败说明、支持矩阵/许可来源/候选备份 | 专业用户完成模板→检查→计算→读资格；当前与历史身份分开，形成独立本地候选提交 |

依赖顺序：W01 → W02 与 W03 的 inspect 部分 → W04 检查候选 → W03 compute/W05 → W06 → W07。W02 纯解析无需等待完整研究审查；W03/W05 基础参考可以与工程封装分开推进。科学运行必须满足已冻结输入/profile/阈值/资源与预算，未定的研究解释不被作者自签；无需逐项重复确认已经授权的工程工作。

W01/W02 是当前应首先实施的批次。W03/W04 的科学代码和新镜像产生后各有新身份；其验证不重做旧 L3/L4。每批完成记录“实现/实际执行/通过/未知”，不以写出文件就算运行验收。

## 12. 测试覆盖与验收矩阵

| 测试层 | 内容 | 合同映射 |
|---|---|---|
| 纯解析/路径 | 重复键/NaN/类型、XYZ 截断/计数/元素/xy、碳组、UTF-8/中文空格、逃逸、原文件/快照变化 | A02—A04、A17；不依赖科学计算 |
| 状态/进程 | 分态成功失败、必需非有限、未定义诊断、比较 null、pilot/范围真值表、宿主容器未启动/未知终态 | A09/A13/A17；模拟用于语义，不能代替实际 OOM |
| 数学控制 | toy ERI/十五类/八重对称/固定 D 账本、A/B 重命名、同步重排和单组内部控制 | A06/A08；不宣称完整分子独立参考 |
| 小体系数值 | 至少两新冻结体系；普通驱动、存储路径、每研究 profile 完整条件参考；所有阈值运行前冻结 | A05—A10；不能只比较总能量 |
| 真实容器 | 有限资源、拒绝、取消/超时/受限 OOM、只读/非 root/断网、删除后输出 | A11—A13/A15；低预算故障，不压满科研宿主 |
| 易用性/声明 | C01—C06 简报、本地用户独立操作、来源/镜像/启动器/结果对应 | A14—A18；模型量不冒充单键能、实验或普遍科学结论 |

科学候选夹具和参考、病态/近碰撞/小 gap、普通态独立参考阈值、完整默认/有效参数、峰值模型仍需冻结；列入待办，不从旧单个 P14 值外推。没有真实结果填 NOT_EXECUTED；失配调查原因，不放宽容差或改分片以满足预期。

CI 运行当前仍 NOT_EXECUTED。未来增加纯解析/状态/小 toy 的自动测试，受预算数值和 Docker 验收按显式 job/授权登记；CI 不自动执行旧 L3/L4、不推镜像、建正式标签或 Release。公开运行附件只含受审教学夹具，不能自动上传用户私有分子和日志。静态 workflow 审查与实际 job 状态分开。

## 13. 当前准入与后续门槛

工程准入依据是用户本次“目前可以进入实施阶段”的明确指示，足以推进 W01/W02 与授权范围内的实现，不再要求用户重复批准同一设计。科学复审仍按 R1—R6/Q01—Q09 保留：全局占据/允许变化/能量—算子解释、方法范围、独立参考谱系和完整 profile/预算；工程准入不是这些问题的通过证明。

check 能接收合法请求并揭示未知范围，但 compute 不可绕过完整配置/受限环境/资源和数值条件；研究资格只有 D3 实证和范围匹配才成立。对真正缺失且影响科学结论或资源授权的新决定，在具体可审阅材料准备好后集中处理，其他工程工作继续推进。

平台/发布独立状态保持：WSLc BLOCKED / NOT_EXECUTED；Colab DEFERRED；CI 运行 NOT_EXECUTED；镜像分发 BLOCKED；源码公开、正式标签、Release 和推送未获本轮授权。新代码/依赖/科学解释若新增分发义务，针对选定范围补材料，不扩展成通用合规平台。

## 14. 本轮交付范围与来源

本轮新增本技术方案，并在专业方案、主合同、本地细则、评审任务书记录工程准入与链接；不修改 runtime/科学代码、旧来源锁、Dockerfile、七任务或历史支持声明，不创建代码提交/新镜像/运行结果。实际静态核查另行记录，不标数值或平台 PASS。

代码事实来自当前 runtime/scripts/locks/container 与独立固定归档的 p09_conditional_scf.py；外部资料仅官方 Docker/PySCF 文档。目录/命令/退出码是新设计，读到的旧代码与尚未实现的接口明确区分。本地旧审阅包、方案修改前原字节及提交保留；所有新增草稿仍待纳入本地提交并另审公开范围。
