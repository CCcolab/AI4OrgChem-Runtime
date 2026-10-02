# L3 固定几何复算准备

2026-10-02：用户首次 evidence 与两次 p14-smoke 均 PASS。下一步准备 p14-fixed；本文件不代表 L3 已执行或已支持。WSL 升级和 WSLc 实机验收继续暂缓，原项目文件及环境保留。

## 资源核查

现有候选镜像内只读探针返回有效可用内存 15397363712 字节（约 14684 MiB），cgroup unlimited，errors=[]；CPU affinity 22。D 盘剩余 250927624192 字节（约 233.7 GiB）。这是瞬时值，不保证实际启动时仍满足条件。

L3 启动门槛为有效可用内存至少 13000 MiB，目前约有 1684 MiB 余量；门槛通过不保证整个计算不发生 OOM。避免并发科学计算，运行时保留内存预检与共享锁，不改变全局 WSL 配置或降低阈值。CPU 默认 8 线程。实际耗时与临时磁盘峰值尚未知，不能用 L2 耗时外推；启动前需明确可接受的连续运行窗口及中止预算。

## 输入与运行

使用已验收镜像 ai4orgchem-runtime:oci-candidate-20261002，其代码提交 f30b2906794d14f9030daab779c0d6a7cd4bd6f7、固定科学源码提交 28511f3d84fa65707a107cde1e8121a7b4334ecb。镜像中封存的协议、积分类别和来源几何由上游脚本读取，不新增或拟合参数。

仅在明确授权计算预算后，从 PowerShell 7.3+ 执行以下命令；每次生成唯一目录：

```powershell
cd D:\AI4Science\ai4orgchem-runtime
./scripts/run-wslc.ps1 -Engine docker -Task p14-fixed -Image ai4orgchem-runtime:oci-candidate-20261002 -Threads 8 -OutputRoot 'D:\AI4Science\ai4orgchem-runtime-runs\L3固定几何复算'
```

不启动 L4，不使用原项目开发目录作为输入或输出，不清理历史文件。已有启动器无需运行时联网，但未显式禁用网络；若要求严格断网，执行前应使用 --network none 的受控命令或完善启动器后复验，不把原生启动器描述为网络隔离已开启。

## 验收与科学解释

1. 记录实际镜像身份、科学/runtime 提交、输入和输出哈希、依赖版本、线程、有效内存、耗时、峰值 RSS 与原退出码。
2. run-manifest.json 为 PASS 且退出码 0，result.json 的 anchor_gate_verdict 为 PASS；全部 12 项上游 acceptance_checks 为 true。
3. 资格包括三个状态收敛、78 电子、单张量模式、能量分量闭合（1e-9 Eh）、交换子（1e-5）、幂等性（1e-7）和端点为正；电子数容差为 1e-7。完整规则以固定源码为准，不更改容差。
4. 单独报告 fixed_geometry_endpoint_kcal_mol、G/PLG 能量残差及 fixed_endpoint_residual_kcal_mol。上游 anchor PASS 不包含“与文献端点残差足够小”的判据，不能把 PASS 宣称为文献定量重现或最终科学分类。
5. 检查 result.json、report.md、checkpoint.json 与日志持久保留，复核 manifest 输出哈希。失败时记录 OOM、预检拒绝、SCF 不收敛或门禁失败等实际原因，不修改科学规则、冻结值或容差。

完成后更新验证报告与 OCI 支持矩阵，仅将实际完成的 L3 检查改为 PASS/FAIL。L4 和完整新四输入分类继续 NOT_EXECUTED。L4 可保存检查点，但不支持恢复运行；L3 检查点同样不得被假定为恢复接口。
