# Runtime 本地网页指南

## 2026-10-09公开同步后的当前状态

Runtime源码及用户提供的网页指南已按用户授权同步到[公开仓库CCcolab/AI4OrgChem-Runtime](https://github.com/CCcolab/AI4OrgChem-Runtime)，首推提交为`06d50885bdccf31f83b89229c1513121542375d5`。[Actions run 37933616122](https://github.com/CCcolab/AI4OrgChem-Runtime/actions/runs/37933616122)三个限定job均成功；详见[公开同步实绩](GITHUB_PUBLIC_SYNC_20261009_zh-CN.md)。网站目前是仓库中的使用指南，Pages未启用，不提供在线计算，也不把CI成功视作全部网页／科学验收。

源码与指南的公开范围已获用户授权；该授权不替第三方授予权利，YouMind来源、原包及NOTICE许可边界继续保留。十一Skill导出已延后，不作为已实现Skill交付；新版本号未确定，未打正式标签或发布Release。镜像分发BLOCKED_LOCAL_ONLY、WSLc BLOCKED／NOT_EXECUTED且暂停、旧条件态Compute BLOCKED及L4不支持恢复运行均未改变。

以下各轮导入、改名与推送前局部验收属于历史记录；其中“未推送／公开待确认／远端CI NOT_EXECUTED”保留当时意义，当前状态以本段及新同步记录为准。当前活动网页仍以docs/index.html为唯一编辑入口，维护字节增补另行保存身份，不把此前浏览器实测套用给后来字节。

以下导入／模块改名章节保留各自历史字节；当前网页身份与导出见文末“推送前验收记录口径修订”。

2026-10-09已接纳 YouMind 更新的 `v0.3.0-candidate` 为本地文档候选，本轮未发现必须继续修改的功能或声明问题。网页入口为 [docs/index.html](index.html)，可直接在本地浏览器打开。

完整原包10成员保存在 [runtime-guide/source](runtime-guide/source/README.md)，原ZIP备份在 [runtime-guide/archive](runtime-guide/archive/ai4orgchem-runtime-guide-v0.3.0-candidate.zip)。网页是使用指南，本地科学计算由对应Runtime入口执行。GitHub推送和Pages部署留待后续整体同步，当前未执行。

## 验证与身份

原ZIP为389414字节，SHA-256 `ca0e947b0e11ae931ee097780e9872c63fd5a9d72cfdb6dd2798e5f8e27d8b8d`。原HTML为183232字节，SHA-256 `b4762b4b4f1851afc1c13f177a7f1a08bbacb91ada1fe977cd3ce7567d110cca`。导入时网页入口、导入快照和原包的字节身份均核验一致；下列模块名称修订产生新的活动网页身份，原包与导入快照继续保持原字节。

本地 Edge 154.0.4258.62 无界面会话已验证：ZIP CRC／安全路径、360/768/1440默认和全展开布局、79个复制按钮的逻辑文本、三路径与清除、七项维护下载、独立HTTP根／模拟仓库子路径及导出默认重开。79个复制中42个原始字节一致、37个仅Windows CRLF不同；七个维护导出均与原包字节一致。真禁JavaScript的关键内容可读；搜索仅记录行为。真实200%缩放、完整键盘和多浏览器未执行，当前接纳不宣称完整网页平台认证。

第三批78个固定状态接入、仅两个旧候选单态通过科学验收，以及新源码安装身份的范围均已准确区分。网页记录的源码候选575127b与受测构建59f576c是既有快照，本次导入提交不冒充科学镜像构建提交。不重算P12，不重复旧PASS的内存预检，不升级WSL、不开展WSLc验收；原科学规则和数值门槛保留。

机器记录见 [integration-20261009.json](../validation/web-guide/integration-20261009.json)、[浏览器实测](../validation/web-guide/browser-20261009.json)和[包装核验](../validation/web-guide/package-20261009.json)。本地原始审阅证据保存在 `D:\AI4Science\ai4orgchem-runtime-deliveries\20261009-guide-v030-final-review`。

## 后续维护

以 `docs/index.html` 为唯一日常编辑入口。页面布局、交互、复制与下载逻辑均为完整自包含HTML/CSS/JS，后续可以由本地Codex直接维护。修改后同步重新导出的文案、README、来源、检查和迁移材料，保留旧ZIP及哈希，更新验证记录并作独立本地提交。导入目录中的原包和快照保留为历史材料，不各自修改成第二份活动网页。

页面的支持声明必须分别注明已实现、实测范围和未执行项目。普通分子RHF、固定研究任务与legacy条件Compute分别表述；来源身份登记不等于完整科学验收。镜像分发BLOCKED、WSLc BLOCKED、远端CI NOT_EXECUTED，以及检查点不支持恢复运行的限制继续保留。

包内网页权属和来源说明保留；网页材料未因保存到仓库自动扩大为Runtime源码许可。公开范围与实际托管按后续用户指令处理。本轮仅保存文档与验证记录，没有新增在线计算服务或修改科学代码。

## 2026-10-09：以计算模块名称为入口

活动网页的十四个模块已按实际计算操作命名。导航提示、标题、按钮说明及问答不再要求用户先理解专著编号。内部编号仍用于命令参数、任务键和来源路径；对应表放入“模块名称与内部协议编号（来源追溯）”折叠区，机器映射见 [module-names.json](runtime-guide/module-names.json)。

本轮只改变展示与维护材料。普通用户分子服务仍限定普通RHF单点；十四个模块采用固定案例或已有证据，没有扩大任意分子条件态、优化或尺寸扫描能力。高成本固定状态清单的接入与实际验收继续分别说明。

模块改名轮的实际网页导出当时保存在 [current/README.md](runtime-guide/current/README.md)，可携带包为 [模块名称修订ZIP](runtime-guide/archive/ai4orgchem-runtime-guide-v0.3.0-candidate-module-names.zip)。current是从唯一活动入口重新生成的维护快照，不作为第二个日常编辑入口；source及原ZIP是历史导入材料。

本次独立本地Edge检查通过三宽度默认／展开布局、十四名称与对应表、按功能名搜索、三路径与清除、79个复制目标、七项实际导出、ZIP CRC／10成员及根／模拟仓库子路径重开。复制内容仅允许Windows CRLF→LF归一化，计算命令及输入文本与导入版一致。禁JavaScript检查使用浏览器原生折叠操作读取全部名称；首次默认收起文本探针与后续检查均保留在记录中。真实200%缩放、完整键盘及多浏览器未执行，不宣称完整网页认证。

记录见 [模块修订身份与范围](../validation/web-guide/module-names-20261009.json)和[模块改名轮浏览器实测](../validation/web-guide/browser-module-names-20261009.json)。原导入测试属于历史字节版本，不冒充本轮记录。本轮未运行科学计算、Docker或WSL，也未推送或部署网站；来源和权属边界沿用原记录。

## 推送前验收记录口径修订

最终静态审查发现，原维护导出的“当前全部NOT_EXECUTED”会与已经保存的局部浏览器实测混淆。现已把YouMind原始维护文字明确标为历史；浏览器内手工QA初始未填写另列，包外实测按实际HTML SHA与范围登记。未把手工QA所有项自动改成PASS，真实200%缩放、完整键盘和多浏览器仍未执行。

当前活动入口仍为docs/index.html；[current维护导出](runtime-guide/current/README.md)现对应本轮字节，可携带[最终口径修订网页包](runtime-guide/archive/ai4orgchem-runtime-guide-v0.3.0-candidate-final-consistency.zip)。旧模块名称包、原YouMind包和原始导入快照均保留。此前记录中的current_export是历史导出位置；原字节可在对应归档ZIP及Git提交恢复，不用当前目录冒充旧哈希。

本轮三宽度默认／全展开、79逻辑复制目标、功能名搜索、三路径、七项导出CRC和HTTP根／子路径重开、真禁JS原生展开阅读通过；计算命令及水模板原字节不变。新身份与范围见[final-consistency-20261009.json](../validation/web-guide/final-consistency-20261009.json)和[本轮浏览器记录](../validation/web-guide/browser-final-consistency-20261009.json)。没有科学重算、镜像重建、WSL变更或公开动作，未分配新Runtime版本。

### 维护语义与两项下载出口补核

当前活动字节和current目录以[final-consistency-r2-20261009.json](../validation/web-guide/final-consistency-r2-20261009.json)为准，[本轮浏览器记录](../validation/web-guide/browser-final-consistency-r2-20261009.json)绑定新HTML。明确保留“仅描述当时状态，不是当前能力”的原意；guide与sources附加的交付说明同样标为历史，不再把原提供时未执行误写成当前全未执行。旧final-consistency记录／归档继续保留各自身份。最新[可携带网页包](runtime-guide/archive/ai4orgchem-runtime-guide-v0.3.0-candidate-final-consistency-r2.zip)另存，未更改原始输入或科学内容。

## 公开状态增补后的当前网页身份

本次仅同步已发生的源码公开与三项远端CI结果，Pages仍未启用。当前HTML、10成员导出与归档身份见[public-status-20261009.json](../validation/web-guide/public-status-20261009.json)，[局部浏览器记录](../validation/web-guide/browser-public-status-20261009.json)绑定新字节；三宽度、79复制、三路径、模块名搜索、七导出、HTTP根/模拟子路径和真禁JS阅读通过。全部计算命令与水模板未变，旧原包与r2归档继续保留各自哈希。[当前可携带网页包](runtime-guide/archive/ai4orgchem-runtime-guide-public-status-20261009.zip)只是指南；200%/全键盘/多浏览器仍未执行，未分配新Runtime版本。
