"""仅重抽 atomic_facts + fact_contradictions（清理噪音后用）。

不动 entities/relations/semantic（那些已经 backfill 过且没有噪音问题）。
只对所有 v2_chunks 重新跑 fact_extractor（修复了 attribute 末尾虚词噪音）
+ contradiction_detector（修复了同事实重复 N 次造成的 N×N 告警）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.services.contradiction_detector import persist_chunk_facts
from app.services.fact_extractor import extract_facts_from_chunk


def _default_db_path() -> Path:
    data_dir = Path(
        os.getenv("YIYU_WORKBENCH_DATA_DIR")
        or (Path.home() / "Library" / "Application Support" / "YiyuThinkTankWorkbench2")
    )
    return data_dir / "app.db"


def main() -> int:
    db = Database(_default_db_path())
    print(f"[INFO] DB: {_default_db_path()}")

    rows = db.fetchall(
        """
        SELECT vc.id AS chunk_id, vc.content AS content,
               vc.v2_document_id AS v2_document_id,
               vd.client_id AS client_id,
               vd.imported_at AS created_at
        FROM v2_chunks vc
        JOIN v2_documents vd ON vd.id = vc.v2_document_id
        ORDER BY vd.imported_at DESC
        """
    )
    print(f"[INFO] 待重抽 chunk 数: {len(rows)}")

    total_facts = 0
    total_contradictions = 0
    batch = 0
    for index, row in enumerate(rows, start=1):
        content = str(row["content"] or "")
        if not content.strip():
            continue
        client_id = str(row["client_id"])
        v2_doc_id = str(row["v2_document_id"])
        chunk_id = str(row["chunk_id"])
        created_at = str(row["created_at"] or "")
        try:
            facts = extract_facts_from_chunk(content)
            if facts:
                inserted, contras = persist_chunk_facts(
                    db.conn,
                    client_id=client_id,
                    v2_document_id=v2_doc_id,
                    v2_chunk_id=chunk_id,
                    facts=facts,
                    now=created_at,
                )
                total_facts += inserted
                total_contradictions += contras
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] chunk {chunk_id}: {exc}", file=sys.stderr)
            continue
        batch += 1
        if batch >= 100:
            db.conn.commit()
            batch = 0
        if index % 500 == 0:
            print(f"[PROGRESS] {index}/{len(rows)} facts+{total_facts} contras+{total_contradictions}")
    if batch:
        db.conn.commit()

    print(f"\n[SUMMARY]")
    print(f"  facts: {total_facts}")
    print(f"  contradictions: {total_contradictions}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
