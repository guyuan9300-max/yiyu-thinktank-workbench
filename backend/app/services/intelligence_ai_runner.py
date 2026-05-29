from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class IntelligenceAiCallResult:
    ok: bool
    text: str = ""
    payload: dict[str, object] | None = None
    error: str = ""
    attempts: list[str] = field(default_factory=list)
    partial: bool = False


def intelligence_ai_ready(ai_service: object | None, *, task_kind: str = "deep_analysis") -> bool:
    if ai_service is None or not hasattr(ai_service, "get_health"):
        return False
    try:
        health = ai_service.get_health(task_kind=task_kind)
    except TypeError:
        try:
            health = ai_service.get_health()
        except Exception:
            return False
    except Exception:
        return False
    return bool(getattr(health, "ready", False)) and str(getattr(health, "provider", "mock")) != "mock"


def _error_text(exc: BaseException) -> str:
    detail = str(exc).strip()
    return detail if detail else exc.__class__.__name__


def _strip_code_fence(text: str) -> str:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 2:
            cleaned = "\n".join(lines[1:-1] if lines[-1].strip().startswith("```") else lines[1:]).strip()
    return cleaned


def _load_json_object(text: str) -> dict[str, object] | None:
    cleaned = _strip_code_fence(text)
    if not cleaned:
        return None
    candidates = [cleaned]
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match and match.group(0) != cleaned:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def generate_intelligence_text(
    ai_service: object | None,
    *,
    prompt: str,
    system_instruction: str,
    timeout_seconds: float = 180.0,
    max_tokens: int = 1600,
    temperature: float = 0.28,
    top_p: float = 0.9,
    task_kind: str = "deep_analysis",
    enable_thinking: bool = True,
    min_chars: int = 0,
) -> IntelligenceAiCallResult:
    if not intelligence_ai_ready(ai_service, task_kind=task_kind):
        return IntelligenceAiCallResult(ok=False, error="AI 未配置或不可用")

    attempts: list[str] = []
    stream = getattr(ai_service, "_qwen_generate_streaming", None)
    if callable(stream):
        chunks: list[str] = []
        try:
            text = str(
                stream(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    on_token=chunks.append,
                    timeout_seconds=timeout_seconds,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    enable_thinking=enable_thinking,
                    task_kind=task_kind,
                )
                or ""
            ).strip()
            if len(text) >= min_chars:
                return IntelligenceAiCallResult(ok=True, text=text, attempts=["stream"])
            attempts.append("stream:empty")
        except Exception as exc:
            partial = "".join(chunks).strip()
            attempts.append(f"stream:{_error_text(exc)}")
            if len(partial) >= max(80, min_chars):
                logger.warning("intelligence AI stream interrupted; using partial response: %s", exc)
                return IntelligenceAiCallResult(ok=True, text=partial, attempts=attempts, partial=True)
            logger.warning("intelligence AI stream failed; retrying non-stream: %s", exc)

    generate = getattr(ai_service, "_qwen_generate", None)
    if callable(generate):
        attempts_to_run = [("generate_thinking", True), ("generate", False)] if enable_thinking else [("generate", False)]
        for attempt_name, thinking in attempts_to_run:
            try:
                text = str(
                    generate(
                        prompt=prompt,
                        system_instruction=system_instruction,
                        response_schema=None,
                        timeout_seconds=timeout_seconds,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        top_p=top_p,
                        enable_thinking=thinking,
                        task_kind=task_kind,
                    )
                    or ""
                ).strip()
                if len(text) >= min_chars:
                    return IntelligenceAiCallResult(ok=True, text=text, attempts=[*attempts, attempt_name])
                attempts.append(f"{attempt_name}:empty")
            except Exception as exc:
                attempts.append(f"{attempt_name}:{_error_text(exc)}")
                logger.warning("intelligence AI %s failed: %s", attempt_name, exc)

    # Test doubles used in backend tests often expose only this older surface.
    # Real production AiService has _qwen_generate and will not normally reach this branch.
    general = getattr(ai_service, "generate_general_fallback", None)
    if callable(general) and not callable(generate):
        try:
            response = general(prompt, "资讯情报站 AI Runner 兼容调用")
            text = "\n\n".join(
                str(part or "").strip()
                for part in (
                    getattr(response, "content", ""),
                    getattr(response, "judgment", ""),
                    getattr(response, "analysis", ""),
                    getattr(response, "actions", ""),
                    getattr(response, "timeline", ""),
                )
                if str(part or "").strip()
            )
            if len(text) >= min_chars:
                return IntelligenceAiCallResult(ok=True, text=text, attempts=[*attempts, "legacy_general"])
            attempts.append("legacy_general:empty")
        except Exception as exc:
            attempts.append(f"legacy_general:{_error_text(exc)}")

    return IntelligenceAiCallResult(ok=False, error="；".join(attempts) or "AI 调用没有稳定返回", attempts=attempts)


def generate_intelligence_json(
    ai_service: object | None,
    *,
    prompt: str,
    system_instruction: str,
    response_schema: dict[str, object],
    timeout_seconds: float = 180.0,
    max_tokens: int = 1600,
    temperature: float = 0.22,
    top_p: float = 0.86,
    task_kind: str = "deep_analysis",
    enable_thinking: bool = True,
) -> IntelligenceAiCallResult:
    if not intelligence_ai_ready(ai_service, task_kind=task_kind):
        return IntelligenceAiCallResult(ok=False, error="AI 未配置或不可用")
    attempts: list[str] = []
    generate = getattr(ai_service, "_qwen_generate", None)
    if callable(generate):
        attempts_to_run = [("json_thinking", True), ("json", False)] if enable_thinking else [("json", False)]
        for attempt_name, thinking in attempts_to_run:
            try:
                payload = generate(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    response_schema=response_schema,
                    timeout_seconds=timeout_seconds,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    enable_thinking=thinking,
                    task_kind=task_kind,
                )
                if isinstance(payload, dict):
                    return IntelligenceAiCallResult(ok=True, payload=dict(payload), attempts=[*attempts, attempt_name])
                parsed = _load_json_object(str(payload or ""))
                if parsed is not None:
                    return IntelligenceAiCallResult(ok=True, payload=parsed, attempts=[*attempts, attempt_name])
                attempts.append(f"{attempt_name}:non_json")
            except Exception as exc:
                attempts.append(f"{attempt_name}:{_error_text(exc)}")
                logger.warning("intelligence AI %s failed: %s", attempt_name, exc)

    text_result = generate_intelligence_text(
        ai_service,
        prompt=(
            "请只返回一个 JSON 对象，不要使用 Markdown。\n"
            f"JSON Schema：{json.dumps(response_schema, ensure_ascii=False)}\n\n"
            f"{prompt}"
        ),
        system_instruction=system_instruction,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        task_kind=task_kind,
        enable_thinking=enable_thinking,
        min_chars=20,
    )
    attempts.extend(text_result.attempts)
    if text_result.ok:
        parsed = _load_json_object(text_result.text)
        if parsed is not None:
            return IntelligenceAiCallResult(ok=True, payload=parsed, text=text_result.text, attempts=attempts, partial=text_result.partial)
        attempts.append("text_json_parse_failed")
    return IntelligenceAiCallResult(ok=False, error=text_result.error or "AI JSON 调用没有稳定返回", attempts=attempts)
