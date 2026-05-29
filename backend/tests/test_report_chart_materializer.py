"""R2 · chart_materializer 单测。"""

from __future__ import annotations

import base64

import pytest

from app.models import ChartHint
from app.services.report_chart_materializer import (
    ChartMaterializeError,
    materialize_chart,
)


def _hint(kind: str, title: str = "测试图") -> ChartHint:
    return ChartHint(
        kind=kind,  # type: ignore[arg-type]
        title=title,
        caption=None,
        data_source_hint="test",
    )


@pytest.mark.unit
def test_pie_happy() -> None:
    chart = materialize_chart(
        _hint("pie"),
        {"labels": ["A", "B", "C"], "counts": [10, 5, 3]},
    )
    assert chart.hint.kind == "pie"
    assert chart.png_bytes_base64
    raw = base64.b64decode(chart.png_bytes_base64)
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.unit
def test_pie_missing_labels() -> None:
    with pytest.raises(ChartMaterializeError, match="labels"):
        materialize_chart(_hint("pie"), {"counts": [1, 2]})


@pytest.mark.unit
def test_pie_size_mismatch() -> None:
    with pytest.raises(ChartMaterializeError, match="数量不一致"):
        materialize_chart(
            _hint("pie"), {"labels": ["A", "B"], "counts": [1, 2, 3]}
        )


@pytest.mark.unit
def test_pie_all_zero() -> None:
    with pytest.raises(ChartMaterializeError, match="全为 0"):
        materialize_chart(
            _hint("pie"), {"labels": ["A", "B"], "counts": [0, 0]}
        )


@pytest.mark.unit
def test_pie_negative_count() -> None:
    with pytest.raises(ChartMaterializeError, match="不能为负"):
        materialize_chart(
            _hint("pie"), {"labels": ["A", "B"], "counts": [3, -1]}
        )


@pytest.mark.unit
def test_progress_bar_h_happy() -> None:
    chart = materialize_chart(
        _hint("progress_bar_h"),
        {
            "items": ["模块 A", "模块 B"],
            "before": [30, 40],
            "after": [80, 70],
            "target": 75,
        },
    )
    assert chart.png_bytes_base64
    assert base64.b64decode(chart.png_bytes_base64)[:4] == b"\x89PNG"


@pytest.mark.unit
def test_progress_bar_h_no_before_defaults_zero() -> None:
    """before 缺省时应自动用 [0]*N（"从 0 起步" 是常见情形）。"""
    chart = materialize_chart(
        _hint("progress_bar_h"),
        {"items": ["A", "B"], "after": [50, 80]},
    )
    assert chart.png_bytes_base64


@pytest.mark.unit
def test_progress_bar_h_size_mismatch() -> None:
    with pytest.raises(ChartMaterializeError, match="数量不一致"):
        materialize_chart(
            _hint("progress_bar_h"),
            {
                "items": ["A", "B", "C"],
                "before": [30, 40],
                "after": [80, 70],
            },
        )


@pytest.mark.unit
def test_timeline_happy_tuple_form() -> None:
    chart = materialize_chart(
        _hint("timeline"),
        {
            "events": [
                ["2026-01-10", "启动会", "done"],
                ["2026-02-15", "中期检视", "in_progress"],
                ["2026-03-25", "Q1 收尾", "planned"],
            ]
        },
    )
    assert chart.png_bytes_base64


@pytest.mark.unit
def test_timeline_happy_dict_form() -> None:
    chart = materialize_chart(
        _hint("timeline"),
        {
            "events": [
                {"date": "2026-01-10", "label": "启动会", "status": "done"},
                {
                    "date": "2026-03-25",
                    "label": "Q1 收尾",
                    "status": "planned",
                },
            ]
        },
    )
    assert chart.png_bytes_base64


@pytest.mark.unit
def test_timeline_invalid_status_falls_back_to_planned() -> None:
    """非法 status 不应让整图报错，应静默回退到 planned。"""
    chart = materialize_chart(
        _hint("timeline"),
        {
            "events": [
                ["2026-01-10", "启动会", "weirdstatus"],
            ]
        },
    )
    assert chart.png_bytes_base64


