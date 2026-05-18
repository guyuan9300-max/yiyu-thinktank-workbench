# Step 0 · 数据中心改造蓝图 v0.1

> 状态：**第一稿，待用户审阅**
> 日期：2026-05-15
> 范围：定义业务主线（business thread）层及其周边基建。本文档**只做产品讨论与字段定义**，不含代码改动。
> 验证样本：日慈基金会 + 为爱黔行公益服务中心（两次澄清问答完整记录见附录）

---

## 0 · 北极星宣言

> **「这一个软件就像一个超级员工，他是站在战略层面的高度和完整度去陪伴这个组织发展。」**
> — 顾源源 2026/5/15

所有后续设计决策的判断标准：**这件事能否让战略陪伴更像一个超级员工？** 不能的，不做。

---

## 1 · 改造哲学的 3 个核心翻转

整次改造不是"加几张表"。是 3 个底层视角的翻转：

### 1.1 功能价值 → 业务价值

| 维度 | 功能价值（当前） | 业务价值（目标） |
|---|---|---|
| AI 输出 | "知识完整度 47%，建议补充文档" | "您 4/28 对庆华承诺 5/15 交付，距承诺日 0 天，交付物形式至今未定" |
| 价值评估 | 这个功能有什么能力 | (能力 × 解决的问题 × 频次 × 困扰程度) |

### 1.2 AI 视角 → 用户视角

不能再让 AI 说"我（AI）的工作卡在没有数据上"。**必须让 AI 像咨询顾问一样说"你（用户）的工作卡在 X 上"。**

支点：**AI 必须先懂"你在做的这件事是什么"**——这就是业务主线。

### 1.3 对象存储 → 证据解释网络

当前数据中心是"对象存储 + LLM 临时调用"的混合体。缺一个 **统一的事实解释层**。改造完成后：

- 每个事件被结构化解释（承诺/决策/风险/事实/教训/进展）
- 每个主体（人/客户/主线/部门）有稳定 ID
- 每个解释带时间锚、置信度、可追溯
- 每个数字可钻取到原始证据
- 数据中心从此从"存了什么"升级到"对每个主体都有可解释、可追溯、可横向对标的画像"

### 1.4 客户 DNA = 数据中心持续沉淀的详尽资料大全（非临时 AI 摘要）

> "现在的'DNA'是把资料丢给 AI 让 AI 临时写。真正的 DNA 应该是数据中心持续沉淀的、详尽的客户资料大全。"

**三种主体的 DNA**（这次改造的最终输出物）：
- **客户 DNA** = 客户资料大全 + 业务主线 + 判断 + 时间快照
- **主线 DNA** = 业务主线的事实链 + 多维澄清 + 推进节奏
- **人 DNA** = operator 的能力证据 + 岗位锚点 + 时间快照

---

## 2 · 真实数据诊断

基于 5/15 生产数据库 248MB 副本。

### 2.1 数据健康度盘点

| 表 | 行数 | 状态 | 关键问题 |
|---|---|---|---|
| event_lines | 41 | 🟡 半活 | 颗粒度混乱（5 种级别全用 project_line） / AI 生成的 current_blocker 是模板废话 / business_category 全空 |
| event_line_activities | 70 | 🔴 90% 测试垃圾 | 缺业务语义标签 |
| event_line_weekly_snapshots | **0** | 🔴 死表 | 字段设计完美但无人写 ← **最大浪费** |
| event_line_memory_snapshots | 36 | 🟡 半活 | current_blocker/next_step 全空或模板化 |
| memory_facts | 3010 | ✅ 大丰收 | 但跟 thread 没显式关联 |
| evidence_cards | 168 | 🟡 全 'neutral' | polarity 单一未分化 |
| entities | **0** | 🔴 死表 | 客户字典实体没用这张 |
| atomic_facts | **0** | 🔴 死表 | 设计了但没用 |
| fact_contradictions | **0** | 🔴 死表 | 之前的扇出 #4 都没数据 |
| meetings | 7 | 🔴 严重不足 | 录入流程没跑 |
| action_items | 4 | 🔴 死表 | 承诺链断流的最致命点 |
| judgment_versions | 21 | 🟡 全 candidate | 没人 approved |
| client_strategic_profiles | 0（日慈+黔行） | 🔴 完全空 | 表存在但流程没跑 |
| cooperation_relationships | 0（日慈+黔行） | 🔴 完全空 | 同上 |
| plan_items | **表不存在** | 🔴 缺失 | weekly_reviews.related_plan_ids_json 是死链接 |

