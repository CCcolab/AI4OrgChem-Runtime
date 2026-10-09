# 从源码安装本地 Runtime

本入口为已有服务提供独立的本地安装身份。它不公开镜像，不把历史候选的科学验收结论赋予新镜像，不修改原科研环境、WSL 设置或原来源锁。

## 环境与下载

需要 Python 3.12 或更新版本、可用的 Linux/amd64 Docker 引擎，以及构建时访问 GitHub、PyPI、Docker Hub 和 Debian 软件源的网络。主机 Python 只运行标准库脚本，不在主机或原 WSL 科研环境中安装科学依赖。首次构建下载约 161 MB 的 Python 依赖，另外需要基础系统镜像和 Git 系统包。磁盘与任务资源仍由各服务的原预检核查。

可以在 Git 克隆目录运行，或使用本项目 `install-local-runtime.py package` 制作的安装源码 ZIP。该 ZIP 携带 Git commit/tree/blob 身份证据，不含镜像、wheels 或旧 `science.tar`。普通 GitHub 自动源码 ZIP 尚不携带本安装证据，使用它时应改用 Git 克隆或本项目制作的安装 ZIP；不要自行改写身份清单。

本地候选未公开，未来 GitHub 地址、公开分支和下载包仍需用户另外确认。

## 准备与构建

在选定源码目录执行以下命令，`D:\RuntimeInstall\candidate` 必须不存在。示例路径可以更换为用户自己的独立目录。

```powershell
python -B .\scripts\install-local-runtime.py prepare --destination D:\RuntimeInstall\candidate
python -B .\scripts\install-local-runtime.py build --destination D:\RuntimeInstall\candidate
```

`prepare` 只从 Git 导出已提交文件，或验证安装 ZIP 的文件与 Git 对象。它下载固定公开科学提交，合并三份保留的适配文件，逐文件校验 591 项源码；再从官方 PyPI 下载并校验 21 个 wheel 和 1 个源码包。新科学归档有独立哈希，与历史 `science.tar` 不作字节同一声明。

`build` 先校验整个构建目录，再从固定公开 Python 基础镜像构建基础环境，最后构建 Runtime。geomeTRIC 从固定源码包在镜像内构建，记录新 wheel 哈希。Debian Git 包的实际版本与全部 Python 包版本保存于镜像 `/opt/install-build`；Debian 软件源版本未作位级可重复承诺。该流程不需要任何旧私有 Runtime 基础镜像。

在 `built-image.json` 查看新镜像 ID 和本地标签。构建日志与每步命令保留在安装目录。失败时查看对应 `*.stderr.log`，使用新目录重新准备；不要重置旧安装或改科学规则。

## 登记已有服务

进入安装目录中的 `runtime`，使用 `built-image.json` 的本地标签分别登记。每个输出目录必须不存在：

```powershell
python -B .\scripts\register-installation.py --service molecular-service --image <本地标签> --output-dir ..\installations\molecular-service
python -B .\scripts\register-installation.py --service registered-cases --image <本地标签> --output-dir ..\installations\registered-cases
python -B .\scripts\register-installation.py --service protocol-cases --image <本地标签> --output-dir ..\installations\protocol-cases
python -B .\scripts\register-installation.py --service high-cost-cases --image <本地标签> --output-dir ..\installations\high-cost-cases
```

登记检查实际镜像 ID、基础层、平台、标签、非 root 用户、依赖版本和关键源码文件。`ENGINEERING_VALIDATED` 只表示这些工程身份检查通过，科学验收状态仍为 `UNKNOWN`。执行每个任务时，原科学协议、资源限制、离线运行、数值门槛与证据收集继续生效。历史候选记录不被改写。

P11/P12 的新安装来源清单仅重新绑定两个已存在的主机运行器／测试文件，另 105 项与历史清单完全一致。原清单另存于安装目录，记录这种精确限定的变化；不更新科学源码或降低原门槛。

## 使用新安装身份

小体系普通 RHF 单点计算使用既有水分子请求，并生成新安装自己的数值记录：

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\molecular-service\installation-record.json --task single-point --request .\examples\molecular-service\water\request.json --output-root ..\runs\water
```

请求路径以实际源码树内示例为准。固定任务不接受用户分子请求。例如：

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\registered-cases\installation-record.json --task p02-statistics --output-root ..\runs\statistics
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\registered-cases\installation-record.json --task p13-graph-ledger --output-root ..\runs\graph
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P07 --mode ledger --output-root ..\runs\p07-ledger
```

P03—P10 保留原 `ledger/preflight/live` 范围和预算检查；P07 仅支持账本。P11/P12 保留单状态准入、依赖记录、资源与原数值验收。安装验收不重复历史已通过的 P12，也不自动运行高成本任务。一个新安装中未经实际重算的科学任务必须保持 `NOT_EXECUTED`，不能以登记成功替代数值验收。

P01—P14 历史证据的 Show/Review 是本机只读模块，无须新 Docker 身份，继续通过 `start-local-runtime.ps1` 使用。它不自动下载原始证据；未提供对应来源目录时，缺失项会如实记为 `MISSING`，不能称为完成 P14 复算。用户分子 Check 可通过原启动器显式提供新镜像 ID，须使用该入口自己的请求格式；这里的水分子请求仅用于普通单点服务。ResultReview/Report 继续读取实际记录。条件用户分子的 Compute 仍为 `BLOCKED`；普通 RHF 单点入口不改变这个结论。

WSLc 保持 `BLOCKED`，原 WSL 平台验收暂停。Native WSL2 仍只有已记录的 Check 能力，未开放 Native Compute。镜像分发保持 `BLOCKED`，GitHub Actions 运行仍为 `NOT_EXECUTED`。L4 可以保存检查点，仍不支持恢复运行。
