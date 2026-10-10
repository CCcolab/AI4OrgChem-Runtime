# 当前高成本固定体系服务

先完成[源码安装](SOURCE_INSTALLATION_zh-CN.md)。以下命令在安装器生成的同一个工作目录运行；将示例路径替换为自己的实际目录。读取 `built-image.json` 的本地标签，仅首次登记该服务时创建记录；已有记录不得覆盖。新镜像不继承历史科学验收，旧候选启动器不接收该新镜像。

```powershell
Set-Location 'D:\chem-work\runtime-install\runtime'
$installed = Get-Content ..\built-image.json -Raw | ConvertFrom-Json
python -B .\scripts\register-installation.py --service high-cost-cases --image $installed.local_tag --output-dir ..\installations\high-cost-cases
```

本家族新安装通过精确派生来源合同核对原107条基线、七份本地测试排除和允许的工程字节覆盖，安装载荷为100条；旧候选仍保留原107条路径，不机械降低来源门槛。

先查看注册状态，按任务选择账本：

```powershell
python -B .\scripts\list-high-cost-cases.py
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\high-cost-cases\installation-record.json --task P11 --mode ledger --output-root ..\runs\p11-ledger-new
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\high-cost-cases\installation-record.json --task P12 --mode ledger --output-root ..\runs\p12-ledger-new
```

P11 17态、P12 61态合计78个登记单元。只有旧镜像苯G和N12-G两个先导有数值验收，其余76态及新安装镜像的科学重放不继承 PASS。

preflight 按状态清单选择一个尚未执行的真实 Unit，使用 `--task P11` 或 `--task P12`、`--mode preflight` 和 `--unit`；不重做已通过态的资源探针。本轮不安排 preflight 或 live 实跑。

live 除同一 `--installation-record` 外，要求 `--mode live`、一个真实 `--unit`、独立 `--budget`、全新 `--output-root`。前序依赖以 `--inputs` 传入本轮合格 output 映射；P11A 按 G→GL→GE，P12 GL/GE 依赖本轮 G，N16 GE 另需本轮 GL。用 create-high-cost-budget.py 创建预算，不手写、复用或清空。单态一次，失败也计费，无重试、无恢复。

未知 create、rm、所属资源探针状态会保留隔离锁；预算保持 RESERVED，不能以一次查询无容器或尚无 ID 结算。只有确认所有所属操作闭合并释放自己的锁，才允许结算。不得手动删锁绕过未知状态。

资源、数值及依赖合同以 [冻结配置](../configs/high-cost-cases-v1.json) 和 [历史科学边界](PROTOCOL_CASES_BATCH3_zh-CN.public.md) 为准。本轮不降低内存、线程或容差。保存 host、worker、guard、资源、预算与 manifest，scratch 是保留中间文件，不冒充最终科学结果。

历史“相对 CESE 2.103137%”的分母是两类能量差加权组装项之和的绝对值；它是登记边界指标，不是相对于原著数字的百分比误差。完整组装尚未建立。L4 可以保存检查点，但不支持断点恢复。

旧 start-high-cost-case.ps1 与旧 candidate-image 仅适用于它自己的历史环境。
