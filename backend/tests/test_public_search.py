from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services import public_search
from app.services.public_search import PublicSearchResult


def test_public_search_continues_when_one_provider_fails(monkeypatch) -> None:
    def fail_provider(*_args, **_kwargs):
        raise RuntimeError("provider down")

    def sogou_provider(*_args, **_kwargs):
        return [
            PublicSearchResult(
                title="益语智库 信息公开",
                url="https://www.yiyu.example/about",
                snippet="益语智库公开信息。",
                source="www.yiyu.example",
                provider="sogou_html",
            )
        ]

    monkeypatch.setattr(public_search, "_fetch_so360_results", fail_provider)
    monkeypatch.setattr(public_search, "_fetch_sogou_results", sogou_provider)
    monkeypatch.setattr(public_search, "_fetch_bing_results", lambda *_args, **_kwargs: [])

    results = public_search.search_public_web(
        "益语智库 信息公开",
        providers=("so360_html", "sogou_html", "bing_html"),
    )

    assert len(results) == 1
    assert results[0].provider == "sogou_html"
    assert results[0].title == "益语智库 信息公开"


def test_public_search_filters_image_vertical_results() -> None:
    html = """
    <li class="b_algo">
      <h2><a href="https://image.so.com/i?q=%E7%9B%8A%E8%AF%AD%E6%99%BA%E5%BA%93">益语智库_360图片</a></h2>
      <p>查看全部图片搜索结果。</p>
    </li>
    <li class="b_algo">
      <h2><a href="https://www.yiyu.example/news">益语智库公开报道</a></h2>
      <p>益语智库公开报道正文摘要。</p>
    </li>
    """

    results = public_search._parse_bing_results(html)

    assert [item.url for item in results] == ["https://www.yiyu.example/news"]


def test_public_search_does_not_relax_long_timely_query_to_region_only() -> None:
    expanded = public_search._expand_queries("广东 儿童青少年心理健康 公益创投 申报 通知")
    ranking_terms = public_search._ranking_terms("广东 儿童青少年心理健康 公益创投 申报 通知")

    assert "广东" not in expanded[1:]
    assert "广东" not in ranking_terms
    assert any("儿童青少年心理健康" in item or "公益创投" in item for item in expanded)
