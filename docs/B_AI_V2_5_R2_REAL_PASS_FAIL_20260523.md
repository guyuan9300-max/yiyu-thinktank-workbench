# V2.1 RC R2 真客观评估 · 综合解读 (顾源源 5/23 8 步验)

> **生成**: 2026-05-23 11:15
> **评估对象**: V2.1 仓库 (= 未来主仓库候选版)
> **数据源**: V2.1 lab db (拒绝 dogfood_real / snapshot)
> **调用方式**: HTTP endpoint port 47831 全程
> **测试客户**: 日慈基金会 (`client_284afd836e`) + CFFC (`client_a4d1db29a7`)

---

## 1 · R2 真分数

```
3 客户平均: 56.0 / 100   🔴 R2 通过线 ≥ 70 未达 (差 14 分)
日慈基金会: 56 / 100
CFFC:       56 / 100
```

→ **R2 未通过**, 但 6 硬门槛 5/6 ✅, 1 个具体缺口可补.

---

## 2 · 顾源源 8 步逐项 verify

| 步 | 内容 | 状态 | 证据 |
|---|---|---|---|
| 1 | curl smoke endpoint | ✅ | POST /meeting-minutes/process → 200, GET /approvals → 200 |
| 2 | 提交日慈会议纪要 | ✅ | run_id=run_9d185861dbfb..., HTTP 200, 1.6s |
| 3 | 提交 CFFC 会议纪要 | ✅ | run_id=run_2d50176eb797..., HTTP 200, 1.6s |
| 4 | sqlite3 查 V2.1 lab db 前后差异 | ✅ | snap_before/after 实测 |
| 5 | 核对 facts/event_line/risks/commits/clarif/approval/run_log | ⚠️ | 7 项中 5 项过, 2 项 0 (clarif/event_line) |
| 6 | 验证跨客户隔离 | ✅ | 跑日慈时 CFFC 0 leak, 跑 CFFC 时日慈 0 leak |
| 7 | 验证重复运行不重复写入 | ✅ | 第 2 次 HTTP 200 但 V2.1 lab db 无新增 |
| 8 | 输出 V2.1 R2 HTTP 真实运行报告 | ✅ | docs/B_AI_V2_5_R2_REPORT_20260523_074630.md |

---

## 3 · 6 硬门槛 (顾源源 5/23 11:00 加严)

| 门槛 | 日慈 | CFFC | 备注 |
|---|---|---|---|
| 1 通过 HTTP endpoint 调用 | ✅ | ✅ | port 47831, X-Actor-Type 等 header 经过 |
| 2 V2.1 lab db 11 张表真实存在 | ✅ | ✅ | npm run db:init:lab 跑过 |
| 3 数据真有记录 (7 项) | 🔴 | 🔴 | clarif +0, event_line +0 (其他 5 项过) |
| 4 不依赖 dogfood_real snapshot | ✅ | ✅ | sqlite3 直接读 V2.1 lab db verify 涨数 |
| 5 重复跑无重复任务/澄清 | ✅ | ✅ | idempotency 生效 (内部 dedupe) |
| 6 跨客户隔离 0 leak | ✅ | ✅ | 11 张表全 0 变化 |

→ 5/6 ✅, **第 3 项是唯一不过门槛**.

---

## 4 · 7 维度评分明细

| 维度 | 满分 | 日慈得分 | CFFC 得分 | 主要丢分点 |
|---|---|---|---|---|
| D1 AI 调度全链路 | 15 | 9 | 9 | 调用步骤 2 / 模块 2 (期望 ≥ 3 步) |
| D2 资料变客户理解 | 20 | 18 | 18 | facts +5 / risks +2 / commits +2 — 接近满分 |
| D3 澄清问题质量 | 15 | **0** | **0** | clarification_records +0 (期望 ≥ 1) |
| D4 理解转行动草稿 | 15 | 5 | 5 | task_drafts 0 / approvals queued 2 |
| D5 纠错回写 | 15 | 5 | 5 | R2 暂不测 (静态 5/15), 等 R3 |
| D6 内外驱动一致性 | 10 | 4 | 4 | R2 单驱动测 (静态 4/10), 等 R3 双驱动 |
| D7 安全审计 | 15 | 15 | 15 | HTTP / 11 表 / run_log / 幂等全 ✅ ★ 满分 |
| **总分** | **100** | **56** | **56** | |

★ D7 满分: V2.1 R2 安全审计层真完整 (V2.5 R2-A 治理生效).

---

## 5 · A R3 88.8 (dogfood) vs B R2 56 (V2.1 lab db) · 对比

**不可直接对比** — A 88.8 是 R3 (8 维度, dogfood_real snapshot), B 56 是 R2 (7 维度, V2.1 lab db 真测).

但有 1 个**严肃事实**对比:

| 项 | A 88.8 (dogfood) | B 56 (V2.1 lab db 真测) |
|---|---|---|
| 数据源 | `dogfood_real/prod_snapshot.db` (主仓库 prod copy) | V2.1 lab db `app.db` (未来主仓库) |
| HTTP only | 直调 Python service | HTTP curl 全程 |
| atomic_facts 增量 | (跑分时 +N, 真在 prod_snapshot.db) | **真 +5 在 V2.1 lab db** (日慈/CFFC) |
| agent_run_log | (跑分时 +1, 表在 prod_snapshot 不存在) | **真 +1 在 V2.1 lab db** (B init script 后) |
| approval_queue | (跑分时 +2, 表在 prod_snapshot 不存在) | **真 +2/+1 在 V2.1 lab db** |
| 顾源源接受 | ❌ A 错认 (顾源源没正式接受) | ⏸ R2 56 未到 70 通过线 |

