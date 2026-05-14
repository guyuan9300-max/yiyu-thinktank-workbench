from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import parse_qsl, quote_plus, urlencode, urljoin, urlparse

import httpx


SEARCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

DEFAULT_PUBLIC_SEARCH_PROVIDERS = ("so360_html", "sogou_html", "bing_html")
GENERIC_QUERY_TERMS = {
    "登记信息",
    "信息公开",
    "年报",
    "服务对象",
    "规模",
    "项目成效",
    "报告",
    "合作方",
    "执行方法",
    "公开报告",
    "filetype:pdf",
    "官网",
    "官方网站",
}


@dataclass(frozen=True)
class PublicSearchResult:
    title: str
    url: str
    snippet: str
    source: str
    provider: str


def search_public_web(
    query: str,
    *,
    max_results: int = 5,
    timeout_seconds: float = 8.0,
    providers: tuple[str, ...] | list[str] | None = None,
) -> list[PublicSearchResult]:
    cleaned_query = re.sub(r"\s+", " ", str(query or "")).strip()
    if not cleaned_query:
        return []

    selected_providers = tuple(providers or DEFAULT_PUBLIC_SEARCH_PROVIDERS)
    expanded_queries = _expand_queries(cleaned_query)
    ranking_terms = _ranking_terms(cleaned_query)
    results: list[PublicSearchResult] = []
    seen: set[str] = set()
    for current_query in expanded_queries:
        for provider in selected_providers:
            try:
                if provider == "so360_html":
                    provider_results = _fetch_so360_results(
                        current_query,
                        timeout_seconds=timeout_seconds,
                        ranking_terms=ranking_terms,
                    )
                elif provider == "sogou_html":
                    provider_results = _fetch_sogou_results(current_query, timeout_seconds=timeout_seconds)
                elif provider == "bing_html":
                    provider_results = _fetch_bing_results(current_query, timeout_seconds=timeout_seconds)
                else:
                    continue
            except Exception:
                continue
            for item in provider_results:
                normalized_url = _normalize_url_for_dedupe(item.url)
                if not normalized_url or normalized_url in seen:
                    continue
                seen.add(normalized_url)
                results.append(item)
    results.sort(key=lambda item: _result_rank(item, ranking_terms), reverse=True)
    return results[:max_results]


def _fetch_so360_results(query: str, *, timeout_seconds: float, ranking_terms: list[str]) -> list[PublicSearchResult]:
    url = f"https://www.so.com/s?q={quote_plus(query)}&src=srp"
    response = httpx.get(url, timeout=timeout_seconds, follow_redirects=True, headers=SEARCH_HEADERS)
    response.raise_for_status()
    return _parse_so360_results(
        response.text,
        timeout_seconds=min(timeout_seconds, 3.0),
        ranking_terms=ranking_terms,
    )


def _fetch_sogou_results(query: str, *, timeout_seconds: float) -> list[PublicSearchResult]:
    url = f"https://www.sogou.com/web?query={quote_plus(query)}"
    response = httpx.get(url, timeout=timeout_seconds, follow_redirects=True, headers=SEARCH_HEADERS)
    response.raise_for_status()
    return _parse_sogou_results(response.text, timeout_seconds=min(timeout_seconds, 4.0))


def _fetch_bing_results(query: str, *, timeout_seconds: float) -> list[PublicSearchResult]:
    url = f"https://www.bing.com/search?q={quote_plus(query)}&setlang=zh-CN&mkt=zh-CN"
    response = httpx.get(url, timeout=timeout_seconds, follow_redirects=True, headers=SEARCH_HEADERS)
    response.raise_for_status()
    return _parse_bing_results(response.text)


def _parse_so360_results(html_text: str, *, timeout_seconds: float, ranking_terms: list[str]) -> list[PublicSearchResult]:
    blocks = re.findall(
        r'<li[^>]+class=["\'][^"\']*\bres-list\b[^"\']*["\'][^>]*>.*?</li>',
        html_text or "",
        flags=re.I | re.S,
    )
    results: list[PublicSearchResult] = []
    for block in blocks[:8]:
        block_text = _clean_html_text(block, max_len=1200).lower()
        if ranking_terms and not any(term.lower() in block_text for term in ranking_terms):
            continue
        anchors = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', block, flags=re.I | re.S)
        chosen_href = ""
        chosen_title = ""
        for href, title_html in anchors:
            href = _clean_href(href)
            title = _clean_html_text(title_html, max_len=180)
            if not title or title.startswith("http"):
                continue
            if "so.com/link" in href or href.startswith("http://") or href.startswith("https://"):
                chosen_href = href
                chosen_title = title
                break
        if not chosen_href:
            continue
        resolved_url = _resolve_so360_url(chosen_href, timeout_seconds=timeout_seconds)
        if not resolved_url.startswith(("http://", "https://")):
            continue
        if _is_low_value_search_result(resolved_url, chosen_title, block):
            continue
        snippet = _clean_result_snippet(block, fallback=chosen_title)
        results.append(
            PublicSearchResult(
                title=chosen_title,
                url=resolved_url,
                snippet=snippet,
                source=_domain_label(resolved_url),
                provider="so360_html",
            )
        )
        if len(results) >= 8:
            break
    return results


