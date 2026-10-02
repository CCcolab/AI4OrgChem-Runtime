# v0.1.0 候选发布材料（未发布）

建议标题：AI4OrgChem Reproducible Runtime v0.1.0。

当前发布就绪状态：BLOCKED。本地 OCI 候选已构建且本轮验收 PASS，WSLc 未验收，不能把下述候选定位当作已实现的公开承诺。

候选说明：固定 AI4OrgChem v0.3.2 / 28511f3d84fa65707a107cde1e8121a7b4334ecb，提供 CPU 分层任务封装、依赖与归档哈希锁、资源预检、持久日志/检查点和身份 manifest。已在独立 WSL2 候选环境验证 L0—L2 与 STO-3G 等价性；Docker OCI 的 L0—L2/等价性、非 root/只读/离线、退出码/低内存拒绝与输出保留已通过；WSLc 兼容性待实际执行。L4 可保存检查点，但不支持恢复运行。高级入口未开放为已验证支持，不新增科学判定或认证。

已有本地构建日志、镜像身份和源码/runtime 映射见 oci-summary.json。发布前补齐：完整基础/依赖组件许可清单、WSLc 实际运行和对照报告、WSLc 挂载/退出码/低内存/停止/路径验收及矩阵一致性检查。仅有 Docker 测试不认定 WSLc。

GHCR 候选地址 `ghcr.io/cccolab/ai4orgchem-runtime` 尚未创建/核对可见性；不称已存在。取得一次明确发布授权、具备相应账户权限且验收合格后，在目标主机为已验证本地镜像加候选 tag，使用专用账户凭据通过 `docker login ghcr.io` 安全登录，再 `docker push`，记录 registry digest。不得把令牌写入日志、Git 或脚本；不要在不可信 PR 上使用凭据或自托管 runner。本仓库 CI 仅构建/测试，permissions contents:read，无 push 权限。

正式标签/Release 由授权发布流程执行；本轮不创建。发布附件建议为验证摘要 JSON、镜像/源码映射与 SHA-256 清单，原始大日志/密度/检查点另行归档并给出身份，不直接放入源码 Git。
