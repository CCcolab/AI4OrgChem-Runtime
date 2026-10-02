# WSLc 能力与实测矩阵

本轮收尾决定（2026-10-02）：用户为优先保护原 AI4OrgChem 科研运行环境，暂停 WSL 升级和 WSLc 实机验收。WSLc 继续 BLOCKED / NOT_EXECUTED；后续恢复须明确授权。本地 Docker OCI 已验证范围保留，不替代 WSLc 支持声明。

2026-10-02 本机：Windows 10.0.26300.9550（wsl --version 输出）、AMD64、WSL 2.3.26.0、内核 5.15.167.4-1。Ubuntu-24.04 可执行。PATH 中未发现 wslc.exe，无法读取本机 wslc --help；**WSLc 平台验收 BLOCKED，各项测试 NOT_EXECUTED**。用户授权启动已有 Docker Desktop 4.78.0 后，Docker 29.5.3 Linux/amd64 引擎可用；**本地 OCI 干净构建、L0—L2/等价性与本轮安全/持久性验收 PASS**。未更新 WSL、修改全局配置、重启或安装其他引擎。下表专门记录 WSLc，仍全部 NOT_EXECUTED。

微软[官方入门文档](https://learn.microsoft.com/en-us/windows/wsl/tutorials/wsl-containers)与[概览](https://learn.microsoft.com/en-us/windows/wsl/wsl-container)在核查日列出 WSL 2.9.3+ 前提；该数字来自文档，不是本项目实测最低版本。[3.0.1 发布记录](https://github.com/microsoft/WSL/releases/tag/3.0.1)对应 2026-09-29 GA。官方[GA 公告](https://blogs.windows.com/windowsdeveloper/2026/09/29/wsl-containers-now-generally-available/)说明 --mount、构建运行与存储路径配置；Compose 仍列为后续计划。本项目不依赖 Compose。

| 能力 | 官方/源码依据 | 本机实测 | 验收入口 |
|---|---|---|---|
| build、OCI 镜像运行 | 官方入门示例 | NOT_EXECUTED | build-wslc.ps1；实际镜像检查 |
| image inspect、镜像身份 | 官方入门检查命令 | NOT_EXECUTED | 启动器检查源提交/锁/非 root 标签 |
| 拉取、导入、GHCR | 官方容器 CLI 具相关能力；目标 GHCR 尚无发布 | NOT_EXECUTED | probe-wslc.ps1 + 目标主机独立记录；不能把 Docker 结果替代 |
| --mount、只读挂载 | GA 公告；精确语法需本机 help/实跑 | NOT_EXECUTED | acceptance-wslc.ps1 |
| 空格/中文 Windows 路径 | 无本机证明 | NOT_EXECUTED | acceptance 脚本实际路径 |
| 非 root、源码/证据只读 | OCI USER/文件权限候选实现 | NOT_EXECUTED | runtime.platform_probe |
| 删除容器后的结果保留 | 受控 bind mount 候选 | NOT_EXECUTED | acceptance 实测 --rm 后文件 |
| 退出码/日志 | 启动器传递原退出码 | NOT_EXECUTED | 子程序退出 37 探针与 L0—L2 |
| 信号、停止、检查点保留 | container stop 文档；真实语义待测 | NOT_EXECUTED | acceptance 合成任务停止/删除探针；不等于 L4 已验证 |
| 内存限制/cgroup | 实际参数先看 help | NOT_EXECUTED | help 有 --memory 才执行低内存拒绝探针 |
| CPU 配额/线程 | 不照搬 Docker 参数 | NOT_EXECUTED | 本机 help 与实际 cgroup 记录，尚需目标主机核查 |
| 会话资源/存储配置 | GA 公告 | NOT_EXECUTED | 目标主机 system info 与配置记录；不自动更改 |

启动器是**候选适配**，PowerShell 语法及路径逻辑可本地检查，但不等于经过 WSLc 验收。--mount 格式以官方宣布的能力为候选，启动前核查 help；仍须真实运行验证 JSON inspect、挂载权限和信号语义。

普通 WSL2 采用 /mnt/d 映射，仅用于 WSL2 独立验收；Windows 启动器向 WSLc 传递 Windows 宿主路径，不将 /mnt/d 当作容器路径。

同一 Windows 用户的容器启动器使用宿主 FileShare.None 锁，所有相关容器同时绑定同一 /locks；Linux 入口使用 flock。不同用户、不同锁目录、手工启动或与未受 runtime 管理的科学任务之间不保证统一排他；不能因此宣称全主机所有进程都已受控。用户须保持中高内存任务串行。

## Docker OCI 独立支持矩阵（2026-10-02）

| 项目 | 本地 Docker 候选 |
|---|---|
| 干净构建、镜像身份、L0—L2、STO-3G 等价性 | PASS |
| 非 root UID/GID 10001、源码/证据禁止写入、588 文件哈希 | PASS |
| --network none、中文/空格 bind 路径 | PASS |
| 退出 0/37、256 MiB 低内存预检拒绝 | PASS |
| --rm 后四份 manifest 与全部输出哈希 | PASS |
| 封装测试 | PASS，12 项，无跳过；含合成中断保留测试 |
| Docker stop 信号语义、完整 L4 中断 | NOT_EXECUTED |
| L3 p14-fixed | PASS，后续授权实跑 12/12 anchor 资格，见 l3-summary.json |
| L4 p14-optimize | PASS，18/18 优化资格，见 l4-summary.json |
| 四份新输入联合分类 | PASS：consistent，见 classification-summary.json |

本地镜像与记录见 [OCI 汇总](../validation/oci-summary.json)。L4 可保存检查点，但不支持恢复运行。
