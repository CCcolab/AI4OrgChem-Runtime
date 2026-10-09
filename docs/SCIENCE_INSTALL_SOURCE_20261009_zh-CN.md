# 干净安装科学源码输入（2026-10-09）

科学输入可由固定公开上游归档和本仓库保留的三份适配增补重建；无需原科学工作区或既有 Docker 镜像。

公开基线为 `CCcolab/AI4OrgChem` 的 `28511f3d84fa65707a107cde1e8121a7b4334ecb`，codeload 归档 SHA-256 为 `f4a0a416c227218d0bc84bf597cb43f2ba0a32695566e131bdcc6b19ac3f207e`。其 588 份文件必须逐项匹配旧基线清单。`assets/science-install-overlay/cc743790/` 保留适配器、适配器测试和说明三份原字节，来自已封存交付的科学归档；保留前验证该归档哈希及全部 591 份内容。旧基线 LICENSE、NOTICE、AUTHORS 等随完整源码保留。

```powershell
python -B scripts/prepare-science-install-source.py prepare --output D:/installation/source-inputs
python -B scripts/prepare-science-install-source.py extract --archive D:/installation/source-inputs/science.tar --destination D:/installation/science
```

已有固定公开基线归档时，可给 `prepare` 加 `--baseline-archive <archive.tar.gz>`。两种方式均核对归档哈希、588 份基线内容、三份增补内容、全部 591 份树内容与确定性输出归档。目标目录必须尚不存在；验证失败不修复或覆盖目标。命令只处理源码字节，不导入科学模块、不进行 SCF、网格、积分或 P12 重算。

新增 `locks/source.installation.lock.json` 固定重建归档 SHA-256 `a2d1b18d22c363893b53801a6a7e3f6aa4e7bccc18de119b4b2bd9e62e0ffed7`，大小 7,075,840 字节。它与历史 `cc743790` 文件内容清单完全一致，但使用统一权限、所有者、时间和排序重新序列化；不重建 Git 提交对象。历史归档 SHA-256 `92cb1a467b9c5c502fbc0e353c17f0083218c8dfdbb322fb51f7aa6e8db5eb73`、旧来源锁及旧提取脚本保持原记录。新归档须通过新脚本 `extract` 提取，不能给旧提取脚本冒充旧归档。

安装收据 `science-install-source.receipt.json` 将公开基线获取、重建文件树、新归档身份和旧归档身份分列。源码准备成功不代表新镜像安装验收、科学验收或历史 PASS 的转移；这些由本次新安装的实际登记和示例验收另行记录。本轮只在本地准备，不发布镜像或公开推送。
