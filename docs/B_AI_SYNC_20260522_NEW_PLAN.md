# B AI · 5/22 新计划同步指令(基于 4 维度评估)

> **顾源源 5/22 下午** 请 A AI 把这段贴给 B AI
> **优先级**: 立刻停手, 先读 3 份文档, 再按阶段开干
> **触发**: 上次 sync (`B_AI_SYNC_20260522_ASSET_PIVOT.md`) 后, A 又跑了 4 维度评估发现更深偏差

---

## 一、必读前置(15 分钟,顺序不能跳)

```bash
cd ~/openclaw/workspace/V2.1

# 1. 新计划全文 (463 行,本指令的母版)
cat docs/V2.2_NEW_PLAN_20260522.md

# 2. 4 维度评估报告 (新计划的依据)
cat docs/V2.2_ASSESSMENT_4D_20260522.md

# 3. 产品手册全文 (官方真相源,9 份 docx 镜像 651 行)
cat docs/V2.2_PRODUCT_MANUAL_FULL_TEXT.md
```

**读完后必答的核心问题**(自检):

Q1: 产品手册 §03 战略陪伴**钦定的 6 段叙事**字段名是哪 6 个?
> 答: essence / cooperation / business_intro / people / timeline / next_steps

Q2: 我之前接的 endpoint(`/api/v1/clients/{id}/full-narrative`)拉的是几段?段名是什么?
> 答: 8 段 (identity / people / main_lines / recent_changes / risks / our_collab / open_questions / timeline) — **跟产品手册完全冲突**

Q3: 主仓库 `narrative_generator.py` 已经实现了什么?
> 答: 1156 行,完整实现 6 段叙事 + 调本地 AiService + 引用 narrative_collector 拉的 13 张现成表

Q4: V2.1 NarrativeKernel 跟主仓库 narrative_generator 关系是?
> 答: 重复造轮子,V2.1 砍,用主仓库

**4 道题任一答错 → 回去重读,不准动手**。

---

## 二、6 阶段 B AI 任务清单

### 阶段 0 (30 min) · 砍 V2.1 旧设计假增量

**B AI 立刻干**:

1. **砍 baseline runner**(你自检报告承认 30% 保留度)
   ```bash
   cd ~/openclaw/workspace/V2.1
   git mv scripts/run_v22_n2_baseline.py scripts/run_v22_n2_baseline.py.DEPRECATED
   ```
   在文件头加:
   ```python
   """[DEPRECATED 2026-05-22] V2.1 baseline runner — 只查 atomic_facts 单源.
   新设计(产品手册 §03 6 段) baseline 应该测 6 段在战略陪伴渲染的命中率,
   不是 atomic_facts 一张表的命中. 重写参考 docs/V2.2_NEW_PLAN_20260522.md 阶段 2.
   """
   ```

2. **砍前端 8 段 hook + 组件**(iterate 1 commit 4b254c1 的部分)
   - `src/renderer/hooks/useClientFullNarrative.ts` → `.DEPRECATED`
   - `src/renderer/lib/fullNarrativeTypes.ts` → `.DEPRECATED`
   - `src/renderer/components/FullNarrativeSection.tsx` → `.DEPRECATED`
   - `StrategicClarificationView` 里 import 这些的地方注释掉(不删 view,只断 8 段引用)

3. **砍前端 8 段 endpoint shell**(iterate 1 commit 07b5dd7)
   - `backend/app/api/clients/full_narrative.py` → `.DEPRECATED`
   - main.py 里 include_router 这个 endpoint 的地方注释掉

4. **砍 8 段集成测试**
   - `backend/tests/test_v22_full_narrative_endpoint.py` → `.DEPRECATED`

5. **B 自己写 audit**:`docs/B_AI_PHASE_0_DEPRECATED_LIST.md`
   - 列你砍了哪些文件
   - 列哪些 view 因为砍引用断了链路(用 placeholder 兜底)
   - 估算保留度数字

6. **commit**:
   ```
   [B] chore(v2.2 ★ pivot): 砍 V2.1 8 段叙事 / baseline runner / frontend hook — 跟产品手册 6 段冲突
   ```

**B 阶段 0 验收门**:
- `git grep -l "full-narrative\|FullNarrative\|8 段\|StorySection\|cited_fact_ids"` 结果 ≤ 5 个文件(都是文档 / DEPRECATED 标记,不是活代码)
- 前端 build 不报错(可能有 unused import 警告,可以)
- 任何提到 atomic_facts 单源命中的 baseline 代码全砍

