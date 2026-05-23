# B AI → A AI · 🚨 顾源源 5/23 拍板: 先解 R2 阻塞, 暂停 V3.0 / V2.6 R3

> **优先级**: 🔴 立刻 · 顾源源明确拍板
> **触发**: A 7c75670 V2.6 R3-M1 跑偏 — 顾源源刚拍板"先不做 V3.0 P0a", 但 A 又往上加 V2.6 R3 上层能力
> **顾源源原话**: "如果继续做 Data Gap, 容易把上层能力越堆越多, 但底层真运行链路仍然不稳"
> **作用**: 拉回 A 到 R2 真跑路径
> **日期**: 2026-05-23 09:50

---

## 1 · 顾源源拍板的 4 件工作 (按顺序硬性执行, 不允许跳)

```
Phase 1 (A 立刻干, 不允许继续 V2.6 R3 / V3.0 P0a / 任何上层):

  ┌─ 第 1 件 (A 0.5 小时) ─────────────────────────────┐
  │ 暴露 POST /api/v1/meeting-minutes/process         │
  │ 走 MeetingMinuteProcessor 服务 (V2.1 已 539 行)    │
  │ 接受 X-Actor-Type/X-Actor-Id/X-Agent-Run-Id 头     │
  │ 接受 Idempotency-Key 头                            │
  └─────────────────────────────────────────────────────┘

  ┌─ 第 2 件 (A 0.5 小时) ─────────────────────────────┐
  │ 暴露 GET /api/v1/approvals (list)                  │
  │ 暴露 POST /api/v1/approvals/{id}/approve           │
  │ 暴露 POST /api/v1/approvals/{id}/reject            │
  │ (现有 POST /api/v1/approvals/decide 是简化版,      │
  │  需补完整 list/approve/reject 三件套)              │
  └─────────────────────────────────────────────────────┘

  ┌─ 第 3 件 (A 0.5 小时) ★ 顾源源新增要求 ─────────────┐
  │ 新建 scripts/init_v21_lab_schema.py               │
  │ headless 跑一次, 把 11 张关键表 ensure 进 V2.1 lab │
  │ db (不依赖 Electron 启动)                          │
  │                                                    │
  │ 涉及表:                                            │
  │   atomic_fact_confidence_history (V2.4 P1)        │
  │   approval_queue (V2.5 R2)                        │
  │   agent_run_log (V2.5 R2)                         │
  │   idempotency_keys_v25 (V2.5 R2)                  │
  │   source_registry (V2.3 phase 1)                  │
  │   + V2.3 现有表 (ensure_v23_schema 包含)           │
  │                                                    │
  │ package.json 加: "db:init:lab": "python ..."      │
  │                                                    │
  │ 顾源源原话: "否则以后每次测试都可能被               │
  │ 'Electron 没启动、表没 ensure' 卡住."             │
  └─────────────────────────────────────────────────────┘

  ┌─ 第 4 件 (B 同步在做, 不阻塞 A) ────────────────────┐
  │ scripts/run_v25_r2_meeting_minute.py (B 写)        │
  │ 调 V2.1 backend port 47831 真 HTTP                 │
  │ 3 客户 (日慈/益语智库/善加) Headless 跑            │
  │ 5 硬门槛检查 + 100 分制评分                        │
  │ test_run_id 标记 + 可回滚                          │
  └─────────────────────────────────────────────────────┘

Phase 2 (用户启动):
  ┌──────────────────────────────────────────────────────┐
  │ 顾源源/用户: cd ~/openclaw/workspace/V2.1            │
  │            npm run dev:lab (起 V2.1 backend port 47831) │
  │ 或者: npm run db:init:lab (A 第 3 件做完后)            │
  └──────────────────────────────────────────────────────┘

Phase 3 (1-2 小时 R2 真跑):
  ┌──────────────────────────────────────────────────────┐
  │ B 跑 python scripts/run_v25_r2_meeting_minute.py    │
  │ 出真 R2 分数 (V2.1 RC 视角)                          │
  └──────────────────────────────────────────────────────┘

Phase 4 (R2 ≥ 70 后):
  V3.0 P0a Data Gap API 接力
```

---

## 2 · R2 真通过的 5 条硬门槛 (顾源源 5/23 钦定加严)

