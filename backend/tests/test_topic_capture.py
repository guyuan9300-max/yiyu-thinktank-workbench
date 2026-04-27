from pathlib import Path
from datetime import datetime, timedelta
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services import topic_capture
from app.services.topic_capture import TopicSearchHit, _candidate_queries, _expand_topic_queries, _extract_prompt_queries, _keyword_tokens, fetch_topic_candidates_from_web
from app.services.topic_source_fetcher import PreferredSourceHit


class DummyAi:
    def suggest_topic_search_queries(self, *, title: str, prompt: str, time_range: str) -> list[str]:
        return ["第一条 近 30 天", "第二条"]

    def shortlist_topic_search_hits(self, *, title: str, prompt: str, hits: list[dict[str, str]], max_items: int = 4) -> list[dict[str, object]]:
        return [{"index": 1}]

    def localize_topic_hit(self, *, title: str, summary: str, radar_title: str, radar_prompt: str) -> dict[str, str]:
        return {"title": title, "summary": summary}


class FakeResponse:
    def __init__(self, text: str = "<rss></rss>"):
        self.text = text

    def raise_for_status(self) -> None:
        return None


class FakeClient:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url: str) -> FakeResponse:
        return FakeResponse()


def test_candidate_queries_strip_time_phrase_and_keep_fallback():
    queries = _candidate_queries(
        title="公益资助",
        prompt="公益资助线索，现金资助或服务购买",
        queries=["公益资助 现金资助 近 30 天", "公益组织 服务购买 项目案例"],
    )
    assert queries[0] == "公益资助 现金资助"
    assert "公益组织 服务购买 项目案例" in queries
    assert "公益资助" in queries


def test_extract_prompt_queries_reads_embedded_suggestions():
    prompt = '重点追踪 GitHub 爆，可优先使用 “GitHub 热门项目 3 天”、“GitHub Trending 新项目 价值分析” 这些搜索表达。'
    queries = _extract_prompt_queries(prompt)
    assert queries == ["GitHub 热门项目 3 天", "GitHub Trending 新项目 价值分析"]


def test_keyword_tokens_keep_concise_terms_and_drop_long_noise():
    tokens = _keyword_tokens(
        "CodeX 开发 我想找到更多与这个 code x 相关的经验分享的内容 "
        "可优先使用 “CodeX 开发板 开源项目”、“CodeX 半成型产品 落地经验” 这些搜索表达。"
    )
    assert "CodeX" in tokens
    assert "开发" in tokens
    assert "开发板" in tokens
    assert not any("经验分享的内容" in token for token in tokens)
    assert not any(len(token) > 12 and any("\u4e00" <= ch <= "\u9fff" for ch in token) for token in tokens)


def test_expand_topic_queries_for_technical_radar_adds_alias_clusters():
    queries = _expand_topic_queries(
        "CodeX 开发",
        "我想找到更多与这个 code x 相关的经验分享内容，最好是落地的一些开源项目和半成型产品。",
    )
    assert "OpenAI Codex 落地案例" in queries
    assert "Codex 开源项目 实战经验" in queries
    assert any("开发工作流" in item for item in queries)


def test_fetch_topic_candidates_tries_later_queries(monkeypatch):
    requested_queries: list[str] = []

    def fake_build_search_urls(*, query: str, time_range: str, preferred_source_urls=None):
        requested_queries.append(query)
        return [("google_news", f"https://example.com/{len(requested_queries)}", query)]

    def fake_parse_rss_hits(xml_text: str, *, provider: str, query: str):
        if query != "第二条":
            return []
        return [
            TopicSearchHit(
                title="第二条命中",
                summary="这是第二条查询词命中的测试内容。",
                source="测试来源",
                source_url="https://example.com/hit",
                published_at=None,
                provider=provider,
                query=query,
            )
        ]

    monkeypatch.setattr(topic_capture, "_build_search_urls", fake_build_search_urls)
    monkeypatch.setattr(topic_capture, "_parse_rss_hits", fake_parse_rss_hits)
    monkeypatch.setattr(topic_capture.httpx, "Client", lambda *args, **kwargs: FakeClient())

    hits = fetch_topic_candidates_from_web(
        DummyAi(),
        radar_title="大模型应用",
        radar_prompt="关注咨询行业的大模型应用实例。",
        time_range="3_days",
    )

    assert requested_queries[:2] == ["第一条", "第二条"]
    assert len(hits) == 1
    assert hits[0].query == "第二条"


def test_fetch_topic_candidates_filters_out_expired_hits(monkeypatch):
    recent_time = (datetime.now().astimezone() - timedelta(days=2)).replace(microsecond=0).isoformat()
    old_time = (datetime.now().astimezone() - timedelta(days=400)).replace(microsecond=0).isoformat()

    def fake_build_search_urls(*, query: str, time_range: str, preferred_source_urls=None):
        return [("google_news", "https://example.com/filter", query)]

    def fake_parse_rss_hits(xml_text: str, *, provider: str, query: str):
        return [
            TopicSearchHit(
                title="超出时间范围的旧新闻",
                summary="这条结果应该被过滤掉。",
                source="测试来源",
                source_url="https://example.com/old",
                published_at=old_time,
                provider=provider,
                query=query,
            ),
            TopicSearchHit(
                title="时间范围内的新新闻",
                summary="这条结果应该被保留下来。",
                source="测试来源",
                source_url="https://example.com/recent",
                published_at=recent_time,
                provider=provider,
                query=query,
            ),
        ]

    monkeypatch.setattr(topic_capture, "_build_search_urls", fake_build_search_urls)
    monkeypatch.setattr(topic_capture, "_parse_rss_hits", fake_parse_rss_hits)
    monkeypatch.setattr(topic_capture.httpx, "Client", lambda *args, **kwargs: FakeClient())

    hits = fetch_topic_candidates_from_web(
        DummyAi(),
        radar_title="公益资助",
        radar_prompt="关注近 30 天内的资助线索。",
        time_range="30_days",
    )

    assert len(hits) == 1
    assert hits[0].title == "时间范围内的新新闻"


def test_fetch_topic_candidates_includes_preferred_source_hits(monkeypatch):
    monkeypatch.setattr(
        topic_capture,
        "fetch_preferred_source_hits",
        lambda preferred_source_urls, max_items=8: [
            PreferredSourceHit(
                title="优先网址直抓命中",
                summary="这条结果来自配置站点的列表页。",
                source="中国发展简报",
                source_url="https://www.chinadevelopmentbrief.org.cn/abutment/detail/16463.html",
                published_at="2026-03-19T00:00:00",
                provider="preferred_source:list",
            )
        ],
    )
    monkeypatch.setattr(topic_capture, "_build_search_urls", lambda **kwargs: [])
    monkeypatch.setattr(topic_capture.httpx, "Client", lambda *args, **kwargs: FakeClient())

    hits = fetch_topic_candidates_from_web(
        DummyAi(),
        radar_title="公益资助",
        radar_prompt="关注公益资助与活动招募。",
        time_range="30_days",
        preferred_source_urls=["https://www.chinadevelopmentbrief.org.cn/abutment/index.html"],
    )

    assert len(hits) == 1
    assert hits[0].provider == "preferred_source:list"
    assert hits[0].title == "优先网址直抓命中"
