from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

import httpx

from app.db import Database
from app.models import AiStructuredResponse


DEFAULT_PROVIDER = "mock"
DEFAULT_MODELS = {
    "mock": "mock-summarizer",
    "qwen": "qwen3.5-plus",
}
DEFAULT_MODEL = DEFAULT_MODELS[DEFAULT_PROVIDER]
QWEN_BASE_URL = "https://coding.dashscope.aliyuncs.com/v1"


@dataclass
class AiHealth:
    provider: str
    model: str
    ready: bool
    detail: str
    credential_source: str
    fingerprint: str | None = None


class AiInvocationError(RuntimeError):
    def __init__(self, provider: str, detail: str):
        super().__init__(detail)
        self.provider = provider
        self.detail = detail


class AiService:
    def __init__(self, db: Database, secret_stores: dict[str, object]):
        self.db = db
        self.secret_stores = secret_stores
        provider = self.db.get_setting("ai_provider", DEFAULT_PROVIDER)
        if provider not in DEFAULT_MODELS:
            provider = DEFAULT_PROVIDER
        self.db.set_setting("ai_provider", provider)
        self.db.set_setting("ai_model", self.db.get_setting("ai_model", DEFAULT_MODELS[provider]) or DEFAULT_MODELS[provider])

    def current_provider(self) -> str:
        provider = self.db.get_setting("ai_provider", DEFAULT_PROVIDER)
        return provider if provider in DEFAULT_MODELS else DEFAULT_PROVIDER

    def current_model(self) -> str:
        model = self.db.get_setting("ai_model", "")
        return model or DEFAULT_MODELS[self.current_provider()]

    def configure(self, provider: str | None, model: str | None, api_key: str | None, clear_api_key: bool) -> None:
        target_provider = provider or self.current_provider()
        if target_provider not in DEFAULT_MODELS:
            target_provider = DEFAULT_PROVIDER
        if provider:
            self.db.set_setting("ai_provider", target_provider)
            if not model:
                self.db.set_setting("ai_model", DEFAULT_MODELS[target_provider])
        if model:
            self.db.set_setting("ai_model", model)
        store = self._store_for(target_provider)
        if clear_api_key and store:
            store.delete_api_key()
        if api_key and store:
            store.set_api_key(api_key)

    def get_health(self) -> AiHealth:
        provider = self.current_provider()
        model = self.current_model()
        if provider == "mock":
            return AiHealth(
                provider=provider,
                model=DEFAULT_MODELS["mock"],
                ready=True,
                detail="当前使用本地 mock 推演器，可稳定支撑桌面端流程联调。",
                credential_source="local",
                fingerprint=None,
            )
        store = self._store_for(provider)
        source = store.get_source_label() if store else "unavailable"
        fingerprint = store.get_api_key_fingerprint() if store else None
        api_key = store.get_api_key() if store else ""
        if not api_key:
            return AiHealth(
                provider=provider,
                model=model,
                ready=False,
                detail="Qwen 3.5 未配置 API Key，当前只能切回 mock。",
                credential_source=source,
                fingerprint=fingerprint,
            )
        return AiHealth(
            provider=provider,
            model=model,
            ready=True,
            detail="Qwen 3.5 凭证已配置，可用于结构化问答与分析。",
            credential_source=source,
            fingerprint=fingerprint,
        )

    def test_connection(self) -> AiHealth:
        health = self.get_health()
        if health.provider == "mock" or not health.ready:
            return health
        self._qwen_generate(
            prompt="请用一句中文确认连接成功。",
            system_instruction="你是系统健康检查助手。只返回纯文本。",
            response_schema=None,
        )
        return AiHealth(
            provider=health.provider,
            model=health.model,
            ready=True,
            detail="Qwen 3.5 联通测试成功。",
            credential_source=health.credential_source,
            fingerprint=health.fingerprint,
        )

    def generate_structured(self, prompt: str, system_instruction: str, context_summary: str) -> AiStructuredResponse:
        health = self.get_health()
        if health.provider == "qwen" and health.ready:
            return self._qwen_generate_structured_with_retry(prompt, system_instruction, context_summary)
        return self._mock_generate(prompt, context_summary)

    def generate_general_fallback(self, prompt: str, note: str = "", *, subject_name: str = "") -> AiStructuredResponse:
        health = self.get_health()
        if health.provider == "qwen" and health.ready:
            try:
                return self._qwen_generate_general_fallback(prompt, note, subject_name=subject_name)
            except Exception as error:
                raise AiInvocationError("qwen", self._format_provider_error(error)) from error
        return self._mock_generate(prompt, note or "当前资料回答阶段失败，以下为本地保守兜底判断。")

    def generate_chat_response(
        self,
        prompt: str,
        system_instruction: str,
        context_summary: str,
        *,
        on_partial: Callable[[dict[str, Any]], None] | None = None,
    ) -> AiStructuredResponse:
        health = self.get_health()
        if health.provider == "qwen" and health.ready:
            if on_partial is not None:
                opening = "正在围绕核心判断、关键张力和潜在风险整合原始证据，准备输出连续长文分析。"
                on_partial(
                    {
                        "stageLabel": "正在整合长文分析",
                        "progress": 58.0,
                        "content": opening,
                        "structured": {
                            "content": opening,
                            "judgment": "",
                            "analysis": "",
                            "actions": "",
                            "timeline": "",
                        },
                    }
                )
            try:
                return self._qwen_generate_chat_response(
                    prompt,
                    system_instruction,
                    context_summary,
                    on_partial=on_partial,
                )
            except Exception as error:
                primary_error = error
                try:
                    return self._qwen_generate_textual_fallback(
                        prompt,
                        system_instruction,
                        context_summary,
                        timeout_seconds=110.0,
                        max_tokens=5200,
                    )
                except Exception as retry_error:
                    detail = "；".join(
                        part
                        for part in (
                            f"主长文生成失败：{self._format_provider_error(primary_error)}",
                            f"长文重试失败：{self._format_provider_error(retry_error)}",
                        )
                        if part
                    )
                    raise AiInvocationError("qwen", detail) from retry_error
        return self._mock_generate(prompt, context_summary)

    def generate_topic_candidate_chat_response(
        self,
        prompt: str,
        system_instruction: str,
        context_summary: str,
    ) -> AiStructuredResponse:
        health = self.get_health()
        compact_context = self._compact_context_summary(context_summary, max_chars=1600)
        quick_instruction = (
            f"{system_instruction}\n"
            "这是资讯情报站里的追问，不是长文写作。"
            "请先直接回答用户最关心的问题，再补 1 到 2 层解释。"
            "默认控制在 220 到 420 字内，最多 3 小段。"
            "优先讲清楚：它解决什么问题、对谁有用、为什么值得关心、落地会卡在哪。"
            "少讲空泛趋势，少做宏大评论，不要写成长文分析。"
            "不要输出 JSON 或 Markdown 代码块。"
        )
        if health.provider == "qwen" and health.ready:
            try:
                text = self._qwen_generate(
                    prompt=f"用户问题：{prompt}\n\n当前情报背景：\n{compact_context}",
                    system_instruction=quick_instruction,
                    response_schema=None,
                    timeout_seconds=16.0,
                    max_tokens=1100,
                    temperature=0.35,
                    top_p=0.9,
                    enable_thinking=False,
                )
                return self._structured_from_plain_answer(str(text))
            except Exception as error:
                try:
                    return self._qwen_generate_brief_grounded_rescue(prompt, compact_context or context_summary)
                except Exception as rescue_error:
                    detail = "；".join(
                        part
                        for part in (
                            f"资讯快答失败：{self._format_provider_error(error)}",
                            f"简短兜底失败：{self._format_provider_error(rescue_error)}",
                        )
                        if part
                    )
                    raise AiInvocationError("qwen", detail) from rescue_error
        return self._mock_generate(prompt, compact_context or context_summary)

    def generate_template_field_value(
        self,
        *,
        field_label: str,
        template_name: str,
        client_name: str,
        context_summary: str,
        field_type: str | None = None,
    ) -> str:
        health = self.get_health()
        field_rule = self._template_field_rule(field_type)
        system_instruction = (
            "你正在为客户资料模板填写单个字段。"
            "请只输出可以直接粘贴进 Word 文档的最终内容，不要解释过程，不要写'根据资料'、'建议填写'、'可写为'这类前缀。"
            "如果资料不足，请只输出“【待确认】”开头的一句简短提示。"
            "不要输出“可从……进一步梳理”“建议补充”“可填写为”这类过程性提示。"
            "不要输出 Markdown 代码块，不要输出 JSON。"
        )
        prompt = (
            f"客户：{client_name}\n"
            f"模板：{template_name}\n"
            f"待填写字段：{field_label}\n\n"
            f"字段类型：{field_type or 'general'}\n"
            f"字段要求：{field_rule}\n\n"
            f"可参考材料：\n{context_summary.strip()}\n\n"
            "请直接给出这个字段应填写的内容。"
        )
        if health.provider == "qwen" and health.ready:
            try:
                text = self._qwen_generate(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    response_schema=None,
                    timeout_seconds=26.0,
                    max_tokens=700,
                    temperature=0.28,
                    top_p=0.9,
                    enable_thinking=False,
                )
                return self._clean_template_field_value(str(text), field_type=field_type)
            except Exception as first_error:
                compact_context = context_summary.strip()[:2400]
                try:
                    text = self._qwen_generate(
                        prompt=(
                            f"客户：{client_name}\n"
                            f"模板：{template_name}\n"
                            f"待填写字段：{field_label}\n\n"
                            f"字段类型：{field_type or 'general'}\n"
                            f"字段要求：{field_rule}\n\n"
                            f"可参考材料：\n{compact_context}\n\n"
                            "请直接给出这个字段应填写的内容。"
                        ),
                        system_instruction=system_instruction,
                        response_schema=None,
                        timeout_seconds=14.0,
                        max_tokens=420,
                        temperature=0.22,
                        top_p=0.88,
                        enable_thinking=False,
                    )
                    return self._clean_template_field_value(str(text), field_type=field_type)
                except Exception as second_error:
                    raise AiInvocationError(
                        "qwen",
                        "；".join(
                            part
                            for part in (
                                f"字段填写主调用失败：{self._format_provider_error(first_error)}",
                                f"字段填写紧凑重试失败：{self._format_provider_error(second_error)}",
                            )
                            if part
                        ),
                    ) from second_error
        fallback = context_summary.strip().splitlines()
        best_line = next((line.strip() for line in fallback if line.strip()), "")
        return self._clean_template_field_value(best_line or "【待确认】当前缺少可直接填写该字段的资料。", field_type=field_type)

    def generate_template_field_values_batch(
        self,
        *,
        template_name: str,
        client_name: str,
        field_contexts: list[tuple[str, str]],
        field_types: dict[str, str] | None = None,
    ) -> dict[str, str]:
        if not field_contexts:
            return {}
        health = self.get_health()
        labels = [label for label, _ in field_contexts]
        schema = {
            "type": "OBJECT",
            "properties": {label: {"type": "STRING"} for label in labels},
            "required": labels,
        }
        system_instruction = (
            "你正在为客户资料模板批量填写多个字段。"
            "每个字段都带有它自己的参考材料。"
            "请严格返回一个 JSON 对象，键必须和字段名完全一致。"
            "每个值都必须是可直接粘贴进 Word 文档的最终内容，不要加解释或前缀。"
            "如果资料不足，该字段值只输出“【待确认】”开头的一句简短提示。"
            "不要输出 Markdown 代码块，不要输出 JSON 以外的任何内容。"
        )
        prompt_blocks: list[str] = []
        for index, (label, context_summary) in enumerate(field_contexts, start=1):
            current_type = str((field_types or {}).get(label) or "general")
            prompt_blocks.append(
                (
                    f"[字段 {index}]\n"
                    f"字段名：{label}\n"
                    f"字段类型：{current_type}\n"
                    f"字段要求：{self._template_field_rule(current_type)}\n"
                    "只填写这个字段，不要引用其他字段。\n"
                    f"{context_summary.strip()}"
                ).strip()
            )
        prompt = (
            f"客户：{client_name}\n"
            f"模板：{template_name}\n"
            f"字段总数：{len(field_contexts)}\n\n"
            "请分别填写以下字段，并返回 JSON 对象：\n\n"
            + "\n\n".join(prompt_blocks)
        )
        if health.provider == "qwen" and health.ready:
            try:
                payload = self._qwen_generate(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    response_schema=schema,
                    timeout_seconds=75.0,
                    max_tokens=min(4200, max(1800, 520 * len(field_contexts))),
                    temperature=0.28,
                    top_p=0.9,
                    enable_thinking=False,
                )
            except Exception as error:
                raise AiInvocationError("qwen", self._format_provider_error(error)) from error
            if isinstance(payload, dict):
                return {
                    label: self._clean_template_field_value(
                        str(payload.get(label) or "【待确认】当前缺少可直接填写该字段的资料。"),
                        field_type=str((field_types or {}).get(label) or "general"),
                    )
                    for label in labels
                }
        return {
            label: self.generate_template_field_value(
                field_label=label,
                template_name=template_name,
                client_name=client_name,
                context_summary=context_summary,
                field_type=str((field_types or {}).get(label) or "general"),
            )
            for label, context_summary in field_contexts
        }

    def _qwen_generate_chat_response(
        self,
        prompt: str,
        system_instruction: str,
        context_summary: str,
        *,
        on_partial: Callable[[dict[str, Any]], None] | None = None,
    ) -> AiStructuredResponse:
        detailed_context = str(context_summary or "").strip()
        base_instruction = (
            f"{system_instruction}\n"
            "你现在是在直接回答用户，不要把答案写成系统产物。"
            "请把后面的原始材料当作你已经完整读过的材料直接使用。"
            "不要解释检索过程、系统过程、命中规则或技术细节。"
            "不要满足于字面摘录、材料摘要或安全概括。"
            "请主动做更高层的综合判断，讲清因果关系、结构性矛盾、关键张力、利益约束、风险与机会。"
            "允许把多条材料共同指向的信号组织成更高层的结论。"
            "除非用户明确要求简短，否则请尽量展开。"
            "你可以自由决定长度、结构、段落、小标题和结尾方式。"
            "只有材料里没有出现过的具体事实、数字、人名、时间和身份，不要直接写成已被证实。"
            "不要输出 JSON 或 Markdown 代码块。"
        )
        errors: list[str] = []
        try:
            if on_partial is not None:
                on_partial(
                    {
                        "stageLabel": "正在直接生成长文回答",
                        "progress": 62.0,
                        "content": "千问正在基于完整材料直接生成长文回答。",
                        "structured": {
                            "content": "千问正在基于完整材料直接生成长文回答。",
                            "judgment": "",
                            "analysis": "",
                            "actions": "",
                            "timeline": "",
                        },
                    }
                )
            text = self._qwen_generate(
                prompt=f"用户问题：{prompt}\n\n参考材料：\n{detailed_context}",
                system_instruction=base_instruction,
                response_schema=None,
                timeout_seconds=180.0,
                max_tokens=7600,
                temperature=0.48,
                top_p=0.96,
                enable_thinking=True,
            )
            return self._structured_from_plain_answer(str(text))
        except Exception as error:
            errors.append(self._format_provider_error(error))
        try:
            return self._qwen_generate_textual_fallback(
                prompt,
                system_instruction,
                detailed_context,
                timeout_seconds=140.0,
                max_tokens=6200,
            )
        except Exception as error:
            errors.append(f"长文重试仍失败：{self._format_provider_error(error)}")
        raise AiInvocationError("qwen", "；".join(part for part in errors if part))

    def _qwen_generate_progressive_chat_response(
        self,
        prompt: str,
        system_instruction: str,
        context_summary: str,
        *,
        on_partial: Callable[[dict[str, Any]], None] | None = None,
    ) -> AiStructuredResponse:
        focus_context = self._compact_context_summary(context_summary, max_chars=2800)
        analysis_context = self._compact_context_summary(context_summary, max_chars=5200)
        action_context = self._compact_context_summary(context_summary, max_chars=3200)
        base_instruction = (
            f"{system_instruction}\n"
            "你现在要分阶段写成一版完整顾问回答。"
            "每个阶段都直接服务最终成文，不要解释系统过程，也不要输出技术细节。"
            "不要使用 JSON 或 Markdown 代码块。"
            "优先写得深、清楚、有判断。"
        )

        def emit_partial(stage_label: str, progress: float, content: str, *, judgment: str = "", analysis: str = "", actions: str = "") -> None:
            if on_partial is None:
                return
            on_partial(
                {
                    "stageLabel": stage_label,
                    "progress": progress,
                    "content": content.strip(),
                    "structured": {
                        "content": content.strip(),
                        "judgment": judgment.strip(),
                        "analysis": analysis.strip(),
                        "actions": actions.strip(),
                        "timeline": "",
                    },
                }
            )

        errors: list[str] = []
        opener_text = ""
        title = ""
        judgment = ""
        analysis_text = ""
        actions_text = ""

        try:
            opener_text = str(
                self._qwen_generate(
                    prompt=(
                        f"问题：{prompt}\n\n"
                        f"顾问底稿：\n{focus_context}\n\n"
                        "请先写出回答的开场部分。"
                        "如果你觉得需要标题就写，不需要就直接进入正文。"
                        "这部分要直接回答问题，并自然点出最重要的主线、判断或观察。不要为了格式而格式化。"
                    ),
                    system_instruction=(
                        f"{base_instruction}\n"
                        "这一阶段只负责把回答开头写出来。"
                    ),
                    response_schema=None,
                    timeout_seconds=8.0,
                    max_tokens=720,
                    temperature=0.42,
                    top_p=0.96,
                    enable_thinking=False,
                )
            ).strip()
        except Exception as error:
            errors.append(f"开场判断失败：{self._format_provider_error(error)}")
        if not opener_text:
            raise AiInvocationError("qwen", "；".join(errors) or "分阶段生成未返回开场判断")

        extracted_title = self._extract_segment_field(opener_text, ("标题", "题目"))
        title = re.sub(r"\s+", " ", extracted_title or "").strip()[:24]
        judgment = self._extract_segment_field(opener_text, ("总判断", "判断")) or opener_text
        partial_content = "\n\n".join(part for part in [title, judgment] if part.strip())
        emit_partial("正在形成开场判断", 62.0, partial_content, judgment=judgment)

        try:
            analysis_text = str(
                self._qwen_generate(
                    prompt=(
                        f"问题：{prompt}\n\n"
                        f"顾问底稿：\n{analysis_context}\n\n"
                        f"当前总判断：\n{judgment}\n\n"
                        "请继续完成主体分析。"
                        "由你自己判断最适合这道问题的展开方式，可以用自然段，也可以用小标题。"
                        "尽量把真正值得展开的部分讲透，而不是把所有可能方向平均铺开。"
                        "不要复述材料标题，不要把回答写成资料摘要。"
                    ),
                    system_instruction=(
                        f"{base_instruction}\n"
                        "这一阶段只负责把主体内容写深、写透。"
                    ),
                    response_schema=None,
                    timeout_seconds=14.0,
                    max_tokens=1600,
                    temperature=0.42,
                    top_p=0.95,
                    enable_thinking=False,
                )
            ).strip()
        except Exception as error:
            errors.append(f"主体分析失败：{self._format_provider_error(error)}")

        analysis_density = len(re.sub(r"\s+", "", analysis_text))
        if analysis_density < 260:
            try:
                rescue_text = str(
                    self._qwen_generate(
                        prompt=(
                            f"问题：{prompt}\n\n"
                            f"顾问底稿：\n{analysis_context}\n\n"
                            f"已有总判断：\n{judgment}\n\n"
                        "请补写主体分析。"
                        "如果已有主体内容偏短，就继续把最值得展开的部分补深。"
                        "不需要机械补齐固定小节，也不要反复围绕同一个判断来回改写。"
                        "你可以自由决定是继续展开已有主线，还是补进新的关键分析面。"
                    ),
                    system_instruction=(
                        f"{base_instruction}\n"
                        "这一阶段是主体内容补写。"
                    ),
                    response_schema=None,
                    timeout_seconds=10.0,
                    max_tokens=1200,
                    temperature=0.4,
                    top_p=0.95,
                    enable_thinking=False,
                )
            ).strip()
                if len(re.sub(r"\s+", "", rescue_text)) > analysis_density:
                    analysis_text = rescue_text
                    analysis_density = len(re.sub(r"\s+", "", analysis_text))
            except Exception as error:
                errors.append(f"主体分析补写失败：{self._format_provider_error(error)}")

        if analysis_text:
            partial_content = "\n\n".join(part for part in [title, judgment, analysis_text] if part.strip())
            emit_partial("正在展开主体分析", 79.0, partial_content, judgment=judgment, analysis=analysis_text)

        try:
            actions_text = str(
                self._qwen_generate(
                    prompt=(
                        f"问题：{prompt}\n\n"
                        f"顾问底稿：\n{action_context}\n\n"
                        f"已有总判断：\n{judgment}\n\n"
                        "请完成回答的收束部分。"
                        "由你自己判断最自然的结束方式。"
                        "如果适合给建议、优先级或下一步，就写出来；如果不适合，就自然收束，不要强行加动作。"
                    ),
                    system_instruction=(
                        f"{base_instruction}\n"
                        "这一阶段只负责完成回答的结尾。"
                    ),
                    response_schema=None,
                    timeout_seconds=8.0,
                    max_tokens=560,
                    temperature=0.38,
                    top_p=0.94,
                    enable_thinking=False,
                )
            ).strip()
        except Exception as error:
            errors.append(f"建议动作失败：{self._format_provider_error(error)}")

        if not analysis_text and not actions_text:
            raise AiInvocationError("qwen", "；".join(errors) or "分阶段生成只返回了开场判断")

        assembled_parts = [title, judgment]
        if analysis_text:
            assembled_parts.append(analysis_text)
        if actions_text:
            assembled_parts.append(actions_text)
        content = "\n\n".join(part.strip() for part in assembled_parts if part and part.strip())
        emit_partial("正在整理最终成文", 91.0, content, judgment=judgment, analysis=analysis_text, actions=actions_text)
        return self._structured_from_plain_answer(content)

    def generate_compact_grounded_fallback(self, prompt: str, note: str) -> AiStructuredResponse:
        health = self.get_health()
        if health.provider == "qwen" and health.ready:
            try:
                return self._qwen_generate_compact_grounded_fallback(prompt, note)
            except Exception as error:
                raise AiInvocationError("qwen", self._format_provider_error(error)) from error
        return self._mock_generate(prompt, note or "基于已命中资料的紧凑综述。")

    def generate_brief_grounded_rescue(self, prompt: str, note: str) -> AiStructuredResponse:
        health = self.get_health()
        if health.provider == "qwen" and health.ready:
            try:
                return self._qwen_generate_brief_grounded_rescue(prompt, note)
            except Exception as error:
                raise AiInvocationError("qwen", self._format_provider_error(error)) from error
        return self._mock_generate(prompt, note or "基于已命中资料的一版简短保守回答。")

    def suggest_short_title(self, prompt: str) -> str:
        health = self.get_health()
        try:
            if health.provider == "qwen" and health.ready:
                result = self._qwen_generate(
                    prompt=f"请将以下追踪规则提炼为 3 到 6 个字的中文标签，只返回标签本身：{prompt}",
                    system_instruction="你是中文编辑，擅长压缩标题。",
                    response_schema=None,
                    timeout_seconds=12.0,
                )
                title = str(result).strip().replace("“", "").replace("”", "")
                if title:
                    return title[:8]
        except Exception:
            pass
        cleaned = re.sub(r"[，。；：、,.!?！？\\s]+", "", prompt)
        cleaned = re.sub(r"^(关注|跟踪|追踪|围绕|关于)", "", cleaned)
        return (cleaned[:6] or "自定义雷达").strip()

    def suggest_topic_search_queries(self, *, title: str, prompt: str, time_range: str) -> list[str]:
        health = self.get_health()
        fallback = self._fallback_topic_search_queries(title=title, prompt=prompt, time_range=time_range)
        schema = {
            "type": "OBJECT",
            "properties": {
                "queries": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                }
            },
        }
        query_prompt = (
            "请把下面的资讯追踪需求提炼成 2 到 3 条适合新闻/信息搜索的中文查询词。"
            "要求：保留核心对象、行业和技术关键词，避免空泛词。"
            "返回 JSON：{\"queries\": [\"查询1\", \"查询2\"]}。\n"
            f"雷达标题：{title}\n"
            f"追踪说明：{prompt}\n"
            f"时间范围：{time_range}\n"
        )
        try:
            if health.provider == "qwen" and health.ready:
                result = self._qwen_generate(
                    query_prompt,
                    "你是检索词生成助手。只返回 JSON。",
                    schema,
                    timeout_seconds=18.0,
                    max_tokens=600,
                )
                if isinstance(result, dict):
                    queries = [str(item).strip() for item in result.get("queries", []) if str(item).strip()]
                    if queries:
                        return queries[:3]
        except Exception:
            pass
        return fallback

    def shortlist_topic_search_hits(
        self,
        *,
        title: str,
        prompt: str,
        hits: list[dict[str, str]],
        max_items: int = 4,
    ) -> list[dict[str, object]]:
        if not hits:
            return []
        health = self.get_health()
        schema = {
            "type": "OBJECT",
            "properties": {
                "items": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "index": {"type": "INTEGER"},
                            "title": {"type": "STRING"},
                            "summary": {"type": "STRING"},
                        },
                    },
                }
            },
        }
        entries = []
        for index, hit in enumerate(hits, start=1):
            entries.append(
                "\n".join(
                    [
                        f"[{index}] 标题：{hit.get('title', '')}",
                        f"来源：{hit.get('source', '')}",
                        f"发布时间：{hit.get('publishedAt', '') or '未知'}",
                        f"摘要：{hit.get('summary', '')}",
                    ]
                )
            )
        joined_entries = "\n\n".join(entries)
        screening_prompt = (
            "你是资讯情报筛选助手。请根据雷达标题和追踪说明，从候选结果中挑选最相关的结果。"
            f"最多返回 {max_items} 条，优先保留真正相关、可转成选题候选的条目，明显跑题的不要选。"
            "title 要写成 10 到 28 个字的中文标题；如果原文不是中文，要准确翻译成中文。"
            "summary 要写成 40 到 90 字的中文摘要，适合直接落到候选池。"
            "返回 JSON：{\"items\": [{\"index\": 1, \"title\": \"...\", \"summary\": \"...\"}]}\n"
            f"雷达标题：{title}\n"
            f"追踪说明：{prompt}\n"
            f"候选结果：\n{joined_entries}"
        )
        try:
            if health.provider == "qwen" and health.ready:
                result = self._qwen_generate(
                    screening_prompt,
                    "你是资讯情报筛选助手。只返回 JSON。",
                    schema,
                    timeout_seconds=25.0,
                    max_tokens=1400,
                )
                if isinstance(result, dict):
                    items = result.get("items", [])
                    if isinstance(items, list):
                        return [item for item in items if isinstance(item, dict)][:max_items]
        except Exception:
            pass
        return []

    def localize_topic_hit(
        self,
        *,
        title: str,
        summary: str,
        radar_title: str,
        radar_prompt: str,
    ) -> dict[str, str]:
        cleaned_title = str(title or "").strip()
        cleaned_summary = str(summary or cleaned_title).strip() or cleaned_title
        if self._has_sufficient_cjk(cleaned_title) and self._has_sufficient_cjk(cleaned_summary):
            return {
                "title": cleaned_title[:60],
                "summary": cleaned_summary[:140],
            }
        health = self.get_health()
        schema = {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING"},
                "summary": {"type": "STRING"},
            },
        }
        prompt = (
            "请把下面这条资讯候选整理成适合内部候选池展示的中文标题和中文摘要。"
            "如果原文不是中文，请准确翻译成中文；不要编造没有出现过的事实。"
            "title 保持 10 到 28 个中文字符；summary 保持 40 到 90 个中文字符。"
            "返回 JSON：{\"title\": \"中文标题\", \"summary\": \"中文摘要\"}\n"
            f"雷达标题：{radar_title}\n"
            f"雷达说明：{radar_prompt}\n"
            f"原始标题：{cleaned_title}\n"
            f"原始摘要：{cleaned_summary}\n"
        )
        try:
            if health.provider == "qwen" and health.ready:
                result = self._qwen_generate(
                    prompt,
                    "你是资讯翻译编辑助手。只返回 JSON。",
                    schema,
                    timeout_seconds=20.0,
                    max_tokens=800,
                )
                if isinstance(result, dict):
                    localized_title = str(result.get("title") or "").strip()
                    localized_summary = str(result.get("summary") or "").strip()
                    if localized_title and localized_summary:
                        return {
                            "title": localized_title[:60],
                            "summary": localized_summary[:140],
                        }
        except Exception:
            pass
        fallback_title = cleaned_title[:60]
        if not self._has_sufficient_cjk(fallback_title):
            fallback_title = f"{radar_title}相关机会"
        fallback_summary = cleaned_summary[:140]
        if not self._has_sufficient_cjk(fallback_summary):
            fallback_summary = f"原始来源提到“{cleaned_title[:40]}”，建议打开原文核对后再决定是否跟进。"
        return {"title": fallback_title, "summary": fallback_summary}

    def build_topic_candidate_insight(
        self,
        *,
        candidate_title: str,
        candidate_summary: str,
        source: str,
        published_at: str | None,
        source_url: str | None,
        source_content: str,
        organization_context: str = "",
    ) -> dict[str, object]:
        health = self.get_health()
        schema = {
            "type": "OBJECT",
            "properties": {
                "overview": {"type": "STRING"},
                "keyPoints": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                },
                "recommendationReasons": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                },
                "practicalUses": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                },
                "editorialNote": {"type": "STRING"},
                "discussionPrompts": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                },
            },
        }
        prompt = (
            "请把下面这条资讯候选整理成适合内部团队阅读的中文解析。"
            "输出要求：\n"
            "1. overview 用 140 到 220 字中文，聚焦“文章本身在讲什么”，必须讲清楚文章主线、它明确提出的关键观点，以及文中出现的事实或案例线索；不要把你的评论混进这一段。\n"
            "2. keyPoints 返回 3 到 5 条，每条都是清晰完整的一句话，提炼文章作者真正表达的核心观点、方法、信号或判断，不要泛泛复述主题。\n"
            "3. recommendationReasons 返回 2 到 4 条，直接说明这东西到底解决什么问题、对谁有用、能省哪一步、能创造什么具体价值。少写空泛大词，少写“值得关注”“可以参考”。\n"
            "4. editorialNote 用 180 到 320 字中文，写成“大周自己的判断”，但口气要像一个懂产品的人在给同事讲这东西到底有什么用。先讲清楚它解决什么问题，再讲它创造什么价值，最后点出真正值得继续看的地方或局限。语气口语化、直接，不要写成新闻评论、官方口径或行业社论；少用“这反映出”“结构性变化”“专业能力民主化”这种宏大套话。\n"
            "4a. 如果材料是 GitHub 开源项目、产品 demo、工具发布或技术案例，优先回答 4 个问题：它到底替谁省事、具体省掉哪一步、为什么这一步值钱、什么情况下才真的能用。不要先从行业趋势和组织变革讲起。\n"
            "5. practicalUses 返回 2 到 4 条，改写成“可直接展开成文的角度”。每条都应该像文章切口、评论角度或分享主题，而不是待办动作。\n"
            "6. discussionPrompts 返回 2 到 4 条，写成值得继续追问的问题句，优先从产品价值、用户场景、落地门槛、替代关系和真实使用条件继续追问。\n"
            "7. 只根据现有材料输出，不要编造文章里没有出现过的事实；如果材料有限，可以做克制推断，但要避免装作已经证实。\n"
            "8. 即使原文是英文，overview、keyPoints、recommendationReasons、editorialNote、practicalUses、discussionPrompts 也必须全部输出中文。\n"
            "9. 优先提炼文章里的关键事实、方法变化、商业机会、行业门槛、组织能力要求或资源线索；不要只写“值得关注”“可以参考”这种空话。\n"
            f"候选标题：{candidate_title}\n"
            f"候选摘要：{candidate_summary}\n"
            f"来源：{source}\n"
            f"发布时间：{published_at or '未知'}\n"
            f"原文链接：{source_url or '无'}\n"
            f"组织 DNA：{organization_context[:1400] or '未提供'}\n"
            f"原文摘录：{(source_content or '未抓到原文全文，只有标题和摘要。')[:4200]}"
        )
        try:
            if health.provider == "qwen" and health.ready:
                result = self._qwen_generate(
                    prompt,
                    "你是资讯研判助手。只返回 JSON。",
                    schema,
                    timeout_seconds=28.0,
                    max_tokens=1800,
                )
                if isinstance(result, dict):
                    normalized = self._normalize_topic_candidate_insight_payload(result)
                    if normalized["keyPoints"]:
                        return self._localize_topic_insight_payload(
                            normalized,
                            candidate_title=candidate_title,
                            candidate_summary=candidate_summary,
                            source=source,
                            published_at=published_at,
                            source_url=source_url,
                            source_content=source_content,
                        )
        except Exception:
            pass
        fallback = self._fallback_topic_candidate_insight(
            candidate_title=candidate_title,
            candidate_summary=candidate_summary,
            source=source,
            published_at=published_at,
            source_url=source_url,
            source_content=source_content,
        )
        return self._localize_topic_insight_payload(
            fallback,
            candidate_title=candidate_title,
            candidate_summary=candidate_summary,
            source=source,
            published_at=published_at,
            source_url=source_url,
            source_content=source_content,
        )

    def build_topic_task_plan(
        self,
        *,
        candidate_title: str,
        candidate_summary: str,
        source: str,
        published_at: str | None,
        source_url: str | None,
        source_content: str,
        candidate_insight: dict[str, object] | None = None,
        organization_context: str = "",
    ) -> dict[str, object]:
        health = self.get_health()
        today_iso = datetime.now().date().isoformat()
        schema = {
            "type": "OBJECT",
            "properties": {
                "overview": {"type": "STRING"},
                "tasks": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "title": {"type": "STRING"},
                            "desc": {"type": "STRING"},
                            "dueDate": {"type": "STRING"},
                            "ddl": {"type": "STRING"},
                            "note": {"type": "STRING"},
                            "priority": {"type": "STRING"},
                            "tags": {
                                "type": "ARRAY",
                                "items": {"type": "STRING"},
                            },
                        },
                    },
                },
            },
        }
        prompt = (
            "请根据下面的资讯候选，拆成可以直接派给同事执行的中文任务清单。"
            "输出要求：\n"
            "1. overview 用 40 到 90 字中文说明这条机会为什么值得跟进。\n"
            "2. tasks 返回 1 到 6 条可执行任务，title 必须是具体动作，不要写空泛标题。\n"
            "3. desc 用一句中文说明交付物或动作标准。\n"
            "4. dueDate 只有在材料里出现明确截止日期或时间时才填写 YYYY-MM-DD，否则留空字符串。\n"
            "5. ddl 用中文简短表达，如“3月17日前”“本周内”“待确认”。\n"
            "6. note 写补充说明，包含来源线索、限制条件或需要特别注意的点，并明确这条任务对应的推荐理由或判断依据。\n"
            "7. priority 只能是 low、normal、high。\n"
            "8. tags 返回 1 到 3 个中文标签。\n"
            "9. 任务优先从 recommendationReasons 和 practicalUses 延展开来，避免与推荐理由无关的空泛动作。\n"
            "请只根据已知材料输出，不要编造不存在的要求。\n"
            f"今天日期：{today_iso}\n"
            f"候选标题：{candidate_title}\n"
            f"候选摘要：{candidate_summary}\n"
            f"来源：{source}\n"
            f"发布时间：{published_at or '未知'}\n"
            f"原文链接：{source_url or '无'}\n"
            f"组织 DNA：{organization_context[:1400] or '未提供'}\n"
            f"候选解析综述：{str((candidate_insight or {}).get('overview') or '无')}\n"
            f"主要内涵：{'；'.join(str(item) for item in (candidate_insight or {}).get('keyPoints', [])[:6]) or '无'}\n"
            f"推荐理由：{'；'.join(str(item) for item in (candidate_insight or {}).get('recommendationReasons', [])[:4]) or '无'}\n"
            f"实用方向：{'；'.join(str(item) for item in (candidate_insight or {}).get('practicalUses', [])[:4]) or '无'}\n"
            f"原文摘录：{(source_content or '未抓到原文全文，只有标题和摘要。')[:3600]}"
        )
        try:
            if health.provider == "qwen" and health.ready:
                result = self._qwen_generate(
                    prompt,
                    "你是项目执行拆解助手。只返回 JSON。",
                    schema,
                    timeout_seconds=28.0,
                    max_tokens=1800,
                )
                if isinstance(result, dict):
                    normalized = self._normalize_topic_task_plan_payload(result)
                    if normalized["tasks"]:
                        return normalized
        except Exception:
            pass
        return self._fallback_topic_task_plan(
            candidate_title=candidate_title,
            candidate_summary=candidate_summary,
            source=source,
            published_at=published_at,
            source_url=source_url,
            source_content=source_content,
            candidate_insight=candidate_insight,
        )

    def suggest_task_tags(
        self,
        *,
        title: str,
        desc: str,
        collaborator_names: list[str],
        due_date: str | None,
        module: str,
    ) -> list[str]:
        health = self.get_health()
        prompt = (
            "请根据下面的任务信息，提炼 1 到 3 个简短中文标签。"
            "标签必须具体可读，不要输出“事务、工作、内容、处理”这种空泛词。"
            "只返回 JSON，格式为 {\"tags\": [\"标签1\", \"标签2\"]}。\n"
            f"标题：{title}\n"
            f"描述：{desc or '无'}\n"
            f"协作对象：{'、'.join(collaborator_names) or '无'}\n"
            f"截止日期：{due_date or '未设置'}\n"
            f"所属模块：{module}\n"
        )
        try:
            if health.provider == "qwen" and health.ready:
                result = self._qwen_generate(
                    prompt=prompt,
                    system_instruction="你是任务标签编辑助手。只返回 JSON。",
                    response_schema={
                        "type": "OBJECT",
                        "properties": {
                            "tags": {
                                "type": "ARRAY",
                                "items": {"type": "STRING"},
                            }
                        },
                    },
                    timeout_seconds=18.0,
                )
                if isinstance(result, dict):
                    tags = [str(item).strip() for item in result.get("tags", []) if str(item).strip()]
                    if tags:
                        return tags[:3]
        except Exception:
            pass

        fallback_tags: list[str] = []
        text = f"{title} {desc}"
        mapping = [
            ("会议", ["会议", "复盘", "纪要"]),
            ("客户沟通", ["客户", "沟通", "访谈"]),
            ("材料整理", ["材料", "文档", "整理", "汇总"]),
            ("审核", ["审核", "审批", "确认"]),
            ("汇报", ["汇报", "报告", "简报", "ppt"]),
            ("高优先级", ["紧急", "高优", "优先"]),
            ("本周完成", ["本周", "周五", "周内"]),
        ]
        for label, keywords in mapping:
            if any(keyword.lower() in text.lower() for keyword in keywords) and label not in fallback_tags:
                fallback_tags.append(label)
        if due_date and not fallback_tags:
            fallback_tags.append("待确认")
        if not fallback_tags:
            fallback_tags = ["跟进中"]
        return fallback_tags[:3]

    def _normalize_topic_task_plan_payload(self, payload: dict[str, object]) -> dict[str, object]:
        overview = str(payload.get("overview") or "").strip()
        raw_tasks = payload.get("tasks", [])
        tasks: list[dict[str, object]] = []
        if isinstance(raw_tasks, list):
            for item in raw_tasks:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()
                if not title:
                    continue
                due_date = self._normalize_due_date_value(item.get("dueDate"))
                ddl = str(item.get("ddl") or "").strip()
                tasks.append(
                    {
                        "title": title[:60],
                        "desc": str(item.get("desc") or "").strip()[:180],
                        "dueDate": due_date,
                        "ddl": ddl or (self._label_due_date(due_date) if due_date else "待确认"),
                        "note": str(item.get("note") or "").strip()[:280],
                        "priority": self._normalize_priority(item.get("priority")),
                        "tags": [
                            str(tag).strip()[:16]
                            for tag in item.get("tags", [])
                            if str(tag).strip()
                        ][:3]
                        if isinstance(item.get("tags"), list)
                        else [],
                    }
                )
        return {
            "overview": overview[:140],
            "tasks": tasks,
        }

    def _normalize_topic_candidate_insight_payload(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "overview": str(payload.get("overview") or "").strip()[:420],
            "keyPoints": self._normalize_string_list(payload.get("keyPoints"), max_items=6, max_length=220),
            "recommendationReasons": self._normalize_string_list(payload.get("recommendationReasons"), max_items=4, max_length=180),
            "practicalUses": self._normalize_string_list(payload.get("practicalUses"), max_items=4, max_length=160),
            "editorialNote": str(payload.get("editorialNote") or "").strip()[:520],
            "discussionPrompts": self._normalize_string_list(payload.get("discussionPrompts"), max_items=4, max_length=180),
        }

    def _enrich_topic_insight_payload(
        self,
        payload: dict[str, object],
        *,
        candidate_title: str,
        candidate_summary: str,
        source: str,
        source_content: str,
    ) -> dict[str, object]:
        normalized = self._normalize_topic_candidate_insight_payload(payload)
        if self._looks_like_weak_topic_material(candidate_title, candidate_summary, source_content):
            source_hint = self._extract_topic_source_hint(candidate_title, candidate_summary)
            normalized["overview"] = (
                f"一、当前判断：这条候选暂时不能被当成一篇有效行业文章来解读。现有材料只显示原始来源提到了“{source_hint}”，"
                "更像是搜索结果误抓到的索引页、行情页或无关网页，而不是围绕当前雷达主题展开的正文内容。\n"
                "二、为什么不能直接使用：现在没有足够可靠的正文信息可供提炼，因此无法负责任地总结它的主要观点，也无法证明它对团队真的有实际价值。"
                "如果继续基于这条候选拆任务，后续执行方向很容易被带偏。\n"
                "三、对团队最有价值的动作：先复核来源链接、确认是否误抓取，并在必要时删除、归档或重新抓取更相关的中文文章；这比继续围绕一条错候选展开讨论更重要。"
            )[:420]
            normalized["keyPoints"] = [
                "当前没有抓到足够可靠的正文内容，现有信息不足以支持严肃的主题研判。",
                "候选里出现的线索更像搜索误抓到的索引页或无关页面，不像真正围绕雷达主题展开的文章。",
                "如果继续基于这条结果拆任务，后续执行方向很容易被带偏。",
            ]
            normalized["recommendationReasons"] = [
                "先识别并拦住误抓取结果，本身就是保证情报质量的重要一步。",
                "这条结果反过来说明当前雷达关键词或过滤规则还需要继续收紧。",
            ]
            normalized["practicalUses"] = [
                "把这次误抓取写成一篇“为什么情报系统容易被噪音带偏”的方法反思。",
                "围绕“如何判断一条线索是否值得进入候选池”整理一套内部筛选标准。",
                "把这条错候选当成案例，讨论应该怎样收紧雷达描述、时间窗和优先网址策略。",
            ]
            normalized["editorialNote"] = (
                "真正值得警惕的不是这条候选本身，而是它暴露出的情报系统误抓风险。"
                "当抓取链路把索引页、无关页或弱线索误当成正文时，团队后续的判断、讨论甚至任务安排都会建立在错误底稿上。"
                "这提醒我们：高质量情报站不仅要会抓，还要会及时识别噪音、收紧规则，并把“为什么这条内容不值得看”也沉淀成方法论。"
            )[:520]
            normalized["discussionPrompts"] = [
                "这条候选是因为搜索词过宽、时间窗失效，还是站点解析规则不准才进入候选池？",
                "如果以后再遇到类似噪音，系统应该在哪一层把它挡掉，而不是等人工兜底？",
                "哪些判断信号可以帮助我们更早识别“看起来像资讯、其实不是正文”的结果？",
            ]
            return normalized

        overview = str(normalized.get("overview") or "").strip()
        filtered_key_points = [
            item for item in normalized["keyPoints"]
            if not self._looks_like_topic_noise(item, candidate_title)
        ]
        if not filtered_key_points:
            filtered_key_points = self._extract_topic_source_sentences(source_content, candidate_title, max_items=4)
        if filtered_key_points:
            normalized["keyPoints"] = filtered_key_points[:6]

        summary_text = ""
        if self._has_sufficient_cjk(candidate_summary) and not self._looks_like_topic_noise(candidate_summary, candidate_title):
            summary_text = self._compact_topic_sentence(candidate_summary, 180)
        elif filtered_key_points:
            summary_text = "；".join(self._compact_topic_sentence(item, 90) for item in filtered_key_points[:2])
        elif overview and not self._looks_generic_topic_overview(overview):
            summary_text = self._compact_topic_sentence(overview, 180)
        else:
            summary_text = f"这篇内容围绕“{candidate_title[:32]}”展开，当前抓到的材料显示它更关注该主题背后的关键事实、方法线索或可执行信息。"

        key_points = normalized["keyPoints"][:3]
        point_text = "；".join(self._compact_topic_sentence(item, 110) for item in key_points) if key_points else "当前提炼结果尚未形成足够具体的文章观点。"

        reasons = normalized["recommendationReasons"][:2]
        reason_text = "；".join(self._compact_topic_sentence(item, 90) for item in reasons) if reasons else "需要进一步核对原文后再决定是否值得跟进。"

        normalized["overview"] = (
            f"一、这篇内容主要讲什么：{summary_text}\n"
            f"二、文章里最值得抓住的观点：{point_text}\n"
            f"三、它对团队的实际价值：{reason_text}"
        )[:420]
        focus_text = f"{candidate_title} {candidate_summary} {source_content}".lower()
        source_sentences = self._extract_topic_source_sentences(source_content, candidate_title, max_items=4)
        editorial_note = str(normalized.get("editorialNote") or "").strip()
        generic_editorial_note = self._looks_generic_topic_editorial_note(editorial_note)
        needs_grounded_editorial_note = not editorial_note or len(editorial_note) < 120 or generic_editorial_note
        if needs_grounded_editorial_note:
            if re.search(r"(资助|基金|grant|申请|申报|征集|招募|报名|捐赠)", focus_text, re.I):
                editorial_note = (
                    "如果把这类信息当成一个产品线索来看，它解决的不是“有没有机会”这么简单，而是告诉你：外部资方现在到底按什么标准筛人。"
                    "它真正的价值，是帮团队少走弯路，早点看清楚申请方最看重的是项目逻辑、执行证据，还是机构叙事。"
                    "所以大周更在意的不是窗口又多了一个，而是这篇内容有没有把评估口径讲明白；如果讲明白了，它就能直接反过来指导我们准备材料、补能力、改表达。"
                )
            elif re.search(r"(安全|风控|风险|攻击|漏洞|泄露|合规|防护|权限|越权|注入|越狱)", focus_text, re.I):
                editorial_note = (
                    "如果把这篇东西当成产品问题来看，它在提醒你的不是“又多了几个风险名词”，而是这类系统一旦碰真实业务，治理就是产品的一部分。"
                    "换句话说，它解决不了安全和责任边界之前，功能再强也很难真的落地。"
                    "所以它的实用价值，是帮团队提前想清楚哪些权限、流程和兜底机制必须先配上；不然项目很容易卡在试用可以、上线不行。"
                )
            elif re.search(r"(github|开源|repo|仓库|star|stars)", focus_text, re.I):
                editorial_note = (
                    "如果把这个 GitHub 项目当成一个产品来看，最该先问的不是它酷不酷，而是它到底替用户省掉了哪一步麻烦。"
                    "它真正值钱的地方，通常也不是功能清单有多长，而是把原来很重、很慢、很专业的一段流程，压缩成普通人也能先跑起来的一套用法。"
                    "所以大周更关心的是：这个项目到底解决了什么具体问题，能让谁少花时间、少踩坑、少依赖专家；如果这些答案说得清，它才不是“又一个开源仓库”，而是真有可能接进真实工作流的东西。"
                )
                discussion_prompts = [
                    "这个项目最核心是在替用户省哪一步麻烦？",
                    "它带来的价值更像提效工具，还是会直接改掉一段工作流？",
                    "如果真要落进团队或客户场景，最大的使用门槛会卡在哪？",
                ]
            elif re.search(r"(筹资|传播|品牌|捐赠人|fundraising|donor)", focus_text, re.I):
                editorial_note = (
                    "如果把这篇内容当成一个增长问题来看，它在讲的其实不是“文案怎么写得更好看”，而是组织怎么更稳定地拿到注意力和信任。"
                    "它的价值在于把那些真正影响转化和关系维护的环节说具体了，比如内容怎么组织、渠道怎么选、关系怎么接住。"
                    "所以大周不会只把它当技巧贴，而会看它到底是在修一个短期转化问题，还是在帮组织建立更长期的筹资和品牌能力。"
                )
            elif re.search(r"(ai|大模型|模型|codex|copilot|自动化|数字化|工具)", focus_text, re.I):
                editorial_note = (
                    "如果把这篇东西当成产品在看，它真正解决的通常不是“AI 能不能再炫一点”，而是某个原本又慢又重的工作环节能不能被直接做薄。"
                    "它最值得看的价值，也不是多了一个新功能，而是把谁的时间省下来了、把哪段流程缩短了、让哪些原本做不到的人也能先把事做起来。"
                    "所以大周会更关心它是不是已经从演示玩具变成了能接进真实业务的工具：如果答案是可以，那它改的就不只是效率，而是团队以后怎么交付、客户以后会期待什么。"
                )
                discussion_prompts = [
                    "这个工具最直接替人省掉的是哪一步，而不是哪句概念？",
                    "它创造的价值更像提效插件，还是会直接改掉一段业务流程？",
                    "如果真要落地，最可能卡在数据、流程、权限还是使用门槛？",
                ]
            else:
                editorial_note = (
                    "如果把这篇内容当成一个产品线索来看，最值得先讲清楚的不是新闻本身，而是它到底把哪个老问题说透了。"
                    "它有没有把一个原本模糊的痛点讲具体，有没有告诉你谁会直接受益、谁会被迫调整、或者哪一步流程会因此被改写。"
                    "对大周来说，这才是它的实用价值：不是把新闻再复述一遍，而是把“这东西到底有啥用、为什么值得花时间看”讲成人能马上听懂的话。"
                )
        if needs_grounded_editorial_note:
            editorial_note = self._build_grounded_topic_editorial_note(
                candidate_title=candidate_title,
                candidate_summary=candidate_summary,
                key_points=normalized["keyPoints"],
                recommendation_reasons=normalized["recommendationReasons"],
                source_sentences=source_sentences,
                fallback=editorial_note,
            )
        normalized["editorialNote"] = editorial_note[:520]

        writing_angles = normalized["practicalUses"][:4]
        if not writing_angles:
            if re.search(r"(资助|基金|grant|申请|申报|征集|招募|报名|捐赠)", focus_text, re.I):
                writing_angles = [
                    "从这篇文章切入，讨论资助方正在通过哪些信号重新定义“值得支持的机构能力”。",
                    "围绕机会线索背后的门槛变化，写一篇“为什么现在的申报竞争越来越像能力审计”的评论。",
                    "把文章中的项目要求、叙事方式和材料标准拆开，整理成机构如何准备外部合作窗口的参考框架。",
                ]
            elif re.search(r"(ai|大模型|模型|codex|copilot|自动化|数字化|工具)", focus_text, re.I):
                writing_angles = [
                    "以这篇案例为切口，分析 AI 工具正在怎样改写咨询、研发或知识工作的专业分工。",
                    "围绕“从提效工具到业务机会”的跃迁，写一篇 AI 落地为何开始重塑服务边界的评论。",
                    "把文中的落地案例拆成组织能力、流程变化和商业价值三层，形成内部分享主题。",
                ]
            elif re.search(r"(筹资|传播|品牌|捐赠人|fundraising|donor)", focus_text, re.I):
                writing_angles = [
                    "围绕文章中的筹资或传播案例，写一篇公众注意力变化如何倒逼组织改写叙事方式的评论。",
                    "把文中方法放进更长的品牌建设周期里，讨论短期转化与长期关系之间的张力。",
                    "从捐赠人或公众视角重写这篇内容，分析他们真正被什么样的组织表达打动。",
                ]
            else:
                writing_angles = [
                    "以这篇文章为起点，写一篇“表面信息之下更值得关注的结构性变化”评论。",
                    "把文章中的案例、判断和门槛拆开，形成一篇更适合团队内部讨论的前哨短文。",
                    "围绕文中最容易被忽略的一条信号，展开成更完整的行业观察或方法反思。",
                ]
        normalized["practicalUses"] = writing_angles[:4]

        discussion_prompts = normalized["discussionPrompts"][:4]
        if not discussion_prompts or generic_editorial_note:
            if re.search(r"(ai|大模型|模型|codex|copilot|自动化|数字化|工具)", focus_text, re.I):
                discussion_prompts = [
                    "这篇文章提到的能力变化，哪些会真正改变团队的服务方式，哪些只是表层提效？",
                    "如果这些案例持续增多，团队的专业壁垒未来应该建立在什么地方？",
                    "文章里的落地路径是否依赖特定组织条件，还是已经具备可迁移性？",
                ]
            elif re.search(r"(资助|基金|grant|申请|申报|征集|招募|报名|捐赠)", focus_text, re.I):
                discussion_prompts = [
                    "这篇内容反映的资助偏好变化，和我们当前项目准备方式之间有哪些错位？",
                    "如果要把这类窗口真正抓住，机构最缺的是材料、证据、叙事能力还是执行能力？",
                    "文章里的要求是一次性门槛，还是说明外部评估标准正在长期变化？",
                ]
            else:
                discussion_prompts = [
                    "这篇文章表面的信息背后，真正值得继续追问的结构性变化是什么？",
                    "如果把这条线索放进更长的时间线上看，它说明判断标准正在怎样变化？",
                    "文章里的观点对团队当前工作最有启发的一层，不是事实本身，而是什么？",
                ]
        if generic_editorial_note or not discussion_prompts:
            discussion_prompts = self._build_grounded_topic_discussion_prompts(
                candidate_title=candidate_title,
                key_points=normalized["keyPoints"],
                recommendation_reasons=normalized["recommendationReasons"],
                source_sentences=source_sentences,
            )
        normalized["discussionPrompts"] = discussion_prompts[:4]
        return normalized

    def _localize_topic_insight_payload(
        self,
        payload: dict[str, object],
        *,
        candidate_title: str,
        candidate_summary: str,
        source: str,
        published_at: str | None,
        source_url: str | None,
        source_content: str,
    ) -> dict[str, object]:
        normalized = self._normalize_topic_candidate_insight_payload(payload)
        if self._topic_insight_is_chinese(normalized):
            return self._enrich_topic_insight_payload(
                normalized,
                candidate_title=candidate_title,
                candidate_summary=candidate_summary,
                source=source,
                source_content=source_content,
            )

        health = self.get_health()
        if not health.ready or health.provider == "mock":
            return self._fallback_localized_topic_insight(
                normalized,
                candidate_title=candidate_title,
                candidate_summary=candidate_summary,
                source=source,
                source_content=source_content,
            )

        schema = {
            "type": "OBJECT",
            "properties": {
                "overview": {"type": "STRING"},
                "keyPoints": {"type": "ARRAY", "items": {"type": "STRING"}},
                "recommendationReasons": {"type": "ARRAY", "items": {"type": "STRING"}},
                "practicalUses": {"type": "ARRAY", "items": {"type": "STRING"}},
                "editorialNote": {"type": "STRING"},
                "discussionPrompts": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
        }
        prompt = (
            "请把下面这份资讯解析改写成自然、准确、完整的中文版本。"
            "要求：\n"
            "1. overview、keyPoints、recommendationReasons、practicalUses、editorialNote、discussionPrompts 必须全部是中文。\n"
            "1a. overview 必须展开写，至少 140 字，清楚交代文章主旨、主要观点和对团队的价值，不要只写一句结论。\n"
            "1b. editorialNote 必须改成口语化、像产品经理跟同事解释价值的说法。至少 180 字，优先讲清楚它解决什么问题、给谁省了什么、为什么现在值得看，以及落地会卡在哪。不要写成新闻评论、官样文章或宏大社论。\n"
            "1c. 如果内容是 GitHub 开源项目、技术工具或新产品，直接用“它到底替用户省了哪一步麻烦、为什么这一步值钱”来改写，不要先讲行业趋势或大词判断。\n"
            "2. 可以结合候选标题、摘要和原文摘录，把过于泛的地方改得更具体，但不能编造事实。\n"
            "3. keyPoints 重点提炼文章真正有价值的信息点；recommendationReasons 要写得更像“这个东西到底有啥用”；practicalUses 改写成可直接成文的角度；discussionPrompts 改写成值得继续追问的问题。\n"
            "4. 返回 JSON，不要输出解释。\n"
            f"候选标题：{candidate_title}\n"
            f"候选摘要：{candidate_summary}\n"
            f"来源：{source}\n"
            f"发布时间：{published_at or '未知'}\n"
            f"原文链接：{source_url or '无'}\n"
            f"原文摘录：{(source_content or '暂无原文摘录。')[:3600]}\n"
            f"当前解析 overview：{normalized['overview']}\n"
            f"当前解析 keyPoints：{'；'.join(normalized['keyPoints']) or '无'}\n"
            f"当前解析 recommendationReasons：{'；'.join(normalized['recommendationReasons']) or '无'}\n"
            f"当前解析 practicalUses：{'；'.join(normalized['practicalUses']) or '无'}\n"
            f"当前解析 editorialNote：{normalized['editorialNote'] or '无'}\n"
            f"当前解析 discussionPrompts：{'；'.join(normalized['discussionPrompts']) or '无'}"
        )
        try:
            result = self._qwen_generate(
                prompt,
                "你是资讯翻译与提炼助手。只返回 JSON。",
                schema,
                timeout_seconds=24.0,
                max_tokens=1600,
            )
            if isinstance(result, dict):
                localized = self._normalize_topic_candidate_insight_payload(result)
                if self._topic_insight_is_chinese(localized):
                    return self._enrich_topic_insight_payload(
                        localized,
                        candidate_title=candidate_title,
                        candidate_summary=candidate_summary,
                        source=source,
                        source_content=source_content,
                    )
        except Exception:
            pass
        return self._fallback_localized_topic_insight(
            normalized,
            candidate_title=candidate_title,
            candidate_summary=candidate_summary,
            source=source,
            source_content=source_content,
        )

    def _normalize_string_list(self, value: object, *, max_items: int, max_length: int) -> list[str]:
        if not isinstance(value, list):
            return []
        items: list[str] = []
        for item in value:
            text = str(item or "").strip()
            if not text or text in items:
                continue
            items.append(text[:max_length])
            if len(items) >= max_items:
                break
        return items

    def _fallback_topic_candidate_insight(
        self,
        *,
        candidate_title: str,
        candidate_summary: str,
        source: str,
        published_at: str | None,
        source_url: str | None,
        source_content: str,
    ) -> dict[str, object]:
        raw_text = "\n".join(part for part in [candidate_summary, source_content] if part).strip() or candidate_title
        sentences = [
            segment.strip(" -")
            for segment in re.split(r"[\n。！？!?；;]+", raw_text)
            if segment.strip()
        ]
        key_points: list[str] = []
        for sentence in sentences:
            text = sentence.strip()
            if len(text) < 8:
                continue
            if self._looks_like_topic_noise(text, candidate_title):
                continue
            if text not in key_points:
                key_points.append(text[:150])
            if len(key_points) >= 4:
                break
        if not key_points:
            key_points = self._extract_topic_source_sentences(source_content, candidate_title, max_items=4)
        if not key_points:
            summary_candidate = candidate_summary[:150] if candidate_summary and not self._looks_like_topic_noise(candidate_summary, candidate_title) else ""
            key_points = [summary_candidate or candidate_title]

        focus_text = f"{candidate_title} {candidate_summary} {source_content}".lower()
        recommendation_reasons: list[str] = []
        practical_uses: list[str] = []
        if re.search(r"(安全|风控|风险|攻击|漏洞|泄露|合规|防护|权限|越权|注入|越狱)", focus_text, re.I):
            recommendation_reasons = [
                "这条内容直接对应大模型落地中的真实安全与合规问题，适合帮助团队判断哪些风险需要在项目推进前就前置处理。",
                "如果文章把风险场景、防护机制和治理路径讲得足够具体，就能为团队制定内部安全要求、供应商评估标准或试点边界提供参考。",
            ]
            practical_uses = [
                "围绕风险治理前置这件事，写一篇大模型项目为何不能只看功能上线的评论。",
                "把文章中的风险案例拆成“场景、后果、治理动作”，形成一篇安全观察短文。",
                "从供应商评估或项目边界切入，讨论安全要求如何变成业务落地门槛。",
            ]
        elif re.search(r"(资助|基金|grant|申请|申报|征集|招募|报名|捐赠)", focus_text, re.I):
            recommendation_reasons = [
                "这条内容可能对应真实的资金、合作或项目申报窗口，值得尽快判断是否匹配当前机构需求。",
                "文章里通常会带出申请条件、截止时间或所需资料，对团队推进资源争取有直接帮助。",
            ]
            practical_uses = [
                "从这条线索切入，写一篇资助窗口背后正在怎样重写机构能力评估标准的评论。",
                "把文中的门槛、主题和材料要求拆开，形成一篇“为什么申报越来越像能力审计”的文章提纲。",
                "围绕外部机会与内部准备之间的错位，整理成一次团队内部讨论分享。",
            ]
        elif re.search(r"(ai|大模型|模型|copilot|自动化|数字化|工具)", focus_text, re.I):
            recommendation_reasons = [
                "这条内容更像方法或案例信号，可以帮助团队快速理解同类组织在技术上的真实落地方式。",
                "如果文章提到具体做法、流程或产品选择，适合沉淀成内部学习资料或试点清单。",
            ]
            practical_uses = [
                "以这篇案例为切口，分析 AI 工具为什么开始改变专业工作的交付边界。",
                "把文中的落地路径拆成能力变化、流程变化和商业变化，形成一篇前哨观察。",
                "围绕“AI 从提效走向重构工作流”写一篇更适合对外分享的评论框架。",
            ]
        elif re.search(r"(筹资|传播|品牌|捐赠人|fundraising|donor)", focus_text, re.I):
            recommendation_reasons = [
                "这条内容可能反映筹资或传播领域的新打法，适合用于调整当前团队的外部沟通策略。",
                "如果文章包含案例和结果数据，能直接帮助判断哪些动作值得试做或复盘。",
            ]
            practical_uses = [
                "从公众注意力变化切入，写一篇筹资与传播为什么正在失去旧有默认打法的评论。",
                "把文章中的案例放进更长的品牌建设周期里，形成一篇方法反思。",
                "围绕捐赠人关系如何被重新定义，整理成团队内部研讨的切口。",
            ]
        else:
            recommendation_reasons = [
                "这条内容提供了可继续追踪的行业线索，值得先判断它是否与当前项目方向相关。",
                "如果文中包含可验证的信息点或案例，适合先沉淀成内部参考，再决定是否进一步投入。",
            ]
            practical_uses = [
                "把文章里最值得抓住的一条变化展开，写成一篇前哨式短评。",
                "从案例背后的结构性变化切入，整理成一次团队内部讨论发言。",
                "围绕文中最容易被忽略的一条判断，形成后续选题角度。",
            ]

        overview_seed = ""
        if self._has_sufficient_cjk(candidate_summary):
            overview_seed = candidate_summary[:90]
        elif key_points and self._has_sufficient_cjk(key_points[0]):
            overview_seed = key_points[0][:90]

        if overview_seed:
            overview = f"这篇内容主要围绕“{candidate_title[:28]}”展开，重点提到：{overview_seed}"
        else:
            overview = (
                f"这条内容来自 {source}，核心价值在于它不只是提供资讯本身，"
                f"还带出了可供团队学习、判断机会或补充资源的具体线索。"
            )
            if published_at:
                overview += f" 发布时间为 {published_at[:10]}。"
        if source_url and not practical_uses:
            practical_uses.append("把原文里的关键信号和边界条件拆开，形成一篇更完整的评论角度。")

        editorial_note = ""
        discussion_prompts: list[str] = []
        if re.search(r"(安全|风控|风险|攻击|漏洞|泄露|合规|防护|权限|越权|注入|越狱)", focus_text, re.I):
            editorial_note = (
                "如果把这篇东西当成产品问题来看，它在提醒你的不是“又多了几个风险名词”，而是这类系统一旦碰真实业务，治理就是产品的一部分。"
                "换句话说，它解决不了安全和责任边界之前，功能再强也很难真的落地。"
                "所以它的实用价值，是帮团队提前想清楚哪些权限、流程和兜底机制必须先配上；不然项目很容易卡在试用可以、上线不行。"
            )
            discussion_prompts = [
                "这里提到的风险，哪些已经是我们当前项目必须先回答的？",
                "如果真要落地，最容易卡住的会是权限、流程还是责任归属？",
                "哪些治理要求应该在项目启动前就讲清楚，而不是等出事后再补？",
            ]
        elif re.search(r"(资助|基金|grant|申请|申报|征集|招募|报名|捐赠)", focus_text, re.I):
            editorial_note = (
                "如果把这类信息当成一个产品线索来看，它解决的不是“有没有机会”这么简单，而是告诉你：外部资方现在到底按什么标准筛人。"
                "它真正的价值，是帮团队少走弯路，早点看清楚申请方最看重的是项目逻辑、执行证据，还是机构叙事。"
                "所以大周更在意的不是窗口又多了一个，而是这篇内容有没有把评估口径讲明白；如果讲明白了，它就能直接反过来指导我们准备材料、补能力、改表达。"
            )
            discussion_prompts = [
                "这篇内容真正告诉我们的，是机会本身，还是资方的筛选标准？",
                "如果要去争取这类窗口，我们最缺的是材料、证据，还是项目逻辑？",
                "这里面哪些要求是一次性门槛，哪些是长期的能力要求？",
            ]
        elif re.search(r"(github|开源|repo|仓库|star|stars)", focus_text, re.I):
            editorial_note = (
                "如果把这个 GitHub 项目当成一个产品来看，最该先问的不是它酷不酷，而是它到底替用户省掉了哪一步麻烦。"
                "它真正值钱的地方，通常也不是功能清单有多长，而是把原来很重、很慢、很专业的一段流程，压缩成普通人也能先跑起来的一套用法。"
                "所以大周更关心的是：这个项目到底解决了什么具体问题，能让谁少花时间、少踩坑、少依赖专家；如果这些答案说得清，它才不是“又一个开源仓库”，而是真有可能接进真实工作流的东西。"
            )
            discussion_prompts = [
                "这个项目最核心是在替用户省哪一步麻烦？",
                "它带来的价值更像提效工具，还是会直接改掉一段工作流？",
                "如果真要落进团队或客户场景，最大的使用门槛会卡在哪？",
            ]
        elif re.search(r"(ai|大模型|模型|copilot|自动化|数字化|工具)", focus_text, re.I):
            editorial_note = (
                "如果把这篇东西当成产品在看，它真正解决的通常不是“AI 能不能再炫一点”，而是某个原本又慢又重的工作环节能不能被直接做薄。"
                "它最值得看的价值，也不是多了一个新功能，而是把谁的时间省下来了、把哪段流程缩短了、让哪些原本做不到的人也能先把事做起来。"
                "所以大周会更关心它是不是已经从演示玩具变成了能接进真实业务的工具：如果答案是可以，那它改的就不只是效率，而是团队以后怎么交付、客户以后会期待什么。"
            )
            discussion_prompts = [
                "这个工具最直接替人省掉的是哪一步，而不是哪句概念？",
                "它创造的价值更像提效插件，还是会直接改掉一段业务流程？",
                "如果真要落地，最可能卡在数据、流程、权限还是使用门槛？",
            ]
        elif re.search(r"(筹资|传播|品牌|捐赠人|fundraising|donor)", focus_text, re.I):
            editorial_note = (
                "如果把这篇内容当成一个增长问题来看，它在讲的其实不是“文案怎么写得更好看”，而是组织怎么更稳定地拿到注意力和信任。"
                "它的价值在于把那些真正影响转化和关系维护的环节说具体了，比如内容怎么组织、渠道怎么选、关系怎么接住。"
                "所以大周不会只把它当技巧贴，而会看它到底是在修一个短期转化问题，还是在帮组织建立更长期的筹资和品牌能力。"
            )
            discussion_prompts = [
                "它解决的更像短期转化问题，还是长期关系问题？",
                "如果真照着做，最先要改的是内容、渠道，还是关系维护方式？",
                "这篇内容背后真正变了的，是传播动作，还是公众判断标准？",
            ]
        else:
            editorial_note = (
                "如果把这篇内容当成一个产品线索来看，最值得先讲清楚的不是新闻本身，而是它到底把哪个老问题说透了。"
                "它有没有把一个原本模糊的痛点讲具体，有没有告诉你谁会直接受益、谁会被迫调整、或者哪一步流程会因此被改写。"
                "对大周来说，这才是它的实用价值：不是把新闻再复述一遍，而是把“这东西到底有啥用、为什么值得花时间看”讲成人能马上听懂的话。"
            )
            discussion_prompts = [
                "它真正解决的问题到底是什么，而不是表面在说什么？",
                "如果真把它用起来，最先会改掉的是哪一步旧流程？",
                "这条线索最值得继续核实的，不是新闻本身，而是哪种实际价值？",
            ]

        return {
            "overview": overview[:180],
            "keyPoints": key_points[:4],
            "recommendationReasons": recommendation_reasons[:4],
            "practicalUses": practical_uses[:4],
            "editorialNote": editorial_note[:520],
            "discussionPrompts": discussion_prompts[:4],
        }

    def _fallback_localized_topic_insight(
        self,
        payload: dict[str, object],
        *,
        candidate_title: str,
        candidate_summary: str,
        source: str,
        source_content: str,
    ) -> dict[str, object]:
        normalized = self._normalize_topic_candidate_insight_payload(payload)
        overview = normalized["overview"]
        if not self._has_sufficient_cjk(overview):
            summary_hint = candidate_summary if self._has_sufficient_cjk(candidate_summary) else ""
            overview = (
                summary_hint
                or f"这条内容来自 {source}，主题围绕“{candidate_title[:40]}”，建议结合原文继续核对关键细节与可执行线索。"
            )[:180]

        key_points = [item for item in normalized["keyPoints"] if self._has_sufficient_cjk(item)]
        if not key_points:
            if self._has_sufficient_cjk(candidate_summary):
                key_points = [candidate_summary[:150]]
            else:
                key_points = [f"文章主要围绕“{candidate_title[:40]}”展开，建议结合原文核对更具体的信息点。"]

        recommendation_reasons = [item for item in normalized["recommendationReasons"] if self._has_sufficient_cjk(item)]
        if not recommendation_reasons:
            recommendation_reasons = [
                "这条内容提到了值得继续核实的信息点，适合先判断是否与当前工作方向相关。",
                "如果原文包含具体案例、门槛或资源线索，适合沉淀成内部参考后再决定是否推进。",
            ]

        practical_uses = [item for item in normalized["practicalUses"] if self._has_sufficient_cjk(item)]
        if not practical_uses:
            practical_uses = [
                "把文章里最有价值的一条观点展开成一篇短评，解释它为什么不只是个案。",
                "围绕文中提到的方法或案例，写一篇更适合团队内部分享的前哨观察。",
                "从文章最容易被忽略的一条信号切入，形成一个可继续讨论的写作角度。",
            ]

        editorial_note = str(normalized.get("editorialNote") or "").strip()
        if not self._has_sufficient_cjk(editorial_note):
            editorial_note = (
                "如果把这篇内容当成一个产品线索来看，最有用的地方不是再复述一遍新闻，而是先说清楚它到底解决什么问题。"
                "它有没有帮人省步骤、降门槛、提效率，或者把原来很难做的一件事变得更容易，这些才是大周更在意的。"
                "所以比起写成评论稿，我更想把它讲成人话：这东西值不值得看，关键就看它到底有没有把某个具体麻烦真的做薄。"
            )[:520]

        discussion_prompts = [item for item in normalized["discussionPrompts"] if self._has_sufficient_cjk(item)]
        if not discussion_prompts:
            discussion_prompts = [
                "这篇文章最值得继续追问的变化，不是事实本身，而是什么？",
                "如果把文章里的案例放进更长时间线里看，它预示了怎样的结构性变化？",
                "文中的观点对团队当前判断最有用的一层，究竟是方法、趋势，还是门槛变化？",
            ]

        return self._enrich_topic_insight_payload(
            {
                "overview": overview,
                "keyPoints": key_points[:6],
                "recommendationReasons": recommendation_reasons[:4],
                "practicalUses": practical_uses[:4],
                "editorialNote": editorial_note,
                "discussionPrompts": discussion_prompts[:4],
            },
            candidate_title=candidate_title,
            candidate_summary=candidate_summary,
            source=source,
            source_content=source_content,
        )

    def _fallback_topic_task_plan(
        self,
        *,
        candidate_title: str,
        candidate_summary: str,
        source: str,
        published_at: str | None,
        source_url: str | None,
        source_content: str,
        candidate_insight: dict[str, object] | None = None,
    ) -> dict[str, object]:
        raw_text = "\n".join(
            part for part in [candidate_title, candidate_summary, source_content] if part
        )
        due_date = self._extract_due_date_from_text(raw_text)
        deadline_label = self._label_due_date(due_date) if due_date else ("待确认" if re.search(r"(截止|deadline|due|截至|报名时间)", raw_text, re.I) else "本周内")
        insight_overview = str((candidate_insight or {}).get("overview") or "").strip()
        recommendation_reasons = self._normalize_string_list((candidate_insight or {}).get("recommendationReasons"), max_items=4, max_length=160)
        practical_uses = self._normalize_string_list((candidate_insight or {}).get("practicalUses"), max_items=4, max_length=100)
        overview = insight_overview or f"这条线索来自 {source}，建议先核对机会要求、准备材料，并尽快确认是否进入正式推进。"
        note_prefix = f"来源：{source}"
        if published_at:
            note_prefix += f"；发布时间：{published_at[:10]}"
        if source_url:
            note_prefix += f"；链接：{source_url}"

        if practical_uses:
            tasks: list[dict[str, object]] = []
            for index, action in enumerate(practical_uses[:3]):
                reason = recommendation_reasons[min(index, len(recommendation_reasons) - 1)] if recommendation_reasons else "这条内容值得继续跟进。"
                due = due_date if index == len(practical_uses[:3]) - 1 else None
                tasks.append(
                    {
                        "title": action[:60],
                        "desc": f"围绕“{reason[:36]}”完成这项动作，并把结论回写到任务记录里。",
                        "dueDate": due,
                        "ddl": deadline_label if due else ("今天" if index == 0 else "本周内"),
                        "note": f"{note_prefix}；关联理由：{reason}",
                        "priority": "high" if index == 0 else "normal",
                        "tags": ["资讯跟进", "选题解析"][:2],
                    }
                )
            return {
                "overview": overview,
                "tasks": tasks,
            }

        funding_like = bool(re.search(r"(资助|申报|申请|基金|grant|征集|招募|报名)", raw_text, re.I))
        if funding_like:
            tasks = [
                {
                    "title": "核对资助要求并确认申报策略",
                    "desc": "确认申请条件、资助方向、所需材料和内部是否值得申报。",
                    "dueDate": None,
                    "ddl": "今天",
                    "note": f"{note_prefix}；先判断这条机会与机构当前项目是否匹配。",
                    "priority": "high",
                    "tags": ["机会评估", "资助申报"],
                },
                {
                    "title": "整理机构资料与证明材料",
                    "desc": "准备机构简介、项目案例、预算说明和过往成果等申报材料。",
                    "dueDate": None,
                    "ddl": "本周内",
                    "note": f"{note_prefix}；把历史案例和证明文件统一整理成可提交版本。",
                    "priority": "normal",
                    "tags": ["材料准备"],
                },
                {
                    "title": "撰写并提交申请材料",
                    "desc": "根据要求完成申请表和附件填写，并在截止前完成提交。",
                    "dueDate": due_date,
                    "ddl": deadline_label,
                    "note": f"{note_prefix}；若原文有明确截止时间，请以原文时间为准。",
                    "priority": "high",
                    "tags": ["申请提交"],
                },
            ]
        else:
            tasks = [
                {
                    "title": "确认这条机会的适配性与优先级",
                    "desc": "梳理核心要求、适用对象和推进价值，判断是否值得继续投入。",
                    "dueDate": None,
                    "ddl": "今天",
                    "note": f"{note_prefix}；先完成机会评估，再决定后续动作。",
                    "priority": "normal",
                    "tags": ["机会评估"],
                },
                {
                    "title": "整理对外沟通或执行所需材料",
                    "desc": "准备介绍材料、案例、联系人信息或内部决策依据，形成可执行包。",
                    "dueDate": None,
                    "ddl": "本周内",
                    "note": f"{note_prefix}；把分散资料归并成一份可交接材料。",
                    "priority": "normal",
                    "tags": ["材料整理"],
                },
                {
                    "title": "安排后续跟进并记录下一步",
                    "desc": "明确谁来推进、何时反馈，以及是否需要在截止前提交或报名。",
                    "dueDate": due_date,
                    "ddl": deadline_label,
                    "note": f"{note_prefix}；如果原文没有明确截止时间，请在备注里补齐。",
                    "priority": "normal",
                    "tags": ["后续跟进"],
                },
            ]
        return {
            "overview": overview,
            "tasks": tasks,
        }

    def _normalize_due_date_value(self, value: object) -> str | None:
        text = str(value or "").strip()
        if not text:
            return None
        if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
            return text
        return self._extract_due_date_from_text(text)

    def _extract_due_date_from_text(self, text: str) -> str | None:
        today = datetime.now().date()
        direct = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
        if direct:
            return direct.group(1)
        zh_match = re.search(r"(?:(20\d{2})年)?(\d{1,2})月(\d{1,2})日", text)
        if zh_match:
            year = int(zh_match.group(1) or today.year)
            month = int(zh_match.group(2))
            day = int(zh_match.group(3))
            try:
                return datetime(year, month, day).date().isoformat()
            except ValueError:
                return None
        en_match = re.search(
            r"\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\s+(\d{1,2})(?:,\s*(20\d{2}))?",
            text,
            re.I,
        )
        if en_match:
            month_map = {
                "jan": 1,
                "january": 1,
                "feb": 2,
                "february": 2,
                "mar": 3,
                "march": 3,
                "apr": 4,
                "april": 4,
                "may": 5,
                "jun": 6,
                "june": 6,
                "jul": 7,
                "july": 7,
                "aug": 8,
                "august": 8,
                "sep": 9,
                "sept": 9,
                "september": 9,
                "oct": 10,
                "october": 10,
                "nov": 11,
                "november": 11,
                "dec": 12,
                "december": 12,
            }
            month = month_map[en_match.group(1).lower()]
            day = int(en_match.group(2))
            year = int(en_match.group(3) or today.year)
            try:
                return datetime(year, month, day).date().isoformat()
            except ValueError:
                return None
        return None

    def _label_due_date(self, due_date: str | None) -> str:
        if not due_date:
            return "待确认"
        try:
            date = datetime.fromisoformat(due_date).date()
        except ValueError:
            return due_date
        return f"{date.month}月{date.day}日前"

    def _normalize_priority(self, value: object) -> str:
        text = str(value or "normal").strip().lower()
        return text if text in {"low", "normal", "high"} else "normal"

    def _has_sufficient_cjk(self, text: str) -> bool:
        matches = re.findall(r"[\u4e00-\u9fff]", text or "")
        return len(matches) >= 4

    def _topic_insight_is_chinese(self, payload: dict[str, object]) -> bool:
        overview = str(payload.get("overview") or "").strip()
        if not self._has_sufficient_cjk(overview):
            return False
        editorial_note = str(payload.get("editorialNote") or "").strip()
        if not self._has_sufficient_cjk(editorial_note):
            return False
        for key in ("keyPoints", "recommendationReasons", "practicalUses", "discussionPrompts"):
            values = payload.get(key)
            if not isinstance(values, list) or not values:
                return False
            if any(not self._has_sufficient_cjk(str(item)) for item in values):
                return False
        return True

    def _looks_like_topic_noise(self, text: str, candidate_title: str) -> bool:
        compact = re.sub(r"\s+", "", text)
        title_compact = re.sub(r"\s+", "", candidate_title or "")
        noise_patterns = (
            "点赞",
            "收藏",
            "评论",
            "关注",
            "打开知乎",
            "下载app",
            "下载App",
            "APP",
            "上一页",
            "下一页",
        )
        if self._is_title_like_topic_text(text, candidate_title):
            return True
        if any(pattern.lower() in compact.lower() for pattern in noise_patterns):
            return True
        if re.search(r"(?:https?://|www\.|\.com\b|\.net\b|\.cn\b)", text.lower()) and len(compact) < 140:
            return True
        if title_compact and compact.count(title_compact[:12]) >= 2:
            return True
        return False

    def _is_title_like_topic_text(self, text: str, candidate_title: str) -> bool:
        compact = re.sub(r"\s+", "", text or "")
        title_compact = re.sub(r"\s+", "", candidate_title or "")
        if not compact or not title_compact:
            return False
        if compact == title_compact:
            return True
        if title_compact in compact and abs(len(compact) - len(title_compact)) <= 18:
            return True
        return False

    def _extract_topic_source_sentences(self, source_content: str, candidate_title: str, *, max_items: int) -> list[str]:
        sentences = [
            segment.strip(" -")
            for segment in re.split(r"[\n。！？!?；;]+", source_content or "")
            if segment.strip()
        ]
        items: list[str] = []
        for sentence in sentences:
            text = sentence.strip()
            if len(text) < 10:
                continue
            if self._looks_like_topic_noise(text, candidate_title):
                continue
            if text in items:
                continue
            items.append(text[:180])
            if len(items) >= max_items:
                break
        return items

    def _looks_like_weak_topic_material(self, candidate_title: str, candidate_summary: str, source_content: str) -> bool:
        summary = (candidate_summary or "").strip()
        title = (candidate_title or "").strip()
        if "原始来源提到" in summary:
            return True
        if "相关机会" in title and not source_content:
            return True
        if not source_content and not self._has_sufficient_cjk(summary) and re.search(r"[A-Za-z]{8,}", title):
            return True
        return False

    def _extract_topic_source_hint(self, candidate_title: str, candidate_summary: str) -> str:
        match = re.search(r"原始来源提到“([^”]+)”", candidate_summary or "")
        if match:
            return match.group(1).strip()[:80]
        return (candidate_title or "未知来源").strip()[:80]

    def _looks_generic_topic_overview(self, overview: str) -> bool:
        text = (overview or "").strip()
        generic_phrases = (
            "核心价值在于它不只是提供资讯本身",
            "带出了可供团队学习",
            "建议结合原文继续核对关键细节",
            "值得继续跟进",
        )
        if len(text) < 90:
            return True
        return any(phrase in text for phrase in generic_phrases)

    def _looks_generic_topic_editorial_note(self, editorial_note: str) -> bool:
        text = (editorial_note or "").strip()
        if not text:
            return True
        generic_phrases = (
            "如果把这个 GitHub 项目当成一个产品来看",
            "如果把这篇东西当成产品在看",
            "如果把这篇内容当成一个产品线索来看",
            "如果把这类信息当成一个产品线索来看",
            "如果把这篇内容当成一个增长问题来看",
            "如果把这篇东西当成产品问题来看",
            "它真正值钱的地方，通常也不是功能清单有多长",
            "它最值得看的价值，也不是多了一个新功能",
            "对大周来说，这才是它的实用价值",
        )
        return any(phrase in text for phrase in generic_phrases)

    def _looks_stale_topic_editorial_note(self, editorial_note: str) -> bool:
        text = (editorial_note or "").strip()
        stale_phrases = (
            "这篇内容背后更重要的信号",
            "真正值得深想的",
            "更深层的意义",
            "结构性变化",
            "默认做法正在被重写",
            "专业能力民主化",
            "大周自己的写作因此不会停留在复述新闻",
            "背后不仅是工具的流行",
            "更折射出",
            "深层趋势",
            "意味着双重挑战",
            "我们不应只关注工具本身",
            "组织的竞争壁垒",
            "组织需要重新审视",
        )
        if len(text) < 120:
            return True
        return self._looks_generic_topic_editorial_note(text) or any(phrase in text for phrase in stale_phrases)

    def _build_grounded_topic_editorial_note(
        self,
        *,
        candidate_title: str,
        candidate_summary: str,
        key_points: list[str],
        recommendation_reasons: list[str],
        source_sentences: list[str],
        fallback: str = "",
    ) -> str:
        material_facts: list[str] = []
        for item in list(key_points or []) + list(source_sentences or []):
            text = self._compact_topic_sentence(str(item or ""), 96)
            if not text or text in material_facts:
                continue
            material_facts.append(text)
            if len(material_facts) >= 3:
                break

        value_points: list[str] = []
        for item in recommendation_reasons or []:
            text = self._compact_topic_sentence(str(item or ""), 96)
            if not text or text in value_points:
                continue
            value_points.append(text)
            if len(value_points) >= 2:
                break

        lead_fact = material_facts[0] if material_facts else self._compact_topic_sentence(candidate_summary or candidate_title, 96)
        value_fact = value_points[0] if value_points else (material_facts[1] if len(material_facts) > 1 else "")
        follow_fact = material_facts[1] if len(material_facts) > 1 else ""

        note_parts = [
            f"先别把它当成一条泛新闻，这篇材料真正值得抓住的是：{lead_fact or candidate_title[:48]}。",
        ]
        if value_fact:
            note_parts.append(f"对团队来说，它有用不是因为“又多了一条资讯”，而是因为{value_fact}。")
        elif fallback.strip():
            note_parts.append(self._compact_topic_sentence(fallback.strip(), 120) + "。")
        else:
            note_parts.append("对团队来说，更重要的是先把它到底解决了什么问题、能给谁省事这件事讲具体。")
        if follow_fact:
            note_parts.append(
                f"接下来最该继续核对的是：{follow_fact}。这部分如果原文里讲得足够具体，才能判断它到底只是热度信号，还是已经能接进真实工作流。"
            )
        else:
            note_parts.append("接下来最该继续核对的，是它的适用场景、落地门槛和边界条件有没有被原文讲清楚；这决定了它到底能不能真的拿来用。")
        return "".join(note_parts)[:520]

    def _build_grounded_topic_discussion_prompts(
        self,
        *,
        candidate_title: str,
        key_points: list[str],
        recommendation_reasons: list[str],
        source_sentences: list[str],
    ) -> list[str]:
        prompts: list[str] = []

        fact = self._compact_topic_sentence((key_points or source_sentences or [candidate_title])[0], 32)
        if fact:
            prompts.append(f"文里提到的“{fact}”到底已经在哪些真实场景里成立了？")

        reason = self._compact_topic_sentence((recommendation_reasons or [candidate_title])[0], 32)
        if reason:
            prompts.append(f"如果它最有价值的是“{reason}”，那这件事对我们现在哪类项目最直接？")

        follow = self._compact_topic_sentence((source_sentences[1] if len(source_sentences) > 1 else key_points[1] if len(key_points) > 1 else candidate_title), 32)
        if follow:
            prompts.append(f"原文里还没讲透的“{follow}”，会不会正好就是它能不能落地的关键门槛？")

        if len(prompts) < 3:
            prompts.append("如果把这条线索真的拿来用，最先需要补证据、补案例，还是补具体使用条件？")
        return prompts[:4]

    def _compact_topic_sentence(self, text: str, max_length: int) -> str:
        cleaned = re.sub(r"\s+", " ", text or "").strip()
        cleaned = cleaned.rstrip("。；;，,、")
        return cleaned[:max_length]

    def generate_knowledge_surrogate(
        self,
        *,
        title: str,
        kind: str,
        primary_category: str,
        secondary_category: str,
        raw_text: str,
        source_path: str,
        fallback: dict[str, object],
    ) -> dict[str, object]:
        health = self.get_health()
        prompt = (
            "请为知识底座生成一个给 AI 检索使用的代理文档摘要。"
            "不要写空泛总结，必须突出未来搜索时最可能使用的线索。"
            "请返回 JSON，对象字段固定为：overview_summary, retrieval_summary, document_role, core_questions, query_hints, distinct_findings, entities, time_markers。\n"
            f"标题：{title}\n类型：{kind}\n一级分类：{primary_category}\n二级分类：{secondary_category}\n原路径：{source_path}\n正文：{raw_text[:5000]}"
        )
        schema = {
            "type": "OBJECT",
            "properties": {
                "overview_summary": {"type": "STRING"},
                "retrieval_summary": {"type": "STRING"},
                "document_role": {"type": "STRING"},
                "core_questions": {"type": "ARRAY", "items": {"type": "STRING"}},
                "query_hints": {"type": "ARRAY", "items": {"type": "STRING"}},
                "distinct_findings": {"type": "ARRAY", "items": {"type": "STRING"}},
                "entities": {"type": "ARRAY", "items": {"type": "STRING"}},
                "time_markers": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
        }
        try:
            if health.provider == "qwen" and health.ready:
                result = self._qwen_generate(prompt, "你是知识底座加工助手。只返回 JSON。", schema, timeout_seconds=25.0)
                if isinstance(result, dict):
                    return result
        except Exception:
            pass
        return fallback

    def generate_memory_surrogate(
        self,
        *,
        title: str,
        content: str,
        analysis: str,
        actions: str,
        fallback: dict[str, object],
    ) -> dict[str, object]:
        health = self.get_health()
        prompt = (
            "请把下面这条 AI 回答沉淀为可复用的战略陪伴记忆。"
            "输出必须适合未来检索和复用，不要写空话。"
            "请返回 JSON，对象字段固定为：overview_summary, retrieval_summary, document_role, core_questions, query_hints, distinct_findings, entities, time_markers。\n"
            f"标题：{title}\n回答内容：{content}\n分析：{analysis}\n建议动作：{actions}"
        )
        schema = {
            "type": "OBJECT",
            "properties": {
                "overview_summary": {"type": "STRING"},
                "retrieval_summary": {"type": "STRING"},
                "document_role": {"type": "STRING"},
                "core_questions": {"type": "ARRAY", "items": {"type": "STRING"}},
                "query_hints": {"type": "ARRAY", "items": {"type": "STRING"}},
                "distinct_findings": {"type": "ARRAY", "items": {"type": "STRING"}},
                "entities": {"type": "ARRAY", "items": {"type": "STRING"}},
                "time_markers": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
        }
        try:
            if health.provider == "qwen" and health.ready:
                result = self._qwen_generate(prompt, "你是战略陪伴记忆整理助手。只返回 JSON。", schema, timeout_seconds=25.0)
                if isinstance(result, dict):
                    return result
        except Exception:
            pass
        return fallback

    def generate_event_line_clarification_draft(
        self,
        *,
        event_line_name: str,
        conversation_text: str,
        current_summary: str = "",
        current_stage: str = "",
        current_intent: str = "",
        current_blocker: str = "",
        current_next_step: str = "",
        current_recent_decision: str = "",
        recent_activity_lines: list[str] | None = None,
    ) -> dict[str, object]:
        cleaned_conversation = str(conversation_text or "").strip()
        fallback = self._fallback_event_line_clarification_draft(
            event_line_name=event_line_name,
            conversation_text=cleaned_conversation,
            current_summary=current_summary,
            current_stage=current_stage,
            current_intent=current_intent,
            current_blocker=current_blocker,
            current_next_step=current_next_step,
            current_recent_decision=current_recent_decision,
        )
        health = self.get_health()
        if not cleaned_conversation or not health.ready or health.provider == "mock":
            return fallback

        activity_summary = "；".join(str(item).strip() for item in (recent_activity_lines or []) if str(item).strip())[:1200]
        prompt = (
            "请把下面这段和客户相关的聊天记录、会议纪要或沟通摘录，整理成事件线当前态草稿。"
            "目标不是逐句复述，而是提炼出这条线现在在推进什么、卡在哪、下一步是什么、最近哪次决定改变了走向。"
            "请返回 JSON，对象字段固定为：summary, stage, intent, currentBlocker, nextStep, recentDecision, missingInfo, confidence。\n"
            "输出约束：\n"
            "1. summary 用 60-120 字中文概括这条线当前在发生什么。\n"
            "2. stage 只写一句当前阶段，如“等待确认”“资料补齐中”“执行推进中”“复盘沉淀中”。\n"
            "3. intent 用 1-3 句说明这条线当前到底在推进什么。\n"
            "4. currentBlocker 只写最关键阻塞；如果没有明确阻塞，可写空字符串。\n"
            "5. nextStep 只写最关键的一步动作；如果聊天里没有明确下一步，可写空字符串。\n"
            "6. recentDecision 只写最近真正改变走向的决定；如果没有明确决定，可写空字符串。\n"
            "7. missingInfo 返回还缺哪些信息，使用中文短句数组。\n"
            "8. confidence 只能是 low、medium、high。\n"
            "9. 不要编造没有出现的事实；不确定就放进 missingInfo。\n\n"
            f"事件线名称：{event_line_name}\n"
            f"当前已有摘要：{current_summary or '无'}\n"
            f"当前已有阶段：{current_stage or '无'}\n"
            f"当前已有事项：{current_intent or '无'}\n"
            f"当前已有阻塞：{current_blocker or '无'}\n"
            f"当前已有下一步：{current_next_step or '无'}\n"
            f"当前已有关键决策：{current_recent_decision or '无'}\n"
            f"最近活动摘要：{activity_summary or '无'}\n"
            f"聊天记录：\n{cleaned_conversation[:5000]}"
        )
        schema = {
            "type": "OBJECT",
            "properties": {
                "summary": {"type": "STRING"},
                "stage": {"type": "STRING"},
                "intent": {"type": "STRING"},
                "currentBlocker": {"type": "STRING"},
                "nextStep": {"type": "STRING"},
                "recentDecision": {"type": "STRING"},
                "missingInfo": {"type": "ARRAY", "items": {"type": "STRING"}},
                "confidence": {"type": "STRING", "enum": ["low", "medium", "high"]},
            },
        }
        try:
            result = self._qwen_generate(
                prompt,
                "你是事件线当前态提炼助手。只返回 JSON。",
                schema,
                timeout_seconds=28.0,
                max_tokens=1600,
            )
            if isinstance(result, dict):
                normalized = self._normalize_event_line_clarification_draft_payload(result, fallback)
                if any(
                    normalized.get(key)
                    for key in ("summary", "stage", "intent", "currentBlocker", "nextStep", "recentDecision")
                ):
                    return normalized
        except Exception:
            pass
        return fallback

    def _normalize_event_line_clarification_draft_payload(
        self,
        payload: dict[str, object],
        fallback: dict[str, object],
    ) -> dict[str, object]:
        confidence_raw = str(payload.get("confidence") or "").strip().lower()
        confidence = confidence_raw if confidence_raw in {"low", "medium", "high"} else str(fallback.get("confidence") or "medium")
        return {
            "summary": str(payload.get("summary") or fallback.get("summary") or "").strip()[:180],
            "stage": str(payload.get("stage") or fallback.get("stage") or "").strip()[:40],
            "intent": str(payload.get("intent") or fallback.get("intent") or "").strip()[:240],
            "currentBlocker": str(payload.get("currentBlocker") or fallback.get("currentBlocker") or "").strip()[:240],
            "nextStep": str(payload.get("nextStep") or fallback.get("nextStep") or "").strip()[:240],
            "recentDecision": str(payload.get("recentDecision") or fallback.get("recentDecision") or "").strip()[:240],
            "missingInfo": self._normalize_string_list(payload.get("missingInfo"), max_items=5, max_length=80)
            or list(fallback.get("missingInfo") or []),
            "confidence": confidence,
        }

    def _fallback_event_line_clarification_draft(
        self,
        *,
        event_line_name: str,
        conversation_text: str,
        current_summary: str,
        current_stage: str,
        current_intent: str,
        current_blocker: str,
        current_next_step: str,
        current_recent_decision: str,
    ) -> dict[str, object]:
        lines = [
            re.sub(r"\s+", " ", segment).strip(" -•\t")
            for segment in re.split(r"[\n\r]+", conversation_text)
            if segment.strip()
        ]
        sentences: list[str] = []
        for line in lines:
            for segment in re.split(r"[。！？!?；;]+", line):
                text = re.sub(r"\s+", " ", segment).strip(" -•\t")
                if text:
                    sentences.append(text)

        def pick_sentence(keywords: list[str]) -> str:
            for sentence in sentences:
                if any(keyword in sentence for keyword in keywords):
                    return sentence[:220]
            return ""

        def pick_sentence_prefix(prefixes: list[str]) -> str:
            for sentence in sentences:
                normalized = sentence.lstrip("：:，,。 ")
                if any(normalized.startswith(prefix) for prefix in prefixes):
                    return sentence[:220]
            return ""

        stage = current_stage.strip()
        if not stage:
            if re.search(r"(等待|确认|审批|口径|回复|定稿)", conversation_text):
                stage = "等待确认"
            elif re.search(r"(补齐|整理|收集|导入|扫描|资料)", conversation_text):
                stage = "资料补齐中"
            elif re.search(r"(执行|推进|落地|跟进|排期)", conversation_text):
                stage = "执行推进中"
            elif re.search(r"(复盘|总结|沉淀)", conversation_text):
                stage = "复盘沉淀中"

        intent = pick_sentence(["推进", "沟通", "确认", "整理", "补齐", "梳理", "对齐", "发送"])
        if not intent:
            intent = current_intent.strip() or "；".join(lines[:2])[:220]

        blocker = pick_sentence(["卡", "阻塞", "等待", "没", "未", "缺", "无法", "来不及", "拖", "确认"])
        if not blocker:
            blocker = current_blocker.strip()

        next_step = (
            pick_sentence_prefix(["下一步", "接下来", "后续"])
            or pick_sentence(["安排", "同步", "跟进", "推进"])
            or pick_sentence(["需要", "先", "再"])
        )
        if not next_step:
            next_step = current_next_step.strip()

        recent_decision = (
            pick_sentence(["决定", "确定", "改成", "暂定", "拍板"])
            or pick_sentence(["统一"])
            or pick_sentence(["先"])
        )
        if not recent_decision:
            recent_decision = current_recent_decision.strip()

        summary_parts = [part for part in [intent, blocker and f"当前卡在：{blocker}", next_step and f"下一步：{next_step}"] if part]
        summary = current_summary.strip() or "；".join(summary_parts)[:160]
        if not summary:
            summary = f"{event_line_name} 当前聊天记录已导入，但还需要继续补足当前态信息。"

        missing_info: list[str] = []
        if not stage:
            missing_info.append("当前阶段还不清楚")
        if not blocker:
            missing_info.append("当前阻塞还不清楚")
        if not next_step:
            missing_info.append("下一步动作还不清楚")
        if not recent_decision:
            missing_info.append("最近关键决策还不清楚")

        filled_slots = sum(1 for item in [summary, stage, intent, blocker, next_step, recent_decision] if item)
        confidence = "high" if filled_slots >= 5 else "medium" if filled_slots >= 3 else "low"
        return {
            "summary": summary[:180],
            "stage": stage[:40],
            "intent": intent[:240],
            "currentBlocker": blocker[:240],
            "nextStep": next_step[:240],
            "recentDecision": recent_decision[:240],
            "missingInfo": missing_info[:5],
            "confidence": confidence,
        }

    def _store_for(self, provider: str) -> Any | None:
        return self.secret_stores.get(provider)

    def _mock_generate(self, prompt: str, context_summary: str) -> AiStructuredResponse:
        topic = self._short_topic(prompt)
        signals = context_summary or "当前上下文中尚无完整材料，以下为保守推演。"
        return AiStructuredResponse(
            content=f"已围绕“{topic}”整理出一版可执行的内部判断。",
            judgment=f"{topic}当前最需要的是把零散线索整合成可落地动作，而不是继续堆信息。",
            analysis="\n".join(
                [
                    f"1. 已知上下文：{signals}",
                    f"2. 问题本质：{topic}涉及客户推进、证据沉淀与任务闭环的联动。",
                    "3. 风险提醒：如果没有明确负责人和时间点，后续行动会再次散掉。",
                ]
            ),
            actions="先确认负责人，再补关键材料，最后将结论写回任务与手册。",
            timeline="建议今天完成判断，48 小时内完成任务拆解，一周内复盘一次。",
        )

    def _short_topic(self, prompt: str) -> str:
        compact = re.sub(r"\s+", "", prompt)
        return compact[:16] or "当前议题"

    def _qwen_generate_structured(
        self,
        prompt: str,
        system_instruction: str,
        context_summary: str,
        *,
        timeout_seconds: float = 60.0,
        max_tokens: int = 2200,
    ) -> AiStructuredResponse:
        payload = self._qwen_generate(
            prompt=f"问题：{prompt}\n\n上下文：{context_summary}",
            system_instruction=system_instruction,
            response_schema=self._structured_schema(),
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
        )
        if not isinstance(payload, dict):
            raise RuntimeError("Qwen 返回了非结构化数据。")
        return self._structured_from_payload(payload)

    def _structured_schema(self) -> dict[str, object]:
        return {
            "type": "OBJECT",
            "properties": {
                "content": {"type": "STRING"},
                "judgment": {"type": "STRING"},
                "analysis": {"type": "STRING"},
                "actions": {"type": "STRING"},
                "timeline": {"type": "STRING"},
            },
        }

    def _structured_from_payload(self, payload: dict[str, object]) -> AiStructuredResponse:
        return AiStructuredResponse(
            content=str(payload.get("content", "")),
            judgment=str(payload.get("judgment", "")),
            analysis=str(payload.get("analysis", "")),
            actions=str(payload.get("actions", "")),
            timeline=str(payload.get("timeline", "")),
        )

    def _build_http_timeout(self, read_timeout_seconds: float) -> httpx.Timeout:
        read_timeout = max(4.0, float(read_timeout_seconds))
        connect_timeout = min(10.0, max(5.0, read_timeout / 3))
        write_timeout = min(20.0, max(8.0, read_timeout))
        pool_timeout = min(10.0, max(5.0, read_timeout / 2))
        return httpx.Timeout(timeout=None, connect=connect_timeout, read=read_timeout, write=write_timeout, pool=pool_timeout)

    def _qwen_generate(
        self,
        prompt: str,
        system_instruction: str,
        response_schema: dict | None,
        timeout_seconds: float = 60.0,
        max_tokens: int = 2200,
        *,
        temperature: float = 0.25,
        top_p: float = 0.9,
        enable_thinking: bool = False,
    ) -> object:
        store = self._store_for("qwen")
        api_key = store.get_api_key() if store else ""
        if not api_key:
            raise RuntimeError("Qwen API Key 未配置。")
        model = self.current_model()
        user_prompt = prompt
        if response_schema:
            user_prompt = (
                "请严格返回一个 JSON 对象，不要使用 Markdown，不要添加解释。"
                "请确保返回结构满足下面这个 JSON Schema。\n"
                f"{json.dumps(response_schema, ensure_ascii=False)}\n\n"
                f"{prompt}"
            )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_instruction or "你是系统助手。"},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": False,
            "enable_thinking": enable_thinking,
        }
        with httpx.Client(timeout=self._build_http_timeout(timeout_seconds)) as client:
            response = client.post(
                f"{QWEN_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
        text = (
            result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        if response_schema:
            return self._load_relaxed_json(text)
        return text

    def _qwen_generate_structured_with_retry(
        self,
        prompt: str,
        system_instruction: str,
        context_summary: str,
    ) -> AiStructuredResponse:
        first_error: Exception | None = None
        second_error: Exception | None = None
        try:
            return self._qwen_generate_structured(
                prompt,
                system_instruction,
                context_summary,
                timeout_seconds=18.0,
                max_tokens=1400,
            )
        except Exception as error:
            first_error = error
        compact_context = self._compact_context_summary(context_summary)
        if compact_context:
            try:
                return self._qwen_generate_structured(
                    prompt,
                    system_instruction,
                    compact_context,
                    timeout_seconds=10.0,
                    max_tokens=900,
                )
            except Exception as error:
                second_error = error
        try:
            return self._qwen_generate_textual_fallback(prompt, system_instruction, compact_context or context_summary)
        except Exception as third_error:
            detail_parts = [self._format_provider_error(first_error)]
            if second_error is not None:
                detail_parts.append(f"缩上下文重试后仍失败：{self._format_provider_error(second_error)}")
            detail_parts.append(f"文本结构化降级仍失败：{self._format_provider_error(third_error)}")
            raise AiInvocationError("qwen", "；".join(part for part in detail_parts if part)) from third_error
        raise AiInvocationError("qwen", self._format_provider_error(first_error)) from first_error

    def _qwen_generate_general_fallback(self, prompt: str, note: str, *, subject_name: str = "") -> AiStructuredResponse:
        text = self._qwen_generate(
            prompt=(
                f"问题：{prompt}\n\n"
                f"补充说明：{note or '当前本地背景回答阶段失败，请直接给出通用知识下的初步回答。'}\n\n"
                f"当前讨论对象：{subject_name or '当前客户'}\n\n"
                "请直接输出一篇完整、自然、专业的中文回答。"
            ),
            system_instruction=(
                "你是益语智库的资深战略顾问。请基于通用知识给出完整、专业的初步回答。"
                "你面对的是一个希望迅速、全面了解这家公司的人，而不是系统管理员。"
                "除非问题明确问益语智库、你们、顾问方或服务方式，否则默认回答对象是当前客户。"
                "不要把益语智库、顾问机构、外部服务方的人名或业务介绍当成当前客户本身。"
                "如果确实需要，只能用一句极轻的过渡说明本地背景没有直接覆盖这个问题，但不要反复展开这一点。"
                "请减少寒暄和重复句，直接进入结论与分析。"
                "不要使用 JSON 或 Markdown 代码块。"
                "第一段必须明确提醒：以下不是基于当前客户原始资料的正式分析，而是通用背景下的初步判断。"
                "回答可以使用自然标题、短段落和少量列表，但不要机械固定成 4 到 6 个栏目。"
                "不要写成表格，也不要使用僵硬固定栏目名。"
                "回答要像资深战略顾问的自然口头汇报转成文稿，而不是知识库说明。"
            ),
            response_schema=None,
            timeout_seconds=20.0,
            max_tokens=1500,
            temperature=0.35,
            top_p=0.92,
        )
        return self._structured_from_plain_answer(str(text))

    def _qwen_generate_compact_grounded_fallback(self, prompt: str, note: str) -> AiStructuredResponse:
        text = self._qwen_generate(
            prompt=(
                f"问题：{prompt}\n\n"
                f"内部观察摘要：\n{note or '当前已有部分内部观察，请基于这些观察先形成紧凑但完整的一版说明。'}\n\n"
                "请直接输出回答。由你自己决定结构、长度和结尾方式。"
            ),
            system_instruction=(
                "请只基于给定观察摘要回答。"
                "不要编造观察摘要里没有出现过的确定性事实。"
                "除此之外，不要预设固定格式、固定结构、固定段数或固定栏目。"
            ),
            response_schema=None,
            timeout_seconds=10.0,
            max_tokens=1200,
            temperature=0.42,
            top_p=0.96,
        )
        return self._structured_from_plain_answer(str(text))

    def _qwen_generate_brief_grounded_rescue(self, prompt: str, note: str) -> AiStructuredResponse:
        text = self._qwen_generate(
            prompt=(
                f"问题：{prompt}\n\n"
                f"顾问观察要点：\n{note or '当前已有部分观察，请基于这些要点给出一版简洁保守的回答。'}\n\n"
                "请直接输出回答。由你自己决定结构、长度和结尾方式。"
            ),
            system_instruction=(
                "请只基于给定观察要点回答。"
                "不要编造观察要点里没有出现过的确定性事实。"
                "除此之外，不要预设固定格式、固定结构、固定段数或固定栏目。"
            ),
            response_schema=None,
            timeout_seconds=8.0,
            max_tokens=900,
            temperature=0.4,
            top_p=0.95,
        )
        return self._structured_from_plain_answer(str(text))

    def _extract_segment_field(self, text: str, labels: tuple[str, ...]) -> str:
        for label in labels:
            match = re.search(
                rf"(?:^|\n){re.escape(label)}[:：]\s*([\s\S]+?)(?=\n(?:{'|'.join(re.escape(item) for item in labels)}|标题|题目|总判断|判断)[:：]|\Z)",
                str(text),
            )
            if match:
                return match.group(1).strip()
        lines = [line.strip() for line in str(text).splitlines() if line.strip()]
        for line in lines:
            for label in labels:
                prefix = f"{label}:"
                alt_prefix = f"{label}："
                if line.startswith(prefix):
                    return line[len(prefix) :].strip()
                if line.startswith(alt_prefix):
                    return line[len(alt_prefix) :].strip()
        return ""

    def _qwen_generate_textual_fallback(
        self,
        prompt: str,
        system_instruction: str,
        context_summary: str,
        *,
        timeout_seconds: float = 110.0,
        max_tokens: int = 5200,
    ) -> AiStructuredResponse:
        fallback_instruction = (
            f"{system_instruction}\n"
            "请继续直接回答用户，不要退化成摘要、说明书或系统提示。"
            "不要使用 JSON 或 Markdown 代码块。"
            "如果完整材料过长，请优先保留最关键的判断、推理链和支撑证据，不要把回答压扁成几段概述。"
            "除非用户明确要求简短，否则请保持足够展开。"
        )
        text = self._qwen_generate(
            prompt=f"用户问题：{prompt}\n\n参考材料：\n{context_summary}",
            system_instruction=fallback_instruction,
            response_schema=None,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
            temperature=0.4,
            top_p=0.95,
            enable_thinking=True,
        )
        return self._structured_from_plain_answer(str(text))

    def _compact_context_summary(self, context_summary: str, max_chars: int = 1800) -> str:
        text = (context_summary or "").strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return text[:max_chars]
        pinned: list[str] = []
        markers = ("客户背景=", "背景底稿（仅用于理解客户）", "原始证据包（可用于正式判断）", "[证据", "顾问角色口径=", "重点维度=")
        for index, line in enumerate(lines):
            if not any(marker in line for marker in markers):
                continue
            block_end = min(len(lines), index + (5 if "[证据" in line else 2))
            for block_line in lines[index:block_end]:
                compact_line = block_line[:960]
                if compact_line not in pinned:
                    pinned.append(compact_line)
        head = [line[:960] for line in lines[:14]]
        tail = [line[:960] for line in lines[-12:]]
        compact_lines = []
        for line in head + pinned[:36]:
            if line not in compact_lines:
                compact_lines.append(line)
        for line in tail:
            if line not in compact_lines:
                compact_lines.append(line)
        compact = "\n".join(compact_lines).strip()
        if not compact:
            compact = text
        compact = compact[:max_chars]
        if compact == text[:max_chars]:
            focus = tail[0] if tail else ""
            fallback_excerpt = "\n".join(compact_lines[:8])[:max_chars]
            compact = "\n".join(part for part in [fallback_excerpt, focus] if part).strip() or text[:max_chars]
        return compact[:max_chars]

    def _structured_from_plain_answer(self, text: str) -> AiStructuredResponse:
        cleaned = str(text).strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(lines[1:-1] if len(lines) > 2 else lines[1:]).strip()
        paragraphs = [item.strip() for item in re.split(r"\n{2,}", cleaned) if item.strip()]
        if not paragraphs:
            paragraphs = [cleaned]
        def is_heading_like(value: str) -> bool:
            candidate = value.strip()
            if not candidate:
                return False
            if re.match(r"^#{1,6}\s+", candidate):
                return True
            if re.match(r"^\d+\.\s+[^\n]{2,42}$", candidate):
                return True
            if re.match(r"^[一二三四五六七八九十]+、", candidate):
                return False
            return len(candidate) <= 42 and not re.search(r"[。！？!?]", candidate)

        judgment_paragraph_index = 1 if len(paragraphs) >= 2 and is_heading_like(paragraphs[0]) else 0
        first_paragraph = paragraphs[judgment_paragraph_index]
        first_sentence_match = re.search(r"(.+?[。！？!?])", first_paragraph)
        judgment = first_sentence_match.group(1).strip() if first_sentence_match else first_paragraph[:180]
        analysis_source = paragraphs[judgment_paragraph_index + 1 :] if len(paragraphs) > judgment_paragraph_index + 1 else paragraphs[judgment_paragraph_index : judgment_paragraph_index + 1]
        analysis_parts = analysis_source[:4] if analysis_source else paragraphs[:1]
        analysis = "\n\n".join(analysis_parts)
        if not analysis.strip():
            analysis = cleaned[:1800]
        actions = "如有需要，可继续围绕当前判断往下追问或展开。"
        suggestion_match = re.search(r"(?:^|\n)\s*(下一步建议|建议动作)[:：]\s*([\s\S]+)$", cleaned, re.IGNORECASE)
        if suggestion_match:
            actions = suggestion_match.group(2).strip() or actions
        return AiStructuredResponse(
            content=cleaned,
            judgment=judgment,
            analysis=analysis,
            actions=actions or "如有需要，可继续围绕当前判断往下追问或展开。",
            timeline="后续可随资料和讨论继续迭代。",
        )

    def _clean_template_field_value(self, text: str, *, field_type: str | None = None) -> str:
        cleaned = str(text or "").strip()
        if cleaned.startswith("```"):
            inline_fence = re.match(r"^```(?:[a-zA-Z0-9_-]+)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
            if inline_fence:
                cleaned = inline_fence.group(1).strip()
            else:
                lines = cleaned.splitlines()
                cleaned = "\n".join(lines[1:-1] if len(lines) > 2 else lines[1:]).strip()
        cleaned = re.sub(r"^(?:字段(?:填写)?(?:内容)?|答案|建议填写|可填写为|可直接填写为)[:：]\s*", "", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        if not cleaned:
            return "【待确认】当前缺少可直接填写该字段的资料。"
        return self._enforce_template_field_constraints(cleaned[:1200], field_type=field_type)

    def _template_field_rule(self, field_type: str | None) -> str:
        normalized = str(field_type or "general")
        if normalized == "precise_fact":
            return "只能填写可直接核验的精确事实；资料不够时直接输出【待确认】。"
        if normalized == "structural_summary":
            return "允许基于多份材料压缩概括，但不要夹带如何填写的解释。"
        if normalized == "governance_mechanism":
            return "强依赖章程、制度、会议纪要或党组织记录；资料不足时宁可输出【待确认】，不要写空泛套话。"
        if normalized == "quantitative_result":
            return "优先填写可引用数字；如果没有明确数字，不要用模糊描述凑数，直接输出【待确认】。"
        if normalized == "attachment_material":
            return "只判断材料是否已具备或缺失，不要输出解释性文字。"
        return "请尽量保守、可复核地填写，不要输出过程性提示。"

    def _enforce_template_field_constraints(self, text: str, *, field_type: str | None) -> str:
        cleaned = str(text or "").strip()
        if not cleaned:
            return "【待确认】当前缺少可直接填写该字段的资料。"
        process_hint_markers = (
            "可从",
            "进一步梳理",
            "建议补",
            "建议补充",
            "建议内部核验",
            "可填写",
            "如何填写",
        )
        if cleaned.startswith("【待确认】"):
            return cleaned
        normalized = str(field_type or "general")
        if normalized == "precise_fact":
            if any(marker in cleaned for marker in process_hint_markers) or any(marker in cleaned for marker in ("可能", "大约", "约", "左右", "公开招聘页面显示", "建设中")):
                return "【待确认】当前资料不足以直接确认该精确事实字段。"
        if normalized == "governance_mechanism":
            if any(marker in cleaned for marker in process_hint_markers):
                return "【待确认】当前缺少可直接支撑该治理/党建字段的章程、制度或会议记录。"
        if normalized == "quantitative_result":
            if not re.search(r"\d", cleaned):
                return "【待确认】当前缺少可直接引用的数量或统计口径。"
        if normalized == "attachment_material":
            if "已备" in cleaned or "待补" in cleaned:
                return cleaned
            return "【待确认】当前需进一步核验该材料是否已备齐。"
        return cleaned

    def _soften_caveat_heavy_opening(self, text: str) -> str:
        paragraphs = [item.strip() for item in re.split(r"\n{2,}", str(text).strip()) if item.strip()]
        if not paragraphs:
            return str(text).strip()
        target_index = 0
        if len(paragraphs) >= 2 and len(paragraphs[0]) <= 36 and not re.search(r"[。！？!?]", paragraphs[0]):
            target_index = 1
        first = paragraphs[target_index]
        if not any(
            marker in first
            for marker in (
                "需要首先明确",
                "需要首先说明",
                "资料主要聚焦于",
                "暂时无法确认",
                "以下分析将",
                "事实边界",
            )
        ):
            return "\n\n".join(paragraphs).strip()
        softened = first
        softened = re.sub(r"需要首先(?:明确|说明)的是，?", "", softened)
        softened = re.sub(r"现有资料主要聚焦于[^。！？!?]*[。！？!?]", "", softened)
        softened = re.sub(r"且多呈现为[^。！？!?]*[。！？!?]", "", softened)
        softened = re.sub(r"这意味着[^。！？!?]*暂时无法确认[^。！？!?]*[。！？!?]", "", softened)
        softened = re.sub(r"关于[^。！？!?]*暂时无法确认[^。！？!?]*[。！？!?]", "", softened)
        softened = re.sub(r"以下分析将[^。！？!?]*[。！？!?]", "", softened)
        softened = re.sub(r"就事实边界而言，?[^。！？!?]*[。！？!?]", "", softened)
        softened = re.sub(r"\s+", " ", softened).strip(" ，,。")
        if len(softened) < 24:
            softened = "已经能够勾勒出该对象当前的机构定位、战略意图与核心工作脉络，以下重点展开其中最有判断价值的部分。"
        if not re.search(r"[。！？!?]$", softened):
            softened = f"{softened}。"
        paragraphs[target_index] = softened
        refined = "\n\n".join(paragraphs).strip()
        refined = re.sub(r"基于益语智库当前掌握的[^。！？!?]*[。！？!?]", "", refined)
        refined = re.sub(r"根据现有[^。！？!?]*(?:观察|背景|底稿)[^。！？!?]*[。！？!?]", "", refined)
        refined = re.sub(r"从现有(?:资料|材料|观察)(?:交叉)?来看，?", "", refined)
        refined = re.sub(r"资料中反复出现的", "", refined)
        refined = re.sub(r"文档中(?:反复)?出现的", "", refined)
        refined = re.sub(r"工作坊记录显示", "", refined)
        refined = re.sub(r"\n{3,}", "\n\n", refined).strip()
        return refined

    def _format_provider_error(self, error: Exception | None) -> str:
        if error is None:
            return "未知模型错误"
        if isinstance(error, AiInvocationError):
            return error.detail
        message = str(error).strip() or error.__class__.__name__
        if isinstance(error, httpx.ReadTimeout):
            return f"读取超时：{message}"
        if isinstance(error, httpx.TimeoutException):
            return f"请求超时：{message}"
        if isinstance(error, httpx.HTTPStatusError):
            status = error.response.status_code if error.response is not None else "unknown"
            return f"上游状态异常 {status}：{message}"
        return message

    def _structured_from_text_sections(self, text: str) -> AiStructuredResponse:
        cleaned = str(text).strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(lines[1:-1] if len(lines) > 2 else lines[1:]).strip()
        sections = self._extract_section_blocks(cleaned)
        content = sections.get("内容综述", cleaned[:900]).strip()
        analysis = sections.get("结构化分析", sections.get("支持判断的要点", cleaned[:1500])).strip()
        actions = sections.get("建议动作", sections.get("下一步建议", "建议先确认当前资料能支撑的事实，再决定下一步动作。")).strip()
        judgment = sections.get("核心判断", "").strip()
        if not judgment:
            first_line = next((line.strip(" -") for line in analysis.splitlines() if line.strip()), "")
            judgment = first_line or content[:180]
        timeline = sections.get("关键时间线", "建议今天先形成初判，后续随资料补充再更新。").strip()
        return AiStructuredResponse(
            content=content or cleaned[:900],
            judgment=judgment or content[:180],
            analysis=analysis or cleaned[:1500],
            actions=actions,
            timeline=timeline,
        )

    def _extract_section_blocks(self, text: str) -> dict[str, str]:
        pattern = re.compile(r"【(内容综述|核心判断|结构化分析|建议动作|关键时间线|支持判断的要点|下一步建议)】")
        matches = list(pattern.finditer(text))
        if not matches:
            return {}
        sections: dict[str, str] = {}
        for index, match in enumerate(matches):
            label = match.group(1)
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            sections[label] = text[start:end].strip()
        return sections

    def _load_relaxed_json(self, text: str) -> dict[str, object]:
        stripped = str(text).strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            stripped = "\n".join(lines[1:-1] if len(lines) > 2 else lines[1:])
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            start = stripped.find("{")
            end = stripped.rfind("}")
            if start == -1 or end <= start:
                raise RuntimeError("模型返回了不可解析的 JSON。")
            payload = json.loads(stripped[start : end + 1])
        if not isinstance(payload, dict):
            raise RuntimeError("模型返回了非对象 JSON。")
        return payload

    def _fallback_topic_search_queries(self, *, title: str, prompt: str, time_range: str) -> list[str]:
        merged = f"{title} {prompt}".strip()
        for phrase in ("关注", "跟踪", "追踪", "最新", "案例", "信息", "新闻", "如何", "怎么", "打法"):
            merged = merged.replace(phrase, " ")
        merged = re.sub(r"[，。；：、,.!?！？\"“”‘’()（）]+", " ", merged)
        merged = re.sub(r"\s+", " ", merged).strip()
        parts = [part.strip() for part in merged.split(" ") if part.strip()]
        base = " ".join(parts[:6]).strip() or title.strip() or prompt.strip() or "行业资讯"
        compact_title = title.strip()
        window_label = {"1_day": "近一天", "3_days": "近三天", "7_days": "近七天"}.get(time_range, "")
        queries = [base]
        if compact_title and compact_title not in base:
            queries.append(f"{compact_title} {base}".strip())
        if compact_title:
            queries.append(f"{compact_title} {window_label}".strip())
        deduped: list[str] = []
        for item in queries:
            normalized = item.strip()
            if normalized and normalized not in deduped:
                deduped.append(normalized[:72])
        return deduped[:3] or ["行业资讯"]
