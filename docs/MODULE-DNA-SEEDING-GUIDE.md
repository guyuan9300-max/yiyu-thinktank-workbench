# 软件 DNA 沉淀指南 — 给其他 AI 线程的工作指引

> 本文档**专供复制粘贴给其他 AI 线程使用**。每个线程只要照本指南做一遍，
> 所有线程贡献的内容会自动汇集到同一个数据库里，跨 session、跨设备共享。

---

## 0 · 这是干嘛的

益语智库的所有 AI 线程 (Claude Code / 其他 AI 工具) 都在重复跟用户澄清同一些东西：
- 软件定位
- 模块边界
- 设计原则
- 各种产品决策

我们要建一个**长期记忆**，让每个线程都把自己听用户澄清过的内容**写进去**，
未来任何 AI 启动新任务时，先**读**这个记忆，少做重复澄清。

---

## 1 · 你 (AI 线程) 要做的事

### Step 1 · 读全部已有内容
**GET** `http://127.0.0.1:47829/api/v1/settings/module-dna`

返回结构:
```json
{
  "modules": [
    {
      "id": "software:root",
      "level": 1,
      "displayName": "益语智库",
      "summary": "...",
      "entries": [
        {
          "id": "entry_xxx",
          "category": "purpose",
          "content": "...",
          "isUserQuote": true,
          "sourceThread": "...",
          "createdAt": "..."
        }
      ]
    }
  ]
}
```

读完后, 把已有内容当作"先验背景知识", **避免重复添加**。

### Step 2 · 梳理你这条线程内用户澄清过的内容
回顾你跟用户的所有对话，找出涉及以下任一类的内容:
- 软件整体定位
- 任何一个模块的定位 (purpose / scope / target_user / value)
- 设计原则
- 产品决策
- 工作流/数据流约定
- 历史背景 / 演化故事
- 反模式 (用户明确说"不要做 X")
- 用户对某个功能的偏好/口味

### Step 3 · 追加 entries (不覆盖)
对每条澄清内容, **POST** 到对应模块:

**POST** `http://127.0.0.1:47829/api/v1/settings/module-dna/{module_id}/entries`

Body:
```json
{
  "category": "purpose | scope | target_user | expected_value | interaction | principle | reverse_design | workflow | open_question | decision | history | example | free_note",
  "content": "用户原话或你的整理 - **不要压缩, 保留细节**",
  "isUserQuote": true | false,
  "sourceThread": "你这条线程的标识 (推荐格式: 'claude-code:R11-workspace' 或 'cursor:bugfix-2026-05')",
  "sourceSession": "(可选) session id",
  "confidence": 0.7 | 0.95 | 1.0,
  "tags": ["可选: formula / metaphor / architecture / from-memory ..."]
}
```

### Step 4 · 如果模块不存在 → 创建
**POST** `http://127.0.0.1:47829/api/v1/settings/module-dna`

Body:
```json
{
  "id": "module:xxx | submodule:xxx | software:root",
  "level": 1 | 2 | 3 | 4,
  "displayName": "可读名",
  "summary": "一句话定位",
  "parentId": "父模块 id (软件级填 null)"
}
```

---

## 2 · 关键原则 (必须遵守)

### 2.1 保留原话, 不要过度压缩
- 用户原话能引用就引用 (`isUserQuote: true`, `confidence: 1.0`)
- 你的整理也写进去, 但**保留细节, 不要总结成 bullet points**
- 用户可能说了一段 200 字的解释 → 完整写进 content, 不要压成一句话

### 2.2 不互相覆盖
- 多个线程都能往同一个模块追加 entries
- 即使内容看起来重复, 也优先追加而不是删除原有
- 例外: 如果用户**明确撤回了某条**, 用 DELETE 删除那条 (不是覆盖)

### 2.3 不要问澄清问题
- 你的任务是**沉淀已有的澄清**, 不是开新的澄清
- 用户原话: "我向你澄清的, 可能向其他人也澄清过" → 不要再问
- 不清楚时, **写下你的不清楚** 到 `category: "open_question"`, 不要直接问用户

### 2.4 标记来源 (sourceThread)
- 用统一格式: `claude-code:<你的主任务>` 或 `cursor:<context>` 或 `chatgpt:<topic>`
- 让用户能追溯每条 entry 来自哪条线程

---

