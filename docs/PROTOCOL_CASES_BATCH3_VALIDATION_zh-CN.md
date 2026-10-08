# 第三批 P11/P12 本地交付与验收

当前状态：**本地候选工程部署已形成；P11为1/17（苯G）、P12为1/61（N12-G），其余76态及完整组装仍NOT_EXECUTED。P12-N12-G按原资源门槛完成一次优化，并通过源科学门禁、保存证据与删除后保留复核。** 这不是全部第三批科学验收，也不开放任意用户条件Compute。

| 交付 | 实际状态 |
| --- | --- |
| P11-A 呋喃4态、P11-B苯/氰苯13态 | 全部注册独立优化入口，保留不同算子、约束、原优化参数和完整依赖 |
| P12 N12/N14/N16 | 8/23/30态，共61态；N16 GE要求本轮G+GL，未扩到N18/N20/N22 |
| 冻结科学 OCI 镜像 | 原05308a干净构建镜像保持；本次补救未重建科学镜像 |
| 冻结镜像本地工程 CI | 108项运行，107通过、1跳过；不含宿主后续补丁，也不是新科学计算 |
| 第二批工程回归 | 115项通过；第二批关键来源锁仍为20708a08… |
| 真实账本复核 | P11/P12各PASS；读取历史结果算术，不产生新SCF |
| 真实AO/几何预检 | 全部17+61=78态PASS；SCF/梯度/量子优化器/积分调用均0 |
| 氰苯纯坐标重建 | P11预检10次；独立工程计数，不计量子优化 |
| PowerShell 5.1 启动器 | 真实账本操作PASS，不要求pwsh |
| 非root/源码只读/无网络/CPU内存无swap/退出码/输出保持 | 原控制容器worker输出删除后复核PASS；宿主完整日志封存另行核对 |
| P11B-benzene-G新优化 | 修复前宿主运行；1优化、5SCF、3梯度，源单态门禁PASS；原宿主manifest缺陷单独补核 |
| 宿主封存补丁 | 17项零kernel回归PASS；旧启动器封存顺序缺陷由回归重现 |
| 补丁后真实P11账本 | 42项宿主载荷全匹配，科学计数为空，容器删除后worker输出复核PASS |
| 全部17/61态与最终组装 | NOT_EXECUTED；缺完整新状态集合，不用历史结果或fake测试替代 |

构建提交：`05308a1872d769aaa85e39adbafe7020e36358e6`。镜像：`sha256:18dcd1da2e634cf6ab8d49a7281ca853c0a393e140ac95c6ec00448a3fc934bc`。
关键源码锁：`d8ee6bb0b7880db0f6d40dd38d93b633e1400ff6995f4e56e07042fddd6e7322`；依赖锁：`ca5f5e8b6de0e95364383bb7481e091bb37595cc7e2668dd489eadb9e0b3bb3c`；profile：`0fa3a9205eaec088f704bfc4139c15a01ec5a3b684300f37015b7aa464282308`。
宿主补丁独立锁为 `c10fb922a89ef122d4988cda19db77a2d6c6dd542060a665ca1e44494afb5574`，scope `HOST_FINAL_EVIDENCE_ONLY`，仅覆盖 `scripts/run-high-cost-case.py`、`tests/test_high_cost_supervisor.py`；其余105项原字节实际核验通过。candidate锚定宿主锁SHA，宿主回执写独立 `host_launcher`；科学镜像label和worker计算合同仍为原构建/源锁身份，兼容同worker环境的旧先导输出。

当前HEAD包含宿主补丁及后续文档，不能直接当作原107项worker干净构建上下文，也不能冒充镜像构建提交。原构建日志/干净源码位于初始交付build/；原运行证据在controls/和ps51-controls/。冻结worker源码与原CI在镜像中验证，当前宿主字节与17项回归另行验证，命令见 [第三批指南](PROTOCOL_CASES_BATCH3_zh-CN.md)。原CLI参数/基础SHA失败记录保持。

## 单态先导与宿主封存补核

