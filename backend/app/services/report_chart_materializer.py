"""R2 · 把 LLM B 输出的 chart 数据 + ChartHint 派发到 chart_generator，
生成真实 PNG 并 base64 编码。

5 种实图（pie / progress_bar_h / timeline / grouped_bar / risk_bubble）
+ 2 种占位（table_only / callout_only 不画图，但仍返回 GeneratedChart 占位）。

matplotlib pyplot 全局 state 在多线程下不安全，所有渲染都串行通过 _CHART_LOCK。
LLM 调用是大头（30-90s），chart 渲染只占毫秒级，串行不会成为瓶颈。
"""

from __future__ import annotations

import base64
import logging
import threading
from typing import Any

from app.models import ChartHint, GeneratedChart
from app.services import report_chart_generator as cg


logger = logging.getLogger(__name__)


_CHART_LOCK = threading.Lock()
_PLACEHOLDER_KINDS = {"table_only", "callout_only"}


class ChartMaterializeError(RuntimeError):
    """绘图失败（数据形状不对、依赖出错等），上层 drafter 接住记 warning。"""


def materialize_chart(hint: ChartHint, data: dict[str, Any]) -> GeneratedChart:
    """根据 hint.kind 派发到对应 chart_generator 函数。

    table_only / callout_only：不画图，但仍返回 GeneratedChart 占位
    （base64 为空），渲染器 R3 读到空字符串就只走 markdown，不嵌图。
    """
    if hint.kind in _PLACEHOLDER_KINDS:
        return GeneratedChart(hint=hint, png_bytes_base64="", width_cm=14.5)

    if not isinstance(data, dict):
        raise ChartMaterializeError(
            f"chart data 必须是 dict，得到 {type(data).__name__}"
        )

    try:
        with _CHART_LOCK:
            png_bytes = _dispatch(hint.kind, hint.title, data)
    except ChartMaterializeError:
        raise
    except Exception as exc:
        raise ChartMaterializeError(
            f"绘图失败 ({hint.kind} · {hint.title}): {exc}"
        ) from exc

    encoded = base64.b64encode(png_bytes).decode("ascii")
    return GeneratedChart(hint=hint, png_bytes_base64=encoded, width_cm=14.5)


def _dispatch(kind: str, title: str, data: dict[str, Any]) -> bytes:
    if kind == "pie":
        return _pie(title, data)
    if kind == "progress_bar_h":
        return _progress_bar_h(title, data)
    if kind == "timeline":
        return _timeline(title, data)
    if kind == "grouped_bar":
        return _grouped_bar(title, data)
    if kind == "risk_bubble":
        return _risk_bubble(title, data)
    raise ChartMaterializeError(f"未知图表类型: {kind}")


def _pie(title: str, data: dict[str, Any]) -> bytes:
    labels = list(data.get("labels") or [])
    counts = list(data.get("counts") or [])
    if not labels or not counts:
        raise ChartMaterializeError("pie 需要 labels 和 counts")
    if len(labels) != len(counts):
        raise ChartMaterializeError(
            f"pie labels({len(labels)}) 与 counts({len(counts)}) 数量不一致"
        )
    try:
        counts_int = [int(c) for c in counts]
    except (TypeError, ValueError) as exc:
        raise ChartMaterializeError(f"pie counts 必须是整数：{exc}")
    if any(c < 0 for c in counts_int):
        raise ChartMaterializeError("pie counts 不能为负")
    if sum(counts_int) == 0:
        raise ChartMaterializeError("pie counts 全为 0，无可绘内容")
    return cg.pie_commit_breakdown(
        title=title, labels=[str(l) for l in labels], counts=counts_int
    )


