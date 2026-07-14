from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main as cloud_main
from app.main import DEFAULT_ORG_ID, create_app, now_iso
from app.services import client_narrative as narrative_service


FOREIGN_ORG_ID = "org_narrative_scope_foreign"


def make_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(tmp_path / "cloud-data"))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    return TestClient(create_app(), raise_server_exceptions=False)


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@yiyu-system.com", "password": "Admin123!"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def seed_foreign_organization(client: TestClient) -> None:
    timestamp = now_iso()
    client.app.state.app_state.db.execute(
        """
        INSERT INTO organizations(id, name, slug, created_at, updated_at)
        VALUES(?, '叙事越权测试组织', ?, ?, ?)
        """,
        (FOREIGN_ORG_ID, FOREIGN_ORG_ID, timestamp, timestamp),
    )


def test_regenerate_ignores_foreign_org_pending_clarifications(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with make_client(tmp_path, monkeypatch) as client:
        headers = auth_headers(client)
        state = client.app.state.app_state
        timestamp = now_iso()
        seed_foreign_organization(client)
        client_id = "client_narrative_scope_local"
        state.db.execute(
            """
            INSERT INTO clients(id, organization_id, name, type, created_at, updated_at)
            VALUES(?, ?, '本组织叙事客户', 'client', ?, ?)
            """,
            (client_id, DEFAULT_ORG_ID, timestamp, timestamp),
        )
        narrative_service.write_new_version(
            state.db,
            DEFAULT_ORG_ID,
            client_id,
            {dimension: {} for dimension in narrative_service.DIMENSIONS},
            overall_confidence=0.5,
            data_layer_gaps=[],
        )
        state.db.execute(
            """
            INSERT INTO client_narrative_clarifications(
                id, organization_id, client_id, based_on_rev, dimension, question,
                asked_by, answer, answered_by_display_name, answered_at, status,
                created_at, updated_at
            ) VALUES(
                'clarification_narrative_scope_foreign', ?, ?, 1, 'essence', '',
                'user', 'foreign organization secret', 'foreign user', ?, 'pending',
                ?, ?
            )
            """,
            (FOREIGN_ORG_ID, client_id, timestamp, timestamp, timestamp),
        )

        calls = {"regenerate": 0}

        def regenerate_spy(*args, **kwargs) -> None:
            calls["regenerate"] += 1

        monkeypatch.setattr(cloud_main.narrative_generator, "regenerate_narrative", regenerate_spy)

        response = client.post(
            f"/api/v1/clients/{client_id}/narrative/regenerate",
            headers=headers,
            json={"trigger": "manual", "force": False},
        )

        assert response.status_code == 200, response.text
        assert calls == {"regenerate": 0}
        foreign = state.db.fetchone(
            "SELECT status FROM client_narrative_clarifications WHERE id = ?",
            ("clarification_narrative_scope_foreign",),
        )
        assert foreign is not None
        assert str(foreign["status"]) == "pending"


def test_ingest_fails_closed_when_client_id_belongs_to_foreign_org(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with make_client(tmp_path, monkeypatch) as client:
        headers = auth_headers(client)
        state = client.app.state.app_state
        timestamp = now_iso()
        seed_foreign_organization(client)
        client_id = "client_narrative_scope_foreign"
        state.db.execute(
            """
            INSERT INTO clients(id, organization_id, name, type, created_at, updated_at)
            VALUES(?, ?, '外组织叙事客户', 'client', ?, ?)
            """,
            (client_id, FOREIGN_ORG_ID, timestamp, timestamp),
        )

        response = client.post(
            f"/api/v1/clients/{client_id}/narrative/ingest",
            headers=headers,
            json={
                "dimensions": {},
                "clientName": "不得覆盖的本组织客户名",
                "generator": "scope-test",
            },
        )

        assert response.status_code == 404, response.text
        assert state.db.scalar(
            "SELECT COUNT(*) FROM client_narrative_versions WHERE client_id = ?",
            (client_id,),
        ) == 0
        owner = state.db.fetchone("SELECT organization_id, name FROM clients WHERE id = ?", (client_id,))
        assert owner is not None
        assert str(owner["organization_id"]) == FOREIGN_ORG_ID
        assert str(owner["name"]) == "外组织叙事客户"
