from __future__ import annotations

from app.models import (
    AnswerMaterialRecord,
    DataCenterPrepResultRecord,
    DataCenterPrepSectionRecord,
    DataCenterRequestRecord,
    PageContextPackRecord,
    PrepPackMaterialRecord,
    RouteDecisionRecord,
)


def _material_record(source_type: str, source_id: str, title: str, summary: str, authority: str = "") -> PrepPackMaterialRecord:
    return PrepPackMaterialRecord(
        sourceType=source_type,
        sourceId=source_id,
        title=title,
        summary=summary,
        authorityLevel=authority,
    )


def build_data_center_prep_result(
    *,
    request: DataCenterRequestRecord,
    page_context: PageContextPackRecord,
    route_decision: RouteDecisionRecord,
    answer_material: AnswerMaterialRecord | None = None,
) -> DataCenterPrepResultRecord:
    scope = request.scope

    known_facts: list[str] = []
    key_risks: list[str] = []
    open_questions: list[str] = []
    agenda: list[str] = []
    next_actions: list[str] = []
    boundary_notes: list[str] = list(page_context.boundaryNotes[:6])
    materials: list[PrepPackMaterialRecord] = []

    if scope.scopeType == "task" or scope.page in {"task_detail", "task_ai"}:
        prep_type = "task"
        title = f"任务准备：{scope.scopeId}"
        task = page_context.relatedTasks[0] if page_context.relatedTasks else {}
        if task:
            known_facts.append(f"任务标题：{task.get('title') or ''}")
            known_facts.append(f"任务状态：{task.get('status') or ''}")
            if task.get("clientId"):
                known_facts.append(f"关联客户：{task.get('clientId')}")
            if task.get("eventLineId"):
                known_facts.append(f"关联事件线：{task.get('eventLineId')}")
        known_facts.extend([fact for fact in page_context.memoryFacts[:6] if fact])
        for item in page_context.conflicts[:5]:
            summary = str(item.get("summary") or item.get("title") or "").strip()
            if summary:
                key_risks.append(summary)
        key_risks.extend([item for item in page_context.missingContext[:4] if item])
        for item in page_context.openQuestions[:6]:
            text = str(item.get("question") or item.get("summary") or "").strip()
            if text:
                open_questions.append(text)
        if answer_material is not None:
            next_actions.extend(answer_material.nextActions[:6])
        for task_item in page_context.relatedTasks[:5]:
            summary = str(task_item.get("desc") or task_item.get("status") or "").strip()
            materials.append(
                _material_record(
                    "task",
                    str(task_item.get("id") or ""),
                    str(task_item.get("title") or "任务"),
                    summary,
                    "candidate" if page_context.candidateJudgments else "informational",
                )
            )
    elif scope.scopeType == "meeting" or scope.page == "meeting_detail":
        prep_type = "meeting"
        title = f"会议准备：{scope.scopeId}"
        context_pack = page_context.contextPack if isinstance(page_context.contextPack, dict) else {}
        meeting_title = str(context_pack.get("title") or scope.scopeId)
        objective = f"围绕“{meeting_title}”组织会议目标、关键判断与行动安排。"
        known_facts.append(f"会议：{meeting_title}")
        if context_pack.get("scheduledAt"):
            known_facts.append(f"计划时间：{context_pack.get('scheduledAt')}")
        for item in page_context.openQuestions[:8]:
            text = str(item.get("question") or item.get("summary") or "").strip()
            if text:
                open_questions.append(text)
        for item in page_context.conflicts[:5]:
            text = str(item.get("summary") or item.get("title") or "").strip()
            if text:
                key_risks.append(text)
        agenda.extend(open_questions[:4])
        agenda.extend([f"候选判断复核：{str(item.get('summary') or item.get('topic') or '').strip()}" for item in page_context.candidateJudgments[:3] if str(item.get('summary') or item.get('topic') or '').strip()])
        for meeting in page_context.relatedMeetings[:4]:
            materials.append(
                _material_record(
                    "meeting",
                    str(meeting.get("id") or ""),
                    str(meeting.get("title") or "会议"),
                    str(meeting.get("stage") or ""),
                    "informational",
                )
            )
        return DataCenterPrepResultRecord(
            prepType="meeting",
            title=title,
            objective=objective,
            knownFacts=list(dict.fromkeys([item for item in known_facts if item]))[:12],
            keyRisks=list(dict.fromkeys([item for item in key_risks if item]))[:10],
            openQuestions=list(dict.fromkeys([item for item in open_questions if item]))[:10],
            recommendedAgenda=list(dict.fromkeys([item for item in agenda if item]))[:10],
            nextActions=list(dict.fromkeys([item for item in (answer_material.nextActions if answer_material else []) if item]))[:8],
            materials=materials[:20],
            sections=[
                DataCenterPrepSectionRecord(title="会议目标", bullets=[objective], evidenceRefs=[]),
                DataCenterPrepSectionRecord(title="关键议题", bullets=list(dict.fromkeys([item for item in agenda if item]))[:8], evidenceRefs=[]),
                DataCenterPrepSectionRecord(title="风险与待确认", bullets=list(dict.fromkeys([*key_risks, *open_questions]))[:10], evidenceRefs=[]),
            ],
            boundaryNotes=list(dict.fromkeys([item for item in boundary_notes if item]))[:8],
        )
    else:
        prep_type = "client_conversation"
        title = f"客户会谈准备：{scope.scopeId}"
        known_facts.extend([str(item.get("summary") or item.get("topic") or "").strip() for item in page_context.officialJudgments[:4] if str(item.get("summary") or item.get("topic") or "").strip()])
        if not known_facts:
            known_facts.extend([str(item.get("summary") or item.get("topic") or "").strip() for item in page_context.candidateJudgments[:4] if str(item.get("summary") or item.get("topic") or "").strip()])
        key_risks.extend([str(item.get("summary") or item.get("title") or "").strip() for item in page_context.conflicts[:5] if str(item.get("summary") or item.get("title") or "").strip()])
        open_questions.extend([str(item.get("question") or item.get("summary") or "").strip() for item in page_context.openQuestions[:6] if str(item.get("question") or item.get("summary") or "").strip()])

    if answer_material is not None:
        next_actions.extend(answer_material.nextActions[:8])
        agenda.extend(answer_material.structuredPoints[:8])

    for item in page_context.rawEvidence[:8]:
        title_text = str(item.get("title") or "原文证据").strip() or "原文证据"
        excerpt = str(item.get("excerpt") or "").strip()
        materials.append(_material_record("raw_evidence", str(item.get("documentId") or ""), title_text, excerpt, "raw"))
    for item in page_context.relatedDocuments[:8]:
        title_text = str(item.get("title") or item.get("source_ref") or "资料").strip() or "资料"
        summary = str(item.get("summary") or item.get("short_summary") or "").strip()
        materials.append(_material_record("document", str(item.get("id") or item.get("documentId") or ""), title_text, summary, "informational"))

    objective = "围绕当前上下文组织会前/会谈准备，优先确保事实边界清晰。"
    if route_decision.intent == "task_next_action":
        objective = "围绕任务下一步形成可执行准备包，明确阻塞与负责人。"

    return DataCenterPrepResultRecord(
        prepType=prep_type,  # type: ignore[arg-type]
        title=title,
        objective=objective,
        knownFacts=list(dict.fromkeys([item for item in known_facts if item]))[:12],
        keyRisks=list(dict.fromkeys([item for item in key_risks if item]))[:10],
        openQuestions=list(dict.fromkeys([item for item in open_questions if item]))[:10],
        recommendedAgenda=list(dict.fromkeys([item for item in agenda if item]))[:10],
        nextActions=list(dict.fromkeys([item for item in next_actions if item]))[:10],
        materials=materials[:24],
        sections=[
            DataCenterPrepSectionRecord(title="已知事实", bullets=list(dict.fromkeys([item for item in known_facts if item]))[:8], evidenceRefs=[]),
            DataCenterPrepSectionRecord(title="风险与未决", bullets=list(dict.fromkeys([*key_risks, *open_questions]))[:10], evidenceRefs=[]),
            DataCenterPrepSectionRecord(title="建议动作", bullets=list(dict.fromkeys([item for item in next_actions if item]))[:8], evidenceRefs=[]),
        ],
        boundaryNotes=list(dict.fromkeys([item for item in boundary_notes if item]))[:8],
    )
