from __future__ import annotations

import sys
import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("YIYU_WORKBENCH_DATA_DIR", tempfile.mkdtemp(prefix="yiyu-p3-tests-"))

from app.db import Database, to_json
from app.main import create_app
from app.services.intelligence_candidate_supply import (
    CandidateHit,
    ensure_default_source_configs,
    run_intelligence_candidate_refresh,
)
from app.services.intelligence_feedback import (
    FeedbackContext,
    feedback_score_for_candidate,
    record_feedback_event,
    source_domain_from_url,
    source_feedback_adjustment,
    work_object_feedback_score,
)
from app.services.intelligence_search_intents import (
    GeneratedSearchIntent,
    IntelligenceSearchScope,
    generate_intelligence_search_intents,
)


def _seed_client(db: Database, *, client_id: str = "client_rici", name: str = "日慈基金会") -> None:
    db.execute(
        """
        INSERT OR REPLACE INTO clients(id, name, alias, domain, type, intro, stage, color, created_at, updated_at)
        VALUES(?, ?, ?, '儿童心理健康', 'foundation', '关注困境儿童和儿童心理健康服务', 'active', '#5B7BFE', '2026-05-14T09:00:00', '2026-05-14T09:00:00')
        """,
        (client_id, name, name),
    )


def test_p3_focus_directive_feeds_search_intents_without_frontend_strategy(tmp_path: Path) -> None:
    app = create_app(tmp_path / "data")
    with TestClient(app) as client:
        db = client.app.state.app_state.db
        _seed_client(db)

        response = client.put(
            "/api/v1/intelligence/focus-directives",
            json={
                "scopeType": "client",
                "scopeId": "client_rici",
                "profileCompletionFocus": ["年报 信息公开"],
                "timelyIntelligenceFocus": ["公益创投 困境儿童"],
                "exclude": ["商业培训广告"],
            },
        )

        assert response.status_code == 200, response.text
        actions = {
            row["action_type"]
            for row in db.fetchall("SELECT action_type FROM intelligence_feedback_events WHERE scope_id='client_rici'")
        }
        assert {"focus", "focus_exclude"} <= actions

        generation = generate_intelligence_search_intents(
            db,
            None,
            scope_type="client",
            scope_id="client_rici",
            force=True,
        )
        timely = [item for item in generation.intents if item.content_kind == "timely_intelligence"]
        profile = [item for item in generation.intents if item.content_kind == "profile_completion"]

        assert timely[0].reason.startswith("用户关注")
        assert "公益创投" in timely[0].query
        assert any("年报" in item.query for item in profile[:3])
        assert all("商业培训广告" in item.exclude_terms for item in generation.intents)
        assert any("focus:公益创投 困境儿童" in item.source_inputs for item in timely)
        assert any("feedback:timely_intelligence:negative:商业培训广告" in item.source_inputs for item in timely)


def test_p3_follow_modes_feed_distinct_strategy_summaries(tmp_path: Path) -> None:
    db = Database(tmp_path / "p3_feedback.sqlite")
    timestamp = "2026-05-14T10:00:00"
    db.execute(
        """
        INSERT INTO intelligence_source_configs(
            id, scope_type, scope_id, client_id, source_type, source_name,
            source_url_template, content_kinds_json, reliability_tier, priority,
            created_at, updated_at
        )
        VALUES('src_nansha', 'client', 'source_client', 'source_client', 'gov_policy',
            '南沙民政', 'site:nansha.gov.cn {query}', ?, 'strong', 90, ?, ?)
        """,
        (to_json(["timely_intelligence"]), timestamp, timestamp),
    )

    base_context = {
        "content_kind": "timely_intelligence",
        "title": "南沙公益创投困境儿童项目征集",
        "summary": "征集困境儿童心理健康服务项目。",
        "tags": ["资助机会"],
        "extracted_topics": ["公益创投", "困境儿童"],
    }
    record_feedback_event(
        db,
        context=FeedbackContext(scope_type="client", scope_id="theme_client", client_id="theme_client", **base_context),
        action_type="follow",
        reason_code="same_theme",
        note="继续看困境儿童公益创投",
    )
    theme_types = {
        row["target_type"]
        for row in db.fetchall("SELECT target_type FROM intelligence_feedback_summaries WHERE scope_id='theme_client'")
    }
    assert theme_types == {"theme", "tag"}

    record_feedback_event(
        db,
        context=FeedbackContext(
            scope_type="client",
            scope_id="source_client",
            client_id="source_client",
            source="南沙民政",
            source_url="https://nansha.gov.cn/grants",
            source_domain="nansha.gov.cn",
            source_config_id="src_nansha",
            **base_context,
        ),
        action_type="follow",
        reason_code="same_source",
        note="继续看这个来源",
    )
    source_types = {
        row["target_type"]
        for row in db.fetchall("SELECT target_type FROM intelligence_feedback_summaries WHERE scope_id='source_client'")
    }
    assert source_types == {"source", "domain", "source_config"}
    assert source_feedback_adjustment(db, source_config_id="src_nansha", content_kind="timely_intelligence") > 0

    record_feedback_event(
        db,
        context=FeedbackContext(scope_type="client", scope_id="object_client", client_id="object_client", **base_context),
        action_type="follow",
        reason_code="same_work_object",
        note="继续关注这个客户",
    )
    object_types = {
        row["target_type"]
        for row in db.fetchall("SELECT target_type FROM intelligence_feedback_summaries WHERE scope_id='object_client'")
    }
    assert object_types == {"work_object"}
    assert work_object_feedback_score(db, scope_type="client", scope_id="object_client", content_kind="timely_intelligence") > 0


