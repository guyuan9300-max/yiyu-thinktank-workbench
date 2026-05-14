"""Outline-First 多段生成的单测。

覆盖：
- _parse_outline_json：原始 JSON / ```json fence / 前缀解释 / 空 / 非法 / 数组
- _compose_markdown：headline + 多段拼装
- plan_workspace_answer_outline：成功 / Pass1 抛错 / 返回非 dict / sections 缺失
- generate_workspace_answer_section：成功 / 抛错 / 空字符串
- generate_multipass_answer：Pass1 失败传播 / 全段成功 / 中途失败保留前段 / callback 触发顺序
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.workspace_chat_multipass import (  # noqa: E402
    AnswerOutline,
    MultipassPlanError,
    SectionPlan,
    _compose_markdown,
    _parse_outline_json,
    generate_multipass_answer,
    generate_workspace_answer_section,
    plan_workspace_answer_outline,
)


# ---- 工具单测 ------------------------------------------------------------


class TestParseOutlineJson:
    def test_plain_json(self) -> None:
        assert _parse_outline_json('{"a": 1}') == {"a": 1}

    def test_with_markdown_fence(self) -> None:
        assert _parse_outline_json("```json\n{\"a\":1}\n```") == {"a": 1}

    def test_with_prefix_text(self) -> None:
        assert _parse_outline_json("Sure:\n{\"a\":1}\nthat's it") == {"a": 1}

    def test_empty_returns_none(self) -> None:
        assert _parse_outline_json("") is None

    def test_invalid_returns_none(self) -> None:
        assert _parse_outline_json("not json at all 哈哈") is None

    def test_array_returns_none(self) -> None:
        # 顶层不是 dict 算失败
        assert _parse_outline_json('[1,2,3]') is None


class TestComposeMarkdown:
    def test_empty_returns_empty(self) -> None:
        assert _compose_markdown("h", [], []) == ""

    def test_single_section_no_heading(self) -> None:
        md = _compose_markdown(
            "整体判断",
            [SectionPlan(title="第一段")],
            ["这是第一段的正文。"],
        )
        assert "# 整体判断" in md
        assert "## 第一段" not in md  # 第一段不打 ##
        assert "这是第一段的正文。" in md

    def test_multiple_sections_with_headings(self) -> None:
        md = _compose_markdown(
            "总论断",
            [SectionPlan(title="A"), SectionPlan(title="B"), SectionPlan(title="C")],
            ["正文 A", "正文 B", "正文 C"],
        )
        assert md.startswith("# 总论断")
        assert "## B" in md
        assert "## C" in md
        assert "## A" not in md  # 第一段不带 heading
        assert "正文 A" in md and "正文 B" in md and "正文 C" in md


# ---- Pass 1 单测 ---------------------------------------------------------


class _AiServiceStub:
    """模拟 AiService 的最小表面 —— 只需要 _qwen_generate 方法。"""
    def __init__(
        self,
        *,
        outline_response: str | None = None,
        section_responses: list[str | Exception] | None = None,
        raise_on_outline: Exception | None = None,
    ) -> None:
        self.outline_response = outline_response
        self.section_responses = list(section_responses or [])
        self.raise_on_outline = raise_on_outline
        self.calls: list[dict[str, Any]] = []

    def _qwen_generate(  # noqa: SLF001
        self,
        prompt: str,
        system_instruction: str,
        response_schema: Any,
        **kwargs: Any,
    ) -> str:
        self.calls.append({
            "prompt": prompt[:80],
            "is_outline": response_schema is not None,
            "max_tokens": kwargs.get("max_tokens"),
        })
        if response_schema is not None:
            if self.raise_on_outline is not None:
                raise self.raise_on_outline
            return self.outline_response or ""
        # section call
        if not self.section_responses:
            return "默认段正文（fallback）。"
        next_response = self.section_responses.pop(0)
        if isinstance(next_response, Exception):
            raise next_response
        return str(next_response)


class TestPlanOutline:
    def test_success(self) -> None:
        outline_json = json.dumps({
            "headline": "战略走差异化路径",
            "judgmentLine": "聚焦预防前置 + 资产化沉淀",
            "sections": [
                {"title": "差异化定位", "hints": ["不走干预", "锚定预防"]},
                {"title": "第二曲线布局", "hints": ["场域资产", "数据资产"]},
            ],
        }, ensure_ascii=False)
        stub = _AiServiceStub(outline_response=outline_json)

        outline = plan_workspace_answer_outline(
            question="日慈基金会战略有什么特点",
            background_pack="客户：日慈基金会...",
            evidence_summary="资料命中 21 条",
            ai_service=stub,
        )
        assert outline.headline == "战略走差异化路径"
        assert outline.judgment_line == "聚焦预防前置 + 资产化沉淀"
        assert len(outline.sections) == 2
        assert outline.sections[0].title == "差异化定位"
        assert outline.sections[0].hints == ("不走干预", "锚定预防")
        assert len(stub.calls) == 1
        assert stub.calls[0]["is_outline"] is True

    def test_call_failure_raises_plan_error(self) -> None:
        stub = _AiServiceStub(raise_on_outline=RuntimeError("network died"))
        with pytest.raises(MultipassPlanError, match="Pass1 调用失败"):
            plan_workspace_answer_outline(
                question="x",
                background_pack="",
                evidence_summary="",
                ai_service=stub,
            )

    def test_invalid_json_raises(self) -> None:
        stub = _AiServiceStub(outline_response="not json")
        with pytest.raises(MultipassPlanError, match="无法解析为 JSON"):
            plan_workspace_answer_outline(
                question="x",
                background_pack="",
                evidence_summary="",
                ai_service=stub,
            )

    def test_missing_sections_raises(self) -> None:
        stub = _AiServiceStub(outline_response=json.dumps({"headline": "x"}))
        with pytest.raises(MultipassPlanError, match="sections"):
            plan_workspace_answer_outline(
                question="x",
                background_pack="",
                evidence_summary="",
                ai_service=stub,
            )

    def test_all_sections_filtered_raises(self) -> None:
        stub = _AiServiceStub(outline_response=json.dumps({
            "headline": "x",
            "sections": [{"hints": []}],  # title 缺失 → 跳过
        }))
        with pytest.raises(MultipassPlanError, match="sections 全部解析失败"):
            plan_workspace_answer_outline(
                question="x",
                background_pack="",
                evidence_summary="",
                ai_service=stub,
            )

    def test_max_sections_truncation(self) -> None:
        outline = json.dumps({
            "headline": "h",
            "sections": [{"title": f"段{i}"} for i in range(8)],
        }, ensure_ascii=False)
        stub = _AiServiceStub(outline_response=outline)
        result = plan_workspace_answer_outline(
            question="x",
            background_pack="",
            evidence_summary="",
            ai_service=stub,
            max_sections=4,
        )
        assert len(result.sections) == 4


# ---- Pass 2-N 单测 -------------------------------------------------------


class TestGenerateSection:
    def test_success(self) -> None:
        stub = _AiServiceStub(section_responses=["这是第一段的正文，详细描述了差异化定位。"])
        text = generate_workspace_answer_section(
            question="战略特点",
            section_plan=SectionPlan(title="差异化定位", hints=("不走干预",)),
            section_index=0,
            total_sections=3,
            headline="走差异化",
            judgment_line="锚定预防",
            full_context="完整背景包 + 资料",
            previous_section_recaps=[],
            ai_service=stub,
        )
        assert "差异化定位" in text
        assert stub.calls[0]["is_outline"] is False

    def test_failure_raises(self) -> None:
        stub = _AiServiceStub(section_responses=[RuntimeError("oops")])
        with pytest.raises(RuntimeError, match="第 1 段调用失败"):
            generate_workspace_answer_section(
                question="x", section_plan=SectionPlan(title="A"),
                section_index=0, total_sections=2,
                headline="h", judgment_line="j",
                full_context="ctx", previous_section_recaps=[],
                ai_service=stub,
            )

    def test_empty_response_raises(self) -> None:
        stub = _AiServiceStub(section_responses=["   "])
        with pytest.raises(RuntimeError, match="返回为空"):
            generate_workspace_answer_section(
                question="x", section_plan=SectionPlan(title="A"),
                section_index=0, total_sections=2,
                headline="h", judgment_line="j",
                full_context="ctx", previous_section_recaps=[],
                ai_service=stub,
            )

    def test_on_partial_called(self) -> None:
        stub = _AiServiceStub(section_responses=["text"])
        partials: list[dict[str, Any]] = []
        generate_workspace_answer_section(
            question="x", section_plan=SectionPlan(title="A"),
            section_index=1, total_sections=4,
            headline="h", judgment_line="j",
            full_context="ctx", previous_section_recaps=[],
            ai_service=stub,
            on_partial=partials.append,
        )
        assert len(partials) == 1
        assert "第 2/4 段" in partials[0]["stageLabel"]


# ---- 编排器单测 ----------------------------------------------------------


class TestGenerateMultipassAnswer:
    def _make_stub(self, sections: list[str | Exception]) -> _AiServiceStub:
        outline = json.dumps({
            "headline": "整体走差异化",
            "judgmentLine": "锚定预防 + 资产化",
            "sections": [
                {"title": f"段 {i + 1}", "hints": []}
                for i in range(len(sections))
            ],
        }, ensure_ascii=False)
        return _AiServiceStub(outline_response=outline, section_responses=sections)

    def test_full_success(self) -> None:
        stub = self._make_stub([
            "第一段正文，提到具体项目名 X 和合作方 Y。",
            "第二段正文，引用数字 30%。",
            "第三段正文，谈时间节点 2026 Q2。",
        ])
        result = generate_multipass_answer(
            question="日慈战略有什么特点",
            background_pack="客户：日慈",
            evidence_summary="资料 21 条",
            full_context="完整 context",
            ai_service=stub,
        )
        assert result.sections_generated == 3
        assert result.failure_stage is None
        assert result.llm_attempt_count == 4  # 1 outline + 3 sections
        assert "# 整体走差异化" in result.markdown
        assert "第一段正文" in result.markdown
        assert "## 段 2" in result.markdown
        assert "## 段 3" in result.markdown

    def test_pass1_failure_propagates(self) -> None:
        stub = _AiServiceStub(raise_on_outline=RuntimeError("Pass1 挂了"))
        with pytest.raises(MultipassPlanError):
            generate_multipass_answer(
                question="x", background_pack="", evidence_summary="",
                full_context="ctx", ai_service=stub,
            )

    def test_mid_section_failure_preserves_earlier(self) -> None:
        stub = self._make_stub([
            "第一段成功。",
            RuntimeError("第二段挂了"),
            "永远到不了的第三段",
        ])
        result = generate_multipass_answer(
            question="x", background_pack="", evidence_summary="",
            full_context="ctx", ai_service=stub,
        )
        assert result.sections_generated == 1
        assert result.failure_stage == "section_2"
        assert "第一段成功。" in result.markdown
        assert "第二段" not in result.markdown
        assert "第三段" not in result.markdown

    def test_first_section_failure(self) -> None:
        stub = self._make_stub([RuntimeError("从头挂")])
        result = generate_multipass_answer(
            question="x", background_pack="", evidence_summary="",
            full_context="ctx", ai_service=stub,
        )
        assert result.sections_generated == 0
        assert result.failure_stage == "section_1"
        assert result.markdown == ""  # 没成段不输出

    def test_callbacks_invoked_in_order(self) -> None:
        stub = self._make_stub(["A", "B"])
        events: list[tuple[str, Any]] = []
        result = generate_multipass_answer(
            question="x", background_pack="", evidence_summary="",
            full_context="ctx", ai_service=stub,
            on_outline_ready=lambda o: events.append(("outline_ready", o.headline)),
            on_section_started=lambda i, p: events.append(("section_started", i)),
            on_section_completed=lambda i, t, txt: events.append(("section_completed", i)),
        )
        kinds = [e[0] for e in events]
        assert kinds[0] == "outline_ready"
        assert ("section_started", 0) in events
        assert ("section_completed", 0) in events
        assert ("section_started", 1) in events
        assert ("section_completed", 1) in events
        # 顺序约束：outline_ready 在所有 section_* 之前
        assert kinds.index("outline_ready") < min(i for i, e in enumerate(events) if e[0] == "section_started")
        assert result.sections_generated == 2
