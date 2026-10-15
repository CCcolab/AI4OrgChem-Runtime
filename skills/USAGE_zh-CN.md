# 安装和调用Skill

[技能目录](README_zh-CN.md) · [English](USAGE.md)

## 1. 取得源码

从GitHub克隆main到自己的新目录，并记录实际提交；不要以旧v0.1.0资产代替本次增补：

```sh
git clone --branch main https://github.com/CCcolab/AI4OrgChem-Runtime.git runtime-source
cd runtime-source
git rev-parse HEAD
```

也可下载包含skills/的分支源码ZIP，解压后进入仓库根目录。指南下载ZIP仅供阅读，不是技能包或安装环境。

## 2. 按需安装一个技能

Codex用户级位置为Windows的`%USERPROFILE%\.agents\skills`或Linux/macOS的`~/.agents/skills`，项目级为`.agents/skills`。仅仓库的skills/目录不自动加载。下面只安装RHF示例，其他项替换为目录中的真实名称；不要求一次安装15项。目标已存在先自行备份/核对，本命令拒绝覆盖。

Windows PowerShell，在克隆的仓库根目录：

```powershell
$skillName = 'rhf-single-point'
$skillSource = Join-Path (Join-Path (Get-Location) 'skills') $skillName
$skillParent = Join-Path $env:USERPROFILE '.agents\skills'
$skillTarget = Join-Path $skillParent $skillName
if (-not (Test-Path -LiteralPath (Join-Path $skillSource 'SKILL.md'))) { throw 'Skill source missing' }
if (Test-Path -LiteralPath $skillTarget) { throw 'Target exists; review and back up before updating' }
New-Item -ItemType Directory -Path $skillParent -Force | Out-Null
Copy-Item -LiteralPath $skillSource -Destination $skillTarget -Recurse
```

Linux/macOS，在克隆的仓库根目录：

```sh
skill_name=rhf-single-point
skill_parent="$HOME/.agents/skills"
skill_target="$skill_parent/$skill_name"
if [ ! -f "skills/$skill_name/SKILL.md" ]; then
  printf '%s\n' 'Skill source missing' >&2
  false
elif [ -e "$skill_target" ] || [ -L "$skill_target" ]; then
  printf '%s\n' 'Target exists; review and back up before updating' >&2
  false
else
  mkdir -p "$skill_parent" && cp -R "skills/$skill_name" "$skill_target"
fi
```

项目级安装时将目标父目录改为该项目的`.agents/skills`；不要重复安装同名用户级/项目级副本。同名技能不会自动合并。Codex检测到后可用`$技能名`调用，未出现时重启Codex。SKILL.md可手工创建，不需要shell中的create-skill命令，optional子目录不是必要条件。平台规则以[官方Skill说明](https://learn.chatgpt.com/docs/build-skills)为准。

上面只复制技能文件，不安装依赖或Runtime。单个目录独立使用所需指令都在SKILL.md；复制后的README可查来源仓库中的[公共安装指南](https://github.com/CCcolab/AI4OrgChem-Runtime/blob/main/skills/USAGE_zh-CN.md)，它的相对目录/测试链接适用于完整skills树。

## 3. 调用并准备真实任务

```text
使用 $rhf-single-point。
输入：填写实际molecule.xyz路径。RHF/6-31G(d)，电荷0，多重度1，单位Å。
保持坐标和原子顺序，先检查输入与已有后端，生成完整输入/程序和实际命令。
本次只准备，不执行或安装；结果写入新目录。
```

选定输入与资源后可明确要求执行一次，保留日志和拒绝记录。其他Agent按其实际加载机制读取完整SKILL.md，不假设它识别Codex的$语法；只有Python终端时，应先取得Agent生成的程序，不能执行Markdown。README中的run_analysis.py是待生成示例，不是随包脚本。

## 4. 使用环境与Runtime的区别

表格/矩阵可用已有NumPy/SciPy，图模式按需RDKit，量化任务用已有且许可/接口明确的后端。PySCF的平台条件见[官方安装文档](https://pyscf.org/user/install.html)；不把维护者特定解释器或测试机器当用户配置。依赖安装、全局环境修改与远程提交不因读取Skill自动授权。

使用Runtime服务时另按[源码安装指南](../docs/SOURCE_INSTALLATION_zh-CN.md)和实际服务合同操作，固定对象不允许任意换XYZ，P14独立镜像不混入四家安装记录。通用Skill准备的离子、其他基组或约束方案不属于Runtime现有受限RHF服务验收；条件Compute仍未开放，完整轨道资格、多态全集合和镜像分发限制保留。L4可保存检查点但不能恢复。

## 5. 输出与本地测试

写入新目录；记录输入、单位、方法、参数、版本、真实日志与执行状态。未执行/不合格不得填成功结果，残差和容差来源分列。[测试范围](TESTING_zh-CN.md)说明每项实际覆盖和未执行事项；公开摘要不含全部原始证据。安装示例的隔离副本检查不认证所有平台。

公开维护补充：[最小程序回归](../validation/public_regression/README.md) · [完整 MO 附加审查](../docs/CANONICAL_ORBITAL_REVIEW_zh-CN.md)。仅执行工程/合成数据检查，未补跑当前 RHF；历史测试不转为新版本 Agent 验收。15 个 Skill 属于 v0.1.0 后源码增补，旧 Release 资产及指南 ZIP 不自动包含。
