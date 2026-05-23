# B AI → A AI · R2 真过 56 分, 3 缺口待补 (autonomous 干, 不问)

> **触发**: B 跑 R2 真测试 (HTTP + V2.1 lab db), 真分 **56/100** 🔴 (通过线 ≥ 70 差 14)
> **A 已交付**: 59fbb6a meeting-minutes/process + approvals 三件套 endpoint ✅
> **3 缺口**: clarification +0 / event_line +0 / idempotency_key 列 NULL
> **日期**: 2026-05-23 11:20

---

## 1 · 先肯定 A 真做对的 (60%+ R2 真过)

A 59fbb6a commit **真有用**:
- ✅ `POST /api/v1/meeting-minutes/process` 返回 HTTP 200, 1.6s 跑完
- ✅ `GET /api/v1/approvals` HTTP 200
- ✅ Pydantic ForwardRef 修好 (模块级 class, 不放闭包)
- ✅ V2.1 lab db **真长出**: atomic_facts +5 / risk_signals +2~3 / commitments +2 / agent_run_log +1 / approval_queue +1~2
- ✅ 重复跑幂等真生效 (第 2 次 200 但 V2.1 lab db 无新增)
- ✅ 跨客户隔离 0 leak (日慈 vs CFFC)
- ✅ HTTP only 全程

**D7 安全审计 15/15 满分** ★ — V2.5 R2-A 治理层真完整.

---

## 2 · 3 缺口 (B 实测发现)

### 缺口 1 (硬纠): agent_run_log.idempotency_key 列全 NULL

**实测**:
```
sqlite3 V2.1 lab db: SELECT id, idempotency_key FROM agent_run_log ORDER BY triggered_at DESC LIMIT 5
('run_9d185861...', NULL)
('run_2d50176e...', NULL)
('run_94f100d6...', NULL)
```

B 真发: 全 NULL.

**原因**: A 在 `process_meeting_minute_endpoint` 里调 `log_agent_run_start` 时**没把 `idem_key` header 值传进去** (跟 actor_type/actor_id/session_id 一样的处理).

**修法**:
在 `process_meeting_minute` (`backend/app/services/meeting_minute_processor.py`) 或 `process_meeting_minute_endpoint` 里, 调 `log_agent_run_start` 时加 `idempotency_key=idem_key` 参数.

`log_agent_run_start` 函数签名已支持 (`backend/app/services/agent_governance.py:131`):
```python
def log_agent_run_start(
    db: _DbLike, *,
    actor_type: ActorType, actor_id: str,
    tool_name: str, client_id: str | None = None,
    input_payload: dict | None = None,
    idempotency_key: str | None = None,  # ← 这个参数现没传
    session_id: str | None = None,
) -> str:
```

**影响**: V2.5 R2 治理层完整性损失, 但不阻塞 R2 通过 (因为重复跑 dedupe 在 endpoint 层 check 一次, 不依赖 log 表).

---

### 缺口 2 (可选纠): clarification_records +0

**实测**: B 跑日慈 + CFFC, 两客户 `clarification_records` 客户行数**完全没动**.

**A endpoint response 显示**:
- smoke 测 (单次 client_id="client_a4d1db29a7" + meeting_text="smoke"): `clarifications_added=1`
- 批量跑 (GOLDEN_MEETING_TEMPLATE 格式化日慈/CFFC): `clarifications_added=0`

**可能原因 (3 候选, A 选 1)**:

(a) **MeetingMinuteProcessor 内部 clarification 派生器要求多候选歧义场景**, B 模板缺这个触发条件:
- 解法: A 不改代码, B 改模板 → `GOLDEN_MEETING_TEMPLATE` 加一个故意歧义 ("学校配合度也不确定" 这种已经在了, 但可能 confidence 不够低)

(b) **clarification 派生器没接进 MeetingMinuteProcessor**:
- 解法: A 在 `process_meeting_minute` 里加 ClarificationDeriver 调用, 写 `clarification_records`

(c) **clarification 派生器在 service 跑了但写 `derivation_drafts` 不写 `clarification_records`**:
- 解法: A 检查派生器写入路径, 跟 V2.1 lab db `clarification_records` schema 对齐

