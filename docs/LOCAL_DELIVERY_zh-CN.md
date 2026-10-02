# 本地交付与日常使用

当前状态（2026-10-03）：本地 Docker L0—L4/等价性/联合分类已验证，WSLc 暂缓并保持 BLOCKED / NOT_EXECUTED；CI 静态审查完成、运行 NOT_EXECUTED；许可映射与对应源码提供未齐，公开发布仍阻塞。身份与范围以 validation/final-delivery-status.json 和 DELIVERY_REVIEW_2026-10-03_zh-CN.md 为准，既有备份为历史快照。

截至 2026-10-02，本机 Docker 候选已完成 L0—L4、STO-3G 等价性及四份新结果联合分类。联合结果为 consistent，仅适用于固定 C12H6 来源代理、PLG 定义及五参数平面 D3h 协议。WSLc 仍 BLOCKED / NOT_EXECUTED；升级和实机验收暂停。未公开发布，未赋予训练资格。

## Windows PowerShell 5.1 或 PowerShell 7 入口

```powershell
cd D:\AI4Science\ai4orgchem-runtime
./scripts/start-runtime.ps1 -Task evidence
./scripts/start-runtime.ps1 -Task p14-smoke
```

入口自动查找 7.3+，在独立子进程执行原启动器，完成后显示退出码、状态及输出目录，不关闭当前终端。默认使用已验证 Docker 候选及 runtime-runs/daily-use；可用 -OutputRoot 指定其他绝对目录，空格和中文路径受支持。-CheckOnly 仅检查终端选择，不运行任务；如未自动找到，可用 -PowerShell7 指定完整路径。不会安装软件、修改 PATH、启动或升级 WSL。Docker 引擎须事先可用。

L3/L4 仅在用户明确预算下启动：p14-fixed 和 p14-optimize。实际请求 8 线程不是强制 CPU 配额；部分阶段 CPU 并行量可能超过 8 个逻辑处理器。L4 可保存检查点，但不支持恢复运行。默认启动器运行不依赖网络，但未强制网络隔离；严格隔离的 L0—L2 探针见 acceptance-docker.ps1。

## 当前验证记录

| 项目 | 本机 Docker 结果 |
|---|---|
| L0/L1/L2、STO-3G 等价性 | PASS |
| 非 root、源码只读、断网、退出码、删除后输出 | PASS（OCI 验收子集） |
| L3 固定几何 | PASS，54.37 秒，峰值 8.60 GiB |
| L4 优化 | PASS，21.20 分钟，峰值 8.60 GiB |
| 四份新结果分类 | PASS / consistent，13 判定与 19 优化资格全部满足 |
| L3/L4 严格网络隔离与真实中断 | NOT_EXECUTED |
| WSLc、WSL2/WSLc 对照 | BLOCKED / NOT_EXECUTED |

validation/REPORT_2026-10-02_zh-CN.md 保存时间顺序历史；最新小型摘要为 oci-summary.json、l3-summary.json、l4-summary.json、classification-summary.json。分类结果中的 runtime_provenance 是上游历史快照，本次来源以对应 run-manifest.json 为准。

## 备份及恢复

PowerShell 7.3+ 执行 scripts/backup-local.ps1 -Destination 绝对路径。使用新空目录，待计算结束再执行。保存不可变镜像 ID、整个 runtime-runs、Git 历史 bundle、源码 ZIP、逐文件 SHA-256 及备份清单。不会备份原 AI4OrgChem 开发仓库或全局 Python/WSL 环境。

恢复前按 backup-manifest.json 校验每个归档的 SHA-256，并按独立 backup-manifest.sha256.txt 核对清单。清单校验只能发现意外损坏，不是数字签名或身份认证。不要覆盖现有目录：

1. git clone runtime-history.bundle 到新的 runtime 目录，或将 runtime-source.zip 解压到新的目录。
2. docker load --input candidate-image.tar，再核对 image inspect 的源码/runtime/锁身份。按清单中的 image_tag_hint 重新标记加载的镜像；离线镜像导出不保证 registry digest 或签名附件一并保存，不声称公开仓库身份已恢复。
3. 将 runs.zip 解压到新的恢复父目录。run-files.sha256.json 用于复核普通文件。归档使用 .NET ZIP 支持中文路径，并明确排除 classifier-view 中指向 /opt/ai4orgchem 的容器内源码链接；源内容已保存在镜像中。四份输入副本、原运行结果、result、report、manifest 与日志均保留，排除模式记录在清单中，不修改全局链接权限。
4. 在新输出目录跑 evidence/core-tests/p14-smoke，确认恢复后的环境再开展科研计算。

备份仍在同一 D 盘，属于本地快照；应另行复制到独立存储以抵御磁盘损坏。当前交付不是正式 Release。具体原生 wheel 来源和通知交付、CI 实跑及 WSLc 验收仍待完成；组件清单和 Debian/Python 源码已补齐。

## 本轮备份与启动复验

最终交付位置为 D:\AI4Science\ai4orgchem-runtime-deliveries\20261002-handoff。此前成功备份 20261002-verified 已完成 256 普通运行文件、19 镜像 blob 及归档清单校验；早期失败尝试保留，原因是 Windows tar 处理容器源码链接与中文文件列表失败，最终改用 .NET ZIP。

Windows PowerShell 5.1 测试使用单个子进程的 -ExecutionPolicy Bypass，仅验证本地已审查脚本，未更改用户/系统执行策略。若你自己的终端阻止脚本，请使用已有 PowerShell 7 运行入口，或自行决定单次进程策略，不修改全局配置。

校验命令：python scripts/verify-local-backup.py D:\AI4Science\ai4orgchem-runtime-deliveries\20261002-handoff。该检查逐项验证归档、ZIP 内的运行文件及镜像 blob；没有执行 Docker 重新加载或系统环境恢复。备份清单记录真实仓库与镜像提交，两者不同属于正常的宿主工具/文档后续更新。


最新许可/源码与候选包续审见 [公开边界说明](PUBLICATION_BOUNDARIES_zh-CN.md)。20261002 备份和首次 211 文件材料包是历史快照；当前候选包路径为 D:\AI4Science\ai4orgchem-runtime-deliveries\20261003-final-candidate。所有执行后哈希与归档验证以该目录 package-manifest.json、package-verification.json 和 backup-verification.json 为准。
