"""[A] V2.3 阶段 1 · A 补充 3 · 澄清优先级 5 维量化

服务: docs/V2.3_DATA_CENTER_MASTER_PLAN.md § 四 机制五

蓝图原话:
  澄清优先级 = 影响程度 × 冲突程度 × 当前行动依赖 × 时间紧迫度 × 置信度不足

A 补充 3 给每维 1-5 量化规则, 总分 1-3125, top-N 进澄清队列.

V2.3 阶段 3 落地时, 澄清队列 UI 按本 priority_score 排序.
"""
from __future__ import annotations

from typing import Any, Protocol


class _DbLike(Protocol):
    def fetchone(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchall(self, sql: str, params: tuple = ...) -> Any: ...


# ─── 5 维量化规则 ───────────────────────────────


def score_impact(db: _DbLike, fact_id: str, client_id: str) -> int:
    """D1 · 影响程度 (1-5).

    维度含义: 这条事实影响多大 — 客户活跃度 + 事实被引用次数

    规则:
        5: Top-3 客户 + 事实被 narrative/task/proposal 多处引用
        4: Top-3 客户 + 事实被引用 1-2 处
        3: 中部客户 + 事实被引用 ≥ 1 处
        2: 中部客户 + 事实未被引用
        1: 边缘客户 + 事实未被引用
    """
    # 客户活跃度: 看最近 30 天 atomic_facts 增量
    activity_row = db.fetchone(
        """SELECT COUNT(*) c FROM atomic_facts
           WHERE client_id = ? AND created_at > datetime('now', '-30 days')""",
        (client_id,),
    )
    activity = activity_row["c"] if activity_row else 0

    # 事实被引用次数 (粗估: 看 fact_id 在 derived_from_ids_json / reasoning_traces 等出现)
    ref_row = db.fetchone(
        """SELECT COUNT(*) c FROM atomic_facts
           WHERE derived_from_ids_json LIKE ? AND status='active'""",
        (f'%{fact_id}%',),
    )
    refs = ref_row["c"] if ref_row else 0

    # 综合打分
    if activity >= 100 and refs >= 3: return 5
    if activity >= 100 and refs >= 1: return 4
    if activity >= 30 and refs >= 1: return 3
    if activity >= 30: return 2
    return 1


def score_conflict(db: _DbLike, fact_id: str, client_id: str,
                   subject_text: str, attribute: str) -> int:
    """D2 · 冲突程度 (1-5).

    维度含义: 该事实跟其他源给出的值是否冲突

    规则:
        5: 同 (subject,attribute) 有 ≥3 个不同 value_text (强冲突)
        4: 同 (subject,attribute) 有 2 个不同 value_text + fact_contradictions 有记录
        3: 同 (subject,attribute) 有 2 个不同 value_text
        2: update_relation = 'conflict' 或 'supersedes'
        1: update_relation = 'none' (无冲突)
    """
    same_sa_rows = db.fetchall(
        """SELECT DISTINCT value_normalized FROM atomic_facts
           WHERE client_id = ? AND subject_text = ? AND attribute = ?
             AND status IN ('active', 'superseded')""",
        (client_id, subject_text, attribute),
    )
    distinct_values = len(same_sa_rows)

    # fact_contradictions 检查
    contradiction_row = db.fetchone(
        """SELECT COUNT(*) c FROM fact_contradictions
           WHERE fact_a_id = ? OR fact_b_id = ?""",
        (fact_id, fact_id),
    )
    has_contradiction = (contradiction_row["c"] if contradiction_row else 0) > 0

    fact_row = db.fetchone(
        "SELECT update_relation FROM atomic_facts WHERE id = ?",
        (fact_id,),
    )
    update_rel = fact_row["update_relation"] if fact_row else "none"

    if distinct_values >= 3: return 5
    if distinct_values == 2 and has_contradiction: return 4
    if distinct_values == 2: return 3
    if update_rel in ("conflict", "supersedes"): return 2
    return 1


def score_action_dependency(db: _DbLike, fact_id: str, client_id: str,
                           subject_text: str) -> int:
    """D3 · 当前行动依赖 (1-5).

    维度含义: 该事实是否被当前活跃任务/承诺/方案引用

    规则:
        5: ≥ 3 个进行中的 task 涉及该 subject
        4: 1-2 个进行中的 task + 1 个 commitment
        3: 1 个进行中的 task 或 1 个 commitment
        2: 只在已完成的历史中出现
        1: 无任何关联
    """
    active_task_rows = db.fetchone(
        """SELECT COUNT(*) c FROM tasks
           WHERE client_id = ? AND status NOT IN ('completed','archived')
             AND (title LIKE ? OR description LIKE ?)""",
        (client_id, f"%{subject_text}%", f"%{subject_text}%"),
    )
    active_tasks = active_task_rows["c"] if active_task_rows else 0

    active_commit_rows = db.fetchone(
        """SELECT COUNT(*) c FROM commitments
           WHERE client_id = ? AND status NOT IN ('done','cancelled')
             AND content LIKE ?""",
        (client_id, f"%{subject_text}%"),
    )
    active_commitments = active_commit_rows["c"] if active_commit_rows else 0

    if active_tasks >= 3: return 5
    if active_tasks >= 1 and active_commitments >= 1: return 4
    if active_tasks >= 1 or active_commitments >= 1: return 3
    # 历史关联
    history_rows = db.fetchone(
        """SELECT COUNT(*) c FROM tasks
           WHERE client_id = ? AND (title LIKE ? OR description LIKE ?)""",
        (client_id, f"%{subject_text}%", f"%{subject_text}%"),
    )
    history = history_rows["c"] if history_rows else 0
    if history > 0: return 2
    return 1


def score_time_urgency(db: _DbLike, fact_id: str, client_id: str,
                       subject_text: str) -> int:
    """D4 · 时间紧迫度 (1-5).

    维度含义: 涉及 due 时间 + due 距离当前多久

    规则:
        5: 7 天内有 due 的 task 涉及该 subject
        4: 30 天内有 due 的 task
        3: 90 天内有 due 的 task / 用户最近 7 天主动询问
        2: 90+ 天 due 或纯历史性事实
        1: 无 due 时间关联
    """
    # 7 天内 due
    urgent_7d = db.fetchone(
        """SELECT COUNT(*) c FROM tasks
           WHERE client_id = ? AND due_date BETWEEN datetime('now') AND datetime('now', '+7 days')
             AND status NOT IN ('completed','archived')
             AND (title LIKE ? OR description LIKE ?)""",
        (client_id, f"%{subject_text}%", f"%{subject_text}%"),
    )
    if (urgent_7d["c"] if urgent_7d else 0) > 0: return 5

    urgent_30d = db.fetchone(
        """SELECT COUNT(*) c FROM tasks
           WHERE client_id = ? AND due_date BETWEEN datetime('now') AND datetime('now', '+30 days')
             AND status NOT IN ('completed','archived')
             AND (title LIKE ? OR description LIKE ?)""",
        (client_id, f"%{subject_text}%", f"%{subject_text}%"),
    )
    if (urgent_30d["c"] if urgent_30d else 0) > 0: return 4

    urgent_90d = db.fetchone(
        """SELECT COUNT(*) c FROM tasks
           WHERE client_id = ? AND due_date BETWEEN datetime('now') AND datetime('now', '+90 days')
             AND status NOT IN ('completed','archived')
             AND (title LIKE ? OR description LIKE ?)""",
        (client_id, f"%{subject_text}%", f"%{subject_text}%"),
    )
    if (urgent_90d["c"] if urgent_90d else 0) > 0: return 3

    # 历史 due
    historical = db.fetchone(
        """SELECT COUNT(*) c FROM tasks
           WHERE client_id = ? AND due_date IS NOT NULL
             AND (title LIKE ? OR description LIKE ?)""",
        (client_id, f"%{subject_text}%", f"%{subject_text}%"),
    )
    if (historical["c"] if historical else 0) > 0: return 2
    return 1


def score_confidence_gap(db: _DbLike, fact_id: str) -> int:
    """D5 · 置信度不足 (1-5).

    维度含义: 置信度越低,越值得澄清

    规则:
        5: confidence < 0.3
        4: 0.3-0.5
        3: 0.5-0.7
        2: 0.7-0.85
        1: ≥ 0.85
    """
    fact_row = db.fetchone(
        "SELECT confidence FROM atomic_facts WHERE id = ?",
        (fact_id,),
    )
    if not fact_row: return 1
    conf = float(fact_row["confidence"] or 0.5)
    if conf < 0.3: return 5
    if conf < 0.5: return 4
    if conf < 0.7: return 3
    if conf < 0.85: return 2
    return 1


# ─── 综合公式 ──────────────────────────────────────


def calculate_priority(
    db: _DbLike,
    fact_id: str,
    client_id: str,
    subject_text: str,
    attribute: str,
) -> dict[str, Any]:
    """蓝图 § 四 机制五 公式: 影响 × 冲突 × 行动依赖 × 时间紧迫 × 置信度不足

    返回 dict:
        · score (int 1-3125)
        · breakdown (5 维各分)
        · suggested_action (basis: queue_top / queue_normal / skip)
    """
    d1 = score_impact(db, fact_id, client_id)
    d2 = score_conflict(db, fact_id, client_id, subject_text, attribute)
    d3 = score_action_dependency(db, fact_id, client_id, subject_text)
    d4 = score_time_urgency(db, fact_id, client_id, subject_text)
    d5 = score_confidence_gap(db, fact_id)

    score = d1 * d2 * d3 * d4 * d5  # 1 ~ 3125

    if score >= 500:
        suggested = "queue_top"      # top-N 进澄清队列首页
    elif score >= 100:
        suggested = "queue_normal"  # 进队列尾部
    elif score >= 30:
        suggested = "background"    # 后台慢慢澄清, 不打扰用户
    else:
        suggested = "skip"          # 不值得澄清

    return {
        "fact_id": fact_id,
        "score": score,
        "breakdown": {
            "d1_impact": d1,
            "d2_conflict": d2,
            "d3_action_dep": d3,
            "d4_time_urgency": d4,
            "d5_confidence_gap": d5,
        },
        "suggested_action": suggested,
    }


def top_n_clarifications_for_client(
    db: _DbLike, client_id: str, limit: int = 10
) -> list[dict[str, Any]]:
    """拉某客户 top-N 该澄清的事实.

    V2.3 阶段 3 高级澄清中心 UI 调用本函数填澄清队列.
    """
    # 拉 candidate facts (低置信 + 跨源印证 + status=active)
    candidates = db.fetchall(
        """SELECT id, subject_text, attribute, confidence, update_relation
           FROM atomic_facts
           WHERE client_id = ? AND status = 'active'
             AND (confidence < 0.85 OR update_relation IN ('conflict', 'supersedes'))
           ORDER BY confidence ASC LIMIT 100""",
        (client_id,),
    )

    scored = []
    for f in candidates:
        result = calculate_priority(
            db, str(f["id"]), client_id,
            str(f["subject_text"] or ""), str(f["attribute"] or ""),
        )
        scored.append(result)

    scored.sort(key=lambda x: -x["score"])
    return scored[:limit]
