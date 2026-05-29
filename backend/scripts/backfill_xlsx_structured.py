"""xlsx 重解析 backfill：把现有 xlsx 文档结构化解析后写入 structured_tables。

Phase 0/1 代码已经合入，但生产环境的 structured_tables 表是空的——
所有历史 xlsx 还是用旧的 `_archive_xml_text` 路径只拿到了拼接文本。
本脚本对所有 kind='xlsx' 的 v2_documents 重跑 parse_xlsx_structured，
然后 upsert_table_from_parsed_sheet 落入 structured_tables。

只做 xlsx：pptx 的结构化需要重写 v2_chunks（会失效已存在的
entity_ids_json / semantic_type / facts / contradictions），影响面太大，
留作独立决策。

不动 v2_chunks：旧的拼接文本 chunks 保留，让现有检索路径继续工作；
structured_tables 是叠加的新能力（结构化计算路径），互不干扰。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.services.structured_table_parser import (
    StructuredParseError,
    parse_xlsx_structured,
)
from app.services.structured_table_store import upsert_table_from_parsed_sheet


def _default_db_path() -> Path:
    data_dir = Path(
        os.getenv("YIYU_WORKBENCH_DATA_DIR")
        or (Path.home() / "Library" / "Application Support" / "YiyuThinkTankWorkbench2")
    )
    return data_dir / "app.db"


def _resolve_file_path(managed_path: str, original_path: str) -> Path | None:
    """优先 managed_path（导入后保留在 client_workspace 的副本）。"""
    for candidate in (managed_path, original_path):
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            return path
    return None


def main() -> int:
    db = Database(_default_db_path())
    print(f"[INFO] DB: {_default_db_path()}")

    rows = db.fetchall(
        """
        SELECT id AS v2_document_id,
               client_id AS client_id,
               document_id AS knowledge_document_id,
               file_name AS file_name,
               managed_path AS managed_path,
               original_path AS original_path
        FROM v2_documents
        WHERE kind = 'xlsx'
        ORDER BY imported_at DESC
        """
    )
    print(f"[INFO] xlsx 文档: {len(rows)}")

    total_sheets = 0
    parsed_docs = 0
    failed_docs = 0
    missing_files = 0

    for index, row in enumerate(rows, start=1):
        v2_doc_id = str(row["v2_document_id"])
        client_id = str(row["client_id"] or "")
        knowledge_doc_id = str(row["knowledge_document_id"] or "") or None
        file_name = str(row["file_name"] or "")
        managed_path = str(row["managed_path"] or "")
        original_path = str(row["original_path"] or "")

        target_path = _resolve_file_path(managed_path, original_path)
        if target_path is None:
            print(
                f"[SKIP] [{index}/{len(rows)}] {file_name}: 文件不存在"
                f" (managed={managed_path!r}, original={original_path!r})"
            )
            missing_files += 1
            continue

        try:
            sheets = parse_xlsx_structured(target_path)
        except StructuredParseError as exc:
            print(f"[FAIL] [{index}/{len(rows)}] {file_name}: {exc}")
            failed_docs += 1
            continue
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] [{index}/{len(rows)}] {file_name}: {type(exc).__name__}: {exc}")
            failed_docs += 1
            continue

        doc_sheets_written = 0
        for sheet_index, parsed in enumerate(sheets):
            try:
                upsert_table_from_parsed_sheet(
                    db.conn,
                    client_id=client_id,
                    v2_document_id=v2_doc_id,
                    knowledge_document_id=knowledge_doc_id,
                    sheet_index=sheet_index,
                    parsed=parsed,
                )
                doc_sheets_written += 1
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[WARN] {file_name} / {parsed.sheet_name}:"
                    f" {type(exc).__name__}: {exc}"
                )
        db.conn.commit()
        total_sheets += doc_sheets_written
        parsed_docs += 1
        print(
            f"[OK] [{index}/{len(rows)}] {file_name}"
            f" → {doc_sheets_written}/{len(sheets)} sheets"
        )

    print("\n[SUMMARY]")
    print(f"  xlsx 总数: {len(rows)}")
    print(f"  成功解析:   {parsed_docs}")
    print(f"  解析失败:   {failed_docs}")
    print(f"  文件缺失:   {missing_files}")
    print(f"  写入 sheets: {total_sheets}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
