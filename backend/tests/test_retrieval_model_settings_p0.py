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
