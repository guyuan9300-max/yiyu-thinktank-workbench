# 主动能力线程 · Claude Code 执行计划

**适用对象：** Claude Code（CLI 兄弟实例）  
**对接：** Cowork Claude（跑在 Cowork 模式下，专攻"理解深度"线程）  
**项目根：** `/Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench`  
**目标分支：** `feature/proactive-capability`（新建）  
**起草日期：** 2026-05-12

---

## 0. 背景与目标（必读 30 秒）

益语智库自用平台 V2.0 是一个 Electron + Python 桌面应用，正在做"客户计算中心"
深度优化。两条优化线程并行：

| 线程 | 责任人 | 分支 | 板块 |
|---|---|---|---|
| 理解深度 | Cowork Claude | `feature/understanding-depth` | 实体/关系/事实/矛盾/术语 |
| **主动能力** | **你（Claude Code）** | **`feature/proactive-capability`**（新建） | **调度器/通知/事件总线/周期摘要/风险扫描** |

**你的板块完成度从 15% → 50%（一期 3 个月）→ 80%（二期 6 个月）。**

详细板块设计见姊妹文档：
- `docs/主动能力-优化方案-2026-05-12.md`（9 个子能力 + 现状审计）
- `docs/数据中心-未完成清单-2026-05-12.md`（全局未完成项）
- `docs/客户计算中心-差距清单-2026-05-12.md`（架构审计）
- `docs/客户计算中心-功能差距清单-2026-05-12.md`（功能审计）

---

## 1. 工作模式

### 1.1 六步迭代（每个迭代严格走完）

```
①  目标锁定（量化验收 + UI 验证场景）
②  方案确认（停下来给用户决策，等他回应）
③  实现
④a 代码验证（pytest 全过 + 回归无新红）
④b UI 验证（重启 dev app + 真实操作 + 截图对比）
⑤  集成与提交（commit + 更新进度文档 + checkpoint）
```

**强制规则：**
- 没量化验收 → 不进入 ②
- 没用户确认方案 → 不进入 ③
- ④a 或 ④b 失败 → 回 ③，不强行进 ⑤
- 每个迭代末 **必须 checkpoint**——给用户一份简报（含 diff、测试结果、UI 截图描述、风险），等他回应再开下一迭代

### 1.2 何时主动推进 vs 何时停下来等用户

| 情形 | 处理 |
|---|---|
| 字段命名、测试用例细节、集成点写法 | 主动决定，不打扰 |
| 简单 schema 调整（加字段）、内部重构 | 主动决定 |
| **架构选型**（如 APScheduler vs Celery、单进程 vs 多进程） | **停，问用户** |
| **业务规则**（如周报推送时间、风险扫描频率） | **停，问用户** |
| **新增依赖**（pyproject.toml） | **停，问用户** |
| **影响打包流程或 dev/packaged 兼容** | **停，问用户** |
| 与"理解深度"线程的潜在冲突 | **停，问用户**或与 Cowork 协调 |

### 1.3 与 Cowork（理解深度线程）的协调

**潜在冲突点（提前注意）：**

1. **`backend/app/main.py` 的 `@app.on_event("startup")` 区（约 line 2847）**——两条线程都要加启动 worker。
   - **协调办法：** 第一次动这里时，**你新建** `backend/app/startup_hooks.py`，把启动逻辑统一放进去；main.py 里只保留 `from app.startup_hooks import register_startup_hooks; register_startup_hooks(app, state)`。Cowork 之后动启动区时会用同一套机制。
   - 如果发现 Cowork 已经动过 startup 区，先 git pull / git log 看下，按既有 pattern 加。

2. **`backend/app/db.py`**——两条线程都加表。
   - **协调办法：** 严格只加 `CREATE TABLE IF NOT EXISTS`，加在文件末尾，不动现有表。

3. **`backend/app/models.py`**——两条线程都加 Pydantic 模型。
   - **协调办法：** 同上，只加不动。

