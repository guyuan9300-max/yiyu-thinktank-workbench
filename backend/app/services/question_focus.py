from __future__ import annotations

import re
from typing import Iterable

from app.models import (
    PageContextPackRecord,
    QuestionFocusFacet,
    QuestionFocusFrameRecord,
    QuestionFocusGoal,
    RouteDecisionRecord,
    SemanticSourceRole,
)


def _norm(value: str | None) -> str:
    return re.sub(r"\s+", "", str(value or "").lower())


def _contains_any(text: str, tokens: Iterable[str]) -> bool:
    return any(token in text for token in tokens)


def build_question_focus_frame(
    *,
    prompt: str,
    route_decision: RouteDecisionRecord,
    page_context: PageContextPackRecord | None = None,
) -> QuestionFocusFrameRecord:
    # P2.14 FREEZE(answer-shaping-question-focus): question_focus 在 workspace/chat 主回答链里已经降级为纯诊断信息。
    # 当前只允许输出开放的 explain/general，不再参与证据加权、展开抑制或回答结构塑形。
    del prompt, page_context
    if route_decision.intent == "official_judgment_registry":
        return QuestionFocusFrameRecord(
            goal="judgment",
            subjectFacet="general",
            depth="focused",
            suppressedExpansions=[],
            preferredRoles=[],
            discouragedRoles=[],
            reasonTrace=["diagnostic:official_registry"],
        )
    return QuestionFocusFrameRecord(
        goal="explain",
        subjectFacet="general",
        depth="expanded",
        suppressedExpansions=[],
        preferredRoles=[],
        discouragedRoles=[],
        reasonTrace=["diagnostic:open_workspace_chat"],
    )


def score_focus_role_match(
    focus_frame: QuestionFocusFrameRecord,
    roles: list[SemanticSourceRole],
) -> tuple[float, list[str]]:
    # P2.14 FREEZE(answer-shaping-focus-scoring): 焦点匹配分当前固定停用，防止 question_focus 重新影响主回答供料排序。
    del focus_frame, roles
    return 0.0, []


def coverage_targets_for_focus(focus_frame: QuestionFocusFrameRecord) -> list[SemanticSourceRole]:
    # P2.14 FREEZE(answer-shaping-focus-coverage): 主回答链不再从 focus 派生 coverage targets。
    del focus_frame
    return []
