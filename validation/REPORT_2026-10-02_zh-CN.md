# 2026-10-02 候选环境实施与验证报告

## 后续授权的 L3 实测更新

用户完成首次使用后明确授权启动 L3。本地 Docker 候选 p14-fixed 已完成，manifest PASS、退出码 0，全部输出哈希复核一致；原始记录位于 `D:\AI4Science\ai4orgchem-runtime-runs\20261002-l3`，小型汇总见 [l3-summary.json](l3-summary.json)。下文未运行 L3 的陈述保留为此前阶段历史，本节更新其当前 Docker 状态。

CPU 为 Intel Core Ultra 9 185H，16 物理核心/22 逻辑处理器；容器 affinity 22，本次请求 8 线程，运行中 CPU 采样 798.87%（约 8 个逻辑处理器的计算量），容器内存采样 5.077 GiB。启动前有效可用内存约 14.35 GiB，无 cgroup 限额；科学进程实际峰值 RSS 8800.86328125 MiB（约 8.60 GiB）。耗时 54.369574647 秒，约 0.015 小时。本次结果不能保证以后不同负载同样耗时或峰值。

12 项上游 anchor 资格全部通过，固定几何端点 67.08689934803395 kcal/mol；来源报告端点 67.08，残差 +0.006899348033954311 kcal/mol。G/PLG 来源能量残差分别 +0.009631057372416763 Eh、+0.009621278124541277 Eh。anchor PASS 不包含文献残差合格门禁，不认定完全重现或最终科学分类。未修改科学规则或容差。

本次采用现有 Docker 启动器，运行不需要网络但未显式 --network none，不将本次 L3 声称为网络隔离实测。L4 与新四输入联合分类仍 NOT_EXECUTED；L4 可保存检查点，但不支持恢复运行。WSL 升级和 WSLc 实机验收继续暂缓，WSLc 保持 BLOCKED / NOT_EXECUTED。

## 本轮收尾决定

2026-10-02 用户明确要求优先保护原 AI4OrgChem 科研运行环境，暂停 WSL 升级和 WSLc 实机验收。本轮收尾，不继续平台升级或验收；后续恢复须由用户明确授权。原项目未启用 Docker，不将 runtime 的 Docker 验收视为原项目运行方式，也不据此推断原项目完全不依赖 WSL。

WSLc 状态保持 **BLOCKED**，相关实机测试保持 **NOT_EXECUTED**，不宣称已支持。已完成的独立 runtime 实现、来源/依赖锁、本地 Docker OCI 镜像、验收日志和报告全部保留，Docker 的 PASS 范围不变。原项目已修改和未跟踪文件保留；未升级 WSL、修改全局配置、重启或公开发布。L3/L4 仍未执行；L4 可保存检查点，但不支持恢复运行。

这是实际记录：本地 Docker OCI 本轮验收已通过，WSLc 仍未执行。下方 WSL2 历史记录和启动前阻塞保留；最新 OCI 结果见末节。原项目工作区、科学源码、协议与冻结证据未修改；未推送、发布镜像、打正式标签或发布 Release。

## 阶段状态

| 阶段 | 状态 | 依据 |
|---|---|---|
| A 来源/入口/平台核查 | PASS | 固定标签与 SHA、归档与 588 文件哈希、源码审查和平台工具记录 |
| B 构建工程与依赖锁 | PASS（本地 OCI） | 固定来源与 17 wheel 锁，从干净 runtime 仓库实际构建成功 |
| C 任务封装与持久输出 | Docker 子集 PASS；WSLc BLOCKED | L0—L2/等价性、权限、离线、退出码、持久输出通过；WSLc 尚无实机验收 |
| D WSL2/WSLc 对照 | BLOCKED | WSL2 有记录，WSLc 工具版本条件不足，相关测试 NOT_EXECUTED |
| E L3/L4/本次联合分类 | NOT_EXECUTED | 接口完成，耗时预算未知，高成本任务未授权预算/未启动 |
| F 候选文档与发布材料 | 候选材料已交付 | 发布就绪仍受 WSLc 验收及许可清单待办阻塞；不是正式发布 |

## 已执行结果

独立候选 Python 3.12.13，NumPy 2.5.1、SciPy 1.18.0、PySCF 2.14.0；完整 17 依赖见锁和运行 manifest。源 commit `28511f3d84fa65707a107cde1e8121a7b4334ecb`，上游包版本 `0.1.0`。最终 LF 依赖锁摘要 `a8dbe44d12930427ca1f377b17eba3fcdb17b6dd922737884b3b77d0d9c4ea71`。首次记录摘要 `7145fe7b4e9e0444920d4f3ba86d0a22c58fee9c4248a7b1de23e4e68bf37c6b` 对应 Windows CRLF；提交前只归一化锁文件换行以保证干净检出稳定，版本与 wheel 哈希没有改变。

