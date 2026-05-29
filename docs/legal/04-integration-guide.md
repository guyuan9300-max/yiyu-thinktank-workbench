# 法律文档工程实施指南

> 这份文档告诉**工程师**如何把法律文档落到代码里：怎么弹同意窗、怎么在关于面板显示、怎么管理协议版本号。给 Claude Code 或主开发同学读。

---

## 1. 集成总览

```
法律文档（.md）  ──┬──→  转 HTML 嵌入应用 (首启弹窗 + 关于面板)
                 │
                 ├──→  转 HTML 部署到官网（App Store 必填的 Privacy Policy URL）
                 │
                 └──→  导出 PDF（备案、客户存档）
```

---

## 2. 工程实施清单（按依赖顺序）

### 2.1 资源准备

```bash
# 仓库根目录下建议结构
docs/legal/
├── 00-README.md                    # 总入口
├── 01-user-agreement.md            # 用户协议（源文件）
├── 02-privacy-policy.md            # 隐私政策（源文件）
├── 03-app-store-compliance.md      # App Store 合规清单
├── 04-integration-guide.md         # 本文档
├── 05-license-attributions-template.md  # 开源依赖归属模板
├── scripts/
│   ├── collect-licenses.mjs        # 自动收集 license
│   └── md-to-html.mjs              # 协议转 HTML
└── generated/                      # 自动生成的产物（gitignore 中）
    ├── user-agreement.html
    ├── privacy-policy.html
    └── NOTICE.txt
```

### 2.2 首启同意弹窗

#### 2.2.1 触发逻辑

```typescript
// src/renderer/App.tsx 或新建 src/renderer/components/legal/ConsentDialog.tsx

const LEGAL_VERSION = '1.0';  // 与协议头里的版本号一致
const CONSENT_KEY = 'legal-consent-v' + LEGAL_VERSION;

// 检查是否已同意
const hasConsented = async () => {
  const stored = await electronAPI.getStorage(CONSENT_KEY);
  return stored?.acceptedAt && stored?.version === LEGAL_VERSION;
};

// 在 App 启动时，所有用户操作之前
useEffect(() => {
  hasConsented().then(consented => {
    if (!consented) {
      setShowConsentDialog(true);
    }
  });
}, []);
```

#### 2.2.2 弹窗设计要点

- 复选框默认未勾选
- "稍后"按钮：关闭弹窗但禁用敏感功能（AI、云端、数据上报）
- "同意并继续"：未勾选时禁用
- 协议链接点击后必须能查看完整内容（推荐内置 modal 显示 HTML 渲染版本）

#### 2.2.3 存储格式

```typescript
// 同意记录写入用户数据目录
// 路径: ~/Library/Application Support/YiyuThinkTankWorkbench2/legal-consent.json
{
  "version": "1.0",
  "acceptedAt": "2026-05-11T14:32:00.000Z",
  "acceptedDocuments": [
    { "name": "user-agreement", "version": "1.0", "hash": "sha256:..." },
    { "name": "privacy-policy", "version": "1.0", "hash": "sha256:..." }
  ],
  "userAgent": "yiyu-workbench/2.0 macOS 14.5 arm64",
  "ipAddress": null  // 本机模式不记录
}
```

#### 2.2.4 协议变更时重新征求

```typescript
// 检测协议升级
const currentVersion = await fetchCurrentLegalVersion();  // 从远端或本地配置读
const storedConsent = await getStorage(CONSENT_KEY);
if (storedConsent.version !== currentVersion) {
  // 弹出"协议变更"专用弹窗，强调变更点
  showLegalUpdateDialog(storedConsent.version, currentVersion);
}
```

### 2.3 关于面板（About Panel）

在系统设置中新增一节"关于本软件 / 法律信息"，包含：

