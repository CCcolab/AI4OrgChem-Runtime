# Runtime 与网站 GitHub 同步准备

准备日期：2026-10-09。目标为独立仓库 **CCcolab/AI4OrgChem-Runtime**。已核验GitHub CLI登录账号CCcolab；目标仓库当前不存在。本轮完成本地候选整理、历史扫描和备份准备，尚未创建仓库、设置remote、推送、改变可见性或启用Pages。

## 拟同步内容与历史

活动源码位于独立工作分支`implementation/protocol-cases-batch3`。应推送该分支最终候选提交到新仓库`main`；原本地`main`仍停留于0288eb8，不切换、重置或误推这个旧分支，也不修改原AI4OrgChem科研工作区。

本次审阅基线bdf813bc8a4912797ae179118fb2ee649b536f93共125个提交、818个当前文件和1249个历史文件对象。准备增补提交另行追加，不改写历史。基线文件正文共12,544,916字节，历史唯一blob合计18,099,261字节；最大单个对象512,661字节，无超过50或100MiB的文件。清单与完整提交元数据见 [历史扫描](../validation/github-sync/history-audit.json)、[当前文件](../validation/github-sync/current-files.json)、[提交清单](../validation/github-sync/commits.json)。最终封包身份、增补后文件数与哈希在仓库外的本地同步准备交付manifest中登记，避免报告把自身提交哈希写入自身。

| 纳入候选 | 具体范围 |
| --- | --- |
| Runtime | runtime、scripts、schemas、configs、profiles、container、locks、tests，以及README、LICENSE、NOTICE |
| 科学来源与许可 | 已冻结且署名的reference/源码片段、assets中安装源码覆盖、compliance许可／来源材料 |
| 使用与证据 | docs、examples、validation中的现有报告、摘要、身份／失败／未执行记录；不是完整原始运行档案 |
| 网站 | docs/index.html、.nojekyll、模块名称映射；docs/runtime-guide的原始快照、当前维护导出和两个小型网页ZIP |
| 需显式接受的现有材料 | 根目录两份实施方案、AI4OrgChem-user-molecule-DRAFT2-review_zh-CN.md外部意见；完整历史、个人路径和系统／工具信息 |

不上传本地OCI镜像／image tar、wheel／sdist／原生依赖源码归档、检查点、科研完整运行目录、Git工作树管理元数据、未跟踪私有材料或原科研项目工作区。只推送候选HEAD可达历史，不`--mirror`、不`--all`、不推送标签。候选中的reference保存研究来源与验证材料；它们不是容器内全部依赖软件。

有限凭证模式扫描覆盖125提交全部1249个唯一blob以及遇到的两个网页ZIP的成员，七类模式没有命中。这不是全面安全认证。315条blob／归档成员记录包含本地路径，完整披露索引见[路径记录](../validation/github-sync/local-path-disclosures.json)。提交身份为Codex (AI4OrgChem local)／ai4orgchem@localhost。若不接受这些历史内容公开，应在推送前另行确定公开分支策略；仅从最新树删除文件不能从完整历史中移除它们，本轮不擅自改写历史。

## 网站和许可证边界

网页可从仓库一起取得；公开托管需单独启用GitHub Pages。简单静态指南拟用`main`的`/docs`作为发布源，现有.nojekyll保留。预期地址为`https://CCcolab.github.io/AI4OrgChem-Runtime/`，**当前不是已存在网站**。使用仓库Pages功能时须确认账号方案和可见性支持。[GitHub官方发布源说明](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)明确可选分支根目录或/docs；Pages通常对外可访问，不能把私有仓库等同于私有网站。

/docs分支发布会使该目录内的文档、原包和当前维护文件一同可访问；不自动缩小为仅index.html。若只希望托管单页，后续应明确选定发布文件再配置Actions，当前不新增该流水线。网站已完成本地三宽度、复制、功能名搜索、导出CRC与根／模拟仓库路径检查；真实GitHub Pages HTTP尚未执行，200%缩放、完整键盘、多浏览器仍未执行。

自有Runtime代码沿用Apache-2.0；科学来源与第三方原文保留各自版权／许可。用户提供的YouMind指南及其派生网页包保留原记录的权属待确认状态，不自动套用根Apache。公开同步前需项目负责人确认其公开使用范围；本轮没有替第三方授予权利。许可证原生构建／字体缺口限制**镜像分发**，不包装成源码／网站已获分发认证；当前不发布镜像。相关依据见[公开边界](PUBLICATION_BOUNDARIES_zh-CN.md)、[高成本实际组件](../compliance/HIGH_COST_COMPONENTS_20261009_zh-CN.md)。

