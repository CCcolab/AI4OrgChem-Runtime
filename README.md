# AI4OrgChem Local Molecular Calculation Runtime

[中文说明](README_zh-CN.md)

**Version v0.1.0** · [Release and downloads](docs/en/DOWNLOADS.md) · [release scope](docs/en/RELEASE_v0.1.0.md) · [authors and acknowledgements](docs/en/AUTHORS.md). Source and guide only; no prebuilt image or bundled environment.

**[Open the Runtime user guide](https://cccolab.github.io/AI4OrgChem-Runtime/en/)**

**Author and maintainer:** [Xiao Chen / CCcolab](https://github.com/CCcolab). **AI-assisted engineering contributor: OpenAI Codex** — Runtime implementation, input and resource checks, engineering tests, evidence records, documentation and guide maintenance, under the maintainer's direction. See [contributions and acknowledgements](docs/en/AUTHORS.md#codex-contributions).

## Purpose and goals

AI4OrgChem Runtime helps you run molecular calculations on your own computer and review the project's registered research examples. It packages fixed scientific sources and dependencies, checks inputs, and saves inputs, logs and results together so calculations can be traced and reviewed.

The goal is to make it easier to obtain single-point energies, inspect orbitals and density matrices, and reproduce specified energy and structure comparisons. The online guide helps you choose a module and prepare a command; calculations run in your local Runtime.

## Agent Skills

[Browse 15 calculation and review Skills](skills/README.md) · [Install and invoke](skills/USAGE.md) · [Local tests and limitations](skills/TESTING.md).

Use an Agent with your existing backend to prepare inputs, analyze tables/matrices, review energy and structural records, or navigate registered Runtime services. Skills are instruction-only and can be installed individually; they do not include a chemistry engine or expand Runtime's accepted computational scope. This post-v0.1.0 source addition is obtained from the branch/commit containing `skills/`, not the immutable v0.1.0 assets or guide ZIP.

## Calculate your own molecule

| Module | Input | Results and supported scope |
| --- | --- | --- |
| [RHF single-point energy, orbitals and density](docs/en/CURRENT_MOLECULAR_SINGLE_POINT.md) | Your own XYZ structure and request file | RHF/6-31G(d) energy, canonical orbitals and spin-summed AO density matrix. H/C/N/O, neutral closed-shell singlets, at most 20 atoms and 80 atomic orbitals. |

This is the current entry for your own molecule. DFT, ions, open-shell states, geometry optimization, scans and conditional-state comparisons for user-supplied molecules require further development and validation.

## Review fixed research protocols

The following modules use registered molecules, geometries, tables and method settings. They are fixed-case calculations or saved-result reviews; their inputs cannot be replaced with your own XYZ.

Choose a module by its research goal and input scope. Each usage guide explains that module’s inputs, execution steps and results; you do not need to choose a guide category.

| Module | What you can calculate or review | Usage guide |
| --- | --- | --- |
| Orbital representation and density comparison | Fixed ethene orbital rotations; compare density and energy invariants. | [Usage guide](docs/en/CURRENT_REGISTERED_CASES.md) |
| Structure and spectrum table statistics | Statistics and regression from frozen published tables; produces no new spectrum. | [Usage guide](docs/en/CURRENT_REGISTERED_CASES.md) |
| Torsion endpoints and energy ledger | Review saved torsion endpoints and run a single point at the registered frozen geometry. | [Usage guide](docs/en/CURRENT_PROTOCOL_CASES.md) |
| π–π conditional states and orbital response | Compare the direct term and orbital response of two fixed conditional states. | [Usage guide](docs/en/CURRENT_PROTOCOL_CASES.md) |
| π–σ conditional-energy comparison | Compare saved angle records and calculate the registered fixed-angle conditional-energy point. | [Usage guide](docs/en/CURRENT_PROTOCOL_CASES.md) |
| Fragment conditional-energy assembly | Independently assemble the energy of a fixed two-fragment σ–σ conditional state. | [Usage guide](docs/en/CURRENT_PROTOCOL_CASES.md) |
| Energy-ledger closure checks | Check saved energy ledgers under the same Hamiltonian; runs no new quantum calculation. | [Usage guide](docs/en/CURRENT_PROTOCOL_CASES.md) |
| Localized endpoints and reference energies | Fixed butadiene localization endpoints and reference thermochemistry; fixed-geometry calculations. | [Usage guide](docs/en/CURRENT_PROTOCOL_CASES.md) |
| Conditional-state and stability diagnostics | Conditional-state and stability diagnostics at the fixed cyclobutadiene geometry. | [Usage guide](docs/en/CURRENT_PROTOCOL_CASES.md) |
| Bond-length alternation and energy response | Ordinary DFT energy response at five fixed benzene geometries. | [Usage guide](docs/en/CURRENT_PROTOCOL_CASES.md) |
| Constrained multistate geometry optimization | 17 registered fixed states; only the benzene G pilot has completed acceptance. | [Usage guide](docs/en/CURRENT_HIGH_COST_CASES.md) |
| Cyclic-system size and state comparison | 61 registered fixed states; only the N12-G pilot has completed acceptance. | [Usage guide](docs/en/CURRENT_HIGH_COST_CASES.md) |
| Conjugated graph rules and energy ledger | Fixed graph cases and ESE/CESE arithmetic ledgers; produces no new quantum energies. | [Usage guide](docs/en/CURRENT_REGISTERED_CASES.md) |
| Conditional-energy and structure-response review | Fixed-protocol energy and constrained-geometry calculations, implementation comparisons and joint review. | [Usage guide](docs/en/CURRENT_P14_BUILD_RUN.md) |

The two high-cost modules list 78 states in total; the two accepted pilots do not establish acceptance of the remaining states or complete multistate results. Each module's guide states its input, method, resource and result boundaries. Saved-ledger arithmetic and a new molecular calculation are separate operations.

## Start in three steps

1. **Prepare a local Runtime.** Follow the [source installation guide](docs/en/SOURCE_INSTALLATION.md) to prepare, build and register a local Docker environment. Source is public; the project does not provide a prebuilt public image. A new installation keeps its own validation records.
2. **Choose your input and module.** Use the [molecular single-point guide](docs/en/CURRENT_MOLECULAR_SINGLE_POINT.md) for your XYZ, or the [local entry guide](docs/en/LOCAL_RUNTIME_ENTRY.md) and fixed-protocol guides above for registered examples.
3. **Run and read the result.** Follow your module's command, retain the generated run directory, and use the [current service matrix](docs/en/CURRENT_PROFESSIONAL_SERVICES.md), the result section in your module guide and the [service review template](docs/en/CURRENT_SERVICE_REVIEW.md) to interpret its scope and checks.

For component licenses and distribution conditions, see the [license review](docs/en/LICENSE_REVIEW.md) and [publication boundaries](docs/en/PUBLICATION_BOUNDARIES.md). Detailed development and historical validation records remain available below.

<!-- CURRENT_CAPABILITIES_START -->
See the [current professional service matrix](docs/en/CURRENT_PROFESSIONAL_SERVICES.md) for inputs, methods, recorded acceptance, cost and interpretation; the [current capability registry](configs/runtime-capabilities-v2.json) is the machine-readable declaration.

[2 CI jobs succeeded for be51dcbb](https://github.com/CCcolab/AI4OrgChem-Runtime/actions/runs/38036972441); this records engineering contracts and legacy L0/L1, not acceptance of later changes or all scientific services.
<!-- CURRENT_CAPABILITIES_END -->

Runtime development tests are retained locally and excluded from the current public tree and installation package. Public CI now covers source installation, container permissions/exit codes/output persistence and legacy L0/L1; Runtime unit suites are no longer executed in public CI. Prior passing records retain their original commits and scope. See [test distribution scope](docs/en/TEST_DISTRIBUTION.md).


<details>
<summary>Development, support and historical validation records / 开发、支持与历史验证记录</summary>

**[Open the Runtime user guide](https://cccolab.github.io/AI4OrgChem-Runtime/en/)** — a static website you can read directly, without Docker or WSL. Copy calculation commands for execution in your own local Runtime; the website does not run molecular calculations. See the [Pages deployment record](docs/en/HISTORICAL_RECORDS.md#github-pages-guide-20261010).

Source and the supplied web guide have been publicly synchronized to [CCcolab/AI4OrgChem-Runtime](https://github.com/CCcolab/AI4OrgChem-Runtime) under the owner's authorization. The first push of `06d50885bdccf31f83b89229c1513121542375d5` completed [GitHub Actions run 37933616122](https://github.com/CCcolab/AI4OrgChem-Runtime/actions/runs/37933616122): all three scoped jobs succeeded. See the [public synchronization record](docs/en/HISTORICAL_RECORDS.md#github-public-sync-20261009); this does not certify all scientific services or release an image. GitHub Pages static-guide hosting is enabled as of 2026-10-10; no online calculation, new version number, tag or Release is provided.

The [online browser guide](https://cccolab.github.io/AI4OrgChem-Runtime/en/) is hosted through GitHub Pages from `main` / `docs`; the [HTML source](docs/index.html) remains available for local use. Its [import and maintenance record](docs/en/HISTORICAL_RECORDS.md#runtime-web-guide) preserves the original package and validation scope. Website publication does not distribute a container image or constitute a complete software Release.

Source installation now has a separate [prepare/build/identity-registration guide](docs/en/SOURCE_INSTALLATION.md). It uses a public pinned base, public locked dependencies and a reconstructed frozen scientific source tree; newly built images receive independent installation records and do not inherit historical scientific PASS. Use a Git clone or the installer-produced source ZIP. [Clean-directory acceptance](docs/en/HISTORICAL_RECORDS.md#source-installation-acceptance-20261009) passed public preparation/build, four service registrations, 45 engineering tests and four bounded tasks. High-cost scientific replay and fresh-machine acceptance were NOT_EXECUTED; historical candidates below remain separately identified.

Reading GitHub, the guide or saved results requires no running WSL2 or Docker. Local calculations require the selected backend. Current scientific acceptance mainly applies to identified Docker candidates. The [ordinary native WSL2 entry](docs/en/NATIVE_WSL2_RUNTIME.md) passed read-only Check; native Compute is not implemented or accepted. Ordinary native WSL2 Check does not grant Docker scientific qualification. Docker can be closed when unused; stored images do not need to run.

2026-10-09 maintenance: the [Docker startup safeguard](docs/en/HISTORICAL_RECORDS.md#docker-startup-recovery-20261009) passed three scoped restarts and active-work refusal. The [actual component license addendum](docs/en/HISTORICAL_RECORDS.md#high-cost-components-20261009) preserves image distribution as BLOCKED_LOCAL_ONLY. Accepted P12-N12-G remains PASS without recomputation or repeated memory admission. The old uniform 15-GiB Docker gate is not a daily user requirement; [memory-tier candidates](docs/en/HISTORICAL_RECORDS.md#p12-resource-tiers-candidate) remain disabled. Current scoped remote CI and source publication records are separate from historical validation.

The product goal is a local chemistry calculation platform for user-provided molecules, organized by input checks, single-point energies, orbital/density analysis and geometry tasks. Users need not understand the monograph's P01–P14 IDs; those remain in examples, validation and provenance details. See the [general molecular entry design](docs/en/HISTORICAL_RECORDS.md#general-chemistry-entry-design). The first ordinary user-molecule RHF single-point service is implemented and locally accepted, with canonical orbitals and spin-summed AO density export. Its profile supports H/C/N/O, neutral singlets, RHF/6-31G(d), up to20 atoms and actual AO count≤80. Three-dimensional structures require no P identifier or project-specific fragments. DFT, open-shell calculations, general optimization, scans and grid density remain separate future work.

For your own molecule, follow the [four-step guide](docs/en/CURRENT_MOLECULAR_SINGLE_POINT.md) and use `scripts/run-installed-runtime.py` with your molecular-service installation record and XYZ/request. The following acceptance refers to the historical candidate, not your new installation: four molecular executions and same-version PySCF direct-call comparisons passed;114 guarded engineering tests passed in the locked candidate. Non-root operation, read-only source/input, network isolation, exit codes and output retention after container removal were checked. See the [acceptance report](docs/en/HISTORICAL_RECORDS.md#molecular-single-point-acceptance-20261008) and [machine record](validation/molecular-service/deployment-20261008.public.json). The same-library comparison is not independent scientific-engine certification; wavefunction stability was NOT_EXECUTED.

For examples and historical review, use the [local entry guide](docs/en/LOCAL_RUNTIME_ENTRY.md): read existing P01–P14 evidence, use restricted Check/Report, or run three new [fixed registered controls](docs/en/CURRENT_REGISTERED_CASES.md): P02 frozen-table statistics, P13 graph rules and energy-ledger arithmetic, and one small ethene P01 occupied-representation control. Their source lock, local image and actual acceptance records are separate from prior P14 images; see [deployment boundaries](docs/en/HISTORICAL_RECORDS.md#registered-cases-deployment-boundaries). The legacy user-molecule conditional-state Compute remains BLOCKED, separately from the new ordinary single-point service. Git/project ZIP supply verifiable source, not an installed environment. Image distribution and source publication retain separate status records.

The dated records below preserve their historical engineering, conditional-state and original seven-task scope. Their GitHub CI NOT_EXECUTED and pending-publication statements describe the status at the recorded dates; the actual first public push and successful scoped Actions run are recorded above. Their Compute BLOCKED statements concern the legacy conditional-state comparison, rather than the new scoped ordinary RHF entry.

[2026-10-07 cooperative-stop engineering](docs/en/HISTORICAL_RECORDS.md#user-molecule-native-shutdown-engineering-20261007):154 scoped engineering regressions passed; two zero-native stop cases saved closed receipts, while a forced-kill negative case retains unknown final evidence. Three timings per segment do not qualify real solver capacity. That 2026-10-07 increment ran no new science/budget; old139-call OPEN records remain preserved without retry. Compute remains BLOCKED.

[Previous framework acceptance](docs/en/HISTORICAL_RECORDS.md#local-runtime-framework-20261007):231 unique engineering tests,22 PowerShell processes and12 source/preflight checks passed; no science budget at that increment. GitHub CI execution remains NOT_EXECUTED.

[Latest one native root diagnosis](docs/en/HISTORICAL_RECORDS.md#user-molecule-root-native-diagnostic-20261007):139NR completions,138successful callbacks and1deadline failure;279.031s through cleanup. First96-sample Jacobian completed, second partial; no normal root/tails, raw OPEN journal preserved, no retry, Compute BLOCKED.

[Previous native root candidate engineering](docs/en/HISTORICAL_RECORDS.md#user-molecule-root-native-engineering-20261007):108 scoped engineering cases and actual29-guard cached zero-F preparation passed. At that increment root solving was NOT_EXECUTED and no science budget was reserved; the subsequent one-run attempt is recorded above. Compute remains BLOCKED; no image rebuild.

Previous `7530595` [single-start candidate and zero-F preparation](docs/en/HISTORICAL_RECORDS.md#user-molecule-occupied-space-root-preparation-20261007) passed 150 scoped engineering tests (40 new,110 regressions) and actual cached zero-F preparation, with zero new native F/NR/SCF. That historical version could not authorize live root solving or reserve a science budget; its runner was NOT_IMPLEMENTED / NOT_EXECUTED. The subsequent attempt is recorded above; no additional/reusable retry budget is authorized and Compute remains BLOCKED. Original rules,gates and numerical records remain.

Previous [twelve-point occupied-space response](docs/en/HISTORICAL_RECORDS.md#user-molecule-occupied-space-response-20261007): 129 scoped engineering tests and actual zero-F preparation passed; one new process completed 12 true F/NR evaluations and 8 same-D operator/energy subsets. Every point passes initial gap but fails commutator/raw-map checks; no qualified root, SCF or tail rechecks. Compute remains BLOCKED; the new twelve-slot budget is closed.

Previous [deterministic occupied-space seeds and fake admission](docs/en/HISTORICAL_RECORDS.md#user-molecule-occupied-space-admission-20261007) prepared four array seeds and passed 97 scoped tests plus 12 synthetic callbacks, with 0 real F/SCF. At that increment the real-response and root-search workers were not implemented/executed; the real-response worker was subsequently executed in the separately recorded increment above. Original gates and Compute BLOCKED remain.

Previous [single-F response diagnostic](docs/en/HISTORICAL_RECORDS.md#user-molecule-occupation-response-20261007): 101 targeted engineering tests and actual zero-F preparation passed. One new process completed three densities × three paths, nine true F/NR calls and zero SCF iterations. Six same-D operator subsets passed; every point failed the single-point predicate, with no qualified endpoint or Compute activation. The new nine-slot budget is closed without retry.

Earlier [strict-scope occupation diagnosis](docs/en/HISTORICAL_RECORDS.md#user-molecule-occupation-scope-20261007) verifies two saved production operators and six frozen occupation witnesses. Changing occupation with the same frozen F cannot satisfy the original positive-gap gate. The existing operational scope is clarified; no new F/SCF/container ran and Compute remains BLOCKED. Its response proposal was subsequently implemented and executed in the separately recorded increment above.

Earlier [budget-aware recording engineering](docs/en/HISTORICAL_RECORDS.md#user-molecule-budget-recording-20261007): 122 targeted fake-array cases and three persisted synthetic examples passed. No real molecular F/SCF ran. The explicit engineering candidate preserves original gates and is not registered in the scientific worker; Compute remains BLOCKED.

Earlier [stored-matrix internal analysis](docs/en/HISTORICAL_RECORDS.md#user-molecule-seed-v2-internal-analysis-20261007): the saved boundary contains a two-dimensional narrow π cluster with rank-one occupation; the reference returned its initial seed after a budget guard. Formal energy-derivative relations and recorded sample roles are clarified. No new F/SCF or container run occurred; Compute remains BLOCKED.

Earlier [seed-V2 implementation and diagnostic](docs/en/HISTORICAL_RECORDS.md#user-molecule-seed-v2-diagnostic-20261007): 239 targeted engineering cases and zero-F cached seed admission passed. One 591-F diagnostic took about 4.82 minutes; production mapped-occupation/positive-gap gates failed, and the reference final gate was not completed within budget. Original operators/thresholds remain; Compute is BLOCKED. This is not a repeated full CI or a rerun of old results.

External expert consultation, opinion collection and signatures are CANCELLED_BY_USER. Development follows [internal definition and validation](docs/en/HISTORICAL_RECORDS.md#user-molecule-internal-validation), without waiting for external responses. The three scientific questions remain internal work items. Existing numerical failures and resource gates remain; V2 is implemented and has undergone one bounded diagnostic; final qualification has not passed and Compute is disabled.

A [near-degeneracy V2 initialization draft](docs/en/HISTORICAL_RECORDS.md#user-molecule-near-degeneracy-rules-v2) now specifies a masked-metric reorthogonalization of the verified ordinary occupied space. Final global 2/0, Aufbau-map and positive-gap gates remain unchanged. Revision 0.2 records user-provided static feedback, existing per-path seed admission and UM-P12/UM-P13 aliases. MDR-002 revision 0.4 records implementation and the unqualified diagnostic; executed definition revision 0.3 is preserved byte for byte. Scientific interpretation remains pending and Compute is disabled. The former external review materials remain historical; their consultation process is cancelled.

The earlier [live admission and conditional initialization diagnostic](docs/en/HISTORICAL_RECORDS.md#user-molecule-residual-live-diagnostic-20261006) executed once in a 1-GiB/one-CPU/no-swap process, reusing the old ordinary cache. Each of three paths evaluated F(D0) once and refused initialization: gaps near 1e-14 Hartree fail the unchanged 1e-6 guard. Orbital iteration did not start. A same-D0 operator/energy/prepared-mask subset passed; full T05 and qualified user-molecule UM-P12/UM-P13/T06 comparisons are NOT_EXECUTED (historical machine keys remain P12/P13). Resource observations cover this preparation/initialization scope only. Research W07 and production Compute remain BLOCKED. Original records remain; a later label-only correction passed array regressions without repeating the real diagnostic or rebuilding the image.

[Fixed preparation, an independent reference and durable budgets](docs/en/HISTORICAL_RECORDS.md#user-molecule-preparation-reference-20261006) are implemented, with 97 unique cases covered across verified source versions (72 new plus 25 resource regressions) and an actual mapping of the old ordinary cache using pinned PySCF. This is not a single complete CI run of 97 cases. That preparation round ran no real conditional calculation; the subsequent live diagnostic is recorded above; production Compute remains BLOCKED. Earlier [operator bridge](docs/en/HISTORICAL_RECORDS.md#user-molecule-residual-bridge-20261006), [array prototype](docs/en/HISTORICAL_RECORDS.md#user-molecule-residual-prototype-20261006) and failed records remain; previous complete CI does not certify these increments.

The [local W01–W07 engineering CI](docs/en/HISTORICAL_RECORDS.md#user-molecule-ci-w01-w07-20261006) passed 176 unique unit cases (284 executions), ten launcher actions, four platform probes and nine W07 host-report actions. Eighteen test containers were removed according to successful removal receipts; outputs remain. No new molecular calculation ran. Research Compute remains BLOCKED; human feedback is deferred by user, not a current engineering blocker. GitHub Actions remains NOT_EXECUTED.

Isolated branch update (2026-10-05): Check and Report work; production Compute remains **BLOCKED**. [Bounded W05–W06 molecular acceptance](docs/en/HISTORICAL_RECORDS.md#user-molecule-w05-w06-numerical-review) has now executed. Ordinary and same-density operator comparisons passed in their stated scope, but conditional stationarity, storage-path equivalence and full-reference gates failed. No qualified research result or formal W07 exit is claimed. The original workspaces and legacy L0–L4 evidence remain preserved.

[W05 preparation](docs/en/HISTORICAL_RECORDS.md#user-molecule-w05-preparation) is a historical metadata-only batch. The earlier 84-test driver and four fixture bundles remain recorded. The latest [solver-v2 candidate](docs/en/HISTORICAL_RECORDS.md#user-molecule-solver-v2) passed 122 guarded engineering tests and both same-density paths for pilot ethene, but all three conditional solves failed. Exact 1-GiB/one-CPU/no-swap bundle observations do not calibrate a general user resource model or grant method scope.

The earlier 2026-10-06 [stored-evidence method review](docs/en/HISTORICAL_RECORDS.md#user-molecule-method-review-20261006) locates a narrow initial occupied-boundary spectrum, documents occupied-projector jumps and states the energy/operator stationarity criterion. No new molecular calculation or method approval is claimed. The [previous molecular solver design](docs/en/HISTORICAL_RECORDS.md#user-molecule-solver-next-design) remains historical. Preparation mapping, explicit candidate initialization, the independent reference and accounting are now implemented; the historical 900-second/1-GiB/603-slot proposal was followed by a separate live contract and one refused initialization diagnostic. Scientific scope approval remains pending. Research W07/Compute stays BLOCKED.

The earlier Report-only increment provides [host-only reporting and export](docs/en/HISTORICAL_RECORDS.md#user-molecule-report-20261006), preserving existing runs, verifying saved bytes/identities and distinguishing numerical failure from non-execution and host failure. Its scoped 48 standard-library tests and eleven host report integrations passed. Basic mode verifies registered bytes and reads saved snapshots; advanced mode checks required evidence and exports derived reports. That increment started no molecular calculation, container or image build.

[W07 engineering trial](docs/en/HISTORICAL_RECORDS.md#user-molecule-w07-engineering-trial) now provides a three-step input, Check and report/export workflow with a feedback template. One existing ethene fixture passed a real container Check followed by three host report actions; no SCF, grid, full ERI or Compute ran. This was an engineering demonstration, not an independent professional-user trial. External consultation is cancelled by the latest user instruction; internal definition and validation remain pending. Formal W07 and production Compute remain **BLOCKED**.

The [W07 agent-simulated selftest](docs/en/HISTORICAL_RECORDS.md#user-molecule-w07-selftest) passed nine launcher scenarios (eight containers), six host protection/saved-failure scenarios and twelve host parser cases. Existing ethene/butadiene fixtures covered both profiles, refusal paths and report/export. Two Compute CLI calls tested refusal only; no new scientific calculation ran. Human trial and feedback are DEFERRED_BY_USER and optional future work, not a current engineering blocker. Scoped local engineering handoff is complete; research W07/production Compute remains BLOCKED. Simulation does not certify human UX or numerical qualification.

The local W07 source/evidence candidate also includes relocated Check and failed-result examples, source backups and a service-specific support/source matrix. Both examples were read successfully after relocation and from reconstructed runtime Git source. Scientific source extraction matched 591 locked files. The package excludes the Docker image and dependencies; full environment recovery and the r3 image's complete installed-component license audit remain NOT_EXECUTED. [Delivery scope](docs/en/HISTORICAL_RECORDS.md#user-molecule-w07-engineering-trial) distinguishes these limits from legacy acceptance.

[Local W01–W05 engineering/contract CI](docs/en/HISTORICAL_RECORDS.md#user-molecule-ci-20261005) passed 38 unit tests, 10 integration actions and four platform probes. GitHub Actions remains **NOT_EXECUTED**; W05 numerical acceptance remains blocked.

The earlier [full local W01–W06 engineering CI](docs/en/HISTORICAL_RECORDS.md#user-molecule-ci-w01-w06-20261005) passed 63 unique unit cases (102 executions), 10 Windows integration actions, three W06 service actions, four platform probes and seven PowerShell checks. It remains separate from the new numerical failures. The GitHub Actions non-execution statement belongs to this earlier local record; current remote runs are recorded above.

[W06 engineering](docs/en/HISTORICAL_RECORDS.md#user-molecule-w06-engineering) and the new independent molecular bridge run from read-only committed-source mounts over the existing r3 image; they are not baked into it. [SCF/method review questions](docs/en/HISTORICAL_RECORDS.md#user-molecule-scf-review-request) identify the remaining scientific decisions. No image was rebuilt or published.

Delivery review (2026-10-03): local Docker L0–L4, equivalence and scoped joint classification are verified. GitHub Actions is **statically reviewed; execution NOT_EXECUTED**; later local engineering CI runs have separate records. **Image distribution is BLOCKED; source-only publication requires separate confirmation.** Apache-2.0 covers runtime-owned code, not every image component. See [final review](docs/en/HISTORICAL_RECORDS.md#delivery-review-2026-10-03) and [license review](docs/en/LICENSE_REVIEW.md).

An Apache-2.0 CPU runtime wrapper around the unchanged, commit-pinned AI4OrgChem public software and protocols. Source: `v0.3.2`, commit `28511f3d84fa65707a107cde1e8121a7b4334ecb`.

Development candidate only; no image or release has been published. L0 evidence checks, L1 core tests and L2 technical smoke have passed in a separate WSL2 candidate environment. The local Docker candidate passed L0–L2, STO-3G equivalence, non-root/read-only source checks, exit-code checks and output retention after deletion. L0–L2, equivalence and specified acceptance probes were verified with networking disabled; strict network isolation for L3/L4 is **NOT_EXECUTED**. These technical passes do not certify scientific conclusions.

The repository includes source and wheel hash locks, an OCI Dockerfile, task wrappers, persistent manifests/logs/checkpoints, candidate PowerShell launchers, and target-host acceptance scripts. See the [English run guide](docs/en/CURRENT_P14_BUILD_RUN.md), [source audit](docs/en/HISTORICAL_RECORDS.md#source-audit), and [actual validation report](docs/en/HISTORICAL_RECORDS.md#report-2026-10-02).

Builds need network access. Task execution requires no installation, Git update, model API, monograph text or credentials. Local Docker L3/L4 and four-run joint classification have now passed under the fixed C12H6 protocol; these results do not establish support for other environments or a universal scientific claim. The upstream five-parameter optimizer writes checkpoints but offers no resume interface. See the [local delivery guide](docs/en/HISTORICAL_RECORDS.md#local-delivery) for the PowerShell 5.1 bootstrap, measured results and backup/restore workflow.

## Build and run locally with Docker

In a clean runtime checkout, use PowerShell 7.3+ with an available Docker Linux/amd64 engine. Builds require network access; no published image is required:

```powershell
./scripts/build-docker.ps1 -Tag ai4orgchem-runtime:local-source-candidate
./scripts/run-docker.ps1 -Task evidence -Image ai4orgchem-runtime:local-source-candidate -OutputRoot 'D:\AI4Science\ai4orgchem-runtime-runs\source-review'
```

This is the Docker-only build path for the original seven-task environment. A new build has a new runtime/image identity; historical acceptance results apply to the recorded candidate and do not automatically certify a newly built image. The normal launcher does not enforce network isolation. For the previously verified local image, the PowerShell 5.1 bootstrap is `./scripts/start-runtime.ps1 -Task evidence`.


The authorized first push triggered the current CI workflow: all three scoped jobs succeeded in [run 37933616122](https://github.com/CCcolab/AI4OrgChem-Runtime/actions/runs/37933616122). The workflow builds/tests and uploads execution evidence with seven-day retention; logs and artifacts are within the authorized public scope. It does not push images, create formal tags or publish Releases. This run does not replace historical scientific acceptance or execute high-cost scientific replay.

The second local service batch provides fixed-protocol torsion ledgers, conditional-state response comparisons, independent energy assembly, same-Hamiltonian path closure, a butadiene GL endpoint, a cyclobutadiene conditional diagnostic, and a benzene nuclear-repulsion/ordinary-DFT scan. See the [bounded case guide](docs/en/CURRENT_PROTOCOL_CASES.md), [measured validation summary](docs/en/HISTORICAL_RECORDS.md#protocol-cases-batch2-validation), and [support matrix](validation/protocol-cases/support-matrix.public.json). These are registered fixed inputs; the first ordinary RHF user-molecule service has its own limits, and general user conditional Compute remains BLOCKED. Numerical records belong to their recorded build/image identities, rather than implying that every case was recalculated on the final candidate image. No full geometry optimization or online calculation is introduced.

Third-party notice materials and outstanding corresponding-source requirements: [source delivery plan](docs/en/HISTORICAL_RECORDS.md#corresponding-source), [material verification](validation/license-materials-review.json). Supplemental notices do not certify binary/source correspondence; **image distribution remains BLOCKED; source and the supplied guide have been published under owner authorization**. Existing third-party licenses and NOTICE boundaries continue to apply.


Source publication and image distribution are assessed separately: [publication boundaries and local candidate](docs/en/PUBLICATION_BOUNDARIES.md). Source and guide synchronization is complete; native wheel provenance remains unresolved and no image has been distributed.

Professional review documentation (English summaries; Chinese originals retained): [S1–S6 services and task mapping](docs/en/HISTORICAL_RECORDS.md#professional-services), [result interpretation](docs/en/REVIEW_RESULTS.md), [three user paths](docs/en/CURRENT_USER_PATHS.md), and [historical Docker example](docs/en/HISTORICAL_RECORDS.md#p14-review-20261002). The [review report](docs/en/P14_REVIEW_TEMPLATE.md) and [feedback](docs/en/FEEDBACK_TEMPLATE.md) templates are filled manually. An automatic summarizer is not implemented; the legacy seven-task entry remains, with three separate fixed P02/P13/P01 entries added on 2026-10-08. The original `2460eef` candidate and this documentation supplement retain their distinct historical identities; both are included in the complete history authorized for the current source synchronization. That earlier export deferral is historical. The current source now includes [15 instruction Skills](skills/README.md), with separate local test scope; engines are not bundled.


</details>
