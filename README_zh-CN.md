# AI4OrgChem 可复算运行环境

本项目封装 AI4OrgChem 公开科学程序，以固定源码、精确依赖、分层启动和持久结果降低复核门槛。科学程序、协议、冻结证据和判定由上游管理。

当前为 **v0.1.0 开发候选**，未公开发布。上游来源为 `v0.3.2` / `28511f3d84fa65707a107cde1e8121a7b4334ecb`；上游 Python 包版本另为 `0.1.0`。

| 入口 | 独立 WSL2 候选环境 | OCI 镜像 | Windows WSLc |
|---|---|---|---|
| L0 evidence | PASS | PASS | NOT_EXECUTED |
| L1 core-tests | PASS | PASS | NOT_EXECUTED |
| L2 p14-smoke | PASS | PASS | NOT_EXECUTED |
| p14-equivalence | PASS（另保留一次预检 FAIL） | PASS | NOT_EXECUTED |
| L3 p14-fixed | NOT_EXECUTED | PASS（固定几何 anchor 资格） | NOT_EXECUTED |
| L4 p14-optimize | NOT_EXECUTED | NOT_EXECUTED | NOT_EXECUTED |
| p14-classify 实际四输入联合分类 | NOT_EXECUTED | NOT_EXECUTED | NOT_EXECUTED |

本地 Docker OCI 候选已完成断网、非 root、源码只读、退出码与删除容器后输出保留验收；WSLc 仍为 BLOCKED，Docker 结果不替代 WSLc。详见 validation/oci-summary.json。L4 可保存检查点，但不支持恢复运行。L0 只核验冻结证据；L1 是核心实现测试；L2 是 STO-3G 技术试跑，不作为科学复算认证。

构建和目标主机运行（WSLc 候选，需实际验收）：

```powershell
./scripts/probe-wslc.ps1 -OutputDirectory D:\AI4Science\ai4orgchem-runtime-runs\platform-probe
./scripts/build-wslc.ps1 -Tag ai4orgchem-runtime:candidate
./scripts/run-wslc.ps1 -Task evidence -Image ai4orgchem-runtime:candidate
./scripts/acceptance-wslc.ps1 -Image ai4orgchem-runtime:candidate -OutputRoot D:\AI4Science\ai4orgchem-runtime-runs\target-validation
```

安装条件见 [安装指南](docs/INSTALL_zh-CN.md)，任务参数、输出和状态见 [运行指南](docs/RUN_zh-CN.md)，实际状态见 [验证报告](validation/REPORT_2026-10-02_zh-CN.md)。源码审查见 [审查报告](docs/SOURCE_AUDIT_zh-CN.md)。

不纳入 GPU 训练、在线 Agent 服务、新命题、P09/P10 尚未开放入口或原著全文。运行任务不临时安装软件、更新源码或调用大模型 API。项目不新增科学判定，也不构成科学认证。
