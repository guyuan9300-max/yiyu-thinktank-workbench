from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import RetrievalModelSettingsRecord, RouteDecisionRecord
from app.services.local_semantic_router import route_by_local_semantic


class DummyProvider:
    def embed_texts(self, texts):
        vectors = []
        for text in texts:
            if "业务" in text:
                vectors.append([1.0, 0.0])
            elif "战略" in text:
                vectors.append([0.0, 1.0])
            else:
                vectors.append([0.1, 0.1])
        return vectors, type("Meta", (), {"provider": "dummy", "model": "dummy", "dimension": 2, "signature": "dummy", "fallbackUsed": False, "error": None})()


def test_local_semantic_router_matches_business_profile():
    settings = RetrievalModelSettingsRecord(routerConfidenceThreshold=0.2, updatedAt="")
    base = RouteDecisionRecord(intent="general", routeMode="state_first", dataSources=["state_pool"], retrievalMode="hybrid")
    decision = route_by_local_semantic(
        prompt="CFFC 核心业务是什么？",
        base_decision=base,
        settings=settings,
        embedding_provider=DummyProvider(),
    )
    assert decision.intent == "business_profile"
    assert decision.routerSource == "local_semantic"


def test_local_semantic_router_respects_protected_intent():
    settings = RetrievalModelSettingsRecord(routerConfidenceThreshold=0.2, updatedAt="")
    base = RouteDecisionRecord(intent="official_judgment_registry", routeMode="registry_only", dataSources=["judgment_registry"], retrievalMode="state_only")
    decision = route_by_local_semantic(
        prompt="这家机构核心业务是什么？",
        base_decision=base,
        settings=settings,
        embedding_provider=DummyProvider(),
    )
    assert decision.intent == "official_judgment_registry"
