from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.services.ai import AiHealth, AiService


def test_generate_template_field_values_batch_returns_cleaned_mapping(tmp_path: Path, monkeypatch):
    db = Database(tmp_path / "app.db")
    service = AiService(db, {"qwen": SimpleNamespace()})

    monkeypatch.setattr(
        service,
        "get_health",
        lambda: AiHealth(
            provider="qwen",
            model="qwen3.5-plus",
            ready=True,
            detail="ok",
            credential_source="local",
            fingerprint=None,
        ),
    )

    def fake_qwen_generate(*, prompt: str, system_instruction: str, response_schema: dict | None, **_: object):
        assert response_schema is not None
        assert "机构名称" in response_schema["properties"]
        assert "机构简介" in response_schema["properties"]
        return {
            "机构名称": "建议填写：日慈基金会",
            "机构简介": "```专注于青少年心理健康与社会情感学习。```",
        }

    monkeypatch.setattr(service, "_qwen_generate", fake_qwen_generate)

    values = service.generate_template_field_values_batch(
        template_name="模板.docx",
        client_name="日慈基金会",
        field_contexts=[
            ("机构名称", "字段一上下文"),
            ("机构简介", "字段二上下文"),
        ],
        field_types={
            "机构名称": "precise_fact",
            "机构简介": "structural_summary",
        },
    )

    assert values["机构名称"] == "日慈基金会"
    assert values["机构简介"] == "专注于青少年心理健康与社会情感学习。"


def test_exact_fact_field_stays_conservative_when_model_returns_process_hint(tmp_path: Path, monkeypatch):
    db = Database(tmp_path / "app.db")
    service = AiService(db, {"qwen": SimpleNamespace()})

    monkeypatch.setattr(
        service,
        "get_health",
        lambda: AiHealth(provider="qwen", model="qwen3.5-plus", ready=True, detail="ok", credential_source="local", fingerprint=None),
    )
    monkeypatch.setattr(
        service,
        "_qwen_generate",
        lambda **_: "可从登记证书或章程进一步核实统一社会信用代码。",
    )

    value = service.generate_template_field_value(
        field_label="统一社会信用代码",
        template_name="模板.docx",
        client_name="CFFC",
        context_summary="资料不足",
        field_type="precise_fact",
    )

    assert value.startswith("【待确认】")


def test_governance_field_does_not_output_process_style_hint(tmp_path: Path, monkeypatch):
    db = Database(tmp_path / "app.db")
    service = AiService(db, {"qwen": SimpleNamespace()})

    monkeypatch.setattr(
        service,
        "get_health",
        lambda: AiHealth(provider="qwen", model="qwen3.5-plus", ready=True, detail="ok", credential_source="local", fingerprint=None),
    )
    monkeypatch.setattr(
        service,
        "_qwen_generate",
        lambda **_: "可从制度文件、会议纪要中进一步梳理党建与业务结合方式。",
    )

    value = service.generate_template_field_value(
        field_label="党建与业务工作的结合方式",
        template_name="模板.docx",
        client_name="CFFC",
        context_summary="若干治理资料",
        field_type="governance_mechanism",
    )

    assert value.startswith("【待确认】")


def test_quantitative_field_cannot_use_vague_description_as_fact(tmp_path: Path, monkeypatch):
    db = Database(tmp_path / "app.db")
    service = AiService(db, {"qwen": SimpleNamespace()})

    monkeypatch.setattr(
        service,
        "get_health",
        lambda: AiHealth(provider="qwen", model="qwen3.5-plus", ready=True, detail="ok", credential_source="local", fingerprint=None),
    )
    monkeypatch.setattr(
        service,
        "_qwen_generate",
        lambda **_: "近三年开展了较多活动，覆盖面较广。",
    )

    value = service.generate_template_field_value(
        field_label="近三年代表性活动/会议数量",
        template_name="模板.docx",
        client_name="CFFC",
        context_summary="若干活动总结",
        field_type="quantitative_result",
    )

    assert value.startswith("【待确认】")


