"""[A] V2.6 R3-M4 · DataGapCompensator + ExternalEvidenceCardWriter

用户甲 5/23 R3 场景 4:
> 用户或 AI 在数据中心发现: '客户内部资料显示项目预算已调整,
>   但外部官网/媒体可能仍沿用旧口径.'
> 系统应该调用资讯情报站补证, 写入 external_evidence_cards.
> 但**外部信息不能直接覆盖内部权威事实**, 只能作为支持/冲突/滞后/待确认.

设计:
  · detect_data_gaps(client_id)        — 找客户事实里需要外部补证的 gap
  · find_intelligence_candidates(client_id, gap) — 从 intelligence_candidate_items 找相关
  · write_external_evidence_card(item, gap) — 转写到 external_evidence_cards
  · evaluate_external_relation(external_value, internal_value)
                                       — 判 supports/conflicts/lags/needs_confirm

L1/L2/L3 来源分级:
  · L1 — 客户官网 / 政府部门官网 (高可信)
  · L2 — 主流媒体 / 行业新闻 (中可信)
  · L3 — 自媒体 / 论坛 / 一般网络 (低可信)
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Protocol

logger = logging.getLogger(__name__)


class _DbLike(Protocol):
    def execute(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchone(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchall(self, sql: str, params: tuple = ...) -> Any: ...


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


ExternalRelation = Literal["supports", "conflicts", "lags", "needs_confirm", "unrelated"]
SourceLevel = Literal["L1", "L2", "L3"]


@dataclass
class DataGap:
    """一个数据 gap (缺外部证据或外部口径滞后)."""
    gap_type: str  # "version_diff_vs_external" / "no_external_evidence" / "outdated_external"
    subject: str
    internal_value: str | None = None
    external_value: str | None = None
    related_fact_ids: list[str] = field(default_factory=list)
    severity: str = "medium"
    suggested_action: str = ""


@dataclass
class ExternalEvidenceItem:
    title: str
    snippet: str
    url: str | None = None
    source_level: SourceLevel = "L2"
    relation_to_internal: ExternalRelation = "needs_confirm"
    related_internal_fact_id: str | None = None
    confidence: float = 0.5


# ─── schema ───────────────────────────────────────────


def ensure_external_evidence_schema(db: _DbLike) -> None:
    """V2.6 R3-M4 — external_evidence_cards 沿用 prod 现有 schema, 仅建 data_gaps 表."""
    # external_evidence_cards 是 prod 已存在表, 不重建; 这里只加 R3 兼容列
    for sql in [
        # 现有 schema 用 source_tier (L1/L2/L3), 不重建表
        "ALTER TABLE external_evidence_cards ADD COLUMN relation_to_internal TEXT DEFAULT 'needs_confirm'",
        "ALTER TABLE external_evidence_cards ADD COLUMN related_internal_fact_id TEXT",
    ]:
        try:
            db.execute(sql)
        except Exception:
            pass  # 列已存在
    for sql in [
        """CREATE TABLE IF NOT EXISTS data_gaps (
            id TEXT PRIMARY KEY,
            client_id TEXT,
            gap_type TEXT NOT NULL,
            subject TEXT NOT NULL,
            internal_value TEXT,
            external_value TEXT,
            related_fact_ids_json TEXT NOT NULL DEFAULT '[]',
            severity TEXT NOT NULL DEFAULT 'medium',
            suggested_action TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'open',
            detected_at TEXT NOT NULL
        )""",
        """CREATE INDEX IF NOT EXISTS idx_data_gaps_client
           ON data_gaps(client_id, status, detected_at DESC)""",
    ]:
        try:
            db.execute(sql)
        except Exception as exc:
            logger.warning("ensure_external_evidence_schema failed: %s", exc)


# ─── detect gaps ──────────────────────────────────────


def detect_data_gaps(db: _DbLike, client_id: str) -> list[DataGap]:
    """检测客户数据缺口 (需要外部补证).

    场景:
      A. atomic_facts 有 v2 新值 + atomic_facts 也有旧 internet_media 值 → outdated_external
      B. fact_contradictions 含 media_lag 类型 → outdated_external
      C. atomic_facts 高 confidence 但无任何 internet_* 来源 → no_external_evidence
    """
    gaps: list[DataGap] = []

    # A. media_lag 冲突
    try:
        rows = db.fetchall(
            """SELECT fc.id, fc.fact_a_id, fc.fact_b_id,
                      fa.subject_text AS a_subj, fa.value_text AS a_val, fa.source_type AS a_src,
                      fb.subject_text AS b_subj, fb.value_text AS b_val, fb.source_type AS b_src
               FROM fact_contradictions fc
               LEFT JOIN atomic_facts fa ON fa.id = fc.fact_a_id
               LEFT JOIN atomic_facts fb ON fb.id = fc.fact_b_id
               WHERE fc.client_id = ? AND fc.contradiction_type = 'media_lag'""",
            (client_id,),
        )
        for r in rows[:10]:
            d = dict(r)
            gaps.append(DataGap(
                gap_type="outdated_external",
                subject=d["a_subj"] or "",
                internal_value=d.get("b_val") if d.get("b_src", "").startswith("client_") else d.get("a_val"),
                external_value=d.get("a_val") if d.get("a_src", "") == "internet_media" else d.get("b_val"),
                related_fact_ids=[d["fact_a_id"], d["fact_b_id"]],
                severity="medium",
                suggested_action="向客户确认外部口径是否需要同步",
            ))
    except Exception as exc:
        logger.warning("detect media_lag failed: %s", exc)

    # B. atomic_facts 缺外部证据 (高 confidence 但无 internet_* 来源)
    try:
        subjs = db.fetchall(
            """SELECT subject_text, COUNT(DISTINCT source_type) AS src_diversity,
                      SUM(CASE WHEN source_type LIKE 'internet_%' THEN 1 ELSE 0 END) AS has_external
               FROM atomic_facts WHERE client_id = ? AND status = 'active' AND confidence >= 0.85
               GROUP BY subject_text
               HAVING has_external = 0 AND src_diversity >= 1
               LIMIT 10""",
            (client_id,),
        )
        for s in subjs:
            d = dict(s)
            gaps.append(DataGap(
                gap_type="no_external_evidence",
                subject=d["subject_text"],
                internal_value=None, external_value=None,
                severity="low",
                suggested_action=f"检索外部官网/媒体确认 {d['subject_text']} 的对外口径",
            ))
    except Exception:
        pass

    return gaps


def persist_data_gap(db: _DbLike, gap: DataGap, client_id: str) -> str:
    """持久化 gap."""
    ensure_external_evidence_schema(db)
    gid = f"gap_{uuid.uuid4().hex[:24]}"
    db.execute(
        """INSERT INTO data_gaps (
            id, client_id, gap_type, subject, internal_value, external_value,
            related_fact_ids_json, severity, suggested_action, status, detected_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)""",
        (gid, client_id, gap.gap_type, gap.subject, gap.internal_value, gap.external_value,
         json.dumps(gap.related_fact_ids, ensure_ascii=False),
         gap.severity, gap.suggested_action, _now_iso()),
    )
    return gid


# ─── external evidence card 写入 ────────────────────


def _classify_source_level(source: str, url: str | None = None) -> SourceLevel:
    """L1 (官网/政府) / L2 (主流媒体) / L3 (自媒体)."""
    s = (source or "").lower() + " " + (url or "").lower()
    if any(k in s for k in ["官网", "official", "gov.cn", ".gov.", "政府", "教育部",
                            "民政部", "财政部", "基金会官网"]):
        return "L1"
    if any(k in s for k in ["新华", "人民", "央视", "media", "新闻", "日报", "周刊"]):
        return "L2"
    return "L3"


def _evaluate_relation(external_text: str, internal_value: str | None) -> ExternalRelation:
    """判 supports/conflicts/lags/needs_confirm."""
    if not internal_value:
        return "needs_confirm"
    # 简单规则: 数字命中
    ext_nums = set(re.findall(r"\d+", external_text or ""))
    int_nums = set(re.findall(r"\d+", internal_value or ""))
    if not ext_nums or not int_nums:
        return "needs_confirm"
    if ext_nums & int_nums:
        return "supports"
    # 数字完全不同 → 可能 conflicts 或 lags
    # 简化: 假设内部为最新, 外部为旧 → lags
    return "lags"


def write_external_evidence_card(
    db: _DbLike, item: ExternalEvidenceItem, client_id: str,
    *, source_id: str | None = None,
) -> str:
    """写一条 external_evidence_card (适配 prod 现有 schema).

    prod schema:
      source_url / source_domain / source_tier (L1/L2/L3) / title
      fact_excerpt / summary / tags_json / related_scope_type / related_scope_id
      confidence / status / linked_proposal_ids_json / created_at / updated_at
      + R3 加: relation_to_internal / related_internal_fact_id
    """
    ensure_external_evidence_schema(db)
    cid = f"eec_{uuid.uuid4().hex[:24]}"
    now = _now_iso()

    url = item.url or "internal://intelligence_candidate"
    # source_domain 从 url 抽
    domain = "unknown"
    if item.url:
        m = re.search(r"://([^/]+)", item.url)
        if m:
            domain = m.group(1)
    db.execute(
        """INSERT INTO external_evidence_cards (
            id, source_url, source_domain, source_tier, title,
            published_at, fact_excerpt, summary, tags_json,
            related_scope_type, related_scope_id, confidence,
            status, review_note, linked_proposal_ids_json,
            created_at, updated_at,
            topic_candidate_id, client_id,
            relation_to_internal, related_internal_fact_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '[]', 'client', ?, ?,
                  'candidate', '', '[]', ?, ?, ?, ?, ?, ?)""",
        (
            cid, url, domain, item.source_level, item.title,
            _now_iso(),  # published_at
            item.snippet, item.snippet[:200],  # fact_excerpt + summary
            client_id, item.confidence, now, now,
            source_id, client_id,
            item.relation_to_internal, item.related_internal_fact_id,
        ),
    )
    return cid


def harvest_intelligence_for_client(
    db: _DbLike, client_id: str, *,
    keywords: list[str] | None = None,
    limit: int = 10,
) -> dict:
    """从 intelligence_candidate_items 拉跟 client 相关的, 写 external_evidence_cards.

    用户甲 R3 硬门槛 5: 外部情报不得覆盖内部权威, 只作支持/冲突/滞后/待确认.
    """
    ensure_external_evidence_schema(db)

    # 拉 intelligence 候选
    # 跟客户相关: title 或 snippet 含客户名 / 关键 keyword
    client_row = db.fetchone("SELECT name FROM clients WHERE id = ?", (client_id,))
    client_name = dict(client_row)["name"] if client_row else ""
    if not keywords:
        keywords = [client_name] if client_name else []

    if not keywords:
        return {"items_found": 0, "cards_written": 0}

    # WHERE clause: 任一 keyword 命中
    where_clauses = []
    params: list[Any] = []
    for kw in keywords:
        where_clauses.append("(title LIKE ? OR snippet LIKE ?)")
        params.extend([f"%{kw}%", f"%{kw}%"])
    where = " OR ".join(where_clauses)

    try:
        rows = db.fetchall(
            f"""SELECT id, title, snippet, url
                FROM intelligence_candidate_items WHERE {where}
                LIMIT {limit}""",
            tuple(params),
        )
    except Exception:
        rows = []

    cards_written = 0
    for r in rows:
        d = dict(r)
        level = _classify_source_level(d.get("title", "") + " " + (d.get("snippet") or ""), d.get("url"))
        relation = "needs_confirm"  # 默认待确认
        item = ExternalEvidenceItem(
            title=d.get("title", "")[:200],
            snippet=(d.get("snippet") or "")[:500],
            url=d.get("url"),
            source_level=level,
            relation_to_internal=relation,
            confidence=0.5 if level == "L3" else (0.7 if level == "L2" else 0.85),
        )
        try:
            write_external_evidence_card(db, item, client_id, source_id=d["id"])
            cards_written += 1
        except Exception as exc:
            logger.warning("write_external_evidence_card failed: %s", exc)

    return {
        "items_found": len(rows),
        "cards_written": cards_written,
        "keywords": keywords,
    }


# ─── 主入口 ──────────────────────────────────────────


def run_data_gap_pipeline(db: _DbLike, client_id: str) -> dict:
    """完整 pipeline: detect gaps + harvest + write external_evidence_cards."""
    ensure_external_evidence_schema(db)
    gaps = detect_data_gaps(db, client_id)
    gap_ids = [persist_data_gap(db, g, client_id) for g in gaps]
    harvest = harvest_intelligence_for_client(db, client_id)
    return {
        "gaps_detected": len(gaps),
        "gap_ids": gap_ids,
        "gap_details": [
            {"type": g.gap_type, "subject": g.subject,
             "internal": g.internal_value, "external": g.external_value,
             "action": g.suggested_action}
            for g in gaps
        ],
        "external_harvest": harvest,
    }
