# 工作树整理执行计划（2026-05-11）

> 在**副本隔离工作区**里执行，原仓库保持只读直到验收通过。
> 副本路径形如：`~/Desktop/yiyu-cleanup-test-<时间戳>/`
> 原仓库：`~/.openclaw/workspace/yiyu-thinktank-workbench/`（不动）

---

## 第 0 阶段：准备副本和数据备份

```bash
SRC="$HOME/.openclaw/workspace/yiyu-thinktank-workbench"
TS="$(date +%Y%m%d-%H%M%S)"
DST="$HOME/Desktop/yiyu-cleanup-test-$TS"
DATA="$HOME/Library/Application Support/YiyuThinkTankWorkbench2"

# 1. 全量复制源仓库（含 node_modules / dist，~2-3GB）
cp -Rp "$SRC" "$DST"

# 2. 备份用户数据目录（红线：永不删，先备份再说）
cp -R "$DATA" "$DATA.backup-$TS"

# 3. 副本基本校验
cd "$DST"
git status --short | wc -l    # 期望 ~16 行（10 M + 6 ??）
git log -1 --oneline           # 应该是 1a0a08d sync: 合并 origin/main...
ls node_modules | head -3      # 确认 node_modules 完整复制了
ls dist                        # 确认 dist 存在

# 4. 记录起点 commit
git rev-parse HEAD > .cleanup-start-commit
echo "副本工作区就绪：$DST"
echo "起点 commit：$(cat .cleanup-start-commit)"
```

**🛑 停下来给用户报告**：副本路径、备份路径、git status 行数、起点 commit。等用户回 "继续" 再进下一步。

---

## 第 1 阶段：建议 6 个 commit 的清单

### Commit 1 — `docs: 接手交接 + 代码库索引 + 一键打包脚本`

文件（全部 untracked，新增到主线）：

```
docs/project-handoff-2026-05-11.md             # 上游产品交接（用户上传）
docs/handoff-followup-2026-05-11.md            # 上一棒接手评估（dirty 改动分组、§4 偏差、AuthShell bug）
docs/handoff-to-claude-code-2026-05-11.md      # 给 Claude Code 的接手包
docs/cleanup-plan-2026-05-11.md                # 本文档
docs/codebase-map/README.md                    # 索引入口
docs/codebase-map/00-overview.md
docs/codebase-map/10-electron-main.md
docs/codebase-map/11-renderer-app-blocks.md
docs/codebase-map/12-renderer-misc-and-types.md
docs/codebase-map/20-backend-routes-services.md
docs/codebase-map/21-cloud-backend.md
docs/codebase-map/30-scripts.md
docs/codebase-map/31-docs.md
docs/codebase-map/40-mobile.md
scripts/build-and-ship-dmg.command             # 一键打包脚本
```

执行：

```bash
git add docs/project-handoff-2026-05-11.md \
        docs/handoff-followup-2026-05-11.md \
        docs/handoff-to-claude-code-2026-05-11.md \
        docs/cleanup-plan-2026-05-11.md \
        docs/codebase-map/ \
        scripts/build-and-ship-dmg.command

git diff --cached --stat                       # 应该 ~15 个文件 added

git commit -m "docs: 接手交接 + 代码库索引 + 一键打包脚本

- docs/project-handoff-2026-05-11.md: 上游产品交接（业务/产品意图、§4 验收、§7 排查路径、§8 数据库保护）
- docs/handoff-followup-2026-05-11.md: 上一棒（Claude Cowork）接手评估
- docs/handoff-to-claude-code-2026-05-11.md: 给 Claude Code（终端版）的接手包
- docs/cleanup-plan-2026-05-11.md: 本次工作树整理执行计划
- docs/codebase-map/: 10 个索引文件，覆盖前后端/脚本/文档/移动端
- scripts/build-and-ship-dmg.command: 一键打包脚本（build → DMG → 桌面）"
```

风险：无。

---

### Commit 2 — `fix(runtime): Electron Python 运行时硬化 + relocation 修复 (P0)`

文件：

