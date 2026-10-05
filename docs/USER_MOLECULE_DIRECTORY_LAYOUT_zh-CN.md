# 用户分子服务：本地目录结构

日期：2026-10-05；LOCAL-SETUP-1。目录准备已完成，代码、schema、profile、请求模板、镜像及新计算仍未实现或执行。空目录和 `.gitkeep` 只用于占位，不表示功能可用。当前文档入口见 [文档索引](USER_MOLECULE_DOCUMENT_INDEX_zh-CN.md)，工程合同见 [技术方案](USER_MOLECULE_TECHNICAL_PLAN_zh-CN.md)。

## 1. 本地布局

```text
D:\AI4Science\
├─ AI4OrgChem\                              原科研工作区，保持原样
├─ ai4orgchem-runtime\                      既有 runtime 仓库与当前文档
│  ├─ docs\                                 当前方案、合同、目录和步骤说明
│  ├─ runtime\user_molecule\               新服务包占位
│  ├─ schemas\                              请求/检查/结果 schema 的预定位置
│  ├─ profiles\user-molecule\              固定配置占位
│  ├─ examples\user-molecule\
│  │  └─ templates\                         请求模板占位
│  ├─ tests\fixtures\user-molecule\        冻结测试夹具占位
│  ├─ validation\user-molecule\            本轮准备记录；后续新服务验收记录
│  ├─ scripts\                              既有目录，后续新增启动器
│  ├─ container\                            既有目录，后续新增专用 Dockerfile
│  └─ locks\                                既有来源锁保留，后续新增独立锁
├─ ai4orgchem-runtime-workspaces\user-molecule\
│  ├─ runtime\                              空目录，预留 runtime 隔离工作区
│  └─ science\                              空目录，预留科学隔离工作区
├─ user-molecule-inputs\
│  └─ requests\                            用户请求目录，位于仓库外
├─ user-molecule-runs\
│  ├─ locks\                                后续本服务的共享锁
│  ├─ scratch\                              后续受限临时空间
│  └─ <唯一 check/run ID>\                  由未来启动器创建，本轮尚不存在
└─ ai4orgchem-runtime-deliveries\
   ├─ <既有候选与审阅包>                     保留原件
   └─ 20261005-user-molecule-preimplementation-setup\
      ├─ before\                            本轮编辑前的方案原字节
      ├─ latest\                            本轮保存的当前文档与准备记录快照
      ├─ BASELINE.json                       基线与保留核查依据
      ├─ LATEST_DOCUMENTS_MANIFEST.json       最新快照大小与 SHA-256
      └─ STATIC_REVIEW.json                  本轮目录/文档核查
```

`runtime` 和 `science` 两个预留工作区保持为空，尚不是 Git checkout，不在其中伪造 `.git` 或复制整个原工作区。后续 W01 从受控提交创建隔离工作区，再明确选择移入的草稿/目录材料；不把原项目所有未跟踪文件一起加入新候选。

## 2. 目录与工作包

| 位置 | 当前内容/状态 | 使用步骤 |
|---|---|---|
| runtime/user_molecule | `.gitkeep`；没有可运行模块 | W02—W04 输入、状态和执行封装 |
| schemas | `.gitkeep`；没有生效 schema | W02 请求/检查/结果合同 |
| profiles/user-molecule | `.gitkeep`；没有启用 profile | W03/W05/W06 参数冻结与数值验收 |
| examples/user-molecule、templates | 目录占位；没有伪造请求或科学样例 | W02 模板、W07 用户示例 |
| tests/fixtures/user-molecule | `.gitkeep`；没有 expected 能量 | W02 解析夹具、W05/W06 科学夹具 |
| validation/user-molecule | directory-manifest.json、implementation-state.json | W01 准备记录；后续各步真实验收 |
| 外部 runtime/science 工作区 | 空目录，Git 工作区 NOT_CREATED | W01 隔离开发、W03 科学适配 |
| user-molecule-inputs/requests | 空目录 | 用户输入准备；私有材料留在仓库外 |
| user-molecule-runs | 本地说明、空 locks/scratch | W04 实际执行输出；当前无新 run |
| 本轮 deliveries 目录 | 前后文档、清单与静态核查 | W01/W07 本地保存和复核 |

schemas 仍采用技术方案中的顶层文件路径，如 `schemas/user-molecule-request-v1.json`；本轮未创建这些文件。scripts、container 和 locks 复用既有目录，不创建假的启动器、Dockerfile 或来源锁。

## 3. 输入和输出约定

未来一个用户请求可放在 `D:\AI4Science\user-molecule-inputs\requests\<自定请求名>\`，包含 `request.json` 与其引用的 `molecule.xyz`。目前没有请求模板，不需要手工尝试执行尚未实现的命令。

未来每次 Check 或 Compute 在 `D:\AI4Science\user-molecule-runs\<唯一 ID>\` 保存自己的输入快照和记录。Compute 引用 Check 的身份，不覆盖检查目录。locks/scratch 是公共运行辅助目录，不是结果记录；具体 scratch 配额、清理和锁实现须在 W04 验证，当前没有自动清理动作。

用户输入、运行日志、矩阵/检查点及临时文件均留在 runtime Git 仓库外；本轮不修改 `.gitignore`。将来需要公开的教学示例须单独审阅后选择复制到 examples，不能自动收集用户私有材料。

## 4. 当前完成范围

本轮完成目录占位、最新文档保存、编辑前备份和静态核查。W01 为 IN_PROGRESS，隔离 Git 工作区尚未创建，W02—W07 为 NOT_STARTED；目录齐备不代表整个 W01 或 D1 已通过。

runtime HEAD 保留为 `0288eb8455a85c2082142dbdc62b7c018adb2e56`。原科研工作区的修改和未跟踪文件、旧候选/来源锁/运行记录不覆盖；WSLc/WSL 升级、Colab 和公开仍按原边界。L4 可保存检查点但不支持恢复的限制保留。本轮不安装依赖、启 Docker、构建镜像、执行科学计算或创建提交。

路径和用途的机器清单见 [directory-manifest.json](../validation/user-molecule/directory-manifest.json)，当前实施状态见 [implementation-state.json](../validation/user-molecule/implementation-state.json)。这些是准备记录，不是新服务验收结果。
