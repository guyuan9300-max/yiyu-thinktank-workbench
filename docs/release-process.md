# 官网版 Mac 发版流程

## 目标

- 首次安装通过官网下载安装包完成。
- 后续版本通过软件内更新提示完成下载与安装。
- 发版动作由受控构建机或 CI 完成，不在普通用户机器上执行。

## 适用范围

- 渠道：`stable`、`beta`
- 平台：macOS 官网分发版
- 当前不包含：Mac App Store

## 角色分工

- 产品/主线程：
  - 决定版本号
  - 决定发布渠道
  - 确认版本说明
- 构建负责人：
  - 触发构建
  - 处理签名与公证
  - 上传产物与更新元数据
- 验收负责人：
  - 在干净机器验证安装
  - 验证更新发现、下载、安装链路

## 发布前检查

### 代码与构建

- 主分支已合入本次版本需要的改动。
- `npm run build:main` 通过。
- `npm run build:renderer` 通过。
- 如本次涉及后端协议或数据结构，相关测试已通过。

### 打包与凭据

- `Developer ID Application` 证书可用。
- notarization 凭据可用。
- `build-resources/icon.icns` 已准备。
- `build-resources/entitlements.mac.plist` 与 `build-resources/entitlements.mac.inherit.plist` 已准备。
- 下载域名与对象存储可访问。
- 本机若只是做功能自测，请改用 `npm run dist:mac-local`，不要拿它替代正式官网发布包。

签名、公证和申请材料详见：

- `docs/developer-id-signing-notarization.md`
- `docs/mac-developer-id-handoff-for-codex.md`

### 版本信息

- 版本号已写入 `package.json`。
- 已确定发布渠道：
  - `stable`
  - `beta`
- 已写好更新说明。

## 构建产物要求

每次发布至少要生成：

- `DMG`
- `ZIP`
- `latest-mac.yml`
- 对应 `blockmap`

说明：

- `DMG` 给官网首次下载安装使用。
- `ZIP + latest-mac.yml + blockmap` 给应用内更新使用。

## 发布步骤

推荐让开发同事机器上的 Codex 按 `docs/codex-release-runbook.md` 执行。触发语：

> 我已经提交最新修改到 main，你可以发布新版本了

对应总入口：

```bash
git checkout main
git pull --ff-only origin main
npm run release:mac:tos
```

手动拆解时按以下顺序：

1. 确认本次版本号与发布渠道。
2. 在受控构建机或 CI 执行 macOS 构建。
3. 对 `.app` 与产物完成签名。
4. 完成 notarization 并确认通过。
5. 将 DMG、ZIP、blockmap 上传到对应渠道目录。
6. 最后上传 `latest-mac.yml`，让客户端开始发现新版。
7. 更新官网手动下载入口：
   - `stable` 发布时更新官网主下载入口
   - `beta` 仅更新测试版入口
8. 在干净机器完成安装与启动验证。
9. 用旧版本客户端验证：
   - 可发现新版本
   - 可完成下载
   - 可完成重启安装
10. 记录发版日志。

## 发布后验证

### 手动安装验证

- 从官网下载安装 `DMG`
- 拖入 `~/Applications/益语智库自用平台.app`
- 首次启动成功
- 本地数据目录正常创建

### 唯一安装入口规则

- 日常运行与验证只认一个入口：
  - `~/Applications/益语智库自用平台.app`
- 不要直接从这些位置长期启动：
  - `dist/mac-arm64/*.app`
  - `~/Library/Application Support/yiyu-thinktank-workbench/runtime/local-electron/*.app`
  - `/Applications/益语智库.app`
- 如果本机做本地封装验证，先执行：
  - `npm run dist:mac-local`
  - `npm run install:mac-local`
- `npm run install:mac-local` 会把旧版本自动归档到：
  - `~/Library/Application Support/yiyu-thinktank-workbench/runtime/install-backups/`
- 如发现多个同名或旧名字应用并存，以设置页“版本与更新”中的“安装入口自检”为准，定位并清理旧入口。

### 应用内更新验证

- 使用上一版本客户端启动
- 能看到新版本提示
- 能开始下载
- 下载后能触发“重启并安装”
- 升级后版本号正确
- 升级后本地数据不丢失

## 渠道规则

### beta

- 用于内部测试与小范围试装。
- 允许更快发布。
- 问题可接受，但必须可回滚。

### stable

- 只在 `beta` 验证通过后发布。
- 官网默认下载入口始终指向 `stable`。

## 版本说明最小模板

- 版本号
- 发布日期
- 本次重点改动
- 已知限制
- 回滚说明（如有）

## 禁止事项

