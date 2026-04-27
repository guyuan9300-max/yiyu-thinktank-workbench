# 益语软件平台源码导出（第006卷）

- 导出时间: 2026-04-20 18:08:04
- 内容范围: 主仓库源码 + mobile 子仓库源码
- 说明: 每个条目为完整源码文件。

## `cloud_backend/app/db.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import json
import shutil
import sqlite3
import threading
from pathlib import Path


class Database:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self.conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS organizations (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    slug TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS employee_accounts (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    full_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    primary_role TEXT NOT NULL,
                    account_status TEXT NOT NULL,
                    approved_at TEXT,
                    approved_by TEXT,
                    rejected_reason TEXT,
                    disabled_at TEXT,
                    recent_mentions_json TEXT NOT NULL DEFAULT '[]',
                    last_login_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(approved_by) REFERENCES employee_accounts(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS employee_role_bindings (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(user_id, role),
                    FOREIGN KEY(user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS auth_refresh_sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    refresh_token TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT,
                    FOREIGN KEY(user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS auth_audit_logs (
                    id TEXT PRIMARY KEY,
                    actor_user_id TEXT,
                    target_user_id TEXT,
                    action TEXT NOT NULL,
                    detail_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(actor_user_id) REFERENCES employee_accounts(id) ON DELETE SET NULL,
                    FOREIGN KEY(target_user_id) REFERENCES employee_accounts(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS feishu_binding_relay_sessions (
                    state_token TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    code TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    authorized_at TEXT,
                    cleared_at TEXT,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS task_lists (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    color TEXT NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_default INTEGER NOT NULL DEFAULT 0,
                    scope TEXT NOT NULL DEFAULT 'org',
                    archived_at TEXT,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS task_tag_library (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    scope TEXT NOT NULL DEFAULT 'org',
                    color TEXT NOT NULL DEFAULT '#5B7BFE',
                    owner_user_id TEXT NOT NULL DEFAULT '',
                    created_by TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT '',
                    archived_at TEXT,
                    UNIQUE(organization_id, scope, owner_user_id, name),
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS task_settings (
                    user_id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    default_list_id TEXT,
                    default_priority TEXT NOT NULL DEFAULT 'normal',
                    default_due_date_preset TEXT NOT NULL DEFAULT 'today',
                    default_view_mode TEXT NOT NULL DEFAULT 'list',
                    list_sort_mode TEXT NOT NULL DEFAULT 'manual',
                    show_completed_tasks INTEGER NOT NULL DEFAULT 0,
                    default_review_scope TEXT NOT NULL DEFAULT 'work',
                    auto_assign_self INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(default_list_id) REFERENCES task_lists(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS task_views (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL DEFAULT 'custom',
                    description TEXT NOT NULL DEFAULT '',
                    calendar_scope TEXT NOT NULL DEFAULT 'all',
                    shareability TEXT NOT NULL DEFAULT 'private',
                    sort_by TEXT NOT NULL DEFAULT 'updatedAt',
                    sort_direction TEXT NOT NULL DEFAULT 'desc',
                    visible_fields_json TEXT NOT NULL DEFAULT '[]',
                    filter_set_json TEXT NOT NULL DEFAULT '{}',
                    built_in INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_task_views_org_kind
                    ON task_views(organization_id, kind, built_in, updated_at DESC);

                CREATE TABLE IF NOT EXISTS clients (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    alias TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_clients_org_updated
                    ON clients(organization_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    creator_id TEXT NOT NULL,
                    owner_id TEXT,
                    due_date TEXT,
                    duration_minutes INTEGER NOT NULL DEFAULT 60,
                    scope_mode TEXT NOT NULL DEFAULT 'COLLAB_SHARED',
                    business_category TEXT,
                    current_blocker TEXT,
                    next_action TEXT,
                    recent_decision TEXT,
                    completion_note TEXT,
                    evidence_count INTEGER NOT NULL DEFAULT 0,
                    priority TEXT NOT NULL,
                    list_id TEXT NOT NULL,
                    progress_status TEXT NOT NULL DEFAULT 'todo',
                    source_type TEXT NOT NULL,
                    source_id TEXT,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    tag_ids_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(creator_id) REFERENCES employee_accounts(id) ON DELETE CASCADE,
                    FOREIGN KEY(owner_id) REFERENCES employee_accounts(id) ON DELETE SET NULL,
                    FOREIGN KEY(list_id) REFERENCES task_lists(id) ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS task_collaborators (
                    task_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    order_index INTEGER NOT NULL,
                    is_owner INTEGER NOT NULL DEFAULT 0,
                    inbox_status TEXT NOT NULL,
                    return_reason TEXT,
                    handled_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (task_id, user_id),
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS mention_history (
                    actor_id TEXT NOT NULL,
                    mentioned_user_id TEXT NOT NULL,
                    use_count INTEGER NOT NULL DEFAULT 1,
                    last_mentioned_at TEXT NOT NULL,
                    PRIMARY KEY (actor_id, mentioned_user_id),
                    FOREIGN KEY(actor_id) REFERENCES employee_accounts(id) ON DELETE CASCADE,
                    FOREIGN KEY(mentioned_user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS task_activity_events (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                    FOREIGN KEY(actor_id) REFERENCES employee_accounts(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS event_lines (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL DEFAULT 'custom',
                    status TEXT NOT NULL DEFAULT 'active',
                    business_category TEXT,
                    stage TEXT,
                    summary TEXT,
                    intent TEXT,
                    current_blocker TEXT,
                    recent_decision TEXT,
                    next_step TEXT,
                    evidence_count INTEGER NOT NULL DEFAULT 0,
                    owner_id TEXT,
                    primary_client_id TEXT,
                    primary_client_name TEXT,
                    primary_department_id TEXT,
                    participant_ids_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(owner_id) REFERENCES employee_accounts(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS event_line_activities (
                    id TEXT PRIMARY KEY,
                    event_line_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    happened_at TEXT NOT NULL,
                    actor_id TEXT,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(event_line_id) REFERENCES event_lines(id) ON DELETE CASCADE,
                    FOREIGN KEY(actor_id) REFERENCES employee_accounts(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS org_units (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    parent_id TEXT,
                    name TEXT NOT NULL,
                    unit_type TEXT NOT NULL,
                    leader_user_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(parent_id) REFERENCES org_units(id) ON DELETE SET NULL,
                    FOREIGN KEY(leader_user_id) REFERENCES employee_accounts(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS reporting_lines (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    manager_user_id TEXT NOT NULL,
                    report_user_id TEXT NOT NULL,
                    relationship_type TEXT NOT NULL,
                    effective_from TEXT NOT NULL,
                    effective_to TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(manager_user_id, report_user_id, relationship_type),
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(manager_user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE,
                    FOREIGN KEY(report_user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS plan_nodes (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    owner_user_id TEXT,
                    owner_unit_id TEXT,
                    level TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    status TEXT NOT NULL,
                    starts_at TEXT,
                    ends_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(owner_user_id) REFERENCES employee_accounts(id) ON DELETE SET NULL,
                    FOREIGN KEY(owner_unit_id) REFERENCES org_units(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS org_profiles (
                    organization_id TEXT PRIMARY KEY,
                    annual_goal TEXT NOT NULL DEFAULT '',
                    annual_strategy_year TEXT NOT NULL DEFAULT '',
                    annual_strategy_text TEXT NOT NULL DEFAULT '',
                    quarter_plans_json TEXT NOT NULL DEFAULT '[]',
                    quarterly_focus_json TEXT NOT NULL DEFAULT '[]',
                    leader_user_id TEXT,
                    management_user_ids_json TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(leader_user_id) REFERENCES employee_accounts(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS org_departments (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    color TEXT NOT NULL DEFAULT '#5B7BFE',
                    leader_user_id TEXT,
                    parent_department_id TEXT,
                    mission TEXT NOT NULL DEFAULT '',
                    business_context TEXT NOT NULL DEFAULT '',
                    team_context TEXT NOT NULL DEFAULT '',
                    quarter_plan_json TEXT NOT NULL DEFAULT '{}',
                    quarterly_focus_json TEXT NOT NULL DEFAULT '[]',
                    collaboration_department_ids_json TEXT NOT NULL DEFAULT '[]',
                    active INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(leader_user_id) REFERENCES employee_accounts(id) ON DELETE SET NULL,
                    FOREIGN KEY(parent_department_id) REFERENCES org_departments(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS org_role_templates (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    department_id TEXT,
                    name TEXT NOT NULL,
                    level TEXT NOT NULL,
                    manager_role_id TEXT,
                    is_manager INTEGER NOT NULL DEFAULT 0,
                    goal TEXT NOT NULL DEFAULT '',
                    responsibilities_json TEXT NOT NULL DEFAULT '[]',
                    should_avoid_json TEXT NOT NULL DEFAULT '[]',
                    collaboration_role_ids_json TEXT NOT NULL DEFAULT '[]',
                    task_edit_scope TEXT NOT NULL DEFAULT 'self',
                    can_approve_tasks INTEGER NOT NULL DEFAULT 0,
                    can_reassign_tasks INTEGER NOT NULL DEFAULT 0,
                    can_change_deadline INTEGER NOT NULL DEFAULT 0,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(department_id) REFERENCES org_departments(id) ON DELETE SET NULL,
                    FOREIGN KEY(manager_role_id) REFERENCES org_role_templates(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS org_employee_role_bindings (
                    user_id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    department_id TEXT,
                    primary_role_id TEXT,
                    manager_user_id TEXT,
                    is_manager INTEGER NOT NULL DEFAULT 0,
                    project_role_labels_json TEXT NOT NULL DEFAULT '[]',
                    current_focus TEXT NOT NULL DEFAULT '',
                    task_edit_scope TEXT NOT NULL DEFAULT 'self',
                    can_approve_tasks INTEGER NOT NULL DEFAULT 0,
                    can_reassign_tasks INTEGER NOT NULL DEFAULT 0,
                    can_change_deadline INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(department_id) REFERENCES org_departments(id) ON DELETE SET NULL,
                    FOREIGN KEY(primary_role_id) REFERENCES org_role_templates(id) ON DELETE SET NULL,
                    FOREIGN KEY(manager_user_id) REFERENCES employee_accounts(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS org_reporting_lines (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    manager_user_id TEXT NOT NULL,
                    report_user_id TEXT NOT NULL,
                    line_type TEXT NOT NULL DEFAULT 'business',
                    approves_tasks INTEGER NOT NULL DEFAULT 0,
                    can_adjust_tasks INTEGER NOT NULL DEFAULT 0,
                    can_change_deadline INTEGER NOT NULL DEFAULT 0,
                    can_reassign_tasks INTEGER NOT NULL DEFAULT 0,
                    is_cross_department_approver INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL,
                    UNIQUE(organization_id, manager_user_id, report_user_id, line_type),
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(manager_user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE,
                    FOREIGN KEY(report_user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS org_task_control_rules (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    control_level TEXT NOT NULL DEFAULT 'normal',
                    department_id TEXT,
                    role_template_id TEXT,
                    content_editable_by TEXT NOT NULL DEFAULT 'assignee',
                    deadline_editable_by TEXT NOT NULL DEFAULT 'manager',
                    owner_editable_by TEXT NOT NULL DEFAULT 'manager',
                    cancellable_by TEXT NOT NULL DEFAULT 'manager',
                    require_collab_confirmation INTEGER NOT NULL DEFAULT 0,
                    default_approver_user_id TEXT,
                    active INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(department_id) REFERENCES org_departments(id) ON DELETE SET NULL,
                    FOREIGN KEY(role_template_id) REFERENCES org_role_templates(id) ON DELETE SET NULL,
                    FOREIGN KEY(default_approver_user_id) REFERENCES employee_accounts(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS org_role_process_templates (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    role_template_id TEXT,
                    name TEXT NOT NULL,
                    trigger_type TEXT NOT NULL DEFAULT 'manual',
                    trigger_condition TEXT NOT NULL DEFAULT '',
                    key_steps_json TEXT NOT NULL DEFAULT '[]',
                    collaboration_step TEXT NOT NULL DEFAULT '',
                    approval_step TEXT NOT NULL DEFAULT '',
                    output_artifact TEXT NOT NULL DEFAULT '',
                    common_blockers_json TEXT NOT NULL DEFAULT '[]',
                    active INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(role_template_id) REFERENCES org_role_templates(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS org_focus_items (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    period_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    statement TEXT NOT NULL DEFAULT '',
                    owner_user_id TEXT,
                    priority TEXT NOT NULL DEFAULT 'medium',
                    status TEXT NOT NULL DEFAULT 'active',
                    evidence_keywords_json TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(owner_user_id) REFERENCES employee_accounts(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS org_department_plans (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    department_id TEXT,
                    week_label TEXT NOT NULL,
                    owner_user_id TEXT,
                    summary TEXT NOT NULL DEFAULT '',
                    major_risks_json TEXT NOT NULL DEFAULT '[]',
                    dependencies_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'draft',
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(department_id) REFERENCES org_departments(id) ON DELETE SET NULL,
                    FOREIGN KEY(owner_user_id) REFERENCES employee_accounts(id) ON DELETE SET NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_org_department_plans_department_week
                    ON org_department_plans(organization_id, department_id, week_label);

                CREATE TABLE IF NOT EXISTS org_department_plan_items (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    focus_item_id TEXT,
                    title TEXT NOT NULL,
                    statement TEXT NOT NULL DEFAULT '',
                    owner_user_id TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    expected_output TEXT NOT NULL DEFAULT '',
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(plan_id) REFERENCES org_department_plans(id) ON DELETE CASCADE,
                    FOREIGN KEY(focus_item_id) REFERENCES org_focus_items(id) ON DELETE SET NULL,
                    FOREIGN KEY(owner_user_id) REFERENCES employee_accounts(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS task_plan_links (
                    task_id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    department_plan_item_id TEXT,
                    focus_item_id TEXT,
                    linked_by TEXT NOT NULL DEFAULT 'ai',
                    confidence REAL NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(department_plan_item_id) REFERENCES org_department_plan_items(id) ON DELETE SET NULL,
                    FOREIGN KEY(focus_item_id) REFERENCES org_focus_items(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS support_requests (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    task_id TEXT,
                    requester_user_id TEXT NOT NULL,
                    target_scope TEXT NOT NULL,
                    target_ref_id TEXT,
                    request_type TEXT NOT NULL,
                    urgency TEXT NOT NULL DEFAULT 'medium',
                    summary TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    resolution_note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE SET NULL,
                    FOREIGN KEY(requester_user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS task_org_links (
                    task_id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    department_id TEXT,
                    role_template_id TEXT,
                    organization_focus_key TEXT,
                    department_focus_key TEXT,
                    is_cross_department INTEGER NOT NULL DEFAULT 0,
                    approval_state TEXT NOT NULL DEFAULT 'none',
                    blocked_at_step TEXT,
                    control_rule_id TEXT,
                    needs_review INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(department_id) REFERENCES org_departments(id) ON DELETE SET NULL,
                    FOREIGN KEY(role_template_id) REFERENCES org_role_templates(id) ON DELETE SET NULL,
                    FOREIGN KEY(control_rule_id) REFERENCES org_task_control_rules(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS weekly_review_entries (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    week_label TEXT NOT NULL,
                    work_progress TEXT NOT NULL,
                    work_blocker TEXT NOT NULL,
                    blocker_type TEXT NOT NULL,
                    work_direction TEXT NOT NULL,
                    next_week_focus TEXT NOT NULL,
                    support_needed TEXT NOT NULL,
                    related_plan_ids_json TEXT NOT NULL DEFAULT '[]',
                    work_free_note TEXT NOT NULL DEFAULT '',
                    personal_growth_note TEXT NOT NULL DEFAULT '',
                    personal_private_note TEXT NOT NULL DEFAULT '',
                    personal_visibility TEXT NOT NULL DEFAULT 'self',
                    submitted_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, week_label),
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS weekly_review_sections (
                    id TEXT PRIMARY KEY,
                    review_id TEXT NOT NULL,
                    section_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_domain TEXT NOT NULL,
                    visibility_scope TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(review_id) REFERENCES weekly_review_entries(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS weekly_review_task_entries (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    review_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    week_label TEXT NOT NULL,
                    content_domain TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    structured_note_json TEXT NOT NULL DEFAULT '{}',
                    reviewed_at TEXT NOT NULL,
                    task_snapshot_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(review_id, task_id),
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(review_id) REFERENCES weekly_review_entries(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE,
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS management_signal_cards (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    review_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    week_label TEXT NOT NULL,
                    content_domain TEXT NOT NULL DEFAULT 'work',
                    visibility_scope TEXT NOT NULL DEFAULT 'team',
                    eligible_for_aggregation INTEGER NOT NULL DEFAULT 1,
                    eligible_for_manager_retrieval INTEGER NOT NULL DEFAULT 1,
                    signal_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(review_id, user_id, week_label),
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(review_id) REFERENCES weekly_review_entries(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS personal_growth_cards (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    review_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    content_domain TEXT NOT NULL DEFAULT 'personal',
                    visibility_scope TEXT NOT NULL DEFAULT 'self',
                    eligible_for_aggregation INTEGER NOT NULL DEFAULT 0,
                    eligible_for_manager_retrieval INTEGER NOT NULL DEFAULT 0,
                    summary_json TEXT NOT NULL,
                    suggestions_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(review_id, user_id),
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(review_id) REFERENCES weekly_review_entries(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS aggregated_scope_reports (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    scope_type TEXT NOT NULL,
                    scope_ref_id TEXT NOT NULL,
                    week_label TEXT NOT NULL,
                    logic_mode TEXT NOT NULL,
                    summary_json TEXT NOT NULL,
                    source_policy_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(scope_type, scope_ref_id, week_label, logic_mode),
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS report_action_cards (
                    id TEXT PRIMARY KEY,
                    report_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(report_id) REFERENCES aggregated_scope_reports(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS cloud_client_workspace_snapshots (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    snapshot_version INTEGER NOT NULL DEFAULT 1,
                    snapshot_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    UNIQUE(organization_id, client_id, source_id),
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_cloud_workspace_snapshots_client
                    ON cloud_client_workspace_snapshots(organization_id, client_id, updated_at DESC, published_at DESC);

                CREATE TABLE IF NOT EXISTS cloud_client_dna_summaries (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    snapshot_version INTEGER NOT NULL DEFAULT 1,
                    snapshot_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    UNIQUE(organization_id, client_id, source_id),
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_cloud_client_dna_client
                    ON cloud_client_dna_summaries(organization_id, client_id, updated_at DESC, published_at DESC);

                CREATE TABLE IF NOT EXISTS cloud_event_line_snapshots (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    snapshot_version INTEGER NOT NULL DEFAULT 1,
                    snapshot_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    UNIQUE(organization_id, client_id, source_id),
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_cloud_event_line_snapshots_client
                    ON cloud_event_line_snapshots(organization_id, client_id, updated_at DESC, published_at DESC);

                CREATE TABLE IF NOT EXISTS cloud_meeting_summaries (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    snapshot_version INTEGER NOT NULL DEFAULT 1,
                    snapshot_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    UNIQUE(organization_id, client_id, source_id),
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_cloud_meeting_summaries_client
                    ON cloud_meeting_summaries(organization_id, client_id, updated_at DESC, published_at DESC);

                CREATE TABLE IF NOT EXISTS cloud_knowledge_surrogates (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    snapshot_version INTEGER NOT NULL DEFAULT 1,
                    snapshot_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    UNIQUE(organization_id, client_id, source_id),
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_cloud_knowledge_surrogates_client
                    ON cloud_knowledge_surrogates(organization_id, client_id, updated_at DESC, published_at DESC);

                CREATE TABLE IF NOT EXISTS cloud_strategic_cockpit_snapshots (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    snapshot_version INTEGER NOT NULL DEFAULT 1,
                    snapshot_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    UNIQUE(organization_id, client_id, source_id),
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_cloud_cockpit_snapshots_client
                    ON cloud_strategic_cockpit_snapshots(organization_id, client_id, updated_at DESC, published_at DESC);

                CREATE TABLE IF NOT EXISTS cloud_context_bundle_cache (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    client_id TEXT,
                    event_line_id TEXT,
                    snapshot_hash TEXT NOT NULL,
                    context_quality_level TEXT NOT NULL DEFAULT 'none',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    available_sources_json TEXT NOT NULL DEFAULT '[]',
                    missing_sources_json TEXT NOT NULL DEFAULT '[]',
                    stale_sources_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(organization_id, snapshot_hash),
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_cloud_context_bundle_cache_client
                    ON cloud_context_bundle_cache(organization_id, client_id, updated_at DESC);
                """
            )
            self._migrate_task_tag_library_schema()
            self._ensure_column("employee_accounts", "department_id", "TEXT")
            self._ensure_column("employee_accounts", "department_name", "TEXT")
            self._ensure_column("employee_accounts", "job_title", "TEXT")
            self._ensure_column("employee_accounts", "manager_name", "TEXT")
            self._ensure_column("employee_accounts", "current_focus", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("employee_accounts", "is_department_lead", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("employee_accounts", "feishu_mobile", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("tasks", "tag_ids_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("tasks", "project_module_id", "TEXT")
            self._ensure_column("tasks", "project_flow_id", "TEXT")
            self._ensure_column("task_tag_library", "scope", "TEXT NOT NULL DEFAULT 'org'")
            self._ensure_column("task_tag_library", "color", "TEXT NOT NULL DEFAULT '#5B7BFE'")
            self._ensure_column("task_tag_library", "owner_user_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("task_tag_library", "created_by", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("task_tag_library", "updated_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("task_tag_library", "archived_at", "TEXT")
            self._ensure_column("task_lists", "is_default", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("task_lists", "scope", "TEXT NOT NULL DEFAULT 'org'")
            self._ensure_column("task_lists", "archived_at", "TEXT")
            self._ensure_column("org_profiles", "annual_strategy_year", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("org_profiles", "annual_strategy_text", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("org_profiles", "quarter_plans_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("org_departments", "business_context", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("org_departments", "team_context", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("org_departments", "quarter_plan_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column("weekly_review_task_entries", "structured_note_json", "TEXT NOT NULL DEFAULT '{}'")
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_settings (
                    user_id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    default_list_id TEXT,
                    default_priority TEXT NOT NULL DEFAULT 'normal',
                    default_due_date_preset TEXT NOT NULL DEFAULT 'today',
                    default_view_mode TEXT NOT NULL DEFAULT 'list',
                    list_sort_mode TEXT NOT NULL DEFAULT 'manual',
                    show_completed_tasks INTEGER NOT NULL DEFAULT 0,
                    default_review_scope TEXT NOT NULL DEFAULT 'work',
                    auto_assign_self INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(default_list_id) REFERENCES task_lists(id) ON DELETE SET NULL
                );
                """
            )
            self.conn.execute(
                "UPDATE task_lists SET is_default = CASE WHEN id = 'list-0' THEN 1 ELSE COALESCE(is_default, 0) END WHERE is_default IS NULL OR is_default = ''"
            )
            self._ensure_column("tasks", "client_id", "TEXT")
            self._ensure_column("tasks", "start_date", "TEXT")
            self._ensure_column("tasks", "duration_minutes", "INTEGER NOT NULL DEFAULT 60")
            self._ensure_column("tasks", "scope_mode", "TEXT NOT NULL DEFAULT 'COLLAB_SHARED'")
            self._ensure_column("tasks", "event_line_id", "TEXT")
            self._ensure_column("tasks", "business_category", "TEXT")
            self._ensure_column("tasks", "current_blocker", "TEXT")
            self._ensure_column("tasks", "next_action", "TEXT")
            self._ensure_column("tasks", "recent_decision", "TEXT")
            self._ensure_column("tasks", "completion_note", "TEXT")
            self._ensure_column("tasks", "evidence_count", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("event_lines", "business_category", "TEXT")
            self._ensure_column("event_lines", "current_blocker", "TEXT")
            self._ensure_column("event_lines", "recent_decision", "TEXT")
            self._ensure_column("event_lines", "evidence_count", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("event_lines", "primary_client_name", "TEXT")
            self._ensure_column("event_lines", "visibility_scope", "TEXT NOT NULL DEFAULT 'project_public'")
            self._ensure_column("event_lines", "closed_at", "TEXT")
            self._ensure_column("event_lines", "closed_by_user_id", "TEXT")
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS task_attachments (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    client_id TEXT,
                    event_line_id TEXT,
                    title TEXT NOT NULL,
                    summary TEXT,
                    path TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    source TEXT NOT NULL,
                    mime_type TEXT,
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    duration_seconds INTEGER NOT NULL DEFAULT 0,
                    created_by_user_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                    FOREIGN KEY(created_by_user_id) REFERENCES employee_accounts(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_task_attachments_task_created
                    ON task_attachments(task_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_task_attachments_event_line_created
                    ON task_attachments(event_line_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS org_ai_config (
                    org_id TEXT PRIMARY KEY,
                    ai_provider TEXT NOT NULL DEFAULT 'mock',
                    ai_model TEXT NOT NULL DEFAULT '',
                    api_key_encrypted TEXT NOT NULL DEFAULT '',
                    encryption_nonce TEXT NOT NULL DEFAULT '',
                    configured_by TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(org_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(configured_by) REFERENCES employee_accounts(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS org_feishu_integrations (
                    organization_id TEXT PRIMARY KEY,
                    app_id TEXT NOT NULL DEFAULT '',
                    app_secret_encrypted TEXT NOT NULL DEFAULT '',
                    encryption_nonce TEXT NOT NULL DEFAULT '',
                    callback_mode TEXT NOT NULL DEFAULT 'cloud_relay',
                    custom_callback_url TEXT NOT NULL DEFAULT '',
                    effective_callback_url TEXT NOT NULL DEFAULT '',
                    enabled INTEGER NOT NULL DEFAULT 0,
                    configured_by TEXT,
                    configured_at TEXT,
                    updated_at TEXT NOT NULL,
                    last_validation_status TEXT NOT NULL DEFAULT 'idle',
                    last_validation_message TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(configured_by) REFERENCES employee_accounts(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS org_feishu_integration_audits (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    actor_user_id TEXT,
                    app_id TEXT NOT NULL DEFAULT '',
                    callback_mode TEXT NOT NULL DEFAULT 'cloud_relay',
                    custom_callback_url TEXT NOT NULL DEFAULT '',
                    effective_callback_url TEXT NOT NULL DEFAULT '',
                    validation_status TEXT NOT NULL,
                    validation_message TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(actor_user_id) REFERENCES employee_accounts(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS org_feishu_member_authorizations (
                    organization_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    app_id TEXT NOT NULL DEFAULT '',
                    open_id TEXT,
                    union_id TEXT,
                    feishu_user_id TEXT,
                    name TEXT,
                    en_name TEXT,
                    avatar_url TEXT,
                    email TEXT,
                    tenant_key TEXT,
                    authorized_at TEXT,
                    last_verified_at TEXT,
                    last_error TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (organization_id, user_id),
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS org_feishu_delivery_targets (
                    organization_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    mobile TEXT NOT NULL DEFAULT '',
                    receive_id_type TEXT NOT NULL DEFAULT 'open_id',
                    receive_id TEXT,
                    match_status TEXT NOT NULL DEFAULT 'not_found',
                    last_verified_at TEXT,
                    last_error TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (organization_id, user_id),
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_org_feishu_delivery_targets_status
                    ON org_feishu_delivery_targets(organization_id, match_status, updated_at DESC);

                CREATE TABLE IF NOT EXISTS org_feishu_task_notifications (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    recipient_user_id TEXT NOT NULL,
                    recipient_open_id TEXT,
                    delivery_status TEXT NOT NULL,
                    delivery_message TEXT NOT NULL DEFAULT '',
                    changed_fields_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                    FOREIGN KEY(recipient_user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_org_feishu_task_notifications_task
                    ON org_feishu_task_notifications(task_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_org_feishu_task_notifications_recipient
                    ON org_feishu_task_notifications(recipient_user_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS org_feishu_notifications (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    message_type TEXT NOT NULL,
                    object_type TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    event_type TEXT NOT NULL DEFAULT '',
                    recipient_user_id TEXT NOT NULL,
                    recipient_open_id TEXT,
                    title TEXT NOT NULL DEFAULT '',
                    card_json TEXT NOT NULL DEFAULT '',
                    text_fallback TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    dedupe_key TEXT,
                    delivery_status TEXT NOT NULL DEFAULT 'queued',
                    delivery_channel TEXT NOT NULL DEFAULT '',
                    delivery_message TEXT NOT NULL DEFAULT '',
                    due_at TEXT,
                    sent_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(recipient_user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_org_feishu_notifications_due
                    ON org_feishu_notifications(delivery_status, due_at, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_org_feishu_notifications_recipient
                    ON org_feishu_notifications(recipient_user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_org_feishu_notifications_dedupe
                    ON org_feishu_notifications(dedupe_key, recipient_user_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS org_feishu_query_logs (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    message_id TEXT NOT NULL UNIQUE,
                    sender_open_id TEXT NOT NULL,
                    sender_feishu_user_id TEXT,
                    chat_id TEXT NOT NULL DEFAULT '',
                    query_type TEXT NOT NULL DEFAULT '',
                    query_text TEXT NOT NULL DEFAULT '',
                    resolved_user_id TEXT,
                    status TEXT NOT NULL DEFAULT 'resolved',
                    reply_excerpt TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(resolved_user_id) REFERENCES employee_accounts(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_org_feishu_query_logs_org_created
                    ON org_feishu_query_logs(organization_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_org_feishu_query_logs_sender
                    ON org_feishu_query_logs(sender_open_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS event_line_attachments (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    event_line_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT,
                    path TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'event_line_attachment',
                    mime_type TEXT,
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    created_by_user_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(event_line_id) REFERENCES event_lines(id) ON DELETE CASCADE,
                    FOREIGN KEY(created_by_user_id) REFERENCES employee_accounts(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS task_notes (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    task_id TEXT NOT NULL UNIQUE,
                    user_id TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS consultation_answers (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    author_user_id TEXT NOT NULL,
                    client_id TEXT,
                    client_name TEXT,
                    task_id TEXT,
                    event_line_id TEXT,
                    question TEXT NOT NULL DEFAULT '',
                    answer TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'mobile_consult',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(author_user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE,
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE SET NULL,
                    FOREIGN KEY(event_line_id) REFERENCES event_lines(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_consultation_answers_org_created
                    ON consultation_answers(organization_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS consultation_knowledge_requests (
                    id TEXT PRIMARY KEY,
                    answer_id TEXT NOT NULL,
                    organization_id TEXT NOT NULL,
                    target TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    requested_by_user_id TEXT NOT NULL,
                    error_message TEXT,
                    local_document_id TEXT,
                    local_document_path TEXT,
                    completed_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(answer_id) REFERENCES consultation_answers(id) ON DELETE CASCADE,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(requested_by_user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_consultation_knowledge_requests_org_status
                    ON consultation_knowledge_requests(organization_id, status, updated_at DESC);
                """
            )
            self.conn.execute(
                """
                UPDATE employee_accounts
                   SET account_status = 'approved',
                       approved_at = COALESCE(approved_at, created_at),
                       rejected_reason = NULL,
                       disabled_at = NULL,
                       updated_at = COALESCE(updated_at, created_at)
                 WHERE account_status = 'pending'
                """
            )
            self.conn.commit()

    def _table_columns(self, table_name: str) -> set[str]:
        return {
            str(row["name"])
            for row in self.conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }

    def _ensure_column(self, table_name: str, column_name: str, definition: str) -> None:
        if column_name in self._table_columns(table_name):
            return
        self.conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

    def _migrate_task_tag_library_schema(self) -> None:
        columns = self._table_columns("task_tag_library")
        if {"scope", "owner_user_id", "updated_at"}.issubset(columns):
            return
        self.conn.execute("ALTER TABLE task_tag_library RENAME TO task_tag_library_legacy")
        self.conn.executescript(
            """
            CREATE TABLE task_tag_library (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                name TEXT NOT NULL,
                scope TEXT NOT NULL DEFAULT 'org',
                owner_user_id TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT '',
                UNIQUE(organization_id, scope, owner_user_id, name),
                FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE
            );
            """
        )
        self.conn.execute(
            """
            INSERT INTO task_tag_library(id, organization_id, name, scope, owner_user_id, created_at, updated_at)
            SELECT id, organization_id, name, 'org', '', created_at, created_at
            FROM task_tag_library_legacy
            """
        )
        self.conn.execute("DROP TABLE task_tag_library_legacy")

    def fetchone(self, query: str, params: tuple = ()) -> sqlite3.Row | None:
        with self._lock:
            cur = self.conn.execute(query, params)
            return cur.fetchone()

    def fetchall(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            cur = self.conn.execute(query, params)
            return cur.fetchall()

    def execute(self, query: str, params: tuple = ()) -> None:
        with self._lock:
            self.conn.execute(query, params)
            self.conn.commit()

    def executemany(self, query: str, params: list[tuple]) -> None:
        with self._lock:
            self.conn.executemany(query, params)
            self.conn.commit()

    def executescript(self, script: str) -> None:
        with self._lock:
            self.conn.executescript(script)
            self.conn.commit()

    def scalar(self, query: str, params: tuple = ()) -> int:
        row = self.fetchone(query, params)
        if not row:
            return 0
        first_key = row.keys()[0]
        value = row[first_key]
        if value is None:
            return 0
        return int(value)

    def set_setting(self, key: str, value: str) -> None:
        self.execute(
            """
            INSERT INTO settings(key, value) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )

    def get_setting(self, key: str, default: str = "") -> str:
        row = self.fetchone("SELECT value FROM settings WHERE key = ?", (key,))
        return str(row["value"]) if row else default

    def backup_to(self, target_path: Path) -> Path:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self.conn.commit()
            shutil.copy2(self.db_path, target_path)
        return target_path


def to_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def from_json(value: str | None, default: object) -> object:
    if not value:
        return default
    return json.loads(value)
~~~

## `cloud_backend/app/department_catalog.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DepartmentCatalogEntry:
    id: str
    name: str
    color: str
    aliases: tuple[str, ...] = ()


DEPARTMENT_CATALOG: tuple[DepartmentCatalogEntry, ...] = (
    DepartmentCatalogEntry(
        id="dept_consult_strategy",
        name="咨询策略部",
        color="#5B7BFE",
        aliases=("咨询策略", "咨询策略部", "战略设计部", "战略设计", "战略陪伴组"),
    ),
    DepartmentCatalogEntry(
        id="dept_tech_development",
        name="科技发展部",
        color="#F59E0B",
        aliases=("科技发展部", "科技发展"),
    ),
    DepartmentCatalogEntry(
        id="dept_info_data",
        name="信息数据部",
        color="#10B981",
        aliases=("信息数据部", "信息数据", "洞察研究", "洞察研究部"),
    ),
    DepartmentCatalogEntry(
        id="dept_customer_service",
        name="客户服务部",
        color="#14B8A6",
        aliases=("客户服务部", "客户服务", "交付协同", "交付协同部"),
    ),
)

_ALIAS_LOOKUP: dict[str, DepartmentCatalogEntry] = {}
for _entry in DEPARTMENT_CATALOG:
    _ALIAS_LOOKUP[_entry.id.lower()] = _entry
    _ALIAS_LOOKUP[_entry.name.lower()] = _entry
    for _alias in _entry.aliases:
        _ALIAS_LOOKUP[_alias.lower()] = _entry


def list_department_catalog() -> list[DepartmentCatalogEntry]:
    return list(DEPARTMENT_CATALOG)


def get_department_entry(raw_id: str | None = None, raw_name: str | None = None) -> DepartmentCatalogEntry | None:
    for value in (raw_id, raw_name):
        key = (value or "").strip().lower()
        if key and key in _ALIAS_LOOKUP:
            return _ALIAS_LOOKUP[key]
    return None
~~~

## `cloud_backend/app/knowledge_store.py`

- 编码: `utf-8`

~~~python
"""
向量知识库 — ChromaDB + 本地 Embedding

使用 ChromaDB 内置的 default embedding function（基于 all-MiniLM-L6-v2），
提供语义检索能力：
1. 把咨询问答、任务摘要、事件线资料等写入向量库
2. 咨询时按语义相关性检索最相关的知识片段
"""
from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ─── ChromaDB Knowledge Store ───────────────────

_chroma_client = None
_chroma_collection = None

CHROMA_COLLECTION_NAME = "yiyu_knowledge"


def desktop_app_db_candidates() -> list[Path]:
    candidates: list[Path] = []
    explicit = os.getenv("YIYU_DESKTOP_APP_DB_PATH", "").strip()
    if explicit:
        candidates.append(Path(explicit))

    suffix = Path("Library") / "Application Support" / "YiyuThinkTankWorkbench" / "app.db"
    for base in (Path.home(), Path("/home/yiyu"), Path("/var/lib/yiyu-cloud")):
        candidate = base / suffix
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def find_desktop_app_db_path() -> Path | None:
    for candidate in desktop_app_db_candidates():
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _data_dir() -> Path:
    base = os.getenv(
        "YIYU_CLOUD_DATA_DIR",
        str(Path.home() / "Library" / "Application Support" / "YiyuThinkTankCloud"),
    )
    return Path(base) / "chromadb"


def _get_collection():
    """Lazy-init ChromaDB persistent client + collection.

    Uses ChromaDB's default embedding function which auto-downloads
    and runs a lightweight model (all-MiniLM-L6-v2) locally.
    No external API calls needed for embedding.
    """
    global _chroma_client, _chroma_collection
    if _chroma_collection is not None:
        return _chroma_collection

    import chromadb

    persist_dir = str(_data_dir())
    os.makedirs(persist_dir, exist_ok=True)
    _chroma_client = chromadb.PersistentClient(path=persist_dir)
    _chroma_collection = _chroma_client.get_or_create_collection(
        name=CHROMA_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info(
        "ChromaDB collection '%s' ready at %s (%d docs)",
        CHROMA_COLLECTION_NAME,
        persist_dir,
        _chroma_collection.count(),
    )
    return _chroma_collection


def _doc_id(org_id: str, source: str, content: str) -> str:
    """Deterministic ID to avoid duplicates."""
    h = hashlib.sha256(f"{org_id}:{source}:{content}".encode()).hexdigest()[:16]
    return f"{org_id}-{source}-{h}"


# ─── Public API ─────────────────────────────────


def add_knowledge(
    *,
    organization_id: str,
    source: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Add a knowledge document to the vector store.

    ChromaDB handles embedding automatically using its default model.
    """
    if not content.strip():
        return False

    doc_id = _doc_id(organization_id, source, content)
    meta = {"organization_id": organization_id, "source": source}
    if metadata:
        meta.update({k: str(v) for k, v in metadata.items() if v is not None})

    try:
        collection = _get_collection()
        collection.upsert(
            ids=[doc_id],
            documents=[content],
            metadatas=[meta],
        )
        return True
    except Exception as exc:
        logger.error("ChromaDB upsert error: %s", exc)
        return False


def query_knowledge(
    *,
    organization_id: str,
    query: str,
    n_results: int = 15,
    client_id: str | None = None,
) -> list[str]:
    """Retrieve relevant knowledge snippets by semantic similarity.

    ChromaDB handles query embedding automatically.
    Returns list of document texts, most relevant first.
    """
    try:
        collection = _get_collection()
        if collection.count() == 0:
            return []

        if client_id:
            where_filter: dict[str, Any] = {
                "$and": [
                    {"organization_id": organization_id},
                    {"client_id": client_id},
                ]
            }
        else:
            where_filter = {"organization_id": organization_id}

        results = collection.query(
            query_texts=[query],
            n_results=min(n_results, 25),
            where=where_filter,
        )
        documents = results.get("documents", [[]])[0]
        return [doc for doc in documents if doc]
    except Exception as exc:
        logger.error("ChromaDB query error: %s", exc)
        return []


def ingest_consultation_answer(
    *,
    organization_id: str,
    question: str,
    answer: str,
    client_id: str | None = None,
    client_name: str | None = None,
    event_line_id: str | None = None,
) -> bool:
    """Convenience: ingest a Q&A pair into the knowledge store."""
    content = f"问题：{question}\n回答：{answer}"
    return add_knowledge(
        organization_id=organization_id,
        source="consultation",
        content=content,
        metadata={
            "client_id": client_id,
            "client_name": client_name,
            "event_line_id": event_line_id,
            "type": "qa",
        },
    )


def ingest_event_line_summary(
    *,
    organization_id: str,
    event_line_id: str,
    client_id: str | None = None,
    client_name: str | None = None,
    name: str,
    summary: str | None = None,
    blocker: str | None = None,
    next_step: str | None = None,
) -> bool:
    """Ingest event line context into the knowledge store."""
    parts = [f"事件线：{name}"]
    if summary:
        parts.append(f"摘要：{summary}")
    if blocker:
        parts.append(f"当前阻塞：{blocker}")
    if next_step:
        parts.append(f"下一步：{next_step}")
    content = "\n".join(parts)
    return add_knowledge(
        organization_id=organization_id,
        source="event_line",
        content=content,
        metadata={
            "client_id": client_id,
            "client_name": client_name,
            "event_line_id": event_line_id,
            "type": "event_line",
        },
    )


def sync_desktop_surrogates_to_cloud(
    *,
    organization_id: str,
    client_id: str,
    client_name: str,
) -> dict[str, int]:
    """Sync desktop surrogate blocks (enriched + profile) into cloud ChromaDB.

    Reads from the desktop app.db and vector_store directory, then upserts
    the AI-enriched retrieval_summary + overview_summary into ChromaDB.
    """
    import sqlite3 as _sqlite3

    desktop_db_path = find_desktop_app_db_path()
    if desktop_db_path is None:
        return {"synced": 0, "error": "desktop db not found"}

    synced = 0
    try:
        conn = _sqlite3.connect(str(desktop_db_path))
        conn.row_factory = _sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, title, folder_category, source_type, overview_summary, retrieval_summary,
                   document_role, distinct_findings_json
            FROM knowledge_surrogates
            WHERE client_id = ?
            ORDER BY updated_at DESC
            """,
            (client_id,),
        ).fetchall()
        conn.close()
    except Exception as exc:
        logger.error("Desktop DB read failed: %s", exc)
        return {"synced": 0, "error": str(exc)}

    for row in rows:
        source_type = str(row["source_type"] or "document")
        title = str(row["title"] or "")
        overview = str(row["overview_summary"] or "")
        retrieval = str(row["retrieval_summary"] or "")
        category = str(row["folder_category"] or "")
        role = str(row["document_role"] or "")

        # Build a rich content block for ChromaDB
        content_parts = [f"【{title}】"]
        if role:
            content_parts.append(f"角色：{role}")
        if category:
            content_parts.append(f"分类：{category}")
        if overview:
            content_parts.append(overview[:1500])
        if retrieval:
            content_parts.append(f"检索摘要：{retrieval}")

        # Parse distinct findings
        try:
            import json
            findings = json.loads(row["distinct_findings_json"]) if row["distinct_findings_json"] else []
            if isinstance(findings, list) and findings:
                content_parts.append("关键发现：" + "；".join(str(f) for f in findings[:5]))
        except Exception:
            pass

        content = "\n".join(content_parts)
        if len(content.strip()) < 50:
            continue

        doc_type = "profile_block" if source_type == "memory_answer" else "surrogate"
        success = add_knowledge(
            organization_id=organization_id,
            source=f"desktop_{doc_type}",
            content=content,
            metadata={
                "client_id": client_id,
                "client_name": client_name,
                "type": doc_type,
                "category": category,
                "surrogate_id": str(row["id"]),
            },
        )
        if success:
            synced += 1

    return {"synced": synced, "total": len(rows)}
~~~

## `cloud_backend/app/main.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import asyncio
import hashlib
import html
import ipaddress
import json
import logging
import mimetypes
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event, Thread
from typing import Literal, cast
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
    CloudKnowledgeMirrorPublishPayload,
    CloudKnowledgeMirrorPublishResultRecord,
    ConsultationChatPayload,
    ConsultationChatResponse,
    ConsultationContextQualityRecord,
    ConsultationEvidenceRecord,
    ConsultationKnowledgeRequestCreatePayload,
    ConsultationKnowledgeRequestRecord,
    ConsultationKnowledgeRequestUpdatePayload,
    ConsultationMissingContextRecord,
    DepartmentOption,
    EmployeeRecord,
    EmployeeDepartmentPayload,
    EventLineActivityRecord,
    EventLineCreatePayload,
    EventLineDetailRecord,
    EventLineImportBatchPayload,
    EventLineImportItemResult,
    EventLineImportResultRecord,
    EventLineRecord,
    EventLineReportAttachmentRecord,
    EventLineReportSnapshotRecord,
    EventLineUpdatePayload,
    FeishuBadgeNotificationPayload,
    FeishuDeliveryProfileRecord,
    FeishuDeliveryProfileSavePayload,
    FeishuNotificationDispatchRecord,
    HealthResponse,
    HierarchyReportRecord,
    FeishuBindingRelaySessionCreatePayload,
    FeishuBindingRelaySessionStatusRecord,
    AdminResetPasswordPayload,
    ChangePasswordPayload,
    LoginPayload,
    ManagementSignalCardRecord,
    MentionCandidate,
    MobileCapabilityRecord,
    MobileContextSourceStatusRecord,
    MobileCockpitHeadlineRecord,
    MobileCockpitSummaryItemRecord,
    MobileStrategicCockpitCompatResponse,
    MobileWorkspaceCompatClientRecord,
    MobileWorkspaceCompatItemRecord,
    MobileWorkspaceCompatResponse,
    MobileWorkspaceCompatTaskRecord,
    MobileWorkspaceKnowledgeStatusRecord,
    OrgDepartmentRecord,
    OrgFeishuIntegrationAuditRecord,
    OrgFeishuIntegrationRecord,
    OrgFeishuIntegrationSavePayload,
    OrgDepartmentPlanItemRecord,
    OrgDepartmentPlanRecord,
    OrgDepartmentQuarterPlanRecord,
    OrgEmployeeBindingRecord,
    OrgFocusItemRecord,
    OrgMembershipSummaryRecord,
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
    UpdateProfilePayload,
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
TASK_IMMEDIATE_FEISHU_CHANGE_FIELDS: tuple[str, ...] = ("startDate", "dueDate", "durationMinutes", "ownerId", "collaboratorIds")
TASK_DEFERRED_FEISHU_CHANGE_FIELDS: tuple[str, ...] = ("title", "description", "priority", "listId")
FEISHU_QUERY_REPLY_LIMIT = 5
FEISHU_QUERY_HELP_TEXT = (
    "当前支持这些问法：\n"
    "1. 我今天有哪些任务\n"
    "2. 我本周有哪些任务\n"
    "3. 我有哪些逾期任务\n"
    "4. 我有哪些待确认协作任务\n"
    "5. 我有哪些任务未完成 / 我的待办\n"
    "6. 我有哪些进行中的任务 / 我有哪些已完成任务\n"
    "7. 我和顾源源协作的任务有哪些\n"
    "8. 我这周复盘提交了吗\n"
    "9. 我参与的事件线有哪些\n"
    "10. 任务 xxx 状态 / 事件线 xxx 状态\n"
)


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
    feishu_notification_stop: Event = field(default_factory=Event)
    feishu_notification_thread: Thread | None = None
    feishu_notifications: "FeishuNotificationService | None" = None
    feishu_query_stop: Event = field(default_factory=Event)
    feishu_query_thread: Thread | None = None
    feishu_query_manager: "FeishuLongConnectionCoordinator | None" = None


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


MIRROR_TABLE_BY_SOURCE_TYPE: dict[str, str] = {
    "workspace_snapshot": "cloud_client_workspace_snapshots",
    "client_dna": "cloud_client_dna_summaries",
    "event_line_snapshot": "cloud_event_line_snapshots",
    "meeting_summary": "cloud_meeting_summaries",
    "knowledge_surrogate": "cloud_knowledge_surrogates",
    "strategic_cockpit": "cloud_strategic_cockpit_snapshots",
}


def _client_row_or_404(state: AppState, client_id: str, organization_id: str):
    row = _client_row_by_id(state, client_id, organization_id)
    if not row:
        raise HTTPException(status_code=404, detail="Client not found")
    return row


def _mirror_latest_row(
    state: AppState,
    table_name: str,
    organization_id: str,
    client_id: str,
    source_id: str | None = None,
):
    sql = f"SELECT * FROM {table_name} WHERE organization_id = ? AND client_id = ?"
    params: list[str] = [organization_id, client_id]
    if source_id:
        sql += " AND source_id = ?"
        params.append(source_id)
    sql += " ORDER BY updated_at DESC, published_at DESC LIMIT 1"
    return state.db.fetchone(sql, tuple(params))


def _mirror_rows(
    state: AppState,
    table_name: str,
    organization_id: str,
    client_id: str,
    limit: int = 4,
):
    return state.db.fetchall(
        f"""
        SELECT *
        FROM {table_name}
        WHERE organization_id = ? AND client_id = ?
        ORDER BY updated_at DESC, published_at DESC
        LIMIT ?
        """,
        (organization_id, client_id, limit),
    )


def _mirror_payload(row) -> dict[str, object]:
    if not row:
        return {}
    raw_payload = from_json(str(row["payload_json"] or "{}"), {})
    return raw_payload if isinstance(raw_payload, dict) else {}


def _mirror_updated_at(row) -> str | None:
    if not row:
        return None
    return str(row["updated_at"] or row["published_at"] or "") or None


def _mirror_has_any_records(state: AppState, organization_id: str) -> bool:
    for table_name in MIRROR_TABLE_BY_SOURCE_TYPE.values():
        if state.db.scalar(
            f"SELECT COUNT(1) AS count FROM {table_name} WHERE organization_id = ?",
            (organization_id,),
        ):
            return True
    return False


def _context_source_status(
    source: str,
    *,
    available: bool,
    status: Literal["ready", "partial", "missing", "unavailable"],
    detail: str | None = None,
    updated_at: str | None = None,
) -> MobileContextSourceStatusRecord:
    return MobileContextSourceStatusRecord(
        source=source,
        available=available,
        status=status,
        detail=detail,
        updatedAt=updated_at,
    )


def _coerce_text(value: object | None, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _mobile_summary_item(item: dict[str, object] | None, fallback_title: str) -> MobileWorkspaceCompatItemRecord:
    payload = item or {}
    item_id = _coerce_text(
        payload.get("id")
        or payload.get("meetingId")
        or payload.get("documentId")
        or payload.get("questionId")
        or fallback_title,
        fallback_title,
    )
    return MobileWorkspaceCompatItemRecord(
        id=item_id,
        title=_coerce_text(payload.get("title") or payload.get("name") or payload.get("label"), fallback_title),
        summary=_coerce_text(payload.get("summary") or payload.get("description") or payload.get("note")),
        subtitle=_coerce_text(payload.get("subtitle") or payload.get("updatedAt") or payload.get("sourceType")),
        updatedAt=_coerce_text(payload.get("updatedAt") or payload.get("createdAt")) or None,
    )


def _mobile_task_item(item: dict[str, object] | None) -> MobileWorkspaceCompatTaskRecord:
    payload = item or {}
    return MobileWorkspaceCompatTaskRecord(
        id=_coerce_text(payload.get("id"), "unknown-task"),
        title=_coerce_text(payload.get("title") or payload.get("name"), "未命名任务"),
        status=_coerce_text(payload.get("status") or payload.get("progressStatus")),
        clientName=_coerce_text(payload.get("clientName")) or None,
        eventLineName=_coerce_text(payload.get("eventLineName")) or None,
        nextAction=_coerce_text(payload.get("nextAction")) or None,
    )


def _build_mobile_capabilities(state: AppState, current_user: SessionUser) -> MobileCapabilityRecord:
    return MobileCapabilityRecord(
        consultationChat=True,
        clientWorkspace=True,
        strategicCockpit=True,
        knowledgeMirror=_mirror_has_any_records(state, current_user.organizationId),
        contextBundle=True,
        consultationPayloadVersion="v2",
        updatedAt=now_iso(),
    )


def _workspace_related_tasks(state: AppState, client_id: str, organization_id: str, limit: int = 6) -> list[MobileWorkspaceCompatTaskRecord]:
    rows = state.db.fetchall(
        """
        SELECT id, title, progress_status, current_blocker, next_action, updated_at
        FROM tasks
        WHERE organization_id = ? AND client_id = ?
        ORDER BY updated_at DESC, created_at DESC
        LIMIT ?
        """,
        (organization_id, client_id, limit),
    )
    return [
        MobileWorkspaceCompatTaskRecord(
            id=str(row["id"]),
            title=_coerce_text(row["title"], "未命名任务"),
            status=_coerce_text(row["progress_status"]),
            nextAction=_coerce_text(row["next_action"]) or _coerce_text(row["current_blocker"]) or None,
        )
        for row in rows
    ]


def _event_line_summary_items(state: AppState, client_id: str, organization_id: str, limit: int = 4) -> list[MobileWorkspaceCompatItemRecord]:
    rows = state.db.fetchall(
        """
        SELECT id, name, stage, summary, current_blocker, next_step, updated_at
        FROM event_lines
        WHERE organization_id = ? AND primary_client_id = ?
        ORDER BY updated_at DESC, created_at DESC
        LIMIT ?
        """,
        (organization_id, client_id, limit),
    )
    return [
        MobileWorkspaceCompatItemRecord(
            id=str(row["id"]),
            title=_coerce_text(row["name"], "事件线"),
            summary=_coerce_text(row["summary"]) or _coerce_text(row["current_blocker"]) or _coerce_text(row["next_step"]),
            subtitle=_coerce_text(row["stage"]),
            updatedAt=_coerce_text(row["updated_at"]) or None,
        )
        for row in rows
    ]


def _recent_meeting_items_from_mirror(state: AppState, organization_id: str, client_id: str) -> list[MobileWorkspaceCompatItemRecord]:
    rows = _mirror_rows(state, "cloud_meeting_summaries", organization_id, client_id, limit=4)
    result: list[MobileWorkspaceCompatItemRecord] = []
    for row in rows:
        payload = _mirror_payload(row)
        result.append(
            MobileWorkspaceCompatItemRecord(
                id=_coerce_text(row["source_id"], "meeting"),
                title=_coerce_text(payload.get("title"), "会议"),
                summary=_coerce_text(payload.get("summary") or payload.get("coreConclusion")),
                subtitle=_coerce_text(payload.get("meetingDate") or payload.get("participantSummary")),
                updatedAt=_mirror_updated_at(row),
            )
        )
    return result


def _recent_document_items_from_mirror(state: AppState, organization_id: str, client_id: str) -> list[MobileWorkspaceCompatItemRecord]:
    rows = _mirror_rows(state, "cloud_knowledge_surrogates", organization_id, client_id, limit=4)
    result: list[MobileWorkspaceCompatItemRecord] = []
    for row in rows:
        payload = _mirror_payload(row)
        result.append(
            MobileWorkspaceCompatItemRecord(
                id=_coerce_text(row["source_id"], "knowledge"),
                title=_coerce_text(payload.get("title"), "知识代理"),
                summary=_coerce_text(payload.get("summary") or payload.get("overview") or payload.get("overviewSummary")),
                subtitle=_coerce_text(payload.get("sourceType") or payload.get("documentType")),
                updatedAt=_mirror_updated_at(row),
            )
        )
    return result


def _build_workspace_compat_response(state: AppState, client_row, organization_id: str) -> MobileWorkspaceCompatResponse:
    client_id = str(client_row["id"])
    client_name = _coerce_text(client_row["name"], "客户")
    workspace_row = _mirror_latest_row(state, "cloud_client_workspace_snapshots", organization_id, client_id)
    cockpit_row = _mirror_latest_row(state, "cloud_strategic_cockpit_snapshots", organization_id, client_id)
    dna_row = _mirror_latest_row(state, "cloud_client_dna_summaries", organization_id, client_id)
    meeting_items = _recent_meeting_items_from_mirror(state, organization_id, client_id)
    surrogate_items = _recent_document_items_from_mirror(state, organization_id, client_id)
    related_tasks = _workspace_related_tasks(state, client_id, organization_id)
    event_line_items = _event_line_summary_items(state, client_id, organization_id)

    available_sources: list[MobileContextSourceStatusRecord] = []
    missing_sources: list[str] = []

    workspace_payload = _mirror_payload(workspace_row)
    workspace_updated_at = _mirror_updated_at(workspace_row)

    if workspace_row:
        available_sources.append(
            _context_source_status(
                "workspace_snapshot",
                available=True,
                status="ready",
                detail="已找到云端客户工作台快照。",
                updated_at=workspace_updated_at,
            )
        )
    else:
        missing_sources.append("workspace_snapshot")
        available_sources.append(
            _context_source_status(
                "workspace_snapshot",
                available=False,
                status="missing",
                detail="当前云端没有客户工作台快照，只能退回轻量兼容视图。",
            )
        )

    if dna_row:
        available_sources.append(
            _context_source_status(
                "client_dna",
                available=True,
                status="ready",
                detail="已找到客户 DNA 摘要。",
                updated_at=_mirror_updated_at(dna_row),
            )
        )
    else:
        missing_sources.append("client_dna")
        available_sources.append(
            _context_source_status(
                "client_dna",
                available=False,
                status="missing",
                detail="未找到客户 DNA 摘要。",
            )
        )

    if meeting_items:
        available_sources.append(
            _context_source_status(
                "recent_meetings",
                available=True,
                status="ready",
                detail="已找到最近会议摘要。",
                updated_at=meeting_items[0].updatedAt,
            )
        )
    else:
        missing_sources.append("recent_meetings")
        available_sources.append(
            _context_source_status(
                "recent_meetings",
                available=False,
                status="missing",
                detail="云端没有最近会议摘要。",
            )
        )

    if cockpit_row:
        available_sources.append(
            _context_source_status(
                "strategic_cockpit",
                available=True,
                status="ready",
                detail="已找到战略 cockpit 快照。",
                updated_at=_mirror_updated_at(cockpit_row),
            )
        )
    else:
        missing_sources.append("strategic_cockpit")
        available_sources.append(
            _context_source_status(
                "strategic_cockpit",
                available=False,
                status="missing",
                detail="云端还没有战略 cockpit 快照。",
            )
        )

    if surrogate_items:
        available_sources.append(
            _context_source_status(
                "knowledge_surrogate",
                available=True,
                status="ready",
                detail="已找到知识代理摘要。",
                updated_at=surrogate_items[0].updatedAt,
            )
        )
    else:
        missing_sources.append("knowledge_surrogate")
        available_sources.append(
            _context_source_status(
                "knowledge_surrogate",
                available=False,
                status="missing",
                detail="云端没有可用于咨询的知识代理。",
            )
        )

    goals = [
        _mobile_summary_item(item, "目标")
        for item in cast(list[dict[str, object]], workspace_payload.get("goals") or [])
    ] if workspace_payload.get("goals") else event_line_items
    meetings = [
        _mobile_summary_item(item, "会议")
        for item in cast(list[dict[str, object]], workspace_payload.get("meetings") or [])
    ] if workspace_payload.get("meetings") else meeting_items
    document_cards = [
        _mobile_summary_item(item, "资料")
        for item in cast(list[dict[str, object]], workspace_payload.get("documentCards") or [])
    ] if workspace_payload.get("documentCards") else surrogate_items
    latest_open_questions = [
        _mobile_summary_item(item, "开放问题")
        for item in cast(list[dict[str, object]], workspace_payload.get("latestOpenQuestions") or [])
    ]
    latest_conflicts = [
        _mobile_summary_item(item, "冲突")
        for item in cast(list[dict[str, object]], workspace_payload.get("latestConflicts") or [])
    ]
    if not latest_open_questions:
        latest_open_questions = [
            MobileWorkspaceCompatItemRecord(
                id=f"task-open-{task.id}",
                title=task.title,
                summary=task.nextAction or "缺少更完整的工作台/会议资料，当前只保留了任务面上的下一步。",
                subtitle=task.status,
            )
            for task in related_tasks[:3]
            if task.nextAction
        ]
    if not latest_conflicts and event_line_items:
        latest_conflicts = [
            MobileWorkspaceCompatItemRecord(
                id=f"line-conflict-{item.id}",
                title=item.title,
                summary=item.summary or "当前云端还没有正式冲突整理，只保留了事件线摘要。",
                subtitle=item.subtitle,
                updatedAt=item.updatedAt,
            )
            for item in event_line_items[:2]
            if item.summary
        ]

    if workspace_payload.get("relatedTasks"):
        related_tasks = [
            _mobile_task_item(item)
            for item in cast(list[dict[str, object]], workspace_payload.get("relatedTasks") or [])
        ]

    status: Literal["rich", "partial", "missing"]
    if workspace_row and not missing_sources:
        status = "rich"
    elif goals or meetings or document_cards or related_tasks:
        status = "partial"
    else:
        status = "missing"

    if workspace_payload.get("missingSources"):
        for source in cast(list[object], workspace_payload.get("missingSources") or []):
            source_name = _coerce_text(source)
            if source_name and source_name not in missing_sources:
                missing_sources.append(source_name)

    knowledge_status = MobileWorkspaceKnowledgeStatusRecord(
        status="ready" if status == "rich" else ("partial" if status == "partial" else "missing"),
        statusLabel="工作台资料已同步" if status == "rich" else ("工作台资料部分可用" if status == "partial" else "工作台资料未同步"),
        summary=(
            "已找到客户工作台、战略判断和最近资料，可以提供较完整的上下文。"
            if status == "rich"
            else (
                "当前只找到了部分云端资料，更多上下文仍缺失。"
                if status == "partial"
                else "当前云端没有这位客户的工作台快照，只能显示轻量兼容结果。"
            )
        ),
        missingSources=missing_sources,
        updatedAt=workspace_updated_at,
    )

    return MobileWorkspaceCompatResponse(
        client=MobileWorkspaceCompatClientRecord(id=client_id, name=client_name, updatedAt=_coerce_text(client_row["updated_at"]) or None),
        status=status,
        updatedAt=workspace_updated_at or _coerce_text(client_row["updated_at"]) or None,
        goals=goals[:4],
        meetings=meetings[:4],
        documentCards=document_cards[:4],
        latestOpenQuestions=latest_open_questions[:4],
        latestConflicts=latest_conflicts[:4],
        relatedTasks=related_tasks[:6],
        knowledgeStatus=knowledge_status,
        missingSources=missing_sources,
        sourceAvailability=available_sources,
    )


def _build_cockpit_compat_response(state: AppState, client_row, organization_id: str) -> MobileStrategicCockpitCompatResponse:
    client_id = str(client_row["id"])
    client_name = _coerce_text(client_row["name"], "客户")
    cockpit_row = _mirror_latest_row(state, "cloud_strategic_cockpit_snapshots", organization_id, client_id)
    workspace_row = _mirror_latest_row(state, "cloud_client_workspace_snapshots", organization_id, client_id)
    dna_row = _mirror_latest_row(state, "cloud_client_dna_summaries", organization_id, client_id)
    event_line_rows = state.db.fetchall(
        """
        SELECT id, name, stage, summary, current_blocker, next_step, updated_at
        FROM event_lines
        WHERE organization_id = ? AND primary_client_id = ?
        ORDER BY updated_at DESC, created_at DESC
        LIMIT 4
        """,
        (organization_id, client_id),
    )
    cockpit_payload = _mirror_payload(cockpit_row)
    available_sources: list[MobileContextSourceStatusRecord] = []
    missing_sources: list[str] = []

    def _status_for(row, source: str, missing_detail: str, ready_detail: str) -> None:
        if row:
            available_sources.append(
                _context_source_status(
                    source,
                    available=True,
                    status="ready",
                    detail=ready_detail,
                    updated_at=_mirror_updated_at(row),
                )
            )
        else:
            missing_sources.append(source)
            available_sources.append(
                _context_source_status(
                    source,
                    available=False,
                    status="missing",
                    detail=missing_detail,
                )
            )

    _status_for(cockpit_row, "strategic_cockpit", "云端还没有正式战略 cockpit。", "已找到战略 cockpit 快照。")
    _status_for(workspace_row, "workspace_snapshot", "云端还没有客户工作台快照。", "已找到客户工作台快照。")
    _status_for(dna_row, "client_dna", "云端还没有客户 DNA 摘要。", "已找到客户 DNA 摘要。")
    if event_line_rows:
        available_sources.append(
            _context_source_status(
                "event_line_snapshot",
                available=True,
                status="partial",
                detail="当前可退回事件线摘要作为轻量战略线索。",
                updated_at=_coerce_text(event_line_rows[0]["updated_at"]) or None,
            )
        )
    else:
        missing_sources.append("event_line_snapshot")
        available_sources.append(
            _context_source_status(
                "event_line_snapshot",
                available=False,
                status="missing",
                detail="连事件线级别的线索都还没有。",
            )
        )

    health_items = [
        MobileCockpitSummaryItemRecord(
            summary=_coerce_text(item.get("summary") or item.get("label") or item.get("value")),
            updatedAt=_coerce_text(item.get("updatedAt")) or None,
        )
        for item in cast(list[dict[str, object]], cockpit_payload.get("health") or [])
        if _coerce_text(item.get("summary") or item.get("label") or item.get("value"))
    ]
    two_week_changes = [
        MobileCockpitSummaryItemRecord(
            summary=_coerce_text(item.get("summary") or item.get("title") or item.get("label")),
            updatedAt=_coerce_text(item.get("updatedAt")) or None,
        )
        for item in cast(list[dict[str, object]], cockpit_payload.get("twoWeekChanges") or [])
        if _coerce_text(item.get("summary") or item.get("title") or item.get("label"))
    ]
    pending_decisions = [
        MobileCockpitSummaryItemRecord(
            summary=_coerce_text(item.get("summary") or item.get("title") or item.get("label")),
            updatedAt=_coerce_text(item.get("updatedAt")) or None,
        )
        for item in cast(list[dict[str, object]], cockpit_payload.get("pendingDecisions") or [])
        if _coerce_text(item.get("summary") or item.get("title") or item.get("label"))
    ]
    pending_materials = [
        MobileCockpitSummaryItemRecord(
            summary=_coerce_text(item.get("summary") or item.get("title") or item.get("label")),
            updatedAt=_coerce_text(item.get("updatedAt")) or None,
        )
        for item in cast(list[dict[str, object]], cockpit_payload.get("pendingMaterials") or [])
        if _coerce_text(item.get("summary") or item.get("title") or item.get("label"))
    ]

    if not health_items and event_line_rows:
        health_items = [
            MobileCockpitSummaryItemRecord(
                summary=_coerce_text(row["summary"]) or f"事件线「{_coerce_text(row['name'], '事件线')}」当前没有更完整的战略摘要。",
                updatedAt=_coerce_text(row["updated_at"]) or None,
            )
            for row in event_line_rows[:2]
        ]
    if not two_week_changes and event_line_rows:
        two_week_changes = [
            MobileCockpitSummaryItemRecord(
                summary=f"最近更新的事件线：{_coerce_text(row['name'], '事件线')}，下一步 { _coerce_text(row['next_step']) or '仍需补充' }。",
                updatedAt=_coerce_text(row["updated_at"]) or None,
            )
            for row in event_line_rows[:2]
        ]
    if not pending_decisions and event_line_rows:
        pending_decisions = [
            MobileCockpitSummaryItemRecord(
                summary=_coerce_text(row["current_blocker"]) or f"事件线「{_coerce_text(row['name'], '事件线')}」还缺更正式的经营判断。",
                updatedAt=_coerce_text(row["updated_at"]) or None,
            )
            for row in event_line_rows[:3]
        ]
    if not pending_materials:
        pending_materials = [
            MobileCockpitSummaryItemRecord(summary="当前云端还没有正式战略材料包，建议先从桌面端发布 workspace / DNA / 会议摘要。")
        ]

    headline_summary = _coerce_text(
        cast(dict[str, object], cockpit_payload.get("headline") or {}).get("summary")
        if isinstance(cockpit_payload.get("headline"), dict)
        else cockpit_payload.get("headline")
    )
    if not headline_summary:
        if cockpit_row:
            headline_summary = "已找到战略 cockpit 快照，但当前快照没有可直接展示的 headline。"
        elif event_line_rows:
            headline_summary = "当前云端没有正式战略 cockpit，以下是根据事件线与任务生成的轻量战略视图。"
        else:
            headline_summary = "当前云端没有战略 cockpit，也没有足够的事件线数据。"

    status: Literal["rich", "partial", "missing"]
    if cockpit_row and not missing_sources:
        status = "rich"
    elif cockpit_row or event_line_rows:
        status = "partial"
    else:
        status = "missing"

    return MobileStrategicCockpitCompatResponse(
        clientId=client_id,
        clientName=client_name,
        status=status,
        updatedAt=_mirror_updated_at(cockpit_row) or _coerce_text(client_row["updated_at"]) or None,
        headline=MobileCockpitHeadlineRecord(summary=headline_summary),
        health=health_items[:4],
        twoWeekChanges=two_week_changes[:4],
        pendingDecisions=pending_decisions[:4],
        pendingMaterials=pending_materials[:4],
        missingSources=missing_sources,
        sourceAvailability=available_sources,
    )


def _upsert_cloud_mirror_item(
    state: AppState,
    *,
    organization_id: str,
    client_id: str,
    source_type: str,
    source_id: str,
    snapshot_version: int,
    snapshot_hash: str,
    updated_at: str,
    published_at: str,
    payload: dict[str, object],
    evidence_refs: list[str],
) -> None:
    table_name = MIRROR_TABLE_BY_SOURCE_TYPE.get(source_type)
    if not table_name:
        raise HTTPException(status_code=400, detail=f"Unsupported sourceType: {source_type}")
    state.db.execute(
        f"""
        INSERT INTO {table_name}(
            id, organization_id, client_id, source_type, source_id, snapshot_version, snapshot_hash,
            payload_json, evidence_refs_json, updated_at, published_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(organization_id, client_id, source_id) DO UPDATE SET
            source_type = excluded.source_type,
            snapshot_version = excluded.snapshot_version,
            snapshot_hash = excluded.snapshot_hash,
            payload_json = excluded.payload_json,
            evidence_refs_json = excluded.evidence_refs_json,
            updated_at = excluded.updated_at,
            published_at = excluded.published_at
        """,
        (
            new_id("mirror"),
            organization_id,
            client_id,
            source_type,
            source_id,
            snapshot_version,
            snapshot_hash,
            to_json(payload),
            to_json(evidence_refs),
            updated_at,
            published_at,
        ),
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
    # 普通协作任务只保留“收件箱确认”链路，不再把协作确认误挂成复核流程。
    needs_review = False
    approval_state = "none"
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


def _assert_task_edit_permission(
    state: AppState,
    actor: SessionUser,
    task_row,
    content_changed: bool,
    due_date_changed: bool,
    owner_changed: bool,
    status_changed: bool = False,
) -> None:
    if actor.primaryRole == "admin":
        return
    organization_id = str(task_row["organization_id"])
    owner_id = str(task_row["owner_id"]) if task_row["owner_id"] else None
    creator_id = str(task_row["creator_id"])
    collaborator_ids = set(_task_collaborator_ids(state, str(task_row["id"])))
    editable_actor_ids = {creator_id, *collaborator_ids}
    if owner_id:
        editable_actor_ids.add(owner_id)
    task_link_row = _task_org_link_row(state, str(task_row["id"]))
    rule_row = None
    if task_link_row and task_link_row["control_rule_id"]:
        rule_row = state.db.fetchone("SELECT * FROM org_task_control_rules WHERE id = ?", (str(task_link_row["control_rule_id"]),))
    if not rule_row:
        if status_changed and actor.id not in collaborator_ids and actor.id != owner_id and not _manager_has_capability(state, organization_id, actor.id, owner_id, "content"):
            raise HTTPException(status_code=403, detail="只有负责人或协作者可以标记任务完成")
        if content_changed and actor.id not in editable_actor_ids and not _manager_has_capability(state, organization_id, actor.id, owner_id, "content"):
            raise HTTPException(status_code=403, detail="你当前没有修改该任务内容的权限")
        if due_date_changed and actor.id not in collaborator_ids and actor.id != owner_id and not _manager_has_capability(state, organization_id, actor.id, owner_id, "deadline"):
            raise HTTPException(status_code=403, detail="你当前没有修改该任务截止时间的权限")
        if owner_changed and actor.id not in editable_actor_ids and not _manager_has_capability(state, organization_id, actor.id, owner_id, "owner"):
            raise HTTPException(status_code=403, detail="你当前没有调整该任务负责人的权限")
        return
    if status_changed and actor.id not in collaborator_ids and actor.id != owner_id and not _matches_rule_actor_scope(state, actor, task_row, task_link_row, str(rule_row["content_editable_by"] or "assignee"), "content"):
        raise HTTPException(status_code=403, detail="只有负责人或协作者可以标记任务完成")
    if content_changed and actor.id not in editable_actor_ids and not _matches_rule_actor_scope(state, actor, task_row, task_link_row, str(rule_row["content_editable_by"] or "assignee"), "content"):
        raise HTTPException(status_code=403, detail="你当前没有修改该任务内容的权限")
    if due_date_changed and actor.id not in collaborator_ids and actor.id != owner_id and not _matches_rule_actor_scope(state, actor, task_row, task_link_row, str(rule_row["deadline_editable_by"] or "manager"), "deadline"):
        raise HTTPException(status_code=403, detail="你当前没有修改该任务截止时间的权限")
    if owner_changed and actor.id not in editable_actor_ids and not _matches_rule_actor_scope(state, actor, task_row, task_link_row, str(rule_row["owner_editable_by"] or "manager"), "owner"):
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


def _auto_approve_legacy_pending_account(state: AppState, row):
    if not row or str(row["account_status"]) != "pending":
        return row
    timestamp = now_iso()
    state.db.execute(
        """
        UPDATE employee_accounts
           SET account_status = 'approved',
               approved_at = COALESCE(approved_at, created_at, ?),
               rejected_reason = NULL,
               disabled_at = NULL,
               updated_at = ?
         WHERE id = ?
        """,
        (timestamp, timestamp, str(row["id"])),
    )
    _log_audit(
        state,
        "account_status_auto_approved",
        actor_user_id=str(row["id"]),
        target_user_id=str(row["id"]),
        detail={"reason": "legacy_pending_account_removed"},
    )
    refreshed = state.db.fetchone("SELECT * FROM employee_accounts WHERE id = ?", (str(row["id"]),))
    return refreshed or row


def _require_auth(app: FastAPI, authorization: str | None = Header(default=None)) -> SessionUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_access_token(_state(app).secret_key, token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    state = _state(app)
    user_row = state.db.fetchone("SELECT * FROM employee_accounts WHERE id = ?", (payload["sub"],))
    if not user_row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    user_row = _auto_approve_legacy_pending_account(state, user_row)
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


def _normalize_feishu_custom_callback_url(value: str | None) -> str:
    return (value or "").strip().rstrip("/")


def _is_public_https_feishu_url(url: str | None) -> bool:
    from urllib.parse import urlparse

    normalized = (url or "").strip()
    if not normalized:
        return False
    parsed = urlparse(normalized)
    hostname = parsed.hostname or ""
    return parsed.scheme == "https" and _is_public_hostname(hostname)


def _build_org_feishu_callback_url(request: Request, callback_mode: str, custom_callback_url: str) -> tuple[str, str | None]:
    normalized_custom = _normalize_feishu_custom_callback_url(custom_callback_url)
    if callback_mode == "custom":
        if _is_public_https_feishu_url(normalized_custom):
            return normalized_custom, None
        return "", "当前自定义回调地址不是可公网访问的 HTTPS 地址，成员暂时还不能授权飞书身份。"

    public_base_url = _resolve_public_base_url(request)
    if public_base_url and public_base_url.startswith("https://"):
        return f"{public_base_url}/api/v1/integrations/feishu/member-authorization/callback", None
    return "", "当前组织飞书应用已验证，但云端还没有可公网访问的 HTTPS 授权回调地址，成员暂时还不能授权飞书身份。"


def _feishu_parse_response_json(response) -> dict:
    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="飞书返回了无法解析的响应。") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="飞书返回了无效的响应结构。")
    return payload


def _raise_for_feishu_api_error(payload: dict, fallback_message: str) -> None:
    code = payload.get("code", 0)
    if code == 0:
        return
    message = str(payload.get("msg") or payload.get("message") or fallback_message)
    raise HTTPException(status_code=400, detail=message)


def _feishu_fetch_app_access_token(*, app_id: str, app_secret: str) -> tuple[str, dict]:
    import httpx

    with httpx.Client(timeout=httpx.Timeout(12.0, connect=4.0)) as client:
        response = client.post(
            "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
        )
    payload = _feishu_parse_response_json(response)
    _raise_for_feishu_api_error(payload, "飞书应用令牌获取失败。")
    token = str(payload.get("app_access_token") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="飞书没有返回 app access token。")
    return token, payload


def _feishu_exchange_authorization_code(*, app_access_token: str, app_id: str, app_secret: str, code: str) -> dict:
    import httpx

    with httpx.Client(timeout=httpx.Timeout(12.0, connect=4.0)) as client:
        response = client.post(
            "https://open.feishu.cn/open-apis/authen/v1/access_token",
            headers={"Authorization": f"Bearer {app_access_token}"},
            json={
                "grant_type": "authorization_code",
                "code": code,
                "app_id": app_id,
                "app_secret": app_secret,
            },
        )
    payload = _feishu_parse_response_json(response)
    _raise_for_feishu_api_error(payload, "飞书授权码换取用户令牌失败。")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="飞书用户令牌响应缺少 data。")
    access_token = str(data.get("access_token") or "").strip()
    if not access_token:
        raise HTTPException(status_code=400, detail="飞书没有返回用户 access token。")
    return data


def _feishu_fetch_user_info(*, user_access_token: str) -> dict:
    import httpx

    with httpx.Client(timeout=httpx.Timeout(12.0, connect=4.0)) as client:
        response = client.get(
            "https://open.feishu.cn/open-apis/authen/v1/user_info",
            headers={"Authorization": f"Bearer {user_access_token}"},
        )
    payload = _feishu_parse_response_json(response)
    _raise_for_feishu_api_error(payload, "飞书用户信息获取失败。")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="飞书用户信息响应缺少 data。")
    return data


def _build_feishu_authorize_url(*, app_id: str, redirect_uri: str, state_token: str) -> str:
    from urllib.parse import urlencode

    query = urlencode({"app_id": app_id, "redirect_uri": redirect_uri, "state": state_token})
    return f"https://open.feishu.cn/open-apis/authen/v1/index?{query}"


def _org_feishu_encrypt(state: AppState, plain_text: str, organization_id: str) -> tuple[str, str]:
    import base64
    from hashlib import sha256
    from os import urandom
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = sha256(f"{state.secret_key}:{organization_id}:feishu_config".encode()).digest()
    nonce = urandom(12)
    cipher = AESGCM(key)
    cipher_text = cipher.encrypt(nonce, plain_text.encode("utf-8"), None)
    return base64.b64encode(cipher_text).decode(), base64.b64encode(nonce).decode()


def _org_feishu_decrypt(state: AppState, encrypted_b64: str, nonce_b64: str, organization_id: str) -> str:
    import base64
    from hashlib import sha256
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if not encrypted_b64 or not nonce_b64:
        return ""
    key = sha256(f"{state.secret_key}:{organization_id}:feishu_config".encode()).digest()
    cipher = AESGCM(key)
    cipher_text = base64.b64decode(encrypted_b64)
    nonce = base64.b64decode(nonce_b64)
    return cipher.decrypt(nonce, cipher_text, None).decode("utf-8")


def _org_membership_summary(state: AppState, current_user: SessionUser) -> OrgMembershipSummaryRecord:
    if not current_user.organizationId:
        return OrgMembershipSummaryRecord(hasOrganization=False)
    row = state.db.fetchone("SELECT id, name FROM organizations WHERE id = ?", (current_user.organizationId,))
    if not row:
        return OrgMembershipSummaryRecord(hasOrganization=False)
    return OrgMembershipSummaryRecord(
        hasOrganization=True,
        organizationId=str(row["id"]),
        organizationName=str(row["name"]),
    )


def _org_feishu_audit_records(state: AppState, organization_id: str, limit: int = 6) -> list[OrgFeishuIntegrationAuditRecord]:
    rows = state.db.fetchall(
        """
        SELECT audit.*, actor.full_name AS actor_name
        FROM org_feishu_integration_audits AS audit
        LEFT JOIN employee_accounts AS actor ON actor.id = audit.actor_user_id
        WHERE audit.organization_id = ?
        ORDER BY audit.created_at DESC
        LIMIT ?
        """,
        (organization_id, limit),
    )
    return [
        OrgFeishuIntegrationAuditRecord(
            id=str(row["id"]),
            organizationId=str(row["organization_id"]),
            actorUserId=str(row["actor_user_id"]) if row["actor_user_id"] else None,
            actorName=str(row["actor_name"]) if row["actor_name"] else None,
            appId=str(row["app_id"] or ""),
            validationStatus=str(row["validation_status"] or "failed"),
            validationMessage=str(row["validation_message"] or ""),
            createdAt=str(row["created_at"]),
        )
        for row in rows
    ]


def _record_org_feishu_audit(
    state: AppState,
    current_user: SessionUser,
    *,
    app_id: str,
    validation_status: Literal["success", "failed"],
    validation_message: str,
) -> None:
    state.db.execute(
        """
        INSERT INTO org_feishu_integration_audits(
            id, organization_id, actor_user_id, app_id, callback_mode, custom_callback_url,
            effective_callback_url, validation_status, validation_message, created_at
        ) VALUES(?, ?, ?, ?, '', '', '', ?, ?, ?)
        """,
        (
            new_id("feishu_audit"),
            current_user.organizationId,
            current_user.id,
            app_id,
            validation_status,
            validation_message,
            now_iso(),
        ),
    )


def _org_feishu_integration_record(state: AppState, current_user: SessionUser, request: Request | None = None) -> OrgFeishuIntegrationRecord:
    membership = _org_membership_summary(state, current_user)
    if not membership.hasOrganization or not membership.organizationId:
        return OrgFeishuIntegrationRecord(
            organizationId=None,
            organizationName=None,
            updatedAt=now_iso(),
            lastValidationStatus="idle",
            lastValidationMessage="你还没有加入任何组织。飞书提醒依赖组织信息，请先加入组织或创建组织。",
        )
    row = state.db.fetchone(
        "SELECT * FROM org_feishu_integrations WHERE organization_id = ?",
        (membership.organizationId,),
    )
    if not row:
        return OrgFeishuIntegrationRecord(
            organizationId=membership.organizationId,
            organizationName=membership.organizationName,
            updatedAt=now_iso(),
            lastValidationStatus="idle",
            lastValidationMessage="当前组织尚未接通飞书，任一组织成员都可先完成这一步。",
            recentAudits=_org_feishu_audit_records(state, membership.organizationId),
        )
    configured_by = None
    if row["configured_by"]:
        actor_row = state.db.fetchone("SELECT full_name FROM employee_accounts WHERE id = ?", (str(row["configured_by"]),))
        configured_by = str(actor_row["full_name"]) if actor_row and actor_row["full_name"] else str(row["configured_by"])
    last_validation_message = str(row["last_validation_message"] or "") or None
    if bool(row["enabled"]) and str(row["last_validation_status"] or "idle") == "success":
        last_validation_message = "飞书应用验证成功。成员填写飞书手机号后，任务提醒即可自动按手机号匹配发送。"
    return OrgFeishuIntegrationRecord(
        organizationId=membership.organizationId,
        organizationName=membership.organizationName,
        appId=str(row["app_id"] or ""),
        enabled=bool(row["enabled"]),
        hasAppSecret=bool(row["app_secret_encrypted"]),
        configuredBy=configured_by,
        configuredAt=str(row["configured_at"]) if row["configured_at"] else None,
        updatedAt=str(row["updated_at"]),
        lastValidationStatus=str(row["last_validation_status"] or "idle"),
        lastValidationMessage=last_validation_message,
        recentAudits=_org_feishu_audit_records(state, membership.organizationId),
    )


def _normalize_feishu_mobile(raw_value: str | None) -> str:
    digits = re.sub(r"\D+", "", str(raw_value or "").strip())
    if digits.startswith("86") and len(digits) > 11:
        digits = digits[2:]
    return digits


def _feishu_delivery_status_label(status: str) -> str:
    return {
        "missing_org": "请先加入或创建组织",
        "integration_pending": "请先完成组织飞书接入",
        "missing_mobile": "请填写飞书手机号",
        "matched": "已匹配飞书提醒目标",
        "not_found": "暂未匹配到飞书接收身份",
        "failed": "飞书提醒目标校验失败",
    }.get(status, "飞书提醒状态未知")


def _feishu_delivery_profile_record(state: AppState, current_user: SessionUser) -> FeishuDeliveryProfileRecord:
    membership = _org_membership_summary(state, current_user)
    row = state.db.fetchone(
        "SELECT feishu_mobile FROM employee_accounts WHERE id = ?",
        (current_user.id,),
    )
    raw_mobile = str(row["feishu_mobile"] or "") if row else ""
    normalized_mobile = _normalize_feishu_mobile(raw_mobile)

    if not membership.hasOrganization:
        return FeishuDeliveryProfileRecord(
            userId=current_user.id,
            organizationId=None,
            organizationName=None,
            mobile=raw_mobile,
            normalizedMobile=normalized_mobile or None,
            deliveryStatus="missing_org",
            deliveryStatusLabel=_feishu_delivery_status_label("missing_org"),
            readyForNotifications=False,
            blockedReason="飞书提醒依赖组织信息，请先加入组织或创建组织。",
        )

    integration = _org_feishu_integration_record(state, current_user)
    if not integration.enabled:
        return FeishuDeliveryProfileRecord(
            userId=current_user.id,
            organizationId=membership.organizationId,
            organizationName=membership.organizationName,
            mobile=raw_mobile,
            normalizedMobile=normalized_mobile or None,
            deliveryStatus="integration_pending",
            deliveryStatusLabel=_feishu_delivery_status_label("integration_pending"),
            readyForNotifications=False,
            blockedReason="当前组织尚未接通飞书，请先完成组织飞书接入。",
        )

    target_row = state.db.fetchone(
        "SELECT * FROM org_feishu_delivery_targets WHERE organization_id = ? AND user_id = ?",
        (membership.organizationId, current_user.id),
    )
    if not normalized_mobile:
        status = "missing_mobile"
        return FeishuDeliveryProfileRecord(
            userId=current_user.id,
            organizationId=membership.organizationId,
            organizationName=membership.organizationName,
            mobile=raw_mobile,
            normalizedMobile=None,
            deliveryStatus=status,
            deliveryStatusLabel=_feishu_delivery_status_label(status),
            readyForNotifications=False,
            lastVerifiedAt=str(target_row["last_verified_at"]) if target_row and target_row["last_verified_at"] else None,
            lastError=str(target_row["last_error"]) if target_row and target_row["last_error"] else None,
            blockedReason="请填写你登录飞书时使用的手机号，软件会按该手机号匹配你的飞书身份并发送任务提醒。",
        )

    status = str(target_row["match_status"] or "not_found") if target_row else "missing_mobile"
    if status == "missing_mobile":
        status = "not_found"
    last_error = str(target_row["last_error"]) if target_row and target_row["last_error"] else None
    return FeishuDeliveryProfileRecord(
        userId=current_user.id,
        organizationId=membership.organizationId,
        organizationName=membership.organizationName,
        mobile=raw_mobile,
        normalizedMobile=normalized_mobile or None,
        deliveryStatus=status,
        deliveryStatusLabel=_feishu_delivery_status_label(status),
        readyForNotifications=status == "matched",
        receiveId=str(target_row["receive_id"]) if target_row and target_row["receive_id"] else None,
        lastVerifiedAt=str(target_row["last_verified_at"]) if target_row and target_row["last_verified_at"] else None,
        lastError=last_error,
        blockedReason=None if status == "matched" else (
            last_error
            or ("请填写你登录飞书时使用的手机号，软件会按该手机号匹配你的飞书身份并发送任务提醒。" if status == "missing_mobile" else None)
        ),
    )


def _feishu_fetch_tenant_access_token(*, app_id: str, app_secret: str) -> tuple[str, dict]:
    import httpx

    with httpx.Client(timeout=httpx.Timeout(12.0, connect=4.0)) as client:
        response = client.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
        )
    payload = _feishu_parse_response_json(response)
    _raise_for_feishu_api_error(payload, "飞书租户令牌获取失败。")
    token = str(payload.get("tenant_access_token") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="飞书没有返回 tenant access token。")
    return token, payload


def _feishu_lookup_open_id_by_mobile(*, tenant_access_token: str, mobile: str) -> tuple[str | None, str | None]:
    import httpx

    normalized_mobile = _normalize_feishu_mobile(mobile)
    if not normalized_mobile:
        return None, "请先填写飞书手机号。"

    with httpx.Client(timeout=httpx.Timeout(12.0, connect=4.0)) as client:
        response = client.post(
            "https://open.feishu.cn/open-apis/contact/v3/users/batch_get_id",
            params={"user_id_type": "open_id"},
            headers={"Authorization": f"Bearer {tenant_access_token}"},
            json={"mobiles": [normalized_mobile]},
        )
    payload = _feishu_parse_response_json(response)
    _raise_for_feishu_api_error(payload, "按手机号查询飞书成员失败。")
    data = payload.get("data")
    if not isinstance(data, dict):
        return None, "飞书成员查询结果缺少 data。"
    user_list = data.get("user_list")
    if not isinstance(user_list, list) or not user_list:
        return None, "暂未在飞书通讯录中找到该手机号，请确认该成员已加入当前飞书组织且手机号填写正确。"
    for item in user_list:
        if not isinstance(item, dict):
            continue
        user_id = str(item.get("user_id") or "").strip()
        mobile_value = _normalize_feishu_mobile(str(item.get("mobile") or ""))
        if user_id and (not mobile_value or mobile_value == normalized_mobile):
            return user_id, None
    first = user_list[0]
    if isinstance(first, dict):
        candidate = str(first.get("user_id") or "").strip()
        if candidate:
            return candidate, None
    return None, "暂未在飞书通讯录中找到该手机号，请确认该成员已加入当前飞书组织且手机号填写正确。"


def _resolve_org_feishu_tenant_access_token(
    state: AppState,
    *,
    organization_id: str,
) -> tuple[str, str] | None:
    integration_row = state.db.fetchone(
        "SELECT * FROM org_feishu_integrations WHERE organization_id = ?",
        (organization_id,),
    )
    if not integration_row or not integration_row["enabled"] or not integration_row["app_id"] or not integration_row["app_secret_encrypted"]:
        return None

    app_id = str(integration_row["app_id"])
    app_secret = _org_feishu_decrypt(
        state,
        str(integration_row["app_secret_encrypted"]),
        str(integration_row["encryption_nonce"]),
        organization_id,
    )
    tenant_access_token, _ = _feishu_fetch_tenant_access_token(
        app_id=app_id,
        app_secret=app_secret,
    )
    return app_id, tenant_access_token


def _feishu_send_text_message(*, tenant_access_token: str, receive_id_type: Literal["open_id"], receive_id: str, text: str) -> dict:
    import httpx

    with httpx.Client(timeout=httpx.Timeout(12.0, connect=4.0)) as client:
        response = client.post(
            "https://open.feishu.cn/open-apis/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            headers={"Authorization": f"Bearer {tenant_access_token}"},
            json={
                "receive_id": receive_id,
                "msg_type": "text",
                "content": to_json({"text": text}),
            },
        )
    payload = _feishu_parse_response_json(response)
    _raise_for_feishu_api_error(payload, "飞书消息发送失败。")
    return payload


def _feishu_send_interactive_message(*, tenant_access_token: str, receive_id_type: Literal["open_id"], receive_id: str, card: dict) -> dict:
    import httpx

    with httpx.Client(timeout=httpx.Timeout(12.0, connect=4.0)) as client:
        response = client.post(
            "https://open.feishu.cn/open-apis/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            headers={"Authorization": f"Bearer {tenant_access_token}"},
            json={
                "receive_id": receive_id,
                "msg_type": "interactive",
                "content": json.dumps(card, ensure_ascii=False),
            },
        )
    payload = _feishu_parse_response_json(response)
    _raise_for_feishu_api_error(payload, "飞书卡片发送失败。")
    return payload


def _feishu_patch_interactive_message(*, tenant_access_token: str, message_id: str, card: dict) -> dict:
    import httpx

    with httpx.Client(timeout=httpx.Timeout(12.0, connect=4.0)) as client:
        response = client.patch(
            f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}",
            headers={
                "Authorization": f"Bearer {tenant_access_token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={"content": json.dumps(card, ensure_ascii=False)},
        )
    payload = _feishu_parse_response_json(response)
    _raise_for_feishu_api_error(payload, "飞书查询卡片更新失败。")
    return payload


def _feishu_message_id_from_payload(payload: dict | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if isinstance(data, dict) and data.get("message_id"):
        return str(data["message_id"])
    if payload.get("message_id"):
        return str(payload["message_id"])
    return None


def _upsert_org_feishu_delivery_target(
    state: AppState,
    *,
    organization_id: str,
    user_id: str,
    mobile: str,
    receive_id: str | None,
    match_status: Literal["matched", "not_found", "failed", "manual"],
    last_error: str | None,
) -> None:
    timestamp = now_iso()
    state.db.execute(
        """
        INSERT INTO org_feishu_delivery_targets(
            organization_id, user_id, mobile, receive_id_type, receive_id, match_status, last_verified_at, last_error, updated_at
        ) VALUES(?, ?, ?, 'open_id', ?, ?, ?, ?, ?)
        ON CONFLICT(organization_id, user_id) DO UPDATE SET
            mobile = excluded.mobile,
            receive_id_type = excluded.receive_id_type,
            receive_id = excluded.receive_id,
            match_status = excluded.match_status,
            last_verified_at = excluded.last_verified_at,
            last_error = excluded.last_error,
            updated_at = excluded.updated_at
        """,
        (
            organization_id,
            user_id,
            mobile,
            receive_id,
            match_status,
            timestamp,
            last_error,
            timestamp,
        ),
    )


def _resolve_feishu_delivery_target(
    state: AppState,
    *,
    organization_id: str,
    user_id: str,
    tenant_access_token: str,
) -> tuple[str | None, Literal["matched", "not_found", "failed"], str | None]:
    user_row = state.db.fetchone(
        "SELECT feishu_mobile FROM employee_accounts WHERE id = ?",
        (user_id,),
    )
    mobile = _normalize_feishu_mobile(str(user_row["feishu_mobile"] or "")) if user_row else ""
    if not mobile:
        _upsert_org_feishu_delivery_target(
            state,
            organization_id=organization_id,
            user_id=user_id,
            mobile="",
            receive_id=None,
            match_status="not_found",
            last_error="成员尚未填写飞书手机号，已跳过发送。",
        )
        return None, "not_found", "成员尚未填写飞书手机号，已跳过发送。"

    target_row = state.db.fetchone(
        "SELECT * FROM org_feishu_delivery_targets WHERE organization_id = ? AND user_id = ?",
        (organization_id, user_id),
    )
    if (
        target_row
        and str(target_row["mobile"] or "") == mobile
        and str(target_row["match_status"] or "") == "matched"
        and str(target_row["receive_id"] or "").strip()
    ):
        return str(target_row["receive_id"]).strip(), "matched", None

    try:
        receive_id, lookup_error = _feishu_lookup_open_id_by_mobile(
            tenant_access_token=tenant_access_token,
            mobile=mobile,
        )
    except Exception as exc:
        error_message = str(exc.detail) if isinstance(exc, HTTPException) else "按手机号查询飞书成员失败。"
        _upsert_org_feishu_delivery_target(
            state,
            organization_id=organization_id,
            user_id=user_id,
            mobile=mobile,
            receive_id=None,
            match_status="failed",
            last_error=error_message,
        )
        return None, "failed", error_message

    if not receive_id:
        error_message = lookup_error or "暂未在飞书通讯录中找到该手机号，请确认该成员已加入当前飞书组织且手机号填写正确。"
        _upsert_org_feishu_delivery_target(
            state,
            organization_id=organization_id,
            user_id=user_id,
            mobile=mobile,
            receive_id=None,
            match_status="not_found",
            last_error=error_message,
        )
        return None, "not_found", error_message

    _upsert_org_feishu_delivery_target(
        state,
        organization_id=organization_id,
        user_id=user_id,
        mobile=mobile,
        receive_id=receive_id,
        match_status="matched",
        last_error=None,
    )
    return receive_id, "matched", None


@dataclass
class FeishuSenderProfile:
    open_id: str
    feishu_user_id: str | None = None
    union_id: str | None = None
    name: str | None = None
    email: str | None = None
    enterprise_email: str | None = None
    mobile: str | None = None
    tenant_key: str | None = None


@dataclass
class FeishuQueryIntent:
    kind: str
    keyword: str | None = None
    status_filter: Literal["open", "doing", "done", "overdue", "pending", "any"] | None = None
    time_filter: Literal["today", "week", "none"] | None = None
    participant_name: str | None = None
    owner_name: str | None = None


@dataclass
class FeishuQueryModelConfig:
    api_key: str
    model: str
    provider: str = "env"


def _feishu_extract_text_content(content: str | None) -> str:
    raw = str(content or "").strip()
    if not raw:
        return ""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(payload, dict):
        text = str(payload.get("text") or "").strip()
        if text:
            return text
    return raw


def _feishu_text_for_match(value: str | None) -> str:
    return re.sub(r"\s+", "", str(value or "").strip()).lower()


def _feishu_extract_json_object(raw: str | None) -> dict[str, object] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    candidates = [text]
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    candidates.extend(fenced)
    if "{" in text and "}" in text:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return cast(dict[str, object], payload)
    return None


def _org_ai_decrypt_value(state: AppState, encrypted_b64: str, nonce_b64: str, organization_id: str) -> str:
    import base64
    from hashlib import sha256

    if not encrypted_b64 or not nonce_b64:
        return ""
    key = sha256(f"{state.secret_key}:{organization_id}:ai_config".encode()).digest()
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    cipher = AESGCM(key)
    return cipher.decrypt(base64.b64decode(nonce_b64), base64.b64decode(encrypted_b64), None).decode("utf-8")


def _load_feishu_query_model_config(state: AppState, organization_id: str) -> FeishuQueryModelConfig | None:
    from app.smart_input import DEFAULT_LLM_MODEL, _qwen_api_key

    configured = state.db.fetchone("SELECT * FROM org_ai_config WHERE org_id = ?", (organization_id,))
    default_model = os.getenv("YIYU_FEISHU_QUERY_MODEL", os.getenv("YIYU_SMART_INPUT_MODEL", DEFAULT_LLM_MODEL))
    if configured and configured["api_key_encrypted"]:
        provider = str(configured["ai_provider"] or "").strip() or "configured"
        if provider != "mock":
            try:
                api_key = _org_ai_decrypt_value(
                    state,
                    str(configured["api_key_encrypted"] or ""),
                    str(configured["encryption_nonce"] or ""),
                    organization_id,
                )
            except Exception as exc:
                logger.warning("feishu.query.load_org_ai_config_failed: %s", exc)
                api_key = ""
            if api_key:
                return FeishuQueryModelConfig(
                    api_key=api_key,
                    model=str(configured["ai_model"] or "").strip() or default_model,
                    provider=provider,
                )
    fallback_key = _qwen_api_key()
    if not fallback_key:
        return None
    return FeishuQueryModelConfig(api_key=fallback_key, model=default_model, provider="env")


def _feishu_name_matches(candidate: str | None, target: str | None) -> bool:
    left = _feishu_text_for_match(candidate)
    right = _feishu_text_for_match(target)
    if not left or not right:
        return False
    return left == right or left in right or right in left


def _task_matches_keyword(task: TaskRecord, keyword: str | None) -> bool:
    normalized = _feishu_text_for_match(keyword)
    if not normalized:
        return True
    haystacks = (
        task.title,
        task.description,
        task.ownerName,
        task.creatorName,
        task.eventLineName,
        task.clientName,
    )
    for value in haystacks:
        if normalized in _feishu_text_for_match(value):
            return True
    return False


def _task_matches_participant(task: TaskRecord, participant_name: str | None) -> bool:
    normalized = _feishu_text_for_match(participant_name)
    if not normalized:
        return True
    if _feishu_name_matches(task.ownerName, participant_name):
        return True
    return any(_feishu_name_matches(item.fullName, participant_name) for item in task.collaborators)


def _feishu_query_card_template(status: str) -> str:
    return {
        "resolved": "blue",
        "no_result": "grey",
        "denied": "orange",
        "unresolved": "orange",
        "error": "red",
    }.get(status, "blue")


def _feishu_query_card_title(query_type: str, status: str) -> str:
    if status == "error":
        return "益语智库｜查询失败"
    if status == "unresolved":
        return "益语智库｜身份待确认"
    if status == "denied":
        return "益语智库｜查询范围受限"
    mapping = {
        "tasks_today": "益语智库｜今日任务",
        "tasks_week": "益语智库｜本周任务",
        "tasks_overdue": "益语智库｜逾期任务",
        "tasks_pending": "益语智库｜待确认任务",
        "tasks_open": "益语智库｜待办任务",
        "tasks_doing": "益语智库｜进行中任务",
        "tasks_done": "益语智库｜已完成任务",
        "tasks_list": "益语智库｜任务查询",
        "task_lookup": "益语智库｜任务摘要",
        "review_status": "益语智库｜周复盘查询",
        "review_summary": "益语智库｜周复盘摘要",
        "eventline_list": "益语智库｜事件线查询",
        "eventline_lookup": "益语智库｜事件线摘要",
        "feishu_status": "益语智库｜飞书状态",
        "scope_denied": "益语智库｜查询范围受限",
        "identity": "益语智库｜身份待确认",
        "help": "益语智库｜支持问法",
    }
    return mapping.get(query_type, "益语智库｜查询结果")


def _build_feishu_query_progress_card(question: str) -> dict:
    normalized_question = str(question or "").strip()
    short_question = normalized_question[:80] + ("..." if len(normalized_question) > 80 else "")
    return {
        "config": {"update_multi": True, "wide_screen_mode": True},
        "header": {
            "template": "wathet",
            "title": {"tag": "plain_text", "content": "益语智库｜正在处理"},
        },
        "elements": [
            {"tag": "markdown", "content": "**⌨️ 正在查询益语云数据**"},
            {"tag": "markdown", "content": f"你刚才问的是：{short_question or '未提供问题内容'}"},
            {"tag": "note", "elements": [{"tag": "plain_text", "content": "请稍候，结果会直接替换这张卡片。"}]},
        ],
    }


def _build_feishu_query_result_card(*, query_type: str, status: str, reply_text: str) -> dict:
    lines = [line.strip() for line in str(reply_text or "").splitlines() if line.strip()]
    body_lines = lines[:8] if lines else ["暂无可展示结果。"]
    elements: list[dict[str, object]] = []
    if body_lines:
        elements.append({"tag": "markdown", "content": "\n".join(body_lines)})
    if len(lines) > len(body_lines):
        elements.append({"tag": "note", "elements": [{"tag": "plain_text", "content": "内容较长，已截取关键信息显示。"}]})
    return {
        "config": {"update_multi": True, "wide_screen_mode": True},
        "header": {
            "template": _feishu_query_card_template(status),
            "title": {"tag": "plain_text", "content": _feishu_query_card_title(query_type, status)},
        },
        "elements": elements or [{"tag": "plain_text", "content": "暂无可展示结果。"}],
    }


def _week_label_for_today() -> str:
    iso = datetime.now().date().isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _task_progress_label(value: str | None) -> str:
    return {
        "inbox": "待确认",
        "todo": "待处理",
        "doing": "进行中",
        "done": "已完成",
        "rejected": "已退回",
    }.get(str(value or "").strip(), str(value or "未知状态") or "未知状态")


def _task_time_brief(record: TaskRecord) -> str:
    if record.dueDate:
        return f"截止 {_task_datetime_text(record.dueDate)}"
    if record.startDate:
        return f"开始 {_task_datetime_text(record.startDate)}"
    return "未设时间"


def _task_latest_activity_brief(state: AppState, task_id: str) -> str | None:
    row = state.db.fetchone(
        """
        SELECT e.event_type, e.created_at, u.full_name
        FROM task_activity_events e
        JOIN employee_accounts u ON u.id = e.actor_id
        WHERE e.task_id = ?
        ORDER BY e.created_at DESC
        LIMIT 1
        """,
        (task_id,),
    )
    if not row:
        return None
    event_label = {
        "created": "创建",
        "updated": "更新",
        "completed": "完成",
        "reviewed": "复核",
        "returned": "退回",
        "note_added": "补充备注",
    }.get(str(row["event_type"] or "").strip(), str(row["event_type"] or "更新") or "更新")
    actor_name = str(row["full_name"] or "同事")
    return f"{actor_name} 于 {str(row['created_at'])[:16].replace('T', ' ')} {event_label}"


def _task_date_span(record: TaskRecord) -> tuple[datetime.date | None, datetime.date | None]:
    start_dt = _task_datetime_value(record.startDate) or _task_datetime_value(record.dueDate)
    due_dt = _task_datetime_value(record.dueDate) or start_dt
    return (start_dt.date() if start_dt else None, due_dt.date() if due_dt else None)


def _task_intersects_dates(record: TaskRecord, range_start: datetime.date, range_end: datetime.date) -> bool:
    start_date, end_date = _task_date_span(record)
    if start_date is None and end_date is None:
        return False
    start_value = start_date or end_date
    end_value = end_date or start_date
    assert start_value is not None and end_value is not None
    return not (end_value < range_start or start_value > range_end)


def _task_sort_key(record: TaskRecord) -> tuple[datetime, int, str]:
    due_dt = _task_datetime_value(record.dueDate) or _task_datetime_value(record.startDate) or datetime.max
    priority_order = {"high": 0, "normal": 1, "low": 2}
    return (
        due_dt,
        priority_order.get(record.priority, 3),
        str(record.updatedAt),
    )


def _match_accounts_by_field(state: AppState, organization_id: str, field_name: str, value: str | None) -> list:
    normalized = str(value or "").strip()
    if not normalized:
        return []
    if field_name == "email":
        return state.db.fetchall(
            """
            SELECT *
            FROM employee_accounts
            WHERE organization_id = ?
              AND account_status NOT IN ('rejected', 'disabled')
              AND lower(email) = lower(?)
            """,
            (organization_id, normalized),
        )
    if field_name == "feishu_mobile":
        normalized_mobile = _normalize_feishu_mobile(normalized)
        if not normalized_mobile:
            return []
        return state.db.fetchall(
            """
            SELECT *
            FROM employee_accounts
            WHERE organization_id = ?
              AND account_status NOT IN ('rejected', 'disabled')
              AND replace(feishu_mobile, ' ', '') = ?
            """,
            (organization_id, normalized_mobile),
        )
    if field_name == "full_name":
        return state.db.fetchall(
            """
            SELECT *
            FROM employee_accounts
            WHERE organization_id = ?
              AND account_status NOT IN ('rejected', 'disabled')
              AND full_name = ?
            """,
            (organization_id, normalized),
        )
    return []


def _feishu_fetch_contact_user_profile(
    *,
    tenant_access_token: str,
    open_id: str | None,
    feishu_user_id: str | None = None,
    union_id: str | None = None,
    tenant_key: str | None = None,
) -> FeishuSenderProfile | None:
    import httpx

    last_error: Exception | None = None
    for user_id_type, identifier in (
        ("open_id", str(open_id or "").strip()),
        ("user_id", str(feishu_user_id or "").strip()),
    ):
        if not identifier:
            continue
        try:
            with httpx.Client(timeout=httpx.Timeout(12.0, connect=4.0)) as client:
                response = client.get(
                    f"https://open.feishu.cn/open-apis/contact/v3/users/{identifier}",
                    params={"user_id_type": user_id_type},
                    headers={"Authorization": f"Bearer {tenant_access_token}"},
                )
            payload = _feishu_parse_response_json(response)
            _raise_for_feishu_api_error(payload, "飞书成员信息获取失败。")
            data = payload.get("data") or {}
            user = data.get("user") or {}
            if not isinstance(user, dict):
                continue
            resolved_open_id = str(user.get("open_id") or open_id or "").strip()
            if not resolved_open_id:
                continue
            return FeishuSenderProfile(
                open_id=resolved_open_id,
                feishu_user_id=str(user.get("user_id") or feishu_user_id or "").strip() or None,
                union_id=str(user.get("union_id") or union_id or "").strip() or None,
                name=str(user.get("name") or "").strip() or None,
                email=str(user.get("email") or "").strip() or None,
                enterprise_email=str(user.get("enterprise_email") or "").strip() or None,
                mobile=_normalize_feishu_mobile(str(user.get("mobile") or "")) or None,
                tenant_key=tenant_key,
            )
        except Exception as exc:
            last_error = exc
            continue
    if last_error:
        logger.warning("feishu.query.fetch_user_profile_failed: %s", last_error)
    return None


def _record_feishu_query_log(
    state: AppState,
    *,
    organization_id: str,
    message_id: str,
    sender_open_id: str,
    sender_feishu_user_id: str | None,
    chat_id: str,
    query_type: str,
    query_text: str,
    resolved_user_id: str | None,
    status: str,
    reply_excerpt: str,
) -> None:
    timestamp = now_iso()
    existing = state.db.fetchone(
        "SELECT id FROM org_feishu_query_logs WHERE message_id = ?",
        (message_id,),
    )
    if existing:
        state.db.execute(
            """
            UPDATE org_feishu_query_logs
            SET organization_id = ?,
                sender_open_id = ?,
                sender_feishu_user_id = ?,
                chat_id = ?,
                query_type = ?,
                query_text = ?,
                resolved_user_id = ?,
                status = ?,
                reply_excerpt = ?,
                created_at = ?
            WHERE message_id = ?
            """,
            (
                organization_id,
                sender_open_id,
                sender_feishu_user_id,
                chat_id,
                query_type,
                query_text,
                resolved_user_id,
                status,
                _truncate_plain_text(reply_excerpt, 600),
                timestamp,
                message_id,
            ),
        )
        return
    state.db.execute(
        """
        INSERT INTO org_feishu_query_logs(
            id, organization_id, message_id, sender_open_id, sender_feishu_user_id, chat_id,
            query_type, query_text, resolved_user_id, status, reply_excerpt, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id("fs_query"),
            organization_id,
            message_id,
            sender_open_id,
            sender_feishu_user_id,
            chat_id,
            query_type,
            query_text,
            resolved_user_id,
            status,
            _truncate_plain_text(reply_excerpt, 600),
            timestamp,
        ),
    )


class FeishuIdentityResolver:
    def __init__(self, state: AppState):
        self.state = state

    def resolve_user(
        self,
        *,
        organization_id: str,
        sender_open_id: str,
        sender_feishu_user_id: str | None,
        sender_union_id: str | None,
        tenant_access_token: str,
        tenant_key: str | None,
    ) -> tuple[SessionUser | None, str | None]:
        mapped = self.state.db.fetchone(
            """
            SELECT acc.*
            FROM org_feishu_delivery_targets target
            JOIN employee_accounts acc ON acc.id = target.user_id
            WHERE target.organization_id = ?
              AND target.receive_id = ?
              AND target.match_status = 'matched'
              AND acc.account_status NOT IN ('rejected', 'disabled')
            LIMIT 1
            """,
            (organization_id, sender_open_id),
        )
        if mapped:
            return _row_user(mapped), None

        profile = _feishu_fetch_contact_user_profile(
            tenant_access_token=tenant_access_token,
            open_id=sender_open_id,
            feishu_user_id=sender_feishu_user_id,
            union_id=sender_union_id,
            tenant_key=tenant_key,
        )
        if not profile:
            return None, "暂时还没识别到你在益语软件里的身份。请先在软件“系统设置”里填写飞书手机号，或确认当前组织已给机器人开通成员信息读取权限。"

        matched_row = self._match_employee_account(organization_id=organization_id, profile=profile)
        if not matched_row:
            return None, "暂时还没识别到你在益语软件里的账号。请先在软件“系统设置”里补充飞书手机号，或确认你的飞书邮箱/姓名与益语账号一致。"

        mobile_value = profile.mobile or ""
        _upsert_org_feishu_delivery_target(
            self.state,
            organization_id=organization_id,
            user_id=str(matched_row["id"]),
            mobile=mobile_value,
            receive_id=profile.open_id,
            match_status="matched",
            last_error=None,
        )
        return _row_user(matched_row), None

    def _match_employee_account(self, *, organization_id: str, profile: FeishuSenderProfile):
        candidate_sets = [
            _match_accounts_by_field(self.state, organization_id, "email", profile.email),
            _match_accounts_by_field(self.state, organization_id, "email", profile.enterprise_email),
            _match_accounts_by_field(self.state, organization_id, "feishu_mobile", profile.mobile),
            _match_accounts_by_field(self.state, organization_id, "full_name", profile.name),
        ]
        for rows in candidate_sets:
            if len(rows) == 1:
                return rows[0]
        return None


class FeishuQueryService:
    def __init__(self, state: AppState):
        self.state = state

    def build_reply(self, *, current_user: SessionUser, text: str) -> tuple[str, str, str]:
        intent = self._parse_intent(current_user, text)
        if intent.kind == "denied_scope":
            return "denied", "scope_denied", "当前机器人 V1 仅支持查询你本人的任务、周复盘、事件线和飞书接通状态。"
        if intent.kind == "help":
            return "resolved", "help", FEISHU_QUERY_HELP_TEXT
        if self._is_task_list_intent(intent):
            normalized_intent = self._normalized_task_list_intent(intent)
            if normalized_intent.status_filter == "pending":
                reply = self._reply_pending_tasks(current_user, normalized_intent)
            else:
                reply = self._reply_task_list(self._task_list_title(normalized_intent), self._filter_tasks_by_intent(current_user, normalized_intent))
            return self._status_for_lookup_reply(intent.kind, reply), intent.kind, reply
        if intent.kind == "review_status":
            return "resolved", intent.kind, self._reply_review_status(current_user)
        if intent.kind == "review_summary":
            return "resolved", intent.kind, self._reply_review_summary(current_user)
        if intent.kind == "eventline_list":
            reply = self._reply_event_line_list(current_user)
            return self._status_for_lookup_reply(intent.kind, reply), intent.kind, reply
        if intent.kind == "eventline_lookup":
            reply = self._reply_event_line_detail(current_user, intent.keyword or "")
            return self._status_for_lookup_reply(intent.kind, reply), intent.kind, reply
        if intent.kind == "task_lookup":
            reply = self._reply_task_detail(current_user, intent.keyword or "", participant_name=intent.participant_name)
            return self._status_for_lookup_reply(intent.kind, reply), intent.kind, reply
        if intent.kind == "feishu_status":
            return "resolved", intent.kind, self._reply_feishu_status(current_user)
        return "resolved", "help", FEISHU_QUERY_HELP_TEXT

    @staticmethod
    def _status_for_lookup_reply(kind: str, reply_text: str) -> str:
        if kind in {"task_lookup", "eventline_lookup", "tasks_list", "tasks_today", "tasks_week", "tasks_overdue", "tasks_pending", "tasks_open", "tasks_doing", "tasks_done", "eventline_list"}:
            if any(marker in reply_text for marker in ("当前没有", "没有找到", "没有查到")):
                return "no_result"
        return "resolved"

    @staticmethod
    def _is_task_list_intent(intent: FeishuQueryIntent) -> bool:
        return intent.kind in {"tasks_list", "tasks_today", "tasks_week", "tasks_overdue", "tasks_pending", "tasks_open", "tasks_doing", "tasks_done"}

    def _parse_intent(self, current_user: SessionUser, text: str) -> FeishuQueryIntent:
        model_intent = self._parse_intent_with_model(current_user, text)
        if model_intent and model_intent.kind != "help":
            return model_intent
        rules_intent = self._parse_intent_with_rules(text)
        if model_intent and model_intent.kind == "help" and rules_intent.kind == "help":
            return model_intent
        return rules_intent

    def _parse_intent_with_rules(self, text: str) -> FeishuQueryIntent:
        normalized = _feishu_text_for_match(text)
        if not normalized:
            return FeishuQueryIntent(kind="help")
        if any(keyword in normalized for keyword in ("部门", "组织", "团队", "同事", "别人")):
            return FeishuQueryIntent(kind="denied_scope")
        if "有哪些任务" in normalized and "我" not in normalized and not normalized.startswith("任务"):
            return FeishuQueryIntent(kind="denied_scope")
        if any(keyword in normalized for keyword in ("帮助", "怎么查", "支持哪些", "能查什么", "菜单")):
            return FeishuQueryIntent(kind="help")
        if "飞书" in normalized and any(keyword in normalized for keyword in ("匹配", "接通", "状态", "提醒")):
            return FeishuQueryIntent(kind="feishu_status")
        if "待确认" in normalized and "任务" in normalized:
            return FeishuQueryIntent(kind="tasks_pending")
        if any(keyword in normalized for keyword in ("逾期", "过期")) and "任务" in normalized:
            return FeishuQueryIntent(kind="tasks_overdue")
        if ("今天" in normalized or "今日" in normalized) and "任务" in normalized:
            return FeishuQueryIntent(kind="tasks_today")
        if ("本周" in normalized or "这周" in normalized) and "任务" in normalized:
            return FeishuQueryIntent(kind="tasks_week")
        if self._is_task_list_query(normalized):
            if any(keyword in normalized for keyword in ("进行中", "正在做", "处理中")):
                return FeishuQueryIntent(kind="tasks_doing")
            if any(keyword in normalized for keyword in ("已完成", "完成了", "做完", "做完了", "已做完")):
                return FeishuQueryIntent(kind="tasks_done")
            return FeishuQueryIntent(kind="tasks_open")
        if "复盘" in normalized and any(keyword in normalized for keyword in ("提交", "了吗", "状态")):
            return FeishuQueryIntent(kind="review_status")
        if "复盘" in normalized:
            return FeishuQueryIntent(kind="review_summary")
        if "事件线" in normalized and any(keyword in normalized for keyword in ("有哪些", "哪些", "参与")):
            return FeishuQueryIntent(kind="eventline_list")
        if "事件线" in normalized:
            keyword = self._extract_lookup_keyword(
                text,
                base_words=("事件线", "状态", "进展", "情况", "任务", "详情", "我的", "查一下", "看看", "是什么"),
            )
            if keyword:
                return FeishuQueryIntent(kind="eventline_lookup", keyword=keyword)
        if self._is_task_detail_query(normalized):
            keyword = self._extract_lookup_keyword(
                text,
                base_words=("任务", "状态", "详情", "谁负责", "负责人", "协作者", "截止", "开始", "变更", "最近", "查一下", "看看", "我的", "是什么", "未完成", "进行中", "已完成"),
            )
            if keyword:
                return FeishuQueryIntent(kind="task_lookup", keyword=keyword)
        return FeishuQueryIntent(kind="help")

    def _parse_intent_with_model(self, current_user: SessionUser, text: str) -> FeishuQueryIntent | None:
        config = _load_feishu_query_model_config(self.state, current_user.organizationId)
        if not config:
            return None
        member_names = self._org_member_names(current_user.organizationId)
        system_prompt = (
            "你是益语智库飞书查询意图解析器。你的唯一任务是把用户问题解析成 JSON，不要直接回答问题。\n"
            "只允许输出一个 JSON 对象，不能输出 markdown、解释或多余文本。\n"
            "可选 intent：tasks_list、task_lookup、review_status、review_summary、eventline_list、eventline_lookup、feishu_status、help、denied_scope。\n"
            "status_filter 只能是 open、doing、done、overdue、pending、any。\n"
            "time_filter 只能是 today、week、none。\n"
            "规则：\n"
            "1. 当前机器人只允许查询“本人”数据。\n"
            "2. 允许“我和某成员协作的任务有哪些”这类问法，此时 intent=tasks_list，participant_name=该成员姓名。\n"
            "3. 如果是在问别人自己的数据，例如“顾源源有哪些任务”，应返回 denied_scope。\n"
            "4. overdue 表示“已过截止时间且还没完成”。\n"
            "5. pending 表示“待确认协作任务”。\n"
            "6. 只有在明确点名某一条任务或事件线时，才使用 task_lookup / eventline_lookup。\n"
            "7. 如果用户问“我有哪些任务过期了但还没完成”，应识别为 tasks_list + overdue。\n"
            "8. 如果用户问“我和顾源源协作的任务有哪些”，应识别为 tasks_list，participant_name=顾源源。\n"
            f"当前提问人：{current_user.fullName}。\n"
            f"当前组织成员名单：{', '.join(member_names[:80]) or '暂无'}。\n"
            '输出格式：{"intent":"","status_filter":"open","time_filter":"none","participant_name":"","owner_name":"","keyword":""}'
        )
        payload = {
            "model": config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": str(text or "").strip()},
            ],
            "temperature": 0.1,
            "top_p": 0.8,
            "max_tokens": 320,
            "stream": False,
        }
        try:
            import httpx

            timeout = httpx.Timeout(timeout=None, connect=5.0, read=12.0, write=8.0, pool=8.0)
            raw = _sync_qwen_chat(config.api_key, payload, timeout)
            parsed = _feishu_extract_json_object(raw)
            if not parsed:
                return None
            return self._intent_from_model_payload(current_user, parsed)
        except Exception as exc:
            logger.warning("feishu.query.model_parse_failed: %s", exc)
            return None

    def _intent_from_model_payload(self, current_user: SessionUser, payload: dict[str, object]) -> FeishuQueryIntent | None:
        raw_kind = str(payload.get("intent") or payload.get("kind") or "").strip().lower()
        kind_alias = {
            "task_list": "tasks_list",
            "task_lookup": "task_lookup",
            "eventline_detail": "eventline_lookup",
            "event_line_list": "eventline_list",
            "event_line_lookup": "eventline_lookup",
            "review": "review_summary",
            "review_check": "review_status",
        }
        kind = kind_alias.get(raw_kind, raw_kind)
        allowed_kinds = {"tasks_list", "task_lookup", "review_status", "review_summary", "eventline_list", "eventline_lookup", "feishu_status", "help", "denied_scope"}
        if kind not in allowed_kinds:
            return None
        status_filter = str(payload.get("status_filter") or payload.get("status") or "open").strip().lower() or "open"
        if status_filter not in {"open", "doing", "done", "overdue", "pending", "any"}:
            status_filter = "open"
        time_filter = str(payload.get("time_filter") or payload.get("time_scope") or "none").strip().lower() or "none"
        if time_filter not in {"today", "week", "none"}:
            time_filter = "none"
        participant_name = self._normalize_member_name(
            current_user.organizationId,
            str(
                payload.get("participant_name")
                or payload.get("collaborator_name")
                or payload.get("with_person")
                or payload.get("person_name")
                or ""
            ).strip(),
        )
        owner_name = self._normalize_member_name(current_user.organizationId, str(payload.get("owner_name") or "").strip())
        keyword = str(payload.get("keyword") or payload.get("task_keyword") or payload.get("eventline_keyword") or "").strip() or None
        if participant_name and _feishu_name_matches(participant_name, current_user.fullName):
            participant_name = None
        if owner_name and _feishu_name_matches(owner_name, current_user.fullName):
            owner_name = None
        return FeishuQueryIntent(
            kind=kind,
            keyword=keyword,
            status_filter=status_filter,
            time_filter=time_filter,
            participant_name=participant_name,
            owner_name=owner_name,
        )

    def _org_member_names(self, organization_id: str) -> list[str]:
        rows = self.state.db.fetchall(
            """
            SELECT full_name
            FROM employee_accounts
            WHERE organization_id = ?
              AND account_status NOT IN ('rejected', 'disabled')
            ORDER BY full_name COLLATE NOCASE ASC
            LIMIT 80
            """,
            (organization_id,),
        )
        return [str(row["full_name"]) for row in rows if str(row["full_name"] or "").strip()]

    def _normalize_member_name(self, organization_id: str, candidate: str | None) -> str | None:
        normalized = str(candidate or "").strip()
        if not normalized:
            return None
        for name in self._org_member_names(organization_id):
            if _feishu_name_matches(name, normalized):
                return name
        return normalized[:24]

    @staticmethod
    def _is_task_list_query(normalized: str) -> bool:
        if any(keyword in normalized for keyword in ("待办", "待处理")):
            return True
        if "任务" not in normalized:
            return False
        explicit_list_markers = (
            "有哪些",
            "哪些任务",
            "我的任务",
            "还有哪些",
            "手上有哪些",
            "未完成",
            "没完成",
            "未做完",
            "没做完",
            "待办",
            "待处理",
            "进行中",
            "正在做",
            "处理中",
            "已完成",
            "完成了",
            "做完",
            "做完了",
            "已做完",
        )
        return "我" in normalized and any(marker in normalized for marker in explicit_list_markers)

    @staticmethod
    def _is_task_detail_query(normalized: str) -> bool:
        if "任务" not in normalized:
            return False
        detail_markers = ("状态", "详情", "负责人", "协作者", "截止", "开始", "变更", "最近", "谁负责")
        if normalized.startswith("任务") and len(normalized) > 2:
            return True
        return any(marker in normalized for marker in detail_markers)

    def _all_task_records(self, current_user: SessionUser) -> list[TaskRecord]:
        rows = self.state.db.fetchall(
            """
            SELECT DISTINCT t.*
            FROM tasks t
            LEFT JOIN task_collaborators tc ON tc.task_id = t.id
            WHERE t.organization_id = ?
              AND (
                    t.owner_id = ?
                    OR tc.user_id = ?
                  )
            ORDER BY t.updated_at DESC
            """,
            (current_user.organizationId, current_user.id, current_user.id),
        )
        return sorted([_task_record(self.state, row, current_user.id) for row in rows], key=_task_sort_key)

    def _extract_lookup_keyword(self, text: str, *, base_words: tuple[str, ...]) -> str | None:
        candidate = str(text or "").strip()
        for item in base_words:
            candidate = candidate.replace(item, " ")
        candidate = re.sub(r"[：:，,。？！!?、/]+", " ", candidate)
        candidate = re.sub(r"\s+", " ", candidate).strip()
        if len(candidate) >= 2:
            return candidate[:24]
        return None

    def _active_task_records(self, current_user: SessionUser) -> list[TaskRecord]:
        rows = self.state.db.fetchall(
            """
            SELECT DISTINCT t.*
            FROM tasks t
            LEFT JOIN task_collaborators tc ON tc.task_id = t.id
            WHERE t.organization_id = ?
              AND t.progress_status NOT IN ('done', 'rejected')
              AND (
                    t.owner_id = ?
                    OR (tc.user_id = ? AND tc.inbox_status = 'accepted')
                  )
            ORDER BY t.updated_at DESC
            """,
            (current_user.organizationId, current_user.id, current_user.id),
        )
        return sorted([_task_record(self.state, row, current_user.id) for row in rows], key=_task_sort_key)

    def _pending_task_records(self, current_user: SessionUser) -> list[TaskRecord]:
        rows = self.state.db.fetchall(
            """
            SELECT DISTINCT t.*
            FROM tasks t
            JOIN task_collaborators tc ON tc.task_id = t.id
            WHERE t.organization_id = ?
              AND tc.user_id = ?
              AND tc.inbox_status = 'pending'
            ORDER BY t.updated_at DESC
            """,
            (current_user.organizationId, current_user.id),
        )
        return [_task_record(self.state, row, current_user.id) for row in rows]

    @staticmethod
    def _normalized_task_list_intent(intent: FeishuQueryIntent) -> FeishuQueryIntent:
        if intent.kind == "tasks_today":
            return FeishuQueryIntent(kind="tasks_list", status_filter="open", time_filter="today", participant_name=intent.participant_name, owner_name=intent.owner_name, keyword=intent.keyword)
        if intent.kind == "tasks_week":
            return FeishuQueryIntent(kind="tasks_list", status_filter="open", time_filter="week", participant_name=intent.participant_name, owner_name=intent.owner_name, keyword=intent.keyword)
        if intent.kind == "tasks_overdue":
            return FeishuQueryIntent(kind="tasks_list", status_filter="overdue", time_filter="none", participant_name=intent.participant_name, owner_name=intent.owner_name, keyword=intent.keyword)
        if intent.kind == "tasks_pending":
            return FeishuQueryIntent(kind="tasks_list", status_filter="pending", time_filter="none", participant_name=intent.participant_name, owner_name=intent.owner_name, keyword=intent.keyword)
        if intent.kind == "tasks_doing":
            return FeishuQueryIntent(kind="tasks_list", status_filter="doing", time_filter="none", participant_name=intent.participant_name, owner_name=intent.owner_name, keyword=intent.keyword)
        if intent.kind == "tasks_done":
            return FeishuQueryIntent(kind="tasks_list", status_filter="done", time_filter="none", participant_name=intent.participant_name, owner_name=intent.owner_name, keyword=intent.keyword)
        if intent.kind == "tasks_open":
            return FeishuQueryIntent(kind="tasks_list", status_filter="open", time_filter="none", participant_name=intent.participant_name, owner_name=intent.owner_name, keyword=intent.keyword)
        return FeishuQueryIntent(
            kind="tasks_list",
            status_filter=intent.status_filter or "open",
            time_filter=intent.time_filter or "none",
            participant_name=intent.participant_name,
            owner_name=intent.owner_name,
            keyword=intent.keyword,
        )

    def _filter_tasks_by_intent(self, current_user: SessionUser, intent: FeishuQueryIntent) -> list[TaskRecord]:
        status_filter = intent.status_filter or "open"
        if status_filter == "pending":
            tasks = self._pending_task_records(current_user)
        elif status_filter == "done":
            tasks = [item for item in self._all_task_records(current_user) if item.progressStatus == "done"]
        elif status_filter == "any":
            tasks = self._all_task_records(current_user)
        else:
            tasks = self._active_task_records(current_user)

        today = datetime.now().date()
        if status_filter == "doing":
            tasks = [item for item in tasks if item.progressStatus == "doing"]
        elif status_filter == "overdue":
            tasks = [
                item
                for item in tasks
                if (due_dt := _task_datetime_value(item.dueDate)) is not None and due_dt.date() < today
            ]

        if intent.time_filter == "today":
            tasks = [item for item in tasks if _task_intersects_dates(item, today, today)]
        elif intent.time_filter == "week":
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            tasks = [item for item in tasks if _task_intersects_dates(item, week_start, week_end)]

        if intent.owner_name:
            tasks = [item for item in tasks if _feishu_name_matches(item.ownerName, intent.owner_name)]
        if intent.participant_name:
            tasks = [item for item in tasks if _task_matches_participant(item, intent.participant_name)]
        if intent.keyword:
            tasks = [item for item in tasks if _task_matches_keyword(item, intent.keyword)]
        return tasks[:FEISHU_QUERY_REPLY_LIMIT]

    def _filter_tasks(self, current_user: SessionUser, mode: Literal["today", "week", "overdue", "open", "doing", "done"]) -> list[TaskRecord]:
        if mode == "done":
            rows = self.state.db.fetchall(
                """
                SELECT DISTINCT t.*
                FROM tasks t
                LEFT JOIN task_collaborators tc ON tc.task_id = t.id
                WHERE t.organization_id = ?
                  AND t.progress_status = 'done'
                  AND (
                        t.owner_id = ?
                        OR tc.user_id = ?
                      )
                ORDER BY t.updated_at DESC
                """,
                (current_user.organizationId, current_user.id, current_user.id),
            )
            tasks = [_task_record(self.state, row, current_user.id) for row in rows]
            return tasks[:FEISHU_QUERY_REPLY_LIMIT]

        tasks = self._active_task_records(current_user)
        today = datetime.now().date()
        if mode == "open":
            return tasks[:FEISHU_QUERY_REPLY_LIMIT]
        if mode == "doing":
            return [item for item in tasks if item.progressStatus == "doing"][:FEISHU_QUERY_REPLY_LIMIT]
        if mode == "overdue":
            overdue: list[TaskRecord] = []
            for item in tasks:
                due_dt = _task_datetime_value(item.dueDate)
                if due_dt and due_dt.date() < today:
                    overdue.append(item)
            return overdue[:FEISHU_QUERY_REPLY_LIMIT]
        if mode == "today":
            return [item for item in tasks if _task_intersects_dates(item, today, today)][:FEISHU_QUERY_REPLY_LIMIT]
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        return [item for item in tasks if _task_intersects_dates(item, week_start, week_end)][:FEISHU_QUERY_REPLY_LIMIT]

    def _task_list_title(self, intent: FeishuQueryIntent) -> str:
        partner_prefix = f"我和{intent.participant_name}协作的" if intent.participant_name else ""
        if intent.status_filter == "pending":
            return f"{partner_prefix or '我的'}待确认协作任务"
        if intent.status_filter == "overdue":
            return f"{partner_prefix}逾期任务" if partner_prefix else "我的逾期任务"
        if intent.time_filter == "today":
            return f"我今天和{intent.participant_name}协作的任务" if intent.participant_name else "我今天的任务"
        if intent.time_filter == "week":
            return f"我本周和{intent.participant_name}协作的任务" if intent.participant_name else "我本周的任务"
        if intent.status_filter == "doing":
            return f"{partner_prefix}进行中的任务" if partner_prefix else "我进行中的任务"
        if intent.status_filter == "done":
            return f"{partner_prefix}已完成的任务" if partner_prefix else "我已完成的任务"
        return f"{partner_prefix}任务" if partner_prefix else "我的待办"

    def _reply_task_list(self, title: str, tasks: list[TaskRecord]) -> str:
        if not tasks:
            return f"【益语智库】{title}\n当前没有匹配任务。你也可以补充标题关键词再查。"
        lines = [f"【益语智库】{title}（{len(tasks)} 项）"]
        for index, item in enumerate(tasks[:FEISHU_QUERY_REPLY_LIMIT], start=1):
            lines.append(f"{index}. {item.title}｜{_task_progress_label(item.progressStatus)}｜{_task_time_brief(item)}")
        if len(tasks) >= FEISHU_QUERY_REPLY_LIMIT:
            lines.append("如需继续缩小范围，请补标题关键词或时间范围。")
        return "\n".join(lines)

    def _reply_pending_tasks(self, current_user: SessionUser, intent: FeishuQueryIntent) -> str:
        tasks = self._filter_tasks_by_intent(current_user, intent)
        if not tasks:
            return f"【益语智库】{self._task_list_title(intent)}\n当前没有待确认任务。"
        lines = [f"【益语智库】{self._task_list_title(intent)}（{len(tasks)} 项）"]
        for index, item in enumerate(tasks, start=1):
            lines.append(f"{index}. {item.title}｜发起人 {item.creatorName}｜{_task_time_brief(item)}")
        lines.append("如需处理，请回到益语智库协作收件箱确认接受。")
        return "\n".join(lines)

    def _reply_task_detail(self, current_user: SessionUser, keyword: str, *, participant_name: str | None = None) -> str:
        tasks = [
            item
            for item in self._all_task_records(current_user)
            if _task_matches_keyword(item, keyword) and _task_matches_participant(item, participant_name)
        ]
        if not tasks:
            return f"【益语智库】任务查询\n我查了你当前组织下你参与的任务，没有找到和“{keyword}”匹配的任务。你也可以直接问“我有哪些任务未完成”这类列表问题。"
        if len(tasks) > 1:
            lines = [f"【益语智库】任务查询\n我找到 {min(len(tasks), FEISHU_QUERY_REPLY_LIMIT)} 个候选任务，请补更具体的标题关键词："]
            for index, item in enumerate(tasks[:FEISHU_QUERY_REPLY_LIMIT], start=1):
                lines.append(f"{index}. {item.title}｜{_task_progress_label(item.progressStatus)}｜{_task_time_brief(item)}")
            return "\n".join(lines)
        task = tasks[0]
        collaborators = "、".join(item.fullName for item in task.collaborators[:3]) if task.collaborators else "无"
        latest_activity = _task_latest_activity_brief(self.state, task.id) or "暂无明显变更记录"
        return "\n".join(
            [
                f"【益语智库】任务摘要｜{task.title}",
                f"状态：{_task_progress_label(task.progressStatus)}",
                f"负责人：{task.ownerName or '未设置'}",
                f"协作者：{collaborators}",
                f"开始时间：{_task_datetime_text(task.startDate)}",
                f"截止时间：{_task_datetime_text(task.dueDate)}",
                f"最近变更：{latest_activity}",
            ]
        )

    def _reply_review_status(self, current_user: SessionUser) -> str:
        dashboard = _dashboard_for_user(self.state, current_user, None)
        current_week = _week_label_for_today()
        if dashboard.currentReview and dashboard.currentReview.weekLabel == current_week:
            return f"【益语智库】周复盘状态\n你本周（{current_week}）已提交周复盘，提交时间：{str(dashboard.currentReview.submittedAt)[:16].replace('T', ' ')}。"
        return f"【益语智库】周复盘状态\n你本周（{current_week}）还没有提交周复盘。"

    def _reply_review_summary(self, current_user: SessionUser) -> str:
        dashboard = _dashboard_for_user(self.state, current_user, None)
        review = dashboard.currentReview
        if not review:
            return f"【益语智库】周复盘摘要\n你本周（{_week_label_for_today()}）还没有提交周复盘。"
        highlights = _extract_non_empty_lines(review.workProgress, review.workFreeNote, limit=3)
        blockers = _extract_non_empty_lines(review.workBlocker, review.supportNeeded, limit=2)
        next_focus = _extract_non_empty_lines(review.nextWeekFocus, review.workDirection, limit=1)
        lines = [f"【益语智库】周复盘摘要｜{review.weekLabel}"]
        if highlights:
            lines.append(f"重点：{'；'.join(highlights)}")
        if blockers:
            lines.append(f"卡点：{'；'.join(blockers)}")
        if next_focus:
            lines.append(f"下周重点：{next_focus[0]}")
        lines.append(f"提交时间：{str(review.submittedAt)[:16].replace('T', ' ')}")
        return "\n".join(lines)

    def _reply_event_line_list(self, current_user: SessionUser) -> str:
        rows = self.state.db.fetchall(
            """
            SELECT DISTINCT el.*
            FROM event_lines el
            JOIN tasks t ON t.event_line_id = el.id
            LEFT JOIN task_collaborators tc ON tc.task_id = t.id
            WHERE el.organization_id = ?
              AND (t.owner_id = ? OR tc.user_id = ?)
            ORDER BY el.updated_at DESC
            LIMIT ?
            """,
            (current_user.organizationId, current_user.id, current_user.id, FEISHU_QUERY_REPLY_LIMIT),
        )
        if not rows:
            return "【益语智库】我的事件线\n当前没有查到你参与的事件线。"
        lines = [f"【益语智库】我的事件线（{len(rows)} 条）"]
        for index, row in enumerate(rows, start=1):
            event_line = _event_line_record(self.state, row)
            task_count = int(
                self.state.db.scalar(
                    """
                    SELECT COUNT(DISTINCT t.id)
                    FROM tasks t
                    LEFT JOIN task_collaborators tc ON tc.task_id = t.id
                    WHERE t.event_line_id = ?
                      AND (t.owner_id = ? OR tc.user_id = ?)
                    """,
                    (event_line.id, current_user.id, current_user.id),
                )
                or 0
            )
            lines.append(f"{index}. {event_line.name}｜{event_line.status}｜关联任务 {task_count} 项")
        return "\n".join(lines)

    def _reply_event_line_detail(self, current_user: SessionUser, keyword: str) -> str:
        rows = self.state.db.fetchall(
            """
            SELECT DISTINCT el.*
            FROM event_lines el
            JOIN tasks t ON t.event_line_id = el.id
            LEFT JOIN task_collaborators tc ON tc.task_id = t.id
            WHERE el.organization_id = ?
              AND (t.owner_id = ? OR tc.user_id = ?)
            ORDER BY el.updated_at DESC
            """,
            (current_user.organizationId, current_user.id, current_user.id),
        )
        matched = [row for row in rows if _feishu_text_for_match(keyword) in _feishu_text_for_match(str(row["name"] or ""))]
        if not matched:
            return f"【益语智库】事件线查询\n没有找到名称包含“{keyword}”的事件线。"
        if len(matched) > 1:
            lines = [f"【益语智库】事件线查询\n我找到 {min(len(matched), FEISHU_QUERY_REPLY_LIMIT)} 个候选事件线，请补更具体的关键词："]
            for index, row in enumerate(matched[:FEISHU_QUERY_REPLY_LIMIT], start=1):
                lines.append(f"{index}. {str(row['name'])}｜{str(row['status'] or 'active')}")
            return "\n".join(lines)
        detail = _event_line_detail_record(self.state, matched[0], current_user.id)
        related_tasks = detail.tasks[:3]
        lines = [f"【益语智库】事件线摘要｜{detail.eventLine.name}"]
        lines.append(f"状态：{detail.eventLine.status}")
        if detail.eventLine.stage:
            lines.append(f"阶段：{detail.eventLine.stage}")
        if detail.eventLine.currentBlocker:
            lines.append(f"当前卡点：{detail.eventLine.currentBlocker}")
        if detail.eventLine.nextStep:
            lines.append(f"下一步：{detail.eventLine.nextStep}")
        if related_tasks:
            lines.append("关联任务：")
            for item in related_tasks:
                lines.append(f"- {item.title}｜{_task_progress_label(item.progressStatus)}｜{_task_time_brief(item)}")
        return "\n".join(lines)

    def _reply_feishu_status(self, current_user: SessionUser) -> str:
        delivery = _feishu_delivery_profile_record(self.state, current_user)
        integration = _org_feishu_integration_record(self.state, current_user)
        lines = ["【益语智库】飞书接通状态"]
        lines.append(f"组织飞书接入：{'已接通' if integration.enabled else '未接通'}")
        lines.append(f"本人身份匹配：{delivery.deliveryStatusLabel}")
        if delivery.mobile:
            lines.append(f"手机号：{delivery.mobile}")
        if delivery.blockedReason:
            lines.append(f"提示：{delivery.blockedReason}")
        return "\n".join(lines)


class FeishuInboundService:
    def __init__(self, state: AppState):
        self.state = state
        self.identity_resolver = FeishuIdentityResolver(state)
        self.query_service = FeishuQueryService(state)

    def _send_processing_placeholder(
        self,
        *,
        tenant_access_token: str,
        sender_open_id: str,
        question: str,
    ) -> str | None:
        try:
            payload = _feishu_send_interactive_message(
                tenant_access_token=tenant_access_token,
                receive_id_type="open_id",
                receive_id=sender_open_id,
                card=_build_feishu_query_progress_card(question),
            )
        except Exception as exc:
            logger.warning("feishu.query.placeholder_send_failed: %s", exc)
            return None
        return _feishu_message_id_from_payload(payload)

    def _deliver_query_reply(
        self,
        *,
        tenant_access_token: str,
        sender_open_id: str,
        placeholder_message_id: str | None,
        query_type: str,
        status: str,
        reply_text: str,
    ) -> tuple[str, str]:
        card = _build_feishu_query_result_card(query_type=query_type, status=status, reply_text=reply_text)
        if placeholder_message_id:
            try:
                _feishu_patch_interactive_message(
                    tenant_access_token=tenant_access_token,
                    message_id=placeholder_message_id,
                    card=card,
                )
                return status, reply_text
            except Exception as exc:
                logger.warning("feishu.query.placeholder_patch_failed: %s", exc)
        try:
            _feishu_send_interactive_message(
                tenant_access_token=tenant_access_token,
                receive_id_type="open_id",
                receive_id=sender_open_id,
                card=card,
            )
            return status, reply_text
        except Exception as card_exc:
            try:
                _feishu_send_text_message(
                    tenant_access_token=tenant_access_token,
                    receive_id_type="open_id",
                    receive_id=sender_open_id,
                    text=reply_text,
                )
                return status, reply_text
            except Exception as text_exc:
                error_text = f"{reply_text}\n（当前回消息失败：{str(text_exc)[:80]}）"
                return "error", error_text

    def handle_text_message(
        self,
        *,
        organization_id: str,
        tenant_access_token: str,
        sender_open_id: str,
        sender_feishu_user_id: str | None,
        sender_union_id: str | None,
        tenant_key: str | None,
        chat_id: str,
        message_id: str,
        text: str,
    ) -> None:
        existing = self.state.db.fetchone(
            "SELECT id FROM org_feishu_query_logs WHERE message_id = ?",
            (message_id,),
        )
        if existing:
            return
        placeholder_message_id = self._send_processing_placeholder(
            tenant_access_token=tenant_access_token,
            sender_open_id=sender_open_id,
            question=text,
        )

        current_user, resolve_error = self.identity_resolver.resolve_user(
            organization_id=organization_id,
            sender_open_id=sender_open_id,
            sender_feishu_user_id=sender_feishu_user_id,
            sender_union_id=sender_union_id,
            tenant_access_token=tenant_access_token,
            tenant_key=tenant_key,
        )
        if current_user is None:
            reply_text = resolve_error or "暂时无法识别你的益语账号，请先在软件里完成飞书身份匹配。"
            status = "unresolved"
            status, reply_text = self._deliver_query_reply(
                tenant_access_token=tenant_access_token,
                sender_open_id=sender_open_id,
                placeholder_message_id=placeholder_message_id,
                query_type="identity",
                status=status,
                reply_text=reply_text,
            )
            _record_feishu_query_log(
                self.state,
                organization_id=organization_id,
                message_id=message_id,
                sender_open_id=sender_open_id,
                sender_feishu_user_id=sender_feishu_user_id,
                chat_id=chat_id,
                query_type="identity",
                query_text=text,
                resolved_user_id=None,
                status=status,
                reply_excerpt=reply_text,
            )
            return

        status, query_type, reply_text = self.query_service.build_reply(current_user=current_user, text=text)
        status, reply_text = self._deliver_query_reply(
            tenant_access_token=tenant_access_token,
            sender_open_id=sender_open_id,
            placeholder_message_id=placeholder_message_id,
            query_type=query_type,
            status=status,
            reply_text=reply_text,
        )
        _record_feishu_query_log(
            self.state,
            organization_id=organization_id,
            message_id=message_id,
            sender_open_id=sender_open_id,
            sender_feishu_user_id=sender_feishu_user_id,
            chat_id=chat_id,
            query_type=query_type,
            query_text=text,
            resolved_user_id=current_user.id,
            status=status,
            reply_excerpt=reply_text,
        )


class FeishuLongConnectionCoordinator:
    reconcile_interval_seconds = 45
    reconnect_delay_seconds = 10

    def __init__(self, state: AppState):
        self.state = state
        self.inbound_service = FeishuInboundService(state)
        self._active_workers: dict[str, Thread] = {}

    def run(self) -> None:
        while not self.state.feishu_query_stop.is_set():
            try:
                self._ensure_workers()
            except Exception:
                logger.exception("feishu.query.coordinator_failed")
            self.state.feishu_query_stop.wait(self.reconcile_interval_seconds)

    def _ensure_workers(self) -> None:
        rows = self.state.db.fetchall(
            """
            SELECT organization_id, app_id, updated_at
            FROM org_feishu_integrations
            WHERE enabled = 1
              AND app_id != ''
              AND app_secret_encrypted != ''
            ORDER BY updated_at DESC
            """
        )
        for row in rows:
            organization_id = str(row["organization_id"])
            if organization_id in self._active_workers and self._active_workers[organization_id].is_alive():
                continue
            worker = Thread(
                target=self._run_org_worker,
                args=(organization_id,),
                name=f"feishu-query-{organization_id}",
                daemon=True,
            )
            worker.start()
            self._active_workers[organization_id] = worker

    def _run_org_worker(self, organization_id: str) -> None:
        while not self.state.feishu_query_stop.is_set():
            try:
                import lark_oapi as lark

                integration_row = self.state.db.fetchone(
                    "SELECT * FROM org_feishu_integrations WHERE organization_id = ? AND enabled = 1",
                    (organization_id,),
                )
                if not integration_row:
                    return
                app_id = str(integration_row["app_id"] or "").strip()
                if not app_id or not integration_row["app_secret_encrypted"]:
                    return
                app_secret = _org_feishu_decrypt(
                    self.state,
                    str(integration_row["app_secret_encrypted"]),
                    str(integration_row["encryption_nonce"]),
                    organization_id,
                )

                def _handler(data) -> None:
                    try:
                        event = getattr(data, "event", None)
                        sender = getattr(event, "sender", None)
                        message = getattr(event, "message", None)
                        sender_id = getattr(sender, "sender_id", None)
                        if not sender or not message or not sender_id:
                            return
                        if str(getattr(sender, "sender_type", "") or "") == "app":
                            return
                        if str(getattr(message, "chat_type", "") or "") != "p2p":
                            return
                        if str(getattr(message, "message_type", "") or "") != "text":
                            return
                        sender_open_id = str(getattr(sender_id, "open_id", "") or "").strip()
                        if not sender_open_id:
                            return
                        tenant_access = _resolve_org_feishu_tenant_access_token(self.state, organization_id=organization_id)
                        if not tenant_access:
                            return
                        _app_id, tenant_access_token = tenant_access
                        self.inbound_service.handle_text_message(
                            organization_id=organization_id,
                            tenant_access_token=tenant_access_token,
                            sender_open_id=sender_open_id,
                            sender_feishu_user_id=str(getattr(sender_id, "user_id", "") or "").strip() or None,
                            sender_union_id=str(getattr(sender_id, "union_id", "") or "").strip() or None,
                            tenant_key=str(getattr(sender, "tenant_key", "") or "").strip() or None,
                            chat_id=str(getattr(message, "chat_id", "") or "").strip(),
                            message_id=str(getattr(message, "message_id", "") or "").strip(),
                            text=_feishu_extract_text_content(getattr(message, "content", None)),
                        )
                    except Exception:
                        logger.exception("feishu.query.handle_text_message_failed", extra={"organization_id": organization_id})

                event_handler = lark.EventDispatcherHandler.builder("", "") \
                    .register_p2_im_message_receive_v1(_handler) \
                    .build()

                cli = lark.ws.Client(
                    app_id,
                    app_secret,
                    event_handler=event_handler,
                    log_level=lark.LogLevel.INFO,
                )
                cli.start()
            except Exception:
                logger.exception("feishu.query.worker_failed", extra={"organization_id": organization_id})
            if self.state.feishu_query_stop.wait(self.reconnect_delay_seconds):
                break


def _record_task_feishu_notification(
    state: AppState,
    *,
    organization_id: str,
    task_id: str,
    event_type: Literal["created", "key_fields_changed", "content_fields_changed"],
    recipient_user_id: str,
    recipient_open_id: str | None,
    delivery_status: Literal["sent", "skipped_unbound", "failed"],
    delivery_message: str,
    changed_fields: list[str] | None = None,
) -> None:
    state.db.execute(
        """
        INSERT INTO org_feishu_task_notifications(
            id, organization_id, task_id, event_type, recipient_user_id, recipient_open_id,
            delivery_status, delivery_message, changed_fields_json, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id("fs_task_notice"),
            organization_id,
            task_id,
            event_type,
            recipient_user_id,
            recipient_open_id,
            delivery_status,
            delivery_message,
            to_json(changed_fields or []),
            now_iso(),
        ),
    )


def _task_datetime_text(value: str | None) -> str:
    if not value:
        return "未设置"
    raw = str(value).strip()
    if not raw:
        return "未设置"
    try:
        normalized = raw.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if len(raw) <= 10 and "T" not in raw:
            return f"{parsed.strftime('%Y-%m-%d')} 09:00"
        return parsed.replace(tzinfo=None).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        if "T" not in raw and ":" not in raw:
            return f"{raw} 09:00"
        return raw.replace("T", " ")


def _task_person_name_map(state: AppState, user_ids: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for user_id in user_ids:
        if not user_id or user_id in result:
            continue
        row = state.db.fetchone("SELECT full_name FROM employee_accounts WHERE id = ?", (user_id,))
        result[user_id] = str(row["full_name"]) if row and row["full_name"] else user_id
    return result


def _task_role_label(task_row, recipient_user_id: str) -> str:
    owner_id = str(task_row["owner_id"]) if task_row["owner_id"] else None
    return "负责人" if owner_id and owner_id == recipient_user_id else "协作者"


def _task_changed_field_labels(changed_fields: list[str]) -> list[str]:
    labels: list[str] = []
    if "title" in changed_fields:
        labels.append("标题")
    if "description" in changed_fields:
        labels.append("详情")
    if "priority" in changed_fields:
        labels.append("优先级")
    if "listId" in changed_fields:
        labels.append("任务清单")
    if "startDate" in changed_fields:
        labels.append("开始时间")
    if "dueDate" in changed_fields:
        labels.append("截止时间")
    if "durationMinutes" in changed_fields:
        labels.append("时长")
    if "ownerId" in changed_fields:
        labels.append("负责人")
    if "collaboratorIds" in changed_fields:
        labels.append("协作者")
    return labels


def _task_change_notice_heading(changed_fields: list[str]) -> str:
    if any(field in TASK_IMMEDIATE_FEISHU_CHANGE_FIELDS for field in changed_fields):
        return "任务安排已更新"
    return "任务内容已更新"


def _task_priority_label(value: str | None) -> str:
    return {
        "low": "低优先级",
        "normal": "普通优先级",
        "high": "高优先级",
    }.get(str(value or "").strip(), str(value or "未设置") or "未设置")


def _task_list_name(state: AppState, list_id: str | None) -> str:
    if not list_id:
        return "未设置"
    row = state.db.fetchone("SELECT name FROM task_lists WHERE id = ?", (list_id,))
    return str(row["name"]) if row and row["name"] else str(list_id)


def _build_task_created_feishu_message(
    state: AppState,
    *,
    task_row,
    recipient_user_id: str,
    actor_name: str,
) -> str:
    return "\n".join(
        [
            "【益语智库】你有新的协作任务",
            f"任务：{str(task_row['title'])}",
            f"你的角色：{_task_role_label(task_row, recipient_user_id)}",
            f"发起人：{actor_name}",
            f"开始时间：{_task_datetime_text(str(task_row['start_date']) if task_row['start_date'] else None)}",
            f"截止时间：{_task_datetime_text(str(task_row['due_date']) if task_row['due_date'] else None)}",
            "请回到益语智库处理。",
        ]
    )


def _build_task_changed_feishu_message(
    state: AppState,
    *,
    task_row,
    collaborator_ids: list[str],
    recipient_user_id: str,
    actor_name: str,
    changed_fields: list[str],
) -> str:
    person_names = _task_person_name_map(
        state,
        [str(task_row["owner_id"]) if task_row["owner_id"] else "", *collaborator_ids],
    )
    lines = [
        f"【益语智库】{_task_change_notice_heading(changed_fields)}",
        f"任务：{str(task_row['title'])}",
        f"你的角色：{_task_role_label(task_row, recipient_user_id)}",
        f"发起变更：{actor_name}",
        f"变更项：{'、'.join(_task_changed_field_labels(changed_fields))}",
    ]
    if "title" in changed_fields:
        lines.append(f"当前标题：{str(task_row['title'])}")
    if "description" in changed_fields:
        description = str(task_row["description"] or "").strip()
        lines.append(f"当前详情：{_truncate_plain_text(description, 80) if description else '已清空'}")
    if "priority" in changed_fields:
        lines.append(f"优先级：{_task_priority_label(str(task_row['priority']) if task_row['priority'] else None)}")
    if "listId" in changed_fields:
        lines.append(f"任务清单：{_task_list_name(state, str(task_row['list_id']) if task_row['list_id'] else None)}")
    if "startDate" in changed_fields:
        lines.append(f"开始时间：{_task_datetime_text(str(task_row['start_date']) if task_row['start_date'] else None)}")
    if "dueDate" in changed_fields:
        lines.append(f"截止时间：{_task_datetime_text(str(task_row['due_date']) if task_row['due_date'] else None)}")
    if "durationMinutes" in changed_fields:
        lines.append(f"任务时长：{int(task_row['duration_minutes'] or 60)} 分钟")
    if "ownerId" in changed_fields:
        owner_id = str(task_row["owner_id"]) if task_row["owner_id"] else ""
        lines.append(f"负责人：{person_names.get(owner_id) or '未设置'}")
    if "collaboratorIds" in changed_fields:
        names = [person_names.get(user_id, user_id) for user_id in collaborator_ids if user_id]
        lines.append(f"协作者：{'、'.join(names) if names else '无'}")
    lines.append("请回到益语智库查看最新安排。")
    return "\n".join(lines)


def _task_datetime_value(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        normalized = raw.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo:
            parsed = parsed.astimezone().replace(tzinfo=None)
        if len(raw) <= 10 and "T" not in raw:
            return parsed.replace(hour=9, minute=0, second=0, microsecond=0)
        return parsed.replace(second=0, microsecond=0)
    except ValueError:
        return None


def _truncate_plain_text(value: str, limit: int = 48) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 1)]}…"


def _extract_non_empty_lines(*values: str, limit: int) -> list[str]:
    lines: list[str] = []
    for value in values:
        for item in str(value or "").splitlines():
            cleaned = item.strip().lstrip("•").strip()
            if cleaned and cleaned not in lines:
                lines.append(cleaned)
            if len(lines) >= limit:
                return lines
    return lines


def _build_feishu_readonly_card(
    *,
    template: Literal["blue", "orange", "cyan", "green", "turquoise", "red"],
    title: str,
    headline: str,
    core_lines: list[str],
    secondary_blocks: list[tuple[str, list[str] | str]],
    footer: str,
) -> dict:
    elements: list[dict[str, object]] = [
        {"tag": "markdown", "content": f"**{headline}**"},
    ]
    if core_lines:
        elements.append(
            {
                "tag": "markdown",
                "content": "\n".join(f"• {line}" for line in core_lines if line),
            }
        )
    for index, (section_title, section_value) in enumerate(secondary_blocks):
        lines = section_value if isinstance(section_value, list) else [section_value]
        normalized = [str(item).strip() for item in lines if str(item).strip()]
        if not normalized:
            continue
        elements.append({"tag": "hr"})
        content = "\n".join(f"• {line}" for line in normalized)
        elements.append({"tag": "markdown", "content": f"**{section_title}**\n{content}"})
        if index >= 2:
            break
    elements.append({"tag": "hr"})
    elements.append({"tag": "markdown", "content": f"> {footer}"})
    return {
        "header": {
            "template": template,
            "title": {"tag": "plain_text", "content": title},
        },
        "elements": elements,
    }


def _feishu_dispatch_record(row) -> FeishuNotificationDispatchRecord:
    return FeishuNotificationDispatchRecord(
        id=str(row["id"]),
        messageType=str(row["message_type"]),
        objectType=str(row["object_type"]),
        objectId=str(row["object_id"]),
        recipientUserId=str(row["recipient_user_id"]),
        deliveryStatus=str(row["delivery_status"]),
        deliveryChannel=str(row["delivery_channel"] or ""),
        deliveryMessage=str(row["delivery_message"] or ""),
        dedupeKey=str(row["dedupe_key"]) if row["dedupe_key"] else None,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
        sentAt=str(row["sent_at"]) if row["sent_at"] else None,
    )


class FeishuNotificationService:
    task_change_merge_window_seconds = 3 * 60

    def __init__(self, state: AppState):
        self.state = state

    def notify_task_change(
        self,
        *,
        task_row,
        current_user: SessionUser,
        collaborator_ids: list[str],
        event_type: Literal["created", "key_fields_changed"],
        changed_fields: list[str] | None = None,
    ) -> None:
        if event_type == "created":
            self._send_task_created(task_row=task_row, current_user=current_user, collaborator_ids=collaborator_ids)
            return
        normalized_changed_fields = [
            field
            for field in (changed_fields or [])
            if field in {*TASK_IMMEDIATE_FEISHU_CHANGE_FIELDS, *TASK_DEFERRED_FEISHU_CHANGE_FIELDS}
        ]
        if not normalized_changed_fields:
            return
        immediate_changed_fields = [field for field in normalized_changed_fields if field in TASK_IMMEDIATE_FEISHU_CHANGE_FIELDS]
        deferred_changed_fields = [field for field in normalized_changed_fields if field in TASK_DEFERRED_FEISHU_CHANGE_FIELDS]
        if immediate_changed_fields:
            self._send_task_changed_immediately(
                task_row=task_row,
                current_user=current_user,
                collaborator_ids=collaborator_ids,
                changed_fields=normalized_changed_fields,
            )
            return
        self._queue_task_changed(
            task_row=task_row,
            current_user=current_user,
            collaborator_ids=collaborator_ids,
            changed_fields=deferred_changed_fields,
        )

    def notify_weekly_review(
        self,
        *,
        review_id: str,
        current_user: SessionUser,
        payload: WeeklyReviewCreatePayload,
    ) -> FeishuNotificationDispatchRecord:
        headline = _truncate_plain_text(
            next(
                (
                    value
                    for value in [
                        payload.workFreeNote,
                        payload.workProgress,
                        payload.personalGrowthNote,
                        payload.nextWeekFocus,
                        f"{payload.weekLabel} 周复盘已保存",
                    ]
                    if str(value or "").strip()
                ),
                f"{payload.weekLabel} 周复盘已保存",
            ),
            60,
        )
        highlights = _extract_non_empty_lines(payload.workProgress, payload.workFreeNote, limit=3)
        blockers = _extract_non_empty_lines(payload.workBlocker, payload.supportNeeded, limit=2)
        next_focus = _extract_non_empty_lines(payload.nextWeekFocus, payload.workDirection, limit=1)
        card = _build_feishu_readonly_card(
            template="cyan",
            title=f"周复盘已保存｜{payload.weekLabel}",
            headline=headline,
            core_lines=[
                f"周标题：{payload.weekLabel}",
                f"提交人：{current_user.fullName}",
                f"下周重点：{next_focus[0] if next_focus else '待补充'}",
            ],
            secondary_blocks=[
                ("本周亮点", highlights),
                ("卡点关注", blockers),
            ],
            footer="请回到益语智库查看完整周复盘。",
        )
        text = "\n".join(
            [
                "【益语智库】周复盘已保存",
                f"周标题：{payload.weekLabel}",
                f"一句话总结：{headline}",
                *(f"亮点：{item}" for item in highlights[:3]),
                *(f"卡点：{item}" for item in blockers[:2]),
                f"下周重点：{next_focus[0] if next_focus else '待补充'}",
                "请回到益语智库查看完整周复盘。",
            ]
        )
        return self._send_prepared_notification(
            organization_id=current_user.organizationId,
            message_type="weekly_review",
            object_type="weekly_review",
            object_id=review_id,
            event_type="saved",
            recipient_user_id=current_user.id,
            title=f"{payload.weekLabel} 周复盘",
            card=card,
            text=text,
            payload={
                "weekLabel": payload.weekLabel,
                "headline": headline,
                "highlights": highlights,
                "blockers": blockers,
                "nextFocus": next_focus,
            },
        )

    def notify_badge_unlock(
        self,
        *,
        current_user: SessionUser,
        payload: FeishuBadgeNotificationPayload,
    ) -> FeishuNotificationDispatchRecord:
        dedupe_key = f"badge_unlock:{current_user.organizationId}:{current_user.id}:{payload.badgeId}"
        existing = self._blocking_dedupe_record(dedupe_key=dedupe_key)
        if existing:
            return existing
        card = _build_feishu_readonly_card(
            template="green",
            title=f"点亮徽章｜{_truncate_plain_text(payload.badgeName, 30)}",
            headline=payload.badgeName,
            core_lines=[
                f"获得者：{current_user.fullName}",
                f"分类：{payload.categoryName or '成长徽章'}",
                f"获得 XP：+{int(payload.xp or 0)}",
            ],
            secondary_blocks=[
                ("徽章说明", payload.badgeDescription or "恭喜完成一次新的成长点亮。"),
            ],
            footer="请回到益语智库查看完整徽章与成长记录。",
        )
        text = "\n".join(
            [
                "【益语智库】你点亮了新徽章",
                f"徽章：{payload.badgeName}",
                f"分类：{payload.categoryName or '成长徽章'}",
                f"获得 XP：+{int(payload.xp or 0)}",
                f"说明：{payload.badgeDescription or '恭喜完成一次新的成长点亮。'}",
                "请回到益语智库查看完整徽章与成长记录。",
            ]
        )
        return self._send_prepared_notification(
            organization_id=current_user.organizationId,
            message_type="badge_unlock",
            object_type="badge_unlock",
            object_id=payload.badgeId,
            event_type="unlocked",
            recipient_user_id=current_user.id,
            title=payload.badgeName,
            card=card,
            text=text,
            dedupe_key=dedupe_key,
            payload=payload.model_dump(),
        )

    def process_due_notifications(self, *, reference_time: datetime | None = None) -> None:
        now_value = (reference_time or datetime.now()).replace(microsecond=0).isoformat()
        rows = self.state.db.fetchall(
            """
            SELECT * FROM org_feishu_notifications
            WHERE delivery_status = 'queued' AND due_at IS NOT NULL AND due_at <= ?
            ORDER BY created_at ASC
            LIMIT 50
            """,
            (now_value,),
        )
        for row in rows:
            if str(row["message_type"]) not in {"task_changed", "task_content_changed"}:
                continue
            self._deliver_task_changed_row(row)

    def process_overdue_digest(self, *, reference_time: datetime | None = None) -> None:
        current_time = reference_time or datetime.now()
        if current_time.weekday() >= 5 or current_time.hour < 9:
            return
        today_key = current_time.date().isoformat()
        org_rows = self.state.db.fetchall("SELECT id FROM organizations")
        for org_row in org_rows:
            organization_id = str(org_row["id"])
            user_rows = self.state.db.fetchall(
                """
                SELECT id, full_name
                FROM employee_accounts
                WHERE organization_id = ? AND account_status != 'disabled'
                ORDER BY created_at ASC
                """,
                (organization_id,),
            )
            for user_row in user_rows:
                user_id = str(user_row["id"])
                dedupe_key = f"overdue_digest:{organization_id}:{user_id}:{today_key}"
                if self._any_dedupe_record(dedupe_key=dedupe_key):
                    continue
                overdue_tasks = self._collect_overdue_tasks_for_user(
                    organization_id=organization_id,
                    user_id=user_id,
                    reference_time=current_time,
                )
                if not overdue_tasks:
                    continue
                user_name = str(user_row["full_name"] or user_id)
                earliest = overdue_tasks[0]["dueText"]
                card = _build_feishu_readonly_card(
                    template="red",
                    title=f"逾期任务提醒｜{len(overdue_tasks)} 项",
                    headline=f"{user_name}，你有 {len(overdue_tasks)} 项任务已逾期",
                    core_lines=[
                        f"逾期总数：{len(overdue_tasks)}",
                        f"最早逾期：{earliest}",
                    ],
                    secondary_blocks=[
                        ("待处理任务", [f"{item['title']}｜截止 {item['dueText']}" for item in overdue_tasks[:5]]),
                    ],
                    footer="请回到益语智库处理或调整截止时间。",
                )
                text = "\n".join(
                    [
                        "【益语智库】今日逾期提醒",
                        f"逾期总数：{len(overdue_tasks)}",
                        f"最早逾期：{earliest}",
                        *[f"{item['title']}｜截止 {item['dueText']}" for item in overdue_tasks[:5]],
                        "请回到益语智库处理或调整截止时间。",
                    ]
                )
                self._send_prepared_notification(
                    organization_id=organization_id,
                    message_type="overdue_digest",
                    object_type="overdue_digest",
                    object_id=today_key,
                    event_type="daily_digest",
                    recipient_user_id=user_id,
                    title=f"{today_key} 逾期提醒",
                    card=card,
                    text=text,
                    dedupe_key=dedupe_key,
                    payload={
                        "date": today_key,
                        "taskCount": len(overdue_tasks),
                        "taskIds": [item["id"] for item in overdue_tasks[:5]],
                    },
                )

    def _task_recipient_ids(self, *, task_row, collaborator_ids: list[str]) -> list[str]:
        owner_id = str(task_row["owner_id"]) if task_row["owner_id"] else None
        recipient_ids: list[str] = []
        for candidate in [owner_id, *collaborator_ids]:
            if candidate and candidate not in recipient_ids:
                recipient_ids.append(candidate)
        return recipient_ids

    def _send_task_created(self, *, task_row, current_user: SessionUser, collaborator_ids: list[str]) -> None:
        recipient_ids = self._task_recipient_ids(task_row=task_row, collaborator_ids=collaborator_ids)
        for recipient_user_id in recipient_ids:
            card = _build_feishu_readonly_card(
                template="blue",
                title=f"新建任务｜{_truncate_plain_text(str(task_row['title']), 30)}",
                headline=str(task_row["title"]),
                core_lines=[
                    f"你的角色：{_task_role_label(task_row, recipient_user_id)}",
                    f"发起人：{current_user.fullName}",
                    f"开始时间：{_task_datetime_text(str(task_row['start_date']) if task_row['start_date'] else None)}",
                    f"截止时间：{_task_datetime_text(str(task_row['due_date']) if task_row['due_date'] else None)}",
                ],
                secondary_blocks=[],
                footer="请回到益语智库处理。",
            )
            text = _build_task_created_feishu_message(
                self.state,
                task_row=task_row,
                recipient_user_id=recipient_user_id,
                actor_name=current_user.fullName,
            )
            self._send_prepared_notification(
                organization_id=str(task_row["organization_id"]),
                message_type="task_created",
                object_type="task",
                object_id=str(task_row["id"]),
                event_type="created",
                recipient_user_id=recipient_user_id,
                title=str(task_row["title"]),
                card=card,
                text=text,
                payload={
                    "changedFields": [],
                    "collaboratorIds": collaborator_ids,
                },
            )

    def _send_task_changed_immediately(
        self,
        *,
        task_row,
        current_user: SessionUser,
        collaborator_ids: list[str],
        changed_fields: list[str],
    ) -> None:
        recipient_ids = self._task_recipient_ids(task_row=task_row, collaborator_ids=collaborator_ids)
        task_id = str(task_row["id"])
        timestamp = now_iso()
        pending_rows = self.state.db.fetchall(
            """
            SELECT *
            FROM org_feishu_notifications
            WHERE object_type = 'task'
              AND object_id = ?
              AND message_type = 'task_content_changed'
              AND delivery_status = 'queued'
            ORDER BY created_at ASC
            """,
            (task_id,),
        )
        pending_by_recipient = {str(row["recipient_user_id"]): row for row in pending_rows}
        for row in pending_rows:
            pending_recipient = str(row["recipient_user_id"])
            if pending_recipient in recipient_ids:
                continue
            self.state.db.execute(
                """
                UPDATE org_feishu_notifications
                SET delivery_status = 'cancelled',
                    delivery_message = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                ("成员已不在最新任务安排中，本次内容提醒已取消。", timestamp, str(row["id"])),
            )
        for recipient_user_id in recipient_ids:
            merged_changed_fields = list(changed_fields)
            pending_row = pending_by_recipient.get(recipient_user_id)
            if pending_row:
                pending_payload = from_json(str(pending_row["payload_json"] or "{}"), {})
                pending_fields = list(pending_payload.get("changedFields") or []) if isinstance(pending_payload, dict) else []
                for item in pending_fields:
                    if item not in merged_changed_fields:
                        merged_changed_fields.append(item)
                self.state.db.execute(
                    """
                    UPDATE org_feishu_notifications
                    SET delivery_status = 'cancelled',
                        delivery_message = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    ("已并入一次即时任务更新提醒。", timestamp, str(pending_row["id"])),
                )
            card = _build_feishu_readonly_card(
                template="orange",
                title=f"{_task_change_notice_heading(merged_changed_fields)}｜{_truncate_plain_text(str(task_row['title']), 30)}",
                headline=str(task_row["title"]),
                core_lines=[
                    f"你的角色：{_task_role_label(task_row, recipient_user_id)}",
                    f"变更人：{current_user.fullName}",
                    f"变更项：{'、'.join(_task_changed_field_labels(merged_changed_fields)) or '任务安排'}",
                ],
                secondary_blocks=[
                    (
                        "最新安排",
                        [
                            f"开始时间：{_task_datetime_text(str(task_row['start_date']) if task_row['start_date'] else None)}",
                            f"截止时间：{_task_datetime_text(str(task_row['due_date']) if task_row['due_date'] else None)}",
                            f"负责人：{_task_person_name_map(self.state, [str(task_row['owner_id']) if task_row['owner_id'] else '']).get(str(task_row['owner_id']) if task_row['owner_id'] else '', '未设置')}",
                        ],
                    ),
                    (
                        "当前协作者",
                        [name for name in _task_person_name_map(self.state, collaborator_ids).values()] or ["无"],
                    ),
                ],
                footer="请回到益语智库查看最新安排。",
            )
            text = _build_task_changed_feishu_message(
                self.state,
                task_row=task_row,
                collaborator_ids=collaborator_ids,
                recipient_user_id=recipient_user_id,
                actor_name=current_user.fullName,
                changed_fields=merged_changed_fields,
            )
            self._send_prepared_notification(
                organization_id=str(task_row["organization_id"]),
                message_type="task_changed",
                object_type="task",
                object_id=task_id,
                event_type="key_fields_changed",
                recipient_user_id=recipient_user_id,
                title=str(task_row["title"]),
                card=card,
                text=text,
                payload={"changedFields": merged_changed_fields},
            )

    def _queue_task_changed(
        self,
        *,
        task_row,
        current_user: SessionUser,
        collaborator_ids: list[str],
        changed_fields: list[str],
    ) -> None:
        recipient_ids = self._task_recipient_ids(task_row=task_row, collaborator_ids=collaborator_ids)
        task_id = str(task_row["id"])
        timestamp = now_iso()
        due_at = (datetime.now() + timedelta(seconds=self.task_change_merge_window_seconds)).replace(microsecond=0).isoformat()
        existing_rows = self.state.db.fetchall(
            """
            SELECT id, recipient_user_id FROM org_feishu_notifications
            WHERE object_type = 'task' AND object_id = ? AND message_type = 'task_content_changed' AND delivery_status = 'queued'
            """,
            (task_id,),
        )
        for row in existing_rows:
            existing_recipient = str(row["recipient_user_id"])
            if existing_recipient in recipient_ids:
                continue
            self.state.db.execute(
                """
                UPDATE org_feishu_notifications
                SET delivery_status = 'cancelled',
                    delivery_message = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                ("成员已不在最新任务安排中，本次提醒已取消。", timestamp, str(row["id"])),
            )
        for recipient_user_id in recipient_ids:
            dedupe_key = f"task_content_changed:{task_id}:{recipient_user_id}"
            payload = {
                "actorName": current_user.fullName,
                "changedFields": changed_fields,
            }
            existing = self.state.db.fetchone(
                """
                SELECT * FROM org_feishu_notifications
                WHERE dedupe_key = ? AND delivery_status = 'queued'
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (dedupe_key,),
            )
            if existing:
                existing_payload = from_json(str(existing["payload_json"] or "{}"), {})
                merged_changed_fields = list(existing_payload.get("changedFields") or []) if isinstance(existing_payload, dict) else []
                for item in changed_fields:
                    if item not in merged_changed_fields:
                        merged_changed_fields.append(item)
                payload["changedFields"] = merged_changed_fields
                self.state.db.execute(
                    """
                    UPDATE org_feishu_notifications
                    SET title = ?,
                        payload_json = ?,
                        due_at = ?,
                        updated_at = ?,
                        delivery_message = ''
                    WHERE id = ?
                    """,
                    (
                        str(task_row["title"]),
                        to_json(payload),
                        due_at,
                        timestamp,
                        str(existing["id"]),
                    ),
                )
                continue
            self.state.db.execute(
                """
                INSERT INTO org_feishu_notifications(
                    id, organization_id, message_type, object_type, object_id, event_type, recipient_user_id,
                    title, payload_json, dedupe_key, delivery_status, delivery_message, due_at, created_at, updated_at
                ) VALUES(?, ?, 'task_content_changed', 'task', ?, 'content_fields_changed', ?, ?, ?, ?, 'queued', '', ?, ?, ?)
                """,
                (
                    new_id("fs_notice"),
                    str(task_row["organization_id"]),
                    task_id,
                    recipient_user_id,
                    str(task_row["title"]),
                    to_json(payload),
                    dedupe_key,
                    due_at,
                    timestamp,
                    timestamp,
                ),
            )

    def _deliver_task_changed_row(self, row) -> None:
        task_id = str(row["object_id"])
        task_row = self.state.db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))
        if not task_row:
            self.state.db.execute(
                """
                UPDATE org_feishu_notifications
                SET delivery_status = 'failed',
                    delivery_message = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                ("任务已不存在，无法继续发送飞书提醒。", now_iso(), str(row["id"])),
            )
            return
        recipient_user_id = str(row["recipient_user_id"])
        collaborator_ids = _task_collaborator_ids(self.state, task_id)
        current_recipient_ids = self._task_recipient_ids(task_row=task_row, collaborator_ids=collaborator_ids)
        if recipient_user_id not in current_recipient_ids:
            self.state.db.execute(
                """
                UPDATE org_feishu_notifications
                SET delivery_status = 'cancelled',
                    delivery_message = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                ("成员已不在最新任务安排中，本次提醒已取消。", now_iso(), str(row["id"])),
            )
            return
        payload = from_json(str(row["payload_json"] or "{}"), {})
        actor_name = str(payload.get("actorName") or "同事") if isinstance(payload, dict) else "同事"
        changed_fields = list(payload.get("changedFields") or []) if isinstance(payload, dict) else []
        event_type = str(row["event_type"] or "content_fields_changed")
        card = _build_feishu_readonly_card(
            template="orange",
            title=f"{_task_change_notice_heading(changed_fields)}｜{_truncate_plain_text(str(task_row['title']), 30)}",
            headline=str(task_row["title"]),
            core_lines=[
                f"你的角色：{_task_role_label(task_row, recipient_user_id)}",
                f"变更人：{actor_name}",
                f"变更项：{'、'.join(_task_changed_field_labels(changed_fields)) or '任务安排'}",
            ],
            secondary_blocks=[
                (
                    "最新安排",
                    [
                        f"开始时间：{_task_datetime_text(str(task_row['start_date']) if task_row['start_date'] else None)}",
                        f"截止时间：{_task_datetime_text(str(task_row['due_date']) if task_row['due_date'] else None)}",
                        f"负责人：{_task_person_name_map(self.state, [str(task_row['owner_id']) if task_row['owner_id'] else '']).get(str(task_row['owner_id']) if task_row['owner_id'] else '', '未设置')}",
                    ],
                ),
                (
                    "当前协作者",
                    [name for name in _task_person_name_map(self.state, collaborator_ids).values()] or ["无"],
                ),
            ],
            footer="请回到益语智库查看最新安排。",
        )
        text = _build_task_changed_feishu_message(
            self.state,
            task_row=task_row,
            collaborator_ids=collaborator_ids,
            recipient_user_id=recipient_user_id,
            actor_name=actor_name,
            changed_fields=changed_fields,
        )
        self._send_prepared_notification(
            notification_id=str(row["id"]),
            organization_id=str(task_row["organization_id"]),
            message_type=str(row["message_type"]),
            object_type="task",
            object_id=task_id,
            event_type=event_type,
            recipient_user_id=recipient_user_id,
            title=str(task_row["title"]),
            card=card,
            text=text,
            dedupe_key=str(row["dedupe_key"]) if row["dedupe_key"] else None,
            payload={"changedFields": changed_fields},
        )

    def _collect_overdue_tasks_for_user(self, *, organization_id: str, user_id: str, reference_time: datetime) -> list[dict[str, str]]:
        rows = self.state.db.fetchall(
            """
            SELECT DISTINCT t.id, t.title, t.due_date
            FROM tasks t
            LEFT JOIN task_collaborators tc ON tc.task_id = t.id
            WHERE t.organization_id = ?
              AND t.progress_status NOT IN ('done', 'rejected')
              AND t.due_date IS NOT NULL
              AND (t.owner_id = ? OR tc.user_id = ?)
            ORDER BY t.due_date ASC, t.created_at ASC
            """,
            (organization_id, user_id, user_id),
        )
        overdue: list[dict[str, str]] = []
        for row in rows:
            due_value = str(row["due_date"]) if row["due_date"] else None
            due_dt = _task_datetime_value(due_value)
            if due_dt is None or due_dt >= reference_time:
                continue
            overdue.append(
                {
                    "id": str(row["id"]),
                    "title": str(row["title"]),
                    "dueText": _task_datetime_text(due_value),
                }
            )
        return overdue

    def _blocking_dedupe_record(self, *, dedupe_key: str) -> FeishuNotificationDispatchRecord | None:
        row = self.state.db.fetchone(
            """
            SELECT * FROM org_feishu_notifications
            WHERE dedupe_key = ? AND delivery_status IN ('queued', 'sending', 'sent_card', 'sent_text_fallback')
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (dedupe_key,),
        )
        return _feishu_dispatch_record(row) if row else None

    def _any_dedupe_record(self, *, dedupe_key: str) -> bool:
        row = self.state.db.fetchone(
            "SELECT id FROM org_feishu_notifications WHERE dedupe_key = ? ORDER BY updated_at DESC LIMIT 1",
            (dedupe_key,),
        )
        return row is not None

    def _send_prepared_notification(
        self,
        *,
        organization_id: str,
        message_type: str,
        object_type: str,
        object_id: str,
        event_type: str,
        recipient_user_id: str,
        title: str,
        card: dict,
        text: str,
        dedupe_key: str | None = None,
        payload: dict[str, object] | None = None,
        notification_id: str | None = None,
    ) -> FeishuNotificationDispatchRecord:
        timestamp = now_iso()
        payload_json = to_json(payload or {})
        card_json = to_json(card)
        if notification_id:
            self.state.db.execute(
                """
                UPDATE org_feishu_notifications
                SET organization_id = ?,
                    message_type = ?,
                    object_type = ?,
                    object_id = ?,
                    event_type = ?,
                    recipient_user_id = ?,
                    title = ?,
                    card_json = ?,
                    text_fallback = ?,
                    payload_json = ?,
                    dedupe_key = ?,
                    delivery_status = 'sending',
                    delivery_channel = '',
                    delivery_message = '',
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    organization_id,
                    message_type,
                    object_type,
                    object_id,
                    event_type,
                    recipient_user_id,
                    title,
                    card_json,
                    text,
                    payload_json,
                    dedupe_key,
                    timestamp,
                    notification_id,
                ),
            )
            row_id = notification_id
        else:
            row_id = new_id("fs_notice")
            self.state.db.execute(
                """
                INSERT INTO org_feishu_notifications(
                    id, organization_id, message_type, object_type, object_id, event_type, recipient_user_id, title,
                    card_json, text_fallback, payload_json, dedupe_key, delivery_status, delivery_channel, delivery_message,
                    due_at, sent_at, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'sending', '', '', NULL, NULL, ?, ?)
                """,
                (
                    row_id,
                    organization_id,
                    message_type,
                    object_type,
                    object_id,
                    event_type,
                    recipient_user_id,
                    title,
                    card_json,
                    text,
                    payload_json,
                    dedupe_key,
                    timestamp,
                    timestamp,
                ),
            )

        recipient_open_id: str | None = None
        delivery_status = "failed"
        delivery_channel = ""
        delivery_message = ""
        tenant_access = _resolve_org_feishu_tenant_access_token(self.state, organization_id=organization_id)
        if not tenant_access:
            delivery_message = "当前组织尚未接通飞书，提醒未发送。"
        else:
            try:
                _app_id, tenant_access_token = tenant_access
                recipient_open_id, match_status, match_error = _resolve_feishu_delivery_target(
                    self.state,
                    organization_id=organization_id,
                    user_id=recipient_user_id,
                    tenant_access_token=tenant_access_token,
                )
                if not recipient_open_id:
                    delivery_status = "skipped_unbound"
                    delivery_message = match_error or ("成员飞书提醒目标未匹配，已跳过发送。" if match_status == "not_found" else "飞书提醒目标校验失败。")
                else:
                    try:
                        _feishu_send_interactive_message(
                            tenant_access_token=tenant_access_token,
                            receive_id_type="open_id",
                            receive_id=recipient_open_id,
                            card=card,
                        )
                        delivery_status = "sent_card"
                        delivery_channel = "interactive"
                        delivery_message = "卡片发送成功。"
                    except Exception as card_exc:
                        card_error = str(card_exc.detail) if isinstance(card_exc, HTTPException) else "飞书卡片发送失败。"
                        try:
                            _feishu_send_text_message(
                                tenant_access_token=tenant_access_token,
                                receive_id_type="open_id",
                                receive_id=recipient_open_id,
                                text=text,
                            )
                            delivery_status = "sent_text_fallback"
                            delivery_channel = "text"
                            delivery_message = f"卡片发送失败，已自动降级为文本：{card_error}"
                        except Exception as text_exc:
                            delivery_status = "failed"
                            delivery_message = str(text_exc.detail) if isinstance(text_exc, HTTPException) else card_error
            except Exception as exc:
                logger.exception(
                    "feishu.notification.send_failed",
                    extra={"message_type": message_type, "object_id": object_id, "recipient_user_id": recipient_user_id},
                )
                delivery_message = str(exc.detail) if isinstance(exc, HTTPException) else "飞书提醒发送失败。"

        sent_at = now_iso() if delivery_status in {"sent_card", "sent_text_fallback"} else None
        self.state.db.execute(
            """
            UPDATE org_feishu_notifications
            SET recipient_open_id = ?,
                delivery_status = ?,
                delivery_channel = ?,
                delivery_message = ?,
                sent_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                recipient_open_id,
                delivery_status,
                delivery_channel,
                delivery_message,
                sent_at,
                now_iso(),
                row_id,
            ),
        )
        if object_type == "task" and event_type in {"created", "key_fields_changed", "content_fields_changed"}:
            payload_obj = payload or {}
            changed_fields = list(payload_obj.get("changedFields") or []) if isinstance(payload_obj, dict) else []
            _record_task_feishu_notification(
                self.state,
                organization_id=organization_id,
                task_id=object_id,
                event_type=cast(Literal["created", "key_fields_changed", "content_fields_changed"], event_type),
                recipient_user_id=recipient_user_id,
                recipient_open_id=recipient_open_id,
                delivery_status="sent" if delivery_status in {"sent_card", "sent_text_fallback"} else "skipped_unbound" if delivery_status == "skipped_unbound" else "failed",
                delivery_message=delivery_message or "发送成功。",
                changed_fields=changed_fields,
            )
        row = self.state.db.fetchone("SELECT * FROM org_feishu_notifications WHERE id = ?", (row_id,))
        assert row is not None
        return _feishu_dispatch_record(row)


def _notify_task_feishu_recipients(
    state: AppState,
    *,
    task_row,
    current_user: SessionUser,
    collaborator_ids: list[str],
    event_type: Literal["created", "key_fields_changed"],
    changed_fields: list[str] | None = None,
) -> None:
    if not state.feishu_notifications:
        state.feishu_notifications = FeishuNotificationService(state)
    state.feishu_notifications.notify_task_change(
        task_row=task_row,
        current_user=current_user,
        collaborator_ids=collaborator_ids,
        event_type=event_type,
        changed_fields=changed_fields,
    )


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


def _feishu_notification_loop(state: AppState) -> None:
    if not state.feishu_notifications:
        state.feishu_notifications = FeishuNotificationService(state)
    while not state.feishu_notification_stop.is_set():
        try:
            state.feishu_notifications.process_due_notifications()
            state.feishu_notifications.process_overdue_digest()
        except Exception:
            logger.exception("feishu.notification.loop_failed")
        state.feishu_notification_stop.wait(20.0)


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
    forced_id: str | None = None,
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
    tag_id = (forced_id or "").strip() or new_id("tag")
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
        startDate=task.startDate,
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
        startDate=str(row["start_date"]) if row["start_date"] else None,
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
    state.feishu_notifications = FeishuNotificationService(state)
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

    @app.on_event("startup")
    def _startup_feishu_notifications() -> None:
        if os.getenv("PYTEST_CURRENT_TEST"):
            return
        if state.feishu_notification_thread and state.feishu_notification_thread.is_alive():
            return
        state.feishu_notification_stop.clear()
        state.feishu_notification_thread = Thread(
            target=_feishu_notification_loop,
            args=(state,),
            name="feishu-notification-loop",
            daemon=True,
        )
        state.feishu_notification_thread.start()

    @app.on_event("startup")
    def _startup_feishu_query_bridge() -> None:
        if os.getenv("PYTEST_CURRENT_TEST"):
            return
        if state.feishu_query_thread and state.feishu_query_thread.is_alive():
            return
        state.feishu_query_stop.clear()
        state.feishu_query_manager = FeishuLongConnectionCoordinator(state)
        state.feishu_query_thread = Thread(
            target=state.feishu_query_manager.run,
            name="feishu-query-coordinator",
            daemon=True,
        )
        state.feishu_query_thread.start()

    @app.on_event("shutdown")
    def _shutdown_feishu_notifications() -> None:
        state.feishu_notification_stop.set()
        if state.feishu_notification_thread and state.feishu_notification_thread.is_alive():
            state.feishu_notification_thread.join(timeout=1.5)

    @app.on_event("shutdown")
    def _shutdown_feishu_query_bridge() -> None:
        state.feishu_query_stop.set()
        if state.feishu_query_thread and state.feishu_query_thread.is_alive():
            state.feishu_query_thread.join(timeout=1.5)

    @app.get("/api/v1/auth/department-options", response_model=list[DepartmentOption])
    def list_department_options() -> list[DepartmentOption]:
        return [DepartmentOption(id=item.id, name=item.name, color=item.color) for item in list_department_catalog()]

    def _ensure_login_allowed(row):
        row = _auto_approve_legacy_pending_account(state, row)
        status_value = str(row["account_status"])
        if status_value == "rejected":
            reason = row["rejected_reason"] or "账号未通过审核，请联系管理员。"
            raise HTTPException(status_code=403, detail=str(reason))
        if status_value == "disabled":
            raise HTTPException(status_code=403, detail="账号已停用")
        return row

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

    @app.post("/api/v1/auth/register", response_model=AuthTokenResponse)
    def register(payload: RegisterPayload) -> AuthTokenResponse:
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
            ) VALUES(?, ?, ?, ?, ?, 'employee', 'approved', ?, NULL, NULL, NULL, '[]', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                DEFAULT_ORG_ID,
                payload.email.lower(),
                payload.fullName,
                hash_password(payload.password),
                timestamp,
                timestamp,
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
        row = state.db.fetchone("SELECT * FROM employee_accounts WHERE id = ?", (user_id,))
        if not row:
            raise HTTPException(status_code=500, detail="注册成功后未找到账号记录")
        session_id = new_id("sess")
        refresh_token = new_id("rt")
        expires_at = (datetime.now() + timedelta(days=30)).replace(microsecond=0).isoformat()
        state.db.execute(
            "INSERT INTO auth_refresh_sessions(id, user_id, refresh_token, created_at, expires_at, revoked_at) VALUES(?, ?, ?, ?, ?, NULL)",
            (session_id, user_id, refresh_token, timestamp, expires_at),
        )
        _log_audit(state, "register_login", actor_user_id=user_id, target_user_id=user_id, detail={"sessionId": session_id})
        return _issue_auth_tokens(row, session_id=session_id, refresh_token=refresh_token)

    @app.post("/api/v1/auth/login", response_model=AuthTokenResponse)
    def login(payload: LoginPayload) -> AuthTokenResponse:
        row = state.db.fetchone("SELECT * FROM employee_accounts WHERE email = ?", (payload.email.lower(),))
        if not row or not verify_password(payload.password, str(row["password_hash"])):
            raise HTTPException(status_code=401, detail="邮箱或密码错误")
        row = _ensure_login_allowed(row)
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
        row = _ensure_login_allowed(row)
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

    @app.patch("/api/v1/auth/me", response_model=SessionUser)
    def update_me(
        payload: UpdateProfilePayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> SessionUser:
        updates: list[str] = []
        params: list[object] = []
        if payload.fullName and payload.fullName.strip():
            updates.append("full_name = ?")
            params.append(payload.fullName.strip())
        if payload.email:
            normalized_email = str(payload.email).strip().lower()
            existing = state.db.fetchone(
                "SELECT id FROM employee_accounts WHERE email = ? AND id != ?",
                (normalized_email, current_user.id),
            )
            if existing:
                raise HTTPException(status_code=409, detail="这个邮箱已被其他账号占用。")
            updates.append("email = ?")
            params.append(normalized_email)
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

    @app.get("/api/v1/me/org-membership", response_model=OrgMembershipSummaryRecord)
    def get_org_membership(
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> OrgMembershipSummaryRecord:
        return _org_membership_summary(state, current_user)

    @app.get("/api/v1/org-integrations/feishu", response_model=OrgFeishuIntegrationRecord)
    def get_org_feishu_integration(
        request: Request,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> OrgFeishuIntegrationRecord:
        return _org_feishu_integration_record(state, current_user, request)

    @app.post("/api/v1/org-integrations/feishu/validate-and-save", response_model=OrgFeishuIntegrationRecord)
    def validate_and_save_org_feishu_integration(
        payload: OrgFeishuIntegrationSavePayload,
        request: Request,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> OrgFeishuIntegrationRecord:
        membership = _org_membership_summary(state, current_user)
        if not membership.hasOrganization or not membership.organizationId:
            raise HTTPException(status_code=400, detail="飞书协作需要组织信息，请先加入组织或创建组织。")

        existing = state.db.fetchone(
            "SELECT * FROM org_feishu_integrations WHERE organization_id = ?",
            (membership.organizationId,),
        )
        resolved_app_id = str(payload.appId).strip() if payload.appId is not None else str(existing["app_id"] or "") if existing else ""

        app_secret = ""
        if existing and existing["app_secret_encrypted"] and not payload.clearAppSecret:
            try:
                app_secret = _org_feishu_decrypt(
                    state,
                    str(existing["app_secret_encrypted"]),
                    str(existing["encryption_nonce"]),
                    membership.organizationId,
                )
            except Exception:
                app_secret = ""
        if payload.appSecret and payload.appSecret.strip():
            app_secret = payload.appSecret.strip()

        if not resolved_app_id:
            _record_org_feishu_audit(
                state,
                current_user,
                app_id="",
                validation_status="failed",
                validation_message="请先填写飞书 App ID。",
            )
            raise HTTPException(status_code=400, detail="请先填写飞书 App ID。")
        if not app_secret:
            _record_org_feishu_audit(
                state,
                current_user,
                app_id=resolved_app_id,
                validation_status="failed",
                validation_message="请先填写飞书 App Secret。",
            )
            raise HTTPException(status_code=400, detail="请先填写飞书 App Secret。")

        try:
            _feishu_fetch_app_access_token(app_id=resolved_app_id, app_secret=app_secret)
        except HTTPException as exc:
            _record_org_feishu_audit(
                state,
                current_user,
                app_id=resolved_app_id,
                validation_status="failed",
                validation_message=str(exc.detail),
            )
            raise

        encrypted_secret, encryption_nonce = _org_feishu_encrypt(state, app_secret, membership.organizationId)
        timestamp = now_iso()
        success_message = "飞书应用验证成功。成员填写飞书手机号后，任务提醒即可自动按手机号匹配发送。"
        state.db.execute(
            """
            INSERT INTO org_feishu_integrations(
                organization_id, app_id, app_secret_encrypted, encryption_nonce, callback_mode, custom_callback_url,
                effective_callback_url, enabled, configured_by, configured_at, updated_at, last_validation_status, last_validation_message
            ) VALUES(?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, 'success', ?)
            ON CONFLICT(organization_id) DO UPDATE SET
                app_id = excluded.app_id,
                app_secret_encrypted = excluded.app_secret_encrypted,
                encryption_nonce = excluded.encryption_nonce,
                callback_mode = excluded.callback_mode,
                custom_callback_url = excluded.custom_callback_url,
                effective_callback_url = excluded.effective_callback_url,
                enabled = excluded.enabled,
                configured_by = excluded.configured_by,
                configured_at = excluded.configured_at,
                updated_at = excluded.updated_at,
                last_validation_status = excluded.last_validation_status,
                last_validation_message = excluded.last_validation_message
            """,
            (
                membership.organizationId,
                resolved_app_id,
                encrypted_secret,
                encryption_nonce,
                "",
                "",
                "",
                current_user.id,
                timestamp,
                timestamp,
                success_message,
            ),
        )
        _record_org_feishu_audit(
            state,
            current_user,
            app_id=resolved_app_id,
            validation_status="success",
            validation_message=success_message,
        )
        return _org_feishu_integration_record(state, current_user, request)

    @app.get("/api/v1/me/feishu-delivery-profile", response_model=FeishuDeliveryProfileRecord)
    def get_feishu_delivery_profile(
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> FeishuDeliveryProfileRecord:
        return _feishu_delivery_profile_record(state, current_user)

    @app.post("/api/v1/me/feishu-delivery-profile", response_model=FeishuDeliveryProfileRecord)
    def save_feishu_delivery_profile(
        payload: FeishuDeliveryProfileSavePayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> FeishuDeliveryProfileRecord:
        normalized_mobile = _normalize_feishu_mobile(payload.mobile)
        state.db.execute(
            "UPDATE employee_accounts SET feishu_mobile = ?, updated_at = ? WHERE id = ?",
            (normalized_mobile, now_iso(), current_user.id),
        )
        membership = _org_membership_summary(state, current_user)
        if membership.hasOrganization and membership.organizationId:
            if not normalized_mobile:
                state.db.execute(
                    """
                    INSERT INTO org_feishu_delivery_targets(
                        organization_id, user_id, mobile, receive_id_type, receive_id, match_status, last_verified_at, last_error, updated_at
                    ) VALUES(?, ?, ?, 'open_id', NULL, ?, NULL, NULL, ?)
                    ON CONFLICT(organization_id, user_id) DO UPDATE SET
                        mobile = excluded.mobile,
                        receive_id = NULL,
                        match_status = excluded.match_status,
                        last_verified_at = NULL,
                        last_error = NULL,
                        updated_at = excluded.updated_at
                    """,
                    (
                        membership.organizationId,
                        current_user.id,
                        normalized_mobile,
                        "missing_mobile",
                        now_iso(),
                    ),
                )
            else:
                try:
                    tenant_access = _resolve_org_feishu_tenant_access_token(
                        state,
                        organization_id=membership.organizationId,
                    )
                    if tenant_access:
                        _, tenant_access_token = tenant_access
                        _resolve_feishu_delivery_target(
                            state,
                            organization_id=membership.organizationId,
                            user_id=current_user.id,
                            tenant_access_token=tenant_access_token,
                        )
                    else:
                        state.db.execute(
                            """
                            INSERT INTO org_feishu_delivery_targets(
                                organization_id, user_id, mobile, receive_id_type, receive_id, match_status, last_verified_at, last_error, updated_at
                            ) VALUES(?, ?, ?, 'open_id', NULL, ?, NULL, NULL, ?)
                            ON CONFLICT(organization_id, user_id) DO UPDATE SET
                                mobile = excluded.mobile,
                                receive_id = NULL,
                                match_status = excluded.match_status,
                                last_verified_at = NULL,
                                last_error = NULL,
                                updated_at = excluded.updated_at
                            """,
                            (
                                membership.organizationId,
                                current_user.id,
                                normalized_mobile,
                                "integration_pending",
                                now_iso(),
                            ),
                        )
                except Exception as exc:
                    error_message = str(exc.detail) if isinstance(exc, HTTPException) else "按手机号校验飞书接收身份失败。"
                    _upsert_org_feishu_delivery_target(
                        state,
                        organization_id=membership.organizationId,
                        user_id=current_user.id,
                        mobile=normalized_mobile,
                        receive_id=None,
                        match_status="failed",
                        last_error=error_message,
                    )
        return _feishu_delivery_profile_record(state, current_user)

    @app.post("/api/v1/me/feishu-notifications/badge-unlock", response_model=FeishuNotificationDispatchRecord)
    def send_badge_unlock_feishu_notification(
        payload: FeishuBadgeNotificationPayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> FeishuNotificationDispatchRecord:
        if not state.feishu_notifications:
            state.feishu_notifications = FeishuNotificationService(state)
        return state.feishu_notifications.notify_badge_unlock(current_user=current_user, payload=payload)

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

    @app.get("/api/v1/integrations/feishu/member-authorization/callback", response_class=HTMLResponse)
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

        organization_id = str(row["organization_id"])
        user_id = str(row["user_id"])
        integration_row = state.db.fetchone(
            "SELECT * FROM org_feishu_integrations WHERE organization_id = ?",
            (organization_id,),
        )
        if not integration_row or not integration_row["enabled"] or not integration_row["app_id"] or not integration_row["app_secret_encrypted"]:
            message = "当前组织尚未完成飞书接入，请先回到软件里补齐组织飞书配置。"
            state.db.execute(
                "UPDATE feishu_binding_relay_sessions SET error_message = ? WHERE state_token = ?",
                (message, state_token),
            )
            return _render_feishu_relay_callback_page("飞书绑定失败", message, success=False)

        try:
            app_secret = _org_feishu_decrypt(
                state,
                str(integration_row["app_secret_encrypted"]),
                str(integration_row["encryption_nonce"]),
                organization_id,
            )
            app_access_token, _ = _feishu_fetch_app_access_token(
                app_id=str(integration_row["app_id"]),
                app_secret=app_secret,
            )
            token_payload = _feishu_exchange_authorization_code(
                app_access_token=app_access_token,
                app_id=str(integration_row["app_id"]),
                app_secret=app_secret,
                code=code.strip(),
            )
            user_access_token = str(token_payload.get("access_token") or "").strip()
            user_info = _feishu_fetch_user_info(user_access_token=user_access_token)
            timestamp = now_iso()
            open_id = str(user_info.get("open_id") or token_payload.get("open_id") or "").strip()
            if not open_id:
                raise HTTPException(status_code=400, detail="飞书没有返回 open_id，无法完成成员授权。")
            state.db.execute(
                """
                INSERT INTO org_feishu_member_authorizations(
                    organization_id, user_id, app_id, open_id, union_id, feishu_user_id, name, en_name,
                    avatar_url, email, tenant_key, authorized_at, last_verified_at, last_error, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
                ON CONFLICT(organization_id, user_id) DO UPDATE SET
                    app_id = excluded.app_id,
                    open_id = excluded.open_id,
                    union_id = excluded.union_id,
                    feishu_user_id = excluded.feishu_user_id,
                    name = excluded.name,
                    en_name = excluded.en_name,
                    avatar_url = excluded.avatar_url,
                    email = excluded.email,
                    tenant_key = excluded.tenant_key,
                    authorized_at = excluded.authorized_at,
                    last_verified_at = excluded.last_verified_at,
                    last_error = NULL,
                    updated_at = excluded.updated_at
                """,
                (
                    organization_id,
                    user_id,
                    str(integration_row["app_id"]),
                    open_id,
                    str(user_info.get("union_id") or token_payload.get("union_id") or "").strip() or None,
                    str(user_info.get("user_id") or token_payload.get("user_id") or "").strip() or None,
                    str(user_info.get("name") or "").strip() or None,
                    str(user_info.get("en_name") or "").strip() or None,
                    str(user_info.get("avatar_url") or "").strip() or None,
                    str(user_info.get("email") or "").strip() or None,
                    str(user_info.get("tenant_key") or token_payload.get("tenant_key") or "").strip() or None,
                    timestamp,
                    timestamp,
                    timestamp,
                ),
            )
            state.db.execute(
                """
                UPDATE feishu_binding_relay_sessions
                SET code = ?, error_message = NULL, authorized_at = ?
                WHERE state_token = ?
                """,
                (code.strip(), timestamp, state_token),
            )
            return _render_feishu_relay_callback_page("成员飞书授权成功", "当前组织成员飞书身份已授权成功，现在回到桌面工作台即可自动刷新授权状态。", success=True)
        except HTTPException as exc:
            message = str(exc.detail)
        except Exception as exc:
            message = str(exc)
        state.db.execute(
            "UPDATE feishu_binding_relay_sessions SET error_message = ? WHERE state_token = ?",
            (message, state_token),
        )
        state.db.execute(
            """
            INSERT INTO org_feishu_member_authorizations(
                organization_id, user_id, app_id, last_error, updated_at
            ) VALUES(?, ?, ?, ?, ?)
            ON CONFLICT(organization_id, user_id) DO UPDATE SET
                app_id = excluded.app_id,
                last_error = excluded.last_error,
                updated_at = excluded.updated_at
            """,
            (
                organization_id,
                user_id,
                str(integration_row["app_id"]) if integration_row and integration_row["app_id"] else "",
                message,
                now_iso(),
            ),
        )
        return _render_feishu_relay_callback_page("飞书绑定失败", message, success=False)

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

    @app.get("/api/v1/mobile/capabilities", response_model=MobileCapabilityRecord)
    def get_mobile_capabilities(
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> MobileCapabilityRecord:
        return _build_mobile_capabilities(state, current_user)

    @app.get("/api/v1/clients/{client_id}/workspace", response_model=MobileWorkspaceCompatResponse)
    def get_mobile_client_workspace(
        client_id: str,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> MobileWorkspaceCompatResponse:
        client_row = _client_row_or_404(state, client_id, current_user.organizationId)
        return _build_workspace_compat_response(state, client_row, current_user.organizationId)

    @app.get("/api/v1/clients/{client_id}/strategic-cockpit", response_model=MobileStrategicCockpitCompatResponse)
    def get_mobile_client_strategic_cockpit(
        client_id: str,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> MobileStrategicCockpitCompatResponse:
        client_row = _client_row_or_404(state, client_id, current_user.organizationId)
        return _build_cockpit_compat_response(state, client_row, current_user.organizationId)

    @app.post("/api/v1/mobile/knowledge-mirror/publish", response_model=CloudKnowledgeMirrorPublishResultRecord)
    def publish_mobile_knowledge_mirror(
        payload: CloudKnowledgeMirrorPublishPayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> CloudKnowledgeMirrorPublishResultRecord:
        if not payload.items:
            raise HTTPException(status_code=400, detail="至少需要一条知识快照。")

        published_at = now_iso()
        client_ids: set[str] = set()
        source_types: set[str] = set()
        published_count = 0

        for item in payload.items:
            client_row = _client_row_or_404(state, item.clientId, current_user.organizationId)
            _upsert_cloud_mirror_item(
                state,
                organization_id=current_user.organizationId,
                client_id=str(client_row["id"]),
                source_type=item.sourceType,
                source_id=item.sourceId,
                snapshot_version=item.snapshotVersion,
                snapshot_hash=item.snapshotHash,
                updated_at=item.updatedAt,
                published_at=item.publishedAt or published_at,
                payload=item.payload,
                evidence_refs=item.evidenceRefs,
            )
            client_ids.add(item.clientId)
            source_types.add(item.sourceType)
            published_count += 1

        _log_audit(
            state,
            "mobile.knowledge_mirror_published",
            actor_user_id=current_user.id,
            target_user_id=None,
            detail={
                "publishedCount": published_count,
                "clientIds": sorted(client_ids),
                "sourceTypes": sorted(source_types),
            },
        )
        return CloudKnowledgeMirrorPublishResultRecord(
            publishedCount=published_count,
            clientIds=sorted(client_ids),
            sourceTypes=sorted(source_types),
            publishedAt=published_at,
        )

    @app.post("/api/v1/event-lines", response_model=EventLineRecord)
    def create_event_line(
        payload: EventLineCreatePayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> EventLineRecord:
        if payload.ownerId:
            _get_user_or_404(state, payload.ownerId)
        timestamp = now_iso()
        event_line_id = (payload.id or "").strip() or new_id("eline")
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

    @app.post("/api/v1/event-lines/import-desktop", response_model=EventLineImportResultRecord)
    def import_desktop_event_lines(
        payload: EventLineImportBatchPayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> EventLineImportResultRecord:
        if current_user.primaryRole != "admin":
            raise HTTPException(status_code=403, detail="只有管理员可以导入本地事件线到云端。")

        results: list[EventLineImportItemResult] = []
        imported = 0
        skipped = 0

        def _resolve_org_user_id(user_id: str | None, fallback: str | None = None) -> str | None:
            normalized = (user_id or "").strip()
            if not normalized:
                return fallback
            row = state.db.fetchone(
                "SELECT id FROM employee_accounts WHERE id = ? AND organization_id = ?",
                (normalized, current_user.organizationId),
            )
            return str(row["id"]) if row else fallback

        def _resolve_department_id(department_id: str | None) -> str | None:
            normalized = (department_id or "").strip()
            if not normalized:
                return None
            row = state.db.fetchone(
                "SELECT id FROM org_departments WHERE id = ? AND organization_id = ?",
                (normalized, current_user.organizationId),
            )
            return str(row["id"]) if row else None

        for item in payload.eventLines:
            existing = state.db.fetchone(
                "SELECT id FROM event_lines WHERE id = ? AND organization_id = ?",
                (item.id, current_user.organizationId),
            )
            if existing:
                skipped += 1
                results.append(
                    EventLineImportItemResult(
                        id=item.id,
                        name=item.name,
                        status="skipped",
                        reason="云端已存在同 ID 事件线",
                        importedActivityCount=0,
                    )
                )
                continue

            owner_id = _resolve_org_user_id(item.ownerId, current_user.id) or current_user.id
            closed_by_user_id = _resolve_org_user_id(item.closedByUserId)
            participant_ids: list[str] = []
            seen_participants: set[str] = set()
            for candidate in [owner_id, *item.participantIds]:
                resolved = _resolve_org_user_id(candidate)
                if not resolved or resolved in seen_participants:
                    continue
                participant_ids.append(resolved)
                seen_participants.add(resolved)
            if not participant_ids:
                participant_ids = [owner_id]

            resolved_department_id = _resolve_department_id(item.primaryDepartmentId)
            client_id = (item.primaryClientId or "").strip() or None
            client_name = (item.primaryClientName or "").strip() or None
            if client_id:
                client_row = _client_row_by_id(state, client_id, current_user.organizationId)
                if client_row:
                    client_name = str(client_row["name"]) if client_row["name"] else client_name

            state.db.execute(
                """
                INSERT INTO event_lines(
                    id, organization_id, name, kind, status, visibility_scope, business_category, stage, summary, intent,
                    current_blocker, recent_decision, next_step, evidence_count, owner_id,
                    primary_client_id, primary_client_name, primary_department_id, participant_ids_json,
                    closed_at, closed_by_user_id, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    current_user.organizationId,
                    item.name.strip(),
                    item.kind,
                    item.status,
                    item.visibilityScope,
                    item.businessCategory,
                    item.stage,
                    item.summary,
                    item.intent,
                    item.currentBlocker,
                    item.recentDecision,
                    item.nextStep,
                    max(int(item.evidenceCount or 0), 0),
                    owner_id,
                    client_id,
                    client_name,
                    resolved_department_id,
                    to_json(participant_ids),
                    item.closedAt,
                    closed_by_user_id,
                    item.createdAt,
                    item.updatedAt,
                ),
            )

            imported_activity_count = 0
            for activity in item.activities:
                existing_activity = state.db.fetchone(
                    "SELECT id FROM event_line_activities WHERE id = ?",
                    (activity.id,),
                )
                if existing_activity:
                    continue
                activity_actor_id = _resolve_org_user_id(activity.actorId)
                state.db.execute(
                    """
                    INSERT INTO event_line_activities(
                        id, event_line_id, source_type, source_id, happened_at, actor_id, title, summary, metadata_json
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        activity.id,
                        item.id,
                        activity.sourceType,
                        activity.sourceId,
                        activity.happenedAt,
                        activity_actor_id,
                        activity.title,
                        activity.summary,
                        to_json(activity.metadata),
                    ),
                )
                imported_activity_count += 1

            imported += 1
            results.append(
                EventLineImportItemResult(
                    id=item.id,
                    name=item.name,
                    status="imported",
                    importedActivityCount=imported_activity_count,
                )
            )

        _log_audit(
            state,
            "event_line.import_desktop",
            actor_user_id=current_user.id,
            target_user_id=None,
            detail={
                "requested": len(payload.eventLines),
                "imported": imported,
                "skipped": skipped,
            },
        )
        return EventLineImportResultRecord(
            requested=len(payload.eventLines),
            imported=imported,
            skipped=skipped,
            updatedAt=now_iso(),
            items=results,
        )

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
        previous_client_id = str(row["primary_client_id"]).strip() if row["primary_client_id"] else None
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
        should_sync_linked_task_client_ids = (
            bool(payload.syncLinkedTaskClientIds)
            and bool(merged["primary_client_id"])
            and merged["primary_client_id"] != previous_client_id
        )
        updated_at = now_iso()
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
                updated_at,
                event_line_id,
            ),
        )
        if should_sync_linked_task_client_ids:
            state.db.execute(
                "UPDATE tasks SET client_id = ?, updated_at = ? WHERE event_line_id = ? AND organization_id = ?",
                (merged["primary_client_id"], updated_at, event_line_id, current_user.organizationId),
            )
            state.db.execute(
                "UPDATE task_attachments SET client_id = ? WHERE event_line_id = ? AND organization_id = ?",
                (merged["primary_client_id"], event_line_id, current_user.organizationId),
            )
            state.db.execute(
                """
                UPDATE consultation_answers
                SET client_id = ?, client_name = ?, updated_at = ?
                WHERE event_line_id = ? AND organization_id = ?
                """,
                (
                    merged["primary_client_id"],
                    merged["primary_client_name"],
                    updated_at,
                    event_line_id,
                    current_user.organizationId,
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

        def _trim_context_block(value: str | None, limit: int = 1800) -> str:
            text = (value or "").strip()
            if not text:
                return ""
            if len(text) <= limit:
                return text
            return f"{text[:limit - 3]}..."

        def _append_context_block(target: list[str], label: str, value: str | None, limit: int = 1800) -> None:
            text = _trim_context_block(value, limit)
            if not text:
                return
            if "\n" in text:
                target.append(f"{label}：\n{text}")
                return
            target.append(f"{label}：{text}")

        context_parts: list[str] = []
        evidence: list[ConsultationEvidenceRecord] = []
        missing_context: list[ConsultationMissingContextRecord] = []
        available_sources: list[str] = []
        missing_sources: list[str] = []
        stale_sources: list[str] = []

        def _append_evidence(
            evidence_type: Literal[
                "workspace",
                "client_dna",
                "event_line",
                "meeting",
                "task",
                "knowledge_surrogate",
                "cockpit",
                "thread_snapshot",
                "task_board",
                "client_name",
            ],
            title: str,
            *,
            snippet: str | None = None,
            updated_at: str | None = None,
            evidence_id: str | None = None,
            source_name: str | None = None,
        ) -> None:
            record = ConsultationEvidenceRecord(
                id=evidence_id or f"{evidence_type}:{len(evidence) + 1}",
                type=evidence_type,
                title=title,
                updatedAt=updated_at,
                snippet=_trim_context_block(snippet, 220) or None,
            )
            evidence.append(record)
            if updated_at:
                try:
                    age_days = (datetime.now() - datetime.fromisoformat(updated_at)).days
                    stale_name = source_name or evidence_type
                    if age_days >= 21 and stale_name not in stale_sources:
                        stale_sources.append(stale_name)
                except ValueError:
                    pass

        def _mark_available(source: str) -> None:
            if source not in available_sources:
                available_sources.append(source)
            if source in missing_sources:
                missing_sources.remove(source)

        def _mark_missing(
            source: Literal[
                "client_dna",
                "workspace",
                "event_line",
                "meeting",
                "person_profile",
                "project_background",
                "strategic_cockpit",
                "knowledge_surrogate",
                "task_board",
            ],
            message: str,
        ) -> None:
            if source not in missing_sources:
                missing_sources.append(source)
            if not any(item.type == source for item in missing_context):
                missing_context.append(ConsultationMissingContextRecord(type=source, message=message))

        normalized_message = payload.message.strip()
        intro_request = any(
            keyword in normalized_message
            for keyword in ("介绍", "简介", "是谁", "做什么", "背景", "全称")
        )

        client_row = _client_row_by_id(state, payload.clientId, current_user.organizationId) if payload.clientId else None
        if not client_row and payload.clientName:
            client_row = state.db.fetchone(
                """
                SELECT *
                FROM clients
                WHERE organization_id = ?
                  AND (name = ? OR alias = ?)
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (current_user.organizationId, payload.clientName, payload.clientName),
            )
        resolved_client_id = str(client_row["id"]) if client_row and client_row["id"] else payload.clientId
        resolved_client_name = _coerce_text(
            payload.clientName or (str(client_row["name"]) if client_row and client_row["name"] else ""),
            "",
        ) or None

        workspace_compat = (
            _build_workspace_compat_response(state, client_row, current_user.organizationId)
            if client_row
            else None
        )
        cockpit_compat = (
            _build_cockpit_compat_response(state, client_row, current_user.organizationId)
            if client_row
            else None
        )
        dna_row = _mirror_latest_row(state, "cloud_client_dna_summaries", current_user.organizationId, resolved_client_id) if resolved_client_id else None
        surrogate_rows = _mirror_rows(state, "cloud_knowledge_surrogates", current_user.organizationId, resolved_client_id, limit=6) if resolved_client_id else []
        event_line_snapshot_row = (
            _mirror_latest_row(state, "cloud_event_line_snapshots", current_user.organizationId, resolved_client_id, payload.eventLineId)
            if resolved_client_id and payload.eventLineId
            else None
        )

        workspace_context_text = payload.workspaceContext
        if not workspace_context_text and workspace_compat and workspace_compat.status != "missing":
            workspace_lines: list[str] = []
            if workspace_compat.goals:
                workspace_lines.append("阶段目标：" + "；".join(item.title for item in workspace_compat.goals[:3]))
            if workspace_compat.meetings:
                workspace_lines.append("最近会议：" + "；".join(
                    _coerce_text(item.summary or item.title, item.title)
                    for item in workspace_compat.meetings[:2]
                ))
            if workspace_compat.latestOpenQuestions:
                workspace_lines.append("开放问题：" + "；".join(
                    _coerce_text(item.summary or item.title, item.title)
                    for item in workspace_compat.latestOpenQuestions[:2]
                ))
            if workspace_compat.relatedTasks:
                workspace_lines.append("相关任务：" + "；".join(item.title for item in workspace_compat.relatedTasks[:3]))
            workspace_context_text = "\n".join(workspace_lines)

        event_line_context_text = payload.eventLineContext
        if not event_line_context_text and payload.eventLineId:
            try:
                el_row = _event_line_row_or_404(state, payload.eventLineId, current_user.organizationId)
                event_line_context_text = "\n".join(
                    part
                    for part in (
                        f"事件线：{_coerce_text(el_row['name'])}" if el_row["name"] else "",
                        f"摘要：{_coerce_text(el_row['summary'])}" if el_row["summary"] else "",
                        f"当前阻塞：{_coerce_text(el_row['current_blocker'])}" if el_row["current_blocker"] else "",
                        f"下一步：{_coerce_text(el_row['next_step'])}" if el_row["next_step"] else "",
                    )
                    if part
                )
            except HTTPException:
                event_line_context_text = None
        if not event_line_context_text and event_line_snapshot_row:
            event_line_payload = _mirror_payload(event_line_snapshot_row)
            event_line_context_text = "\n".join(
                part
                for part in (
                    f"事件线：{_coerce_text(event_line_payload.get('name'))}" if event_line_payload.get("name") else "",
                    f"摘要：{_coerce_text(event_line_payload.get('summary'))}" if event_line_payload.get("summary") else "",
                    f"当前阻塞：{_coerce_text(event_line_payload.get('currentBlocker'))}" if event_line_payload.get("currentBlocker") else "",
                    f"下一步：{_coerce_text(event_line_payload.get('nextStep'))}" if event_line_payload.get("nextStep") else "",
                )
                if part
            )

        cockpit_context_text = None
        if cockpit_compat and cockpit_compat.status != "missing":
            cockpit_lines: list[str] = []
            if cockpit_compat.headline.summary:
                cockpit_lines.append(f"战略 headline：{cockpit_compat.headline.summary}")
            if cockpit_compat.pendingDecisions:
                cockpit_lines.append("待决策：" + "；".join(item.summary for item in cockpit_compat.pendingDecisions[:2]))
            if cockpit_compat.pendingMaterials:
                cockpit_lines.append("待材料：" + "；".join(item.summary for item in cockpit_compat.pendingMaterials[:2]))
            cockpit_context_text = "\n".join(cockpit_lines)

        if resolved_client_name:
            context_parts.append(f"当前客户：{resolved_client_name}")
            _mark_available("client_name")
            _append_evidence("client_name", f"客户：{resolved_client_name}", evidence_id=f"client:{resolved_client_id or resolved_client_name}")
        else:
            _mark_missing("project_background", "当前没有锁定客户，系统无法知道你在问哪一条客户/项目线。")

        if payload.eventLineName and not payload.eventLineId:
            context_parts.append(f"当前事件线：{payload.eventLineName}")
        if payload.taskTitle:
            context_parts.append(f"当前任务：{payload.taskTitle}")
            _append_evidence("task", f"任务：{payload.taskTitle}", snippet=payload.taskContext, evidence_id=f"task:{payload.taskId or payload.taskTitle}")
        if payload.sourceLabels:
            context_parts.append("上下文标签：" + " / ".join(label for label in payload.sourceLabels[:6] if label))
        if event_line_context_text:
            _append_context_block(context_parts, "事件线摘要", event_line_context_text, 1600)
            _mark_available("event_line")
            _append_evidence(
                "event_line",
                payload.eventLineName or "当前事件线",
                snippet=event_line_context_text,
                updated_at=_mirror_updated_at(event_line_snapshot_row),
                evidence_id=f"event-line:{payload.eventLineId or payload.eventLineName or 'current'}",
            )
        elif payload.eventLineId or payload.eventLineName:
            _mark_missing("event_line", "已锁定事件线，但云端没有找到这条事件线的正式摘要。")

        if workspace_context_text:
            _append_context_block(context_parts, "移动端工作台摘要", workspace_context_text, 2200)
            _mark_available("workspace")
            _append_evidence(
                "workspace",
                "客户工作台",
                snippet=workspace_context_text,
                updated_at=workspace_compat.updatedAt if workspace_compat else None,
                source_name="workspace",
            )
        elif resolved_client_id:
            _mark_missing("workspace", "当前云端没有客户工作台快照，因此无法恢复阶段目标、最近会议和开放问题。")

        if workspace_compat and workspace_compat.meetings:
            _mark_available("recent_meetings")
            _append_evidence(
                "meeting",
                workspace_compat.meetings[0].title or "最近会议",
                snippet=workspace_compat.meetings[0].summary or workspace_compat.meetings[0].title,
                updated_at=workspace_compat.meetings[0].updatedAt,
                evidence_id=f"meeting:{workspace_compat.meetings[0].id}",
                source_name="recent_meetings",
            )
        elif resolved_client_id:
            _mark_missing("meeting", "当前云端没有最近会议摘要，无法知道这位客户最近一次沟通发生了什么。")

        if payload.taskBoardContext or payload.taskContext:
            _append_context_block(context_parts, "移动端任务板摘要", payload.taskBoardContext, 1800)
            if payload.taskContext:
                _append_context_block(context_parts, "用户当前任务上下文", payload.taskContext, 1400)
            _mark_available("task_board")
            _append_evidence(
                "task_board",
                "任务板 / 当前任务",
                snippet=payload.taskBoardContext or payload.taskContext,
                evidence_id=f"task-board:{payload.taskId or resolved_client_id or 'current'}",
            )
        elif resolved_client_id:
            _mark_missing("task_board", "当前没有任务板摘要，系统只能看到更薄的客户/任务字段。")

        if payload.missingEventLineHint:
            context_parts.append(f"上下文边界：{payload.missingEventLineHint}")

        if cockpit_context_text:
            _append_context_block(context_parts, "战略 Cockpit 摘要", cockpit_context_text, 1200)
            _mark_available("strategic_cockpit")
            _append_evidence(
                "cockpit",
                "战略 Cockpit",
                snippet=cockpit_context_text,
                updated_at=cockpit_compat.updatedAt if cockpit_compat else None,
                source_name="strategic_cockpit",
            )
        elif resolved_client_id:
            _mark_missing("strategic_cockpit", "当前云端没有战略 cockpit 快照，无法给出正式战略判断层。")

        dna_context = ""
        dna_doc_map: dict[str, str] = {}
        surrogate_overviews: list[str] = []
        if dna_row:
            dna_payload = _mirror_payload(dna_row)
            dna_sections: list[str] = []
            modules = dna_payload.get("modules")
            if isinstance(modules, list):
                for raw_module in modules[:8]:
                    if not isinstance(raw_module, dict):
                        continue
                    module_key = _coerce_text(raw_module.get("moduleKey") or raw_module.get("module_key"))
                    title = _coerce_text(raw_module.get("title"), module_key or "客户资料")
                    text = _coerce_text(raw_module.get("summary") or raw_module.get("text") or raw_module.get("content"))
                    if text:
                        if module_key:
                            dna_doc_map[module_key] = text
                        dna_sections.append(f"【{title}】\n{text[:1800]}")
            summary_text = _coerce_text(dna_payload.get("summary"))
            if summary_text:
                dna_sections.insert(0, f"【客户 DNA 摘要】\n{summary_text[:1800]}")
            if dna_sections:
                dna_context = "\n\n客户知识档案：\n" + "\n---\n".join(dna_sections)
                _mark_available("client_dna")
                _append_evidence(
                    "client_dna",
                    "客户 DNA",
                    snippet=summary_text or dna_sections[0],
                    updated_at=_mirror_updated_at(dna_row),
                    evidence_id=f"dna:{resolved_client_id}",
                    source_name="client_dna",
                )

        if surrogate_rows:
            surrogate_blocks: list[str] = []
            for row in surrogate_rows[:6]:
                surrogate_payload = _mirror_payload(row)
                title = _coerce_text(surrogate_payload.get("title"), "知识代理")
                overview = _coerce_text(
                    surrogate_payload.get("summary")
                    or surrogate_payload.get("overview")
                    or surrogate_payload.get("overviewSummary")
                )
                if overview:
                    surrogate_overviews.append(overview)
                    surrogate_blocks.append(f"【{title}】\n{overview[:1200]}")
            if surrogate_blocks and not dna_context:
                dna_context = "\n\n客户知识档案：\n" + "\n---\n".join(surrogate_blocks)
            if surrogate_blocks:
                _mark_available("knowledge_surrogate")
                _append_evidence(
                    "knowledge_surrogate",
                    "知识代理",
                    snippet=surrogate_overviews[0],
                    updated_at=_mirror_updated_at(surrogate_rows[0]),
                    evidence_id=f"surrogate:{resolved_client_id or 'current'}",
                    source_name="knowledge_surrogate",
                )
        elif resolved_client_id:
            _mark_missing("knowledge_surrogate", "当前云端没有知识代理摘要，无法用客户资料替代原始长文。")

        # ── Desktop knowledge fallback (dev / compatibility only) ──
        resolved_desktop_client_id = resolved_client_id
        if not dna_context and (resolved_client_id or resolved_client_name):
            try:
                import sqlite3 as _sqlite3
                from app.knowledge_store import find_desktop_app_db_path

                desktop_db_path = find_desktop_app_db_path()
                if desktop_db_path is not None:
                    dconn = _sqlite3.connect(str(desktop_db_path))
                    dconn.row_factory = _sqlite3.Row

                    if resolved_desktop_client_id:
                        check = dconn.execute("SELECT id FROM clients WHERE id = ?", (resolved_desktop_client_id,)).fetchone()
                        if not check and resolved_client_name:
                            name_match = dconn.execute(
                                "SELECT id FROM clients WHERE name = ? OR alias = ? LIMIT 1",
                                (resolved_client_name, resolved_client_name),
                            ).fetchone()
                            if name_match:
                                resolved_desktop_client_id = str(name_match["id"])
                    elif resolved_client_name:
                        name_match = dconn.execute(
                            "SELECT id FROM clients WHERE name = ? OR alias = ? LIMIT 1",
                            (resolved_client_name, resolved_client_name),
                        ).fetchone()
                        if name_match:
                            resolved_desktop_client_id = str(name_match["id"])

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
                            title = str(doc["title"] or module or "客户资料")
                            if module:
                                dna_doc_map[module] = text
                            dna_parts.append(f"【{title}】\n{text[:2000]}")

                        surrogates = dconn.execute(
                            """SELECT title, overview_summary, retrieval_summary
                               FROM knowledge_surrogates
                               WHERE client_id = ? AND source_type = 'memory_answer'
                               ORDER BY updated_at DESC LIMIT 10""",
                            (resolved_desktop_client_id,),
                        ).fetchall()
                        surrogate_parts: list[str] = []
                        for s in surrogates:
                            s_title = str(s["title"] or "知识代理")
                            s_overview = str(s["overview_summary"] or "")
                            if s_overview:
                                surrogate_overviews.append(s_overview)
                                surrogate_parts.append(f"【{s_title}】\n{s_overview[:1500]}")
                        all_parts = surrogate_parts + dna_parts
                        if all_parts:
                            dna_context = "\n\n客户知识档案：\n" + "\n---\n".join(all_parts)
                            _mark_available("client_dna")
                            if not any(item.type == "client_dna" for item in evidence):
                                _append_evidence(
                                    "client_dna",
                                    "桌面端客户知识档案",
                                    snippet=all_parts[0],
                                    evidence_id=f"desktop-dna:{resolved_desktop_client_id}",
                                    source_name="client_dna",
                                )
                    dconn.close()
            except Exception as dna_err:
                logger.warning("Desktop knowledge read failed: %s", dna_err)
        if not dna_context and resolved_client_id:
            _mark_missing("client_dna", "当前云端没有客户 DNA 摘要，因此无法准确介绍这位客户的使命、业务和项目类型。")

        knowledge_context = ""
        if not any(item.type == "knowledge_surrogate" for item in evidence):
            try:
                from app.knowledge_store import query_knowledge

                search_client_id = resolved_desktop_client_id or resolved_client_id
                vector_snippets = await asyncio.to_thread(
                    query_knowledge,
                    organization_id=current_user.organizationId,
                    query=payload.message,
                    n_results=20,
                    client_id=search_client_id,
                )
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
                    _mark_available("knowledge_surrogate")
                    _append_evidence(
                        "knowledge_surrogate",
                        "检索知识片段",
                        snippet=vector_snippets[0],
                        evidence_id=f"vector:{resolved_client_id or 'global'}",
                        source_name="knowledge_surrogate",
                    )
            except Exception as vec_err:
                logger.warning("Vector knowledge query failed: %s", vec_err)

        if not knowledge_context and resolved_client_id:
            recent_answers = state.db.fetchall(
                """SELECT question, answer, created_at FROM consultation_answers
                   WHERE organization_id = ? AND client_id = ?
                   ORDER BY created_at DESC LIMIT 5""",
                (current_user.organizationId, resolved_client_id),
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
                    _mark_available("knowledge_surrogate")
                    if not any(item.type == "knowledge_surrogate" for item in evidence):
                        _append_evidence(
                            "knowledge_surrogate",
                            "历史咨询沉淀",
                            snippet=snippets[0],
                            updated_at=str(recent_answers[0]["created_at"]) if recent_answers[0]["created_at"] else None,
                            source_name="knowledge_surrogate",
                        )

        logger.info("Consult context for client %s: workspace=%s dna=%s cockpit=%s knowledge=%s",
            resolved_client_id,
            bool(workspace_context_text),
            bool(dna_context.strip()),
            bool(cockpit_context_text),
            bool(knowledge_context.strip()),
        )

        has_mobile_context = any(
            _trim_context_block(item)
            for item in (
                workspace_context_text,
                event_line_context_text,
                payload.taskBoardContext,
                payload.taskContext,
                cockpit_context_text,
            )
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

        substantive_sources = {
            source
            for source in available_sources
            if source in {
                "workspace",
                "client_dna",
                "knowledge_surrogate",
                "event_line",
                "task_board",
                "strategic_cockpit",
                "recent_meetings",
            }
        }
        if not substantive_sources and not resolved_client_name:
            context_level: Literal["none", "thin", "partial", "rich"] = "none"
        elif {"workspace", "client_dna", "strategic_cockpit"}.issubset(substantive_sources) or (
            {"workspace", "client_dna", "knowledge_surrogate"}.issubset(substantive_sources)
        ):
            context_level = "rich"
        elif len(substantive_sources) >= 2:
            context_level = "partial"
        else:
            context_level = "thin"

        answer_mode: Literal["grounded", "limited_context", "missing_context", "error"]
        if context_level == "none":
            answer_mode = "missing_context"
        elif context_level == "thin":
            answer_mode = "limited_context"
        else:
            answer_mode = "grounded"

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

        known_facts_text = "\n".join(context_parts) if context_parts else "当前没有已知事实。"
        missing_sources_text = "\n".join(f"- {item.message}" for item in missing_context) or "- 当前没有额外缺口。"

        if answer_mode == "missing_context":
            response = (
                "当前还没有锁定足够的客户、事件线或任务上下文。\n\n"
                "已知：只有你刚刚输入的问题本身。\n\n"
                "缺失：需要至少补一项客户、事件线、任务板或工作台资料，系统才能进入业务回答。"
            )
        elif answer_mode == "limited_context":
            system_prompt = (
                "你是益语智库的资深战略顾问，但当前处于 limited_context 模式。\n"
                "你只能根据【已知事实】回答，严禁根据客户名字、组织类型或常识去推断使命、业务、项目领域或合作状态。\n"
                "尤其禁止出现“通常基金会可能……”“大概率……”“一般来说……”这类按名称推断的内容。\n"
                "回答必须严格三段：\n"
                "第一段：当前已知事实。\n"
                "第二段：当前明确缺失的上下文。\n"
                "第三段：为了把回答变准，下一步最该补什么。\n"
                "如果问题是介绍客户，直接说明“当前只知道客户名/任务板/工作台片段，不足以准确介绍其使命与项目”。"
            )
            system_prompt += role_boundary
            system_prompt += "\n\n【已知事实】\n" + known_facts_text
            system_prompt += "\n\n【明确缺失】\n" + missing_sources_text
            if knowledge_context:
                system_prompt += knowledge_context
            user_prompt = normalized_message
        elif has_client_knowledge and intro_request:
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
        elif intro_request and has_mobile_context:
            system_prompt = (
                "你是益语智库的资深战略顾问。系统已经提供了移动端当前工作台、事件线、任务板或任务摘要。"
                "请基于这些已知上下文回答，不要忽略它们，也不要退化成空泛的基金会常识猜测。\n"
                "默认按三段回答：第一段说当前已知的客户/合作定位；第二段说当前推进状态、关键卡点与下一步；"
                "第三段明确还缺哪些信息。\n"
                "如果资料还不够完整，也必须先总结已知事实，再列缺口；禁止只回答“信息不足”“上下文不足”。\n"
                "严禁把未知内容脑补成事实，任何判断都要紧贴已提供的上下文。"
            )
            system_prompt += role_boundary
            if context_parts:
                system_prompt += "\n\n当前上下文：\n" + "\n".join(context_parts)
            if knowledge_context:
                system_prompt += knowledge_context
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
            if has_mobile_context:
                system_prompt += (
                    "\n【移动端上下文使用要求】\n"
                    "- 系统已经提供了移动端工作台、事件线、任务板或任务摘要，必须先提炼这些已知事实再回答\n"
                    "- 如果只能回答一部分，也要先说清已知进展、卡点和下一步，再说明仍缺什么\n"
                    "- 禁止无视已给出的上下文，直接退回空泛建议\n"
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
        if answer_mode != "missing_context":
            chat_payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.35 if answer_mode == "limited_context" else 0.5,
                "top_p": 0.95,
                "max_tokens": 2000 if (has_client_knowledge and intro_request) else (700 if terse_request else 2200),
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

        context_bundle_hash = hashlib.sha256(
            json.dumps(
                {
                    "clientId": resolved_client_id,
                    "eventLineId": payload.eventLineId,
                    "taskId": payload.taskId,
                    "availableSources": sorted(available_sources),
                    "missingSources": sorted(missing_sources),
                    "staleSources": sorted(stale_sources),
                    "message": normalized_message,
                },
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:16]

        state.db.execute(
            """
            INSERT INTO cloud_context_bundle_cache(
                id, organization_id, client_id, event_line_id, snapshot_hash, context_quality_level,
                payload_json, available_sources_json, missing_sources_json, stale_sources_json, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(organization_id, snapshot_hash) DO UPDATE SET
                client_id = excluded.client_id,
                event_line_id = excluded.event_line_id,
                context_quality_level = excluded.context_quality_level,
                payload_json = excluded.payload_json,
                available_sources_json = excluded.available_sources_json,
                missing_sources_json = excluded.missing_sources_json,
                stale_sources_json = excluded.stale_sources_json,
                updated_at = excluded.updated_at
            """,
            (
                new_id("ctxbundle"),
                current_user.organizationId,
                resolved_client_id,
                payload.eventLineId,
                context_bundle_hash,
                context_level,
                to_json(
                    {
                        "clientName": resolved_client_name,
                        "contextParts": context_parts,
                        "workspaceContext": workspace_context_text,
                        "eventLineContext": event_line_context_text,
                        "taskBoardContext": payload.taskBoardContext,
                        "taskContext": payload.taskContext,
                        "cockpitContext": cockpit_context_text,
                    }
                ),
                to_json(sorted(available_sources)),
                to_json(sorted(missing_sources)),
                to_json(sorted(stale_sources)),
                now_iso(),
                now_iso(),
            ),
        )

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
        if answer_mode != "missing_context":
            asyncio.create_task(_ingest_bg())

        return ConsultationChatResponse(
            reply=response,
            model=model_name,
            answerMode=answer_mode,
            contextQuality=ConsultationContextQualityRecord(
                level=context_level,
                availableSources=sorted(available_sources),
                missingSources=sorted(missing_sources),
                staleSources=sorted(stale_sources),
                contextBundleHash=context_bundle_hash,
            ),
            evidence=evidence[:8],
            missingContext=missing_context[:8],
        )

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
        list_id = (payload.id or "").strip() or new_id("list")
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
        return _ensure_task_tag(state, current_user, payload.name, payload.scope, payload.color, payload.id)

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
        owner_id = (payload.ownerId or "").strip() or None
        if owner_id and owner_id in collaborator_ids:
            collaborator_ids = [owner_id] + [item for item in collaborator_ids if item != owner_id]
        elif owner_id:
            collaborator_ids = [owner_id, *[item for item in collaborator_ids if item != owner_id]]
        collaborator_ids = list(dict.fromkeys(collaborator_ids))
        for user_id in ([owner_id] if owner_id else []) + collaborator_ids:
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
        task_id = (payload.id or "").strip() or new_id("task")
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
                id, organization_id, title, description, creator_id, owner_id, start_date, due_date, duration_minutes, client_id, event_line_id, project_module_id, project_flow_id,
                scope_mode, priority, list_id, progress_status, source_type, source_id, business_category, current_blocker, next_action, recent_decision, evidence_count,
                tags_json, tag_ids_json, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'todo', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                current_user.organizationId,
                payload.title,
                payload.description,
                current_user.id,
                owner_id,
                payload.startDate,
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
                    1 if owner_id and user_id == owner_id else 0,
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
        if owner_id:
            _notify_task_feishu_recipients(
                state,
                task_row=task_row,
                current_user=current_user,
                collaborator_ids=collaborator_ids,
                event_type="created",
            )
        return _task_record(state, task_row, current_user.id)

    @app.patch("/api/v1/tasks/{task_id}", response_model=TaskRecord)
    def update_task(
        task_id: str,
        payload: TaskUpdatePayload,
        current_user: SessionUser = Depends(lambda authorization=Header(default=None): _require_auth(app, authorization)),
    ) -> TaskRecord:
        row = _task_row_or_404(state, task_id)
        existing_collaborator_ids = _task_collaborator_ids(state, task_id)
        owner_field_touched = "ownerId" in payload.model_fields_set
        next_owner_id = (payload.ownerId or "").strip() if owner_field_touched and payload.ownerId else None
        if not owner_field_touched:
            next_owner_id = str(row["owner_id"]) if row["owner_id"] else None
        next_collaborator_ids = [item for item in (payload.collaboratorIds if payload.collaboratorIds is not None else existing_collaborator_ids) if item]
        if next_owner_id and next_owner_id in next_collaborator_ids:
            next_collaborator_ids = [next_owner_id] + [item for item in next_collaborator_ids if item != next_owner_id]
        elif next_owner_id:
            next_collaborator_ids = [next_owner_id, *[item for item in next_collaborator_ids if item != next_owner_id]]
        next_collaborator_ids = list(dict.fromkeys(next_collaborator_ids))
        previous_owner_id = str(row["owner_id"]) if row["owner_id"] else None
        previous_start_date = str(row["start_date"]) if row["start_date"] else None
        previous_due_date = str(row["due_date"]) if row["due_date"] else None
        previous_duration_minutes = int(row["duration_minutes"] or 60)
        status_changed = payload.progressStatus is not None and payload.progressStatus != str(row["progress_status"])
        content_changed = any(
            [
                payload.title is not None and payload.title != str(row["title"]),
                payload.description is not None and payload.description != str(row["description"]),
                payload.priority is not None and payload.priority != str(row["priority"]),
                payload.listId is not None and payload.listId != str(row["list_id"]),
            ]
        )
        due_date_changed = (
            (payload.startDate is not None and payload.startDate != (str(row["start_date"]) if row["start_date"] else None))
            or (payload.dueDate is not None and payload.dueDate != row["due_date"])
        )
        owner_changed = owner_field_touched and next_owner_id != previous_owner_id
        _assert_task_edit_permission(state, current_user, row, content_changed, due_date_changed, owner_changed, status_changed)
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
        for user_id in ([next_owner_id] if next_owner_id else []) + next_collaborator_ids:
            _get_user_or_404(state, user_id)
        merged = {
            "title": payload.title or row["title"],
            "description": payload.description if payload.description is not None else row["description"],
            "priority": payload.priority or row["priority"],
            "list_id": payload.listId or row["list_id"],
            "start_date": payload.startDate if payload.startDate is not None else row["start_date"],
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
            SET title = ?, description = ?, priority = ?, list_id = ?, start_date = ?, due_date = ?, duration_minutes = ?, scope_mode = ?, client_id = ?, event_line_id = ?, project_module_id = ?, project_flow_id = ?, progress_status = ?, owner_id = ?, business_category = ?, current_blocker = ?, next_action = ?, recent_decision = ?, evidence_count = ?, tags_json = ?, tag_ids_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                merged["title"],
                merged["description"],
                merged["priority"],
                merged["list_id"],
                merged["start_date"],
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
        if payload.collaboratorIds is not None or owner_field_touched:
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
                        1 if next_owner_id and user_id == next_owner_id else 0,
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
        changed_fields: list[str] = []
        if payload.title is not None and str(merged["title"] or "") != str(row["title"] or ""):
            changed_fields.append("title")
        if payload.description is not None and str(merged["description"] or "") != str(row["description"] or ""):
            changed_fields.append("description")
        if payload.priority is not None and str(merged["priority"] or "") != str(row["priority"] or ""):
            changed_fields.append("priority")
        if payload.listId is not None and str(merged["list_id"] or "") != str(row["list_id"] or ""):
            changed_fields.append("listId")
        if payload.startDate is not None and merged["start_date"] != previous_start_date:
            changed_fields.append("startDate")
        if payload.dueDate is not None and merged["due_date"] != previous_due_date:
            changed_fields.append("dueDate")
        if payload.durationMinutes is not None and int(merged["duration_minutes"] or 60) != previous_duration_minutes:
            changed_fields.append("durationMinutes")
        if next_owner_id != previous_owner_id:
            changed_fields.append("ownerId")
        if payload.collaboratorIds is not None:
            if {item for item in next_collaborator_ids if item} != {item for item in existing_collaborator_ids if item}:
                changed_fields.append("collaboratorIds")
        if changed_fields and next_owner_id:
            _notify_task_feishu_recipients(
                state,
                task_row=updated_row,
                current_user=current_user,
                collaborator_ids=next_collaborator_ids,
                event_type="key_fields_changed",
                changed_fields=changed_fields,
            )
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
            review_id = (payload.id or "").strip() or new_id("review")
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
        if state.feishu_notifications:
            state.feishu_notifications.notify_weekly_review(
                review_id=review_id,
                current_user=current_user,
                payload=payload,
            )
        return _dashboard_for_user(state, current_user, payload.weekLabel)

    return app


app = create_app()
~~~

## `cloud_backend/app/models.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field


AccountStatus = Literal["pending", "approved", "rejected", "disabled"]
PrimaryRole = Literal["admin", "employee"]
Priority = Literal["low", "normal", "high"]
TaskProgressStatus = Literal["inbox", "todo", "doing", "done", "rejected"]
CollaboratorInboxStatus = Literal["pending", "accepted", "returned"]
TaskDueDatePreset = Literal["today", "none"]
TaskListSortMode = Literal["dueDate", "priority", "manual"]
TaskViewMode = Literal["inbox", "list", "calendar", "review"]
PlanLevel = Literal["ceo", "director", "manager", "project"]
ReviewScopeType = Literal["employee", "team", "org"]
ContentDomain = Literal["work", "personal"]
VisibilityScope = Literal["self", "team", "department", "org"]
OrgRoleLevel = Literal["employee", "supervisor", "department_lead", "organization_lead"]
OrgReportingLineType = Literal["business", "administrative"]
OrgTaskEditScope = Literal["self", "manager", "department", "organization"]
OrgTaskControlLevel = Literal["normal", "leader_control", "department_control", "organization_control"]
OrgRuleActorScope = Literal["assignee", "manager", "department_lead", "organization_lead", "creator"]
OrgWorkflowTriggerType = Literal["weekly_followup", "task_created", "meeting_closed", "client_update", "manual"]
ConsultationKnowledgeTarget = Literal["vector_memory", "document_archive"]
ConsultationKnowledgeRequestStatus = Literal["pending", "processing", "completed", "failed"]
SmartInputIntent = Literal["task_schedule", "record_note", "unknown"]


class SessionUser(BaseModel):
    id: str
    organizationId: str
    email: EmailStr
    fullName: str
    primaryRole: PrimaryRole
    accountStatus: AccountStatus


class AuthTokenResponse(BaseModel):
    accessToken: str
    refreshToken: str | None = None
    tokenType: str = "bearer"
    expiresInSeconds: int = 12 * 60 * 60
    user: SessionUser


class RegisterPayload(BaseModel):
    email: EmailStr
    fullName: str
    password: str = Field(min_length=8)
    departmentId: str | None = None
    jobTitle: str | None = None
    managerName: str | None = None
    currentFocus: str | None = None
    isDepartmentLead: bool = False


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordPayload(BaseModel):
    currentPassword: str = Field(min_length=1)
    newPassword: str = Field(min_length=8)


class UpdateProfilePayload(BaseModel):
    fullName: str | None = Field(default=None, min_length=1)
    email: EmailStr | None = None


class AdminResetPasswordPayload(BaseModel):
    newPassword: str = Field(min_length=8)


class RefreshPayload(BaseModel):
    refreshToken: str = Field(min_length=1)


class FeishuBindingRelaySessionCreatePayload(BaseModel):
    state: str = Field(min_length=1)
    expiresAt: str = Field(min_length=1)


class FeishuBindingRelaySessionStatusRecord(BaseModel):
    state: str
    status: Literal["pending", "authorized", "expired", "error"] = "pending"
    expiresAt: str
    authorizedAt: str | None = None
    errorMessage: str | None = None
    code: str | None = None


class OrgMembershipSummaryRecord(BaseModel):
    hasOrganization: bool = False
    organizationId: str | None = None
    organizationName: str | None = None


class OrgFeishuIntegrationAuditRecord(BaseModel):
    id: str
    organizationId: str
    actorUserId: str | None = None
    actorName: str | None = None
    appId: str = ""
    validationStatus: Literal["success", "failed"] = "failed"
    validationMessage: str = ""
    createdAt: str


class OrgFeishuIntegrationRecord(BaseModel):
    organizationId: str | None = None
    organizationName: str | None = None
    appId: str = ""
    enabled: bool = False
    hasAppSecret: bool = False
    configuredBy: str | None = None
    configuredAt: str | None = None
    updatedAt: str
    lastValidationStatus: Literal["idle", "success", "failed"] = "idle"
    lastValidationMessage: str | None = None
    recentAudits: list[OrgFeishuIntegrationAuditRecord] = Field(default_factory=list)


class OrgFeishuIntegrationSavePayload(BaseModel):
    appId: str | None = None
    appSecret: str | None = None
    clearAppSecret: bool = False


class FeishuDeliveryProfileRecord(BaseModel):
    userId: str
    organizationId: str | None = None
    organizationName: str | None = None
    mobile: str = ""
    normalizedMobile: str | None = None
    deliveryStatus: Literal["missing_org", "integration_pending", "missing_mobile", "matched", "not_found", "failed"] = "missing_mobile"
    deliveryStatusLabel: str = "未填写飞书手机号"
    readyForNotifications: bool = False
    receiveId: str | None = None
    lastVerifiedAt: str | None = None
    lastError: str | None = None
    blockedReason: str | None = None


class FeishuDeliveryProfileSavePayload(BaseModel):
    mobile: str | None = None


class FeishuTaskNotificationRecord(BaseModel):
    id: str
    organizationId: str
    taskId: str
    eventType: Literal["created", "key_fields_changed", "content_fields_changed"]
    recipientUserId: str
    recipientOpenId: str | None = None
    deliveryStatus: Literal["sent", "skipped_unbound", "failed"]
    deliveryMessage: str = ""
    changedFields: list[str] = Field(default_factory=list)
    createdAt: str


class FeishuBadgeNotificationPayload(BaseModel):
    badgeId: str = Field(min_length=1)
    badgeName: str = Field(min_length=1)
    categoryName: str = ""
    badgeDescription: str = ""
    xp: int = 0
    unlockedAt: str | None = None


class FeishuNotificationDispatchRecord(BaseModel):
    id: str
    messageType: str
    objectType: str
    objectId: str
    recipientUserId: str
    deliveryStatus: str
    deliveryChannel: str = ""
    deliveryMessage: str = ""
    dedupeKey: str | None = None
    createdAt: str
    updatedAt: str
    sentAt: str | None = None


class RolePayload(BaseModel):
    role: PrimaryRole


class EmployeeDepartmentPayload(BaseModel):
    departmentId: str | None = None


class RejectPayload(BaseModel):
    reason: str = ""


class EmployeeRecord(BaseModel):
    id: str
    email: EmailStr
    fullName: str
    primaryRole: PrimaryRole
    accountStatus: AccountStatus
    departmentId: str | None = None
    departmentName: str | None = None
    jobTitle: str | None = None
    managerName: str | None = None
    currentFocus: str | None = None
    isDepartmentLead: bool = False
    approvedAt: str | None = None
    rejectedReason: str | None = None
    disabledAt: str | None = None
    lastLoginAt: str | None = None
    createdAt: str


class DepartmentOption(BaseModel):
    id: str
    name: str
    color: str


class OrgProfileRecord(BaseModel):
    organizationId: str
    name: str
    annualGoal: str = ""
    annualStrategyYear: str = ""
    annualStrategy: str = ""
    quarterPlans: list["OrgQuarterPlanRecord"] = Field(default_factory=list)
    quarterlyFocus: list[str] = Field(default_factory=list)
    leaderUserId: str | None = None
    managementUserIds: list[str] = Field(default_factory=list)
    updatedAt: str


class OrgQuarterPlanRecord(BaseModel):
    id: str
    year: str = ""
    quarter: Literal["Q1", "Q2", "Q3", "Q4"] = "Q1"
    theme: str = ""
    objective: str = ""
    keyResults: list[str] = Field(default_factory=list)
    keyActions: list[str] = Field(default_factory=list)
    majorRisks: list[str] = Field(default_factory=list)
    updatedAt: str = ""


class OrgDepartmentQuarterPlanRecord(BaseModel):
    year: str = ""
    quarter: Literal["Q1", "Q2", "Q3", "Q4"] = "Q1"
    objective: str = ""
    deliverables: list[str] = Field(default_factory=list)
    successMetrics: list[str] = Field(default_factory=list)
    majorRisks: list[str] = Field(default_factory=list)
    updatedAt: str = ""


class OrgDepartmentRecord(BaseModel):
    id: str
    name: str
    color: str
    leaderUserId: str | None = None
    leaderName: str = ""
    parentDepartmentId: str | None = None
    mission: str = ""
    businessContext: str = ""
    teamContext: str = ""
    quarterPlan: OrgDepartmentQuarterPlanRecord = Field(default_factory=OrgDepartmentQuarterPlanRecord)
    quarterlyFocus: list[str] = Field(default_factory=list)
    collaborationDepartmentIds: list[str] = Field(default_factory=list)
    active: bool = True
    updatedAt: str


class OrgRoleTemplateRecord(BaseModel):
    id: str
    departmentId: str | None = None
    name: str
    level: OrgRoleLevel
    managerRoleId: str | None = None
    isManager: bool = False
    goal: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    shouldAvoid: list[str] = Field(default_factory=list)
    collaborationRoleIds: list[str] = Field(default_factory=list)
    taskEditScope: OrgTaskEditScope = "self"
    canApproveTasks: bool = False
    canReassignTasks: bool = False
    canChangeDeadline: bool = False
    sortOrder: int = 0
    active: bool = True
    updatedAt: str


class OrgEmployeeBindingRecord(BaseModel):
    userId: str
    departmentId: str | None = None
    primaryRoleId: str | None = None
    managerUserId: str | None = None
    isManager: bool = False
    projectRoleLabels: list[str] = Field(default_factory=list)
    currentFocus: str = ""
    taskEditScope: OrgTaskEditScope = "self"
    canApproveTasks: bool = False
    canReassignTasks: bool = False
    canChangeDeadline: bool = False
    updatedAt: str


class OrgReportingLineRecord(BaseModel):
    id: str
    managerUserId: str
    reportUserId: str
    lineType: OrgReportingLineType = "business"
    approvesTasks: bool = False
    canAdjustTasks: bool = False
    canChangeDeadline: bool = False
    canReassignTasks: bool = False
    isCrossDepartmentApprover: bool = False
    active: bool = True
    updatedAt: str


class OrgTaskControlRuleRecord(BaseModel):
    id: str
    name: str
    controlLevel: OrgTaskControlLevel = "normal"
    departmentId: str | None = None
    roleTemplateId: str | None = None
    contentEditableBy: OrgRuleActorScope = "assignee"
    deadlineEditableBy: OrgRuleActorScope = "manager"
    ownerEditableBy: OrgRuleActorScope = "manager"
    cancellableBy: OrgRuleActorScope = "manager"
    requireCollabConfirmation: bool = False
    defaultApproverUserId: str | None = None
    active: bool = True
    updatedAt: str


class OrgRoleProcessTemplateRecord(BaseModel):
    id: str
    roleTemplateId: str | None = None
    name: str
    triggerType: OrgWorkflowTriggerType = "manual"
    triggerCondition: str = ""
    keySteps: list[str] = Field(default_factory=list)
    collaborationStep: str = ""
    approvalStep: str = ""
    outputArtifact: str = ""
    commonBlockers: list[str] = Field(default_factory=list)
    active: bool = True
    updatedAt: str


class OrgFocusItemRecord(BaseModel):
    id: str
    periodKey: str
    title: str
    statement: str = ""
    ownerUserId: str | None = None
    priority: Literal["high", "medium", "low"] = "medium"
    status: Literal["draft", "active", "paused", "done"] = "active"
    evidenceKeywords: list[str] = Field(default_factory=list)
    updatedAt: str


class OrgDepartmentPlanItemRecord(BaseModel):
    id: str
    focusItemId: str | None = None
    title: str
    statement: str = ""
    ownerUserId: str | None = None
    status: Literal["active", "paused", "done", "dropped"] = "active"
    expectedOutput: str = ""
    sortOrder: int = 0
    updatedAt: str


class OrgDepartmentPlanRecord(BaseModel):
    id: str
    departmentId: str | None = None
    weekLabel: str
    ownerUserId: str | None = None
    summary: str = ""
    majorRisks: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    status: Literal["draft", "active", "closed"] = "draft"
    items: list[OrgDepartmentPlanItemRecord] = Field(default_factory=list)
    updatedAt: str


class TaskPlanLinkRecord(BaseModel):
    taskId: str
    departmentPlanItemId: str | None = None
    focusItemId: str | None = None
    linkedBy: Literal["ai", "manager", "rule"] = "ai"
    confidence: float = 0
    updatedAt: str


class SupportRequestRecord(BaseModel):
    id: str
    taskId: str | None = None
    requesterUserId: str
    targetScope: Literal["manager", "department", "organization", "cross_department"]
    targetRefId: str | None = None
    requestType: Literal["resource", "decision", "collaboration", "workload", "clarification"]
    urgency: Literal["high", "medium", "low"] = "medium"
    summary: str
    status: Literal["open", "accepted", "resolved", "dismissed"] = "open"
    resolutionNote: str = ""
    createdAt: str
    updatedAt: str


class ConsultationKnowledgeRequestCreatePayload(BaseModel):
    target: ConsultationKnowledgeTarget
    question: str = ""
    answer: str = Field(min_length=1)
    clientId: str | None = None
    clientName: str | None = None
    taskId: str | None = None
    eventLineId: str | None = None


class ConsultationKnowledgeRequestUpdatePayload(BaseModel):
    status: Literal["processing", "completed", "failed"]
    errorMessage: str = ""
    localDocumentId: str | None = None
    localDocumentPath: str | None = None


class ConsultationKnowledgeRequestRecord(BaseModel):
    id: str
    answerId: str
    organizationId: str
    target: ConsultationKnowledgeTarget
    status: ConsultationKnowledgeRequestStatus = "pending"
    requestedByUserId: str
    requestedByName: str
    clientId: str | None = None
    clientName: str | None = None
    taskId: str | None = None
    eventLineId: str | None = None
    question: str = ""
    answer: str
    errorMessage: str | None = None
    localDocumentId: str | None = None
    localDocumentPath: str | None = None
    completedAt: str | None = None
    createdAt: str
    updatedAt: str


class TaskAttachmentTranscriptionResponse(BaseModel):
    attachmentId: str
    transcript: str
    documentRequest: ConsultationKnowledgeRequestRecord


class ConsultationChatPayload(BaseModel):
    message: str
    clientId: str | None = None
    clientName: str | None = None
    eventLineId: str | None = None
    eventLineName: str | None = None
    taskId: str | None = None
    taskTitle: str | None = None
    taskContext: str | None = None
    workspaceContext: str | None = None
    eventLineContext: str | None = None
    taskBoardContext: str | None = None
    sourceLabels: list[str] = Field(default_factory=list)
    missingEventLineHint: str | None = None


class ConsultationContextQualityRecord(BaseModel):
    level: Literal["none", "thin", "partial", "rich"] = "none"
    availableSources: list[str] = Field(default_factory=list)
    missingSources: list[str] = Field(default_factory=list)
    staleSources: list[str] = Field(default_factory=list)
    contextBundleHash: str | None = None


class ConsultationEvidenceRecord(BaseModel):
    id: str
    type: Literal[
        "workspace",
        "client_dna",
        "event_line",
        "meeting",
        "task",
        "knowledge_surrogate",
        "cockpit",
        "thread_snapshot",
        "task_board",
        "client_name",
    ]
    title: str
    updatedAt: str | None = None
    snippet: str | None = None


class ConsultationMissingContextRecord(BaseModel):
    type: Literal[
        "client_dna",
        "workspace",
        "event_line",
        "meeting",
        "person_profile",
        "project_background",
        "strategic_cockpit",
        "knowledge_surrogate",
        "task_board",
    ]
    message: str


class ConsultationChatResponse(BaseModel):
    reply: str
    model: str | None = None
    answerMode: Literal["grounded", "limited_context", "missing_context", "error"] | None = None
    contextQuality: ConsultationContextQualityRecord | None = None
    evidence: list[ConsultationEvidenceRecord] = Field(default_factory=list)
    missingContext: list[ConsultationMissingContextRecord] = Field(default_factory=list)


class MobileCapabilityRecord(BaseModel):
    consultationChat: bool = True
    clientWorkspace: bool = False
    strategicCockpit: bool = False
    knowledgeMirror: bool = False
    contextBundle: bool = False
    consultationPayloadVersion: str = "v2"
    updatedAt: str


class MobileContextSourceStatusRecord(BaseModel):
    source: str
    available: bool = False
    status: Literal["ready", "partial", "missing", "unavailable"] = "missing"
    detail: str | None = None
    updatedAt: str | None = None


class MobileWorkspaceCompatClientRecord(BaseModel):
    id: str
    name: str
    updatedAt: str | None = None


class MobileWorkspaceCompatItemRecord(BaseModel):
    id: str
    title: str
    summary: str = ""
    subtitle: str = ""
    updatedAt: str | None = None


class MobileWorkspaceCompatTaskRecord(BaseModel):
    id: str
    title: str
    status: str = ""
    clientName: str | None = None
    eventLineName: str | None = None
    nextAction: str | None = None


class MobileWorkspaceKnowledgeStatusRecord(BaseModel):
    status: Literal["ready", "partial", "missing"] = "missing"
    statusLabel: str = "资料未同步"
    summary: str = ""
    missingSources: list[str] = Field(default_factory=list)
    updatedAt: str | None = None


class MobileWorkspaceCompatResponse(BaseModel):
    client: MobileWorkspaceCompatClientRecord
    status: Literal["rich", "partial", "missing"] = "missing"
    updatedAt: str | None = None
    goals: list[MobileWorkspaceCompatItemRecord] = Field(default_factory=list)
    meetings: list[MobileWorkspaceCompatItemRecord] = Field(default_factory=list)
    documentCards: list[MobileWorkspaceCompatItemRecord] = Field(default_factory=list)
    latestOpenQuestions: list[MobileWorkspaceCompatItemRecord] = Field(default_factory=list)
    latestConflicts: list[MobileWorkspaceCompatItemRecord] = Field(default_factory=list)
    relatedTasks: list[MobileWorkspaceCompatTaskRecord] = Field(default_factory=list)
    knowledgeStatus: MobileWorkspaceKnowledgeStatusRecord | None = None
    missingSources: list[str] = Field(default_factory=list)
    sourceAvailability: list[MobileContextSourceStatusRecord] = Field(default_factory=list)


class MobileCockpitHeadlineRecord(BaseModel):
    summary: str = ""


class MobileCockpitSummaryItemRecord(BaseModel):
    summary: str = ""
    updatedAt: str | None = None


class MobileStrategicCockpitCompatResponse(BaseModel):
    clientId: str
    clientName: str
    status: Literal["rich", "partial", "missing"] = "missing"
    updatedAt: str | None = None
    headline: MobileCockpitHeadlineRecord = Field(default_factory=MobileCockpitHeadlineRecord)
    health: list[MobileCockpitSummaryItemRecord] = Field(default_factory=list)
    twoWeekChanges: list[MobileCockpitSummaryItemRecord] = Field(default_factory=list)
    pendingDecisions: list[MobileCockpitSummaryItemRecord] = Field(default_factory=list)
    pendingMaterials: list[MobileCockpitSummaryItemRecord] = Field(default_factory=list)
    missingSources: list[str] = Field(default_factory=list)
    sourceAvailability: list[MobileContextSourceStatusRecord] = Field(default_factory=list)


class CloudKnowledgeMirrorPublishItemPayload(BaseModel):
    clientId: str
    sourceType: Literal[
        "workspace_snapshot",
        "client_dna",
        "event_line_snapshot",
        "meeting_summary",
        "knowledge_surrogate",
        "strategic_cockpit",
    ]
    sourceId: str
    snapshotVersion: int = 1
    snapshotHash: str
    updatedAt: str
    publishedAt: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    evidenceRefs: list[str] = Field(default_factory=list)


class CloudKnowledgeMirrorPublishPayload(BaseModel):
    items: list[CloudKnowledgeMirrorPublishItemPayload] = Field(default_factory=list)


class CloudKnowledgeMirrorPublishResultRecord(BaseModel):
    publishedCount: int = 0
    clientIds: list[str] = Field(default_factory=list)
    sourceTypes: list[str] = Field(default_factory=list)
    publishedAt: str


class SmartTaskDraftRecord(BaseModel):
    title: str | None = None
    dueDate: str | None = None
    endDate: str | None = None
    dueTime: str | None = None
    durationMinutes: int | None = None
    location: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    clientId: str | None = None
    clientName: str | None = None
    eventLineId: str | None = None
    eventLineName: str | None = None
    projectQuery: str | None = None
    eventLineQuery: str | None = None


class SmartTaskDraftResponse(BaseModel):
    transcript: str
    intent: SmartInputIntent = "task_schedule"
    draft: SmartTaskDraftRecord = Field(default_factory=SmartTaskDraftRecord)
    warnings: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class OrgModelProfileRecord(BaseModel):
    organization: OrgProfileRecord
    departments: list[OrgDepartmentRecord] = Field(default_factory=list)
    roles: list[OrgRoleTemplateRecord] = Field(default_factory=list)
    bindings: list[OrgEmployeeBindingRecord] = Field(default_factory=list)
    reportingLines: list[OrgReportingLineRecord] = Field(default_factory=list)
    taskControlRules: list[OrgTaskControlRuleRecord] = Field(default_factory=list)
    roleProcessTemplates: list[OrgRoleProcessTemplateRecord] = Field(default_factory=list)
    focusItems: list[OrgFocusItemRecord] = Field(default_factory=list)
    departmentPlans: list[OrgDepartmentPlanRecord] = Field(default_factory=list)
    updatedAt: str


class TaskOrgBackfillResultRecord(BaseModel):
    organizationId: str
    totalTasks: int
    linkedTasks: int
    createdLinks: int
    updatedLinks: int
    updatedAt: str


class MentionCandidate(BaseModel):
    id: str
    fullName: str
    email: EmailStr
    primaryRole: PrimaryRole
    isSelf: bool = False


class ClientSummaryRecord(BaseModel):
    id: str
    name: str
    alias: str | None = None


class TaskListRecord(BaseModel):
    id: str
    name: str
    color: str
    sortOrder: int = 0
    isDefault: bool = False
    scope: Literal["org", "personal"] = "org"
    archivedAt: str | None = None


class TaskTagRecord(BaseModel):
    id: str
    name: str
    color: str
    scope: Literal["org", "self"] = "org"
    ownerUserId: str | None = None
    createdBy: str | None = None
    updatedAt: str
    archivedAt: str | None = None


class TaskSettingsRecord(BaseModel):
    defaultListId: str | None = None
    defaultPriority: Priority = "normal"
    defaultDueDatePreset: TaskDueDatePreset = "today"
    defaultViewMode: TaskViewMode = "list"
    listSortMode: TaskListSortMode = "manual"
    showCompletedTasks: bool = False
    defaultReviewScope: ContentDomain = "work"
    autoAssignSelf: bool = True
    updatedAt: str


class TaskCollaboratorRecord(BaseModel):
    userId: str
    fullName: str
    email: EmailStr
    orderIndex: int
    isOwner: bool
    inboxStatus: CollaboratorInboxStatus
    returnReason: str | None = None
    handledAt: str | None = None


class TaskActivityRecord(BaseModel):
    id: str
    taskId: str
    actorId: str
    actorName: str
    eventType: str
    payload: dict[str, object]
    createdAt: str


class TaskRecord(BaseModel):
    id: str
    title: str
    description: str
    creatorId: str
    creatorName: str
    listName: str
    listColor: str
    ownerId: str | None = None
    ownerName: str | None = None
    startDate: str | None = None
    dueDate: str | None = None
    durationMinutes: int = 60
    scopeMode: Literal["COLLAB_SHARED", "PERSONAL_ONLY"] = "COLLAB_SHARED"
    clientId: str | None = None
    clientName: str | None = None
    eventLineId: str | None = None
    eventLineName: str | None = None
    projectModuleId: str | None = None
    projectFlowId: str | None = None
    priority: Priority
    listId: str
    progressStatus: TaskProgressStatus
    sourceType: str
    sourceId: str | None = None
    businessCategory: str | None = None
    currentBlocker: str | None = None
    nextAction: str | None = None
    recentDecision: str | None = None
    completionNote: str | None = None
    note: str | None = None
    evidenceCount: int = 0
    tags: list[TaskTagRecord]
    attachments: list["TaskAttachmentRecord"] = Field(default_factory=list)
    collaborators: list[TaskCollaboratorRecord]
    collaborationSummary: dict[str, int]
    viewerInboxStatus: CollaboratorInboxStatus | None = None
    orgContext: "TaskOrgContextRecord | None" = None
    createdAt: str
    updatedAt: str


class TaskAttachmentRecord(BaseModel):
    id: str
    taskId: str
    clientId: str | None = None
    eventLineId: str | None = None
    title: str
    summary: str | None = None
    path: str
    kind: str
    source: str
    mimeType: str | None = None
    sizeBytes: int = 0
    durationSeconds: int = 0
    createdAt: str


class TaskOrgContextRecord(BaseModel):
    departmentId: str | None = None
    roleTemplateId: str | None = None
    controlRuleId: str | None = None
    controlLevel: OrgTaskControlLevel | None = None
    organizationFocusKey: str | None = None
    departmentFocusKey: str | None = None
    focusItemId: str | None = None
    departmentPlanItemId: str | None = None
    isCrossDepartment: bool = False
    approvalState: str | None = None
    blockedAtStep: str | None = None
    needsReview: bool = False


class TaskBoardResponse(BaseModel):
    tasks: list[TaskRecord]
    lists: list[TaskListRecord]
    tags: list[TaskTagRecord] = Field(default_factory=list)
    commonTags: list[str]


class TaskCreatePayload(BaseModel):
    id: str | None = None
    title: str
    description: str = ""
    priority: Priority = "normal"
    listId: str
    startDate: str | None = None
    dueDate: str | None = None
    durationMinutes: int = 60
    scopeMode: Literal["COLLAB_SHARED", "PERSONAL_ONLY"] = "COLLAB_SHARED"
    clientId: str | None = None
    eventLineId: str | None = None
    projectModuleId: str | None = None
    projectFlowId: str | None = None
    collaboratorIds: list[str] = Field(default_factory=list)
    ownerId: str | None = None
    tagIds: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    sourceType: str = "manual"
    sourceId: str | None = None
    businessCategory: str | None = None
    currentBlocker: str | None = None
    nextAction: str | None = None
    recentDecision: str | None = None
    evidenceCount: int | None = None


class TaskUpdatePayload(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: Priority | None = None
    listId: str | None = None
    startDate: str | None = None
    dueDate: str | None = None
    durationMinutes: int | None = None
    scopeMode: Literal["COLLAB_SHARED", "PERSONAL_ONLY"] | None = None
    clientId: str | None = None
    eventLineId: str | None = None
    projectModuleId: str | None = None
    projectFlowId: str | None = None
    progressStatus: TaskProgressStatus | None = None
    collaboratorIds: list[str] | None = None
    ownerId: str | None = None
    tagIds: list[str] | None = None
    tags: list[str] | None = None
    businessCategory: str | None = None
    currentBlocker: str | None = None
    nextAction: str | None = None
    recentDecision: str | None = None
    evidenceCount: int | None = None


class TaskPlanLinkUpsertPayload(BaseModel):
    departmentPlanItemId: str | None = None
    focusItemId: str | None = None
    linkedBy: Literal["ai", "manager", "rule"] = "manager"
    confidence: float = 1.0


class TaskReturnPayload(BaseModel):
    reason: str = Field(min_length=1)


class TaskCompletionReviewPayload(BaseModel):
    reviewNote: str = Field(min_length=1)


class SupportRequestCreatePayload(BaseModel):
    taskId: str | None = None
    eventLineId: str | None = None
    targetScope: Literal["manager", "department", "organization", "cross_department"]
    targetRefId: str | None = None
    requestType: Literal["resource", "decision", "collaboration", "workload", "clarification"]
    urgency: Literal["high", "medium", "low"] = "medium"
    summary: str = Field(min_length=1)


class SupportRequestResolvePayload(BaseModel):
    resolutionNote: str = ""
    status: Literal["accepted", "resolved", "dismissed"] = "resolved"


class EventLineRecord(BaseModel):
    id: str
    name: str
    kind: Literal["project_line", "issue_line", "coordination_line", "case_line", "custom"] = "custom"
    status: Literal["active", "blocked", "paused", "done", "archived"] = "active"
    visibilityScope: Literal["private", "project_public"] = "project_public"
    businessCategory: str | None = None
    stage: str | None = None
    summary: str | None = None
    intent: str | None = None
    currentBlocker: str | None = None
    recentDecision: str | None = None
    nextStep: str | None = None
    evidenceCount: int = 0
    ownerId: str | None = None
    ownerName: str | None = None
    primaryClientId: str | None = None
    primaryClientName: str | None = None
    primaryDepartmentId: str | None = None
    primaryDepartmentName: str | None = None
    participantIds: list[str] = Field(default_factory=list)
    closedAt: str | None = None
    closedByUserId: str | None = None
    createdAt: str
    updatedAt: str


class EventLineActivityRecord(BaseModel):
    id: str
    eventLineId: str
    sourceType: Literal["task_activity", "meeting", "support_request", "review", "attachment", "manual_note"]
    sourceId: str
    happenedAt: str
    actorId: str | None = None
    actorName: str | None = None
    title: str
    summary: str
    metadata: dict[str, object] = Field(default_factory=dict)


class EventLineDetailRecord(BaseModel):
    eventLine: EventLineRecord
    tasks: list[TaskRecord] = Field(default_factory=list)
    activities: list[EventLineActivityRecord] = Field(default_factory=list)


class EventLineReportAttachmentRecord(BaseModel):
    id: str
    taskId: str
    title: str
    kind: str
    mimeType: str | None = None
    sizeBytes: int = 0
    downloadUrl: str
    actorName: str | None = None
    createdAt: str


class EventLineReportSnapshotRecord(BaseModel):
    eventLine: EventLineRecord
    activities: list[EventLineActivityRecord]
    tasks: list[TaskRecord] = Field(default_factory=list)
    attachments: list[EventLineReportAttachmentRecord] = Field(default_factory=list)
    participantNames: list[str] = Field(default_factory=list)
    snapshotAt: str


class EventLineCreatePayload(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1)
    kind: Literal["project_line", "issue_line", "coordination_line", "case_line", "custom"] = "custom"
    status: Literal["active", "blocked", "paused", "done", "archived"] = "active"
    visibilityScope: Literal["private", "project_public"] = "project_public"
    businessCategory: str | None = None
    stage: str | None = None
    summary: str | None = None
    intent: str | None = None
    currentBlocker: str | None = None
    recentDecision: str | None = None
    nextStep: str | None = None
    evidenceCount: int | None = None
    ownerId: str | None = None
    primaryClientId: str | None = None
    primaryDepartmentId: str | None = None
    participantIds: list[str] = Field(default_factory=list)


class EventLineUpdatePayload(BaseModel):
    name: str | None = None
    kind: Literal["project_line", "issue_line", "coordination_line", "case_line", "custom"] | None = None
    status: Literal["active", "blocked", "paused", "done", "archived"] | None = None
    businessCategory: str | None = None
    stage: str | None = None
    summary: str | None = None
    intent: str | None = None
    currentBlocker: str | None = None
    recentDecision: str | None = None
    nextStep: str | None = None
    evidenceCount: int | None = None
    ownerId: str | None = None
    primaryClientId: str | None = None
    primaryDepartmentId: str | None = None
    participantIds: list[str] | None = None
    syncLinkedTaskClientIds: bool | None = None


class EventLineImportActivityPayload(BaseModel):
    id: str = Field(min_length=1)
    sourceType: Literal["task_activity", "meeting", "support_request", "review", "attachment", "manual_note"]
    sourceId: str = Field(min_length=1)
    happenedAt: str = Field(min_length=1)
    actorId: str | None = None
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)


class EventLineImportPayload(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    kind: Literal["project_line", "issue_line", "coordination_line", "case_line", "custom"] = "custom"
    status: Literal["active", "blocked", "paused", "done", "archived"] = "active"
    visibilityScope: Literal["private", "project_public"] = "project_public"
    businessCategory: str | None = None
    stage: str | None = None
    summary: str | None = None
    intent: str | None = None
    currentBlocker: str | None = None
    recentDecision: str | None = None
    nextStep: str | None = None
    evidenceCount: int = 0
    ownerId: str | None = None
    primaryClientId: str | None = None
    primaryClientName: str | None = None
    primaryDepartmentId: str | None = None
    participantIds: list[str] = Field(default_factory=list)
    closedAt: str | None = None
    closedByUserId: str | None = None
    createdAt: str = Field(min_length=1)
    updatedAt: str = Field(min_length=1)
    activities: list[EventLineImportActivityPayload] = Field(default_factory=list)


class EventLineImportBatchPayload(BaseModel):
    eventLines: list[EventLineImportPayload] = Field(default_factory=list)


class EventLineImportItemResult(BaseModel):
    id: str
    name: str
    status: Literal["imported", "skipped"]
    reason: str | None = None
    importedActivityCount: int = 0


class EventLineImportResultRecord(BaseModel):
    requested: int = 0
    imported: int = 0
    skipped: int = 0
    updatedAt: str
    items: list[EventLineImportItemResult] = Field(default_factory=list)


class TaskTagLibraryResponse(BaseModel):
    tags: list[TaskTagRecord]


class TaskListLibraryResponse(BaseModel):
    lists: list[TaskListRecord]


class OrgAiConfigRecord(BaseModel):
    orgId: str
    aiProvider: str
    aiModel: str
    hasApiKey: bool
    configuredBy: str | None = None
    updatedAt: str


class OrgAiConfigUpdatePayload(BaseModel):
    aiProvider: str = Field(min_length=1)
    aiModel: str = ""
    apiKey: str | None = None
    clearApiKey: bool = False


class OrgAiConfigSecretRecord(BaseModel):
    """Only returned to authenticated org members — contains decrypted key."""
    orgId: str
    aiProvider: str
    aiModel: str
    apiKey: str
    updatedAt: str


class TaskNotePayload(BaseModel):
    note: str


class TaskTagMutationPayload(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=20)
    color: str | None = None
    scope: Literal["org", "self"] = "org"
    archived: bool | None = None


class TaskListMutationPayload(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=30)
    color: str = Field(min_length=4, max_length=16)
    isDefault: bool | None = None
    scope: Literal["org", "personal"] | None = None
    archived: bool | None = None
    sortOrder: int | None = None


class TaskSettingsPayload(BaseModel):
    defaultListId: str | None = None
    defaultPriority: Priority | None = None
    defaultDueDatePreset: TaskDueDatePreset | None = None
    defaultViewMode: TaskViewMode | None = None
    listSortMode: TaskListSortMode | None = None
    showCompletedTasks: bool | None = None
    defaultReviewScope: ContentDomain | None = None
    autoAssignSelf: bool | None = None


class ReviewDashboardEvidenceRefRecord(BaseModel):
    sourceType: Literal["task", "meeting", "support_request", "attachment", "clarification", "event_line", "notebook", "event_line_memory"]
    sourceId: str
    title: str
    summary: str | None = None


class ReviewDashboardCardTargetRecord(BaseModel):
    targetType: Literal["event_line", "task_view", "meeting", "support_request", "attachment_group"]
    targetId: str
    targetLabel: str | None = None
    targetFilters: dict[str, object] = Field(default_factory=dict)
    evidenceRefs: list[ReviewDashboardEvidenceRefRecord] = Field(default_factory=list)


class TaskViewFilterSetRecord(BaseModel):
    sourceTypes: list[str] = Field(default_factory=list)
    businessCategories: list[str] = Field(default_factory=list)
    eventLineIds: list[str] = Field(default_factory=list)
    onlyRisky: bool = False
    onlyWithEventLine: bool = False
    needsReview: bool | None = None
    minimumEvidenceCount: int | None = None


class TaskViewDefinitionRecord(BaseModel):
    id: str
    name: str
    kind: Literal["event_line", "risk", "source", "business_category", "custom"] = "custom"
    description: str
    calendarScope: Literal["all", "event_line", "risk", "source", "business_category"] = "all"
    shareability: Literal["private", "org"] = "private"
    sortBy: Literal["updatedAt", "dueDate", "priority", "evidenceCount"] = "updatedAt"
    sortDirection: Literal["asc", "desc"] = "desc"
    visibleFields: list[str] = Field(default_factory=list)
    filterSet: TaskViewFilterSetRecord = Field(default_factory=TaskViewFilterSetRecord)
    builtIn: bool = False
    createdAt: str
    updatedAt: str


class TaskViewPresetRecord(BaseModel):
    key: Literal["event_line", "risk", "source", "business_category"]
    label: str
    description: str
    viewId: str


class TaskViewsResponse(BaseModel):
    views: list[TaskViewDefinitionRecord] = Field(default_factory=list)
    presets: list[TaskViewPresetRecord] = Field(default_factory=list)


class TaskViewMutationPayload(BaseModel):
    name: str
    kind: Literal["event_line", "risk", "source", "business_category", "custom"] = "custom"
    description: str = ""
    calendarScope: Literal["all", "event_line", "risk", "source", "business_category"] = "all"
    shareability: Literal["private", "org"] = "private"
    sortBy: Literal["updatedAt", "dueDate", "priority", "evidenceCount"] = "updatedAt"
    sortDirection: Literal["asc", "desc"] = "desc"
    visibleFields: list[str] = Field(default_factory=list)
    filterSet: TaskViewFilterSetRecord = Field(default_factory=TaskViewFilterSetRecord)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
    organizationCount: int
    employeeCount: int
    taskCount: int


class PlanNodeRecord(BaseModel):
    id: str
    level: PlanLevel
    title: str
    summary: str
    status: str
    ownerUserId: str | None = None
    ownerName: str | None = None
    ownerUnitId: str | None = None
    startsAt: str | None = None
    endsAt: str | None = None


class WeeklyReviewEntryRecord(BaseModel):
    id: str
    userId: str
    userName: str
    weekLabel: str
    workProgress: str = ""
    workBlocker: str = ""
    blockerType: str = ""
    workDirection: str = ""
    nextWeekFocus: str = ""
    supportNeeded: str = ""
    relatedPlanIds: list[str] = Field(default_factory=list)
    workFreeNote: str = ""
    personalGrowthNote: str = ""
    personalPrivateNote: str = ""
    personalVisibility: Literal["self"] = "self"
    submittedAt: str
    createdAt: str
    updatedAt: str


class WeeklyReviewTaskSnapshotRecord(BaseModel):
    title: str
    status: Literal["inbox", "todo", "doing", "done", "rejected"]
    startDate: str | None = None
    dueDate: str | None = None
    createdAt: str
    completionNote: str | None = None
    ownerId: str | None = None
    ownerName: str | None = None
    clientId: str | None = None
    clientName: str | None = None
    eventLineId: str | None = None
    eventLineName: str | None = None
    tags: list[TaskTagRecord] = Field(default_factory=list)
    listName: str
    listColor: str
    orgContext: TaskOrgContextRecord | None = None
    eventLineContext: "WeeklyReviewEventLineContextRecord | None" = None


class WeeklyReviewEventLineContextRecord(BaseModel):
    id: str | None = None
    name: str | None = None
    businessCategory: str | None = None
    stage: str | None = None
    summary: str | None = None
    intent: str | None = None
    currentBlocker: str | None = None
    recentDecision: str | None = None
    nextStep: str | None = None
    evidenceCount: int = 0
    primaryClientId: str | None = None
    primaryClientName: str | None = None


class WeeklyReviewTaskStructuredNoteRecord(BaseModel):
    reflection: str = ""
    lightweightTag: Literal["", "资料不足", "等待他人", "方向不清", "资源不够", "工作过度饱和"] = ""
    planCommitment: str = ""
    progress: str = ""
    completionStatus: Literal["done_on_time", "done_late", "in_progress", "not_done"] = "in_progress"
    departmentPlanId: str | None = None
    departmentPlanAlignment: Literal["aligned", "partial", "misaligned", "unknown"] = "unknown"
    organizationPlanId: str | None = None
    organizationPlanAlignment: Literal["aligned", "partial", "misaligned", "unknown"] = "unknown"
    successReason: str = ""
    successExperience: str = ""
    blockerReason: str = ""
    failureInsight: str = ""
    supportNeeded: str = ""
    nextAction: str = ""


class WeeklyReviewTaskEntryRecord(BaseModel):
    id: str
    reviewId: str | None = None
    taskId: str
    weekLabel: str
    contentDomain: Literal["work", "personal"]
    note: str = ""
    structuredNote: WeeklyReviewTaskStructuredNoteRecord = Field(default_factory=WeeklyReviewTaskStructuredNoteRecord)
    reviewedAt: str | None = None
    taskSnapshot: WeeklyReviewTaskSnapshotRecord


class ManagementSignalCardRecord(BaseModel):
    id: str
    reviewId: str
    userId: str
    userName: str
    weekLabel: str
    contentDomain: ContentDomain
    visibilityScope: VisibilityScope
    eligibleForAggregation: bool
    eligibleForManagerRetrieval: bool
    signals: dict[str, object]
    createdAt: str
    updatedAt: str


class PersonalGrowthCardRecord(BaseModel):
    id: str
    reviewId: str
    userId: str
    contentDomain: Literal["personal"]
    visibilityScope: Literal["self"]
    summary: str
    suggestions: list[str]
    createdAt: str
    updatedAt: str


class ReportActionCardRecord(BaseModel):
    id: str
    actionType: Literal["task", "support_request", "resource_request", "meeting", "one_on_one"]
    title: str
    payload: dict[str, object]
    status: str
    createdAt: str
    target: ReviewDashboardCardTargetRecord | None = None
    evidenceRefs: list[ReviewDashboardEvidenceRefRecord] = Field(default_factory=list)


class ReviewMetricCardRecord(BaseModel):
    key: Literal["timely_completion", "department_alignment", "strategy_alignment", "reflection_capture"]
    label: str
    valueText: str
    numerator: int
    denominator: int
    rate: float
    description: str
    tone: Literal["positive", "neutral", "warning", "risk"]


class HierarchyReportRecord(BaseModel):
    id: str
    scopeType: ReviewScopeType
    scopeRefId: str
    weekLabel: str
    logicMode: str
    headline: str
    summary: str
    summaryMetrics: list[ReviewMetricCardRecord] = Field(default_factory=list)
    focusAreas: list[str]
    supportSignals: list[str]
    suggestedActions: list[str]
    anonymousInsights: list[str]
    sourcePolicy: dict[str, object]
    actions: list[ReportActionCardRecord]
    createdAt: str
    updatedAt: str


class ReviewDashboardResponse(BaseModel):
    currentReview: WeeklyReviewEntryRecord | None = None
    workItems: list[WeeklyReviewTaskEntryRecord] = Field(default_factory=list)
    personalItems: list[WeeklyReviewTaskEntryRecord] = Field(default_factory=list)
    workSignalCard: ManagementSignalCardRecord | None = None
    personalGrowthCard: PersonalGrowthCardRecord | None = None
    teamReport: HierarchyReportRecord | None = None
    orgReport: HierarchyReportRecord | None = None
    plans: list[PlanNodeRecord]


class ReviewDashboardDrillTargetResponse(BaseModel):
    target: ReviewDashboardCardTargetRecord
    eventLineDetail: EventLineDetailRecord | None = None
    tasks: list[TaskRecord] = Field(default_factory=list)
    meetings: list[dict[str, object]] = Field(default_factory=list)
    supportRequests: list["SupportRequestRecord"] = Field(default_factory=list)
    attachments: list[dict[str, object]] = Field(default_factory=list)


class ReviewHistoryEntryRecord(BaseModel):
    weekLabel: str
    submittedAt: str
    workItemCount: int = 0
    personalItemCount: int = 0


class ReviewHistoryResponse(BaseModel):
    items: list[ReviewHistoryEntryRecord] = Field(default_factory=list)


class WeeklyReviewCreatePayload(BaseModel):
    id: str | None = None
    weekLabel: str
    taskEntries: list[dict[str, object]] = Field(default_factory=list)
    workProgress: str = ""
    workBlocker: str = ""
    blockerType: str = ""
    workDirection: str = ""
    nextWeekFocus: str = ""
    supportNeeded: str = ""
    relatedPlanIds: list[str] = Field(default_factory=list)
    workFreeNote: str = ""
    personalGrowthNote: str = ""
    personalPrivateNote: str = ""
~~~

## `cloud_backend/app/security.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return pwd_context.verify(password, password_hash)
    except ValueError:
        return False


def create_access_token(secret_key: str, subject: str, extra: dict[str, Any] | None = None, expires_minutes: int = 720) -> str:
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, secret_key, algorithm=ALGORITHM)


def decode_access_token(secret_key: str, token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, secret_key, algorithms=[ALGORITHM])
    except JWTError as exc:  # pragma: no cover
        raise ValueError("invalid token") from exc

~~~

## `cloud_backend/app/simulation_seed.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal

from app.db import Database, from_json, to_json
from app.security import hash_password


TaskStatus = Literal["todo", "doing", "done"]

SIMULATION_SOURCE_TYPE = "simulation_seed"
DEFAULT_SIM_PASSWORD = "Simulate123!"


@dataclass(frozen=True)
class EmployeeSeed:
    user_id: str
    full_name: str
    email: str
    password: str
    department_id: str
    leader_user_id: str | None
    title: str
    focus: str


@dataclass(frozen=True)
class DepartmentSeed:
    unit_id: str
    name: str
    leader_user_id: str
    leader_password: str
    monthly_dna: str
    focus_tracks: tuple[str, ...]
    blocker_pool: tuple[str, ...]
    support_pool: tuple[str, ...]
    success_pool: tuple[str, ...]
    tag_specs: tuple[tuple[str, str], ...]
    member_specs: tuple[tuple[str, str, str], ...]


DEPARTMENTS: tuple[DepartmentSeed, ...] = (
    DepartmentSeed(
        unit_id="dept_consult_strategy",
        name="咨询策略部",
        leader_user_id="user_qinghua",
        leader_password="Qinghua123!",
        monthly_dna="本月重点是把客户战略诊断、提案叙事和组织DNA对齐成一条稳定交付链，确保每个客户项目都能快速形成判断、方案和复盘。",
        focus_tracks=("客户战略诊断", "提案叙事", "访谈提纲", "组织DNA对齐", "项目节奏校准", "合作方案收束"),
        blocker_pool=("客户输入还不够完整", "跨部门信息口径不一致", "决策边界尚未最终确认", "案例证据不足以支撑最终判断"),
        support_pool=("更明确的优先级判断", "最新的客户背景材料", "部门负责人做一次判断校准", "数据同学补一轮样本验证"),
        success_pool=("前置材料整理得比较完整", "本周判断框架已经统一", "关键人反馈来得及时", "项目目标比上周更聚焦"),
        tag_specs=(("策略判断", "#5B7BFE"), ("方案推进", "#8B5CF6"), ("客户研究", "#10B981")),
        member_specs=(
            ("user_yishuo", "一朔", "方案研究顾问"),
            ("user_sim_suyan", "苏妍", "战略分析师"),
            ("user_sim_chenxi", "晨曦", "项目策划师"),
            ("user_sim_yiming", "奕鸣", "提案顾问"),
        ),
    ),
    DepartmentSeed(
        unit_id="dept_tech_development",
        name="科技发展部",
        leader_user_id="user_jiale",
        leader_password="Jiale123!",
        monthly_dna="本月重点是把周复盘、部门模拟日程、任务链路和系统设置打成一套稳定可用的产品闭环，优先处理可靠性与交互一致性。",
        focus_tracks=("周复盘链路", "部门模拟日程", "任务协作收件箱", "系统设置持久化", "稳定性回归", "权限可见性"),
        blocker_pool=("接口返回字段仍有兼容差异", "页面状态切换后缺少稳定性兜底", "一部分交互还没有做完验证", "历史数据结构和新模型之间还存在缝隙"),
        support_pool=("更清晰的产品优先级", "一轮真实使用后的问题清单", "后端接口约定再锁一次", "测试样本再扩一轮"),
        success_pool=("组件边界拆得更清楚了", "接口约定基本稳定", "回归链路已经能快速复测", "这周问题集中暴露后更容易收敛"),
        tag_specs=(("系统迭代", "#F59E0B"), ("稳定性", "#EF4444"), ("交互优化", "#06B6D4")),
        member_specs=(
            ("user_sim_haoran", "昊然", "前端工程师"),
            ("user_sim_linyue", "林越", "后端工程师"),
            ("user_sim_junhao", "君昊", "全栈工程师"),
            ("user_sim_xinning", "欣宁", "测试工程师"),
        ),
    ),
    DepartmentSeed(
        unit_id="dept_info_data",
        name="信息数据部",
        leader_user_id="user_dazhou",
        leader_password="Dazhou123!",
        monthly_dna="本月重点是把情报抓取、候选清洗、标签治理和数据库维护跑成稳定生产流，确保一线决策能看到及时、可靠、可追踪的信息。",
        focus_tracks=("情报抓取", "候选清洗", "标签治理", "数据库校对", "样本归档", "监测日报"),
        blocker_pool=("源站结构变化导致抓取成本上升", "标签边界还不够稳定", "历史样本质量参差不齐", "一线需求描述还不够标准"),
        support_pool=("技术同学补一个自动化脚本", "更明确的标签治理规则", "业务侧补充优先级说明", "部门负责人拍板一轮异常处理标准"),
        success_pool=("清洗标准已经开始统一", "本周样本覆盖面更广", "热点线索反馈比之前更快", "抓取与复核分工更清楚了"),
        tag_specs=(("情报处理", "#10B981"), ("数据清洗", "#14B8A6"), ("标签治理", "#64748B")),
        member_specs=(
            ("user_sim_ruoxi", "罗茜茜", "情报分析师"),
            ("user_sim_bochen", "柏辰", "数据运营专员"),
            ("user_sim_shuting", "舒婷", "内容标注专员"),
            ("user_sim_jiayi", "嘉译", "监测研究员"),
        ),
    ),
    DepartmentSeed(
        unit_id="dept_customer_service",
        name="客户服务部",
        leader_user_id="user_jianing",
        leader_password="Jianing123!",
        monthly_dna="本月重点是把客户交付、跨部门交接和服务资料回流收成一条更稳的客户服务链路。",
        focus_tracks=("客户交付排期", "反馈收口", "跨部门交接", "客户材料回流", "服务节奏校准", "项目复盘沉淀"),
        blocker_pool=("前序输入交接还不够完整", "客户反馈回流速度偏慢", "服务边界暂时还不够清楚", "资料沉淀动作经常被放到收尾"),
        support_pool=("更清晰的交接清单", "客户反馈同步得更及时", "部门负责人统一一次服务边界", "本周优先级再校准一轮"),
        success_pool=("交接清单更清楚了", "客户反馈来得更及时", "服务节奏和内部排期更贴合", "本周输入输出边界更明确"),
        tag_specs=(("客户交付", "#14B8A6"), ("服务回流", "#06B6D4"), ("协同收口", "#F59E0B")),
        member_specs=(
            ("user_sim_qiuyue", "秋月", "客户访谈研究员"),
            ("user_sim_muyang", "沐阳", "项目资料专员"),
            ("user_sim_zeyu", "泽宇", "客户成功专员"),
            ("user_sim_yaotong", "瑶彤", "服务协调专员"),
        ),
    ),
)


def _iso_timestamp(day: date, hour: int, minute: int = 0) -> str:
    return datetime.combine(day, time(hour=hour, minute=minute)).replace(microsecond=0).isoformat()


def _week_label_for(day: date) -> str:
    iso = day.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _week_days(base_date: date | None) -> list[date]:
    anchor = base_date or date.today()
    start = anchor - timedelta(days=anchor.weekday())
    return [start + timedelta(days=index) for index in range(7)]


def _upsert_employee(
    db: Database,
    *,
    organization_id: str,
    user_id: str,
    full_name: str,
    email: str,
    password: str,
    department_id: str | None = None,
    department_name: str | None = None,
    primary_role: str = "employee",
) -> None:
    timestamp = datetime.now().replace(microsecond=0).isoformat()
    password_hash = hash_password(password)
    existing = db.fetchone("SELECT id FROM employee_accounts WHERE id = ?", (user_id,))
    if existing:
        db.execute(
            """
            UPDATE employee_accounts
            SET organization_id = ?, email = ?, full_name = ?, password_hash = ?, primary_role = ?, account_status = 'approved',
                approved_at = COALESCE(approved_at, ?), approved_by = COALESCE(approved_by, 'user_guyuan'),
                rejected_reason = NULL, disabled_at = NULL, department_id = ?, department_name = ?, updated_at = ?
            WHERE id = ?
            """,
            (organization_id, email.lower(), full_name, password_hash, primary_role, timestamp, department_id, department_name, timestamp, user_id),
        )
    else:
        db.execute(
            """
            INSERT INTO employee_accounts(
                id, organization_id, email, full_name, password_hash, primary_role, account_status,
                approved_at, approved_by, rejected_reason, disabled_at, recent_mentions_json, last_login_at,
                department_id, department_name, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, 'approved', ?, 'user_guyuan', NULL, NULL, '[]', NULL, ?, ?, ?, ?)
            """,
            (user_id, organization_id, email.lower(), full_name, password_hash, primary_role, timestamp, department_id, department_name, timestamp, timestamp),
        )
    db.execute("DELETE FROM employee_role_bindings WHERE user_id = ?", (user_id,))
    db.execute(
        "INSERT OR REPLACE INTO employee_role_bindings(id, user_id, role, created_at) VALUES(?, ?, ?, ?)",
        (f"role_{user_id}", user_id, primary_role, timestamp),
    )
    settings_exists = db.fetchone("SELECT user_id FROM task_settings WHERE user_id = ?", (user_id,))
    if not settings_exists:
        db.execute(
            """
            INSERT INTO task_settings(
                user_id, organization_id, default_list_id, default_priority, default_due_date_preset,
                default_view_mode, list_sort_mode, show_completed_tasks, default_review_scope,
                auto_assign_self, updated_at
            ) VALUES(?, ?, 'list-0', 'normal', 'today', 'list', 'manual', 0, 'work', 1, ?)
            """,
            (user_id, organization_id, timestamp),
        )


def _ensure_tag(db: Database, *, organization_id: str, name: str, color: str) -> dict[str, str]:
    row = db.fetchone(
        "SELECT * FROM task_tag_library WHERE organization_id = ? AND scope = 'org' AND owner_user_id = '' AND name = ?",
        (organization_id, name),
    )
    timestamp = datetime.now().replace(microsecond=0).isoformat()
    if row:
        db.execute(
            "UPDATE task_tag_library SET color = ?, created_by = COALESCE(NULLIF(created_by, ''), '系统'), updated_at = ?, archived_at = NULL WHERE id = ?",
            (color, timestamp, str(row["id"])),
        )
        row = db.fetchone("SELECT * FROM task_tag_library WHERE id = ?", (str(row["id"]),))
    else:
        tag_id = f"tag_sim_{abs(hash(name)) % 1000000:06d}"
        db.execute(
            """
            INSERT INTO task_tag_library(id, organization_id, name, scope, color, owner_user_id, created_by, created_at, updated_at, archived_at)
            VALUES(?, ?, ?, 'org', ?, '', '系统', ?, ?, NULL)
            """,
            (tag_id, organization_id, name, color, timestamp, timestamp),
        )
        row = db.fetchone("SELECT * FROM task_tag_library WHERE id = ?", (tag_id,))
    assert row is not None
    return {
        "id": str(row["id"]),
        "name": str(row["name"]),
        "color": str(row["color"]),
        "scope": str(row["scope"]),
        "ownerUserId": str(row["owner_user_id"]) if row["owner_user_id"] else None,
        "createdBy": str(row["created_by"]) if row["created_by"] else None,
        "updatedAt": str(row["updated_at"] or row["created_at"]),
        "archivedAt": str(row["archived_at"]) if row["archived_at"] else None,
    }


def _status_for(day_index: int, slot_index: int) -> TaskStatus:
    if slot_index == 0:
        return "doing" if day_index == 6 else "done"
    if slot_index == 1:
        if day_index >= 5:
            return "todo" if day_index == 6 else "doing"
        return "doing" if day_index % 3 == 0 else "done"
    return "done" if day_index < 6 else "doing"


def _task_template(
    department: DepartmentSeed,
    employee: EmployeeSeed,
    *,
    project_label: str,
    day_index: int,
    slot_index: int,
) -> tuple[str, str]:
    if department.unit_id == "dept_consult_strategy":
        templates = (
            (f"梳理{project_label}的{employee.focus}关键判断", f"围绕{department.focus_tracks[(day_index + slot_index) % len(department.focus_tracks)]}补齐假设、边界和关键证据。"),
            (f"跟进{project_label}的对齐与反馈收口", "把外部反馈、内部判断和下一步动作合成一个可执行版本。"),
            (f"沉淀{project_label}的日复盘与交付摘要", "把今天形成的判断写成团队可复用的简版方法和输出。"),
        )
    elif department.unit_id == "dept_tech_development":
        templates = (
            (f"推进{project_label}的{employee.focus}", f"处理核心链路、状态同步和可见性细节，保证本周主线继续前进。"),
            (f"对齐{project_label}的边界并回归验证", "跟产品和测试把变更边界重新锁一轮，并记录需要回归的点。"),
            (f"记录{project_label}今日迭代与复盘", "把今天的改动、风险和下一步修正动作补进系统节奏。"),
        )
    elif department.unit_id == "dept_customer_service":
        templates = (
            (f"推进{project_label}的{employee.focus}收口", "把客户反馈、当前交付状态和下一步服务动作对齐成一条清晰节奏。"),
            (f"校准{project_label}的交接边界与输入物", "把跨部门交接需要的输入、负责人和时间点重新锁一轮。"),
            (f"沉淀{project_label}的服务复盘与回流摘要", "把今天的客户反馈、内部响应和资料回流补进服务面板。"),
        )
    else:
        templates = (
            (f"完成{project_label}的{employee.focus}整理", f"更新样本、标签和结构化字段，保证信息可继续流转。"),
            (f"核对{project_label}的异常与来源质量", "把重复、缺字段和低质量样本筛出来，并决定后续处理方式。"),
            (f"沉淀{project_label}的今日洞察与复盘", "把今天新增的信号和处理方法补进部门知识面板。"),
        )
    return templates[slot_index]


def _note_for_task(
    department: DepartmentSeed,
    employee: EmployeeSeed,
    *,
    title: str,
    status: TaskStatus,
    day_index: int,
    slot_index: int,
) -> str:
    success = department.success_pool[(day_index + slot_index) % len(department.success_pool)]
    blocker = department.blocker_pool[(day_index + slot_index) % len(department.blocker_pool)]
    support = department.support_pool[(day_index + slot_index) % len(department.support_pool)]
    if status == "done":
        return (
            f"今天把《{title}》推进到了可交付状态，已经和相关同事对齐了关键口径。"
            f"这项工作推进顺的原因是{success}，所以判断和执行之间的往返明显变少了。"
            f"我会把今天的结论继续沉淀进团队方法，避免下次从头摸索。"
        )
    if status == "doing":
        return (
            f"今天已经完成了《{title}》的主体部分，目前还差最后一轮收口。"
            f"当前主要卡在{blocker}，所以还需要一点时间把细节全部对齐。"
            f"如果能拿到{support}，这项工作下一个工作日就能闭环。"
        )
    return (
        f"今天先把《{title}》的问题范围和资料清单梳理清楚，正式执行还没完全展开。"
        f"主要原因是{blocker}还没有彻底对齐，现在直接往前做反而容易返工。"
        f"接下来最需要的是{support}，拿到后会优先推进。"
    )


def _structured_note_for_task(
    department: DepartmentSeed,
    employee: EmployeeSeed,
    *,
    title: str,
    status: TaskStatus,
    day_index: int,
    slot_index: int,
    department_plan_id: str,
    organization_plan_id: str,
) -> dict[str, object]:
    success = department.success_pool[(day_index + slot_index) % len(department.success_pool)]
    blocker = department.blocker_pool[(day_index + slot_index) % len(department.blocker_pool)]
    support = department.support_pool[(day_index + slot_index) % len(department.support_pool)]
    department_alignment = "aligned" if (day_index + slot_index) % 6 not in {2, 5} else ("partial" if (day_index + slot_index) % 2 == 0 else "misaligned")
    organization_alignment = "aligned" if (day_index + slot_index) % 5 not in {1, 4} else ("partial" if slot_index == 1 else "misaligned")
    if status == "done":
        completion_status = "done_late" if (day_index + slot_index) % 4 == 0 else "done_on_time"
        return {
            "planCommitment": f"本周把《{title}》推进到可交付或可复用状态。",
            "progress": f"已经把《{title}》推进到本周目标状态，并完成了关键对齐。",
            "completionStatus": completion_status,
            "departmentPlanId": department_plan_id,
            "departmentPlanAlignment": department_alignment,
            "organizationPlanId": organization_plan_id,
            "organizationPlanAlignment": organization_alignment,
            "successReason": success,
            "successExperience": f"这件事顺利完成后，比较值得保留的经验是：{success}，以后类似事项也应该先把这一环做扎实。",
            "blockerReason": "",
            "failureInsight": "",
            "supportNeeded": "",
            "nextAction": f"把《{title}》的方法和判断沉淀进{department.name}的周复盘与资料面板。",
        }
    if status == "doing":
        return {
            "planCommitment": f"本周把《{title}》推进到稳定收口阶段。",
            "progress": f"《{title}》已经完成主体推进，目前剩最后一轮收口和校准。",
            "completionStatus": "in_progress",
            "departmentPlanId": department_plan_id,
            "departmentPlanAlignment": department_alignment,
            "organizationPlanId": organization_plan_id,
            "organizationPlanAlignment": organization_alignment,
            "successReason": "",
            "successExperience": "",
            "blockerReason": blocker,
            "failureInsight": f"这项工作还没闭环暴露出一个问题：{blocker}如果不提前处理，后面很容易反复返工。",
            "supportNeeded": support,
            "nextAction": f"下周优先收口《{title}》剩余环节，并减少因为{blocker}带来的往返。",
        }
    return {
        "planCommitment": f"本周把《{title}》至少推进到可执行起点。",
        "progress": f"《{title}》目前还在准备和梳理阶段，尚未进入稳定执行。",
        "completionStatus": "not_done",
        "departmentPlanId": department_plan_id,
        "departmentPlanAlignment": department_alignment,
        "organizationPlanId": organization_plan_id,
        "organizationPlanAlignment": organization_alignment,
        "successReason": "",
        "successExperience": "",
        "blockerReason": blocker,
        "failureInsight": f"本周没按计划完成，最大的心得是：{blocker}如果不先澄清，继续堆动作只会让返工更多。",
        "supportNeeded": support,
        "nextAction": f"先补齐《{title}》需要的前置输入，再决定是否继续推进或调整优先级。",
    }


def _task_snapshot(
    *,
    title: str,
    status: TaskStatus,
    due_date: date,
    created_at: str,
    list_name: str,
    list_color: str,
    tags: list[dict[str, str | None]],
) -> dict[str, object]:
    return {
        "title": title,
        "status": status,
        "dueDate": due_date.isoformat(),
        "createdAt": created_at,
        "tags": tags,
        "listName": list_name,
        "listColor": list_color,
    }


def _employee_summary(
    department: DepartmentSeed,
    employee: EmployeeSeed,
    *,
    task_count: int,
    done_count: int,
    doing_count: int,
    todo_count: int,
) -> dict[str, str]:
    dominant_blocker = department.blocker_pool[(done_count + doing_count + todo_count) % len(department.blocker_pool)]
    support = department.support_pool[(done_count + 2 * doing_count + todo_count) % len(department.support_pool)]
    work_progress = f"本周围绕{employee.focus}累计推进 {task_count} 条工作内容，其中完成 {done_count} 条、持续推进 {doing_count} 条、待启动 {todo_count} 条。"
    work_blocker = f"主要阻碍集中在{dominant_blocker}，一旦信息不齐或边界不清，推进效率就会明显下降。"
    work_direction = f"继续围绕{department.monthly_dna}"
    next_focus = f"下周优先把{employee.focus}相关的关键动作收束成稳定节奏，并减少重复沟通成本。"
    work_free = (
        f"这一周我主要围绕{employee.title}的职责推进了{employee.focus}相关事项。"
        f"从结果看，能够往前走的部分通常都依赖于{department.success_pool[0]}；"
        f"推进慢的部分则多半卡在{dominant_blocker}。"
        f"下周会优先收口最影响节奏的两个问题，并把可复制的方法沉淀下来。"
    )
    personal_growth = f"这周我对{employee.focus}的判断更稳了一些，也更清楚什么信息要提前准备。"
    return {
        "workProgress": work_progress,
        "workBlocker": work_blocker,
        "blockerType": "协作卡住" if "对齐" in dominant_blocker or "口径" in dominant_blocker else ("信息不足" if "资料" in dominant_blocker or "输入" in dominant_blocker else "资源不足"),
        "workDirection": work_direction,
        "nextWeekFocus": next_focus,
        "supportNeeded": support,
        "workFreeNote": work_free,
        "personalGrowthNote": personal_growth,
        "personalPrivateNote": "",
    }


def _all_employee_profiles() -> list[EmployeeSeed]:
    employees: list[EmployeeSeed] = []
    leader_profiles = {
        "user_qinghua": ("庆华", "qinghua@yiyu-system.com"),
        "user_jiale": ("佳乐", "jiale@yiyu-system.com"),
        "user_dazhou": ("大周", "dazhou@yiyu-system.com"),
        "user_jianing": ("嘉宁", "jianing@yiyu-system.com"),
    }
    for department in DEPARTMENTS:
        leader_name, leader_email = leader_profiles[department.leader_user_id]
        leader_title = f"{department.name}负责人"
        employees.append(
            EmployeeSeed(
                user_id=department.leader_user_id,
                full_name=leader_name,
                email=leader_email,
                password=department.leader_password,
                department_id=department.unit_id,
                leader_user_id="user_guyuan",
                title=leader_title,
                focus=department.focus_tracks[0],
            )
        )
        for index, (user_id, full_name, title) in enumerate(department.member_specs):
            email = (
                "jianing@yiyu-system.com"
                if user_id == "user_jianing"
                else ("yishuo@yiyu-system.com" if user_id == "user_yishuo" else f"{user_id.replace('user_', '')}@yiyu-system.com")
            )
            password = (
                "Jianing123!" if user_id == "user_jianing" else ("Yishuo123!" if user_id == "user_yishuo" else DEFAULT_SIM_PASSWORD)
            )
            employees.append(
                EmployeeSeed(
                    user_id=user_id,
                    full_name=full_name,
                    email=email,
                    password=password,
                    department_id=department.unit_id,
                    leader_user_id=department.leader_user_id,
                    title=title,
                    focus=department.focus_tracks[(index + 1) % len(department.focus_tracks)],
                )
            )
    return employees


def seed_simulated_review_org(
    db: Database,
    *,
    organization_id: str,
    base_date: date | None = None,
    ceo_user_id: str = "user_guyuan",
    ceo_name: str = "顾源源",
    reset: bool = True,
) -> dict[str, object]:
    week_days = _week_days(base_date)
    week_label = _week_label_for(week_days[-1])
    timestamp = datetime.now().replace(microsecond=0).isoformat()
    employee_profiles = _all_employee_profiles()
    sim_user_ids = [item.user_id for item in employee_profiles]

    if reset:
        review_ids = [
            str(row["id"])
            for row in db.fetchall(
                f"SELECT id FROM weekly_review_entries WHERE user_id IN ({','.join('?' for _ in sim_user_ids)}) AND week_label = ?",
                (*sim_user_ids, week_label),
            )
        ]
        if review_ids:
            db.execute(
                f"DELETE FROM weekly_review_entries WHERE id IN ({','.join('?' for _ in review_ids)})",
                tuple(review_ids),
            )
        db.execute(
            "DELETE FROM aggregated_scope_reports WHERE week_label = ? AND (scope_ref_id = ? OR scope_ref_id IN (?, ?, ?))",
            (week_label, organization_id, "user_qinghua", "user_jiale", "user_dazhou"),
        )
        db.execute(
            f"DELETE FROM tasks WHERE source_type = ? AND creator_id IN ({','.join('?' for _ in sim_user_ids)})",
            (SIMULATION_SOURCE_TYPE, *sim_user_ids),
        )

    db.execute(
        "UPDATE org_units SET leader_user_id = ?, updated_at = ? WHERE id = 'unit_org'",
        (ceo_user_id, timestamp),
    )
    db.execute(
        """
        INSERT OR IGNORE INTO org_units(id, organization_id, parent_id, name, unit_type, leader_user_id, created_at, updated_at)
        VALUES('unit_org', ?, NULL, '益语智库', 'organization', ?, ?, ?)
        """,
        (organization_id, ceo_user_id, timestamp, timestamp),
    )

    for profile in employee_profiles:
        _upsert_employee(
            db,
            organization_id=organization_id,
            user_id=profile.user_id,
            full_name=profile.full_name,
            email=profile.email,
            password=profile.password,
            department_id=profile.department_id,
            department_name=next(item.name for item in DEPARTMENTS if item.unit_id == profile.department_id),
            primary_role="employee",
        )

    db.execute(
        f"DELETE FROM reporting_lines WHERE organization_id = ? AND (manager_user_id IN ({','.join('?' for _ in (*sim_user_ids, ceo_user_id, 'user_admin'))}) OR report_user_id IN ({','.join('?' for _ in sim_user_ids)}))",
        (organization_id, *sim_user_ids, ceo_user_id, "user_admin", *sim_user_ids),
    )

    plan_ids: dict[str, str] = {"org": f"plan_org_{week_label.replace('-', '_').lower()}"}
    db.execute(
        """
        INSERT OR REPLACE INTO plan_nodes(
            id, organization_id, owner_user_id, owner_unit_id, level, title, summary, status, starts_at, ends_at, created_at, updated_at
        ) VALUES(?, ?, ?, 'unit_org', 'ceo', ?, ?, 'active', ?, ?, ?, ?)
        """,
        (
            plan_ids["org"],
            organization_id,
            ceo_user_id,
            f"{week_label} 机构主线",
            "本周重点是通过真实任务和复盘看清各部门推进节奏、阻碍来源和下周支持重点。",
            week_days[0].isoformat(),
            week_days[-1].isoformat(),
            timestamp,
            timestamp,
        ),
    )

    tags_by_name: dict[str, dict[str, str | None]] = {}
    task_lists = {
        str(row["id"]): {"name": str(row["name"]), "color": str(row["color"])}
        for row in db.fetchall("SELECT id, name, color FROM task_lists WHERE organization_id = ?", (organization_id,))
    }
    list_cycle = tuple(task_lists.keys()) or ("list-0",)

    for department_index, department in enumerate(DEPARTMENTS):
        leader_name = next(item.full_name for item in employee_profiles if item.user_id == department.leader_user_id)
        db.execute(
            """
            INSERT OR REPLACE INTO org_units(id, organization_id, parent_id, name, unit_type, leader_user_id, created_at, updated_at)
            VALUES(?, ?, 'unit_org', ?, 'department', ?, ?, ?)
            """,
            (department.unit_id, organization_id, department.name, department.leader_user_id, timestamp, timestamp),
        )
        plan_id = f"plan_{department.unit_id}_{week_label.replace('-', '_').lower()}"
        plan_ids[department.unit_id] = plan_id
        db.execute(
            """
            INSERT OR REPLACE INTO plan_nodes(
                id, organization_id, owner_user_id, owner_unit_id, level, title, summary, status, starts_at, ends_at, created_at, updated_at
            ) VALUES(?, ?, ?, ?, 'director', ?, ?, 'active', ?, ?, ?, ?)
            """,
            (
                plan_id,
                organization_id,
                department.leader_user_id,
                department.unit_id,
                f"{department.name} 本周主线",
                department.monthly_dna,
                week_days[0].isoformat(),
                week_days[-1].isoformat(),
                timestamp,
                timestamp,
            ),
        )
        db.execute(
            """
            INSERT INTO reporting_lines(id, organization_id, manager_user_id, report_user_id, relationship_type, effective_from, effective_to, created_at)
            VALUES(?, ?, ?, ?, 'direct', ?, NULL, ?)
            """,
            (f"line_{ceo_user_id}_{department.leader_user_id}", organization_id, ceo_user_id, department.leader_user_id, week_days[0].isoformat(), timestamp),
        )
        for name, color in department.tag_specs:
            tags_by_name[name] = _ensure_tag(db, organization_id=organization_id, name=name, color=color)
        tags_by_name.setdefault("周复盘", _ensure_tag(db, organization_id=organization_id, name="周复盘", color="#EC4899"))
        tags_by_name.setdefault("跨部门协同", _ensure_tag(db, organization_id=organization_id, name="跨部门协同", color="#5B7BFE"))

        member_profiles = [item for item in employee_profiles if item.department_id == department.unit_id and item.user_id != department.leader_user_id]
        for member in member_profiles:
            db.execute(
                """
                INSERT INTO reporting_lines(id, organization_id, manager_user_id, report_user_id, relationship_type, effective_from, effective_to, created_at)
                VALUES(?, ?, ?, ?, 'direct', ?, NULL, ?)
                """,
                (f"line_{department.leader_user_id}_{member.user_id}", organization_id, department.leader_user_id, member.user_id, week_days[0].isoformat(), timestamp),
            )

        # make sure leaders remain visible in existing organization snapshots
        _upsert_employee(
            db,
            organization_id=organization_id,
            user_id=department.leader_user_id,
            full_name=leader_name,
            email=next(item.email for item in employee_profiles if item.user_id == department.leader_user_id),
            password=department.leader_password,
            department_id=department.unit_id,
            department_name=department.name,
            primary_role="employee",
        )

    total_tasks = 0
    total_reviews = 0
    total_review_items = 0
    created_department_counts: dict[str, int] = {}

    for employee_index, employee in enumerate(employee_profiles):
        department = next(item for item in DEPARTMENTS if item.unit_id == employee.department_id)
        member_count = created_department_counts.get(department.name, 0)
        created_department_counts[department.name] = member_count + 1

        task_ids_for_review: list[str] = []
        done_count = 0
        doing_count = 0
        todo_count = 0
        for day_index, work_day in enumerate(week_days):
            for slot_index in range(3):
                project_label = department.focus_tracks[(employee_index + day_index + slot_index) % len(department.focus_tracks)]
                title, description = _task_template(
                    department,
                    employee,
                    project_label=project_label,
                    day_index=day_index,
                    slot_index=slot_index,
                )
                status = _status_for(day_index, slot_index)
                if status == "done":
                    done_count += 1
                elif status == "doing":
                    doing_count += 1
                else:
                    todo_count += 1
                task_id = f"task_sim_{employee.user_id}_{work_day.strftime('%Y%m%d')}_{slot_index}"
                created_at = _iso_timestamp(work_day, 9 + slot_index * 3, 10)
                updated_at = _iso_timestamp(work_day, 18, 10 + slot_index)
                list_id = list_cycle[(employee_index + slot_index) % len(list_cycle)]
                list_meta = task_lists.get(list_id, {"name": "收集箱", "color": "#888681"})
                tag_names = [department.tag_specs[slot_index % len(department.tag_specs)][0], "周复盘"]
                if slot_index == 1:
                    tag_names.append("跨部门协同")
                tag_records = [tags_by_name[name] for name in tag_names]
                collaborator_id = employee.leader_user_id if employee.leader_user_id and slot_index == 1 else None
                db.execute(
                    """
                    INSERT INTO tasks(
                        id, organization_id, title, description, creator_id, owner_id, due_date, priority, list_id,
                        progress_status, source_type, source_id, tags_json, tag_ids_json, created_at, updated_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        organization_id,
                        title,
                        description,
                        employee.user_id,
                        employee.user_id,
                        work_day.isoformat(),
                        "high" if slot_index == 0 and day_index in (0, 3) else ("normal" if slot_index != 1 else "normal"),
                        list_id,
                        status,
                        SIMULATION_SOURCE_TYPE,
                        department.unit_id,
                        to_json([item["name"] for item in tag_records]),
                        to_json([item["id"] for item in tag_records]),
                        created_at,
                        updated_at,
                    ),
                )
                collaborator_rows = [
                    (task_id, employee.user_id, 0, 1, "accepted", None, updated_at, created_at, updated_at),
                ]
                if collaborator_id:
                    collaborator_rows.append((task_id, collaborator_id, 1, 0, "accepted", None, updated_at, created_at, updated_at))
                db.executemany(
                    """
                    INSERT INTO task_collaborators(
                        task_id, user_id, order_index, is_owner, inbox_status, return_reason, handled_at, created_at, updated_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    collaborator_rows,
                )
                db.execute(
                    """
                    INSERT INTO task_activity_events(id, task_id, actor_id, event_type, payload_json, created_at)
                    VALUES(?, ?, ?, 'created', ?, ?)
                    """,
                    (f"activity_{task_id}", task_id, employee.user_id, to_json({"sourceType": SIMULATION_SOURCE_TYPE}), created_at),
                )
                task_ids_for_review.append(task_id)
                total_tasks += 1

        review_id = f"review_sim_{employee.user_id}_{week_label.lower().replace('-', '_')}"
        summary = _employee_summary(
            department,
            employee,
            task_count=len(task_ids_for_review),
            done_count=done_count,
            doing_count=doing_count,
            todo_count=todo_count,
        )
        submitted_at = _iso_timestamp(week_days[-1], 20, (employee_index % 10) * 3)
        db.execute(
            """
            INSERT INTO weekly_review_entries(
                id, organization_id, user_id, week_label, work_progress, work_blocker, blocker_type, work_direction,
                next_week_focus, support_needed, related_plan_ids_json, work_free_note, personal_growth_note,
                personal_private_note, personal_visibility, submitted_at, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'self', ?, ?, ?)
            """,
            (
                review_id,
                organization_id,
                employee.user_id,
                week_label,
                summary["workProgress"],
                summary["workBlocker"],
                summary["blockerType"],
                summary["workDirection"],
                summary["nextWeekFocus"],
                summary["supportNeeded"],
                to_json([plan_ids[department.unit_id], plan_ids["org"]]),
                summary["workFreeNote"],
                summary["personalGrowthNote"],
                summary["personalPrivateNote"],
                submitted_at,
                submitted_at,
                submitted_at,
            ),
        )
        total_reviews += 1

        review_items: list[tuple[str, str, str, str, str, str, str, str, str, str, str, str, str]] = []
        for task_id in task_ids_for_review:
            row = db.fetchone(
                """
                SELECT t.*, l.name AS list_name, l.color AS list_color
                FROM tasks t
                JOIN task_lists l ON l.id = t.list_id
                WHERE t.id = ?
                """,
                (task_id,),
            )
            assert row is not None
            due_date = date.fromisoformat(str(row["due_date"]))
            tag_records = [tags_by_name[name] for name in (from_json(row["tags_json"], []) if isinstance(from_json(row["tags_json"], []), list) else []) if name in tags_by_name]
            note = _note_for_task(
                department,
                employee,
                title=str(row["title"]),
                status=str(row["progress_status"]),
                day_index=(due_date - week_days[0]).days,
                slot_index=int(str(row["id"]).rsplit("_", 1)[1]),
            )
            structured_note = _structured_note_for_task(
                department,
                employee,
                title=str(row["title"]),
                status=str(row["progress_status"]),
                day_index=(due_date - week_days[0]).days,
                slot_index=int(str(row["id"]).rsplit("_", 1)[1]),
                department_plan_id=plan_ids[department.unit_id],
                organization_plan_id=plan_ids["org"],
            )
            snapshot = _task_snapshot(
                title=str(row["title"]),
                status=str(row["progress_status"]),
                due_date=due_date,
                created_at=str(row["created_at"]),
                list_name=str(row["list_name"]),
                list_color=str(row["list_color"]),
                tags=tag_records,
            )
            review_items.append(
                (
                    f"review_item_{task_id}",
                    organization_id,
                    review_id,
                    employee.user_id,
                    task_id,
                    week_label,
                    "work",
                    note,
                    to_json(structured_note),
                    str(row["updated_at"]),
                    to_json(snapshot),
                    str(row["updated_at"]),
                    str(row["updated_at"]),
                )
            )
        db.executemany(
            """
            INSERT INTO weekly_review_task_entries(
                id, organization_id, review_id, user_id, task_id, week_label, content_domain, note, structured_note_json, reviewed_at, task_snapshot_json, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            review_items,
        )
        total_review_items += len(review_items)
        db.execute(
            """
            INSERT INTO weekly_review_sections(id, review_id, section_type, content, content_domain, visibility_scope, created_at)
            VALUES(?, ?, 'work', ?, 'work', 'team', ?)
            """,
            (
                f"section_{review_id}",
                review_id,
                "\n".join(item[7] for item in review_items[:6]),
                submitted_at,
            ),
        )

    return {
        "weekLabel": week_label,
        "employeeCount": len(employee_profiles),
        "departmentCount": len(DEPARTMENTS),
        "taskCount": total_tasks,
        "reviewCount": total_reviews,
        "reviewItemCount": total_review_items,
        "departmentBreakdown": created_department_counts,
    }
~~~

## `cloud_backend/app/smart_input.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import json
import os
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Sequence
from uuid import uuid4

import httpx

from app.models import EventLineRecord, SmartTaskDraftRecord, SmartTaskDraftResponse


# ─── LLM provider: Volcengine Ark (火山方舟) ───────────────────────
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_LLM_MODEL = "ep-m-20260326120641-m4lf6"  # Doubao-Seed-1.6

# Legacy aliases kept for grep-ability
QWEN_BASE_URL = ARK_BASE_URL
DEFAULT_QWEN_MODEL = DEFAULT_LLM_MODEL
DOUBAO_STANDARD_SUBMIT_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit"
DOUBAO_STANDARD_QUERY_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/query"
DOUBAO_STANDARD_RESOURCE_ID = "volc.seedasr.auc"
DOUBAO_STANDARD_EXTENSIONS = {
    "pcm",
    "opus",
    "mp3",
    "wav",
    "spx",
    "ogg",
    "amr",
    "aac",
    "m4a",
}

_CN_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_DATE_CN_PATTERN = re.compile(r"([零〇一二两三四五六七八九十]{1,3})(月|日|号)")
_DATE_RANGE_FULL_PATTERN = re.compile(
    r"(?:(\d{4})年)?\s*(\d{1,2})月(\d{1,2})(?:日|号)?\s*(?:到|至|-|—|~)\s*(?:(\d{1,2})月)?(\d{1,2})(?:日|号)?"
)
_DATE_SINGLE_PATTERN = re.compile(r"(?:(\d{4})年)?\s*(\d{1,2})月(\d{1,2})(?:日|号)?")
_TIME_RANGE_PATTERN = re.compile(
    r"(上午|早上|中午|下午|晚上)?\s*(\d{1,2})(?:[:：点时](\d{1,2}))?\s*(?:到|至|-|—|~)\s*(上午|早上|中午|下午|晚上)?\s*(\d{1,2})(?:[:：点时](\d{1,2}))?"
)


def _normalize_search_text(value: str) -> str:
    return (
        value.lower()
        .replace(" ", "")
        .replace("\n", "")
        .replace("\t", "")
        .translate(str.maketrans("", "", '·•,，。！？、:：;；"\'“”‘’（）()【】[]{}<>《》-_/\\'))
        .strip()
    )


def _split_search_fragments(value: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"[\s·•,，。！？、:：;；\"'“”‘’（）()【】\[\]{}<>《》\-_\/\\]+", value)
        if item.strip() and len(item.strip()) >= 2
    ]


def derive_project_label(event_line: EventLineRecord) -> str:
    if event_line.primaryClientName and event_line.primaryClientName.strip():
        return event_line.primaryClientName.strip()
    first_segment = event_line.name.split("·", 1)[0].split("•", 1)[0].split("|", 1)[0].split("/", 1)[0]
    compact = first_segment.strip() or event_line.name.strip()
    first_word = compact.split(maxsplit=1)[0].strip()
    return first_word or compact


def _score_event_line_match(search_key: str, event_line: EventLineRecord) -> int:
    if not search_key or len(search_key) < 2:
        return 0

    aliases = {
        event_line.name,
        event_line.primaryClientName or "",
        derive_project_label(event_line),
        *(_split_search_fragments(event_line.name)),
        *(_split_search_fragments(event_line.primaryClientName or "")),
    }
    best_score = 0
    for alias in aliases:
        normalized = _normalize_search_text(alias)
        if len(normalized) < 2:
            continue
        if search_key == normalized:
            best_score = max(best_score, 320 + len(normalized))
            continue
        if search_key in normalized:
            best_score = max(best_score, 220 + len(search_key))
            continue
        if normalized in search_key:
            best_score = max(best_score, 160 + len(normalized))
    return best_score


def _coerce_chinese_number(raw: str) -> int | None:
    value = raw.strip()
    if not value:
        return None
    if value.isdigit():
        return int(value)
    if value == "十":
        return 10
    if "十" in value:
        left, _, right = value.partition("十")
        tens = 1 if not left else _CN_DIGITS.get(left)
        if tens is None:
            return None
        ones = 0 if not right else _CN_DIGITS.get(right)
        if ones is None:
            return None
        return tens * 10 + ones
    if len(value) == 1:
        return _CN_DIGITS.get(value)
    total = 0
    for ch in value:
        digit = _CN_DIGITS.get(ch)
        if digit is None:
            return None
        total = total * 10 + digit
    return total


def _normalize_spoken_text(text: str) -> str:
    return _DATE_CN_PATTERN.sub(
        lambda match: f"{_coerce_chinese_number(match.group(1)) or match.group(1)}{match.group(2)}",
        text.strip(),
    )


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _format_date_key(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _parse_date_range(text: str, reference_date: date) -> tuple[str | None, str | None]:
    normalized = _normalize_spoken_text(text)
    full_match = _DATE_RANGE_FULL_PATTERN.search(normalized)
    if full_match:
        year = int(full_match.group(1) or reference_date.year)
        start_month = int(full_match.group(2))
        start_day = int(full_match.group(3))
        end_month = int(full_match.group(4) or start_month)
        end_day = int(full_match.group(5))
        start_date = _safe_date(year, start_month, start_day)
        end_year = year + 1 if start_month > end_month else year
        end_date = _safe_date(end_year, end_month, end_day)
        return _format_date_key(start_date), _format_date_key(end_date or start_date)

    single_match = _DATE_SINGLE_PATTERN.search(normalized)
    if single_match:
        year = int(single_match.group(1) or reference_date.year)
        parsed_date = _safe_date(year, int(single_match.group(2)), int(single_match.group(3)))
        return _format_date_key(parsed_date), None

    lowered = normalized.lower()
    if "明天" in lowered:
        target = reference_date + timedelta(days=1)
        return target.isoformat(), None
    if "后天" in lowered:
        target = reference_date + timedelta(days=2)
        return target.isoformat(), None
    if "昨天" in lowered:
        target = reference_date - timedelta(days=1)
        return target.isoformat(), None
    if "今天" in lowered:
        return reference_date.isoformat(), None
    return None, None


def _convert_clock(hour: int, minute: int, meridiem: str | None) -> tuple[int, int]:
    label = (meridiem or "").strip()
    if label in {"下午", "晚上"} and hour < 12:
        hour += 12
    if label == "中午" and hour < 11:
        hour += 12
    return hour, minute


def _parse_time_range(text: str) -> tuple[str | None, int | None]:
    normalized = _normalize_spoken_text(text)
    match = _TIME_RANGE_PATTERN.search(normalized)
    if not match:
        single_time = re.search(
            r"(?P<meridiem>上午|早上|中午|下午|晚上)?\s*(?P<hour>\d{1,2})(?:[:：点时](?P<minute>\d{1,2}))?",
            normalized,
        )
        if not single_time:
            return None, None
        match_payload = single_time.groupdict()
        hour = int(match_payload.get("hour") or 0)
        minute = int(match_payload.get("minute") or 0)
        meridiem = match_payload.get("meridiem")
        hour, minute = _convert_clock(hour, minute, meridiem)
        return f"{hour:02d}:{minute:02d}", None

    start_hour, start_minute = _convert_clock(int(match.group(2)), int(match.group(3) or 0), match.group(1))
    end_hour, end_minute = _convert_clock(int(match.group(5)), int(match.group(6) or 0), match.group(4))
    duration = max(((end_hour * 60 + end_minute) - (start_hour * 60 + start_minute)), 30)
    return f"{start_hour:02d}:{start_minute:02d}", duration


def _extract_location(text: str) -> str | None:
    patterns = (
        r"(?:去|到|在)([\u4e00-\u9fffA-Za-z]{2,16})[\s，,]*?(?:做|开|办|参加|进行|开展|出差|调研|工作坊|会议|沟通|拜访)",
        r"(?:地点|位置)[:：]?\s*([\u4e00-\u9fffA-Za-z]{2,16})",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None


def _infer_title(text: str, location: str | None) -> str | None:
    patterns = (
        r"(?:做|开|办|参加|进行|安排)([^，。；,\n]{2,28}(?:工作坊|会议|沟通|调研|复盘|拜访|培训|汇报|讨论|出差))",
        r"([^，。；,\n]{2,28}(?:工作坊|会议|沟通|调研|复盘|拜访|培训|汇报|讨论|出差))",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        candidate = match.group(1).strip(" ，。；,")
        if location and location not in candidate:
            return f"{location}{candidate}"
        return candidate
    fragments = [frag for frag in re.split(r"[，。；,\n]", text) if frag.strip()]
    if not fragments:
        return None
    head = re.sub(r"^(帮我|请|安排一下|建一个|创建一个|新增一个)(日程|任务)?", "", fragments[0]).strip()
    return head[:24] or None


def _infer_project_query(text: str, title: str | None, location: str | None) -> str | None:
    patterns = (
        r"(?:项目(?:是)?关于|关于)([^，。；,\n]{2,24})",
        r"(?:关联到|归档到)([^，。；,\n]{2,24})",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip(" ，。；,的")
    if title and location and location in title:
        return f"{location}{re.sub(r'(工作坊|会议|沟通|调研|复盘|拜访|培训|汇报|讨论|出差)$', '项目', title)}"
    return title or None


def _truncate_compact_text(value: str | None, limit: int) -> str | None:
    if not value:
        return None
    compact = re.sub(r"\s+", "", value).strip(" ·•|｜/-，。；,")
    if not compact:
        return None
    return compact if len(compact) <= limit else compact[:limit]


def _strip_duplicate_terms(value: str, *terms: str | None) -> str:
    result = value
    for term in terms:
        term = (term or "").strip()
        if not term:
            continue
        result = result.replace(term, "")
        normalized_term = re.sub(r"(基金会|老师|项目|合作|研究)$", "", term)
        if normalized_term and normalized_term != term:
            result = result.replace(normalized_term, "")
    return result.strip(" ·•|｜/-，。；,")


def _summarize_event_line_label(event_line_name: str | None, client_name: str | None) -> str | None:
    base = (event_line_name or "").strip()
    if not base:
        return None

    candidates: list[str] = []
    if client_name:
        stripped = base
        if stripped.startswith(client_name):
            stripped = stripped[len(client_name) :].strip(" ·•|｜/-")
        stripped = _strip_duplicate_terms(stripped, client_name)
        candidates.append(stripped)
    candidates.append(base)

    generic_labels = {"项目", "工作坊", "会议", "沟通", "调研", "复盘", "合作"}
    cleanup_patterns = (
        r"^跟[^的]{0,12}(?:老师|总|主任|校长|院长|会长|负责人)?",
        r"^(?:跟|和|与|围绕|关于|针对|推进|跟进|沟通|核对|讨论|安排|整理|准备|发给|确认|对接)",
        r"^(?:她的|他的|其|本次|这个|那个)",
    )

    for candidate in candidates:
        label = candidate.strip(" ·•|｜/-")
        if not label:
            continue
        for pattern in cleanup_patterns:
            label = re.sub(pattern, "", label)
        label = label.strip(" ·•|｜/-")
        if "的" in label:
            tail = label.split("的")[-1].strip()
            if 2 <= len(tail) <= 12:
                label = tail
        label = re.sub(r"(进度|推进|事项|事宜|安排|计划|时间|节点|规划)$", "", label).strip()
        if label in generic_labels and client_name and base.startswith(client_name):
            carry = client_name[-min(4, len(client_name)) :].strip()
            lifted = f"{carry}{label}".strip()
            if lifted and lifted not in generic_labels:
                return _truncate_compact_text(lifted, 10)
        if label and label not in generic_labels:
            return _truncate_compact_text(label, 10)

    fallback = _strip_duplicate_terms(base, client_name)
    compact = _truncate_compact_text(fallback or base, 10)
    return compact


def _extract_deadline_fragment(text: str) -> str | None:
    match = re.search(r"(今天|明天|后天|本周[一二三四五六日天]?|下周[一二三四五六日天]?|周[一二三四五六日天](?:之前|前|后)?)", text)
    if not match:
        return None
    return match.group(1).replace("之前", "前")


def _clean_action_object(value: str, client_name: str | None, event_line_name: str | None) -> str:
    text = value.strip(" ，。；,")
    text = re.sub(r"^(一个|一下|一版|一份|关于|把|将|再|先|会|要|需要)", "", text)
    text = re.sub(r"(过来|一下|一下子|出来|完成|落实)$", "", text)
    text = re.sub(r"(的)?(时间规划|时间安排)$", "规划", text)
    text = re.sub(r"(安排|计划|时间)$", "", text)
    text = _strip_duplicate_terms(text, client_name, event_line_name)
    text = text.strip("的 ")
    return text.strip(" ，。；,")


def _looks_like_good_action_summary(value: str | None) -> bool:
    if not value:
        return False
    text = value.strip()
    if len(text) < 3:
        return False
    if re.search(r"(今天|明天|后天|本周|下周|周[一二三四五六日天](?:之前|前|后)?|\d{1,2}月\d{1,2}[日号]?|\d{1,2}[:：点时])", text):
        return False
    if re.search(r"(会发|要发|需要|之前|过来|帮我|请|安排一下|创建一个|新增一个)", text):
        return False
    return True


def _infer_action_summary(
    transcript: str,
    raw_title: str | None,
    client_name: str | None,
    event_line_name: str | None,
) -> str | None:
    preferred = _clean_action_object(raw_title or "", client_name, event_line_name)
    if _looks_like_good_action_summary(preferred):
        preferred_short = _truncate_compact_text(preferred, 20)
        if preferred_short:
            return preferred_short

    deadline = _extract_deadline_fragment(transcript)
    verb_match = re.search(
        r"(发|提交|确认|安排|推进|跟进|整理|输出|准备|完成|沟通|对齐|核对|复盘|拜访|汇报|讨论|调研|梳理)([^，。；,\n]{0,24})",
        transcript,
    )
    if verb_match:
        verb = verb_match.group(1)
        obj = _clean_action_object(verb_match.group(2), client_name, event_line_name)
        if "关于" in obj:
            obj = _clean_action_object(obj.split("关于", 1)[1], client_name, event_line_name)
        if obj:
            candidate = f"{deadline or ''}{verb}{obj}"
            shortened = _truncate_compact_text(candidate, 14)
            if shortened:
                return shortened

    topic_match = re.search(r"关于([^，。；,\n]{2,18})", transcript)
    if topic_match:
        topic = _clean_action_object(topic_match.group(1), client_name, event_line_name)
        if topic:
            if re.search(r"(发|提交)", transcript):
                return _truncate_compact_text(f"{deadline or ''}发{topic}", 14)
            return _truncate_compact_text(topic, 14)

    source = _strip_duplicate_terms(raw_title or transcript, client_name, event_line_name)
    source = re.sub(r"^(帮我|请|安排一下|安排|建一个|创建一个|新增一个|提醒我|记一下|记得|我要|我想|我们|现在|之后|然后|就是)", "", source)
    source = re.sub(r"(今天|明天|后天|本周|下周|周[一二三四五六日天](?:之前|前|后)?|\d{1,2}月\d{1,2}[日号]?|上午|下午|晚上|中午|\d{1,2}[:：点时]\d{0,2})", "", source)
    source = source.strip(" ，。；,")
    return _truncate_compact_text(source, 14)


def _compose_structured_title(
    *,
    client_name: str | None,
    event_line_name: str | None,
    action_summary: str | None,
    fallback_title: str,
) -> str:
    parts: list[str] = []
    client_label = _truncate_compact_text(client_name, 10)
    event_line_label = _summarize_event_line_label(event_line_name, client_name)
    action_label = _truncate_compact_text(action_summary, 20)

    if client_label:
        parts.append(client_label)

    if event_line_label and event_line_label not in parts:
        parts.append(event_line_label)

    if action_label and action_label not in parts:
        parts.append(action_label)

    if not parts:
        return _truncate_compact_text(fallback_title, 24) or fallback_title[:24]

    joined = "｜".join(parts)
    if len(joined) <= 40:
        return joined

    compact_parts = [
        _truncate_compact_text(client_label, 8),
        _truncate_compact_text(event_line_label, 10),
        _truncate_compact_text(action_label, 16),
    ]
    compact_joined = "｜".join([item for item in compact_parts if item])
    return compact_joined or (_truncate_compact_text(fallback_title, 24) or fallback_title[:24])


def _infer_action_tag(text: str) -> str:
    if re.search(r"会议|沟通|对接|拜访|工作坊|复盘|汇报|讨论|访谈", text):
        return "会议/沟通"
    if re.search(r"调研|分析|研究|诊断|梳理|摸底", text):
        return "内部分析"
    return "材料/交付"


def _build_description(
    transcript: str,
    start_date: str | None,
    end_date: str | None,
    due_time: str | None,
    duration_minutes: int | None,
    location: str | None,
) -> str:
    lines: list[str] = []
    if start_date and end_date and start_date != end_date:
        lines.append(f"时间范围：{start_date} 至 {end_date}")
    elif start_date:
        lines.append(f"日期：{start_date}")
    if due_time:
        lines.append(f"开始时间：{due_time}")
    if duration_minutes and duration_minutes > 0:
        hours = duration_minutes / 60
        lines.append(f"预计时长：{hours:g} 小时")
    if location:
        lines.append(f"地点：{location}")
    lines.append("原始输入：")
    lines.append(transcript.strip())
    return "\n".join(lines)


def _load_relaxed_json(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end >= start:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def _qwen_api_key() -> str:
    """Return the LLM API key. Checks Volcengine Ark keys first, then legacy Qwen keys."""
    return (
        os.getenv("ARK_API_KEY", "").strip()
        or os.getenv("VOLCENGINE_API_KEY", "").strip()
        or os.getenv("DASHSCOPE_API_KEY", "").strip()
        or os.getenv("QWEN_API_KEY", "").strip()
        or os.getenv("YIYU_QWEN_API_KEY", "").strip()
    )


def _doubao_file_asr_credentials() -> tuple[str, str]:
    app_id = (
        os.getenv("DOUBAO_FILE_ASR_APP_ID", "").strip()
        or os.getenv("YIYU_DOUBAO_FILE_ASR_APP_ID", "").strip()
        or os.getenv("VOLCENGINE_FILE_ASR_APP_ID", "").strip()
        or os.getenv("DOUBAO_ASR_APP_ID", "").strip()
        or os.getenv("YIYU_DOUBAO_ASR_APP_ID", "").strip()
        or os.getenv("VOLCENGINE_ASR_APP_ID", "").strip()
    )
    access_token = (
        os.getenv("DOUBAO_FILE_ASR_ACCESS_TOKEN", "").strip()
        or os.getenv("YIYU_DOUBAO_FILE_ASR_ACCESS_TOKEN", "").strip()
        or os.getenv("VOLCENGINE_FILE_ASR_ACCESS_TOKEN", "").strip()
        or os.getenv("DOUBAO_ASR_ACCESS_TOKEN", "").strip()
        or os.getenv("YIYU_DOUBAO_ASR_ACCESS_TOKEN", "").strip()
        or os.getenv("VOLCENGINE_ASR_ACCESS_TOKEN", "").strip()
    )
    return app_id, access_token


def _doubao_stream_asr_credentials() -> tuple[str, str]:
    app_id = (
        os.getenv("DOUBAO_STREAM_ASR_APP_ID", "").strip()
        or os.getenv("YIYU_DOUBAO_STREAM_ASR_APP_ID", "").strip()
        or os.getenv("VOLCENGINE_STREAM_ASR_APP_ID", "").strip()
        or os.getenv("DOUBAO_ASR_APP_ID", "").strip()
        or os.getenv("YIYU_DOUBAO_ASR_APP_ID", "").strip()
        or os.getenv("VOLCENGINE_ASR_APP_ID", "").strip()
    )
    access_token = (
        os.getenv("DOUBAO_STREAM_ASR_ACCESS_TOKEN", "").strip()
        or os.getenv("YIYU_DOUBAO_STREAM_ASR_ACCESS_TOKEN", "").strip()
        or os.getenv("VOLCENGINE_STREAM_ASR_ACCESS_TOKEN", "").strip()
        or os.getenv("DOUBAO_ASR_ACCESS_TOKEN", "").strip()
        or os.getenv("YIYU_DOUBAO_ASR_ACCESS_TOKEN", "").strip()
        or os.getenv("VOLCENGINE_ASR_ACCESS_TOKEN", "").strip()
    )
    return app_id, access_token


def _infer_extension(file_name: str | None, mime_type: str | None) -> str:
    suffix = Path(file_name or "").suffix.lower().lstrip(".")
    if suffix:
        return suffix
    lowered = (mime_type or "").lower()
    if "mpeg" in lowered or "mp3" in lowered:
        return "mp3"
    if "wav" in lowered:
        return "wav"
    if "ogg" in lowered or "opus" in lowered:
        return "ogg"
    if "aac" in lowered:
        return "aac"
    if "m4a" in lowered or "mp4" in lowered:
        return "m4a"
    return "bin"


def _build_asr_headers(*, app_id: str, access_token: str, resource_id: str, request_id: str, tt_logid: str | None = None) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "X-Api-App-Key": app_id,
        "X-Api-Access-Key": access_token,
        "X-Api-Resource-Id": resource_id,
        "X-Api-Request-Id": request_id,
        "X-Api-Sequence": "-1",
    }
    if tt_logid:
        headers["X-Tt-Logid"] = tt_logid
    return headers


def _extract_asr_text(payload: dict[str, Any]) -> str:
    result = payload.get("result")
    if isinstance(result, dict):
        text = result.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        utterances = result.get("utterances")
        if isinstance(utterances, list):
            parts = [str(item.get("text", "")).strip() for item in utterances if isinstance(item, dict) and str(item.get("text", "")).strip()]
            if parts:
                return "\n".join(parts)
    text = payload.get("text")
    return text.strip() if isinstance(text, str) else ""


def _extract_doubao_error_message(response: httpx.Response) -> str:
    header_message = (response.headers.get("X-Api-Message") or "").strip()
    status_code = (response.headers.get("X-Api-Status-Code") or "").strip()
    body_message = ""
    try:
        payload = response.json()
        if isinstance(payload, dict):
            header = payload.get("header")
            if isinstance(header, dict):
                body_message = str(header.get("message") or "").strip()
            if not body_message:
                body_message = str(payload.get("message") or "").strip()
    except Exception:
        body_message = response.text.strip()

    message = header_message or body_message or response.text.strip() or f"HTTP {response.status_code}"
    if "requested resource not granted" in message:
        return (
            f"豆包语音识别资源未授权（{status_code or response.status_code}）。"
            "当前云端配置的 App ID / Access Token 没有拿到当前调用资源的权限，"
            "通常是用了错误的资源 ID，或填成了没有对应识别能力的应用。"
        )
    return f"豆包语音识别请求失败：{status_code or response.status_code} {message}".strip()


def transcribe_audio_with_doubao(
    audio_bytes: bytes,
    *,
    file_name: str | None,
    mime_type: str | None,
    public_url: str | None = None,
) -> str:
    app_id, access_token = _doubao_file_asr_credentials()
    if not app_id or not access_token:
        raise RuntimeError("豆包 ASR 未配置 appid 或 access token。")
    extension = _infer_extension(file_name, mime_type)
    if not audio_bytes:
        raise RuntimeError("录音内容为空，无法转写。")
    request_id = str(uuid4())

    if not public_url:
        raise RuntimeError("当前录音格式需要云端可访问 URL 才能转写。")
    if extension not in DOUBAO_STANDARD_EXTENSIONS:
        raise RuntimeError(f"当前录音格式 {extension} 暂不支持自动转写。")

    submit_payload = {
        "user": {"uid": app_id},
        "audio": {
            "format": extension,
            "url": public_url,
        },
        "request": {
            "model_name": "bigmodel",
            "enable_itn": True,
            "enable_punc": True,
            "enable_ddc": True,
        },
    }

    with httpx.Client(timeout=httpx.Timeout(timeout=None, connect=8.0, read=20.0, write=20.0, pool=8.0)) as client:
        submit_response = client.post(
            DOUBAO_STANDARD_SUBMIT_URL,
            headers=_build_asr_headers(
                app_id=app_id,
                access_token=access_token,
                resource_id=DOUBAO_STANDARD_RESOURCE_ID,
                request_id=request_id,
            ),
            json=submit_payload,
        )
        if submit_response.status_code >= 400:
            raise RuntimeError(_extract_doubao_error_message(submit_response))
        submit_status = submit_response.headers.get("X-Api-Status-Code", "")
        if submit_status != "20000000":
            raise RuntimeError(f"豆包标准版提交失败：{submit_status} {submit_response.headers.get('X-Api-Message', '')}".strip())

        tt_logid = submit_response.headers.get("X-Tt-Logid", "")
        for _ in range(60):
            time.sleep(1.0)
            query_response = client.post(
                DOUBAO_STANDARD_QUERY_URL,
                headers=_build_asr_headers(
                    app_id=app_id,
                    access_token=access_token,
                    resource_id=DOUBAO_STANDARD_RESOURCE_ID,
                    request_id=request_id,
                    tt_logid=tt_logid or None,
                ),
                json={},
            )
            if query_response.status_code >= 400:
                raise RuntimeError(_extract_doubao_error_message(query_response))
            query_status = query_response.headers.get("X-Api-Status-Code", "")
            if query_status == "20000000":
                transcript = _extract_asr_text(query_response.json())
                if transcript:
                    return transcript
                raise RuntimeError("豆包标准版已完成，但未返回有效转写文本。")
            if query_status == "20000003":
                raise RuntimeError("录音中没有识别到有效人声。")
            if query_status not in {"20000001", "20000002"}:
                raise RuntimeError(f"豆包标准版查询失败：{query_status} {query_response.headers.get('X-Api-Message', '')}".strip())
        raise RuntimeError("豆包标准版转写超时，请稍后重试。")


def _qwen_extract(transcript: str, reference_date: date) -> dict[str, Any] | None:
    api_key = _qwen_api_key()
    if not api_key:
        return None

    schema = {
        "type": "object",
        "properties": {
            "intent": {"type": "string"},
            "title": {"type": ["string", "null"]},
            "actionSummary": {"type": ["string", "null"]},
            "startDate": {"type": ["string", "null"]},
            "endDate": {"type": ["string", "null"]},
            "startTime": {"type": ["string", "null"]},
            "durationMinutes": {"type": ["integer", "null"]},
            "location": {"type": ["string", "null"]},
            "description": {"type": ["string", "null"]},
            "projectQuery": {"type": ["string", "null"]},
            "eventLineQuery": {"type": ["string", "null"]},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["intent", "tags"],
    }
    user_prompt = (
        "请从以下中文口语中提取移动端任务/日程草稿。\n"
        "任务标题的命名结构必须是：「组织/客户名称 + 事件线/项目名 + 具体动作」，用竖线分隔。\n"
        "例如：'华润万家｜Q4供应链优化｜提交方案初稿'、'日慈基金会｜品牌改造｜等高老师发时间规划'。\n"
        "projectQuery 填口语中提到的组织/客户名称（如'日慈基金会'、'华润万家'）。\n"
        "eventLineQuery 填口语中提到的项目/事件线关键词（如'品牌改造'、'供应链优化'）。\n"
        "actionSummary 填具体要做的事（如'等高老师发时间规划'、'提交方案初稿'），不要截断。\n"
        "description 必须填写！把口语内容整理成条理清晰的任务描述：\n"
        "  - 提炼核心要做的事情\n"
        "  - 列出关键人物、步骤、注意事项\n"
        "  - 不要照搬原文，要用书面语重新组织\n"
        "  - 如果有多个步骤，用编号列出\n"
        "如果是多天安排，请 startDate 用开始日期，endDate 用结束日期。\n"
        "不要把整段转写原文照搬进 title，要提炼结构化。\n"
        "只返回 JSON，不要解释。\n"
        f"参考日期：{reference_date.isoformat()}\n"
        f"口语内容：{transcript}"
    )
    payload = {
        "model": os.getenv("YIYU_SMART_INPUT_MODEL", DEFAULT_QWEN_MODEL),
        "messages": [
            {"role": "system", "content": "你是移动端智能输入解析器。只返回 JSON。"},
            {
                "role": "user",
                "content": (
                    "请严格返回一个 JSON 对象，不要使用 Markdown，不要添加解释。"
                    f"请确保返回结构满足下面这个 JSON Schema。\n{json.dumps(schema, ensure_ascii=False)}\n\n{user_prompt}"
                ),
            },
        ],
        "temperature": 0.2,
        "top_p": 0.85,
        "max_tokens": 1200,
        "stream": False,
        "enable_thinking": False,
    }
    timeout = httpx.Timeout(timeout=None, connect=8.0, read=18.0, write=18.0, pool=8.0)
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
    return _load_relaxed_json(text)


def _heuristic_extract(transcript: str, reference_date: date) -> tuple[dict[str, Any], list[str]]:
    cleaned = transcript.strip()
    start_date, end_date = _parse_date_range(cleaned, reference_date)
    due_time, duration_minutes = _parse_time_range(cleaned)
    location = _extract_location(cleaned)
    title = _infer_title(cleaned, location)
    project_query = _infer_project_query(cleaned, title, location)
    payload = {
        "intent": "task_schedule",
        "title": title,
        "startDate": start_date,
        "endDate": end_date,
        "startTime": due_time,
        "durationMinutes": duration_minutes,
        "location": location,
        "description": _build_description(cleaned, start_date, end_date, due_time, duration_minutes, location),
        "projectQuery": project_query,
        "eventLineQuery": title or project_query,
        "tags": [_infer_action_tag(cleaned)],
    }
    warnings: list[str] = []
    if not title:
        warnings.append("标题无法完全确定，已使用原始输入生成草稿。")
        payload["title"] = cleaned[:24]
    if not start_date:
        warnings.append("未识别到明确日期，已保留为无截止日期草稿。")
    return payload, warnings


def _match_event_line(
    event_lines: Sequence[EventLineRecord],
    *,
    current_event_line_id: str | None,
    title: str | None,
    project_query: str | None,
    event_line_query: str | None,
    raw_transcript: str | None = None,
) -> EventLineRecord | None:
    best: EventLineRecord | None = None
    best_score = 0
    search_terms = [
        _normalize_search_text(event_line_query or ""),
        _normalize_search_text(project_query or ""),
        _normalize_search_text(title or ""),
    ]
    # Also match against fragments from the raw voice transcript.
    # This catches client/project names that AI may have dropped from the title.
    if raw_transcript:
        for fragment in _split_search_fragments(raw_transcript):
            normalized = _normalize_search_text(fragment)
            if len(normalized) >= 2 and normalized not in search_terms:
                search_terms.append(normalized)
    for event_line in event_lines:
        score = 0
        if current_event_line_id and event_line.id == current_event_line_id:
            score += 28
        for search_key in search_terms:
            score = max(score, _score_event_line_match(search_key, event_line))
        if score > best_score:
            best_score = score
            best = event_line
    return best if best_score >= 120 else None


def build_smart_task_draft(
    transcript: str,
    event_lines: Sequence[EventLineRecord],
    *,
    reference_date: date | None = None,
    current_event_line_id: str | None = None,
) -> SmartTaskDraftResponse:
    reference = reference_date or datetime.now().date()
    warnings: list[str] = []
    parsed: dict[str, Any] | None = None
    confidence = 0.42

    try:
        parsed = _qwen_extract(transcript, reference)
        if parsed:
            confidence = 0.84
    except Exception:
        warnings.append("AI 解析暂时不可用，已切换到规则兜底。")

    if not parsed:
        parsed, heuristic_warnings = _heuristic_extract(transcript, reference)
        warnings.extend(heuristic_warnings)

    raw_title = str(parsed.get("title") or "").strip() or transcript.strip()[:24]
    start_date = str(parsed.get("startDate") or "").strip() or None
    end_date = str(parsed.get("endDate") or "").strip() or None
    due_time = str(parsed.get("startTime") or "").strip() or None
    raw_duration = parsed.get("durationMinutes")
    duration_minutes = int(raw_duration) if isinstance(raw_duration, int) else None
    location = str(parsed.get("location") or "").strip() or None
    project_query = str(parsed.get("projectQuery") or "").strip() or None
    event_line_query = str(parsed.get("eventLineQuery") or "").strip() or None
    raw_action_summary = str(parsed.get("actionSummary") or "").strip() or None
    tags = [str(item).strip() for item in parsed.get("tags", []) if str(item).strip()] or [_infer_action_tag(transcript)]

    description = str(parsed.get("description") or "").strip() or _build_description(
        transcript,
        start_date,
        end_date,
        due_time,
        duration_minutes,
        location,
    )

    matched_event_line = _match_event_line(
        event_lines,
        current_event_line_id=current_event_line_id,
        title=raw_title,
        project_query=project_query,
        event_line_query=event_line_query,
        raw_transcript=transcript,
    )

    client_name = derive_project_label(matched_event_line) if matched_event_line else None
    event_line_name = matched_event_line.name if matched_event_line else None
    action_summary = _infer_action_summary(
        transcript,
        raw_action_summary or raw_title,
        client_name,
        event_line_name,
    )
    title = _compose_structured_title(
        client_name=client_name,
        event_line_name=event_line_name,
        action_summary=action_summary,
        fallback_title=raw_title,
    )

    draft = SmartTaskDraftRecord(
        title=title,
        dueDate=start_date,
        endDate=end_date,
        dueTime=due_time,
        durationMinutes=duration_minutes,
        location=location,
        description=description,
        tags=tags,
        clientId=matched_event_line.primaryClientId if matched_event_line else None,
        clientName=client_name,
        eventLineId=matched_event_line.id if matched_event_line else None,
        eventLineName=event_line_name,
        projectQuery=project_query or client_name or title,
        eventLineQuery=event_line_query or event_line_name or title,
    )

    if not matched_event_line:
        warnings.append("未自动命中项目/事件线，生成后可在表单里手动调整。")

    return SmartTaskDraftResponse(
        transcript=transcript.strip(),
        intent=str(parsed.get("intent") or "task_schedule"),
        draft=draft,
        warnings=warnings,
        confidence=confidence,
    )
~~~

## `cloud_backend/app/task_pressure_seed.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from app.db import Database, to_json
from app.security import hash_password
from app.simulation_seed import _ensure_tag, _upsert_employee


PRESSURE_SEED_SOURCE_TYPE = "pressure_seed_doc_v2"
DEFAULT_SEED_PASSWORD = "Simulate123!"

TASK_LIST_SPECS: tuple[tuple[str, str, str, int, int], ...] = (
    ("list-0", "收集箱", "#888681", 0, 1),
    ("list-1", "客户项目", "#5B7BFE", 1, 0),
    ("list-2", "产品研发", "#F59E0B", 2, 0),
    ("list-3", "数据分析", "#10B981", 3, 0),
    ("list-4", "组织管理", "#8B5CF6", 4, 0),
    ("list-5", "品牌市场", "#EC4899", 5, 0),
)

QUARTER_GOAL_SUMMARIES = {
    "Q1-G1": "完成客户工作台、知识底座与日程任务模块的联动原型，验证软件底座闭环。",
    "Q1-G2": "围绕蓝信封、日慈、为爱黔行形成稳定推进与判断输出。",
    "Q1-G3": "完成官网、业务介绍、团队介绍、对外叙事等基础品牌资产更新。",
    "Q1-G4": "建立部门级周计划、周总结、AI 自动汇总与组织判断机制。",
}

DEPARTMENT_SPECS = {
    "咨询策略部": {
        "unit_id": "dept_consult_strategy",
        "leader_name": "庆华",
        "monthly_dna": "本月重点是把客户战略诊断、方案共创和品牌叙事收成一条能持续复用的判断链，确保咨询动作可以真正落地。",
        "color": "#5B7BFE",
    },
    "科技发展部": {
        "unit_id": "dept_tech_development",
        "leader_name": "佳乐",
        "monthly_dna": "本月重点是把任务、周计划、周总结和管理看板打成一套稳定的产品闭环，优先解决可靠性与交互一致性。",
        "color": "#F59E0B",
    },
    "信息数据部": {
        "unit_id": "dept_info_data",
        "leader_name": "大周",
        "monthly_dna": "本月重点是把种子数据、标签治理、检索支撑和预测规则建立成稳定的数据分析体系，为管理判断提供可信依据。",
        "color": "#10B981",
    },
    "客户服务部": {
        "unit_id": "dept_customer_service",
        "leader_name": "嘉宁",
        "monthly_dna": "本月重点是把客户交付、资料回流、跨部门交接和服务节奏校准成一条更稳的客户服务链路。",
        "color": "#14B8A6",
    },
}

USER_DIRECTORY = {
    "庆华": {"user_id": "user_qinghua", "email": "qinghua@yiyu-system.com", "password": "Qinghua123!"},
    "苏妍": {"user_id": "user_sim_suyan", "email": "suyan@yiyu-system.com", "password": DEFAULT_SEED_PASSWORD},
    "晨曦": {"user_id": "user_sim_chenxi", "email": "chenxi@yiyu-system.com", "password": DEFAULT_SEED_PASSWORD},
    "奕鸣": {"user_id": "user_sim_yiming", "email": "yiming@yiyu-system.com", "password": DEFAULT_SEED_PASSWORD},
    "佳乐": {"user_id": "user_jiale", "email": "jiale@yiyu-system.com", "password": "Jiale123!"},
    "昊然": {"user_id": "user_sim_haoran", "email": "haoran@yiyu-system.com", "password": DEFAULT_SEED_PASSWORD},
    "林越": {"user_id": "user_sim_linyue", "email": "linyue@yiyu-system.com", "password": DEFAULT_SEED_PASSWORD},
    "君昊": {"user_id": "user_sim_junhao", "email": "junhao@yiyu-system.com", "password": DEFAULT_SEED_PASSWORD},
    "欣宁": {"user_id": "user_sim_xinning", "email": "xinning@yiyu-system.com", "password": DEFAULT_SEED_PASSWORD},
    "大周": {"user_id": "user_dazhou", "email": "dazhou@yiyu-system.com", "password": "Dazhou123!"},
    "罗茜茜": {"user_id": "user_sim_ruoxi", "email": "ruoxi@yiyu-system.com", "password": DEFAULT_SEED_PASSWORD},
    "柏辰": {"user_id": "user_sim_bochen", "email": "bochen@yiyu-system.com", "password": DEFAULT_SEED_PASSWORD},
    "舒婷": {"user_id": "user_sim_shuting", "email": "shuting@yiyu-system.com", "password": DEFAULT_SEED_PASSWORD},
    "嘉译": {"user_id": "user_sim_jiayi", "email": "jiayi@yiyu-system.com", "password": DEFAULT_SEED_PASSWORD},
    "一朔": {"user_id": "user_yishuo", "email": "yishuo@yiyu-system.com", "password": "Yishuo123!"},
    "嘉宁": {"user_id": "user_jianing", "email": "jianing@yiyu-system.com", "password": "Jianing123!"},
    "秋月": {"user_id": "user_sim_qiuyue", "email": "qiuyue@yiyu-system.com", "password": DEFAULT_SEED_PASSWORD},
    "泽宇": {"user_id": "user_sim_zeyu", "email": "zeyu@yiyu-system.com", "password": DEFAULT_SEED_PASSWORD},
    "瑶彤": {"user_id": "user_sim_yaotong", "email": "yaotong@yiyu-system.com", "password": DEFAULT_SEED_PASSWORD},
    "沐阳": {"user_id": "user_sim_muyang", "email": "muyang@yiyu-system.com", "password": DEFAULT_SEED_PASSWORD},
}


@dataclass(frozen=True)
class ImportedTask:
    task_id: str
    title: str
    customer_or_project: str
    priority: str
    due_date: str
    expected_output: str
    linked_goal: str
    status: str
    result: str
    reflection: str
    support_needed: str


@dataclass(frozen=True)
class ImportedEmployeeReview:
    name: str
    department: str
    manager: str
    role_type: str
    week: str
    linked_quarter_goals: tuple[str, ...]
    overall_status: str
    key_results: tuple[str, ...]
    key_learnings: tuple[str, ...]
    support_needed: tuple[str, ...]
    tasks: tuple[ImportedTask, ...]


def _slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    normalized = text.strip("_")
    if normalized:
        return normalized
    return f"u{hashlib.md5(value.encode('utf-8')).hexdigest()[:8]}"


def _iso_timestamp(day: date, hour: int, minute: int = 0) -> str:
    return datetime.combine(day, time(hour=hour, minute=minute)).replace(microsecond=0).isoformat()


def _week_label_from_range(range_text: str) -> str:
    start_text = str(range_text).split("~", 1)[0].strip()
    week_start = date.fromisoformat(start_text)
    iso = week_start.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _priority_to_level(value: str) -> str:
    normalized = str(value).strip().upper()
    if normalized == "P0":
        return "high"
    if normalized == "P2":
        return "low"
    return "normal"


def _review_status_to_task_status(value: str) -> str:
    normalized = str(value).strip()
    if normalized == "完成":
        return "done"
    if normalized in {"部分完成", "延后"}:
        return "doing"
    return "todo"


def _review_status_to_completion_status(value: str) -> str:
    normalized = str(value).strip()
    if normalized == "完成":
        return "done_on_time"
    if normalized == "部分完成":
        return "in_progress"
    if normalized == "延后":
        return "done_late"
    return "not_done"


def _alignment_for_task(status: str) -> tuple[str, str]:
    normalized = str(status).strip()
    if normalized == "完成":
        return "aligned", "aligned"
    if normalized == "部分完成":
        return "partial", "partial"
    if normalized == "延后":
        return "partial", "misaligned"
    return "misaligned", "misaligned"


def _infer_blocker_type(support_text: str, reflections: str) -> str:
    text = f"{support_text} {reflections}"
    if any(keyword in text for keyword in ("资料", "样本", "证据", "评论", "数据", "文档")):
        return "信息不足"
    if any(keyword in text for keyword in ("明确", "拍板", "优先级", "边界", "判断", "阈值", "标准", "方向")):
        return "决策卡住"
    if any(keyword in text for keyword in ("协助", "联调", "共享", "同步", "客户服务部", "信息数据部", "科技部", "策略部", "客户补资料", "客户反馈")):
        return "协作卡住"
    return "推进受阻"


def _task_list_id_for(employee: ImportedEmployeeReview, task: ImportedTask) -> str:
    if employee.department == "科技发展部":
        return "list-2"
    if employee.department == "信息数据部":
        return "list-3"
    if task.customer_or_project in {"内部管理", "组织看板", "分析模板", "预测分析", "压力测试", "内部支持"}:
        return "list-4"
    if task.customer_or_project in {"品牌内容", "市场支持"}:
        return "list-5"
    return "list-1"


def _task_tag_names(employee: ImportedEmployeeReview, task: ImportedTask) -> list[str]:
    names = [employee.department, task.customer_or_project, task.linked_goal]
    deduped: list[str] = []
    for name in names:
        cleaned = str(name).strip()
        if cleaned and cleaned not in deduped:
            deduped.append(cleaned)
    return deduped


def _ensure_task_lists(db: Database, organization_id: str) -> None:
    timestamp = datetime.now().replace(microsecond=0).isoformat()
    for list_id, name, color, sort_order, is_default in TASK_LIST_SPECS:
        exists = db.fetchone("SELECT id FROM task_lists WHERE id = ?", (list_id,))
        if exists:
            db.execute(
                """
                UPDATE task_lists
                SET organization_id = ?, name = ?, color = ?, sort_order = ?, is_default = ?, scope = 'org', archived_at = NULL
                WHERE id = ?
                """,
                (organization_id, name, color, sort_order, is_default, list_id),
            )
        else:
            db.execute(
                """
                INSERT INTO task_lists(id, organization_id, name, color, sort_order, is_default, scope, archived_at)
                VALUES(?, ?, ?, ?, ?, ?, 'org', NULL)
                """,
                (list_id, organization_id, name, color, sort_order, is_default),
            )
    db.execute("UPDATE task_lists SET is_default = CASE WHEN id = 'list-0' THEN 1 ELSE 0 END WHERE organization_id = ?", (organization_id,))
    db.execute("UPDATE task_lists SET archived_at = ? WHERE organization_id = ? AND id NOT IN ('list-0','list-1','list-2','list-3','list-4','list-5')", (timestamp, organization_id))


def _upsert_ceo_account(db: Database, organization_id: str, user_id: str, full_name: str) -> None:
    timestamp = datetime.now().replace(microsecond=0).isoformat()
    password_hash = hash_password("Guyuan123!")
    exists = db.fetchone("SELECT id FROM employee_accounts WHERE id = ?", (user_id,))
    if exists:
        db.execute(
            """
            UPDATE employee_accounts
            SET organization_id = ?, full_name = ?, email = COALESCE(NULLIF(email, ''), 'guyuan@klngo.org'),
                password_hash = COALESCE(NULLIF(password_hash, ''), ?), primary_role = 'admin',
                account_status = 'approved', approved_at = COALESCE(approved_at, ?),
                approved_by = COALESCE(approved_by, ?), updated_at = ?
            WHERE id = ?
            """,
            (organization_id, full_name, password_hash, timestamp, user_id, timestamp, user_id),
        )
    else:
        db.execute(
            """
            INSERT INTO employee_accounts(
                id, organization_id, email, full_name, password_hash, primary_role, account_status,
                approved_at, approved_by, rejected_reason, disabled_at, recent_mentions_json, last_login_at,
                department_id, department_name, created_at, updated_at
            ) VALUES(?, ?, 'guyuan@klngo.org', ?, ?, 'admin', 'approved', ?, ?, NULL, NULL, '[]', NULL, NULL, NULL, ?, ?)
            """,
            (user_id, organization_id, full_name, password_hash, timestamp, user_id, timestamp, timestamp),
        )
    if not db.fetchone("SELECT id FROM employee_role_bindings WHERE user_id = ? AND role = 'admin'", (user_id,)):
        db.execute(
            "INSERT INTO employee_role_bindings(id, user_id, role, created_at) VALUES(?, ?, 'admin', ?)",
            (f"role_{user_id}_admin", user_id, timestamp),
        )


def parse_pressure_seed_markdown(markdown_path: Path) -> list[ImportedEmployeeReview]:
    text = markdown_path.read_text(encoding="utf-8")
    blocks = re.findall(r"```yaml\n(.*?)\n```", text, flags=re.S)
    employees: list[ImportedEmployeeReview] = []
    for block in blocks:
        lines = block.splitlines()
        payload: dict[str, Any] = {}
        index = 0
        while index < len(lines):
            raw_line = lines[index]
            if not raw_line.strip():
                index += 1
                continue
            if _leading_spaces(raw_line) != 0 or ":" not in raw_line:
                index += 1
                continue
            key, value = raw_line.strip().split(":", 1)
            parsed_value = value.strip()
            if key == "linked_quarter_goals":
                payload[key] = _parse_inline_list(parsed_value)
                index += 1
                continue
            if key == "weekly_plan":
                items, index = _parse_dict_list(lines, index + 1, 2)
                payload[key] = items
                continue
            if key == "weekly_review":
                review_payload, index = _parse_weekly_review(lines, index + 1, 2)
                payload[key] = review_payload
                continue
            payload[key] = _parse_scalar(parsed_value)
            index += 1

        if "name" not in payload or "weekly_plan" not in payload or "weekly_review" not in payload:
            continue
        if not str(payload.get("name") or "").strip():
            continue
        weekly_review = payload.get("weekly_review") or {}
        if not isinstance(weekly_review, dict):
            continue
        review_tasks: dict[str, dict[str, Any]] = {}
        raw_review_tasks = weekly_review.get("tasks") or []
        if isinstance(raw_review_tasks, list):
            for item in raw_review_tasks:
                if isinstance(item, dict) and str(item.get("task_id") or "").strip():
                    review_tasks[str(item["task_id"]).strip()] = item

        imported_tasks: list[ImportedTask] = []
        raw_plan = payload.get("weekly_plan") or []
        if isinstance(raw_plan, list):
            for item in raw_plan:
                if not isinstance(item, dict):
                    continue
                task_id = str(item.get("task_id") or "").strip()
                if not task_id:
                    continue
                review_item = review_tasks.get(task_id, {})
                imported_tasks.append(
                    ImportedTask(
                        task_id=task_id,
                        title=str(item.get("title") or "").strip(),
                        customer_or_project=str(item.get("customer_or_project") or "").strip(),
                        priority=str(item.get("priority") or "P1").strip(),
                        due_date=str(item.get("due_date") or "").strip(),
                        expected_output=str(item.get("expected_output") or "").strip(),
                        linked_goal=str(item.get("linked_goal") or "").strip(),
                        status=str(review_item.get("status") or "未完成").strip(),
                        result=str(review_item.get("result") or "").strip(),
                        reflection=str(review_item.get("reflection") or "").strip(),
                        support_needed=str(review_item.get("support_needed") or "").strip(),
                    )
                )

        employees.append(
            ImportedEmployeeReview(
                name=str(payload.get("name") or "").strip(),
                department=str(payload.get("department") or "").strip(),
                manager=str(payload.get("manager") or "").strip(),
                role_type=str(payload.get("role_type") or "member").strip(),
                week=str(payload.get("week") or "").strip(),
                linked_quarter_goals=tuple(str(item).strip() for item in (payload.get("linked_quarter_goals") or []) if str(item).strip()),
                overall_status=str(weekly_review.get("overall_status") or "").strip(),
                key_results=tuple(str(item).strip() for item in (weekly_review.get("key_results") or []) if str(item).strip()),
                key_learnings=tuple(str(item).strip() for item in (weekly_review.get("key_learnings") or []) if str(item).strip()),
                support_needed=tuple(str(item).strip() for item in (weekly_review.get("support_needed") or []) if str(item).strip()),
                tasks=tuple(imported_tasks),
            )
        )
    return employees


def _backup_db(db_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = Path("/Users/guyuanyuan/.openclaw/workspace/tmp/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{db_path.name}.before-pressure-seed-{timestamp}"
    shutil.copy2(db_path, backup_path)
    wal_path = db_path.with_suffix(db_path.suffix + "-wal")
    shm_path = db_path.with_suffix(db_path.suffix + "-shm")
    if wal_path.exists():
        shutil.copy2(wal_path, backup_dir / f"{db_path.name}.before-pressure-seed-{timestamp}-wal")
    if shm_path.exists():
        shutil.copy2(shm_path, backup_dir / f"{db_path.name}.before-pressure-seed-{timestamp}-shm")
    return backup_path


def _parse_inline_list(value: str) -> list[str]:
    text = value.strip()
    if not (text.startswith("[") and text.endswith("]")):
        return [text] if text else []
    items = []
    for part in text[1:-1].split(","):
        cleaned = part.strip().strip("'").strip('"')
        if cleaned:
            items.append(cleaned)
    return items


def _leading_spaces(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _parse_scalar(value: str) -> str:
    return value.strip().strip("'").strip('"')


def _parse_string_list(lines: list[str], start_index: int, item_indent: int) -> tuple[list[str], int]:
    items: list[str] = []
    index = start_index
    while index < len(lines):
        raw_line = lines[index]
        if not raw_line.strip():
            index += 1
            continue
        indent = _leading_spaces(raw_line)
        stripped = raw_line.strip()
        if indent < item_indent or not stripped.startswith("- "):
            break
        items.append(_parse_scalar(stripped[2:]))
        index += 1
    return items, index


def _parse_dict_list(lines: list[str], start_index: int, item_indent: int) -> tuple[list[dict[str, str]], int]:
    items: list[dict[str, str]] = []
    index = start_index
    current: dict[str, str] | None = None
    while index < len(lines):
        raw_line = lines[index]
        if not raw_line.strip():
            index += 1
            continue
        indent = _leading_spaces(raw_line)
        stripped = raw_line.strip()
        if indent < item_indent:
            break
        if indent == item_indent and stripped.startswith("- "):
            if current:
                items.append(current)
            current = {}
            payload = stripped[2:]
            if payload and ":" in payload:
                key, value = payload.split(":", 1)
                current[key.strip()] = _parse_scalar(value)
            index += 1
            continue
        if current is None or indent < item_indent + 2 or ":" not in stripped:
            break
        key, value = stripped.split(":", 1)
        current[key.strip()] = _parse_scalar(value)
        index += 1
    if current:
        items.append(current)
    return items, index


def _parse_weekly_review(lines: list[str], start_index: int, base_indent: int) -> tuple[dict[str, Any], int]:
    payload: dict[str, Any] = {}
    index = start_index
    while index < len(lines):
        raw_line = lines[index]
        if not raw_line.strip():
            index += 1
            continue
        indent = _leading_spaces(raw_line)
        if indent < base_indent:
            break
        if indent != base_indent or ":" not in raw_line.strip():
            break
        key, value = raw_line.strip().split(":", 1)
        parsed_value = value.strip()
        if key in {"key_results", "key_learnings", "support_needed"}:
            items, index = _parse_string_list(lines, index + 1, base_indent + 2)
            payload[key] = items
            continue
        if key == "tasks":
            items, index = _parse_dict_list(lines, index + 1, base_indent + 2)
            payload[key] = items
            continue
        payload[key] = _parse_scalar(parsed_value)
        index += 1
    return payload, index


def _ensure_org_units(
    db: Database,
    organization_id: str,
    ceo_user_id: str,
    timestamp: str,
    departments: list[str],
) -> None:
    db.execute(
        """
        INSERT OR REPLACE INTO org_units(id, organization_id, parent_id, name, unit_type, leader_user_id, created_at, updated_at)
        VALUES('unit_org', ?, NULL, '益语智库', 'organization', ?, ?, ?)
        """,
        (organization_id, ceo_user_id, timestamp, timestamp),
    )
    for department_name in departments:
        spec = DEPARTMENT_SPECS[department_name]
        leader_user_id = USER_DIRECTORY[str(spec["leader_name"])]["user_id"]
        db.execute(
            """
            INSERT OR REPLACE INTO org_units(id, organization_id, parent_id, name, unit_type, leader_user_id, created_at, updated_at)
            VALUES(?, ?, 'unit_org', ?, 'department', ?, ?, ?)
            """,
            (str(spec["unit_id"]), organization_id, department_name, leader_user_id, timestamp, timestamp),
        )


def _ensure_reporting_lines(db: Database, organization_id: str, employees: list[ImportedEmployeeReview], ceo_user_id: str, timestamp: str) -> None:
    db.execute("DELETE FROM reporting_lines WHERE organization_id = ?", (organization_id,))
    seen: set[tuple[str, str]] = set()
    for department_name in sorted({employee.department for employee in employees}):
        spec = DEPARTMENT_SPECS[department_name]
        leader_user_id = USER_DIRECTORY[str(spec["leader_name"])]["user_id"]
        db.execute(
            """
            INSERT INTO reporting_lines(id, organization_id, manager_user_id, report_user_id, relationship_type, effective_from, effective_to, created_at)
            VALUES(?, ?, ?, ?, 'direct', ?, NULL, ?)
            """,
            (f"line_{ceo_user_id}_{leader_user_id}", organization_id, ceo_user_id, leader_user_id, timestamp[:10], timestamp),
        )
        seen.add((ceo_user_id, leader_user_id))

    for employee in employees:
        user_id = USER_DIRECTORY[employee.name]["user_id"]
        manager_user_id = USER_DIRECTORY[employee.manager]["user_id"]
        if user_id == manager_user_id or (manager_user_id, user_id) in seen:
            continue
        db.execute(
            """
            INSERT INTO reporting_lines(id, organization_id, manager_user_id, report_user_id, relationship_type, effective_from, effective_to, created_at)
            VALUES(?, ?, ?, ?, 'direct', ?, NULL, ?)
            """,
            (f"line_{manager_user_id}_{user_id}", organization_id, manager_user_id, user_id, timestamp[:10], timestamp),
        )
        seen.add((manager_user_id, user_id))


def _ensure_plan_nodes(
    db: Database,
    organization_id: str,
    employees: list[ImportedEmployeeReview],
    week_label: str,
    ceo_user_id: str,
    timestamp: str,
) -> dict[str, str]:
    week_slug = week_label.lower().replace("-", "_")
    department_managers = {employee.department: employee for employee in employees if employee.role_type == "manager"}
    plan_ids: dict[str, str] = {}
    db.execute("DELETE FROM plan_nodes WHERE organization_id = ? AND id LIKE 'pressure_%'", (organization_id,))
    plan_ids["org_week"] = f"pressure_org_week_{week_slug}"
    db.execute(
        """
        INSERT INTO plan_nodes(id, organization_id, owner_user_id, owner_unit_id, level, title, summary, status, starts_at, ends_at, created_at, updated_at)
        VALUES(?, ?, ?, 'unit_org', 'ceo', ?, ?, 'active', ?, ?, ?, ?)
        """,
        (
            plan_ids["org_week"],
            organization_id,
            ceo_user_id,
            f"{week_label} 组织主线",
            "本周重点是验证任务系统是否能同时支撑协作执行、部门判断和组织级趋势预测。",
            timestamp[:10],
            timestamp[:10],
            timestamp,
            timestamp,
        ),
    )
    for goal_id, summary in QUARTER_GOAL_SUMMARIES.items():
        plan_id = f"pressure_{goal_id.lower().replace('-', '_')}"
        plan_ids[goal_id] = plan_id
        db.execute(
            """
            INSERT INTO plan_nodes(id, organization_id, owner_user_id, owner_unit_id, level, title, summary, status, starts_at, ends_at, created_at, updated_at)
            VALUES(?, ?, ?, 'unit_org', 'ceo', ?, ?, 'active', ?, ?, ?, ?)
            """,
            (
                plan_id,
                organization_id,
                ceo_user_id,
                goal_id,
                summary,
                timestamp[:10],
                timestamp[:10],
                timestamp,
                timestamp,
            ),
        )
    for department_name, manager in department_managers.items():
        spec = DEPARTMENT_SPECS[department_name]
        plan_id = f"pressure_{_slugify(department_name)}_{week_slug}"
        plan_ids[f"dept::{department_name}"] = plan_id
        summary = "；".join(task.title for task in manager.tasks) or str(spec["monthly_dna"])
        db.execute(
            """
            INSERT INTO plan_nodes(id, organization_id, owner_user_id, owner_unit_id, level, title, summary, status, starts_at, ends_at, created_at, updated_at)
            VALUES(?, ?, ?, ?, 'director', ?, ?, 'active', ?, ?, ?, ?)
            """,
            (
                plan_id,
                organization_id,
                USER_DIRECTORY[manager.name]["user_id"],
                str(spec["unit_id"]),
                f"{department_name} 本周计划",
                summary,
                timestamp[:10],
                timestamp[:10],
                timestamp,
                timestamp,
            ),
        )
    return plan_ids


def _reset_existing_operational_data(db: Database, organization_id: str) -> None:
    db.execute(
        "DELETE FROM report_action_cards WHERE report_id IN (SELECT id FROM aggregated_scope_reports WHERE organization_id = ?)",
        (organization_id,),
    )
    db.execute("DELETE FROM aggregated_scope_reports WHERE organization_id = ?", (organization_id,))
    db.execute("DELETE FROM management_signal_cards WHERE organization_id = ?", (organization_id,))
    db.execute("DELETE FROM personal_growth_cards WHERE organization_id = ?", (organization_id,))
    db.execute("DELETE FROM weekly_review_sections WHERE review_id IN (SELECT id FROM weekly_review_entries WHERE organization_id = ?)", (organization_id,))
    db.execute("DELETE FROM weekly_review_task_entries WHERE organization_id = ?", (organization_id,))
    db.execute("DELETE FROM weekly_review_entries WHERE organization_id = ?", (organization_id,))
    db.execute("DELETE FROM tasks WHERE organization_id = ?", (organization_id,))


def _extract_support_user_ids(texts: list[str], exclude_user_ids: set[str]) -> list[str]:
    matched: list[str] = []
    for text in texts:
        for name, directory in USER_DIRECTORY.items():
            if name in text and directory["user_id"] not in exclude_user_ids and directory["user_id"] not in matched:
                matched.append(directory["user_id"])
    return matched


def seed_task_pressure_doc(
    db: Database,
    *,
    markdown_path: Path,
    organization_id: str,
    ceo_user_id: str = "user_guyuan",
    ceo_name: str = "顾源源",
    replace_all: bool = True,
    expected_employee_count: int | None = 20,
) -> dict[str, Any]:
    employees = parse_pressure_seed_markdown(markdown_path)
    if expected_employee_count is not None and len(employees) != expected_employee_count:
        raise ValueError(f"Expected {expected_employee_count} employee blocks, got {len(employees)}")
    week_labels = { _week_label_from_range(employee.week) for employee in employees }
    if len(week_labels) != 1:
        raise ValueError(f"Inconsistent week labels: {sorted(week_labels)}")
    week_label = next(iter(week_labels))
    timestamp = datetime.now().replace(microsecond=0).isoformat()

    _upsert_ceo_account(db, organization_id, ceo_user_id, ceo_name)
    _ensure_task_lists(db, organization_id)

    if replace_all:
        _reset_existing_operational_data(db, organization_id)

    for employee in employees:
        if employee.name not in USER_DIRECTORY:
            raise ValueError(f"Unknown employee mapping for {employee.name}")
        if employee.department not in DEPARTMENT_SPECS:
            raise ValueError(f"Unknown department {employee.department}")
        user_spec = USER_DIRECTORY[employee.name]
        dept_spec = DEPARTMENT_SPECS[employee.department]
        _upsert_employee(
            db,
            organization_id=organization_id,
            user_id=str(user_spec["user_id"]),
            full_name=employee.name,
            email=str(user_spec["email"]),
            password=str(user_spec["password"]),
            department_id=str(dept_spec["unit_id"]),
            department_name=employee.department,
            primary_role="employee",
        )

    _ensure_org_units(
        db,
        organization_id,
        ceo_user_id,
        timestamp,
        departments=sorted({employee.department for employee in employees}),
    )
    _ensure_reporting_lines(db, organization_id, employees, ceo_user_id, timestamp)
    plan_ids = _ensure_plan_nodes(db, organization_id, employees, week_label, ceo_user_id, timestamp)

    tag_cache: dict[str, dict[str, str | None]] = {}
    for tag_name, color in [
        ("咨询策略部", "#5B7BFE"),
        ("科技发展部", "#F59E0B"),
        ("信息数据部", "#10B981"),
        ("客户服务部", "#14B8A6"),
        ("Q1-G1", "#1D4ED8"),
        ("Q1-G2", "#7C3AED"),
        ("Q1-G3", "#DB2777"),
        ("Q1-G4", "#0F766E"),
    ]:
        tag_cache[tag_name] = _ensure_tag(db, organization_id=organization_id, name=tag_name, color=color)

    seeded_tasks = 0
    seeded_reviews = 0
    seeded_review_items = 0
    department_breakdown: dict[str, int] = defaultdict(int)
    known_names = {name: spec["user_id"] for name, spec in USER_DIRECTORY.items()}

    for employee_index, employee in enumerate(employees):
        employee_user_id = str(USER_DIRECTORY[employee.name]["user_id"])
        manager_user_id = str(USER_DIRECTORY[employee.manager]["user_id"])
        department_spec = DEPARTMENT_SPECS[employee.department]
        department_plan_id = plan_ids[f"dept::{employee.department}"]
        related_plan_ids = [department_plan_id, plan_ids["org_week"], *[plan_ids[goal] for goal in employee.linked_quarter_goals if goal in plan_ids]]
        review_id = f"pressure_review_{employee_user_id}_{week_label.lower().replace('-', '_')}"
        submitted_at = _iso_timestamp(date.fromisoformat(employee.tasks[-1].due_date if employee.tasks else employee.week.split('~', 1)[-1].strip()), 20, employee_index % 10)
        work_progress = f"{employee.overall_status}。关键结果：{'；'.join(employee.key_results)}"
        blocker_candidates = [task.support_needed for task in employee.tasks if task.status != "完成" and task.support_needed] or list(employee.support_needed)
        blocker_reflections = "；".join(task.reflection for task in employee.tasks if task.status != "完成" and task.reflection)
        work_blocker = "；".join(blocker_candidates[:2]) if blocker_candidates else "本周没有额外阻塞说明。"
        db.execute(
            """
            INSERT INTO weekly_review_entries(
                id, organization_id, user_id, week_label, work_progress, work_blocker, blocker_type, work_direction,
                next_week_focus, support_needed, related_plan_ids_json, work_free_note, personal_growth_note,
                personal_private_note, personal_visibility, submitted_at, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', 'self', ?, ?, ?)
            """,
            (
                review_id,
                organization_id,
                employee_user_id,
                week_label,
                work_progress,
                work_blocker,
                _infer_blocker_type(work_blocker, blocker_reflections),
                f"本周主要支撑 {' / '.join(employee.linked_quarter_goals)}，并围绕{employee.department}职责推进。",
                "；".join(task.title for task in employee.tasks if task.status != "完成") or "继续维持当前有效推进节奏。",
                "；".join(employee.support_needed),
                to_json(related_plan_ids),
                "；".join([employee.overall_status, *employee.key_results, *employee.key_learnings]),
                "；".join(employee.key_learnings),
                submitted_at,
                submitted_at,
                submitted_at,
            ),
        )
        seeded_reviews += 1
        department_breakdown[employee.department] += 1

        section_lines: list[str] = []
        for task_index, task in enumerate(employee.tasks):
            due_date = date.fromisoformat(task.due_date)
            list_id = _task_list_id_for(employee, task)
            collaborator_owner_id = employee_user_id
            creator_user_id = ceo_user_id if employee.role_type == "manager" else manager_user_id
            task_id = task.task_id
            tag_names = _task_tag_names(employee, task)
            tag_records = []
            for tag_name in tag_names:
                if tag_name not in tag_cache:
                    color = DEPARTMENT_SPECS[employee.department]["color"] if tag_name == employee.department else "#64748B"
                    tag_cache[tag_name] = _ensure_tag(db, organization_id=organization_id, name=tag_name, color=str(color))
                tag_records.append(tag_cache[tag_name])
            created_at = _iso_timestamp(due_date, 9, task_index * 7)
            updated_at = _iso_timestamp(due_date, 18, task_index * 5)
            description = (
                f"{task.customer_or_project}｜预期输出：{task.expected_output}｜关联目标：{task.linked_goal}。"
                f"周结果：{task.result or '待补充'}"
            )
            db.execute(
                """
                INSERT INTO tasks(
                    id, organization_id, title, description, creator_id, owner_id, due_date, priority, list_id,
                    progress_status, source_type, source_id, tags_json, tag_ids_json, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    organization_id,
                    task.title,
                    description,
                    creator_user_id,
                    collaborator_owner_id,
                    task.due_date,
                    _priority_to_level(task.priority),
                    list_id,
                    _review_status_to_task_status(task.status),
                    PRESSURE_SEED_SOURCE_TYPE,
                    employee.department,
                    to_json([record["name"] for record in tag_records]),
                    to_json([record["id"] for record in tag_records]),
                    created_at,
                    updated_at,
                ),
            )
            collaborator_rows: list[tuple[Any, ...]] = [
                (task_id, collaborator_owner_id, 0, 1, "accepted", None, created_at, created_at, updated_at),
            ]
            excluded = {collaborator_owner_id}
            if creator_user_id != collaborator_owner_id:
                collaborator_rows.append((task_id, creator_user_id, 1, 0, "accepted", None, created_at, created_at, updated_at))
                excluded.add(creator_user_id)
            support_user_ids = _extract_support_user_ids(
                [task.support_needed, *employee.support_needed, task.reflection],
                exclude_user_ids=excluded,
            )
            for order_index, support_user_id in enumerate(support_user_ids, start=len(collaborator_rows)):
                if not db.fetchone("SELECT id FROM employee_accounts WHERE id = ?", (support_user_id,)):
                    continue
                collaborator_rows.append((task_id, support_user_id, order_index, 0, "pending", None, None, created_at, updated_at))
            db.executemany(
                """
                INSERT INTO task_collaborators(
                    task_id, user_id, order_index, is_owner, inbox_status, return_reason, handled_at, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                collaborator_rows,
            )
            db.execute(
                """
                INSERT INTO task_activity_events(id, task_id, actor_id, event_type, payload_json, created_at)
                VALUES(?, ?, ?, 'created', ?, ?)
                """,
                (f"activity_create_{task_id}", task_id, creator_user_id, to_json({"sourceType": PRESSURE_SEED_SOURCE_TYPE}), created_at),
            )
            db.execute(
                """
                INSERT INTO task_activity_events(id, task_id, actor_id, event_type, payload_json, created_at)
                VALUES(?, ?, ?, 'reviewed', ?, ?)
                """,
                (
                    f"activity_review_{task_id}",
                    task_id,
                    collaborator_owner_id,
                    to_json({"status": task.status, "result": task.result, "supportNeeded": task.support_needed}),
                    updated_at,
                ),
            )

            department_alignment, organization_alignment = _alignment_for_task(task.status)
            snapshot = {
                "title": task.title,
                "status": _review_status_to_task_status(task.status),
                "dueDate": task.due_date,
                "createdAt": created_at,
                "ownerId": collaborator_owner_id,
                "ownerName": employee.name,
                "tags": tag_records,
                "listName": next(spec[1] for spec in TASK_LIST_SPECS if spec[0] == list_id),
                "listColor": next(spec[2] for spec in TASK_LIST_SPECS if spec[0] == list_id),
            }
            structured_note = {
                "planCommitment": f"本周完成《{task.title}》并产出{task.expected_output}",
                "progress": task.result,
                "completionStatus": _review_status_to_completion_status(task.status),
                "departmentPlanId": department_plan_id,
                "departmentPlanAlignment": department_alignment,
                "organizationPlanId": plan_ids.get(task.linked_goal),
                "organizationPlanAlignment": organization_alignment,
                "successReason": task.reflection if task.status == "完成" else "",
                "successExperience": task.reflection if task.status == "完成" else "",
                "blockerReason": task.support_needed if task.status != "完成" else "",
                "failureInsight": task.reflection if task.status != "完成" else "",
                "supportNeeded": task.support_needed,
                "nextAction": f"围绕《{task.title}》继续收口下一轮动作，并校准对 {task.linked_goal} 的支撑。",
            }
            db.execute(
                """
                INSERT INTO weekly_review_task_entries(
                    id, organization_id, review_id, user_id, task_id, week_label, content_domain, note, structured_note_json, reviewed_at, task_snapshot_json, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, 'work', ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"review_item_{task_id}",
                    organization_id,
                    review_id,
                    employee_user_id,
                    task_id,
                    week_label,
                    task.result,
                    to_json(structured_note),
                    updated_at,
                    to_json(snapshot),
                    updated_at,
                    updated_at,
                ),
            )
            section_lines.append(f"{task.title}｜{task.status}｜{task.result}｜复盘：{task.reflection}")
            seeded_tasks += 1
            seeded_review_items += 1

        db.execute(
            """
            INSERT INTO weekly_review_sections(id, review_id, section_type, content, content_domain, visibility_scope, created_at)
            VALUES(?, ?, 'work', ?, 'work', 'team', ?)
            """,
            (f"section_{review_id}", review_id, "\n".join(section_lines), submitted_at),
        )

    return {
        "weekLabel": week_label,
        "employeeCount": len(employees),
        "departmentCount": len({employee.department for employee in employees}),
        "taskCount": seeded_tasks,
        "reviewCount": seeded_reviews,
        "reviewItemCount": seeded_review_items,
        "departmentBreakdown": dict(department_breakdown),
    }


def import_task_pressure_seed_to_db(
    *,
    db_path: Path,
    markdown_path: Path,
    organization_id: str,
    ceo_user_id: str = "user_guyuan",
    ceo_name: str = "顾源源",
    replace_all: bool = True,
) -> dict[str, Any]:
    backup_path = _backup_db(db_path)
    db = Database(db_path)
    summary = seed_task_pressure_doc(
        db,
        markdown_path=markdown_path,
        organization_id=organization_id,
        ceo_user_id=ceo_user_id,
        ceo_name=ceo_name,
        replace_all=replace_all,
        expected_employee_count=20,
    )
    summary["backupPath"] = str(backup_path)
    summary["dbPath"] = str(db_path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="导入任务与日程 20 人压力测试种子数据")
    parser.add_argument("--db", required=True, help="cloud.db 路径")
    parser.add_argument("--markdown", required=True, help="压力测试 markdown 路径")
    parser.add_argument("--organization-id", default="org_yiyu_default")
    parser.add_argument("--ceo-user-id", default="user_guyuan")
    parser.add_argument("--ceo-name", default="顾源源")
    parser.add_argument("--no-replace-all", action="store_true", help="不清空现有任务/周复盘，仅追加或覆盖同 ID 数据")
    args = parser.parse_args()

    summary = import_task_pressure_seed_to_db(
        db_path=Path(args.db),
        markdown_path=Path(args.markdown),
        organization_id=args.organization_id,
        ceo_user_id=args.ceo_user_id,
        ceo_name=args.ceo_name,
        replace_all=not args.no_replace_all,
    )
    print(summary)


if __name__ == "__main__":
    main()
~~~

## `cloud_backend/pyproject.toml`

- 编码: `utf-8`

~~~toml
[project]
name = "yiyu-workbench-cloud-backend"
version = "0.1.0"
description = "益语智库自用平台中心认证与协作任务后端"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn>=0.30.0",
    "pydantic>=2.9.0",
    "httpx>=0.27.0",
    "lark-oapi>=1.4.18",
    "email-validator>=2.2.0",
    "python-multipart>=0.0.9",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "pytest>=8.3.0",
    "chromadb>=0.5.0",
    "python-docx>=1.1.0"
]

[tool.pytest.ini_options]
pythonpath = ["."]
~~~

## `cloud_backend/requirements.deploy.txt`

- 编码: `utf-8`

~~~text
fastapi>=0.111.0
uvicorn>=0.30.0
pydantic>=2.9.0
httpx>=0.27.0
lark-oapi>=1.4.18
email-validator>=2.2.0
python-multipart>=0.0.9
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
chromadb>=0.5.0
Pillow>=10.0.0
~~~

## `cloud_backend/tests/test_auth_refresh.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app  # noqa: E402


def test_refresh_token_rotates_and_restores_session(tmp_path, monkeypatch):
    data_dir = tmp_path / "cloud-data"
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Qinghua123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Jianing123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Yishuo123!")

    app = create_app()
    client = TestClient(app)

    login = client.post("/api/v1/auth/login", json={"email": "admin@yiyu-system.com", "password": "Admin123!"})
    assert login.status_code == 200, login.text
    login_payload = login.json()
    first_access = login_payload["accessToken"]
    first_refresh = login_payload["refreshToken"]
    assert first_refresh

    refreshed = client.post("/api/v1/auth/refresh", json={"refreshToken": first_refresh})
    assert refreshed.status_code == 200, refreshed.text
    refreshed_payload = refreshed.json()
    second_access = refreshed_payload["accessToken"]
    second_refresh = refreshed_payload["refreshToken"]

    assert second_access
    assert second_refresh
    assert second_refresh != first_refresh

    stale_refresh = client.post("/api/v1/auth/refresh", json={"refreshToken": first_refresh})
    assert stale_refresh.status_code == 401, stale_refresh.text

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {second_access}"})
    assert me.status_code == 200, me.text
    assert me.json()["email"] == "admin@yiyu-system.com"
~~~

## `cloud_backend/tests/test_auth_register.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import DEFAULT_ORG_ID, create_app  # noqa: E402
from app.security import hash_password  # noqa: E402


def test_register_returns_tokens_and_allows_immediate_login(tmp_path, monkeypatch):
    data_dir = tmp_path / "cloud-data"
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Qinghua123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Jianing123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Yishuo123!")

    client = TestClient(create_app())

    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": "new-personal-user@example.com",
            "fullName": "个人注册用户",
            "password": "Password123!",
        },
    )
    assert register.status_code == 200, register.text
    payload = register.json()
    assert payload["accessToken"]
    assert payload["refreshToken"]
    assert payload["user"]["email"] == "new-personal-user@example.com"
    assert payload["user"]["accountStatus"] == "approved"

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "new-personal-user@example.com",
            "password": "Password123!",
        },
    )
    assert login.status_code == 200, login.text
    assert login.json()["user"]["email"] == "new-personal-user@example.com"


def test_legacy_pending_account_can_login_without_manual_approval(tmp_path, monkeypatch):
    data_dir = tmp_path / "cloud-data"
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Qinghua123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Jianing123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Yishuo123!")

    app = create_app()
    db = app.state.app_state.db
    db.execute(
        """
        INSERT INTO employee_accounts(
            id, organization_id, email, full_name, password_hash, primary_role, account_status,
            approved_at, approved_by, rejected_reason, disabled_at, recent_mentions_json, last_login_at,
            department_id, department_name, job_title, manager_name, current_focus, is_department_lead, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, 'employee', 'pending', NULL, NULL, NULL, NULL, '[]', NULL, NULL, NULL, NULL, NULL, '', 0, ?, ?)
        """,
        (
            "emp_legacy_pending",
            DEFAULT_ORG_ID,
            "legacy-pending@example.com",
            "旧待审核用户",
            hash_password("Password123!"),
            "2026-04-07T00:00:00",
            "2026-04-07T00:00:00",
        ),
    )
    client = TestClient(app)

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "legacy-pending@example.com",
            "password": "Password123!",
        },
    )
    assert login.status_code == 200, login.text
    assert login.json()["user"]["accountStatus"] == "approved"

    row = db.fetchone("SELECT account_status, approved_at FROM employee_accounts WHERE id = ?", ("emp_legacy_pending",))
    assert row is not None
    assert row["account_status"] == "approved"
    assert row["approved_at"]
~~~

## `cloud_backend/tests/test_auth_tasks.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

TEST_DATA_DIR = Path(__file__).resolve().parent / "test_cloud_data"
os.environ["YIYU_CLOUD_DATA_DIR"] = str(TEST_DATA_DIR)
os.environ["YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD"] = "Admin123!"
os.environ["YIYU_CLOUD_QINGHUA_PASSWORD"] = "Qinghua123!"
os.environ["YIYU_CLOUD_JIANING_PASSWORD"] = "Jianing123!"
os.environ["YIYU_CLOUD_YISHUO_PASSWORD"] = "Yishuo123!"
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import main as cloud_main  # noqa: E402
from app.main import create_app, now_iso  # noqa: E402


def setup_function():
    os.environ["YIYU_CLOUD_DATA_DIR"] = str(TEST_DATA_DIR)
    if TEST_DATA_DIR.exists():
        for child in TEST_DATA_DIR.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    else:
        TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)


def teardown_function():
    if TEST_DATA_DIR.exists():
        for child in TEST_DATA_DIR.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()


def auth_headers(client: TestClient, email: str = "admin@yiyu-system.com", password: str = "Admin123!"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_register_approve_login_and_collaboration_flow():
    app = create_app()
    client = TestClient(app)

    department_options = client.get("/api/v1/auth/department-options")
    assert department_options.status_code == 200, department_options.text
    assert any(item["id"] == "dept_consult_strategy" for item in department_options.json())

    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": "new-user@yiyu-system.com",
            "fullName": "新成员",
            "password": "Password123!",
            "departmentId": "dept_customer_service",
            "jobTitle": "客户成功专员",
            "managerName": "顾源源",
            "currentFocus": "先熟悉客户服务流程与常用资料库",
            "isDepartmentLead": False,
        },
    )
    assert register.status_code == 200, register.text

    pending_login = client.post("/api/v1/auth/login", json={"email": "new-user@yiyu-system.com", "password": "Password123!"})
    assert pending_login.status_code == 403

    admin_headers = auth_headers(client)
    employees = client.get("/api/v1/admin/employees", headers=admin_headers)
    pending_user = next(item for item in employees.json() if item["email"] == "new-user@yiyu-system.com")
    assert pending_user["departmentId"] == "dept_customer_service"
    assert pending_user["departmentName"] == "客户服务部"
    assert pending_user["jobTitle"] == "客户成功专员"
    assert pending_user["managerName"] == "顾源源"
    assert pending_user["currentFocus"] == "先熟悉客户服务流程与常用资料库"
    assert pending_user["isDepartmentLead"] is False

    approve = client.post(
        f"/api/v1/admin/employees/{pending_user['id']}/approve",
        json={"role": "employee"},
        headers=admin_headers,
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["departmentId"] == "dept_customer_service"
    org_profile = client.get("/api/v1/settings/org-model/profile", headers=admin_headers)
    assert org_profile.status_code == 200, org_profile.text
    approved_binding = next(item for item in org_profile.json()["bindings"] if item["userId"] == pending_user["id"])
    assert approved_binding["departmentId"] == "dept_customer_service"
    assert approved_binding["primaryRoleId"] == "role_cs_member"
    assert approved_binding["managerUserId"] == "user_guyuan"
    assert approved_binding["currentFocus"] == "先熟悉客户服务流程与常用资料库"
    assert approved_binding["projectRoleLabels"] == ["客户成功专员"]
    assert approved_binding["isManager"] is False
    approved_line = next(item for item in org_profile.json()["reportingLines"] if item["reportUserId"] == pending_user["id"])
    assert approved_line["managerUserId"] == "user_guyuan"
    assert approved_line["lineType"] == "business"

    patch_department = client.patch(
        f"/api/v1/admin/employees/{pending_user['id']}/department",
        json={"departmentId": "dept_info_data"},
        headers=admin_headers,
    )
    assert patch_department.status_code == 200, patch_department.text
    assert patch_department.json()["departmentName"] == "信息数据部"
    org_profile_after_patch = client.get("/api/v1/settings/org-model/profile", headers=admin_headers)
    assert org_profile_after_patch.status_code == 200, org_profile_after_patch.text
    patched_binding = next(item for item in org_profile_after_patch.json()["bindings"] if item["userId"] == pending_user["id"])
    assert patched_binding["departmentId"] == "dept_info_data"
    assert patched_binding["primaryRoleId"] == "role_info_member"
    assert patched_binding["managerUserId"] == "user_guyuan"
    assert patched_binding["projectRoleLabels"] == ["客户成功专员"]

    user_headers = auth_headers(client, "new-user@yiyu-system.com", "Password123!")
    directory = client.get("/api/v1/employees/directory", headers=user_headers)
    assert directory.status_code == 200, directory.text
    assert any(item["id"] == pending_user["id"] and item["departmentId"] == "dept_info_data" for item in directory.json())
    candidates = client.get("/api/v1/employees/mention-candidates", headers=user_headers)
    assert candidates.status_code == 200
    assert candidates.json()[0]["isSelf"] is True
    assert len(candidates.json()) >= 3
    assert any(item["id"] == "user_qinghua" for item in candidates.json())

    task = client.post(
        "/api/v1/tasks",
        json={
            "title": "【测试】多人协作任务",
            "description": "请一起跟进",
            "priority": "high",
            "listId": "list-0",
            "dueDate": "2026-03-20T14:30",
            "clientId": "client_demo_yellow_river",
            "projectModuleId": "module_client_delivery",
            "projectFlowId": "flow_weekly_sync",
            "collaboratorIds": [pending_user["id"], "user_qinghua", "user_jianing"],
            "tags": ["会议", "紧急"],
        },
        headers=user_headers,
    )
    assert task.status_code == 200, task.text
    body = task.json()
    assert body["dueDate"] == "2026-03-20T14:30"
    assert body["clientId"] == "client_demo_yellow_river"
    assert body["projectModuleId"] == "module_client_delivery"
    assert body["projectFlowId"] == "flow_weekly_sync"
    assert body["ownerId"] == pending_user["id"]
    assert len(body["collaborators"]) == 3

    updated = client.patch(
        f"/api/v1/tasks/{body['id']}",
        json={
            "clientId": "client_demo_for_love",
            "projectModuleId": "module_strategy_review",
            "projectFlowId": "flow_risk_review",
            "priority": "normal",
        },
        headers=user_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["clientId"] == "client_demo_for_love"
    assert updated.json()["projectModuleId"] == "module_strategy_review"
    assert updated.json()["projectFlowId"] == "flow_risk_review"

    qinghua_headers = auth_headers(client, "qinghua@yiyu-system.com", "Qinghua123!")
    accepted = client.post(
        f"/api/v1/tasks/{body['id']}/collaborators/user_qinghua/accept",
        headers=qinghua_headers,
    )
    assert accepted.status_code == 200, accepted.text

    collaborator_update = client.patch(
        f"/api/v1/tasks/{body['id']}",
        json={
            "title": "【测试】协作者已调整标题",
            "ownerId": "user_qinghua",
        },
        headers=qinghua_headers,
    )
    assert collaborator_update.status_code == 200, collaborator_update.text
    assert collaborator_update.json()["title"] == "【测试】协作者已调整标题"
    assert collaborator_update.json()["ownerId"] == "user_qinghua"

    jianing_headers = auth_headers(client, "jianing@yiyu-system.com", "Jianing123!")
    returned = client.post(
        f"/api/v1/tasks/{body['id']}/collaborators/user_jianing/return",
        json={"reason": "当前优先级冲突，需要重新排期"},
        headers=jianing_headers,
    )
    assert returned.status_code == 200, returned.text
    assert any(item["inboxStatus"] == "returned" for item in returned.json()["collaborators"])

    activity = client.get(f"/api/v1/tasks/{body['id']}/activity", headers=user_headers)
    assert activity.status_code == 200
    event_types = [item["eventType"] for item in activity.json()]
    assert "accepted" in event_types
    assert "returned" in event_types


def test_mention_candidates_fill_recent_gap_with_other_approved_employees():
    app = create_app()
    client = TestClient(app)

    headers = auth_headers(client, "jianing@yiyu-system.com", "Jianing123!")
    response = client.get("/api/v1/employees/mention-candidates", headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload[0]["id"] == "user_jianing"
    assert payload[0]["isSelf"] is True
    assert any(item["id"] == "user_qinghua" for item in payload)
    assert any(item["id"] == "user_yishuo" for item in payload)


def test_collaborator_can_update_task_content_and_owner():
    app = create_app()
    client = TestClient(app)

    qinghua_headers = auth_headers(client, "qinghua@yiyu-system.com", "Qinghua123!")
    jianing_headers = auth_headers(client, "jianing@yiyu-system.com", "Jianing123!")

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "协作者权限测试任务",
            "description": "初始描述",
            "priority": "normal",
            "listId": "list-0",
            "dueDate": "2026-03-20",
            "collaboratorIds": ["user_jianing"],
            "ownerId": "user_qinghua",
        },
        headers=qinghua_headers,
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["id"]

    accept = client.post(
        f"/api/v1/tasks/{task_id}/collaborators/user_jianing/accept",
        headers=jianing_headers,
    )
    assert accept.status_code == 200, accept.text

    updated = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={
            "title": "协作者已修改标题",
            "description": "协作者已修改描述",
            "ownerId": "user_jianing",
        },
        headers=jianing_headers,
    )
    assert updated.status_code == 200, updated.text
    payload = updated.json()
    assert payload["title"] == "协作者已修改标题"
    assert payload["description"] == "协作者已修改描述"
    assert payload["ownerId"] == "user_jianing"


def test_event_line_clarification_fields_persist_in_cloud_backend():
    app = create_app()
    client = TestClient(app)

    headers = auth_headers(client)
    created = client.post(
        "/api/v1/event-lines",
        json={
            "name": "云端事件线澄清",
            "kind": "project_line",
            "primaryClientId": "client_demo_yellow_river",
        },
        headers=headers,
    )
    assert created.status_code == 200, created.text
    event_line_id = created.json()["id"]

    updated = client.patch(
        f"/api/v1/event-lines/{event_line_id}",
        json={
            "businessCategory": "业务扩展",
            "stage": "资料补齐中",
            "currentBlocker": "客户侧接口人还没确认最终口径。",
            "nextStep": "把这周会议结论同步给客户并确认时间。",
            "recentDecision": "先统一资料，再进入下一轮推进。",
            "evidenceCount": 4,
        },
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["businessCategory"] == "业务扩展"
    assert body["stage"] == "资料补齐中"
    assert body["currentBlocker"] == "客户侧接口人还没确认最终口径。"
    assert body["nextStep"] == "把这周会议结论同步给客户并确认时间。"
    assert body["recentDecision"] == "先统一资料，再进入下一轮推进。"
    assert body["evidenceCount"] == 4

    detail = client.get(f"/api/v1/event-lines/{event_line_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["eventLine"]["businessCategory"] == "业务扩展"
    assert detail.json()["eventLine"]["currentBlocker"] == "客户侧接口人还没确认最终口径。"
    assert detail.json()["eventLine"]["recentDecision"] == "先统一资料，再进入下一轮推进。"
    assert detail.json()["eventLine"]["evidenceCount"] == 4


def test_event_line_transfer_syncs_linked_task_client_ids_in_cloud():
    app = create_app()
    client = TestClient(app)

    headers = auth_headers(client)
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    organization_id = me.json()["organizationId"]
    target_client = {"id": "client_transfer_target", "name": "正式签约客户"}
    timestamp = now_iso()
    client.app.state.app_state.db.execute(
        """
        INSERT INTO clients(id, organization_id, name, alias, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?, ?)
        """,
        (target_client["id"], organization_id, target_client["name"], target_client["name"], timestamp, timestamp),
    )

    created = client.post(
        "/api/v1/event-lines",
        json={
            "name": "潜在线索推进线",
            "kind": "project_line",
            "primaryClientId": "client_demo_yellow_river",
        },
        headers=headers,
    )
    assert created.status_code == 200, created.text
    event_line_id = created.json()["id"]

    task = client.post(
        "/api/v1/tasks",
        json={
            "title": "继续推进意向沟通",
            "priority": "high",
            "listId": "list-0",
            "eventLineId": event_line_id,
        },
        headers=headers,
    )
    assert task.status_code == 200, task.text
    task_payload = task.json()
    assert task_payload["clientId"] == "client_demo_yellow_river"

    upload = client.post(
        f"/api/v1/tasks/{task_payload['id']}/attachments",
        headers=headers,
        data={
            "clientId": "client_demo_yellow_river",
            "eventLineId": event_line_id,
            "taskTitle": task_payload["title"],
        },
        files={
            "file": (
                "签约录音.md",
                "# 签约录音\n\n客户已经明确签约范围和推进节奏。".encode("utf-8"),
                "text/markdown",
            )
        },
    )
    assert upload.status_code == 200, upload.text
    attachment_id = upload.json()["attachments"][0]["id"]

    updated = client.patch(
        f"/api/v1/event-lines/{event_line_id}",
        json={
            "primaryClientId": target_client["id"],
            "syncLinkedTaskClientIds": True,
        },
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["primaryClientId"] == target_client["id"]

    board = client.get("/api/v1/tasks", headers=headers)
    assert board.status_code == 200, board.text
    migrated_task = next(item for item in board.json()["tasks"] if item["id"] == task_payload["id"])
    assert migrated_task["clientId"] == target_client["id"]
    assert migrated_task["clientName"] == target_client["name"]

    attachment_row = client.app.state.app_state.db.fetchone(
        "SELECT client_id FROM task_attachments WHERE id = ?",
        (attachment_id,),
    )
    assert attachment_row is not None
    assert attachment_row["client_id"] == target_client["id"]


def test_desktop_event_line_import_preserves_id_and_skips_existing_rows():
    app = create_app()
    client = TestClient(app)

    headers = auth_headers(client)
    payload = {
        "eventLines": [
            {
                "id": "eline_desktop_import_1",
                "name": "桌面端补迁移事件线",
                "kind": "project_line",
                "status": "active",
                "visibilityScope": "project_public",
                "businessCategory": "业务扩展",
                "stage": "资料补齐中",
                "summary": "先把本地事件线补到云端。",
                "intent": "保留原始 ID 迁移到云端",
                "currentBlocker": "还没正式迁移。",
                "recentDecision": "先做增量导入。",
                "nextStep": "确认导入成功后再讨论任务规则。",
                "evidenceCount": 2,
                "ownerId": "user_qinghua",
                "primaryClientId": "client_demo_yellow_river",
                "participantIds": ["user_qinghua", "user_admin"],
                "createdAt": now_iso(),
                "updatedAt": now_iso(),
                "activities": [
                    {
                        "id": "ela_desktop_import_1",
                        "sourceType": "manual_note",
                        "sourceId": "ela_desktop_import_1",
                        "happenedAt": now_iso(),
                        "actorId": "user_qinghua",
                        "title": "桌面备注",
                        "summary": "这是从桌面端补迁移过来的备注。",
                        "metadata": {"source": "desktop"},
                    }
                ],
            }
        ]
    }

    imported = client.post("/api/v1/event-lines/import-desktop", json=payload, headers=headers)
    assert imported.status_code == 200, imported.text
    imported_payload = imported.json()
    assert imported_payload["requested"] == 1
    assert imported_payload["imported"] == 1
    assert imported_payload["items"][0]["id"] == "eline_desktop_import_1"
    assert imported_payload["items"][0]["status"] == "imported"
    assert imported_payload["items"][0]["importedActivityCount"] == 1

    detail = client.get("/api/v1/event-lines/eline_desktop_import_1", headers=headers)
    assert detail.status_code == 200, detail.text
    detail_payload = detail.json()
    assert detail_payload["eventLine"]["id"] == "eline_desktop_import_1"
    assert detail_payload["eventLine"]["ownerId"] == "user_qinghua"
    assert detail_payload["eventLine"]["primaryClientId"] == "client_demo_yellow_river"
    assert any(item["id"] == "ela_desktop_import_1" for item in detail_payload["activities"])

    second_run = client.post("/api/v1/event-lines/import-desktop", json=payload, headers=headers)
    assert second_run.status_code == 200, second_run.text
    second_payload = second_run.json()
    assert second_payload["imported"] == 0
    assert second_payload["skipped"] == 1
    assert second_payload["items"][0]["status"] == "skipped"


def test_review_dashboard_works_for_task_with_event_line_context():
    app = create_app()
    client = TestClient(app)

    headers = auth_headers(client)
    event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "黄河基金会合作推进",
            "kind": "project_line",
            "primaryClientId": "client_demo_yellow_river",
        },
        headers=headers,
    )
    assert event_line.status_code == 200, event_line.text
    event_line_id = event_line.json()["id"]

    updated_line = client.patch(
        f"/api/v1/event-lines/{event_line_id}",
        json={
            "businessCategory": "业务扩展",
            "stage": "方案推进中",
            "summary": "围绕黄河基金会合作方案持续推进。",
            "intent": "确认合作范围与报价口径。",
            "currentBlocker": "客户侧预算和范围还没完全收口。",
            "recentDecision": "先继续推进官网侧准备，再给出报价判断。",
            "nextStep": "整理合作方案并约下一轮确认。",
            "evidenceCount": 3,
        },
        headers=headers,
    )
    assert updated_line.status_code == 200, updated_line.text

    task = client.post(
        "/api/v1/tasks",
        json={
            "title": "给黄河教系统合作方案",
            "description": "围绕黄河基金会合作范围继续推进方案整理。",
            "priority": "high",
            "listId": "list-0",
            "dueDate": "2026-03-20T10:00",
            "clientId": "client_demo_yellow_river",
            "eventLineId": event_line_id,
            "businessCategory": "业务扩展",
            "currentBlocker": "客户侧预算和范围还没完全收口。",
            "nextAction": "整理合作方案并约下一轮确认。",
            "recentDecision": "先继续推进官网侧准备，再给出报价判断。",
            "evidenceCount": 5,
        },
        headers=headers,
    )
    assert task.status_code == 200, task.text
    task_payload = task.json()
    assert task_payload["businessCategory"] == "业务扩展"
    assert task_payload["currentBlocker"] == "客户侧预算和范围还没完全收口。"
    assert task_payload["nextAction"] == "整理合作方案并约下一轮确认。"
    assert task_payload["recentDecision"] == "先继续推进官网侧准备，再给出报价判断。"
    assert task_payload["evidenceCount"] == 5

    created_review = client.post(
        "/api/v1/reviews/weekly",
        json={
            "weekLabel": "2026-W12",
            "workFreeNote": "围绕黄河基金会合作推进。",
        },
        headers=headers,
    )
    assert created_review.status_code == 200, created_review.text

    dashboard = client.get("/api/v1/reviews/dashboard?weekLabel=2026-W12", headers=headers)
    assert dashboard.status_code == 200, dashboard.text
    payload = dashboard.json()
    matched = next(item for item in payload["workItems"] if item["taskId"] == task_payload["id"])
    assert matched["taskSnapshot"]["eventLineContext"]["id"] == event_line_id
    assert matched["taskSnapshot"]["eventLineContext"]["name"] == "黄河基金会合作推进"
    assert matched["taskSnapshot"]["eventLineContext"]["businessCategory"] == "业务扩展"
    assert matched["taskSnapshot"]["eventLineContext"]["evidenceCount"] == 3
    assert matched["taskSnapshot"]["eventLineContext"]["primaryClientId"] == "client_demo_yellow_river"


def test_personal_task_scope_mode_persists_in_cloud_backend():
    app = create_app()
    client = TestClient(app)

    headers = auth_headers(client)
    event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "不应挂接的共享线",
            "kind": "project_line",
            "primaryClientId": "client_demo_yellow_river",
        },
        headers=headers,
    )
    assert event_line.status_code == 200, event_line.text

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "去健身",
            "description": "个人安排，不进入共享判断。",
            "priority": "normal",
            "listId": "list-0",
            "scopeMode": "PERSONAL_ONLY",
            "clientId": "client_demo_yellow_river",
            "eventLineId": event_line.json()["id"],
            "projectModuleId": "module_should_clear",
            "projectFlowId": "flow_should_clear",
        },
        headers=headers,
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["scopeMode"] == "PERSONAL_ONLY"
    assert body["clientId"] in ("", None)
    assert body["eventLineId"] in ("", None)
    assert body["projectModuleId"] in ("", None)
    assert body["projectFlowId"] in ("", None)

    row = client.app.state.app_state.db.fetchone(
        "SELECT scope_mode, client_id, event_line_id, project_module_id, project_flow_id FROM tasks WHERE id = ?",
        (body["id"],),
    )
    assert row["scope_mode"] == "PERSONAL_ONLY"
    assert row["client_id"] is None
    assert row["event_line_id"] is None
    assert row["project_module_id"] is None
    assert row["project_flow_id"] is None


def test_personal_growth_content_is_self_only_and_excluded_from_team_report():
    app = create_app()
    client = TestClient(app)

    week_label = "2026-W11"
    jianing_headers = auth_headers(client, "jianing@yiyu-system.com", "Jianing123!")
    submitted = client.post(
        "/api/v1/reviews/weekly",
        json={
            "weekLabel": week_label,
            "workProgress": "完成客户材料整理并推进会议纪要落地。",
            "workBlocker": "跨部门协作信息不同步。",
            "blockerType": "协作卡住",
            "workDirection": "围绕战略陪伴闭环推进。",
            "nextWeekFocus": "补齐客户访谈与周会动作项。",
            "supportNeeded": "需要一个更清晰的优先级排序。",
            "relatedPlanIds": ["plan_mgr_support"],
            "workFreeNote": "工作域内容用于层级视野。",
            "personalGrowthNote": "我最近有些焦虑，想更稳定地安排节奏。",
            "personalPrivateNote": "这是完全私密的成长备注，只能自己看。",
        },
        headers=jianing_headers,
    )
    assert submitted.status_code == 200, submitted.text
    dashboard = submitted.json()
    assert dashboard["personalGrowthCard"]["summary"].startswith("我最近有些焦虑")
    assert dashboard["workSignalCard"]["contentDomain"] == "work"

    qinghua_headers = auth_headers(client, "qinghua@yiyu-system.com", "Qinghua123!")
    team_dashboard = client.get("/api/v1/reviews/dashboard", headers=qinghua_headers)
    assert team_dashboard.status_code == 200, team_dashboard.text
    payload = team_dashboard.json()
    assert payload["teamReport"] is not None
    assert payload["teamReport"]["sourcePolicy"]["excludedDomains"] == ["personal", "private", "self_only"]
    serialized = str(payload["teamReport"])
    assert "完全私密的成长备注" not in serialized
    assert "最近有些焦虑" not in serialized


def test_feishu_binding_relay_session_roundtrip():
    app = create_app()
    client = TestClient(app)

    headers = auth_headers(client)
    create_response = client.post(
        "/api/v1/integrations/feishu/user-binding/sessions",
        json={
            "state": "fs_state_demo",
            "expiresAt": (datetime.now() + timedelta(minutes=10)).replace(microsecond=0).isoformat(),
        },
        headers=headers,
    )
    assert create_response.status_code == 200, create_response.text
    assert create_response.json()["status"] == "pending"

    callback_response = client.get(
        "/api/v1/integrations/feishu/user-binding/callback",
        params={"state": "fs_state_demo", "code": "authorization_code_demo"},
    )
    assert callback_response.status_code == 200, callback_response.text
    assert "飞书授权结果已回传" in callback_response.text

    status_response = client.get(
        "/api/v1/integrations/feishu/user-binding/sessions/fs_state_demo",
        headers=headers,
    )
    assert status_response.status_code == 200, status_response.text
    payload = status_response.json()
    assert payload["status"] == "authorized"
    assert payload["code"] == "authorization_code_demo"

    delete_response = client.delete(
        "/api/v1/integrations/feishu/user-binding/sessions/fs_state_demo",
        headers=headers,
    )
    assert delete_response.status_code == 200, delete_response.text

    missing_response = client.get(
        "/api/v1/integrations/feishu/user-binding/sessions/fs_state_demo",
        headers=headers,
    )
    assert missing_response.status_code == 404


def test_task_overdue_only_after_calendar_day_ends():
    app = create_app()
    client = TestClient(app)

    admin_login = client.post("/api/v1/auth/login", json={"email": "admin@yiyu-system.com", "password": "Admin123!"})
    assert admin_login.status_code == 200, admin_login.text
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['accessToken']}"}

    register = client.post(
        "/api/v1/auth/register",
        json={"email": "overdue-check@yiyu-system.com", "fullName": "逾期校验员", "password": "Password123!", "departmentId": "dept_customer_service"},
    )
    assert register.status_code == 200, register.text

    employees = client.get("/api/v1/admin/employees", headers=admin_headers)
    assert employees.status_code == 200, employees.text
    pending_user = next(item for item in employees.json() if item["email"] == "overdue-check@yiyu-system.com")

    approve = client.post(
        f"/api/v1/admin/employees/{pending_user['id']}/approve",
        json={"role": "employee"},
        headers=admin_headers,
    )
    assert approve.status_code == 200, approve.text

    user_login = client.post("/api/v1/auth/login", json={"email": "overdue-check@yiyu-system.com", "password": "Password123!"})
    assert user_login.status_code == 200, user_login.text
    user_headers = {"Authorization": f"Bearer {user_login.json()['accessToken']}"}
    user_id = user_login.json()["user"]["id"]

    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    due_today = client.post(
        "/api/v1/tasks",
        json={
            "title": "今天 16:00 截止也不算逾期",
            "description": "",
            "priority": "normal",
            "listId": "list-0",
            "dueDate": f"{today.isoformat()}T16:00",
            "collaboratorIds": [],
        },
        headers=user_headers,
    )
    assert due_today.status_code == 200, due_today.text

    due_yesterday = client.post(
        "/api/v1/tasks",
        json={
            "title": "昨天截止才算逾期",
            "description": "",
            "priority": "normal",
            "listId": "list-0",
            "dueDate": f"{yesterday.isoformat()}T16:00",
            "collaboratorIds": [],
        },
        headers=user_headers,
    )
    assert due_yesterday.status_code == 200, due_yesterday.text

    metrics = cloud_main._task_metrics_for_user(app.state.app_state, user_id)
    assert metrics["taskCount"] == 2
    assert metrics["activeCount"] == 2
    assert metrics["overdueCount"] == 1


def test_review_history_lists_previous_weeks_and_dashboard_can_switch_by_weeklabel():
    app = create_app()
    client = TestClient(app)

    headers = auth_headers(client, "jianing@yiyu-system.com", "Jianing123!")

    first = client.post(
        "/api/v1/reviews/weekly",
        json={
            "weekLabel": "2026-W11",
            "workFreeNote": "W11 工作复盘",
            "personalGrowthNote": "W11 成长复盘",
        },
        headers=headers,
    )
    assert first.status_code == 200, first.text

    second = client.post(
        "/api/v1/reviews/weekly",
        json={
            "weekLabel": "2026-W12",
            "workFreeNote": "W12 工作复盘",
            "personalGrowthNote": "W12 成长复盘",
        },
        headers=headers,
    )
    assert second.status_code == 200, second.text

    history = client.get("/api/v1/reviews/history", headers=headers)
    assert history.status_code == 200, history.text
    history_payload = history.json()["items"]
    assert [item["weekLabel"] for item in history_payload][:2] == ["2026-W12", "2026-W11"]

    dashboard = client.get("/api/v1/reviews/dashboard?weekLabel=2026-W11", headers=headers)
    assert dashboard.status_code == 200, dashboard.text
    dashboard_payload = dashboard.json()
    assert dashboard_payload["currentReview"]["weekLabel"] == "2026-W11"
    assert dashboard_payload["currentReview"]["workFreeNote"] == "W11 工作复盘"


def test_org_model_profile_roundtrip():
    app = create_app()
    client = TestClient(app)

    headers = auth_headers(client)

    response = client.get('/api/v1/settings/org-model/profile', headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['organization']['name'] == '益语智库'
    assert len(payload['departments']) == 4
    assert len(payload['roles']) >= 4
    assert len(payload['bindings']) >= 4
    assert 'roleProcessTemplates' in payload

    payload['organization']['annualGoal'] = '把 AI 任务系统和组织判断真正打通'
    payload['organization']['quarterlyFocus'] = ['组织模型 P0 上线', '部门周计划接入']
    payload['departments'][0]['mission'] = '把策略判断转成可执行路径'
    payload['focusItems'] = [
        {
            'id': 'focus_q2_signal',
            'periodKey': '2026-Q2',
            'title': '管理信号引擎上线',
            'statement': '让部门总结和 CEO 总结能直接引用结构化管理信号',
            'ownerUserId': 'user_admin',
            'priority': 'high',
            'status': 'active',
            'evidenceKeywords': ['管理信号', '周总结', '组织判断'],
            'updatedAt': '',
        }
    ]
    payload['departmentPlans'] = [
        {
            'id': 'plan_consult_w12',
            'departmentId': 'dept_consult_strategy',
            'weekLabel': '2026-W12',
            'ownerUserId': 'user_qinghua',
            'summary': '把咨询判断沉淀成可复用的策略输出结构',
            'majorRisks': ['资料不完整'],
            'dependencies': ['等待科技发展部确认能力边界'],
            'status': 'active',
            'items': [
                {
                    'id': 'plan_item_consult_signal',
                    'focusItemId': 'focus_q2_signal',
                    'title': '沉淀咨询判断模板',
                    'statement': '把顾问判断过程写成固定模板',
                    'ownerUserId': 'user_qinghua',
                    'status': 'active',
                    'expectedOutput': '判断模板 v1',
                    'sortOrder': 0,
                    'updatedAt': '',
                }
            ],
            'updatedAt': '',
        }
    ]
    payload['roleProcessTemplates'] = [
        {
            'id': 'process_cs_followup',
            'roleTemplateId': 'role_cs_member',
            'name': '客户周会后推进流程',
            'triggerType': 'weekly_followup',
            'triggerCondition': '客户周会结束',
            'keySteps': ['确认需补资料项', '更新客户工作台', '同步飞书群重点', '生成下周待确认事项'],
            'collaborationStep': '同步飞书群重点',
            'approvalStep': '生成下周待确认事项',
            'outputArtifact': '客户推进摘要 + 新任务清单',
            'commonBlockers': ['资料未补齐', '等待部门确认'],
            'active': True,
            'updatedAt': '',
        }
    ]

    updated = client.post('/api/v1/settings/org-model/profile', json=payload, headers=headers)
    assert updated.status_code == 200, updated.text
    updated_payload = updated.json()
    assert updated_payload['organization']['annualGoal'] == '把 AI 任务系统和组织判断真正打通'
    assert updated_payload['organization']['quarterlyFocus'] == ['组织模型 P0 上线', '部门周计划接入']
    assert updated_payload['departments'][0]['mission'] == '把策略判断转成可执行路径'
    assert updated_payload['focusItems'][0]['title'] == '管理信号引擎上线'
    assert updated_payload['departmentPlans'][0]['items'][0]['title'] == '沉淀咨询判断模板'
    assert len(updated_payload['roleProcessTemplates']) == 1
    assert updated_payload['roleProcessTemplates'][0]['triggerType'] == 'weekly_followup'

    reread = client.get('/api/v1/settings/org-model/profile', headers=headers)
    assert reread.status_code == 200, reread.text
    reread_payload = reread.json()
    assert reread_payload['organization']['annualGoal'] == '把 AI 任务系统和组织判断真正打通'
    assert reread_payload['departments'][0]['mission'] == '把策略判断转成可执行路径'
    assert reread_payload['focusItems'][0]['evidenceKeywords'] == ['管理信号', '周总结', '组织判断']
    assert reread_payload['departmentPlans'][0]['dependencies'] == ['等待科技发展部确认能力边界']
    assert reread_payload['roleProcessTemplates'][0]['commonBlockers'] == ['资料未补齐', '等待部门确认']


def test_task_org_link_and_department_control_permissions():
    app = create_app()
    client = TestClient(app)

    qinghua_headers = auth_headers(client, "qinghua@yiyu-system.com", "Qinghua123!")
    create = client.post(
        "/api/v1/tasks",
        json={
            "title": "客户服务部关键推进",
            "description": "需要下周给 CEO 汇报",
            "priority": "high",
            "listId": "list-0",
            "dueDate": "2026-03-20T16:00",
            "collaboratorIds": ["user_jianing"],
            "ownerId": "user_jianing",
        },
        headers=qinghua_headers,
    )
    assert create.status_code == 200, create.text
    create_payload = create.json()
    task_id = create_payload["id"]
    assert create_payload["orgContext"]["departmentId"] == "dept_customer_service"
    assert create_payload["orgContext"]["roleTemplateId"] == "role_cs_lead"
    assert create_payload["orgContext"]["controlRuleId"] == "rule_department_key"
    assert create_payload["orgContext"]["controlLevel"] == "department_control"
    assert create_payload["orgContext"]["needsReview"] is True
    assert create_payload["orgContext"]["approvalState"] == "pending"

    link_row = app.state.app_state.db.fetchone("SELECT * FROM task_org_links WHERE task_id = ?", (task_id,))
    assert link_row is not None
    assert str(link_row["department_id"]) == "dept_customer_service"
    assert str(link_row["role_template_id"]) == "role_cs_lead"
    assert str(link_row["control_rule_id"]) == "rule_department_key"

    jianing_headers = auth_headers(client, "jianing@yiyu-system.com", "Jianing123!")
    denied = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"dueDate": "2026-03-21T18:00"},
        headers=jianing_headers,
    )
    assert denied.status_code == 403
    assert "截止时间" in denied.text

    allowed = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"dueDate": "2026-03-21T18:00"},
        headers=qinghua_headers,
    )
    assert allowed.status_code == 200, allowed.text
    allowed_payload = allowed.json()
    assert allowed_payload["dueDate"] == "2026-03-21T18:00"
    assert allowed_payload["orgContext"]["controlLevel"] == "department_control"


def test_task_plan_link_and_support_request_flow():
    app = create_app()
    client = TestClient(app)

    admin_headers = auth_headers(client)
    profile = client.get('/api/v1/settings/org-model/profile', headers=admin_headers).json()
    profile['focusItems'] = [
        {
            'id': 'focus_q2_signal',
            'periodKey': '2026-Q2',
            'title': '管理信号引擎上线',
            'statement': '推进周总结和任务系统的管理信号能力',
            'ownerUserId': 'user_admin',
            'priority': 'high',
            'status': 'active',
            'evidenceKeywords': ['管理信号', '任务系统'],
            'updatedAt': '',
        }
    ]
    profile['departmentPlans'] = [
        {
            'id': 'plan_info_w12',
            'departmentId': 'dept_info_data',
            'weekLabel': '2026-W12',
            'ownerUserId': 'user_yishuo',
            'summary': '搭建信息数据部本周重点',
            'majorRisks': [],
            'dependencies': [],
            'status': 'active',
            'items': [
                {
                    'id': 'plan_item_signal',
                    'focusItemId': 'focus_q2_signal',
                    'title': '管理信号模板接入',
                    'statement': '完善管理信号模板与导入逻辑',
                    'ownerUserId': 'user_yishuo',
                    'status': 'active',
                    'expectedOutput': '模板 v1',
                    'sortOrder': 0,
                    'updatedAt': '',
                }
            ],
            'updatedAt': '',
        }
    ]
    saved = client.post('/api/v1/settings/org-model/profile', json=profile, headers=admin_headers)
    assert saved.status_code == 200, saved.text

    yishuo_headers = auth_headers(client, "yishuo@yiyu-system.com", "Yishuo123!")
    create = client.post(
        "/api/v1/tasks",
        json={
            "title": "管理信号模板接入周总结",
            "description": "本周把管理信号模板接进组织总结",
            "priority": "high",
            "listId": "list-0",
            "dueDate": "2026-03-19T10:00",
        },
        headers=yishuo_headers,
    )
    assert create.status_code == 200, create.text
    task_id = create.json()["id"]

    recompute = client.post(f"/api/v1/tasks/{task_id}/plan-link/recompute", headers=admin_headers)
    assert recompute.status_code == 200, recompute.text
    recompute_payload = recompute.json()
    assert recompute_payload["focusItemId"] == "focus_q2_signal"
    assert recompute_payload["departmentPlanItemId"] == "plan_item_signal"

    support = client.post(
        "/api/v1/support-requests",
        json={
            "taskId": task_id,
            "targetScope": "department",
            "targetRefId": "dept_info_data",
            "requestType": "resource",
            "urgency": "medium",
            "summary": "需要补一位同事协助整理历史模板",
        },
        headers=yishuo_headers,
    )
    assert support.status_code == 200, support.text
    support_id = support.json()["id"]

    listed = client.get("/api/v1/support-requests?taskId=" + task_id, headers=admin_headers)
    assert listed.status_code == 200, listed.text
    assert any(item["id"] == support_id for item in listed.json())

    resolved = client.post(
        f"/api/v1/support-requests/{support_id}/resolve",
        json={"status": "resolved", "resolutionNote": "已由部门负责人安排支持"},
        headers=admin_headers,
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "resolved"


def test_event_line_roundtrip_and_detail_collects_task_and_support_request():
    app = create_app()
    client = TestClient(app)

    admin_headers = auth_headers(client)

    created_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "云南连心推进线",
            "kind": "project_line",
            "status": "active",
            "stage": "本周推进",
            "summary": "串起云南连心相关任务、会议和支持请求。",
            "intent": "推进云南连心合作闭环",
            "ownerId": "user_admin",
            "primaryClientId": "client_demo_yellow_river",
            "primaryDepartmentId": "dept_consult_strategy",
            "participantIds": ["user_admin", "user_qinghua"],
        },
        headers=admin_headers,
    )
    assert created_line.status_code == 200, created_line.text
    event_line = created_line.json()
    assert event_line["name"] == "云南连心推进线"
    assert event_line["primaryClientId"] == "client_demo_yellow_river"

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "推进云南连心合作方案",
            "description": "补齐合作方案与对接节奏",
            "priority": "high",
            "listId": "list-0",
            "dueDate": "2026-03-24T14:00",
            "clientId": "client_demo_yellow_river",
            "eventLineId": event_line["id"],
        },
        headers=admin_headers,
    )
    assert created_task.status_code == 200, created_task.text
    task_payload = created_task.json()
    assert task_payload["eventLineId"] == event_line["id"]
    assert task_payload["eventLineName"] == "云南连心推进线"

    support_request = client.post(
        "/api/v1/support-requests",
        json={
            "taskId": task_payload["id"],
            "targetScope": "department",
            "targetRefId": "dept_consult_strategy",
            "requestType": "collaboration",
            "urgency": "medium",
            "summary": "需要补齐云南连心合作推进中的协作确认。",
        },
        headers=admin_headers,
    )
    assert support_request.status_code == 200, support_request.text

    detail = client.get(f"/api/v1/event-lines/{event_line['id']}", headers=admin_headers)
    assert detail.status_code == 200, detail.text
    detail_payload = detail.json()
    assert detail_payload["eventLine"]["id"] == event_line["id"]
    assert any(item["id"] == task_payload["id"] for item in detail_payload["tasks"])
    activity_source_types = [item["sourceType"] for item in detail_payload["activities"]]
    assert "task_activity" in activity_source_types
    assert "support_request" in activity_source_types


def test_task_review_approve_and_return_follow_org_permissions():
    app = create_app()
    client = TestClient(app)
    db = app.state.app_state.db

    qinghua_headers = auth_headers(client, "qinghua@yiyu-system.com", "Qinghua123!")
    admin_headers = auth_headers(client)

    register = client.post(
        "/api/v1/auth/register",
        json={"email": "review-worker@yiyu-system.com", "fullName": "复核执行员", "password": "Password123!", "departmentId": "dept_customer_service"},
    )
    assert register.status_code == 200, register.text

    employees = client.get("/api/v1/admin/employees", headers=admin_headers)
    assert employees.status_code == 200, employees.text
    pending_user = next(item for item in employees.json() if item["email"] == "review-worker@yiyu-system.com")
    approve = client.post(
        f"/api/v1/admin/employees/{pending_user['id']}/approve",
        json={"role": "employee"},
        headers=admin_headers,
    )
    assert approve.status_code == 200, approve.text
    worker_headers = auth_headers(client, "review-worker@yiyu-system.com", "Password123!")

    create = client.post(
        "/api/v1/tasks",
        json={
            "title": "客户服务部待复核任务",
            "description": "需要部门负责人复核",
            "priority": "high",
            "listId": "list-0",
            "dueDate": "2026-03-23T16:00",
            "collaboratorIds": [pending_user["id"]],
            "ownerId": pending_user["id"],
        },
        headers=qinghua_headers,
    )
    assert create.status_code == 200, create.text
    task_id = create.json()["id"]
    assert create.json()["orgContext"]["needsReview"] is True
    assert create.json()["orgContext"]["approvalState"] == "pending"

    self_owned = client.post(
        "/api/v1/tasks",
        json={
            "title": "自己创建自己负责的任务",
            "description": "验证负责人不能自己复核",
            "priority": "normal",
            "listId": "list-0",
            "dueDate": "2026-03-23T18:00",
            "ownerId": pending_user["id"],
        },
        headers=worker_headers,
    )
    assert self_owned.status_code == 200, self_owned.text
    self_task_id = self_owned.json()["id"]
    db.execute(
        """
        UPDATE task_org_links
           SET approval_state = 'pending',
               needs_review = 1,
               updated_at = ?
         WHERE task_id = ?
        """,
        (now_iso(), self_task_id),
    )
    self_denied = client.post(f"/api/v1/tasks/{self_task_id}/review/approve", headers=worker_headers)
    assert self_denied.status_code == 403, self_denied.text

    denied = client.post(f"/api/v1/tasks/{task_id}/review/approve", headers=worker_headers)
    assert denied.status_code == 403, denied.text

    approved = client.post(f"/api/v1/tasks/{task_id}/review/approve", headers=qinghua_headers)
    assert approved.status_code == 200, approved.text
    approved_payload = approved.json()
    assert approved_payload["orgContext"]["needsReview"] is False
    assert approved_payload["orgContext"]["approvalState"] == "approved"

    create_again = client.post(
        "/api/v1/tasks",
        json={
            "title": "客户服务部退回复核任务",
            "description": "需要退回复核",
            "priority": "high",
            "listId": "list-0",
            "dueDate": "2026-03-24T16:00",
            "collaboratorIds": [pending_user["id"]],
            "ownerId": pending_user["id"],
        },
        headers=qinghua_headers,
    )
    assert create_again.status_code == 200, create_again.text
    second_task_id = create_again.json()["id"]

    returned = client.post(
        f"/api/v1/tasks/{second_task_id}/review/return",
        json={"reason": "等待补充客户信息"},
        headers=qinghua_headers,
    )
    assert returned.status_code == 200, returned.text
    returned_payload = returned.json()
    assert returned_payload["orgContext"]["approvalState"] == "rejected"
    assert returned_payload["orgContext"]["needsReview"] is True
    assert returned_payload["orgContext"]["blockedAtStep"] == "等待补充客户信息"


def test_org_model_backfill_restores_missing_task_links_for_existing_tasks():
    app = create_app()
    client = TestClient(app)

    qinghua_headers = auth_headers(client, "qinghua@yiyu-system.com", "Qinghua123!")
    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "历史任务补链验证",
            "description": "验证存量任务能补回组织挂接",
            "priority": "normal",
            "listId": "list-0",
            "dueDate": "2026-03-22T10:00",
            "collaboratorIds": ["user_jianing"],
            "ownerId": "user_jianing",
        },
        headers=qinghua_headers,
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["id"]

    app.state.app_state.db.execute("DELETE FROM task_org_links WHERE task_id = ?", (task_id,))
    missing = app.state.app_state.db.fetchone("SELECT * FROM task_org_links WHERE task_id = ?", (task_id,))
    assert missing is None

    admin_headers = auth_headers(client)
    backfill = client.post("/api/v1/settings/org-model/backfill-task-links", headers=admin_headers)
    assert backfill.status_code == 200, backfill.text
    payload = backfill.json()
    assert payload["organizationId"] == "org_yiyu_default"
    assert payload["linkedTasks"] >= 1
    assert payload["createdLinks"] >= 1

    restored = app.state.app_state.db.fetchone("SELECT * FROM task_org_links WHERE task_id = ?", (task_id,))
    assert restored is not None
    assert str(restored["department_id"]) == "dept_customer_service"
~~~

## `cloud_backend/tests/test_bootstrap_security.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.bootstrap_security import BOOTSTRAP_USERS_FILENAME, JWT_SECRET_FILENAME  # noqa: E402
from app.main import create_app  # noqa: E402


def test_secure_bootstrap_defaults_do_not_accept_source_credentials(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / 'secure-cloud-data'
    monkeypatch.setenv('YIYU_CLOUD_DATA_DIR', str(data_dir))
    monkeypatch.delenv('YIYU_CLOUD_INSECURE_SEED_PASSWORDS', raising=False)
    monkeypatch.delenv('YIYU_CLOUD_SECRET_KEY', raising=False)
    monkeypatch.delenv('YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD', raising=False)
    monkeypatch.delenv('YIYU_CLOUD_GUYUAN_PASSWORD', raising=False)
    monkeypatch.delenv('YIYU_CLOUD_QINGHUA_PASSWORD', raising=False)
    monkeypatch.delenv('YIYU_CLOUD_JIANING_PASSWORD', raising=False)
    monkeypatch.delenv('YIYU_CLOUD_YISHUO_PASSWORD', raising=False)

    app = create_app()
    client = TestClient(app)

    default_login = client.post('/api/v1/auth/login', json={'email': 'admin@yiyu-system.com', 'password': 'Admin123!'})
    assert default_login.status_code == 401, default_login.text

    password_store = json.loads((data_dir / BOOTSTRAP_USERS_FILENAME).read_text(encoding='utf-8'))
    bootstrap_password = password_store['user_admin']['password']
    assert bootstrap_password != 'Admin123!'

    secret_value = (data_dir / JWT_SECRET_FILENAME).read_text(encoding='utf-8').strip()
    assert secret_value
    assert secret_value != 'yiyu-cloud-dev-secret'

    bootstrap_login = client.post('/api/v1/auth/login', json={'email': 'admin@yiyu-system.com', 'password': bootstrap_password})
    assert bootstrap_login.status_code == 200, bootstrap_login.text


def test_seed_password_from_env_refreshes_existing_admin_login(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / 'cloud-data'
    monkeypatch.setenv('YIYU_CLOUD_DATA_DIR', str(data_dir))
    monkeypatch.setenv('YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD', 'Admin123!')

    first_app = create_app()
    first_client = TestClient(first_app)
    first_login = first_client.post('/api/v1/auth/login', json={'email': 'admin@yiyu-system.com', 'password': 'Admin123!'})
    assert first_login.status_code == 200, first_login.text

    monkeypatch.setenv('YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD', 'Admin456!')
    second_app = create_app()
    second_client = TestClient(second_app)

    old_login = second_client.post('/api/v1/auth/login', json={'email': 'admin@yiyu-system.com', 'password': 'Admin123!'})
    assert old_login.status_code == 401, old_login.text

    new_login = second_client.post('/api/v1/auth/login', json={'email': 'admin@yiyu-system.com', 'password': 'Admin456!'})
    assert new_login.status_code == 200, new_login.text
~~~

## `cloud_backend/tests/test_feishu_notification_service.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as cloud_main  # noqa: E402
from app.main import create_app, now_iso  # noqa: E402


def make_client(tmp_path, monkeypatch) -> TestClient:
    data_dir = tmp_path / "cloud-data"
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Qinghua123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Jianing123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Yishuo123!")
    return TestClient(create_app())


def auth_headers(client: TestClient, email: str, password: str) -> tuple[dict[str, str], dict]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    payload = response.json()
    return {"Authorization": f"Bearer {payload['accessToken']}"}, payload["user"]


def save_org_feishu_integration(client: TestClient, headers: dict[str, str], monkeypatch) -> None:
    monkeypatch.setattr(cloud_main, "_feishu_fetch_app_access_token", lambda **_: ("app_token_demo", {"code": 0}))
    response = client.post(
        "/api/v1/org-integrations/feishu/validate-and-save",
        json={"appId": "cli_demo_app", "appSecret": "secret_demo"},
        headers=headers,
    )
    assert response.status_code == 200, response.text


def seed_member_mobile(client: TestClient, user_id: str, mobile: str) -> None:
    client.app.state.app_state.db.execute(
        "UPDATE employee_accounts SET feishu_mobile = ?, updated_at = ? WHERE id = ?",
        (mobile, now_iso(), user_id),
    )


def configure_send_mocks(monkeypatch, sent_cards: list[dict[str, object]]) -> None:
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(
        cloud_main,
        "_feishu_lookup_open_id_by_mobile",
        lambda *, tenant_access_token, mobile: (
            "ou_admin" if mobile == "13800138000" else None,
            None if mobile == "13800138000" else "not found",
        ),
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_send_interactive_message",
        lambda *, tenant_access_token, receive_id_type, receive_id, card: sent_cards.append(
            {"receive_id": receive_id, "card": card}
        )
        or {"code": 0},
    )


def test_weekly_review_send_uses_unified_card_service(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers, user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    save_org_feishu_integration(client, headers, monkeypatch)
    seed_member_mobile(client, user["id"], "13800138000")

    sent_cards: list[dict[str, object]] = []
    configure_send_mocks(monkeypatch, sent_cards)

    response = client.post(
        "/api/v1/reviews/weekly",
        json={
            "weekLabel": "2026-W15",
            "taskEntries": [],
            "workProgress": "推进飞书提醒卡片化\n梳理任务提醒链路",
            "workBlocker": "还需要完善逾期提醒",
            "nextWeekFocus": "补齐消息统一规范",
            "workFreeNote": "这周把四类消息先收进同一条云端发送链路。",
            "personalGrowthNote": "开始形成统一通知底座意识。",
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text

    assert len(sent_cards) == 1
    assert sent_cards[0]["receive_id"] == "ou_admin"
    assert sent_cards[0]["card"]["header"]["template"] == "cyan"

    row = client.app.state.app_state.db.fetchone(
        "SELECT * FROM org_feishu_notifications WHERE message_type = 'weekly_review' ORDER BY created_at DESC LIMIT 1"
    )
    assert row is not None
    assert str(row["delivery_status"]) == "sent_card"


def test_badge_unlock_endpoint_sends_once_with_dedupe(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers, user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    save_org_feishu_integration(client, headers, monkeypatch)
    seed_member_mobile(client, user["id"], "13800138000")

    sent_cards: list[dict[str, object]] = []
    configure_send_mocks(monkeypatch, sent_cards)

    payload = {
        "badgeId": "badge_exec_demo",
        "badgeName": "执行推进试跑者",
        "categoryName": "执行推进",
        "badgeDescription": "完成第一次真实飞书提醒链路打通。",
        "xp": 18,
    }
    first = client.post("/api/v1/me/feishu-notifications/badge-unlock", json=payload, headers=headers)
    assert first.status_code == 200, first.text
    second = client.post("/api/v1/me/feishu-notifications/badge-unlock", json=payload, headers=headers)
    assert second.status_code == 200, second.text

    assert len(sent_cards) == 1
    assert sent_cards[0]["card"]["header"]["template"] == "green"
    assert first.json()["deliveryStatus"] == "sent_card"
    assert second.json()["deliveryStatus"] == "sent_card"

    rows = client.app.state.app_state.db.fetchall(
        "SELECT * FROM org_feishu_notifications WHERE message_type = 'badge_unlock' ORDER BY created_at ASC"
    )
    assert len(rows) == 1


def test_overdue_digest_sends_red_summary_once_per_day(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers, user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    save_org_feishu_integration(client, headers, monkeypatch)
    seed_member_mobile(client, user["id"], "13800138000")

    sent_cards: list[dict[str, object]] = []
    configure_send_mocks(monkeypatch, sent_cards)

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "逾期测试任务",
            "description": "",
            "priority": "normal",
            "listId": "list-0",
            "startDate": "2026-04-09",
            "dueDate": "2026-04-09T09:00",
            "collaboratorIds": [user["id"]],
            "ownerId": user["id"],
        },
        headers=headers,
    )
    assert created.status_code == 200, created.text
    sent_cards.clear()

    service = client.app.state.app_state.feishu_notifications
    assert service is not None
    reference_time = datetime(2026, 4, 13, 9, 0, 0)
    service.process_overdue_digest(reference_time=reference_time)
    service.process_overdue_digest(reference_time=reference_time)

    assert len(sent_cards) == 1
    assert sent_cards[0]["card"]["header"]["template"] == "red"

    rows = client.app.state.app_state.db.fetchall(
        "SELECT * FROM org_feishu_notifications WHERE message_type = 'overdue_digest' ORDER BY created_at ASC"
    )
    assert len(rows) == 1
    assert str(rows[0]["delivery_status"]) == "sent_card"
~~~

## `cloud_backend/tests/test_feishu_org_integration.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as cloud_main  # noqa: E402
from app.main import create_app  # noqa: E402


def make_client(tmp_path, monkeypatch) -> TestClient:
    data_dir = tmp_path / "cloud-data"
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Qinghua123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Jianing123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Yishuo123!")
    return TestClient(create_app())


def auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_org_feishu_validate_and_delivery_profile_flow(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client, "admin@yiyu-system.com", "Admin123!")

    before = client.get("/api/v1/me/feishu-delivery-profile", headers=headers)
    assert before.status_code == 200, before.text
    before_payload = before.json()
    assert before_payload["deliveryStatus"] == "integration_pending"
    assert before_payload["readyForNotifications"] is False

    monkeypatch.setattr(cloud_main, "_feishu_fetch_app_access_token", lambda **_: ("app_token_demo", {"code": 0}))
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_token_demo", {"code": 0}))
    monkeypatch.setattr(
        cloud_main,
        "_feishu_lookup_open_id_by_mobile",
        lambda **_: (None, "暂未在飞书通讯录中找到该手机号，请确认该成员已加入当前飞书组织且手机号填写正确。"),
    )

    saved = client.post(
        "/api/v1/org-integrations/feishu/validate-and-save",
        json={
            "appId": "cli_demo_app",
            "appSecret": "secret_demo",
        },
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    payload = saved.json()
    assert payload["enabled"] is True
    assert payload["appId"] == "cli_demo_app"
    assert payload["recentAudits"][0]["validationStatus"] == "success"
    assert "手机号" in (payload["lastValidationMessage"] or "")

    delivery = client.get("/api/v1/me/feishu-delivery-profile", headers=headers)
    assert delivery.status_code == 200, delivery.text
    delivery_payload = delivery.json()
    assert delivery_payload["deliveryStatus"] == "missing_mobile"
    assert delivery_payload["readyForNotifications"] is False

    saved_mobile = client.post(
        "/api/v1/me/feishu-delivery-profile",
        json={"mobile": "138 0013 8000"},
        headers=headers,
    )
    assert saved_mobile.status_code == 200, saved_mobile.text
    saved_mobile_payload = saved_mobile.json()
    assert saved_mobile_payload["mobile"] == "13800138000"
    assert saved_mobile_payload["normalizedMobile"] == "13800138000"
    assert saved_mobile_payload["deliveryStatus"] == "not_found"
    assert saved_mobile_payload["readyForNotifications"] is False
    assert "暂未在飞书通讯录中找到该手机号" in (saved_mobile_payload["blockedReason"] or "")


def test_invalid_feishu_config_does_not_override_existing_valid_config(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers = auth_headers(client, "admin@yiyu-system.com", "Admin123!")

    monkeypatch.setattr(cloud_main, "_feishu_fetch_app_access_token", lambda **_: ("app_token_demo", {"code": 0}))
    initial = client.post(
        "/api/v1/org-integrations/feishu/validate-and-save",
        json={
            "appId": "cli_good_app",
            "appSecret": "secret_good",
        },
        headers=headers,
    )
    assert initial.status_code == 200, initial.text

    def raise_invalid(**_kwargs):
        raise HTTPException(status_code=400, detail="飞书应用校验失败")

    monkeypatch.setattr(cloud_main, "_feishu_fetch_app_access_token", raise_invalid)

    failed = client.post(
        "/api/v1/org-integrations/feishu/validate-and-save",
        json={
            "appId": "cli_bad_app",
            "appSecret": "secret_bad",
        },
        headers=headers,
    )
    assert failed.status_code == 400, failed.text

    current = client.get("/api/v1/org-integrations/feishu", headers=headers)
    assert current.status_code == 200, current.text
    current_payload = current.json()
    assert current_payload["appId"] == "cli_good_app"
    assert current_payload["enabled"] is True
    audit_statuses = {item["validationStatus"] for item in current_payload["recentAudits"]}
    assert "failed" in audit_statuses
    assert "success" in audit_statuses
~~~

## `cloud_backend/tests/test_feishu_query_service.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as cloud_main  # noqa: E402
from app.main import create_app  # noqa: E402


def make_client(tmp_path, monkeypatch) -> TestClient:
    data_dir = tmp_path / "cloud-data"
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Qinghua123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Jianing123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Yishuo123!")
    return TestClient(create_app())


def auth_headers(client: TestClient, email: str, password: str) -> tuple[dict[str, str], dict]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    payload = response.json()
    return {"Authorization": f"Bearer {payload['accessToken']}"}, payload["user"]


def save_org_feishu_integration(client: TestClient, headers: dict[str, str], monkeypatch) -> str:
    monkeypatch.setattr(cloud_main, "_feishu_fetch_app_access_token", lambda **_: ("app_token_demo", {"code": 0}))
    response = client.post(
        "/api/v1/org-integrations/feishu/validate-and-save",
        json={"appId": "cli_demo_app", "appSecret": "secret_demo"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return str(response.json()["organizationId"])


def disable_outbound_feishu(monkeypatch, client: TestClient) -> None:
    monkeypatch.setattr(cloud_main, "_notify_task_feishu_recipients", lambda *args, **kwargs: None)
    service = client.app.state.app_state.feishu_notifications
    if service is not None:
        monkeypatch.setattr(service, "notify_weekly_review", lambda *args, **kwargs: None)


def seed_delivery_target(client: TestClient, organization_id: str, user_id: str, receive_id: str) -> None:
    cloud_main._upsert_org_feishu_delivery_target(  # noqa: SLF001
        client.app.state.app_state,
        organization_id=organization_id,
        user_id=user_id,
        mobile="13800138000",
        receive_id=receive_id,
        match_status="matched",
        last_error=None,
    )


def create_task(
    client: TestClient,
    headers: dict[str, str],
    *,
    title: str,
    owner_id: str,
    collaborator_ids: list[str] | None = None,
    event_line_id: str | None = None,
    due_date: str | None = None,
    start_date: str | None = None,
) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    response = client.post(
        "/api/v1/tasks",
        json={
            "title": title,
            "description": "",
            "priority": "normal",
            "listId": "list-0",
            "startDate": start_date or today,
            "dueDate": due_date or f"{today}T18:00",
            "collaboratorIds": collaborator_ids or [],
            "ownerId": owner_id,
            "eventLineId": event_line_id,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def make_inbound_service(client: TestClient) -> cloud_main.FeishuInboundService:
    return cloud_main.FeishuInboundService(client.app.state.app_state)


def capture_query_delivery(monkeypatch) -> dict[str, list[dict[str, object]]]:
    records: dict[str, list[dict[str, object]]] = {"texts": [], "cards": [], "patched_cards": []}

    def fake_send_text_message(*, tenant_access_token, receive_id_type, receive_id, text):
        records["texts"].append({"receive_id": receive_id, "text": text})
        return {"code": 0, "data": {"message_id": f"om_text_{len(records['texts'])}"}}

    def fake_send_interactive_message(*, tenant_access_token, receive_id_type, receive_id, card):
        message_id = f"om_card_{len(records['cards']) + 1}"
        records["cards"].append({"receive_id": receive_id, "card": card, "message_id": message_id})
        return {"code": 0, "data": {"message_id": message_id}}

    def fake_patch_interactive_message(*, tenant_access_token, message_id, card):
        records["patched_cards"].append({"message_id": message_id, "card": card})
        return {"code": 0, "data": {"message_id": message_id}}

    monkeypatch.setattr(cloud_main, "_feishu_send_text_message", fake_send_text_message)
    monkeypatch.setattr(cloud_main, "_feishu_send_interactive_message", fake_send_interactive_message)
    monkeypatch.setattr(cloud_main, "_feishu_patch_interactive_message", fake_patch_interactive_message)
    return records


def _flatten_card_text(card: dict) -> str:
    chunks: list[str] = []
    header = card.get("header")
    if isinstance(header, dict):
        title = header.get("title")
        if isinstance(title, dict) and title.get("content"):
            chunks.append(str(title["content"]))
    for element in card.get("elements", []):
        if not isinstance(element, dict):
            continue
        if element.get("content"):
            chunks.append(str(element["content"]))
        for child in element.get("elements", []):
            if isinstance(child, dict) and child.get("content"):
                chunks.append(str(child["content"]))
    return "\n".join(chunks)


def latest_query_reply_text(records: dict[str, list[dict[str, object]]]) -> str:
    if records["patched_cards"]:
        return _flatten_card_text(records["patched_cards"][-1]["card"])  # type: ignore[arg-type]
    if records["cards"]:
        return _flatten_card_text(records["cards"][-1]["card"])  # type: ignore[arg-type]
    if records["texts"]:
        return str(records["texts"][-1]["text"])
    return ""


def test_mapped_sender_can_query_today_tasks_and_logs_result(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers, user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    organization_id = save_org_feishu_integration(client, headers, monkeypatch)
    disable_outbound_feishu(monkeypatch, client)
    seed_delivery_target(client, organization_id, user["id"], "ou_admin")
    create_task(client, headers, title="今天要跟进的筹款任务", owner_id=user["id"])

    records = capture_query_delivery(monkeypatch)

    service = make_inbound_service(client)
    service.handle_text_message(
        organization_id=organization_id,
        tenant_access_token="tenant_demo",
        sender_open_id="ou_admin",
        sender_feishu_user_id="ou_user_admin",
        sender_union_id=None,
        tenant_key=None,
        chat_id="chat_demo",
        message_id="msg_today_tasks",
        text="我今天有哪些任务",
    )

    assert len(records["cards"]) == 1
    assert "正在处理" in _flatten_card_text(records["cards"][0]["card"])  # type: ignore[arg-type]
    assert len(records["patched_cards"]) == 1
    final_text = latest_query_reply_text(records)
    assert "我今天的任务" in final_text
    assert "今天要跟进的筹款任务" in final_text

    log_row = client.app.state.app_state.db.fetchone(
        "SELECT * FROM org_feishu_query_logs WHERE message_id = ?",
        ("msg_today_tasks",),
    )
    assert log_row is not None
    assert str(log_row["query_type"]) == "tasks_today"
    assert str(log_row["status"]) == "resolved"
    assert str(log_row["resolved_user_id"]) == user["id"]


def test_unfinished_task_question_is_treated_as_task_list_not_title_keyword_search(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers, user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    organization_id = save_org_feishu_integration(client, headers, monkeypatch)
    disable_outbound_feishu(monkeypatch, client)
    seed_delivery_target(client, organization_id, user["id"], "ou_admin")
    create_task(client, headers, title="补飞书查询规则", owner_id=user["id"])

    records = capture_query_delivery(monkeypatch)

    service = make_inbound_service(client)
    service.handle_text_message(
        organization_id=organization_id,
        tenant_access_token="tenant_demo",
        sender_open_id="ou_admin",
        sender_feishu_user_id="ou_user_admin",
        sender_union_id=None,
        tenant_key=None,
        chat_id="chat_demo",
        message_id="msg_unfinished_list",
        text="我有哪些任务未完成",
    )

    final_text = latest_query_reply_text(records)
    assert "我的待办" in final_text
    assert "补飞书查询规则" in final_text
    assert "标题包含" not in final_text

    log_row = client.app.state.app_state.db.fetchone(
        "SELECT * FROM org_feishu_query_logs WHERE message_id = ?",
        ("msg_unfinished_list",),
    )
    assert log_row is not None
    assert str(log_row["query_type"]) == "tasks_open"


def test_sender_profile_can_auto_bind_unique_account_before_querying(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers, user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    organization_id = save_org_feishu_integration(client, headers, monkeypatch)
    disable_outbound_feishu(monkeypatch, client)
    create_task(client, headers, title="本周待处理项目复盘", owner_id=user["id"])

    monkeypatch.setattr(
        cloud_main,
        "_feishu_fetch_contact_user_profile",
        lambda **_: cloud_main.FeishuSenderProfile(
            open_id="ou_admin_auto",
            feishu_user_id="user_admin_auto",
            name=user["fullName"],
            email=user["email"],
            mobile="13800138000",
        ),
    )
    records = capture_query_delivery(monkeypatch)

    service = make_inbound_service(client)
    service.handle_text_message(
        organization_id=organization_id,
        tenant_access_token="tenant_demo",
        sender_open_id="ou_admin_auto",
        sender_feishu_user_id="user_admin_auto",
        sender_union_id=None,
        tenant_key=None,
        chat_id="chat_demo",
        message_id="msg_auto_bind",
        text="我本周有哪些任务",
    )

    final_text = latest_query_reply_text(records)
    assert "我本周的任务" in final_text

    target_row = client.app.state.app_state.db.fetchone(
        "SELECT * FROM org_feishu_delivery_targets WHERE organization_id = ? AND user_id = ?",
        (organization_id, user["id"]),
    )
    assert target_row is not None
    assert str(target_row["receive_id"]) == "ou_admin_auto"
    assert str(target_row["match_status"]) == "matched"


def test_unresolved_sender_gets_binding_guide_and_scope_denied_is_explicit(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers, user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    organization_id = save_org_feishu_integration(client, headers, monkeypatch)
    disable_outbound_feishu(monkeypatch, client)
    seed_delivery_target(client, organization_id, user["id"], "ou_admin")

    monkeypatch.setattr(cloud_main, "_feishu_fetch_contact_user_profile", lambda **_: None)
    records = capture_query_delivery(monkeypatch)

    service = make_inbound_service(client)
    service.handle_text_message(
        organization_id=organization_id,
        tenant_access_token="tenant_demo",
        sender_open_id="ou_unknown",
        sender_feishu_user_id=None,
        sender_union_id=None,
        tenant_key=None,
        chat_id="chat_demo",
        message_id="msg_unresolved",
        text="我今天有哪些任务",
    )
    assert "识别" in latest_query_reply_text(records)
    unresolved_log = client.app.state.app_state.db.fetchone(
        "SELECT * FROM org_feishu_query_logs WHERE message_id = ?",
        ("msg_unresolved",),
    )
    assert str(unresolved_log["status"]) == "unresolved"

    service.handle_text_message(
        organization_id=organization_id,
        tenant_access_token="tenant_demo",
        sender_open_id="ou_admin",
        sender_feishu_user_id="ou_user_admin",
        sender_union_id=None,
        tenant_key=None,
        chat_id="chat_demo",
        message_id="msg_scope_denied",
        text="林佳维有哪些任务",
    )
    assert "仅支持查询你本人" in latest_query_reply_text(records)
    denied_log = client.app.state.app_state.db.fetchone(
        "SELECT * FROM org_feishu_query_logs WHERE message_id = ?",
        ("msg_scope_denied",),
    )
    assert str(denied_log["status"]) == "denied"
    assert str(denied_log["query_type"]) == "scope_denied"


def test_weekly_review_and_event_line_queries_return_personal_summaries(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers, user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    organization_id = save_org_feishu_integration(client, headers, monkeypatch)
    disable_outbound_feishu(monkeypatch, client)
    seed_delivery_target(client, organization_id, user["id"], "ou_admin")

    review_response = client.post(
        "/api/v1/reviews/weekly",
        json={
            "weekLabel": cloud_main._week_label_for_today(),  # noqa: SLF001
            "taskEntries": [],
            "workProgress": "完成飞书查询链路接线",
            "workBlocker": "等待补全权限配置",
            "nextWeekFocus": "验证私聊机器人查询稳定性",
            "supportNeeded": "需要补开发者平台权限",
        },
        headers=headers,
    )
    assert review_response.status_code == 200, review_response.text

    event_line_response = client.post(
        "/api/v1/event-lines",
        json={
            "name": "飞书桥联调",
            "kind": "coordination_line",
            "status": "active",
            "participantIds": [user["id"]],
        },
        headers=headers,
    )
    assert event_line_response.status_code == 200, event_line_response.text
    event_line_id = event_line_response.json()["id"]
    create_task(
        client,
        headers,
        title="联调飞书查询入口",
        owner_id=user["id"],
        event_line_id=event_line_id,
    )

    records = capture_query_delivery(monkeypatch)
    service = make_inbound_service(client)

    service.handle_text_message(
        organization_id=organization_id,
        tenant_access_token="tenant_demo",
        sender_open_id="ou_admin",
        sender_feishu_user_id="ou_user_admin",
        sender_union_id=None,
        tenant_key=None,
        chat_id="chat_demo",
        message_id="msg_review_status",
        text="我这周复盘提交了吗",
    )
    service.handle_text_message(
        organization_id=organization_id,
        tenant_access_token="tenant_demo",
        sender_open_id="ou_admin",
        sender_feishu_user_id="ou_user_admin",
        sender_union_id=None,
        tenant_key=None,
        chat_id="chat_demo",
        message_id="msg_eventline_list",
        text="我参与的事件线有哪些",
    )

    combined = "\n".join(
        _flatten_card_text(item["card"])  # type: ignore[arg-type]
        for item in records["patched_cards"]
    )
    assert "已提交周复盘" in combined
    assert "飞书桥联调" in combined


def test_model_parse_can_filter_tasks_by_collaboration_partner(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers, admin_user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    _, qinghua_user = auth_headers(client, "qinghua@yiyu-system.com", "Qinghua123!")
    _, jianing_user = auth_headers(client, "jianing@yiyu-system.com", "Jianing123!")
    organization_id = save_org_feishu_integration(client, headers, monkeypatch)
    disable_outbound_feishu(monkeypatch, client)
    seed_delivery_target(client, organization_id, admin_user["id"], "ou_admin")

    create_task(
        client,
        headers,
        title="测试卡片更新慢通知",
        owner_id=admin_user["id"],
        collaborator_ids=[admin_user["id"], qinghua_user["id"]],
    )
    create_task(
        client,
        headers,
        title="另一个协作任务",
        owner_id=admin_user["id"],
        collaborator_ids=[admin_user["id"], jianing_user["id"]],
    )

    monkeypatch.setattr(
        cloud_main,
        "_load_feishu_query_model_config",
        lambda state, org_id: cloud_main.FeishuQueryModelConfig(api_key="demo-key", model="demo-model"),
    )
    monkeypatch.setattr(
        cloud_main,
        "_sync_qwen_chat",
        lambda api_key, payload, timeout: json.dumps(
            {
                "intent": "tasks_list",
                "status_filter": "open",
                "time_filter": "none",
                "participant_name": qinghua_user["fullName"],
                "owner_name": "",
                "keyword": "",
            },
            ensure_ascii=False,
        ),
    )

    records = capture_query_delivery(monkeypatch)

    service = make_inbound_service(client)
    service.handle_text_message(
        organization_id=organization_id,
        tenant_access_token="tenant_demo",
        sender_open_id="ou_admin",
        sender_feishu_user_id="ou_user_admin",
        sender_union_id=None,
        tenant_key=None,
        chat_id="chat_demo",
        message_id="msg_partner_tasks",
        text=f"我和{qinghua_user['fullName']}协作的任务有哪些",
    )

    final_text = latest_query_reply_text(records)
    assert "测试卡片更新慢通知" in final_text
    assert "另一个协作任务" not in final_text
    assert qinghua_user["fullName"] in final_text

    log_row = client.app.state.app_state.db.fetchone(
        "SELECT * FROM org_feishu_query_logs WHERE message_id = ?",
        ("msg_partner_tasks",),
    )
    assert log_row is not None
    assert str(log_row["query_type"]) == "tasks_list"
    assert str(log_row["status"]) == "resolved"


def test_model_parse_can_distinguish_overdue_unfinished_tasks(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    headers, admin_user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    organization_id = save_org_feishu_integration(client, headers, monkeypatch)
    disable_outbound_feishu(monkeypatch, client)
    seed_delivery_target(client, organization_id, admin_user["id"], "ou_admin")

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")
    create_task(
        client,
        headers,
        title="已经过期但还没完成",
        owner_id=admin_user["id"],
        start_date=yesterday,
        due_date=f"{yesterday}T18:00",
    )
    create_task(
        client,
        headers,
        title="今天还没过期的任务",
        owner_id=admin_user["id"],
        start_date=today,
        due_date=f"{today}T21:00",
    )

    monkeypatch.setattr(
        cloud_main,
        "_load_feishu_query_model_config",
        lambda state, org_id: cloud_main.FeishuQueryModelConfig(api_key="demo-key", model="demo-model"),
    )
    monkeypatch.setattr(
        cloud_main,
        "_sync_qwen_chat",
        lambda api_key, payload, timeout: json.dumps(
            {
                "intent": "tasks_list",
                "status_filter": "overdue",
                "time_filter": "none",
                "participant_name": "",
                "owner_name": "",
                "keyword": "",
            },
            ensure_ascii=False,
        ),
    )

    records = capture_query_delivery(monkeypatch)

    service = make_inbound_service(client)
    service.handle_text_message(
        organization_id=organization_id,
        tenant_access_token="tenant_demo",
        sender_open_id="ou_admin",
        sender_feishu_user_id="ou_user_admin",
        sender_union_id=None,
        tenant_key=None,
        chat_id="chat_demo",
        message_id="msg_overdue_open_tasks",
        text="我有哪些任务过期了但还没完成",
    )

    final_text = latest_query_reply_text(records)
    assert "我的逾期任务" in final_text
    assert "已经过期但还没完成" in final_text
    assert "今天还没过期的任务" not in final_text

    log_row = client.app.state.app_state.db.fetchone(
        "SELECT * FROM org_feishu_query_logs WHERE message_id = ?",
        ("msg_overdue_open_tasks",),
    )
    assert log_row is not None
    assert str(log_row["query_type"]) == "tasks_list"
~~~

## `cloud_backend/tests/test_local_first_auth.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app  # noqa: E402


def make_client(tmp_path, monkeypatch) -> TestClient:
    data_dir = tmp_path / "cloud-data"
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Qinghua123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Jianing123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Yishuo123!")
    return TestClient(create_app())


def auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_personal_register_can_upgrade_to_shared_org_and_invite_member(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": "local-first-owner@example.com",
            "fullName": "本地优先拥有者",
            "password": "Password123!",
        },
    )
    assert register.status_code == 200, register.text
    owner_headers = {"Authorization": f"Bearer {register.json()['accessToken']}"}

    membership = client.get("/api/v1/account/membership", headers=owner_headers)
    assert membership.status_code == 200, membership.text
    assert membership.json()["isPersonalWorkspace"] is True

    created_org = client.post("/api/v1/orgs", json={"name": "益语测试组织"}, headers=owner_headers)
    assert created_org.status_code == 200, created_org.text
    assert created_org.json()["organizationName"] == "益语测试组织"
    assert created_org.json()["isPersonalWorkspace"] is False

    invitation = client.post(
        "/api/v1/org-invitations",
        json={"roleName": "研究员", "expiresInDays": 7, "maxUses": 1},
        headers=owner_headers,
    )
    assert invitation.status_code == 200, invitation.text
    invite_code = invitation.json()["code"]

    joiner = client.post(
        "/api/v1/auth/register",
        json={
            "email": "joiner@example.com",
            "fullName": "加入成员",
            "password": "Password123!",
        },
    )
    assert joiner.status_code == 200, joiner.text
    joiner_headers = {"Authorization": f"Bearer {joiner.json()['accessToken']}"}

    redeemed = client.post("/api/v1/org-invitations/redeem", json={"code": invite_code}, headers=joiner_headers)
    assert redeemed.status_code == 200, redeemed.text
    assert redeemed.json()["organizationName"] == "益语测试组织"
    assert redeemed.json()["jobTitle"] == "研究员"
    assert redeemed.json()["isPersonalWorkspace"] is False


def test_import_local_structured_data_creates_lists_tasks_and_tags(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    owner_headers = auth_headers(client, "admin@yiyu-system.com", "Admin123!")

    response = client.post(
        "/api/v1/sync/import-local",
        json={
            "taskLists": [
                {"localId": "list-local-1", "name": "本地导入清单", "color": "#123456", "scope": "org"},
            ],
            "tasks": [
                {
                    "localId": "task-local-1",
                    "title": "导入后的结构化任务",
                    "description": "只同步结构化记录",
                    "priority": "high",
                    "listLocalId": "list-local-1",
                    "tags": ["同步", "组织"],
                }
            ],
        },
        headers=owner_headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["importedListCount"] == 1
    assert payload["importedTaskCount"] == 1
    assert payload["importedTagCount"] >= 1

    tasks = client.get("/api/v1/tasks", headers=owner_headers)
    assert tasks.status_code == 200, tasks.text
    imported_task = next(item for item in tasks.json()["tasks"] if item["sourceType"] == "local_import")
    assert imported_task["title"] == "导入后的结构化任务"
    assert "同步" in [tag["name"] for tag in imported_task["tags"]]
~~~

## `cloud_backend/tests/test_mobile_consult_context.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from fastapi.testclient import TestClient

TEST_DATA_DIR = Path(__file__).resolve().parent / "test_cloud_data"
os.environ["YIYU_CLOUD_DATA_DIR"] = str(TEST_DATA_DIR)
os.environ["YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD"] = "Admin123!"
os.environ["ARK_API_KEY"] = "test-ark-key"
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app  # noqa: E402
from app import main as cloud_main  # noqa: E402
from app import knowledge_store as cloud_knowledge_store  # noqa: E402


def setup_function():
    if TEST_DATA_DIR.exists():
        for child in TEST_DATA_DIR.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    else:
        TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)


def teardown_function():
    if TEST_DATA_DIR.exists():
        for child in TEST_DATA_DIR.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()


def auth_headers(client: TestClient):
    response = client.post("/api/v1/auth/login", json={"email": "admin@yiyu-system.com", "password": "Admin123!"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def seed_client(app, client_id: str = "client_mobile_context", client_name: str = "日慈基金会") -> tuple[str, str]:
    timestamp = cloud_main.now_iso()
    app.state.app_state.db.execute(
        "INSERT INTO clients(id, organization_id, name, alias, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?)",
        (client_id, "org_yiyu_default", client_name, "", timestamp, timestamp),
    )
    return client_id, client_name


def test_mobile_capabilities_and_workspace_routes_stop_faking_missing_routes():
    app = create_app()
    client = TestClient(app)
    headers = auth_headers(client)
    client_id, _ = seed_client(app)

    capabilities = client.get("/api/v1/mobile/capabilities", headers=headers)
    assert capabilities.status_code == 200, capabilities.text
    payload = capabilities.json()
    assert payload["consultationChat"] is True
    assert payload["clientWorkspace"] is True
    assert payload["strategicCockpit"] is True
    assert payload["contextBundle"] is True
    assert payload["consultationPayloadVersion"] == "v2"

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace", headers=headers)
    assert workspace.status_code == 200, workspace.text
    workspace_payload = workspace.json()
    assert workspace_payload["status"] in {"partial", "missing", "rich"}
    assert "missingSources" in workspace_payload
    assert "sourceAvailability" in workspace_payload

    cockpit = client.get(f"/api/v1/clients/{client_id}/strategic-cockpit", headers=headers)
    assert cockpit.status_code == 200, cockpit.text
    cockpit_payload = cockpit.json()
    assert cockpit_payload["status"] in {"partial", "missing", "rich"}
    assert "missingSources" in cockpit_payload
    assert "sourceAvailability" in cockpit_payload


def test_thin_context_consult_forces_limited_context(monkeypatch):
    captured: dict[str, str] = {}

    def fake_qwen_chat(api_key: str, payload: dict, timeout: object) -> str:
        captured["system"] = str(payload["messages"][0]["content"])
        return "已知：当前只找到客户名。\n\n缺失：还没有工作台、DNA、会议或 cockpit。\n\n下一步：先同步客户工作台与 DNA。"

    monkeypatch.setattr(cloud_main, "_sync_qwen_chat", fake_qwen_chat)
    monkeypatch.setattr(cloud_knowledge_store, "find_desktop_app_db_path", lambda: None)

    app = create_app()
    client = TestClient(app)
    headers = auth_headers(client)
    client_id, client_name = seed_client(app)

    response = client.post(
        "/api/v1/consultation/chat",
        headers=headers,
        json={
            "message": f"介绍一下{client_name}",
            "clientId": client_id,
            "clientName": client_name,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["answerMode"] == "limited_context"
    assert payload["contextQuality"]["level"] == "thin"
    missing_types = {item["type"] for item in payload["missingContext"]}
    assert "workspace" in missing_types
    assert "client_dna" in missing_types
    assert "meeting" in missing_types
    assert "strategic_cockpit" in missing_types
    assert "只能根据【已知事实】回答" in captured["system"]
    assert "通常基金会可能" in captured["system"]


def test_publish_knowledge_mirror_flips_capability_and_feeds_workspace():
    app = create_app()
    client = TestClient(app)
    headers = auth_headers(client)
    client_id, _ = seed_client(app)

    before = client.get("/api/v1/mobile/capabilities", headers=headers)
    assert before.status_code == 200, before.text
    assert before.json()["knowledgeMirror"] is False

    publish = client.post(
        "/api/v1/mobile/knowledge-mirror/publish",
        headers=headers,
        json={
            "items": [
                {
                    "clientId": client_id,
                    "sourceType": "workspace_snapshot",
                    "sourceId": f"workspace:{client_id}",
                    "snapshotVersion": 1,
                    "snapshotHash": "abc123",
                    "updatedAt": "2026-04-19T10:00:00",
                    "payload": {
                        "status": "partial",
                        "goals": [{"id": "g1", "title": "准备沟通材料", "summary": "本周先补客户材料"}],
                        "meetings": [],
                        "documentCards": [],
                        "latestOpenQuestions": [],
                        "latestConflicts": [],
                        "relatedTasks": [{"id": "task-1", "title": "准备材料", "status": "todo"}],
                        "missingSources": ["client_dna", "recent_meetings"],
                    },
                    "evidenceRefs": ["seed:test"],
                }
            ]
        },
    )
    assert publish.status_code == 200, publish.text
    assert publish.json()["publishedCount"] == 1

    after = client.get("/api/v1/mobile/capabilities", headers=headers)
    assert after.status_code == 200, after.text
    assert after.json()["knowledgeMirror"] is True

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace", headers=headers)
    assert workspace.status_code == 200, workspace.text
    payload = workspace.json()
    assert payload["status"] == "partial"
    assert payload["goals"][0]["title"] == "准备沟通材料"
~~~

## `cloud_backend/tests/test_simulation_seed.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import os
import shutil
import sys
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

TEST_DATA_DIR = Path(__file__).resolve().parent / "test_cloud_simulation_data"
os.environ["YIYU_CLOUD_DATA_DIR"] = str(TEST_DATA_DIR)
os.environ["YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD"] = "Admin123!"
os.environ["YIYU_CLOUD_QINGHUA_PASSWORD"] = "Qinghua123!"
os.environ["YIYU_CLOUD_JIANING_PASSWORD"] = "Jianing123!"
os.environ["YIYU_CLOUD_YISHUO_PASSWORD"] = "Yishuo123!"
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import DEFAULT_ORG_ID, create_app  # noqa: E402
from app.simulation_seed import seed_simulated_review_org  # noqa: E402


def setup_function():
    os.environ["YIYU_CLOUD_DATA_DIR"] = str(TEST_DATA_DIR)
    if TEST_DATA_DIR.exists():
        for child in TEST_DATA_DIR.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    else:
        TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)


def teardown_function():
    if TEST_DATA_DIR.exists():
        for child in TEST_DATA_DIR.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()


def auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_seed_simulated_review_org_populates_week_and_visibility():
    app = create_app()
    client = TestClient(app)
    db = app.state.app_state.db

    seeded = seed_simulated_review_org(db, organization_id=DEFAULT_ORG_ID, base_date=date(2026, 3, 15))
    reseeded = seed_simulated_review_org(db, organization_id=DEFAULT_ORG_ID, base_date=date(2026, 3, 15))

    assert seeded["weekLabel"] == "2026-W11"
    assert reseeded["weekLabel"] == "2026-W11"
    assert seeded["employeeCount"] == 20
    assert seeded["departmentCount"] == 4
    assert db.scalar("SELECT COUNT(1) AS count FROM tasks WHERE source_type = 'simulation_seed'") == 420
    assert db.scalar("SELECT COUNT(1) AS count FROM weekly_review_entries WHERE week_label = ?", ("2026-W11",)) == 20
    assert db.scalar("SELECT COUNT(1) AS count FROM weekly_review_task_entries WHERE week_label = ?", ("2026-W11",)) == 420
    assert db.scalar(
        "SELECT COUNT(1) AS count FROM weekly_review_task_entries WHERE week_label = ? AND TRIM(COALESCE(structured_note_json, '')) != ''",
        ("2026-W11",),
    ) == 420

    per_day_counts = db.fetchall(
        """
        SELECT owner_id, due_date, COUNT(1) AS item_count
        FROM tasks
        WHERE source_type = 'simulation_seed'
        GROUP BY owner_id, due_date
        ORDER BY owner_id, due_date
        """
    )
    assert len(per_day_counts) == 140
    assert all(int(row["item_count"]) == 3 for row in per_day_counts)

    qinghua_dashboard = client.get(
        "/api/v1/reviews/dashboard",
        headers=auth_headers(client, "qinghua@yiyu-system.com", "Qinghua123!"),
    )
    assert qinghua_dashboard.status_code == 200, qinghua_dashboard.text
    qinghua_payload = qinghua_dashboard.json()
    assert qinghua_payload["currentReview"] is not None
    assert qinghua_payload["workItems"][0]["structuredNote"]["completionStatus"] in {"done_on_time", "done_late", "in_progress", "not_done"}
    assert qinghua_payload["teamReport"] is not None
    assert "84 条任务复盘" in qinghua_payload["teamReport"]["summary"]

    jiale_dashboard = client.get(
        "/api/v1/reviews/dashboard",
        headers=auth_headers(client, "jiale@yiyu-system.com", "Jiale123!"),
    )
    assert jiale_dashboard.status_code == 200, jiale_dashboard.text
    assert "84 条任务复盘" in jiale_dashboard.json()["teamReport"]["summary"]

    dazhou_dashboard = client.get(
        "/api/v1/reviews/dashboard",
        headers=auth_headers(client, "dazhou@yiyu-system.com", "Dazhou123!"),
    )
    assert dazhou_dashboard.status_code == 200, dazhou_dashboard.text
    assert "84 条任务复盘" in dazhou_dashboard.json()["teamReport"]["summary"]

    jianing_dashboard = client.get(
        "/api/v1/reviews/dashboard",
        headers=auth_headers(client, "jianing@yiyu-system.com", "Jianing123!"),
    )
    assert jianing_dashboard.status_code == 200, jianing_dashboard.text
    assert "84 条任务复盘" in jianing_dashboard.json()["teamReport"]["summary"]

    admin_dashboard = client.get(
        "/api/v1/reviews/dashboard",
        headers=auth_headers(client, "admin@yiyu-system.com", "Admin123!"),
    )
    assert admin_dashboard.status_code == 200, admin_dashboard.text
    admin_payload = admin_dashboard.json()
    assert admin_payload["orgReport"] is not None
    assert "420 条工作任务复盘" in admin_payload["orgReport"]["summary"]
~~~

## `cloud_backend/tests/test_smart_input.py`

- 编码: `utf-8`

~~~python
from datetime import date

from app.models import EventLineRecord
from app.smart_input import build_smart_task_draft


def test_build_smart_task_draft_extracts_range_title_and_match():
    event_lines = [
        EventLineRecord(
            id="event_yunnan",
            name="云南儿童调研工作坊",
            primaryClientId="client_yunnan",
            primaryClientName="云南儿童调研",
            createdAt="2026-03-01T10:00:00",
            updatedAt="2026-03-01T10:00:00",
        )
    ]

    result = build_smart_task_draft(
        "帮我建一个日程，3月7号到3月9号去云南，做儿童协作工作坊，这个项目是关于云南儿童调研的。",
        event_lines,
        reference_date=date(2026, 3, 1),
    )

    assert result.draft.title == "云南儿童调研｜儿童调研工作坊｜云南儿童协作工作坊"
    assert result.draft.dueDate == "2026-03-07"
    assert result.draft.endDate == "2026-03-09"
    assert result.draft.clientId == "client_yunnan"
    assert result.draft.eventLineId == "event_yunnan"
    assert result.intent == "task_schedule"


def test_build_smart_task_draft_handles_relative_day_and_analysis_tag():
    result = build_smart_task_draft(
        "明天下午3点调研广州项目的现状，先做一版摸底分析。",
        [],
        reference_date=date(2026, 3, 30),
    )

    assert result.draft.dueDate == "2026-03-31"
    assert result.draft.dueTime == "15:00"
    assert result.draft.tags == ["内部分析"]
    assert result.draft.title


def test_build_smart_task_draft_builds_structured_title_for_client_event_line_and_action():
    event_lines = [
        EventLineRecord(
            id="event_rc",
            name="日慈基金会跟笑雨老师核对她的教师项目进度",
            primaryClientId="client_rc",
            primaryClientName="日慈基金会",
            createdAt="2026-03-01T10:00:00",
            updatedAt="2026-03-01T10:00:00",
        )
    ]

    result = build_smart_task_draft(
        "日慈基金会高老师周五之前会发一个关于日慈品牌改造的时间规划过来。",
        event_lines,
        reference_date=date(2026, 3, 31),
    )

    assert result.draft.clientId == "client_rc"
    assert result.draft.eventLineId == "event_rc"
    assert result.draft.title == "日慈基金会｜教师项目｜周五前发品牌改造规划"
~~~

