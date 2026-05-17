# 战略陪伴 · 澄清面板叙事架构 spec

**作者**: Claude (在顾源源指导下 / 2026-05-16)
**版本**: v0.1
**位置**: 战略陪伴 → 「事实澄清」Tab (替换原"矛盾 & 待确认")
**前置文档**: `DATA-CENTER-RELATIONSHIP-GRAPH-PLAN.md` v0.3 / `PHASE-0-FUNCTION-DRIVEN-REVERSE-PLAN.md`
**长期记忆**: `submodule:strategic_clarification_panel` + 本次新增 `principle:user_perspective_anchor`

---

## 0. 北极星 (顾源源 5/16 原话定位)

> "**它是可以看到整个故事** (故事它的展示形有哪些关键人, 这些关键人的角色是做什么的, 然后这是一件什么事情, 然后当中有哪些承诺)。其次, 有一些问题需要向用户澄清, **用户用语音或者打字跟你澄清这些内容之后, AI 就会更新它的织起来的这张故事网**, 澄清得越清晰, **整个组织对这个业务的理解深度或者广度也会越清晰**。它是所有就是对于这个项目有关的人**共同编织的**。"

> "凡是跟这一个项目有关的人都会关联到这个澄清面板。"

→ 用户价值 (北极星): **用户/组织通过看 AI 怎么讲这个项目的故事, 判断 AI 是否已经全面理解了这个业务; 看到不清楚的地方就澄清, 澄清后 AI 更新故事网, 越澄清整个组织对业务的理解越深。**

→ 反 pattern: 把 db row 平铺给用户当"澄清"面板。这只是数据展示, 不是叙事, 用户没法判断 AI 是否真懂。

→ 服从 `principle:user_judgment_pace`: 必须出 UI 才能判断, 但 UI 必须呈现"AI 叙事"而不是"db dump"。

→ 服从 `principle:formula_filter`: 频次 (战略陪伴 Tab 每日打开) × 价值感知 (强 — 决定 AI 输出能否信任) = 25 / 25。

---

## 1. 叙事架构 · 6 大维度

不是 5 区块 db 字段, 是 **6 大叙事维度**, 每一维度 AI 用自然语言讲一段, 都是"AI 自己讲的故事"。

| # | 维度 | AI 叙事段落写什么 | 用户能判断什么 |
|---|---|---|---|
| **1** | **项目本质 · 这是什么事情** | 客户是谁 / 体量 / 来找益语做什么 / 项目类型 (培训/咨询/落地/续约/方案) / 客户对成功的定义 / 边界 / 当前阶段 | "AI 你说的这家客户是不是这个"; "项目目标错了" |
| **2** | **关键人物网 · 谁是谁** | 客户方关键人物 (姓名+职务+角色: 决策/sponsor/经办/反对/中立) + 益语方分工 + 人物间关系 (谁信任谁/谁影响谁) | "张真不是经办, 是秘书长"; "李四是反对者, 不是中立" |
| **3** | **来龙去脉 · 怎么走到现在** | 项目怎么起来 (引荐/老客复购/RFP) + 关键节点 (合同/启动会/关键交付/转折事件) + 现在哪一步 | "AI 你漏了 4 月那次重要的吃饭"; "顺序搞反了" |
| **4** | **承诺网 · 在路上的事** | 益语 → 客户承诺 (做什么/deadline/履约状态) + 客户 → 益语承诺 (付款/配合/资源) + 风险高的承诺 | "这条承诺 deadline 错了"; "客户那个承诺其实早就口头取消了" |
| **5** | **卡点与风险 · 警惕信号** | 当前阻塞 (业务/人/决策) + 已知风险 + AI 觉得需要警惕的信号 (人物变动/客户冷却/竞品介入) | "这个不是风险, 客户口头说没事了"; "你漏了一个大风险" |
| **6** | **下一步 · 接下来去哪** | 1-2 周关键事 + 由谁负责 + 衡量进展的标志 + AI 推荐的下一步动作 | "AI 你推荐的方向不对, 应该先做 X" |

(维度 7 · 横向参考 · 跟同类客户/这家其他单子对照 → 留 Phase 2, 现在做不到。)

---

## 2. 每段叙事的统一结构 (强约束)

每个维度的"故事段落"必须包含:

