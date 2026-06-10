"""数据中心 · 四仓健康仪表盘（只读）。

3+4 信息高速公路审计(2026-06-10 主干道一·仪表盘)落地：把审计里靠人工 SQL 才看得到的
「四仓行数/空表数、统一来源登记覆盖率、后台队列卡死、深读覆盖率」做成一个只读端点，
让"修好了/没修好"可被度量，而不是黑箱断言。

设计纪律：
- 纯只读：只 SELECT / PRAGMA，绝不写库。
- 全程表/列存在性 guard：在全新（空 schema）库上也返回 0 而非 500。
- 表名取自固定白名单（非用户输入），f-string 拼表名安全（SQLite 无法参数化表名）。
- 与既有 data-center status 家族(operational_status/artifact_status)并列，互不污染：
  本端点是"活数据健康"，operational_status 是"eval/发版裁决"，性质不同不合并。
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.db import Database

# 四仓代表表（分类依据见审计交付物《数据表四仓归属清单.csv》）。
# 只取每仓主力表做体检盘，不求全列 227 表。
_WAREHOUSES: dict[str, list[str]] = {
    "原始资料仓": ["documents", "v2_documents", "knowledge_documents", "chat_messages", "meetings", "imports"],
    "共识事实仓": ["entities", "entity_mentions", "atomic_facts", "memory_facts", "commitments", "risk_signals", "event_lines", "clients", "tasks"],
    "富化索引仓": ["v2_chunks", "v2_sections", "document_chunks", "knowledge_master_index", "evidence_cards", "knowledge_surrogates"],
    "认知产品仓": ["answer_runs", "answer_citations", "client_analysis_runs", "report_runs", "weekly_reviews", "context_packs", "strategic_thought_insights"],
}

# 后台队列表（按 status 分布 + 卡死计数）。
_QUEUE_TABLES: list[str] = [
    "job_stage_runs", "local_model_tasks", "document_deep_read_states",
    "analysis_jobs", "knowledge_jobs", "intelligence_fetch_jobs",
]

# 视为"在途"的状态值（用于卡死判定）。
_INFLIGHT = ("queued", "running", "pending")


def _table_exists(db: Database, name: str) -> bool:
    return db.fetchone(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ) is not None


def _columns(db: Database, name: str) -> set[str]:
    try:
        return {str(r[1]) for r in db.fetchall(f'PRAGMA table_info("{name}")')}
    except Exception:
        return set()


def _count(db: Database, name: str) -> int:
    """行数；表不存在返回 -1。"""
    if not _table_exists(db, name):
        return -1
    row = db.fetchone(f'SELECT COUNT(*) FROM "{name}"')
    return int(row[0]) if row else 0


def _warehouse_health(db: Database) -> dict[str, object]:
    out: dict[str, object] = {}
    for warehouse, tables in _WAREHOUSES.items():
        counts = {t: _count(db, t) for t in tables}
        present = {t: c for t, c in counts.items() if c >= 0}
        out[warehouse] = {
            "tables": counts,
            "total_rows": sum(c for c in present.values()),
            "empty_tables": sorted(t for t, c in present.items() if c == 0),
            "missing_tables": sorted(t for t, c in counts.items() if c < 0),
        }
    return out


def _table_population(db: Database) -> dict[str, int]:
    """全库表数 + 空表数（审计头条指标：54 空表/24%）。"""
    names = [
        str(r[0]) for r in db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    empty = 0
    for n in names:
        row = db.fetchone(f'SELECT COUNT(*) FROM "{n}"')
        if row is not None and int(row[0]) == 0:
            empty += 1
    return {"total_tables": len(names), "empty_tables": empty}


def _source_registration_coverage(db: Database) -> dict[str, object]:
    """统一来源登记覆盖率（北极星·来源可追溯）。"""
    af_total = _count(db, "atomic_facts")
    af_with_registry = 0
    af_with_v2doc = 0
    if af_total > 0:
        af_cols = _columns(db, "atomic_facts")
        if "source_registry_id" in af_cols:
            row = db.fetchone(
                "SELECT COUNT(*) FROM atomic_facts WHERE source_registry_id IS NOT NULL AND source_registry_id != ''"
            )
            af_with_registry = int(row[0]) if row else 0
        if "source_v2_document_id" in af_cols:
            row = db.fetchone(
                "SELECT COUNT(*) FROM atomic_facts WHERE source_v2_document_id IS NOT NULL AND source_v2_document_id != ''"
            )
            af_with_v2doc = int(row[0]) if row else 0

    ingest_by_type: dict[str, int] = {}
    if _table_exists(db, "data_center_ingest_events"):
        for r in db.fetchall(
            "SELECT source_type, COUNT(*) FROM data_center_ingest_events GROUP BY source_type ORDER BY 2 DESC"
        ):
            ingest_by_type[str(r[0])] = int(r[1])

    def _ratio(n: int, d: int) -> float:
        return round(n / d, 4) if d else 0.0

    return {
        "source_registry_rows": _count(db, "source_registry"),
        "data_center_ingest_events_rows": _count(db, "data_center_ingest_events"),
        "ingest_events_by_source_type": ingest_by_type,
        "documents_rows": _count(db, "documents"),
        "atomic_facts_total": af_total,
        "atomic_facts_with_source_registry": af_with_registry,
        "atomic_facts_with_v2_document": af_with_v2doc,
        # 蓝图理想：registry 覆盖≈1.0；真实主干：v2_document 溯源
        "registry_coverage_ratio": _ratio(af_with_registry, af_total),
        "provenance_coverage_ratio": _ratio(af_with_v2doc, af_total),
    }


def _queue_health(db: Database, name: str) -> dict[str, object]:
    if not _table_exists(db, name):
        return {"exists": False}
    cols = _columns(db, name)
    out: dict[str, object] = {"exists": True, "total": _count(db, name)}
    if "status" in cols:
        out["by_status"] = {
            str(r[0]): int(r[1])
            for r in db.fetchall(f'SELECT status, COUNT(*) FROM "{name}" GROUP BY status')
        }
        ts = "updated_at" if "updated_at" in cols else ("created_at" if "created_at" in cols else None)
        if ts:
            placeholders = ",".join("?" for _ in _INFLIGHT)
            for label, days in (("stuck_gt_24h", 1), ("stuck_gt_7d", 7)):
                row = db.fetchone(
                    f'SELECT COUNT(*) FROM "{name}" '
                    f"WHERE status IN ({placeholders}) AND {ts} != '' "
                    f"AND replace({ts}, 'T', ' ') < datetime('now', ?)",
                    (*_INFLIGHT, f"-{days} day"),
                )
                out[label] = int(row[0]) if row else 0
    return out


def _deep_read_coverage(db: Database) -> dict[str, object]:
    """系统级深读覆盖（与 document_deep_read_service.coverage_for_client 同口径，不分客户）。"""
    docs = _count(db, "v2_documents")
    deep = 0
    if _table_exists(db, "knowledge_surrogates"):
        # 与 document_deep_read_service.coverage_for_client 同口径：source_type='document' 行数。
        if "source_type" in _columns(db, "knowledge_surrogates"):
            row = db.fetchone("SELECT COUNT(*) FROM knowledge_surrogates WHERE source_type='document'")
        else:
            row = db.fetchone("SELECT COUNT(*) FROM knowledge_surrogates")
        deep = int(row[0]) if row and row[0] is not None else 0
    chunk_covered = -1
    if "chunk_count" in _columns(db, "v2_documents"):
        row = db.fetchone("SELECT COUNT(*) FROM v2_documents WHERE chunk_count > 0")
        chunk_covered = int(row[0]) if row else 0
    return {
        "v2_documents": docs,
        "deep_read_done": deep,
        "deep_read_coverage_ratio": round(deep / docs, 4) if docs else 0.0,
        "v2_documents_with_chunks": chunk_covered,
        "chunk_coverage_ratio": round(chunk_covered / docs, 4) if (docs and chunk_covered >= 0) else 0.0,
    }


def build_data_center_health_dashboard(db: Database) -> dict[str, object]:
    """组装四仓健康仪表盘（只读）。"""
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "tablePopulation": _table_population(db),
        "warehouses": _warehouse_health(db),
        "sourceRegistration": _source_registration_coverage(db),
        "queues": {name: _queue_health(db, name) for name in _QUEUE_TABLES},
        "deepRead": _deep_read_coverage(db),
    }
