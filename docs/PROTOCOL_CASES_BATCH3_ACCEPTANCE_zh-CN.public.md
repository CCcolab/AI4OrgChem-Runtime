> 当前公开阅读节选。原始历史材料已按原字节保存在本地归档；本文件不是原件，不能用于原始哈希验收，也不把旧验收转移至当前代码。
> 原件 Git 提交：eb65b4586c83637569f6359814338c1292948861；SHA-256：dcabc9e9dbed459c8b2281b3d26891a4eb925fdabe9ca54c8823da9bf57c652f。

# 第三批 P11/P12 验收合同与待验证登记

**登记状态：`LOCAL_CANDIDATE_ENGINEERING_ACCEPTED_P11_AND_P12_SINGLE_PILOTS_PASS_FULL_SCIENCE_INCOMPLETE`。** 当前P11为1/17（苯G）、P12为1/61（N12-G），其余76态及完整组装未执行。P11旧宿主manifest缺陷与补核仍保留；修复后的宿主已完成零SCF账本和本次真实P12-N12-G科学路径，其61项宿主载荷全部匹配。两次科学先导身份分别登记，不重算苯G，不重新认证原P11/P12全部科学结论。

| 项目 | 当前登记 | 更新所需证据 |
| --- | --- | --- |
| 固定优化接口 | `IMPLEMENTED_LOCAL_CANDIDATE` | 78态注册及源协议/参数核对 |
| 76份科学来源捕获与原107项源锁 | `PASS_BYTE_IDENTITY` | 实际捕获清单、逐文件SHA、tracked/blob/上下文记录 |
| 冻结科学镜像身份与原工程CI | `PASS_ENGINEERING_SCOPED` | 构建05308a、镜像18dcd、原d8ee锁；108项运行、107通过、1跳过 |
| P11 ledger / 17态 preflight | `PASS_ZERO_SCIENCE_METADATA` | 历史算术与真实AO/几何；量化入口计数0 |
| P12 ledger / 61态 preflight | `PASS_ZERO_SCIENCE_METADATA` | 三尺寸恒等式/对称控制、真实Mole/AO预检 |
| P11 本轮17态新优化 | `PARTIAL_1_OF_17_SCIENTIFIC_GATES_PASS` | 仅苯G；原宿主日志缺陷与50文件补核独立披露，完整集合NOT_EXECUTED |
| P12 本轮8/23/30态新优化 | `PARTIAL_1_OF_61_SCIENTIFIC_GATES_PASS` | N12-G通过；其余60态及完整新CESE未执行 |
| 宿主补丁身份、回归与最终manifest | `PASS_HOST_PATCH_REAL_SCIENCE_SCOPED` | c10fb宿主锁、其他105项原字节；原17项回归/42项账本保留，本次科学路径61项载荷完全匹配 |
| 本次P12启动资源准入 | `PASS_SINGLE_STATE_ADMISSION` | 用户授权WSL上限18GiB后，按原主机16GiB/guest15GiB门槛通过；不代表后续状态自动合格 |
| 完整17/61态验收及新结果组装 | `NOT_EXECUTED_INCOMPLETE_STATE_SET` | 全部新状态与一致身份；不得以先导或fake组装替代 |
| GitHub Actions | `NOT_EXECUTED` | 本轮无远端执行声明 |

工程、历史算术、metadata、单态科学门禁及完整科学验收分别登记。未执行状态不能填写优化墙时、内存峰值、收敛态或科学PASS。苯G cgroup峰值不是单进程RSS，不能外推其他分子/状态容量。

## 固定科学范围

总数为 P11 17态加 P12 61态，单次 live 恰一个优化器：P11-A furan 4态，P11-B benzene 3态及cyanobenzene 10态；P12 N12/N14/N16为8/23/30态。N12含独立控制态，控制不进入CESE加权。N14/N16使用全部21/28组对、权重1；N16不能替换成历史8+1对称缩减队列。

P11-A 与 P11-B 的 h/F/S、F/S、物理hcore和ERI规则分别按来源协议核验，不互换。P12几何和能量保持 `B3LYPG/6-311g(2df,p)`、PySCF2.14.0、grid3、无DF、球谐基组、SCF `1e-10 Eh` /150周期；原全平面和内氢拓扑不变。P12原geomeTRIC参数为：能量 `1e-6`、GRMS `3e-4`、GMAX `4.5e-4`、DRMS `1.2e-3`、DMAX `1.8e-3`，最多80步；最终 `|z|≤1e-8 Å`。

P12每态必须是新优化记录，含非空新轨迹、原源协议、指定构型、优化和末态SCF资格；G保留普通RKS身份，GL/GE保留源2011算子身份。N16 GE 前先验证本轮G＋GL的状态JSON和优化XYZ哈希，并写本轮授权下的审阅记录；不复制历史审阅日期或文件。N16冻结contract/base SHA保持原值，工程ROOT路由到独立work，不更改原协议字节。

N12历史ledger复核包括15对覆盖、重数3、参考GL的C3残差，以及独立控制能差 `≤0.02 kcal/mol`、映射几何残差 `≤0.002 Å`。新的加权账本同样须有本轮几何与控制证据；旧对称通过不能为新几何背书。未通过时拒绝weight，不自动扩展组对或改变科学范围。当前第三批单态live没有新CESE自动组装入口。

## 三种模式分别验收

