# W05 验收准备决策单

2026-10-05 / W05-PREPARATION-1。此表是具体科学/验收审阅材料；空白、待审、讨论或文件存在不代表批准。当前 approver=null、approved_at=null、SCF 预算未批准、Compute disabled。来源为 [准备记录](../USER_MOLECULE_W05_PREPARATION_zh-CN.md) 和 [机器可读未决项](../../validation/user-molecule/w05/pending-decisions.json)。

| ID | 需要决定或补齐的事项 | 应留存的证据 | 当前状态 |
|---|---|---|---|
| B01 | 两份候选 XYZ、π 组及技术测试用途；复用丁二烯坐标是否满足“两个新体系”，否则另选夹具 | XYZ/请求 SHA、来源、原子图、理由与可解释范围 | PENDING_METHOD_REVIEW |
| B02 | 近碰撞距离规则、S̃ 条件数门禁 | 数字/公式/单位/依据、失败样例；通用门禁实现与测试 | TBD |
| B03 | 小 gap/简并处理与 required/diagnostic 分类 | 操作策略、gap_operator_source、未定义/null 规则；不修改占据来强迫通过 | TBD |
| B04 | 普通/条件有效设置、独立参考谱系、T04—T06 逐字段容差 | profile 原始及镜像字节身份、各算子/分量阈值、固定 D 生成配方、比较表 | PENDING_REVIEW |
| B05 | 校准批预算、分阶段峰值与累计限额 | 硬内存/线程/时间、累计执行器、cgroup峰值、tmpfs余量、停止行为 | PROPOSED_NOT_EXECUTED |
| B06 | 独立参考、两模式验收驱动、缺失门禁及完整诊断字段 | 新实现提交、禁止导入核查、toy十五类/八重对称/允许项与失败测试 | NOT_IMPLEMENTED |
| B07 | W06 完整参考及研究解释范围 | 能量—算子—占据关系、有限范围批准记录；不同方法比较另报 | DEFERRED_TO_W06 |

逐项填写：结论（接受/修订/拒绝/待证）、具体值或策略、证据文件及哈希、理由、审阅人、日期、适用 profile/夹具/代码身份。改动必须产生新身份；不得追改旧验收记录。

B01—B06 不能以“建议可行”自动关闭。缺少参考实现、阈值、门禁或预算时科学验收仍 NOT_EXECUTED；即便技术测试可开展，也不能打开未经限制的生产 Compute。B07 是 W06 研究出口，不能用 W05 技术通过替代。
