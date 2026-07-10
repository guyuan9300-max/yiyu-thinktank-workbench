"""Backfill 历史 v2_chunks 的实体/语义/事实/关系（迭代 2-6 follow-up）。

为什么需要：迭代 2-6 给每个 chunk 入库时即时跑了规则层抽取，但**历史
已入库**的 chunks 还停留在原状（entity_ids_json='[]', semantic_type=
'unclassified', 没有 atomic_facts / relationship_triples）。本脚本扫
整库把它们补上。

使用：
    cd backend
    uv run python -m scripts.backfill_understanding              # 全量
    uv run python -m scripts.backfill_understanding --client X   # 单客户
    uv run python -m scripts.backfill_understanding --dry-run    # 只数不写

幂等：再次运行不会重复抽取（按 entity_ids_json != '[]' 跳过已处理）。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# 允许脚本直接运行（python -m scripts.backfill_understanding）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database_guard import open_database_with_migration_guard  # noqa: E402
from app.db import Database  # noqa: E402
from app.services.contradiction_detector import persist_chunk_facts  # noqa: E402
from app.services.entity_extractor import extract_entities_from_chunk  # noqa: E402
from app.services.entity_store import persist_chunk_entities  # noqa: E402
from app.services.fact_extractor import extract_facts_from_chunk  # noqa: E402
from app.services.relation_extractor import extract_relations_from_chunk  # noqa: E402
from app.services.relation_store import persist_chunk_relations  # noqa: E402
from app.services.semantic_classifier import classify_chunk_semantic  # noqa: E402


def _default_db_path() -> Path:
    data_dir = Path(
        os.getenv("YIYU_WORKBENCH_DATA_DIR")
        or (Path.home() / "Library" / "Application Support" / "YiyuThinkTankWorkbench2")
    )
    return data_dir / "app.db"


def find_unprocessed_chunks(
    db: Database,
    *,
    client_id: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """找出还没抽过实体的 chunks（entity_ids_json='[]' 且 semantic_type=
    'unclassified' 视为未处理）。如果两者之一已处理过，认为这个 chunk
    走过 backfill，跳过。
    """
    where = ["(vc.entity_ids_json IN ('[]', '', NULL) OR vc.semantic_type = 'unclassified')"]
    params: list = []
    if client_id:
        where.append("vd.client_id = ?")
        params.append(client_id)
    where_sql = " AND ".join(where)
    limit_sql = f"LIMIT {int(limit)}" if limit else ""
    sql = f"""
        SELECT vc.id AS chunk_id,
               vc.content AS content,
               vc.v2_document_id AS v2_document_id,
               vd.client_id AS client_id,
               vd.imported_at AS created_at
        FROM v2_chunks vc
        JOIN v2_documents vd ON vd.id = vc.v2_document_id
        WHERE {where_sql}
        ORDER BY vd.imported_at DESC
        {limit_sql}
    """
    return [dict(r) for r in db.fetchall(sql, tuple(params))]


def process_chunk(
    db: Database,
    chunk: dict,
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    """对单个 chunk 跑完四类抽取。返回各部分计数。"""
    content = str(chunk.get("content") or "")
    chunk_id = str(chunk["chunk_id"])
    client_id = str(chunk["client_id"])
    v2_doc_id = str(chunk["v2_document_id"])
    created_at = str(chunk.get("created_at") or "")

    stats = {
        "entities": 0,
        "facts": 0,
        "contradictions": 0,
        "relations": 0,
        "semantic_set": 0,
    }

    if not content.strip():
        return stats

    # 1. 实体
    extracted_entities = extract_entities_from_chunk(content)
    if extracted_entities and not dry_run:
        ids = persist_chunk_entities(
            db.conn,
            client_id=client_id,
            v2_document_id=v2_doc_id,
            v2_chunk_id=chunk_id,
            extracted=extracted_entities,
            now=created_at,
        )
        stats["entities"] = len(ids)
    elif extracted_entities:
        stats["entities"] = len(extracted_entities)

    # 2. 语义分类
    semantic = classify_chunk_semantic(content)
    if not dry_run and semantic.semantic_type != "unclassified":
        db.conn.execute(
            "UPDATE v2_chunks SET semantic_type = ?, semantic_confidence = ? WHERE id = ?",
            (semantic.semantic_type, semantic.confidence, chunk_id),
        )
        stats["semantic_set"] = 1

    # 3. 事实 + 矛盾检测
    facts = extract_facts_from_chunk(content)
    if facts and not dry_run:
        inserted, contras = persist_chunk_facts(
            db.conn,
            client_id=client_id,
            v2_document_id=v2_doc_id,
            v2_chunk_id=chunk_id,
            facts=facts,
            now=created_at,
        )
        stats["facts"] = inserted
        stats["contradictions"] = contras
    elif facts:
        stats["facts"] = len(facts)

    # 4. 关系（依赖实体已入库 → 必须在 persist_chunk_entities 之后）
    relations = extract_relations_from_chunk(content)
    if relations and not dry_run:
        moved = persist_chunk_relations(
            db.conn,
            client_id=client_id,
            v2_document_id=v2_doc_id,
            v2_chunk_id=chunk_id,
            extracted=relations,
            now=created_at,
        )
        stats["relations"] = moved
    elif relations:
        stats["relations"] = len(relations)

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="backfill 历史 v2_chunks 的语义/实体/事实/关系")
    parser.add_argument("--client", help="只处理某个 client_id（默认全部）", default=None)
    parser.add_argument("--limit", type=int, help="最多处理多少个 chunk（默认无限）", default=None)
    parser.add_argument("--dry-run", action="store_true", help="只统计不写库")
    parser.add_argument("--db-path", help="自定义 SQLite 文件路径", default=None)
    args = parser.parse_args()

    db_path = Path(args.db_path) if args.db_path else _default_db_path()
    if not db_path.exists():
        print(f"[ERROR] 找不到数据库: {db_path}", file=sys.stderr)
        return 1

    print(f"[INFO] 数据库: {db_path}")
    db, _ = open_database_with_migration_guard(db_path)

    chunks = find_unprocessed_chunks(db, client_id=args.client, limit=args.limit)
    print(f"[INFO] 待处理 chunk 数: {len(chunks)}")
    if args.dry_run:
        print("[INFO] dry-run 模式，不会写入")

    totals = {
        "entities": 0,
        "facts": 0,
        "contradictions": 0,
        "relations": 0,
        "semantic_set": 0,
        "chunks_processed": 0,
    }
    batch = 0
    for index, chunk in enumerate(chunks, start=1):
        try:
            stats = process_chunk(db, chunk, dry_run=args.dry_run)
            for key, val in stats.items():
                totals[key] += val
            totals["chunks_processed"] += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] chunk {chunk['chunk_id']} 失败: {exc}", file=sys.stderr)
            continue
        batch += 1
        if not args.dry_run and batch >= 50:
            db.conn.commit()
            batch = 0
        if index % 100 == 0:
            print(
                f"[PROGRESS] {index}/{len(chunks)} "
                f"entities+{totals['entities']} facts+{totals['facts']} "
                f"contras+{totals['contradictions']} relations+{totals['relations']}"
            )
    if not args.dry_run and batch:
        db.conn.commit()

    print("\n[SUMMARY]")
    for k, v in totals.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
