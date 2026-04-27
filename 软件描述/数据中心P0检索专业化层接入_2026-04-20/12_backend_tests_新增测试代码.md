# backend/tests/test_retrieval_model_settings_p0.py

```python
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_client(client: TestClient, name: str = "retrieval-settings-test") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "retrieval settings test",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_retrieval_settings_default_and_health(tmp_path: Path):
    client = make_client(tmp_path)
    settings_resp = client.get("/api/v1/retrieval/settings")
    assert settings_resp.status_code == 200, settings_resp.text
    settings = settings_resp.json()
    assert settings["routerEnabled"] is False
    assert settings["shadowMode"] is True
    assert settings["embeddingProvider"] in {"local_fastembed", "hash_fallback", "doubao"}

    health_resp = client.get("/api/v1/retrieval/health")
    assert health_resp.status_code == 200, health_resp.text
    health = health_resp.json()
    assert "embedding" in health
    assert "router" in health
    assert "rerank" in health
    assert "shadowMode" in health


def test_update_retrieval_settings_marks_signature_stale(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client(client, "stale-signature-client")
    db = client.app.state.app_state.db
    db.set_setting(f"knowledge.active_embedding_signature:{client_id}", "local_fastembed:BAAI/bge-small-zh-v1.5:256")

    update_resp = client.post(
        "/api/v1/retrieval/settings",
        json={
            "embeddingProvider": "doubao",
            "embeddingModel": "doubao-embedding-large",
            "embeddingDimension": 1024,
            "embeddingMode": "doubao",
            "routerEnabled": True,
            "routerProvider": "doubao",
            "routerModel": "doubao-smart-router",
            "rerankEnabled": True,
            "rerankProvider": "rules",
            "shadowMode": True,
        },
    )
    assert update_resp.status_code == 200, update_resp.text
    payload = update_resp.json()
    assert payload["embeddingProvider"] == "doubao"
    assert payload["embeddingDimension"] == 1024
    assert payload["routerEnabled"] is True
    assert payload["shadowMode"] is True

    stale_value = db.get_setting(f"knowledge.active_embedding_signature:{client_id}", "")
    assert stale_value == ""

    health_resp = client.get("/api/v1/retrieval/health")
    assert health_resp.status_code == 200, health_resp.text
    health = health_resp.json()
    assert health["embedding"]["provider"] == "doubao"
    assert health["embedding"]["ready"] in {True, False}
```

---

# backend/tests/test_embedding_provider_p0.py

```python
from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import RetrievalModelSettingsRecord
from app.services.embedding_provider import build_embedding_provider


def test_local_fastembed_provider_or_hash_fallback_is_safe():
    settings = RetrievalModelSettingsRecord(
        embeddingProvider="local_fastembed",
        embeddingModel="BAAI/bge-small-zh-v1.5",
        embeddingDimension=256,
        embeddingMode="local",
        routerEnabled=False,
        routerProvider="rules",
        routerModel="",
        rerankEnabled=False,
        rerankProvider="rules",
        shadowMode=True,
        updatedAt="",
    )
    provider = build_embedding_provider(settings, ai_service=None)
    vectors, meta = provider.embed_texts(["你好，向量检索", "P0 fallback check"])
    assert len(vectors) == 2
    assert meta.dimension == 256
    assert meta.provider in {"local_fastembed", "hash_fallback"}


def test_doubao_provider_without_key_falls_back_safely():
    settings = RetrievalModelSettingsRecord(
        embeddingProvider="doubao",
        embeddingModel="doubao-embedding-large",
        embeddingDimension=1024,
        embeddingMode="doubao",
        routerEnabled=False,
        routerProvider="rules",
        routerModel="",
        rerankEnabled=False,
        rerankProvider="rules",
        shadowMode=True,
        updatedAt="",
    )
    provider = build_embedding_provider(settings, ai_service=None)
    vectors, meta = provider.embed_texts(["没有 key 时也不能崩溃"])
    assert len(vectors) == 1
    assert meta.provider in {"local_fastembed", "hash_fallback"}
    assert meta.fallbackUsed is True
    assert "doubao_api_key_missing" in str(meta.error or "")
```

---

# backend/tests/test_query_router_p0.py

