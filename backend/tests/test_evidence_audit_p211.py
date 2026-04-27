from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.models import DataCenterRequestRecord, EvidenceItem, PageContextPackRecord, RetrievalModelSettingsRecord, RouteDecisionRecord
from app.services import data_center_kernel as kernel
from app.services.evidence_quality import classify_evidence_quality
from app.services.evidence_selector import select_answer_evidence_with_trace
from app.services.question_focus import build_question_focus_frame
from app.services.source_reachability import build_source_reachability_audit


NOW = datetime.now().replace(microsecond=0).isoformat()


def _insert_client(db: Database, client_id: str) -> None:
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, color, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (client_id, "日慈基金会", "日慈", "rici.org", "ngo", "", "active", "#5B7BFE", NOW, NOW),
    )


def _insert_document(db: Database, *, document_id: str, client_id: str, title: str, path: str, excerpt: str = "") -> None:
    db.execute(
        """
        INSERT INTO documents(id, client_id, folder_id, title, path, original_source_path, kind, source, excerpt, tags_json, created_at)
        VALUES(?, ?, NULL, ?, ?, NULL, 'document', 'import', ?, '[]', ?)
        """,
        (document_id, client_id, title, path, excerpt, NOW),
    )


def _insert_v2_document(
    db: Database,
    *,
    v2_id: str,
    client_id: str,
    document_id: str,
    path: str,
    file_name: str,
    preview_text: str,
    parse_status: str,
    visible_category: str = "项目与业务",
    secondary_category: str = "待人工复核",
    material_layer: str = "evidence",
) -> None:
    db.execute(
        """
        INSERT INTO v2_documents(
            id, client_id, document_id, original_path, managed_path, markdown_path, file_name, kind,
            material_layer, visible_category, secondary_category, parse_status, parse_error,
            preview_text, doc_index_text, content_hash, classification_confidence,
            section_count, chunk_count, imported_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, NULL, ?, 'document', ?, ?, ?, ?, NULL, ?, ?, 'hash', 0.9, 1, ?, ?, ?)
        """,
        (
            v2_id,
            client_id,
            document_id,
            path,
            path,
            file_name,
            material_layer,
            visible_category,
            secondary_category,
            parse_status,
            preview_text,
            preview_text,
            4 if parse_status == "ready" else 0,
            NOW,
            NOW,
        ),
    )


def test_classify_evidence_quality_assigns_semantic_roles():
    identity = EvidenceItem(
        id="identity",
        title="日慈-项目资助申请书-20231008",
        excerpt="申请机构：广东省日慈公益基金会，关注儿童青少年心理健康与心理教育。",
        sourceType="knowledge_chunk",
        retrievalStage="raw_chunk",
        sectionLabel="正文",
    )
    signal = classify_evidence_quality(identity)
    assert "institution_identity" in signal.semanticRoles
    assert "program_overview" in signal.semanticRoles
    assert "financial_or_admin" not in signal.semanticRoles

    meeting = EvidenceItem(
        id="meeting",
        title="日慈基金会-繁星计划一季度沟通会议纪要",
        excerpt="当前推进品牌协同与路演筹备，存在待确认事项。",
        sourceType="meeting_note",
        retrievalStage="state_pool",
    )
    meeting_signal = classify_evidence_quality(meeting)
    assert "operational_update" in meeting_signal.semanticRoles
    assert "risk_or_open_issue" in meeting_signal.semanticRoles

    support = EvidenceItem(
        id="support",
        title="日慈基金会业务介绍.md",
        excerpt="将心理健康嵌入教育现场，形成可复制路径。",
        sourceType="knowledge_document",
        path="/tmp/client/_imports/imp_x/日慈基金会业务介绍.md",
        retrievalStage="master_index",
    )
    support_signal = classify_evidence_quality(support)
    assert "derived_profile_support" in support_signal.semanticRoles


