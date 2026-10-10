> 当前公开阅读节选。原始历史材料已按原字节保存在本地归档；本文件不是原件，不能用于原始哈希验收，也不把旧验收转移至当前代码。
> 原件 Git 提交：eb65b4586c83637569f6359814338c1292948861；SHA-256：cb8327886a5a62e8c186131ab051de24c939f225be617246adcb38ee4fe960c6。

# 唯一原生根诊断：墙钟停止与只读取证

2026-10-07。已执行用户对明确201次/300秒问句批准的一次固定乙烯原生根诊断。**139次NR均有完成事件；138回调成功、最后1回调因截止时间失败。运行未返回正式根或尾检，Compute仍BLOCKED。** 停止后仅验算保存数组，没有重试、恢复或新增F。

## 执行身份与结果

实际执行提交 `73e8dfd8aef4881dec6b8cd30b21b2228f8b51ab`；此前工程受测 `aad7c5b` 的52项关键代码一致。复用r3镜像 `sha256:24f46f33264924e5d3d3bec386298585267c6f30d6e6a0cd0a6486ecf45db93d`、构建提交 `5098775c9cf40468ab92712447a3e5c7b1361a63`、科学适配 `cc7437901119e71ef7945a12813c021c383e7648`、冻结基线 `28511f3d84fa65707a107cde1e8121a7b4334ecb`。最终文档交付提交另列，不冒充执行或镜像构建提交。

| 项目 | 保存证据 |
|---|---|
| 单次范围 | 14AO/16电子乙烯，seed2/−0.10，一条independent_reference、一chart/max_nfev2；原2/0全局Aufbau、正能隙与阈值保持 |
| 限额 | 201槽、300秒含清理，275秒停止；1CPU/1GiB/零swap、非root、断网、根/源码/输入只读 |
| 第一完整差分 | 槽3—98共96成功，持久状态COMPLETED |
| 第二差分 | 槽100—139共40收费、39成功/1失败；原STARTED的actual0是初始快照，不能当实际零调用，也不回填旧记录 |
| 原生与回调计数 | 139 entered/139 completed/0 NRfailed；138成功callback/1失败，pending0；139对完整JSON/NPZ捕获 |
| 停止与资源 | 含清理279.031秒，exit137、wall_stop_requested；Docker OOMKilled=false，峰值250994688字节约239.37MiB，无记录内存限额失败/OOM |
| 独立保存数组审计 | 1675个NPZ成员、52项源码/合同/账本身份及139点原九门槛重建；算子/能量组件对应成立，139点均无完整合格 |
| 正式验收 | 无正常solver return，无正式density；最终端点gate、returned/mapped尾检NOT_EXECUTED；最终护栏/账本回执缺失 |
| 原始预算状态 | wall已SETTLED；callback path仍OPEN，accounting closed=false/statusFAILED_NO_RETRY。保持原字节，不假装正式闭账，不复用剩余62槽或剩余墙钟 |

第139次NR与结果捕获已完成，但AFTER_CALLBACK检查发现截止时间到达。父监督器275秒停止并采用2秒Docker停止宽限，随后exit137，子进程未完成finally的正式账本/护栏发布。退出137不单独证明OOM，本次Docker和cgroup没有报告OOM。原EXECUTION的new_source_native_NR_calls仍null；139计数来自停止后的完整事件/账本/捕获交叉核验，作为派生取证，不修改原执行记录。

## 数值判读与未完成项

纯NumPy/标准库独立审计重建初值白化投影、F=Pmask(G)、G的保存h/J/K/Vxc组合及能量项，并重建139点原九项门槛；不重新调用PySCF、网格积分、ERI、核能或F/NR。第99槽仅为未正常返回的优化试探：占据—虚空间残差约0.01110、comm约0.01736、map相对约0.43351，未合格。较好FD样本也只作为诊断，不能替代正式端点。没有新研究能量差、完整生产/参考根等价或稳定性验收。

一次预算内未完成、保存点不合格不能证明合格根不存在；也不自动推翻原P01—P14冻结结果。网格电子数/Exc只做保存记录对应，不冒充独立积分验证；新诊断的最终完整护栏回执未生成，未知保留。

## 时间诊断与下一步

139对BEFORE→AFTER标记合计145.003秒（平均1.043秒），138个AFTER→下一BEFORE混合间隔合计122.780秒，占首BEFORE至末AFTER区间约45.85%。这些时间混合算子、校验、保存、资源观测、优化器与记账；原生事件没有时间戳，无法给出纯NR耗时或把间隔全归因于磁盘/哈希。成功回调至少四次遍历52项源码的核查是静态代码事实，尚未单独计时。CPU仅记录配额，没有用量/节流数据，不能据此断言CPU瓶颈或需增加核数。

下一步限于工程：完善合作停止与正式关闭回执，再用零原生调用/工程替身分段测量校验与持久化成本。当前不重试分子、不提高201/300预算、不取消身份/持久化保证、不改科学门槛。任何后续新科学进程需另立具体执行预算，当前一次批准已使用；本轮外部专家流程仍取消。


详见[机器状态](../validation/user-molecule/root-native-diagnostic-20261007.public.json)、[MDR-010](../validation/user-molecule/method-decisions/mdr-010/record.public.json)和[能力登记](../docs/LOCAL_HISTORY_ARCHIVE_zh-CN.md)。授权原话与问句分角色保留，完整日志、原OPEN账本、139捕获、只读复现脚本与封存清单在 `D:\AI4Science\ai4orgchem-runtime-deliveries\20261007-user-molecule-root-native-diagnostic`；11250项旧交付及原两项目HEAD/工作区状态保持。
