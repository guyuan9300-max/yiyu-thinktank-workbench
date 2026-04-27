from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.models import EvidenceItem, PageContextPackRecord, RouteDecisionRecord
from app.services.evidence_quality_feedback import build_evidence_excerpt_hash
from app.services.evidence_quality_store import ensure_evidence_quality_annotation_schema
from app.services.evidence_selector import select_answer_evidence


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def _insert_annotation(
    client: TestClient,
    *,
    annotation_id: str,
    source_id: str,
    evidence: EvidenceItem,
    label: str,
) -> None:
    db = client.app.state.app_state.db
    now = datetime.now().replace(microsecond=0).isoformat()
    excerpt_hash = build_evidence_excerpt_hash(
        title=evidence.title,
        excerpt=evidence.excerpt,
        path=evidence.path,
    )
    db.execute(
        """
        INSERT INTO evidence_quality_annotations(
            id, source_type, source_id, document_id, path, excerpt_hash, source_kind,
            quality_score, demotion_score, noise_reasons_json, authority_hint,
            human_label, human_note, created_at, updated_at
        )
        VALUES(?, 'workspace_chat', ?, ?, ?, ?, 'raw_document', 0.7, 0.0, '[]', 'raw', ?, '', ?, ?)
        """,
        (
            annotation_id,
            source_id,
            evidence.documentId,
            evidence.path,
            excerpt_hash,
            label,
            now,
            now,
        ),
    )


def test_evidence_quality_feedback_changes_selector_priority(tmp_path: Path):
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    ensure_evidence_quality_annotation_schema(db)
    source_id = "client_selector_feedback_p24"

    noisy = EvidenceItem(
        id="ev_noise",
        title="历史回答生成稿",
        excerpt="这是历史回答生成稿，模板内容模板内容模板内容。",
        sourceType="generated_answer",
        documentId="doc_noise",
        path="/tmp/answer_noise.md",
        score=1.5,
        sectionLabel="模板页",
        retrievalStage="raw_chunk",
    )
    useful = EvidenceItem(
        id="ev_useful",
        title="业务介绍与服务对象",
        excerpt="该机构核心业务包括资源支持、项目服务与平台协作，重点服务儿童群体。",
        sourceType="knowledge_chunk",
        documentId="doc_useful",
        path="/tmp/business_intro.md",
        score=0.2,
        sectionLabel="业务介绍",
        retrievalStage="raw_chunk",
    )
    route = RouteDecisionRecord(intent="business_profile", retrievalMode="hybrid")
    page_context = PageContextPackRecord(page="workspace_chat", scopeType="client", scopeId=source_id, clientId=source_id)

    baseline = select_answer_evidence(
        prompt="核心业务是什么",
        intent="business_profile",
        route_decision=route,
        evidence=[noisy, useful],
        page_context=page_context,
    )
    assert baseline

    _insert_annotation(client, annotation_id="eqa_selector_noise", source_id=source_id, evidence=noisy, label="noise")
    _insert_annotation(client, annotation_id="eqa_selector_useful", source_id=source_id, evidence=useful, label="useful")

    selected = select_answer_evidence(
        prompt="核心业务是什么",
        intent="business_profile",
        route_decision=route,
        evidence=[noisy, useful],
        page_context=page_context,
        db=db,
        source_type="workspace_chat",
        source_id=source_id,
    )
    assert selected
    assert selected[0].id == "ev_useful"

    # registry/state-only 查询不受人工标注排序干预
    registry_route = RouteDecisionRecord(intent="official_judgment_registry", retrievalMode="state_only", judgmentQueryMode="registry_only")
    selected_registry = select_answer_evidence(
        prompt="已批准正式判断有哪些",
        intent="official_judgment_registry",
        route_decision=registry_route,
        evidence=[noisy, useful],
        page_context=page_context,
        db=db,
        source_type="workspace_chat",
        source_id=source_id,
    )
    assert selected_registry


def test_evidence_quality_feedback_missing_annotation_table_is_safe(tmp_path: Path):
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    source_id = "client_selector_feedback_no_table_p24"

    evidence = EvidenceItem(
        id="ev_any",
        title="业务介绍",
        excerpt="机构业务包含项目支持与资源协作。",
        sourceType="knowledge_chunk",
        documentId="doc_any",
        path="/tmp/any.md",
        score=0.5,
        sectionLabel="业务介绍",
        retrievalStage="raw_chunk",
    )
    route = RouteDecisionRecord(intent="business_profile", retrievalMode="hybrid")
    page_context = PageContextPackRecord(page="workspace_chat", scopeType="client", scopeId=source_id, clientId=source_id)

    selected = select_answer_evidence(
        prompt="核心业务是什么",
        intent="business_profile",
        route_decision=route,
        evidence=[evidence],
        page_context=page_context,
        db=db,
        source_type="workspace_chat",
        source_id=source_id,
    )
    assert selected
    assert selected[0].id == "ev_any"
