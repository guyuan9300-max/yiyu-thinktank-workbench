"""实体合并 + 候选重复检测（迭代 3）。

iter2 已经做了"入库期完全相同 normalized_name 自动 dedup"。本迭代解决
"近似重复"：例如 "张总" / "张总监"、"阿里科技" / "阿里科技有限公司"
这种字符级相似但 normalized_name 不一样的情况。

策略：
- 发现：扫描同 (client_id, entity_type) 的实体对，按以下规则评分：
  * 互为前缀（"张总" 是 "张总监" 的前缀） → 0.85
  * 互为子串（"阿里科技" 在 "阿里科技有限公司" 里） → 0.75
  * 字符集 Jaccard 相似度 > 0.7 → 0.7
  * 编辑距离 ≤ 2 且最短长度 ≥ 3 → 0.65
  评分 ≥ 0.65 视为合并候选
- 合并：把 merged_entity_id 的 mention / triple / atomic_fact 转移到
  surviving_entity_id，merged_entity_id.status = 'merged_into:<id>'
- 操作记入 entity_merge_log 便于审计/回滚
"""
from __future__ import annotations

import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---- 候选发现 -------------------------------------------------------------


@dataclass(frozen=True)
class MergeCandidate:
    entity_a_id: str
    entity_b_id: str
    entity_type: str
    name_a: str
    name_b: str
    mention_count_a: int
    mention_count_b: int
    similarity: float
    reason: str


def _jaccard(a: str, b: str) -> float:
    set_a, set_b = set(a), set(b)
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union else 0.0


def _edit_distance(a: str, b: str) -> int:
    """简化 Levenshtein，仅给 2 个字符差以内的精度。"""
    if a == b:
        return 0
    if abs(len(a) - len(b)) > 5:
        return 99
    # 标准 DP
    m, n = len(a), len(b)
    if m == 0:
        return n
    if n == 0:
        return m
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        curr = [i] + [0] * n
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[n]


def _score_pair(name_a: str, name_b: str) -> tuple[float, str]:
    """对一对名字打 (similarity, reason)。<0.65 视为不相关。"""
    if name_a == name_b:
        return 1.0, "完全相同"
    short, long_ = (name_a, name_b) if len(name_a) <= len(name_b) else (name_b, name_a)
    if len(short) < 2:
        return 0.0, ""
    # 互为前缀
    if long_.startswith(short):
        return 0.85, "前缀重合"
    # 互为子串
    if short in long_:
        return 0.75, "子串重合"
    # Jaccard
    j = _jaccard(name_a, name_b)
    if j >= 0.7:
        return min(0.7, j), f"字符相似 {j:.2f}"
    # 编辑距离
    if len(short) >= 3:
        d = _edit_distance(name_a, name_b)
        if d <= 2:
            return 0.65, f"编辑距离 {d}"
    return 0.0, ""


def find_merge_candidates(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    min_similarity: float = 0.65,
    limit: int = 50,
) -> list[MergeCandidate]:
    """扫描客户范围内的实体，找出可能重复的对。

    O(n²) — 同 (client_id, entity_type) 内两两比较。客户范围内通常
    n < 1000，性能 OK。
    """
    rows = conn.execute(
        """
        SELECT id, entity_type, normalized_name, display_name, mention_count
        FROM entities
        WHERE client_id = ? AND status = 'active'
        ORDER BY entity_type, normalized_name
        """,
        (client_id,),
    ).fetchall()
    # 按 entity_type 分桶，避免跨类型比对
    by_type: dict[str, list[sqlite3.Row]] = {}
    for r in rows:
        by_type.setdefault(str(r["entity_type"]), []).append(r)

    candidates: list[MergeCandidate] = []
    for entity_type, bucket in by_type.items():
        n = len(bucket)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = bucket[i], bucket[j]
                sim, reason = _score_pair(
                    str(a["normalized_name"]),
                    str(b["normalized_name"]),
                )
                if sim >= min_similarity:
                    candidates.append(
                        MergeCandidate(
                            entity_a_id=str(a["id"]),
                            entity_b_id=str(b["id"]),
                            entity_type=entity_type,
                            name_a=str(a["display_name"]),
                            name_b=str(b["display_name"]),
                            mention_count_a=int(a["mention_count"] or 0),
                            mention_count_b=int(b["mention_count"] or 0),
                            similarity=sim,
                            reason=reason,
                        )
                    )
    # 按相似度倒序，再按提及总数倒序
    candidates.sort(
        key=lambda c: (-c.similarity, -(c.mention_count_a + c.mention_count_b))
    )
    return candidates[:limit]


