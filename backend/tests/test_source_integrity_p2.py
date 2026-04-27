from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.services.source_integrity import build_source_integrity_report


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def test_source_integrity_endpoint(tmp_path: Path):
    client = make_client(tmp_path)
    response = client.get("/api/v1/system/source-integrity")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "runningBackendRoot" in payload
    assert "runningHash" in payload
    assert "match" in payload
    assert "buildVersion" in payload
    assert "runtimeMode" in payload


def test_source_integrity_with_workspace_hint(tmp_path: Path):
    client = make_client(tmp_path)
    workspace_backend = str(Path(__file__).resolve().parents[1])
    response = client.get(
        "/api/v1/system/source-integrity",
        params={"workspaceBackendRoot": workspace_backend},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["workspaceBackendRoot"] == workspace_backend
    assert "workspaceHash" in payload
    assert payload["match"] is True


def test_source_integrity_report_without_workspace_root_returns_unavailable():
    running_backend = Path(__file__).resolve().parents[1]
    report = build_source_integrity_report(
        running_backend_root=running_backend,
        expected_workspace_root=None,
        build_version="2026.04.22-test",
        git_commit="deadbeef",
        runtime_mode="packaged",
    )
    assert report["match"] is None
    assert report["workspaceBackendRoot"] is None


def test_source_integrity_accepts_frontend_build_metadata(tmp_path: Path):
    client = make_client(tmp_path)
    response = client.get(
        "/api/v1/system/source-integrity",
        params={
            "frontendBuildVersion": "2026.04.21-ui",
            "frontendGitCommit": "frontend-sha",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["frontendBuildVersion"] == "2026.04.21-ui"
    assert payload["frontendGitCommit"] == "frontend-sha"
