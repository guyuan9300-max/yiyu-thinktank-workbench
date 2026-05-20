"""W3 验证 · services 层切线到 Repository

跑法:
    backend/.venv/bin/python3 -m pytest tests/test_w3_services_migration.py -v

设计:
- Repository 新方法单测(GlossaryRepository × 4 / CommitmentRepository × 3)
- ConnAdapter 兼容:raw sqlite3.Connection 也能用 Repository
- 切线后的 services 函数行为等价(glossary_store + todo_aggregator + clarification + narrative)
- 边界:空 client_id / 不存在 / 重复 / frozen 客户
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.db import Database  # noqa: E402
from app.modules.commitment import (  # noqa: E402
    Commitment,
    CommitmentRepository,
    get_commitment_repository,
)
from app.modules.glossary import (  # noqa: E402
    GlossaryRepository,
    GlossaryTerm,
    get_glossary_repository,
)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "app.db")
    db.conn.execute("PRAGMA foreign_keys=OFF")
    return db


@pytest.fixture
def db_seeded(db: Database) -> Database:
    """1 active client + 3 commitments (含 cancelled / fulfilled / pending) + 2 glossary terms"""
    now = "2026-05-20T10:00:00"
    db.conn.execute(
        """INSERT INTO clients(id, name, alias, domain, type, intro, stage, color,
                               created_at, updated_at, frozen_at)
           VALUES('c1', '某客户', '', '项目', '项目', '', '', '#5B7BFE', ?, ?, NULL)""",
        (now, now),
    )
    db.conn.executemany(
        """INSERT INTO commitments(id, client_id, committer, recipient, commitment_type,
                                   content, deadline, status, created_at, updated_at)
           VALUES(?, 'c1', ?, ?, 'delivery', ?, ?, ?, ?, ?)""",
        [
            ("cm_p1", "顾源源", "客户", "交方案 v1", "2026-06-01", "pending", now, now),
            ("cm_p2", "乐乐", "客户", "回信件",   "2026-05-25", "pending", now, now),
            ("cm_f1", "顾源源", "客户", "送资料",  "2026-05-10", "fulfilled", now, now),
            ("cm_c1", "顾源源", "客户", "已撤回",  "2026-05-30", "cancelled", now, now),
        ],
    )
    db.conn.executemany(
        """INSERT INTO client_glossary(id, client_id, term, normalized_term,
                                       definition, aliases_json, category,
                                       created_at, updated_at, evidence_tier)
           VALUES(?, 'c1', ?, ?, ?, ?, '', ?, ?, 'first_party')""",
        [
            ("gt_1", "战略陪伴", "战略陪伴", "全年陪伴", '["陪跑","顾问"]', now, now),
            ("gt_2", "心盛计划", "心盛计划", "员工心理", "[]", now, now),
        ],
    )
    db.conn.commit()
    return db


# ═══════════════════════════════════════════════════════════════════════
# GlossaryRepository · 新增 CRUD 方法
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.integration
def test_glossary_list_paginated_returns_total(db_seeded: Database):
    repo = get_glossary_repository(db_seeded)
    terms, total = repo.list_terms_paginated("c1", limit=10)
    assert total == 2
    assert len(terms) == 2
    assert {t.term for t in terms} == {"战略陪伴", "心盛计划"}


@pytest.mark.integration
def test_glossary_list_paginated_with_query(db_seeded: Database):
    repo = get_glossary_repository(db_seeded)
    terms, total = repo.list_terms_paginated("c1", query="陪伴")
    assert total == 1
    assert terms[0].term == "战略陪伴"


@pytest.mark.integration
def test_glossary_list_paginated_query_matches_aliases(db_seeded: Database):
    """query 应该匹配 aliases_json('陪跑'/'顾问')"""
    repo = get_glossary_repository(db_seeded)
    terms, total = repo.list_terms_paginated("c1", query="陪跑")
    assert total == 1
    assert terms[0].term == "战略陪伴"


@pytest.mark.integration
def test_glossary_list_paginated_offset_limit(db_seeded: Database):
    repo = get_glossary_repository(db_seeded)
    page1, _ = repo.list_terms_paginated("c1", limit=1, offset=0)
    page2, _ = repo.list_terms_paginated("c1", limit=1, offset=1)
    assert len(page1) == 1
    assert len(page2) == 1
    assert page1[0].id != page2[0].id


@pytest.mark.integration
def test_glossary_list_paginated_empty_client(db: Database):
    repo = get_glossary_repository(db)
    terms, total = repo.list_terms_paginated("")
    assert terms == []
    assert total == 0


@pytest.mark.integration
def test_glossary_create_term(db_seeded: Database):
    repo = get_glossary_repository(db_seeded)
    db_seeded.conn.commit()  # ensure clean state
    created = repo.create_term(
        client_id="c1", term="DNA 工具", definition="组织 DNA 量表", aliases=["DNA"],
    )
    assert created.term == "DNA 工具"
    assert created.client_id == "c1"
    assert created.normalized_term == "dna 工具"  # 归一化
    # 再读
    again = repo.get_term_by_id(created.id)
    assert again is not None
    assert again.term == "DNA 工具"
    assert list(again.aliases) == ["DNA"]


@pytest.mark.integration
def test_glossary_create_term_empty_term_raises(db: Database):
    repo = get_glossary_repository(db)
    with pytest.raises(ValueError, match="term 不能为空"):
        repo.create_term(client_id="c1", term="  ")
    with pytest.raises(ValueError, match="term 不能为空"):
        repo.create_term(client_id="c1", term="")


@pytest.mark.integration
def test_glossary_create_term_empty_client_raises(db: Database):
    repo = get_glossary_repository(db)
    with pytest.raises(ValueError, match="client_id 不能为空"):
        repo.create_term(client_id="", term="X")


@pytest.mark.integration
def test_glossary_update_term_partial(db_seeded: Database):
    repo = get_glossary_repository(db_seeded)
    updated = repo.update_term("gt_1", definition="改后的定义")
    assert updated.definition == "改后的定义"
    assert updated.term == "战略陪伴"  # 未改的字段保留
    assert list(updated.aliases) == ["陪跑", "顾问"]


@pytest.mark.integration
def test_glossary_update_term_changes_normalized(db_seeded: Database):
    repo = get_glossary_repository(db_seeded)
    updated = repo.update_term("gt_1", term="New Term")
    assert updated.term == "New Term"
    assert updated.normalized_term == "new term"


@pytest.mark.integration
def test_glossary_update_term_not_found_raises(db: Database):
    repo = get_glossary_repository(db)
    with pytest.raises(ValueError, match="not found"):
        repo.update_term("ghost", term="X")


@pytest.mark.integration
def test_glossary_delete_term(db_seeded: Database):
    repo = get_glossary_repository(db_seeded)
    assert repo.delete_term("gt_2") is True
    assert repo.get_term_by_id("gt_2") is None


@pytest.mark.integration
def test_glossary_delete_term_nonexistent(db: Database):
    repo = get_glossary_repository(db)
    assert repo.delete_term("ghost") is False
    assert repo.delete_term("") is False


# ═══════════════════════════════════════════════════════════════════════
# CommitmentRepository · 新增 service-shape 方法
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.integration
def test_commitment_list_pending_only(db_seeded: Database):
    """list_pending_for_client 严格只返回 status='pending'"""
    repo = get_commitment_repository(db_seeded)
    pending = repo.list_pending_for_client("c1")
    assert len(pending) == 2
    assert {c.id for c in pending} == {"cm_p1", "cm_p2"}
    assert all(c.status == "pending" for c in pending)


@pytest.mark.integration
def test_commitment_list_pending_empty_client(db: Database):
    repo = get_commitment_repository(db)
    assert repo.list_pending_for_client("") == []


@pytest.mark.integration
def test_commitment_list_status_grouped_full(db_seeded: Database):
    """list_for_client_status_grouped 返回客户全部承诺 (含 cancelled),按 status 分组"""
    repo = get_commitment_repository(db_seeded)
    all_c = repo.list_for_client_status_grouped("c1")
    assert len(all_c) == 4
    # pending 必须排在 fulfilled 前,fulfilled 排在 cancelled 前
    statuses = [c.status for c in all_c]
    pending_idx = [i for i, s in enumerate(statuses) if s == "pending"]
    fulfilled_idx = [i for i, s in enumerate(statuses) if s == "fulfilled"]
    cancelled_idx = [i for i, s in enumerate(statuses) if s == "cancelled"]
    assert all(p < f for p in pending_idx for f in fulfilled_idx)
    assert all(f < c for f in fulfilled_idx for c in cancelled_idx)


@pytest.mark.integration
def test_commitment_list_active_excludes_cancelled(db_seeded: Database):
    """list_active_for_client 排除 cancelled"""
    repo = get_commitment_repository(db_seeded)
    active = repo.list_active_for_client("c1")
    assert len(active) == 3
    assert all(c.status != "cancelled" for c in active)


# ═══════════════════════════════════════════════════════════════════════
# ConnAdapter · raw sqlite3.Connection 兼容
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.integration
def test_glossary_repository_accepts_raw_connection(db_seeded: Database):
    """legacy services 传 conn 直接进 Repository,不应崩"""
    repo = GlossaryRepository(db_seeded.conn)  # 直接传 sqlite3.Connection
    terms = repo.list_terms_for_client("c1")
    assert len(terms) == 2


@pytest.mark.integration
def test_commitment_repository_accepts_raw_connection(db_seeded: Database):
    repo = CommitmentRepository(db_seeded.conn)
    pending = repo.list_pending_for_client("c1")
    assert len(pending) == 2


# ═══════════════════════════════════════════════════════════════════════
# Legacy services 切线后等价 (glossary_store)
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.integration
def test_legacy_glossary_store_list_glossary(db_seeded: Database):
    """glossary_store.list_glossary 走 Repository,返回 GlossaryEntry"""
    from app.services.glossary_store import GlossaryEntry, list_glossary

    entries, total = list_glossary(db_seeded.conn, client_id="c1")
    assert total == 2
    assert all(isinstance(e, GlossaryEntry) for e in entries)
    # legacy 类型保持 list[str]
    assert all(isinstance(e.aliases, list) for e in entries)


@pytest.mark.integration
def test_legacy_glossary_store_create_then_get(db: Database):
    """完整 CRUD legacy 路径不崩"""
    from app.services.glossary_store import (
        create_glossary_entry,
        delete_glossary_entry,
        get_glossary_entry,
        update_glossary_entry,
    )

    now = "2026-05-20T10:00:00"
    db.conn.execute(
        """INSERT INTO clients(id, name, alias, domain, type, intro, stage, color,
                               created_at, updated_at, frozen_at)
           VALUES('c1', 'X', '', 'p', 'p', '', '', '#fff', ?, ?, NULL)""",
        (now, now),
    )
    db.conn.commit()

    e = create_glossary_entry(
        db.conn, client_id="c1", term="测试术语", definition="def", aliases=["a", "b"],
    )
    assert e.term == "测试术语"
    assert e.aliases == ["a", "b"]

    e2 = get_glossary_entry(db.conn, entry_id=e.id)
    assert e2.id == e.id

    e3 = update_glossary_entry(db.conn, entry_id=e.id, definition="new def")
    assert e3.definition == "new def"

    assert delete_glossary_entry(db.conn, entry_id=e.id) is True
    assert delete_glossary_entry(db.conn, entry_id=e.id) is False  # 二次删除


@pytest.mark.integration
def test_legacy_glossary_store_get_not_found_raises(db: Database):
    from app.services.glossary_store import get_glossary_entry

    with pytest.raises(ValueError, match="not found"):
        get_glossary_entry(db.conn, entry_id="ghost")


# ═══════════════════════════════════════════════════════════════════════
# Legacy services 切线后等价 (commitment 3 文件)
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.integration
def test_todo_aggregator_uses_repository(db_seeded: Database):
    """todo_aggregator 应该走 Repository,不再裸 SQL 读 commitments"""
    from app.services.todo_aggregator import collect_all_todos

    # smoke test: 真跑一次 todo_aggregator(只看 commitments 部分,不崩即过)
    todos = collect_all_todos(db_seeded, client_id="c1")
    # 应该看到 2 个 pending commitments(cm_p1 + cm_p2)
    commit_todos = [t for t in todos if t.source == "commitment"]
    assert len(commit_todos) == 2
    assert {t.raw_id for t in commit_todos} == {"cm_p1", "cm_p2"}


@pytest.mark.integration
def test_narrative_collector_uses_repository(db_seeded: Database):
    """narrative_collector._collect_commitments 应该返回 3 个(排除 cancelled)"""
    from app.services.narrative_collector import _collect_commitments

    facts = _collect_commitments(db_seeded, "c1")
    assert len(facts) == 3
    statuses = {f.status for f in facts}
    assert "cancelled" not in statuses


# ═══════════════════════════════════════════════════════════════════════
# 切线后 · services 层不再裸 SQL 在 client_glossary/commitments 表(本次切的 4 个文件)
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.unit
def test_glossary_store_no_raw_sql_after_w3():
    """glossary_store.py 切线后应该 0 处 SELECT/INSERT/UPDATE/DELETE FROM client_glossary"""
    import re

    src = (ROOT / "backend" / "app" / "services" / "glossary_store.py").read_text(encoding="utf-8")
    forbidden = re.compile(
        r"\b(SELECT|INSERT INTO|UPDATE|DELETE FROM)\b.*\bclient_glossary\b",
        re.IGNORECASE,
    )
    matches = forbidden.findall(src)
    assert matches == [], f"glossary_store.py 仍有裸 SQL 操作 client_glossary: {matches}"


@pytest.mark.unit
def test_w3_migrated_services_no_raw_commitments_sql():
    """3 个 commitment services 文件切线后:0 处操作 commitments 表的裸 SQL"""
    import re

    files = [
        ROOT / "backend" / "app" / "services" / "todo_aggregator.py",
        ROOT / "backend" / "app" / "services" / "clarification_context.py",
        ROOT / "backend" / "app" / "services" / "narrative_collector.py",
    ]
    forbidden = re.compile(
        r"\b(FROM|INTO|UPDATE|DELETE FROM)\s+commitments\b",
        re.IGNORECASE,
    )
    for f in files:
        src = f.read_text(encoding="utf-8")
        matches = forbidden.findall(src)
        assert matches == [], f"{f.name} 仍有裸 SQL 操作 commitments: {matches}"
