from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services import topic_source_fetcher
from app.services.topic_source_fetcher import fetch_easyspider_source_hits, fetch_preferred_source_hits, fetch_rsshub_source_hits, fetch_trendradar_source_hits


class FakeResponse:
    def __init__(self, text: str, *, content_type: str = "text/html; charset=utf-8"):
        self.text = text
        self.headers = {"content-type": content_type}

    def raise_for_status(self) -> None:
        return None


class FakeClient:
    def __init__(self, responses: dict[str, FakeResponse]):
        self.responses = responses

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url: str):
        response = self.responses.get(url)
        if response is None:
            raise RuntimeError(f"unexpected url: {url}")
        return response


def test_fetch_preferred_source_hits_discovers_feed(monkeypatch):
    html = """
    <html>
      <head>
        <link rel="alternate" type="application/rss+xml" href="/feed.xml" />
      </head>
    </html>
    """
    feed = """
    <rss version="2.0">
      <channel>
        <title>测试站点</title>
        <item>
          <title>第一条更新</title>
          <link>https://example.com/posts/1</link>
          <description>这是一条来自 RSS 的摘要。</description>
          <pubDate>Fri, 14 Mar 2026 05:24:25 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """
    responses = {
        "https://example.com/": FakeResponse(html),
        "https://example.com/feed.xml": FakeResponse(feed, content_type="application/rss+xml"),
    }
    monkeypatch.setattr(topic_source_fetcher.httpx, "Client", lambda *args, **kwargs: FakeClient(responses))

    hits = fetch_preferred_source_hits(["https://example.com/"])

    assert len(hits) == 1
    assert hits[0].provider == "preferred_source:rss"
    assert hits[0].source == "测试站点"
    assert hits[0].source_url == "https://example.com/posts/1"
    assert hits[0].published_at is not None


def test_fetch_rsshub_source_hits_reads_feed(monkeypatch):
    feed = """
    <rss version="2.0">
      <channel>
        <title>RSSHub 测试源</title>
        <item>
          <title>RSSHub 第一条</title>
          <link>https://example.com/rsshub/1</link>
          <description>这是一条 RSSHub 摘要。</description>
          <pubDate>Fri, 14 Mar 2026 05:24:25 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """
    responses = {
        "https://rsshub.example/test": FakeResponse(feed, content_type="application/rss+xml"),
    }
    monkeypatch.setattr(topic_source_fetcher.httpx, "Client", lambda *args, **kwargs: FakeClient(responses))

    result = fetch_rsshub_source_hits("https://rsshub.example/test")

    assert result.status == "access_ok"
    assert result.error == ""
    assert len(result.hits) == 1
    assert result.hits[0].provider == "rsshub"
    assert result.hits[0].source == "RSSHub 测试源"


def test_fetch_rsshub_source_hits_marks_parse_failure(monkeypatch):
    responses = {
        "https://rsshub.example/broken": FakeResponse("<html>not xml", content_type="text/html"),
    }
    monkeypatch.setattr(topic_source_fetcher.httpx, "Client", lambda *args, **kwargs: FakeClient(responses))

    result = fetch_rsshub_source_hits("https://rsshub.example/broken")

    assert result.status == "parse_failed"
    assert result.error


def test_fetch_easyspider_source_hits_reads_exported_json():
    result = fetch_easyspider_source_hits(
        """
        [
          {
            "标题": "EasySpider 抓到的项目机会",
            "链接": "https://example.org/easyspider/1",
            "摘要": "这是 EasySpider 导出的结构化结果。",
            "来源": "重点来源站"
          }
        ]
        """
    )

    assert result.status == "access_ok"
    assert len(result.hits) == 1
    assert result.hits[0].provider == "easyspider"
    assert result.hits[0].title == "EasySpider 抓到的项目机会"


def test_fetch_easyspider_source_hits_marks_missing_config():
    result = fetch_easyspider_source_hits("easyspider-task-001")

    assert result.status == "needs_manual_config"
    assert result.error


def test_fetch_trendradar_source_hits_reads_public_opinion_sample_json():
    result = fetch_trendradar_source_hits(
        """
        {
          "items": [
            {
              "关键词": "公益数字化讨论升温",
              "摘要": "公开样本中开始集中讨论公益组织数字化能力。",
              "来源范围": "公开社媒与行业网站样本",
              "时间范围": "2026-04-22 至 2026-04-29",
              "样本数": 12,
              "趋势可信度": "low"
            }
          ]
        }
        """
    )

    assert result.status == "access_ok"
    assert len(result.hits) == 1
    assert result.hits[0].provider == "trendradar"
    assert result.hits[0].metadata["sourceScope"] == "公开社媒与行业网站样本"
    assert result.hits[0].metadata["sampleCount"] == 12
    assert result.hits[0].metadata["trendConfidence"] == "low"


def test_fetch_preferred_source_hits_parses_list_page_details(monkeypatch):
    list_html = """
    <html>
      <body>
        <a href="/abutment/detail/16463.html">基金会秘书长：这里有三个好项目，CFF喊你来！</a>
        <a href="/abutment/detail/16461.html">报名 | 调查报告发布会期待您的到来</a>
      </body>
    </html>
    """
    detail_one = """
    <html>
      <head>
        <title>基金会秘书长：这里有三个好项目，CFF喊你来！</title>
        <meta name="description" content="这是一条从详情页提取的摘要。" />
      </head>
      <body>
        <div class="source">来源：<span>基金会论坛</span></div>
        <div class="time pub-flex-align"><span>2026-03-19</span></div>
      </body>
    </html>
    """
    detail_two = """
    <html>
      <head>
        <title>报名 | 调查报告发布会期待您的到来</title>
        <meta name="description" content="第二条详情摘要。" />
      </head>
      <body>
        <div class="source">来源：<span>中国发展简报</span></div>
        <div class="time pub-flex-align"><span>2026-03-13</span></div>
      </body>
    </html>
    """
    responses = {
        "https://www.chinadevelopmentbrief.org.cn/abutment/index.html": FakeResponse(list_html),
        "https://www.chinadevelopmentbrief.org.cn/abutment/detail/16463.html": FakeResponse(detail_one),
        "https://www.chinadevelopmentbrief.org.cn/abutment/detail/16461.html": FakeResponse(detail_two),
    }
    monkeypatch.setattr(topic_source_fetcher.httpx, "Client", lambda *args, **kwargs: FakeClient(responses))

    hits = fetch_preferred_source_hits(["https://www.chinadevelopmentbrief.org.cn/abutment/index.html"])

    assert len(hits) == 2
    assert all(hit.provider == "preferred_source:list" for hit in hits)
    assert hits[0].source_url == "https://www.chinadevelopmentbrief.org.cn/abutment/detail/16463.html"
    assert hits[0].summary == "这是一条从详情页提取的摘要。"
    assert hits[0].source == "基金会论坛"
    assert hits[0].published_at is not None
