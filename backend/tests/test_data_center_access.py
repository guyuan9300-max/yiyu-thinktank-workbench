from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.services.data_center_access import (
    DataCenterAccessContext,
    build_ingest_event_access_where,
    build_memory_fact_access_where,
)
from app.services.data_center_ingest import ensure_data_center_ingest_schema
from app.services.knowledge_v2 import fetch_document_cards, retrieve_knowledge_bundle, upsert_canonical_text_document


NOW = "2026-04-26T10:00:00"


def _insert_client(db: Database) -> None:
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, created_at, updated_at)
        VALUES('client_access', '益语平台', '益语平台', '公益科技', '客户', '公益组织数字化平台', '推进中', ?, ?)
        """,
        (NOW, NOW),
    )


def _upsert_doc(
    db: Database,
    data_dir: Path,
    *,
    origin_id: str,
    title: str,
    text: str,
    department_id: str = "",
    department_ids: list[str] | None = None,
    owner_user_id: str = "",
    visibility_scope: str = "project_public",
    content_domain: str = "work",
    lifecycle_status: str = "active",
) -> None:
    upsert_canonical_text_document(
        db,
        data_dir=data_dir,
        client_id="client_access",
        canonical_kind="raw_file",
        origin_type="file_import",
        origin_id=origin_id,
        title=title,
        text=text,
        visible_category="项目与业务",
        secondary_category="测试资料",
        created_at=NOW,
        updated_at=NOW,
        organization_id="org_access",
        department_id=department_id,
        department_ids=department_ids,
        owner_user_id=owner_user_id,
        source_entity_type="file_import",
        source_entity_id=origin_id,
        visibility_scope=visibility_scope,
        content_domain=content_domain,
        lifecycle_status=lifecycle_status,
    )


def _titles(bundle) -> set[str]:
    return {item.title for item in bundle.citations}


def test_ceo_reads_all_active_work_docs_but_not_private_or_deleted(tmp_path: Path) -> None:
    db = Database(tmp_path / "access.db")
    _insert_client(db)
    _upsert_doc(db, tmp_path / "data", origin_id="dept_a", title="部门A平台资料", text="平台价值表达 A", department_id="dept_a")
    _upsert_doc(db, tmp_path / "data", origin_id="dept_b", title="部门B平台资料", text="平台价值表达 B", department_id="dept_b")
    _upsert_doc(db, tmp_path / "data", origin_id="missing_dept", title="无部门平台资料", text="平台价值表达 missing")
    _upsert_doc(
        db,
        tmp_path / "data",
        origin_id="private_doc",
        title="个人平台资料",
        text="平台个人记录",
        owner_user_id="user_a",
        visibility_scope="self",
        content_domain="personal",
    )
    _upsert_doc(
        db,
        tmp_path / "data",
        origin_id="deleted_doc",
        title="已删除平台资料",
        text="平台删除记录",
        department_id="dept_a",
        lifecycle_status="deleted",
    )

    bundle = retrieve_knowledge_bundle(
        db,
        tmp_path / "data",
        "client_access",
        "平台",
        access_context=DataCenterAccessContext(organization_id="org_access", role="ceo"),
    )

    titles = _titles(bundle)
    assert "部门A平台资料" in titles
    assert "部门B平台资料" in titles
    assert "无部门平台资料" in titles
    assert "个人平台资料" not in titles
    assert "已删除平台资料" not in titles


def test_department_view_requires_matching_department_ids(tmp_path: Path) -> None:
    db = Database(tmp_path / "access_department.db")
    _insert_client(db)
    _upsert_doc(db, tmp_path / "data", origin_id="dept_a", title="部门A平台资料", text="平台价值表达 A", department_id="dept_a")
    _upsert_doc(db, tmp_path / "data", origin_id="dept_b", title="部门B平台资料", text="平台价值表达 B", department_id="dept_b")
    _upsert_doc(db, tmp_path / "data", origin_id="multi", title="多部门平台资料", text="平台价值表达 C", department_ids=["dept_b", "dept_c"])
    _upsert_doc(db, tmp_path / "data", origin_id="missing", title="无部门平台资料", text="平台价值表达 missing", owner_user_id="other_user")

    bundle = retrieve_knowledge_bundle(
        db,
        tmp_path / "data",
        "client_access",
        "平台",
        access_context=DataCenterAccessContext(
            organization_id="org_access",
            role="department_lead",
            viewer_user_id="lead_a",
            department_ids=("dept_a",),
        ),
    )

    assert _titles(bundle) == {"部门A平台资料"}


def test_owner_can_read_owned_work_doc_even_without_department(tmp_path: Path) -> None:
    db = Database(tmp_path / "access_owner.db")
    _insert_client(db)
    _upsert_doc(db, tmp_path / "data", origin_id="owned", title="本人平台资料", text="平台本人记录", owner_user_id="user_a")
    _upsert_doc(db, tmp_path / "data", origin_id="other", title="他人平台资料", text="平台他人记录", owner_user_id="user_b")

    bundle = retrieve_knowledge_bundle(
        db,
        tmp_path / "data",
        "client_access",
        "平台",
        access_context=DataCenterAccessContext(
            organization_id="org_access",
            role="employee",
            viewer_user_id="user_a",
        ),
    )

    assert _titles(bundle) == {"本人平台资料"}


def test_personal_docs_only_visible_to_owner_when_requested(tmp_path: Path) -> None:
    db = Database(tmp_path / "access_private.db")
    _insert_client(db)
    _upsert_doc(
        db,
        tmp_path / "data",
        origin_id="private_owned",
        title="个人平台资料",
        text="平台个人记录",
        owner_user_id="user_a",
        visibility_scope="self",
        content_domain="personal",
    )

    hidden = retrieve_knowledge_bundle(
        db,
        tmp_path / "data",
        "client_access",
        "平台",
        access_context=DataCenterAccessContext(organization_id="org_access", role="employee", viewer_user_id="user_a"),
    )
    visible = retrieve_knowledge_bundle(
        db,
        tmp_path / "data",
        "client_access",
        "平台",
        access_context=DataCenterAccessContext(
            organization_id="org_access",
            role="employee",
            viewer_user_id="user_a",
            include_personal=True,
        ),
    )

    assert not hidden.citations
    assert _titles(visible) == {"个人平台资料"}


def test_document_cards_use_same_access_filter(tmp_path: Path) -> None:
    db = Database(tmp_path / "access_cards.db")
    _insert_client(db)
    _upsert_doc(db, tmp_path / "data", origin_id="dept_a", title="部门A平台资料", text="平台价值表达 A", department_id="dept_a")
    _upsert_doc(db, tmp_path / "data", origin_id="dept_b", title="部门B平台资料", text="平台价值表达 B", department_id="dept_b")

    cards = fetch_document_cards(
        db,
        "client_access",
        data_dir=tmp_path / "data",
        access_context=DataCenterAccessContext(
            organization_id="org_access",
            role="department_lead",
            viewer_user_id="lead_b",
            department_ids=("dept_b",),
        ),
    )

    assert [card["title"] for card in cards] == ["部门B平台资料"]


def test_memory_facts_and_ingest_events_use_central_access_sql(tmp_path: Path) -> None:
    db = Database(tmp_path / "access_facts.db")
    ensure_data_center_ingest_schema(db)
    db.execute(
        """
        INSERT INTO memory_facts(
            id, scope_type, scope_id, fact_key, fact_value, source_type, source_id,
            confidence, freshness, evidence_refs_json, valid_from, valid_to, created_at, updated_at,
            organization_id, department_id, department_ids_json, owner_user_id, visibility_scope, content_domain, lifecycle_status
        ) VALUES
        ('fact_a', 'client', 'client_access', 'a', '部门A', 'test', 'a', 1, 1, '[]', NULL, NULL, ?, ?,
            'org_access', 'dept_a', '[""dept_a""]', 'lead_a', 'project_public', 'work', 'active'),
        ('fact_b', 'client', 'client_access', 'b', '部门B', 'test', 'b', 1, 1, '[]', NULL, NULL, ?, ?,
            'org_access', 'dept_b', '[""dept_b""]', 'lead_b', 'project_public', 'work', 'active')
        """,
        (NOW, NOW, NOW, NOW),
    )
    db.execute(
        """
        INSERT INTO data_center_ingest_events(
            id, source_type, source_id, source_version, content_hash,
            organization_id, department_id, department_ids_json, owner_user_id, source_entity_type, source_entity_id,
            client_id, event_line_id, task_id, meeting_id, week_label, title,
            visibility_scope, content_domain, lifecycle_status, document_id, status, error_message,
            metadata_json, created_at, updated_at
        ) VALUES
        ('event_a', 'task', 'a', '', 'hash_a', 'org_access', 'dept_a', '[""dept_a""]', 'lead_a',
            'task', 'a', 'client_access', NULL, 'a', NULL, NULL, '部门A', 'project_public', 'work', 'active',
            NULL, 'ready', '', '{}', ?, ?),
        ('event_b', 'task', 'b', '', 'hash_b', 'org_access', 'dept_b', '[""dept_b""]', 'lead_b',
            'task', 'b', 'client_access', NULL, 'b', NULL, NULL, '部门B', 'project_public', 'work', 'active',
            NULL, 'ready', '', '{}', ?, ?)
        """,
        (NOW, NOW, NOW, NOW),
    )
    context = DataCenterAccessContext(
        organization_id="org_access",
        role="department_lead",
        viewer_user_id="lead_a",
        department_ids=("dept_a",),
    )
    fact_access = build_memory_fact_access_where("mf", context)
    event_access = build_ingest_event_access_where("e", context)

    fact_rows = db.fetchall(f"SELECT id FROM memory_facts mf WHERE {fact_access.sql}", fact_access.params)
    event_rows = db.fetchall(f"SELECT id FROM data_center_ingest_events e WHERE {event_access.sql}", event_access.params)

    assert [str(row["id"]) for row in fact_rows] == ["fact_a"]
    assert [str(row["id"]) for row in event_rows] == ["event_a"]