### 2.2 关键 finding

1. **结构已就位 70%**：event_lines / activities / weekly_snapshots / memory_snapshots / memory_facts / evidence_cards / judgment_versions —— 完整四层结构（主线/标注/快照/字典/判断）的字段都设计过了。
2. **真问题不是"缺表"，是"很多设计了但没人在用"**。
3. **AI 生成的字段质量灾难性**：current_blocker / next_step 大量出现模板废话（"当前没有特别突出的阻塞，但仍需盯住推进收束。下一步：根据最近会议'飞书会议按钮联调'形成明确后续安排"）—— 这是 AI 视角废话的活靶子。
4. **测试数据混入生产**：庆华是系统模拟角色 / 黔行教室改造 3 个 task 是测试数据 / 90% event_line_activities 是 smoke test 附件。
5. **承诺链上游断流**：meetings 7 条 / action_items 4 条，跨整个产品 / 跨多个客户。

---

## 3 · 核心结构决策

### 3.1 不新建 business_thread 表，升级 event_lines 体系

**理由**：

| 我之前设想的 | event_lines 现状 |
|---|---|
| business_thread (主线表) | event_lines（已存在，70% 字段重合） |
| evidence_annotations (标注层) | event_line_activities（已存在，需加 4 字段升级） |
| thread_weekly_snapshot | event_line_weekly_snapshots（已存在，字段完美） |
| thread_current_snapshot | event_line_memory_snapshots（已存在） |

再造 thread 表 = 结构性冗余 + 现有代码大改 + 数据迁移痛苦。

**所以方向**：**保留 event_lines 名字，补字段+改抽取机制+激活死表**。改名（如果坚持要叫 business_thread）可以放在 Step 3 收尾时统一做。

### 3.2 周边新表（不是升级现有，是真新增）

- **external_persons** —— 外部人物表（张真/王强/詹瑶/吴建林 等，operators 不够用）
- **client_artifacts** —— 客户级版本化产物（价值观/使命/工作坊设计等）
- **contracts** —— 合作合同
- **plan_items** —— 部门/机构计划项（周复盘 related_plan_ids 的真正归宿）

---

## 4 · 字段升级清单

### 4.1 event_lines 加 9 个新字段

```
event_lines:
  + thread_level         TEXT  -- project/phase/commitment/single_touch/mechanism
  + parent_thread_id     TEXT  -- 嵌套关系（承诺级挂到阶段级）
  + derivation_from_id   TEXT  -- "衍生自"关系（区别于父级，如美育系列衍生自大山里的音乐课堂）
  + committed_at         TEXT  -- 承诺产生日（业务时间锚）
  + expected_completion_at TEXT -- 预期完成日
  + deliverable_spec_json TEXT -- 交付物 + 验收标准
  + clarification_status_json TEXT -- 每个维度的 ✓/⚠️/❌
  + is_test_data         INTEGER DEFAULT 0  -- 测试数据标记
  + name_history_json    TEXT  -- 命名变更（教师赋能 → 心松松）
```

**关键约束**：
- thread_level 必填，是颗粒度的硬规范（见 §5）
- 不设 `expected_lifespan` —— 承诺级寿命可变（几周到 3 年）

### 4.2 event_line_activities → evidence_annotations 升级（加 5 字段）

```
event_line_activities:
  + business_semantic    TEXT  -- 承诺/决策/风险/事实/教训/进展（取代单一 polarity）
  + impact               TEXT  -- 推进/中性/阻塞
  + annotator_type       TEXT  -- llm / human / system / multi_source
  + confidence           REAL  -- 0.0~1.0
  + user_confirmed_at    TEXT  -- 用户确认时间（高置信度证据）
```

**说明**：把 `evidence_cards.polarity='neutral'` 的单一标签升级到 6 类业务语义。每条 annotation 自带 lineage（已有 source_type/source_id）+ confidence + user_confirmed_at，实现「血缘 + 置信度」原则**内置而非单独建表**。