```
┌─────────────────────────────────────────┐
│ 关于本软件                                │
├─────────────────────────────────────────┤
│                                         │
│ 益语智库自用平台 V2.0                     │
│ 版本：2.0.0 (commit: abc1234)            │
│ 构建时间：2026-05-11 14:30:00            │
│ 运行模式：本机模式（packaged）            │
│                                         │
├─────────────────────────────────────────┤
│ 法律信息                                 │
├─────────────────────────────────────────┤
│ 📄 用户协议           [查看]              │
│ 📄 隐私政策           [查看]              │
│ 📄 开源许可（NOTICE） [查看]              │
│                                         │
│ 协议版本：v1.0                            │
│ 您接受协议的时间：2026-05-11 14:32       │
│ [撤回同意 / 重新阅读]                     │
│                                         │
├─────────────────────────────────────────┤
│ 联系我们                                 │
├─────────────────────────────────────────┤
│ 客服：support@yiyu.example.com           │
│ 隐私问题：privacy@yiyu.example.com       │
│ 反馈：[发送反馈]                          │
│                                         │
└─────────────────────────────────────────┘
```

实现建议：在 `src/renderer/App.tsx` 已有的系统设置中新增 tab `legal`，内容由独立的 `<LegalPanel />` 组件渲染。

### 2.4 协议显示

#### 2.4.1 In-App 显示

把 `.md` 转 HTML 嵌入：

```bash
# 一次性转换（构建时）
node docs/legal/scripts/md-to-html.mjs
# 产物：
#   docs/legal/generated/user-agreement.html
#   docs/legal/generated/privacy-policy.html
```

在应用中通过 IPC 加载：

```typescript
// preload
window.legalAPI = {
  getDocument: (name: 'user-agreement' | 'privacy-policy') =>
    ipcRenderer.invoke('legal:get-document', name),
};

// main
ipcMain.handle('legal:get-document', (event, name) => {
  const filePath = path.join(app.getAppPath(), 'resources', 'legal', `${name}.html`);
  return fs.readFileSync(filePath, 'utf-8');
});
```

#### 2.4.2 官网部署（App Store 必填）

把同一份 HTML 部署到官网：

```
https://yiyu.example.com/legal/user-agreement
https://yiyu.example.com/legal/privacy-policy
```

要求：

- 公网可访问、HTTPS
- 不需要登录
- 支持中文 + 英文双语（如有海外用户）
- 提供历史版本归档：`/legal/privacy-policy/v1.0`、`/v0.9` 等

### 2.5 账号删除流程（App Store §5.1.1(v)）

#### 2.5.1 入口位置（不超过 3 次点击）

```
系统设置（侧栏） → 身份与组织（左侧 tab） → 账号操作（卡片） → 注销账号（红色按钮）
```

#### 2.5.2 确认流程

```typescript
async function deleteAccount() {
  // Step 1: 显示影响说明
  const confirmed1 = await showConfirmDialog({
    title: '注销账号',
    message: `注销账号将：
• 您的云端业务数据将在 30 天内永久删除（保留期内可联系恢复）
• 您将退出所有组织
• 已签发的电子凭证依法保留
• 本机数据不会被删除（如需可单独清除）`,
    confirmText: '我已了解，继续',
    cancelText: '取消',
  });
  if (!confirmed1) return;

  // Step 2: 二次验证（输入密码或验证码）
  const password = await promptForPassword();
  if (!password) return;

  // Step 3: 调用 API
  const result = await api.deleteAccount({ password });
  if (result.ok) {
    showSuccessToast('账号注销请求已提交');
    await clearLocalSession();
    await navigateTo('/login');
  } else {
    showErrorToast(result.error);
  }
}
```

#### 2.5.3 后端实现

云端 API: `DELETE /api/v1/me`

```python
# cloud_backend/app/main.py 中加入
@app.delete("/api/v1/me")
def delete_my_account(
    current_user: EmployeeAccount = Depends(_require_auth),
    password: str = Body(..., embed=True),
):
    # 验证密码
    if not verify_password(password, current_user.password_hash):
        raise HTTPException(401, "密码不正确")
    
    # 标记账号进入删除队列（30 天后真删）
    state.db.execute("""
        UPDATE employee_accounts
        SET account_status = 'pending_deletion',
            deletion_requested_at = ?,
            deletion_scheduled_at = datetime(?, '+30 days'),
            disabled_at = ?
        WHERE id = ?
    """, (now_iso(), now_iso(), now_iso(), current_user.id))
    
    # 撤销所有 session
    state.db.execute("DELETE FROM sessions WHERE user_id = ?", (current_user.id,))
    
    # 记审计日志
    _log_audit(state, "account_deletion_requested", actor_user_id=current_user.id, ...)
    
    return {"status": "scheduled", "deletion_at": "..."}
```

