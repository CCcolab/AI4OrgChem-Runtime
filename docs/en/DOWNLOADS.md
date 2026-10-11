# AI4OrgChem Runtime: release and downloads

[English guide](USER_GUIDE.md) · [English README](../../README.md) · [Release scope](RELEASE_v0.1.0.md) · [Authors](AUTHORS.md)

**Current release: v0.1.0**, published on 2026-10-10. This is a source-and-static-guide release, not a prebuilt image or complete installed environment. The version belongs to Runtime, independently of the original AI4OrgChem scientific project's v0.3.2.

## Choose a download

| Download | Purpose | Bytes |
| --- | --- | ---: |
| [AI4OrgChem-Runtime-source-v0.1.0.zip](https://github.com/CCcolab/AI4OrgChem-Runtime/releases/download/v0.1.0/AI4OrgChem-Runtime-source-v0.1.0.zip) | Source package with Git commit/tree/blob proofs for the installer. Extract into a new directory and follow the source-installation guide. No environment or dependency binaries are bundled. | 3497634 |
| [AI4OrgChem-Runtime-guide-v0.1.0.zip](https://github.com/CCcolab/AI4OrgChem-Runtime/releases/download/v0.1.0/AI4OrgChem-Runtime-guide-v0.1.0.zip) | The original ten-member static guide package. Open `docs/index.html` after extraction. Its website content is Chinese; it is not an installation package and does not contain the later English documentation supplement. | 499322 |
| [SHA256SUMS.txt](https://github.com/CCcolab/AI4OrgChem-Runtime/releases/download/v0.1.0/SHA256SUMS.txt) | Checksums for the two ZIP assets. | 205 |

For the English guide, [read it online](https://cccolab.github.io/AI4OrgChem-Runtime/en/) or obtain `docs/en/` from the current `main` branch. Later English materials do not replace the fixed release assets.

## Verify the release assets

| Asset | SHA-256 |
| --- | --- |
| Source ZIP | `37cc2921543ef0e4f2331296b9ec16ac18bbf7e58a9055acf4c6108651e4c077` |
| Guide ZIP | `6f7d7dbe9bc2abcf129059704902739afd2bce1e01cfa53f8cbb8f4691b56ac7` |
| Checksum text | `29eb1f7ebe7a8a10c2a001eb193448da721638c65bfadead313034d92f40521b` |

These identities belong to the original published v0.1.0 assets, not a newly generated guide ZIP or current-main source archive. See the [GitHub Release](https://github.com/CCcolab/AI4OrgChem-Runtime/releases/tag/v0.1.0) for the formal release and assets.

## Clone the source instead

For the fixed release:

```powershell
git clone --branch v0.1.0 --depth 1 https://github.com/CCcolab/AI4OrgChem-Runtime.git D:\chem-work\runtime-v0.1.0
Set-Location D:\chem-work\runtime-v0.1.0
git rev-parse HEAD
```

The tag resolves to `b4a74e7667bd601a4fe3090e0092f029f13848b1`. To read the later English pages and maintenance changes, clone the current main branch into a different new directory and record its actual commit:

```powershell
git clone --branch main https://github.com/CCcolab/AI4OrgChem-Runtime.git D:\chem-work\runtime-current
Set-Location D:\chem-work\runtime-current
git rev-parse HEAD
```

Continue with [source installation](SOURCE_INSTALLATION.md), using existing Python 3.12+, Docker Linux/amd64 and build-time network access. The named source asset and a Git clone provide installation source identities; GitHub's automatic Source code ZIP does not contain the installer's proofs. New installations need their own image registration and run evidence; historical scientific PASS does not transfer automatically.

The [release scope](RELEASE_v0.1.0.md) and [publication boundaries](PUBLICATION_BOUNDARIES.md) distinguish ordinary small-system RHF, fixed protocols, unexecuted states and unsupported functions. User conditional Compute remains closed; image distribution remains blocked; L4 checkpoints cannot resume.
