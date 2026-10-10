# 原生 WSL2 Runtime：只读 Check 入口

`scripts/check-wsl2-runtime.py` 现在支持检查普通 WSL2 发行版和指定 Python 环境。它只读取标准库、包 metadata、`/proc`、cgroup 计数器，以及显式指定的来源文件 SHA256。不会导入原科研脚本、导入 PySCF/numpy/scipy 的科学模块或启动 SCF、F 构建、优化。既有 P12 PASS 保持原判定，此入口不重算、不新增 P12 内存准入或探针。

这不是原生 Compute 后端。`--action Compute` 在发现或启动 WSL 进程前直接拒绝；结果始终有 `compute_enabled: false`、`image_id: null`、`native_p12_compute: NOT_IMPLEMENTED` 和 `scientific_acceptance: NOT_EXECUTED`。原生环境身份与 Docker 映像资格分开记录，不可用原生 Check 的 PASS 替代旧 Docker 验收或 P12 科学验收。

## 本轮使用

在 Windows Runtime 仓库目录执行（主机 Python 只需标准库）：

```powershell
$NativeCheckRecord = Join-Path 'D:\AI4Science\ai4orgchem-runtime-runs\native-wsl2' ('check-' + [guid]::NewGuid().ToString('N'))
python -I -B scripts/check-wsl2-runtime.py --action Check --distribution Ubuntu-24.04 --python /home/cascade/micromamba/envs/ai4orgchem/bin/python --record-dir $NativeCheckRecord
```

记录目录必须是新的绝对主机路径，入口不会覆盖已有目录。省略 `--record-dir` 仅输出 JSON。需要来源身份时，可显式增加 `--source-file /mnt/d/AI4Science/AI4OrgChem/src/ai4orgchem/qm/p12_source2011_rks.py` 等参数；这只读取文件哈希，不运行P12。参数可重复，不扫描来源目录或凭证。环境默认值只适用于当前机器，可通过 argv 指定。全部进程参数以 argv 传递，不通过 shell 插值；worker 内容通过 stdin 传递。本轮验收记录独立保存在文末的新交付根，示例使用另一个新运行目录。

Check 首先读取 WSL 版本、发行版版本及正在运行的列表，并记录检查前运行状态。随后正常调用指定发行版的 `--exec`，以 `PYTHONNOUSERSITE=1`、`-I -B` 运行独立 stdlib worker；WSL 可能按其正常行为启动已停止的指定发行版。加 `--require-running` 可在发行版未运行时拒绝。入口不会关闭任何发行版。单次命令超时默认 30 秒，可设大于 0 且不超过 60 秒，超时或不合法 JSON、缺失环境/包、root 用户、身份不匹配均失败关闭。不会安装、升级、下载、改变 WSL 全局配置、原环境、全局设置或旧 launcher。

## 身份与资源观测的范围

环境指纹包含发行版、WSL 版本文本、kernel、Python executable/prefix/version、七项包 metadata 版本及哈希、显式来源哈希、新入口/worker 哈希。这是观测时身份，尚不是不可变环境快照。报告显示 UID、PID 1、逻辑/亲和 CPU、物理内存与 swap、当前 cgroup 内存层级原始计数器，以及已存在的进程控制工具。工具存在不证明隔离或资源限制可实施。

原生 WSL2 不自动套用 Docker 的 14 GiB、高成本 cgroup、16 GiB 主机、15 GiB guest 门槛；也不降低或修改旧合同。内存、swap 与 cgroup 在本入口仅为平台观测，不对已通过的 P12 新增门槛，不授权计算，不得将 `MemAvailable` 当成任务预算。

## 开放原生 P12 Compute 前必须完成的工程准入

1. **只读快照与来源映射**：为原科研环境建立不会修改它的候选快照/任务封装；固定环境包完整身份、原 P12 脚本及其实际依赖的来源映射，核验与冻结 107 文件合同的关系。Check 的两份脚本哈希不能替代全依赖映射。
2. **任务输入输出与隔离**：只读输入、明确输出目录、写入边界及网络边界需由原生任务封装实施和验收；非 root、`-I -B` 与工具存在不等于旧 `/output` 挂载、lo-only 和 UID 10001 隔离。不得为此自动安装 bwrap、使用 sudo 或改变原环境。
3. **进程生命周期**：明确任务进程组/cgroup ownership、启动日志、stdout/stderr 持久化、超时、用户取消、TERM→KILL、后代进程清理、崩溃恢复和完成/失败终态；用零 QM 故障注入证明不会残留进程或损坏来源。
4. **原生资源分档**：结合实际 WSL2 可用内存、swap、CPU/亲和/cgroup 委派能力制定独立的 native profiles；定义预算、预检、运行时限制和峰值证据。原环境长期 P12 成功运行是有价值的基线，但不能替代新封装的资源合同。
5. **科学验收**：上述工程门通过后，再取得针对原生候选任务的计算授权，依次做低成本对照与目标 P12 来源、参数、方法和结果验收。此次 0 QM Check 不提供能量、轨道或优化结论。

当前可用范围是普通 WSL2 **只读环境 Check**。原生 P12 任务封装、隔离、日志终止、资源分档和科学验收尚未实现/未执行。原科研环境和 WSL 全局设置保持；该入口不要求升级。源码与静态指南已经公开，镜像分发仍受独立材料和授权条件约束。

## 零 QM 测试

```powershell
python -I -B -m unittest discover -s tests -p test_native_wsl2_check.py -v
```

13 项模拟测试覆盖 Compute 提前拒绝、缺 WSL、缺环境、超时、非法/重复/非有限 JSON、可选未运行发行版拒绝、正常 Check 启动状态、包/身份/UID/隔离 flags 失败、中文/空格/shell 元字符 argv、UTF-16 输出和记录目录防覆盖。测试不调用 WSL 或科学库。

## 2026-10-09 零 QM 验收记录

本轮新记录根：`D:\AI4Science\ai4orgchem-runtime-deliveries\20261009-six-issue-remediation\native-wsl2`。

| 记录 | 结果 | 范围 |
| --- | --- | --- |
| `tests-001.txt` | 13/13 PASS，exit 0 | stdlib 模拟故障测试，无 WSL/科学计算 |
| `check-001/check.json` | FAIL，`distribution_not_running` | 首版附加运行状态门槛检测到 Ubuntu-24.04 已停止；保留原记录 |
| `check-002/check.json` | PASS，exit 0 | 显式原生 Check 正常调用 stdlib worker；启动前 false、完成后 true，0 QM |
| `compute-refused-001/check.json` | REFUSED，exit 2 | Compute 在发现或启动 WSL 前拒绝，0 QM |

实际观测为 WSL 2.3.26.0、WSL2 kernel 5.15.167.4、UID 1000、Python 3.12.13；七项包 metadata 版本均在 JSON 中记录。两个显式 P12 来源文件仅被读取哈希。`check-002` 的平台资源数据不对已通过的 P12 新增门槛或改判。该次 Check 没有升级、依赖安装、环境修改、原科研脚本导入或 SCF/F/优化。
