from __future__ import annotations

import hashlib
import logging
import re
import tempfile
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urljoin, urlparse, urlunparse
from xml.etree import ElementTree as ET

import httpx

from app.db import Database
from app.db import to_json
from app.services.knowledge_v2 import (
    extract_document_with_metadata,
    ingest_document_knowledge,
    now_iso,
    upsert_canonical_text_document,
)

logger = logging.getLogger(__name__)

FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

BING_WEB_RSS_TEMPLATE = "https://www.bing.com/search?q={query}&format=rss&setlang=zh-cn"

DETAIL_HINT_PATTERNS = (
    re.compile(r"/sys-nd/\d+\.html?$", re.I),
    re.compile(r"/content/\d+", re.I),
    re.compile(r"/news(?:/|_|-).+", re.I),
    re.compile(r"/(?:detail|article)/\d+\.html?$", re.I),
    re.compile(r"/\d+\.html?$", re.I),
)

LIST_HINT_PATTERNS = (
    re.compile(r"/h-col-\d+\.html?$", re.I),
    re.compile(r"/(?:news|projects?|info|gongyi|notice)(?:/|$)", re.I),
)

IGNORE_PATH_PATTERNS = (
    re.compile(r"/(?:login|logout|register|search)(?:/|$)", re.I),
    re.compile(r"/(?:contact|privacy|terms|help)(?:/|$)", re.I),
)

NAVIGATION_LINE_MARKERS = (
    "首页 Home",
    "关于我们 About",
    "项目展示 projects",
    "信息公开 Info",
    "支持我们 Support",
    "合作伙伴 Partners",
    "留言板 Messages",
    "管理登录",
    "本站使用",
    "贵公网安备",
    "手机版",
    "联系我们",
    "更多资讯",
    "分享到",
)

BOILERPLATE_LINE_PATTERNS = (
    re.compile(r"^联系电话[:：]"),
    re.compile(r"^邮箱[:：]"),
    re.compile(r"^地址[:：]"),
    re.compile(r"ICP备\d+"),
    re.compile(r"^上一篇"),
    re.compile(r"^下一篇"),
)

GENERIC_RELEVANCE_TERMS = {
    "项目",
    "预算",
    "评估",
    "传播",
    "案例",
    "标准",
    "指标",
    "公益",
    "合作",
    "资料",
}

GOV_DOMAINS = ("gov.cn", "moe.gov.cn")
FOUNDATION_DOMAINS = (
    "weiaiqianxing.cn",
    "naradafoundation.org",
    "cfpa.org.cn",
    "onefoundation.cn",
    "hefengart.org.cn",
)
NEWS_DOMAINS = (
    "news.cn",
    "xinhuanet.com",
    "chinanews.com.cn",
    "chinadaily.com.cn",
    "gzstv.com",
    "thepaper.cn",
    "people.com.cn",
    "xinhua",
)

INTERNET_SOURCE_CANONICAL_KINDS = {
    "internet_source_doc",
    "evaluation_reference_doc",
    "similar_case_doc",
    "policy_context_doc",
}


@dataclass
class InternetCrawlOptions:
    max_pages: int = 30
    max_depth: int = 2
    max_pdfs: int = 10
    request_timeout_seconds: float = 12.0
    min_text_chars: int = 180
    # depth==0 且来自调用方 seed_urls 的 URL 是用户已确认的官方渠道, 跳过两道相关性过滤.
    # 搜索引擎结果回填的 URL 不享受此豁免 (它们没被人工确认过).
    trust_user_seeds: bool = True


@dataclass
class FetchedContent:
    url: str
    status_code: int
    content_type: str
    text: str = ""
    body: bytes = b""


@dataclass
class InternetCrawlDocument:
    url: str
    title: str
    content: str
    source_type: str
    credibility_level: str
    canonical_kind: str
    domain: str
    published_at: str | None
    crawled_at: str
    content_hash: str
    depth: int = 0
    source_label: str = ""
    time_scope: str = ""
    raw_content_type: str = "html"
    errors: list[str] = field(default_factory=list)
    # 仅 PDF/二进制资料保留原始字节, 用于扫描件走 OCR 入库. HTML 资料留空避免内存膨胀.
    raw_bytes: bytes = b""


@dataclass
class InternetFactCard:
    source_url: str
    source_title: str
    fact_lines: list[str]
    generated_at: str


@dataclass
class InternetEnrichmentResult:
    crawled_count: int = 0
    source_doc_count: int = 0
    fact_card_count: int = 0
    project_doc_count: int = 0
    failed_count: int = 0
    remaining_user_required_gaps: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


Fetcher = Callable[[str], FetchedContent | None]
EventCallback = Callable[[str, str, dict[str, object] | None], None]
ProgressCallback = Callable[[int, str], None]


def stable_url_key(url: str) -> str:
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()[:20]


def normalize_url(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if not parsed.scheme:
        parsed = urlparse(f"https://{raw}")
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    cleaned = parsed._replace(fragment="", path=path)
    return urlunparse(cleaned).rstrip("/")


def domain_label(url: str) -> str:
    return urlparse(url).netloc.lower().replace("www.", "")


def classify_source_domain(url: str) -> tuple[str, str]:
    domain = domain_label(url)
    if domain.endswith("gov.cn") or any(token in domain for token in GOV_DOMAINS):
        return "government", "L1"
    if any(domain.endswith(item) or item in domain for item in FOUNDATION_DOMAINS):
        return "official_or_foundation", "L1"
    if any(item in domain for item in NEWS_DOMAINS):
        return "media", "L2"
    return "reference", "L3"


def classify_canonical_kind(*, title: str, url: str, source_type: str) -> str:
    merged = f"{title} {url}".lower()
    if source_type == "government" or any(token in merged for token in ("政策", "条例", "通知", "教育部", "gov.cn")):
        return "policy_context_doc"
    if any(token in merged for token in ("评估报告", "扫描报告", "成效评估", "assessment", "report")):
        return "evaluation_reference_doc"
    if any(token in merged for token in ("案例", "艺术课堂", "壹乐园", "快乐合唱", "荷风", "奇尼")) and "大山里的音乐课堂" not in title:
        return "similar_case_doc"
    return "internet_source_doc"


def _default_fetcher(timeout_seconds: float) -> Fetcher:
    client = httpx.Client(timeout=httpx.Timeout(timeout_seconds, connect=6.0), headers=FETCH_HEADERS, follow_redirects=True)

    def fetch(url: str) -> FetchedContent | None:
        try:
            response = client.get(url)
            response.raise_for_status()
            return FetchedContent(
                url=str(response.url),
                status_code=response.status_code,
                content_type=response.headers.get("content-type", ""),
                text=response.text if _looks_like_text(response.headers.get("content-type", ""), str(response.url)) else "",
                body=response.content,
            )
        except Exception:
            return None

    return fetch


def _looks_like_text(content_type: str, url: str) -> bool:
    lowered = f"{content_type} {url}".lower()
    return any(token in lowered for token in ("text/html", "xml", "json", ".html", ".htm")) and ".pdf" not in lowered


def _looks_like_pdf(content_type: str, url: str) -> bool:
    lowered = f"{content_type} {url}".lower()
    return "pdf" in lowered or urlparse(url).path.lower().endswith(".pdf")


def html_title(html: str) -> str:
    for pattern in (
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)["\']',
        r"<title>(.*?)</title>",
        r"<h1[^>]*>(.*?)</h1>",
    ):
        match = re.search(pattern, html, flags=re.I | re.S)
        if match:
            value = clean_inline_text(match.group(1))
            if value:
                return value
    return ""


def extract_published_at(html: str) -> str | None:
    patterns = (
        r"发布时间[：:]\s*([12]\d{3}[-年/]\d{1,2}[-月/]\d{1,2}(?:[日\s]+\d{1,2}:\d{2}(?::\d{2})?)?)",
        r"发表时间[：:]\s*([12]\d{3}[-年/]\d{1,2}[-月/]\d{1,2}(?:[日\s]+\d{1,2}:\d{2}(?::\d{2})?)?)",
        r"([12]\d{3}-\d{1,2}-\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)",
    )
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.I | re.S)
        if not match:
            continue
        normalized = normalize_datetime(match.group(1))
        if normalized:
            return normalized
    return None


