[English guide](USER_GUIDE.md) · [English README](../../README.md) · [Chinese counterpart](../../docs/CURRENT_MOLECULAR_SINGLE_POINT_zh-CN.md)

# Your molecule: RHF single-point energy, orbitals and density

First follow [source installation](SOURCE_INSTALLATION.md). Run from that installation's `runtime` directory and register this service once. Never overwrite an existing installation record or hand the newly built image to a historical candidate launcher.

```powershell
Set-Location 'D:\chem-work\runtime-install\runtime'
$installed = Get-Content ..\built-image.json -Raw | ConvertFrom-Json
python -B .\scripts\register-installation.py --service molecular-service --image $installed.local_tag --output-dir ..\installations\molecular-service
```

1. Put the XYZ and request JSON in the same directory. Coordinates use angstroms; `structure.file` is the XYZ basename inside the request directory. Start with the files in `examples/molecular-service/water/` and the [request schema](../../schemas/molecular-single-point-v1.json).
2. Confirm the model: RHF/6-31G(d), H/C/N/O, neutral closed-shell singlet, at most 20 atoms and actual AO count at most 80. Even electron count and a singlet declaration do not establish that the real molecule is adequately described by a closed-shell single determinant. General three-dimensional structures are allowed.
3. Run with the same installation record and a new external output directory. Choose either the example or your request:

```powershell
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\molecular-service\installation-record.json --task single-point --request .\examples\molecular-service\water\request.json --output-root ..\runs\water-new
python -B .\scripts\run-installed-runtime.py --installation-record ..\installations\molecular-service\installation-record.json --task single-point --request D:\chem-work\my-molecule\request.json --output-root ..\runs\my-molecule-new
```

4. Read the records directory returned by the launcher. Keep `output/calculation/report.md`, `result.json`, `orbitals-density.npz`, and all host, worker, guard, resource and manifest records together. In `result.json`, inspect `diagnostics.energy_ledger`, `diagnostics.orbital_summary`, `diagnostics.checks` and `diagnostics.residuals`.

The budget is one CPU/thread, 1 GiB, a 120-second hard deadline and a 100-second soft-stop boundary; at most one RHF kernel and 100 SCF cycles. There is no retry or resume. These are instructions, not a report that this run has already been executed.

## How to interpret qualification

The initial twelve numerical checks qualify only the recorded fixed-geometry RHF endpoint scope. Canonical orbitals, especially the virtual space, do not acquire full-space qualification merely because existing booleans pass. Full-MO eigen residuals are diagnostics. New host receipts disclose `evidence_review.qualification_scope` and `evidence_review.orbital_export_qualification`.

The complete orbital orthogonality/eigen gate is not implemented; wavefunction stability and physical-ground-state certification were not executed. Four historical molecule runs and four same-version PySCF direct-call controls establish scoped wrapper consistency, not an independent-engine scientific certification. HOMO–LUMO gap is a diagnostic rather than a gate for this service. Preserve the original four results and twelve checks.

User DFT, ions, open-shell states, general optimization, scans and conditional-state comparisons are outside this entry. The historical `start-molecular-service.ps1` requires its own original candidate image and is not the new-installation launcher.
