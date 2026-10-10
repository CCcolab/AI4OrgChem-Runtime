> 当前公开阅读节选。原始历史材料已按原字节保存在本地归档；本文件不是原件，不能用于原始哈希验收，也不把旧验收转移至当前代码。
> 原件 Git 提交：eb65b4586c83637569f6359814338c1292948861；SHA-256：dd150e37dfed1f59416ec5f203f52debb9fd5596bafc278c5ed7daac0d8cf30e。

# W01—W05 本地 CI 测试与远端范围


## 1. 实际测试范围

| 工作包 | 本轮实际检查 | 结论及边界 |
|---|---|---|
| W01 | 原 runtime 108 份文件、原科学工作区 5 份已改文件和 Git 状态；独立科学包 591 份文件；旧交付 145 项与 W05 准备 100 项记录、三份历史 ZIP | 记录范围内字节/状态保持，PASS；不是全盘安全审计 |
| W02 | 15 项输入/资源单元测试；未知字段、非有限值、路径/符号链接、资源限额、组映射等；实际失败退出 10 | 工程合同 PASS；碰撞/条件数/gap 科学判据仍未闭合 |
| W03 | 4 项适配器单元测试；pilot inspect、Compute 禁用、非有限诊断及必需门禁；research 守卫 inspect | 元数据/禁用门禁 PASS；新分子能量与独立数值参考 NOT_EXECUTED |
| W04 | 12 项旧封装低成本回归；PowerShell AST/路径 7 项检查；PS5.1→PS7 启动器；隔离/超时/取消/OOM 四探针 | 受测工程范围 PASS；本轮复用原镜像，不是新构建验收 |
| W05 | 7 项候选输入/配置快照/来源/预算/禁用状态合同测试；乙烯、丁二烯两个 profile 的四次实际 Check | 准备合同 PASS；数值验收、资源峰值校准、方法范围审阅仍未执行 |

合计 **38 项单元测试**（15+7+4+12）、**10 个启动器集成用例**、**4 个平台探针**，另有 research 守卫和 PowerShell AST/路径检查。数量按各类分别登记，不能相加成“科学计算通过数”。

十个集成用例：四次 Check；禁用 Compute（20）；只读 Report（0）；未知字段、宿主资源越界、路径越界（各10）；变更几何后使用旧收据（20）。宿主资源/路径错误在创建容器前拒绝。Compute 的比较量保持 null，numerical_status=NOT_EXECUTED。

平台检查实际验证非 root 10001、输入/软件只读、network=none、受限 CPU/内存及容器删除后输出保留。超时、取消均为实际退出137且 OOMKilled=false；受限 OOM 为137且 OOMKilled=true。不能仅凭137推断 OOM。探针的128 MiB和 Check 的512 MiB是工程测试限额，不是科学峰值校准数据。

research 四碳守卫实际检查56 nAO、16 π AO、8 个 xz/yz d π AO；SCF、grid build、完整及逐壳 ERI 调用受守卫禁止。四份分子请求的 nAO 为14/36/26/68，资格均为 false。

## 2. 身份与留存

| 对象 | 实际身份 |
|---|---|
| 成功 CI 受测提交及宿主启动器基线 | `c671025e2a2933ed26e9406ee4b878f1163c443c` |
| 镜像构建 runtime | `5098775c9cf40468ab92712447a3e5c7b1361a63` |
| 科学源码/适配器 | `cc7437901119e71ef7945a12813c021c383e7648` |
| 复用镜像 | `sha256:24f46f33264924e5d3d3bec386298585267c6f30d6e6a0cd0a6486ecf45db93d` |

容器内 runtime/测试从受测提交的干净 Git 归档只读挂载；科学适配器来自固定镜像。宿主脚本的实际工作字节另由 BASELINE 与 host-execution 登记。后续本报告提交不冒充受测提交或镜像构建提交。

证据根目录：`D:\AI4Science\ai4orgchem-runtime-deliveries\20261005-user-molecule-ci\`。attempt-1 保留失败；attempt-2 保存通过的命令、stdout/stderr、实际容器 inspect、运行清单、输入快照和输出。EVIDENCE_AND_PRESERVATION_REVIEW.json 核对90份新输出及原交付字节；最终 Git/归档备份身份另在 LOCAL_FINAL_DELIVERY.json。

机器可读摘要：[ci-local-20261005.json](../validation/user-molecule/ci-local-20261005.public.json)。测试代码、工作字节、归档和执行记录分别有哈希，不混用 Windows CRLF、Git LF 与镜像身份。

## 3. 发现、修正与远端 CI 边界

原 workflow 对 `/tests` 广泛 discover，但旧 Dockerfile 不提供新增测试所需 schema、profile、例子和未公开适配器；这属于静态发现，未将其称为远端实际失败。已将旧封装测试收窄为 test_runtime/test_process/test_classifier_adapter，新增 user-molecule-contracts job。

新 job 在独立虚拟环境使用 [六项最小依赖锁](../locks/requirements-user-molecule-ci.txt)，版本与 wheel 哈希均为原完整依赖锁的精确子集，要求 CPython3.12/linux-amd64。其22项输入/资源/准备合同测试已在本地干净 Linux 容器、独立环境中通过，依赖从既有 wheel 离线安装，未改宿主科研 Python。

本地首轮在默认 noexec `/tmp` 创建虚拟环境时无法执行复制的 Python，退出1。修正仅为测试环境增加独立 `/ci-env` 可执行 tmpfs；生产启动器、容器安全设置、科学规则和容差不变。第二轮全部通过；旧失败和当时提交身份均保留。

workflow YAML 已用锁定 PyYAML 解析，五段 shell 经 Git Bash `-n` 语法检查，权限仍 contents:read，Actions 使用完整提交 SHA；没有镜像推送、正式标签、Release 或 L3/L4 步骤。附件保留7天，首次公开推送可能触发两项 job并产生公开可读日志/附件，公开范围仍需确认。

**GitHub Actions 的 Ubuntu runner、在线依赖下载、实际构建、L0/L1步骤及 upload-artifact 尚未执行。** 本地测试不替代这些记录。新远端 job只覆盖22项合同测试；未公开科学适配器、Windows/Docker监督和独立数值验收不在其范围。尚未使用 act，也未推送或触发远端 workflow。

## 4. 如何在本机重复

使用现有 Python3.12、Docker、PowerShell7.3+、固定上游源码和已下载 wheel，指定新的输出目录。具体本机命令示例：

```powershell
$python = 'C:\Users\chenx\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$ps7 = 'C:\Users\chenx\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe'
Set-Location D:\AI4Science\ai4orgchem-runtime-workspaces\user-molecule\runtime
& $python .\scripts\test-user-molecule-ci.py `
  --output-root 'D:\AI4Science\ai4orgchem-runtime-deliveries\user-molecule-ci-new-run' `
  --legacy-source 'D:\AI4Science\tmp\runtime-source-v032-20261002' `
  --wheels 'D:\AI4Science\ai4orgchem-runtime-deliveries\20261005-user-molecule-w01-w04\clean-build-context-r3\build-inputs\wheels' `
  --powershell7 $ps7
```
