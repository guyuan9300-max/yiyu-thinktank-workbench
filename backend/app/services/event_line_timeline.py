from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any


TimelineNodeKind = str


_MEETING_RE = re.compile(r"(会议纪要|沟通会|会议|纪要|复盘)")
_ADMIN_RE = re.compile(r"(报销|票据|发票|收据|凭证|通行费|捐赠票据|行政)")
_TEST_RE = re.compile(r"(^|[/\\])(test[_\-.]|smoke[_\-.])|测试|test_attachment|smoke_att", re.I)
_SYSTEM_RE = re.compile(r"(创建事件线|更新事件线|结束事件线|上传附件|新增任务|创建任务|更新任务|附件已归档|已归档到任务附件)")


def _text(value: Any) -> str:
    return " ".join(str(value or "").replace("#", " ").split()).strip()


def _truncate(value: Any, limit: int = 260) -> str:
    normalized = _text(value)
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: max(0, limit - 1)].rstrip()}…"


def _metadata(item: dict[str, Any]) -> dict[str, Any]:
    value = item.get("metadata")
    return value if isinstance(value, dict) else {}


def _activity_title(activity: dict[str, Any]) -> str:
    return _text(activity.get("editedTitle") or activity.get("title"))


def _activity_summary(activity: dict[str, Any]) -> str:
    return _text(activity.get("editedSummary") or activity.get("summary"))


def _activity_time(activity: dict[str, Any]) -> str:
    return _text(activity.get("happenedAt") or activity.get("createdAt"))


def _task_title(task: dict[str, Any]) -> str:
    return _text(task.get("title"))


def _task_desc(task: dict[str, Any]) -> str:
    return _text(task.get("desc") or task.get("description") or task.get("note"))


def _attachment_title(attachment: dict[str, Any]) -> str:
    return _text(attachment.get("title") or attachment.get("fileName") or attachment.get("name"))


def _attachment_preview(attachment: dict[str, Any]) -> str:
    return _text(attachment.get("parsedPreview") or attachment.get("summary") or attachment.get("description"))


def _attachment_time(attachment: dict[str, Any]) -> str:
    return _text(attachment.get("createdAt") or attachment.get("uploadedAt"))


