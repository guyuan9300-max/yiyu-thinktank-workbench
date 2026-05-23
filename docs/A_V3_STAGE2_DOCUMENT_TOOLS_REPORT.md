# A · V3 Stage 2 文档生成工具报告 (M2)

**时间**: 2026-05-24 03:15
**触发**: 顾源源 §M2 — 通用 documents.generate + contracts.draft + templates.generate

---

## 1 · 交付物

3 个 endpoint(backend/app/main.py):

| endpoint | 性质 | document_type |
|---|---|---|
| POST /api/v1/documents/generate | 通用 | 7 种 |
| POST /api/v1/contracts/draft | 兼容 | contract_draft |
| POST /api/v1/templates/generate | 兼容 | board_brief 等 |

---

## 2 · 7 种 document_type(参数化,不写死流程)

| document_type | 用途 | approval | external |
|---|---|---|---|
| contract_draft | 合同草稿 | true | true |
| board_brief | 理事会简版 | true | true |
| brand_proposal | 品牌建议 | true | true |
| meeting_pack | 会谈提纲 | false | false |
| action_list | 行动清单 | false | false |
| project_note | 项目说明 | false | false |
| review_material | 复盘材料 | false | false |

---

## 3 · 接口契约(全过 §M2 通过线 9 项)

| 通过线 | 实测 |
|---|---|
| documents.generate 可用 | ✅ |
| contracts.draft 兼容可用 | ✅ |
| templates.generate 兼容可用 | ✅ |
| 每次生成写 agent_run_log | ✅ (tool_name=documents.generate:{type}) |
| 每次生成支持 Idempotency-Key | ✅ (check + record) |
| 对外材料 approval_required | ✅ (3 种自动进 approval) |
| 不直接发送 | ✅ (status='draft') |
| 使用 ContextBuilder | ✅ (task_type 路由) |
| 输出附 evidence_summary | ✅ (15 字段) |

**9/9 通过线全过**

---

## 4 · 用户视角真测(顾源源补充 lens)

输入: POST /documents/generate {client_id: CFFC, document_type: board_brief, goal: 理事会汇报}

输出:
- markdown 真含 CFFC 真实数据(5月补充协议 / 王主任承诺 / 师资不足风险 / 学校配合度)
- "下一步建议" actionable("处理 20 个待澄清问题 / 补 10 个数据缺口")
- "待确认项" 真问具体问题
- 用户可直接改 30 秒拿来用

---

## 5 · 真测 db diff

```
approval_queue (document.publish): 0 → 2 (+2 from board_brief + contract_draft)
agent_run_log (documents.generate%): 0 → 2
其它业务表: Δ=0 (draft 不写)

同 Idempotency-Key 重发 → db Δ=0 ✅
```

---

## 6 · 接力

报告 docs/A_V3_STAGE2_DOCUMENT_TOOLS_REPORT.md + 桌面 38 号位.

B 复验时跑:
- documents.generate × 7 types
- 验 sections 真含真实数据
- 验 idempotency
- 验 approval gate