```
src/main/main.ts        # 全文件改动（D 主题 + 上一棒 P0 修复合并）
```

执行：

```bash
git add src/main/main.ts
git diff --cached --stat                       # 应该 +72 -2 或类似数字

git commit -m "fix(runtime): Electron Python 运行时硬化 + relocation 修复 (P0)

D 主题（运行时硬化）：
- backendEnv 清理 PYTHONHOME/PYTHONPATH 防外部污染
- 新增 PYTHONNOUSERSITE=1
- 新增 assertPythonRuntimeUsable smoke 测试
- packagedRuntimeFingerprint 加入 seed.root 区分不同 venv
- validatePackagedRuntimeSeed 增加 encodings/__init__.py 存在性检查
- ensurePackagedBackendRuntime 已存在 venv 也跑健康检查，失败则重建

P0 修复（接手时新加）：
- 删完 PYTHONHOME 后，在 app.isPackaged 时显式设回到 seed root，
  避免 python-build-standalone 二进制 fallback 到编译时硬编码 /install
- VIRTUAL_ENV 存在时同步设 PYTHONPATH 到 venv site-packages
- assertPythonRuntimeUsable 去掉 -I 隔离模式，对齐真实启动环境

症状：ModuleNotFoundError: No module named 'encodings'，sys.path=['/install/lib/...']
根因：codesign / 中文路径 / App Translocation 干扰 Python self-relocation
解法：用 PYTHONHOME 显式覆盖编译时 prefix
验证：已用此修复打出可用 DMG（详见 docs/handoff-followup-2026-05-11.md §3）"
```

风险：低。

---

### Commit 3 — `feat(packaging): stabilize→verify 顺序对齐 + 启动诊断脚本`

文件：

```
scripts/package-local-mac-dmg.mjs        # M
package.json                              # M（dist:mac-local 顺序调整）
scripts/collect-mac-startup-diagnostics.command  # 新增 untracked
```

执行：

```bash
git add scripts/package-local-mac-dmg.mjs \
        package.json \
        scripts/collect-mac-startup-diagnostics.command

git diff --cached --stat

git commit -m "feat(packaging): stabilize→verify 顺序对齐 + 启动诊断脚本

- scripts/package-local-mac-dmg.mjs: verify 移到 stabilize 之后，且对 staged 副本 verify
- package.json: dist:mac-local 内部 stabilize→verify 顺序调整一致
- scripts/collect-mac-startup-diagnostics.command: 新增双击式启动诊断脚本，
  用户首启失败时双击即可生成 ~/Desktop/yiyu-startup-diagnostics-*.txt"
```

风险：低。

---

### Commit 4 — `feat(workspace): 数据中心本地模型优化队列 + UnderstandingSnapshot.humanBrief`

文件：

```
src/shared/types.ts                # M（B 主题 + humanBrief 一个 hunk）
backend/app/models.py              # M（B 主题）
backend/app/main.py                # 仅 3 个 hunk：line 778、33521、33651
```

**重要**：`backend/app/main.py` 跨 A 和 B 两个主题，必须用 `git add -p` 拆 hunk。

执行：

```bash
git add src/shared/types.ts backend/app/models.py

# 拆 hunk 处理 backend/app/main.py：保留 B 主题的 3 个 hunk，跳过 A 主题的 25102 hunk
git add -p backend/app/main.py
# 交互式 prompt 出现时：
#   - hunk 1 (@@ -774,6 +774,11 import app.services.local_model_optimizer)  → y
#   - hunk 2 (@@ -25097 _remembered_cloud_auth_store)                          → n   ← A 主题，跳过
#   - hunk 3 (@@ -33505 localOptimization 字段加入 jobs response)             → y
#   - hunk 4 (@@ -33634 enqueue/retry action handlers)                         → y

git diff --cached --stat
git diff --cached backend/app/main.py | head -50    # 校验没误带 25102 段

git commit -m "feat(workspace): 数据中心本地模型优化队列 + UnderstandingSnapshot.humanBrief

B 主题（本地模型优化）：
- src/shared/types.ts: 新增 WorkspaceDataCenterLocalOptimizationStatus 接口
  和 enqueue_local_model_optimization / retry_local_model_optimization action types
- backend/app/models.py: 镜像 record + Literal 扩展
- backend/app/main.py: import app.services.local_model_optimizer 三个函数，
  在 jobs response 挂 localOptimization 字段，新增 enqueue/retry 两个 action handler

附带（同区域类型补丁）：
- src/shared/types.ts: UnderstandingSnapshotV1 新增 humanBrief 字段
  （配合前端 UnderstandingPanel.tsx 和后端 understanding_builder.py 已有的实现）

前置依赖确认：
- backend/app/services/local_model_optimizer.py 已存在（31KB，3 个导出函数齐全）
- src/renderer/components/data_center/DataCenterOpsPanel.tsx 已有完整 UI 调用入口
- backend/tests/test_local_model_optimizer.py 已有测试覆盖"
```