```python
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.models import ContextQualityRecord, PageContextPackRecord, RetrievalModelSettingsRecord
from app.services.query_router import route_page_query


def build_context_pack(intent: str = "general", quality: str = "weak") -> PageContextPackRecord:
    return PageContextPackRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId="client_router",
        clientId="client_router",
        intent=intent,  # type: ignore[arg-type]
        quality=ContextQualityRecord(contextQuality=quality),  # type: ignore[arg-type]
    )


def test_official_registry_rule_guard(tmp_path: Path):
    db = Database(tmp_path / "router.db")
    decision = route_page_query(
        db,
        page="workspace_chat",
        prompt="系统里已批准的正式判断有哪些？",
        client_id="client_router",
        page_context=build_context_pack(intent="official_judgment_registry", quality="strong"),
        settings=RetrievalModelSettingsRecord(updatedAt=""),
        ai_service=None,
    )
    assert decision.intent == "official_judgment_registry"
    assert decision.judgmentQueryMode == "registry_only"
    assert decision.retrievalMode == "state_only"
    assert decision.shouldUseRawEvidence is False


def test_intro_query_forces_raw_drilldown(tmp_path: Path):
    db = Database(tmp_path / "router_intro.db")
    decision = route_page_query(
        db,
        page="workspace_chat",
        prompt="请介绍一下这个客户",
        client_id="client_router",
        page_context=build_context_pack(intent="intro_profile", quality="strong"),
        settings=RetrievalModelSettingsRecord(updatedAt=""),
        ai_service=None,
    )
    assert decision.intent in {"intro_profile", "project_intro"}
    assert decision.retrievalMode == "raw_only"
    assert decision.shouldUseRawEvidence is True


def test_complex_query_produces_hybrid_plan(tmp_path: Path):
    db = Database(tmp_path / "router_complex.db")
    decision = route_page_query(
        db,
        page="workspace_chat",
        prompt="这个客户最近推进到哪了，上次会议说了什么，下一步应该谁做？",
        client_id="client_router",
        page_context=build_context_pack(intent="general", quality="weak"),
        settings=RetrievalModelSettingsRecord(updatedAt=""),
        ai_service=None,
    )
    assert decision.retrievalMode in {"hybrid", "raw_only"}
    assert len(decision.queryPlan) >= 2
    assert any(source in decision.dataSources for source in ("state_pool", "meetings", "tasks"))


def test_smart_router_invalid_output_falls_back_to_rules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = Database(tmp_path / "router_fallback.db")
    settings = RetrievalModelSettingsRecord(
        embeddingProvider="local_fastembed",
        embeddingModel="BAAI/bge-small-zh-v1.5",
        embeddingDimension=256,
        embeddingMode="local",
        routerEnabled=True,
        routerProvider="doubao",
        routerModel="doubao-smart-router",
        rerankEnabled=False,
        rerankProvider="rules",
        shadowMode=True,
        updatedAt="",
    )

    import app.services.query_router as query_router

    monkeypatch.setattr(query_router, "_invoke_doubao_router_model", lambda **_kwargs: None)
    decision = route_page_query(
        db,
        page="workspace_chat",
        prompt="这个项目接下来要怎么判断优先级？请给路径",
        client_id="client_router",
        page_context=build_context_pack(intent="general", quality="none"),
        settings=settings,
        ai_service=object(),
    )
    assert decision.routerSource == "fallback"
    assert decision.fallbackUsed is True
    assert decision.routeReason
```

---

# backend/tests/test_workspace_chat_router_shadow_p0.py

