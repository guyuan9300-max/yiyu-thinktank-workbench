# B AI 进展雷达 · 持续追踪 (顾源源 5/23 钦定)

> **作用**: 每次 A 或 B 有新 commit, B 在 30 分钟内更新一次. 给顾源源一眼图谱.
> **当前 snapshot**: 2026-05-23 20:20 (commit `804a849`)
> **上次 snapshot**: 19:50 (commit `efd6870`, B 7 件交付齐)
> **下次更新触发**: A 暴露任一 V3.0 任务书 5 endpoint / B 完成 Golden Pack × 14 复验

---

## 1 · 北极星指标

| 指标 | 当前 | 目标 | 状态 | 数据来源 |
|---|---|---|---|---|
| R4 用户可感知分 | 90 (A 自评) → R4-P1 **94** (A 20:20 复测) | ≥ 80 (P0) / ≥ 95 (R4-P1) | ⚠️ **A 自评待 B 复验, 差 1 到 R4-P1 通过线 95** | A 285e185 + 804a849 |
| 数据库—功能深度联动分 | 90 → 94 (A 自评) | ≥ 80 | ⚠️ **A 自评待 B 复验** | A 5fefcf3 → 285e185 → 804a849 |
| V3.0 AI 驱动软件做事分 | 56.5 | ≥ 80 | 🔴 **差 23.5** | B 748c833 真测 V2.1 lab db |
| **V3.0 L1-L4 通过层数** | **1 / 4** | 4 / 4 | 🔴 **只 L1 通** | B 19:45 / 20:18 dryrun (2 次都 1/4) |

---

## 2 · L1-L4 分层 (V3.0 北极星)

| 层 | 状态 | 关键证据 | 阻塞 |
|---|---|---|---|
| **L1 单链路处理** | ✅ ok | facts +5 / risks +2 / commit +2 / clarif +1 / approval +2 | - |
| **L2 多模块调度** | 🔴 blocked_by_A | 调用 1 模块 (目标 ≥ 4) | 5 endpoint 缺: contracts/draft, templates/generate, brand-proposition, brand-mirror/analyze payload, meeting-pack 403 |
| **L3 主动缺口发现** | 🔴 blocked_by_A | data-gaps endpoint 404 + 没 data_gaps 表派生 | GET /clients/{id}/data-gaps endpoint 缺 |
| **L4 Goal-Plan-Run** | 🔴 blocked_by_A | 0/3 endpoint 通 | POST /agent/plan + POST /agent/run + GET /agent/status 全缺 |

→ **现在能做到的: AI 是会议纪要专员**.
→ **目标: AI 是公司操作官**.
→ **距离: A 暴露 5-7 个 endpoint + 前端挂 4 badge = 8-12h**.

---

## 3 · 14 功能 A/B/C/D/E 评级 (跟 A SELF_CHECK 对照)

| 来源 | 时间 | A | B | C | D | E |
|---|---|---|---|---|---|---|
| A SELF_CHECK 17:32 | (A 自评) | 1 | 5 | 5 | 3 | 0 |
| A 18:10 P0-2/3/5 后预测 | (A 自预测) | 3-5 | ? | ? | ? | ? |
| **B 独立复验** | **(未跑)** | **?** | **?** | **?** | **?** | **?** |

→ B 下阶段补: 14 功能逐项 Golden Test Pack 复验.
→ R4-P0 通过线: A 级 ≥ 5.

---

## 4 · single_file_only 风险

| 功能 | 目标 | 当前 (A 自报) | B 独立 verify |
|---|---|---|---|
| 工作台问答 | ≤ 10% | false (A 18:10) | ⚠️ 待 B 复验 (Golden Pack 跑 10 题) |
| 战略陪伴 | 0% | A 自报 P0-4 未做 | ⚠️ 待 B 复验 |
| 模板填充 | ≤ 10% | endpoint 缺 | n/a |
| 粘贴生成 | ≤ 20% | endpoint 缺 | n/a |

---

