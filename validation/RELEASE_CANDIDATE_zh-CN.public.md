> 当前公开阅读节选。原始历史材料已按原字节保存在本地归档；本文件不是原件，不能用于原始哈希验收，也不把旧验收转移至当前代码。
> 原件 Git 提交：eb65b4586c83637569f6359814338c1292948861；SHA-256：d229476864659e3b025ff246bd1c03ac4adff0249c476e8bae07cc41c9fcef09。

# v0.1.0 候选发布材料（未发布）


建议标题：AI4OrgChem Reproducible Runtime v0.1.0。




GHCR 候选地址 `ghcr.io/cccolab/ai4orgchem-runtime` 尚未创建/核对可见性；不称已存在。取得一次明确发布授权、具备相应账户权限且验收合格后，在目标主机为已验证本地镜像加候选 tag，使用专用账户凭据通过 `docker login ghcr.io` 安全登录，再 `docker push`，记录 registry digest。不得把令牌写入日志、Git 或脚本；不要在不可信 PR 上使用凭据或自托管 runner。本仓库 CI 仅构建/测试，permissions contents:read，无 push 权限。

正式标签/Release 由授权发布流程执行；本轮不创建。发布附件建议为验证摘要 JSON、镜像/源码映射与 SHA-256 清单，原始大日志/密度/检查点另行归档并给出身份，不直接放入源码 Git。
