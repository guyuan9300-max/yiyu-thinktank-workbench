"""[A] V2.3 阶段 1 P0 · source_registry_store 单测

测:
1. ensure_schema idempotent
2. register_source 写入 + 默认 confidence
3. 4 必填强校验 raise ValueError
4. find_by_content_hash 去重
5. supersede_version 版本链
6. atomic_fact_confidence_history 写入 + trend 计算
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# V2.1 backend 优先
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


class _SimpleDb:
    """轻量 db wrapper (跟 V2.1 Database 接口同形)."""

    def __init__(self, path: str = ":memory:"):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, params)

    def fetchone(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()


def _fresh_db():
    from app.services.source_registry_store import ensure_schema as ensure_sr
    from app.services.atomic_fact_confidence_history import ensure_schema as ensure_ch

    db = _SimpleDb()
    ensure_sr(db)
    ensure_ch(db)
    return db


# ─── Tests · source_registry ───────────────────────


def test_ensure_schema_idempotent():
    """跑两次 ensure_schema 不报错 (idempotent)."""
    db = _SimpleDb()
    from app.services.source_registry_store import ensure_schema
    ensure_schema(db)
    ensure_schema(db)  # 第二次不应该报错
    # 确认表存在
    r = db.fetchone(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='source_registry'"
    )
    assert r is not None
    assert r["name"] == "source_registry"


def test_register_source_basic():
    """基本写入 + initial_confidence 自动算."""
    db = _fresh_db()
    from app.services.source_registry_store import register_source, get_source

    src_id = register_source(
        db,
        source_type="workbench_file",
        source_channel="smart_file_import",
        source_role="client_official",
        client_id="client_test",
        content="日慈基金会 法人代表 张真",
        raw_reference="v2doc_xxx",
    )

    assert src_id.startswith("src_")
    src = get_source(db, src_id)
    assert src is not None
    assert src["source_type"] == "workbench_file"
    assert src["source_channel"] == "smart_file_import"
    assert src["client_id"] == "client_test"
    # initial_confidence 算法: 0.4 * 0.90 (type) + 0.6 * 0.95 (role) = 0.93
    assert abs(src["initial_confidence"] - 0.93) < 0.01


def test_register_source_strict_4_required():
    """4 必填全空 raise ValueError."""
    db = _fresh_db()
    from app.services.source_registry_store import register_source

    import pytest
    with pytest.raises(ValueError, match="V2.3 P2 强校验"):
        register_source(
            db,
            source_type="workbench_file",
            source_channel="smart_file_import",
            content="...",
            strict_4_required=True,
            # 4 必填全空
        )


def test_register_source_strict_disabled():
    """strict_4_required=False 时允许 4 必填空(向后兼容旧数据)."""
    db = _fresh_db()
    from app.services.source_registry_store import register_source

    src_id = register_source(
        db,
        source_type="system_log",
        source_channel="ai_self_verify",
        content="...",
        strict_4_required=False,
    )
    assert src_id.startswith("src_")


def test_find_by_content_hash_dedupe():
    """同 content 二次写入应能 find_by_content_hash 找到第一条."""
    db = _fresh_db()
    from app.services.source_registry_store import register_source, find_by_content_hash, _compute_content_hash

    src_id_1 = register_source(
        db, source_type="task_review", source_channel="task_create",
        client_id="client_X", content="同样的内容",
    )

    h = _compute_content_hash("同样的内容")
    existing = find_by_content_hash(db, h, client_id="client_X")
    assert existing is not None
    assert existing["source_id"] == src_id_1


def test_supersede_version_chain():
    """版本链: 旧 → superseded, 新 → prev_version_id 指向旧."""
    db = _fresh_db()
    from app.services.source_registry_store import (
        register_source, supersede_version, get_source,
    )

    src_v1 = register_source(
        db, source_type="workbench_file", source_channel="workbench_upload",
        client_id="client_X", content="协议 0623", version_id="v1",
    )
    src_v2 = register_source(
        db, source_type="workbench_file", source_channel="workbench_upload",
        client_id="client_X", content="协议 0822", version_id="v2",
    )
    supersede_version(db, src_v1, src_v2)

    v1 = get_source(db, src_v1)
    v2 = get_source(db, src_v2)
    assert v1["status"] == "superseded"
    assert v2["prev_version_id"] == src_v1


# ─── Tests · atomic_fact_confidence_history ─────────


def test_confidence_history_record_and_trend():
    """confidence 变化记录 + trend 计算."""
    db = _fresh_db()
    from app.services.atomic_fact_confidence_history import (
        record_confidence_change, list_history_for_fact, get_current_trend,
    )

    fid = "fact_abc"
    # 初始抽取
    record_confidence_change(
        db, fact_id=fid, new_confidence=0.6, trigger_event="initial_extract",
        actor_id="ai_extractor",
    )
    # 跨源印证上升
    record_confidence_change(
        db, fact_id=fid, old_confidence=0.6, new_confidence=0.75,
        trigger_event="cross_source_confirm",
        evidence_link="src_yyy", actor_id="system",
    )
    # 用户确权
    record_confidence_change(
        db, fact_id=fid, old_confidence=0.75, new_confidence=0.95,
        trigger_event="user_confirm",
        actor_id="user_zzz",
    )

    history = list_history_for_fact(db, fid)
    assert len(history) == 3
    assert history[0]["new_confidence"] == 0.95  # 最新在前
    assert history[2]["new_confidence"] == 0.6   # 最早在后

    trend = get_current_trend(db, fid)
    assert trend == "rising"  # 0.6 → 0.75 → 0.95
