# 普通WSL2原生Runtime路径的只读可行性核查


本轮新增QM、SCF、积分、优化、科学预算均0；不导入科研脚本或任何科学库，不安装/升级/修改环境，不修改原项目/冻结worker/profile，不关闭任何WSL发行版，不改全局内存上限。原`ai4orgchem`环境仅查询标准库包元数据，使用`-I -B`确认isolated=1、no_user_site=1、不写bytecode。

## 实机只读结果

`wsl --list --verbose`最初：Ubuntu-24.04和Ubuntu均Stopped，docker-desktop Running。为执行获准的只读查询，Ubuntu-24.04正常启动为Running；Ubuntu仍Stopped，docker-desktop仍Running。本轮没有shutdown；这次状态变化已完整记录，不能说“发行版状态完全未变”。

| 项目 | 实际观察 |
|---|---|
| 发行版 | Ubuntu-24.04，WSL2；现有WSL2.3.26/内核5.15.167.4-1 |
| 原科学解释器 | `/home/cascade/micromamba/envs/ai4orgchem/bin/python`确实存在 |
| Python | 3.12.13（conda-forge） |
| PySCF/NumPy/SciPy | 2.14.0 / 2.5.1 / 1.18.0 |
| geomeTRIC | 1.1.1 |
| PyYAML/RDKit/networkx/six | 6.0.3 / 2026.3.4 / 3.6.1 / 1.17.0 |
| jsonschema | 4.26.0 |
| Pillow | 12.3.0；旧Docker锁为11.3.0 |
| 用户/进程 | UID/GID1000；PID1为systemd；22逻辑CPU；cgroup v1 |
| 当时内存 | MemTotal16,565,334,016字节≈15.43GiB；MemAvailable15,415,652,352字节≈14.36GiB；swap4GiB |
| 现有工具 | systemd-run/systemctl/prlimit/unshare/timeout/taskset/flock/setsid可找到；bwrap不在PATH |
| 原scratch | `/home/cascade/ai4orgchem-scratch`存在，仅查询，未写入 |

所有冻结Docker包锁的版本逐项核对，仅Pillow版本不同；但版本相同不证明wheel/conda构建、BLAS/libc/libxc/编译选项或库字节相同。元数据查询也不证明科学包可成功导入或执行。必须建立新的原生依赖/环境身份，不能填写旧Docker完整dependency SHA或image ID。其他已有环境只列名字，未执行或改动base、cascade-qc-linux等受保护环境。

原项目`AGENTS.md`规定Ubuntu-24.04及上述专用环境、`PYTHONNOUSERSITE=1`、默认8线程/单中高成本任务；`configs/resources/local_wsl.yaml`有客体15GiB、swap4GiB、可用低于4GiB停止、scratch20GiB和宿主盘至少80GiB等历史原生规则。它们作为设计参照保留，不被Docker14/15/16GiB合同覆盖，也不被本轮自动重写。

## 冻结worker不能不经适配直接执行

现有`runtime.high_cost_cases.__main__`和宿主Docker启动器分别硬核验：

1. `/output`必须全新，`/opt/runtime`、`/opt/venv`、`/task-contract.json`、`/inputs`须OS只读挂载；原生路径没有这些容器布局。
2. UID/GID必须10001、接口仅lo、cgroup memory/swap/cpu精确匹配容器合同。现UID1000仍是非root，不能冒充10001；swap可见4GiB不等于任务实际额外swap=0。
3. 输入前序及输出回执绑定同一个Dockerimage ID/完整依赖/profile SHA，镜像构建环境变量也作身份核验；原生环境没有这些镜像事实。
4. 原生启动器要记录整个进程树的结束、硬墙时、峰值和后续输出，而不是Docker container removed回执。

因此可复用冻结科学`p11/p12`适配器、源文件捕获、规则、门槛、HighCostGuard和一次预算语义；平台worker必须是单独后端入口/契约。不能删除上述检查后沿用原Docker“PASS”标签，也不能修改冻结worker让它接受任何平台。

