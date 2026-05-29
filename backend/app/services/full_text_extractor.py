"""全文抓取 + 正文提取（P7-6）。

目的：把搜索引擎返回的 200 字 snippet 升级为完整正文，
让下游 LLM 主题聚类 / brand audit 在更厚的内容上跑。

实现：纯 stdlib + httpx，不引入 trafilatura/readability 等新依赖。
对中文资讯类网页（微信公众号、新闻站、知乎专栏）效果可接受；
复杂 SPA 站点会失败 — 失败时降级回 snippet。
"""
from __future__ import annotations

import logging
import re
from html import unescape

import httpx

logger = logging.getLogger(__name__)


# 提取正文优先尝试的标签（按命中优先级）
ARTICLE_TAGS = [
    # 微信公众号
    (r'<div[^>]+id=["\']js_content["\'][^>]*>(.*?)</div>\s*(?:<script|<style|$)', "wechat"),
    # 通用 article / main
    (r'<article[^>]*>(.*?)</article>', "article"),
    (r'<main[^>]*>(.*?)</main>', "main"),
    # 常见 content 类
    (r'<div[^>]+(?:id|class)=["\'](?:[^"\']*\b)?(?:content|article-content|post-content|entry-content|article-body|main-content)\b[^"\']*["\'][^>]*>(.*?)</div>\s*(?:<footer|<aside|<div class="(?:sidebar|comment|share)|$)', "content_div"),
]

# 噪声标签整段删除
NOISE_BLOCK_PATTERNS = [
    r'<script\b[^>]*>.*?</script>',
    r'<style\b[^>]*>.*?</style>',
    r'<noscript\b[^>]*>.*?</noscript>',
    r'<nav\b[^>]*>.*?</nav>',
    r'<footer\b[^>]*>.*?</footer>',
    r'<aside\b[^>]*>.*?</aside>',
    r'<header\b[^>]*>.*?</header>',
    r'<form\b[^>]*>.*?</form>',
    r'<!--.*?-->',
]


HEADERS_DESKTOP = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def fetch_full_text(
    url: str,
    *,
    timeout_seconds: float = 10.0,
    max_chars: int = 5000,
    min_chars: int = 200,
) -> str:
    """对单 URL 跑全文抓取。

    成功返回纯文本（去标签、去空白），失败返回空字符串。
    """
    if not url or not url.startswith(("http://", "https://")):
        return ""
    try:
        resp = httpx.get(url, timeout=timeout_seconds, follow_redirects=True, headers=HEADERS_DESKTOP)
    except Exception as exc:  # noqa: BLE001
        logger.debug("[full-text] fetch failed url=%s: %s", url, exc)
        return ""
    if resp.status_code != 200 or not resp.text:
        return ""

    html = resp.text

    # 1. 删除明显噪声段
    for pattern in NOISE_BLOCK_PATTERNS:
        html = re.sub(pattern, " ", html, flags=re.I | re.S)

    # 2. 优先抓 article/main 标签内容
    extracted = ""
    for pattern, _label in ARTICLE_TAGS:
        m = re.search(pattern, html, flags=re.I | re.S)
        if m:
            extracted = m.group(1)
            break

    # 3. 没找到结构化标签 → 取 body 全文（兜底）
    if not extracted:
        body_m = re.search(r'<body[^>]*>(.*?)</body>', html, flags=re.I | re.S)
        extracted = body_m.group(1) if body_m else html

    # 4. 删 tag → 还原实体 → 压缩空白
    text = re.sub(r"<[^>]+>", " ", extracted)
    text = unescape(text)
    text = re.sub(r"[​-‏﻿]", "", text)  # 零宽字符
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) < min_chars:
        return ""

    return text[:max_chars]


def fetch_full_texts_batch(
    urls: list[str],
    *,
    timeout_seconds: float = 10.0,
    max_chars_each: int = 5000,
    max_total: int = 30,
) -> dict[str, str]:
    """批量抓取 - 串行版本（最多 max_total 条，超时也不阻塞主流程）。"""
    result: dict[str, str] = {}
    for url in urls[:max_total]:
        if url in result:
            continue
        text = fetch_full_text(
            url,
            timeout_seconds=timeout_seconds,
            max_chars=max_chars_each,
        )
        if text:
            result[url] = text
    return result
