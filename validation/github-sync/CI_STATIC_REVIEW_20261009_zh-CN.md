# 首次 GitHub 同步的 CI 静态审查

2026-10-09，审查对象为 `.github/workflows/validate.yml`、`container/Dockerfile`、`runtime/cli.py`、两项工程 runner 的范围定义。结论为**静态审查完成，远端运行 NOT_EXECUTED**，没有在本轮构建镜像或运行测试。

| Job | 首次 push 的配置行为 | 不可据此声称 |
| --- | --- | --- |
| linux，20分钟上限 | 从固定公开Python/Debian基础镜像、冻结科学来源及hashlocked wheels构建本地`:ci`镜像；3组wrapper unittest；L0 evidence运行4项保存证据验证脚本，L1 core-tests运行3份P09条件SCF／能量组装／ERI规则测试；permissions/persistence探针 | 构建离线、L2—L4通过、用户分子Compute通过或所有科学任务认证 |
| user-molecule-contracts，5分钟上限 | CPython3.12、venv、hashlocked最小二进制依赖；严格输入/资源/记录合同；来源、分布与历史材料工程测试 | 数组／科学adapter、Docker／PowerShell及W07本地场景完整验收 |
| local-service-contracts，10分钟上限 | CPython3.12、venv、hashlocked依赖；固定案例、常规／高成本接口、普通分子及WSL2 Check的工程mocks/arrays；runner阻止真实PySCF导入且拒绝科学opt-in | 新镜像高成本重放、真实SCF／优化或原生WSL2 Compute支持 |

push、pull_request和workflow_dispatch均触发；未筛选分支／路径，push与PR可能各产生一次运行。35分钟只是三项job超时之和，不是时长或费用承诺。允许网络用于构建和依赖安装；`--network none`仅覆盖配置中指定的运行容器。实际远端效果尚未执行，不把runner注释当作实测证明。

三项job无论成功失败均尝试上传各自RUNNER_TEMP证据目录，保留7天。日志、环境／版本、镜像检查信息、测试fixture路径及失败输出属于需确认的公开范围；没有真实产物就不能完成产物内容验收。工作流未声明读取用户私人分子或本地交付目录；不以此保证未来改动永不产生敏感信息。

全局权限`contents:read`，checkout禁用凭据持久化，checkout/upload-artifact固定SHA。没有registry push、Git标签创建、Release、Pages部署或write权限；镜像的本地`:ci`标签不等于公开镜像分发。不存在Pages工作流，首次源码推送不自动使网站上线。

保留原配置，本轮不新增自动发布。推送后应核对3项job实际结果和附件，失败时保留原因，不降低科学阈值，也不将远端未覆盖组标为PASS。Pages启用和网站HTTP复核单独执行。
