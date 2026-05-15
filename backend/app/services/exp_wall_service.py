"""组织经验墙 service 层。

设计原则参见 memory：
- project-yiyu-growth-principle：卷 + 清晰秩序 = 安全感
- project-yiyu-seamless-learning：无感学习（用户不做额外动作）
- project-yiyu-surface-equality：UI 表面平等，算法 leader 加权
- project-yiyu-exp-wall-rules：具体规则（数据源/积分/删除权）

公开 API：
- insert_quote(...)                       AI runner 写入金句
- list_feed(...)                          前端拉信息流（latest/hot/category）
- get_user_reactions(...)                 拉某个用户对一批金句的点赞/收藏状态
- toggle_reaction(...)                    点赞/取消、收藏/取消
- delete_quote(...)                       删除（含权限校验）
- count_contribution_by_user(...)         按用户聚合贡献分（给其他模块的排行用）

不公开 API：
- _recompute_scores(...)                  互动后重算贡献分 + 热度
- _resolve_user_tier(...)                 ceo/leader/member
- _weight_for_tier(...)                   1.5 / 1.2 / 1.0
"""
from __future__ import annotations

import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Literal

from app.db import Database

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# 常量 / 配置
# ──────────────────────────────────────────────────────────────────

ROLE_TIER_CEO = "ceo"
ROLE_TIER_LEADER = "leader"
ROLE_TIER_MEMBER = "member"

REACTION_LIKE = "like"
REACTION_SAVE = "save"
REACTION_TYPES = frozenset({REACTION_LIKE, REACTION_SAVE})

CATEGORIES = (
    "项目推进", "客户沟通", "风险识别",
    "方法论", "团队协作", "判断决策",
)
DEFAULT_CATEGORY = "方法论"

SOURCE_TYPES = frozenset({"task", "meeting", "document", "client_analysis", "ai_chat"})

# 加权（表面平等，算法不平等）。改这里就改了规则，UI 永远展示真实数字
TIER_WEIGHTS: dict[str, float] = {
    ROLE_TIER_CEO: 1.5,
    ROLE_TIER_LEADER: 1.2,
    ROLE_TIER_MEMBER: 1.0,
}

# 积分公式：基础分（推到墙）+ 互动溢价（被点赞/收藏）
PUSH_BASE_SCORE = 5.0     # 推上来即得 +5
LIKE_BASE_SCORE = 1.0     # 每次点赞基础 +1
SAVE_BASE_SCORE = 5.0     # 每次收藏基础 +5（更重的认可）


# ──────────────────────────────────────────────────────────────────
# 数据类
# ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class QuoteRecord:
    id: str
    author_user_id: str
    author_name: str            # JOIN 来的
    author_role: str            # JOIN 来的，UI 展示用
    quote_text: str
    source_excerpt: str
    source_type: str
    source_object_id: str
    category: str
    status: str
    like_count: int
    save_count: int
    contribution_score: float
    hot_score: float
    created_at: str
    extracted_at: str


# ──────────────────────────────────────────────────────────────────
# 工具
# ──────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_id() -> str:
    return f"qt_{uuid.uuid4().hex[:12]}"


def _weight_for_tier(tier: str | None) -> float:
    return TIER_WEIGHTS.get((tier or "").strip().lower(), 1.0)


def _resolve_user_tier(db: Database, user_id: str) -> str:
    row = db.fetchone(
        "SELECT role_tier FROM operators WHERE id = ?",
        (user_id,),
    )
    if not row:
        return ROLE_TIER_MEMBER
    return str(row["role_tier"] or ROLE_TIER_MEMBER)


def _row_to_quote(row: sqlite3.Row) -> QuoteRecord:
    return QuoteRecord(
        id=str(row["id"]),
        author_user_id=str(row["author_user_id"]),
        author_name=str(row["author_name"] or ""),
        author_role=str(row["author_role"] or ""),
        quote_text=str(row["quote_text"]),
        source_excerpt=str(row["source_excerpt"] or ""),
        source_type=str(row["source_type"]),
        source_object_id=str(row["source_object_id"] or ""),
        category=str(row["category"] or DEFAULT_CATEGORY),
        status=str(row["status"] or "active"),
        like_count=int(row["like_count"] or 0),
        save_count=int(row["save_count"] or 0),
        contribution_score=float(row["contribution_score"] or 0),
        hot_score=float(row["hot_score"] or 0),
        created_at=str(row["created_at"] or ""),
        extracted_at=str(row["extracted_at"] or ""),
    )


