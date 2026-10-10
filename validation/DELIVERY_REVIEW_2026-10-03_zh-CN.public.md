> 当前公开阅读节选。原始历史材料已按原字节保存在本地归档；本文件不是原件，不能用于原始哈希验收，也不把旧验收转移至当前代码。
> 原件 Git 提交：eb65b4586c83637569f6359814338c1292948861；SHA-256：968c6bf87be7252e9c3240e5fbf44e0cf03d2b883ab12c56b5bb4e11ad97ef82。

# 三项交付审查与最终摘要


## 审查清单

| 项目 | 结论 | 记录 |
|---|---|---|
| 实际组件许可证与署名 | 审查完成，有发布阻塞项 | docs/LICENSE_REVIEW_zh-CN.md、component-license-inventory.json |
| 科学源码/构建提交/宿主入口/镜像/结果对应 | 核对通过；当前状态统一 | provenance-review.json、final-delivery-status.json |
| CI 执行范围、权限、发布行为 | 静态审查完成；运行 NOT_EXECUTED | CI_REVIEW_2026-10-03_zh-CN.md |

实际镜像内 14 个 runtime/锁/署名文件与构建 Git 内容 SHA-256 一致。7 份最终 manifest 的源、runtime、镜像身份一致，输出哈希复核；联合分类四个 parent 的原始 result 哈希也核对。未修改原项目或历史 manifest。

## 身份关系

| 标识 | 实际内容 |
|---|---|
| 科学来源 | v0.3.2，commit 28511f3d84fa65707a107cde1e8121a7b4334ecb |
| 镜像构建 runtime | f30b2906794d14f9030daab779c0d6a7cd4bd6f7 |
| 最终本地镜像 | sha256:ddc45b1fe500ed3d5ed30520eb4e49f3969cb69f02121f28e2ff851f7a724f54 |
| 日常入口 start-runtime.ps1 | 最后内容提交 b515c1d10f7077ebbdff7b4c5a7240432e4b8545；当前文件哈希见 provenance-review.json |
| 审查前宿主仓库/交付备份 | c27101414d88350598a1977eecf2a2fd60761333；20261002-handoff 保持历史快照，不伪称包含本次审查修正 |

宿主后续更新不等于镜像代码更新，不能把当前 HEAD 填入旧镜像或历史 manifest。首轮 788d33e... 镜像/acceptance-01/02 是历史；最终镜像证据为 acceptance-03。summary.json 仅存历史 WSL2 记录，早期 UNKNOWN 和一次缺源码预检 FAIL 保留。最终当前状态以 final-delivery-status.json 为准。

## 最终验收入口

- Docker L0/L1/L2/等价性：20261002-oci/acceptance-03 的四份运行。
- 用户使用 smoke：20261002T115757Z-p14-smoke-5edcc0ade184，作为分类输入；另一次用户 smoke 与 evidence 是使用验证记录。
- L3：20261002T123033Z-p14-fixed-d621c0cfab97，54.37 秒、峰值约 8.60 GiB，12/12 anchor 资格。
- L4：20261002T123346Z-p14-optimize-d7f348003891，21.20 分钟、峰值约 8.60 GiB，18/18 优化资格。
- 联合分类：20261002T144015Z-p14-classify-675fab20a66f，PASS/consistent，13 判定及 19 优化资格全部满足。

本地 Docker 已验证 L0—L4、等价性及固定协议四输入分类；非 root/源码只读/中文空格路径/退出码/删除后输出/断网等能力以 OCI L0—L2 探针实际范围为准。L3/L4 本次不依赖网络但未显式隔离，完整 L4 中断未执行；8 线程请求不是严格 CPU 配额。L4 可保存检查点，不支持恢复运行。

科学 consistent 只限固定 C12H6 来源代理与平面 D3h 五参数协议，不是普遍认证、19 分子面板复现或训练授权。分类 result 内的 historical runtime_provenance 与 source_calculation_git_commit 不是本次 Docker 身份，本次以 manifest 为准。

## 未解决事项与发布状态

1. **许可证发布阻塞**：部分内嵌数值库原始许可证/署名及精确 binary 来源不齐；系统/运行库 GPL/LGPL 与 XCFun MPL 对应源码提供机制未落实；vendor/file-level 映射仍有 UNKNOWN。本地使用成果保留，公开镜像不能据此宣称许可审查全通过。
3. **CI 未执行**：仅静态审查完成，没有真实运行记录，不标 PASS。
4. **交付限制**：归档完整性已验证，环境恢复未实测，备份同盘不等于灾备。本次修正文档/CI 不在先前备份内，旧备份保持原身份；需要更新快照时另生成新目录。


原始审查资料及采集脚本在 `D:\AI4Science\ai4orgchem-runtime-runs\20261003-review`，audit-files.sha256.json 记录原始证据摘要；不把大许可证全文或原始日志加入源码 Git。

## 许可材料续审



最新许可/源码与候选包续审见 [公开边界说明](../docs/PUBLICATION_BOUNDARIES_zh-CN.md)。20261002 备份和首次 211 文件材料包是历史快照；当前候选包路径为 D:\AI4Science\ai4orgchem-runtime-deliveries\20261003-final-candidate。所有执行后哈希与归档验证以该目录 package-manifest.json、package-verification.json 和 backup-verification.json 为准。
