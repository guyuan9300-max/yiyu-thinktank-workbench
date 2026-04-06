from __future__ import annotations

import asyncio
import html
import ipaddress
import logging
import mimetypes
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import Body, Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response

logger = logging.getLogger(__name__)

from app.department_catalog import get_department_entry, list_department_catalog
from app.db import Database, from_json, to_json
from app.models import (
    AuthTokenResponse,
    ClientSummaryRecord,
    ConsultationChatPayload,
    ConsultationChatResponse,
    ConsultationKnowledgeRequestCreatePayload,
    ConsultationKnowledgeRequestRecord,
    ConsultationKnowledgeRequestUpdatePayload,
    DepartmentOption,
    EmployeeRecord,
    EmployeeDepartmentPayload,
    EventLineActivityRecord,
    EventLineCreatePayload,
    EventLineDetailRecord,
    EventLineRecord,
    EventLineReportAttachmentRecord,
    EventLineReportSnapshotRecord,
    EventLineUpdatePayload,
    HealthResponse,
    HierarchyReportRecord,
    FeishuBindingRelaySessionCreatePayload,
    FeishuBindingRelaySessionStatusRecord,
    AdminResetPasswordPayload,
    ChangePasswordPayload,
    LoginPayload,
    ManagementSignalCardRecord,
    MentionCandidate,
    OrgDepartmentRecord,
    OrgDepartmentPlanItemRecord,
    OrgDepartmentPlanRecord,
    OrgDepartmentQuarterPlanRecord,
    OrgEmployeeBindingRecord,
    OrgFocusItemRecord,
    OrgModelProfileRecord,
    OrgProfileRecord,
    OrgQuarterPlanRecord,
    OrgRoleProcessTemplateRecord,
    OrgReportingLineRecord,
    OrgRoleTemplateRecord,
    OrgTaskControlRuleRecord,
    TaskOrgBackfillResultRecord,
    PersonalGrowthCardRecord,
    PlanNodeRecord,
    PrimaryRole,
    RefreshPayload,
    ReviewDashboardResponse,
    ReviewHistoryEntryRecord,
    ReviewHistoryResponse,
    RegisterPayload,
    RejectPayload,
    ReportActionCardRecord,
    RolePayload,
    SessionUser,
    SmartTaskDraftResponse,
    SupportRequestCreatePayload,
    SupportRequestRecord,
    SupportRequestResolvePayload,
    TaskActivityRecord,
    TaskAttachmentRecord,
    TaskAttachmentTranscriptionResponse,
    TaskBoardResponse,
    TaskCollaboratorRecord,
    TaskCompletionReviewPayload,
    TaskCreatePayload,
    TaskListLibraryResponse,
    TaskListMutationPayload,
    TaskListRecord,
    TaskNotePayload,
    OrgAiConfigRecord,
    OrgAiConfigUpdatePayload,
    OrgAiConfigSecretRecord,
    TaskOrgContextRecord,
    TaskRecord,
    TaskReturnPayload,
    TaskSettingsPayload,
    TaskSettingsRecord,
    TaskTagLibraryResponse,
    TaskTagMutationPayload,
    TaskTagRecord,
    TaskPlanLinkRecord,
    TaskPlanLinkUpsertPayload,
    TaskUpdatePayload,
    WeeklyReviewCreatePayload,
    WeeklyReviewEntryRecord,
    WeeklyReviewEventLineContextRecord,
    WeeklyReviewTaskEntryRecord,
    WeeklyReviewTaskSnapshotRecord,
    WeeklyReviewTaskStructuredNoteRecord,
)
from app.smart_input import build_smart_task_draft, transcribe_audio_with_doubao
from app.bootstrap_security import DEFAULT_BOOTSTRAP_ADMIN_EMAIL, ensure_cloud_secret, resolve_seed_users
from app.security import create_access_token, decode_access_token, hash_password, verify_password


APP_NAME = "益语智库中心任务后端"
APP_VERSION = "0.1.0"
DEFAULT_ORG_ID = "org_yiyu_default"
DEFAULT_ADMIN_EMAIL = DEFAULT_BOOTSTRAP_ADMIN_EMAIL
ALLOWED_APPROVER_ROLES: tuple[PrimaryRole, ...] = ("admin",)
ORG_QUARTERS: tuple[str, ...] = ("Q1", "Q2", "Q3", "Q4")


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


def safe_filename(name: str) -> str:
    candidate = Path(name or "attachment").name.strip() or "attachment"
    sanitized = re.sub(r"[^0-9A-Za-z._\-\u4e00-\u9fff]+", "_", candidate)
    return sanitized[:120] or "attachment"


def _is_public_hostname(hostname: str) -> bool:
    value = hostname.strip().lower()
    if not value or value == "localhost" or value.endswith(".local"):
        return False
    try:
        return not ipaddress.ip_address(value).is_private and not ipaddress.ip_address(value).is_loopback
    except ValueError:
        return True


def _resolve_public_base_url(request: Request) -> str | None:
    configured = (
        os.getenv("YIYU_CLOUD_PUBLIC_BASE_URL", "").strip()
        or os.getenv("YIYU_PUBLIC_BASE_URL", "").strip()
    )
    if configured:
        return configured.rstrip("/")

    forwarded_host = (request.headers.get("x-forwarded-host") or "").split(",", 1)[0].strip()
    host = forwarded_host or (request.headers.get("host") or "").split(",", 1)[0].strip()
    hostname = host.split(":", 1)[0]
    if not _is_public_hostname(hostname):
        return None

    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "http").split(",", 1)[0].strip()
    return f"{proto}://{host}".rstrip("/")


@dataclass
class AppState:
    db: Database
    data_dir: Path
    secret_key: str


def _state(app: FastAPI) -> AppState:
    return app.state.app_state


def _sql_placeholders(values: list[str] | tuple[str, ...]) -> str:
    return ",".join("?" for _ in values)


def _row_user(row) -> SessionUser:
    return SessionUser(
        id=str(row["id"]),
        organizationId=str(row["organization_id"]),
        email=str(row["email"]),
        fullName=str(row["full_name"]),
        primaryRole=str(row["primary_role"]),
        accountStatus=str(row["account_status"]),
    )


def _employee_record(row) -> EmployeeRecord:
    department = get_department_entry(str(row["department_id"]) if row["department_id"] else None, str(row["department_name"]) if row["department_name"] else None)
    return EmployeeRecord(
        id=str(row["id"]),
        email=str(row["email"]),
        fullName=str(row["full_name"]),
        primaryRole=str(row["primary_role"]),
        accountStatus=str(row["account_status"]),
        departmentId=department.id if department else (str(row["department_id"]) if row["department_id"] else None),
        departmentName=department.name if department else (str(row["department_name"]) if row["department_name"] else None),
        jobTitle=str(row["job_title"]) if row["job_title"] else None,
        managerName=str(row["manager_name"]) if row["manager_name"] else None,
        currentFocus=str(row["current_focus"]) if row["current_focus"] else None,
        isDepartmentLead=bool(int(row["is_department_lead"] or 0)),
        approvedAt=row["approved_at"],
        rejectedReason=row["rejected_reason"],
        disabledAt=row["disabled_at"],
        lastLoginAt=row["last_login_at"],
        createdAt=str(row["created_at"]),
    )


def _split_lines(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in str(value).splitlines() if item.strip()]


def _bool_value(row, key: str) -> bool:
    return bool(int(row[key] or 0))


def _normalize_quarter(value: str | None) -> Literal["Q1", "Q2", "Q3", "Q4"]:
    normalized = (value or "").strip().upper()
    if normalized in ORG_QUARTERS:
        return normalized  # type: ignore[return-value]
    return "Q1"


def _default_quarter_plan(year: str, quarter: Literal["Q1", "Q2", "Q3", "Q4"]) -> OrgQuarterPlanRecord:
    return OrgQuarterPlanRecord(
        id=f"org_{year or 'draft'}_{quarter.lower()}",
        year=year,
        quarter=quarter,
        theme="",
        objective="",
        keyResults=[],
        keyActions=[],
        majorRisks=[],
        updatedAt="",
    )


def _coerce_org_quarter_plans(raw_value, year: str) -> list[OrgQuarterPlanRecord]:
    raw_items = from_json(raw_value, [])
    by_quarter: dict[str, OrgQuarterPlanRecord] = {}
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        quarter = _normalize_quarter(item.get("quarter"))
        plan = OrgQuarterPlanRecord(
            id=str(item.get("id") or f"org_{year or 'draft'}_{quarter.lower()}"),
            year=str(item.get("year") or year or ""),
            quarter=quarter,
            theme=str(item.get("theme") or ""),
            objective=str(item.get("objective") or ""),
            keyResults=[str(part).strip() for part in item.get("keyResults", []) if str(part).strip()],
            keyActions=[str(part).strip() for part in item.get("keyActions", []) if str(part).strip()],
            majorRisks=[str(part).strip() for part in item.get("majorRisks", []) if str(part).strip()],
            updatedAt=str(item.get("updatedAt") or ""),
        )
        by_quarter[quarter] = plan
    return [by_quarter.get(quarter) or _default_quarter_plan(year, quarter) for quarter in ORG_QUARTERS]


def _coerce_department_quarter_plan(raw_value) -> OrgDepartmentQuarterPlanRecord:
    raw = from_json(raw_value, {})
    if not isinstance(raw, dict):
        raw = {}
    return OrgDepartmentQuarterPlanRecord(
        year=str(raw.get("year") or ""),
        quarter=_normalize_quarter(raw.get("quarter")),
        objective=str(raw.get("objective") or ""),
        deliverables=[str(item).strip() for item in raw.get("deliverables", []) if str(item).strip()],
        successMetrics=[str(item).strip() for item in raw.get("successMetrics", []) if str(item).strip()],
        majorRisks=[str(item).strip() for item in raw.get("majorRisks", []) if str(item).strip()],
        updatedAt=str(raw.get("updatedAt") or ""),
    )


def _org_profile_record(state: AppState, organization_id: str) -> OrgProfileRecord:
    org_row = state.db.fetchone("SELECT * FROM organizations WHERE id = ?", (organization_id,))
    if not org_row:
        raise HTTPException(status_code=404, detail="机构不存在")
    profile_row = state.db.fetchone("SELECT * FROM org_profiles WHERE organization_id = ?", (organization_id,))
    if not profile_row:
        return OrgProfileRecord(
            organizationId=organization_id,
            name=str(org_row["name"]),
            annualGoal="",
            annualStrategyYear="",
            annualStrategy="",
            quarterPlans=_coerce_org_quarter_plans([], ""),
            quarterlyFocus=[],
            leaderUserId=None,
            managementUserIds=[],
            updatedAt=str(org_row["updated_at"]),
        )
    annual_strategy_year = str(profile_row["annual_strategy_year"] or "")
    return OrgProfileRecord(
        organizationId=organization_id,
        name=str(org_row["name"]),
        annualGoal=str(profile_row["annual_goal"] or ""),
        annualStrategyYear=annual_strategy_year,
        annualStrategy=str(profile_row["annual_strategy_text"] or ""),
        quarterPlans=_coerce_org_quarter_plans(profile_row["quarter_plans_json"], annual_strategy_year),
        quarterlyFocus=[str(item) for item in from_json(profile_row["quarterly_focus_json"], []) if str(item).strip()],
        leaderUserId=str(profile_row["leader_user_id"]) if profile_row["leader_user_id"] else None,
        managementUserIds=[str(item) for item in from_json(profile_row["management_user_ids_json"], []) if str(item).strip()],
        updatedAt=str(profile_row["updated_at"]),
    )


def _list_org_departments(state: AppState, organization_id: str) -> list[OrgDepartmentRecord]:
    rows = state.db.fetchall(
        """
        SELECT *
        FROM org_departments
        WHERE organization_id = ?
        ORDER BY active DESC, name COLLATE NOCASE ASC
        """,
        (organization_id,),
    )
    return [
        OrgDepartmentRecord(
            id=str(row["id"]),
            name=str(row["name"]),
            color=str(row["color"] or "#5B7BFE"),
            leaderUserId=str(row["leader_user_id"]) if row["leader_user_id"] else None,
            parentDepartmentId=str(row["parent_department_id"]) if row["parent_department_id"] else None,
            mission=str(row["mission"] or ""),
            businessContext=str(row["business_context"] or ""),
            teamContext=str(row["team_context"] or ""),
            quarterPlan=_coerce_department_quarter_plan(row["quarter_plan_json"]),
            quarterlyFocus=[str(item) for item in from_json(row["quarterly_focus_json"], []) if str(item).strip()],
            collaborationDepartmentIds=[str(item) for item in from_json(row["collaboration_department_ids_json"], []) if str(item).strip()],
            active=_bool_value(row, "active"),
            updatedAt=str(row["updated_at"]),
        )
        for row in rows
    ]


def _list_org_roles(state: AppState, organization_id: str) -> list[OrgRoleTemplateRecord]:
    rows = state.db.fetchall(
        """
        SELECT *
        FROM org_role_templates
        WHERE organization_id = ?
        ORDER BY sort_order ASC, updated_at DESC
        """,
        (organization_id,),
    )
    return [
        OrgRoleTemplateRecord(
            id=str(row["id"]),
            departmentId=str(row["department_id"]) if row["department_id"] else None,
            name=str(row["name"]),
            level=str(row["level"]),
            managerRoleId=str(row["manager_role_id"]) if row["manager_role_id"] else None,
            isManager=_bool_value(row, "is_manager"),
            goal=str(row["goal"] or ""),
            responsibilities=[str(item) for item in from_json(row["responsibilities_json"], []) if str(item).strip()],
            shouldAvoid=[str(item) for item in from_json(row["should_avoid_json"], []) if str(item).strip()],
            collaborationRoleIds=[str(item) for item in from_json(row["collaboration_role_ids_json"], []) if str(item).strip()],
            taskEditScope=str(row["task_edit_scope"] or "self"),
            canApproveTasks=_bool_value(row, "can_approve_tasks"),
            canReassignTasks=_bool_value(row, "can_reassign_tasks"),
            canChangeDeadline=_bool_value(row, "can_change_deadline"),
            sortOrder=int(row["sort_order"] or 0),
            active=_bool_value(row, "active"),
            updatedAt=str(row["updated_at"]),
        )
        for row in rows
    ]


def _list_org_bindings(state: AppState, organization_id: str) -> list[OrgEmployeeBindingRecord]:
    rows = state.db.fetchall(
        """
        SELECT *
        FROM org_employee_role_bindings
        WHERE organization_id = ?
        ORDER BY updated_at DESC
        """,
        (organization_id,),
    )
    return [
        OrgEmployeeBindingRecord(
            userId=str(row["user_id"]),
            departmentId=str(row["department_id"]) if row["department_id"] else None,
            primaryRoleId=str(row["primary_role_id"]) if row["primary_role_id"] else None,
            managerUserId=str(row["manager_user_id"]) if row["manager_user_id"] else None,
            isManager=_bool_value(row, "is_manager"),
            projectRoleLabels=[str(item) for item in from_json(row["project_role_labels_json"], []) if str(item).strip()],
            currentFocus=str(row["current_focus"] or ""),
            taskEditScope=str(row["task_edit_scope"] or "self"),
            canApproveTasks=_bool_value(row, "can_approve_tasks"),
            canReassignTasks=_bool_value(row, "can_reassign_tasks"),
            canChangeDeadline=_bool_value(row, "can_change_deadline"),
            updatedAt=str(row["updated_at"]),
        )
        for row in rows
    ]


def _list_org_reporting_lines(state: AppState, organization_id: str) -> list[OrgReportingLineRecord]:
    rows = state.db.fetchall(
        """
        SELECT *
        FROM org_reporting_lines
        WHERE organization_id = ?
        ORDER BY updated_at DESC
        """,
        (organization_id,),
    )
    return [
        OrgReportingLineRecord(
            id=str(row["id"]),
            managerUserId=str(row["manager_user_id"]),
            reportUserId=str(row["report_user_id"]),
            lineType=str(row["line_type"] or "business"),
            approvesTasks=_bool_value(row, "approves_tasks"),
            canAdjustTasks=_bool_value(row, "can_adjust_tasks"),
            canChangeDeadline=_bool_value(row, "can_change_deadline"),
            canReassignTasks=_bool_value(row, "can_reassign_tasks"),
            isCrossDepartmentApprover=_bool_value(row, "is_cross_department_approver"),
            active=_bool_value(row, "active"),
            updatedAt=str(row["updated_at"]),
        )
        for row in rows
    ]


def _list_org_task_control_rules(state: AppState, organization_id: str) -> list[OrgTaskControlRuleRecord]:
    rows = state.db.fetchall(
        """
        SELECT *
        FROM org_task_control_rules
        WHERE organization_id = ?
        ORDER BY updated_at DESC
        """,
        (organization_id,),
    )
    return [
        OrgTaskControlRuleRecord(
            id=str(row["id"]),
            name=str(row["name"]),
            controlLevel=str(row["control_level"] or "normal"),
            departmentId=str(row["department_id"]) if row["department_id"] else None,
            roleTemplateId=str(row["role_template_id"]) if row["role_template_id"] else None,
            contentEditableBy=str(row["content_editable_by"] or "assignee"),
            deadlineEditableBy=str(row["deadline_editable_by"] or "manager"),
            ownerEditableBy=str(row["owner_editable_by"] or "manager"),
            cancellableBy=str(row["cancellable_by"] or "manager"),
            requireCollabConfirmation=_bool_value(row, "require_collab_confirmation"),
            defaultApproverUserId=str(row["default_approver_user_id"]) if row["default_approver_user_id"] else None,
            active=_bool_value(row, "active"),
            updatedAt=str(row["updated_at"]),
        )
        for row in rows
    ]


def _list_org_role_process_templates(state: AppState, organization_id: str) -> list[OrgRoleProcessTemplateRecord]:
    rows = state.db.fetchall(
        """
        SELECT *
        FROM org_role_process_templates
        WHERE organization_id = ?
        ORDER BY updated_at DESC
        """,
        (organization_id,),
    )
    return [
        OrgRoleProcessTemplateRecord(
            id=str(row["id"]),
            roleTemplateId=str(row["role_template_id"]) if row["role_template_id"] else None,
            name=str(row["name"]),
            triggerType=str(row["trigger_type"] or "manual"),
            triggerCondition=str(row["trigger_condition"] or ""),
            keySteps=[str(item) for item in from_json(row["key_steps_json"], []) if str(item).strip()],
            collaborationStep=str(row["collaboration_step"] or ""),
            approvalStep=str(row["approval_step"] or ""),
            outputArtifact=str(row["output_artifact"] or ""),
            commonBlockers=[str(item) for item in from_json(row["common_blockers_json"], []) if str(item).strip()],
            active=_bool_value(row, "active"),
            updatedAt=str(row["updated_at"]),
        )
        for row in rows
    ]



def _list_org_focus_items(state: AppState, organization_id: str) -> list[OrgFocusItemRecord]:
    rows = state.db.fetchall(
        """
        SELECT *
        FROM org_focus_items
        WHERE organization_id = ?
        ORDER BY CASE status WHEN 'active' THEN 0 WHEN 'draft' THEN 1 WHEN 'paused' THEN 2 ELSE 3 END,
                 CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                 updated_at DESC
        """,
        (organization_id,),
    )
    return [
        OrgFocusItemRecord(
            id=str(row["id"]),
            periodKey=str(row["period_key"] or ""),
            title=str(row["title"] or ""),
            statement=str(row["statement"] or ""),
            ownerUserId=str(row["owner_user_id"]) if row["owner_user_id"] else None,
            priority=str(row["priority"] or "medium"),
            status=str(row["status"] or "active"),
            evidenceKeywords=[str(item).strip() for item in from_json(row["evidence_keywords_json"], []) if str(item).strip()],
            updatedAt=str(row["updated_at"]),
        )
        for row in rows
    ]


def _list_org_department_plan_items(state: AppState, organization_id: str, plan_id: str) -> list[OrgDepartmentPlanItemRecord]:
    rows = state.db.fetchall(
        """
        SELECT *
        FROM org_department_plan_items
        WHERE organization_id = ? AND plan_id = ?
        ORDER BY sort_order ASC, updated_at DESC
        """,
        (organization_id, plan_id),
    )
    return [
        OrgDepartmentPlanItemRecord(
            id=str(row["id"]),
            focusItemId=str(row["focus_item_id"]) if row["focus_item_id"] else None,
            title=str(row["title"] or ""),
            statement=str(row["statement"] or ""),
            ownerUserId=str(row["owner_user_id"]) if row["owner_user_id"] else None,
            status=str(row["status"] or "active"),
            expectedOutput=str(row["expected_output"] or ""),
            sortOrder=int(row["sort_order"] or 0),
            updatedAt=str(row["updated_at"]),
        )
        for row in rows
    ]


def _list_org_department_plans(state: AppState, organization_id: str) -> list[OrgDepartmentPlanRecord]:
    rows = state.db.fetchall(
        """
        SELECT *
        FROM org_department_plans
        WHERE organization_id = ?
        ORDER BY updated_at DESC
        """,
        (organization_id,),
    )
    return [
        OrgDepartmentPlanRecord(
            id=str(row["id"]),
            departmentId=str(row["department_id"]) if row["department_id"] else None,
            weekLabel=str(row["week_label"] or ""),
            ownerUserId=str(row["owner_user_id"]) if row["owner_user_id"] else None,
            summary=str(row["summary"] or ""),
            majorRisks=[str(item).strip() for item in from_json(row["major_risks_json"], []) if str(item).strip()],
            dependencies=[str(item).strip() for item in from_json(row["dependencies_json"], []) if str(item).strip()],
            status=str(row["status"] or "draft"),
            items=_list_org_department_plan_items(state, organization_id, str(row["id"])),
            updatedAt=str(row["updated_at"]),
        )
        for row in rows
    ]


def _week_label_for_task_due_date(value: str | None) -> str:
    due_date = _parse_date_only(value) or datetime.now().date()
    iso = due_date.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _matching_fragments(*values: str | None) -> list[str]:
    fragments: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value:
            continue
        for chunk in re.split(r"[\n,，。；;、|/]+", str(value).lower()):
            part = chunk.strip()
            if len(part) >= 2 and part not in seen:
                seen.add(part)
                fragments.append(part)
            if " " in part:
                for token in part.split():
                    token = token.strip()
                    if len(token) >= 3 and token not in seen:
                        seen.add(token)
                        fragments.append(token)
    return fragments


def _score_text_against_fragments(task_text: str, fragments: list[str]) -> float:
    haystack = task_text.lower()
    score = 0.0
    for fragment in fragments:
        if fragment and fragment in haystack:
            score += 1.0 + min(len(fragment), 16) / 16.0
    return score


def _resolve_focus_item_candidate(state: AppState, organization_id: str, task_text: str):
    best_row = None
    best_score = 0.0
    rows = state.db.fetchall(
        """
        SELECT *
        FROM org_focus_items
        WHERE organization_id = ? AND status IN ('draft', 'active', 'paused')
        ORDER BY updated_at DESC
        """,
        (organization_id,),
    )
    for row in rows:
        fragments = _matching_fragments(row["title"], row["statement"], *from_json(row["evidence_keywords_json"], []))
        score = _score_text_against_fragments(task_text, fragments)
        if score > best_score:
            best_row = row
            best_score = score
    return best_row, best_score


def _resolve_department_plan_candidate(state: AppState, organization_id: str, department_id: str | None, week_label: str, task_text: str):
    if not department_id:
        return None, None, 0.0, "ai"
    plan_rows = state.db.fetchall(
        """
        SELECT *
        FROM org_department_plans
        WHERE organization_id = ? AND department_id = ? AND week_label = ? AND status IN ('draft', 'active')
        ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, updated_at DESC
        """,
        (organization_id, department_id, week_label),
    )
    if not plan_rows:
        return None, None, 0.0, "ai"
    best_item = None
    best_focus = None
    best_score = 0.0
    for plan_row in plan_rows:
        item_rows = state.db.fetchall(
            """
            SELECT *
            FROM org_department_plan_items
            WHERE organization_id = ? AND plan_id = ?
            ORDER BY sort_order ASC, updated_at DESC
            """,
            (organization_id, str(plan_row["id"])),
        )
        for item_row in item_rows:
            fragments = _matching_fragments(item_row["title"], item_row["statement"], item_row["expected_output"])
            score = _score_text_against_fragments(task_text, fragments)
            focus_row = None
            if item_row["focus_item_id"]:
                focus_row = state.db.fetchone("SELECT * FROM org_focus_items WHERE id = ?", (str(item_row["focus_item_id"]),))
                if focus_row:
                    score += _score_text_against_fragments(
                        task_text,
                        _matching_fragments(
                            focus_row["title"],
                            focus_row["statement"],
                            *from_json(focus_row["evidence_keywords_json"], []),
                        ),
                    ) * 0.35
            if score > best_score:
                best_item = item_row
                best_focus = focus_row
                best_score = score
    if best_item:
        return best_item, best_focus, best_score, "ai"
    total_items = state.db.fetchone(
        """
        SELECT COUNT(*) AS count
        FROM org_department_plan_items items
        JOIN org_department_plans plans ON plans.id = items.plan_id
        WHERE items.organization_id = ? AND plans.department_id = ? AND plans.week_label = ? AND plans.status IN ('draft', 'active')
        """,
        (organization_id, department_id, week_label),
    )
    if total_items and int(total_items["count"] or 0) == 1:
        item_row = state.db.fetchone(
            """
            SELECT items.*
            FROM org_department_plan_items items
            JOIN org_department_plans plans ON plans.id = items.plan_id
            WHERE items.organization_id = ? AND plans.department_id = ? AND plans.week_label = ? AND plans.status IN ('draft', 'active')
            LIMIT 1
            """,
            (organization_id, department_id, week_label),
        )
        if item_row:
            focus_row = state.db.fetchone("SELECT * FROM org_focus_items WHERE id = ?", (str(item_row["focus_item_id"]),)) if item_row["focus_item_id"] else None
            return item_row, focus_row, 0.45, "rule"
    return None, None, 0.0, "ai"


def _task_plan_link_row(state: AppState, task_id: str):
    return state.db.fetchone("SELECT * FROM task_plan_links WHERE task_id = ?", (task_id,))


def _task_plan_link_record(row) -> TaskPlanLinkRecord:
    return TaskPlanLinkRecord(
        taskId=str(row["task_id"]),
        departmentPlanItemId=str(row["department_plan_item_id"]) if row["department_plan_item_id"] else None,
        focusItemId=str(row["focus_item_id"]) if row["focus_item_id"] else None,
        linkedBy=str(row["linked_by"] or "ai"),
        confidence=float(row["confidence"] or 0),
        updatedAt=str(row["updated_at"]),
    )


def _sync_task_plan_link(state: AppState, task_row, org_link_row=None):
    task_id = str(task_row["id"])
    existing = _task_plan_link_row(state, task_id)
    if existing and str(existing["linked_by"] or "ai") == "manager":
        return existing
    organization_id = str(task_row["organization_id"])
    task_text = f"{str(task_row['title'] or '')}\n{str(task_row['description'] or '')}"
    week_label = _week_label_for_task_due_date(str(task_row["due_date"]) if task_row["due_date"] else None)
    department_id = str(org_link_row["department_id"]) if org_link_row and org_link_row["department_id"] else None
    plan_item_row, focus_row, plan_score, linked_by = _resolve_department_plan_candidate(state, organization_id, department_id, week_label, task_text)
    if not focus_row:
        focus_candidate, focus_score = _resolve_focus_item_candidate(state, organization_id, task_text)
        if focus_candidate and focus_score >= max(plan_score * 0.8, 1.0):
            focus_row = focus_candidate
            if not plan_item_row:
                linked_by = "ai"
                plan_score = focus_score
    if not plan_item_row and not focus_row:
        if existing:
            state.db.execute("DELETE FROM task_plan_links WHERE task_id = ?", (task_id,))
        return None
    state.db.execute(
        """
        INSERT OR REPLACE INTO task_plan_links(
            task_id, organization_id, department_plan_item_id, focus_item_id, linked_by, confidence, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task_id,
            organization_id,
            str(plan_item_row["id"]) if plan_item_row else None,
            str(focus_row["id"]) if focus_row else None,
            linked_by,
            round(plan_score, 2),
            now_iso(),
        ),
    )
    return _task_plan_link_row(state, task_id)


def _support_request_record(row) -> SupportRequestRecord:
    return SupportRequestRecord(
        id=str(row["id"]),
        taskId=str(row["task_id"]) if row["task_id"] else None,
        requesterUserId=str(row["requester_user_id"]),
        targetScope=str(row["target_scope"]),
        targetRefId=str(row["target_ref_id"]) if row["target_ref_id"] else None,
        requestType=str(row["request_type"]),
        urgency=str(row["urgency"] or "medium"),
        summary=str(row["summary"] or ""),
        status=str(row["status"] or "open"),
        resolutionNote=str(row["resolution_note"] or ""),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _consultation_knowledge_request_record(row) -> ConsultationKnowledgeRequestRecord:
    return ConsultationKnowledgeRequestRecord(
        id=str(row["id"]),
        answerId=str(row["answer_id"]),
        organizationId=str(row["organization_id"]),
        target=str(row["target"]),
        status=str(row["status"]),
        requestedByUserId=str(row["requested_by_user_id"]),
        requestedByName=str(row["requested_by_name"] or ""),
        clientId=str(row["client_id"]) if row["client_id"] else None,
        clientName=str(row["client_name"]) if row["client_name"] else None,
        taskId=str(row["task_id"]) if row["task_id"] else None,
        eventLineId=str(row["event_line_id"]) if row["event_line_id"] else None,
        question=str(row["question"] or ""),
        answer=str(row["answer"] or ""),
        errorMessage=str(row["error_message"]) if row["error_message"] else None,
        localDocumentId=str(row["local_document_id"]) if row["local_document_id"] else None,
        localDocumentPath=str(row["local_document_path"]) if row["local_document_path"] else None,
        completedAt=str(row["completed_at"]) if row["completed_at"] else None,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _consultation_request_row_or_404(state: AppState, request_id: str, organization_id: str):
    row = state.db.fetchone(
        """
        SELECT
            req.*,
            ans.client_id,
            ans.client_name,
            ans.task_id,
            ans.event_line_id,
            ans.question,
            ans.answer,
            author.full_name AS requested_by_name
        FROM consultation_knowledge_requests req
        JOIN consultation_answers ans ON ans.id = req.answer_id
        LEFT JOIN employee_accounts author ON author.id = req.requested_by_user_id
        WHERE req.id = ? AND req.organization_id = ?
        """,
        (request_id, organization_id),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Consultation knowledge request not found")
    return row


def _create_consultation_knowledge_request_internal(
    state: AppState,
    *,
    current_user: SessionUser,
    target: Literal["vector_memory", "document_archive"],
    question: str,
    answer: str,
    client_id: str | None,
    client_name: str | None,
    task_id: str | None,
    event_line_id: str | None,
    source: str,
) -> ConsultationKnowledgeRequestRecord:
    normalized_answer = answer.strip()
    if not normalized_answer:
        raise HTTPException(status_code=400, detail="答案内容不能为空")

    timestamp = now_iso()
    answer_id = new_id("consult_answer")
    request_id = new_id("consult_req")
    state.db.execute(
        """
        INSERT INTO consultation_answers(
            id, organization_id, author_user_id, client_id, client_name, task_id, event_line_id,
            question, answer, source, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            answer_id,
            current_user.organizationId,
            current_user.id,
            client_id,
            client_name.strip() if client_name else None,
            task_id,
            event_line_id,
            question.strip(),
            normalized_answer,
            source,
            timestamp,
            timestamp,
        ),
    )
    state.db.execute(
        """
        INSERT INTO consultation_knowledge_requests(
            id, answer_id, organization_id, target, status, requested_by_user_id, error_message,
            local_document_id, local_document_path, completed_at, created_at, updated_at
        ) VALUES(?, ?, ?, ?, 'pending', ?, NULL, NULL, NULL, NULL, ?, ?)
        """,
        (
            request_id,
            answer_id,
            current_user.organizationId,
            target,
            current_user.id,
            timestamp,
            timestamp,
        ),
    )
    _log_audit(
        state,
        "consultation.knowledge_request_created",
        actor_user_id=current_user.id,
        target_user_id=None,
        detail={
            "requestId": request_id,
            "answerId": answer_id,
            "target": target,
            "clientId": client_id or "",
            "taskId": task_id or "",
            "eventLineId": event_line_id or "",
            "source": source,
        },
    )
    row = _consultation_request_row_or_404(state, request_id, current_user.organizationId)
    return _consultation_knowledge_request_record(row)


