# v0.1.0发布后同步状态说明
指南中的当前同步卡已补齐正式Release、作者、引用及GitHub自动统计说明；本次正文修订与实际导出身份见validation/web-guide/postrelease-status-card-20261010.json。已发布v0.1.0标签及附件不替换；原发布包记录仍绑定其当时字节。

# v0.1.0发布链接与指南身份
当前源码与指南版本为v0.1.0，Release入口https://github.com/CCcolab/AI4OrgChem-Runtime/releases/tag/v0.1.0 。本次实际导出身份见validation/web-guide/release-v0.1.0-downloads.json；原浏览器补验PASS是外部审阅者经负责人报告，对应此前固定字节，见validation/web-guide/external-browser-retest-20261010.json。旧记录保持原身份。源码ZIP用于安装，指南ZIP不含计算引擎。

# 历史维护说明与本地实测范围
以下原始维护登记中“当时”“原次”指YouMind提供材料时的状态；保留原失败与未执行清单，不把它们当作当前包外实测结论。本次修订网页及实际按钮产物登记于 Runtime validation/web-guide/special-review-followup-20261010.json；此前 full-review-repairs-20261010.json、online-browser-followup-fa7b4ee-20261010.json 和 export-compatibility-round2-20261010.json 均仅对应各自旧字节，逐项核对对应对象；记录缺少、未执行或哈希不匹配时标未知，不自动继承 PASS。final-consistency-r2-20261009.json 仅为历史网页身份，不绑定本版 HTML 或浏览器 ZIP。本页手工QA初始未填写与包外实测是两种记录。真实200%缩放、完整键盘和多浏览器仍NOT_EXECUTED，不宣称完整网页认证；网页和CI均不授予新增科学资格。



## 原轮具体修正
固定Runtime参数为p02-statistics、p13-graph-ledger、p01-orbital-density；case-前缀仅用于DOM id。P13冻结量为ESE／CESE。水execution为a95e7d0f4cb74b9585f1528b19162972。普通服务使用molecular-service/candidate-image，3项固定服务使用registered-cases/candidate-image；两者均需Python3.12+、PowerShell 5.1或7及匹配Docker环境，不要求pwsh。普通路径不要求旧r3或PS7.3；旧Check／Report与旧P14条件仅在对应专项折叠展开后显示并参与可见条件计数。学习路径新增3项固定服务清单。诊断明确属于旧条件态。旧14卡、7任务命令、10成员ZIP及QA保留。


