[English guide](USER_GUIDE.md) · [English README](../../README.md) · [Chinese counterpart](../../docs/CURRENT_HIGH_COST_CASES_zh-CN.md)

# High-cost fixed-system states

Complete [source installation](SOURCE_INSTALLATION.md). Register this family once in the same installed directory:

```powershell
Set-Location 'D:\chem-work\runtime-install\runtime'
$installed = Get-Content ..\built-image.json -Raw | ConvertFrom-Json
python -B .\scripts\register-installation.py --service high-cost-cases --image $installed.local_tag --output-dir ..\installations\high-cost-cases
```

The installed source contract checks the original 107 entries, seven exact local-test exclusions and allowed engineering overrides, giving 100 installed entries. The historical candidate still uses its original 107 entries; this is not a relaxed source threshold.

```powershell
python -B .\scripts\list-high-cost-cases.py
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\high-cost-cases\installation-record.json --task P11 --mode ledger --output-root ..\runs\p11-ledger-new
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\high-cost-cases\installation-record.json --task P12 --mode ledger --output-root ..\runs\p12-ledger-new
```

P11 registers 17 states and P12 registers 61, totaling 78 units. Only the historical benzene-G and N12-G pilots have numerical acceptance. The other 76 states, complete multistate assembly and scientific replay on a new installation have not inherited PASS.

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
