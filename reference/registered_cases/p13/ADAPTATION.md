# P13 固定案例适配边界

原驱动 `run_p13_polycyclic_benzenoid.py` 和协议 YAML 逐字节保存；大小、SHA-256、原开发仓库捕获 HEAD 见 `SOURCE_METADATA.json`。两文件在捕获时均未跟踪，捕获 HEAD **不代表这些正文是该提交的 Git 对象**。它们不是 `28511f3` 公开基线中的可执行驱动。

驱动是 AI4OrgChem 项目代码，沿用 Apache-2.0；冻结表格的原著署名为 Zhongheng Yu，2024，*Questioning Fundamental Principles of Organic Chemistry*，DOI `10.6084/m9.figshare.27261243`，协议声明 CC-BY-4.0。此处不重新裁定这些声明，也不携带原著 PDF。

适配器固定执行一个 P13 案例，没有任意用户分子、输入参数或优化入口。

| 原驱动范围 | 当前适配 |
|---|---|
| 六个数学助手：edge、build_linear_acene、enumerate_perfect_matchings、recompute_ledger、rdkit_formula、enumerate_acene | 对原字节验 SHA 后提取原 AST；表达式不改 |
| 原 run 中第218—300行的账本、筛选、图枚举、15项检查 | 原 AST 原样编译；检查名、严格比较和阈值不变 |
| 首行读取可配置 YAML 路径 | 只读已锁定的随包 YAML 字节，以真实 PyYAML safe_load 解析 |
| 检查失败时直接抛出 | 检查仍执行；写 FAIL 回执保存全部结果 |
| 末尾读取 PDF 和查询原 Git HEAD | 删除执行路径；PDF `NOT_REAUTHENTICATED`，实际 SHA 为 null；历史/声明来源和当前捕获身份分别保存 |
| 原 main 默认写原项目 data/docs | 不执行；仅向父 runner 给出的新空目录独占写 case-result.json 和 case-report.md |

此次能量工作是 **Frozen-table lane**：重算21行冻结印刷账本的 ESE/CESE 算术及规则层级（14候选、3跨拓扑、4留出，另有6行趋势检查），不是新量子计算。没有执行原2007程序、几何优化或新SCF；`new_quantum_calls=0`。原判定字符串仅作为冻结协议的范围化合同记录。

分子式必须调用原 `Chem.RWMol → Chem.SanitizeMol → rdMolDescriptors.CalcMolFormula`，不使用解析式替代。RDKit 锁定 `Chem.rdBase.rdkitVersion == 2026.03.4`，对应 PyPI 版本 `2026.3.4`；PyYAML 由隔离候选环境锁定并记录实际版本。缺依赖、版本不符或源字节不匹配时返回 BLOCKED，检查 NOT_EXECUTED；不安装全局依赖。

标准库测试只执行固定图构造、完美匹配/GL计数、账本算术、AST一致性和安全拒绝；不冒充真实 RDKit 分子式验收。完整固定案例由父任务在隔离候选环境另行验收。
