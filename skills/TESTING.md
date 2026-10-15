# Local test scope and evidence boundaries

[Catalog](README.md) · [中文](TESTING_zh-CN.md) · [Machine summary](../validation/skills/test-summary.json)

Two historical water single-point records exist for RHF/6-31G(d) and RHF/STO-3G, each with one SCF call. The current instruction was revised afterward, so those runs do not constitute execution of every current instruction branch. The other ten original modules have 106 scoped scenarios; four local workflow modules have 64. Correct refusals and explicit non-execution satisfy a negative case's expected outcome; they are not successful molecular calculations.

| Skill | Scoped scenarios | Evidence type |
| --- | ---: | --- |
| `rhf-single-point` | 2 historical RHF runs | Historical single-point outputs; later instruction revision |
| `table-fitting-residuals` | 13 | Maintainer-generated limited workflows, including negative cases |
| `orbital-localization-density` | 12 | Maintainer-generated limited workflows, including negative cases |
| `molecular-graph-energy-ledger` | 12 | Maintainer-generated limited workflows, including negative cases |
| `same-hamiltonian-path-closure` | 10 | Maintainer-generated limited workflows, including negative cases |
| `nonorthogonal-subspace` | 10 | Maintainer-generated limited workflows, including negative cases |
| `partition-mask-audit` | 9 | Maintainer-generated limited workflows, including negative cases |
| `reflection-parity` | 9 | Maintainer-generated limited workflows, including negative cases |
| `fragment-working-basis` | 9 | Maintainer-generated limited workflows, including negative cases |
| `nuclear-repulsion-response` | 11 | Maintainer-generated limited workflows, including negative cases |
| `scan-energy-curvature` | 11 | Maintainer-generated limited workflows, including negative cases |
| `fixed-protocol-energy-review` | 18 | Maintainer-generated limited workflows, including negative cases |
| `constrained-optimization-response` | 13 | Maintainer-generated limited workflows, including negative cases |
| `multistate-size-comparison` | 16 | Maintainer-generated limited workflows, including negative cases |
| `runtime-usage-assistant` | 17 | Maintainer-generated limited workflows, including negative cases |

Tests were generated and executed by the maintainer's Codex session after reading the instructions; this is not an independent blind Agent evaluation. Ten-module scope includes analytic numeric oracles, RDKit graph operations, saved-array review and Boys/PM each once on a saved occupied wavefunction, with no new SCF. Four-module scope includes real SciPy optimization of an analytic quadratic, saved P14 scalar records, saved RHF arrays, actual budget/assembly/input-parser APIs and zero-science CLI calls. No new molecular optimization, integral or Docker run was performed in those four-module tests.

The public summary hashes refer to locally retained original records. Full requests, workers, arrays and raw logs are not distributed here, so these files alone cannot independently reproduce or certify all 170 scenarios. Current instruction hashes and tested snapshot hashes are separate. Runtime usage assistant has one post-test editorial replacement of a withdrawn platform name with a generic unaccepted-platform limitation; its prior test snapshot remains retained. No method, threshold or execution rule changed, and no fresh workflow rerun is claimed for that text.

Only the recorded Windows numeric/RDKit and existing Linux-backend scopes were tested. Installing the folders is not backend or cross-platform scientific acceptance. Full conditional SCF, real constrained molecular optimization, complete P11/P12 collections, real four-parent classification, fresh-engine installation/lifecycle, stable wavefunctions and full orbital qualification remain outside these Skill tests. Historical Runtime acceptance does not transfer to another image, protocol or molecule. Skill tests are not run by the current public GitHub Actions jobs.

Publication packaging checks validate current formatting, instruction hashes, safe copies and internal links only. They do not repeat scientific calculation or modify the existing v0.1.0 Release.

## 2026-10-15 public deterministic regression

A [public minimal set](../validation/public_regression/README.md) now includes fixed inputs, expected values, explicit tolerances and programs. Every Skill has a normal example, a specific refusal and a common missing-file recording case. Further probes use the existing budget/assembly/input APIs and reject corrupt virtual orbitals even when the old endpoint flag passes. These are deterministic program checks, not independent Agent task evaluation.

```console
python -B scripts/run-public-review-regression.py --output /path/to/new-review-record
```

This increment uses only synthetic data and saved arrays. No new RHF/SCF, integrals, molecular optimization, training or container execution occurs. Current RHF end-to-end calculation remains NOT_EXECUTED under the user's no-calculation boundary. Usage-assistant examples validate explicit service selection/admission, not natural-language routing. The new CI job is configured; remote execution is NOT_EXECUTED. The historical 170 cases and their hashes are retained, as are current instruction bytes. See [increment status](../validation/review-20261015/status.json).
