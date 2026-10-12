# 当前固定案例：统计、图账本、轨道密度

本页提供统计、图规则与轨道表示的固定案例的安装与使用说明。任务使用登记对象与协议，不接收自己的XYZ；自己的分子应使用[普通RHF入口](CURRENT_MOLECULAR_SINGLE_POINT_zh-CN.md)。

## 1. 首次准备共用 Runtime 环境

本模块共用[统一Runtime源码与Docker环境](SOURCE_INSTALLATION_zh-CN.md)，没有单独的模块安装包。已有该安装的built-image.json时跳到第2步；已有本服务installation-record.json时直接选择并运行任务。不要重复构建、覆盖登记或要求全部模块一起运行。

首次需要已有Git、Python3.12+、Docker Linux/amd64引擎及构建网络；计算/容器内账本运行时也需要Docker可用。下面各目标目录应全新，在Windows PowerShell执行；专用源码ZIP、下载校验和Linux输出权限条件见统一安装页。

```powershell
git clone --branch main https://github.com/CCcolab/AI4OrgChem-Runtime.git D:\chem-work\runtime-source
Set-Location 'D:\chem-work\runtime-source'
git rev-parse HEAD
python -B .\scripts\install-local-runtime.py prepare --destination D:\chem-work\runtime-install
python -B .\scripts\install-local-runtime.py build --destination D:\chem-work\runtime-install
```

上面从 `runtime-source` 准备并构建；后续工作目录是 `runtime-install\runtime`，并不是下载源码目录。built-image.json位于runtime-install根目录，installations和runs位于该runtime目录的同级。失败时先查安装日志，不进入计算或更改科学规则。

## 2. 只登记所选服务（首次一次）

仅登记 `registered-cases`。读取本次构建标签，输出登记目录必须不存在；已有记录保留。登记保存和校验身份，不启动计算；新镜像不继承旧科学PASS。本文修订没有执行下面的构建或计算。

```powershell
Set-Location 'D:\chem-work\runtime-install\runtime'
$installed = Get-Content ..\built-image.json -Raw | ConvertFrom-Json
python -B .\scripts\register-installation.py --service registered-cases --image $installed.local_tag --output-dir ..\installations\registered-cases
```

## 3. 按研究目的选择固定任务

按研究目的选择一个固定任务；不是任意分子入口，不接受用户 request，也不更改分片、几何、基组或容差。

| 模块 | 真实 task | 科学调用范围 |
| --- | --- | --- |
| 结构与光谱表值统计 | p02-statistics | 固定表值拟合，零 SCF |
| 共轭图规则与能量账本 | p13-graph-ledger | 固定图/RDKit及保存账本，零新 QM |
| 轨道表示与密度对照 | p01-orbital-density | 固定乙烯 RHF、Boys、PM 各一次；需实际计算授权 |

## 4. 运行所选任务

选择下面的一条命令单独执行；不是要求三项全部运行。统计／图账本不产生新量子能量；轨道控制会实际计算一次登记乙烯。

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\registered-cases\installation-record.json --task p02-statistics --output-root ..\runs\p02-statistics-new
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\registered-cases\installation-record.json --task p13-graph-ledger --output-root ..\runs\p13-graph-ledger-new
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\registered-cases\installation-record.json --task p01-orbital-density --output-root ..\runs\p01-orbital-density-new
```

## 5. 查看结果、资源和适用范围

以上是可选操作说明，本轮没有执行。1 CPU/线程、1 GiB、120 秒硬限。保存终端 records 中的 `output/case/case-report.md`、`case-result.json` 及完整回执。执行、数值资格、比较量及科学解释分别判读。

历史旧镜像和旧 start-registered-case.ps1 操作见 [历史固定案例指南](REGISTERED_CASES_zh-CN.md)；不把新安装镜像交给它。

从终端报告的实际运行目录打开 `output/case/case-report.md`。保存 `output/case/case-result.json`、`output/guard-receipt.json`、资源、worker与host回执及manifest。P02重点读拟合与参照残差，P13重点读图规则与账本恒等式，P01重点读密度／能量不变量与占据表示变化。模块命令相同环境不代表结果schema或解释完全相同；见[专业服务矩阵](CURRENT_PROFESSIONAL_SERVICES_zh-CN.md)。缺文件、身份不符、检查失败时保留实际状态，不因进程退出0补写PASS。
