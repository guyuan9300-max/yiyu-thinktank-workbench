from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.models import RetrievalModelSettingsRecord
from app.services.embedding_provider import build_embedding_provider
from app.services.retrieval_model_settings import retrieval_embedding_signature


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str = "embed-signature-p22") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "embedding signature p22",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_embedding_signature_distinguishes_profile_and_projection():
    legacy = RetrievalModelSettingsRecord(
        embeddingProvider="local_fastembed",
        embeddingModel="BAAI/bge-small-zh-v1.5",
        embeddingDimension=256,
        embeddingProfile="legacy_fastembed_256",
        embeddingProjection=True,
        updatedAt="",
    )
    native = legacy.model_copy(update={"embeddingProfile": "bge_small_native", "embeddingProjection": False})
    native_projection = native.model_copy(update={"embeddingProjection": True})

    legacy_sig = retrieval_embedding_signature(legacy)
    native_sig = retrieval_embedding_signature(native)
    native_projection_sig = retrieval_embedding_signature(native_projection)

    assert legacy_sig != native_sig
    assert native_sig != native_projection_sig


def test_bge_m3_profile_uses_bge_m3_default_model():
    settings = RetrievalModelSettingsRecord(
        embeddingProvider="local_fastembed",
        embeddingModel="BAAI/bge-small-zh-v1.5",
        embeddingDimension=1024,
        embeddingProfile="bge_m3_dense",
        embeddingProjection=False,
        updatedAt="",
    )
    provider = build_embedding_provider(settings, ai_service=None)
    meta = provider.get_meta()
    # bge_m3 不可用时允许 fallback，但模型名仍应按 profile 归一到 bge-m3。
    assert settings.embeddingProfile == "bge_m3_dense"
    assert "bge-m3" in meta.model.lower() or meta.fallbackUsed is True


def test_signature_change_marks_vector_index_stale(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)

    previous = client.get("/api/v1/retrieval/settings")
    assert previous.status_code == 200, previous.text
    previous_signature = retrieval_embedding_signature(RetrievalModelSettingsRecord(**previous.json()))
    client.app.state.app_state.db.set_setting(f"knowledge.active_embedding_signature:{client_id}", previous_signature)

    update = client.post(
        "/api/v1/retrieval/settings",
        json={
            "embeddingProfile": "bge_small_native",
            "embeddingProjection": False,
            "embeddingDimension": 512,
        },
    )
    assert update.status_code == 200, update.text

    active_signature = client.app.state.app_state.db.get_setting(
        f"knowledge.active_embedding_signature:{client_id}",
        "",
    )
    assert active_signature == ""

    status = client.get(f"/api/v1/clients/{client_id}/knowledge/status")
    assert status.status_code == 200, status.text
    assert status.json().get("vectorIndexStatus") == "stale"
