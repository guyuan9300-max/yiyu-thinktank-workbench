from __future__ import annotations

import re
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import quote, urlparse
from xml.etree import ElementTree as ET

import httpx

from app.services.ai import AiService
from app.services.topic_source_fetcher import fetch_preferred_source_hits


SEARCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

GOOGLE_NEWS_TEMPLATE = "https://news.google.com/rss/search?q={query}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
BING_NEWS_TEMPLATE = "https://www.bing.com/news/search?q={query}&format=RSS&setlang=zh-cn"
BING_WEB_TEMPLATE = "https://www.bing.com/search?q={query}&format=rss&setlang=zh-cn"
BING_WEB_HTML_TEMPLATE = "https://cn.bing.com/search?q={query}&setlang=zh-cn&cc=CN"
JINA_READER_TEMPLATE = "https://r.jina.ai/http://{target}"

STOP_PHRASES = (
    "关注",
    "跟踪",
    "追踪",
    "请",
    "帮我",
    "想看",
    "如何",
    "怎么",
    "以及",
    "有关",
    "相关",
    "最新",
    "趋势",
    "打法",
    "案例",
    "信息",
    "新闻",
)

TOKEN_STOPWORDS = {
    "重点",
    "优先",
    "留意",
    "动态",
    "最新动态",
    "项目",
    "方法总结",
    "争议讨论",
    "行业信号",
    "发布时间",
    "适用场景",
    "关键数据",
    "执行门槛",
    "涉及机构",
    "可复用做法",
    "最新",
    "案例",
    "信息",
    "现在",
    "然后",
    "就是",
    "这个",
    "这些",
    "那个",
    "有关",
    "相关",
    "里面",
    "上面",
    "希望",
    "了解",
    "找到",
    "内容",
    "很好",
    "非常好",
    "最好",
    "经验",
    "分享",
    "讲得很清楚",
    "都讲得很清楚",
    "priority",
}

TOKEN_SUBSTRING_STOPWORDS = (
    "我想",
    "希望",
    "找到",
    "使用",
    "表达",
    "内容",
    "动态",
    "优先留意",
    "优先使用",
    "讲清楚",
)

QUERY_TIME_PATTERNS = (
    r"近\s*\d+\s*天",
    r"近\s*\d+\s*周",
    r"近\s*\d+\s*月",
    r"最近\s*\d+\s*天",
    r"最近\s*\d+\s*周",
    r"最近\s*\d+\s*月",
    r"最近[一二三四五六七八九十两]+天",
    r"最近[一二三四五六七八九十两]+周",
    r"最近[一二三四五六七八九十两]+月",
)

TECH_RADAR_PATTERNS = (
    r"\bcodex\b",
    r"code\s*x",
    r"github",
    r"开源",
    r"开发",
    r"开发者",
    r"coding agent",
    r"computer use agent",
    r"developer tool",
    r"copilot",
    r"智能体",
)


@dataclass
class TopicSearchHit:
    title: str
    summary: str
    source: str
    source_url: str
    published_at: str | None
    provider: str
    query: str
    direction: str = ""


