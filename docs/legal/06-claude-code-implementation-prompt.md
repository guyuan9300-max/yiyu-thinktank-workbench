# 法律组件实施任务（给 Claude Code 的指令）

> 这是 Cowork 那边的 Claude 写给你（终端版 Claude Code）的实施任务包。
> 8 个子任务、6 个 commit、约 1 周工作量、每步停下报告。
>
> **任务总目标**：把首启同意弹窗 + 关于面板 + 账号删除流程落到代码，对齐 PIPL §17 §22 §15 与 App Store §5.1.1(ii) §5.1.1(v) 强制要求。

---

## 第 0 阶段：前置检查（必须完成才进入第 1 阶段）

### 0.1 工作位置确认

**默认工作目录**：`~/.openclaw/workspace/yiyu-thinktank-workbench/`（原仓库）

⚠️ **不在副本（`~/Desktop/yiyu-cleanup-test-*`）里做法律工作**，因为副本随时可能被验收失败后删除。

### 0.2 cleanup-plan 进度依赖

```bash
cd ~/.openclaw/workspace/yiyu-thinktank-workbench
git log --oneline -10
```

期望状态：

- 如果原仓库 main 已经吸收了副本的 6 个 cleanup commit（docs / runtime / packaging / workspace 等）→ 进入第 1 阶段
- 如果还没吸收 → **先去把 cleanup 完成并推回原仓库**，本任务暂缓
- 如果根本没开始 cleanup → 跟用户确认次序，建议先 cleanup 再 legal

### 0.3 报告给用户

在 0.1 和 0.2 完成后，给 Cowork 那边的用户报告：

```
0 阶段完成：
- 当前工作目录：~/.openclaw/workspace/yiyu-thinktank-workbench
- 当前 HEAD：<commit hash> <subject>
- cleanup-plan 状态：已合并 / 进行中 / 未开始
- 是否可以进入第 1 阶段：是 / 否（原因：...）

等用户回 "继续" 再进第 1 阶段。
```

---

## 第 1 阶段：建分支 + 目录骨架

### 1.1 切分支

```bash
git checkout -b feature/legal-components
```

### 1.2 建目录

```bash
mkdir -p src/renderer/components/legal
mkdir -p docs/legal/generated   # 这是 build 时生成的 HTML，加到 .gitignore
mkdir -p docs/legal/archive     # 历史版本归档
```

### 1.3 .gitignore 更新

```bash
echo "" >> .gitignore
echo "# Generated legal HTML files (rebuild via docs/legal/scripts/md-to-html.mjs)" >> .gitignore
echo "docs/legal/generated/" >> .gitignore
```

### 1.4 Commit & 报告

```bash
git add .gitignore src/renderer/components/legal/ docs/legal/
git status --short
git commit -m "chore(legal): bootstrap legal components dir + .gitignore"
```

**🛑 停下来报告**：git log 顶部 commit、变更行数。等用户回 "继续 第2阶段" 再进。

---

## 第 2 阶段：Markdown→HTML 转换脚本（最先做，后续依赖它）

### 2.1 装依赖

```bash
npm install --save-dev markdown-it@14 --no-audit --no-fund
# 不要用 npm ci，避免之前的 EBADPLATFORM 问题
```

### 2.2 写脚本

新建 `docs/legal/scripts/md-to-html.mjs`，要求：

- 输入：`docs/legal/01-user-agreement.md` 和 `02-privacy-policy.md`
- 输出：`docs/legal/generated/user-agreement.html` 和 `privacy-policy.html`
- HTML 必须：
  - UTF-8 + lang="zh-CN"
  - 嵌入 minimal CSS（白底黑字、最大宽度 720px、行高 1.7、表格有边框）
  - 顶部加固定 sticky header "益语智库 - 用户协议 / 隐私政策 - 版本 v1.0"
  - 启用 markdown-it 的 table + linkify 插件
- 同时输出一份给官网部署用的版本：`docs/legal/generated/user-agreement-web.html`（含外部 CSS 链接占位、SEO meta、og 标签）

脚本 CLI：

```bash
node docs/legal/scripts/md-to-html.mjs           # 转两份默认文档
node docs/legal/scripts/md-to-html.mjs --web    # 也生成 -web.html
node docs/legal/scripts/md-to-html.mjs --watch  # watch 模式（开发用）
```

### 2.3 试跑