---

### 阶段 1 (45 min) · 前端 NarrativePanel 接通情况报告

**前置**: 等 A 完成阶段 0 砍废 + 跑出 dogfood baseline(顾源源会通知)

**B AI 任务**:

1. **看主仓库现有的 narrative endpoint URL**
   ```bash
   cd ~/openclaw/workspace/yiyu-thinktank-workbench
   grep -rn "narrative_generator\|/narrative\|narrative/refresh" backend/app/main.py | head -20
   ```
   报告:用户在战略陪伴看到的 6 段是从哪个 endpoint 拉的?

2. **看前端 NarrativePanel 组件**
   ```bash
   grep -rln "NarrativePanel\|essence\|cooperation\|business_intro" src/renderer/ | head -10
   ```
   报告:
   - NarrativePanel 在哪个 view 里渲染?
   - 它调的 API 是?
   - 6 段每段在前端怎么展示?(单 markdown / 卡片 / 段落?)

3. **看「让 AI 重新理解」按钮**(产品手册 §03 提到)
   - 这个按钮的位置在哪?
   - 它触发什么 endpoint?
   - 是否真的触发 broadcast?

4. **写报告**:`docs/B_AI_PHASE_1_FRONTEND_AUDIT.md`
   - 主仓库 narrative endpoint URL
   - 前端 NarrativePanel 组件路径
   - 「让 AI 重新理解」按钮链路
   - 当前用户能不能在 app 里看到 6 段?
   - 如果不能,哪个环节断了?

5. **不要改前端**(等 A 完成 collector 补表后再统一改)

**B 阶段 1 验收门**:
- 报告里 4 个问题全部有事实答案(引用代码行号)
- 不是猜测,是 grep 后的真实结果

---

### 阶段 2 (2h) · endpoint 集成测试 + 前端 6 段渲染

**前置**: 等 A 完成 collector 补 8 张表 + LLM prompt 改 + 单测(顾源源会通知)

**B AI 任务**:

1. **写 narrative endpoint 集成测试**(测主仓库 + V2.1 同时)
   - 用日慈基金会作 fixture
   - 调 endpoint 拿 6 段
   - 验证每段:
     - 字段名是产品手册 §03 钦定的 6 个之一(不是 V2.1 旧 8 段)
     - body_markdown 非空(把握度 high/medium)
     - sources 引用现成表(client_dna_documents / risk_signals / weekly_reviews 等)
     - 5/19 张真会议金标准 7 道命中 ≥ 5 道

2. **测「让 AI 重新理解」按钮的 broadcast 触发**
   - 调触发 endpoint
   - 验证 60-90 秒内 narrative_stale_signals 标记 + 6 段刷新

3. **前端 NarrativePanel 兼容现成表新字段**(如果 A 的 collector 引入了新字段)
   - 比如 entities (people 段) 拉了人物 attributes,前端要展示
   - 比如 activity_logs (timeline 段) 拉了 26677 条,前端要 truncate 到最近 50 条
   - 不要新建组件,在主仓库 NarrativePanel 上扩展

4. **commit**:
   ```
   [B] feat(v2.2 N2): narrative endpoint 集成测试 + 前端 6 段渲染兼容现成表新字段
   ```

**B 阶段 2 验收门**:
- 集成测试 12+ 个 PASS
- 前端 build 干净
- 5/19 金标准 ≥ 5/7
- 任意入口看战略陪伴,6 段都有内容(非空)

---

### 阶段 3 (2h) · smart_file_import 前端流程验证

**前置**: 等 A 完成 smart_file_import → IngestPipeline → broadcast 接通(顾源源会通知)

**B AI 任务**:

1. **smart_file_import 前端 e2e 验证**
   - 在前端 dev 跑一次 SmartFileImport 完整流程
   - 拖 2 份新 docx + 写一段背景 + 提交
   - 验证:
     - 5 秒内工作台文件数 +2
     - 60-90 秒内战略陪伴 6 段叙事自动刷新(不需要手动点「让 AI 重新理解」)
     - 任务与日程 timeline 里新增 entry

2. **前端「让 AI 重新理解」按钮验证**
   - 点按钮 → 验证后端真的触发 broadcast
   - 30-90 秒内页面刷新

3. **commit**:
   ```
   [B] test(v2.2 N1): smart_file_import e2e + 让 AI 重新理解按钮链路验证
   ```

