# W06 工程候选：完整参考与研究资格

2026-10-05 / W06-ENGINEERING-1。当前部署范围是可独立开展的工程实现，**W06 / D3 尚未验收完成**。W05 分子数值与资源标定仍 BLOCKED / NOT_EXECUTED；两个生产 profile 的 Compute 保持禁用。原本地 Docker 工程验收、远端 CI、研究数值和平台支持分别记录。

## 实现与用途

| 文件 | 已实现 | 未验证或未接入 |
|---|---|---|
| `reference/user_molecule.py` | 独立 AO 标签/定向核查、锁定 YAML 读取、十五类标量谓词和八重对称、h/S/F 投影、标量 J/K witness、张量收缩、五分量账本、全局闭壳层占据、阻尼/独立 Pulay/完整条件固定点迭代、最终指标及 gap 来源 | 分子级独立参考未执行；普通 RKS 独立驱动、预算监督/峰值记账、同 D 采样/NPZ 身份与完整分子验收驱动仍缺；原始 PySCF XC 桥接函数未实测 |
| `runtime/user_molecule/research.py` | 拒绝优先的只读资格判读；精确请求/几何/profile/规则/科学来源/镜像绑定；关联方法审阅、A01—A18、两个新体系、完整参考及资源证据的字节哈希 | 未连接生产 Compute 启用；哈希不是签名或审批权认证；没有真实批准范围 |
| `runtime/user_molecule/records.py`、`__main__.py` | 请求问题/碳组、两态能量、差值符号/单位、账本残差、分层资格及解释限制的短简报；Report 读取已有快照 | 已有 r3 镜像不包含本轮代码，仍使用原简报；生产报告不装载批准记录，不生成研究合格声明 |
| `validation/user-molecule/w06/research-scope-registry.json` | 空范围登记、责任/日期空值、明确未批准 | 不含真实签署、数值或研究范围；测试生成的 SYNTHETIC 记录只在临时目录 |

独立参考暂放在 runtime 仓库的 `reference/`，作为隔离验收源码，不进入生产计算路径；科学仓库及其 591 文件清单、旧/新来源锁均不改。后续若迁移到科学仓库，需要另记参考提交与源码映射，不能把参考增补冒充现有镜像的科学提交。

## 参考的数学与复用边界

定义来自固定 [条件操作合同](USER_MOLECULE_CONDITION_DEFINITION_zh-CN.md) 和科学提交 `cc7437901119e71ef7945a12813c021c383e7648` 的规则 YAML，SHA-256 `324c2e7988be48ed8898a5e9b04a87d40386ca8a8f7eb603d9a697d3ac6a6ee2`。代码不导入或调用生产 AO/mask/J/K/能量/条件 SCF 辅助；允许阅读锁定规则数据。独立实现是代码验证路线，不是 BLW/ALMO/NBO/cDFT 方法等价或科学解释验证。

完整数组迭代使用 S̃ 广义本征问题、全局 2/0 占据和同一原始 AO/grid 的 XC。标量 J/K witness 限 8 AO；完整数组候选限 40 AO，仅表示实现边界，**不是已校准的内存峰值、运行预算或研究支持规模**。采用独立 affine Gram DIIS：普通求解，奇异时 least-squares，输出回退次数。这与生产 PySCF DIIS 的退化处理尚需在 T06/状态选择审查中核对，不要求逐步迭代轨迹相同；若终态不一致，调查状态与原因，不修改科学规则或放宽阈值。

共享 NumPy/SciPy 线性代数及未来 PySCF 原始积分/LibXC/XC 的误差不由本参考独立验证。当前 toy 的 XC 是明确的解析回调，没有网格、真实积分、Mole 构建或分子 SCF；收敛 toy 不代表分子会收敛。`molecular_acceptance=NOT_EXECUTED`、`variational_status=NOT_ESTABLISHED`、`stability_status=NOT_EXECUTED` 继续保留。gap 来源为最后一次可能含 DIIS 的对角化；最终交换子使用返回密度重算、无 DIIS 的 Fcond。

## 资格判读边界

失败、部分完成、非有限必需量、缺失状态测试、未登记 profile、差值符号或单位不一致均不提供合格比较。成功 pilot 仍 TECHNICAL_ONLY；成功 research 没有精确范围证据则 NOT_REVIEWED。研究判读模块要求四类带哈希的机器记录及同一完整身份绑定，还绑定全部结果正文的 canonical JSON SHA-256（UTF-8、key 排序、无多余分隔空格、严格有限 JSON，与原文件字节哈希分别记录）。同请求下结果正文改变不能沿用资格。真实审批权、科学依据、原始日志和残差仍须审阅。登记的两个新体系需由审阅者确认，不能用两个不同字符串或旧 P08 重复记录替代科学验收。

本轮报告不加载范围登记，也不改变旧 result schema 或科学适配器的返回字段。门禁是**单独测试的判读候选**，不是生产研究就绪服务；后续启用需有新 profile/schema/来源构建与实际验收身份，不能只写一个 PASS 或修改 `compute_enabled`。

## 仍需闭合的出口

1. W05 B01—B06：候选体系/分片用途、近碰撞/条件数/gap、完整 profile、T04/T05/T06 逐字段容差、独立普通驱动/完整验收驱动、冻结预算及资源峰值记账。原准备记录保留历史状态，本轮不填审批人或未执行数值。
2. W05 实际普通态、固定 D 算子/分量、两个生产存储路径和不变量验收；受限新分子运行需完整冻结及批准预算，才能退出 D2。
3. W06 每研究 profile 的完整独立分子条件参考、至少两个获审新体系、方法范围/责任和 C06 允许解释；A01—A18 实际适用项及专业用户操作，才能退出 D3。
4. 新代码进镜像并验收的身份链；本轮不重建或将 r3 标成已含 W06。生产资格激活和资源模型仍未实现/未验收闭合。

本地 Docker 的原 W01—W04 工程范围已验证；本轮测试是干净新源码只读挂载到旧镜像的工程验证。WSLc BLOCKED / NOT_EXECUTED，WSL 升级暂停；GitHub Actions NOT_EXECUTED；镜像分发 BLOCKED；源码推送/正式标签/Release 未授权。旧 L3/L4 不重算，L4 保存检查点但不支持恢复。

实际执行次数、提交、镜像身份和日志索引以 [本轮验证记录](../validation/user-molecule/w06/engineering-review.json) 为准；该记录不把静态实现列为科学 PASS。
