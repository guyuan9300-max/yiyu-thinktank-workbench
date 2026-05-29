"""数据中心 AI 自校验流水线 (L3 of broadcast).

写后扩散完成 narrative/portrait 之后, 让 AI 反过来"自我审稿":
  - 找重复/别名 entity → 自动合并 or 写澄清队列
  - 找矛盾 atomic_facts → 写 fact_contradictions
  - 把字典里的别名替换成 canonical → 减少重复事实

设计原则:
  - 每个 verifier 独立 daemon, 失败不影响其他
  - throttle 控制 LLM 调用频率 (broadcast 已经过滤)
  - LLM token 用量受控: 实体 ≤ 50 个, 事实 ≤ 80 条/批
  - 写库都 ON CONFLICT 去重, 同 run 可幂等
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ─── 工具 ────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _safe_loads(text: str | None, default: Any) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


# ─── #1 实体聚类 + 别名合并 ─────────────────────────────────────────────────

_ENTITY_CLUSTER_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "clusters": {"type": "ARRAY"},
    },
    "required": ["clusters"],
}

_ENTITY_CLUSTER_PROMPT = """\
你是数据档案整理助手。下面是同一客户档案下的人物/机构列表(可能含别名、错字、同人不同写法)。
请按"是否实际为同一个人/机构"聚类。

== 实体列表 ==
{entity_list}

== 任务 ==
返回 JSON, 把名字相同/相近/明显是别名的归为一簇, 每簇带置信度:

{{
  "clusters": [
    {{"members": ["顾源源", "小顾", "顾老师"], "canonical": "顾源源",
      "confidence": "high", "reason": "字面/上下文一致"}},
    {{"members": ["仪婷"], "canonical": "仪婷", "confidence": "high", "reason": "无别名候选"}},
    {{"members": ["雅尼", "依婷"], "canonical": "?",
      "confidence": "low", "reason": "拼写完全不同但同为对接人, 不确定是否同一人"}}
  ]
}}