## 3 · 当前已有模块清单 (截至 2026-05-16 上午)

由 `claude-code:data-center-relationship-graph` 线程预填:

| Level | ID | DisplayName | 已有 entries 数 |
|---|---|---|---|
| L1 | `software:root` | 益语智库 | 14 |
| L2 | `module:tasks_calendar` | 任务与日程 | 3 |
| L2 | `module:client_workspace` | 客户工作台 | 3 |
| L2 | `module:strategic_accompaniment` | 战略陪伴 | 5 |
| L2 | `module:intelligence_station` | 资讯情报站 | 3 |
| L2 | `module:growth_center` | 成长中心 | 4 |
| L2 | `module:data_center` | 数据中心 | 4 |
| L2 | `module:settings` | 系统设置 | 5 |
| L2 | `module:weekly_review` | 周复盘 | 3 |
| L3 | `submodule:weekly_overview` | 周复盘/本周概览 | 2 |
| L3 | `submodule:client_strategic_home` | 战略陪伴/客户主页 | 2 |
| L3 | `submodule:strategic_clarification_panel` | 战略陪伴/澄清面板 (规划中) | 3 |

**你可以直接往这些模块追加 entries**, 不需要再创建。
如果你这条线程涉及的模块**不在上表**, 用 Step 4 创建。

---

## 4 · category 字段推荐值 (**建议分类不是硬性限制**)

> **重要**: category 是检索时的方便标签, **不是限制**。如果一条内容跨多个类, 选最贴近的就行。
> 用户原话表达: "你的这些分类限制了进去的入口, 让我没沉淀进去"。
> → **宁可多写, 不要因为'找不到合适分类'就放弃**。category 不合适, 用 `free_note` 兜底, 但内容一定要进。


| category | 用于 | 示例 |
|---|---|---|
| `purpose` | 这个模块解决什么问题 / 北极星 | "本周的这个概览主要是关于任务的概览" |
| `scope` | 边界 (做什么 / 不做什么) | "不显示数据中心动态/文件录入等非任务信息" |
| `target_user` | 谁用 (CEO / 部门领导 / 普通员工) | "员工自己 + 部门领导 + CEO" |
| `expected_value` | 用户能感受到的价值 | "一眼看出本周哪些事必须处理" |
| `interaction` | 跟哪些其他模块协同 | "数据中心 (任务挂主线) + 周复盘 (本周任务)" |
| `principle` | 设计原则 / 哲学 | "卷起来 + 清晰秩序 = 安全感" |
| `reverse_design` | 反模式 (不做什么) | "不造 3 个轮子跑的车" |
| `workflow` | 工作流 / 数据流 / 用户判断方式 | "用户只能判断方向不能判断细节" |
| `open_question` | 待澄清的问题 | "成长中心的排行榜对什么时间窗排?" |
| `decision` | 已做出的设计决策 | "澄清页放在战略陪伴的知识健康度 tab" |
| `history` | 历史背景 / 演化 | "原 hero 区有 6 数字, 已撤回到二级入口" |
| `example` | 真实案例引用 | "日慈基金会 4 条主线: 心灵魔法学院/心松松/..." |
| `data_flow` | 数据流详述 (从前端调 API 到后端处理流程) | "前端 getReviews → backend list_reviews → reconcile..." |
| `architecture` | 架构决定 (层数 / 字段 / 模块组成) | "5 层结构 + 5 个引擎" |
| `bug_pattern` | 已知 bug 模式 + 修复 | "参数名 ?week= vs ?weekLabel= 是常见坑" |
| `gold_sample` | 黄金样本 / 真实数据快照 | "日慈 5 条 event_lines 颗粒度混乱" |
| `migration_note` | 迁移 / 演化笔记 | "v0.1 → v0.2 → v0.3 文档演化" |
| `edge_rule` | 边界规则 (一些必须遵守的硬约束) | "所有 AI 输出必须可钻取到原始证据" |
| `free_note` | 自由备注 (找不到合适分类的兜底) | 杂项 |

**给其他线程的核心建议**:
- 不要因为想不出 category 就不写
- 一条内容**完整 200 字写进 content**, 比拆成 3 个 30 字 entry 更有价值
- 多写不会污染数据 - 我们要的是细节, 不是精简
- 对其他模块的"细节描述"才让该模块知道整体怎么配合


