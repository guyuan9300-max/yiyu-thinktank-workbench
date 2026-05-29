from __future__ import annotations

from datetime import datetime

from app.db import Database
from app.services.local_model_optimizer import (
    TASK_TYPE_DOCUMENT_CARD,
    TASK_TYPE_PATH_OPTIMIZATION,
    enqueue_local_model_optimization_tasks,
    is_within_run_window,
    requeue_interrupted_local_model_tasks,
    run_due_local_model_tasks,
)


class FakeLocalAi:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate_local_model_json(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(dict(kwargs))
        prompt = str(kwargs.get("user_prompt") or "")
        if "virtual_path" in prompt:
            return {
                "virtual_path": "A组织/项目报告/云南调研/对外提交",
                "classification_tags": ["项目报告", "云南调研", "对外材料"],
                "recommended_owner": "示例工作台",
                "recommended_project": "云南儿童资助研究",
                "confidence": 0.86,
                "reason": "文件内容包含项目报告、合作基金会和云南调研线索。",
                "evidence": ["云南", "项目报告", "基金会"],
            }
        return {
            "title": "云南儿童资助项目报告",
            "purpose": "支撑A组织理解项目进展、成果证据和后续协作重点。",
            "audience": "A组织项目负责人、示例工作台研究与交付团队。",
            "project_context": "该资料属于云南儿童资助研究项目的对外报告材料，用于沉淀项目价值和合作依据。",
            "key_topics": ["项目进展", "成果证据", "合作沟通"],
            "good_questions": ["这份报告能证明项目产生了什么价值？", "后续汇报应重点解释哪些风险？"],
            "keywords": ["A组织", "云南", "儿童资助", "项目报告"],
            "summary": "报告用于向A组织呈现云南儿童资助项目的阶段性进展、主要发现和合作价值。",
            "risk_notes": "需关注错字、页码和对外口径一致性。",
        }


def _db(tmp_path) -> Database:
    return Database(tmp_path / "app.db")


def _seed_document(db: Database) -> tuple[str, str, str]:
    client_id = "client_rici"
    document_id = "doc_report"
    knowledge_document_id = "kd_report"
    now = "2026-05-08T22:00:00"
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, color, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (client_id, "A组织", "A组织", "公益", "foundation", "儿童资助项目合作方", "active", "#4F7DF3", now, now),
    )
    db.execute(
        """
        INSERT INTO documents(id, client_id, title, path, original_source_path, kind, source, excerpt, tags_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            document_id,
            client_id,
            "云南儿童资助项目报告.docx",
            "/original/云南儿童资助项目报告.docx",
            "/original/云南儿童资助项目报告.docx",
            "docx",
            "import",
            "报告面向A组织，说明云南儿童资助项目进展、成果和后续建议。",
            "[]",
            now,
        ),
    )
    db.execute(
        """
        INSERT INTO knowledge_documents(
            id, client_id, document_id, doc_uid, original_path, kind, primary_category,
            secondary_category, binary_hash, normalized_hash, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            knowledge_document_id,
            client_id,
            document_id,
            "uid_report",
            "/original/云南儿童资助项目报告.docx",
            "docx",
            "项目资料",
            "报告",
            "binary_hash",
            "normalized_hash",
            now,
            now,
        ),
    )
    db.execute(
        """
        INSERT INTO knowledge_document_versions(id, knowledge_document_id, version_no, raw_text, raw_hash, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "kdv_report",
            knowledge_document_id,
            1,
            "本报告提交给A组织，说明云南儿童资助项目进展、成果证据、合作价值和后续风险。",
            "raw_hash",
            now,
        ),
    )
    return client_id, document_id, knowledge_document_id


def test_empty_queue_does_not_call_local_model(tmp_path) -> None:
    db = _db(tmp_path)
    ai = FakeLocalAi()

    result = run_due_local_model_tasks(db, ai, settings={"enabled": True}, force=True)

    assert result["processed"] == 0
    assert ai.calls == []


def test_overnight_window_has_no_two_hour_cap() -> None:
    settings = {"dailyWindows": [{"start": "22:00", "end": "08:00"}]}

    assert is_within_run_window(settings, datetime(2026, 5, 8, 23, 30))
    assert is_within_run_window(settings, datetime(2026, 5, 9, 7, 30))
    assert not is_within_run_window(settings, datetime(2026, 5, 9, 12, 0))


def test_processes_card_and_virtual_path_without_moving_original_file(tmp_path) -> None:
    db = _db(tmp_path)
    client_id, _, knowledge_document_id = _seed_document(db)
    ai = FakeLocalAi()
    enqueue_local_model_optimization_tasks(
        db,
        client_id=client_id,
        document_ids=[knowledge_document_id],
        task_types=[TASK_TYPE_DOCUMENT_CARD, TASK_TYPE_PATH_OPTIMIZATION],
        model_profile_id="local_text_deep",
        model_name="qwen3:32b",
    )

    result = run_due_local_model_tasks(db, ai, settings={"enabled": True}, force=True, batch_size=2)

    card = db.fetchone("SELECT * FROM document_cards WHERE knowledge_document_id = ?", (knowledge_document_id,))
    path_row = db.fetchone("SELECT * FROM document_path_optimizations WHERE knowledge_document_id = ?", (knowledge_document_id,))
    document = db.fetchone("SELECT path FROM documents WHERE id = ?", ("doc_report",))
    assert result["processed"] == 2
    assert len(ai.calls) == 2
    assert card is not None
    assert card["purpose"].startswith("支撑A组织")
    assert path_row is not None
    assert path_row["virtual_path"] == "A组织/项目报告/云南调研/对外提交"
    assert path_row["apply_status"] == "applied"
    assert document["path"] == "/original/云南儿童资助项目报告.docx"


def test_requeue_interrupted_running_task(tmp_path) -> None:
    db = _db(tmp_path)
    _, _, knowledge_document_id = _seed_document(db)
    db.execute(
        """
        INSERT INTO local_model_tasks(
            id, task_type, client_id, knowledge_document_id, model_profile_id, status,
            priority, attempts, input_hash, result_json, locked_by, locked_at, started_at,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "lmt_running",
            TASK_TYPE_DOCUMENT_CARD,
            "client_rici",
            knowledge_document_id,
            "local_text_deep",
            "running",
            100,
            1,
            "input_hash",
            "{}",
            "worker",
            "2026-05-08T22:10:00",
            "2026-05-08T22:10:00",
            "2026-05-08T22:00:00",
            "2026-05-08T22:10:00",
        ),
    )

    recovered = requeue_interrupted_local_model_tasks(db)
    task = db.fetchone("SELECT status, locked_by, started_at FROM local_model_tasks WHERE id = ?", ("lmt_running",))

    assert recovered == 1
    assert task["status"] == "queued"
    assert task["locked_by"] is None
    assert task["started_at"] is None