- 不要在普通用户电脑上执行签名、公证和上传。
- 不要发布未完成签名或未完成 notarization 的安装包。
- 不要只上传 `DMG` 而遗漏更新元数据。
- 不要把 `beta` 包误放进 `stable` 目录。
- 不要在 `npm run dist:mac` 前置检查失败时绕过脚本继续发布；那样产出的包会继续出现“闪一下就退出”。
- 不要把 `dist/mac-arm64/*.app` 直接当作长期使用入口；那样很容易继续出现“装错包/开错包”。

## 上传到火山云 OSS

正式构建完成后,产物在 `dist/`,需要上传到火山云 TOS bucket `yiyu-thinktank-releases` 的 `desktop/mac/` 前缀下,客户端 electron-updater 才能发现新版本。

### 一次性环境准备

- 安装火山云命令行 `tosutil`(参考 https://www.volcengine.com/docs/6349/148777)
- 在火山云控制台为发布账号生成 Access Key / Secret Key
- 配置一次:
  ```
  tosutil config -i <AK> -k <SK> -e tos-cn-beijing.volces.com
  ```
- AK/SK 严禁入仓库;放在发布机用户目录的标准 tosutil 配置中即可

### 每次发版的上传步骤

正式构建完成后:

```bash
npm run release:mac:tos            # 推荐:检查、构建、验证、预演、上传、URL 验证一条龙
```

如果需要拆开排查:

```bash
npm run release:mac:publish:dry    # 先预演,看要传的文件列表
npm run release:mac:publish        # 实际上传
```

脚本会上传 4 个文件:

- `yiyu-workbench-<version>-arm64.dmg` — 用户首次下载入口
- `yiyu-workbench-<version>-arm64.zip` — electron-updater 真正用来更新的产物(必须存在)
- `yiyu-workbench-<version>-arm64.zip.blockmap` — 增量更新差分用
- `latest-mac.yml` — 更新清单,electron-updater 第一个读的就是它(覆盖式替换 = 新版本立即生效)

注意：脚本会先传安装包和 blockmap，最后才覆盖 `latest-mac.yml`。不要手工反过来传，否则用户可能读到指向不存在文件的更新清单。

### 公开下载链接

- DMG: `https://yiyu-thinktank-releases.tos-cn-beijing.volces.com/desktop/mac/yiyu-workbench-<version>-arm64.dmg`
- 更新清单(给客户端用,人不需要点): 同前缀 + `latest-mac.yml`

### 回滚

如果新版上线后发现严重问题,**最快的回滚方式**是用 `tosutil` 把 `latest-mac.yml` 替换回上一版的:

- 把上一版本的 `latest-mac.yml` 重新覆盖上传到同一位置
- 还没下载完的客户端会改读旧清单,不会再升级到坏版本
- 已经下载完成但还没重启的客户端,可以提示用户先别点重启

更激进的回滚:

- 删除 OSS 上坏版本的 `.zip` 和 `.zip.blockmap`,正在下载的客户端会失败回退
- 不要删 `.dmg`,以免有用户正在通过链接首次下载

## 更新交付策略:飞书式静默

本产品采用"飞书式无感更新"——用户感知 = 0:

| 阶段 | 用户感知 | 实现 |
|---|---|---|
| 检查 | 无感(后台) | 启动 10s + 每 6h |
| 下载 | 无感(后台,差分 blockmap 几 MB) | `autoDownload = true` |
| 安装 | 无感(下次自然退出时静默替换 .app) | `autoInstallOnAppQuit = true` |
| 生效 | 下次打开就是新版 | macOS 启动 .app bundle |

**主界面不弹任何更新相关 UI**(`UpdateNotifier` 组件 mount 但只订阅事件不渲染 UI)。

主动入口在**设置 → 关于本软件**:
- 显示当前版本号 / 平台 / 通道
- 【检查更新】按钮(用户主动触发,有可见状态反馈)
- 【立即重启更新】按钮(仅当后台已下载完成时显示,给急着用新功能的用户)

错误也不打扰用户,只走 console.log + macOS Console.app 日志诊断。

维护同步入口与检查更新是两条链路:
- 【检查更新】始终读取益语官方火山云 TOS 更新源,不读取 GitHub。
- GitHub 推送/拉取只在内部维护模式下出现,且仅当登录账号连接益语智库官方云、组织识别为益语时显示。

如果未来想给重大版本加一次性"What's New"弹窗,可以基于 `window.__yiyuUpdateState__.downloadedVersion` 在启动时判断"上次还没看过新版日志"再弹一次。

## 当前阶段说明

- 自动更新引擎已通过 electron-updater 接入(2026-05-18)。
- 发布流水线已通过 `npm run release:mac:publish` 接入。
- 更新交付策略改为飞书式静默 + 设置页主动入口(2026-05-19)。
- 后续可补:CI 自动化、灰度发布(channel=beta vs stable)、增量更新效果监控、What's New 弹窗。
