# 三密度单次条件算子响应：实施与诊断

2026-10-07。本轮已实现单次响应入口，完成101项专项工程测试和实际缓存零F准备，并在**一个新进程中执行三密度×三路径，共9次真F/NR**。九次均完成，零SCF迭代；六个同D算子/账本子集对照通过原阈值。**九个单点均未通过其数值谓词，未形成合格固定点，Compute仍BLOCKED。** 原科学算子、占据及最终门槛未改，旧失败和预算保留。

## 实现入口与调用范围

新[纯数组预检与编排器](../runtime/user_molecule/occupation_response.py)对全部三份密度先做有限性、对称、PSD/白化投影、屏蔽电子数、白化迹/绝对幂等和生产重构检查，保留原1e-10等准入阈值。通过后，每个probe依次由COPY、OWNED、独立参考各求一次F，执行前预收费；异常或数据/身份拒绝即停止全批，失败槽不退款，不补齐或自动重试，全部路径关闭。

新[stdlib合同](../runtime/user_molecule/occupation_response_contract.py)固定已封存的两生产来源审查材料和70项NPZ成员身份，实际采用COPY来源的A/B/对称和三份明确密度。合同先核对全部成员字节，再由实际NumPy预检核对矩阵条件。它是输入/版本声明核查，不以哈希代替用户授权、分子引擎认证或科学方法批准。

[监督器](../scripts/diagnose-user-molecule-occupation-response.py)默认只执行零F准备；`--execute`须有相同受测提交及源文件字节的实际准备回执，另建一次120秒/9槽预算。新[worker](../scripts/diagnose-user-molecule-occupation-response-worker.py)复用`prepare_cached_context`，恢复旧basis表示并挂接旧网格/积分；直接调用既有`PreparedResidualBridge.evaluate`和`PreparedResidualReference.evaluate`，**不调用run、SCF、求解器、Jacobian或V2种子流程**。

外层模式为`PREPARED_SINGLE_F_RESPONSE_DIAGNOSTIC`，内层复用原prepared molecular callback类型；未改名或绕过预算工程候选的ENGINEERING_FAKE限制。COPY继续使用`COPY_MASK/optimize=True`，OWNED使用`INPLACE_OWNED/optimize=False`。源码、缓存、profile、规则、AO/原子映射、实际屏蔽度量和环境版本分别核验。

## 工程验证与失败记录

| 专项组 | 独立用例 | 结果 |
| --- | ---: | --- |
| 新响应编排器与零F预检 | 19 | PASS |
| 新输入/执行合同与封存字节绑定 | 20 | PASS |
| 原生产prepared bridge | 21 | PASS |
| 原独立prepared reference | 12 | PASS |
| 原持久化回调预算 | 12 | PASS |
| 原候选求解器/数值门禁 | 17 | PASS |
| 合计 | 101：39新增、62回归 | 专项工程PASS，完整W01—W07未重跑 |

测试执行提交`616be48`。13个SCF/grid/intor/NR guard在测试全程保持，未触发。模拟wrapper计数为96进入、94返回、2预期异常；它们不是原生NR计数。实际科学操作为0。测试在512MiB/1CPU/零swap/离线/只读源码容器运行，含日志及删除约16.172秒。

首轮`b8e9c29`的测试夹具漏写持久化预算要求的geometry/profile/dependency身份字段，账本构造即拒绝，19项测试组FAIL，未进入科学或模拟回调。修正仅涉及该测试fixture，原失败JSON、完整日志和删除回执保留，复验使用独立`engineering-a2`目录；没有改科学门槛以使测试通过。

实际缓存的零F准备在相同`616be48`提交下通过：三路径屏蔽度量与probe来源一致，三个密度全部准入，NR/核能/SCF/新grid/intor为0，无科学callback账本，工程进程约8.625秒。准备的约199.28MiB峰值仅覆盖metadata与数组准备，不能移作SCF容量结论。

## 实际九次响应与账本

科学批次合同SHA-256为`136997ce546821d22c3da1ec4db9959abffd234c67984ac1ce6f453151a5f050`，新预算9槽全部SUCCEEDED、0PENDING、0FAILED，三路径CLOSED。每次源回调进入前均核验PENDING槽、path/probe/D身份及单槽最多一次NR；原生NR和核能分别在进入、完成或失败时落盘，不从slot数推断调用。

| 原生操作 | COPY | OWNED | 独立参考 | 合计 |
| --- | ---: | ---: | ---: | ---: |
| NR进入/完成 | 3/3 | 3/3 | 3/3 | 9/9 |
| NR失败 | 0 | 0 | 0 | 0 |
| 核能进入/完成 | 3/3 | 3/3 | 0/0，使用缓存 | 6/6 |
| 新普通态SCF/grid/full integral | 0 | 0 | 0 | 0 |

