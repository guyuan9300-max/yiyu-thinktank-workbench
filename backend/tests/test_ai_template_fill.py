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
