"""多平台公开搜索（P7-3）。

接入：搜狗微信 / 知乎搜索 / B 站搜索 / 基金会中心网 / 百家号
（天眼查需要 cookie，单独放 tianyancha_search.py）

定位：每个平台一个 search_xxx() 函数，复用 PublicSearchResult 结构。
所有平台抓不到时静默返回 []，不阻塞主流程。
"""
from __future__ import annotations

import logging
import re
from html import unescape
from urllib.parse import quote_plus

import httpx

from app.services.public_search import PublicSearchResult, SEARCH_HEADERS

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# 搜狗微信公众号文章
# ──────────────────────────────────────────────────────────────────────────


def search_wechat(
    query: str,
    *,
    max_results: int = 8,
    timeout_seconds: float = 10.0,
    page: int = 1,
) -> list[PublicSearchResult]:
    """搜狗微信文章搜索。未登录可拿前 10 条左右。

    type=2 表示搜文章；type=1 是搜公众号。
    page: 翻页参数 (1 起算), 每页约 10 条. 5 页约 50 条, 5 页后开始触发 antispider.
    """
    query = (query or "").strip()
    if not query:
        return []
    page = max(1, int(page or 1))
    url = (
        f"https://weixin.sogou.com/weixin?type=2&query={quote_plus(query)}&page={page}"
    )
    try:
        resp = httpx.get(url, timeout=timeout_seconds, follow_redirects=True, headers={
            **SEARCH_HEADERS,
            "Referer": "https://weixin.sogou.com/",
        })
        if resp.status_code != 200 or not resp.text:
            return []
    except Exception:  # noqa: BLE001
        return []

    # 搜狗微信文章卡：<div class="news-box"> 或 <li id="sogou_vr_xxx">
    blocks = re.findall(
        r'<li[^>]+id=["\']sogou_vr[^"\']*["\'][^>]*>.*?(?=<li[^>]+id=["\']sogou_vr|</ul>)',
        resp.text, flags=re.I | re.S,
    )
    if not blocks:
        blocks = re.findall(
            r'<div[^>]+class=["\'][^"\']*\bnews-box\b[^"\']*["\'][^>]*>.*?(?=<div[^>]+class=["\'][^"\']*\bnews-box\b|</body>)',
            resp.text, flags=re.I | re.S,
        )

    results: list[PublicSearchResult] = []
    for block in blocks[:max_results * 2]:
        # 标题
        title_m = re.search(
            r'<h3[^>]*>.*?<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            block, flags=re.I | re.S,
        )
        if not title_m:
            continue
        raw_url = title_m.group(1).strip()
        title = _clean_html(title_m.group(2))[:180]
        if not title or not raw_url:
            continue

        # 搜狗微信链接是 /link?url=...形式，需要 hop
        if raw_url.startswith("/"):
            raw_url = f"https://weixin.sogou.com{raw_url}"
        elif not raw_url.startswith("http"):
            continue

        # snippet
        snip_m = re.search(
            r'<p[^>]+class=["\'][^"\']*\btxt-info\b[^"\']*["\'][^>]*>(.*?)</p>',
            block, flags=re.I | re.S,
        )
        snippet = _clean_html(snip_m.group(1)) if snip_m else ""

        # 公众号名 + 时间
        author_m = re.search(
            r'<a[^>]+id=["\']sogou_preview[^"\']*["\'][^>]*>(.*?)</a>',
            block, flags=re.I | re.S,
        )
        author = _clean_html(author_m.group(1)) if author_m else "公众号"

        results.append(PublicSearchResult(
            title=title,
            url=raw_url,
            snippet=snippet[:500],
            source=f"微信公众号·{author}",
            provider="wechat_sogou",
        ))
        if len(results) >= max_results:
            break
    return results


