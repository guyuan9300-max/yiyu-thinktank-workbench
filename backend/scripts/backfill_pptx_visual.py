"""把存量 pptx 拆成 per-slide 任务，入到 local_model_tasks 队列。

走完 Phase 0+1 后用：
  ./backend/.venv/bin/python backend/scripts/backfill_pptx_visual.py --dry-run
  ./backend/.venv/bin/python backend/scripts/backfill_pptx_visual.py --enqueue

不直接跑 OCR，只入队。实际执行交给 local_model_optimizer 后台 worker
（用户可在设置面板里看到队列、暂停、调阈值）。

幂等：UNIQUE(task_type, knowledge_document_id, input_hash) 保证同 slide 入队
两次只产生一条 task；input_hash 用 v2_document_id+slide_no 计算。

清理：开启 --clean-existing-chunks 时，会先清掉这些 pptx 的旧 v2_chunks 以及
对应的 entity_mentions / atomic_facts，避免 Phase 1 跑完后出现新旧混杂。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database_guard import open_database_with_migration_guard
from app.services.local_model_optimizer import (
    TASK_TYPE_VISUAL_OCR,
    DEFAULT_PROFILE_ID,
)


def _default_db_path() -> Path:
    base = Path(
        os.getenv("YIYU_WORKBENCH_DATA_DIR")
        or (Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2")
    )
    return base / "app.db"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _input_hash(v2_document_id: str, slide_no: int) -> str:
    payload = f"{TASK_TYPE_VISUAL_OCR}|{v2_document_id}|{slide_no}"
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def _resolve_file_path(managed_path: str, original_path: str) -> Path | None:
    for candidate in (managed_path, original_path):
        if not candidate:
            continue
        p = Path(candidate)
        if p.exists():
            return p
    return None


def _slide_count(pptx_path: Path) -> int:
    try:
        from pptx import Presentation  # noqa: PLC0415

        prs = Presentation(str(pptx_path))
        return len(list(prs.slides))
    except Exception as exc:  # noqa: BLE001
        print(f"  [WARN] 打开失败 {pptx_path.name}: {exc}", file=sys.stderr)
        return 0


def _clean_existing(db: Database, v2_document_id: str) -> dict[str, int]:
    """删该 pptx 的所有旧 v2_chunks/sections + 对应 entity_mentions/atomic_facts。"""
    counts = {"chunks": 0, "sections": 0, "mentions": 0, "facts": 0}

    rows = db.fetchall(
        "SELECT id FROM v2_chunks WHERE v2_document_id = ?",
        (v2_document_id,),
    )
    chunk_ids = [str(r["id"]) for r in rows]

    if chunk_ids:
        ph = ",".join("?" * len(chunk_ids))
        cur = db.conn.execute(
            f"DELETE FROM entity_mentions WHERE v2_chunk_id IN ({ph})",
            chunk_ids,
        )
        counts["mentions"] = cur.rowcount
        cur = db.conn.execute(
            f"DELETE FROM atomic_facts WHERE source_v2_chunk_id IN ({ph})",
            chunk_ids,
        )
        counts["facts"] = cur.rowcount

    cur = db.conn.execute(
        "DELETE FROM v2_chunks WHERE v2_document_id = ?",
        (v2_document_id,),
    )
    counts["chunks"] = cur.rowcount
    cur = db.conn.execute(
        "DELETE FROM v2_sections WHERE v2_document_id = ?",
        (v2_document_id,),
    )
    counts["sections"] = cur.rowcount
    db.conn.commit()
    return counts


def _resolve_knowledge_document_id(db: Database, v2_document_id: str) -> str:
    """v2_documents.document_id → 'kd_<inner>'  if knowledge_documents 行存在。"""
    row = db.fetchone(
        "SELECT document_id FROM v2_documents WHERE id = ?",
        (v2_document_id,),
    )
    if not row:
        return ""
    inner = str(row["document_id"] or "")
    if not inner:
        return ""
    candidate = f"kd_{inner}"
    kd_row = db.fetchone(
        "SELECT id FROM knowledge_documents WHERE id = ?",
        (candidate,),
    )
    return str(kd_row["id"]) if kd_row else ""


def _enqueue_one(
    db: Database,
    *,
    v2_document_id: str,
    knowledge_document_id: str,
    client_id: str,
    file_name: str,
    file_path: str,
    slide_no: int,
    priority: int,
) -> bool:
    payload = {
        "source_kind": "pptx_slide_images",
        "source_path": file_path,
        "source_v2_document_id": v2_document_id,
        "source_client_id": client_id,
        "region": {"slide_no": slide_no},
        "title": file_name,
    }
    task_id = _new_id("lmt")
    now = _now_iso()
    try:
        db.conn.execute(
            """
            INSERT INTO local_model_tasks (
                id, task_type, client_id, knowledge_document_id,
                model_profile_id, model_name, status, priority,
                input_hash, payload_json, result_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, '', 'queued', ?, ?, ?, '{}', ?, ?)
            """,
            (
                task_id,
                TASK_TYPE_VISUAL_OCR,
                client_id,
                knowledge_document_id,  # FK 指向 knowledge_documents
                "local_vision_ocr",
                priority,
                _input_hash(v2_document_id, slide_no),
                json.dumps(payload, ensure_ascii=False),
                now,
                now,
            ),
        )
        return True
    except Exception as exc:  # noqa: BLE001
        # UNIQUE 冲突 = 已入过队，跳过
        if "UNIQUE" in str(exc) or "constraint" in str(exc).lower():
            return False
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="把存量 pptx 按 slide 入到 local_model_tasks")
    parser.add_argument("--db-path", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true", help="只列出，不入队")
    parser.add_argument(
        "--enqueue", action="store_true",
        help="确认入队（必须显式指定，防误操作）",
    )
    parser.add_argument(
        "--clean-existing-chunks", action="store_true",
        help="入队前清掉旧 v2_chunks/sections + 关联的 entity_mentions/atomic_facts",
    )
    parser.add_argument("--limit", type=int, default=0, help="只处理前 N 个 pptx")
    args = parser.parse_args()

    if not args.dry_run and not args.enqueue:
        print("必须指定 --dry-run 或 --enqueue", file=sys.stderr)
        return 2

    db_path = args.db_path or _default_db_path()
    db, _ = open_database_with_migration_guard(db_path)
    print(f"[INFO] DB: {db_path}")

    rows = db.fetchall(
        """
        SELECT id, client_id, file_name, managed_path, original_path, chunk_count
        FROM v2_documents
        WHERE kind = 'pptx'
        ORDER BY imported_at DESC
        """
    )
    print(f"[INFO] pptx 总数: {len(rows)}")

    total_enqueued = 0
    total_skipped = 0
    total_missing = 0
    total_cleaned_chunks = 0
    processed_docs = 0

    for index, row in enumerate(rows, start=1):
        if args.limit and processed_docs >= args.limit:
            break

        v2_id = str(row["id"])
        client_id = str(row["client_id"] or "")
        file_name = str(row["file_name"] or "")
        managed = str(row["managed_path"] or "")
        original = str(row["original_path"] or "")

        path = _resolve_file_path(managed, original)
        if path is None:
            print(f"  [SKIP] {file_name}: 磁盘上找不到")
            total_missing += 1
            continue

        n_slides = _slide_count(path)
        if n_slides <= 0:
            print(f"  [SKIP] {file_name}: slide 数读不到")
            total_missing += 1
            continue

        if args.dry_run:
            print(f"  [DRY] {file_name} → {n_slides} slides")
            processed_docs += 1
            continue

        # 真入队
        if args.clean_existing_chunks:
            cleanup = _clean_existing(db, v2_id)
            total_cleaned_chunks += cleanup["chunks"]
            if any(cleanup.values()):
                print(
                    f"  [CLEAN] {file_name}: "
                    f"chunks={cleanup['chunks']} mentions={cleanup['mentions']} facts={cleanup['facts']}"
                )

        # 解析 FK 用的 knowledge_document_id
        kd_id = _resolve_knowledge_document_id(db, v2_id)
        if not kd_id:
            print(f"  [SKIP] {file_name}: 没有对应的 knowledge_documents 行")
            total_missing += 1
            continue

        enqueued = 0
        skipped = 0
        for slide_no in range(1, n_slides + 1):
            ok = _enqueue_one(
                db,
                v2_document_id=v2_id,
                knowledge_document_id=kd_id,
                client_id=client_id,
                file_name=file_name,
                file_path=str(path),
                slide_no=slide_no,
                priority=100 + index,
            )
            if ok:
                enqueued += 1
            else:
                skipped += 1
        db.conn.commit()
        total_enqueued += enqueued
        total_skipped += skipped
        processed_docs += 1
        print(
            f"  [ENQ ] {file_name} → 入队 {enqueued}/{n_slides}"
            f"{(' (已存在 ' + str(skipped) + ')') if skipped else ''}"
        )

    print("\n[SUMMARY]")
    print(f"  pptx 处理:     {processed_docs}")
    print(f"  入队 tasks:    {total_enqueued}")
    print(f"  跳过 tasks:    {total_skipped} (已存在或 UNIQUE 冲突)")
    print(f"  磁盘缺失:      {total_missing}")
    if args.clean_existing_chunks:
        print(f"  清理旧 chunks: {total_cleaned_chunks}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
