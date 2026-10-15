[English guide](USER_GUIDE.md) · [English README](../../README.md) · [Chinese counterpart](../../docs/TEST_DISTRIBUTION_zh-CN.md)

# Runtime development test distribution scope

On 2026-10-10, the owner requested removal of root `tests/` from the current public tree. The 101 tracked files were first saved with their original bytes from `3597a5221765be7ecffdf1264fa46f90842a14ec` in a local ZIP and SHA-256 inventory. Workspace copies remain local; `/tests/` is ignored. History was not rewritten, so old commits still contain them. Frozen upstream scientific tests/licenses/source records are outside this removal.

The saved `2f9e7f75` run records success for the following two jobs; remote CI was not rerun in this increment:

- `linux`: build the candidate, run original L0/L1, and check offline container permissions/output retention.
- `public-installation-engineering`: install from public sources, register four service identities, and use standard-library file probes for non-root, read-only source, offline operation, Linux output permissions, exits and output retention after removal. No molecule/high-cost replay.

On 2026-10-15 a third lightweight `public-review-regression` job was configured for [public deterministic examples](../../validation/public_regression/README.md) and saved arrays. It installs no quantum backend, builds no image and runs no molecular calculation. Remote execution of this new job is NOT_EXECUTED. The 79 local checks remain separate from the historical 170 Skill cases and from Agent/scientific evaluation. Root `tests/` stays withdrawn.

Runtime unit jobs depending on root tests are no longer run publicly. A successful two-job run does not certify those private suites or all scientific services. Previous four-job success at `3597a52` remains a historical record. Local acceptance without the test directory must refuse instead of declaring zero tests PASS.

Original source locks remain byte unchanged. V4 installation excludes exactly five protocol-family and seven high-cost-family test rows, records their original hashes/sizes, and explicitly distinguishes original/installed counts. Ordinary/fixed source catalogs have no test rows. Permitted engineering overrides do not alter scientific source, protocols, resources or tolerances; missing scientific rows or unknown changes must refuse. Existing image/result identities do not transfer to a new installation.

This distribution-scope change did not itself publish a version/tag/Release. The separately authorized v0.1.0 publication is described in [release scope](RELEASE_v0.1.0.md); conditional Compute and image limitations persist.
