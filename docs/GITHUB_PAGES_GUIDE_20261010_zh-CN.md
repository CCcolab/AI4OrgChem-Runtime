# 直接打开 Runtime 用户指南

可直接在浏览器打开：[AI4OrgChem Runtime 用户指南](https://cccolab.github.io/AI4OrgChem-Runtime/)。无需先下载源码、查看 `index.html` 代码，也无需启动 Docker 或 WSL。网页提供阅读、搜索、按研究目标导航、复制命令和下载指南；复制的计算命令仍在用户本地 Runtime 执行，不提供在线计算。

## 打开方式

1. 点击上方指南网址；也可从仓库 README 顶部的“在线使用指南”入口进入。
2. 根据目标选择“计算自己的分子”“学习与复算示例”或“查阅已有证据”。
3. 需要真正计算时，按对应模块准备本地输入与环境；网页本身不调用计算引擎。

仓库的 `docs/index.html` 页面用于查看或维护源码；GitHub Pages 地址用于实际浏览网页。下载整份网页包后，也可在本地解压并双击包内的 `docs/index.html`。网页 ZIP 只是指南，不是完整 Runtime 安装环境。

## 托管来源与验证范围

2026-10-10按用户要求启用 GitHub Pages，发布源为公开仓库的 `main` / `docs`，使用既有 `.nojekyll` 与 HTTPS，没有新增自定义域名或在线服务。整个已公开 docs（包括文档和网页归档）随分支托管；后续修改并推送此目录会更新网站。[GitHub 官方说明](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)解释了分支与 /docs 发布方式。

首次部署 [pages build and deployment 37998298990](https://github.com/CCcolab/AI4OrgChem-Runtime/actions/runs/37998298990) 成功，绑定 `99a52b8a992260cc7ee3e88f699da5454ffb87af`；真实 HTTPS 根地址返回 200、`text/html`，页面 SHA-256 为 `2d36e3af14108defeab5c1f58cdb746569a13bcdec26d50d0f92c1815ff59659`，与当时仓库 HTML 逐字一致。

本次仅更新托管状态、源码入口和 README 直达链接。增补网页的本地局部检查通过三宽度默认／展开、79 个逻辑复制、三条阅读路径、模块名称搜索、七项维护下载、10 成员 ZIP CRC、HTTP 根／模拟项目路径重开及真禁 JavaScript 阅读；所有计算代码块、复制目标和水输入模板未变。[身份与首轮部署记录](../validation/web-guide/pages-deployment-20261010.json)区分首轮线上字节与增补后的新 HTML，[局部浏览器记录](../validation/web-guide/browser-pages-state-20261010.json)绑定新字节。新源提交的真实线上身份必须按自己的部署另核对，不能继承首轮的 HTTP 哈希；原包和全部旧归档保留。

本地原始部署响应、HTTPS 页面、浏览器证据与后续线上核对保存于 `D:\AI4Science\ai4orgchem-runtime-deliveries\20261010-pages-deployment`。完整 200% 缩放、全键盘、多浏览器并未执行，本轮不宣称完整网页平台认证。

## 项目边界继续保留

本次是静态使用指南上线。GitHub 管理 Pages 部署，不改变现有三个 Runtime CI job 的构建／验证范围；Runtime CI 不推镜像、不创建标签或 Release。WSLc 暂停并保持 BLOCKED / NOT_EXECUTED；镜像分发 BLOCKED_LOCAL_ONLY；旧用户分子条件态 Compute BLOCKED；普通用户 RHF 单点保持原已验收的分子、方法与规模边界。L4 可以保存检查点，但不支持恢复运行。

没有升级 WSL、启动本地 Docker、改全局配置、重算科学任务或部署在线计算。没有确定新 Runtime 版本、创建标签、发布 Release 或镜像。YouMind 原始包、第三方许可与 NOTICE 边界不随托管改变。十一份 Skill 导出继续按用户决定延后。
