# R4-P0 · 公司大脑用户可见化 · 评估范围 (顾源源 5/23 钦定)

> **触发**: 顾源源 5/23 范式转移 — 不再评估"代码接了什么", 评估"用户做真实动作后看到了什么"
> **B 落档**: 2026-05-23 11:35
> **作用**: 把顾源源 8/9 段直接钦定的方案转成 B 可执行的评估脚本设计

---

## 1 · 北极星 + 通过线

```
北极星: 用户打开软件以后, 是否真的感觉系统更懂客户/更会找证据/
        更会提醒不确定/更会给下一步建议.

通过线: 用户可感知得分 ≥ 80 / 100

3 层评估:
  L1 API contract — 公司大脑字段是否真返回 (B 自动测)
  L2 V2.1 lab db — 真实写入是否发生 (B 自动测)
  L3 前端可见   — 用户界面是否真显示 (人工 + 截图)
```

**L3 不能由 API 替代** — 顾源源 5/23 严卡: "必须标注'需人工确认'或提供可截图/可界面验证路径".

---

## 2 · 6 维度 100 分评分 (顾源源六钦定)

| 维度 | 满分 | L1 (API) | L2 (DB) | L3 (UI) |
|---|---|---|---|---|
| 1 工作台问答深度 | 20 | 8 | 6 | 6 |
| 2 文件导入理解 | 20 | 8 | 6 | 6 |
| 3 战略陪伴解释 | 20 | 8 | 6 | 6 |
| 4 evidence 前端可见 | 15 | 5 | — | 10 |
| 5 待澄清/待审批可处理 | 15 | 5 | 5 | 5 |
| 6 单文件风险控制 | 10 | 5 | 5 | — |
| **总** | **100** | **39 (B 自动)** | **28 (B 自动)** | **33 (人工)** |

→ B 自动可测 67 分 (L1 + L2), 33 分 (L3) 需顾源源人工 verify 截图.

---

## 3 · 10 硬门槛 (R2 沿用 5 + R4-P0 新 5)

```
R2 沿用 (顾源源 5/23 11:30 钦定 "不绕过 R2"):
H1  POST /meeting-minutes/process HTTP 200 + 真处理
H2  GET /approvals 三件套 HTTP 200
H3  clarification_records V2.1 lab db 真涨 ≥ 1
H4  approval_queue V2.1 lab db 真涨 ≥ 1
H5  agent_run_log V2.1 lab db 真涨 ≥ 1 + idempotency_key 真持久化

R4-P0 新 (顾源源 5/23 11:00 钦定 "5 项 P0"):
H6  workspace/chat response 含 companyBrainSummary 字段
H7  workspace/chat response 含 evidence_types ≥ 3 (10 真问题 ≥9/10)
H8  smart_import response 含 file_identity + contract_structure
H9  strategic narrative 引用 contract / historical / data_gap (至少 2 类)
H10 P0 功能 single_file_only ≤ 10% (10 题 ≤1 题)
```

→ B 自动可测 H1-H10 全部 (sqlite3 + curl).

---

## 4 · 7 项测试 (顾源源九钦定)

### 测试 1 · 工作台问答 10 真实问题 (D1 20 分)

10 题 (顾源源 3 段钦定):
1. 这个客户当前最重要的项目是什么?
2. 最新预算是多少? 旧版本是多少?
3. 5 月补充协议是哪一份?
4. 这份协议是谁和谁签的?
5. 合同里约定了哪些交付?
6. 最近复盘提到的合作和哪份合同有关?
7. 哪些内容只有用户口述?
8. 当前最大的风险是什么?
9. 哪些问题需要问客户确认?
10. 下一步最应该做什么?

每题记录:
| 字段 | L | 来源 |
|---|---|---|
| 用户问题 | - | 测试输入 |
| HTTP status | L1 | curl status |
| response.companyBrainSummary | L1 | API response |
| evidence_types_count | L1 | response.evidence_types.length |
| 引用源 count | L1 | response.citations.length |
| single_file_only | L1 | response.single_file_only |
| proposed_clarifications | L1 | response.proposed_clarifications |
| 答案文本 | L1 | response.answer |
| 用户能否看懂 (1-5 主观) | L3 | 人工 |

