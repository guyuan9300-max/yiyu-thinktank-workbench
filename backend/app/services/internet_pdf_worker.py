"""互联网 PDF · 后台 OCR worker.

== 解决的真问题 ==

公益年报 PDF 95% 是扫描件 (image-based, 无文字层). 单个 25MB 95 页扫描件
完整 OCR (含 retry round 2/3) 实测 ~1-2 小时. 这种 IO+CPU 重的工作绝不能
卡在用户主流程里 (爬虫调用 / API 请求 / 字典 Stage 1 调用都不等).

== 闲时 worker 设计 ==

  1. 爬虫层只下载 PDF + 写 v2_documents (parse_status='pending_ocr') → 秒级返回
  2. 后台 worker daemon thread 启动 → 每 60s 扫一次 pending_ocr
  3. 取 1 个 PDF (按落档时间 FIFO) → 调 ingest_document_knowledge 完整 OCR
     (不限页数, 让 OCR retry 跑完, 目标是把整个年报里所有字段都抽出来)
  4. 完成后 parse_status='ready', 触发 fact_extractor + Stage 3 增量
  5. 串行处理避免并发资源冲突, 一个一个慢慢跑

== 机制化原则 ==

  · 用户感受不到 OCR 在跑 (后台线程, daemon, uvicorn 退出自动结束)
  · 30 个客户的 30 个年报 PDF 全部下载落档后, worker 自动顺序 OCR 完
  · 失败的 PDF 标 parse_status='ocr_failed' 跳过 (避免反复重跑)
  · 完整性优先: 不限 OCR 页数, 不切断 retry, 目标是抽完整个 PDF
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# worker 单例锁: 避免重复启动
_WORKER_STARTED = False
_WORKER_LOCK = threading.Lock()

# 内存状态 (供 UI 查询当前 OCR 进度)
_CURRENT_PROCESSING: dict[str, Any] = {
    "doc_id": None,
    "client_id": None,
    "file_name": None,
    "started_at": None,
    "stage": None,  # "ocr" / "fact_extract" / "stage3"
}


def get_current_processing_status() -> dict[str, Any]:
    """供 UI/API 查询: 当前 worker 在处理哪个 PDF.

    返回 dict 含: doc_id, client_id, file_name, started_at, stage. 没在跑时全 None.
    """
    return dict(_CURRENT_PROCESSING)


def _find_next_pending_pdf(db: Any) -> dict | None:
    """找下一个待 OCR 的 PDF.

    选取规则:
      - parse_status = 'pending_ocr'
      - content_domain = 'internet_enrichment'
      - kind = 'pdf'
      - 按 imported_at 升序 (先到先服务)
    """
    row = db.fetchone(
        """SELECT v.id AS v2_id, v.document_id, v.client_id, v.file_name, v.original_path,
                  v.imported_at, d.title
           FROM v2_documents v LEFT JOIN documents d ON d.id = v.document_id
           WHERE v.parse_status = 'pending_ocr'
             AND v.content_domain = 'internet_enrichment'
             AND v.kind = 'pdf'
           ORDER BY v.imported_at ASC
           LIMIT 1""",
    )
    return dict(row) if row else None


def _ensure_import_row(db: Any, *, import_id: str, client_id: str, source_path: str) -> None:
    """确保 imports 表有对应行 (满足 knowledge_documents FK)."""
    if db.fetchone("SELECT id FROM imports WHERE id = ?", (import_id,)):
        return
    now = datetime.now(timezone.utc).isoformat()
    try:
        db.execute(
            """INSERT INTO imports(id, client_id, source_path, mode, status, imported_count, skipped_count, created_at)
               VALUES (?, ?, ?, 'internet_pdf_worker', 'running', 0, 0, ?)""",
            (import_id, client_id, source_path, now),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[internet-pdf-worker] imports insert failed: %s", exc)


def _process_one_pdf(db: Any, ai_service: Any, data_dir: Path, pending: dict) -> bool:
    """处理 1 个 pending PDF: 完整 OCR + ingest + fact 抽取.

    返回 True 表示成功, False 失败 (parse_status 已标 ocr_failed).
    """
    from app.services.knowledge_v2 import ingest_document_knowledge

    v2_id = str(pending["v2_id"])
    doc_id = str(pending["document_id"])
    client_id = str(pending["client_id"])
    file_name = str(pending["file_name"] or "")
    pdf_path = Path(pending["original_path"]) if pending["original_path"] else None
    title = str(pending.get("title") or file_name)

    if not pdf_path or not pdf_path.exists():
        logger.warning("[internet-pdf-worker] PDF 物理文件缺失, 跳过并标 ocr_failed: %s", pdf_path)
        try:
            db.execute(
                "UPDATE v2_documents SET parse_status='ocr_failed', parse_error=? WHERE id=?",
                ("PDF 物理文件缺失", v2_id),
            )
        except Exception:  # noqa: BLE001
            pass
        return False

    # 标记当前正在处理 (供 UI 显示)
    started_at = datetime.now(timezone.utc).isoformat()
    _CURRENT_PROCESSING.update({
        "doc_id": doc_id, "client_id": client_id, "file_name": file_name,
        "started_at": started_at, "stage": "ocr",
    })

    # 先把状态改成 ocr_running, 防止并发重复处理
    try:
        db.execute(
            "UPDATE v2_documents SET parse_status='ocr_running' WHERE id=?",
            (v2_id,),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[internet-pdf-worker] status update failed: %s", exc)

    import_id = f"imp_pdf_worker_{uuid.uuid4().hex[:10]}"
    _ensure_import_row(db, import_id=import_id, client_id=client_id, source_path=str(pdf_path))

    logger.info(
        "[internet-pdf-worker] start OCR · client=%s · file=%s · size=%.1fMB",
        client_id, file_name, pdf_path.stat().st_size / 1024 / 1024,
    )
    t0 = time.time()
    try:
        # 关键: ocr_max_pages 设大 (完整性优先), ocr_continue_to_end=True
        # 让 OCR pipeline 自己决定何时停 (retry 直到 doc_score ≥ 0.85)
        ingest_document_knowledge(
            db, data_dir=data_dir, client_id=client_id,
            import_id=import_id,
            document_id=doc_id, source_path=pdf_path, original_source_path=pdf_path,
            title=title, kind="pdf", source="internet_enrichment",
            fallback_excerpt=f"互联网 PDF · OCR worker 处理 · {file_name[:40]}",
            created_at=started_at,
            ai_service=ai_service,
            force_ocr=False,                 # fitz 抽得到文字就不强制 OCR
            ocr_max_pages=200,               # 实际公益年报很少 > 200 页
            ocr_continue_to_end=True,        # 完整跑, 不切断
        )
        elapsed = time.time() - t0
        logger.info("[internet-pdf-worker] OCR done · %s · %.0fs", file_name, elapsed)

        # ingest_document_knowledge 内部已经把 parse_status 改成 'ready' 并写 chunks
        _CURRENT_PROCESSING["stage"] = "fact_extract"

        # 触发 Stage 3 增量 (扫新增 chunks 抽属性) — 通过运行额外的字典补全步骤
        try:
            _trigger_stage3_increment(db, ai_service, client_id)
            _CURRENT_PROCESSING["stage"] = "stage3_done"
        except Exception as exc:  # noqa: BLE001
            logger.warning("[internet-pdf-worker] Stage 3 trigger failed: %s", exc)

        return True
    except Exception as exc:  # noqa: BLE001
        elapsed = time.time() - t0
        logger.warning(
            "[internet-pdf-worker] OCR failed after %.0fs · %s · %s",
            elapsed, file_name, exc,
        )
        try:
            db.execute(
                "UPDATE v2_documents SET parse_status='ocr_failed', parse_error=? WHERE id=?",
                (str(exc)[:500], v2_id),
            )
        except Exception:  # noqa: BLE001
            pass
        return False
    finally:
        _CURRENT_PROCESSING.update({
            "doc_id": None, "client_id": None, "file_name": None,
            "started_at": None, "stage": None,
        })


def _trigger_stage3_increment(db: Any, ai_service: Any, client_id: str) -> None:
    """单 PDF OCR 完成后, 跑一次 Stage 3 compact 把新增 chunks 抽进字典 pending.

    用 compact 模式 timeout 240s, 因为只是增量, 不需要 full prompt.
    """
    from app.services.glossary_attribute_extractor import extract_candidates
    extract_candidates(db, ai_service, client_id, compact=True,
                       timeout_seconds=240.0, max_tokens=8000)


def _worker_loop(db: Any, ai_service: Any, data_dir: Path, sleep_secs: int = 60) -> None:
    """主循环: 每 sleep_secs 秒扫一次 pending_ocr, 取一个跑.

    daemon thread 起来后跑直到进程退出.
    """
    logger.info("[internet-pdf-worker] worker daemon started · sleep_secs=%d", sleep_secs)
    while True:
        try:
            pending = _find_next_pending_pdf(db)
            if pending:
                logger.info(
                    "[internet-pdf-worker] picked PDF · client=%s · file=%s",
                    pending["client_id"], pending["file_name"],
                )
                _process_one_pdf(db, ai_service, data_dir, pending)
                # 处理完一个继续找下一个, 不睡 (闲时尽快消化队列)
                continue
            # 没有待处理 PDF, 睡 sleep_secs 后再扫
            time.sleep(sleep_secs)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[internet-pdf-worker] loop iteration failed: %s", exc)
            time.sleep(sleep_secs)


def start_worker_if_not_running(db: Any, ai_service: Any, data_dir: Path) -> bool:
    """uvicorn startup hook 调用: 启动 worker daemon (单例, 不重复启).

    返回 True 表示这次启动了, False 表示已在跑.
    """
    global _WORKER_STARTED
    with _WORKER_LOCK:
        if _WORKER_STARTED:
            return False
        thread = threading.Thread(
            target=_worker_loop,
            args=(db, ai_service, data_dir),
            kwargs={"sleep_secs": 60},
            daemon=True,
            name="internet_pdf_ocr_worker",
        )
        thread.start()
        _WORKER_STARTED = True
        logger.info("[internet-pdf-worker] daemon thread spawned")
        return True
