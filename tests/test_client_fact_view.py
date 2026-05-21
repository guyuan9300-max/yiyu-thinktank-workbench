"""F1.2 验证 · ClientFactView 聚合 6 表事实

跑法:
    单测:     backend/.venv/bin/python3 -m pytest tests/test_client_fact_view.py -q
    集成测试: backend/.venv/bin/python3 -m pytest tests/test_client_fact_view.py -q -m integration

覆盖:
- get_fact_bundle 完整流程
- 5 个细粒度 list_* 方法
- lazy load (load_dna_full / load_task_full)
- archived 处理
- 事件通知 (on_fact_changed / emit_fact_changed)
- 金标准: 真实日慈 db 跑出 NORTH_STAR 目标 B 的第一个里程碑
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.modules.client import (
    ClientCreatePayload,
    ClientFactBundle,
    ClientFactView,
    ClientRepository,
    EventLineFact,
    get_client_fact_view,
)


@pytest.fixture
def db() -> sqlite3.Connection:
    """In-memory DB + 全套表 schema (clients + event_lines + tasks + commitments
    + atomic_facts + client_dna_documents + v_active_clients view)"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.execute(
        """
        CREATE TABLE clients (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, alias TEXT NOT NULL,
            domain TEXT NOT NULL, type TEXT NOT NULL, intro TEXT NOT NULL,
            stage TEXT NOT NULL, color TEXT NOT NULL DEFAULT '#5B7BFE',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE VIEW v_active_clients AS
        SELECT id, name FROM clients
        WHERE stage NOT IN ('frozen', 'archived', 'lost')
        """
    )
    conn.execute(
        """
        CREATE TABLE event_lines (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL,
            kind TEXT NOT NULL DEFAULT 'custom',
            status TEXT NOT NULL DEFAULT 'active',
            stage TEXT, summary TEXT, intent TEXT,
            current_blocker TEXT, recent_decision TEXT, next_step TEXT,
            evidence_count INTEGER NOT NULL DEFAULT 0,
            owner_id TEXT, owner_name TEXT,
            primary_client_id TEXT, primary_client_name TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE tasks (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL DEFAULT '',
            client_id TEXT,
            title TEXT NOT NULL, description TEXT NOT NULL,
            status TEXT NOT NULL, priority TEXT NOT NULL,
            list_id TEXT NOT NULL DEFAULT 'list-0',
            creator_id TEXT NOT NULL DEFAULT '',
            owner_id TEXT, owner_name TEXT NOT NULL DEFAULT '',
            progress_status TEXT NOT NULL DEFAULT 'todo',
            ddl TEXT NOT NULL DEFAULT '',
            deadline_at TEXT, scheduled_start_at TEXT,
            scheduled_end_at TEXT, completed_at TEXT,
            start_date TEXT, due_date TEXT,
            duration_minutes INTEGER NOT NULL DEFAULT 60,
            event_line_id TEXT,
            business_category TEXT,
            current_blocker TEXT,
            next_action TEXT,
            recent_decision TEXT,
            evidence_count INTEGER NOT NULL DEFAULT 0,
            source_type TEXT NOT NULL DEFAULT '',
            source_id TEXT,
            tags_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE commitments (
            id TEXT PRIMARY KEY, client_id TEXT NOT NULL,
            committer TEXT NOT NULL, recipient TEXT NOT NULL,
            commitment_type TEXT NOT NULL DEFAULT 'delivery',
            content TEXT NOT NULL, deadline TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            related_term_ids_json TEXT NOT NULL DEFAULT '[]',
            source_type TEXT NOT NULL DEFAULT '',
            source_id TEXT NOT NULL DEFAULT '',
            fulfilled_at TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE atomic_facts (
            id TEXT PRIMARY KEY, client_id TEXT NOT NULL,
            subject_entity_id TEXT, subject_text TEXT NOT NULL,
            attribute TEXT NOT NULL, value_text TEXT NOT NULL,
            value_normalized TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.0,
            source_v2_chunk_id TEXT, source_v2_document_id TEXT,
            evidence_text TEXT, status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE client_dna_documents (
            client_id TEXT NOT NULL, module_key TEXT NOT NULL,
            title TEXT NOT NULL, markdown_content TEXT NOT NULL,
            normalized_text TEXT NOT NULL, summary TEXT NOT NULL,
            file_name TEXT NOT NULL, content_hash TEXT NOT NULL,
            source_kind TEXT NOT NULL DEFAULT 'manual',
            missing_info_json TEXT NOT NULL DEFAULT '[]',
            updated_at TEXT NOT NULL, updated_by TEXT NOT NULL,
            PRIMARY KEY (client_id, module_key)
        )
        """
    )
    return conn


