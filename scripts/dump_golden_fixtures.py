"""
Dump golden fixtures · v2.1 重构 baseline 快照

在 v1.0 main 分支上跑一次,产出 3 个客户的关键数据快照。
v2.1 重构后必须能 95%+ 复现这些 JSON,否则迁移视为失败。

使用:
    python scripts/dump_golden_fixtures.py
    # 输出到 tests/fixtures/golden/{client_name}.json

设计原则:
- 排除时间戳字段(避免重跑产生 diff)
- 排除 LLM 生成内容(prompt/output 漂移属正常)
- 只保留"业务事实"层:event_lines / commitments / glossary / entities / tasks
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

# 让 backend 模块可 import
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.db import Database  # noqa: E402
from app.services.narrative_collector import collect_client_fact_bundle  # noqa: E402
from app.services.todo_aggregator import collect_all_todos  # noqa: E402


# 3 个 golden 客户(数据库 ID 跟界面名)
GOLDEN_CLIENTS = [
    ("client_284afd836e", "日慈基金会"),
    ("client_85d5c52575", "为爱黔行"),
    ("client_a4d1db29a7", "CFFC"),
]

# 时间戳字段:dump 时统一删掉,避免重跑产生 diff
TIMESTAMP_FIELDS = {
    "created_at", "updated_at", "imported_at", "last_synced_at",
    "verified_at", "fulfilled_at", "first_seen_at", "last_seen_at",
    "deleted_at", "modified_at", "completed_at", "decided_at",
    "captured_at", "indexed_at", "processed_at", "generated_at",
}


def _scrub(value: Any) -> Any:
    """递归清掉时间戳字段 + 把 dataclass/Path 转 JSON-friendly"""
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items() if k not in TIMESTAMP_FIELDS}
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "isoformat"):  # datetime / date
        return None  # 直接丢弃,不保留
    return value


def _safe_filename(name: str) -> str:
    """中文客户名 → 文件名安全字符"""
    return re.sub(r"[^\w一-鿿\-]+", "_", name)


def _dump_entity_table(db: Database, client_id: str) -> list[dict]:
    """直接 SQL 查 entities 表(业务事实,不走 narrative_collector)"""
    rows = db.fetchall(
        """
        SELECT id, display_name, entity_type, aliases_json, mention_count
        FROM entities
        WHERE client_id = ?
        ORDER BY mention_count DESC, display_name ASC
        """,
        (client_id,),
    )
    return [
        {
            "id": str(r["id"]),
            "display_name": str(r["display_name"] or ""),
            "entity_type": str(r["entity_type"] or ""),
            "aliases": str(r["aliases_json"] or "[]"),
            "mention_count": int(r["mention_count"] or 0),
        }
        for r in rows
    ]


def _dump_glossary(db: Database, client_id: str) -> list[dict]:
    """字典属性(verified 的算 baseline)— join client_glossary 取 term 名"""
    rows = db.fetchall(
        """
        SELECT ga.id, ga.term_id, cg.term, ga.attribute_name,
               ga.value_text, ga.value_unit, ga.scope,
               ga.confidence, ga.verification_status
        FROM glossary_attributes ga
        LEFT JOIN client_glossary cg ON cg.id = ga.term_id
        WHERE ga.client_id = ?
        ORDER BY cg.term, ga.attribute_name
        """,
        (client_id,),
    )
    return [
        {
            "id": str(r["id"]),
            "term": str(r["term"] or ""),
            "attribute_name": str(r["attribute_name"] or ""),
            "value_text": str(r["value_text"] or ""),
            "value_unit": str(r["value_unit"] or ""),
            "scope": str(r["scope"] or ""),
            "confidence": float(r["confidence"] or 0),
            "verification_status": str(r["verification_status"] or ""),
        }
        for r in rows
    ]


def _dump_commitments(db: Database, client_id: str) -> list[dict]:
    """承诺(commitments)"""
    rows = db.fetchall(
        """
        SELECT id, committer, recipient, commitment_type, content, deadline, status
        FROM commitments
        WHERE client_id = ?
        ORDER BY deadline NULLS LAST, committer
        """,
        (client_id,),
    )
    return [
        {
            "id": str(r["id"]),
            "committer": str(r["committer"] or ""),
            "recipient": str(r["recipient"] or ""),
            "commitment_type": str(r["commitment_type"] or ""),
            "content": str(r["content"] or ""),
            "deadline": str(r["deadline"] or ""),
            "status": str(r["status"] or ""),
        }
        for r in rows
    ]


def _dump_event_lines(db: Database, client_id: str) -> list[dict]:
    """事件线(business 字段,排除 sync 元数据)"""
    rows = db.fetchall(
        """
        SELECT id, name, kind, status, stage, summary, intent,
               current_blocker, recent_decision, next_step,
               evidence_count, primary_client_name
        FROM event_lines
        WHERE primary_client_id = ?
        ORDER BY status, updated_at DESC
        """,
        (client_id,),
    )
    return [
        {
            "id": str(r["id"]),
            "name": str(r["name"] or ""),
            "kind": str(r["kind"] or ""),
            "status": str(r["status"] or ""),
            "stage": str(r["stage"] or ""),
            "summary": str(r["summary"] or ""),
            "intent": str(r["intent"] or ""),
            "current_blocker": str(r["current_blocker"] or ""),
            "recent_decision": str(r["recent_decision"] or ""),
            "next_step": str(r["next_step"] or ""),
            "evidence_count": int(r["evidence_count"] or 0),
            "primary_client_name": str(r["primary_client_name"] or ""),
        }
        for r in rows
    ]


def _dump_tasks_via_event_lines(db: Database, client_id: str) -> list[dict]:
    """task 通过 client_id 或 event_line_id 双路径关联"""
    rows = db.fetchall(
        """
        SELECT DISTINCT t.id, t.title, t.status, t.priority, t.ddl,
               t.event_line_id, t.owner_name
        FROM tasks t
        WHERE t.client_id = ?
           OR t.event_line_id IN (
                SELECT id FROM event_lines WHERE primary_client_id = ?
           )
        ORDER BY t.status, t.priority DESC
        """,
        (client_id, client_id),
    )
    return [
        {
            "id": str(r["id"]),
            "title": str(r["title"] or ""),
            "status": str(r["status"] or ""),
            "priority": str(r["priority"] or ""),
            "ddl": str(r["ddl"] or ""),
            "event_line_id": str(r["event_line_id"] or ""),
            "owner_name": str(r["owner_name"] or ""),
        }
        for r in rows
    ]


def dump_one_client(db: Database, client_id: str, client_name: str) -> dict:
    """收集一个客户的完整快照"""
    # 高层:复用现有 collector(包含 entity 关联 / atomic facts 等)
    try:
        bundle = collect_client_fact_bundle(db, client_id)
        bundle_dict = _scrub(bundle)
    except Exception as exc:
        bundle_dict = {"error": f"collect_client_fact_bundle failed: {exc!r}"}

    try:
        todos = collect_all_todos(db, client_id)
        todos_dict = [_scrub(t) for t in todos]
    except Exception as exc:
        todos_dict = [{"error": f"collect_all_todos failed: {exc!r}"}]

    return {
        "client_id": client_id,
        "client_name": client_name,
        "schema_version": "v1.0-baseline",
        # 高层视图(给 narrative / qa 用)
        "fact_bundle": bundle_dict,
        "unified_todos": todos_dict,
        # 原始业务事实(给 diff 用)
        "raw": {
            "event_lines": _dump_event_lines(db, client_id),
            "entities": _dump_entity_table(db, client_id),
            "glossary_attributes": _dump_glossary(db, client_id),
            "commitments": _dump_commitments(db, client_id),
            "tasks": _dump_tasks_via_event_lines(db, client_id),
        },
    }


def main() -> int:
    data_dir = os.environ.get(
        "YIYU_WORKBENCH_DATA_DIR",
        os.path.expanduser("~/Library/Application Support/YiyuThinkTankWorkbench2"),
    )
    db_path = Path(data_dir) / "app.db"
    if not db_path.exists():
        print(f"❌ database not found: {db_path}", file=sys.stderr)
        return 1

    db = Database(db_path)

    out_dir = ROOT / "tests" / "fixtures" / "golden"
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = []
    for client_id, client_name in GOLDEN_CLIENTS:
        print(f"→ dumping {client_name} ({client_id})...")
        try:
            snapshot = dump_one_client(db, client_id, client_name)
        except Exception as exc:
            print(f"  ❌ failed: {exc!r}")
            summary.append({"client": client_name, "status": "failed", "error": str(exc)})
            continue

        out_path = out_dir / f"{_safe_filename(client_name)}.json"
        out_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        size_kb = out_path.stat().st_size / 1024
        raw = snapshot["raw"]
        print(
            f"  ✓ {out_path.name} ({size_kb:.1f} KB) — "
            f"{len(raw['event_lines'])} events / "
            f"{len(raw['entities'])} entities / "
            f"{len(raw['glossary_attributes'])} attrs / "
            f"{len(raw['commitments'])} commits / "
            f"{len(raw['tasks'])} tasks"
        )
        summary.append({
            "client": client_name,
            "status": "ok",
            "path": str(out_path),
            "size_kb": round(size_kb, 1),
        })

    print()
    print("=" * 60)
    print("Golden fixtures dump 完成。这是 v2.1 重构的 baseline。")
    print("v2.1 重构后,这些 JSON 必须能被复现(95%+ 字段相同)。")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
