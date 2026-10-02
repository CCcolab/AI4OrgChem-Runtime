# CI 静态审查

状态：**静态审查完成，运行 NOT_EXECUTED**。本机仓库无 remote，未调用 GitHub workflow、未推送代码，也没有真实 run URL/日志。配置或本地解析通过不能记为 CI PASS。

对象：.github/workflows/validate.yml。

| 审查项 | 静态结果 |
|---|---|
| 触发 | push、pull_request、workflow_dispatch；无 pull_request_target 或发布触发 |
| 权限 | contents:read；无 packages:write、contents:write、id-token:write |
| runner | ubuntu-24.04 托管 runner；20 分钟超时，无自托管 runner |
| checkout | 固定完整 SHA，persist-credentials:false；没有显式 secrets 注入 |
| 构建 | 固定 base/source/wheel 锁，RUNTIME_COMMIT=$GITHUB_SHA；只生成本地 ci tag，需要下载网络 |
| 测试范围 | wrapper 单元/过程测试、L0、L1、非 root/只读/持久探针；不执行 L2/L3/L4 或联合科学分类，不执行 WSLc |
| 运行网络 | wrapper/L0/L1/平台探针显式 --network none |
| 宿主变更 | 仅托管 runner 临时输出目录 chown；不修改用户本机 WSL/全局配置 |
| 镜像身份 | L0/L1 按实际 inspect ID 运行并注入 ID，保存 inspect JSON；无法获取 registry digest 时仍 UNKNOWN，不伪造 registry 身份 |
| 失败传播 | set -euo pipefail 保留 docker/tee 失败状态，无 continue-on-error |
| 日志 | build/wrapper 日志及运行目录以 always() artifact 保存，保留 7 天；无镜像 push、docker login、Release、Git tag 或 deploy |
| artifact | Actions 内部运行证据保存，不等于正式 Release；可能随仓库可见性被读取，不上传环境变量/凭证 |

修正了 wrapper 未显式断网、失败后原始运行文件未归档、CI manifest 镜像 ID 未注入三项。新增 actions/upload-artifact 固定 SHA `ea165f8d65b6e75b540449e92b4886f43607fa02`，通过官方仓库 `git ls-remote ... refs/tags/v4.6.2` 核对。既有 checkout 固定 SHA 不在本轮更新。

未知/限制：托管 runner 实際 Docker/网络/包下载条件未执行；artifact 上传权限与可见性需真实 run 核查；完整 action 实现及传递依赖未做供应链安全认证。未来若扩展自托管 runner 或 secrets，须重新审查，不能在不可信 PR 使用科研主机凭证。