| 项目 | 实测 |
|---|---|
| pip check | PASS：独立 venv 离线哈希安装 |
| runtime 单元/过程测试 | PASS：最终 Linux 12 项全通过；含分类器冻结样例路径适配测试与真实 CLI 缺输入拒绝 |
| PowerShell | PASS：7 项路径/语法检查；不代表 WSLc 命令已运行 |
| L0 | PASS：十四项、P12、导航、P14 底层证据全部核验 |
| L1 | PASS：三份原测试共 11 项 |
| L2 | PASS：15/15 自身数值资格，最终复验 12.31 秒，峰值 RSS 547.88 MiB |
| STO-3G 等价性 | PASS；第一次源码缺失预检 FAIL 保留 |
| 源码/证据 | 只读、任务前后 588 个文件哈希校验一致 |
| 输出 | 与源码目录分离，在 Windows 宿主持久目录保留 |

L2 技术端点 `26.471605327369403 kcal/mol`，固定提交同层级冻结值 `26.471605327226722 kcal/mol`，绝对差 `1.4268053405430692e-10 kcal/mol`。这是 STO-3G 技术对照，不是 L3 的 67.086899 端点复算，不能作科学定判。L3/L4 残差 UNKNOWN，未计算；WSL2/WSLc 相互残差 UNKNOWN。

## 已提交代码的最终复验

实现提交 `c2cc5027d25defa32338b04cda577285dcc06cf9` 在干净 runtime 工作区完成复验，四份新 manifest 都包含真实 runtime commit 与代码/锁快照摘要 `7aece0641285de490a4ff59a605b5684fbad305482ffc8daf63a093663d20762`。本报告和汇总的后续提交只更新文档/验收摘要。

| task | 最终运行 ID | 结果 |
|---|---|---|
| evidence | 20261002T105729Z-evidence-7262f14bf797 | PASS |
| core-tests | 20261002T105731Z-core-tests-84c2141cb412 | PASS，11 原测试 |
| p14-smoke | 20261002T105733Z-p14-smoke-6358690e4876 | PASS，15/15 |
| p14-equivalence | 20261002T105746Z-p14-equivalence-5d389d942d59 | PASS，13.84 秒 |

最终 L2 技术端点 `26.471605327226722 kcal/mol`，与同层级冻结值的本次绝对差为 `0.0 kcal/mol`；这不是对其他平台或将来运行逐位相同的承诺。等价性两实现总能绝对差 `0.0 Eh`，密度 Frobenius 差 `6.034833410415508e-13`。所有九份已记录运行（含一次预检失败）的输出哈希已经汇总脚本复核，见 summary.json。12 项测试与 PowerShell 7 项检查的小型记录见 checks.json；该 WSL2 验收时 CI、容器和 WSLc 尚未执行；后续 Docker 结果见末节。

原始日志目录：`D:\AI4Science\ai4orgchem-runtime-runs\20261002-wsl2`。首次三个运行 ID：`20261002T104043Z-evidence-ab57bf8dbabf`、`20261002T104045Z-core-tests-6b8796c8ba75`、`20261002T104047Z-p14-smoke-afbe6f3bce33`。这些在首次提交前执行，runtime_commit 为 UNKNOWN，未伪补写。后续已识别提交的执行记录另行汇总，不覆盖历史 manifest。

等价性首次预检失败 ID `20261002T104545Z-p14-equivalence-126b8b2e7cd6`：旧 `/tmp/...` 源码目录已不存在，588 文件缺失，未进入科学计算。重新获取同一固定归档到新持久 Linux 目录后运行 `20261002T104918Z-p14-equivalence-26d968497afa` 通过。没有修改哈希规则、数值规则或容差。

## 启动 Docker 前的历史阻塞与限制（由末节更新 OCI 状态）

WSL 安装包 2.3.26.0，Windows AMD64；官方核查日要求 WSL 2.9.3+ 方有 WSLc，本机 wslc 与别名不可访问且已知安装路径不存在。WSLc 平台验收 BLOCKED、全部相关运行 NOT_EXECUTED。

Docker Desktop 已安装但未启动：无相关后台进程，两个引擎管道都不存在；沙箱外 status 仍报告未运行。OCI 构建/容器验收 BLOCKED、实际构建测试 NOT_EXECUTED。未启动 Desktop、更新 WSL、启用系统功能、修改全局配置或重启。具体恢复步骤见 INSTALL_zh-CN.md。

源码归档下载和独立提取证明不依赖同级开发仓库；Docker 干净构建、容器非 root/挂载/离线、目标 WSLc 信号/资源/中文路径必须待工具恢复后实测。PowerShell AST 与候选参数/路径防护测试不能替代实际原生命令运行。

L4 写检查点但不能 resume；过程测试证明封装中断保留已写检查点，尚无完整 L4 实跑中断证明。分类器路径适配已实现；本次四份新科学结果未齐，联合分类 NOT_EXECUTED，缺输入拒绝已经测试。

镜像候选摘要 UNKNOWN（尚无镜像）；基础镜像摘要不是最终镜像摘要。没有“B—D 全部完成”或“WSLc 已支持”的声明。

