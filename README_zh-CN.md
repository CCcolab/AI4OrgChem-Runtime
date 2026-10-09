# AI4OrgChem 本地分子计算 Runtime

[English](README.md)

源码与用户提供的网页指南已按用户授权公开同步到[CCcolab/AI4OrgChem-Runtime](https://github.com/CCcolab/AI4OrgChem-Runtime)。首推提交`06d50885bdccf31f83b89229c1513121542375d5`对应[GitHub Actions run 37933616122](https://github.com/CCcolab/AI4OrgChem-Runtime/actions/runs/37933616122)，三个限定范围的job均成功。详见[公开同步实绩](docs/GITHUB_PUBLIC_SYNC_20261009_zh-CN.md)；不据此认证全部科学服务或分发镜像。Pages尚未启用，不提供在线计算，尚未确定新版本号、打标签或发布Release。

[网页使用指南](docs/index.html)已随Runtime源码纳入公开仓库，可下载后在本地浏览器打开；[导入、验收与后续维护说明](docs/RUNTIME_WEB_GUIDE_zh-CN.md)保留原包和字节身份。仓库同步已完成，Pages托管仍是单独待办。

新增[源码安装、构建与独立身份登记指南](docs/SOURCE_INSTALLATION_zh-CN.md)：使用固定公开基础镜像、公开锁定依赖和重建的冻结科学源码，不再依赖旧的本地 Runtime 基础镜像。新镜像独立登记，不继承历史科学 PASS。使用 Git 克隆或安装器制作的源码 ZIP；[干净目录受限验收](docs/SOURCE_INSTALLATION_ACCEPTANCE_20261009_zh-CN.md)已通过公开准备、构建、四类登记、45 项工程测试及四个小任务。高成本重放和全新机器验收未执行，以下历史候选记录继续独立保留。

阅读 GitHub、网页指南或已有结果无需启动 WSL2／Docker；实际本地计算时才需要所选后端。当前计算验收主要对应记录中的 Docker 候选。[普通WSL2原生入口](docs/NATIVE_WSL2_RUNTIME_zh-CN.md)现已通过只读 Check，原生 Compute 尚未实现／验收；普通WSL2与暂停的WSLc分开。不计算时可退出Docker，镜像保存在磁盘即可。

2026-10-09维护增补：[Docker启动防护](docs/DOCKER_STARTUP_RECOVERY_20261009_zh-CN.md)三次受限重启与活动任务拒绝通过；[实际组件许可附录](compliance/HIGH_COST_COMPONENTS_20261009_zh-CN.md)已补齐新增材料，镜像分发仍BLOCKED_LOCAL_ONLY。已验收P12-N12-G继续PASS，不重算或重复内存准入；15GiB是旧Docker统一门槛，不是用户日常默认要求。[P12资源分档候选](docs/P12_RESOURCE_TIERS_CANDIDATE_zh-CN.md)未启用。远端CI、WSLc和源码公开仍按各自记录确认。

项目目标是面向用户分子的本地化学计算平台：按分子输入、单点能量、轨道/密度分析和结构优化等研究目标提供服务。用户无需先了解专著P01—P14；这些编号保留在“示例与验证”及来源详情。新增通用入口的拆分、实施顺序和验收要求见[面向用户分子的入口设计](docs/GENERAL_CHEMISTRY_ENTRY_DESIGN_zh-CN.md)。已交付首版用户自选分子普通RHF单点、canonical轨道与AO密度矩阵导出；首版范围为H/C/N/O、中性单重态、RHF/6-31G(d)、最多20原子且实际AO数≤80。三维结构可用，无需P编号或专有片段。DFT、开壳层、通用优化、扫描和网格密度仍待独立实施。

普通分子计算从[四步使用指南](docs/MOLECULAR_SINGLE_POINT_zh-CN.md)开始，使用 `scripts/start-molecular-service.ps1` 和自己的XYZ/请求。四个分子实测及同库直接调用对照通过，候选镜像内114项工程测试通过；非root、只读源与输入、断网、退出码和删除容器后输出保留分别核验。见[2026-10-08验收报告](docs/MOLECULAR_SINGLE_POINT_ACCEPTANCE_20261008_zh-CN.md)及[机器状态](validation/molecular-service/deployment-20261008.json)。同库对照不是独立科学引擎认证，波函数稳定性未执行。

示例与历史复核从 [本地Runtime入口](docs/LOCAL_RUNTIME_ENTRY_zh-CN.md) 开始：查阅P01—P14既有证据、执行受限Check/Report，或选择三个新增[固定登记复算](docs/REGISTERED_CASES_zh-CN.md)：P02冻结表统计、P13图规则与账本、小体系P01乙烯占据表示控制。三个任务有独立来源锁、受控本地镜像和运行记录；实际部署状态见[部署边界](docs/REGISTERED_CASES_DEPLOYMENT_BOUNDARIES_zh-CN.md)。旧用户分子条件态比较Compute仍BLOCKED，与新普通单点分开。Git/项目ZIP提供来源可核对的源码，不包含完整安装环境；WSLc、镜像分发及源码公开保持分别记录。

以下带日期的工程、条件态失败和原七任务记录保留各自历史范围；其中GitHub CI未执行、源码公开待确认等表述属于对应日期的历史状态，当前首推与远端CI实绩见上方新记录。“Compute BLOCKED”指旧条件态比较服务，不撤销上方普通RHF入口的限定支持。

[2026-10-07合作停止工程](docs/USER_MOLECULE_NATIVE_SHUTDOWN_ENGINEERING_20261007_zh-CN.md)：154项专项工程回归通过；两种零原生停止场景保存关闭回执，强杀反例的最终回执保持未知。四段开销各测3次，不外推真实求解容量。该2026-10-07增补无新增科学计算/预算，旧139次OPEN账本保留，不重试；Compute仍BLOCKED。

[此前框架验收](docs/LOCAL_RUNTIME_FRAMEWORK_20261007_zh-CN.md)：231个独立工程测试、22项PowerShell进程及12项来源/预检通过；该轮未新建科学预算。GitHub CI运行仍NOT_EXECUTED。

[最新唯一原生根诊断](docs/USER_MOLECULE_ROOT_NATIVE_DIAGNOSTIC_20261007_zh-CN.md)：139次NR完成、138成功回调/1截止失败；含清理279.031秒，第一96差分完成、第二部分未完成。无正式根/尾检，原OPEN账本保留，Compute仍BLOCKED；未自动重试。

[此前原生根候选工程](docs/USER_MOLECULE_ROOT_NATIVE_ENGINEERING_20261007_zh-CN.md)：108项专项工程测试及29护栏真实缓存零F准备通过；该轮根搜索NOT_EXECUTED、科学预算为空。后续唯一真实尝试见上段，当前Compute仍BLOCKED；未重建镜像。

此前 `7530595` 的 [单起点候选与零计算准备](docs/USER_MOLECULE_OCCUPIED_SPACE_ROOT_PREPARATION_20261007_zh-CN.md)已完成：150项专项工程测试（40新增、110回归）及实际缓存零F准备通过；新增真实F/NR/SCF为0。该历史版本不允许真实根搜索或预约科学预算，实际runner未实现/未执行。后续唯一真实尝试见上段；当前没有可追加或复用的重试预算，Compute仍BLOCKED。原规则、门槛和旧数值记录保留。

此前 [十二点真实条件算子响应](docs/USER_MOLECULE_OCCUPIED_SPACE_RESPONSE_20261007_zh-CN.md)已完成：129项专项工程测试、实际零F准备与12次真F/NR通过，8组同D子集通过；所有点gap通过但comm/map失败，无合格自洽根，Compute保持BLOCKED。SCF/根搜索/尾检未执行，新12槽预算关闭。

此前 [确定性占据空间初值与模拟准入](docs/USER_MOLECULE_OCCUPIED_SPACE_ADMISSION_20261007_zh-CN.md)已形成：四个纯数组初值、97项专项测试和12次模拟回调通过，新增真实F/SCF为0。当轮真实响应及根搜索未实现/未执行；真实响应后续已执行，见上方新记录，原门槛和Compute BLOCKED保留。

此前 [单次条件算子响应诊断](docs/USER_MOLECULE_OCCUPATION_RESPONSE_20261007_zh-CN.md)已实现并完成：101项专项工程测试、实际零F准备通过；一个新进程完成三密度×三路径9次真F/NR，零SCF。六个同D算子子集对照通过，但九个单点均未合格，Compute保持BLOCKED。旧预算已保留，新9槽预算关闭，不自动追加计算。

此前 [原规则服务范围与占据方向诊断](docs/USER_MOLECULE_OCCUPATION_SCOPE_20261007_zh-CN.md)已完成：两生产保存算子的精确谱窗口与六个冻结占据见证均已核验；仅改变冻结F下的占据方向不能通过原正能隙门槛。内部操作性范围已明确，新增F/SCF/容器为0，Compute仍BLOCKED。该只读轮的响应提案已另行实现并执行，见上方新记录；原定义和门槛保持。

此前 [预算感知与匹配诊断记录工程](docs/USER_MOLECULE_BUDGET_RECORDING_20261007_zh-CN.md)已实现，122项专项模拟测试和三个导出示例通过。新分子F/SCF为0，未接入科学worker、未改门槛，Compute仍BLOCKED。

此前 [V2存量矩阵内部分析](docs/USER_MOLECULE_SEED_V2_INTERNAL_ANALYSIS_20261007_zh-CN.md)已确认窄π谱空间中的秩一占据和参考预算返回语义，并澄清能量导数关系。新增F/SCF/容器为0，原门槛及Compute BLOCKED保留；该轮提出的预算记录候选现已另行实现并通过模拟工程验证，真实分子路径未切换。

此前 [V2种子实施与诊断](docs/USER_MOLECULE_SEED_V2_DIAGNOSTIC_20261007_zh-CN.md)：239项专项工程测试及零F种子准入通过；一次591F/约4.82分钟诊断完成，生产最终占据/能隙门禁失败，参考最终门禁未完成。原算子与门槛保留，Compute仍BLOCKED；完整CI及旧结果不重跑。

用户已明确取消外部专家咨询、意见征询及签署流程（CANCELLED_BY_USER）。后续按 [内部定义与验证](docs/USER_MOLECULE_INTERNAL_VALIDATION_zh-CN.md) 推进，不等待外部回复；三个科学问题保留为内部工作项。现有数值失败和资源门槛保留，V2已实现并完成一次受限诊断，最终资格未通过，Compute关闭。

[近简并规则与验收候选V2](docs/USER_MOLECULE_NEAR_DEGENERACY_RULES_V2_zh-CN.md) 已明确为“普通态占据子空间按屏蔽度量重正交的初值”；原最终2/0、Aufbau映射和正能隙门槛保留。已收到材料/静态反馈并补齐A02准入与UM编号；V2种子与独立参考已实现；一次受限诊断已执行但数值未合格，内部解释待完成，不追加计算或启用Compute。原专项外审材料保留为历史，其咨询流程已取消。

此前 [实时准入与条件初始化诊断](docs/USER_MOLECULE_RESIDUAL_LIVE_DIAGNOSTIC_20261006_zh-CN.md) 已执行：单个1 GiB/1 CPU/零swap进程复用旧普通态，三路径各求值一次，均因约1e-14 Hartree的初始能隙未满足原1e-6门槛而拒绝；轨道迭代未启动。同D0算子/能量/已准备mask子范围通过，完整T05及用户分子入口的UM-P12／UM-P13／T06合格比较未执行（历史机器键保留为P12／P13）。实时资源范围仅覆盖本次准备与初始化，科研W07/生产Compute仍BLOCKED。原始记录保留，后续仅修正独立参考拒绝标签并通过数组回归；没有重复真实诊断或重建镜像。

[最小准备、独立参考与持久化预算](docs/USER_MOLECULE_PREPARATION_REFERENCE_20261006_zh-CN.md) 已补齐，97个唯一用例形成按版本核对的通过覆盖（72新项＋25资源回归），并完成真实PySCF旧缓存映射；这不是一次97项完整CI。该准备轮没有新真实条件计算；后续实时诊断另见上方，生产Compute仍BLOCKED。此前 [条件算子桥](docs/USER_MOLECULE_RESIDUAL_BRIDGE_20261006_zh-CN.md)、[纯数组残差原型](docs/USER_MOLECULE_RESIDUAL_PROTOTYPE_20261006_zh-CN.md) 和旧失败保留，旧完整CI不自动包含这些增补。

此前完整 [W01—W07 本地工程 CI](docs/USER_MOLECULE_CI_W01_W07_20261006_zh-CN.md) 已通过176个独立单元用例（284次执行）、启动器10项、平台4项及W07宿主报告9项；18个测试容器按成功删除回执移除，输出保留。新增科学计算为0，科研Compute仍BLOCKED，真人反馈不阻塞当前工程交付。GitHub Actions仍NOT_EXECUTED，来源和平台边界保持分列。

2026-10-05 隔离分支现状：Check 和 Report 可用，生产 Compute 保持 **BLOCKED**。[W05—W06 受限分子验收](docs/USER_MOLECULE_W05_W06_NUMERICAL_REVIEW_zh-CN.md) 已执行，普通态及同密度算子对照在所列范围内通过，但条件态驻定、两存储路径等价性和完整参考门禁失败，不能进入正式 W07。下文 L0—L4 属于原七任务候选，不转移为新服务科学资格；原工作区与既有交付保留。

W05 [验收准备](docs/USER_MOLECULE_W05_PREPARATION_zh-CN.md) 是此前的元数据批次。先前验收驱动84项工程测试和四组完整流程峰值保留；最新 [求解器 v2](docs/USER_MOLECULE_SOLVER_V2_zh-CN.md) 的122项工程测试通过，乙烯 pilot 两条同密度对照通过，但三条条件路径仍失败。实际限额1 GiB、1 CPU、零 swap，资源结论限定精确流程，不构成通用用户计算规模或研究范围批准。

2026-10-06 的既有 [存量方法审阅](docs/USER_MOLECULE_METHOD_REVIEW_20261006_zh-CN.md)定位了初始占据边界的窄谱区间和历史占据跳变，并给出能量—算子关系判据；没有新增分子计算或方法批准。[旧下一版分子求解设计](docs/USER_MOLECULE_SOLVER_NEXT_DESIGN_zh-CN.md)保留为历史候选。准备映射、候选初始化、独立参考及持久化记账工程已实现；旧工程方案仅登记单进程900秒/1GiB/603slot候选；后续已另立实时执行合同完成一次初始化拒绝诊断，科学范围仍未验收。科研 W07/Compute 保持 BLOCKED。

此前 [主机只读 Report 与导出](docs/USER_MOLECULE_REPORT_20261006_zh-CN.md) 增补保护旧运行目录、核对记录字节/身份、区分未执行与数值失败，并保留宿主/容器退出码。其48项标准库测试和11项主机报告集成通过。基础模式核对登记字节并读取历史快照；高级模式检查关键证据并导出派生报告。该增补轮次没有重算、启动新容器或重建镜像。

此前 [W07 工程试用指南](docs/USER_MOLECULE_W07_ENGINEERING_TRIAL_zh-CN.md) 提供输入、Check、报告/导出三步流程及反馈模板。已用现有乙烯夹具完成一次真实容器 Check 和三项主机报告操作；无 SCF、网格、完整 ERI 或 Compute。这是历史工程人员演示；真人试用与反馈现按用户要求 DEFERRED_BY_USER，作为未来可选事项，不阻塞当前工程验收。原外部一致性咨询已按用户最新指示取消；内部定义与验证尚未完成，正式 W07 和生产 Compute 保持 **BLOCKED**。

此前 [W07 代理模拟自测](docs/USER_MOLECULE_W07_SELFTEST_zh-CN.md) 已通过9个启动器场景（8个容器）、6个宿主保护/历史失败判读场景及12个宿主 parser 用例。覆盖已有乙烯/丁二烯两 profile 的 Check、输入/身份拒绝、只读报告与导出；两次 Compute CLI 仅执行拒绝探针，该轮新科学计算为0。本地工程交付已形成，科研 W07/生产 Compute 仍 BLOCKED；模拟不冒充真人体验或数值合格。

W07 本地源码/证据候选另含可搬移 Check 和失败样例、源码备份及新服务专属支持/来源矩阵。两类样例搬移后和从重建的 runtime Git 源码读取均通过，科学源码解包匹配591个锁定文件。候选包不含 Docker 镜像或依赖，不宣称完整环境恢复；r3 实际安装组件的完整许可审计仍 NOT_EXECUTED。[交付范围](docs/USER_MOLECULE_W07_ENGINEERING_TRIAL_zh-CN.md#交付范围按需查阅) 明确这些边界，不移用旧镜像验收结论。

[W01—W05 本地工程/合同 CI](docs/USER_MOLECULE_CI_20261005_zh-CN.md) 已通过38项单元测试、10个集成用例和4项平台探针；GitHub Actions 未执行，该结论不代表 W05 数值验收通过。

此前完整 [W01—W06 本地工程 CI](docs/USER_MOLECULE_CI_W01_W06_20261005_zh-CN.md) 的63项独立单元用例（102次执行）及集成/平台记录保留，与本轮数值失败分别登记。GitHub Actions 仍 NOT_EXECUTED，WSLc 仍 BLOCKED/暂停。

[W06 工程候选](docs/USER_MOLECULE_W06_ENGINEERING_zh-CN.md) 和新参考通过干净提交的只读挂载复用旧 r3 镜像，尚未重建到镜像内。[SCF与方法审阅任务书](docs/USER_MOLECULE_SCF_REVIEW_REQUEST_zh-CN.md) 列出真实剩余阻塞；没有数值合格研究结果，没有公开发布。

2026-10-03 交付审查完成：本地 Docker 已验证 L0—L4、等价性与固定协议联合分类；WSLc **BLOCKED / NOT_EXECUTED**；CI **静态审查完成，运行 NOT_EXECUTED**。**镜像分发 BLOCKED；源码公开另行确认**。见 [最终审查摘要](validation/DELIVERY_REVIEW_2026-10-03_zh-CN.md)、[许可证审查](docs/LICENSE_REVIEW_zh-CN.md)。

日常使用入口：`./scripts/start-runtime.ps1 -Task evidence`，可从 Windows PowerShell 5.1 自动调用已有 PowerShell 7。镜像、日志备份及恢复说明见 [本地交付指南](docs/LOCAL_DELIVERY_zh-CN.md)。当前以本地 Docker 实测为交付范围；WSLc 升级及验收暂停。

本项目封装 AI4OrgChem 公开科学程序，以固定源码、精确依赖、分层启动和持久结果降低复核门槛。科学程序、协议、冻结证据和判定由上游管理。

Runtime源码和指南现已公开同步，本轮以提交身份记录候选，尚未确定新Runtime版本号；此前v0.1.0开发候选标记属于历史记录，不是本轮正式Release。上游来源为 `v0.3.2` / `28511f3d84fa65707a107cde1e8121a7b4334ecb`；上游 Python 包版本另为 `0.1.0`。

| 入口 | 独立 WSL2 候选环境 | 本地 Docker 候选镜像 | Windows WSLc |
|---|---|---|---|
| L0 evidence | PASS | PASS | NOT_EXECUTED |
| L1 core-tests | PASS | PASS | NOT_EXECUTED |
| L2 p14-smoke | PASS | PASS | NOT_EXECUTED |
| p14-equivalence | PASS（另保留一次预检 FAIL） | PASS | NOT_EXECUTED |
| L3 p14-fixed | NOT_EXECUTED | PASS（固定几何 anchor 资格） | NOT_EXECUTED |
| L4 p14-optimize | NOT_EXECUTED | PASS（优化资格） | NOT_EXECUTED |
| p14-classify 实际四输入联合分类 | NOT_EXECUTED | PASS：consistent（固定协议范围） | NOT_EXECUTED |

本地 Docker 候选的 L0—L2、等价性及指定验收探针已断网验证，同时验证了非 root、源码只读、退出码与删除容器后输出保留；**L3/L4 严格断网未执行**。WSLc 仍为 BLOCKED，Docker 结果不替代 WSLc。详见 validation/oci-summary.json。L4 可保存检查点，但不支持恢复运行。L0 只核验冻结证据；L1 是核心实现测试；L2 是 STO-3G 技术试跑，不作为科学复算认证。

## Docker 自行构建与运行

在干净的 runtime 检出中，使用 PowerShell 7.3+ 和已可用的 Docker Linux/amd64 引擎。构建需要网络，无需公开镜像：

```powershell
./scripts/build-wslc.ps1 -Engine docker -Tag ai4orgchem-runtime:local-source-candidate
./scripts/run-wslc.ps1 -Engine docker -Task evidence -Image ai4orgchem-runtime:local-source-candidate -OutputRoot 'D:\AI4Science\ai4orgchem-runtime-runs\source-review'
```

build-wslc.ps1 虽以 WSLc 命名，也支持显式 Docker 引擎。自行构建会形成新的 runtime/镜像身份；既有验收结果只属于记录中的旧候选，不能直接作为新镜像的通过证明。普通启动器没有强制网络隔离。已有本地验证镜像可使用前述 PowerShell 5.1 启动入口。

## 未验收的 WSLc 候选适配

本机 WSL 升级和 WSLc 实测已暂停。以下仅说明候选接口，不是当前已验证的使用路径：

```powershell
./scripts/probe-wslc.ps1 -OutputDirectory D:\AI4Science\ai4orgchem-runtime-runs\platform-probe
./scripts/build-wslc.ps1 -Tag ai4orgchem-runtime:candidate
./scripts/run-wslc.ps1 -Task evidence -Image ai4orgchem-runtime:candidate
./scripts/acceptance-wslc.ps1 -Image ai4orgchem-runtime:candidate -OutputRoot D:\AI4Science\ai4orgchem-runtime-runs\target-validation
```

安装条件见 [安装指南](docs/INSTALL_zh-CN.md)，任务参数、输出和状态见 [运行指南](docs/RUN_zh-CN.md)，实际状态见 [验证报告](validation/REPORT_2026-10-02_zh-CN.md)。源码审查见 [审查报告](docs/SOURCE_AUDIT_zh-CN.md)。

不纳入 GPU 训练、在线 Agent 服务、新命题、P09/P10 完整重优化、任意用户分子条件态或原著全文。第二批另提供固定协议的 P09 诊断与 P10 普通 DFT 扫描，范围见下方指南。运行任务不临时安装软件、更新源码或调用大模型 API。项目不新增科学判定，也不构成科学认证。

专业复核阅读层见 [S1—S6 模块对应与服务卡片](docs/PROFESSIONAL_SERVICES_zh-CN.md)、[结果判读](docs/REVIEW_RESULTS_zh-CN.md)、[三类用户路径](docs/USER_PATHS_zh-CN.md)及[已有 Docker 记录示例](docs/examples/P14_REVIEW_20261002_zh-CN.md)。[复核报告](docs/templates/REVIEW_REPORT_zh-CN.md)与[反馈模板](docs/templates/FEEDBACK_zh-CN.md)供手工填写；自动汇总工具未实现，旧七任务入口保留；2026-10-08另增加三个固定P02/P13/P01入口，见上方指南。该文档增补与 `2460eef` 此前候选保留不同历史身份；两者现已纳入用户授权公开的完整历史。十一份YouMind Skill导出由用户延后，不作为已实现Skill交付。

获授权的首次推送已触发现有 GitHub Actions CI：[run 37933616122](https://github.com/CCcolab/AI4OrgChem-Runtime/actions/runs/37933616122)三个限定job均成功，执行构建／轻量测试并上传运行证据附件，保留七天；日志和附件已纳入用户授权公开范围。CI不推送镜像、不打正式标签、不发布Release。本次运行不替代历史科学验收，不执行WSLc或高成本科学重放；本地工程CI旧记录继续单独保留。

第二批按研究用途接入扭转路径账本、条件态直接响应、π–σ 比较、独立能量组装、路径闭合、丁二烯 GL 端点、环丁二烯条件态诊断及苯核排斥／普通 DFT 扫描。入口、固定输入及新计算范围见[第二批使用指南](docs/PROTOCOL_CASES_BATCH2_zh-CN.md)，实际结果见[验证摘要](docs/PROTOCOL_CASES_BATCH2_VALIDATION_zh-CN.md)及[支持矩阵](validation/protocol-cases/support-matrix.json)。这是本地固定协议服务；任意用户小分子的普通 RHF 服务另有首批范围，任意用户分子的条件态 Compute 仍 BLOCKED。各次数值记录属于各自登记的镜像，不冒充最终候选镜像上全部重新执行的验收。

第三方许可补充包与未解决的对应源码要求见 [源码交付方案](docs/CORRESPONDING_SOURCE_zh-CN.md)及[材料校验记录](validation/license-materials-review.json)。取得通知不等于 binary/source 对应关系已证明；**镜像分发BLOCKED；源码与用户提供的指南已按授权公开**。第三方许可和NOTICE边界继续适用。


源码公开和镜像分发分别评估，见[公开边界与本地候选](docs/PUBLICATION_BOUNDARIES_zh-CN.md)。源码与指南同步已完成；原生wheel来源仍有未解决项，镜像未分发。