**B 阶段 3 验收门**:
- SmartFileImport 模态关闭后 5 秒内 atomic_facts 表 +N (B 不直接查表, 看工作台 UI 文件数)
- 90 秒内战略陪伴 6 段 markdown 更新
- 「让 AI 重新理解」按钮真的有反应

---

### 阶段 4 (1h) · A 主导, B 旁观

阶段 4 是 A AI 加 N3 AI Memory 5 表流量(IngestPipeline 写 ai_episode_log / DocumentLLMExtractor 写 reasoning_traces),**B AI 这阶段没动手任务**。

**B AI 可选**:
- 跑一遍 V2.2 acceptance 三道门看一下当前状态
- 看 ai_episode_log / reasoning_traces 表的数据增长情况
- 不要改代码

---

### 阶段 5 (45 min) · 9 模块手动过 + 配合 final dogfood

**B AI 任务**:

1. **9 模块手动过**(N1 顾源源原话"现有功能不掉链")
   按产品手册 9 份 docx 各对应一个模块:
   - 任务与日程: 收件箱 / 日历 / 周复盘 / Agent 模拟
   - 工作台: 客户列表 / 对话 / 工具 tab
   - 战略陪伴: 6 段叙事 / 思考研判 / 事实澄清 / 让 AI 重新理解按钮
   - 资讯情报站: 品牌监测 / 时效情报 / 焦点指令
   - 成长中心: 我的成长 / 个人手册 / 团队墙 / 徽章
   - 智能文件导入: 多段叙事 / 文件分类 / 确认导入
   - 数据中心: (用户不直接打开,看「待澄清 N」徽章是否正常)
   - 组织计划工坊: 解析部门计划 / 任务挂接
   - 系统设置: 账号 / AI 配置 / 同步

   每个模块标:
   - 🟢 完全顺畅
   - 🟡 能跑但有小问题
   - 🔴 卡住或报错

   写报告 `docs/B_AI_PHASE_5_9MODULE_AUDIT.md`

2. **配合顾源源 final dogfood**
   - 顾源源在 app 里跑一次完整业务流程(智能文件导入 → 战略陪伴看 6 段刷新)
   - B 不参与点击,只看后端日志 + 报问题

3. **commit**:
   ```
   [B] docs(v2.2 ★ final): 9 模块手动过 audit + final dogfood 观察
   ```

**B 阶段 5 验收门**:
- 9 模块审计完成
- 至少 7/9 🟢 (允许 2 个 🟡, 不允许 🔴)

---

## 三、跟 A AI 的接力点(协作必读)

| 接力点 | A 触发 | B 接力 |
|---|---|---|
| T+30min | A 砍废完成 commit | B 砍废完成 commit |
| T+45min | A 跑出 dogfood 6 段 baseline | B 阶段 1 报告前端接通情况 |
| T+1h15m | 顾源源 review baseline | (B 等顾源源决策点 1) |
| T+1h30m | A 开始阶段 2 补 collector | B 等 A 单测 PASS 后开集成测试 |
| T+3h30m | A 完成阶段 2 + 5/19 ≥ 5/7 | (B 等顾源源决策点 2) |
| T+3h30m | A 开始阶段 3 接 smart_file_import | B 等 A endpoint 改完后跑前端 e2e |
| T+5h30m | A 完成阶段 3 + 90s 内 6 段刷新 | (B 等顾源源决策点 3) |
| T+5h30m | A 阶段 4 写 ai_episode_log | B 旁观,可跑 acceptance |
| T+6h30m | A 完成阶段 4 | B 开阶段 5 9 模块审计 |
| T+7h15m | 顾源源 final dogfood | B 看后端日志,报问题 |

**关键规则**:
- 每阶段开始前,先 `git log --since="30 min" --pretty=format:"%h | %s"` 看 A 推了什么 commit
- 不要在 A 还在改的代码上同时改(读 A 的 commit message 知道 A 改了什么)
- 任何阶段超时 30 分钟没 A 通知,先 `cat docs/V2.2_PROGRESS.md` 看 A 进度

---

## 四、commit 前缀 + 共享文件规范

### Commit 前缀

```
[B] feat(v2.2 N1):    阶段 0 砍 / 阶段 3 e2e 验证
[B] feat(v2.2 N2):    阶段 2 集成测试 + 前端渲染
[B] test(v2.2 N1/N2): 测试相关
[B] chore(v2.2 ★ pivot): 阶段 0 砍废
[B] docs(v2.2 ★ final): 阶段 5 audit
```

### 共享文件(改前必先 read)