通过条件 (顾源源 P0-2):
- ≥ 9/10 题: evidence_types ≥ 3 + 引用源 ≥ 2 + single_file_only=false + 遇到不确定生成澄清

### 测试 2 · 20 文件导入 (D2 20 分)

输入: 20 个真实测试文件 (会议纪要/合同/方案/会议录音等)
endpoint: `POST /api/v1/clients/{id}/workspace/smart-import` 或 `/files/identify` (顾源源 P0-3)

每文件记录:
| 字段 | L | 来源 |
|---|---|---|
| 文件名 | - | 测试输入 |
| file_identity (type/role) | L1 | response.file_identity |
| contract_structure (合同时只) | L1 | response.contract_structure |
| confidence | L1 | response.confidence |
| 进入澄清 (低置信) | L2 | clarification_records 表 |
| 前端 badge 显示 | L3 | 人工 |
| 合同结构卡片显示 | L3 | 人工 |

通过条件:
- 文件类型识别 ≥ 95% (≥19/20)
- 文件角色识别 ≥ 95% (≥19/20)
- 合同结构解析率 100%
- 低置信文件 100% 进入澄清
- 前端 badge + 合同结构卡 100% 可见 (L3 人工)

### 测试 3 · 战略陪伴 6 段叙事 (D3 20 分)

endpoint: `GET /api/v1/clients/{id}/strategic-cockpit/narrative` 或 `POST .../re-understand`

每段叙事 6 段 (顾源源产品手册钦定: essence/cooperation/business_intro/people/timeline/next_steps):
| 字段 | L | 来源 |
|---|---|---|
| 段名 | - | API |
| 段文本 | L1 | API response |
| evidence ≥ 1 个 | L1 | response.evidence_refs |
| 引用合同 | L1 | response.uses.contracts |
| 引用历史材料 | L1 | response.uses.historical_links |
| 引用 data_gaps | L1 | response.uses.data_gaps |
| 低把握度标记 | L1 | response.low_confidence |
| 段落 evidence 标签前端显示 | L3 | 人工 |

通过条件 (顾源源 P0-4):
- 最近变化 ≥ 3 条 (L1)
- 待澄清 ≥ 3 条 (L1)
- 每段叙事至少 1 个 evidence (L1)
- 低把握度段落可见 (L3)
- 合同/历史材料/data gap 至少出现 2 类 (L1)

### 测试 4 · evidence 摘要可见 (D4 15 分)

每个 workspace/chat 回答 response 必须含:
```json
{
  "companyBrainSummary": {
    "facts_count": 8,
    "contracts_count": 2,
    "meetings_count": 1,
    "reviews_count": 1,
    "risks_count": 2,
    "clarifications_count": 1
  }
}
```

L1 自动测: response 字段存在 + 数字 ≥ 0
L3 人工测: 前端 AI 回答下方真显示这个 summary box

### 测试 5 · 待澄清 + 待审批徽章 (D5 15 分)

L1 自动测:
- `GET /api/v1/clients/{id}/clarifications?status=pending` count ≥ 0
- `GET /api/v1/approvals?client_id={id}&status=pending` count ≥ 0

L2 自动测:
- V2.1 lab db `clarification_records WHERE status='pending'` count
- V2.1 lab db `approval_queue WHERE status='pending'` count

L3 人工测:
- 客户页右上角 "待澄清 N / 待审批 M" 徽章真显示
- 用户能点击徽章进入处理页

通过条件:
- 100% 任务草稿进入 approval_queue (L1+L2)
- 用户可点击查看来源 (L3)

### 测试 6 · single_file_only 风险 (D6 10 分)

每个 workspace/chat 回答 response 含 `single_file_only: bool`.

L1 自动测: 10 题 + 模板填充 + 粘贴生成 测一遍
| 功能 | 目标 |
|---|---|
| 工作台问答 single_file_only | ≤ 10% |
| 战略陪伴 single_file_only | 0% |
| 模板填充 single_file_only | ≤ 10% |
| 粘贴生成 single_file_only | ≤ 20% |

若 single_file_only=true 比例超标, **列出哪个功能仍在旧通道**.

### 测试 7 · R2 5 硬门槛沿用

