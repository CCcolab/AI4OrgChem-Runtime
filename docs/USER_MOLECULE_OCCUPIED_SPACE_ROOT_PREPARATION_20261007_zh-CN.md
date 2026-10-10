# 用户分子入口：单起点候选与零计算准备

2026-10-07。**本轮完成150项专项工程测试（40新增、110回归）和实际旧缓存零F准备；新增真实F/NR/SCF为0。** 范围限于固定乙烯技术夹具、一个初值和一条参考路径。实际root runner未实现，根搜索与新科学预算均未启动，Compute仍BLOCKED。

## 身份与来源

受测代码提交`7530595c71c0395c37f2e0e8669db14de5e14342`；前序交付`fae8a17d3ff44fa14f2c84b66a0570d0e1fa2dbb`保留。复用现有r3镜像`sha256:24f46f33264924e5d3d3bec386298585267c6f30d6e6a0cd0a6486ecf45db93d`，镜像构建runtime提交`5098775c9cf40468ab92712447a3e5c7b1361a63`，science提交`cc7437901119e71ef7945a12813c021c383e7648`、基线`28511f3d84fa65707a107cde1e8121a7b4334ecb`。新代码由干净提交导出并只读挂载，未重建镜像；收尾文档提交不冒充受测提交或镜像身份。

准备合同SHA-256为`9cb736eeda4aa2bde34e2fd80e750bc94a467741876d93472fb2065c6288c9fb`，schema为`occupied-space-single-start-root-candidate-contract-v1`。虽然execution_kind注明候选将来用途，其`scientific_execution_authorized=false`、`scientific_budget_reserved=false`被本版校验器硬锁；不能将字段名或用户“继续”当成当前实际root许可。

选择已保存seed2、θ=−0.10 rad、D身份`6b0d501aba96ac5c53ca633491e105d7c5dab13836350bd6d7350437f91bd7c0`；原始数组SHA`d1a6206219fcbbb8863ccc95d5cc0644f817f3b234fedd662689fde0c5c8828c`。来源两份JSON/两份NPZ、MDR-007与十二点历史结果共六份输入逐字节核对，随后按原完整配方验证全部四种子，再选择该固定D。选择是技术初值，不是科学选态、最低能量或普通态列空间保持声明；不冒用V2初始化。

历史−0.10参考点能隙约1.02640707877e−4 Hartree只作为旧证据登记。准备输出中的当前F、能量和operator ID为空；不从旧响应移用为CURRENT_INITIAL或尾检。实际准备绑定的root提案仍是0.1，正文已在revisions逐字节保留；当前0.2仅登记工程完成，不改旧合同字节。

## 新增实现与工程验证

新增九份代码/测试：隔离fake根候选、候选合同、host/worker准备入口、受保护测试runner及四份测试。此前科学源码、生产路径、旧参考求解器、profile、来源锁和阈值未修改。`occupied_space_root_candidate.py`继续复用NumPy/SciPy及原参考方程；原预算候选max_nfev实际为8，保持不动。新候选把调度明确缩至一chart、max_nfev=2，仅在fake模式使用。

原48个全局占据—虚变量的一组三点差分需要96个回调；进入Jacobian前先核对完整费用并预留两个尾检槽。复用已收费的基点f0，不偷偷补算。默认成本上限197=1次初始+2次objective+192次差分+2次尾检，适用范围仅14AO/16电子、上述参数和SciPy1.18.0，不是收敛保证。201为硬候选上限，包括失败回调和尾检；300秒/1GiB/1CPU/零swap只是拟定实际root进程的无效力元数据，未预约或确认足够资源。

只有SciPy正常返回且残差严格改善才更新正式返回D。best sample、基点和内部已接受但未返回的点只作诊断，不替代D；预算拒绝不自动追加尾检。检查SciPy1.18实现后确认其callback在新Jacobian之后，不能保证捕获Jacobian中断前的最新内部接受点；本轮不增加新的返回策略。旧2/0占据、屏蔽度量、Pmask(G)、十五类ERI、真F残差、全局raw-Aufbau及正能隙门槛全部保留，raw G只登记，不改成能量梯度。

专项150个唯一用例、150次执行全部通过，无跳过/重复/失败。新增15项候选、14项合同、6项supervisor、5项worker；110项相关回归。包含真实pinned SciPy对14×14人工矩阵完成两组96次差分、预算不足零差分、部分回调失败收费、返回语义、身份/源数组保护、全部旧尾检以及禁止LIVE执行。fake回调计数为356进入/355完成/1预期异常，来自显式计数器，不能算成科学F或跨旧回归层累加。

工程进程整个发现/测试/取证过程保持14个科学API guard，零命中、零绑定变化，原生F/NR/核能/SCF/网格/积分0。模块自身原生计数仍为UNOBSERVED；runner保护证据只适用于这次受测进程。fake快照VALIDATED只表示接口及身份检查，fake engine_qualified也不构成分子计算合格、稳定性或方法批准。独立静态审查只覆盖九份代码/测试及绑定的Git blob。

## 实际缓存准备与保留

host只接受`--prepare-only`，不存在`--execute`；worker同样先拒绝非准备模式。实际UID/GID10001、只读根文件系统/源码/缓存/六输入/合同、断网loopback平台快照均通过。worker保持34个NR、核能、SCF、积分、旧/新求解器和Jacobian guard；没有callback journal、科学预约或任何求解调用。supervisor核对完整哈希、固定D、六输入绑定、四种子配方、34个唯一guard及严格整数零计数；退出0或文字PASS不能单独认证成功。

实际准备约15.187秒含清理，资源范围仅ZERO_F_PREPARATION_ONLY，不能外推197/201次root、其它分子或研究容量。只读后处理以标准库核对三组JSON/NPZ和11个NPY成员的shape/dtype/真实负载哈希、有限性及选定density-v1；全部通过。

首次受限终端工程启动在创建容器前失败，原记录/源导出/预算快照保留；系统许可下的人工第二次工程运行通过。另核对失败启动的拥有标签无遗留容器并关闭其工程墙钟预约，保留原快照。两个实际工程/准备容器退出0后删除，日志和输出保留；没有自动科学重试。没有重算旧12/9/591F，不重新打开旧12/9/603预算。

## 未完成事项与边界

实际root runner和源原生201槽记账尚未实现；根搜索、当前初值新F、返回/映射真F尾检均NOT_EXECUTED。本版合同拒绝真实执行。未来如推进，需另行授权和版本，接入真实逐次计数、独立科学预算及实时准入；本轮不自动开展。根存在性、收敛、最终gap、唯一性、驻定/稳定性与研究解释仍未知，不能因fake通过宣布用户Compute可用。

最近真实科学记录仍为[十二点响应](USER_MOLECULE_OCCUPIED_SPACE_RESPONSE_20261007_zh-CN.md)：12个点gap通过、comm/map失败，没有合格自洽端点。旧完整W01—W07本地CI不自动覆盖本次增补；本轮完整CI和GitHub Actions均NOT_EXECUTED。外部专家流程CANCELLED_BY_USER，具体科学/资源证据尚缺与取消咨询分开。


[机器记录](../validation/user-molecule/occupied-space-root-preparation-20261007.public.json)与[MDR-008](../validation/user-molecule/method-decisions/mdr-008/record.json)给出详细身份。本地记录和备份在`D:\AI4Science\ai4orgchem-runtime-deliveries\20261007-user-molecule-occupied-space-root`。
