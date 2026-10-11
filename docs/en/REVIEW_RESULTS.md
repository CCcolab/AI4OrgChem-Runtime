[English guide](USER_GUIDE.md) · [English README](../../README.md) · [Chinese counterpart](../../docs/REVIEW_RESULTS_zh-CN.public.md)

# Interpret results and assemble review evidence

Use [the current service matrix](CURRENT_PROFESSIONAL_SERVICES.md) and [review template](CURRENT_SERVICE_REVIEW.md). The historical S1–S6/P14 interpretation is preserved below in its original scope. Evidence-reading tasks do not require a nonexistent molecule result JSON.

| Layer | Read | Establishes | Does not replace |
| --- | --- | --- | --- |
| Execution/integrity | Manifest status, process/runtime exits, output hashes, identities | How a task ended and whether recorded bytes match | Scientific numerical qualification |
| Numerical qualification | Task gates, acceptance checks, electron/convergence/residual fields | Whether the registered checks passed | Printed-source comparison or general method validity |
| Numerical comparison | Source comparison, differences, quantitative evidence, reference and units | Fixed/optimized endpoint or geometry-response deviation | Scientific classification and its scope |
| Classification | Classification, decision verdict/checks, scope and limitations | The registered C12H6 joint decision | Arbitrary molecules or all aromaticity theories |

The older record describes a legacy defect: process exit0 with failed/unknown gates could leave runtime_exit_code0 despite manifest FAIL. This is historical behavior; subsequent engineering repairs reject failed/unknown/missing required gates. Read the actual version's manifest and exit fields together. NOT_APPLICABLE, UNKNOWN, unavailable, NOT_EXECUTED, BLOCKED and FAIL have distinct meanings.

## Ledgers, references and identities

List ordinary G, ordinary@PLG and conditional PLG energies separately. Conditional terms are `one_electron_energy_hartree`, `coulomb_energy_hartree`, `exact_exchange_energy_hartree`, `semilocal_xc_energy_hartree`, `nuclear_repulsion_hartree`, `total_energy_hartree` and closure residuals; do not invent unreported ordinary-state components.

Report signed residuals first. Derived absolute differences must include their formula. Printed endpoint 67.08 kcal/mol and frozen fixed-geometry endpoint about 67.086899 kcal/mol are different references; printed dΔr 0.179 Å and frozen optimized response about 0.172204 Å are also different. Matching a frozen result establishes same-protocol repeatability. P.final_classification uses 5.0 kcal/mol energy tolerance, 0.03 Å bond-response tolerance and 0.015 Å PLG near-equal-bond threshold; these do not replace SCF/equivalence gates. Do not tune settings for an expected outcome.

Record actual scientific source, image-build Runtime, host launcher, image ID, dependencies and lock hashes separately. A local image ID is not a published registry manifest digest. Preserve old `image_digest` fields without treating them as a download address. Compare every original against `manifest.output_sha256`; four-parent result hashes must also match classification `parent_runs` and `evidence_sha256`. Historical result metadata may refer to frozen upstream calculations; the actual executed run is identified by its manifest, not by overwriting those fields.

## Missing or failed evidence

- Preserve failed L0/L1 logs and stop scientific interpretation.
- Report actual memory/source refusal and resource evidence; retain thresholds.
- A checkpoint without the final L4 result is partial and cannot enter classification or resume.
- Missing parents, mismatched hashes or incompatible dependencies do not form a qualified input set; do not fill gaps with frozen results.
- Preserve partial/disagreement decisions instead of replacing them with success based on exit0.
- Unperformed platform/offline/interruption checks are NOT_EXECUTED with separate blocking reasons.

Keep `review/summary.md` and `review/source-references.md` separate from complete `runs/<run-id>/` originals. For handoff copies, preserve manifests and hashes, record the new location and verify bytes. Manual reports neither alter classifications nor upload automatically. Historical automatic summary/index/copy/general-Python-classifier proposals are not represented as implemented features here.
