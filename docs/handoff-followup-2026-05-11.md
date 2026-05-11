# 益语智库项目接手评估报告（2026-05-11）

本报告是基于 `docs/project-handoff-2026-05-11.md` 完成的接手评估。仓库已在
`/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench`，工作区 dirty，
未做任何写入或 reset 动作；本次只读评估 + 决策清单。

## 0. 一句话结论

工作区里的未提交改动可以分成 5 条独立工作线，**绝大多数是健康的**，并且其中 4 条
（A/B/D/E）直接服务于"内测 DMG"目标。但有 3 个需要你拍板的偏差和 1 个高优先级
Bug 根因，必须在打包前确认或修复，否则发出去的内测包很可能在登录注册首屏就翻车。

## 1. 未提交改动按工作线拆解

| 主题 | 涉及文件 | 性质 |
| --- | --- | --- |
| A. 本机模式 / 益语账号术语清晰化（含"记住的 fullName 被清空" fix） | `src/renderer/App.tsx`、`backend/app/main.py`（`_remembered_cloud_auth_store` 段） | UI + 后端 |
| B. 数据中心新增"本地模型优化"队列功能 | `src/shared/types.ts`、`backend/app/main.py`（import 与两个 action handler）、`backend/app/models.py` | 后端 + 前端类型 |
| C. 云端：组织创建者自动 bootstrap 为 admin | `cloud_backend/app/main.py`、`cloud_backend/tests/test_local_first_auth.py` | 云端业务逻辑 |
| D. Electron 主进程：Python 运行时硬化 | `src/main/main.ts` | 桌面壳 |
| E. 打包流程加固：stabilize → verify 顺序、对 staged 副本 verify | `scripts/package-local-mac-dmg.mjs`、`package.json`、`scripts/collect-mac-startup-diagnostics.command`（新增） | 打包脚本 |

### A 的具体改动

- App.tsx 把"云端账号"统一改成"益语账号"，新增 `'local'` membership status，
  AccountIdentityCard 拆分本机/云端两种视图。
- App.tsx 的 `saveCloudAuthInputMemory` 调用增加了用 `response.user.email/fullName`
  做兜底的逻辑，避免登录成功后"记住的 fullName"被空值覆盖。
- backend `_remembered_cloud_auth_store` 同步加了基于 cached session user 的身份
  覆盖逻辑，保住 fullName / email 不被 payload 空值清掉。

### B 的具体改动

- `types.ts` 新增 `WorkspaceDataCenterLocalOptimizationStatus`（18 个字段：队列总数 /
  并发 / 已完成 / 失败计数 / 窗口标签等）；同时新增两个 action type
  `enqueue_local_model_optimization`、`retry_local_model_optimization`。
- `backend/app/models.py` 镜像一份 record + 把两个 action type 加入 Literal 枚举。
- `backend/app/main.py` 导入 `app.services.local_model_optimizer` 的 3 个函数
  （`enqueue_local_model_optimization_tasks` / `get_local_model_optimization_stats` /
  `retry_failed_local_model_optimization_tasks`），并在 readiness jobs 响应里挂
  `localOptimization` 字段、在 action 处理器里加两个分支。
- 实测：`backend/app/services/local_model_optimizer.py` 已存在（31KB），三个函数齐全。
  不会因为这次改动 ImportError。

### C 的具体改动

新增 5 个云端 helper：

- `_organization_has_approved_admin` / `_is_first_organization_account` / `_should_bootstrap_organization_owner`
- `_ensure_founder_role_bindings` / `_ensure_org_profile_owner`
- `_auto_approve_bootstrap_owner_account`

这些 helper 被插入到 `_require_auth`、`_ensure_login_allowed`、`/api/v1/auth/register`、
`/api/v1/me/org-membership` 申请流程里——首个组织账号或新建组织的注册者会自动获得
`primaryRole=admin`、`account_status=approved`、`membership_status=approved`，
并写入 `employee_role_bindings`、`org_profiles.leader_user_id`，记审计日志
`bootstrap_org_owner`。