## 支持声明继续保留

- 用户自有分子：限定H/C/N/O、中性单重态、RHF/6-31G(d)、≤20原子且AO≤80的普通单点／canonical轨道／AO密度矩阵服务；不扩展为任意DFT、开壳层、通用优化或扫描。
- 网页十四模块使用实际计算名称，内部P01—P14供命令与来源追溯；固定案例接入、历史验收、新镜像登记分别描述，旧PASS不继承给新镜像。
- 用户分子旧条件态比较Compute保持BLOCKED；WSLc BLOCKED／NOT_EXECUTED且实机验收暂停；原生WSL2 Check不冒充原生Compute。
- GitHub远端CI NOT_EXECUTED；本地工程记录不冒充远端运行；高成本状态全集未实测，L3/L4严格断网范围和L4仅保存检查点／不支持恢复运行仍保留。
- 镜像分发BLOCKED；源码公开与网页托管另按项目负责人确认的范围执行，不发布镜像、标签或Release，不重复高成本计算。

## 获确认后的执行顺序

以下是待执行说明，不是本轮实际创建或推送记录。先确认仓库可见性、完整历史／材料公开范围、网站使用权属与是否启用Pages。新建空仓库时不添加GitHub自动README、LICENSE或.gitignore，防止与本地历史产生无关根提交。

```powershell
# 在最新候选Runtime工作目录执行；可见性参数须依最终确认选择
gh repo create CCcolab/AI4OrgChem-Runtime --public --description 'Local molecular-computation runtime and user guide'
git remote add origin https://github.com/CCcolab/AI4OrgChem-Runtime.git

# 从本地交付manifest读取已封存的完整候选SHA，不用旧本地main
$candidate = Get-Content '实际同步准备交付目录\sync-candidate-manifest.json' -Raw | ConvertFrom-Json
git push origin "$($candidate.runtime_commit):refs/heads/main"
gh repo edit CCcolab/AI4OrgChem-Runtime --default-branch main
```

只有目标确认为空仓库才执行该推送；若已存在远端内容，先读取并核对，不force、不覆盖。推送后比较远端main SHA与候选manifest、检查3项Actions及上传证据；成功／失败／未执行分别入记录。现有[CI静态审查](../validation/github-sync/CI_STATIC_REVIEW_20261009_zh-CN.md)不是远端PASS。Pages经确认后从Settings→Pages选Deploy from a branch→main→/docs→Save，并检查真实根地址、锚点刷新、手机布局、复制与下载；没有成功部署记录前不写“网站上线”。

Git克隆用于源码安装；GitHub自动Download ZIP缺少安装器要求的commit/tree/blob证据，不能冒充专用安装源码包。本地准备交付会同时保存安装器`package`生成的、含来源证明的源码ZIP和Git bundle备份，仅封包，不构建镜像。网页ZIP始终只是指南。正式Release附件分发另行安排。

## 本轮完成与待确认

本地候选、扫描、文件／提交清单、CI静态审查、来源标签核对和备份均可供最终确认。上游注释标签v0.3.2对象afd91ea6ec6847b329ee75a7b20ed564560d9460解析到28511f3d84fa65707a107cde1e8121a7b4334ecb，与冻结来源锁一致。Git对象检查未报告损坏；本地不可达dangling对象与工作树管理提示不属于拟推送HEAD历史，本轮不清理它们。

待确认的是公开动作与范围；远端CI及Pages验收只能在该动作后执行。镜像许可／来源缺口和WSLc暂停继续单独保留。外部专家咨询已由用户取消，不作为同步前置条件。本轮不改变原科研环境。

## 推送前最终增补

十一YouMind Skill由用户延后导出，不构成本次源码／指南同步前置；私有原指令与空目录没有加入候选。独立复核后的[两项记录修正](../validation/github-sync/FINAL_CONSISTENCY_CORRECTIONS_20261009_zh-CN.md)明确网页历史维护／当前手工QA／包外实测的区别，并修正未来CI工程job的执行上下文，保持实际远端CI NOT_EXECUTED。当前网页身份见[最终局部验收](../validation/web-guide/final-consistency-20261009.json)，旧68ab316封包与旧记录保留，最终新源码以仓库外封存manifest为准。版本号暂不确定；创建仓库、公开范围与Pages仍待用户确认。

当前网页最终字节与导出另见[语义补核记录](../validation/web-guide/final-consistency-r2-20261009.json)；较早记录仅用于其相应历史归档。