### 4.3 新表 · external_persons（外部人物）

```
external_persons:
  id                       TEXT PRIMARY KEY
  canonical_name           TEXT  -- 主名（如"王强"）
  aliases_json             TEXT  -- [{alias:"强哥", source:"asr", confidence:0.9}, {alias:"王老师", source:"user"}]
  client_id                TEXT  -- 主要关联客户
  current_title            TEXT  -- 当前职位
  titles_history_json      TEXT  -- 历史职位变更
  roles_json               TEXT  -- [{role:"心灵魔法学院负责人", scope:"心灵魔法学院", since:"长期"}, {role:"心盛实管", scope:"心盛", since:"2026-05"}]
  family_relations_json    TEXT  -- [{related_person_id:"...", relation:"配偶", note:"共同创始人"}]
  health_signal_json       TEXT  -- {status:"recovering", since:"2025-08", note:"精神状态不好"}
  work_style_traits_json   TEXT  -- ["管得细", "信任度低", "亲力亲为"]
  employment_status        TEXT  -- 在职 / 离职 / 休假 / 退休
  status_changed_at        TEXT
  is_simulated             INTEGER DEFAULT 0  -- AI 模拟角色标记
  source_evidence_ids_json TEXT  -- 这个人物的来源证据
  created_at, updated_at
```

**关键设计**：
- `aliases_json` 必须带 `source` 字段（asr/ocr/user/doc/manual）—— ASR 来源的别名置信度自动降低，防止录音转文字错误污染
- `is_simulated` 防止把测试模拟角色（如"庆华"）当真人处理
- `family_relations_json` —— 黔行案例验证（吴建林+詹瑶夫妇共治是治理关键 DNA）
- `health_signal_json` + `employment_status` —— 日慈+黔行都验证（高老师躯体化→离职 / 詹瑶精神状态→休假回归）

### 4.4 新表 · client_artifacts（客户版本化产物）

```
client_artifacts:
  id                  TEXT PRIMARY KEY
  client_id           TEXT
  thread_id           TEXT  -- 关联到具体主线
  artifact_type       TEXT  -- mission_vision_values / workshop_design / strategy_report / brand_guideline / process_map
  title               TEXT
  version             TEXT  -- v1.0 / v1.1
  content             TEXT  -- 全文（或 markdown）
  approval_status     TEXT  -- draft / internal_reviewed / client_reviewed / client_approved / superseded
  client_feedback_json TEXT -- [{from:"詹瑶", date:"2026-05-15", note:"同意，需增加行动部分"}]
  supersedes_id       TEXT  -- 上一版本
  superseded_by_id    TEXT
  source_document_id  TEXT  -- 关联到 documents 表
  authored_by_user_id TEXT
  delivered_at        TEXT
  created_at, updated_at
```

**用例**：
- 日慈使命愿景价值观（益语调整版）—— mission_vision_values，v1，已交付，张真基本同意
- 黔行 5 条价值观 + 待补行动篇 —— mission_vision_values，v1，client_reviewed（詹瑶同意），有 client_feedback
- 黔行 6 月工作坊设计（顾老师创新方案）—— workshop_design，v2（取代乐乐方案 v1）
- 黔行三年战略咨询报告 V1.0 —— strategy_report，client_reviewed（无异议）

### 4.5 新表 · contracts（合作合同）

```
contracts:
  id                TEXT PRIMARY KEY
  client_id         TEXT
  title             TEXT
  contract_type     TEXT  -- 战略陪伴 / 项目咨询 / 培训 / 援助
  signed_at         TEXT
  term_type         TEXT  -- one_year / multi_year
  service_period_start TEXT
  service_period_end TEXT
  billing_period    TEXT  -- annual / per_milestone
  renewal_status    TEXT  -- active / expiring_soon / renewed / lapsed
  renewal_decision_due TEXT  -- 续约决策应在什么时候做出
  total_amount      REAL
  document_id       TEXT  -- 关联 documents 表里的合同 PDF
  notes             TEXT
  created_at, updated_at
```

