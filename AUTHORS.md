# Authors and acknowledgements / 作者与致谢

**Project author and maintainer / 项目作者与维护者:** Xiao Chen — [CCcolab](https://github.com/CCcolab).

AI-assisted Runtime engineering, testing and documentation were carried out through OpenAI Codex under the project owner's direction. Scientific interpretation and publication responsibility remain with the human project owner.

AI4OrgChem scientific implementations retain their upstream authorship, LICENSE and NOTICE. PySCF, geomeTRIC, RDKit and other dependencies retain their own authors and terms. The user-supplied YouMind guide has separately recorded provenance and rights; see [NOTICE](NOTICE) and [compliance](compliance/README.md).

## Codex contributions / Codex 贡献

**OpenAI Codex** contributed AI-assisted engineering under Xiao Chen's direction. These contributions are present in the Runtime main branch and its recorded development history:

| Area / 工作范围 | Contribution / 实际贡献 |
| --- | --- |
| Runtime engineering / 运行工程 | Implemented task adapters, launchers, source installation, container lifecycle handling and persistent output records. / 实现任务适配、启动器、源码安装、容器生命周期处理与输出保留。 |
| Input and resource checks / 输入与资源预检 | Implemented request checks, execution budgets, resource preflight and refusal paths. / 实现请求检查、计算预算、资源预检与拒绝路径。 |
| Engineering verification / 工程验证 | Prepared and executed engineering tests and scoped acceptance checks, investigated review findings, and retained failures and non-execution records. / 编写并执行工程测试及限定范围验收，调查审阅问题，保留失败和未执行记录。 |
| Traceability / 可追溯材料 | Organized source locks, input/code/image/result identities, verification reports and publication-boundary records. / 整理来源锁、输入／代码／镜像／结果身份、验证报告与公开边界记录。 |
| Documentation and guide maintenance / 文档与指南维护 | Prepared usage and interpretation guidance and maintained the user-supplied YouMind website after import. / 编写使用与判读指南，并维护导入后的 YouMind 网页。 |

This acknowledges Codex's actual work; it does not attribute those commits to the separate GitHub account `chatgpt-codex-connector[bot]`. Codex assistance is not an independent scientific endorsement. Scientific authorship, method definitions, result qualifications and unresolved limitations retain their recorded scope.

本节明确记录 Codex 已参与并合入项目的工作。GitHub 右侧 Contributors 按账号关联的提交自动统计，本节署名与该统计分别呈现；科学源码原有署名、人工解释与发布责任继续保留。

## Skills / 技能指令

Xiao Chen supplied the first eleven personal chemistry Skills created on YouMind. OpenAI Codex adapted their instructions for use outside that platform, prepared usage guides and ran scoped local workflows under the maintainer's direction. Four additional instruction Skills cover fixed-protocol energy review, constrained optimization, multistate/size comparisons and Runtime usage. YouMind is the original authoring platform, not a bundled calculation engine or an independent scientific reviewer. See [the catalog](skills/README.md) and [test scope](skills/TESTING.md).

前11份个人指令来自维护者在YouMind创建的Skill；Codex完成平台外适配、文档与限定测试，另补4份流程指令。原始汇编和完整本地证据保留归档，公开目录只含明确范围的指令与材料，不将平台或AI协助署名当成科学认证。

## Git commit attribution / Git 提交身份

GitHub's Contributors sidebar is derived from account-associated commits on the default branch. Historical Runtime commits through `a4a39a4` retain `Codex (AI4OrgChem local)` / `ai4orgchem@localhost`; these unlinked local identities remain part of the public provenance and are not rewritten.

For subsequent maintainer-directed contributions, this repository uses `Xiao Chen` / `157860111+CCcolab@users.noreply.github.com`, the account-associated privacy email also used by CCcolab in AI4OrgChem. This is a repository-local Git setting. AI-assisted work remains acknowledged above; account attribution does not imply independent scientific validation or create contributions for a bot account. GitHub may take time to refresh its contributor summary.

**提交身份与历史保留：** `a4a39a4` 及此前提交保留原有本地署名。从本次维护提交起，本仓库使用维护者 Xiao Chen 的 GitHub 隐私邮箱，使经其指示完成的贡献可关联到 CCcolab；不修改全局 Git 设置，不改写已公开历史，也不改变 `v0.1.0` 的标签与附件。AI 工程协助及人工科学解释、发布责任仍按上文区分。

本文件说明作者、维护者及工程协助，不虚构 GitHub 贡献次数，也不把 AI 工程协助视为独立科学认证。Languages 由 GitHub 自动识别；不为展示比例修改科学文件。
