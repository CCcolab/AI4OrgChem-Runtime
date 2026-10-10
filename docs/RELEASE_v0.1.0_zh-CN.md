# AI4OrgChem Runtime v0.1.0 — 受限本地计算与可追溯复核

这是 Runtime 的首个源码与用户指南版本，独立于原科学项目 AI4OrgChem v0.3.2。网页材料保留的 v0.3.0-candidate 是内部历史交付标识，不是 Runtime 版本。正式版本、标签与下载入口为 [v0.1.0 Release](https://github.com/CCcolab/AI4OrgChem-Runtime/releases/tag/v0.1.0)。

## 用户可以做什么

- 提交自己的XYZ，在H/C/N/O、中性闭壳层单重态、RHF/6-31G(d)、≤20原子且AO≤80范围内执行普通单点，保存能量、轨道和AO密度矩阵。资格是首版端点数值资格，不是全部轨道或真实基态认证。
- 使用登记对象进行固定案例及专题协议计算，或只读复核保存的统计、图规则、能量账本和数值见证。不能把固定分子任意替换成自己的分子。
- 使用版本锁定的源码安装流程构建自己的Docker环境，登记每个服务的独立安装身份，保留输入、日志、退出码、资源、预算及清理记录。
- 阅读[在线指南](https://cccolab.github.io/AI4OrgChem-Runtime/)或离线指南；网页不上传分子、不在线执行科学计算。

## 三项下载附件

| 附件 | 用途 |
|---|---|
| AI4OrgChem-Runtime-source-v0.1.0.zip | 安装器制作的源码包，带Git commit/tree/blob身份证明；解压到全新目录后使用，不含环境或依赖二进制 |
| AI4OrgChem-Runtime-guide-v0.1.0.zip | 10成员静态指南包，解压后打开docs/index.html；不是Runtime安装包 |
| SHA256SUMS.txt | 核对两个ZIP的实际大小对应字节哈希；正式发布资产哈希另随Release附件登记 |

GitHub自动生成的Source code ZIP不包含本项目安装身份证明；需要ZIP安装路径时请选择名称明确的source-v0.1.0附件。或使用Git克隆指定标签：

```powershell
git clone --branch v0.1.0 --depth 1 https://github.com/CCcolab/AI4OrgChem-Runtime.git D:\chem-work\runtime-v0.1.0
Set-Location D:\chem-work\runtime-v0.1.0
git rev-parse HEAD
```

源码ZIP解压后，进入包含scripts的根目录。按[源码安装指南](SOURCE_INSTALLATION_zh-CN.md)执行prepare/build，在生成的runtime目录按服务登记installation record。需要已有Python3.12+、Docker Linux/amd64及构建网络；包不会自动安装系统功能或启动计算。不继承维护者历史镜像的科学PASS。

## 实际证据与剩余范围

基准f3c6bdf的两个公开CI job及Pages已通过；此前全面本地工程集合537项，535通过、2项明确跳过，见[全面检查](../validation/COMPREHENSIVE_CHECK_20261010_zh-CN.md)。这些记录各自绑定原提交，发布材料的增补不改写历史身份。

原失败浏览器的HTML、ZIP、清单三按钮和实际文件补验由外部审阅者经项目负责人报告通过；登记为限定PASS，证据来源是该报告，不冒充维护者独立执行。对应旧网页字节、报告范围及缺失原始附件见[外部补验登记](../validation/web-guide/external-browser-retest-20261010.json)。发布链接文字更新不改导出算法，新的网页包另记录其实际字节，不能代用旧哈希。

条件态Compute仍BLOCKED；全canonical/虚轨道门禁未实现，普通波函数稳定性未执行。P11/P12的78个登记态只有两个旧先导验收，其余76态、完整组装及新安装科学重放未执行。L4检查点不支持恢复。首版不包括用户DFT、离子、开壳层、通用优化或扫描，也不认证原项目全部命题。

公开预构建镜像继续不分发；准确对应源码、第三方通知及部分原生库/字体事项仍见[公开边界](PUBLICATION_BOUNDARIES_zh-CN.md)。Runtime自有代码适用Apache-2.0，第三方与YouMind材料按其原有权利说明，不因本Release改变许可。

## GitHub右侧板块

Releases提供上述版本和附件；Packages保持为空，没有发布容器或PyPI软件包。作者、维护者及协助见[AUTHORS.md](../AUTHORS.md)，引用元数据见[CITATION.cff](../CITATION.cff)。Contributors和Languages由GitHub根据真实提交与文件自动生成；不改历史署名或人为调整语言比例。

## English release scope

v0.1.0 is the first source-and-static-guide release for scoped local RHF calculations, registered fixed-protocol replay and traceable review. It provides a Git-proof source ZIP, a guide ZIP and checksums; it does not distribute a prebuilt image or a complete environment. New installations require their own image registration and execution evidence. Conditional Compute, full orbital qualification, wavefunction stability and unexecuted high-cost states retain their documented limits. No new molecular computation or local image rebuild was performed for this release.
