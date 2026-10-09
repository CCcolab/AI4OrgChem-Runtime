# 本地服务工程CI增补（2026-10-09）

已新增 `local-service-contracts` 工作流任务，覆盖首批登记任务、第二/第三批工程合同、普通分子服务与原生WSL2 Check。旧Linux和用户分子合同任务保留，权限为 `contents: read`，Actions固定完整提交，不推送镜像、创建标签或Release。**GitHub Actions运行仍NOT_EXECUTED。** 静态审查和本地执行分别记录。

入口为 [ci-unit-local-services.py](../scripts/ci-unit-local-services.py)，依赖 [精确CI子集锁](../locks/requirements-local-services-ci.txt) 来自既有Linux来源锁。该任务不安装PySCF，主动阻止真实PySCF导入、禁止高成本科学测试opt-in；测试使用数组、模拟、临时夹具和源码合同。原生WSL2测试模拟命令响应，不启动WSL。

## 实际本地执行

使用现存 `sha256:18dcd1da2e634cf6ab8d49a7281ca853c0a393e140ac95c6ec00448a3fc934bc`，构建提交仍为 `05308a1872d769aaa85e39adbafe7020e36358e6`。本轮当前工作区只读挂载到 `/candidate`，不是把后续源码冒充已烘焙进旧镜像。容器内另建仅9项锁定依赖的临时venv，离线从镜像已有wheel取得；未修改原镜像或WSL科研环境。

新记录目录：`D:\AI4Science\ai4orgchem-runtime-deliveries\20261009-six-issue-remediation\ci-installation`。

| 轮次 | 结果 | 处置 |
| --- | --- | --- |
| 首轮 | FAIL：临时文件系统执行权限阻止NumPy扩展映射 | 保留日志；仅修正测试用tmpfs权限 |
| attempt-02 | 440执行，434通过，1跳过，5错误 | CI子集遗漏SciPy；补入既有确切版本/哈希，不改科学代码 |
| attempt-03 | **440执行，439通过，1跳过，0失败/错误** | 最终本地轻量工程CI通过，自有容器已删除 |

| 工程组 | 独立用例数 |
| --- | ---: |
| 固定登记P01/P02/P13任务 | 96 |
| 第二批P03—P10 | 115 |
| 第三批P11/P12 | 119 |
| 普通分子服务 | 97 |
| 原生WSL2 Check | 13 |

唯一跳过项为P11真实分子预检，需要科学容器显式opt-in，本轮保持关闭。跳过不标PASS；已保存的78态真实零QM预检属于此前独立记录。本轮不执行SCF、F/NR、优化，不复算P12，不新增P12内存准入。

运行限额为512MiB、1CPU、禁止网络、只读root/source、非root、仅新输出目录写入；这些是工程CI限额，不是科学任务资源校准或新的P12最低内存。

## 准确的支持边界

此组通过不等于远端CI、全部旧工程测试、完整科学验收、异机安装、WSLc或原生Compute通过。既有更大工程组保留各自记录。后续首次推送会触发工作流及运行证据上传，应纳入源码公开范围确认；本轮未推送、发布、重建镜像或改变旧科学锁。
