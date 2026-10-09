# GitHub 源码与指南首次公开同步

2026-10-09，项目负责人授权“请确认后推送”。已核对封存的 `06d50885bdccf31f83b89229c1513121542375d5`（128 个提交、836 个文件）及四份交付包哈希，创建公开独立仓库 [CCcolab/AI4OrgChem-Runtime](https://github.com/CCcolab/AI4OrgChem-Runtime)，将这个完整候选精确推送到远端 `main`。远端 SHA 与候选一致，默认分支为 `main`；原本地 `main` 仍为 `0288eb8`。不改写历史、不覆盖原科研项目工作区。

## 实际远端 CI

首次 [GitHub Actions 37933616122](https://github.com/CCcolab/AI4OrgChem-Runtime/actions/runs/37933616122) 由上述提交的 push 触发，三项 job 均 `success`。执行时间为 2026-10-09 12:58:43—12:59:34 UTC（日本时间 21:58:43—21:59:34）。

| Job | 实际通过范围 | 保留的未执行范围 |
| --- | --- | --- |
| linux | 在线构建候选镜像；12 项 wrapper、L0 四项冻结证据验证、L1 11 项核心测试；执行容器断网、非 root、来源只读与证据哈希探针 | 不含 L2—L4、新镜像高成本重放或全部科学任务 |
| user-molecule-contracts | 157 项最小合同与 74 项附加工程测试，共 231 项，无失败或跳过 | 12 个 GUARDED、9 个 LOCAL_ONLY 文件未在此 job 执行；不运行新用户分子计算 |
| local-service-contracts | 444 项登记，443 项通过，1 项实际 P11 预检按设计跳过；无失败或错误 | 真实 P11 预检要求另行 opt-in 科学容器；mock/数组测试不授予科学资格 |

两份 Linux 运行 manifest 为 `PASS`、退出码 0，数值／科学资格为 `NOT_APPLICABLE`。实际 job 上下文、run、attempt、源码 SHA 已与 GitHub API 相符；不是把本地模拟测试认定为远端执行。三个原始附件的 GitHub SHA-256 digest、ZIP CRC、43 项解压内容均已核验，附件保留七天，完整日志和下载副本另存本地交付目录，见[机器记录](../validation/github-sync/public-push-20261009.json)。CI 构建过程需要网络，不能把运行容器的 `--network none` 写成构建断网。

旧文档、审阅包与验收记录的 `CI NOT_EXECUTED`／未推送属于各自历史时点，保留原文；上表仅覆盖本次指定提交及三个 job，不将所有旧候选记录改写为 PASS。当前增补只同步真实公开状态及 CI 记录，未修改求解器、科学规则、阈值、输入或计算命令。后续文档提交不冒充首个候选镜像的构建提交；其 Actions 状态以各自真实 run 为准。

## 公开范围及保留边界

用户本轮授权按已审阅范围公开 Runtime 源码、完整候选历史、署名／许可材料、报告摘要及用户提供的 YouMind 指南与历史网页归档。历史包括已列明的方案、评审、提交身份、本地路径及工具信息；私有 Skill 原指令和未跟踪的 YouMind 设计目录未纳入。公开包含范围不替第三方授予权利，YouMind 原包和派生材料仍按 `NOTICE` 与来源记录各自保留，不自动改为根 Apache-2.0。

网页文件已随仓库公开，但 **GitHub Pages 未启用**，不宣称网站已托管；网页只是指南，无在线计算入口。Git 克隆可用于源码安装，GitHub 自动 ZIP 缺少安装器要求的来源证明，不能冒充专用源码安装包或完整安装环境。

未创建新 Runtime 版本、标签或 Release，未推送镜像／OCI archive。镜像分发继续 `BLOCKED_LOCAL_ONLY`；WSLc `BLOCKED / NOT_EXECUTED` 且升级与实机验收暂停；旧用户分子条件态 Compute `BLOCKED`；原生 WSL2 Compute `NOT_IMPLEMENTED`。这些状态不因源码公开或本次 CI 改变。L4 可保存检查点，但不支持恢复运行。没有重复 P12 或其他高成本科学计算，也没有改动本地 Docker／WSL 环境。

YouMind 11 个 Skill 的导出由用户延后，不构成此次同步前置。完整网页的真实 200% 缩放、全键盘、多浏览器及真实 Pages 平台验收仍未执行；局部页面状态文字增补按新 HTML 哈希另存浏览器记录，不继承旧哈希的 PASS。

当前网页状态文字增补的局部实测见[网页身份](../validation/web-guide/public-status-20261009.json)及[浏览器记录](../validation/web-guide/browser-public-status-20261009.json)，79个复制目标、所有计算代码块及水输入模板与公开前候选一致。三个外部链接采用原网页相同的target/rel规则，活动HTML与实际导出逐字一致；原提供记录与归档不覆盖。

## 2026-10-10后续静态指南托管

本文件保留2026-10-09首次源码同步时的身份和“Pages未启用”历史状态。后续已按用户要求启用静态指南，直接入口为 https://cccolab.github.io/AI4OrgChem-Runtime/ ，范围与独立部署记录见[网页打开与托管指南](GITHUB_PAGES_GUIDE_20261010_zh-CN.md)。原先源码公开和CI记录不改写为网页部署记录；网站不提供在线计算，科学和镜像限制保留。
