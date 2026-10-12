# 其他计算模块安装与使用说明核查

日期：2026-10-12。审查基线 `1ad48c413a5010b473686372a9dfed443eb705aa`。本轮仅静态检查并补充文档，不执行安装、构建、容器运行、科学计算或新的P12内存准入。

## 修订范围

| 服务 | 发现的说明缺口 | 本轮补充 | 中英文入口 |
| --- | --- | --- | --- |
| 固定案例：表统计、图账本、占据轨道控制 | 直接从安装链接跳到登记，没有完整首次使用顺序 | 共用环境安装、跳过已有安装/登记、任务选择、单条运行及结果判读 | [中文](CURRENT_REGISTERED_CASES_zh-CN.md)／[English](en/CURRENT_REGISTERED_CASES.md) |
| 专题协议：扭转、条件能量、闭合及结构响应 | 中文页依赖历史材料建立预算，模式和模块对应不够直观 | 八项计算用途与真实Task对应、ledger/preflight/live区分、新预算模板和结果字段入口 | [中文](CURRENT_PROTOCOL_CASES_zh-CN.md)／[English](en/CURRENT_PROTOCOL_CASES.md) |
| 高成本：固定多态优化与尺寸/状态比较 | 缺完整单状态命令和前序输出路径示例 | 实际Unit的预检、预算工具和live形式，精确父态output映射、资源和未闭合清理处理 | [中文](CURRENT_HIGH_COST_CASES_zh-CN.md)／[English](en/CURRENT_HIGH_COST_CASES.md) |
| P14：条件能量与结构响应 | 独立构建页过短，未列首次检查、任务次序和四父参数 | 干净Git检出、PowerShell7.3+、CheckOnly与实际build的区别、独立七任务及四父分类步骤 | [中文](CURRENT_P14_BUILD_RUN_zh-CN.md)／[English](en/CURRENT_P14_BUILD_RUN.md) |

三个共用服务家族只登记自己需要的服务，仍使用同一次安装的built-image.json和对应installation-record.json。P14保持独立Dockerfile、588份科学来源和镜像身份，不把它改接到四家安装记录。已安装用户不用每次计算重新构建。

## 静态核查依据

- `scripts/run-installed-runtime.py` 的实际参数和家族拒绝合同；不是按中文展示名构造Task。
- `configs/high-cost-cases-v1.json` 的真实Unit、dependencies与资源；预算工具和宿主 `snapshot_inputs` 的精确前序检查。
- 原专题预算schema、6300秒上限和七个live任务集合；P07不提供live。
- `scripts/build-docker.ps1`、`container/Dockerfile`、`scripts/run-docker.ps1`、原RUN合同：P14来源预检不等于构建，四父目录必须在同一OutputRoot下。
- 每对中英文PowerShell命令一致；预算JSON、父态映射、文件链接和说明步骤另做静态校验。

实际结果：四对中英文共16组命令块逐一一致，每种语言35条操作命令的参数／路径形式核对通过；48个相对链接存在。高成本示例Unit和父态映射与固定配置相符，专题预算schema与七项集合一致。442个已有受保护文件与HEAD内容相容；其中12个已有工作区／Git换行差异保留，不改写工作字节。该结果是静态文档核查，不是35次任务执行。

这些检查验证说明与现有接口的衔接，不证明用户机器已安装成功，也不替代新镜像的科学验收。文档中的运行命令可供用户按所选任务执行，但本轮没有执行它们。

## 保留的边界

只有原高成本苯G和N12-G两个先导有历史数值验收，不将78个注册态写成78态通过，不重复已通过计算或P12资源探针。live预算和依赖必须对应实际本轮运行；未知创建/清理保留RESERVED及隔离锁，不能手工删锁或清预算重试。内存和科学阈值保持原合同。

用户分子条件态Compute仍关闭；本文不开放任意分子DFT、优化或新条件态。L4可保存检查点但不能resume，历史L3/L4严格断网验收未执行。普通WSL2 Check不授予原生Compute资格；不升级WSL、不恢复已撤下的平台入口、不公开镜像。v0.1.0标签和附件保持原身份。
