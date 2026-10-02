# 固定源码与历史环境审查

后续 2026-10-03 交付审查已完成，实际镜像第三方许可和对应源码义务仍有 UNKNOWN/未完成项，详见 LICENSE_REVIEW_zh-CN.md；当前统一状态见 validation/final-delivery-status.json。下文保留阶段 A 的来源调查和已补充的结果。

审查日期：2026-10-02（Asia/Tokyo）。阶段 A 已完成来源解析、入口审查及本机平台条件核查；缺失平台明确记录，不推断支持。

## 仓库边界及来源

新目录 `D:\AI4Science\ai4orgchem-runtime` 原来仅含用户实施方案，已初始化独立 main 仓库。父目录不在 Git 管理下。原项目有 5 个修改的跟踪文件及大量未跟踪内容；均未修改、切换、重置、清理或加入新仓库。

远端 `git ls-remote` 确认 annotated tag `v0.3.2`，标签对象为 `afd91ea6ec6847b329ee75a7b20ed564560d9460`，解析后提交为 `28511f3d84fa65707a107cde1e8121a7b4334ecb`。独立 detached clone 用于审查，固定提交归档用于构建与实跑。`locks/source.lock.json` 记录归档 SHA-256；`locks/source-files.sha256.json` 记录全部 588 个文件哈希。构建不读取同级 AI4OrgChem 或其未提交内容。

