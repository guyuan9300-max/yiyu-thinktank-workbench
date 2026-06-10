"""公益机构权威源 seed 发现器.

为什么需要这个模块：
  internet_crawler.py 原本用 Bing RSS 搜，但 Bing RSS 现在返回的是百度百科 / 披萨店
  这种无关结果。本模块用 public_search (360/搜狗/Bing HTML) 找候选 URL,
  并主动识别"权威源"和"官网信息公开二级页"，确保抓到登记信息 + 年报 + 财务数据。

设计原则：
  - 权威源优先：百科 (搜狗/百度) / 民政平台 (cszg.mca / gdnpo.gov.cn) / 南都基金会等
  - 官网识别：搜索结果命中客户名 + 域名含 .org/.com 且非新闻/微信链接
  - 二级页发现：官网 HTML 里有"信息公开/章程/审计/年报/年刊/工作报告/管理制度"这些
    导航链接，必须主动加入种子(否则 max_depth 默认只能跟一级链接, 抓不到具体年报详情页)
"""
from __future__ import annotations

import logging
import re
from typing import Callable
from urllib.parse import urljoin, urlparse

from app.services.public_search import PublicSearchResult, search_public_web

logger = logging.getLogger(__name__)


# 关键词：链接 anchor 文字里出现这些 → 这是机构信息公开类二级页, 必抓
SECONDARY_PAGE_KEYWORDS: tuple[str, ...] = (
    "信息公开", "章程", "管理制度", "财务制度",
    "年报", "年度报告", "年刊", "审计报告", "工作报告",
    "公示", "公示信息", "款物", "款物收支",
    "组织架构", "机构介绍", "关于", "简介",
    "捐赠", "捐赠人",
)

# 权威源域名（命中即为 L1，优先抓取）
AUTHORITY_DOMAINS: tuple[str, ...] = (
    "cszg.mca.gov.cn",          # 慈善中国 - 全国慈善信息公开平台
    "mca.gov.cn",               # 民政部
    "gdnpo.gov.cn",             # 广东省非营利组织信息公开平台
    "tyjg.gov.cn",              # 类似省级平台
    "naradafoundation.org",     # 南都基金会(行业公认结构化好)
    "foundationcenter.org.cn",  # 基金会中心网
    "fjcsh.gov.cn",             # 福建慈善
    "shanghaifoundation.org",
    "baike.sogou.com",
    "baike.baidu.com",
    "bnu1.org",                 # 北师大公益研究院
)

# 排除域名（典型噪音）
EXCLUDE_DOMAINS: tuple[str, ...] = (
    "mp.weixin.qq.com",
    "weixin.qq.com",
    "so.html5.qq.com",
    "weibo.com",
    "toutiao.com",
    "bilibili.com",
    "tieba.baidu.com",
)

# 新闻/媒体/聚合域名 — 不能当"客户官网"识别. 它们可能含客户报道,
# 但本身页面充斥头条/推荐/sidebar 等噪音, 跟进二级页会带回大量无关内容.
NEWS_AND_AGGREGATOR_DOMAINS: tuple[str, ...] = (
    "163.com", "qq.com", "sina.com.cn", "sohu.com", "ifeng.com",
    "thepaper.cn", "people.com.cn", "xinhuanet.com", "chinanews.com",
    "chinadaily.com.cn", "news.cn", "guancha.cn", "huanqiu.com",
    "jianshu.com", "zhihu.com", "csdn.net", "douban.com",
    "163.com.cn", "qq.com.cn",
    "baidu.com", "so.com", "sogou.com", "bing.com",  # 搜索引擎本身
    "qichamao.com", "tianyancha.com", "qcc.com", "qichacha.com",  # 工商查询 (单独处理,作为 SEMI 权威源)
)


def _is_news_or_aggregator(url: str) -> bool:
    u = url.lower()
    return any(d in u for d in NEWS_AND_AGGREGATOR_DOMAINS)


class AuthoritySeedDiscovery:
    """权威源 seed 发现结果."""

    def __init__(self) -> None:
        self.authority_urls: list[str] = []  # 百科 / 民政平台 / 行业平台
        self.official_homepages: list[str] = []  # 客户官网首页候选
        self.disclosure_pages: list[str] = []  # 官网"信息公开"类二级页
        self.media_urls: list[str] = []  # 媒体报道


def _is_excluded(url: str) -> bool:
    u = url.lower()
    return any(d in u for d in EXCLUDE_DOMAINS)


def _is_authority(url: str) -> bool:
    u = url.lower()
    return any(d in u for d in AUTHORITY_DOMAINS)


