# 用户分子单点能量与轨道／密度使用指南

本入口接受你自己的 XYZ 分子结构，计算普通闭壳层 RHF 单点能量，并导出轨道和 AO 电子密度矩阵。无需选择命题编号、阅读专著或指定项目特有的片段。

2026-10-08，首版本地候选已完成验收：锁定镜像内114项工程测试通过，水、甲烷、氨及乙烯的四次正式运行和四次同版本PySCF直接调用对照通过。支持范围以[本轮验收报告](MOLECULAR_SINGLE_POINT_ACCEPTANCE_20261008_zh-CN.md)和[机器状态](../validation/molecular-service/deployment-20261008.json)为准。[首版验收合同](MOLECULAR_SINGLE_POINT_ACCEPTANCE_CONTRACT_zh-CN.md)列明准入、门槛和预算。

## 四步运行

### 1. 打开项目目录，确认本地工具

在 PowerShell 中进入本轮独立 runtime 目录：

```powershell
Set-Location D:\AI4Science\ai4orgchem-runtime-workspaces\user-molecule\runtime
```

需要已有 Python 3.12+、正在运行的本地 Docker 引擎，以及本轮登记的本地候选镜像。启动器兼容 Windows PowerShell 5.1 和 PowerShell 7，选择已有 Python；它不安装软件、不修改全局 WSL 配置或执行策略。

镜像身份来自 [candidate-image.json](../validation/molecular-service/candidate-image.json)。启动器使用登记的完整 image ID，并检查镜像、来源锁和依赖锁。没有该身份记录、没有镜像或身份不匹配时，应保留拒绝记录。只取得源码 Git/ZIP，不等于另一台电脑已经具备同一计算环境；本轮没有公开镜像下载地址。

### 2. 准备 XYZ 和请求文件

先使用仓库中的水分子示例 [request.json](../examples/molecular-service/water/request.json) 和 [molecule.xyz](../examples/molecular-service/water/molecule.xyz)。准备自己的分子时，将这两份文件复制到自己的输入目录，替换 XYZ 原子与坐标，再保留下面的明确计算设置：

```json
{
  "schema": "molecular-single-point-v1",
  "task": "single-point",
  "profile": "rhf-631gd-small-v1",
  "structure": {
    "file": "molecule.xyz",
    "format": "xyz",
    "unit": "angstrom"
  },
  "charge": 0,
  "multiplicity": 1,
  "method": "RHF",
  "basis": "6-31G(d)"
}
```

XYZ 第一行是原子数，第二行是注释，随后每行只有 `元素 x y z`。坐标必须为 Å；请求与 XYZ 放在同一真实目录，`structure.file` 只填写一个文件名。不得使用路径跳转、链接或 junction。原子数必须和内容一致，不接收多结构拼接文件。

本 profile 接受 **H/C/N/O、中性、单重态、偶电子、至多20个原子**。三维和非平面结构可以使用。引擎还会在进入 SCF 前检查实际 AO 数不超过80。坐标每一分量的绝对值须≤10000 Å，任意两核距离须≥0.5 Å；这是输入工程检查，不是化学几何认证。程序保留原始字节、原子顺序和坐标，不自动加氢、重排、旋转、居中或优化。

这一版固定使用 RHF/6-31G(d)。DFT、离子、开壳层、更多元素、几何优化和扫描各需独立适配及验收；不能在请求中随意改方法、基组或资源字段绕过首版支持范围。

### 3. 执行一次计算

水示例命令：

```powershell
.\scripts\start-molecular-service.ps1 -Request .\examples\molecular-service\water\request.json -OutputRoot D:\AI4Science\ai4orgchem-runtime-runs\molecular
```

执行自己的输入时，仅将 `-Request` 改为自己的 `request.json` 路径。`-Task` 默认是 `single-point`。输出根目录使用独立运行目录，避免选择科研项目、runtime 源码、输入目录或历史记录目录；启动器为每次运行创建新目录，不覆盖旧结果。

如果终端找不到 Docker，可使用本机已有可执行文件的完整路径：

```powershell
.\scripts\start-molecular-service.ps1 -Request .\examples\molecular-service\water\request.json -OutputRoot D:\AI4Science\ai4orgchem-runtime-runs\molecular -DockerExecutable 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
```

找不到合适 Python 时，在同一命令末尾增加 `-PythonExecutable '<已有Python 3.12+的完整路径>'`。本机已存在的路径是 `C:\Users\chenx\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`。启动器不要求你安装 `pwsh`，也不会替换原科研环境。

每次调用使用1 CPU、1线程、1 GiB内存；受控执行120秒上限，100秒软停止。至多执行一次 RHF kernel、最多100轮 SCF，无自动重试或方法切换。超时、内存不足或未收敛会保留实际终止状态；缺少尾部检查和最终回执时，不得按成功判读。

### 4. 打开报告，保存完整记录

终端最终 JSON 的 `records` 指向本次运行目录。先打开其中的：

- `output/calculation/report.md`：能量、收敛、数值检查与适用范围。
- `output/calculation/result.json`：原子映射、请求身份、方法、能量账本、占据和残差。
- `output/calculation/orbitals-density.npz`：原始 AO 顺序下的重叠、密度、轨道系数、轨道能级、占据及相关矩阵。

例如，将终端给出的实际路径填入 `$records`：

```powershell
$records = '<终端 records 的实际路径>'
Get-Content -LiteralPath (Join-Path $records 'output\calculation\report.md') -Encoding UTF8
```

要确认完整运行成功，还需看 `host-execution.json` 和 `output/worker-receipt.json`：最终主机状态、退出码、输入及镜像身份、资源与守卫检查、容器删除和输出保留都应闭合。数值合格状态是 `NUMERICALLY_QUALIFIED_ORDINARY_RHF`；完整 worker 验收状态是 `PASS_SCOPED_MOLECULAR_SINGLE_POINT`。单独看到能量或程序退出0，不能替代完整记录。

保存整个 `records` 目录，包括只读输入快照、合同、命令日志、操作账本、运行 manifest 和守卫回执。结果在宿主独立目录中保存，容器删除不应删除结果。

## 如何理解本版结果

总能量及轨道能级使用 Hartree；结构使用 Å。能量账本区分单电子项、库仑／交换项和核排斥项，并给出闭合残差。SCF 收敛及12项独立数值检查说明本次普通 RHF 结果的数值资格。

导出的密度是**自旋求和 AO 密度矩阵**，需要结合 AO 基函数和重叠矩阵解释。它不是已经采样的三维网格、密度等值面或实验电子密度图；本轮没有提供网格可视化和 Boys／Pipek–Mezey 局域化计算。轨道符号、顺序或简并空间表示的变化，不应单独解读为电子态变化。

HOMO／LUMO 能隙作为观察值保存，不作为旧条件态能隙门槛。本轮波函数稳定性分析为 **NOT_EXECUTED**；普通 SCF 收敛不自动证明局部极小态、全局基态或实验精度。分子间比较需先核对结构、电荷、自旋、方法、基组及单位是否适合相应研究问题。

本入口是受支持 profile 内的用户自选分子普通计算。旧条件态比较的用户 Compute 继续 **BLOCKED**。WSLc 升级及实测暂停、GitHub CI **NOT_EXECUTED**、镜像分发 **BLOCKED**；本轮不进行在线计算或公开发布。
