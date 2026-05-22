"""[A] V2.3 阶段 4 P0 · story_card_generator · 项目故事卡 10 段 markdown 生成

服务: docs/V2.3_DATA_CENTER_MASTER_PLAN.md § 九 项目故事卡

蓝图 10 段:
  1. 项目背景
  2. 当前阶段
  3. 关键人物
  4. 时间线
  5. 核心事实
  6. 关键判断
  7. 冲突与待澄清
  8. 风险
  9. 下一步
  10. 证据来源

输入: client_id
输出: markdown 字符串 (用户直接 review)

V2.3 阶段 4 真用户感: 不用翻 100 个文件, 也能知道一个项目到底发生了什么, 现在怎么看, 下一步怎么做.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol


class _DbLike(Protocol):
    def fetchone(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchall(self, sql: str, params: tuple = ...) -> Any: ...


# ─── 10 段 各自 builder ────────────────────────────


def _section_1_background(db: _DbLike, client_id: str) -> str:
    """段 1 · 项目背景."""
    client = db.fetchone(
        "SELECT name, alias, intro, stage FROM clients WHERE id = ?",
        (client_id,),
    )
    if not client:
        return "_(无客户基本信息)_"
    name = client["name"] or ""
    intro = (client["intro"] or "")[:300]
    stage = client["stage"] or "?"
    return f"**{name}** · 阶段: {stage}\n\n{intro}"


def _section_2_current_phase(db: _DbLike, client_id: str) -> str:
    """段 2 · 当前阶段 — 看最近 event_lines + active tasks."""
    el_rows = db.fetchall(
        """SELECT name, stage, status, current_blocker, next_step
           FROM event_lines WHERE primary_client_id = ?
           ORDER BY updated_at DESC LIMIT 5""",
        (client_id,),
    )
    active_task_count = db.fetchone(
        """SELECT COUNT(*) c FROM tasks
           WHERE client_id = ? AND status NOT IN ('completed','archived')""",
        (client_id,),
    )
    lines = []
    for el in el_rows:
        lines.append(f"- **{el['name']}** · {el['stage']} · {el['status']}")
        if el['current_blocker']:
            lines.append(f"  - 卡点: {el['current_blocker'][:80]}")
        if el['next_step']:
            lines.append(f"  - 下一步: {el['next_step'][:80]}")
    lines.append(f"\n_活跃任务: {active_task_count['c'] if active_task_count else 0} 条_")
    return "\n".join(lines) if lines else "_(无活跃事件线)_"


def _section_3_key_people(db: _DbLike, client_id: str) -> str:
    """段 3 · 关键人物 — entities + atomic_facts (新任职务/角色)."""
    # atomic_facts 含 attribute='职务/角色' 的人物
    rows = db.fetchall(
        """SELECT DISTINCT subject_text, attribute, value_text
           FROM atomic_facts
           WHERE client_id = ?
             AND (attribute LIKE '%职务%' OR attribute LIKE '%角色%'
                  OR attribute LIKE '%新任%' OR attribute LIKE '%接任%')
             AND status = 'active' LIMIT 15""",
        (client_id,),
    )
    if not rows:
        return "_(无关键人物职务变更记录)_"
    lines = []
    for r in rows:
        lines.append(f"- **{r['subject_text']}** · {r['attribute']} = {r['value_text'][:80]}")
    return "\n".join(lines)


def _section_4_timeline(db: _DbLike, client_id: str) -> str:
    """段 4 · 时间线 — event_line_activities + meetings."""
    rows = db.fetchall(
        """SELECT a.happened_at, a.actor_name, a.title
           FROM event_line_activities a
           JOIN event_lines el ON el.id = a.event_line_id
           WHERE el.primary_client_id = ? AND a.happened_at IS NOT NULL
           ORDER BY a.happened_at DESC LIMIT 15""",
        (client_id,),
    )
    if not rows:
        return "_(无时间线活动)_"
    lines = []
    for r in rows:
        date = (r['happened_at'] or '')[:10]
        actor = r['actor_name'] or 'sys'
        title = (r['title'] or '')[:80]
        lines.append(f"- **{date}** · {actor}: {title}")
    return "\n".join(lines)


def _section_5_core_facts(db: _DbLike, client_id: str) -> str:
    """段 5 · 核心事实 — atomic_facts 高置信."""
    rows = db.fetchall(
        """SELECT subject_text, attribute, value_text, confidence
           FROM atomic_facts
           WHERE client_id = ? AND confidence >= 0.85 AND status = 'active'
           ORDER BY confidence DESC, created_at DESC LIMIT 20""",
        (client_id,),
    )
    if not rows:
        return "_(无高置信事实)_"
    lines = []
    for r in rows:
        lines.append(
            f"- **{r['subject_text'][:20]}** · {r['attribute'][:20]} = "
            f"{(r['value_text'] or '')[:60]} _(conf {r['confidence']:.2f})_"
        )
    return "\n".join(lines)


def _section_6_key_judgments(db: _DbLike, client_id: str) -> str:
    """段 6 · 关键判断 — strategic_thought_insights."""
    rows = db.fetchall(
        """SELECT title, insight_type, insight_text, recommended_action
           FROM strategic_thought_insights
           WHERE client_id = ? AND is_deleted = 0
           ORDER BY created_at DESC LIMIT 8""",
        (client_id,),
    )
    if not rows:
        return "_(无关键判断记录)_"
    lines = []
    for r in rows:
        lines.append(f"- **{r['title'][:60]}** _{r['insight_type']}_")
        if r['insight_text']:
            lines.append(f"  - {(r['insight_text'] or '')[:120]}")
        if r['recommended_action']:
            lines.append(f"  - 推荐: {(r['recommended_action'] or '')[:80]}")
    return "\n".join(lines)


def _section_7_conflicts_to_clarify(db: _DbLike, client_id: str) -> str:
    """段 7 · 冲突与待澄清 — clarification_records pending + fact_contradictions."""
    clar_rows = db.fetchall(
        """SELECT question, slot_key FROM clarification_records
           WHERE scope_type = 'client' AND scope_id = ? AND status = 'pending'
           ORDER BY created_at DESC LIMIT 10""",
        (client_id,),
    )
    contr_rows = db.fetchall(
        """SELECT contradiction_type, severity, resolution_note
           FROM fact_contradictions
           WHERE client_id = ? AND review_status = 'pending'
           LIMIT 5""",
        (client_id,),
    )
    lines = []
    if clar_rows:
        lines.append("**澄清队列 (跨源嫌疑)**:")
        for r in clar_rows:
            lines.append(f"- {r['question'][:120]}")
    if contr_rows:
        lines.append("\n**事实冲突**:")
        for r in contr_rows:
            lines.append(f"- {r['contradiction_type']} ({r['severity']}): {(r['resolution_note'] or '')[:80]}")
    return "\n".join(lines) if lines else "_(无待澄清)_"


def _section_8_risks(db: _DbLike, client_id: str) -> str:
    """段 8 · 风险."""
    rows = db.fetchall(
        """SELECT title, signal_kind, severity, description
           FROM risk_signals
           WHERE client_id = ? AND status = 'active'
           ORDER BY severity DESC LIMIT 8""",
        (client_id,),
    )
    if not rows:
        return "_(无活跃风险信号)_"
    lines = []
    for r in rows:
        lines.append(
            f"- **{r['title']}** · {r['signal_kind']} · 严重度 {r['severity']}\n"
            f"  - {(r['description'] or '')[:100]}"
        )
    return "\n".join(lines)


def _section_9_next_steps(db: _DbLike, client_id: str) -> str:
    """段 9 · 下一步 — active tasks + open commitments + event_lines.next_step."""
    task_rows = db.fetchall(
        """SELECT title, owner_name, due_date FROM tasks
           WHERE client_id = ? AND status NOT IN ('completed','archived')
           ORDER BY due_date LIMIT 8""",
        (client_id,),
    )
    commit_rows = db.fetchall(
        """SELECT committer, recipient, content, deadline FROM commitments
           WHERE client_id = ? AND status NOT IN ('done','cancelled')
           LIMIT 5""",
        (client_id,),
    )
    lines = []
    if task_rows:
        lines.append("**待办任务**:")
        for r in task_rows:
            due = (r['due_date'] or '')[:10]
            lines.append(f"- {r['title'][:60]} · {r['owner_name']} {('· ' + due) if due else ''}")
    if commit_rows:
        lines.append("\n**承诺**:")
        for r in commit_rows:
            lines.append(f"- {r['committer']} → {r['recipient']}: {(r['content'] or '')[:80]}")
    return "\n".join(lines) if lines else "_(无待办)_"


def _section_10_evidence_sources(db: _DbLike, client_id: str) -> str:
    """段 10 · 证据来源 — source_registry + v2_documents."""
    doc_count = db.fetchone(
        "SELECT COUNT(*) c FROM v2_documents WHERE client_id = ?",
        (client_id,),
    )
    fact_count = db.fetchone(
        "SELECT COUNT(*) c FROM atomic_facts WHERE client_id = ?",
        (client_id,),
    )
    # source_registry 可能没数据/没建表 (V2.3 阶段 1 P2 接通后才有)
    try:
        sr_count_row = db.fetchone(
            "SELECT COUNT(*) c FROM source_registry WHERE client_id = ?",
            (client_id,),
        )
        sr_count = sr_count_row["c"] if sr_count_row else 0
    except Exception:
        sr_count = 0  # 表不存在 (旧 db)

    lines = [
        f"- v2_documents: {doc_count['c']} 份",
        f"- atomic_facts: {fact_count['c']} 条",
        f"- source_registry: {sr_count} 条 (V2.3 阶段 1 接通后填充)",
    ]
    return "\n".join(lines)


# ─── 主入口 ────────────────────────────────────────


def generate_story_card(db: _DbLike, client_id: str) -> str:
    """生成项目故事卡 markdown (10 段)."""
    client = db.fetchone("SELECT name FROM clients WHERE id = ?", (client_id,))
    client_name = client["name"] if client else client_id

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    sections = [
        ("1️⃣ 项目背景", _section_1_background(db, client_id)),
        ("2️⃣ 当前阶段", _section_2_current_phase(db, client_id)),
        ("3️⃣ 关键人物", _section_3_key_people(db, client_id)),
        ("4️⃣ 时间线", _section_4_timeline(db, client_id)),
        ("5️⃣ 核心事实", _section_5_core_facts(db, client_id)),
        ("6️⃣ 关键判断", _section_6_key_judgments(db, client_id)),
        ("7️⃣ 冲突与待澄清", _section_7_conflicts_to_clarify(db, client_id)),
        ("8️⃣ 风险", _section_8_risks(db, client_id)),
        ("9️⃣ 下一步", _section_9_next_steps(db, client_id)),
        ("🔟 证据来源", _section_10_evidence_sources(db, client_id)),
    ]

    md = [f"# 📋 项目故事卡 · {client_name}\n"]
    md.append(f"_生成时间: {now}_  \n_客户 ID: `{client_id}`_  \n")
    md.append("> 顾源源 5/22 蓝图 § 九 钦定 10 段产品形态\n")
    md.append("---\n")
    for title, content in sections:
        md.append(f"## {title}\n")
        md.append(content)
        md.append("\n")

    return "\n".join(md)
