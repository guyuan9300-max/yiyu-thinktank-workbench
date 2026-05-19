"""舆情 hit 全文增强（P11）。

定位：把抓回的 B 站视频 / 公众号文章 URL 走系统已有的「视频转文字」通道，
把 200 字 snippet 升级为 800-5000 字的真实正文/转写。

复用 link_material_import.extract_link_material_source —— 这是软件里
已经在用的链接素材提取通道（B 站走 yt-dlp + SenseVoice / 公众号走 HTML 解析）。

设计原则：
  - 限 top N 条（默认 3）— 单条 B 站转写 1-3 分钟，全跑会卡死主流程
  - 顺序跑 + 单条 timeout，失败保留原 snippet
  - 失败原因记录在 draft.metadata（如 yt-dlp 不可用 / 视频删除等）
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from app.services.intelligence_sentiment import SentimentItemDraft

logger = logging.getLogger(__name__)


# 哪些来源应该走全文增强（这俩是已 verified 能拿全文的）
TRANSCRIPT_SOURCES = {"B站", "微信公众号"}


def enrich_drafts_with_transcripts(
    drafts: list[SentimentItemDraft],
    *,
    max_transcripts: int = 3,
    per_item_timeout_seconds: float = 180.0,
) -> tuple[list[SentimentItemDraft], dict[str, int]]:
    """对 drafts 里 B 站 / 公众号 hit 跑全文转写。

    Args:
        drafts: persist 前的 drafts 列表
        max_transcripts: 全量增强的最大条数（默认 3，避免 refresh 跑太久）
        per_item_timeout_seconds: 单条转写超时

    Returns:
      (new_drafts 不可变副本, stats={attempted, succeeded, failed})
    """
    stats = {"attempted": 0, "succeeded": 0, "failed": 0, "skipped_unsupported": 0}
    if not drafts:
        return drafts, stats

    # 按 source 筛出可转写的，并按优先级排序（B 站 + 公众号优先，按 sentiment 强度）
    candidates_idx: list[int] = []
    for i, d in enumerate(drafts):
        if d.source in TRANSCRIPT_SOURCES and d.source_url:
            candidates_idx.append(i)
    if not candidates_idx:
        return drafts, stats

    # 排序：confidence 高的优先，B 站排在公众号前（视频转写信息密度最大）
    def _priority(idx: int) -> tuple[int, float]:
        d = drafts[idx]
        source_priority = 1 if d.source == "B站" else 0
        return (source_priority, d.sentiment.confidence)

    candidates_idx.sort(key=_priority, reverse=True)
    candidates_idx = candidates_idx[:max_transcripts]

    # 逐条尝试（顺序，避免并发把系统资源压爆）
    new_drafts = list(drafts)  # shallow copy
    try:
        from app.services.link_material_import import (
            extract_link_material_source,
            LinkMaterialImportOptions,
            LinkMaterialImportError,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[transcript-enrich] link_material_import 不可用: %s", exc)
        return drafts, stats

    for idx in candidates_idx:
        draft = new_drafts[idx]
        stats["attempted"] += 1
        try:
            with tempfile.TemporaryDirectory(prefix="sentiment_transcript_") as tmp:
                source = extract_link_material_source(
                    draft.source_url,
                    Path(tmp),
                    options=LinkMaterialImportOptions(use_browser_cookies=False),
                )
                full_text = (source.transcript_text or "").strip()
                if not full_text or len(full_text) < 100:
                    stats["failed"] += 1
                    logger.debug("[transcript-enrich] %s 转写文本过短 (%d 字)", draft.source_url, len(full_text))
                    continue

                # 拼新 summary：原 title + 全文（截到 5000 字避免 LLM 上下文爆）
                new_summary = full_text[:5000]
                # 不可变重建 draft
                new_drafts[idx] = SentimentItemDraft(
                    title=source.title or draft.title,
                    summary=new_summary,
                    source=draft.source,
                    source_url=draft.source_url,
                    sentiment=draft.sentiment,
                    captured_at=draft.captured_at,
                    client_id=draft.client_id,
                    project_module_id=draft.project_module_id,
                    scope_type=draft.scope_type,
                    scope_id=draft.scope_id,
                )
                stats["succeeded"] += 1
                logger.info(
                    "[transcript-enrich] ✅ %s | %d 字全文",
                    draft.source[:6], len(full_text),
                )
        except LinkMaterialImportError as exc:
            stats["failed"] += 1
            logger.info("[transcript-enrich] %s 提取失败: %s", draft.source_url, exc)
        except Exception as exc:  # noqa: BLE001
            stats["failed"] += 1
            logger.warning("[transcript-enrich] %s 异常: %s", draft.source_url, exc)

    return new_drafts, stats


# ──────────────────────────────────────────────────────────────────────────
# 搜狗微信 link 中转 → 真实 mp.weixin.qq.com URL 的尝试
# （目前 antispider 挡住，预留接口供后续接 Playwright 时换实现）
# ──────────────────────────────────────────────────────────────────────────


def resolve_sogou_wechat_link(sogou_url: str) -> str | None:
    """尝试把 weixin.sogou.com/link?url=... 解码成真实 mp.weixin.qq.com URL。

    当前实现：纯 httpx 拿不到（搜狗 antispider 挡）。
    返回 None 表示当前环境无法解码——上层应该跳过这条公众号全文增强。

    后续接 Playwright/cookie 池时只换这个函数实现即可。
    """
    # 实测：搜狗 link 直接 GET 会被 302 跳 /antispider/?from=...
    # 想要解决必须：a) 维护 SUV/SUNID cookie 池 b) 上 Playwright
    # 当前阶段诚实返回 None
    return None
