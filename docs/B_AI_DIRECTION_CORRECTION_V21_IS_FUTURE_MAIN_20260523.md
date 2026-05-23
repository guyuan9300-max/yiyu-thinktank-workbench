# B AI · 方向校正: V2.1 = 未来主仓库, R2 真执行计划

> **触发**: 顾源源 5/23 关键澄清 "V2.1 仓库整个做完之后会替代主仓库, 就成为主仓库, 不用再评估主仓库了"
> **作用**: 撤回 d5bf241 的"主仓库 vs lab 二分法", 重新规划 R2 真执行
> **执行人**: AI B
> **日期**: 2026-05-23 09:05

---

## 1 · 立刻撤回的判断

### 撤回 d5bf241 报告里这几句

| ❌ 撤回 | ✅ 改成 |
|---|---|
| "主仓库 prod db 一行没动" | (无意义, V2.1 就是未来主仓库) |
| "A 17c8814 = V2.1 lab snapshot, 不是真验证" | A 17c8814 写在 V2.1 backend = 真验证, **但跑分数据流量不在 V2.1 lab db, 在 A 临时 dogfood_real/** |
| "必须 cherry-pick V2.1 → 主仓库" | (不需要, V2.1 替代主仓库) |
| "用户日常 app 看不到 V2.4/V2.5" | (将来用户 app 切到 V2.1 lab 后就能看到 — 是 packaging/发布问题, 不是开发问题) |

### 保留的判断 (仍正确)

| ✅ 仍正确 | 证据 |
|---|---|
| A 17c8814 跑分数字不在 V2.1 lab db | V2.1 lab db `app.db` 实测: approval_queue/agent_run_log/idempotency_keys_v25 表不存在, atomic_facts 5/23 后 +0 |
| A 流量在 `dogfood_real/` 本地 copy 跑的 | A `.gitignore` 加了 `dogfood_real/` |
| schema migration 没在 V2.1 lab db 跑 | 上面 3 张新表 `no such table` |

---

## 2 · V2.1 真实形态 (顾源源澄清后的正确理解)

```
现在:
  V2.1 仓库 = 实验下游 mirror (用 dev:lab 启 Electron, db 在 YiyuThinkTankWorkbench2_V21Lab/)
  主仓库   = 现在用户每天打开的 V2.0 app (db 在 YiyuThinkTankWorkbench2/)

V2.1 完成后:
  V2.1 = 新主仓库 (Mac app 切到 V2.1, 用户 app 装 V2.1)
  旧主仓库 = 历史归档

→ V2.1 lab db 就是"未来用户用的 db"
→ V2.1 backend 就是"未来用户用的 backend"
```

→ **B 之前用"主仓库 prod db" 当真相是错的, 应该用 V2.1 lab db**.

---

## 3 · V2.1 lab db 真实现状 (我刚 sqlite3 实测)

```
路径: ~/Library/Application Support/YiyuThinkTankWorkbench2_V21Lab/app.db (266 MB)

★ 现状:
  atomic_facts                  1998   (主仓库 2310)
  event_line_activities         104    (主仓库 104)
  risk_signals                  20     (主仓库 20)
  commitments                   66     (主仓库 66)
  strategic_thought_insights    18     (主仓库 18)
  fact_contradictions           81     (主仓库 81)
  clarification_records         0      (主仓库 0)
  external_evidence_cards       0
  event_log                     0      (主仓库 312)
  ai_episode_log                0      (主仓库 312)
  reasoning_traces              0      (主仓库 7)
  tasks                         256    (主仓库 238)

  approval_queue                no such table
  agent_run_log                 no such table
  idempotency_keys_v25          no such table
```

★ 关键发现:
- **V2.1 lab db 比主仓库 prod db 更落后** (event_log/ai_episode_log/reasoning_traces 全 0)
- **A V2.5 R2 新表 (approval_queue/agent_run_log/idempotency_keys_v25) 没建到 V2.1 lab db**
- A 17c8814 跑的 "R2 7/7" **既不在 V2.1 lab db, 也不在主仓库 prod db** — 是 A 临时 `dogfood_real/` 第三个 db

---

## 4 · 真 R2 客观评估 = "在 V2.1 lab db 跑通真测试"

### 阻塞项 (A 必须先做)

| # | 阻塞 | 谁做 | 工作量 |
|---|---|---|---|
| 1 | **V2.1 lab db schema migration** — 把 approval_queue/agent_run_log/idempotency_keys_v25 表建进去 | A | 0.5 小时 |
| 2 | **V2.1 lab db V2.4 派生器表 schema** — 跑 ensure_v23_schema + V2.4 新增字段 | A | 0.5 小时 |
| 3 | **V2.1 lab db backfill V2.5 P0-3 ChatMessageReverseIngester 一次** — 把现有 1125 chat_messages 转 atomic_facts | A | 1-2 小时 (LLM 调用) |
| 4 | **启动 V2.1 backend (port 47831)** — 让 B 能 HTTP 调 | 用户或 A 跑 npm run dev:lab | 0.5 小时 |
| 5 | **暴露 MeetingMinuteProcessor + agent_governance HTTP endpoint** — 当前 service 写好了, main.py 没 @app.post 暴露 | A | 0.5-1 小时 |
| 6 | **暴露 Data Gap API endpoint** (B-2 协商完了, A 实现) | A | 1-2 小时 |
| 7 | **暴露 Goal-Plan-Run 三件套 endpoint** (V3.0 P1) | A | 2-3 天 |

→ R2 真跑前 A 需要 **0.5-1 天**完成阻塞项 1-5 (schema + endpoint 暴露). 阻塞项 6-7 是 V3.0 P0a + P1, 不阻塞最小 R2.

### 最小 R2 (今天能跑)

如果 A 完成阻塞项 1-5 (0.5-1 天), B 立刻跑最小 R2:

```python
# scripts/run_v30_r2_minimal.py (B 临时写, 不依赖 V3.0 P0a/P1)
def minimal_r2_test():
    BASE = "http://localhost:47831"  # V2.1 backend
    hdr = {"X-Actor-Type": "external_ai_agent", "X-Actor-Id": "b-r2-minimal"}

    for client_name in ["日慈基金会", "益语智库", "善加基金会"]:
        client_id = lookup_client_id(client_name)

        # 调 A V2.5 R2 写好的 MeetingMinuteProcessor
        resp = httpx.post(
            f"{BASE}/api/v1/meeting-minutes/process",
            headers={**hdr, "X-Agent-Run-Id": f"r2_{uuid.uuid4().hex[:12]}"},
            json={
                "client_id": client_id,
                "meeting_text": GOLDEN_MEETING_TEXT.format(client=client_name),
                "mode": "draft",
            },
            timeout=300,
        )

        # verify V2.1 lab db 真有新数据
        new_facts = sqlite3_count("atomic_facts", client_id, since=run_start)
        new_clarifications = sqlite3_count("clarification_records", client_id, since=run_start)
        new_approvals_queued = sqlite3_count("approval_queue", client_id, since=run_start)
        ...

        # 100 分制 7 维度评分
```

### 完整 R2 (等 V3.0 P0a + P1)

跑 `scripts/run_v30_objective_eval.py` (B-3 设计的), 调 Goal-Plan-Run 三件套 + Data Gap API + Tool Registry + Approval Queue + Skill Manifest.

依赖 A 完成 V3.0 P0+P1 (3-5 天).

---

## 5 · 修正后的路径建议 (替代 d5bf241 方案 C)

### Phase 1 · 立刻 (今天 0.5-1 天)

A 做 5 件:
1. V2.1 lab db schema migration (approval_queue + agent_run_log + idempotency_keys_v25 + V2.4 派生器字段)
2. backfill V2.5 P0-3 (chat 1125 → atomic_facts)
3. 启动 V2.1 backend (用户跑 npm run dev:lab)
4. 暴露 MeetingMinuteProcessor endpoint (`POST /api/v1/meeting-minutes/process`)
5. 暴露 agent_governance endpoint (`GET /api/v1/approvals` 等)

完成后 B 跑**最小 R2 测试** (1-2 小时), 出"V2.1 = 未来主仓库" 真分数.

### Phase 2 · V3.0 P0+P1 (1 周)

A 继续 V3.0 P0 Data Gap API + X-Actor-Type middleware + P1 Goal-Plan-Run + Tool Registry + P2 Approval Queue + Skill Manifest.

不再纠结 cherry-pick — V2.1 = 未来主仓库, 直接在 V2.1 推就行.

### Phase 3 · R2 完整客观评估

B 跑 `scripts/run_v30_objective_eval.py`, 100 分制 7 维度 + 7 硬门槛 + 3 客户横向对比.

### Phase 4 · 切换 Mac 公证打包发布

V2.1 替代主仓库, 用户 app 切到 V2.1. (这是 packaging 工作, 不是开发)

---

## 6 · B 当前立刻能做的事 (不阻塞 A)

| # | B 任务 | 何时 |
|---|---|---|
| 1 | 把 d5bf241 报告里"主仓库 vs lab" 二分法**软删除** (本文 §1 公开撤回) | 现在 |
| 2 | 写 `scripts/run_v30_r2_minimal.py` 最小 R2 测试脚本 | 现在 0.5-1 天 |
| 3 | 跟 A 协商 V2.1 lab db schema migration 顺序 | 现在 |
| 4 | 等 A 暴露 endpoint 后立刻跑最小 R2 | 等 A 阻塞项 1-5 完成 |

---

## 7 · 一句话总结

V2.1 = 未来主仓库, A V2.4/V2.5/R2 都是真做.
**但 A 跑分流量在 dogfood_real/ snapshot, 不在 V2.1 lab db**.
**真 R2 客观评估 = 在 V2.1 lab db 跑通**, 需 A 先做 5 件阻塞项 (0.5-1 天 schema + backfill + endpoint 暴露).

跟 V2.5 ee50669 HONEST 教训一致: A 在临时 db 跑测试不算数, 必须**让 V2.1 lab db 这个"未来主仓库"自己长出数据**.

---

**Author**: AI B · 2026-05-23 09:05
**严肃建议给顾源源**: A 下个 commit 必须**让 V2.1 lab db 真有新数据** (schema migration + endpoint 暴露 + 跑 MeetingMinuteProcessor 真写入), 不允许再用 `dogfood_real/` snapshot 跑测试声称"R2 真验证".
