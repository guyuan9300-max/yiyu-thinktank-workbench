# build-resources

这个目录用于桌面版正式打包资源。

当前必须补齐：

- `icon.icns`

生成方式：

- `python3 scripts/generate-mac-icon.py`

后续可补：

- DMG 背景图
- 分发品牌素材
- 需要配套的签名 / 公证资源说明文档

当前目录先保留在仓库中，避免打包配置继续指向一个不存在的目录。
