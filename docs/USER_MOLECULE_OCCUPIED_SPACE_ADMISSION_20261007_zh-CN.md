# 用户分子入口：确定性占据空间初值与模拟准入

2026-10-07。本轮已构造四个新的全局闭壳层初值，97项专项工程测试和四密度×三路径12次模拟回调通过；**真实新F/NR/SCF/网格/积分为0**。Compute仍BLOCKED。真实十二点响应和固定点搜索未实现、未执行，不将数组准入称为科学验收。

## 范围和来源

本轮在隔离分支继续，基线`34f115723d8537759259bee7279a7cfb61ea54d2`，实际受测源码`029cd557f2a858051a4f98d34cadc981b932346c`。复用r3镜像`sha256:24f46f33264924e5d3d3bec386298585267c6f30d6e6a0cd0a6486ecf45db93d`，镜像构建runtime提交`5098775c9cf40468ab92712447a3e5c7b1361a63`，science提交`cc7437901119e71ef7945a12813c021c383e7648`；当前源码以已提交的只读挂载执行，未重建镜像。原项目及原runtime工作区未切换、重置或清理。前轮九点诊断及原失败保持，最新真实数值记录仍为[九点响应](USER_MOLECULE_OCCUPATION_RESPONSE_20261007_zh-CN.md)。

来源D是九点响应中`AO_ANCHOR_SYMMETRIC_SUM / production_copy`保存的单点密度，density-v1 ID为`bde824cc2957779325a8f8c2fb53fb626970c55b757285a1da4a69fdb92b4faf`。该D未通过科学固定点验收；其历史算子身份仅表示祖先，**不作为任何新D的F或能量**。来源JSON、NPZ、所有102个已读取response/mask成员及旧1471载荷清单先核对，导出仅含D、两种S、mask和两个anchor六个小数组，不携带网格/ERI到模拟容器。身份对应、每个新D和实际导出字节见[机器记录](../validation/user-molecule/occupied-space-admission-20261007.json)。

Profile需区分三种身份：执行导出LF原文件SHA-256为`18bd594a8b606ef2c90db4390243155031035cd98fbe72dfc2e9367aeadce2e9`；canonical JSON SHA-256为`5c78ef8e741b255421a465895524cdb7aa208ef90751a1524eff9c7f88e5d537`；当前工作区CRLF文件SHA-256为`c3359c80f2b292c14875335b8e14a22e37f35858581402b0b47e0f20c6884f45`。本轮保存的SOURCE和fake账本中`profile_sha256`是canonical JSON别名，已另存`PROFILE_IDENTITY_CLARIFICATION.json`澄清，原执行记录不回写。后续正式科学合同分别记录canonical和实际执行文件哈希。

## 构造与原规则的关系

令H=S̃^(1/2)，X=S̃^(-1/2)，P=HDH/2。固定AO占据anchor为`e4+e9`（两个碳pz，零基索引），虚anchor为`e2+e7`（两个碳px）。u由`PH a_occ`归一化，v由`(I−P)H a_vir`投影、移除已核查≤1e−10的u方向正交舍入后归一化；只处理所选方向，**不净化、重构替换或修补P/D/S**。投影比例必须大于1e−12，这是数值方向准入，不是最终科学门槛。

固定角度θ=−0.25、−0.10、+0.10、+0.25 rad，按顺序取t=cosθu+sinθv，Pθ=P−uuᵀ+ttᵀ，Dθ=2XPθX。方向不使用F本征向量、能量排序、随机数、MOM/IMOM或片段配额，没有失败后的anchor替换。

原全局2/0流形允许σ–π占据—虚轨道旋转：固定xy几何用于AO分类，现有h/S/F及ERI条件规则没有强制电子密度D的σπ块为零。当前夹具测得u的σ泄漏约1.894e−15、v的π泄漏约1.431e−15，虚anchor有效投影比例约0.618826；generic函数本身不保证π/σ分类，其他体系须重新验证标签和方向。

四个Pθ仍为秩8的0/1投影，MO占据仍2/0；局部π权重cos²θ不能称为分数MO占据。新初值改变原占据列空间，因此是**独立初始化诊断候选**，不叫V2，不宣称保留普通态占据空间。V2包装器和旧bridge的启动路径不能直接冒用。条件算子、全局Aufbau最终目标、最终能隙≥1e−6 Hartree及所有旧门槛保持。

## 数组检查结果

所有密度独立通过原白化迹/绝对幂等≤1e−10、电子数≤1e−7及生产重构≤1e−10检查。下面是实际观测误差；屏蔽电子数均约16，原AO电子数另列，网格电子数NOT_EXECUTED。

| θ / rad | 白化迹误差 | 白化绝对幂等 | 重构相对差 | 原AO电子数 |
|---|---:|---:|---:|---:|
| -0.25 | 3.109e-14 | 1.623e-14 | 3.283e-15 | 16.445490691 |
| -0.10 | 3.109e-14 | 1.614e-14 | 3.170e-15 | 16.469806892 |
| +0.10 | 2.931e-14 | 1.601e-14 | 3.489e-15 | 16.469806892 |
| +0.25 | 3.109e-14 | 1.618e-14 | 3.386e-15 | 16.445490691 |

