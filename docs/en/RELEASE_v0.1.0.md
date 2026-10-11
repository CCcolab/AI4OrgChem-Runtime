[English guide](USER_GUIDE.md) · [English README](../../README.md) · [Chinese counterpart](../../docs/RELEASE_v0.1.0_zh-CN.md)

# AI4OrgChem Runtime v0.1.0

The first source-and-static-guide Runtime release is independent of AI4OrgChem science v0.3.2. The guide's historical `v0.3.0-candidate` is an internal delivery label, not the Runtime version. [Release and assets](https://github.com/CCcolab/AI4OrgChem-Runtime/releases/tag/v0.1.0) remain fixed at `b4a74e7667bd601a4fe3090e0092f029f13848b1`. Later English documentation does not replace these immutable assets.

You can run user-XYZ ordinary RHF within H/C/N/O, neutral closed-shell singlet, RHF/6-31G(d), ≤20 atoms/AO≤80; replay registered fixed protocols; review saved ledgers/witnesses; and build/register your own local Docker installation. The website does not upload molecules or execute online science.

| Asset | Purpose |
| --- | --- |
| `AI4OrgChem-Runtime-source-v0.1.0.zip` | Installer-produced Git-proof source, no complete environment or dependency binaries |
| `AI4OrgChem-Runtime-guide-v0.1.0.zip` | Ten-member static guide; open docs/index.html after extraction; not an installation package |
| `SHA256SUMS.txt` | Published checksums for the source and guide ZIPs |

Use the dedicated source asset or clone the tag, rather than GitHub's automatic Source code ZIP, which lacks installation proofs. See [source installation](SOURCE_INSTALLATION.md).

The release notes record two public CI jobs/Pages for `f3c6bdf` and a prior local engineering set: 537 executions, 535 passed and two explicit skips. These are scoped records for their own commits. The original failing browser's three download buttons/files were subsequently reported PASS by an external reviewer via the project owner; this is user-provided evidence, not maintainer-independent execution. See [the exact retest record](../../validation/web-guide/external-browser-retest-20261010.json). Later guide bytes have separate hashes; old hashes cannot certify new bytes.

Conditional user Compute remains BLOCKED, complete canonical/virtual-orbital gates are not implemented, ordinary stability was not executed, and only two of 78 high-cost registered states have historical pilot acceptance. The remaining 76 states, complete assembly and new-installation science replay remain unexecuted. L4 checkpoints do not resume. User DFT/ions/open-shell/general optimization/scans and full original-project certification are not part of this release.

No prebuilt image or complete bundled environment is distributed. Runtime-owned code is Apache-2.0; third-party and YouMind rights remain separate. See [publication boundaries](PUBLICATION_BOUNDARIES.md), [authors and acknowledgements](AUTHORS.md) and [CITATION.cff](../../CITATION.cff). Packages remain unpublished; GitHub Contributors/Languages are generated from actual account-attributed commits/files.

For asset links, original sizes/hashes and the distinction between release assets and later English documentation, see [English release and downloads](DOWNLOADS.md).