def test_p3_negative_feedback_blocks_card_promotion(tmp_path: Path) -> None:
    db = Database(tmp_path / "p3_candidate.sqlite")
    _seed_client(db)
    scope = IntelligenceSearchScope(
        scope_type="client",
        scope_id="client_rici",
        client_id="client_rici",
        project_module_id=None,
        display_name="日慈基金会",
    )
    configs = ensure_default_source_configs(db, scope)
    config = configs[0]
    hit_url = "https://risk.rici.org.cn/risk"
    hit_title = "日慈基金会公开募捐风险提示"
    hit_snippet = "民政部门提醒基金会公开募捐合规风险，日慈基金会需核对项目传播材料。"
    for source_config in configs:
        if "timely_intelligence" not in source_config.content_kinds:
            continue
        record_feedback_event(
            db,
            context=FeedbackContext(
                scope_type="client",
                scope_id="client_rici",
                client_id="client_rici",
                content_kind="timely_intelligence",
                title=hit_title,
                summary=hit_snippet,
                source=source_config.source_name,
                source_url=hit_url,
                source_domain=source_domain_from_url(hit_url),
                source_config_id=source_config.id,
                tags=[source_config.source_type, "行业风险"],
                extracted_topics=["公开募捐", "风险提示"],
            ),
            action_type="dismiss",
            reason_code="low_value",
            note="这类低价值风险提示不要再成卡",
        )
    assert (
        feedback_score_for_candidate(
            db,
            scope_type="client",
            scope_id="client_rici",
            content_kind="timely_intelligence",
            title=hit_title,
            snippet=hit_snippet,
            tags=[config.source_type],
            source=config.source_name,
            source_domain=source_domain_from_url(hit_url),
            source_config_id=config.id,
        )
        <= -2.0
    )

    intent = GeneratedSearchIntent(
        id="intent_risk",
        scope_type="client",
        scope_id="client_rici",
        client_id="client_rici",
        project_module_id=None,
        content_kind="timely_intelligence",
        query="日慈基金会 公开募捐 风险 通知",
        exclude_terms=[],
        source_inputs=["client:日慈基金会"],
        reason="风险提示",
        priority=99,
        status="ready",
        input_hash="hash",
        expires_at="2026-05-15T00:00:00",
    )
    db.execute(
        """
        INSERT INTO intelligence_search_intents(
            id, scope_type, scope_id, client_id, content_kind, query,
            exclude_terms_json, source_inputs_json, reason, priority, status,
            input_hash, expires_at, generator_version, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, '[]', ?, ?, ?, 'ready', ?, ?, 'test', ?, ?)
        """,
        (
            intent.id,
            intent.scope_type,
            intent.scope_id,
            intent.client_id,
            intent.content_kind,
            intent.query,
            to_json(intent.source_inputs),
            intent.reason,
            intent.priority,
            intent.input_hash,
            intent.expires_at,
            "2026-05-14T09:00:00",
            "2026-05-14T09:00:00",
        ),
    )

    def fake_fetcher(_query: str, source_config) -> list[CandidateHit]:
        return [
            CandidateHit(
                title=hit_title,
                url=hit_url,
                snippet=hit_snippet,
                source=source_config.source_name,
                published_at="2026-05-14T08:00:00",
            )
        ]

    result = run_intelligence_candidate_refresh(
        db,
        data_dir=tmp_path,
        ai_service=None,
        scope=scope,
        intents=[intent],
        max_fetch_jobs=1,
        hit_fetcher=fake_fetcher,
    )

    assert result.candidate_count == 1
    row = db.fetchone("SELECT promotion_reason FROM intelligence_candidate_items WHERE scope_id='client_rici'")
    assert row is not None
    assert "用户反馈降权" in row["promotion_reason"]


def test_p3_verification_feedback_hides_item_and_updates_rules(tmp_path: Path) -> None:
    app = create_app(tmp_path / "data")
    with TestClient(app) as client:
        db = client.app.state.app_state.db
        _seed_client(db)
        db.execute(
            """
            INSERT INTO intelligence_items(
                id, content_kind, scope_type, scope_id, client_id, title, summary,
                tags_json, source, source_url, captured_at, created_at, updated_at
            )
            VALUES('item_low_value', 'timely_intelligence', 'client', 'client_rici',
                'client_rici', '泛营销网页', '这不是日慈基金会公开资料。', ?,
                '测试来源', 'https://example.org/marketing', '2026-05-14T09:00:00',
                '2026-05-14T09:00:00', '2026-05-14T09:00:00')
            """,
            (to_json(["低价值"]),),
        )

        response = client.post(
            "/api/v1/intelligence/verification-feedback",
            json={
                "targetType": "item",
                "targetId": "item_low_value",
                "scopeType": "client",
                "scopeId": "client_rici",
                "note": "不是日慈基金会公开资料，不采纳泛营销网页",
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert any("不是日慈基金会公开资料" in item for item in payload["excludeRules"])
        assert any("不是日慈基金会公开资料" in item for item in payload["clarificationExamples"])
        item_row = db.fetchone("SELECT user_status FROM intelligence_items WHERE id='item_low_value'")
        assert item_row["user_status"] == "dismissed"
        diagnostics = client.get(
            "/api/v1/intelligence/feedback-diagnostics",
            params={"scopeType": "client", "scopeId": "client_rici", "contentKind": "timely_intelligence"},
        )
        assert diagnostics.status_code == 200
        assert any(event["reasonCode"] == "verification_rule" for event in diagnostics.json()["events"])
        assert any(summary["negativeCount"] > 0 for summary in diagnostics.json()["summaries"])