每个测试客户跑一次 R2 (meeting-minutes/process), 验证:
- H1 endpoint HTTP 200 ✅
- H2 approvals 三件套 HTTP 200 ✅
- H3 clarification_records +1 ✅
- H4 approval_queue +1 ✅
- H5 agent_run_log +1 + idempotency_key 真持久化 ✅

→ 复用现有 `scripts/run_v25_r2_meeting_minute.py` 框架.

---

## 5 · 报告主表 (顾源源 5/23 11:30 钦定 5 问)

报告 `docs/V2_7_R4_P0_USER_VISIBLE_EVAL_REPORT.md` 主表必须回答:

| 问题 | L1 | L2 | L3 | 综合 |
|---|---|---|---|---|
| 1 用户问问题后, 是否看到多源 evidence? | evidence_types ≥3? | facts/contracts 真写入? | UI 摘要框可见? | ✅/⚠️/❌ |
| 2 用户导入文件后, 是否看到文件身份和合同结构? | response.file_identity + contract_structure? | file_identities + contract_structures 表? | UI badge + 卡片可见? | ✅/⚠️/❌ |
| 3 用户看战略陪伴时, 是否看到合同/历史材料/data gaps? | narrative.uses.contracts/historical_links/data_gaps? | 表数据真存在? | 段落 evidence 标签可见? | ✅/⚠️/❌ |
| 4 用户是否看到待澄清和待审批? | endpoint count > 0? | clarification + approval 表 pending? | 客户页徽章可见? | ✅/⚠️/❌ |
| 5 是否还有 single_file_only 风险? | response.single_file_only 比例? | (n/a) | UI 标注真值? | ✅/⚠️/❌ |

---

## 6 · 报告输出格式

```
docs/V2_7_R4_P0_USER_VISIBLE_EVAL_REPORT_<timestamp>.md   (主报告, 含 L3 截图清单)
docs/V2_7_R4_P0_USER_VISIBLE_EVAL_REPORT_<timestamp>.json (机器可读)
docs/screenshots/r4_p0/<timestamp>/README.md             (L3 人工截图清单 + verify 模板)
docs/screenshots/r4_p0/<timestamp>/*.png                 (顾源源截图, 人工)
```

---

## 7 · npm 命令

```
npm run eval:r4:p0:user-visible
  = python3 scripts/run_r4_p0_user_visible_eval.py --clients 日慈基金会,CFFC

npm run eval:r4:p0:check-only
  = python3 scripts/run_r4_p0_user_visible_eval.py --clients 日慈基金会,CFFC --check-only
    (只跑 L1 + L2, skip L3 截图)
```

---

## 8 · R3 88.8 重测处置 (顾源源接受)

R3 重测**暂停**. R4-P0 6 维度跟 R3 8 维度部分重合, 但**视角不同**:
- R3: 服务层能力指数 (后端干了啥)
- R4-P0: 用户感知层 (用户看到啥)

R4-P0 通过 ≥80 = V2.1 RC 真合格证明 (Release Candidate 真过).

R3 88.8 不再追求重测 — 视角已转.

---

## 9 · A 的 5 项 P0 跟 B 的 7 项测试映射

| A P0 | 顾源源描述 | B 测试 | 通过条件 |
|---|---|---|---|
| P0-1 CompanyBrainContextBuilder | 统一上下文入口 | 测 7 项都依赖 | 5 task_type 支持 |
| P0-2 workspace/chat 接公司大脑 | response 扩字段 | 测试 1 (10 问) | ≥9/10 满足 evidence ≥3 + 引用 ≥2 + 不 single_file |
| P0-3 smart_import 接文件身份+合同 | response 扩 file_identity | 测试 2 (20 文件) | type 95% + role 95% + 合同 100% |
| P0-4 strategic narrative 扩 | 引入 contract/historical/data_gap | 测试 3 (6 段) | 每段 ≥1 evidence + 至少 2 类来源 |
| P0-5 前端 evidence/澄清/审批可见 | UI 显示 | 测试 4/5 + L3 截图 | UI 100% 可见 (人工) |

---

**Author**: AI B · 2026-05-23 11:35
**关联**:
- 顾源源 8/9 段钦定 R4-P0 (本对话)
- 桌面 14 V2.1 RC R2 评估 (待写 R4-P0 接续版)
- inbox-A 第一条 (B → A 转达)
- `scripts/run_r4_p0_user_visible_eval.py` (B 下一步写)
