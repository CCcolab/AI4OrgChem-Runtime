# W01—W04 本地工程交付与验证

2026-10-05 / W01-W04-ENGINEERING-1。工程入口已部署，可准备并检查用户 XYZ/请求、读取记录；Compute 保持 BLOCKED。没有执行新分子 SCF、完整 ERI、独立数值参考、资源峰值校准或研究验收。

| 工作包 | 实际交付 | 验证边界 |
|---|---|---|
| W01 | 从 0288eb8 和固定科学提交建立两个隔离 Git worktree；保存基线 | 原 runtime 108 份已跟踪文件、原科研 5 份修改文件与 Git 状态、588 份固定科学文件及 3 个历史包核对通过 |
| W02 | 严格 JSON/XYZ、路径与原子组检查、规范化、输入快照、检查回执 | 15 项输入/CPU 单元测试；真实 AO 检查已执行；近碰撞/病态/间隙科学判据未冻结，D1 未全部验收 |
| W03 | 新科学分支 inspect/compute 适配器，复用固定 P09 条件核 | 4 项 metadata/禁用计算/诊断测试通过；compute 数值运行 NOT_EXECUTED，不能宣称科学等价性 |
| W04 | 干净提交构建新候选，PS 5.1 引导、受限容器、宿主监督和持久记录 | 9 个实际入口操作、4 个最终候选容器探针通过；只证明受测工程行为 |

另有 12 项旧任务低成本回归通过，使用旧 588 文件固定来源夹具。合计 31 项单元测试；不含旧 L3/L4、完整旧七任务运行或新科学计算。请求模板是四个裸碳的 AO 工程夹具，没有化学研究推荐或 expected 能量。

## 身份链与运行记录

- 科学基线：`28511f3d84fa65707a107cde1e8121a7b4334ecb`，原 v0.3.2。
- 新适配器提交：`cc7437901119e71ef7945a12813c021c383e7648`；只新增适配器、测试和说明 3 个文件，原 588 个文件逐字节未改。新提交没有正式标签，不标为 v0.3.2。
- 最终候选镜像构建 runtime 提交：`5098775c9cf40468ab92712447a3e5c7b1361a63`。
- 本地镜像：`ai4orgchem-user-molecule:engineering-20261005-r3`；immutable ID：`sha256:24f46f33264924e5d3d3bec386298585267c6f30d6e6a0cd0a6486ecf45db93d`。
- 科学归档 SHA-256：`92cb1a467b9c5c502fbc0e353c17f0083218c8dfdbb322fb51f7aa6e8db5eb73`。
- 构建 runtime 归档 SHA-256：`7f714581269e9ed352f7f78c7ae3c1134b5d00a5cd559d61d406cf567daaec9d`。
- 构建后宿主启动器补齐实际参数数组/快照路径落盘与输入错误分类；随后文档/记录另有本地提交。不得把最终宿主/文档提交冒充镜像构建提交。最终提交与备份身份在本轮 `LOCAL_FINAL_DELIVERY.json`；实际工作字节 SHA 在 `w01-w04-status.json` 和每次 host-execution 中。

最终宿主检查实例：`D:\AI4Science\user-molecule-runs\w01-w04-host-final\check-20261005T075430Z-5248c027d56e4b4b856837a7387cb23b`。合法检查退出 0，但 compute_eligible=false；nAO=20，电子数=24，SCF/网格/完整 ERI 均未执行。有效 CPU=1.0 核；实际硬内存为 512 MiB、swap 同值、线程数 1。检查后可用内存不是预留或计算峰值保证。

实际拒绝：禁用 Compute 为 20、未知请求字段为 10、几何变更后的旧回执为 20；宿主非法资源/越界路径为 10，容器未创建且原始容器退出码为 null。Report 从 Windows PowerShell 5.1 经已有 PowerShell 7 运行，核对前后文件哈希未改变。Compute 没有产生能量，两态差值为 null。

## 支持矩阵

