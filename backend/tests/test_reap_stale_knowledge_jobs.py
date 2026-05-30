"""回归测试:_reap_stale_knowledge_jobs SQL 绑定参数修复(P0-C2)。

根因:原 SQL 把 `?` 写进字符串字面量 ' ... > ? min',它不是绑定占位符,
导致真实占位符 3 个却传 4 个参数 → sqlite3 抛 "uses 3, but 4 supplied",
reap 永远失败(被双层 try/except 吞掉),卡死的 running 作业永远清不掉、
工作台进度条永远转。

修复:把 `?` 移出字符串字面量用 || 拼接,使其成为第 4 个真占位符。
本测试证明:① 不再抛异常;② stale running 作业被正确标 failed;
③ 新鲜作业与非 running 作业不受影响;④ 阈值分钟数正确写入 last_error。
"""
from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from app.services.smart_file_import import _reap_stale_knowledge_jobs


class _DbLike:
    """最小 db 适配器:复刻函数所需的 execute / conn 接口。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, params)


@pytest.fixture()
def db() -> _DbLike:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """CREATE TABLE knowledge_jobs (
            id TEXT PRIMARY KEY,
            status TEXT,
            last_error TEXT,
            started_at TEXT,
            updated_at TEXT,
            finished_at TEXT,
            created_at TEXT
        )"""
    )
    # A: stale running(2020 年,远早于 30 分钟前)→ 应被 reap
    conn.execute(
        "INSERT INTO knowledge_jobs(id,status,updated_at,created_at) VALUES('A','running','2020-01-01T00:00:00','2020-01-01T00:00:00')"
    )
    # B: 新鲜 running(刚刚,sqlite datetime('now') 同格式)→ 不应动
    conn.execute(
        "INSERT INTO knowledge_jobs(id,status,updated_at,created_at) VALUES('B','running',datetime('now'),datetime('now'))"
    )
    # C: 老的 completed → 不是 running,不应动
    conn.execute(
        "INSERT INTO knowledge_jobs(id,status,updated_at,created_at) VALUES('C','completed','2020-01-01T00:00:00','2020-01-01T00:00:00')"
    )
    conn.commit()
    return _DbLike(conn)


def _status(db: _DbLike, job_id: str) -> tuple[Any, Any]:
    row = db.conn.execute(
        "SELECT status, last_error FROM knowledge_jobs WHERE id=?", (job_id,)
    ).fetchone()
    return row[0], row[1]


def test_reaps_only_stale_running_jobs(db: _DbLike) -> None:
    reaped = _reap_stale_knowledge_jobs(db, max_running_minutes=30)

    # ① 恰好 reap 1 条(若 SQL 仍报绑定错,会被吞 → 返回 0,这里就会失败)
    assert reaped == 1

    # ② stale running → failed,且阈值分钟数正确写入消息
    status_a, last_error_a = _status(db, "A")
    assert status_a == "failed"
    assert "auto-reaped: stale running > 30 min" in (last_error_a or "")

    # ③ 新鲜 running 不受影响
    assert _status(db, "B")[0] == "running"

    # ④ 非 running 不受影响
    assert _status(db, "C")[0] == "completed"


def test_reap_does_not_raise_on_empty(db: _DbLike) -> None:
    # 先全部清掉 running,再跑一次,确认无异常且返回 0
    db.conn.execute("UPDATE knowledge_jobs SET status='done' WHERE status='running'")
    db.conn.commit()
    assert _reap_stale_knowledge_jobs(db, max_running_minutes=30) == 0
