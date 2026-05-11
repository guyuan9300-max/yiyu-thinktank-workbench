# 接手包：益语智库桌面端项目（给 Claude Code / 顶替我的人）

> 写于 2026-05-11，写完时间戳 `20260511-174131`。
> 上一棒（Claude，Linux 沙箱环境）已经做完一波接手评估 + 一次 P0 修复 + 出了一个内测 DMG 放桌面。
> 你接手后**先读完本文档再动手**。你有用户 Mac 上的真实 shell 权限，可以直接跑 `npm`、`codesign`、`hdiutil` 等命令；上一棒不能。

---

## 0. 项目坐标

| 项 | 值 |
| --- | --- |
| 仓库路径 | `/Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench`（**注意 .openclaw 隐藏目录**） |
| App ID | `com.yiyu.selfworkbench2` |
| 产品名 | `益语智库自用平台 V2.0` |
| 安装路径（默认） | `~/Applications/益语智库自用平台 V2.0.app` |
| 用户数据目录（**永不删**） | `~/Library/Application Support/YiyuThinkTankWorkbench2/` |
| 本地后端端口 | `127.0.0.1:47829` |
| 当前 git 分支 | `main` |
| 当前 HEAD | `1a0a08d sync: 合并 origin/main 后继续推送选中的本地修改` |

---

## 1. 当前立即任务（用户最关心的）

把这个项目打包成 DMG 放桌面给同事内测。

- 上一棒已经产出过一个：`~/Desktop/益语智库自用平台 V2.0-20260511-174131-arm64-local.dmg`（约 264MB，含 P0 #1 修复）
- 上一棒已经写好一键脚本：`scripts/build-and-ship-dmg.command`（双击或 `bash scripts/build-and-ship-dmg.command` 直接跑，60-120 秒出 DMG 到桌面）
- 你接手后，建议**先验证现有 DMG 是否真的可用**（见 §6 验证步骤），不必盲目重打；如果 §4 决策有改动，再重打

---

## 2. 上下游文档（按重要性读）

1. **`docs/project-handoff-2026-05-11.md`** — 上游交接（产品负责人写的，业务/产品意图，包含 §4 登录注册验收标准、§7 排查路径、§8 数据库保护边界、§9 已知风险等）。**这是项目宪法**，先读。
2. **`docs/handoff-followup-2026-05-11.md`** — 上一棒接手评估（dirty 改动 5 主题分组、§4 验收偏差对比表、AuthShell 高优先级 Bug 根因、命令序列）
3. **`docs/codebase-map/README.md`** — 代码库索引入口（10 个索引文件覆盖：仓库全景、主进程、App.tsx 区块图、types.ts 导出、本地/云端路由表、scripts 用途、文档主题）
4. **本文档** — 桥接两者，给你做下一步决策用

代码索引的用法：找东西时**先 grep `docs/codebase-map/*.md` 拿行号**，再 `sed -n 'AAA,BBBp' src/file.ts` 精读那一节——别一上来读 23000 行的 `App.tsx`。

---

## 3. 当前 dirty 工作区状态（**不要 git reset，不要 stash**）

```
 M backend/app/main.py                        # A 主题 + B 主题
 M backend/app/models.py                       # B 主题
 M cloud_backend/app/main.py                   # C 主题
 M cloud_backend/tests/test_local_first_auth.py  # C 主题
 m mobile                                      # 子模块 dirty（先不动）
 M package.json                                # E 主题（打包脚本顺序）
 M scripts/package-local-mac-dmg.mjs           # E 主题
 M src/main/main.ts                            # D 主题 + 上一棒新加的 P0 #1 修复
 M src/renderer/App.tsx                        # A 主题（登录注册术语 + §4 偏差）
 M src/shared/types.ts                         # B 主题
?? docs/codebase-map/                          # 上一棒建的索引
?? docs/handoff-followup-2026-05-11.md         # 上一棒的评估
?? docs/handoff-to-claude-code-2026-05-11.md   # 本文档
?? docs/project-handoff-2026-05-11.md          # 上游交接
?? scripts/build-and-ship-dmg.command          # 上一棒写的一键打包脚本
?? scripts/collect-mac-startup-diagnostics.command  # dirty 工作区里的诊断脚本
```

### dirty 改动 5 主题（详见 handoff-followup §1）

