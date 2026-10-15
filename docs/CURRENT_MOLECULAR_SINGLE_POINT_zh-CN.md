# 自己的分子：RHF 单点计算安装与使用

本模块在你提供的XYZ几何上计算RHF/6-31G(d)单点能量，保存正则轨道和自旋求和的AO密度矩阵。支持H/C/N/O、中性闭壳层单重态、最多20原子、实际AO≤80；不优化结构，不自动加氢或判断真实基态。

## 安装的是整个 Runtime，还是单独的 RHF？

[从源码安装本地Runtime](SOURCE_INSTALLATION_zh-CN.md)是**统一的Runtime源码与共用Docker环境安装流程**，不是单独的RHF安装包。**只做RHF时，仅登记 `molecular-service` 即可，不需要登记或运行其他三个服务家族。** 登记只检查并保存镜像身份，不启动计算；原七任务／P14另有独立构建合同。

专用 `AI4OrgChem-Runtime-source-v0.1.0.zip` 是带安装身份证明的源码包，不含完整已安装环境；指南ZIP只供阅读。源码仍需prepare/build。首次安装需要已有Python3.12+、Git（克隆时）、Docker Linux/amd64引擎和构建网络。运行计算需要Docker可用，阅读指南不用启动Docker。

| 当前情况 | 从哪里开始 |
| --- | --- |
| 首次使用，尚未取得源码或构建环境 | 第1步 |
| 已有本次安装的built-image.json，但未登记RHF | 第3步 |
| 已有该服务installation-record.json | 第4或第5步；不用重建或覆盖登记 |

下面是Windows PowerShell操作说明，示例路径可换成自己的独立目录；本文修订没有执行构建或计算。

## 1. 取得 Runtime 源码

取得当前main的维护与使用说明，记录实际提交；目标必须是全新目录：

```powershell
git clone --branch main https://github.com/CCcolab/AI4OrgChem-Runtime.git D:\chem-work\runtime-source
Set-Location 'D:\chem-work\runtime-source'
git rev-parse HEAD
```

也可解压[正式Release的专用源码附件](https://github.com/CCcolab/AI4OrgChem-Runtime/releases/tag/v0.1.0)，进入包含scripts的根目录；它固定在v0.1.0，不含之后的main文档。普通GitHub自动Source code ZIP缺少本安装流程所需身份证明。完整下载与校验条件见[安装说明](SOURCE_INSTALLATION_zh-CN.md)。

## 2. 在本机构建共用环境

在第1步的源码目录执行，安装目标runtime-install必须不存在：

```powershell
python -B .\scripts\install-local-runtime.py prepare --destination D:\chem-work\runtime-install
python -B .\scripts\install-local-runtime.py build --destination D:\chem-work\runtime-install
```

prepare取得并核对固定科学源码与依赖；build实际构建本地镜像。失败时先读安装日志，不进入计算、不重置旧环境或更改科学规则。

```text
D:\chem-work\runtime-source\                  下载源码；从这里执行prepare/build
D:\chem-work\runtime-install\built-image.json  新构建镜像记录
D:\chem-work\runtime-install\runtime\         后续登记和运行命令的工作目录
D:\chem-work\runtime-install\installations\   服务登记生成的身份记录
D:\chem-work\runtime-install\runs\            运行命令生成的新输出
```

## 3. 只登记 RHF 服务（首次一次）

进入安装器生成的runtime目录，读取本次built-image.json的本地标签。登记输出目录必须不存在，已有记录不要覆盖。新镜像不继承历史科学验收，旧候选启动器不接收该新镜像。

```powershell
Set-Location 'D:\chem-work\runtime-install\runtime'
$installed = Get-Content ..\built-image.json -Raw | ConvertFrom-Json
python -B .\scripts\register-installation.py --service molecular-service --image $installed.local_tag --output-dir ..\installations\molecular-service
```

以后一直使用这份 `..\installations\molecular-service\installation-record.json`；登记成功不等于已经完成RHF计算。

## 4. 先跑通随包水分子示例

仍在第3步的runtime目录执行。这条命令实际运行一个RHF单点，输出目录必须全新：

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\molecular-service\installation-record.json --task single-point --request .\examples\molecular-service\water\request.json --output-root ..\runs\water-new
```

水示例是技术固定几何，不是已优化或认证的实验结构。失败时保存本次错误和日志；有输出文件不等于成功，不覆盖旧运行自动重试。

## 5. 换成自己的分子

把XYZ和请求JSON放在同一新分子目录。坐标单位为Å；XYZ第一行填原子数，第二行为注释，之后每行是元素和三个坐标。可复制[水示例XYZ](../examples/molecular-service/water/molecule.xyz)和[请求模板](../examples/molecular-service/water/request.json)，替换成自己确认的结构；`structure.file` 填同目录XYZ的基本名，不填绝对路径。

采用中性闭壳层单重态RHF/6-31G(d)模型；H/C/N/O、≤20原子、实际AO≤80。偶电子与单重态声明不能证明真实分子适合闭壳层单行列式。使用同一安装记录和不同的全新输出目录：

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\molecular-service\installation-record.json --task single-point --request D:\chem-work\my-molecule\request.json --output-root ..\runs\my-molecule-new
```

水示例和自己的分子分别保留各自运行。资源为1CPU/线程、1GiB、120秒硬限、100秒软停，最多一次RHF kernel、100轮SCF，无自动重试或恢复。命令不会由文档自动执行；不通过改变profile或容差绕过支持范围。

## 6. 阅读结果并保留记录

读取终端返回的 records 目录：`output/calculation/report.md`、`result.json`、`orbitals-density.npz` 和完整 host/worker/guard/资源回执，整目录保留。账本与残差位于 `result.json` 的 `diagnostics.energy_ledger`、`diagnostics.orbital_summary`、`diagnostics.checks`、`diagnostics.residuals`。

首版数值门禁仅限定指定几何 RHF 的已登记检查。所有 canonical 轨道，尤其虚空间，不因现有布尔值通过而取得全空间资格；全 MO 本征残差只是诊断。新宿主回执的 `evidence_review.qualification_scope` 与 `evidence_review.orbital_export_qualification` 明确该限制。全轨道正交／本征门禁的新版本尚未实现；稳定性与物理基态认证未执行。原四分子结果及12项门禁不改写。

历史候选环境的操作与身份见 [历史普通服务节选](MOLECULAR_SINGLE_POINT_zh-CN.public.md)，只适用于其原候选镜像。当前安装不要使用其中的 start-molecular-service.ps1。

[完整 MO 附加只读审查](CANONICAL_ORBITAL_REVIEW_zh-CN.md)已提供独立工具；尚未接入冻结生产门槛，稳定性仍未执行，不改写历史验收。