def search_wechat_pages(
    query: str,
    *,
    max_pages: int = 5,
    per_page: int = 10,
    timeout_seconds: float = 10.0,
) -> list[PublicSearchResult]:
    """翻 1..max_pages 页累加搜狗微信结果, 按 (sogou_url) 去重.

    搜狗对未登录用户翻页 5+ 后开始触发 antispider; 翻页时遇到 200 但 0 结果,
    立即停止 (大概率被 ban 或已到末页).
    """
    max_pages = max(1, min(10, int(max_pages or 5)))
    seen_urls: set[str] = set()
    aggregated: list[PublicSearchResult] = []
    for page in range(1, max_pages + 1):
        page_results = search_wechat(
            query, max_results=per_page, timeout_seconds=timeout_seconds, page=page
        )
        if not page_results:
            logger.info("[wechat-sogou] page=%s 0 results — stop pagination", page)
            break
        new_in_page = 0
        for result in page_results:
            if result.url in seen_urls:
                continue
            seen_urls.add(result.url)
            aggregated.append(result)
            new_in_page += 1
        if new_in_page == 0:
            # 搜狗某些 query 在末页会重复返回上一页, 0 新结果 = 翻完了
            break
    return aggregated


# ──────────────────────────────────────────────────────────────────────────
# 知乎搜索（公开内容）
# ──────────────────────────────────────────────────────────────────────────


def search_zhihu(
    query: str,
    *,
    max_results: int = 8,
    timeout_seconds: float = 10.0,
) -> list[PublicSearchResult]:
    """知乎全站搜索（content 类型）。

    知乎对 UA 校验严，需要尽量完整的浏览器 headers + 一个游客 cookie。
    抓不到时返回 []。
    """
    query = (query or "").strip()
    if not query:
        return []
    url = f"https://www.zhihu.com/search?type=content&q={quote_plus(query)}"
    try:
        resp = httpx.get(url, timeout=timeout_seconds, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Ch-Ua": '"Google Chrome";v="135", "Chromium";v="135", "Not?A_Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        })
        if resp.status_code != 200 or not resp.text:
            return []
    except Exception:  # noqa: BLE001
        return []

    # 知乎 SSR 渲染部分内容在 __NEXT_DATA__ 里；这里只解析能从 HTML 直接抓的卡片
    # 提取所有 https://www.zhihu.com/question/xxx/answer/yyy 形式的链接 + 周围文本
    matches = re.findall(
        r'<a[^>]+href=["\'](https?://(?:www\.)?zhihu\.com/(?:question/\d+(?:/answer/\d+)?|p/\d+|zvideo/\d+))["\'][^>]*>(.*?)</a>',
        resp.text, flags=re.I | re.S,
    )
    seen_urls: set[str] = set()
    results: list[PublicSearchResult] = []
    for url_, title_html in matches[: max_results * 4]:
        if url_ in seen_urls:
            continue
        title = _clean_html(title_html)
        if not title or len(title) < 5:
            continue
        seen_urls.add(url_)
        results.append(PublicSearchResult(
            title=title[:200],
            url=url_,
            snippet="",  # 知乎 snippet 难抽，让全文抓取阶段去补
            source="知乎",
            provider="zhihu_html",
        ))
        if len(results) >= max_results:
            break
    return results


# ──────────────────────────────────────────────────────────────────────────
# B 站搜索
# ──────────────────────────────────────────────────────────────────────────