```
┌─ AI 叙事 (200-500 字自然语言) ─────────────────────────────┐
│ 这家客户来找益语做的不是一次性培训, 而是 6 个月组织诊断 +  │
│ 干部培训综合方案。客户最看重的是"看到我们干部到底差在哪",  │
│ 而不是培训本身, 益语团队由老高主导 (✅高), 但老高 5 月底  │
│ 离职后交接给王强 (⚠️中, 仅基于一次 4/28 周会提及)...      │
└────────────────────────────────────────────────────────────┘
  ↓ 折叠区: AI 引用源 (展开看)
  [✅ document #1432: 2026-04-12 日慈秘书长见面纪要]
  [✅ event_line #38: 老高离职公告 5/29]
  [⚠️ chat #1192: 4/28 周会 — 仅一次提及王强]

  ↓ AI 把握度
  [✅高 4 段 · ⚠️中 2 段 · ❌低 1 段 (人物角色)]

  ↓ AI 想跟用户澄清的问题 (针对低把握度自动生成)
  > "王强是正式接手老高的工作吗? 还是临时代管?"
  [语音 / 打字回答 →] 提交后 AI 重新生成这段, 并标记[您 5/16 澄清]

  ↓ 这段被谁澄清过 (共同编织)
  [顾源源 5/15 · 王 5/16 (王强角色) · 老李 5/16 (项目阶段)]
```

→ 5 个统一元素: **叙事文本 / 引用源 / 把握度 / 澄清入口 / 贡献者**

---

## 3. 服从约束 · 5 项硬铁律

**铁律 1 (真实数据)** — `submodule:strategic_clarification_panel.decision`: "**必须去想它是真实数据作为支撑的, 不能乱编**"。
→ 每段叙事的每个事实/判断都必须能追到 db row (引用源); AI 不能凭空生成, 只能"加工"db 里已有的事实。

**铁律 2 (用户视角判断价值)** — `principle:user_perspective_anchor`: 用户视角判断价值, 不要让用户当 PM。
→ 叙事的语言、详略、维度选择都从"用户读了能不能 1 分钟内判断 AI 是否真懂"出发, 不从"数据库里有什么"出发。

**铁律 3 (六个轮子才上路, 不要三个轮子跑车)** — `principle:formula_filter` (≥12 才硬交付):
→ 6 大维度必须全部有最小叙事, 不能"先上 3 个我知道的", 因为读者一眼看不出整体故事网。
→ 缺数据的维度也要有"AI 暂时讲不出, 因为 [具体原因]"的诚实段落, 不能跳过。

**铁律 4 (组织共编)** — 5/16 原话 "**共同编织**":
→ 叙事生成 + 澄清记录全部上云端, 同组织有权限的账号 (A/B 都跟日慈关联) 看到的是同一份故事。
→ 任何人澄清都让 AI 更新故事, 后来人看到"AI v3 (王 5/16 修订)"。
→ 权限: admin/leader 看所有客户; employee 看自己 task/客户工作台关联的客户。

**铁律 5 (引用可钻取)** — `module:data_center.architecture` 第 5 项 "**血缘 + 置信度**":
→ AI 说的每句话都能点开看到引用源 (document / chat / event / action / fact)。
→ 用户能直接打开原文件确认 AI 是不是从这个文件得出这个结论 — 实现"直接打开软件让客户确认是不是这个文件讲的东西" (`submodule:strategic_clarification_panel.purpose`)。

---

## 4. 数据中心加工层 · 诚实缺口清单

**用户原话 (5/16)**: "在搜索的过程当中, 再去排查数据中心有没有加工他所拿到的, 没有加工他从日程复盘当中拿到的文件。之前讲到, 数据中心平时要有一个去确认重点信息, 类似像这个用户字典这样的, 他要把这些关键的信息串成一张网, 要让这一张网在这一个功能界面上发挥作用。"

诚实评估: 6 维度叙事现在能讲到哪一步? 哪些靠"db 里加工过的关键信息"才能讲好?