```python
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.main import create_app
from app.models import AiStructuredResponse
from app.services.knowledge_v2 import CitationMatch, RetrievalBundle


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str = "shadow-chat-client") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "shadow chat test",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def build_retrieval_bundle() -> RetrievalBundle:
    citations = [
        CitationMatch(
            knowledge_document_id="kd_shadow_1",
            chunk_id="chunk_shadow_1",
            title="shadow 资料 1",
            excerpt="该客户当前推进到执行协调阶段，下一步需要确认负责人。",
            score=0.92,
            coverage=0.83,
            section_label="正文",
            source_stage="raw_chunk",
            drillthrough_used=True,
            matched_terms=["推进", "负责人"],
            path="/tmp/shadow_1.md",
        ),
        CitationMatch(
            knowledge_document_id="kd_shadow_2",
            chunk_id="chunk_shadow_2",
            title="shadow 资料 2",
            excerpt="最近会议纪要要求先补齐证据，再推进周计划。",
            score=0.88,
            coverage=0.83,
            section_label="会议纪要",
            source_stage="raw_chunk",
            drillthrough_used=True,
            matched_terms=["会议", "证据"],
            path="/tmp/shadow_2.md",
        ),
    ]
    return RetrievalBundle(
        citations=citations,
        coverage=0.83,
        retrieval_summary={
            "masterHitCount": 2,
            "surrogateHitCount": 2,
            "rawChunkHitCount": 2,
        },
        context_text="",
        matched_terms=["推进", "会议"],
        failure_reason=None,
    )


def test_shadow_mode_keeps_answer_and_records_shadow_run(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_client_record(client)

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", lambda *_args, **_kwargs: build_retrieval_bundle())
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_chat_response",
        lambda *_args, **_kwargs: AiStructuredResponse(
            content="当前推进已进入执行协调阶段，建议先确认负责人与截止时间。",
            judgment="回答来自状态池与原文证据混合路径。",
            analysis="已引用会议纪要与任务资料。",
            actions="先补齐负责人，再确认时间线。",
            timeline="本周内完成对齐。",
        ),
    )

    settings_resp = client.post(
        "/api/v1/retrieval/settings",
        json={
            "embeddingProvider": "local_fastembed",
            "embeddingModel": "BAAI/bge-small-zh-v1.5",
            "embeddingDimension": 256,
            "embeddingMode": "local",
            "routerEnabled": True,
            "routerProvider": "rules",
            "routerModel": "",
            "rerankEnabled": True,
            "rerankProvider": "rules",
            "shadowMode": True,
        },
    )
    assert settings_resp.status_code == 200, settings_resp.text

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "这个客户现在推进到哪了，上次会议说了什么？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert "执行协调阶段" in payload["content"]
    summary = payload["retrievalSummary"]
    assert summary["shadowMode"] is True
    assert "routeDecision" in summary
    assert "retrievalTrace" in summary
    assert "answerIntent" in summary
    assert "retrievalDecisionReason" in summary
    assert "embeddingSignature" in summary

    shadow_runs_resp = client.get("/api/v1/retrieval/shadow-runs", params={"clientId": client_id})
    assert shadow_runs_resp.status_code == 200, shadow_runs_resp.text
    runs = shadow_runs_resp.json()
    assert runs
    assert runs[0]["clientId"] == client_id
    assert "baselineSummary" in runs[0]
    assert "candidateSummary" in runs[0]
```

---

# backend/tests/test_retrieval_shadow_eval_p0.py

```python
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.services.retrieval_shadow import create_retrieval_shadow_run
from scripts.eval_retrieval_p0 import run_eval


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def test_eval_fixture_contains_minimum_cases():
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "retrieval_eval_cases.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    assert len(payload) >= 20


def test_eval_script_returns_metrics():
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "retrieval_eval_cases.json"
    report = run_eval(fixtures=fixture_path, mode="baseline", client_id="eval_client")
    assert report["caseCount"] >= 20
    assert 0.0 <= float(report["intentAccuracy"]) <= 1.0
    assert 0.0 <= float(report["routeAccuracy"]) <= 1.0
    assert "registryProtectionPass" in report
    assert "avgLatencyMs" in report


def test_retrieval_shadow_summary_endpoint(tmp_path: Path):
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    create_retrieval_shadow_run(
        db,
        client_id="client_shadow_eval",
        page="workspace_chat",
        prompt="测试 shadow 评测",
        baseline_summary={"timing": {"totalMs": 300}},
        candidate_summary={"timing": {"totalMs": 420}},
        overlap_rate=0.6,
        candidate_better=True,
        failure_reason=None,
    )

    response = client.get("/api/v1/retrieval/shadow-summary", params={"clientId": "client_shadow_eval"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] >= 1
    assert "candidateBetterRate" in payload
    assert "overlapRateAvg" in payload
    assert "latencyDeltaMsAvg" in payload
```

---

# backend/tests/fixtures/retrieval_eval_cases.json