def test_generate_chat_response_extreme_context_uses_relaxed_profile(tmp_path: Path, monkeypatch):
    db = Database(tmp_path / "app.db")
    service = AiService(db, {"qwen": SimpleNamespace()})
    monkeypatch.setattr(
        service,
        "get_health",
        lambda: AiHealth(provider="qwen", model="qwen3.5-plus", ready=True, detail="ok", credential_source="local", fingerprint=None),
    )

    calls: list[dict[str, object]] = []

    def fake_qwen_generate(**kwargs):
        calls.append(kwargs)
        return "这是最终回答。"

    monkeypatch.setattr(service, "_qwen_generate", fake_qwen_generate)

    long_context = "\n\n".join(
        f"[原始证据 {index}]\n标题：材料{index}\n片段：{'原文片段' * 400}"
        for index in range(1, 45)
    )

    response = service.generate_chat_response("请介绍这家组织", "你是顾问。", long_context)

    assert response.content == "这是最终回答。"
    assert len(calls) == 1
    first_call = calls[0]
    assert float(first_call["timeout_seconds"]) >= 36.0
    assert int(first_call["max_tokens"]) <= 1000
    assert first_call["enable_thinking"] is False
    assert len(str(first_call["prompt"])) < len(f"用户问题：请介绍这家组织\n\n参考材料：\n{long_context}")


def test_generate_chat_response_retry_downgrades_to_fast_non_thinking(tmp_path: Path, monkeypatch):
    db = Database(tmp_path / "app.db")
    service = AiService(db, {"qwen": SimpleNamespace()})
    monkeypatch.setattr(
        service,
        "get_health",
        lambda: AiHealth(provider="qwen", model="qwen3.5-plus", ready=True, detail="ok", credential_source="local", fingerprint=None),
    )

    calls: list[dict[str, object]] = []

    def fake_qwen_generate(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise RuntimeError("read timeout")
        return "兜底回答"

    monkeypatch.setattr(service, "_qwen_generate", fake_qwen_generate)

    medium_context = "\n\n".join(
        f"[原始证据 {index}]\n标题：材料{index}\n片段：{'背景信息' * 280}"
        for index in range(1, 22)
    )

    response = service.generate_chat_response("请给出完整判断", "你是顾问。", medium_context)

    assert response.content == "兜底回答"
    assert len(calls) == 2
    first_call, second_call = calls
    assert first_call["enable_thinking"] is True
    assert second_call["enable_thinking"] is False
    assert float(second_call["timeout_seconds"]) >= 20.0
    assert int(second_call["max_tokens"]) <= 600
    assert len(str(second_call["prompt"])) < len(str(first_call["prompt"]))


def test_build_chat_generation_profile_prefers_shorter_first_answer_budget(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    service = AiService(db, {"qwen": SimpleNamespace()})

    profile = service._build_chat_generation_profile("背景信息" * 900)

    assert profile.primary_timeout_seconds >= 30.0
    assert profile.primary_max_tokens <= 900
    assert profile.fallback_timeout_seconds >= 16.0
    assert profile.fallback_max_tokens <= 420


def test_batch_failure_falls_through_to_per_field(tmp_path: Path, monkeypatch):
    """Phase 1.5: 批量 _qwen_generate 抛错时,不再 raise AiInvocationError 整批兜底,
    而是落到现成的逐字段 generate_template_field_value(thinking关/小prompt/稳)。"""
    db = Database(tmp_path / "app.db")
    service = AiService(db, {"qwen": SimpleNamespace()})

    monkeypatch.setattr(
        service, "get_health",
        lambda: AiHealth(provider="qwen", provider_label="Qwen", base_url="http://x",
                         model="m", ready=True, detail="ok",
                         credential_source="local", fingerprint=None),
    )

    # 批量调用必失败(模拟大复合字段 45s 超时)
    def boom(**_: object):
        raise RuntimeError("simulated batch timeout")
    monkeypatch.setattr(service, "_qwen_generate", boom)

    # 逐字段方法返回可识别哨兵值
    calls = []
    def fake_single(*, field_label, **_):
        calls.append(field_label)
        return f"单字段填好-{field_label}"
    monkeypatch.setattr(service, "generate_template_field_value", fake_single)

    # 不应抛 AiInvocationError;应返回逐字段结果
    values = service.generate_template_field_values_batch(
        template_name="模板.docx", client_name="为爱黔行",
        field_contexts=[
            ("13. 主要服务内容/活动安排", "ctx13"),
            ("14. 项目特点与创新点", "ctx14"),
            ("15. 实施计划与关键节点", "ctx15"),
        ],
    )
    # 批量失败 → 全部走逐字段(3 个都被单独调用)
    assert calls == ["13. 主要服务内容/活动安排", "14. 项目特点与创新点", "15. 实施计划与关键节点"]
    assert values["13. 主要服务内容/活动安排"] == "单字段填好-13. 主要服务内容/活动安排"
    assert values["15. 实施计划与关键节点"] == "单字段填好-15. 实施计划与关键节点"
    # 关键:没有任何字段拿到"整批兜底"(build_fast_missing_value 的【待确认】)
    assert all("单字段填好" in v for v in values.values())