def _event_line_row_or_404(state: AppState, event_line_id: str, organization_id: str):
    row = state.db.fetchone(
        "SELECT * FROM event_lines WHERE id = ? AND organization_id = ?",
        (event_line_id, organization_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Event line not found")
    return row


def _event_line_primary_client_id(row) -> str | None:
    if not row or not row["primary_client_id"]:
        return None
    value = str(row["primary_client_id"]).strip()
    return value or None


def _event_line_primary_client_name(row) -> str | None:
    if not row or not row["primary_client_name"]:
        return None
    value = str(row["primary_client_name"]).strip()
    return value or None


def _client_row_by_id(state: AppState, client_id: str | None, organization_id: str | None = None):
    normalized = (client_id or "").strip()
    if not normalized:
        return None
    if organization_id:
        return state.db.fetchone(
            "SELECT * FROM clients WHERE id = ? AND organization_id = ?",
            (normalized, organization_id),
        )
    return state.db.fetchone("SELECT * FROM clients WHERE id = ?", (normalized,))


def _client_summary_record(row) -> ClientSummaryRecord:
    return ClientSummaryRecord(
        id=str(row["id"]),
        name=str(row["name"]),
        alias=str(row["alias"]) if row["alias"] else None,
    )


def _event_line_record(state: AppState, row) -> EventLineRecord:
    owner_name = None
    if row["owner_id"]:
        owner_row = state.db.fetchone("SELECT full_name FROM employee_accounts WHERE id = ?", (str(row["owner_id"]),))
        owner_name = str(owner_row["full_name"]) if owner_row else None
    department_name = None
    if row["primary_department_id"]:
        department_row = state.db.fetchone("SELECT name FROM org_departments WHERE id = ?", (str(row["primary_department_id"]),))
        department_name = str(department_row["name"]) if department_row else None
    activity_count = int(state.db.scalar("SELECT COUNT(1) FROM event_line_activities WHERE event_line_id = ?", (str(row["id"]),)) or 0)
    client_row = _client_row_by_id(state, _event_line_primary_client_id(row), str(row["organization_id"]))
    primary_client_name = _event_line_primary_client_name(row) or (str(client_row["name"]) if client_row and client_row["name"] else None)
    return EventLineRecord(
        id=str(row["id"]),
        name=str(row["name"]),
        kind=str(row["kind"] or "custom"),
        status=str(row["status"] or "active"),
        visibilityScope=str(row["visibility_scope"]) if row["visibility_scope"] else "project_public",
        businessCategory=str(row["business_category"]) if row["business_category"] else None,
        stage=str(row["stage"]) if row["stage"] else None,
        summary=str(row["summary"]) if row["summary"] else None,
        intent=str(row["intent"]) if row["intent"] else None,
        currentBlocker=str(row["current_blocker"]) if row["current_blocker"] else None,
        recentDecision=str(row["recent_decision"]) if row["recent_decision"] else None,
        nextStep=str(row["next_step"]) if row["next_step"] else None,
        evidenceCount=max(int(row["evidence_count"] or 0), activity_count),
        ownerId=str(row["owner_id"]) if row["owner_id"] else None,
        ownerName=owner_name,
        primaryClientId=_event_line_primary_client_id(row),
        primaryClientName=primary_client_name,
        primaryDepartmentId=str(row["primary_department_id"]) if row["primary_department_id"] else None,
        primaryDepartmentName=department_name,
        participantIds=[str(item) for item in from_json(row["participant_ids_json"], []) if str(item)],
        closedAt=str(row["closed_at"]) if row["closed_at"] else None,
        closedByUserId=str(row["closed_by_user_id"]) if row["closed_by_user_id"] else None,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _event_line_activity_record(state: AppState, row) -> EventLineActivityRecord:
    actor_name = None
    if row["actor_id"]:
        actor_row = state.db.fetchone("SELECT full_name FROM employee_accounts WHERE id = ?", (str(row["actor_id"]),))
        actor_name = str(actor_row["full_name"]) if actor_row else None
    metadata = from_json(row["metadata_json"], {})
    return EventLineActivityRecord(
        id=str(row["id"]),
        eventLineId=str(row["event_line_id"]),
        sourceType=str(row["source_type"]),
        sourceId=str(row["source_id"]),
        happenedAt=str(row["happened_at"]),
        actorId=str(row["actor_id"]) if row["actor_id"] else None,
        actorName=actor_name,
        title=str(row["title"]),
        summary=str(row["summary"]),
        metadata=metadata if isinstance(metadata, dict) else {},
    )


def _record_event_line_activity(
    state: AppState,
    event_line_id: str | None,
    source_type: str,
    source_id: str,
    actor_id: str | None,
    title: str,
    summary: str,
    metadata: dict[str, object] | None = None,
) -> None:
    if not event_line_id:
        return
    state.db.execute(
        """
        INSERT INTO event_line_activities(
            id, event_line_id, source_type, source_id, happened_at, actor_id, title, summary, metadata_json
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id("ela"),
            event_line_id,
            source_type,
            source_id,
            now_iso(),
            actor_id,
            title,
            summary,
            to_json(metadata or {}),
        ),
    )


def _first_nonempty_text(*values: object) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _contains_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _infer_action_os_business_category(
    *,
    title: str = "",
    desc: str = "",
    source_type: str | None = None,
    event_line_name: str | None = None,
) -> str:
    normalized = " ".join(
        part.strip()
        for part in [title, desc, event_line_name or "", source_type or ""]
        if part and part.strip()
    )
    if not normalized:
        return "专项推进"
    if _contains_any_keyword(normalized, ("模板", "标准", "手册", "知识库", "沉淀", "资料库", "归档")):
        return "产品化沉淀"
    if _contains_any_keyword(normalized, ("审批", "复核", "确认", "对齐", "同步", "协同", "会签", "回收")):
        return "组织协同"
    if _contains_any_keyword(normalized, ("流程", "机制", "规则", "自动汇总", "制度", "治理")):
        return "管理机制"
    if _contains_any_keyword(normalized, ("合作", "拜访", "约见", "介绍", "方案", "报价", "基金会", "客户", "赋能")):
        return "业务扩展"
    if _contains_any_keyword(normalized, ("交付", "上线", "实施", "演示", "需求", "开发", "系统", "网站", "官网")):
        return "项目推进"
    if _contains_any_keyword(normalized, ("伙伴", "联盟", "开源", "外部", "生态")):
        return "外部合作"
    return "专项推进"


def _resolve_cloud_task_action_os_fields(
    *,
    title: str,
    desc: str,
    source_type: str | None,
    business_category: str | None,
    current_blocker: str | None,
    next_action: str | None,
    recent_decision: str | None,
    evidence_count: int | None,
    event_line_row=None,
) -> tuple[str | None, str | None, str | None, str | None, int]:
    event_line_name = _first_nonempty_text(str(event_line_row["name"]) if event_line_row and event_line_row["name"] else None)
    event_line_business_category = _first_nonempty_text(str(event_line_row["business_category"]) if event_line_row and event_line_row["business_category"] else None)
    event_line_current_blocker = _first_nonempty_text(str(event_line_row["current_blocker"]) if event_line_row and event_line_row["current_blocker"] else None)
    event_line_recent_decision = _first_nonempty_text(str(event_line_row["recent_decision"]) if event_line_row and event_line_row["recent_decision"] else None)
    event_line_next_step = _first_nonempty_text(str(event_line_row["next_step"]) if event_line_row and event_line_row["next_step"] else None)
    event_line_evidence_count = int(event_line_row["evidence_count"] or 0) if event_line_row is not None else 0
    resolved_business_category = _first_nonempty_text(
        business_category,
        event_line_business_category,
        _infer_action_os_business_category(
            title=title,
            desc=desc,
            source_type=source_type,
            event_line_name=event_line_name,
        ),
    )
    resolved_current_blocker = _first_nonempty_text(current_blocker, event_line_current_blocker)
    resolved_next_action = _first_nonempty_text(next_action, event_line_next_step)
    resolved_recent_decision = _first_nonempty_text(recent_decision, event_line_recent_decision)
    resolved_evidence_count = max(int(evidence_count or 0), event_line_evidence_count)
    return (
        resolved_business_category,
        resolved_current_blocker,
        resolved_next_action,
        resolved_recent_decision,
        resolved_evidence_count,
    )


def _event_line_detail_record(state: AppState, row, viewer_id: str | None = None) -> EventLineDetailRecord:
    event_line = _event_line_record(state, row)
    task_rows = state.db.fetchall(
        """
        SELECT DISTINCT t.*
        FROM tasks t
        LEFT JOIN task_collaborators tc ON tc.task_id = t.id
        WHERE t.event_line_id = ?
          AND (t.creator_id = ? OR tc.user_id = ?)
        ORDER BY t.updated_at DESC
        """,
        (event_line.id, viewer_id or "", viewer_id or ""),
    )
    activity_rows = state.db.fetchall(
        """
        SELECT *
        FROM event_line_activities
        WHERE event_line_id = ?
        ORDER BY happened_at DESC
        LIMIT 40
        """,
        (event_line.id,),
    )
    return EventLineDetailRecord(
        eventLine=event_line,
        tasks=[_task_record(state, item, viewer_id) for item in task_rows],
        activities=[_event_line_activity_record(state, item) for item in activity_rows],
    )


def _event_line_dependency_counts(state: AppState, event_line_id: str, organization_id: str) -> dict[str, int]:
    task_count = state.db.fetchone(
        "SELECT COUNT(1) AS cnt FROM tasks WHERE event_line_id = ? AND organization_id = ?",
        (event_line_id, organization_id),
    )
    activity_count = state.db.fetchone(
        """
        SELECT COUNT(1) AS cnt
        FROM event_line_activities ela
        JOIN event_lines el ON el.id = ela.event_line_id
        WHERE ela.event_line_id = ? AND el.organization_id = ?
        """,
        (event_line_id, organization_id),
    )
    try:
        attachment_count = state.db.fetchone(
            """
            SELECT COUNT(1) AS cnt
            FROM event_line_attachments
            WHERE event_line_id = ? AND organization_id = ?
            """,
            (event_line_id, organization_id),
        ) or {"cnt": 0}
    except Exception:
        attachment_count = {"cnt": 0}
    return {
        "tasks": int(task_count["cnt"] if task_count else 0),
        "activities": int(activity_count["cnt"] if activity_count else 0),
        "attachments": int(attachment_count["cnt"] if attachment_count else 0),
    }


def _get_org_model_profile(state: AppState, organization_id: str) -> OrgModelProfileRecord:
    organization = _org_profile_record(state, organization_id)
    departments = _list_org_departments(state, organization_id)
    roles = _list_org_roles(state, organization_id)
    bindings = _list_org_bindings(state, organization_id)
    reporting_lines = _list_org_reporting_lines(state, organization_id)
    task_control_rules = _list_org_task_control_rules(state, organization_id)
    role_process_templates = _list_org_role_process_templates(state, organization_id)
    focus_items = _list_org_focus_items(state, organization_id)
    department_plans = _list_org_department_plans(state, organization_id)
    plan_item_updates = [item.updatedAt for plan in department_plans for item in plan.items]
    updated_candidates = [
        organization.updatedAt,
        *(item.updatedAt for item in departments),
        *(item.updatedAt for item in roles),
        *(item.updatedAt for item in bindings),
        *(item.updatedAt for item in reporting_lines),
        *(item.updatedAt for item in task_control_rules),
        *(item.updatedAt for item in role_process_templates),
        *(item.updatedAt for item in focus_items),
        *(item.updatedAt for item in department_plans),
        *plan_item_updates,
    ]
    updated_at = max(updated_candidates) if updated_candidates else now_iso()
    return OrgModelProfileRecord(
        organization=organization,
        departments=departments,
        roles=roles,
        bindings=bindings,
        reportingLines=reporting_lines,
        taskControlRules=task_control_rules,
        roleProcessTemplates=role_process_templates,
        focusItems=focus_items,
        departmentPlans=department_plans,
        updatedAt=updated_at,
    )


def _org_binding_row_for_user(state: AppState, organization_id: str, user_id: str | None):
    if not user_id:
        return None
    return state.db.fetchone(
        """
        SELECT *
        FROM org_employee_role_bindings
        WHERE organization_id = ? AND user_id = ?
        """,
        (organization_id, user_id),
    )


def _org_role_row(state: AppState, organization_id: str, role_id: str | None):
    if not role_id:
        return None
    return state.db.fetchone(
        """
        SELECT *
        FROM org_role_templates
        WHERE organization_id = ? AND id = ?
        """,
        (organization_id, role_id),
    )


def _org_reporting_line_row(state: AppState, organization_id: str, manager_user_id: str, report_user_id: str):
    return state.db.fetchone(
        """
        SELECT *
        FROM org_reporting_lines
        WHERE organization_id = ?
          AND manager_user_id = ?
          AND report_user_id = ?
          AND active = 1
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (organization_id, manager_user_id, report_user_id),
    )


def _normalize_loose_text(value: str | None) -> str:
    if not value:
        return ""
    return "".join(char.lower() for char in str(value).strip() if not char.isspace() and char not in "-_/")


def _match_manager_user_id(state: AppState, organization_id: str, employee_id: str, manager_name: str | None) -> str | None:
    normalized_name = str(manager_name or "").strip()
    if not normalized_name:
        return None
    row = state.db.fetchone(
        """
        SELECT id
        FROM employee_accounts
        WHERE organization_id = ?
          AND account_status = 'approved'
          AND full_name = ?
        ORDER BY CASE WHEN primary_role = 'admin' THEN 0 ELSE 1 END, updated_at DESC
        LIMIT 1
        """,
        (organization_id, normalized_name),
    )
    if not row:
        return None
    manager_user_id = str(row["id"])
    return manager_user_id if manager_user_id != employee_id else None


def _match_role_template_for_employee(state: AppState, organization_id: str, account_row, department_id: str | None):
    if not department_id and str(account_row["primary_role"] or "") != "admin":
        return None
    role_rows = state.db.fetchall(
        """
        SELECT *
        FROM org_role_templates
        WHERE organization_id = ?
          AND active = 1
          AND ((department_id = ?) OR (? IS NULL AND department_id IS NULL))
        ORDER BY sort_order ASC, updated_at DESC
        """,
        (organization_id, department_id, department_id),
    )
    if not role_rows:
        return None

    is_department_lead = bool(int(account_row["is_department_lead"] or 0))
    job_title = _normalize_loose_text(str(account_row["job_title"] or ""))
    if str(account_row["primary_role"] or "") == "admin":
        manager_rows = [row for row in role_rows if _bool_value(row, "is_manager") or str(row["level"] or "") == "organization_lead"]
        return manager_rows[0] if manager_rows else role_rows[0]

    if is_department_lead:
        manager_rows = [row for row in role_rows if _bool_value(row, "is_manager") or str(row["level"] or "") == "department_lead"]
        if job_title:
            exact = [row for row in manager_rows if _normalize_loose_text(str(row["name"] or "")) == job_title]
            if exact:
                return exact[0]
        if manager_rows:
            return manager_rows[0]

    if job_title:
        exact = [row for row in role_rows if _normalize_loose_text(str(row["name"] or "")) == job_title]
        if exact:
            return exact[0]
        fuzzy = [
            row
            for row in role_rows
            if job_title in _normalize_loose_text(str(row["name"] or ""))
            or _normalize_loose_text(str(row["name"] or "")) in job_title
        ]
        if fuzzy:
            return fuzzy[0]

    member_rows = [row for row in role_rows if not _bool_value(row, "is_manager")]
    if len(member_rows) == 1:
        return member_rows[0]
    return role_rows[0] if len(role_rows) == 1 else None


def _sync_employee_org_binding_from_account(
    state: AppState,
    organization_id: str,
    employee_id: str,
    *,
    fill_missing_only: bool = False,
) -> None:
    account_row = state.db.fetchone(
        "SELECT * FROM employee_accounts WHERE id = ? AND organization_id = ?",
        (employee_id, organization_id),
    )
    if not account_row or str(account_row["account_status"] or "") != "approved":
        return

    binding_row = _org_binding_row_for_user(state, organization_id, employee_id)
    department_id = str(account_row["department_id"]) if account_row["department_id"] else None
    manager_user_id = _match_manager_user_id(
        state,
        organization_id,
        employee_id,
        str(account_row["manager_name"]) if account_row["manager_name"] else None,
    )
    matched_role_row = _match_role_template_for_employee(state, organization_id, account_row, department_id)
    existing_role_row = _org_role_row(state, organization_id, str(binding_row["primary_role_id"])) if binding_row and binding_row["primary_role_id"] else None
    if existing_role_row and department_id:
        existing_role_department = str(existing_role_row["department_id"]) if existing_role_row["department_id"] else None
        if existing_role_department != department_id:
            existing_role_row = None

    role_row = existing_role_row if fill_missing_only and existing_role_row else matched_role_row or existing_role_row
    is_manager = bool(int(account_row["is_department_lead"] or 0))
    if binding_row and _bool_value(binding_row, "is_manager"):
        is_manager = True
    if role_row and _bool_value(role_row, "is_manager"):
        is_manager = True
    if str(account_row["primary_role"] or "") == "admin":
        is_manager = True

    current_focus = str(account_row["current_focus"] or "").strip()
    if fill_missing_only and binding_row and not current_focus:
        current_focus = str(binding_row["current_focus"] or "").strip()

    project_role_labels = [str(item) for item in from_json(binding_row["project_role_labels_json"], []) if str(item).strip()] if binding_row else []
    if not project_role_labels and account_row["job_title"]:
        project_role_labels = [str(account_row["job_title"]).strip()]

    task_edit_scope = str(binding_row["task_edit_scope"] or "self") if binding_row and fill_missing_only else ("department" if is_manager else "self")
    can_approve_tasks = _bool_value(binding_row, "can_approve_tasks") if binding_row and fill_missing_only else is_manager
    can_reassign_tasks = _bool_value(binding_row, "can_reassign_tasks") if binding_row and fill_missing_only else is_manager
    can_change_deadline = _bool_value(binding_row, "can_change_deadline") if binding_row and fill_missing_only else is_manager
    if role_row:
        task_edit_scope = str(role_row["task_edit_scope"] or task_edit_scope)
        can_approve_tasks = _bool_value(role_row, "can_approve_tasks")
        can_reassign_tasks = _bool_value(role_row, "can_reassign_tasks")
        can_change_deadline = _bool_value(role_row, "can_change_deadline")

    state.db.execute(
        """
        INSERT OR REPLACE INTO org_employee_role_bindings(
            user_id, organization_id, department_id, primary_role_id, manager_user_id, is_manager,
            project_role_labels_json, current_focus, task_edit_scope, can_approve_tasks,
            can_reassign_tasks, can_change_deadline, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            employee_id,
            organization_id,
            department_id,
            str(role_row["id"]) if role_row else (str(binding_row["primary_role_id"]) if binding_row and binding_row["primary_role_id"] and fill_missing_only else None),
            manager_user_id or (str(binding_row["manager_user_id"]) if binding_row and binding_row["manager_user_id"] and fill_missing_only else None),
            1 if is_manager else 0,
            to_json(project_role_labels),
            current_focus,
            task_edit_scope,
            1 if can_approve_tasks else 0,
            1 if can_reassign_tasks else 0,
            1 if can_change_deadline else 0,
            now_iso(),
        ),
    )

    if manager_user_id:
        state.db.execute(
            """
            INSERT OR REPLACE INTO org_reporting_lines(
                id, organization_id, manager_user_id, report_user_id, line_type, approves_tasks,
                can_adjust_tasks, can_change_deadline, can_reassign_tasks, is_cross_department_approver, active, updated_at
            ) VALUES(?, ?, ?, ?, 'business', 1, 1, 1, 1, 0, 1, ?)
            """,
            (f"auto_line_{employee_id}", organization_id, manager_user_id, employee_id, now_iso()),
        )
    else:
        state.db.execute("DELETE FROM org_reporting_lines WHERE id = ?", (f"auto_line_{employee_id}",))


def _backfill_employee_org_bindings_from_accounts(state: AppState, organization_id: str) -> None:
    rows = state.db.fetchall(
        """
        SELECT id
        FROM employee_accounts
        WHERE organization_id = ? AND account_status = 'approved'
        ORDER BY created_at ASC
        """,
        (organization_id,),
    )
    for row in rows:
        _sync_employee_org_binding_from_account(state, organization_id, str(row["id"]), fill_missing_only=True)


def _first_focus_from_json(value: str | None) -> str | None:
    for item in from_json(value, []):
        text = str(item).strip()
        if text:
            return text
    return None


def _resolve_task_control_rule_for_binding(state: AppState, organization_id: str, binding_row):
    if not binding_row:
        return None
    task_edit_scope = str(binding_row["task_edit_scope"] or "self")
    control_level = {
        "organization": "organization_control",
        "department": "department_control",
        "manager": "leader_control",
    }.get(task_edit_scope)
    if not control_level:
        return None
    department_id = str(binding_row["department_id"]) if binding_row["department_id"] else None
    role_template_id = str(binding_row["primary_role_id"]) if binding_row["primary_role_id"] else None
    rows = state.db.fetchall(
        """
        SELECT *
        FROM org_task_control_rules
        WHERE organization_id = ?
          AND active = 1
          AND control_level = ?
          AND (department_id IS NULL OR department_id = ?)
          AND (role_template_id IS NULL OR role_template_id = ?)
        ORDER BY
          CASE WHEN role_template_id = ? THEN 0 WHEN role_template_id IS NULL THEN 1 ELSE 2 END,
          CASE WHEN department_id = ? THEN 0 WHEN department_id IS NULL THEN 1 ELSE 2 END,
          updated_at DESC
        """,
        (organization_id, control_level, department_id, role_template_id, role_template_id, department_id),
    )
    return rows[0] if rows else None


def _task_collaborator_ids(state: AppState, task_id: str) -> list[str]:
    return [
        str(row["user_id"])
        for row in state.db.fetchall(
            "SELECT user_id FROM task_collaborators WHERE task_id = ? ORDER BY order_index ASC",
            (task_id,),
        )
    ]


def _sync_task_org_link(state: AppState, task_row, collaborator_ids: list[str] | None = None):
    organization_id = str(task_row["organization_id"])
    owner_id = str(task_row["owner_id"]) if task_row["owner_id"] else None
    creator_id = str(task_row["creator_id"])
    binding_row = _org_binding_row_for_user(state, organization_id, owner_id) or _org_binding_row_for_user(state, organization_id, creator_id)
    role_row = _org_role_row(state, organization_id, str(binding_row["primary_role_id"]) if binding_row and binding_row["primary_role_id"] else None)
    department_id = None
    if binding_row and binding_row["department_id"]:
        department_id = str(binding_row["department_id"])
    else:
        owner_row = _get_user_or_404(state, owner_id or creator_id)
        department_id = str(owner_row["department_id"]) if owner_row["department_id"] else None
    collaborator_ids = collaborator_ids if collaborator_ids is not None else _task_collaborator_ids(state, str(task_row["id"]))
    is_cross_department = False
    if department_id:
        for collaborator_id in collaborator_ids:
            collaborator_binding = _org_binding_row_for_user(state, organization_id, collaborator_id)
            collaborator_department_id = str(collaborator_binding["department_id"]) if collaborator_binding and collaborator_binding["department_id"] else None
            if collaborator_department_id and collaborator_department_id != department_id:
                is_cross_department = True
                break
    department_row = state.db.fetchone("SELECT quarterly_focus_json FROM org_departments WHERE id = ?", (department_id,)) if department_id else None
    profile_row = state.db.fetchone("SELECT quarterly_focus_json FROM org_profiles WHERE organization_id = ?", (organization_id,))
    rule_row = _resolve_task_control_rule_for_binding(state, organization_id, binding_row)
    needs_review = bool(is_cross_department or (rule_row and int(rule_row["require_collab_confirmation"] or 0)))
    approval_state = "pending" if needs_review else "none"
    state.db.execute(
        """
        INSERT OR REPLACE INTO task_org_links(
            task_id, organization_id, department_id, role_template_id, organization_focus_key, department_focus_key,
            is_cross_department, approval_state, blocked_at_step, control_rule_id, needs_review, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(task_row["id"]),
            organization_id,
            department_id,
            str(role_row["id"]) if role_row else None,
            _first_focus_from_json(profile_row["quarterly_focus_json"]) if profile_row else None,
            _first_focus_from_json(department_row["quarterly_focus_json"]) if department_row else None,
            1 if is_cross_department else 0,
            approval_state,
            None,
            str(rule_row["id"]) if rule_row else None,
            1 if needs_review else 0,
            now_iso(),
        ),
    )
    org_link_row = state.db.fetchone("SELECT * FROM task_org_links WHERE task_id = ?", (str(task_row["id"]),))
    _sync_task_plan_link(state, task_row, org_link_row)
    return org_link_row


def _task_org_link_row(state: AppState, task_id: str):
    row = state.db.fetchone("SELECT * FROM task_org_links WHERE task_id = ?", (task_id,))
    if row:
        return row
    task_row = _task_row_or_404(state, task_id)
    return _sync_task_org_link(state, task_row)


def _is_organization_lead(state: AppState, organization_id: str, user_id: str, primary_role: str) -> bool:
    if primary_role == "admin":
        return True
    binding_row = _org_binding_row_for_user(state, organization_id, user_id)
    role_row = _org_role_row(state, organization_id, str(binding_row["primary_role_id"]) if binding_row and binding_row["primary_role_id"] else None)
    return bool(role_row and str(role_row["level"]) == "organization_lead")


def _is_task_manager(state: AppState, organization_id: str, actor_id: str, owner_id: str | None) -> bool:
    if not owner_id or actor_id == owner_id:
        return False
    owner_binding = _org_binding_row_for_user(state, organization_id, owner_id)
    if owner_binding and owner_binding["manager_user_id"] and str(owner_binding["manager_user_id"]) == actor_id:
        return True
    return bool(_org_reporting_line_row(state, organization_id, actor_id, owner_id))


def _manager_has_capability(state: AppState, organization_id: str, actor_id: str, owner_id: str | None, capability: str) -> bool:
    if not owner_id:
        return False
    line_row = _org_reporting_line_row(state, organization_id, actor_id, owner_id)
    capability_map = {
        "deadline": "can_change_deadline",
        "owner": "can_reassign_tasks",
        "content": "can_adjust_tasks",
    }
    if line_row and capability_map[capability] in line_row.keys() and int(line_row[capability_map[capability]] or 0):
        return True
    if not _is_task_manager(state, organization_id, actor_id, owner_id):
        return False
    actor_binding = _org_binding_row_for_user(state, organization_id, actor_id)
    if not actor_binding:
        return False
    if capability == "deadline":
        return bool(int(actor_binding["can_change_deadline"] or 0))
    if capability == "owner":
        return bool(int(actor_binding["can_reassign_tasks"] or 0))
    return True


def _matches_rule_actor_scope(state: AppState, actor: SessionUser, task_row, task_link_row, scope: str, capability: str) -> bool:
    organization_id = str(task_row["organization_id"])
    owner_id = str(task_row["owner_id"]) if task_row["owner_id"] else None
    if _is_organization_lead(state, organization_id, actor.id, actor.primaryRole):
        return True
    if scope == "assignee":
        return actor.id == owner_id
    if scope == "creator":
        return actor.id == str(task_row["creator_id"])
    if scope == "manager":
        return _manager_has_capability(state, organization_id, actor.id, owner_id, capability)
    if scope == "department_lead":
        actor_binding = _org_binding_row_for_user(state, organization_id, actor.id)
        actor_role = _org_role_row(state, organization_id, str(actor_binding["primary_role_id"]) if actor_binding and actor_binding["primary_role_id"] else None)
        return bool(
            actor_binding
            and task_link_row
            and actor_binding["department_id"]
            and task_link_row["department_id"]
            and str(actor_binding["department_id"]) == str(task_link_row["department_id"])
            and actor_role
            and str(actor_role["level"]) in {"department_lead", "organization_lead"}
        )
    if scope == "organization_lead":
        return False
    return False


def _assert_task_edit_permission(state: AppState, actor: SessionUser, task_row, content_changed: bool, due_date_changed: bool, owner_changed: bool) -> None:
    if actor.primaryRole == "admin":
        return
    organization_id = str(task_row["organization_id"])
    owner_id = str(task_row["owner_id"]) if task_row["owner_id"] else None
    creator_id = str(task_row["creator_id"])
    task_link_row = _task_org_link_row(state, str(task_row["id"]))
    rule_row = None
    if task_link_row and task_link_row["control_rule_id"]:
        rule_row = state.db.fetchone("SELECT * FROM org_task_control_rules WHERE id = ?", (str(task_link_row["control_rule_id"]),))
    if not rule_row:
        if content_changed and actor.id not in {creator_id, owner_id} and not _manager_has_capability(state, organization_id, actor.id, owner_id, "content"):
            raise HTTPException(status_code=403, detail="你当前没有修改该任务内容的权限")
        if due_date_changed and actor.id not in {creator_id, owner_id} and not _manager_has_capability(state, organization_id, actor.id, owner_id, "deadline"):
            raise HTTPException(status_code=403, detail="你当前没有修改该任务截止时间的权限")
        if owner_changed and actor.id not in {creator_id, owner_id} and not _manager_has_capability(state, organization_id, actor.id, owner_id, "owner"):
            raise HTTPException(status_code=403, detail="你当前没有调整该任务负责人的权限")
        return
    if content_changed and not _matches_rule_actor_scope(state, actor, task_row, task_link_row, str(rule_row["content_editable_by"] or "assignee"), "content"):
        raise HTTPException(status_code=403, detail="你当前没有修改该任务内容的权限")
    if due_date_changed and not _matches_rule_actor_scope(state, actor, task_row, task_link_row, str(rule_row["deadline_editable_by"] or "manager"), "deadline"):
        raise HTTPException(status_code=403, detail="你当前没有修改该任务截止时间的权限")
    if owner_changed and not _matches_rule_actor_scope(state, actor, task_row, task_link_row, str(rule_row["owner_editable_by"] or "manager"), "owner"):
        raise HTTPException(status_code=403, detail="你当前没有调整该任务负责人的权限")


def _can_review_task(state: AppState, actor: SessionUser, task_row, task_link_row) -> bool:
    organization_id = str(task_row["organization_id"])
    owner_id = str(task_row["owner_id"]) if task_row["owner_id"] else None
    if owner_id and owner_id == actor.id:
        return False
    if actor.primaryRole == "admin":
        return True
    if _is_organization_lead(state, organization_id, actor.id, actor.primaryRole):
        return True
    rule_row = None
    if task_link_row and task_link_row["control_rule_id"]:
        rule_row = state.db.fetchone("SELECT * FROM org_task_control_rules WHERE id = ?", (str(task_link_row["control_rule_id"]),))
    if rule_row and rule_row["default_approver_user_id"] and str(rule_row["default_approver_user_id"]) == actor.id:
        return True
    if owner_id and _manager_has_capability(state, organization_id, actor.id, owner_id, "content"):
        return True
    if task_link_row and task_link_row["department_id"]:
        actor_binding = _org_binding_row_for_user(state, organization_id, actor.id)
        actor_role = _org_role_row(state, organization_id, str(actor_binding["primary_role_id"]) if actor_binding and actor_binding["primary_role_id"] else None)
        if (
            actor_binding
            and actor_role
            and actor_binding["department_id"]
            and str(actor_binding["department_id"]) == str(task_link_row["department_id"])
            and str(actor_role["level"]) in {"department_lead", "organization_lead"}
        ):
            return True
    return False


def _ensure_org_model_seed(state: AppState) -> None:
    db = state.db
    timestamp = now_iso()
    if not db.fetchone("SELECT organization_id FROM org_profiles WHERE organization_id = ?", (DEFAULT_ORG_ID,)):
        db.execute(
            """
            INSERT INTO org_profiles(
                organization_id, annual_goal, annual_strategy_year, annual_strategy_text, quarter_plans_json,
                quarterly_focus_json, leader_user_id, management_user_ids_json, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                DEFAULT_ORG_ID,
                "围绕战略陪伴、产品化交付和组织预测性管理建立稳定闭环。",
                str(datetime.now().year),
                "围绕战略陪伴闭环、知识底座产品化和组织预测性管理，建立全年清晰节奏。",
                to_json([
                    {
                        "id": "org_seed_q1",
                        "year": str(datetime.now().year),
                        "quarter": "Q1",
                        "theme": "打稳底盘",
                        "objective": "先把组织骨架、组织 DNA 和关键流程跑通。",
                        "keyResults": ["组织骨架稳定", "组织 DNA 可调用", "关键流程可复用"],
                        "keyActions": ["完成部门起盘", "补组织资料", "固化首批流程"],
                        "majorRisks": ["基础信息缺失", "角色边界不清"],
                        "updatedAt": timestamp,
                    },
                    {
                        "id": "org_seed_q2",
                        "year": str(datetime.now().year),
                        "quarter": "Q2",
                        "theme": "战略陪伴闭环",
                        "objective": "把战略陪伴、任务落地和复盘沉淀接成闭环。",
                        "keyResults": ["客户推进更稳定", "任务闭环更顺", "周复盘开始有效"],
                        "keyActions": ["打通会议到任务", "补强客户判断", "沉淀成长信号"],
                        "majorRisks": ["跨部门协同断裂", "计划承接不足"],
                        "updatedAt": timestamp,
                    },
                    {
                        "id": "org_seed_q3",
                        "year": str(datetime.now().year),
                        "quarter": "Q3",
                        "theme": "产品化交付",
                        "objective": "把高频方法和知识资产转成稳定可复用的产品能力。",
                        "keyResults": ["关键方法被复用", "内部工具产品化", "交付更标准"],
                        "keyActions": ["整理方法卡", "补模板", "推进内部工具"],
                        "majorRisks": ["闭门造车", "脱离真实项目"],
                        "updatedAt": timestamp,
                    },
                    {
                        "id": "org_seed_q4",
                        "year": str(datetime.now().year),
                        "quarter": "Q4",
                        "theme": "组织预测性管理",
                        "objective": "建立跨部门节奏感和更稳定的组织预测机制。",
                        "keyResults": ["季度回顾更清楚", "风险前置更早", "节奏更可预测"],
                        "keyActions": ["补强季度复盘", "统一计划视角", "沉淀组织方法"],
                        "majorRisks": ["数据质量不足", "计划只停留在口头"],
                        "updatedAt": timestamp,
                    },
                ]),
                to_json(["战略陪伴闭环", "知识底座升级", "跨部门作战机制"]),
                "user_guyuan",
                to_json(["user_guyuan", "user_qinghua"]),
                timestamp,
            ),
        )

    seeded_departments = [
        ("dept_consult_strategy", "咨询策略部", "#5B7BFE", "user_qinghua", "把场景判断力沉淀成可复制的方法与方案。", ["客户判断", "方案推进", "高层决策支持"], ["dept_customer_service", "dept_tech_development"]),
        ("dept_tech_development", "科技发展部", "#F59E0B", None, "把顾问视角沉淀成可运行的产品与底层能力。", ["系统稳定性", "关键功能闭环", "内部工具产品化"], ["dept_consult_strategy", "dept_info_data"]),
        ("dept_info_data", "信息数据部", "#10B981", "user_yishuo", "把信息处理和信号识别沉淀成预测性管理引擎。", ["情报导入", "结构化分析", "管理信号"], ["dept_consult_strategy", "dept_tech_development"]),
        ("dept_customer_service", "客户服务部", "#14B8A6", "user_jianing", "把客户现场阻力转化成组织行动与交付节奏。", ["客户推进", "会后跟进", "交付协同"], ["dept_consult_strategy", "dept_tech_development"]),
    ]
    for department_id, name, color, leader_user_id, mission, quarterly_focus, collaboration_ids in seeded_departments:
        if db.fetchone("SELECT id FROM org_departments WHERE id = ?", (department_id,)):
            continue
        db.execute(
            """
            INSERT INTO org_departments(
                id, organization_id, name, color, leader_user_id, parent_department_id, mission,
                quarterly_focus_json, collaboration_department_ids_json, active, updated_at
            ) VALUES(?, ?, ?, ?, ?, NULL, ?, ?, ?, 1, ?)
            """,
            (
                department_id,
                DEFAULT_ORG_ID,
                name,
                color,
                leader_user_id,
                mission,
                to_json(quarterly_focus),
                to_json(collaboration_ids),
                timestamp,
            ),
        )

    seeded_roles = [
        ("role_org_ceo", None, "机构负责人", "organization_lead", None, 1, "定义机构季度重点与关键判断。", ["机构判断", "目标设定", "关键拍板"], ["大量日常跟单"], [], "organization", 1, 1, 1, 0),
        ("role_strategy_lead", "dept_consult_strategy", "咨询策略部负责人", "department_lead", None, 1, "统筹咨询策略部的判断、方案与推进。", ["部门判断", "方案把关", "关键客户推进"], ["长期承担细碎排版"], [], "department", 1, 1, 1, 1),
        ("role_strategy_member", "dept_consult_strategy", "咨询顾问", "employee", "role_strategy_lead", 0, "推进客户诊断、方案和判断输出。", ["客户沟通", "方案输出", "会后推进"], ["长期承担技术排查"], [], "self", 0, 0, 0, 2),
        ("role_tech_lead", "dept_tech_development", "科技发展部负责人", "department_lead", None, 1, "统筹科技发展部的产品化与技术稳定性。", ["技术判断", "系统规划", "风险把关"], ["长期承担客户会务协调"], [], "department", 1, 1, 1, 3),
        ("role_tech_member", "dept_tech_development", "产品开发", "employee", "role_tech_lead", 0, "推进系统能力落地与内部工具建设。", ["功能开发", "稳定性治理", "需求实现"], ["长期承担人工资料整理"], [], "self", 0, 0, 1, 4),
        ("role_info_lead", "dept_info_data", "信息数据部负责人", "department_lead", None, 1, "统筹信息处理、结构化分析与管理信号。", ["信息判断", "信号建模", "结构化规则"], ["长期承担客户跟单"], [], "department", 1, 1, 1, 5),
        ("role_info_member", "dept_info_data", "信息分析", "employee", "role_info_lead", 0, "沉淀结构化资料、分析模板和信号卡片。", ["信息处理", "结构化输出", "分析支持"], ["长期承担外部协调"], [], "self", 0, 0, 0, 6),
        ("role_cs_lead", "dept_customer_service", "客户服务部负责人", "department_lead", None, 1, "统筹客户推进与交付协同。", ["客户推进", "交付判断", "跨部门协同"], ["长期承担底层技术修复"], [], "department", 1, 1, 1, 7),
        ("role_cs_member", "dept_customer_service", "客户推进", "employee", "role_cs_lead", 0, "推进客户跟进、资料补齐与会后落地。", ["客户沟通", "资料整理", "会后推进"], ["长期承担架构设计"], [], "self", 0, 0, 0, 8),
    ]
    for role_id, department_id, name, level, manager_role_id, is_manager, goal, responsibilities, should_avoid, collaboration_role_ids, task_edit_scope, can_approve, can_reassign, can_change_deadline, sort_order in seeded_roles:
        if db.fetchone("SELECT id FROM org_role_templates WHERE id = ?", (role_id,)):
            continue
        db.execute(
            """
            INSERT INTO org_role_templates(
                id, organization_id, department_id, name, level, manager_role_id, is_manager, goal,
                responsibilities_json, should_avoid_json, collaboration_role_ids_json, task_edit_scope,
                can_approve_tasks, can_reassign_tasks, can_change_deadline, sort_order, active, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                role_id,
                DEFAULT_ORG_ID,
                department_id,
                name,
                level,
                manager_role_id,
                is_manager,
                goal,
                to_json(responsibilities),
                to_json(should_avoid),
                to_json(collaboration_role_ids),
                task_edit_scope,
                can_approve,
                can_reassign,
                can_change_deadline,
                sort_order,
                timestamp,
            ),
        )

    seeded_bindings = [
        ("user_guyuan", None, "role_org_ceo", None, 1, [], "机构季度重点与关键项目判断", "organization", 1, 1, 1),
        ("user_qinghua", "dept_consult_strategy", "role_strategy_lead", "user_guyuan", 1, [], "咨询策略部周计划与高价值客户推进", "department", 1, 1, 1),
        ("user_yishuo", "dept_info_data", "role_info_lead", "user_qinghua", 1, [], "信息数据部结构化分析与信号建模", "department", 1, 1, 1),
        ("user_jianing", "dept_customer_service", "role_cs_lead", "user_qinghua", 1, [], "客户服务部推进与交付协同", "department", 1, 1, 1),
        ("user_admin", None, "role_org_ceo", None, 1, [], "系统级治理与管理员支持", "organization", 1, 1, 1),
    ]
    for user_id, department_id, primary_role_id, manager_user_id, is_manager, project_labels, current_focus, task_edit_scope, can_approve, can_reassign, can_change_deadline in seeded_bindings:
        if db.fetchone("SELECT user_id FROM org_employee_role_bindings WHERE user_id = ?", (user_id,)):
            continue
        db.execute(
            """
            INSERT INTO org_employee_role_bindings(
                user_id, organization_id, department_id, primary_role_id, manager_user_id, is_manager,
                project_role_labels_json, current_focus, task_edit_scope, can_approve_tasks,
                can_reassign_tasks, can_change_deadline, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                DEFAULT_ORG_ID,
                department_id,
                primary_role_id,
                manager_user_id,
                is_manager,
                to_json(project_labels),
                current_focus,
                task_edit_scope,
                can_approve,
                can_reassign,
                can_change_deadline,
                timestamp,
            ),
        )

    seeded_org_lines = [
        ("user_guyuan", "user_qinghua", "business", 1, 1, 1, 1, 1),
        ("user_qinghua", "user_yishuo", "business", 1, 1, 1, 1, 0),
        ("user_qinghua", "user_jianing", "business", 1, 1, 1, 1, 1),
    ]
    for manager_user_id, report_user_id, line_type, approves_tasks, can_adjust_tasks, can_change_deadline, can_reassign_tasks, is_cross_department_approver in seeded_org_lines:
        if db.fetchone(
            "SELECT id FROM org_reporting_lines WHERE organization_id = ? AND manager_user_id = ? AND report_user_id = ? AND line_type = ?",
            (DEFAULT_ORG_ID, manager_user_id, report_user_id, line_type),
        ):
            continue
        db.execute(
            """
            INSERT INTO org_reporting_lines(
                id, organization_id, manager_user_id, report_user_id, line_type, approves_tasks,
                can_adjust_tasks, can_change_deadline, can_reassign_tasks, is_cross_department_approver, active, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                new_id("orgline"),
                DEFAULT_ORG_ID,
                manager_user_id,
                report_user_id,
                line_type,
                approves_tasks,
                can_adjust_tasks,
                can_change_deadline,
                can_reassign_tasks,
                is_cross_department_approver,
                timestamp,
            ),
        )

    seeded_rules = [
        ("rule_department_key", "关键部门任务", "department_control", None, None, "assignee", "manager", "manager", "manager", 1, "user_qinghua"),
        ("rule_org_key", "机构关键任务", "organization_control", None, None, "manager", "organization_lead", "organization_lead", "organization_lead", 1, "user_guyuan"),
    ]
    for rule_id, name, control_level, department_id, role_template_id, content_editable_by, deadline_editable_by, owner_editable_by, cancellable_by, require_collab_confirmation, default_approver_user_id in seeded_rules:
        if db.fetchone("SELECT id FROM org_task_control_rules WHERE id = ?", (rule_id,)):
            continue
        db.execute(
            """
            INSERT INTO org_task_control_rules(
                id, organization_id, name, control_level, department_id, role_template_id, content_editable_by,
                deadline_editable_by, owner_editable_by, cancellable_by, require_collab_confirmation,
                default_approver_user_id, active, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                rule_id,
                DEFAULT_ORG_ID,
                name,
                control_level,
                department_id,
                role_template_id,
                content_editable_by,
                deadline_editable_by,
                owner_editable_by,
                cancellable_by,
                require_collab_confirmation,
                default_approver_user_id,
                timestamp,
            ),
        )


def _ensure_seed_data(state: AppState) -> None:
    db = state.db
    timestamp = now_iso()
    if not db.fetchone("SELECT id FROM organizations WHERE id = ?", (DEFAULT_ORG_ID,)):
        db.execute(
            "INSERT INTO organizations(id, name, slug, created_at, updated_at) VALUES(?, ?, ?, ?, ?)",
            (DEFAULT_ORG_ID, "益语智库", "yiyu-thinktank", timestamp, timestamp),
        )

    people = resolve_seed_users(state.data_dir)
    for person in people:
        user_id = person.user_id
        full_name = person.full_name
        email = person.email
        primary_role = person.primary_role
        status_value = person.account_status
        department_id = person.department_id
        secret = {"password": person.password}
        existing_by_id = db.fetchone("SELECT id FROM employee_accounts WHERE id = ?", (user_id,))
        existing = existing_by_id or db.fetchone("SELECT id FROM employee_accounts WHERE email = ?", (email.lower(),))
        department = get_department_entry(department_id)
        department_name = department.name if department else None
        if not existing:
            password_hash = secret.get("password_hash")
            if not password_hash:
                password_hash = hash_password(str(secret["password"]))
            db.execute(
                """
                INSERT INTO employee_accounts(
                    id, organization_id, email, full_name, password_hash, primary_role, account_status,
                    approved_at, approved_by, rejected_reason, disabled_at, recent_mentions_json, last_login_at,
                    department_id, department_name, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, '[]', NULL, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    DEFAULT_ORG_ID,
                    email.lower(),
                    full_name,
                    password_hash,
                    primary_role,
                    status_value,
                    timestamp if status_value == "approved" else None,
                    "user_admin" if user_id != "user_admin" else "user_admin",
                    department_id,
                    department_name,
                    timestamp,
                    timestamp,
                ),
            )
            bound_user_id = user_id
        else:
            bound_user_id = str(existing["id"])
            password_hash_override = hash_password(str(secret["password"])) if person.password_locked else None
            db.execute(
                """
                UPDATE employee_accounts
                   SET password_hash = COALESCE(?, password_hash),
                       full_name = ?,
                       primary_role = ?,
                       account_status = ?,
                       approved_at = COALESCE(approved_at, ?),
                       approved_by = COALESCE(approved_by, ?),
                       department_id = ?,
                       department_name = ?,
                       updated_at = ?
                WHERE id = ?
                """,
                (
                    password_hash_override,
                    full_name,
                    primary_role,
                    status_value,
                    timestamp if status_value == "approved" else None,
                    "user_admin" if user_id != "user_admin" else "user_admin",
                    department_id,
                    department_name,
                    timestamp,
                    bound_user_id,
                ),
            )
        if not db.fetchone("SELECT id FROM employee_role_bindings WHERE user_id = ? AND role = ?", (bound_user_id, primary_role)):
            db.execute(
                "INSERT INTO employee_role_bindings(id, user_id, role, created_at) VALUES(?, ?, ?, ?)",
                (new_id("role"), bound_user_id, primary_role, timestamp),
            )

    for list_id, name, color, sort_order, is_default in [
        ("list-0", "收集箱", "#888681", 0, 1),
        ("list-1", "Q3 营销", "#5B7BFE", 1, 0),
        ("list-2", "用户体验", "#F59E0B", 2, 0),
        ("list-3", "商业化", "#10B981", 3, 0),
    ]:
        db.execute(
            """
            INSERT OR IGNORE INTO task_lists(id, organization_id, name, color, sort_order, is_default, scope, archived_at)
            VALUES(?, ?, ?, ?, ?, ?, 'org', NULL)
            """,
            (list_id, DEFAULT_ORG_ID, name, color, sort_order, is_default),
        )
    for list_id, name, color, sort_order, is_default in [
        ("plist-1", "健身", "#5B7BFE", 10, 1),
        ("plist-2", "约会", "#EC4899", 11, 0),
        ("plist-3", "吃饭", "#F59E0B", 12, 0),
        ("plist-4", "学习", "#10B981", 13, 0),
    ]:
        db.execute(
            """
            INSERT OR IGNORE INTO task_lists(id, organization_id, name, color, sort_order, is_default, scope, archived_at)
            VALUES(?, ?, ?, ?, ?, ?, 'personal', NULL)
            """,
            (list_id, DEFAULT_ORG_ID, name, color, sort_order, is_default),
        )

    for name, color in [
        ("会议", "#5B7BFE"),
        ("审核", "#F59E0B"),
        ("客户", "#10B981"),
        ("传播", "#8B5CF6"),
        ("文档", "#64748B"),
        ("复盘", "#EC4899"),
        ("紧急", "#EF4444"),
        ("跟进中", "#06B6D4"),
    ]:
        db.execute(
            """
            INSERT OR IGNORE INTO task_tag_library(
                id, organization_id, name, scope, color, owner_user_id, created_by, created_at, updated_at, archived_at
            ) VALUES(?, ?, ?, 'org', ?, '', '系统', ?, ?, NULL)
            """,
            (new_id("tag"), DEFAULT_ORG_ID, name, color, timestamp, timestamp),
        )

    for seed_user_id in ["user_admin", "user_guyuan", "user_qinghua", "user_jianing", "user_yishuo"]:
        if db.fetchone("SELECT user_id FROM task_settings WHERE user_id = ?", (seed_user_id,)):
            continue
        db.execute(
            """
            INSERT INTO task_settings(
                user_id, organization_id, default_list_id, default_priority, default_due_date_preset,
                default_view_mode, list_sort_mode, show_completed_tasks, default_review_scope,
                auto_assign_self, updated_at
            ) VALUES(?, ?, 'list-0', 'normal', 'today', 'list', 'manual', 0, 'work', 1, ?)
            """,
            (seed_user_id, DEFAULT_ORG_ID, timestamp),
        )

    for unit_id, parent_id, name, unit_type, leader_user_id in [
        ("unit_org", None, "益语智库", "organization", "user_admin"),
        ("dept_consult_strategy", "unit_org", "咨询策略部", "department", "user_qinghua"),
        ("dept_tech_development", "unit_org", "科技发展部", "department", None),
        ("dept_info_data", "unit_org", "信息数据部", "department", "user_yishuo"),
        ("dept_customer_service", "unit_org", "客户服务部", "department", "user_jianing"),
    ]:
        db.execute(
            """
            INSERT OR IGNORE INTO org_units(id, organization_id, parent_id, name, unit_type, leader_user_id, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (unit_id, DEFAULT_ORG_ID, parent_id, name, unit_type, leader_user_id, timestamp, timestamp),
        )

    for manager_user_id, report_user_id, relationship_type in [
        ("user_admin", "user_qinghua", "direct"),
        ("user_qinghua", "user_jianing", "direct"),
        ("user_qinghua", "user_yishuo", "direct"),
    ]:
        if db.fetchone(
            "SELECT id FROM reporting_lines WHERE manager_user_id = ? AND report_user_id = ? AND relationship_type = ?",
            (manager_user_id, report_user_id, relationship_type),
        ):
            continue
        db.execute(
            """
            INSERT INTO reporting_lines(id, organization_id, manager_user_id, report_user_id, relationship_type, effective_from, effective_to, created_at)
            VALUES(?, ?, ?, ?, ?, ?, NULL, ?)
            """,
            (new_id("line"), DEFAULT_ORG_ID, manager_user_id, report_user_id, relationship_type, timestamp, timestamp),
        )

    for plan_id, owner_user_id, owner_unit_id, level, title, summary, status in [
        ("plan_ceo_q2", "user_admin", "unit_org", "ceo", "Q2 组织主线", "聚焦战略陪伴闭环与知识底座升级。", "active"),
        ("plan_mgr_support", "user_qinghua", "dept_consult_strategy", "manager", "团队本周主线", "把客户推进、方案判断和任务闭环跑顺。", "active"),
    ]:
        db.execute(
            """
            INSERT OR IGNORE INTO plan_nodes(
                id, organization_id, owner_user_id, owner_unit_id, level, title, summary, status, starts_at, ends_at, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (plan_id, DEFAULT_ORG_ID, owner_user_id, owner_unit_id, level, title, summary, status, timestamp, None, timestamp, timestamp),
        )

    _ensure_org_model_seed(state)


def _log_audit(state: AppState, action: str, *, actor_user_id: str | None, target_user_id: str | None, detail: dict[str, object]) -> None:
    state.db.execute(
        "INSERT INTO auth_audit_logs(id, actor_user_id, target_user_id, action, detail_json, created_at) VALUES(?, ?, ?, ?, ?, ?)",
        (new_id("audit"), actor_user_id, target_user_id, action, to_json(detail), now_iso()),
    )


def _save_org_model_profile(state: AppState, current_user: SessionUser, payload: OrgModelProfileRecord) -> OrgModelProfileRecord:
    organization_id = current_user.organizationId
    timestamp = now_iso()
    state.db.execute(
        "UPDATE organizations SET name = ?, updated_at = ? WHERE id = ?",
        (payload.organization.name.strip() or "未命名机构", timestamp, organization_id),
    )
    state.db.execute(
        """
        INSERT OR REPLACE INTO org_profiles(
            organization_id, annual_goal, annual_strategy_year, annual_strategy_text, quarter_plans_json,
            quarterly_focus_json, leader_user_id, management_user_ids_json, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            organization_id,
            payload.organization.annualGoal.strip(),
            payload.organization.annualStrategyYear.strip(),
            payload.organization.annualStrategy.strip(),
            to_json([
                {
                    "id": plan.id,
                    "year": plan.year.strip(),
                    "quarter": plan.quarter,
                    "theme": plan.theme.strip(),
                    "objective": plan.objective.strip(),
                    "keyResults": [item.strip() for item in plan.keyResults if item.strip()],
                    "keyActions": [item.strip() for item in plan.keyActions if item.strip()],
                    "majorRisks": [item.strip() for item in plan.majorRisks if item.strip()],
                    "updatedAt": timestamp,
                }
                for plan in payload.organization.quarterPlans
            ]),
            to_json([item.strip() for item in payload.organization.quarterlyFocus if item.strip()]),
            payload.organization.leaderUserId,
            to_json([item for item in payload.organization.managementUserIds if item]),
            timestamp,
        ),
    )

    state.db.execute("DELETE FROM org_task_control_rules WHERE organization_id = ?", (organization_id,))
    state.db.execute("DELETE FROM org_role_process_templates WHERE organization_id = ?", (organization_id,))
    state.db.execute("DELETE FROM org_department_plan_items WHERE organization_id = ?", (organization_id,))
    state.db.execute("DELETE FROM org_department_plans WHERE organization_id = ?", (organization_id,))
    state.db.execute("DELETE FROM org_focus_items WHERE organization_id = ?", (organization_id,))
    state.db.execute("DELETE FROM org_reporting_lines WHERE organization_id = ?", (organization_id,))
    state.db.execute("DELETE FROM org_employee_role_bindings WHERE organization_id = ?", (organization_id,))
    state.db.execute("DELETE FROM org_role_templates WHERE organization_id = ?", (organization_id,))
    state.db.execute("DELETE FROM org_departments WHERE organization_id = ?", (organization_id,))

    for department in payload.departments:
        state.db.execute(
            """
            INSERT INTO org_departments(
                id, organization_id, name, color, leader_user_id, parent_department_id, mission,
                business_context, team_context, quarter_plan_json, quarterly_focus_json,
                collaboration_department_ids_json, active, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                department.id,
                organization_id,
                department.name.strip() or department.id,
                department.color,
                department.leaderUserId,
                department.parentDepartmentId,
                department.mission.strip(),
                department.businessContext.strip(),
                department.teamContext.strip(),
                to_json(
                    {
                        "year": department.quarterPlan.year.strip(),
                        "quarter": department.quarterPlan.quarter,
                        "objective": department.quarterPlan.objective.strip(),
                        "deliverables": [item.strip() for item in department.quarterPlan.deliverables if item.strip()],
                        "successMetrics": [item.strip() for item in department.quarterPlan.successMetrics if item.strip()],
                        "majorRisks": [item.strip() for item in department.quarterPlan.majorRisks if item.strip()],
                        "updatedAt": timestamp,
                    }
                ),
                to_json([item.strip() for item in department.quarterlyFocus if item.strip()]),
                to_json([item for item in department.collaborationDepartmentIds if item]),
                1 if department.active else 0,
                timestamp,
            ),
        )

    for role in payload.roles:
        state.db.execute(
            """
            INSERT INTO org_role_templates(
                id, organization_id, department_id, name, level, manager_role_id, is_manager, goal,
                responsibilities_json, should_avoid_json, collaboration_role_ids_json, task_edit_scope,
                can_approve_tasks, can_reassign_tasks, can_change_deadline, sort_order, active, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                role.id,
                organization_id,
                role.departmentId,
                role.name.strip() or role.id,
                role.level,
                role.managerRoleId,
                1 if role.isManager else 0,
                role.goal.strip(),
                to_json([item.strip() for item in role.responsibilities if item.strip()]),
                to_json([item.strip() for item in role.shouldAvoid if item.strip()]),
                to_json([item for item in role.collaborationRoleIds if item]),
                role.taskEditScope,
                1 if role.canApproveTasks else 0,
                1 if role.canReassignTasks else 0,
                1 if role.canChangeDeadline else 0,
                role.sortOrder,
                1 if role.active else 0,
                timestamp,
            ),
        )

    department_name_by_id = {department.id: department.name for department in payload.departments}
    for binding in payload.bindings:
        state.db.execute(
            """
            INSERT INTO org_employee_role_bindings(
                user_id, organization_id, department_id, primary_role_id, manager_user_id, is_manager,
                project_role_labels_json, current_focus, task_edit_scope, can_approve_tasks,
                can_reassign_tasks, can_change_deadline, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                binding.userId,
                organization_id,
                binding.departmentId,
                binding.primaryRoleId,
                binding.managerUserId,
                1 if binding.isManager else 0,
                to_json([item.strip() for item in binding.projectRoleLabels if item.strip()]),
                binding.currentFocus.strip(),
                binding.taskEditScope,
                1 if binding.canApproveTasks else 0,
                1 if binding.canReassignTasks else 0,
                1 if binding.canChangeDeadline else 0,
                timestamp,
            ),
        )
        state.db.execute(
            """
            UPDATE employee_accounts
               SET department_id = ?, department_name = ?, updated_at = ?
             WHERE id = ? AND organization_id = ?
            """,
            (
                binding.departmentId,
                department_name_by_id.get(binding.departmentId or "", None),
                timestamp,
                binding.userId,
                organization_id,
            ),
        )

    for line in payload.reportingLines:
        state.db.execute(
            """
            INSERT INTO org_reporting_lines(
                id, organization_id, manager_user_id, report_user_id, line_type, approves_tasks,
                can_adjust_tasks, can_change_deadline, can_reassign_tasks, is_cross_department_approver, active, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                line.id,
                organization_id,
                line.managerUserId,
                line.reportUserId,
                line.lineType,
                1 if line.approvesTasks else 0,
                1 if line.canAdjustTasks else 0,
                1 if line.canChangeDeadline else 0,
                1 if line.canReassignTasks else 0,
                1 if line.isCrossDepartmentApprover else 0,
                1 if line.active else 0,
                timestamp,
            ),
        )

    for rule in payload.taskControlRules:
        state.db.execute(
            """
            INSERT INTO org_task_control_rules(
                id, organization_id, name, control_level, department_id, role_template_id, content_editable_by,
                deadline_editable_by, owner_editable_by, cancellable_by, require_collab_confirmation,
                default_approver_user_id, active, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rule.id,
                organization_id,
                rule.name.strip() or rule.id,
                rule.controlLevel,
                rule.departmentId,
                rule.roleTemplateId,
                rule.contentEditableBy,
                rule.deadlineEditableBy,
                rule.ownerEditableBy,
                rule.cancellableBy,
                1 if rule.requireCollabConfirmation else 0,
                rule.defaultApproverUserId,
                1 if rule.active else 0,
                timestamp,
            ),
        )

    for template in payload.roleProcessTemplates:
        state.db.execute(
            """
            INSERT INTO org_role_process_templates(
                id, organization_id, role_template_id, name, trigger_type, trigger_condition, key_steps_json,
                collaboration_step, approval_step, output_artifact, common_blockers_json, active, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                template.id,
                organization_id,
                template.roleTemplateId,
                template.name.strip() or template.id,
                template.triggerType,
                template.triggerCondition.strip(),
                to_json([item.strip() for item in template.keySteps if item.strip()]),
                template.collaborationStep.strip(),
                template.approvalStep.strip(),
                template.outputArtifact.strip(),
                to_json([item.strip() for item in template.commonBlockers if item.strip()]),
                1 if template.active else 0,
                timestamp,
            ),
        )

    for focus_item in payload.focusItems:
        state.db.execute(
            """
            INSERT INTO org_focus_items(
                id, organization_id, period_key, title, statement, owner_user_id, priority, status, evidence_keywords_json, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                focus_item.id,
                organization_id,
                focus_item.periodKey.strip(),
                focus_item.title.strip() or focus_item.id,
                focus_item.statement.strip(),
                focus_item.ownerUserId,
                focus_item.priority,
                focus_item.status,
                to_json([item.strip() for item in focus_item.evidenceKeywords if item.strip()]),
                timestamp,
            ),
        )

    for plan in payload.departmentPlans:
        state.db.execute(
            """
            INSERT INTO org_department_plans(
                id, organization_id, department_id, week_label, owner_user_id, summary, major_risks_json, dependencies_json, status, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan.id,
                organization_id,
                plan.departmentId,
                plan.weekLabel.strip(),
                plan.ownerUserId,
                plan.summary.strip(),
                to_json([item.strip() for item in plan.majorRisks if item.strip()]),
                to_json([item.strip() for item in plan.dependencies if item.strip()]),
                plan.status,
                timestamp,
            ),
        )
        for item in plan.items:
            state.db.execute(
                """
                INSERT INTO org_department_plan_items(
                    id, organization_id, plan_id, focus_item_id, title, statement, owner_user_id, status, expected_output, sort_order, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    organization_id,
                    plan.id,
                    item.focusItemId,
                    item.title.strip() or item.id,
                    item.statement.strip(),
                    item.ownerUserId,
                    item.status,
                    item.expectedOutput.strip(),
                    item.sortOrder,
                    timestamp,
                ),
            )

    _backfill_employee_org_bindings_from_accounts(state, organization_id)
    _log_audit(
        state,
        "save_org_model_profile",
        actor_user_id=current_user.id,
        target_user_id=None,
        detail={
            "departmentCount": len(payload.departments),
            "roleCount": len(payload.roles),
            "bindingCount": len(payload.bindings),
            "reportingLineCount": len(payload.reportingLines),
            "taskControlRuleCount": len(payload.taskControlRules),
            "roleProcessTemplateCount": len(payload.roleProcessTemplates),
            "focusItemCount": len(payload.focusItems),
            "departmentPlanCount": len(payload.departmentPlans),
        },
    )
    _backfill_task_org_links(state, organization_id)
    return _get_org_model_profile(state, organization_id)


def _get_user_or_404(state: AppState, user_id: str):
    row = state.db.fetchone("SELECT * FROM employee_accounts WHERE id = ?", (user_id,))
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return row


def _require_auth(app: FastAPI, authorization: str | None = Header(default=None)) -> SessionUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_access_token(_state(app).secret_key, token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    user_row = _state(app).db.fetchone("SELECT * FROM employee_accounts WHERE id = ?", (payload["sub"],))
    if not user_row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if str(user_row["account_status"]) != "approved":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not approved")
    return _row_user(user_row)


def _require_admin(app: FastAPI, authorization: str | None = Header(default=None)) -> SessionUser:
    user = _require_auth(app, authorization)
    if user.primaryRole not in ALLOWED_APPROVER_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin permissions required")
    return user


def _render_feishu_relay_callback_page(title: str, detail: str, *, success: bool) -> HTMLResponse:
    tone = "#16a34a" if success else "#dc2626"
    badge = "授权结果已回传" if success else "授权失败"
    escaped_title = html.escape(title)
    escaped_detail = html.escape(detail)
    markup = f"""<!doctype html>
<html lang=\"zh-CN\">
  <head>
    <meta charset=\"utf-8\" />
    <title>{escaped_title}</title>
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <style>
      body {{ font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Helvetica Neue', sans-serif; background: #f8fafc; color: #0f172a; margin: 0; padding: 32px; }}
      .card {{ max-width: 560px; margin: 8vh auto; background: #fff; border: 1px solid #e2e8f0; border-radius: 24px; padding: 28px; box-shadow: 0 16px 48px rgba(15, 23, 42, 0.08); }}
      .badge {{ display: inline-flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 700; color: {tone}; background: rgba(91, 123, 254, 0.08); border-radius: 999px; padding: 6px 12px; }}
      h1 {{ font-size: 24px; line-height: 1.3; margin: 18px 0 12px; }}
      p {{ font-size: 14px; line-height: 1.75; color: #475569; margin: 0 0 12px; white-space: pre-wrap; }}
    </style>
  </head>
  <body>
    <div class=\"card\">
      <div class=\"badge\">{badge}</div>
      <h1>{escaped_title}</h1>
      <p>{escaped_detail}</p>
      <p>现在可以回到桌面工作台；工作台会自动刷新飞书绑定状态。</p>
    </div>
  </body>
</html>"""
    return HTMLResponse(markup)


def _feishu_relay_session_status(row) -> Literal["pending", "authorized", "expired", "error"]:
    if row is None:
        return "error"
    expires_at_raw = str(row["expires_at"] or "")
    try:
        if expires_at_raw and datetime.fromisoformat(expires_at_raw) <= datetime.now():
            return "expired"
    except ValueError:
        return "error"
    if row["error_message"]:
        return "error"
    if row["code"]:
        return "authorized"
    return "pending"


def _feishu_relay_status_record(row, *, include_code: bool = False) -> FeishuBindingRelaySessionStatusRecord:
    return FeishuBindingRelaySessionStatusRecord(
        state=str(row["state_token"]),
        status=_feishu_relay_session_status(row),
        expiresAt=str(row["expires_at"]),
        authorizedAt=str(row["authorized_at"]) if row["authorized_at"] else None,
        errorMessage=str(row["error_message"]) if row["error_message"] else None,
        code=str(row["code"]) if include_code and row["code"] else None,
    )


def _collaborators_for_task(state: AppState, task_id: str) -> list[TaskCollaboratorRecord]:
    rows = state.db.fetchall(
        """
        SELECT tc.*, u.full_name, u.email, u.primary_role
        FROM task_collaborators tc
        JOIN employee_accounts u ON u.id = tc.user_id
        WHERE tc.task_id = ?
        ORDER BY tc.order_index ASC
        """,
        (task_id,),
    )
    return [
        TaskCollaboratorRecord(
            userId=str(row["user_id"]),
            fullName=str(row["full_name"]),
            email=str(row["email"]),
            orderIndex=int(row["order_index"]),
            isOwner=bool(row["is_owner"]),
            inboxStatus=str(row["inbox_status"]),
            returnReason=row["return_reason"],
            handledAt=row["handled_at"],
        )
        for row in rows
    ]


def _collaboration_summary(collaborators: list[TaskCollaboratorRecord]) -> dict[str, int]:
    summary = {"pending": 0, "accepted": 0, "returned": 0}
    for item in collaborators:
        summary[item.inboxStatus] += 1
    return summary


def _parse_date_only(value: str | None) -> datetime.date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _week_bounds(week_label: str) -> tuple[datetime.date, datetime.date] | None:
    parts = week_label.strip().split("-W")
    if len(parts) != 2:
        return None
    try:
        year = int(parts[0])
        week = int(parts[1])
        start = datetime.fromisocalendar(year, week, 1).date()
    except ValueError:
        return None
    return start, start + timedelta(days=6)


def _is_due_date_overdue_by_day(value: str | None, today: datetime.date | None = None) -> bool:
    due_date = _parse_date_only(value)
    if not due_date:
        return False
    reference_date = today or datetime.now().date()
    return due_date < reference_date


def _task_tag_record(row) -> TaskTagRecord:
    return TaskTagRecord(
        id=str(row["id"]),
        name=str(row["name"]),
        color=str(row["color"] or ("#9CA3AF" if str(row["scope"]) == "self" else "#5B7BFE")),
        scope=str(row["scope"]),
        ownerUserId=str(row["owner_user_id"]) if str(row["owner_user_id"]) else None,
        createdBy=str(row["created_by"]) if str(row["created_by"]) else None,
        updatedAt=str(row["updated_at"] or row["created_at"]),
        archivedAt=str(row["archived_at"]) if row["archived_at"] else None,
    )


def _task_list_record(row) -> TaskListRecord:
    return TaskListRecord(
        id=str(row["id"]),
        name=str(row["name"]),
        color=str(row["color"]),
        sortOrder=int(row["sort_order"] or 0),
        isDefault=bool(int(row["is_default"] or 0)),
        scope=str(row["scope"] or "org"),
        archivedAt=str(row["archived_at"]) if row["archived_at"] else None,
    )


def _default_list_id(state: AppState, organization_id: str) -> str | None:
    row = state.db.fetchone(
        "SELECT id FROM task_lists WHERE organization_id = ? AND is_default = 1 ORDER BY sort_order ASC LIMIT 1",
        (organization_id,),
    )
    if row:
        return str(row["id"])
    row = state.db.fetchone(
        "SELECT id FROM task_lists WHERE organization_id = ? AND (archived_at IS NULL OR archived_at = '') ORDER BY sort_order ASC LIMIT 1",
        (organization_id,),
    )
    return str(row["id"]) if row else None


def _default_task_settings(state: AppState, current_user: SessionUser) -> TaskSettingsRecord:
    return TaskSettingsRecord(
        defaultListId=_default_list_id(state, current_user.organizationId),
        defaultPriority="normal",
        defaultDueDatePreset="today",
        defaultViewMode="list",
        listSortMode="manual",
        showCompletedTasks=False,
        defaultReviewScope="work",
        autoAssignSelf=True,
        updatedAt=now_iso(),
    )


def _task_settings_record(state: AppState, current_user: SessionUser, row) -> TaskSettingsRecord:
    defaults = _default_task_settings(state, current_user)
    return TaskSettingsRecord(
        defaultListId=str(row["default_list_id"]) if row["default_list_id"] else defaults.defaultListId,
        defaultPriority=str(row["default_priority"] or defaults.defaultPriority),  # type: ignore[arg-type]
        defaultDueDatePreset=str(row["default_due_date_preset"] or defaults.defaultDueDatePreset),  # type: ignore[arg-type]
        defaultViewMode=str(row["default_view_mode"] or defaults.defaultViewMode),  # type: ignore[arg-type]
        listSortMode=str(row["list_sort_mode"] or defaults.listSortMode),  # type: ignore[arg-type]
        showCompletedTasks=bool(int(row["show_completed_tasks"] or 0)),
        defaultReviewScope=str(row["default_review_scope"] or defaults.defaultReviewScope),  # type: ignore[arg-type]
        autoAssignSelf=bool(int(row["auto_assign_self"] if row["auto_assign_self"] is not None else 1)),
        updatedAt=str(row["updated_at"] or defaults.updatedAt),
    )


def _get_task_settings(state: AppState, current_user: SessionUser) -> TaskSettingsRecord:
    row = state.db.fetchone(
        "SELECT * FROM task_settings WHERE user_id = ?",
        (current_user.id,),
    )
    if row:
        return _task_settings_record(state, current_user, row)
    defaults = _default_task_settings(state, current_user)
    state.db.execute(
        """
        INSERT OR REPLACE INTO task_settings(
            user_id, organization_id, default_list_id, default_priority, default_due_date_preset,
            default_view_mode, list_sort_mode, show_completed_tasks, default_review_scope,
            auto_assign_self, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            current_user.id,
            current_user.organizationId,
            defaults.defaultListId,
            defaults.defaultPriority,
            defaults.defaultDueDatePreset,
            defaults.defaultViewMode,
            defaults.listSortMode,
            1 if defaults.showCompletedTasks else 0,
            defaults.defaultReviewScope,
            1 if defaults.autoAssignSelf else 0,
            defaults.updatedAt,
        ),
    )
    return defaults


def _visible_task_tags(state: AppState, current_user: SessionUser) -> list[TaskTagRecord]:
    rows = state.db.fetchall(
        """
        SELECT *
        FROM task_tag_library
        WHERE organization_id = ?
          AND (scope = 'org' OR owner_user_id = ?)
        ORDER BY CASE WHEN archived_at IS NULL OR archived_at = '' THEN 0 ELSE 1 END,
                 CASE scope WHEN 'org' THEN 0 ELSE 1 END,
                 name COLLATE NOCASE ASC
        """,
        (current_user.organizationId, current_user.id),
    )
    return [_task_tag_record(row) for row in rows]


def _tag_rows_by_ids(state: AppState, tag_ids: list[str]) -> list:
    if not tag_ids:
        return []
    rows = state.db.fetchall(
        f"SELECT * FROM task_tag_library WHERE id IN ({_sql_placeholders(tag_ids)})",
        tuple(tag_ids),
    )
    by_id = {str(row["id"]): row for row in rows}
    return [by_id[tag_id] for tag_id in tag_ids if tag_id in by_id]


def _ensure_task_tag(
    state: AppState,
    current_user: SessionUser,
    name: str,
    scope: str = "org",
    color: str | None = None,
) -> TaskTagRecord:
    trimmed = name.strip()
    if not trimmed:
        raise HTTPException(status_code=400, detail="Tag name is required")
    owner_user_id = current_user.id if scope == "self" else ""
    resolved_color = color or ("#9CA3AF" if scope == "self" else "#5B7BFE")
    existing = state.db.fetchone(
        "SELECT * FROM task_tag_library WHERE organization_id = ? AND scope = ? AND owner_user_id = ? AND name = ?",
        (current_user.organizationId, scope, owner_user_id, trimmed),
    )
    timestamp = now_iso()
    if existing:
        if not str(existing["updated_at"]) or not str(existing["color"] or ""):
            state.db.execute(
                """
                UPDATE task_tag_library
                SET updated_at = ?, color = COALESCE(NULLIF(color, ''), ?), created_by = COALESCE(NULLIF(created_by, ''), ?)
                WHERE id = ?
                """,
                (timestamp, resolved_color, current_user.fullName, str(existing["id"])),
            )
            existing = state.db.fetchone("SELECT * FROM task_tag_library WHERE id = ?", (str(existing["id"]),))
        assert existing is not None
        return _task_tag_record(existing)
    tag_id = new_id("tag")
    state.db.execute(
        """
        INSERT INTO task_tag_library(id, organization_id, name, scope, color, owner_user_id, created_by, created_at, updated_at, archived_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
        """,
        (tag_id, current_user.organizationId, trimmed, scope, resolved_color, owner_user_id, current_user.fullName, timestamp, timestamp),
    )
    row = state.db.fetchone("SELECT * FROM task_tag_library WHERE id = ?", (tag_id,))
    assert row is not None
    return _task_tag_record(row)


def _resolve_task_tags(state: AppState, current_user: SessionUser, tag_ids: list[str], legacy_names: list[str]) -> list[TaskTagRecord]:
    rows = _tag_rows_by_ids(state, tag_ids)
    if rows:
        return [_task_tag_record(row) for row in rows]
    if not legacy_names:
        return []
    return [_ensure_task_tag(state, current_user, name, "org") for name in legacy_names if name.strip()]


def _event_line_snapshot_context(state: AppState, event_line_id: str | None, fallback_name: str | None = None) -> WeeklyReviewEventLineContextRecord | None:
    resolved_id = (event_line_id or "").strip()
    resolved_name = (fallback_name or "").strip()
    if not resolved_id and not resolved_name:
        return None
    row = None
    if resolved_id:
        row = state.db.fetchone("SELECT * FROM event_lines WHERE id = ?", (resolved_id,))
    if not row and resolved_name:
        return WeeklyReviewEventLineContextRecord(name=resolved_name)
    if not row:
        return None
    activity_count = int(state.db.scalar("SELECT COUNT(1) FROM event_line_activities WHERE event_line_id = ?", (str(row["id"]),)) or 0)
    return WeeklyReviewEventLineContextRecord(
        id=str(row["id"]),
        name=str(row["name"] or ""),
        businessCategory=str(row["business_category"] or "") or None,
        stage=str(row["stage"] or "") or None,
        summary=str(row["summary"] or "") or None,
        intent=str(row["intent"] or "") or None,
        currentBlocker=str(row["current_blocker"] or "") or None,
        recentDecision=str(row["recent_decision"] or "") or None,
        nextStep=str(row["next_step"] or "") or None,
        evidenceCount=max(int(row["evidence_count"] or 0), activity_count),
        primaryClientId=str(row["primary_client_id"] or "") or None,
        primaryClientName=str(row["primary_client_name"] or "") or None,
    )


def _task_snapshot_from_record(state: AppState, task: TaskRecord) -> WeeklyReviewTaskSnapshotRecord:
    return WeeklyReviewTaskSnapshotRecord(
        title=task.title,
        status=task.progressStatus if task.viewerInboxStatus != "pending" else "inbox",
        dueDate=task.dueDate,
        createdAt=task.createdAt,
        completionNote=task.completionNote,
        tags=task.tags,
        listName=task.listName,
        listColor=task.listColor,
        ownerId=task.ownerId,
        ownerName=task.ownerName,
        clientId=task.clientId,
        clientName=task.clientName,
        eventLineId=task.eventLineId,
        eventLineName=task.eventLineName,
        eventLineContext=_event_line_snapshot_context(state, task.eventLineId, task.eventLineName),
        orgContext=task.orgContext,
    )


def _is_private_task(task: TaskRecord) -> bool:
    return task.scopeMode == "PERSONAL_ONLY" or any(tag.scope == "self" for tag in task.tags)


def _task_attachment_record(row) -> TaskAttachmentRecord:
    return TaskAttachmentRecord(
        id=str(row["id"]),
        taskId=str(row["task_id"]),
        clientId=str(row["client_id"]) if row["client_id"] else None,
        eventLineId=str(row["event_line_id"]) if row["event_line_id"] else None,
        title=str(row["title"]),
        summary=str(row["summary"]) if row["summary"] else None,
        path=str(row["path"]),
        kind=str(row["kind"]),
        source=str(row["source"]),
        mimeType=str(row["mime_type"]) if row["mime_type"] else None,
        sizeBytes=int(row["size_bytes"] or 0),
        durationSeconds=int(row["duration_seconds"] or 0),
        createdAt=str(row["created_at"]),
    )


def _task_attachment_row_or_404(state: AppState, attachment_id: str, task_id: str, organization_id: str):
    row = state.db.fetchone(
        """
        SELECT *
        FROM task_attachments
        WHERE id = ? AND task_id = ? AND organization_id = ?
        """,
        (attachment_id, task_id, organization_id),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Task attachment not found")
    return row


def _task_attachments_for_task(state: AppState, task_id: str) -> list[TaskAttachmentRecord]:
    rows = state.db.fetchall(
        """
        SELECT *
        FROM task_attachments
        WHERE task_id = ?
        ORDER BY created_at DESC
        """,
        (task_id,),
    )
    return [_task_attachment_record(row) for row in rows]


def _task_note_text(state: AppState, task_id: str) -> str | None:
    note_row = state.db.fetchone("SELECT note FROM task_notes WHERE task_id = ?", (task_id,))
    return str(note_row["note"]) if note_row and note_row["note"] else None


def _task_record(state: AppState, row, viewer_id: str | None = None) -> TaskRecord:
    creator = _get_user_or_404(state, str(row["creator_id"]))
    owner = _get_user_or_404(state, str(row["owner_id"])) if row["owner_id"] else None
    list_row = state.db.fetchone("SELECT name, color FROM task_lists WHERE id = ?", (str(row["list_id"]),))
    collaborators = _collaborators_for_task(state, str(row["id"]))
    attachments = _task_attachments_for_task(state, str(row["id"]))
    viewer_status = next((item.inboxStatus for item in collaborators if item.userId == viewer_id), None)
    org_link_row = _task_org_link_row(state, str(row["id"]))
    task_plan_link_row = _task_plan_link_row(state, str(row["id"]))
    rule_row = None
    if org_link_row and org_link_row["control_rule_id"]:
        rule_row = state.db.fetchone(
            "SELECT control_level FROM org_task_control_rules WHERE id = ?",
            (str(org_link_row["control_rule_id"]),),
        )
    org_context = None
    event_line_name = None
    event_line_row = None
    if org_link_row:
        org_context = TaskOrgContextRecord(
            departmentId=str(org_link_row["department_id"]) if org_link_row["department_id"] else None,
            roleTemplateId=str(org_link_row["role_template_id"]) if org_link_row["role_template_id"] else None,
            controlRuleId=str(org_link_row["control_rule_id"]) if org_link_row["control_rule_id"] else None,
            controlLevel=str(rule_row["control_level"]) if rule_row and rule_row["control_level"] else "normal",
            organizationFocusKey=str(org_link_row["organization_focus_key"]) if org_link_row["organization_focus_key"] else None,
            departmentFocusKey=str(org_link_row["department_focus_key"]) if org_link_row["department_focus_key"] else None,
            focusItemId=str(task_plan_link_row["focus_item_id"]) if task_plan_link_row and task_plan_link_row["focus_item_id"] else None,
            departmentPlanItemId=str(task_plan_link_row["department_plan_item_id"]) if task_plan_link_row and task_plan_link_row["department_plan_item_id"] else None,
            isCrossDepartment=bool(int(org_link_row["is_cross_department"] or 0)),
            approvalState=str(org_link_row["approval_state"]) if org_link_row["approval_state"] else None,
            blockedAtStep=str(org_link_row["blocked_at_step"]) if org_link_row["blocked_at_step"] else None,
            needsReview=bool(int(org_link_row["needs_review"] or 0)),
        )
    if row["event_line_id"]:
        event_line_row = state.db.fetchone("SELECT * FROM event_lines WHERE id = ?", (str(row["event_line_id"]),))
        event_line_name = str(event_line_row["name"]) if event_line_row else None
    client_row = _client_row_by_id(state, str(row["client_id"]) if row["client_id"] else None, str(row["organization_id"]))
    client_name = (
        (str(client_row["name"]) if client_row and client_row["name"] else None)
        or (
            _event_line_primary_client_name(event_line_row)
            if event_line_row and _event_line_primary_client_id(event_line_row) == str(row["client_id"]).strip()
            else None
        )
    )
    (
        business_category,
        current_blocker,
        next_action,
        recent_decision,
        evidence_count,
    ) = _resolve_cloud_task_action_os_fields(
        title=str(row["title"]),
        desc=str(row["description"]),
        source_type=str(row["source_type"]),
        business_category=str(row["business_category"]) if row["business_category"] else None,
        current_blocker=str(row["current_blocker"]) if row["current_blocker"] else None,
        next_action=str(row["next_action"]) if row["next_action"] else None,
        recent_decision=str(row["recent_decision"]) if row["recent_decision"] else None,
        evidence_count=max(int(row["evidence_count"] or 0), len(attachments)),
        event_line_row=event_line_row,
    )
    return TaskRecord(
        id=str(row["id"]),
        title=str(row["title"]),
        description=str(row["description"]),
        creatorId=str(row["creator_id"]),
        creatorName=str(creator["full_name"]),
        listName=str(list_row["name"]) if list_row else "收集箱",
        listColor=str(list_row["color"]) if list_row else "#888681",
        ownerId=str(row["owner_id"]) if row["owner_id"] else None,
        ownerName=str(owner["full_name"]) if owner else None,
        dueDate=row["due_date"],
        durationMinutes=int(row["duration_minutes"] or 60),
        scopeMode=str(row["scope_mode"] or "COLLAB_SHARED"),
        clientId=str(row["client_id"]) if row["client_id"] else None,
        clientName=client_name,
        eventLineId=str(row["event_line_id"]) if row["event_line_id"] else None,
        eventLineName=event_line_name,
        projectModuleId=str(row["project_module_id"]) if row["project_module_id"] else None,
        projectFlowId=str(row["project_flow_id"]) if row["project_flow_id"] else None,
        priority=str(row["priority"]),
        listId=str(row["list_id"]),
        progressStatus=str(row["progress_status"]),
        sourceType=str(row["source_type"]),
        sourceId=row["source_id"],
        businessCategory=business_category,
        currentBlocker=current_blocker,
        nextAction=next_action,
        recentDecision=recent_decision,
        completionNote=str(row["completion_note"]) if row["completion_note"] else None,
        note=_task_note_text(state, str(row["id"])),
        evidenceCount=max(evidence_count, len(attachments)),
        tags=[_task_tag_record(tr) for tr in _tag_rows_by_ids(state, [str(i) for i in from_json(row["tag_ids_json"], []) if i])] if row["tag_ids_json"] else [],
        attachments=attachments,
        collaborators=collaborators,
        collaborationSummary=_collaboration_summary(collaborators),
        viewerInboxStatus=viewer_status,
        orgContext=org_context,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _task_row_or_404(state: AppState, task_id: str):
    row = state.db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    return row


def _normalize_task_tags(state: AppState, current_user: SessionUser, tag_ids: list[str] | None, legacy_names: list[str] | None) -> list[TaskTagRecord]:
    resolved: list[TaskTagRecord] = []
    seen_ids: set[str] = set()
    if tag_ids:
        for row in _tag_rows_by_ids(state, [item for item in tag_ids if item]):
            tag = _task_tag_record(row)
            if tag.id in seen_ids:
                continue
            seen_ids.add(tag.id)
            resolved.append(tag)
    for name in legacy_names or []:
        if not name.strip():
            continue
        tag = _ensure_task_tag(state, current_user, name, "org")
        if tag.id in seen_ids:
            continue
        seen_ids.add(tag.id)
        resolved.append(tag)
    return resolved


def _sync_tasks_for_tag_change(state: AppState, tag_id: str) -> None:
    tag_row = state.db.fetchone("SELECT * FROM task_tag_library WHERE id = ?", (tag_id,))
    task_rows = state.db.fetchall("SELECT id, tag_ids_json FROM tasks")
    for row in task_rows:
        tag_ids = [str(item) for item in from_json(row["tag_ids_json"], [])] if isinstance(from_json(row["tag_ids_json"], []), list) else []
        if tag_id not in tag_ids:
            continue
        next_tag_ids = tag_ids if tag_row else [item for item in tag_ids if item != tag_id]
        resolved = [_task_tag_record(item) for item in _tag_rows_by_ids(state, next_tag_ids)]
        state.db.execute(
            "UPDATE tasks SET tag_ids_json = ?, tags_json = ?, updated_at = ? WHERE id = ?",
            (to_json([item.id for item in resolved]), to_json([item.name for item in resolved]), now_iso(), str(row["id"])),
        )


def _record_activity(state: AppState, task_id: str, actor_id: str, event_type: str, payload: dict[str, object]) -> None:
    state.db.execute(
        "INSERT INTO task_activity_events(id, task_id, actor_id, event_type, payload_json, created_at) VALUES(?, ?, ?, ?, ?, ?)",
        (new_id("tae"), task_id, actor_id, event_type, to_json(payload), now_iso()),
    )


def _refresh_recent_mentions(state: AppState, actor_id: str) -> None:
    rows = state.db.fetchall(
        """
        SELECT mentioned_user_id
        FROM mention_history
        WHERE actor_id = ?
        ORDER BY use_count DESC, last_mentioned_at DESC
        LIMIT 5
        """,
        (actor_id,),
    )
    recent_ids = [str(row["mentioned_user_id"]) for row in rows]
    state.db.execute(
        "UPDATE employee_accounts SET recent_mentions_json = ?, updated_at = ? WHERE id = ?",
        (to_json(recent_ids), now_iso(), actor_id),
    )


def _bump_mentions(state: AppState, actor_id: str, collaborator_ids: list[str]) -> None:
    timestamp = now_iso()
    for mentioned_user_id in collaborator_ids:
        row = state.db.fetchone(
            "SELECT use_count FROM mention_history WHERE actor_id = ? AND mentioned_user_id = ?",
            (actor_id, mentioned_user_id),
        )
        if row:
            state.db.execute(
                "UPDATE mention_history SET use_count = ?, last_mentioned_at = ? WHERE actor_id = ? AND mentioned_user_id = ?",
                (int(row["use_count"]) + 1, timestamp, actor_id, mentioned_user_id),
            )
        else:
            state.db.execute(
                "INSERT INTO mention_history(actor_id, mentioned_user_id, use_count, last_mentioned_at) VALUES(?, ?, 1, ?)",
                (actor_id, mentioned_user_id, timestamp),
            )
    _refresh_recent_mentions(state, actor_id)


def _current_week_label() -> str:
    today = datetime.now()
    iso = today.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _approved_user_name(state: AppState, user_id: str | None) -> str | None:
    if not user_id:
        return None
    row = state.db.fetchone("SELECT full_name FROM employee_accounts WHERE id = ?", (user_id,))
    return str(row["full_name"]) if row else None


def _plan_nodes(state: AppState, organization_id: str) -> list[PlanNodeRecord]:
    rows = state.db.fetchall(
        "SELECT * FROM plan_nodes WHERE organization_id = ? ORDER BY CASE level WHEN 'ceo' THEN 0 WHEN 'director' THEN 1 WHEN 'manager' THEN 2 ELSE 3 END, created_at DESC",
        (organization_id,),
    )
    return [
        PlanNodeRecord(
            id=str(row["id"]),
            level=str(row["level"]),
            title=str(row["title"]),
            summary=str(row["summary"]),
            status=str(row["status"]),
            ownerUserId=str(row["owner_user_id"]) if row["owner_user_id"] else None,
            ownerName=_approved_user_name(state, str(row["owner_user_id"])) if row["owner_user_id"] else None,
            ownerUnitId=str(row["owner_unit_id"]) if row["owner_unit_id"] else None,
            startsAt=row["starts_at"],
            endsAt=row["ends_at"],
        )
        for row in rows
    ]


def _direct_report_rows(state: AppState, manager_id: str) -> list:
    return state.db.fetchall(
        """
        SELECT u.*
        FROM reporting_lines rl
        JOIN employee_accounts u ON u.id = rl.report_user_id
        WHERE rl.manager_user_id = ?
          AND rl.effective_to IS NULL
          AND u.account_status = 'approved'
        ORDER BY u.full_name COLLATE NOCASE ASC
        """,
        (manager_id,),
    )


def _task_metrics_for_user(state: AppState, user_id: str) -> dict[str, int]:
    today = datetime.now().date()
    task_rows = state.db.fetchall(
        """
        SELECT DISTINCT t.id, t.progress_status, t.due_date
        FROM tasks t
        LEFT JOIN task_collaborators tc ON tc.task_id = t.id
        WHERE t.creator_id = ? OR t.owner_id = ? OR tc.user_id = ?
        """,
        (user_id, user_id, user_id),
    )
    pending_collab = state.db.scalar(
        "SELECT COUNT(1) AS count FROM task_collaborators WHERE user_id = ? AND inbox_status = 'pending'",
        (user_id,),
    )
    returned_collab = state.db.scalar(
        "SELECT COUNT(1) AS count FROM task_collaborators WHERE user_id = ? AND inbox_status = 'returned'",
        (user_id,),
    )
    metrics = {
        "taskCount": len(task_rows),
        "doneCount": 0,
        "activeCount": 0,
        "overdueCount": 0,
        "pendingInboxCount": int(pending_collab),
        "returnedCount": int(returned_collab),
    }
    for row in task_rows:
        status_value = str(row["progress_status"])
        if status_value == "done":
            metrics["doneCount"] += 1
        else:
            metrics["activeCount"] += 1
            if _is_due_date_overdue_by_day(str(row["due_date"]) if row["due_date"] else None, today):
                metrics["overdueCount"] += 1
    return metrics


def _supportive_growth_suggestions(text: str) -> list[str]:
    if not text.strip():
        return []
    suggestions: list[str] = []
    lowered = text.lower()
    if any(keyword in text for keyword in ["焦虑", "压力", "疲惫", "累"]) or "stress" in lowered:
        suggestions.append("给自己留一个 20 分钟的整理窗口，先把最重要的一件事排到最前。")
    if any(keyword in text for keyword in ["不清楚", "迷茫", "混乱"]) or "unclear" in lowered:
        suggestions.append("把本周最想确认的一条方向写成一句问题，下周优先找人确认。")
    if any(keyword in text for keyword in ["成长", "学习", "提升", "能力"]) or "learn" in lowered:
        suggestions.append("挑一个最影响当前工作的能力点，拆成可在一周内完成的小练习。")
    if not suggestions:
        suggestions.append("先保留一条对自己最重要的观察，下周只追踪这一条变化。")
    return suggestions[:3]


def _build_review_entry_record(state: AppState, row) -> WeeklyReviewEntryRecord:
    user_row = _get_user_or_404(state, str(row["user_id"]))
    return WeeklyReviewEntryRecord(
        id=str(row["id"]),
        userId=str(row["user_id"]),
        userName=str(user_row["full_name"]),
        weekLabel=str(row["week_label"]),
        workProgress=str(row["work_progress"]),
        workBlocker=str(row["work_blocker"]),
        blockerType=str(row["blocker_type"]),
        workDirection=str(row["work_direction"]),
        nextWeekFocus=str(row["next_week_focus"]),
        supportNeeded=str(row["support_needed"]),
        relatedPlanIds=[str(item) for item in from_json(row["related_plan_ids_json"], [])] if isinstance(from_json(row["related_plan_ids_json"], []), list) else [],
        workFreeNote=str(row["work_free_note"]),
        personalGrowthNote=str(row["personal_growth_note"]),
        personalPrivateNote=str(row["personal_private_note"]),
        personalVisibility="self",
        submittedAt=str(row["submitted_at"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _review_row_for_user_week(state: AppState, user_id: str, week_label: str):
    return state.db.fetchone(
        "SELECT * FROM weekly_review_entries WHERE user_id = ? AND week_label = ? ORDER BY submitted_at DESC LIMIT 1",
        (user_id, week_label),
    )


def _review_history_for_user(state: AppState, user_id: str) -> ReviewHistoryResponse:
    rows = state.db.fetchall(
        """
        SELECT
            r.week_label,
            COALESCE(r.submitted_at, r.updated_at, r.created_at) AS submitted_at,
            (
                SELECT COUNT(*)
                FROM weekly_review_task_entries e
                WHERE e.review_id = r.id AND e.content_domain = 'work'
            ) AS work_item_count,
            (
                SELECT COUNT(*)
                FROM weekly_review_task_entries e
                WHERE e.review_id = r.id AND e.content_domain = 'personal'
            ) AS personal_item_count
        FROM weekly_review_entries r
        WHERE r.user_id = ?
        ORDER BY COALESCE(r.submitted_at, r.updated_at, r.created_at) DESC, r.week_label DESC
        """,
        (user_id,),
    )
    return ReviewHistoryResponse(
        items=[
            ReviewHistoryEntryRecord(
                weekLabel=str(row["week_label"] or ""),
                submittedAt=str(row["submitted_at"] or ""),
                workItemCount=int(row["work_item_count"] or 0),
                personalItemCount=int(row["personal_item_count"] or 0),
            )
            for row in rows
            if str(row["week_label"] or "").strip()
        ]
    )


def _visible_tasks_for_user(state: AppState, current_user: SessionUser) -> list[TaskRecord]:
    rows = state.db.fetchall(
        """
        SELECT DISTINCT t.*
        FROM tasks t
        LEFT JOIN task_collaborators tc ON tc.task_id = t.id
        WHERE t.organization_id = ?
          AND (t.creator_id = ? OR tc.user_id = ?)
        ORDER BY t.updated_at DESC
        """,
        (current_user.organizationId, current_user.id, current_user.id),
    )
    return [_task_record(state, row, current_user.id) for row in rows]


def _task_in_week(task: TaskRecord, week_label: str) -> bool:
    bounds = _week_bounds(week_label)
    if not bounds:
        return False
    review_date = _parse_date_only(task.dueDate) or _parse_date_only(task.createdAt)
    if not review_date:
        return False
    start, end = bounds
    return start <= review_date <= end


def _weekly_review_task_entry_from_row(row) -> WeeklyReviewTaskEntryRecord:
    snapshot = from_json(str(row["task_snapshot_json"]), {})
    if not isinstance(snapshot, dict):
        snapshot = {}
    structured_note_raw = from_json(str(row["structured_note_json"] or "{}"), {})
    if isinstance(structured_note_raw, WeeklyReviewTaskStructuredNoteRecord):
        structured_note = structured_note_raw
    elif isinstance(structured_note_raw, dict):
        structured_note = WeeklyReviewTaskStructuredNoteRecord(
            reflection=str(
                structured_note_raw.get("reflection")
                or structured_note_raw.get("successExperience")
                or structured_note_raw.get("supportNeeded")
                or structured_note_raw.get("failureInsight")
                or structured_note_raw.get("blockerReason")
                or structured_note_raw.get("progress")
                or structured_note_raw.get("nextAction")
                or structured_note_raw.get("successReason")
                or ""
            ).strip(),
            lightweightTag=str(structured_note_raw.get("lightweightTag") or "").strip(),  # type: ignore[arg-type]
            planCommitment=str(structured_note_raw.get("planCommitment") or "").strip(),
            progress=str(structured_note_raw.get("progress") or "").strip(),
            completionStatus=str(structured_note_raw.get("completionStatus") or "in_progress").strip(),  # type: ignore[arg-type]
            departmentPlanId=str(structured_note_raw.get("departmentPlanId")).strip() if structured_note_raw.get("departmentPlanId") else None,
            departmentPlanAlignment=str(structured_note_raw.get("departmentPlanAlignment") or "unknown").strip(),  # type: ignore[arg-type]
            organizationPlanId=str(structured_note_raw.get("organizationPlanId")).strip() if structured_note_raw.get("organizationPlanId") else None,
            organizationPlanAlignment=str(structured_note_raw.get("organizationPlanAlignment") or "unknown").strip(),  # type: ignore[arg-type]
            successReason=str(structured_note_raw.get("successReason") or "").strip(),
            successExperience=str(structured_note_raw.get("successExperience") or "").strip(),
            blockerReason=str(structured_note_raw.get("blockerReason") or "").strip(),
            failureInsight=str(structured_note_raw.get("failureInsight") or "").strip(),
            supportNeeded=str(structured_note_raw.get("supportNeeded") or "").strip(),
            nextAction=str(structured_note_raw.get("nextAction") or "").strip(),
        )
    else:
        structured_note = WeeklyReviewTaskStructuredNoteRecord()
    return WeeklyReviewTaskEntryRecord(
        id=str(row["id"]),
        reviewId=str(row["review_id"]),
        taskId=str(row["task_id"]),
        weekLabel=str(row["week_label"]),
        contentDomain=str(row["content_domain"]),
        note=str(row["note"]),
        structuredNote=structured_note,
        reviewedAt=str(row["reviewed_at"]),
        taskSnapshot=WeeklyReviewTaskSnapshotRecord(**snapshot),
    )


def _coerce_review_structured_note_payload(value: object) -> WeeklyReviewTaskStructuredNoteRecord:
    parsed = value
    if isinstance(value, str):
        parsed = from_json(value, {})
    if isinstance(parsed, WeeklyReviewTaskStructuredNoteRecord):
        return parsed
    if isinstance(parsed, dict):
        return WeeklyReviewTaskStructuredNoteRecord(
            reflection=str(
                parsed.get("reflection")
                or parsed.get("successExperience")
                or parsed.get("supportNeeded")
                or parsed.get("failureInsight")
                or parsed.get("blockerReason")
                or parsed.get("progress")
                or parsed.get("nextAction")
                or parsed.get("successReason")
                or ""
            ).strip(),
            lightweightTag=str(parsed.get("lightweightTag") or "").strip(),  # type: ignore[arg-type]
            planCommitment=str(parsed.get("planCommitment") or "").strip(),
            progress=str(parsed.get("progress") or "").strip(),
            completionStatus=str(parsed.get("completionStatus") or "in_progress").strip(),  # type: ignore[arg-type]
            departmentPlanId=str(parsed.get("departmentPlanId")).strip() if parsed.get("departmentPlanId") else None,
            departmentPlanAlignment=str(parsed.get("departmentPlanAlignment") or "unknown").strip(),  # type: ignore[arg-type]
            organizationPlanId=str(parsed.get("organizationPlanId")).strip() if parsed.get("organizationPlanId") else None,
            organizationPlanAlignment=str(parsed.get("organizationPlanAlignment") or "unknown").strip(),  # type: ignore[arg-type]
            successReason=str(parsed.get("successReason") or "").strip(),
            successExperience=str(parsed.get("successExperience") or "").strip(),
            blockerReason=str(parsed.get("blockerReason") or "").strip(),
            failureInsight=str(parsed.get("failureInsight") or "").strip(),
            supportNeeded=str(parsed.get("supportNeeded") or "").strip(),
            nextAction=str(parsed.get("nextAction") or "").strip(),
        )
    return WeeklyReviewTaskStructuredNoteRecord()


def _compose_review_note(structured_note: WeeklyReviewTaskStructuredNoteRecord, fallback_note: str) -> str:
    if structured_note.reflection.strip():
        if structured_note.completionStatus in {"done_on_time", "done_late"}:
            return f"任务完成心得：{structured_note.reflection.strip()}"
        if structured_note.lightweightTag:
            return f"需要支持 / 思考：{structured_note.reflection.strip()}（当前卡点：{structured_note.lightweightTag}）"
        return f"需要支持 / 思考：{structured_note.reflection.strip()}"
    if structured_note.lightweightTag and structured_note.completionStatus not in {"done_on_time", "done_late"}:
        return f"需要支持 / 思考：{structured_note.lightweightTag}"
    has_meaningful_content = any(
        [
            structured_note.reflection.strip(),
            structured_note.lightweightTag,
            structured_note.planCommitment.strip(),
            structured_note.progress.strip(),
            (structured_note.departmentPlanId or "").strip(),
            (structured_note.organizationPlanId or "").strip(),
            structured_note.successReason.strip(),
            structured_note.successExperience.strip(),
            structured_note.blockerReason.strip(),
            structured_note.failureInsight.strip(),
            structured_note.supportNeeded.strip(),
            structured_note.nextAction.strip(),
            structured_note.completionStatus != "in_progress",
            structured_note.departmentPlanAlignment != "unknown",
            structured_note.organizationPlanAlignment != "unknown",
        ]
    )
    completion_label = {
        "done_on_time": "按时完成",
        "done_late": "延迟完成",
        "in_progress": "仍在推进",
        "not_done": "未完成",
    }.get(structured_note.completionStatus, "")
    alignment_label = {
        "aligned": "明确对齐",
        "partial": "部分对齐",
        "misaligned": "存在偏离",
        "unknown": "待补录",
    }
    parts = [
        f"本周计划：{structured_note.planCommitment}" if structured_note.planCommitment else "",
        f"本周推进：{structured_note.progress}" if structured_note.progress else "",
        f"计划状态：{completion_label}" if completion_label and has_meaningful_content else "",
        f"部门计划对齐：{alignment_label.get(structured_note.departmentPlanAlignment, '待补录')}" if structured_note.departmentPlanId or structured_note.departmentPlanAlignment != "unknown" else "",
        f"机构战略对齐：{alignment_label.get(structured_note.organizationPlanAlignment, '待补录')}" if structured_note.organizationPlanId or structured_note.organizationPlanAlignment != "unknown" else "",
        f"成功原因：{structured_note.successReason}" if structured_note.successReason else "",
        f"成功经验：{structured_note.successExperience}" if structured_note.successExperience else "",
        f"阻碍原因：{structured_note.blockerReason}" if structured_note.blockerReason else "",
        f"失败心得：{structured_note.failureInsight}" if structured_note.failureInsight else "",
        f"支持需求：{structured_note.supportNeeded}" if structured_note.supportNeeded else "",
        f"下周动作：{structured_note.nextAction}" if structured_note.nextAction else "",
    ]
    return "\n".join(part for part in parts if part) or fallback_note.strip()


def _dashboard_review_items(state: AppState, current_user: SessionUser, week_label: str, review_row) -> tuple[list[WeeklyReviewTaskEntryRecord], list[WeeklyReviewTaskEntryRecord]]:
    visible_tasks = [task for task in _visible_tasks_for_user(state, current_user) if _task_in_week(task, week_label)]
    entry_rows = state.db.fetchall(
        """
        SELECT *
        FROM weekly_review_task_entries
        WHERE user_id = ? AND week_label = ?
        ORDER BY reviewed_at DESC
        """,
        (current_user.id, week_label),
    )
    entries_by_task = {str(row["task_id"]): row for row in entry_rows}
    work_items: list[WeeklyReviewTaskEntryRecord] = []
    personal_items: list[WeeklyReviewTaskEntryRecord] = []
    for task in visible_tasks:
        stored = entries_by_task.get(task.id)
        note = str(stored["note"]) if stored else ""
        reviewed_at = str(stored["reviewed_at"]) if stored else None
        snapshot = from_json(str(stored["task_snapshot_json"]), {}) if stored else _task_snapshot_from_record(state, task).model_dump()
        if not isinstance(snapshot, dict):
            snapshot = _task_snapshot_from_record(state, task).model_dump()
        item = WeeklyReviewTaskEntryRecord(
            id=str(stored["id"]) if stored else f"draft_{task.id}_{week_label}",
            reviewId=str(review_row["id"]) if review_row else None,
            taskId=task.id,
            weekLabel=week_label,
            contentDomain="personal" if _is_private_task(task) else "work",
            note=note,
            structuredNote=(
                _weekly_review_task_entry_from_row(stored).structuredNote
                if stored
                else WeeklyReviewTaskStructuredNoteRecord()
            ),
            reviewedAt=reviewed_at,
            taskSnapshot=WeeklyReviewTaskSnapshotRecord(**snapshot),
        )
        if item.contentDomain == "personal":
            personal_items.append(item)
        else:
            work_items.append(item)
    return work_items, personal_items


def _note_theme_counts(items: list[WeeklyReviewTaskEntryRecord]) -> dict[str, int]:
    problem_keywords = ("卡住", "阻力", "困难", "问题", "不清", "风险", "不足")
    harvest_keywords = ("收获", "学到", "发现", "更清楚", "有效")
    support_keywords = ("需要支持", "需要帮助", "需要资源", "协同")
    return {
        "problem": sum(
            1
            for item in items
            if item.structuredNote.lightweightTag.strip()
            or item.structuredNote.blockerReason.strip()
            or item.structuredNote.failureInsight.strip()
            or any(keyword in item.note for keyword in problem_keywords)
        ),
        "harvest": sum(
            1
            for item in items
            if item.structuredNote.reflection.strip()
            or item.structuredNote.successReason.strip()
            or item.structuredNote.successExperience.strip()
            or any(keyword in item.note for keyword in harvest_keywords)
        ),
        "support": sum(
            1
            for item in items
            if item.structuredNote.lightweightTag.strip()
            or item.structuredNote.supportNeeded.strip()
            or any(keyword in item.note for keyword in support_keywords)
        ),
    }


def _build_signal_payload(state: AppState, current_user: SessionUser, review_row, work_items: list[WeeklyReviewTaskEntryRecord]) -> dict[str, object]:
    metrics = _task_metrics_for_user(state, current_user.id)
    theme_counts = _note_theme_counts(work_items)
    reviewed_count = len(work_items)
    completed_count = sum(1 for item in work_items if item.taskSnapshot.status == "done")
    unfinished_count = reviewed_count - completed_count
    focus_areas = []
    if theme_counts["problem"]:
        focus_areas.append("问题与阻力暴露较多")
    if theme_counts["harvest"]:
        focus_areas.append("有效经验值得沉淀")
    if theme_counts["support"]:
        focus_areas.append("存在支持与协同需求")
    if not focus_areas:
        focus_areas = ["本周复盘仍偏少，先补齐任务说明"]
    suggested_actions = []
    if unfinished_count > 0:
        suggested_actions.append("优先把未完成任务的阻力写清楚，再决定下周动作。")
    if theme_counts["support"]:
        suggested_actions.append("把支持请求改写成明确对象、资源和时间点。")
    if theme_counts["harvest"]:
        suggested_actions.append("把本周有效做法沉淀成团队可复用的方法。")
    return {
        "headline": f"{current_user.fullName}本周任务复盘已整理完成。",
        "metrics": {
            **metrics,
            "reviewedCount": reviewed_count,
            "completedReviewedCount": completed_count,
            "unfinishedReviewedCount": unfinished_count,
        },
        "focusAreas": focus_areas[:3],
        "suggestedActions": suggested_actions[:3],
        "contentDomain": "work",
        "visibilityScope": "team",
    }


def _upsert_signal_card(state: AppState, current_user: SessionUser, review_row, work_items: list[WeeklyReviewTaskEntryRecord]) -> ManagementSignalCardRecord:
    payload = _build_signal_payload(state, current_user, review_row, work_items)
    existing = state.db.fetchone(
        "SELECT id FROM management_signal_cards WHERE review_id = ? AND user_id = ? AND week_label = ?",
        (str(review_row["id"]), current_user.id, str(review_row["week_label"])),
    )
    timestamp = now_iso()
    if existing:
        signal_id = str(existing["id"])
        state.db.execute("UPDATE management_signal_cards SET signal_json = ?, updated_at = ? WHERE id = ?", (to_json(payload), timestamp, signal_id))
    else:
        signal_id = new_id("signal")
        state.db.execute(
            """
            INSERT INTO management_signal_cards(
                id, organization_id, review_id, user_id, week_label, content_domain, visibility_scope,
                eligible_for_aggregation, eligible_for_manager_retrieval, signal_json, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, 'work', 'team', 1, 1, ?, ?, ?)
            """,
            (signal_id, str(review_row["organization_id"]), str(review_row["id"]), current_user.id, str(review_row["week_label"]), to_json(payload), timestamp, timestamp),
        )
    return ManagementSignalCardRecord(
        id=signal_id,
        reviewId=str(review_row["id"]),
        userId=current_user.id,
        userName=current_user.fullName,
        weekLabel=str(review_row["week_label"]),
        contentDomain="work",
        visibilityScope="team",
        eligibleForAggregation=True,
        eligibleForManagerRetrieval=True,
        signals=payload,
        createdAt=timestamp,
        updatedAt=timestamp,
    )


def _upsert_personal_growth_card(state: AppState, current_user: SessionUser, review_row, personal_items: list[WeeklyReviewTaskEntryRecord]) -> PersonalGrowthCardRecord:
    text = "\n".join(item.note.strip() for item in personal_items if item.note.strip())
    if not text.strip():
        legacy_growth = str(review_row["personal_growth_note"] or "").strip()
        legacy_private = str(review_row["personal_private_note"] or "").strip()
        text = legacy_growth or legacy_private
    summary = text if text else "本周还没有填写个人成长复盘。"
    suggestions = _supportive_growth_suggestions(text)
    existing = state.db.fetchone(
        "SELECT id FROM personal_growth_cards WHERE review_id = ? AND user_id = ?",
        (str(review_row["id"]), current_user.id),
    )
    timestamp = now_iso()
    if existing:
        card_id = str(existing["id"])
        state.db.execute("UPDATE personal_growth_cards SET summary_json = ?, suggestions_json = ?, updated_at = ? WHERE id = ?", (to_json({"summary": summary}), to_json(suggestions), timestamp, card_id))
    else:
        card_id = new_id("growth")
        state.db.execute(
            """
            INSERT INTO personal_growth_cards(
                id, organization_id, review_id, user_id, content_domain, visibility_scope,
                eligible_for_aggregation, eligible_for_manager_retrieval, summary_json, suggestions_json, created_at, updated_at
            ) VALUES(?, ?, ?, ?, 'personal', 'self', 0, 0, ?, ?, ?, ?)
            """,
            (card_id, str(review_row["organization_id"]), str(review_row["id"]), current_user.id, to_json({"summary": summary}), to_json(suggestions), timestamp, timestamp),
        )
    return PersonalGrowthCardRecord(
        id=card_id,
        reviewId=str(review_row["id"]),
        userId=current_user.id,
        contentDomain="personal",
        visibilityScope="self",
        summary=summary,
        suggestions=suggestions,
        createdAt=timestamp,
        updatedAt=timestamp,
    )


def _upsert_weekly_review_sections(
    state: AppState,
    review_id: str,
    work_items: list[WeeklyReviewTaskEntryRecord],
    personal_items: list[WeeklyReviewTaskEntryRecord],
) -> None:
    state.db.execute("DELETE FROM weekly_review_sections WHERE review_id = ?", (review_id,))
    timestamp = now_iso()
    sections = [
        ("work", "\n".join(f"{item.taskSnapshot.title}：{item.note}" for item in work_items if item.note.strip()), "work", "team"),
        ("personal_growth", "\n".join(f"{item.taskSnapshot.title}：{item.note}" for item in personal_items if item.note.strip()), "personal", "self"),
    ]
    state.db.executemany(
        """
        INSERT INTO weekly_review_sections(id, review_id, section_type, content, content_domain, visibility_scope, created_at)
        VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (new_id("section"), review_id, section_type, content, domain, visibility, timestamp)
            for section_type, content, domain, visibility in sections
            if content.strip()
        ],
    )


def _report_from_row(state: AppState, row) -> HierarchyReportRecord:
    actions = [
        ReportActionCardRecord(
            id=str(item["id"]),
            actionType=str(item["action_type"]),
            title=str(item["title"]),
            payload=from_json(item["payload_json"], {}) if isinstance(from_json(item["payload_json"], {}), dict) else {},
            status=str(item["status"]),
            createdAt=str(item["created_at"]),
        )
        for item in state.db.fetchall("SELECT * FROM report_action_cards WHERE report_id = ? ORDER BY created_at ASC", (str(row["id"]),))
    ]
    summary = from_json(str(row["summary_json"]), {})
    source_policy = from_json(str(row["source_policy_json"]), {})
    return HierarchyReportRecord(
        id=str(row["id"]),
        scopeType=str(row["scope_type"]),
        scopeRefId=str(row["scope_ref_id"]),
        weekLabel=str(row["week_label"]),
        logicMode=str(row["logic_mode"]),
        headline=str(summary.get("headline", "")),
        summary=str(summary.get("summary", "")),
        focusAreas=[str(item) for item in summary.get("focusAreas", [])] if isinstance(summary.get("focusAreas", []), list) else [],
        supportSignals=[str(item) for item in summary.get("supportSignals", [])] if isinstance(summary.get("supportSignals", []), list) else [],
        suggestedActions=[str(item) for item in summary.get("suggestedActions", [])] if isinstance(summary.get("suggestedActions", []), list) else [],
        anonymousInsights=[str(item) for item in summary.get("anonymousInsights", [])] if isinstance(summary.get("anonymousInsights", []), list) else [],
        sourcePolicy=source_policy if isinstance(source_policy, dict) else {},
        actions=actions,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _upsert_hierarchy_report(
    state: AppState,
    *,
    organization_id: str,
    scope_type: str,
    scope_ref_id: str,
    week_label: str,
    summary: dict[str, object],
    actions: list[dict[str, object]],
) -> HierarchyReportRecord:
    existing = state.db.fetchone(
        "SELECT id FROM aggregated_scope_reports WHERE scope_type = ? AND scope_ref_id = ? AND week_label = ? AND logic_mode = 'hierarchy_view_v1'",
        (scope_type, scope_ref_id, week_label),
    )
    timestamp = now_iso()
    source_policy = {
        "excludedDomains": ["personal", "private", "self_only"],
        "allowedDomain": "work",
        "audience": scope_type,
    }
    if existing:
        report_id = str(existing["id"])
        state.db.execute(
            """
            UPDATE aggregated_scope_reports
            SET summary_json = ?, source_policy_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (to_json(summary), to_json(source_policy), timestamp, report_id),
        )
        state.db.execute("DELETE FROM report_action_cards WHERE report_id = ?", (report_id,))
    else:
        report_id = new_id("report")
        state.db.execute(
            """
            INSERT INTO aggregated_scope_reports(
                id, organization_id, scope_type, scope_ref_id, week_label, logic_mode, summary_json, source_policy_json, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, 'hierarchy_view_v1', ?, ?, ?, ?)
            """,
            (report_id, organization_id, scope_type, scope_ref_id, week_label, to_json(summary), to_json(source_policy), timestamp, timestamp),
        )
    state.db.executemany(
        """
        INSERT INTO report_action_cards(id, report_id, action_type, title, payload_json, status, created_at)
        VALUES(?, ?, ?, ?, ?, 'suggested', ?)
        """,
        [
            (new_id("action"), report_id, str(item["actionType"]), str(item["title"]), to_json(item.get("payload", {})), timestamp)
            for item in actions
        ],
    )
    row = state.db.fetchone("SELECT * FROM aggregated_scope_reports WHERE id = ?", (report_id,))
    assert row is not None
    return _report_from_row(state, row)


def _team_report_for_manager(state: AppState, manager_user: SessionUser, week_label: str) -> HierarchyReportRecord | None:
    reports = _direct_report_rows(state, manager_user.id)
    if not reports:
        return None
    report_ids = [str(row["id"]) for row in reports]
    placeholders = _sql_placeholders(report_ids)
    entry_rows = state.db.fetchall(
        f"""
        SELECT * FROM weekly_review_task_entries
        WHERE user_id IN ({placeholders}) AND week_label = ? AND content_domain = 'work'
        ORDER BY reviewed_at DESC
        """,
        (*report_ids, week_label),
    )
    if entry_rows:
        items = [_weekly_review_task_entry_from_row(row) for row in entry_rows]
        completed_count = sum(1 for item in items if item.taskSnapshot.status == "done")
        theme_counts = _note_theme_counts(items)
        insights = [f"有成员提到「{item.note[:18]}」这类一线问题。" for item in items if item.note.strip()][:3]
        summary = {
            "headline": "团队工作域信号已完成聚合。",
            "summary": f"本周纳入 {len(items)} 条任务复盘，其中已完成 {completed_count} 条，未完成 {len(items) - completed_count} 条；说明中提到问题 {theme_counts['problem']} 次、收获 {theme_counts['harvest']} 次、支持需求 {theme_counts['support']} 次。",
            "focusAreas": [
                "任务完成度",
                "问题与阻力" if theme_counts["problem"] else "任务闭环",
                "支持需求" if theme_counts["support"] else "经验沉淀",
            ],
            "supportSignals": [
                f"{theme_counts['support']} 条任务说明明确提出支持或协同需求。" if theme_counts["support"] else "本周未出现明确的集中支持请求。",
                "所有个人成长/隐私内容均已排除在团队报告之外。",
            ],
            "suggestedActions": [
                "优先安排一次团队级优先级澄清。",
                "把重复出现的阻力转成模板、资源或协调动作。",
                "针对支持需求高的事项安排一对一跟进。",
            ],
            "anonymousInsights": insights[:3] or ["本周团队层主要看见的是工作推进信号，而非个体私密状态。"],
        }
    else:
        legacy_rows = state.db.fetchall(
            f"""
            SELECT * FROM weekly_review_entries
            WHERE user_id IN ({placeholders}) AND week_label = ? AND TRIM(COALESCE(work_free_note, '')) != ''
            ORDER BY submitted_at DESC
            """,
            (*report_ids, week_label),
        )
        if not legacy_rows:
            return None
        legacy_notes = [str(row["work_free_note"]).strip() for row in legacy_rows if str(row["work_free_note"]).strip()]
        summary = {
            "headline": "团队工作域信号已按兼容模式聚合。",
            "summary": f"本周纳入 {len(legacy_notes)} 份历史工作复盘摘要；当前仍保持个人成长与隐私内容排除在团队报告之外。",
            "focusAreas": ["历史工作摘要", "任务说明迁移", "团队闭环"],
            "supportSignals": [
                "当前报告来自旧版周复盘摘要兼容模式。",
                "所有个人成长/隐私内容均已排除在团队报告之外。",
            ],
            "suggestedActions": [
                "逐步把旧版大表单迁移到逐任务复盘。",
                "优先补录关键任务的说明与阻力。",
                "后续团队聚合统一切到任务级数据源。",
            ],
            "anonymousInsights": [f"有成员在历史周报中提到「{note[:18]}」。" for note in legacy_notes[:3]],
        }
    actions = [
        {"actionType": "meeting", "title": "安排团队优先级澄清会", "payload": {"scope": "team", "weekLabel": week_label}},
        {"actionType": "one_on_one", "title": "为需要支持的成员安排一对一", "payload": {"scope": "team", "weekLabel": week_label}},
    ]
    return _upsert_hierarchy_report(
        state,
        organization_id=manager_user.organizationId,
        scope_type="team",
        scope_ref_id=manager_user.id,
        week_label=week_label,
        summary=summary,
        actions=actions,
    )


def _org_report_for_admin(state: AppState, admin_user: SessionUser, week_label: str) -> HierarchyReportRecord | None:
    rows = state.db.fetchall(
        """
        SELECT * FROM weekly_review_task_entries
        WHERE organization_id = ? AND week_label = ? AND content_domain = 'work'
        ORDER BY reviewed_at DESC
        """,
        (admin_user.organizationId, week_label),
    )
    if rows:
        items = [_weekly_review_task_entry_from_row(row) for row in rows]
        completed_count = sum(1 for item in items if item.taskSnapshot.status == "done")
        theme_counts = _note_theme_counts(items)
        anonymous_insights = [f"有一线任务提到「{item.note[:20]}」这样的现场信息。" for item in items if item.note.strip()][:4]
        summary = {
            "headline": "组织层工作域信号已完成聚合。",
            "summary": f"本周共纳入 {len(items)} 条工作任务复盘，其中已完成 {completed_count} 条；说明中提到问题 {theme_counts['problem']} 次、收获 {theme_counts['harvest']} 次、支持需求 {theme_counts['support']} 次，组织层可据此判断共性阻力与成长信号。",
            "focusAreas": ["组织主线对齐", "跨部门推进", "任务说明洞察"],
            "supportSignals": [
                f"{theme_counts['support']} 条任务说明提出支持需求。" if theme_counts["support"] else "本周未见集中支持请求，但仍需关注隐性负荷。",
                "组织报告已默认排除个人成长与隐私内容。",
            ],
            "suggestedActions": [
                "针对跨团队反复出现的阻力配置统一支持动作。",
                "把 CEO / 总监计划拆成更清晰的团队级行动锚点。",
                "优先处理最影响闭环的资源与协作摩擦。",
            ],
            "anonymousInsights": anonymous_insights[:4] or ["组织层报告只基于工作域信号，不涉及个人私密内容。"],
        }
    else:
        legacy_rows = state.db.fetchall(
            """
            SELECT * FROM weekly_review_entries
            WHERE organization_id = ? AND week_label = ? AND TRIM(COALESCE(work_free_note, '')) != ''
            ORDER BY submitted_at DESC
            """,
            (admin_user.organizationId, week_label),
        )
        if not legacy_rows:
            return None
        legacy_notes = [str(row["work_free_note"]).strip() for row in legacy_rows if str(row["work_free_note"]).strip()]
        summary = {
            "headline": "组织层工作域信号已按兼容模式聚合。",
            "summary": f"本周共纳入 {len(legacy_notes)} 份历史工作复盘摘要；当前组织视角仍严格排除个人成长与隐私内容。",
            "focusAreas": ["历史工作摘要", "组织主线对齐", "迁移补录"],
            "supportSignals": [
                "当前报告来自旧版周复盘摘要兼容模式。",
                "组织报告已默认排除个人成长与隐私内容。",
            ],
            "suggestedActions": [
                "继续把旧版工作复盘迁移到任务级说明。",
                "优先补录关键任务的阻力和收获。",
                "将组织共性阻力转换为支持动作。",
            ],
            "anonymousInsights": [f"有历史周报提到「{note[:20]}」这样的现场信息。" for note in legacy_notes[:4]],
        }
    actions = [
        {"actionType": "resource_request", "title": "评估组织级资源支持缺口", "payload": {"scope": "org", "weekLabel": week_label}},
        {"actionType": "meeting", "title": "发起跨部门协同校准会", "payload": {"scope": "org", "weekLabel": week_label}},
    ]
    return _upsert_hierarchy_report(
        state,
        organization_id=admin_user.organizationId,
        scope_type="org",
        scope_ref_id=admin_user.organizationId,
        week_label=week_label,
        summary=summary,
        actions=actions,
    )

def _dashboard_for_user(state: AppState, current_user: SessionUser, week_label: str | None = None) -> ReviewDashboardResponse:
    plans = _plan_nodes(state, current_user.organizationId)
    target_week = week_label or _current_week_label()
    review_row = _review_row_for_user_week(state, current_user.id, target_week)
    current_review = _build_review_entry_record(state, review_row) if review_row else None
    work_items, personal_items = _dashboard_review_items(state, current_user, target_week, review_row)
    signal_card: ManagementSignalCardRecord | None = None
    growth_card: PersonalGrowthCardRecord | None = None
    team_report: HierarchyReportRecord | None = None
    org_report: HierarchyReportRecord | None = None
    if review_row:
        signal_card = _upsert_signal_card(state, current_user, review_row, work_items)
        growth_card = _upsert_personal_growth_card(state, current_user, review_row, personal_items)
    if _direct_report_rows(state, current_user.id):
        team_report = _team_report_for_manager(state, current_user, target_week)
    if current_user.primaryRole == "admin":
        org_report = _org_report_for_admin(state, current_user, target_week)
    return ReviewDashboardResponse(
        currentReview=current_review,
        workItems=work_items,
        personalItems=personal_items,
        workSignalCard=signal_card,
        personalGrowthCard=growth_card,
        teamReport=team_report,
        orgReport=org_report,
        plans=plans,
    )


def _backfill_task_tag_ids(state: AppState) -> None:
    timestamp = now_iso()
    state.db.execute(
        """
        UPDATE task_tag_library
        SET scope = COALESCE(NULLIF(scope, ''), 'org'),
            color = COALESCE(NULLIF(color, ''), CASE WHEN scope = 'self' THEN '#9CA3AF' ELSE '#5B7BFE' END),
            owner_user_id = COALESCE(owner_user_id, ''),
            created_by = COALESCE(NULLIF(created_by, ''), '系统'),
            updated_at = COALESCE(NULLIF(updated_at, ''), created_at)
        WHERE updated_at = '' OR scope = '' OR owner_user_id IS NULL OR color = '' OR color IS NULL
        """,
    )
    state.db.execute(
        "UPDATE task_lists SET is_default = CASE WHEN id = 'list-0' THEN 1 ELSE COALESCE(is_default, 0) END WHERE is_default IS NULL OR is_default = ''"
    )
    org_row = state.db.fetchone("SELECT id FROM organizations ORDER BY created_at ASC LIMIT 1")
    if not org_row:
        return
    org_id = str(org_row["id"])
    fallback_user = state.db.fetchone("SELECT * FROM employee_accounts WHERE organization_id = ? ORDER BY created_at ASC LIMIT 1", (org_id,))
    if not fallback_user:
        return
    fallback_session = _row_user(fallback_user)
    for row in state.db.fetchall("SELECT id, organization_id, tags_json, tag_ids_json FROM tasks"):
        tag_ids = [str(item) for item in from_json(row["tag_ids_json"], [])] if isinstance(from_json(row["tag_ids_json"], []), list) else []
        if tag_ids:
            continue
        tag_names = [str(item) for item in from_json(row["tags_json"], [])] if isinstance(from_json(row["tags_json"], []), list) else []
        if not tag_names:
            continue
        current_user = SessionUser(
            id=fallback_session.id,
            organizationId=str(row["organization_id"]),
            email=fallback_session.email,
            fullName=fallback_session.fullName,
            primaryRole=fallback_session.primaryRole,
            accountStatus=fallback_session.accountStatus,
        )
        resolved = [_ensure_task_tag(state, current_user, name, "org") for name in tag_names if name.strip()]
        state.db.execute(
            "UPDATE tasks SET tag_ids_json = ?, tags_json = ?, updated_at = ? WHERE id = ?",
            (to_json([item.id for item in resolved]), to_json([item.name for item in resolved]), timestamp, str(row["id"])),
        )


def _backfill_task_org_links(
    state: AppState,
    organization_id: str,
    task_ids: list[str] | None = None,
) -> TaskOrgBackfillResultRecord:
    query = "SELECT * FROM tasks WHERE organization_id = ? ORDER BY updated_at DESC"
    params: tuple[object, ...] = (organization_id,)
    if task_ids:
        placeholders = _sql_placeholders(task_ids)
        query = f"SELECT * FROM tasks WHERE organization_id = ? AND id IN ({placeholders}) ORDER BY updated_at DESC"
        params = (organization_id, *task_ids)
    task_rows = state.db.fetchall(query, params)
    created_links = 0
    updated_links = 0
    linked_tasks = 0
    for task_row in task_rows:
        existing = state.db.fetchone("SELECT updated_at FROM task_org_links WHERE task_id = ?", (str(task_row["id"]),))
        _sync_task_org_link(state, task_row)
        if existing:
            updated_links += 1
        else:
            created_links += 1
        linked_tasks += 1
    return TaskOrgBackfillResultRecord(
        organizationId=organization_id,
        totalTasks=len(task_rows),
        linkedTasks=linked_tasks,
        createdLinks=created_links,
        updatedLinks=updated_links,
        updatedAt=now_iso(),
    )


def _sync_qwen_chat(api_key: str, payload: dict, timeout: object) -> str:
    """Synchronous LLM chat call (Volcengine Ark / OpenAI-compatible), run via asyncio.to_thread."""
    import httpx
    from app.smart_input import ARK_BASE_URL

    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            f"{ARK_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        result = response.json()
    text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not text:
        return "抱歉，AI 未能生成有效回复，请稍后重试。"
    return text.strip()


def _generate_recording_summary(
    *,
    transcript: str,
    task_title: str,
    client_name: str | None = None,
    event_line_name: str | None = None,
) -> str:
    """Generate AI summary from recording transcript using Volcengine Ark."""
    from app.smart_input import _qwen_api_key, ARK_BASE_URL, DEFAULT_LLM_MODEL

    api_key = _qwen_api_key()
    if not api_key or len(transcript.strip()) < 20:
        # Fallback: first 140 chars
        s = transcript[:140].strip()
        return f"{s}..." if len(transcript) > 140 else s

    context_parts = []
    if task_title:
        context_parts.append(f"任务：{task_title}")
    if client_name:
        context_parts.append(f"客户：{client_name}")
    if event_line_name:
        context_parts.append(f"事件线：{event_line_name}")
    context = "\n".join(context_parts)

    # Truncate very long transcripts to stay within model limits
    max_transcript = 8000
    truncated = transcript[:max_transcript] if len(transcript) > max_transcript else transcript

    system_prompt = (
        "你是录音摘要助理。根据录音转写文本，生成会议/沟通摘要。\n"
        "要求：\n"
        "1. 概括核心内容，根据内容复杂度自由决定长度\n"
        "2. 列出关键决策点（如果有）\n"
        "3. 列出待办事项和负责人（如果有）\n"
        "4. 使用中文\n"
        "5. 不要重复转写原文，要提炼和总结\n"
    )
    if context:
        system_prompt += f"\n上下文：\n{context}"

    model_name = os.getenv("YIYU_CONSULTATION_CHAT_MODEL", os.getenv("YIYU_SMART_INPUT_MODEL", DEFAULT_LLM_MODEL))
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"录音转写文本：\n{truncated}"},
        ],
        "temperature": 0.5,
        "top_p": 0.9,
        "max_tokens": 2000,
        "stream": False,
    }
    try:
        import httpx
        read_timeout = 60.0 if (has_client_knowledge and intro_request) else 30.0
        timeout = httpx.Timeout(timeout=None, connect=8.0, read=read_timeout, write=8.0, pool=8.0)
        summary = _sync_qwen_chat(api_key, payload, timeout)
        return summary if summary else transcript[:140]
    except Exception as exc:
        logger.warning("AI summary generation failed, falling back: %s", exc)
        s = transcript[:140].strip()
        return f"{s}..." if len(transcript) > 140 else s


def create_app() -> FastAPI:
    app = FastAPI(title=APP_NAME, version=APP_VERSION)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:4173",
            "http://localhost:4173",
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "app://renderer",
            # Mobile app (Expo dev + production)
            "http://localhost:8081",
            "http://localhost:19006",
            "exp://localhost:8081",
        ],
        # Allow any origin in dev for mobile (React Native uses various origins)
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    data_dir = Path(os.environ.get("YIYU_CLOUD_DATA_DIR", Path.home() / "Library/Application Support/YiyuThinkTankCloud"))
    state = AppState(
        db=Database(data_dir / "cloud.db"),
        data_dir=data_dir,
        secret_key=ensure_cloud_secret(data_dir),
    )
    app.state.app_state = state
    _ensure_seed_data(state)
    _backfill_task_tag_ids(state)
    for org_row in state.db.fetchall("SELECT id FROM organizations"):
        _backfill_task_org_links(state, str(org_row["id"]))

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            service=APP_NAME,
            organizationCount=state.db.scalar("SELECT COUNT(1) AS count FROM organizations"),
            employeeCount=state.db.scalar("SELECT COUNT(1) AS count FROM employee_accounts"),
            taskCount=state.db.scalar("SELECT COUNT(1) AS count FROM tasks"),
        )

    @app.get("/api/v1/auth/department-options", response_model=list[DepartmentOption])
    def list_department_options() -> list[DepartmentOption]:
        return [DepartmentOption(id=item.id, name=item.name, color=item.color) for item in list_department_catalog()]

    def _ensure_login_allowed(row) -> None:
        status_value = str(row["account_status"])
        if status_value == "pending":
            raise HTTPException(status_code=403, detail="你的账号已提交，正在等待管理员审核。")
        if status_value == "rejected":
            reason = row["rejected_reason"] or "账号未通过审核，请联系管理员。"
            raise HTTPException(status_code=403, detail=str(reason))
        if status_value == "disabled":
            raise HTTPException(status_code=403, detail="账号已停用")

    def _issue_auth_tokens(row, *, session_id: str, refresh_token: str) -> AuthTokenResponse:
        token = create_access_token(
            state.secret_key,
            str(row["id"]),
            extra={
                "organization_id": str(row["organization_id"]),
                "primary_role": str(row["primary_role"]),
                "session_id": session_id,
            },
        )
        return AuthTokenResponse(accessToken=token, refreshToken=refresh_token, user=_row_user(row))

    @app.post("/api/v1/auth/register")
    def register(payload: RegisterPayload) -> dict[str, str]:
        existing = state.db.fetchone("SELECT id FROM employee_accounts WHERE email = ?", (payload.email.lower(),))
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")
        department = get_department_entry(payload.departmentId) if payload.departmentId else None
        if payload.departmentId and not department:
            raise HTTPException(status_code=400, detail="请选择有效的部门")
        job_title = payload.jobTitle.strip() if payload.jobTitle else None
        manager_name = payload.managerName.strip() if payload.managerName else None
        current_focus = payload.currentFocus.strip() if payload.currentFocus else ""
        timestamp = now_iso()
        user_id = new_id("emp")
        state.db.execute(
            """
            INSERT INTO employee_accounts(
                id, organization_id, email, full_name, password_hash, primary_role, account_status,
                approved_at, approved_by, rejected_reason, disabled_at, recent_mentions_json, last_login_at,
                department_id, department_name, job_title, manager_name, current_focus, is_department_lead, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, 'employee', 'pending', NULL, NULL, NULL, NULL, '[]', NULL, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                DEFAULT_ORG_ID,
                payload.email.lower(),
                payload.fullName,
                hash_password(payload.password),
                department.id if department else None,
                department.name if department else None,
                job_title,
                manager_name,
                current_focus,
                1 if payload.isDepartmentLead else 0,
                timestamp,
                timestamp,
            ),
        )
        _log_audit(
            state,
            "register",
            actor_user_id=None,
            target_user_id=user_id,
            detail={
                "email": payload.email.lower(),
                "departmentId": department.id if department else None,
                "jobTitle": job_title,
                "managerName": manager_name,
                "currentFocus": current_focus,
                "isDepartmentLead": bool(payload.isDepartmentLead),
            },
        )
        return {"message": "你的账号已提交，正在等待管理员审核。"}

    @app.post("/api/v1/auth/login", response_model=AuthTokenResponse)
    def login(payload: LoginPayload) -> AuthTokenResponse:
        row = state.db.fetchone("SELECT * FROM employee_accounts WHERE email = ?", (payload.email.lower(),))
        if not row or not verify_password(payload.password, str(row["password_hash"])):
            raise HTTPException(status_code=401, detail="邮箱或密码错误")
        _ensure_login_allowed(row)
        session_id = new_id("sess")
        refresh_token = new_id("rt")
        timestamp = now_iso()
        expires_at = (datetime.now() + timedelta(days=30)).replace(microsecond=0).isoformat()
        state.db.execute(
            "INSERT INTO auth_refresh_sessions(id, user_id, refresh_token, created_at, expires_at, revoked_at) VALUES(?, ?, ?, ?, ?, NULL)",
            (session_id, str(row["id"]), refresh_token, timestamp, expires_at),
        )
        state.db.execute(
            "UPDATE employee_accounts SET last_login_at = ?, updated_at = ? WHERE id = ?",
            (timestamp, timestamp, str(row["id"])),
        )
        _log_audit(state, "login", actor_user_id=str(row["id"]), target_user_id=str(row["id"]), detail={"sessionId": session_id})
        return _issue_auth_tokens(row, session_id=session_id, refresh_token=refresh_token)

    @app.post("/api/v1/auth/refresh", response_model=AuthTokenResponse)
    def refresh_auth(payload: RefreshPayload) -> AuthTokenResponse:
        session_row = state.db.fetchone("SELECT * FROM auth_refresh_sessions WHERE refresh_token = ?", (payload.refreshToken,))
        if not session_row:
            raise HTTPException(status_code=401, detail="登录状态已过期，请重新登录")
        if session_row["revoked_at"]:
            raise HTTPException(status_code=401, detail="登录状态已失效，请重新登录")
        expires_at = datetime.fromisoformat(str(session_row["expires_at"]))
        if expires_at <= datetime.now():
            state.db.execute(
                "UPDATE auth_refresh_sessions SET revoked_at = ? WHERE id = ?",
                (now_iso(), str(session_row["id"])),
            )
            raise HTTPException(status_code=401, detail="登录状态已过期，请重新登录")
        row = state.db.fetchone("SELECT * FROM employee_accounts WHERE id = ?", (str(session_row["user_id"]),))
        if not row:
            state.db.execute(
                "UPDATE auth_refresh_sessions SET revoked_at = ? WHERE id = ?",
                (now_iso(), str(session_row["id"])),
            )
            raise HTTPException(status_code=401, detail="账号不存在，请重新登录")
        _ensure_login_allowed(row)
        timestamp = now_iso()
        next_refresh_token = new_id("rt")
        next_expires_at = (datetime.now() + timedelta(days=30)).replace(microsecond=0).isoformat()
        state.db.execute(
            "UPDATE auth_refresh_sessions SET refresh_token = ?, expires_at = ?, revoked_at = NULL WHERE id = ?",
            (next_refresh_token, next_expires_at, str(session_row["id"])),
        )
        state.db.execute(
            "UPDATE employee_accounts SET last_login_at = ?, updated_at = ? WHERE id = ?",
            (timestamp, timestamp, str(row["id"])),
        )
        _log_audit(
            state,
            "refresh_login",
            actor_user_id=str(row["id"]),
            target_user_id=str(row["id"]),
            detail={"sessionId": str(session_row["id"])},
        )
        return _issue_auth_tokens(row, session_id=str(session_row["id"]), refresh_token=next_refresh_token)

    @app.get("/api/v1/auth/me", response_model=SessionUser)
    def me(current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization))) -> SessionUser:
        return current_user

    @app.patch("/api/v1/auth/me")
    def update_me(
        payload: dict,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> SessionUser:
        allowed_fields = {"fullName", "primaryRole"}
        updates: list[str] = []
        params: list[str] = []
        if "fullName" in payload and payload["fullName"]:
            updates.append("full_name = ?")
            params.append(str(payload["fullName"]).strip())
        if "primaryRole" in payload and payload["primaryRole"]:
            updates.append("primary_role = ?")
            params.append(str(payload["primaryRole"]).strip())
        if not updates:
            raise HTTPException(status_code=400, detail="没有可更新的字段。")
        updates.append("updated_at = ?")
        params.append(now_iso())
        params.append(current_user.id)
        state.db.execute(
            f"UPDATE employee_accounts SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )
        row = state.db.fetchone("SELECT * FROM employee_accounts WHERE id = ?", (current_user.id,))
        if not row:
            raise HTTPException(status_code=404, detail="用户不存在。")
        return SessionUser(
            id=str(row["id"]),
            organizationId=str(row["organization_id"]),
            email=str(row["email"]),
            fullName=str(row["full_name"]),
            primaryRole=str(row["primary_role"]),
            accountStatus=str(row["account_status"]),
        )

    @app.post("/api/v1/auth/change-password")
    def change_password(
        payload: ChangePasswordPayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> dict[str, str]:
        row = state.db.fetchone("SELECT * FROM employee_accounts WHERE id = ?", (current_user.id,))
        if not row:
            raise HTTPException(status_code=404, detail="用户不存在")
        if not verify_password(payload.currentPassword, str(row["password_hash"])):
            raise HTTPException(status_code=400, detail="当前密码不正确")
        state.db.execute(
            "UPDATE employee_accounts SET password_hash = ?, updated_at = ? WHERE id = ?",
            (hash_password(payload.newPassword), now_iso(), current_user.id),
        )
        _log_audit(state, "change_password", actor_user_id=current_user.id, target_user_id=current_user.id, detail={})
        return {"message": "密码修改成功"}

    @app.post("/api/v1/auth/logout")
    def logout(current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)), authorization: str | None = Header(default=None)) -> dict[str, str]:
        token = authorization.split(" ", 1)[1]
        payload = decode_access_token(state.secret_key, token)
        session_id = payload.get("session_id")
        if session_id:
            state.db.execute(
                "UPDATE auth_refresh_sessions SET revoked_at = ? WHERE id = ?",
                (now_iso(), session_id),
            )
        _log_audit(state, "logout", actor_user_id=current_user.id, target_user_id=current_user.id, detail={})
        return {"message": "ok"}

    @app.post("/api/v1/integrations/feishu/user-binding/sessions", response_model=FeishuBindingRelaySessionStatusRecord)
    def create_feishu_binding_relay_session(
        payload: FeishuBindingRelaySessionCreatePayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> FeishuBindingRelaySessionStatusRecord:
        try:
            expires_at = datetime.fromisoformat(payload.expiresAt)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="expiresAt 必须是合法 ISO 时间。") from exc
        if expires_at <= datetime.now():
            raise HTTPException(status_code=400, detail="expiresAt 已过期，不能创建扫码授权会话。")
        timestamp = now_iso()
        state.db.execute(
            """
            INSERT INTO feishu_binding_relay_sessions(
                state_token, organization_id, user_id, code, error_message, created_at, expires_at, authorized_at, cleared_at
            )
            VALUES(?, ?, ?, NULL, NULL, ?, ?, NULL, NULL)
            ON CONFLICT(state_token) DO UPDATE SET
                organization_id = excluded.organization_id,
                user_id = excluded.user_id,
                code = NULL,
                error_message = NULL,
                created_at = excluded.created_at,
                expires_at = excluded.expires_at,
                authorized_at = NULL,
                cleared_at = NULL
            """,
            (payload.state, current_user.organizationId, current_user.id, timestamp, payload.expiresAt),
        )
        row = state.db.fetchone(
            "SELECT * FROM feishu_binding_relay_sessions WHERE state_token = ?",
            (payload.state,),
        )
        if not row:
            raise HTTPException(status_code=500, detail="飞书扫码中继会话创建失败。")
        return _feishu_relay_status_record(row)

    @app.get("/api/v1/integrations/feishu/user-binding/sessions/{state_token}", response_model=FeishuBindingRelaySessionStatusRecord)
    def get_feishu_binding_relay_session(
        state_token: str,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> FeishuBindingRelaySessionStatusRecord:
        row = state.db.fetchone(
            "SELECT * FROM feishu_binding_relay_sessions WHERE state_token = ?",
            (state_token,),
        )
        if not row or str(row["user_id"]) != current_user.id:
            raise HTTPException(status_code=404, detail="没有找到这次飞书扫码授权会话。")
        if row["cleared_at"]:
            raise HTTPException(status_code=404, detail="这次飞书扫码授权会话已清理。")
        return _feishu_relay_status_record(row, include_code=True)

    @app.delete("/api/v1/integrations/feishu/user-binding/sessions/{state_token}")
    def delete_feishu_binding_relay_session(
        state_token: str,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> dict[str, str]:
        row = state.db.fetchone(
            "SELECT * FROM feishu_binding_relay_sessions WHERE state_token = ?",
            (state_token,),
        )
        if row and str(row["user_id"]) == current_user.id:
            state.db.execute(
                "UPDATE feishu_binding_relay_sessions SET cleared_at = ? WHERE state_token = ?",
                (now_iso(), state_token),
            )
        return {"message": "ok"}

    @app.get("/api/v1/integrations/feishu/user-binding/callback", response_class=HTMLResponse)
    def receive_feishu_binding_relay_callback(
        code: str | None = Query(default=None),
        state_token: str | None = Query(default=None, alias="state"),
    ) -> HTMLResponse:
        if not state_token:
            return _render_feishu_relay_callback_page("飞书绑定失败", "缺少 state，无法确认这次授权属于哪个工作台会话。", success=False)
        row = state.db.fetchone(
            "SELECT * FROM feishu_binding_relay_sessions WHERE state_token = ?",
            (state_token,),
        )
        if not row:
            return _render_feishu_relay_callback_page("飞书绑定失败", "这次扫码授权会话不存在或已失效，请回到桌面工作台重新发起绑定。", success=False)
        if row["cleared_at"]:
            return _render_feishu_relay_callback_page("飞书绑定失败", "这次扫码授权会话已经结束，请回到桌面工作台重新发起绑定。", success=False)
        try:
            if row["expires_at"] and datetime.fromisoformat(str(row["expires_at"])) <= datetime.now():
                state.db.execute(
                    "UPDATE feishu_binding_relay_sessions SET error_message = ? WHERE state_token = ?",
                    ("这次扫码授权请求已经过期，请重新发起绑定。", state_token),
                )
                return _render_feishu_relay_callback_page("飞书绑定失败", "这次扫码授权请求已经过期，请回到桌面工作台重新发起绑定。", success=False)
        except ValueError:
            state.db.execute(
                "UPDATE feishu_binding_relay_sessions SET error_message = ? WHERE state_token = ?",
                ("扫码授权会话时间损坏，请重新发起绑定。", state_token),
            )
            return _render_feishu_relay_callback_page("飞书绑定失败", "扫码授权会话时间损坏，请回到桌面工作台重新发起绑定。", success=False)
        if not code or not code.strip():
            state.db.execute(
                "UPDATE feishu_binding_relay_sessions SET error_message = ? WHERE state_token = ?",
                ("飞书没有返回有效授权码。", state_token),
            )
            return _render_feishu_relay_callback_page("飞书绑定失败", "飞书没有返回有效授权码，请回到桌面工作台重新发起绑定。", success=False)
        state.db.execute(
            """
            UPDATE feishu_binding_relay_sessions
            SET code = ?, error_message = NULL, authorized_at = ?
            WHERE state_token = ?
            """,
            (code.strip(), now_iso(), state_token),
        )
        return _render_feishu_relay_callback_page("飞书授权结果已回传", "扫码授权已完成，现在回到桌面工作台即可自动刷新个人飞书绑定状态。", success=True)

    @app.get("/api/v1/admin/employees", response_model=list[EmployeeRecord])
    def list_employees(current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_admin(app, authorization))) -> list[EmployeeRecord]:
        rows = state.db.fetchall(
            "SELECT * FROM employee_accounts WHERE organization_id = ? ORDER BY created_at DESC",
            (current_user.organizationId,),
        )
        return [_employee_record(row) for row in rows]

    # ── Org AI Config (encrypted, admin-write, member-read) ──

    def _org_ai_encrypt(plain_text: str, org_id: str) -> tuple[str, str]:
        """AES-256-GCM encrypt using org-scoped key derived from app secret + org_id."""
        import base64
        from hashlib import sha256
        from os import urandom
        key = sha256(f"{state.secret_key}:{org_id}:ai_config".encode()).digest()
        nonce = urandom(12)
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        cipher = AESGCM(key)
        ct = cipher.encrypt(nonce, plain_text.encode("utf-8"), None)
        return base64.b64encode(ct).decode(), base64.b64encode(nonce).decode()

    def _org_ai_decrypt(encrypted_b64: str, nonce_b64: str, org_id: str) -> str:
        import base64
        from hashlib import sha256
        if not encrypted_b64 or not nonce_b64:
            return ""
        key = sha256(f"{state.secret_key}:{org_id}:ai_config".encode()).digest()
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        cipher = AESGCM(key)
        ct = base64.b64decode(encrypted_b64)
        nonce = base64.b64decode(nonce_b64)
        return cipher.decrypt(nonce, ct, None).decode("utf-8")

    @app.get("/api/v1/settings/org-ai-config", response_model=OrgAiConfigRecord)
    def get_org_ai_config(
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> OrgAiConfigRecord:
        row = state.db.fetchone("SELECT * FROM org_ai_config WHERE org_id = ?", (current_user.organizationId,))
        if not row:
            return OrgAiConfigRecord(
                orgId=current_user.organizationId,
                aiProvider="mock",
                aiModel="",
                hasApiKey=False,
                updatedAt=now_iso(),
            )
        return OrgAiConfigRecord(
            orgId=str(row["org_id"]),
            aiProvider=str(row["ai_provider"]),
            aiModel=str(row["ai_model"]),
            hasApiKey=bool(row["api_key_encrypted"]),
            configuredBy=str(row["configured_by"]) if row["configured_by"] else None,
            updatedAt=str(row["updated_at"]),
        )

    @app.post("/api/v1/settings/org-ai-config", response_model=OrgAiConfigRecord)
    def update_org_ai_config(
        payload: OrgAiConfigUpdatePayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_admin(app, authorization)),
    ) -> OrgAiConfigRecord:
        org_id = current_user.organizationId
        timestamp = now_iso()
        existing = state.db.fetchone("SELECT * FROM org_ai_config WHERE org_id = ?", (org_id,))
        encrypted_key = str(existing["api_key_encrypted"]) if existing else ""
        encryption_nonce = str(existing["encryption_nonce"]) if existing else ""
        if payload.clearApiKey:
            encrypted_key = ""
            encryption_nonce = ""
        elif payload.apiKey and payload.apiKey.strip():
            encrypted_key, encryption_nonce = _org_ai_encrypt(payload.apiKey.strip(), org_id)
        state.db.execute(
            """
            INSERT INTO org_ai_config(org_id, ai_provider, ai_model, api_key_encrypted, encryption_nonce, configured_by, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(org_id) DO UPDATE SET
                ai_provider = excluded.ai_provider,
                ai_model = excluded.ai_model,
                api_key_encrypted = excluded.api_key_encrypted,
                encryption_nonce = excluded.encryption_nonce,
                configured_by = excluded.configured_by,
                updated_at = excluded.updated_at
            """,
            (org_id, payload.aiProvider, payload.aiModel or "", encrypted_key, encryption_nonce, current_user.id, timestamp),
        )
        return get_org_ai_config(current_user)

    @app.get("/api/v1/settings/org-ai-config/secret", response_model=OrgAiConfigSecretRecord)
    def get_org_ai_config_secret(
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> OrgAiConfigSecretRecord:
        """Returns decrypted API key — only accessible to authenticated org members."""
        row = state.db.fetchone("SELECT * FROM org_ai_config WHERE org_id = ?", (current_user.organizationId,))
        if not row or not row["api_key_encrypted"]:
            return OrgAiConfigSecretRecord(
                orgId=current_user.organizationId,
                aiProvider="mock",
                aiModel="",
                apiKey="",
                updatedAt=now_iso(),
            )
        try:
            decrypted = _org_ai_decrypt(
                str(row["api_key_encrypted"]),
                str(row["encryption_nonce"]),
                current_user.organizationId,
            )
        except Exception:
            decrypted = ""
        return OrgAiConfigSecretRecord(
            orgId=str(row["org_id"]),
            aiProvider=str(row["ai_provider"]),
            aiModel=str(row["ai_model"]),
            apiKey=decrypted,
            updatedAt=str(row["updated_at"]),
        )

    @app.get("/api/v1/settings/org-model/profile", response_model=OrgModelProfileRecord)
    def get_org_model_profile(
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_admin(app, authorization)),
    ) -> OrgModelProfileRecord:
        return _get_org_model_profile(state, current_user.organizationId)

    @app.post("/api/v1/settings/org-model/profile", response_model=OrgModelProfileRecord)
    def save_org_model_profile(
        payload: OrgModelProfileRecord,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_admin(app, authorization)),
    ) -> OrgModelProfileRecord:
        return _save_org_model_profile(state, current_user, payload)

    @app.post("/api/v1/settings/org-model/backfill-task-links", response_model=TaskOrgBackfillResultRecord)
    def backfill_org_task_links(
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_admin(app, authorization)),
    ) -> TaskOrgBackfillResultRecord:
        result = _backfill_task_org_links(state, current_user.organizationId)
        _log_audit(
            state,
            "backfill_task_org_links",
            actor_user_id=current_user.id,
            target_user_id=None,
            detail=result.model_dump(),
        )
        return result

    @app.get("/api/v1/event-lines", response_model=list[EventLineRecord])
    def list_event_lines(
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> list[EventLineRecord]:
        rows = state.db.fetchall(
            """
            SELECT *
            FROM event_lines
            WHERE organization_id = ?
            ORDER BY CASE status WHEN 'active' THEN 0 WHEN 'blocked' THEN 1 WHEN 'paused' THEN 2 WHEN 'done' THEN 3 ELSE 4 END,
                     updated_at DESC
            """,
            (current_user.organizationId,),
        )
        return [_event_line_record(state, row) for row in rows]

    @app.get("/api/v1/clients", response_model=list[ClientSummaryRecord])
    def list_clients(
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> list[ClientSummaryRecord]:
        rows = state.db.fetchall(
            """
            SELECT *
            FROM clients
            WHERE organization_id = ?
            ORDER BY updated_at DESC, name COLLATE NOCASE ASC
            """,
            (current_user.organizationId,),
        )
        return [_client_summary_record(row) for row in rows]

    @app.post("/api/v1/event-lines", response_model=EventLineRecord)
    def create_event_line(
        payload: EventLineCreatePayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> EventLineRecord:
        if payload.ownerId:
            _get_user_or_404(state, payload.ownerId)
        timestamp = now_iso()
        event_line_id = new_id("eline")
        owner_id = payload.ownerId or current_user.id
        participant_ids = list(dict.fromkeys([owner_id, *[item for item in payload.participantIds if item]]))
        department_name = None
        client_name = None
        if payload.primaryDepartmentId:
            department_row = state.db.fetchone("SELECT name FROM org_departments WHERE id = ?", (payload.primaryDepartmentId,))
            department_name = str(department_row["name"]) if department_row else None
        if payload.primaryClientId:
            client_row = _client_row_by_id(state, payload.primaryClientId, current_user.organizationId)
            client_name = str(client_row["name"]) if client_row and client_row["name"] else None
        state.db.execute(
            """
            INSERT INTO event_lines(
                id, organization_id, name, kind, status, visibility_scope, business_category, stage, summary, intent, current_blocker, recent_decision, next_step, evidence_count, owner_id,
                primary_client_id, primary_client_name, primary_department_id, participant_ids_json, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_line_id,
                current_user.organizationId,
                payload.name.strip(),
                payload.kind,
                payload.status,
                payload.visibilityScope,
                payload.businessCategory,
                payload.stage,
                payload.summary,
                payload.intent,
                payload.currentBlocker,
                payload.recentDecision,
                payload.nextStep,
                int(payload.evidenceCount or 0),
                owner_id,
                payload.primaryClientId,
                client_name,
                payload.primaryDepartmentId,
                to_json(participant_ids),
                timestamp,
                timestamp,
            ),
        )
        _record_event_line_activity(
            state,
            event_line_id,
            "manual_note",
            event_line_id,
            current_user.id,
            "创建事件线",
            f"创建事件线：{payload.name.strip()}",
            {"primaryDepartmentName": department_name or ""},
        )
        row = _event_line_row_or_404(state, event_line_id, current_user.organizationId)
        return _event_line_record(state, row)

    @app.get("/api/v1/event-lines/{event_line_id}", response_model=EventLineDetailRecord)
    def get_event_line(
        event_line_id: str,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> EventLineDetailRecord:
        row = _event_line_row_or_404(state, event_line_id, current_user.organizationId)
        return _event_line_detail_record(state, row, current_user.id)

    def _has_event_line_attachments_table() -> bool:
        row = state.db.fetchone(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'event_line_attachments'"
        )
        return row is not None

    @app.get("/api/v1/event-lines/{event_line_id}/report-snapshot", response_model=EventLineReportSnapshotRecord)
    def get_event_line_report_snapshot(
        event_line_id: str,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> EventLineReportSnapshotRecord:
        row = _event_line_row_or_404(state, event_line_id, current_user.organizationId)
        event_line = _event_line_record(state, row)
        activity_rows = state.db.fetchall(
            "SELECT * FROM event_line_activities WHERE event_line_id = ? ORDER BY happened_at ASC",
            (event_line_id,),
        )
        task_rows = state.db.fetchall(
            "SELECT * FROM tasks WHERE event_line_id = ? AND organization_id = ? ORDER BY updated_at DESC",
            (event_line_id, current_user.organizationId),
        )
        if _has_event_line_attachments_table():
            attachment_rows = state.db.fetchall(
                """
                SELECT id, organization_id, event_line_id, title, summary, path, kind, source, mime_type, size_bytes, created_by_user_id, created_at, task_id FROM task_attachments WHERE event_line_id = ? AND organization_id = ?
                UNION ALL
                SELECT id, organization_id, event_line_id, title, summary, path, kind, source, mime_type, size_bytes, created_by_user_id, created_at, '' as task_id FROM event_line_attachments WHERE event_line_id = ? AND organization_id = ?
                ORDER BY created_at ASC
                """,
                (event_line_id, current_user.organizationId, event_line_id, current_user.organizationId),
            )
        else:
            attachment_rows = state.db.fetchall(
                """
                SELECT id, organization_id, event_line_id, title, summary, path, kind, source, mime_type, size_bytes, created_by_user_id, created_at, task_id
                FROM task_attachments
                WHERE event_line_id = ? AND organization_id = ?
                ORDER BY created_at ASC
                """,
                (event_line_id, current_user.organizationId),
            )
        participant_ids = [str(item) for item in from_json(row["participant_ids_json"], []) if str(item).strip()]
        participant_names = []
        for uid in participant_ids:
            user_row = state.db.fetchone("SELECT full_name FROM employee_accounts WHERE id = ?", (uid,))
            if user_row:
                participant_names.append(str(user_row["full_name"]))
        return EventLineReportSnapshotRecord(
            eventLine=event_line,
            activities=[_event_line_activity_record(state, item) for item in activity_rows],
            tasks=[_task_record(state, item, current_user.id) for item in task_rows],
            attachments=[
                EventLineReportAttachmentRecord(
                    id=str(att["id"]),
                    taskId=str(att["task_id"]),
                    title=str(att["title"]),
                    kind=str(att["kind"]),
                    mimeType=str(att["mime_type"]) if att["mime_type"] else None,
                    sizeBytes=int(att["size_bytes"] or 0),
                    downloadUrl=f"/api/public/task-attachments/{att['id']}",
                    actorName=str(
                        state.db.fetchone("SELECT full_name FROM employee_accounts WHERE id = ?", (str(att["created_by_user_id"]),))["full_name"]
                    ) if att["created_by_user_id"] and state.db.fetchone("SELECT full_name FROM employee_accounts WHERE id = ?", (str(att["created_by_user_id"]),)) else None,
                    createdAt=str(att["created_at"]),
                )
                for att in attachment_rows
            ],
            participantNames=participant_names,
            snapshotAt=now_iso(),
        )

    @app.post("/api/v1/event-lines/{event_line_id}/attachments")
    async def upload_event_line_attachment(
        event_line_id: str,
        file: UploadFile = File(...),
        title: str | None = Form(default=None),
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> dict:
        _event_line_row_or_404(state, event_line_id, current_user.organizationId)
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="上传内容为空")
        resolved_title = (title or file.filename or "事件线附件").strip()
        mime_type = str(file.content_type or "application/octet-stream")
        upload_name = safe_filename(file.filename or f"{resolved_title}")
        att_dir = state.data_dir / "event-line-attachments" / current_user.organizationId / event_line_id
        att_dir.mkdir(parents=True, exist_ok=True)
        stored_name = safe_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{upload_name}")
        att_path = att_dir / stored_name
        att_path.write_bytes(content)
        timestamp = now_iso()
        attachment_id = new_id("elatt")
        relative_path = str(att_path.relative_to(state.data_dir))
        state.db.execute(
            """
            INSERT INTO event_line_attachments(
                id, organization_id, event_line_id, title, summary, path, kind, source,
                mime_type, size_bytes, created_by_user_id, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attachment_id, current_user.organizationId, event_line_id,
                resolved_title, f"事件线附件：{resolved_title}",
                relative_path, Path(stored_name).suffix.lower().lstrip(".") or "file",
                "event_line_attachment", mime_type, len(content),
                current_user.id, timestamp,
            ),
        )
        _record_event_line_activity(
            state, event_line_id, "attachment", attachment_id, current_user.id,
            f"上传附件：{resolved_title}",
            f"事件线附件已归档：{resolved_title}",
            {"attachmentId": attachment_id, "mimeType": mime_type, "sizeBytes": len(content), "path": relative_path},
        )
        return {"id": attachment_id, "title": resolved_title, "downloadUrl": f"/api/public/task-attachments/{attachment_id}"}

    @app.patch("/api/v1/event-lines/{event_line_id}", response_model=EventLineRecord)
    def update_event_line(
        event_line_id: str,
        payload: EventLineUpdatePayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> EventLineRecord:
        row = _event_line_row_or_404(state, event_line_id, current_user.organizationId)
        if payload.ownerId:
            _get_user_or_404(state, payload.ownerId)
        merged = {
            "name": payload.name.strip() if payload.name is not None else str(row["name"]),
            "kind": payload.kind or str(row["kind"] or "custom"),
            "status": payload.status or str(row["status"] or "active"),
            "business_category": payload.businessCategory if "businessCategory" in payload.model_fields_set else row["business_category"],
            "stage": payload.stage if "stage" in payload.model_fields_set else row["stage"],
            "summary": payload.summary if "summary" in payload.model_fields_set else row["summary"],
            "intent": payload.intent if "intent" in payload.model_fields_set else row["intent"],
            "current_blocker": payload.currentBlocker if "currentBlocker" in payload.model_fields_set else row["current_blocker"],
            "recent_decision": payload.recentDecision if "recentDecision" in payload.model_fields_set else row["recent_decision"],
            "next_step": payload.nextStep if "nextStep" in payload.model_fields_set else row["next_step"],
            "evidence_count": payload.evidenceCount if "evidenceCount" in payload.model_fields_set and payload.evidenceCount is not None else int(row["evidence_count"] or 0),
            "owner_id": payload.ownerId if "ownerId" in payload.model_fields_set else row["owner_id"],
            "primary_client_id": payload.primaryClientId if "primaryClientId" in payload.model_fields_set else row["primary_client_id"],
            "primary_client_name": None,
            "primary_department_id": payload.primaryDepartmentId if "primaryDepartmentId" in payload.model_fields_set else row["primary_department_id"],
            "participant_ids_json": to_json(payload.participantIds if payload.participantIds is not None else from_json(row["participant_ids_json"], [])),
        }
        client_row = _client_row_by_id(state, merged["primary_client_id"], current_user.organizationId)
        merged["primary_client_name"] = str(client_row["name"]) if client_row and client_row["name"] else None
        state.db.execute(
            """
            UPDATE event_lines
            SET name = ?, kind = ?, status = ?, business_category = ?, stage = ?, summary = ?, intent = ?, current_blocker = ?, recent_decision = ?, next_step = ?, evidence_count = ?, owner_id = ?, primary_client_id = ?, primary_client_name = ?, primary_department_id = ?, participant_ids_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                merged["name"],
                merged["kind"],
                merged["status"],
                merged["business_category"],
                merged["stage"],
                merged["summary"],
                merged["intent"],
                merged["current_blocker"],
                merged["recent_decision"],
                merged["next_step"],
                merged["evidence_count"],
                merged["owner_id"],
                merged["primary_client_id"],
                merged["primary_client_name"],
                merged["primary_department_id"],
                merged["participant_ids_json"],
                now_iso(),
                event_line_id,
            ),
        )
        _record_event_line_activity(
            state,
            event_line_id,
            "manual_note",
            event_line_id,
            current_user.id,
            "更新事件线",
            f"更新事件线：{merged['name']}",
            {
                "stage": merged["stage"] or "",
                "currentBlocker": merged["current_blocker"] or "",
                "recentDecision": merged["recent_decision"] or "",
            },
        )
        row = _event_line_row_or_404(state, event_line_id, current_user.organizationId)
        return _event_line_record(state, row)

    def _can_manage_event_line(current_user: SessionUser, row) -> bool:
        """Check if user can close/manage this event line: creator, their manager, or admin."""
        if current_user.primaryRole == "admin":
            return True
        owner_id = str(row["owner_id"]) if row["owner_id"] else None
        if owner_id == current_user.id:
            return True
        # Check if current user is the manager of the creator
        if owner_id:
            is_manager = state.db.fetchone(
                "SELECT 1 FROM reporting_lines WHERE manager_user_id = ? AND report_user_id = ? AND effective_to IS NULL",
                (current_user.id, owner_id),
            )
            if is_manager:
                return True
        return False

    @app.post("/api/v1/event-lines/{event_line_id}/close")
    def close_event_line(
        event_line_id: str,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> dict:
        row = _event_line_row_or_404(state, event_line_id, current_user.organizationId)
        if str(row["status"]) in ("done", "archived"):
            return {"status": str(row["status"])}
        if not _can_manage_event_line(current_user, row):
            raise HTTPException(status_code=403, detail="只有事件线创建者、其上级主管或管理员可以结束事件线。")
        timestamp = now_iso()
        state.db.execute(
            "UPDATE event_lines SET status = 'archived', closed_at = ?, closed_by_user_id = ?, updated_at = ? WHERE id = ? AND organization_id = ?",
            (timestamp, current_user.id, timestamp, event_line_id, current_user.organizationId),
        )
        _record_event_line_activity(state, event_line_id, "manual_note", event_line_id, current_user.id, "结束事件线", "事件线已归档")
        # Send notification to all participants
        participant_ids = [str(item) for item in from_json(row["participant_ids_json"], []) if str(item)]
        notify_user_ids = [uid for uid in participant_ids if uid != current_user.id]
        if notify_user_ids:
            operator_row = state.db.fetchone("SELECT full_name FROM employee_accounts WHERE id = ?", (current_user.id,))
            operator_name = str(operator_row["full_name"]) if operator_row else current_user.id
            event_line_name = str(row["name"])
            notify_title = f"事件线已结束：{event_line_name}"
            notify_desc = f"{operator_name} 于 {timestamp[:10]} 结束了事件线「{event_line_name}」"
            list_id = _default_list_id(state, current_user.organizationId)
            if list_id:
                notify_task_id = new_id("task")
                state.db.execute(
                    """
                    INSERT INTO tasks(
                        id, organization_id, title, description, creator_id, owner_id, priority, list_id,
                        progress_status, source_type, source_id, scope_mode, event_line_id,
                        tags_json, tag_ids_json, created_at, updated_at
                    ) VALUES(?, ?, ?, ?, ?, ?, 'normal', ?, 'inbox', 'event_line_notification', ?, 'COLLAB_SHARED', ?, '[]', '[]', ?, ?)
                    """,
                    (notify_task_id, current_user.organizationId, notify_title, notify_desc,
                     current_user.id, current_user.id, list_id, event_line_id, event_line_id, timestamp, timestamp),
                )
                collab_rows = [(notify_task_id, uid, idx, 0, "pending", None, timestamp, timestamp)
                               for idx, uid in enumerate(notify_user_ids)]
                state.db.executemany(
                    "INSERT INTO task_collaborators(task_id, user_id, order_index, is_owner, inbox_status, handled_at, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                    collab_rows,
                )
        return {"status": "archived"}

    @app.post("/api/v1/event-lines/{event_line_id}/reopen")
    def reopen_event_line(
        event_line_id: str,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> dict:
        row = _event_line_row_or_404(state, event_line_id, current_user.organizationId)
        if not _can_manage_event_line(current_user, row):
            raise HTTPException(status_code=403, detail="只有事件线创建者、其上级主管或管理员可以重新打开事件线。")
        timestamp = now_iso()
        state.db.execute(
            "UPDATE event_lines SET status = 'active', closed_at = NULL, closed_by_user_id = NULL, updated_at = ? WHERE id = ? AND organization_id = ?",
            (timestamp, event_line_id, current_user.organizationId),
        )
        _record_event_line_activity(state, event_line_id, "manual_note", event_line_id, current_user.id, "重新打开事件线", "事件线已恢复为活跃")
        return {"status": "active"}

    @app.delete("/api/v1/event-lines/{event_line_id}")
    def delete_event_line(
        event_line_id: str,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> dict:
        row = _event_line_row_or_404(state, event_line_id, current_user.organizationId)
        # Only admin can delete event lines
        if current_user.primaryRole != "admin":
            raise HTTPException(status_code=403, detail="只有管理员可以删除事件线。")
        # Can only delete event lines with zero associated tasks
        task_count = int(state.db.scalar(
            "SELECT COUNT(1) FROM tasks WHERE event_line_id = ? AND organization_id = ?",
            (event_line_id, current_user.organizationId),
        ) or 0)
        if task_count > 0:
            raise HTTPException(status_code=403, detail="事件线已有关联任务，不能删除，请使用「结束事件线」功能进行归档。")
        counts = _event_line_dependency_counts(state, event_line_id, current_user.organizationId)
        state.db.execute(
            "UPDATE tasks SET event_line_id = NULL, updated_at = ? WHERE event_line_id = ? AND organization_id = ?",
            (now_iso(), event_line_id, current_user.organizationId),
        )
        state.db.execute(
            "DELETE FROM event_lines WHERE id = ? AND organization_id = ?",
            (event_line_id, current_user.organizationId),
        )
        return {"status": "deleted", "counts": counts}

    @app.get("/api/v1/tasks/{task_id}/plan-link", response_model=TaskPlanLinkRecord | None)
    def get_task_plan_link(
        task_id: str,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> TaskPlanLinkRecord | None:
        task_row = _task_row_or_404(state, task_id)
        if str(task_row["organization_id"]) != current_user.organizationId:
            raise HTTPException(status_code=404, detail="Task not found")
        row = _task_plan_link_row(state, task_id)
        return _task_plan_link_record(row) if row else None

    @app.post("/api/v1/tasks/{task_id}/plan-link/recompute", response_model=TaskPlanLinkRecord | None)
    def recompute_task_plan_link(
        task_id: str,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> TaskPlanLinkRecord | None:
        task_row = _task_row_or_404(state, task_id)
        if str(task_row["organization_id"]) != current_user.organizationId:
            raise HTTPException(status_code=404, detail="Task not found")
        row = _sync_task_plan_link(state, task_row, _task_org_link_row(state, task_id))
        _record_activity(state, task_id, current_user.id, "plan_link_recomputed", {})
        return _task_plan_link_record(row) if row else None

    @app.patch("/api/v1/tasks/{task_id}/plan-link", response_model=TaskPlanLinkRecord | None)
    def patch_task_plan_link(
        task_id: str,
        payload: TaskPlanLinkUpsertPayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> TaskPlanLinkRecord | None:
        task_row = _task_row_or_404(state, task_id)
        task_link_row = _task_org_link_row(state, task_id)
        if str(task_row["organization_id"]) != current_user.organizationId:
            raise HTTPException(status_code=404, detail="Task not found")
        if not _can_review_task(state, current_user, task_row, task_link_row):
            raise HTTPException(status_code=403, detail="你当前没有调整任务计划挂接的权限")
        if payload.departmentPlanItemId is None and payload.focusItemId is None:
            state.db.execute("DELETE FROM task_plan_links WHERE task_id = ?", (task_id,))
            _record_activity(state, task_id, current_user.id, "plan_link_cleared", {})
            return None
        focus_item_id = payload.focusItemId
        if payload.departmentPlanItemId:
            item_row = state.db.fetchone(
                "SELECT * FROM org_department_plan_items WHERE id = ? AND organization_id = ?",
                (payload.departmentPlanItemId, current_user.organizationId),
            )
            if not item_row:
                raise HTTPException(status_code=400, detail="无效的部门计划项")
            focus_item_id = focus_item_id or (str(item_row["focus_item_id"]) if item_row["focus_item_id"] else None)
        if focus_item_id:
            focus_row = state.db.fetchone(
                "SELECT id FROM org_focus_items WHERE id = ? AND organization_id = ?",
                (focus_item_id, current_user.organizationId),
            )
            if not focus_row:
                raise HTTPException(status_code=400, detail="无效的机构目标")
        state.db.execute(
            """
            INSERT OR REPLACE INTO task_plan_links(
                task_id, organization_id, department_plan_item_id, focus_item_id, linked_by, confidence, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                current_user.organizationId,
                payload.departmentPlanItemId,
                focus_item_id,
                payload.linkedBy,
                payload.confidence,
                now_iso(),
            ),
        )
        _record_activity(
            state,
            task_id,
            current_user.id,
            "plan_link_updated",
            {
                "departmentPlanItemId": payload.departmentPlanItemId or "",
                "focusItemId": focus_item_id or "",
                "linkedBy": payload.linkedBy,
                "confidence": payload.confidence,
            },
        )
        row = _task_plan_link_row(state, task_id)
        return _task_plan_link_record(row) if row else None

    @app.get("/api/v1/support-requests", response_model=list[SupportRequestRecord])
    def list_support_requests(
        status_filter: str | None = Query(default=None, alias="status"),
        task_id: str | None = Query(default=None, alias="taskId"),
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> list[SupportRequestRecord]:
        binding_row = _org_binding_row_for_user(state, current_user.organizationId, current_user.id)
        department_id = str(binding_row["department_id"]) if binding_row and binding_row["department_id"] else None
        query = ["SELECT * FROM support_requests WHERE organization_id = ?"]
        params: list[object] = [current_user.organizationId]
        if task_id:
            query.append("AND task_id = ?")
            params.append(task_id)
        if status_filter:
            query.append("AND status = ?")
            params.append(status_filter)
        if current_user.primaryRole != "admin":
            query.append(
                "AND (requester_user_id = ? OR (target_scope = 'manager' AND target_ref_id = ?) OR (target_scope = 'department' AND target_ref_id = ?) OR target_scope = 'organization')"
            )
            params.extend([current_user.id, current_user.id, department_id or "__none__"])
        query.append("ORDER BY updated_at DESC")
        rows = state.db.fetchall(" ".join(query), tuple(params))
        return [_support_request_record(row) for row in rows]

    @app.post("/api/v1/support-requests", response_model=SupportRequestRecord)
    def create_support_request(
        payload: SupportRequestCreatePayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> SupportRequestRecord:
        task_row = None
        if payload.taskId:
            task_row = _task_row_or_404(state, payload.taskId)
            if str(task_row["organization_id"]) != current_user.organizationId:
                raise HTTPException(status_code=404, detail="Task not found")
        event_line_id = payload.eventLineId or (str(task_row["event_line_id"]) if task_row and task_row["event_line_id"] else None)
        if event_line_id:
            _event_line_row_or_404(state, event_line_id, current_user.organizationId)
        timestamp = now_iso()
        request_id = new_id("support")
        state.db.execute(
            """
            INSERT INTO support_requests(
                id, organization_id, task_id, requester_user_id, target_scope, target_ref_id, request_type, urgency, summary, status, resolution_note, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', '', ?, ?)
            """,
            (
                request_id,
                current_user.organizationId,
                payload.taskId,
                current_user.id,
                payload.targetScope,
                payload.targetRefId,
                payload.requestType,
                payload.urgency,
                payload.summary.strip(),
                timestamp,
                timestamp,
            ),
        )
        if payload.taskId:
            _record_activity(state, payload.taskId, current_user.id, "support_requested", payload.model_dump())
        _record_event_line_activity(
            state,
            event_line_id,
            "support_request",
            request_id,
            current_user.id,
            "创建支持请求",
            payload.summary.strip(),
            {"requestType": payload.requestType, "targetScope": payload.targetScope},
        )
        row = state.db.fetchone("SELECT * FROM support_requests WHERE id = ?", (request_id,))
        return _support_request_record(row)

    @app.post("/api/v1/support-requests/{request_id}/resolve", response_model=SupportRequestRecord)
    def resolve_support_request(
        request_id: str,
        payload: SupportRequestResolvePayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> SupportRequestRecord:
        row = state.db.fetchone("SELECT * FROM support_requests WHERE id = ?", (request_id,))
        if not row or str(row["organization_id"]) != current_user.organizationId:
            raise HTTPException(status_code=404, detail="Support request not found")
        binding_row = _org_binding_row_for_user(state, current_user.organizationId, current_user.id)
        department_id = str(binding_row["department_id"]) if binding_row and binding_row["department_id"] else None
        can_resolve = current_user.primaryRole == "admin" or str(row["requester_user_id"]) == current_user.id
        if not can_resolve and str(row["target_scope"]) == "manager" and str(row["target_ref_id"] or "") == current_user.id:
            can_resolve = True
        if not can_resolve and str(row["target_scope"]) == "department" and department_id and str(row["target_ref_id"] or "") == department_id:
            can_resolve = True
        if not can_resolve:
            raise HTTPException(status_code=403, detail="你当前没有处理该支持请求的权限")
        state.db.execute(
            "UPDATE support_requests SET status = ?, resolution_note = ?, updated_at = ? WHERE id = ?",
            (payload.status, payload.resolutionNote.strip(), now_iso(), request_id),
        )
        updated = state.db.fetchone("SELECT * FROM support_requests WHERE id = ?", (request_id,))
        if updated and updated["task_id"]:
            _record_activity(
                state,
                str(updated["task_id"]),
                current_user.id,
                "support_request_resolved",
                {"requestId": request_id, "status": payload.status, "resolutionNote": payload.resolutionNote.strip()},
            )
            task_row = _task_row_or_404(state, str(updated["task_id"]))
            _record_event_line_activity(
                state,
                str(task_row["event_line_id"]) if task_row["event_line_id"] else None,
                "support_request",
                request_id,
                current_user.id,
                "处理支持请求",
                payload.resolutionNote.strip() or f"支持请求状态更新为 {payload.status}",
                {"status": payload.status},
            )
        return _support_request_record(updated)

    @app.get("/api/v1/consultation/knowledge-requests", response_model=list[ConsultationKnowledgeRequestRecord])
    def list_consultation_knowledge_requests(
        status_filter: str | None = Query(default=None, alias="status"),
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> list[ConsultationKnowledgeRequestRecord]:
        query = [
            """
            SELECT
                req.*,
                ans.client_id,
                ans.client_name,
                ans.task_id,
                ans.event_line_id,
                ans.question,
                ans.answer,
                author.full_name AS requested_by_name
            FROM consultation_knowledge_requests req
            JOIN consultation_answers ans ON ans.id = req.answer_id
            LEFT JOIN employee_accounts author ON author.id = req.requested_by_user_id
            WHERE req.organization_id = ?
            """
        ]
        params: list[object] = [current_user.organizationId]
        if status_filter:
            query.append("AND req.status = ?")
            params.append(status_filter)
        if current_user.primaryRole != "admin":
            query.append("AND req.requested_by_user_id = ?")
            params.append(current_user.id)
        query.append("ORDER BY req.updated_at DESC")
        rows = state.db.fetchall(" ".join(query), tuple(params))
        return [_consultation_knowledge_request_record(row) for row in rows]

    @app.post("/api/v1/consultation/knowledge-requests", response_model=ConsultationKnowledgeRequestRecord)
    def create_consultation_knowledge_request(
        payload: ConsultationKnowledgeRequestCreatePayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> ConsultationKnowledgeRequestRecord:
        if payload.taskId:
            task_row = _task_row_or_404(state, payload.taskId)
            if str(task_row["organization_id"]) != current_user.organizationId:
                raise HTTPException(status_code=404, detail="Task not found")
        if payload.eventLineId:
            _event_line_row_or_404(state, payload.eventLineId, current_user.organizationId)
        return _create_consultation_knowledge_request_internal(
            state,
            current_user=current_user,
            target=payload.target,
            question=payload.question,
            answer=payload.answer,
            client_id=payload.clientId,
            client_name=payload.clientName,
            task_id=payload.taskId,
            event_line_id=payload.eventLineId,
            source="mobile_consult",
        )

    @app.post("/api/v1/consultation/knowledge-requests/{request_id}/status", response_model=ConsultationKnowledgeRequestRecord)
    def update_consultation_knowledge_request(
        request_id: str,
        payload: ConsultationKnowledgeRequestUpdatePayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> ConsultationKnowledgeRequestRecord:
        row = _consultation_request_row_or_404(state, request_id, current_user.organizationId)
        can_update = current_user.primaryRole == "admin" or str(row["requested_by_user_id"]) == current_user.id
        if not can_update:
            raise HTTPException(status_code=403, detail="你当前没有处理该沉淀请求的权限")

        timestamp = now_iso()
        normalized_error = payload.errorMessage.strip() or None
        completed_at = timestamp if payload.status == "completed" else None
        if payload.status == "processing":
            normalized_error = None
        state.db.execute(
            """
            UPDATE consultation_knowledge_requests
            SET status = ?, error_message = ?, local_document_id = ?, local_document_path = ?, completed_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.status,
                normalized_error,
                payload.localDocumentId,
                payload.localDocumentPath,
                completed_at,
                timestamp,
                request_id,
            ),
        )
        _log_audit(
            state,
            "consultation.knowledge_request_updated",
            actor_user_id=current_user.id,
            target_user_id=None,
            detail={
                "requestId": request_id,
                "status": payload.status,
                "localDocumentId": payload.localDocumentId or "",
                "localDocumentPath": payload.localDocumentPath or "",
            },
        )
        updated_row = _consultation_request_row_or_404(state, request_id, current_user.organizationId)
        return _consultation_knowledge_request_record(updated_row)

    # ── Consultation Chat (real AI) ─────────────────

    @app.post("/api/v1/consultation/chat", response_model=ConsultationChatResponse)
    async def consultation_chat(
        payload: ConsultationChatPayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> ConsultationChatResponse:
        from app.smart_input import _qwen_api_key, DEFAULT_QWEN_MODEL

        api_key = _qwen_api_key()
        if not api_key:
            raise HTTPException(status_code=503, detail="AI 服务暂不可用：未配置 API Key（请设置 ARK_API_KEY 环境变量）。")

        # Build context from client/task/event-line info
        context_parts: list[str] = []
        if payload.clientName:
            context_parts.append(f"当前客户：{payload.clientName}")
        if payload.eventLineId:
            try:
                el_row = _event_line_row_or_404(state, payload.eventLineId, current_user.organizationId)
                el_name = str(el_row["name"]) if el_row["name"] else ""
                el_summary = str(el_row["summary"]) if el_row["summary"] else ""
                el_blocker = str(el_row["current_blocker"]) if el_row["current_blocker"] else ""
                el_next = str(el_row["next_step"]) if el_row["next_step"] else ""
                if el_name:
                    context_parts.append(f"事件线：{el_name}")
                if el_summary:
                    context_parts.append(f"事件线摘要：{el_summary}")
                if el_blocker:
                    context_parts.append(f"当前阻塞：{el_blocker}")
                if el_next:
                    context_parts.append(f"下一步：{el_next}")
            except HTTPException:
                pass
        if payload.taskContext:
            context_parts.append(f"用户当前任务上下文：{payload.taskContext}")

        # ── Desktop knowledge (DNA + surrogates) ──
        dna_context = ""
        dna_doc_map: dict[str, str] = {}
        surrogate_overviews: list[str] = []
        resolved_desktop_client_id = payload.clientId
        if payload.clientId or payload.clientName:
            try:
                import sqlite3 as _sqlite3
                from app.knowledge_store import find_desktop_app_db_path

                desktop_db_path = find_desktop_app_db_path()
                if desktop_db_path is not None:
                    dconn = _sqlite3.connect(str(desktop_db_path))
                    dconn.row_factory = _sqlite3.Row

                    # Resolve desktop client_id: try direct match first, then fallback by name
                    if payload.clientId:
                        check = dconn.execute("SELECT id FROM clients WHERE id = ?", (payload.clientId,)).fetchone()
                        if check:
                            resolved_desktop_client_id = payload.clientId
                        elif payload.clientName:
                            name_match = dconn.execute(
                                "SELECT id FROM clients WHERE name = ? OR alias = ? LIMIT 1",
                                (payload.clientName, payload.clientName),
                            ).fetchone()
                            if name_match:
                                resolved_desktop_client_id = str(name_match["id"])
                    elif payload.clientName:
                        name_match = dconn.execute(
                            "SELECT id FROM clients WHERE name = ? OR alias = ? LIMIT 1",
                            (payload.clientName, payload.clientName),
                        ).fetchone()
                        if name_match:
                            resolved_desktop_client_id = str(name_match["id"])

                    # Read DNA documents
                    dna_parts: list[str] = []
                    if resolved_desktop_client_id:
                        dna_docs = dconn.execute(
                            "SELECT module_key, title, summary, normalized_text FROM client_dna_documents WHERE client_id = ?",
                            (resolved_desktop_client_id,),
                        ).fetchall()
                        for doc in dna_docs:
                            text = str(doc["normalized_text"] or doc["summary"] or "")
                            if text.startswith('{"prompt'):
                                continue
                            module = str(doc["module_key"] or "")
                            title = str(doc["title"] or module)
                            if module:
                                dna_doc_map[module] = text
                            dna_parts.append(f"【{title}】\n{text[:2000]}")

                    # Read surrogates (enriched summaries + profile blocks)
                    surrogate_parts: list[str] = []
                    if resolved_desktop_client_id:
                        surrogates = dconn.execute(
                            """SELECT title, overview_summary, retrieval_summary, document_role, source_type
                               FROM knowledge_surrogates
                               WHERE client_id = ? AND source_type = 'memory_answer'
                               ORDER BY updated_at DESC LIMIT 10""",
                            (resolved_desktop_client_id,),
                        ).fetchall()
                        for s in surrogates:
                            s_title = str(s["title"] or "")
                            s_overview = str(s["overview_summary"] or "")
                            s_retrieval = str(s["retrieval_summary"] or "")
                            if s_overview:
                                surrogate_overviews.append(s_overview)
                                surrogate_parts.append(f"【{s_title}】\n{s_overview[:1500]}")

                    dconn.close()

                    all_parts = surrogate_parts + dna_parts  # profile blocks first, then DNA
                    if all_parts:
                        dna_context = "\n\n客户知识档案：\n" + "\n---\n".join(all_parts)
            except Exception as dna_err:
                logger.warning("Desktop knowledge read failed: %s", dna_err)
        logger.info("Desktop context for client %s (resolved: %s): %d chars", payload.clientId, resolved_desktop_client_id, len(dna_context))

        # ── Vector knowledge retrieval (semantic search) ──
        knowledge_context = ""
        try:
            from app.knowledge_store import query_knowledge
            # Try with resolved desktop client_id first, then original payload clientId
            search_client_id = resolved_desktop_client_id or payload.clientId
            vector_snippets = await asyncio.to_thread(
                query_knowledge,
                organization_id=current_user.organizationId,
                query=payload.message,
                n_results=20,
                client_id=search_client_id,
            )
            # If no results with resolved id, try without client_id filter
            if not vector_snippets and search_client_id:
                vector_snippets = await asyncio.to_thread(
                    query_knowledge,
                    organization_id=current_user.organizationId,
                    query=payload.message,
                    n_results=20,
                    client_id=None,
                )
            if vector_snippets:
                knowledge_context = "\n\n相关知识参考：\n" + "\n---\n".join(
                    snippet[:1200] for snippet in vector_snippets[:10]
                )
        except Exception as vec_err:
            logger.warning("Vector knowledge query failed: %s", vec_err)

        # ── Fallback: recent consultation answers from DB ──
        if not knowledge_context and payload.clientId:
            recent_answers = state.db.fetchall(
                """SELECT question, answer FROM consultation_answers
                   WHERE organization_id = ? AND client_id = ?
                   ORDER BY created_at DESC LIMIT 5""",
                (current_user.organizationId, payload.clientId),
            )
            if recent_answers:
                snippets = []
                for row in recent_answers:
                    q = str(row["question"]) if row["question"] else ""
                    a = str(row["answer"]) if row["answer"] else ""
                    if q and a:
                        snippets.append(f"Q: {q[:200]}\nA: {a[:400]}")
                if snippets:
                    knowledge_context = "\n\n已有知识沉淀：\n" + "\n---\n".join(snippets[:3])

        normalized_message = payload.message.strip()
        intro_request = any(
            keyword in normalized_message
            for keyword in ("介绍", "简介", "是谁", "做什么", "背景", "全称")
        )
        has_client_knowledge = bool(dna_context.strip())
        intro_context = ""
        if has_client_knowledge and intro_request:
            intro_parts: list[str] = []
            if surrogate_overviews:
                intro_parts.append(f"【战略陪伴记忆】\n{surrogate_overviews[0][:900]}")
            for module_key, title in (
                ("organization_intro", "组织介绍"),
                ("business_intro", "项目与业务介绍"),
                ("market_intro", "市场背景介绍"),
                ("team_intro", "团队介绍"),
            ):
                text = dna_doc_map.get(module_key, "").strip()
                if text:
                    limit = 1400 if module_key in {"organization_intro", "business_intro"} else 900
                    intro_parts.append(f"【{title}】\n{text[:limit]}")
            if intro_parts:
                intro_context = "\n\n客户知识档案：\n" + "\n---\n".join(intro_parts)

        model_name = os.getenv("YIYU_CONSULTATION_CHAT_MODEL", os.getenv("YIYU_SMART_INPUT_MODEL", DEFAULT_QWEN_MODEL))

        import httpx
        terse_request = "只回答" in payload.message or len(normalized_message) <= 40
        # Role boundary: prevent confusing consultant team with client team
        role_boundary = (
            "\n\n【角色边界 — 严格遵守】\n"
            "- 益语智库是顾问方/服务方，顾源源是益语智库的创始人。\n"
            "- 当前客户是合作对象，不是益语智库的一部分。\n"
            "- 除非用户明确问益语智库、你们、顾问方、服务方式，否则回答对象默认是当前客户。\n"
            "- 绝对不要把益语智库的人名（如顾源源）、益语智库的业务介绍当成客户本身的信息。\n"
            "- 如果资料中出现益语智库团队成员参与客户工作的描述，要明确区分：谁是顾问方的人，谁是客户方的人。\n"
        )

        if has_client_knowledge and intro_request:
            system_prompt = (
                "你是益语智库的资深战略顾问。下面是客户的知识档案。"
                "你必须严格依据这些资料直接回答，禁止说\"缺乏信息\"\"上下文不足\"\"无法介绍\"。\n"
                "请简要介绍这个客户，默认按三段回答：它是谁、它做什么、当前战略重点。\n"
                "优先综合组织介绍、项目与业务介绍、市场背景介绍、团队介绍和战略陪伴记忆，不要只摘抄一句原文。"
            )
            system_prompt += role_boundary
            if context_parts:
                system_prompt += "\n\n当前上下文：\n" + "\n".join(context_parts)
            system_prompt += intro_context or dna_context
            user_prompt = normalized_message
        else:
            system_prompt = (
                "你是益语智库的资深战略顾问。你帮助用户基于客户合作上下文回答问题、"
                "准备会议要点、分析推进策略、梳理阻塞与下一步。\n"
                "如果系统提供了「相关知识参考」或「已有知识沉淀」或「客户知识档案」，必须优先使用这些内容作答；"
                "当参考里已经包含与用户问题直接对应的结论时，直接提炼并复述该结论，不要泛化改写成空泛建议。\n"
                "如果上下文不足，坦诚说明并给出通用建议。\n"
                "【矛盾处理】如果不同文档或不同时期的资料之间存在矛盾（如方向调整、目标变更），请以最新日期的资料为准，并标注「注意：此观点与早期资料有所不同，以最新结论为准」。"
            )
            system_prompt += role_boundary
            system_prompt += (
                "\n\n【回答风格——必须严格遵守】\n"
                "- 先给结论，再给关键论据，不要铺垫\n"
                "- **严禁长段落**：任何一段文字不得超过 3 句话。超过 3 句必须换段（插入空行）\n"
                "- **编号必须独立成段**：凡出现「第一」「第二」「第三」「首先」「其次」「最后」等序号词，"
                "每个序号点必须另起一段，序号点之间用空行分隔，绝对不能把多个序号点写在同一段里\n"
                "- 多层结构用「一、二、三」做大标题，每层下用「- 」列要点\n"
                "- 关键结论用 **加粗**（加粗完整判断句，不要只加粗关键词）\n"
                "- 根据问题复杂度自由决定总长度，但必须保持短段落、多分层的排版节奏\n"
            )
            if context_parts:
                system_prompt += "\n当前上下文：\n" + "\n".join(context_parts)
            if dna_context:
                system_prompt += dna_context
                system_prompt += (
                    "\n\n【回答强约束】\n"
                    '- 系统已经提供了客户知识档案，禁止回答"缺乏信息""上下文不足""无法介绍"。\n'
                    "- 必须先提炼客户知识档案里的结论，再组织成回答，不能忽略档案内容。\n"
                )
            if knowledge_context:
                system_prompt += knowledge_context
            user_prompt = normalized_message
        chat_payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.5,
            "top_p": 0.95,
            "max_tokens": 2000 if (has_client_knowledge and intro_request) else (600 if terse_request else 2500),
            "stream": False,
            "enable_thinking": True,
        }
        read_timeout = 60.0 if (has_client_knowledge and intro_request) else 30.0
        timeout = httpx.Timeout(timeout=None, connect=8.0, read=read_timeout, write=8.0, pool=8.0)
        try:
            response = await asyncio.to_thread(
                _sync_qwen_chat, api_key, chat_payload, timeout
            )
        except Exception as error:
            raise HTTPException(status_code=502, detail=f"AI 回复失败：{error}") from error

        # Auto-ingest Q&A into vector knowledge store (fire-and-forget)
        async def _ingest_bg():
            try:
                from app.knowledge_store import ingest_consultation_answer
                await asyncio.to_thread(
                    ingest_consultation_answer,
                    organization_id=current_user.organizationId,
                    question=payload.message,
                    answer=response,
                    client_id=payload.clientId,
                    client_name=payload.clientName,
                    event_line_id=payload.eventLineId,
                )
            except Exception as ingest_err:
                logger.warning("Knowledge ingest failed: %s", ingest_err)
        asyncio.create_task(_ingest_bg())

        return ConsultationChatResponse(reply=response, model=model_name)

    @app.get("/api/public/smart-input-audio/{file_key}")
    def get_public_smart_input_audio(file_key: str) -> FileResponse:
        if not re.fullmatch(r"[0-9a-f]{32}\.[0-9A-Za-z]{1,8}", file_key):
            raise HTTPException(status_code=404, detail="File not found")
        audio_path = state.data_dir / "smart-input-audio" / file_key
        if not audio_path.exists() or not audio_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        media_type = mimetypes.guess_type(audio_path.name)[0] or "application/octet-stream"
        return FileResponse(audio_path, media_type=media_type, filename=audio_path.name)

    @app.get("/api/public/task-attachments/{attachment_id}")
    def get_public_task_attachment(attachment_id: str) -> FileResponse:
        row = state.db.fetchone("SELECT * FROM task_attachments WHERE id = ?", (attachment_id,))
        if row is None and _has_event_line_attachments_table():
            row = state.db.fetchone("SELECT * FROM event_line_attachments WHERE id = ?", (attachment_id,))
        if row is None:
            raise HTTPException(status_code=404, detail="File not found")
        attachment_path = state.data_dir / str(row["path"])
        if not attachment_path.exists() or not attachment_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        media_type = str(row["mime_type"] or mimetypes.guess_type(attachment_path.name)[0] or "application/octet-stream")
        return FileResponse(attachment_path, media_type=media_type, filename=attachment_path.name)

    @app.get("/api/public/task-attachments/{attachment_id}/thumbnail")
    def get_attachment_thumbnail(attachment_id: str, max_width: int = 600) -> Response:
        row = state.db.fetchone("SELECT * FROM task_attachments WHERE id = ?", (attachment_id,))
        if row is None and _has_event_line_attachments_table():
            row = state.db.fetchone("SELECT * FROM event_line_attachments WHERE id = ?", (attachment_id,))
        if row is None:
            raise HTTPException(status_code=404, detail="File not found")
        attachment_path = state.data_dir / str(row["path"])
        if not attachment_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        mime = str(row["mime_type"] or "").lower()
        if not mime.startswith("image/"):
            raise HTTPException(status_code=404, detail="Not an image")
        try:
            from PIL import Image
            from io import BytesIO
            img = Image.open(attachment_path)
            if img.width > max_width:
                ratio = max_width / img.width
                img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
            buf = BytesIO()
            out_format = "JPEG" if mime in ("image/jpeg", "image/jpg") else "PNG"
            img.save(buf, format=out_format, quality=85)
            buf.seek(0)
            return Response(
                content=buf.getvalue(),
                media_type=f"image/{out_format.lower()}",
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"缩略图生成失败: {exc}") from exc

    @app.get("/api/public/task-attachments/{attachment_id}/text-content")
    def get_attachment_text_content(attachment_id: str) -> dict:
        row = state.db.fetchone("SELECT * FROM task_attachments WHERE id = ?", (attachment_id,))
        if row is None and _has_event_line_attachments_table():
            row = state.db.fetchone("SELECT * FROM event_line_attachments WHERE id = ?", (attachment_id,))
        if row is None:
            raise HTTPException(status_code=404, detail="File not found")
        attachment_path = state.data_dir / str(row["path"])
        if not attachment_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        kind = str(row["kind"] or "").lower()
        mime = str(row["mime_type"] or "").lower()
        title = str(row["title"] or attachment_path.name)
        try:
            if kind == "docx" or title.lower().endswith(".docx"):
                from docx import Document as _WordDoc
                doc = _WordDoc(str(attachment_path))
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()][:100]
                return {"title": title, "kind": "docx", "text": "\n".join(paragraphs), "paragraphCount": len(paragraphs)}
            elif kind in ("md", "txt", "csv", "json") or mime.startswith("text/"):
                text = attachment_path.read_text(encoding="utf-8", errors="ignore")[:5000]
                return {"title": title, "kind": kind, "text": text, "paragraphCount": text.count("\n") + 1}
            else:
                return {"title": title, "kind": kind, "text": "", "paragraphCount": 0, "unsupported": True}
        except Exception as exc:
            return {"title": title, "kind": kind, "text": f"内容提取失败: {exc}", "paragraphCount": 0}

    @app.get("/api/public/task-attachments/{attachment_id}/ocr-summary")
    def get_attachment_ocr_summary(attachment_id: str) -> dict:
        row = state.db.fetchone("SELECT * FROM task_attachments WHERE id = ?", (attachment_id,))
        if row is None and _has_event_line_attachments_table():
            row = state.db.fetchone("SELECT * FROM event_line_attachments WHERE id = ?", (attachment_id,))
        if row is None:
            raise HTTPException(status_code=404, detail="File not found")
        mime = str(row["mime_type"] or "").lower()
        if not mime.startswith("image/"):
            return {"title": str(row["title"]), "summary": "", "unsupported": True}
        attachment_path = state.data_dir / str(row["path"])
        if not attachment_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        # Use Ark multimodal to OCR the image
        import base64
        ark_key = (
            os.getenv("ARK_API_KEY", "").strip()
            or os.getenv("VOLCENGINE_API_KEY", "").strip()
        )
        if not ark_key:
            return {"title": str(row["title"]), "summary": "OCR 未配置 API Key", "unsupported": True}
        try:
            img_bytes = attachment_path.read_bytes()
            img_b64 = base64.b64encode(img_bytes).decode()
            resp = httpx.post(
                "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
                headers={"Authorization": f"Bearer {ark_key}", "Content-Type": "application/json"},
                json={
                    "model": os.getenv("YIYU_OCR_MODEL", "ep-m-20260326120641-m4lf6"),
                    "messages": [
                        {"role": "system", "content": "你是票据识别助手。请识别图片中的票据内容，用一行简要概括：类型、金额、日期、付款方/收款方（如果能识别的话）。只返回纯文本，不要 JSON。"},
                        {"role": "user", "content": [
                            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
                            {"type": "text", "text": "请识别这张票据的内容"},
                        ]},
                    ],
                    "max_tokens": 200,
                },
                timeout=15.0,
            )
            if resp.status_code == 200:
                summary = resp.json()["choices"][0]["message"]["content"].strip()
                return {"title": str(row["title"]), "summary": summary}
            return {"title": str(row["title"]), "summary": f"OCR 识别失败 (HTTP {resp.status_code})"}
        except Exception as exc:
            return {"title": str(row["title"]), "summary": f"OCR 识别失败: {exc}"}

    @app.post("/api/v1/event-lines/{event_line_id}/attachments/download-zip")
    def download_event_line_attachments_zip(
        event_line_id: str,
        payload: dict | None = None,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> Response:
        _event_line_row_or_404(state, event_line_id, current_user.organizationId)
        attachment_ids = (payload or {}).get("attachmentIds")
        has_event_line_attachments = _has_event_line_attachments_table()
        if attachment_ids and isinstance(attachment_ids, list):
            placeholders = ",".join("?" for _ in attachment_ids)
            if has_event_line_attachments:
                rows = state.db.fetchall(
                    f"SELECT id, title, path, mime_type, size_bytes FROM task_attachments WHERE event_line_id = ? AND id IN ({placeholders}) UNION ALL SELECT id, title, path, mime_type, size_bytes FROM event_line_attachments WHERE event_line_id = ? AND id IN ({placeholders}) ORDER BY id",
                    (event_line_id, *attachment_ids, event_line_id, *attachment_ids),
                )
            else:
                rows = state.db.fetchall(
                    f"SELECT id, title, path, mime_type, size_bytes FROM task_attachments WHERE event_line_id = ? AND id IN ({placeholders}) ORDER BY id",
                    (event_line_id, *attachment_ids),
                )
        else:
            if has_event_line_attachments:
                rows = state.db.fetchall(
                    "SELECT id, title, path, mime_type, size_bytes FROM task_attachments WHERE event_line_id = ? UNION ALL SELECT id, title, path, mime_type, size_bytes FROM event_line_attachments WHERE event_line_id = ? ORDER BY id",
                    (event_line_id, event_line_id),
                )
            else:
                rows = state.db.fetchall(
                    "SELECT id, title, path, mime_type, size_bytes FROM task_attachments WHERE event_line_id = ? ORDER BY id",
                    (event_line_id,),
                )
        if not rows:
            raise HTTPException(status_code=404, detail="没有可下载的附件")
        import zipfile
        from io import BytesIO
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            seen_names: dict[str, int] = {}
            for row in rows:
                file_path = state.data_dir / str(row["path"])
                if not file_path.exists():
                    continue
                name = str(row["title"] or file_path.name)
                if name in seen_names:
                    seen_names[name] += 1
                    stem, ext = (name.rsplit(".", 1) + [""])[:2]
                    name = f"{stem}_{seen_names[name]}.{ext}" if ext else f"{stem}_{seen_names[name]}"
                else:
                    seen_names[name] = 0
                zf.write(file_path, name)
        buf.seek(0)
        el_row = state.db.fetchone("SELECT name FROM event_lines WHERE id = ?", (event_line_id,))
        zip_name = safe_filename(f"{str(el_row['name'])[:20]}_附件.zip") if el_row else "attachments.zip"
        return Response(
            content=buf.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{zip_name}"'},
        )

    @app.post("/api/v1/mobile/smart-input/task-draft", response_model=SmartTaskDraftResponse)
    async def create_mobile_smart_task_draft(
        request: Request,
        transcriptText: str | None = Form(default=None),
        referenceDate: str | None = Form(default=None),
        currentEventLineId: str | None = Form(default=None),
        audio: UploadFile | None = File(default=None),
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> SmartTaskDraftResponse:
        transcript = (transcriptText or "").strip()
        if not transcript:
            if audio is None:
                raise HTTPException(status_code=400, detail="请先输入或转写自然语言内容。")
            audio_bytes = await audio.read()
            file_name = safe_filename(audio.filename or f"smart-input-{uuid4().hex}.m4a")
            extension = Path(file_name).suffix.lower() or ".m4a"
            file_key = f"{uuid4().hex}{extension}"
            audio_dir = state.data_dir / "smart-input-audio"
            audio_dir.mkdir(parents=True, exist_ok=True)
            audio_path = audio_dir / file_key
            audio_path.write_bytes(audio_bytes)
            public_base_url = _resolve_public_base_url(request)
            public_url = (
                f"{public_base_url}/api/public/smart-input-audio/{file_key}"
                if public_base_url
                else None
            )
            try:
                # Run file ASR in a worker thread so this request does not block the
                # event loop from serving the public audio URL Doubao must fetch.
                transcript = (
                    await asyncio.to_thread(
                        transcribe_audio_with_doubao,
                        audio_bytes,
                        file_name=file_name,
                        mime_type=audio.content_type,
                        public_url=public_url,
                    )
                ).strip()
            except RuntimeError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error
            except Exception as error:
                raise HTTPException(status_code=502, detail=f"语音转写失败：{error}") from error
            finally:
                try:
                    audio_path.unlink(missing_ok=True)
                except Exception:
                    pass
            if not transcript:
                raise HTTPException(status_code=400, detail="语音已上传，但未能识别出有效文本。")

        reference = None
        if referenceDate:
            try:
                reference = datetime.fromisoformat(referenceDate.strip()).date()
            except ValueError:
                raise HTTPException(status_code=400, detail="referenceDate 格式无效，应为 YYYY-MM-DD。") from None

        rows = state.db.fetchall(
            """
            SELECT *
            FROM event_lines
            WHERE organization_id = ?
              AND status != 'archived'
            ORDER BY updated_at DESC
            """,
            (current_user.organizationId,),
        )
        event_lines = [_event_line_record(state, row) for row in rows]
        return build_smart_task_draft(
            transcript,
            event_lines,
            reference_date=reference,
            current_event_line_id=currentEventLineId,
        )

    @app.get("/api/v1/employees/directory", response_model=list[EmployeeRecord])
    def list_employee_directory(
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> list[EmployeeRecord]:
        rows = state.db.fetchall(
            """
            SELECT *
            FROM employee_accounts
            WHERE organization_id = ? AND account_status = 'approved'
            ORDER BY created_at DESC
            """,
            (current_user.organizationId,),
        )
        return [_employee_record(row) for row in rows]

    @app.post("/api/v1/admin/employees/{employee_id}/approve", response_model=EmployeeRecord)
    def approve_employee(
        employee_id: str,
        payload: RolePayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_admin(app, authorization)),
    ) -> EmployeeRecord:
        row = _get_user_or_404(state, employee_id)
        timestamp = now_iso()
        state.db.execute(
            """
            UPDATE employee_accounts
            SET primary_role = ?, account_status = 'approved', approved_at = ?, approved_by = ?, rejected_reason = NULL, disabled_at = NULL, updated_at = ?
            WHERE id = ?
            """,
            (payload.role, timestamp, current_user.id, timestamp, employee_id),
        )
        existing_role = state.db.fetchone("SELECT id FROM employee_role_bindings WHERE user_id = ?", (employee_id,))
        if existing_role:
            state.db.execute("DELETE FROM employee_role_bindings WHERE user_id = ?", (employee_id,))
        state.db.execute(
            "INSERT INTO employee_role_bindings(id, user_id, role, created_at) VALUES(?, ?, ?, ?)",
            (new_id("role"), employee_id, payload.role, timestamp),
        )
        _sync_employee_org_binding_from_account(state, current_user.organizationId, employee_id)
        _log_audit(state, "approve_employee", actor_user_id=current_user.id, target_user_id=employee_id, detail={"role": payload.role})
        return _employee_record(_get_user_or_404(state, employee_id))

    @app.post("/api/v1/admin/employees/{employee_id}/reject", response_model=EmployeeRecord)
    def reject_employee(
        employee_id: str,
        payload: RejectPayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_admin(app, authorization)),
    ) -> EmployeeRecord:
        row = _get_user_or_404(state, employee_id)
        if str(row["id"]) == current_user.id:
            raise HTTPException(status_code=400, detail="不能驳回当前管理员账号")
        timestamp = now_iso()
        state.db.execute(
            """
            UPDATE employee_accounts
            SET account_status = 'rejected', rejected_reason = ?, updated_at = ?
            WHERE id = ?
            """,
            (payload.reason or "账号未通过审核，请联系管理员。", timestamp, employee_id),
        )
        _log_audit(state, "reject_employee", actor_user_id=current_user.id, target_user_id=employee_id, detail={"reason": payload.reason})
        return _employee_record(_get_user_or_404(state, employee_id))

    @app.post("/api/v1/admin/employees/{employee_id}/disable", response_model=EmployeeRecord)
    def disable_employee(employee_id: str, current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_admin(app, authorization))) -> EmployeeRecord:
        if employee_id == current_user.id:
            raise HTTPException(status_code=400, detail="不能停用当前管理员账号")
        timestamp = now_iso()
        state.db.execute(
            "UPDATE employee_accounts SET account_status = 'disabled', disabled_at = ?, updated_at = ? WHERE id = ?",
            (timestamp, timestamp, employee_id),
        )
        _log_audit(state, "disable_employee", actor_user_id=current_user.id, target_user_id=employee_id, detail={})
        return _employee_record(_get_user_or_404(state, employee_id))

    @app.post("/api/v1/admin/employees/{employee_id}/reset-password")
    def admin_reset_password(
        employee_id: str,
        payload: AdminResetPasswordPayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_admin(app, authorization)),
    ) -> dict[str, str]:
        _get_user_or_404(state, employee_id)
        state.db.execute(
            "UPDATE employee_accounts SET password_hash = ?, updated_at = ? WHERE id = ?",
            (hash_password(payload.newPassword), now_iso(), employee_id),
        )
        _log_audit(state, "admin_reset_password", actor_user_id=current_user.id, target_user_id=employee_id, detail={})
        return {"message": "密码已重置"}

    @app.patch("/api/v1/admin/employees/{employee_id}/role", response_model=EmployeeRecord)
    def update_employee_role(
        employee_id: str,
        payload: RolePayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_admin(app, authorization)),
    ) -> EmployeeRecord:
        state.db.execute(
            "UPDATE employee_accounts SET primary_role = ?, updated_at = ? WHERE id = ?",
            (payload.role, now_iso(), employee_id),
        )
        state.db.execute("DELETE FROM employee_role_bindings WHERE user_id = ?", (employee_id,))
        state.db.execute(
            "INSERT INTO employee_role_bindings(id, user_id, role, created_at) VALUES(?, ?, ?, ?)",
            (new_id("role"), employee_id, payload.role, now_iso()),
        )
        _log_audit(state, "change_role", actor_user_id=current_user.id, target_user_id=employee_id, detail={"role": payload.role})
        return _employee_record(_get_user_or_404(state, employee_id))

    @app.patch("/api/v1/admin/employees/{employee_id}/department", response_model=EmployeeRecord)
    def update_employee_department(
        employee_id: str,
        payload: EmployeeDepartmentPayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_admin(app, authorization)),
    ) -> EmployeeRecord:
        department = get_department_entry(payload.departmentId) if payload.departmentId else None
        if payload.departmentId and not department:
            raise HTTPException(status_code=400, detail="请选择有效的部门")
        state.db.execute(
            """
            UPDATE employee_accounts
            SET department_id = ?, department_name = ?, updated_at = ?
            WHERE id = ?
            """,
            (department.id if department else None, department.name if department else None, now_iso(), employee_id),
        )
        _log_audit(
            state,
            "change_department",
            actor_user_id=current_user.id,
            target_user_id=employee_id,
            detail={"departmentId": department.id if department else None},
        )
        _sync_employee_org_binding_from_account(state, current_user.organizationId, employee_id)
        return _employee_record(_get_user_or_404(state, employee_id))

    @app.get("/api/v1/employees/mention-candidates", response_model=list[MentionCandidate])
    def mention_candidates(
        q: str = Query(default=""),
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> list[MentionCandidate]:
        current_row = _get_user_or_404(state, current_user.id)
        recent_ids = [str(item) for item in from_json(current_row["recent_mentions_json"], [])]
        candidate_rows = state.db.fetchall(
            """
            SELECT id, full_name, email, primary_role
            FROM employee_accounts
            WHERE organization_id = ? AND account_status = 'approved'
            ORDER BY full_name COLLATE NOCASE ASC
            """,
            (current_user.organizationId,),
        )
        rows_by_id = {str(row["id"]): row for row in candidate_rows}
        ordered_ids: list[str] = [current_user.id]
        for user_id in recent_ids:
            if user_id != current_user.id and user_id in rows_by_id:
                ordered_ids.append(user_id)
        if q.strip():
            needle = q.strip().lower()
            matched_ids = [
                user_id
                for user_id, row in rows_by_id.items()
                if needle in str(row["full_name"]).lower() or needle in str(row["email"]).lower()
            ]
            ordered_ids = [current_user.id] + [user_id for user_id in ordered_ids[1:] if user_id in matched_ids]
            for user_id in matched_ids:
                if user_id not in ordered_ids and user_id != current_user.id:
                    ordered_ids.append(user_id)
        else:
            for row in candidate_rows:
                user_id = str(row["id"])
                if user_id == current_user.id or user_id in ordered_ids:
                    continue
                ordered_ids.append(user_id)
            ordered_ids = ordered_ids[:6]
        if current_user.id not in rows_by_id:
            ordered_ids = [user_id for user_id in ordered_ids if user_id != current_user.id]
            ordered_ids.insert(0, current_user.id)
            rows_by_id[current_user.id] = current_row
        return [
            MentionCandidate(
                id=user_id,
                fullName=str(rows_by_id[user_id]["full_name"]),
                email=str(rows_by_id[user_id]["email"]),
                primaryRole=str(rows_by_id[user_id]["primary_role"]),
                isSelf=user_id == current_user.id,
            )
            for user_id in ordered_ids
            if user_id in rows_by_id
        ]

    @app.get("/api/v1/settings/tasks", response_model=TaskSettingsRecord)
    def get_task_settings(current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization))) -> TaskSettingsRecord:
        return _get_task_settings(state, current_user)

    @app.post("/api/v1/settings/tasks", response_model=TaskSettingsRecord)
    def update_task_settings(
        payload: TaskSettingsPayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> TaskSettingsRecord:
        current = _get_task_settings(state, current_user)
        next_default_list_id = payload.defaultListId if payload.defaultListId is not None else current.defaultListId
        if next_default_list_id:
            list_row = state.db.fetchone(
                "SELECT * FROM task_lists WHERE id = ? AND organization_id = ?",
                (next_default_list_id, current_user.organizationId),
            )
            if not list_row or list_row["archived_at"]:
                raise HTTPException(status_code=400, detail="默认清单无效")
        timestamp = now_iso()
        next_record = TaskSettingsRecord(
            defaultListId=next_default_list_id,
            defaultPriority=payload.defaultPriority or current.defaultPriority,
            defaultDueDatePreset=payload.defaultDueDatePreset or current.defaultDueDatePreset,
            defaultViewMode=payload.defaultViewMode or current.defaultViewMode,
            listSortMode=payload.listSortMode or current.listSortMode,
            showCompletedTasks=payload.showCompletedTasks if payload.showCompletedTasks is not None else current.showCompletedTasks,
            defaultReviewScope=payload.defaultReviewScope or current.defaultReviewScope,
            autoAssignSelf=payload.autoAssignSelf if payload.autoAssignSelf is not None else current.autoAssignSelf,
            updatedAt=timestamp,
        )
        state.db.execute(
            """
            INSERT OR REPLACE INTO task_settings(
                user_id, organization_id, default_list_id, default_priority, default_due_date_preset,
                default_view_mode, list_sort_mode, show_completed_tasks, default_review_scope,
                auto_assign_self, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                current_user.id,
                current_user.organizationId,
                next_record.defaultListId,
                next_record.defaultPriority,
                next_record.defaultDueDatePreset,
                next_record.defaultViewMode,
                next_record.listSortMode,
                1 if next_record.showCompletedTasks else 0,
                next_record.defaultReviewScope,
                1 if next_record.autoAssignSelf else 0,
                next_record.updatedAt,
            ),
        )
        if next_record.defaultListId:
            state.db.execute(
                "UPDATE task_lists SET is_default = CASE WHEN id = ? THEN 1 ELSE 0 END WHERE organization_id = ?",
                (next_record.defaultListId, current_user.organizationId),
            )
        return _get_task_settings(state, current_user)

    @app.get("/api/v1/task-lists", response_model=TaskListLibraryResponse)
    def get_task_lists(current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization))) -> TaskListLibraryResponse:
        state.db.execute(
            "UPDATE task_lists SET scope = 'org' WHERE organization_id = ? AND (scope IS NULL OR scope = '')",
            (current_user.organizationId,),
        )
        if state.db.scalar(
            "SELECT COUNT(1) AS count FROM task_lists WHERE organization_id = ? AND scope = 'personal'",
            (current_user.organizationId,),
        ) == 0:
            timestamp = now_iso()
            for name, color, sort_order, is_default in [
                ("健身", "#5B7BFE", 10, 1),
                ("约会", "#EC4899", 11, 0),
                ("吃饭", "#F59E0B", 12, 0),
                ("学习", "#10B981", 13, 0),
            ]:
                list_id = new_id("list")
                state.db.execute(
                    """
                    INSERT INTO task_lists(id, organization_id, name, color, sort_order, is_default, scope, archived_at)
                    VALUES(?, ?, ?, ?, ?, ?, 'personal', NULL)
                    """,
                    (list_id, current_user.organizationId, name, color, sort_order, is_default),
                )
            state.db.execute(
                "UPDATE task_lists SET is_default = 0 WHERE organization_id = ? AND scope = 'personal' AND id NOT IN (SELECT id FROM task_lists WHERE organization_id = ? AND scope = 'personal' ORDER BY sort_order ASC LIMIT 1)",
                (current_user.organizationId, current_user.organizationId),
            )
        rows = state.db.fetchall(
            """
            SELECT *
            FROM task_lists
            WHERE organization_id = ?
            ORDER BY CASE WHEN archived_at IS NULL OR archived_at = '' THEN 0 ELSE 1 END,
                     CASE WHEN is_default = 1 THEN 0 ELSE 1 END,
                     sort_order ASC,
                     name COLLATE NOCASE ASC
            """,
            (current_user.organizationId,),
        )
        return TaskListLibraryResponse(lists=[_task_list_record(row) for row in rows])

    @app.post("/api/v1/task-lists", response_model=TaskListRecord)
    def create_task_list(
        payload: TaskListMutationPayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> TaskListRecord:
        if current_user.primaryRole != "admin" and (payload.scope or "org") != "personal":
            raise HTTPException(status_code=403, detail="Only admin can create public task lists")
        trimmed_name = payload.name.strip()
        if not trimmed_name:
            raise HTTPException(status_code=400, detail="清单名称不能为空")
        timestamp = now_iso()
        list_id = new_id("list")
        next_scope = payload.scope or "org"
        is_default = bool(payload.isDefault) or state.db.scalar(
            "SELECT COUNT(1) AS count FROM task_lists WHERE organization_id = ? AND scope = ?",
            (current_user.organizationId, next_scope),
        ) == 0
        sort_order = payload.sortOrder if payload.sortOrder is not None else state.db.scalar(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 AS count FROM task_lists WHERE organization_id = ?",
            (current_user.organizationId,),
        )
        if is_default:
            state.db.execute(
                "UPDATE task_lists SET is_default = 0 WHERE organization_id = ? AND scope = ?",
                (current_user.organizationId, next_scope),
            )
        state.db.execute(
            """
            INSERT INTO task_lists(id, organization_id, name, color, sort_order, is_default, scope, archived_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (list_id, current_user.organizationId, trimmed_name, payload.color.strip(), sort_order, 1 if is_default else 0, next_scope),
        )
        row = state.db.fetchone("SELECT * FROM task_lists WHERE id = ?", (list_id,))
        assert row is not None
        return _task_list_record(row)

    @app.patch("/api/v1/task-lists/{list_id}", response_model=TaskListRecord)
    def update_task_list(
        list_id: str,
        payload: TaskListMutationPayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> TaskListRecord:
        row = state.db.fetchone(
            "SELECT * FROM task_lists WHERE id = ? AND organization_id = ?",
            (list_id, current_user.organizationId),
        )
        if not row:
            raise HTTPException(status_code=404, detail="Task list not found")
        if current_user.primaryRole != "admin" and (payload.scope or str(row["scope"] or "org")) != "personal":
            raise HTTPException(status_code=403, detail="Only admin can update public task lists")
        next_archived_at = str(row["archived_at"]) if row["archived_at"] else None
        next_scope = payload.scope or str(row["scope"] or "org")
        if payload.archived is True:
            active_list_count = state.db.scalar(
                "SELECT COUNT(1) AS count FROM task_lists WHERE organization_id = ? AND scope = ? AND (archived_at IS NULL OR archived_at = '')",
                (current_user.organizationId, next_scope),
            )
            if active_list_count <= 1 and not row["archived_at"]:
                raise HTTPException(status_code=400, detail="至少保留一个可用清单")
            next_archived_at = now_iso()
        elif payload.archived is False:
            next_archived_at = None
        next_is_default = bool(payload.isDefault) if payload.isDefault is not None else bool(int(row["is_default"] or 0))
        if next_archived_at:
            next_is_default = False
        if next_is_default:
            state.db.execute(
                "UPDATE task_lists SET is_default = 0 WHERE organization_id = ? AND scope = ?",
                (current_user.organizationId, next_scope),
            )
        state.db.execute(
            """
            UPDATE task_lists
            SET name = ?, color = ?, sort_order = ?, is_default = ?, scope = ?, archived_at = ?
            WHERE id = ?
            """,
            (
                payload.name.strip(),
                payload.color.strip(),
                payload.sortOrder if payload.sortOrder is not None else int(row["sort_order"] or 0),
                1 if next_is_default else 0,
                next_scope,
                next_archived_at,
                list_id,
            ),
        )
        if next_archived_at and bool(int(row["is_default"] or 0)):
            fallback_row = state.db.fetchone(
                """
                SELECT id
                FROM task_lists
                WHERE organization_id = ? AND scope = ? AND id != ? AND (archived_at IS NULL OR archived_at = '')
                ORDER BY sort_order ASC, name COLLATE NOCASE ASC
                LIMIT 1
                """,
                (current_user.organizationId, next_scope, list_id),
            )
            if fallback_row:
                state.db.execute(
                    "UPDATE task_lists SET is_default = CASE WHEN id = ? THEN 1 ELSE 0 END WHERE organization_id = ? AND scope = ?",
                    (str(fallback_row["id"]), current_user.organizationId, next_scope),
                )
        updated = state.db.fetchone("SELECT * FROM task_lists WHERE id = ?", (list_id,))
        assert updated is not None
        return _task_list_record(updated)

    @app.delete("/api/v1/task-lists/{list_id}")
    def delete_task_list(
        list_id: str,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> dict[str, bool]:
        row = state.db.fetchone(
            "SELECT * FROM task_lists WHERE id = ? AND organization_id = ?",
            (list_id, current_user.organizationId),
        )
        if not row:
            raise HTTPException(status_code=404, detail="Task list not found")
        if current_user.primaryRole != "admin" and str(row["scope"] or "org") != "personal":
            raise HTTPException(status_code=403, detail="Only admin can delete public task lists")
        task_count = state.db.scalar(
            "SELECT COUNT(1) AS count FROM tasks WHERE organization_id = ? AND list_id = ?",
            (current_user.organizationId, list_id),
        )
        if task_count > 0:
            raise HTTPException(status_code=400, detail="该清单已有任务，请先归档，不支持直接删除")
        if state.db.scalar(
            "SELECT COUNT(1) AS count FROM task_lists WHERE organization_id = ? AND scope = ?",
            (current_user.organizationId, str(row["scope"] or "org")),
        ) <= 1:
            raise HTTPException(status_code=400, detail="至少保留一个清单")
        if bool(int(row["is_default"] or 0)):
            fallback_row = state.db.fetchone(
                "SELECT id FROM task_lists WHERE organization_id = ? AND scope = ? AND id != ? ORDER BY sort_order ASC, name COLLATE NOCASE ASC LIMIT 1",
                (current_user.organizationId, str(row["scope"] or "org"), list_id),
            )
            if fallback_row:
                state.db.execute(
                    "UPDATE task_lists SET is_default = CASE WHEN id = ? THEN 1 ELSE 0 END WHERE organization_id = ? AND scope = ?",
                    (str(fallback_row["id"]), current_user.organizationId, str(row["scope"] or "org")),
                )
        state.db.execute("DELETE FROM task_lists WHERE id = ?", (list_id,))
        return {"deleted": True}

    @app.get("/api/v1/task-tags", response_model=TaskTagLibraryResponse)
    def get_task_tags(current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization))) -> TaskTagLibraryResponse:
        return TaskTagLibraryResponse(tags=_visible_task_tags(state, current_user))

    @app.post("/api/v1/task-tags", response_model=TaskTagRecord)
    def create_task_tag(
        payload: TaskTagMutationPayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> TaskTagRecord:
        return _ensure_task_tag(state, current_user, payload.name, payload.scope, payload.color)

    @app.patch("/api/v1/task-tags/{tag_id}", response_model=TaskTagRecord)
    def update_task_tag(
        tag_id: str,
        payload: TaskTagMutationPayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> TaskTagRecord:
        row = state.db.fetchone("SELECT * FROM task_tag_library WHERE id = ?", (tag_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Tag not found")
        timestamp = now_iso()
        archived_at = timestamp if payload.archived else None
        state.db.execute(
            "UPDATE task_tag_library SET name = ?, color = ?, scope = ?, archived_at = ?, updated_at = ? WHERE id = ?",
            (payload.name, payload.color or str(row["color"]), payload.scope, archived_at, timestamp, tag_id),
        )
        updated = state.db.fetchone("SELECT * FROM task_tag_library WHERE id = ?", (tag_id,))
        assert updated is not None
        return _task_tag_record(updated)

    @app.delete("/api/v1/task-tags/{tag_id}")
    def delete_task_tag(
        tag_id: str,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> dict[str, bool]:
        row = state.db.fetchone("SELECT * FROM task_tag_library WHERE id = ?", (tag_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Tag not found")
        state.db.execute("DELETE FROM task_tag_library WHERE id = ?", (tag_id,))
        return {"deleted": True}

    @app.get("/api/v1/tasks", response_model=TaskBoardResponse)
    def list_tasks(current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization))) -> TaskBoardResponse:
        list_rows = state.db.fetchall(
            """
            SELECT *
            FROM task_lists
            WHERE organization_id = ?
            ORDER BY CASE WHEN archived_at IS NULL OR archived_at = '' THEN 0 ELSE 1 END,
                     CASE WHEN is_default = 1 THEN 0 ELSE 1 END,
                     sort_order ASC
            """,
            (current_user.organizationId,),
        )
        task_rows = state.db.fetchall(
            """
            SELECT DISTINCT t.*
            FROM tasks t
            LEFT JOIN task_collaborators tc ON tc.task_id = t.id
            WHERE t.organization_id = ?
              AND (t.creator_id = ? OR tc.user_id = ?)
            ORDER BY t.updated_at DESC
            """,
            (current_user.organizationId, current_user.id, current_user.id),
        )
        all_tags = _visible_task_tags(state, current_user)
        return TaskBoardResponse(
            tasks=[_task_record(state, row, current_user.id) for row in task_rows],
            lists=[_task_list_record(row) for row in list_rows],
            tags=all_tags,
            commonTags=[tag.name for tag in all_tags if tag.scope == "org"],
        )

    @app.post("/api/v1/tasks", response_model=TaskRecord)
    def create_task(payload: TaskCreatePayload, current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization))) -> TaskRecord:
        list_row = state.db.fetchone(
            "SELECT * FROM task_lists WHERE id = ? AND organization_id = ?",
            (payload.listId, current_user.organizationId),
        )
        if not list_row or list_row["archived_at"]:
            raise HTTPException(status_code=400, detail="Invalid task list")
        collaborator_ids = [item for item in payload.collaboratorIds if item]
        if payload.ownerId and payload.ownerId in collaborator_ids:
            collaborator_ids = [payload.ownerId] + [item for item in collaborator_ids if item != payload.ownerId]
        if not collaborator_ids:
            collaborator_ids = [current_user.id]
        owner_id = collaborator_ids[0]
        for user_id in collaborator_ids:
            _get_user_or_404(state, user_id)
        scope_mode = payload.scopeMode or "COLLAB_SHARED"
        requested_client_id = None if scope_mode == "PERSONAL_ONLY" else payload.clientId
        requested_event_line_id = None if scope_mode == "PERSONAL_ONLY" else payload.eventLineId
        requested_project_module_id = None if scope_mode == "PERSONAL_ONLY" else payload.projectModuleId
        requested_project_flow_id = None if scope_mode == "PERSONAL_ONLY" else payload.projectFlowId
        event_line_row = _event_line_row_or_404(state, requested_event_line_id, current_user.organizationId) if requested_event_line_id else None
        event_line_client_id = _event_line_primary_client_id(event_line_row)
        if event_line_client_id:
            requested_client_id = event_line_client_id
        timestamp = now_iso()
        task_id = new_id("task")
        resolved_tags: list[TaskTagRecord] = []
        (
            business_category,
            current_blocker,
            next_action,
            recent_decision,
            evidence_count,
        ) = _resolve_cloud_task_action_os_fields(
            title=payload.title,
            desc=payload.description,
            source_type=payload.sourceType,
            business_category=payload.businessCategory,
            current_blocker=payload.currentBlocker,
            next_action=payload.nextAction,
            recent_decision=payload.recentDecision,
            evidence_count=payload.evidenceCount,
            event_line_row=event_line_row,
        )
        state.db.execute(
            """
            INSERT INTO tasks(
                id, organization_id, title, description, creator_id, owner_id, due_date, duration_minutes, client_id, event_line_id, project_module_id, project_flow_id,
                scope_mode, priority, list_id, progress_status, source_type, source_id, business_category, current_blocker, next_action, recent_decision, evidence_count,
                tags_json, tag_ids_json, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'todo', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                current_user.organizationId,
                payload.title,
                payload.description,
                current_user.id,
                owner_id,
                payload.dueDate,
                payload.durationMinutes,
                requested_client_id,
                requested_event_line_id,
                requested_project_module_id,
                requested_project_flow_id,
                scope_mode,
                payload.priority,
                payload.listId,
                payload.sourceType,
                payload.sourceId,
                business_category,
                current_blocker,
                next_action,
                recent_decision,
                evidence_count,
                to_json([tag.name for tag in resolved_tags]),
                to_json([tag.id for tag in resolved_tags]),
                timestamp,
                timestamp,
            ),
        )
        state.db.executemany(
            """
            INSERT INTO task_collaborators(
                task_id, user_id, order_index, is_owner, inbox_status, return_reason, handled_at, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, NULL, ?, ?, ?)
            """,
            [
                (
                    task_id,
                    user_id,
                    index,
                    1 if index == 0 else 0,
                    "accepted" if user_id == current_user.id else "pending",
                    timestamp if user_id == current_user.id else None,
                    timestamp,
                    timestamp,
                )
                for index, user_id in enumerate(collaborator_ids)
            ],
        )
        _bump_mentions(state, current_user.id, [user_id for user_id in collaborator_ids if user_id != current_user.id])
        _record_activity(
            state,
            task_id,
            current_user.id,
            "created",
            {
                "collaboratorIds": collaborator_ids,
                "tagIds": [tag.id for tag in resolved_tags],
                "dueDate": payload.dueDate or "",
                "eventLineId": requested_event_line_id or "",
                "scopeMode": scope_mode,
            },
        )
        _record_event_line_activity(
            state,
            requested_event_line_id,
            "task_activity",
            task_id,
            current_user.id,
            "新增任务",
            f"创建任务：{payload.title}",
            {"eventType": "created"},
        )
        task_row = _task_row_or_404(state, task_id)
        _sync_task_org_link(state, task_row, collaborator_ids)
        return _task_record(state, task_row, current_user.id)

    @app.patch("/api/v1/tasks/{task_id}", response_model=TaskRecord)
    def update_task(
        task_id: str,
        payload: TaskUpdatePayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> TaskRecord:
        row = _task_row_or_404(state, task_id)
        existing_collaborator_ids = _task_collaborator_ids(state, task_id)
        next_collaborator_ids = [item for item in (payload.collaboratorIds if payload.collaboratorIds is not None else existing_collaborator_ids) if item]
        if payload.ownerId and payload.ownerId in next_collaborator_ids:
            next_collaborator_ids = [payload.ownerId] + [item for item in next_collaborator_ids if item != payload.ownerId]
        elif payload.ownerId:
            next_collaborator_ids = [payload.ownerId, *[item for item in next_collaborator_ids if item != payload.ownerId]]
        if not next_collaborator_ids:
            fallback_owner_id = payload.ownerId or (str(row["owner_id"]) if row["owner_id"] else current_user.id)
            next_collaborator_ids = [fallback_owner_id]
        next_owner_id = payload.ownerId or next_collaborator_ids[0]
        content_changed = any(
            [
                payload.title is not None and payload.title != str(row["title"]),
                payload.description is not None and payload.description != str(row["description"]),
                payload.priority is not None and payload.priority != str(row["priority"]),
                payload.listId is not None and payload.listId != str(row["list_id"]),
                payload.progressStatus is not None and payload.progressStatus != str(row["progress_status"]),
            ]
        )
        due_date_changed = payload.dueDate is not None and payload.dueDate != row["due_date"]
        owner_changed = payload.ownerId is not None and payload.ownerId != (str(row["owner_id"]) if row["owner_id"] else None)
        _assert_task_edit_permission(state, current_user, row, content_changed, due_date_changed, owner_changed)
        if payload.listId:
            list_row = state.db.fetchone(
                "SELECT * FROM task_lists WHERE id = ? AND organization_id = ?",
                (payload.listId, current_user.organizationId),
            )
            if not list_row or list_row["archived_at"]:
                raise HTTPException(status_code=400, detail="Invalid task list")
        next_scope_mode = payload.scopeMode if payload.scopeMode is not None else str(row["scope_mode"] or "COLLAB_SHARED")
        if next_scope_mode == "PERSONAL_ONLY":
            next_client_id = None
            next_event_line_id = None
            next_project_module_id = None
            next_project_flow_id = None
        else:
            next_client_id = payload.clientId if "clientId" in payload.model_fields_set else row["client_id"]
            next_event_line_id = payload.eventLineId if "eventLineId" in payload.model_fields_set else (str(row["event_line_id"]) if row["event_line_id"] else None)
            next_project_module_id = payload.projectModuleId if "projectModuleId" in payload.model_fields_set else row["project_module_id"]
            next_project_flow_id = payload.projectFlowId if "projectFlowId" in payload.model_fields_set else row["project_flow_id"]
        if next_event_line_id:
            event_line_row = _event_line_row_or_404(state, next_event_line_id, current_user.organizationId)
            event_line_client_id = _event_line_primary_client_id(event_line_row)
            if event_line_client_id:
                next_client_id = event_line_client_id
        else:
            event_line_row = None
        resolved_tags: list[TaskTagRecord] = []
        (
            business_category,
            current_blocker,
            next_action,
            recent_decision,
            evidence_count,
        ) = _resolve_cloud_task_action_os_fields(
            title=payload.title or str(row["title"]),
            desc=payload.description if payload.description is not None else str(row["description"]),
            source_type=str(row["source_type"]),
            business_category=payload.businessCategory if "businessCategory" in payload.model_fields_set else (str(row["business_category"]) if row["business_category"] else None),
            current_blocker=payload.currentBlocker if "currentBlocker" in payload.model_fields_set else (str(row["current_blocker"]) if row["current_blocker"] else None),
            next_action=payload.nextAction if "nextAction" in payload.model_fields_set else (str(row["next_action"]) if row["next_action"] else None),
            recent_decision=payload.recentDecision if "recentDecision" in payload.model_fields_set else (str(row["recent_decision"]) if row["recent_decision"] else None),
            evidence_count=payload.evidenceCount if "evidenceCount" in payload.model_fields_set else int(row["evidence_count"] or 0),
            event_line_row=event_line_row,
        )
        merged = {
            "title": payload.title or row["title"],
            "description": payload.description if payload.description is not None else row["description"],
            "priority": payload.priority or row["priority"],
            "list_id": payload.listId or row["list_id"],
            "due_date": payload.dueDate if payload.dueDate is not None else row["due_date"],
            "duration_minutes": payload.durationMinutes if payload.durationMinutes is not None else int(row["duration_minutes"] or 60),
            "scope_mode": next_scope_mode,
            "client_id": next_client_id,
            "event_line_id": next_event_line_id,
            "project_module_id": next_project_module_id,
            "project_flow_id": next_project_flow_id,
            "progress_status": payload.progressStatus or row["progress_status"],
            "owner_id": next_owner_id,
            "business_category": business_category,
            "current_blocker": current_blocker,
            "next_action": next_action,
            "recent_decision": recent_decision,
            "evidence_count": evidence_count,
            "tags_json": to_json([tag.name for tag in resolved_tags]),
            "tag_ids_json": to_json([tag.id for tag in resolved_tags]),
        }
        state.db.execute(
            """
            UPDATE tasks
            SET title = ?, description = ?, priority = ?, list_id = ?, due_date = ?, duration_minutes = ?, scope_mode = ?, client_id = ?, event_line_id = ?, project_module_id = ?, project_flow_id = ?, progress_status = ?, owner_id = ?, business_category = ?, current_blocker = ?, next_action = ?, recent_decision = ?, evidence_count = ?, tags_json = ?, tag_ids_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                merged["title"],
                merged["description"],
                merged["priority"],
                merged["list_id"],
                merged["due_date"],
                merged["duration_minutes"],
                merged["scope_mode"],
                merged["client_id"],
                merged["event_line_id"],
                merged["project_module_id"],
                merged["project_flow_id"],
                merged["progress_status"],
                merged["owner_id"],
                merged["business_category"],
                merged["current_blocker"],
                merged["next_action"],
                merged["recent_decision"],
                merged["evidence_count"],
                merged["tags_json"],
                merged["tag_ids_json"],
                now_iso(),
                task_id,
            ),
        )
        if payload.collaboratorIds is not None or payload.ownerId is not None:
            state.db.execute("UPDATE tasks SET owner_id = ?, updated_at = ? WHERE id = ?", (next_owner_id, now_iso(), task_id))
            existing_rows = state.db.fetchall("SELECT user_id, inbox_status FROM task_collaborators WHERE task_id = ?", (task_id,))
            existing_by_user = {str(item["user_id"]): str(item["inbox_status"]) for item in existing_rows}
            state.db.execute("DELETE FROM task_collaborators WHERE task_id = ?", (task_id,))
            state.db.executemany(
                """
                INSERT INTO task_collaborators(
                    task_id, user_id, order_index, is_owner, inbox_status, return_reason, handled_at, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, NULL, ?, ?, ?)
                """,
                [
                    (
                        task_id,
                        user_id,
                        index,
                        1 if index == 0 else 0,
                        existing_by_user.get(user_id, "accepted" if user_id == current_user.id else "pending"),
                        now_iso() if existing_by_user.get(user_id) == "accepted" else None,
                        now_iso(),
                        now_iso(),
                    )
                    for index, user_id in enumerate(next_collaborator_ids)
                ],
            )
            _bump_mentions(state, current_user.id, [user_id for user_id in next_collaborator_ids if user_id != current_user.id])
        _record_activity(state, task_id, current_user.id, "updated", payload.model_dump(exclude_none=True))
        if merged["event_line_id"]:
            previous_event_line_id = str(row["event_line_id"]) if row["event_line_id"] else None
            _record_event_line_activity(
                state,
                merged["event_line_id"],
                "task_activity",
                task_id,
                current_user.id,
                "加入事件线" if merged["event_line_id"] != previous_event_line_id else "任务更新",
                f"更新任务：{merged['title']}",
                {"eventType": "updated", "previousEventLineId": previous_event_line_id},
            )
        updated_row = _task_row_or_404(state, task_id)
        _sync_task_org_link(state, updated_row, next_collaborator_ids)
        return _task_record(state, updated_row, current_user.id)

    @app.delete("/api/v1/tasks/{task_id}")
    def delete_task(
        task_id: str,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> dict[str, bool]:
        row = _task_row_or_404(state, task_id)
        content_changed = True
        due_date_changed = False
        owner_changed = False
        _assert_task_edit_permission(state, current_user, row, content_changed, due_date_changed, owner_changed)
        state.db.execute("DELETE FROM event_line_activities WHERE source_type = 'task_activity' AND source_id = ?", (task_id,))
        state.db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return {"deleted": True}

    @app.post("/api/v1/tasks/{task_id}/attachments", response_model=TaskRecord)
    async def upload_task_attachment(
        task_id: str,
        file: UploadFile = File(...),
        clientId: str | None = Form(default=None),
        eventLineId: str | None = Form(default=None),
        title: str | None = Form(default=None),
        taskTitle: str | None = Form(default=None),
        durationSeconds: int | None = Form(default=None),
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> TaskRecord:
        task_row = _task_row_or_404(state, task_id)
        _assert_task_edit_permission(state, current_user, task_row, True, False, False)

        resolved_client_id = str(task_row["client_id"]) if task_row["client_id"] else clientId
        resolved_event_line_id = str(task_row["event_line_id"]) if task_row["event_line_id"] else eventLineId
        if resolved_event_line_id:
            _event_line_row_or_404(state, resolved_event_line_id, current_user.organizationId)

        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="上传失败：录音内容为空。")

        base_title = _first_nonempty_text(title, taskTitle, file.filename, str(task_row["title"]), "任务附件") or "任务附件"
        mime_type = str(file.content_type or "application/octet-stream")
        fallback_ext = Path(file.filename or "").suffix or (".m4a" if mime_type.startswith("audio/") else "")
        upload_name = safe_filename(file.filename or f"{base_title}{fallback_ext}")
        if "." not in upload_name and fallback_ext:
            upload_name = safe_filename(f"{upload_name}{fallback_ext}")

        task_dir = state.data_dir / "task-attachments" / current_user.organizationId / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        stored_name = safe_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{upload_name}")
        attachment_path = task_dir / stored_name
        attachment_path.write_bytes(content)

        timestamp = now_iso()
        attachment_id = new_id("tatt")
        kind = "audio" if mime_type.startswith("audio/") else (Path(stored_name).suffix.lower().lstrip(".") or "file")
        source = "mobile_recording" if mime_type.startswith("audio/") else "task_attachment"
        summary = "任务补充录音已归档" if mime_type.startswith("audio/") else "任务附件已归档"
        resolved_title = base_title.strip() or upload_name
        relative_path = str(attachment_path.relative_to(state.data_dir))

        state.db.execute(
            """
            INSERT INTO task_attachments(
                id, organization_id, task_id, client_id, event_line_id, title, summary, path, kind, source,
                mime_type, size_bytes, duration_seconds, created_by_user_id, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attachment_id,
                current_user.organizationId,
                task_id,
                resolved_client_id,
                resolved_event_line_id,
                resolved_title,
                summary,
                relative_path,
                kind,
                source,
                mime_type,
                len(content),
                max(durationSeconds or 0, 0),
                current_user.id,
                timestamp,
            ),
        )

        attachment_count = int(
            state.db.scalar("SELECT COUNT(1) AS count FROM task_attachments WHERE task_id = ?", (task_id,)) or 0
        )
        state.db.execute(
            "UPDATE tasks SET evidence_count = ?, updated_at = ? WHERE id = ?",
            (max(int(task_row["evidence_count"] or 0), attachment_count), timestamp, task_id),
        )

        activity_payload = {
            "attachmentId": attachment_id,
            "title": resolved_title,
            "kind": kind,
            "source": source,
            "clientId": resolved_client_id or "",
            "eventLineId": resolved_event_line_id or "",
            "mimeType": mime_type,
            "sizeBytes": len(content),
            "durationSeconds": max(durationSeconds or 0, 0),
            "path": relative_path,
        }
        _record_activity(state, task_id, current_user.id, "attachment_added", activity_payload)
        _record_event_line_activity(
            state,
            resolved_event_line_id,
            "attachment",
            attachment_id,
            current_user.id,
            "上传录音" if mime_type.startswith("audio/") else "上传附件",
            f"{resolved_title} 已归档到任务附件",
            activity_payload,
        )
        return _task_record(state, _task_row_or_404(state, task_id), current_user.id)

    @app.post("/api/v1/tasks/{task_id}/attachments/{attachment_id}/transcribe-to-document", response_model=TaskAttachmentTranscriptionResponse)
    def transcribe_task_attachment_to_document(
        task_id: str,
        attachment_id: str,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> TaskAttachmentTranscriptionResponse:
        task_row = _task_row_or_404(state, task_id)
        _assert_task_edit_permission(state, current_user, task_row, True, False, False)
        attachment_row = _task_attachment_row_or_404(state, attachment_id, task_id, current_user.organizationId)
        mime_type = str(attachment_row["mime_type"] or "")
        if not mime_type.startswith("audio/"):
            raise HTTPException(status_code=400, detail="当前附件不是录音文件，无法转写。")

        attachment_path = state.data_dir / str(attachment_row["path"])
        if not attachment_path.exists() or not attachment_path.is_file():
            raise HTTPException(status_code=404, detail="录音文件不存在，无法转写。")

        public_base_url = os.getenv("YIYU_CLOUD_PUBLIC_BASE_URL", "").strip()
        public_url = None
        if public_base_url:
            public_url = f"{public_base_url.rstrip('/')}/api/public/task-attachments/{attachment_id}"

        try:
            transcript = transcribe_audio_with_doubao(
                attachment_path.read_bytes(),
                file_name=attachment_path.name,
                mime_type=mime_type,
                public_url=public_url,
            ).strip()
        except RuntimeError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=502, detail=f"录音转写失败：{error}") from error

        if not transcript:
            raise HTTPException(status_code=400, detail="录音已上传，但未识别出有效文本。")

        event_line_id = str(attachment_row["event_line_id"]) if attachment_row["event_line_id"] else (str(task_row["event_line_id"]) if task_row["event_line_id"] else None)
        client_id = str(attachment_row["client_id"]) if attachment_row["client_id"] else (str(task_row["client_id"]) if task_row["client_id"] else None)
        client_name = str(task_row["client_name"]) if task_row["client_name"] else None
        document_request = _create_consultation_knowledge_request_internal(
            state,
            current_user=current_user,
            target="document_archive",
            question=f"录音转写：{str(attachment_row['title'])}",
            answer=transcript,
            client_id=client_id,
            client_name=client_name,
            task_id=task_id,
            event_line_id=event_line_id,
            source="mobile_recording_transcript",
        )
        # AI-generated summary via Volcengine Ark (Doubao)
        # Resolve event line name for AI summary context
        _el_name_for_summary = ""
        if event_line_id:
            try:
                _el_row = state.db.fetchone("SELECT name FROM event_lines WHERE id = ?", (event_line_id,))
                if _el_row:
                    _el_name_for_summary = str(_el_row["name"] or "")
            except Exception:
                pass
        summary = _generate_recording_summary(
            transcript=transcript,
            task_title=str(task_row["title"]),
            client_name=client_name,
            event_line_name=_el_name_for_summary,
        )
        timestamp = now_iso()
        state.db.execute(
            "UPDATE task_attachments SET summary = ? WHERE id = ?",
            (summary, attachment_id),
        )
        _record_activity(
            state,
            task_id,
            current_user.id,
            "attachment_transcribed",
            {
                "attachmentId": attachment_id,
                "knowledgeRequestId": document_request.id,
                "target": document_request.target,
                "transcript": transcript,
                "attachmentTitle": str(attachment_row["title"]) if attachment_row["title"] else None,
            },
        )
        _record_event_line_activity(
            state,
            event_line_id,
            "attachment",
            attachment_id,
            current_user.id,
            "录音已转写",
            f"{str(attachment_row['title'])} 已生成文档沉淀请求",
            {
                "attachmentId": attachment_id,
                "knowledgeRequestId": document_request.id,
                "target": document_request.target,
                "updatedAt": timestamp,
            },
        )
        return TaskAttachmentTranscriptionResponse(
            attachmentId=attachment_id,
            transcript=transcript,
            documentRequest=document_request,
        )

    @app.post("/api/v1/tasks/{task_id}/collaborators/{user_id}/accept", response_model=TaskRecord)
    def accept_task(task_id: str, user_id: str, current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization))) -> TaskRecord:
        if user_id != current_user.id:
            raise HTTPException(status_code=403, detail="只能处理自己的协作收件箱")
        row = state.db.fetchone("SELECT * FROM task_collaborators WHERE task_id = ? AND user_id = ?", (task_id, user_id))
        if not row:
            raise HTTPException(status_code=404, detail="Collaboration item not found")
        timestamp = now_iso()
        state.db.execute(
            "UPDATE task_collaborators SET inbox_status = 'accepted', return_reason = NULL, handled_at = ?, updated_at = ? WHERE task_id = ? AND user_id = ?",
            (timestamp, timestamp, task_id, user_id),
        )
        # Notification tasks go straight to done after acknowledgement (don't enter calendar/task list)
        task_row = _task_row_or_404(state, task_id)
        if str(task_row["source_type"]) == "event_line_notification":
            all_accepted = not state.db.fetchone(
                "SELECT 1 FROM task_collaborators WHERE task_id = ? AND inbox_status = 'pending'", (task_id,),
            )
            if all_accepted:
                state.db.execute(
                    "UPDATE tasks SET progress_status = 'done', updated_at = ? WHERE id = ?", (timestamp, task_id),
                )
        _record_activity(state, task_id, current_user.id, "accepted", {"userId": user_id})
        return _task_record(state, _task_row_or_404(state, task_id), current_user.id)

    @app.post("/api/v1/tasks/{task_id}/collaborators/{user_id}/return", response_model=TaskRecord)
    def return_task(
        task_id: str,
        user_id: str,
        payload: TaskReturnPayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> TaskRecord:
        if user_id != current_user.id:
            raise HTTPException(status_code=403, detail="只能处理自己的协作收件箱")
        row = state.db.fetchone("SELECT * FROM task_collaborators WHERE task_id = ? AND user_id = ?", (task_id, user_id))
        if not row:
            raise HTTPException(status_code=404, detail="Collaboration item not found")
        timestamp = now_iso()
        state.db.execute(
            "UPDATE task_collaborators SET inbox_status = 'returned', return_reason = ?, handled_at = ?, updated_at = ? WHERE task_id = ? AND user_id = ?",
            (payload.reason.strip(), timestamp, timestamp, task_id, user_id),
        )
        _record_activity(state, task_id, current_user.id, "returned", {"userId": user_id, "reason": payload.reason.strip()})
        return _task_record(state, _task_row_or_404(state, task_id), current_user.id)

    @app.post("/api/v1/tasks/{task_id}/complete-with-review", response_model=TaskRecord)
    def complete_task_with_review(
        task_id: str,
        payload: TaskCompletionReviewPayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> TaskRecord:
        task_row = _task_row_or_404(state, task_id)
        _assert_task_edit_permission(state, current_user, task_row, True, False, False)
        review_note = payload.reviewNote.strip()
        timestamp = now_iso()
        previous_status = str(task_row["progress_status"])
        state.db.execute(
            """
            UPDATE tasks
               SET progress_status = 'done',
                   completion_note = ?,
                   updated_at = ?
             WHERE id = ?
            """,
            (review_note, timestamp, task_id),
        )
        activity_payload = {
            "reviewNote": review_note,
            "previousStatus": previous_status,
            "nextStatus": "done",
        }
        _record_activity(state, task_id, current_user.id, "completed_with_review", activity_payload)
        _record_event_line_activity(
            state,
            str(task_row["event_line_id"]) if task_row["event_line_id"] else None,
            "review",
            new_id("trev"),
            current_user.id,
            "任务完成复盘",
            review_note[:120],
            activity_payload,
        )
        return _task_record(state, _task_row_or_404(state, task_id), current_user.id)

    @app.post("/api/v1/tasks/{task_id}/review/approve", response_model=TaskRecord)
    def approve_task_review(
        task_id: str,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> TaskRecord:
        task_row = _task_row_or_404(state, task_id)
        task_link_row = _task_org_link_row(state, task_id)
        if not task_link_row or not bool(int(task_link_row["needs_review"] or 0)):
            raise HTTPException(status_code=400, detail="该任务当前无需复核")
        if not _can_review_task(state, current_user, task_row, task_link_row):
            raise HTTPException(status_code=403, detail="你当前没有执行复核的权限")
        timestamp = now_iso()
        state.db.execute(
            """
            UPDATE task_org_links
               SET approval_state = 'approved',
                   blocked_at_step = NULL,
                   needs_review = 0,
                   updated_at = ?
             WHERE task_id = ?
            """,
            (timestamp, task_id),
        )
        _record_activity(state, task_id, current_user.id, "review_approved", {})
        return _task_record(state, _task_row_or_404(state, task_id), current_user.id)

    @app.post("/api/v1/tasks/{task_id}/review/return", response_model=TaskRecord)
    def return_task_review(
        task_id: str,
        payload: TaskReturnPayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> TaskRecord:
        task_row = _task_row_or_404(state, task_id)
        task_link_row = _task_org_link_row(state, task_id)
        if not task_link_row or not bool(int(task_link_row["needs_review"] or 0)):
            raise HTTPException(status_code=400, detail="该任务当前无需复核")
        if not _can_review_task(state, current_user, task_row, task_link_row):
            raise HTTPException(status_code=403, detail="你当前没有执行复核的权限")
        timestamp = now_iso()
        state.db.execute(
            """
            UPDATE task_org_links
               SET approval_state = 'rejected',
                   blocked_at_step = ?,
                   needs_review = 1,
                   updated_at = ?
             WHERE task_id = ?
            """,
            (payload.reason.strip() or "需要补充说明后再复核", timestamp, task_id),
        )
        _record_activity(state, task_id, current_user.id, "review_returned", {"reason": payload.reason.strip()})
        return _task_record(state, _task_row_or_404(state, task_id), current_user.id)

    @app.post("/api/v1/tasks/{task_id}/note", response_model=TaskRecord)
    def save_task_note(
        task_id: str,
        payload: TaskNotePayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> TaskRecord:
        task_row = _task_row_or_404(state, task_id)
        timestamp = now_iso()
        existing = state.db.fetchone("SELECT id FROM task_notes WHERE task_id = ?", (task_id,))
        if existing:
            state.db.execute(
                "UPDATE task_notes SET note = ?, user_id = ?, updated_at = ? WHERE task_id = ?",
                (payload.note, current_user.id, timestamp, task_id),
            )
        else:
            state.db.execute(
                "INSERT INTO task_notes(id, organization_id, task_id, user_id, note, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
                (str(uuid4()), current_user.organizationId, task_id, current_user.id, payload.note, timestamp, timestamp),
            )
        _record_activity(state, task_id, current_user.id, "note_updated", {"noteLength": len(payload.note)})
        return _task_record(state, task_row, current_user.id)

    @app.get("/api/v1/tasks/{task_id}/activity", response_model=list[TaskActivityRecord])
    def task_activity(task_id: str, current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization))) -> list[TaskActivityRecord]:
        _task_row_or_404(state, task_id)
        rows = state.db.fetchall(
            """
            SELECT e.*, u.full_name
            FROM task_activity_events e
            JOIN employee_accounts u ON u.id = e.actor_id
            WHERE e.task_id = ?
            ORDER BY e.created_at DESC
            """,
            (task_id,),
        )
        return [
            TaskActivityRecord(
                id=str(row["id"]),
                taskId=str(row["task_id"]),
                actorId=str(row["actor_id"]),
                actorName=str(row["full_name"]),
                eventType=str(row["event_type"]),
                payload=from_json(row["payload_json"], {}) if isinstance(from_json(row["payload_json"], {}), dict) else {},
                createdAt=str(row["created_at"]),
            )
            for row in rows
        ]

    @app.get("/api/v1/reviews/dashboard", response_model=ReviewDashboardResponse)
    def review_dashboard(
        weekLabel: str | None = Query(default=None),
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> ReviewDashboardResponse:
        return _dashboard_for_user(state, current_user, weekLabel)

    @app.get("/api/v1/reviews/history", response_model=ReviewHistoryResponse)
    def review_history(current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization))) -> ReviewHistoryResponse:
        return _review_history_for_user(state, current_user.id)

    @app.post("/api/v1/reviews/weekly", response_model=ReviewDashboardResponse)
    def submit_weekly_review(
        payload: WeeklyReviewCreatePayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> ReviewDashboardResponse:
        timestamp = now_iso()
        legacy_work_segments = [
            payload.workProgress.strip(),
            payload.workBlocker.strip(),
            payload.workDirection.strip(),
            payload.nextWeekFocus.strip(),
            payload.supportNeeded.strip(),
            payload.workFreeNote.strip(),
        ]
        legacy_work_text = "\n".join(segment for segment in legacy_work_segments if segment)
        legacy_personal_text = payload.personalGrowthNote.strip()
        legacy_private_text = payload.personalPrivateNote.strip()
        existing = state.db.fetchone(
            "SELECT id FROM weekly_review_entries WHERE user_id = ? AND week_label = ?",
            (current_user.id, payload.weekLabel),
        )
        if existing:
            review_id = str(existing["id"])
        else:
            review_id = new_id("review")
        normalized_entries: list[tuple[TaskRecord, str, str, str]] = []
        for entry in payload.taskEntries:
            task_id = str(entry.get("taskId", "")).strip()
            if not task_id:
                continue
            task_row = _task_record(state, _task_row_or_404(state, task_id), current_user.id)
            structured_note = _coerce_review_structured_note_payload(entry.get("structuredNote"))
            note = _compose_review_note(structured_note, str(entry.get("note", "")).strip())
            domain = str(entry.get("contentDomain") or ("personal" if _is_private_task(task_row) else "work"))
            normalized_entries.append((task_row, note, domain, to_json(structured_note.model_dump())))
        work_text = "\n".join(f"{task.title}：{note}" for task, note, domain, _ in normalized_entries if domain == "work" and note) or legacy_work_text
        personal_text = "\n".join(f"{task.title}：{note}" for task, note, domain, _ in normalized_entries if domain == "personal" and note) or legacy_personal_text
        if existing:
            state.db.execute(
                """
                UPDATE weekly_review_entries
                SET work_progress = '', work_blocker = '', blocker_type = '', work_direction = '', next_week_focus = '',
                    support_needed = '', related_plan_ids_json = '[]', work_free_note = ?, personal_growth_note = ?,
                    personal_private_note = '', personal_visibility = 'self', submitted_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (work_text, personal_text, timestamp, timestamp, review_id),
            )
            state.db.execute(
                "UPDATE weekly_review_entries SET personal_private_note = ? WHERE id = ?",
                (legacy_private_text, review_id),
            )
        else:
            state.db.execute(
                """
                INSERT INTO weekly_review_entries(
                    id, organization_id, user_id, week_label, work_progress, work_blocker, blocker_type, work_direction,
                    next_week_focus, support_needed, related_plan_ids_json, work_free_note, personal_growth_note,
                    personal_private_note, personal_visibility, submitted_at, created_at, updated_at
                ) VALUES(?, ?, ?, ?, '', '', '', '', '', '', '[]', ?, ?, '', 'self', ?, ?, ?)
                """,
                (review_id, current_user.organizationId, current_user.id, payload.weekLabel, work_text, personal_text, timestamp, timestamp, timestamp),
            )
            state.db.execute(
                "UPDATE weekly_review_entries SET personal_private_note = ? WHERE id = ?",
                (legacy_private_text, review_id),
            )
        for task_row, note, domain, structured_note_json in normalized_entries:
            existing_entry = state.db.fetchone(
                "SELECT id FROM weekly_review_task_entries WHERE review_id = ? AND task_id = ?",
                (review_id, task_row.id),
            )
            if not note:
                if existing_entry:
                    state.db.execute("DELETE FROM weekly_review_task_entries WHERE id = ?", (str(existing_entry["id"]),))
                continue
            snapshot = _task_snapshot_from_record(state, task_row).model_dump()
            if existing_entry:
                state.db.execute(
                    """
                    UPDATE weekly_review_task_entries
                    SET content_domain = ?, note = ?, structured_note_json = ?, reviewed_at = ?, task_snapshot_json = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (domain, note, structured_note_json, timestamp, to_json(snapshot), timestamp, str(existing_entry["id"])),
                )
            else:
                state.db.execute(
                    """
                    INSERT INTO weekly_review_task_entries(
                        id, organization_id, review_id, user_id, task_id, week_label, content_domain, note, structured_note_json, reviewed_at, task_snapshot_json, created_at, updated_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (new_id("review_item"), current_user.organizationId, review_id, current_user.id, task_row.id, payload.weekLabel, domain, note, structured_note_json, timestamp, to_json(snapshot), timestamp, timestamp),
                )
        review_row = state.db.fetchone("SELECT * FROM weekly_review_entries WHERE id = ?", (review_id,))
        assert review_row is not None
        work_items, personal_items = _dashboard_review_items(state, current_user, payload.weekLabel, review_row)
        _upsert_weekly_review_sections(state, review_id, work_items, personal_items)
        _upsert_signal_card(state, current_user, review_row, work_items)
        _upsert_personal_growth_card(state, current_user, review_row, personal_items)
        _log_audit(
            state,
            "weekly_review.submit",
            actor_user_id=current_user.id,
            target_user_id=current_user.id,
            detail={"weekLabel": payload.weekLabel, "contentDomains": ["work", "personal"], "personalExcludedFromAggregation": True},
        )
        return _dashboard_for_user(state, current_user, payload.weekLabel)

    return app


app = create_app()
