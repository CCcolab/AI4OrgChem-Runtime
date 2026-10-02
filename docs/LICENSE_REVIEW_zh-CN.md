# 实际候选镜像组件许可证审查

审查日期：2026-10-03。对象为本地 `sha256:ddc45b1fe500ed3d5ed30520eb4e49f3969cb69f02121f28e2ff851f7a724f54`，不是新构建镜像。断网、非 root 读取实际 dpkg、Python METADATA/RECORD、许可证文件及共享库 ldd；只加载数值库读取版本，没有科研计算。审查完成但有未解决项，**发布许可就绪 BLOCKED**。

全量逐组件清单见 [component-license-inventory.json](../validation/component-license-inventory.json)：105 Debian 包、虚拟环境 18 Python 分发包、基础环境另一份 pip，42 条内嵌依赖版本记录（含环境重复项）、191 共享库文件。203 份许可证/署名/版本文件全文与 SHA-256 保存在 `D:\AI4Science\ai4orgchem-runtime-runs\20261003-review\components.json`。原始包作者/版权以这些全文为准，不用本表替代署名。逐组件版本、来源、许可证据、义务、缺失项都有记录；不是完成所有文件级许可证判定的声明。

## 系统、Python 与署名

| 对象 | 版本/来源 | 许可及义务 |
|---|---|---|
| runtime、AI4OrgChem | 构建 runtime f30b290...；科学提交 28511f3... | Apache-2.0；LICENSE/NOTICE 保留；上游 AUTHORS.md 保留。记录修改与归属，不用署名声称科学认证 |
| Debian bookworm 包 | 实际 dpkg 105 包，精确版本及 source package 在清单；基础镜像摘要见 base-image.lock.json | /usr/share/doc/<包>/copyright 全部可读；多数 DEP5 标签，多许可按文件区分，16 包为自由文本，精确 SPDX 表达式 UNKNOWN。通用条款位于 /usr/share/common-licenses；不能把全部包标为 Apache |
| CPython | 3.12.13；官方 Python slim 基础镜像 | /usr/local/lib/python3.12/LICENSE.txt 已采集，PSF 与历史/附属条款需完整保留 |
| NumPy | 2.5.1，锁定 PyPI wheel | 元数据 BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0；另含数值库许可；保留全部随包 LICENSE，不只保留主 BSD |
| SciPy | 1.18.0，锁定 PyPI wheel | BSD-3-Clause，随包 OpenBLAS/LAPACK/GCC 等条款；保留完整文本和第三方署名 |
| PySCF | 2.14.0，锁定 PyPI wheel | 主体 Apache-2.0，LICENSE/NOTICE 可读；内嵌库不自动继承 Apache |
| h5py | 3.16.0，锁定 PyPI wheel | 主体 BSD-3-Clause、LZF 署名保留；内嵌 HDF5/libaec 等另核对 |
| attrs/jsonschema/jsonschema-specifications/rpds-py/referencing/iniconfig | 26.1.0 / 4.26.0 / 2025.9.1 / 2026.6.3 / 0.37.0 / 2.3.0 | MIT；保留版权、许可与免责 |
| pytest/pluggy/PyYAML/setuptools/pip | 8.4.2 / 1.6.0 / 6.0.3 / 78.1.0 / 25.0.1 | 主体 MIT；setuptools 与 pip 内嵌组件各自许可，42 条版本记录不等于 42 个独立已结案许可 |
| Pygments/typing_extensions/packaging | 2.21.0 / 4.16.0 / 26.3 | BSD-2-Clause / PSF-2.0 / Apache-2.0 OR BSD-2-Clause；保留原始选择、条款与署名 |

## 实际携带的数值库

