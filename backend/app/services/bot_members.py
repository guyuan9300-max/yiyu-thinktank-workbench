"""[A] V3 Final · 组织搭建中心机器人同事 (顾源源 5/24 大型任务).

不动 mirror_users / mirror_departments (云镜像只读), 新建独立表.

数据模型 (4 张表):
  bot_members              — 机器人基本信息 (id / display_name / handle / actor_id / department_id)
  bot_reporting_lines      — 汇报审批人配置 (report_to_dept_lead / report_to_ceo)
  bot_permission_policies  — 权限策略 (capability_key + enabled + approval_required)
  ai_task_plans            — AI 任务计划 (含 status + approval_id + plan_version)

核心 capability_keys (顾源源 §4.3):
  workspace_file_write.request          可申请写入客户工作台正式文件
  data_center_parse.request             可申请触发数据中心解析
  external_material_draft.create        可生成对外材料草稿
  external_send.request                 可申请对外发送
  clarification_resolution.propose      可提出待澄清处理建议
  inline_approval.allow_from_supervisor 允许主管在指令中直接授权执行

底线 hard_denies (顾源源 §4.4, 后端硬约束, 不放 UI):
  self_approve                          机器人不能 self-approve
  delete_client_materials               删除客户资料
  direct_write_atomic_facts             直接写正式 atomic_facts
  direct_write_commitments              直接写正式 commitments
  direct_write_risk_signals             直接写正式 risk_signals
  bypass_approval_queue                 绕 approval queue
  mark_as_client_official_resource      把 AI 内容标客户官方资料
  unapproved_external_send              未审批对外发送
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Protocol

logger = logging.getLogger(__name__)


class _DbLike(Protocol):
    def execute(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchone(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchall(self, sql: str, params: tuple = ...) -> Any: ...


CAPABILITY_KEYS = [
    "workspace_file_write.request",
    "data_center_parse.request",
    "external_material_draft.create",
    "external_send.request",
    "clarification_resolution.propose",
    "inline_approval.allow_from_supervisor",
]

HARD_DENIES = [
    "self_approve",
    "delete_client_materials",
    "direct_write_atomic_facts",
    "direct_write_commitments",
    "direct_write_risk_signals",
    "bypass_approval_queue",
    "mark_as_client_official_resource",
    "unapproved_external_send",
]

# 不允许 inline approval 的高风险动作 (顾源源 §7.3)
INLINE_APPROVAL_BLOCKED_ACTIONS = [
    "external_send.request",
    "delete_client_materials",
    "modify_org_permissions",
    "mark_as_client_official_resource",
    "batch_write_atomic_facts",
    "close_critical_risks",
    "batch_handle_clarifications",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


def ensure_bot_schema(db: _DbLike) -> None:
    """创建 4 张机器人同事相关表."""
    statements = [
        """CREATE TABLE IF NOT EXISTS bot_members (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL DEFAULT '',
            display_name TEXT NOT NULL,
            handle TEXT NOT NULL UNIQUE,
            actor_id TEXT NOT NULL UNIQUE,
            actor_type TEXT NOT NULL DEFAULT 'internal_ai_agent',
            department_id TEXT,
            department_name TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active',
            created_by_user_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        """CREATE INDEX IF NOT EXISTS idx_bot_members_status
           ON bot_members(status, department_id)""",
        """CREATE TABLE IF NOT EXISTS bot_reporting_lines (
            id TEXT PRIMARY KEY,
            bot_member_id TEXT NOT NULL,
            report_to_creator INTEGER NOT NULL DEFAULT 0,
            report_to_department_lead INTEGER NOT NULL DEFAULT 0,
            report_to_ceo INTEGER NOT NULL DEFAULT 0,
            department_leader_user_ids TEXT NOT NULL DEFAULT '[]',
            ceo_user_ids TEXT NOT NULL DEFAULT '[]',
            approval_mode TEXT NOT NULL DEFAULT 'any_one',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        """CREATE INDEX IF NOT EXISTS idx_bot_reporting_member
           ON bot_reporting_lines(bot_member_id)""",
        # P1 migration: 已有 bot_reporting_lines 表加 report_to_creator 列(顾源源 5/24)
        """ALTER TABLE bot_reporting_lines ADD COLUMN report_to_creator INTEGER NOT NULL DEFAULT 0""",
        """CREATE TABLE IF NOT EXISTS bot_permission_policies (
            id TEXT PRIMARY KEY,
            bot_member_id TEXT NOT NULL,
            capability_key TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 0,
            approval_required INTEGER NOT NULL DEFAULT 1,
            approval_policy TEXT NOT NULL DEFAULT 'supervisor_required',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (bot_member_id, capability_key)
        )""",
        """CREATE INDEX IF NOT EXISTS idx_bot_perm_member
           ON bot_permission_policies(bot_member_id)""",
        """CREATE TABLE IF NOT EXISTS ai_task_plans (
            id TEXT PRIMARY KEY,
            task_id TEXT,
            bot_member_id TEXT NOT NULL,
            client_id TEXT,
            event_line_id TEXT,
            plan_title TEXT NOT NULL,
            plan_text TEXT NOT NULL DEFAULT '',
            required_modules_json TEXT NOT NULL DEFAULT '[]',
            steps_json TEXT NOT NULL DEFAULT '[]',
            expected_outputs_json TEXT NOT NULL DEFAULT '[]',
            write_actions_json TEXT NOT NULL DEFAULT '[]',
            approval_required INTEGER NOT NULL DEFAULT 1,
            approval_id TEXT,
            approval_source TEXT NOT NULL DEFAULT 'supervisor_required',
            status TEXT NOT NULL DEFAULT 'pending_approval',
            human_initiator_id TEXT,
            approved_by TEXT,
            approved_at TEXT,
            supervisor_feedback TEXT,
            plan_version INTEGER NOT NULL DEFAULT 1,
            prev_plan_json TEXT,
            created_by_actor_type TEXT NOT NULL DEFAULT 'internal_ai_agent',
            created_by_actor_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        """CREATE INDEX IF NOT EXISTS idx_ai_plans_bot
           ON ai_task_plans(bot_member_id, status)""",
        """CREATE INDEX IF NOT EXISTS idx_ai_plans_task
           ON ai_task_plans(task_id)""",
    ]
    for sql in statements:
        try:
            db.execute(sql)
        except Exception as exc:
            logger.warning("ensure_bot_schema failed for stmt: %s", exc)


def _slugify_handle(name: str) -> str:
    """中文 handle 保留, 英文 lowercase, 去空格."""
    name = name.strip()
    if not name:
        return f"bot_{uuid.uuid4().hex[:8]}"
    # 中文直接用, 英文 lowercase + 下划线
    if re.search(r"[一-龥]", name):
        return name
    return re.sub(r"\s+", "_", name.lower())


def _auto_actor_id(handle: str) -> str:
    """生成 actor_id (英文 bot_xxx 格式, 用 hex 兜底中文)."""
    if re.match(r"^[a-zA-Z0-9_]+$", handle):
        return f"bot_{handle.lower()}"
    # 中文 → hex
    import hashlib
    return f"bot_{hashlib.md5(handle.encode('utf-8')).hexdigest()[:12]}"


def create_bot_member(
    db: _DbLike,
    *,
    display_name: str,
    handle: str | None = None,
    actor_id: str | None = None,
    department_id: str | None = None,
    department_name: str = "",
    description: str = "",
    status: str = "active",
    organization_id: str = "",
    created_by_user_id: str = "",
    report_to_creator: bool = True,
    report_to_department_lead: bool = True,
    report_to_ceo: bool = False,
    department_leader_user_ids: list[str] | None = None,
    ceo_user_ids: list[str] | None = None,
    enabled_capabilities: list[str] | None = None,
) -> dict:
    """创建机器人同事 + 默认汇报线 + 默认权限策略."""
    ensure_bot_schema(db)
    display_name = display_name.strip()
    if not display_name:
        raise ValueError("display_name required")
    handle = (handle or "").strip() or _slugify_handle(display_name)
    actor_id = (actor_id or "").strip() or _auto_actor_id(handle)

    # 唯一性校验
    if db.fetchone("SELECT id FROM bot_members WHERE handle = ?", (handle,)):
        raise ValueError(f"handle 已被占用: {handle}")
    if db.fetchone("SELECT id FROM bot_members WHERE actor_id = ?", (actor_id,)):
        raise ValueError(f"actor_id 已被占用: {actor_id}")

    bot_id = _new_id("botmem")
    now = _now_iso()
    db.execute(
        """INSERT INTO bot_members (
            id, organization_id, display_name, handle, actor_id, actor_type,
            department_id, department_name, description, status,
            created_by_user_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, 'internal_ai_agent', ?, ?, ?, ?, ?, ?, ?)""",
        (bot_id, organization_id, display_name, handle, actor_id,
         department_id, department_name, description, status,
         created_by_user_id, now, now),
    )

    # 汇报线 (3 类平权: 创建人 / 部门领导 / CEO)
    rep_id = _new_id("botrep")
    db.execute(
        """INSERT INTO bot_reporting_lines (
            id, bot_member_id, report_to_creator,
            report_to_department_lead, report_to_ceo,
            department_leader_user_ids, ceo_user_ids, approval_mode,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'any_one', ?, ?)""",
        (rep_id, bot_id,
         1 if report_to_creator else 0,
         1 if report_to_department_lead else 0,
         1 if report_to_ceo else 0,
         json.dumps(department_leader_user_ids or [], ensure_ascii=False),
         json.dumps(ceo_user_ids or [], ensure_ascii=False),
         now, now),
    )

    # 权限策略 (所有 capability 默认 enabled=0, 用户开关后改)
    enabled_set = set(enabled_capabilities or [])
    for cap in CAPABILITY_KEYS:
        pid = _new_id("botperm")
        # inline_approval.allow_from_supervisor: approval_required=False (它本身是 meta 开关)
        approval_required = 0 if cap == "inline_approval.allow_from_supervisor" else 1
        db.execute(
            """INSERT INTO bot_permission_policies (
                id, bot_member_id, capability_key, enabled, approval_required,
                approval_policy, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'supervisor_required', ?, ?)""",
            (pid, bot_id, cap, 1 if cap in enabled_set else 0,
             approval_required, now, now),
        )

    return get_bot_member(db, bot_id)


def _resolve_dept_leader_user_id(db: _DbLike, department_id: str | None) -> str | None:
    """从 mirror_departments 拿当前部门 leader 的 user_id (随 leader 变更自动更新)."""
    if not department_id:
        return None
    try:
        row = db.fetchone(
            "SELECT leader_user_id FROM mirror_departments WHERE id = ?",
            (department_id,),
        )
        if row and row["leader_user_id"]:
            return str(row["leader_user_id"])
    except Exception:
        pass
    return None


def _resolve_ceo_user_ids(db: _DbLike, organization_id: str | None = None) -> list[str]:
    """从 mirror_users 找 primary_role='admin' 的 user_id 当 CEO 候选."""
    ids: list[str] = []
    try:
        if organization_id:
            rows = db.fetchall(
                """SELECT id FROM mirror_users
                   WHERE organization_id = ? AND primary_role = 'admin'
                     AND account_status = 'approved'""",
                (organization_id,),
            )
        else:
            rows = db.fetchall(
                """SELECT id FROM mirror_users
                   WHERE primary_role = 'admin' AND account_status = 'approved'""",
            )
        ids = [str(dict(r)["id"]) for r in rows or []]
    except Exception:
        pass
    return ids


def resolve_bot_approvers(db: _DbLike, bot: dict) -> dict:
    """动态算 bot 的 3 类 approvers (创建人 / 部门领导 / CEO).

    每类来源:
      · 创建人: bot_members.created_by_user_id (创建时前端传, 一般是当前 session user)
      · 部门领导: 实时查 mirror_departments.leader_user_id (随组织变更自动跟)
      · CEO: 实时查 mirror_users.primary_role='admin' (随 admin 任命变更跟)

    回退:
      若 mirror 表暂无数据 (V2.1 lab dogfood 阶段), 字段为空 list; 但 reporting flag 仍真.
    """
    rep = bot.get("reporting") or {}
    result = {
        "creator_user_id": None,
        "department_leader_user_id": None,
        "ceo_user_ids": [],
        "all_approver_user_ids": [],
        "approver_details": [],
    }
    seen: set[str] = set()
    approvers: list[dict] = []

    # 1. 创建人
    if rep.get("report_to_creator"):
        creator = bot.get("created_by_user_id") or ""
        if creator:
            result["creator_user_id"] = creator
            if creator not in seen:
                seen.add(creator)
                approvers.append({"user_id": creator, "role": "creator"})

    # 2. 部门领导
    if rep.get("report_to_department_lead"):
        # 优先用显式存的 (用户手动覆盖的); 否则自动 resolve
        explicit = rep.get("department_leader_user_ids") or []
        if explicit:
            for uid in explicit:
                if uid and uid not in seen:
                    seen.add(uid); approvers.append({"user_id": uid, "role": "department_lead"})
            result["department_leader_user_id"] = explicit[0]
        else:
            uid = _resolve_dept_leader_user_id(db, bot.get("department_id"))
            if uid:
                result["department_leader_user_id"] = uid
                if uid not in seen:
                    seen.add(uid); approvers.append({"user_id": uid, "role": "department_lead"})

    # 3. CEO
    if rep.get("report_to_ceo"):
        explicit_ceo = rep.get("ceo_user_ids") or []
        ceo_ids = explicit_ceo if explicit_ceo else _resolve_ceo_user_ids(db, bot.get("organization_id"))
        for uid in ceo_ids:
            if uid and uid not in seen:
                seen.add(uid); approvers.append({"user_id": uid, "role": "CEO"})
        result["ceo_user_ids"] = list(ceo_ids)

    result["all_approver_user_ids"] = [a["user_id"] for a in approvers]
    result["approver_details"] = approvers
    return result


def get_bot_member(db: _DbLike, bot_member_id: str) -> dict | None:
    """拿机器人完整信息 (含汇报线 + 权限策略 + 动态 resolved approvers)."""
    row = db.fetchone(
        "SELECT * FROM bot_members WHERE id = ?", (bot_member_id,),
    )
    if not row:
        return None
    d = dict(row)
    rep_row = db.fetchone(
        "SELECT * FROM bot_reporting_lines WHERE bot_member_id = ?",
        (bot_member_id,),
    )
    if rep_row:
        rd = dict(rep_row)
        try:
            rd["department_leader_user_ids"] = json.loads(rd["department_leader_user_ids"] or "[]")
            rd["ceo_user_ids"] = json.loads(rd["ceo_user_ids"] or "[]")
        except Exception:
            pass
        d["reporting"] = rd
    perm_rows = db.fetchall(
        "SELECT * FROM bot_permission_policies WHERE bot_member_id = ?",
        (bot_member_id,),
    )
    d["capabilities"] = [dict(r) for r in perm_rows or []]
    # 动态 resolved approvers (3 类平权)
    d["resolved_approvers"] = resolve_bot_approvers(db, d)
    return d


def resolve_bot_by_handle(db: _DbLike, handle: str) -> dict | None:
    """根据 handle 解析机器人(给 B 线程 @庆华 用)."""
    handle = (handle or "").strip()
    if not handle:
        return None
    row = db.fetchone(
        "SELECT id FROM bot_members WHERE handle = ? AND status = 'active'",
        (handle,),
    )
    if not row:
        return None
    return get_bot_member(db, dict(row)["id"])


def list_bot_members(db: _DbLike, *, status: str | None = None) -> list[dict]:
    """列机器人."""
    if status:
        rows = db.fetchall(
            "SELECT id FROM bot_members WHERE status = ? ORDER BY created_at DESC",
            (status,),
        )
    else:
        rows = db.fetchall(
            "SELECT id FROM bot_members ORDER BY created_at DESC",
        )
    return [get_bot_member(db, dict(r)["id"]) for r in rows or []]


def update_bot_member(
    db: _DbLike, bot_member_id: str,
    *,
    display_name: str | None = None,
    department_id: str | None = None,
    department_name: str | None = None,
    description: str | None = None,
    status: str | None = None,
    report_to_creator: bool | None = None,
    report_to_department_lead: bool | None = None,
    report_to_ceo: bool | None = None,
    department_leader_user_ids: list[str] | None = None,
    ceo_user_ids: list[str] | None = None,
    enabled_capabilities: list[str] | None = None,
) -> dict | None:
    """修改机器人 (含权限/汇报线)."""
    bot = get_bot_member(db, bot_member_id)
    if not bot:
        return None
    now = _now_iso()
    sets, params = [], []
    if display_name is not None:
        sets.append("display_name = ?"); params.append(display_name.strip())
    if department_id is not None:
        sets.append("department_id = ?"); params.append(department_id)
    if department_name is not None:
        sets.append("department_name = ?"); params.append(department_name)
    if description is not None:
        sets.append("description = ?"); params.append(description)
    if status is not None and status in ("active", "disabled"):
        sets.append("status = ?"); params.append(status)
    if sets:
        sets.append("updated_at = ?"); params.append(now)
        db.execute(
            f"UPDATE bot_members SET {', '.join(sets)} WHERE id = ?",
            tuple(params + [bot_member_id]),
        )

    # 汇报线更新
    rep_sets, rep_params = [], []
    if report_to_creator is not None:
        rep_sets.append("report_to_creator = ?")
        rep_params.append(1 if report_to_creator else 0)
    if report_to_department_lead is not None:
        rep_sets.append("report_to_department_lead = ?")
        rep_params.append(1 if report_to_department_lead else 0)
    if report_to_ceo is not None:
        rep_sets.append("report_to_ceo = ?")
        rep_params.append(1 if report_to_ceo else 0)
    if department_leader_user_ids is not None:
        rep_sets.append("department_leader_user_ids = ?")
        rep_params.append(json.dumps(department_leader_user_ids, ensure_ascii=False))
    if ceo_user_ids is not None:
        rep_sets.append("ceo_user_ids = ?")
        rep_params.append(json.dumps(ceo_user_ids, ensure_ascii=False))
    if rep_sets:
        rep_sets.append("updated_at = ?"); rep_params.append(now)
        db.execute(
            f"UPDATE bot_reporting_lines SET {', '.join(rep_sets)} WHERE bot_member_id = ?",
            tuple(rep_params + [bot_member_id]),
        )

    # 权限更新 (enabled_capabilities 给的列表 = enable, 其它 disable)
    if enabled_capabilities is not None:
        en_set = set(enabled_capabilities)
        for cap in CAPABILITY_KEYS:
            db.execute(
                """UPDATE bot_permission_policies
                   SET enabled = ?, updated_at = ?
                   WHERE bot_member_id = ? AND capability_key = ?""",
                (1 if cap in en_set else 0, now, bot_member_id, cap),
            )

    return get_bot_member(db, bot_member_id)


def get_bot_permissions(db: _DbLike, bot_member_id: str) -> dict:
    """返回机器人权限完整视图 (含 hard_denies 底线)."""
    bot = get_bot_member(db, bot_member_id)
    if not bot:
        return {"error": "bot not found"}
    return {
        "bot_member_id": bot_member_id,
        "actor_id": bot.get("actor_id"),
        "capabilities": [
            {
                "capability_key": c["capability_key"],
                "enabled": bool(c["enabled"]),
                "approval_required": bool(c["approval_required"]),
                "approval_policy": c["approval_policy"],
            }
            for c in bot.get("capabilities") or []
        ],
        "hard_denies": HARD_DENIES,
        "inline_approval_blocked_actions": INLINE_APPROVAL_BLOCKED_ACTIONS,
    }


def can_inline_authorize(
    db: _DbLike, *,
    bot_member_id: str,
    human_initiator_id: str,
    action_capability: str | None = None,
) -> tuple[bool, str]:
    """判断 human_initiator 是否能 inline authorize 该 bot 的动作.

    返回 (allowed, reason).

    硬规则:
      1. bot 必须 enable inline_approval.allow_from_supervisor
      2. human_initiator 必须在 reporting approvers 中 (department leader 或 CEO)
      3. action_capability 不在 INLINE_APPROVAL_BLOCKED_ACTIONS
    """
    bot = get_bot_member(db, bot_member_id)
    if not bot:
        return False, "bot not found"
    if bot.get("status") != "active":
        return False, "bot is disabled"

    # 1. 是否 enable inline approval
    caps = {c["capability_key"]: c for c in bot.get("capabilities") or []}
    inline_cap = caps.get("inline_approval.allow_from_supervisor")
    if not inline_cap or not inline_cap.get("enabled"):
        return False, "bot 未开启 inline_approval.allow_from_supervisor"

    # 2. 检查 action 是否在 BLOCKED 列表
    if action_capability and action_capability in INLINE_APPROVAL_BLOCKED_ACTIONS:
        return False, f"action '{action_capability}' 属于高风险, 必须单独审批 (不能 inline)"

    # 3. human_initiator 必须在 resolved_approvers 中 (3 类平权: 创建人/部门领导/CEO)
    resolved = bot.get("resolved_approvers") or resolve_bot_approvers(db, bot)
    approvers = set(resolved.get("all_approver_user_ids") or [])

    if not approvers:
        return False, "bot 未配置任何审批人 (汇报线为空)"

    if human_initiator_id not in approvers:
        return False, f"human_initiator '{human_initiator_id}' 不是该 bot 的审批人 (审批人: {sorted(approvers)})"

    # 4. 禁止 bot 自审批 (虽然 inline 是 human 授权, 但仍要校验 initiator != bot.actor_id)
    if human_initiator_id == bot.get("actor_id"):
        return False, "bot 不能自我授权 (self_approve 硬禁止)"

    return True, "ok"


# ─── AI Task Plans ───────────────────────────────────────────────


def create_ai_task_plan(
    db: _DbLike, *,
    bot_member_id: str,
    plan_title: str,
    plan_text: str = "",
    client_id: str | None = None,
    event_line_id: str | None = None,
    task_id: str | None = None,
    required_modules: list[str] | None = None,
    steps: list[dict] | None = None,
    expected_outputs: list[str] | None = None,
    write_actions: list[dict] | None = None,
    approval_required: bool = True,
    inline_authorization: bool = False,
    inline_authorization_text: str = "",
    human_initiator_id: str | None = None,
    action_capability: str | None = None,
) -> dict:
    """创建 AI 任务计划 + 自动 enqueue approval.

    inline_authorization=True 时:
      - 校验 human_initiator 是 bot 审批人 + action 不在 blocked 列表
      - 校验过则 approval 直接 status='approved', source='inline_authorization'
      - 校验不过则 fallback 到 pending_approval (返回 reason)
    """
    ensure_bot_schema(db)
    bot = get_bot_member(db, bot_member_id)
    if not bot:
        raise ValueError(f"bot_member_id 不存在: {bot_member_id}")
    if bot.get("status") != "active":
        raise ValueError("bot 已禁用")

    plan_id = _new_id("aiplan")
    now = _now_iso()
    actor_id = bot.get("actor_id") or ""

    # 默认 approval 状态
    approval_source = "supervisor_required"
    approval_status = "pending_approval"
    approved_by = None
    approved_at = None
    pending_reason = None

    # inline authorization 校验
    if inline_authorization and approval_required:
        if not human_initiator_id:
            pending_reason = "inline_authorization 需 human_initiator_id"
        else:
            allowed, reason = can_inline_authorize(
                db, bot_member_id=bot_member_id,
                human_initiator_id=human_initiator_id,
                action_capability=action_capability,
            )
            if allowed:
                approval_source = "inline_authorization"
                approval_status = "approved"
                approved_by = human_initiator_id
                approved_at = now
            else:
                pending_reason = reason

    # 创建 approval_queue 记录 (无论 pending 还是 approved 都创建, 不绕)
    approval_id = None
    if approval_required:
        from app.services.agent_governance import enqueue_approval, ApprovalRequest, decide_approval
        try:
            approval_id = enqueue_approval(db, ApprovalRequest(
                action_type="ai_plan.execute",  # type: ignore
                actor_type="internal_ai_agent",  # type: ignore
                actor_id=actor_id,
                payload={
                    "bot_member_id": bot_member_id,
                    "ai_task_plan_id": plan_id,
                    "client_id": client_id,
                    "plan_title": plan_title,
                    "action_capability": action_capability,
                    "human_initiator_id": human_initiator_id,
                    "inline_authorization_text": inline_authorization_text if inline_authorization else None,
                },
                reason=plan_title[:100],
                client_id=client_id,
                target_resource=f"ai_plan/{plan_id}",
            ))
            # inline approved 时立即 decide 为 approved
            if approval_status == "approved" and approved_by:
                decide_approval(
                    db, approval_id,
                    decision="approved",  # type: ignore
                    decided_by=approved_by,
                    decision_note=f"inline_authorization: {inline_authorization_text[:200]}",
                )
        except Exception as exc:
            logger.warning("enqueue_approval fail: %s", exc)

    db.execute(
        """INSERT INTO ai_task_plans (
            id, task_id, bot_member_id, client_id, event_line_id,
            plan_title, plan_text, required_modules_json, steps_json,
            expected_outputs_json, write_actions_json,
            approval_required, approval_id, approval_source, status,
            human_initiator_id, approved_by, approved_at, plan_version,
            created_by_actor_type, created_by_actor_id,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'internal_ai_agent', ?, ?, ?)""",
        (plan_id, task_id, bot_member_id, client_id, event_line_id,
         plan_title, plan_text,
         json.dumps(required_modules or [], ensure_ascii=False),
         json.dumps(steps or [], ensure_ascii=False),
         json.dumps(expected_outputs or [], ensure_ascii=False),
         json.dumps(write_actions or [], ensure_ascii=False),
         1 if approval_required else 0,
         approval_id, approval_source, approval_status,
         human_initiator_id, approved_by, approved_at,
         actor_id, now, now),
    )

    return {
        "ai_task_plan_id": plan_id,
        "task_id": task_id,
        "approval_id": approval_id,
        "approval_status": approval_status,
        "approval_source": approval_source,
        "approved_by": approved_by,
        "status": approval_status,
        "pending_reason": pending_reason,
    }


def decide_ai_task_plan(
    db: _DbLike, ai_task_plan_id: str,
    *,
    decision: Literal["approve", "reject", "revise"],
    decided_by: str,
    feedback: str = "",
    modified_plan: dict | None = None,
) -> dict | None:
    """主管对 AI 任务计划做出审批决定.

    decision:
      · approve  → status=approved, decide approval_queue
      · reject   → status=rejected, decide approval_queue
      · revise   → status=needs_revision, 不 decide approval (留着, B 重新提交时新建)
                   保存 supervisor_feedback
    modified_plan: revise 模式可同时改 plan_text/steps 等; 保存原 plan 到 prev_plan_json
    """
    row = db.fetchone(
        "SELECT * FROM ai_task_plans WHERE id = ?", (ai_task_plan_id,),
    )
    if not row:
        return None
    plan = dict(row)
    bot_member_id = plan.get("bot_member_id")
    bot = get_bot_member(db, bot_member_id) if bot_member_id else None

    # self-approve 硬禁止 (decided_by 不能 = bot.actor_id)
    if bot and decided_by == bot.get("actor_id"):
        raise ValueError("bot 不能 self-approve (硬禁止)")

    now = _now_iso()
    new_status, approval_decision = {
        "approve": ("approved", "approved"),
        "reject":  ("rejected", "rejected"),
        "revise":  ("needs_revision", None),
    }[decision]

    prev_plan_json = None
    if decision == "revise" and modified_plan:
        # 保存原 plan
        prev_plan_json = json.dumps({
            "plan_title": plan["plan_title"],
            "plan_text": plan["plan_text"],
            "steps": plan.get("steps_json"),
            "expected_outputs": plan.get("expected_outputs_json"),
        }, ensure_ascii=False)
        sets = ["plan_text = ?"]
        params: list = [modified_plan.get("plan_text", plan["plan_text"])]
        if "plan_title" in modified_plan:
            sets.append("plan_title = ?"); params.append(modified_plan["plan_title"])
        if "steps" in modified_plan:
            sets.append("steps_json = ?")
            params.append(json.dumps(modified_plan["steps"], ensure_ascii=False))
        if "expected_outputs" in modified_plan:
            sets.append("expected_outputs_json = ?")
            params.append(json.dumps(modified_plan["expected_outputs"], ensure_ascii=False))
        sets.append("prev_plan_json = ?"); params.append(prev_plan_json)
        sets.append("plan_version = plan_version + 1")
        sets.append("supervisor_feedback = ?"); params.append(feedback)
        sets.append("status = ?"); params.append(new_status)
        sets.append("updated_at = ?"); params.append(now)
        db.execute(
            f"UPDATE ai_task_plans SET {', '.join(sets)} WHERE id = ?",
            tuple(params + [ai_task_plan_id]),
        )
    else:
        sets = ["status = ?", "supervisor_feedback = ?",
                "approved_by = ?", "approved_at = ?", "updated_at = ?"]
        params = [new_status, feedback,
                  decided_by if decision != "revise" else None,
                  now if decision != "revise" else None, now]
        if decision == "approve":
            sets.append("approval_source = ?")
            params.append("supervisor_required")
        db.execute(
            f"UPDATE ai_task_plans SET {', '.join(sets)} WHERE id = ?",
            tuple(params + [ai_task_plan_id]),
        )

    # 同步 approval_queue
    if approval_decision and plan.get("approval_id"):
        try:
            from app.services.agent_governance import decide_approval
            decide_approval(
                db, plan["approval_id"],
                decision=approval_decision,  # type: ignore
                decided_by=decided_by,
                decision_note=f"AI plan {decision}: {feedback[:200]}",
            )
        except Exception as exc:
            logger.warning("decide_approval sync fail: %s", exc)

    # 返回最新 plan
    updated = db.fetchone(
        "SELECT * FROM ai_task_plans WHERE id = ?", (ai_task_plan_id,),
    )
    return dict(updated) if updated else None


def list_ai_task_plans(
    db: _DbLike, *,
    bot_member_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    where = []
    params: list = []
    if bot_member_id:
        where.append("bot_member_id = ?"); params.append(bot_member_id)
    if status:
        where.append("status = ?"); params.append(status)
    wsql = " WHERE " + " AND ".join(where) if where else ""
    rows = db.fetchall(
        f"SELECT * FROM ai_task_plans{wsql} ORDER BY created_at DESC LIMIT ?",
        tuple(params + [limit]),
    )
    return [dict(r) for r in rows or []]
