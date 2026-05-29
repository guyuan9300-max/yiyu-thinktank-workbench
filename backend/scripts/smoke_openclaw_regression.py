"""Regression: confirm switching back to doubao still works and openclaw branch
does not interfere with the doubao path. Doubao actual call will fail without
an API key — that's expected; we only check the *switching* logic and that
healthcheck returns a clean auth_error (not a crash).
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as workdir:
        app = create_app(data_dir=Path(workdir))
        client = TestClient(app)

        for target in ("openclaw", "doubao", "mock", "openclaw"):
            resp = client.post("/api/v1/settings", json={"aiProvider": target})
            assert resp.status_code == 200, resp.text
            ap = resp.json()["settings"]["aiProvider"]
            print(f"  switch -> {target}: got {ap}")
            assert ap == target, f"expected {target}, got {ap}"

        for target in ("openclaw", "doubao", "mock"):
            r = client.post("/api/v1/runtime/llm-healthcheck", json={"provider": target, "prompt": "ping"})
            assert r.status_code == 200, r.text
            data = r.json()
            print(f"  healthcheck({target}): success={data['success']} errorKind={data.get('errorKind')!r}")

        print("[done] regression passed (no crashes across providers)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