# ---- 合并 ----------------------------------------------------------------


def merge_entities(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    surviving_id: str,
    merged_id: str,
    merge_reason: str = "",
    merged_by: str | None = None,
) -> dict[str, int]:
    """把 merged_id 的所有外键引用迁到 surviving_id，merged_id 标记 merged。

    Returns:
        计数字典：mentions_moved / triples_moved / facts_moved
    """
    if surviving_id == merged_id:
        raise ValueError("surviving_id 和 merged_id 不能相同")

    # 验证两条都属于同一客户
    rows = conn.execute(
        "SELECT id, client_id, display_name, aliases_json, mention_count FROM entities "
        "WHERE id IN (?, ?)",
        (surviving_id, merged_id),
    ).fetchall()
    by_id = {str(r["id"]): r for r in rows}
    if len(by_id) != 2:
        raise ValueError("找不到 entity")
    if str(by_id[surviving_id]["client_id"]) != client_id:
        raise ValueError("surviving entity 不属于该客户")
    if str(by_id[merged_id]["client_id"]) != client_id:
        raise ValueError("merged entity 不属于该客户")

    timestamp = _now_iso()

    # 1. 迁 mentions
    cur = conn.execute(
        "UPDATE entity_mentions SET entity_id = ? WHERE entity_id = ?",
        (surviving_id, merged_id),
    )
    mentions_moved = cur.rowcount or 0

    # 2. 迁 relationship_triples（subject 和 object 两边都要迁）
    cur = conn.execute(
        "UPDATE relationship_triples SET subject_entity_id = ? WHERE subject_entity_id = ?",
        (surviving_id, merged_id),
    )
    triples_subj = cur.rowcount or 0
    cur = conn.execute(
        "UPDATE relationship_triples SET object_entity_id = ? WHERE object_entity_id = ?",
        (surviving_id, merged_id),
    )
    triples_obj = cur.rowcount or 0
    triples_moved = triples_subj + triples_obj

    # 3. 迁 atomic_facts.subject_entity_id
    cur = conn.execute(
        "UPDATE atomic_facts SET subject_entity_id = ? WHERE subject_entity_id = ?",
        (surviving_id, merged_id),
    )
    facts_moved = cur.rowcount or 0

    # 4. 合并 aliases + mention_count
    import json as _json

    surviving_row = by_id[surviving_id]
    merged_row = by_id[merged_id]
    surviving_aliases = _json.loads(str(surviving_row["aliases_json"] or "[]"))
    merged_aliases = _json.loads(str(merged_row["aliases_json"] or "[]"))
    merged_display = str(merged_row["display_name"] or "")
    for alias in merged_aliases + ([merged_display] if merged_display else []):
        if alias and alias not in surviving_aliases:
            surviving_aliases.append(alias)
    new_mention_count = int(surviving_row["mention_count"] or 0) + int(
        merged_row["mention_count"] or 0
    )
    conn.execute(
        """
        UPDATE entities
        SET aliases_json = ?, mention_count = ?, last_seen_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            _json.dumps(surviving_aliases, ensure_ascii=False),
            new_mention_count,
            timestamp,
            timestamp,
            surviving_id,
        ),
    )

    # 5. 标记 merged entity 为 merged_into:<surviving_id>
    conn.execute(
        """
        UPDATE entities
        SET status = ?, updated_at = ?
        WHERE id = ?
        """,
        (f"merged_into:{surviving_id}", timestamp, merged_id),
    )

    # 6. 写日志
    log_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO entity_merge_log (
            id, client_id, surviving_entity_id, merged_entity_id,
            mentions_moved, triples_moved, facts_moved, merge_reason,
            merged_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            log_id,
            client_id,
            surviving_id,
            merged_id,
            mentions_moved,
            triples_moved,
            facts_moved,
            merge_reason,
            merged_by,
            timestamp,
        ),
    )

    return {
        "mentions_moved": mentions_moved,
        "triples_moved": triples_moved,
        "facts_moved": facts_moved,
    }


__all__ = [
    "MergeCandidate",
    "find_merge_candidates",
    "merge_entities",
]
