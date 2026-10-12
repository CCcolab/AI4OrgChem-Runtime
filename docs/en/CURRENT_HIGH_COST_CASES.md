[English guide](USER_GUIDE.md) · [English README](../../README.md) · [Chinese counterpart](../../docs/CURRENT_HIGH_COST_CASES_zh-CN.md)

# High-cost fixed-system states

This page explains installation and use for registered multistate optimization and ring-size/state comparisons. Inputs and protocols are registered and fixed; arbitrary user XYZ belongs to the [ordinary RHF entry](CURRENT_MOLECULAR_SINGLE_POINT.md).

## 1. Prepare the shared Runtime environment once

This module uses the [unified Runtime source/Docker environment](SOURCE_INSTALLATION.md), not a standalone module installer. With this installation's built-image.json, skip to step2; with this service's installation-record.json, go directly to task selection/run. Do not rebuild, overwrite registration or run every module together.

For first installation, use existing Git, Python3.12+, Docker Linux/amd64 and build-time network. Container calculations/ledger tasks also need Docker available. Use new directories for the following Windows PowerShell commands; dedicated source-ZIP/checksum and Linux output-permission requirements are in the installation guide.

```powershell
git clone --branch main https://github.com/CCcolab/AI4OrgChem-Runtime.git D:\chem-work\runtime-source
Set-Location 'D:\chem-work\runtime-source'
git rev-parse HEAD
python -B .\scripts\install-local-runtime.py prepare --destination D:\chem-work\runtime-install
python -B .\scripts\install-local-runtime.py build --destination D:\chem-work\runtime-install
```

Prepare/build runs in `runtime-source`. Subsequent commands run in `runtime-install\runtime`, not the downloaded source directory. built-image.json is in the installation root; installations and runs are siblings of runtime. On failure read installation logs before proceeding, without changing scientific rules.

## 2. Register only the selected service, once

Register `high-cost-cases` using this build's local tag and a new registration directory. Preserve an existing record. Registration checks identity without starting science; new images do not inherit historical PASS. This documentation update executed none of these builds or calculations.

```powershell
Set-Location 'D:\chem-work\runtime-install\runtime'
$installed = Get-Content ..\built-image.json -Raw | ConvertFrom-Json
python -B .\scripts\register-installation.py --service high-cost-cases --image $installed.local_tag --output-dir ..\installations\high-cost-cases
```

The installed source contract checks the original 107 entries, seven exact local-test exclusions and allowed engineering overrides, giving 100 installed entries. The historical candidate still uses its original 107 entries; this is not a relaxed source threshold.

## 3. Start with the state listing and saved ledgers

```powershell
python -B .\scripts\list-high-cost-cases.py
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\high-cost-cases\installation-record.json --task P11 --mode ledger --output-root ..\runs\p11-ledger-new
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\high-cost-cases\installation-record.json --task P12 --mode ledger --output-root ..\runs\p12-ledger-new
```

P11 registers 17 states and P12 registers 61, totaling 78 units. Only the historical benzene-G and N12-G pilots have numerical acceptance. The other 76 states, complete multistate assembly and scientific replay on a new installation have not inherited PASS.

## 4. Single-state preflight and a new budget

For preflight, select one actual unexecuted unit from the listing, then use `--task P11` or `--task P12`, `--mode preflight` and `--unit`. Do not repeat resource admission for an already accepted historical state just to recheck its record.

Live execution additionally requires the same `--installation-record`, `--mode live`, one real `--unit`, an independently created `--budget`, and a new `--output-root`. Supply qualified dependencies from this execution batch through `--inputs`. P11A orders G → GL → GE; P12 GL/GE require this batch's G, and N16 GE also requires its GL. Create the budget with `create-high-cost-budget.py`; do not hand-write, reuse or clear it. One execution per state; failed executions count; no retry or resume.

Unknown create, removal or owned-resource probe states preserve the isolation lock and `RESERVED` budget. A single query reporting no container, or lack of a returned ID, is not proof of closure. Settlement requires every owned operation to close and the owner's lock to be released. Do not delete a lock to bypass uncertainty.

| Scope | CPU/threads | Memory | Scratch | Deadline |
| --- | ---: | ---: | ---: | --- |
| Ledger/preflight | 1 | 1 GiB | As configured | 180 seconds |
| P11 live, one unit | 8 | 8 GiB | 20 GiB | 12 hours |
| P12 live, one unit | 16 | 14 GiB | 20 GiB | 12 hours; at most 80 geometry steps |

These live limits are task admission contracts, not daily idle memory requirements. Frozen [configuration](../../configs/high-cost-cases-v1.json), state dependencies and scientific thresholds remain unchanged. Preserve host, worker, guard, resource, budget and manifest records. Scratch intermediates are not final scientific results.

The historical relative CESE value `2.103137%` uses the absolute sum of weighted energy-difference assembly terms as its denominator. It is a boundary indicator, not percentage error relative to a book value; complete assembly is not established. L4 can save checkpoints but does not support restart/resume. Old `start-high-cost-case.ps1` belongs to its own historical image.

## 5. Single-state command example, not an automatic workload

The example selects `P11A-furan-G`, without parent-state dependencies and outside the two accepted historical pilots. Confirm your intended state/resource contract before separately running preflight, budget creation and live; do not repeat accepted benzene-G/N12-G merely to review records. The budget file must be new;43200 seconds is this state’s12-hour ceiling, not an expected runtime.

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\high-cost-cases\installation-record.json --task P11 --mode preflight --unit P11A-furan-G --output-root ..\runs\p11-furan-g-preflight-new
python -B .\scripts\create-high-cost-budget.py --unit P11A-furan-G --ceiling-seconds 43200 --output D:\chem-work\p11-furan-budget-new.json
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\high-cost-cases\installation-record.json --task P11 --mode live --unit P11A-furan-G --budget D:\chem-work\p11-furan-budget-new.json --output-root ..\runs\p11-furan-g-live-new
```

States with prerequisites additionally require an `--inputs` JSON. For example, furan-GL needs this batch’s furan-G **actual output subdirectory**, not its top-level output root or a frozen historical result:

```json
{"P11A-furan-G": "D:/chem-work/runtime-install/runs/p11-furan-g-live-new/ACTUAL_RUN_ID/output"}
```

Replace `ACTUAL_RUN_ID` with the real launcher-returned directory. Create a separate budget listing the actual GL unit, then add `--inputs D:\chem-work\p11-gl-inputs.json` to its live command. Mapping keys must exactly match configured dependencies; parents must have qualified completed outputs/confirmed removal and matching source/profile/dependency/image identity. List every parent for multi-parent states such as N16 GE. Historical pilot PASS cannot fill a gap. Ledger/preflight needs no scientific dependency mapping; stop there when prerequisites are incomplete.

## 6. Resources, results and failures

Ledger/preflight requires1GiB scratch as well as its1GiB memory profile. The live limits in the table above are task-specific, not idle daily memory consumption.

Read `output/result.json`, `output/worker-receipt.json`, `output/guard-receipt.json`, `output/run-manifest.json`, host records and budget from the actual returned run. Use [the matrix](CURRENT_PROFESSIONAL_SERVICES.md) for state checks/method/identity. Keep actual optimized.xyz/trajectories/intermediates without assuming a uniform trajectory format. Insufficient resources mean recorded refusal, not reduced memory/scientific thresholds. No new admission is imposed on the previously accepted P12 by this documentation review. Single-state acceptance is not complete assembly; L4 has no resume.
