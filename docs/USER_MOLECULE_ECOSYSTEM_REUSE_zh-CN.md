# 用户分子入口：生态复用与数据对应

日期：2026-10-05；DRAFT-3 / DESIGN_ONLY。本轮仅核查资料、设计字段映射，不安装依赖、不更改锁或构建文件。与 [主合同](USER_MOLECULE_ENTRY_DESIGN_zh-CN.md)和 [方法对照](USER_MOLECULE_METHOD_COMPARISON_zh-CN.md)共同审阅。

COLAB-ADDENDUM-2：本地 Docker 与启动器为首版主入口；Colab 设计保留为后续可选增强，详见 [阶段与验收补充](USER_MOLECULE_COLAB_ENTRY_zh-CN.md)。当前不要求实现或实测 Notebook，不把其缺失作为本地交付阻塞；未来启用时仍独立验收。

## 1. 复用选择

| 功能 | 选择与理由 | 类别 / 当前状态 | 进入实现前核查 |
|---|---|---|---|
| 原始积分、RKS、semilocal XC | PySCF 2.14.0 及现有数值库；保持既有锁定来源 | 复用现有库；旧任务已使用，新入口未实现 | 实际基组/泛函/网格、依赖身份与新体系参考 |
| 十五类 ERI 与条件 h/S/F | 复用冻结条件核；增加显式输入适配，不另写生产积分器 | 项目特有协议 + 适配；新服务未实现 | 方法范围、占据/能量关系、独立参考 |
| 请求/结果与来源字段 | 先按 QCSchema 建对应表；当前严格 JSON 合同继续保留 | 增加适配；本轮仅映射设计 | schema 精确版本、字段损失、单位/方向/编号、往返验收 |
| QCElemental 解析/单位工具 | 候选库；先核查行为再决定是否增加运行依赖 | 后续可选适配；未安装 | 坐标截断、默认平移/旋转、原字节身份及适用版本 |
| 执行封装 | 现有 runtime 管理输入、容器、输出；QCEngine 作参考或外部普通态适配候选 | 复用 runtime + 最小适配；不部署通用跨引擎平台 | QCEngine 不自动支持条件核，超时/结果语义不丢失 |
| 基组来源与引用 | BSE 核对 C/H 参数、数据版本及引用；运行继续用锁定 PySCF 实际基组 | 来源核对 + 适配；新核对未执行 | 同名不保证系数一致；不在线自动替换或取 latest |
| 结构准备 | 用户外部用 Avogadro；RDKit 为将来图形/编号候选 | 复用外部工具；首版仍 XYZ | 明确 H、原子顺序、坐标方向；化学图验证不等于方法准入 |
| 分片回执与简短报告 | 原子编号/元素/坐标/A-B 表，加已有日志/JSON/Markdown | 项目特有最小呈现；未实现 | 用户确认真实分片，合法另分片应有另模型身份 |
| Colab 用户入口 | 后续复用 Notebook/上传下载生态并调用共用适配器；专业用户可直接走本地入口 | 后续可选增强；当前 DEFERRED，不是首版欠账；实现/实测记录保持未完成 | 恢复实施后核查安装身份、依赖、资源、数据位置与 NB01—NB12；不作为本地 D0—D3 前置项 |
| 多任务数据库/服务器 | QCArchive 记录结构供参考；本地单任务不部署 QCFractal/QCPortal | 后续增强 | 实际多任务需求、预算与维护责任另审 |
| 外部成熟方法比较 | 选择适用程序作单独方法对照 | 后续按 A01 登记，不作为条件核替换 | 可用软件/版本/许可条件、方法适用性与独立预算 |