def test_selector_uses_focus_and_role_coverage_for_intro_questions():
    route = RouteDecisionRecord(intent="intro_profile", routeMode="raw_doc_drilldown", retrievalMode="hybrid")
    context = PageContextPackRecord(page="workspace_chat", scopeType="client", scopeId="c1", clientId="c1", intent="intro_profile")
    evidence = [
        EvidenceItem(
            id="meeting1",
            title="日慈基金会-繁星计划一季度沟通会议纪要",
            excerpt="推进品牌协同与路演筹备。",
            sourceType="meeting_note",
            score=0.95,
            retrievalStage="state_pool",
        ),
        EvidenceItem(
            id="meeting2",
            title="和日慈张真核对战略陪伴的进度",
            excerpt="本周推进战略陪伴进度与交付安排。",
            sourceType="meeting_note",
            score=0.92,
            retrievalStage="state_pool",
        ),
        EvidenceItem(
            id="identity",
            title="日慈-项目资助申请书-20231008",
            excerpt="申请机构：广东省日慈公益基金会，关注儿童青少年心理健康与心理教育。",
            sourceType="knowledge_chunk",
            score=0.45,
            retrievalStage="raw_chunk",
            sectionLabel="正文",
        ),
        EvidenceItem(
            id="program",
            title="心灵魔法学院项目__DUP1_日慈_20260216",
            excerpt="乡村儿童青少年心理健康发展的教育公益项目，覆盖学校与教师。",
            sourceType="knowledge_chunk",
            score=0.4,
            retrievalStage="raw_chunk",
            sectionLabel="正文",
        ),
        EvidenceItem(
            id="method",
            title="日慈工作坊核心核心观点总结",
            excerpt="通过场域、数字化、组织记忆和第二曲线形成可复制的心理教育路径。",
            sourceType="knowledge_chunk",
            score=0.35,
            retrievalStage="raw_chunk",
            sectionLabel="正文",
        ),
    ]

    result = select_answer_evidence_with_trace(
        prompt="介绍日慈基金会",
        intent="intro_profile",
        route_decision=route,
        evidence=evidence,
        page_context=context,
    )

    selected_titles = [item.title for item in result.selected]
    assert any("资助申请书" in title for title in selected_titles)
    assert any("心灵魔法学院" in title for title in selected_titles)
    assert "institution_identity" in result.selected_roles
    assert "program_overview" in result.selected_roles
    assert not all("纪要" in title or "进度" in title for title in selected_titles[:3])
    assert result.question_focus_frame.goal == "define"


def test_selector_limits_duplicate_documents_for_intro_questions():
    route = RouteDecisionRecord(intent="intro_profile", routeMode="raw_doc_drilldown", retrievalMode="hybrid")
    context = PageContextPackRecord(page="workspace_chat", scopeType="client", scopeId="c1", clientId="c1", intent="intro_profile")
    evidence = [
        EvidenceItem(
            id="checklist-1",
            title="日慈基金会·第一年度战略陪伴重点事项清单（讨论稿） (1).docx",
            excerpt="日慈基金会聚焦儿童青少年心理健康，强调关系生态建设与数字化工具赋能。",
            sourceType="knowledge_chunk",
            score=0.95,
            retrievalStage="raw_chunk",
            sectionLabel="正文",
            documentId="doc_checklist",
            path="/tmp/doc_checklist.docx",
        ),
        EvidenceItem(
            id="checklist-2",
            title="日慈基金会·第一年度战略陪伴重点事项清单（讨论稿） (1).docx",
            excerpt="年度主线：从课程服务交付向关系生态建设转型，完成第二曲线样板验证。",
            sourceType="knowledge_chunk",
            score=0.94,
            retrievalStage="raw_chunk",
            sectionLabel="正文",
            documentId="doc_checklist",
            path="/tmp/doc_checklist.docx",
        ),
        EvidenceItem(
            id="identity",
            title="日慈-项目资助申请书-20231008",
            excerpt="申请机构：广东省日慈公益基金会，关注儿童青少年心理健康与心理教育。",
            sourceType="knowledge_chunk",
            score=0.45,
            retrievalStage="raw_chunk",
            sectionLabel="正文",
            documentId="doc_grant",
            path="/tmp/doc_grant.docx",
        ),
        EvidenceItem(
            id="method",
            title="日慈工作坊核心核心观点总结",
            excerpt="通过场域、数字化、组织记忆和第二曲线形成可复制路径。",
            sourceType="knowledge_chunk",
            score=0.4,
            retrievalStage="raw_chunk",
            sectionLabel="正文",
            documentId="doc_workshop",
            path="/tmp/doc_workshop.docx",
        ),
    ]

    result = select_answer_evidence_with_trace(
        prompt="介绍日慈基金会",
        intent="intro_profile",
        route_decision=route,
        evidence=evidence,
        page_context=context,
    )

    selected_document_ids = [item.documentId for item in result.selected]
    assert selected_document_ids.count("doc_checklist") == 1
    assert "doc_grant" in selected_document_ids