规则:
1. confidence='high' 才会自动合并; 'medium'/'low' 留给人工裁决
2. 单独成簇也要返回(表示已确认无别名)
3. canonical 是该簇的标准名, 取最完整的写法
4. reason 简短一句话
5. 忽略明显是金额/日期/时间词汇的"伪实体" (比如 "300万元", "2026年")
"""


def verify_entities_cluster(db: Any, ai: Any, client_id: str) -> dict[str, Any]:
    """LLM 聚类同 client 下的 entities, 高置信自动 merge, 低置信进澄清队列.

    Returns: {merged: N, queued: M, errors: [...]}
    """
    stats = {"merged": 0, "queued": 0, "errors": []}
    if not client_id:
        return stats

    # 取前 50 个 active entities (按 mention_count 降序, 跳过明显伪实体)
    rows = db.fetchall(
        """SELECT id, display_name, entity_type, mention_count
           FROM entities
           WHERE client_id=? AND status='active'
             AND entity_type NOT IN ('amount', 'date', 'time')
             AND length(display_name) >= 2
           ORDER BY mention_count DESC, updated_at DESC
           LIMIT 50""",
        (client_id,),
    )
    if len(rows) < 2:
        logger.info("[verify entities] client=%s skip (entities<2)", client_id)
        return stats

    entity_list = "\n".join(
        f"  - {r['display_name']} (type={r['entity_type']}, mentions={r['mention_count']})"
        for r in rows
    )
    name_to_id: dict[str, str] = {r["display_name"]: r["id"] for r in rows}

    try:
        result = ai._qwen_generate(  # noqa: SLF001
            _ENTITY_CLUSTER_PROMPT.format(entity_list=entity_list),
            "你是数据档案整理助手, 只返回 JSON.",
            _ENTITY_CLUSTER_SCHEMA,
            timeout_seconds=120.0,
            max_tokens=4000,
            temperature=0.1,
            provider_override="doubao",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("[verify entities] LLM failed client=%s", client_id)
        stats["errors"].append(f"llm: {str(exc)[:100]}")
        return stats

    clusters = (result or {}).get("clusters") or []
    now = _now_iso()
    for cluster in clusters:
        if not isinstance(cluster, dict):
            continue
        members = [str(m).strip() for m in (cluster.get("members") or []) if str(m).strip()]
        if len(members) < 2:
            continue
        canonical = str(cluster.get("canonical") or "").strip() or members[0]
        confidence = str(cluster.get("confidence") or "low").strip().lower()
        # 找 cluster 里所有 entity_id
        member_ids = [name_to_id[n] for n in members if n in name_to_id]
        if len(member_ids) < 2:
            continue
        canonical_id = name_to_id.get(canonical, member_ids[0])
        dup_ids = [eid for eid in member_ids if eid != canonical_id]

        if confidence == "high":
            # 自动 merge: 把 dups 的 aliases 合并进 canonical, 删 dups
            try:
                _merge_entities(db, canonical_id, dup_ids, now)
                stats["merged"] += len(dup_ids)
            except Exception as exc:  # noqa: BLE001
                stats["errors"].append(f"merge {canonical}: {str(exc)[:80]}")
        else:
            # 低置信: 把这堆"可能同人"作为 unverified 标记, UI 后续可裁决
            # 用 entities.aliases_json 字段加一个 'suggested_merges' 记录, 不真的删
            try:
                _mark_suggested_merge(db, canonical_id, dup_ids, members, cluster.get("reason", ""), now)
                stats["queued"] += len(dup_ids)
            except Exception as exc:  # noqa: BLE001
                stats["errors"].append(f"queue {canonical}: {str(exc)[:80]}")

    try:
        db.conn.commit()
    except Exception:  # noqa: BLE001
        pass
    logger.info(
        "[verify entities] client=%s clusters=%d merged=%d queued=%d errors=%d",
        client_id, len(clusters), stats["merged"], stats["queued"], len(stats["errors"]),
    )
    return stats


def _merge_entities(db: Any, canonical_id: str, dup_ids: list[str], now: str) -> None:
    """把 dup_ids 合并到 canonical_id. 累计 mention_count + aliases, 把 dup 标记为 merged.

    ★ ER v4 人工金标层(5/28 加): 已 verified_canonical 的 entity 不能作为 dup 被合掉
    (人工金标永远不被算法覆盖). verified_noise 的 dup 也跳过(已经被人工排除).
    """
    canonical_row = db.fetchone(
        "SELECT aliases_json, mention_count, display_name, verified_status FROM entities WHERE id=?",
        (canonical_id,),
    )
    if not canonical_row:
        return
    # canonical 自己若已 verified_noise → 不应该作为 canonical(算法搞错了, 跳过整个合并)
    canonical_verified = canonical_row["verified_status"]
    if canonical_verified == "verified_noise":
        logger.info("[_merge_entities] skip: canonical_id=%s is verified_noise", canonical_id)
        return
    aliases = _safe_loads(canonical_row["aliases_json"], [])
    if not isinstance(aliases, list):
        aliases = []
    total_mentions = int(canonical_row["mention_count"] or 0)

    skipped_count = 0
    for dup_id in dup_ids:
        dup_row = db.fetchone(
            "SELECT display_name, mention_count, aliases_json, verified_status FROM entities WHERE id=?",
            (dup_id,),
        )
        if not dup_row:
            continue
        # ★ ER v4: 已 verified_canonical 的 entity 是人工金标, 不能被合掉
        dup_verified = dup_row["verified_status"]
        if dup_verified == "verified_canonical":
            logger.info("[_merge_entities] skip dup_id=%s (verified_canonical, human gold standard)", dup_id)
            skipped_count += 1
            continue
        # verified_noise 的 dup 也跳过(用户已排除, 不参与合并)
        if dup_verified == "verified_noise":
            logger.info("[_merge_entities] skip dup_id=%s (verified_noise)", dup_id)
            skipped_count += 1
            continue
        dup_name = str(dup_row["display_name"] or "")
        if dup_name and dup_name not in aliases:
            aliases.append(dup_name)
        dup_aliases = _safe_loads(dup_row["aliases_json"], [])
        if isinstance(dup_aliases, list):
            for a in dup_aliases:
                if a not in aliases:
                    aliases.append(a)
        total_mentions += int(dup_row["mention_count"] or 0)
        # 标 merged 而不是删 — 保留追溯
        db.execute(
            "UPDATE entities SET status='merged', updated_at=? WHERE id=?",
            (now, dup_id),
        )

    if skipped_count > 0:
        logger.info("[_merge_entities] canonical=%s: skipped %d verified dups", canonical_id, skipped_count)

    db.execute(
        """UPDATE entities SET aliases_json=?, mention_count=?, updated_at=?
           WHERE id=?""",
        (json.dumps(aliases, ensure_ascii=False), total_mentions, now, canonical_id),
    )


def _mark_suggested_merge(
    db: Any, canonical_id: str, dup_ids: list[str], members: list[str], reason: str, now: str,
) -> None:
    """低置信合并建议: 在 canonical entity 的 attributes_json 里加一个 suggested_merges 记录."""
    row = db.fetchone("SELECT attributes_json FROM entities WHERE id=?", (canonical_id,))
    if not row:
        return
    attrs = _safe_loads(row["attributes_json"], {})
    if not isinstance(attrs, dict):
        attrs = {}
    suggestions = attrs.get("suggested_merges") or []
    suggestions.append({
        "candidates": members,
        "dup_ids": dup_ids,
        "reason": str(reason or "")[:200],
        "suggested_at": now,
    })
    attrs["suggested_merges"] = suggestions[-5:]  # 只保留最近 5 个建议
    db.execute(
        "UPDATE entities SET attributes_json=?, updated_at=? WHERE id=?",
        (json.dumps(attrs, ensure_ascii=False), now, canonical_id),
    )


# ─── #2 矛盾主动检测 ────────────────────────────────────────────────────────

_CONTRADICTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "pairs": {"type": "ARRAY"},
    },
    "required": ["pairs"],
}

_CONTRADICTION_PROMPT = """\
你是数据档案矛盾检测助手。下面是同一客户档案的"原子事实"列表(每条带 id), 请找出**互相矛盾的两两组合**。

