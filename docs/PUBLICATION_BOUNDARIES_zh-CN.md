# 源码公开、镜像分发与本地候选交付

## 2026-10-09公开同步实绩（最新状态）

用户已授权公开本次候选的完整历史、源码材料及用户提供的网页指南，公开仓库为[CCcolab/AI4OrgChem-Runtime](https://github.com/CCcolab/AI4OrgChem-Runtime)。首推main为`06d50885bdccf31f83b89229c1513121542375d5`；[Actions run 37933616122](https://github.com/CCcolab/AI4OrgChem-Runtime/actions/runs/37933616122)三个限定job均成功，日志与证据附件属于授权公开范围。详见[公开同步记录](GITHUB_PUBLIC_SYNC_20261009_zh-CN.md)。

这是源码与指南公开同步，不是镜像分发或全部科学服务认证。Pages尚未启用，不提供在线计算；新版本号未确定，没有正式标签或Release。YouMind十一Skill导出由用户延后。公开授权不替第三方授予权利，根Apache-2.0和NOTICE的第三方材料边界继续适用。镜像分发仍BLOCKED_LOCAL_ONLY，WSLc仍BLOCKED／NOT_EXECUTED并暂停；旧用户分子条件态Compute仍BLOCKED，L4可保存检查点但不支持恢复运行。

下文2026-10-03及“同步准备增补”保留各自历史状态；其中未推送、公开待确认和远端CI NOT_EXECUTED不代表本段最新状态，不改写旧证据。

历史核对日期：2026-10-03。当轮仅完成本地材料和备份；未设置 remote、推送、改变可见性、打正式标签或发布 Release。

## 已闭合的本地材料

- 105 个 Debian binary 包映射到 73 组精确 source package/version；236 份 `.dsc`/上游归档/Debian 补丁归档取得并校验。三个官方 Sources 索引与 InRelease 签名验证通过，信任锚为固定候选镜像自带 Debian archive keyring。
- 17 个锁定 Python 分发包加 pip 的 18 份精确版本 sdist，均与 PyPI 版本 JSON 声明的 SHA-256 一致。此校验不等于独立签名或原生 wheel 构建证明。
- pip/setuptools 内嵌清单纠正为 52 条环境记录：原统计漏计 pip 缩进行的 5 个传递组件，每份 pip 各漏 5 条。634 个实际内嵌 Python 文件与精确父包 sdist 全部一致，原许可证和版权完整保留。setuptools 内嵌 autocommand 为 LGPLv3，不应随主体标为 MIT。
- 原镜像 pip 内独立 vendor 许可证未找到；从匹配父包 sdist 补出 21 份通知，独立装入本地候选包，没有修改旧镜像。Libxc/HDF5/CPython/h5py 官方版本源码已取得；XCFun 固定提交及 PySCF 补丁、libcint v6.1.3 源码已保存。XCFun 补丁静态适用性检查通过，未应用到科学运行镜像。

版本匹配、签名、源码匹配、镜像支持是不同结论；实际记录见 validation/source-materials-final-review.json、source-verification.json、vendor-license-mapping.json 和 native-provenance.json。

## GitHub 源码公开尚缺什么

限定公开内容为 runtime 自有源码、构建与锁、候选适配、如实记录的报告及已署名上游许可/构建配方/补丁；不把镜像、下载的依赖归档、运行日志、私有结果或原开发工作区加入 Git。compliance/README.md 明确第三方文件授权边界，根 Apache-2.0 不覆盖全部材料。

在此范围内，没有发现必须先完成所有原生库二进制来源调查才能公开 runtime 源码的技术条件。源码候选可审阅，**没有公开授权，仍未发布**。公开前仍须：确认目标仓库所有权/地址与可见性、取得明确源码公开授权、检查最终拟上传文件及报告中的本地路径披露范围，完成目标仓库推送操作。当前无 remote；实际 CI 运行 NOT_EXECUTED，可在获授权的目标仓库推送后执行，不伪造预先 PASS。

WSLc 暂停不妨碍如实公开“候选适配、尚未支持”的源代码，但阻止将该仓库宣传为已验收的 WSLc 产品。不能把仅公开源码与 v0.1.0 正式镜像 Release 合并为同一次默认授权。

## 容器镜像分发尚缺什么

镜像保持原 ID sha256:ddc45b1fe500ed3d5ed30520eb4e49f3969cb69f02121f28e2ff851f7a724f54，构建 runtime 为 f30b2906794d14f9030daab779c0d6a7cd4bd6f7。新审查/材料提交不写成旧镜像构建提交。

1. 各 wheel 内嵌 libgfortran/libgomp/libquadmath 的准确源版本、补丁和构建记录未取得。ELF `.comment` 在这些运行库中为空；其他库的 GCC/Clang 编译器标记不能反推运行库来源。Debian gcc-12 源码不能冒充这些 wheel 内嵌运行库的对应源码。
2. SciPy OpenBLAS 开发提交、NumPy/PySCF BLAS 构建来源未闭合。父包 sdist 和文件名不是原生库精确来源证明。
3. h5py Linux wheel 使用上游自建 manylinux HDF5 镜像；源码配方未提供本轮实际 wheel 所用构建镜像不可变身份。HDF5 2.0.0 API/版本源码已确认，但 libaec/libsz 版本、补丁和实际构建来源仍 UNKNOWN。
4. PySCF 原生库实际构建选项、XCFun 补丁是否成功应用缺少 wheel 构建记录。保存原始源码和补丁并通过 apply --check，只闭合候选配方，不证明二进制对应。
5. 最终分发形式须实际向接收方提供完整通知和适用对应源码，并核查 LGPL 修改/重新链接条件。当前本地补充包已形成，公开获取路径尚未启用；原镜像本身未装入新增通知。不能只推送旧镜像并把本地路径当作接收方能访问的来源。MPL 的源码与通知要求见[官方第 3 节](https://www.mozilla.org/en-US/MPL/2.0/)。

16 个自由文本 Debian 版权文件的精确单一 SPDX 表达式仍未归一化；完整原文与精确源归档已保存。这是进一步文件级判读事项，不应再描述成“未取得 Debian 源码”，也不能只因未生成单一 SPDX 字符串就推断许可缺失。原始多许可和例外继续保留。

除以上材料问题外，公开镜像还缺 GHCR 目标/权限/可见性核对、明确镜像发布授权、推送拉取实测和 registry digest。若仍按实施方案首发 WSLc，则还缺真实最低入口与 WSL2/WSLc 对照；当前全部暂停。Docker 已验证范围可独立如实描述，但不自动改变首发范围或解除发布阻塞。

## 本地候选包与备份

目录：D:\AI4Science\ai4orgchem-runtime-deliveries\20261003-final-candidate。包包含现有镜像导出、运行记录、当前 Git bundle 与源码快照、完整通知补充、取得的源码归档与校验/签名记录。package-manifest.json 记录实际候选源码提交和旧镜像构建提交；package-verification.json 是执行后的归档校验记录。旧 20261002 备份保留，不覆盖。

这是本地候选交付和同盘备份，不是正式 Release，也不是已完成环境恢复的证明。镜像支持、来源 UNKNOWN、WSLc BLOCKED、CI NOT_EXECUTED 及 L4 无恢复能力均随包声明。

## 只是后续增强的事项

独立存储副本、真实恢复演练、镜像签名/供应链证明、机器可交换 SBOM、自动发布流水线属于后续增强，不扩展为通用合规平台。L3/L4 严格断网和完整 L4 中断实测不在本轮重复；低成本停止探针仍是尚缺的平台验收。WSLc L3/L4 可待最低入口恢复后按预算单独验证。L4 不支持恢复运行，实现 resume 不属于欠账。

## 2026-10-09同步准备增补

上文为2026-10-03历史材料范围，不替代新增普通分子服务、三批固定案例及网页的当前记录。现已形成完整本地候选和网页功能名修订；拟建CCcolab/AI4OrgChem-Runtime，仓库尚未创建／推送，Pages未启用。当前文件、125提交基线、有限凭证扫描、实施方案／评审材料及网站权属待确认范围见[同步准备](GITHUB_SYNC_PREPARATION_20261009_zh-CN.md)。完整历史公开需明确接受其正文；仅最新树无秘密不证明历史可公开。

镜像分发的新增组件与字体问题见[2026-10-09组件附录](../compliance/HIGH_COST_COMPONENTS_20261009_zh-CN.md)，继续BLOCKED_LOCAL_ONLY。上文旧镜像身份仍是历史对象，不冒充最新构建。远端CI NOT_EXECUTED、WSLc BLOCKED／暂停及L4不支持恢复运行的限制继续保留；同步准备不重新计算或改写这些结论。
