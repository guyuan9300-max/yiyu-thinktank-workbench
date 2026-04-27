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


def test_topic_radar_kernel_lite(tmp_path: Path):
    client = make_client(tmp_path)

    radar = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "政策追踪",
            "prompt": "关注公益行业政策变化",
            "timeRange": "7_days",
            "preferredSources": [],
        },
    )
    assert radar.status_code == 200, radar.text
    radar_id = radar.json()["id"]

    candidate = client.post(
        "/api/v1/topics/candidates",
        json={
            "radarId": radar_id,
            "title": "地方心理服务支持政策",
            "summary": "本地出台新扶持措施，可能影响项目推进。",
            "source": "manual",
        },
    )
    assert candidate.status_code == 200, candidate.text
    topic_id = candidate.json()["id"]

    response = client.post(
        "/api/v1/data-center/resolve",
        json={
            "scope": {
                "page": "topic_radar",
                "scopeType": "topic",
                "scopeId": topic_id,
                "topicId": topic_id,
            },
            "prompt": "这个话题是否值得转任务？",
            "mode": "proposal",
            "includeRawEvidence": False,
            "includeActionSuggestions": True,
            "shadow": True,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["pageContext"]["page"] == "topic_radar"
    assert payload["proposalDrafts"] is not None
    assert any("external-evidence-lite" in note for note in payload["pageContext"]["boundaryNotes"])
