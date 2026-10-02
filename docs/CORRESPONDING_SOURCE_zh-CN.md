# 第三方通知与对应源码交付方案

对象：已验证候选镜像 `sha256:ddc45b1fe500ed3d5ed30520eb4e49f3969cb69f02121f28e2ff851f7a724f54`。本方案不构成发布者书面源码提供承诺，也不宣称已满足全部分发义务。公开发布保持 BLOCKED。

最新执行结果：73 组 Debian 精确源码已取得并通过签名索引与归档哈希验证；18 份 Python sdist、4 份原生/基础版本源码、已锁科学提交归档与 XCFun/libcint 材料均已保留。52 条内嵌环境记录及 634 个 Python 文件来源已映射；具体阻塞和源码公开/镜像分发区别见 PUBLICATION_BOUNDARIES_zh-CN.md。下述首次材料包是历史记录，当前包为 20261003-final-candidate。

## 已形成的本地材料

`scripts/collect-license-materials.py` 从实际镜像审查证据提取完整许可证和署名，保持镜像路径层次；可选下载官方补充材料。输出 `manifest.json` 和 `third-party-materials.zip`，对 ZIP 每个材料文件重新计算 SHA-256。包内 manifest 与仓库验证记录说明来源与未知项。原始镜像、科学依赖和验收结果不改变。

默认离线运行；`--fetch` 才访问上游。首次下载的哈希仅锁定本次取到的材料，不证明原始 wheel 使用这些源码构建。上游标签 URL 可能变化，后续重取必须与已记录哈希比较，不能覆盖旧锁后宣称一致。镜像文本经 UTF-8 导出；原证据文件哈希和每条原文本哈希单独保留。

本地材料目录：`D:\AI4Science\ai4orgchem-runtime-deliveries\20261003-license-materials`。它是许可材料补充包，不替代 20261002 科学交付备份；同一磁盘也不是灾难恢复副本。

## 对应源码要求

1. Debian 包：按实际 dpkg 的 source package 和精确 source version 去重建清单；取得对应 `.dsc`、上游 tarball、Debian 补丁包和构建/安装材料，校验仓库签名及文件哈希。保留 source version 中 epoch/revision。未取得前清单标为 NOT_ACQUIRED。包项目首页和 source version 清单不能替代源码。
2. PySCF：保留版本构建配方及原补丁。XCFun 配方固定提交 `a89b783497d4fe146b477ac7a053303ce4189e9a` 并应用 `pyscf/lib/libxcfun.patch`；不能用未修改的 v2.1.1 发布包替代。配方包含允许补丁失败的命令，因此必须取得 wheel 构建记录确认哪些修改实际进入 binary。API 版本为 2.1.1 不足以证明对应关系。
3. libcint：配方 v6.1.3 与已安装头文件一致，但仍需确认 wheel 实际构建选项及来源。Libxc 配方 7.0.0 与 API 一致；完整许可材料、源码、构建记录均需核对。
4. HDF5：运行版本 2.0.0 的官方 LICENSE 可补充署名，但原 h5py wheel 的来源、补丁、构建选项及 libaec/libsz 精确版本仍需查证。SONAME 不是发行版本。
5. 数值库/GCC：各 wheel 自带通知完整保留；逐二进制确认 OpenBLAS 开发提交、GCC 源版本及编译补丁。区分 libgfortran/libgomp 的 GPL 加运行库例外与 libquadmath 的 LGPL 条款，不能把例外扩展到所有库。

## 未来发布时的操作

优先随候选镜像交付经核验的对应源码归档、补丁、构建材料及通知包，用公开可访问且与 binary 对应的不可变文件和哈希组织材料。逐组件确认适用许可证所要求的源码提供方式、通知和可修改/重新链接条件。不能用一个泛化声明取代 GPL/LGPL/MPL 各自要求，也不自动选择书面要约途径。

材料齐备后再审查分发包实际内容、获取路径和源码对应关系，更新发布就绪状态。当前不重建、不打正式标签、不上传镜像、不创建 Release。WSLc 为 BLOCKED / NOT_EXECUTED，CI 为静态审查完成、运行 NOT_EXECUTED；L4 保存检查点但不支持恢复运行。
