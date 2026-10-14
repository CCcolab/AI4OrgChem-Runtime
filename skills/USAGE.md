# Install and invoke a Skill

[Catalog](README.md) · [中文步骤](USAGE_zh-CN.md)

Clone `main` into a new directory or download a branch source ZIP that includes `skills/`, and record its commit. The existing v0.1.0 assets and guide ZIP do not include this later source supplement.

```sh
git clone --branch main https://github.com/CCcolab/AI4OrgChem-Runtime.git runtime-source
cd runtime-source
git rev-parse HEAD
```

Install only the folders you need. Codex local discovery uses `.agents/skills` in a project and `~/.agents/skills` for user-wide skills (`%USERPROFILE%\.agents\skills` on Windows). The repository's `skills/` is a distribution location, not automatic discovery. Existing destinations must be reviewed and backed up; avoid duplicate same-name copies. SKILL.md is required; optional resource folders and a shell `create-skill` command are not required. See [official instructions](https://learn.chatgpt.com/docs/build-skills).

Windows PowerShell, from the repository root:

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

Linux/macOS:

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

Replace the parent with the chosen project's `.agents/skills` for repository-scoped discovery. Copying files does not install chemistry dependencies. All execution instructions are self-contained in SKILL.md; a copied folder's relative catalog/testing links refer to the complete source tree. The bilingual module README also supplies direct links to this repository's public guides. Skill instructions remain in Chinese.

Invoke by name in Codex; if discovery has not refreshed, restart Codex. For other Agents, use their actual loading mechanism or ask them to read the complete SKILL.md.

```text
Use $rhf-single-point.
Input: my actual molecule.xyz, angstrom coordinates, charge 0, multiplicity 1.
Use RHF/6-31G(d), preserve atom order and coordinates.
Inspect my existing backend and generate full inputs/program plus actual commands.
Prepare only for now; do not install or execute. Use a new output directory.
```

For execution, specify the selected method, backend and CPU/thread/memory/time/call budget. `run_analysis.py` in a README is a requested generated program, not a shipped executable. Missing engines produce preparation material with explicit non-execution.

Use existing compatible NumPy/SciPy, RDKit or quantum-chemistry software according to the task. Backend compatibility follows its own documentation, including [PySCF installation requirements](https://pyscf.org/user/install.html). Skill setup does not require the whole Runtime; using registered Runtime services separately follows [source installation](../docs/en/SOURCE_INSTALLATION.md), identity, resource and method contracts. Generic preparation for ions, different bases or optimization does not extend Runtime's accepted neutral RHF profile. User conditional Compute remains closed; L4 checkpoints cannot resume.

Preserve inputs, parameters, versions, logs and qualified/unqualified/unexecuted outcomes. Use a new output directory and meaningful failure exits. Read [test scope](TESTING.md); no blind Agent evaluation, full scientific certification or arbitrary-platform acceptance is claimed.
