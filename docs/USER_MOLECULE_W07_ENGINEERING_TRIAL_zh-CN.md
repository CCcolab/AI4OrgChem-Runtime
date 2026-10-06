# W07 工程试用：检查、读报告、导出与未来可选反馈

2026-10-06 / W07-ENGINEERING-PREPARATION-1，当前试用安排按用户要求修订。既有实际演示源码基线为 `e03e3371709df917b718bf50cbe62d5363efecdb`；既有 Check、基础 Report、高级 Report、fresh 外部导出四步原进程均退出 0，完成 **PASS_SCOPED_ENGINEERING_CHECK_REPORT_EXPORT_DEMONSTRATION**。操作人为工程人员，使用登记乙烯夹具；该历史演示及其原回执保留。自有分子真人试用与真实专业用户独立操作反馈现为 **DEFERRED_BY_USER**，不作为当前 W07 工程验收阻塞，也不是本轮欠账。这份指南保留 A14 类操作与判读步骤，反馈模板供未来可选使用；正式 W07 科研用户验收和两个生产 profile 的 Compute 仍 **BLOCKED**。W05/W06 已执行的数值失败、不可用比较及方法待审状态继续保留。

用户明确授权本轮由代理模拟真实场景进行工程路径自测，现阶段无需真人试用或反馈。预期覆盖多分子与两个 profile 的 Check、无效输入拒绝、宿主路径校验、Compute 资格及旧回执拒绝、Report 保护；这些目标已由本轮实际回执验证；通过范围仅为已执行工程场景，具体未知和未执行项保留。实际动作、退出码、容器数及证据由 [模拟自测机器记录](../validation/user-molecule/w07-simulated-selftest-20261006.json) 和 [自测报告](USER_MOLECULE_W07_SELFTEST_zh-CN.md) 按真实回执登记。代理模拟工程路径不等于真人体验，也不构成科学或科研验收；不能代填真实使用者意见。

## 1. 确认输入并选择请求

自有输入须由使用者先确认：固定几何、中性闭壳层 C/H、`coordinate_unit=angstrom`、`charge=0`、`multiplicity=1`，已在 xy 平面。XYZ 原子编号从原子行的 1 开始；逐个确认 A/B 的碳编号，每个碳恰好归入一组，两组均非空，不分配氢，不自动识别化学片段。入口不旋转、不重排、不加氢；不满足范围时先停止并记录问题。

将已有 XYZ 与请求放在自己的输入目录；`geometry_file` 必须是该目录内的相对文件路径。可复制 [现有请求模板](../examples/user-molecule/templates/request.json)，手动填写研究问题和 A/B 编号，保留登记的 condition/profile 与资源字段。`condition_definition_acknowledged` 表示理解：A/B 是两组碳 π 归属，条件态按登记规则屏蔽跨组 π 项，并非清零所有跨组作用；该确认不表示方法批准。详细方法可选查阅 [条件定义](USER_MOLECULE_CONDITION_DEFINITION_zh-CN.md)。若使用本轮准备目录，选择其中实际存在且已核对的请求；目录占位或模板中旧编号不代表自有输入已经确认。

默认工程演示使用已核对的乙烯夹具：

```powershell
Set-Location D:\AI4Science\ai4orgchem-runtime-workspaces\user-molecule\runtime
$request = '.\examples\user-molecule\w05-candidates\ethene-planar-technical-v1\request-pilot.json'
# 自有输入准备完成后，将上行改为自己的 request.json 实际路径。
$image = (Get-Content .\validation\user-molecule\candidate-image.json -Raw | ConvertFrom-Json).image_id
```

该请求引用同目录 `molecule.xyz`：6 个原子，A=`[1]`、B=`[2]`；pilot profile 为 `pilot-b3lypg-sto3g-grid2-v1`，限额为 1 线程 / 512 MiB / 60 秒。它是参数构造的解析几何，无 expected 科研能量，不代替自有分子。

使用已有 PowerShell 7.3+ 和已存在的 Docker 候选镜像。启动器可从 Windows PowerShell 5.1 转交至已有 PS 7；本流程不安装工具。`candidate-image.json` 缺失、`image_id` 为空或本地镜像不可用时，在实际操作记录中记下问题并停止 Check，不改用旧七任务镜像。

## 2. 运行现有 Check，记录实际回执

本轮首次 Docker Desktop 启动失败：2026-10-06T06:26:25Z 的 backend 日志记录 Inference manager 初始化 `dockerInference` listener 时发生文件访问/路径语法错误，backend 退出，Linux pipe 不可用；失败原日志保留。获准后核验相关进程为 0、两个临时目录仅含 4 个零字节 reparse socket，改名保留原目录并重建空目录，恢复既有 Engine 29.5.3 / Desktop 4.78.0。恢复未删除文件、修改全局配置、重启/停止 WSL 或重建镜像；最终 Check 创建 1 个容器，完成后已删除，输出保留。

