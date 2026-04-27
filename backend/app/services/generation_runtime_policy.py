from __future__ import annotations

from datetime import datetime, timedelta

from app.db import Database
from app.models import GenerationRuntimeDecisionRecord, GenerationRuntimeStateRecord


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


def _now_iso() -> str:
    return _now().isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _norm_provider_model(provider: str | None, model: str | None) -> tuple[str, str]:
    return (str(provider or "").strip(), str(model or "").strip())


def _supports_column(db: Database, table: str, column: str) -> bool:
    rows = db.fetchall(f"PRAGMA table_info({table})")
    for row in rows:
        if str(row["name"] or "") == column:
            return True
    return False


def ensure_generation_runtime_schema(db: Database) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS generation_runtime_state_v2 (
            client_id TEXT NOT NULL,
            answer_intent TEXT NOT NULL,
            provider TEXT NOT NULL DEFAULT '',
            model TEXT NOT NULL DEFAULT '',
            recent_total INTEGER NOT NULL DEFAULT 0,
            recent_timeouts INTEGER NOT NULL DEFAULT 0,
            recent_local_fallbacks INTEGER NOT NULL DEFAULT 0,
            recent_successes INTEGER NOT NULL DEFAULT 0,
            stable_fallback_active INTEGER NOT NULL DEFAULT 0,
            stable_fallback_reason TEXT,
            cooldown_until TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (client_id, answer_intent, provider, model)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS generation_runtime_state (
            client_id TEXT NOT NULL,
            answer_intent TEXT NOT NULL,
            provider TEXT,
            model TEXT,
            recent_total INTEGER NOT NULL DEFAULT 0,
            recent_timeouts INTEGER NOT NULL DEFAULT 0,
            recent_local_fallbacks INTEGER NOT NULL DEFAULT 0,
            recent_successes INTEGER NOT NULL DEFAULT 0,
            stable_fallback_active INTEGER NOT NULL DEFAULT 0,
            stable_fallback_reason TEXT,
            cooldown_until TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (client_id, answer_intent)
        )
        """
    )

    # Best-effort migration: copy legacy rows once into v2.
    row = db.fetchone("SELECT COUNT(*) AS count FROM generation_runtime_state_v2")
    v2_count = int(row["count"] or 0) if row else 0
    if v2_count > 0:
        return
    if not _supports_column(db, "generation_runtime_state", "client_id"):
        return
    legacy_rows = db.fetchall("SELECT * FROM generation_runtime_state")
    for legacy in legacy_rows:
        provider, model = _norm_provider_model(legacy["provider"], legacy["model"])
        db.execute(
            """
            INSERT INTO generation_runtime_state_v2(
                client_id, answer_intent, provider, model,
                recent_total, recent_timeouts, recent_local_fallbacks, recent_successes,
                stable_fallback_active, stable_fallback_reason, cooldown_until, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(client_id, answer_intent, provider, model) DO UPDATE SET
                recent_total = excluded.recent_total,
                recent_timeouts = excluded.recent_timeouts,
                recent_local_fallbacks = excluded.recent_local_fallbacks,
                recent_successes = excluded.recent_successes,
                stable_fallback_active = excluded.stable_fallback_active,
                stable_fallback_reason = excluded.stable_fallback_reason,
                cooldown_until = excluded.cooldown_until,
                updated_at = excluded.updated_at
            """,
            (
                str(legacy["client_id"] or ""),
                str(legacy["answer_intent"] or "general"),
                provider,
                model,
                int(legacy["recent_total"] or 0),
                int(legacy["recent_timeouts"] or 0),
                int(legacy["recent_local_fallbacks"] or 0),
                int(legacy["recent_successes"] or 0),
                int(legacy["stable_fallback_active"] or 0),
                str(legacy["stable_fallback_reason"] or "") or None,
                str(legacy["cooldown_until"] or "") or None,
                str(legacy["updated_at"] or _now_iso()),
            ),
        )


def _row_to_record(row, *, client_id: str, answer_intent: str) -> GenerationRuntimeStateRecord:
    if row is None:
        return GenerationRuntimeStateRecord(
            clientId=client_id,
            answerIntent=answer_intent,
            updatedAt=_now_iso(),
        )
    return GenerationRuntimeStateRecord(
        clientId=str(row["client_id"]),
        answerIntent=str(row["answer_intent"]),
        provider=str(row["provider"]) if row["provider"] else None,
        model=str(row["model"]) if row["model"] else None,
        recentTotal=int(row["recent_total"] or 0),
        recentTimeouts=int(row["recent_timeouts"] or 0),
        recentLocalFallbacks=int(row["recent_local_fallbacks"] or 0),
        recentSuccesses=int(row["recent_successes"] or 0),
        stableFallbackActive=bool(row["stable_fallback_active"]),
        stableFallbackReason=str(row["stable_fallback_reason"]) if row["stable_fallback_reason"] else None,
        cooldownUntil=str(row["cooldown_until"]) if row["cooldown_until"] else None,
        updatedAt=str(row["updated_at"] or _now_iso()),
    )


def get_generation_runtime_state(
    db: Database,
    *,
    client_id: str,
    answer_intent: str,
    provider: str | None = None,
    model: str | None = None,
) -> GenerationRuntimeStateRecord:
    ensure_generation_runtime_schema(db)
    provider_text, model_text = _norm_provider_model(provider, model)
    if provider_text or model_text:
        row = db.fetchone(
            """
            SELECT *
            FROM generation_runtime_state_v2
            WHERE client_id = ? AND answer_intent = ? AND provider = ? AND model = ?
            """,
            (client_id, answer_intent, provider_text, model_text),
        )
        record = _row_to_record(row, client_id=client_id, answer_intent=answer_intent)
        record.provider = provider_text or None
        record.model = model_text or None
        return record

    row = db.fetchone(
        """
        SELECT *
        FROM generation_runtime_state_v2
        WHERE client_id = ? AND answer_intent = ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (client_id, answer_intent),
    )
    if row is not None:
        return _row_to_record(row, client_id=client_id, answer_intent=answer_intent)
    return GenerationRuntimeStateRecord(
        clientId=client_id,
        answerIntent=answer_intent,
        updatedAt=_now_iso(),
    )


def decide_generation_runtime_policy(
    db: Database,
    *,
    client_id: str,
    answer_intent: str,
    provider: str | None,
    model: str | None,
    mode: str = "legacy",
) -> GenerationRuntimeDecisionRecord:
    provider_text, model_text = _norm_provider_model(provider, model)
    state = get_generation_runtime_state(
        db,
        client_id=client_id,
        answer_intent=answer_intent,
        provider=provider_text,
        model=model_text,
    )

    cooldown_until = _parse_iso(state.cooldownUntil)
    cooldown_active = bool(cooldown_until and cooldown_until > _now())

    should_use_local_only = False
    should_use_compact_first = False
    should_queue_long_retry = False
    should_probe_after_cooldown = False
    reason = "normal_runtime"

    data_center_primary = str(mode or "legacy").strip() == "data_center_primary"

    if data_center_primary:
        # P2.14 FREEZE(answer-shaping-open-runtime): workspace/chat 主回答链当前明确禁止 compact/local/probe 回退重新接回。
        # 这条开放 runtime 边界先冻结，避免旧压缩链或本地回答链回流到主回答。
        return GenerationRuntimeDecisionRecord(
            shouldAttemptLlm=True,
            shouldUseCompactFirst=False,
            shouldUseLocalOnly=False,
            shouldQueueLongAnswerRetry=False,
            shouldProbeAfterCooldown=False,
            reason="workspace_chat_open_runtime",
            cooldownActive=False,
        )

    if cooldown_active:
        should_use_local_only = True
        reason = "cooldown_active_after_timeouts"
    elif state.stableFallbackActive and state.recentTimeouts >= 4:
        should_probe_after_cooldown = True
        reason = "cooldown_expired_probe_llm"
    elif state.recentTimeouts >= 4:
        should_use_local_only = True
        reason = "severe_timeout_burst"
    elif state.recentTimeouts >= 2 or state.recentLocalFallbacks >= 2:
        should_use_compact_first = True
        should_queue_long_retry = True
        reason = "timeout_or_fallback_burst"

    return GenerationRuntimeDecisionRecord(
        shouldAttemptLlm=not should_use_local_only,
        shouldUseCompactFirst=should_use_compact_first,
        shouldUseLocalOnly=should_use_local_only,
        shouldQueueLongAnswerRetry=should_queue_long_retry,
        shouldProbeAfterCooldown=should_probe_after_cooldown,
        reason=reason,
        cooldownActive=cooldown_active,
    )


def _is_timeout_failure(*, failure_reason: str | None, error_detail: str | None) -> bool:
    merged = f"{failure_reason or ''} {error_detail or ''}".lower()
    return any(token in merged for token in ("timeout", "timed out", "read timeout", "超时"))


def _is_local_fallback(*, answer_mode: str, failure_reason: str | None) -> bool:
    if answer_mode != "grounded_fallback":
        return False
    reason = str(failure_reason or "").lower()
    return any(token in reason for token in ("llm_", "fallback", "timeout", "state_only"))


def _is_success(*, answer_mode: str, failure_reason: str | None) -> bool:
    if failure_reason:
        return False
    return answer_mode in {"grounded_answer", "low_confidence_answer", "general_answer"}


def _roll_window(
    *,
    recent_total: int,
    recent_timeouts: int,
    recent_local_fallbacks: int,
    recent_successes: int,
) -> tuple[int, int, int, int]:
    if recent_total < 20:
        return recent_total, recent_timeouts, recent_local_fallbacks, recent_successes
    return (
        max(0, int(recent_total * 0.7)),
        max(0, int(recent_timeouts * 0.7)),
        max(0, int(recent_local_fallbacks * 0.7)),
        max(0, int(recent_successes * 0.7)),
    )


def record_generation_result(
    db: Database,
    *,
    client_id: str,
    answer_intent: str,
    provider: str | None,
    model: str | None,
    answer_mode: str,
    failure_reason: str | None,
    error_detail: str | None,
    llm_invoked: bool,
    total_ms: float,
) -> None:
    del llm_invoked, total_ms
    ensure_generation_runtime_schema(db)
    provider_text, model_text = _norm_provider_model(provider, model)
    current = get_generation_runtime_state(
        db,
        client_id=client_id,
        answer_intent=answer_intent,
        provider=provider_text,
        model=model_text,
    )

    recent_total, recent_timeouts, recent_local_fallbacks, recent_successes = _roll_window(
        recent_total=current.recentTotal,
        recent_timeouts=current.recentTimeouts,
        recent_local_fallbacks=current.recentLocalFallbacks,
        recent_successes=current.recentSuccesses,
    )
    recent_total += 1

    timed_out = _is_timeout_failure(failure_reason=failure_reason, error_detail=error_detail)
    used_local_fallback = _is_local_fallback(answer_mode=answer_mode, failure_reason=failure_reason)
    succeeded = _is_success(answer_mode=answer_mode, failure_reason=failure_reason)

    if timed_out:
        recent_timeouts += 1
    if used_local_fallback:
        recent_local_fallbacks += 1
    if succeeded:
        recent_successes += 1

    stable_active = current.stableFallbackActive
    stable_reason = current.stableFallbackReason
    cooldown_until = _parse_iso(current.cooldownUntil)

    if timed_out and recent_timeouts >= 4:
        stable_active = True
        stable_reason = "recent_llm_read_timeouts"
        cooldown_until = _now() + timedelta(minutes=10)
    elif succeeded and stable_active:
        stable_active = False
        stable_reason = None
        cooldown_until = None
        recent_timeouts = max(0, recent_timeouts - 3)
        recent_local_fallbacks = max(0, recent_local_fallbacks - 2)
    elif succeeded and recent_timeouts > 0:
        recent_timeouts = max(0, recent_timeouts - 2)
        recent_local_fallbacks = max(0, recent_local_fallbacks - 1)

    db.execute(
        """
        INSERT INTO generation_runtime_state_v2(
            client_id, answer_intent, provider, model,
            recent_total, recent_timeouts, recent_local_fallbacks, recent_successes,
            stable_fallback_active, stable_fallback_reason, cooldown_until, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(client_id, answer_intent, provider, model) DO UPDATE SET
            provider = excluded.provider,
            model = excluded.model,
            recent_total = excluded.recent_total,
            recent_timeouts = excluded.recent_timeouts,
            recent_local_fallbacks = excluded.recent_local_fallbacks,
            recent_successes = excluded.recent_successes,
            stable_fallback_active = excluded.stable_fallback_active,
            stable_fallback_reason = excluded.stable_fallback_reason,
            cooldown_until = excluded.cooldown_until,
            updated_at = excluded.updated_at
        """,
        (
            client_id,
            answer_intent,
            provider_text,
            model_text,
            int(recent_total),
            int(recent_timeouts),
            int(recent_local_fallbacks),
            int(recent_successes),
            1 if stable_active else 0,
            stable_reason,
            cooldown_until.isoformat() if cooldown_until else None,
            _now_iso(),
        ),
    )


def reset_generation_runtime_state(
    db: Database,
    *,
    client_id: str,
    answer_intent: str,
    provider: str | None = None,
    model: str | None = None,
    reset_scope: str = "intent",
) -> GenerationRuntimeStateRecord:
    ensure_generation_runtime_schema(db)
    provider_text, model_text = _norm_provider_model(provider, model)
    scope = str(reset_scope or "intent")
    if scope == "client":
        db.execute(
            """
            DELETE FROM generation_runtime_state_v2
            WHERE client_id = ?
            """,
            (client_id,),
        )
        return GenerationRuntimeStateRecord(
            clientId=client_id,
            answerIntent=answer_intent,
            provider=provider_text or None,
            model=model_text or None,
            updatedAt=_now_iso(),
        )
    if scope == "model":
        db.execute(
            """
            DELETE FROM generation_runtime_state_v2
            WHERE client_id = ? AND answer_intent = ? AND provider = ? AND model = ?
            """,
            (client_id, answer_intent, provider_text, model_text),
        )
    else:
        db.execute(
            """
            DELETE FROM generation_runtime_state_v2
            WHERE client_id = ? AND answer_intent = ?
            """,
            (client_id, answer_intent),
        )
    return get_generation_runtime_state(
        db,
        client_id=client_id,
        answer_intent=answer_intent,
        provider=provider_text or None,
        model=model_text or None,
    )
