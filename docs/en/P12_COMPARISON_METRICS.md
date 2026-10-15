# P12 N16 comparison metrics

This note reads the [frozen N16 ledger](https://github.com/CCcolab/AI4OrgChem/blob/28511f3d84fa65707a107cde1e8121a7b4334ecb/evidence/P01-P14/P12/n16-same-basis-ledger.json); it adds no calculation and changes no `P12_CONSISTENT` result. The original scientific three-point determination is distinct from Runtime's two historical pilot acceptances.

| Quantity | Value | Denominator and precision |
| --- | ---: | --- |
| Project N16 CESE | −0.339527 kcal/mol | Rounded display value |
| Monograph N16 CESE | −0.65 kcal/mol | Printed source value |
| Absolute difference | 0.310473 kcal/mol | `abs(-0.339527 - (-0.65))` |
| Difference relative to source magnitude | Approximately 47.7651% | `0.310473 / abs(-0.65) × 100%`, derived from rounded values |
| Registered relative CESE | 2.103137% | `abs(CESE) / abs(sum_delta_EAm + sum_delta_EnAm) × 100%`, using unrounded ledger scalars |

The registered denominator is `abs(17.426664112539722 + (-1.282813532688139)) = 16.143850579851583 kcal/mol`. Signed terms are added before taking the absolute value. It is not the sum of absolute contributions or the magnitude of the source CESE. The ledger CESE is `−0.33952721462311064 kcal/mol`. The 2.103137% boundary indicator must not be described as a 2.10% difference from the monograph.

Report direction, the registered boundary and the source-magnitude difference separately. Near-zero quantities require an absolute difference; arithmetic closure is not physical uncertainty. No N18/N20/N22 calculation, N16 rerun or original ledger modification is included. See the [machine explanation](../../validation/review-20261015/p12-metrics.json).
