[English guide](USER_GUIDE.md) · [English README](../../README.md) · [Chinese counterpart](../../docs/CURRENT_PROTOCOL_CASES_zh-CN.md)

# Fixed research protocols: torsion, conditional energies and closure

Complete [source installation](SOURCE_INSTALLATION.md), enter the same installed `runtime` directory and register once:

```powershell
Set-Location 'D:\chem-work\runtime-install\runtime'
$installed = Get-Content ..\built-image.json -Raw | ConvertFrom-Json
python -B .\scripts\register-installation.py --service protocol-cases --image $installed.local_tag --output-dir ..\installations\protocol-cases
```

Choose one registered P03–P10 object using the [service matrix](CURRENT_PROFESSIONAL_SERVICES.md). Their input, method, comparison and result contracts differ. These tasks are not an arbitrary user-XYZ entry.

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P07 --mode ledger --output-root ..\runs\p07-ledger-new
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\protocol-cases\installation-record.json --task P03 --mode preflight --output-root ..\runs\p03-preflight-new
```

`ledger` and `preflight` require matching image/source identities, resources and output paths. They do not grant convergence or scientific qualification. P07 has no `live` mode. The other seven live tasks each require an independently created fresh batch budget and one execution per task; keep the original failed records. Do not repeat already accepted historical calculations merely to complete documentation.

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

Ledger/preflight: one CPU/thread, 1 GiB, 120 seconds. Live: two CPUs/threads, 4 GiB, 900-second hard limit, soft stop at 840 seconds, no additional swap. The seven-item batch reserves at most 6300 seconds and runs serially.

Keep `output/case-result.json`, `guard-receipt.json`, resource receipts, host execution and the complete directory manifest. Fixed-protocol consistency does not establish independent-engine certification. `start-protocol-case.ps1` belongs only to its original historical candidate environment.
