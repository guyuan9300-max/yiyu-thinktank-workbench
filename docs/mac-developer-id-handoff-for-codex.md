# 给发布机器 Codex 的 Mac 官网分发交接说明

## 先读结论

益语智库自用平台 V2.0 暂时不走 Mac App Store，上线目标是“官网/私有链接下载 DMG 后，用户能正常拖入 Applications 并首次打开”。这条路线需要：

1. 用 Apple Developer 账号下的 `Developer ID Application` 证书给 app 签名。
2. 开启 hardened runtime。
3. 把签好的产物提交 Apple notarization。
4. 把公证 ticket staple 回 app/DMG。
5. 在干净 Mac 上通过 Gatekeeper 验证和首次启动验证。

当前建议：**正式证书和公证凭据在你所在的发布机器上创建和保存**。另一台设备已经把仓库里的发布流水线、体检脚本、密钥模板和交接文档准备好；它不创建 Developer ID 证书，避免后续每次发版都依赖从另一台设备导出私钥。

## Apple Developer 账号现状

根据用户确认：

- Apple Developer 已经用顾源源的 Apple Developer 账号开通 1 年会员资格。
- 后续软件更新预计以你这台发布机器为主。
- 因此你这台机器应作为主发布机器，负责生成 Developer ID 证书、保存私钥、执行正式打包、公证和发版验证。

需要你登录 Apple Developer / App Store Connect 后确认，但当前仓库无法自动确认的信息：

- Apple Developer Team ID。
- Apple Developer 后台显示的主体名称是个人还是组织。
- 你的账号是否具备创建证书和 App Store Connect API Key 的权限。
- 是否已启用双重认证。

## 关键规则

### 证书不是只能创建一张

同一个 Apple Developer 团队可以创建多张 Developer ID 证书。Apple 帮助文档当前说明：可以创建最多 5 张 `Developer ID Application` 证书，以及最多 5 张 `Developer ID Installer` 证书。

### 证书记录和私钥不是一回事

证书记录在 Apple Developer 后台，但私钥只在创建证书请求的那台 Mac 的钥匙串里。

所以：

- 如果你这台发布机器创建证书，你的钥匙串天然拥有私钥，后续发布最方便。
- 如果另一台设备创建证书，你这台发布机器不能自动获得私钥，必须由对方导出 `.p12` 再安全交给你。
- 为了后续更新方便，本项目建议由你这台发布机器自己创建证书。

### 不上架 App Store 仍然需要签名和公证

Mac App Store 之外分发的 app，需要 Developer ID 证书签名并提交 Apple notarization，才能在默认 Gatekeeper 设置下获得正常打开体验。Apple 文档也说明，notarization 成功后会生成 ticket，可以 staple 到软件上，也会发布在线供 Gatekeeper 查询。

### 证书和密钥绝不能进仓库

不能提交：

- `.env.release`
- `.p8`
- `.p12`
- `.cer`
- `.certSigningRequest`
- Apple ID 密码或 app-specific password
- API Key ID / Issuer ID 与 `.p8` 的组合

仓库 `.gitignore` 已经排除这些敏感文件，但执行前仍要用 `git status` 自查。

## 另一台设备已完成并提交给仓库的事

以下是仓库资产，不依赖那台设备的本地状态。你拉到最新代码后应能看到这些文件和命令。

发布配置已经在仓库里：

- `package.json`
  - `build.appId`: `com.yiyu.selfworkbench2`
  - `build.productName`: `益语智库自用平台 V2.0`
  - `mac.hardenedRuntime: true`
  - `mac.forceCodeSigning: true`
  - `mac.notarize: true`
  - `mac.entitlements`: `build-resources/entitlements.mac.plist`
  - `mac.entitlementsInherit`: `build-resources/entitlements.mac.inherit.plist`
- `build-resources/icon.icns`
- `build-resources/entitlements.mac.plist`
- `build-resources/entitlements.mac.inherit.plist`

发布命令已经接好：

```bash
npm run release:mac:doctor
npm run release:mac:doctor:strict
npm run release:mac
npm run release:mac:verify-dmg
```

辅助文件已经准备：

