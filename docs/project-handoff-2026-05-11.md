# 益语智库项目交接资料（2026-05-11）

## 0. 当前交接结论

当前最重要目标不是做正式发布，而是先产出一个“本机安装、打开、基础功能通过”的内部测试 DMG，再发给同事安装测试。

交接时必须先守住四件事：

1. 先确认源码、`dist` 产物、已安装 App、实际打开入口是一致的，再判断页面或功能是否正确。
2. 当前工作区不是干净状态，不能直接假设它就是可发布版本。
3. 数据库不要动。用户数据目录是 `~/Library/Application Support/YiyuThinkTankWorkbench2`，卸载或清理旧 App 时不要删除这个目录。
4. 本地服务默认端口是 `http://127.0.0.1:47829`。如果注册页提示“无法连接本地服务”，先排查本地后端启动和打包运行时，不要直接叠加 UI 兜底方案。

## 1. 项目与入口

- 仓库路径：`/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench`
- App ID：`com.yiyu.selfworkbench2`
- 产品名：`益语智库自用平台 V2.0`
- 当前安装脚本默认安装位置：`~/Applications/益语智库自用平台 V2.0.app`
- 打包后的 App 目录：`dist/mac-arm64/益语智库自用平台 V2.0.app`
- Apple Silicon 默认 DMG：`dist/益语智库自用平台 V2.0-0.1.0-arm64.dmg`
- 用户数据目录：`~/Library/Application Support/YiyuThinkTankWorkbench2`
- 安装冒烟证据默认目录：`~/Library/Application Support/YiyuThinkTankWorkbench2/runtime/main-chain-rc/v0.3.4`

入口一致性是当前第一风险。历史截图里出现过 `/Applications`、旧 App 名、Launchpad 多个重复图标等情况，但当前脚本主路径是 `~/Applications/益语智库自用平台 V2.0.app`。如果用户说“打开的页面不对”，先确认实际启动的是哪个 bundle，不要只看源码或 `dist`。

## 2. 主要代码分区

- `src/renderer/App.tsx`：前端主入口、登录注册页、身份门、主工作台。
- `src/main/main.ts`：Electron 主进程、本地服务启动、窗口和运行时连接。
- `src/shared/types.ts`：前后端共享类型，例如本机登录注册参数。
- `backend/app/main.py`：本地后端 API、账号、本地身份、记住登录状态等。
- `cloud_backend/app/main.py`：云端后端 API、云账号和组织相关逻辑。
- `scripts/`：打包、安装、验证、运行时检查和诊断脚本。
- `docs/`：发布流程、签名公证、更新方案和本交接文档。
- `mobile/`：移动端子仓库，目前工作区显示为 modified submodule。

## 3. 当前工作区状态

交接时看到的未提交变更如下：

```text
 M backend/app/main.py
 M backend/app/models.py
 M cloud_backend/app/main.py
 M cloud_backend/tests/test_local_first_auth.py
 m mobile
 M package.json
 M scripts/package-local-mac-dmg.mjs
 M src/main/main.ts
 M src/renderer/App.tsx
 M src/shared/types.ts
?? scripts/collect-mac-startup-diagnostics.command
```

这些变更大概率和本机优先登录注册、云端账号绑定、本地服务启动、打包诊断有关。接手人不要执行 `git reset` 或覆盖这些文件。正确做法是先确认这些修改是否都属于当前测试包，再决定提交、分支隔离或继续修复。

## 4. 登录与注册验收标准

首屏默认应该进入登录页，而不是注册页，也不是旧的云账号绑定弹窗。

登录页应满足：

- 页面整体居中，当前视觉目标是比最初大图缩小约 20%。
- 顶部 Tab 文案是“登录”和“注册”。
- 登录表单只保留账号、密码、找回密码。
- 增加“记住我的登录状态”勾选项。
- 输入账号密码时内容不能因为刷新或渲染分支切换而消失。

注册页应满足：

- 注册页分“个人注册”和“组织注册”。
- 个人注册字段：姓名、邮箱、密码、重复密码、组织邀请码。
- 组织注册在个人信息之外，还要有“组织全称”，要求填写工商或民政注册的组织全称。
- 底部盾牌只是装饰物，应该缩小并放在底部，不能遮挡说明文字。

云账号绑定弹窗属于已有本机身份后的云端连接流程，不应该替代干净安装后的登录注册首屏。若打开后直接出现“登录已有云账号绑定”，要优先排查本机会话状态、身份门判断和实际启动入口。

## 5. 常用命令

所有命令默认在仓库根目录执行：

```bash
cd /Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench

npm run dev
npm run build
npm run backend:test
npm run cloud:test

npm run dist:mac-local
node scripts/package-local-mac-dmg.mjs
node scripts/verify-mac-dmg.mjs
node scripts/install-and-smoke-mac-dmg.mjs --keep-running
node scripts/check-installed-runtime.mjs --force-relaunch
```

`scripts/install-and-smoke-mac-dmg.mjs` 默认会做 fresh runtime，但它清理的是可重建的 `runtime/backend-venv`，不是数据库。不要把它等同于删除用户数据。

## 6. 给同事前必须跑的本机包流程

内部测试包的交付标准是：本机安装并打开过，登录/注册首屏和基础交互手工确认过。

建议流程：

1. 先看工作区状态：

   ```bash
   git status --short
   ```

2. 构建：

   ```bash
   npm run build
   ```

