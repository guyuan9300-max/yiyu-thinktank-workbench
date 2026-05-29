"""软件模块 DNA - 跨 session 的长期记忆.

设计原则:
- **多线程联合写作**: 多个 AI session 都能往同一个模块追加 entries, 不互相覆盖.
- **保留原话**: entry 的 content 字段不压缩, 完整保留用户澄清内容.
- **可追溯**: 每条 entry 带 source_thread / source_session / created_at, 知道来源.
- **分类**: 按 category 区分 (purpose / scope / principle / target_user 等), 同一模块可有多条同类 entries.
"""

from __future__ import annotations

import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


__all__ = [
    "ensure_schema",
    "list_modules",
    "get_module",
    "create_module",
    "update_module",
    "append_entry",
    "list_entries",
    "delete_entry",
    "load_dna_brief",
]


# --- Schema ---


def ensure_schema(db: sqlite3.Connection) -> None:
    """幂等建表; 应用启动时调一次即可."""
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS module_definitions (
            id TEXT PRIMARY KEY,
            level INTEGER NOT NULL,
            parent_id TEXT,
            display_name TEXT NOT NULL,
            summary TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS module_definition_entries (
            id TEXT PRIMARY KEY,
            module_id TEXT NOT NULL,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            is_user_quote INTEGER NOT NULL DEFAULT 0,
            source_thread TEXT NOT NULL DEFAULT '',
            source_session TEXT NOT NULL DEFAULT '',
            confidence REAL NOT NULL DEFAULT 0.7,
            tags_json TEXT NOT NULL DEFAULT '[]',
            superseded_by TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(module_id) REFERENCES module_definitions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_module_entries_module
            ON module_definition_entries(module_id, category, created_at DESC);
        """
    )
    db.commit()


# --- 模块定义 (壳) CRUD ---


def list_modules(db: sqlite3.Connection) -> list[dict[str, Any]]:
    """列出所有模块, 按 level 升序 + name."""
    rows = db.execute(
        """
        SELECT id, level, parent_id, display_name, summary, created_at, updated_at
        FROM module_definitions
        ORDER BY level ASC, display_name ASC
        """
    ).fetchall()
    return [_module_row_to_dict(r) for r in rows]


def get_module(db: sqlite3.Connection, module_id: str) -> dict[str, Any] | None:
    row = db.execute(
        """
        SELECT id, level, parent_id, display_name, summary, created_at, updated_at
        FROM module_definitions
        WHERE id = ?
        """,
        (module_id,),
    ).fetchone()
    if row is None:
        return None
    return _module_row_to_dict(row)


def create_module(
    db: sqlite3.Connection,
    *,
    module_id: str,
    level: int,
    display_name: str,
    summary: str = "",
    parent_id: str | None = None,
) -> dict[str, Any]:
    now = _now_iso()
    db.execute(
        """
        INSERT OR IGNORE INTO module_definitions
            (id, level, parent_id, display_name, summary, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (module_id, level, parent_id, display_name, summary, now, now),
    )
    db.commit()
    result = get_module(db, module_id)
    assert result is not None
    return result


def update_module(
    db: sqlite3.Connection,
    module_id: str,
    *,
    display_name: str | None = None,
    summary: str | None = None,
) -> dict[str, Any] | None:
    existing = get_module(db, module_id)
    if existing is None:
        return None
    now = _now_iso()
    db.execute(
        """
        UPDATE module_definitions
        SET display_name = COALESCE(?, display_name),
            summary = COALESCE(?, summary),
            updated_at = ?
        WHERE id = ?
        """,
        (display_name, summary, now, module_id),
    )
    db.commit()
    return get_module(db, module_id)


# --- Entries 追加 / 列出 ---


def append_entry(
    db: sqlite3.Connection,
    module_id: str,
    *,
    category: str,
    content: str,
    is_user_quote: bool = False,
    source_thread: str = "",
    source_session: str = "",
    confidence: float = 0.7,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """追加一条 entry. 不覆盖任何已有内容.

    category 推荐值:
        - purpose          : 模块解决什么问题 / 北极星
        - scope            : 边界 (做什么 / 不做什么)
        - target_user      : 谁用 (CEO / 部门领导 / 普通员工)
        - expected_value   : 用户能感受到的价值
        - interaction      : 跟哪些其他模块协同
        - principle        : 设计原则 / 哲学
        - reverse_design   : 反模式 (不做什么)
        - workflow         : 工作流 / 数据流
        - open_question    : 待澄清的问题
        - decision         : 做出的设计决策
        - history          : 历史背景 / 演化
        - example          : 真实案例引用
        - free_note        : 自由备注

    is_user_quote: True 表示这是用户原话引用 (权威性最高, 不要轻易覆盖).
    """
    if not module_id or not category or not content:
        raise ValueError("module_id / category / content 都不可为空")

    import json

    entry_id = f"entry_{uuid.uuid4().hex[:12]}"
    now = _now_iso()
    tags_json = json.dumps(tags or [], ensure_ascii=False)

    db.execute(
        """
        INSERT INTO module_definition_entries
            (id, module_id, category, content, is_user_quote, source_thread,
             source_session, confidence, tags_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (entry_id, module_id, category, content, 1 if is_user_quote else 0,
         source_thread, source_session, confidence, tags_json, now),
    )
    # 触发 module 更新时间
    db.execute(
        "UPDATE module_definitions SET updated_at = ? WHERE id = ?",
        (now, module_id),
    )
    db.commit()
    return _entry_row_to_dict(db.execute(
        """
        SELECT id, module_id, category, content, is_user_quote, source_thread,
               source_session, confidence, tags_json, superseded_by, created_at
        FROM module_definition_entries
        WHERE id = ?
        """,
        (entry_id,),
    ).fetchone())


def list_entries(
    db: sqlite3.Connection,
    module_id: str,
    *,
    category: str | None = None,
    include_superseded: bool = False,
) -> list[dict[str, Any]]:
    where_parts = ["module_id = ?"]
    params: list[Any] = [module_id]
    if category:
        where_parts.append("category = ?")
        params.append(category)
    if not include_superseded:
        where_parts.append("superseded_by IS NULL")
    where = " AND ".join(where_parts)
    rows = db.execute(
        f"""
        SELECT id, module_id, category, content, is_user_quote, source_thread,
               source_session, confidence, tags_json, superseded_by, created_at
        FROM module_definition_entries
        WHERE {where}
        ORDER BY is_user_quote DESC, created_at DESC
        """,
        tuple(params),
    ).fetchall()
    return [_entry_row_to_dict(r) for r in rows]


def delete_entry(db: sqlite3.Connection, entry_id: str) -> bool:
    cur = db.execute(
        "DELETE FROM module_definition_entries WHERE id = ?",
        (entry_id,),
    )
    db.commit()
    return cur.rowcount > 0


# --- 浏览/检索 ---


def load_dna_brief(db: sqlite3.Connection) -> dict[str, Any]:
    """给 AI 启动 task 时一次性拉的完整 DNA 摘要.

    返回结构:
        {
            "modules": [
                {
                    "id": "...", "level": 1, "displayName": "...",
                    "parentId": "...", "summary": "...",
                    "entries": [{"category": "...", "content": "...", ...}, ...]
                }, ...
            ],
            "generatedAt": "..."
        }
    """
    modules = list_modules(db)
    for m in modules:
        m["entries"] = list_entries(db, m["id"])
    return {
        "modules": modules,
        "generatedAt": _now_iso(),
    }


# --- helpers ---


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _module_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "level": int(row["level"]),
        "parentId": row["parent_id"],
        "displayName": row["display_name"],
        "summary": row["summary"] or "",
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _entry_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    import json
    try:
        tags = json.loads(row["tags_json"] or "[]")
    except json.JSONDecodeError:
        tags = []
    return {
        "id": row["id"],
        "moduleId": row["module_id"],
        "category": row["category"],
        "content": row["content"],
        "isUserQuote": bool(row["is_user_quote"]),
        "sourceThread": row["source_thread"] or "",
        "sourceSession": row["source_session"] or "",
        "confidence": float(row["confidence"]),
        "tags": tags if isinstance(tags, list) else [],
        "supersededBy": row["superseded_by"],
        "createdAt": row["created_at"],
    }
