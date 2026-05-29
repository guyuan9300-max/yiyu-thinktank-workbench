"""Smoke test: drive AiService through the openclaw provider end-to-end.

Requires:
  - openclaw CLI in PATH
  - openclaw gateway running with a logged-in ChatGPT account
  - default agent id "main" available
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import Database  # noqa: E402
from app.services.ai import AiService  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as workdir:
        db_path = Path(workdir) / "smoke.db"
        db = Database(str(db_path))
        ai = AiService(db, secret_stores={})

        ai.configure(provider="openclaw", model=None, api_key=None, clear_api_key=False)
        assert ai.current_provider() == "openclaw", ai.current_provider()
        print(f"[ok] provider set: {ai.current_provider()} model={ai.current_model()}")

        health = ai.get_health()
        print(f"[ok] health: ready={health.ready} detail={health.detail}")
        if not health.ready:
            print(f"[fail] not ready — abort")
            return 2

        start = time.perf_counter()
        result = ai._qwen_generate(
            prompt="Reply with exactly one word: pong",
            system_instruction="You are a connectivity probe. Reply with the single word the user asks for.",
            response_schema=None,
            timeout_seconds=90.0,
            max_tokens=20,
        )
        elapsed = time.perf_counter() - start
        text = (result or "").strip() if isinstance(result, str) else str(result)
        print(f"[ok] reply in {elapsed:.1f}s: {text!r}")

        if "pong" not in text.lower():
            print(f"[fail] reply did not contain 'pong'")
            return 3

        print("[done] smoke test passed")
        return 0


if __name__ == "__main__":
    sys.exit(main())