def fetch_topic_candidates_from_web(
    ai: AiService,
    *,
    radar_title: str,
    radar_prompt: str,
    time_range: str,
    preferred_source_urls: list[str] | None = None,
    search_intents: list[dict[str, object]] | None = None,
    max_items: int = 5,
    search_fallback_enabled: bool = True,
    ai_query_suggestions_enabled: bool = True,
) -> list[TopicSearchHit]:
    intent_queries: list[str] = []
    intent_direction_by_query: dict[str, str] = {}
    for intent in search_intents or []:
        query_text = str(intent.get("query") or "").strip()
        if not query_text:
            continue
        direction = str(intent.get("direction") or "").strip()
        intent_queries.append(query_text)
        if direction:
            intent_direction_by_query[_normalize_query_key(query_text)] = direction
    queries = _candidate_queries(
        title=radar_title,
        prompt=radar_prompt,
        queries=[
            *intent_queries,
            *_extract_prompt_queries(radar_prompt),
            *_expand_topic_queries(radar_title, radar_prompt),
        ],
    )
    relevance_tokens = _keyword_tokens(f"{radar_title} {radar_prompt}")
    raw_hit_limit = max(18, max_items * 6)
    shortlist_limit = max(10, max_items * 3)

    hits: list[TopicSearchHit] = []
    seen_keys: set[str] = set()

    for preferred_hit in fetch_preferred_source_hits(preferred_source_urls, max_items=max(10, max_items * 4)):
        dedupe_key = preferred_hit.source_url.strip().lower() or re.sub(r"\s+", "", preferred_hit.title).lower()
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        hits.append(
            TopicSearchHit(
                title=preferred_hit.title,
                summary=preferred_hit.summary,
                source=preferred_hit.source,
                source_url=preferred_hit.source_url,
                published_at=preferred_hit.published_at,
                provider=preferred_hit.provider,
                query=f"preferred:{preferred_hit.source}",
                direction="",
            )
        )

    if not search_fallback_enabled:
        hits = _filter_hits_by_time_range(hits, time_range)
        if relevance_tokens:
            filtered_hits = [hit for hit in hits if _score_hit(hit, relevance_tokens) > 0]
            if filtered_hits:
                hits = filtered_hits
        ranked = _fallback_rank_hits(radar_title, radar_prompt, hits, max_items=shortlist_limit) or hits[:shortlist_limit]
        return ranked

    if ai_query_suggestions_enabled:
        try:
            query_suggestions = ai.suggest_topic_search_queries(
                title=radar_title,
                prompt=radar_prompt,
                time_range=time_range,
            )
        except Exception:
            query_suggestions = []
        if query_suggestions:
            queries = _candidate_queries(
                title=radar_title,
                prompt=radar_prompt,
                queries=[
                    *query_suggestions,
                    *queries,
                ],
            )

    with httpx.Client(timeout=httpx.Timeout(8.0, connect=4.0), headers=SEARCH_HEADERS, follow_redirects=True) as client:
        if len(hits) < raw_hit_limit:
            for query in queries:
                for provider, url, effective_query in _build_search_urls(query=query, time_range=time_range, preferred_source_urls=preferred_source_urls):
                    try:
                        response = client.get(url)
                        response.raise_for_status()
                    except Exception:
                        continue
                    parsed_hits = (
                        _parse_bing_html_hits(response.text, provider=provider, query=effective_query)
                        if provider == "bing_web_html"
                        else _parse_rss_hits(response.text, provider=provider, query=effective_query)
                    )
                    for hit in parsed_hits:
                        direction = intent_direction_by_query.get(_normalize_query_key(effective_query), "")
                        if direction:
                            hit = _with_topic_hit_direction(hit, direction)
                        dedupe_key = _dedupe_key(hit)
                        if dedupe_key in seen_keys:
                            continue
                        seen_keys.add(dedupe_key)
                        hits.append(hit)
                    if len(hits) >= raw_hit_limit:
                        break
                if len(hits) >= raw_hit_limit:
                    break

        hits = _filter_hits_by_time_range(hits, time_range)
        if not hits:
            for fallback_query in queries:
                try:
                    response = client.get(BING_WEB_TEMPLATE.format(query=quote(fallback_query)))
                    response.raise_for_status()
                    for hit in _parse_rss_hits(response.text, provider="bing_web", query=fallback_query):
                        direction = intent_direction_by_query.get(_normalize_query_key(fallback_query), "")
                        if direction:
                            hit = _with_topic_hit_direction(hit, direction)
                        dedupe_key = _dedupe_key(hit)
                        if dedupe_key in seen_keys:
                            continue
                        seen_keys.add(dedupe_key)
                        hits.append(hit)
                        if len(hits) >= raw_hit_limit:
                            break
                except Exception:
                    continue
                if len(hits) >= raw_hit_limit:
                    break

    hits = _filter_hits_by_time_range(hits, time_range)
    if not hits:
        return []

    if relevance_tokens:
        filtered_hits = [hit for hit in hits if _score_hit(hit, relevance_tokens) > 0]
        if filtered_hits:
            hits = filtered_hits
    if not hits:
        return []

    try:
        shortlisted = ai.shortlist_topic_search_hits(
            title=radar_title,
            prompt=radar_prompt,
            hits=[
                {
                    "title": hit.title,
                    "summary": hit.summary,
                    "source": hit.source,
                    "url": hit.source_url,
                    "publishedAt": hit.published_at or "",
                    "provider": hit.provider,
                    "query": hit.query,
                }
                for hit in hits
            ],
            max_items=shortlist_limit,
        )
    except Exception:
        shortlisted = []

    selected: list[TopicSearchHit] = []
    selected_keys: set[str] = set()

    for item in shortlisted:
        index_raw = item.get("index")
        if isinstance(index_raw, str) and index_raw.isdigit():
            index = int(index_raw)
        elif isinstance(index_raw, int):
            index = index_raw
        else:
            continue

        if index >= 1:
            index -= 1
        if index < 0 or index >= len(hits):
            continue

        hit = hits[index]
        dedupe_key = _dedupe_key(hit)
        if dedupe_key in selected_keys:
            continue
        selected_keys.add(dedupe_key)

        refined_title = str(item.get("title") or "").strip()
        refined_summary = str(item.get("summary") or "").strip()
        if refined_title or refined_summary:
            hit = TopicSearchHit(
                title=(refined_title or hit.title)[:120],
                summary=(refined_summary or hit.summary)[:180],
                source=hit.source,
                source_url=hit.source_url,
                published_at=hit.published_at,
                provider=hit.provider,
                query=hit.query,
                direction=hit.direction,
            )
        selected.append(hit)

    if selected:
        return _ensure_hits_in_chinese(ai, selected[:shortlist_limit], radar_title=radar_title, radar_prompt=radar_prompt)

    fallback_hits = _fallback_rank_hits(radar_title, radar_prompt, hits, max_items=shortlist_limit)
    return _ensure_hits_in_chinese(
        ai,
        fallback_hits or hits[:shortlist_limit],
        radar_title=radar_title,
        radar_prompt=radar_prompt,
    )