```json
[
  {
    "id": "client_intro_001",
    "page": "workspace_chat",
    "prompt": "请介绍一下这个客户",
    "expectedIntent": "intro_profile",
    "expectedRetrievalMode": "raw_only",
    "mustUseRawEvidence": true
  },
  {
    "id": "official_registry_001",
    "page": "workspace_chat",
    "prompt": "系统里已批准的正式判断有哪些？",
    "expectedIntent": "official_judgment_registry",
    "expectedRetrievalMode": "state_only",
    "expectedJudgmentQueryMode": "registry_only",
    "mustUseRawEvidence": false
  },
  {
    "id": "task_next_001",
    "page": "task_ai",
    "prompt": "这条任务下一步应该做什么？",
    "expectedIntent": "task_next_action",
    "expectedRetrievalMode": "hybrid",
    "mustUseTaskContext": true
  },
  {
    "id": "status_001",
    "page": "workspace_chat",
    "prompt": "这个客户现在推进到哪了？",
    "expectedIntent": "status_progress",
    "expectedRetrievalMode": "hybrid",
    "mustUseRawEvidence": false
  },
  {
    "id": "evidence_001",
    "page": "workspace_chat",
    "prompt": "这条结论的证据和原文出处是什么？",
    "expectedIntent": "evidence_question",
    "expectedRetrievalMode": "raw_only",
    "mustUseRawEvidence": true
  },
  {
    "id": "meeting_001",
    "page": "workspace_chat",
    "prompt": "最新会议纪要说了什么？",
    "expectedIntent": "meeting_summary",
    "expectedRetrievalMode": "hybrid",
    "mustUseRawEvidence": true
  },
  {
    "id": "next_actions_001",
    "page": "workspace_chat",
    "prompt": "接下来最重要的事情是什么？",
    "expectedIntent": "next_actions",
    "expectedRetrievalMode": "hybrid"
  },
  {
    "id": "identity_001",
    "page": "workspace_chat",
    "prompt": "这个项目的负责人是谁？",
    "expectedIntent": "evidence_question",
    "expectedRetrievalMode": "hybrid",
    "mustUseRawEvidence": true
  },
  {
    "id": "project_intro_001",
    "page": "workspace_chat",
    "prompt": "请简要介绍这个项目背景",
    "expectedIntent": "project_intro",
    "expectedRetrievalMode": "raw_only",
    "mustUseRawEvidence": true
  },
  {
    "id": "task_context_001",
    "page": "task_detail",
    "prompt": "这条任务为什么重要？",
    "expectedIntent": "task_context",
    "expectedRetrievalMode": "hybrid",
    "mustUseTaskContext": true
  },
  {
    "id": "status_risk_001",
    "page": "workspace_chat",
    "prompt": "这个客户本周有什么风险和卡点？",
    "expectedIntent": "status_progress",
    "expectedRetrievalMode": "hybrid"
  },
  {
    "id": "evidence_002",
    "page": "workspace_chat",
    "prompt": "请引用原文说明这条判断",
    "expectedIntent": "evidence_question",
    "expectedRetrievalMode": "raw_only",
    "mustUseRawEvidence": true
  },
  {
    "id": "intro_002",
    "page": "workspace_chat",
    "prompt": "这个机构是做什么的？",
    "expectedIntent": "intro_profile",
    "expectedRetrievalMode": "raw_only",
    "mustUseRawEvidence": true
  },
  {
    "id": "official_registry_002",
    "page": "workspace_chat",
    "prompt": "请列出系统内已批准判断",
    "expectedIntent": "official_judgment_registry",
    "expectedRetrievalMode": "state_only",
    "expectedJudgmentQueryMode": "registry_only",
    "mustUseRawEvidence": false
  },
  {
    "id": "meeting_002",
    "page": "workspace_chat",
    "prompt": "上次会议决定了哪些行动项？",
    "expectedIntent": "meeting_summary",
    "expectedRetrievalMode": "hybrid",
    "mustUseRawEvidence": true
  },
  {
    "id": "task_next_002",
    "page": "task_ai",
    "prompt": "这条任务下一步怎么推进？",
    "expectedIntent": "task_next_action",
    "expectedRetrievalMode": "hybrid",
    "mustUseTaskContext": true
  },
  {
    "id": "general_complex_001",
    "page": "workspace_chat",
    "prompt": "这个客户最近推进到哪了，上次会议说了什么，下一步应该谁做？",
    "expectedIntent": "meeting_summary",
    "expectedRetrievalMode": "hybrid",
    "mustUseRawEvidence": true
  },
  {
    "id": "status_002",
    "page": "workspace_chat",
    "prompt": "当前状态和下一步重点是什么？",
    "expectedIntent": "next_actions",
    "expectedRetrievalMode": "hybrid"
  },
  {
    "id": "evidence_003",
    "page": "workspace_chat",
    "prompt": "这份资料对客户有什么影响，请给依据",
    "expectedIntent": "evidence_question",
    "expectedRetrievalMode": "raw_only",
    "mustUseRawEvidence": true
  },
  {
    "id": "task_missing_001",
    "page": "task_detail",
    "prompt": "这条任务缺什么背景？",
    "expectedIntent": "task_context",
    "expectedRetrievalMode": "hybrid",
    "mustUseTaskContext": true
  }
]
```
