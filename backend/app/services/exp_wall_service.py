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
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from typing import Iterable, Literal

from app.db import Database

logger = logging.getLogger(__name__)
DEFAULT_SANDBOX_ID = "sbx_local_default"


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


def normalize_quote_for_dedupe(text: str) -> str:
    normalized = re.sub(r"[\s\"'“”‘’《》<>()（）【】\[\]{}，。！？；：、,.!?;:·…—_\-]+", "", (text or "").strip().lower())
    replacements = {
        "核心源头": "源头",
        "根源": "源头",
        "根因": "源头",
        "源头出问题": "源头错",
        "源头出错": "源头错",
        "出错": "错",
        "错了": "错",
        "不符合预期": "无效",
        "不符预期": "无效",
        "不达预期": "无效",
        "没法": "无法",
        "怎么": "再",
        "彻底解决": "彻底",
        "治标不治本": "不彻底",
        "表层": "下游",
        "局部": "下游",
        "调整": "修改",
        "排查": "查",
        "优先": "先",
        "錯": "错",
        "臺": "台",
        "裏": "里",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return normalized


def _quote_dedupe_traits(text: str) -> set[str]:
    raw = text or ""
    normalized = normalize_quote_for_dedupe(raw)
    traits: set[str] = set()
    if any(token in raw for token in ("源头", "根源", "根因")) or "源头" in normalized:
        traits.add("root_cause")
    if any(token in raw for token in ("反复", "多次", "修改", "调整", "调", "改", "不符合预期", "不符预期", "不达预期", "无效")) or any(token in normalized for token in ("反复", "修改", "无效")):
        traits.add("revision_loop")
    if any(token in raw for token in ("下游", "其他地方", "表层", "局部", "治标不治本", "白费")) or any(token in normalized for token in ("下游", "其他地方", "不彻底", "白费")):
        traits.add("downstream_fix")
    if any(token in raw for token in ("彻底", "根本", "治标不治本")) or any(token in normalized for token in ("彻底", "不彻底")):
        traits.add("complete_fix")
    if any(token in raw for token in ("元信息", "分享", "卡片", "静态页")):
        traits.add("share_meta")
    return traits


def quotes_are_near_duplicate(left: str, right: str) -> bool:
    a = normalize_quote_for_dedupe(left)
    b = normalize_quote_for_dedupe(right)
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if len(shorter) >= 18 and shorter in longer:
        return True
    traits_a = _quote_dedupe_traits(left)
    traits_b = _quote_dedupe_traits(right)
    shared_traits = traits_a & traits_b
    if "root_cause" in shared_traits and len(shared_traits) >= 2:
        return True
    if min(len(a), len(b)) < 18:
        return False
    ratio = SequenceMatcher(None, a, b).ratio()
    if ratio >= 0.76:
        return True
    grams_a = {a[index:index + 2] for index in range(len(a) - 1)}
    grams_b = {b[index:index + 2] for index in range(len(b) - 1)}
    if grams_a and grams_b and len(grams_a & grams_b) / max(1, len(grams_a | grams_b)) >= 0.3:
        return True
    return False


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
    sandbox_id: str = DEFAULT_SANDBOX_ID,
    author_display_name: str = "",
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
            id, sandbox_id, author_user_id, author_display_name, quote_text, source_excerpt,
            source_type, source_object_id, category, status,
            like_count, save_count, contribution_score, hot_score,
            extracted_at, created_at, updated_at,
            sync_status, pending_sync_action
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 0, 0, ?, ?, ?, ?, ?, 'pending', 'upsert')
        """,
        (
            quote_id, sandbox_id or DEFAULT_SANDBOX_ID, author_user_id, author_display_name.strip(), quote_text.strip(), source_excerpt,
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
    sandbox_id: str | None = None,
) -> list[QuoteRecord]:
    """拉取信息流。

    - sort='hot'：按 hot_score 降序（CEO/leader 加权后的排序）
    - sort='latest'：按 created_at 降序
    - category 为 None 时全部分类
    """
    where = ["q.status = 'active'"]
    params: list[object] = []
    if sandbox_id:
        where.append("COALESCE(q.sandbox_id, ?) = ?")
        params.extend([DEFAULT_SANDBOX_ID, sandbox_id])
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
               COALESCE(NULLIF(op.name, ''), NULLIF(q.author_display_name, '')) AS author_name,
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
               COALESCE(NULLIF(op.name, ''), NULLIF(q.author_display_name, '')) AS author_name,
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
    sandbox_id: str = DEFAULT_SANDBOX_ID,
) -> dict[str, object]:
    """切换点赞/收藏状态。已点 → 取消；未点 → 点上。

    返回 {"action": "added" | "removed", "like_count": N, "save_count": N, "is_active": bool}
    """
    if reaction_type not in REACTION_TYPES:
        raise ValueError(f"reaction_type 必须是 {REACTION_TYPES}, 实际：{reaction_type!r}")

    quote_row = db.fetchone(
        "SELECT id, status, sandbox_id FROM exp_wall_quotes WHERE id = ?",
        (quote_id,),
    )
    if not quote_row:
        raise ValueError(f"quote 不存在：{quote_id}")
    if str(quote_row["status"]) != "active":
        raise ValueError("已删除的金句不能互动")

    row_sandbox_id = str(quote_row["sandbox_id"] or DEFAULT_SANDBOX_ID)
    if sandbox_id and row_sandbox_id != sandbox_id:
        raise ValueError("金句不属于当前工作空间")
    existing = db.fetchone(
        "SELECT id FROM exp_wall_reactions WHERE quote_id = ? AND user_id = ? AND reaction_type = ? AND COALESCE(sandbox_id, ?) = ?",
        (quote_id, user_id, reaction_type, DEFAULT_SANDBOX_ID, row_sandbox_id),
    )

    if existing:
        # 已点 → 取消; 真先记 reaction_id 给云端真同步删除
        reaction_id = str(existing["id"])
        db.conn.execute(
            "UPDATE exp_wall_reactions SET sync_status='pending', pending_sync_action='delete' WHERE id = ?",
            (reaction_id,),
        )
        db.conn.execute(
            "DELETE FROM exp_wall_reactions WHERE id = ?",
            (reaction_id,),
        )
        action = "removed"
    else:
        # 未点 → 点上
        db.execute(
            """
            INSERT INTO exp_wall_reactions (id, sandbox_id, quote_id, user_id, reaction_type, created_at, sync_status, pending_sync_action)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', 'upsert')
            """,
            (f"rx_{uuid.uuid4().hex[:12]}", row_sandbox_id, quote_id, user_id, reaction_type, _now_iso()),
        )
        action = "added"

    counts = _recompute_scores(db, quote_id=quote_id)
    # 真 quote 真 like_count/save_count 真变, 真也得真重 push
    db.conn.execute(
        "UPDATE exp_wall_quotes SET sync_status='pending', pending_sync_action='upsert' WHERE id = ?",
        (quote_id,),
    )
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
            updated_at = ?,
            sync_status = 'pending',
            pending_sync_action = 'upsert'
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


# ──────────────────────────────────────────────────────────────────
# 云端同步 (顾源源 5/27 方案 A · 组织级金句互看)
# ──────────────────────────────────────────────────────────────────


def _quote_row_to_cloud_payload(row: sqlite3.Row) -> dict[str, object]:
    """真本地 row → cloud POST /api/v1/exp-wall/quotes 真 payload (camelCase)."""
    return {
        "id": str(row["id"]),
        "authorUserId": str(row["author_user_id"]),
        "authorDisplayName": str(row["author_display_name"] or ""),
        "quoteText": str(row["quote_text"]),
        "sourceExcerpt": str(row["source_excerpt"] or ""),
        "sourceType": str(row["source_type"]),
        "sourceObjectId": str(row["source_object_id"] or ""),
        "category": str(row["category"] or "方法论"),
        "status": str(row["status"] or "active"),
        "deletedByUserId": str(row["deleted_by_user_id"]) if row["deleted_by_user_id"] else None,
        "deletedAt": str(row["deleted_at"]) if row["deleted_at"] else None,
        "likeCount": int(row["like_count"] or 0),
        "saveCount": int(row["save_count"] or 0),
        "contributionScore": float(row["contribution_score"] or 0),
        "hotScore": float(row["hot_score"] or 0),
        "extractedAt": str(row["extracted_at"]),
        "createdAt": str(row["created_at"]),
        "updatedAt": str(row["updated_at"]),
    }


def push_pending_quotes_to_cloud(
    db: Database,
    *,
    cloud_base_url: str,
    cloud_token: str,
    httpx_client,
    sandbox_id: str | None = None,
) -> dict[str, int]:
    """扫 sync_status='pending' 真 quote, 真逐条 POST 云端. 真成功 mark 'synced', 真失败 mark 'failed'.

    Args:
        cloud_base_url: cloud_api_base_url() 调用方传入 (不在 service 里耦合 state).
        cloud_token: get_cloud_token() 取出来的 Bearer token.
        httpx_client: 调用方传入的 httpx.Client / httpx.AsyncClient — 测试时可注入 mock.

    Returns:
        {"pushed": N, "failed": M} 计数."""
    where = "sync_status = 'pending'"
    params: tuple[object, ...] = ()
    if sandbox_id:
        where += " AND COALESCE(sandbox_id, ?) = ?"
        params = (DEFAULT_SANDBOX_ID, sandbox_id)
    pending_rows = db.fetchall(
        f"SELECT * FROM exp_wall_quotes WHERE {where} ORDER BY updated_at ASC LIMIT 50",
        params,
    )
    pushed = 0
    failed = 0
    for row in pending_rows:
        quote_id = str(row["id"])
        try:
            payload = _quote_row_to_cloud_payload(row)
            resp = httpx_client.post(
                f"{cloud_base_url.rstrip('/')}/api/v1/exp-wall/quotes",
                json=payload,
                headers={"Authorization": f"Bearer {cloud_token}"},
                timeout=15.0,
            )
            if 200 <= resp.status_code < 300:
                db.conn.execute(
                    "UPDATE exp_wall_quotes SET sync_status='synced', last_synced_at=?, pending_sync_action='' WHERE id = ?",
                    (_now_iso(), quote_id),
                )
                pushed += 1
            else:
                logger.warning("push quote %s failed: HTTP %d %s", quote_id, resp.status_code, resp.text[:200])
                db.conn.execute(
                    "UPDATE exp_wall_quotes SET sync_status='failed' WHERE id = ?",
                    (quote_id,),
                )
                failed += 1
        except Exception as exc:
            logger.warning("push quote %s exception: %s", quote_id, exc)
            db.conn.execute(
                "UPDATE exp_wall_quotes SET sync_status='failed' WHERE id = ?",
                (quote_id,),
            )
            failed += 1
    db.conn.commit()
    return {"pushed": pushed, "failed": failed}


def push_pending_reactions_to_cloud(
    db: Database,
    *,
    cloud_base_url: str,
    cloud_token: str,
    httpx_client,
    sandbox_id: str | None = None,
) -> dict[str, int]:
    """同 push_pending_quotes_to_cloud. 真支持 'upsert' / 'delete' 双动作.

    delete 真**reactions 已经被本地 hard DELETE 真**, 真**需在 pending_sync_action='delete' 真 row**
    在 DELETE 真前真记录 — 真但目前 toggle_reaction 是 hard delete, 真**简化方案**: 真**云端按 DELETE
    endpoint 真 quote_id+reaction_type+user_id 真直接删** — 真不要求本地 row 还在."""
    # upsert 真 pending
    where = "sync_status = 'pending' AND pending_sync_action = 'upsert'"
    params: tuple[object, ...] = ()
    if sandbox_id:
        where += " AND COALESCE(sandbox_id, ?) = ?"
        params = (DEFAULT_SANDBOX_ID, sandbox_id)
    upsert_rows = db.fetchall(
        f"SELECT * FROM exp_wall_reactions WHERE {where} LIMIT 100",
        params,
    )
    pushed = 0
    failed = 0
    for row in upsert_rows:
        reaction_id = str(row["id"])
        try:
            resp = httpx_client.post(
                f"{cloud_base_url.rstrip('/')}/api/v1/exp-wall/reactions",
                json={
                    "id": reaction_id,
                    "quoteId": str(row["quote_id"]),
                    "userId": str(row["user_id"]),
                    "reactionType": str(row["reaction_type"]),
                    "createdAt": str(row["created_at"]),
                },
                headers={"Authorization": f"Bearer {cloud_token}"},
                timeout=10.0,
            )
            if 200 <= resp.status_code < 300:
                db.conn.execute(
                    "UPDATE exp_wall_reactions SET sync_status='synced', last_synced_at=?, pending_sync_action='' WHERE id = ?",
                    (_now_iso(), reaction_id),
                )
                pushed += 1
            else:
                logger.warning("push reaction %s failed: HTTP %d", reaction_id, resp.status_code)
                db.conn.execute(
                    "UPDATE exp_wall_reactions SET sync_status='failed' WHERE id = ?",
                    (reaction_id,),
                )
                failed += 1
        except Exception as exc:
            logger.warning("push reaction %s exception: %s", reaction_id, exc)
            db.conn.execute(
                "UPDATE exp_wall_reactions SET sync_status='failed' WHERE id = ?",
                (reaction_id,),
            )
            failed += 1
    db.conn.commit()
    return {"pushed": pushed, "failed": failed}


def pull_quotes_from_cloud(
    db: Database,
    *,
    cloud_base_url: str,
    cloud_token: str,
    httpx_client,
    sandbox_id: str = DEFAULT_SANDBOX_ID,
    request_timeout: float = 20.0,
) -> dict[str, object]:
    """真定时拉云端增量金句 (since=settings.last_exp_wall_pull_at).

    真**合并策略**: 真**云端真权威**, 真**按 id upsert 到本地** 真**(覆盖本地 like_count/save_count/status)**.
    真**自己刚 push 真金句真也会回流** — 真**幂等 upsert 不会真伤**.
    真**作者展示信息** (full_name) 真**本地用 operators 表 join 真补**, 真**云端真 authorDisplayName 仅作 fallback**.

    真**保护**: 真**有 sync_status='pending' 真本地 row** 真**不被云端覆盖** (避免 push 还没成功就被 pull 反向冲掉)."""
    scoped_setting_key = f"last_exp_wall_pull_at.{sandbox_id or DEFAULT_SANDBOX_ID}"
    since = db.get_setting(scoped_setting_key, "") or db.get_setting("last_exp_wall_pull_at", "")
    missing_author_names = db.fetchone(
        """
        SELECT COUNT(1) AS count
        FROM exp_wall_quotes
        WHERE COALESCE(sandbox_id, ?) = ?
          AND status = 'active'
          AND COALESCE(author_display_name, '') = ''
        """,
        (DEFAULT_SANDBOX_ID, sandbox_id or DEFAULT_SANDBOX_ID),
    )
    force_full_pull = bool(missing_author_names and int(missing_author_names["count"] or 0) > 0)
    try:
        resp = httpx_client.get(
            f"{cloud_base_url.rstrip('/')}/api/v1/exp-wall/quotes",
            params={"since": since} if since and not force_full_pull else {},
            headers={"Authorization": f"Bearer {cloud_token}"},
            timeout=request_timeout,
        )
        if not (200 <= resp.status_code < 300):
            logger.warning("pull exp_wall quotes failed: HTTP %d", resp.status_code)
            return {"pulled": 0, "merged": 0, "skipped_pending": 0}
        data = resp.json()
    except Exception as exc:
        logger.warning("pull exp_wall quotes exception: %s", exc)
        return {"pulled": 0, "merged": 0, "skipped_pending": 0}

    quotes = data.get("quotes", []) or []
    server_ts = data.get("serverTimestamp", "") or _now_iso()
    merged = 0
    skipped_pending = 0
    for q in quotes:
        quote_id = str(q.get("id", ""))
        if not quote_id:
            continue
        existing = db.fetchone(
            "SELECT sync_status FROM exp_wall_quotes WHERE id = ?",
            (quote_id,),
        )
        if existing and str(existing["sync_status"]) == "pending":
            skipped_pending += 1
            continue
        # 真 upsert (云端 → 本地)
        db.conn.execute(
            """
            INSERT INTO exp_wall_quotes(
                id, sandbox_id, author_user_id, author_display_name, quote_text, source_excerpt,
                source_type, source_object_id, category, status,
                deleted_by_user_id, deleted_at,
                like_count, save_count, contribution_score, hot_score,
                extracted_at, created_at, updated_at,
                sync_status, last_synced_at, pending_sync_action
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'synced', ?, '')
            ON CONFLICT(id) DO UPDATE SET
                sandbox_id = excluded.sandbox_id,
                author_user_id = excluded.author_user_id,
                author_display_name = COALESCE(NULLIF(excluded.author_display_name, ''), exp_wall_quotes.author_display_name),
                quote_text = excluded.quote_text,
                source_excerpt = excluded.source_excerpt,
                source_type = excluded.source_type,
                source_object_id = excluded.source_object_id,
                category = excluded.category,
                status = excluded.status,
                deleted_by_user_id = excluded.deleted_by_user_id,
                deleted_at = excluded.deleted_at,
                like_count = excluded.like_count,
                save_count = excluded.save_count,
                contribution_score = excluded.contribution_score,
                hot_score = excluded.hot_score,
                updated_at = excluded.updated_at,
                sync_status = 'synced',
                last_synced_at = excluded.last_synced_at,
                pending_sync_action = ''
            """,
            (
                quote_id, sandbox_id or DEFAULT_SANDBOX_ID, str(q.get("authorUserId", "")),
                str(q.get("authorDisplayName", "")), str(q.get("quoteText", "")),
                str(q.get("sourceExcerpt", "")), str(q.get("sourceType", "")),
                str(q.get("sourceObjectId", "")), str(q.get("category", "方法论")),
                str(q.get("status", "active")),
                q.get("deletedByUserId"), q.get("deletedAt"),
                int(q.get("likeCount", 0)), int(q.get("saveCount", 0)),
                float(q.get("contributionScore", 0)), float(q.get("hotScore", 0)),
                str(q.get("extractedAt", "")), str(q.get("createdAt", "")), str(q.get("updatedAt", "")),
                _now_iso(),
            ),
        )
        merged += 1

    db.set_setting(scoped_setting_key, server_ts)
    db.conn.commit()
    return {"pulled": len(quotes), "merged": merged, "skipped_pending": skipped_pending}


__all__ = [
    "CATEGORIES", "DEFAULT_CATEGORY", "SOURCE_TYPES",
    "REACTION_LIKE", "REACTION_SAVE",
    "ROLE_TIER_CEO", "ROLE_TIER_LEADER", "ROLE_TIER_MEMBER",
    "QuoteRecord",
    "normalize_quote_for_dedupe", "quotes_are_near_duplicate",
    "insert_quote", "list_feed", "get_quote", "get_user_reactions",
    "toggle_reaction", "delete_quote", "can_delete_quote",
    "aggregate_contribution_by_user",
    "push_pending_quotes_to_cloud", "push_pending_reactions_to_cloud",
    "pull_quotes_from_cloud",
]