---

## 5 · 示例: 给客户工作台追加一条 entry

假设你这条线 (假设叫 `cursor:client-workspace-search`) 跟用户澄清过:
> 顾源源: "客户工作台的 AI 问答, 必须基于当前主线回答, 不要漫无目的检索"

那你应该:

```bash
curl -X POST 'http://127.0.0.1:47829/api/v1/settings/module-dna/module:client_workspace/entries' \
  -H "Content-Type: application/json" \
  -d '{
    "category": "decision",
    "content": "客户工作台的 AI 问答必须基于当前主线回答, 不要漫无目的检索 — 顾源源原话",
    "isUserQuote": true,
    "sourceThread": "cursor:client-workspace-search",
    "confidence": 1.0
  }'
```

---

## 6 · 持续沉淀机制（关键 — 让 DNA 活起来）

**一次性沉淀历史只是起点**。要让软件 DNA 真正变成"软件越用越懂自己"，每条线程必须养成
**持续沉淀**的习惯。

### 6.1 触发持续沉淀的 5 个时刻

| 时刻 | 怎么做 | category |
|---|---|---|
| **用户澄清了新的产品定位/原则/边界** | 立刻 POST 一条，标记 `isUserQuote: true` | purpose / principle / scope / target_user / reverse_design |
| **一轮重大工作结束**（一个 Phase 完成、一个大 bug 修完、一个新功能上线） | 总结本轮经验，POST 一条或多条 | decision / history / workflow |
| **发现/确认了一个反模式** | 用户说"不要做 X" 或者亲眼看到 X 不好 → POST | reverse_design |
| **发现矛盾/不清楚的地方** | 不要去问用户，写到 `category: "open_question"` | open_question |
| **用户撤回了之前的决定** | DELETE 旧 entry，POST 新 entry 说明原因 | history（旧）+ decision（新） |

### 6.2 每轮工作结束前的"沉淀 checklist"

在你这条线程完成一轮任务（无论大小）**结束前**，问自己 4 个问题：

1. 用户这轮里**有没有澄清新的产品定位**？（即使是顺嘴一句也算）
   → 有 → POST 到对应模块的 `principle` / `decision`
2. 用户**有没有撤回**之前的某个决定 / 表达不喜欢某个做法？
   → 有 → POST 到对应模块的 `reverse_design` / `history`
3. 我**发现了哪些产品哲学**用户没说但我体会到的？
   → 写到 `principle` 但 `isUserQuote: false`，`confidence: 0.7`
4. 我**还有哪些不清楚的地方**？（之前不能直接问用户，现在沉淀下来）
   → 写到 `open_question`，未来其他线程 / 用户主动 review 时能看到

### 6.3 示例：一轮工作结束的沉淀

假设你这轮做的是"修复周复盘组织视角 bug"，用户澄清过几件事。结束前你应该 POST：

```bash
# 1. 用户原话 → principle
POST /api/v1/settings/module-dna/module:weekly_review/entries
{
  "category": "principle",
  "content": "顾源源原话: '我希望软件可以分角色显示不同视角 — 普通员工不显示切换器, 部门领导 2 按钮无下拉, CEO 3 按钮+部门下拉'",
  "isUserQuote": true,
  "sourceThread": "claude-code:weekly-review-bug-fix",
  "confidence": 1.0
}

# 2. 本轮发现 → decision
POST /api/v1/settings/module-dna/module:weekly_review/entries
{
  "category": "decision",
  "content": "组织视角实际包含全组织成员任务 (验证: 传 weekLabel=2026-W20 时返回 32 项含林佳维 3 项/乐乐 1 项)。AI 主线聚合卡片当前没显示 owner 分布 — 是 UI 暴露不足, 不是数据丢失",
  "isUserQuote": false,
  "sourceThread": "claude-code:weekly-review-bug-fix",
  "confidence": 0.95
}

# 3. 还不清楚的 → open_question
POST /api/v1/settings/module-dna/module:weekly_review/entries
{
  "category": "open_question",
  "content": "云端 reviews/dashboard 不传 weekLabel 时默认返回上一周 (W19) — 这是 by-design 还是 bug? 待用户/云端工程师确认",
  "sourceThread": "claude-code:weekly-review-bug-fix"
}
```

### 6.4 给主任务工作流的指引

