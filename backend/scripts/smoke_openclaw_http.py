"""HTTP-level smoke: drive the FastAPI app to switch provider to openclaw and
hit the runtime healthcheck endpoint.

This exercises exactly what the renderer would do:
  1. POST /api/v1/settings { aiProvider: 'openclaw', aiModel: '...' }
  2. POST /api/v1/runtime/llm-healthcheck

Prereqs: openclaw CLI + gateway running + ChatGPT logged in.
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as workdir:
        app = create_app(data_dir=Path(workdir))
        client = TestClient(app)

        switch = client.post(
            "/api/v1/settings",
            json={
                "aiProvider": "openclaw",
                "aiModel": "openai-codex/gpt-5.4",
            },
        )
        print(f"[POST /api/v1/settings] {switch.status_code}")
        if switch.status_code != 200:
            print(switch.text[:600])
            return 2
        body = switch.json()
        settings = body.get("settings") or {}
        print(f"  aiProvider={settings.get('aiProvider')!r} aiModel={settings.get('aiModel')!r}")
        if settings.get("aiProvider") != "openclaw":
            print("[fail] provider did not switch")
            return 3

        start = time.perf_counter()
        check = client.post(
            "/api/v1/runtime/llm-healthcheck",
            json={"prompt": "Reply with single word: pong"},
        )
        elapsed = time.perf_counter() - start
        print(f"[POST /api/v1/runtime/llm-healthcheck] {check.status_code} ({elapsed:.1f}s)")
        if check.status_code != 200:
            print(check.text[:600])
            return 4

        result = check.json()
        print(f"  success={result.get('success')} model={result.get('model')!r}")
        print(f"  error={result.get('error')!r} errorKind={result.get('errorKind')!r}")

        if not result.get("success"):
            print("[fail] healthcheck reported failure")
            return 5

        print("[done] HTTP-level smoke passed")
        return 0


if __name__ == "__main__":
    sys.exit(main())