```bash
node docs/legal/scripts/md-to-html.mjs
ls -la docs/legal/generated/
# 期望看到 user-agreement.html 和 privacy-policy.html
# 跑 file size 确认 > 5KB（不能是空白）
```

### 2.4 Commit & 报告

```bash
git add package.json package-lock.json docs/legal/scripts/md-to-html.mjs
git status --short
git commit -m "feat(legal): markdown-to-html converter for in-app and web display

- New script: docs/legal/scripts/md-to-html.mjs
- Generates clean HTML from user-agreement.md and privacy-policy.md
- In-app version: minimal inline CSS, sticky header
- Web version: --web flag, includes SEO meta + og tags
- Output: docs/legal/generated/ (gitignored)"
```

**🛑 停下来报告**：commit hash + 生成的 HTML 文件大小。

---

## 第 3 阶段：IPC + Consent 持久化（主进程层）

### 3.1 新增 IPC handlers

修改 `src/main/main.ts`，新增以下 IPC handlers（按"在已有 IPC 注册区域追加"原则，不打散现有代码）：

```typescript
// 法律文档相关 IPC（约在文件靠后位置已有 ipcMain.handle 集中处）

ipcMain.handle('legal:get-document', async (_event, name: string) => {
  // 验证 name 是白名单
  if (!['user-agreement', 'privacy-policy'].includes(name)) {
    throw new Error(`unsupported legal document: ${name}`);
  }
  // 优先读 packaged Resources，dev 时 fallback 到源码路径
  const candidates = [
    path.join(process.resourcesPath, 'legal', `${name}.html`),
    path.join(projectRoot, 'docs', 'legal', 'generated', `${name}.html`),
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) {
      return { html: fs.readFileSync(p, 'utf-8'), source: p };
    }
  }
  throw new Error(`legal document not found: ${name}`);
});

const LEGAL_CONSENT_FILE = path.join(fixedUserDataPath, 'legal-consent.json');
const CURRENT_LEGAL_VERSION = '1.0';

ipcMain.handle('legal:get-consent', async () => {
  if (!fs.existsSync(LEGAL_CONSENT_FILE)) return null;
  try {
    return JSON.parse(fs.readFileSync(LEGAL_CONSENT_FILE, 'utf-8'));
  } catch (error) {
    logElectronError(`legal-consent.json corrupt: ${error}`);
    return null;
  }
});

ipcMain.handle('legal:set-consent', async (_event, payload: {
  acceptedDocuments: Array<{ name: string; version: string }>;
}) => {
  const record = {
    version: CURRENT_LEGAL_VERSION,
    acceptedAt: new Date().toISOString(),
    acceptedDocuments: payload.acceptedDocuments,
    userAgent: `yiyu-workbench/${app.getVersion()} ${os.platform()} ${os.release()} ${os.arch()}`,
    ipAddress: null, // 本机模式不记录
  };
  fs.mkdirSync(path.dirname(LEGAL_CONSENT_FILE), { recursive: true });
  fs.writeFileSync(LEGAL_CONSENT_FILE, JSON.stringify(record, null, 2), 'utf-8');
  return record;
});

ipcMain.handle('legal:withdraw-consent', async () => {
  if (fs.existsSync(LEGAL_CONSENT_FILE)) {
    fs.unlinkSync(LEGAL_CONSENT_FILE);
  }
  return { withdrawn: true };
});

ipcMain.handle('legal:get-version-info', async () => {
  return {
    appVersion: app.getVersion(),
    commitHash: process.env.YIYU_COMMIT_HASH || 'dev',
    buildTime: process.env.YIYU_BUILD_TIME || 'dev',
    legalVersion: CURRENT_LEGAL_VERSION,
    runtimeMode: app.isPackaged ? 'packaged' : 'dev',
    userDataDir: fixedUserDataPath,
  };
});
```

### 3.2 preload.ts 暴露 API

修改 `src/main/preload.ts`，在 contextBridge 暴露：

```typescript
contextBridge.exposeInMainWorld('legalAPI', {
  getDocument: (name) => ipcRenderer.invoke('legal:get-document', name),
  getConsent: () => ipcRenderer.invoke('legal:get-consent'),
  setConsent: (payload) => ipcRenderer.invoke('legal:set-consent', payload),
  withdrawConsent: () => ipcRenderer.invoke('legal:withdraw-consent'),
  getVersionInfo: () => ipcRenderer.invoke('legal:get-version-info'),
});
```