def test_selector_keeps_operational_material_for_status_questions():
    route = RouteDecisionRecord(intent="status_progress", routeMode="hybrid", retrievalMode="hybrid")
    context = PageContextPackRecord(page="workspace_chat", scopeType="client", scopeId="c1", clientId="c1", intent="status_progress")
    evidence = [
        EvidenceItem(
            id="meeting1",
            title="日慈基金会-繁星计划一季度沟通会议纪要",
            excerpt="当前推进品牌协同与路演筹备。",
            sourceType="meeting_note",
            score=0.8,
            retrievalStage="state_pool",
        ),
        EvidenceItem(
            id="identity",
            title="日慈-项目资助申请书-20231008",
            excerpt="申请机构：广东省日慈公益基金会。",
            sourceType="knowledge_chunk",
            score=0.6,
            retrievalStage="raw_chunk",
        ),
    ]

    result = select_answer_evidence_with_trace(
        prompt="日慈最近推进到哪了",
        intent="status_progress",
        route_decision=route,
        evidence=evidence,
        page_context=context,
    )

    assert result.selected
    assert result.selected[0].id == "meeting1"
    assert "operational_update" in result.selected_roles
    assert result.question_focus_frame.goal == "status"


def test_source_reachability_audit_reports_support_and_parse_failures(tmp_path: Path):
    db = Database(tmp_path / "audit.db")
    client_id = "client_audit_p211"
    _insert_client(db, client_id)

    _insert_document(
        db,
        document_id="doc_ready",
        client_id=client_id,
        title="日慈-项目资助申请书-20231008.docx",
        path="/workspace/项目与业务/日慈-项目资助申请书-20231008.docx",
        excerpt="广东省日慈公益基金会，关注儿童青少年心理健康与心理教育。",
    )
    _insert_v2_document(
        db,
        v2_id="v2_ready",
        client_id=client_id,
        document_id="doc_ready",
        path="/workspace/项目与业务/日慈-项目资助申请书-20231008.docx",
        file_name="日慈-项目资助申请书-20231008.docx",
        preview_text="广东省日慈公益基金会，关注儿童青少年心理健康与心理教育。",
        parse_status="ready",
    )

    _insert_document(
        db,
        document_id="doc_support",
        client_id=client_id,
        title="日慈基金会业务介绍.md",
        path="/workspace/_imports/imp_x/日慈基金会业务介绍.md",
        excerpt="形成可复制的心理教育路径。",
    )
    _insert_document(
        db,
        document_id="doc_unindexed",
        client_id=client_id,
        title="心灵魔法学院项目__DUP1_日慈_20260216.pdf",
        path="/workspace/项目与业务/心灵魔法学院项目__DUP1_日慈_20260216.pdf",
        excerpt="乡村儿童青少年心理健康发展的教育公益项目。",
    )
    _insert_document(
        db,
        document_id="doc_failed",
        client_id=client_id,
        title="日慈战略结构 2_日慈_20260211.pdf",
        path="/workspace/组织与战略/日慈战略结构 2_日慈_20260211.pdf",
        excerpt="战略升级三大飞轮与第二曲线。",
    )
    _insert_v2_document(
        db,
        v2_id="v2_failed",
        client_id=client_id,
        document_id="doc_failed",
        path="/workspace/组织与战略/日慈战略结构 2_日慈_20260211.pdf",
        file_name="日慈战略结构 2_日慈_20260211.pdf",
        preview_text="战略升级三大飞轮与第二曲线。",
        parse_status="failed",
        visible_category="组织与战略",
    )

    focus_frame = build_question_focus_frame(
        prompt="介绍日慈基金会",
        route_decision=RouteDecisionRecord(intent="intro_profile", routeMode="raw_doc_drilldown", retrievalMode="hybrid"),
        page_context=PageContextPackRecord(page="workspace_chat", scopeType="client", scopeId=client_id, clientId=client_id, intent="intro_profile"),
    )
    evidence_items = [
        EvidenceItem(
            id="ev_ready",
            title="日慈-项目资助申请书-20231008.docx",
            excerpt="广东省日慈公益基金会，关注儿童青少年心理健康与心理教育。",
            sourceType="knowledge_chunk",
            documentId="doc_ready",
            path="/workspace/项目与业务/日慈-项目资助申请书-20231008.docx",
            retrievalStage="raw_chunk",
        )
    ]
    audit = build_source_reachability_audit(
        db,
        client_id=client_id,
        focus_frame=focus_frame,
        evidence_items=evidence_items,
        selected_evidence=evidence_items,
    )

    assert audit["indexedPrimarySources"]
    assert audit["reachableSupportSources"]
    assert audit["unreachableLocalSources"]
    assert audit["priorityParseFailures"]