核对的[固定提交](https://github.com/CCcolab/AI4OrgChem/tree/28511f3d84fa65707a107cde1e8121a7b4334ecb)包含 README（中英）、AUTHORS、Apache-2.0 LICENSE、NOTICE、典型程序指南、运行手册、平台矩阵、environment.yml、software/pyproject.toml、目标脚本/测试、P14 配置与输入/冻结结果、P12 账本、公开发布验证器与工作流。公开精选包没有开发仓库的 AGENTS.md、PROJECT_STATUS.md 或 configs/project.yaml；原开发目录约定已读取，仅用于边界调查。当前 runtime 不继承原项目未开放的科学/训练许可，也不修改其 Gate 0 状态。

## 实际任务路径

以下路径相对于固定提交公开包根目录；全部脚本在 `software/scripts/` 下。

| task | 上游文件 | 实际封装 |
|---|---|---|
| evidence | validate_public_evidence.py、validate_p12_evidence.py、validate_evidence_navigation.py | 逐项检查，并额外运行 validate_p14_evidence.py；原退出码保留 |
| core-tests | software/tests/test_p09_conditional_scf.py、test_p09_energy_assembly.py、test_p09_eri_mask.py | 原测试，禁止 pytest/字节码缓存写入源码 |
| p14-smoke | run_p14_benzotricyclobutadiene_smoke.py | 显式 --output、--report、--protocol、--classes |
| p14-equivalence | validate_p14_memory_controlled_conditional_scf.py | 同样显式输出；STO-3G 两实现等价性 |
| p14-fixed | run_p14_benzotricyclobutadiene_source_level_fixed_geometry.py | 显式输出与 --checkpoint |
| p14-optimize | run_p14_benzotricyclobutadiene_production_optimization.py | 显式输出与 --checkpoint；无恢复接口 |
| p14-classify | classify_p14_strained_aromatic_pi_distortivity.py | 必须提供四个已完成的 runtime 运行目录；无冻结输入回退 |

## 路径与行为风险

脚本用 `Path(__file__).resolve().parents[2]` 定位根目录，默认写根下 runs/reproduction。改变工作目录或单个环境变量不能重定向这些输出。本实现使用已有显式输出参数，不修改科学脚本。

分类器还对输入执行 `relative_to(ROOT)`。封装因此建立本次运行的 classifier-view：只读 configs/evidence 链接和四份经过运行身份、协议、依赖、输出哈希检查的结果副本；仅在独立子程序中设置分类器模块的 ROOT 路径，并显式传递全部输入/输出参数。数值计算、分类规则、容差、协议及冻结记录保持上游原样。后续已用完整四份新结果完成本机 Docker 端到端分类，PASS/consistent；限固定协议范围，WSLc 尚未验收。

上游分类器即使得到 PARTIAL_OR_FAIL 也返回 0。manifest 分别记录 process_exit_code、numerical_qualification、scientific_comparison；不将退出 0 当作科学资格通过。

L3 脚本读取 `/proc/meminfo`，源码阈值为 13000 MiB。L4 源码也引用该阈值，但指南要求 13 GiB：runtime 对 L4 采用指南更严格的 13 GiB（13312 MiB），对 L3 保持 13000 MiB，并在上游预检前检查 cgroup 剩余内存。两者不互换，也不改写上游。检查点是过程记录，不是完整可恢复 SCF/优化器状态；源码无读取检查点或 resume 参数。

P14 smoke/pilot 的结果字段 `thread_count=8` 为静态字段，脚本没有实际调用 `lib.num_threads(8)`。封装在导入科学库前设置 OMP/BLAS 线程变量，以 manifest 的实际请求/约束记录为准。CPU 配额与线程数分别处理；不把静态字段当作实测线程计数。

## 依赖版本来源

公开环境是兼容范围：Python 3.12、NumPy >=2,<3、SciPy >=1.14,<2、PySCF >=2.8,<3。P14 协议快照记录 Python 3.12.13 / NumPy 2.5.1 / PySCF 2.14.0，并明确 `project_environment_snapshot_not_embedded_in_original_per_job_record`。历史 conda explicit lock 日期 2026-08-12，不含 pip PySCF，不能代表后续每个作业。

只读现有 ai4orgchem 环境元数据取得 SciPy 1.18.0、h5py 3.16.0、PyYAML 6.0.3、jsonschema 4.26.0、setuptools 78.1.0；pytest 元数据 UNKNOWN，因此选择 pytest 8.4.2 新候选。PyPI 解析并下载 17 个 linux/amd64 CPython 3.12 wheel，全部精确锁定 SHA-256，离线安装在新 venv，pip check 通过。其身份为新候选，不是完整历史复刻。

候选基础镜像选择官方 Python 3.12.13-slim-bookworm，而非 Ubuntu+micromamba，以固定 CPython、避开修改原有环境，并通过相同 wheel 锁验证 API。Docker Hub manifest 索引与 amd64 子摘要已核对，记录在 base-image.lock.json。Debian 基础与已验收 Ubuntu WSL2 不相同，镜像仍需实际构建和运行，不宣称平台等价。

## 冻结参考与判据

P14 固定几何冻结端点 67.086899 kcal/mol、生产优化 67.679719 kcal/mol、dΔr 0.172204 Å。最终分类比较对象是协议的原著锚点 67.08 kcal/mol 和 0.179 Å，能量容差 5.0 kcal/mol、键长响应容差 0.03 Å；冻结参考残差与原著比较残差必须分开。runtime 不另定容差。

## 许可证与剩余风险

保留上游 LICENSE/NOTICE/AUTHORS；runtime 使用 Apache-2.0。依赖元数据和下载身份见 wheels.lock.json，安装的 dist-info 保留第三方许可。NumPy/SciPy/PySCF/h5py 等所带数值库许可须随镜像保留；镜像已构建且 L0—L2/等价性动态库运行通过；完整基础组件/动态链接许可证清单仍待发布前专项核查。原著 Figshare 的许可不用于覆盖代码许可。

已执行：独立固定归档获取、588 文件校验、候选依赖离线安装、WSL2 L0—L2 与 STO-3G 等价性。等价性首次预检发现 /tmp 旧源码目录已不存在，588 文件缺失、无额外文件；保留 FAIL，并改用新独立 Linux 持久目录获取同一固定归档后实跑 PASS。只观测到 /tmp 目录缺失，不把具体清理机制作为已证实原因。

OCI 已从干净 runtime 仓库构建，不引用同级原项目；非 root/只读/离线及 L0—L2/等价性验收 PASS。后续 Docker L3/L4 与完整本次输入联合分类均已通过；未执行 WSLc 平台对照。WSLc 缺口继续阻塞 C/D 的目标平台验收。