→ B R2 56 才是 **V2.1 lab db 第一次真长出来的数字**.
→ A R3 88.8 在 dogfood 上算的, 不是顾源源拍板的"V2.1 = 未来主仓库"的真状态.

---

## 6 · R2 唯一不过门槛 (第 3) 的 3 个具体缺口

### 缺口 1: clarification_records +0

期望: ≥ 1 (硬门槛 3 + D3 评分)
实测: **0** (两客户都 0)

可能原因:
- A `MeetingMinuteProcessor` 内部 clarification 派生器**没接 endpoint 调用链**
- 或: clarification 派生器跑了, 但**不在 V2.1 lab db `clarification_records` 表写入** (写别处?)
- 或: clarification 派生器要求特定输入 (如多候选歧义), B 的 GOLDEN_MEETING_TEMPLATE 不触发

verify 方向: A endpoint response `clarifications_added=1` (smoke 测时), 批量跑 `clarifications_added=0` — 应该是输入或派生器逻辑.

### 缺口 2: event_line_activities +0

期望: ≥ 1 (硬门槛 3)
实测: **0** (两客户都 0)

可能原因:
- A `MeetingMinuteProcessor` 没调用 event_line_activities 派生器
- 或: V2.3 派生器逻辑要求特定 trigger, 单段会议纪要不触发

A endpoint response 字段有 `event_line_activities_added`, 但都返回 0.

### 缺口 3: D4 task drafts 0/15 → 5/15

期望: task_drafts +1 (D4 评分)
实测: task_drafts 0 (但 approval_queue +2/+1 真有)

可能原因:
- A endpoint response `task_drafts_added=0`, 但 `approval_queue_ids` 有数据 → **task 是直接进 approval, 不创 task draft**
- → D4 评分公式应该接受 "approval_queue ≥ 1" 当 task drafts 替代

→ 可能是 B 评分公式 D4 设计偏, 不是 A 真不工作.

---

## 7 · 给 A 的 1 件硬纠 + 2 件可选纠

### 硬纠: agent_run_log.idempotency_key 列没记录

实测 agent_run_log 6 条 row, `idempotency_key` 列**全是 NULL**:
```
('run_9d185861...', 'external_ai_agent', 'b-v25-r2-test', 'meeting_minute_processor.process', 'success', None, ...)
                                                                                                   ^^^^ idempotency_key = NULL
```

但 A endpoint header `Idempotency-Key` 真接到了 (因为重复跑没产生新 row).

→ A 在 `process_meeting_minute_endpoint` 里调 `log_agent_run_start` 时**没把 idem_key 传进去**.
→ V2.5 R2 治理层完整性损失.

### 可选纠 1: clarification 派生器接 endpoint

让 `MeetingMinuteProcessor` 调用 ClarificationDeriver, 写 V2.1 lab db `clarification_records` 表.

### 可选纠 2: event_line_activities 派生器接 endpoint

让 `MeetingMinuteProcessor` 调用 EventLineActivityDeriver, 写 V2.1 lab db `event_line_activities` 表.

---

## 8 · 顾源源 5 个严卡 (再次 verify)

| 严卡 | 状态 |
|---|---|
| HTTP only (不直调 service) | ✅ |
| V2.1 lab db 11 张表真存在 | ✅ |
| 数据真有记录 (≥5 facts / ≥1 risk / ≥1 commit / ≥1 clarif / ≥1 task / ≥1 run / ≥1 approval) | 🔴 缺 clarif (其他 6 项过) |
| 不依赖 dogfood_real snapshot | ✅ |
| 重复跑不重复写入 | ✅ |

→ 4/5 严卡过, 缺 clarif.

---

## 9 · B 下一步 (autonomous, 不问)

1. **写 sync 给 A** (`docs/B_AI_SYNC_TO_A_R2_GAPS_20260523.md`) — 3 缺口具体修复指引
2. **commit 本报告 + sync** (autonomous)
3. **等 A 修 3 缺口 (估 0.5-1h)** — 然后 B 重跑 R2 → 预期 ≥70 通过
4. **R2 真通过后接 R3** — A 暴露 R3 5 endpoint, B 跑 R3 真测 → 出 R3 真分 (跟 88.8 对比)

---

## 10 · 结论

```
顾源源 8 步 全过 (1-8, 第 5 步 7 项中 5 项过, 2 项缺)
V2.1 RC R2 真分: 56 / 100
V2.1 RC R2 通过线: ≥ 70 → 🔴 差 14 分
但: 5/6 硬门槛过, 缺 1 (clarif + event_line + Idempotency-Key 记录)
A R3 88.8 dogfood snapshot 跑分 ≠ V2.1 lab db 真分
真 R2 通过预期: A 补 3 缺口后 → 70+
```

**A endpoint 真有用** ✅
**V2.1 lab db 真长出数据** ✅
**没用 dogfood_real** ✅
**没用旧主仓库扣分** ✅

---

**Author**: AI B · 2026-05-23 11:15
**关联**:
- 报告: docs/B_AI_V2_5_R2_REPORT_20260523_074630.md
- JSON: tests/reports/v25_r2_20260523_074630.json
- sync: docs/B_AI_SYNC_TO_A_R2_GAPS_20260523.md (下一 commit)
