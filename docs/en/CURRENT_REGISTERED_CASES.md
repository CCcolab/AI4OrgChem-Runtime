[English guide](USER_GUIDE.md) · [English README](../../README.md) · [Chinese counterpart](../../docs/CURRENT_REGISTERED_CASES_zh-CN.md)

# Fixed examples: statistics, graph ledgers and orbital density

This page explains installation and use for frozen-table statistics, graph rules and occupied-orbital controls. Inputs and protocols are registered and fixed; arbitrary user XYZ belongs to the [ordinary RHF entry](CURRENT_MOLECULAR_SINGLE_POINT.md).

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

Register `registered-cases` using this build's local tag and a new registration directory. Preserve an existing record. Registration checks identity without starting science; new images do not inherit historical PASS. This documentation update executed none of these builds or calculations.

```powershell
Set-Location 'D:\chem-work\runtime-install\runtime'
$installed = Get-Content ..\built-image.json -Raw | ConvertFrom-Json
python -B .\scripts\register-installation.py --service registered-cases --image $installed.local_tag --output-dir ..\installations\registered-cases
```

## 3. Choose a fixed task

Choose by research purpose. These tasks use registered inputs and do not accept a user request or arbitrary changes to fragments, geometry, basis or tolerances.

| Module | Actual task argument | Calculation scope |
| --- | --- | --- |
| Structure and spectrum table statistics | `p02-statistics` | Frozen-table fitting; zero SCF calls; no new spectrum |
| Conjugated graph rules and energy ledger | `p13-graph-ledger` | Fixed graphs/RDKit rules and saved-ledger arithmetic; no new quantum energy |
| Orbital representation and density comparison | `p01-orbital-density` | Fixed ethene RHF, Boys and Pipek–Mezey once each; actual calculation must be authorized |

## 4. Run your selected task

Choose one command; you are not required to execute all three. Statistics/graph ledgers produce no new quantum energies; the orbital control actually calculates registered ethene.

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\registered-cases\installation-record.json --task p02-statistics --output-root ..\runs\p02-statistics-new
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\registered-cases\installation-record.json --task p13-graph-ledger --output-root ..\runs\p13-graph-ledger-new
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\registered-cases\installation-record.json --task p01-orbital-density --output-root ..\runs\p01-orbital-density-new
```

## 5. Read results, resources and scope

The resource contract is one CPU/thread, 1 GiB and 120 seconds. These are alternative instructions, not automatic execution. Keep `output/case/case-report.md`, `case-result.json` and complete receipts. Separate execution, numerical qualification, comparison and scientific interpretation.

P02 verifies statistics for the registered table, not PDF/CIF authenticity, crystallographic refinement or causation. P13 verifies the registered graph and arithmetic, not independent QM optimization of every candidate. P01 shows how occupied-orbital representations may change while the same electronic state's density and energy remain invariant; it does not establish a chemical stabilization-energy label. Inspect `representations`, `findings`, `control_qualified` and `occupied-representations.npz` where applicable.

Historical image/launcher identities remain separate. Do not pass a newly installed image to `start-registered-case.ps1`. See [the service matrix](CURRENT_PROFESSIONAL_SERVICES.md) for actual acceptance and evidence.

Open `output/case/case-report.md` inside the actual run directory returned by the launcher. Keep `output/case/case-result.json`, `output/guard-receipt.json`, resources, worker/host receipts and manifests. P02 focuses on fits/reference residuals, P13 on graph rules/ledger identities, and P01 on density/energy invariants and occupied representations. Shared environment does not imply a shared schema/interpretation. See [the service matrix](CURRENT_PROFESSIONAL_SERVICES.md). Preserve missing/identity/failed-check status rather than declaring PASS from exit0 alone.
