# 2026-10-02 候选环境实施与验证报告

这是实际记录，不是镜像/WSLc 验收完成声明。原项目工作区、科学源码、协议与冻结证据未修改；未推送、发布镜像、打正式标签或发布 Release。

## 阶段状态

| 阶段 | 状态 | 依据 |
|---|---|---|
| A 来源/入口/平台核查 | PASS | 固定标签与 SHA、归档与 588 文件哈希、源码审查和平台工具记录 |
| B 构建工程与依赖锁 | BLOCKED（实现已交付） | 17 wheel 哈希锁、基础摘要和 Dockerfile 已形成；无运行中容器引擎，未构建镜像 |
| C 任务封装与持久输出 | BLOCKED（WSL2 实跑子集 PASS） | L0—L2/等价性成功；Windows WSLc 启动器尚无实机验收 |
| D WSL2/WSLc 对照 | BLOCKED | WSL2 有记录，WSLc 工具版本条件不足，相关测试 NOT_EXECUTED |
| E L3/L4/本次联合分类 | NOT_EXECUTED | 接口完成，耗时预算未知，高成本任务未授权预算/未启动 |
| F 候选文档与发布材料 | 候选材料已交付 | 发布就绪仍受 B—D 阻塞；不是正式发布 |

## 已执行结果

独立候选 Python 3.12.13，NumPy 2.5.1、SciPy 1.18.0、PySCF 2.14.0；完整 17 依赖见锁和运行 manifest。源 commit `28511f3d84fa65707a107cde1e8121a7b4334ecb`，上游包版本 `0.1.0`。最终 LF 依赖锁摘要 `a8dbe44d12930427ca1f377b17eba3fcdb17b6dd922737884b3b77d0d9c4ea71`。首次记录摘要 `7145fe7b4e9e0444920d4f3ba86d0a22c58fee9c4248a7b1de23e4e68bf37c6b` 对应 Windows CRLF；提交前只归一化锁文件换行以保证干净检出稳定，版本与 wheel 哈希没有改变。

| 项目 | 实测 |
|---|---|
| pip check | PASS：独立 venv 离线哈希安装 |
| runtime 单元/过程测试 | PASS：9 项初测；后续新增项以 summary.json 为准 |
| L0 | PASS：十四项、P12、导航、P14 底层证据全部核验 |
| L1 | PASS：三份原测试共 11 项 |
| L2 | PASS：15/15 自身数值资格，约 12.6 秒，峰值 RSS 546.15 MiB |
| STO-3G 等价性 | PASS；第一次源码缺失预检 FAIL 保留 |
| 源码/证据 | 只读、任务前后 588 个文件哈希校验一致 |
| 输出 | 与源码目录分离，在 Windows 宿主持久目录保留 |

L2 技术端点 `26.471605327369403 kcal/mol`，固定提交同层级冻结值 `26.471605327226722 kcal/mol`，绝对差 `1.4268053405430692e-10 kcal/mol`。这是 STO-3G 技术对照，不是 L3 的 67.086899 端点复算，不能作科学定判。L3/L4 残差 UNKNOWN，未计算；WSL2/WSLc 相互残差 UNKNOWN。

原始日志目录：`D:\AI4Science\ai4orgchem-runtime-runs\20261002-wsl2`。首次三个运行 ID：`20261002T104043Z-evidence-ab57bf8dbabf`、`20261002T104045Z-core-tests-6b8796c8ba75`、`20261002T104047Z-p14-smoke-afbe6f3bce33`。这些在首次提交前执行，runtime_commit 为 UNKNOWN，未伪补写。后续已识别提交的执行记录另行汇总，不覆盖历史 manifest。

等价性首次预检失败 ID `20261002T104545Z-p14-equivalence-126b8b2e7cd6`：旧 `/tmp/...` 源码目录已不存在，588 文件缺失，未进入科学计算。重新获取同一固定归档到新持久 Linux 目录后运行 `20261002T104918Z-p14-equivalence-26d968497afa` 通过。没有修改哈希规则、数值规则或容差。

## 平台阻塞与限制

WSL 安装包 2.3.26.0，Windows AMD64；官方核查日要求 WSL 2.9.3+ 方有 WSLc，本机 wslc 与别名不可访问且已知安装路径不存在。WSLc 平台验收 BLOCKED、全部相关运行 NOT_EXECUTED。

Docker Desktop 已安装但未启动：无相关后台进程，两个引擎管道都不存在；沙箱外 status 仍报告未运行。OCI 构建/容器验收 BLOCKED、实际构建测试 NOT_EXECUTED。未启动 Desktop、更新 WSL、启用系统功能、修改全局配置或重启。具体恢复步骤见 INSTALL_zh-CN.md。

源码归档下载和独立提取证明不依赖同级开发仓库；Docker 干净构建、容器非 root/挂载/离线、目标 WSLc 信号/资源/中文路径必须待工具恢复后实测。PowerShell AST 与候选参数/路径防护测试不能替代实际原生命令运行。

L4 写检查点但不能 resume；过程测试证明封装中断保留已写检查点，尚无完整 L4 实跑中断证明。分类器路径适配已实现；本次四份新科学结果未齐，联合分类 NOT_EXECUTED，缺输入拒绝已经测试。

镜像候选摘要 UNKNOWN（尚无镜像）；基础镜像摘要不是最终镜像摘要。没有“B—D 全部完成”或“WSLc 已支持”的声明。
