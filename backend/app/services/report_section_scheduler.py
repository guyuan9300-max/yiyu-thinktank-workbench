"""R2 · 章节并行调度器。

ThreadPoolExecutor 把 N 个章节并行扔给 LLM B。max_workers 默认 4，可降。
进度回调 progress_cb(idx, status, content, error) 让上层（endpoint）
实时把 report_section_runs.status 写回 DB —— 前端 poll get_report_run
能看到逐节完成。
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from app.models import ReportBlueprint, SectionContent
from app.services.ai import AiService
from app.services.report_context_builder import ReportPromptContext
from app.services.report_section_drafter import (
    SectionDraftError,
    draft_section,
)


logger = logging.getLogger(__name__)


ProgressCallback = Callable[
    [int, str, SectionContent | None, str | None], None
]


def draft_sections_parallel(
    ai: AiService,
    *,
    blueprint: ReportBlueprint,
    context: ReportPromptContext,
    section_indices: list[int] | None = None,
    max_workers: int = 4,
    timeout_per_section: float = 120.0,
    progress_cb: ProgressCallback | None = None,
    glossary_pack: str = "",
) -> dict[int, SectionContent | str]:
    """并行起草多个章节。

    Args:
        section_indices: 要起草的章节下标子集；None = 全部
        max_workers: 并行 worker 数（触 rate limit 时降）
        timeout_per_section: 每节 LLM 调用 timeout（秒）
        progress_cb: 状态变化回调；status ∈ {"drafting", "done", "failed"}

    Returns:
        {section_idx: SectionContent 或 错误字符串}
    """
    if section_indices is None:
        target_indices = list(range(len(blueprint.sections)))
    else:
        target_indices = sorted(
            i
            for i in section_indices
            if 0 <= i < len(blueprint.sections)
        )

    if not target_indices:
        return {}

    results: dict[int, SectionContent | str] = {}
    effective_workers = max(1, min(max_workers, len(target_indices)))

    with ThreadPoolExecutor(
        max_workers=effective_workers, thread_name_prefix="report-sec"
    ) as pool:
        future_to_idx: dict = {}
        for idx in target_indices:
            plan = blueprint.sections[idx]
            if progress_cb is not None:
                try:
                    progress_cb(idx, "drafting", None, None)
                except Exception as cb_exc:
                    logger.warning(
                        "progress_cb(drafting, %d) raised: %s", idx, cb_exc
                    )
            fut = pool.submit(
                draft_section,
                ai,
                plan=plan,
                context=context,
                blueprint_title=blueprint.title,
                blueprint_audience=blueprint.audience,
                blueprint_tone=blueprint.tone,
                section_idx=idx,
                timeout_seconds=timeout_per_section,
                glossary_pack=glossary_pack,
            )
            future_to_idx[fut] = idx

        for fut in as_completed(future_to_idx):
            idx = future_to_idx[fut]
            try:
                content = fut.result()
                results[idx] = content
                if progress_cb is not None:
                    try:
                        progress_cb(idx, "done", content, None)
                    except Exception as cb_exc:
                        logger.warning(
                            "progress_cb(done, %d) raised: %s", idx, cb_exc
                        )
            except SectionDraftError as exc:
                err_msg = str(exc)
                results[idx] = err_msg
                logger.warning("section %d draft failed: %s", idx, err_msg)
                if progress_cb is not None:
                    try:
                        progress_cb(idx, "failed", None, err_msg)
                    except Exception as cb_exc:
                        logger.warning(
                            "progress_cb(failed, %d) raised: %s",
                            idx,
                            cb_exc,
                        )
            except Exception as exc:
                err_msg = f"未预期错误: {exc}"
                results[idx] = err_msg
                logger.exception(
                    "section %d unexpected error: %s", idx, exc
                )
                if progress_cb is not None:
                    try:
                        progress_cb(idx, "failed", None, err_msg)
                    except Exception as cb_exc:
                        logger.warning(
                            "progress_cb(failed-uncaught, %d) raised: %s",
                            idx,
                            cb_exc,
                        )

    return results
