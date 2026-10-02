# 三项交付审查与最终摘要

审查日期：2026-10-03。仅实际镜像元数据/许可证读取、已有结果核对和 CI 静态审查；无科学重算、WSL 升级、WSLc 实测、公开发布。本次审查的本地提交是宿主配置与文档更新，不是镜像重新构建身份。

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
| 底层 run-wslc.ps1 | 最后内容提交 c2cc5027d25defa32338b04cda577285dcc06cf9；当前文件哈希另记 |
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
2. **目标平台阻塞**：WSLc BLOCKED / NOT_EXECUTED，用户已暂停升级与实机验收。D 阶段 WSL2/WSLc 对照未完成，Docker 不替代 WSLc。
3. **CI 未执行**：仅静态审查完成，没有真实运行记录，不标 PASS。
4. **交付限制**：归档完整性已验证，环境恢复未实测，备份同盘不等于灾备。本次修正文档/CI 不在先前备份内，旧备份保持原身份；需要更新快照时另生成新目录。

未发现最终科学输入/输出身份错配；已修正摘要历史范围不明和 CI 证据保存问题。上述许可事项及 WSLc 缺口仍影响原定发布；无公开发布授权，未推送、打正式标签或 Release。

原始审查资料及采集脚本在 `D:\AI4Science\ai4orgchem-runtime-runs\20261003-review`，audit-files.sha256.json 记录原始证据摘要；不把大许可证全文或原始日志加入源码 Git。

## 许可材料续审

已形成 211 文件本地材料包并逐文件校验 ZIP：203 份镜像文本和 8 份上游补充材料。Libxc 7.0.0 MPL-2.0 与 HDF5 2.0.0 主 BSD-3-Clause 已取得正文；XCFun 固定提交源码及 PySCF 补丁、libcint v6.1.3 源码已保存。73 组 Debian 对应源码尚未取得；实际 wheel 的补丁、构建参数及数值库来源仍需映射，发布 BLOCKED 不变。详情见 docs/CORRESPONDING_SOURCE_zh-CN.md 与 validation/license-materials-review.json。镜像未重建，CI/WSLc 状态未变。
