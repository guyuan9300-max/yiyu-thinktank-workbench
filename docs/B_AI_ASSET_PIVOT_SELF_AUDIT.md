# B AI · iterate 1 资产盘点纠偏自检报告

> **对应**: A AI 5/22 sync 指令 (`docs/B_AI_SYNC_20260522_ASSET_PIVOT.md`)
> **执行**: 收到指令 → 完整读 inventory § 1/3/4/5/6 + 协作文档 §6 / §6.1 / §6.2 → 4 道自检
> **状态**: ★ 不动代码, 自检完毕, 等 A + 顾源源 review 后再 iterate
> **日期**: 2026-05-22

---

## 0 · 我读了什么 (按 §6.1 强制场景: 用户问"客观排查/重新评估" + session > 4h)

| 文档 | 关键章节 | 状态 |
|---|---|---|
| `docs/V2.2_DATA_ASSET_INVENTORY.md` (523 行) | §3 重大发现 5 条 / §4 8 段→现成表映射 / §5 atomic_facts 应该/不应该 / §6 5 条新原则 | ✅ 完整读 |
| `docs/V2.1_AI_COLLABORATION.md` (新增 §6.1/§6.2) | 7 步开局 / 强制重读 6 场景 / 提案前 4 道自检 | ✅ 完整读 |
| `docs/B_AI_SYNC_20260522_ASSET_PIVOT.md` (135 行) | sync 指令本体 | ✅ 完整读 |
| `git show 9dad38d` A v1 prompt 草稿 | 看 A v1 是否已绑现成表 | ✅ 确认 — A v1 还基于 atomic_facts 单源, 5/22 资产盘点之前写的 |

---

## 1 · iterate 1 五个 commit 在新设计视角下逐项自检

### 1.1 commit 07b5dd7 · backend/app/api/ 模块化 router + full-narrative endpoint shell

| 检查项 | 结果 |
|---|---|
| URL `/api/v1/clients/{id}/full-narrative` 跟现成 endpoint 冲突? | ❌ 不冲突, 现有 `digital-assets/narrative/refresh` 是单 markdown 字段, shape 不同 |
| FastAPI APIRouter + Depends 模式跟现有 closure endpoint 冲突? | ❌ 是新模式 (audit §EDGE 已 flag), 给 main.py 27000 行立模块化模板 |
| Idempotency-Key 复用 F2.8 store? | ✅ 复用, 不重复造轮子 |
| **endpoint 数据源跟 §4 现成表映射冲突?** | ⚠️ endpoint 本身跟数据源解耦 (调 kernel.generate), 但 **kernel v0 只读 atomic_facts**, 不读 §4 8 组现成表 — A 重设计 kernel 后我跟 |

**保留度**: 100% (endpoint shell 是 wrapper, contract 跟数据源解耦)

---

### 1.2 commit 90bf24f · full-narrative endpoint 8 集成测试

| 检查项 | 结果 |
|---|---|
| 测的是 endpoint 行为还是 kernel 数据源? | ✅ 测 endpoint (404 / Idempotency / acceptance / shape / 任意入口) |
| 测试用 fixture INSERT atomic_facts 是否还合理? | ⚠️ A kernel v0 数据源是 atomic_facts, 这是当前真实, 不算错; **A kernel v2 接现成表后** fixture 需要扩展 INSERT 到 risk_signals / open_questions / weekly_reviews 等 |

**保留度**: 95% (kernel 内核改后, 部分 fixture 需要扩 schema, test 主体不动)

---

### 1.3 commit 4b254c1 · 前端 hook + 共用组件 + StrategicClarification 接入

