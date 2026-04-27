from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.services.evidence_quality_feedback import build_evidence_excerpt_hash
from app.services.evidence_quality_store import ensure_evidence_quality_annotation_schema
from app.services.rerank_provider import RuleRerankProvider


@dataclass
class _Candidate:
    score: float
    source_stage: str
    section_label: str
    title: str
    excerpt: str
    source_type: str
    path: str
    document_id: str


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
    candidate: _Candidate,
    label: str,
) -> None:
    db = client.app.state.app_state.db
    now = datetime.now().replace(microsecond=0).isoformat()
    excerpt_hash = build_evidence_excerpt_hash(
        title=candidate.title,
        excerpt=candidate.excerpt,
        path=candidate.path,
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
            candidate.document_id,
            candidate.path,
            excerpt_hash,
            label,
            now,
            now,
        ),
    )


def test_evidence_quality_feedback_changes_rule_rerank_order(tmp_path: Path):
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    ensure_evidence_quality_annotation_schema(db)
    source_id = "client_rerank_feedback_p24"

    noisy = _Candidate(
        score=2.0,
        source_stage="raw_chunk",
        section_label="模板页",
        title="历史回答模板",
        excerpt="这是历史回答模板内容，重复生成稿。",
        source_type="generated_answer",
        path="/tmp/history_answer.md",
        document_id="doc_noise",
    )
    useful = _Candidate(
        score=0.1,
        source_stage="raw_chunk",
        section_label="业务介绍",
        title="核心业务说明",
        excerpt="机构通过资源支持与项目服务推动儿童发展。",
        source_type="knowledge_chunk",
        path="/tmp/business_source.md",
        document_id="doc_useful",
    )

    provider = RuleRerankProvider(db=db)
    baseline, _ = provider.rerank(
        "核心业务是什么",
        [noisy, useful],
        source_type="workspace_chat",
        source_id=source_id,
    )
    assert baseline

    _insert_annotation(client, annotation_id="eqa_rerank_noise", source_id=source_id, candidate=noisy, label="noise")
    _insert_annotation(client, annotation_id="eqa_rerank_useful", source_id=source_id, candidate=useful, label="useful")

    reranked, meta = provider.rerank(
        "核心业务是什么",
        [noisy, useful],
        source_type="workspace_chat",
        source_id=source_id,
    )
    assert meta.rerankUsed is True
    assert reranked
    assert reranked[0].title == useful.title

    no_feedback_provider = RuleRerankProvider(db=None)
    reranked_no_feedback, _ = no_feedback_provider.rerank(
        "核心业务是什么",
        [noisy, useful],
        source_type="workspace_chat",
        source_id=source_id,
    )
    assert reranked_no_feedback
