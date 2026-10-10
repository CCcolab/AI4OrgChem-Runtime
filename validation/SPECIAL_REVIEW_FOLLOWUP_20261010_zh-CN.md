# 70ad3d6 专项复审的剩余修订

审阅基准为 `70ad3d64aed263ac34329cfb0ee1ac3063ebbe21`。本轮只修订当前导航、声明元数据及网页导出，不改变科学源码、来源锁、计算定义或数值阈值；不运行分子计算、重建本地镜像或升级环境。

## 当前入口与记录

- 中英文 README 的通用结果入口改为当前专业服务矩阵、各模块指南的结果段及 `docs/templates/CURRENT_SERVICE_REVIEW_zh-CN.md`。旧 P14 解释不再作为所有服务的通用入口。
- 普通分子操作明确使用 `run-installed-runtime.py` 与本家族 installation record；四个旧候选分子结果及同库对照仅作为原候选验收，不能转移到新安装。
- 能力 CLI 从登记记录读取 CI 成功 job 数和 scope；登记仍保留 be51dcbb 的两个 job 身份，不将该旧运行认证为本轮修订。
- P14.source 明确绑定独立 Dockerfile、fetch-source.py 和 source.lock.json 的冻结提交归档；adapter_files 为 0，不再挂入四家安装增补来源。四家来源权威和旧科学字节保持。
- 当前网页包的说明指向本轮字节记录，此前 full-review-repairs、online-browser-followup-fa7b4ee、export-compatibility-round2 分别保留原身份，不验证本轮新产物。
- 最小数值见证的表格标为 NumPy 2.4.6 历史观察，链接的最新公共审计使用 2.5.1；未重做数值审计。

## 动态导出修订与实测

原第三方浏览器记录在 EXPORT_SOURCE 已通过，EXPORT_SERIALIZED 报 HEAD_PREFIX_MISMATCH；其原冻结 root 中是否含额外 DIV 未经证明。本轮不将这一假设描述为已确定的原环境根因。

导出现在要求捕获 root 有唯一的直接 HEAD、BODY，使用捕获中已经校验的 head/body 组装只含它们的 root，根属性只保留自有 lang。根层工具节点和属性不装入下载。charset、viewport、title、完整 style 的唯一性、内容比对、组装后复核和精确序列化前缀守卫均保留；缺失 head 不补造。诊断增加捕获根节点摘要及序列化失败的 head offset、预期长度和首差异位置，不收集分子数据。

Codex 本机 in-app browser 的 localhost 受限实测：

| 场景 | 实际结果 |
|---|---|
| 干净页面 | HTML、ZIP、包外交付清单均取得实际文件；CRC、10成员大小和 SHA-256 全匹配 |
| 冻结捕获前插入无标记根 DIV 及 cursor 属性 | 同样三个产物成功；导出 HTML 和 ZIP 与干净场景逐字节一致 |
| 旧 70ad3d6 算法加入同一受控插入 | 实际拒绝，重现 HEAD_PREFIX_MISMATCH；仅为机制复现，不冒充原云浏览器 |
| 捕获前删除自有 style | 拒绝 EXPORT_SOURCE_CAPTURE:INCOMPLETE |
| 捕获前重复自有 title | 拒绝 EXPORT_SOURCE_CAPTURE:INCOMPLETE |

82份带 ID 的命令／模板正文与 70ad3d6 完全一致；水 request／XYZ 原字节保留。当前静态 HTML、ZIP 和维护副本由实际按钮下载产物核对后更新，不用手工构造包冒充浏览器下载。

定向本地工程回归 22 项通过，包含 CI 计数从绑定记录读取的合成记录反例，以及既有来源、预算、隔离锁和计数回归。首轮沙箱临时目录权限失败已保留；在正常本机权限重跑通过。根 Runtime tests 继续仅在本地，不加入公开树。

机器证据及本轮实物身份见 [special-review-followup-20261010.json](web-guide/special-review-followup-20261010.json)。历史失败和本机 Chrome／Edge 成功记录原字节保留。

## 未闭合范围

**原第三方云浏览器尚未重测本轮新页面。** 其 70ad3d6 三按钮失败保持失败；本地机制修复与实物通过不能改写那个结论。下一次专项复核仅需在原环境重试三个动态按钮并核对新产物身份，静态备用下载继续保留。全键盘及真实200%缩放没有新增验收。

条件态 Compute 仍 BLOCKED，完整 canonical／虚轨道门禁仍 NOT_IMPLEMENTED，波函数稳定性未执行；高成本两个旧先导不认证其他76态或新安装科学重放；镜像分发仍受限制。本轮不新增科学资格、不恢复暂停平台、不公开预构建镜像、不打版本标签或 Release。L4检查点不支持恢复运行。
