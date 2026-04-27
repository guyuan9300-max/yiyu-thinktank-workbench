from __future__ import annotations

import re
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

import httpx


FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

DETAIL_HINT_PATTERNS = (
    re.compile(r"/detail/\d+\.html?$", re.I),
    re.compile(r"/article/\d+\.html?$", re.I),
    re.compile(r"/news/.+\.html?$", re.I),
    re.compile(r"/\d+\.html?$", re.I),
)

IGNORE_PATH_PATTERNS = (
    re.compile(r"/(?:login|logout|register)(?:/|$)", re.I),
    re.compile(r"/(?:category|tag|tags|author|search)(?:/|$)", re.I),
    re.compile(r"/(?:about|contact|guide|help|terms|privacy)(?:/|$)", re.I),
)

DATE_PATTERNS = (
    re.compile(r'class="[^"]*(?:time|date|publish)[^"]*"[^>]*>.*?<span[^>]*>\s*([12]\d{3}-\d{1,2}-\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)', re.I | re.S),
    re.compile(r'class="[^"]*(?:time|date|publish)[^"]*"[^>]*>\s*([12]\d{3}-\d{1,2}-\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)', re.I | re.S),
    re.compile(r'([12]\d{3}-\d{1,2}-\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)'),
)


@dataclass
class PreferredSourceHit:
    title: str
    summary: str
    source: str
    source_url: str
    published_at: str | None
    provider: str


def fetch_preferred_source_hits(
    preferred_source_urls: list[str] | None,
    *,
    max_items: int = 8,
) -> list[PreferredSourceHit]:
    if not preferred_source_urls:
        return []

    hits: list[PreferredSourceHit] = []
    seen_urls: set[str] = set()
    with httpx.Client(timeout=httpx.Timeout(12.0, connect=6.0), headers=FETCH_HEADERS, follow_redirects=True) as client:
        for source_url in preferred_source_urls[:4]:
            for hit in _fetch_single_preferred_source(client, source_url, max_items=max_items):
                normalized_url = hit.source_url.strip().lower()
                if not normalized_url or normalized_url in seen_urls:
                    continue
                seen_urls.add(normalized_url)
                hits.append(hit)
                if len(hits) >= max_items:
                    return hits
    return hits


def _fetch_single_preferred_source(client: httpx.Client, source_url: str, *, max_items: int) -> list[PreferredSourceHit]:
    response = _safe_get(client, source_url)
    if response is None:
        return []
    content_type = response.headers.get("content-type", "")
    text = response.text

    if _looks_like_feed(text, content_type=content_type):
        return _parse_feed_hits(text, source_url=source_url)[:max_items]

    feed_url = _discover_feed_url(text, base_url=source_url)
    if feed_url:
        feed_response = _safe_get(client, feed_url)
        if feed_response and _looks_like_feed(feed_response.text, content_type=feed_response.headers.get("content-type", "")):
            feed_hits = _parse_feed_hits(feed_response.text, source_url=feed_url)
            if feed_hits:
                return feed_hits[:max_items]

    list_hits = _fetch_list_page_hits(client, source_url=source_url, html=text, max_items=max_items)
    if list_hits:
        return list_hits

    detail_hit = _parse_detail_hit(source_url, text, fallback_title="", fallback_source=_domain_label(source_url))
    return [detail_hit] if detail_hit is not None else []


def _safe_get(client: httpx.Client, url: str) -> httpx.Response | None:
    try:
        response = client.get(url)
        response.raise_for_status()
        return response
    except Exception:
        return None


def _looks_like_feed(text: str, *, content_type: str) -> bool:
    content = (text or "").lstrip().lower()
    ctype = (content_type or "").lower()
    if "xml" in ctype or "rss" in ctype or "atom" in ctype:
        return "<rss" in content or "<feed" in content or "<rdf" in content
    return content.startswith("<?xml") and ("<rss" in content or "<feed" in content or "<rdf" in content)


def _discover_feed_url(html: str, *, base_url: str) -> str | None:
    match = re.search(
        r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]+href=["\']([^"\']+)["\']',
        html,
        flags=re.I,
    )
    if match:
        return urljoin(base_url, match.group(1).strip())

    parsed = urlparse(base_url)
    normalized_path = (parsed.path or "").rstrip("/")
    if normalized_path not in {"", "/index.html", "/index.htm"}:
        return None
    for suffix in ("/feed", "/rss", "/rss.xml", "/feed.xml"):
        feed_url = f"{parsed.scheme}://{parsed.netloc}{suffix}"
        if feed_url != base_url:
            return feed_url
    return None


def _parse_feed_hits(xml_text: str, *, source_url: str) -> list[PreferredSourceHit]:
    hits: list[PreferredSourceHit] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return hits

    channel = root.find("channel")
    channel_title = _clean_text(channel.findtext("title") if channel is not None else "")
    feed_source = channel_title or _domain_label(source_url)

    items = channel.findall("item") if channel is not None else []
    if items:
        for item in items[:8]:
            title = _clean_text(item.findtext("title"))
            link = _clean_text(item.findtext("link"))
            summary = _clean_text(item.findtext("description")) or title
            published_at = _normalize_datetime(item.findtext("pubDate") or item.findtext("published") or item.findtext("updated"))
            if not title or not link:
                continue
            hits.append(
                PreferredSourceHit(
                    title=title[:120],
                    summary=summary[:180],
                    source=feed_source,
                    source_url=link,
                    published_at=published_at,
                    provider="preferred_source:rss",
                )
            )
        return hits

    entries = [item for item in root.findall(".//{*}entry")][:8]
    for entry in entries:
        title = _clean_text(_find_xml_text(entry, "title"))
        link = _extract_entry_link(entry)
        summary = _clean_text(_find_xml_text(entry, "summary") or _find_xml_text(entry, "content")) or title
        published_at = _normalize_datetime(_find_xml_text(entry, "published") or _find_xml_text(entry, "updated"))
        if not title or not link:
            continue
        hits.append(
            PreferredSourceHit(
                title=title[:120],
                summary=summary[:180],
                source=feed_source,
                source_url=link,
                published_at=published_at,
                provider="preferred_source:rss",
            )
        )
    return hits