def test_kernel_diagnostic_exposes_question_focus_and_reachability(tmp_path: Path, monkeypatch):
    db = Database(tmp_path / "kernel_audit.db")
    client_id = "client_kernel_p211"
    _insert_client(db, client_id)

    fake_context = PageContextPackRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId=client_id,
        clientId=client_id,
        intent="intro_profile",
        rawEvidence=[
            {
                "id": "raw1",
                "title": "日慈-项目资助申请书-20231008",
                "excerpt": "广东省日慈公益基金会，关注儿童青少年心理健康与心理教育。",
                "sourceType": "knowledge_chunk",
                "sectionLabel": "正文",
                "sourceStage": "raw_chunk",
            },
            {
                "id": "raw2",
                "title": "日慈基金会-繁星计划一季度沟通会议纪要",
                "excerpt": "推进品牌协同与路演筹备。",
                "sourceType": "meeting_note",
                "sourceStage": "state_pool",
            },
        ],
    )

    monkeypatch.setattr(kernel, "_build_page_context", lambda *_args, **_kwargs: fake_context.model_copy(deep=True))
    monkeypatch.setattr(
        kernel,
        "get_retrieval_model_settings",
        lambda _db: RetrievalModelSettingsRecord(updatedAt="", routerEnabled=False),
    )
    monkeypatch.setattr(
        kernel,
        "_route_with_settings",
        lambda *_args, **_kwargs: RouteDecisionRecord(
            intent="intro_profile",
            routeMode="raw_doc_drilldown",
            dataSources=["raw_docs"],
            retrievalMode="hybrid",
            shouldUseRawEvidence=True,
            rerankNeeded=True,
            routerSource="rules",
        ),
    )

    request = DataCenterRequestRecord(
        scope={
            "page": "workspace_chat",
            "scopeType": "client",
            "scopeId": client_id,
            "clientId": client_id,
        },
        prompt="介绍日慈基金会",
        mode="diagnostic",
        shadow=False,
    )
    result = kernel.resolve_data_center_kernel(db, data_dir=tmp_path, request=request, ai_service=None)
    assert result.debug.get("questionFocusFrame")
    assert "selectedEvidenceRoles" in result.debug
    assert "sourceReachability" in result.debug
    assert "evidenceDecisionTrace" in result.debug