- **A. 本机模式 / 益语账号术语清晰化**：App.tsx + backend `_remembered_cloud_auth_store` 段，把"云端账号"统一改成"益语账号"、新增 `'local'` membership 状态、修了"记住的 fullName 被清空" bug
- **B. 数据中心新增"本地模型优化"队列**：types.ts + backend main.py 引入 `app.services.local_model_optimizer`，加两个 action handler；服务文件已存在 31KB 不会 ImportError
- **C. 云端：组织创建者自动 bootstrap 为 admin**：cloud_backend 加 5 个 helper，注入到 register / membership 流程；测试已对齐新行为。**与内测 DMG 关联弱**（DMG 走本地后端）
- **D. Electron 主进程 Python 运行时硬化**：main.ts 清理 PYTHONHOME 污染、加 `assertPythonRuntimeUsable` smoke 测试、fingerprint 加入 root、encodings 验证等。**上一棒在这块基础上又改了一次 → §4**
- **E. 打包流程加固**：stabilize → verify 顺序对齐，对 staged 副本 verify；新增 `collect-mac-startup-diagnostics.command`

---

## 4. 上一棒最重要的一次代码改动（**你需要知道这件事**）

### P0 修复：Python 启动报 `ModuleNotFoundError: encodings`

**症状**：用户首次启动打包的 app，主窗口弹错误 `Fatal Python error: init_fs_encoding`、`sys.path = ['/install/lib/python311.zip', ...]`。

**根因**：D 主题在 `backendEnv()` 里**新加**了 `delete env.PYTHONHOME; delete env.PYTHONPATH`，意图是防外部 Python 污染，但删完没有重新设置。当 python-build-standalone 二进制的 self-relocation 因 codesign / 中文路径 / App Translocation 失败时，Python fallback 到编译时硬编码的 `/install`，找不到 stdlib。

**修复**（已 apply 到 `src/main/main.ts`）：

1. `backendEnv()` 函数末尾、`return env;` 之前，新加一段：当 `app.isPackaged` 且 seed 完整时，显式设 `PYTHONHOME = <bundle>/Contents/Resources/runtime/python-seed`；如果 `VIRTUAL_ENV` 也设了，把 `PYTHONPATH` 设到 `<venv>/lib/python3.11/site-packages`（因为 PYTHONHOME 一旦设了，pyvenv.cfg 的 home 解析就被覆盖）。
2. `assertPythonRuntimeUsable()` 去掉 `-I` 隔离模式（隔离模式会忽略 PYTHONHOME 和 pyvenv.cfg，导致 smoke 测试在用户机器上必然误判）。

补丁特征：`+72 / -2`，仅改 `src/main/main.ts`。git diff 可见。

如果你重打 DMG 然后启动还报同样的 Python 错误，先确认这个修复**真的被编译进了 main 进程**（看 `.app/Contents/Resources/app.asar` 里反编译出来的 main 是否含 `PYTHONHOME = seedRoot` 字样）。

---

## 5. 上一棒留下的待决策清单（**用户还没拍板**）

来自 `docs/project-handoff-2026-05-11.md` §4 登录/注册首屏验收标准，dirty 改动与之的偏差：

1. **Tab 文案**：§4 要求"登录"/"注册"，dirty 改成了"登录账号"/"注册账号"。位置：`src/renderer/App.tsx` line 7742-7743
2. **找回密码入口**：§4 要求保留，**全代码搜不到任何"找回密码"或"忘记密码"关键字**。位置：登录表单字段区
3. **组织全称输入框**：§4 要求组织注册必填"组织全称"（工商/民政注册全称），**表单 state 里完全没有 `organizationName` 字段**，注册 payload 也没传
4. **注册页"两步"vs"两种"**：§4 用的是分类语义（个人注册 / 组织注册），当前实现是分步（Step 1 个人 → Step 2 组织）
5. **C 主题是否进本次内测**：云端 bootstrap admin 改动，与 DMG 目标弱关联，可单独分支隔离

### 还有 1 个高优先级 Bug 根因（**上一棒只定位没修**）

**`AuthShell` 组件是在 App 函数体内部定义的内联组件**（约 `src/renderer/App.tsx` line 7556 处 `const AuthShell = () => { ... }`，line 23292 `return <AuthShell />;`）。

App 顶层有 backend health polling、session recovery、`localInputMemoryState` 等高频 setState，**每次 App 重渲染，AuthShell 都是新函数引用，React 把它当作新组件类型 → 卸载旧实例、挂载新实例 → 内部 useState 创建的所有 form / rememberMe / showPassword 状态重置成初始值**。

这是 §7.4「输入时内容突然消失」的最可能根因。

**修复方法**：把 `AuthShell` 提到 App 函数外（顶级声明），需要的 state 用 props 传进去或 AuthShell 自己 useState + callback 上报。改动较 invasive，未做，等用户点头。

---

## 6. 桌面 DMG 的验证步骤（**最先做这个**）

