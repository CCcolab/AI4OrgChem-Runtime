> 当前公开阅读节选。原始历史材料已按原字节保存在本地归档；本文件不是原件，不能用于原始哈希验收，也不把旧验收转移至当前代码。
> 原件 Git 提交：eb65b4586c83637569f6359814338c1292948861；SHA-256：6257d4f0ce2791d8e1316c5ffae3568ee815c457dca2928a5520f803368fa4b7。

# 本机 Docker 启动防护与验收

2026-10-09，本机 Docker Desktop 4.78.0／Engine 29.5.3 的已知启动故障已有可重复验证的维护入口。厂商底层原因仍未闭合；本页不宣称升级或永久修复已经完成。

已有错误涉及 `Docker/run/dockerInference`、`docker-secrets-engine/engine.sock` 等零字节 reparse 项。正常停止 Docker 后，仅把两个完整临时目录保留到同父目录的唯一 quarantine 路径，再重建空目录，能够恢复本机启动。镜像、模型、WSL 数据盘与科研目录均不删除。

## 本机入口

脚本 [local-docker-startup.ps1](../scripts/local-docker-startup.ps1) 需要 PowerShell 7；不要在 Windows PowerShell 5.1 直接执行。可用已安装的 PowerShell 7 或本机已有的 Codex 配套 PowerShell 7，不要求安装／升级 WSL。

```powershell
# 在 PowerShell 7 中，先只检查；健康引擎返回后不重启、不移动目录。
./scripts/local-docker-startup.ps1 -RecordRoot 'D:\AI4Science\docker-maintenance\check-unique'

# 仅在没有活动容器或其他 Docker CLI 时，明确要求正常停止／启动。
./scripts/local-docker-startup.ps1 -RecordRoot 'D:\AI4Science\docker-maintenance\restart-unique' -Restart
```

每次使用新的记录目录，禁止覆盖。`-Restart` 验收要求引擎起初可用，先读取全部镜像身份、确认无活动容器和其他 Docker CLI。引擎已失败且仍有后台进程时，脚本拒绝移动目录；保留错误，按既有人工恢复记录处理，不强杀未知任务。

两个目标目录须为预期绝对路径且自身不是 reparse。所有子项必须是已登记名称的零字节 reparse 文件；发现目录、非零文件或其他名称即拒绝。两个目录全部验证后才移动。不自动重试、不自动清空 quarantine。

重启后只运行128 MiB、1 CPU、无网络、非root、只读文件系统的 Python 标准库探针，使用现存固定镜像且 `--pull never`。探针不导入科学库，完成后自动删除；异常清理只处理带本脚本标签的 UUID 自有探针。脚本不调用 `wsl --shutdown`，不改 `.wslconfig`，不关闭其他发行版，不禁用模型服务，不恢复出厂、不升级或发布。

## 实际验证

记录目录：`D:\AI4Science\ai4orgchem-runtime-deliveries\20261009-six-issue-remediation\docker-startup`。

| 检查 | 结果 |
| --- | --- |
| 健康引擎的默认检查 | PASS，零重启、零目录移动 |
| 三次串行正常停止／启动 | 三次均 `PASS_SCOPED_STARTUP_MITIGATION_VENDOR_CAUSE_UNRESOLVED` |
| 前后镜像清单 | 10 个完整镜像 ID 全部不变 |
| 隔离探针与删除 | UID10001、源码只读、仅 loopback；三次删除回执通过 |
| 活动容器拒绝反例 | PASS；自有测试容器保持运行，维护没有重启引擎或移动目录，随后仅删除自有测试容器 |
| 新科学计算／镜像构建／WSL 配置变更 | 均为0 |

本次验证的是明确版本、本机、已知目录与零工作负载条件下的维护路径。未确认 Docker 厂商修复版本；不能据此保证其他机器或未来版本同样适用。
