> 当前公开阅读节选。原始历史材料已按原字节保存在本地归档；本文件不是原件，不能用于原始哈希验收，也不把旧验收转移至当前代码。
> 原件 Git 提交：eb65b4586c83637569f6359814338c1292948861；SHA-256：d6f1379308dc5ac9cce39ea7c034e39196cffb2a792949609e89495ddd766d63。

# W01—W07 本地 CI 验证

2026-10-06。**本地工程 CI 通过**，共 176 个独立单元用例、284 次执行，无失败、错误或跳过；108 次是最小/完整套件及 legacy runtime 的明确重叠，不算新增用例。另完成启动器 10 项、受防护 Python 服务 3 项、研究 profile 元数据守卫 1 项、PowerShell AST/路径 7 项、真实平台探针 4 项及 W07 宿主报告 9 项。逐个 ID 和实际回执见 [机器记录](../validation/user-molecule/ci-local-w01-w07-20261006.public.json)。没有执行新的分子 SCF、格点或完整分子 ERI；科研资格未因此通过。

## 受测身份与执行方式

受测源码为干净提交 `44ad90e0e3b293879ec67b7a10475825cde05d3a`，由 Git 导出后只读挂载。既有 r3 镜像 `sha256:24f46f33264924e5d3d3bec386298585267c6f30d6e6a0cd0a6486ecf45db93d`；镜像 runtime 构建 `5098775c9cf40468ab92712447a3e5c7b1361a63`；科学适配 `cc7437901119e71ef7945a12813c021c383e7648`，基线 `28511f3d84fa65707a107cde1e8121a7b4334ecb`。本轮后续报告提交单列于外部 `FINAL_CI_DELIVERY.json`，不是受测代码或镜像构建提交。

使用已有 Docker Desktop 4.78 / Engine 29.5.3、Linux/amd64 候选及已有 PS7/标准库 Python。最小环境在容器 tmpfs 创建 venv，通过既有 wheel、`--no-index --require-hashes` 安装固定六包；没有修改宿主依赖。完整套件使用镜像既有依赖，并在整个进程禁止 PySCF 的 SCF/kernel、Grids.build 与积分调用；独立参考只执行 2/3 AO 分析数组和假引擎，不执行真实分子求解。未单独重复运行相同 W06 套件。

| 单元组 | 实际执行次数 |
|---|---:|
| 最小输入/资源/契约/报告组 | 101 |
| 全程防护组：user 130、参考 v1/v2 各15、runtime 7 | 167 |
| 科学适配器工程组 | 4 |
| 单列 legacy runtime/process/classifier | 7 / 3 / 2 |
| 合计 / 去重 | 284 / 176 |

## 工作包与验收范围

| 工作包 | 本轮工程证据 | 科研边界 |
|---|---|---|
| W01 | 干净来源导出、镜像/锁身份、冻结源与旧材料保护 | 旧候选不冒充新科学资格 |
| W02 | 严格解析、映射/路径/资源/输入合同、四个有效 Check | 合法格式不证明方法适用 |
| W03 | adapter、研究 metadata guard、检查与拒绝 | 两个 production profile 的 Compute 仍关闭 |
| W04 | 封装回归、限额与隔离、超时/取消/OOM、输出持久性 | 故障探针不执行分子计算 |
| W05 | 夹具/预算/有限指标/谱系、数组与假引擎 | 既有分子数值门禁已执行但失败，本轮未重算 |
| W06 | v1/v2 数组参考、资格/失败状态、只读判读 | 完整分子参考/路径门禁失败、方法范围未审 |
| W07 | evidence 20、export 8、preservation 10 及实际宿主9场景 | 工程自测通过；科研W07仍BLOCKED，真人反馈延期 |

实际新建 **18 个容器**：7 个单元/metadata/guard、4 个平台探针、7 个入口动作。顺序运行、1 CPU、非 root、只读根/源码/输入、network none；单元组和本轮所有入口按冻结请求均为 512 MiB，故障探针 128 MiB，memory-swap 与 memory 相等。此前模拟自测的 research 1024 MiB 属于另一批记录，不移用到本轮。隔离探针实测 UID、拒绝写源码/输入及网络；超时、取消、OOM 都保留宿主观测、退出码与提前写出的输出。删除结论依据实际成功 `rm` 和 `container_removed` 回执，未追加删除后查询；已核对仍在宿主的清单字节与输出。可写 tmpfs 是临时测试空间，不改变只读源码。

主启动器10项含四有效Check、禁止Compute、只读Report、未知字段/资源越界/路径逃逸拒绝、修改几何后拒绝旧Check。两次 Compute CLI 仅做资格/身份拒绝，另有全防护进程内一次禁止Compute；不是科学执行成功。早期 r3 错误记录中缺失的科学字段保留 UNKNOWN；缓存 W05_NOT_EXECUTED 不覆盖项目后来实际失败的记录。

W07宿主9项为基础/高级读取、新目录导出、重复/源内导出拒绝、损坏副本拒绝、不完整副本的基础0/高级40、旧科学失败判读。副本明确标为合成控制，原回执未改；三份新导出清单核对通过。旧科学失败的 Report 退出0同时保持 FAILED/NOT_QUALIFIED、比较false、delta null；历史 EXECUTED 不算本轮科学执行。基础Report的0不能证明关键快照齐全；高级不完整证据为40/UNVERIFIED。

## CI 修正与复现

修复最小锁中无NumPy却由通配符导入数组测试的问题；新脚本明确分类全部12个user测试文件，最小组实际101，数组/参考在受防护本地组执行。增加漏掉的参考v2组；修正W07测试的旧笼统BLOCKED断言，工程PASS与科研BLOCKED分列；三个合成夹具输出隔离到tmpfs，不回写旧交付；按实际机器记录读计数而非首条 `Ran N`。这些仅为测试/CI修正，没有修改科学规则、profile、容差或求解器。

当前完整本地入口为 `scripts/test-user-molecule-ci.py` 与 `scripts/test-user-molecule-w07.py`：前者需全新输出目录、冻结legacy-source、既有wheels和PS7；后者引用前者生成的单次valid Check及已有单次失败记录，配合已有PS7/Python，只做Report。精确argv、原stdout/stderr、导出和来源文件均保存于 `D:\AI4Science\ai4orgchem-runtime-deliveries\20261006-user-molecule-ci-w01-w07`，不覆盖旧CI或W07包。运行前保持源码干净；不要把原输出目录用于重跑。

远端 workflow 的最小合约job已同步选择9类测试文件、共101个用例，明确另外的数组/适配器/Windows/平台范围仍为本地；legacy Linux job继续按原配置构建/轻量验证。权限 `contents: read`、action SHA固定，保留失败证据、七天附件；没有镜像推送、正式标签或Release步骤。**GitHub Actions真实执行仍NOT_EXECUTED**，本地容器不是GitHub runner，未执行远端构建/上传。

## 保留与未关闭事项

39个科学/runtime实现、参考、profile/schema/锁/构建文件字节未变，591个科学源码匹配锁；旧W07冻结清单614文件及原ZIP未变，历史失败原32文件在W07前后匹配。未登记历史字节仍不作保证。新增CI代码与报告提交独立保留，未推送或发布。