## 当时内容修订（下一批ZIP／QA）
普通RHF 限定范围内本地可用；只有legacy条件态任意用户分子的旧条件态比较 Compute BLOCKED。自选分子的普通DFT尚未开放，部分固定协议已有受限RKS/GL/条件核，新入口PS5.1无需pwsh；无公开镜像，无WSL reset，无AO改基组retry，无resume。网页不上传、不执行。14 evidence／7 historical／3 fixed／1 ordinary分别计数，旧14卡与7任务原命令及矩阵完整保留。结果先读output/calculation/report.md，保存全部records；12 checks全真仅数值资格，worker 限定范围内 PASS与host退出资源清理独立，未知非0／PASS，退出0非完整。NPZ非grid，canonical非化学分类，收敛非基态，稳定性NOT_EXECUTED。同PySCF参考仅封装一致性。水为20261008冻结记录，不原次重算。114普通镜像专项＝97新＋17限制器；固定96专项＋3固定Docker，不是GitHub／全部Runtime。L3／L4严格断网NOT_EXECUTED。Actions NOT_EXECUTED，分发BLOCKED，源码确认待完成，Colab deferred，expert CANCELLED_BY_USER。旧HTTP／8ZIP／reexport PASS只作历史。源码、文档commit、build、host与image分别索引，tag非registry digest。
Markdown阅读物理顺序：overview、quick-start、user-molecule、results、tasks、help。来源输出含新版来源details；阈值仅引首版合同。下一批核对ZIP实际成员、CRC／size、哈希、复制、折叠导航、导出重开、三宽度及FAQ一致性；修订前实测及下载仅作历史证据，原次维护更新后需重新核对，不继承旧QA。
# MIGRATION
已取得完整网页源码，已保存修訂单文件及内嵌维护文本；源码取得不等于独立运行通过。原次仅静态修订待复核，修订后脚本未重新语法执行验证。独立运行与完整迁移验收未完成。
## 后续步骤（待执行）
1. 重新下载并确认单文件与五维护文件，或点击“下载完整网页包 ZIP”取得 ai4orgchem-runtime-guide-v0.3.0-candidate.zip 后解压。包根目录 ai4orgchem-runtime-guide/：docs/index.html（完整内嵌CSS/JS、可编辑并再次导出ZIP）、docs/.nojekyll（空）、README.md、content/guide_zh-CN.md、provenance/sources.md、verification/checks.md、MIGRATION.md、MANIFEST.txt，共10个文件（另两项为templates/molecular-service/water/request.json及templates/molecular-service/water/molecule.xyz），无依赖占位文件。核对原始结构及所有已登记自有脚本；检查平台注入未进入导出。完整仅指网页与维护材料，不含Runtime、镜像、科学档案或未取得资料；ZIP下载、解压与迁移验收尚未完成。
2. 对新版各自有脚本做语法执行检查；旧版静态报告不能自动覆盖新版。
3. 环境前提与预览详见README：安装可用的Python 3或获准静态服务器，在解压根目录执行 python -m http.server 8000 --directory docs，测试 http://localhost:8000/ 。单文件模式可在其目录执行 python -m http.server 8000。另行布置仓库子路径后测试对应repo/index.html的 http://localhost:8000/repo/ ，并测试带#sources等锚点刷新；不声称这些测试通过。
4. 独立复测新版T01—T34；测试中文前提、区域标题、手工label、英文大小写、隐藏任务、无结果、键盘和无JS移动目录，以及360/768/1440布局、剪贴板权限失败、导出HTML再运行。均未在原次执行。
5. 按README实际修改同步并核对T14/T19；确认必要运行资源全部内嵌或经明确授权打包。合法资料超链接不是运行依赖，但点击可能联网。
6. 核对网页来源、权属及授权，无未获准资料后再考虑迁移；不自动套用Runtime源码许可证。
历史局部操作、下载实物及未定位错误只见checks.md，不作为完整迁移验收。无上传、不依赖YouMind URL、不发布、不变权限。

## v0.3.0-candidate 内容维护与导出
运行时网页 HTML 是唯一内容源；guide_zh-CN.md 与 provenance/sources.md 由实际 domToMarkdown 函数从 pristineDoc 默认正文导出结构化 UTF-8 快照。没有 MD 自动反向构建。修改 HTML 六区域、多命令（按每个代码ID与data-language登记），入门命令 evidence-command 与唯一矩阵 history-registry，手工同步相关摘要、FAQ、来源及维护常量，然后重新导出 HTML、MD 与 ZIP；按 T14/T19 实际复核。ZIP真实目录10 members，保留原8文件，加templates/molecular-service/water/request.json与molecule.xyz；QA与包外交付清单不入ZIP。XYZ上传原文默认静态嵌入docs/index.html，并由guide Markdown的text语言代码块导出；molecule-xyz-text保留8行与结尾换行，不trim、不改注释、数值或行序。已补原文但逐字复制/导出/运行验证NOT_EXECUTED，未独立字节哈希/Runtime重运行；外部咨询CANCELLED_BY_USER、任意用户分子的旧条件态比较 Compute BLOCKED，无期望能量，不作研究结果、不运行计算。原次维护更新后的新字节版本需重新验收；修订前三宽度结构实测与下载实物列于历史区，不继承为当时 QA 成功。QA 实际记录须单独下载，不进入正文或 ZIP。

## 第二批协议修订（候选，不发布）
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

八ledger、八preflight、七live是已保存本地限定记录，不是原轮重算，不是总计算数或全通过数。115本地工程非GitHub Actions；science lane非其runner执行。内存为cgroup峰值，非RSS。所有科学项最终镜像重跑、scratch峰值、异机安装：NOT\_EXECUTED。

普通四步、水技术样例和固定案例已提供；完整网页验收仍有未执行项。任意用户分子的旧条件态比较 Compute BLOCKED；镜像分发 BLOCKED 等其他对象状态不改。
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
<a id="verification-records"></a>

## 验证记录（外部记录与当时版本分开）

外部来源：用户上传 REVIEW\_SUMMARY 转述；执行方本地 Codex，浏览器 IAB，2026-10-08。非 YouMind 原轮自执行，非真实 GitHub 部署。

