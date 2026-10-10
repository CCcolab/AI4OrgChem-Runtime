> 当前公开阅读节选。原始历史材料已按原字节保存在本地归档；本文件不是原件，不能用于原始哈希验收，也不把旧验收转移至当前代码。
> 原件 Git 提交：eb65b4586c83637569f6359814338c1292948861；SHA-256：c79df7edfe160a2614b8a702c49cece25e4ca119a6a451dd8668d615703b7103。

# 2026-10-02 候选环境实施与验证报告

本文件为分阶段历史报告。2026-10-03 最终交付审查与当前结论见 [DELIVERY_REVIEW_2026-10-03_zh-CN.md](DELIVERY_REVIEW_2026-10-03_zh-CN.public.md) 和 final-delivery-status.json；下文的阶段性 NOT_EXECUTED/UNKNOWN 保留对应时间语义，不能替代后续最终记录。CI 仅静态审查，未执行；发布许可问题仍未结案。

## 后续授权的 L3 实测更新

用户完成首次使用后明确授权启动 L3。本地 Docker 候选 p14-fixed 已完成，manifest PASS、退出码 0，全部输出哈希复核一致；原始记录位于 `D:\AI4Science\ai4orgchem-runtime-runs\20261002-l3`，小型汇总见 [l3-summary.json](l3-summary.public.json)。下文未运行 L3 的陈述保留为此前阶段历史，本节更新其当前 Docker 状态。

CPU 为 Intel Core Ultra 9 185H，16 物理核心/22 逻辑处理器；容器 affinity 22，本次请求 8 线程，运行中 CPU 采样 798.87%（约 8 个逻辑处理器的计算量），容器内存采样 5.077 GiB。启动前有效可用内存约 14.35 GiB，无 cgroup 限额；科学进程实际峰值 RSS 8800.86328125 MiB（约 8.60 GiB）。耗时 54.369574647 秒，约 0.015 小时。本次结果不能保证以后不同负载同样耗时或峰值。

12 项上游 anchor 资格全部通过，固定几何端点 67.08689934803395 kcal/mol；来源报告端点 67.08，残差 +0.006899348033954311 kcal/mol。G/PLG 来源能量残差分别 +0.009631057372416763 Eh、+0.009621278124541277 Eh。anchor PASS 不包含文献残差合格门禁，不认定完全重现或最终科学分类。未修改科学规则或容差。






## 阶段状态

| 阶段 | 状态 | 依据 |
|---|---|---|
| A 来源/入口/平台核查 | PASS | 固定标签与 SHA、归档与 588 文件哈希、源码审查和平台工具记录 |
| B 构建工程与依赖锁 | PASS（本地 OCI） | 固定来源与 17 wheel 锁，从干净 runtime 仓库实际构建成功 |
| E L3/L4/本次联合分类 | PASS（本地 Docker） | 后续明确授权已实跑通过；见 l3/l4/classification-summary.json |

## 已执行结果

独立候选 Python 3.12.13，NumPy 2.5.1、SciPy 1.18.0、PySCF 2.14.0；完整 17 依赖见锁和运行 manifest。源 commit `28511f3d84fa65707a107cde1e8121a7b4334ecb`，上游包版本 `0.1.0`。最终 LF 依赖锁摘要 `a8dbe44d12930427ca1f377b17eba3fcdb17b6dd922737884b3b77d0d9c4ea71`。首次记录摘要 `7145fe7b4e9e0444920d4f3ba86d0a22c58fee9c4248a7b1de23e4e68bf37c6b` 对应 Windows CRLF；提交前只归一化锁文件换行以保证干净检出稳定，版本与 wheel 哈希没有改变。

| 项目 | 实测 |
|---|---|
| pip check | PASS：独立 venv 离线哈希安装 |
| runtime 单元/过程测试 | PASS：最终 Linux 12 项全通过；含分类器冻结样例路径适配测试与真实 CLI 缺输入拒绝 |
| L0 | PASS：十四项、P12、导航、P14 底层证据全部核验 |
| L1 | PASS：三份原测试共 11 项 |
| L2 | PASS：15/15 自身数值资格，最终复验 12.31 秒，峰值 RSS 547.88 MiB |
| STO-3G 等价性 | PASS；第一次源码缺失预检 FAIL 保留 |
| 源码/证据 | 只读、任务前后 588 个文件哈希校验一致 |
| 输出 | 与源码目录分离，在 Windows 宿主持久目录保留 |


## 已提交代码的最终复验

