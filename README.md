# AI4OrgChem Reproducible Runtime

Start with the [local Runtime entry guide](docs/LOCAL_RUNTIME_ENTRY_zh-CN.md): inspect capabilities, choose existing P01–P14 evidence and export a read-only review, or prepare a restricted user-molecule Check/Report request. `start-local-runtime.ps1` runs from host source. Catalogue entries do not implement P01–P13 recomputation; production user Compute remains BLOCKED. Git/project ZIP snapshots supply verifiable source, not a complete installed environment. No new image build, WSLc acceptance or public release is implied.

Latest [single-start candidate and zero-F preparation](docs/USER_MOLECULE_OCCUPIED_SPACE_ROOT_PREPARATION_20261007_zh-CN.md) passed 150 scoped engineering tests (40 new,110 regressions) and actual cached zero-F preparation, with zero new native F/NR/SCF. This version cannot authorize live root solving or reserve science callbacks; the live runner remains NOT_IMPLEMENTED / NOT_EXECUTED and Compute BLOCKED. Original rules,gates and numerical records remain.

Previous [twelve-point occupied-space response](docs/USER_MOLECULE_OCCUPIED_SPACE_RESPONSE_20261007_zh-CN.md): 129 scoped engineering tests and actual zero-F preparation passed; one new process completed 12 true F/NR evaluations and 8 same-D operator/energy subsets. Every point passes initial gap but fails commutator/raw-map checks; no qualified root, SCF or tail rechecks. Compute remains BLOCKED; the new twelve-slot budget is closed.

Previous [deterministic occupied-space seeds and fake admission](docs/USER_MOLECULE_OCCUPIED_SPACE_ADMISSION_20261007_zh-CN.md) prepared four array seeds and passed 97 scoped tests plus 12 synthetic callbacks, with 0 real F/SCF. At that increment the real-response and root-search workers were not implemented/executed; the real-response worker was subsequently executed in the separately recorded increment above. Original gates and Compute BLOCKED remain.

Previous [single-F response diagnostic](docs/USER_MOLECULE_OCCUPATION_RESPONSE_20261007_zh-CN.md): 101 targeted engineering tests and actual zero-F preparation passed. One new process completed three densities × three paths, nine true F/NR calls and zero SCF iterations. Six same-D operator subsets passed; every point failed the single-point predicate, with no qualified endpoint or Compute activation. The new nine-slot budget is closed without retry.

Earlier [strict-scope occupation diagnosis](docs/USER_MOLECULE_OCCUPATION_SCOPE_20261007_zh-CN.md) verifies two saved production operators and six frozen occupation witnesses. Changing occupation with the same frozen F cannot satisfy the original positive-gap gate. The existing operational scope is clarified; no new F/SCF/container ran and Compute remains BLOCKED. Its response proposal was subsequently implemented and executed in the separately recorded increment above.

Earlier [budget-aware recording engineering](docs/USER_MOLECULE_BUDGET_RECORDING_20261007_zh-CN.md): 122 targeted fake-array cases and three persisted synthetic examples passed. No real molecular F/SCF ran. The explicit engineering candidate preserves original gates and is not registered in the scientific worker; Compute remains BLOCKED.

Earlier [stored-matrix internal analysis](docs/USER_MOLECULE_SEED_V2_INTERNAL_ANALYSIS_20261007_zh-CN.md): the saved boundary contains a two-dimensional narrow π cluster with rank-one occupation; the reference returned its initial seed after a budget guard. Formal energy-derivative relations and recorded sample roles are clarified. No new F/SCF or container run occurred; Compute remains BLOCKED.

Earlier [seed-V2 implementation and diagnostic](docs/USER_MOLECULE_SEED_V2_DIAGNOSTIC_20261007_zh-CN.md): 239 targeted engineering cases and zero-F cached seed admission passed. One 591-F diagnostic took about 4.82 minutes; production mapped-occupation/positive-gap gates failed, and the reference final gate was not completed within budget. Original operators/thresholds remain; Compute is BLOCKED. This is not a repeated full CI or a rerun of old results.

External expert consultation, opinion collection and signatures are CANCELLED_BY_USER. Development follows [internal definition and validation](docs/USER_MOLECULE_INTERNAL_VALIDATION_zh-CN.md), without waiting for external responses. The three scientific questions remain internal work items. Existing numerical failures and resource gates remain; V2 is implemented and has undergone one bounded diagnostic; final qualification has not passed and Compute is disabled.

A [near-degeneracy V2 initialization draft](docs/USER_MOLECULE_NEAR_DEGENERACY_RULES_V2_zh-CN.md) now specifies a masked-metric reorthogonalization of the verified ordinary occupied space. Final global 2/0, Aufbau-map and positive-gap gates remain unchanged. Revision 0.2 records user-provided static feedback, existing per-path seed admission and UM-P12/UM-P13 aliases. MDR-002 revision 0.4 records implementation and the unqualified diagnostic; executed definition revision 0.3 is preserved byte for byte. Scientific interpretation remains pending and Compute is disabled. The former external review materials remain historical; their consultation process is cancelled.

