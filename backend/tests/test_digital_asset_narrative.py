from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.models import DigitalAssetClientDetailRecord
from app.services.digital_asset_narrative import (
    DigitalAssetNarrativeQualityError,
    build_digital_asset_narrative_context,
    get_latest_digital_asset_narrative,
    refresh_digital_asset_narrative,
)


NOW = "2026-04-28T10:00:00"


def _db(tmp_path: Path) -> Database:
    return Database(tmp_path / "app.db")


def _insert_client(db: Database, client_id: str = "client_rici") -> None:
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (client_id, "日慈基金会", "日慈基金会", "公益", "战略陪伴", "关注儿童韧性与教师支持网络。", "推进中", NOW, NOW),
    )


def _detail(client_id: str = "client_rici") -> DigitalAssetClientDetailRecord:
    return DigitalAssetClientDetailRecord(
        id=client_id,
        name="日慈基金会",
        intro="关注儿童韧性与教师支持网络。",
        stage="推进中",
        assetStage="资料整理期",
        assetTrackTitle="组织资产型",
        stageProgress=18,
        understandingStatement="AI 已看到部分组织和项目资料。",
    )


def _insert_document(
    db: Database,
    *,
    document_id: str,
    title: str,
    markdown: str,
    client_id: str = "client_rici",
    visible_category: str = "组织与战略",
    secondary_category: str = "核心资料",
    parse_status: str = "ready",
) -> None:
    db.execute(
        """
        INSERT INTO documents(id, client_id, folder_id, title, path, kind, source, excerpt, tags_json, created_at)
        VALUES(?, ?, NULL, ?, ?, 'md', 'import', ?, '[]', ?)
        """,
        (document_id, client_id, title, f"/tmp/{title}", markdown[:180], NOW),
    )
    db.execute(
        """
        INSERT INTO v2_documents(
            id, client_id, document_id, original_path, managed_path, markdown_path, file_name, kind,
            material_layer, visible_category, secondary_category, parse_status, parse_error,
            preview_text, doc_index_text, content_hash, markdown_content, classification_confidence,
            section_count, chunk_count, imported_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, NULL, ?, 'md', 'background', ?, ?, ?, NULL, ?, '', ?, ?, ?, 1, 1, ?, ?)
        """,
        (
            f"v2_{document_id}",
            client_id,
            document_id,
            f"/tmp/{title}",
            f"/tmp/{title}",
            title,
            visible_category,
            secondary_category,
            parse_status,
            markdown[:260],
            f"hash_{document_id}",
            markdown,
            0.92,
            NOW,
            NOW,
        ),
    )


def _insert_task_list(db: Database) -> None:
    db.execute(
        """
        INSERT INTO task_lists(id, name, color, sort_order, is_default)
        VALUES('list_default', '默认', '#5B7BFE', 0, 1)
        """
    )


def _insert_event_line(db: Database, client_id: str = "client_rici") -> None:
    db.execute(
        """
        INSERT INTO event_lines(
            id, name, kind, status, stage, summary, intent, current_blocker, recent_decision,
            next_step, evidence_count, primary_client_id, primary_client_name, created_at, updated_at
        )
        VALUES(?, ?, 'project', 'active', ?, ?, ?, ?, ?, ?, 4, ?, '日慈基金会', ?, ?)
        """,
        (
            "event_teacher",
            "教师项目设计",
            "方案调整",
            "教师项目设计不完整，需要王老师支持，不能由外部团队直接代偿。",
            "近期任务说明提到项目负责人笑雨项目设计能力较弱，需要王老师支持。",
            "方案边界尚未定清。",
            "不要代偿项目组内部设计。",
            "先完成项目设计说明。",
            client_id,
            NOW,
            NOW,
        ),
    )


def _insert_task(db: Database) -> None:
    _insert_task_list(db)
    db.execute(
        """
        INSERT INTO tasks(
            id, title, description, status, priority, list_id, creator_id, owner_name,
            progress_status, ddl, due_date, duration_minutes, scope_mode, event_line_id,
            current_blocker, next_action, recent_decision, evidence_count, source_type,
            source_id, tags_json, tag_ids_json, created_at, updated_at
        )
        VALUES(?, ?, ?, 'todo', 'normal', 'list_default', 'user_1', '笑雨',
               'todo', '', NULL, 60, 'COLLAB_SHARED', 'event_teacher',
               ?, ?, ?, 2, 'event_line', 'event_teacher', '[]', '[]', ?, ?)
        """,
        (
            "task_teacher",
            "教师项目方案调整",
            "任务说明：笑雨项目设计能力偏弱，需要王老师支持，但外部团队不能代替项目组完成设计。",
            "负责人设计能力不足",
            "王老师先给出项目设计边界",
            "不要代偿",
            NOW,
            NOW,
        ),
    )


def _insert_judgment(db: Database, client_id: str = "client_rici") -> None:
    db.execute(
        """
        INSERT INTO judgment_versions(
            id, client_id, target_type, target_id, topic, version, status, summary,
            evidence_ids_json, risk_level, confidence, created_at, updated_at
        )
        VALUES(?, ?, 'client', ?, ?, 1, 'draft', ?, '[]', 'medium', 'medium', ?, ?)
        """,
        (
            "judgment_1",
            client_id,
            client_id,
            "教师项目需要从课程交付转向关系支持",
            "资料显示教师项目不只是课程问题，还涉及教师关系支持、项目边界和负责人能力。",
            NOW,
            NOW,
        ),
    )


