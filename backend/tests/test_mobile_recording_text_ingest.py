from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app


NOW = "2026-05-07T09:30:00"


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def seed_recording_context(client: TestClient) -> None:
    db = client.app.state.app_state.db
    db.execute(
        """
        INSERT OR REPLACE INTO clients(id, name, alias, domain, type, intro, stage, color, created_at, updated_at)
        VALUES('client_foundation', 'A组织', '', '', 'foundation', '', '', '#5B7BFE', ?, ?)
        """,
        (NOW, NOW),
    )
    db.execute(
        """
        INSERT OR IGNORE INTO task_lists(id, name, color, sort_order, is_default, scope)
        VALUES('list-0', '收集箱', '#5B7BFE', 0, 1, 'org')
        """
    )
    db.execute(
        """
        INSERT OR REPLACE INTO event_lines(
            id, name, kind, status, primary_client_id, primary_client_name,
            participant_ids_json, created_at, updated_at
        )
        VALUES('eline-q1', 'A组织战略陪伴 Q1 复盘', 'custom', 'active', 'client_foundation', 'A组织', '[]', ?, ?)
        """,
        (NOW, NOW),
    )
    db.execute(
        """
        INSERT OR REPLACE INTO tasks(
            id, title, description, status, progress_status, priority, list_id, owner_name,
            ddl, source_type, client_id, event_line_id, tags_json, tag_ids_json, created_at, updated_at
        )
        VALUES(
            'task-local', 'A组织项目复盘', '整理 Q1 项目复盘记录。', 'todo', 'todo', 'normal',
            'list-0', '', '', 'manual', 'client_foundation', 'eline-q1', '[]', '[]', ?, ?
        )
        """,
        (NOW, NOW),
    )
    db.execute(
        """
        INSERT OR REPLACE INTO meetings(
            id, client_id, title, stage, scheduled_at, transcript_text, notes, created_at, updated_at
        )
        VALUES('meeting-q1', 'client_foundation', 'Q1 项目复盘会', 'prepared', ?, '', '', ?, ?)
        """,
        (NOW, NOW, NOW),
    )


def test_mobile_recording_text_ingest_creates_text_only_records(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    try:
        seed_recording_context(client)

        response = client.post(
            "/api/v1/mobile/recordings/text-ingest",
            json={
                "recordingId": "rec-20260507-001",
                "clientId": "client_foundation",
                "eventLineId": "eline-q1",
                "taskId": "task-local",
                "meetingId": "meeting-q1",
                "rawTranscript": "老师赋能项目设计待补完善 下一步整理项目复盘结论",
                "cleanTranscript": "老师赋能项目设计待补完善。\n下一步整理项目复盘结论。",
                "summary": {
                    "brief": "A组织 Q1 复盘确认项目设计仍需补充。",
                    "actionItems": ["整理项目复盘结论"],
                },
                "segments": [
                    {
                        "segmentIndex": 0,
                        "startMs": 0,
                        "endMs": 4200,
                        "text": "老师赋能项目设计待补完善。",
                        "confidence": 0.82,
                        "isFinal": True,
                    }
                ],
                "recordedAt": NOW,
                "durationSeconds": 4.2,
            },
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["recordingId"] == "rec-20260507-001"
        assert body["syncStatus"] == "synced"
        assert body["documentId"]
        assert body["evidenceRefId"]
        assert body["meetingId"] == "meeting-q1"
        assert body["eventLineActivityId"]
        assert "task-local" in body["taskIds"]
        assert any(task_id != "task-local" for task_id in body["taskIds"])

        db = client.app.state.app_state.db
        document = db.fetchone("SELECT * FROM documents WHERE id = ?", (body["documentId"],))
        assert document is not None
        assert document["source"] == "mobile_recording_text"
        assert Path(str(document["path"])).exists()
        document_text = Path(str(document["path"])).read_text(encoding="utf-8")
        assert "## 整理文本" in document_text
        assert "audio.m4a" not in document_text
        assert "audioPath" not in document_text

        evidence = db.fetchone("SELECT * FROM evidence_refs WHERE id = ?", (body["evidenceRefId"],))
        assert evidence is not None
        assert evidence["source_type"] == "mobile_recording_text"
        assert evidence["document_id"] == body["documentId"]

        attachment = db.fetchone("SELECT * FROM task_attachments WHERE task_id = ?", ("task-local",))
        assert attachment is not None
        assert attachment["source"] == "mobile_recording_text"
        assert attachment["kind"] == "md"

        activity = db.fetchone(
            "SELECT * FROM event_line_activities WHERE id = ?",
            (body["eventLineActivityId"],),
        )
        assert activity is not None
        assert activity["source_type"] == "mobile_recording_text"
        assert activity["source_id"] == "rec-20260507-001"

        meeting = db.fetchone("SELECT * FROM meetings WHERE id = ?", ("meeting-q1",))
        assert meeting is not None
        assert meeting["stage"] == "ingested"
        assert "项目设计待补完善" in meeting["transcript_text"]

        generated = db.fetchone(
            "SELECT * FROM tasks WHERE source_type = ? AND source_id = ? AND id != ?",
            ("mobile_recording_text", "rec-20260507-001", "task-local"),
        )
        assert generated is not None
        assert generated["title"] == "整理项目复盘结论"
    finally:
        client.__exit__(None, None, None)


def test_mobile_recording_text_ingest_rejects_empty_text(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    try:
        seed_recording_context(client)
        response = client.post(
            "/api/v1/mobile/recordings/text-ingest",
            json={
                "recordingId": "rec-empty",
                "clientId": "client_foundation",
                "rawTranscript": "",
                "cleanTranscript": "",
            },
        )
        assert response.status_code == 400
        assert "录音转写文本为空" in response.text
    finally:
        client.__exit__(None, None, None)