```powershell
.\scripts\start-user-molecule.ps1 -Action Check -Image $image -Request $request
$checkExit = $LASTEXITCODE
```

从最后的 `records:` 行复制本次唯一输出目录；默认父目录为 `D:\AI4Science\user-molecule-runs`。核对 `preflight.json` 的输入、原子映射、A/B、profile 和 `compute_eligible`，并保留 `host-execution.json`、`run-manifest.json`、日志及 `report.md`。输入或分组有误时，修订自己的请求并重新 Check，不修改旧回执。

Check 会在既有候选容器中导入 PySCF 并创建 Molecule，进行输入/AO 元数据与资格检查；不执行 Compute、SCF、格点或完整 ERI。既有演示实际输入为 `VALID`、`compute_eligible=false`，宿主服务码与容器码均为 0；inspection 的 `scf_executed`、`grid_built`、`full_eri_allocated` 均为 false。实际操作时填写真实退出码，不用既有演示码代填；退出非 0 时保留宿主服务码、容器码及原因，未知填 UNKNOWN。

## 3. 读报告，导出到新目录，未来可选填写反馈

将 `$run` 替换为自己的实际单次 Check 目录；也可选择已有 Check 或 v2 失败记录的实际单次目录，填写来源，分别导出到全新目录。不能选整个验收批次父目录。本轮最终四步演示使用新 Check 的留存目录，真实使用者应另存自己的操作记录。

```powershell
$run = 'D:\AI4Science\user-molecule-runs\这里替换为实际单次目录'
.\scripts\start-user-molecule.ps1 -Action Report -RunDirectory $run
$basicReportExit = $LASTEXITCODE

# 替换为本机已有 Python 3.12+ 可执行文件，不安装科学依赖。
$python = 'C:\这里替换为已有Python目录\python.exe'
.\scripts\start-user-molecule.ps1 -Action Report -RunDirectory $run -PythonExecutable $python
$advancedReportExit = $LASTEXITCODE

# 该目录必须不存在，并位于源运行目录之外。
$export = 'D:\AI4Science\user-molecule-reports\这里填写全新目录名'
.\scripts\start-user-molecule.ps1 -Action Report -RunDirectory $run `
  -PythonExecutable $python -ReportExportDirectory $export