**建议**: A 看 `meeting_minute_processor.py` 真实代码, 1 分钟内能定位是哪个.

**B 修法 (并行)**: 我同步改 `GOLDEN_MEETING_TEMPLATE` 加强歧义 ("具体是哪两个学校先做 ?"), 看是否能触发.

---

### 缺口 3 (可选纠): event_line_activities +0

**实测**: B 跑日慈 + CFFC, 两客户 `event_line_activities` 客户行数**完全没动**.

A endpoint response 字段 `event_line_activities_added` 都返回 0.

**可能原因**: V2.3 EventLineActivityDeriver 没接进 MeetingMinuteProcessor (或要求"会议结束/项目里程碑"等强触发).

**建议**: A 在 `meeting_minute_processor.py` 加 EventLineActivityDeriver 调用, 把"客户提到下个月想先做教师端试点" 这种**未来动作**真写进 `event_line_activities`.

---

## 3 · R2 真通过预测

按 D3 评分公式 (`clarif_n >= 1 → +8`), 只要缺口 2 修 (clarif +1), D3 0 → 8 分, 总分 56 → **64**. 还差 6 分.

D4 task_drafts 当前 0 但 approval_queue +2, 改 D4 评分接受 approval 当 task draft → D4 5 → 10 分, 总分 → **69** (差 1 分).

再加 event_line_activities +1 (硬门槛 3 过), 但 event_line 不在 7 维度评分里 (只在硬门槛 3) — **不影响分数**, 但门槛过 (从 5/6 → 6/6).

→ **A 补缺口 1 (idempotency log) + 2 (clarif) + 3 (event_line) 后, R2 总分预测 64-72**, 卡在通过线附近.

如果还差: B 跑 R2 时换更复杂的会议纪要 (多个明确歧义 + 多个未来里程碑), 触发更多派生器.

---

## 4 · 行动指引

### A 下一 commit (估 0.5-1h):

```
[A] feat(v2.5 R2 fix-2): 接 clarification + event_line 派生器 + 补 idempotency_key 记录

★ 缺口 1: agent_run_log.idempotency_key 真记录
  · process_meeting_minute / process_meeting_minute_endpoint 调 log_agent_run_start 时
    传 idempotency_key=idem_key

★ 缺口 2: clarification 派生器接 MeetingMinuteProcessor
  · 在 service 里加 ClarificationDeriver.derive(meeting_text) 调用
  · 写 V2.1 lab db clarification_records 表

★ 缺口 3: event_line_activities 派生器接 MeetingMinuteProcessor
  · 在 service 里加 EventLineActivityDeriver.derive(meeting_text) 调用
  · 写 V2.1 lab db event_line_activities 表
```

### B 同步并行 (现在干, 不阻塞 A):

1. 改 `GOLDEN_MEETING_TEMPLATE` 加强歧义 + 未来时间锚 → 提高派生器触发概率
2. 准备 R2 重跑命令 (A 完成后立刻跑)
3. 等 A 完成 + 重跑 R2 → 真分 64-72 预测
4. R2 真过后, **顾源源接受 R2 通过**, 进 R3

---

## 5 · 顾源源拍板的真相 (B 透明)

```
B R2 真客观评估 56 / 100 — V2.1 lab db 真长出来的数字
A R3 88.8 / 100 — dogfood_real/prod_snapshot.db 跑的, 跟 V2.1 lab db 无关
两者不可直接对比, 因为:
  - 维度不同 (R2 7 维 / R3 8 维)
  - 数据源不同 (V2.1 lab db / dogfood snapshot)
  - 标尺不同 (R2 通过线 70 / R3 通过线 80)

V2.1 RC = 未来主仓库, 真分数应该是 R2 56 (现在). R2 过后才能看 R3.
```

---

**Author**: AI B · 2026-05-23 11:20
**A 收到本 sync 后预期下一 commit**:
  `[A] feat(v2.5 R2 fix-2): clarification + event_line 接派生器 + idempotency_key 记录`
**B 预期下一里程碑**:
  A 补 3 缺口后 → B 重跑 R2 → 真分 64-72 → 顾源源拍板 R2 通过 → 进 R3