| 叙事维度 | 需要的加工层 | 数据中心当前状态 | 当前能讲多少 |
|---|---|---|---|
| 1 · 项目本质 | `client_strategic_profile` + 新字段 `project_type` / `project_goal` / `success_metric` / `current_phase` | ⚠️ profile 表存在但 60% 字段空; project_type 等字段尚未建 | 50% (能讲客户名 + 行业, 讲不清项目类型/目标) |
| 2 · 人物网 | `external_persons` 花名册 (姓名+别名+职务+在某客户/项目里的角色) | ❌ **关键缺失** — 当前只能从 `owner_name` / `actor_name` 粗糙提取名字 | 20% (只能列名字, 讲不出角色) |
| 3 · 来龙去脉 | `event_lines` 升级 (thread_level: project/phase/commitment/single_touch/mechanism) + `event_line_activities` 业务语义标注 | ⚠️ event_lines 41 颗粒度混乱; activities 70 条原始没分级 | 40% (能讲流水账, 讲不出"哪几个是关键转折") |
| 4 · 承诺网 | `event_lines` 升级为承诺级 thread + `action_items` 业务化 + 履约状态计算 | ⚠️ action_items 136 但稀疏; 没区分"承诺"vs"task" | 30% (能列 actions, 讲不清"谁向谁承诺什么/履约风险") |
| 5 · 卡点与风险 | `evidence_cards.polarity` 多元化 (现全 neutral) + 新建 `risk_signals` 表 (人物变动 / 承诺逾期 / 客户冷却信号) | ❌ **大缺口** — evidence_cards 168 但 polarity 全 neutral; judgment_versions 21 全 candidate; risk_signals 不存在 | 10% (基本讲不出风险, 只能说"无") |
| 6 · 下一步 | `tasks` (136) + plan 上下文 + AI 推测的"下一步关键动作" | ⚠️ task 有但没业务化; "AI 推荐下一步"逻辑不存在 | 25% (能列 7 天内 task, 讲不清"这背后是哪条主线的下一步") |

**总体**: 叙事 v0.1 整体可讲度 ~30%。所以**第一版叙事面板必须明示这一点** — 把 ⚠️/❌ 段落直接标记 "AI 暂时讲不出, 因为数据中心还没建 [花名册 / 风险信号表 / 主线颗粒度]"。这本身就是"让用户看到 AI 哪里没懂"的最诚实形式。

