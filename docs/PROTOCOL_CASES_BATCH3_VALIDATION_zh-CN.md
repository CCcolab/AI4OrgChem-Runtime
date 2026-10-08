# 第三批 P11/P12 本地交付与验收

本轮状态：**本地候选实现及工程验收完成，高成本新优化仍因资源不足 BLOCKED / NOT_EXECUTED**。不能写成第三批科学验收全部完成。

| 交付 | 实际状态 |
| --- | --- |
| P11-A 呋喃4态、P11-B苯/氰苯13态 | 全部注册独立优化入口，保留不同算子、约束、原优化参数和完整依赖 |
| P12 N12/N14/N16 | 8/23/30态，共61态；N16 GE要求本轮G+GL，未扩到N18/N20/N22 |
| 新候选 OCI 镜像 | 已从干净提交构建，构建断网，原始捕获字节在干净clone逐项验证 |
| 第三批本地工程 CI | 108项运行，107项通过，1项跳过；不是新科学计算 |
| 第二批工程回归 | 115项通过；第二批关键来源锁仍为20708a08… |
| 真实账本复核 | P11/P12各PASS；读取历史结果算术，不产生新SCF |
| 真实AO/几何预检 | 全部17+61=78态PASS；SCF/梯度/量子优化器/积分调用均0 |
| 氰苯纯坐标重建 | P11预检10次；独立工程计数，不计量子优化 |
| PowerShell 5.1 启动器 | 真实账本操作PASS，不要求pwsh |
| 非root/源码只读/无网络/CPU内存无swap/退出码/输出保持 | 四次控制容器实际核验，均删除后哈希复核PASS；PS5.1另有一次成功账本记录 |
| 新78态多态优化与最终组装 | NOT_EXECUTED；没有用旧结果或fake测试冒充 |

构建提交：`05308a1872d769aaa85e39adbafe7020e36358e6`。镜像：`sha256:18dcd1da2e634cf6ab8d49a7281ca853c0a393e140ac95c6ec00448a3fc934bc`。
关键源码锁：`d8ee6bb0b7880db0f6d40dd38d93b633e1400ff6995f4e56e07042fddd6e7322`；依赖锁：`ca5f5e8b6de0e95364383bb7481e091bb37595cc7e2668dd489eadb9e0b3bb3c`；profile：`0fa3a9205eaec088f704bfc4139c15a01ec5a3b684300f37015b7aa464282308`。
最终文档/记录提交会晚于构建提交，两者不得混称。原始构建日志与干净源码位于build/；实际运行证据在controls/和ps51-controls/。早期CLI参数/基础SHA解析失败也保留，没有冒充最终PASS。

## 当前阻塞

正式优化准入各检查一次，均在创建科学容器、占用正式预算及运行SCF之前拒绝。

| 项目 | 冻结单态合同 | 实测缺口 |
| --- | --- | --- |
| P11 | 8CPU/8线程、8GiB，主机另留2GiB | 主机可用约8.32GiB，需要至少10GiB |
| P12 | 16CPU/16线程、14GiB，主机留2GiB、guest留1GiB | 主机约8.22GiB，需要16GiB；guest约14.28GiB，需要15GiB |

两类单态硬墙时均12小时（43200s），43080s开始停止；scratch可用需求20GiB加1GiB余量。当前CPU和磁盘满足相应静态条件，内存未通过。没有通过降低源max_memory/容差、停止原科研进程或更改WSL配置来放行。

恢复条件后，用全新独立第三批预算先验收少量状态，再推进多态；每个完整合格状态可作为下一状态输入。预算不复用第二批、不自动重试、不恢复未完成checkpoint。N16历史19个GE完整子进程累计84.38小时、平均4.44小时，仅作规划参考；78态完整新验收可能多日，当前没有启动后台长队列。

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
