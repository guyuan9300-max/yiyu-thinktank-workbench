"""W2-C 验证 · 7 个业务模块骨架

跑法:
    backend/.venv/bin/python3 -m pytest tests/test_w2_business_modules.py -v

设计:
- 7 个模块都能 import,有 __all__ 暴露 Repository
- 完整模块(commitment / glossary)测核心方法
- 占位模块(client / task / knowledge / intelligence / narrative)测最小可用接口
- 所有 Repository 通过 SQL view / 业务表能查 → SSOT 通路完整
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.db import Database  # noqa: E402

# 7 个模块
from app.modules.client import ClientRepository, get_client_repository  # noqa: E402
from app.modules.commitment import (  # noqa: E402
    Commitment, CommitmentRepository, get_commitment_repository,
)
from app.modules.glossary import (  # noqa: E402
    GlossaryAttribute, GlossaryRepository, GlossaryTerm, get_glossary_repository,
)
from app.modules.intelligence import (  # noqa: E402
    IntelligenceRepository, get_intelligence_repository,
)
from app.modules.knowledge import KnowledgeRepository, get_knowledge_repository  # noqa: E402
from app.modules.narrative import NarrativeRepository, get_narrative_repository  # noqa: E402
from app.modules.task import TaskRepository, get_task_repository  # noqa: E402


# ── Fixture ──


@pytest.fixture
def db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "app.db")
    db.conn.execute("PRAGMA foreign_keys=OFF")
    return db


@pytest.fixture
def db_with_data(db: Database) -> Database:
    now = "2026-05-20T10:00:00"
    # 1 active client + 1 frozen
    db.conn.executemany(
        """INSERT INTO clients(id, name, alias, domain, type, intro, stage, color,
                               created_at, updated_at, frozen_at)
           VALUES(?, ?, '', '项目', '项目', '', '', '#5B7BFE', ?, ?, ?)""",
        [
            ("c_active", "活客户", now, now, None),
            ("c_frozen", "冻客户", now, now, "2026-05-19"),
        ],
    )
    # 1 active event
    db.conn.execute(
        """INSERT INTO event_lines(id, name, kind, status, primary_client_id,
                                   created_at, updated_at)
           VALUES('el_1', 'E1', 'custom', 'active', 'c_active', ?, ?)""",
        (now, now),
    )
    # task_list + 1 todo task
    db.conn.execute(
        """INSERT INTO task_lists(id, organization_id, name, color, sort_order, is_default, scope)
           VALUES('list_d', '', 'def', '#fff', 0, 1, 'org')"""
    )
    db.conn.execute(
        """INSERT INTO tasks(id, title, description, status, priority, list_id,
                             owner_name, ddl, source_type, tags_json,
                             created_at, updated_at, client_id)
           VALUES('t_1', 'T1', '', 'todo', 'high', 'list_d', '', '',
                  'manual', '[]', ?, ?, 'c_active')""",
        (now, now),
    )
    # 2 commitments
    db.conn.executemany(
        """INSERT INTO commitments(id, client_id, committer, recipient, commitment_type,
                                   content, deadline, status, created_at, updated_at)
           VALUES(?, ?, ?, ?, 'delivery', ?, ?, ?, ?, ?)""",
        [
            ("cm_1", "c_active", "顾源源", "客户", "交方案", "2026-05-25", "pending", now, now),
            ("cm_2", "c_active", "乐乐", "客户", "回邮件", "2026-05-15", "pending", now, now),  # 过期
        ],
    )
    # 1 glossary term + 2 attributes
    db.conn.execute(
        """INSERT INTO client_glossary(id, client_id, term, normalized_term,
                                       definition, aliases_json, category,
                                       created_at, updated_at, evidence_tier)
           VALUES('gt_1', 'c_active', '战略陪伴', '战略陪伴', '', '[]', '',
                  ?, ?, 'first_party')""",
        (now, now),
    )
    db.conn.executemany(
        """INSERT INTO glossary_attributes(id, client_id, term_id, attribute_name,
                                           value_text, verification_status,
                                           created_at, updated_at)
           VALUES(?, 'c_active', 'gt_1', ?, ?, ?, ?, ?)""",
        [
            ("ga_1", "周期", "12 个月", "verified", now, now),
            ("ga_2", "频率", "每月 1 次", "pending", now, now),
        ],
    )
    # 1 knowledge
    db.conn.execute(
        """INSERT INTO knowledge_master_index(id, client_id, surrogate_id, title,
                                              folder_category, document_role,
                                              retrieval_summary, searchable_text,
                                              surrogate_md_path, updated_at)
           VALUES('k_1', 'c_active', 'sg_1', '文档', '', '', '摘要', '文本',
                  '', ?)""",
        (now,),
    )
    db.conn.commit()
    return db


# ═══════════════════════════════════════════════════════════════════════════
# 7 个模块的 import 都能成
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.unit
@pytest.mark.parametrize("repo_factory", [
    get_client_repository,
    get_commitment_repository,
    get_glossary_repository,
    get_intelligence_repository,
    get_knowledge_repository,
    get_narrative_repository,
    get_task_repository,
])
def test_repository_factory_callable(repo_factory, db: Database):
    """每个模块的 factory 都能调出一个 Repository 实例"""
    repo = repo_factory(db)
    assert repo is not None


# ═══════════════════════════════════════════════════════════════════════════
# 完整模块:commitment
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
def test_commitment_list_for_client_only_open(db_with_data: Database):
    repo = get_commitment_repository(db_with_data)
    items = repo.list_for_client("c_active", only_open=True)
    assert len(items) == 2
    assert all(isinstance(c, Commitment) for c in items)


@pytest.mark.integration
def test_commitment_list_overdue(db_with_data: Database):
    """deadline < now 的承诺"""
    repo = get_commitment_repository(db_with_data)
    overdue = repo.list_overdue(now_iso="2026-05-20T00:00:00", client_id="c_active")
    # cm_2 deadline 是 2026-05-15,应被算 overdue
    assert len(overdue) == 1
    assert overdue[0].id == "cm_2"


@pytest.mark.integration
def test_commitment_list_for_committer(db_with_data: Database):
    repo = get_commitment_repository(db_with_data)
    guyuan_owes = repo.list_for_committer("顾源源")
    assert len(guyuan_owes) == 1
    assert guyuan_owes[0].content == "交方案"


@pytest.mark.integration
def test_commitment_mark_fulfilled(db_with_data: Database):
    repo = get_commitment_repository(db_with_data)
    ok = repo.mark_fulfilled("cm_1", fulfilled_at="2026-05-21", updated_at="2026-05-21")
    assert ok is True
    item = repo.get_by_id("cm_1")
    assert item.status == "fulfilled"
    assert item.fulfilled_at == "2026-05-21"


@pytest.mark.integration
def test_commitment_get_nonexistent_returns_none(db: Database):
    repo = get_commitment_repository(db)
    assert repo.get_by_id("ghost") is None
    assert repo.get_by_id("") is None


# ═══════════════════════════════════════════════════════════════════════════
# 完整模块:glossary
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
def test_glossary_list_terms_for_client(db_with_data: Database):
    repo = get_glossary_repository(db_with_data)
    terms = repo.list_terms_for_client("c_active")
    assert len(terms) == 1
    assert terms[0].term == "战略陪伴"
    assert isinstance(terms[0], GlossaryTerm)


@pytest.mark.integration
def test_glossary_find_by_normalized(db_with_data: Database):
    repo = get_glossary_repository(db_with_data)
    term = repo.find_term_by_normalized("c_active", "战略陪伴")
    assert term is not None
    term2 = repo.find_term_by_normalized("c_active", "不存在")
    assert term2 is None


@pytest.mark.integration
def test_glossary_list_attributes_verified_only(db_with_data: Database):
    repo = get_glossary_repository(db_with_data)
    verified = repo.list_attributes_for_client("c_active", verified_only=True)
    assert len(verified) == 1
    assert verified[0].attribute_name == "周期"
    all_attrs = repo.list_attributes_for_client("c_active", verified_only=False)
    assert len(all_attrs) == 2


@pytest.mark.integration
def test_glossary_count_pending_verifications(db_with_data: Database):
    repo = get_glossary_repository(db_with_data)
    assert repo.count_pending_verifications("c_active") == 1


@pytest.mark.integration
def test_glossary_verify_attribute(db_with_data: Database):
    repo = get_glossary_repository(db_with_data)
    ok = repo.verify_attribute(
        "ga_2", verified_by="顾源源",
        verified_at="2026-05-21", updated_at="2026-05-21",
    )
    assert ok is True
    assert repo.count_pending_verifications("c_active") == 0


# ═══════════════════════════════════════════════════════════════════════════
# 占位模块:client / task / knowledge / narrative / intelligence
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
def test_client_repository_uses_v_active_clients(db_with_data: Database):
    """v2.1 守卫:client repo 通过 SQL view,frozen client 不出现"""
    repo = get_client_repository(db_with_data)
    ids = repo.list_active_client_ids()
    assert "c_active" in ids
    assert "c_frozen" not in ids
    assert repo.count_active() == 1


@pytest.mark.integration
def test_task_repository_uses_v_pending_tasks(db_with_data: Database):
    repo = get_task_repository(db_with_data)
    assert repo.count_pending() == 1
    assert repo.count_pending(client_id="c_active") == 1
    assert repo.count_pending(client_id="c_frozen") == 0


@pytest.mark.integration
def test_knowledge_repository_uses_v_searchable_knowledge(db_with_data: Database):
    repo = get_knowledge_repository(db_with_data)
    # k_1 挂 c_active(active),应能查到
    assert repo.count_searchable() == 1
    assert repo.count_searchable(client_id="c_active") == 1


@pytest.mark.integration
def test_narrative_repository_uses_v_active_event_lines(db_with_data: Database):
    repo = get_narrative_repository(db_with_data)
    assert repo.count_active_event_lines() == 1
    assert repo.count_active_event_lines(client_id="c_active") == 1


@pytest.mark.integration
def test_intelligence_repository_graceful_when_no_table(db: Database):
    """intelligence_items 表 v1 没建,Repository 应优雅返 0(不崩)"""
    repo = get_intelligence_repository(db)
    # 应该返回 0(没表或空表)
    count = repo.count_items()
    assert isinstance(count, int)
    assert count >= 0


# ═══════════════════════════════════════════════════════════════════════════
# 7 个模块 __all__ 暴露的接口齐全
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.unit
@pytest.mark.parametrize("module_name,expected_names", [
    ("client", {"ClientRepository", "get_client_repository"}),
    ("commitment", {"Commitment", "CommitmentStatus", "CommitmentRepository", "get_commitment_repository"}),
    ("glossary", {"GlossaryTerm", "GlossaryAttribute", "GlossaryRepository", "get_glossary_repository"}),
    ("intelligence", {"IntelligenceRepository", "get_intelligence_repository"}),
    ("knowledge", {"KnowledgeRepository", "get_knowledge_repository"}),
    ("narrative", {"NarrativeRepository", "get_narrative_repository"}),
    ("task", {"TaskRepository", "get_task_repository"}),
])
def test_module_exports_complete(module_name, expected_names):
    """每个模块的 __all__ 至少包含期望的接口"""
    import importlib
    mod = importlib.import_module(f"app.modules.{module_name}")
    actual = set(getattr(mod, "__all__", []))
    missing = expected_names - actual
    assert not missing, f"module {module_name} missing exports: {missing}"
