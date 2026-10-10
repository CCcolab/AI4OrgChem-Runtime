> 当前公开阅读节选。原始历史材料已按原字节保存在本地归档；本文件不是原件，不能用于原始哈希验收，也不把旧验收转移至当前代码。
> 原件 Git 提交：eb65b4586c83637569f6359814338c1292948861；SHA-256：1b812c4cad70a58db045cfef530c62dd6e5d9a96b81d827f773c387021ecae27。

# 2026-10-09 源码安装验收

三个安装缺口已在本轮限定范围内闭合：公开来源准备输入、独立安装身份、干净目录安装与小任务运行。验收是在已有 Windows/Docker 引擎上进行，未重置引擎或删除旧镜像；不等同于全新机器、所有平台或所有科学任务的认证。

## 实际身份

受测 Runtime 提交：`59f576c5a11f7192d0425765611a49369c6f561a`。后续验收文档提交不冒充镜像构建提交。

新镜像：`sha256:a4086d916101ab16650a878971361b5ee6e4e7f9e62b7d750f672825b6bbe96f`。

新基础环境：`sha256:d8cfae924e225782eec07ac494401a4090f473793fb850fc10af2ea1080bdebd`，直接基于固定公开 Python 3.12.13 镜像，不使用旧私有 Runtime 基础镜像。安装时仍需 Docker 引擎与网络，计算时禁用网络。

科学内容为公开基线 `28511f3d84fa65707a107cde1e8121a7b4334ecb` 的 588 文件，加本地适配来源 `cc7437901119e71ef7945a12813c021c383e7648` 的三个原字节文件。共 591 文件逐项校验一致；新归档 SHA-256 为 `a2d1b18d22c363893b53801a6a7e3f6aa4e7bccc18de119b4b2bd9e62e0ffed7`。该过程重建文件内容，没有重建或冒充 Git commit 对象，也没有把适配提交命名为 v0.3.2。

Python 输入为官方 PyPI 的 21 wheel＋1 geomeTRIC 源码包，22 项版本与哈希固定；镜像包含这 22 项及基础镜像中的 pip，共 23 个 distribution。geomeTRIC 新生成 wheel SHA-256：`4476a95744dd70c9c930efcb33f37d28a9e78359d6e443a697275e841c709174`，作为本次构建输出独立记录。系统 Git 的实际版本已记录，Debian 软件源未固定到不可变快照，因此不作位级可重复声明。

## 已完成检查

| 检查 | 本轮结果 | 范围 |
|---|---|---|
| 源码 ZIP 的 Git commit/tree/blob 证明、CRC、完整构建目录 | PASS | 原始 Git blob 导出，拒绝未登记代码；保留明确 HC 目录变换 |
| 默认安装命令自行公开下载 | PASS | 不传外部输入目录；得到的全部构建文件摘要与受测构建一致 |
| 公开来源基础环境与 Runtime 构建 | PASS | 新本地候选，不推送镜像 |
| 四类服务登记 | ENGINEERING_VALIDATED | 普通单点、固定案例、协议案例、高成本案例；登记科学状态均 UNKNOWN |
| 安装工程测试 | 45 PASS | 源码准备、依赖哈希、身份绑定、任务范围及路径保护 |
| 新镜像水分子普通 RHF 单点 | PASS_SCOPED_MOLECULAR_SINGLE_POINT | 原 RHF/6-31G(d) 小体系协议；1 次 SCF、0 次条件核 |
| P02 统计、P13 图规则账本 | PASS_SCOPED_FIXED_CASE | 两个固定任务，不接受自选分子 |
| P07 协议账本 | PASS_SCOPED_PROTOCOL_CASE | ledger；不开放 P07 live |
| 原用户分子 Check 使用新镜像 | COMPLETED、退出 0 | 原请求格式；条件 Compute 继续 BLOCKED |
| 非 root、只读根文件系统、断网、退出码与输出留存 | PASS | 四个受测任务均检查实际容器；删除后复核 196 项输出哈希 |

通过 `run-installed-runtime.py` 执行的任务保存 `INSTALLATION_RECORD.json`、`INSTALLATION_PREFLIGHT.json` 和原任务证据。原用户分子 Check 另以原格式保存镜像身份、预检及运行清单。新镜像的安装 ID 与历史验收记录区分，标签被重指向、来源或依赖不同、越范围任务均拒绝。原预算、科学规则、数值门槛和清理合同继续生效。

## 保留的限制

P01 与 P03—P10 live、P11/P12 在新镜像上的科学重放均为 `NOT_EXECUTED`；本轮没有重复已通过的 P12，也没有 P12 实际内存探测。原 N12-G 的 PASS 保留，不因安装验收重新打开。登记高成本服务只证明其身份与源码对应，不能替代数值验收。

用户自选分子的首版普通 RHF 服务保留既有元素、总电荷、自旋、原子数和 AO 数范围；条件态用户 Compute 保持 `BLOCKED`。通用优化、DFT、开壳层、扫描及 Native Compute 未因本轮安装交付新增支持。P01—P14 历史导航继续只读，缺失原始材料如实显示，不算重新计算。


全新机器或其他主机验收、进一步篡改回归、自动安装主机工具及无网络安装包可作为后续增强，不是本轮已完成项目，也不替代当前环境前提。

## 记录位置

机器摘要：[acceptance-20261009.json](../validation/clean-installation/acceptance-20261009.public.json)。使用入口：[源码安装指南](SOURCE_INSTALLATION_zh-CN.md)。

完整本地证据在 `D:\AI4Science\ai4orgchem-runtime-deliveries\20261009-clean-installation`：保留首次导出拒绝、第二次 BuildKit 引用失败、最终受限验收、默认公开下载及组件版本。受测安装源码包位于 `attempt-59f576c\ai4orgchem-runtime-source-59f576c.zip`；它是源码安装候选，不含镜像或依赖二进制。
