#!/usr/bin/env python3
"""Verify fresh-install dual-organization login and switching.

Environment variables:
  YIYU_VERIFY_EMAIL
  YIYU_VERIFY_PASSWORD
  YIYU_VERIFY_YIYU_CLOUD_URL
  YIYU_VERIFY_XINGCONG_CLOUD_URL

The script uses a temporary data directory and does not create, update, or
delete business records. It only logs in, reads module summaries, and switches
between the two resulting organization workspaces.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.main import create_app  # noqa: E402


@dataclass(frozen=True)
class OrgLoginResult:
    label: str
    cloud_url: str
    organization_id: str
    organization_name: str
    user_name: str
    user_email: str


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"missing env: {name}")
    return value


def post_json(client: TestClient, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post(path, json=payload)
    if response.status_code != 200:
        raise RuntimeError(f"{path} failed: {response.status_code} {response.text[:300]}")
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"{path} returned non-object payload")
    return data


def get_json(client: TestClient, path: str) -> Any:
    response = client.get(path)
    if response.status_code != 200:
        raise RuntimeError(f"{path} failed: {response.status_code} {response.text[:300]}")
    return response.json()


def login_cloud(client: TestClient, *, label: str, cloud_url: str, email: str, password: str) -> OrgLoginResult:
    payload = {
        "identifier": email,
        "email": email,
        "password": password,
        "rememberMe": True,
        "cloudApiUrl": cloud_url,
    }
    auth_state = post_json(client, "/api/v1/auth/login", payload)
    if auth_state.get("organizationSelectionRequired"):
        candidates = auth_state.get("organizations") or []
        if not candidates:
            raise RuntimeError(f"{label}: organization selection required but no candidates returned")
        selected = candidates[0]
        auth_state = post_json(
            client,
            "/api/v1/auth/select-organization",
            {
                "organizationSelectionToken": auth_state.get("organizationSelectionToken"),
                "organizationId": selected.get("organizationId"),
                "cloudApiUrl": cloud_url,
            },
        )
    if not auth_state.get("authenticated") or not auth_state.get("user"):
        raise RuntimeError(f"{label}: login did not authenticate: {auth_state.get('message')}")
    user = auth_state["user"]
    org_id = str(user.get("organizationId") or "")
    if not org_id:
        raise RuntimeError(f"{label}: authenticated user missing organizationId")
    return OrgLoginResult(
        label=label,
        cloud_url=cloud_url,
        organization_id=org_id,
        organization_name=str(user.get("organizationName") or ""),
        user_name=str(user.get("fullName") or user.get("email") or ""),
        user_email=str(user.get("email") or ""),
    )


def workspace_for_org(client: TestClient, organization_id: str) -> dict[str, Any]:
    payload = get_json(client, "/api/v1/workspaces")
    workspaces = payload.get("workspaces", []) if isinstance(payload, dict) else []
    for workspace in workspaces:
        if str(workspace.get("organizationId") or "") == organization_id:
            return workspace
    raise RuntimeError(f"workspace not found for organizationId={organization_id}")


def activate_org(client: TestClient, result: OrgLoginResult) -> dict[str, Any]:
    workspace = workspace_for_org(client, result.organization_id)
    workspace_id = str(workspace.get("id") or "")
    if not workspace_id:
        raise RuntimeError(f"{result.label}: workspace missing id")
    post_json(client, f"/api/v1/workspaces/{workspace_id}/activate", {})
    current = get_json(client, "/api/v1/workspaces/current")
    if str(current.get("organizationId") or "") != result.organization_id:
        raise RuntimeError(f"{result.label}: active workspace organization mismatch")
    return current


def module_summary(client: TestClient) -> dict[str, Any]:
    current = get_json(client, "/api/v1/workspaces/current")
    tasks_payload = get_json(client, "/api/v1/tasks?syncMode=blocking")
    clients_payload = get_json(client, "/api/v1/clients")
    event_lines = get_json(client, "/api/v1/event-lines")
    settings_tasks = get_json(client, "/api/v1/settings/tasks")
    badges = get_json(client, "/api/v1/growth/badges")
    reviews = get_json(client, "/api/v1/reviews/history")
    try:
        intelligence = get_json(client, "/api/v1/intelligence/items?contentKind=timely_intelligence&pageSize=5")
        intelligence_count = int(intelligence.get("total") or len(intelligence.get("items") or []))
    except Exception as exc:
        intelligence_count = f"degraded: {str(exc)[:120]}"
    task_items = tasks_payload.get("tasks", []) if isinstance(tasks_payload, dict) else []
    client_items = clients_payload if isinstance(clients_payload, list) else clients_payload.get("items", [])
    event_line_items = event_lines if isinstance(event_lines, list) else []

    def sample(items: list[Any], *keys: str) -> list[str]:
        values: list[str] = []
        for item in items[:5]:
            if not isinstance(item, dict):
                continue
            value = ""
            for key in keys:
                value = str(item.get(key) or "").strip()
                if value:
                    break
            if value:
                values.append(value[:80])
        return values

    return {
        "runtimeStatus": current.get("runtimeStatus"),
        "identityState": current.get("identityState"),
        "requiresLogin": bool(current.get("requiresLogin")),
        "workspace": current.get("name"),
        "organizationId": current.get("organizationId"),
        "organizationName": current.get("organizationName"),
        "cloudInstanceId": current.get("cloudInstanceId"),
        "sessionUser": (current.get("sessionSnapshot") or {}).get("fullName") or (current.get("sessionSnapshot") or {}).get("email"),
        "clients": len(client_items),
        "clientSamples": sample(client_items, "name", "clientName", "title"),
        "tasks": len(task_items),
        "taskSamples": sample(task_items, "title", "name"),
        "eventLines": len(event_line_items),
        "eventLineSamples": sample(event_line_items, "title", "name"),
        "intelligenceItems": intelligence_count,
        "badgeCategories": len(badges.get("categories", [])),
        "reviewHistory": len(reviews.get("items", [])),
        "taskSettingsPreset": settings_tasks.get("defaultDueDatePreset"),
    }


def stable_module_summary(client: TestClient, *, attempts: int = 6, delay_seconds: float = 2.0) -> dict[str, Any]:
    previous: dict[str, Any] | None = None
    for attempt in range(1, attempts + 1):
        current = module_summary(client)
        if previous:
            stable_keys = ("clients", "tasks", "eventLines", "intelligenceItems", "reviewHistory")
            if all(previous.get(key) == current.get(key) for key in stable_keys):
                return {**current, "stabilizedAfterAttempts": attempt}
        previous = current
        if attempt < attempts:
            time.sleep(delay_seconds)
    return {**(previous or {}), "stabilizedAfterAttempts": attempts, "stabilityWarning": "core counts did not stabilize within wait window"}


def main() -> int:
    email = require_env("YIYU_VERIFY_EMAIL")
    password = require_env("YIYU_VERIFY_PASSWORD")
    yiyu_url = require_env("YIYU_VERIFY_YIYU_CLOUD_URL")
    xingcong_url = require_env("YIYU_VERIFY_XINGCONG_CLOUD_URL")

    with tempfile.TemporaryDirectory(prefix="yiyu-dual-org-verify-") as tmp:
        data_dir = Path(tmp) / "data"
        app = create_app(data_dir)
        with TestClient(app) as client:
            fresh = get_json(client, "/api/v1/workspaces/current")
            print(json.dumps({"step": "fresh-start", "runtimeStatus": fresh.get("runtimeStatus"), "kind": fresh.get("kind"), "workspace": fresh.get("name")}, ensure_ascii=False))

            yiyu = login_cloud(client, label="yiyu", cloud_url=yiyu_url, email=email, password=password)
            print(json.dumps({"step": "login", "label": yiyu.label, "organizationId": yiyu.organization_id, "organizationName": yiyu.organization_name, "user": yiyu.user_name}, ensure_ascii=False))
            print(json.dumps({"step": "summary", "label": yiyu.label, **stable_module_summary(client)}, ensure_ascii=False))

            xingcong = login_cloud(client, label="xingcong", cloud_url=xingcong_url, email=email, password=password)
            print(json.dumps({"step": "login", "label": xingcong.label, "organizationId": xingcong.organization_id, "organizationName": xingcong.organization_name, "user": xingcong.user_name}, ensure_ascii=False))
            print(json.dumps({"step": "summary", "label": xingcong.label, **stable_module_summary(client)}, ensure_ascii=False))

            for index, result in enumerate((yiyu, xingcong, yiyu, xingcong), start=1):
                current = activate_org(client, result)
                if current.get("runtimeStatus") not in {"ready", "sync_degraded"}:
                    raise RuntimeError(f"{result.label}: unexpected runtimeStatus {current.get('runtimeStatus')}")
                print(json.dumps({"step": "switch", "round": index, "label": result.label, **stable_module_summary(client)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