3. 生成本地 macOS 产物：

   ```bash
   npm run dist:mac-local
   ```

4. 生成内部测试 DMG：

   ```bash
   node scripts/package-local-mac-dmg.mjs
   ```

5. 验证 DMG：

   ```bash
   node scripts/verify-mac-dmg.mjs
   ```

6. 安装并做自动冒烟：

   ```bash
   node scripts/install-and-smoke-mac-dmg.mjs --keep-running
   ```

7. 手工冒烟：

   - 打开确认是 `~/Applications/益语智库自用平台 V2.0.app`。
   - 首屏默认是登录页。
   - 登录页字段、找回密码、记住登录状态存在。
   - 注册页个人/组织切换和字段正确。
   - 输入账号、密码时内容不会突然消失。
   - 关闭再打开后，记住登录状态表现符合预期。

8. 记录脚本输出里的 DMG 路径和 `sha256`，再发给同事。

注意：`dist:mac-local` 和 `package-local-mac-dmg.mjs` 产出的是内部本地测试包，不是签名公证完成的正式发布包。正式分发仍需要 Developer ID 签名、公证和更新元数据闭环。

## 7. 系统性排查路径

### 7.1 打开的是旧页面或旧 App

先查真实启动入口：

```bash
pgrep -af "益语|Yiyu|Electron"
mdfind "kMDItemFSName == '益语智库自用平台 V2.0.app'"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -dump | rg "益语|selfworkbench"
node scripts/check-installed-runtime.mjs --force-relaunch
```

如果 Launchpad 或 Finder 里有多个旧副本，优先把旧 `.app` 移到废纸篓，但保留 `~/Library/Application Support/YiyuThinkTankWorkbench2`。

### 7.2 源码和包不一致

验证 `dist` 中的 App：

```bash
node scripts/verify-packaged-app.mjs "dist/mac-arm64/益语智库自用平台 V2.0.app"
node scripts/check-installed-runtime.mjs --source-app "dist/mac-arm64/益语智库自用平台 V2.0.app" --force-relaunch
```

如果源码已经改了但包里没有，重新执行 `npm run build`、`npm run dist:mac-local`、`node scripts/package-local-mac-dmg.mjs`。

### 7.3 注册页提示无法连接本地服务

先看端口和日志：

```bash
lsof -nP -iTCP:47829 -sTCP:LISTEN
tail -n 200 "$HOME/Library/Application Support/YiyuThinkTankWorkbench2/electron-launch.log"
scripts/collect-mac-startup-diagnostics.command
```

重点判断：

- Electron 主进程有没有启动本地后端。
- 打包运行时是否包含 `Contents/Resources/runtime`。
- 后端虚拟环境是否损坏或还没初始化完成。
- 前端是否过早请求 API，导致用户看到“无法连接本地服务”。

### 7.4 输入内容突然消失

不要先加新的兜底状态。先排查：

- Renderer 是否发生整页 reload。
- `authState`、`currentSessionUser`、`shouldShowIdentityGate` 是否让页面从 auth 分支跳到 identity/main 分支再回来。
- 后端 ready 状态变化是否触发了表单组件重挂载。
- 登录/注册组件 key 是否因为状态变化而变化。
- 记住账号和记住密码逻辑是否在输入中途覆盖本地输入。

## 8. 数据库保护边界

可以清理：

- 旧的 `.app` 副本。
- `dist/` 中旧构建产物。
- 可重建的 `~/Library/Application Support/YiyuThinkTankWorkbench2/runtime/backend-venv`。

不要清理：

- `~/Library/Application Support/YiyuThinkTankWorkbench2/app.db`
- `~/Library/Application Support/YiyuThinkTankWorkbench2` 整个目录
- 用户导入文档、工作台数据、运行证据中还需要复盘的日志

如果要模拟干净安装，应先复制或备份用户数据目录，再做隔离测试。不要用删除数据库的方式验证安装问题。

## 9. 已知风险

- 工作区 dirty，未提交变更范围较大。
- 安装路径和旧文档存在不一致：当前脚本用 `~/Applications/益语智库自用平台 V2.0.app`，部分旧流程可能仍写 `/Applications` 或无 `V2.0` 的旧名称。
- 内部测试 DMG 未签名未公证，不能当正式发布包。
- 软件内更新方向已明确，但正式 updater 和发布元数据闭环还没有完全完成。
- 云端默认地址仍有 HTTP 地址使用痕迹，正式发布前要确认 HTTPS 和证书。
- “输入时内容消失”的根因需要通过 reload/分支切换/组件重挂载继续确认。
- 干净电脑失败的判断不能只基于当前电脑，必须用同一个 DMG 做本机安装冒烟，再让同事测试。
- `mobile` 子仓库显示 modified，交接时要单独确认是否相关。

## 10. 相关资料

- 发布流程：`docs/release-process.md`
- Mac 更新方案：`docs/mac-release-update-plan.md`
- 签名公证：`docs/developer-id-signing-notarization.md`
- 应用清单：`scripts/app-manifest.mjs`
- 本地 DMG 打包：`scripts/package-local-mac-dmg.mjs`
- 安装并冒烟：`scripts/install-and-smoke-mac-dmg.mjs`
- 已安装运行时检查：`scripts/check-installed-runtime.mjs`
- 打包 App 验证：`scripts/verify-packaged-app.mjs`
- 启动诊断：`scripts/collect-mac-startup-diagnostics.command`
