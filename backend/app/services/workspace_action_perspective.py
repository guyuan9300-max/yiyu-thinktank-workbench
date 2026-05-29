from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


ActionAnswerPerspective = Literal["individual", "team", "organization", "project", "meeting_followup"]
ActionPerspectiveSource = Literal["explicit_prompt", "page_context", "account_role", "fallback_default"]


@dataclass(frozen=True)
class ActionPerspectiveRecord:
    answerPerspective: ActionAnswerPerspective
    perspectiveSource: ActionPerspectiveSource
    viewerRole: str = "employee"
    reason: str = ""


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").lower())


def infer_action_perspective(
    *,
    prompt: str,
    page: str = "workspace_chat",
    scope_type: str = "client",
    viewer_role: str = "employee",
    primary_role: str = "employee",
) -> ActionPerspectiveRecord:
    text = _compact(prompt)
    role = str(viewer_role or primary_role or "employee").strip().lower()
    primary = str(primary_role or "").strip().lower()
    page_key = str(page or "").strip().lower()
    scope_key = str(scope_type or "").strip().lower()

    organization_tokens = (
        "作为秘书长",
        "作为ceo",
        "作为创始人",
        "机构层面",
        "组织层面",
        "整个机构",
        "整个组织",
        "全机构",
        "理事会",
    )
    team_tokens = ("作为部门负责人", "部门层面", "团队层面", "我们团队", "部门接下来")
    project_tokens = ("作为项目负责人", "项目负责人", "项目层面", "这个项目", "项目下一步")
    meeting_tokens = ("会后", "这次会议", "会议之后", "会议后")
    individual_tokens = ("我接下来", "我下一步", "我应该", "作为个人", "我自己")

    if any(token in text for token in organization_tokens):
        return ActionPerspectiveRecord("organization", "explicit_prompt", role, "prompt_requested_organization")
    if any(token in text for token in team_tokens):
        return ActionPerspectiveRecord("team", "explicit_prompt", role, "prompt_requested_team")
    if any(token in text for token in project_tokens):
        return ActionPerspectiveRecord("project", "explicit_prompt", role, "prompt_requested_project")
    if any(token in text for token in meeting_tokens):
        return ActionPerspectiveRecord("meeting_followup", "explicit_prompt", role, "prompt_requested_meeting")
    if any(token in text for token in individual_tokens):
        return ActionPerspectiveRecord("individual", "explicit_prompt", role, "prompt_requested_individual")

    if page_key == "meeting_detail" or scope_key == "meeting":
        return ActionPerspectiveRecord("meeting_followup", "page_context", role, "meeting_scope")
    if page_key in {"project_module_detail", "project_flow_detail", "task_detail", "event_line_detail"} or scope_key in {
        "project_module",
        "project_flow",
        "task",
        "event_line",
    }:
        return ActionPerspectiveRecord("project", "page_context", role, "project_or_task_scope")

    if role == "admin" or primary in {"admin", "ceo", "organization_lead", "organization_admin", "org_admin"}:
        return ActionPerspectiveRecord("organization", "account_role", role or primary, "organization_leader_role")
    if role == "department_lead" or primary in {"department_lead", "supervisor", "director", "manager"}:
        return ActionPerspectiveRecord("team", "account_role", role or primary, "department_lead_role")

    return ActionPerspectiveRecord("individual", "fallback_default", role or primary or "employee", "default_individual")
