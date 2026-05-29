from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("YIYU_WORKBENCH_DATA_DIR", tempfile.mkdtemp(prefix="yiyu-auto-due-tests-"))

import app.main as app_main
from app.main import create_app


class _EmptyGeneration:
    intents: list[object] = []


class _EmptyRefresh:
    def as_payload(self) -> dict[str, object]:
        return {
            "fetchJobCount": 0,
            "candidateCount": 0,
            "promotedCount": 0,
            "effectiveLeadCount": 0,
            "successQueryCount": 0,
            "noResultQueryCount": 0,
            "rejectionCounts": {},
        }


def test_auto_refresh_due_queues_only_expired_content_kind(tmp_path: Path, monkeypatch) -> None:
    app = create_app(tmp_path / "data")
    monkeypatch.setattr(app_main, "generate_intelligence_search_intents", lambda *_args, **_kwargs: _EmptyGeneration())
    monkeypatch.setattr(app_main, "run_intelligence_candidate_refresh", lambda *_args, **_kwargs: _EmptyRefresh())
    with TestClient(app) as client:
        db = client.app.state.app_state.db
        db.execute(
            """
            INSERT OR REPLACE INTO clients(id, name, alias, domain, type, intro, stage, color, created_at, updated_at)
            VALUES('client_due', '到期客户', '到期客户', '儿童心理健康', 'foundation', '关注儿童服务', 'active', '#5B7BFE',
                   '2026-05-18T08:00:00', '2026-05-18T08:00:00')
            """
        )
        db.set_setting("intelligence_profile_completion_cycle_hours", "1")
        db.set_setting("intelligence_timely_intelligence_cycle_hours", "72")
        db.execute(
            """
            INSERT INTO intelligence_refresh_runs(
                id, scope_type, scope_id, client_id, content_kind, trigger_source,
                status, stage, message, created_at, updated_at, started_at, finished_at
            )
            VALUES
              ('old_profile_run', 'client', 'client_due', 'client_due', 'profile_completion', 'manual',
               'completed', 'completed', 'old', '2020-01-01T00:00:00', '2020-01-01T00:00:00',
               '2020-01-01T00:00:00', '2020-01-01T00:00:00'),
              ('fresh_timely_run', 'client', 'client_due', 'client_due', 'timely_intelligence', 'manual',
               'completed', 'completed', 'fresh', '2026-05-18T08:30:00', '2026-05-18T08:30:00',
               '2026-05-18T08:30:00', '2099-01-01T00:00:00')
            """
        )

        response = client.post(
            "/api/v1/intelligence/auto-refresh-due",
            json={"contentKinds": ["profile_completion", "timely_intelligence"], "scopeType": "client", "scopeId": "client_due"},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["queuedCount"] == 1
        queued = [item for item in payload["results"] if item["queued"]]
        assert queued[0]["contentKind"] == "profile_completion"
        row = db.fetchone(
            """
            SELECT trigger_source
            FROM intelligence_refresh_runs
            WHERE client_id='client_due' AND content_kind='profile_completion'
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        assert row["trigger_source"] == "auto_due"


def test_auto_refresh_due_skips_active_run(tmp_path: Path) -> None:
    app = create_app(tmp_path / "data")
    with TestClient(app) as client:
        db = client.app.state.app_state.db
        db.execute(
            """
            INSERT OR REPLACE INTO clients(id, name, alias, domain, type, intro, stage, color, created_at, updated_at)
            VALUES('client_active', '运行中客户', '运行中客户', '儿童心理健康', 'foundation', '关注儿童服务', 'active', '#5B7BFE',
                   '2026-05-18T08:00:00', '2026-05-18T08:00:00')
            """
        )
        db.execute(
            """
            INSERT INTO intelligence_refresh_runs(
                id, scope_type, scope_id, client_id, content_kind, trigger_source,
                status, stage, message, created_at, updated_at
            )
            VALUES('active_profile_run', 'client', 'client_active', 'client_active', 'profile_completion',
                   'manual', 'running', 'researching_sources', 'running', '2026-05-18T08:00:00', '2026-05-18T08:05:00')
            """
        )

        response = client.post(
            "/api/v1/intelligence/auto-refresh-due",
            json={"contentKinds": ["profile_completion"], "scopeType": "client", "scopeId": "client_active"},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["queuedCount"] == 0
        assert payload["results"][0]["skippedReason"] == "已有排队或运行中的刷新任务"