```
docs/V2.2_PROGRESS.md                  # 每个 commit 后追加一段
docs/V2.2_NEW_PLAN_20260522.md         # A 主写,B 看
docs/V2.2_NORTH_STAR.md                # 顾源源主导
backend/app/services/ingest_pipeline.py # A 主改
backend/app/services/narrative_collector.py  # A 主改
backend/app/services/narrative_generator.py  # A 主改
backend/app/services/smart_file_import.py    # A 主改
```

### B 主写文件

```
docs/B_AI_PHASE_0_DEPRECATED_LIST.md    # 阶段 0 输出
docs/B_AI_PHASE_1_FRONTEND_AUDIT.md     # 阶段 1 输出
docs/B_AI_PHASE_5_9MODULE_AUDIT.md      # 阶段 5 输出
src/renderer/**                          # 前端 view / hook / 组件
backend/tests/test_v22_*_integration.py # 集成测试
```

---

## 五、强制流程提醒(协作文档 §6.1 + §7.1)

每次开新阶段前,**强制按下列顺序读**:

1. `cat docs/V2.2_DATA_ASSET_INVENTORY.md`(208 张表)
2. `cat docs/V2.2_PRODUCT_MANUAL_FULL_TEXT.md`(产品手册 9 份)
3. `cat docs/V2.1_AI_COLLABORATION.md`(协作规则)
4. `cat docs/V2.2_NEW_PLAN_20260522.md`(本计划)

**提案 4 道自检**(§6.2):

```
Q1: 我做的事在 §4 现成表映射里有现成表吗? 有 → 改设计用现成表
Q2: 我加的代码跟主仓库 narrative_generator / narrative_collector 重叠吗? 重叠 → 砍
Q3: 我引用的"段"是产品手册 §03 钦定 6 个之一吗? 不是 → 重写
Q4: 我的判断引用了"行数 / 字段 / commit"事实吗? 没有 → 空中楼阁,回 Q1
```

任一题不过,不准 commit。

---

## 六、立刻开干

**B 现在就做的事**(不等):

1. 读完一、二、三、四节(15 分钟)
2. 阶段 0 砍废开干(30 分钟)
3. 砍完 commit + 写 `docs/B_AI_PHASE_0_DEPRECATED_LIST.md`
4. 等 A 通知阶段 1 起步

**砍 0 阶段的具体清单**(再核对一遍):

```bash
cd ~/openclaw/workspace/V2.1

# 后端 8 段相关
git mv scripts/run_v22_n2_baseline.py scripts/run_v22_n2_baseline.py.DEPRECATED 2>/dev/null
git mv backend/app/api/clients/full_narrative.py backend/app/api/clients/full_narrative.py.DEPRECATED 2>/dev/null
git mv backend/tests/test_v22_full_narrative_endpoint.py backend/tests/test_v22_full_narrative_endpoint.py.DEPRECATED 2>/dev/null

# 前端 8 段相关
git mv src/renderer/hooks/useClientFullNarrative.ts src/renderer/hooks/useClientFullNarrative.ts.DEPRECATED 2>/dev/null
git mv src/renderer/lib/fullNarrativeTypes.ts src/renderer/lib/fullNarrativeTypes.ts.DEPRECATED 2>/dev/null
git mv src/renderer/components/FullNarrativeSection.tsx src/renderer/components/FullNarrativeSection.tsx.DEPRECATED 2>/dev/null

# 注释掉 main.py 里 include_router 的地方 + StrategicClarificationView 里 import

# 文件头加废弃声明 (示例见 §阶段 0)

# 写 docs/B_AI_PHASE_0_DEPRECATED_LIST.md
```

**A AI 跟你同步开干阶段 0**(A 砍 narrative_kernel.py + 测试 + v1 prompt 草稿)。

---

## 七、不要做的事(防偏方向)

| ❌ 不要 | ✅ 应该 |
|---|---|
| 重新设计 8 段 / 7 段 / 9 段 | 严格用产品手册 §03 钦定 6 段 |
| 创建新的 endpoint / 组件 | 修改主仓库 narrative_generator + NarrativePanel |
| 测 atomic_facts 单源命中率 | 测战略陪伴 6 段最终用户看到的命中率 |
| 改 IngestPipeline 4 路径定义 | A 已绑定 §0.2/§0.3 数据源 |
| 跑新的 baseline P% | 等阶段 2 collector 补完再测 |
| 新建测试 fixture INSERT atomic_facts | 集成测试用主仓库 collector 拉真实数据 |

---

**B AI · 5/22 接力开干 · 等 A 阶段 0 commit 后协同推进**
