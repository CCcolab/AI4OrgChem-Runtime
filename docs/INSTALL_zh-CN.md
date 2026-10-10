# 安装与构建

当前服务、输入和实际验收范围见[能力注册表](../configs/runtime-capabilities-v2.json)及[专业服务矩阵](CURRENT_PROFESSIONAL_SERVICES_zh-CN.md)。源码与静态指南已公开；项目没有公开预构建镜像。新用户按[源码安装指南](SOURCE_INSTALLATION_zh-CN.md)准备、构建并登记自己的 Docker 环境。

## 1. 选择入口

- 仅阅读网页、协议或已有报告：不需要启动 Docker 或 WSL2。
- 执行本地计算：需要可用的 Linux/amd64 Docker 引擎及所选服务的输入、资源和安装身份。
- 检查已有普通 WSL2 科研环境：使用[原生 WSL2 只读 Check](NATIVE_WSL2_RUNTIME_zh-CN.md)。该入口记录环境身份和资源，不是原生计算后端，也不继承 Docker 科学验收。

Windows 可复用已有 Docker Desktop；Linux 可使用已有 Docker 引擎。本项目不自动安装系统功能、升级 WSL、修改 WSL 全局配置或重启电脑。Docker Desktop 在 Windows 上使用 WSL2 时会启动相应后台环境并占用主机资源；不用计算时可退出，磁盘上的镜像不需要全部运行。

## 2. 确认已有 Docker 引擎

在正常终端执行：

```powershell
docker version
docker info
```

应同时取得客户端和 Linux 服务端信息。只有客户端、服务端未响应或权限错误都不算引擎可用；保留实际错误并解决现有引擎的启动或访问问题。已有 Docker Desktop 且用户决定启动时，可执行：

```powershell
docker desktop start
docker desktop status
docker version
```

若提示系统功能、升级或重启要求，先评估，不自动接受。当前项目不依赖 Compose。可用已有 PowerShell 7.3+ 执行 Docker 专用探测，它只记录平台状态，不执行分子计算：

```powershell
./scripts/probe-docker.ps1 -OutputDirectory D:\your-work\runtime-runs\platform-probe
```

## 3. 新安装从公开源码开始

按[源码安装指南](SOURCE_INSTALLATION_zh-CN.md)使用已有 Python 3.12+，从干净、已提交的源码准备全新目录，构建并分别登记所需服务。该路径取得固定公开科学源码和锁定依赖，不需要原 AI4OrgChem 开发工作区或旧私有基础镜像。

Git 克隆包含源码和历史；本项目制作的安装源码 ZIP 还带 Git 对象证明。二者都不包含已安装环境、容器镜像或完整运行缓存。普通 GitHub 自动源码 ZIP 缺少安装证明，不能冒充已验证的安装 ZIP。

构建需要访问固定来源和软件仓库；执行阶段按服务合同使用已安装依赖。新镜像保存新的构建、安装与任务记录，不能套用旧候选的科学 PASS。遇到来源或 wheel 哈希差异应拒绝并保留日志，不替换来源锁或使用浮动依赖绕过。

## 4. 原七任务的 Docker 构建入口

此入口仅构建 `container/Dockerfile` 对应的原七任务环境，不替代新普通分子及三批案例的源码安装流程。在干净 Runtime 源码中，使用已有 PowerShell 7.3+ 和可用 Docker Linux/amd64 引擎：

```powershell
./scripts/build-docker.ps1 -CheckOnly
./scripts/build-docker.ps1 -Tag ai4orgchem-runtime:local-source-candidate
./scripts/run-docker.ps1 -Task evidence -Image ai4orgchem-runtime:local-source-candidate -OutputRoot D:\your-work\runtime-runs\evidence
```

`-CheckOnly` 只核对来源并准备构建身份，不访问引擎，不表示构建或计算通过。构建注入 Runtime 提交和依赖锁摘要，完成后核对镜像身份、平台与非 root 用户；原依赖和科学规则不变。

已有本地 P14 候选可经 `./scripts/start-runtime.ps1 -Task evidence` 从 Windows PowerShell 5.1 调用已有 PowerShell 7.3+。该启动器固定使用 Docker；参数和输出见[运行合同](RUN_zh-CN.md)。

## 5. 验收与边界

对自己选择的镜像和全新输出根，可显式运行低成本 Docker 验收：

```powershell
./scripts/acceptance-docker.ps1 -Image ai4orgchem-runtime:local-source-candidate -OutputRoot D:\your-work\runtime-runs\docker-recheck
```

脚本以实际不可变镜像 ID 运行并保留命令、stdout/stderr、退出码和验收记录；它不启动 L3/L4。历史本地 Docker 候选已验收的 L0—L4、等价性和联合分类只属于各自记录中的镜像、协议与输入。L0—L2、等价性和指定探针有断网记录；L3/L4 严格断网未执行。L4 可保存检查点，不支持恢复运行。

[Actions run 38003025857](https://github.com/CCcolab/AI4OrgChem-Runtime/actions/runs/38003025857)对 `86e29b47` 三个既有 job 成功，覆盖工程合同和旧 L0/L1；不代表全部科学服务或本轮新安装 CI 已通过。普通用户条件态 Compute 仍缺合格端点，高成本 78 个登记态中仅两个先导态完成验收。公开镜像分发的材料与授权阻塞见[公开边界](PUBLICATION_BOUNDARIES_zh-CN.md)。
