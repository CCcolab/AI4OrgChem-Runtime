[English guide](USER_GUIDE.md) · [English README](../../README.md) · [Chinese counterpart](../../docs/LICENSE_REVIEW_zh-CN.md)

# Actual candidate-image license review

This English reading version describes the 2026-10-03 review of historical image `sha256:ddc45b1fe500ed3d5ed30520eb4e49f3969cb69f02121f28e2ff851f7a724f54`, not a new build or legal certification. The reviewer inspected dpkg, Python metadata/RECORD, license texts and dynamic libraries offline as non-root. No research calculation ran. Image-distribution readiness remains blocked.

The [component inventory](../../validation/component-license-inventory.json) records 105 Debian packages, 18 venv Python distributions, an additional base-environment pip, 52 bundled dependency-environment entries and 191 shared-library files. An earlier 42-entry vendor count omitted pip nesting; the corrected record is retained. Original notice/license texts, including a first 203-file capture and later addenda, govern attribution; the summary is not a replacement or complete file-level determination.

Subsequent material review acquired 236 Debian archives covering 73/73 exact source versions, passed signatures/hash chains for three indexes, and acquired 18/18 exact Python sdists. 634/634 bundled Python files matched parent sources; 21 pip notices were added. setuptools' bundled autocommand is LGPLv3. Exact native-wheel correspondence and deliverable notices remain unresolved. See [final material review](../../validation/source-materials-final-review.public.json) and [publication boundaries](PUBLICATION_BOUNDARIES.md).

| Component | Recorded version/source | License / obligation scope |
| --- | --- | --- |
| Runtime / AI4OrgChem | Runtime build f30b290; science28511f3 | Apache-2.0 for owned code; retain LICENSE/NOTICE/upstream authors and modifications |
| Debian bookworm | Actual 105-package dpkg inventory | Per-file package copyright/common-license terms; 16 free-text packages have UNKNOWN normalized SPDX expressions, not missing texts |
| CPython | 3.12.13, official slim base | Preserve PSF and historical/additional terms |
| NumPy | 2.5.1, locked PyPI wheel | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 plus bundled numerical-library texts |
| SciPy | 1.18.0, locked wheel | BSD-3-Clause plus OpenBLAS/LAPACK/GCC and other bundled terms |
| PySCF | 2.14.0, locked wheel | Main Apache-2.0; bundled libraries retain their own terms |
| h5py | 3.16.0, locked wheel | Main BSD-3-Clause/LZF notices; HDF5/libaec etc. separately mapped |
| attrs / jsonschema / jsonschema-specifications / rpds-py / referencing / iniconfig | 26.1.0 / 4.26.0 / 2025.9.1 / 2026.6.3 / 0.37.0 / 2.3.0 | MIT; preserve copyright/license/disclaimer |
| pytest / pluggy / PyYAML / setuptools / pip | 8.4.2 / 1.6.0 / 6.0.3 / 78.1.0 / 25.0.1 | Main MIT; 52 bundled entries keep mapped terms, including autocommand LGPLv3 and certifi MPL-2.0 |
| Pygments / typing_extensions / packaging | 2.21.0 / 4.16.0 / 26.3 | BSD-2-Clause / PSF-2.0 / Apache-2.0 OR BSD-2-Clause; retain original choices and attribution |

Recorded native evidence includes NumPy OpenBLAS `0.3.33.112.0`, SciPy OpenBLAS `0.3.31.dev` (exact development commit UNKNOWN), HDF5 `2.0.0`, Libxc `7.0.0` (MPL-2.0), XCFun API `2.1.1` (MPL-2.0; pinned recipe `a89b783497d4fe146b477ac7a053303ce4189e9a` and patches retained, actual wheel patch application UNKNOWN), and libcint header `6.1.3` (Apache-2.0; exact binary build correspondence unresolved). libaec/libsz exact versions and patches remain unknown. Dynamic linkage is not proof of all statically bundled code or license completeness. A distributed bundled library requires review even if P14 never calls it.

Before image distribution, establish exact GPL/LGPL corresponding sources/patches/builds and recipient access, applicable modification/relink conditions, MPL source-access information and notices, and complete PySCF/HDF5/libaec/libsz notices with actual binary provenance. Preserve multiple licenses/exceptions rather than reducing them to one SPDX value. The OCI Apache-2.0 label describes Runtime-owned code, not all image contents. Do not silently replace or upgrade scientific dependencies to resolve documentation gaps.

The original 211-file supplemental material package and later acquisition records keep distinct historical identities. No dependencies/image/scientific results were changed for this review or English documentation. The inventory and original notices remain the authoritative detailed component records.
