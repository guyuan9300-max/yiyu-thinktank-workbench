"""社交平台公开搜索 — 微博/小红书/抖音 兜底抓取。

定位：
  - 三大搜索引擎（360/Sogou/Bing）对 UGC 平台索引覆盖差，本模块直接打 s.weibo.com 等公开搜索页。
  - 未登录情形下平台多有跳转 / 风控，抓不到时**静默返回空列表**，不阻塞主流程。
  - 输出复用 public_search.PublicSearchResult，下游词表情感分析可直接吃。

策略（用户要求三家都抓·微博优先）：
  - 微博：s.weibo.com 公开搜索页，可解析卡片。
  - 小红书：sojump 反爬严，公开 hashtag 页需 JS 渲染。当前返回 []，留 stub 等后续接 Playwright。
  - 抖音：登录墙，公开搜索几乎不可用。当前返回 []。
"""
from __future__ import annotations

import re
from html import unescape
from urllib.parse import quote_plus

import httpx

from app.services.public_search import PublicSearchResult, SEARCH_HEADERS


WEIBO_SEARCH_URL = "https://s.weibo.com/weibo"
WEIBO_LOGIN_REDIRECT_HINT = "passport.weibo.com"


def search_weibo(
    query: str,
    *,
    max_results: int = 5,
    timeout_seconds: float = 8.0,
) -> list[PublicSearchResult]:
    """微博公开搜索。未登录时若被跳登录页则返回 []。

    解析 s.weibo.com 的实时卡片：每条卡片含 .card-wrap > .card > .card-feed。
    取卡片内的正文文本 + 作者昵称 + 时间 + 详情链接。
    """
    query = (query or "").strip()
    if not query:
        return []
    url = f"{WEIBO_SEARCH_URL}?q={quote_plus(query)}&Refer=weibo_weibo"
    try:
        resp = httpx.get(
            url,
            timeout=timeout_seconds,
            follow_redirects=False,
            headers={
                **SEARCH_HEADERS,
                "Referer": "https://weibo.com/",
            },
        )
    except Exception:  # noqa: BLE001
        return []
    # 风控/未登录跳转 → 直接放弃
    if resp.status_code in (301, 302, 303, 307, 308):
        return []
    if WEIBO_LOGIN_REDIRECT_HINT in (resp.headers.get("location") or ""):
        return []
    if resp.status_code != 200 or not resp.text:
        return []
    return _parse_weibo_cards(resp.text, query=query, max_results=max_results)


def search_xiaohongshu(
    query: str,
    *,
    max_results: int = 5,
    timeout_seconds: float = 8.0,
) -> list[PublicSearchResult]:
    """小红书公开搜索 stub。

    当前实现：返回 []。
    原因：小红书 web 端搜索接口需要 sign 头 + JS 渲染笔记卡片，纯 httpx 抓不到内容。
    后续接 Playwright 或拿到合法 API key 后再实现。
    """
    return []


def search_douyin(
    query: str,
    *,
    max_results: int = 5,
    timeout_seconds: float = 8.0,
) -> list[PublicSearchResult]:
    """抖音公开搜索 stub — 同 search_xiaohongshu，需破 X-Bogus 签名，当前不实现。"""
    return []


# ──────────────────────────────────────────────────────────────────────────
# 微博 HTML 解析
# ──────────────────────────────────────────────────────────────────────────


def _parse_weibo_cards(html_text: str, *, query: str, max_results: int) -> list[PublicSearchResult]:
    cards = re.findall(
        r'<div[^>]+class=["\'][^"\']*\bcard-wrap\b[^"\']*["\'][^>]*>.*?(?=<div[^>]+class=["\'][^"\']*\bcard-wrap\b|<div[^>]+class=["\'][^"\']*\bm-page\b|</body>)',
        html_text or "",
        flags=re.I | re.S,
    )
    results: list[PublicSearchResult] = []
    for block in cards[: max_results * 3]:
        if "card-feed" not in block:
            continue  # 跳过广告卡 / 用户卡
        content_text = _extract_weibo_text(block)
        if not content_text or len(content_text) < 8:
            continue
        url = _extract_weibo_url(block)
        if not url:
            continue
        author = _extract_weibo_author(block)
        title = f"微博 · {author}" if author else "微博"
        results.append(
            PublicSearchResult(
                title=title,
                url=url,
                snippet=content_text[:500],
                source="weibo.com",
                provider="weibo_html",
            )
        )
        if len(results) >= max_results:
            break
    return results


def _extract_weibo_text(block: str) -> str:
    """取 .content > p[node-type='feed_list_content'] 的文本。"""
    m = re.search(
        r'<p[^>]+(?:node-type|nick-name)=["\'][^"\']*feed_list_content[^"\']*["\'][^>]*>(.*?)</p>',
        block,
        flags=re.I | re.S,
    )
    raw = m.group(1) if m else ""
    if not raw:
        # 兜底：取 .txt 区块
        m2 = re.search(
            r'<p[^>]+class=["\'][^"\']*\btxt\b[^"\']*["\'][^>]*>(.*?)</p>',
            block,
            flags=re.I | re.S,
        )
        raw = m2.group(1) if m2 else ""
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_weibo_url(block: str) -> str:
    """微博详情页 URL：通常 a[href='/{uid}/{mid}'] 或 a[href='//weibo.com/...']。"""
    matches = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>', block, flags=re.I)
    for href in matches:
        href = (href or "").strip()
        if not href:
            continue
        if href.startswith("//"):
            href = "https:" + href
        elif href.startswith("/") and not href.startswith("//"):
            href = "https://weibo.com" + href
        if not href.startswith(("http://", "https://")):
            continue
        if "weibo.com" not in href and "weibo.cn" not in href:
            continue
        # 跳过头像 / 标签 / 用户主页（含 /u/）
        if any(seg in href for seg in ("/u/", "/p/", "javascript:", "#")):
            continue
        return href
    return ""


def _extract_weibo_author(block: str) -> str:
    m = re.search(
        r'<a[^>]+nick-name=["\']([^"\']+)["\']',
        block,
        flags=re.I,
    )
    if m:
        return unescape(m.group(1)).strip()
    m2 = re.search(
        r'<a[^>]+class=["\'][^"\']*\bname\b[^"\']*["\'][^>]*>(.*?)</a>',
        block,
        flags=re.I | re.S,
    )
    if m2:
        return re.sub(r"<[^>]+>", "", unescape(m2.group(1))).strip()
    return ""