def normalize_datetime(value: str | None) -> str | None:
    raw = clean_inline_text(value)
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).astimezone().replace(microsecond=0).isoformat()
    except Exception:
        pass
    normalized = raw.replace("/", "-").replace(".", "-").replace("年", "-").replace("月", "-").replace("日", "")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    from datetime import datetime

    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(normalized, pattern).isoformat()
        except ValueError:
            continue
    return None


def clean_inline_text(value: str | None) -> str:
    text = unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_html_to_markdown(html: str, *, source_url: str = "") -> str:
    text = html or ""
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<svg[^>]*>.*?</svg>", " ", text)
    text = re.sub(r"(?is)<(?:nav|footer|header|form|aside)[^>]*>.*?</(?:nav|footer|header|form|aside)>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(?:p|div|section|article|li|h1|h2|h3|h4|tr)>", "\n", text)
    text = re.sub(r"(?i)<(?:h1|h2|h3)[^>]*>", "\n## ", text)
    text = re.sub(r"(?i)<li[^>]*>", "\n- ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[\t\r\f\v]+", " ", text)

    lines: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line or len(line) <= 1:
            continue
        if any(marker in line for marker in NAVIGATION_LINE_MARKERS):
            continue
        if any(pattern.search(line) for pattern in BOILERPLATE_LINE_PATTERNS):
            continue
        if len(line) < 8 and not re.search(r"[\u4e00-\u9fff].*[\u4e00-\u9fff]", line):
            continue
        key = re.sub(r"\s+", "", line.lower())
        if key in seen:
            continue
        seen.add(key)
        lines.append(line)
    return "\n\n".join(lines).strip()


def extract_links(html: str, *, base_url: str, relevance_terms: list[str] | None = None) -> list[str]:
    base_domain = domain_label(base_url)
    terms = [term for term in (relevance_terms or []) if term]
    candidates: list[tuple[int, str]] = []
    seen: set[str] = set()
    for href, inner_html in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html or "", flags=re.I | re.S):
        normalized = normalize_url(urljoin(base_url, href.strip()))
        if not normalized:
            continue
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"}:
            continue
        if domain_label(normalized) != base_domain:
            continue
        if normalized in seen:
            continue
        path = parsed.path or ""
        if any(pattern.search(path) for pattern in IGNORE_PATH_PATTERNS):
            continue
        title = clean_inline_text(inner_html)
        score = 0
        if _looks_like_detail_path(path):
            score += 8
        if any(pattern.search(path) for pattern in LIST_HINT_PATTERNS):
            score += 3
        if path.lower().endswith(".pdf"):
            score += 6
        merged = f"{title} {path}".lower()
        for term in terms:
            if term.lower() in merged:
                score += 4
        if score <= 0:
            continue
        seen.add(normalized)
        candidates.append((score, normalized))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [url for _score, url in candidates]


def _looks_like_detail_path(path: str) -> bool:
    return any(pattern.search(path or "") for pattern in DETAIL_HINT_PATTERNS)


def relevance_terms_from_inputs(
    seed_queries: list[str],
    gaps: list[str],
    *,
    client_name: str = "",
) -> list[str]:
    """从 seed_queries + gaps + client_name 抽相关性关键词.

    机制化: client_name 作为参数注入,**不硬编码任何客户名/项目名**.
    """
    raw = " ".join([*seed_queries, *gaps])
    terms: list[str] = []
    if client_name and client_name not in terms:
        terms.append(client_name)
    for token in re.split(r"[\s,，。；;:：|/]+", raw):
        token = token.strip().strip('"“”')
        if len(token) >= 3 and token not in terms:
            terms.append(token)
    return terms[:24]


def expand_seed_queries(seed_queries: list[str], gaps: list[str], seed_urls: list[str]) -> list[str]:
    """机制化查询扩展: 用 seed_queries 第一项作为 site: 限定关键词,
    任意客户/项目都能自动构造站内检索, 不依赖特定项目名硬编码。
    """
    queries: list[str] = []
    for query in [*seed_queries, *gaps]:
        cleaned = re.sub(r"\s+", " ", str(query or "")).strip()
        if cleaned and cleaned not in queries:
            queries.append(cleaned)
    primary_seed = queries[0] if queries else ""
    if primary_seed:
        for url in seed_urls:
            domain = domain_label(url)
            if not domain:
                continue
            site_query = f"site:{domain} {primary_seed}"
            if site_query not in queries:
                queries.append(site_query)
    return queries[:12]


def search_urls_for_queries(
    queries: list[str],
    *,
    fetcher: Fetcher | None = None,
    max_urls: int = 20,
    relevance_terms: list[str] | None = None,
) -> list[str]:
    fetch = fetcher or _default_fetcher(10.0)
    terms = [term for term in (relevance_terms or []) if term]
    found: list[str] = []
    seen: set[str] = set()
    for query in queries:
        if len(found) >= max_urls:
            break
        url = BING_WEB_RSS_TEMPLATE.format(query=quote(query))
        fetched = fetch(url)
        if not fetched or not fetched.text:
            continue
        for link, title, description in _parse_rss_items(fetched.text):
            normalized = normalize_url(link)
            if normalized and normalized not in seen:
                if terms and _search_result_relevance_score(normalized, title, description, terms) <= 0:
                    continue
                seen.add(normalized)
                found.append(normalized)
                if len(found) >= max_urls:
                    break
    return found