- `.env.release.example`
- `scripts/inspect-mac-release-readiness.mjs`
- `scripts/ensure-mac-release-prereqs.mjs`
- `scripts/verify-packaged-app.mjs`
- `scripts/verify-mac-dmg.mjs`
- `docs/developer-id-signing-notarization.md`
- `docs/release-process.md`

另一台设备已验证：

- 体检脚本能正常运行。
- Xcode Command Line Tools 里的 `notarytool` 和 `stapler` 可用。
- 另一台设备当前没有 Developer ID Application 证书。
- 另一台设备当前没有 notarization 凭据。
- 另一台设备磁盘空间不足以跑完整正式构建。

这些验证只说明：**仓库流水线已铺好，但正式证书和凭据应在你这台发布机器完成。**不要把另一台设备的证书缺失或磁盘不足理解为你这台机器也必然如此；你要以这台发布机器的体检输出为准。

## 建议什么时候开始

建议分两个时间点：

### 现在可以开始

你这台发布机器可以现在就做：

1. 拉取最新代码。
2. 跑发布体检，确认缺什么。
3. 在 Apple Developer 后台创建 Developer ID Application 证书。
4. 创建 App Store Connect API Key。
5. 在你这台机器保存 `.env.release`。
6. 跑到 `release:mac:doctor:strict` 通过。

这些动作不要求当前软件功能已经最终定版，因为证书和发布环境是长期能力。

### 等版本确认后再开始

等要给外部用户或正式测试用户发包时，再做：

1. 确认当前 `main` 或发布分支就是要发的版本。
2. 确认版本号、更新说明和回滚方案。
3. 执行 `npm run release:mac`。
4. 验证 DMG 和首次启动。
5. 上传分发。

不要在功能还未确认、分支不干净、或本地装错版本风险未排除时制作正式发布包。

## 你的执行流程

以下步骤由你在这台发布机器上执行。

### 第 0 步：确认代码基线

```bash
git status -sb
git branch --show-current
git rev-parse HEAD
git remote -v
```

要求：

- 当前代码是准备发布的 2.0 仓库。
- 不在 1.0 仓库。
- 不把未确认的本地脏改动混进正式包。
- 若需要发布你这台机器上的最新版本，先确保改动已提交或明确保留。

### 第 1 步：确认工具链

```bash
xcode-select --install
xcrun -f notarytool
xcrun -f stapler
```

如果 `xcode-select --install` 提示已经安装，可以忽略。

### 第 2 步：运行仓库体检

```bash
npm run release:mac:doctor
```

第一次运行大概率会提示：

- 缺 Developer ID Application identity。
- 缺 notarization credentials。

这是正常的。

### 第 3 步：在你这台发布机器创建 Developer ID Application 证书

推荐用你这台机器创建 CSR 和证书，确保私钥留在你的钥匙串里。

大致流程：

1. 打开“钥匙串访问”。
2. 菜单选择“证书助理”。
3. 选择“从证书颁发机构请求证书”。
4. 保存 `.certSigningRequest` 到你这台机器的临时位置。
5. 登录 Apple Developer 后台。
6. 创建 `Developer ID Application` 证书。
7. 上传 CSR。
8. 下载证书并双击安装。
9. 删除或妥善保存 CSR，不提交仓库。

验证：

```bash
security find-identity -v -p codesigning
```

应看到类似：

```text
Developer ID Application: <个人或组织名称> (<TEAMID>)
```

当前项目发布 `.app` / `.dmg` / `.zip`，优先只需要 `Developer ID Application`。如果以后改 `.pkg` 安装器，再补 `Developer ID Installer`。

### 第 4 步：创建 notarization 凭据

推荐 App Store Connect API Key，不推荐长期依赖个人 Apple ID + app-specific password。

在 Apple Developer / App Store Connect 里创建 API Key 后，得到：

- `AuthKey_XXXXXXXXXX.p8`
- Key ID
- Issuer ID

在仓库根目录执行：

```bash
cp .env.release.example .env.release
```

填入：