def search_bilibili(
    query: str,
    *,
    max_results: int = 8,
    timeout_seconds: float = 10.0,
) -> list[PublicSearchResult]:
    """B 站搜索 — 走官方 search API（实测 verified work, 2026-05-19）。

    API: https://api.bilibili.com/x/web-interface/wbi/search/type
    无需 wbi 签名也能返回结果，且包含 author/play/desc 等完整字段。
    单次平均 20 条命中，比 HTML SEO 解析靠谱 10 倍。
    """
    query = (query or "").strip()
    if not query:
        return []
    url = (
        "https://api.bilibili.com/x/web-interface/wbi/search/type"
        f"?keyword={quote_plus(query)}&search_type=video"
    )
    try:
        resp = httpx.get(url, timeout=timeout_seconds, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36",
            "Referer": "https://www.bilibili.com/",
            "Accept": "application/json, text/plain, */*",
        })
        if resp.status_code != 200:
            return []
        data = resp.json()
        if data.get("code") != 0:
            logger.debug("[bilibili-api] non-zero code: %s", data.get("message"))
            return []
    except Exception as exc:  # noqa: BLE001
        logger.debug("[bilibili-api] failed: %s", exc)
        return []

    items = data.get("data", {}).get("result", []) or []
    results: list[PublicSearchResult] = []
    seen: set[str] = set()
    for v in items[: max_results * 2]:
        if not isinstance(v, dict):
            continue
        bvid = str(v.get("bvid") or "").strip()
        if not bvid or bvid in seen:
            continue
        seen.add(bvid)
        # B 站 title 含 <em class="keyword">...</em> 高亮，去掉
        title = re.sub(r"<[^>]+>", "", str(v.get("title") or "")).strip()
        if not title:
            continue
        desc = re.sub(r"<[^>]+>", "", str(v.get("description") or "")).strip()
        author = str(v.get("author") or "").strip()
        play = int(v.get("play") or 0)
        # 拼 snippet：作者 + 播放量 + 简介
        snippet_parts = []
        if author:
            snippet_parts.append(f"UP主：{author}")
        if play:
            snippet_parts.append(f"播放 {play:,}")
        if desc:
            snippet_parts.append(desc[:200])
        snippet = " · ".join(snippet_parts)[:500]
        results.append(PublicSearchResult(
            title=title[:200],
            url=f"https://www.bilibili.com/video/{bvid}",
            snippet=snippet,
            source="B站",
            provider="bilibili_api",
        ))
        if len(results) >= max_results:
            break
    return results


# 旧 HTML 解析路径已废弃 — B 站 SPA 严重导致 HTML 几乎无可用内容
# 上面 API 路径已 verified work（实测「公益基金会」20 条 / 「儿童心理 公益」20 条）
def _search_bilibili_html_legacy(
    query: str,
    *,
    max_results: int = 8,
    timeout_seconds: float = 10.0,
) -> list[PublicSearchResult]:
    """Legacy HTML 路径 — 已废弃，仅保留代码归档。"""
    return []  # 直接返回空，避免被错误调用


def _legacy_unused_bilibili_html(query: str, max_results: int, timeout_seconds: float):
    """归档的旧解析逻辑（仅文档）。"""
    url = f"https://search.bilibili.com/all?keyword={quote_plus(query)}"
    try:
        resp = httpx.get(url, timeout=timeout_seconds, follow_redirects=True, headers={
            **SEARCH_HEADERS,
            "Referer": "https://www.bilibili.com/",
        })
        if resp.status_code != 200 or not resp.text:
            return []
    except Exception:  # noqa: BLE001
        return []
    matches = re.findall(
        r'<a[^>]+href=["\']https?://(?:www\.)?bilibili\.com/video/(BV[A-Za-z0-9]+)[^"\']*["\'][^>]*title=["\']([^"\']+)["\']',
        resp.text, flags=re.I,
    )
    seen: set[str] = set()
    results: list[PublicSearchResult] = []
    for bvid, title in matches[: max_results * 3]:
        if bvid in seen:
            continue
        seen.add(bvid)
        results.append(PublicSearchResult(
            title=unescape(title)[:200],
            url=f"https://www.bilibili.com/video/{bvid}",
            snippet="",
            source="B站",
            provider="bilibili_html",
        ))
        if len(results) >= max_results:
            break
    return results


# ──────────────────────────────────────────────────────────────────────────
# 基金会中心网（公益机构权威信源）
# ──────────────────────────────────────────────────────────────────────────


