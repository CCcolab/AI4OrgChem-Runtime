# 当前专题协议使用指南

先完成[源码安装](SOURCE_INSTALLATION_zh-CN.md)。以下命令在安装器生成的同一个工作目录运行；将示例路径替换为自己的实际目录。读取 `built-image.json` 的本地标签，仅首次登记该服务时创建记录；已有记录不得覆盖。新镜像不继承历史科学验收，旧候选启动器不接收该新镜像。

```powershell
Set-Location 'D:\chem-work\runtime-install\runtime'
$installed = Get-Content ..\built-image.json -Raw | ConvertFrom-Json
python -B .\scripts\register-installation.py --service protocol-cases --image $installed.local_tag --output-dir ..\installations\protocol-cases
```

选择固定 P03—P10 协议对象。所有输入、方法、比较量及结果字段见 [当前专业矩阵](CURRENT_PROFESSIONAL_SERVICES_zh-CN.md)，原协议及实际运行身份见 [历史专题材料](PROTOCOL_CASES_BATCH2_zh-CN.public.md)。

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P07 --mode ledger --output-root ..\runs\p07-ledger-new
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P03 --mode preflight --output-root ..\runs\p03-preflight-new
```

ledger/preflight 均要求匹配镜像、来源、资源及输出目录；不授予收敛或科学资格。P07 不支持 live。其他七个 live 任务各一次、需独立新批次预算，未知创建／清理必须保留 RESERVED 与隔离锁，不自动重试或解锁。

以下只是尚未执行对象的参数形式，须先按历史协议材料准备本轮预算，不能覆盖或重用旧预算；已有通过记录不安排重跑：

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P03 --mode live --budget D:\chem-work\batch-budget-new.json --output-root ..\runs\p03-live-new
```

资源：ledger/preflight 1 CPU/线程、1 GiB、120 秒；live 2 CPU/线程、4 GiB、900 秒硬限、840 秒软停，无额外 swap。保存 `output/case-result.json`、`guard-receipt.json`、资源记录、host-execution 和整目录 manifest。固定协议结果不等于独立引擎认证。

旧 start-protocol-case.ps1 只用于原候选环境，不是本页新安装入口。
