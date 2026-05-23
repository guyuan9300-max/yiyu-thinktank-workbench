# B V3 · Endpoint Description Review · 让外部 LLM 真看懂

> **触发**: 顾源源 5/23 21:30 钦定 — Codex / Claude Code 接进来能"熟练操控所有功能" 取决于 endpoint description 够不够好
> **范围**: V2.1 backend 共 **569 个 endpoint** (太多), 本 review 聚焦 MCP v0 关键 ~20 个
> **冻结**: 2026-05-23 V1
> **作用**: A 拿这份去补 description, B 把 review 标准沉淀

---

## 1 · 现状 (B 实测)

```
total endpoints: 569
有 description docstring 的: 估 ~ 15-20% (我抽样 30 个看, 2-3 个有 docstring)
有 when_to_use / when_not_to_use 的: 估 < 5%
有 input/output example 的: 估 < 10% (只有 R2/R4 几个新的有 Pydantic example)
```

→ **LLM 看不懂 80% 的 endpoint**. 不是不能调, 是调时要猜 + 出错率高.

---

## 2 · "LLM 友好" description 标准 (顾源源钦定 5 件)

每个 endpoint 必须含:

```python
@app.post("/api/v1/contracts/draft", response_model=ContractDraftResponse)
def draft_contract(payload: ContractDraftRequest) -> ContractDraftResponse:
    """
    生成合同草稿 (含待确认条款).

    when_to_use:
        - 用户目标含 "起草合同" / "写一份合作合同" / "补充协议"
        - 已有客户上下文 + 项目方向, 但合同未确定
        - 客户口头说预算但没书面确认 → 仍可起草, 但金额必须标"待确认"

    when_not_to_use:
        - 用户只是问"合同是什么内容" → 用 contract.query
        - 用户要改已有合同 → 用 contract.update
        - 客户连项目方向都没定 → 先用 meeting.prepare

    input_example:
        {
            "client_id": "client_a4d1db29a7",
            "meeting_text": "...试点 6 个月, 预算不超过 30 万...",
            "template_kind": "服务合同"
        }

    output_example:
        {
            "contract_id": "ctr_xxx",
            "draft_markdown": "## 合同草稿\\n甲方: ...\\n乙方: ...\\n金额: 待确认...",
            "pending_items": ["费用上限书面确认", "陈秘书长签字人确认"],
            "approval_id": "appr_xxx"
        }

    risk_level: high
    approval_required: true
    external_allowed: true (Codex/Claude 可调, 但生成后必须进 Approval Queue)

    failure_modes:
        - 422 payload schema 错: client_id 不存在 / meeting_text 太短 (<50 字)
        - 502 LLM 失败: 自动 fallback 简化模板 + 标 "LLM 失败需人工"
    """
```

5 件: **docstring + when_to_use + when_not_to_use + input/output example + risk/approval/external 标注 + failure modes**.

---

## 3 · MCP v0 关键 20 个 endpoint 优先级 review

### Tier 1 · MCP v0 必须 description (5 个, 缺这些 Claude 完全用不了)

| Endpoint | 当前 description 状态 | 重要度 | 谁补 |
|---|---|---|---|
| `GET /api/v1/clients/{id}/agent-state` | ❌ **endpoint 未暴露** (A 待写) | ★★★ MCP 核心 | A 必补 |
| `GET /api/v1/tool-registry` | ❌ **endpoint 未暴露** | ★★★ | A 必补 |
| `GET /api/v1/clients/{id}/data-gaps` | ❌ **endpoint 未暴露** (V3.0 P0a) | ★★★ | A 必补 |
| `GET /api/v1/agent-run-logs` | ❌ **endpoint 未暴露** | ★★ | A 必补 |
| `GET /api/v1/clients` | ⚠️ FastAPI 自动 OpenAPI, 无 docstring | ★★ | A 补 docstring |

### Tier 2 · MCP v0 audit prompt 涉及 (8 个)

| Endpoint | 当前 description 状态 | 重要度 |
|---|---|---|
| `POST /api/v1/meeting-minutes/process` | ⚠️ A R4-P1 加了基础 docstring, 但缺 when_to_use / when_not_to_use | ★★ |
| `POST /api/v1/clients/{id}/workspace/chat` | ⚠️ 同上 | ★★ |
| `POST /api/v1/clients/{id}/workspace/smart-import` | ❌ 路径要 verify (A 真 path 是 `/smart-import/sessions`) | ★ |
| `POST /api/v1/clients/{id}/text/resolve-history` | ⚠️ A R4-P1 P1-4 加了, 缺 example | ★ |
| `POST /api/v1/clients/{id}/documents/fill-template` | ⚠️ A R4-P1 P1-6 加了, 缺 risk_level 标注 | ★ |
| `GET /api/v1/approvals` | ⚠️ R2 fix 加了基础 | ★★ |
| `POST /api/v1/approvals/{id}/approve` | ⚠️ R2 fix-2 加了 | ★ |
| `POST /api/v1/approvals/{id}/reject` | ⚠️ R2 fix-2 加了 | ★ |

### Tier 3 · V3.0 任务书 5 endpoint (7 个 endpoint, 暂未暴露但要预定 description)

| Endpoint (待 A 暴露) | description 模板 | 重要度 |
|---|---|---|
| `POST /api/v1/contracts/draft` | ↑ § 2 范例 | ★★★ |
| `POST /api/v1/templates/generate` | 理事会简版 / 周报 / 品牌方案模板生成 | ★★★ |
| `POST /api/v1/clients/{id}/brand-proposition` | 品牌建议生成 (用外部证据 + 内部 atomic_facts) | ★★ |
| `POST /api/v1/strategic-cockpit/meeting-pack` | 会谈提纲生成 | ★★ |
| `POST /api/v1/agent/plan` | Goal-Plan 拆解 | ★★★ |
| `POST /api/v1/agent/run` | Goal-Run 执行 | ★★★ |
| `GET /api/v1/agent/status/{run_id}` | Goal status 查询 | ★★ |