严格绑定旧 HTML：161123 bytes，SHA256 ` 9a40351eac2ea05ef3990b5a6f7d782b8b9311e0abf4f06a5efbc965e3efcaea `；ZIP：257444 bytes，SHA256 ` 2f448b02c737b60caa605af76543d085649a8593d2da2652c54ebd0271ab643b `。新版字节改变，不继承 PASS。

外部限定记录：10 ZIP 成员 CRC、安全唯一路径、README 内外一致、水277/123一致、132 ID无重复／49 targets、50复制回读（49+Capabilities/List）、360/768/1440三宽度无整页overflow、三路径与搜索、默认导出、真实HTTP根模拟repo子路径与刷新、基础手机菜单与Tab范围。

200%真缩放、真禁JS、全键盘、多浏览器、二次导出、全部维护独立按钮：NOT\_EXECUTED。当时版本完整检查默认 NOT\_EXECUTED；字节身份按钮不执行结构测试，不授予结构PASS。

<a id="verification-current"></a>

```text
NOT_EXECUTED
```

当时复制按钮与目标动态inventory单独下载，不自动升级逐字PASS；当时完整验收NOT_EXECUTED。


## 文件索引表局部滚动修复
文件索引表局部滚动修复已写入，修后独立三宽度复测待执行。360/768/1440 须在全部 details 展开时独立复测；原次不登记通过、不套用旧哈希。裸表已在源 HTML 中置入可键盘聚焦的 table-scroll 局部滚动区域，保留表格 min-width:680px 与现有 grid/card/details 收缩规则；cleanExport 与 ZIP 内 docs/index.html 沿用源 HTML 修复，导出算法未改。

## 发布后同步状态说明
当时同步卡已补齐v0.1.0正式发布；原次实际正文与下载字节见validation/web-guide/postrelease-status-card-20261010.json。正式Release标签和附件保持不变，不用新网页字节冒充旧包。

## v0.1.0源码与指南发布材料
发布入口：https://github.com/CCcolab/AI4OrgChem-Runtime/releases/tag/v0.1.0 。原次发布链接文字与实际导出字节记录见 validation/web-guide/release-v0.1.0-downloads.json；旧修订及原浏览器补验记录各保留其原字节身份，不作为原次新包哈希。没有改动导出算法或科学代码。

## 静态指南网址与使用方式（2026-10-10）
GitHub Pages静态指南已启用：https://cccolab.github.io/AI4OrgChem-Runtime/ 。可直接在浏览器阅读、搜索、复制命令和下载指南；网页不提供在线计算，计算命令仍由用户本地Runtime执行。整个已公开main/docs作为发布源。

## 2026-10-09源码首次公开与远端CI记录（历史）
2026-10-09已按项目负责人授权公开源码与指南：https://github.com/CCcolab/AI4OrgChem-Runtime 。06d5088首次CI三项job均成功，真实P11预检一项跳过；详见https://github.com/CCcolab/AI4OrgChem-Runtime/actions/runs/37933616122 。Pages未启用；；未创建新版本/标签/Release。

说明：下列状态是YouMind原提供时的登记，不是最新包外实测。原次修订身份与受限实测见 Runtime validation/web-guide/special-review-followup-20261010.json；此前 full-review-repairs-20261010.json、online-browser-followup-fa7b4ee-20261010.json 和 export-compatibility-round2-20261010.json 保留各自旧字节身份，不验证原次修订；final-consistency-r2-20261009.json 仅为历史身份；手工QA默认未填写及200%缩放／完整键盘／多浏览器NOT_EXECUTED单独保留。

## 原YouMind v0.3.0-candidate交付登记（历史）
候选非已验收；currentordinaryenabled / legacyconditionalblocked。物理顺序 overview、quick-start、user-molecule、results、tasks、help。10 members：原8文件，加 templates/molecular-service/water/request.json 与 molecule.xyz；277/123 bytes、LF结尾、代码textContent原文。14 evidence、7旧任务、3固定案例、1普通服务，12数值checks。原提供时新字节版本的复制核对、ZIP实物CRC/哈希、HTML一致性、重开再导出与迁移及完整WEB合同尚未完成；修订前下载实物与三宽度结构实测只作历史，原提供时QA不继承。新包大小和SHA-256须现场生成。


