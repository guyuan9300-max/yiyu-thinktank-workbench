"""文档导入后的本地推理任务派发（Phase 2 + W3a）。

`route_document_for_local_inference(db, v2_document_id)` 在导入时入队两类任务：

- **深读（所有 kind 统一）**：每篇文档入 `document_card_generation`（+ 可选 path_optimization）。
  这是深读地基的"导入即触发"入口——新客户、用户未来上传的资料由构造自动获得深读，
  不靠人手动补。受 settings.local_model_optimization 的 autoEnqueue* 开关 gate。
- **视觉 OCR（kind 专属）**：pptx 每 slide 一条 visual_ocr task（其他 kind 暂 no-op，等 runner 扩展）。

由 `knowledge_v2.ingest_document_knowledge` 末尾调用。**不阻塞主流程**——
任何异常都吞掉只打日志，不让一个 router 故障拖累整个导入。
**只入队，不在此跑**：实际消化由 deep-read-worker 线程按 enabled/窗口/governor 节流。

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


def _enqueue_deep_read(db: Database, doc_row: dict) -> int:
    """W3a · 导入即入队深读任务（客户无关，覆盖所有 kind）。

    每篇导入文档都入 `document_card_generation`（深读地基所需）+ 可选 path_optimization，
    使新客户/用户未来上传的资料由构造自动获得深读，不靠人手动补。
    受 `settings.local_model_optimization` gate：autoEnqueueDocumentCards /
    autoEnqueuePathOptimization 关时不入对应类型。只入队，不在此跑——实际消化由
    deep-read-worker 线程按 enabled/窗口/governor 节流（默认 enabled=False，零成本）。
    幂等由 enqueue 函数的 INSERT OR IGNORE + input_hash 保证。
    """
    from app.services.local_model_optimizer import (  # noqa: PLC0415
        TASK_TYPE_DOCUMENT_CARD,
        TASK_TYPE_PATH_OPTIMIZATION,
        enqueue_local_model_optimization_tasks,
        get_local_model_optimization_settings,
    )

    settings = get_local_model_optimization_settings(db)
    task_types: list[str] = []
    if bool(settings.get("autoEnqueueDocumentCards", True)):
        task_types.append(TASK_TYPE_DOCUMENT_CARD)
    if bool(settings.get("autoEnqueuePathOptimization", False)):
        task_types.append(TASK_TYPE_PATH_OPTIMIZATION)
    if not task_types:
        return 0

    knowledge_doc_id = _resolve_knowledge_document_id(db, doc_row)
    if not knowledge_doc_id:
        return 0

    result = enqueue_local_model_optimization_tasks(
        db,
        document_ids=[knowledge_doc_id],
        task_types=task_types,
    )
    return int(result.get("created", 0) or 0)


# 路由表：文档 kind → 视觉 OCR 派发函数（仅 pptx 需要 per-slide OCR）。
# 注意：document_card 深读对所有 kind 统一入队，不走此表（见 _enqueue_deep_read）。
_ROUTERS = {
    "pptx": _route_pptx,
}


def route_document_for_local_inference(
    db: Database,
    v2_document_id: str,
) -> dict[str, int]:
    """文档导入后调用。统一入深读任务（所有 kind）+ kind 专属 OCR（pptx）。

    Returns:
        dict 含 enqueued 总数 + documentCard / visualOcr 细分，给日志/前端用。
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

    doc_dict = dict(row)
    kind = str(row["kind"] or "").lower()

    # W3a：所有 kind 统一入深读（document_card）。任何异常吞掉，不拖累导入主流程。
    card_enqueued = 0
    try:
        card_enqueued = _enqueue_deep_read(db, doc_dict)
    except Exception as exc:  # noqa: BLE001
        logger.warning("router: 深读入队失败 doc=%s: %s", v2_document_id, exc)

    # kind 专属：pptx 每 slide 一条 visual_ocr（其他 kind 暂 no-op，等 runner 扩展）
    ocr_enqueued = 0
    router_fn = _ROUTERS.get(kind)
    if router_fn is not None:
        source_path = _resolve_source_path(doc_dict)
        if source_path is not None:
            try:
                ocr_enqueued = router_fn(db, doc_dict, source_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("router: %s OCR 入队失败 doc=%s: %s", kind, v2_document_id, exc)

    # 深读入队走 db.execute（已逐条在锁内提交）。pptx 的 _enqueue_visual_ocr 走 db.conn.execute
    # 原始写（未提交），仅当它真入了队才需在此 commit；加锁避免与其它共享 conn 的后台线程
    # （knowledge/analysis/deep-read worker）的提交竞争（HIGH 修复：原来裸 db.conn.commit() 绕过锁）。
    if ocr_enqueued:
        with db._lock:
            db.conn.commit()
    return {
        "enqueued": card_enqueued + ocr_enqueued,
        "documentCard": card_enqueued,
        "visualOcr": ocr_enqueued,
        "kind": kind,
    }


__all__ = ["route_document_for_local_inference"]
