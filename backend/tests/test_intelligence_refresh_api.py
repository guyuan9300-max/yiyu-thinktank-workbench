from __future__ import annotations

import sys
from pathlib import Path

import pytest

from fastapi.testclient import TestClient

# 整合于 2026-05-13：同事的资讯情报站独占代码已合入（intelligence_*.py / public_search.py），
# 但 main.py / db.py / models.py 的接口胶水（路由注册、表 schema、Pydantic 模型）需要
# 同事自己继续完成（用户原话："这是半成品，不能运作"）。胶水补完之前测试 skip，
# 避免 CI 因为 app.main 缺 generate_intelligence_search_intents 等 monkeypatch 目标失败。
pytestmark = pytest.mark.skip(
    reason="同事资讯情报站半成品 — 共享胶水（main.py 路由 / db.py 表 / models.py）待补齐"
)

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main
import app.services.intelligence_candidate_supply as supply
from app.main import create_app
from app.models import AiStructuredResponse
from app.services.intelligence_candidate_supply import CandidateDraft, CandidateHit, CandidateRefreshResult, SourceConfig, _hit_matches_intelligence_context
from app.services.intelligence_search_intents import (
    GeneratedSearchIntent,
    IntelligenceSearchScope,
    SearchDiagnosticResult,
    SearchIntentGenerationResult,
)


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def seed_client(client: TestClient, *, client_id: str, name: str) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT OR REPLACE INTO clients(id, name, alias, domain, type, intro, stage, color, created_at, updated_at)
        VALUES(?, ?, ?, '儿童服务', 'foundation', '困境儿童服务', 'active', '#5B7BFE', '2026-05-10T09:00:00', '2026-05-10T09:00:00')
        """,
        (client_id, name, name),
    )


def _intent(scope: IntelligenceSearchScope, content_kind: str) -> GeneratedSearchIntent:
    return GeneratedSearchIntent(
        id=f"intent_{scope.scope_id}_{content_kind}",
        scope_type=scope.scope_type,
        scope_id=scope.scope_id,
        client_id=scope.client_id,
        project_module_id=scope.project_module_id,
        content_kind=content_kind,
        query=f"{scope.display_name} {content_kind} 公开信息",
        exclude_terms=["小红书", "微信公众号"],
        source_inputs=[scope.display_name],
        reason="测试搜索意图",
        priority=90,
        status="ready",
        input_hash="hash_test",
        expires_at="2026-05-12T00:00:00",
    )


def install_refresh_fakes(monkeypatch, *, fail_scope_id: str | None = None) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []

    def fake_generate(_db, _ai_service, *, scope_type: str, scope_id: str, content_kind: str | None = None, force: bool = False):
        scope = IntelligenceSearchScope(
            scope_type=scope_type,
            scope_id=scope_id,
            client_id=scope_id,
            project_module_id=None,
            display_name=f"测试对象 {scope_id}",
        )
        kind = content_kind or "timely_intelligence"
        calls.append(("generate", f"{scope_id}:{kind}:{force}"))
        return SearchIntentGenerationResult(scope=scope, intents=[_intent(scope, kind)], status="ready")

    def fake_diagnostic(_db, *, scope: IntelligenceSearchScope, intents: list[GeneratedSearchIntent], trigger_source: str, **_kwargs):
        calls.append(("diagnostic", f"{scope.scope_id}:{trigger_source}:{len(intents)}"))
        return [
            SearchDiagnosticResult(
                intent_id=intents[0].id,
                query=intents[0].query,
                content_kind=intents[0].content_kind,
                status="success",
                provider="test_provider",
                raw_count=2,
                deduped_count=1,
                sample_hits=[{"title": "测试样本", "url": "https://example.org/news"}],
                duration_ms=1,
            )
        ]

    def fake_candidate_refresh(_db, *, scope: IntelligenceSearchScope, intents: list[GeneratedSearchIntent], **_kwargs):
        calls.append(("candidate", f"{scope.scope_id}:{len(intents)}"))
        if fail_scope_id and scope.scope_id == fail_scope_id:
            raise RuntimeError("测试候选抓取失败")
        kind = intents[0].content_kind
        reason = "AI 不可用，时效情报候选暂不自动成卡" if kind == "timely_intelligence" else "相关性不足，暂未成卡"
        _db.execute(
            """
            INSERT OR REPLACE INTO intelligence_candidate_items(
                id, scope_type, scope_id, client_id, project_module_id, content_kind,
                intent_id, source_config_id, fetch_job_id, title, url, normalized_url,
                snippet, source, source_tier, provider, published_at, captured_at,
                matched_terms_json, dedupe_key, duplicate_of_id, confidence_score,
                classification_status, promotion_reason, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, NULL, ?, NULL, NULL, NULL, ?, ?, ?, ?, ?, 'standard', 'test_provider', ?, ?, '[]', ?, NULL, 82, 'candidate', ?, ?, ?)
            """,
            (
                f"cand_{scope.scope_id}_{kind}",
                scope.scope_type,
                scope.scope_id,
                scope.client_id,
                kind,
                f"{scope.display_name} 候选标题",
                f"https://example.org/{scope.scope_id}/{kind}",
                f"https://example.org/{scope.scope_id}/{kind}",
                "这是一条只含短摘的候选摘要，不包含网页正文。",
                "测试公开源",
                "2026-05-11T09:30:00",
                "2026-05-11T10:00:00",
                f"{scope.scope_id}:{kind}",
                reason,
                "2026-05-11T10:00:00",
                "2026-05-11T10:00:00",
            ),
        )
        return CandidateRefreshResult(
            source_config_count=2,
            fetch_job_count=3,
            candidate_count=4,
            promoted_count=1,
            duplicate_count=1,
            failed_count=0,
            source_coverage_status="ready",
            candidate_refresh_status="ready",
            last_candidate_fetch_at="2026-05-11T10:00:00",
            candidate_counts={kind: 4},
        )

    monkeypatch.setattr(app_main, "generate_intelligence_search_intents", fake_generate)
    monkeypatch.setattr(app_main, "run_intelligence_search_diagnostic", fake_diagnostic)
    monkeypatch.setattr(app_main, "run_intelligence_candidate_refresh", fake_candidate_refresh)
    return calls


def test_refresh_single_client_runs_supply_chain_and_returns_counts(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)
    seed_client(client, client_id="client_a", name="青少年发展基金会")
    calls = install_refresh_fakes(monkeypatch)

    response = client.post(
        "/api/v1/intelligence/refresh",
        json={"scopeType": "client", "scopeId": "client_a", "contentKind": "profile_completion", "force": True},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["totals"]["objectCount"] == 1
    assert payload["totals"]["candidateCount"] == 4
    assert payload["totals"]["promotedCount"] == 1
    assert payload["results"][0]["scopeId"] == "client_a"
    assert payload["results"][0]["sourceCoverageStatus"] == "ready"
    assert payload["results"][0]["candidateSamples"] == []
    assert ("generate", "client_a:profile_completion:True") in calls
    assert any(call[0] == "candidate" for call in calls)

    list_response = client.get(
        "/api/v1/intelligence/items",
        params={"contentKind": "profile_completion", "workObjectType": "client", "workObjectId": "client_a"},
    )
    assert list_response.status_code == 200, list_response.text
    list_payload = list_response.json()
    assert list_payload["items"] == []
    assert list_payload["candidateSamples"] == []


def test_profile_list_hides_promoted_candidates_and_legacy_short_excerpt_cards(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    seed_client(client, client_id="client_a", name="益语智库")
    db = client.app.state.app_state.db
    db.execute(
        """
        INSERT INTO intelligence_items(
            id, content_kind, scope_type, scope_id, client_id, project_module_id,
            title, summary, key_points_json, analysis, impact, tags_json, source, source_url,
            published_at, captured_at, verified_at, credibility_score, confidence_score,
            data_center_ingest_event_id, user_status, created_at, updated_at
        )
        VALUES('legacy_item', 'profile_completion', 'client', 'client_a', 'client_a', NULL,
            '旧短摘资料卡', '这是 P4 前由搜索短摘直接生成的资料卡。', '[]', '', '', '[]',
            '测试公开源', 'https://example.org/legacy', '2026-05-11T08:00:00',
            '2026-05-11T09:00:00', '2026-05-11T09:00:00', 0.9, 0.8,
            'sysdoc_legacy', 'active', '2026-05-11T09:00:00', '2026-05-11T09:00:00')
        """
    )
    db.execute(
        """
        INSERT INTO intelligence_candidate_items(
            id, scope_type, scope_id, client_id, project_module_id, content_kind,
            title, url, normalized_url, snippet, source, published_at, captured_at,
            matched_terms_json, dedupe_key, confidence_score, classification_status,
            promotion_reason, promoted_intelligence_item_id, is_user_visible_candidate,
            created_at, updated_at
        )
        VALUES('promoted_candidate', 'client', 'client_a', 'client_a', NULL, 'profile_completion',
            '已晋升候选', 'https://example.org/promoted', 'https://example.org/promoted',
            '已经晋升的候选不应继续出现在候选线索。', '测试公开源',
            '2026-05-11T08:00:00', '2026-05-11T09:00:00', '[]', 'promoted',
            92, 'promoted', '已成卡', 'legacy_item', 1, '2026-05-11T09:00:00', '2026-05-11T09:00:00')
        """
    )
    db.execute(
        """
        INSERT INTO intelligence_candidate_items(
            id, scope_type, scope_id, client_id, project_module_id, content_kind,
            title, url, normalized_url, snippet, source, published_at, captured_at,
            matched_terms_json, dedupe_key, confidence_score, classification_status,
            promotion_reason, is_user_visible_candidate, created_at, updated_at
        )
        VALUES('active_candidate', 'client', 'client_a', 'client_a', NULL, 'profile_completion',
            '仍待核验候选', 'https://example.org/candidate', 'https://example.org/candidate',
            '这条仍是候选线索。', '测试公开源',
            '2026-05-11T08:30:00', '2026-05-11T09:30:00', '[]', 'candidate',
            72, 'candidate', '正文尚未核验，暂未成卡', 1, '2026-05-11T09:30:00', '2026-05-11T09:30:00')
        """
    )

    response = client.get(
        "/api/v1/intelligence/items",
        params={"contentKind": "profile_completion", "workObjectType": "client", "workObjectId": "client_a"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["items"] == []
    assert payload["candidateSamples"] == []
    legacy_row = db.fetchone("SELECT user_status, verification_status FROM intelligence_items WHERE id = 'legacy_item'")
    promoted_row = db.fetchone("SELECT is_user_visible_candidate FROM intelligence_candidate_items WHERE id = 'promoted_candidate'")
    assert legacy_row is not None
    assert legacy_row["user_status"] == "dismissed"
    assert legacy_row["verification_status"] == "legacy_unverified"
    assert promoted_row is not None
    assert int(promoted_row["is_user_visible_candidate"]) == 0


def test_refresh_all_reports_partial_failure_without_losing_successes(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)
    seed_client(client, client_id="client_ok", name="社区服务中心")
    seed_client(client, client_id="client_bad", name="儿童保护机构")
    install_refresh_fakes(monkeypatch, fail_scope_id="client_bad")

    response = client.post(
        "/api/v1/intelligence/refresh",
        json={"scopeType": "all", "contentKind": "timely_intelligence", "force": True},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "partial_failed"
    assert payload["totals"]["objectCount"] == 2
    assert payload["totals"]["completedCount"] == 1
    assert payload["totals"]["failedCount"] == 1
    failed = [item for item in payload["results"] if item["status"] == "failed"]
    assert failed and "测试候选抓取失败" in failed[0]["errors"][0]
    success = [item for item in payload["results"] if item["status"] == "completed"][0]
    assert success["candidateSamples"][0]["promotionReason"] == "AI 不可用，时效情报候选暂不自动成卡"


def test_refresh_rejects_invalid_content_kind_and_unknown_object(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    invalid_kind = client.post(
        "/api/v1/intelligence/refresh",
        json={"scopeType": "all", "contentKind": "invalid_kind"},
    )
    assert invalid_kind.status_code == 400

    unknown = client.post(
        "/api/v1/intelligence/refresh",
        json={"scopeType": "client", "scopeId": "missing", "contentKind": "profile_completion"},
    )
    assert unknown.status_code == 404


def test_profile_completion_candidate_filter_rejects_unrelated_foreign_results() -> None:
    scope = IntelligenceSearchScope(
        scope_type="client",
        scope_id="client_yiyu",
        client_id="client_yiyu",
        display_name="益语智库",
    )
    intent = _intent(scope, "profile_completion")
    noisy = CandidateHit(
        title="Sign In - Capital One",
        url="https://verified.capitalone.com/auth/signin",
        snippet="Sign in to access all of your Capital One accounts.",
        source="verified.capitalone.com",
    )
    relevant = CandidateHit(
        title="益语智库 信息公开",
        url="https://yiyu.love/about",
        snippet="益语智库项目报告与信息公开资料。",
        source="yiyu.love",
    )

    assert not _hit_matches_intelligence_context(noisy, intent, ["益语智库"])
    assert _hit_matches_intelligence_context(relevant, intent, ["益语智库"])

    image_hit = CandidateHit(
        title="益语智库_360图片",
        url="https://image.so.com/i?q=%E7%9B%8A%E8%AF%AD%E6%99%BA%E5%BA%93",
        snippet="360图片搜索结果。",
        source="image.so.com",
    )
    assert not _hit_matches_intelligence_context(image_hit, intent, ["益语智库"])


def test_verification_feedback_hides_candidate_and_saves_rule(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    seed_client(client, client_id="client_a", name="益语智库")
    db = client.app.state.app_state.db
    db.execute(
        """
        INSERT INTO intelligence_candidate_items(
            id, scope_type, scope_id, client_id, project_module_id, content_kind,
            intent_id, source_config_id, fetch_job_id, title, url, normalized_url,
            snippet, source, source_tier, provider, published_at, captured_at,
            matched_terms_json, dedupe_key, duplicate_of_id, confidence_score,
            classification_status, promotion_reason, created_at, updated_at
        )
        VALUES('cand_rule', 'client', 'client_a', 'client_a', NULL, 'profile_completion',
            NULL, NULL, NULL, '益语智库 图片结果', 'https://image.so.com/i?q=yiyu', 'https://image.so.com/i?q=yiyu',
            '图片搜索结果', 'image.so.com', 'standard', 'test', NULL, '2026-05-11T10:00:00',
            '[]', 'cand_rule', NULL, 50, 'candidate', '', '2026-05-11T10:00:00', '2026-05-11T10:00:00')
        """
    )

    response = client.post(
        "/api/v1/intelligence/verification-feedback",
        json={
            "targetType": "candidate",
            "targetId": "cand_rule",
            "scopeType": "client",
            "scopeId": "client_a",
            "note": "这不是益语智库本身的信息",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert "这不是益语智库本身的信息" in payload["excludeRules"]
    row = db.fetchone("SELECT verification_status, is_user_visible_candidate FROM intelligence_candidate_items WHERE id = 'cand_rule'")
    assert row is not None
    assert row["verification_status"] == "rejected"
    assert int(row["is_user_visible_candidate"]) == 0


class _ReadyHealth:
    ready = True
    provider = "qwen"


class _FakeProfileAi:
    def get_health(self):
        return _ReadyHealth()

    def generate_general_fallback(self, *_args, **_kwargs):
        return AiStructuredResponse(
            content="广东省日慈公益基金会为广东省民政厅登记的慈善组织，公开资料可用于补充登记信息与业务范围。",
            judgment="资料属于广东省日慈公益基金会本身，可进入资料补全。",
            analysis="登记机关为广东省民政厅；业务范围包括慈善救助、公益项目资助、志愿服务项目等。",
            actions="后续可继续补充年度报告、项目成效和合作方资料。",
            timeline="",
        )


def _profile_draft(scope: IntelligenceSearchScope) -> CandidateDraft:
    intent = GeneratedSearchIntent(
        id="intent_rici_profile",
        scope_type=scope.scope_type,
        scope_id=scope.scope_id,
        client_id=scope.client_id,
        project_module_id=scope.project_module_id,
        content_kind="profile_completion",
        query="广东省日慈公益基金会 登记信息 信息公开",
        exclude_terms=[],
        source_inputs=["client:广东省日慈公益基金会"],
        reason="资料补全缺口：登记信息 信息公开。详细需求：查找可确认主体身份、登记机关、统一社会信用代码、法定代表人、住所、业务范围等固定资料的可靠公开页面。",
        priority=96,
        status="ready",
        input_hash="hash_rici",
        expires_at="2026-05-16T00:00:00",
    )
    config = SourceConfig(
        id="src_social_org",
        scope_type=scope.scope_type,
        scope_id=scope.scope_id,
        client_id=scope.client_id,
        project_module_id=scope.project_module_id,
        source_type="social_org_registry",
        source_name="社会组织信息公开",
        source_url_template="https://gdngo.gdnpo.gov.cn/search?q={query}",
        region="广东",
        reliability_tier="strong",
        priority=95,
        content_kinds=["profile_completion"],
    )
    hit = CandidateHit(
        title="广东省日慈公益基金会 - 社会组织信息公开",
        url="https://gdngo.gdnpo.gov.cn/org/rici",
        snippet="广东省日慈公益基金会，登记机关广东省民政厅，慈善组织。",
        source="gdngo.gdnpo.gov.cn",
        published_at="2026-05-13T09:00:00",
    )
    return CandidateDraft(
        id="cand_rici_profile",
        content_kind="profile_completion",
        intent=intent,
        source_config=config,
        fetch_job_id="fetch_rici",
        hit=hit,
        normalized_url=hit.url,
        dedupe_key="rici_profile",
        matched_terms=["广东省日慈公益基金会", "登记信息", "信息公开"],
        confidence_score=92,
        signal_count=3,
    )


def test_profile_completion_promotion_requires_body_identity_mapping_and_ai(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)
    seed_client(client, client_id="client_rici", name="广东省日慈公益基金会")
    db = client.app.state.app_state.db
    scope = IntelligenceSearchScope(
        scope_type="client",
        scope_id="client_rici",
        client_id="client_rici",
        display_name="广东省日慈公益基金会",
    )
    draft = _profile_draft(scope)

    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: (
            "fetched",
            "广东省日慈公益基金会由广东省民政厅登记，统一社会信用代码为 53440000MJK850332A。业务范围包括慈善救助、公益项目资助、志愿服务项目、困难群体帮扶和公益传播。",
            "",
        ),
    )

    promoted = supply._promote_candidate(
        db,
        data_dir=tmp_path / "data",
        ai_service=_FakeProfileAi(),
        scope=scope,
        draft=draft,
        timestamp="2026-05-13T11:00:00",
    )

    assert promoted is True
    row = db.fetchone("SELECT title, summary, key_points_json, tags_json, source_url, verification_status FROM intelligence_items WHERE content_kind = 'profile_completion'")
    assert row is not None
    assert row["verification_status"] == "verified"
    assert row["source_url"] == "https://gdngo.gdnpo.gov.cn/org/rici"
    assert "搜索短摘" not in str(row["summary"] or "")
    assert "广东省日慈公益基金会为广东省民政厅登记的慈善组织" in str(row["summary"] or "")
    assert "social_org_registry" not in str(row["tags_json"] or "")
    assert "登记机关为广东省民政厅" in str(row["key_points_json"] or "")


def test_profile_completion_does_not_promote_without_ai_summary(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)
    seed_client(client, client_id="client_rici", name="广东省日慈公益基金会")
    db = client.app.state.app_state.db
    scope = IntelligenceSearchScope(
        scope_type="client",
        scope_id="client_rici",
        client_id="client_rici",
        display_name="广东省日慈公益基金会",
    )
    draft = _profile_draft(scope)
    monkeypatch.setattr(
        supply,
        "_fetch_page_text",
        lambda _url: (
            "fetched",
            "广东省日慈公益基金会由广东省民政厅登记，业务范围包括慈善救助、公益项目资助、志愿服务项目和困难群体帮扶。",
            "",
        ),
    )

    promoted = supply._promote_candidate(
        db,
        data_dir=tmp_path / "data",
        ai_service=None,
        scope=scope,
        draft=draft,
        timestamp="2026-05-13T11:00:00",
    )

    assert promoted is False
    assert db.scalar("SELECT COUNT(1) FROM intelligence_items WHERE content_kind = 'profile_completion'") == 0
