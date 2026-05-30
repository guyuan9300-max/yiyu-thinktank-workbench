"""回归测试:ensure_bot_schema 不再每次启动假报 duplicate-column noise (P0-noise)。

根因:CREATE TABLE bot_members 已含 token_hash/salt/prefix/rotated_at 列,
后面又有给旧库的 ALTER TABLE ADD COLUMN token_*。对新库 CREATE 已建列 →
ALTER 必报 "duplicate column" → 每次启动 logger.warning("ensure_bot_schema
failed for stmt: ...") 假报 failed 噪音(违背白箱/装干净仪表盘)。

修法:循环里把 "duplicate column" 当预期情况静默 continue,真失败仍 warn。
"""
from __future__ import annotations

import io
import logging
import sqlite3

from app.services.bot_members import ensure_bot_schema


class _Db:
    def __init__(self) -> None:
        self.c = sqlite3.connect(":memory:")

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self.c.execute(sql, params)


def test_ensure_bot_schema_no_duplicate_column_noise() -> None:
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setLevel(logging.WARNING)
    lg = logging.getLogger("app.services.bot_members")
    lg.addHandler(handler)
    lg.setLevel(logging.WARNING)
    try:
        db = _Db()
        ensure_bot_schema(db)  # 首次:CREATE 含 token 列,ALTER 报 duplicate(应静默)
        ensure_bot_schema(db)  # 二次:全已存在,ALTER 又 duplicate(应静默)
        logs = buf.getvalue()
        assert "duplicate column" not in logs
        assert "ensure_bot_schema failed" not in logs
        # schema 仍正确建好
        cols = [r[1] for r in db.c.execute("PRAGMA table_info(bot_members)")]
        assert "token_hash" in cols
        assert "token_rotated_at" in cols
    finally:
        lg.removeHandler(handler)
