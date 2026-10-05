# 本地用户分子入口：当前工程候选

2026-10-05 / W05-PREPARATION-1。入口支持 Check 和只读 Report；Compute 已接通适配器与监督，但两个 profile 均禁用计算，返回 BLOCKED / 20，等待 W05 数值/资源和 W06 研究验收。当前没有新分子能量或研究合格结果。输入合法不代表方法或资源合格。最新 [验收准备记录](USER_MOLECULE_W05_PREPARATION_zh-CN.md) 保存两份候选输入及四次实际 Check。

## 1. 从隔离工作区使用

```powershell
Set-Location D:\AI4Science\ai4orgchem-runtime-workspaces\user-molecule\runtime
$image = (Get-Content .\validation\user-molecule\candidate-image.json -Raw | ConvertFrom-Json).image_id
```

candidate-image.json 在实际构建成功后生成；不存在或没有 image_id 时不执行后续命令。不要使用旧七任务镜像代替新候选。

## 2. 准备输入

将 request.json 和它引用的 molecule.xyz 放在自己的输入目录。JSON 明确 Å、中性/单重态、xy 平面 C/H、两个碳 π 组、固定 profile 和资源限额。系统不旋转、不加氢、不重排。

examples/user-molecule/templates 中的四碳输入仅用于 AO/解析工程检查，不是化学研究推荐或科学参考。[W05 候选输入](../examples/user-molecule/w05-candidates/README_zh-CN.md) 已保存乙烯与复用上游坐标的丁二烯，均未进行 SCF、不包含 expected 能量，方法用途待审。研究夹具与具体适用范围须在 W05/W06 审阅后冻结。

## 3. 运行检查

```powershell
.\scripts\start-user-molecule.ps1 -Action Check -Image $image `
  -Request .\examples\user-molecule\templates\request.json
```

在打印出的唯一目录阅读 report.md、preflight.json 和 host-execution.json。默认输出为 D:\AI4Science\user-molecule-runs。合法检查退出 0，同时 compute_eligible=false；原因明确列出数值验收、资源模型和未冻结判据。退出 0 不代表科学计算通过。

## 4. 阅读结果或核对阻塞

```powershell
# 替换为检查实际生成的目录。
$checkRun = 'D:\AI4Science\user-molecule-runs\这里替换为实际的check目录名'
.\scripts\start-user-molecule.ps1 -Action Report -RunDirectory $checkRun

# 当前按合同拒绝计算并保留原因，预期退出 20；没有 SCF 或能量。
.\scripts\start-user-molecule.ps1 -Action Compute -Image $image `
  -Request .\examples\user-molecule\templates\request.json -CheckRun $checkRun
```

检查后输入/profile/科学来源/镜像变化须重新检查。失败记录、日志、容器实际退出码和宿主服务码分别保留；未知终态写 UNKNOWN，不用 0 补齐。取消可用 -CancelFile 指定一个信号文件，运行期间创建该文件后只停止本次容器；无需停止 vmmemWSL 或其他科研进程。

## 5. 支持边界

PowerShell 5.1 入口查找已有 PS 7.3+，不自动安装；无需宿主 PySCF。运行使用非 root、只读输入/软件、断网和有限内存/CPU/时间，实际平台证据在 validation/user-molecule 与本轮 deliveries。

pilot / STO-3G 与 research / 6-31G(d) 已完成两份候选输入的 AO/元数据 Check；research 的 d π 分类另有禁止 SCF/格点/ERI 调用的守卫实测。两个 profile 的 SCF 均未执行；资格继续 false。身份及当前范围见 [W05 准备记录](USER_MOLECULE_W05_PREPARATION_zh-CN.md)；此前镜像构建、监督与失败说明见保留的历史 [W01—W04 交付记录](USER_MOLECULE_W01_W04_DELIVERY_zh-CN.md)。

同定义独立数值参考与成熟方法解释对照尚未执行；变分性 NOT_ESTABLISHED、稳定性 NOT_EXECUTED，不宣称单键能、实验测量、普遍共轭/芳香性结论或任意分子适用。原 L4 可保存检查点但不能恢复。WSLc BLOCKED、Colab DEFERRED、镜像分发 BLOCKED；公开继续暂停。本地工程/合同 [CI 检查已通过](USER_MOLECULE_CI_20261005_zh-CN.md)，GitHub Actions 实跑仍 NOT_EXECUTED；该通过不打开 Compute。
