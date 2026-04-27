from __future__ import annotations

from typing import Any


def _field(hit: object, name: str) -> str:
    if isinstance(hit, dict):
        value = hit.get(name)
    else:
        value = getattr(hit, name, None)
    return str(value or "").strip()


def build_file_search_user_summary(search_result: Any) -> str:
    if not search_result:
        return "没有找到足够匹配的文件。可以换一个文件名、项目名或关键词再试。"
    selected_hits = getattr(search_result, "selectedHits", None)
    hits = list(selected_hits or getattr(search_result, "hits", []) or [])
    if not hits:
        return "没有找到足够匹配的文件。可以换一个文件名、项目名或关键词再试。"

    lines = ["我找到了这些可能相关的资料："]
    for index, hit in enumerate(hits[:8], start=1):
        title = _field(hit, "title") or "未命名资料"
        excerpt = _field(hit, "excerpt")
        path = _field(hit, "path")
        section = _field(hit, "sectionLabel")
        lines.append(f"{index}. {title}")
        if section:
            lines.append(f"   位置：{section}")
        if excerpt:
            lines.append(f"   片段：{excerpt[:180]}")
        if path:
            lines.append(f"   路径：{path}")
    lines.append("")
    lines.append("你可以点击文件卡片打开原文，或选择若干资料后让我基于这些资料生成回答。")
    return "\n".join(lines)