MolSSI 明确 QCSchema、QCElemental、QCEngine 可以独立使用，无需部署 QCFractal/QCPortal。[官方说明](https://molssi.org/software/qcarchive/)支持当前先建立互操作合同的选择。是否引入库由适配成本与受测行为决定，标准对应不等于已经兼容。

## 2. QCSchema 字段对应（候选，不是兼容认证）

本表参照 [QCElemental 0.30.2 Molecule](https://molssi.github.io/QCElemental/v0.30.2/api/qcelemental.models.Molecule.html)的 QCSchema molecule v2 及 MolSSI 输入输出概念；计算结果 schema/版本仍待选定，不声称 v3 或全部 QCSchema 兼容。

| 当前合同 | 标准候选字段/处理 | 保留信息与验收 |
|---|---|---|
| XYZ 元素与实际顺序 | molecule.symbols | 不加 H、不重排；逐原子往返匹配 |
| Å 坐标、xy 方向 | molecule.geometry 的 a0/Bohr；fix_com=true、fix_orientation=true | 转换常数/版本、原 Å 与原文件留存；不静默旋转/投影，复查 1e-8 Å 门槛 |
| charge=0、multiplicity=1 | molecular_charge、molecular_multiplicity | 不把 PySCF spin=0 误写为 multiplicity=0 |
| 两组 1-based 碳编号 | 本项目扩展命名空间中的 pi_groups 与显式 1→0 映射 | 不直接写 molecule.fragments；标准碎片要求覆盖全部原子且有片段电荷/多重度，当前 π 组不满足相同语义 |
| calculation_profile | model.method/basis 的候选映射 + 完整 profile 扩展 | 固定网格、XC 解析身份、DIIS/阈值等不能丢失或静默改默认 |
| condition_profile / rule hash | extras 下本项目命名空间或 sidecar | 标明操作性定义、规则版本、变分状态；普通能量结果不能冒充条件核 |
| 两态能量与账本 | 分别构造单态记录，登记单位；比较量作为关联派生记录 | 不把一份 AtomicResult.return_result 塞成语义不明的两态能量差 |
| scientific/runtime/image 身份 | provenance + 扩展 manifest | 标准 provenance 不够表达全部身份；完整 SHA、image ID/digest、输入哈希仍保留 |
| 执行/数值/研究三层状态 | success/error 映射 + 扩展状态账本 | success 不能替代 research_eligibility；部分成功、OOM/UNKNOWN 不能丢失 |
| 原始请求/XYZ SHA-256 | manifest 原字节哈希，另存规范化输入哈希 | QCElemental 分子哈希/精度截断不能替代原字节身份 |

QCElemental 所查版本默认允许平移/旋转，且文档说明坐标/质量/电荷精度整理。采用时须测试实际处理后的几何，不可仅设置标志便声称字节无损。输入归一化、显示坐标与实际运行坐标分别有身份；任何截断影响平面边界或模型身份时拒绝或重新由用户明确确认，不能改变计算输入后沿用旧哈希。

互操作测试并入 A02/A04/A08/A17：Å↔Bohr、0↔1 编号、原子重排+同步映射、原点/方向、数值精度、完整 profile、失败状态、条件扩展及 provenance 的往返。未实现的适配项不要求 D1 先安装整套工具，也不能标 PASS。

## 3. 基组来源核对与离线执行

[BSE 官方用法](https://molssi-bse.github.io/basis_set_exchange/usage.html)提供基组、引用和显式数据版本；不指定版本时会取最新。新 profile 应记录实际运行的 PySCF C/H 展开基组、球谐设置、壳层/收缩数、参数规范化哈希，以及对应 BSE 数据版本/引用和差异。核对结果是 SAME/DIFFERENT/UNKNOWN，不预设同名一致。

BSE 用于来源核对和准备期材料；实际计算不在线下载、不自动升级基组。若确需替换参数，形成新 profile/来源身份与独立验收。当前未获取并核对全部 C/H 参数，不能声称基组来源映射已闭合。

## 4. 进一步发现与后续增强

官方 [GPU4PySCF EDA 测试源码](https://github.com/pyscf/gpu4pyscf/blob/master/gpu4pyscf/properties/tests/test_eda.py)也出现 ALMO-EDA2 及 Q-Chem 参考比较。这里只确认 master 中有相关测试内容；尚未核查对应实现、确切发行版本、硬件可用性或本项目适用性，不采用其测试容差，也不安装 GPU 栈。它可在路径 II 选型时继续核查。

[Avogadro 输入生成接口](https://avogadro.cc/develop/scripts/generators.html)可由结构和选项生成输入；当前先让用户用外部工具准备确认后的 XYZ。[RDKit 官方入门](https://www.rdkit.org/docs/GettingStartedInPython.html)可支持后续编号/化学图准备。SMILES/InChI 等分子图标识与实际几何、计算协议及分片是不同身份；不能替代 geometry_sha256。

本轮没有添加依赖锁、schema 实现、图形编辑器、通用调度或外部程序执行能力。可选工具真正纳入构建时才针对选定版本处理兼容性、署名和分发条件；当前不扩大为通用合规平台。