def fetch_topic_source_excerpt(source_url: str, *, max_chars: int = 4200) -> str:
    if not source_url:
        return ""
    direct_text = _fetch_source_text(source_url)
    cleaned = _clean_source_text(direct_text)
    if len(cleaned) >= 240:
        return cleaned[:max_chars]

    reader_text = _fetch_reader_text(source_url)
    reader_cleaned = _clean_reader_text(reader_text)
    if len(reader_cleaned) >= 120:
        return reader_cleaned[:max_chars]

    merged = " ".join(part for part in [cleaned, reader_cleaned] if part).strip()
    return merged[:max_chars]


def _fetch_source_text(source_url: str) -> str:
    try:
        with httpx.Client(timeout=httpx.Timeout(8.0, connect=4.0), headers=SEARCH_HEADERS, follow_redirects=True) as client:
            response = client.get(source_url)
            response.raise_for_status()
            return response.text
    except Exception:
        return ""


def _fetch_reader_text(source_url: str) -> str:
    target = source_url.strip()
    if not target:
        return ""
    try:
        with httpx.Client(timeout=httpx.Timeout(16.0, connect=6.0), headers=SEARCH_HEADERS, follow_redirects=True) as client:
            response = client.get(JINA_READER_TEMPLATE.format(target=target))
            response.raise_for_status()
            if response.text.lstrip().startswith("{\"data\":null,\"code\":451"):
                return ""
            return response.text
    except Exception:
        return ""


def _clean_source_text(value: str) -> str:
    text = value or ""
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    return _clean_text(text)


