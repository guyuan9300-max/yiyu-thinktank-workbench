from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("YIYU_WORKBENCH_DATA_DIR", tempfile.mkdtemp(prefix="yiyu-profile-layered-tests-"))

from app.db import Database
from app.db import from_json
from app.db import to_json
from app.models import AiStructuredResponse
from app.services import intelligence_candidate_supply as supply
from app.services.intelligence_candidate_supply import CandidateHit, run_profile_completion_research
from app.services.intelligence_search_intents import GeneratedSearchIntent, IntelligenceSearchScope


def _seed_client(db: Database, *, client_id: str = "client_layered", name: str = "广州样本公益中心") -> None:
    db.execute(
        """
        INSERT OR REPLACE INTO clients(id, name, alias, domain, type, intro, stage, color, created_at, updated_at)
        VALUES(?, ?, ?, '儿童心理健康', 'foundation', '面向困境儿童提供心理健康服务', 'active', '#5B7BFE',
            '2026-05-15T09:00:00', '2026-05-15T09:00:00')
        """,
        (client_id, name, name),
    )


def _scope(client_id: str = "client_layered", name: str = "广州样本公益中心") -> IntelligenceSearchScope:
    return IntelligenceSearchScope(
        scope_type="client",
        scope_id=client_id,
        client_id=client_id,
        project_module_id=None,
        display_name=name,
    )


def _intent(client_id: str, query: str, *, intent_id: str = "intent_layered") -> GeneratedSearchIntent:
    return GeneratedSearchIntent(
        id=intent_id,
        scope_type="client",
        scope_id=client_id,
        client_id=client_id,
        project_module_id=None,
        content_kind="profile_completion",
        query=query,
        exclude_terms=[],
        source_inputs=[f"client:{client_id}", "profile_layered:test"],
        reason="资料补全分层研究测试",
        priority=99,
        status="ready",
        input_hash=f"hash_{intent_id}",
        expires_at="2026-05-16T00:00:00",
    )


def _insert_intent(db: Database, intent: GeneratedSearchIntent) -> None:
    db.execute(
        """
        INSERT INTO intelligence_search_intents(
            id, scope_type, scope_id, client_id, project_module_id, content_kind, query,
            exclude_terms_json, source_inputs_json, reason, priority, status,
            input_hash, expires_at, generator_version, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ready', ?, ?, 'profile-layered-test', ?, ?)
        """,
        (
            intent.id,
            intent.scope_type,
            intent.scope_id,
            intent.client_id,
            intent.project_module_id,
            intent.content_kind,
            intent.query,
            to_json(intent.exclude_terms),
            to_json(intent.source_inputs),
            intent.reason,
            intent.priority,
            intent.input_hash,
            intent.expires_at,
            "2026-05-15T09:00:00",
            "2026-05-15T09:00:00",
        ),
    )


class _ProfileAi:
    def get_health(self):
        return type("Health", (), {"ready": True, "provider": "doubao"})()

    def generate_general_fallback(self, *_args, **_kwargs):
        return AiStructuredResponse(
            content="资料摘要：该页面可用于补充机构定位、儿童心理服务项目和团队能力等资料维度。",
            analysis=(
                "可复用事实：\n"
                "- 广州样本公益中心公开介绍了机构宗旨和定位，可补充机构简介。\n"
                "- 广州样本公益中心儿童心理服务项目面向困境儿童，可补充项目介绍和服务对象。\n"
                "- 广州样本公益中心网页列出负责人李明和项目团队，可补充负责人/团队线索。"
            ),
            judgment="证据缺口：仍需核验登记信息、年报和项目成效。",
            actions="",
            timeline="",
        )