| 能力/平台 | 当前状态 |
|---|---|
| 新服务 Check / Report | 受测 pilot/STO-3G 本地 Docker/Windows 入口 PASS；research/6-31G(d) inspect 未实测；Report 不依赖运行引擎 |
| 新服务 Compute / 数值等价性 / 研究资格 | BLOCKED / NOT_EXECUTED；两个 profile 均 compute_enabled=false |
| 非 root、只读输入/软件、断网 | 最终 r3 候选实证 PASS；运行 UID 10001、network=none、只读根文件系统 |
| CPU/内存硬配额、超时、取消、OOM、退出与持久输出 | 受测探针 PASS；OOM 仅在 128 MiB 容器发生，实际 OOMKilled=true、退出 137；宿主记录在容器外，输出在删除后保留 |
| 原七任务历史验收 | 仍属于旧镜像 ddc45b1…；未将其 PASS 移给新候选；新镜像仅测了 12 项低成本回归 |
| WSLc | BLOCKED / NOT_EXECUTED，继续暂停；未升级 WSL、改全局配置或重启 |
| CI | 原静态审查保持；新分支运行 NOT_EXECUTED，未推送触发 |
| Colab | DEFERRED |
| 镜像分发 | BLOCKED；原许可证/来源/通知闭合事项保留，新候选没有新增分发批准 |
| 源码公开 | 原候选保留；本分支新增文件/提交/本地路径披露另行审阅和授权；没有推送、正式标签或 Release |

## 已修正故障与保留的旧记录

1. Docker Desktop 的 Inference Manager 和 Secrets Engine 残留 Windows 套接字不可访问。确认相关后台退出后，临时目录改名备份并重建，现有引擎恢复；未做出厂重置/清空镜像/升级或停止原科研 WSL。详见本轮 `DOCKER_RECOVERY_zh-CN.md`、两份操作 JSON 和引擎恢复核查。
2. 第一轮构建被旧 `.dockerignore` 排除新目录阻塞。新增专用 Dockerfile ignore；失败日志和第二轮记录保留。最终 r3 使用干净 Git archive、固定基础与依赖、已验证科学 tar 和缓存 wheels，RUN 安装阶段 `--network=none`，没有新依赖升级或公开推送。
3. 初始 PS 参数数组把 Image 与值拼为一个参数；已修正，并以 Windows PowerShell 5.1/中文、空格与方括号路径实测。
4. 初次旧回归由于新来源文件集合被旧锁拒绝而失败，旧锁行为正确。换用原固定来源夹具后 12 项通过，没有放宽规则。
5. r2 资源记录把未承载 CPU 的 cgroup v2 层级误记为未知；修正混合 v1/v2 观察后，r3 实际读到 1 核配额且无错误。r2 与此前所有回执保留，最终结论以 r3 记录为准。

构建器的两条固定 linux/amd64 FROM lint 警告保留；这是当前平台范围限制，不作为多架构支持证明。实际构建和非科学探针通过。

## 未完成事项与后续边界

W05 尚未开始：需冻结受审夹具、近碰撞/病态/间隙判据、完整 profile、资源预算与计算 nAO 上限，做峰值校准、普通/条件状态与基础独立参考、两种 ERI 路径和数值资格实测。W06 尚未开始：每研究 profile 的完整独立条件参考、至少两个冻结新体系、范围和能量—算子/占据解释复审。作者未自签研究适用性；变分性 NOT_ESTABLISHED，稳定性 NOT_EXECUTED。

W07 的完整科研样例和用户验收也未完成；当前仅提供工程入口指南。不得手动翻转 profile 开关来绕过上述条件，不把条件能量响应称为单键能、实验测量或普遍共轭/芳香性结论。原 L4 可保存检查点但不支持恢复。

机器状态见 [w01-w04-status.json](../validation/user-molecule/w01-w04-status.json)、[implementation-state.json](../validation/user-molecule/implementation-state.json)。实际命令、stdout/stderr、manifest/哈希、构建归档与故障记录位于 `D:\AI4Science\ai4orgchem-runtime-deliveries\20261005-user-molecule-w01-w04`；原始运行目录位于仓库外，不自动加入 Git。静态核查和最终清单逐项指向这些证据，不把未执行项目标为 PASS。
