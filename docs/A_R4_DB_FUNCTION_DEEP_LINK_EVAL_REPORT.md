# A · R4 数据中心—功能深度联动评估报告

**时间**: 2026-05-23 18:30
**口径**: V2.1 lab backend HTTP + V2.1 lab db sqlite3 实测(不接受 snapshot)
**触发**: 顾源源 5/23 R4 深度联动评估指令(读取 50 + 写入 50 双轴 100 分)
**测试方法**: A 不动代码,只读 db / 调 HTTP / 出诚实分数

---

## 1 · 总分

```
数据库—功能深度联动指数:  63 / 100   🟡 (差 7 到初步接通 70, 差 17 到 R4-P0 通过 80)
  · 读取深度指数:   33 / 50
  · 写入分析指数:   30 / 50

通过线对照:
  ≥70 初步接通        : 差 7
  ≥80 R4-P0 通过      : 差 17
  ≥90 真 dogfood      : 差 27
  ≥95 宣传核心能力     : 差 32
```

**核心根因**(下一节详)**: V2.1 lab db 缺 4 张 R3 关键表 schema**
- `file_identities` / `contract_structures` / `historical_reference_links` / `data_gaps`
- B 31a74d1 init schema 时只 init 11 张,漏了 R3-M1/M2/M4 的 4 张

---

## 2 · 读取深度评估表(5 个生成功能,33/50)

curl 实测 `POST /api/v1/clients/{id}/workspace/chat` 真返回:

| 功能 | evidence 类型数 | 引用合同 | 引用历史材料 | single_file | 评分 |
|---|---|---|---|---|---|
| 工作台问答(Q1 合同回指) | 5 | ❌(表无) | ❌(表无) | false ✅ | B |
| 工作台问答(Q2 权威预算) | 5 | ❌(表无) | ❌(表无) | false ✅ | B |
| 工作台问答(Q3 战略判断) | 5 | ❌(表无) | ❌(表无) | false ✅ | B |
| 战略陪伴 6 段叙事 | (bundle 加 5 R4 字段,prompt 没真用) | ❌ | ❌ | - | B |
| 模板填充 | (没接 ContextBuilder) | ❌ | ❌ | (可能 true) | C |

7 维度评分:
| 维度 | 满分 | 得分 | 说明 |
|---|---|---|---|
| 客户上下文绑定 | 5 | **5** | 全部带 client_id ✅ |
| 多源 evidence 覆盖 | 10 | **6** | 5 类(应 ≥8 类 含合同/文件/历史) |
| 关键资料召回 | 10 | **5** | contracts/files/historical 表全无 |
| 权威口径优先 | 8 | **4** | 没 contract_structures 无法用合同口径 |
| 不确定识别 | 7 | **6** | proposedClarifications 真返回 |
| 生成内容完整性 | 5 | **3** | LLM 输出质量 OK 但缺关键 evidence |
| 前端可见性 | 5 | **4** | evidence badge ✅,4 个新 UI 组件未挂头部 |
| **小计** | **50** | **33** | |

---

## 3 · 写入分析评估表(7 个入口,30/50)

sqlite3 实测 V2.1 lab db `~/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab/app.db`:

### 11 张关键表当前数据

| 表 | 计数 | 说明 |
|---|---|---|
| atomic_facts | **2048** | ✅ 主表健康(CFFC 913 / 日慈 722) |
| event_line_activities | **145** | ✅ 派生器实时跑 |
| commitments | **88** | ✅ |
| risk_signals | **43** | ✅ |
| clarification_records | **53** | ✅ |
| strategic_thought_insights | **42** | ✅ |
| agent_run_log | **18** | ✅(7/18 含 idempotency_key) |
| approval_queue | **12** | ✅(11 pending + 1 rejected) |
| external_evidence_cards | 0 | ⚠️ 有表但 0 数据 |
| ai_learned_rules | 0 | ⚠️ 有表但 0 数据 |
| **file_identities** | **(无表)** | 🔴 **R3-M1 表 schema 未 init** |
| **contract_structures** | **(无表)** | 🔴 **R3-M1 表 schema 未 init** |
| **historical_reference_links** | **(无表)** | 🔴 **R3-M2 表 schema 未 init** |
| **data_gaps** | **(无表)** | 🔴 **R3-M4 表 schema 未 init** |

### 7 个入口写入深度