#### 2.5.4 定时任务

每天跑一次清理任务，把 `deletion_scheduled_at < now()` 的账号彻底删除：

```python
# backend/scripts/cleanup_deleted_accounts.py
def cleanup_pending_deletion_accounts(db):
    rows = db.fetchall("""
        SELECT id FROM employee_accounts
        WHERE account_status = 'pending_deletion'
          AND deletion_scheduled_at <= datetime('now')
    """)
    for row in rows:
        delete_user_data_cascade(db, user_id=row['id'])
```

---

## 3. License 收集（NOTICE 文件）

### 3.1 collect-licenses.mjs 脚本

参见同目录 `scripts/collect-licenses.mjs`。

运行：

```bash
# 一次性收集
node docs/legal/scripts/collect-licenses.mjs

# 产出：
# docs/legal/generated/NOTICE.txt           # 完整的依赖归属清单
# docs/legal/generated/license-summary.csv  # 摘要表格
# docs/legal/generated/license-warnings.txt # GPL/AGPL 等高风险 license 警告
```

### 3.2 高风险 license 处理

如脚本告警有 GPL / AGPL 依赖：

| License | 风险 | 建议 |
| --- | --- | --- |
| MIT / Apache-2.0 / BSD | 低 | 列入 NOTICE 即可 |
| LGPL-2.1 / LGPL-3.0 | 中 | 列入 NOTICE，确保可替换 |
| MPL-2.0 | 中 | 列入 NOTICE，对修改的 MPL 文件保留开源 |
| **GPL-2.0 / GPL-3.0** | **高** | **可能要求整个 App 开源** —— 必须评估并考虑替换 |
| **AGPL-3.0** | **极高** | **网络使用即触发开源** —— 几乎必须替换 |
| 未知 / no-license | 极高 | 法律风险 —— 必须替换或联系作者获取授权 |

### 3.3 集成到关于面板

```typescript
// 关于面板 → 开源许可入口
<button onClick={() => openModal('NOTICE.txt 的渲染版本')}>
  查看开源许可
</button>
```

---

## 4. 协议变更与版本管理

### 4.1 语义化版本

```
v1.0           初版
v1.1           小幅修改（措辞优化、补充说明）→ 通知用户但不重新征求同意
v2.0           重大变更（处理目的扩大、第三方新增、用户权利收窄）→ 必须重新征求同意
```

### 4.2 通知方式

| 变更类型 | 通知时间 | 通知方式 |
| --- | --- | --- |
| 措辞优化（v1.x） | 生效前 7 日 | 软件内弹窗（一次性提示） + 邮件（非必需） |
| 处理范围扩大（v2.0+） | 生效前 15 日 | 软件内弹窗（必须勾选同意） + 邮件 + 推送 |
| 紧急安全修复 | 立即生效 | 邮件 + 后续 7 日内软件内补充告知 |

### 4.3 历史版本归档

每次升级，旧版本保留到 `docs/legal/archive/`：

```
docs/legal/archive/
├── user-agreement-v0.9-2025-12-01.md
├── privacy-policy-v0.9-2025-12-01.md
├── user-agreement-v1.0-2026-05-11.md
└── privacy-policy-v1.0-2026-05-11.md
```

官网相应路径 `/legal/privacy-policy/history` 列出所有历史版本。

---

## 5. 用户撤回同意流程

PIPL §15 要求允许用户撤回同意。实现：

```
设置 → 关于本软件 → 法律信息 → "撤回同意"

确认 → 执行：
  1. 删除 legal-consent.json
  2. 关闭所有需同意才能使用的功能（AI、云端、统计上报）
  3. 提示用户："您已撤回同意。已禁用敏感功能。下次启动会再次询问。"
  4. （可选）询问是否同时注销账号或清除本机数据
```

---

## 6. 日志与审计

所有法律相关操作必须记录：

```typescript
// 后端 audit_log 表
{
  id: 'uuid',
  user_id: 'xxx',         // 本机模式可为 null
  action: 'consent_accepted' | 'consent_withdrawn' | 'account_deletion_requested' | 'data_exported' | ...
  detail: { version: '1.0', documents: [...] },
  ip_address: '127.0.0.1', // 本机操作记 127.0.0.1
  user_agent: 'yiyu-workbench/2.0 ...',
  timestamp: '2026-05-11T14:32:00Z',
}
```