def _looks_like_official_homepage(url: str, title: str, client_name: str) -> bool:
    """判断这条搜索结果是否像客户官网首页.

    严格启发式 (基于实测对测试机构B误判 163.com/sohu.com 导致噪音):
    - 域名既不是权威源也不是噪音也不是新闻/聚合站
    - 标题含客户名 (优先) 或 域名特征 + 客户全名命中
    - URL 路径短(<=4 段)
    """
    if _is_excluded(url) or _is_authority(url) or _is_news_or_aggregator(url):
        return False
    domain = urlparse(url).netloc.lower()
    if not domain:
        return False
    path = urlparse(url).path
    seg_count = len([p for p in path.split("/") if p])
    if seg_count > 4:
        return False
    title_l = (title or "").lower()
    cname_l = (client_name or "").lower()
    # 标题里直接出现客户名是最可靠的官网信号
    if cname_l and cname_l in title_l:
        return True
    # 域名内含 foundation/ngo/charity + 标题里含明确"官网"标记
    return any(k in domain for k in ("foundation", "ngo", "charity", "gongyi")) and any(
        marker in title_l for marker in ("官网", "官方", "首页")
    )


def _extract_disclosure_links(homepage_html: str, base_url: str) -> list[str]:
    """从官网 HTML 抽出"信息公开/章程/年报"类二级页 URL."""
    out: set[str] = set()
    # 匹配 <a href="X">anchor</a> 模式
    for m in re.finditer(r'<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', homepage_html):
        href = m.group(1).strip()
        anchor = m.group(2).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        if not any(k in anchor for k in SECONDARY_PAGE_KEYWORDS):
            continue
        try:
            absu = urljoin(base_url, href)
            parsed = urlparse(absu)
            if not parsed.netloc:
                continue
            # 只要同域
            if parsed.netloc.lower() != urlparse(base_url).netloc.lower():
                continue
            out.add(absu)
        except Exception:  # noqa: BLE001
            continue
    return sorted(out)


def _expand_client_name_candidates(client_name: str, ai: Any | None = None) -> list[str]:
    """把客户简称扩展成多个候选全称.

    背景: 实测发现 7 客户中 3 个 (测试机构C/士平/测试论坛A) 用注册简称在搜索引擎上找不到内容,
    但用全称 "测试机构C" 可以. 客户在数据库里录入名字时往往用日常简称,
    爬虫层应该有能力补全成"官方注册可能的全称"集合, 用全称去搜.

    机制 (不硬编码):
      1. 原名直接保留 (兼容已知客户)
      2. 用 LLM 推测可能的官方注册全称, 输出多个候选 (例: 测试机构C → 测试机构C / 测试机构C)
      3. 加常见后缀变体 (基金会/公益基金会/慈善基金会/服务中心)
    """
    name = (client_name or "").strip()
    if not name:
        return []
    candidates = [name]
    # 启发式 1: 已经含官方后缀, 不扩展
    if any(suf in name for suf in ("基金会", "服务中心", "公益服务中心")):
        # 还是补 "广东省 X" / "上海 X" 等省级前缀变体 (因为搜索引擎对带省份的命中率更高)
        bare = name
        for suf in ("公益基金会", "基金会", "公益服务中心", "服务中心"):
            if bare.endswith(suf):
                bare = bare[: -len(suf)]
                break
        if bare and len(bare) >= 2:
            for province_prefix in ("广东省", "上海市", "北京市", "贵州省"):
                full = f"{province_prefix}{bare}{name[len(bare):]}"
                if full not in candidates:
                    candidates.append(full)
        return candidates[:5]

    # 启发式 2: 客户名不含官方后缀, 启动 LLM 推测全称
    if ai is not None and hasattr(ai, "_qwen_generate"):
        try:
            prompt = f"""客户在系统里录入的名字: "{name}"

这是个公益/基金会客户的日常简称, 请推测它在民政部门官方注册可能的全称.

要求:
1. 列出 2-4 个最可能的全称候选 (含省级前缀 + 完整后缀)
2. 不要硬编码 — 不知道就少给, 不要乱猜
3. 如果原名已经看起来像全称, 返回原名一个就够

严格 JSON 数组输出, 例: ["广东省{name}公益基金会","上海市{name}慈善基金会"]

只输出 JSON 数组, 不要其他文字."""
            result = ai._qwen_generate(  # noqa: SLF001
                prompt, "你是公益机构注册信息专家. 只输出 JSON 数组.", None,
                timeout_seconds=30.0, max_tokens=300, temperature=0.2,
            )
            extra = []
            if isinstance(result, list):
                extra = [str(x).strip() for x in result if isinstance(x, str) and x.strip()]
            elif isinstance(result, str):
                import json as _json
                try:
                    parsed = _json.loads(result)
                    if isinstance(parsed, list):
                        extra = [str(x).strip() for x in parsed if isinstance(x, str) and x.strip()]
                except (ValueError, _json.JSONDecodeError):
                    pass
            for x in extra:
                if x and x not in candidates and 4 <= len(x) <= 40:
                    candidates.append(x)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[authority-seeds] LLM expand name failed: %s", exc)

    # 启发式 3: 兜底加常见后缀
    if len(candidates) == 1:
        for suf in ("公益基金会", "基金会", "慈善基金会"):
            full = f"{name}{suf}"
            if full not in candidates:
                candidates.append(full)

    return candidates[:5]


