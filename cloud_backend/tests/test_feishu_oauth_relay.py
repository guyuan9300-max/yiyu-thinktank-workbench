from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[2]))

from services.feishu_oauth_relay.app import create_app


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def test_feishu_oauth_relay_register_callback_claim_once(tmp_path, monkeypatch):
    monkeypatch.setenv("YIYU_FEISHU_OAUTH_RELAY_DB", str(tmp_path / "relay.sqlite3"))
    client = TestClient(create_app())
    state = "state_demo_token_123456"
    claim_secret = "claim_secret_demo_123456"

    register = client.post(
        "/feishu/member/sessions",
        json={
            "stateHash": _hash(state),
            "claimSecretHash": _hash(claim_secret),
            "expiresAt": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        },
    )
    assert register.status_code == 200, register.text
    assert register.json()["status"] == "registered"

    callback = client.get("/feishu/member/callback", params={"state": state, "code": "code_demo"})
    assert callback.status_code == 200, callback.text
    assert "授权已收到" in callback.text

    claim = client.post("/feishu/member/code/claim", json={"state": state, "claimSecret": claim_secret})
    assert claim.status_code == 200, claim.text
    assert claim.json()["status"] == "authorized"
    assert claim.json()["code"] == "code_demo"

    second_claim = client.post("/feishu/member/code/claim", json={"state": state, "claimSecret": claim_secret})
    assert second_claim.status_code == 404


def test_feishu_oauth_relay_rejects_wrong_claim_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("YIYU_FEISHU_OAUTH_RELAY_DB", str(tmp_path / "relay.sqlite3"))
    client = TestClient(create_app())
    state = "state_demo_token_abcdef"
    claim_secret = "claim_secret_demo_abcdef"

    client.post(
        "/feishu/member/sessions",
        json={
            "stateHash": _hash(state),
            "claimSecretHash": _hash(claim_secret),
            "expiresAt": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        },
    )
    client.get("/feishu/member/callback", params={"state": state, "code": "code_demo"})

    claim = client.post("/feishu/member/code/claim", json={"state": state, "claimSecret": "wrong_secret_demo"})
    assert claim.status_code == 403


def test_feishu_oauth_relay_expires_sessions(tmp_path, monkeypatch):
    monkeypatch.setenv("YIYU_FEISHU_OAUTH_RELAY_DB", str(tmp_path / "relay.sqlite3"))
    client = TestClient(create_app())
    state = "state_demo_token_expired"
    claim_secret = "claim_secret_demo_expired"

    register = client.post(
        "/feishu/member/sessions",
        json={
            "stateHash": _hash(state),
            "claimSecretHash": _hash(claim_secret),
            "expiresAt": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        },
    )
    assert register.status_code == 400
