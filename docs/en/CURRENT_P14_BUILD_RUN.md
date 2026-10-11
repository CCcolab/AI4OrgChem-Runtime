[English guide](USER_GUIDE.md) · [English README](../../README.md) · [Chinese counterpart](../../docs/CURRENT_P14_BUILD_RUN_zh-CN.md)

# Original seven tasks: a separate P14 build and run contract

This environment is not one of the four `register-installation.py` service families. It uses its own Dockerfile, frozen 588-file scientific source archive and actual image identity. Do not pass a four-family image or installation record to the old seven-task launcher. You need an existing Docker Linux/amd64 engine and PowerShell 7.3+.

```powershell
.\scripts\build-docker.ps1 -Tag ai4orgchem-runtime:p14-local
.\scripts\run-docker.ps1 -Task evidence -Image ai4orgchem-runtime:p14-local -OutputRoot D:\chem-work\p14-runs-new -LockRoot D:\chem-work\p14-locks-new
```

These commands illustrate the workflow; this documentation update does not build or execute it. Build from clean, committed, identity-fixed Runtime source. A new image/result cannot inherit historical scientific PASS. Inspect the actual [launcher](../../scripts/run-docker.ps1) and [task implementation](../../runtime/cli.py) before running other tasks.

| Task | Purpose |
| --- | --- |
| `evidence` | Read and verify frozen evidence; no new molecular calculation |
| `core-tests` | Exercise the frozen scientific core implementation |
| `p14-smoke` | Technical STO-3G trial; not a scientific endpoint certification |
| `p14-equivalence` | STO-3G implementation comparison in its recorded scope |
| `p14-fixed` | Fixed-geometry ordinary/conditional energy comparison |
| `p14-optimize` | Constrained G/PLG optimization and structure response |
| `p14-classify` | Joint review of four complete, compatible parent results |

The source-proxy is fixed C12H6 with a planar D3h five-parameter geometry; production uses B3LYPG/6-31G(d), grid level 3 and registered PLG screening rules. See [result interpretation](REVIEW_RESULTS.md), [the service matrix](CURRENT_PROFESSIONAL_SERVICES.md) and [the four-parent review template](P14_REVIEW_TEMPLATE.md). P14 production has a distinct effective-memory requirement of at least 13 GiB; default eight threads are not a hard CPU quota. Historical 54.37-second/21.20-minute observations are not universal runtime estimates.

Task-specific resources, dependency outputs and calculation authorization still apply. Invalid image/scientific qualification must be refused. L3/L4 strict offline acceptance was not executed. Checkpoints are saved, but L4 cannot resume. User-entry failures do not automatically reopen the original P01–P14 conclusions.
