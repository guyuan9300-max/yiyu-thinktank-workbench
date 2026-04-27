from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_get_local_input_memory_includes_feishu_callback_fields() -> None:
    response = client.get(
        "/api/v1/local-input-memory",
        headers={"Origin": "http://127.0.0.1:4173"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["feishuIntegration"]["callbackMode"] == "cloud_relay"
    assert payload["feishuIntegration"]["customCallbackUrl"] == ""
