# App Store 提审合规清单

> 本文档是为将"益语智库自用平台 V2.0"上架 Apple Mac App Store / iOS App Store 准备的合规清单。提审前请逐项对照，避免被 App Review 打回。

---

## 0. 前置准备

### 0.1 必须先完成的事

| # | 事项 | 说明 |
| --- | --- | --- |
| 1 | 注册 Apple Developer Program 账号 | 个人 / 公司账号都可，公司账号需 DUNS 编号；年费 USD 99 |
| 2 | 完成税务与银行信息（Agreements, Tax, and Banking） | 后台 → Agreements 里填好，否则无法发布 |
| 3 | 获取 Developer ID 签名证书 | 用于 macOS Notarization；与 App Store 提交证书不同 |
| 4 | 获取 App Store 提交证书（Mac App Store / iOS App Store Distribution） | 在 Developer 后台 Certificates → 创建 |
| 5 | 在 App Store Connect 创建 App | Bundle ID 必须与代码中一致：`com.yiyu.selfworkbench2` |
| 6 | 准备 App 图标（多尺寸） | 详见 §3 |
| 7 | 准备 App Store 截图 | 详见 §4 |
| 8 | 完成 App Privacy 隐私问卷 | 详见 §5（最重要） |

### 0.2 关键约束

- **Mac App Store 强制 Sandbox**：所有上架 MAS 的 app 必须运行在 macOS Sandbox 中。当前架构需评估是否兼容（详见 §7）。
- **不允许执行任意代码下载**：python-build-standalone 在用户首次启动时安装 venv 涉及"动态运行外部代码"，可能触发审核——需要在提审时充分说明，或改用静态打包。

---

## 1. App Review Guidelines 重点条款对照

### 1.1 §2.5 Software Requirements

| 条款 | 内容 | 我们的处理 |
| --- | --- | --- |
| 2.5.2 | 不得下载或安装可执行代码、解释器、其他二进制 | **风险点**：Python venv 创建过程涉及从内置 wheelhouse 安装包到用户目录。需在提审说明中阐明：①所有内容均预打包在 .app 中；②不从互联网下载；③解压/复制操作而非"执行下载"。 |
| 2.5.4 | 多任务 App 仅在确实需要时才使用相应资源 | 本软件后端长驻进程使用网络服务 + 持续 IPC。需声明。 |
| 2.5.6 | 浏览器引擎必须用 WebKit | Electron 用 Chromium。**Mac App Store 允许 Electron**（在 macOS 沙箱框架下）。iOS 不允许。 |
| 2.5.9 | 不得修改、复制、与系统组件互操作（含 UI/行为） | 我们改了 macOS 通知图标、Dock 行为——需评估。 |

### 1.2 §3 Business

| 条款 | 内容 | 我们的处理 |
| --- | --- | --- |
| 3.1.1 | App 内购需走 IAP；不得提示用户去网外支付 | 当前免费，未来收费需评估 IAP 集成 |
| 3.1.5(a) | 商品/订阅必须有清晰描述 | 适用 |
| 3.2.1 | 不得包含未声明的功能、隐藏功能 | 提审 build 与公开 build 必须一致 |

### 1.3 §4 Design

| 条款 | 内容 | 我们的处理 |
| --- | --- | --- |
| 4.1 | 不得抄袭其他 App | 我们是原创 |
| 4.2 | 必须有原创内容与独立功能 | 适用 |
| 4.2.3 | 模板化 App / SDK 套壳通常拒绝 | N/A |
| 4.3 | 不得是垃圾 App、重复提交 | N/A |
| 4.5.1 | 不得在 metadata 中包含违规内容（关键词堆砌、误导描述） | 提审描述需精炼 |
| 4.8 | 用户登录必须支持 Sign in with Apple（如果支持第三方登录） | **当前不支持第三方登录，不触发此规则**。如未来加入微信登录/Google 登录等，需同时加入 Sign in with Apple。 |

### 1.4 §5 Legal（最严重，最易拒）