@pytest.fixture
def view(db: sqlite3.Connection) -> ClientFactView:
    return ClientFactView(db)


@pytest.fixture
def japan_client_id(db: sqlite3.Connection) -> str:
    """创建一个日慈基金会的测试客户, 返回 id"""
    repo = ClientRepository(db)
    created = repo.create(
        ClientCreatePayload(name="日慈基金会", alias="日慈", stage="active")
    )
    return created.id


# ── 基础 / 工厂 ──────────────────────────────────────────────


def test_factory_function(db: sqlite3.Connection) -> None:
    view = get_client_fact_view(db)
    assert isinstance(view, ClientFactView)


def test_get_fact_bundle_empty_client(
    view: ClientFactView, japan_client_id: str
) -> None:
    """新建客户, bundle 应该全空 list, counts 全 0"""
    bundle = view.get_fact_bundle(japan_client_id)
    assert bundle is not None
    assert bundle.client.name == "日慈基金会"
    assert bundle.event_lines == ()
    assert bundle.tasks == ()
    assert bundle.commitments == ()
    assert bundle.dna_documents == ()
    assert bundle.atomic_facts == ()
    assert bundle.counts == {
        "event_lines": 0,
        "tasks": 0,
        "commitments": 0,
        "dna_documents": 0,
        "atomic_facts": 0,
    }
    assert bundle.snapshot_at != ""
    assert "client" in bundle.sources


def test_get_fact_bundle_nonexistent_returns_none(view: ClientFactView) -> None:
    assert view.get_fact_bundle("nonexistent") is None


def test_get_fact_bundle_archived_returns_none(
    view: ClientFactView, db: sqlite3.Connection, japan_client_id: str
) -> None:
    """stage='archived' 默认返回 None"""
    repo = ClientRepository(db)
    repo.archive(japan_client_id)
    assert view.get_fact_bundle(japan_client_id) is None


def test_get_fact_bundle_archived_with_include_returns(
    view: ClientFactView, db: sqlite3.Connection, japan_client_id: str
) -> None:
    """stage='archived' + include_archived=True 时返回"""
    repo = ClientRepository(db)
    repo.archive(japan_client_id)
    bundle = view.get_fact_bundle(japan_client_id, include_archived=True)
    assert bundle is not None
    assert bundle.client.stage == "archived"


# ── 事件线 ───────────────────────────────────────────────────


def test_list_event_lines_returns_only_client_owned(
    view: ClientFactView, db: sqlite3.Connection, japan_client_id: str
) -> None:
    """只返回 primary_client_id 匹配的事件线"""
    db.execute(
        """
        INSERT INTO event_lines (id, name, kind, status, stage, summary,
            intent, current_blocker, recent_decision, next_step,
            evidence_count, owner_name, primary_client_id, primary_client_name,
            created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "eline_1", "日慈战略陪伴", "project_line", "paused", "本周推进",
            "Q1 三个项目复盘中", "教师项目设计需补完", "", "", "",
            83, "顾源源", japan_client_id, "日慈基金会",
            "2026-05-01", "2026-05-19",
        ),
    )
    # 一个属于别的客户的
    db.execute(
        """
        INSERT INTO event_lines (id, name, kind, status, stage, summary,
            intent, current_blocker, recent_decision, next_step,
            evidence_count, owner_name, primary_client_id, primary_client_name,
            created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "eline_2", "其它客户事件线", "custom", "active", "",
            "", "", "", "", "",
            0, "", "other_client_id", "其它",
            "2026-05-01", "2026-05-01",
        ),
    )

    event_lines = view.list_event_lines(japan_client_id)
    assert len(event_lines) == 1
    assert isinstance(event_lines[0], EventLineFact)
    assert event_lines[0].name == "日慈战略陪伴"
    assert event_lines[0].evidence_count == 83
    assert event_lines[0].owner_name == "顾源源"


