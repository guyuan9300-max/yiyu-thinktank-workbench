# A · V3 Final Test 支撑状态报告 (M0 冻结版本)

**时间**: 2026-05-24 02:30
**触发**: 顾源源 §A 线程 V3 最终验收支撑 §M0 — 冻结当前 P0 修复版本
**目标**: B 可基于本文档稳定复验,不再因为环境不清导致测试混乱
**口径**: V2.1 lab backend HTTP 真测 + sqlite3 实测

---

## 1 · 当前 commit

```
git log --oneline -3:
  9878acf [B] feat(v3 mcp-v0 round2): 第 2 轮客观评估 96/100 ✅
  80e3340 [A] C 审计 P0 全修复 (57 → 75, +18) ★ 本份基线
  52f30e2 [B] feat(v3 mcp-simulator + first-audit): 第 1 轮真体检

A 本份冻结版本: 80e3340
B 第 2 轮 simulator: 9878acf (基于 A 80e3340 跑)
```

---

## 2 · backend 启动方式

```bash
# V2.1 lab backend 已在运行 (Electron 内嵌, PID 53863):
/Users/guyuanyuan/Library/Application\ Support/YiyuThinkTankWorkbench2_V21Lab/runtime/backend-venv/bin/python \
  -m uvicorn app.main:app \
  --host 127.0.0.1 \
  --port 47831 \
  --reload \
  --reload-dir /Users/guyuanyuan/openclaw/workspace/V2.1/backend/app \
  --reload-delay 2

# B 复验时不需手动启动 - 已在运行
# 端口: 47831
# Host: 127.0.0.1
# Reload: 真开 (改 backend/app/*.py 自动 reload)

# 若需手动重启 (Electron 重启):
#   1. ps aux | grep uvicorn.*47831 → kill PID
#   2. Electron app 会自动重新拉起 backend
```

---

## 3 · V2.1 lab db 路径

```
/Users/guyuanyuan/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab/app.db

大小: 281 MB
最后修改: 2026-05-23 23:21
重要: B 务必读这一份, 不是 cloud_backend 或 dogfood_real_2025
```

---

## 4 · 测试客户 ID

```
client_a4d1db29a7  CFFC          主测客户 (2 合同 / 3 文件 / 10 historical / 16 commitments / 18 risks / 20 data_gaps)
client_284afd836e  日慈基金会      副测客户 (有数据)
client_53d82aa249  益语智库        内部客户
client_bda0f1d379  云南儿童资助研究  其它
client_30a392788c  顾源源文章       其它

测试推荐顺序: CFFC → 日慈 → 益语智库
跨客户隔离测试: 用 nonexistent_xxx → 期望 404
```

---

## 5 · Tool Registry endpoint

```bash
curl http://127.0.0.1:47831/api/v1/tool-registry
→ HTTP 200, 真返 20 工具完整 schema
  (17 available + 2 missing blocked_by_A + 1 feishu.tasks.push 新加 C P0-4)

可选 query:
  ?status_filter=available|partial|missing
  ?risk_level=low|medium|high
```

---

## 6 · Agent State endpoint

```bash
# Client 级
curl http://127.0.0.1:47831/api/v1/clients/{client_id}/agent-state
→ HTTP 200, 24 顶层字段 (B 实测确认)

# Project 级 (event_line 维度)
curl http://127.0.0.1:47831/api/v1/projects/{project_id}/agent-state
→ HTTP 200

期望字段 (14 必返):
  client_profile / active_projects / latest_events / file_identities /
  contract_structures / historical_reference_links / commitments /
  risk_signals / clarifications / approval_queue / data_gaps /
  agent_run_logs / recommended_next_actions / evidence_summary

Header (可选, 但建议传):
  X-Actor-Type: external_ai_agent | human | system
  X-Actor-Id: <agent 标识>
```

---

## 7 · Data Gaps endpoint

```bash
# Query
curl http://127.0.0.1:47831/api/v1/clients/{client_id}/data-gaps?status_filter=open&severity=high&limit=10
→ HTTP 200, schema_version=v3_m3_full_fields, 10 字段全命中

# Compensate (触发补证 pipeline)
curl -X POST http://127.0.0.1:47831/api/v1/clients/{client_id}/data-gaps/compensate \
  -H "Idempotency-Key: <unique>" \
  -H "X-Actor-Type: external_ai_agent"
→ HTTP 200, 真触发 detect + harvest, 写 data_gaps + external_evidence_cards + agent_run_log

每个 gap 真带:
  gap_id / gap_type / description / missing_evidence / related_facts /
  related_files / suggested_tools / suggested_clarification /
  priority / approval_required
```

