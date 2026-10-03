# 三类用户使用路径

这些路径共用七个 task 与固定协议；专业计算化学和理论方法审查者属于第二类路径的两种侧重。现有结果可直接阅读，本轮整理材料不需要重新运行。

## 读者与证据查阅者

先读 [S1 范围索引](PROFESSIONAL_SERVICES_zh-CN.md#s1-协议与范围查阅)，进入固定上游每项 data-card/protocol/report/result。需要本地完整性检查时，按 [RUN](RUN_zh-CN.md) 使用 `evidence`；它不会重新计算十四项 QM。P12 查阅 N12/N14/N16 账本，当前没有 P12 runtime 复算 task。把完整性结论与科学判定范围分别记录。

## 专业计算与方法复核者

先读共用方法合同、S2 对应表、[四层判读](REVIEW_RESULTS_zh-CN.md)，再使用[已有运行示例](examples/P14_REVIEW_20261002_zh-CN.md)和[报告模板](templates/REVIEW_REPORT_zh-CN.md)。方法审查者重点检查规则、测试及覆盖缺口；计算研究者重点检查能量账本、参照、结构响应和运行身份。

未来另行选择新复算时，顺序为 L0 → L1 → L2 与单独等价性 → 资源核查 → 可选 L3/L4 → 四父联合分类。前序失败停止解释；L3/L4 需要单独预算，不能为了填写报告重算。本轮没有新计算授权。

Windows PowerShell 5.1 用户可用 `scripts/start-runtime.ps1` 自动寻找已有 PowerShell 7.3+；无需假设 PATH 中存在 pwsh。底层 `run-wslc.ps1` 在 PowerShell 7.3+ 执行，并显式传 `-Engine docker`。候选镜像须已经存在；下载和重建不是阅读报告的前置条件。

RUN 的命令是未来运行示例，替换 Image、OutputRoot 与四个完整运行目录后才使用。任意分子、基组/泛函扫描、全空间优化、resume 均无现有接口。不能用自由参数或冻结文件绕过登记范围。

## 开发者与环境维护者

先查 [来源审查](SOURCE_AUDIT_zh-CN.md)、[安装指南](INSTALL_zh-CN.md)、锁文件、runtime 和 [支持矩阵](WSLC_COMPATIBILITY_zh-CN.md)。后续新候选采用固定归档与干净 runtime 检出，不读取原项目未提交修改；更换依赖或科学来源需另行审查和验收。

当前镜像不因文档增补重建。现有本地 Docker 范围不能自动迁移到新镜像或 WSLc；CI 静态审查完成、运行 NOT_EXECUTED。不要为适配 WSLc 修改全局 WSL 配置、升级平台或重启；这些工作继续暂停。公开源码另行确认，镜像分发 BLOCKED。

问题按 [反馈模板](templates/FEEDBACK_zh-CN.md)手工整理：启动/资源/路径问题定位 runtime，规则/科学数值问题附上游精确来源和原始记录，探索性新体系另开议题。日志先审阅敏感信息，项目不自动上传反馈。