def _clean_reader_text(value: str) -> str:
    text = value or ""
    text = re.sub(r"(?im)^Title:.*$", " ", text)
    text = re.sub(r"(?im)^URL Source:.*$", " ", text)
    text = re.sub(r"(?im)^Markdown Content:?", " ", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
    text = re.sub(r"[#>*`_~-]+", " ", text)
    return _clean_text(text)


def _preferred_source_domains(preferred_source_urls: list[str] | None) -> list[str]:
    seen: set[str] = set()
    domains: list[str] = []
    for item in preferred_source_urls or []:
        parsed = urlparse(item.strip())
        domain = parsed.netloc.lower().replace("www.", "")
        if not domain or domain in seen:
            continue
        seen.add(domain)
        domains.append(domain)
    return domains


def _domain_label(url: str) -> str:
    parsed = urlparse((url or "").strip())
    domain = parsed.netloc.lower().replace("www.", "")
    return domain or "公开网页"


def _build_search_urls(*, query: str, time_range: str, preferred_source_urls: list[str] | None = None) -> list[tuple[str, str, str]]:
    window = _time_window_token(time_range)
    scoped_query = f"{query} when:{window}" if window else query
    urls: list[tuple[str, str, str]] = []
    news_rss_fallback_enabled = str(os.getenv("YIYU_TOPIC_NEWS_RSS_FALLBACK", "")).strip().lower() in {"1", "true", "yes", "on"}
    for domain in _preferred_source_domains(preferred_source_urls)[:4]:
        site_query = f"site:{domain} {query}"
        scoped_site_query = f"{site_query} when:{window}" if window else site_query
        urls.append((f"bing_web_html:{domain}", BING_WEB_HTML_TEMPLATE.format(query=quote(site_query)), site_query))
        urls.append((f"bing_web:{domain}", BING_WEB_TEMPLATE.format(query=quote(site_query)), site_query))
        if news_rss_fallback_enabled:
            urls.append((f"google_news:{domain}", GOOGLE_NEWS_TEMPLATE.format(query=quote(scoped_site_query)), site_query))
            urls.append((f"bing_news:{domain}", BING_NEWS_TEMPLATE.format(query=quote(site_query)), site_query))
    urls.append(("bing_web_html", BING_WEB_HTML_TEMPLATE.format(query=quote(query)), query))
    urls.append(("bing_web", BING_WEB_TEMPLATE.format(query=quote(query)), query))
    if news_rss_fallback_enabled:
        urls.append(("google_news", GOOGLE_NEWS_TEMPLATE.format(query=quote(scoped_query)), query))
        urls.append(("bing_news", BING_NEWS_TEMPLATE.format(query=quote(query)), query))
    return urls


def _time_window_token(time_range: str) -> str:
    mapping = {
        "1_day": "1d",
        "3_days": "3d",
        "7_days": "7d",
        "30_days": "30d",
    }
    return mapping.get(time_range, "7d")


def _parse_rss_hits(xml_text: str, *, provider: str, query: str) -> list[TopicSearchHit]:
    hits: list[TopicSearchHit] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return hits

    channel = root.find("channel")
    items = channel.findall("item") if channel is not None else []
    for item in items[:12]:
        title_text = _find_child_text(item, "title")
        link = _find_child_text(item, "link")
        description = _clean_text(_find_child_text(item, "description"))
        source = _extract_source(item, title_text)
        published_at = _parse_pub_date(_find_child_text(item, "pubDate"))

        title = _clean_title(title_text, source=source)
        if not title or not link:
            continue
        if not description:
            description = title

        hits.append(
            TopicSearchHit(
                title=title[:120],
                summary=description[:180],
                source=source or provider,
                source_url=link,
                published_at=published_at,
                provider=provider,
                query=query,
                direction="",
            )
        )
    return hits


def _parse_bing_html_hits(html_text: str, *, provider: str, query: str) -> list[TopicSearchHit]:
    hits: list[TopicSearchHit] = []
    text = html_text or ""
    blocks = re.findall(r'<li[^>]+class=["\'][^"\']*\bb_algo\b[^"\']*["\'][^>]*>(.*?)</li>', text, flags=re.I | re.S)
    if not blocks:
        blocks = re.findall(r'<h2[^>]*>\s*<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>\s*</h2>(.*?)(?=<h2|</ol>|</body>)', text, flags=re.I | re.S)
        normalized_blocks = []
        for url, title_html, tail in blocks[:12]:
            normalized_blocks.append(f'<a href="{url}">{title_html}</a>{tail}')
        blocks = normalized_blocks

    for block in blocks[:12]:
        link_match = re.search(r'<h2[^>]*>\s*<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', block, flags=re.I | re.S)
        if not link_match:
            link_match = re.search(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', block, flags=re.I | re.S)
        if not link_match:
            continue
        link = unescape(link_match.group(1)).strip()
        title = _clean_text(link_match.group(2))
        if not title or not link.startswith(("http://", "https://")):
            continue
        snippet = ""
        snippet_match = re.search(r'<p[^>]*>(.*?)</p>', block, flags=re.I | re.S)
        if snippet_match:
            snippet = _clean_text(snippet_match.group(1))
        if not snippet:
            snippet = title
        source = _domain_label(link) or "公开网页"
        published_at = _extract_search_result_date(block)
        hits.append(
            TopicSearchHit(
                title=title[:120],
                summary=snippet[:180],
                source=source[:80],
                source_url=link,
                published_at=published_at,
                provider=provider,
                query=query,
                direction="",
            )
        )
    return hits


def _extract_search_result_date(block: str) -> str | None:
    cleaned = _clean_text(block)
    for pattern in (
        r"([12]\d{3})[年/-](\d{1,2})[月/-](\d{1,2})日?",
        r"([12]\d{3})\.(\d{1,2})\.(\d{1,2})",
    ):
        match = re.search(pattern, cleaned)
        if not match:
            continue
        year, month, day = match.groups()
        try:
            return datetime(int(year), int(month), int(day)).astimezone().replace(microsecond=0).isoformat()
        except Exception:
            continue
    return None


def _find_child_text(item: ET.Element, tag: str) -> str:
    child = item.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    for sub in item:
        if sub.tag.endswith(tag) and sub.text:
            return sub.text.strip()
    return ""


def _extract_source(item: ET.Element, title: str) -> str:
    source = _find_child_text(item, "source")
    if source:
        return _clean_text(source)
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    return ""


def _clean_title(title: str, *, source: str) -> str:
    cleaned = _clean_text(title)
    if source and cleaned.endswith(f" - {source}"):
        cleaned = cleaned[: -(len(source) + 3)].strip()
    return cleaned


def _clean_text(value: str) -> str:
    text = unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_pub_date(value: str) -> str | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.isoformat()
    return parsed.astimezone().replace(microsecond=0).isoformat()


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.astimezone()
    return parsed.astimezone()


def _time_window_days(time_range: str) -> int:
    mapping = {
        "1_day": 1,
        "3_days": 3,
        "7_days": 7,
        "30_days": 30,
    }
    return mapping.get(time_range, 7)


def _filter_hits_by_time_range(hits: list[TopicSearchHit], time_range: str) -> list[TopicSearchHit]:
    if not hits:
        return []
    cutoff = datetime.now().astimezone() - timedelta(days=_time_window_days(time_range))
    recent_hits: list[TopicSearchHit] = []
    undated_hits: list[TopicSearchHit] = []
    for hit in hits:
        if str(hit.provider or "").startswith("preferred_source") or hit.provider in {"rsshub", "easyspider", "trendradar"}:
            recent_hits.append(hit)
            continue
        published_at = _parse_iso_datetime(hit.published_at)
        if published_at is None:
            undated_hits.append(hit)
            continue
        if published_at >= cutoff:
            recent_hits.append(hit)
    if recent_hits:
        return recent_hits + undated_hits
    return undated_hits


def _dedupe_key(hit: TopicSearchHit) -> str:
    title = re.sub(r"\s+", "", hit.title).lower()
    url = hit.source_url.strip().lower()
    return url or f"{title}|{hit.source.lower()}"


def _fallback_query(title: str, prompt: str) -> str:
    merged = f"{title} {prompt}".strip()
    for phrase in STOP_PHRASES:
        merged = merged.replace(phrase, " ")
    merged = re.sub(r"[，。；：、,.!?！？\"“”‘’()（）]+", " ", merged)
    merged = re.sub(r"\s+", " ", merged).strip()
    return merged[:64] or title or prompt[:32] or "行业资讯"


def _normalize_search_query(query: str) -> str:
    cleaned = query.strip()
    for pattern in QUERY_TIME_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned)
    cleaned = re.sub(r"[，。；：、,.!?！？]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _candidate_queries(*, title: str, prompt: str, queries: list[str]) -> list[str]:
    options: list[str] = []
    seen: set[str] = set()

    for raw_query in [*queries, _fallback_query(title, prompt), title]:
        normalized = _normalize_search_query(raw_query)
        if len(normalized) < 2:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        options.append(normalized)
    return options[:8]


def _extract_prompt_queries(prompt: str) -> list[str]:
    quoted = re.findall(r"[“\"]([^”\"]{2,60})[”\"]", prompt or "")
    options: list[str] = []
    seen: set[str] = set()
    for item in quoted:
        normalized = _normalize_search_query(item)
        if len(normalized) < 2:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        options.append(normalized)
    return options[:4]


def _expand_topic_queries(title: str, prompt: str) -> list[str]:
    combined = f"{title} {prompt}"
    if _looks_like_technical_radar(combined):
        return _expand_technical_queries(title, prompt)
    return []


def _looks_like_technical_radar(text: str) -> bool:
    lowered = (text or "").lower()
    return any(re.search(pattern, lowered, re.I) for pattern in TECH_RADAR_PATTERNS)


def _expand_technical_queries(title: str, prompt: str) -> list[str]:
    text = f"{title} {prompt}"
    lowered = text.lower()
    aliases: list[str] = []
    seen: set[str] = set()

    def add_alias(value: str) -> None:
        candidate = value.strip()
        if not candidate:
            return
        key = candidate.lower()
        if key in seen:
            return
        seen.add(key)
        aliases.append(candidate)

    normalized_title = title.strip()
    if normalized_title:
        add_alias(normalized_title)

    if re.search(r"\bcodex\b|code\s*x", lowered, re.I):
        add_alias("Codex")
        add_alias("CodeX")
        add_alias("OpenAI Codex")
    if "github" in lowered or "开源" in text:
        add_alias("GitHub")
        add_alias("GitHub Trending")
    if re.search(r"coding agent|computer use agent|智能体", lowered, re.I):
        add_alias("AI coding agent")
        add_alias("Computer Use Agent")
    if re.search(r"developer tool|开发者工具|开发工具", text, re.I):
        add_alias("developer tool")

    if not aliases:
        add_alias(normalized_title or "AI 开发工具")

    themes: list[str] = [
        "开源项目",
        "落地案例",
        "实战经验",
        "开发工作流",
    ]
    if re.search(r"半成型|产品|商业化|落地", text, re.I):
        themes.extend(["产品化", "商业化信号"])
    if re.search(r"开发板|开发版", text, re.I):
        themes.extend(["开发板", "开发版"])

    expanded: list[str] = []
    expanded_seen: set[str] = set()

    def add_query(value: str) -> None:
        normalized = _normalize_search_query(value)
        if len(normalized) < 2:
            return
        key = normalized.lower()
        if key in expanded_seen:
            return
        expanded_seen.add(key)
        expanded.append(normalized)

    alias_cycle = aliases[1:] + aliases[:1] if len(aliases) > 1 else aliases
    primary_alias = alias_cycle[0]

    if any(alias.lower() in {"github", "github trending"} for alias in aliases):
        add_query("GitHub 高星开源项目 功能介绍")
        add_query("GitHub Trending 新项目 价值分析")
    if re.search(r"\bcodex\b|code\s*x", lowered, re.I):
        add_query("OpenAI Codex 落地案例")
        add_query("Codex 开源项目 实战经验")
        add_query("AI coding agent 开发工作流")
    add_query(f"{primary_alias} 开源项目 落地案例")
    add_query(f"{primary_alias} 实战经验 开发工作流")

    for alias in alias_cycle[:4]:
        for theme in themes[:4]:
            add_query(f"{alias} {theme}")

    return expanded[:6]


def _fallback_rank_hits(title: str, prompt: str, hits: list[TopicSearchHit], *, max_items: int) -> list[TopicSearchHit]:
    tokens = _keyword_tokens(f"{title} {prompt}")
    scored: list[tuple[int, TopicSearchHit]] = []
    for hit in hits:
        score = _score_hit(hit, tokens)
        if score > 0:
            scored.append((score, hit))
    if scored:
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:max_items]]
    return []