---

## 8 · Agent Run Logs endpoint

```bash
# 列表
curl http://127.0.0.1:47831/api/v1/agent-run-logs?client_id={id}&actor_type=external_ai_agent&limit=20
→ HTTP 200, items 含 tool_name/actor/status/duration_ms/idempotency_key

# 单条
curl http://127.0.0.1:47831/api/v1/agent-run-logs/{run_id}
→ HTTP 200, 完整 input_json/output_json/error_message
```

---

## 9 · Approval Queue endpoint

```bash
# 列待审批
curl http://127.0.0.1:47831/api/v1/approvals?client_id={id}&limit=20
→ HTTP 200, list of pending approvals

# 真审批 (用户决定 / agent 不能 self-approve)
curl -X POST http://127.0.0.1:47831/api/v1/approvals/{approval_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"decided_by": "human:user_name", "note": "<reason>"}'
→ HTTP 200, status=approved

curl -X POST http://127.0.0.1:47831/api/v1/approvals/{approval_id}/reject \
  -H "Content-Type: application/json" \
  -d '{"decided_by": "human:user_name", "note": "<reason>"}'
→ HTTP 200, status=rejected

# 通用 decide
curl -X POST http://127.0.0.1:47831/api/v1/approvals/decide \
  -H "Content-Type: application/json" \
  -d '{"approval_id": "<id>", "decision": "approved|rejected", "decided_by": "...", "note": "..."}'
→ HTTP 200
```

---

## 10 · Feishu Approval Gate 测试方式(C P0-1 修复)

```bash
# 步骤 1: 默认调用 → 进 approval queue, 不真发飞书
curl -X POST "http://127.0.0.1:47831/api/v1/feishu/tasks/push?task_id={任意现有 task id}" \
  -H "X-Actor-Type: external_ai_agent" \
  -H "X-Actor-Id: b_audit" \
  -H "Idempotency-Key: feishu-test-001"
→ HTTP 200, status=pending_approval, feishuGuid=null, 返回 approval_id

  期望 db diff:
    approval_queue (action_type='task.publish'): +1
    agent_run_log (tool_name='feishu.tasks.push'): +1

# 步骤 2: 同 Idempotency-Key 重发 → cached, db 不变
curl -X POST "..." -H "Idempotency-Key: feishu-test-001"
→ 同 approval_id 返回, db Δ=0

# 步骤 3: force_execute=true 无 approved → 必 403
curl -X POST "...?task_id=...&force_execute=true" \
  -H "X-Actor-Type: external_ai_agent"
→ HTTP 403, detail "高风险动作必须先走审批..."

# 步骤 4: 真 approve 后才能发
curl -X POST "http://127.0.0.1:47831/api/v1/approvals/{approval_id}/approve" \
  -d '{"decided_by": "human:user", "note": "approved by user"}'
curl -X POST "...?task_id=...&force_execute=true"
→ 此时通过 approval 校验, 飞书未配置 → 400 (但 gate 逻辑过)
```

---

## 11 · Idempotency 测试方式(C P0-2 修复)

5 个 endpoint 全支持 `Idempotency-Key` Header:

| endpoint | 来源 | 测试 |
|---|---|---|
| POST /api/v1/meeting-minutes/process | R2 fix-2 | 同 key 重发 → atomic_facts Δ=0 |
| POST /api/v1/smart-import/sessions/{id}/commit | C P0-2 (本份) | 同 key 重发 → v2_documents Δ=0 |
| POST /api/v1/tasks | R4-P1-5 | 同 key 重发 → tasks Δ=0 (HTTP 409 in_progress) |
| POST /api/v1/clients/{id}/documents/fill-template | C P0-2 (本份) | 同 key 重发 → 返同 ClientTemplateFillResponse, fs Δ=0 |
| POST /api/v1/feishu/tasks/push | C P0-1 (本份) | 同 key 重发 → 返同 approval_id, approval_queue Δ=0 |

通用测试模板:
```bash
TS=$(date +%s)
KEY="b-idemp-$TS"

# 第一次
curl -X POST <endpoint> -H "Idempotency-Key: $KEY" -d <body>
TBL_BEFORE=$(sqlite3 ... "SELECT COUNT(*) FROM <写入表>")

# 同 key 重发
curl -X POST <endpoint> -H "Idempotency-Key: $KEY" -d <body>
TBL_AFTER=$(sqlite3 ... "SELECT COUNT(*) FROM <写入表>")

# 验证
[ "$TBL_BEFORE" -eq "$TBL_AFTER" ] && echo "PASS" || echo "FAIL Δ=$((TBL_AFTER-TBL_BEFORE))"
```

