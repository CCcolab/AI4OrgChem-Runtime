[English guide](USER_GUIDE.md) · [English README](../../README.md) · [Chinese counterpart](../../docs/CURRENT_MOLECULAR_SINGLE_POINT_zh-CN.md)

# Your molecule: install and use RHF single-point calculations

This module evaluates RHF/6-31G(d) at your XYZ geometry and saves energy, canonical orbitals and spin-summed AO density. Supported scope: H/C/N/O, neutral closed-shell singlets, at most20 atoms and actual AO≤80. It does not optimize geometry, add hydrogens or identify the real ground state automatically.

## Is this the whole Runtime or a separate RHF installer?

[Source installation](SOURCE_INSTALLATION.md) prepares unified Runtime source and the shared Docker environment, rather than a standalone RHF package. **For RHF alone, register only `molecular-service`; you do not need to register or execute the other three families.** Registration checks/records image identity and does not start science. The original seven-task/P14 environment has a separate build contract.

The dedicated source ZIP carries installation proofs, not a complete installed environment. The guide ZIP is reading material. Source still needs prepare/build. First installation requires existing Python3.12+, Git when cloning, available Docker Linux/amd64 and build-time network. Docker is also needed for calculations, but not for reading guidance.

| Existing setup | Start here |
| --- | --- |
| No source or built environment | Step1 |
| This installation has built-image.json but no RHF registration | Step3 |
| This service already has installation-record.json | Step4 or5; do not rebuild or overwrite registration |

These Windows PowerShell instructions use replaceable example directories. This documentation update executed no build or calculation.

## 1. Obtain Runtime source

Clone current main into a new directory for committed maintenance/documentation; record the actual commit:

```powershell
git clone --branch main https://github.com/CCcolab/AI4OrgChem-Runtime.git D:\chem-work\runtime-source
Set-Location 'D:\chem-work\runtime-source'
git rev-parse HEAD
```

Alternatively, extract the [dedicated v0.1.0 source asset](DOWNLOADS.md) into a new directory and enter its root containing scripts. It stays fixed at v0.1.0 and excludes later main documents. GitHub's automatic Source code ZIP lacks installation proofs. See [installation requirements](SOURCE_INSTALLATION.md).

## 2. Build the shared local environment

Run from the source directory. The installation destination must not exist:

```powershell
python -B .\scripts\install-local-runtime.py prepare --destination D:\chem-work\runtime-install
python -B .\scripts\install-local-runtime.py build --destination D:\chem-work\runtime-install
```

Prepare downloads/verifies fixed scientific sources/dependencies; build actually creates a local image. On failure inspect installation logs before proceeding, without resetting an old environment or changing scientific rules.

```text
D:\chem-work\runtime-source\                  Downloaded source; prepare/build here
D:\chem-work\runtime-install\built-image.json  New local image record
D:\chem-work\runtime-install\runtime\         Working directory for registration/runs
D:\chem-work\runtime-install\installations\   Generated service identity records
D:\chem-work\runtime-install\runs\            New execution outputs
```

## 3. Register only RHF, once

Enter the generated runtime directory and use this installation's local tag. Registration requires a new output directory. Never overwrite an existing record or hand the new image to a historical candidate launcher; historical scientific acceptance does not transfer.

```powershell
Set-Location 'D:\chem-work\runtime-install\runtime'
$installed = Get-Content ..\built-image.json -Raw | ConvertFrom-Json
python -B .\scripts\register-installation.py --service molecular-service --image $installed.local_tag --output-dir ..\installations\molecular-service
```

Keep using `..\installations\molecular-service\installation-record.json`; registration success is not a completed RHF calculation.

## 4. Run the supplied water example

In the same runtime directory, this command actually runs one RHF single point. Use a new output directory:

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\molecular-service\installation-record.json --task single-point --request .\examples\molecular-service\water\request.json --output-root ..\runs\water-new
```

Water is a technical fixed geometry, not an optimized/authenticated experimental structure. If it fails, retain its errors/logs; a created output file alone is not success. Do not overwrite a run or retry automatically.

## 5. Use your own molecule

Put XYZ and request JSON together in your new molecule directory. Coordinates use angstroms. XYZ has the actual atom count on line1, a comment on line2, then one element/three coordinates per line. Copy the [water XYZ](../../examples/molecular-service/water/molecule.xyz) and [request template](../../examples/molecular-service/water/request.json) and replace the geometry with your confirmed structure. `structure.file` is the XYZ basename, not an absolute path; see [the schema](../../schemas/molecular-single-point-v1.json).

Confirm RHF/6-31G(d), H/C/N/O, neutral closed-shell singlet, ≤20 atoms and actual AO≤80. Even electron count and singlet declaration do not establish closed-shell single-determinant applicability. General three-dimensional structures are allowed. Use the same installation record and a different new output directory:

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\molecular-service\installation-record.json --task single-point --request D:\chem-work\my-molecule\request.json --output-root ..\runs\my-molecule-new
```

Water and your molecule are separate executions with separate outputs. Do not change profiles/tolerances to bypass unsupported inputs.

The budget is one CPU/thread, 1 GiB, a 120-second hard deadline and a 100-second soft-stop boundary; at most one RHF kernel and 100 SCF cycles. There is no retry or resume. These are instructions, not a report that this run has already been executed.

## 6. Read and retain results

Read the records directory returned by the launcher, starting with `output/calculation/report.md`. Keep `result.json`, `orbitals-density.npz` and all host, worker, guard, resource and manifest records together. Inspect `diagnostics.energy_ledger`, `diagnostics.orbital_summary`, `diagnostics.checks` and `diagnostics.residuals`; separate execution, numerical qualification and interpretation. See [the service matrix](CURRENT_PROFESSIONAL_SERVICES.md).

The initial twelve numerical checks qualify only the recorded fixed-geometry RHF endpoint scope. Canonical orbitals, especially the virtual space, do not acquire full-space qualification merely because existing booleans pass. Full-MO eigen residuals are diagnostics. New host receipts disclose `evidence_review.qualification_scope` and `evidence_review.orbital_export_qualification`.

The complete orbital orthogonality/eigen gate is not implemented; wavefunction stability and physical-ground-state certification were not executed. Four historical molecule runs and four same-version PySCF direct-call controls establish scoped wrapper consistency, not an independent-engine scientific certification. HOMO–LUMO gap is a diagnostic rather than a gate for this service. Preserve the original four results and twelve checks.

User DFT, ions, open-shell states, general optimization, scans and conditional-state comparisons are outside this entry. The historical `start-molecular-service.ps1` requires its own original candidate image and is not the new-installation launcher.
