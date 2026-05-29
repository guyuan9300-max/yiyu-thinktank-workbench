#!/usr/bin/env python3
"""[B] 5/25 PM · 一次性脚本: 回填 path D 改动 (16:56) 之前的历史 plan.

背景:
  管理员甲 5/25 反馈"事件复盘看不到成员甲做的事".
  真因: path D handler (auto-build task + auto-review) 只对未来 plan 生效,
        历史 6 个 success plan 全在 path D 之前跑, 没自动写 task/复盘.

这个脚本:
  · 扫 ai_task_plans WHERE bot=成员甲 + status=approved + execution_status=success/partial
  · 每个 plan 拉它的 agent_run_log 真动作 (documents.generate + tasks.create)
  · documents.generate → 建 task (status=done, owner=成员甲, 管理员甲为协作者) + 复盘 entry
  · tasks.create → 建会议 task (status=todo) + 复盘 entry
  · 复盘 entry 给成员甲本周 + 发起人本周 各一份 (path C 双重归属)

幂等: 已回填过 (source_id=plan_id 已有 task) 的 plan 跳过.
"""
import json
import sqlite3
import sys
import uuid
from datetime import datetime
from pathlib import Path

DB_PATH = Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2_V21Lab/app.db"

BOT_ID = "botmem_7fcfcd0e47fc437a92671b40"
BOT_ACTOR_ID = "bot_60ab0ec2b071"
BOT_DISPLAY_NAME = "成员甲"


def _now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _current_week_label() -> str:
    iso = datetime.now().isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _bot_write_self_review(action: str, output_summary: str) -> str:
    """简化版自动复盘 (规则生成, 不调 LLM, 回填够用)."""
    return "\n".join([
        f"【做了什么】{output_summary or action}",
        "【依据数据源】客户工作台已有材料 + plan_text 设定 (回填时未重读 evidence)",
        "【不足 / 待改进】",
        "  1. 本条复盘为回填生成 (因 path D handler 改前的 plan 没自动写复盘)",
        "  2. 没接历史合同 RAG, 合同结构可能用通用法律模板",
        "  3. 评估字数 / 引用密度 待管理员甲审阅",
        "【下一步】",
        "  1. 等管理员甲审阅, 按反馈修改",
        "  2. RAG 接好后重做合同条款",
    ])


def _ensure_weekly_review(conn, *, user_id: str, week_label: str) -> str:
    row = conn.execute(
        "SELECT id FROM weekly_reviews WHERE user_id=? AND week_label=? LIMIT 1",
        (user_id, week_label),
    ).fetchone()
    if row:
        return row[0]
    review_id = f"review_{uuid.uuid4().hex[:10]}"
    now = _now_iso()
    conn.execute(
        """INSERT INTO weekly_reviews (
            id, organization_id, week_label, operator_id, user_id,
            summary, created_at, updated_at, sync_status
        ) VALUES (?, '', ?, ?, ?, '', ?, ?, 'local')""",
        (review_id, week_label, user_id, user_id, now, now),
    )
    return review_id


def _write_review_entry(conn, *, review_id: str, task_id: str, user_id: str,
                         week_label: str, note: str, task_snapshot: dict) -> bool:
    entry_id = f"wrte_{uuid.uuid4().hex[:12]}"
    now = _now_iso()
    cur = conn.execute(
        """INSERT OR IGNORE INTO weekly_review_task_entries (
            id, organization_id, review_id, task_id, user_id, week_label,
            content_domain, note, structured_note_json, reviewed_at,
            task_snapshot_json, created_at, updated_at
        ) VALUES (?, '', ?, ?, ?, ?, 'work', ?, '{}', ?, ?, ?, ?)""",
        (entry_id, review_id, task_id, user_id, week_label, note, now,
         json.dumps(task_snapshot, ensure_ascii=False), now, now),
    )
    return cur.rowcount > 0


def _add_collab(conn, task_id: str, user_id: str, full_name: str) -> None:
    if not user_id:
        return
    now = _now_iso()
    conn.execute(
        """INSERT OR IGNORE INTO task_collaborators (
            task_id, organization_id, user_id, full_name, email,
            order_index, is_owner, inbox_status, created_at, updated_at
        ) VALUES (?, '', ?, ?, '', 0, 0, 'accepted', ?, ?)""",
        (task_id, user_id, full_name, now, now),
    )


