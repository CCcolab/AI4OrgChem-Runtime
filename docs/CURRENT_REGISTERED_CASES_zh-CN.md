# 当前固定案例：统计、图账本、轨道密度

先完成[源码安装](SOURCE_INSTALLATION_zh-CN.md)。以下命令在安装器生成的同一个工作目录运行；将示例路径替换为自己的实际目录。读取 `built-image.json` 的本地标签，仅首次登记该服务时创建记录；已有记录不得覆盖。新镜像不继承历史科学验收，旧候选启动器不接收该新镜像。

```powershell
Set-Location 'D:\chem-work\runtime-install\runtime'
$installed = Get-Content ..\built-image.json -Raw | ConvertFrom-Json
python -B .\scripts\register-installation.py --service registered-cases --image $installed.local_tag --output-dir ..\installations\registered-cases
```

按研究目的选择一个固定任务；不是任意分子入口，不接受用户 request，也不更改分片、几何、基组或容差。

| 模块 | 真实 task | 科学调用范围 |
| --- | --- | --- |
| 结构与光谱表值统计 | p02-statistics | 固定表值拟合，零 SCF |
| 共轭图规则与能量账本 | p13-graph-ledger | 固定图/RDKit及保存账本，零新 QM |
| 轨道表示与密度对照 | p01-orbital-density | 固定乙烯 RHF、Boys、PM 各一次；需实际计算授权 |

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\registered-cases\installation-record.json --task p02-statistics --output-root ..\runs\p02-statistics-new
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\registered-cases\installation-record.json --task p13-graph-ledger --output-root ..\runs\p13-graph-ledger-new
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\registered-cases\installation-record.json --task p01-orbital-density --output-root ..\runs\p01-orbital-density-new
```

以上是可选操作说明，本轮没有执行。1 CPU/线程、1 GiB、120 秒硬限。保存终端 records 中的 `output/case/case-report.md`、`case-result.json` 及完整回执。执行、数值资格、比较量及科学解释分别判读。

历史旧镜像和旧 start-registered-case.ps1 操作见 [历史固定案例指南](REGISTERED_CASES_zh-CN.md)；不把新安装镜像交给它。
