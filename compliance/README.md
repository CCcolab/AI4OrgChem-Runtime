# Third-party materials in this source repository

The root Apache-2.0 license covers runtime-owned code and documentation. It does not relicense third-party files in this directory or software carried by an image.

| File | Origin and terms |
|---|---|
| upstream/pyscf-CMakeLists.txt | PySCF v2.14.0 build recipe; Apache-2.0; original header retained |
| upstream/pyscf-libxcfun.patch | Patch distributed with PySCF v2.14.0 for XCFun; retain upstream patch and treat changes to MPL-covered XCFun files under MPL-2.0; corresponding XCFun notice in xcfun-LICENSE.md |
| upstream/xcfun-LICENSE.md | Original license from XCFun commit a89b783497d4fe146b477ac7a053303ce4189e9a; MPL-2.0 |
| upstream/libxc-COPYING | Original Libxc 7.0.0 COPYING; MPL-2.0 |
| upstream/libcint-LICENSE | Original libcint v6.1.3 license; Apache-2.0 |
| upstream/hdf5-LICENSE | Original HDF5 2.0.0 license, including copyright and additional notices |
| upstream/libxc-AUTHORS | Unmodified author list from the acquired Libxc 7.0.0 source archive; accompanying libxc-COPYING remains MPL-2.0 |
| upstream/libcint-AUTHORS | Unmodified author list from the acquired libcint v6.1.3 source archive; accompanying libcint-LICENSE remains Apache-2.0 |

These are attributed upstream materials, not a second maintained scientific implementation. The original versions, sources and hashes are recorded in validation/license-materials-manifest.json. A successful source patch applicability check does not prove which patches were applied when building the installed wheel.

The XCFun patch touches CMakeLists.txt, whose original header credits Radovan Bast, Roberto Di Remigio, Jonas Juselius and contributors (2015–2020), and src/XCFunctional.cpp, whose original header states Copyright (C) 2020 Ulf Ekström and contributors and MPL-2.0. The patch itself is retained byte-for-byte as distributed by PySCF. Source header excerpts, original file hashes and the supplemental author-list archive provenance are recorded in validation/third-party-attribution-review.json. These notices supplement generic license templates; they do not claim to enumerate every contributor to the full native libraries.

Native dependency archives and the OCI image are outside Git, in the local candidate package. Source-only publication and image distribution have separate readiness assessments in docs/PUBLICATION_BOUNDARIES_zh-CN.md. Neither is published by this repository's CI.

The actual high-cost Docker candidate has a separate [2026-10-09 component review](HIGH_COST_COMPONENTS_20261009_zh-CN.md) and [machine addendum](high-cost-license-addendum-20261009.json). geomeTRIC 1.1.1 carries an additional training-dataset restriction and must not be described as unmodified BSD-3-Clause. RDKit's core BSD and wheel-packaging MIT notices are distinct. Bundled native build/source mapping and the Amadeus font's redistribution authorization remain unresolved. Image distribution stays BLOCKED_LOCAL_ONLY; this source repository's Apache-2.0 does not relicense those materials.

The user-supplied YouMind guide at `docs/index.html` and the original/derived
guide materials under `docs/runtime-guide` preserve their recorded provenance
and pending rights status. The root Apache-2.0 does not automatically relicense
them. Public inclusion is part of the project owner's final synchronization
scope confirmation, distinct from OCI image distribution. See
[the synchronization preparation](../docs/GITHUB_SYNC_PREPARATION_20261009_zh-CN.public.md).