| 条款 | 内容 | 我们的处理 |
| --- | --- | --- |
| 5.1.1 | 隐私 - 数据收集与存储 | 必须有 Privacy Policy URL（已在《隐私政策》中提供） |
| 5.1.1(i) | 必须告知用户收集了什么、如何使用 | 已覆盖 |
| 5.1.1(ii) | 收集前必须征得同意 | **首启弹窗必须实现**（详见 §2） |
| 5.1.1(iv) | 不得收集用于初始化使用之外的数据 | 已遵守最小必要原则 |
| 5.1.1(v) | App 必须提供账号删除入口 | **必须在 UI 中提供**（详见 §6） |
| 5.1.2 | 数据使用与共享 - 不得未经授权与第三方共享 | 已在隐私政策中声明 |
| 5.1.5 | 位置服务 | N/A（不收集位置） |
| 5.2 | 知识产权 | 必须有合法权利 |
| 5.4 | VPN | N/A |
| 5.6 | 开发者代码合作 | 不允许联合开发模糊 |

### 1.5 §5.1.1(v) Account Deletion（2022 起强制）

**所有支持账号创建的 App 必须提供账号删除入口**，且必须满足：

- ✅ 入口位于 App **内部**（不能仅指向网页）
- ✅ 删除流程"易于发现"，不超过 3 次点击触达
- ✅ 删除是完整的（不只是"停用"）
- ✅ 删除后即时生效，或在合理时间内完成
- ✅ 如有法律保留期限（财务/反洗钱），必须明示告知

**我们的实现**：

```
系统设置 → 身份与组织 → 账号操作 → 注销账号
  ↓
确认弹窗（说明影响、保留期、不可恢复）
  ↓
二次确认（输入"删除"或密码）
  ↓
执行：
  - 云端业务数据进入 30 天删除队列
  - 退出所有组织
  - 清除本机会话凭证
  - （可选）清除本机数据
```

---

## 2. 首启同意弹窗

### 2.1 必须包含的元素

按 PIPL §17 与 App Store §5.1.1(ii)：

```
┌────────────────────────────────────────────────────┐
│  欢迎使用益语智库自用平台 V2.0                       │
├────────────────────────────────────────────────────┤
│                                                    │
│  在开始使用前，请阅读：                              │
│                                                    │
│  📄《用户协议》  [点击阅读全文]                       │
│  📄《隐私政策》  [点击阅读全文]                       │
│                                                    │
│  关键信息：                                          │
│  • 您的数据默认仅存储在本机（本机优先架构）            │
│  • 智能化功能会将您选择的文本片段发送至 AI 引擎        │
│  • 您可随时撤回同意或注销账号                         │
│                                                    │
│  [ ] 我已阅读并同意《用户协议》和《隐私政策》          │
│                                                    │
│              [稍后]   [同意并继续]                    │
│                                                    │
└────────────────────────────────────────────────────┘
```

### 2.2 实现要点

- **复选框默认未勾选**（PIPL 要求 + Apple 要求）
- 协议链接点击后必须能完整阅读（嵌入式 WebView 或外部浏览器）
- "同意并继续"按钮在复选框未勾选时**禁用**（灰色）
- 用户拒绝后不应禁止 App 启动，但应将敏感功能（AI、云端）置灰，提示"需要先同意协议才能使用"
- 协议版本更新后须重新弹窗征求同意

---

## 3. App 图标准备

### 3.1 macOS Mac App Store 需要的尺寸

| 尺寸 | 用途 |
| --- | --- |
| 1024x1024 | App Store 商店展示 |
| 512x512 + @2x | Dock |
| 256x256 + @2x | Finder |
| 128x128 + @2x | Finder |
| 32x32 + @2x | 小尺寸 |
| 16x16 + @2x | 极小尺寸 |

### 3.2 设计要求

- 不得包含 Apple 商标
- 不得使用屏幕截图作为图标
- 不得包含价格、版本号
- 建议带圆角（系统自动遮罩）
- 背景不透明
- 设计原稿建议是 1024x1024 PNG，由 `electron-builder` 自动生成 `.icns`

---

## 4. App Store 截图

### 4.1 Mac App Store 截图要求