## P11/P12局部补齐维护边界
状态清单置于两卡前，high-cost-list-command原命令字节与id保留。P11只复制历史账本，不建议已PASS苯G重复preflight；从实际注册清单尚未执行16态恰选一个Unit，不猜ID。P11高级原生details仅说明：工具创建全新不存在的独立预算、单态ceiling43200s，live精确Unit/Budget/OutputRoot，可选PythonExe/DockerExe；呋喃G→GL→GE使用原轮合格output的Inputs映射，P11B独立初始化。P11合同8GiB/8CPU/8线程；P12合同14GiB/16CPU/16线程，前序原轮G，N16 GE额外GL。两者软43080/硬43200s、scratch20GiB、engine+1/host+2/disk+1GiB，每态一次、失败计费、容器删除及证据闭合前不后续，不retry/resume。P12可复制预检改为来源已有未执行P12-N16-G；高级链接n16-live-details存在于完整guide快照，转换继续传guideTargets。原资源合同不明不足拒绝、分档未启用，不将15GiB作日常默认，不恢复18GiB，不重复内存探针。不是任意分子优化、不代表78态全部验收、不改科学规则，新安装镜像未重放，旧两PASS原历史保留且不继承新镜像。六主区顺序不变，tasks主标题最前。共同顶层10成员、水277/XYZ123原文、复制不执行保留；真200%/键盘/多浏览器/新版复制磁盘HTTP均NOT_EXECUTED，原轮不运行Runtime/Docker/科学。


## 2026-10-09限定更新（优先于历史维护说明）
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

