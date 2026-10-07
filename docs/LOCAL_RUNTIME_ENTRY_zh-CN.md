# 本地 Runtime 使用入口

2026-10-07。网页仅提供使用指南；操作在本机进行。当前为本地工程候选，生产用户分子 Compute 仍 BLOCKED。本页对应宿主源码入口，新功能没有重建进旧 Docker 镜像。

## 从一个目标开始

在 runtime 仓库根目录打开 PowerShell。以下入口兼容 Windows PowerShell 5.1，选定文件阅读使用已有 Python 3.12+；Check/Report 复用已有 PowerShell 7.3+ 服务启动器。找不到工具时给出现有可执行文件路径，不自动安装。

1. 查看当前可用功能及限制：

```powershell
./scripts/start-local-runtime.ps1 -Action Capabilities
```

2. 列出 P01—P14，选一个感兴趣的命题：

```powershell
./scripts/start-local-runtime.ps1 -Action List
./scripts/start-local-runtime.ps1 -Action Show -Proposition P01
```

第二条没有给出来源目录时，会显示缺失来源并返回20。它仍提供协议、证据路径和状态说明，不下载科学源码。

3. 阅读已有冻结证据，指定自己实际持有的科学源码目录及全新报告目录：

```powershell
$scienceSource='D:\your-work\science-v0.3.2'
$reviewOutput='D:\your-work\reviews\p01-new'
./scripts/start-local-runtime.ps1 -Action Review -Proposition P01 `
  -SourceDirectory $scienceSource -OutputDirectory $reviewOutput
```

输出 `review.json` 和 `summary.md`。目录不可位于源码中，也不能覆盖已有报告。来源固定为 `v0.3.2` / `28511f3d84fa65707a107cde1e8121a7b4334ecb`，逐项核对所选材料与588文件来源锁中的SHA-256；**没有核对全部588文件，没有重新执行计算或验证能量算术**。退出0表示所选字节匹配，20表示缺失，40表示非法路径、身份或篡改等拒绝。机器读取加 `-Json`。

P11分别列furan和取代基子项；P12分别列N12/N14/N16与历史账本，旧结果不冒充当前结果；P14列现有五个计算任务及固定范围。四份P14旧processed JSON存在非标准`Infinity`，只保留锁定原始文本，不能据此作标准JSON数值或能量判读。P01—P13目录不等于重算入口。

4. 若目标是准备自己的分子，使用现有受限 Check。填写既有请求JSON后运行：

```powershell
./scripts/start-local-runtime.ps1 -Action Check `
  -Request 'D:\your-work\request.json' -OutputRoot 'D:\your-work\check-runs'
```

默认使用本机已有r3镜像的完整image ID；其他镜像需显式`-Image`且通过原身份检查。Check执行输入/AO元数据核查，不进行SCF、网格或完整ERI。现有范围为两个登记profile和已声明的C/H、闭壳层、平面、两片段输入条件；不会自动调方向、加氢或重排。通过Check不代表可计算。当前入口没有Compute操作，原服务Compute拒绝门禁保留。

5. 查看一个既有用户服务运行目录，必要时向全新目录导出派生报告：

```powershell
./scripts/start-local-runtime.ps1 -Action Report -RunDirectory 'D:\your-work\check-runs\one-run'
./scripts/start-local-runtime.ps1 -Action Report -RunDirectory 'D:\your-work\check-runs\one-run' `
  -PythonExecutable 'C:\your-python\python.exe' `
  -ReportExportDirectory 'D:\your-work\exports\one-new'
```

基础Report复用原PowerShell报告；指定Python进入原高级只读报告路径。它核对既有服务记录及配套证据，不是所有旧科学输出或根诊断的通用读取器。Report不需要Docker。可显式提供`-PowerShell7`；List/Show/Review/Capabilities可显式提供`-PythonExecutable`。

## 登记P14计算仍使用原入口

`start-runtime.ps1`现有七任务中，`evidence/core-tests`为证据/核心测试，`p14-smoke/p14-equivalence/p14-fixed/p14-optimize/p14-classify`为五项固定P14任务。详情见[运行指南](RUN_zh-CN.md)。它们不是用户任意XYZ计算，也不是P01—P14统一量化学求解器。P14本地Docker验证来自旧镜像及旧构建提交，不能移用到当前源码的新镜像。L4可保存检查点，不支持恢复运行；L3/L4严格断网未执行。

## Git与ZIP取得的是什么

Git clone取得源码和历史。项目来源ZIP取得已跟踪源码快照，包含`RUNTIME_SOURCE_MANIFEST.json`的提交对象、树对象与文件证明；不包含Git历史、Docker镜像、依赖wheel、科学源码或运行缓存。**均不是双击即用的完整安装包**。普通GitHub ZIP缺少项目manifest，来源准备器明确拒绝；可以保留它用于阅读，不能冒充已验证构建来源。

已有本地Python可从干净Git仓库制作来源ZIP，再准备全新目录：

```powershell
python -B scripts/prepare-runtime-source.py export --source . --output 'D:\your-work\runtime-source.zip'
python -B scripts/prepare-runtime-source.py prepare --source 'D:\your-work\runtime-source.zip' `
  --target 'D:\your-work\runtime-prepared' --expected-commit '<独立确认的完整commit SHA>'
python -B 'D:\your-work\runtime-prepared\scripts\prepare-runtime-source.py' verify `
  --source 'D:\your-work\runtime-prepared' --expected-commit '<同一完整commit SHA>'
```

可另外指定独立确认的`--expected-manifest-sha256`。对象证明绑定提交、树与文件，**不认证发布者**。准备目录写`SOURCE_IDENTITY.json`，不会伪造`.git`。来源检查拒绝不干净Git、未知额外文件、路径穿越、重解析点及哈希差异；PS1仅允许明确的Git blob对应换行转换。

PowerShell 7.3+可先验证旧固定Runtime构建入口，不接触引擎：

```powershell
./scripts/build-wslc.ps1 -Engine docker -CheckOnly
```

此检查可在干净Git或已验证准备目录使用；准备目录需要现有Python，必要时`-PythonExecutable`。它只准备`container/Dockerfile`的旧固定Runtime构建身份；**不准备新的用户分子镜像、其science.tar或依赖wheel**，也不代表实际构建成功。移除`-CheckOnly`会实际构建新镜像，需要用户自己的引擎/依赖条件，必须另行验收。准备目录的构建记录写入相邻新目录，保持来源字节不变。本轮未重建镜像。

## 当前交付边界

新入口及目录为宿主源码工程能力；[能力登记](../validation/local-runtime-capabilities-v1.json)和[本轮验证记录](../validation/local-runtime-framework-20261007.json)分别说明状态和实测范围。GitHub CI仍NOT_EXECUTED，33份用户测试的分类不等于全部测试运行通过。WSLc BLOCKED/暂停；镜像分发BLOCKED；源码公开另行确认。外部专家咨询已取消，不是实施前置条件。生产Compute缺少合格端点、独立对照及研究/资源资格；内部证据不足仍需解决。

当前顺序是工程分类与登记 → 本地目录与只读报告 → 来源包准备 → 独立有预算的真实根诊断 → 按命题增加P01—P13适配 → 框架稳定后改网页。真实根求解器未实现，现行合同科学授权为false。本轮不启动科学计算，也不改变方法、占据规则或最终容差。
