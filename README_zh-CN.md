# AI4OrgChem 可复算运行环境

2026-10-05 隔离分支增补：用户分子入口 W01—W04 工程候选已建立，Check 和 Report 已实测；Compute 保持 BLOCKED，尚未执行新分子 SCF 或 W05/W06 科学验收。使用 [新入口指南](docs/USER_MOLECULE_RUN_zh-CN.md)，核查 [本轮交付与支持矩阵](docs/USER_MOLECULE_W01_W04_DELIVERY_zh-CN.md)。下文 L0—L4 结论属于原七任务候选，不转移为新服务的科学资格。原主工作区与既有候选保留。

W05 [验收准备](docs/USER_MOLECULE_W05_PREPARATION_zh-CN.md) 已保存两份候选分子、两配置四次元数据 Check、判据/独立参考/资源提案；数值验收 NOT_EXECUTED，生产 Compute 继续关闭，研究范围待审。

[W01—W05 本地工程/合同 CI](docs/USER_MOLECULE_CI_20261005_zh-CN.md) 已通过38项单元测试、10个集成用例和4项平台探针；GitHub Actions 未执行，该结论不代表 W05 数值验收通过。

最新 [W01—W06 本地工程 CI](docs/USER_MOLECULE_CI_W01_W06_20261005_zh-CN.md) 已通过63项独立单元用例（102次执行）、10个Windows集成动作、3个W06服务动作、4项平台探针和7项PowerShell检查。此前批次保留；新分子科学验收、GitHub Actions与WSLc状态不因此升级。

[W06 工程候选](docs/USER_MOLECULE_W06_ENGINEERING_zh-CN.md) 增加独立数组条件参考、只读研究资格判读和短简报；分子参考/资源/研究验收仍未执行，Compute 保持关闭。当前 r3 镜像尚不包含这些增补。

2026-10-03 交付审查完成：本地 Docker 已验证 L0—L4、等价性与固定协议联合分类；WSLc **BLOCKED / NOT_EXECUTED**；CI **静态审查完成，运行 NOT_EXECUTED**。**镜像分发 BLOCKED；源码公开另行确认**。见 [最终审查摘要](validation/DELIVERY_REVIEW_2026-10-03_zh-CN.md)、[许可证审查](docs/LICENSE_REVIEW_zh-CN.md)。

日常使用入口：`./scripts/start-runtime.ps1 -Task evidence`，可从 Windows PowerShell 5.1 自动调用已有 PowerShell 7。镜像、日志备份及恢复说明见 [本地交付指南](docs/LOCAL_DELIVERY_zh-CN.md)。当前以本地 Docker 实测为交付范围；WSLc 升级及验收暂停。

本项目封装 AI4OrgChem 公开科学程序，以固定源码、精确依赖、分层启动和持久结果降低复核门槛。科学程序、协议、冻结证据和判定由上游管理。

当前为 **v0.1.0 开发候选**，未公开发布。上游来源为 `v0.3.2` / `28511f3d84fa65707a107cde1e8121a7b4334ecb`；上游 Python 包版本另为 `0.1.0`。

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

不纳入 GPU 训练、在线 Agent 服务、新命题、P09/P10 尚未开放入口或原著全文。运行任务不临时安装软件、更新源码或调用大模型 API。项目不新增科学判定，也不构成科学认证。

专业复核阅读层见 [S1—S6 模块对应与服务卡片](docs/PROFESSIONAL_SERVICES_zh-CN.md)、[结果判读](docs/REVIEW_RESULTS_zh-CN.md)、[三类用户路径](docs/USER_PATHS_zh-CN.md)及[已有 Docker 记录示例](docs/examples/P14_REVIEW_20261002_zh-CN.md)。[复核报告](docs/templates/REVIEW_REPORT_zh-CN.md)与[反馈模板](docs/templates/FEEDBACK_zh-CN.md)供手工填写；自动汇总工具未实现，计算任务仍为七个。该文档增补与 `2460eef` 此前公开候选分开审阅，公开范围另行确认。

首次向获授权仓库推送会触发现有 CI，执行构建/轻量测试并上传运行证据附件，保留七天；日志和附件须纳入公开范围审阅。CI 不推送镜像、不打正式标签、不发布 Release；当前实际运行仍为 NOT_EXECUTED。

第三方许可补充包与未解决的对应源码要求见 [源码交付方案](docs/CORRESPONDING_SOURCE_zh-CN.md)及[材料校验记录](validation/license-materials-review.json)。取得通知不等于 binary/source 对应关系已证明；**镜像分发 BLOCKED；源码公开另行确认**。


源码公开和镜像分发分别评估，见[公开边界与本地候选](docs/PUBLICATION_BOUNDARIES_zh-CN.md)。原生 wheel 来源仍有未解决项，两类公开操作均未执行。
