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
                SET organization_id = ?, name = ?, color = ?, sort_order = ?, is_default = ?, archived_at = NULL
                WHERE id = ?
                """,
                (organization_id, name, color, sort_order, is_default, list_id),
            )
        else:
            db.execute(
                """
                INSERT INTO task_lists(id, organization_id, name, color, sort_order, is_default, archived_at)
                VALUES(?, ?, ?, ?, ?, ?, NULL)
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