def _ensure_hits_in_chinese(
    ai: AiService,
    hits: list[TopicSearchHit],
    *,
    radar_title: str,
    radar_prompt: str,
) -> list[TopicSearchHit]:
    normalized: list[TopicSearchHit] = []
    for hit in hits:
        try:
            localized = ai.localize_topic_hit(
                title=hit.title,
                summary=hit.summary,
                radar_title=radar_title,
                radar_prompt=radar_prompt,
            )
        except Exception:
            localized = {"title": hit.title, "summary": hit.summary}
        normalized.append(
            TopicSearchHit(
                title=str(localized.get("title") or hit.title)[:120],
                summary=str(localized.get("summary") or hit.summary)[:180],
                source=hit.source,
                source_url=hit.source_url,
                published_at=hit.published_at,
                provider=hit.provider,
                query=hit.query,
                direction=hit.direction,
            )
        )
    return normalized


def _normalize_query_key(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _with_topic_hit_direction(hit: TopicSearchHit, direction: str) -> TopicSearchHit:
    return TopicSearchHit(
        title=hit.title,
        summary=hit.summary,
        source=hit.source,
        source_url=hit.source_url,
        published_at=hit.published_at,
        provider=hit.provider,
        query=hit.query,
        direction=direction,
    )


def _keyword_tokens(text: str) -> list[str]:
    merged = text.strip().replace("*", " ")
    for phrase in STOP_PHRASES:
        merged = merged.replace(phrase, " ")
    merged = re.sub(r"[，。；：、,.!?！？\"“”‘’()（）/\\|:+\-]+", " ", merged)
    merged = re.sub(r"\s+", " ", merged).strip()
    if not merged:
        return []

    tokens: list[str] = []
    seen: set[str] = set()

    def add_token(candidate: str) -> None:
        token = candidate.strip()
        if len(token) < 2:
            return
        lowered = token.lower()
        if lowered in seen:
            return
        if lowered in TOKEN_STOPWORDS:
            return
        if any(part in token for part in TOKEN_SUBSTRING_STOPWORDS):
            return
        if token.isdigit():
            return
        if re.fullmatch(r"[A-Za-z]{1,2}", token):
            return
        if re.fullmatch(r"[\u4e00-\u9fff]{9,}", token):
            return
        seen.add(lowered)
        tokens.append(token)

    for chunk in merged.split(" "):
        cleaned = chunk.strip()
        if not cleaned:
            continue
        if re.search(r"[A-Za-z]", cleaned):
            for part in re.findall(r"[A-Za-z][A-Za-z0-9._+-]{1,20}", cleaned):
                add_token(part)
        if re.search(r"[\u4e00-\u9fff]", cleaned):
            for part in re.split(r"(?:与|和|及|以及|或|并|跟|有关|相关|正在|如何|哪些|什么|不是|然后|最好|可以|希望|明确|直接|就是|其中|当前|主要|例如|这些|那个|这个|以及)", cleaned):
                token = part.strip()
                if not token:
                    continue
                if 2 <= len(token) <= 8:
                    add_token(token)
    return tokens[:16]


def _score_hit(hit: TopicSearchHit, tokens: list[str]) -> int:
    haystack = f"{hit.title} {hit.summary} {hit.source}".lower()
    score = 0
    for token in tokens:
        needle = token.lower()
        if needle and needle in haystack:
            score += max(1, len(token))
    return score
