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
        leader_password=DEFAULT_SIM_PASSWORD,
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
        leader_password=DEFAULT_SIM_PASSWORD,
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
        leader_password=DEFAULT_SIM_PASSWORD,
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
        leader_password=DEFAULT_SIM_PASSWORD,
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
                approved_at = COALESCE(approved_at, ?), approved_by = COALESCE(approved_by, 'user_admin_demo'),
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
            ) VALUES(?, ?, ?, ?, ?, ?, 'approved', ?, 'user_admin_demo', NULL, NULL, '[]', NULL, ?, ?, ?, ?)
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
        "user_qinghua": ("庆华", "member-a@example.org"),
        "user_jiale": ("佳乐", "member-d@example.org"),
        "user_dazhou": ("大周", "member-e@example.org"),
        "user_jianing": ("嘉宁", "member-b@example.org"),
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
                leader_user_id="user_admin_demo",
                title=leader_title,
                focus=department.focus_tracks[0],
            )
        )
        for index, (user_id, full_name, title) in enumerate(department.member_specs):
            email = (
                "member-b@example.org"
                if user_id == "user_jianing"
                else ("member-c@example.org" if user_id == "user_yishuo" else f"{user_id.replace('user_', '')}@example.org")
            )
            password = DEFAULT_SIM_PASSWORD
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
    ceo_user_id: str = "user_admin_demo",
    ceo_name: str = "用户甲",
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