def search_foundation_center(
    query: str,
    *,
    max_results: int = 5,
    timeout_seconds: float = 10.0,
) -> list[PublicSearchResult]:
    """基金会中心网搜索。

    `foundationcenter.org.cn` 是公益机构权威信源——查机构注册、年报、慈善法合规等。
    现在通过 site: 限定走 360/Sogou 搜索引擎间接抓；后续可加直接接入。
    """
    query = (query or "").strip()
    if not query:
        return []
    # 当前实现：通过 Bing 走 site: 限定，抓取速度更稳
    site_query = f"{query} site:foundationcenter.org.cn"
    url = f"https://www.bing.com/search?q={quote_plus(site_query)}&setlang=zh-CN&mkt=zh-CN"
    try:
        resp = httpx.get(url, timeout=timeout_seconds, follow_redirects=True, headers=SEARCH_HEADERS)
        if resp.status_code != 200:
            return []
    except Exception:  # noqa: BLE001
        return []

    # 简单解析 bing 结果
    matches = re.findall(
        r'<li[^>]+class=["\']b_algo["\'][^>]*>.*?<h2><a href=["\']([^"\']+)["\'][^>]*>(.*?)</a></h2>.*?<p[^>]*>(.*?)</p>',
        resp.text, flags=re.I | re.S,
    )
    results: list[PublicSearchResult] = []
    for url_, title_html, snippet_html in matches[:max_results]:
        if "foundationcenter.org.cn" not in url_:
            continue
        title = _clean_html(title_html)[:200]
        snippet = _clean_html(snippet_html)[:500]
        results.append(PublicSearchResult(
            title=title,
            url=url_,
            snippet=snippet,
            source="基金会中心网",
            provider="foundation_center",
        ))
    return results


# ──────────────────────────────────────────────────────────────────────────
# 百家号（自媒体长文）
# ──────────────────────────────────────────────────────────────────────────


def search_baijiahao(
    query: str,
    *,
    max_results: int = 8,
    timeout_seconds: float = 10.0,
) -> list[PublicSearchResult]:
    """百家号文章 — 通过百度搜 site:baijiahao.baidu.com。"""
    query = (query or "").strip()
    if not query:
        return []
    site_query = f"{query} site:baijiahao.baidu.com"
    url = f"https://www.bing.com/search?q={quote_plus(site_query)}&setlang=zh-CN&mkt=zh-CN"
    try:
        resp = httpx.get(url, timeout=timeout_seconds, follow_redirects=True, headers=SEARCH_HEADERS)
        if resp.status_code != 200:
            return []
    except Exception:  # noqa: BLE001
        return []
    matches = re.findall(
        r'<li[^>]+class=["\']b_algo["\'][^>]*>.*?<h2><a href=["\']([^"\']+)["\'][^>]*>(.*?)</a></h2>.*?<p[^>]*>(.*?)</p>',
        resp.text, flags=re.I | re.S,
    )
    results: list[PublicSearchResult] = []
    for url_, title_html, snippet_html in matches[: max_results * 2]:
        if "baijiahao.baidu.com" not in url_:
            continue
        results.append(PublicSearchResult(
            title=_clean_html(title_html)[:200],
            url=url_,
            snippet=_clean_html(snippet_html)[:500],
            source="百家号",
            provider="baijiahao_bing",
        ))
        if len(results) >= max_results:
            break
    return results


# ──────────────────────────────────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────────────────────────────────


def _clean_html(s: str) -> str:
    if not s:
        return ""
    text = re.sub(r"<[^>]+>", " ", s)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# 统一调度
PLATFORM_DISPATCH = {
    "wechat": (search_wechat, "wechat_article"),
    "zhihu": (search_zhihu, "zhihu_answer"),
    "bilibili": (search_bilibili, "bilibili_video"),
    "foundation_registry": (search_foundation_center, "foundation_registry"),
    "baijiahao": (search_baijiahao, "baijiahao_article"),
}


def search_by_platform(
    platform: str,
    query: str,
    *,
    max_results: int = 5,
    timeout_seconds: float = 10.0,
) -> tuple[list[PublicSearchResult], str]:
    """统一入口：传 platform key 派发到对应抓取器。返回 (results, source_type)。"""
    entry = PLATFORM_DISPATCH.get(platform)
    if not entry:
        return [], "external_search_engine"
    func, source_type = entry
    try:
        results = func(query, max_results=max_results, timeout_seconds=timeout_seconds)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[multi-platform] %s failed: %s", platform, exc)
        return [], source_type
    return results, source_type
