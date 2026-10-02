# AI4OrgChem Reproducible Runtime

Delivery review (2026-10-03): local Docker L0–L4, equivalence and scoped joint classification are verified. WSLc is **BLOCKED / NOT_EXECUTED**. CI is **statically reviewed; execution NOT_EXECUTED**. Third-party notices/source-distribution mapping still blocks public release. Apache-2.0 covers runtime-owned code, not every image component. See [final review](validation/DELIVERY_REVIEW_2026-10-03_zh-CN.md) and [license review](docs/LICENSE_REVIEW_zh-CN.md).

[中文说明](README_zh-CN.md)

An Apache-2.0 CPU runtime wrapper around the unchanged, commit-pinned AI4OrgChem public software and protocols. Source: `v0.3.2`, commit `28511f3d84fa65707a107cde1e8121a7b4334ecb`.

Development candidate only; no image or release has been published. L0 evidence checks, L1 core tests and L2 technical smoke have passed in a separate WSL2 candidate environment. The local Docker OCI candidate also passed L0–L2, STO-3G equivalence, offline execution, non-root/read-only source checks, exit-code checks and output retention after deletion. WSLc remains **BLOCKED / NOT_EXECUTED**. These technical passes do not certify scientific conclusions.

The repository includes source and wheel hash locks, an OCI Dockerfile, task wrappers, persistent manifests/logs/checkpoints, candidate PowerShell launchers, and target-host acceptance scripts. See the [Chinese run guide](docs/RUN_zh-CN.md), [source audit](docs/SOURCE_AUDIT_zh-CN.md), [compatibility matrix](docs/WSLC_COMPATIBILITY_zh-CN.md), and [actual validation report](validation/REPORT_2026-10-02_zh-CN.md).

Builds need network access. Task execution requires no installation, Git update, model API, monograph text or credentials. Local Docker L3/L4 and four-run joint classification have now passed under the fixed C12H6 protocol; these results do not establish WSLc support or a universal scientific claim. The upstream five-parameter optimizer writes checkpoints but offers no resume interface. See the [local delivery guide](docs/LOCAL_DELIVERY_zh-CN.md) for the PowerShell 5.1 bootstrap, measured results and backup/restore workflow.

Third-party notice materials and outstanding corresponding-source requirements: [source delivery plan](docs/CORRESPONDING_SOURCE_zh-CN.md), [material verification](validation/license-materials-review.json). Supplemental notices do not certify binary/source correspondence; public release remains BLOCKED.


Source-only publication and image distribution are assessed separately: [publication boundaries and local candidate](docs/PUBLICATION_BOUNDARIES_zh-CN.md). No public release; native wheel provenance remains unresolved.