如果你跑在一个**有阶段性产物**的工作流里（如 Phase 0/1/2、R11/R12/R13、Stage A/B/C），
每个阶段结束前**必须** POST 至少 1 条到 `category: "history"`，记录这阶段做了什么、学到什么。

---

## 7 · 不要做的事

- ❌ 不要修改/覆盖别的线程的 entries
- ❌ 不要把用户原话压缩成 bullet (会丢失细节)
- ❌ 不要主动找用户问问题 (你的任务是沉淀, 不是澄清)
- ❌ 不要重复添加内容 (先 GET 看已有, 真重复就跳过)
- ❌ 不要把客户业务知识 (日慈/为爱黔行/林佳维等) 写进来 — 那些归数据中心的客户档案/external_persons 表

---

## 8 · 复制给其他线程的提示词模板

### 8.1 一次性沉淀历史 (首次启动)

```
你是益语智库项目里的一条 AI 线程。我们在做"软件 DNA 长期记忆"项目,
让所有 AI 线程把跟我澄清过的产品定位/模块/原则/决策沉淀到同一个数据库, 跨 session 共享。

请读这份指南: /Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench/docs/MODULE-DNA-SEEDING-GUIDE.md

按指南做首次沉淀:
1. GET 一遍现有的 modules 和 entries, 知道已有什么
2. 回顾你跟我的所有对话, 找出我澄清过的所有定位类内容
3. POST 追加到对应模块 (不要覆盖, 不要压缩, 保留原话引用 isUserQuote: true)
4. 模块不存在就先 POST 创建 (看指南 Step 4 格式)
5. 不需要再问我澄清问题 — 我可能跟其他线程也澄清过
6. 不清楚的地方写到 category: "open_question"
7. 完成后报告: 你新增了多少 entries, 分别在哪些模块, sourceThread 是什么

API 在 http://127.0.0.1:47829, 后端必须在跑。
你的 sourceThread 标识自己取一个有辨识度的名字 (推荐 claude-code:<主任务名> 或 cursor:<context> 或 chatgpt:<topic>)。

关键原则:
- 保留原话不压缩 (哪怕一段 200 字也完整写进 content)
- 不互相覆盖 (其他线程已写的内容不要改)
- 客户业务知识 (日慈/黔行/林佳维等具体人和客户) 不写在这里 — 那些归客户档案
```

### 8.2 持续沉淀指令 (每轮工作结束前必读)

**复制这段给所有你正在用的 AI 线程, 让它们形成习惯:**

```
[软件 DNA 持续沉淀 — 每轮结束执行]

在你这条线程结束本轮工作前, 必须做以下"沉淀 checklist":

1. 我这轮里有没有澄清新的产品定位/边界/原则?
   → 有 → POST 到对应模块的 principle / decision / scope
   → 用户原话标 isUserQuote: true + confidence: 1.0

2. 我有没有撤回之前的某个决定 / 表达不喜欢某个做法?
   → 有 → POST 到 reverse_design / history (说明为什么撤回)

3. AI 本轮发现了哪些产品哲学 (用户没明说但 AI 体会到的)?
   → POST 到 principle 但 isUserQuote: false, confidence: 0.7

4. 还有哪些不清楚的地方?
   → POST 到 open_question (未来其他线程或我主动 review 时会看到)

5. 如果本轮是一个完整阶段 (Phase / Stage / R 系列工作) 的收尾:
   → POST 一条 history 总结这阶段做了什么、学到什么

API: POST http://127.0.0.1:47829/api/v1/settings/module-dna/{module_id}/entries
sourceThread 用同一个标识, 让我能追溯每条沉淀来自哪轮工作。

不要问我澄清问题 — 这是沉淀环节, 不是澄清环节。
不清楚的写到 open_question, 我以后会主动 review。
```

---

## 9 · 数据库直接读 (备用)

如果 API 调用不通, 数据存在 SQLite:
- 表 `module_definitions` — 模块壳
- 表 `module_definition_entries` — 内容 entries (一个模块多条)
- DB 路径: `~/Library/Application Support/YiyuThinkTankWorkbench2/app.db`

---

## 10 · UI 入口 (未来)

软件设置里会加一个「软件 DNA」tab, 让用户能直接看 + 编辑所有 entries。
当前 (2026-05-16) UI 还没建, 但 API 完整可用。
