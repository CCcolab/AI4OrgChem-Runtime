# Local regression prepared for public review

These are deterministic checks linked to the current 15 instruction hashes, not a natural-language Agent benchmark. Input and expected outputs are public in [fixtures.json](fixtures.json), with explicit absolute tolerances and zero relative tolerance. [The example program](../../review_tools/skill_examples.py) checks selected mathematical and input rules. It is not a general chemistry engine or a complete implementation of any Skill.

From the repository root, with an existing Python/NumPy/RDKit environment:

```console
python -B scripts/run-public-review-regression.py --output /path/to/new-review-record
```

Use a genuinely new path. The runner records actual versions, imported source hashes, current instruction hashes, individual test IDs and logs. Zero/partial discovery, skipped tests or unexpected failures return nonzero. No quantum backend, Docker, WSL, geometry optimization or training is started. The CI dependency file pins already-recorded Linux CPython 3.12 wheels; this local invocation does not install them.

Each Skill has a normal deterministic example and a specific refusal input. A missing-file case in the common recording harness is exercised in each Skill context; those 15 cases do **not** constitute 15 real backend failure tests. Additional cases cover complex/fractional occupations, nonorthogonal rank loss, Fock non-positivity, path bridges, scan units, strict input handling, actual budget/assembly APIs and the complete MO review counterexample.

Normal checks, expected refusals and execution-error recording are counted separately. A PASS means the program met those expectations; it does not mean a molecular calculation succeeded or an Agent followed the instruction. The historical 170 cases and two RHF runs retain their prior snapshot identities. The [actual CI run at 09cbab5](https://github.com/CCcolab/AI4OrgChem-Runtime/actions/runs/38692149789) passed the added regression job and fresh Linux CI source-installation engineering. Current RHF end-to-end execution, Windows fresh installation plus new water RHF, and independent/blind Agent evaluation remain deferred and NOT_EXECUTED. See the [current delivery scope](../../docs/en/DELIVERY_SYNC_20261015.md); historical local records keep their execution-time status.

The instruction example rejects injected request fields, but this is a parser test, not proof of an Agent's prompt-injection resistance. All unavailable scientific qualifications remain unavailable. See [English test scope](../../skills/TESTING.md) / [中文](../../skills/TESTING_zh-CN.md).

## Normalized leakage correction

The nonorthogonal example returns the dimensionless squared S-norm fraction `r†Sr/(v†Sv)`, never the raw numerator. It accepts a single finite real/complex vector of shape `(n,)`; zero vectors are undefined and refused. Matrices and column-vector batches are not silently flattened or averaged. The [numerical policy](../../review_tools/nonorthogonal_leakage_policy_v1.json) declares metric/rank/roundoff limits and rescaling conventions. These limits apply only to the example, not a frozen scientific worker.

[Seventeen analytic regression tests](test_nonorthogonal_leakage.py) cover the seven review probes and scaling, complex metrics, rank loss, invalid inputs and failure recording. Discovery requires the four modules and every named leakage test. The new run has 96 tests; the prior 79-test log and historical 170-scenario records remain unchanged and are not added to that count. See the [correction record](../../docs/REVIEW_CORRECTIONS_20261015_zh-CN.md).
