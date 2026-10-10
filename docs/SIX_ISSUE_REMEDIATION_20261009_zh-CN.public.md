> 当前公开阅读节选。原始历史材料已按原字节保存在本地归档；本文件不是原件，不能用于原始哈希验收，也不把旧验收转移至当前代码。
> 原件 Git 提交：eb65b4586c83637569f6359814338c1292948861；SHA-256：d045e8c95af63dfde6013d0f3998ecb0094d7f5a5e46eb49cd302a8f9a9f72de。

# 六项问题的本轮处置与剩余边界


| 原问题 | 已完成 | 尚未闭合 |
| --- | --- | --- |
| 1. 第三批完整科学验收 | 78态工程登记/路由保留；P11苯G与P12-N12-G历史PASS保留；76态依赖无环已核对 | P11剩余16、P12剩余60的Runtime实际重放及完整账本组装未执行。这是验证范围限制，不是缺76个功能；原项目冻结结论不自动重审 |
| 2. P12资源门槛 | 明确15GiB为旧Docker统一合同，非固有需求或日常默认配置；九档关闭候选及27项禁用拒绝模拟形成；原生WSL2可行性和Check通过 | 低内存档未实测/未启用；原生Compute需独立资源、workspace与任务封装。原 `max_memory=12000` 与低cap衔接仍需处理 |
| 3. Docker重复启动错误 | 默认健康检查不改动；三次受限重启、10镜像身份保留及活动容器拒绝通过 | 已有可验证维护路径，厂商底层根因仍未知；不自动升级、禁用模型服务或清理数据 |
| 4. 默认WSL配置与报告不一致 | 当前记录恢复无自定义 `.wslconfig`；18GiB只保留为成功先导的历史启动条件 | 已闭合。当前容量快照仅涉及未来未执行态，不重新否定保存PASS |
| 5. 来源/许可与安装交付 | 实际23发行包、50项License-File、254既有源码归档及新增纯Python来源补证；紧凑附录入仓 | 原生库精确构建对应、Amadeus再分发授权、RDPaths生成来源及分发机制仍缺；源码ZIP不是完整安装程序，异机安装NOT_EXECUTED，镜像分发BLOCKED_LOCAL_ONLY |

## 已通过P12的保留政策

P12-N12-G继续PASS，不重算、不重复内存预检、不把新容量快照当作旧验收的新条件。其2721.5秒、3.7136GiB峰值和原身份/日志按历史记录保留。本轮后续只有工程模拟与只读来源查询，没有追加P12资源探针或科学预算。

旧Docker合同继续用于其未来未执行任务；新资源档独立版本、当前禁用。不能把N12-G峰值直接推广到条件态、N14、N16，也不把源PySCF `max_memory` 当作实际已分配内存。

## 普通WSL2、Docker与网页

浏览GitHub、静态指南和保存结果，不需要运行WSL2或Docker。实际本地计算才需要后端；当前已记录科学验收主要对应Docker候选。新的 [原生WSL2 Check](NATIVE_WSL2_RUNTIME_zh-CN.md)只核对环境与显式来源，独立身份 `image_id=null`、Compute关闭，不能冒充Docker科学资格。


下一步原生任务工程按 [可行性核查](NATIVE_WSL2_FEASIBILITY_20261009_zh-CN.md) 和 [原生入口准入](NATIVE_WSL2_RUNTIME_zh-CN.md) 实施：只读快照、任务输入输出、来源/依赖身份、进程生命周期及独立资源策略。尚未完成时不能直接调用硬绑Docker环境的冻结worker。

## 证据与身份

- [CI增补与失败/最终记录](LOCAL_SERVICES_CI_20261009_zh-CN.md)：440个独立工程用例；唯一SKIP保留，不计PASS。两次测试环境失败未覆盖。
- [Docker启动维护](DOCKER_STARTUP_RECOVERY_20261009_zh-CN.public.md)：操作范围、保护条件和三次重启。
- [许可与对应源码附录](../compliance/HIGH_COST_COMPONENTS_20261009_zh-CN.md)：当前镜像分发缺口，不覆盖所有历史镜像。
- [P12资源候选](P12_RESOURCE_TIERS_CANDIDATE_zh-CN.public.md)：设计参考，不是已验收配置。
- `validation/high-cost-cases/support-matrix.public.json`：保存科学PASS和未来资源状态分列。

科学worker仍为构建提交 `05308a1872d769aaa85e39adbafe7020e36358e6`、镜像 `sha256:18dcd1da2e634cf6ab8d49a7281ca853c0a393e140ac95c6ec00448a3fc934bc`、来源锁 `d8ee6bb0b7880db0f6d40dd38d93b633e1400ff6995f4e56e07042fddd6e7322`。实际先导宿主提交、当前维护源码与镜像构建身份分别记录；本轮只读挂载运行工程测试，没有重建镜像或把新提交写成旧构建提交。

全部新记录在 `D:\AI4Science\ai4orgchem-runtime-deliveries\20261009-six-issue-remediation`；旧候选、原工作区与封存记录保留。源码公开范围仍另行确认，新的本地提交/ZIP/备份不等于公开授权。外部专家咨询保持用户已取消状态，不重新列为前置。检查点继续仅保存、不支持恢复运行。
