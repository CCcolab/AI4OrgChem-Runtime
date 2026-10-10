> 当前公开阅读节选。原始历史材料已按原字节保存在本地归档；本文件不是原件，不能用于原始哈希验收，也不把旧验收转移至当前代码。
> 原件 Git 提交：eb65b4586c83637569f6359814338c1292948861；SHA-256：1e941b39978f6a8176c7751a5e1dc1c1201b9805ab7e8e7469f2f9705595d8fe。

# 当前交付与后续边界


2026-10-02 本地 Docker 候选已完成 L0—L4、STO-3G 等价性及四份新结果联合分类。全部运行与输入/输出哈希保留，分类为 consistent，范围限固定 C12H6 来源代理、PLG 定义与五参数平面 D3h 协议。最新摘要见 validation/oci-summary.public.json、l3-summary.json、l4-summary.json、classification-summary.json；完整历史见验证报告。


日常使用 scripts/start-runtime.ps1，兼容 PowerShell 5.1 并自动选择已有 7.3+。默认 Docker；新入口已用中文/空格路径实际执行 evidence PASS，7 项 PowerShell 语法/路径检查 PASS。镜像科学代码仍来自提交 f30b2906794d14f9030daab779c0d6a7cd4bd6f7，后续宿主启动/备份脚本及文档提交不冒充已构建镜像代码。

本地备份使用 scripts/backup-local.ps1，校验用 scripts/verify-local-backup.py。恢复流程与备份范围见 LOCAL_DELIVERY_zh-CN.md。备份不包含原开发仓库或全局 WSL/Python 环境，也不是跨盘灾备；普通运行文件保存于 ZIP，容器源码链接明确排除，源内容随镜像保留。失败尝试和错误日志未清理。

L3 实测 54.37 秒，L4 实测 21.20 分钟，峰值 RSS 均约 8.60 GiB；请求 8 线程不等于严格 CPU 配额。L4 可保存检查点，但不支持恢复运行。L3/L4 未严格断网实跑或真实中断验收。分类中上游历史环境快照与本次身份分开，以 manifest 为准。