# ──────────────────────────────────────────────────────────────────
# 写入：AI runner 调用
# ──────────────────────────────────────────────────────────────────


def insert_quote(
    db: Database,
    *,
    author_user_id: str,
    quote_text: str,
    source_excerpt: str,
    source_type: str,
    source_object_id: str = "",
    category: str = DEFAULT_CATEGORY,
    now: str | None = None,
) -> str:
    """AI 提取 + 润色后调用此函数自动推送到组织墙。

    幂等性：调用方应当用 (author_user_id, source_type, source_object_id, quote_text)
    哈希判重；本函数不主动 dedup（让上层决定）。

    返回新金句 id。
    """
    if not quote_text or not quote_text.strip():
        raise ValueError("quote_text 不能为空")
    if source_type not in SOURCE_TYPES:
        raise ValueError(f"source_type 必须是 {SOURCE_TYPES}, 实际：{source_type!r}")
    if category not in CATEGORIES:
        category = DEFAULT_CATEGORY

    quote_id = _new_id()
    timestamp = now or _now_iso()

    db.execute(
        """
        INSERT INTO exp_wall_quotes (
            id, author_user_id, quote_text, source_excerpt,
            source_type, source_object_id, category, status,
            like_count, save_count, contribution_score, hot_score,
            extracted_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'active', 0, 0, ?, ?, ?, ?, ?)
        """,
        (
            quote_id, author_user_id, quote_text.strip(), source_excerpt,
            source_type, source_object_id, category,
            PUSH_BASE_SCORE, PUSH_BASE_SCORE,  # 初始分 = 基础分
            timestamp, timestamp, timestamp,
        ),
    )
    return quote_id


# ──────────────────────────────────────────────────────────────────
# 读取：信息流
# ──────────────────────────────────────────────────────────────────


def list_feed(
    db: Database,
    *,
    sort: Literal["hot", "latest"] = "hot",
    category: str | None = None,
    limit: int = 30,
    offset: int = 0,
) -> list[QuoteRecord]:
    """拉取信息流。

    - sort='hot'：按 hot_score 降序（CEO/leader 加权后的排序）
    - sort='latest'：按 created_at 降序
    - category 为 None 时全部分类
    """
    where = ["q.status = 'active'"]
    params: list[object] = []
    if category and category in CATEGORIES:
        where.append("q.category = ?")
        params.append(category)
    clause = " AND ".join(where)

    order = "q.hot_score DESC, q.created_at DESC" if sort == "hot" else "q.created_at DESC"
    clipped_limit = max(1, min(200, int(limit)))
    clipped_offset = max(0, int(offset))

    rows = db.fetchall(
        f"""
        SELECT q.*,
               op.name AS author_name,
               op.role AS author_role
        FROM exp_wall_quotes q
        LEFT JOIN operators op ON op.id = q.author_user_id
        WHERE {clause}
        ORDER BY {order}
        LIMIT ? OFFSET ?
        """,
        (*params, clipped_limit, clipped_offset),
    )
    return [_row_to_quote(r) for r in rows]


def get_quote(db: Database, quote_id: str) -> QuoteRecord | None:
    row = db.fetchone(
        """
        SELECT q.*,
               op.name AS author_name,
               op.role AS author_role
        FROM exp_wall_quotes q
        LEFT JOIN operators op ON op.id = q.author_user_id
        WHERE q.id = ?
        """,
        (quote_id,),
    )
    return _row_to_quote(row) if row else None


def get_user_reactions(
    db: Database,
    *,
    user_id: str,
    quote_ids: Iterable[str],
) -> dict[str, set[str]]:
    """返回 {quote_id: {'like', 'save', ...}} 表示当前用户对哪些金句已点赞/收藏。

    前端拉 feed 后用这个 API 渲染按钮高亮状态。
    """
    ids = [str(q) for q in quote_ids if q]
    if not ids or not user_id:
        return {}
    placeholders = ",".join("?" * len(ids))
    rows = db.fetchall(
        f"""
        SELECT quote_id, reaction_type
        FROM exp_wall_reactions
        WHERE user_id = ? AND quote_id IN ({placeholders})
        """,
        (user_id, *ids),
    )
    result: dict[str, set[str]] = {}
    for r in rows:
        qid = str(r["quote_id"])
        result.setdefault(qid, set()).add(str(r["reaction_type"]))
    return result