def discover_authority_seeds(
    client_name: str,
    *,
    fetcher: Callable[[str], object] | None = None,
    max_search_per_query: int = 6,
    search_timeout: float = 12.0,
    ai: Any | None = None,
) -> AuthoritySeedDiscovery:
    """构造 seed URL 集合：权威源 + 官网首页 + 信息公开二级页 + 媒体报道.

    实测对"测试机构A"返回约 18-25 个高价值 URL, 覆盖：
      - 搜狗百科条目 (含成立时间/性质/注册机关等结构化字段)
      - 官网首页 + 7-8 个"信息公开"二级页 (含历年年报/审计报告标题列表)
      - 南都基金会条目 / 行业评估文章
      - 网易/搜狐媒体报道 (项目细节)

    新增 (G 任务): ai 参数. 客户名是简称时 LLM 扩展成候选全称, 用全称去搜.
    实测对"测试机构C/士平/测试论坛A"这种名字模糊客户, 从 0-4 篇 → 期望 15+ 篇.
    """
    name = (client_name or "").strip()
    out = AuthoritySeedDiscovery()
    if not name:
        return out

    # 客户名扩展 (G 任务): "测试机构C" → ["测试机构C", "测试机构C", ...]
    name_candidates = _expand_client_name_candidates(name, ai)
    logger.info("[authority-seeds] '%s' 扩展候选: %s", name, name_candidates)

    # 多视角查询: 主名(原名+扩展全称) × 视角 (官网/年报/信息公开等)
    queries: list[str] = []
    for nm in name_candidates:
        queries.append(nm)
        queries.append(f"{nm} 官网")
        queries.append(f"{nm} 年报")
        queries.append(f"{nm} 信息公开")
    # 限总查询数避免被搜索引擎限流
    queries = queries[:12]

    collected: list[PublicSearchResult] = []
    seen_urls: set[str] = set()
    for q in queries:
        try:
            results = search_public_web(q, max_results=max_search_per_query, timeout_seconds=search_timeout)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[authority-seeds] search '%s' failed: %s", q, exc)
            continue
        for r in results:
            if not r.url or r.url in seen_urls:
                continue
            if _is_excluded(r.url):
                continue
            seen_urls.add(r.url)
            collected.append(r)

    # 分类
    for r in collected:
        if _is_authority(r.url):
            out.authority_urls.append(r.url)
        elif _looks_like_official_homepage(r.url, r.title, name):
            out.official_homepages.append(r.url)
        else:
            out.media_urls.append(r.url)

    # 去重 (保序)
    out.authority_urls = list(dict.fromkeys(out.authority_urls))
    out.official_homepages = list(dict.fromkeys(out.official_homepages))
    out.media_urls = list(dict.fromkeys(out.media_urls))

    # 对每个官网首页：抓 HTML, 发现"信息公开"二级页
    if fetcher and out.official_homepages:
        for home in out.official_homepages[:3]:  # 最多探测 3 个官网候选
            try:
                fetched = fetcher(home)
                if not fetched:
                    continue
                html = getattr(fetched, "text", None) or ""
                if not html:
                    continue
                disc = _extract_disclosure_links(html, home)
                out.disclosure_pages.extend(disc)
                logger.info(
                    "[authority-seeds] homepage=%s 发现信息公开二级页 %d 个", home, len(disc),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("[authority-seeds] homepage fetch %s failed: %s", home, exc)
    out.disclosure_pages = list(dict.fromkeys(out.disclosure_pages))

    return out


def build_seed_url_list(discovery: AuthoritySeedDiscovery, *, max_total: int = 30) -> list[str]:
    """把发现结果展平成 internet_crawler 接受的 seed_urls 列表, 权威源在前."""
    seeds: list[str] = []
    # 顺序：权威源 (百科 + 民政) > 官网首页 + 信息公开二级页 > 媒体
    seeds.extend(discovery.authority_urls)
    seeds.extend(discovery.official_homepages)
    seeds.extend(discovery.disclosure_pages)
    seeds.extend(discovery.media_urls)
    # 去重保序
    seeds = list(dict.fromkeys(seeds))
    return seeds[:max_total]
