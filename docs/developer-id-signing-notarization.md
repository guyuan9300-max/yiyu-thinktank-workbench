# Mac Developer ID 签名与公证准备清单

## 目标

本阶段只做官网分发，不上架 Mac App Store。

目标效果：

- 用户从官网下载安装包。
- 双击安装并首次打开时，不再被 macOS 拦在“无法验证开发者”“需要到系统设置允许”等环节。
- 后续每次发布新版本时，由同一套 Developer ID 证书重新签名并提交公证。

## 当前仓库已准备

- `package.json`
  - `mac.forceCodeSigning: true`
  - `mac.hardenedRuntime: true`
  - `mac.notarize: true`
  - `mac.entitlements` 指向 `build-resources/entitlements.mac.plist`
  - `mac.entitlementsInherit` 指向 `build-resources/entitlements.mac.inherit.plist`
- `build-resources/icon.icns`
- `build-resources/entitlements.mac.plist`
- `build-resources/entitlements.mac.inherit.plist`
- `scripts/ensure-mac-release-prereqs.mjs`
  - 检查 Developer ID Application 证书
  - 检查 notarization 凭据
  - 检查 Xcode notarization 工具
  - 检查图标和 entitlements
- `scripts/inspect-mac-release-readiness.mjs`
  - 不构建、不签名，只做发布环境体检
  - 可给同事机器上的 Codex 先跑，确认缺哪类证书、凭据或工具
- `.env.release.example`
  - notarization 环境变量模板
  - 复制为 `.env.release` 后在本机私下填写
- `docs/mac-developer-id-handoff-for-codex.md`
  - 给同事机器上的 Codex 使用的逐步发布交接说明
- `npm run dist:mac`
  - 正式官网分发包路径
- `npm run dist:mac-local`
  - 仅本机自测路径，不可给外部用户

## 需要手动申请或配置

### 1. Apple Developer Program

需要加入 Apple Developer Program。

如果以公司/机构名义分发，优先用组织账号；如果以个人名义分发，用户看到的开发者名称会更偏个人身份。

通常需要准备：

- Apple Account，开启双重认证。
- 组织英文法定名称。
- D-U-N-S Number。
- 官网或公开联系方式。
- 账号持有人或有授权签署的人完成注册。
- 年费或符合条件时申请费用豁免。

### 2. Developer ID Application 证书

在 Apple Developer 后台创建 `Developer ID Application` 证书。

本项目只做 `.app / DMG / ZIP` 分发，优先需要这个证书；只有以后改成 `.pkg` 安装器，才额外考虑 `Developer ID Installer`。

证书安装后，本机应能查到类似：

```bash
security find-identity -v -p codesigning
```

输出里应出现：

```text
Developer ID Application: 机构或个人名称 (TEAMID)
```

### 3. Notarization 凭据

推荐使用 App Store Connect API Key，不建议把个人 Apple ID 密码链路作为长期发布方式。

正式构建机需要配置以下环境变量：

```bash
export APPLE_API_KEY="/absolute/path/to/AuthKey_XXXXXXXXXX.p8"
export APPLE_API_KEY_ID="XXXXXXXXXX"
export APPLE_API_ISSUER="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

备用方案是 Apple ID + app-specific password：

```bash
export APPLE_ID="apple-account@example.com"
export APPLE_APP_SPECIFIC_PASSWORD="xxxx-xxxx-xxxx-xxxx"
export APPLE_TEAM_ID="TEAMID"
```

不要把这些值写进仓库。

## 正式打包流程

拿到证书并配置凭据后，在受控 Mac 构建机执行：

```bash
npm run release:mac:doctor
npm run release:mac
```

构建后验证：

```bash
codesign -dv --verbose=4 "dist/mac-arm64/益语智库自用平台 V2.0.app"
spctl --assess --type execute --verbose=4 "dist/mac-arm64/益语智库自用平台 V2.0.app"
```

理想结果：

- `codesign` 显示 `Developer ID Application` 和 `TeamIdentifier`。
- `spctl` 显示 accepted。
- DMG 从浏览器下载后可正常打开、拖入 Applications、首次启动成功。

## 后续软件继续修改是否影响签名

不会影响已经发出去的旧版本；旧版本签名仍然是旧版本自己的签名结果。

但每一个新构建产物都必须重新签名、重新公证。原因是签名绑定的是“这一份 app bundle 的具体内容”，只要代码、前端资源、后端文件、图标、依赖等有任何变化，旧签名都不能直接复用。

不用每次重新申请 Apple Developer Program，也不用每次重新申请证书。正常情况是：

- 账号申请一次。
- Developer ID Application 证书在有效期内持续复用。
- 每次发布新版本时，用同一证书重新签名。
- 每次对外分发的新版本都重新提交 notarization。

只有这些情况才需要重新处理证书：

- 证书过期。
- 证书被撤销。
- 换了 Apple Developer 团队或开发者主体。
- 构建机丢失证书私钥。

## 官方参考

- [Apple Developer Program Enrollment](https://developer.apple.com/programs/enroll/)
- [Developer ID](https://developer.apple.com/developer-id/)
- [Create Developer ID certificates](https://developer.apple.com/help/account/certificates/create-developer-id-certificates)
- [Configuring the Hardened Runtime](https://developer.apple.com/documentation/xcode/configuring-the-hardened-runtime)
- [Safely open apps on your Mac](https://support.apple.com/en-us/102445)