$exportExit = $LASTEXITCODE
```

高级模式复用现有 `report-user-molecule.py`，仅使用标准库，不启动 Docker 或科学计算；如需直接调用：`& $python -B .\scripts\report-user-molecule.py report --run-directory $run --export-directory $export`。两种方式任选其一，避免对同一导出目录重复执行。没有已有 Python 时先记录高级读取/导出未执行，仍可完成基础读取；未来真人试用时可选填写反馈。

高级导出包含 `report.md`、`report-summary.json`、`run-manifest.json`。未来恢复真人试用时，可按 [反馈模板](templates/USER_MOLECULE_W07_FEEDBACK_zh-CN.md) 填写各步实际退出码、可用性、问题、输入确认和报告原状态；本轮不要求填写该模板，代理自测事实记录在独立机器记录与自测报告中。JSON 的 `host_service_exit_code`、`container_exit_code`、`host_exit_code` 分列，不以其中一个补齐另一个；同时保留 `original_exit_code_source`。没有证据时保留 null/UNKNOWN，未执行写 NOT_EXECUTED。

既有演示留存位置仅供读取；其中 `exported-report` 已存在，不能作为下次 fresh 导出目标：

```powershell
$trial = 'D:\AI4Science\ai4orgchem-runtime-deliveries\20261006-user-molecule-w07-engineering-trial\attempt-2'
$run = Join-Path $trial 'check-runs\check-20261006T064214Z-9ade4bb9a87c4917aa5f964f23a9dfdf'
$completedExport = Join-Path $trial 'exported-report'
# 原始执行记录：Join-Path $trial 'TRIAL_EXECUTION.json'
```

| 阅读结果 | 本次应如何理解 |
|---|---|
| 基础 Report 退出 0 | 清单登记的字节核对及缓存读取成功；没有检查关键请求等快照是否应存在 |
| 高级 Report 退出 0 | 本地记录读取成功；不构成 `sciencePass`、数值或方法批准，可同时报告原科学失败 |
| 高级 Report 退出 40 / UNVERIFIED | 关键证据缺失或不完整；保留诊断与旧目录，不提升资格 |
| `comparison_available=false` | `delta_hartree`、`delta_kcal_mol` 保持 null；失败诊断能量或旧状态标签不能补成可用比较 |

完整说明见 [Report 指南](USER_MOLECULE_REPORT_20261006_zh-CN.md) 与 [Run 指南](USER_MOLECULE_RUN_zh-CN.md)。未来可选反馈由实际使用者填写；本指南和准备材料不代填真实用户意见，不自动发送或上传。真人反馈的延期不阻塞本轮代理模拟工程路径验收。

## 交付范围（按需查阅）

本轮工程交付目录为 `D:\AI4Science\ai4orgchem-runtime-deliveries\20261006-user-molecule-w07-delivery`。两个已有样例搬移后的只读 Report、旧 `9e1c1b9` Git 源码重建及两例 Report 已有通过回执；见 [W07 交付登记](../validation/user-molecule/w07-delivery-20261006.json) 和目录中的 `PORTABLE_SAMPLE_VERIFICATION.json`、`RUNTIME_SOURCE_RESTORE_PROBE.json`。最终新增文档候选的 Git bundle、源码归档身份及校验以该目录外部 `FINAL_DELIVERY.json` 为准；旧提交恢复检查未包含本轮新版 NOTICE，不构成完整环境恢复或正式 W07 科研验收。

| 新服务操作 / 平台 | 当前范围与证据 |
|---|---|
| Check：Windows PowerShell 5.1 引导至已有 7.3+，本地 Docker Linux/amd64 r3 | 既有乙烯演示及本轮乙烯/丁二烯×两个 profile 的 Check 工程自测通过；输入 VALID、Compute 资格 false，无 SCF/网格/完整 ERI。限于登记输入、镜像与限额，不证明任意自有分子可算 |
| 基础 Report：已有 PowerShell 7.3+ | 宿主清单字节核对和缓存读取；无需 Docker 或宿主 Python，返回 0 不补证关键快照完整性 |
| 高级 Report / fresh 导出：已有 Python 3.12+ | 宿主标准库只读工具；本轮两个已有样例搬移后读取/导出均退出 0，旧 `9e1c1b9` Git 重建源码读取两例也均退出 0。仅证明已登记记录可读，不启动科学计算 |
| Compute：pilot / research 两个生产 profile | BLOCKED；开关仍禁用，W05/W06 实际数值失败、资源和范围门禁未关闭 |
| WSLc / Colab / GitHub Actions | BLOCKED 且暂停 / DEFERRED / NOT_EXECUTED；本地工程 CI 与宿主 Report 不补写这些平台通过 |
| 原七任务 L0—L4、等价性与分类 | 属于 legacy 镜像及固定协议历史证据，见 [原平台矩阵](WSLC_COMPATIBILITY_zh-CN.md)；其 PASS 不转移给新服务或 r3，原 L4 仍不可 resume |

| 来源与许可对象 | 登记与限制 |
|---|---|
| 当前宿主 runtime 源码、LICENSE / NOTICE | 自有代码 Apache-2.0；交付提交、工作字节与 Git 身份逐项登记。宿主通知的范围修订须随源码保存；未重建的 r3 不因此携带新版通知 |
| 科学适配源码 | [来源锁](../locks/source.user-molecule.lock.json) 登记 `cc7437901119e71ef7945a12813c021c383e7648`，基于 `28511f3d84fa65707a107cde1e8121a7b4334ecb`；588 个基线文件未变，新增适配器、测试、说明 3 文件，非已发布 v0.3.2 身份。保留上游 LICENSE / NOTICE / AUTHORS |
| r3 镜像与宿主源码 | [候选身份](../validation/user-molecule/candidate-image.json) 为镜像 `24f46f…`、runtime 构建 `5098775…`、science `cc743…`；宿主当前提交和数值测试提交分列，缺失身份仍 UNKNOWN |
| 基础镜像与依赖 | r3 复用登记的固定基础摘要和依赖锁；同基础、同锁不能证明与 legacy 镜像逐组件相同。以 [base-image.lock.json](../locks/base-image.lock.json)、[wheels.lock.json](../locks/wheels.lock.json) 和构建回执核对来源，不新增或浮动升级依赖 |
| 第三方许可审查与分发 | [原许可审查](LICENSE_REVIEW_zh-CN.md) 对象为旧 `ddc45b1…`；其材料只作来源关联。r3 完整逐组件 audit 为 NOT_EXECUTED，精确原生来源、通知和源码交付未闭合，镜像分发继续 BLOCKED；自有 Apache-2.0 不覆盖全部镜像组件 |

| 候选备份范围 | 包含 / 排除与可验证边界 |
|---|---|
| 当前 runtime | 保存范围为完整已跟踪源码快照与完整可用 Git 历史 bundle，含当前文档、Report 工具、来源锁、profile、LICENSE / 新版 NOTICE；最终新增文档候选的身份和归档校验由外部 `FINAL_DELIVERY.json` 登记 |
| 已有科学源码 | 已复用既存 `science.tar` 完整源码和 `science-adapter-w01-w04.bundle`；归档提取到新目录并匹配锁中 591 文件。科学增量 bundle 必须先具备 `28511f3…` 基线，不能单独声称包含完整 Git 历史 |
| 两个真实样例 | 已原样复制上一轮完整单次 Check 和既有 `numerical-a1/pilot-ethene` v2 失败目录至 `local-candidate/samples`；源字节未变，搬移后只读 Report 读取/导出均通过。失败样例仍 NOT_QUALIFIED，两例 delta 均 null、比较 false，无新科学样例 |
| 静态与 Git 恢复检查 | 已从旧 `9e1c1b9` runtime bundle 重建源码并读取两例，原默认 HEAD 未检出的错误保留，显式 checkout 后通过；该测试恢复旧 NOTICE。新候选 bundle/归档字节检验单独登记，不能移用旧恢复回执 |
| 镜像、依赖与环境 | 排除镜像导出、私有输入、全部历史运行及新增依赖归档。新增镜像导出与完整 Docker / Python / WSL 环境恢复 NOT_EXECUTED；候选 ZIP 供本地源码和证据审阅，不是独立安装器 |
| 存储与发布 | 本地同盘候选快照；独立介质容灾复制未执行。打包不授权镜像分发、源码公开、推送、正式标签或 Release |

恢复 runtime bundle 时显式指定分支：`git clone --branch implementation/user-molecule-w01-w04 <完整runtime-bundle路径> <全新恢复目录>`；默认 HEAD 不能作为可检出保证。克隆后核对交付清单登记的完整提交及文件身份，再只读 Report；新候选的源码/NOTICE 身份以新清单为准。

自有分子真人试用所需的 XYZ 与 A/B 确认、真实专业用户独立操作及反馈为 DEFERRED_BY_USER；恢复真人试用后仍须由真实使用者确认自己的输入，当前不作为 W07 工程验收阻塞，也不是本轮欠账。代理及工程人员只记录工程事实，不代填使用者意见。方法四问咨询按用户要求 DEFERRED，MDR-001 尚未批准；正式 W07 科研交付、两个合格研究体系和生产 Compute 继续 BLOCKED。

## 既有工程演示回执与保留边界

| 既有工程演示项目 | 原回执与当前边界 |
|---|---|
| Check / 基础 Report / 高级 Report / fresh 外部导出 | 前轮工程人员演示 PASS，四步原进程退出码均为 0，1 个 Check 容器已删除、输出保留；既有交付记录中的新增容器为 0，不能代替本轮模拟自测的实际容器记录 |
| 前轮 Check 高级报告 | `record_integrity=MATCHED`；科学与数值状态均为 `NOT_EXECUTED`，方法与研究状态均为 `NOT_REVIEWED` |
| 前轮 Check 比较与身份 | `comparison_available=false`，`delta_hartree=null`、`delta_kcal_mol=null`；未登记 `runtime_test_commit`，显示 UNKNOWN |
| 自有分子真人试用所需 XYZ 与 A/B 确认、真实用户独立操作反馈 | DEFERRED_BY_USER；未来可选，不作为当前 W07 工程验收阻塞或本轮欠账。默认乙烯演示和代理模拟自测均不满足真人体验或真实用户验收 |
| 本轮代理模拟工程路径自测 | 用户已授权；预期覆盖与实际回执分别记录在模拟自测机器记录及报告中，已按实际回执通过所列工程场景；不提升科学或科研资格 |
| 方法四问咨询 | DEFERRED；材料齐全后再征询，MDR-001 尚未真实审阅批准 |
| 正式 W07 与 Compute | BLOCKED；本轮两次 Compute CLI 仅测资格/身份拒绝，科学 Compute/SCF/网格/完整 ERI 为0，不改变 profile 开关 |

机器证据见 [既有工程试用记录](../validation/user-molecule/w07-engineering-trial-20261006.json)，原始四步命令、退出码与源文件字节留存在上列 `TRIAL_EXECUTION.json`；本轮样例搬移和源码恢复证据另见上节交付登记。既有 r3 镜像未重建，镜像构建身份与宿主/数值测试身份分别记录。旧 r3 缓存中的 `W05_NUMERICAL_ACCEPTANCE_NOT_EXECUTED` 等原因与 UNKNOWN 仅描述该记录登记的信息；当前 W05/W06 真数值失败按最新验收记录保留，不能由旧缓存改写。当前 WSLc BLOCKED/暂停、远端 CI NOT_EXECUTED、Colab DEFERRED、镜像分发 BLOCKED、公开/推送/正式发布继续暂停，均为项目边界，不能从旧缓存原因推断或更新。原 L4 可保存检查点，但不可 resume。工程操作记录齐全也不能关闭这些边界或完整科研用户验收。