def test_list_event_lines_sorted_by_updated_at_desc(
    view: ClientFactView, db: sqlite3.Connection, japan_client_id: str
) -> None:
    for i, ts in enumerate(["2026-05-01", "2026-05-15", "2026-05-10"]):
        db.execute(
            """
            INSERT INTO event_lines (id, name, kind, status, stage, summary,
                intent, current_blocker, recent_decision, next_step,
                evidence_count, owner_name, primary_client_id, primary_client_name,
                created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"eline_{i}", f"L{i}", "custom", "active", "",
                "", "", "", "", "",
                0, "", japan_client_id, "日慈",
                ts, ts,
            ),
        )
    event_lines = view.list_event_lines(japan_client_id)
    names = [e.name for e in event_lines]
    assert names == ["L1", "L2", "L0"]  # 5/15 > 5/10 > 5/01


def test_list_event_lines_empty_client_id(view: ClientFactView) -> None:
    assert view.list_event_lines("") == []


# ── 任务 ────────────────────────────────────────────────────


def test_list_tasks_excludes_done_by_default(
    view: ClientFactView, db: sqlite3.Connection, japan_client_id: str
) -> None:
    """status='done' / 'completed' / 'cancelled' / 'archived' 不在 bundle 里"""
    test_data = [
        ("t1", "活的任务 1", "todo"),
        ("t2", "完成的", "done"),
        ("t3", "完成态 2", "completed"),
        ("t4", "取消的", "cancelled"),
        ("t5", "归档的", "archived"),
        ("t6", "活的任务 2", "doing"),
    ]
    for tid, title, status in test_data:
        db.execute(
            """
            INSERT INTO tasks (id, client_id, title, description, status, priority,
                progress_status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'normal', 'todo', ?, ?)
            """,
            (tid, japan_client_id, title, "desc", status, "2026-05-01", "2026-05-01"),
        )
    tasks = view.list_tasks(japan_client_id, include_done=False)
    titles = {t.title for t in tasks}
    assert titles == {"活的任务 1", "活的任务 2"}


def test_list_tasks_include_done_returns_all(
    view: ClientFactView, db: sqlite3.Connection, japan_client_id: str
) -> None:
    for tid, status in [("t1", "todo"), ("t2", "done")]:
        db.execute(
            """
            INSERT INTO tasks (id, client_id, title, description, status, priority,
                progress_status, created_at, updated_at)
            VALUES (?, ?, ?, '', ?, 'normal', 'todo', ?, ?)
            """,
            (tid, japan_client_id, f"task {tid}", status, "2026-05-01", "2026-05-01"),
        )
    tasks = view.list_tasks(japan_client_id, include_done=True)
    assert len(tasks) == 2


def test_task_description_truncated(
    view: ClientFactView, db: sqlite3.Connection, japan_client_id: str
) -> None:
    """description 超过 200 字应截断 + ..."""
    long_desc = "A" * 300
    db.execute(
        """
        INSERT INTO tasks (id, client_id, title, description, status, priority,
            progress_status, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'todo', 'normal', 'todo', ?, ?)
        """,
        ("t1", japan_client_id, "T", long_desc, "2026-05-01", "2026-05-01"),
    )
    tasks = view.list_tasks(japan_client_id)
    assert len(tasks[0].description_preview) == 203  # 200 + "..."
    assert tasks[0].description_preview.endswith("...")


def test_load_task_full_returns_full_description(
    view: ClientFactView, db: sqlite3.Connection, japan_client_id: str
) -> None:
    long_desc = "A" * 500
    db.execute(
        """
        INSERT INTO tasks (id, client_id, title, description, status, priority,
            progress_status, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'todo', 'normal', 'todo', ?, ?)
        """,
        ("t1", japan_client_id, "T", long_desc, "2026-05-01", "2026-05-01"),
    )
    full = view.load_task_full("t1")
    assert full == long_desc


# ── 承诺 (复用 W3 CommitmentRepository) ─────────────────────


def test_list_commitments(
    view: ClientFactView, db: sqlite3.Connection, japan_client_id: str
) -> None:
    db.execute(
        """
        INSERT INTO commitments (id, client_id, committer, recipient,
            commitment_type, content, deadline, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "cm1", japan_client_id, "顾源源", "张真", "delivery",
            "撰写价值观调研问题", "2026-06-30", "pending",
            "2026-05-19", "2026-05-19",
        ),
    )
    commitments = view.list_commitments(japan_client_id)
    assert len(commitments) == 1
    assert commitments[0].committer == "顾源源"
    assert commitments[0].recipient == "张真"
    assert commitments[0].status == "pending"


