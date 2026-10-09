# Runtime 本地网页指南

2026-10-09已接纳 YouMind 更新的 `v0.3.0-candidate` 为本地文档候选，本轮未发现必须继续修改的功能或声明问题。网页入口为 [docs/index.html](index.html)，可直接在本地浏览器打开。

完整原包10成员保存在 [runtime-guide/source](runtime-guide/source/README.md)，原ZIP备份在 [runtime-guide/archive](runtime-guide/archive/ai4orgchem-runtime-guide-v0.3.0-candidate.zip)。网页是使用指南，本地科学计算由对应Runtime入口执行。GitHub推送和Pages部署留待后续整体同步，当前未执行。

## 验证与身份

原ZIP为389414字节，SHA-256 `ca0e947b0e11ae931ee097780e9872c63fd5a9d72cfdb6dd2798e5f8e27d8b8d`。原HTML为183232字节，SHA-256 `b4762b4b4f1851afc1c13f177a7f1a08bbacb91ada1fe977cd3ce7567d110cca`。网页入口、导入快照和原包的字节身份均核验一致。

本地 Edge 154.0.4258.62 无界面会话已验证：ZIP CRC／安全路径、360/768/1440默认和全展开布局、79个复制按钮的逻辑文本、三路径与清除、七项维护下载、独立HTTP根／模拟仓库子路径及导出默认重开。79个复制中42个原始字节一致、37个仅Windows CRLF不同；七个维护导出均与原包字节一致。真禁JavaScript的关键内容可读；搜索仅记录行为。真实200%缩放、完整键盘和多浏览器未执行，当前接纳不宣称完整网页平台认证。

第三批78个固定状态接入、仅两个旧候选单态通过科学验收，以及新源码安装身份的范围均已准确区分。网页记录的源码候选575127b与受测构建59f576c是既有快照，本次导入提交不冒充科学镜像构建提交。不重算P12，不重复旧PASS的内存预检，不升级WSL、不开展WSLc验收；原科学规则和数值门槛保留。

机器记录见 [integration-20261009.json](../validation/web-guide/integration-20261009.json)、[浏览器实测](../validation/web-guide/browser-20261009.json)和[包装核验](../validation/web-guide/package-20261009.json)。本地原始审阅证据保存在 `D:\AI4Science\ai4orgchem-runtime-deliveries\20261009-guide-v030-final-review`。

## 后续维护

以 `docs/index.html` 为唯一日常编辑入口。页面布局、交互、复制与下载逻辑均为完整自包含HTML/CSS/JS，后续可以由本地Codex直接维护。修改后同步重新导出的文案、README、来源、检查和迁移材料，保留旧ZIP及哈希，更新验证记录并作独立本地提交。导入目录中的原包和快照保留为历史材料，不各自修改成第二份活动网页。

页面的支持声明必须分别注明已实现、实测范围和未执行项目。普通分子RHF、固定研究任务与legacy条件Compute分别表述；来源身份登记不等于完整科学验收。镜像分发BLOCKED、WSLc BLOCKED、远端CI NOT_EXECUTED，以及检查点不支持恢复运行的限制继续保留。

包内网页权属和来源说明保留；网页材料未因保存到仓库自动扩大为Runtime源码许可。公开范围与实际托管按后续用户指令处理。本轮仅保存文档与验证记录，没有新增在线计算服务或修改科学代码。
