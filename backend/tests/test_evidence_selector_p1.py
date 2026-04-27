from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import EvidenceItem, PageContextPackRecord, RouteDecisionRecord
from app.services.evidence_selector import select_answer_evidence


def test_business_profile_selector_downranks_template_noise():
    evidence = [
        EvidenceItem(id="1", title="PPT 模板页", excerpt="模板目录", sourceType="knowledge_chunk", score=0.95),
        EvidenceItem(id="2", title="CFFC 核心业务介绍", excerpt="核心业务包括资源支持与平台建设。", sourceType="knowledge_chunk", score=0.75),
    ]
    selected = select_answer_evidence(
        prompt="CFFC 核心业务是什么？",
        intent="business_profile",
        route_decision=RouteDecisionRecord(intent="business_profile", routeMode="raw_doc_drilldown", dataSources=["raw_docs"], retrievalMode="hybrid"),
        evidence=evidence,
        page_context=PageContextPackRecord(page="workspace_chat", scopeType="client", scopeId="c1", intent="business_profile"),
    )
    assert selected
    assert selected[0].title == "CFFC 核心业务介绍"
