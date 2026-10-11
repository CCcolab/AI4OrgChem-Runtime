[English guide](USER_GUIDE.md) · [English README](../../README.md) · [Chinese counterpart](../../docs/templates/CURRENT_SERVICE_REVIEW_zh-CN.md)

# Professional service review template

Fill manually after choosing a module from [the service matrix](CURRENT_PROFESSIONAL_SERVICES.md). This is not an acceptance record and does not generate PASS. Retain NOT_APPLICABLE, UNKNOWN, MISSING and NOT_EXECUTED where appropriate. Use [the P14 template](P14_REVIEW_TEMPLATE.md) additionally for four-parent classification.

## Question and protocol

| Required item | Actual value | Evidence file/field |
| --- | --- | --- |
| Module, task/case/unit, question and date | Fill in | Actual run; capability table is navigation only |
| Input, atom/fragment mapping, geometry, charge/multiplicity and hashes | Fill in | Request, XYZ, read-only input snapshot |
| Profile/protocol version and source | Fill in | Contract/source lock; frozen baseline and captured adapters separately |
| Method/basis/grid, operators, constraints and functional | Fill in | Ordinary/conditional; h/F/S/ERI rules separately |
| Comparison, formula, sign, units and reference states | Fill in | Method/geometry/state compatibility or explicit differences |
| Actual acceptance and uncovered checks | Fill in | Original checks/failures; source and independent audit scope |
| Cost and budget | Fill in | CPU/threads/memory/scratch/wall and actual calls; reservations are not observations |
| Permitted interpretation/research scope | Fill in | Numerical qualification, protocol comparison and interpretation separately |

## Identities and evidence

| Identity | Actual value or UNKNOWN | Evidence |
| --- | --- | --- |
| Scientific baseline, captured worktree context and file SHAs | Fill in | 588+3 installation lock, or this module's own lock |
| Historical/current image-build Runtime commit | Fill in | Actual build record, never substituted by current HEAD |
| Host launcher identity and documentation commit | Fill in | Independent host identity/hash |
| Image ID and public registry digest | Fill in separately | No public digest: UNKNOWN |
| Dependencies, installation identity, input/profile/source/result/manifest hashes | Fill in | Receipts; historical PASS does not transfer |
| Accepted run/execution ID, parent tasks/unit dependencies | Fill in | Complete compatible results required by the protocol |
| Public witness and complete local originals | Fill in | Paths, SHA, review command and scope; summary is not the matrix |

## Execution, numerical checks and interpretation

| Layer | Original state, fields and evidence | Scope of conclusion |
| --- | --- | --- |
| Execution | Process/worker/host/runtime exit codes, logs, guards, resources, removal/output retention | Fill in |
| Numerical | SCF, electron count, density/idempotency/commutator, gap/mapping, closure, optimizer gradients/bounds/checks | Fill in; unexecuted audits do not become PASS |
| Scientific comparison | Reference, signed/absolute residual, units, tolerance, classification/scope | Fill in; wrapper consistency and independent implementations separately |
| Research interpretation | Stationarity, stability, applicability and allowed claim | Fill in; fixed point is not automatically a stable minimum |

For conditional states, separately report `Tr(S̃D)`, `Tr(SD)` and grid-integrated electron counts using the original result field names. Separate one-electron, Coulomb, exact exchange, semilocal XC, nuclear, total and closure terms; missing ordinary-state terms are unavailable. AO matrices and operational conditional energy differences are not direct experimental measurements or bond energies.

## Failure, gaps and delivery

Original failures, abnormal termination, missing tails, public-witness coverage and unfinished states: fill in. Two high-cost pilots do not establish full multistate assembly. No formal root endpoint means no qualified conditional difference. L4 checkpoints cannot resume. Keep original runs and derived reports separate.
