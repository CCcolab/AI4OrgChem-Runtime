[English guide](USER_GUIDE.md) · [English README](../../README.md) · [Chinese counterpart](../../docs/templates/REVIEW_REPORT_zh-CN.public.md)

# P14 four-parent review template

This manual template retains the original S1–S6/P14 scope. For ordinary molecules and other fixed services start with [the current template](CURRENT_SERVICE_REVIEW.md). Historical CI/publication status is evidence for its recorded date; use [current publication scope](PUBLICATION_BOUNDARIES.md) for today's disclosure. A template is not acceptance.

## Scope and materials

Fill in date, author/reviewer/question, `proposition/protocol_id/scope` (registered planar D3h five-parameter C12H6 source-proxy), comparison/sign/units/reference states, geometry, method/basis/grid/constraints, fixed rules and uncovered questions.

| Identity | Actual value or UNKNOWN | Evidence |
| --- | --- | --- |
| Full scientific source SHA/tag | Fill in | Source lock / manifest.source_commit |
| Image-build Runtime SHA | Fill in | manifest.runtime_commit / image labels |
| Host launcher and document commits | Fill in | Separate retained records |
| Local image ID / registry digest | Fill in separately | Original fields and identity explanation |
| Dependencies, lock/code hashes | Fill in | dependencies / dependency_lock_sha256 / runtime_code_sha256 |
| Platform, CPU/threads/memory/time/network | Fill in | Actual measurements; absent checks NOT_EXECUTED |
| Protocol, input/output hashes and locations | Fill in | input_sha256 / output_sha256 |

## Task results

For `evidence`, `core-tests`, `p14-smoke`, `p14-equivalence`, `p14-fixed`, `p14-optimize` and `p14-classify`, separately list run ID; execution status and process/runtime exits; numerical qualification/failed checks; comparison/reference/signed and absolute residual/units; and classification/scope. Technical smoke/equivalence do not independently classify science. For fixed/optimized tasks record the ledger and geometry/gradient/boundary/endpoint/dΔr; for classify record original `decision_verdict/checks`, `quantitative_evidence`, `classification/scope/limitations`.

Separate the conditional energy components and closure. Include electron count, convergence, commutator and idempotency. For G/PLG optimization include `termination_reason`, gradients, `active_bounds` and geometry parameters.

## Four-parent integrity

| Parent task | run_id | Result SHA-256 | Manifest SHA-256 | Matches classification / missing |
| --- | --- | --- | --- | --- |
| p14-smoke | Fill in | Fill in | Fill in | Fill in |
| p14-equivalence | Fill in | Fill in | Fill in | Fill in |
| p14-fixed | Fill in | Fill in | Fill in | Fill in |
| p14-optimize | Fill in | Fill in | Fill in | Fill in |

Record classification run ID, manifest/result hashes and actual command, source/input/dependency/protocol compatibility, and every failed item. A missing parent permits only a partial report, not completed classification.

## Limits and delivery

Preserve original decisions, numerical qualification, reference differences, historical metadata and failed/unknown/unexecuted records. L4 does not support resume; real interruption acceptance remains NOT_EXECUTED absent separate evidence. Retain `production_label/training_eligible` without granting new eligibility. List material hashes, review findings and unresolved questions. This report does not authorize publication or new calculation.
