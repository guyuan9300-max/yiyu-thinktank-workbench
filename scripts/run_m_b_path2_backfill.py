"""[A] M-B · 路径 2 backfill: event_line_activities + tasks + commitments + meetings + decisions + action_items → atomic_facts

服务: docs/V2.2_NEW_PLAN_20260522_v2.md M-B (顾源源 5/22 批准, autonomous)

跑法:
    cd ~/openclaw/workspace/V2.1
    ~/openclaw/workspace/yiyu-thinktank-workbench/backend/.venv/bin/python3 \\
        scripts/run_m_b_path2_backfill.py [client_id=client_284afd836e]

目的:
1. 把现有 event_line_activities (104) + tasks (238) + commitments (66) +
   weekly_reviews (9) + meetings (7) + decisions (3) + action_items (4) 共 ~431 条
   通过 IngestPipeline.ingest(path='task_review') 写入 atomic_facts
2. 不传 ai 给 IngestPipeline (避免 backfill 触发大量 broadcast)
3. 跑完后看 atomic_facts.update_relation 是否出现 supersedes/complement (跨源印证)

红线:
- 不污染主仓库 (跑在 V2.1 用 tmp db, 实测后才决定是否写真 prod)
- 默认 --dry-run, 加 --commit 才真写
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN_REPO = Path.home() / "openclaw/workspace/yiyu-thinktank-workbench"
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))
sys.path.append(str(MAIN_REPO / "backend"))
sys.path.append(str(MAIN_REPO))

PROD_DB = Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2/app.db"
DEFAULT_CID = "client_284afd836e"  # 日慈


def main():
    client_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CID
    is_dry = "--commit" not in sys.argv

    print(f"\n{'=' * 72}")
    print(f"  [A] M-B · 路径 2 backfill → atomic_facts")
    print(f"  client_id: {client_id}")
    print(f"  mode: {'DRY-RUN (tmp db)' if is_dry else 'COMMIT (写 prod)'}")
    print(f"{'=' * 72}\n")

    if is_dry:
        tmp_dir = Path(tempfile.mkdtemp(prefix="m_b_backfill_"))
        data_dir = tmp_dir / "data"
        data_dir.mkdir()
        shutil.copy(PROD_DB, data_dir / "app.db")
        print(f"tmp db: {data_dir}/app.db")
    else:
        data_dir = PROD_DB.parent
        print(f"⚠ 写真 prod db: {data_dir}")

    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app(data_dir)
    client = TestClient(app)
    client.__enter__()
    state = app.state.app_state
    db = state.db

    from app.services.ingest_pipeline import (
        IngestPipeline, IngestRequest, metadata_for_task_review,
    )
    # 不传 ai → broadcast skip (backfill 不触发大量 LLM)
    pipeline = IngestPipeline(db, ai=None)
    actor_id = "M-B backfill 2026-05-22"
    ai_session_id = f"m_b_backfill_{int(time.time())}"

    stats = {
        "event_line_activities": 0,
        "tasks": 0,
        "commitments": 0,
        "weekly_reviews": 0,
        "meetings": 0,
        "decisions": 0,
        "action_items": 0,
    }
    relations: Counter[str] = Counter()
    errors = []

    def _ingest(subject, attribute, value, evidence, source_v2_doc_id, sub_kind, time_anchor, source_label):
        try:
            metadata = metadata_for_task_review(
                sub_kind=sub_kind,
                actor_id=actor_id,
                time_anchor=time_anchor,
            )
            req = IngestRequest(
                path="task_review",
                client_id=client_id,
                subject_text=(subject or "").strip()[:200],
                attribute=(attribute or "").strip()[:100],
                value_text=(value or "").strip()[:500],
                metadata=metadata,
                source_v2_document_id=source_v2_doc_id,
                evidence_text=(evidence or "").strip()[:500],
                ai_session_id=ai_session_id,
            )
            if not req.subject_text or not req.value_text:
                return
            result = pipeline.ingest(req)
            relations[result.update_relation] += 1
            if result.written:
                stats[source_label] += 1
        except Exception as exc:
            errors.append(f"{source_label}: {exc}")

    # ─── event_line_activities (日慈相关) ─────────────
    print("▸ 1/7 event_line_activities backfill...", flush=True)
    rows = db.fetchall("""
        SELECT a.happened_at, a.source_type, a.source_id, a.actor_id, a.actor_name,
               a.title, a.summary, el.name AS event_line_name
        FROM event_line_activities a
        JOIN event_lines el ON el.id = a.event_line_id
        WHERE el.primary_client_id = ?
        ORDER BY a.happened_at DESC
    """, (client_id,))
    for r in rows:
        actor = (r["actor_name"] or "system").strip()
        title = (r["title"] or "").strip()
        if not title:
            continue
        if r["source_type"] == "task_activity":
            attr = "新增任务" if "新增任务" in title else "任务动作"
            value = title.replace("新增任务:", "").replace("新增任务:", "").strip()
            subj = actor
        elif r["source_type"] == "document_ingest":
            attr = "新增文件关联"
            value = title.replace("新资料关联:", "").replace("新资料关联:", "").strip()
            subj = r["event_line_name"]
        elif r["source_type"] == "attachment":
            attr = "上传附件"
            value = title.replace("上传附件:", "").replace("上传附件:", "").strip()
            subj = r["event_line_name"]
        else:
            attr = r["source_type"]
            value = title
            subj = actor
        _ingest(subj, attr, value, r["summary"] or title,
                None, "task", r["happened_at"], "event_line_activities")
    print(f"  ✓ {stats['event_line_activities']} 条写入")

    # ─── tasks (日慈相关) ─────────────────
    print("▸ 2/7 tasks backfill...", flush=True)
    rows = db.fetchall("""
        SELECT id, title, description, status, owner_name, current_blocker,
               next_action, recent_decision, business_category, created_at, due_date
        FROM tasks WHERE client_id = ?
    """, (client_id,))
    for r in rows:
        title = (r["title"] or "").strip()
        if not title:
            continue
        # task title 本身作为 fact
        _ingest(r["owner_name"] or "顾源源", "任务",
                title, r["description"] or title,
                None, "task", r["created_at"], "tasks")
        # current_blocker / next_action / recent_decision 各作为独立 fact
        for fld, attr in [("current_blocker", "当前卡点"),
                          ("next_action", "下一步动作"),
                          ("recent_decision", "近期决策")]:
            v = (r[fld] or "").strip()
            if v:
                _ingest(title, attr, v, v, None, "task", r["created_at"], "tasks")
    print(f"  ✓ {stats['tasks']} 条")

    # ─── commitments ───────────────────
    print("▸ 3/7 commitments backfill...", flush=True)
    rows = db.fetchall("""
        SELECT committer, recipient, commitment_type, content, deadline, status
        FROM commitments WHERE client_id = ?
    """, (client_id,))
    for r in rows:
        if not r["content"]:
            continue
        _ingest(r["committer"] or "顾源源", f"承诺_{r['commitment_type'] or '通用'}",
                r["content"], r["content"], None, "task", r["deadline"], "commitments")
    print(f"  ✓ {stats['commitments']} 条")

    # ─── weekly_reviews + entries ──────────
    print("▸ 4/7 weekly_reviews backfill...", flush=True)
    rows = db.fetchall("""
        SELECT week_label, work_progress, work_blocker, user_id
        FROM weekly_reviews
    """)
    for r in rows:
        if not r["work_progress"]:
            continue
        _ingest(r["user_id"] or "顾源源", f"周复盘_{r['week_label']}_进展",
                r["work_progress"], r["work_progress"],
                None, "weekly_review", None, "weekly_reviews")
        if r["work_blocker"]:
            _ingest(r["user_id"] or "顾源源", f"周复盘_{r['week_label']}_卡点",
                    r["work_blocker"], r["work_blocker"],
                    None, "weekly_review", None, "weekly_reviews")
    print(f"  ✓ {stats['weekly_reviews']} 条")

    # ─── meetings ──────────────────
    print("▸ 5/7 meetings backfill...", flush=True)
    rows = db.fetchall("""
        SELECT title, scheduled_at, transcript_text, notes
        FROM meetings WHERE client_id = ?
    """, (client_id,))
    for r in rows:
        if not r["title"]:
            continue
        _ingest("日慈基金会", "会议", r["title"],
                (r["notes"] or r["transcript_text"] or r["title"])[:300],
                None, "task", r["scheduled_at"], "meetings")
    print(f"  ✓ {stats['meetings']} 条")

    # ─── decisions + action_items ──────────
    print("▸ 6/7 decisions + action_items backfill...", flush=True)
    rows = db.fetchall("SELECT summary, meeting_id, created_at FROM decisions")
    for r in rows:
        if r["summary"]:
            _ingest("会议", "决议", r["summary"], r["summary"],
                    None, "task", r["created_at"], "decisions")

    rows = db.fetchall("SELECT title, owner_name, due_date FROM action_items")
    for r in rows:
        if r["title"]:
            _ingest(r["owner_name"] or "未指定", "行动项", r["title"], r["title"],
                    None, "task", r["due_date"], "action_items")
    print(f"  ✓ {stats['decisions']} decisions / {stats['action_items']} action_items")

    # ─── 总结 ──────────
    print(f"\n▸ 7/7 总结")
    print(f"\n=== M-B backfill 统计 ===")
    total = sum(stats.values())
    for src, c in stats.items():
        print(f"  {src:<25} {c:>4}")
    print(f"  TOTAL: {total}")

    print(f"\n=== update_relation 分布 (★ 跨源印证真相) ===")
    total_r = sum(relations.values())
    for r, c in relations.most_common():
        pct = c/total_r*100 if total_r else 0
        print(f"  {r:<15} {c:>4}  ({pct:.1f}%)")

    if errors:
        print(f"\n=== {len(errors)} 错误 (前 5) ===")
        for e in errors[:5]: print(f"  · {e}")

    # 跑完后看 atomic_facts 总数变化
    cnt = db.fetchone("SELECT COUNT(*) FROM atomic_facts WHERE client_id=?", (client_id,))
    print(f"\natomic_facts 当前总数 (日慈): {cnt[0] if cnt else 0}")

    if is_dry:
        print(f"\n⚠ DRY-RUN 完毕. tmp db 不会污染 prod.")
        print(f"  如果数字看着对, 加 --commit 重跑写真 prod.")
        print(f"  tmp db: {tmp_dir}")

    client.__exit__(None, None, None)


if __name__ == "__main__":
    main()