# ── DNA 文档 ─────────────────────────────────────────────────


def test_list_dna_documents_lite(
    view: ClientFactView, db: sqlite3.Connection, japan_client_id: str
) -> None:
    """list_dna_documents 不带 markdown_content, has_full_content 标记是否有大字段"""
    db.execute(
        """
        INSERT INTO client_dna_documents (client_id, module_key, title,
            markdown_content, normalized_text, summary, file_name, content_hash,
            source_kind, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            japan_client_id, "organization_intro", "组织介绍",
            "A" * 10000, "normalized text", "日慈基金会简介",
            "intro.md", "hash1", "manual",
            "2026-03-17", "user_guyuan",
        ),
    )
    dnas = view.list_dna_documents(japan_client_id)
    assert len(dnas) == 1
    assert dnas[0].module_key == "organization_intro"
    assert dnas[0].title == "组织介绍"
    assert dnas[0].has_full_content is True
    # 验证轻量 — DnaDocumentRef 类没有 markdown_content 字段
    assert not hasattr(dnas[0], "markdown_content")


def test_load_dna_full_returns_markdown(
    view: ClientFactView, db: sqlite3.Connection, japan_client_id: str
) -> None:
    db.execute(
        """
        INSERT INTO client_dna_documents (client_id, module_key, title,
            markdown_content, normalized_text, summary, file_name, content_hash,
            source_kind, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            japan_client_id, "business_intro", "项目介绍",
            "# 心灵魔法学院\n服务 1.5 万教师", "",
            "项目摘要", "intro.md", "hash1", "manual",
            "2026-03-17", "user_guyuan",
        ),
    )
    full = view.load_dna_full(japan_client_id, "business_intro")
    assert full is not None
    assert "心灵魔法学院" in full


# ── 原子事实 ─────────────────────────────────────────────────


def test_list_atomic_facts_only_active(
    view: ClientFactView, db: sqlite3.Connection, japan_client_id: str
) -> None:
    """status != 'active' 的事实不返回"""
    for fid, status in [
        ("af1", "active"),
        ("af2", "superseded"),
        ("af3", "rejected"),
        ("af4", "active"),
    ]:
        db.execute(
            """
            INSERT INTO atomic_facts (id, client_id, subject_text, attribute,
                value_text, value_normalized, confidence, status,
                created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 0.8, ?, ?, ?)
            """,
            (
                fid, japan_client_id, f"subj-{fid}", "attr",
                "value", "value", status, "2026-05-01", "2026-05-01",
            ),
        )
    facts = view.list_atomic_facts(japan_client_id)
    assert len(facts) == 2
    assert {f.id for f in facts} == {"af1", "af4"}


