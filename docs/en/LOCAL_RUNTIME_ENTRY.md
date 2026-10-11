[English guide](USER_GUIDE.md) · [English README](../../README.md) · [Chinese counterpart](../../docs/LOCAL_RUNTIME_ENTRY_zh-CN.md)

# Local Runtime entry points

Choose by your input and research goal, not by a proposition number. The first user-XYZ ordinary RHF service is available in its [documented small-system scope](CURRENT_MOLECULAR_SINGLE_POINT.md). General optimization/scans and user conditional Compute are not delivered. The website is guidance only; operations run locally.

## Your molecule or a fixed example

Follow [source installation](SOURCE_INSTALLATION.md) and use the same installation record with the [ordinary RHF](CURRENT_MOLECULAR_SINGLE_POINT.md), [fixed example](CURRENT_REGISTERED_CASES.md), [protocol](CURRENT_PROTOCOL_CASES.md) or [high-cost](CURRENT_HIGH_COST_CASES.md) guide. Ordinary successful completion requires host/worker closure, the twelve numerical checks, resources and retained outputs, not just a report file. Host commands use existing Python 3.12+ and Docker; they do not install these tools automatically.

## Optional: read frozen evidence

From the repository root in PowerShell, the host navigation entry supports Windows PowerShell 5.1. Selected-file reading needs existing Python 3.12+. Legacy Check/Report uses existing PowerShell 7.3+.

```powershell
./scripts/start-local-runtime.ps1 -Action Capabilities
./scripts/start-local-runtime.ps1 -Action List
./scripts/start-local-runtime.ps1 -Action Show -Proposition P01
```

Without a source directory, Show reports missing sources and returns 20. It still presents protocol/evidence/status navigation; it does not download scientific sources.

```powershell
$scienceSource='D:\your-work\science-v0.3.2'
$reviewOutput='D:\your-work\reviews\p01-new'
./scripts/start-local-runtime.ps1 -Action Review -Proposition P01 `
  -SourceDirectory $scienceSource -OutputDirectory $reviewOutput
```

Review writes `review.json` and `summary.md` to a new directory outside the source. It compares selected evidence bytes against the frozen `v0.3.2` / `28511f3d84fa65707a107cde1e8121a7b4334ecb` source lock, not all 588 files and not energy arithmetic or rerun results. Exit0 means selected bytes match, 20 means missing materials, and 40 means invalid paths, identities or tampering/refusal. Add `-Json` for machine output. Four historical P14 processed JSON files contain nonstandard `Infinity`; retained raw text alone is not standard-JSON numerical qualification. P01–P13 evidence navigation is not a recalculation entry.

## Optional: legacy conditional-request Check/Report

```powershell
./scripts/start-local-runtime.ps1 -Action Check `
  -Request 'D:\your-work\request.json' -OutputRoot 'D:\your-work\check-runs'
./scripts/start-local-runtime.ps1 -Action Report -RunDirectory 'D:\your-work\check-runs\one-run'
./scripts/start-local-runtime.ps1 -Action Report -RunDirectory 'D:\your-work\check-runs\one-run' `
  -PythonExecutable 'C:\your-python\python.exe' `
  -ReportExportDirectory 'D:\your-work\exports\one-new'
```

Check uses its own original conditional-request schema/profile, not the ordinary-water request. The default is an existing r3 image ID; another image requires explicit `-Image` and its original identity checks. It checks input/AO metadata, not SCF, grid or full ERI. Its two profiles require declared C/H, closed-shell, planar, two-fragment inputs, without automatic reorientation, added hydrogens or atom reordering. Passing Check does not enable Compute. Report reads existing compatible service records; it is not a universal reader for all original results/native-root diagnostics. An advanced export goes into a new directory and cannot overwrite the source run.

## Source and platform checks

The original source-preparation/build entry checks clean Git or verified installer-produced context, exact identities, path traversal/reparse points and allowed PS1 newline transformations. It does not invent `.git`. Keep existing workspaces unchanged; use a fresh clone if non-PS1 working bytes differ from their Git blobs solely through CRLF.

```powershell
./scripts/build-docker.ps1 -CheckOnly
```

PowerShell 7.3+ is needed for this old build preflight. It prepares the original `container/Dockerfile` identity, not the new molecule image, science archive or wheels. It does not contact the engine or prove that an OCI build succeeded. Optional `-ExpectedRuntimeCommit`, and prepared-context `-ExpectedManifestSha256`, enforce expected identities; they do not authenticate a publisher. Removing CheckOnly is a separate actual build requiring its own acceptance.

Source/static guide are public. Images remain undistributed. Native WSL2 has recorded Check only and no native Compute qualification. External expert consultation is cancelled. The [service matrix](CURRENT_PROFESSIONAL_SERVICES.md) distinguishes recorded engineering CI and historical scientific acceptance from the unqualified conditional endpoint.