## 5 · endpoint 缺口 (V3.0 ≥ 80 阻塞)

| Endpoint | 含义 | 阻塞层 | 优先级 (B 推荐) |
|---|---|---|---|
| `POST /api/v1/contracts/draft` | 合同草稿 | L2 | P0 (用户感知最强, 顾源源样本 1 题) |
| `POST /api/v1/templates/generate` | 理事会说明等 | L2 | P0 |
| `POST /api/v1/clients/{id}/brand-proposition` | 品牌建议 | L2 | P1 |
| `GET /api/v1/clients/{id}/data-gaps` | Data Gap (V3.0 P0a) | L3 | P0 |
| `POST /api/v1/agent/plan` | Goal-Plan | L4 | P2 (跟 P1 比晚做) |
| `POST /api/v1/agent/run` | Goal-Run | L4 | P2 |
| `GET /api/v1/agent-run-logs` | Run Log list | (UI) | P1 |
| `strategic-cockpit/meeting-pack` 403 | 会谈提纲 | L2 | P1 (修权限) |

→ **5 件 P0**: 合同 + 模板 + 品牌 + Data Gap + 会谈提纲权限.
→ **3 件 P1**: brand-proposition + agent-run-logs + meeting-pack
→ **2 件 P2**: Goal-Plan-Run

---

## 6 · UI 待人工确认项 (L3, B 不能自动判)

10 项 (B3 dry-run 输出):
- `ui_evidence_badge` — 工作台 evidence 摘要框 ✅ A 自报 P0-5 挂了, 顾源源截图
- `ui_pending_clarification_badge` — 客户工作台 待澄清徽章 ❌ A 18:10 自报未挂头部
- `ui_pending_approval_badge` — 客户工作台 待审批徽章 ❌ A 18:10 自报未挂头部
- `ui_file_identity_badge` — smart_import 文件身份 badge ❌ A 18:10 自报未挂
- `ui_contract_structure_card` — 合同结构卡片 ❌ A 18:10 自报未挂
- `ui_proposed_clarifications_list` — 澄清列表用户能采纳/修正 ✅ A 自报 P0-5 挂了
- `ui_narrative_evidence_label` — 战略陪伴 evidence 标签 ❌ A 18:10 自报 P0-4 未做
- `ui_low_confidence_marker` — 战略陪伴 低把握度标记 ❌ A 自报 P0-4 未做
- `ui_agent_run_log_history` — Run Log 历史可见 ❌ endpoint 缺
- `ui_approval_actions` — 审批通过/拒绝 ✅ endpoint 已暴露, 等顾源源截图

→ **6 项 blocked_by_A** (前端没挂), **4 项 blocked_by_user** (等顾源源截图).

---

## 7 · blocked_by_A 清单 (8 项, 按优先级)

```
P0 (V3.0 L2/L3 直接卡):
  1. 暴露 POST /api/v1/contracts/draft
  2. 暴露 POST /api/v1/templates/generate
  3. 修 strategic-cockpit/meeting-pack 403 权限
  4. 暴露 GET /api/v1/clients/{id}/data-gaps + 接 data_gap_compensator

P1 (R4-P0 P0-4 + UI 前端):
  5. narrative_generator prompt 真用 R4 字段 (战略陪伴 P0-4)
  6. 4 badge 挂客户工作台头部 + smart_import + 战略陪伴
  7. 暴露 GET /api/v1/agent-run-logs (用户可见 Run Log)

P2 (V3.0 P1, 大工程):
  8. 暴露 POST /api/v1/agent/plan + /api/v1/agent/run + /agent/status
```

---

## 8 · blocked_by_B 清单 (本阶段 0 项)