| 入口 | 来源登记 | 类型识别 | 结构化抽取 | 历史关联 | 语义派生 | 缺口澄清 | 写后扩散 | 等级 |
|---|---|---|---|---|---|---|---|---|
| 工作台对话 | ✅ chat_messages | ⚠️ 不分类 | ❌ 不抽 | ❌ | ⚠️ broadcast | ❌ | ✅ | C |
| 智能文件导入 | ✅ v2_documents | ❌ 表无 | ⚠️ atomic_facts | ❌ 表无 | ✅ | ⚠️ | ✅ | C |
| 任务创建 | ✅ tasks | ❌ | ❌ | ❌ | ❌ ela 0 | ❌ | ⚠️ | C |
| 周复盘 | ✅ weekly_reviews | ❌ | ⚠️ 抽 tasks | ❌ | ⚠️ | ❌ | ⚠️ | C |
| 资讯情报 | ✅ intelligence_candidate_items | ⚠️ | ❌ | ❌ | ❌ EEC 0 | ❌ | ⚠️ | D |
| 成长方法卡 | ✅ handbook_entries | ❌ | ❌ | ❌ | ❌ ai_learned_rules 0 | ❌ | ❌ | D |
| 组织计划 | ⚠️ project_modules | ❌ | ❌ | ❌ | ❌ task 挂接 0 | ❌ | ❌ | D |
| ★ 会议纪要 endpoint | ✅ agent_run_log | ✅ MeetingMinuteProcessor | ✅ atomic_facts+5 | ⚠️ | ✅ ela+2/clar+2 | ✅ | ✅ | B+ |

8 维度评分:
| 维度 | 满分 | 得分 | 说明 |
|---|---|---|---|
| 来源登记 | 5 | **5** | source_registry + atomic_facts 强校验 ✅ |
| 信息类型识别 | 7 | **3** | file_identities 表无 → 无法识别文件类型 |
| 结构化抽取 | 8 | **5** | atomic_facts 抽 ✅,合同结构没抽(表无) |
| 历史材料关联 | 8 | **0** | historical_reference_links 表无 |
| 语义表派生 | 8 | **7** | 7 张语义表真有数据 |
| 缺口与澄清 | 6 | **3** | clarif 53 ✅,data_gaps 表无 |
| 写后扩散 | 4 | **3** | broadcast 接通 ✅ |
| 安全与隔离 | 4 | **4** | V2.5 R2-D 跨客户 0 leak 已验 ✅ |
| **小计** | **50** | **30** | |

---

## 4 · 双向闭环测试结果

### Step 1 · 写入(CFFC 会议纪要)

```
输入: '5/23 CFFC 季度复盘: 王主任明确新疆试点改为 1 所 (原 3 所).
       李丽担忧师资跟不上. 周明承诺 5/30 给财务可行性. 下季度想扩展内蒙.'

调 POST /meeting-minutes/process Idempotency-Key=deep-eval-loop-001:
  ✅ facts+5
  ✅ risks+2
  ✅ commits+1
  ✅ clarif+2
  ✅ task+1 (进 approval_queue)
  ✅ ela+2
```

### Step 2 · 数据中心实际新增

```
sqlite3 实测:
  CFFC atomic_facts:  913 → 918 (+5 ✅)
  approval_queue:     11 → 12 (+1 ✅)
  agent_run_log:      已含 idempotency_key='deep-eval-loop-001'
  本次 evidence_text 含 run_id 的 facts: 5 ✅
```

### Step 3 · 工作台问答读取

```
问: '新疆试点最新决定是什么? 是几所学校? 培训计划是什么? 责任人是谁?'
返回:
  evidenceTypes: 5 类
  usedTables: 6 张
  proposedClarifications: 多条
```

**双向闭环 PASS** — 写入即读到 ✅

---

## 5 · single_file_only 风险报告

实测无 single_file_only 触发(全部 false)。

但**功能维度**仍有单一来源风险:
- 模板填充:不调 ContextBuilder
- 粘贴生成文档:只读当前粘贴文本
- 任务智能解析:只读 tasks
- 周复盘:不调 historical_resolver

---

## 6 · 数据缺口与澄清报告

V2.1 lab db 缺口:

| 缺口 | 影响 | 修复 |
|---|---|---|
| `file_identities` 表无 schema | 智能文件导入不能写文件身份 | R3-M1 ensure_file_identity_schema 没在 init script 跑 |
| `contract_structures` 表无 | 合同结构无法持久化 | 同上 |
| `historical_reference_links` 表无 | 复盘历史关联完全失效 | R3-M2 ensure_resolver_schema 没在 init |
| `data_gaps` 表无 | data_gap_compensator 不能写 | R3-M4 同上 |
| `ai_learned_rules` 0 | 方法卡反哺生成 0 | 服务未接 |

clarification_records 真生成 53 条 ✅,但 data_gaps 完全无表 ❌。

---

## 7 · 用户可感知结果(用户语言)

