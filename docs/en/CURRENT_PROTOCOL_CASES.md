[English guide](USER_GUIDE.md) · [English README](../../README.md) · [Chinese counterpart](../../docs/CURRENT_PROTOCOL_CASES_zh-CN.md)

# Fixed research protocols: torsion, conditional energies and closure

This page explains installation and use for fixed torsion, conditional energy, closure and structure-response protocols. Inputs and protocols are registered and fixed; arbitrary user XYZ belongs to the [ordinary RHF entry](CURRENT_MOLECULAR_SINGLE_POINT.md).

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

Register `protocol-cases` using this build's local tag and a new registration directory. Preserve an existing record. Registration checks identity without starting science; new images do not inherit historical PASS. This documentation update executed none of these builds or calculations.

```powershell
Set-Location 'D:\chem-work\runtime-install\runtime'
$installed = Get-Content ..\built-image.json -Raw | ConvertFrom-Json
python -B .\scripts\register-installation.py --service protocol-cases --image $installed.local_tag --output-dir ..\installations\protocol-cases
```

## 3. Choose a protocol and mode

List tasks with `python -B .\scripts\list-protocol-cases.py`. Choose by calculation name; P IDs are exact command arguments. Methods differ and are not all ordinary RHF.

| Module | --task | Live scope |
| --- | --- | --- |
| Torsion endpoints and energy ledger | P03 | One ordinary DFT point at frozen geometry |
| π–π direct term and orbital response | P04 | One fixed DSI3/FUD point |
| π–σ conditional-energy comparison | P05 | Fixed17° G/FUD |
| Fragment conditional-energy assembly | P06 | Fixed0° PDSI/FUL |
| Same-Hamiltonian ledger closure | P07 | No live mode |
| Butadiene localized endpoint/reference | P08 | Frozen GL geometry, no optimization |
| Cyclobutadiene conditional diagnostic | P09 | Fixed geometry, no optimization |
| Benzene BLA energy response | P10 | Five fixed ordinary DFT points |

| Mode | Meaning |
| --- | --- |
| ledger | Saved-ledger arithmetic, no new SCF |
| preflight | Registered input/AO/resource checks, no SCF or convergence guarantee |
| live | New calculation within this fixed protocol; requires a fresh independent budget |

Choose one registered P03–P10 object using the [service matrix](CURRENT_PROFESSIONAL_SERVICES.md). Their input, method, comparison and result contracts differ. These tasks are not an arbitrary user-XYZ entry.

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P07 --mode ledger --output-root ..\runs\p07-ledger-new
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P03 --mode preflight --output-root ..\runs\p03-preflight-new
```

`ledger` and `preflight` require matching image/source identities, resources and output paths. They do not grant convergence or scientific qualification. P07 has no `live` mode. The other seven live tasks each require an independently created fresh batch budget and one execution per task; keep the original failed records. Do not repeat already accepted historical calculations merely to complete documentation.

## 4. New science: prepare a budget before live execution

For a separately authorized, unexecuted object, the live parameter form is:

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P03 --mode live --budget D:\chem-work\batch-budget-new.json --output-root ..\runs\p03-live-new
```

This is an example, not execution authorization. For a separately authorized new batch, save the following contract as a new UTF-8 file **without a BOM**, then pass its absolute path to `--budget`. Never overwrite, clear or reuse a previous ledger. The fixed [protocol configuration](../../configs/protocol-cases-v1.json) still determines each task's scientific inputs and gates.

```json
{
  "schema": "protocol-case-batch2-budget-v1",
  "ceiling_seconds": 6300,
  "one_attempt_per_case": true,
  "scientific_cases": ["P03", "P04", "P05", "P06", "P08", "P09", "P10"],
  "attempts": {},
  "old_root_budget_reused": false,
  "budget_is_accounting_not_method_approval": true
}
```

Unknown create/cleanup states keep the budget `RESERVED` and retain the isolation lock; no automatic retry or manual unlock bypass is allowed. A native-admission pause record, if present, refuses new reservations/containers before scientific work without altering the protocol.

## 5. Read results and execution records

Ledger/preflight: one CPU/thread, 1 GiB, 120 seconds. Live: two CPUs/threads, 4 GiB, 900-second hard limit, soft stop at 840 seconds, no additional swap. The seven-item batch reserves at most 6300 seconds and runs serially.

Keep `output/case-result.json`, `guard-receipt.json`, resource receipts, host execution and the complete directory manifest. Fixed-protocol consistency does not establish independent-engine certification. `start-protocol-case.ps1` belongs only to its original historical candidate environment.

First inspect `output/case-result.json` in the actual run directory: task, mode, selected object and current checks, then the module-specific fields in [the service matrix](CURRENT_PROFESSIONAL_SERVICES.md). Preserve `output/guard-receipt.json`, `output/worker-receipt.json`, `output/run-manifest.json` and host execution records. Where no common automatic report.md exists, read JSON; ledger/preflight success is not live acceptance. Preserve uncertain cleanup/open budgets/failures without deleting locks or retrying.