The earlier [live admission and conditional initialization diagnostic](docs/USER_MOLECULE_RESIDUAL_LIVE_DIAGNOSTIC_20261006_zh-CN.md) executed once in a 1-GiB/one-CPU/no-swap process, reusing the old ordinary cache. Each of three paths evaluated F(D0) once and refused initialization: gaps near 1e-14 Hartree fail the unchanged 1e-6 guard. Orbital iteration did not start. A same-D0 operator/energy/prepared-mask subset passed; full T05 and qualified P12/P13/T06 comparisons are NOT_EXECUTED. Resource observations cover this preparation/initialization scope only. Research W07 and production Compute remain BLOCKED. Original records remain; a later label-only correction passed array regressions without repeating the real diagnostic or rebuilding the image.

[Fixed preparation, an independent reference and durable budgets](docs/USER_MOLECULE_PREPARATION_REFERENCE_20261006_zh-CN.md) are implemented, with 97 unique cases covered across verified source versions (72 new plus 25 resource regressions) and an actual mapping of the old ordinary cache using pinned PySCF. This is not a single complete CI run of 97 cases. That preparation round ran no real conditional calculation; the subsequent live diagnostic is recorded above; production Compute remains BLOCKED. Earlier [operator bridge](docs/USER_MOLECULE_RESIDUAL_BRIDGE_20261006_zh-CN.md), [array prototype](docs/USER_MOLECULE_RESIDUAL_PROTOTYPE_20261006_zh-CN.md) and failed records remain; previous complete CI does not certify these increments.

The [local W01–W07 engineering CI](docs/USER_MOLECULE_CI_W01_W07_20261006_zh-CN.md) passed 176 unique unit cases (284 executions), ten launcher actions, four platform probes and nine W07 host-report actions. Eighteen test containers were removed according to successful removal receipts; outputs remain. No new molecular calculation ran. Research Compute remains BLOCKED; human feedback is deferred by user, not a current engineering blocker. GitHub Actions remains NOT_EXECUTED.

Isolated branch update (2026-10-05): Check and Report work; production Compute remains **BLOCKED**. [Bounded W05–W06 molecular acceptance](docs/USER_MOLECULE_W05_W06_NUMERICAL_REVIEW_zh-CN.md) has now executed. Ordinary and same-density operator comparisons passed in their stated scope, but conditional stationarity, storage-path equivalence and full-reference gates failed. No qualified research result or formal W07 exit is claimed. The original workspaces and legacy L0–L4 evidence remain preserved.

[W05 preparation](docs/USER_MOLECULE_W05_PREPARATION_zh-CN.md) is a historical metadata-only batch. The earlier 84-test driver and four fixture bundles remain recorded. The latest [solver-v2 candidate](docs/USER_MOLECULE_SOLVER_V2_zh-CN.md) passed 122 guarded engineering tests and both same-density paths for pilot ethene, but all three conditional solves failed. Exact 1-GiB/one-CPU/no-swap bundle observations do not calibrate a general user resource model or grant method scope.

The earlier 2026-10-06 [stored-evidence method review](docs/USER_MOLECULE_METHOD_REVIEW_20261006_zh-CN.md) locates a narrow initial occupied-boundary spectrum, documents occupied-projector jumps and states the energy/operator stationarity criterion. No new molecular calculation or method approval is claimed. The [previous molecular solver design](docs/USER_MOLECULE_SOLVER_NEXT_DESIGN_zh-CN.md) remains historical. Preparation mapping, explicit candidate initialization, the independent reference and accounting are now implemented; the historical 900-second/1-GiB/603-slot proposal was followed by a separate live contract and one refused initialization diagnostic. Scientific scope approval remains pending. Research W07/Compute stays BLOCKED.

The earlier Report-only increment provides [host-only reporting and export](docs/USER_MOLECULE_REPORT_20261006_zh-CN.md), preserving existing runs, verifying saved bytes/identities and distinguishing numerical failure from non-execution and host failure. Its scoped 48 standard-library tests and eleven host report integrations passed. Basic mode verifies registered bytes and reads saved snapshots; advanced mode checks required evidence and exports derived reports. That increment started no molecular calculation, container or image build.

[W07 engineering trial](docs/USER_MOLECULE_W07_ENGINEERING_TRIAL_zh-CN.md) now provides a three-step input, Check and report/export workflow with a feedback template. One existing ethene fixture passed a real container Check followed by three host report actions; no SCF, grid, full ERI or Compute ran. This was an engineering demonstration, not an independent professional-user trial. External consultation is cancelled by the latest user instruction; internal definition and validation remain pending. Formal W07 and production Compute remain **BLOCKED**.

The [W07 agent-simulated selftest](docs/USER_MOLECULE_W07_SELFTEST_zh-CN.md) passed nine launcher scenarios (eight containers), six host protection/saved-failure scenarios and twelve host parser cases. Existing ethene/butadiene fixtures covered both profiles, refusal paths and report/export. Two Compute CLI calls tested refusal only; no new scientific calculation ran. Human trial and feedback are DEFERRED_BY_USER and optional future work, not a current engineering blocker. Scoped local engineering handoff is complete; research W07/production Compute remains BLOCKED. Simulation does not certify human UX or numerical qualification.

The local W07 source/evidence candidate also includes relocated Check and failed-result examples, source backups and a service-specific support/source matrix. Both examples were read successfully after relocation and from reconstructed runtime Git source. Scientific source extraction matched 591 locked files. The package excludes the Docker image and dependencies; full environment recovery and the r3 image's complete installed-component license audit remain NOT_EXECUTED. [Delivery scope](docs/USER_MOLECULE_W07_ENGINEERING_TRIAL_zh-CN.md#交付范围按需查阅) distinguishes these limits from legacy acceptance.

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