| 项 | 要求 |
| --- | --- |
| 分辨率 | 至少 1280x800，建议 2880x1800（适配 Retina） |
| 数量 | 至少 1 张，最多 10 张 |
| 格式 | PNG 或 JPEG（不带 alpha） |
| 内容 | 必须是当前提审 build 的真实截图，不允许 mockup |
| 文字 | 不得包含价格、违规内容 |

### 4.2 建议截图清单

1. **登录/欢迎页** - 突出"本机优先"特性
2. **任务与日程主界面** - 月历 + 任务卡片
3. **战略陪伴 - 组织级智能资产** - 突出 AI 价值
4. **数据中心** - 突出本地大模型优化
5. **系统设置** - 突出 AI 引擎可自定义、数据本机存储

每张配 30-50 字的文字说明（在 App Store Connect 中填写）。

---

## 5. App Privacy 隐私问卷（最重要）

### 5.1 必须如实填写

App Store Connect → App Privacy 中需逐项申报。下表是我们的回答草稿，**提交前必须由产品 + 法务再核对一次**：

#### 5.1.1 Data Used to Track You（用于跟踪您的数据）

**当前回答：无**。我们不进行跨 App 或网站的跟踪。

#### 5.1.2 Data Linked to You（与您关联的数据）

| 数据类型 | 是否收集 | 用途 |
| --- | --- | --- |
| Contact Info → Email Address | ✅（仅云端模式） | App Functionality, Account Authentication |
| Contact Info → Name | ✅（仅云端模式） | App Functionality |
| Contact Info → Phone Number | ✅ 选填（仅云端模式） | App Functionality, Account Authentication |
| User Content → Other User Content | ✅（您主动产生的业务内容） | App Functionality |
| User Content → Emails or Text Messages | ❌ | - |
| User Content → Photos or Videos | ❌ | - |
| Identifiers → User ID | ✅（仅云端模式） | App Functionality |
| Identifiers → Device ID | ❌ | - |
| Usage Data → Product Interaction | ✅（仅用户开启使用统计时） | Analytics |
| Diagnostics → Crash Data | ✅（仅用户主动上报时） | App Functionality |
| Diagnostics → Performance Data | ✅（仅用户主动上报时） | App Functionality |

#### 5.1.3 Data Not Linked to You（不与您关联的数据）

无（我们收集的所有数据要么不收集，要么与账号关联）。

#### 5.1.4 Privacy Practices

- ✅ Provide a privacy policy URL: 【需填写: https://yiyu.example.com/legal/privacy-policy】
- ✅ Data collection is optional / users can opt out
- ✅ Users can request data deletion via in-app account deletion

### 5.2 注意陷阱

- ⚠️ 如果你**实际收集了某项数据但没在 App Privacy 中申报**，被发现后会被立即下架并罚款
- ⚠️ 如果你**接入的第三方 SDK 收集数据，也算在你头上**——必须如实申报所有 SDK 的数据收集
- ⚠️ 申报每年至少复审一次，与实际功能保持同步

---

## 6. 第三方 SDK 申报

### 6.1 当前使用的可能涉及数据收集的依赖

| 依赖名 | 类别 | 数据收集情况 | 申报要求 |
| --- | --- | --- | --- |
| Electron | 框架 | 自身不收集；但 Chromium 可能有崩溃上报 | 评估是否禁用 Chromium 内置 reporting |
| Python Build Standalone | 运行时 | 不收集 | 无 |
| openai-python (如启用) | AI 客户端 | 转发用户输入至 OpenAI | 在 App Privacy 中作为 third-party service 声明 |
| volcengine-sdk (默认 AI) | AI 客户端 | 转发用户输入至火山方舟 | 在 App Privacy 中作为 third-party service 声明 |
| sqlite | 本地存储 | 不收集 | 无 |
| 【需填写: 崩溃报告 SDK，如 Sentry】 | 监控 | 收集崩溃堆栈 | 必须申报 + 用户同意 |

### 6.2 检查方法

提审前跑：

