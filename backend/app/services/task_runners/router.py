"""文档导入后的本地推理任务派发（Phase 2）。

`route_document_for_local_inference(db, v2_document_id)` 根据文档 kind 决定
要入队哪些本地推理任务。当前实现：

- pptx：每 slide 一条 visual_ocr task（Phase 1 已支持）
- pdf / xlsx 内嵌图 / docx 内嵌图 / 图片文件：留 hook 但暂不入队（runner Phase 1 只支持 pptx_slide_images，等扩展 source_kind 后开）

由 `knowledge_v2.ingest_document_knowledge` 末尾调用。**不阻塞主流程**——
任何异常都吞掉只打日志，不让一个 router 故障拖累整个导入。

幂等：UNIQUE(task_type, knowledge_document_id, input_hash) 保证多次调用不重复入队。
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from app.db import Database
from app.services.local_model_optimizer import TASK_TYPE_VISUAL_OCR

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _input_hash(task_type: str, v2_document_id: str, region_key: str) -> str:
    payload = f"{task_type}|{v2_document_id}|{region_key}"
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def _resolve_source_path(row: dict) -> Path | None:
    """从 v2_documents 行里挑一个磁盘上真实存在的路径。"""
    import os

    for col in ("managed_path", "original_path"):
        candidate = str(row.get(col) or "")
        if candidate and os.path.exists(candidate):
            return Path(candidate)
    return None


def _resolve_knowledge_document_id(db: Database, v2_document_row: dict) -> str:
    """从 v2_documents 行算出 knowledge_documents.id（FK 要的就是这个）。

    数据约定：knowledge_documents.id = 'kd_' + v2_documents.document_id
    若 knowledge_documents 行不存在，返回空串（调用方应跳过入队）。
    """
    doc_inner_id = str(v2_document_row.get("document_id") or "")
    if not doc_inner_id:
        return ""
    candidate = f"kd_{doc_inner_id}"
    row = db.fetchone("SELECT id FROM knowledge_documents WHERE id = ?", (candidate,))
    return str(row["id"]) if row else ""


def _enqueue_visual_ocr(
    db: Database,
    *,
    v2_document_id: str,
    knowledge_document_id: str,
    client_id: str,
    source_kind: str,
    source_path: str,
    region: dict,
    title: str,
    priority: int = 200,
) -> bool:
    """单条入队。UNIQUE 冲突视为已入过，返回 False。"""
    region_key = json.dumps(region, sort_keys=True, ensure_ascii=False)
    input_hash = _input_hash(TASK_TYPE_VISUAL_OCR, v2_document_id, region_key)
    payload = {
        "source_kind": source_kind,
        "source_path": source_path,
        "source_v2_document_id": v2_document_id,
        "source_client_id": client_id,
        "region": region,
        "title": title,
    }
    now = _now_iso()
    task_id = _new_id("lmt")
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
                task_id, TASK_TYPE_VISUAL_OCR, client_id, knowledge_document_id,
                "local_vision_ocr", priority, input_hash,
                json.dumps(payload, ensure_ascii=False), now, now,
            ),
        )
        return True
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if "unique" in msg or "constraint" in msg:
            return False
        logger.warning("enqueue visual_ocr failed (doc=%s): %s", v2_document_id, exc)
        return False


def _route_pptx(db: Database, doc_row: dict, source_path: Path) -> int:
    """pptx：每 slide 入一条 visual_ocr task。返回入队条数。"""
    knowledge_doc_id = _resolve_knowledge_document_id(db, doc_row)
    if not knowledge_doc_id:
        logger.info(
            "router: skip pptx %s（找不到对应的 knowledge_documents 行）",
            doc_row.get("id"),
        )
        return 0

    try:
        from pptx import Presentation  # noqa: PLC0415

        prs = Presentation(str(source_path))
        n_slides = len(list(prs.slides))
    except Exception as exc:  # noqa: BLE001
        logger.warning("router: 读 pptx 失败 %s: %s", source_path.name, exc)
        return 0

    enqueued = 0
    for slide_no in range(1, n_slides + 1):
        if _enqueue_visual_ocr(
            db,
            v2_document_id=str(doc_row["id"]),
            knowledge_document_id=knowledge_doc_id,
            client_id=str(doc_row.get("client_id") or ""),
            source_kind="pptx_slide_images",
            source_path=str(source_path),
            region={"slide_no": slide_no},
            title=str(doc_row.get("file_name") or ""),
        ):
            enqueued += 1
    return enqueued


# 路由表：文档 kind → 派发函数。其他 kind 暂时 no-op（等 Phase 5 runner 扩展）
_ROUTERS = {
    "pptx": _route_pptx,
}


def route_document_for_local_inference(
    db: Database,
    v2_document_id: str,
) -> dict[str, int]:
    """文档导入后调用。根据 kind 决定派发哪些本地推理任务。

    Returns:
        dict 含 enqueued_count + per_runner 细分，给日志/前端用。
    """
    if not v2_document_id:
        return {"enqueued": 0, "skipped_reason": "no v2_document_id"}

    row = db.fetchone(
        """
        SELECT id, client_id, document_id, kind, file_name, managed_path, original_path
        FROM v2_documents WHERE id = ?
        """,
        (v2_document_id,),
    )
    if not row:
        return {"enqueued": 0, "skipped_reason": "v2_document not found"}

    kind = str(row["kind"] or "").lower()
    router_fn = _ROUTERS.get(kind)
    if router_fn is None:
        return {"enqueued": 0, "skipped_reason": f"no router for kind={kind}"}

    source_path = _resolve_source_path(dict(row))
    if source_path is None:
        return {"enqueued": 0, "skipped_reason": "source file not on disk"}

    enqueued = router_fn(db, dict(row), source_path)
    db.conn.commit()
    return {"enqueued": enqueued, "kind": kind, "source": str(source_path)}


__all__ = ["route_document_for_local_inference"]
