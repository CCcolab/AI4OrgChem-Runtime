# W07 模拟用户场景自测

2026-10-06。结论：**已执行范围内的工程自测通过**，当前不需要真人试用或反馈。操作人为代理（`AGENT_SIMULATED_USER_NOT_HUMAN_PARTICIPANT`），使用已有登记夹具模拟请求；没有代填真人意见，也未生成新的合格研究结果。W07 本地工程交付和自测可收尾，科研交付及两个生产 profile 的 Compute 继续 **BLOCKED**。

## 实际执行

从 Windows PowerShell 5.1 经现有 PS 7.6.5 启动器执行，请求路径包含中文及空格。四份有效请求沿用原坐标与碳 A/B 分组，模拟研究问题和请求限额；没有优化、旋转、重排或加氢。按冻结合同执行 9 个启动器场景，实际创建 8 个容器；路径逃逸在宿主拒绝，未创建容器。每次输出保留，8 个容器均已删除。

| 场景 | 动作与实际退出码 | 核查结果 |
|---|---|---|
| 乙烯 pilot / research | Check：0 / 0；nAO：14 / 36 | 输入与映射 VALID；计算资格 false；SCF、网格、完整 ERI 未执行 |
| 丁二烯 pilot / research | Check：0 / 0；nAO：26 / 68 | 输入与映射 VALID；计算资格 false；SCF、网格、完整 ERI 未执行 |
| 错误单位 bohr | Check：10 | 明确拒绝，不自动换单位 |
| 重复/遗漏碳分组 | Check：10 | 明确拒绝，不自动修复分片 |
| `../molecule.xyz` 逃逸 | Check：10 | 宿主拒绝；容器身份及容器码为 null |
| 合法 Check 后尝试 Compute | 资格探针：20 | 返回 BLOCKED / NOT_EXECUTED；比较 false，两个 delta 为 null |
| 修改研究问题后复用旧 Check | 身份探针：20 | 拒绝旧回执；父回执未改，未执行科学 Compute |

两次调用 Compute CLI 只测试资格与身份拒绝，均在科学求解前退出；**本轮新科学 Compute / SCF / 网格 / 完整 ERI 为 0**。不能把拒绝探针写成计算通过，也不能写成没有调用 Compute CLI。

实际容器观测记录了 `10001:10001`、只读根文件系统、只读输入（旧 Check 挂载也只读）、`network=none`、1 CPU、512/1024 MiB、memory-swap 与 memory 相等；科学源码位于只读镜像层。bind 挂载中仅输出和锁目录可写，`/tmp` 另有 64 MiB 可写 tmpfs。这些是本次容器配置及输出持久性事实，不是新的强制写入攻击、OOM、取消或超时测试。8 个容器观测运行区间合计约 20.48 秒，不是流程总耗时或科学计算资源预测。

四个有效 Check 的基础 Report 均退出 0。全部 9 个场景的高级 Report 与 fresh 外部导出均退出 0，核对清单字节、原退出码及来源身份，比较始终 false、delta 始终 null；源回执、父 Check 和原输入字节未变。`MATCHED` 仅表示本地清单字节匹配，不认证来源真实性、方法或科学结论。

## 宿主保护与解析场景

| 场景 | 实际结果 |
|---|---|
| 导出到已存在目录 | 40；原导出与源运行未改 |
| 导出到源运行内部 | 40；源运行未改 |
| 读取被改动的证据副本 | 40；检测清单字节不匹配，原记录未改 |
| 缺少规范化请求的受控副本：基础读取 | 0；说明基础模式不能证明关键快照完整 |
| 同一不完整副本：高级读取/新导出 | 40 / UNVERIFIED；比较 false、delta null |
| 读取既有 v2 科学失败记录 | Report 0；仍 FAILED / NOT_QUALIFIED、不可比较，旧文件全部未改 |

不完整和损坏材料均为明确标注的测试副本；未修改原运行或其清单。最后一行的 `scientific_execution_status=EXECUTED` 来自历史科学运行，不能计入本轮执行。

另完成 **11 个负向 parser 探针和 1 个原样有效控制，12/12 通过**：重复 JSON 键、NaN/溢出、截断/重合/尾随 XYZ、非平面、非 C/H 与超 128 原子计数等分别返回预期 10/11。探针只调用宿主 `strict_json` / `parse_xyz`，禁用科学模块导入，原 XYZ 和源码哈希未变；这是 parser 单元场景，不增加镜像端到端或科学验收覆盖。