## 最小原生启动器设计

- 增加独立 `backend_id=wsl2-native-v1`，原Docker入口不动。Windows端解析明确发行版、环境解释器、独立源快照/输入/output/scratch和新native依赖锁，不使用原项目可写目录执行，不install到原环境。
- 科学源来自冻结捕获的只读副本，原解释器/科学库可作为候选只读挂载复用。隔离需验证user/mount/network namespace或等效机制；仅`chmod`或约定不写不足以复用Docker只读声明。当前bwrap缺失，unshare是否允许所需namespace及只读bind mount尚未测试；不自动安装bwrap或sudo改系统设置。
- 采用原生单任务OS锁，覆盖新增backend与现有Runtime任务；与原项目非Runtime任务的互斥范围如实说明，不能假称全主机已经统一受控。默认8线程；freeze线程/CPU资源身份并核验实际库线程。
- 使用独立native资源profile，按尺寸/状态/direct路径定容量，记录WSL MemAvailable、Windows可用及宿主盘。**不要求照搬Dockerguest≥15GiB**，也不自动配置18GiB。启发式档位仍须实测；旧库`max_memory=12000`与低cap衔接未实施。
- CPU/cgroup内存/零任务swap/进程数硬限制优先使用可证明的systemd scope或对应OS资源控制；cgroup v1用户委托与属性支持尚未核验。`prlimit`的RLIMIT_RSS在Linux不能当可靠硬RSS限额，RLIMIT_AS也不是实际RAM峰值，不以二者伪装等价保证。原项目4GiB可用停止规则不能冒充已验证native候选模型。
- 时间以宿主/监督器monotonic硬期限为准，setsid进程组配合有限SIGTERM宽限和SIGKILL；只回收本任务所有权进程，不`wsl --shutdown`。停止/失败收费，未知结束保持预留，检查点不恢复、不自动重试。
- 回执明确native来源、环境fingerprint、实际UID/权限、网络、cgroup/线程、输出大小/SHA、进程树结束、资源/预算。使用`image_id=null`或新明确environment_id字段，不能把Docker ID冒充实际执行身份。
- 原已PASS苯G和N12-G不重算。若将Docker G作为native GL/GE前序，须在新backend合同中明确原G完整来源与跨backend兼容依据；旧`validate_inputs`要求同image/dependency，不能静默绕过。保留每态真实环境，完整组装需要兼容身份策略，不能强行说全部来自同镜像。

## 可执行的零QM验收顺序

1. 已完成本页发行版/解释器/元数据/路径观察。下一步在全新外部测试目录做native源码/依赖快照、路径/中文/空格及原工作区保护核验；不运行科学脚本。
2. 用标准库替身验证namespace与只读绑定：试写源码/env/输入应拒绝，output/scratch可写，网络接口及外连拒绝真实观察。没有隔离权限时返回具体BLOCKED，不改系统配置。
3. 在独立小scope/进程组执行标准库内存/CPU替身，实测cgroup内存、任务swap、CPU线程和OOM/拒绝；这一测试需要单独明确瞬时资源合同。工具存在不等于属性控制已通过。
4. 给替身注入退出37、合作停止和不合作强杀，核对原退出码、子进程全部结束、日志/输出保留、最终清单封存和不删除他人进程。
5. 使用工程替身验证source/profile/native环境/前序绑定不匹配、预算重复/不足/未知、旧结果复用与resume均拒绝；容量充足也不自动批准未验证科学profile。
6. 只有新worker的隔离、资源、预算、保存等工程测试完成后，另立一份尚未执行态的具体新科学验收范围/预算。普通WSL2可能适合原模型，但当前没有native Runtime科学执行记录，不赋予新的科学资格。


实际命令、原字节stdout/stderr、启动状态和包元数据见 `native-wsl2-readiness.json`、`complete-dependencies.json`。查询不输出环境变量、令牌或秘密。
