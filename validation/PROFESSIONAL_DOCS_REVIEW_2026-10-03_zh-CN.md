# 专业用户文档增补静态核查

日期：2026-10-03。基线提交 `2460eef636be9a143d3bbb81daf8f66fc7e70959` 保留；本轮按用户授权补充专业复核文档，拟形成独立本地提交。新增提交、示例中的本地路径和未跟踪修订方案均需另行确认公开范围。

## 交付清单与范围

| 文件 | 用途/修改 |
|---|---|
| docs/PROFESSIONAL_SERVICES_zh-CN.md | S1—S6→七任务→固定协议、代码、测试、实际字段；六张服务卡及覆盖边界 |
| docs/REVIEW_RESULTS_zh-CN.md | 四层判读、参照与残差、历史身份、失败/未知及手工交付布局 |
| docs/USER_PATHS_zh-CN.md | 读者、专业复核者、开发者三条路径；专业两类侧重共用结果 |
| docs/templates/REVIEW_REPORT_zh-CN.md | 手工报告：方法、身份、四层状态、账本、四父关系、失败与范围 |
| docs/templates/FEEDBACK_zh-CN.md | 最小可核查反馈及提交前脱敏；无自动上传 |
| docs/examples/P14_REVIEW_20261002_zh-CN.md | 真实旧运行的可读示例，区分验收 smoke 与分类父 smoke |
| docs/examples/P14_REVIEW_20261002.json | 八份原始 manifest 与选择性 result 摘录、四父哈希、原路径；省略迭代 history，不修改原记录 |
| docs/examples/professional-source-index.json | 64 项固定来源路径、永久提交链接与来源锁 SHA-256 |
| docs/RUN_zh-CN.md | Docker 命令显式 -Engine docker，改为本地已验收候选标签；区分公开、WSLc、断网范围 |
| README.md、README_zh-CN.md | 专业材料导航、手工模板与未实现工具声明；新增公开范围单独审阅 |
| 本文件、professional-docs-review.json | 静态核对结论、检查范围、材料哈希与未实现项 |

没有修改 runtime、启动器、Dockerfile、依赖锁、科学代码、协议、容差或已有验收摘要。旧备份和候选包未更新，不冒充包含本次增补。用户未跟踪方案和 PDF 保留原状、不加入提交。

## 来源与检查依据

设计依据为用户修订方案及本轮五项交付授权；事实依据为 runtime/cli.py、runtime/classify.py、启动器参数、来源锁、provenance-review、l3/l4/classification 摘要和本机原始运行。上游实现从独立 `tmp/runtime-source-v032-20261002` 固定归档读取，未切换或修改原项目工作区。

已对 588 个固定来源文件重新核对 SHA-256；对七个最终验收运行及联合分类实际额外引用的 smoke（共八份）核对 manifest 与其登记输出哈希。四父 result 哈希匹配分类 manifest.parent_runs 与 result.evidence_sha256，父任务、状态、源码、输入及依赖一致。此检查是只读文件核对，不是重新执行科学计算。

核对三份上游 L1 日志为 11 passed。规则表明确 AO PySCF 分类与完整分子电子数不是这三份单元测试直接完整覆盖的内容；没有把测试通过表述为物理普遍证明。数值取自实际字段，普通态未输出能量分项写 unavailable；旧分类元数据与实际 manifest 分开。

机器可读记录见 [professional-docs-review.json](professional-docs-review.json)：新增/修改文件范围、JSON 可解析性、相对链接/锚点、固定来源、摘录字段、RUN 参数、数值引用及材料 SHA-256。静态检查通过仅说明本轮文档检查项通过，命令实际运行、CI 和平台验收没有因此变成 PASS。

## 未实现、阻塞与公开边界

- 自动只读汇总/导出、review/index.json 自动生成、自动复制跨目录结果、通用任意分子输入、第八个计算任务：未实现，本轮不需要新增代码。
- 新文档命令未执行；科学复算、镜像重建、WSLc 实机验收、WSL 升级、CI 执行、真实高级任务中断及 L3/L4 严格断网：本轮均未开展。
- 本地 Docker 已验证七个 task，严格断网限 L0—L2、等价性及指定探针；L4 检查点可保存但不支持恢复。
- WSLc BLOCKED / NOT_EXECUTED；升级与实机验收暂停。CI 静态审查完成，运行 NOT_EXECUTED。
- 源码公开另行确认；`2460eef` 保留为此前候选。独立文档增补及未跟踪方案不自动纳入已确认范围，也未授权首次推送/CI 附件公开。
- 镜像分发 BLOCKED：原生 wheel 的精确构建来源/补丁/选项对应、实际通知与对应源码提供仍有未闭合项，详见 source-materials-final-review.json 与 PUBLICATION_BOUNDARIES。文档增补不解除许可证/来源阻塞。

本轮不新增科学验收结论、发布标签或 Release，不修改既有历史。
