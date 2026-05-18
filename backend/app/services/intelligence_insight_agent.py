"""Insight Agent — 舆情条目的深度判断（Qwen LLM 兜底）。

定位（参考 BettaFish 多 Agent 思路，做了简化）：
  - 词表分级覆盖 90% 明显的正/负/中性；
  - 剩 10% 边界情况（confidence 低、neutral 但含 soft_neg、negative 但被网站噪声影响）
    交给本 Agent 用 Qwen 二次判定 + 抽取"投诉主题"。
  - 不对所有 draft 跑 LLM —— qwen3-vl:32b 调一次 1~3 秒，全跑会让 refresh 卡 10 分钟。
  - 严格复用 ai.py 的 _qwen_generate，不另起进程，符合 [[project_yiyu_model_reuse]]。

输出：
  - 升级 / 修正 SentimentAnalysisResult 的 label / confidence / reason；
  - 新增字段 insight_theme（"信息不公开 / 善款流向不明"等具体投诉点）。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from app.services.intelligence_sentiment import (
    SentimentAnalysisResult,
    SentimentItemDraft,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# 判断哪些 draft 值得跑 LLM（成本控制）
# ──────────────────────────────────────────────────────────────────────────


def _needs_deep_judge(draft: SentimentItemDraft) -> bool:
    """决定是否对这条 draft 跑 Qwen 二次判定。

    规则：
      1. label=negative 但 confidence < 0.7：可能误判（被噪声词触发），让 LLM 复核；
      2. label=neutral 但 reason 含"soft_neg 无上下文"：可能漏判，让 LLM 看真上下文；
      3. label=positive：跳过（误判风险低）；
      4. label=negative 且 confidence >= 0.85：硬负词命中，跳过（省钱）。
    """
    s = draft.sentiment
    if s.label == "negative" and s.confidence < 0.7:
        return True
    if s.label == "neutral" and "soft_neg" in (s.reason or "").lower():
        return True
    if s.label == "neutral" and any(
        kw in (s.reason or "") for kw in ("无上下文", "孤立的负面词", "可能为模板")
    ):
        return True
    return False


# ──────────────────────────────────────────────────────────────────────────
# LLM Prompt
# ──────────────────────────────────────────────────────────────────────────

INSIGHT_SYSTEM_INSTRUCTION = (
    "你是舆情分析师。给你一条搜索引擎抓到的网页摘要，"
    "判断对目标对象（target_name）是 negative / neutral / positive 三档中的哪档；"
    "如果是 negative，再抽出 1 句话的 insight_theme（投诉/质疑的具体点，如『信息不公开』『善款流向不明』）。"
    "严格只看针对 target_name 的态度，避免把同页其他内容当成对它的评价。"
    "只返回 JSON，不要任何解释。"
)

INSIGHT_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["label", "confidence"],
    "properties": {
        "label": {"type": "string", "enum": ["negative", "neutral", "positive"]},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "reason": {"type": "string"},
        "insight_theme": {"type": "string"},
    },
}


def _build_prompt(draft: SentimentItemDraft, target_name: str) -> str:
    return (
        f"target_name: {target_name}\n\n"
        f"网页标题: {draft.title}\n"
        f"网页摘要:\n{draft.summary}\n\n"
        f"来源: {draft.source} ({draft.source_url})\n\n"
        f"词表初判: label={draft.sentiment.label} confidence={draft.sentiment.confidence:.2f} "
        f"reason={draft.sentiment.reason}\n\n"
        "请判断这条摘要对 target_name 的态度："
    )


# ──────────────────────────────────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class DeepJudgeStats:
    """统计 LLM 调用次数 / 命中改判次数，供调试 + 限速。"""
    candidates: int = 0
    invoked: int = 0
    flipped: int = 0
    failed: int = 0


def deep_judge_drafts(
    ai_service: object | None,
    drafts: list[SentimentItemDraft],
    *,
    target_name: str,
    max_invocations: int = 8,
    timeout_seconds: float = 25.0,
) -> tuple[list[SentimentItemDraft], DeepJudgeStats]:
    """对 drafts 列表中需要复核的条目跑 Qwen 二次判定。

    Args:
        ai_service: AiService 实例（state.ai）。None 时直接返回原列表。
        drafts: 词表初判后的 drafts。
        target_name: 监控对象主名。
        max_invocations: 单次 refresh 最多调几次 LLM（默认 8 次，~24s）。
        timeout_seconds: 单次 LLM 调用 timeout。

    Returns:
        (新 drafts 列表, 统计)。原列表不变（[[coding-style.md immutability]]）。
    """
    stats = DeepJudgeStats()
    if not ai_service or not drafts:
        return drafts, stats

    # 检查 ai_service 是否可用（避免对死配置调 LLM 慢死）
    try:
        health = ai_service.get_health()  # type: ignore[attr-defined]
        if not getattr(health, "ready", False):
            logger.info("[insight-agent] ai_service not ready, skip deep judge")
            return drafts, stats
    except Exception:  # noqa: BLE001
        return drafts, stats

    new_drafts: list[SentimentItemDraft] = []
    for draft in drafts:
        if stats.invoked >= max_invocations or not _needs_deep_judge(draft):
            new_drafts.append(draft)
            continue
        stats.candidates += 1
        upgraded = _judge_one(ai_service, draft, target_name=target_name, timeout_seconds=timeout_seconds)
        if upgraded is None:
            stats.failed += 1
            new_drafts.append(draft)
            continue
        stats.invoked += 1
        new_sent, new_summary = upgraded
        if new_sent.label != draft.sentiment.label:
            stats.flipped += 1
        # 不可变：构造新 draft
        new_drafts.append(SentimentItemDraft(
            title=draft.title,
            summary=new_summary or draft.summary,
            source=draft.source,
            source_url=draft.source_url,
            sentiment=new_sent,
            captured_at=draft.captured_at,
            client_id=draft.client_id,
            project_module_id=draft.project_module_id,
            scope_type=draft.scope_type,
            scope_id=draft.scope_id,
        ))
    return new_drafts, stats


def _judge_one(
    ai_service: object,
    draft: SentimentItemDraft,
    *,
    target_name: str,
    timeout_seconds: float,
) -> tuple[SentimentAnalysisResult, str] | None:
    """单条 LLM 调用。返回 (新 sentiment, 新 summary) 或 None（失败时）。"""
    try:
        raw = ai_service._qwen_generate(  # type: ignore[attr-defined]  # noqa: SLF001
            _build_prompt(draft, target_name),
            INSIGHT_SYSTEM_INSTRUCTION,
            INSIGHT_RESPONSE_SCHEMA,
            timeout_seconds=timeout_seconds,
            max_tokens=400,
            temperature=0.1,
            task_kind="fast_structured",
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("[insight-agent] _qwen_generate failed for url=%s: %s", draft.source_url, exc)
        return None

    if not isinstance(raw, dict):
        # 有时返回 JSON 字符串
        try:
            raw = json.loads(str(raw))
        except Exception:  # noqa: BLE001
            return None
    if not isinstance(raw, dict):
        return None

    label = str(raw.get("label") or "").strip().lower()
    if label not in ("negative", "neutral", "positive"):
        return None
    try:
        confidence = float(raw.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    reason = str(raw.get("reason") or "").strip() or f"LLM 复核：{label}"
    insight_theme = str(raw.get("insight_theme") or "").strip()

    # score：保留词表 score 的符号方向但用 LLM confidence 加权
    if label == "negative":
        score = -confidence
    elif label == "positive":
        score = confidence
    else:
        score = 0.0

    new_sentiment = SentimentAnalysisResult(
        label=label,
        score=score,
        confidence=confidence,
        matched_terms=list(draft.sentiment.matched_terms),  # 保留词表命中信息
        reason=f"[LLM] {reason}",
    )

    # 把 insight_theme 拼进 summary 头部，前端不改 UI 也能看到
    new_summary = draft.summary
    if insight_theme and label == "negative":
        new_summary = f"【主题】{insight_theme}\n{draft.summary}"

    return new_sentiment, new_summary