@pytest.mark.unit
def test_timeline_no_events() -> None:
    with pytest.raises(ChartMaterializeError, match="events"):
        materialize_chart(_hint("timeline"), {"events": []})


@pytest.mark.unit
def test_timeline_all_invalid_events() -> None:
    with pytest.raises(ChartMaterializeError, match="全部无效"):
        materialize_chart(
            _hint("timeline"),
            {"events": [{"label": "缺日期"}, "纯字符串"]},
        )


@pytest.mark.unit
def test_grouped_bar_happy() -> None:
    chart = materialize_chart(
        _hint("grouped_bar"),
        {
            "categories": ["Q1", "Q2", "Q3"],
            "series_a_name": "实际",
            "series_a_values": [12, 18, 22],
            "series_b_name": "目标",
            "series_b_values": [10, 20, 20],
            "y_label": "完成数",
        },
    )
    assert chart.png_bytes_base64


@pytest.mark.unit
def test_grouped_bar_size_mismatch() -> None:
    with pytest.raises(ChartMaterializeError, match="数量不一致"):
        materialize_chart(
            _hint("grouped_bar"),
            {
                "categories": ["Q1", "Q2"],
                "series_a_name": "a",
                "series_a_values": [1],
                "series_b_name": "b",
                "series_b_values": [2, 3],
            },
        )


@pytest.mark.unit
def test_risk_bubble_happy() -> None:
    chart = materialize_chart(
        _hint("risk_bubble"),
        {
            "risks": [
                ["人员流失", 4, 3, 2.0],
                ["资金不足", 3, 4, 3.0],
                ["范围蔓延", 2, 2, 1.5],
            ]
        },
    )
    assert chart.png_bytes_base64


@pytest.mark.unit
def test_risk_bubble_clamps_out_of_range() -> None:
    """impact / prob 超出 0-5 应该被钳，不应 raise。"""
    chart = materialize_chart(
        _hint("risk_bubble"),
        {"risks": [["A", 9, 9, 2.0], ["B", -3, 8, 0.05]]},
    )
    assert chart.png_bytes_base64


@pytest.mark.unit
def test_risk_bubble_dict_form() -> None:
    chart = materialize_chart(
        _hint("risk_bubble"),
        {
            "risks": [
                {"name": "X", "impact": 3, "prob": 4, "weight": 2.5},
                {"name": "Y", "impact": 1, "probability": 1, "weight": 1.0},
            ]
        },
    )
    assert chart.png_bytes_base64


@pytest.mark.unit
def test_risk_bubble_all_invalid() -> None:
    with pytest.raises(ChartMaterializeError, match="全部无效"):
        materialize_chart(
            _hint("risk_bubble"),
            {"risks": [{"name": ""}, "not-a-dict"]},
        )


@pytest.mark.unit
def test_table_only_returns_placeholder() -> None:
    chart = materialize_chart(_hint("table_only", "对比表"), {})
    assert chart.png_bytes_base64 == ""
    assert chart.hint.kind == "table_only"


@pytest.mark.unit
def test_callout_only_returns_placeholder() -> None:
    chart = materialize_chart(_hint("callout_only", "提醒"), {"anything": 1})
    assert chart.png_bytes_base64 == ""


@pytest.mark.unit
def test_data_not_dict_raises_for_real_chart() -> None:
    with pytest.raises(ChartMaterializeError, match="必须是 dict"):
        materialize_chart(_hint("pie"), "not a dict")  # type: ignore[arg-type]


@pytest.mark.unit
def test_placeholder_kind_accepts_non_dict_data() -> None:
    """占位图（table_only / callout_only）不会检查 data 类型。"""
    chart = materialize_chart(_hint("table_only"), None)  # type: ignore[arg-type]
    assert chart.png_bytes_base64 == ""