| 检查项 | 结果 |
|---|---|
| `fullNarrativeTypes.ts` `StorySection.cited_fact_ids` 字段 | ⚠️ 只有 fact_ids, 没有 `cited_record_ids` (跨现成表引用) — A 改 dataclass 后我跟 |
| `useClientFullNarrative` hook 跟现有 hook 冲突? | ❌ 不冲突, 套 `useClientFact` 模板 |
| `FullNarrativeSection` 组件跟现有组件冲突? | ❌ 不冲突, **但跟现有 `NarrativePanel` (6 维度, 旧 Plan A) 形成 2 套并行 UI** — kernel 重设计后需要收敛 (audit §EDGE.3 已 flag) |
| `StrategicClarificationView` 接入位置 | ✅ 在旧 6 维度顶部, 不替代不删除 |

**保留度**: 85% (citation 展示需要扩展跨表 id; 跟旧 NarrativePanel 收敛是 A 决策)

---

### 1.4 commit 5aa92d8 · baseline runner 扩展 6 待办 + 5 人物归一 + 综合 P%

🔴 **这一项是最大偏差点 — 跟新指令 §六 直接冲突**

新指令明确:
> "baseline P% 87% 这个数字基于 'NarrativeKernel 从 atomic_facts 一张表' 的旧设计,
>  新设计下 baseline 必须改成: 测 8 组现成表能直接答多少 / 7 道金标准,
>  不是测 atomic_facts 抽出来多少条"

| 检查项 | 结果 |
|---|---|
| baseline runner SQL 走哪张表? | 🔴 `FROM atomic_facts` × 2 处 (lines 269 + 294) — 单源 |
| 是否查 §4 映射的现成表? | 🔴 **0 查** — `risk_signals` (20) / `open_questions` (23) / `weekly_reviews` (9) / `commitments` (66) / `meetings` (7) / `decisions` (3) / `tasks` (238) / `event_lines` (16) / `entities` (4987) / `client_dna_documents` (32) 全没接 |
| 综合 P% 87% 反映的是什么? | 🔴 反映 atomic_facts 命中, **不是用户能看到的故事网命中** |

**保留度**: 30% (主结构 dataclass / CLI / 输出格式保留, probes 查询逻辑要重写)

**应该改成的设计 (待 A + 顾源源 review)**:
```
新 baseline runner 调用方式:
  baseline = run_v22_n2_baseline(client_id)
  ↓ 内部:
  narrative = NarrativeKernel.generate(client_id)   # 走新设计聚合现成表
  for probe in PROBES_5_19_TRUE_ALIGN:
      hit = probe 在 narrative.story_sections[任一段].body_markdown 中命中?
  for probe in PROBES_TODO_6:
      hit = probe 在 commitments / tasks 表中? OR 在 narrative 中?
  for probe in PROBES_PEOPLE_5:
      hit = probe 在 entities (type=person) 表中? OR 在 narrative 中?

→ 这才是真"业务侧 P%" — 测的是用户/AI 看故事网时能拿到多少
```

---

### 1.5 commit e05bb88 · MILESTONE FULL_NARRATIVE audit + PROGRESS

| 检查项 | 结果 |
|---|---|
| audit 里 87% 数字诚实吗? | ⚠️ **数字本身真实**(确实 7/7 弱 + 5/6 待办 + 3/5 人物), **但解读偏差**: 我把它解读为"业务侧 N2 突破", 实际只是"atomic_facts 单源命中" |
| audit §EDGE 是否 flag 关键债? | ✅ Flag 了 NarrativeKernel SECTION_KEYS 命名差异 + narrative_generator vs NarrativeKernel 收敛 + 前端 2/3 入口 — 但**没 flag** "8 段没用现成表" 这一根本债 |
| PROGRESS 追加内容是否需要纠正? | ⚠️ 需要追加纠偏说明, 不删除 (历史诚实) |

**保留度**: 100% (历史诚实记录, 后续追加纠偏补充)

---

## 2 · 对应 sync 指令 4 道自检题答案

### Q1: 我的 endpoint 拉的数据源是只读 atomic_facts? 还是聚合 §4 现成表?

**答**: endpoint 本身是 wrapper, 调 `kernel.generate()`. **当前 A v0 kernel 只读 atomic_facts**, 不读 §4 现成表 → **偏差存在, 但责任在 kernel 内核而非 endpoint shell**.