---

## 12 · V3 前端入口位置

```
启动: Electron app (V2.1 lab) 已在运行 (PID 内嵌 backend 53863)
路径: 设置 → 系统日志 → 滚到底部 → "AGENT READY · V3 调试" 节

代码:
  src/renderer/lib/api.ts                  9 个 V3 wrapper (608-790 行附近)
  src/renderer/components/data_center/AgentReadyPanel.tsx (440 行, 4 tab)
  src/renderer/App.tsx                     挂载点 28553 (设置 → 系统日志 case)

4 个 tab:
  数据缺口 (DataGapsView)        ← getClientDataGaps
  AI 调用历史 (AgentRunLogsView)  ← listAgentRunLogs
  工具清单 (ToolRegistryView)     ← getToolRegistry
  待审批 (ApprovalQueueView)      ← listApprovals + approveApproval + rejectApproval
```

---

## 13 · 当前 blocked_by_A

```
P1 (本阶段后期, 或下轮):
  · contracts.draft endpoint (V3.0 任务书 P0-1)  ← M2 本阶段做
  · templates.generate endpoint (V3.0 任务书 P0-2) ← M2 本阶段做
  · documents.generate 通用工具                    ← M2 本阶段做 (新加, 顾源源 §M2 钦定)
  · MCP server wrapper (scripts/yiyu_mcp_server.py)  ← M1 本阶段做
  · 10/14 生成功能迁移 ContextBuilder (C P1-1)
  · 591 endpoint 24% docstring 全量补 (C P1-2)
  · 5 个生成型 endpoint 加 audit log (C P1-3)

P2 (优化, 不阻塞 MCP v0):
  · OpenAPI /openapi.json 默认 404 (C P2-1)
  · M2-1 keyword 切词偏差 (C P2-2)
  · M2-3 authority 同 score 排序 (C P2-3)
  · narrative 6 段框架软化 (C P2-4)

(P0 三件套 + Tool Registry 一致性 全修, C 审计 75/100)
```

---

## 14 · B 下一步应该复验什么

按顾源源 §M0 §M1 §M2 §M3 顺序:

```
1. 跑 yiyu_mcp_server.py (本阶段 M1 A 交付后):
   - 配 Claude Desktop / Cursor 接入
   - 6 类 resources 真读
   - 17 tools 自动同步 Tool Registry
   - 跑 3 audit prompts

2. 跑 Stage 2 dry-run (本阶段 M3 fixtures 后):
   - 场景 1 外部体检官: read-only 真测
   - 场景 2 dry-run: 输入会议纪要, 只生成 plan, 不写库
   - 场景 3 draft-run: 生成草稿, 危险动作进 approval

3. 跑 Final Acceptance (本阶段总报告后):
   - Claude Desktop 真接入
   - 14 功能 Golden Pack 大样本
   - 跨客户隔离 100% 全 3 客户
   - Idempotency 5 endpoint duplicate
   - 出 V3 最终验收报告 (汇总 B 和 A 两边)
```

---

## 15 · 顾源源原则自检

| 原则 | 自检 |
|---|---|
| A 不再自证完成 | ✅ (本份是状态文档, 不是 FINAL 自评) |
| 不扩散新方向 | ✅ (本阶段只做 M0-M3 + 文档生成 3 工具 + MCP wrapper) |
| 坚持开放架构 | ✅ (documents.generate 设计为 document_type 参数化, 不写死会议→合同→品牌流程) |
| 危险动作必须进 Approval Queue | ✅ (C P0-1 修复后真生效 + M2 文档生成走 approval) |
| 写入型必须幂等 | ✅ (C P0-2 5/5) |

---

## 16 · 状态总结

```
A 本阶段 M0 冻结 commit 80e3340:
  · C 审计 P0 全修, 估分 75/100
  · 4 件 P0: feishu gate / idempotency 5/5 / V3 前端 4 入口 / Tool Registry 一致
  · backend 在线 (V2.1 lab port 47831 真活)
  · V2.1 lab db 281 MB 包含 5 客户真数据

下一步 (本阶段 autonomous loop):
  M1 MCP wrapper (read-only/dry-run/audit, 顾源源 §M1 钦定 A 做)
  M2 documents.generate 通用 + contracts.draft 兼容 + templates.generate 兼容
  M3 Final Test fixtures (3 场景)
  + 总报告 (40 号位) + inbox-B 通知

报告 docs/A_V3_FINAL_TEST_SUPPORT_STATUS.md + 桌面 36 号位.
```