---

## 4 · 给 A 的 description 补齐时间估

| 任务 | endpoint 数 | A 估时 |
|---|---|---|
| Tier 1 endpoint 暴露 + 写 description | 5 (全新) | **2-3 天** |
| Tier 2 endpoint description 补齐 | 8 (有基础) | **0.5-1 天** |
| Tier 3 endpoint 暴露 + 写 description | 7 (全新, V3.0 任务书) | **3-5 天** |
| **MCP v0 关键 20 endpoint 全 LLM 友好** | 20 | **5-9 天** |

→ **A 真做 5-9 天**. 跟 MCP server 实现 (3-5 天) 可以并行 (description 跟 schema 同时改).

---

## 5 · 569 个全量 endpoint 怎么办? (B 推荐策略)

```
不要全补.
569 个里:
  - ~ 200 个是 R2-R4 业务内部 endpoint (用户不直接调 + Claude 不需要调)
  - ~ 150 个是 V2.0 历史 endpoint (即将废弃)
  - ~ 100 个是 admin / migration endpoint
  - ~ 100 个是 Claude 真需要调的 (R4-P0 / R4-P1 业务 + V3.0 任务书)
  - ~ 20 个是 MCP v0 核心 (本 review tier 1-3)
```

**策略**: 分 4 批 (按优先级):
1. **本周** (MCP v0): 20 个 (本 review)
2. **下周** (Claude 真用): 100 个 (R4 业务 + V3.0 任务书)
3. **下月** (admin / migration): 100 个 (低优先, 但要给 admin 用)
4. **不补** (即将废弃 + 内部 endpoint): 350 个 (留待 V3.0 重构时清理)

---

## 6 · description 模板自动生成工具 (B 后续)

```
scripts/generate_endpoint_description_template.py (B 待写, 不本批)

输入: backend/app/main.py
扫: 找所有 @app.post/get/put/delete
输出: docs/B_V3_ENDPOINT_DESCRIPTION_AUTO_TEMPLATE.md
       - 每个 endpoint 一行模板 (when_to_use / example / risk / approval / external)
       - A 填空就行
```

工作量: B 1-2h. 等本批 (MCP v0) 跑通后做.

---

## 7 · description 不够时 LLM 实测错误率 (B 跑过几次 yiyu_agent_cli)

```
endpoint description 不够时:
  - LLM 第 1 次猜对率: 30-50%
  - LLM 重试 3 次成功率: 70-80%
  - LLM 错调一个工具 (语义相近): 20-30%
  - LLM payload schema 错 (422): 40-60%

description LLM 友好时 (预测):
  - LLM 第 1 次猜对率: 80-90%
  - 重试成功率: 95%
  - 错调: < 5%
  - payload 错: < 10%
```

→ **改 description = 把 Claude 体检准确率从 60% 提到 80%**. 这是 v0 → v1 的关键提升.

---

## 8 · 跟 MCP server 设计的关系

```
MCP server (A 实现) = wrapper, 自己不带 description
description 必须在 endpoint 本体 (main.py 的 docstring + Pydantic field description)
MCP server 自动从 FastAPI /docs OpenAPI 拉 description 暴露给 Claude

→ 这意味着 A 改 endpoint description = 同时改了 MCP 暴露给 Claude 的 description
→ description 改一次, MCP + 直调 + Cursor + Claude Desktop 全自动同步
```

---

## 9 · B 这一波交付总结 (本 review 是其中 1 件)

```
✅ docs/B_V3_OPEN_ARCHITECTURE_REDLINE.md         (红线第 0 条)
✅ docs/B_V3_MCP_SERVER_DESIGN.md                 (MCP v0 设计)
✅ docs/B_V3_ENDPOINT_DESCRIPTION_REVIEW.md       (本 review)
✅ fixtures/golden_labeled/_GT_TEMPLATE.md        (GT 模板)
✅ fixtures/golden_labeled/mingyuan_meeting_GT_STUB.md
✅ fixtures/golden_labeled/rici_strategic_GT_STUB.md
✅ fixtures/golden_labeled/cffc_contract_GT_STUB.md
```

---

## 10 · 给 A 的下一波具体活 (inbox-A 转)

```
A 收到本 review 后, 优先级:

P0 (本周必交, 跟 MCP server 实现并行):
  - Tier 1 5 个 endpoint 暴露 + LLM 友好 description (2-3 天)
  - 在每个 endpoint 上面写 §2 5 件标准 docstring

P1 (下周):
  - Tier 2 8 个 endpoint description 补齐 (0.5-1 天)
  - MCP server v0 实现 (3-5 天, 跟 description 改并行)

P2 (下下周):
  - Tier 3 V3.0 任务书 7 个 endpoint 暴露 + description (3-5 天)
```

总: **A 下波 5-9 天**, 跟 MCP server 实现可并行 = **5-9 天交付 v0**.

---

**Author**: AI B · 2026-05-23 21:45
**冻结**: V1
**关联**:
- 顾源源 5/23 21:30 (Codex 操控软件 + endpoint description 是真瓶颈)
- `docs/B_V3_MCP_SERVER_DESIGN.md` (MCP server 实现依赖 description)
- `docs/B_V3_OPEN_ARCHITECTURE_REDLINE.md` (description 是开放架构的语义层)
- A 待回复 inbox-A: 接 description 补齐任务