def test_profile_layered_research_promotes_quick_html_before_deep_sources(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "layered.sqlite")
    _seed_client(db)
    scope = _scope()
    intent = _intent("client_layered", "广州样本公益中心 官网 项目 团队 年报")
    _insert_intent(db, intent)
    fetch_order: list[str] = []
    progress_stages: list[str] = []

    def fake_fetch(query: str, source_config):
        fetch_order.append(source_config.source_type)
        if source_config.source_type in {"official_site", "official_site_section", "web_search", "charity_media"}:
            return [
                CandidateHit(
                    title="广州样本公益中心官网介绍",
                    url="https://sample-foundation.org/about",
                    snippet="广州样本公益中心公开机构定位、儿童心理服务项目和团队介绍。",
                    source=source_config.source_name,
                )
            ]
        if source_config.source_type == "profile_report":
            return [
                CandidateHit(
                    title="广州样本公益中心年度报告 PDF",
                    url="https://sample-foundation.org/report/2025.pdf",
                    snippet="年度报告 PDF。",
                    source=source_config.source_name,
                )
            ]
        return []

    def fake_page_text(url: str):
        if url.endswith(".pdf"):
            return "failed", "", "PDF 深水来源暂未解析"
        return (
            "fetched",
            "广州样本公益中心官网介绍其机构宗旨和定位。广州样本公益中心儿童心理服务项目面向困境儿童，覆盖社区和学校。"
            "广州样本公益中心网页列出负责人李明和项目团队，并介绍课程、培训和活动方法。",
            "",
        )

    monkeypatch.setattr(supply, "_fetch_page_text", fake_page_text)
    result = run_profile_completion_research(
        db,
        data_dir=tmp_path,
        ai_service=_ProfileAi(),
        scope=scope,
        intents=[intent],
        max_fetch_jobs=16,
        hit_fetcher=fake_fetch,
        official_site_hit_fetcher=lambda _query, _config: [],
        progress_callback=lambda _result, stage, _message: progress_stages.append(stage),
    )

    assert progress_stages[0] == "quick_start"
    assert "quick" in progress_stages
    assert result.quick_win_card_count >= 1
    assert result.profile_fact_card_count >= 2
    assert result.deep_queue_count >= 1
    assert result.deep_dive_queued_count >= 1
    assert result.deep_dive_remaining_count >= 1
    assert fetch_order
    assert "profile_report" in fetch_order
    assert any(source_type != "profile_report" for source_type in fetch_order[: fetch_order.index("profile_report")])