另以K=vuᵀ−uvᵀ、R=I+sinθK+(1−cosθ)K²复核`RP Rᵀ`，投影Frobenius差约9.4e−15—9.8e−15，密度相对差小于9e−16。该独立表达式只检查旋转代数，没有验证科学求解器。±θ的z反射密度关系残差约1.94e−14—2.03e−14，仅为数组关系，未判断同根、同能量或物理稳定性。

## 模拟准入和实际测试

真实F前的配方核查目前仅在fake适配器实现：先核对来源D/S/anchors实际字节与density-v1/array identities，再独立重生成全族、精确比较完整canonical记录；对调两个合法D并同步其哈希、换合法投影、换anchor并同步身份、伪改派生检查都在首次回调前拒绝。核对只验证，不替换实际输入。

只有`ENGINEERING_FAKE`模式可进入。每路径4槽、合计12槽，seed外层/路径内层；每次回调前收费，异常或非法快照保留FAILED槽并停止整批、关闭所有路径，不退费、不自动重试、不追加尾检。KeyboardInterrupt也收费、关闭后传播。prepared对象防复用仅覆盖同一对象/同一进程，不覆盖深拷贝、重建或其他进程，不构成内容级持久化去重或科学授权。

模拟例使用明确的任意NumPy toy：G=diag(linspace(−0.9,0.7,14))+0.03125D，F=Pmask(G)，E=Tr(hD)+0.5×0.03125Tr(D²)，没有分子XC、核排斥或网格求值；grid count是显式Tr(S̃D)占位。12快照均标ENGINEERING_FAKE；旧wire `TRUE_CONDITIONAL_AT_REQUESTED_DENSITY`仅为接口的callback声明，另有synthetic证据标识，不能截取为分子算子证据。8组同D三路径字节比较仅验证模拟接线，不是T05/UM-P12/UM-P13/T06。

专项共97个唯一单元用例（29新项＋68相关回归），全部通过，无跳过。新adapter单元测试实际59次fake回调进入、57完成、2次预期抛出；独立导出示例12进入/12完成/0失败。它们与native F/NR分列，其他回归层不从测试数量推算回调数量。两轮共194次测试执行，不能写成194个独立用例。源数组10个、模拟结果84个NPZ成员及12个模拟operator IDs已用宿主只读脚本逐项核对。

第一次a1的97测试通过，但示例账本参数名错误导致TypeError，未创建示例账本、未进入示例回调；整个a1为FAIL。修正本地示例的keyword-only path/batch_id后，新a2测试＋示例整体通过。旧日志和脚本原字节保留。a1 supervisor中的native count原为null；其13 guards实际零命中证据支持本轮派生零调用结论，不回写旧记录。

两容器均使用1CPU/512MiB/零swap、断网、非root10001:10001、源码和输入只读，tmpfs仅存测试夹具，输出另挂载并在容器删除后保留。13个科学API guards从discover、测试到示例/收集均保持、零命中；模块本身仍记录native counts为UNOBSERVED/null，由实际guard回执另证0。a2墙钟含清理11.110秒；实际memory.peak不可读，因此峰值未观测，不宣称科学资源资格。

## 下一步和仍未完成的工作

[十二点真实响应设计](../validation/user-molecule/occupied-space/response-proposal-v1.json)只登记下一轮提案：新单进程4密度×3路径，每路径4/合计12次F，不开SCF、Jacobian或F(mapped D)。候选上限120秒/1GiB/1CPU/零swap来源于前轮精确夹具单次响应资源记录；本轮fake成功不能转移为这项科学执行批准。真实worker/schema、执行提交/合同哈希、源级NR计数和实时资源准入尚未形成，没有创建科学预算。旧9槽与603槽预算均关闭、不得补充。

随后才根据真实单点记录设计受限根搜索，须显式initial-D包装器及预算感知求解器。每初值201F意味着单路径四初值804F、三路径2412F，不能直接复制旧201/603限额或自动多根扫算；须另冻预算并保留整Jacobian与返回/映射端点尾检费用。当前未知其他合格根是否存在、能否收敛、驻定性/稳定性，以及科研能差允许用途；不把本轮初值准入视为这些问题已解决。

外部专家流程维持CANCELLED_BY_USER，不要求外部角色或意见，也不将缺少意见作为阻塞。Compute因缺合格端点、完整实现等价性及研究/资源范围保持BLOCKED，科学能差null。完整W01—W07本地CI本轮NOT_EXECUTED，远端GitHub Actions NOT_EXECUTED；WSLc暂停BLOCKED/NOT_EXECUTED，镜像分发BLOCKED，无WSL升级、镜像重建或公开推送。原P01—P14不重算、不自动重审；L4只支持保存检查点、不支持恢复运行。

本轮结果、输入澄清、静态核查与备份在`D:\AI4Science\ai4orgchem-runtime-deliveries\20261007-user-molecule-occupied-space-admission`，独立本地增补提交供审阅，不改变此前源码公开候选。