风险：低。

---

### Commit 5 — `fix(auth): 本机模式与益语账号术语清晰化 + 记住凭据兜底`

**⚠️ 在 feature 分支上，不进 main**

文件：

```
src/renderer/App.tsx                # M（A 主题，所有 hunk）
backend/app/main.py                 # 剩下未提交的 1 个 hunk：line 25102
```

执行：

```bash
# 1. 切分支
git checkout -b feature/auth-terminology-cleanup

# 2. 加文件
git add src/renderer/App.tsx
git add backend/app/main.py    # 此时只剩 A 主题那个 hunk，可整体 add

git diff --cached --stat
git status --short              # backend/app/main.py 应该已经 staged

git commit -m "fix(auth): 本机模式与益语账号术语清晰化 + 记住凭据兜底

A 主题：
- src/renderer/App.tsx:
  - 术语统一：'云端账号' → '益语账号'
  - 新增 membership status 'local'，对应 '本机模式' 视觉标签
  - AccountIdentityCard 拆分本机/云端两种视图
  - saveCloudAuthInputMemory 用 response.user 数据 + fallback，
    避免登录成功后 '记住的 fullName' 被空值覆盖
- backend/app/main.py: _remembered_cloud_auth_store 同步逻辑，
  用 cached session user 兜底保住 fullName / email

⚠️ 已知偏差（详见 docs/handoff-followup-2026-05-11.md §2 与 §4 验收对照表）：
  1. Tab 文案当前是 '登录账号/注册账号'，§4 要求 '登录/注册'
  2. 缺 '找回密码' 入口
  3. 缺 '组织全称' 输入框
  4. '两步式' 注册 vs §4 的 '两种平行模式'
  5. AuthShell 内联组件导致输入消失（§3）尚未修复

下一步：按用户决策修上述偏差后再 merge 回 main。"

# 3. 回 main 分支继续后续 commit
git checkout main
```

风险：中（含 §4 偏差，不进主线）。

---

### Commit 6 — `feat(cloud-auth): 组织创建者自动 bootstrap 为 admin`

**⚠️ 在 feature 分支上，不进 main**

文件：

```
cloud_backend/app/main.py
cloud_backend/tests/test_local_first_auth.py
```

执行：

```bash
git checkout -b feature/cloud-bootstrap-admin

git add cloud_backend/app/main.py cloud_backend/tests/test_local_first_auth.py
git diff --cached --stat

git commit -m "feat(cloud-auth): 组织创建者自动 bootstrap 为 admin

C 主题：
- 5 个 helper：_organization_has_approved_admin / _is_first_organization_account /
  _should_bootstrap_organization_owner / _ensure_founder_role_bindings /
  _ensure_org_profile_owner / _auto_approve_bootstrap_owner_account
- 注入点：_require_auth、_ensure_login_allowed、/api/v1/auth/register、
  /api/v1/me/org-membership 申请流程
- 行为：首位组织账号或新建组织的注册者自动获得
  primaryRole=admin、account_status=approved、membership_status=approved
- 写入 employee_role_bindings、org_profiles.leader_user_id
- 审计日志 bootstrap_org_owner

测试更新（cloud_backend/tests/test_local_first_auth.py）：
- 原断言 membershipStatus='none' / hasOrganization=False / tasks→403
  改为 membershipStatus='approved' / hasOrganization=True / tasks→200
- 新增 3 个测试：profile 字段触发 bootstrap、首位账号被后来者抢 admin 时的修复路径

⚠️ 与内测 DMG 弱关联（DMG 走本地后端 127.0.0.1:47829）。
   等云端联调时再 merge 回 main。"

git checkout main
```