测试 `test_local_first_auth.py` 已经把断言对齐到新行为：以前期望 `membershipStatus="none"` /
`hasOrganization=False` / `/api/v1/tasks → 403`，现在期望 `"approved"` / `True` / `200`。
还新增 3 个测试覆盖：带 profile 字段触发 bootstrap、首位账号被后来者抢 admin 时的修复路径。

**这一条与内测 DMG 目标关联较弱**，因为内测 DMG 走的是本地后端（端口 47829），
不直接连云。除非测试同事去注册新组织并触发云端 bootstrap，否则当前 DMG 不依赖这块。

### D 的具体改动

- `backendEnv()` 主动 `delete env.PYTHONHOME / env.PYTHONPATH`，再加 `PYTHONNOUSERSITE=1`，
  彻底避免外部 Python 环境污染打包运行时。
- 新增 `assertPythonRuntimeUsable(pythonPath, label, env)`：用 `-I`（isolated mode）
  跑 `import encodings; print(...)`，能在打包阶段就发现 Python 标准库缺失 / venv 损坏。
- `packagedRuntimeFingerprint` 现在把 `seed.root` 加入指纹，不同位置的 seed 不会再
  误共用旧的 venv。
- `validatePackagedRuntimeSeed` 增加 `encodings/__init__.py` 存在性检查。
- `ensurePackagedBackendRuntime` 路径：venv 存在时也会跑一次 self-check，失败就重建；
  重建前先 smoke-test seed Python；wheel 装完之后再 smoke-test venv Python。

这套改动**直接对应**交接文档 §7.3"注册页提示无法连接本地服务"的根因排查路径，
是这次 dirty 工作区里最高价值的一块。

### E 的具体改动

- `scripts/package-local-mac-dmg.mjs`：把 `verify-packaged-app.mjs` 从输入路径
  移到 staged 副本上跑，并放在 `stabilize-mac-app.mjs` 之后；保证我们 verify 的
  正是最终进 DMG 的 app。
- `package.json` 的 `dist:mac-local` 同样调换 stabilize / verify 顺序。
- 新增 `scripts/collect-mac-startup-diagnostics.command`：双击就能跑的诊断脚本，
  把日志输出到 `~/Desktop/yiyu-startup-diagnostics-<ts>.txt`，定位 App / 进程 /
  端口 / 日志四件套。

## 2. 与 §4 登录注册验收标准的对比

逐条比对工作区当前状态 vs 交接文档第 4 节验收清单：

| 验收项 | 当前状态 | 结论 |
| --- | --- | --- |
| 首屏默认登录页（不是注册、不是云端绑定弹窗） | `renderBranch` 走 `!authState.authenticated → AuthShell`，AuthShell 内 `mode` 初值 `'login'` | ✅ |
| 页面整体居中 | `min-h-screen ... flex items-center justify-center` | ✅ |
| 比最初大图缩小约 20% | 当前 `max-w-[980px]`，无可对比的"最初大图"基准，无法机械判定 | ⚠️ 需肉眼对齐 |
| 顶部 Tab 文案"登录"/"注册" | **当前是"登录账号"/"注册账号"** | ❌ 冲突 |
| 登录表单只保留账号、密码、找回密码 | 实际：账号选择(可选下拉) + 邮箱/手机 + 密码 + "记住我的登录状态" + "显示密码" + "记住这组账号和密码(仅本机)"；**没有"找回密码"入口** | ❌ 缺失 |
| 增加"记住我的登录状态"勾选 | 文案完全匹配，`rememberMe` state 接到 `login()` 调用 | ✅ |
| 输入账号密码时内容不会因刷新或渲染分支切换而消失 | A 主题改了"记住值兜底"，但**根因没修**（见 §3） | ⚠️ 治表 |
| 注册页分"个人注册"和"组织注册" | 当前是 Step 1 = 个人账号 → Step 2 = 组织身份 的"两步式"，不是"两种平行模式" | ⚠️ 语义偏差 |
| 个人注册字段：姓名、邮箱、密码、重复密码、组织邀请码 | Step 1 实际：姓名 / 邮箱 / 登录手机号(可选) / 密码 / 确认密码；**组织邀请码不在个人步骤，在 Step 2** | ⚠️ 字段归位 |
| 组织注册需"组织全称"（工商或民政注册全称） | 表单 state 里**完全没有 `organizationName` 字段**，注册 payload 也没传；当前注册时云端用 fullName 自动拼"<姓名> 的组织" | ❌ 关键缺失 |
| 底部盾牌只是装饰物、缩小、放底部、不遮挡说明 | 没找到独立的"底部盾牌装饰"组件，左侧封面顶部有一个 12×12 圆角方块里的 `ShieldAlert` icon | ⚠️ 需肉眼对齐 |