== 事实列表 ==
{facts_list}

== 任务 ==
返回 JSON, 只标出**确实矛盾**的事实对(不矛盾的不要列):

{{
  "pairs": [
    {{"fact_a_id": "af_xxx", "fact_b_id": "af_yyy",
      "type": "value_diff", "severity": "high",
      "reason": "A 说项目预算 300万, B 说 500万, 同一客户同一项目"}}
  ]
}}

规则:
1. **type**: value_diff(数值矛盾) / time_diff(时间矛盾) / role_diff(角色矛盾) / claim_diff(论断矛盾)
2. **severity**: high(直接冲突无法共存) / medium(可能因上下文不同共存) / low(可能是补充而非矛盾)
3. **reason**: 一句话, 明确说出冲突在哪里
4. 严格忠实于原文, 不要推测没说的
5. 单纯措辞不同/视角不同不算矛盾
6. 优先 high+medium, 不要返回大量 low
"""


def verify_contradictions(db: Any, ai: Any, client_id: str) -> dict[str, Any]:
    """LLM 在 atomic_facts 里找矛盾, 写入 fact_contradictions 让用户裁决.

    Returns: {detected: N, inserted: M, skipped_dup: K, errors: [...]}
    """
    stats = {"detected": 0, "inserted": 0, "skipped_dup": 0, "errors": []}
    if not client_id:
        return stats

    # 取最近 80 条 active facts
    rows = db.fetchall(
        """SELECT id, subject_text, attribute, value_text, value_normalized,
                  confidence, evidence_text
           FROM atomic_facts
           WHERE client_id=? AND status='active'
           ORDER BY updated_at DESC LIMIT 80""",
        (client_id,),
    )
    if len(rows) < 4:
        logger.info("[verify contradictions] client=%s skip (facts<4)", client_id)
        return stats

    facts_list = "\n".join(
        f"  - id={r['id']}: 主体={r['subject_text']}, 属性={r['attribute']}, "
        f"值={r['value_text'] or r['value_normalized'] or '?'}"
        for r in rows
    )
    valid_ids = {r["id"] for r in rows}

    try:
        result = ai._qwen_generate(  # noqa: SLF001
            _CONTRADICTION_PROMPT.format(facts_list=facts_list),
            "你是矛盾检测助手, 只返回 JSON.",
            _CONTRADICTION_SCHEMA,
            timeout_seconds=120.0,
            max_tokens=4000,
            temperature=0.1,
            provider_override="doubao",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("[verify contradictions] LLM failed client=%s", client_id)
        stats["errors"].append(f"llm: {str(exc)[:100]}")
        return stats

    pairs = (result or {}).get("pairs") or []
    stats["detected"] = len(pairs)
    now = _now_iso()
    for p in pairs:
        if not isinstance(p, dict):
            continue
        a_id = str(p.get("fact_a_id") or "").strip()
        b_id = str(p.get("fact_b_id") or "").strip()
        if not a_id or not b_id or a_id == b_id:
            continue
        if a_id not in valid_ids or b_id not in valid_ids:
            continue
        # 排序 id 保证 (a,b) 跟 (b,a) 同一条 (利用唯一索引去重)
        ai_, bi_ = sorted([a_id, b_id])
        try:
            db.execute(
                """INSERT OR IGNORE INTO fact_contradictions
                   (id, client_id, fact_a_id, fact_b_id, contradiction_type,
                    severity, review_status, resolution_note, detected_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
                (
                    _new_id("fc"), client_id, ai_, bi_,
                    str(p.get("type") or "value_diff"),
                    str(p.get("severity") or "medium"),
                    str(p.get("reason") or "")[:300],
                    now,
                ),
            )
            # rowcount 1 = 新插入, 0 = 已存在被 IGNORE
            if db.conn.total_changes > 0:
                stats["inserted"] += 1
            else:
                stats["skipped_dup"] += 1
        except Exception as exc:  # noqa: BLE001
            stats["errors"].append(f"pair {a_id[:8]}/{b_id[:8]}: {str(exc)[:80]}")

    try:
        db.conn.commit()
    except Exception:  # noqa: BLE001
        pass
    logger.info(
        "[verify contradictions] client=%s detected=%d inserted=%d dup=%d errors=%d",
        client_id, stats["detected"], stats["inserted"], stats["skipped_dup"], len(stats["errors"]),
    )
    return stats