实现提交 `c2cc5027d25defa32338b04cda577285dcc06cf9` 在干净 runtime 工作区完成复验，四份新 manifest 都包含真实 runtime commit 与代码/锁快照摘要 `7aece0641285de490a4ff59a605b5684fbad305482ffc8daf63a093663d20762`。本报告和汇总的后续提交只更新文档/验收摘要。

| task | 最终运行 ID | 结果 |
|---|---|---|
| evidence | 20261002T105729Z-evidence-7262f14bf797 | PASS |
| core-tests | 20261002T105731Z-core-tests-84c2141cb412 | PASS，11 原测试 |
| p14-smoke | 20261002T105733Z-p14-smoke-6358690e4876 | PASS，15/15 |
| p14-equivalence | 20261002T105746Z-p14-equivalence-5d389d942d59 | PASS，13.84 秒 |


原始日志目录：`D:\AI4Science\ai4orgchem-runtime-runs\20261002-wsl2`。首次三个运行 ID：`20261002T104043Z-evidence-ab57bf8dbabf`、`20261002T104045Z-core-tests-6b8796c8ba75`、`20261002T104047Z-p14-smoke-afbe6f3bce33`。这些在首次提交前执行，runtime_commit 为 UNKNOWN，未伪补写。后续已识别提交的执行记录另行汇总，不覆盖历史 manifest。

等价性首次预检失败 ID `20261002T104545Z-p14-equivalence-126b8b2e7cd6`：旧 `/tmp/...` 源码目录已不存在，588 文件缺失，未进入科学计算。重新获取同一固定归档到新持久 Linux 目录后运行 `20261002T104918Z-p14-equivalence-26d968497afa` 通过。没有修改哈希规则、数值规则或容差。

## 启动 Docker 前的历史阻塞与限制（由末节更新 OCI 状态）


Docker Desktop 已安装但未启动：无相关后台进程，两个引擎管道都不存在；沙箱外 status 仍报告未运行。OCI 构建/容器验收 BLOCKED、实际构建测试 NOT_EXECUTED。未启动 Desktop、更新 WSL、启用系统功能、修改全局配置或重启。具体恢复步骤见 INSTALL_zh-CN.md。


L4 写检查点但不能 resume；过程测试证明封装中断保留已写检查点，尚无完整 L4 实跑中断证明。分类器路径适配已实现；本次四份新科学结果未齐，联合分类 NOT_EXECUTED，缺输入拒绝已经测试。


## 用户授权后的 Docker OCI 最终验收

Docker Desktop 4.78.0（229452）已启动，Docker 客户端/服务端 29.5.3，desktop-linux、Linux/amd64。从干净 runtime 提交 `f30b2906794d14f9030daab779c0d6a7cd4bd6f7` 构建，无同级原项目依赖。

候选 tag：`ai4orgchem-runtime:oci-candidate-20261002`；本地镜像 ID/索引摘要：`sha256:ddc45b1fe500ed3d5ed30520eb4e49f3969cb69f02121f28e2ff851f7a724f54`。这是本地构建身份，尚无公开 registry 发布。四份运行均记录源码提交、runtime 提交、代码快照、依赖和镜像身份，详见 [OCI 汇总](oci-summary.public.json)。

| 项目 | 最终实测 |
|---|---|
| L0 / L1 | PASS；冻结证据校验 / 11 项原核心测试 |
| L2 | PASS，15/15；端点 26.47160532579993 kcal/mol |
| 同层冻结值及 WSL2 最终端点残差 | 1.426791129688354e-09 kcal/mol |
| STO-3G 等价性 | PASS；总能差 2.2737367544323206e-13 Eh，密度 Frobenius 差 6.226066644162052e-13 |
| 非 root、源码/证据只读 | PASS；USER 10001:10001，写打开被拒绝，588 文件任务前后哈希一致 |
| 离线 / 路径 | PASS；--network none，中文与空格 bind 目录 |
| 退出码 | PASS；任务退出 0，合成进程实际退出 37；封装传播由过程测试覆盖 |
| 真实 256 MiB 限额 | PASS；cgroup 剩余 258629632 字节，errors=[]，资源 helper 显式 MemoryError 退出 1 |
| 删除容器后保留输出 | PASS；四个容器已不存在，四份 manifest 与全部输出 SHA-256 复核 |
| 封装测试 | PASS；Linux 容器 12 项全通过，无跳过 |


首轮镜像验收通过后发现混合 cgroup 挂载识别问题：存在有效 v1 memory 控制器及未挂载的 v2 membership，封装保守报告 UNKNOWN。修正仅在有效 v1 可读时采用其限额，缺失/不可读控制器仍拒绝；新增回归断言后从干净提交重新构建并完整复验。中途一次 PowerShell 括号语法错误在运行前失败，已修正，错误日志未删除。

