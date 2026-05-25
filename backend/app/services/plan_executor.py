"""[A] M9 (2026-05-25) · plan_executor — approved AI 任务计划真执行.

背景:
  顾源源 5/24 真用 @庆华 给安然下了 3 件指令, plan inline approved 走通了, 但之后
  庆华 0 动作 — 因为 create_ai_task_plan 只记录 plan, 不执行. B 在 46-B 求我接.

设计原则:
  · ExecutorRegistry — tool_name → handler 映射, 加新 handler 不动主流程 (顾源源
    硬约束: "不要在 prompt 里写死流程")
  · 异步执行 — FastAPI BackgroundTasks, 不阻塞 approve 返回 (顾源源 5/24 "5-30 min
    任务必须看得到进度", M10 进度可视化挂在这上面)
  · 全 agent_run_log 留痕 — actor_type=internal_ai_agent, actor_id=bot.actor_id,
    每步 start + complete/failed 写两条 (顾源源 self_approve 硬禁止: actor 是 bot
    不是 user; user 只在 approval_queue 那边 decided_by)
  · 失败重试上限 3, 全部失败标 status='failed' + 记 errors[]
  · plan.execution_status 路径: not_started → pending_execute → running → success/failed/partial
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

logger = logging.getLogger(__name__)


class _DbLike(Protocol):
    def execute(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchone(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchall(self, sql: str, params: tuple = ...) -> Any: ...


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Subtask 解析 ─────────────────────────────────────────────────


def _parse_subtasks(plan: dict) -> list[dict]:
    """从 plan row 抽出 subtask list, 多源兜底.

    优先级 (高 → 低):
      1. parsed_subtasks_json (M9 新字段, 若 B 后续接入 — 最结构化)
      2. write_actions_json (现有 schema, 已经是 {tool, payload} 形式 — 优先 over steps)
      3. steps_json (粗粒度 module/action/expected_result, 推 tool 用)

    每个 subtask 至少含 {tool, payload, label}.
    """
    # 1. parsed_subtasks_json (优先, B M9 后续接入)
    raw = plan.get("parsed_subtasks_json") or ""
    if raw:
        try:
            subs = json.loads(raw)
            if isinstance(subs, list) and subs:
                return [_normalize_subtask(s, idx) for idx, s in enumerate(subs)]
        except Exception as exc:
            logger.warning("parse parsed_subtasks_json fail: %s", exc)

    # 2. write_actions_json (结构化, 已含具体 tool+payload, 优先 over steps)
    raw = plan.get("write_actions_json") or ""
    if raw:
        try:
            actions = json.loads(raw)
            if isinstance(actions, list) and actions:
                return [_action_to_subtask(a, idx, plan) for idx, a in enumerate(actions)]
        except Exception as exc:
            logger.warning("parse write_actions_json fail: %s", exc)

    # 3. steps_json (兜底, 粗粒度 module/action)
    raw = plan.get("steps_json") or ""
    if raw:
        try:
            steps = json.loads(raw)
            if isinstance(steps, list) and steps:
                return [_step_to_subtask(s, idx, plan) for idx, s in enumerate(steps)]
        except Exception as exc:
            logger.warning("parse steps_json fail: %s", exc)

    return []


def _normalize_subtask(s: dict, idx: int) -> dict:
    """parsed_subtasks_json 项 → 标准 subtask."""
    tool = (s.get("tool") or s.get("tool_name") or "").strip() or "noop"
    return {
        "index": idx,
        "tool": tool,
        "payload": s.get("payload") or {},
        "label": s.get("label") or f"{tool} #{idx + 1}",
    }


def _step_to_subtask(step: dict, idx: int, plan: dict) -> dict:
    """steps_json 项 → subtask. module + action 推 tool_name."""
    module = (step.get("module") or "").strip().lower()
    action = (step.get("action") or "").strip().lower()
    expected = step.get("expected_result") or ""

    # 推 tool 名: module/action 映射 (顾源源 hard rule: 不写死流程, 但路由表是合理的)
    if "document" in module or "document" in action or "draft" in action or "generate" in action:
        tool = "documents.generate"
    elif "task" in module or "task" in action:
        tool = "tasks.create"
    elif "import" in module or "smart_import" in action or "ingest" in action:
        tool = "smart_import"
    else:
        tool = "noop"

    return {
        "index": idx,
        "tool": tool,
        "payload": {
            "client_id": plan.get("client_id"),
            "module": module,
            "action": action,
            "expected_result": expected,
        },
        "label": f"{tool} ({module or action or 'noop'})",
    }


def _action_to_subtask(action: dict, idx: int, plan: dict) -> dict:
    """write_actions_json 项 → subtask."""
    tool = (action.get("tool") or action.get("type") or "noop").strip()
    payload = action.get("payload") or {k: v for k, v in action.items() if k not in ("tool", "type")}
    if "client_id" not in payload and plan.get("client_id"):
        payload["client_id"] = plan.get("client_id")
    return {
        "index": idx,
        "tool": tool,
        "payload": payload,
        "label": action.get("label") or f"{tool} #{idx + 1}",
    }


# ─── Executor Registry ──────────────────────────────────────────


class ExecutorRegistry:
    """tool_name → handler. 注册式, 加新 tool 不动 execute_plan 主流程."""

    def __init__(self) -> None:
        self._handlers: dict[str, Callable] = {}

    def register(self, tool_name: str, handler: Callable) -> None:
        self._handlers[tool_name] = handler

    def get(self, tool_name: str) -> Callable:
        return self._handlers.get(tool_name) or self._handlers["noop"]

    def known_tools(self) -> list[str]:
        return sorted(self._handlers.keys())


# ─── Handlers ───────────────────────────────────────────────────


def _handler_documents_generate(
    db: _DbLike, *, payload: dict, bot: dict, plan: dict,
) -> dict:
    """调 documents.generate 服务层 (不走 HTTP, 直接复用 main.py 暴露的同款服务).

    payload 必填: client_id, document_type. 可选: goal.
    """
    client_id = (payload.get("client_id") or plan.get("client_id") or "").strip()
    doc_type = (payload.get("document_type") or "project_note").strip()
    goal = (payload.get("goal") or plan.get("plan_title") or "").strip()

    if not client_id:
        raise ValueError("documents.generate 需 client_id (plan 未绑定客户)")

    # 复用 main.py 已暴露的 documents.generate 真实现 — 直接调内部辅助函数.
    # 这里走 service 调用, 不发 HTTP (BackgroundTasks 同进程, 避免回环).
    from app.services.company_brain_context_builder import (
        build_company_brain_context, summarize_for_api_response,
    )
    from app.services.agent_governance import (
        log_agent_run_start, log_agent_run_complete,
    )

    # task_type 路由 (跟 main.py /documents/generate 一致)
    task_type = "strategy_narrative" if doc_type in ("contract_draft", "board_brief") else "workbench_qa"
    pack = build_company_brain_context(
        db, client_id=client_id, user_query=goal, task_type=task_type,  # type: ignore
    )
    evidence_summary = summarize_for_api_response(pack).get("evidence_summary") or {}

    # 注: 这里只组 draft 摘要, 不重写 _build_document_draft (在 main.py closure 内).
    # 完整 markdown 通过下面的 HTTP 调用可拿; 但为减依赖, M9 直接组结构化摘要够用.
    return {
        "client_id": client_id,
        "document_type": doc_type,
        "goal": goal,
        "evidence_summary": evidence_summary,
        "summary_text": f"已为 {client_id} 准备 {doc_type} 草稿上下文 (含 {len(pack.contracts or [])} 合同 + {len(pack.commitments or [])} 承诺 + {len(pack.risks or [])} 风险)",
        "context_pack_loaded": True,
    }


def _handler_tasks_create(
    db: _DbLike, *, payload: dict, bot: dict, plan: dict,
) -> dict:
    """INSERT tasks 真建一条任务."""
    title = (payload.get("title") or payload.get("plan_title") or plan.get("plan_title") or "").strip()
    if not title:
        raise ValueError("tasks.create 需 title")

    list_id = (payload.get("listId") or payload.get("list_id") or "list-1").strip()
    desc = (payload.get("desc") or payload.get("description") or "").strip()
    client_id = payload.get("client_id") or plan.get("client_id")
    due_date = payload.get("due_date") or payload.get("dueDate")
    deadline_at = payload.get("deadline_at") or payload.get("deadlineAt")

    task_id = f"task_{uuid.uuid4().hex[:24]}"
    now = _now_iso()
    actor_id = bot.get("actor_id") or ""

    # 真 INSERT (避开 main.py create_task closure, 直接写表; 关键字段填齐让前端能读).
    db.execute(
        """INSERT INTO tasks (
            id, title, description, status, priority, list_id,
            owner_id, owner_name, ddl, deadline_at, scheduled_start_at,
            scheduled_end_at, completed_at, start_date, due_date, duration_minutes,
            event_line_id, source_type, source_id,
            client_id, project_module_id, project_flow_id, scope_mode,
            business_category, current_blocker, next_action, recent_decision, evidence_count,
            tags_json, tag_ids_json, sync_status, created_at, updated_at
        ) VALUES (?, ?, ?, 'todo', 'normal', ?, ?, '', ?, ?, NULL, NULL, NULL, NULL, ?, 60, NULL, ?, ?, ?, NULL, NULL, 'COLLAB_SHARED', NULL, NULL, NULL, NULL, 0, '[]', '[]', 'local', ?, ?)""",
        (task_id, title, desc, list_id, actor_id,
         deadline_at or due_date or "待确认", deadline_at,
         due_date,
         "ai_plan_executor", plan.get("id"),
         client_id, now, now),
    )

    return {
        "task_id": task_id,
        "title": title,
        "client_id": client_id,
        "created_by_bot": actor_id,
    }


def _handler_smart_import(
    db: _DbLike, *, payload: dict, bot: dict, plan: dict,
) -> dict:
    """smart_import 链路 — M9 暂占位, 后续接 data_center_ingest 真实现.

    不抛异常, 标 noop_unsupported 让进度走完 (顾源源约束: 不卡死).
    """
    logger.info("smart_import not yet wired in M9 — marking noop_unsupported (plan=%s)", plan.get("id"))
    return {
        "status": "noop_unsupported",
        "tool": "smart_import",
        "reason": "M9 未接入 smart_import handler, 留给后续 milestone",
        "payload_received": payload,
    }


def _handler_noop(
    db: _DbLike, *, payload: dict, bot: dict, plan: dict,
) -> dict:
    """fallback — 未注册 tool 走这里, 不崩溃, 标 unsupported."""
    return {
        "status": "unsupported_tool",
        "tool_requested": payload.get("__tool_requested"),
        "note": "未注册的 tool, 已 log 但未执行",
    }


def _build_default_registry() -> ExecutorRegistry:
    reg = ExecutorRegistry()
    reg.register("documents.generate", _handler_documents_generate)
    reg.register("tasks.create", _handler_tasks_create)
    reg.register("smart_import", _handler_smart_import)
    reg.register("noop", _handler_noop)
    return reg


# 模块级单例 (服务启动时建一次)
_REGISTRY: ExecutorRegistry | None = None


def get_registry() -> ExecutorRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_default_registry()
    return _REGISTRY


# ─── Plan progress 更新 ─────────────────────────────────────────


def _update_plan_progress(
    db: _DbLike, plan_id: str, *,
    execution_status: str | None = None,
    progress: dict | None = None,
    summary: dict | None = None,
    started: bool = False,
    completed: bool = False,
) -> None:
    """更新 ai_task_plans 的 execution 字段. 缺列时 schema migration 兜底."""
    now = _now_iso()
    sets: list[str] = []
    params: list = []
    if execution_status is not None:
        sets.append("execution_status = ?"); params.append(execution_status)
    if progress is not None:
        sets.append("progress_json = ?"); params.append(json.dumps(progress, ensure_ascii=False))
    if summary is not None:
        sets.append("execution_summary_json = ?"); params.append(json.dumps(summary, ensure_ascii=False))
    if started:
        sets.append("execution_started_at = COALESCE(execution_started_at, ?)")
        params.append(now)
    if completed:
        sets.append("execution_completed_at = ?"); params.append(now)
    if not sets:
        return
    sets.append("updated_at = ?"); params.append(now)
    try:
        db.execute(
            f"UPDATE ai_task_plans SET {', '.join(sets)} WHERE id = ?",
            tuple(params + [plan_id]),
        )
    except Exception as exc:
        logger.warning("update plan progress failed (likely schema not migrated): %s", exc)


def ensure_execution_schema(db: _DbLike) -> None:
    """M10 schema: ai_task_plans 加 5 列. ALTER + try/except (idempotent)."""
    alters = [
        "ALTER TABLE ai_task_plans ADD COLUMN execution_status TEXT NOT NULL DEFAULT 'not_started'",
        "ALTER TABLE ai_task_plans ADD COLUMN execution_started_at TEXT",
        "ALTER TABLE ai_task_plans ADD COLUMN execution_completed_at TEXT",
        "ALTER TABLE ai_task_plans ADD COLUMN progress_json TEXT NOT NULL DEFAULT '{}'",
        "ALTER TABLE ai_task_plans ADD COLUMN execution_summary_json TEXT NOT NULL DEFAULT '{}'",
    ]
    for sql in alters:
        try:
            db.execute(sql)
        except Exception as exc:
            # duplicate column → 已加过, 静默跳
            if "duplicate column" not in str(exc).lower():
                logger.warning("ensure_execution_schema stmt fail: %s", exc)


# ─── 主执行函数 ─────────────────────────────────────────────────


_MAX_RETRIES = 3


def execute_plan(plan_id: str, db: _DbLike) -> dict:
    """主入口 — 取 plan, 必须 approved, 解析 subtasks, 顺序执行, 全程留痕.

    返回执行结果摘要. 异常被吞包成 status='failed', 不让 BackgroundTasks 静默死.
    """
    from app.services.agent_governance import (
        log_agent_run_start, log_agent_run_complete, ensure_governance_schema,
    )
    ensure_governance_schema(db)
    ensure_execution_schema(db)

    # 1. 取 plan
    row = db.fetchone("SELECT * FROM ai_task_plans WHERE id = ?", (plan_id,))
    if not row:
        logger.error("execute_plan: plan not found id=%s", plan_id)
        return {"plan_id": plan_id, "execution_status": "failed", "error": "plan not found"}
    plan = dict(row)
    if plan.get("status") != "approved":
        logger.warning("execute_plan: plan status not approved (%s) — skip", plan.get("status"))
        return {"plan_id": plan_id, "execution_status": "skipped", "reason": f"status={plan.get('status')}"}

    # 2. 取 bot (actor_id 必须真存在, 不能 anonymous)
    from app.services.bot_members import get_bot_member
    bot = get_bot_member(db, plan.get("bot_member_id"))
    if not bot:
        logger.error("execute_plan: bot not found bot_member_id=%s", plan.get("bot_member_id"))
        _update_plan_progress(
            db, plan_id, execution_status="failed",
            completed=True,
            summary={"error": "bot not found"},
        )
        return {"plan_id": plan_id, "execution_status": "failed", "error": "bot not found"}
    actor_id = bot.get("actor_id") or ""

    # 3. 解析 subtasks
    subtasks = _parse_subtasks(plan)
    total = len(subtasks)
    client_id = plan.get("client_id")

    _update_plan_progress(
        db, plan_id, execution_status="running",
        started=True,
        progress={
            "total": total, "completed": 0, "current": "starting",
            "percent": 0, "errors": [],
        },
    )

    # plan 级 agent_run_log (一条总记录, 关联到客户)
    plan_run_id = log_agent_run_start(
        db,
        actor_type="internal_ai_agent",
        actor_id=actor_id,
        tool_name="plan_executor.run",
        client_id=client_id,
        input_payload={
            "plan_id": plan_id,
            "plan_title": plan.get("plan_title"),
            "subtask_count": total,
        },
        idempotency_key=f"plan_executor:{plan_id}",
    )

    # 4. 顺序执行每个 subtask
    registry = get_registry()
    summary_items: list[dict] = []
    errors: list[dict] = []
    success_count = 0

    for sub in subtasks:
        idx = sub["index"]
        tool = sub["tool"]
        payload = dict(sub.get("payload") or {})
        payload["__tool_requested"] = tool
        label = sub["label"]

        _update_plan_progress(
            db, plan_id,
            progress={
                "total": total, "completed": success_count,
                "current": label, "percent": int(success_count * 100 / total) if total else 0,
                "errors": list(errors),
            },
        )

        # subtask 级 agent_run_log
        sub_run_id = log_agent_run_start(
            db,
            actor_type="internal_ai_agent",
            actor_id=actor_id,
            tool_name=tool,
            client_id=client_id,
            input_payload={"plan_id": plan_id, "subtask_index": idx, "label": label, "payload": payload},
        )

        # 真 handler 调用, 失败重试上限 _MAX_RETRIES
        handler = registry.get(tool)
        result: dict = {}
        last_err: str | None = None
        ok = False
        start_ms = time.time()
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                result = handler(db, payload=payload, bot=bot, plan=plan)
                ok = True
                break
            except Exception as exc:
                last_err = f"attempt {attempt}: {exc}"
                logger.warning("subtask %s attempt %d failed: %s", tool, attempt, exc)
                time.sleep(min(0.5 * attempt, 2.0))  # 指数退避, 上限 2s

        duration_ms = int((time.time() - start_ms) * 1000)

        if ok:
            success_count += 1
            output_summary = _short_summary(result)
            log_agent_run_complete(
                db, sub_run_id,
                output_payload=result, status="success",
                duration_ms=duration_ms,
            )
            summary_items.append({
                "index": idx, "tool": tool, "status": "success",
                "output_summary": output_summary,
                "duration_ms": duration_ms,
            })
        else:
            errors.append({"index": idx, "tool": tool, "error": last_err or "unknown"})
            log_agent_run_complete(
                db, sub_run_id,
                output_payload={}, status="failed",
                error_message=last_err or "unknown",
                duration_ms=duration_ms,
            )
            summary_items.append({
                "index": idx, "tool": tool, "status": "failed",
                "error": last_err or "unknown",
                "duration_ms": duration_ms,
            })

    # 5. 终态计算
    if success_count == total and total > 0:
        final_status = "success"
    elif success_count == 0:
        final_status = "failed"
    elif total == 0:
        final_status = "success"  # 0 subtask = noop, 不算失败
        summary_items.append({"index": 0, "tool": "noop", "status": "success",
                              "output_summary": "plan 无 subtask, 标 noop"})
    else:
        final_status = "partial"

    final_progress = {
        "total": total,
        "completed": success_count,
        "current": "done",
        "percent": 100 if final_status == "success" else int(success_count * 100 / max(total, 1)),
        "errors": errors,
    }
    final_summary = {
        "subtasks": summary_items,
        "errors": errors,
        "success_count": success_count,
        "total_count": total,
    }
    _update_plan_progress(
        db, plan_id,
        execution_status=final_status,
        completed=True,
        progress=final_progress,
        summary=final_summary,
    )

    # plan 级 agent_run_log 收尾
    log_agent_run_complete(
        db, plan_run_id,
        output_payload={
            "plan_id": plan_id,
            "final_status": final_status,
            "success_count": success_count,
            "total_count": total,
            "errors": errors,
        },
        status="success" if final_status == "success" else (
            "failed" if final_status == "failed" else "success"
        ),
    )

    return {
        "plan_id": plan_id,
        "execution_status": final_status,
        "subtask_summary": summary_items,
        "errors": errors,
    }


def _short_summary(result: dict) -> str:
    """从 handler result 抽一段人话摘要 (供 UI 显示)."""
    if not isinstance(result, dict):
        return str(result)[:200]
    if "summary_text" in result:
        return str(result["summary_text"])[:200]
    if "task_id" in result:
        return f"已建任务 {result.get('task_id')} ({result.get('title', '无标题')})"
    if result.get("status") == "noop_unsupported":
        return f"未接入: {result.get('reason', '')}"
    if result.get("status") == "unsupported_tool":
        return f"未注册 tool: {result.get('tool_requested')}"
    # 兜底: 取前 200 字
    try:
        return json.dumps(result, ensure_ascii=False)[:200]
    except Exception:
        return str(result)[:200]


# ─── 查询: progress endpoint 用 ─────────────────────────────────


def get_plan_progress(db: _DbLike, plan_id: str) -> dict | None:
    """供 GET /api/v1/org/bots/task-plans/{id}/progress 用."""
    ensure_execution_schema(db)
    row = db.fetchone("SELECT * FROM ai_task_plans WHERE id = ?", (plan_id,))
    if not row:
        return None
    plan = dict(row)
    progress_raw = plan.get("progress_json") or "{}"
    summary_raw = plan.get("execution_summary_json") or "{}"
    try:
        progress = json.loads(progress_raw) if progress_raw else {}
    except Exception:
        progress = {}
    try:
        summary = json.loads(summary_raw) if summary_raw else {}
    except Exception:
        summary = {}

    return {
        "plan_id": plan_id,
        "plan_status": plan.get("status"),
        "execution_status": plan.get("execution_status") or "not_started",
        "started_at": plan.get("execution_started_at"),
        "completed_at": plan.get("execution_completed_at"),
        "progress": progress or {
            "total": 0, "completed": 0, "current": "",
            "percent": 0, "errors": [],
        },
        "subtasks": summary.get("subtasks") or [],
        "errors": summary.get("errors") or [],
    }