**用例**：日慈 2025/6/23 签的战略陪伴合作协议 —— 三年期，服务期到 2026/8 结束，费用一年一结，**renewal_status='expiring_soon'** —— 当前未续约，必须主动提醒。

### 4.6 client_strategic_profiles 字段扩展

```
client_strategic_profiles:
  ... (现有字段保留)
  + governance_mode             TEXT  -- 理事会驱动 / 秘书处驱动 / 创始人驱动
  + governance_structure_json   TEXT  -- {founders:[...], current_leadership:[...], decision_process:"..."}
  + business_lines_json         TEXT  -- [{name:"大山里音乐课堂", proportion:"50%", method:"美育", relation:"起步项目"}]
  + funder_relations_json       TEXT  -- [{funder:"杉树基金会", strength:"weak", contact:"丁杰理事长", note:"年会结识"}]
  + key_personnel_health_signals_json TEXT  -- 关键人员健康/在岗信号汇总
  + needs_review                INTEGER DEFAULT 0  -- 已有
  + last_human_confirmed_at     TEXT
```

**用例**：
- 日慈 `governance_mode='秘书处驱动'`（用户明确说"日慈不是理事会驱动"）
- 黔行 `governance_structure_json` 必须记录"吴建林+詹瑶夫妇共治+理念不合"
- 黔行 `business_lines_json` 记录 50%/30-40%/其他 的占比和方法差异

### 4.7 测试数据 / AI 模拟 标记机制（跨表）

**所有承担"生产业务"的表加 `is_test_data` + `is_simulated` 字段**：
- tasks
- event_lines
- meetings
- documents
- external_persons / operators

**配套机制**：
- 软件 UI 在"工作台 / 战略陪伴"默认**过滤掉** `is_test_data=1` 和 `is_simulated=1` 的记录
- 提供"包含测试数据"切换开关
- 任务模板生成的测试样本**默认标记** `is_test_data=1`

**应用场景**（这次澄清直接揭示）：
- 庆华 → `is_simulated=1`
- 黔行教室改造 3 个 task → `is_test_data=1`
- 黔行音乐课堂当前 event_line 下挂的测试任务 → `is_test_data=1`

### 4.8 数据剔除 / 纠错机制

**对所有"AI 自动归类"的关联加可撤回字段**：

```
documents:
  + misattribution_status   TEXT  -- ''/disputed/removed
  + removed_reason          TEXT
  + removed_at              TEXT
```

**应用场景**：浙江敦和慈善基金会的研究报告被错误归到黔行库 → 用户一键标记 `misattribution_status='removed'` → 软件后续过滤掉这些资料 → 不再误导 DNA。

**澄清面板里要内置这个操作**（"这份文档真的属于这个客户吗？"）。

---

## 5 · 主线颗粒度规范

5 种 `thread_level`，配套不同 UI 形态和嵌套规则：

| 级别 | 寿命 | 典型样本 | UI 形态 | 嵌套 |
|---|---|---|---|---|
| `project` | 1-3 年 | 日慈战略陪伴 / 大山里的音乐课堂 / 心松松（原教师赋能） | 总览卡片，置顶 | 顶层 |
| `phase` | 季度/半年 | 日慈使命愿景价值观调整 / 黔行 6 月工作坊 / 黔行价值观系统 v1 | 进度条卡片 | 挂在 project 下 |
| `commitment` | 几周-几个月 | 跟笑雨核对教师项目 / 5/1 前发价值观给詹瑶 | 待办列表项 | 挂在 phase 或 project 下 |
| `single_touch` | 一次性 | 约见日慈张真看益语系统 / 4/19 河南面谈 | 时间线点 | 挂在 commitment 下 |
| `mechanism` | 长期 | 建立重点客户周跟进节奏表 | 持续模块卡片 | 顶层 |

**判断规则**：
- 有明确交付物 + 明确截止日 = `commitment`
- 跨多个 commitment + 阶段性目标 = `phase`
- 跨多个 phase + 整体战略方向 = `project`
- 一次见面/电话/会议 = `single_touch`
- 没有终点的运营机制 = `mechanism`

**长程跟踪原则**：寿命**不预设**，按 `committed_at` → `closed_at` 真实跨度走。长寿命主线（>1 年）会触发"阶段性滚动摘要"接口（Step 3 实施）。