**B 这边没错的部分**: endpoint shell + 5 维 acceptance + Idempotency-Key + response shape 跟数据源解耦.
**B 这边需跟改的部分**: response shape 中 `StorySection.cited_fact_ids` 需扩展为 `cited_record_ids` (含 atomic_facts/risk_signals/open_questions 等跨表 id).

### Q2: 前端 view 渲染 8 段, 用户能看到现成表内容 (risk_signals 20 / open_questions 23) ?

**答**: 🔴 **看不到**. 因为 kernel v0 没拉现成表, 即便 `risk_signals` 表有 20 条数据, 用户在故事网 risks 段看到的是 atomic_facts.content_role='risk' (3 条), 不是 risk_signals 表的 20 条 .

**含义**: 现有用户已经手工填了 20 条 risk_signals, 但 v2.2 故事全景看不到 → 用户白填了.

### Q3: timeline 段是否在拉 activity_logs (26677 行) ?

**答**: 🔴 **没拉**. A v0 kernel `narrative_kernel.py:230`:
```python
elif section_key == "timeline":
    section_facts = [f for f in all_facts if f["time_anchor"]]
```
`all_facts` 来源是 atomic_facts 表, 跟 `activity_logs (26677)` 完全无关.

**含义**: 用户看到的 timeline 段是 atomic_facts 中带 time_anchor 的少数事实 (估计 < 100 条), 不是真主时间线 26677 条 activity_logs.

### Q4: 我做的事是不是跟"现成表 / 现成管道"重叠?

**答**:
- ✅ **不重叠** (保留): endpoint shell / hook / 共用组件 / Idempotency / acceptance / 测试 / audit / PROGRESS
- 🔴 **重叠 (重叠的是"测试维度" — 没用现成表只用 atomic_facts)**: baseline runner probes 查询逻辑

---

## 3 · 我上次评估 (1 小时前) 的纠错

### 误评估: "N2 业务数字综合 P% = 87%"

**实际**: 87% 是 atomic_facts 单源命中率, **不是用户/AI 看故事网时能拿到的内容覆盖率**.

**用资产清单事实重算 (粗估)**:

| 段 | 现成表数据 | 用户看故事网能否看到 (现状) |
|---|---|---|
| identity | client_dna_documents 32 + clients 12 | ❌ 看不到 (kernel 没拉) |
| people | entities 4987 + entity_mentions 12184 | ❌ 看不到 |
| main_lines | event_lines 16 + tasks 238 + commitments 66 | ❌ 看不到 |
| recent_changes | dna_deltas 13 + decisions 3 | ❌ 看不到 |
| risks | risk_signals 20 + fact_contradictions 81 | ❌ 看不到 |
| our_collab | weekly_reviews 9 + chat_threads 305 + meetings 7 | ❌ 看不到 |
| open_questions | open_questions 表 23 | ❌ 看不到 |
| timeline | activity_logs 26677 | ❌ 看不到 |

**真业务侧 N2 命中率**: 8 段里 0 段真用了现成表 = 0/8 = **0%**

**B 87% 数字撤回**, 真业务命中 0%. atomic_facts 命中 87% 只是 "kernel v0 在自己造的小池子里 87%", 跟用户看到的故事网无关.

---

## 4 · 哪些 commit 保留 / 改 / 重写 (待 A + 顾源源 review)

| commit | 保留度 | 动作 |
|---|---|---|
| 07b5dd7 backend router + endpoint shell | 100% | 保留, 等 kernel 重设计后扩展 cited_records 字段 |
| 90bf24f endpoint 8 测试 | 95% | 保留, fixture 等 kernel v2 接现成表后扩展 INSERT 多表 |
| 4b254c1 前端 hook + 组件 + 接入 | 85% | 保留, citation 展示扩展跨表 id |
| 5aa92d8 baseline runner 扩展 | 30% | 🔴 probes 查询逻辑重写 (走 NarrativeKernel 输出, 测 8 段命中, 不是 atomic_facts 命中) |
| e05bb88 audit + PROGRESS | 100% | 保留 + 追加本自检纠偏 |