# ──────────────────────────────────────────────────────────────────
# 写入：互动
# ──────────────────────────────────────────────────────────────────


def toggle_reaction(
    db: Database,
    *,
    quote_id: str,
    user_id: str,
    reaction_type: str,
) -> dict[str, object]:
    """切换点赞/收藏状态。已点 → 取消；未点 → 点上。

    返回 {"action": "added" | "removed", "like_count": N, "save_count": N, "is_active": bool}
    """
    if reaction_type not in REACTION_TYPES:
        raise ValueError(f"reaction_type 必须是 {REACTION_TYPES}, 实际：{reaction_type!r}")

    quote_row = db.fetchone(
        "SELECT id, status FROM exp_wall_quotes WHERE id = ?",
        (quote_id,),
    )
    if not quote_row:
        raise ValueError(f"quote 不存在：{quote_id}")
    if str(quote_row["status"]) != "active":
        raise ValueError("已删除的金句不能互动")

    existing = db.fetchone(
        "SELECT id FROM exp_wall_reactions WHERE quote_id = ? AND user_id = ? AND reaction_type = ?",
        (quote_id, user_id, reaction_type),
    )

    if existing:
        # 已点 → 取消
        db.conn.execute(
            "DELETE FROM exp_wall_reactions WHERE id = ?",
            (str(existing["id"]),),
        )
        action = "removed"
    else:
        # 未点 → 点上
        db.execute(
            """
            INSERT INTO exp_wall_reactions (id, quote_id, user_id, reaction_type, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (f"rx_{uuid.uuid4().hex[:12]}", quote_id, user_id, reaction_type, _now_iso()),
        )
        action = "added"

    counts = _recompute_scores(db, quote_id=quote_id)
    db.conn.commit()
    return {
        "action": action,
        "like_count": counts["like_count"],
        "save_count": counts["save_count"],
        "is_active": action == "added",
    }


def _recompute_scores(db: Database, *, quote_id: str) -> dict[str, object]:
    """重算一条金句的 like_count / save_count / contribution_score / hot_score。

    contribution_score = PUSH_BASE_SCORE
                       + Σ(like.tier_weight × LIKE_BASE_SCORE)
                       + Σ(save.tier_weight × SAVE_BASE_SCORE)

    hot_score 当前 = contribution_score（暂不加时间衰减，留扩展位）
    """
    # 真实计数（UI 用）
    counts = db.fetchone(
        """
        SELECT
          SUM(CASE WHEN reaction_type = 'like' THEN 1 ELSE 0 END) AS like_count,
          SUM(CASE WHEN reaction_type = 'save' THEN 1 ELSE 0 END) AS save_count
        FROM exp_wall_reactions WHERE quote_id = ?
        """,
        (quote_id,),
    )
    like_count = int(counts["like_count"] or 0)
    save_count = int(counts["save_count"] or 0)

    # 加权分（排序用）。要 JOIN operators.role_tier
    weighted_rows = db.fetchall(
        """
        SELECT r.reaction_type, COALESCE(op.role_tier, 'member') AS tier
        FROM exp_wall_reactions r
        LEFT JOIN operators op ON op.id = r.user_id
        WHERE r.quote_id = ?
        """,
        (quote_id,),
    )
    weighted = PUSH_BASE_SCORE  # 推上来基础分
    for r in weighted_rows:
        rtype = str(r["reaction_type"])
        weight = _weight_for_tier(str(r["tier"]))
        base = LIKE_BASE_SCORE if rtype == REACTION_LIKE else SAVE_BASE_SCORE
        weighted += weight * base

    db.execute(
        """
        UPDATE exp_wall_quotes
        SET like_count = ?, save_count = ?,
            contribution_score = ?, hot_score = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (like_count, save_count, weighted, weighted, _now_iso(), quote_id),
    )
    return {"like_count": like_count, "save_count": save_count, "score": weighted}