**优先补的 5 个加工层 (Task #61)**:
1. **`external_persons` 花名册** (Phase 1 基础设施 / DNA module:data_center.decision 已规划)
2. **`event_lines` 9 字段升级** (Phase 1 基础设施 / 已规划)
3. **`evidence_cards.polarity` 重打标** (业务语义化 → 跑 LLM 批量重判)
4. **`client_strategic_profile` 补字段** (`project_type`, `project_goal`, `success_metric`, `current_phase`)
5. **`risk_signals` 表新建** (AI 巡检产物 + 用户标注)

---

## 5. 云端共享架构 (顾源源 5/16 明确指示)

> "判断应该是放在云端的, 因为这些判断它是这一个组织所有账号有权限的账号, 它需要共享。A 账号和 B 账号都跟日慈基金会关联, 那么这两个账号应该都可以去澄清, 以及看到澄清的所有的东西。"

### 5.1 新建云端表

```sql
-- 叙事最新版本 (每个客户一行最新, 历史进 revisions)
CREATE TABLE client_narrative_versions (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL,
  rev INTEGER NOT NULL,         -- 1, 2, 3... 每次澄清 +1
  generated_at TEXT NOT NULL,
  generator TEXT NOT NULL,      -- 'ai' / 'human_edit' / 'merge'
  -- 6 段叙事 (每段含文本 + 引用 + 把握度)
  dim_essence_json TEXT,        -- 维度 1 项目本质
  dim_people_json TEXT,         -- 维度 2 人物网
  dim_history_json TEXT,        -- 维度 3 来龙去脉
  dim_commitments_json TEXT,    -- 维度 4 承诺网
  dim_risks_json TEXT,          -- 维度 5 卡点风险
  dim_next_json TEXT,           -- 维度 6 下一步
  overall_confidence REAL,      -- AI 整体把握度
  open_clarifications_count INTEGER,
  data_layer_gaps_json TEXT,    -- 当时数据中心缺失的加工层 (诚实标记)
  created_at TEXT, updated_at TEXT
);

-- 澄清记录 (谁问 / 谁答 / 哪段 / 内容) - 共同编织的核心
CREATE TABLE client_narrative_clarifications (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL,
  narrative_rev INTEGER NOT NULL,     -- 基于哪一版叙事
  dimension TEXT NOT NULL,            -- essence / people / history / commitments / risks / next
  question TEXT,                       -- AI 问的问题 (可为空, 用户主动补充)
  asked_by TEXT,                       -- 'ai' / user_id (用户主动质疑的情况)
  answer TEXT NOT NULL,                -- 用户答复 (语音转文本 + 打字)
  answered_by TEXT NOT NULL,           -- user_id
  answered_at TEXT NOT NULL,
  resulted_in_rev INTEGER,             -- 这次澄清生成了哪一版新叙事
  status TEXT NOT NULL DEFAULT 'pending'   -- pending / applied / discarded
);

-- 历史所有版本 (审计 + 还原)
CREATE TABLE client_narrative_revisions (
  client_id TEXT, rev INTEGER, snapshot_json TEXT, created_at TEXT,
  PRIMARY KEY (client_id, rev)
);
```

### 5.2 权限 (跟客户工作台关联收敛)

- **admin / leader** → 所有客户的叙事
- **employee** → 只看 (自己 task.related_client + 客户工作台关联) 的客户
- **看到 = 能澄清** (这是 5/16 原话 "凡是跟这一个项目有关的人都会关联到这个澄清面板")

### 5.3 流程

```
用户 A 打开战略陪伴 → 选客户日慈
  ↓
本地拉云端 /api/v1/clients/{id}/narrative (60s 缓存)
  ↓
渲染 6 维度叙事 + 每段 AI 把握度 + 澄清入口
  ↓
A 在维度 2 (人物网) 上语音补充: "张真是秘书长, 不是经办"
  ↓
本地上传 → 云端写 clarifications row → 触发 LLM 重生成
  ↓
LLM 用 (旧叙事 + 新澄清 + 数据中心 facts) 生成新 rev
  ↓
A/B/C 任何人下次打开都看到 "v3 (A 5/16 修订 · 王 5/16 修订)"
```

---

## 6. Phase 1.5c · 实施路径 (我自己定, 不问用户)

**本周内出 UI demo** (服从 `principle:user_judgment_pace`):

| 周内日 | 做什么 | 输出 |
|---|---|---|
| Day 1 (今天) | 本文档 + DNA 沉淀 + 任务跟踪 | spec 定 |
| Day 2 | 云端 schema migration (3 张新表) + backend service `client_narrative.py` | API 框架 |
| Day 3 | 写叙事生成 prompt (6 维度 / 引用源 / 把握度 / 数据缺口诚实标记) + 跑日慈/为爱前行/黔行 3 个客户的 v1 叙事 | LLM 输出真实例 |
| Day 4 | 替换 `StrategicClarificationView` 主体: 6 维度叙事在顶, 当前 5 区块 db dump 折叠到"AI 引用源"层 | UI 可点 |
| Day 5 | 用户 (顾源源) 看真实 UI 反馈 | 拿到方向校正 |

**并行 (Task #61)**: 数据中心加工层补齐 (花名册 / event_lines / evidence_cards 重打标) — 不等加工层补完就先出叙事 v0.1, 让"加工层缺口"暴露在 UI 上促使补齐。

---

## 7. 当前 mockup 的角色重定位

不删, 但改角色:

| 现状 | 改后 |
|---|---|
| `StrategicClarificationView` 5 区块是 **主视图** | 6 维度叙事是主视图 |
| 5 区块以"AI 当前状态 db dump"展示 | 5 区块降为"AI 引用源 · 字典层" (折叠在每段叙事下面) |
| `ClarificationQueue` 字段级缺失提示 | 替换为"业务级澄清问题" (来自 LLM 生成, 服从 Quality Score ≥80 — 见 DNA `submodule:strategic_clarification_panel.decision`) |
| `DataHygieneSection` 测试数据折叠 | 保留, 但跟"数据中心加工层缺口"区分开 |

---

## 8. 反 pattern 防御

(都已沉淀进 DNA `principle:user_perspective_anchor` 的 anti-pattern entry)

❌ 不要再做的事:
- 让用户帮我决定"叙事生成放本地还是云端" → 5/16 用户原话已定 = 云端
- 让用户帮我决定"先做哪个维度" → 6 维度同时上, 服从 formula_filter
- 让用户帮我判断"5 区块够不够" → 用户只能判断方向 (user_judgment_pace), 我做出叙事 UI 再让用户看
- 用 db row 平铺当"故事" → 必须叙事化 (5/16 原话 "看到整个故事")
- 假装数据中心已经完整加工 → 诚实在 UI 上暴露加工层缺口, 这本身就是"AI 没懂的部分"

---

## 9. 沉淀回 DNA 的清单

本文档关键决策追加到:
- `principle:user_perspective_anchor` (新建, 3 entries)
- `submodule:strategic_clarification_panel` (append: 叙事架构 / 加工层缺口 / 云端共享 / Phase 1.5c 路径)
- `module:data_center` (append: 加工层 5 项缺口清单)
- `software:root` (append: 战略陪伴叙事面板 = 数据中心北极星功能)
