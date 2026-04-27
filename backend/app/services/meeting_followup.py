from __future__ import annotations

import hashlib

from app.models import DataCenterProposalDraftRecord, PageContextPackRecord, ProposalTargetRefRecord


def _safe_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _hash_text(value: str) -> str:
    return hashlib.sha1(str(value or "").encode("utf-8")).hexdigest()[:12]


def build_meeting_followup_proposal_drafts(
    *,
    meeting_context: PageContextPackRecord,
) -> list[DataCenterProposalDraftRecord]:
    drafts: list[DataCenterProposalDraftRecord] = []
    meeting_id = meeting_context.scopeId
    target_refs = [
        ProposalTargetRefRecord(targetType="meeting", targetId=meeting_id, label="meeting"),
    ]
    if meeting_context.clientId:
        target_refs.append(ProposalTargetRefRecord(targetType="client", targetId=meeting_context.clientId, label="client"))

    context_pack = meeting_context.contextPack if isinstance(meeting_context.contextPack, dict) else {}
    action_items = _safe_list(context_pack.get("actionItems"))
    risks = _safe_list(context_pack.get("risks"))
    ambiguities = _safe_list(context_pack.get("ambiguities"))
    open_questions = meeting_context.openQuestions if isinstance(meeting_context.openQuestions, list) else []
    candidate_judgments = meeting_context.candidateJudgments if isinstance(meeting_context.candidateJudgments, list) else []

    # 兜底：当 meeting contextPack 暂时不完整时，使用 relatedTasks/conflicts 信号补齐 follow-up 草稿。
    if not action_items and isinstance(meeting_context.relatedTasks, list):
        for task in meeting_context.relatedTasks[:8]:
            if not isinstance(task, dict):
                continue
            title = str(task.get("title") or "").strip()
            if not title:
                continue
            action_items.append(
                {
                    "id": task.get("id"),
                    "title": title,
                    "ownerName": task.get("ownerName") or task.get("owner_name"),
                    "dueDate": task.get("dueDate") or task.get("due_date"),
                }
            )
    if not risks and isinstance(meeting_context.conflicts, list):
        for conflict in meeting_context.conflicts[:8]:
            if not isinstance(conflict, dict):
                continue
            summary = str(conflict.get("summary") or conflict.get("title") or "").strip()
            if not summary:
                continue
            risks.append(
                {
                    "id": conflict.get("id"),
                    "summary": summary,
                    "severity": conflict.get("severity") or "medium",
                }
            )

    for item in action_items:
        action_id = str(item.get("id") or "").strip()
        title = str(item.get("title") or "").strip()
        owner = str(item.get("owner_name") or item.get("ownerName") or "").strip()
        due = str(item.get("due_date") or item.get("dueDate") or "").strip()
        if not title:
            continue
        summary = title
        if owner or due:
            summary = f"{title}（负责人：{owner or '待确认'}；截止：{due or '待确认'}）"
        drafts.append(
            DataCenterProposalDraftRecord(
                kind="meeting_followup",
                title=f"会后跟进：{title[:40]}",
                summary=summary,
                rationale="将会议行动项转化为可审批的后续动作，避免会后失焦。",
                riskLevel="medium",
                targetRefs=target_refs,
                sourceRefs=[f"meeting_action_item:{action_id or _hash_text(title)}"],
                boundaryNotes=["该草稿仅用于会后跟进建议，需审批后执行。"],
                payload={"meetingId": meeting_id, "meetingActionItemId": action_id or None},
                requiresApproval=True,
            )
        )

    for item in risks:
        risk_id = str(item.get("id") or "").strip()
        summary = str(item.get("summary") or "").strip()
        severity = str(item.get("severity") or "").strip().lower()
        if not summary:
            continue
        high_risk = severity in {"high", "critical", "高", "严重"}
        kind = "task_prep" if high_risk else "evidence_request"
        drafts.append(
            DataCenterProposalDraftRecord(
                kind=kind,  # type: ignore[arg-type]
                title=("风险处置：" if high_risk else "补充风险证据：") + summary[:36],
                summary=summary,
                rationale="会议风险需要明确处置或补充证据，避免判断漂移。",
                riskLevel="high" if high_risk else "medium",
                targetRefs=target_refs,
                sourceRefs=[f"meeting_risk:{risk_id or _hash_text(summary)}"],
                boundaryNotes=["风险项需确认责任人与处置路径后执行。"],
                payload={"meetingId": meeting_id, "meetingRiskId": risk_id or None, "severity": severity},
                requiresApproval=True,
            )
        )

    for item in ambiguities:
        ambiguity_id = str(item.get("id") or "").strip()
        raw_text = str(item.get("raw_text") or item.get("rawText") or "").strip()
        if not raw_text:
            continue
        drafts.append(
            DataCenterProposalDraftRecord(
                kind="evidence_request",
                title=f"澄清会议歧义：{raw_text[:36]}",
                summary="会议存在歧义，建议先补证据再推进结论。",
                rationale="减少歧义导致的会后反复与执行偏差。",
                riskLevel="medium",
                targetRefs=target_refs,
                sourceRefs=[f"meeting_ambiguity:{ambiguity_id or _hash_text(raw_text)}"],
                boundaryNotes=["歧义项在证据补齐前不得转为正式判断。"],
                payload={"meetingId": meeting_id, "ambiguityId": ambiguity_id or None},
                requiresApproval=True,
            )
        )

    for item in open_questions[:6]:
        qid = str(item.get("id") or "").strip()
        question = str(item.get("question") or item.get("summary") or "").strip()
        if not question:
            continue
        drafts.append(
            DataCenterProposalDraftRecord(
                kind="evidence_request",
                title=f"补齐会议未决问题：{question[:30]}",
                summary=question,
                rationale="会后未决问题需要补证据，避免后续判断失真。",
                riskLevel="medium",
                targetRefs=target_refs,
                sourceRefs=[f"meeting_open_question:{qid or _hash_text(question)}"],
                boundaryNotes=["未决问题仅作为待确认事项。"],
                payload={"meetingId": meeting_id, "openQuestionId": qid or None},
                requiresApproval=True,
            )
        )

    if candidate_judgments and not meeting_context.officialJudgments:
        drafts.append(
            DataCenterProposalDraftRecord(
                kind="judgment_review",
                title="会议候选判断复核",
                summary="会议后存在候选判断，建议进入复核流程。",
                rationale="保持候选判断与正式判断边界，避免误用。",
                riskLevel="medium",
                targetRefs=target_refs,
                sourceRefs=[f"meeting_candidate_judgments:{len(candidate_judgments)}"],
                boundaryNotes=["候选判断不得直接作为 approved judgment。"],
                payload={"meetingId": meeting_id, "candidateCount": len(candidate_judgments)},
                requiresApproval=True,
            )
        )

    dedup: dict[tuple[str, str], DataCenterProposalDraftRecord] = {}
    for draft in drafts:
        source_key = draft.sourceRefs[0] if draft.sourceRefs else _hash_text(draft.title)
        key = (draft.kind, source_key)
        if key not in dedup:
            dedup[key] = draft
    return list(dedup.values())[:8]