def _create_doc_task(conn, *, plan_id, plan_created_at, doc_id, doc_title,
                      client_id, human_id, human_name, summary_text) -> str:
    task_id = f"task_{uuid.uuid4().hex[:24]}"
    now = _now_iso()
    desc = f"AI 同事 {BOT_DISPLAY_NAME} 完成 · 文档 ID: {doc_id} · {summary_text[:200]}"
    # ddl 用 plan_created_at (历史时间, 不影响日历未来事件)
    conn.execute(
        """INSERT INTO tasks (
            id, title, description, status, progress_status, priority, list_id,
            owner_id, owner_name, ddl, deadline_at, completed_at, due_date, duration_minutes,
            source_type, source_id,
            client_id, scope_mode, evidence_count,
            tags_json, tag_ids_json, sync_status,
            created_at, updated_at, creator_id
        ) VALUES (?, ?, ?, 'done', 'done', 'normal', 'list-1',
                  ?, ?, ?, ?, ?, ?, 0,
                  'ai_plan_executor', ?,
                  ?, 'COLLAB_SHARED', 0,
                  '[]', '[]', 'local',
                  ?, ?, ?)""",
        (task_id, doc_title[:80], desc,
         BOT_ACTOR_ID, BOT_DISPLAY_NAME, plan_created_at, plan_created_at,
         plan_created_at, plan_created_at,
         plan_id, client_id, plan_created_at, now, BOT_ACTOR_ID),
    )
    _add_collab(conn, task_id, human_id, human_name)
    return task_id


def _create_event_task(conn, *, plan_id, plan_created_at, evt_title, evt_ddl,
                        client_id, human_id, human_name) -> str:
    task_id = f"task_{uuid.uuid4().hex[:24]}"
    now = _now_iso()
    desc = f"AI 同事 {BOT_DISPLAY_NAME} 建会议任务 · ddl={evt_ddl or '待确认'}"
    conn.execute(
        """INSERT INTO tasks (
            id, title, description, status, progress_status, priority, list_id,
            owner_id, owner_name, ddl, deadline_at, due_date, duration_minutes,
            source_type, source_id,
            client_id, scope_mode, evidence_count,
            tags_json, tag_ids_json, sync_status,
            created_at, updated_at, creator_id
        ) VALUES (?, ?, ?, 'todo', 'todo', 'normal', 'list-1',
                  ?, ?, ?, ?, ?, 60,
                  'ai_plan_executor', ?,
                  ?, 'COLLAB_SHARED', 0,
                  '[]', '[]', 'local',
                  ?, ?, ?)""",
        (task_id, evt_title[:80], desc,
         BOT_ACTOR_ID, BOT_DISPLAY_NAME, evt_ddl or '待确认', evt_ddl, evt_ddl,
         plan_id, client_id, plan_created_at, now, BOT_ACTOR_ID),
    )
    _add_collab(conn, task_id, human_id, human_name)
    return task_id


def _add_review_pair(conn, *, task_id: str, week_label: str, note: str,
                      task_snapshot: dict, bot_user_id: str, human_id: str) -> int:
    """给两个 user (bot + human) 都写一条复盘 entry. 返回真插入数."""
    n = 0
    bot_review = _ensure_weekly_review(conn, user_id=bot_user_id, week_label=week_label)
    if _write_review_entry(conn, review_id=bot_review, task_id=task_id,
                            user_id=bot_user_id, week_label=week_label,
                            note=note, task_snapshot=task_snapshot):
        n += 1
    if human_id:
        human_review = _ensure_weekly_review(conn, user_id=human_id, week_label=week_label)
        if _write_review_entry(conn, review_id=human_review, task_id=task_id,
                                user_id=human_id, week_label=week_label,
                                note=note, task_snapshot=task_snapshot):
            n += 1
    return n