| 库 | 实际版本证据 | 许可与未解决事项 |
|---|---|---|
| NumPy OpenBLAS/LAPACK | NumPy show_config：0.3.33.112.0 | 随 wheel BSD/LAPACK 许可存在；对应编译来源仍应映射 |
| SciPy OpenBLAS/LAPACK | SciPy show_config：0.3.31.dev | 随 wheel BSD/LAPACK 许可存在；开发版本精确 commit UNKNOWN |
| PySCF OpenBLAS | 文件名含 0.3.3；不当作已验证精确版本 | 实际来源/完整第三方署名映射 UNKNOWN |
| libgfortran/libgomp | 实际 so/SONAME 和 ldd 已记录；精确 GCC 编译版本 UNKNOWN | GPL 与 GCC Runtime Library Exception 需逐份核对；运行库例外不等于整个镜像免除许可义务 |
| libquadmath | 多份实际 so 已记录，精确 GCC 编译版本 UNKNOWN | LGPL 系列；逐份版本、条款和对应源码交付路径未齐 |
| HDF5 | h5py runtime 2.0.0 | HDF Group BSD 风格；现有 h5py 许可文本不足以确认完整独立 HDF5 署名已随 binary 交付 |
| libaec/libsz | 有实际 binary，精确版本 UNKNOWN | 不凭 libsz 名称推断原 SZIP 授权；实际构建、许可及署名需映射 |
| Libxc | API 返回 7.0.0 | 官方 7.0.0 COPYING 已补充采集，为 MPL-2.0；对应源码和实际 binary 构建映射仍 UNKNOWN |
| XCFun | API 返回 2.1.1 | 固定构建配方提交 a89b783497d4fe146b477ac7a053303ce4189e9a 的 MPL-2.0 文本及源码已取得，PySCF 自带补丁另保存；实际 wheel 应用补丁情况 UNKNOWN，不能用未修改 v2.1.1 源码替代 |
| libcint | 安装 cint.h 为 6.1.3 | v6.1.3 官方 Apache-2.0 文本及源码已补充取得；精确 binary 构建来源尚未结案 |

191 个共享库包括 Python 扩展与上述依赖，不表示 191 个独立软件项目。ldd 为动态链接证据；未由 ldd 推断静态内嵌代码许可或证明许可证完整。即使某库未在 P14 中被调用，只要随镜像分发仍需审查。

## 发布前必须完成的事项

1. 为 GPL/LGPL 系统包及内嵌运行库匹配精确源版本、补丁、构建材料，并建立符合对应许可证的源码随附/提供机制。仅有 Debian tracker 或 GitHub 首页链接不足以证明对应源码义务已满足；不自动替发布者作出书面承诺。[GPL 条款](https://www.gnu.org/licenses/gpl.html)、[LGPL 条款](https://www.gnu.org/licenses/lgpl.html)。
2. 为 MPL XCFun 明确对应源码的获取方式并保留许可通知；发布 executable form 时不能遗漏源码提供信息。[MPL 2.0 第 3 节](https://www.mozilla.org/en-US/MPL/2.0/)。
3. 补全 PySCF/HDF5/libaec/libsz 等内嵌库的原始许可和署名包；核查精确 binary 来源，未知版本继续 UNKNOWN。不得为解决许可问题随意替换科学库或浮动升级。
4. 完成 pip/setuptools 内嵌依赖与 16 个系统自由文本版权文件的文件级映射。原始文本存在不等于机器提取标签完整；不能自动把 GPL 字样或多许可任选项改成单一许可证。
5. 镜像 `org.opencontainers.image.licenses=Apache-2.0` 只能描述 runtime 自有代码，不代表所有内容都属 Apache。现有镜像不修改、不重新标为全面许可合格；未来合规构建须提供独立第三方清单和通知。

续审补充：HDF5 2.0.0 官方 LICENSE 主许可为 BSD-3-Clause，完整文本已另存；镜像本身尚未增加这些通知，libaec/libsz 精确版本和完整来源仍 UNKNOWN。实际镜像 203 份文本加 8 份上游材料组成 211 文件补充包，ZIP 逐文件哈希校验 PASS，73 组 Debian source package/version 的对应源码尚未取得。详情见 [材料记录](../validation/license-materials-review.json)、[全量材料锁](../validation/license-materials-manifest.json)及[对应源码方案](CORRESPONDING_SOURCE_zh-CN.md)。许可材料取到不等于 binary 对应关系已证明，也不等于分发合规已完成。

本轮保留全部原许可文本，没有发现自有代码署名丢失；但第三方映射与源码提供事项足以继续阻塞公开镜像发布。没有替换依赖、重建镜像或对外分发。