补救目录：`D:\AI4Science\ai4orgchem-runtime-deliveries\20261008-deployment-limit-remediation`。苯G先导记录为其下 `pilot-runs/20261008T115227Z-P11B-benzene-G-130390e0008e44d5b1105c7341fb516d`，使用修复前宿主和原18dcd镜像/d8ee源锁。

冻结runner实际执行1次优化、5次SCF、3次梯度，优化器与末态SCF收敛，最终能量 `−232.2438286466917 Eh`，最大 `|z|=6.767906539742088e−19 Å`；原数值门禁保持。连同原科学清理及证据哈希56.687秒，cgroup峰值 `1287622656 B`（约1.20GiB），8CPU/8线程、8GiB硬限、无swap、非root、只读科学源码、离线，未观察到OOM。峰值只属于苯G，不能作为单进程RSS或外推其他状态资源合同。

独立核查确认12项worker载荷、真实入口关闭、科学门禁、资源、容器删除后输出及独立预算结算通过。但原host manifest的47项中 `commands.jsonl` 不一致：旧hash精确对应22行前缀，最后探针检查追加后为23行，两个新探针日志也未登记。原记录保留，`pilot-verification.json` 如实记为 `SCOPED_SCIENTIFIC_GATES_PASS_HOST_MANIFEST_INCONSISTENT`；另有50文件 `pilot-evidence-addendum-manifest.json` 补核当前字节，没有回写原manifest或宣称原封存完整。

宿主修复把hash采集移至所有所属探针清理和日志结束之后。补丁后真实零SCF P11账本记录为 `host-patch-zero-kernel-runs/20261008T124717Z-P11-faec53fdcaeb4199bd93c30152f09e45`，`host-patch-actual-verification.json` 登记 `PASS_ACTUAL_HOST_OVERLAY_ZERO_SCIENCE_FULL_MANIFEST`：42项宿主载荷全匹配，科学计数为空，所属容器删除，输出和回执删除后核验PASS。此记录证明新宿主封存闭合；没有用新宿主重算苯G或改写其运行身份。

苯G为普通RKS，尚未执行独立AO电子数/幂等/能量分量审计、SCF稳定性认证或13态ESE/CE/IE组装，不据此认证其他条件态或一般用户Compute。

## 先前资源快照与当前剩余工作

最新快照为补救目录的 `capacity-734d312c6f1b42bbaf7b3f452c53abb1.json`，观察时间 `2026-10-08T12:50:11.572651Z`。初始内存拒绝记录作为历史保留，不再代表最新P11状态。

| 项目 | 冻结单态合同 | 实测缺口 |
| --- | --- | --- |
| P11 | 8CPU/8线程、8GiB，主机≥10GiB、guest≥9GiB | 主机11.872GiB、guest14.440GiB，PASS_CAPACITY_ONLY |
| P12 | 16CPU/16线程、14GiB，主机≥16GiB、guest≥15GiB | 先前快照主机及guest均不足；本次N12-G按原门槛通过，后续启动仍重新预检 |

两类单态硬墙时均12小时（43200s），43080s开始停止；scratch需求20GiB加1GiB余量。CPU和磁盘满足冻结条件；资源快照不是全部Unit准入或收敛保证，下一次启动仍核对当时容量、依赖和预算。没有降低源max_memory/科学容差、升级WSL或修改全局配置。

P11其余16态、P12其余60态未执行；完整17/61态验收及组装需要完整新状态集合，保持NOT_EXECUTED。预算独立、每态一次、失败照常结算，无自动重试，不恢复未完成checkpoint。N16历史19个GE累计84.38小时、平均4.44小时仅作规划参考，本轮没有启动多日后台队列。

## 历史镜像恢复

第二批缺失的两份完整OCI index已从本机保留原内容恢复并实际 `Docker load/inspect`。镜像ID `sha256:6eeccf5ba4192f827986625fae238982ab162e6aadffe6ffc03e3ef642c34e12`、`sha256:e20591dd7ba3b50f4bd68fcbeaec51b415923da747711bb0f5675bb6df427dd9` 的index、platform、RootFS和原config逐项匹配；`original-image-load-verification.json` 为PASS。没有镜像重建或第二批重算。