原始目录：`D:\AI4Science\ai4orgchem-runtime-runs\20261002-oci`。保留 engine-version.log、两次 build-attempt 日志、cgroup-diagnostic.log、acceptance-01/02 历史与错误记录；最终为 acceptance-03 目录及 acceptance-03-console/error.log。构建仅有固定 linux/amd64 的 Dockerfile lint 提示，无构建失败。小型汇总入 Git，大日志/结果仍独立保留。


## 后续授权的 L4 实测更新

用户授权的 Docker p14-optimize 完成，manifest PASS、程序与封装退出码 0；18 项上游 production 资格全部通过。G 和 PLG 优化器均成功，未触及参数边界，梯度满足原协议容差。耗时 1272.177734144 秒（21.20 分钟、0.353 小时），峰值 RSS 8801.19921875 MiB（约 8.60 GiB）。请求 8 线程；启动初期 CPU 采样曾为 1547.50%，不能将请求线程数描述为强制 CPU 上限。

优化端点 67.67971905631804 kcal/mol，d_delta_r_GP 为 0.1722036356645249 Å；同层冻结值对照残差单列于 [l4-summary.json](l4-summary.public.json)。全部 manifest 输出 SHA-256 复核一致，checkpoint.json 保留，launcher stderr 为空；原始目录 D:\AI4Science\ai4orgchem-runtime-runs\20261002-l4\20261002T123346Z-p14-optimize-d7f348003891。


## 四份新结果联合分类完成

后续授权联合分类运行 20261002T144015Z-p14-classify-675fab20a66f 已完成。实际输入为本次 smoke 20261002T115757Z-p14-smoke-5edcc0ade184、等价性 20261002T111600Z-p14-equivalence-a83e2e3a8f2f、L3 20261002T123033Z-p14-fixed-d621c0cfab97、L4 20261002T123346Z-p14-optimize-d7f348003891，全部输出哈希预核对一致。四份 manifest 均为 PASS、源与 runtime 提交相同；入口另核对协议、输入哈希、依赖版本及 result 哈希。未用冻结 JSON 替代本次输入，未修改科学分类规则。

manifest、decision_verdict 均 PASS，退出码 0，13 项 decision_checks 与 19 项 optimization_eligibility_checks 全部 true。分类 consistent（与原著一致），限定于冻结的 C12H6 来源代理和 PLG 操作定义、预注册平面 D3h 五参数子空间。优化 dΔr 残差 -0.006796364335475091 Å，优化端点残差 +0.5997190563180368 kcal/mol，固定几何端点残差 +0.006899348033954311 kcal/mol；这些是相对来源报告值，不与同层冻结实现微小残差混用。

全部分类输出哈希复核一致，stderr 为空，原始文件在 D:\AI4Science\ai4orgchem-runtime-runs\20261002T144015Z-p14-classify-675fab20a66f；摘要见 [classification-summary.json](classification-summary.public.json)。结果中的 runtime_provenance=WSL_2_Ubuntu_24_04 与 source_calculation_git_commit 来自上游协议历史快照，不是本次 Docker 实机来源；实际来源以本次 run-manifest.json 为准，未改写上游科学结果字段。

原著完整 Cartesian 坐标未公开；C–H 来源代理、五参数子空间等限制见输出。结论不代表全 Cartesian 频率分析、更广对称性搜索或 19 分子面板复现。production_label=false、training_eligible=false，不自动授予发布/训练许可。


## 本地交付完善

已增加 PowerShell 5.1 bootstrap，自动查找已有 7.3+，实际 evidence 运行 20261002T144551Z-evidence-d53bc4cf86a4 在中文/空格目录 PASS；7 项 PowerShell 检查 PASS。默认目录初始化问题已修正，缺少输出参数的首次测试调用未成功，其后补齐参数复验通过。未修改 PATH 或全局执行策略。

本地备份工程已交付，成功快照 20261002-verified 含 256 普通运行文件与约 454.8 MB 镜像 tar；全部文件及 19 个镜像 blob 已校验。最终带当前宿主脚本/文档的快照位于 runtime-deliveries/20261002-handoff，身份和 SHA-256 以 backup-manifest.json 为准。Windows tar 两类兼容失败的尝试与日志保留；普通文件改用 .NET ZIP，明确排除容器 configs/evidence 源码链接，其源内容保存在镜像内。