# ─── #4 术语 canonical 化(批量, 不调 LLM) ──────────────────────────────────

def canonicalize_atomic_facts(db: Any, client_id: str) -> dict[str, Any]:
    """对 client 下所有 atomic_facts.subject_text 跑一遍 glossary canonical 化,
    把别名替换成 canonical name. 复用 glossary_helpers.canonicalize(纯规则, 无 LLM)."""
    stats = {"scanned": 0, "updated": 0, "errors": []}
    if not client_id:
        return stats
    try:
        from app.services.glossary_helpers import canonicalize
    except Exception as exc:  # noqa: BLE001
        stats["errors"].append(f"import canonicalize: {exc}")
        return stats

    rows = db.fetchall(
        """SELECT id, subject_text FROM atomic_facts
           WHERE client_id=? AND status='active' AND COALESCE(subject_text,'') != ''
           LIMIT 500""",
        (client_id,),
    )
    now = _now_iso()
    for r in rows:
        stats["scanned"] += 1
        original = str(r["subject_text"] or "").strip()
        if not original:
            continue
        try:
            normalized = canonicalize(db, client_id, original)
        except Exception as exc:  # noqa: BLE001
            stats["errors"].append(f"{r['id']}: {str(exc)[:60]}")
            continue
        if normalized and normalized != original:
            try:
                db.execute(
                    "UPDATE atomic_facts SET subject_text=?, updated_at=? WHERE id=?",
                    (normalized, now, r["id"]),
                )
                stats["updated"] += 1
            except Exception as exc:  # noqa: BLE001
                stats["errors"].append(f"update {r['id']}: {str(exc)[:60]}")

    try:
        db.conn.commit()
    except Exception:  # noqa: BLE001
        pass
    logger.info(
        "[canonicalize facts] client=%s scanned=%d updated=%d errors=%d",
        client_id, stats["scanned"], stats["updated"], len(stats["errors"]),
    )
    return stats


# ─── L3 入口: 给 broadcast 调用 ──────────────────────────────────────────────

def run_self_verify(db: Any, ai: Any, client_id: str) -> dict[str, Any]:
    """跑全套 L3 自校验. 串行(不并发, 避免 LLM 限流).

    各 verifier 独立 try, 一个失败不影响其他.
    """
    results: dict[str, Any] = {}
    # 先 canonicalize(纯规则, 快)
    try:
        results["canonicalize"] = canonicalize_atomic_facts(db, client_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[self_verify] canonicalize failed")
        results["canonicalize"] = {"error": str(exc)[:100]}
    # 再做实体聚类(LLM)
    try:
        results["entities_cluster"] = verify_entities_cluster(db, ai, client_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[self_verify] entities_cluster failed")
        results["entities_cluster"] = {"error": str(exc)[:100]}
    # 最后矛盾检测(LLM)
    try:
        results["contradictions"] = verify_contradictions(db, ai, client_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[self_verify] contradictions failed")
        results["contradictions"] = {"error": str(exc)[:100]}
    return results