```
本阶段 7 件交付 (B0-B5 + 总结) 全完成 ✅:
  B0 docs/B_AI_EVAL_STANDARD_V1.md
  B1 fixtures/golden/ × 7 + docs/B_AI_GOLDEN_TEST_PACK.md
  B2 scripts/run_b_eval_baseline.py
  B3 scripts/run_v3_ai_driven_dryrun_eval.py
  B4 docs/B_AI_EXTERNAL_AGENT_DRYRUN_CONTRACT.md
  B5 docs/B_AI_PROGRESS_RADAR.md (本文)
  + docs/B_AI_NEXT_STAGE_WORK_REPORT.md (总结)

下阶段 B 待办:
  - 14 功能逐项独立复验 (跟 A 41/100 / 90/100 对照)
  - api-contract 模式 LLM 慢 timeout 修 (改 60s)
  - 跨客户隔离 V3.0 dryrun 加进 L1
```

---

## 9 · blocked_by_user 清单 (等顾源源)

```
1. 拍板 5 件 P0 endpoint 优先级 (B 推荐 合同 > 模板 > Data Gap > 会谈提纲 > 品牌)
2. 截图 4 项 UI L3 verify (evidence 摘要框 / proposed_clarifications / 审批通过 / smart_import file_identity)
3. 拍板是否接受 A 90 自评当 R4-P0 真过, 还是等 B 独立复验
4. 桌面 17 V3.0 报告 + 18 R4 复测报告同步 (顾源源拷)
```

---

## 10 · 时间线

```
5/23 16:46 B sync R4-P0 给 A
5/23 17:10 A R2 fix-2 三缺口修通 (V2.1 lab db 真过)
5/23 18:10 A R4-P0 P0-2/3/5 commit (workspace/chat 顶层 5 字段 + smart_import + 前端 5 组件)
5/23 18:30 B V3.0 baseline 56.5/100 (V2.1 lab db 真测)
5/23 18:35 A R4 联动 63/100 (求 B 扩 init 4 表)
5/23 18:42 B init 16/16 (4 R3 表全建)
5/23 19:35 A R4 复测 90/100 ★ (A 自评待 B 复验)
5/23 19:30 顾源源新角色钦定: B = 自动验收官
5/23 19:50 B 7 件交付完成 (B0-B5 + 总结) commit ea481ce
5/23 20:10 A R4-P1 P1-1+P1-2 commit efd6870 (narrative R4 + 4 badge 挂)
5/23 20:18 A R4-P1 P1-3+P1-4+P1-6 commit 69adfb3 (chat 反向入库 + text/resolve-history + 模板 ContextBuilder)
5/23 20:20 A R4-P1 复测 90→94 commit 804a849 (A 自评待 B 复验) ★ 本 snapshot
5/23 20:25 B 重跑 V3.0 dryrun 仍 1/4 (A 69adfb3 endpoint 不在 V3.0 L2 测试集)

★ 关键发现 (B 20:25):
  · A R4-P1 真涨 (90→94, A 自评)
  · 但 R4-P1 改的 endpoint (text/resolve-history, fill-template, send_chat 内部反向入库)
    跟 V3.0 L2 任务书 5 endpoint (contracts/draft / templates/generate /
    brand-proposition / brand-mirror / meeting-pack) 是 **不同集合**
  · V3.0 L2 仍 blocked_by_A — A 还没碰 V3.0 任务书 5 endpoint

下次 snapshot 触发:
- A 暴露任一 V3.0 任务书 5 endpoint (contracts/draft 等)
- B 跑 14 功能独立 Golden Pack 复验
- 顾源源截图 L3 verify 4 项
```

---

**更新规则**:
- 每次 A/B 有新 commit, B 30 min 内更新本文件
- 只更新数字, 不删历史 (历史在 `docs/AI_COORDINATION/log.md`)
- 每次更新写 commit message 包含 "[B] radar update"

**关联**:
- 评估标准: `docs/B_AI_EVAL_STANDARD_V1.md`
- Golden Pack: `docs/B_AI_GOLDEN_TEST_PACK.md`
- B 评估基线: `docs/B_AI_EVAL_BASELINE_REPORT.md`
- V3.0 dry-run: `docs/B_AI_V3_DRYRUN_REPORT.md`
- 外置 Agent 契约: `docs/B_AI_EXTERNAL_AGENT_DRYRUN_CONTRACT.md`