def _parse_sogou_results(html_text: str, *, timeout_seconds: float) -> list[PublicSearchResult]:
    blocks = re.findall(
        r'<div[^>]+class=["\'][^"\']*\bvrwrap\b[^"\']*["\'][^>]*>.*?(?=<div[^>]+class=["\'][^"\']*\bvrwrap\b|</body>)',
        html_text or "",
        flags=re.I | re.S,
    )
    if not blocks:
        blocks = re.findall(
            r'<div[^>]+class=["\'][^"\']*\bresult\b[^"\']*["\'][^>]*>.*?(?=<div[^>]+class=["\'][^"\']*\bresult\b|</body>)',
            html_text or "",
            flags=re.I | re.S,
        )

    results: list[PublicSearchResult] = []
    for block in blocks[:12]:
        anchors = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', block, flags=re.I | re.S)
        chosen_href = ""
        chosen_title = ""
        for href, title_html in anchors:
            href = _clean_href(href)
            title = _clean_html_text(title_html, max_len=180)
            if not title or title.startswith("http") or "推荐您搜索" in title:
                continue
            if href.startswith("/link?url=") or href.startswith("http://") or href.startswith("https://"):
                chosen_href = href
                chosen_title = title
                break
        if not chosen_href:
            continue
        resolved_url = _resolve_sogou_url(chosen_href, timeout_seconds=timeout_seconds)
        if not resolved_url.startswith(("http://", "https://")):
            continue
        if _is_low_value_search_result(resolved_url, chosen_title, block):
            continue
        snippet = _clean_result_snippet(block, fallback=chosen_title)
        results.append(
            PublicSearchResult(
                title=chosen_title,
                url=resolved_url,
                snippet=snippet,
                source=_domain_label(resolved_url),
                provider="sogou_html",
            )
        )
        if len(results) >= 8:
            break
    return results


def _parse_bing_results(html_text: str) -> list[PublicSearchResult]:
    blocks = re.findall(
        r'<li[^>]+class=["\'][^"\']*\bb_algo\b[^"\']*["\'][^>]*>.*?</li>',
        html_text or "",
        flags=re.I | re.S,
    )
    results: list[PublicSearchResult] = []
    for block in blocks[:10]:
        match = re.search(r'<h2[^>]*>\s*<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', block, flags=re.I | re.S)
        if not match:
            match = re.search(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', block, flags=re.I | re.S)
        if not match:
            continue
        url = unescape(match.group(1) or "").strip()
        title = _clean_html_text(match.group(2), max_len=180)
        if not title or not url.startswith(("http://", "https://")):
            continue
        if _is_low_value_search_result(url, title, block):
            continue
        snippet_match = re.search(r'<p[^>]*>(.*?)</p>', block, flags=re.I | re.S)
        snippet = _clean_html_text(snippet_match.group(1) if snippet_match else title, max_len=500)
        results.append(
            PublicSearchResult(
                title=title,
                url=url,
                snippet=snippet,
                source=_domain_label(url),
                provider="bing_html",
            )
        )
    return results


def _resolve_so360_url(href: str, *, timeout_seconds: float) -> str:
    raw_url = _clean_href(href)
    if not raw_url:
        return ""
    absolute_url = urljoin("https://www.so.com/", raw_url)
    parsed = urlparse(absolute_url)
    if parsed.netloc.lower().endswith("so.com") and parsed.path.startswith("/link"):
        try:
            response = httpx.get(
                absolute_url,
                timeout=timeout_seconds,
                follow_redirects=False,
                headers={**SEARCH_HEADERS, "Referer": "https://www.so.com/"},
            )
            replacement = re.search(r'window\.location\.replace\(["\']([^"\']+)["\']', response.text or "", flags=re.I)
            if replacement:
                return _clean_href(replacement.group(1))
            refresh = re.search(r'url=([^"\'>\s]+)', response.text or "", flags=re.I)
            if refresh:
                return _clean_href(refresh.group(1))
        except Exception:
            return ""
        return ""
    return absolute_url


def _resolve_sogou_url(href: str, *, timeout_seconds: float) -> str:
    raw_url = _clean_href(href)
    if not raw_url:
        return ""
    absolute_url = urljoin("https://www.sogou.com/", raw_url)
    parsed = urlparse(absolute_url)
    if parsed.netloc.lower().endswith("sogou.com") and parsed.path.startswith("/link"):
        try:
            response = httpx.get(
                absolute_url,
                timeout=timeout_seconds,
                follow_redirects=False,
                headers={**SEARCH_HEADERS, "Referer": "https://www.sogou.com/"},
            )
            replacement = re.search(r'window\.location\.replace\(["\']([^"\']+)["\']', response.text or "", flags=re.I)
            if replacement:
                return _clean_href(replacement.group(1))
            refresh = re.search(r'url=([^"\'>\s]+)', response.text or "", flags=re.I)
            if refresh:
                return _clean_href(refresh.group(1))
        except Exception:
            return ""
        return ""
    return absolute_url


def _clean_result_snippet(block: str, *, fallback: str) -> str:
    text = _clean_html_text(block, max_len=1200)
    text = text.split("推荐您搜索", 1)[0]
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return fallback
    return text[:500].strip()


def _clean_html_text(value: object, *, max_len: int) -> str:
    text = unescape(str(value or ""))
    text = re.sub(r"<!--/?red_(?:beg|end)-->", "", text, flags=re.I)
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len].strip()


