# 自己的分子：当前普通 RHF 使用指南

先完成[源码安装](SOURCE_INSTALLATION_zh-CN.md)。以下命令在安装器生成的同一个工作目录运行；将示例路径替换为自己的实际目录。读取 `built-image.json` 的本地标签，仅首次登记该服务时创建记录；已有记录不得覆盖。新镜像不继承历史科学验收，旧候选启动器不接收该新镜像。

```powershell
Set-Location 'D:\chem-work\runtime-install\runtime'
$installed = Get-Content ..\built-image.json -Raw | ConvertFrom-Json
python -B .\scripts\register-installation.py --service molecular-service --image $installed.local_tag --output-dir ..\installations\molecular-service
```

1. 把 XYZ 和请求 JSON 放在同一目录；结构单位为 Å，`structure.file` 是请求目录内的 XYZ basename。可从 `examples/molecular-service/water/` 复制模板。
2. 明确采用中性闭壳层单重态 RHF/6-31G(d) 模型；H/C/N/O、≤20 原子、实际 AO≤80。偶电子与单重态声明不能证明真实分子适合闭壳层单行列式。
3. 使用这份安装记录运行；输出必须是全新外部目录。

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\molecular-service\installation-record.json --task single-point --request .\examples\molecular-service\water\request.json --output-root ..\runs\water-new
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\molecular-service\installation-record.json --task single-point --request D:\chem-work\my-molecule\request.json --output-root ..\runs\my-molecule-new
```

两条命令是二选一示例，不会由文档自动执行。资源为一 CPU/线程、1 GiB、120 秒硬限，最多一次 RHF kernel，无重试或恢复。

读取终端返回的 records 目录：`output/calculation/report.md`、`result.json`、`orbitals-density.npz` 和完整 host/worker/guard/资源回执，整目录保留。账本与残差位于 `result.json` 的 `diagnostics.energy_ledger`、`diagnostics.orbital_summary`、`diagnostics.checks`、`diagnostics.residuals`。

首版数值门禁仅限定指定几何 RHF 的已登记检查。所有 canonical 轨道，尤其虚空间，不因现有布尔值通过而取得全空间资格；全 MO 本征残差只是诊断。新宿主回执的 `evidence_review.qualification_scope` 与 `evidence_review.orbital_export_qualification` 明确该限制。全轨道正交／本征门禁的新版本尚未实现；稳定性与物理基态认证未执行。原四分子结果及12项门禁不改写。

历史候选环境的操作与身份见 [历史普通服务节选](MOLECULAR_SINGLE_POINT_zh-CN.public.md)，只适用于其原候选镜像。当前安装不要使用其中的 start-molecular-service.ps1。