留存期限：审计日志保留 3 年（PIPL 与网安法要求最少 6 个月，建议至少 3 年）。

---

## 7. 检查清单（发版前）

每次发版前对照下面打勾：

### 7.1 协议层

- [ ] 用户协议、隐私政策内容与当前 App 功能一致
- [ ] 协议版本号已更新（如有变化）
- [ ] 所有 `【需填写: XXX】` 已填空
- [ ] 已请律师审过
- [ ] 公司主体信息正确

### 7.2 工程层

- [ ] 首启弹窗已上线
- [ ] 协议显示页面 UI 已实现
- [ ] 关于面板已包含法律信息区
- [ ] 账号删除流程已实现并测试
- [ ] 撤回同意流程已实现
- [ ] license 脚本已跑过，NOTICE.txt 已更新
- [ ] 高风险 license 已评估处理

### 7.3 部署层

- [ ] Privacy Policy URL 已在官网部署
- [ ] User Agreement URL 已在官网部署
- [ ] 历史版本归档可访问
- [ ] 客服邮箱（support / privacy / legal）已设置并测试可收

### 7.4 App Store 层（若提审）

- [ ] App Privacy 问卷已填
- [ ] Age Rating 已选择（建议 12+）
- [ ] Encryption Export Compliance 已声明
- [ ] 提审说明（Review Notes）已写
- [ ] 提审演示账号已准备
- [ ] 所有截图、图标已上传

---

## 8. 给 Claude Code 的具体编码任务

如果要让 Claude Code 实施这套集成，建议任务拆分为：

1. **法律组件（1d）**：新建 `src/renderer/components/legal/`，含 `ConsentDialog.tsx`、`LegalDocViewer.tsx`、`LegalPanel.tsx`
2. **首启拦截（0.5d）**：在 `App.tsx` 的 `renderBranch` 之前加一层 `<ConsentGate>`
3. **关于面板（0.5d）**：在系统设置中加一个 `legal` tab，集成 LegalPanel
4. **账号删除前端（0.5d）**：身份与组织卡片加 "注销账号" 入口 + 流程
5. **账号删除后端（0.5d）**：cloud_backend 加 `DELETE /api/v1/me` + 清理任务
6. **协议转 HTML 脚本（0.5d）**：`docs/legal/scripts/md-to-html.mjs`
7. **license 收集脚本（0.5d）**：`docs/legal/scripts/collect-licenses.mjs`
8. **build 集成（0.5d）**：electron-builder 打包时把 generated/HTML 复制到 Resources

**总工作量：约 1 周**。每完成一项让 Claude Code 给出 git diff 给你过一遍再 commit。

---

## 9. 风险点与建议

| 风险 | 影响 | 建议 |
| --- | --- | --- |
| 律师审核未做 | 法律层面无效，纠纷时不利 | **必须做**，预算 5000-15000 元 |
| AI 第三方协议未告知用户 | 违反 PIPL §22-23（委托处理） | 已在隐私政策中详细告知，落地前再确认 |
| 跨境传输无评估 | 违反 PIPL §38 | 默认接入境内 AI；境外引擎需在 UI 中再次告警 |
| 儿童保护未实现 | 违反《未成年人保护法》《个人信息保护法》§31 | 注册时收集出生年（如未来加） |
| 账号删除流程不彻底 | 违反 App Store §5.1.1(v) | 严格按 §2.5 实现，定时任务真删 |
| 协议变更不通知 | 违反 PIPL §17 | 实现协议版本检测 + 弹窗 |

---

## 10. 进度跟踪建议

建议在 `docs/legal/PROGRESS.md` 中跟踪：

```markdown
# 法律文档与合规落地进度

## v1.0 阶段（目标：2026-06-30）

- [x] 写用户协议（v1.0）
- [x] 写隐私政策（v1.0）
- [x] 写 App Store 合规清单
- [x] 写实施指南
- [ ] 律师审核 ← 进行中
- [ ] 公司主体信息填空
- [ ] 官网 URL 部署
- [ ] App 内首启弹窗实现
- [ ] App 内关于面板实现
- [ ] 账号删除流程实现
- [ ] license 脚本跑一遍
- [ ] 内部冒烟测试
- [ ] 用户测试
```