### 3.3 类型声明

在 `src/renderer/types/global.d.ts`（如不存在则新建）：

```typescript
interface LegalAPI {
  getDocument(name: 'user-agreement' | 'privacy-policy'): Promise<{ html: string; source: string }>;
  getConsent(): Promise<LegalConsentRecord | null>;
  setConsent(payload: { acceptedDocuments: Array<{ name: string; version: string }> }): Promise<LegalConsentRecord>;
  withdrawConsent(): Promise<{ withdrawn: true }>;
  getVersionInfo(): Promise<VersionInfo>;
}

interface LegalConsentRecord {
  version: string;
  acceptedAt: string;
  acceptedDocuments: Array<{ name: string; version: string }>;
  userAgent: string;
  ipAddress: string | null;
}

interface VersionInfo {
  appVersion: string;
  commitHash: string;
  buildTime: string;
  legalVersion: string;
  runtimeMode: 'packaged' | 'dev';
  userDataDir: string;
}

declare global {
  interface Window {
    legalAPI: LegalAPI;
  }
}

export {};
```

### 3.4 验证

```bash
npm run build 2>&1 | tail -20      # 确认编译通过
# 不需要装运行，IPC handler 的功能下个阶段再测
```

### 3.5 Commit & 报告

```bash
git add src/main/main.ts src/main/preload.ts src/renderer/types/
git diff --cached --stat
git commit -m "feat(legal): IPC + consent persistence in main process

- 5 new IPC handlers: get-document, get-consent, set-consent, withdraw-consent, get-version-info
- Consent stored at <userData>/legal-consent.json
- Documents loaded from packaged Resources or dev source path fallback
- preload exposes window.legalAPI with TypeScript types"
```

**🛑 停下来报告**：commit hash + main.ts 改动行数。

---

## 第 4 阶段：渲染层 - ConsentDialog（首启弹窗）

### 4.1 新建 ConsentDialog 组件

`src/renderer/components/legal/ConsentDialog.tsx`，要求：

- Modal 居中显示，遮罩层 z-index: 9999（最高，盖在 AuthShell 之上）
- 包含两段说明 + 复选框 + "查看完整内容"按钮 + 同意/稍后按钮
- 默认复选框未勾选；未勾选时"同意并继续"按钮禁用（灰）
- 点击"查看完整内容"打开内嵌 `LegalDocViewer`
- 同意后调用 `window.legalAPI.setConsent(...)` 保存
- 设计上参考 `docs/legal/04-integration-guide.md` §2.2 的 ASCII 示意

UI 风格对齐项目现有：

