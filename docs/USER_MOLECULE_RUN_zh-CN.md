# 本地用户分子入口：当前工程候选

准备自己的输入、执行 Check、读取和导出报告，从 [W07 三步工程试用](USER_MOLECULE_W07_ENGINEERING_TRIAL_zh-CN.md) 开始；不要求先阅读全部实施文档。当前提供输入/报告操作，Compute 与正式科研验收仍关闭。

2026-10-05 / W05-W06-NUMERICAL-EVIDENCE-1。入口支持 Check 和只读 Report；两个生产 profile 均禁用 Compute，返回 BLOCKED / 20。本轮受限验收已有新分子诊断能量，但条件态/等价性/完整参考未通过，没有研究合格结果。输入合法不代表方法或资源合格。最新 [数值验收记录](USER_MOLECULE_W05_W06_NUMERICAL_REVIEW_zh-CN.md) 说明失败与资源实测范围；它不开放用户计算。

后续 [求解器 v2](USER_MOLECULE_SOLVER_V2_zh-CN.md) 已通过 122 项工程测试并在乙烯 pilot 拒绝假停止；唯一新分子诊断仍失败。两条同密度路径已在该夹具通过，完整迭代与资源推广资格尚未闭合，用户 Compute 状态不变。

[W06 工程增补](USER_MOLECULE_W06_ENGINEERING_zh-CN.md) 已实现参考/资格判读与短简报候选，测试源码可只读挂载复用旧镜像；现有 r3 的生产启动入口不因此升级，仍使用原报告且禁用 Compute。不得将本轮 toy 测试当作用户分子数值验收。

## 1. 从隔离工作区使用

```powershell
Set-Location D:\AI4Science\ai4orgchem-runtime-workspaces\user-molecule\runtime
$image = (Get-Content .\validation\user-molecule\candidate-image.json -Raw | ConvertFrom-Json).image_id
```

candidate-image.json 在实际构建成功后生成；不存在或没有 image_id 时不执行后续命令。不要使用旧七任务镜像代替新候选。

## 2. 准备输入

将 request.json 和它引用的 molecule.xyz 放在自己的输入目录。JSON 明确 Å、中性/单重态、xy 平面 C/H、两个碳 π 组、固定 profile 和资源限额。系统不旋转、不加氢、不重排。

examples/user-molecule/templates 中的四碳输入仅用于 AO/解析工程检查，不是化学研究推荐或科学参考。[W05 候选输入](../examples/user-molecule/w05-candidates/README_zh-CN.md) 的乙烯与丁二烯已用于所列受限验收，新乙炔是解析数学夹具；诊断失败不生成 expected 科研能量，方法用途仍待审。不要把三种夹具自动当成适用研究模板。

## 3. 运行检查

```powershell
.\scripts\start-user-molecule.ps1 -Action Check -Image $image `
  -Request .\examples\user-molecule\templates\request.json
```

在打印出的唯一目录阅读 report.md、preflight.json 和 host-execution.json。默认输出为 D:\AI4Science\user-molecule-runs。合法检查退出 0，同时 compute_eligible=false；原因明确列出数值验收、资源模型和未冻结判据。退出 0 不代表科学计算通过。

## 4. 阅读结果或核对阻塞

2026-10-06 已新增 [主机只读 Report 与导出](USER_MOLECULE_REPORT_20261006_zh-CN.md)：基础模式不用宿主 Python 或 Docker，校验清单后读历史缓存/终态；高级模式用已有标准 Python 读取门禁、失败、身份与缺失，并只导出到新的目录。读取退出0不代表科学通过。容器 r3 没有重建，科学 Compute 仍关闭。

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

pilot / STO-3G 与 research / 6-31G(d) 的普通态及小夹具条件 SCF 已在验收驱动中执行，最终数值资格未通过，生产资格继续 false。原生峰值仅覆盖精确顺序验收流程，通用资源模型仍未校准。身份及当前范围见 [数值验收记录](USER_MOLECULE_W05_W06_NUMERICAL_REVIEW_zh-CN.md)；此前镜像构建与监督见历史 [W01—W04 交付记录](USER_MOLECULE_W01_W04_DELIVERY_zh-CN.md)。

同定义独立数值参考已执行但完整条件比较失败；成熟方法外部计算仍未执行，真实方法审阅待办。变分性 NOT_ESTABLISHED、稳定性 NOT_EXECUTED，不宣称单键能、实验测量、普遍共轭/芳香性结论或任意分子适用。原 L4 可保存检查点但不能恢复。WSLc BLOCKED、Colab DEFERRED、镜像分发 BLOCKED；公开继续暂停。工程测试通过不打开 Compute；GitHub Actions 实跑仍 NOT_EXECUTED。
