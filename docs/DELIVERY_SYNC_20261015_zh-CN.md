# 整改交付与真实 CI 记录

[English](en/DELIVERY_SYNC_20261015.md) · [能力登记](../configs/runtime-capabilities-v2.json) · [机器状态](../validation/delivery-sync-20261015/status.json)

## 已通过的工程基线

[GitHub Actions 运行 38692149789](https://github.com/CCcolab/AI4OrgChem-Runtime/actions/runs/38692149789)对应提交 [09cbab5](https://github.com/CCcolab/AI4OrgChem-Runtime/commit/09cbab553d5920157a14b97fac1c5ea9059c28a1)，三个 job 均成功。该运行最初来自专项分支，验收身份不随之后的文档提交改变。[原 CI 汇总回执](../validation/delivery-sync-20261015/remote-ci-09cbab5.json)原字节保留。

| Job | 实际覆盖 | 不包含 |
| --- | --- | --- |
| `public-review-regression` | 96 项确定性程序检查、跳过 0；15 份指令及 20 份受测源码身份；保存数值见证和一份水分子完整轨道数组复核 | 独立 Agent 行为评测、新 RHF、波函数稳定性 |
| `public-installation-engineering` | GitHub Ubuntu Linux amd64 新建源码安装、本次 CI 本地构建、四家服务登记与来源绑定；非 root、只读源、断网、Linux 输出权限正反例、非零退出码、容器删除及输出保留 | Windows 用户新安装、分子复算、历史科学 PASS 的继承；科学调用为 0 |
| `linux` | 旧入口 L0 保存证据验证、L1 十一个核心检查及权限/持久化探针 | 全部历史科学测试、新分子计算或高成本状态重放 |

Linux CI 的实际安装工程验收已经执行，不能再笼统记为“全新安装未执行”。Windows 新安装与一次新水分子 RHF 的合并验收、独立 Agent 评测由用户决定暂缓，分别保持未执行。程序回归不是 Agent 阅读指令后完成任务的独立测评。

## 历史记录与后续状态

[初次整改记录](REVIEW_REMEDIATION_20261015_zh-CN.md)、[R01/R02 回修记录](REVIEW_CORRECTIONS_20261015_zh-CN.md)及其原始机器记录保留各自执行时点的状态；其中“本地未推送”“远端 CI 未执行”“待独立复核”等不是本页的当前结论。R01、R02 已收到用户转述的独立复核关闭结论；外部 ZIP 未在本地提供，不将用户报告冒充本机独立复验。

原 79 项、本地修正后的 96 项、历史 170 项 Skill 场景和旧科学记录仍分别保留，不叠加成一次验收数字。当前 CI 声明引用已完成的精确提交；后续源码或文档提交仍以各自 Actions 运行记录为准，不能继承同一提交身份。

原项目的 [9091389 文档候选](https://github.com/CCcolab/AI4OrgChem/commit/9091389a2adb147dbae98602e332a9accdde4a57)相对公开基线只改四份 P12 说明及两份生成清单。其五个只读证据验证器已通过，没有改动计算代码、数据、分类、门槛或运行身份。主分支实际合入状态以对应仓库的 PR 和 Git 记录为准。

## 本次同步边界

这次同步仅交付源码整改、说明与 CI 回执，不新增版本标签或 Release，不分发容器镜像。十五份 `SKILL.md` 不改写；旧 v0.1.0 资产和指南 ZIP 不自动包含后续 Skill 增补。

用户分子条件态 Compute 继续关闭；P11/P12 仍是 78 个登记单元中的两个 Runtime 先导态通过。L4 可保存检查点，但不支持恢复运行。普通 RHF 的历史验收、波函数稳定性和新安装资格分别判读；本次 CI 不扩大科学服务范围。暂停的平台验收和镜像分发限制保持不变。
