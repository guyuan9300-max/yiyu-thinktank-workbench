"""PromptLogger · LLM 调用全量持久化

设计原则:
- 每次 LLM 调用必须 log 一条(成功/失败都记)
- prompt / output 全量保存(不裁剪),数据驱动改进的根基
- log 操作不能阻塞 LLM 主流程(失败时只打 warn,不抛)

用法:
    logger = PromptLogger(db)
    log_id = logger.log(
        context=composed_context,    # 来自 ContextComposer
        output_text=llm_response,
        duration_ms=1234.5,
        tokens_used=512,
        model_id="qwen3-vl:32b",
        error="",                     # 失败时填错误
    )
"""
from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Any

from .types import LLMContext

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return "plog_" + secrets.token_hex(6)


class PromptLogger:
    def __init__(self, db: Any):
        self._db = db

    def log(
        self,
        *,
        context: LLMContext,
        output_text: str = "",
        duration_ms: float = 0.0,
        tokens_used: int = 0,
        model_id: str = "",
        error: str = "",
        metadata: dict | None = None,
    ) -> str | None:
        """记录一次 LLM 调用 · 返回 log id(失败时 None,不抛)"""
        log_id = _new_id()
        try:
            self._db.execute(
                """
                INSERT INTO prompt_log(
                    id, intent, client_id, user_id, system_text, prompt_text,
                    output_text, duration_ms, tokens_used, model_id, error,
                    score, score_note, metadata_json, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, '', ?, ?)
                """,
                (
                    log_id,
                    context.intent,
                    context.client_id,
                    context.user_id,
                    context.system_text,
                    context.prompt_text,
                    output_text or "",
                    float(duration_ms),
                    int(tokens_used),
                    model_id or "",
                    error or "",
                    json.dumps(metadata or {}, ensure_ascii=False),
                    _now_iso(),
                ),
            )
            return log_id
        except Exception as exc:  # noqa: BLE001
            # 不能让 logger 失败阻塞 LLM 主流程
            logger.warning("PromptLogger.log failed (silently swallowed): %r", exc)
            return None

    def update_score(self, log_id: str, *, score: float, note: str = "") -> bool:
        """事后给某次调用打分 · 用于数据驱动改进"""
        try:
            self._db.execute(
                "UPDATE prompt_log SET score = ?, score_note = ? WHERE id = ?",
                (float(score), note, log_id),
            )
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("PromptLogger.update_score failed: %r", exc)
            return False


def log_prompt(
    db: Any,
    *,
    context: LLMContext,
    output_text: str = "",
    duration_ms: float = 0.0,
    tokens_used: int = 0,
    model_id: str = "",
    error: str = "",
    metadata: dict | None = None,
) -> str | None:
    """函数式入口"""
    return PromptLogger(db).log(
        context=context,
        output_text=output_text,
        duration_ms=duration_ms,
        tokens_used=tokens_used,
        model_id=model_id,
        error=error,
        metadata=metadata,
    )
