# AGENTS.md - 益语智库工作台 2.0

## 发布新版本

当用户或开发同事说：

> 我已经提交最新修改到 main，你可以发布新版本了

Codex 必须把这理解为“发布正式 macOS 官网分发版到火山云 TOS 更新源”，而不是普通本地安装、GitHub 同步或生成未签名测试包。

执行前先读：

- `docs/codex-release-runbook.md`
- `docs/release-process.md`
- `docs/developer-id-signing-notarization.md`
- `docs/release-rollback.md`

默认执行：

```bash
git checkout main
git pull --ff-only origin main
npm run release:mac:tos
```

关键规则：

- 正式用户更新源是火山云 TOS，不是 GitHub。
- 普通用户不需要也不应该看到 GitHub 同步、推送、拉取或发布入口；维护同步入口仅在登录账号连接益语智库官方云且组织识别为益语时显示。
- 不得发布未签名、未公证或 `dist:mac-local` 产物。
- 不得把 Apple、TOS、GitHub 密钥写入仓库。
- 上传必须先传 DMG/ZIP/blockmap，最后上传 `latest-mac.yml`。
- 发布完成后必须验证 TOS 上的 `latest-mac.yml` 和安装包 URL，并提醒用旧版软件点击“检查更新”做端到端验收。