def _parse_rss_links(xml_text: str) -> list[str]:
    return [link for link, _title, _description in _parse_rss_items(xml_text)]


def _parse_rss_items(xml_text: str) -> list[tuple[str, str, str]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    items: list[tuple[str, str, str]] = []
    for item in root.findall(".//item"):
        link = item.findtext("link") or ""
        if link.strip():
            title = item.findtext("title") or ""
            description = item.findtext("description") or ""
            items.append((link.strip(), clean_inline_text(title), clean_inline_text(description)))
    return items


def _search_result_relevance_score(url: str, title: str, description: str, terms: list[str]) -> int:
    haystack = f"{title}\n{description}\n{url}".lower()
    score = 0
    strong_score = 0
    for term in terms:
        normalized = term.lower().strip()
        if not normalized:
            continue
        if normalized in haystack:
            term_score = 3 if len(normalized) >= 6 else 1
            score += term_score
            if _is_strong_relevance_term(normalized):
                strong_score += term_score
    if strong_score <= 0:
        return 0
    if _is_generic_reference_page(title, url):
        return 0
    return score


def _document_relevance_score(document: InternetCrawlDocument, terms: list[str]) -> int:
    haystack = f"{document.title}\n{document.url}\n{document.content[:3600]}".lower()
    score = 0
    strong_score = 0
    for term in terms:
        normalized = term.lower().strip()
        if not normalized:
            continue
        if normalized in haystack:
            term_score = 3 if len(normalized) >= 6 else 1
            score += term_score
            if _is_strong_relevance_term(normalized):
                strong_score += term_score
    if strong_score <= 0 and document.credibility_level != "L1":
        return 0
    if _is_generic_reference_page(document.title, document.url):
        return 0
    return score


def _is_strong_relevance_term(term: str) -> bool:
    cleaned = term.strip().lower()
    if not cleaned or cleaned in GENERIC_RELEVANCE_TERMS:
        return False
    if len(cleaned) >= 4:
        return True
    return any(token in cleaned for token in ("为爱", "黔行", "日慈", "cffc"))


def _is_generic_reference_page(title: str, url: str) -> bool:
    text = f"{title} {url}".lower()
    generic_titles = {"项目", "项目 - mba智库百科", "项目（汉语词语）_百度百科"}
    if title.strip().lower() in generic_titles:
        return True
    if any(domain in text for domain in ("baike.baidu.com/item/%e9%a1%b9%e7%9b%ae", "wiki.mbalib.com/wiki/%e9%a1%b9%e7%9b%ae")):
        return True
    return False


def crawl_internet_sources(
    *,
    seed_urls: list[str],
    seed_queries: list[str] | None = None,
    gaps: list[str] | None = None,
    options: InternetCrawlOptions | None = None,
    fetcher: Fetcher | None = None,
    event_callback: EventCallback | None = None,
    client_name: str = "",
) -> list[InternetCrawlDocument]:
    """爬虫主流程.

    client_name (机制化): 用于 (1) 注入相关性关键词 (2) HTML 正文最终保险过滤.
    传空表示"不限主题"(老调用方兼容), 但实测带客户名能把噪音率从 50% 降到 <10%.
    """
    opts = options or InternetCrawlOptions()
    fetch = fetcher or _default_fetcher(opts.request_timeout_seconds)
    queries = expand_seed_queries(seed_queries or [], gaps or [], seed_urls)
    relevance_terms = relevance_terms_from_inputs(queries, gaps or [], client_name=client_name)
    # 用户在 official_channels 里勾选的域名 = "整个域名都是这家机构的官方资料".
    # 抓到的页面只要 domain 命中, 跳过相关性 / 客户名子串过滤 — 因为页面标题里
    # 可能只写"项目详情 | 心智素养课程"而没出现 client_name 字面, 但仍属官方内容.
    # 通用导航页 (_is_generic_reference_page) 仍会被过滤; 短文(min_text_chars) 也仍过滤.
    trusted_seed_domains: set[str] = set()
    if opts.trust_user_seeds:
        for raw_seed in seed_urls:
            seed_domain = domain_label(raw_seed)
            if seed_domain:
                trusted_seed_domains.add(seed_domain.lower())
    if event_callback:
        event_callback("info", "互联网搜索词已生成", {"queries": queries, "seedUrlCount": len(seed_urls), "trustedDomains": sorted(trusted_seed_domains)})
    # queue 元素: (url, depth, is_user_seed). is_user_seed=True 表示由调用方显式传入的种子,
    # 用户已人工确认过, depth==0 且 opts.trust_user_seeds 时可跳过相关性 + 客户名过滤.
    # 搜索引擎结果 / 扩散链接 is_user_seed=False.
    queue: list[tuple[str, int, bool]] = []
    seen: set[str] = set()
    for url in seed_urls:
        normalized = normalize_url(url)
        if normalized and normalized not in seen:
            queue.append((normalized, 0, True))
            seen.add(normalized)
    for url in search_urls_for_queries(queries, fetcher=fetch, max_urls=opts.max_pages, relevance_terms=relevance_terms):
        if url not in seen:
            queue.append((url, 0, False))
            seen.add(url)

    documents: list[InternetCrawlDocument] = []
    pdf_count = 0
    index = 0
    while queue and len(documents) < opts.max_pages:
        url, depth, is_user_seed = queue.pop(0)
        index += 1
        if event_callback:
            event_callback("info", "互联网 URL 开始抓取", {"url": url, "depth": depth, "index": index})
        fetched = fetch(url)
        if not fetched:
            if event_callback:
                event_callback("warning", "互联网资料抓取失败", {"url": url, "depth": depth})
            continue
        crawled_at = now_iso()
        final_url = normalize_url(fetched.url or url)
        # PDF magic-byte 兜底识别 (例: ricifoundation.com/Home/Info/reportDetail/id/56.html
        # 实际是 application/pdf 但 URL 后缀是 .html, _looks_like_pdf 之前需要 content_type
        # 含 "pdf"; 此处加 body 头 %PDF 探测, 即使 content_type 不规范也能识别)
        looks_pdf = _looks_like_pdf(fetched.content_type, final_url) or (
            fetched.body[:4] == b"%PDF"
        )
        try:
            if looks_pdf:
                if pdf_count >= opts.max_pdfs:
                    continue
                pdf_count += 1
                document = _document_from_pdf(final_url, fetched.body, crawled_at=crawled_at, depth=depth)
            else:
                document = _document_from_html(final_url, fetched.text, crawled_at=crawled_at, depth=depth)
        except Exception as error:
            if event_callback:
                event_callback("warning", "互联网资料清洗失败", {"url": final_url, "error": str(error)[:300]})
            continue
        # 用户已确认 = 两条 bypass 通路:
        # (1) depth==0 显式 seed: 用户在 official_channels 里勾选的具体 URL → 必收录;
        # (2) trusted_seed_domains 命中: 用户勾选的域名整站, 子页扩散到同域名也算官方资料,
        #     例如 ricifoundation.com/Home/About/index.html 是官网"日慈简介"页, 标题里
        #     可能没"日慈基金会"字面但仍是该机构官方内容. 通用导航页/短文仍会被下游过滤.
        final_domain = domain_label(document.url).lower() if document.url else ""
        bypass_relevance = bool(
            opts.trust_user_seeds
            and (
                (is_user_seed and depth == 0)
                or (final_domain and final_domain in trusted_seed_domains)
            )
        )
        if not bypass_relevance and document.credibility_level != "L1" and _document_relevance_score(document, relevance_terms) <= 0:
            # PDF 扫描件文本为 0 字, 也无 url 词命中 → 不能用相关性分数过滤. 看 URL/标题宽松通过.
            if document.raw_content_type != "pdf":
                if event_callback:
                    event_callback(
                        "warning",
                        "互联网资料系统相关性过滤",
                        {"url": document.url, "title": document.title, "credibilityLevel": document.credibility_level},
                    )
                continue
        # 机制化最终保险: HTML 文档"标题 或 正文前 500 字"必须命中 client_name.
        # - 全文命中不够 (实测网站 navigation/footer 里有客户名导航链接, 会让全站
        #   无关页面全部命中, 例如 gzculture.net 上"贵州其他公益新闻"被误带入)
        # - 标题命中是最强信号 (文章主题就是客户)
        # - 正文前 500 字命中是次强信号 (开头介绍提到客户)
        # PDF 跳过 (此时 content 还是空, 由下游 OCR 判定).
        # user_seed bypass: 用户已确认是这家机构的官方渠道, client_name 是否字面出现不再重要.
        if client_name and document.raw_content_type != "pdf" and not bypass_relevance:
            head = (document.title or "") + "\n" + (document.content or "")[:500]
            if client_name not in head:
                if event_callback:
                    event_callback(
                        "warning",
                        "互联网资料客户名缺失过滤",
                        {"url": document.url, "title": document.title, "clientName": client_name},
                    )
                continue
        # PDF 即使文本为 0 字也保留 — 让下游 ingest 走 OCR.
        is_pdf_needs_ocr = document.raw_content_type == "pdf" and "pdf_needs_ocr" in document.errors
        if len(document.content) >= opts.min_text_chars or is_pdf_needs_ocr:
            documents.append(document)
            if event_callback:
                event_callback(
                    "info",
                    "互联网资料已抓取",
                    {
                        "url": document.url,
                        "title": document.title,
                        "textChars": len(document.content),
                        "canonicalKind": document.canonical_kind,
                        "credibilityLevel": document.credibility_level,
                    },
                )
        if depth < opts.max_depth and fetched.text:
            for link in extract_links(fetched.text, base_url=final_url, relevance_terms=relevance_terms):
                if len(seen) >= opts.max_pages * 4:
                    break
                if link not in seen:
                    seen.add(link)
                    # 扩散链接不享受 user_seed 豁免 — 它们没被人工确认过, 仍需走相关性过滤.
                    queue.append((link, depth + 1, False))
    return _dedupe_documents(documents)


def _document_from_html(url: str, html: str, *, crawled_at: str, depth: int) -> InternetCrawlDocument:
    title = html_title(html) or domain_label(url) or "互联网资料"
    content = clean_html_to_markdown(html, source_url=url)
    source_type, credibility = classify_source_domain(url)
    canonical_kind = classify_canonical_kind(title=title, url=url, source_type=source_type)
    published_at = extract_published_at(html)
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return InternetCrawlDocument(
        url=url,
        title=title,
        content=content,
        source_type=source_type,
        credibility_level=credibility,
        canonical_kind=canonical_kind,
        domain=domain_label(url),
        published_at=published_at,
        crawled_at=crawled_at,
        content_hash=content_hash,
        depth=depth,
        source_label=domain_label(url),
        time_scope=published_at or crawled_at,
        raw_content_type="html",
    )


def _document_from_pdf(url: str, body: bytes, *, crawled_at: str, depth: int) -> InternetCrawlDocument:
    title = Path(urlparse(url).path).name or "互联网PDF资料"
    # 伪 .html 后缀的 PDF (例: 官网 reportDetail/id/56.html 实际是 application/pdf)
    # 给文件名补 .pdf, 避免下游 OCR 链路按 html 处理.
    if not title.lower().endswith(".pdf"):
        title = f"{title.rsplit('.', 1)[0]}.pdf"
    with tempfile.TemporaryDirectory(prefix="internet_pdf_") as tmp:
        pdf_path = Path(tmp) / title
        pdf_path.write_bytes(body)
        try:
            extracted = extract_document_with_metadata(pdf_path, title=title)
            content = extracted.text.strip()
        except Exception:  # noqa: BLE001
            content = ""
    source_type, credibility = classify_source_domain(url)
    canonical_kind = classify_canonical_kind(title=title, url=url, source_type=source_type)
    # 二进制内容用 body hash, 避免空文本时 hash 全相同导致 _dedupe_documents 误杀.
    content_hash = hashlib.sha256(body if not content else content.encode("utf-8")).hexdigest()
    errors: list[str] = []
    if not content:
        # 扫描件 (image-based PDF) 当前层无法解出文字, 标记 needs_ocr 让下游 ingest 走完整 OCR.
        errors.append("pdf_needs_ocr")
    return InternetCrawlDocument(
        url=url,
        title=title,
        content=content,
        source_type=source_type,
        credibility_level=credibility,
        canonical_kind=canonical_kind,
        domain=domain_label(url),
        published_at=None,
        crawled_at=crawled_at,
        content_hash=content_hash,
        depth=depth,
        source_label=domain_label(url),
        time_scope=crawled_at,
        raw_content_type="pdf",
        errors=errors,
        raw_bytes=body,
    )


def _extract_facts_for_v2_doc(
    db: Database,
    client_id: str,
    *,
    v2_document_id: str,
    event_callback: EventCallback | None = None,
) -> int:
    """对一份刚入库的 v2_document 的所有 chunks 跑 fact_extractor + persist.

    主干断点修复 (用户原话): 爬虫抓回的文档只入库 v2_documents 但不抽 atomic_facts,
    导致用户填表时还是看不到字段值. 本函数让 internet_enrichment 链路与 ingest 链路
    在"抽事实"步骤上对齐, 抓完即可见。

    返回新增 atomic_facts 数。
    """
    from app.services.contradiction_detector import persist_chunk_facts
    from app.services.fact_extractor import extract_facts_from_chunk

    chunks = db.fetchall(
        "SELECT id, content FROM v2_chunks WHERE v2_document_id = ? ORDER BY chunk_index ASC",
        (v2_document_id,),
    )
    total = 0
    for chunk in chunks:
        try:
            facts = extract_facts_from_chunk(chunk["content"] or "")
        except Exception:  # noqa: BLE001
            continue
        if not facts:
            continue
        try:
            inserted, _conflicts = persist_chunk_facts(
                db.conn,
                client_id=client_id,
                v2_document_id=v2_document_id,
                v2_chunk_id=str(chunk["id"]),
                facts=facts,
            )
            total += int(inserted)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[internet-enrichment] persist_chunk_facts failed: %s", exc)
    if total and event_callback:
        event_callback(
            "info",
            "互联网文档自动抽事实完成",
            {"v2DocumentId": v2_document_id, "factsInserted": total},
        )
    return total


def _ingest_internet_pdf(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    ai_service: Any | None,
    document: InternetCrawlDocument,
    origin_id: str,
    event_callback: EventCallback | None = None,
) -> bool:
    """互联网抓回 PDF (含扫描件) → 保存到客户数据目录 + 调 ingest 走完整 OCR.

    为什么不复用 upsert_canonical_text_document:
        - canonical 路径只写 markdown_content, 扫描件正文为空, 写进去也没价值
        - 需要让 PDF 走 ingest_document_knowledge → 触发 fitz/pypdf 文本提取
          → 失败回退到 OCR pipeline (qwen-vl/豆包视觉) → 抽 facts + 字典候选

    返回 True 表示文档已入库 (或之前已存在), False 表示完全失败.
    """
    # 稳定 doc id 复用 origin_id 的 url-hash, 保证幂等
    doc_id = f"doc_internet_{origin_id}"
    pdf_dir = data_dir / "client_workspace" / client_id / "internet_pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    # 文件名清理: 防止 ":" / "?" / "/" 等非法字符
    safe_name = re.sub(r'[\\/:*?"<>|]', "_", document.title)[:100]
    if not safe_name.lower().endswith(".pdf"):
        safe_name = f"{safe_name}.pdf"
    pdf_path = pdf_dir / f"{origin_id}_{safe_name}"
    pdf_path.write_bytes(document.raw_bytes)

    now = now_iso()
    fallback_excerpt = (
        f"互联网抓取 · 来源: {document.url} · 抓取时间: {document.crawled_at}\n"
        f"可信度: {document.credibility_level} · 来源类型: {document.source_type}"
    )

    # 幂等: 如果同 doc_id 已存在, 跳过 INSERT (但仍调 ingest 以触发 OCR)
    existing = db.fetchone("SELECT id FROM documents WHERE id = ?", (doc_id,))
    if not existing:
        db.execute(
            """INSERT INTO documents(
                id, client_id, folder_id, title, path, original_source_path, kind, source, excerpt, tags_json, created_at,
                document_family_id, canonical_kind, origin_type, origin_id, is_searchable,
                organization_id, department_id, department_ids_json, owner_user_id, source_entity_type, source_entity_id,
                visibility_scope, content_domain, lifecycle_status
            ) VALUES(?, ?, NULL, ?, ?, ?, 'pdf', 'internet_enrichment', ?, ?, ?, ?, ?, ?, ?, 1,
                     '', '', '[]', '', 'internet_source', ?, 'project_public', 'internet_enrichment', 'active')""",
            (
                doc_id, client_id, document.title, str(pdf_path), document.url,
                fallback_excerpt, to_json(["internet_enrichment", "pdf", document.credibility_level]),
                now, f"family_internet:{origin_id}", "internet_pdf", "internet_enrichment", origin_id,
                origin_id,
            ),
        )

    # 重要: 不在爬虫主流程里同步跑 OCR — 公益年报多为图片型扫描件 (实测 95 页扫描
    # 件每页 30-60 秒, 单个 PDF 卡爬虫 1 小时+)。
    # 策略: 爬虫层只完成"下载 + 落档 + documents/v2_documents 占位",
    # 标记 parse_status='pending' 等知识 job 队列异步消化 OCR。
    # 这样 30 个互联网 PDF 在 < 1 分钟里全部"进系统", OCR 在后台慢慢跑。
    try:
        v2_id = f"v2doc_{doc_id}"
        existing_v2 = db.fetchone("SELECT id FROM v2_documents WHERE id = ?", (v2_id,))
        if not existing_v2:
            db.execute(
                """INSERT INTO v2_documents(
                    id, client_id, document_id, original_path, managed_path, markdown_path, file_name, kind,
                    material_layer, visible_category, secondary_category, parse_status, parse_error,
                    preview_text, doc_index_text, content_hash, classification_confidence,
                    document_family_id, canonical_kind, origin_type, origin_id, is_searchable,
                    organization_id, department_id, department_ids_json, owner_user_id,
                    source_entity_type, source_entity_id, visibility_scope, content_domain, lifecycle_status,
                    imported_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pdf', 'evidence', '互联网补充资料', ?, 'pending_ocr', NULL,
                          ?, '', ?, 0.9,
                          ?, 'internet_pdf', 'internet_enrichment', ?, 1,
                          '', '', '[]', '',
                          'internet_source', ?, 'project_public', 'internet_enrichment', 'active',
                          ?, ?)""",
                (
                    v2_id, client_id, doc_id, str(pdf_path), str(pdf_path), str(pdf_path),
                    document.title, document.credibility_level,
                    fallback_excerpt[:500], document.content_hash,
                    f"family_internet:{origin_id}", origin_id, origin_id, now, now,
                ),
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[internet-pdf] v2_documents insert failed for %s: %s", doc_id, exc)

    if event_callback:
        event_callback(
            "info",
            "互联网 PDF 已入库(待异步 OCR)",
            {"url": document.url, "title": document.title, "pdfBytes": len(document.raw_bytes),
             "docId": doc_id, "path": str(pdf_path)},
        )
    return True


def _dedupe_documents(documents: list[InternetCrawlDocument]) -> list[InternetCrawlDocument]:
    deduped: list[InternetCrawlDocument] = []
    seen_urls: set[str] = set()
    seen_hashes: set[str] = set()
    for document in documents:
        url_key = normalize_url(document.url)
        hash_key = document.content_hash
        if url_key in seen_urls or hash_key in seen_hashes:
            continue
        seen_urls.add(url_key)
        seen_hashes.add(hash_key)
        deduped.append(document)
    return deduped


def render_internet_source_markdown(document: InternetCrawlDocument) -> str:
    return "\n".join(
        [
            f"# {document.title}",
            "",
            "## 来源元数据",
            f"- 来源链接：{document.url}",
            f"- 来源域名：{document.domain}",
            f"- 来源类型：{document.source_type}",
            f"- 可信度等级：{document.credibility_level}",
            f"- 发布时间：{document.published_at or '未知'}",
            f"- 抓取时间：{document.crawled_at}",
            f"- 时间口径：{document.time_scope or document.published_at or document.crawled_at}",
            f"- 内容哈希：{document.content_hash}",
            "",
            "## 正文",
            document.content.strip(),
        ]
    ).strip()


def extract_fact_lines_with_doubao(
    ai_service: Any,
    *,
    document: InternetCrawlDocument,
    current_date: str,
    gaps: list[str] | None = None,
    max_chars: int = 1000,
) -> list[str]:
    if not ai_service or not hasattr(ai_service, "_qwen_generate"):
        return []
    lines: list[str] = []
    seen: set[str] = set()
    chunks = _split_fact_chunks(document.content, max_chars=max_chars, max_chunks=6)
    for index, excerpt in enumerate(chunks, start=1):
        prompt = (
            f"当前日期：{current_date}\n"
            f"来源标题：{document.title}\n"
            f"来源链接：{document.url}\n"
            f"来源类型：{document.source_type}\n"
            f"可信度等级：{document.credibility_level}\n"
            f"发布时间：{document.published_at or '未知'}\n"
            f"抓取时间：{document.crawled_at}\n"
            f"当前分块：{index}/{len(chunks)}\n"
            f"本次资料缺口：{'；'.join(gaps or []) if gaps else '未提供显式缺口'}\n"
            "只从摘录中抽取与本次资料缺口直接相关的事实；跳过广告、导航、无关项目、无关品牌和页面杂项。"
            "禁止写处理步骤。每行必须以 FACT:、NUMBER:、TIME: 或 GAP: 开头。最多 8 行。\n"
            f"摘录：{excerpt}"
        )
        try:
            result = ai_service._qwen_generate(
                prompt=prompt,
                system_instruction="只抽事实。不要解释，不要写处理过程。",
                response_schema=None,
                timeout_seconds=35.0,
                max_tokens=800,
            )
        except Exception:
            continue
        for raw_line in str(result or "").splitlines():
            line = raw_line.strip()
            if not re.match(r"^(FACT|NUMBER|TIME|GAP):\s*\S", line):
                continue
            normalized = re.sub(r"\s+", " ", line[:500]).strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                lines.append(normalized)
        if len(lines) >= 18:
            break
    return lines[:18]


def _split_fact_chunks(text: str, *, max_chars: int = 1000, max_chunks: int = 6) -> list[str]:
    paragraphs = [item.strip() for item in re.split(r"\n{2,}", text or "") if item.strip()]
    if not paragraphs:
        return [text[:max_chars]] if text else []
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            for start in range(0, len(paragraph), max_chars):
                chunks.append(paragraph[start : start + max_chars].strip())
                if len(chunks) >= max_chunks:
                    return chunks
            continue
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) > max_chars and current:
            chunks.append(current.strip())
            current = paragraph
        else:
            current = candidate
        if len(chunks) >= max_chunks:
            return chunks
    if current and len(chunks) < max_chunks:
        chunks.append(current.strip())
    return chunks[:max_chunks]


def judge_document_relevance_with_doubao(
    ai_service: Any,
    *,
    document: InternetCrawlDocument,
    gaps: list[str],
    current_date: str,
) -> tuple[bool, str]:
    if not ai_service or not hasattr(ai_service, "_qwen_generate"):
        return True, "no_ai_service"
    prompt = (
        f"当前日期：{current_date}\n"
        f"资料标题：{document.title}\n"
        f"来源链接：{document.url}\n"
        f"可信度等级：{document.credibility_level}\n"
        f"发布时间：{document.published_at or '未知'}\n"
        f"本次资料缺口：{'；'.join(gaps) if gaps else '未提供显式缺口'}\n"
        "判断这条资料是否值得进入项目资料库。只回答一行：YES:理由 或 NO:理由。不要排序，不要总结。\n"
        f"正文摘录：{document.content[:900]}"
    )
    try:
        result = str(
            ai_service._qwen_generate(
                prompt=prompt,
                system_instruction="你只做单条资料入库判断。宁可保留可能相关资料，也不要删掉可用项目资料。",
                response_schema=None,
                timeout_seconds=20.0,
                max_tokens=160,
            )
            or ""
        ).strip()
    except Exception as error:
        return True, f"judge_error:{str(error)[:120]}"
    first_line = result.splitlines()[0].strip() if result else ""
    if re.match(r"^NO\s*:", first_line, flags=re.I):
        return False, first_line[:240]
    if re.match(r"^YES\s*:", first_line, flags=re.I):
        return True, first_line[:240]
    return True, f"unstructured_judgment:{first_line[:180]}"


def render_fact_card_markdown(document: InternetCrawlDocument, fact_lines: list[str], *, generated_at: str) -> str:
    return "\n".join(
        [
            f"# 互联网事实卡：{document.title}",
            "",
            "## 来源",
            f"- 来源链接：{document.url}",
            f"- 来源类型：{document.source_type}",
            f"- 可信度等级：{document.credibility_level}",
            f"- 发布时间：{document.published_at or '未知'}",
            f"- 抓取时间：{document.crawled_at}",
            f"- 事实抽取时间：{generated_at}",
            "",
            "## 事实",
            *[f"- {line}" for line in fact_lines],
        ]
    ).strip()


def classify_gap_bucket(gap: str) -> str:
    text = str(gap or "")
    if any(token in text for token in ("本次", "拟走访", "学校名单", "项目预算", "捐赠人", "核心诉求")):
        return "user_required"
    if any(token in text for token in ("参考", "标准", "指标", "案例", "政策", "现状")):
        return "internet_fillable"
    return "hybrid"


def build_project_enrichment_markdown(
    *,
    title: str,
    target_type: str,
    target_id: str,
    documents: list[InternetCrawlDocument],
    fact_cards: list[InternetFactCard],
    gaps: list[str],
    generated_at: str,
) -> tuple[str, list[str]]:
    remaining_user_required = [gap for gap in gaps if classify_gap_bucket(gap) == "user_required"]
    lines = [
        f"# {title or '互联网资料补全文档'}",
        "",
        "## 生成信息",
        f"- 目标类型：{target_type or 'client'}",
        f"- 目标 ID：{target_id or 'client'}",
        f"- 生成时间：{generated_at}",
        f"- 互联网来源数：{len(documents)}",
        f"- 事实卡数：{len(fact_cards)}",
        "",
        "## 已抓取来源",
    ]
    for document in documents[:30]:
        lines.append(f"- [{document.title}]({document.url}) | {document.credibility_level} | {document.published_at or '发布时间未知'} | {document.canonical_kind}")
    lines.extend(["", "## 抽取事实"])
    for card in fact_cards:
        lines.append(f"### {card.source_title}")
        lines.append(f"来源：{card.source_url}")
        for fact in card.fact_lines:
            lines.append(f"- {fact}")
        lines.append("")
    lines.extend(["## 缺口状态"])
    if gaps:
        for gap in gaps:
            lines.append(f"- {classify_gap_bucket(gap)}：{gap}")
    else:
        lines.append("- 当前 job 未提供显式缺口。")
    lines.extend(["", "## 仍需用户补充"])
    if remaining_user_required:
        for gap in remaining_user_required:
            lines.append(f"- {gap}")
    else:
        lines.append("- 暂未识别出必须由用户补充的缺口。")
    return "\n".join(lines).strip(), remaining_user_required


def run_internet_enrichment(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    ai_service: Any | None,
    payload: dict[str, object],
    event_callback: EventCallback | None = None,
    progress_callback: ProgressCallback | None = None,
    fetcher: Fetcher | None = None,
) -> InternetEnrichmentResult:
    seed_urls = [str(item).strip() for item in payload.get("seedUrls", []) if str(item).strip()] if isinstance(payload.get("seedUrls"), list) else []
    seed_queries = [str(item).strip() for item in payload.get("seedQueries", []) if str(item).strip()] if isinstance(payload.get("seedQueries"), list) else []
    gaps = [str(item).strip() for item in payload.get("gaps", []) if str(item).strip()] if isinstance(payload.get("gaps"), list) else []
    max_pages = int(payload.get("maxPages") or 30)
    max_depth = int(payload.get("maxDepth") or 2)
    reason = str(payload.get("reason") or "internet_enrichment").strip()
    target_type = str(payload.get("targetType") or "client").strip()
    target_id = str(payload.get("targetId") or client_id).strip()
    title = str(payload.get("title") or "互联网资料补全文档").strip()
    # P13 · 内容域 override（品牌镜子用 'brand_official_corpus'，默认 'internet_enrichment'）
    content_domain_override = str(payload.get("contentDomainOverride") or "internet_enrichment").strip()
    if content_domain_override not in ("internet_enrichment", "brand_official_corpus"):
        content_domain_override = "internet_enrichment"
    options = InternetCrawlOptions(max_pages=max_pages, max_depth=max_depth)
    fetch_for_seeds = fetcher or _default_fetcher(options.request_timeout_seconds)

    # 权威源 seed 自动发现 (实证：Bing RSS 已死, 必须用 public_search 替代)
    # 当 seed_urls 为空时, 根据 client_name 从搜狗/360/Bing HTML 主动构造高价值种子:
    #   1. 百科条目 (搜狗百科/百度百科) — 含成立时间/性质/注册资金等结构化字段
    #   2. 客户官网首页 + 信息公开二级页 (章程/年报/审计/年刊/工作报告)
    #   3. 行业权威平台 (民政部/慈善中国/南都基金会/北师大公益研究院)
    client_name_for_seeds = str(payload.get("clientName") or "").strip()
    if not seed_urls and client_name_for_seeds:
        from app.services.nonprofit_authority_seeds import (
            build_seed_url_list,
            discover_authority_seeds,
        )
        try:
            discovery = discover_authority_seeds(
                client_name_for_seeds,
                fetcher=fetch_for_seeds,
                ai=ai_service,  # G: 让客户名扩展能调 LLM 推测全称
            )
            seed_urls = build_seed_url_list(discovery, max_total=max(20, max_pages))
            if event_callback:
                event_callback(
                    "info",
                    "权威源 seed 自动发现完成",
                    {
                        "clientName": client_name_for_seeds,
                        "authorityCount": len(discovery.authority_urls),
                        "homepageCount": len(discovery.official_homepages),
                        "disclosureCount": len(discovery.disclosure_pages),
                        "mediaCount": len(discovery.media_urls),
                        "totalSeeds": len(seed_urls),
                    },
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[internet-enrichment] authority seed discovery failed: %s", exc)

    if event_callback:
        event_callback("info", "互联网资料补全开始", {"seedUrls": seed_urls, "seedQueries": seed_queries, "gaps": gaps, "reason": reason})
    documents = crawl_internet_sources(
        seed_urls=seed_urls,
        seed_queries=seed_queries,
        gaps=gaps,
        options=options,
        fetcher=fetcher,
        event_callback=event_callback,
        client_name=client_name_for_seeds,
    )
    result = InternetEnrichmentResult(crawled_count=len(documents))
    generated_at = now_iso()
    fact_cards: list[InternetFactCard] = []
    accepted_documents: list[InternetCrawlDocument] = []
    processed = 0
    # 豆包"入库判断"和"事实抽取" 在抓取层默认关闭. 原因:
    # 1. 每文档 2 次 LLM 调用 (判断 + 抽事实), 30 文档 60 次, 5-15 分钟, 严重拖慢
    # 2. 抓取层已经有客户名命中过滤 + 权威源 seed, 入库判断收益边际
    # 3. 真正抽事实在主干 _extract_facts_for_v2_doc (规则) + 字典 Stage 1 (LLM 集中跑一次)
    # 用户可在 payload['enableDoubaoFactCard']=True 显式打开 (做"事实卡"沉淀时)
    enable_doubao_factcard = bool(payload.get("enableDoubaoFactCard", False))

    for document in documents:
        if enable_doubao_factcard:
            should_store, store_reason = judge_document_relevance_with_doubao(
                ai_service,
                document=document,
                gaps=gaps,
                current_date=generated_at[:10],
            )
            if event_callback:
                event_callback(
                    "info" if should_store else "warning",
                    "豆包资料入库判断完成",
                    {"url": document.url, "title": document.title, "store": should_store, "reason": store_reason},
                )
            if not should_store:
                processed += 1
                if progress_callback:
                    progress_callback(processed, f"已跳过低相关互联网资料：{document.title[:40]}")
                continue
        origin_id = stable_url_key(document.url)

        # PDF 走独立路径: 保存 PDF 文件 + 调 ingest_document_knowledge → 完整 OCR
        # (扫描件年报 90% 是图片型 PDF, upsert_canonical_text_document 只写 markdown 路径
        # 拿不到正文; 必须走文件 → OCR 链路才能抽出财务数字/治理信息)
        if document.raw_content_type == "pdf" and document.raw_bytes:
            try:
                _upserted_pdf = _ingest_internet_pdf(
                    db,
                    data_dir=data_dir,
                    client_id=client_id,
                    ai_service=ai_service,
                    document=document,
                    origin_id=origin_id,
                    event_callback=event_callback,
                )
                if _upserted_pdf:
                    result.source_doc_count += 1
                    accepted_documents.append(document)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[internet-pdf] ingest failed for %s: %s", document.url, exc)
                if event_callback:
                    event_callback("warning", "互联网 PDF 入库失败", {"url": document.url, "error": str(exc)[:300]})
            processed += 1
            if progress_callback:
                progress_callback(processed, f"已入库互联网 PDF (OCR 中)：{document.title[:40]}")
            continue

        source_text = render_internet_source_markdown(document)
        upserted = upsert_canonical_text_document(
            db,
            data_dir=data_dir,
            client_id=client_id,
            canonical_kind=document.canonical_kind,
            origin_type="internet_source",
            origin_id=origin_id,
            title=document.title,
            text=source_text,
            visible_category="互联网补充资料",
            secondary_category=document.credibility_level,
            created_at=document.published_at or document.crawled_at,
            updated_at=document.crawled_at,
            source_entity_type="internet_source",
            source_entity_id=origin_id,
            content_domain=content_domain_override,
        )
        if upserted:
            result.source_doc_count += 1
            accepted_documents.append(document)
            # 主干断点修复: HTML 文档 chunks 自动抽 atomic_facts → 进字典 Stage 1.
            try:
                v2_doc_id = str(upserted.get("v2DocumentId") or "")
                if v2_doc_id:
                    _extract_facts_for_v2_doc(db, client_id, v2_document_id=v2_doc_id, event_callback=event_callback)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[internet-enrichment] auto fact extract failed: %s", exc)
        fact_lines = extract_fact_lines_with_doubao(ai_service, document=document, current_date=generated_at[:10], gaps=gaps) if enable_doubao_factcard else []
        if fact_lines:
            fact_card = InternetFactCard(source_url=document.url, source_title=document.title, fact_lines=fact_lines, generated_at=generated_at)
            fact_cards.append(fact_card)
            fact_text = render_fact_card_markdown(document, fact_lines, generated_at=generated_at)
            fact_upserted = upsert_canonical_text_document(
                db,
                data_dir=data_dir,
                client_id=client_id,
                canonical_kind="internet_fact_card",
                origin_type="internet_fact_card",
                origin_id=origin_id,
                title=f"互联网事实卡：{document.title}",
                text=fact_text,
                visible_category="互联网事实卡",
                secondary_category=document.credibility_level,
                created_at=generated_at,
                updated_at=generated_at,
                source_entity_type="internet_source",
                source_entity_id=origin_id,
                content_domain=content_domain_override,
            )
            if fact_upserted:
                result.fact_card_count += 1
            if event_callback:
                event_callback(
                    "info",
                    "豆包事实抽取完成",
                    {"url": document.url, "title": document.title, "factLineCount": len(fact_lines)},
                )
        else:
            if event_callback:
                event_callback("warning", "豆包事实抽取未产出合格行", {"url": document.url, "title": document.title})
        processed += 1
        if progress_callback:
            progress_callback(processed, f"已处理互联网资料：{document.title[:40]}")
    project_text, remaining_user_required = build_project_enrichment_markdown(
        title=title,
        target_type=target_type,
        target_id=target_id,
        documents=accepted_documents,
        fact_cards=fact_cards,
        gaps=gaps,
        generated_at=generated_at,
    )
    result.remaining_user_required_gaps = remaining_user_required
    if documents or fact_cards or gaps:
        project_origin = hashlib.sha256(f"{client_id}:{target_type}:{target_id}:{reason}".encode("utf-8")).hexdigest()[:20]
        project_upserted = upsert_canonical_text_document(
            db,
            data_dir=data_dir,
            client_id=client_id,
            canonical_kind="project_enrichment_doc",
            origin_type="internet_enrichment",
            origin_id=project_origin,
            title=title,
            text=project_text,
            visible_category="项目补全资料",
            secondary_category="互联网补全",
            created_at=generated_at,
            updated_at=generated_at,
            source_entity_type=target_type or "client",
            source_entity_id=target_id or client_id,
            content_domain=content_domain_override,
        )
        if project_upserted:
            result.project_doc_count = 1
    result.failed_count = max(0, result.crawled_count - result.source_doc_count)

    # 主干: 抓取结束 → 异步触发字典 Stage 1 (LLM candidate generation).
    # 实测 Stage 1 单次 LLM 调用 5-10 分钟, 不能阻塞爬虫主流程
    # (否则 internet_enrichment job 看起来"卡死"几分钟没反馈).
    # 改成 threading.Thread daemon, 让 Stage 1 在后台跑,
    # 用户看到的反馈是"互联网抓取完成", 几分钟后字典 pending 数字自然变化.
    try:
        gloss_count = int(db.fetchone(
            "SELECT COUNT(*) AS n FROM glossary_attributes WHERE client_id = ?",
            (client_id,),
        )["n"])
        if result.source_doc_count >= 3 and gloss_count < 20 and ai_service is not None:
            if event_callback:
                event_callback(
                    "info",
                    "互联网补全后异步触发字典 Stage 1",
                    {"glossaryCountBefore": gloss_count, "sourceDocCount": result.source_doc_count},
                )

            def _run_stage1_and_3_in_background() -> None:
                # daemon thread; 不引用闭包外 logger, 自己导入
                import logging as _logging
                _log = _logging.getLogger("app.services.internet_crawler")
                # Stage 1: term 主表生成 (compact 100s)
                try:
                    from app.services.glossary_candidate_generator import generate_glossary_candidates
                    s1 = generate_glossary_candidates(
                        db, ai_service, client_id,
                        persist=True, compact=True,
                        timeout_seconds=180.0, max_tokens=4500,
                    )
                    _log.info(
                        "[internet-enrichment] Stage 1 done: status=%s terms=%d persisted=%d",
                        s1.get("status", "?"), len(s1.get("terms", [])), s1.get("persisted", 0),
                    )
                except Exception as exc:  # noqa: BLE001
                    _log.warning("[internet-enrichment] Stage 1 failed: %s", exc)
                    return
                # Stage 3: 字典属性值填充 (compact 120s)
                # 关键: 这步把"term.attribute = value" 三元组写入 glossary_attributes pending,
                # 用户在工作台审一下就变 verified, fill_table_evaluator 命中率会跳起来.
                try:
                    from app.services.glossary_attribute_extractor import extract_candidates
                    s3 = extract_candidates(
                        db, ai_service, client_id,
                        compact=True, timeout_seconds=240.0, max_tokens=8000,
                    )
                    _log.info(
                        "[internet-enrichment] Stage 3 done: ok=%s inserted=%d reason=%s",
                        s3.get("ok"), s3.get("inserted", 0), s3.get("reason", "")[:80],
                    )
                except Exception as exc:  # noqa: BLE001
                    _log.warning("[internet-enrichment] Stage 3 failed: %s", exc)

            import threading
            threading.Thread(target=_run_stage1_and_3_in_background, daemon=True).start()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[internet-enrichment] Stage 1 trigger setup failed: %s", exc)

    if event_callback:
        event_callback(
            "info",
            "互联网资料补全完成",
            {
                "crawledCount": result.crawled_count,
                "sourceDocCount": result.source_doc_count,
                "factCardCount": result.fact_card_count,
                "projectDocCount": result.project_doc_count,
                "remainingUserRequiredGaps": result.remaining_user_required_gaps,
            },
        )
    return result
