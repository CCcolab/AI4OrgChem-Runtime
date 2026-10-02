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

These are attributed upstream materials, not a second maintained scientific implementation. The original versions, sources and hashes are recorded in validation/license-materials-manifest.json. A successful source patch applicability check does not prove which patches were applied when building the installed wheel.

Native dependency archives and the OCI image are outside Git, in the local candidate package. Source-only publication and image distribution have separate readiness assessments in docs/PUBLICATION_BOUNDARIES_zh-CN.md. Neither is published by this repository's CI.
