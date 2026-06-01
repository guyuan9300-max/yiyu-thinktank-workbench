# Codex 可执行发布手册：Mac 正式版到火山云 TOS

## 触发语

当开发同事说：

> 我已经提交最新修改到 main，你可以发布新版本了

你要执行的是正式发版：从私有 GitHub `main` 拉取最新代码，构建签名并公证的 macOS 包，上传到益语官方火山云 TOS 更新源，让普通用户通过“检查更新”升级。

不要把它理解为：

- 本机调试安装
- `dist:mac-local` 未签名包
- 普通 GitHub 同步
- 给普通用户开放维护模式

## 固定链路

- 开发协作源：私有 GitHub 仓库 `origin/main`
- 用户更新源：`https://yiyu-thinktank-releases.tos-cn-beijing.volces.com/desktop/mac/`
- 更新清单：`latest-mac.yml`
- 用户首次安装：DMG
- 应用内更新：ZIP + blockmap + `latest-mac.yml`

用户自己的组织云、对象存储、AI 配置不影响软件更新源。

## 一次性环境要求

发布机必须具备：

- macOS
- 可用的 `Developer ID Application` 证书
- Apple notarization 凭据
- Xcode Command Line Tools，包括 `notarytool` 和 `stapler`
- 已配置的 `tosutil`
- TOS 写权限，目标 bucket 为 `yiyu-thinktank-releases`

`tosutil` 配置方式：

```bash
tosutil config -i <AK> -k <SK> -e tos-cn-beijing.volces.com
```

AK/SK、Apple 密钥、GitHub 凭据不得写入仓库。

## 标准发布命令

优先使用总入口：

```bash
git checkout main
git pull --ff-only origin main
npm run release:mac:tos
```

总入口会按顺序执行：

1. 确认当前分支是 `main`。
2. 检查已跟踪文件没有未提交修改。
3. 拉取 `origin/main` 最新提交。
4. 读取并展示 `package.json` 版本号。
5. 运行 `npm run release:mac:doctor:strict`。
6. 运行 `npm run release:mac`。
7. 运行 `npm run release:mac:verify-dmg`。
8. 运行 `npm run release:mac:publish:dry`。
9. 运行 `npm run release:mac:publish`。
10. 验证 TOS 公网 URL。

## 手动拆解流程

如果总入口失败，需要拆开排查时，按这个顺序执行：

```bash
git status --short
git checkout main
git pull --ff-only origin main
npm run release:mac:doctor:strict
npm run release:mac
npm run release:mac:verify-dmg
npm run release:mac:publish:dry
npm run release:mac:publish
```

不要跳过 `doctor:strict`、DMG 验证或 dry-run。

## 上传顺序

发布脚本必须遵守：

1. 先上传 DMG。
2. 再上传 ZIP。
3. 再上传 ZIP blockmap。
4. 最后上传 `latest-mac.yml`。

原因：客户端第一时间读取 `latest-mac.yml`。如果清单先发布而安装包还没上传完，用户会遇到 404 或更新失败。

## 发布完成后的输出

发布成功后，必须告诉开发同事：

- 发布版本号。
- 更新清单 URL：`https://yiyu-thinktank-releases.tos-cn-beijing.volces.com/desktop/mac/latest-mac.yml`
- DMG URL。
- ZIP / blockmap URL 验证已通过。
- 下一步：用旧版软件点击“检查更新”，确认能发现、下载并安装新版。

## Failure Handling

### 缺 Apple 证书或公证配置

停止发布。提示开发同事先配置 Developer ID / notarization。不要改用 `dist:mac-local` 顶替正式包。

### 缺 TOS 写入凭证

停止发布。提示配置 `tosutil`。不得把 AK/SK 写入仓库、文档或环境模板的真实值。

### 有已跟踪文件未提交

停止发布。要求先提交或撤销。未跟踪文件可以提醒，但不默认阻止。

### 构建、签名或公证失败

停止发布。保留错误日志。不要上传半成品。

### dry-run 文件列表异常

停止发布。重点检查版本号、artifact 名称、`dist/latest-mac.yml` 是否匹配当前版本。

### 上传失败

不得宣布发布完成。若 `latest-mac.yml` 尚未上传，修复后重跑发布即可。若清单已经上传但安装包不可用，按 `docs/release-rollback.md` 先恢复上一版清单。

### 更新源 404

优先检查：

- `latest-mac.yml` 是否在 `desktop/mac/` 前缀。
- TOS bucket 是否允许公开读。
- URL 是否仍是 `yiyu-thinktank-releases.tos-cn-beijing.volces.com`。

### 旧版客户端无法更新

不要宣布发布完成。记录失败点，优先检查签名、公证、ZIP、blockmap、`latest-mac.yml` 的 `path` 和 `sha512`。

## 普通用户界面边界

普通用户只应该看到“检查更新”。不要让普通用户看到：

- GitHub 私有仓库
- 同步按钮
- 推送按钮
- 拉取按钮
- 发布到火山云按钮
- TOS 写入凭据

维护模式仍可服务内部开发，但不能作为普通用户更新方式。维护同步入口只能依据后端 `maintenance-mode/status` 返回的官方组织 ID 与授权状态显示；前端不得硬编码官方云地址，也不得仅凭组织名称猜测是否显示 GitHub 同步入口。

## 验收标准

- `latest-mac.yml`、DMG、ZIP、blockmap 全部可公网访问。
- 旧版软件能发现新版。
- 下载完成后能安装新版。
- 升级后用户数据目录不丢失。
- 普通用户界面不暴露开发同步与发布入口。
