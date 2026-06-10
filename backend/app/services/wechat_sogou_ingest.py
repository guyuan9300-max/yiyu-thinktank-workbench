"""微信公众号自动收录 · 搜狗翻页路径 (P13-E5).

策略 (临时-够用方案, 等 RSSHub 部署后切到全文):
  1. 调 search_wechat_pages 翻 1..N 页, 每页 10 条
  2. 每条结果 = (title + snippet + 公众号名 + 发布时间) → 200-500 字摘要
  3. 包装成 markdown 入库 v2_documents + documents (content_domain='brand_official_corpus')
  4. 用 sogou link 的稳定 hash 做 origin_id, 重复跑不会重复入库 (幂等)

边界:
  - 搜狗 link?url= 跳转被 antispider 挡死 → 拿不到 mp.weixin.qq.com 全文
  - 单次抓取覆盖最近 ~50 条公众号文章 (>50 后翻页失败率上升)
  - 标题+摘要对品牌画像约 70% 够用; 全文要等 RSSHub 路径
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from app.db import Database, to_json
from app.services.internet_crawler import now_iso
from app.services.multi_platform_search import search_wechat_pages

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WechatSogouIngestResult:
    """单次入库结果摘要."""

    client_id: str
    query: str
    pages_fetched: int
    raw_results: int
    new_documents: int
    skipped_existing: int
    skipped_off_topic: int
    document_ids: list[str]


_GENERIC_ORG_SUFFIXES = (
    "公益基金会",
    "慈善基金会",
    "基金会",
    "公益协会",
    "公益促进会",
    "慈善会",
    "促进会",
    "协会",
    "学会",
    "联合会",
    "服务中心",
    "中心",
    "研究院",
    "研究中心",
)


def _extract_unique_keyword(client_name: str) -> str:
    """从客户名抽"独特子串"用于公众号结果过滤.

    搜狗对长 query "测试机构A" 会把"基金会"这个泛词单独命中, 导致 70%+ 污染.
    剥掉客户名末尾的通用后缀, 剩下的核心字符 (例 "测试机构A" / "南都" / "壹基金") 才是
    强相关信号. 若剥光后剩 < 2 字符, 退回原名.
    """
    name = (client_name or "").strip()
    if not name:
        return ""
    for suffix in _GENERIC_ORG_SUFFIXES:
        if name.endswith(suffix) and len(name) > len(suffix) + 1:
            stripped = name[: -len(suffix)].strip()
            if len(stripped) >= 2:
                return stripped
    return name


def _is_relevant_to_client(
    title: str, snippet: str, *, keyword: str, aliases: list[str]
) -> bool:
    """title 或 snippet 必须命中 keyword 或任一别名才算相关.

    搜狗结果带空格分词 (例 "测试机构A 公益 基金会"), 这里搜索的是
    "测试机构A" 这种纯连字串, 自动跨过空格.
    """
    haystack_raw = f"{title or ''}\n{snippet or ''}"
    haystack_normalized = haystack_raw.replace(" ", "").replace("　", "")
    keyword_clean = (keyword or "").strip().replace(" ", "")
    candidates: list[str] = []
    if keyword_clean:
        candidates.append(keyword_clean)
    for alias in aliases or []:
        alias_clean = (alias or "").strip().replace(" ", "")
        if alias_clean and alias_clean not in candidates:
            candidates.append(alias_clean)
    return any(candidate in haystack_normalized for candidate in candidates if candidate)


def _stable_origin_id(*, title: str, author: str) -> str:
    """同一篇公众号文章, 用 (title + author) 做稳定 hash.

    sogou /link?url=... 含 nonce, 每次搜索返回的 url 都不同, 所以不能用 URL hash.
    title 在搜狗结果里是带空格分词的 ('测试机构A 公益 基金会 ...'), 这里 normalize 掉空格后再 hash.
    """
    title_norm = re.sub(r"\s+", "", (title or "").strip())
    author_norm = re.sub(r"\s+", "", (author or "").strip())
    return "wxsogou_" + hashlib.sha256(
        f"{title_norm}|{author_norm}".encode("utf-8")
    ).hexdigest()[:16]


def _build_markdown(
    *,
    title: str,
    sogou_url: str,
    snippet: str,
    author: str,
    crawled_at: str,
) -> str:
    """把搜狗结果包装成结构化 markdown (跟 internet_crawler 出来的格式风格一致).

    LLM 画像生成时会读 v2_documents.markdown_content, 这里的格式直接决定画像质量.
    """
    safe_snippet = (snippet or "").strip()
    parts = [
        f"# {title}",
        "",
        "## 来源元数据",
        f"- 来源类型：微信公众号 (搜狗搜索抓取, 标题+摘要)",
        f"- 公众号：{author}",
        f"- 搜狗跳转链接：{sogou_url}",
        f"- 抓取时间：{crawled_at}",
        "- 说明：受搜狗 antispider 限制, 此条目仅保留标题+摘要, 不含全文",
        "",
        "## 标题",
        title,
        "",
        "## 摘要",
        safe_snippet or "(搜狗未返回摘要)",
    ]
    return "\n".join(parts).strip()


def run_wechat_sogou_ingest(
    db: Database,
    *,
    client_id: str,
    client_name: str,
    max_pages: int = 5,
    per_page: int = 10,
    extra_query_aliases: list[str] | None = None,
) -> WechatSogouIngestResult:
    """同步跑一次搜狗微信翻页抓取 → 入库 brand_official_corpus.

    extra_query_aliases: 客户的常用别名 (例 ['测试机构A', '测试机构A']),
        会用 ' OR ' 风格逐别名各翻一遍, 跨别名去重. 不传则只用 client_name 单查.
    """
    if not client_name.strip():
        raise ValueError("client_name 必填 (用于构造搜狗 query)")

    queries: list[str] = [client_name.strip()]
    for alias in extra_query_aliases or []:
        alias_clean = (alias or "").strip()
        if alias_clean and alias_clean not in queries:
            queries.append(alias_clean)

    # 关键: 抽客户名独特子串. "测试机构A" → "测试机构A" 防搜狗对"基金会"泛词污染.
    unique_keyword = _extract_unique_keyword(client_name)

    seen_origin_ids: set[str] = set()
    all_raw: list[tuple[str, str, str, str]] = []  # (title, sogou_url, snippet, author)
    skipped_off_topic = 0
    pages_fetched = 0
    for query in queries:
        page_results = search_wechat_pages(
            query, max_pages=max_pages, per_page=per_page, timeout_seconds=15.0
        )
        pages_fetched += max_pages  # 估算, search_wechat_pages 内部会提前结束
        for result in page_results:
            sogou_url = result.url
            if not sogou_url or "weixin.sogou.com" not in sogou_url:
                continue
            # 严格相关性: title 或 snippet 必须含独特关键词 ("测试机构A") 或客户全名/别名
            if not _is_relevant_to_client(
                result.title,
                result.snippet,
                keyword=unique_keyword,
                aliases=[client_name, *(extra_query_aliases or [])],
            ):
                skipped_off_topic += 1
                continue
            author = ""
            if result.source and "·" in result.source:
                author = result.source.split("·", 1)[1].strip()
            author = author or "公众号"
            origin_id = _stable_origin_id(title=result.title, author=author)
            if origin_id in seen_origin_ids:
                continue
            seen_origin_ids.add(origin_id)
            all_raw.append((result.title, sogou_url, result.snippet, author))

    now = now_iso()
    inserted: list[str] = []
    skipped_existing = 0
    for title, sogou_url, snippet, author in all_raw:
        origin_id = _stable_origin_id(title=title, author=author)
        doc_id = f"doc_internet_{origin_id}"
        # 幂等: 跨 ingest 重复跑也只插入一次.
        existing = db.fetchone("SELECT id FROM documents WHERE id = ?", (doc_id,))
        if existing:
            skipped_existing += 1
            continue
        markdown = _build_markdown(
            title=title,
            sogou_url=sogou_url,
            snippet=snippet,
            author=author,
            crawled_at=now,
        )
        excerpt = (snippet or title)[:480]
        content_hash = hashlib.sha256(markdown.encode("utf-8")).hexdigest()

        db.execute(
            """INSERT INTO documents(
                id, client_id, folder_id, title, path, original_source_path, kind, source, excerpt, tags_json, created_at,
                document_family_id, canonical_kind, origin_type, origin_id, is_searchable,
                organization_id, department_id, department_ids_json, owner_user_id, source_entity_type, source_entity_id,
                visibility_scope, content_domain, lifecycle_status,
                published_at, source_fetched_at, source_revision_no
            ) VALUES(?, ?, NULL, ?, ?, ?, 'wechat_excerpt', 'wechat_sogou_search', ?, ?, ?,
                     ?, 'wechat_article_excerpt', 'wechat_sogou_search', ?, 1,
                     '', '', '[]', '', 'internet_source', ?,
                     'project_public', 'brand_official_corpus', 'active',
                     NULL, ?, 1)""",
            (
                doc_id,
                client_id,
                title[:200],
                sogou_url,
                sogou_url,
                excerpt,
                to_json(["wechat_sogou_search", "brand_official_corpus", "title_snippet_only"]),
                now,
                f"family_wechat:{origin_id}",
                origin_id,
                origin_id,
                now,
            ),
        )
        v2_id = f"v2doc_{doc_id}"
        existing_v2 = db.fetchone("SELECT id FROM v2_documents WHERE id = ?", (v2_id,))
        if not existing_v2:
            db.execute(
                """INSERT INTO v2_documents(
                    id, client_id, document_id, original_path, managed_path, markdown_path, file_name, kind,
                    material_layer, visible_category, secondary_category, parse_status, parse_error,
                    preview_text, doc_index_text, content_hash, markdown_content, classification_confidence,
                    document_family_id, canonical_kind, origin_type, origin_id, is_searchable,
                    organization_id, department_id, department_ids_json, owner_user_id,
                    source_entity_type, source_entity_id, visibility_scope, content_domain, lifecycle_status,
                    imported_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'wechat_excerpt', 'evidence', '互联网补充资料', '微信公众号摘要',
                          'completed', NULL, ?, '', ?, ?, 0.85,
                          ?, 'wechat_article_excerpt', 'wechat_sogou_search', ?, 1,
                          '', '', '[]', '',
                          'internet_source', ?, 'project_public', 'brand_official_corpus', 'active',
                          ?, ?)""",
                (
                    v2_id,
                    client_id,
                    doc_id,
                    sogou_url,
                    sogou_url,
                    sogou_url,
                    title[:200],
                    excerpt[:500],
                    content_hash,
                    markdown,
                    f"family_wechat:{origin_id}",
                    origin_id,
                    origin_id,
                    now,
                    now,
                ),
            )
        inserted.append(doc_id)

    db.conn.commit()

    return WechatSogouIngestResult(
        client_id=client_id,
        query=client_name,
        pages_fetched=pages_fetched,
        raw_results=len(all_raw),
        new_documents=len(inserted),
        skipped_existing=skipped_existing,
        skipped_off_topic=skipped_off_topic,
        document_ids=inserted,
    )
