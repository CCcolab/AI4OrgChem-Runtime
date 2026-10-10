# 用户分子普通RHF单点本地验收报告

2026-10-08。首版profile内的用户XYZ普通单点、canonical轨道和AO密度导出已完成实现、干净构建与本地Docker验收。不是全部化学方法或整个Runtime科学功能已通过。用户操作见[四步指南](MOLECULAR_SINGLE_POINT_zh-CN.public.md)，冻结门槛见[首版合同](MOLECULAR_SINGLE_POINT_ACCEPTANCE_CONTRACT_zh-CN.md)，机器字段见[本轮状态](../validation/molecular-service/deployment-20261008.public.json)。

## 支持范围与方法

`single-point` / `rhf-631gd-small-v1` / `ORDINARY_MOLECULAR_SINGLE_POINT_V0.1`。接受H/C/N/O、中性单重态、正偶电子、至多20原子/实际AO≤80的单份严格XYZ，显式Å；三维可用。请求与结构同目录、原字节/顺序/坐标保持，无P编号、片段或xy要求，不加氢、不旋转、不优化。输入几何检查不认证化学合理性。

PySCF普通RHF/6-31G(d)，symmetry=False，conv_tol=1e-12，conv_tol_grad=1e-8，max_cycle=100，max_memory=768MB。12项数值检查全部为true才授予普通数值资格；能隙仅记录。导出自旋求和AO密度和canonical轨道，不是网格密度、等值面或实验测量。波函数稳定性NOT_EXECUTED，收敛不证明稳定或全局基态。DFT、开壳层、离子、更多元素、用户局域化、通用优化和扫描未开放。

## 构建、来源与身份

- 干净镜像构建runtime提交：`1f139aa87dbd1dca8e318b5e9d0226b2a7c8668b`。
- 四次正式宿主执行提交：`a3f6ec7536c510f06b7d521bc09515eb451b9cff`；后续文档提交另列，不替代构建或运行身份。
- 本地镜像：`sha256:e7ffa6420e743a0db184897d21458d69ec90c113b9e3b3c0df7fd2a94a2e202e`，tag `ai4orgchem-runtime:molecular-rhf-20261008-local`。
- 基础本地固定案例镜像：`sha256:e5dde3bd5f426815b5940a193bbe1ef351a23e940d055a2c8cc1ea9ca5a8cfd2`。9.659秒断网构建，没有新依赖安装；image ID不是公开registry manifest digest。
- 20项关键源码闭合哈希：`0f1370a8ef1c5e1a8c7b58f310dc6ad2faa0c08e568e19b01cf8e02d7eff29ab`。
- 依赖锁：`954b8d84d7d393388990303665b6d7416bd760e92fbed21d1148f7574144dbdd`；profile：`40d9c5c16f35b7c90fad86ea771a4379a27b31856bd21785b1f75e313f703dfb`。

实际候选组件为Python3.12.13、NumPy2.5.1、SciPy1.18.0、PySCF2.14.0、PyYAML6.0.3、RDKit2026.3.4、Pillow11.3.0。本入口普通计算复用PySCF；RDKit/Pillow为继承组件，不据此宣称通用图服务已交付。既有许可与binary/source对应缺口未闭合，镜像分发BLOCKED。

## 工程、科学与完整运行分别验收

候选Linux镜像114个唯一用例通过（97新服务＋17复用原生限制器回归），0skip。发现/导入/执行期间持有18项禁止科学dispatch绑定，实际科学调用为0。宿主新服务97项：核心90PASS＋1真实symlink夹具SKIP，worker6PASS；该symlink项在Linux候选真实执行通过。Windows PowerShell5.1和7实际正向启动路径均通过。这里是本地受控测试，不是GitHub Actions运行。

四个输入为冻结技术几何，未优化、未认证实验来源。每个正式任务SCF kernel恰好1，Boys/PM/条件NR均0；电子数、占据正交、白化幂等、密度重构、能量账本、Fock交换子等12项门槛全部通过。

| 分子夹具 | nAO | 总能量/Eh | SCF轮数 | 含清理秒数 | 内存峰值/MiB |
|---|---|---|---|---|---|
| water | 18 | -76.00909910859735 | 11 | 7.500 | 157.039 |
| methane | 22 | -40.19473232455686 | 9 | 6.796 | 154.793 |
| ammonia | 20 | -56.18326529833526 | 11 | 9.125 | 150.898 |
| ethene | 36 | -78.03040520373332 | 10 | 7.359 | 158.977 |

资源固定1CPU、1线程、1GiB、无额外swap、pids128，100秒软停止/120秒硬期限；UID/GID10001，rootfs、源码和输入只读，网络none、caps全部丢弃、no-new-privileges。完整回执核对精确合同、关键源码/依赖/profile、输入及输出哈希、原生保护绑定和恢复、资源开始/结束、退出码、容器所有权删除及删除后输出保留，四次均PASS。样例7—9秒/约151—159MiB不外推其他分子必然收敛或整个80AO规模的耗时。

四个同版本PySCF直接调用分别1次RHF，共4次。与正式入口相同几何/方法/基组/收敛设置；总能量绝对差、AO密度相对Frobenius差、电子数差和S最大绝对差均为0，通过冻结容差。逐列MO不比较符号/简并旋转。这是同库包装一致性，不是独立科学实现、方法等价或实验精度认证。

本轮总实际SCF kernel为8，局域化/条件NR为0，无科学自动重试或重算。冻结4正式＋4直接＋1零SCF拒绝的总墙钟保留上限1080秒；保存进程含清理、额外启动失败及拒绝的时间总和64.717秒。

## 负向记录与更正

实际8C技术输入有112AO，超过80，engine在SCF前拒绝。原host状态FAILED_WORKER_PROCESS、应用host退出20、worker退出2保留；实际guard的SCF/Boys/PM/NR均0。验收项为“预期AO拒绝且零SCF”，不是分子科学合格。

首次辅助直接对照脚本在 `/tools` 启动，漏设 `/opt/runtime` 导入路径，报 `ModuleNotFoundError: No module named 'runtime'`，退出1；发生于PySCF导入/guard/ledger/native dispatch之前。原失败目录及仍写RUNNING的未完成辅助host状态保留，并由REFERENCE_STARTUP_FAILURE.json记录实际停止和清理；guard计数未产生，保留null，不补成已观测0。只修辅助导入路径后完成原定4个对照，无正式入口重算、无门槛变化。

AO探针外层工具Shell退出1曾被误当应用退出码。直接子进程采样证明已有PowerShell5.1/7启动器均正确返回20，无启动器修改；EXIT_PROPAGATION.json保存零科学调用的合成检查。原观察和更正均保留，不重跑科学任务。此前辅助代理child曾用一次临时Bypass进行合成启动检查，不是默认策略资格；没有修改用户/全局执行策略，真实正向5.1/7路径另有默认策略记录。

## 交付与保留边界

本轮证据目录：`D:\AI4Science\ai4orgchem-runtime-deliveries\20261008-general-molecular-single-point`。ACTUAL_DELIVERY.json、CI_EXECUTION.json、WRAPPER_COMPARISON.json、原始命令/日志、输入快照、完整合同、NPZ、账本、guard/resource/run manifests及失败更正均保留。审查只读取存量记录，不重复计算。