本地备份 `restored-original-batch2-images.oci.tar` 为637224960字节，SHA-256 `4ad723ea53e36097a134e8bce20f3d49d1fc9353793930c5aa2b9a9c6208b858`，含68个唯一闭包blob及两个原index。恢复库存解决保留缺口，不构成分发许可闭合或新平台验收。

## 已保存与边界

- 源闭包76文件；tracked/untracked、原Git背景HEAD与实际捕获blob/SHA分开，未把所有文件称为同一提交源码。
- 当前两套原工作区仅只读查询/复制；76份原始文件与捕获字节仍一致。未清理原科研目录或旧Runtime。
- geomeTRIC1.1.1/networkx3.6.1/six1.17.0只安装进新本地容器；NumPy/SciPy/PySCF及原宿主科研环境未升级。
- 组装器保留P11-A LDE、P11-B CE/IE及P12同基组CESE的不同定义。缺状态/身份不匹配拒绝；N12真实几何控制未通过不作3倍加权；ENGINEERING_FAKE不能获得科学通过。
- checkpoint只保存进度，不支持恢复。P12历史2011程序对齐NOT_ESTABLISHED、电子态连续性NOT_PROVEN等限制保留；不重新认证原P01—P14。
- WSLc保持BLOCKED/暂停，GitHub Actions NOT_EXECUTED，镜像分发BLOCKED、源码公开另确认。没有公开推送、正式标签或Release。
- 新依赖metadata的许可证字段存在未知项，完整许可证/对应源码闭合不是本轮已经完成的事项；镜像分发既有阻塞继续保留。

实际机器结论：validation/high-cost-cases/deployment-verification.json 与 support-matrix.json。
用户指南：docs/PROTOCOL_CASES_BATCH3_zh-CN.md；验收合同：docs/PROTOCOL_CASES_BATCH3_ACCEPTANCE_zh-CN.md。

## P12-N12-G 单态补验（2026-10-09记录）

本次经用户授权先解决环境容量：临时新建WSL 18GiB内存上限，正常重启Docker/WSL，结束确认未使用的NVIDIA Broadcast与Edge浏览器后台应用。该设置影响全部WSL2发行版，可恢复原默认状态；未升级WSL、未重启Windows，资源合同仍为主机16GiB/guest15GiB、14GiB单容器、16线程和43200秒硬限。上节11.872/14.440GiB及BLOCKED属于先前快照，不能作为本次或未来实时容量。

仅运行P12-N12-G，无前序输入、独立单Unit预算，无自动后续或重试。启动器宿主提交03d2d9212d1280945462851e805d6d64218215a0；科学镜像仍为18dcd、构建提交05308a、source d8ee、host overlay c10fb，均未重建或变更。

- 连同清理墙时2721.5秒（45分21.5秒），15个几何点，1次优化、17次SCF、16次梯度、17次grid、186次数值积分调用。
- 最终能量-464.47335210802373 Eh；源优化与初始/最终SCF收敛、构型及全平面门禁通过。
- cgroup峰值3,987,410,944字节（约3.71GiB）；非root、源码/输入只读、network none、无swap及原CPU/内存限额实测通过，无观测到的OOM/硬限失败。
- worker登记24项、宿主登记61项哈希全部匹配；容器退出码0、所属容器及探针删除、运行锁释放，删除后输出/回执复核相同，预算一次尝试并按含清理墙时结算。

证据目录：`D:/AI4Science/ai4orgchem-runtime-deliveries/20261008-p12-n12-g-pilot`；`pilot-verification.json`为`PASS_SCOPED_P12_N12_G_SAVED_EVIDENCE`，原始run位于`runs/20261008T144220Z-P12-N12-G-a12ac23760ff48088c00133bd7fc2e2e`。本次补丁后的真实科学路径没有重现旧commands日志封存缺陷；P11旧缺陷与50文件补核仍按历史身份保留。

P12仍有60态未执行，P11仍有16态未执行；完整CESE、多尺寸验收、电子态连续性、SCF稳定性和原2011程序对齐未由此证明。未恢复检查点，未启动整批队列，未升级WSL、未恢复WSLc、未执行远端CI或公开分发。Docker旧Inference socket故障重启时复现，临时socket目录保留隔离后本次启动恢复，永久根因仍未闭合。
