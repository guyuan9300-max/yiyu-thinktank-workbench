from __future__ import annotations

from typing import Any


def _field(hit: object, name: str) -> str:
    if isinstance(hit, dict):
        value = hit.get(name)
    else:
        value = getattr(hit, name, None)
    return str(value or "").strip()


def _list_field(hit: object, name: str) -> list[str]:
    if isinstance(hit, dict):
        value = hit.get(name)
    else:
        value = getattr(hit, name, None)
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


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
        path = _field(hit, "displayPath") or _field(hit, "virtualOptimizedPath") or _field(hit, "path")
        section = _field(hit, "sectionLabel")
        purpose = _field(hit, "purpose")
        audience = _field(hit, "audience")
        project_context = _field(hit, "projectContext")
        topics = _list_field(hit, "keyTopics")
        risk = _field(hit, "riskNotes")
        lines.append(f"{index}. {title}")
        if section:
            lines.append(f"   位置：{section}")
        if excerpt:
            lines.append(f"   片段：{excerpt[:180]}")
        if path:
            lines.append(f"   路径：{path}")
        if purpose or audience or project_context:
            card_bits = []
            if purpose:
                card_bits.append(f"用途：{purpose}")
            if audience:
                card_bits.append(f"服务对象：{audience}")
            if project_context:
                card_bits.append(f"项目语境：{project_context}")
            lines.append(f"   名片：{'；'.join(card_bits)}")
        if topics:
            lines.append(f"   主题：{'、'.join(topics[:5])}")
        if risk:
            lines.append(f"   提醒：{risk}")
    lines.append("")
    lines.append("你可以点击文件卡片打开原文，或选择若干资料后让我基于这些资料生成回答。")
    return "\n".join(lines)
