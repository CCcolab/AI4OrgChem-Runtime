DOCUMENTATION / 使用与复核

# AI4OrgChem Runtime 用户指南

面向分子研究的本地计算与可追溯复核

自己的XYZ分子固定案例分析模块完整结果与运行记录

<a id="toc"></a>
[01 项目与计算模块](#overview)[02 本地环境与文件准备](#quick-start)[03 计算自己的分子](#user-molecule)[04 查看结果与保存记录](#results)[05 固定案例与分析模块](#tasks)[06 帮助与来源](#help)

选择研究目标，查看对应模块与步骤。
阅读指南无需启动计算环境；运行命令时使用本地Runtime。

<a id="overview"></a>

01 / PROJECT

## 本地分子计算与结果复核

AI4OrgChem Runtime 面向化学研究用户，将分子输入、计算执行和结果记录组织为可复用的本地工作流程。

项目目标是帮助你获得分子能量、轨道与密度信息，开展固定协议对照，并保存可追溯的研究记录。网页负责选择模块和指导操作，计算在你的本地环境执行。

<a id="home-single-point"></a>

自己的分子

### RHF 单点能量、轨道与密度矩阵

提交XYZ结构与计算请求，获得总能量、canonical轨道、AO密度矩阵、占据数和完整运行记录。

当前适用：H/C/N/O，中性单重态，RHF/6-31G(d)，最多20原子且AO数不超过80。

[查看四步计算指南 →](#user-molecule)

<a id="home-modules"></a>

### 按研究目标选择分析与复算模块

以下14个模块使用随项目提供的固定案例和协议；点击模块名称查看输入、运行方式和结果解释。

#### 轨道与密度对照

- [轨道表示与密度对照](#case-p01-orbital-density)乙烯固定案例：轨道表示变化与密度、能量不变量
- [局域化端点与参照能量](#case-protocol-p08)丁二烯固定案例：局域化端点与参照能量

#### 结构数据与图规则

- [结构与光谱表值统计](#case-p02-statistics)已提供表值：统计、拟合与残差分析
- [共轭图规则与能量账本](#case-p13-graph-ledger)固定分子图：图规则检查与能量账本

#### 条件能量与片段分析

- [π–π条件态与轨道响应](#case-protocol-p04)固定双状态：直接项与轨道响应
- [π–σ条件能量对照](#case-protocol-p05)固定角度：条件能量比较
- [片段条件能量组装](#case-protocol-p06)固定双片段：条件能量独立组装

#### 构型与能量响应

- [扭转构型端点与能量账本](#case-protocol-p03)固定扭转端点：单点能量与账本对照
- [键长交替与能量响应](#case-protocol-p10)苯固定五点几何：普通DFT能量响应
- [条件能量与结构响应复核](#p14-tasks)固定应变体系：条件能量与结构端点联合复核

#### 能量闭合与状态诊断

- [能量账本闭合校验](#case-protocol-p07)保存账本：同一哈密顿量下的路径闭合校验
- [条件态与稳定性诊断](#case-protocol-p09)环丁二烯固定几何：条件态诊断

#### 固定体系多态与尺寸对照

- [多态约束结构优化](#case-p11-high-cost)固定多态任务；从苯G先导示例开始
- [环状体系尺寸与状态对照](#case-p12-high-cost)固定环状尺寸与状态任务；从N12-G先导示例开始

这组是高成本固定任务：当前验收起点为上述两个先导，完整状态集合需按预算分态执行。

<a id="home-start"></a>

### 从这里开始

**计算自己的分子**

[准备XYZ → 运行单点 → 读取报告](#user-molecule)

**学习与复算示例**

[选择固定案例模块与运行步骤](#home-modules)

**查阅已有证据**

[按模块读取结果与来源](#proposition-catalog)

第一次使用可先运行水分子示例。[查看本地安装与环境准备](#source-installation)，或[了解结果与记录的保存方式](#results)。

### 需要深入复核？查看专业阅读路径

S1—S6提供协议查阅、实现审查、运行资格、固定几何、结构响应及联合复核的专业材料。

[打开专业服务指南](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/PROFESSIONAL_SERVICES_zh-CN.public.md)

<a id="quick-start"></a>

02 / QUICK START

## 本地准备：按目标确认条件

<a id="source-installation"></a>

### 从源码安装：新用户水分子起点

先取得 Runtime Git 克隆（需要Git），或本项目带 Git commit/tree/blob 证据的安装源码ZIP。公开源码位于[CCcolab/AI4OrgChem-Runtime](https://github.com/CCcolab/AI4OrgChem-Runtime)，可按下方命令Git克隆；v0.1.0的[Release附件](https://github.com/CCcolab/AI4OrgChem-Runtime/releases/tag/v0.1.0)提供带身份证明的source-v0.1.0源码ZIP；guide-v0.1.0只是网页包。普通GitHub自动ZIP不可替代专用安装源码包。网页ZIP不是安装源码包，不含镜像或依赖。

需要自己的 Python3.12+、Docker Linux/amd64；构建网络需访问 GitHub / PyPI / DockerHub / Debian。选择全新的独立目录，不覆盖科研工作区。

<a id="source-install-command"></a>

```powershell
# 取得源码：使用全新的独立目录，记录所选提交
New-Item -ItemType Directory -Path D:\chem-work -Force
git clone https://github.com/CCcolab/AI4OrgChem-Runtime.git D:\chem-work\runtime-source
Set-Location D:\chem-work\runtime-source
git rev-parse HEAD

python -B .\scripts\install-local-runtime.py prepare --destination D:\chem-work\runtime-install
python -B .\scripts\install-local-runtime.py build --destination D:\chem-work\runtime-install

# 进入安装器生成的工作目录，读取实际新镜像标签
Set-Location D:\chem-work\runtime-install\runtime
$installed = Get-Content ..\built-image.json -Raw | ConvertFrom-Json
python -B .\scripts\register-installation.py --service molecular-service --image $installed.local_tag --output-dir ..\installations\molecular-service
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\molecular-service\installation-record.json --task single-point --request .\examples\molecular-service\water\request.json --output-root ..\runs\water
```

prepare 下载固定公开来源591项、21 wheel + 1源码包；geomeTRIC 在镜像内构建，不升级宿主。build、installation identity 与科学证据分层，不互相代替。registered-cases / protocol-cases / high-cost-cases 分别登记自己的 installation-record，不继承历史PASS。

水完成后，进入[自己的XYZ/request指南](#user-molecule)。普通H/C/N/O、电荷0、单重态、RHF/6-31G(d)、≤20原子、实际AO≤80保持；普通请求与旧条件态Check不能混用。

### 安装候选身份与受限验收

候选源码：` 575127b94214ca1a3c605bd2139bf77ba7e5dd1d `
受测构建：` 59f576c5a11f7192d0425765611a49369c6f561a `
新镜像：` sha256:a4086d916101ab16650a878971361b5ee6e4e7f9e62b7d750f672825b6bbe96f `

来源记录：45项工程PASS + 水单点 / P02统计 / P13图账本 / P07账本。不是全部科学任务认证；高成本新镜像重放 NOT\_EXECUTED。公开分发 BLOCKED，但支持从固定公开来源自行本地构建。

新安装的普通、固定、专题和高成本服务均使用各自登记的 installation record。旧候选启动器只用于原环境复核，不把新镜像直接交给只接受旧身份的入口。

先选择目标，不统一要求Docker。进入实际Runtime源码根目录后，在自己的本地终端操作；网页不检测电脑、不安装工具、不启用WSL功能。

| 用户要做什么 | 本地所需条件 |
| --- | --- |
| Capabilities／List／Show／Review | Runtime源码；Windows PowerShell 5.1或可用PowerShell；已有Python3.12+。Review另需自己持有的固定科学源码目录。 |
| 普通RHF单点 | Python3.12+；Windows PowerShell 5.1或PowerShell 7；Docker Linux/amd64与本次 ` molecular-service/installation-record.json ` 登记的镜像。不要求pwsh。源码、网页与镜像分别准备；无公开安装镜像地址。 |
| 3项固定服务 | Python3.12+；Windows PowerShell 5.1或PowerShell 7；Docker Linux/amd64与本次 ` registered-cases/installation-record.json ` 登记的镜像。不要求pwsh；不与普通服务混用镜像。 |
| 旧固定七任务／条件能量与结构响应复核（独立环境） | 可用Docker Linux/amd64引擎；旧任务匹配镜像；已有PowerShell7.3+；持久输出与有效资源。入口可从PS5.1寻找已有PS7。不与普通服务共用环境合同。 |
| 用户分子Check | 本地源码、请求及XYZ；用户分子r3候选或独立验收的匹配环境；Docker、已有PS7.3+。 |
| 用户服务Report | 既有服务运行目录；基础Report需已有PS7.3+；高级只读／导出另需Python3.12+。Report不需要Docker。 |

<a id="build"></a>

### 源码、网页与环境不是同一种交付

网页ZIP只是网页；Runtime Git／带manifest的项目来源ZIP是源码；Docker镜像与依赖是另外的环境条件。普通GitHub ZIP不替代项目来源ZIP，也不存在下载即用的完整Runtime安装包。源码地址已公开；公开预构建镜像分发仍受限制。用户可从固定来源自行构建，不能把网页 ZIP 当作安装包。

可显式指定 ` -PythonExecutable `、` -PowerShell7 `；占位路径必须替换为本机已有的真实可执行文件。不要把Codex工具目录当成外部用户必有路径。

### 按目标手工核对（不是自动检测）

**宿主查阅／Review**

核对源码根目录、PowerShell及Python；Review另核对固定科学来源与全新外部输出目录。

**普通RHF单点**

核对源码、Python3.12+、PowerShell 5.1或7、Docker Linux/amd64与本次 molecular-service installation record 登记的镜像；不要求pwsh。

**3项固定服务**

核对源码、Python3.12+、PowerShell 5.1或7、Docker Linux/amd64与本次 registered-cases installation record 登记的镜像；不要求pwsh。

**旧专项条件**

旧七任务／P14与旧条件态Check／Report的条件只在下方对应专项折叠中核对，不计入普通服务必需条件。

<a id="manual-checklists"></a>

<a id="checks-single-point"></a>

### 普通RHF单点手工核对（与旧条件态r3分开）

Runtime源码、Python3.12+、PS5.1或7、Docker Linux/amd64与本次 molecular-service installation record 登记的镜像；不要求pwshrequest.json与XYZ同一真实目录、basename匹配；全新外部输出目录

<a id="checks-evidence"></a>

### 宿主源码 / Review 手工核对

源码根目录、PowerShell、Python3.12+Review固定科学源码与全新外部输出目录

<a id="checks-registered"></a>

### 3项固定服务手工核对

Runtime源码、Python3.12+、PowerShell 5.1或7、Docker Linux/amd64与本次 registered-cases installation record 登记的镜像；不要求pwsh保留固定输入与容差，使用全新外部输出目录

<a id="legacy-p14-checks"></a>

### 旧七任务／条件能量与结构响应复核专项条件（仅运行旧任务时需要）

<a id="checks-p14"></a>

### 固定协议复核手工核对

Docker Linux/amd64、适用镜像、已有PS7.3+持久输出目录与有效资源

<a id="legacy-condition-checks"></a>

### 旧条件态Check／Report专项条件（普通RHF单点不需要）

<a id="checks-check"></a>

### 用户分子 Check 手工核对

源码、请求JSON、实际XYZ与匹配r3环境Docker、已有PS7.3+与资源合同

<a id="checks-report"></a>

### 服务 Report 手工核对 · 无Docker

既有服务运行目录、已有PS7.3+；不需要Docker高级只读/导出另需Python3.12+及全新导出目录

<a id="proposition-count"></a>

14 个计算模块；固定案例与证据复核，始终可读，不参与任务筛选。

<a id="check-status"></a>

按所选目标核对对应条件；未执行检测，不设统一完成计数。

### 宿主源码入门：读取能力和计算模块目录

<a id="evidence-command"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Capabilities
./scripts/start-local-runtime.ps1 -Action List
```

上述命令只读取能力和计算模块目录；本轮是按任务书核对的接口示例，不是本网页执行结果，也不是L0 Docker冻结证据检查。

<a id="user-molecule"></a>

03 / SINGLE POINT

## 计算自己的分子

普通RHF单点服务已存在：以下四步在你的本地终端执行，默认任务为single-point，不是旧条件态Check或Compute。

### 首版支持范围

H/C/N/O；charge 0；multiplicity 1；正偶电子；RHF / 6-31G(d)；1–20原子，actual AO ≤80。允许三维结构，无A/B、xy平面或PID要求。

1 CPU、1线程、1 GiB；100s软限、120s硬限；无额外swap；≤1 kernel；最多100轮SCF。无retry / resume / fallback。

自选分子的普通DFT尚未开放；部分固定协议已有受限RKS/GL/条件核。离子、开壳层、其他元素、网格、用户局域化、优化与扫描等普通服务限制不变。

### 输入工程几何检查（不是几何认证）

坐标分量绝对值≤10000 Å，核距≥0.5 Å。输入是工程几何，不认证实验结构；不优化、不补氢、不重排原子。

### 步骤1 · 进入已登记的安装工作目录

先完成上方源码安装并登记普通分子服务，再进入同一个安装工作目录；按自己的实际安装位置替换示例路径。

<a id="single-point-location-command"></a>

```powershell
Set-Location 'D:\chem-work\runtime-install\runtime'

```

### 步骤2 · 准备请求与XYZ

水模板为固定工程几何，不是优化或实验认证结构。下载后把request.json与molecule.xyz放在同一个真实目录；structure.file填写XYZ basename。XYZ首行原子数必须与坐标行数一致，单位angstrom。自己的分子请替换XYZ，并保持首版范围。

<a id="single-point-request-json"></a>

```json
{
  "basis": "6-31G(d)",
  "charge": 0,
  "method": "RHF",
  "multiplicity": 1,
  "profile": "rhf-631gd-small-v1",
  "schema": "molecular-single-point-v1",
  "structure": {
    "file": "molecule.xyz",
    "format": "xyz",
    "unit": "angstrom"
  },
  "task": "single-point"
}

```

<a id="single-point-xyz-text"></a>

```text
3
Technical fixed geometry; not optimized or authenticated experimental structure
O 0 0 0
H 0 -0.757 0.587
H 0 0.757 0.587

```

UTF-8原文：请求277 bytes，水XYZ 123 bytes；保留LF结尾换行。复制与保存均不运行计算。

### 步骤3 · 在本地运行普通单点

先运行安装目录中已有的水示例，沿用安装时登记的同一份普通分子 installation record。输出选择源码、输入与历史记录之外的全新目录，不覆盖旧记录。

<a id="single-point-command"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\molecular-service\installation-record.json --task single-point --request .\examples\molecular-service\water\request.json --output-root ..\runs\water-followup

```

自己的 request.json 与 XYZ 同放在 my-molecule 实际目录。structure.file 按请求文件所在目录解析，填写 XYZ basename；下面只替换请求和全新输出目录，installation record 保持相同。

<a id="single-point-custom-command"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\molecular-service\installation-record.json --task single-point --request D:\chem-work\my-molecule\request.json --output-root ..\runs\my-molecule

```

### 步骤4 · 读取报告并保存完整记录

把占位符替换为终端打印的records实际路径。保存整个records目录，不仅保存报告；保留失败与拒绝状态，不记零、不覆盖历史。

<a id="single-point-report-command"></a>

```powershell
$records = '<终端 records 的实际路径>'
Get-Content -LiteralPath (Join-Path $records 'output\calculation\report.md') -Encoding UTF8

```

<a id="ordinary-candidate-history"></a>

### 历史普通分子候选环境入口（新安装不使用）

原 start-molecular-service.ps1 仅接受旧 candidate-image 登记的镜像身份。其历史验收见普通分子结果记录；不得用该入口运行新安装镜像，也不取消镜像身份核对。

<a id="conditional-state-history"></a>

### 专项：条件态输入检查与历史诊断（普通单点不需要）

### 旧条件态：自己的分子准备、检查与报告

本折叠内所有Check、Report、Compute与历史诊断均属于旧条件态服务；任意用户分子的旧条件态比较Compute关闭不表示普通RHF单点不存在。原ID、命令与夹具保留。

你可以准备受限范围内的XYZ和请求文件，在自己的电脑上运行Check，随后读取或导出Report。Check不计算两态能量；正式用户分子Compute目前未开放。独立服务线，不继承固定七任务科学验收。

### 01 找现成示例

` examples/user-molecule/w05-candidates/ethene-planar-technical-v1/ `中的molecule.xyz与request-pilot.json是一对六原子乙烯工程夹具。本次已提供XYZ原文，以下仅静态核对已有六原子乙烯工程夹具；单位angstrom，保持碳1/2原子顺序，A=\[1\]、B=\[2\]。无期望能量，不作研究结果，不运行计算。

以下为已读 request-pilot.json 完整原文，静态内联保留原 text，不是重构请求。research\_question 中“方法范围待审”为原始夹具的历史声明；当前专家咨询已取消，不构成批准，任意用户分子的旧条件态比较Compute 仍因数值与研究资格不足而 BLOCKED。XYZ原文已提供并静态内联；逐字复制、导出与运行验证均为NOT\_EXECUTED。

<a id="molecule-request-json"></a>

```json
{
  "schema_version": 1,
  "service": "user-molecule-fixed",
  "geometry_file": "molecule.xyz",
  "coordinate_unit": "angstrom",
  "charge": 0,
  "multiplicity": 1,
  "research_question": "W05 候选夹具：指定条件定义的代码验证；方法范围待审，尚不开展研究计算",
  "condition_definition_acknowledged": true,
  "fragments": [
    {
      "id": "A",
      "carbon_atom_indices_1based": [
        1
      ]
    },
    {
      "id": "B",
      "carbon_atom_indices_1based": [
        2
      ]
    }
  ],
  "condition_profile": "cross-fragment-pi-2011-v1",
  "calculation_profile": "pilot-b3lypg-sto3g-grid2-v1",
  "resources": {
    "threads": 1,
    "memory_limit_mib": 512,
    "wall_time_limit_seconds": 60
  }
}
```

molecule.xyz 本次上传原文（8行，保留结尾换行）。注释中的 method review pending 是历史夹具注释，不用作当前等待专家状态；现外部咨询 CANCELLED\_BY\_USER，任意用户分子的旧条件态比较 Compute BLOCKED。

<a id="molecule-xyz-text"></a>

```text
6
W05 candidate fixed geometry; method review pending; no expected energy
C -0.67 0.0 0.0
C 0.67 0.0 0.0
H -1.215 0.9439676901250381 0.0
H -1.215 -0.9439676901250381 0.0
H 1.215 0.9439676901250381 0.0
H 1.215 -0.9439676901250381 0.0
```

### 02 理解编号与A/B

XYZ单位angstrom，保持原子原顺序；中性C/H、闭壳层单重态、既定xy定向。碳索引1-based，A/B非空、不重叠且覆盖碳，不给氢分组。夹具A=\[1\]、B=\[2\]，请求1线程、512MiB、60秒仅工程示例。

不自动旋转、补氢、重排或由SMILES生成可信构型。条件屏蔽指定跨组π项，不是全部跨组作用。条件定义确认不等于方法批准。

请求包含geometry\_file、coordinate\_unit、charge、multiplicity、research\_question、condition\_definition\_acknowledged、fragments、condition\_profile、calculation\_profile、resources。

### 03 本地Check

进入Runtime源码根目录；匹配r3环境必须已具备，登记于validation/user-molecule/candidate-image.json，不用旧P14镜像、不自动安装。

<a id="molecule-check-command"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Check `
  -Request '.\examples\user-molecule\w05-candidates\ethene-planar-technical-v1\request-pilot.json' `
  -OutputRoot 'D:\your-work\check-runs'
```

保存启动器打印的新目录；检查输入与AO元数据，不运行SCF、网格或完整ERI，不生成分子能量result。

### 04 Report／导出

YOUR\_CHECK\_RUN替换为实际目录。Report无Docker，仅匹配既有服务记录，不是旧P14或根诊断的通用读取器。

<a id="molecule-report-command"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Report `
  -RunDirectory 'D:\your-work\check-runs\YOUR_CHECK_RUN'
```

### 高级只读核对与全新导出

<a id="molecule-report-export-command"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Report `
  -RunDirectory 'D:\your-work\check-runs\YOUR_CHECK_RUN' `
  -PythonExecutable 'C:\your-python\python.exe' `
  -ReportExportDirectory 'D:\your-work\exports\one-new'
```

使用已有Python3.12+真实路径与全新导出目录。生成report.md、report-summary.json、run-manifest.json；只读、不变原记录、不生研究能量，失败／未执行照实保留。

### 登记profile与检查合同，不是科研资格

pilot-b3lypg-sto3g-grid2-v1、research-b3lypg-631gd-grid3-v1均为工程候选，任意用户分子的旧条件态比较Compute关闭。Check nAO上限80、解析上限128原子只是合同；请求接受整数线程1—2、内存128—4096MiB、时间1—900秒，不是科研规模、服务资源承诺或资格，实际预检仍可拒绝。

<a id="compute-state"></a>

**旧条件态当前未开放，生产 Compute 为 BLOCKED**

这是静态状态说明，不是计算入口。Check / Report 的工程可用性不意味着生产计算获准。

### 方法与诊断现状（按需查看）· 尚未合格

V2种子与候选求解器已实现并有受限诊断运行，数值资格未通过；原生根诊断亦已实施。最近记录为139NR完成、138回调成功／1截止失败，没有正式根与尾检，原OPEN账本保留；不能推断合格根不存在。

外部专家咨询：CANCELLED\_BY\_USER。咨询不再作为Compute前置条件，取消不构成科学批准。合格条件态端点、完整独立对照、两存储路径等价性与研究／资源资格仍不足，任意用户分子的旧条件态比较Compute保持BLOCKED。

154项停止工程测试仅说明专项工程范围；强杀最终回执未知。本轮依据v0.4任务书静态更新，未读取对应专属记录、未重新运行Runtime或网页测试。

<a id="results"></a>

04 / INTERPRETATION

## 查看结果与保存记录

<a id="ordinary-results"></a>

### 普通RHF：先读报告，再核对完整 records

下列路径相对于实际运行 records 目录；能量单位 Hartree，几何单位 Å。完整目录整体保留，不只保存报告或截图。

| 相对路径 | 读取内容与边界 |
| --- | --- |
| ` output/calculation/report.md ` | 先读：方法、输入、能量账本、数值资格与未执行项。 |
| ` output/calculation/result.json ` | 原子／AO映射、方法、占据、能量与残差；缺失或未知不是0或PASS。 |
| ` output/calculation/orbitals-density.npz ` | 原AO顺序的S、D、canonical系数、能级、占据、F、hcore、VHF；数值数组，不是图片。 |
| ` output/calculation/operation-ledger.json ` | 实际调用账本；不以计划调用代替实际执行。 |
| ` output/worker-receipt.json ` ` host-execution.json ` | 完整worker与宿主资源、退出及清理记录；独立核对容器删除与输出保留。 |
| 输入快照、合同、guard、resource、manifest及其他记录 | 整目录保留，维持来源关系；退出0不等于完整交付。 |

` NUMERICALLY_QUALIFIED_ORDINARY_RHF `要求12项检查全部为真。worker的` PASS_SCOPED_MOLECULAR_SINGLE_POINT `与host退出／资源／容器删除／输出保留分别判读，不合并为科学认证。

<a id="ordinary-numeric-checks"></a>

### 数值详情：12个key及中文说明（阈值仅引用首版合同）

阈值与比较规则以普通RHF首版合同原文为准，本页不另造容差；未知、缺失、未执行均不能填true。

**` scf_converged `**

SCF满足合同收敛条件。

**` closed_shell_occupations `**

闭壳层占据符合规定。

**` electron_number `**

由AO密度与重叠核对电子数。

**` occupied_orthonormality `**

占据轨道在S度量下正交归一。

**` whitened_projector_idempotency `**

白化占据投影幂等性残差。

**` density_reconstruction `**

轨道与占据重建密度的一致性。

**` energy_ledger_closure `**

能量分项账本闭合。

**` whitened_fock_projector_commutator `**

白化Fock与占据投影对易残差。

**` finite_arrays_and_energy `**

数组与能量均为有限值。

**` symmetric_ao_matrices `**

AO矩阵满足合同对称性。

**` ordinary_fock_equals_hcore_plus_veff `**

普通Fock等于hcore加有效势。

**` package_energy_ledger_closure `**

封装输出能量账本闭合。

AO自旋求和密度矩阵不是实空间网格、等值面或实验密度。canonical轨道不作化学分类；同PySCF直接参考仅验证封装一致性，不是独立引擎认证。收敛不等于稳定极小或基态；稳定性为NOT\_EXECUTED。HOMO／LUMO仅观察，不套用旧条件态正能隙门槛。

<a id="ordinary-orbital-qualification"></a>

### 轨道输出的资格范围与单重态假设

首版十二项数值门槛用于指定几何的普通 RHF 端点，包含占据空间与密度重构检查；不认证完整虚轨道空间或全部轨道本征方程。canonical 系数与能级可用于观察，不能由端点数值资格推断全部轨道已合格。新宿主在 host-execution.json 的 evidence\_review.orbital\_export\_qualification 分别记录这一范围。闭壳层单重态是用户选择的模型假设，不是实际分子基态或自旋状态认证；波函数稳定性尚未执行。新增完整轨道门槛需另立协议版本，本轮不改变原十二项门槛。

<a id="water-result"></a>

### 水：2026-10-08冻结存量技术结果

技术几何未优化，未认证实验；RHF / 6-31G(d)，18 AO，总能量 **−76.00909910859735 Hartree**，11轮SCF，12项checks全真，完整本地记录PASS。稳定性NOT\_EXECUTED；不是本次重算。

### 水记录身份与材料边界

execution：` a95e7d0f4cb74b9585f1528b19162972 `
result SHA256：` 91e95a9dfb0dd942cec0ab5c71463062fc7688c15ddbcd89bd0ad423715f8db1 `

` actual-example/water/ `材料不是完整NPZ／日志复现包，不能据此宣称已独立重跑。

### 四个冻结示例：普通服务的限定观察

| 分子 | AO | 总能量／Hartree | SCF轮数 |
| --- | --- | --- | --- |
| water | 18 | −76.00909910859735 | 11 |
| methane | 22 | −40.19473232455686 | 9 |
| ammonia | 20 | −56.18326529833526 | 11 |
| ethene | 36 | −78.03040520373332 | 10 |

114项镜像专项工程记录＝97项新增＋17项限制器；不是GitHub或全部Runtime验收。

### 旧操作输出（保留历史范围）

| 操作 | 输出／观察点 | 可得结论 |
| --- | --- | --- |
| Show | 目录、材料清单与来源状态 | 缺来源可能返回20，不是SCF失败。 |
| Review | 全新外部目录review.json、summary.md | 0所选字节匹配／20缺失／40路径、身份、篡改等拒绝；非全588文件审计或科学算术验收。 |
| Check | 打印运行目录、run-manifest.json与适用输入检查／预检服务记录 | 仅输入及AO元数据；无分子能量result，不填0能量。 |
| Report | 终端报告；高级report.md、report-summary.json、run-manifest.json | 只读匹配服务记录，不计算、不改原记录。 |
| 固定P14 | run-manifest.json及任务适用输出 | 资格、比较与分类分开，无全局PASS。 |

### 既有固定协议复核保存摘录 · 2026-10-02

来源docs/examples/P14\_REVIEW\_20261002\_zh-CN.public.md保存摘录；固定C12H6 source-proxy协议的既有consistent，不是新复算或本页实测。使用历史指定本地镜像，不能移用任意XYZ或当前用户分子环境。

原L2验收smoke：20261002T111549Z-p14-smoke-611ad4389dee；分类父smoke：20261002T115757Z-p14-smoke-5edcc0ade184。用途不同，不能互换run\_id。四份旧processed含非标准Infinity，本页不解析数值；不展示能量值。

### 旧条件态用户分子诊断（历史记录，尚未合格）

V2已实施并有受限运行；最近原生根诊断139NR完成、138callback成功／1截止失败，无正式根与尾检，原OPEN账本保留。不推断合格根不存在，不填成功能差；本轮未重运行。

## 结果需要分四层阅读

不要用一个绿色PASS替代不同层次判定。Review／Check不补造四层成功。[来源与核对等级](#sources)

### 1 · 程序执行

记录任务是否执行、结束或拒绝。执行成功不自动授予数值资格。

### 2 · 数值资格

核对收敛、电子数、残差及对应科学协议的资格条件；此处不填写字段值或阈值。未满足资格时，不推进为合格比较。

### 3 · 比较判据

核对参考来源、比较量、单位、偏差及登记比较范围与判据；此处不填写字段值或阈值，不推广到未受测场景。

### 4 · 科学分类

依据固定协议和兼容输入作分类；consistent 也有适用范围。

缺失、未执行、不适用是不同状态，不能记零。L1 依据实际测试输出，不拼造分子账本。

### 历史拒绝记录 · 2026-10-06

附件转述：用户分子工程分支初始化诊断，三路径各一次求值；初始能隙未达原门槛而拒绝，SCF 迭代 0。

这不是 L0 成功或正式 Compute，不可当作研究能差。本页不执行初始化诊断或科学计算。

来源索引：runtime/README\_zh-CN.md、REVIEW\_ENTRY\_zh-CN.md 及 evidence/live；原始记录待补。未添加能隙值、run ID、日志截图或身份。

<a id="tasks"></a>

05 / EXAMPLES & VERIFICATION

## 示例与验证

<a id="protocol-batch3"></a>

### 固定高成本研究示例

固定研究示例的多态结构优化与多个体系尺寸／状态入口已接入，共P11 17态、环状体系尺寸与状态对照 61态。现有旧Docker候选仅完成苯G与N12-G两个单态的受限科学验收，其他76态和完整新结果组装尚未执行。新源码安装镜像的高成本任务尚未重放，身份登记不能替代科学验收。

<a id="high-cost-list-command"></a>

```powershell
python -B .\scripts\list-high-cost-cases.py
```

<a id="case-p11-high-cost"></a>

### 多态结构优化

协议来源P11：呋喃4态G/GL/GE1/GE2；苯3态G/GL/GE1；氰基苯10态G/GL\_I/GL\_II/GE1—GE7。B3LYPG/6-31g(d)、grid3，各自原掩码规则不变。P11A前序G→GL→GE；P11B独立初始化。

不是任意用户分子的通用优化，不代表78态全验收，不改方法或规则，不自动重试／续算。

新安装先登记高成本服务身份；已登记时直接使用现有记录，账本与预检不授权实际计算。

<a id="high-cost-installation-command"></a>

```powershell
Set-Location 'D:\chem-work\runtime-install\runtime'
$installed = Get-Content ..\built-image.json -Raw | ConvertFrom-Json
python -B .\scripts\register-installation.py --service high-cost-cases --image $installed.local_tag --output-dir ..\installations\high-cost-cases

```

<a id="p11-ledger-command"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\high-cost-cases\installation-record.json --task P11 --mode ledger --output-root 'D:\chem-work\high-cost-runs'
```

state list读取实际注册状态与Unit；ledger只读历史账本，不批准计算。preflight仅元数据预检：按状态清单选择尚未执行Unit，不猜ID、不重复准入已通过态；live才是受预算约束的单态科学执行，本卡仅说明、不安排执行。

### 高级：多态约束结构优化 · 单状态live（仅说明，不安排执行）

先用list-high-cost-cases.py读取实际注册Unit，从尚未执行的16态中选择恰一个Unit。已通过P11B-benzene-G保留PASS、不重算、不重复准入。不猜其他Unit ID，不用可运行占位命令冒充真实例子。

用create-high-cost-budget.py为所选Unit在全新、尚不存在的文件创建独立预算，单态ceiling为43200秒。新安装使用 run-installed-runtime.py，指定 high-cost-cases 的 --installation-record、--task P11 --mode live，并精确指定 --unit、--budget、--output-root；可选 --docker-executable。此处只有参数说明，没有可复制的虚构live命令。

P11A呋喃按G→GL→GE，必须以 ` --inputs ` 提供本轮合格前序output映射；P11B保留原独立初始化。科学规则固定，每态一次、失败计费；容器删除与证据闭合前不启动后续，不retry、不resume。

资源合同：8GiB、8CPU、8线程，软43080／硬43200s，scratch20GiB；engine +1GiB、host +2GiB、disk +1GiB。新安装镜像高成本未重放，旧先导PASS不继承到新镜像。

<a id="case-p12-high-cost"></a>

### 尺寸与状态对照

协议来源P12：N12/N14/N16 = 8/23/30态，B3LYPG/6-311g(2df,p)，原2011规则。N12控制不入加权；N14/16全部21/28组对权1。GL/GE依赖本轮G，N16 GE还需本轮GL。

通过回执和output子目录输入映射、哈希及容器删除核对前序，不能历史PASS替代新前序。完整组装未完成，历史2011对齐 NOT\_ESTABLISHED，不新增分类标签。

<a id="p12-ledger-command"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\high-cost-cases\installation-record.json --task P12 --mode ledger --output-root 'D:\chem-work\high-cost-runs'
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\high-cost-cases\installation-record.json --task P12 --mode preflight --unit P12-N16-G --output-root 'D:\chem-work\high-cost-runs'
```

不是用户任意分子的通用优化入口，不代表78态全部验收，不改变原科学规则。state list读取实际注册Unit；ledger只读历史账本；preflight仅元数据预检，按清单选择未执行Unit，以上N16-G为原来源已有未执行态，不重复准入P12-N12-G。live为单态科学执行，仅高级折叠说明，不自动启动、重试或续算。

### 高级：环状体系尺寸与状态对照 · 单状态live边界（仅说明，不安排执行）

参见[已有N16-G单态live来源说明](#n16-live-details)。精确选择一个未执行Unit，工具create-high-cost-budget.py在全新不存在文件创建独立预算，单态43200s；不手写或复用预算。GL/GE前序须为本轮合格G，N16 GE额外需要本轮合格GL，以 ` --inputs ` 提供output映射，历史PASS不能替代。

14GiB、16CPU、16线程，软43080／硬43200s，scratch20GiB，engine +1GiB、host +2GiB、disk +1GiB；原资源合同不明或资源不足拒绝，分档尚未启用。不将15GiB作为所有用户日常默认，不恢复18GiB配置。每态一次、失败计费，容器删除及证据闭合前不后续，不retry/resume，不重复内存探针；新安装镜像未重放，旧先导PASS不继承。

历史已通过态无需重复准入／重算；上述命令仅供未来按授权查看，不安排重跑。metadata：1GiB、1CPU、1线程、120/180s，不SCF、不优化。

<a id="n16-live-details"></a>

### 高级：尚未执行的N16-G单态live说明（不安排运行）

精确单Unit、全新预算由工具生成，不手写或复用；每态一次，失败计费，清理未闭合保留预留。新安装高成本须自己的登记及原接口，不虚构run-installed high-cost参数。

<a id="n16-live-command"></a>

```powershell
python -B .\scripts\create-high-cost-budget.py --output 'D:\chem-work\batch3-n16-g-new.json' --unit P12-N16-G --ceiling-seconds 43200
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\high-cost-cases\installation-record.json --task P12 --mode live --unit P12-N16-G --budget 'D:\chem-work\batch3-n16-g-new.json' --output-root 'D:\chem-work\high-cost-runs'
```

多态约束结构优化 live：8GiB、8CPU/线程；环状体系尺寸与状态对照 live：14GiB、16CPU/线程；43080/43200秒、20GiB scratch。engine +1GiB、host +2GiB、disk +1GiB。不是所有用户默认15GiB；资源分档尚未启用，历史18GiB临时上限已撤销。不教配置WSL，不追加旧PASS内存探针。新任务资源未知或不足拒绝。checkpoint保存不支持resume。

### 旧先导记录与2026-10-08历史边界

2026-10-08第二批历史说明：多态约束结构优化/环状体系尺寸与状态对照 未接入新计算，无新入口。仅描述当时状态，不是当前能力。

旧先导镜像 ` sha256:18dcd1da2e634cf6ab8d49a7281ca853c0a393e140ac95c6ec00448a3fc934bc `；worker构建 ` 05308a1872d769aaa85e39adbafe7020e36358e6 `，不可替换为a4086d。

P12先导：2721.5秒、cgroup 3987410944 bytes；15几何点、17SCF、16梯度、1优化；24worker / 61host哈希通过，容器删除后输出保留。P11苯G旧host日志缺陷与50文件补核保留；补核不表示原封存完美。

结果、receipts、manifests、native-events、资源、optimizedXYZ、checkpoint整目录保留；环状体系尺寸与状态对照 G没有density NPZ。旧受限PASS不重算，本轮没有科学执行。

<a id="protocol-batch2"></a>

新安装入口：先完成[源码安装与构建](https://cccolab.github.io/AI4OrgChem-Runtime/#quick-start)，在同一安装目录登记专题协议案例的服务身份。下列运行命令均沿用这份记录；已登记时不重复登记，不覆盖原记录。示例目录按本机实际位置替换。

<a id="protocol-cases-installation-command"></a>

```powershell
Set-Location 'D:\chem-work\runtime-install\runtime'
$installed = Get-Content ..\built-image.json -Raw | ConvertFrom-Json
python -B .\scripts\register-installation.py --service protocol-cases --image $installed.local_tag --output-dir ..\installations\protocol-cases

```

### 固定协议受限复核

v0.3.0-candidate · 第二批协议修订。研究用途入口与 Show/Review 证据目录分开；普通用户通过自己的 XYZ 普通 RHF 四步启动，不靠 P 编号。固定研究示例的多态结构优化与多个体系尺寸／状态入口已接入，共P11 17态、环状体系尺寸与状态对照 61态。现有旧Docker候选仅完成苯G与N12-G两个单态的受限科学验收，其他76态和完整新结果组装尚未执行。新源码安装镜像的高成本任务尚未重放，身份登记不能替代科学验收。自选分子的普通DFT尚未开放；部分固定协议已有受限RKS/GL/条件核复核。

禁止任意 XYZ/SMILES 替换、不加角度、不重优化、不混协议 Hartree。输出整目录保留：host-execution.json、output/case-result.json、output/guard-receipt.json 及资源记录。

Python 新安装入口：` --installation-record `、` --task `、` --mode `、` --output-root `、` --budget `，可选 ` --docker-executable `。ledger/preflight：1CPU、1线程、1GiB、120s，不SCF（P07真实AO预检例外）；live：2CPU、2线程、4GiB、无swap，840s开始停止、900s硬限，串行每项一次，七项预留6300s。不覆盖普通100/120s合同。

native-admission-pause 存在时，在新预留或容器前拒绝，不绕过。hydrogen UHF1e 必须独立计数，不能只记 hf.kernel。Git缺失封装适配仅 unavailable，不改科学；失败保留，旧墙时计费继承，不重跑已通过五项。预算仅记账拒绝，非方法批准。

### 先另存全新外部预算文件

来源 docs/PROTOCOL\_CASES\_BATCH2\_zh-CN.public.md；保存为 D:\\your-work\\batch-budget-new.json（UTF8无BOM、LF末LF）。禁止覆盖、清空或复用已有验收预算。若文件已存在，取消保存并选择新的外部文件名，同时修改命令；本页不能检查本机文件。

<a id="batch2-budget-json"></a>

```json
{
  "schema": "protocol-case-batch2-budget-v1",
  "ceiling_seconds": 6300,
  "one_attempt_per_case": true,
  "scientific_cases": ["P03", "P04", "P05", "P06", "P08", "P09", "P10"],
  "attempts": {},
  "old_root_budget_reused": false,
  "budget_is_accounting_not_method_approval": true
}

```

<a id="case-protocol-p03"></a>

### 约束扭转路径能量账本

<a id="batch2-p03-ledger"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P03 --mode ledger --output-root '..\runs\batch2-p03-ledger-new'
```

<a id="batch2-p03-preflight"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P03 --mode preflight --output-root '..\runs\batch2-p03-preflight-new'
```

固定输入：旧四优化端点ledger；方法：冻结0° B3LYPG/6-311G(d,p)单点，不新优化。模式 ledger/preflight/live。判读：端点账本与冻结点分开，不声称新优化路径；输出遵循本区整目录清单。

### 高级 live · 扭转构型端点与能量账本 · 先保存新预算

<a id="batch2-p03-live"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P03 --mode live --budget 'D:\your-work\batch-budget-new.json' --output-root 'D:\your-work\runtime-runs\protocol-cases-p03-live-new'
```

 <a id="case-protocol-p04"></a>

### 两条件态直接项和轨道响应

<a id="batch2-p04-ledger"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P04 --mode ledger --output-root '..\runs\batch2-p04-ledger-new'
```

<a id="batch2-p04-preflight"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P04 --mode preflight --output-root '..\runs\batch2-p04-preflight-new'
```

固定输入：11有效点ledger；diphenyl imine 0°，原DSI3/FUD各自求解。模式 ledger/preflight/live；精确泛函/基组以原固定协议为准，不猜。输出遵循整目录清单；直接项与轨道响应分别判读，不替换任意分子。

### 高级 live · π–π条件态与轨道响应 · 先保存新预算

<a id="batch2-p04-live"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P04 --mode live --budget 'D:\your-work\batch-budget-new.json' --output-root 'D:\your-work\runtime-runs\protocol-cases-p04-live-new'
```

 <a id="case-protocol-p05"></a>

### π–σ条件比较

<a id="batch2-p05-ledger"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P05 --mode ledger --output-root '..\runs\batch2-p05-ledger-new'
```

<a id="batch2-p05-preflight"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P05 --mode preflight --output-root '..\runs\batch2-p05-preflight-new'
```

固定输入：七角度同母体账本，原定义17° G/FUD。模式 ledger/preflight/live；精确泛函/基组以原协议为准，不猜。输出遵循整目录清单；同母体条件比较，不增加角度或混入其他协议能量。

### 高级 live · π–σ条件能量对照 · 先保存新预算

<a id="batch2-p05-live"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P05 --mode live --budget 'D:\your-work\batch-budget-new.json' --output-root 'D:\your-work\runtime-runs\protocol-cases-p05-live-new'
```

 <a id="case-protocol-p06"></a>

### 双片段独立能量组装

<a id="batch2-p06-ledger"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P06 --mode ledger --output-root '..\runs\batch2-p06-ledger-new'
```

<a id="batch2-p06-preflight"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P06 --mode preflight --output-root '..\runs\batch2-p06-preflight-new'
```

固定输入：0°/17° FUL-2/PDSI账本；新0°原RHF/STO-3G。模式 ledger/preflight/live。输出遵循整目录清单；双片段独立能量按原定义组装，不重优化、不混协议。

### 高级 live · 片段条件能量组装 · 先保存新预算

<a id="batch2-p06-live"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P06 --mode live --budget 'D:\your-work\batch-budget-new.json' --output-root 'D:\your-work\runtime-runs\protocol-cases-p06-live-new'
```

 <a id="case-protocol-p07"></a>

### 同Hamiltonian路径闭合

<a id="batch2-p07-preflight"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P07 --mode preflight --output-root '..\runs\batch2-p07-preflight-new'
```

<a id="batch2-p07-ledger"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P07 --mode ledger --output-root '..\runs\batch2-p07-ledger-new'
```

固定输入：五态桥接闭合。方法：同Hamiltonian冻结账本与资格/资源预检；P07不构建新的量子计算，零新QM；ledger/preflight ONLY，零新QM，无live入口。输出遵循整目录清单；闭合核对不是新增能量计算或科学端点批准。

 <a id="case-protocol-p08"></a>

### 丁二烯GL端点参照敏感性

<a id="batch2-p08-ledger"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P08 --mode ledger --output-root '..\runs\batch2-p08-ledger-new'
```

<a id="batch2-p08-preflight"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P08 --mode preflight --output-root '..\runs\batch2-p08-preflight-new'
```

固定输入：氢化热表值历史优化账本；新冻结GL几何一次普通RKS、一次原GL核。模式 ledger/preflight/live；精确泛函/基组不猜。输出遵循整目录清单；参照敏感性诊断，非新优化ΔEA。

### 高级 live · 局域化端点与参照能量 · 先保存新预算

<a id="batch2-p08-live"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P08 --mode live --budget 'D:\your-work\batch-budget-new.json' --output-root 'D:\your-work\runtime-runs\protocol-cases-p08-live-new'
```

 <a id="case-protocol-p09"></a>

### 环丁二烯固定几何条件态诊断

<a id="batch2-p09-ledger"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P09 --mode ledger --output-root '..\runs\batch2-p09-ledger-new'
```

<a id="batch2-p09-preflight"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P09 --mode preflight --output-root '..\runs\batch2-p09-preflight-new'
```

固定输入：旧VDE/ADE/ESE账本；新G-like RKS/稳定性/DSI固定核。模式 ledger/preflight/live；精确泛函/基组不猜。输出遵循整目录清单；固定几何诊断，非最终VDE/ADE/ESE。

### 高级 live · 条件态与稳定性诊断 · 先保存新预算

<a id="batch2-p09-live"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P09 --mode live --budget 'D:\your-work\batch-budget-new.json' --output-root 'D:\your-work\runtime-runs\protocol-cases-p09-live-new'
```

 <a id="case-protocol-p10"></a>

### 苯核排斥键长交替

<a id="batch2-p10-ledger"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P10 --mode ledger --output-root '..\runs\batch2-p10-ledger-new'
```

<a id="batch2-p10-preflight"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P10 --mode preflight --output-root '..\runs\batch2-p10-preflight-new'
```

固定输入：旧核公式与五点账本；新delta=0/0.01/0.02/0.04/0.06 Å五普通RKS。模式 ledger/preflight/live；精确泛函/基组不猜。输出遵循整目录清单；核排斥与键长交替分开，不新增点、不重优化。

### 高级 live · 键长交替与能量响应 · 先保存新预算

<a id="batch2-p10-live"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P10 --mode live --budget 'D:\your-work\batch-budget-new.json' --output-root 'D:\your-work\runtime-runs\protocol-cases-p10-live-new'
```

<a id="registered-fixed-cases"></a>

新安装入口：先完成[源码安装与构建](https://cccolab.github.io/AI4OrgChem-Runtime/#quick-start)，在同一安装目录登记三个固定案例的服务身份。下列运行命令均沿用这份记录；已登记时不重复登记，不覆盖原记录。示例目录按本机实际位置替换。

<a id="registered-cases-installation-command"></a>

```powershell
Set-Location 'D:\chem-work\runtime-install\runtime'
$installed = Get-Content ..\built-image.json -Raw | ConvertFrom-Json
python -B .\scripts\register-installation.py --service registered-cases --image $installed.local_tag --output-dir ..\installations\registered-cases

```

分别计数：14项evidence、7项historical任务、3项fixed服务、1项ordinary服务；不合成25，不把7替换为11。

<a id="case-p02-statistics"></a>

### 结构与光谱表值统计 · 冻表值统计

固定发表表值拟合、残差结构与方向；不进行量子计算，不认证PDF／CIF。不能替换表值或容差。

<a id="case-p02-command"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\registered-cases\installation-record.json --task p02-statistics --output-root '..\runs\case-p02-command-new'
```

[P02证据目录](#proposition-catalog)

<a id="case-p13-graph-ledger"></a>

### 共轭图规则与能量账本 · 分子图规则与能量账本

固定分子图独立匹配、使用RDKit核对真实分子式，并读取冻结的ESE／CESE；不进行量子计算。不接受任意SMILES，不是旧量子优化；不能更换分片或容差。

<a id="case-p13-command"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\registered-cases\installation-record.json --task p13-graph-ledger --output-root '..\runs\case-p13-command-new'
```

[P13证据目录](#proposition-catalog)

<a id="case-p01-orbital-density"></a>

### 轨道表示与密度对照 · 轨道局域化与密度不变性

固定乙烯 RHF＋Boys／PM，同态占据旋转的density／energy invariance；不是用户局域化，也不是全部P01。不能换XYZ、基组或容差。

<a id="case-p01-command"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\registered-cases\installation-record.json --task p01-orbital-density --output-root '..\runs\case-p01-command-new'
```

[P01证据目录](#proposition-catalog)

输出 ` output/case/case-report.md `、` output/case/case-result.json `及完整host／worker records。96项专项镜像工程＋3个固定Docker限定PASS，是既有记录，不是此网页执行。所有固定输入不得改成任意案例。

L3／L4严格断网验收NOT\_EXECUTED；L4不支持resume。

[计算模块证据目录](#proposition-catalog) · [固定七任务与平台矩阵](#p14-tasks)

<a id="evidence-catalog"></a>

### 已有科学证据（按需查阅）

固定服务交叉入口：[P01轨道与密度](#case-p01-orbital-density) · [P02统计](#case-p02-statistics) · [P13图与账本](#case-p13-graph-ledger)。下列14张旧卡完整保留；证据命题与新固定服务的验收范围不等同。

<a id="proposition-catalog"></a>

### 计算模块已有证据：查看本地查阅步骤

Show用于查看计算模块目录、材料清单及来源状态；来源缺失时可能返回20，不是新的SCF失败。Review向全新外部目录输出review.json、summary.md，仅核对所选材料字节匹配／缺失／拒绝，不证明能量算术或科学命题正确。

本地所需来源为Runtime源码与自己持有的固定科学源码。轨道表示与密度对照—P13目前可查阅和核对所选既有材料，未提供通用Runtime重算任务。P14证据查阅与固定任务启动分开；固定案例不能替换为任意XYZ。

以下14张卡为WEB\_CONTENT\_BASELINE内容的静态核对，属于本区默认正文，不增加主区域。完整标题是登记计算模块，不是科学认证；CURRENT是材料关系，不代表本次复验。六份上传材料已读并静态核对；29份参考文件仅索引，未逐文件读取或哈希，原始完整科学输出未提供，本轮不重运行。

<a id="module-naming-scope"></a>

按实际计算功能选择模块，无需先了解专著编号。用户自己的分子目前仅支持普通RHF单点服务；下列模块用于固定研究案例计算或已保存证据复核，具体输入、模式与验收范围见各入口。模块名称调整不增加算法、体系或科学验收范围。

<a id="module-protocol-map"></a>

### 模块名称与内部协议编号（来源追溯）

| 内部协议编号 | 计算模块 | 当前范围 |
| --- | --- | --- |
| ` P01 ` | 轨道表示与密度对照 | 固定乙烯轨道变换与密度／能量不变量对照 |
| ` P02 ` | 结构与光谱表值统计 | 冻结出版表值统计与回归；不计算新光谱 |
| ` P03 ` | 扭转构型端点与能量账本 | 已保存端点账本与冻结几何单点 |
| ` P04 ` | π–π条件态与轨道响应 | 固定双状态直接项与轨道响应对照 |
| ` P05 ` | π–σ条件能量对照 | 固定角度条件能量单点 |
| ` P06 ` | 片段条件能量组装 | 固定双片段σ–σ条件态独立组装 |
| ` P07 ` | 能量账本闭合校验 | 同哈密顿量保存账本；无新量子计算 |
| ` P08 ` | 局域化端点与参照能量 | 丁二烯固定局域化端点与参照热化学 |
| ` P09 ` | 条件态与稳定性诊断 | 环丁二烯固定几何的条件态诊断 |
| ` P10 ` | 键长交替与能量响应 | 苯固定五点几何的普通DFT能量响应 |
| ` P11 ` | 多态约束结构优化 | 固定体系17态；旧候选仅苯G先导通过 |
| ` P12 ` | 环状体系尺寸与状态对照 | 固定环状体系61态；旧候选仅N12-G先导通过 |
| ` P13 ` | 共轭图规则与能量账本 | 固定图案例与ESE／CESE算术账本 |
| ` P14 ` | 条件能量与结构响应复核 | 固定协议联合复核；任意用户条件Compute仍BLOCKED |

<a id="inline-propositions"></a>

<a id="p01"></a>

固定案例 · 证据复核

### 轨道表示与密度对照

### 原文标题 · evidence\_identity

P01｜CAT01 必须区分“分子轨道离域”和“电子离域”，传统理论及部分局域化方法可能混淆二者

` INDEPENDENT_QM_IDENTITY_CONTROL `

**材料类别**

独立量子力学身份控制

**Show + Review 步骤**

查看本地查阅步骤；仅复制文本，在本地终端操作。

**固定科学源码**

v0.3.2 · ` 28511f3d84fa65707a107cde1e8121a7b4334ecb `

**输出与判读**

review.json 和 summary.md；只核所选字节。

**限制**

无通用重算；不是新的科学认证。

### 查看本地查阅步骤

<a id="p01-show"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Show -Proposition P01
```

<a id="p01-review"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Review -Proposition P01 `
 -SourceDirectory 'D:\your-work\science-v0.3.2' `
 -OutputDirectory 'D:\your-work\reviews\p01-new'
```

### 文件索引 · 4 项

| path | role | item | relation |
| --- | --- | --- | --- |
| evidence/P01-P14/P01/data-card.md | data-card | main | CURRENT |
| evidence/P01-P14/P01/protocol.md | protocol | main | CURRENT |
| evidence/P01-P14/P01/report.md | report | main | CURRENT |
| evidence/P01-P14/P01/result.json | result | main | CURRENT |

 <a id="p02"></a>

固定案例 · 证据复核

### 结构与光谱表值统计

### 原文标题 · evidence\_identity

P02｜CAT02 共轭作用不一定使分子趋于平面和稳定，也可能伴随结构扭曲

` PUBLISHED_VALUE_REANALYSIS `

**材料类别**

已发表数值再分析

**Show + Review 步骤**

查看本地查阅步骤；仅本地文本，不执行。

**固定科学源码**

v0.3.2 · ` 28511f3d84fa65707a107cde1e8121a7b4334ecb `

**输出与判读**

review.json 和 summary.md；只核所选字节。

**限制**

无通用重算。

### 查看本地查阅步骤

<a id="p02-show"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Show -Proposition P02
```

<a id="p02-review"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Review -Proposition P02 `
 -SourceDirectory 'D:\your-work\science-v0.3.2' `
 -OutputDirectory 'D:\your-work\reviews\p02-new'
```

### 文件索引 · 4 项

| path | role | item | relation |
| --- | --- | --- | --- |
| evidence/P01-P14/P02/data-card.md | data-card | main | CURRENT |
| evidence/P01-P14/P02/protocol.md | protocol | main | CURRENT |
| evidence/P01-P14/P02/report.md | report | main | CURRENT |
| evidence/P01-P14/P02/result.json | result | main | CURRENT |

 <a id="p03"></a>

固定案例 · 证据复核

### 扭转构型端点与能量账本

### 原文标题 · evidence\_identity

P03｜CAT02 在受测路径上电子能与核排斥能可反向变化，近平面构象不一定能量最低

` FROZEN_COORDINATE_QM_LEDGER `

**材料类别**

冻结坐标量子力学账本

**Show + Review 步骤**

查看本地查阅步骤；仅文本，不执行。

**固定科学源码**

v0.3.2 · ` 28511f3d84fa65707a107cde1e8121a7b4334ecb `

**输出与判读**

review.json 和 summary.md；只核所选字节。

**限制**

无通用重算。

### 查看本地查阅步骤

<a id="p03-show"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Show -Proposition P03
```

<a id="p03-review"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Review -Proposition P03 `
 -SourceDirectory 'D:\your-work\science-v0.3.2' `
 -OutputDirectory 'D:\your-work\reviews\p03-new'
```

### 文件索引 · 4 项

| path | role | item | relation |
| --- | --- | --- | --- |
| evidence/P01-P14/P03/data-card.md | data-card | main | CURRENT |
| evidence/P01-P14/P03/protocol.md | protocol | main | CURRENT |
| evidence/P01-P14/P03/report.md | report | main | CURRENT |
| evidence/P01-P14/P03/result.json | result | main | CURRENT |

 <a id="p04"></a>

固定案例 · 证据复核

### π–π条件态与轨道响应

### 原文标题 · evidence\_identity

P04｜CAT03 在原著LFMO定义下，π–π离域总端点可表现为去稳定化

` SOURCE_DEFINED_CONDITIONAL_ENDPOINT `

**材料类别**

来源定义条件端点

**Show + Review 步骤**

查看本地查阅步骤；仅文本，不执行。

**固定科学源码**

v0.3.2 · ` 28511f3d84fa65707a107cde1e8121a7b4334ecb `

**输出与判读**

review.json 和 summary.md；只核所选字节。

**限制**

无通用重算。

### 查看本地查阅步骤

<a id="p04-show"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Show -Proposition P04
```

<a id="p04-review"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Review -Proposition P04 `
 -SourceDirectory 'D:\your-work\science-v0.3.2' `
 -OutputDirectory 'D:\your-work\reviews\p04-new'
```

### 文件索引 · 4 项

| path | role | item | relation |
| --- | --- | --- | --- |
| evidence/P01-P14/P04/data-card.md | data-card | main | CURRENT |
| evidence/P01-P14/P04/protocol.md | protocol | main | CURRENT |
| evidence/P01-P14/P04/report.md | report | main | CURRENT |
| evidence/P01-P14/P04/result.jsonl | result | main | CURRENT |

 <a id="p05"></a>

固定案例 · 证据复核

### π–σ条件能量对照

### 原文标题 · evidence\_identity

P05｜CAT03 π–σ轨道相互作用可表现为去稳定化，不能先验地归入普通“成键稳定化”

` SOURCE_DEFINED_CONDITIONAL_ENDPOINT `

**材料类别**

来源定义条件端点；七角度当前记录与历史 anchor 分开

**Show + Review 步骤**

查看本地查阅步骤；仅文本，不执行。

**固定科学源码**

v0.3.2 · 28511f3d84fa65707a107cde1e8121a7b4334ecb

**输出与判读**

review.json 和 summary.md；只核所选字节。

**限制**

无通用重算。

### 查看本地查阅步骤

<a id="p05-show"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Show -Proposition P05
```

<a id="p05-review"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Review -Proposition P05 `
 -SourceDirectory 'D:\your-work\science-v0.3.2' `
 -OutputDirectory 'D:\your-work\reviews\p05-new'
```

### 文件索引 · 6 项（path / role / item / relation）

evidence/P01-P14/P05/data-card.md / data-card / main / CURRENT
evidence/P01-P14/P05/protocol.md / protocol / main / CURRENT
evidence/P01-P14/P05/report.md / report / main / CURRENT
evidence/P01-P14/P05/result.jsonl / historical-result / main / HISTORICAL\_ANCHOR
evidence/P01-P14/P05/seven-angle-protocol.yaml / current-protocol / main / CURRENT
evidence/P01-P14/P05/seven-angle-result.json / current-result / main / CURRENT

 <a id="p06"></a>

固定案例 · 证据复核

### 片段条件能量组装

### 原文标题 · evidence\_identity

P06｜CAT03 非键σ–σ条件态能量差应独立分析，不能未经计算就等同于传统位阻排斥叙事

` SOURCE_DEFINED_CONDITIONAL_ENDPOINT `

**材料类别**

来源定义条件端点

**Show + Review 步骤**

查看本地查阅步骤；仅文本，不执行。

**固定科学源码**

v0.3.2 · 28511f3d84fa65707a107cde1e8121a7b4334ecb

**输出与判读**

review.json 和 summary.md；只核所选字节。

**限制**

无通用重算。

### 查看本地查阅步骤

<a id="p06-show"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Show -Proposition P06
```

<a id="p06-review"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Review -Proposition P06 `
 -SourceDirectory 'D:\your-work\science-v0.3.2' `
 -OutputDirectory 'D:\your-work\reviews\p06-new'
```

### 文件索引 · 4 项（path / role / item / relation）

evidence/P01-P14/P06/data-card.md / data-card / main / CURRENT
evidence/P01-P14/P06/protocol.md / protocol / main / CURRENT
evidence/P01-P14/P06/report.md / report / main / CURRENT
evidence/P01-P14/P06/result.jsonl / result / main / CURRENT

 <a id="p07"></a>

固定案例 · 证据复核

### 能量账本闭合校验

### 原文标题 · evidence\_identity

P07｜CAT03 分子扭曲不能只用“共轭稳定化—位阻去稳定化”二项竞争解释，应检查π–π、π–σ、σ–σ及轨道响应的共同作用

` INDEPENDENT_COMPUTATIONAL_AUDIT_PLUS_DERIVED_SYNTHESIS `

**材料类别**

独立计算审计 + 派生综合

**Show + Review 步骤**

查看本地查阅步骤；仅文本，不执行。

**固定科学源码**

v0.3.2 · 28511f3d84fa65707a107cde1e8121a7b4334ecb

**输出与判读**

review.json 和 summary.md；只核所选字节。

**限制**

无通用重算。

### 查看本地查阅步骤

<a id="p07-show"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Show -Proposition P07
```

<a id="p07-review"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Review -Proposition P07 `
 -SourceDirectory 'D:\your-work\science-v0.3.2' `
 -OutputDirectory 'D:\your-work\reviews\p07-new'
```

### 文件索引 · 7 项（path / role / item / relation）

evidence/P01-P14/P07/data-card.md / data-card / main / CURRENT
evidence/P01-P14/P07/protocol.md / protocol / main / CURRENT
evidence/P01-P14/P07/report.md / report / main / CURRENT
evidence/P01-P14/P07/result.json / result / main / CURRENT
evidence/P01-P14/P07/same-hamiltonian-audit-protocol.yaml / audit-protocol / main / CURRENT
evidence/P01-P14/P07/same-hamiltonian-audit-report.md / audit-report / main / CURRENT
evidence/P01-P14/P07/same-hamiltonian-audit-result.json / audit-result / main / CURRENT

 <a id="p08"></a>

固定案例 · 证据复核

### 局域化端点与参照能量

### 原文标题 · evidence\_identity

P08｜CAT04 丁二烯的共轭能不一定是稳定化能；选择性氢化热不能直接作为共轭稳定化的唯一证据，中央单键缩短也需要独立结构解释

` SOURCE_DEFINED_COUNTERFACTUAL_ENDPOINT `

**材料类别**

来源定义反事实端点

**Show + Review 步骤**

查看本地查阅步骤；仅文本，不执行。

**固定科学源码**

v0.3.2 · 28511f3d84fa65707a107cde1e8121a7b4334ecb

**输出与判读**

review.json 和 summary.md；只核所选字节。

**限制**

无通用重算；不开放任意丁二烯研究计算。

### 查看本地查阅步骤

<a id="p08-show"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Show -Proposition P08
```

<a id="p08-review"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Review -Proposition P08 `
 -SourceDirectory 'D:\your-work\science-v0.3.2' `
 -OutputDirectory 'D:\your-work\reviews\p08-new'
```

### 文件索引 · 4 项（path / role / item / relation）

evidence/P01-P14/P08/data-card.md / data-card / main / CURRENT
evidence/P01-P14/P08/protocol.md / protocol / main / CURRENT
evidence/P01-P14/P08/report.md / report / main / CURRENT
evidence/P01-P14/P08/result.json / result / main / CURRENT

 <a id="p09"></a>

固定案例 · 证据复核

### 条件态与稳定性诊断

### 原文标题 · evidence\_identity

P09｜CAT05 苯和环丁二烯的芳香/反芳香能可通过无经验参数的局域几何或虚拟参考体系进行纯理论计算

` SOURCE_ALIGNED_VIRTUAL_REFERENCE `

**材料类别**

来源对齐虚拟参照

**Show + Review 步骤**

查看本地查阅步骤；仅文本，不执行。

**固定科学源码**

v0.3.2 · 28511f3d84fa65707a107cde1e8121a7b4334ecb

**输出与判读**

review.json 和 summary.md；只核所选字节。

**限制**

无通用重算。

### 查看本地查阅步骤

<a id="p09-show"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Show -Proposition P09
```

<a id="p09-review"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Review -Proposition P09 `
 -SourceDirectory 'D:\your-work\science-v0.3.2' `
 -OutputDirectory 'D:\your-work\reviews\p09-new'
```

### 文件索引 · 4 项（path / role / item / relation）

evidence/P01-P14/P09/data-card.md / data-card / main / CURRENT
evidence/P01-P14/P09/protocol.md / protocol / main / CURRENT
evidence/P01-P14/P09/report.md / report / main / CURRENT
evidence/P01-P14/P09/result.json / result / main / CURRENT

 <a id="p10"></a>

固定案例 · 证据复核

### 键长交替与能量响应

### 原文标题 · evidence\_identity

P10｜CAT05 苯的键长均一化和高对称性不能简单归因于π电子离域；沿冻结坐标，核排斥能变化与电子能变化反向且绝对幅度更大

` FROZEN_COORDINATE_QM_LEDGER `

**材料类别**

冻结坐标量子力学账本

**Show + Review 步骤**

查看本地查阅步骤；仅文本，不执行。

**固定科学源码**

v0.3.2 · 28511f3d84fa65707a107cde1e8121a7b4334ecb

**输出与判读**

review.json 和 summary.md；只核所选字节。

**限制**

无通用重算。

### 查看本地查阅步骤

<a id="p10-show"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Show -Proposition P10
```

<a id="p10-review"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Review -Proposition P10 `
 -SourceDirectory 'D:\your-work\science-v0.3.2' `
 -OutputDirectory 'D:\your-work\reviews\p10-new'
```

### 文件索引 · 4 项（path / role / item / relation）

evidence/P01-P14/P10/data-card.md / data-card / main / CURRENT
evidence/P01-P14/P10/protocol.md / protocol / main / CURRENT
evidence/P01-P14/P10/report.md / report / main / CURRENT
evidence/P01-P14/P10/result.json / result / main / CURRENT

 <a id="p11"></a>

固定案例 · 证据复核

### 多态约束结构优化

### 原文标题 · evidence\_identity

P11｜CAT05 呋喃类不能沿用苯型ESE判据：` ΔEA>0 `且小于正的局域增量总和，负差值应定义为LDE；取代苯效应需区分纯共轭与纯诱导贡献

` SOURCE_ALIGNED_STATE_SPECIFIC_RESTRICTED_OPTIMIZATION `

呋喃局域化能差（LDE）

取代苯状态特定平面共轭／诱导能量（CE/IE）

**材料类别**

来源对齐状态特定受限优化；两子项分别判读

**Show + Review 步骤**

查看本地查阅步骤；仅文本，不执行。

**固定科学源码**

v0.3.2 · 28511f3d84fa65707a107cde1e8121a7b4334ecb

**输出与判读**

review.json 和 summary.md；只核所选字节。

**限制**

无通用重算；固定几何旧诊断不是当前结果。

### 查看本地查阅步骤

<a id="p11-show"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Show -Proposition P11
```

<a id="p11-review"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Review -Proposition P11 `
 -SourceDirectory 'D:\your-work\science-v0.3.2' `
 -OutputDirectory 'D:\your-work\reviews\p11-new'
```

### 文件索引 · 17 项（path / role / item / relation）

evidence/P01-P14/P11/furan-data-card.md / data-card / P11-A / CURRENT
evidence/P01-P14/P11/furan-protocol.md / protocol / P11-A / CURRENT
evidence/P01-P14/P11/furan-report.md / report / P11-A / CURRENT
evidence/P01-P14/P11/furan-result.json / result / P11-A / CURRENT
evidence/P01-P14/P11/substituent-data-card.md / data-card / P11-B / CURRENT
evidence/P01-P14/P11/substituent-protocol.md / protocol / P11-B / CURRENT
evidence/P01-P14/P11/substituent-report.md / report / P11-B / CURRENT
evidence/P01-P14/P11/substituent-result.json / result / P11-B / CURRENT
evidence/P01-P14/P11/substituent-fixed-geometry-audit-result.json / historical-result / P11-B / HISTORICAL\_SUPERSEDED\_DIAGNOSTIC
evidence/P01-P14/P11/optimized-states/benzene\_G.json / state-record / P11-B / CURRENT
evidence/P01-P14/P11/optimized-states/benzene\_GE1.json / state-record / P11-B / CURRENT
evidence/P01-P14/P11/optimized-states/benzene\_GL.json / state-record / P11-B / CURRENT
evidence/P01-P14/P11/optimized-states/cyanobenzene\_G.json / state-record / P11-B / CURRENT
evidence/P01-P14/P11/optimized-states/cyanobenzene\_GE1.json / state-record / P11-B / CURRENT
evidence/P01-P14/P11/optimized-states/cyanobenzene\_GE2.json / state-record / P11-B / CURRENT
evidence/P01-P14/P11/optimized-states/cyanobenzene\_GE3.json / state-record / P11-B / CURRENT
evidence/P01-P14/P11/optimized-states/cyanobenzene\_GL.json / state-record / P11-B / CURRENT

 <a id="p12"></a>

固定案例 · 证据复核

### 环状体系尺寸与状态对照

### 原文标题 · evidence\_identity

P12｜CAT06 轮烯CESE在指定尺寸点呈现边界前/起点方向变化

` INDEPENDENT_SAME_BASIS_PLANAR_CESE_RECALCULATION `

N12 same-basis planar CESE ledger

N14 same-basis planar CESE ledger

N16 same-basis planar CESE ledger

**材料类别**

独立同基组平面 CESE 重算保存账本

**Show + Review 步骤**

查看本地查阅步骤；仅文本，不执行。

**固定科学源码**

v0.3.2 · 28511f3d84fa65707a107cde1e8121a7b4334ecb

**输出与判读**

review.json 和 summary.md；只核所选字节。

**限制**

无通用重算；旧 v0.3.1 不作当前分类。

### 查看本地查阅步骤

<a id="p12-show"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Show -Proposition P12
```

<a id="p12-review"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Review -Proposition P12 `
 -SourceDirectory 'D:\your-work\science-v0.3.2' `
 -OutputDirectory 'D:\your-work\reviews\p12-new'
```

### 文件索引 · 8 项（path / role / item / relation）

evidence/P01-P14/P12/data-card.md / data-card / main / CURRENT
evidence/P01-P14/P12/protocol.md / protocol / main / CURRENT
evidence/P01-P14/P12/report.md / report / main / CURRENT
evidence/P01-P14/P12/result.json / result / main / CURRENT
evidence/P01-P14/P12/n12-same-basis-ledger.json / same-basis-ledger / N12 / CURRENT
evidence/P01-P14/P12/n14-same-basis-ledger.json / same-basis-ledger / N14 / CURRENT
evidence/P01-P14/P12/n16-same-basis-ledger.json / same-basis-ledger / N16 / CURRENT
evidence/P01-P14/P12/result-v0.3.1-historical.json / historical-result / P12 / HISTORICAL\_NOT\_CURRENT\_CLASSIFICATION

 <a id="p13"></a>

固定案例 · 证据复核

### 共轭图规则与能量账本

### 原文标题 · evidence\_identity

P13｜CAT06 多环苯系烃和稠环芳烃可按GL规则优先、位置/能量规则随后并组装公开PBH能量账本

` DERIVED_RULE_AND_GRAPH_EVIDENCE `

**材料类别**

派生规则与图证据

**Show + Review 步骤**

查看本地查阅步骤；仅文本，不执行。

**固定科学源码**

v0.3.2 · 28511f3d84fa65707a107cde1e8121a7b4334ecb

**输出与判读**

review.json 和 summary.md；只核所选字节。

**限制**

无通用重算。标题的“公开PBH”不代表 Runtime 公开分发 URL。

### 查看本地查阅步骤

<a id="p13-show"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Show -Proposition P13
```

<a id="p13-review"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Review -Proposition P13 `
 -SourceDirectory 'D:\your-work\science-v0.3.2' `
 -OutputDirectory 'D:\your-work\reviews\p13-new'
```

### 文件索引 · 4 项（path / role / item / relation）

evidence/P01-P14/P13/data-card.md / data-card / main / CURRENT
evidence/P01-P14/P13/protocol.md / protocol / main / CURRENT
evidence/P01-P14/P13/report.md / report / main / CURRENT
evidence/P01-P14/P13/result.json / result / main / CURRENT

 <a id="p14"></a>

固定案例 · 证据复核

### 条件能量与结构响应复核

### 原文标题 · evidence\_identity

P14｜CAT07 应变芳香体系的结构扭曲不能完全归因于角应变，π离域可能具有结构扭曲作用

` SOURCE_PROXY_PRODUCTION_CONDITIONAL_QM `

**材料类别**

来源代理生产级条件量子力学保存材料

**Show + Review 步骤**

下方仅查阅和所选文件核对。[五个固定任务导航](#p14-tasks)是另一入口：[smoke](#p14-smoke) · [equivalence](#p14-equivalence) · [fixed](#p14-fixed) · [optimize](#p14-optimize) · [classify](#p14-classify)。

**固定科学源码**

v0.3.2 · 28511f3d84fa65707a107cde1e8121a7b4334ecb

**输出与判读**

review.json 和 summary.md；只核所选字节。

**限制**

无通用重算；技术 smoke、历史 pilot 不作为科学端点。四份旧 processed 含 Infinity，不在浏览器解析。

### 查看本地查阅步骤

<a id="p14-show"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Show -Proposition P14
```

<a id="p14-review"></a>

```powershell
./scripts/start-local-runtime.ps1 -Action Review -Proposition P14 `
 -SourceDirectory 'D:\your-work\science-v0.3.2' `
 -OutputDirectory 'D:\your-work\reviews\p14-new'
```

### 文件索引 · 20 项（path / role / item / relation）

evidence/P01-P14/P14/data-card.md / data-card / main / CURRENT
evidence/P01-P14/P14/protocol.md / protocol / main / CURRENT
evidence/P01-P14/P14/report.md / report / main / CURRENT
evidence/P01-P14/P14/result.json / result / main / CURRENT
configs/qm/p14\_strained\_aromatic\_pi\_distortivity\_v0.1.yaml / fixed-protocol / main / CURRENT
configs/qm/p09\_exchange\_integral\_classes\_v0.1.yaml / conditional-rules / main / CURRENT
evidence/P01-P14/P14/processed/p14\_C12H6\_B3LYPG\_6\_31Gd\_production\_optimization\_v0.1.json / processed-record / main / CURRENT\_REGISTERED\_RECORD
evidence/P01-P14/P14/processed/p14\_C12H6\_source\_level\_fixed\_geometry\_v0.1.json / processed-record / main / CURRENT\_REGISTERED\_RECORD
evidence/P01-P14/P14/processed/p14\_memory\_controlled\_eri\_equivalence\_v0.1.json / processed-record / main / CURRENT\_REGISTERED\_RECORD
evidence/P01-P14/P14/processed/p14\_strained\_aromatic\_pi\_distortivity\_classification\_v0.1.json / processed-record / main / CURRENT\_REGISTERED\_RECORD
evidence/P01-P14/P14/processed/p14\_C12H6\_five\_parameter\_pilot\_v0.1.json / processed-record / main / HISTORICAL\_TECHNICAL\_NOT\_SCIENTIFIC\_ENDPOINT
evidence/P01-P14/P14/processed/p14\_benzotricyclobutadiene\_fixed\_geometry\_smoke\_v0.1.json / processed-record / main / HISTORICAL\_TECHNICAL\_NOT\_SCIENTIFIC\_ENDPOINT
evidence/P01-P14/P14/inputs/README\_zh-CN.md / input-reference / main / CURRENT
evidence/P01-P14/P14/inputs/source\_proxy\_G.xyz / input-reference / main / CURRENT
evidence/P01-P14/P14/inputs/source\_proxy\_PLG.xyz / input-reference / main / CURRENT
software/scripts/run\_p14\_benzotricyclobutadiene\_smoke.py / program-reference / main / REFERENCE\_ONLY\_NOT\_EXECUTABLE\_DISPATCH
software/scripts/validate\_p14\_memory\_controlled\_conditional\_scf.py / program-reference / main / REFERENCE\_ONLY\_NOT\_EXECUTABLE\_DISPATCH
software/scripts/run\_p14\_benzotricyclobutadiene\_source\_level\_fixed\_geometry.py / program-reference / main / REFERENCE\_ONLY\_NOT\_EXECUTABLE\_DISPATCH
software/scripts/run\_p14\_benzotricyclobutadiene\_production\_optimization.py / program-reference / main / REFERENCE\_ONLY\_NOT\_EXECUTABLE\_DISPATCH
software/scripts/classify\_p14\_strained\_aromatic\_pi\_distortivity.py / program-reference / main / REFERENCE\_ONLY\_NOT\_EXECUTABLE\_DISPATCH

<a id="p14-tasks"></a>

### 固定七任务

七任务保留原task ID与六字段；命令依据已读任务书接口，复制仅文本、不执行。固定平台历史按来源等级阅读，不移用用户分子验收。

<a id="task-cards"></a>

<a id="task-evidence"></a>

### evidence · L0 冻结证据

**用途**

冻结证据完整性检查，不新复算。

**前提**

已持有适用镜像、Docker Linux/amd64、已有PS7.3+及持久输出。

**本地步骤**

<a id="task-evidence-command"></a>

```powershell
$fixedImage='sha256:ddc45b1fe500ed3d5ed30520eb4e49f3969cb69f02121f28e2ff851f7a724f54'
$fixedOutput='D:\your-work\fixed-p14-runs'
./scripts/start-runtime.ps1 -Task evidence -Image $fixedImage -OutputRoot $fixedOutput
```

**输出**

启动器打印新目录；run-manifest.json及stdout／stderr；无分子result。

**判读**

完整性不是科学认证。

**来源**

已读任务书5.2接口与固定科学来源索引；本轮未重运行。

 <a id="core-tests"></a>

### core-tests · L1 登记实现测试

**用途**

条件SCF等实现测试。

**前提**

已持有适用镜像、Docker Linux/amd64、已有PS7.3+及持久输出。

**本地步骤**

<a id="core-tests-command"></a>

```powershell
$fixedImage='sha256:ddc45b1fe500ed3d5ed30520eb4e49f3969cb69f02121f28e2ff851f7a724f54'
$fixedOutput='D:\your-work\fixed-p14-runs'
./scripts/start-runtime.ps1 -Task core-tests -Image $fixedImage -OutputRoot $fixedOutput
```

**输出**

启动器打印新目录；run-manifest.json、stdout／stderr与实际测试输出；无分子result。

**判读**

不拼造分子账本，不等于完整复算。

**来源**

已读任务书5.2接口；固定科学来源索引；未重运行。

 <a id="p14-smoke"></a>

### p14-smoke · L2 技术检查

**用途**

固定STO-3G技术smoke，非科学端点。

**前提**

适用本地镜像、Docker Linux/amd64、已有PS7.3+；8线程是请求不是硬配额。

**本地步骤**

<a id="p14-smoke-command"></a>

```powershell
$fixedImage='sha256:ddc45b1fe500ed3d5ed30520eb4e49f3969cb69f02121f28e2ff851f7a724f54'
$fixedOutput='D:\your-work\fixed-p14-runs'
./scripts/start-runtime.ps1 -Task p14-smoke -Image $fixedImage -OutputRoot $fixedOutput -Threads 8
```

**输出**

打印新运行目录；run-manifest.json、stdout／stderr与适用result.json／report.md。

**判读**

仅登记技术范围，不是高层科学认证。

**来源**

已读任务书5.2、P14保存摘录；未重运行。

 <a id="p14-equivalence"></a>

### p14-equivalence · 实现等价性

**用途**

登记直接与内存受控实现比较。

**前提**

适用镜像、Docker Linux/amd64、已有PS7.3+与有效资源；8线程非硬配额。

**本地步骤**

<a id="p14-equivalence-command"></a>

```powershell
$fixedImage='sha256:ddc45b1fe500ed3d5ed30520eb4e49f3969cb69f02121f28e2ff851f7a724f54'
$fixedOutput='D:\your-work\fixed-p14-runs'
./scripts/start-runtime.ps1 -Task p14-equivalence -Image $fixedImage -OutputRoot $fixedOutput -Threads 8
```

**输出**

打印新目录；run-manifest.json、stdout／stderr及适用result.json／report.md。

**判读**

仅受测范围；独立WSL2一次预检FAIL历史保留。

**来源**

已读任务书5.2及P14保存摘录；未重运行。

 <a id="p14-fixed"></a>

### 高级 · p14-fixed · L3 固定几何（新计算）

**用途**

登记固定P14几何；需用户独立决定启动新计算。

**前提**

适用镜像、Docker Linux/amd64、已有PS7.3+；13000MiB有效主机／cgroup可用内存预检，未知或不足拒绝。8线程非硬配额。

**本地步骤**

<a id="p14-fixed-command"></a>

```powershell
$fixedImage='sha256:ddc45b1fe500ed3d5ed30520eb4e49f3969cb69f02121f28e2ff851f7a724f54'
$fixedOutput='D:\your-work\fixed-p14-runs'
./scripts/start-runtime.ps1 -Task p14-fixed -Image $fixedImage -OutputRoot $fixedOutput -Threads 8
```

**输出**

打印新目录；run-manifest.json、stdout／stderr及适用result.json／report.md。

**判读**

anchor资格与比较分开；L3严格断网未执行。

**来源**

已读任务书5.2与P14摘录；未重运行。

 <a id="p14-optimize"></a>

### 高级 · p14-optimize · L4 约束结构响应（新计算）

**用途**

平面D3h五参数子空间优化，非全空间或全局最小；需用户独立决定新计算。

**前提**

适用镜像、Docker Linux/amd64、已有PS7.3+；13GiB有效主机／cgroup内存预检，未知或不足拒绝。8线程非硬配额。

**本地步骤**

<a id="p14-optimize-command"></a>

```powershell
$fixedImage='sha256:ddc45b1fe500ed3d5ed30520eb4e49f3969cb69f02121f28e2ff851f7a724f54'
$fixedOutput='D:\your-work\fixed-p14-runs'
./scripts/start-runtime.ps1 -Task p14-optimize -Image $fixedImage -OutputRoot $fixedOutput -Threads 8
```

**输出**

打印新目录；run-manifest.json、stdout／stderr与适用result.json／report.md／checkpoint.json。

**判读**

L4可留存检查点，不能恢复；严格断网未执行。

**来源**

已读任务书5.2、P14摘录；未重运行。

 <a id="p14-classify"></a>

### p14-classify · 固定协议分类

**用途**

读取本次兼容四类分阶段结果与身份。

**前提**

适用镜像与环境；四份完整目录均在所选OutputRoot内；YOUR\_\*替换为实际目录，不能用冻结JSON或缺manifest历史文件。

**本地步骤**

<a id="p14-classify-command"></a>

```powershell
$fixedImage='sha256:ddc45b1fe500ed3d5ed30520eb4e49f3969cb69f02121f28e2ff851f7a724f54'
$fixedOutput='D:\your-work\fixed-p14-runs'
./scripts/start-runtime.ps1 -Task p14-classify -Image $fixedImage -OutputRoot $fixedOutput `
  -SmokeRun 'D:\your-work\fixed-p14-runs\YOUR_SMOKE_RUN' `
  -OptimizationRun 'D:\your-work\fixed-p14-runs\YOUR_OPTIMIZE_RUN' `
  -EquivalenceRun 'D:\your-work\fixed-p14-runs\YOUR_EQUIVALENCE_RUN' `
  -SourceLevelRun 'D:\your-work\fixed-p14-runs\YOUR_FIXED_RUN'
```

**输出**

打印新目录；run-manifest.json、stdout／stderr及适用分类result.json／report.md。

**判读**

Runtime核对任务、退出码、身份、哈希、依赖与协议；上游partial／disagreement可退出0，联合资格非PASS仍记FAIL。consistent仅固定协议范围。

**来源**

已读任务书5.2与P14摘录；未重运行。

### 平台 × 任务：历史记录，不是现场测试

Docker 各项均有各自范围的 PASS 记录。独立 WSL2 前四项有 PASS，后三项未执行。网页未执行测试，不证明新镜像、新环境或新输入通过。

<a id="history-registry"></a>

唯一历史状态登记 · 附件转述

| 任务 | Docker | 独立 WSL2 |
| --- | --- | --- |
| evidence | PASS · L0 完整性 | PASS · 登记范围 |
| core-tests | PASS · L1 实现测试 | PASS · 登记范围 |
| p14-smoke | PASS · L2 技术检查 | PASS · 登记范围 |
| p14-equivalence | PASS · 受测实现比较 | PASS · 受测范围；另有一次预检 FAIL |
| p14-fixed | PASS · 固定几何anchor资格 | NOT\_EXECUTED |
| p14-optimize | PASS · 登记约束优化资格 | NOT\_EXECUTED |
| p14-classify | PASS、consistent · 限定固定协议 | NOT\_EXECUTED |

<a id="help"></a>

06 / HELP & DELIVERY

## 帮助与来源

<a id="revision-20261009-sources"></a>

### 2026-10-09修改来源与外部本地复核

用户修改文件：YOUMIND\_REQUIRED\_CHANGES\_20261009\_zh-CN（01a11ee5-6d9e-70ec-bf05-0c98e3f38174）。上传ZIP来源记录：14成员CRC实际读取通过、54031 bytes、SHA256 3aa579f84d2b489755cf14b808a9535a82bf12bbf06dc34c21c2afb387d19811。以下为外部本地复核源的路径文字，不是假外链，也不将参考全文装入10成员指南包。

- source\_basis/PROTOCOL\_CASES\_BATCH3\_zh-CN.md
- source\_basis/PROTOCOL\_CASES\_BATCH3\_ACCEPTANCE\_zh-CN.md
- source\_basis/SOURCE\_INSTALLATION\_zh-CN.md
- source\_basis/SOURCE\_INSTALLATION\_ACCEPTANCE\_20261009\_zh-CN.md
- 环状体系尺寸与状态对照 pilot JSON与REVIEW\_SUMMARY（来源索引名；不虚构未提供的完整路径）

外部2026-10-09 Edge154本地复核严格绑定旧导出HTML：166102 bytes，SHA256 ` f1b634e30a16438c635c634b07f46a6ff75a7d6c665b85ee13ce19cd20af727c `；ZIP：311948 bytes，SHA256 ` abbce379db36240b97996f23322f57a11a8044693ce67be4045b0e1514eaf65b `。不是YouMind本轮自执行，不是新版继承PASS，也不是GitHub部署。

旧字节外部记录：10成员CRC／磁盘哈希、8副本一致、74逻辑复制PASS（40 raw equal，34仅LF→CRLF）、7维护下载、水request 277 / XYZ 123 / 预算286精确身份。HTTP根／模拟repo刷新PASS、3路径／清除PASS、默认HTTP重开PASS；真禁JS仅9关键词覆盖。搜索仅OBSERVED；真200%缩放、全键盘、多浏览器仍NOT\_EXECUTED。不要修改复制代码来修平台换行。

YouMind原自动回读BLOCKED历史继续保留，不要求用户再次重复点击。当前修后脚本、三宽度默认／全展开／路径／手机菜单、导出、CRC与复制下载验收均待执行，不预填PASS，不引用旧SHA作为新身份。

维护：进入解压后的 ` ai4orgchem-runtime-guide/ ` 目录，运行 ` python -m http.server 8000 `，浏览 ` http://localhost:8000/docs/ `。仅静态指南维护，不启动Runtime；无真实托管。10成员共同顶层保持，包外清单／审计JSON和MD按当前字节动态生成。

原YouMind提供时状态（历史）：条件Compute BLOCKED；；远CI NOT\_EXECUTED；镜像分发BLOCKED；外部专家咨询已取消非前置。该原包轮不运行Runtime/Docker/WSL/科学，不发布、不改权限；本次公开与实际CI另见当前同步记录。

<a id="home-support-records"></a>

### 支持范围、部署与历史验证记录（按需查阅）

<a id="github-public-status"></a>

### 当前公开版本：AI4OrgChem Runtime v0.1.0

2026-10-10已正式发布[v0.1.0源码与指南Release](https://github.com/CCcolab/AI4OrgChem-Runtime/releases/tag/v0.1.0)，标签指向**b4a74e7**。提供带Git身份证明的源码ZIP、10成员指南ZIP和SHA-256清单；网页不提供在线计算，实际命令在用户本地Runtime执行。

GitHub仓库右侧的Releases已有Latest版本；引用入口由CITATION.cff提供。[作者与维护者说明](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/AUTHORS.md)已公开。Contributors和Languages由GitHub自动统计，旧本地邮箱未关联账号，不改写历史或虚构贡献者；Packages未发布，镜像分发仍受限制。

发布提交的[两个公开CI job](https://github.com/CCcolab/AI4OrgChem-Runtime/actions/runs/38054799419)和[Pages部署](https://github.com/CCcolab/AI4OrgChem-Runtime/actions/runs/38054799318)成功，限定工程范围，不认证全部科学服务。原失败浏览器下载补验已由外部审阅者经负责人报告为限定PASS；旧失败记录保留。条件态Compute仍未开放，L4检查点不支持恢复。

### 首次源码同步（历史记录）

2026-10-09 已按项目负责人授权公开到 [CCcolab/AI4OrgChem-Runtime](https://github.com/CCcolab/AI4OrgChem-Runtime)。首个候选提交 **06d5088** 的 [首次远端 CI](https://github.com/CCcolab/AI4OrgChem-Runtime/actions/runs/37933616122) 三项 job 均成功：Linux 构建、L0/L1、容器探针及限定工程测试；真实 P11 预检保留一项跳过。不是全部科学任务验收。网页文件已随源码同步，GitHub Pages 已于2026-10-10启用，可[直接打开静态指南](https://cccolab.github.io/AI4OrgChem-Runtime/)；本页不提供在线计算，复制的计算命令在用户本地执行。

；镜像分发 BLOCKED；旧条件态 Compute BLOCKED；L4 仅保存检查点、不能恢复运行。下面原提供时及既有版本的状态记录保留历史范围，当前公开与 CI 记录见 [本次同步记录](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/GITHUB_PUBLIC_SYNC_20261009_zh-CN.public.md)。该首次同步时尚未创建Runtime版本、标签或Release；当前状态以上方v0.1.0记录为准。

### 原提供时的项目与阅读状态（历史）

### 项目说明、状态与来源

AI4OrgChem Runtime 通过固定源码与依赖、分层启动和持久输出，帮助用户检查证据、运行登记案例并整理复核材料。科学程序、协议与判定由对应科学来源管理；本指南说明各入口的使用方法和适用范围。

已读任务书、基线、索引、入口、请求与P14保存摘录的核对等级逐项列于来源表；29份参考文件仅索引、未逐读。本轮未重运行或独立哈希。[查看来源索引](#sources)。

### 五项状态摘要

- 开发候选未公开发布（材料记载）。
- 原七任务：Docker 候选历史记录仅限固定协议与登记范围，见唯一平台矩阵；不意味着所有比较判据全通过。
- 用户分子 Check / Report：登记工程范围，不继承原七任务科学验收。
- 普通RHF首版限定范围内可用；旧条件态生产Compute：BLOCKED。

### 需要深入复核？查看专业阅读路径 S1—S6

三个用户流程均不要求先完成S1；以下背景按需阅读。

1. S1 科学协议与证据范围查阅
2. S2 条件 SCF 实现审查
3. S3 运行资格与实现等价性检查
4. S4 登记固定几何与 anchor 资格复核
5. S5 登记约束结构响应与优化资格复核
6. S6 联合分类与独立复核交付

原 S1—S6 指南只描述原七任务及 P14。当前普通分子、固定服务、专题协议和高成本模块的输入、方法、门槛、结果与解释按下方统一服务登记及专业矩阵查阅；不把旧指南范围扩大成所有服务。

<a id="verification-records"></a>

## 验证记录（外部记录与当前版本分开）

外部来源：用户上传 REVIEW\_SUMMARY 转述；执行方本地 Codex，浏览器 IAB，2026-10-08。非 YouMind 本轮自执行，非真实 GitHub 部署。

严格绑定旧 HTML：161123 bytes，SHA256 ` 9a40351eac2ea05ef3990b5a6f7d782b8b9311e0abf4f06a5efbc965e3efcaea `；ZIP：257444 bytes，SHA256 ` 2f448b02c737b60caa605af76543d085649a8593d2da2652c54ebd0271ab643b `。新版字节改变，不继承 PASS。

外部限定记录：10 ZIP 成员 CRC、安全唯一路径、README 内外一致、水277/123一致、132 ID无重复／49 targets、50复制回读（49+Capabilities/List）、360/768/1440三宽度无整页overflow、三路径与搜索、默认导出、真实HTTP根模拟repo子路径与刷新、基础手机菜单与Tab范围。

200%真缩放、真禁JS、全键盘、多浏览器、二次导出、全部维护独立按钮：NOT\_EXECUTED。当前版本完整检查默认 NOT\_EXECUTED；字节身份按钮不执行结构测试，不授予结构PASS。

<a id="verification-current"></a>

```text
NOT_EXECUTED
```

<a id="batch2-sources"></a>

### 第二批来源身份与支持矩阵

此前阅读记录：两个MD、candidate-image与support-matrix四个短文件已完整读取；大型batch2-verification仅已读取运行、镜像、工程测试、失败等相关段，非1967行全审，非原运行目录全审。准确五路径：docs/PROTOCOL\_CASES\_BATCH2\_zh-CN.public.md；docs/PROTOCOL\_CASES\_BATCH2\_VALIDATION\_zh-CN.public.md；validation/protocol-cases/batch2-verification.public.json；validation/protocol-cases/support-matrix.public.json；validation/protocol-cases/candidate-image.json。不虚造公开地址。

**第二批文档提交**

a44fa481af7c5a62d9d7b923f3b3f0d4947e682b

**最新本地候选构建／镜像（不是全部最终镜像重算）**

38cc11b02a978c03c3e2d69a41fc8a0d9886cc6e / sha256:9482bf47bd504c816a8978a5686bc581dba9a06b2bd6c0c9a98b86d801471440

**P03实际构建／镜像**

0ee566397844d9885d50ca2a2d5ae5b974f19425 / sha256:6eeccf5ba4192f827986625fae238982ab162e6aadffe6ffc03e3ef642c34e12

**片段条件能量组装/局域化端点与参照能量/条件态与稳定性诊断/P10实际构建／镜像**

647c7c5a42aa2acd98be388cd77aa1824243351c / sha256:e20591dd7ba3b50f4bd68fcbeaec51b415923da747711bb0f5675bb6df427dd9

**π–π条件态与轨道响应/P05成功构建／镜像**

38cc11b02a978c03c3e2d69a41fc8a0d9886cc6e / sha256:9482bf47bd504c816a8978a5686bc581dba9a06b2bd6c0c9a98b86d801471440；早两失败Git封装缺口保留，非科学反例。

八ledger、八preflight、七live是已保存本地限定记录，不是本轮重算，不是总计算数或全通过数。115本地工程非GitHub Actions；science lane非其runner执行。内存为cgroup峰值，非RSS。所有科学项最终镜像重跑、scratch峰值、异机安装：NOT\_EXECUTED。

普通四步、水技术样例和固定案例已提供；完整网页验收仍有未执行项。任意用户分子的旧条件态比较 Compute BLOCKED；镜像分发 BLOCKED 等其他对象状态不改。

<a id="current-source-addendum"></a>

### 新版来源、提交与镜像身份（可复制，按需查阅）

以下为本次指示提供的来源索引与身份，不冒充本网页实际读取或执行验收。文档提交不当build，image tag不等于registry digest。

| 来源索引（材料列为已读） | 范围 |
| --- | --- |
| 普通guide／contract／acceptance／design | 普通首版合同、设计与限定验收 |
| 固定guide／acceptance／boundaries | 3个固定服务，不推广到通用任务 |
| schema／profile／2 deployments／2 candidate images／capabilities | 输入、环境、镜像及能力声明 |
| water／ethene templates／REVIEW\_SUMMARY／INDEPENDENT\_EXPORT | 冻结模板与来源保存记录 |

**文档提交**

` f7ddf447cb3a2255aa372afcc834d1e97937c57b `

**普通build**

` 1f139aa87dbd1dca8e318b5e9d0226b2a7c8668b `

**普通host**

` a3f6ec7536c510f06b7d521bc09515eb451b9cff `

**普通image**

` sha256:e7ffa6420e743a0db184897d21458d69ec90c113b9e3b3c0df7fd2a94a2e202e `

**fixed build**

` e572787b11bbfc3b9e95779a5166ae413040c50d `

**fixed host**

` e2e90e9bec3637c986d2b581b352730658677113 `

**fixed image**

` sha256:e5dde3bd5f426815b5940a193bbe1ef351a23e940d055a2c8cc1ea9ca5a8cfd2 `

**baseline**

124646 bytes；` 960df3dbf50701aa0decafd70d8a14b14812af5dec5afe9ae131d78981d3f409 `

来源记录称ZIP 36成员的实际CRC／size已验；这不是全Git源码认证。Git blob仅用户来源索引。旧独立HTTP／8项ZIP／reexport PASS保存为历史，不继承新版。下一批再做ZIP／QA，本页未执行。

<a id="current-service-registry"></a>

### 当前服务范围与验证依据

按研究问题选择模块；具体输入、结果字段、成本及允许解释见[当前专业服务矩阵](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/CURRENT_PROFESSIONAL_SERVICES_zh-CN.md)。本表引用统一能力登记，不授予计算权限，也不将历史验收转移到新安装。

[提交 be51dcbb 的 2 个 CI job 成功](https://github.com/CCcolab/AI4OrgChem-Runtime/actions/runs/38036972441)，范围是工程合同与旧入口 L0/L1；后续修改另行验证。

| 服务 | 输入与方法范围 | 已有数值验收 | 输入、协议、结果与入口 |
| --- | --- | --- | --- |
| 自己的分子 RHF 单点能量、轨道与 AO 密度 | User XYZ H/C/N/O, neutral closed-shell singlet, <=20 atoms and actual AO<=80; RHF/6-31G(d); no stability/minimum certification | Four ordinary RHF runs and four same-version PySCF direct wrapper controls; 12 recorded gates | [输入合同](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/schemas/molecular-single-point-v1.json) · [协议与判读](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/CURRENT_MOLECULAR_SINGLE_POINT_zh-CN.md) · [保存结果](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/validation/molecular-service/deployment-20261008.public.json) · [执行边界与入口](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/scripts/run-installed-runtime.py) |
| 冻结表值统计示例 | Frozen published table value recalculation; no PDF/CIF reauthentication, no quantum calculation | One recorded fixed task; P02/P13 use saved arithmetic, P01 one RHF plus Boys/PM | [输入合同](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/configs/registered-cases-v1.json) · [协议与判读](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/CURRENT_REGISTERED_CASES_zh-CN.md) · [保存结果](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/validation/registered-cases/deployment-20261008.public.json) · [执行边界与入口](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/scripts/run-installed-runtime.py) |
| 分子图规则与能量账本示例 | Original graph/RDKit formula rules and frozen energy ledger arithmetic; no quantum calculation | One recorded fixed task; P02/P13 use saved arithmetic, P01 one RHF plus Boys/PM | [输入合同](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/configs/registered-cases-v1.json) · [协议与判读](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/CURRENT_REGISTERED_CASES_zh-CN.md) · [保存结果](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/validation/registered-cases/deployment-20261008.public.json) · [执行边界与入口](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/scripts/run-installed-runtime.py) |
| 乙烯占据轨道变换与密度不变性示例 | One fixed ethene ordinary RHF/6-31G(d), one Boys and one Pipek-Mezey occupied rotation; density/energy invariance only | One recorded fixed task; P02/P13 use saved arithmetic, P01 one RHF plus Boys/PM | [输入合同](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/configs/registered-cases-v1.json) · [协议与判读](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/CURRENT_REGISTERED_CASES_zh-CN.md) · [保存结果](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/validation/registered-cases/deployment-20261008.public.json) · [执行边界与入口](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/scripts/run-installed-runtime.py) |
| 约束扭转路径账本与固定端点 DFT | ONE\_FROZEN\_ORIGINAL\_PROTOCOL\_POINT | One fixed live point/scoped scan plus saved ledgers; P07 ledger only | [输入合同](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/configs/protocol-cases-v1.json) · [协议与判读](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/CURRENT_PROTOCOL_CASES_zh-CN.md) · [保存结果](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/validation/protocol-cases/batch2-verification.public.json) · [执行边界与入口](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/scripts/run-installed-runtime.py) |
| 源原生双状态直接响应 | ONE\_FROZEN\_ORIGINAL\_PROTOCOL\_POINT | One fixed live point/scoped scan plus saved ledgers; P07 ledger only | [输入合同](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/configs/protocol-cases-v1.json) · [协议与判读](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/CURRENT_PROTOCOL_CASES_zh-CN.md) · [保存结果](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/validation/protocol-cases/batch2-verification.public.json) · [执行边界与入口](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/scripts/run-installed-runtime.py) |
| π–σ 条件能量单点 | ONE\_FROZEN\_ORIGINAL\_PROTOCOL\_POINT | One fixed live point/scoped scan plus saved ledgers; P07 ledger only | [输入合同](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/configs/protocol-cases-v1.json) · [协议与判读](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/CURRENT_PROTOCOL_CASES_zh-CN.md) · [保存结果](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/validation/protocol-cases/batch2-verification.public.json) · [执行边界与入口](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/scripts/run-installed-runtime.py) |
| 双片段条件能量独立组装 | ONE\_FROZEN\_ORIGINAL\_PROTOCOL\_POINT | One fixed live point/scoped scan plus saved ledgers; P07 ledger only | [输入合同](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/configs/protocol-cases-v1.json) · [协议与判读](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/CURRENT_PROTOCOL_CASES_zh-CN.md) · [保存结果](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/validation/protocol-cases/batch2-verification.public.json) · [执行边界与入口](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/scripts/run-installed-runtime.py) |
| 同 Hamiltonian 路径闭合账本 | Frozen same-Hamiltonian ledger only; no live mode | One fixed live point/scoped scan plus saved ledgers; P07 ledger only | [输入合同](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/configs/protocol-cases-v1.json) · [协议与判读](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/CURRENT_PROTOCOL_CASES_zh-CN.md) · [保存结果](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/validation/protocol-cases/batch2-verification.public.json) · [执行边界与入口](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/scripts/run-installed-runtime.py) |
| 丁二烯 GL 固定端点与参照热化学 | Fixed butadiene GL endpoint; same implementation initial-density comparison, no new optimization or full P08 replay | One fixed live point/scoped scan plus saved ledgers; P07 ledger only | [输入合同](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/configs/protocol-cases-v1.json) · [协议与判读](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/CURRENT_PROTOCOL_CASES_zh-CN.md) · [保存结果](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/validation/protocol-cases/batch2-verification.public.json) · [执行边界与入口](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/scripts/run-installed-runtime.py) |
| 环丁二烯固定几何条件态诊断 | FIXED\_GEOMETRY\_CBD\_G\_LIKE\_DSI\_SMOKE\_ONLY | One fixed live point/scoped scan plus saved ledgers; P07 ledger only | [输入合同](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/configs/protocol-cases-v1.json) · [协议与判读](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/CURRENT_PROTOCOL_CASES_zh-CN.md) · [保存结果](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/validation/protocol-cases/batch2-verification.public.json) · [执行边界与入口](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/scripts/run-installed-runtime.py) |
| 苯核排斥与五点普通 DFT 扫描 | FIVE\_FROZEN\_ORDINARY\_RKS\_BLA\_POINTS\_PLUS\_REUSED\_G\_GL\_LEDGER | One fixed live point/scoped scan plus saved ledgers; P07 ledger only | [输入合同](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/configs/protocol-cases-v1.json) · [协议与判读](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/CURRENT_PROTOCOL_CASES_zh-CN.md) · [保存结果](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/validation/protocol-cases/batch2-verification.public.json) · [执行边界与入口](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/scripts/run-installed-runtime.py) |
| P11 固定多态几何优化 | 17 registered states; only P11B-benzene-G accepted; remaining states NOT\_EXECUTED; no complete multistate assembly | One single-state source gate per P11/P12; independent AO/component audit coverage incomplete | [输入合同](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/configs/high-cost-cases-v1.json) · [协议与判读](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/CURRENT_HIGH_COST_CASES_zh-CN.md) · [保存结果](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/validation/high-cost-cases/deployment-verification.public.json) · [保存结果](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/validation/high-cost-cases/p12-n12-g-pilot-verification.public.json) · [执行边界与入口](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/scripts/run-installed-runtime.py) |
| P12 固定多态几何优化 | 61 registered states; only P12-N12-G accepted; remaining states NOT\_EXECUTED; no complete multistate assembly | One single-state source gate per P11/P12; independent AO/component audit coverage incomplete | [输入合同](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/configs/high-cost-cases-v1.json) · [协议与判读](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/CURRENT_HIGH_COST_CASES_zh-CN.md) · [保存结果](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/validation/high-cost-cases/deployment-verification.public.json) · [保存结果](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/validation/high-cost-cases/p12-n12-g-pilot-verification.public.json) · [执行边界与入口](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/scripts/run-installed-runtime.py) |
| P14 固定条件态、结构响应与联合分类 | Seven legacy tasks; fixed C12H6 source-proxy / D3h five-parameter protocol; checkpoints cannot resume | Recorded P14 gates and classification scoped to actual runs; L3/L4 strict offline NOT\_EXECUTED | [协议与判读](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/CURRENT_P14_BUILD_RUN_zh-CN.md) · [协议与判读](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/PROFESSIONAL_SERVICES_zh-CN.public.md) · [保存结果](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/validation/oci-summary.public.json) · [保存结果](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/validation/final-delivery-status.public.json) · [执行边界与入口](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/runtime/cli.py) |
| 用户分子条件态 Compute | V2 implemented and diagnosed; no qualified final endpoint; original gap/mapping/commutator gates unchanged | No qualified root; real native attempt ended incomplete at wall stop | [输入合同](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/schemas/user-molecule-request-v1.json) · [协议与判读](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/USER_MOLECULE_INTERNAL_VALIDATION_zh-CN.md) · [保存结果](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/validation/user-molecule/root-native-diagnostic-20261007.public.json) · [保存结果](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/validation/user-molecule/native-shutdown-engineering-20261007.public.json) · [执行边界与入口](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/USER_MOLECULE_INTERNAL_VALIDATION_zh-CN.md) |
| 条件态研究诊断与合作停止工程 | Real root attempt: 139 completed NR / 138 callback success plus deadline failure; no returned root or formal tail/closure | No formal qualified endpoint; zero-native stop checks do not grant numerical qualification | [协议与判读](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/USER_MOLECULE_ROOT_NATIVE_DIAGNOSTIC_20261007_zh-CN.public.md) · [保存结果](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/validation/user-molecule/root-native-diagnostic-20261007.public.json) · [协议与判读](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/USER_MOLECULE_NATIVE_SHUTDOWN_ENGINEERING_20261007_zh-CN.md) · [保存结果](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/validation/user-molecule/native-shutdown-engineering-20261007.public.json) · [执行边界与入口](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/docs/USER_MOLECULE_ROOT_NATIVE_DIAGNOSTIC_20261007_zh-CN.public.md) |

[下载同源能力表 JSON](https://cccolab.github.io/AI4OrgChem-Runtime/runtime-guide/capabilities-v2.json)；[最小数值见证与只读复核](https://github.com/CCcolab/AI4OrgChem-Runtime/tree/main/evidence/numerical-witnesses)。声明文件 SHA-256：` 09be294383a8aceb552357a509eaac62ef0bc38c9236558213ae0c4988ffe109 `。

### 常见问题

<a id="faq-current"></a>

### 01 当前普通服务是否可用？

普通RHF单点可在合同限定范围内、使用匹配本地环境运行；旧条件态Compute仍为BLOCKED，不能笼统说所有计算入口都已关闭。

### 02 自选分子的普通DFT是否开放？

自选分子的普通DFT尚未开放；部分固定协议已有受限RKS/GL/条件核。普通首版仍仅RHF／6-31G(d)登记范围。

### 03 普通服务要分A/B吗？

无需A/B、PID或xy平面；不继承旧条件态输入约束。

### 04 新入口需要pwsh吗？

新普通／固定入口支持Windows PS5.1，无需pwsh。旧七任务及旧条件态仍按其已有PS7合同。

### 05 哪里取得环境镜像？

源码、网页、镜像分别准备；无已确认公开镜像分发地址，不虚构下载链接。

### 06 WSL失败要reset吗？

不要reset、删除发行版或恢复出厂。保存错误；

### 07 AO超限可改基组重试吗？

不能以改基组、fallback或retry绕过首版合同；actual AO必须符合限制。

### 08 应保存哪些records？

保存完整运行目录：输入快照、合同、guard、resource、manifest、计算数组与账本及host／worker回执。

### 09 没有能量能记0吗？

不能。未知、缺失、NOT\_EXECUTED不等于0；退出0不等于记录完整或PASS。

### 10 NPZ是密度图吗？

不是；它保存原AO顺序的自旋求和矩阵与轨道数组，不是grid、等值面或实验密度。

### 11 SCF收敛就是基态吗？

不是。12项数值资格也不是稳定极小认证；稳定性NOT\_EXECUTED，HOMO／LUMO不套旧正能隙门槛。

### 12 固定局域化能处理任意分子吗？

不能。P01仅固定乙烯与Boys／PM同态占据旋转的不变性，不是通用用户局域化或完整P01认证。

### 13 固定服务能换输入吗？

不能换XYZ、表值、基组、分片或容差。结构与光谱表值统计／P13为不进行量子计算固定服务，不推及任意PDF、CIF或SMILES。

### 14 可以resume吗？

不能。普通服务无retry／resume／fallback；L4留存检查点不代表可恢复，严格断网L3／L4 NOT\_EXECUTED。

### 15 网页能上传和执行吗？

不能。只提供本地阅读、文本复制与导出，不上传分子，不运行Runtime。

### 16 同PySCF对照与历史PASS说明什么？

同PySCF直接参考仅封装一致性，不是独立引擎认证。旧独立HTTP／8项ZIP／reexport PASS仅来源保存历史，不继承新版；当前源码与静态指南已公开；CI记录及范围见统一能力表，镜像分发仍受限制，Colab暂缓，外部咨询已取消。

### 是否需要同样的安装包？

Git／来源ZIP是源码，环境另需准备，网页ZIP只含网页，没有公开镜像包可承诺。见[准备条件](#quick-start)。

### 没有Docker能做什么？

宿主查阅／Review与Report按工具条件可用；Check／固定任务需要容器。见[准备条件](#quick-start)。

### 证据目录与固定协议如何分开？

Show/Review只查阅证据及核对所选材料；固定协议使用本区独立登记入口，不是通用重算。普通用户用自己的XYZ走普通RHF四步，不靠PID。多态约束结构优化/P12固定高成本入口见第三批研究示例；仅苯G与N12-G旧候选单态有受限验收，新安装高成本重放NOT\_EXECUTED。见[目录](#proposition-catalog)。

### 能换自己的分子开展条件能量与结构响应复核吗？

不能，P14固定案例不可替换；自有XYZ可走首版普通RHF单点，旧条件态Check不授予Compute资格。见[四步](#user-molecule)。

### 所选文件匹配意味着什么？

仅字节身份，非科学认证或588文件审计。见[判读](#results)。

### Check通过后怎么办？

保存实际目录、读取Report，不能升级Compute。见[第四步](#user-molecule)。

### PS5.1提示requires／找不到pwsh？

新普通／固定入口兼容PS5.1，不要求pwsh；仅旧任务入口的-PowerShell7需提供已有PS7.3+真实路径，不自动安装。见[准备条件](#quick-start)。

### Docker启动失败？

核对引擎、保存错误，不建议恢复出厂、删发行版或自动升级WSL。见[前提](#p14-tasks)。

### 本地工程CI与GitHub CI相同？

不同，历史专项与远端 job 范围分别记录。2026-10-09 提交06d5088的首次 Actions 三项 job 成功，真实P11预检一项跳过；网页验收另列，见[当前同步状态](#github-public-status)及[来源](#sources)。

### 缺失、历史FAIL／NOT\_EXECUTED怎么处理？

如实保留，不造成功、不覆盖旧材料。见[判读](#results)。

### 维护与开发入口

[core-tests](#core-tests)／[smoke](#p14-smoke)／[equivalence](#p14-equivalence)仅登记维护范围。build-docker.ps1 -CheckOnly不访问引擎、不构建、不证明r3就绪。源码准备不安装依赖或构建镜像。见[来源](#sources)；下批接线、维护文本同步与验收。

### 路径怎么选？

了解公开证据选 evidence；复核登记案例查看全部任务；维护环境参考 core-tests / p14-smoke / p14-equivalence。路径只改变导航与任务展示，不批准计算。

### 命令在哪里运行？

在本地 Runtime 项目目录中的终端运行，不在浏览器运行。先确认本地条件，再使用首次使用区登记的命令。

### 输出在哪里？

对照本次运行记录及 RUN / LOCAL\_DELIVERY；已提供普通四步、水技术样例及固定案例；完整网页验收仍有未执行项。本页不读取你的文件或私有路径。

### PASS 有什么科学含义？

看对应任务、平台、资格、比较与分类范围。程序执行状态不等于完整复算或科学认证。

### Check 可用，Compute 为什么 blocked？

工程检查资格与生产计算资格必须区分；Check / Report 登记工程可用不授予生产 Compute 资格。候选规则待审属于记录之一，不由此推导 BLOCKED 的单一因果；完整原因须核对原始记录。

### 源码如何保留？

点击下方“保留网页HTML”，由浏览器在本地生成单文件下载；不会上传或产生平台链接。已取得完整源码；独立运行与迁移验收未完成。请确认浏览器实际保存，并按维护说明复核。

### 反馈前可整理什么？

建议草案，非正式模板：任务 / 阶段、版本 / 候选、使用命令、本地原始记录位置、已做检查。只在你本地整理；页面不读取、上传或收集私有路径。

<a id="sources"></a>

### 已核对原文与保留限制

六份上传材料已读并静态核对：v0.4任务书、WEB\_CONTENT\_BASELINE、SOURCE\_INDEX、START\_HERE、request-pilot、P14\_REVIEW保存摘录；29份参考文件仅索引，未逐文件读取或哈希。原始完整科学输出未提供，本轮不重运行。源路径不是下载URL。

| 区域 | 主张 | 对象 | 版本日期 | 源路径 | 核对等级 | 范围 | 关联显示 | 未验证项 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 全部 | 操作与状态基线 | 任务书 | v0.4 / 2026-10-08 | AI4OrgChem\_Runtime\_YouMind\_网页修改要求\_v0.4\_20261008\_zh-CN | 原文静态已读 | 接口及验收要求 | 六区域 | 执行与浏览器验收 |
| tasks | 14命题登记 | 基线 | 1179行阅读记录 | WEB\_CONTENT\_BASELINE.json；辅助稿《AI4OrgChem 命题目录》 | 主助手实读；本轮读取辅助稿 | 标题、子项、材料关系 | p01—p14 | 科学算术复验 |
| help | 来源与入口 | 索引／请求入口 | 本次资料 | SOURCE\_INDEX / START\_HERE | 主助手实读记录 | 来源导航 | 本地准备、资料 | 公开URL与可访问性 |
| user-molecule | 乙烯请求 | 请求文件 | 工程候选 | examples/user-molecule/w05-candidates/ethene-planar-technical-v1/request-pilot.json | 主助手实读记录 | Check夹具，不是研究端点 | 四步流程 | JSON与XYZ原文已静态内联；逐字复制/导出/运行验证NOT\_EXECUTED |
| user-molecule | 乙烯固定几何 | molecule.xyz | 本次上传 | examples/user-molecule/w05-candidates/ethene-planar-technical-v1/molecule.xyz | 本次上传原文静态读取 | 已有六原子乙烯工程夹具，非研究结果 | molecule-xyz-text | 未独立字节哈希/Runtime重运行；逐字复制/导出/运行验证NOT\_EXECUTED |
| results | 既有consistent | P14摘录 | 2026-10-02 | docs/examples/P14\_REVIEW\_20261002\_zh-CN.public.md | 保存记录摘录已读 | 固定C12H6 source-proxy | 历史折叠 | 本轮未重运行 |
| 全部 | 参考来源导航 | 29参考文件 | 索引记录 | SOURCE\_INDEX中所列29份 | 仅索引，非逐读 | 不冒充原文验证 | 来源说明 | 逐文件核对、独立哈希 |

### 身份与独立状态

2026-10-07旧条件态历史记录，历史P14计算2026-10-02，内容核对2026-10-08；不混用日期或提交身份。

**该历史材料提交**

1eed31c4ab8ae224f0df86b9eb0b26bd28388d1e

**停止工程受测提交**

6eb356a0ebaa647bdf4aa6ea4b0f90cf69fc07f6

**真实根诊断执行提交**

73e8dfd8aef4881dec6b8cd30b21b2228f8b51ab

**固定P14旧镜像构建Runtime**

f30b2906794d14f9030daab779c0d6a7cd4bd6f7

**用户分子r3镜像构建Runtime**

5098775c9cf40468ab92712447a3e5c7b1361a63

**r3本地image ID**

sha256:24f46f33264924e5d3d3bec386298585267c6f30d6e6a0cd0a6486ecf45db93d

**用户分子科学适配提交**

cc7437901119e71ef7945a12813c021c383e7648

Runtime源码与静态指南已公开；任意用户分子的旧条件态比较 Compute BLOCKED；外部咨询CANCELLED\_BY\_USER，不是科学批准；首次Actions三项job已在06d5088通过，范围见当前同步记录；；镜像分发BLOCKED；源码与指南已公开，GitHub Pages静态指南已启用；本页没有在线计算，Colab暂缓。固定L3／L4严格断网未执行，L4不能恢复。

### 原七任务科学来源

AI4OrgChem v0.3.2 · 固定提交：

` 28511f3d84fa65707a107cde1e8121a7b4334ecb `

仅用于原七任务，不用于用户分子分支。历史记录与协议范围依对应原始资料核对。

### P0 · 首要补齐

- README / REVIEW\_ENTRY / mdr-002
- RUN / LOCAL\_DELIVERY / INSTALL
- USER\_MOLECULE\_W07\_ENGINEERING\_TRIAL / USER\_MOLECULE\_REPORT\_20261006

### P1 · 复核与实际结果

- USER\_PATHS / PROFESSIONAL\_SERVICES / REVIEW\_RESULTS
- 复核报告模板 / 真实 L0 和 P14 输出

### P2 · 授权分发资料

有效获准源码下载资料 URL 待补。首版不放外部下载或仓库链接。

历史拒绝记录索引：runtime/README\_zh-CN.md、REVIEW\_ENTRY\_zh-CN.md、evidence/live；记录原文待补。

无第三方必要资源，不加载外部字体、图库、脚本或科学插图。许可范围仍待权属确认，不默认开源许可。

### 导航原型与本地保留

这是导航原型；已提供普通四步、水技术样例及固定案例；完整网页验收仍有未执行项。已取得完整源码，独立运行与迁移验收未完成。

**本轮网页资料包 · v0.3.0-candidate**

沿用下方“下载完整网页包 ZIP”：浏览器本地生成下载，不需上传；一次解压整个包即可，不需逐个解压子目录。包仅含网页、维护资料和水模板，不含 Runtime 源码、Docker 镜像或科学完整档案。Runtime 与镜像须另备；不运行计算、不自动安装、无发布。

- ` docs/index.html ` — 内嵌 CSS/JS 的独立网页，解压后直接打开。
- ` docs/.nojekyll ` — 空的静态托管标记。
- ` README.md ` — 交付与本地阅读说明。
- ` content/guide_zh-CN.md ` — 正文 Markdown 快照。
- ` provenance/sources.md ` — 来源与授权边界。
- ` verification/checks.md ` — 当前检查状态与历史证据。
- ` MIGRATION.md ` — 待执行的迁移维护步骤。
- ` MANIFEST.txt ` — 10 成员用途与交付边界清单。
- ` templates/molecular-service/water/request.json ` — 水请求原文，277 字节。
- ` templates/molecular-service/water/molecule.xyz ` — 水几何原文，123 字节。

水两个文件保持 UTF-8、LF 及末尾 LF，不 trim。动态 QA 与包外清单不装入 ZIP，可另外下载。新包大小和 SHA-256 由现场生成，不继承历史实物数值；尚未完成新包 CRC/哈希独立验证或迁移验收。

下列下载仅在你点击时发生，使用内嵌文本或初始化时保留的 HTML，通过本地 Blob 生成；不依赖当前页面 URL，不上传。

如果当前浏览器的动态导出被完整性守卫拒绝，可下载已核验的部署文件：[静态指南 ZIP](https://cccolab.github.io/AI4OrgChem-Runtime/runtime-guide/current-guide.zip) · [静态指南 HTML](https://cccolab.github.io/AI4OrgChem-Runtime/runtime-guide/current/docs/index.html)。这些文件由实际下载产物核验后随仓库部署，不依赖当前浏览器的快照解析；身份与哈希见本轮导出验收记录。动态导出的守卫继续保留。

静态指南由GitHub Pages托管；托管服务的访问记录由GitHub管理。网页不向计算后端提交分子或请求，复制与导出在本地浏览器完成；科学计算在用户本地Runtime执行。

## 发布后同步状态说明
当前同步卡已补齐v0.1.0正式发布；本次实际正文与下载字节见validation/web-guide/postrelease-status-card-20261010.json。正式Release标签和附件保持不变，不用新网页字节冒充旧包。

## v0.1.0源码与指南发布材料
发布入口：https://github.com/CCcolab/AI4OrgChem-Runtime/releases/tag/v0.1.0 。本次发布链接文字与实际导出字节记录见 validation/web-guide/release-v0.1.0-downloads.json；旧修订及原浏览器补验记录各保留其原字节身份，不作为本次新包哈希。没有改动导出算法或科学代码。

## 静态指南网址与使用方式（2026-10-10）
GitHub Pages静态指南已启用：https://cccolab.github.io/AI4OrgChem-Runtime/ 。可直接在浏览器阅读、搜索、复制命令和下载指南；网页不提供在线计算，计算命令仍由用户本地Runtime执行。整个已公开main/docs作为发布源。

## 2026-10-09源码首次公开与远端CI记录（历史）
2026-10-09已按项目负责人授权公开源码与指南：https://github.com/CCcolab/AI4OrgChem-Runtime 。06d5088首次CI三项job均成功，真实P11预检一项跳过；详见https://github.com/CCcolab/AI4OrgChem-Runtime/actions/runs/37933616122 。Pages未启用；；未创建新版本/标签/Release。

说明：下列状态是YouMind原提供时的登记，不是最新包外实测。本次修订身份与受限实测见 Runtime validation/web-guide/special-review-followup-20261010.json；此前 full-review-repairs-20261010.json、online-browser-followup-fa7b4ee-20261010.json 和 export-compatibility-round2-20261010.json 保留各自旧字节身份，不验证本次修订；final-consistency-r2-20261009.json 仅为历史身份；手工QA默认未填写及200%缩放／完整键盘／多浏览器NOT_EXECUTED单独保留。

## 原YouMind v0.3.0-candidate交付登记（历史）
候选非已验收；currentordinaryenabled / legacyconditionalblocked。物理顺序 overview、quick-start、user-molecule、results、tasks、help。10 members：原8文件，加 templates/molecular-service/water/request.json 与 molecule.xyz；277/123 bytes、LF结尾、代码textContent原文。14 evidence、7旧任务、3固定案例、1普通服务，12数值checks。原提供时新字节版本的复制核对、ZIP实物CRC/哈希、HTML一致性、重开再导出与迁移及完整WEB合同尚未完成；修订前下载实物与三宽度结构实测只作历史，原提供时QA不继承。新包大小和SHA-256须现场生成。
