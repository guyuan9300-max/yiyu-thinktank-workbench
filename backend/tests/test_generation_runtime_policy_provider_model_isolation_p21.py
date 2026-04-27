from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.services.generation_runtime_policy import (
    decide_generation_runtime_policy,
    get_generation_runtime_state,
    record_generation_result,
)


def test_generation_runtime_policy_isolated_by_provider_model(tmp_path: Path):
    db = Database(tmp_path / "runtime_isolation.db")
    client_id = "client_iso"
    intent = "general"

    for _ in range(4):
        record_generation_result(
            db,
            client_id=client_id,
            answer_intent=intent,
            provider="openai",
            model="gpt-a",
            answer_mode="grounded_fallback",
            failure_reason="llm_read_timeout",
            error_detail="timeout",
            llm_invoked=True,
            total_ms=14000,
        )

    model_a = decide_generation_runtime_policy(
        db,
        client_id=client_id,
        answer_intent=intent,
        provider="openai",
        model="gpt-a",
    )
    assert model_a.shouldUseLocalOnly is True

    model_b = decide_generation_runtime_policy(
        db,
        client_id=client_id,
        answer_intent=intent,
        provider="doubao",
        model="doubao-pro",
    )
    assert model_b.shouldUseLocalOnly is False
    assert model_b.shouldUseCompactFirst is False

    state_b = get_generation_runtime_state(
        db,
        client_id=client_id,
        answer_intent=intent,
        provider="doubao",
        model="doubao-pro",
    )
    assert state_b.recentTotal == 0
