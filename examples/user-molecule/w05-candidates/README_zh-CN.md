# W05 候选输入：检查用途

2026-10-05。两种固定 xy 平面、中性单重态 C/H 输入，供验收准备审阅。每个目录包含 molecule.xyz、request-pilot.json 和 request-research.json；不是已获准的研究模板，没有 expected 能量。原子编号从 1 起，两组只指定碳 π 归属；氢的 σ AO 不需被分配到 π 组。

后续 [受限数值验收](../../../docs/USER_MOLECULE_W05_W06_NUMERICAL_REVIEW_zh-CN.public.md) 已执行：乙烯条件态未通过，丁二烯 pilot 普通态门禁失败；丁二烯 research 条件参考未执行（68 nAO 超过参考40上限）。下表是此前元数据 Check，不能作数值或研究资格。

| 目录 | π 组 | 几何来源 | 当前结果 |
|---|---|---|---|
| ethene-planar-technical-v1 | [1] / [2] | 指定参数构造的解析几何，非实验或优化 | 两 profile Check 通过，14/36 nAO |
| butadiene-p08-G-fixed-v1 | [1,2] / [3,4] | 固定上游 P08 ground_geometry 坐标，仅复用几何 | 两 profile Check 通过，26/68 nAO |

来源、单位、字节身份和实际输出见 [夹具登记](../../../validation/user-molecule/w05/candidate-fixtures.json)；科学限制与待办见 [准备说明](../../../docs/USER_MOLECULE_W05_PREPARATION_zh-CN.public.md)。丁二烯的旧能量不得当本次条件模型的参考值，其复用不自动满足“两个新体系”验收。

如自行重复低成本检查，在隔离 runtime 工作区运行：

```powershell
Set-Location D:\AI4Science\ai4orgchem-runtime-workspaces\user-molecule\runtime
$image = (Get-Content .\validation\user-molecule\candidate-image.json -Raw | ConvertFrom-Json).image_id
.\scripts\start-user-molecule.ps1 -Action Check -Image $image `
  -Request .\examples\user-molecule\w05-candidates\ethene-planar-technical-v1\request-pilot.json
```

可替换为同目录 request-research.json 或另一夹具请求。只执行 Check，限额1线程/512MiB/60秒；合法输入退出0，compute_eligible=false。它不会 SCF、构建格点或分配完整 ERI，不会生成能量差。当前无须重复本轮已通过的四次检查，先审阅留存记录即可。
