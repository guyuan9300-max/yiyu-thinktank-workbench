from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.db import Database
from app.main import create_app
from app.services.internet_crawler import InternetCrawlOptions, crawl_internet_sources, run_internet_enrichment

OUT = ROOT / "output" / "internet-enrichment-effect-test"
OUT.mkdir(parents=True, exist_ok=True)

seed_urls = ["https://www.weiaiqianxing.cn/"]
seed_queries = ["为爱黔行 大山里的音乐课堂", "为爱黔行 乡村音乐课堂 公益项目"]
gaps = [
    "乡村音乐课堂案例",
    "贵州乡村学校美育资源现状",
    "公益美育成效指标",
    "同类传播案例",
    "拟走访学校名单",
    "项目预算",
    "捐赠人核心诉求",
]

events: list[dict] = []

def event(level: str, message: str, detail: dict | None = None) -> None:
    events.append({"level": level, "message": message, "detail": detail or {}})

start = perf_counter()
documents = crawl_internet_sources(
    seed_urls=seed_urls,
    seed_queries=seed_queries,
    gaps=gaps,
    options=InternetCrawlOptions(max_pages=8, max_depth=1, max_pdfs=3, min_text_chars=160),
    event_callback=event,
)
crawl_seconds = round(perf_counter() - start, 2)

crawl_summary = {
    "elapsedSeconds": crawl_seconds,
    "documentCount": len(documents),
    "documents": [
        {
            "title": doc.title,
            "url": doc.url,
            "chars": len(doc.content),
            "credibilityLevel": doc.credibility_level,
            "canonicalKind": doc.canonical_kind,
            "publishedAt": doc.published_at,
            "firstText": doc.content[:220],
        }
        for doc in documents
    ],
    "events": events[:60],
}
(OUT / "crawler_summary.json").write_text(json.dumps(crawl_summary, ensure_ascii=False, indent=2), encoding="utf-8")

with tempfile.TemporaryDirectory(prefix="internet_enrichment_effect_") as tmp:
    data_dir = Path(tmp) / "data"
    app = create_app(data_dir)
    state = app.state.app_state
    db: Database = state.db
    client_id = "client_effect_weiai"
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, created_at, updated_at)
        VALUES(?, '为爱黔行', '为爱黔行', '公益', '项目客户', '互联网补全效果测试客户', '推进中', '2026-05-03T00:00:00', '2026-05-03T00:00:00')
        """,
        (client_id,),
    )
    ai_health = state.ai.get_health()
    enrichment_events: list[dict] = []
    progress: list[dict] = []

    def enrichment_event(level: str, message: str, detail: dict | None = None) -> None:
        enrichment_events.append({"level": level, "message": message, "detail": detail or {}})

    def enrichment_progress(count: int, message: str) -> None:
        progress.append({"count": count, "message": message})

    start = perf_counter()
    result = run_internet_enrichment(
        db,
        data_dir=data_dir,
        client_id=client_id,
        ai_service=state.ai if ai_health.ready else None,
        payload={
            "clientId": client_id,
            "targetType": "task",
            "targetId": "task_music_classroom_effect_test",
            "seedUrls": seed_urls,
            "seedQueries": seed_queries,
            "gaps": gaps,
            "maxPages": 8,
            "maxDepth": 1,
            "reason": "effect_test",
            "source": "codex_effect_test",
            "title": "为爱黔行：大山里的音乐课堂互联网补全效果测试",
        },
        event_callback=enrichment_event,
        progress_callback=enrichment_progress,
    )
    enrichment_seconds = round(perf_counter() - start, 2)

    rows = db.fetchall(
        """
        SELECT canonical_kind, file_name, LENGTH(markdown_content) AS chars, preview_text, markdown_content
        FROM v2_documents
        WHERE client_id = ?
        ORDER BY updated_at DESC
        """,
        (client_id,),
    )
    doc_rows = [
        {
            "canonicalKind": str(row["canonical_kind"] or ""),
            "title": str(row["file_name"] or ""),
            "chars": int(row["chars"] or 0),
            "preview": str(row["preview_text"] or "")[:240],
        }
        for row in rows
    ]
    project_doc = next((str(row["markdown_content"] or "") for row in rows if str(row["canonical_kind"] or "") == "project_enrichment_doc"), "")
    fact_card_sample = next((str(row["markdown_content"] or "") for row in rows if str(row["canonical_kind"] or "") == "internet_fact_card"), "")
    enrichment_summary = {
        "aiHealth": {
            "provider": ai_health.provider,
            "model": ai_health.model,
            "ready": ai_health.ready,
            "credentialSource": ai_health.credential_source,
            "fingerprint": ai_health.fingerprint,
            "detail": ai_health.detail,
        },
        "elapsedSeconds": enrichment_seconds,
        "result": result.__dict__,
        "storedDocumentCount": len(rows),
        "storedDocuments": doc_rows,
        "events": enrichment_events[:80],
        "progress": progress,
        "projectDocSample": project_doc[:2500],
        "factCardSample": fact_card_sample[:1800],
    }
    (OUT / "enrichment_summary.json").write_text(json.dumps(enrichment_summary, ensure_ascii=False, indent=2), encoding="utf-8")

print(json.dumps({"crawl": crawl_summary, "outputDir": str(OUT)}, ensure_ascii=False, indent=2))