def _progress_bar_h(title: str, data: dict[str, Any]) -> bytes:
    items = [str(x) for x in (data.get("items") or [])]
    if not items:
        raise ChartMaterializeError("progress_bar_h 需要 items 列表")
    after_raw = data.get("after") or []
    if not after_raw:
        raise ChartMaterializeError("progress_bar_h 需要 after 列表")
    before_raw = data.get("before")
    if before_raw is None or len(before_raw) == 0:
        before_raw = [0.0] * len(items)
    if len(items) != len(after_raw) or len(items) != len(before_raw):
        raise ChartMaterializeError(
            f"progress_bar_h items/before/after 数量不一致: "
            f"items={len(items)} before={len(before_raw)} after={len(after_raw)}"
        )
    try:
        before = [float(x) for x in before_raw]
        after = [float(x) for x in after_raw]
    except (TypeError, ValueError) as exc:
        raise ChartMaterializeError(f"progress_bar_h 数值非法：{exc}")
    target = data.get("target")
    if target is not None:
        try:
            target = float(target)
        except (TypeError, ValueError):
            target = None
    return cg.progress_bar_h(
        title=title, items=items, before=before, after=after, target=target
    )


def _timeline(title: str, data: dict[str, Any]) -> bytes:
    raw = data.get("events") or []
    if not raw:
        raise ChartMaterializeError("timeline 需要 events")
    events: list[tuple[str, str, str]] = []
    for entry in raw:
        if isinstance(entry, dict):
            date = str(entry.get("date") or "").strip()
            label = str(entry.get("label") or "").strip()
            status = str(entry.get("status") or "planned").strip()
        elif isinstance(entry, (list, tuple)) and len(entry) >= 3:
            date = str(entry[0] or "").strip()
            label = str(entry[1] or "").strip()
            status = str(entry[2] or "planned").strip()
        else:
            continue
        if not date or not label:
            continue
        if status not in {"done", "in_progress", "planned"}:
            status = "planned"
        events.append((date, label, status))
    if not events:
        raise ChartMaterializeError("timeline events 全部无效")
    return cg.timeline(title=title, events=events)


def _grouped_bar(title: str, data: dict[str, Any]) -> bytes:
    categories = [str(x) for x in (data.get("categories") or [])]
    if not categories:
        raise ChartMaterializeError("grouped_bar 需要 categories")
    series_a = data.get("series_a_values") or []
    series_b = data.get("series_b_values") or []
    if len(categories) != len(series_a) or len(categories) != len(series_b):
        raise ChartMaterializeError(
            f"grouped_bar 数量不一致 categories={len(categories)} "
            f"a={len(series_a)} b={len(series_b)}"
        )
    try:
        series_a_values = [float(x) for x in series_a]
        series_b_values = [float(x) for x in series_b]
    except (TypeError, ValueError) as exc:
        raise ChartMaterializeError(f"grouped_bar 数值非法：{exc}")
    return cg.grouped_bar(
        title=title,
        categories=categories,
        series_a_name=str(data.get("series_a_name") or "系列 A"),
        series_a_values=series_a_values,
        series_b_name=str(data.get("series_b_name") or "系列 B"),
        series_b_values=series_b_values,
        y_label=str(data.get("y_label") or "数量"),
    )


def _risk_bubble(title: str, data: dict[str, Any]) -> bytes:
    raw = data.get("risks") or []
    if not raw:
        raise ChartMaterializeError("risk_bubble 需要 risks")
    risks: list[tuple[str, float, float, float]] = []
    for entry in raw:
        if isinstance(entry, dict):
            name = str(entry.get("name") or "").strip()
            try:
                impact = float(entry.get("impact") or 0)
                prob = float(
                    entry.get("prob") or entry.get("probability") or 0
                )
                weight = float(entry.get("weight") or 1.0)
            except (TypeError, ValueError):
                continue
        elif isinstance(entry, (list, tuple)) and len(entry) >= 4:
            name = str(entry[0] or "").strip()
            try:
                impact = float(entry[1])
                prob = float(entry[2])
                weight = float(entry[3])
            except (TypeError, ValueError):
                continue
        else:
            continue
        if not name:
            continue
        impact = max(0.0, min(5.0, impact))
        prob = max(0.0, min(5.0, prob))
        weight = max(0.1, min(10.0, weight))
        risks.append((name, impact, prob, weight))
    if not risks:
        raise ChartMaterializeError("risk_bubble risks 全部无效")
    return cg.risk_bubble(title=title, risks=risks)
