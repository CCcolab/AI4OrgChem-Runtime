# W01—W06 本地 CI：工程范围验证

2026-10-05 / LOCAL-CI-W01-W06-1。按当前已部署工作包理解用户的“W01-W0”，完成 W01—W06 本地工程 CI。**受测工程检查全部通过；W05/D2 和 W06/D3 科学验收仍未完成。** Compute 保持关闭，没有分子 SCF、镜像重建、WSLc、远端 CI 或公开操作。

## 实际执行与计数

| 检查 | 实际结果 | 说明 |
|---|---|---|
| 基础工程管线单元测试 | 48 次 PASS | 32 输入/资源/准备/研究资格与简报，4 科学适配器工程，7 旧 runtime，3 进程，2 分类适配 |
| W06 管线单元测试 | 54 次 PASS | 32 上述合同等，15 独立数组参考，7 旧 runtime |
| 合并去重 | **63 项独立用例，102 次执行** | 重复的39项不重复算独立用例；全部日志核对，无失败、错误或跳过 |
| PowerShell 5.1 启动器集成 | 10 个动作 PASS | 四个候选/profile Check、Compute 拒绝、只读 Report、未知字段/资源越界/路径逃逸拒绝、改变几何的旧回执拒绝 |
| W06 容器内 Python 服务 | 3 个动作 PASS | 元数据 Check、Compute BLOCKED/20 且差值 null、Report 保持 Check 字节不变；与 Windows 集成分开计数 |
| 平台探针 | 4 项 PASS | 非 root/只读/断网/输出持久；真实超时、取消和受限 OOM |
| research 元数据守卫 | PASS | 56 AO，16 π AO，8 个 dxz/dyz；无 SCF、网格构建或完整 ERI |
| PowerShell AST/路径 | 7 项 PASS | 安全路径、中文空格和脚本解析；没有执行 WSLc 命令 |

独立数组参考使用 2/3 AO 解析 toy，包括非正交度量和非零 ERI，没有真实分子积分。W06 guard 在测试进程内禁止分子 SCF、网格构建及积分调用。身份、结果正文指纹、空范围登记和必需量失败语义均按本轮实际测试记录判读，不生成真实研究批准。

平台探针超时/取消的137退出与 OOM 的137退出通过实际 OOM 标志区分；OOM 仅在128 MiB受限测试容器中触发。通常工程容器限1 CPU、512 MiB、memory-swap=memory，W06测试上限120秒。没有压满科研宿主或修改 WSL 配置。

## 受测源码与镜像身份

| 对象 | 身份 |
|---|---|
| 当前受测 runtime 提交 | `2dce58cffd5208231772ca1c55ac037bcd0cc9b9` |
| 既有 r3 镜像构建 runtime | `5098775c9cf40468ab92712447a3e5c7b1361a63` |
| 镜像科学源码/适配器 | `cc7437901119e71ef7945a12813c021c383e7648` |
| 复用镜像 ID | `sha256:24f46f33264924e5d3d3bec386298585267c6f30d6e6a0cd0a6486ecf45db93d` |

两套测试均由同一干净 Git 提交导出，归档哈希一致。当前测试源码只读挂载在旧镜像 `/workspace`；Windows 集成使用当前宿主启动器调用旧镜像内服务。W06新增简报/参考由挂载源码管线实际验证，**不能把这些结论写成旧镜像已包含 W06**。报告后续提交不冒充受测提交或镜像构建提交。

## 证据与保留核查

证据目录：`D:\AI4Science\ai4orgchem-runtime-deliveries\20261005-user-molecule-w01-w06-local-ci`。

- `engineering-suite/`：完整命令、stdout/stderr、实际容器状态、PowerShell/平台结果、10次集成输出与清单。
- `w06-suite/`：W06干净源码、54次单元执行、受保护的三项服务操作与只读报告。
- `UNIT_TEST_ID_REVIEW.json`：63项去重 ID、102次执行及无跳过核查。
- `RUN_OUTPUT_HASH_REVIEW.json`：103份运行输出文件哈希/大小核对，容器删除后输出仍保留。
- `INDEPENDENT_STATIC_REVIEW.json`：另一 Codex 子代理只读审查；属于自动静态审查，不是科学或安全认证。
- `POST_TEST_PRESERVATION_REVIEW.json`：已登记原工作区108份runtime文件/5份科学修改及Git状态、591份科学源码、四批旧交付1247项清单和三个历史审阅包均保持原字节/身份。

机器记录见 [本轮合并摘要](../validation/user-molecule/ci-local-w01-w06-20261005.json)。此前 [W01—W05 CI](USER_MOLECULE_CI_20261005_zh-CN.md) 与 [W06 工程验证](USER_MOLECULE_W06_ENGINEERING_zh-CN.md) 保留为历史批次，不覆盖旧失败或旧身份。

## 尚未通过的出口

| 对象 | 当前状态 |
|---|---|
| W05 分子数值/独立普通态与验收驱动、资源峰值标定及冻结预算 | BLOCKED / NOT_EXECUTED；部分驱动仍未实现 |
| W06 每研究profile的完整独立分子参考、两个获审新体系、方法范围/责任及A01—A18研究验收 | BLOCKED / NOT_EXECUTED；范围 NOT_REVIEWED |
| GitHub Actions | 静态审查完成，运行 NOT_EXECUTED；本地测试不替代Ubuntu runner、在线安装、构建、L0/L1和附件上传 |
| WSLc / WSL升级 | BLOCKED / NOT_EXECUTED，继续暂停 |
| 镜像分发 | BLOCKED；本轮没有新镜像或分发审查 |
| 源码公开、推送、正式标签与Release | 未获本轮授权，NOT_EXECUTED |

现有workflow未修改，无镜像推送、正式标签或Release步骤；最小依赖job未来匹配32项合同/研究单测，不包含独立数组参考、未公开科学适配器或Windows本地验收。测试通过不冻结科学阈值或批准研究范围。原L3/L4未重算；L4可以保存检查点，但不支持恢复运行。