水完成后，进入[自己的XYZ/request指南](content/guide_zh-CN.md#user-molecule)。普通H/C/N/O、电荷0、单重态、RHF/6-31G(d)、≤20原子、实际AO≤80保持；普通请求与旧条件态Check不能混用。

### 安装候选身份与受限验收

候选源码：` 575127b94214ca1a3c605bd2139bf77ba7e5dd1d `
受测构建：` 59f576c5a11f7192d0425765611a49369c6f561a `
新镜像：` sha256:a4086d916101ab16650a878971361b5ee6e4e7f9e62b7d750f672825b6bbe96f `

来源记录：45项工程PASS + 水单点 / P02统计 / P13图账本 / P07账本。不是全部科学任务认证；高成本新镜像重放 NOT\_EXECUTED。公开分发 BLOCKED，但支持从固定公开来源自行本地构建。

新安装的普通、固定、专题和高成本服务均使用各自登记的 installation record。旧候选启动器只用于原环境复核，不把新镜像直接交给只接受旧身份的入口。


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

P11A呋喃按G→GL→GE，必须以 ` --inputs ` 提供原轮合格前序output映射；P11B保留原独立初始化。科学规则固定，每态一次、失败计费；容器删除与证据闭合前不启动后续，不retry、不resume。

资源合同：8GiB、8CPU、8线程，软43080／硬43200s，scratch20GiB；engine +1GiB、host +2GiB、disk +1GiB。新安装镜像高成本未重放，旧先导PASS不继承到新镜像。

<a id="case-p12-high-cost"></a>

### 尺寸与状态对照

协议来源P12：N12/N14/N16 = 8/23/30态，B3LYPG/6-311g(2df,p)，原2011规则。N12控制不入加权；N14/16全部21/28组对权1。GL/GE依赖原轮G，N16 GE还需原轮GL。

通过回执和output子目录输入映射、哈希及容器删除核对前序，不能历史PASS替代新前序。完整组装未完成，历史2011对齐 NOT\_ESTABLISHED，不新增分类标签。

<a id="p12-ledger-command"></a>

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\high-cost-cases\installation-record.json --task P12 --mode ledger --output-root 'D:\chem-work\high-cost-runs'
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\high-cost-cases\installation-record.json --task P12 --mode preflight --unit P12-N16-G --output-root 'D:\chem-work\high-cost-runs'
```

不是用户任意分子的通用优化入口，不代表78态全部验收，不改变原科学规则。state list读取实际注册Unit；ledger只读历史账本；preflight仅元数据预检，按清单选择未执行Unit，以上N16-G为原来源已有未执行态，不重复准入P12-N12-G。live为单态科学执行，仅高级折叠说明，不自动启动、重试或续算。

### 高级：环状体系尺寸与状态对照 · 单状态live边界（仅说明，不安排执行）

参见[已有N16-G单态live来源说明](#n16-live-details)。精确选择一个未执行Unit，工具create-high-cost-budget.py在全新不存在文件创建独立预算，单态43200s；不手写或复用预算。GL/GE前序须为原轮合格G，N16 GE额外需要原轮合格GL，以 ` --inputs ` 提供output映射，历史PASS不能替代。

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

结果、receipts、manifests、native-events、资源、optimizedXYZ、checkpoint整目录保留；环状体系尺寸与状态对照 G没有density NPZ。旧受限PASS不重算，原轮没有科学执行。


<a id="revision-20261009-sources"></a>

### 2026-10-09修改来源与外部本地复核

用户修改文件：YOUMIND\_REQUIRED\_CHANGES\_20261009\_zh-CN（01a11ee5-6d9e-70ec-bf05-0c98e3f38174）。上传ZIP来源记录：14成员CRC实际读取通过、54031 bytes、SHA256 3aa579f84d2b489755cf14b808a9535a82bf12bbf06dc34c21c2afb387d19811。以下为外部本地复核源的路径文字，不是假外链，也不将参考全文装入10成员指南包。

- source\_basis/PROTOCOL\_CASES\_BATCH3\_zh-CN.md
- source\_basis/PROTOCOL\_CASES\_BATCH3\_ACCEPTANCE\_zh-CN.md
- source\_basis/SOURCE\_INSTALLATION\_zh-CN.md
- source\_basis/SOURCE\_INSTALLATION\_ACCEPTANCE\_20261009\_zh-CN.md
- 环状体系尺寸与状态对照 pilot JSON与REVIEW\_SUMMARY（来源索引名；不虚构未提供的完整路径）

外部2026-10-09 Edge154本地复核严格绑定旧导出HTML：166102 bytes，SHA256 ` f1b634e30a16438c635c634b07f46a6ff75a7d6c665b85ee13ce19cd20af727c `；ZIP：311948 bytes，SHA256 ` abbce379db36240b97996f23322f57a11a8044693ce67be4045b0e1514eaf65b `。不是YouMind原轮自执行，不是新版继承PASS，也不是GitHub部署。

旧字节外部记录：10成员CRC／磁盘哈希、8副本一致、74逻辑复制PASS（40 raw equal，34仅LF→CRLF）、7维护下载、水request 277 / XYZ 123 / 预算286精确身份。HTTP根／模拟repo刷新PASS、3路径／清除PASS、默认HTTP重开PASS；真禁JS仅9关键词覆盖。搜索仅OBSERVED；真200%缩放、全键盘、多浏览器仍NOT\_EXECUTED。不要修改复制代码来修平台换行。

YouMind原自动回读BLOCKED历史继续保留，不要求用户再次重复点击。当时修后脚本、三宽度默认／全展开／路径／手机菜单、导出、CRC与复制下载验收均待执行，不预填PASS，不引用旧SHA作为新身份。

维护：进入解压后的 ` ai4orgchem-runtime-guide/ ` 目录，运行 ` python -m http.server 8000 `，浏览 ` http://localhost:8000/docs/ `。仅静态指南维护，不启动Runtime；无真实托管。10成员共同顶层保持，包外清单／审计JSON和MD按当时字节动态生成。

原YouMind提供时状态（历史）：条件Compute BLOCKED；；远CI NOT\_EXECUTED；镜像分发BLOCKED；外部专家咨询已取消非前置。该原包轮不运行Runtime/Docker/WSL/科学，不发布、不改权限；原次公开与实际CI另见当时同步记录。


## 2026-10-09本地模块名称修订（优先于历史命名）
网页按实际计算功能命名十四个模块；主标题、选择提示和复制按钮说明无需先了解专著编号。内部P01—P14、任务键、命令参数、来源路径与科学规则保持。名称和编号对应表位于来源追溯折叠区。用户自己的分子目前仅支持普通RHF单点服务；这些模块采用固定案例或保存证据，不增加任意分子条件计算、优化或尺寸扫描的支持范围。多态约束优化和环状体系分别保持固定17态与61态，旧候选仅苯G、N12-G通过；新镜像不继承这些科学验收。2026-10-09已公开源码与指南，06d5088首次CI三项job成功；该源码同步日Pages仍未启用；模块改名轮的历史实测记录保存在Runtime validation/web-guide/module-names-20261009.public.json，绑定其当时HTML与归档ZIP；原次修订另见 validation/web-guide/special-review-followup-20261010.json；此前 full-review-repairs／online-browser-followup-fa7b4ee／export-compatibility-round2 保留各自旧字节身份；旧 final-consistency-r2-20261009.json 仅为历史证据，不继承其 SHA。
<a id="module-protocol-map"></a>

### 模块名称与内部协议编号（来源追溯）

| 内部协议编号 | 计算模块 | 当时范围 |
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