## 3. 高优先级 Bug 根因：输入内容突然消失

`AuthShell` 是在 `App` 函数体内部声明的内联组件（`const AuthShell = () => { ... };`，
约 line 7556），在渲染时用 `return <AuthShell />;`（约 line 23292）。

App 顶层有 backend health polling、session recovery、`localInputMemory` 等高频
setState，**任何一次重渲染都会让 `AuthShell` 拿到新的函数引用，React 视为新组件类型，
卸载旧实例并挂载新实例，导致 AuthShell 内 `useState` 创建的 form / rememberMe /
showPassword 等状态全部重置成初始值**。

这条恰好命中交接文档 §7.4 列出的可能原因之一"登录/注册组件 key 是否因为状态变化
而变化"——AuthShell 不是 key 变了，而是组件类型本身就在变。

**修复方法**（任选其一）：

1. 把 `AuthShell` 提到 App 函数外（顶级声明），需要的 state 用 props 传进去或者
   AuthShell 自己持有 +  callback 上报。改动最干净。
2. 把 `AuthShell` 包成 `useMemo(() => () => { ... }, [...deps])`——临时但能止血。
3. 把 AuthShell 改成 inline JSX（不抽组件），直接在 App 的 return 里写出来。

建议走方案 1。本次评估**没有**对源码做任何修改，等你确认方向再动手。

## 4. 已知风险与待澄清项

### 必须你拍板的决策

1. **Tab 文案到底用"登录"/"注册"还是"登录账号"/"注册账号"？**  
   §4 验收要求前者，dirty 改动改成了后者。
2. **是否补"找回密码"入口？** §4 验收明确要保留；当前完全没有。
3. **是否补"组织全称"输入框？** §4 验收明确要在组织注册里有；当前表单字段都没有，
   后端 payload 也没传。
4. **注册页"两步" vs "两种"？** §4 用的是"分类"语义（个人注册 / 组织注册），
   当前实现是"分步"。要不要改成 mode 切换式？
5. **C 主题（云端组织 bootstrap admin）是否进本次内测包？**  
   内测包只跑本地后端，所以这块本身不影响 DMG 能否打开；但因为它和登录注册同分支，
   后面合并主线时需要单独评审。建议**保留在工作区**、先单独写一个 commit 标题方便回滚。

### 仍需治理的根因（修不修请你定）

- AuthShell 内联组件导致输入丢失（§3 详述）。
- §6 步骤 7 中"关闭再打开后记住登录状态"的端到端验证，目前没看到自动化覆盖；
  云端测试只覆盖云端注册侧。
- 移动子模块 `mobile` 显示 modified（自身工作区也 dirty 一大片），交接文档要求
  单独确认；这次评估**未触碰**子模块。

### 数据库保护（已守住，重申一遍）

- 不动 `~/Library/Application Support/YiyuThinkTankWorkbench2`。
- `app.db` 在仓库根目录是 0 字节占位，真正的数据库在用户数据目录下，请勿 rm。
- `install-and-smoke-mac-dmg.mjs --keep-running` 会清 `runtime/backend-venv`，
  这是可重建的运行时缓存，不是数据。

