# 从源码安装本地 Runtime

## 本页安装什么，哪些步骤只需首次做？

本页是统一Runtime源码与共用Docker计算环境的安装说明，不是某个模块的独立安装包。取得源码后仍需准备依赖并构建本地镜像；专用源码ZIP不含完整已安装环境，指南ZIP不能代替安装。prepare/build在首次建立这份环境或另行建立新环境时执行，不用每次计算都构建。

只做普通RHF时，可直接按[完整RHF安装与使用步骤](CURRENT_MOLECULAR_SINGLE_POINT_zh-CN.md)操作，首次仅登记 `molecular-service`。下文另外三个服务是按需登记的选项，不要求全部登记，也不会自动启动计算。原七任务／P14另有独立构建与身份合同；已有镜像和服务记录的用户直接进入对应运行步骤，保留原记录。

当前服务选择与验收范围统一见 [能力注册表v2](../configs/runtime-capabilities-v2.json)和 [专业服务矩阵](CURRENT_PROFESSIONAL_SERVICES_zh-CN.md)。源码与静态用户指南已公开；本页的受限安装验收属于2026-10-09记录，不赋予之后的代码或新镜像历史科学资格。

本入口为已有服务提供独立的本地安装身份。它不公开镜像，不把历史候选的科学验收结论赋予新镜像，不修改原科研环境、WSL 设置或原来源锁。

2026-10-09 [干净目录受限安装验收](SOURCE_INSTALLATION_ACCEPTANCE_20261009_zh-CN.public.md)已通过：公开下载、构建、四类身份登记、45 项工程测试及四个小任务。高成本任务没有重放；全新机器的验收尚未执行。

## 环境与下载

v0.1.0的[Release附件](https://github.com/CCcolab/AI4OrgChem-Runtime/releases/tag/v0.1.0)提供 `AI4OrgChem-Runtime-source-v0.1.0.zip`，该专用源码ZIP带本项目Git身份证明；解压到全新目录，进入包含scripts的目录后继续下方prepare/build流程。`AI4OrgChem-Runtime-guide-v0.1.0.zip`只是网页指南，不能用于安装。GitHub自动的Source code ZIP仍不替代专用安装源码包。

需要 Python 3.12 或更新版本、可用的 Linux/amd64 Docker 引擎，以及构建时访问 GitHub、PyPI、Docker Hub 和 Debian 软件源的网络。使用 Git 克隆时需要已有 Git。主机 Python 只运行标准库脚本，不在主机或原 WSL 科研环境中安装科学依赖。首次构建下载约 161 MB 的 Python 依赖，另外需要基础系统镜像和 Git 系统包。磁盘与任务资源仍由各服务的原预检核查。原用户分子 Check/Report 的 PowerShell 启动器另需已有 PowerShell 7.3+。

可以在 Git 克隆目录运行，或使用本项目 `install-local-runtime.py package` 制作的安装源码 ZIP。该 ZIP 携带 Git commit/tree/blob 身份证据，不含镜像、wheels 或旧 `science.tar`。普通 GitHub 自动源码 ZIP 尚不携带本安装证据，使用它时应改用 Git 克隆或本项目制作的安装 ZIP；不要自行改写身份清单。

公开源码仓库为 [CCcolab/AI4OrgChem-Runtime](https://github.com/CCcolab/AI4OrgChem-Runtime)，可使用Git克隆；静态 [用户指南](https://cccolab.github.io/AI4OrgChem-Runtime/)可直接阅读。公开预构建镜像仍未提供。安装源码ZIP须由本项目package命令制作并保留身份清单，普通GitHub自动ZIP的上述限制保持。

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

当前安装使用 `REVIEWED_PUBLIC_PAYLOAD_WITH_LOCAL_TESTS_V4`（工程来源合同，不是发行版本）。原四份来源清单逐字保留，独立安装上下文另存 `*.installation-baseline.json`；精确测试排除和允许工程覆盖分别登记，新宿主路径重新核对完整派生合同，科学文件不允许遗漏。

| 家族 | 原清单 | 安装保留 | 测试排除 | 工程覆盖 | 其余不变 |
| --- | ---: | ---: | ---: | ---: | ---: |
| molecular-service | 20 | 20 | 0 | 3 | 17 |
| registered-cases | 37 | 37 | 0 | 3 | 34 |
| protocol-cases | 118 | 113 | 5 | 5 | 108 |
| high-cost-cases | 107 | 100 | 7 | 7 | 93 |

具体排除行、覆盖路径和精确新旧哈希见 [绑定实现](../scripts/installation_source_bindings.py)，每个 installation-record 的 source_catalog_binding 保留完整对应关系。共享宿主安全与绑定器另进入 host/inventory 身份。历史 V3／V4验收属于各自原提交，新宿主的预算与隔离修订不转授数值资格。

更新后的启动器不能冒充历史候选镜像；应从干净已提交源码准备新的上下文、构建并独立登记。旧2026-10-09安装记录仍可审阅，本次合同不会修改或转授其数值结论。新公开安装CI只验证公开固定来源、构建、四类身份登记及标准库文件探针，不重算历史分子。

Linux 的输出目录必须允许 UID/GID `10001:10001` 写入。监督器先执行零科学调用的实际目录写入探针；不可写或未知会在进入科学 worker 前拒绝。宿主用户仍须能创建运行目录；仅将顶层目录chown给10001可能妨碍宿主创建，而且宿主新建子目录的权限不一定继承。已有`setfacl`时，可为**新建专用输出根**授予10001访问及默认继承ACL（保留宿主属主），然后以实际探针核查，例如：

```bash
mkdir -p "$HOME/ai4orgchem-runs"
setfacl -m u:10001:rwx -m d:u:10001:rwx "$HOME/ai4orgchem-runs"
```

上述路径应由用户选择，不要套用到已有科研目录。没有ACL工具时，应由系统维护者准备宿主与worker均可写的专用目录；本项目不会自动安装系统包或宽泛修改权限，也不使用`chmod 777`。Windows Docker bind 的可写性同样以实际探针为准。CI的UID1000/0755负例与新建10001专用目录正例只验证文件I/O，不声称已经测试所有宿主ACL配置。

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

普通 Native WSL2 仍只有已记录的 Check 能力，未开放 Native Compute，不能继承 Docker 的计算验收。镜像分发保持 `BLOCKED`。[Actions run38003025857](https://github.com/CCcolab/AI4OrgChem-Runtime/actions/runs/38003025857)对86e29b47三个既有job成功，覆盖登记工程合同和旧L0/L1；不代表全部科学服务或本轮新安装路径已通过该次CI。L4可以保存检查点，仍不支持恢复运行。

四家当前操作入口：[普通分子](CURRENT_MOLECULAR_SINGLE_POINT_zh-CN.md)、[固定案例](CURRENT_REGISTERED_CASES_zh-CN.md)、[专题](CURRENT_PROTOCOL_CASES_zh-CN.md)、[高成本](CURRENT_HIGH_COST_CASES_zh-CN.md)。原七任务／P14是[独立构建与身份合同](CURRENT_P14_BUILD_RUN_zh-CN.md)，不属于四家登记器。
