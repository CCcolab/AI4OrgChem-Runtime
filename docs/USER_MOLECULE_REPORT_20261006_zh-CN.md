# 等待方法决定期间：查看与导出已有记录

2026-10-06。新增功能只读取 Check、用户入口 Compute/错误、受限验收和宿主终态记录；不启动 Docker、SCF、积分或网格。两个生产 profile 的 Compute 仍禁用，MDR-001 科学定义与外部一致性意见仍待收到。已有记录的数值失败不会被改成通过。

## 1. 选择实际输出目录

在 Windows PowerShell 中进入隔离 runtime，指定自己已有的 Check 或运行目录；不要填整个验收批次父目录。

```powershell
Set-Location D:\AI4Science\ai4orgchem-runtime-workspaces\user-molecule\runtime
$run = 'D:\AI4Science\user-molecule-runs\这里替换为实际输出目录'
```

输入检查可沿用 [用户入口指南](USER_MOLECULE_RUN_zh-CN.md)。输入合法只说明工程检查通过；不表示当前能为自有分子执行科学计算。

## 2. 基础读取：无需宿主 Python 或 Docker

```powershell
.\scripts\start-user-molecule.ps1 -Action Report -RunDirectory $run
```

启动器继续使用已有 PowerShell 7.3+，Windows PowerShell 5.1 会转交并保留真实进程退出码；不安装工具或修改系统设置。基础读取核对清单登记的全部文件大小与 SHA-256，再显示宿主/源记录摘要及原缓存简报。宿主失败或 error 记录优先于旧 Check 缓存。缓存明确标为历史快照，其中旧 NOT_EXECUTED 等原因不自动成为当前项目状态。

基础模式不重新判读完整 gate 表；没有缓存时显示已保存原始状态摘要。缺清单、字节不匹配、非法路径或无可读记录返回 40。要读取完整失败判据、身份或导出，使用下面的高级模式。

## 3. 高级读取：已有标准 Python，不需要科学依赖

使用本机已有 Python 3.12+ 的实际可执行文件路径。本轮实测 Python 3.12.14；Report 仅使用标准库，不安装或导入 PySCF、NumPy、SciPy，不要求激活原项目环境。

```powershell
$python = 'C:\这里替换为已有Python目录\python.exe'
.\scripts\start-user-molecule.ps1 -Action Report -RunDirectory $run -PythonExecutable $python
```

也可直接调用只读入口：

```powershell
& $python -B .\scripts\report-user-molecule.py report --run-directory $run
```

这个专用脚本拒绝 Check/Compute；通用模块的原 Check/Compute CLI 保留原合同。中文与 Å 输出按 UTF-8，避免 Windows 默认编码把有效报告变成编码错误。

高级报告区分检查完成/科学未执行、已执行但数值失败、BLOCKED、宿主超时/取消/收集失败及记录不完整。简报显示原退出码及其来源；导出的 `report-summary.json` 分列宿主服务码、容器码和可用的宿主进程码。报告区分镜像构建 runtime 与数值测试 runtime；缺少构建身份就显示 UNKNOWN，不把 `c8a580f` 测试提交当镜像构建提交。

## 4. 导出到一个新的目录

```powershell
$export = 'D:\AI4Science\user-molecule-reports\这里填写新的目录名'
.\scripts\start-user-molecule.ps1 -Action Report -RunDirectory $run `
  -PythonExecutable $python -ReportExportDirectory $export
```

导出 `report.md`、`report-summary.json` 和 `run-manifest.json`，记录源文件哈希、报告代码哈希、原退出码及本次报告退出码。目录必须不存在且在源运行目录之外；已有导出或原记录不覆盖。科学进程计数为 0。

## 5. 怎样判读

下表的完整性状态以高级模式为准。基础模式返回 0 只表示已登记文件字节核对与缓存读取成功；它不检查规范请求等关键快照是否应存在。同一不完整记录可能基础返回 0、高级返回 40，应使用高级模式确认关键证据和身份完整性。

| 显示/退出 | 含义 |
|---|---|
| Report 退出 0 | 读取已完整登记的记录成功；可以同时显示科学 FAIL 或宿主失败，不是科学验收 PASS |
| 退出 40、UNVERIFIED | 关键快照/清单/文件缺失或未登记；可生成明确标注的不完整诊断，不能提升比较资格 |
| 退出 40、字节/身份/路径/JSON 错误 | 拒绝重新出具有效报告；保留原目录，核对来源或取回完整副本 |
| 检查完成、Compute 记录资格 false | 合法检查仍没有计算资格；旧理由仅表示当时快照 |
| 已执行、NOT_QUALIFIED、delta=null | 保留条件态或参考失败；能量、残差、gap 仅是保存的失败诊断，不用于研究结论 |
| 宿主 BLOCKED、comparison_available=false、delta=null | 保留原码和旧数值标签，不能沿用旧结果中的可用差值 |
| 请求快照“本次未生成” | 早期输入解析错误可能没有合法规范请求；完整登记的 error/progress 仍可读取成功，与成功检查丢失关键快照不同 |

本地 manifest 与文件相符只证明本地字节一致，不证明记录创建者、来源权威、计算正确性或方法批准。Report 不重算矩阵，不复验 T04/T05/T06/P12/P13；显示它们原来登记的失败及状态，并保留旧 `molecular_acceptance=NOT_EXECUTED`、`COMPARABLE_CANDIDATE` 等原始标签供查阅，不能靠这些标签获得资格。

## 6. 本轮实际验证与限制

最终受测代码提交 `ed4a7718e814aaef1f7329555897f0cf0c0455a6`：48 项标准库用例、11 项主机 Report 集成通过，科学依赖导入被禁止。此前 `472714a` 的47项/9项记录作为历史保留。独立代码复核发现的宿主 BLOCKED 仍沿用旧可用差值问题已修复，增加合成记录回归并通过实际 Report CLI 核验。启动器原16个退出码/参数样本与后来2个新参数样本分别保留；宿主收集失败用受控引擎替身模拟，不能写成真实 Docker 验收。旧 Check 与 v2 失败记录只读回验，原文件大小/哈希不变。

初次集成对一个缺规范请求的模拟宿主记录错误期待退出0，实际被拒绝为40/UNVERIFIED。该失败日志保留；核查缺项后，用新的完整模拟副本验证读取成功，未降低完整性检查或科学门槛。

新功能位于当前主机源码，不重建 r3 镜像，容器内原入口仍对应旧构建身份。原科学核、占据、profile、验收容差和 [MDR-001](USER_MOLECULE_METHOD_DECISIONS_001_zh-CN.md) 未变；Compute/W07 BLOCKED，WSLc 暂停，远端 CI NOT_EXECUTED，镜像分发 BLOCKED，未公开推送。P01—P14 不自动重审；L4 保存检查点但不支持恢复。

机器记录见 [本轮工程核验](../validation/user-molecule/report-engineering-20261006.json)。此记录不替代历史科学验收或真实方法批准。