def _attachment_text(attachment: dict[str, Any]) -> str:
    return f"{_attachment_title(attachment)} {_attachment_preview(attachment)}"


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for item in items:
        normalized = _text(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        results.append(normalized)
    return results


def _task_id_for_activity(activity: dict[str, Any]) -> str:
    metadata = _metadata(activity)
    if str(activity.get("sourceType") or "") == "task_activity" and _text(activity.get("sourceId")):
        return _text(activity.get("sourceId"))
    return _text(metadata.get("taskId") or metadata.get("task_id"))


def _attachment_id_for_activity(activity: dict[str, Any]) -> str:
    metadata = _metadata(activity)
    if str(activity.get("sourceType") or "") == "attachment" and _text(activity.get("sourceId")):
        return _text(activity.get("sourceId"))
    return _text(metadata.get("attachmentId") or metadata.get("attachment_id"))


def _is_create_activity(activity: dict[str, Any]) -> bool:
    metadata = _metadata(activity)
    event_type = _text(metadata.get("eventType") or metadata.get("event_type")).lower()
    text = f"{_activity_title(activity)} {_activity_summary(activity)}"
    return event_type in {"event_line_created", "line_created"} or "创建事件线" in text


def _is_system_activity(activity: dict[str, Any]) -> bool:
    if _is_create_activity(activity):
        return True
    metadata = _metadata(activity)
    event_type = _text(metadata.get("eventType") or metadata.get("event_type")).lower()
    text = f"{_activity_title(activity)} {_activity_summary(activity)}"
    return event_type in {"updated", "attachment_uploaded", "event_line_updated"} or bool(_SYSTEM_RE.search(text))


def _is_test_attachment(attachment: dict[str, Any]) -> bool:
    name = _attachment_title(attachment)
    return bool(_TEST_RE.search(name))


def _is_image_attachment(attachment: dict[str, Any]) -> bool:
    mime = _text(attachment.get("mimeType") or attachment.get("mime_type")).lower()
    name = _attachment_title(attachment).lower()
    return mime.startswith("image/") or name.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic"))


def _has_meeting_signal(text: str) -> bool:
    return bool(_MEETING_RE.search(text))


def _has_admin_signal(text: str) -> bool:
    return bool(_ADMIN_RE.search(text))


def _topic_from_text(text: str) -> tuple[str, str] | None:
    normalized = _text(text)
    explicit_topics = [
        ("teacher_enablement", "教师赋能", ("教师赋能", "教师项目", "带领者")),
        ("xinsheng", "心盛计划", ("心盛计划", "关怀员", "青年社群")),
        ("fanxing", "繁星计划", ("繁星计划", "资源库", "行动营", "个人IP", "个人 IP")),
        ("mind_magic", "心灵魔法学院", ("心灵魔法学院", "心灵魔法")),
    ]
    for key, label, keywords in explicit_topics:
        if any(keyword in normalized for keyword in keywords):
            return key, label

    match = re.search(r"「([^」]{2,18})」", normalized)
    if match:
        label = _text(match.group(1))
        return f"topic:{label}", label

    match = re.search(r"[-_—]([^；，,。]{2,18}?)(?:一季度|Q1|沟通|会议|纪要|复盘)", normalized, re.I)
    if match:
        label = _text(match.group(1))
        return f"topic:{label}", label

    return None


def _topic_review_title(label: str, text: str) -> str:
    if label == "教师赋能":
        return "教师赋能项目进入设计校准"
    if label == "心盛计划":
        return "心盛计划从活动运营转向数据与品牌协同"
    if label == "繁星计划":
        return "繁星计划进入战略方向重定"
    if "战略" in text:
        return f"{label}进入战略复盘"
    if "设计" in text or "方案" in text:
        return f"{label}进入方案校准"
    return f"{label}项目复盘"


def _topic_review_summary(label: str, evidence: str) -> str:
    normalized = _text(evidence)
    if not normalized:
        return f"这一节点围绕{label}形成阶段复盘，后续需要继续补充会议纪要或任务说明作为依据。"

    sentences = re.split(r"(?<=[。！？!?])", normalized)
    candidates = [
        _text(sentence)
        for sentence in sentences
        if any(keyword in sentence for keyword in (label, "项目", "需要", "当前", "后续", "形成", "问题", "卡点", "推进", "设计", "数据", "品牌", "战略"))
    ]
    picked = _dedupe(candidates)[:3]
    if picked:
        return _truncate(" ".join(picked), 320)
    return _truncate(normalized, 320)


def _latest_time(values: list[str], fallback: str = "") -> str:
    normalized = sorted([_text(value) for value in values if _text(value)])
    return normalized[-1] if normalized else fallback


def _earliest_time(values: list[str], fallback: str = "") -> str:
    normalized = sorted([_text(value) for value in values if _text(value)])
    return normalized[0] if normalized else fallback


def _attachment_warnings(attachments: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    by_name_size: dict[tuple[str, int], int] = defaultdict(int)
    by_name_sizes: dict[str, set[int]] = defaultdict(set)
    missing_document = False
    pending_parse = False
    for attachment in attachments:
        name = _attachment_title(attachment)
        size = int(attachment.get("sizeBytes") or attachment.get("size_bytes") or 0)
        if name:
            by_name_size[(name, size)] += 1
            by_name_sizes[name].add(size)
        if not _text(attachment.get("documentId")):
            missing_document = True
        elif _text(attachment.get("parseStatus")) and _text(attachment.get("parseStatus")) != "ready":
            pending_parse = True
    duplicate_names = [name for (name, _size), count in by_name_size.items() if count > 1]
    version_names = [name for name, sizes in by_name_sizes.items() if len(sizes) > 1]
    if duplicate_names:
        warnings.append(f"存在重复附件：{duplicate_names[0]} 出现 {by_name_size[(duplicate_names[0], next(iter(by_name_sizes[duplicate_names[0]])))]} 次。")
    if version_names:
        warnings.append(f"存在多版本附件：{version_names[0]}。")
    if missing_document:
        warnings.append("部分附件尚未接入数据中心 documentId。")
    if pending_parse:
        warnings.append("部分附件仍待数据中心解析完成。")
    return warnings


def _build_node(
    *,
    node_id: str,
    kind: TimelineNodeKind,
    title: str,
    time: str,
    summary: str,
    source_task_ids: list[str] | None = None,
    source_activity_ids: list[str] | None = None,
    attachments: list[dict[str, Any]] | None = None,
    evidence_summary: str = "",
    warnings: list[str] | None = None,
    tags: list[str] | None = None,
    actor_name: str | None = None,
    owner_name: str | None = None,
) -> dict[str, Any]:
    attachment_list = attachments or []
    task_ids = _dedupe(source_task_ids or [])
    activity_ids = _dedupe(source_activity_ids or [])
    return {
        "id": node_id,
        "kind": kind,
        "title": title,
        "time": time,
        "summary": _truncate(summary, 420),
        "sourceTaskIds": task_ids,
        "sourceTaskId": task_ids[0] if task_ids else "",
        "sourceActivityIds": activity_ids,
        "attachments": attachment_list,
        "evidenceSummary": _truncate(evidence_summary, 360),
        "warnings": _dedupe(warnings or []),
        "tags": _dedupe(tags or []),
        "actorName": actor_name,
        "ownerName": owner_name,
    }


def _continuing_task_title(task: dict[str, Any]) -> str:
    title = _task_title(task)
    context = f"{title} {_task_desc(task)}"
    if "带领者" in context and ("培训" in context or "演练" in context or "实践" in context):
        return "带领者培训与实践继续推进"
    if len(title) > 28:
        return f"{title[:27].rstrip()}…"
    return title or "持续推进任务"


def _material_intake_title(evidence_text: str, topic_labels: list[str]) -> str:
    if re.search(r"(Q1|一季度)", evidence_text, re.I) and len(topic_labels) >= 2:
        return "Q1项目复盘材料集中入库"
    if len(topic_labels) >= 2:
        return "项目复盘材料集中入库"
    if topic_labels:
        return f"{topic_labels[0]}材料集中入库"
    return "关键材料集中入库"


def _admin_archive_title(event_line: dict[str, Any], task: dict[str, Any] | None) -> str:
    task_title = _task_title(task or {})
    if task_title and "报销" in task_title:
        return f"{task_title}材料归档"
    client = _text(event_line.get("primaryClientName") or event_line.get("name")).replace("基金会", "")
    if client:
        return f"{client}行政材料归档"
    return "行政材料归档"


def build_event_line_timeline_nodes(
    *,
    event_line: dict[str, Any],
    tasks: list[dict[str, Any]],
    activities: list[dict[str, Any]],
    attachments: list[dict[str, Any]],
    snapshot_at: str,
) -> list[dict[str, Any]]:
    """Build customer-readable event-line milestone nodes from a report snapshot.

    The generator intentionally uses rules and parsed previews only. It should be
    deterministic, cheap to run, and safe as both API payload and Word-export input.
    """

    task_by_id = {_text(task.get("id")): task for task in tasks if _text(task.get("id"))}
    activity_ids_by_task: dict[str, list[str]] = defaultdict(list)
    for activity in activities:
        task_id = _task_id_for_activity(activity)
        if task_id:
            activity_ids_by_task[task_id].append(_text(activity.get("id")))

    attachments_by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    loose_attachments: list[dict[str, Any]] = []
    for attachment in attachments:
        task_id = _text(attachment.get("taskId"))
        if task_id:
            attachments_by_task[task_id].append(attachment)
        else:
            loose_attachments.append(attachment)

    nodes: list[dict[str, Any]] = []
    create_activity = next((activity for activity in activities if _is_create_activity(activity)), None)
    start_summary = _text(event_line.get("intent") or event_line.get("summary"))
    if not start_summary:
        start_summary = f"{_text(event_line.get('name')) or '这条事件线'}被建立为一条持续推进的项目线，用来承接后续判断、材料和动作。"
    else:
        start_summary = f"{_text(event_line.get('name')) or '这条事件线'}被建立为一条持续推进的项目线，{start_summary}"
    nodes.append(
        _build_node(
            node_id=f"event-line:{_text(event_line.get('id'))}:start",
            kind="project_start",
            title="项目启动",
            time=_activity_time(create_activity) if create_activity else _text(event_line.get("createdAt") or snapshot_at),
            summary=start_summary,
            source_activity_ids=[_text(create_activity.get("id"))] if create_activity else [],
            tags=["项目启动", "事件线说明"],
            actor_name=_text(create_activity.get("actorName")) if create_activity else None,
            owner_name=_text(event_line.get("ownerName")) or None,
        )
    )

    usable_attachments = [attachment for attachment in attachments if not _is_test_attachment(attachment)]
    test_attachments = [attachment for attachment in attachments if _is_test_attachment(attachment)]
    meeting_attachments = [
        attachment
        for attachment in usable_attachments
        if _has_meeting_signal(_attachment_text(attachment))
    ]

    topic_groups: dict[str, dict[str, Any]] = {}
    unclassified_meeting: list[dict[str, Any]] = []
    for attachment in meeting_attachments:
        topic = _topic_from_text(_attachment_text(attachment))
        if not topic:
            unclassified_meeting.append(attachment)
            continue
        key, label = topic
        group = topic_groups.setdefault(key, {"label": label, "attachments": []})
        group["attachments"].append(attachment)

    if meeting_attachments:
        labels = [str(group["label"]) for group in topic_groups.values()]
        evidence_text = " ".join(_attachment_text(attachment) for attachment in meeting_attachments)
        summary_topics = "、".join(_dedupe(labels)) or "相关会议纪要"
        nodes.append(
            _build_node(
                node_id=f"event-line:{_text(event_line.get('id'))}:material-intake",
                kind="material_intake",
                title=_material_intake_title(evidence_text, labels),
                time=_earliest_time([_attachment_time(attachment) for attachment in meeting_attachments], snapshot_at),
                summary=f"这一阶段集中归集了{summary_topics}等复盘材料，使后续项目判断可以回到会议纪要和解析摘要里核对。",
                attachments=meeting_attachments,
                evidence_summary=_truncate(" ".join(_dedupe([_attachment_preview(attachment) for attachment in meeting_attachments])[:3]), 360),
                warnings=_attachment_warnings(meeting_attachments),
                tags=["材料入库", "会议纪要", f"附件 {len(meeting_attachments)}"],
                actor_name=meeting_attachments[-1].get("actorName") if meeting_attachments else None,
                owner_name=_text(event_line.get("ownerName")) or None,
            )
        )

    for key, group in topic_groups.items():
        group_attachments = list(group["attachments"])
        label = str(group["label"])
        evidence = " ".join(_dedupe([_attachment_preview(attachment) or _attachment_title(attachment) for attachment in group_attachments]))
        nodes.append(
            _build_node(
                node_id=f"event-line:{_text(event_line.get('id'))}:review:{key}",
                kind="project_review",
                title=_topic_review_title(label, evidence),
                time=_earliest_time([_attachment_time(attachment) for attachment in group_attachments], snapshot_at),
                summary=_topic_review_summary(label, evidence),
                attachments=group_attachments,
                evidence_summary=_truncate(evidence, 360),
                warnings=_attachment_warnings(group_attachments),
                tags=["项目复盘", label, f"附件 {len(group_attachments)}"],
                actor_name=group_attachments[-1].get("actorName") if group_attachments else None,
                owner_name=_text(event_line.get("ownerName")) or None,
            )
        )

    admin_task_ids: set[str] = set()
    for task_id, task in task_by_id.items():
        task_attachments = attachments_by_task.get(task_id, [])
        context = f"{_task_title(task)} {_task_desc(task)} {' '.join(_attachment_text(att) for att in task_attachments)}"
        if _has_admin_signal(context):
            admin_task_ids.add(task_id)
            nodes.append(
                _build_node(
                    node_id=f"task:{task_id}:admin-archive",
                    kind="admin_archive",
                    title=_admin_archive_title(event_line, task),
                    time=_latest_time([_attachment_time(att) for att in task_attachments] + [_text(task.get("updatedAt") or task.get("createdAt"))], snapshot_at),
                    summary=f"{_task_title(task) or '行政材料'}已完成材料归档，主要用于后续报销、结项或审计核对。{_truncate(' '.join(_dedupe([_attachment_preview(att) for att in task_attachments])[:2]), 180)}",
                    source_task_ids=[task_id],
                    source_activity_ids=activity_ids_by_task.get(task_id, []),
                    attachments=task_attachments,
                    evidence_summary=_truncate(" ".join(_dedupe([_attachment_preview(att) for att in task_attachments])[:2]), 320),
                    warnings=_attachment_warnings(task_attachments),
                    tags=["行政材料", f"附件 {len(task_attachments)}"],
                    actor_name=_text(task.get("creatorName")) or None,
                    owner_name=_text(task.get("ownerName")) or None,
                )
            )

    loose_admin = [
        attachment
        for attachment in loose_attachments
        if attachment not in meeting_attachments and _has_admin_signal(_attachment_text(attachment))
    ]
    if loose_admin:
        nodes.append(
            _build_node(
                node_id=f"event-line:{_text(event_line.get('id'))}:admin-archive",
                kind="admin_archive",
                title=_admin_archive_title(event_line, None),
                time=_latest_time([_attachment_time(attachment) for attachment in loose_admin], snapshot_at),
                summary=f"这一组材料属于行政归档，可用于后续下载、报销、结项或审计核对。",
                attachments=loose_admin,
                evidence_summary=_truncate(" ".join(_dedupe([_attachment_preview(attachment) for attachment in loose_admin])[:2]), 320),
                warnings=_attachment_warnings(loose_admin),
                tags=["行政材料", f"附件 {len(loose_admin)}"],
                owner_name=_text(event_line.get("ownerName")) or None,
            )
        )

    for task_id, task in task_by_id.items():
        if task_id in admin_task_ids:
            continue
        task_attachments = [attachment for attachment in attachments_by_task.get(task_id, []) if not _is_test_attachment(attachment)]
        if task_attachments and any(attachment in meeting_attachments for attachment in task_attachments):
            continue
        task_title = _task_title(task)
        if not task_title:
            continue
        activity_ids = activity_ids_by_task.get(task_id, [])
        # 不再过滤"无活动且无附件"的任务 —— "按任务查看" 要列出完整任务列表,
        # 即使任务还没有任何附件/活动也保留一个骨架, 让用户能看到全貌。
        summary_seed = _task_desc(task) or " ".join(
            _dedupe([
                _activity_summary(activity)
                for activity in activities
                if _text(activity.get("id")) in set(activity_ids)
            ])
        )
        nodes.append(
            _build_node(
                node_id=f"task:{task_id}:continuing",
                kind="continuing_task",
                title=_continuing_task_title(task),
                time=_latest_time([_text(task.get("updatedAt") or task.get("createdAt"))] + [_attachment_time(att) for att in task_attachments], snapshot_at),
                summary=summary_seed or f"{task_title}正在持续推进，需要继续记录关键卡点、责任人和下一步结果。",
                source_task_ids=[task_id],
                source_activity_ids=activity_ids,
                attachments=task_attachments,
                evidence_summary=_truncate(" ".join(_dedupe([_attachment_preview(att) for att in task_attachments])[:2]), 320),
                warnings=_attachment_warnings(task_attachments),
                tags=["持续推进", _text(task.get("status")) or "", f"附件 {len(task_attachments)}" if task_attachments else ""],
                actor_name=_text(task.get("creatorName")) or None,
                owner_name=_text(task.get("ownerName")) or None,
            )
        )

    if unclassified_meeting:
        nodes.append(
            _build_node(
                node_id=f"event-line:{_text(event_line.get('id'))}:needs-review-meeting",
                kind="needs_review",
                title="待确认会议材料",
                time=_latest_time([_attachment_time(attachment) for attachment in unclassified_meeting], snapshot_at),
                summary=f"有 {len(unclassified_meeting)} 份会议类材料尚缺清晰业务主题，需要补任务或活动归属后再进入主线叙事。",
                attachments=unclassified_meeting,
                evidence_summary=_truncate(" ".join(_dedupe([_attachment_preview(attachment) for attachment in unclassified_meeting])[:2]), 320),
                warnings=["缺少清晰业务主题。", *_attachment_warnings(unclassified_meeting)],
                tags=["待确认", "会议材料"],
                owner_name=_text(event_line.get("ownerName")) or None,
            )
        )

    if test_attachments:
        filenames = "、".join(_attachment_title(attachment) for attachment in test_attachments[:5])
        nodes.append(
            _build_node(
                node_id=f"event-line:{_text(event_line.get('id'))}:needs-review-test",
                kind="needs_review",
                title="待确认测试材料",
                time=_latest_time([_attachment_time(attachment) for attachment in test_attachments], snapshot_at),
                summary=f"疑似测试材料包括：{filenames}。这些附件暂不进入主线判断。",
                attachments=test_attachments,
                warnings=["含疑似测试素材。"],
                tags=["待确认", f"附件 {len(test_attachments)}"],
                owner_name=_text(event_line.get("ownerName")) or None,
            )
        )

    system_activities = [
        activity
        for activity in activities
        if _is_system_activity(activity) and not _is_create_activity(activity)
    ]
    if system_activities:
        nodes.append(
            _build_node(
                node_id=f"event-line:{_text(event_line.get('id'))}:system-trace",
                kind="system_trace",
                title="系统操作记录",
                time=_latest_time([_activity_time(activity) for activity in system_activities], snapshot_at),
                summary=f"保留 {len(system_activities)} 条创建、上传、更新等审计流水，默认折叠展示。",
                source_activity_ids=[_text(activity.get("id")) for activity in system_activities],
                tags=["系统痕迹", f"记录 {len(system_activities)}"],
            )
        )

    kind_rank = {
        "project_start": 0,
        "material_intake": 1,
        "project_review": 2,
        "continuing_task": 3,
        "admin_archive": 4,
        "needs_review": 8,
        "system_trace": 9,
    }
    return sorted(nodes, key=lambda node: (_text(node.get("time")), kind_rank.get(str(node.get("kind")), 5), _text(node.get("id"))))