```bash
APPLE_API_KEY="/absolute/path/to/AuthKey_XXXXXXXXXX.p8"
APPLE_API_KEY_ID="XXXXXXXXXX"
APPLE_API_ISSUER="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

加载环境变量：

```bash
set -a
source .env.release
set +a
```

再次确认没有把密钥放进 git：

```bash
git status -sb
```

### 第 5 步：严格体检

```bash
npm run release:mac:doctor:strict
```

通过后再进入正式构建。

如果失败，先按输出修复，不要绕过。

### 第 6 步：正式构建、签名、公证

正式构建前建议磁盘至少预留 8 GiB。

```bash
npm run release:mac
```

这个命令会执行：

1. 发布前置检查。
2. 前端/主进程/后端构建。
3. packaged runtime 构建。
4. electron-builder Mac DMG/ZIP 构建。
5. Developer ID 签名。
6. notarization。
7. packaged app 验证。

### 第 7 步：验证 DMG

把实际产物路径传给验证命令：

```bash
npm run release:mac:verify-dmg -- "dist/益语智库自用平台 V2.0-0.1.0-arm64.dmg"
```

如果文件名不同，以 `dist/` 下实际 DMG 为准。

还可以手动验证：

```bash
codesign --verify --deep --strict --verbose=4 "dist/mac-arm64/益语智库自用平台 V2.0.app"
codesign -dv --verbose=4 "dist/mac-arm64/益语智库自用平台 V2.0.app"
spctl --assess --type execute --verbose=4 "dist/mac-arm64/益语智库自用平台 V2.0.app"
xcrun stapler validate "dist/mac-arm64/益语智库自用平台 V2.0.app"
```

预期：

- `codesign` 通过。
- 签名身份显示 `Developer ID Application`。
- 能看到 Team ID。
- `spctl` accepted。
- `stapler validate` 通过。

### 第 8 步：干净机器首次启动验证

最好用另一台未装过开发版的 Mac 验证：

1. 从最终下载链接下载 DMG。
2. 打开 DMG。
3. 拖入 Applications。
4. 首次启动。
5. 确认不会出现“无法验证开发者”阻断。
6. 登录、打开主要模块、确认本地后端启动成功。

## 如果你以后要把发布能力交给另一台机器

有两种方式：

### 推荐：另一台机器自己创建证书

适合长期由另一台机器发布。

### 可选：导出 `.p12`

如果必须复用同一张证书：

1. 在钥匙串访问里导出含私钥的 `.p12`。
2. 设置强密码。
3. 用安全渠道传输 `.p12`。
4. 密码用另一个渠道传。
5. 导入后用 `security find-identity -v -p codesigning` 验证。

`.p12` 绝不能进仓库或普通同步目录。

## 常见判断

### 另一台设备是否还要创建证书？

不建议。另一台设备已经完成发布脚手架；正式更新以后以你这台发布机器为主，就让你这台机器持有证书私钥。

### 当前代码没最终定版，是否能先创建证书？

可以。证书是发布能力，不绑定某一版代码。正式 DMG 等版本确认后再构建即可。

### 每次更新都要重新申请证书吗？

不用。证书有效期内复用即可。每次新版本都要重新签名、重新 notarization，因为签名绑定具体 app bundle 内容。

### 可以只签 app，不公证吗？

不建议。官网分发目标是减少 Gatekeeper 阻断；签名和公证要作为一套链路。

### 可以把 `.env.release` 提交给别人吗？

不可以。`.env.release.example` 可以提交；真实 `.env.release` 只留在发布机器。

## 当前不包含

- Mac App Store 上架。
- 自动更新链路。
- `.pkg` 安装器。
- 云端定时发布。
- 多架构 universal 包。

这些可以后续再做。

## 官方依据

- Developer ID: https://developer.apple.com/developer-id/
- 创建 Developer ID 证书: https://developer.apple.com/help/account/create-certificates/create-developer-id-certificates/
- Mac App Store 外分发: https://help.apple.com/xcode/mac/current/en.lproj/dev033e997ca.html
- 公证 macOS 软件: https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution
- macOS 代码签名与 Gatekeeper: https://support.apple.com/guide/security/app-code-signing-process-in-macos-sec3ad8e6e53/web