风险：低（有测试，对本地后端无影响），但与内测 DMG 无关。

---

## 第 2 阶段：mobile 子模块处理（推荐方案 B）

```bash
# 选项 B：解耦，让 mobile 独立管理，主仓库不再追踪 gitlink
git rm --cached mobile
echo "mobile/" >> .gitignore
git add .gitignore
git commit -m "chore(mobile): 解耦移动端子仓库，由 mobile 自身 git 管理

- 主仓库不再以 gitlink 形式追踪 mobile 目录
- mobile/ 加入 .gitignore
- mobile 自己有完整 git 历史（HEAD: bb64401 Initial public mobile source snapshot）
  和 dirty 工作区，独立处理"
```

---

## 第 3 阶段：副本里验证

```bash
cd "$DST"
git status --short       # 应该完全干净（除了 mobile/ 如果选了方案 B）
git log --oneline -10    # 应该看到 5 个新 commit 在 main 上

# 重打 DMG 验证
bash scripts/build-and-ship-dmg.command
# 产物：~/Desktop/益语智库自用平台 V2.0-<新时间戳>-arm64-local.dmg

# 装机冒烟
node scripts/install-and-smoke-mac-dmg.mjs --keep-running

# 手工冒烟 checklist
#   [ ] 打开的是 ~/Applications/益语智库自用平台 V2.0.app
#   [ ] 首屏默认登录页，不弹 Python encodings 错误
#   [ ] 登录页输入账号密码，等 10 秒看是否消失（验证 AuthShell bug 是否触发）
#   [ ] 任务与日程、月历能打开
#   [ ] 数据中心面板能看到 localOptimization 状态（验证 B 主题）
#   [ ] 关闭再打开，记住状态正常
```

**🛑 停下来给用户报告**：装机结果。等用户视觉验收（截图给 Cowork 那边的 Claude）+ 决策"通过/不通过"。

---

## 第 4 阶段：通过后推回原仓库（验收完才执行）

```bash
ORIG="$HOME/.openclaw/workspace/yiyu-thinktank-workbench"
COPY="$DST"

cd "$ORIG"

# 方案 1（推荐）：从副本拉 main 分支
git pull "$COPY" main --no-rebase
# 同时拉两个 feature 分支
git fetch "$COPY" feature/auth-terminology-cleanup:feature/auth-terminology-cleanup
git fetch "$COPY" feature/cloud-bootstrap-admin:feature/cloud-bootstrap-admin

git status --short       # 应该全干净
git log --oneline -10    # 看到新 commits

# 方案 2（更稳但慢）：在原仓库重复一遍相同的 git 操作
# （略，太繁琐，不推荐）
```

如果不通过：

```bash
rm -rf "$DST"
# 用户数据如有污染：
mv "$DATA.backup-$TS" "$DATA"
```

---

## 验收红线（执行全程必须守住）

- 🚫 不删 `~/Library/Application Support/YiyuThinkTankWorkbench2/` 任何东西
- 🚫 不在原仓库 `~/.openclaw/workspace/yiyu-thinktank-workbench/` 执行任何写操作（直到第 4 阶段）
- 🚫 不动 mobile/ 子仓库的内部状态
- 🚫 不 force push、不 rebase
- ✅ 每个 commit 前 `git diff --cached --stat` 给用户看一眼
- ✅ 每个停下点都向用户报告

---

## 异常恢复

副本里出问题：

```bash
cd "$DST"
git reset --hard $(cat .cleanup-start-commit)    # 回到副本起点
# 或者更狠：删副本重做
rm -rf "$DST"
```

原仓库无论如何都不会受影响——这就是隔离副本的意义。
