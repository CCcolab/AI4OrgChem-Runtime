[English guide](USER_GUIDE.md) · [English README](../../README.md) · [Chinese counterpart](../../docs/CURRENT_REGISTERED_CASES_zh-CN.md)

# Fixed examples: statistics, graph ledgers and orbital density

First complete [source installation](SOURCE_INSTALLATION.md). In that installation's `runtime` directory, register once; keep an existing record rather than overwriting it.

```powershell
Set-Location 'D:\chem-work\runtime-install\runtime'
$installed = Get-Content ..\built-image.json -Raw | ConvertFrom-Json
python -B .\scripts\register-installation.py --service registered-cases --image $installed.local_tag --output-dir ..\installations\registered-cases
```

Choose by research purpose. These tasks use registered inputs and do not accept a user request or arbitrary changes to fragments, geometry, basis or tolerances.

| Module | Actual task argument | Calculation scope |
| --- | --- | --- |
| Structure and spectrum table statistics | `p02-statistics` | Frozen-table fitting; zero SCF calls; no new spectrum |
| Conjugated graph rules and energy ledger | `p13-graph-ledger` | Fixed graphs/RDKit rules and saved-ledger arithmetic; no new quantum energy |
| Orbital representation and density comparison | `p01-orbital-density` | Fixed ethene RHF, Boys and Pipek–Mezey once each; actual calculation must be authorized |

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\registered-cases\installation-record.json --task p02-statistics --output-root ..\runs\p02-statistics-new
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\registered-cases\installation-record.json --task p13-graph-ledger --output-root ..\runs\p13-graph-ledger-new
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\registered-cases\installation-record.json --task p01-orbital-density --output-root ..\runs\p01-orbital-density-new
```

The resource contract is one CPU/thread, 1 GiB and 120 seconds. These are alternative instructions, not automatic execution. Keep `output/case/case-report.md`, `case-result.json` and complete receipts. Separate execution, numerical qualification, comparison and scientific interpretation.

P02 verifies statistics for the registered table, not PDF/CIF authenticity, crystallographic refinement or causation. P13 verifies the registered graph and arithmetic, not independent QM optimization of every candidate. P01 shows how occupied-orbital representations may change while the same electronic state's density and energy remain invariant; it does not establish a chemical stabilization-energy label. Inspect `representations`, `findings`, `control_qualified` and `occupied-representations.npz` where applicable.

Historical image/launcher identities remain separate. Do not pass a newly installed image to `start-registered-case.ps1`. See [the service matrix](CURRENT_PROFESSIONAL_SERVICES.md) for actual acceptance and evidence.
