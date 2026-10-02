# 当前交付与后续边界

当前状态（2026-10-03）：本地 Docker L0—L4/等价性/联合分类已验证，WSLc 暂缓并保持 BLOCKED / NOT_EXECUTED；CI 静态审查完成、运行 NOT_EXECUTED；许可映射与对应源码提供未齐，公开发布仍阻塞。身份与范围以 validation/final-delivery-status.json 和 DELIVERY_REVIEW_2026-10-03_zh-CN.md 为准，既有备份为历史快照。

2026-10-02 本地 Docker 候选已完成 L0—L4、STO-3G 等价性及四份新结果联合分类。全部运行与输入/输出哈希保留，分类为 consistent，范围限固定 C12H6 来源代理、PLG 定义与五参数平面 D3h 协议。最新摘要见 validation/oci-summary.json、l3-summary.json、l4-summary.json、classification-summary.json；完整历史见验证报告。

用户优先保护原 AI4OrgChem 科研环境，WSL 升级和 WSLc 实机验收暂停，WSLc BLOCKED / NOT_EXECUTED。恢复须明确授权；不自动升级、改变全局配置、启用功能或重启。原项目未启用 Docker，文件与环境均保留。

日常使用 scripts/start-runtime.ps1，兼容 PowerShell 5.1 并自动选择已有 7.3+。默认 Docker；新入口已用中文/空格路径实际执行 evidence PASS，7 项 PowerShell 语法/路径检查 PASS。镜像科学代码仍来自提交 f30b2906794d14f9030daab779c0d6a7cd4bd6f7，后续宿主启动/备份脚本及文档提交不冒充已构建镜像代码。

本地备份使用 scripts/backup-local.ps1，校验用 scripts/verify-local-backup.py。恢复流程与备份范围见 LOCAL_DELIVERY_zh-CN.md。备份不包含原开发仓库或全局 WSL/Python 环境，也不是跨盘灾备；普通运行文件保存于 ZIP，容器源码链接明确排除，源内容随镜像保留。失败尝试和错误日志未清理。

L3 实测 54.37 秒，L4 实测 21.20 分钟，峰值 RSS 均约 8.60 GiB；请求 8 线程不等于严格 CPU 配额。L4 可保存检查点，但不支持恢复运行。L3/L4 未严格断网实跑或真实中断验收。分类中上游历史环境快照与本次身份分开，以 manifest 为准。

后续许可证、对应源码和来源映射材料已补充，详见 PUBLICATION_BOUNDARIES_zh-CN.md；剩余阻塞集中于原生 wheel 来源与实际分发通知。CI 仍未实跑，目标 WSLc 对照未完成。源码公开与镜像发布分别评估，均未获公开授权；不发布、不启动新高成本计算。继续前先读 git status 并保留全部文件。