科学进程采用1GiB/1CPU/零swap、非root、离线、只读源码/缓存；120秒累计预算包含收尾，实际约**10.187秒**，峰值**241479680字节（230.29MiB）**，无观察到的OOM或限额失败。容器退出0、删除，全部日志与输出保留；没有第二次科学进程、追加槽或尾检。资源结论只覆盖本夹具三密度九点流程，不外推SCF迭代或一般用户规模。

## 单点结果说明了什么

以COPY数值作紧凑展示，完整三路径及每个谓词见[机器记录](../validation/user-molecule/occupation-response-20261007.json)：

| 固定密度 | 真F gap / Eh | 对易Frobenius残差 | raw-map相对残差 | 结果 |
| --- | ---: | ---: | ---: | --- |
| A片段π锚 | 0.302748399 | 0.471590463 | 0.641788559 | gap通过，但对易/映射失败 |
| B片段π锚 | 0.302748399 | 0.471590463 | 0.641788559 | gap通过，但对易/映射失败 |
| A+B对称和π锚 | 5.4123e-16 | 8.6969e-10 | 0.439382414 | 对易通过，gap/映射失败 |

原门槛分别为gap≥1e-6 Eh、对易≤1e-5、raw-map相对及绝对≤2e-8，均未放宽。A/B方向说明**正gap本身不足以接受一个条件态**。

在正确白化π投影内，A输入占据约[1,0]，它的raw Aufbau映射指向约[0,1]；B输入和映射相反。保存的是一次F(D)及一次代数映射，**没有求F(Dmapped)**；mapped全密度还改变σ部分，不能把这个π层面的反向关系叫作已观察到的SCF两周期，也不能据此证明其他根不存在。

对称probe在三个路径的gap约为5.41e-16、9.71e-16、1.03e-15，raw-map相对残差约0.4394、0.4382、0.4271。三个路径的同D真F/G在原容差内一致，而近简并边界的单条特征向量方向会对有限精度敏感。这些不同映射数值不构成条件算子不等价或已完成端点同根比较；原结果均保留。

三个probe×两对路径的六份同D比较均通过既有F/G矩阵、五项能量、总能量及网格电子数子集阈值，F/G最大逐元差约3.55e-15。这个结果不替代完整T05（包括原零mask项/独立标量项）、UM-P12/UM-P13或T06合格端点验收；三条实现仍共享PySCF、XC与原始积分，并非独立科学方法验证。

电子数进一步分列：A/B约为屏蔽16、原AO16、grid16.000002851；对称probe为屏蔽16、原AO16.474536460、grid16.474537339。原AO与grid计数的接近不能证明它们都等于输入16。输出保存的是各固定密度上的未合格条件能量值，不提供跨probe科研δ、物理基态或单键测量解释。

## 证据核验、身份与后续边界

九份匹配D/F/G、五项能量和operator-ID逐项重建；原生source capture、prepared ledger、预收费账本和最终snapshot对应。导出后宿主核验12份JSON/NPZ、全部161项成员字节/shape/dtype/finite；内部独立只读核查也复核了30条原生事件和同D矩阵差。核验不追加F，不补填旧端点gate，不把保存mapped D视为新真算子结果。

实际受测/执行源码为`616be48fb841d4711da42b07793f4bfa90ba40c6`；科学源码仍`cc7437901119e71ef7945a12813c021c383e7648`，r3镜像仍`sha256:24f46f33264924e5d3d3bec386298585267c6f30d6e6a0cd0a6486ecf45db93d`，镜像构建runtime提交仍`5098775`。后续报告/状态提交与这些身份分别登记，没有重建镜像。

[MDR-005](../validation/user-molecule/method-decisions/mdr-005/record.json)保留原正gap全局Aufbau目标，明确本轮仅排除了把这三份probe直接当作合格端点的做法。其他根存在性、不同初始占据空间的收敛、稳定性及研究适用性仍未知。**下一步是依据现有证据开展内部占据/固定点搜索准入设计；本轮9槽预算已关闭，不自动追加F或SCF，不以改占据规则或降低门槛补通过。** 如另提科学目标，须独立版本，不覆盖本轮失败。

全部材料保存于`D:\AI4Science\ai4orgchem-runtime-deliveries\20261007-user-molecule-occupation-response`；此前四包1729项载荷和132份既有代码/配置分别核验保留。当前新增入口不接入生产Compute profile。

本轮共四个容器（首轮失败工程、复验工程、零F准备、唯一科学诊断）全部删除；首轮退出1，其余退出0，日志输出保留。完整本地W01—W07 CI本轮NOT_EXECUTED，远端Actions仍NOT_EXECUTED；WSLc继续暂停/BLOCKED，WSL未升级、全局配置未改、电脑未重启；镜像分发BLOCKED，未推送、打正式标签或发布Release。外部专家流程保持CANCELLED_BY_USER，原P01—P14及L0—L4未重算；L4仍只保存检查点，不支持恢复。