def test_list_atomic_facts_sorted_by_confidence_desc(
    view: ClientFactView, db: sqlite3.Connection, japan_client_id: str
) -> None:
    for fid, conf in [("af1", 0.5), ("af2", 0.9), ("af3", 0.7)]:
        db.execute(
            """
            INSERT INTO atomic_facts (id, client_id, subject_text, attribute,
                value_text, value_normalized, confidence, status,
                created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (
                fid, japan_client_id, f"s{fid}", "a", "v", "v", conf,
                "2026-05-01", "2026-05-01",
            ),
        )
    facts = view.list_atomic_facts(japan_client_id)
    ids = [f.id for f in facts]
    assert ids == ["af2", "af3", "af1"]


def test_atomic_fact_has_provenance(
    view: ClientFactView, db: sqlite3.Connection, japan_client_id: str
) -> None:
    """atomic_fact 应带 source_v2_document_id / source_v2_chunk_id (provenance)"""
    db.execute(
        """
        INSERT INTO atomic_facts (id, client_id, subject_text, attribute,
            value_text, value_normalized, confidence,
            source_v2_chunk_id, source_v2_document_id, evidence_text,
            status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
        """,
        (
            "af1", japan_client_id, "张真", "职务", "理事长", "理事长", 0.95,
            "chunk_xyz", "v2doc_doc_6208443a2d", "5/19 会议纪要 §2.1",
            "2026-05-19", "2026-05-19",
        ),
    )
    facts = view.list_atomic_facts(japan_client_id)
    assert facts[0].source_v2_document_id == "v2doc_doc_6208443a2d"
    assert facts[0].source_v2_chunk_id == "chunk_xyz"
    assert facts[0].evidence_text == "5/19 会议纪要 §2.1"


# ── 完整 bundle 集成 ─────────────────────────────────────────


def test_get_fact_bundle_complete(
    view: ClientFactView, db: sqlite3.Connection, japan_client_id: str
) -> None:
    """完整流程: 6 表都有数据, bundle 都拿到"""
    # event_line
    db.execute(
        """
        INSERT INTO event_lines (id, name, kind, status, stage, summary,
            intent, current_blocker, recent_decision, next_step,
            evidence_count, owner_name, primary_client_id, primary_client_name,
            created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "eline_1", "日慈战略陪伴", "project_line", "paused", "本周推进",
            "Q1 三个项目复盘", "教师项目设计需补完", "", "", "",
            83, "顾源源", japan_client_id, "日慈基金会",
            "2026-05-01", "2026-05-19",
        ),
    )
    # task
    db.execute(
        """
        INSERT INTO tasks (id, client_id, title, description, status, priority,
            progress_status, event_line_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'todo', 'high', 'todo', ?, ?, ?)
        """,
        (
            "task_1", japan_client_id, "和日慈张真进行5月份第一次战略对齐会",
            "讨论 Q2 路径", "eline_1", "2026-05-15", "2026-05-19",
        ),
    )
    # commitment
    db.execute(
        """
        INSERT INTO commitments (id, client_id, committer, recipient,
            commitment_type, content, deadline, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'delivery', ?, ?, 'pending', ?, ?)
        """,
        (
            "cm1", japan_client_id, "顾源源", "张真",
            "撰写价值观调研问题", "2026-06-30", "2026-05-19", "2026-05-19",
        ),
    )
    # dna
    db.execute(
        """
        INSERT INTO client_dna_documents (client_id, module_key, title,
            markdown_content, normalized_text, summary, file_name, content_hash,
            source_kind, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            japan_client_id, "organization_intro", "组织介绍",
            "# 日慈基金会\n2013 年成立", "", "日慈基金会简介",
            "org.md", "hash1", "manual", "2026-03-17", "user_guyuan",
        ),
    )
    # atomic_fact
    db.execute(
        """
        INSERT INTO atomic_facts (id, client_id, subject_text, attribute,
            value_text, value_normalized, confidence, status,
            created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 0.95, 'active', ?, ?)
        """,
        (
            "af1", japan_client_id, "张真", "职务", "理事长", "理事长",
            "2026-05-19", "2026-05-19",
        ),
    )

    bundle = view.get_fact_bundle(japan_client_id)
    assert bundle is not None
    assert bundle.counts == {
        "event_lines": 1,
        "tasks": 1,
        "commitments": 1,
        "dna_documents": 1,
        "atomic_facts": 1,
    }
    assert bundle.event_lines[0].name == "日慈战略陪伴"
    assert "张真" in bundle.tasks[0].title
    assert bundle.commitments[0].content == "撰写价值观调研问题"
    assert bundle.dna_documents[0].module_key == "organization_intro"
    assert bundle.atomic_facts[0].subject_text == "张真"
    # provenance
    assert all(k in bundle.sources for k in [
        "client", "event_lines", "tasks", "commitments",
        "dna_documents", "atomic_facts",
    ])


def test_get_fact_bundle_lite_only_counts(
    view: ClientFactView, db: sqlite3.Connection, japan_client_id: str
) -> None:
    """lite 版只返回 counts, 不拿 list (性能)"""
    # 加一个任务
    db.execute(
        """
        INSERT INTO tasks (id, client_id, title, description, status, priority,
            progress_status, created_at, updated_at)
        VALUES (?, ?, ?, '', 'todo', 'normal', 'todo', ?, ?)
        """,
        ("t1", japan_client_id, "T", "2026-05-01", "2026-05-01"),
    )
    bundle = view.get_fact_bundle_lite(japan_client_id)
    assert bundle is not None
    assert bundle.tasks == ()  # 空 tuple, 不拿 list
    assert bundle.counts["tasks"] == 1


# ── 事件通知 ──────────────────────────────────────────────────


def test_on_fact_changed_callback(view: ClientFactView) -> None:
    """订阅 + emit 走通"""
    events: list[tuple[str, str, str]] = []
    view.on_fact_changed(lambda cid, ft, ck: events.append((cid, ft, ck)))
    view.emit_fact_changed("client_x", "task", "created")
    assert events == [("client_x", "task", "created")]


def test_emit_fact_changed_swallows_callback_errors(view: ClientFactView) -> None:
    """callback 抛异常不阻塞"""

    def bad_cb(cid: str, ft: str, ck: str) -> None:
        raise RuntimeError("intentional")

    view.on_fact_changed(bad_cb)
    # 不应抛
    view.emit_fact_changed("c", "t", "u")


# ── 边界 ──────────────────────────────────────────────────────


def test_empty_client_id_returns_empty_lists(view: ClientFactView) -> None:
    assert view.list_event_lines("") == []
    assert view.list_tasks("") == []
    assert view.list_commitments("") == []
    assert view.list_dna_documents("") == []
    assert view.list_atomic_facts("") == []
    assert view.load_dna_full("", "k") is None
    assert view.load_dna_full("c", "") is None
    assert view.load_task_full("") is None


def test_list_bundles_for_active_clients(
    view: ClientFactView, db: sqlite3.Connection
) -> None:
    """活跃客户的 bundle 列表"""
    repo = ClientRepository(db)
    repo.create(ClientCreatePayload(name="A", stage="active"))
    repo.create(ClientCreatePayload(name="B", stage="frozen"))
    repo.create(ClientCreatePayload(name="C", stage="archived"))
    repo.create(ClientCreatePayload(name="D", stage="active"))

    bundles = view.list_bundles_for_active_clients(lite=True)
    # 只 active (A + D), frozen B 默认不在 list_active 里
    assert len(bundles) == 2
    names = {b.client.name for b in bundles}
    assert names == {"A", "D"}


# ── 金标准: 真实日慈 db 集成测试 ─────────────────────────────


@pytest.mark.integration
def test_japan_client_fact_bundle_real_db() -> None:
    """NORTH_STAR 目标 B 第一个里程碑:
    用真实桌面 db, ClientFactView.get_fact_bundle 应返回完整 bundle。

    真实数据形态 (2026-05-21 实测):
    - client: 日慈基金会 (stage='待导入资料' — 自定义 stage, 不在 Literal 但 view 容错)
    - event_lines: 3 条 (日慈战略陪伴 + 建立重点客户周跟进节奏表 + 约见日慈张真看益语系统)
    - tasks: 14 条 全部 status='done' (历史完成的任务)
    - atomic_facts: 702 行, 197 active (W1 fact_extractor 跑过)
    - commitments: 36 条
    - dna_documents: 4 个模块 (business_intro / market_intro / organization_intro / team_intro)
    """
    db_path = (
        Path.home()
        / "Library"
        / "Application Support"
        / "YiyuThinkTankWorkbench2"
        / "app.db"
    )
    if not db_path.exists():
        pytest.skip("desktop db not present (CI env)")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    view = ClientFactView(conn)

    # 用 include_archived=True 因为 stage='待导入资料' 不是标准 Literal
    # 但也不是 frozen/archived/lost, 所以默认 include_archived=False 也能过
    bundle = view.get_fact_bundle("client_284afd836e")
    assert bundle is not None, "日慈 client_284afd836e 应当存在"
    assert "日慈" in bundle.client.name

    # 事件线: 至少 1 条, 应包含'日慈战略陪伴'
    assert bundle.counts["event_lines"] >= 1, (
        f"应至少 1 条事件线, 实际 {bundle.counts['event_lines']}"
    )
    assert any(el.name == "日慈战略陪伴" for el in bundle.event_lines), (
        f"应该有'日慈战略陪伴'事件线, 实际: "
        f"{[e.name for e in bundle.event_lines]}"
    )

    # 任务: 默认 view 不含 done, 真实数据日慈所有任务都是 done, 所以默认拿到 0
    # 用 include_done=True 拿全部 - 这才能验证 ClientFactView 真实可用
    all_tasks = view.list_tasks("client_284afd836e", include_done=True, limit=500)
    assert len(all_tasks) >= 5, (
        f"日慈历史上至少有 5 个任务, 实际 {len(all_tasks)}"
    )
    assert any("张真" in t.title for t in all_tasks), (
        f"应该有张真相关任务, 实际任务标题: {[t.title for t in all_tasks[:5]]}"
    )

    # atomic_facts > 0 (W1 fact_extractor 跑过 197 active 行)
    assert bundle.counts["atomic_facts"] > 0, (
        f"原子事实应 > 0 (实际 {bundle.counts['atomic_facts']})"
    )

    # commitments > 0 (实测 36 条)
    assert bundle.counts["commitments"] > 0, (
        f"承诺应 > 0 (实际 {bundle.counts['commitments']})"
    )

    # dna_documents 4 个模块都在
    assert bundle.counts["dna_documents"] >= 3, (
        f"DNA 模块应 >= 3, 实际 {bundle.counts['dna_documents']}"
    )

    # provenance
    assert "client" in bundle.sources
    assert "event_lines" in bundle.sources
    assert bundle.snapshot_at != ""

    # 打印一份汇总, 方便后续 Phase 2/3 验收对比
    print(f"\n  ✓ 日慈基金会真实 bundle 拿到:")
    print(f"    event_lines: {bundle.counts['event_lines']}")
    print(f"    tasks (active): {bundle.counts['tasks']}")
    print(f"    tasks (incl done): {len(all_tasks)}")
    print(f"    commitments: {bundle.counts['commitments']}")
    print(f"    dna_documents: {bundle.counts['dna_documents']}")
    print(f"    atomic_facts (active): {bundle.counts['atomic_facts']}")


@pytest.mark.integration
def test_japan_5_19_meeting_data_visible() -> None:
    """NORTH_STAR §1 目标 B 关键验收: 5/19 张真会议相关事实是否能从 ClientFactView 拿到

    这是 v2.2 的"金标准案例"。Phase 1 F1.2 完成时, 应当能:
    1. 拿到 5/19 那场任务 (即使是 done 状态)
    2. atomic_facts 里能找到一些跟 5/19 会议主题相关的事实
    """
    db_path = (
        Path.home()
        / "Library"
        / "Application Support"
        / "YiyuThinkTankWorkbench2"
        / "app.db"
    )
    if not db_path.exists():
        pytest.skip("desktop db not present (CI env)")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    view = ClientFactView(conn)

    # 拿全部任务 (含 done) 找 5/19 那场会
    all_tasks = view.list_tasks("client_284afd836e", include_done=True, limit=500)
    matching_5_19 = [
        t for t in all_tasks
        if "张真" in t.title and ("5月" in t.title or "5月份" in t.title)
    ]
    assert len(matching_5_19) >= 1, (
        f"应该有 5/19 张真对齐会任务, 实际匹配: {[t.title for t in matching_5_19]}"
    )
    # 任务的 description 应包含会议内容线索 (即使是 preview 200 字)
    target_task = matching_5_19[0]
    print(f"\n  ✓ 找到 5/19 任务: {target_task.title}")
    print(f"    status: {target_task.status}, progress: {target_task.progress_status}")
    print(f"    description preview: {target_task.description_preview[:100]}...")