def test_profile_layered_research_requires_ai_refinement_for_profile_cards(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "fallback.sqlite")
    _seed_client(db)
    scope = _scope()
    intent = _intent("client_layered", "广州样本公益中心 机构简介 项目 服务对象")
    _insert_intent(db, intent)
    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: (
            "fetched",
            "广州样本公益中心公开资料介绍其机构定位。广州样本公益中心儿童心理服务项目面向困境儿童。"
            "广州样本公益中心组织课程、培训和活动，服务社区和学校。",
            "",
        ),
    )

    result = run_profile_completion_research(
        db,
        data_dir=tmp_path,
        ai_service=None,
        scope=scope,
        intents=[intent],
        max_fetch_jobs=8,
        hit_fetcher=lambda _query, source_config: [
            CandidateHit(
                title="广州样本公益中心公开资料",
                url="https://sample-foundation.org/profile",
                snippet="广州样本公益中心公开机构和项目资料。",
                source=source_config.source_name,
            )
        ],
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    rows = db.fetchall("SELECT key_points_json FROM intelligence_items WHERE scope_id='client_layered'")
    candidate_rows = db.fetchall("SELECT promotion_reason, summary_status FROM intelligence_candidate_items WHERE scope_id='client_layered'")
    assert result.profile_fact_card_count == 0
    assert rows == []
    assert any("AI 未生成合格" in str(row["promotion_reason"]) for row in candidate_rows)
    assert {row["summary_status"] for row in candidate_rows} == {"failed"}


def test_profile_layered_research_queues_list_pages_for_next_deep_dive_round(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "drilldown.sqlite")
    _seed_client(db)
    scope = _scope()
    intent = _intent("client_layered", "广州样本公益中心 项目 课程 服务对象")
    _insert_intent(db, intent)
    drilldown_called = False

    def fail_if_drilldown(*_args, **_kwargs):
        nonlocal drilldown_called
        drilldown_called = True
        return []

    monkeypatch.setattr(supply, "_drilldown_detail_hits_from_list", fail_if_drilldown)
    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: (
            "fetched",
            "广州样本公益中心项目介绍页面说明儿童心理服务项目面向困境儿童，包含课程、培训和社区活动。",
            "",
        ),
    )

    result = run_profile_completion_research(
        db,
        data_dir=tmp_path,
        ai_service=_ProfileAi(),
        scope=scope,
        intents=[intent],
        max_fetch_jobs=8,
        hit_fetcher=lambda _query, source_config: [
            CandidateHit(
                title="广州样本公益中心项目列表",
                url="https://sample-foundation.org/news/list",
                snippet="项目列表页。",
                source=source_config.source_name,
            )
        ],
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    list_rows = db.fetchall("SELECT page_type, classification_status FROM intelligence_candidate_items WHERE page_type='list_page'")
    item_rows = db.fetchall("SELECT source_url FROM intelligence_items WHERE scope_id='client_layered'")
    assert list_rows
    assert result.deep_queue_count >= 1
    assert result.deep_dive_queued_count >= 1
    assert result.deep_dive_remaining_count >= 1
    assert not drilldown_called
    assert not any("project-detail" in str(row["source_url"]) for row in item_rows)
    evidence = from_json(str(db.fetchone("SELECT evidence_json FROM intelligence_candidate_items WHERE page_type='list_page'")["evidence_json"]), {})
    assert evidence["deepDiveStatus"] == "queued"


def test_profile_layered_research_next_round_prioritizes_deep_dive_pool(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "deep-next.sqlite")
    _seed_client(db)
    scope = _scope()
    intent = _intent("client_layered", "广州样本公益中心 项目 课程 服务对象")
    _insert_intent(db, intent)

    monkeypatch.setattr(
        supply,
        "_drilldown_detail_hits_from_list",
        lambda hit, _terms, limit=10, timeout_seconds=5.0: [
            CandidateHit(
                title="广州样本公益中心项目介绍",
                url="https://sample-foundation.org/news/2026/project-detail.html",
                snippet="由列表页下钻：广州样本公益中心项目介绍。",
                source=hit.source,
                provider="list_drilldown",
            )
        ],
    )
    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: (
            "fetched",
            "广州样本公益中心项目介绍页面说明儿童心理服务项目面向困境儿童，包含课程、培训和社区活动。",
            "",
        ),
    )

    first = run_profile_completion_research(
        db,
        data_dir=tmp_path,
        ai_service=_ProfileAi(),
        scope=scope,
        intents=[intent],
        max_fetch_jobs=8,
        hit_fetcher=lambda _query, source_config: [
            CandidateHit(
                title="广州样本公益中心项目列表",
                url="https://sample-foundation.org/news/list",
                snippet="项目列表页。",
                source=source_config.source_name,
            )
        ],
        official_site_hit_fetcher=lambda _query, _config: [],
    )
    assert first.deep_dive_remaining_count >= 1

    normal_search_called = False

    def fail_normal_fetch(_query, _source_config):
        nonlocal normal_search_called
        normal_search_called = True
        return []

    second = run_profile_completion_research(
        db,
        data_dir=tmp_path,
        ai_service=_ProfileAi(),
        scope=scope,
        intents=[intent],
        max_fetch_jobs=8,
        hit_fetcher=fail_normal_fetch,
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert second.profile_run_mode == "deep_dive"
    assert second.deep_dive_processed_count >= 1
    assert second.deep_dive_remaining_count == 0
    assert not normal_search_called
    item_rows = db.fetchall("SELECT source_url FROM intelligence_items WHERE scope_id='client_layered'")
    assert any("project-detail" in str(row["source_url"]) for row in item_rows)


def test_profile_layered_research_skips_uncertain_complex_sources(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "skip-complex.sqlite")
    _seed_client(db)
    scope = _scope()
    intent = _intent("client_layered", "广州样本公益中心 公开报道", intent_id="intent_skip_complex")
    _insert_intent(db, intent)
    monkeypatch.setattr(supply, "_fetch_page_text", lambda _url: ("failed", "", "不应抓取弱相关复杂来源正文"))

    result = run_profile_completion_research(
        db,
        data_dir=tmp_path,
        ai_service=_ProfileAi(),
        scope=scope,
        intents=[intent],
        max_fetch_jobs=8,
        hit_fetcher=lambda _query, source_config: [
            CandidateHit(
                title="广州样本公益中心资料下载",
                url="https://misc-public.org/downloads/list",
                snippet="下载列表页。",
                source=source_config.source_name,
            )
        ] if source_config.source_type == "web_search" else [],
        official_site_hit_fetcher=lambda _query, _config: [],
    )

    assert result.deep_dive_queued_count == 0
    assert result.deep_dive_skipped_count >= 1
    row = db.fetchone("SELECT evidence_json FROM intelligence_candidate_items WHERE scope_id='client_layered' AND evidence_json LIKE '%deepDiveStatus%'")
    evidence = from_json(str(row["evidence_json"]), {})
    assert evidence["deepDiveStatus"] == "skipped"