4. **运维面板 `src/renderer/components/data_center/DataCenterOpsPanel.tsx`**——两条线程都加 tab。
   - **协调办法：** 各加独立 tab，文案标注清楚。

**冲突探测脚本（每次开工前跑）：**

```bash
cd /Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench
git fetch origin
git log --oneline feature/understanding-depth..HEAD 2>/dev/null | head -10  # Cowork 那条分支最近 commit
git diff feature/understanding-depth..feature/proactive-capability --stat 2>/dev/null | head -10
```

如果发现 Cowork 改了你即将动的文件，先 `git diff` 看一下，按需 rebase 或在不同地方加。

### 1.4 UI 验证的具体做法

应用名：**益语智库自用平台 V2.0（开发版）**（bundle id: `com.yiyu.selfworkbench2.dev`）  
副屏：F34G4Q  
依赖：**Task #28（Cowork 委托的"自主重启机制"）必须先完成**——否则你也得每次手工重启 dev app

**每个迭代必走的 UI 验证三件套：**

1. **Before 截图**——动手前抓取相关界面
2. **改完后重启 Python backend**（用 Task #28 提供的菜单项 / Cmd+Shift+B / 自动 watcher）
3. **After 截图 + 实际操作**——按目标锁定时定义的"UI 验证场景"实际操作；对比 before/after

### 1.5 风险止损

遇到以下情况**立即停**，回 checkpoint 找用户：

- 范围漂移超过预估 30%
- 现有测试大面积红（> 5 个）
- 数据库不可逆改动（DROP、删字段、迁移可能丢数据）
- 与理解深度线程发现严重冲突
- 新增依赖装不上 / 与现有不兼容
- 单迭代 ③ 步工具调用 > 50 次仍未完成

---

## 2. 全局序列与依赖图

```
迭代 A0 准备工作（依赖审计、APScheduler 选型、与 Cowork 协调）
   ↓
迭代 A1 调度器基础设施 ★ 必先做
   ↓
迭代 A2 通知中心     ★ 必先做
   ↓
迭代 A3 事件总线统一
   ├─→ 迭代 A4 周期摘要（依赖 A1+A2）
   ├─→ 迭代 A5 新资料触发洞察（依赖 A3）
   ↓
迭代 A6 风险扫描（依赖 A1+A2，且依赖理解深度迭代 5/6 才完整）
   ↓
迭代 A7 跟进提醒 + 指标变化告警
```

### 关键合流点（与理解深度）

**理解深度迭代 6（矛盾检测）+ 主动能力 A2（通知中心）+ A3（事件总线）合流：**

矛盾 detected → 通过 event_bus.publish('contradiction.detected', ...) → 订阅者投递通知 → 用户在通知中心看到

如果你做到 A3 时 Cowork 还没做完矛盾检测，先准备好订阅 schema，到时候 Cowork
那边一上线就能挂上。

---

## 3. 七个迭代的详细计划

---

### 迭代 A0 · 准备工作

**目标：** 建立基线、新分支、进度文档，确认与 Cowork 不打架。

**量化验收：**
- [ ] 新建分支 `feature/proactive-capability`，起点为 `feature/understanding-depth` 最新 commit（不是 main，避免合并地狱）
- [ ] 跑后端测试基线：`cd backend && uv run pytest tests/ --tb=no -q 2>&1 | tail -5`，记录 baseline
- [ ] 跑 grep 确认现状：调度器/通知/事件总线全是 0（应该跟 Cowork 审计结果一致）
- [ ] 阅读 `docs/主动能力-优化方案-2026-05-12.md` 全文
- [ ] 阅读 `src/main/main.ts` 里 Python 子进程管理那段（约 5KB）
- [ ] 新建 `docs/proactive-capability-progress.md` 跟踪进度
- [ ] 确认 Task #28（dev app 自主重启机制）已完成；如未完成，先做完它再开主动能力

**预算：** 15-20 工具调用

