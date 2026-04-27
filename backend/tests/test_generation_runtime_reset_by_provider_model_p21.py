from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.services.generation_runtime_policy import (
    get_generation_runtime_state,
    record_generation_result,
    reset_generation_runtime_state,
)


def test_generation_runtime_reset_by_provider_model(tmp_path: Path):
    db = Database(tmp_path / "runtime_reset_model.db")
    client_id = "client_reset"
    intent = "strategy_profile"

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
        total_ms=9000,
    )
    record_generation_result(
        db,
        client_id=client_id,
        answer_intent=intent,
        provider="doubao",
        model="doubao-pro",
        answer_mode="grounded_fallback",
        failure_reason="llm_read_timeout",
        error_detail="timeout",
        llm_invoked=True,
        total_ms=9000,
    )

    reset_generation_runtime_state(
        db,
        client_id=client_id,
        answer_intent=intent,
        provider="openai",
        model="gpt-a",
        reset_scope="model",
    )

    state_a = get_generation_runtime_state(
        db,
        client_id=client_id,
        answer_intent=intent,
        provider="openai",
        model="gpt-a",
    )
    state_b = get_generation_runtime_state(
        db,
        client_id=client_id,
        answer_intent=intent,
        provider="doubao",
        model="doubao-pro",
    )
    assert state_a.recentTotal == 0
    assert state_b.recentTotal >= 1
