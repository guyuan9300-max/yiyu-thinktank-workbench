from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database, to_json  # noqa: E402
from app.services.data_center_proposal import ensure_data_center_proposal_draft_schema  # noqa: E402
from app.services.workspace_answer_value_diagnostics import _count_answer_action_artifacts  # noqa: E402


def _insert_client(db: Database, client_id: str) -> None:
    now = '2026-04-22T09:00:00'
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, color, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, '#5B7BFE', ?, ?)
        """,
        (client_id, client_id, client_id, '公益', '战略陪伴', 'test', '推进中', now, now),
    )


def test_workspace_answer_action_metrics_dedupe_p210_counts_unique_message_ids(tmp_path: Path):
    db = Database(tmp_path / 'app.db')
    ensure_data_center_proposal_draft_schema(db)
    _insert_client(db, 'client_p210')

    now = '2026-04-22T09:00:00'
    db.execute(
        """
        INSERT INTO data_center_proposal_drafts(
            id, scope_type, scope_id, client_id, page, mode, kind, title, summary, rationale,
            risk_level, target_refs_json, source_refs_json, boundary_notes_json, payload_json,
            source_prompt, route_decision_json, answer_plan_json, status, dedupe_key, created_at, updated_at
        )
        VALUES(?, 'client', ?, ?, 'workspace', 'proposal', 'evidence_request', 'draft', 'draft', 'draft',
               'low', '[]', '[]', '[]', ?, '', '{}', '{}', 'draft', 'dedupe', ?, ?)
        """,
        ('draft_1', 'client_p210', 'client_p210', to_json({'workspaceAnswerMessageId': 'msg_1'}), now, now),
    )
    db.execute(
        """
        INSERT INTO proposal_records(
            id, client_id, kind, status, risk_level, title, summary, rationale, target_refs_json,
            source_refs_json, boundary_notes_json, payload_json, created_by, created_at, updated_at
        )
        VALUES(?, ?, 'evidence_request', 'approved', 'low', 'proposal', 'proposal', 'proposal',
               '[]', '[]', '[]', ?, 'tester', ?, ?)
        """,
        ('proposal_1', 'client_p210', to_json({'workspaceAnswerMessageId': 'msg_1'}), now, now),
    )
    for ticket_id in ('ticket_1', 'ticket_2'):
        db.execute(
            """
            INSERT INTO execution_tickets(
                id, proposal_id, client_id, execution_type, status, payload_json, result_json, created_at, updated_at
            )
            VALUES(?, 'proposal_1', 'client_p210', 'request_evidence', 'executed', '{}', '{}', ?, ?)
            """,
            (ticket_id, now, now),
        )

    proposal_count, execution_count, metric_errors = _count_answer_action_artifacts(db, client_id='client_p210')

    assert proposal_count == 1
    assert execution_count == 1
    assert metric_errors == []


def test_workspace_answer_action_metrics_dedupe_p210_surfaces_query_errors():
    class BrokenDb:
        def fetchall(self, *_args, **_kwargs):
            raise sqlite3.Error('boom')

    proposal_count, execution_count, metric_errors = _count_answer_action_artifacts(BrokenDb(), client_id='client_p210')  # type: ignore[arg-type]

    assert proposal_count == 0
    assert execution_count == 0
    assert metric_errors