def _find_xml_text(node: ET.Element, tag: str) -> str:
    child = node.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    for sub in node:
        if sub.tag.endswith(tag) and sub.text:
            return sub.text.strip()
    return ""


def _extract_entry_link(entry: ET.Element) -> str:
    direct = _find_xml_text(entry, "link")
    if direct:
        return direct
    for sub in entry:
        if sub.tag.endswith("link"):
            href = sub.attrib.get("href")
            if href:
                return href.strip()
    return ""


def _fetch_list_page_hits(client: httpx.Client, *, source_url: str, html: str, max_items: int) -> list[PreferredSourceHit]:
    candidates = _extract_list_links(html, base_url=source_url)
    hits: list[PreferredSourceHit] = []
    for detail_url, fallback_title in candidates[: max_items * 2]:
        response = _safe_get(client, detail_url)
        if response is None:
            continue
        hit = _parse_detail_hit(
            detail_url,
            response.text,
            fallback_title=fallback_title,
            fallback_source=_domain_label(source_url),
        )
        if hit is None:
            continue
        hits.append(hit)
        if len(hits) >= max_items:
            break
    return hits


def _extract_list_links(html: str, *, base_url: str) -> list[tuple[str, str]]:
    domain = urlparse(base_url).netloc.lower()
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for href, inner_html in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, flags=re.I | re.S):
        normalized_url = urljoin(base_url, href.strip())
        parsed = urlparse(normalized_url)
        if parsed.netloc.lower() != domain:
            continue
        if normalized_url in seen or not _looks_like_detail_link(parsed.path):
            continue
        title = _clean_text(inner_html)
        if len(title) < 6:
            continue
        seen.add(normalized_url)
        links.append((normalized_url, title))
    return links


def _looks_like_detail_link(path: str) -> bool:
    if not path:
        return False
    if any(pattern.search(path) for pattern in IGNORE_PATH_PATTERNS):
        return False
    if any(pattern.search(path) for pattern in DETAIL_HINT_PATTERNS):
        return True
    return False


def _parse_detail_hit(detail_url: str, html: str, *, fallback_title: str, fallback_source: str) -> PreferredSourceHit | None:
    title = _extract_html_title(html) or fallback_title
    title = _clean_text(title)
    if not title:
        return None
    summary = _extract_meta_content(html, "description") or _extract_first_paragraphs(html)
    summary = _clean_text(summary) or title
    published_at = _extract_published_at(html)
    source = _extract_source_name(html) or fallback_source
    return PreferredSourceHit(
        title=title[:120],
        summary=summary[:180],
        source=source[:64],
        source_url=detail_url,
        published_at=published_at,
        provider="preferred_source:list",
    )


def _extract_html_title(html: str) -> str:
    for pattern in (
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<title>(.*?)</title>',
        r'<h1[^>]*>(.*?)</h1>',
        r'<div[^>]+class=["\'][^"\']*\btitle\b[^"\']*["\'][^>]*>(.*?)</div>',
    ):
        match = re.search(pattern, html, flags=re.I | re.S)
        if match:
            value = _clean_text(match.group(1))
            if value:
                return value
    return ""


def _extract_meta_content(html: str, name: str) -> str:
    for pattern in (
        rf'<meta[^>]+name=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']{re.escape(name)}["\']',
        rf'<meta[^>]+property=["\']og:{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:{re.escape(name)}["\']',
    ):
        match = re.search(pattern, html, flags=re.I | re.S)
        if match:
            value = _clean_text(match.group(1))
            if value:
                return value
    return ""


def _extract_first_paragraphs(html: str) -> str:
    paragraphs = [
        _clean_text(item)
        for item in re.findall(r'<p[^>]*>(.*?)</p>', html, flags=re.I | re.S)
    ]
    paragraphs = [
        item
        for item in paragraphs
        if len(item) >= 18 and "版权所有" not in item and "上一篇" not in item and "下一篇" not in item
    ]
    return " ".join(paragraphs[:2]).strip()


def _extract_published_at(html: str) -> str | None:
    for pattern in DATE_PATTERNS:
        match = pattern.search(html)
        if not match:
            continue
        normalized = _normalize_datetime(match.group(1))
        if normalized:
            return normalized
    return None


def _extract_source_name(html: str) -> str:
    for pattern in (
        r'来源[：:]\s*(?:<span[^>]*>)?([^<\n]+)',
        r'class=["\'][^"\']*\bsource\b[^"\']*["\'][^>]*>\s*来源[：:]\s*(?:<span[^>]*>)?([^<\n]+)',
    ):
        match = re.search(pattern, html, flags=re.I | re.S)
        if match:
            value = _clean_text(match.group(1))
            if value:
                return value
    return ""


def _normalize_datetime(value: str | None) -> str | None:
    raw = _clean_text(value)
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).astimezone().replace(microsecond=0).isoformat()
    except Exception:
        pass
    normalized = raw.replace("/", "-").replace(".", "-").replace("年", "-").replace("月", "-").replace("日", "")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            from datetime import datetime

            return datetime.strptime(normalized, pattern).isoformat()
        except ValueError:
            continue
    return None


def _domain_label(url: str) -> str:
    domain = urlparse(url).netloc.lower().replace("www.", "")
    return domain or "优先网址"


def _clean_text(value: str | None) -> str:
    text = unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
