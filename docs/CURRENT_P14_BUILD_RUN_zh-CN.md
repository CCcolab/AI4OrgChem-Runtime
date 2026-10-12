# P14 条件能量与结构响应：独立安装和运行

本模块复核固定C12H6、平面D3h五参数source-proxy的普通／条件能量与结构响应，不接收自己的XYZ。它**不属于四家register-installation服务**：使用冻结588份科学来源、独立Dockerfile和镜像，不用四家的installation-record，不把共用服务镜像传给原七任务。

## 1. 准备独立的干净源码与工具

可使用已有干净Git源码目录；以下首次示例采用独立目录避免与四家安装运行目录混淆。需要Git、已有PowerShell7.3+、Docker Linux/amd64及构建时的公开来源／PyPI／基础镜像网络；不要在Windows PowerShell5.1直接执行要求7.3的脚本，不自动升级或安装系统功能。

```powershell
git clone --branch main https://github.com/CCcolab/AI4OrgChem-Runtime.git D:\chem-work\runtime-p14-source
Set-Location 'D:\chem-work\runtime-p14-source'
git rev-parse HEAD
$PSVersionTable.PSVersion
.\scripts\build-docker.ps1 -CheckOnly
```

CheckOnly只验证来源和构建身份，不访问引擎、不构建镜像，不代表科学通过。本流程示例使用Git检出；四家专用安装ZIP的身份证明与这里的来源快照合同不混用。

## 2. 构建一次，记录实际镜像身份

```powershell
.\scripts\build-docker.ps1 -Tag ai4orgchem-runtime:p14-local
```

container/Dockerfile从固定公开Python基础镜像下载／核对588份来源与依赖；不是旧私有镜像分发。构建要求干净、已提交来源，成功后保留 `.build/image-inspect.json`。已有本模块合格镜像时不重复构建；新构建镜像不继承旧科学PASS。

## 3. 先做证据和核心检查

为本批任务使用同一个外部输出根与共享锁根；启动器在其中为每项创建唯一新运行子目录，不覆盖历史：

```powershell
.\scripts\run-docker.ps1 -Task evidence -Image ai4orgchem-runtime:p14-local -OutputRoot D:\chem-work\p14-runs-new -LockRoot D:\chem-work\p14-locks-new
.\scripts\run-docker.ps1 -Task core-tests -Image ai4orgchem-runtime:p14-local -OutputRoot D:\chem-work\p14-runs-new -LockRoot D:\chem-work\p14-locks-new
```

evidence是冻结字节核查，core-tests是科学核心测试，不是用户分子能量计算。检查失败时保留日志，停止后续科学解释。

## 4. 选择技术对照或生产任务

| 真实-Task | 用途 | 主要边界 |
| --- | --- | --- |
| p14-smoke | 技术试跑 | STO-3G，不作生产科学定判 |
| p14-equivalence | 实现对照 | STO-3G限定等价性 |
| p14-fixed | 固定几何能量账本 | B3LYPG/6-31G(d)、grid3、固定条件规则 |
| p14-optimize | G／PLG约束优化和结构响应 | 五参数范围，非通用用户优化 |
| p14-classify | 四父结果联合判读 | 必须有兼容完整的四个本次运行 |

各任务单独选择执行，不将高成本任务当作首次安装测试自动启动。以下仅示例技术试跑的参数形式：

```powershell
.\scripts\run-docker.ps1 -Task p14-smoke -Image ai4orgchem-runtime:p14-local -Threads 8 -OutputRoot D:\chem-work\p14-runs-new -LockRoot D:\chem-work\p14-locks-new
```

选择其他真实Task时保持同一镜像、输出根和锁根。高级L3内存门槛13000MiB，L4为13GiB，按有效可用内存核查；默认8线程不是硬CPU配额。54.37秒／21.20分钟是旧单次实测，不是用户耗时保证。计划生产计算前核对[完整运行合同](RUN_zh-CN.md)及[服务矩阵](CURRENT_PROFESSIONAL_SERVICES_zh-CN.md)，保留资源／前序／科学门槛，不改容差。历史L3/L4严格断网验收未执行。

## 5. 四个父任务齐全后才能分类

从本次输出根下选择实际smoke、equivalence、fixed、optimization运行子目录。下面的大写目录名必须替换，不是可直接运行的路径；四父目录必须位于同一OutputRoot内：

```powershell
.\scripts\run-docker.ps1 -Task p14-classify -Image ai4orgchem-runtime:p14-local `
  -OutputRoot D:\chem-work\p14-runs-new -LockRoot D:\chem-work\p14-locks-new `
  -SmokeRun D:\chem-work\p14-runs-new\ACTUAL_SMOKE_RUN `
  -EquivalenceRun D:\chem-work\p14-runs-new\ACTUAL_EQUIVALENCE_RUN `
  -SourceLevelRun D:\chem-work\p14-runs-new\ACTUAL_FIXED_RUN `
  -OptimizationRun D:\chem-work\p14-runs-new\ACTUAL_OPTIMIZATION_RUN
```

不能传缺manifest的冻结JSON，不能拼不兼容来源／依赖／输入的历史结果补缺。分类不是新SCF，也不替代四父资格。

## 6. 保存结果并分层判读

每个实际运行目录保留run-manifest.json、stdout/stderr、适用的result.json/report.md和checkpoint.json。核对数值门槛、退出码、输出哈希、源／镜像／依赖身份；有文件或子程序退出0不自动等于PASS。科学门槛FAIL、UNKNOWN或缺失时当前Runtime返回4，历史镜像旧行为不倒写。

按[结果判读](REVIEW_RESULTS_zh-CN.public.md)和[四父模板](templates/REVIEW_REPORT_zh-CN.public.md)分别列执行、数值、比较和分类。固定协议分类不推广为任意分子或全部芳香性结论。L4可保存检查点，**不支持恢复运行**。原P01—P14不因新增用户入口失败自动重审。本文修订未执行构建／计算，不修改原规则或门槛。