def _insert_dna(db: Database, client_id: str = "client_rici") -> None:
    db.execute(
        """
        INSERT INTO client_dna_documents(
            client_id, module_key, title, markdown_content, normalized_text, summary,
            file_name, content_hash, updated_at, updated_by
        )
        VALUES(?, 'strategy', '组织与项目说明', ?, ?, ?, '组织与项目说明.md', 'dna_hash', ?, 'test')
        """,
        (
            client_id,
            "日慈希望从单个项目交付转向儿童韧性生态建设，教师支持网络是重要场景。",
            "日慈希望从单个项目交付转向儿童韧性生态建设，教师支持网络是重要场景。",
            "从项目交付转向韧性生态。",
            NOW,
        ),
    )


class FakeAi:
    def __init__(self, outputs: list[str]):
        self.outputs = outputs

    def get_health(self):
        class Health:
            provider = "fake"
            model = "fake-model"

        return Health()

    def _qwen_generate(self, **kwargs):
        if self.outputs:
            return self.outputs.pop(0)
        return ""


def test_context_counts_documents_and_v2_documents_separately(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _insert_client(db)
    _insert_document(db, document_id="doc_1", title="战略资料.md", markdown="战略定位、项目结构和近期复盘。")

    context = build_digital_asset_narrative_context(db, "client_rici", detail=_detail())
    counts = context["materialAudit"]["counts"]  # type: ignore[index]

    assert counts["documents"] == 1
    assert counts["v2Documents"] == 1
    assert counts["v2Ready"] == 1


def test_context_filters_noise_prompt_docs_and_keeps_event_task_signal(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _insert_client(db)
    _insert_dna(db)
    _insert_event_line(db)
    _insert_task(db)
    _insert_document(db, document_id="doc_core", title="教师项目会议纪要.md", markdown="项目设计、负责人、王老师支持、不要代偿。")
    _insert_document(db, document_id="doc_dup", title="教师项目会议纪要_202604281010.md", markdown="项目设计、负责人、王老师支持、不要代偿。")
    _insert_document(db, document_id="doc_noise", title="日慈报销发票.jpeg", markdown="发票 报销 测试附件。")
    _insert_document(db, document_id="doc_prompt", title="旧提示词.md", markdown="你将作为分析助手，请严格按 YAML front matter 输出。")

    context = build_digital_asset_narrative_context(db, "client_rici", detail=_detail())
    audit = context["materialAudit"]  # type: ignore[assignment]
    selected_titles = [item["title"] for item in audit["selectedPriorityMaterials"]]  # type: ignore[index]
    event_lines = context["priority"]["eventLines"]  # type: ignore[index]
    tasks = context["priority"]["tasks"]  # type: ignore[index]

    assert "日慈报销发票.jpeg" not in selected_titles
    assert "旧提示词.md" not in selected_titles
    assert selected_titles.count("教师项目会议纪要.md") == 1
    assert audit["duplicatePriorityMaterialsRemoved"] == 1  # type: ignore[index]
    assert "不要代偿" in event_lines[0]["recentDecision"]
    assert "笑雨项目设计能力偏弱" in tasks[0]["description"]


def test_refresh_persists_good_narrative_and_get_returns_latest(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _insert_client(db)
    _insert_dna(db)
    _insert_event_line(db)
    _insert_task(db)
    _insert_judgment(db)
    _insert_document(db, document_id="doc_1", title="教师项目资料.md", markdown="项目设计、负责人、教师支持网络。")
    ai = FakeAi(
        [
            "## 资料概况\n资料显示，系统读到了组织说明、事件线和任务说明。\n## 系统已经能看清什么\n教师项目的难点不是写文案，而是项目组内部设计还没有定清。\n## 系统现在能帮什么\n可以把任务说明、事件线和判断版本放在一起，帮助团队看清哪些事情要由项目组自己决定。\n## 现在还不能确定什么\n还不能确定方案落地后的反馈。\n## 接下来建议先整理什么\n先整理教师项目的对象、动作、负责人和证据。",
            "## 资料概况\n资料显示，系统读到了组织说明、事件线和任务说明。\n## 系统已经能看清什么\n教师项目的难点不是写文案，而是项目组内部设计还没有定清。\n## 系统现在能帮什么\n可以把任务说明、事件线和判断版本放在一起，帮助团队看清哪些事情要由项目组自己决定。\n## 现在还不能确定什么\n还不能确定方案落地后的反馈。\n## 接下来建议先整理什么\n先整理教师项目的对象、动作、负责人和证据。",
        ]
    )

    record = refresh_digital_asset_narrative(db, ai, "client_rici")
    latest = get_latest_digital_asset_narrative(db, "client_rici")

    assert record.contentMarkdown
    assert latest is not None
    assert latest.id == record.id
    assert latest.materialAudit["counts"]["documents"] == 1  # type: ignore[index]


def test_refresh_rejects_bad_narrative_and_keeps_old_cache(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _insert_client(db)
    _insert_event_line(db)
    _insert_task(db)
    _insert_document(db, document_id="doc_1", title="教师项目资料.md", markdown="项目设计、负责人、教师支持网络。")
    good_ai = FakeAi(["## 资料概况\n资料显示，已有事件线和任务。", "## 资料概况\n资料显示，已有事件线和任务。"])
    old_record = refresh_digital_asset_narrative(db, good_ai, "client_rici")
    bad_ai = FakeAi(
        [
            "准确率 90%，一定会降本 35%，长期来看会商业化成功。",
            "准确率 90%，一定会降本 35%，长期来看会商业化成功。",
        ]
    )

    with pytest.raises(DigitalAssetNarrativeQualityError):
        refresh_digital_asset_narrative(db, bad_ai, "client_rici")

    latest = get_latest_digital_asset_narrative(db, "client_rici")
    assert latest is not None
    assert latest.id == old_record.id
    assert int(db.scalar("SELECT COUNT(1) AS count FROM digital_asset_narrative_snapshots WHERE failure_reason != ''")) == 1
