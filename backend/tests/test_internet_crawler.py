from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.db import Database
from app.main import create_app
from app.services.internet_crawler import (
    FetchedContent,
    InternetCrawlOptions,
    InternetEnrichmentResult,
    classify_source_domain,
    clean_html_to_markdown,
    crawl_internet_sources,
    extract_fact_lines_with_doubao,
    run_internet_enrichment,
)


def _insert_client(db: Database, client_id: str, name: str = "为爱黔行") -> None:
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, created_at, updated_at)
        VALUES(?, ?, ?, '公益', '项目客户', '互联网补全测试客户', '推进中', '2026-04-01T00:00:00', '2026-04-01T00:00:00')
        """,
        (client_id, name, name),
    )


def _weiai_fetcher(url: str) -> FetchedContent | None:
    pages = {
        "https://www.weiaiqianxing.cn": """
            <html><body>
              <nav>首页 Home 关于我们 About 项目展示 projects 联系我们</nav>
              <a href="/sys-nd/29.html">大山里的音乐课堂公益项目启动</a>
              <a href="/sys-nd/31.html">乡村音乐教师培训回访</a>
              <a href="/contact.html">联系我们</a>
              <main>为爱黔行长期关注贵州山区儿童成长与乡村美育支持。</main>
            </body></html>
        """,
        "https://www.weiaiqianxing.cn/sys-nd/29.html": """
            <html>
              <head><title>大山里的音乐课堂公益项目启动</title></head>
              <body>
                <header>首页 Home 关于我们 About</header>
                <h1>大山里的音乐课堂公益项目启动</h1>
                <p>发布时间：2024-05-12</p>
                <p>为爱黔行联合合作伙伴在贵州山区学校推进音乐课堂建设，目标是补足乡村学校美育资源。</p>
                <p>项目内容包括音乐教室改造、教师培训、课程资源支持和学生展示活动。</p>
                <p>项目评估关注学生参与度、教师持续使用情况、课程开设频次和学校后续维护能力。</p>
                <p>资料还记录了项目执行需要结合学校基础设施、教师排课条件、学生参与时间和本地公益伙伴支持能力来推进。</p>
                <p>这些内容可以作为立项评审中项目方法、执行路径和成效指标设计的基础材料。</p>
              </body>
            </html>
        """,
        "https://www.weiaiqianxing.cn/sys-nd/31.html": """
            <html>
              <head><title>乡村音乐教师培训回访</title></head>
              <body>
                <h1>乡村音乐教师培训回访</h1>
                <p>发布时间：2024-09-20</p>
                <p>项目团队对受益学校开展回访，记录音乐课堂开课、教师备课和学生社团活动情况。</p>
                <p>后续需要继续补充拟走访学校名单、项目预算和捐赠人核心诉求。</p>
                <p>回访信息可帮助判断项目是否具备持续运营条件，也能提示后续签约、改造和传播材料的补充方向。</p>
                <p>学校案例、课程执行记录和教师反馈会直接影响项目成效评估的可信度。</p>
              </body>
            </html>
        """,
    }
    normalized = url.rstrip("/")
    if "bing.com/search" in normalized:
        return FetchedContent(url=url, status_code=200, content_type="application/rss+xml", text="<rss><channel></channel></rss>")
    html = pages.get(normalized)
    if html is None:
        return None
    return FetchedContent(url=normalized, status_code=200, content_type="text/html; charset=utf-8", text=html)


class FakeDoubao:
    def _qwen_generate(self, *, prompt: str, system_instruction: str, response_schema=None, timeout_seconds=30.0, max_tokens=800):
        if "是否值得进入项目资料库" in prompt:
            return "YES: 与项目资料缺口直接相关"
        return "\n".join(
            [
                "FACT: 为爱黔行在贵州山区学校推进音乐课堂建设。",
                "NUMBER: 评估可关注学生参与度、课程开设频次和教师持续使用情况。",
                "TIME: 资料显示项目相关动态发布于 2024 年。",
                "GAP: 仍需补充拟走访学校名单和项目预算。",
                "这行没有合格前缀，应该被丢弃。",
            ]
        )


def test_clean_html_to_markdown_removes_navigation_and_keeps_project_content() -> None:
    html = """
    <html><body>
      <nav>首页 Home 关于我们 About 项目展示 projects</nav>
      <script>window.__DATA__ = true</script>
      <h1>大山里的音乐课堂</h1>
      <p>大山里的音乐课堂关注乡村学校美育资源不足的问题。</p>
      <p>贵公网安备 123456</p>
    </body></html>
    """

    markdown = clean_html_to_markdown(html, source_url="https://www.weiaiqianxing.cn/sys-nd/29.html")

    assert "大山里的音乐课堂关注乡村学校美育资源不足" in markdown
    assert "首页 Home" not in markdown
    assert "贵公网安备" not in markdown
    assert "window.__DATA__" not in markdown


def test_crawl_seed_url_discovers_weiaiqianxing_detail_pages() -> None:
    documents = crawl_internet_sources(
        seed_urls=["https://www.weiaiqianxing.cn/"],
        seed_queries=[],
        gaps=["大山里的音乐课堂", "乡村美育成效指标"],
        options=InternetCrawlOptions(max_pages=8, max_depth=1, min_text_chars=40),
        fetcher=_weiai_fetcher,
    )

    urls = {item.url for item in documents}
    assert "https://www.weiaiqianxing.cn/sys-nd/29.html" in urls
    assert "https://www.weiaiqianxing.cn/sys-nd/31.html" in urls
    assert all("contact" not in item.url for item in documents)
    assert any(item.credibility_level == "L1" for item in documents)


def test_crawl_dedupes_same_url_and_same_content_hash() -> None:
    def fetcher(url: str) -> FetchedContent | None:
        if "bing.com/search" in url:
            return FetchedContent(url=url, status_code=200, content_type="application/rss+xml", text="<rss><channel></channel></rss>")
        html = """
            <html><body>
              <a href="/sys-nd/29.html">重复详情</a>
              <a href="/sys-nd/30.html">重复详情副本</a>
              <h1>重复资料</h1>
              <p>这是一段足够长的互联网项目资料正文，用来验证同正文 hash 不会重复进入资料库。</p>
            </body></html>
        """
        final_url = url.rstrip("/")
        if final_url.endswith("/sys-nd/29.html") or final_url.endswith("/sys-nd/30.html") or final_url == "https://www.weiaiqianxing.cn":
            return FetchedContent(url=final_url, status_code=200, content_type="text/html", text=html)
        return None

    documents = crawl_internet_sources(
        seed_urls=["https://www.weiaiqianxing.cn/"],
        gaps=["重复资料"],
        options=InternetCrawlOptions(max_pages=8, max_depth=1, min_text_chars=20),
        fetcher=fetcher,
    )

    hashes = [item.content_hash for item in documents]
    assert len(hashes) == len(set(hashes))


def test_fact_extraction_requires_fact_number_time_gap_prefixes() -> None:
    documents = crawl_internet_sources(
        seed_urls=["https://www.weiaiqianxing.cn/sys-nd/29.html"],
        gaps=["大山里的音乐课堂"],
        options=InternetCrawlOptions(max_pages=1, max_depth=0, min_text_chars=40),
        fetcher=_weiai_fetcher,
    )

    fact_lines = extract_fact_lines_with_doubao(FakeDoubao(), document=documents[0], current_date="2026-05-03")

    assert fact_lines
    assert all(line.startswith(("FACT:", "NUMBER:", "TIME:", "GAP:")) for line in fact_lines)
    assert not any("没有合格前缀" in line for line in fact_lines)


def test_run_internet_enrichment_materializes_source_fact_and_project_docs(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    client_id = "client_weiai"
    _insert_client(db, client_id)

    result = run_internet_enrichment(
        db,
        data_dir=tmp_path / "data",
        client_id=client_id,
        ai_service=FakeDoubao(),
        payload={
            "targetType": "task",
            "targetId": "task_music_classroom",
            "seedUrls": ["https://www.weiaiqianxing.cn/"],
            "seedQueries": [],
            "gaps": ["乡村音乐课堂案例", "拟走访学校名单", "项目预算"],
            "maxPages": 8,
            "maxDepth": 1,
            "reason": "test",
            "title": "为爱黔行：大山里的音乐课堂互联网补全",
        },
        fetcher=_weiai_fetcher,
    )

    assert result.source_doc_count >= 2
    assert result.fact_card_count >= 1
    assert result.project_doc_count == 1
    assert "拟走访学校名单" in result.remaining_user_required_gaps

    rows = db.fetchall("SELECT canonical_kind, markdown_content FROM v2_documents WHERE client_id = ?", (client_id,))
    kinds = {str(row["canonical_kind"]) for row in rows}
    assert "internet_fact_card" in kinds
    assert "project_enrichment_doc" in kinds
    assert kinds & {"internet_source_doc", "evaluation_reference_doc", "similar_case_doc", "policy_context_doc"}
    all_markdown = "\n".join(str(row["markdown_content"] or "") for row in rows)
    assert "来源链接：https://www.weiaiqianxing.cn/sys-nd/29.html" in all_markdown
    assert "可信度等级：L1" in all_markdown
    assert "## 仍需用户补充" in all_markdown


def test_classify_source_domain_levels() -> None:
    assert classify_source_domain("https://www.weiaiqianxing.cn/sys-nd/29.html")[1] == "L1"
    assert classify_source_domain("https://www.moe.gov.cn/srcsite/test.html")[1] == "L1"
    assert classify_source_domain("https://www.news.cn/local/2024/test.html")[1] == "L2"
    assert classify_source_domain("https://example.org/case-study")[1] == "L3"


def test_readiness_action_queues_internet_enrichment_job(tmp_path: Path, monkeypatch) -> None:
    def fake_run_internet_enrichment(*args: Any, **kwargs: Any) -> InternetEnrichmentResult:
        return InternetEnrichmentResult(crawled_count=1, source_doc_count=1, fact_card_count=0, project_doc_count=1)

    monkeypatch.setattr(app_main, "run_internet_enrichment", fake_run_internet_enrichment)
    app = create_app(tmp_path / "data")
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/clients",
            json={
                "name": "为爱黔行",
                "alias": "为爱黔行",
                "domain": "公益",
                "type": "项目客户",
                "intro": "用于互联网补全队列测试",
                "stage": "推进中",
            },
        )
        assert created.status_code == 200
        client_id = created.json()["id"]

        response = client.post(
            f"/api/v1/clients/{client_id}/workspace/data-center-readiness/actions",
            json={
                "actionType": "internet_enrichment",
                "seedUrls": ["https://www.weiaiqianxing.cn/"],
                "seedQueries": ["为爱黔行 大山里的音乐课堂"],
                "gaps": ["项目方法", "成效指标", "拟走访学校名单"],
                "maxPages": 5,
                "maxDepth": 1,
                "targetType": "task",
                "targetId": "task_music_classroom",
                "title": "为爱黔行互联网补全测试",
            },
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["status"] == "queued"
        assert payload["jobId"]

        row = client.app.state.app_state.db.fetchone("SELECT job_type, payload_json FROM knowledge_jobs WHERE id = ?", (payload["jobId"],))
        assert row is not None
        assert row["job_type"] == "internet_enrichment"
        assert "为爱黔行 大山里的音乐课堂" in row["payload_json"]
        assert "task_music_classroom" in row["payload_json"]