**checkpoint：** 把基线测试结果、Task #28 状态、与 Cowork 分支的关系告诉用户，等他确认进 A1

---

### 迭代 A1 · 调度器基础设施

**一句话目标：** 接入 APScheduler，建立可定义/可触发/可观测的定时任务系统。

**量化验收：**
1. [ ] `backend/pyproject.toml` 新增 `apscheduler>=3.10`，运行 `uv sync` 装好
2. [ ] 新建 `backend/app/services/scheduler.py`：
   - 单例 `BackgroundScheduler`
   - `start()` 在 app 启动时调用，`shutdown()` 在退出时调用
   - 提供 `register_task(name, func, cron_expr)` 公共 API
3. [ ] 新建 `scheduled_tasks` 表（db.py 末尾 `CREATE TABLE IF NOT EXISTS`）：
   ```sql
   CREATE TABLE IF NOT EXISTS scheduled_tasks (
       id TEXT PRIMARY KEY,
       task_name TEXT NOT NULL UNIQUE,
       cron_expr TEXT NOT NULL,
       status TEXT NOT NULL DEFAULT 'enabled',  -- enabled|disabled|errored
       last_run_at TEXT,
       next_run_at TEXT,
       last_error TEXT,
       run_count INTEGER NOT NULL DEFAULT 0,
       created_at TEXT NOT NULL,
       updated_at TEXT NOT NULL
   );
   CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_status ON scheduled_tasks(status);
   ```
4. [ ] 新建 `scheduled_task_runs` 表：
   ```sql
   CREATE TABLE IF NOT EXISTS scheduled_task_runs (
       id TEXT PRIMARY KEY,
       task_id TEXT NOT NULL REFERENCES scheduled_tasks(id),
       started_at TEXT NOT NULL,
       finished_at TEXT,
       status TEXT NOT NULL,  -- running|success|failed
       error_message TEXT,
       duration_ms INTEGER
   );
   CREATE INDEX IF NOT EXISTS idx_task_runs_task ON scheduled_task_runs(task_id, started_at DESC);
   ```
5. [ ] 把启动逻辑统一到新建的 `backend/app/startup_hooks.py`（见 1.3 协调办法）
6. [ ] 注册一个 **demo task**："每 5 分钟 echo 'hello' 到 logger"，证明链路通
7. [ ] 新增 API：
   - `GET /api/v1/dev/scheduled-tasks` 列任务
   - `POST /api/v1/dev/scheduled-tasks/{id}/trigger` 手动跑
   - `POST /api/v1/dev/scheduled-tasks/{id}/disable` 暂停
   - `POST /api/v1/dev/scheduled-tasks/{id}/enable` 恢复
8. [ ] 至少 6 个 pytest 测试
9. [ ] 现有测试 0 个新红
10. [ ] UI 验证场景：见下

**UI 验证场景：**

1. dev app 重启
2. 通过 DevTools console 或 curl `http://127.0.0.1:<dev port>/api/v1/dev/scheduled-tasks` 看返回里有 demo task
3. 等 5 分钟（或调成 30 秒方便测试），看后端日志里有 "hello" 输出
4. POST trigger 接口手动跑一次，看 `scheduled_task_runs` 里多一条记录

**预算：** 35-50 工具调用

**checkpoint：** commit + 跑回归 + UI 截图描述 + checkpoint，等用户进 A2

---

### 迭代 A2 · 通知中心

**一句话目标：** 系统能告诉用户"有事发生"——站内 + Mac 通知。

**量化验收：**
1. [ ] 新建 `notifications` 表：
   ```sql
   CREATE TABLE IF NOT EXISTS notifications (
       id TEXT PRIMARY KEY,
       user_id TEXT,
       type TEXT NOT NULL,
       severity TEXT NOT NULL DEFAULT 'info',  -- info|warning|critical
       title TEXT NOT NULL,
       body_md TEXT,
       source_event_id TEXT,
       client_id TEXT,
       actions_json TEXT,  -- 可点击动作 [{label, url|event}]
       read_at TEXT,
       dismissed_at TEXT,
       created_at TEXT NOT NULL
   );
   CREATE INDEX IF NOT EXISTS idx_notifications_user_unread
       ON notifications(user_id, created_at DESC) WHERE read_at IS NULL;
   ```