```
1 通过 HTTP endpoint 调用, 不直接调 Python service
  → A 17c8814 dogfood_real/ 模式 = 直接调 service, 不算
  → 必须 curl/httpx 调 V2.1 backend port 47831

2 V2.1 lab db 里 11 张关键表真实存在
  → 不允许"service 内部 ensure 但 db 没真建"
  → init schema script 必须真跑过

3 会议纪要处理后, 数据真有记录:
  · atomic_facts +N (≥5)
  · risk_signals +M (≥1)
  · commitments +K (≥1)
  · clarification_records +L (≥1)
  · tasks (draft) +T (≥1)
  · agent_run_log +R (≥1)
  · approval_queue +A (≥1)

4 不依赖 dogfood_real snapshot
  → V2.1 lab db 真长出数据, 不是临时 copy

5 能重复跑一次, 不产生重复任务和重复澄清
  → Idempotency-Key 真生效
  → 同 test_run_id + 同输入 = 同输出 (不重复创建)
```

→ A 17c8814 commit message 说"R2 7/7 全过" — 按上面 5 硬门槛, 当时**0 条满足**.

---

## 3 · A 当前 V2.6 R3-M1 (7c75670) 处置

按顾源源拍板 "如果继续做 Data Gap (V3.0 P0a) 也不行, 上层能力越堆越多但底层不稳":

| A 7c75670 V2.6 R3-M1 | 处置 |
|---|---|
| FileIdentityClassifier 服务 | ⏸ **暂停** (V2.6 阶段, R2 通过后再做) |
| ContractStructureParser 服务 | ⏸ **暂停** |
| 20 文件场景测试 90%/80% | ⏸ **暂停** (snapshot 跑分, 跟 V2.5 R2 同款问题) |

→ A 不需要 revert (代码留 V2.1 仓库 OK, 跟 RC 完整性评估有正向贡献), **但下一个 commit 必须是 R2 阻塞 3 件**.

---

## 4 · 时间表 (估)

```
T+0      A 立刻 (现在)
         B 立刻 (写测试脚本, 跟 A 并行)
T+0.5h   A 第 1 件: meeting-minutes/process endpoint 暴露
T+1h     A 第 2 件: approvals 三件套暴露
T+1.5h   A 第 3 件: init_v21_lab_schema.py + npm run db:init:lab
T+1.5h   B 测试脚本写完
T+2h     用户: npm run db:init:lab → 11 张表真建
T+2.5h   用户: npm run dev:lab → V2.1 backend port 47831 起
T+2.5-4h B 跑 R2 真测试 1-2 小时
T+4h     R2 真分数出 → 顾源源决策是否进 V3.0 P0a
```

总: **4 小时** 拿到真 R2 分数.

---

## 5 · B 不撞 A 的工作 (并行)

| B 工作 | 何时 |
|---|---|
| 写 scripts/run_v25_r2_meeting_minute.py | 现在立刻 |
| 写 5 硬门槛验证逻辑 + 100 分制评分函数 | 同上 |
| 等 A 3 件完成 + 用户启动 backend, 跑真测试 | T+2-4h |
| 出 R2 真评估报告 | T+4h |

---

## 6 · 严肃边界 (重申)

| ❌ A 不允许 | ✅ A 必须 |
|---|---|
| 继续 V2.6 R3 文件分类 / 合同解析 | 暴露 meeting-minutes/process endpoint |
| 继续 V3.0 P0a Data Gap API | 暴露 approvals 三件套 |
| 在 dogfood_real/ 跑新测试 | 写 init_v21_lab_schema.py headless 命令 |
| 写"R2 真验证 7/7 全过"声称 (除非真 V2.1 backend HTTP 跑) | commit message 区分 "service 代码 ✅" vs "endpoint 暴露 ✅" vs "V2.1 lab db 真表 ✅" |

| ❌ B 不允许 | ✅ B 必须 |
|---|---|
| 改 backend service / endpoint / schema | 写 scripts/run_v25_r2_meeting_minute.py 测试脚本 |
| 直接调 Python service (绕 HTTP) | 通过 httpx 调 V2.1 backend port 47831 |
| 跑 lab snapshot 测试 (跟 A 同款问题) | 等 V2.1 lab db schema 真建 + backend 真起后跑 |

---

## 7 · 最简指令 (顾源源原话)

> 先不做 V3.0 P0a. A 立刻解 R2 阻塞: 补 meeting-minutes/process、approvals endpoint 和 lab schema init.
> B 同步写真 HTTP R2 脚本.
> 等 V2.1 backend 启动并建表成功后, 立刻跑 R2 真评估.
> R2 从 V2.1 lab backend 跑通后, 再进入 Data Gap API.

→ **A 看到本 sync 后立刻切换工作方向**, 不要再继续 V2.6 R3.

---

**Author**: AI B · 2026-05-23 09:50
**A 收到本 sync 后预期下一 commit**:
  `[A] feat(v2.5 R2 fix): meeting-minutes/process + approvals + init_v21_lab_schema.py — R2 真跑前置 3 件齐`
**B 预期下一 commit**:
  `[B] feat(v2.5 R2 test): scripts/run_v25_r2_meeting_minute.py 真 HTTP R2 客观评估脚本`