```bash
cd /Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench

# 1. 确认现有 DMG 真的在桌面
ls -la "$HOME/Desktop/" | grep "20260511-174131"
# 期望看到：益语智库自用平台 V2.0-20260511-174131-arm64-local.dmg

# 2. 比对 sha256（自检完整性）
shasum -a 256 "$HOME/Desktop/益语智库自用平台 V2.0-20260511-174131-arm64-local.dmg"

# 3. 看构建日志最后 30 行确认无 [FAIL]
tail -30 "$HOME/Desktop/yiyu-build-20260511-174131.log"

# 4. 装到本机验证 P0 修复是否真生效（关键！）
xattr -dr com.apple.quarantine "$HOME/Desktop/益语智库自用平台 V2.0-20260511-174131-arm64-local.dmg"

# 挂载 + 拖到 ~/Applications，或者用脚本：
node scripts/install-and-smoke-mac-dmg.mjs --keep-running

# 5. 启动看是否还报 Python 错误
#    如果不报 → P0 修复生效，进入下一步
#    如果还报 → 看 ~/Library/Application\ Support/YiyuThinkTankWorkbench2/electron-launch.log
#              用 docs/codebase-map/10-electron-main.md 找 backendEnv 重新定位
```

---

## 7. 如果要重打 DMG

```bash
cd /Users/guyuanyuan/.openclaw/workspace/yiyu-thinktank-workbench

# 用上一棒写的一键脚本（已经 chmod +x）
bash scripts/build-and-ship-dmg.command
# 或者 Finder 双击该文件
# 产物自动落在 ~/Desktop/，文件名带新时间戳

# 或者手工分步（如果要细粒度控制）：
rm -rf dist/mac-arm64 dist/packaged-runtime  # 保留旧 DMG 作为回滚证据
npm run build
npm run dist:mac-local
node scripts/package-local-mac-dmg.mjs
node scripts/verify-mac-dmg.mjs
cp "dist/益语智库自用平台 V2.0-0.1.0-arm64-local.dmg" "$HOME/Desktop/"
```

**注意**：脚本里**不要走 `npm ci`**——`package-lock.json` 里有 `@rollup/rollup-linux-arm64-gnu` 等 linux-only 条目，`npm ci` 会因 EBADPLATFORM 拒装。`npm install` 或直接复用现有 `node_modules` 都行。

---

## 8. 红线（**严格守住**）

- 🚫 **不删** `~/Library/Application Support/YiyuThinkTankWorkbench2/` 任何东西（用户数据库、运行证据、导入文档都在这里）
- 🚫 **不 git reset / git stash / git checkout 覆盖现有 dirty 改动**
- 🚫 **不动 `mobile/` 子模块**（自身也 dirty，需要单独评审；交接文档明确要求）
- 🚫 **不在 UI 上给"无法连接本地服务"加新兜底**——§7.3 已有根因治理（D 主题 + P0 #1 修复），加 UI 兜底是治标
- 🚫 **不删 `dist/` 下的旧 DMG**——留作回滚证据
- ✅ 修任何 §4 偏差前，先和用户确认要不要修、用什么方案
- ✅ 任何改动前，先 grep `docs/codebase-map/*.md` 定位、再读源码相关行区间、再动手

---

## 9. 你接手后的建议起手顺序

1. 读完本文档 + §2 的 4 份文档（约 30 分钟）
2. 跑 §6 的验证步骤，确认现有 DMG 装上去**没有 Python 错误**
3. 如果通过 → 跟用户报"现有 DMG 可用，待你拍板是否处理 §5 的 5 个决策 + AuthShell bug"
4. 如果不通过 → 看 `electron-launch.log` 和 `~/Library/.../runtime/logs/`，对照 §4 的 P0 修复定位是哪一步失效，**先别盲改**
5. 任何源码改动前，写一个 1 段话的"我准备改 file:start-end 这段，原因 X，预期 Y"先告诉用户

---

## 10. 上一棒的能力边界（供你对照）

上一棒（Linux 沙箱环境）能做的：读源码、改源码、用 bash 在挂载目录里查文件 / git diff。
**不能**做的：跑 `codesign` / `hdiutil` / `electron-builder --mac` 等 macOS-only 命令，所以最后通过 computer-use 驱动 Finder 双击脚本完成打包。

**你（Claude Code）**有 macOS shell 真实权限，可以直接跑所有命令，不用走 computer-use 这条慢链路。但**所有红线照样守**。

祝顺利。如果还想看上一棒的具体改动思路，`git diff src/main/main.ts` 看最末段（PYTHONHOME 修复）。