2. [ ] 新建 `notification_delivery_log` 表：跟踪每个 channel 投递状态（in_app / mac_native / email）
3. [ ] 新建 `backend/app/services/notifications.py`：
   - `emit(user_id, type, *, severity, title, body, ...)` 是公共 API
   - 写入 notifications 表
   - 按用户偏好分发到 channel（initial 至少做 in_app；Mac 通知可选）
4. [ ] in_app channel：写表后通过 IPC 给 renderer 推送（沿用现有 Electron IPC 模式）
5. [ ] Mac 通知 channel：`subprocess.run(['osascript', '-e', f'display notification "{body}" with title "{title}"'])`，仅 dev/macOS
6. [ ] Renderer 新增"消息中心"图标 + 红点 + 弹层（在 App.tsx 顶栏；如果太大，可以做最小版：右上角加一个铃铛 + 数字红点）
7. [ ] 新增 API：
   - `GET /api/v1/notifications?unread_only=true` 列未读
   - `POST /api/v1/notifications/{id}/read` 标已读
   - `POST /api/v1/notifications/{id}/dismiss`
8. [ ] 至少 8 个 pytest 测试
9. [ ] 现有测试 0 个新红
10. [ ] UI 验证场景：见下

**UI 验证场景：**

1. 重启 dev app
2. 调 backend API：`POST /api/v1/notifications` 模拟一条通知（或在 backend 写一个 dev-only endpoint）
3. UI 顶栏铃铛应出现红点
4. 点开看到通知详情
5. Mac 通知中心应同时弹出（首次需在系统设置→通知里允许 Electron 应用通知）
6. 点"标已读"后红点消失

**预算：** 40-55 工具调用

**checkpoint：** 同上

---

### 迭代 A3 · 事件总线统一

**一句话目标：** 把现有 `data_center_ingest_events` + `data_center_sync_outbox` 统一为通用 pub/sub。

**量化验收：**
1. [ ] 新建 `event_bus` 表：
   ```sql
   CREATE TABLE IF NOT EXISTS event_bus (
       event_id TEXT PRIMARY KEY,
       event_type TEXT NOT NULL,  -- e.g. ingest.document.created, contradiction.detected
       payload_json TEXT NOT NULL,
       source_service TEXT,
       client_id TEXT,
       created_at TEXT NOT NULL,
       processed_at TEXT
   );
   CREATE INDEX IF NOT EXISTS idx_event_bus_type_unprocessed
       ON event_bus(event_type, created_at) WHERE processed_at IS NULL;
   ```
2. [ ] 新建 `event_subscriptions` 表（subscriber 注册）
3. [ ] 新建 `backend/app/services/event_bus.py`：
   - `publish(event_type, payload, *, client_id=None)` —— 写表
   - `subscribe(pattern, handler)` 装饰器 —— 注册订阅
   - 启动 worker `event_bus_worker_loop`（参考现有 knowledge_worker_loop pattern）
4. [ ] 已有 `data_center_ingest` 的事件写入升级为通过 event_bus.publish 发布 `ingest.document.created` / `ingest.task.created` 等事件
5. [ ] Demo subscriber：监听 `ingest.*`，写一条 logger 输出
6. [ ] 至少 6 个 pytest 测试
7. [ ] **现有的 data_center_ingest_events / data_center_sync_outbox 表保留**（不动），新表并行存在；后续慢慢迁移
8. [ ] UI 验证：触发一次资料导入，看 event_bus 表里多一条事件 + logger 输出

**预算：** 35-50 工具调用

---

### 迭代 A4 · 周期摘要