## 身份、辅助错误与未知

受测宿主提交：`a9f7b3baaf92637d77a88cd983cff94b5b934b87`。既有 r3 镜像：`sha256:24f46f33264924e5d3d3bec386298585267c6f30d6e6a0cd0a6486ecf45db93d`；镜像 runtime 构建：`5098775c9cf40468ab92712447a3e5c7b1361a63`；science：`cc7437901119e71ef7945a12813c021c383e7648`，冻结基线：`28511f3d84fa65707a107cde1e8121a7b4334ecb`。本轮新增文档提交由交付目录的最终登记单列，不能冒充镜像构建或受测代码提交。

首个乙烯 Check 退出 0 后，自测辅助最初把 CRLF 宿主 profile 字节与 LF 镜像构建字节直接比较，导致辅助断言失败。逐份核对两个 profile 的构建 Git blob、LF 转换和 JSON 正文，确认无 profile 变更；辅助 v2 改为绑定构建提交的精确字节，并复用首个成功 Check，未重复创建容器。初版辅助、首个 Check 原执行日志与辅助错误说明保留；初版辅助断言的独立完整 stderr 文件未登记，不宣称已提供。未改科学规则、门槛或容差。

旧 r3 的错误单位/错误分片早期记录未保存 `scf_executed` 等字段；这两例及宿主路径逃逸的高级报告均保留科学/数值 **UNKNOWN**，没有补写 false。静态 Check 路径及错误点证明其在 metadata/科学计算前拒绝；该范围推断与原字段分别记录。旧缓存中的 `W05_NUMERICAL_ACCEPTANCE_NOT_EXECUTED` 只描述当时缓存，不能覆盖后来 W05/W06 已执行但失败的验收记录。

parser 辅助的 HEAD 字段来自预设基线常量；根代理实际 `git rev-parse HEAD` 观察和 parser 源码哈希核对另行完成，不能称为该辅助自行核验 Git。parser JSON 还包含执行包装器追加的退出码/日志字段和 +09:00 时间表示；辅助源码的时间格式为 UTC +00:00，未取得独立包装器原始时间转换记录，因此精确时间来源/转换为 UNKNOWN，不据此计算 parser 耗时。保留原 JSON、辅助和日志，仅登记这项限制，不重跑或改写原证据。

## 覆盖与保留边界

本轮覆盖 A02 正常 Check、A03/A04 部分拒绝/路径、A11 检查限额、A12 实际隔离与持久性、A09/A10/A17 的失败判读/null 比较，以及 A14/A18 的代理工程操作部分。逐项范围见 [机器记录](../validation/user-molecule/w07-simulated-selftest-20261006.json)。没有将整个 A01—A18 标为 PASS；没有新增分子数值验收、资源模型校准、强制取消/OOM 或真人体验证据。原 48/122 项单元测试等仍为历史回执，本轮没有重跑。

真人试用与反馈按用户要求 **DEFERRED_BY_USER**，以后可选，既非当前工程阻塞，也不要求用户提供真实分子后才能收尾。剩余科研门禁包括条件态/选态与固定点定义、实际数值资格、两路径与独立完整参考、第二个合格研究体系、分模式资源规模及方法范围责任；四问咨询继续延后。

WSLc **BLOCKED / NOT_EXECUTED / 暂停**；远端 GitHub Actions **NOT_EXECUTED**；Colab **DEFERRED**；r3 完整实际组件许可审计 **NOT_EXECUTED**、镜像分发 **BLOCKED**；源码公开须另行授权。本轮未重建镜像、升级 WSL、修改全局配置、公开推送或发布。原七任务历史不转移为新服务资格；原 L4 可保存检查点但不支持恢复运行。

实际日志、命令、9 个场景原运行及导出、6 个保护回执、parser 输入/hash、初版辅助错误留存在 `D:\AI4Science\ai4orgchem-runtime-deliveries\20261006-user-molecule-w07-simulated-selftest`。本轮审阅包为增量源码/工程证据包，不是可独立安装或分发的镜像；旧 `a9f7b3b` 候选包不覆盖、不重打包。入口见 [工程指南](USER_MOLECULE_W07_ENGINEERING_TRIAL_zh-CN.md) 与 [Report 指南](USER_MOLECULE_REPORT_20261006_zh-CN.md)。