---

## 6 · 死表激活计划

按优先级：

### P0 · 必须激活
| 表 | 激活方式 |
|---|---|
| event_line_weekly_snapshots | 写周度生成 job（每周一凌晨 03:00），从 event_lines + activities 反推 |
| meetings + action_items | 激活会议录入流程（这是承诺链上游） |

### P1 · 重要
| 表 | 激活方式 |
|---|---|
| evidence_cards.business_semantic | 替换 polarity='neutral' 单一标签 |
| client_strategic_profiles 内容自动填充 | LLM 从 memory_facts 反推 |
| plan_items | 全新建表（部门/机构计划项） |

### P2 · 锦上添花
| 表 | 激活方式 |
|---|---|
| entities | 跟 external_persons 合并讨论 |
| atomic_facts | 评估是否真需要 |
| fact_contradictions | 在 evidence_annotations 上加 contradiction_with_id 即可，可能不需独立表 |

---

## 7 · Step 2 必做项

### 7.1 战略陪伴 · 澄清面板（最高优先级）

**取代/升级现有"矛盾和待确认"模块**，改名 **「事实澄清 · AI 主动询问」**。

**5 个核心能力**：

1. **AI 提问**：基于客户 DNA 完整度，自动生成针对性问题（达到本次澄清同等水平 —— 见 §7.2 KPI）。
2. **引文支撑**：每个问题下方显示"我是基于以下材料问的"+引用 evidence/document，带 quote 高亮。
3. **一键打开文档**：每个引用旁有 `📂 打开` 按钮，调用现有 `window.yiyuWorkbench.openPath()`。
4. **版本核对**：当问"这是不是最新版本"时，自动对比 documents 表里同主题最近上传时间，标记"该文档已是最新"或"X 天前还有更新"。
5. **澄清后自动沉淀**：
   - 答案 patch 到对应字段（memory_facts / event_lines / external_persons / client_strategic_profile / client_artifacts）
   - 新矛盾自动 raise（"心盛 3 种负责人说法"那种）
   - 新文档自动入库提示
   - Q/A 留存到 `clarification_records` 表，作为 DNA 演化 audit trail
6. **跟客户字典融合**：把现有的实体澄清入口和这个面板合并，统一从战略陪伴入口。

### 7.2 Clarification Quality Score（澄清质量评估 KPI）

**用户原话**："至少要达到今天跟你一样的澄清水平"

每条 AI 生成的澄清问题自评打分：

| 维度 | 满分 | 评分依据 |
|---|---|---|
| 针对性 | 30 | 是否引用了具体材料（doc_id / evidence_id），不是泛问 |
| 矛盾揭示 | 25 | 是否指出材料间矛盾（如 ASR 不同写法、字段空缺、时间冲突） |
| 触发深度 | 20 | 用户回答能否引出 ≥1 个新疑问 |
| 业务价值 | 15 | 这个问题的澄清结果是否能直接影响一个决策/动作 |
| 可执行性 | 10 | 是否给用户提供清晰回答路径 |

**目标**：上线时 AI 平均得分 ≥ 80。
**评分员**：先用 GPT 评分 → 用户校准 → 沉淀为软件内置 classifier。
**用户黄金样本**：本文档附录 A、B 中我提的 20 个针对性问题。

### 7.3 模板废话替换（最容易演示的"AI 视角→用户视角"翻转）

`event_lines.current_blocker` / `event_lines.next_step` / 任务的 next_action / 客户的判断 summary，**当前全是 AI 模板**。

替换原则：
- 没有真实证据支撑时**留空**（不生成废话）
- 有证据时按"用户视角 + 业务语言"生成（不是"我（AI）卡在没数据"）
- 用户在 UI 上能一键改写、改完会反馈给抽取 prompt

### 7.4 数据卫生 · 测试数据清理

- 删除/标记所有 `is_test_data=1` 的历史数据
- 删除/标记所有 `is_simulated=1` 的早期模拟角色（庆华、本机用户等）
- 文档误归类一键剔除（敦和基金会从黔行库剔除）

---

## 8 · 长程跟踪原则（3 年时间窗）

整个数据中心设计按"3 年长程跟踪"原则：

