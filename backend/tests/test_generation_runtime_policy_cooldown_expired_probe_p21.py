from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.services.generation_runtime_policy import (
    decide_generation_runtime_policy,
    get_generation_runtime_state,
    record_generation_result,
)


def test_generation_runtime_policy_cooldown_expired_allows_probe(tmp_path: Path):
    db = Database(tmp_path / "runtime_probe.db")
    client_id = "client_probe"
    intent = "business_profile"
    provider = "openai"
    model = "gpt-test"

    for _ in range(4):
        record_generation_result(
            db,
            client_id=client_id,
            answer_intent=intent,
            provider=provider,
            model=model,
            answer_mode="grounded_fallback",
            failure_reason="llm_read_timeout",
            error_detail="read timeout",
            llm_invoked=True,
            total_ms=12000,
        )

    # Force cooldown expired.
    db.execute(
        """
        UPDATE generation_runtime_state_v2
        SET cooldown_until = ?
        WHERE client_id = ? AND answer_intent = ? AND provider = ? AND model = ?
        """,
        (
            (datetime.now() - timedelta(minutes=1)).replace(microsecond=0).isoformat(),
            client_id,
            intent,
            provider,
            model,
        ),
    )

    decision = decide_generation_runtime_policy(
        db,
        client_id=client_id,
        answer_intent=intent,
        provider=provider,
        model=model,
    )
    assert decision.shouldProbeAfterCooldown is True
    assert decision.shouldAttemptLlm is True
    assert decision.shouldUseLocalOnly is False

    # Probe success should clear stable fallback.
    record_generation_result(
        db,
        client_id=client_id,
        answer_intent=intent,
        provider=provider,
        model=model,
        answer_mode="grounded_answer",
        failure_reason=None,
        error_detail=None,
        llm_invoked=True,
        total_ms=2200,
    )

    state = get_generation_runtime_state(
        db,
        client_id=client_id,
        answer_intent=intent,
        provider=provider,
        model=model,
    )
    assert state.stableFallbackActive is False
    assert state.recentTimeouts < 4
