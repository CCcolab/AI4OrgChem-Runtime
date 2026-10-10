# 用户分子服务：已部署的本地目录

2026-10-05 / W01-W04-ENGINEERING-1。以下是实际工作区；先前 LOCAL-SETUP-1 的空目录说明保留在 Git 历史和准备快照。

```text
D:\AI4Science\
├─ AI4OrgChem\                         原科研 checkout，保留修改/未跟踪文件
├─ ai4orgchem-runtime\                 原 runtime main 0288eb8 与未跟踪方案，保持原样
├─ ai4orgchem-runtime-workspaces\user-molecule\
│  ├─ runtime\                         实际工程 Git worktree；从这里运行
│  │  ├─ runtime\user_molecule\      check / compute / report
│  │  ├─ schemas\                     请求/检查/结果合同
│  │  ├─ profiles\user-molecule\     两个禁用 Compute 的工程 profile
│  │  ├─ examples\user-molecule\templates\  AO 工程夹具
│  │  ├─ scripts\                     PS 5.1 引导、PS 7 启动器/监督
│  │  ├─ container\                   新 Dockerfile 与专用 ignore
│  │  ├─ locks\                       新服务锁与不变的旧来源锁
│  │  ├─ tests\                       输入/CPU 及原回归测试
│  │  ├─ validation\user-molecule\   当前候选/工作包/身份状态
│  │  └─ docs\                        当前指南、交付报告和原设计
│  └─ science\                         从独立 v0.3.2 checkout 创建的科学 worktree
│     ├─ software/src/ai4orgchem/qm/user_molecule_adapter.py
│     └─ software/tests/test_user_molecule_adapter.py
├─ user-molecule-inputs\requests\     用户私有 XYZ/请求
├─ user-molecule-runs\                 每次唯一输出；.inputs 下单独只读快照
│  ├─ w01-w04-acceptance\              r2 历史回执，保留
│  ├─ w01-w04-acceptance-r3\           最终镜像集成测试
│  └─ w01-w04-host-final\              最终宿主记录/拒绝测试
├─ ai4orgchem-runtime-runs\.host-locks\ 默认共享 Windows 计算锁
└─ ai4orgchem-runtime-deliveries\20261005-user-molecule-w01-w04\
   ├─ baseline.json / preservation-review.json
   ├─ science.tar / runtime-<构建提交>.tar
   ├─ build-record-r3.json / docker-build-r3.log
   ├─ verification-r3\ / host-final-verification\
   ├─ platform-probes-r3\ / platform-probe-summary-r3.json
   ├─ DOCKER_RECOVERY_zh-CN.md / 修复与恢复核查 JSON
   └─ LOCAL_FINAL_DELIVERY.json / 最终备份与证据清单
```

runtime 与 science 是真实 Git worktree，分支名分别为 implementation/user-molecule-w01-w04，属于不同来源仓库。科学 worktree 共享的是独立发布源码 checkout 的 Git 目录，原 AI4OrgChem 工作区没有切换或重置。

用户输入与运行日志放在仓库外。输入只读快照与可写结果卷分离；输出中的 input/ 是证据副本，不是容器读取的原始输入卷。取消只操作本次已保存 ID。

默认共享锁为 ai4orgchem-runtime-runs/.host-locks/windows-quantum.lock，兼容原启动器；容器另用同一锁根下 quantum.lock。它只协调本 runtime 管理的任务，不能锁住用户独立运行的科研进程。原准备目录 user-molecule-runs/locks 与 scratch 仍保留；它们不是当前默认锁或容器 tmpfs。

用法见 [用户指南](USER_MOLECULE_RUN_zh-CN.public.md)，状态与限制见 [交付报告](USER_MOLECULE_W01_W04_DELIVERY_zh-CN.public.md)。原历史包与准备快照未覆盖；镜像、原始证据和私有输入未自动加入 Git。公开范围另行确认。