## 5. 在你 Mac 上跑的命令序列（按 §6 整理）

我的 shell 是 Linux 沙箱，没法执行 Mac 打包命令。下面这串你贴到 Mac 终端依次跑就行
（已对齐 dirty 工作区里 package.json 的新顺序）：

```bash
cd /Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench

# 0. 决策点：先决定上面 §4 的 5 条到底改不改、什么时候改。
#    如果不改，直接跳到 step 1；如果改，先改源码再走 step 1。

# 1. 工作区状态二次确认
git status --short

# 2. 构建前端 + 打包后端运行时（含 stabilize → verify）
npm run build
npm run dist:mac-local
# 产物：dist/mac-arm64/益语智库自用平台 V2.0.app

# 3. 生成内部测试 DMG（脚本内部会再做一次 stabilize + verify on staged copy）
node scripts/package-local-mac-dmg.mjs
# 产物：dist/益语智库自用平台 V2.0-0.1.0-arm64-local.dmg（旧的会被覆盖）

# 4. 验证 DMG
node scripts/verify-mac-dmg.mjs

# 5. 安装并自动冒烟
node scripts/install-and-smoke-mac-dmg.mjs --keep-running
# 期望：~/Applications/益语智库自用平台 V2.0.app 被替换为新版本，
#       本地后端在 127.0.0.1:47829 上线，电脑保留运行供你手工冒烟。

# 6. 手工冒烟 checklist（对照 §6 步骤 7）
#    [ ] 打开的是 ~/Applications/益语智库自用平台 V2.0.app（用 pgrep / mdfind 确认）
#    [ ] 首屏默认是登录页
#    [ ] 登录表单字段 / 找回密码 / "记住我的登录状态" 都在
#    [ ] 注册个人 / 组织 Tab 与字段正确（含组织全称——如果你拍板要补）
#    [ ] 在登录页连续输入账号密码，等 5 秒（让 backend health polling 跑几轮），
#        确认内容不被清空——这是验证 §3 修复是否生效
#    [ ] 关闭再打开，记住状态保留

# 7. 记录 DMG 路径与 sha256（脚本会输出，截下来）
shasum -a 256 "dist/益语智库自用平台 V2.0-0.1.0-arm64-local.dmg"
```

如果 step 2/3/5 中任何一步报错，先把报错完整贴回来——尤其是 `backend:packaged-*-smoke`
开头的诊断输出，那就是 §D 主题新加的自检在干活，能直接定位是 Python 还是 venv 哪里
坏了。

如果同事装好打不开，让他双击 `scripts/collect-mac-startup-diagnostics.command`，
桌面会生成一份 `yiyu-startup-diagnostics-<ts>.txt`，回传给你。

## 6. 我下一步能直接做（等你点头）

- 修 AuthShell 内联组件 bug（方案 1：提到 App 外，prop 化）。
- 加"找回密码"占位入口（前端弹个"请联系管理员重置"提示，等后端有 reset 接口再接）。
- 加"组织全称"输入框 + 接到 register payload。
- 把 dirty 改动按主题拆成 5 个 commit 草稿（不真 commit，写到 `docs/dirty-split-plan.md`），
  方便你后面 cherry-pick 或分支隔离。
- 把这份报告对应的 git diff 摘要进一步精炼成一页 PR description，给同事评审用。

逐条等你确认要哪几项，再动手。

## 7. 已严格遵守的红线

- 不动 `~/Library/Application Support/YiyuThinkTankWorkbench2/`（也没有任何 Linux 沙箱里能动它的路径）。
- 不 `git reset`、不 stash、不 checkout 覆盖现有 dirty 改动。
- 不写任何源码（本次评估只读 + 写一份新文档到 `docs/`）。
- 不动 `mobile/` 子模块、`dist/` 既有产物。
- 不在 UI 上给"无法连接本地服务"加新兜底——这种问题已经有 §D 的根因治理，不该上层缝合。
