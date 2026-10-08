# P11 原著命题映射 v0.1

> **已被后续协议修订（2026-09-08）：** 本v0.1映射保留固定Figure 7几何审计语义。当前P11-B定判采用`p11-source2007-planar-recalculation/0.2`：13个状态分别进行全平面受限优化，得到`CE=+1.173122`、`IE=+0.490079 kcal/mol`，P11与原著一致。下表旧负IE不再是当前定判。

| 原著公开表述 | P11机器定义 | 当前子目标 |
|---|---|---|
| furan-like species的`ΔEA>0` | `E(G)-E(GL)>0` | P11-A |
| 三个局域相互作用增量为正 | `ΔEA1>0`、`ΔEA2=ΔEA3>0` | P11-A |
| `ΔEA<ΣΔEAm` | `E(G)-E(GL)<E(GE1)-E(GL)+2[E(GE2)-E(GL)]` | P11-A |
| 负差值应称LDE而非ESE | `LDE=ΔEA-ΣΔEAm<0` | P11-A |
| 呋喃类LDE不能与苯型ESE直接比较 | 结论字段禁止`aromatic_extra_stabilization`标签 | P11-A |
| 取代苯整体ESE | `ESE(SB)=ΔEA-(ΔEA1+ΔEA2+ΔEA3)` | P11-B完成；`-38.399223 kcal/mol` |
| 隔离苯环ESE | `ESE(Ph)=ΔEA7-(ΔEA4+ΔEA5+ΔEA6)` | P11-B完成；`-39.580151 kcal/mol` |
| 取代基共轭贡献 | `CE=ESE(SB)-ESE(Ph)` | P11-B完成；`+1.180928`，支持原著`+1.2` |
| 取代基诱导贡献 | `IE=ESE(Ph)-ESE(benzene)`；主锚点为同引擎、同2007语义苯ESE | P11-B完成；`-0.335714`与原著`+0.49`异号，在冻结Figure 7 source-proxy下判为不一致；完整Cartesian缺失仅限制历史身份声明 |

主要公开来源：原著第6章6.2.3与6.3节；作者公开书稿前言；Bao与Yu 2007年restricted geometry optimization论文（DOI `10.1021/jp067440i`，Figure 7及3.4节）。P11-A使用后期原著的LDE命名及无权重`ΣΔEAm`定义，不混用早期论文的ESE-I/ESE-II权重方案。P11-B只采用Figure 7的氰基苯重原子键长和状态拓扑；完整历史Cartesian坐标未公开，因此明确标注为source proxy。
