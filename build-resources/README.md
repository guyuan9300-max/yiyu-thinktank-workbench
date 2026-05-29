# build-resources

这个目录用于桌面版正式打包资源。

当前正式官网分发包需要：

- `icon.icns`
- `entitlements.mac.plist`
- `entitlements.mac.inherit.plist`

生成方式：

- `python3 scripts/generate-mac-icon.py`

后续可补：

- DMG 背景图
- 分发品牌素材
- 需要配套的签名 / 公证资源说明文档

签名与公证交接说明见：

- `docs/developer-id-signing-notarization.md`
