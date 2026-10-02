# 安装与构建

当前无公开镜像。先阅读平台矩阵；本机 WSLc 验收 NOT_EXECUTED，不声明已支持。

Windows 目标主机使用 PowerShell 7.3+（启动器固定 Standard 原生命令参数传递，保护空格/引号路径），需要微软官方文档要求的 WSL/WSLc，并能运行 `wslc version`、`wslc --help`。现有本机 WSL 2.3.26.0 不满足核查日文档所述 WSL 2.9.3+。更新 WSL 会改变全局运行环境，由用户在准备目标主机时明确执行；脚本不自动更新。无需安装 Compose。

## 本机工具诊断与恢复步骤

以下为启动前历史诊断，当前引擎状态见本节末更新。沙箱外只读诊断确认：WSL 已安装且可执行，但版本 2.3.26.0 尚不包含已要求的 WSLc；wslc/container 别名不在 PATH，已知 Program Files 路径亦无 wslc。不能简单称整个 WSL 未安装。Docker Desktop 可执行文件已安装，客户端 29.5.3 可运行；没有 Desktop/backend 进程，默认与 desktop-linux 两个引擎管道均不存在，沙箱外 Desktop status 仍报告未运行。podman/nerdctl 未在 PATH 找到，不声称已全面扫描所有磁盘安装。沙箱内的 WSL ACCESS_DENIED/ Docker 日志目录拒绝已与沙箱外实测区分，原始命令/错误保存在运行根 tool-diagnostics 目录。

优先复用已有 Docker Desktop；用户选择恢复时可在正常 PowerShell 7 执行：

```powershell
docker desktop start
docker desktop status
docker version
./scripts/build-wslc.ps1 -Engine docker -Tag ai4orgchem-runtime:candidate
```

这会启动已有 Desktop 后台进程及其 WSL2 引擎/发行版，并消耗主机内存，不需要重新安装。2026-10-02 已按用户授权执行启动，Docker 29.5.3 Linux/amd64 服务端可用并完成本地候选验收。如果它提示系统功能/安装升级/重启，先保留提示并评估，不自动接受。

选择恢复 WSLc 时，由用户在正常终端执行微软官方更新步骤：

```powershell
wsl --version
wsl --update
wsl --version
wslc version
wslc --help
```

该操作更新全局 WSL 包，可能影响既有发行版运行条件；遇到重启或功能启用要求时暂停，由用户决定。无需为本项目自动修改 .wslconfig，也不自动执行 wsl --shutdown。恢复后先 probe、再构建、再 acceptance，按实跑记录更新支持矩阵。

从 runtime 独立仓库构建，不需要同级 AI4OrgChem。构建需网络访问 Docker Hub、GitHub codeload 和 PyPI；下载按固定摘要/归档与 wheel SHA-256 校验。运行阶段不需要网络。

```powershell
./scripts/probe-wslc.ps1 -OutputDirectory D:\AI4Science\ai4orgchem-runtime-runs\platform-probe
./scripts/build-wslc.ps1 -Tag ai4orgchem-runtime:candidate
```

Docker 可用于独立通用 OCI 候选验收（不能替代 WSLc）：

```powershell
./scripts/build-wslc.ps1 -Engine docker -Tag ai4orgchem-runtime:candidate
./scripts/run-wslc.ps1 -Engine docker -Task evidence -Image ai4orgchem-runtime:candidate
```

构建脚本要求 reviewed commit 与干净 runtime 工作区，注入 runtime commit 和依赖锁摘要，完成后核查镜像标签和非 root 用户。工作目录的 .build 被忽略，只保存本地构建材料。Dockerfile 默认 linux/amd64、Python 3.12.13 官方 Debian slim 固定索引摘要，镜像内 /opt/venv 使用离线哈希安装；不会创建或修改用户原有 conda/micromamba 环境。

本地镜像已成功构建，下载校验、L0—L2 动态库运行、非 root 挂载和离线运行已实测；完整基础组件许可证清单与 WSLc 验收仍待补齐。build 失败保留日志，不通过现场 pip install 或更换浮动依赖绕过。

## 本地 Docker 验收复用

```powershell
./scripts/acceptance-docker.ps1 -Image ai4orgchem-runtime:oci-candidate-20261002 -OutputRoot 'D:\AI4Science\ai4orgchem-runtime-runs\docker-recheck'
```

OutputRoot 应使用新的目录。脚本以检查到的不可变镜像 ID 运行，记录实际命令、stdout/stderr、退出码和 acceptance.json；所有运行断网，不启动 L3/L4。构建需网络，运行不需要网络。原始本轮日志在 `D:\AI4Science\ai4orgchem-runtime-runs\20261002-oci`。

## WSLc 升级与验收条件（独立待办）

1. 本机 WSL 2.3.26.0 不满足核查日官方 2.9.3+ 前提。须另获升级授权后执行上述官方更新步骤；当前轮未升级。
2. 确认 wslc version/help 可用，并记录实际版本、挂载、内存、停止命令支持；如要求功能启用或重启，另行决定。
3. 在目标主机执行 probe-wslc.ps1、干净构建/经核实的镜像导入与 acceptance-wslc.ps1；单独验证中文/空格路径、非 root、只读、离线、退出码、持久输出、资源限制及停止语义。
4. 完成 WSL2/WSLc 同输入同依赖技术对照后更新矩阵；不得用 Docker 的 PASS 补写 WSLc。L3/L4 必须另行授权预算；L4 可保存检查点，但不支持恢复运行。
