# AI4OrgChem Reproducible Runtime

Isolated branch update (2026-10-05): Check and Report work; production Compute remains **BLOCKED**. [Bounded W05–W06 molecular acceptance](docs/USER_MOLECULE_W05_W06_NUMERICAL_REVIEW_zh-CN.md) has now executed. Ordinary and same-density operator comparisons passed in their stated scope, but conditional stationarity, storage-path equivalence and full-reference gates failed. No qualified research result or formal W07 exit is claimed. The original workspaces and legacy L0–L4 evidence remain preserved.

[W05 preparation](docs/USER_MOLECULE_W05_PREPARATION_zh-CN.md) is a historical metadata-only batch. The earlier 84-test driver and four fixture bundles remain recorded. The latest [solver-v2 candidate](docs/USER_MOLECULE_SOLVER_V2_zh-CN.md) passed 122 guarded engineering tests and both same-density paths for pilot ethene, but all three conditional solves failed. Exact 1-GiB/one-CPU/no-swap bundle observations do not calibrate a general user resource model or grant method scope.

The 2026-10-06 [stored-evidence method review](docs/USER_MOLECULE_METHOD_REVIEW_20261006_zh-CN.md) locates a narrow initial occupied-boundary spectrum, documents occupied-projector jumps and states the energy/operator stationarity criterion. No new molecular calculation or method approval is claimed. The [next solver design](docs/USER_MOLECULE_SOLVER_NEXT_DESIGN_zh-CN.md) is DESIGN_ONLY; W07/Compute remains BLOCKED.

[Local W01–W05 engineering/contract CI](docs/USER_MOLECULE_CI_20261005_zh-CN.md) passed 38 unit tests, 10 integration actions and four platform probes. GitHub Actions remains **NOT_EXECUTED**; W05 numerical acceptance remains blocked.

The earlier [full local W01–W06 engineering CI](docs/USER_MOLECULE_CI_W01_W06_20261005_zh-CN.md) passed 63 unique unit cases (102 executions), 10 Windows integration actions, three W06 service actions, four platform probes and seven PowerShell checks. It remains separate from the new numerical failures. GitHub Actions is NOT_EXECUTED; WSLc is BLOCKED/paused.

[W06 engineering](docs/USER_MOLECULE_W06_ENGINEERING_zh-CN.md) and the new independent molecular bridge run from read-only committed-source mounts over the existing r3 image; they are not baked into it. [SCF/method review questions](docs/USER_MOLECULE_SCF_REVIEW_REQUEST_zh-CN.md) identify the remaining scientific decisions. No image was rebuilt or published.

Delivery review (2026-10-03): local Docker L0–L4, equivalence and scoped joint classification are verified. WSLc is **BLOCKED / NOT_EXECUTED**. CI is **statically reviewed; execution NOT_EXECUTED**. **Image distribution is BLOCKED; source-only publication requires separate confirmation.** Apache-2.0 covers runtime-owned code, not every image component. See [final review](validation/DELIVERY_REVIEW_2026-10-03_zh-CN.md) and [license review](docs/LICENSE_REVIEW_zh-CN.md).

[中文说明](README_zh-CN.md)

An Apache-2.0 CPU runtime wrapper around the unchanged, commit-pinned AI4OrgChem public software and protocols. Source: `v0.3.2`, commit `28511f3d84fa65707a107cde1e8121a7b4334ecb`.

Development candidate only; no image or release has been published. L0 evidence checks, L1 core tests and L2 technical smoke have passed in a separate WSL2 candidate environment. The local Docker candidate passed L0–L2, STO-3G equivalence, non-root/read-only source checks, exit-code checks and output retention after deletion. L0–L2, equivalence and specified acceptance probes were verified with networking disabled; strict network isolation for L3/L4 is **NOT_EXECUTED**. WSLc remains **BLOCKED / NOT_EXECUTED**. These technical passes do not certify scientific conclusions.

The repository includes source and wheel hash locks, an OCI Dockerfile, task wrappers, persistent manifests/logs/checkpoints, candidate PowerShell launchers, and target-host acceptance scripts. See the [Chinese run guide](docs/RUN_zh-CN.md), [source audit](docs/SOURCE_AUDIT_zh-CN.md), [compatibility matrix](docs/WSLC_COMPATIBILITY_zh-CN.md), and [actual validation report](validation/REPORT_2026-10-02_zh-CN.md).

Builds need network access. Task execution requires no installation, Git update, model API, monograph text or credentials. Local Docker L3/L4 and four-run joint classification have now passed under the fixed C12H6 protocol; these results do not establish WSLc support or a universal scientific claim. The upstream five-parameter optimizer writes checkpoints but offers no resume interface. See the [local delivery guide](docs/LOCAL_DELIVERY_zh-CN.md) for the PowerShell 5.1 bootstrap, measured results and backup/restore workflow.

## Build and run locally with Docker

In a clean runtime checkout, use PowerShell 7.3+ with an available Docker Linux/amd64 engine. Builds require network access; no published image is required:

```powershell
./scripts/build-wslc.ps1 -Engine docker -Tag ai4orgchem-runtime:local-source-candidate
./scripts/run-wslc.ps1 -Engine docker -Task evidence -Image ai4orgchem-runtime:local-source-candidate -OutputRoot 'D:\AI4Science\ai4orgchem-runtime-runs\source-review'
```

The build script supports Docker despite its filename. A new build has a new runtime/image identity; historical acceptance results apply to the recorded candidate and do not automatically certify a newly built image. The normal launcher does not enforce network isolation. For the previously verified local image, the PowerShell 5.1 bootstrap is `./scripts/start-runtime.ps1 -Task evidence`.

## Unverified WSLc candidate adaptation

WSL upgrade and WSLc acceptance are paused on this host. These commands describe candidate interfaces and are not a currently validated execution path:

```powershell
./scripts/probe-wslc.ps1 -OutputDirectory D:\AI4Science\ai4orgchem-runtime-runs\platform-probe
./scripts/build-wslc.ps1 -Tag ai4orgchem-runtime:candidate
./scripts/run-wslc.ps1 -Task evidence -Image ai4orgchem-runtime:candidate
```

Pushing to an authorized repository will trigger the current CI workflow, which builds/tests and uploads execution evidence with seven-day retention. Those logs/artifacts belong in the publication review scope; the workflow does not push images, create formal tags or publish Releases. CI execution remains NOT_EXECUTED.

Third-party notice materials and outstanding corresponding-source requirements: [source delivery plan](docs/CORRESPONDING_SOURCE_zh-CN.md), [material verification](validation/license-materials-review.json). Supplemental notices do not certify binary/source correspondence; **image distribution remains BLOCKED; source-only publication requires separate confirmation**.


Source-only publication and image distribution are assessed separately: [publication boundaries and local candidate](docs/PUBLICATION_BOUNDARIES_zh-CN.md). Native wheel provenance remains unresolved; neither publication action has been performed.

Professional review documentation (Chinese): [S1–S6 services and task mapping](docs/PROFESSIONAL_SERVICES_zh-CN.md), [result interpretation](docs/REVIEW_RESULTS_zh-CN.md), [three user paths](docs/USER_PATHS_zh-CN.md), and [historical Docker example](docs/examples/P14_REVIEW_20261002_zh-CN.md). The [review report](docs/templates/REVIEW_REPORT_zh-CN.md) and [feedback](docs/templates/FEEDBACK_zh-CN.md) templates are filled manually. An automatic summarizer is not implemented; the seven task IDs are unchanged. This documentation supplement requires separate publication-scope review from the previous `2460eef` candidate.