1. **snapshot 表不做季度归档** —— 无限累积，靠分区/索引优化
2. **thread 不做"completed 后隐藏"** —— 已完成态可查询、可复盘
3. **长寿命主线（>1 年）触发滚动摘要接口** —— Step 3 实施
4. **memory_facts 加 `valid_to` 字段** —— 已有，正确使用
5. **client_strategic_profile 保留 history** —— 每次重大调整生成 snapshot

---

## 9 · 实施路径

### Step 1 · 主战场（3-4 周，工程实施）

| 周 | 动作 |
|---|---|
| W1 | 字段补充 DDL（event_lines + activities + clients + 4 张新表） |
| W2 | 替换抽取机制（不再生成模板废话） |
| W2 | 写 event_line_weekly_snapshots 定时 job |
| W3 | 死表激活 P0（meetings/action_items 录入流程） |
| W3-W4 | evidence_cards.business_semantic 多元化 / 测试数据清理 |

### Step 2 · 必做项（2 周）

| 周 | 动作 |
|---|---|
| W5 | 澄清面板后端（API + clarification_records 表 + LLM 提问 prompt） |
| W5-W6 | 澄清面板前端（战略陪伴里新模块，含 5 个核心能力） |
| W6 | Clarification Quality Score 评分器 + 校准 |
| W6 | 跟客户字典融合 |

### Step 3+ · 后续

- 横向锚点 / 分群标杆（需 2-3 个月数据积累后做）
- 完整 entity resolution（视组织实际情况判断是否对接飞书/HR）
- 长程滚动摘要
- 知识地图 Obsidian 风可视化（已存在的 Stage 4 任务）
- lint 三件套（已存在的 Stage 5 任务）

### 双 demo（Step 2 收尾时）

用同一套基建演示两种视角投影：
- **战略陪伴**：日慈/黔行的主线视图 + 澄清面板
- **成长中心**：顾源源 / 庆华 / 乐乐的能力快照 + 证据钻取

---

## 10 · 待决策点

需要用户在审阅本文档时一并决策：

1. **event_lines 改名 vs 保留名字**：保留省事，改成 business_threads 更语义化。**建议保留**。
2. **operators vs external_persons 是否合并**：当前 operators 是内部人员表，external_persons 是外部人物表。**建议先并列存在，Step 3 评估合并**。
3. **plan_items 表是否本次建**：周复盘 related_plan_ids_json 等着它。**建议本次建空表 + 简单 API，内容留到后续填**。
4. **client_artifacts 跟 documents 的关系**：artifact 是 documents 的"结构化封装"，是同表加字段还是独立表？**建议独立表 + source_document_id 软关联**（version/approval_status 在 documents 上很别扭）。
5. **AI 模拟角色 / 测试数据**是否立刻批量清理：**建议本次只加字段+标记，清理动作单独排期**（避免误删用户测试期间的真实数据）。
6. **澄清面板的"打开文档"按钮**：日慈/黔行的资料在多个目录散落，应该用 documents.path 直接 open，还是先归档到统一目录？**建议直接用 path**。

---

## 附录 A · 日慈基金会 DNA 样本 v0.1

### A.1 机构信息
- 名称：日慈基金会
- 性质：公益基金会
- 域：儿童青少年心理
- 决策机制：**秘书处驱动**

### A.2 战略定位（2026 年新）
- **核心提法**：「以创造普惠关系为中心，以数据资产为底盘」
- **确定时间**：2026/2，理事会已通过
- **「数据资产」具体含义**：
  - 早期：心灵魔法学院中孩子的行为数据
  - 下阶段：心盛计划过程沉淀的大学生困惑数据 + 角度 + 解决方式
  - 价值路径：量积累/交叉计算 → 数据洞察 → 反映问题复杂原因+趋势 → 社会意义
- **战略落地状态**：⚠️ 不定数（取决于新项目设计/业务落地能力）