```bash
# 自动扫描依赖中涉及网络请求的库
node docs/legal/scripts/collect-licenses.mjs --detect-network-libs

# 手动审计 npm 依赖
npm ls --all --json | jq '.dependencies | keys[]'

# 检查 Python 依赖
cat backend/requirements.txt
```

每个发起网络请求的依赖都需要在 App Privacy 中评估是否申报。

---

## 7. Sandbox 兼容性（Mac App Store 必需）

### 7.1 Sandbox 限制

Mac App Store 强制运行在 [App Sandbox](https://developer.apple.com/documentation/security/app_sandbox) 中。Sandbox 限制：

- 限制文件系统访问（仅限 App 容器、用户授权目录）
- 限制网络访问（需要 entitlement 声明）
- 限制 IPC、子进程
- 限制硬件访问

### 7.2 我们当前架构的风险点

| 功能 | Sandbox 兼容性 | 应对 |
| --- | --- | --- |
| Electron 主进程 + Python 子进程 | ⚠️ 需要 `com.apple.security.inherit` entitlement 让子进程继承沙箱 | 工程改造 |
| Python venv 创建（写入 `~/Library/Application Support/...`） | ✅ 在 App 容器内允许 | 路径需调整为 sandbox 内 |
| 网络请求 AI 引擎 | ✅ 加 `com.apple.security.network.client` entitlement | 在 entitlements.plist 配置 |
| 监听 127.0.0.1:47829 本地端口 | ⚠️ sandbox 下可能受限 | 改用 stdin/stdout IPC 或 Unix socket |
| Finder 在数据目录显示 | ⚠️ `NSDocumentsFolderUsageDescription` 等 usage strings | 配置 Info.plist |

### 7.3 改造工作量评估

**保守估计：1-2 周专项工程**

主要工作：
1. 评估并替换不兼容的子进程通信方式（端口 → Unix socket）
2. 调整数据存储路径为 sandbox 兼容路径
3. 配置 entitlements.plist 与 Info.plist usage strings
4. 在 sandbox 模式下全面回归测试
5. 修复 sandbox 下的权限弹窗与用户体验

### 7.4 替代方案

如果短期内 Mac App Store 上架时间紧迫，可考虑：

- **方案 A：先发 Developer ID 签名版（不上架 MAS）**，通过自有渠道分发；同时启动 sandbox 改造工程
- **方案 B：开发 MAS 专版**，砍掉部分需 sandbox 之外权限的功能（如直接访问任意路径文件）
- **方案 C：放弃 Mac App Store，专注 Developer ID 分发**（如目标用户是企业 IT 部门，IT 已熟悉手动安装）

---

## 8. Encryption Export Compliance

### 8.1 是什么

美国出口管制法规要求所有使用加密技术的 App 需进行出口合规申报。

### 8.2 我们的情况

- 使用 HTTPS / TLS：算"标准加密"，可免除文档申报
- 使用 bcrypt 哈希密码：算"非出口管制"
- 使用 SQLite 本地存储：未加密（明文）

### 8.3 申报选项

在 Info.plist 中添加：

```xml
<key>ITSAppUsesNonExemptEncryption</key>
<false/>
```

如果未来增加自定义加密（如端到端加密文档），需改为 `<true/>` 并提交 ATL 申报。

---

## 9. Children's Privacy / 儿童分类

### 9.1 年龄分级

App Store Connect 的 App Information → Age Rating 需评估：

- 暴力 / 色情 / 赌博 / 烟酒：无 → **4+**
- 含 AI 生成内容（可能输出意外内容）：建议至少 **9+** 或 **12+**，并在描述中说明 AI 内容
- 含组织协作 / 实名信息：**17+** 不必要，**12+** 即可

### 9.2 不申报为儿童类别

由于我们的产品面向成年企业用户，**不要勾选 "Made for Kids" 类别**——否则会触发更严格的儿童隐私规则（COPPA / CIPL §31）。

---

## 10. App Tracking Transparency (ATT, iOS 14.5+)

### 10.1 是否需要

ATT 仅适用于使用 IDFA 进行跨 App 跟踪的场景。

**我们不使用 IDFA，不进行跨 App 跟踪 → 不需要 ATT 弹窗**。

### 10.2 如何确认

确保：

- 代码中没有 `requestTrackingAuthorization` 调用
- App Privacy 问卷中 "Data Used to Track You" 选择"无"

---

## 11. 提审材料清单（最终核对）

提交前确认以下所有材料齐全：

- [ ] App Binary（包含正确 entitlements）
- [ ] 应用图标（1024x1024）
- [ ] App Store 截图（至少 1 张，建议 4-6 张）
- [ ] App 名称、副标题、关键词、描述
- [ ] What's New（如果是更新版本）
- [ ] Support URL（必填，公网可访问）
- [ ] Marketing URL（可选）
- [ ] Privacy Policy URL（必填，公网可访问）
- [ ] App Review Information（联系人姓名、电话、邮箱；演示账号；提审说明）
- [ ] Age Rating 问卷
- [ ] App Privacy 问卷（已在 §5 准备）
- [ ] Encryption Export Compliance 信息
- [ ] Build 已通过 Notarization
- [ ] Bundle ID、Version、Build Number 与提交一致

---

## 12. 提审说明（Review Notes）模板

```
Dear App Review Team,

This is "Yiyu Intelligence Workbench V2.0" - a productivity workbench designed
for individuals and small organizations to manage tasks, documents, and AI-assisted
analysis.

KEY POINTS FOR REVIEW:

1. LOCAL-FIRST ARCHITECTURE: This app stores user data locally by default at
   `~/Library/Application Support/YiyuThinkTankWorkbench2/`. Users can optionally
   enable cloud sync.

2. AI INTEGRATION: When users invoke AI features, text snippets are sent to a
   user-configured AI service (default: Volcano Engine ARK, hosted in China).
   Users are informed of this in our Privacy Policy.

3. PYTHON RUNTIME: The app bundles a Python interpreter (python-build-standalone)
   used for local AI processing. The interpreter and all wheels are pre-packaged
   in the .app bundle - no code is downloaded from the internet at runtime.

4. DEMO ACCOUNT for review:
   - Email: review@yiyu.example.com  ← 【需填写】
   - Password: 【需填写: 提审专用密码】

5. PRIVACY: Our privacy policy is at https://yiyu.example.com/legal/privacy-policy
   We have implemented the in-app account deletion flow at:
   Settings → Identity → Delete Account

6. NO TRACKING: This app does not perform any cross-app or cross-website tracking.

Please contact 【需填写: dev@yiyu.example.com】 if you have any questions.

Best regards,
【需填写: 团队 / 联系人】
```

---

## 13. 常见拒绝原因预案

| 拒绝原因 | 预防措施 |
| --- | --- |
| 5.1.1(v) 缺少账号删除 | 已在 §6 设计完整流程 |
| 5.1.1(ii) 未在收集前征得同意 | 已在 §2 设计首启弹窗 |
| 2.5.2 看似下载/执行代码 | 提审说明中明确所有内容预打包 |
| 4.2 内容不足，看起来像测试版 | 提审前确保所有功能可用，UI 完整 |
| 2.1 崩溃 / 重大 bug | 提审前充分测试，特别是首启流程 |
| 5.1.5 位置权限滥用 | N/A（不收集） |
| 元数据违规 | 关键词不堆砌、描述真实 |

---

## 14. 时间线建议

| 阶段 | 任务 | 预估时长 |
| --- | --- | --- |
| 第 1 周 | 完成 sandbox 兼容性改造评估 + 决定走 MAS / Developer ID 哪条路 | 1 周 |
| 第 2-3 周 | 实施账号删除流程、首启弹窗、Privacy Policy URL 部署 | 2 周 |
| 第 4-5 周 | sandbox 改造（若选 MAS） | 2 周 |
| 第 6 周 | 准备所有素材（图标、截图、描述、问卷） | 1 周 |
| 第 7 周 | 内部冒烟 + 提交 App Store 审核 | 1 周 |
| 第 8 周 | App Review 审核（平均 1-3 天，最长 7-14 天） + 修复打回 | 1-2 周 |

**总计：8-10 周到达 App Store 上架**。