`ledger` 只能报告历史能量算术/权重/控制复核，科学入口计数全为0；即使通过，也不得改写旧科学分类或把旧优化标为本轮优化。P12必须保留原印刷值、本次旧复算值及numeric difference：三尺寸旧CESE为 `+2.887010、−15.947079、−0.339527 kcal/mol`，不声明与 `+2.59、−16.28、−0.65` 逐数字相同。N16历史相对CESE门槛保留10%；三点范围不等于N12—N22六点覆盖。

`preflight` 必须真实构建Mole/AO、核对构型、电子数与状态映射，且积分、SCF、梯度、grid/numint和优化入口计数全为0。预检既不产生新能量，也不证明优化收敛。

`live` 必须持有注册Unit、精确源/依赖/profile/镜像身份、独立预算和精确前序清单。冻结源runner或源优化器真实执行一次，审计 `optimizer=1`；每个受管科学入口都在该Unit的固定cap以内，全部正常返回，无被拒绝/改写入口，审计关闭后原属性完整恢复。`ENGINEERING_FAKE`仅能验工程接线，不能成为本轮合格前序或科学证据。

单态收敛不是完整命题复算、稳定性证明、原程序逐行复现或方法批准。P12历史2011实现对齐继续 `NOT_ESTABLISHED`，现runner不证明电子态连续性。原P11/P12科学判定、生产/训练标签边界及任意用户Compute门禁不因此改变。

## 资源、停止与预算闭合

资源限额固定：P11 live为8GiB、8CPU/8线程；P12 live为14GiB、16CPU/16线程；均软停止43080秒、硬墙时43200秒、scratch可用需求20GiB。metadata为1GiB、1CPU/1线程、120/180秒、scratch1GiB。Docker/guest内存另保留1GiB，live主机另保留2GiB，metadata主机另保留512MiB，磁盘另保留1GiB。

核验实际container与cgroup的内存、CPU、线程、无swap、非root `10001:10001`、只读源/依赖/合同/输入、网络none及能力限制；不能只引用launch参数或PySCF内存设置。资源未知/不足必须拒绝，不改WSL、不停止无关进程、不降低方法/容差。历史N16后19GE共约84.38小时属于旧环境，不能冒充本轮wall或容量校准。

每Unit只有一次尝试，启动前预留完整43200秒，结束后包含清理墙时并计费失败。未确定所属容器已删除则维持全额预留，拒绝后续运行；不重置预算，不迁移第二批/旧OPEN账本，无自动retry或resume。checkpoint保存进度，不提供恢复授权或恢复接口。

## 成功必须具有的证据

必须同时核对以下相互绑定的记录，任何缺失/失败均不能登记新高成本PASS：

- `host-execution.json`：实际准入、完整镜像身份、所属容器ID、退出码/OOM/停止原因、连同清理墙时、日志收集和删除后证据复核；最终live状态应为 `PASS_SCOPED_HIGH_COST_LIVE`。
- `output/worker-receipt.json`：实际合同、Unit/mode、source/dependencies/profile/image身份、guard/result/manifest SHA；live状态应为 `PASS_SCOPED_HIGH_COST_STATE`。
- `output/guard-receipt.json` 与 `native-events.jsonl`：真实入口计数、cap、全部返回情况、零拒绝/改写、关闭和属性恢复；metadata全部计数0，live优化器恰1。
- 起止资源JSON、image/container检查、`commands.jsonl`及stdout/stderr：硬资源和隔离的实际观察，不用单进程RSS替代cgroup峰值或反向替代。
- `result.json`、run/host manifests及科学产物：路径与每份字节SHA匹配；P11状态/XYZ/density及源进度，P12原状态JSON/XYZ/条件态NPZ及source-routing-review。P12 G原runner没有保存密度NPZ，不补造缺失证据。
- live前序的已完成host/worker receipts和只读输入快照：来源、依赖、profile、镜像一致，精确dependencies，原输出删除所属容器后仍保存；不能使用历史账本或仅通过预检的结果。

科学worker与宿主身份另行核对。科学镜像固定原干净构建提交05308a、107项源锁d8ee、镜像18dcd；当前宿主仅允许 `scripts/run-high-cost-case.py` 和 `tests/test_high_cost_supervisor.py` 两项覆盖，登记在 `locks/high-cost-host-launcher.json`，scope `HOST_FINAL_EVIDENCE_ONLY`，candidate锚定其SHA c10fb。其余105项原字节必须完全一致，宿主回执写独立 `host_launcher`，计算合同继续原科学身份。当前HEAD不能冒充原worker构建上下文；验证方法见用户指南。

修复前苯G原worker12项哈希及科学门禁/资源/清理/预算通过，但原host manifest的命令日志仅匹配22行旧前缀，最终为23行。原文件保留，50文件后补manifest补核当前字节；不能回写旧manifest或把后补当作原封存已经正确。修复后真实P11 ledger的42项宿主载荷完全匹配、科学计数为空，证明修复后的封存路径闭合，不构成重做苯G科学优化。


本轮实际补验见 [第三批验证报告](PROTOCOL_CASES_BATCH3_VALIDATION_zh-CN.public.md)：原预检、账本与工程记录保留；P11为1/17，P12为1/61。P12-N12-G的原科学门禁、资源、预算、两层manifest及删除后保留均通过。完整集合与组装仍NOT_EXECUTED，不将两个单态先导升级为全部科学完成。


## 当前环境补记：已恢复WSL默认配置（2026-10-09）

用户已撤销临时18GiB上限；原`.wslconfig`已移入备份，恢复原“无自定义配置”状态，WSL2／Docker服务自检通过。成功N12-G的18GiB启动条件、方法、结果与封存记录继续保留，是历史验收依据；不表示当前仍应用18GiB上限。


## 已通过状态的保留政策（2026-10-09补记）
