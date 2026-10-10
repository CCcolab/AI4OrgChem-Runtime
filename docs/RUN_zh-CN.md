# 分层运行合同

当前状态（2026-10-10）：源码和静态指南已公开；当前各类服务见[专业服务矩阵](CURRENT_PROFESSIONAL_SERVICES_zh-CN.md)。本页说明原七任务的 Docker 运行合同。指定本地候选 L0—L4、等价性及联合分类的历史验收保留，严格断网仅覆盖 L0—L2、等价性和指定探针，L3/L4 严格断网未执行。[Actions run 38003025857](https://github.com/CCcolab/AI4OrgChem-Runtime/actions/runs/38003025857)对 `86e29b47` 三个既有 job 成功，仅覆盖工程合同及旧 L0/L1；不认证本轮新安装路径或全部科学服务。镜像分发仍受[公开边界](PUBLICATION_BOUNDARIES_zh-CN.md)中的独立阻塞约束。

专业阅读入口：[模块与规则对应表](PROFESSIONAL_SERVICES_zh-CN.public.md)、[结果判读](REVIEW_RESULTS_zh-CN.public.md)、[三类用户路径](USER_PATHS_zh-CN.public.md)、[已有验收示例](examples/P14_REVIEW_20261002_zh-CN.public.md)。文档示例不自动启动新运行；本轮沿用已有结果。

Windows 日常使用 `scripts/start-runtime.ps1`，可从 PowerShell 5.1 自动选择已有 7.3+，固定 Docker；底层 `scripts/run-docker.ps1` 需已有 PowerShell 7.3+。容器内稳定接口为 `python -m runtime.cli run TASK`，entrypoint 自动调用。任务白名单：evidence、core-tests、p14-smoke、p14-equivalence、p14-fixed、p14-optimize、p14-classify。未知 task/参数由 argparse/PowerShell 拒绝。新普通分子及三批案例使用各自入口，不套用原 P14 镜像身份。

```powershell
./scripts/run-docker.ps1 -Task evidence -Image ai4orgchem-runtime:oci-candidate-20261002 -OutputRoot 'D:\AI4Science\ai4orgchem-runtime-runs\我的复核 output'
./scripts/run-docker.ps1 -Task core-tests -Image ai4orgchem-runtime:oci-candidate-20261002
./scripts/run-docker.ps1 -Task p14-smoke -Image ai4orgchem-runtime:oci-candidate-20261002 -Threads 8
```

每次自动建立唯一 UTC 时间+task+随机 ID 目录；不复用 runs/reproduction，不读取旧输出，不清理历史结果。包含 run-manifest.json、各子程序 stdout/stderr、P14 原输出 result.json/report.md 和适用的 checkpoint.json。日志不主动输出全部环境变量、令牌或用户目录。

manifest 分别记录：固定科学 commit、runtime commit、runtime 代码/锁快照摘要、镜像 registry digest（不可获取写 UNKNOWN）和本地 image ID、依赖锁/实际版本、实际命令、输入/输出哈希、线程、主机/cgroup 内存、耗时、子程序退出码、runtime 退出码、数值资格与科学比较。UNKNOWN 不等于 0；镜像 ID 与 registry manifest digest 不混用。

L0 顺序核验十四项、P12、导航和 P14 内部证据；不做新科学计算。L1 使用三份原测试。L1 失败则停止后续解释；不同 task 的独立运行仍需用户先核对 L1。L2 是 STO-3G 烟测；等价性也只比较 STO-3G 实现。

计算任务实际线程变量在导入 PySCF/NumPy 前设置，默认 8，受 affinity 和可读 CPU quota 约束；静态上游 thread_count 字段不作为实测。高级任务必须通过内存预检：L3 13000 MiB、L4 13 GiB；cgroup 剩余额度与 MemAvailable 取较小值，未知/不足拒绝。原上游另有自带资格门禁，不降低任何阈值。

每个计算任务要求共享锁根。容器启动器绑定宿主统一 /locks 并保持 Windows 排他锁；普通 Linux 用户显式提供同一 --lock-root。锁只覆盖本 runtime 管理、使用同一锁根的集合。临时积分/缓存放 Linux 临时文件系统，检查点和最终结果放持久输出。

## L3/L4 状态与资源

本机 Docker 已按后续授权实跑 L3/L4，均通过原资格门禁。L3 耗时 54.37 秒、L4 耗时 21.20 分钟，峰值均约 8.60 GiB；这是单次实测，不保证不同负载或输入的时间/峰值。VM 内存约 15.43 GiB；每次启动仍须通过有效内存预检。L4 多次状态计算与有限差分优化，未来执行仍需预算，不能用 L2 耗时外推。

L4 检查点持久保存；源码无恢复能力，不提供 resume。重新开始建立全新运行目录，旧检查点保留供审计。不复制旧检查点冒充恢复状态。

## 联合分类

必须先获得本次 smoke、optimization、equivalence、source-level 四个完整运行目录，每份 manifest 的 task、PASS/原退出码、源 commit、输入哈希、依赖版本、协议及输出哈希需匹配。允许分阶段运行，不要求同一时间。不能传冻结 JSON 或缺 manifest 的历史文件。

```powershell
./scripts/run-docker.ps1 -Task p14-classify -Image ai4orgchem-runtime:oci-candidate-20261002 `
  -OutputRoot D:\AI4Science\ai4orgchem-runtime-runs\my-reproduction `
  -SmokeRun D:\AI4Science\ai4orgchem-runtime-runs\my-reproduction\SMOKE_RUN `
  -OptimizationRun D:\AI4Science\ai4orgchem-runtime-runs\my-reproduction\OPTIMIZE_RUN `
  -EquivalenceRun D:\AI4Science\ai4orgchem-runtime-runs\my-reproduction\EQUIVALENCE_RUN `
  -SourceLevelRun D:\AI4Science\ai4orgchem-runtime-runs\my-reproduction\FIXED_RUN
```

上游子程序可能在数值资格未通过时返回 0。本轮 Runtime 修订保留真实子程序退出码；对五个带资格门槛的 P14 任务，子程序退出 0 但门槛为 `FAIL`、`UNKNOWN` 或缺失时，Runtime 返回 4，并在 manifest 记录不合格状态。真实子程序非零退出仍保留其错误码。只看子程序 0 不能判定成功。历史镜像内尚未包含该修订时，应同时核对 manifest，不把新行为倒写到旧记录。完整四结果分类曾在本地 Docker 执行，PASS/consistent；该结论限于保存记录的固定协议。

## 独立普通 WSL2 记录

早期独立 WSL2 candidate venv 曾验收原入口 L0—L2 与 STO-3G 等价性；这些记录只属于当时的环境与源码，不授予新增服务原生计算资格。当前[普通 WSL2 原生入口](NATIVE_WSL2_RUNTIME_zh-CN.md)只有只读环境 Check。`validate-wsl2.sh` 的显式 Python/source/output/共享锁参数不安装软件，不读取同级开发仓库；使用者必须自行准备独立候选目录。不要把该历史辅助脚本当成所有服务的原生计算入口。
