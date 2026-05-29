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

    def test_python_repr_with_single_quotes(self) -> None:
        # 实测豆包等模型偶尔返回 Python repr 字典（单引号），ast.literal_eval 兜底
        result = _parse_outline_json(
            "{'headline': '战略锚定心理公益', 'judgmentLine': '深耕预防层', "
            "'sections': [{'title': '差异化定位', 'hints': ['锚定预防', '场域生长']}]}"
        )
        assert result is not None
        assert result["headline"] == "战略锚定心理公益"
        assert result["sections"][0]["title"] == "差异化定位"
        assert result["sections"][0]["hints"][0] == "锚定预防"

    def test_python_repr_with_fence(self) -> None:
        result = _parse_outline_json(
            "```python\n{'headline': 'X', 'sections': [{'title': 'A'}]}\n```"
        )
        assert result is not None
        assert result["headline"] == "X"


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
    """模拟 AiService 的最小表面 —— 提供 _qwen_generate 和 _qwen_generate_streaming。

    section_responses 同时被两个方法消费：
    - _qwen_generate：整段同步返回
    - _qwen_generate_streaming：把响应拆成 chunk 流式 callback，再返回完整文本

    chunk_size 控制流式 stub 每次 push 多少字符（默认 12）。
    """
    def __init__(
        self,
        *,
        outline_response: str | None = None,
        section_responses: list[str | Exception] | None = None,
        raise_on_outline: Exception | None = None,
        chunk_size: int = 12,
    ) -> None:
        self.outline_response = outline_response
        self.section_responses = list(section_responses or [])
        self.raise_on_outline = raise_on_outline
        self.chunk_size = chunk_size
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
            "full_prompt": prompt,
            "system_instruction": system_instruction,
            "is_outline": response_schema is not None,
            "is_streaming": False,
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

    def _qwen_generate_streaming(  # noqa: SLF001
        self,
        prompt: str,
        system_instruction: str,
        *,
        on_token: Any = None,
        **kwargs: Any,
    ) -> str:
        """流式 stub：从 section_responses 拿下一条响应，拆 chunk 调用 on_token。"""
        self.calls.append({
            "prompt": prompt[:80],
            "full_prompt": prompt,
            "system_instruction": system_instruction,
            "is_outline": False,
            "is_streaming": True,
            "max_tokens": kwargs.get("max_tokens"),
        })
        if not self.section_responses:
            response = "默认段流式正文（fallback）。"
        else:
            next_response = self.section_responses.pop(0)
            if isinstance(next_response, Exception):
                raise next_response
            response = str(next_response)
        # 拆 chunk 逐个推 on_token
        if on_token is not None:
            for start in range(0, len(response), self.chunk_size):
                chunk = response[start:start + self.chunk_size]
                if chunk:
                    on_token(chunk)
        return response


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
            question="A组织战略有什么特点",
            background_pack="客户：A组织...",
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
        with pytest.raises(MultipassPlanError, match="Pass1 调用 3 次都失败"):
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

    def test_strategic_pack_injected_into_prompt(self) -> None:
        """传入 strategic_pack 时，user prompt 应包含 STRATEGIC 标记和内容。"""
        outline = json.dumps({"headline": "h", "sections": [{"title": "A"}]}, ensure_ascii=False)
        stub = _AiServiceStub(outline_response=outline)
        plan_workspace_answer_outline(
            question="A组织战略特点",
            background_pack="客户：A组织",
            evidence_summary="命中 10 条",
            ai_service=stub,
            strategic_pack="【战略素材包】DNA：差异化定位 = 前置心理教育",
        )
        full_prompt = stub.calls[0]["full_prompt"]
        assert "<<<STRATEGIC>>>" in full_prompt
        assert "<<<END STRATEGIC>>>" in full_prompt
        assert "差异化定位 = 前置心理教育" in full_prompt
        # 同时确认 system_instruction 引导了"优先用战略素材"
        assert "战略素材" in stub.calls[0]["system_instruction"]

    def test_empty_strategic_pack_keeps_prompt_clean(self) -> None:
        """不传 strategic_pack（默认空）时，user prompt 不应有 STRATEGIC 标记。"""
        outline = json.dumps({"headline": "h", "sections": [{"title": "A"}]}, ensure_ascii=False)
        stub = _AiServiceStub(outline_response=outline)
        plan_workspace_answer_outline(
            question="x",
            background_pack="bg",
            evidence_summary="ev",
            ai_service=stub,
        )
        full_prompt = stub.calls[0]["full_prompt"]
        assert "<<<STRATEGIC>>>" not in full_prompt
        # background / evidence 块仍然在
        assert "<<<BACKGROUND>>>" in full_prompt
        assert "<<<EVIDENCE>>>" in full_prompt

    def test_strategic_pack_truncated_to_budget(self) -> None:
        """传超长 strategic_pack，应被截断到 13000 字以内（R2 扩大了预算）。"""
        outline = json.dumps({"headline": "h", "sections": [{"title": "A"}]}, ensure_ascii=False)
        stub = _AiServiceStub(outline_response=outline)
        huge_pack = "战略素材" * 8000  # 32000 字
        plan_workspace_answer_outline(
            question="x",
            background_pack="",
            evidence_summary="",
            ai_service=stub,
            strategic_pack=huge_pack,
        )
        full_prompt = stub.calls[0]["full_prompt"]
        # 提取 STRATEGIC 块的内容
        start_marker = "<<<STRATEGIC>>>\n"
        end_marker = "\n<<<END STRATEGIC>>>"
        start = full_prompt.index(start_marker) + len(start_marker)
        end = full_prompt.index(end_marker)
        strategic_content_in_prompt = full_prompt[start:end]
        assert len(strategic_content_in_prompt) <= 13000
        # 同时确认确实有截断（不是全量塞入）
        assert len(strategic_content_in_prompt) < len(huge_pack)


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
        # R4 流式：至少 2 个 partial（开头 stageLabel + 结尾完整 content）
        # token 太少不会触发 throttle 中间 push，所以最少 2 个
        assert len(partials) >= 2
        # 第一个 partial 是 stageLabel
        assert "第 2/4 段" in partials[0]["stageLabel"]
        # 最后一个 partial 含完整内容
        assert partials[-1].get("content") == "text"

    def test_streaming_call_pushes_accumulated_partials(self) -> None:
        """R4：generate_workspace_answer_section 用流式调用，on_partial 在生成过程中
        被多次触发，每次 content 是累计文本（不断增长）。"""
        full_text = "第一段正文。" + "X" * 200  # 200+ 字，确保会触发多次 throttle push
        stub = _AiServiceStub(section_responses=[full_text], chunk_size=20)
        partials: list[dict[str, Any]] = []
        result = generate_workspace_answer_section(
            question="x",
            section_plan=SectionPlan(title="差异化定位"),
            section_index=0,
            total_sections=3,
            headline="h",
            judgment_line="j",
            full_context="ctx",
            previous_section_recaps=[],
            ai_service=stub,
            on_partial=partials.append,
        )
        # 调用走 streaming
        assert stub.calls[0]["is_streaming"] is True
        # on_partial 应该被多次触发（开头 stageLabel + 多个 streaming partial + 最终 streaming=False）
        assert len(partials) >= 2
        # 至少有一个 partial 是 streaming=True
        streaming_partials = [p for p in partials if p.get("streaming") is True]
        assert streaming_partials, "应该有至少一个 streaming=True 的 partial"
        # 累计文本必须递增
        contents = [p.get("content", "") for p in streaming_partials]
        for prev, curr in zip(contents, contents[1:]):
            assert len(curr) >= len(prev), f"流式 content 应递增 prev={len(prev)} curr={len(curr)}"
        # 最终 partial（streaming=False）含完整内容
        final_partials = [p for p in partials if p.get("streaming") is False]
        assert final_partials, "应该有 streaming=False 的最终 partial"
        assert final_partials[-1].get("content") == full_text
        # 返回值也是完整内容
        assert result == full_text

    def test_streaming_failure_raises_with_attempt_info(self) -> None:
        """流式调用失败时抛 RuntimeError 包含段号 + 用时（保持与旧版兼容的错误格式）。"""
        stub = _AiServiceStub(section_responses=[RuntimeError("network died")])
        with pytest.raises(RuntimeError, match="第 1 段调用失败"):
            generate_workspace_answer_section(
                question="x", section_plan=SectionPlan(title="A"),
                section_index=0, total_sections=2,
                headline="h", judgment_line="j",
                full_context="ctx", previous_section_recaps=[],
                ai_service=stub,
            )

    def test_section_instruction_contains_formatting_guidance(self) -> None:
        """R3：Pass 2 system_instruction 必须包含'分段/列表/加粗'等排版引导，
        防止 LLM 写出 1000-1500 字的文字墙。"""
        stub = _AiServiceStub(section_responses=["正文。"])
        generate_workspace_answer_section(
            question="x", section_plan=SectionPlan(title="差异化定位"),
            section_index=0, total_sections=3,
            headline="h", judgment_line="j",
            full_context="ctx", previous_section_recaps=[],
            ai_service=stub,
        )
        instruction = stub.calls[0]["system_instruction"]
        # 排版引导关键词必须出现
        assert "子段落" in instruction or "分段" in instruction
        assert "列表" in instruction
        assert "粗体" in instruction or "加粗" in instruction
        # 同时确认未硬编码框架（不应该出现 SWOT / 三飞轮 / PEST 这类强制结构）
        assert "SWOT" not in instruction
        assert "PEST" not in instruction
        # 注：'三飞轮'是A组织业务里 LLM 可能自然引用的概念，不应在 prompt 里硬编码强制
        # 但作为「角度引导」的间接提及不可避免，所以这里只挡掉 SWOT/PEST 这种通用框架


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
            question="A组织战略有什么特点",
            background_pack="客户：A组织",
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

    def test_strategic_pack_reaches_both_passes(self) -> None:
        """strategic_pack 同时进入 Pass 1 prompt 和 Pass 2 的 full_context 头部。"""
        stub = self._make_stub(["第一段正文。", "第二段正文。"])
        strategic = "【战略素材包】DNA：差异化定位 = 前置心理教育"
        generate_multipass_answer(
            question="x",
            background_pack="bg",
            evidence_summary="ev",
            full_context="原始资料原文",
            ai_service=stub,
            strategic_pack=strategic,
        )
        # 第 0 次调用是 Pass 1（is_outline=True）
        pass1_prompt = stub.calls[0]["full_prompt"]
        assert "<<<STRATEGIC>>>" in pass1_prompt
        assert "差异化定位 = 前置心理教育" in pass1_prompt
        # 第 1+ 次调用是 Pass 2 各段（is_outline=False），其 full_prompt 应含战略素材前置块
        pass2_prompts = [c["full_prompt"] for c in stub.calls[1:] if c["is_outline"] is False]
        assert pass2_prompts, "应有至少一次 Pass 2 调用"
        for pass2_prompt in pass2_prompts:
            assert "【战略素材摘要" in pass2_prompt
            assert "差异化定位 = 前置心理教育" in pass2_prompt
            assert "【原始背景与证据原文】" in pass2_prompt
            assert "原始资料原文" in pass2_prompt

    def test_writing_skill_md_injected_into_pass2_system_instruction(self) -> None:
        """R6：writing_skill_md 通过编排器透传给每段 Pass 2 调用，注入到 section_instruction 最顶部。"""
        stub = self._make_stub(["段一正文。", "段二正文。"])
        skill_md = "## 罗永浩风格\n长短句猛烈交错；段子手节奏；自嘲式诚意感。"
        generate_multipass_answer(
            question="x",
            background_pack="bg",
            evidence_summary="ev",
            full_context="ctx",
            ai_service=stub,
            writing_skill_md=skill_md,
        )
        # Pass 2 调用（is_outline=False）的 system_instruction 必须含风格块
        pass2_systems = [c["system_instruction"] for c in stub.calls if c["is_outline"] is False]
        assert pass2_systems
        for instr in pass2_systems:
            assert "写作风格约束" in instr
            assert "罗永浩风格" in instr
            assert "长短句猛烈交错" in instr
        # Pass 1 大纲不应包含风格块（大纲跟风格无关）
        pass1_systems = [c["system_instruction"] for c in stub.calls if c["is_outline"] is True]
        assert pass1_systems
        for instr in pass1_systems:
            assert "罗永浩风格" not in instr

    def test_creativity_mode_creative_skips_strategic_pack_in_pass2(self) -> None:
        """R7：creative 档 Pass 2 完全不喂 strategic_pack + full_context（即使传入也不进 prompt）"""
        stub = self._make_stub(["段一。", "段二。"])
        generate_multipass_answer(
            question="x",
            background_pack="bg",
            evidence_summary="ev",
            full_context="客户原始资料",
            ai_service=stub,
            strategic_pack="战略素材内容",
            creativity_mode="creative",
        )
        pass2_prompts = [c["full_prompt"] for c in stub.calls if c["is_outline"] is False]
        pass2_systems = [c["system_instruction"] for c in stub.calls if c["is_outline"] is False]
        assert pass2_prompts
        for prompt in pass2_prompts:
            assert "客户原始资料" not in prompt
            assert "战略素材内容" not in prompt
        for instr in pass2_systems:
            assert "创意优先" in instr
            assert "通用 LLM" in instr or "豆包通用窗口" in instr

    def test_creativity_mode_creative_skips_all_client_data_in_pass1(self) -> None:
        """R7.10：creative 档 Pass 1 出大纲时也不能看到任何客户资料
        （strategic_pack / background_pack / evidence_summary 全部清空），
        否则大纲里会出现客户专有名词导致 Pass 2 编造客户专属内容。"""
        stub = self._make_stub(["段一。", "段二。"])
        generate_multipass_answer(
            question="给25岁自己写信",
            background_pack="客户档案：A组织",
            evidence_summary="繁星计划相关证据",
            full_context="客户原始资料",
            ai_service=stub,
            strategic_pack="DNA + 繁星计划 + 青年支持计划",
            creativity_mode="creative",
        )
        # Pass 1 调用（is_outline=True）的 prompt 必须不含任何客户资料
        pass1_prompts = [c["full_prompt"] for c in stub.calls if c["is_outline"] is True]
        assert pass1_prompts
        for prompt in pass1_prompts:
            assert "A组织" not in prompt
            assert "繁星计划" not in prompt
            assert "青年支持计划" not in prompt
            assert "客户档案" not in prompt
            assert "DNA" not in prompt
            assert "战略素材" not in prompt

    def test_creativity_mode_balanced_keeps_resources_with_balanced_block(self) -> None:
        """R7：balanced 档 Pass 2 喂 strategic_pack + full_context，system 含「事实是骨头」"""
        stub = self._make_stub(["段一。"])
        generate_multipass_answer(
            question="x",
            background_pack="bg",
            evidence_summary="ev",
            full_context="原始资料 X",
            ai_service=stub,
            strategic_pack="战略素材 Y",
            creativity_mode="balanced",
        )
        pass2_prompts = [c["full_prompt"] for c in stub.calls if c["is_outline"] is False]
        pass2_systems = [c["system_instruction"] for c in stub.calls if c["is_outline"] is False]
        for prompt in pass2_prompts:
            assert "原始资料 X" in prompt or "战略素材 Y" in prompt
        for instr in pass2_systems:
            assert "兼顾资料" in instr
            assert "事实是骨头" in instr or "语言是血肉" in instr

    def test_creativity_mode_strict_injects_strict_constraints_in_pass2(self) -> None:
        """R7：strict 档 Pass 2 system 含「完全客观/溯源标记」"""
        stub = self._make_stub(["段一。"])
        generate_multipass_answer(
            question="x",
            background_pack="bg",
            evidence_summary="ev",
            full_context="ctx",
            ai_service=stub,
            creativity_mode="strict",
        )
        pass2_systems = [c["system_instruction"] for c in stub.calls if c["is_outline"] is False]
        for instr in pass2_systems:
            assert "完全客观" in instr or "严格模式" in instr
            assert "溯源标记" in instr or "[资料" in instr

    def test_no_writing_skill_md_keeps_pass2_clean(self) -> None:
        """不传 writing_skill_md 时，Pass 2 system_instruction 不出现风格块。"""
        stub = self._make_stub(["段一。"])
        generate_multipass_answer(
            question="x",
            background_pack="bg",
            evidence_summary="ev",
            full_context="ctx",
            ai_service=stub,
        )
        pass2_systems = [c["system_instruction"] for c in stub.calls if c["is_outline"] is False]
        assert pass2_systems
        for instr in pass2_systems:
            assert "写作风格约束" not in instr

    def test_no_strategic_pack_keeps_pass2_context_unchanged(self) -> None:
        """不传 strategic_pack 时，Pass 2 full_context 应保持原样（无包装头）。"""
        stub = self._make_stub(["段一。"])
        generate_multipass_answer(
            question="x",
            background_pack="bg",
            evidence_summary="ev",
            full_context="原始资料 ABC",
            ai_service=stub,
        )
        pass2_prompts = [c["full_prompt"] for c in stub.calls if c["is_outline"] is False]
        assert pass2_prompts
        for pass2_prompt in pass2_prompts:
            assert "【战略素材摘要" not in pass2_prompt
            assert "原始资料 ABC" in pass2_prompt

    def test_mid_section_failure_preserves_earlier(self) -> None:
        # 第 2 段 retry 共 3 次都失败才放弃（multipass 加了 retry）
        stub = self._make_stub([
            "第一段成功。",
            RuntimeError("第二段挂了 attempt1"),
            RuntimeError("第二段挂了 attempt2"),
            RuntimeError("第二段挂了 attempt3"),
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
        # 第 1 段 retry 共 3 次都失败
        stub = self._make_stub([
            RuntimeError("从头挂 1"),
            RuntimeError("从头挂 2"),
            RuntimeError("从头挂 3"),
        ])
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
