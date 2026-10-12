[English guide](USER_GUIDE.md) · [English README](../../README.md) · [Chinese counterpart](../CURRENT_P14_BUILD_RUN_zh-CN.md)

# P14 conditional energy and structure response: separate installation and use

This module reviews the fixed planar D3h five-parameter C12H6 source-proxy, not user XYZ. It is **not one of the four register-installation service families**:588 frozen scientific files, its own Dockerfile/image and seven-task launcher. Do not use a four-family image or installation record here.

## 1. Prepare clean source and existing tools

An existing clean Git checkout is usable; this first-use example chooses a separate directory to avoid installation-directory confusion. Use Git, existing PowerShell7.3+, Docker Linux/amd64 and build-time public-source/PyPI/base-image network. Do not invoke7.3-required scripts directly in Windows PowerShell5.1. No tools/system features are installed or upgraded by this documentation.

```powershell
git clone --branch main https://github.com/CCcolab/AI4OrgChem-Runtime.git D:\chem-work\runtime-p14-source
Set-Location 'D:\chem-work\runtime-p14-source'
git rev-parse HEAD
$PSVersionTable.PSVersion
.\scripts\build-docker.ps1 -CheckOnly
```

CheckOnly verifies source/build identity without engine access/image build or scientific acceptance. This example uses a Git checkout; the four-family source ZIP proofs are not the same source-snapshot contract.

## 2. Build once and retain the actual image identity

```powershell
.\scripts\build-docker.ps1 -Tag ai4orgchem-runtime:p14-local
```

container/Dockerfile downloads/verifies588 sources and locked dependencies from a fixed public Python base; it is not private historical image distribution. Use clean committed source and retain `.build/image-inspect.json`. An existing matching P14 environment needs no rebuild; a new image cannot inherit historical science PASS.

## 3. Start with evidence and core checks

Use one external output root and shared lock root for this batch. Each task creates its own unique run subdirectory without overwriting history:

```powershell
.\scripts\run-docker.ps1 -Task evidence -Image ai4orgchem-runtime:p14-local -OutputRoot D:\chem-work\p14-runs-new -LockRoot D:\chem-work\p14-locks-new
.\scripts\run-docker.ps1 -Task core-tests -Image ai4orgchem-runtime:p14-local -OutputRoot D:\chem-work\p14-runs-new -LockRoot D:\chem-work\p14-locks-new
```

Evidence verifies frozen bytes; core-tests tests the scientific core. Neither is a user-molecule energy calculation. Preserve failed logs and stop later scientific interpretation.

## 4. Choose a technical control or production task

| Actual -Task | Purpose | Boundary |
| --- | --- | --- |
| p14-smoke | Technical trial | STO-3G, not production science certification |
| p14-equivalence | Implementation comparison | Recorded STO-3G equivalence scope |
| p14-fixed | Fixed-geometry energy ledger | B3LYPG/6-31G(d), grid3, registered screening |
| p14-optimize | Constrained G/PLG geometry response | Five parameters, not general user optimization |
| p14-classify | Four-parent joint review | Four compatible completed runs required |

Select tasks individually; do not automatically start high-cost production as an installation test. The technical-trial command form is:

```powershell
.\scripts\run-docker.ps1 -Task p14-smoke -Image ai4orgchem-runtime:p14-local -Threads 8 -OutputRoot D:\chem-work\p14-runs-new -LockRoot D:\chem-work\p14-locks-new
```

For another actual task keep the same image/output/lock roots. L3 requires13000MiB effective memory; L4 requires13GiB. Default8 threads is not a hard CPU quota. Historical54.37-second/21.20-minute observations are not expected runtimes for every user. Review actual [launcher parameters](../../scripts/run-docker.ps1), [resource/task implementation](../../runtime/cli.py) and [service scope](CURRENT_PROFESSIONAL_SERVICES.md) before production. Preserve source/resource/dependency/scientific gates. Historical strict-offline L3/L4 acceptance was not executed.

## 5. Classify only after four parents are complete

Select actual smoke/equivalence/fixed/optimization run subdirectories from this output root. Replace every uppercase placeholder with its real directory; all parents must be under the same OutputRoot:

```powershell
.\scripts\run-docker.ps1 -Task p14-classify -Image ai4orgchem-runtime:p14-local `
  -OutputRoot D:\chem-work\p14-runs-new -LockRoot D:\chem-work\p14-locks-new `
  -SmokeRun D:\chem-work\p14-runs-new\ACTUAL_SMOKE_RUN `
  -EquivalenceRun D:\chem-work\p14-runs-new\ACTUAL_EQUIVALENCE_RUN `
  -SourceLevelRun D:\chem-work\p14-runs-new\ACTUAL_FIXED_RUN `
  -OptimizationRun D:\chem-work\p14-runs-new\ACTUAL_OPTIMIZATION_RUN
```

Do not supply frozen JSON without manifests or combine incompatible historical sources/dependencies/inputs to fill missing parents. Classification performs no new SCF and does not replace parent qualification.

## 6. Retain and interpret results

Keep each run-manifest.json, stdout/stderr and applicable result.json/report.md/checkpoint.json. Check numerical gates, exits, hashes and source/image/dependency identity; a created file or child exit0 alone is not PASS. Current Runtime returns4 for failed/unknown/missing scientific gates; preserve old-image behavior as historical evidence.

Use [result interpretation](REVIEW_RESULTS.md) and [the four-parent template](P14_REVIEW_TEMPLATE.md), distinguishing execution, numerical checks, comparison and classification. Conclusions apply to the fixed protocol, not arbitrary molecules/all aromaticity theories. L4 saves checkpoints but **cannot resume**. User-entry failures do not automatically reopen P01–P14. This documentation change ran no build/science and changed no rules/thresholds.
