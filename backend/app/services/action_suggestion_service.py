from __future__ import annotations

from uuid import uuid4

from app.models import (
    ActionSuggestionRecord,
    AnswerMaterialRecord,
    AnswerPolicyRecord,
    PageContextPackRecord,
    ProposalTargetRefRecord,
    RouteDecisionRecord,
)


def _new_action_id() -> str:
    return f"act_{uuid4().hex[:10]}"


def build_action_suggestions(
    *,
    page_context: PageContextPackRecord,
    route_decision: RouteDecisionRecord,
    answer_policy: AnswerPolicyRecord,
    answer_material: AnswerMaterialRecord,
) -> list[ActionSuggestionRecord]:
    suggestions: list[ActionSuggestionRecord] = []

    if answer_material.missingContext and not page_context.rawEvidence and route_decision.intent in {
        "intro_profile",
        "business_profile",
        "strategy_profile",
        "evidence_question",
    }:
        suggestions.append(
            ActionSuggestionRecord(
                id=_new_action_id(),
                actionType="request_evidence",
                title="补充关键证据",
                summary="当前缺少可直接引用原文，建议补齐资料再生成正式回答。",
                rationale="回答素材不足，优先补齐文档证据可显著提升回答稳定性。",
                riskLevel="medium",
                requiresApproval=False,
                sourceRefs=answer_material.missingContext[:4],
                targetRefs=[
                    ProposalTargetRefRecord(targetType="client", targetId=page_context.clientId or page_context.scopeId, label="客户资料")
                ],
            )
        )

    if page_context.candidateJudgments and not page_context.officialJudgments:
        suggestions.append(
            ActionSuggestionRecord(
                id=_new_action_id(),
                actionType="confirm_candidate_judgment",
                title="确认候选判断",
                summary="存在候选判断但无已批准正式判断，建议尽快完成审核确认。",
                rationale="可减少候选结论长期悬置导致的回答边界不稳定。",
                riskLevel="medium",
                requiresApproval=True,
                sourceRefs=["candidate_judgments"],
                targetRefs=[
                    ProposalTargetRefRecord(targetType="judgment", targetId=page_context.scopeId, label="候选判断")
                ],
            )
        )

    if page_context.quality.contextQuality in {"weak", "none"}:
        suggestions.append(
            ActionSuggestionRecord(
                id=_new_action_id(),
                actionType="refresh_context_pack",
                title="刷新上下文包",
                summary="当前状态池较弱，建议触发一次上下文回填与主链重算。",
                rationale="提升 state object 覆盖后可降低弱回答或回退频率。",
                riskLevel="low",
                requiresApproval=False,
                sourceRefs=[f"contextQuality:{page_context.quality.contextQuality}"],
                targetRefs=[
                    ProposalTargetRefRecord(targetType="client", targetId=page_context.clientId or page_context.scopeId, label="上下文")
                ],
            )
        )

    if route_decision.intent == "task_next_action":
        suggestions.append(
            ActionSuggestionRecord(
                id=_new_action_id(),
                actionType="create_task",
                title="生成下一步任务",
                summary="基于当前任务上下文自动生成一条下一步执行任务建议。",
                rationale="将回答建议转为可执行动作，减少信息损耗。",
                riskLevel="low",
                requiresApproval=False,
                sourceRefs=answer_material.nextActions[:3],
                targetRefs=[
                    ProposalTargetRefRecord(targetType="task", targetId=page_context.scopeId, label="当前任务")
                ],
            )
        )
        suggestions.append(
            ActionSuggestionRecord(
                id=_new_action_id(),
                actionType="create_proposal",
                title="创建任务提案",
                summary="若信息仍不足，建议先创建 proposal 走审批补证据。",
                rationale="在不越权写正式层的前提下推进任务准备。",
                riskLevel="medium",
                requiresApproval=True,
                sourceRefs=answer_material.missingContext[:3],
                targetRefs=[
                    ProposalTargetRefRecord(targetType="task", targetId=page_context.scopeId, label="任务提案")
                ],
            )
        )

    if answer_policy.shouldCreateProposal and not any(item.actionType == "create_proposal" for item in suggestions):
        suggestions.append(
            ActionSuggestionRecord(
                id=_new_action_id(),
                actionType="create_proposal",
                title="建议创建 proposal",
                summary="当前资料不足以形成稳定回答，建议创建提案补齐信息链路。",
                rationale="避免在证据不足时继续输出低置信结论。",
                riskLevel="medium",
                requiresApproval=True,
                sourceRefs=page_context.missingContext[:4],
                targetRefs=[
                    ProposalTargetRefRecord(targetType="client", targetId=page_context.clientId or page_context.scopeId, label="客户提案")
                ],
            )
        )

    return suggestions
