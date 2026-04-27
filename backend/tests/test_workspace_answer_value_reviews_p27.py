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


def create_client_record(client: TestClient, name: str = "workspace-value-review-p27") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "workspace value review p27",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_workspace_answer_value_reviews_and_summary_p27(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)

    review_1 = client.post(
        "/api/v1/workspace-answer-value-reviews",
        json={
            "clientId": client_id,
            "messageId": "msg_review_1",
            "prompt": "客户核心业务是什么？",
            "answerMode": "grounded_answer",
            "userVisibleQualityStatus": "ready",
            "shouldShowRetryBanner": False,
            "usableAnswer": True,
            "reviewerNote": "可直接使用",
            "manualBaselineMinutes": 20,
            "dataCenterReviewMinutes": 8,
        },
    )
    assert review_1.status_code == 200, review_1.text

    review_2 = client.post(
        "/api/v1/workspace-answer-value-reviews",
        json={
            "clientId": client_id,
            "messageId": "msg_review_2",
            "prompt": "最新战略方向是什么？",
            "answerMode": "grounded_fallback",
            "userVisibleQualityStatus": "needs_retry",
            "shouldShowRetryBanner": True,
            "usableAnswer": False,
            "reviewerNote": "需要补资料",
            "manualBaselineMinutes": 18,
            "dataCenterReviewMinutes": 14,
        },
    )
    assert review_2.status_code == 200, review_2.text

    listed = client.get(f"/api/v1/workspace-answer-value-reviews?clientId={client_id}&limit=10")
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert len(rows) >= 2

    summary = client.get(f"/api/v1/workspace-answer-value-summary?clientId={client_id}")
    assert summary.status_code == 200, summary.text
    summary_payload = summary.json()
    assert summary_payload.get("reviewCount") >= 2
    assert float(summary_payload.get("usableAnswerRate") or 0.0) > 0.0
    assert float(summary_payload.get("retryBannerRate") or 0.0) > 0.0
    assert float(summary_payload.get("estimatedTimeSavedRate") or 0.0) >= 0.0