**依赖：** A1 + A2

**一句话目标：** 每周一早上 9:00 自动给每个客户生成一份摘要，推送通知。

**量化验收：**
1. [ ] 新建 `digest_runs` 表
2. [ ] 新建 `backend/app/services/periodic_digest.py`：
   - `generate_weekly_digest(client_id)`：基于最近 7 天的任务/会议/资料/事件线，调 `AiService` 现有 LLM 接口生成 markdown 结构化摘要
3. [ ] 在 A1 调度器里注册任务：每周一 9:00 跑（dev 可配 cron `*/10 * * * *` 每 10 分钟跑方便测试）
4. [ ] 摘要生成后调 A2 notifications.emit 投递通知，actions_json 包含跳转到 digest 详情页的链接
5. [ ] 新增 API：`GET /api/v1/clients/{id}/digests?period=weekly`
6. [ ] Renderer 新增 digest 详情页（最小版：markdown 渲染即可）
7. [ ] 至少 4 个测试
8. [ ] UI 验证：手动 trigger 周报生成（用 A1 的 trigger 接口）→ 通知中心收到 → 点击进 digest 页

**预算：** 30-40 工具调用

---

### 迭代 A5 · 新资料触发洞察

**依赖：** A3

**一句话目标：** 资料一来，AI 主动评估"这是不是有趣的、要立即提醒？"

**量化验收：**
1. [ ] 在 event_bus 订阅 `ingest.document.created`
2. [ ] 处理器：用 `AiService` 评估资料的"新颖性 / 紧迫性 / 与客户战略相关性"，返回 0-1 分数 + 简短理由
3. [ ] 分数 ≥ 0.7 → 调 notifications.emit 投递 severity=warning 的通知
4. [ ] 分数 ≥ 0.9 → severity=critical
5. [ ] 至少 4 个测试（mock LLM 输出）
6. [ ] UI 验证：导入一份明显有价值的资料（含客户关键词、战略相关），看通知中心是否弹出"建议关注"

**预算：** 25-35 工具调用

---

### 迭代 A6 · 风险扫描

**依赖：** A1 + A2，且**最好等理解深度迭代 5/6 完成**（关系 + 矛盾）才完整

**一句话目标：** 每天/每周扫一遍全部客户的资料，发现资料过期、缺口、矛盾，主动告警。

**量化验收：**
1. [ ] 新建 `risk_scan_runs` 表
2. [ ] 注册定时任务：每天凌晨 4:00 跑（dev 可配每小时）
3. [ ] 扫描维度（最小集）：
   - 资料过期：所有客户的 documents，鲜度 < 0.3 且 marked as critical 的资料
   - context_pack 缺口：调现有 `digital_asset_center` 的 gap 检测
   - （如理解深度迭代 6 已上线）未 dismiss 的矛盾
4. [ ] 发现风险 → notifications.emit 严重度分级
5. [ ] 运维面板加"风险扫描"页签：列最近扫描结果、手动 trigger
6. [ ] 至少 5 个测试
7. [ ] UI 验证：手动 trigger 风险扫描 → 通知中心看到 N 条告警 → 运维面板看历史

**预算：** 35-45 工具调用

---

### 迭代 A7 · 跟进提醒 + 指标变化告警

**依赖：** A1 + A2 + A3

**一句话目标：** "你 3 周前问的 X，现在有新资料" + "客户 A 的 KPI 跌了 20%"。

**量化验收：**

跟进提醒部分：
1. [ ] 新建 `followup_topics` 表：记录"用户问过但回答不完整 / 未结案"的话题
2. [ ] 订阅 chat 完成事件，对低置信度回答自动生成 followup_topic
3. [ ] 定时任务：每周扫 followup_topics，看是否有新资料覆盖该话题
4. [ ] 有新资料 → 投递通知

