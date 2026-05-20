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

    # 源 2 · action_items (会议待办, draft + published 都拉; 排除明显占位符 + 已 dismiss/completed)
    try:
        rows = db.fetchall(
            """SELECT ai.id, ai.title, ai.owner_name, ai.due_date,
                      m.title AS meeting_title, ai.publish_status
               FROM action_items ai
               JOIN meetings m ON m.id = ai.meeting_id
               WHERE m.client_id = ?
                 AND ai.title NOT LIKE '%补齐%'
                 AND ai.title NOT LIKE '%占位%'
                 AND (ai.publish_status IS NULL OR ai.publish_status NOT IN ('completed', 'dismissed'))""",
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
    # W3:走 CommitmentRepository (SSOT),不再裸 SQL
    try:
        from app.modules.commitment import get_commitment_repository
        commitments = get_commitment_repository(db).list_pending_for_client(client_id)
        for c in commitments:
            committer = c.committer
            recipient = c.recipient
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
            due = c.deadline or ""
            out.append(UnifiedTodo(
                id=f"commit:{c.id}",
                source="commitment",
                title=f"{committer} 向 {recipient}: {c.content}",
                owner=committer,
                due_date=due,
                status="pending",
                direction=direction,
                related_to=c.commitment_type or "delivery",
                raw_id=c.id,
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
    """归一化标题用于去重: 去标点/空白/方向前缀/常见客户名/冗余动作词."""
    import re
    s = (title or "").strip()
    # 去掉 "X 向 Y:" / "X → Y:" 等承诺类前缀
    s = re.sub(r"^[^:：]+[:：]\s*", "", s)
    # 去掉所有标点和空白
    s = re.sub(r"[\s，。、；：:,.;\-—!\?\(\)\[\]【】《》""''「」]+", "", s)
    # 去掉 LLM 反复重复的客户名词缀 (例: '完成日慈一季度' / '完成日慈基金会一季度' / '完成一季度' 归一为 '完成一季度')
    # 通用化: 任意 2-4 字"X+基金会|公益|协会|学院|项目" 都视为同一客户实体, 抹掉
    s = re.sub(r"[一-龥]{2,4}(基金会|公益|协会|学院|项目|集团|公司)", "", s)
    return s.lower()


def _normalize_owner_for_match(owner: str) -> str:
    """归一化承诺人, 解决"顾老师 / 顾源源"同人问题.

    规则:
      - 去掉常见称谓后缀 (老师/总/总监/经理/同学)
      - 仅保留中文名核心 2-3 字
      - 用于 owner 等价判断时的 fallback (优先看 entities 别名表, 没匹配再用此规则)
    """
    import re
    s = (owner or "").strip()
    s = re.sub(r"(老师|总监|经理|主管|同学|总裁|总|博士|教授)$", "", s)
    return s.lower()


def _title_similar(a: str, b: str, *, threshold: float = 0.5) -> bool:
    """标题相似度: 归一化后, 一方包含另一方 或 字符级重叠 ≥ threshold.

    默认阈值 0.5 (放宽口径): 用户原则是"宁可多提醒, 错了也不漏提醒"。
    """
    na = _normalize_title_for_match(a)
    nb = _normalize_title_for_match(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    set_a, set_b = set(na), set(nb)
    overlap = len(set_a & set_b)
    smaller = min(len(set_a), len(set_b))
    if smaller >= 4 and overlap / smaller >= threshold:
        return True
    return False


_SOURCE_PRIORITY = {"task": 0, "commitment": 1, "meeting_action": 2}


def _dedupe_todos(todos: list[UnifiedTodo]) -> list[UnifiedTodo]:
    """跨 3 源去重: 三档判定, 保留优先级最高的 (task > commitment > meeting_action).

    判定档位 (从严到宽):
      1. 强合并: 标题归一化后完全相等 → 合并 (不要求 owner/due 也等)
         覆盖场景: '完成日慈一季度...' vs '完成一季度...' 客户名词缀归一抹掉后相同
      2. 中合并: owner 归一化等价 (顾老师↔顾源源) + 标题相似 → 合并
      3. 弱合并: owner 严格等 或 due_date 严格等, 再加标题相似 → 合并 (老逻辑)

    机制化保证: 任何客户调用 collect_all_todos 都自动去重, 不需要前端处理.
    """
    if not todos:
        return []
    keep: list[UnifiedTodo] = []
    used: set[int] = set()
    for i, a in enumerate(todos):
        if i in used:
            continue
        cluster: list[tuple[int, UnifiedTodo]] = [(i, a)]
        na = _normalize_title_for_match(a.title)
        oa = _normalize_owner_for_match(a.owner or "")
        for j in range(i + 1, len(todos)):
            if j in used:
                continue
            b = todos[j]
            nb = _normalize_title_for_match(b.title)
            ob = _normalize_owner_for_match(b.owner or "")
            merged = False
            # 档 1: 归一标题完全相等 → 强合并
            if na and nb and na == nb:
                merged = True
            # 档 2: owner 归一相等 + 标题相似
            elif oa and ob and oa == ob and _title_similar(a.title, b.title):
                merged = True
            # 档 3: owner 严格相等 或 due 严格相等 + 标题相似 (老逻辑)
            else:
                owner_match = bool(a.owner) and bool(b.owner) and a.owner == b.owner
                due_match = bool(a.due_date) and bool(b.due_date) and a.due_date == b.due_date
                if (owner_match or due_match) and _title_similar(a.title, b.title):
                    merged = True
            if merged:
                cluster.append((j, b))
                used.add(j)
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