def main() -> int:
    if not DB_PATH.exists():
        print(f"❌ db 不存在: {DB_PATH}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    plans = conn.execute(
        """SELECT id, plan_title, client_id, human_initiator_id, plan_text,
                  execution_summary_json, created_at
           FROM ai_task_plans
           WHERE bot_member_id=?
             AND status='approved'
             AND execution_status IN ('success', 'partial')
           ORDER BY created_at""",
        (BOT_ID,),
    ).fetchall()
    print(f"找到 {len(plans)} 个 success/partial plan 待回填")

    week_label = _current_week_label()
    print(f"回填到本周复盘: {week_label}\n")

    task_n = 0
    entry_n = 0
    skip_n = 0

    for plan in plans:
        plan_d = dict(plan)
        plan_id = plan_d["id"]
        client_id = plan_d["client_id"] or ""
        human_id = plan_d["human_initiator_id"] or "user_admin_demo"
        plan_created = plan_d["created_at"]

        urow = conn.execute("SELECT full_name FROM mirror_users WHERE id=?", (human_id,)).fetchone()
        human_name = urow[0] if urow else human_id

        existing = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE source_type='ai_plan_executor' AND source_id=?",
            (plan_id,),
        ).fetchone()[0]
        if existing > 0:
            print(f"⊘ plan {plan_id[:25]} 已有 {existing} 个 task, 跳过")
            skip_n += 1
            continue

        print(f"→ plan {plan_id[:25]} · {plan_d['plan_title'][:40]}")

        # documents.generate 真动作 → doc task
        doc_actions = conn.execute(
            """SELECT output_json FROM agent_run_log
               WHERE actor_id=? AND tool_name='documents.generate' AND status='success'
                 AND input_json LIKE ?""",
            (BOT_ACTOR_ID, f'%{plan_id}%'),
        ).fetchall()
        for act in doc_actions:
            try:
                out = json.loads(act[0] or "{}")
            except Exception:
                continue
            doc_id = out.get("document_id", "")
            doc_row = conn.execute("SELECT title FROM documents WHERE id=?", (doc_id,)).fetchone() if doc_id else None
            doc_title = (doc_row[0] if doc_row else None) or out.get("document_title") or "(无标题)"
            summary_text = out.get("summary_text") or doc_title

            task_id = _create_doc_task(
                conn, plan_id=plan_id, plan_created_at=plan_created,
                doc_id=doc_id, doc_title=doc_title, client_id=client_id,
                human_id=human_id, human_name=human_name, summary_text=summary_text,
            )
            task_n += 1

            note = _bot_write_self_review(action=f"生成《{doc_title}》", output_summary=summary_text)
            snapshot = {"title": doc_title, "document_id": doc_id, "bot_actor_id": BOT_ACTOR_ID,
                        "client_id": client_id, "bot_display_name": BOT_DISPLAY_NAME}
            entry_n += _add_review_pair(
                conn, task_id=task_id, week_label=week_label, note=note,
                task_snapshot=snapshot, bot_user_id=BOT_ACTOR_ID, human_id=human_id,
            )
            print(f"  ✓ doc task: {doc_title[:50]}")

        # tasks.create 真动作 → event task
        evt_actions = conn.execute(
            """SELECT output_json FROM agent_run_log
               WHERE actor_id=? AND tool_name='tasks.create' AND status='success'
                 AND input_json LIKE ?""",
            (BOT_ACTOR_ID, f'%{plan_id}%'),
        ).fetchall()
        for act in evt_actions:
            try:
                out = json.loads(act[0] or "{}")
            except Exception:
                continue
            evt_title = out.get("title") or "(无标题任务)"
            evt_ddl = out.get("ddl") or out.get("due_date")

            task_id = _create_event_task(
                conn, plan_id=plan_id, plan_created_at=plan_created,
                evt_title=evt_title, evt_ddl=evt_ddl, client_id=client_id,
                human_id=human_id, human_name=human_name,
            )
            task_n += 1
            note = _bot_write_self_review(
                action=f"建任务: {evt_title}",
                output_summary=f"建任务 {evt_title} (ddl={evt_ddl or '待确认'})",
            )
            snapshot = {"title": evt_title, "ddl": evt_ddl, "bot_actor_id": BOT_ACTOR_ID,
                        "client_id": client_id}
            entry_n += _add_review_pair(
                conn, task_id=task_id, week_label=week_label, note=note,
                task_snapshot=snapshot, bot_user_id=BOT_ACTOR_ID, human_id=human_id,
            )
            print(f"  ✓ event task: {evt_title[:50]}")

    conn.commit()
    conn.close()

    print(f"\n=== 回填完成 ===")
    print(f"plan 处理: {len(plans)} (跳过 {skip_n})")
    print(f"新建 task: {task_n}")
    print(f"复盘 entry: {entry_n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
