from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.services.generation_runtime_policy import (
    decide_generation_runtime_policy,
    get_generation_runtime_state,
    record_generation_result,
    reset_generation_runtime_state,
)


def test_generation_runtime_policy_compact_then_cooldown(tmp_path: Path):
    db = Database(tmp_path / "runtime.db")
    client_id = "client_runtime"
    intent = "business_profile"

    normal = decide_generation_runtime_policy(
        db,
        client_id=client_id,
        answer_intent=intent,
        provider="openai",
        model="gpt",
    )
    assert normal.shouldAttemptLlm is True
    assert normal.shouldUseLocalOnly is False

    for _ in range(2):
        record_generation_result(
            db,
            client_id=client_id,
            answer_intent=intent,
            provider="openai",
            model="gpt",
            answer_mode="grounded_fallback",
            failure_reason="llm_read_timeout",
            error_detail="read timeout",
            llm_invoked=True,
            total_ms=12000,
        )

    compact = decide_generation_runtime_policy(
        db,
        client_id=client_id,
        answer_intent=intent,
        provider="openai",
        model="gpt",
    )
    assert compact.shouldUseCompactFirst is True
    assert compact.shouldQueueLongAnswerRetry is True
    assert compact.shouldUseLocalOnly is False

    for _ in range(2):
        record_generation_result(
            db,
            client_id=client_id,
            answer_intent=intent,
            provider="openai",
            model="gpt",
            answer_mode="grounded_fallback",
            failure_reason="llm_read_timeout",
            error_detail="read timeout",
            llm_invoked=True,
            total_ms=12000,
        )

    local_only = decide_generation_runtime_policy(
        db,
        client_id=client_id,
        answer_intent=intent,
        provider="openai",
        model="gpt",
    )
    assert local_only.shouldUseLocalOnly is True

    state = get_generation_runtime_state(db, client_id=client_id, answer_intent=intent)
    assert state.stableFallbackActive is True
    assert state.cooldownUntil is not None


def test_generation_runtime_policy_reset(tmp_path: Path):
    db = Database(tmp_path / "runtime_reset.db")
    client_id = "client_runtime_reset"
    intent = "general"

    record_generation_result(
        db,
        client_id=client_id,
        answer_intent=intent,
        provider="openai",
        model="gpt",
        answer_mode="grounded_fallback",
        failure_reason="llm_read_timeout",
        error_detail="timeout",
        llm_invoked=True,
        total_ms=10000,
    )

    state = get_generation_runtime_state(db, client_id=client_id, answer_intent=intent)
    assert state.recentTotal >= 1

    reset = reset_generation_runtime_state(db, client_id=client_id, answer_intent=intent)
    assert reset.recentTotal == 0
    assert reset.recentTimeouts == 0
    assert reset.stableFallbackActive is False


def test_generation_runtime_policy_data_center_primary_keeps_llm_attempts(tmp_path: Path):
    db = Database(tmp_path / "runtime_dc_primary.db")
    client_id = "client_runtime_dc_primary"
    intent = "business_profile"

    for _ in range(4):
        record_generation_result(
            db,
            client_id=client_id,
            answer_intent=intent,
            provider="openai",
            model="gpt",
            answer_mode="grounded_fallback",
            failure_reason="llm_read_timeout",
            error_detail="read timeout",
            llm_invoked=True,
            total_ms=12000,
        )

    decision = decide_generation_runtime_policy(
        db,
        client_id=client_id,
        answer_intent=intent,
        provider="openai",
        model="gpt",
        mode="data_center_primary",
    )
    assert decision.shouldAttemptLlm is True
    assert decision.shouldUseLocalOnly is False
    assert decision.shouldUseCompactFirst is True
