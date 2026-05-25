"""[A] 测试 2: event_line_activities → atomic_facts 路径打通

顾源源 5/22 核心洞察:
event_line_activities 表本身就是"时间串起人物、串起文件"的天然骨架。
当前 NarrativeKernel timeline 段空 → 因为这条主时间线从来没接进 atomic_facts。

本脚本:
1. 复制 prod db 到 tmp (不污染)
2. 查日慈战略陪伴这条 event_line 下全部 36 条活动
3. 每条活动通过 IngestPipeline 写入 atomic_facts
   - actor_name → subject_text
   - source_type 映射 → attribute (新增任务/上传附件/新增文件)
   - title → value_text
   - happened_at → time_anchor ★ 关键
   - source_v2_document_id 关联 (如果是 document_ingest)
4. 报告:
   - 时间锚完整率
   - 人物分布
   - 文件链能跳回 v2_documents 的比率
   - update_relations 分布

跑法:
    cd ~/openclaw/workspace/V2.1
    ~/openclaw/workspace/yiyu-thinktank-workbench/backend/.venv/bin/python3 \\
        scripts/run_event_line_activities_extraction.py [event_line_name]
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
import traceback
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

REPORTS_DIR = ROOT / "tests" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

PROD_DB = Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2/app.db"
DEFAULT_EVENT_LINE = "日慈战略陪伴"


@dataclass
class ActivityExtractionReport:
    event_line_id: str
    event_line_name: str
    client_id: str
    activities_total: int
    activities_with_time: int
    activities_with_actor: int
    facts_written: int
    facts_skipped: int
    facts_failed: int
    update_relations: dict[str, int] = field(default_factory=dict)
    source_type_distribution: dict[str, int] = field(default_factory=dict)
    actor_distribution: dict[str, int] = field(default_factory=dict)
    doclink_resolved: int = 0
    doclink_total: int = 0
    time_range: tuple[str, str] = ("", "")
    duration_seconds: float = 0.0
    sample_facts: list[dict] = field(default_factory=list)
    timeline_summary: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    tmp_data_dir: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_actor(actor_name: str | None, actor_id: str | None) -> str:
    """actor_name 优先, 兜底 actor_id"""
    name = (actor_name or "").strip()
    if name and name not in ("sys", "AI", "本机用户"):
        return name
    return name or (actor_id or "system")


def _activity_to_fact_shape(activity: dict, event_line_name: str) -> dict | None:
    """把 1 条 activity 转成 IngestRequest shape

    顾源源 5/22 原则: 时间锚必须保留, actor + source_type 决定 attribute
    """
    src = activity.get("source_type") or ""
    title = (activity.get("title") or "").strip()
    summary = (activity.get("summary") or "").strip()
    actor = _normalize_actor(activity.get("actor_name"), activity.get("actor_id"))
    happened_at = activity.get("happened_at")
    source_id = activity.get("source_id")

    if not title:
        return None

    # 映射: source_type → (subject, attribute)
    if src == "task_activity":
        # 提取 title 里的"新增任务:XX" 部分作 attribute
        if title.startswith("新增任务:") or title.startswith("新增任务:"):
            attribute = "新增任务"
            value_text = title.replace("新增任务:", "").replace("新增任务:", "").strip()
        elif title.startswith("任务完成"):
            attribute = "任务完成"
            value_text = summary or title
        else:
            attribute = "任务动作"
            value_text = title
        subject_text = actor
    elif src == "document_ingest":
        attribute = "新增文件关联"
        # title 类似 "新资料关联:日慈xx.docx"
        if title.startswith("新资料关联:") or title.startswith("新资料关联:"):
            value_text = title.replace("新资料关联:", "").replace("新资料关联:", "").strip()
        else:
            value_text = title
        subject_text = event_line_name
    elif src == "attachment":
        attribute = "上传附件"
        if title.startswith("上传附件:") or title.startswith("上传附件:"):
            value_text = title.replace("上传附件:", "").replace("上传附件:", "").strip()
        else:
            value_text = title
        subject_text = event_line_name
    else:
        attribute = src or "动作"
        value_text = title
        subject_text = actor or event_line_name

    return {
        "subject_text": subject_text,
        "attribute": attribute,
        "value_text": value_text,
        "actor_id": actor,
        "time_anchor": happened_at,
        "source_v2_document_id": source_id if src == "document_ingest" else None,
        "evidence_text": summary or title,
        "src": src,
        "actor_name": actor,
    }


def main() -> int:
    event_line_name = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EVENT_LINE
    print(f"\n{'=' * 72}")
    print(f"  [A] 测试 2: event_line_activities → atomic_facts")
    print(f"  event_line: {event_line_name}")
    print(f"  prod db: {PROD_DB}")
    print(f"{'=' * 72}\n")

    if not PROD_DB.exists():
        print(f"✗ prod db 不存在: {PROD_DB}")
        return 1

    report = ActivityExtractionReport(
        event_line_id="", event_line_name=event_line_name,
        client_id="", activities_total=0,
        activities_with_time=0, activities_with_actor=0,
        facts_written=0, facts_skipped=0, facts_failed=0,
    )
    started = time.perf_counter()

    try:
        # ─── Phase 1: copy db + start app ─────────────
        print("▸ 1/4 复制 prod db 到 tmp...", flush=True)
        tmp_dir = Path(tempfile.mkdtemp(prefix="event_line_ext_"))
        data_dir = tmp_dir / "data"
        data_dir.mkdir()
        shutil.copy(PROD_DB, data_dir / "app.db")
        for ext in ("-wal", "-shm"):
            wal = data_dir / f"app.db{ext}"
            if wal.exists():
                wal.unlink()
        print(f"  ✓ tmp data_dir: {data_dir}", flush=True)

        print("▸ 2/4 起 FastAPI app (会跑 migrations)...", flush=True)
        from fastapi.testclient import TestClient
        from app.main import create_app

        app = create_app(data_dir)
        client = TestClient(app)
        client.__enter__()
        state = app.state.app_state  # type: ignore[attr-defined]
        db = state.db

        # ─── Phase 2: 查 event_line + 全部 activities ─
        print(f"▸ 3/4 查 event_line「{event_line_name}」全部活动...", flush=True)
        el_row = db.fetchone(
            "SELECT id, primary_client_id FROM event_lines WHERE name = ? "
            "OR primary_client_name LIKE ? ORDER BY updated_at DESC LIMIT 1",
            (event_line_name, f"%{event_line_name.split('战略')[0]}%"),
        )
        if not el_row:
            print(f"✗ 找不到 event_line: {event_line_name}", flush=True)
            return 1
        report.event_line_id = str(el_row["id"])
        report.client_id = str(el_row["primary_client_id"] or "")

        act_rows = db.fetchall(
            """
            SELECT happened_at, source_type, source_id, actor_id, actor_name,
                   title, summary, is_key, metadata_json
            FROM event_line_activities
            WHERE event_line_id = ?
            ORDER BY happened_at ASC
            """,
            (report.event_line_id,),
        )
        activities = [dict(r) for r in act_rows]
        report.activities_total = len(activities)
        report.activities_with_time = sum(1 for a in activities if a.get("happened_at"))
        report.activities_with_actor = sum(1 for a in activities if a.get("actor_name"))
        if activities:
            times_sorted = sorted([a["happened_at"] for a in activities if a.get("happened_at")])
            if times_sorted:
                report.time_range = (times_sorted[0][:16], times_sorted[-1][:16])
        print(f"  ✓ 共 {len(activities)} 条活动, 时间锚 {report.activities_with_time} 条, 人物 {report.activities_with_actor} 条", flush=True)
        print(f"  ✓ 时间范围: {report.time_range[0]} ~ {report.time_range[1]}", flush=True)

        # ─── Phase 3: 跑 IngestPipeline ────────────────
        print(f"▸ 4/4 把 {len(activities)} 条 activity 通过 IngestPipeline 写入 atomic_facts...", flush=True)
        from app.services.ingest_pipeline import (
            IngestPipeline, IngestRequest, metadata_for_task_review,
        )

        pipeline = IngestPipeline(db)
        ai_session_id = f"event_line_extract_{int(time.time())}"
        actor_id_base = "A AI activity extractor"
        relation_counts: Counter[str] = Counter()
        src_dist: Counter[str] = Counter()
        actor_dist: Counter[str] = Counter()
        doclink_ok = 0
        doclink_total = 0

        for idx, activity in enumerate(activities):
            shape = _activity_to_fact_shape(activity, event_line_name)
            if not shape:
                report.facts_skipped += 1
                continue

            src = shape["src"]
            src_dist[src] += 1
            actor_dist[shape["actor_name"]] += 1

            if src == "task_activity":
                sub_kind = "task"
            elif src == "document_ingest":
                sub_kind = "task"  # source_type=collaboration_task, attribute='新增文件关联'
                doclink_total += 1
                # 验证 source_id 是否能跳回 v2_documents
                if shape["source_v2_document_id"]:
                    hit = db.fetchone(
                        "SELECT id FROM v2_documents WHERE id = ?",
                        (shape["source_v2_document_id"],),
                    )
                    if hit:
                        doclink_ok += 1
            else:
                sub_kind = "task"  # attachment 也走 collaboration_task

            metadata = metadata_for_task_review(
                sub_kind=sub_kind,
                actor_id=shape["actor_id"] or actor_id_base,
                time_anchor=shape["time_anchor"],
            )

            req = IngestRequest(
                path="task_review",
                client_id=report.client_id,
                subject_text=shape["subject_text"],
                attribute=shape["attribute"],
                value_text=shape["value_text"],
                metadata=metadata,
                source_v2_document_id=shape["source_v2_document_id"],
                evidence_text=shape["evidence_text"],
                ai_session_id=ai_session_id,
            )

            try:
                result = pipeline.ingest(req)
                relation_counts[result.update_relation] += 1
                if result.written:
                    report.facts_written += 1
                else:
                    report.facts_skipped += 1
            except Exception as exc:
                report.facts_failed += 1
                report.errors.append(f"activity {idx}: {exc}")
                print(f"    ✗ activity {idx} 失败: {exc}", flush=True)

        report.update_relations = dict(relation_counts)
        report.source_type_distribution = dict(src_dist)
        report.actor_distribution = dict(actor_dist)
        report.doclink_resolved = doclink_ok
        report.doclink_total = doclink_total

        print(f"  ✓ 写入 {report.facts_written} 条 facts / 跳过 {report.facts_skipped} / 失败 {report.facts_failed}", flush=True)
        print(f"  ✓ 文件链解析: {doclink_ok}/{doclink_total} (能跳回 v2_documents)", flush=True)

        # ─── Phase 4: 查写入结果 + 时间线样本 ──────────
        # 拉 atomic_facts 里本次抽出来的, 按 time_anchor 排序看是否真成"时间主线"
        fact_rows = db.fetchall(
            """
            SELECT id, subject_text, attribute, value_text, time_anchor,
                   actor_id, source_type, content_role, confidence,
                   source_v2_document_id, update_relation
            FROM atomic_facts
            WHERE actor_id = ? OR actor_id LIKE 'A AI activity%'
            ORDER BY time_anchor ASC
            """,
            (actor_id_base,),
        )
        all_facts = [dict(r) for r in fact_rows]
        # 用 ai_session_id 过滤本次的
        this_run_facts = [f for f in all_facts]  # 简化, 反正 tmp db
        # 抽 20 条样本
        report.sample_facts = [
            {
                "subject": f["subject_text"],
                "attribute": f["attribute"],
                "value": (f["value_text"] or "")[:60],
                "time": (f["time_anchor"] or "")[:16],
                "actor": f["actor_id"],
                "source": f["source_type"],
                "role": f["content_role"],
            }
            for f in this_run_facts[:30]
        ]

        # 主时间线 — 按时间排序, 每条简化
        report.timeline_summary = [
            {
                "time": (f["time_anchor"] or "")[:16],
                "actor": (f["subject_text"] or "")[:12],
                "what": f"{f['attribute']}: {(f['value_text'] or '')[:40]}",
            }
            for f in this_run_facts
            if f.get("time_anchor")
        ]

        client.__exit__(None, None, None)

    except Exception as exc:
        tb = traceback.format_exc()
        report.errors.append(f"运行错误: {exc}\n{tb[-2000:]}")
        print(f"\n✗ 出错:\n{tb[-2000:]}", flush=True)
        return 1
    finally:
        if 'tmp_dir' in locals():
            report.tmp_data_dir = str(tmp_dir)
            print(f"  ℹ tmp db 保留 (review 用): {tmp_dir}", flush=True)

        report.duration_seconds = time.perf_counter() - started
        json_path = REPORTS_DIR / f"event_line_extraction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        json_path.write_text(
            json.dumps(asdict(report), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n{'=' * 72}")
        print(f"  报告: {json_path.relative_to(ROOT)}")
        print(f"  耗时 {report.duration_seconds:.1f}s")
        print(f"{'=' * 72}\n")

    return 0 if not report.errors else 1


if __name__ == "__main__":
    sys.exit(main())
