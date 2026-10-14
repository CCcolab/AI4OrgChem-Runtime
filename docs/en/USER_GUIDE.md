[English guide](USER_GUIDE.md) · [English README](../../README.md)

# Runtime user guide

[Online English guide](https://cccolab.github.io/AI4OrgChem-Runtime/en/) · [English README](../../README.md) · [Chinese guide](https://cccolab.github.io/AI4OrgChem-Runtime/)

AI4OrgChem Runtime helps you run scoped local molecular calculations and review registered research examples, with inputs, scientific sources, dependencies, logs and results kept traceable. The website provides guidance only. Your molecule is not uploaded and no calculation is executed by reading this page.

1. [Install from source](SOURCE_INSTALLATION.md), build a local Docker environment and record its image identity. Source and guide are public; a prebuilt public image is not supplied.
2. Choose [your own XYZ](CURRENT_MOLECULAR_SINGLE_POINT.md) or a registered research module from the table below. Use the same service installation record for all its commands.
3. Keep a new complete run directory. Read the module-specific checks and [result interpretation](REVIEW_RESULTS.md), then use the [review template](CURRENT_SERVICE_REVIEW.md) where needed. Execution success and scientific interpretation are separate.

For Agent-assisted preparation and saved-data analysis, see the separate [Skills catalog](../../skills/README.md) and [installation steps](../../skills/USAGE.md). Loading a Skill does not require starting Docker or grant a new scientific service.

| Your goal | English guide |
| --- | --- |
| RHF single-point energy, orbitals and AO density for your molecule | [Small-system molecular service](CURRENT_MOLECULAR_SINGLE_POINT.md) |
| Frozen-table statistics, graph/energy ledger, ethene orbital-representation control | [Fixed examples](CURRENT_REGISTERED_CASES.md) |
| Torsion endpoints, conditional-energy response, fragment assembly, same-Hamiltonian closure, butadiene GL, CBD diagnostic, benzene BLA response | [Fixed research protocols](CURRENT_PROTOCOL_CASES.md) |
| Registered constrained multistate optimization and ring-size/state comparison | [High-cost states](CURRENT_HIGH_COST_CASES.md) |
| Fixed C12H6 conditional-energy and structure-response joint review | [Separate original P14 environment](CURRENT_P14_BUILD_RUN.md) |

Each module's input/method/comparison/evidence/cost/interpretation is specified in the [professional service matrix](CURRENT_PROFESSIONAL_SERVICES.md). Also see [three user paths](CURRENT_USER_PATHS.md), [host-only evidence navigation](LOCAL_RUNTIME_ENTRY.md), [release/download scope](RELEASE_v0.1.0.md), [license materials](LICENSE_REVIEW.md), [publication boundaries](PUBLICATION_BOUNDARIES.md) and [historical evidence in English](HISTORICAL_RECORDS.md).

The ordinary user-XYZ profile is H/C/N/O, neutral closed-shell singlet, RHF/6-31G(d), ≤20 atoms and actual AO≤80. DFT/ions/open-shell/general user optimization/scans are future work. Full canonical/virtual orbital qualification and ordinary wavefunction stability are not established. Conditional user Compute is closed. Only two of 78 high-cost states have historical pilot acceptance; a new installation does not inherit scientific PASS. L4 checkpoints cannot resume. Ordinary WSL2 Check does not certify native Compute or Docker computation.

See [English release and downloads](DOWNLOADS.md) and [English authors and acknowledgements](AUTHORS.md). This English documentation supplement does not modify the v0.1.0 tag/Release assets, original Chinese guide download implementation or scientific sources/results. Historical evidence is summarized in English with clearly labelled original Chinese links, not relabelled as newly verified calculation output.