def _expand_queries(query: str) -> list[str]:
    queries = [query]
    parts = [part.strip() for part in re.split(r"\s+", query) if part.strip()]
    candidate_terms = [part for part in parts if part not in GENERIC_QUERY_TERMS and not part.startswith("site:")]
    if candidate_terms:
        primary = candidate_terms[0]
        if primary not in queries:
            queries.append(primary)
    return queries[:2]


def _ranking_terms(query: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"\s+", query) if part.strip()]
    terms = [part for part in parts if part not in GENERIC_QUERY_TERMS and not part.startswith("site:")]
    return terms[:4]


def _result_rank(item: PublicSearchResult, terms: list[str]) -> int:
    text = f"{item.title} {item.snippet} {item.source} {item.url}".lower()
    score = 0
    for term in terms:
        normalized = term.lower()
        if normalized and normalized in text:
            score += 20 + min(len(normalized), 10)
    if item.provider == "so360_html":
        score += 4
    if item.source.endswith((".org.cn", ".org", ".cn", ".gov.cn")):
        score += 3
    return score


def _is_low_value_search_result(url: str, title: str, raw_block: str = "") -> bool:
    parsed = urlparse(url or "")
    domain = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.lower()
    query = parsed.query.lower()
    text = f"{title} {url} {raw_block}".lower()
    if not domain:
        return True
    if any(token in text for token in ("用户登录", "验证码", "账号登录", "立即登录")) and any(token in text for token in ("登录", "注册", "验证码", "账号")):
        return True
    if domain in {"image.so.com", "m.image.so.com"} or domain.endswith(".image.so.com"):
        return True
    if domain in {"map.360.cn", "map.so.com", "ditu.so.com", "map.baidu.com"}:
        return True
    if domain in {"so.com", "www.so.com", "m.so.com", "sogou.com", "www.sogou.com"} and any(
        token in path for token in ("/i", "/image", "/pic", "/video", "/news")
    ):
        return True
    if any(token in path for token in ("/search", "/s", "/web", "/link")) and domain.endswith(("so.com", "sogou.com", "bing.com", "baidu.com")):
        return True
    if any(token in query for token in ("q=", "query=", "wd=")) and domain.endswith(("image.so.com", "map.360.cn", "map.so.com", "sogou.com", "bing.com", "baidu.com")):
        return True
    if any(token in text for token in ("_360图片", "360图片", "图片搜索", "image result", "查看全部图片")):
        return True
    if any(token in path for token in ("/image", "/images", "/pic", "/photo", "/video")) and domain.endswith(("so.com", "sogou.com", "bing.com")):
        return True
    return False


def _clean_href(value: object) -> str:
    return str(value or "").replace("&amp;", "&").strip()


def _domain_label(url: str) -> str:
    domain = urlparse(url).netloc.lower().removeprefix("www.")
    return domain or "public_web"


def _normalize_url_for_dedupe(url: str) -> str:
    parsed = urlparse(url or "")
    if not parsed.netloc:
        return ""
    dropped = {"spm", "from", "source", "fbclid", "gclid", "yclid", "bd_vid", "sa", "ved", "usg"}
    params = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in dropped
    ]
    return parsed._replace(fragment="", query=urlencode(params, doseq=True)).geturl().rstrip("/")
