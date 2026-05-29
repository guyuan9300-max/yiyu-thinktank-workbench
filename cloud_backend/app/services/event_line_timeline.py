from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


def _load_backend_builder():
    repo_root = Path(__file__).resolve().parents[3]
    backend_path = repo_root / "backend" / "app" / "services" / "event_line_timeline.py"
    if not backend_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("_shared_event_line_timeline", backend_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "build_event_line_timeline_nodes", None)


_backend_builder = _load_backend_builder()


def _text(value: Any) -> str:
    return " ".join(str(value or "").replace("#", " ").split()).strip()


def _attachment_title(attachment: dict[str, Any]) -> str:
    return _text(attachment.get("title") or attachment.get("fileName") or attachment.get("name") or "附件")


def _normalize_attachment(attachment: dict[str, Any]) -> dict[str, Any]:
    title = _attachment_title(attachment)
    download_url = _text(attachment.get("downloadUrl"))
    return {
        **attachment,
        "title": title,
        "fileName": _text(attachment.get("fileName") or title),
        "downloadUrl": download_url,
        "openUrl": _text(attachment.get("openUrl") or download_url),
        "parseStatus": _text(attachment.get("parseStatus")) or ("ready" if _text(attachment.get("documentId")) and _text(attachment.get("parsedPreview")) else "missing_document"),
        "parsedPreview": _text(attachment.get("parsedPreview")),
    }


def _build_node(
    *,
    node_id: str,
    kind: str,
    title: str,
    time: str,
    summary: str,
    attachments: list[dict[str, Any]] | None = None,
    source_task_ids: list[str] | None = None,
    source_activity_ids: list[str] | None = None,
    tags: list[str] | None = None,
    warnings: list[str] | None = None,
    actor_name: str | None = None,
    owner_name: str | None = None,
) -> dict[str, Any]:
    normalized_attachments = [_normalize_attachment(item) for item in attachments or []]
    return {
        "id": node_id,
        "kind": kind,
        "title": title,
        "time": time,
        "timeRange": {"start": time, "end": time} if time else {},
        "summary": summary,
        "sourceTaskIds": source_task_ids or [],
        "sourceTaskId": (source_task_ids or [""])[0],
        "sourceActivityIds": source_activity_ids or [],
        "attachments": normalized_attachments,
        "materialCount": len(normalized_attachments),
        "includeInReport": kind not in {"needs_review", "system_trace"},
        "evidenceSummary": " ".join(_text(item.get("parsedPreview")) for item in normalized_attachments if _text(item.get("parsedPreview")))[:360],
        "warnings": warnings or [],
        "tags": tags or [],
        "actorName": actor_name,
        "ownerName": owner_name,
    }


def build_event_line_timeline_nodes(
    *,
    event_line: dict[str, Any],
    tasks: list[dict[str, Any]],
    activities: list[dict[str, Any]],
    attachments: list[dict[str, Any]],
    snapshot_at: str,
) -> list[dict[str, Any]]:
    if _backend_builder is not None:
        return _backend_builder(
            event_line=event_line,
            tasks=tasks,
            activities=activities,
            attachments=attachments,
            snapshot_at=snapshot_at,
        )

    event_line_id = _text(event_line.get("id"))
    owner_name = _text(event_line.get("ownerName")) or None
    nodes = [
        _build_node(
            node_id=f"event-line:{event_line_id}:start",
            kind="project_start",
            title="项目启动",
            time=_text(event_line.get("createdAt") or snapshot_at),
            summary=_text(event_line.get("summary") or event_line.get("intent")) or f"{_text(event_line.get('name')) or '这条事件线'}已建立，后续材料会继续汇入这条线。",
            tags=["项目启动", "事件线说明"],
            owner_name=owner_name,
        )
    ]

    attachments_by_task: dict[str, list[dict[str, Any]]] = {}
    loose_attachments: list[dict[str, Any]] = []
    for attachment in attachments:
        task_id = _text(attachment.get("taskId"))
        if task_id:
            attachments_by_task.setdefault(task_id, []).append(attachment)
        else:
            loose_attachments.append(attachment)

    for task in tasks:
        task_id = _text(task.get("id"))
        title = _text(task.get("title"))
        if not task_id or not title:
            continue
        task_attachments = attachments_by_task.get(task_id, [])
        nodes.append(
            _build_node(
                node_id=f"task:{task_id}:continuing",
                kind="continuing_task",
                title=title,
                time=_text(task.get("updatedAt") or task.get("createdAt") or snapshot_at),
                summary=_text(task.get("desc") or task.get("description")) or f"{title}正在持续推进，相关附件可在节点内打开或下载。",
                attachments=task_attachments,
                source_task_ids=[task_id],
                tags=["任务节点", f"附件 {len(task_attachments)}" if task_attachments else ""],
                actor_name=_text(task.get("creatorName")) or None,
                owner_name=_text(task.get("ownerName")) or owner_name,
            )
        )

    if loose_attachments:
        nodes.append(
            _build_node(
                node_id=f"event-line:{event_line_id}:needs-review-material",
                kind="needs_review",
                title="材料主题待确认",
                time=_text(loose_attachments[-1].get("createdAt") or snapshot_at),
                summary=f"有 {len(loose_attachments)} 个附件暂时缺少清晰任务或活动上下文，先保留为待确认材料。",
                attachments=loose_attachments,
                tags=["待确认", f"附件 {len(loose_attachments)}"],
                warnings=["缺少任务或活动上下文。"],
                owner_name=owner_name,
            )
        )

    return sorted(nodes, key=lambda node: (_text(node.get("time")), _text(node.get("id"))))
