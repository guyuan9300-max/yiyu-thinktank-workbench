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
