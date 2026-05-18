"""统一待办聚合 service.

数据中心的核心职责之一: 把"下一步要做什么" 跨表 union 起来, 给工作台/任务页/chat
等模块**统一消费**.

来源:
  1. tasks (progress_status='todo') — 主待办源, 用户手动建/AI 抽
  2. action_items — 会议待办 (含 draft, 因为 publish 流程没跑通)
  3. commitments (status='pending') — 字典承诺, 双向 (committer→recipient)

返回统一 schema, 含 source / due_date / priority, 让 UI 统一渲染.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Literal


TodoSource = Literal["task", "meeting_action", "commitment"]


@dataclass(frozen=True)
class UnifiedTodo:
    id: str                    # 原表 id, 前缀区分: task:xxx / action:xxx / commit:xxx
    source: TodoSource         # task / meeting_action / commitment
    title: str                 # 待办描述
    owner: str                 # 负责人 (空字符串表示未指派)
    due_date: str              # YYYY-MM-DD 或自由文本 ("本周"/"已完成"/"暂无 deadline")
    status: str                # pending / draft / overdue (统一抽象)
    direction: str             # 仅 commitment 用: 我方→客户 / 客户→我方 / 内部
    related_to: str            # 关联实体 (会议名/项目名/合同, 用于 context)
    raw_id: str                # 原表的真 id, 用于回写
    severity: str              # high / medium / low (按 due_date 临近度算)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _today_str() -> str:
    from datetime import date
    return date.today().isoformat()


def _severity_by_due(due: str) -> str:
    """due_date 越近 severity 越高. 自由文本一律 medium."""
    if not due or len(due) < 10 or due[4] != "-":
        return "medium"
    today = _today_str()
    if due < today:
        return "high"  # overdue
    # diff in days (simple lexicographic for ISO date works 99%)
    from datetime import date
    try:
        d_due = date.fromisoformat(due[:10])
        d_today = date.fromisoformat(today)
        days = (d_due - d_today).days
        if days <= 7:
            return "high"
        if days <= 30:
            return "medium"
        return "low"
    except Exception:
        return "medium"


def collect_all_todos(db: Any, client_id: str) -> list[UnifiedTodo]:
    """跨 3 源拉所有待办, 按 severity + due_date 排序."""
    out: list[UnifiedTodo] = []

    # 源 1 · tasks (progress_status='todo')
    try:
        rows = db.fetchall(
            """SELECT id, title, owner_name, due_date, source_type, event_line_id
               FROM tasks
               WHERE client_id=? AND progress_status='todo'""",
            (client_id,),
        )
        for r in rows:
            due = str(r["due_date"] or "")
            out.append(UnifiedTodo(
                id=f"task:{r['id']}",
                source="task",
                title=str(r["title"] or ""),
                owner=str(r["owner_name"] or ""),
                due_date=due,
                status="pending",
                direction="内部",
                related_to=str(r["source_type"] or "manual"),
                raw_id=str(r["id"]),
                severity=_severity_by_due(due),
            ))
    except Exception:
        pass

    # 源 2 · action_items (会议待办, draft + published 都拉; 排除明显占位符)
    try:
        rows = db.fetchall(
            """SELECT ai.id, ai.title, ai.owner_name, ai.due_date,
                      m.title AS meeting_title, ai.publish_status
               FROM action_items ai
               JOIN meetings m ON m.id = ai.meeting_id
               WHERE m.client_id = ?
                 AND ai.title NOT LIKE '%补齐%'
                 AND ai.title NOT LIKE '%占位%'""",
            (client_id,),
        )
        for r in rows:
            due = str(r["due_date"] or "")
            out.append(UnifiedTodo(
                id=f"action:{r['id']}",
                source="meeting_action",
                title=str(r["title"] or ""),
                owner=str(r["owner_name"] or ""),
                due_date=due,
                status=str(r["publish_status"] or "draft"),
                direction="内部",
                related_to=f"会议: {r['meeting_title']}",
                raw_id=str(r["id"]),
                severity=_severity_by_due(due),
            ))
    except Exception:
        pass

    # 源 3 · commitments (pending) — 区分方向
    try:
        rows = db.fetchall(
            """SELECT id, committer, recipient, content, deadline, status, commitment_type
               FROM commitments
               WHERE client_id=? AND status='pending'""",
            (client_id,),
        )
        for r in rows:
            committer = str(r["committer"] or "")
            recipient = str(r["recipient"] or "")
            # 简单判方向: 含"益语/顾源源/...XX 老师" 类的算我方, 否则按字面
            our_side_keywords = ["益语", "顾源源", "顾老师", "陪伴", "智库"]
            committer_is_ours = any(k in committer for k in our_side_keywords)
            recipient_is_ours = any(k in recipient for k in our_side_keywords)
            if committer_is_ours and not recipient_is_ours:
                direction = "我方→客户"
            elif recipient_is_ours and not committer_is_ours:
                direction = "客户→我方"
            else:
                direction = "双方"
            due = str(r["deadline"] or "")
            out.append(UnifiedTodo(
                id=f"commit:{r['id']}",
                source="commitment",
                title=f"{committer} 向 {recipient}: {r['content']}",
                owner=committer,
                due_date=due,
                status="pending",
                direction=direction,
                related_to=str(r["commitment_type"] or "delivery"),
                raw_id=str(r["id"]),
                severity=_severity_by_due(due),
            ))
    except Exception:
        pass

    # 机制化 dedup: 同一件事跨 3 源出现 → 合并, 优先级 task > commitment > meeting_action
    out = _dedupe_todos(out)

    # 排序: severity (high > medium > low) → due_date 升序 (近的在前)
    severity_order = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda t: (severity_order.get(t.severity, 1), t.due_date or "9999-99-99"))
    return out


def _normalize_title_for_match(title: str) -> str:
    """归一化标题用于去重: 去标点/空白/方向前缀."""
    import re
    s = (title or "").strip()
    # 去掉 "X 向 Y:" / "X → Y:" 等承诺类前缀
    s = re.sub(r"^[^:：]+[:：]\s*", "", s)
    # 去掉所有标点和空白
    s = re.sub(r"[\s，。、；：:,.;\-—!\?\(\)\[\]【】《》""''「」]+", "", s)
    return s.lower()


def _title_similar(a: str, b: str) -> bool:
    """简单标题相似度: 归一化后, 一方完全包含另一方 或 重叠 ≥70%."""
    na = _normalize_title_for_match(a)
    nb = _normalize_title_for_match(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    # 字符级重叠
    set_a, set_b = set(na), set(nb)
    overlap = len(set_a & set_b)
    smaller = min(len(set_a), len(set_b))
    if smaller >= 5 and overlap / smaller >= 0.7:
        return True
    return False


_SOURCE_PRIORITY = {"task": 0, "commitment": 1, "meeting_action": 2}


def _dedupe_todos(todos: list[UnifiedTodo]) -> list[UnifiedTodo]:
    """跨 3 源去重: 同 owner + 同 due_date + 标题相似 → 保留优先级最高的.

    机制化保证: 任何客户调用 collect_all_todos 都自动去重, 不需要前端处理.
    """
    if not todos:
        return []
    # 按 (owner, due_date) 分组, 组内做相似度匹配
    keep: list[UnifiedTodo] = []
    used: set[int] = set()
    for i, a in enumerate(todos):
        if i in used:
            continue
        cluster: list[tuple[int, UnifiedTodo]] = [(i, a)]
        for j in range(i + 1, len(todos)):
            if j in used:
                continue
            b = todos[j]
            # 同 owner 或同 due_date (二选一即足够候选), 然后看标题
            owner_match = a.owner and b.owner and a.owner == b.owner
            due_match = a.due_date and b.due_date and a.due_date == b.due_date
            if not (owner_match or due_match):
                continue
            if _title_similar(a.title, b.title):
                cluster.append((j, b))
                used.add(j)
        # 从 cluster 里选优先级最高的 (task > commitment > meeting_action)
        cluster.sort(key=lambda x: _SOURCE_PRIORITY.get(x[1].source, 9))
        keep.append(cluster[0][1])
        used.add(i)
    return keep


def summarize_todos_for_chat(db: Any, client_id: str, max_items: int = 15) -> str:
    """给 chat raw_evidence_pack 用 — 把待办格式化成可读 markdown."""
    todos = collect_all_todos(db, client_id)
    if not todos:
        return ""
    top = todos[:max_items]
    lines = [f"# 客户待办清单 (共 {len(todos)} 条, 显示前 {len(top)} 条)"]
    by_src = {"task": "📋 任务", "meeting_action": "🎤 会议待办", "commitment": "🤝 承诺"}
    for t in top:
        sev_icon = "🔴" if t.severity == "high" else ("🟡" if t.severity == "medium" else "🟢")
        due_str = f" · 截至 {t.due_date}" if t.due_date else ""
        owner_str = f" · {t.owner}" if t.owner else ""
        lines.append(f"  {sev_icon} [{by_src.get(t.source, t.source)}] {t.title}{owner_str}{due_str}")
    return "\n".join(lines)
