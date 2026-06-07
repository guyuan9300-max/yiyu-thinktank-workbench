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
                    phone_number TEXT,
                    full_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    primary_role TEXT NOT NULL,
                    account_status TEXT NOT NULL,
                    membership_status TEXT NOT NULL DEFAULT 'approved',
                    membership_submitted_at TEXT,
                    membership_rejected_reason TEXT,
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

                CREATE TABLE IF NOT EXISTS organization_maintenance_permissions (
                    organization_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    granted_by TEXT,
                    granted_at TEXT NOT NULL,
                    revoked_at TEXT,
                    can_manage_permissions INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (organization_id, user_id),
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE,
                    FOREIGN KEY(granted_by) REFERENCES employee_accounts(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_org_maintenance_permissions_org
                    ON organization_maintenance_permissions(organization_id, revoked_at);

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
                    type TEXT NOT NULL DEFAULT 'client',
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
                    deadline_at TEXT,
                    scheduled_start_at TEXT,
                    scheduled_end_at TEXT,
                    completed_at TEXT,
                    start_date TEXT,
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

                -- P7：client_related_users 关联表
                --   模仿 task_collaborators 的 (主表, user_id, order_index) 结构。
                --   ACL 入口：creator_id 或 user_id ∈ client_related_users 才能在 GET /clients 看到。
                --   注意：clients 表本身已经存在（最小化定义），多出的扩展字段由后面的 _ensure_column 加。
                --   idx_clients_creator 不能放在这个 executescript 块里——因为 creator_id 列要靠
                --   _ensure_column 在 schema 跑完后才加上；放这里会因列不存在直接失败。
                --   该 index 在下方 _ensure_column("creator_id") 调用之后单独创建。
                CREATE TABLE IF NOT EXISTS client_related_users (
                    client_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    order_index INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (client_id, user_id),
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_client_related_users_user ON client_related_users(user_id);

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
                    leader_name TEXT NOT NULL DEFAULT '',
                    intro_document_json TEXT NOT NULL DEFAULT '{}',
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
                    leader_name TEXT NOT NULL DEFAULT '',
                    parent_department_id TEXT,
                    intro_document_json TEXT NOT NULL DEFAULT '{}',
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
                -- 机器人同事(bot)云端注册表 — 全局共享、桌面+手机两端可见的真相源.
                -- 字段对齐桌面 bot_members; reporting/capabilities 以 JSON 反范式存(桌面同步时拆回三表).
                CREATE TABLE IF NOT EXISTS org_bots (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    handle TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    actor_type TEXT NOT NULL DEFAULT 'internal_ai_agent',
                    department_id TEXT,
                    department_name TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active',
                    created_by_user_id TEXT,
                    token_hash TEXT NOT NULL DEFAULT '',
                    token_salt TEXT NOT NULL DEFAULT '',
                    token_prefix TEXT NOT NULL DEFAULT '',
                    token_rotated_at TEXT,
                    reporting_json TEXT NOT NULL DEFAULT '{}',
                    capabilities_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(organization_id, handle),
                    UNIQUE(organization_id, actor_id),
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(department_id) REFERENCES org_departments(id) ON DELETE SET NULL,
                    FOREIGN KEY(created_by_user_id) REFERENCES employee_accounts(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_org_bots_org
                    ON org_bots(organization_id, status, updated_at DESC);

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

                CREATE TABLE IF NOT EXISTS cloud_client_understanding_snapshots (
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
                CREATE INDEX IF NOT EXISTS idx_cloud_client_understanding_client
                    ON cloud_client_understanding_snapshots(organization_id, client_id, updated_at DESC, published_at DESC);

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
            # 岗位持有人=机器人同事时,记录 bot id,使"岗位归属"也随云端共享(退役桌面本地 sidecar).
            self._ensure_column("org_role_templates", "holder_bot_id", "TEXT")
            self._ensure_column("employee_accounts", "department_id", "TEXT")
            self._ensure_column("employee_accounts", "department_name", "TEXT")
            self._ensure_column("employee_accounts", "job_title", "TEXT")
            self._ensure_column("employee_accounts", "manager_name", "TEXT")
            self._ensure_column("employee_accounts", "current_focus", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("employee_accounts", "is_department_lead", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("employee_accounts", "phone_number", "TEXT")
            self._ensure_column("employee_accounts", "phone_verified_at", "TEXT")
            self._ensure_column("employee_accounts", "membership_status", "TEXT NOT NULL DEFAULT 'approved'")
            self._ensure_column("employee_accounts", "membership_submitted_at", "TEXT")
            self._ensure_column("employee_accounts", "membership_rejected_reason", "TEXT")
            self._ensure_column("employee_accounts", "feishu_mobile", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("employee_accounts", "avatar_url", "TEXT")
            self._ensure_column("clients", "type", "TEXT NOT NULL DEFAULT 'client'")
            # P7：clients 接通 local desktop 同步所需的扩展字段
            #   creator_id：local 创建者；ACL 入口（creator 或 client_related_users.user_id 可见）
            #   domain/intro/stage/color：local 端业务字段
            #   is_data_center_included：仅工作台开关
            self._ensure_column("clients", "creator_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("clients", "domain", "TEXT NOT NULL DEFAULT '项目'")
            self._ensure_column("clients", "intro", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("clients", "stage", "TEXT NOT NULL DEFAULT '待导入资料'")
            self._ensure_column("clients", "color", "TEXT NOT NULL DEFAULT '#5B7BFE'")
            self._ensure_column("clients", "is_data_center_included", "INTEGER NOT NULL DEFAULT 1")
            # P7：creator_id 列加完后再建索引
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_clients_creator ON clients(creator_id, updated_at DESC)")
            self.conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_employee_accounts_phone_number ON employee_accounts(phone_number) WHERE phone_number IS NOT NULL AND phone_number != ''"
            )
            self.conn.execute(
                """
                UPDATE employee_accounts
                   SET membership_status = CASE
                     WHEN account_status IN ('pending', 'approved', 'rejected') THEN account_status
                     ELSE COALESCE(NULLIF(membership_status, ''), 'approved')
                   END,
                       membership_rejected_reason = CASE
                         WHEN account_status = 'rejected' THEN COALESCE(membership_rejected_reason, rejected_reason)
                         ELSE membership_rejected_reason
                       END
                 WHERE membership_status IS NULL
                    OR membership_status = ''
                    OR (account_status IN ('pending', 'rejected') AND membership_status = 'approved')
                """
            )
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
            self._ensure_column("org_profiles", "leader_name", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("org_profiles", "intro_document_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column("org_profiles", "management_user_ids_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("org_departments", "leader_name", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("org_departments", "intro_document_json", "TEXT NOT NULL DEFAULT '{}'")
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
            self._ensure_column("tasks", "deadline_at", "TEXT")
            self._ensure_column("tasks", "scheduled_start_at", "TEXT")
            self._ensure_column("tasks", "scheduled_end_at", "TEXT")
            self._ensure_column("tasks", "reminder_minutes_before", "INTEGER")  # 5/29 任务提醒(跨端共享字段): 0=准时 5=提前5分 NULL=不提醒
            self._ensure_column("tasks", "completed_at", "TEXT")
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
            self.conn.execute(
                """
                UPDATE tasks
                SET deadline_at = due_date
                WHERE deadline_at IS NULL
                  AND due_date IS NOT NULL
                  AND due_date != ''
                  AND (start_date IS NULL OR start_date = '')
                  AND due_date GLOB '????-??-??'
                """
            )
            self.conn.execute(
                """
                UPDATE tasks
                SET scheduled_start_at = COALESCE(NULLIF(start_date, ''), due_date)
                WHERE scheduled_start_at IS NULL
                  AND (
                    (start_date IS NOT NULL AND start_date != '')
                    OR due_date LIKE '%T%'
                    OR due_date GLOB '????-??-?? ??:??*'
                  )
                """
            )
            self.conn.execute(
                """
                UPDATE tasks
                SET scheduled_end_at = due_date
                WHERE scheduled_end_at IS NULL
                  AND start_date IS NOT NULL
                  AND start_date != ''
                  AND due_date IS NOT NULL
                  AND due_date != ''
                  AND due_date != start_date
                  AND (due_date LIKE '%T%' OR due_date GLOB '????-??-?? ??:??*')
                """
            )
            self.conn.execute(
                """
                UPDATE tasks
                SET completed_at = COALESCE(NULLIF(updated_at, ''), datetime('now'))
                WHERE completed_at IS NULL
                  AND progress_status = 'done'
                """
            )
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
                    document_id TEXT,
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
                    ai_provider_label TEXT NOT NULL DEFAULT '',
                    ai_base_url TEXT NOT NULL DEFAULT '',
                    ai_model TEXT NOT NULL DEFAULT '',
                    api_key_encrypted TEXT NOT NULL DEFAULT '',
                    encryption_nonce TEXT NOT NULL DEFAULT '',
                    configured_by TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(org_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(configured_by) REFERENCES employee_accounts(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS org_object_storage_config (
                    org_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL DEFAULT '',
                    credentials_encrypted TEXT NOT NULL DEFAULT '',
                    encryption_nonce TEXT NOT NULL DEFAULT '',
                    extra_config_json TEXT NOT NULL DEFAULT '{}',
                    enabled INTEGER NOT NULL DEFAULT 0,
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

                CREATE TABLE IF NOT EXISTS org_feishu_sync_mappings (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    local_type TEXT NOT NULL,
                    local_id TEXT NOT NULL,
                    remote_type TEXT NOT NULL,
                    remote_id TEXT NOT NULL DEFAULT '',
                    remote_url TEXT NOT NULL DEFAULT '',
                    sync_status TEXT NOT NULL DEFAULT 'idle',
                    sync_message TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    last_synced_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(organization_id, local_type, local_id, remote_type),
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_org_feishu_sync_mappings_local
                    ON org_feishu_sync_mappings(organization_id, local_type, local_id, remote_type);
                CREATE INDEX IF NOT EXISTS idx_org_feishu_sync_mappings_status
                    ON org_feishu_sync_mappings(organization_id, sync_status, updated_at DESC);

                CREATE TABLE IF NOT EXISTS org_feishu_sync_outbox (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    local_type TEXT NOT NULL,
                    local_id TEXT NOT NULL,
                    remote_type TEXT NOT NULL,
                    action TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    sync_status TEXT NOT NULL DEFAULT 'queued',
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT NOT NULL DEFAULT '',
                    due_at TEXT,
                    processed_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_org_feishu_sync_outbox_due
                    ON org_feishu_sync_outbox(organization_id, sync_status, due_at, updated_at DESC);

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
                    document_id TEXT,
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

                -- Phase 1.5c · 战略陪伴叙事面板 (组织共享, A/B 账号同源)
                -- 每个客户最新版的 6 维度故事网, 由 LLM 基于关系网生成, 多人共同编织
                CREATE TABLE IF NOT EXISTS client_narrative_versions (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    rev INTEGER NOT NULL DEFAULT 1,
                    generator TEXT NOT NULL DEFAULT 'ai',
                    generated_at TEXT NOT NULL,
                    model_name TEXT NOT NULL DEFAULT '',
                    dim_essence_json TEXT NOT NULL DEFAULT '{}',
                    dim_people_json TEXT NOT NULL DEFAULT '{}',
                    dim_history_json TEXT NOT NULL DEFAULT '{}',
                    dim_commitments_json TEXT NOT NULL DEFAULT '{}',
                    dim_risks_json TEXT NOT NULL DEFAULT '{}',
                    dim_next_json TEXT NOT NULL DEFAULT '{}',
                    overall_confidence REAL NOT NULL DEFAULT 0.0,
                    open_clarifications_count INTEGER NOT NULL DEFAULT 0,
                    data_layer_gaps_json TEXT NOT NULL DEFAULT '[]',
                    is_latest INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    UNIQUE(client_id, rev)
                );
                CREATE INDEX IF NOT EXISTS idx_client_narrative_versions_org_client_latest
                    ON client_narrative_versions(organization_id, client_id, is_latest, rev DESC);
                CREATE INDEX IF NOT EXISTS idx_client_narrative_versions_client_rev
                    ON client_narrative_versions(client_id, rev DESC);

                -- 共同编织追溯: 谁问/谁答/哪段维度/原话内容
                CREATE TABLE IF NOT EXISTS client_narrative_clarifications (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    based_on_rev INTEGER NOT NULL,
                    dimension TEXT NOT NULL,
                    question TEXT NOT NULL DEFAULT '',
                    asked_by TEXT NOT NULL DEFAULT 'ai',
                    answer TEXT NOT NULL,
                    answered_by_user_id TEXT,
                    answered_by_display_name TEXT NOT NULL DEFAULT '',
                    answered_at TEXT NOT NULL,
                    resulted_in_rev INTEGER,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(answered_by_user_id) REFERENCES employee_accounts(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_client_narrative_clarif_client_created
                    ON client_narrative_clarifications(client_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_client_narrative_clarif_org_status
                    ON client_narrative_clarifications(organization_id, status, updated_at DESC);

                -- 历史叙事版本快照 (审计可还原)
                CREATE TABLE IF NOT EXISTS client_narrative_revisions (
                    client_id TEXT NOT NULL,
                    rev INTEGER NOT NULL,
                    organization_id TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    trigger TEXT NOT NULL DEFAULT 'initial',
                    triggered_by_user_id TEXT,
                    triggered_by_display_name TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (client_id, rev),
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(triggered_by_user_id) REFERENCES employee_accounts(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_client_narrative_revisions_org_created
                    ON client_narrative_revisions(organization_id, created_at DESC);
                """
            )
            # v1.0 事实澄清模块 6 层重构 — 新增 4 个 layer 字段 (essence + people 复用旧字段)
            # 新 6 层映射:
            #   Layer 1 essence       → dim_essence_json (复用)
            #   Layer 2 cooperation   → dim_cooperation_json (新)
            #   Layer 3 business_intro → dim_business_intro_json (新)
            #   Layer 4 people        → dim_people_json (复用, 语义升级到 v1)
            #   Layer 5 timeline      → dim_timeline_json (新)
            #   Layer 6 next_steps    → dim_next_steps_json (新)
            #   废弃: dim_history_json / dim_commitments_json / dim_risks_json / dim_next_json
            #         (保留 schema 兼容旧 rev, 但新 rev 用新字段)
            self._ensure_column("client_narrative_versions", "dim_cooperation_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column("client_narrative_versions", "dim_business_intro_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column("client_narrative_versions", "dim_timeline_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column("client_narrative_versions", "dim_next_steps_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column("client_narrative_versions", "schema_version", "TEXT NOT NULL DEFAULT 'v0'")

            self._ensure_column("org_ai_config", "ai_provider_label", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("org_ai_config", "ai_base_url", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("task_attachments", "document_id", "TEXT")
            self._ensure_column("event_line_attachments", "document_id", "TEXT")

            # 主线还原 LLM 叙事 (P1) — AI 把碎片素材重组成 3-5 个关键转折点
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS cloud_event_line_timeline_narratives (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    event_line_id TEXT NOT NULL,
                    rev INTEGER NOT NULL DEFAULT 1,
                    headline TEXT NOT NULL DEFAULT '',
                    opening TEXT NOT NULL DEFAULT '',
                    closing TEXT NOT NULL DEFAULT '',
                    nodes_json TEXT NOT NULL DEFAULT '[]',
                    overall_confidence REAL NOT NULL DEFAULT 0,
                    generator TEXT NOT NULL DEFAULT 'ai',
                    model_name TEXT NOT NULL DEFAULT '',
                    triggered_by_user_id TEXT,
                    triggered_by_display_name TEXT NOT NULL DEFAULT '',
                    trigger TEXT NOT NULL DEFAULT 'manual',
                    is_latest INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(event_line_id) REFERENCES event_lines(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_eline_narrative_latest
                    ON cloud_event_line_timeline_narratives(event_line_id, is_latest);
                """
            )

            # ── 数据中心加工层 Phase 1 第 1/4 项 ──
            # 项目档案：「项目本质」维度的结构化骨架
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS cloud_client_strategic_profiles (
                    client_id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    project_type TEXT NOT NULL DEFAULT '',
                    project_goal TEXT NOT NULL DEFAULT '',
                    success_metric TEXT NOT NULL DEFAULT '',
                    current_phase TEXT NOT NULL DEFAULT '',
                    cooperation_start_date TEXT,
                    cooperation_end_date TEXT,
                    notes TEXT NOT NULL DEFAULT '',
                    updated_by_user_id TEXT,
                    updated_by_display_name TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_strategic_profiles_org
                    ON cloud_client_strategic_profiles(organization_id);

                -- 人物花名册：「关键人物」维度的结构化骨架
                CREATE TABLE IF NOT EXISTS cloud_external_persons (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    role_title TEXT NOT NULL DEFAULT '',
                    affiliation TEXT NOT NULL DEFAULT '',
                    relationship_type TEXT NOT NULL DEFAULT '',
                    one_liner TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_by_user_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_external_persons_client
                    ON cloud_external_persons(organization_id, client_id, sort_order);
                """
            )

            # ── 组织经验墙云端同步表 (顾源源 5/27 方案 A) ──
            # 设计原则: 组织级金句墙, 同事互看, "卷" 起来
            # 数据流: 本地 exp_wall_quotes / exp_wall_reactions → push 到云端
            #         其他同事的本地 → 定时 pull 云端增量 → 合并
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS cloud_exp_wall_quotes (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    author_user_id TEXT NOT NULL,
                    quote_text TEXT NOT NULL,
                    source_excerpt TEXT NOT NULL DEFAULT '',
                    source_type TEXT NOT NULL,
                    source_object_id TEXT NOT NULL DEFAULT '',
                    category TEXT NOT NULL DEFAULT '方法论',
                    status TEXT NOT NULL DEFAULT 'active',
                    deleted_by_user_id TEXT,
                    deleted_at TEXT,
                    like_count INTEGER NOT NULL DEFAULT 0,
                    save_count INTEGER NOT NULL DEFAULT 0,
                    contribution_score REAL NOT NULL DEFAULT 0,
                    hot_score REAL NOT NULL DEFAULT 0,
                    extracted_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(author_user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_cloud_exp_wall_quotes_org_updated
                    ON cloud_exp_wall_quotes(organization_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_cloud_exp_wall_quotes_org_status_hot
                    ON cloud_exp_wall_quotes(organization_id, status, hot_score DESC);

                CREATE TABLE IF NOT EXISTS cloud_exp_wall_reactions (
                    id TEXT PRIMARY KEY,
                    quote_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    reaction_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    organization_id TEXT NOT NULL,
                    UNIQUE(quote_id, user_id, reaction_type),
                    FOREIGN KEY(quote_id) REFERENCES cloud_exp_wall_quotes(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_cloud_exp_wall_reactions_quote
                    ON cloud_exp_wall_reactions(quote_id, reaction_type);

                -- ════ 发版与反馈控制台 (RELEASE_CONSOLE_HANDOFF 契约 · 5 表) ════
                -- 动态定向 + 静态交付: org_code(=organizations.slug) 解析该装哪版, 二进制走 TOS 静态包
                CREATE TABLE IF NOT EXISTS releases (
                    id TEXT PRIMARY KEY,
                    version TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft',
                    platforms_json TEXT NOT NULL DEFAULT '[]',
                    mandatory INTEGER NOT NULL DEFAULT 0,
                    user_notes_json TEXT NOT NULL DEFAULT '{}',
                    internal_notes TEXT NOT NULL DEFAULT '',
                    screenshots_json TEXT NOT NULL DEFAULT '[]',
                    created_by TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    published_at TEXT,
                    FOREIGN KEY(created_by) REFERENCES employee_accounts(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_releases_status ON releases(status, created_at DESC);

                CREATE TABLE IF NOT EXISTS release_packages (
                    id TEXT PRIMARY KEY,
                    release_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    file_name TEXT NOT NULL DEFAULT '',
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    sha512 TEXT NOT NULL DEFAULT '',
                    download_url TEXT NOT NULL DEFAULT '',
                    blockmap_url TEXT,
                    downloadable INTEGER NOT NULL DEFAULT 1,
                    published_at TEXT,
                    FOREIGN KEY(release_id) REFERENCES releases(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_release_packages_release ON release_packages(release_id, platform);

                CREATE TABLE IF NOT EXISTS release_assignments (
                    id TEXT PRIMARY KEY,
                    release_id TEXT NOT NULL,
                    target_type TEXT NOT NULL DEFAULT 'all',
                    org_code TEXT,
                    rollout_pct INTEGER NOT NULL DEFAULT 100,
                    mandatory INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_by TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(release_id) REFERENCES releases(id) ON DELETE CASCADE,
                    FOREIGN KEY(created_by) REFERENCES employee_accounts(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_release_assignments_org ON release_assignments(org_code, status);
                CREATE INDEX IF NOT EXISTS idx_release_assignments_release ON release_assignments(release_id, status);

                CREATE TABLE IF NOT EXISTS feedback_items (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    severity TEXT NOT NULL DEFAULT 'minor',
                    title TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    submitter_user_id TEXT,
                    submitter_name TEXT NOT NULL DEFAULT '',
                    org_code TEXT,
                    version TEXT,
                    page TEXT,
                    os TEXT,
                    screenshot_url TEXT,
                    log_excerpt TEXT,
                    status TEXT NOT NULL DEFAULT 'open',
                    dup_of TEXT,
                    linked_task_id TEXT,
                    linked_release_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(submitter_user_id) REFERENCES employee_accounts(id) ON DELETE SET NULL,
                    FOREIGN KEY(dup_of) REFERENCES feedback_items(id) ON DELETE SET NULL,
                    FOREIGN KEY(linked_release_id) REFERENCES releases(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_feedback_items_status ON feedback_items(status, severity, updated_at DESC);

                CREATE TABLE IF NOT EXISTS release_problem_links (
                    release_id TEXT NOT NULL,
                    feedback_id TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (release_id, feedback_id),
                    FOREIGN KEY(release_id) REFERENCES releases(id) ON DELETE CASCADE,
                    FOREIGN KEY(feedback_id) REFERENCES feedback_items(id) ON DELETE CASCADE
                );
                """
            )

            # ── 经验手册条目云端同步 (顾源源 5/27 · handbook_entries 真是前端经验墙真当前真数据源)
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS cloud_handbook_entries (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    source_type TEXT NOT NULL,
                    client_id TEXT,
                    source_object_type TEXT,
                    source_object_id TEXT,
                    source_title TEXT,
                    event_line_id TEXT,
                    event_line_name TEXT,
                    project_module_id TEXT,
                    project_module_name TEXT,
                    project_flow_id TEXT,
                    project_flow_name TEXT,
                    project_stage TEXT,
                    business_category TEXT,
                    ability_keys_json TEXT NOT NULL DEFAULT '[]',
                    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                    context_summary TEXT NOT NULL DEFAULT '',
                    reuse_count INTEGER NOT NULL DEFAULT 0,
                    last_reused_at TEXT,
                    author_user_id TEXT NOT NULL,
                    author_user_name TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active',
                    deleted_by_user_id TEXT,
                    deleted_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(author_user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_cloud_handbook_entries_org_updated
                    ON cloud_handbook_entries(organization_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_cloud_handbook_entries_org_status
                    ON cloud_handbook_entries(organization_id, status, created_at DESC);
                """
            )

            # ── 成长积分云端同步 (顾源源 5/27 阶段 1) ──
            # 同事真互看积分 → "卷" 机制生效
            # 3 表: signal_events (信号) + evidence_records (证据/积分) + validation_events (验证)
            # 派生表 (capture_states + weekly_snapshot) 真本地重算, 真不上云
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS cloud_growth_signal_events (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    user_name TEXT NOT NULL DEFAULT '',
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    review_id TEXT,
                    task_id TEXT,
                    week_label TEXT NOT NULL DEFAULT '',
                    raw_text TEXT NOT NULL DEFAULT '',
                    context_json TEXT NOT NULL DEFAULT '{}',
                    dedupe_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(organization_id, dedupe_key),
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_cloud_growth_signal_org_updated
                    ON cloud_growth_signal_events(organization_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_cloud_growth_signal_user_created
                    ON cloud_growth_signal_events(organization_id, user_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS cloud_growth_evidence_records (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    signal_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    user_name TEXT NOT NULL DEFAULT '',
                    ability_key TEXT NOT NULL,
                    evidence_type TEXT NOT NULL,
                    level TEXT NOT NULL,
                    confidence TEXT NOT NULL DEFAULT 'medium',
                    reason TEXT NOT NULL DEFAULT '',
                    review_id TEXT,
                    task_id TEXT,
                    handbook_entry_id TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    contribution_tags_json TEXT NOT NULL DEFAULT '[]',
                    org_contribution_score INTEGER NOT NULL DEFAULT 0,
                    suggested_premium_rate REAL NOT NULL DEFAULT 0,
                    validation_state TEXT NOT NULL DEFAULT 'candidate',
                    ai_reason TEXT NOT NULL DEFAULT '',
                    ai_confidence REAL NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(signal_id) REFERENCES cloud_growth_signal_events(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES employee_accounts(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_cloud_growth_evidence_org_updated
                    ON cloud_growth_evidence_records(organization_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_cloud_growth_evidence_user_ability
                    ON cloud_growth_evidence_records(organization_id, user_id, ability_key, created_at DESC);

                CREATE TABLE IF NOT EXISTS cloud_growth_validation_events (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor_id TEXT NOT NULL DEFAULT '',
                    actor_name TEXT NOT NULL DEFAULT '',
                    source_type TEXT NOT NULL DEFAULT '',
                    source_id TEXT,
                    detail_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                    FOREIGN KEY(evidence_id) REFERENCES cloud_growth_evidence_records(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_cloud_growth_validation_org_updated
                    ON cloud_growth_validation_events(organization_id, updated_at DESC);
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

    def run_in_transaction(self, callback, mode: str = "IMMEDIATE"):
        """单事务跑多步 SQL（用 raw conn，绕开每条 SQL 自动 commit）。

        execute() 每次都自动 commit，多步操作要原子性必须用这条路。
        callback 签名：(conn) -> Any，可以直接 conn.execute(...)。
        失败时回滚整批，异常向上抛。
        """
        with self._lock:
            try:
                self.conn.execute(f"BEGIN {mode}")
                result = callback(self.conn)
                self.conn.commit()
                return result
            except Exception:
                self.conn.rollback()
                raise

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
