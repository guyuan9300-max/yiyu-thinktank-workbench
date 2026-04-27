from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.diagnosis_engines import (
    BettaFishAdapter,
    DiagnosisEngineEndpoint,
    DiagnosisEngineRequest,
    MiroFishAdapter,
    collect_diagnosis_engine_health,
)


def test_request_payload_is_trimmed() -> None:
    payload = DiagnosisEngineRequest(
        scene="pr",
        audience_type="public",
        content="x" * 80,
        knowledge_refs=[{"title": "A" * 120, "summary": "B" * 400}] * 8,
        case_refs=[{"title": "Case", "summary": "C" * 400}] * 8,
    )

    normalized = payload.to_payload(max_payload_chars=20, max_context_items=2)

    assert normalized["content"].endswith("...")
    assert len(normalized["knowledge_refs"]) == 2
    assert len(normalized["case_refs"]) == 2
    assert normalized["knowledge_refs"][0]["title"].endswith("...")


def test_healthcheck_reports_disabled_endpoint() -> None:
    endpoint = DiagnosisEngineEndpoint(
        engine_key="bettafish",
        enabled=False,
        base_url="http://127.0.0.1:18101",
        analyze_path="/analyze",
        health_path="/health",
    )

    report = BettaFishAdapter(endpoint).healthcheck()

    assert report.status == "disabled"
    assert report.reachable is False


def test_bettafish_analysis_extracts_nested_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(
            200,
            json={
                "data": {
                    "emotion": "skeptical",
                    "credibility": "medium",
                    "risk_points": ["语气过强", "证据不足"],
                    "misunderstanding_points": ["公众可能误以为机构在推责"],
                }
            },
        )

    transport = httpx.MockTransport(handler)
    endpoint = DiagnosisEngineEndpoint(
        engine_key="bettafish",
        enabled=True,
        base_url="http://engine.local",
        analyze_path="/analyze",
        health_path="/health",
    )
    adapter = BettaFishAdapter(endpoint, transport=transport)

    result = adapter.analyze(
        DiagnosisEngineRequest(scene="fundraising", audience_type="donor", content="test"),
    )

    assert result.emotion == "skeptical"
    assert result.credibility == "medium"
    assert result.risk_points == ["语气过强", "证据不足"]
    assert result.misunderstanding_points == ["公众可能误以为机构在推责"]


def test_mirofish_simulation_extracts_audiences_and_scenarios() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(
            200,
            json={
                "result": {
                    "summary": "短回应会暂时止血，但证据不足时仍有二次发酵风险。",
                    "audiences": [
                        {"role": "媒体", "reaction": "关注时间线是否完整", "risk_level": "high"},
                    ],
                    "scenarios": [
                        {"strategy": "快速短回应", "outcome": "能暂时降温，但无法彻底止损"},
                    ],
                }
            },
        )

    transport = httpx.MockTransport(handler)
    endpoint = DiagnosisEngineEndpoint(
        engine_key="mirofish",
        enabled=True,
        base_url="http://engine.local",
        analyze_path="/simulate",
        health_path="/health",
    )
    adapter = MiroFishAdapter(endpoint, transport=transport)

    result = adapter.simulate(
        DiagnosisEngineRequest(scene="pr", audience_type="media", content="test"),
    )

    assert result.summary == "短回应会暂时止血，但证据不足时仍有二次发酵风险。"
    assert result.audiences == [{"role": "媒体", "reaction": "关注时间线是否完整", "risk_level": "high"}]
    assert result.scenarios == [{"strategy": "快速短回应", "outcome": "能暂时降温，但无法彻底止损"}]


def test_collect_health_reports_uses_current_env(monkeypatch) -> None:
    monkeypatch.setenv("YIYU_BETTAFISH_ENABLED", "false")
    monkeypatch.setenv("YIYU_MIROFISH_ENABLED", "false")

    reports = collect_diagnosis_engine_health()

    assert [item.engine_key for item in reports] == ["bettafish", "mirofish"]
    assert all(item.status == "disabled" for item in reports)