指标变化告警部分：
5. [ ] 新建 `metric_snapshots` 表：定期捕获每个客户的关键指标（任务数/会议频次/资料更新速度/未解决矛盾数等）
6. [ ] 定时任务：每周生成 snapshot
7. [ ] 对比上周 snapshot，> 20% 变化 → 投递通知

8. [ ] 至少 5 个测试
9. [ ] UI 验证：人为构造一个 metric 变化场景，看通知是否触发

**预算：** 35-45 工具调用

---

## 4. 数据库迁移规范

- **只加不删**：新表 `CREATE TABLE IF NOT EXISTS`，新字段 `ALTER TABLE ... ADD COLUMN`
- **不改类型**：现有字段类型不动
- **幂等性**：所有 migration 重复跑不报错
- 新表统一加在 `db.py` 末尾，加 `# === 主动能力线程新增 ===` 注释区方便后人识别

---

## 5. 进度跟踪

每个迭代结束后更新 `docs/proactive-capability-progress.md`：

```markdown
## 迭代 A<N> · <名称>

**完成日期：** <date>  
**commit：** <hash>

### 改动文件清单
| 文件 | 改动类型 | 说明 |
|---|---|---|

### 测试结果
- 新增测试：N 个，全过
- 回归测试：M passed, K failed（同 baseline）

### UI 验证
- before：（截图描述或文件名）
- after：（截图描述或文件名）

### 已知缺口
| ID | 缺口 | 下一迭代覆盖 |
|---|---|---|

### checkpoint 节点
- ✅ 已 checkpoint：...
```

---

## 6. 提交规范

每个迭代分至少 2 个 commit：

```
feat(proactive/A<N>): 数据模型与服务
feat(proactive/A<N>): 集成与测试 + UI
```

如有第三个：

```
feat(proactive/A<N>): UI 入口
```

---

## 7. 第一步动作

1. **检查 Task #28 状态**——问用户：dev app 自主重启机制 (Task #28) 已经完成了吗？
   - 如果还没完成，先把它做完（详见 `docs/understanding-depth-progress.md` 中 Task #28 部分）
   - 如果完成了，继续下一步

2. **进入迭代 A0 ① 步：目标锁定**
   - 跑现状审计脚本（grep 调度器/通知/事件总线相关代码）
   - 跑测试基线
   - 把结果汇报给用户，确认能进 A1

3. **不要直接开始 A1 实现**——等用户回应再进 ② 方案确认 → ③ 实现

---

## 8. 失败和兜底

| 失败 | 处理 |
|---|---|
| 测试装不上 | 报告并暂停，问用户是否升级 Python / 调整环境 |
| dev app 起不来 | 报告日志，问用户是不是 Task #28 没做完 |
| 与理解深度分支冲突 | 报告冲突文件，问用户怎么 rebase |
| 单迭代超出预算 50 次工具调用 | 强制 checkpoint，让用户决定缩范围或继续 |
| 关键决策不确定 | 不要硬猜，停下来问 |

---

## 9. 沟通规范

- 每次 checkpoint 用结构化 markdown：
  - **状态总览表**（哪些 ✅ 哪些 ⏳）
  - **diff 摘要**
  - **测试结果数字**
  - **UI 验证截图描述**
  - **下一步建议**
- 用户回应后再行动
- 任何"我猜应该这样"的判断 → 改成"我建议这样，请确认"

---

## 10. 关键引用

- 本方案：`docs/主动能力-Claude-Code执行计划-2026-05-12.md`（本文）
- 板块设计：`docs/主动能力-优化方案-2026-05-12.md`
- 全局未完成：`docs/数据中心-未完成清单-2026-05-12.md`
- 架构审计：`docs/客户计算中心-差距清单-2026-05-12.md`
- 功能审计：`docs/客户计算中心-功能差距清单-2026-05-12.md`
- 理解深度执行计划（参考兄弟线程）：`docs/理解深度-执行计划-2026-05-12.md`
- 理解深度进度（看 Cowork 那边在做什么）：`docs/understanding-depth-progress.md`

完。