## 用户授权后的 Docker OCI 最终验收

Docker Desktop 4.78.0（229452）已启动，Docker 客户端/服务端 29.5.3，desktop-linux、Linux/amd64。从干净 runtime 提交 `f30b2906794d14f9030daab779c0d6a7cd4bd6f7` 构建，无同级原项目依赖。

候选 tag：`ai4orgchem-runtime:oci-candidate-20261002`；本地镜像 ID/索引摘要：`sha256:ddc45b1fe500ed3d5ed30520eb4e49f3969cb69f02121f28e2ff851f7a724f54`。这是本地构建身份，尚无公开 registry 发布。四份运行均记录源码提交、runtime 提交、代码快照、依赖和镜像身份，详见 [OCI 汇总](oci-summary.json)。

| 项目 | 最终实测 |
|---|---|
| L0 / L1 | PASS；冻结证据校验 / 11 项原核心测试 |
| L2 | PASS，15/15；端点 26.47160532579993 kcal/mol |
| 同层冻结值及 WSL2 最终端点残差 | 1.426791129688354e-09 kcal/mol |
| STO-3G 等价性 | PASS；总能差 2.2737367544323206e-13 Eh，密度 Frobenius 差 6.226066644162052e-13 |
| 非 root、源码/证据只读 | PASS；USER 10001:10001，写打开被拒绝，588 文件任务前后哈希一致 |
| 离线 / 路径 | PASS；--network none，中文与空格 bind 目录 |
| 退出码 | PASS；任务退出 0，合成进程实际退出 37；封装传播由过程测试覆盖 |
| 真实 256 MiB 限额 | PASS；cgroup 剩余 258629632 字节，errors=[]，资源 helper 显式 MemoryError 退出 1 |
| 删除容器后保留输出 | PASS；四个容器已不存在，四份 manifest 与全部输出 SHA-256 复核 |
| 封装测试 | PASS；Linux 容器 12 项全通过，无跳过 |

L2 与 STO-3G 等价性属于技术验收，科学容差、规则、协议、冻结文件均未改变。上述残差不代表 L3 端点复算或 WSLc 对照。

首轮镜像验收通过后发现混合 cgroup 挂载识别问题：存在有效 v1 memory 控制器及未挂载的 v2 membership，封装保守报告 UNKNOWN。修正仅在有效 v1 可读时采用其限额，缺失/不可读控制器仍拒绝；新增回归断言后从干净提交重新构建并完整复验。中途一次 PowerShell 括号语法错误在运行前失败，已修正，错误日志未删除。

原始目录：`D:\AI4Science\ai4orgchem-runtime-runs\20261002-oci`。保留 engine-version.log、两次 build-attempt 日志、cgroup-diagnostic.log、acceptance-01/02 历史与错误记录；最终为 acceptance-03 目录及 acceptance-03-console/error.log。构建仅有固定 linux/amd64 的 Dockerfile lint 提示，无构建失败。小型汇总入 Git，大日志/结果仍独立保留。

WSLc 升级与验收条件单列于 [安装指南](../docs/INSTALL_zh-CN.md)。本轮未升级 WSL、修改全局配置或重启，未运行 L3/L4/新四输入联合分类，未公开发布或创建正式标签/Release。Docker stop 的原生信号语义未实测；合成中断测试不等于完整 L4 中断。**L4 可保存检查点，但不支持恢复运行。** B 本地 OCI 构建已通过；C 的 WSLc 部分及 D 仍 BLOCKED。

## 后续授权的 L4 实测更新

用户授权的 Docker p14-optimize 完成，manifest PASS、程序与封装退出码 0；18 项上游 production 资格全部通过。G 和 PLG 优化器均成功，未触及参数边界，梯度满足原协议容差。耗时 1272.177734144 秒（21.20 分钟、0.353 小时），峰值 RSS 8801.19921875 MiB（约 8.60 GiB）。请求 8 线程；启动初期 CPU 采样曾为 1547.50%，不能将请求线程数描述为强制 CPU 上限。

优化端点 67.67971905631804 kcal/mol，d_delta_r_GP 为 0.1722036356645249 Å；同层冻结值对照残差单列于 [l4-summary.json](l4-summary.json)。全部 manifest 输出 SHA-256 复核一致，checkpoint.json 保留，launcher stderr 为空；原始目录 D:\AI4Science\ai4orgchem-runtime-runs\20261002-l4\20261002T123346Z-p14-optimize-d7f348003891。

本节更新此前“L4 未运行”的历史状态，仅代表本机 Docker 本次优化资格 PASS。production_label 和 training_eligible 仍为 false；完整新四输入联合分类尚未执行，不将优化门禁代替最终分类或训练资格。科学代码、规则、协议与容差未改变。运行不需要网络但本次未显式网络隔离；未执行 L4 实跑中断或恢复。L4 可保存检查点，但不支持恢复运行。WSL 升级、WSLc 验收继续暂缓，WSLc BLOCKED / NOT_EXECUTED。