```
用户问"上次合同里那个 5 月补充协议":
  ❌ 系统现在找不到 (因为 historical_reference_links 表不存在)

用户问"这个项目当前预算":
  ⚠️ 系统能答数字, 但不能引用具体合同
  (contract_structures 表不存在, 只能引 atomic_facts 旧记录)

用户上传 20 个文件:
  ❌ 系统无法识别"这是合同 / 那是方案 / 这是外部参考"
  (file_identities 表不存在)

用户开完会:
  ✅ 调 POST /meeting-minutes/process 真兑现 (8 步全过)
  ✅ atomic_facts/risks/commits/clarif/task/ela 真长
  ✅ Idempotency-Key 真生效

用户在工作台问 AI:
  ✅ 收到 evidence 摘要 (5 类 / 5 表 / single_file_only=false)
  ✅ 看到 proposedClarifications 5 条
  ⚠️ 但 4 个新 badge (待澄清 / 待审批 / 文件身份 / 合同结构卡) 还没挂客户工作台头部
```

---

## 8 · 下一步修复优先级

### 🔴 P0(顾源源"先修分数最低两项"原则)

| # | 缺口 | 当前分 | 修复路径 | 工作量 |
|---|---|---|---|---|
| 1 | **历史材料关联 0/8** | 0 | 在 init_v21_lab_schema.py 加 R3-M1/M2/M4 4 张表的 CREATE TABLE | B 30 min |
| 2 | **信息类型识别 3/7** | 3 | 同上 + 再跑一次 smart_import commit 让 file_identities 写入 | A 1h |

修完两项后预测:
```
33 (读) + 30 (写) → 33 (读) + (30+4+8) (写) = 75 (差 5 到 80)
```

### 🟡 P1(P0 修完后再做)

| # | 缺口 | 修法 |
|---|---|---|
| 3 | narrative prompt 真用 R4 字段 (战略陪伴 B→A) | 改 narrative_generator.py prompt |
| 4 | 4 badge 挂客户工作台头部 + 文件列表 + 战略陪伴 | App.tsx 挂位置 |
| 5 | 模板填充走 ContextBuilder | 改 template_fill.py |
| 6 | 任务/周复盘/情报/方法卡/计划 反向入库 | 5 件 P1-1~P1-4 |

---

## 9 · 跟 R3 88.8 / R2 64 / SELF_CHECK 41 对比

```
R3 88.8 (snapshot 跑分, 已加免责)         → 实验室分数, 不算
R2 64 + 6/6 硬门槛 (V2.1 lab db, B 真跑) → ✅ R2 真过
SELF_CHECK 41/100 14 功能基线 (本次前)     → 接入率维度
R4 深度联动 63/100 (本次, 双轴)           → 读写深度维度

→ R4 深度比 SELF_CHECK 高一些, 因为评分维度更看真能力 vs 真使用.
→ 但仍差 17 分到 R4-P0 通过线 80.
→ 修 P0 两项 (4 张表 schema) 后预测 75, 仍差 5.
```

---

## 10 · 评估自我审计

**做对的**:
- 用 V2.1 lab db sqlite3 实测, 不接受 snapshot
- curl 真调 V2.1 backend 47831
- 双向闭环跑过 (会议纪要 → 工作台问答)
- 14 张表数据实证

**没做的**:
- 没跑 5 个生成功能全部(战略陪伴 / 模板 / 粘贴 / 周复盘 / 情报写为提案 没 curl, 只评级)
- 没人工审 LLM 输出内容(只看 evidence_types 字段)
- 没跑跨客户隔离 (V2.5 R2-D 已验过, 引用)

**结论**:
- **R4 深度联动 63/100** — 不够好, 但诚实
- 顾源源 "先测后修" 原则: 修 2 项就能上 75, 还差 5 才到通过线
- 真正的瓶颈是 **R3 新表 schema 未在 V2.1 lab db init** — B 替我做最高效

---

## 11 · 留给顾源源和 B

### 给顾源源
- 现在分数 63/100, 不到 R4-P0 通过线
- 修 2 项 (P0-1+P0-2) 可上 75 (B 30min + A 1h)
- 报告放产品手册 17 号位

### 给 B(inbox-A 等 B 读)
- A 请你扩 `scripts/init_v21_lab_schema.py` 加 4 张表:
  ```
  file_identities
  contract_structures
  historical_reference_links
  data_gaps
  ```
- 表 schema 在我服务文件里: file_identity_classifier.py / historical_material_resolver.py / data_gap_compensator.py 的 `ensure_*_schema` 函数
- B 加完跑 `npm run db:init:lab` → 11 → 15 张表
- 然后 A 再跑一次本评估,预测分数 75