### A.3 业务线（4 条平行）
| 项目 | 当前名 | 历史名 | 服务对象 | 负责人 |
|---|---|---|---|---|
| 心灵魔法学院 | 同 | 同 | 儿童 | 王强（项目总监） |
| 心松松 | 心松松 | 教师赋能 | 教师（同行伙伴） | 笑雨老师 / 张真前几天同步过最新进度 |
| 心盛计划 | 同 | 同 | 大学生 | 王强（接替老高，2026/5 起）+ 研究院耀琛+立煌兜底 |
| 繁星计划 | 同 | 同 | 儿童青少年心理生态 | 未明 |

**服务对象统一表述**：最终对象 = 儿童 + 青少年；阵地 = 校园；同行伙伴 = 教师；新增 = 大学生（心盛新增）。

### A.4 关键人物（external_persons）

| 人物 | 别名 | 角色 | 状态 |
|---|---|---|---|
| 张真 | 同 | 秘书长 | 在职。新加坡出差对方是其师兄，无实质合作。前几天同步过心松松进度 |
| 王强 | 强哥 / 王老师 / 王强老师 | 心灵魔法学院负责人 / 项目总监 / 心盛实管（接替老高） | 在职 |
| 岩冰 | 岩冰老师 | 对外筹款负责人 | 在职 |
| 笑雨 | 笑雨老师 | 心松松（原教师赋能）负责人 | 在职 |
| 高老师 | 老高 | 原心盛 + 品牌负责人 | 🔴 **上周离职** |
| 章方 | 同 | 原心盛某层级 | 🔴 同一天离职。抑郁背景，影响长期大额企业捐方 |
| 小鱼 | 同 | 原心盛执行 | 🔴 被辞退（导火索） |
| 耀琛 | 同 | 研究院负责人之一 / 心盛创始人主理人 | 在职兜底 |
| 立煌 | 同 | 研究院负责人之一 / 心盛创始人主理人 | 在职兜底 |

### A.5 合作合同
- 协议：日慈 2025 年战略陪伴合作协议
- 签约：2025/6/23
- 期限：**三年期**
- 服务期：到 **2026/8** 结束
- 结算：费用一年一结
- **续约状态**：🟡 看起来会延续，但尚未续约 → `renewal_status='expiring_soon'`

### A.6 当前主线状态

| 主线 | 状态 | 节点 |
|---|---|---|
| 战略陪伴总线 | active | — |
| 心松松梳理 | 🟢 推进中 | 张真已同步最新进度，资料入库 |
| 使命愿景价值观调整 | 🟢 已交付 v1 | 张真基本同意，在日慈资料库 |
| 品牌升级 | 🔴 责任人离职停摆 | 原责任人高老师离职，建议岩冰主导 |
| 新加坡资助谈判 | 🟡 暂无实质 | 关系链接已建立，用户准备下周再约张真电话 |

### A.7 风险信号
- 🔴 **资方流失风险**：章方状态可能导致长期大额企业捐方断掉（张真原话）
- 🟡 **战略落地不定数**：数据资产战略需依赖业务设计能力
- 🟡 **心盛过渡期风险**：王强同时负责心灵魔法学院 + 心盛，带宽存疑

### A.8 未澄清矛盾点
- M3 章方走后资方对接谁接 → 等下周张真电话
- 王强带宽是否够 → 等下周张真电话

---

## 附录 B · 为爱黔行 DNA 样本 v0.1

### B.1 机构信息
- 名称：贵州省为爱黔行公益服务中心
- 登记：2019/12/24 贵州省民政厅
- 资质：2024 年获 **5A 级社会组织**
- 创始团队：**吴建林（吴老师）+ 詹瑶 —— 夫妇共同创始人**

### B.2 治理结构（关键 DNA）

| 人物 | 角色 | 状态 | 工作风格 |
|---|---|---|---|
| 吴建林（吴老师） | 理事长 / 创始人 | 在职 | **大开大合 / 插手太多 / 临时起意**。追求机构体量增长 → 接很多政府项目 → 导致机构现在问题 |
| 詹瑶 | 秘书长 / 创始人 | 4 月回归 | **管得细 / 信任度低 / 亲力亲为 / 不被理解**。**2025/8 起精神状态不好，休假到 3 月，4 月正式回归** |

**关键判断**：**夫妇共治 + 理念不合 + 一位刚从精神状态恢复回归** —— 决定我们陪伴的语气、节奏、提案路径。

