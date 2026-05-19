"""证据等级分层 / Evidence Tier（P9）。

定位：数据中心防污染的核心约定。3 类源严格隔离：

  first_party                : 客户自报 → 任务/会议/复盘/事件线/客户上传文档
                                可作为客户事实 source of truth

  third_party_authoritative  : 权威外部 → 民政/工商/慈善中国/天眼查
                                可作为客户事实，但必须标注来源

  external_observation       : 爬虫观察 → 媒体/UGC/搜狗微信/百家号
                                **只能作为背景参考**，禁止作为客户事实！


用法规范（强制约定，所有下游消费者必须 follow）：

  ✅ 摸底表 evaluator (fill_table_evaluator):
       只接受 first_party + third_party_authoritative 进 verified
       external_observation 即使 LLM 抽出三元组也只进「背景参考」区

  ✅ 战略陪伴 / 客户档案 / 周复盘等"客户事实"展示:
       默认只读 first_party；权威外部加来源标记；爬虫观察单独折叠

  ✅ 资讯情报站 (舆情/时效):
       既消费 external_observation（这就是它的工作），也消费 third_party_authoritative
       不会污染数据中心的事实层

  ❌ 错误用法：把 external_observation 抽出的 fact 直接写进 client_glossary 主表
              → 应该写进单独的 background_observation 视图或者打 tier 标记
"""
from __future__ import annotations

from typing import Any, Literal

from app.db import Database


EvidenceTier = Literal[
    "first_party",
    "third_party_authoritative",
    "external_observation",
]

# 默认信任档：可作为客户事实的两档
TRUSTED_TIERS: tuple[str, ...] = ("first_party", "third_party_authoritative")

# 仅背景参考档
BACKGROUND_TIERS: tuple[str, ...] = ("external_observation",)

# 全部档（极少需要——通常说明下游缺乏 tier 意识）
ALL_TIERS: tuple[str, ...] = (
    "first_party",
    "third_party_authoritative",
    "external_observation",
)


# ──────────────────────────────────────────────────────────────────────────
# 查询 helpers
# ──────────────────────────────────────────────────────────────────────────


def fetch_client_facts(
    db: Database,
    *,
    client_id: str,
    tiers: tuple[str, ...] = TRUSTED_TIERS,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """从 data_center_ingest_events 拉客户的"事实"事件。

    默认只返回 first_party + third_party_authoritative。
    爬虫观察（external_observation）需要明确传 tiers 才能拿到。
    """
    if not tiers:
        return []
    placeholders = ",".join("?" * len(tiers))
    rows = db.fetchall(
        f"""
        SELECT id, source_type, source_id, title, content_hash, evidence_tier,
               source_entity_type, source_entity_id,
               lifecycle_status, metadata_json, created_at, updated_at
        FROM data_center_ingest_events
        WHERE client_id = ?
          AND evidence_tier IN ({placeholders})
          AND lifecycle_status = 'active'
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (client_id, *tiers, limit),
    )
    return [dict(row) for row in rows]


def fetch_client_background_observations(
    db: Database,
    *,
    client_id: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """专门查爬虫抓回的背景观察（external_observation）。

    资讯情报站消费这个；摸底表 evaluator **不应** 调这个。
    """
    return fetch_client_facts(
        db, client_id=client_id, tiers=BACKGROUND_TIERS, limit=limit,
    )


def fetch_glossary_attributes_filtered(
    db: Database,
    *,
    client_id: str,
    tiers: tuple[str, ...] = TRUSTED_TIERS,
    verification_status: str | None = None,
) -> list[dict[str, Any]]:
    """读 glossary_attributes 时按 evidence_tier 过滤。

    fill_table_evaluator 应该调这个而非直接 SELECT *，避免把爬虫
    抽出的「媒体报道说募捐 1000 万」误当成客户官方事实。
    """
    if not tiers:
        return []
    placeholders = ",".join("?" * len(tiers))
    sql = f"""
        SELECT id, term_id, attribute_name, value_category, value_text,
               value_unit, scope, as_of_date, source_type, source_doc_id,
               source_evidence, confidence, verification_status,
               evidence_tier, created_at, updated_at
        FROM glossary_attributes
        WHERE client_id = ?
          AND evidence_tier IN ({placeholders})
    """
    params: list[Any] = [client_id, *tiers]
    if verification_status:
        sql += " AND verification_status = ?"
        params.append(verification_status)
    sql += " ORDER BY confidence DESC, updated_at DESC"
    rows = db.fetchall(sql, tuple(params))
    return [dict(row) for row in rows]


def tier_breakdown(
    db: Database,
    *,
    client_id: str,
) -> dict[str, dict[str, int]]:
    """给"数据中心健康度"用：客户每类源各有多少 fact。

    Returns: {
      'ingest_events': {'first_party': N, 'third_party_authoritative': M, 'external_observation': K},
      'glossary_attributes': {...},
    }
    """
    out: dict[str, dict[str, int]] = {}
    for table in ("data_center_ingest_events", "glossary_attributes"):
        try:
            rows = db.fetchall(
                f"""
                SELECT evidence_tier, COUNT(*) AS c
                FROM {table}
                WHERE client_id = ?
                GROUP BY evidence_tier
                """,
                (client_id,),
            )
            out[table] = {str(r["evidence_tier"] or "unknown"): int(r["c"]) for r in rows}
        except Exception:  # noqa: BLE001
            out[table] = {}
    return out


# ──────────────────────────────────────────────────────────────────────────
# 写入 helpers
# ──────────────────────────────────────────────────────────────────────────


def mark_glossary_attribute_tier(
    db: Database,
    *,
    attribute_id: str,
    evidence_tier: str,
) -> None:
    """更新某条 glossary_attribute 的证据等级。

    E 任务的 Stage 3 抽取出 attribute 后应该调这个明确打 tier。
    """
    if evidence_tier not in ALL_TIERS:
        raise ValueError(f"invalid evidence_tier: {evidence_tier}")
    db.execute(
        "UPDATE glossary_attributes SET evidence_tier = ?, updated_at = ? WHERE id = ?",
        (evidence_tier, _now_iso(), attribute_id),
    )


def infer_tier_from_source_doc(
    db: Database,
    source_doc_id: str | None,
) -> str:
    """从源文档反推 evidence_tier，方便 Stage 3 抽取时自动打标。

    - 如果文档来源是客户上传 → first_party
    - 如果文档来源是 internet_crawler 抓的，看对应 ingest_event 的 tier
    - 拿不到时默认 external_observation（保守）
    """
    if not source_doc_id:
        return "external_observation"
    try:
        row = db.fetchone(
            """
            SELECT origin_type, source_entity_type
            FROM documents WHERE id = ?
            """,
            (source_doc_id,),
        )
        if not row:
            return "external_observation"
        origin = str(row["origin_type"] or "")
        if origin in ("file_import", "user_upload", "task", "meeting"):
            return "first_party"
        if origin in ("internet_crawler", "external_search"):
            return "external_observation"
        return "external_observation"
    except Exception:  # noqa: BLE001
        return "external_observation"


# ──────────────────────────────────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    from datetime import datetime
    return datetime.utcnow().replace(microsecond=0).isoformat()
