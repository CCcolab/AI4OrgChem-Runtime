# Chemistry calculation and review Skills

[中文](README_zh-CN.md) · [Installation and invocation](USAGE.md) · [Tests and limitations](TESTING.md) · [Runtime home](../README.md)

Choose an instruction module by your input and research goal. These 15 Skills help an Agent prepare calculations, check real data, interpret results and organize reproducible evidence. They do not ship a chemistry engine, Docker image or automatic online service. Most analysis Skills can use your existing environment without installing the entire Runtime.

`skills/` is the repository's distribution source. Install only what you need into your Agent's supported location. It is separate from Runtime code in `runtime/`, launchers in `scripts/`, and the static guide in `docs/`.

| Skill | Invoke in Codex | Role |
| --- | --- | --- |
| [RHF single-point assistant](./rhf-single-point/README.md) | `$rhf-single-point` | Adapted personal Skill |
| [Table fitting and residual analysis](./table-fitting-residuals/README.md) | `$table-fitting-residuals` | Adapted personal Skill |
| [Orbital localization and density invariants](./orbital-localization-density/README.md) | `$orbital-localization-density` | Adapted personal Skill |
| [Molecular graphs and energy ledgers](./molecular-graph-energy-ledger/README.md) | `$molecular-graph-energy-ledger` | Adapted personal Skill |
| [Same-Hamiltonian path closure](./same-hamiltonian-path-closure/README.md) | `$same-hamiltonian-path-closure` | Adapted personal Skill |
| [Nonorthogonal subspace projections](./nonorthogonal-subspace/README.md) | `$nonorthogonal-subspace` | Adapted personal Skill |
| [Partition masks and definiteness checks](./partition-mask-audit/README.md) | `$partition-mask-audit` | Adapted personal Skill |
| [Reflection symmetry and orbital parity](./reflection-parity/README.md) | `$reflection-parity` | Adapted personal Skill |
| [Fragment working-basis assembly](./fragment-working-basis/README.md) | `$fragment-working-basis` | Adapted personal Skill |
| [Nuclear repulsion and geometric response](./nuclear-repulsion-response/README.md) | `$nuclear-repulsion-response` | Adapted personal Skill |
| [Scan energy components and curvature](./scan-energy-curvature/README.md) | `$scan-energy-curvature` | Adapted personal Skill |
| [Fixed-protocol conditional-state energy review](./fixed-protocol-energy-review/README.md) | `$fixed-protocol-energy-review` | Local workflow extension |
| [Constrained optimization and structural response](./constrained-optimization-response/README.md) | `$constrained-optimization-response` | Local workflow extension |
| [Multistate and size comparisons](./multistate-size-comparison/README.md) | `$multistate-size-comparison` | Local workflow extension |
| [Runtime usage assistant](./runtime-usage-assistant/README.md) | `$runtime-usage-assistant` | Local workflow extension |

## What is delivered

Every Skill contains `SKILL.md` and a bilingual `README.md`; no optional subfolders are required. Eleven modules adapt the owner's personal YouMind instructions; four are local workflow extensions. Scientific instructions remain in Chinese. See [authors](../AUTHORS.md), [LICENSE](../LICENSE), [NOTICE](../NOTICE) and the [instruction manifest](manifest.json).

Local records comprise two historical water RHF runs, 106 scenarios for the other ten original modules, and 64 scenarios for four workflow modules. These are scoped maintainer records, not independent blind Agent evaluation or full scientific certification. No scientific run is repeated for this packaging.

This is a post-v0.1.0 source supplement: obtain the branch/commit that contains `skills/`. The immutable v0.1.0 tag/assets and the static guide ZIP do not gain these files. No new version, tag, image or Release is created by this addition.

Review additions: [public deterministic regression](../validation/public_regression/README.md) · [saved-array MO review](../docs/en/CANONICAL_ORBITAL_REVIEW.md). No new RHF is run and historical tests are not new-version Agent acceptance. These 15 Skills are a post-v0.1.0 source supplement, not automatically part of old Release assets or guide ZIP.
