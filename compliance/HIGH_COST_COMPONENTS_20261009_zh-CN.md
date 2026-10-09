# 高成本候选镜像的许可材料补充

本次实际审查对象为 `sha256:18dcd1da2e634cf6ab8d49a7281ca853c0a393e140ac95c6ec00448a3fc934bc`，不把结果自动移用到全部历史镜像。**镜像分发仍为 BLOCKED_LOCAL_ONLY，源码公开另行确认。** 原锁、镜像身份和封存记录保持。

机器摘要见 [许可附录](high-cost-license-addendum-20261009.json)。完整原文、来源归档、层校验和哈希材料保存在本地 `D:\AI4Science\ai4orgchem-runtime-deliveries\20261009-six-issue-remediation\licenses`，未把大体积归档或字体二进制加入 Git。

| 组件 | 已核实许可 | 重要范围与义务 |
| --- | --- | --- |
| geomeTRIC 1.1.1 | BSD式许可加额外 Non-AI 条款 | 保留完整四项条件、版权、作者与免责声明；限制把软件源码、二进制及修改纳入机器学习训练数据集，不能简称标准 BSD-3-Clause。[实际版本正文](https://raw.githubusercontent.com/leeping/geomeTRIC/1.1.1/LICENSE) |
| NetworkX 3.6.1 | BSD-3-Clause | 保留版权、许可与免责声明，不借作者姓名背书；旧元数据 `License=null` 不等于无许可。[版本正文](https://raw.githubusercontent.com/networkx/networkx/networkx-3.6.1/LICENSE.txt) |
| six 1.17.0 | MIT | 保留 Benjamin Peterson 的版权及许可正文 |
| Pillow 11.3.0 | 核心 MIT-CMU | 保留 PIL/Pillow 权利人与许可；wheel 携带的原生图像／codec 库另查。[核心许可](https://raw.githubusercontent.com/python-pillow/Pillow/11.3.0/LICENSE) |
| RDKit 2026.3.4 | 本体 BSD-3-Clause；wheel 打包代码 MIT | 分别保留 RDKit 与 Christopher Kuenneth 署名；本体许可不覆盖全部原生库和字体。[本体许可](https://raw.githubusercontent.com/rdkit/rdkit/Release_2026_03_4/license.txt)、[打包来源](https://github.com/kuelumbus/rdkit-pypi) |

实际23个发行包、237份通知/元数据、413个原生库身份已记录；50项 `License-File` 声明均已找到。105个dpkg包对应既有精确source package/version，254份既有源码归档哈希全部匹配。191个继承原生库与旧清单身份一致，222个新增库另列。上述哈希与对应关系不是完整分发法律认证。

新增Python源码对应为 geomeTRIC49/49、NetworkX580/580、six1/1、Pillow96/96、RDKit293/294；RDKit生成的 `RDPaths.py` 仍待生成来源补证。官方源码版本明确不等于所有wheel原生构建输入已证明。

剩余镜像分发事项：

1. wheel携带的GCC runtime、OpenBLAS、HDF5/libaec/libsz、XCFun等精确源码、补丁和实际构建对应仍有缺口；Debian同名包不代替wheel库。
2. RDKit/Pillow原生库及字体分别提供通知和适用材料，不能套用包主体许可。
3. 实际 `Amadeus.ttf` 的随包说明没有明确再分发授权。后续需补授权，或在独立新候选中去除该非科学字体并验证；本次未删除字体或修改受测镜像。
4. geomeTRIC附加条款须如实交付，RDPaths生成来源须补证；通知与对应源码获取机制仍需验收。

这些事项限制当前镜像分发，不撤销已保存的本地计算记录。原生WSL2复用现有环境也须登记自己的依赖身份，不能借此假定第三方分发问题已经消失。