**0 个 commit 需要 revert**. baseline runner 改动是"扩展逻辑"不是"撤回 commit".

---

## 5 · 我承认的设计偏差 (诚实)

1. ✅ **没违反 §6.2 自检** — 我没有"建表 / 新管道", endpoint shell / 前端 hook / 组件不是新表
2. 🔴 **违反 §6 原则 1 (现成表优先)** — 我接受了 A kernel v0 "atomic_facts 单源" 的设计, 没质疑应该走现成表
3. 🔴 **违反 §6 原则 3 (主时间线走 activity_logs)** — 我的 endpoint 测试甚至没测 timeline 段是否真有时间线数据
4. 🔴 **业务数字解读偏差** — 把 atomic_facts 命中 87% 当 "N2 业务突破", 实际现成表 8 组用户都看不到 → 真 N2 = 0/8 段
5. ⚠️ **没建议 A** — A 1ed0a9f kernel v0 提交时, 我应该在接 endpoint 之前先看 kernel SQL 是不是单源; 我直接接了

---

## 6 · 等 A + 顾源源决策的点

### 决策点 1 (A 主导): kernel 重设计方案

按指令 §三, A 接下来要做"NarrativeKernel 重设计方案 (8 段 ← 8 组现成表 聚合视图)". B 等 A 出方案再跟 endpoint / 前端 / baseline 适配.

### 决策点 2 (顾源源决策): atomic_facts vs memory_facts 归并

资产清单 §5 给了 3 个选项 (合并 / 各司其职 / deprecated memory_facts). 这决策影响:
- IngestPipeline 是否要切到 memory_facts 写入路径
- baseline runner 应该测哪张表
- NarrativeKernel 8 段 EVIDENCE 引用层走哪个

### 决策点 3 (B 等批准后做): baseline runner 重写

具体重写方案 (草稿, 等批准):
```python
def run_v22_n2_baseline_v2(client_id, db) -> ReportV2:
    # 1. 拿 NarrativeKernel 输出 (聚合 8 组现成表后)
    narrative = NarrativeKernel(db).generate(client_id)

    # 2. 主 probes 测"用户在故事网能看到的命中"
    for probe in PROBES_5_19_TRUE_ALIGN:
        text = " ".join(s.body_markdown for s in narrative.story_sections)
        probe.hit = any(kw in text for kw in probe.keywords)

    # 3. 待办测 commitments + tasks 表直接
    todo_hit = count_in_tables(["commitments", "tasks"], PROBES_TODO_6)

    # 4. 人物测 entities (type=person) 表直接
    people_hit = count_in_tables(["entities"], PROBES_PEOPLE_5)

    # 5. 综合 P% 公式不变
    return ReportV2(combined_score=主×50% + 待办×30% + 人物×20%)
```

---

## 7 · 流程承诺 (从本 session 起永久执行)

按 §6.1 强制场景, 下次遇到下列任一情况, **先 read inventory 再回应**:

- 用户说"重新评估 / 新计划 / 做错方向 / 重新设计"
- 用户问"你这件事跟现有 XX 表 / 功能的关系"
- 跨表设计 / 新表创建 / 新管道接通
- 收到上下文压缩通知 (本 session 已发生过 1 次)
- session 超 4 小时 (本 session 已超)
- 评估"完成度 / 偏差度"

按 §6.2 提案前 4 道自检, 任一不过, 不递提案.

---

## 8 · 结论

- iterate 1 五个 commit **0 个 revert, 1 个测试维度重写, 3 个等 A kernel 重设计后跟改**
- 上次 "N2 87% 突破" 数字撤回, 改口为 "atomic_facts 单源 87% / 现成表 8 组 0/8"
- 等 A 出 kernel 重设计方案 + 顾源源决策 atomic_facts vs memory_facts 归并后, B 适配
- 立刻停手, 不改任何代码, 等 review

---

**B AI · 2026-05-22**