- 使用 Tailwind 类（项目已用）
- 圆角 2xl、按钮 bg-[#5B7BFE]、灰色边框 #E5E7EB

### 4.2 新建 LegalDocViewer 组件

`src/renderer/components/legal/LegalDocViewer.tsx`，要求：

- 全屏遮罩 modal（z-index 比 ConsentDialog 高 1，约 10000）
- 顶部 sticky header 显示 "用户协议" 或 "隐私政策"
- 内容区调用 `window.legalAPI.getDocument(name)` 拉 HTML，用 dangerouslySetInnerHTML 渲染
- 右上角 X 关闭按钮
- 内容区 max-width 720px，overflow-y auto，max-height 80vh
- 内嵌 CSS 用 prose 风格

### 4.3 新建 ConsentGate 包装

`src/renderer/components/legal/ConsentGate.tsx`，要求：

- 一个高阶组件 / Wrapper，在 App 渲染前 useEffect 检查 consent
- 若未 consent 或 version 不匹配，渲染 `<ConsentDialog>` 覆盖所有内容
- 已 consent 后 transparent passthrough children

⚠️ **重要**：ConsentGate 必须定义在 App 函数外（顶级声明）。如果嵌套在 App 内部，会触发跟 AuthShell 一样的"内联组件重挂载"bug（详见 docs/handoff-followup-2026-05-11.md §3）。

### 4.4 集成到 App.tsx

在 `src/renderer/App.tsx`，找到顶层 `<div>` 包裹位置（约 `return <AuthShell />` / `return <IdentityGate />` 之前），用 `<ConsentGate>` 包一层。具体位置：

- 在 line 23292 附近的 `return (...)` 整体外层包一层

⚠️ **不要**改动 AuthShell 内联组件结构（那是另一个 bug，留给单独的 commit 修）。这里只是在最外层加 ConsentGate。

### 4.5 验证（不重启 App，先 build 通过）

```bash
npm run build 2>&1 | tail -20
# 必须编译通过，无 TS 错误
```

### 4.6 Commit & 报告

```bash
git add src/renderer/components/legal/ src/renderer/App.tsx
git diff --cached --stat
git commit -m "feat(legal): ConsentDialog + LegalDocViewer + ConsentGate

- ConsentDialog: first-launch modal with checkbox + view-full + accept/later
- LegalDocViewer: in-app modal that renders HTML from legalAPI.getDocument
- ConsentGate: wrapper that checks consent before app render
- Integrated at the outermost return in App.tsx (line ~23292)
- Components are top-level functions (not inline in App) to avoid re-mount bug"
```

**🛑 停下来报告**：commit hash + 改动文件清单。等用户回 "继续" 进第 5 阶段。

---

## 第 5 阶段：LegalPanel（关于面板 + 法律信息）

### 5.1 LegalPanel 组件

`src/renderer/components/legal/LegalPanel.tsx`，要求：

- 顶部"关于本软件"区块：显示从 `getVersionInfo()` 拉到的信息（版本、commit、构建时间、运行模式、用户数据目录）
- "打开数据目录" 按钮，点击调用一个新增的 IPC `system:reveal-data-dir`（实现在主进程里调 `shell.showItemInFolder(fixedUserDataPath)`）
- 中部"法律信息"区块：列出用户协议 / 隐私政策 / 开源许可三个入口，点击调出 LegalDocViewer
- "您已接受协议时间"显示从 consent 记录读
- "撤回同意"按钮，红色，点击二次确认后调用 `withdrawConsent`，提示用户重启
- 底部"联系我们"区块：列出 6 个联系方式（取自隐私政策 §12）

### 5.2 集成到系统设置

打开 `src/renderer/App.tsx`，找系统设置的 sub-nav 渲染处（约 line 22080 附近的 `[ { key: 'system_admin', label: ... }, ... ]` 数组）。

在末尾新增：

```typescript
{ key: 'legal', label: '关于与法律', icon: ShieldAlert, helper: '版本、协议、开源许可、联系我们' },
```

然后在系统设置内容渲染区，对应 `activeSettingsTab === 'legal'` 时渲染 `<LegalPanel />`。

⚠️ 同样：**LegalPanel 必须是顶级组件**，不要在 App 函数体内 const 形式定义。

### 5.3 新增 IPC system:reveal-data-dir

主进程 main.ts 加：

```typescript
ipcMain.handle('system:reveal-data-dir', () => {
  shell.showItemInFolder(fixedUserDataPath);
  return { revealed: fixedUserDataPath };
});
```

preload 暴露 `window.systemAPI = { revealDataDir: () => ipcRenderer.invoke('system:reveal-data-dir') }`。

### 5.4 验证

```bash
npm run build 2>&1 | tail -20
```

### 5.5 Commit & 报告

```bash
git add src/renderer/components/legal/LegalPanel.tsx src/renderer/App.tsx src/main/main.ts src/main/preload.ts src/renderer/types/
git diff --cached --stat
git commit -m "feat(legal): LegalPanel in system settings + 'reveal data dir' IPC

- LegalPanel: shows version info, legal documents, consent status, contact info
- New settings tab 'legal' with ShieldAlert icon
- 'Open data folder' button uses shell.showItemInFolder
- 'Withdraw consent' button (red, double confirm) clears consent file
- Component defined at top level to avoid React re-mount bug"
```

**🛑 停下来报告**：commit hash + 文件改动。

---

## 第 6 阶段：账号删除流程（前端）

### 6.1 在 AccountIdentityCard 增加删除入口

打开 `src/renderer/App.tsx`，找到 `const AccountIdentityCard = () =>` 定义（约 line 22222）。

在该组件返回的 JSX 底部，云端模式下增加新的卡片"账号操作"，含红色 "注销账号" 按钮。

按钮点击触发 `openDeleteAccountFlow()`。

### 6.2 删除流程组件

新建 `src/renderer/components/legal/DeleteAccountModal.tsx`：

- 步骤 1：影响说明 modal，列出 4 条影响（数据保留 30 天、退出所有组织、电子凭证依法保留、本机数据不动），用户必须勾选"我已了解"才能继续
- 步骤 2：密码二次验证 input
- 步骤 3：调用 `await api.deleteAccount({ password })`（需在 lib/api.ts 加这个函数，调云端 `DELETE /api/v1/me`）
- 成功：清本机会话凭证 + 撤回 consent + 引导回登录页
- 失败：显示错误

### 6.3 api.ts 加 deleteAccount

`src/renderer/lib/api.ts` 末尾追加：

```typescript
export async function deleteAccount(payload: { password: string }): Promise<{ status: string; deletion_at: string | null }> {
  const url = `${cloudBaseUrl()}/api/v1/me`;
  const res = await fetch(url, {
    method: 'DELETE',
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`注销账号失败: ${res.status} ${detail}`);
  }
  return res.json();
}
```

（如 `cloudBaseUrl` 和 `authHeaders` 命名不一致，按文件实际命名对齐）

### 6.4 验证

```bash
npm run build 2>&1 | tail -20
```

### 6.5 Commit & 报告

```bash
git add src/renderer/components/legal/DeleteAccountModal.tsx src/renderer/App.tsx src/renderer/lib/api.ts
git diff --cached --stat
git commit -m "feat(legal): account deletion frontend (App Store 5.1.1(v) compliant)

- DeleteAccountModal: 2-step flow (impact disclosure + password verify)
- Entry point: AccountIdentityCard 'Account Operations' card (cloud mode only)
- New api.deleteAccount() calls cloud DELETE /api/v1/me
- After successful deletion: clear session, withdraw consent, navigate to login"
```

**🛑 停下来报告**：commit hash。

---

## 第 7 阶段：账号删除流程（后端）

### 7.1 cloud_backend 加 DELETE 端点

在 `cloud_backend/app/main.py` 加 `delete_my_account` 函数（参考 `docs/legal/04-integration-guide.md` §2.5.3 的 Python 代码片段）。

### 7.2 数据库 schema

如果 `employee_accounts` 表还没 `deletion_requested_at` 和 `deletion_scheduled_at` 字段，需 ALTER TABLE 加上。

在 `cloud_backend/app/db.py`（或对应 schema 初始化处）追加 migration：

```python
def migrate_add_deletion_columns(db):
    if not _column_exists(db, 'employee_accounts', 'deletion_requested_at'):
        db.execute("ALTER TABLE employee_accounts ADD COLUMN deletion_requested_at TEXT")
    if not _column_exists(db, 'employee_accounts', 'deletion_scheduled_at'):
        db.execute("ALTER TABLE employee_accounts ADD COLUMN deletion_scheduled_at TEXT")
```

确保启动时调用。

### 7.3 写定时清理脚本

新建 `cloud_backend/scripts/cleanup_pending_deletion.py`：

- 找所有 `account_status = 'pending_deletion' AND deletion_scheduled_at <= now()` 的账号
- 对每个：删除其在所有表中的数据（cascade）
- 记审计日志 `account_deletion_executed`
- 可独立运行：`python cloud_backend/scripts/cleanup_pending_deletion.py`
- 文档说明：建议每天通过 cron / systemd timer 调用一次

### 7.4 加测试

`cloud_backend/tests/test_account_deletion.py`：

- test_delete_my_account_marks_pending_deletion
- test_delete_my_account_requires_correct_password
- test_cleanup_removes_account_after_grace_period
- test_pending_deletion_blocks_login

### 7.5 验证

```bash
cd cloud_backend && python -m pytest tests/test_account_deletion.py -v 2>&1 | tail -30
```

### 7.6 Commit & 报告

```bash
git add cloud_backend/
git diff --cached --stat
git commit -m "feat(legal): account deletion backend (DELETE /api/v1/me + grace period)

- New endpoint: DELETE /api/v1/me, requires password verification
- Schema: employee_accounts.deletion_requested_at + deletion_scheduled_at
- 30-day grace period (account_status='pending_deletion')
- Cleanup script: cloud_backend/scripts/cleanup_pending_deletion.py (run daily)
- Tests: 4 cases covering mark/auth/cleanup/login-blocking"
```

**🛑 停下来报告**：commit hash + 测试结果。

---

## 第 8 阶段：build 流水线集成

### 8.1 修改 npm scripts

`package.json` 的 scripts 加：

```json
"build:legal-html": "node docs/legal/scripts/md-to-html.mjs",
"prebuild": "npm run build:legal-html"
```

### 8.2 修改 electron-builder 配置

在 `package.json` 的 `build.extraResources` 加：

```json
{
  "from": "docs/legal/generated",
  "to": "legal",
  "filter": ["*.html"]
}
```

这样打包后 HTML 会在 `<.app>/Contents/Resources/legal/` 下，正好对应 main.ts 里的查找路径。

### 8.3 验证

```bash
npm run build:legal-html
ls -la docs/legal/generated/    # 应该有 .html

# 重新打 DMG（不用每次完整流程，先 verify-packaged-app）
bash scripts/build-and-ship-dmg.command    # 这次可能要 60-120s
```

打完后装机测试：

1. 卸载旧 app：`rm -rf ~/Applications/益语智库自用平台\ V2.0.app`
2. 备份 consent 文件（如果存在）：`mv ~/Library/Application\ Support/YiyuThinkTankWorkbench2/legal-consent.json{,.backup}`
3. 装新 DMG
4. 启动：首次应该弹 ConsentDialog
5. 点"查看完整内容"应该能看到协议 HTML
6. 勾选 + 同意 → 进入主界面
7. 进系统设置 → 关于与法律 → 应该看到版本信息 + 数据目录入口
8. 点"撤回同意" → 重启 → 应再次弹 ConsentDialog

### 8.4 Commit & 报告

```bash
git add package.json
git diff --cached --stat
git commit -m "build(legal): integrate legal HTML generation into build pipeline

- New npm script: build:legal-html
- prebuild hook auto-generates HTML before main build
- electron-builder extraResources copies HTML to <.app>/Contents/Resources/legal/
- Main process loads from process.resourcesPath/legal/ at runtime"
```

**🛑 停下来报告**：commit hash + 装机测试结果（哪些步骤过、哪些没过）。

---

## 第 9 阶段：feature 分支总结 + 等用户决策

### 9.1 整理

```bash
git log feature/legal-components ^main --oneline
# 应该看到约 7 个 commit（chore + 6 个 feat）
```

### 9.2 报告

```
feature/legal-components 完成：
- 7 个 commit（清单：...）
- 改动行数：+XXXX / -YYYY
- 涉及文件：src/main/main.ts (+...), src/renderer/App.tsx (+...), src/renderer/components/legal/* (新增 5 个文件), cloud_backend/* (+...), docs/legal/* (+...)
- 装机测试：首启弹窗 [PASS/FAIL]、关于面板 [PASS/FAIL]、账号删除前端 [PASS/FAIL]、账号删除后端测试 [PASS/FAIL]
- 已知风险：（如有）

下一步等用户决定：
A. 直接合并 feature/legal-components 到 main
B. 先做某些细节调整再合
C. 留分支等更多组件（如 Sentry 错误上报）一起合
```

---

## 红线（严格守住，整个 7 个阶段都不能违反）

- 🚫 **不删** `~/Library/Application Support/YiyuThinkTankWorkbench2/` 任何东西，需要清 venv 时只清 `runtime/backend-venv`
- 🚫 **不动副本目录 `~/Desktop/yiyu-cleanup-test-*`**（本任务全部在原仓库做）
- 🚫 **不动 mobile/ 子仓库**
- 🚫 **不改 AuthShell 的内联组件结构**（那是另一个独立 bug，留单独 commit 修）
- 🚫 **不在 dirty 工作区开始本任务**（必须先 cleanup 合回 main）
- 🚫 **不要 force push、rebase**
- 🚫 **不要把法律文档里的 `【需填写: XXX】` 占位符当真值用**——这些占位符必须保留，等用户法务补
- ✅ 每个 commit 前 `git diff --cached --stat` 给用户看
- ✅ 每个 🛑 停顿点都向用户报告
- ✅ 任何意外（编译错误、测试失败、git 冲突）立即停下报告，不盲目继续

---

## 异常恢复

任何阶段出错：

```bash
git status              # 看脏区
git checkout -- <file>  # 撤回单文件
git reset --hard HEAD   # 撤回当前所有未 commit 改动（小心！）
git reset --hard HEAD~1 # 撤回最近一个 commit（小心！）
# 最严重时回到分支起点：
git reset --hard $(git merge-base main feature/legal-components)
```

如果整个分支需要废弃：

```bash
git checkout main
git branch -D feature/legal-components
# 然后从头来过
```

原仓库 main 分支从始至终不应被这个任务污染——这是隔离的意义。
