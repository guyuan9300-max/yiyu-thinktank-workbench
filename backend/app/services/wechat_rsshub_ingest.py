"""微信公众号自动收录 (P13-E · RSSHub 客户端).

策略 (最优方案, 非临时):
  1. 用户自部署 RSSHub (docker, 见 backend/runtime/rsshub/docker-compose.yml)
  2. RSSHub 把公众号镜像成 RSS feed (route: /wechat/ths/<key>/<id> 或 /wechat/cn/<id>)
  3. 本 service: fetch RSS → 解析每条 item → 把 mp.weixin.qq.com URL 列表交给
     internet_crawler 走完整入库管线 (content_domain='brand_official_corpus')
  4. content_hash 去重 + url 标准化 → 增量更新, 重复跑不会重复入库

URL 拼接规则参考 https://docs.rsshub.app/routes/new-media#wei-xin :
  - `<base>/wechat/ths/<key>/<wechat_id>` (推荐, 需 ths key)
  - `<base>/wechat/cn/<wechat_id>` (cn 镜像)
  - `<base>/wechat/wemp/<wechat_id>` (微小宝)
本 service 不绑定具体 route, 交由调用方完整传入 rss_url.
"""
from __future__ import annotations

import secrets
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

import httpx


@dataclass(frozen=True)
class WechatRssItem:
    title: str
    link: str
    pub_date: str
    description: str = ""
    guid: str = ""


@dataclass(frozen=True)
class WechatRssFeed:
    feed_url: str
    feed_title: str
    items: list[WechatRssItem] = field(default_factory=list)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def fetch_rss_feed(rss_url: str, *, timeout_seconds: float = 20.0) -> WechatRssFeed:
    """拉 RSS XML, 解析 channel/items.

    抛 ValueError 表示 URL/响应/解析失败 (调用方应捕获并返回 400/502).
    """
    rss_url = (rss_url or "").strip()
    if not rss_url:
        raise ValueError("rss_url 必填")
    parsed = urlsplit(rss_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"rss_url 非法: {rss_url}")
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/135.0 Safari/537.36"
        ),
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }
    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            response = client.get(rss_url, headers=headers)
    except httpx.RequestError as exc:
        raise ValueError(f"RSS 抓取失败: {exc}") from exc
    if response.status_code >= 400:
        raise ValueError(
            f"RSS 抓取失败: HTTP {response.status_code} (rsshub 服务可能未启动或路由错误)"
        )
    text = response.text or ""
    if not text.strip():
        raise ValueError("RSS 响应为空")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ValueError(f"RSS XML 解析失败: {exc}") from exc

    channel = root.find("channel")
    if channel is None:
        raise ValueError("RSS XML 缺少 <channel> 节点")
    feed_title = (channel.findtext("title") or "").strip()

    items: list[WechatRssItem] = []
    for item in channel.findall("item"):
        link = (item.findtext("link") or "").strip()
        if not link or "mp.weixin.qq.com" not in link.lower():
            # RSSHub 微信路由的 link 应是 mp.weixin.qq.com 文章链接, 否则跳过
            continue
        title = (item.findtext("title") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        description = (item.findtext("description") or "").strip()
        guid = (item.findtext("guid") or "").strip()
        items.append(
            WechatRssItem(
                title=title,
                link=link,
                pub_date=pub_date,
                description=description,
                guid=guid or link,
            )
        )
    return WechatRssFeed(feed_url=rss_url, feed_title=feed_title, items=items)


def _new_job_id() -> str:
    return "kjob_" + secrets.token_hex(5)


def build_ingest_payload(
    *,
    feed: WechatRssFeed,
    client_id: str,
    client_name: str,
    max_articles: int = 50,
) -> dict[str, Any]:
    """把 RSS 解析结果转成 internet_crawler.run_internet_enrichment 能吃的 payload."""
    max_articles = max(1, min(200, int(max_articles or 50)))
    items = feed.items[:max_articles]
    seed_urls = [item.link for item in items]
    return {
        "seedUrls": seed_urls,
        "seedQueries": [],
        "gaps": [],
        # mp.weixin.qq.com 单页文章, 没必要扩散; 整批文章靠 RSS 本身保证范围.
        "maxPages": max(10, len(seed_urls)),
        "maxDepth": 0,
        "reason": "wechat_rsshub_ingest",
        "targetType": "client",
        "targetId": client_id,
        "title": f"{client_name} · 公众号 RSSHub 自动收录",
        "clientName": client_name,
        # P13 关键: 入官方语料池, 不污染数据中心 internet_enrichment
        "contentDomainOverride": "brand_official_corpus",
        # 元信息用于审计 (run_internet_enrichment 不直接读, 但 knowledge_jobs payload_json 保留)
        "rssFeedUrl": feed.feed_url,
        "rssFeedTitle": feed.feed_title,
        "rssItemCount": len(items),
    }
