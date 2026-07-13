# AGENTS.md - 益语智库工作台 2.0

## 发布新版本

当用户或开发同事说：

> 我已经提交最新修改到 main，你可以发布新版本了

Codex 必须把这理解为“构建正式签名、公证安装包并发布到益语智库官网后台”，而不是普通本地安装、GitHub 同步或生成未签名测试包。

执行前先读：

- `docs/codex-release-runbook.md`
- `docs/release-process.md`
- `docs/developer-id-signing-notarization.md`
- `docs/release-rollback.md`

默认从最新 `main` 构建并验证签名、公证安装包，再到官网后台“版本发布”上传、填写版本说明并发布。

关键规则：

- 正式用户更新源是 `https://yiyu.love`，不是 GitHub 或组织云。
- 未连接组织读取官网公开版；已连接组织优先读取官网定向版，否则回落公开版。
- 普通用户不需要也不应该看到 GitHub 同步、推送、拉取或发布入口；维护同步入口仅在登录账号连接益语智库官方云且组织识别为益语时显示。
- 不得发布未签名、未公证或 `dist:mac-local` 产物。
- 不得把 Apple、官网后台或 GitHub 密钥写入仓库。
- 官网发布完成后必须验证版本接口、安装包 URL、SHA512、HEAD 与 Range/206，并用旧版软件点击“检查更新”做端到端验收。
- 包含官网更新链路的首个迁移版本仍需在官网和旧 TOS 双发一次；确认用户完成迁移后，不再更新 TOS。