# ──────────────────────────────────────────────────────────────────
# 删除（权限校验）
# ──────────────────────────────────────────────────────────────────


def can_delete_quote(
    db: Database,
    *,
    deleter_user_id: str,
    quote_id: str,
) -> bool:
    """权限规则：
    - 作者本人可删自己的
    - 部门负责人可删本部门所有人的
    - CEO 可删整个组织的
    """
    quote_row = db.fetchone(
        "SELECT author_user_id FROM exp_wall_quotes WHERE id = ?",
        (quote_id,),
    )
    if not quote_row:
        return False
    author_id = str(quote_row["author_user_id"])
    if author_id == deleter_user_id:
        return True

    deleter_row = db.fetchone(
        "SELECT role_tier, team FROM operators WHERE id = ?",
        (deleter_user_id,),
    )
    if not deleter_row:
        return False
    tier = str(deleter_row["role_tier"] or ROLE_TIER_MEMBER)

    if tier == ROLE_TIER_CEO:
        return True

    if tier == ROLE_TIER_LEADER:
        # 同部门才能删
        deleter_team = str(deleter_row["team"] or "")
        author_team_row = db.fetchone(
            "SELECT team FROM operators WHERE id = ?",
            (author_id,),
        )
        if not author_team_row:
            return False
        return str(author_team_row["team"] or "") == deleter_team

    return False


def delete_quote(
    db: Database,
    *,
    quote_id: str,
    deleter_user_id: str,
) -> bool:
    """删除金句（mark 为 deleted，保留行用于审计/历史）。

    user 拍板「不做日志」—— 我们仍然写 deleted_by_user_id + deleted_at 到行内（便于将来追加，
    但不做单独的 log 表，符合用户决策）。

    返回 True = 删除成功，False = 无权限 / 金句不存在。
    """
    if not can_delete_quote(db, deleter_user_id=deleter_user_id, quote_id=quote_id):
        return False
    db.execute(
        """
        UPDATE exp_wall_quotes
        SET status = 'deleted',
            deleted_by_user_id = ?,
            deleted_at = ?,
            updated_at = ?
        WHERE id = ? AND status = 'active'
        """,
        (deleter_user_id, _now_iso(), _now_iso(), quote_id),
    )
    return True


# ──────────────────────────────────────────────────────────────────
# 聚合：贡献分（给排行榜用，但 UI 不在此模块做）
# ──────────────────────────────────────────────────────────────────


def aggregate_contribution_by_user(
    db: Database,
    *,
    since: str | None = None,
    until: str | None = None,
    team: str | None = None,
) -> list[dict[str, object]]:
    """按用户聚合贡献分（用于排行榜/个人主页等）。

    Args:
        since/until: ISO 时间过滤，None 表示不限
        team: 过滤某个部门内，None 表示全组织
    """
    where = ["q.status = 'active'"]
    params: list[object] = []
    if since:
        where.append("q.created_at >= ?")
        params.append(since)
    if until:
        where.append("q.created_at <= ?")
        params.append(until)
    if team:
        where.append("op.team = ?")
        params.append(team)
    clause = " AND ".join(where)

    rows = db.fetchall(
        f"""
        SELECT q.author_user_id AS user_id,
               op.name          AS user_name,
               op.role          AS user_role,
               op.team          AS user_team,
               COUNT(*)         AS quote_count,
               SUM(q.like_count) AS total_likes,
               SUM(q.save_count) AS total_saves,
               SUM(q.contribution_score) AS total_score
        FROM exp_wall_quotes q
        LEFT JOIN operators op ON op.id = q.author_user_id
        WHERE {clause}
        GROUP BY q.author_user_id
        ORDER BY total_score DESC
        """,
        tuple(params),
    )
    return [dict(r) for r in rows]


__all__ = [
    "CATEGORIES", "DEFAULT_CATEGORY", "SOURCE_TYPES",
    "REACTION_LIKE", "REACTION_SAVE",
    "ROLE_TIER_CEO", "ROLE_TIER_LEADER", "ROLE_TIER_MEMBER",
    "QuoteRecord",
    "insert_quote", "list_feed", "get_quote", "get_user_reactions",
    "toggle_reaction", "delete_quote", "can_delete_quote",
    "aggregate_contribution_by_user",
]