### B.3 业务结构
| 业务线 | 占比 | 手法 | 关系 |
|---|---|---|---|
| 大山里的音乐课堂 | **50%** | 美育课程 + 教师赋能 + 教室改造 | 起步项目，**衍生美育系列** |
| 社区项目 | **30-40%** | **社工手法** | 接政府项目扩张 |
| 其他 | 余下 | — | — |

### B.4 战略定位
- **北极星**：「县域文化美育系统能力」（益语建议稿，对方无异议）
- **覆盖范围**：乡村 + 城乡结合部

### B.5 价值观系统（益语交付 v1）

5 条价值观（詹瑶同意，**需增加行动部分** —— 用户这周内补）：
1. 勇于担当，说到做到，为结果负责
2. 有话直说，当面说，好好说
3. 充分沟通，达成一致，坚决执行
4. 多鼓励、互信任、勤反思、共成长
5. 小步快跑，勇于试错，快速迭代

**状态**：v1 client_reviewed，等用户补行动篇 → 6 月工作坊正式发布。

### B.6 6 月工作坊设计（顾老师创新方案）

**原方案问题**：基层员工无全局思维 / 信息差大，内容抽象客户无法吸收。

**最终方案**：**全程用自研软件**开展工作坊 —— 预制客户基础信息+已知矛盾 → 现场小组讨论 → 软件+大模型输出矛盾原因分析 → 引导客户调整使命/价值观/流程。

**双重价值**：澄清问题 + 客户熟悉软件，会后可直接部署。

**切入点共识**：从客户**最突出的绩效矛盾**切入（不从使命愿景切入）—— 匹配吴老师对数字化落地的期待。

**注意事项**：
- 不硬推、不强调"AI 工作坊" → 先用豆包 → 觉得不好用再推荐自研
- 备案：软件不稳改为讲师演示 + 参会者用豆包

**软件待优化点**：「思考与研究/战略陪伴」板块功能单薄 → 用 GPT 模拟理想结果 → 逆向工程优化。

### B.7 关键人物（external_persons）

| 人物 | 别名 | 角色 | 状态 |
|---|---|---|---|
| 詹瑶 | "张瑶"(ASR err) / "詹老师齐"(ASR err) | 秘书长 / 共同创始人 | 4 月回归 |
| 吴建林 | 吴老师 | 理事长 / 共同创始人 | 在职 |
| 乐乐 | 同 | **益语智库**客户发展部负责人（非黔行） | 在职 |

### B.8 资助方关系
- **浙江敦和慈善基金会** —— ❌ 跟黔行**无关**，早期资料梳理错误 → 应剔除
- **杉树基金会丁杰 + 复旦副教授** —— 🟡 关系较弱，跟项目密切度不高

### B.9 主线推进真实状态

| 主线 | 状态 | 节点 |
|---|---|---|
| 三年战略咨询报告 V1.0 | ✅ 已交付（2026/1/27），无异议 | — |
| 第一次培训 | ✅ 已交付（2026/2/4-5） | — |
| 价值观系统 v1 | 🟡 待补行动篇 | 用户这周内补 |
| **6 月工作坊** | 🟢 设计中 | 取代原 5 月承诺的 2 天工作坊 |
| **6 月深度会谈** | 🟢 设计中 | 原 5 月承诺，合并进工作坊期 |
| 詹瑶硬盘资料 | ✅ 5/14 收到 | 用户这周读完反馈 |

### B.10 数据卫生事项 ⚠️
- **庆华** = AI 模拟角色，应 `is_simulated=1` + 删除
- 大山里的音乐课堂教室改造 3 个 task = 测试数据，应 `is_test_data=1`
- 整个为爱黔行任务模板里所有测试任务 = 测试数据

---

## 文档审阅指引

请用户重点审：

1. **§3 核心结构决策**：不新建 thread 表对吗？
2. **§4 字段升级清单**：哪些字段加多了？哪些缺了？
3. **§5 颗粒度规范**：5 种 thread_level 划分对吗？
4. **§7 Step 2 必做项**：澄清面板的 6 个能力 + KPI 评分系统对吗？
5. **§10 待决策点**：6 个决策点的建议是否接受？

审阅完成后，进入 **Step 1 工程实施**（3-4 周）。
