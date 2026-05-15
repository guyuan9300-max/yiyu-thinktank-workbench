from __future__ import annotations

from app.services.intelligence_ai_runner import (
    generate_intelligence_json,
    generate_intelligence_text,
    intelligence_ai_ready,
)


class _Health:
    ready = True
    provider = "doubao"


class _MockHealth:
    ready = True
    provider = "mock"


class _ReadyAi:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_health(self, *, task_kind: str = "default"):
        self.calls.append({"health_task_kind": task_kind})
        return _Health()

    def _qwen_generate(self, **kwargs):
        self.calls.append(dict(kwargs))
        if kwargs.get("response_schema"):
            return {
                "summary": "外部信号已经进入有效窗口。",
                "relevanceReason": "该信号命中当前对象服务对象和资源需求。",
            }
        return "这是一段稳定返回的资讯情报站 AI 分析。"


class _MockAi:
    def get_health(self, *, task_kind: str = "default"):
        return _MockHealth()


def test_intelligence_ai_runner_uses_deep_analysis_profile() -> None:
    ai = _ReadyAi()

    result = generate_intelligence_text(
        ai,
        prompt="请分析这条情报",
        system_instruction="你是情报研究员",
        task_kind="deep_analysis",
        enable_thinking=True,
    )

    assert result.ok
    assert any(call.get("health_task_kind") == "deep_analysis" for call in ai.calls)
    generate_calls = [call for call in ai.calls if "prompt" in call]
    assert generate_calls
    assert generate_calls[0]["task_kind"] == "deep_analysis"
    assert generate_calls[0]["enable_thinking"] is True


def test_intelligence_ai_json_returns_structured_payload() -> None:
    ai = _ReadyAi()

    result = generate_intelligence_json(
        ai,
        prompt="请返回结构化字段",
        system_instruction="只返回 JSON",
        response_schema={"type": "OBJECT", "properties": {"summary": {"type": "STRING"}}},
    )

    assert result.ok
    assert result.payload
    assert result.payload["summary"] == "外部信号已经进入有效窗口。"


def test_intelligence_ai_ready_rejects_mock_provider() -> None:
    assert intelligence_ai_ready(_MockAi()) is False
