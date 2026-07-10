from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import DEMO_LEGACY_MANIFEST_KEY, build_demo_data_response, create_app  # noqa: E402
from app.services.sandbox_registry import activate_sandbox, create_sandbox  # noqa: E402


def make_client(tmp_path: Path) -> TestClient:
    client = TestClient(create_app(tmp_path / "data"))
    client.__enter__()
    return client


def test_demo_load_and_clear_are_scoped_to_active_sandbox(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    sandbox_a = create_sandbox(db, kind="organization", name="A").id
    sandbox_b = create_sandbox(db, kind="organization", name="B").id

    activate_sandbox(db, sandbox_a)
    loaded_a = client.post("/api/v1/settings/demo-data/load")
    assert loaded_a.status_code == 200, loaded_a.text
    client_a = loaded_a.json()["primaryClientId"]

    activate_sandbox(db, sandbox_b)
    loaded_b = client.post("/api/v1/settings/demo-data/load")
    assert loaded_b.status_code == 200, loaded_b.text
    client_b = loaded_b.json()["primaryClientId"]
    assert client_a != client_b
    assert loaded_b.json()["sandboxId"] == sandbox_b

    cleared_b = client.post("/api/v1/settings/demo-data/clear")
    assert cleared_b.status_code == 200, cleared_b.text
    assert db.fetchone("SELECT id FROM clients WHERE id = ?", (client_b,)) is None
    assert db.fetchone("SELECT id FROM clients WHERE id = ? AND sandbox_id = ?", (client_a, sandbox_a)) is not None

    activate_sandbox(db, sandbox_a)
    response_a = build_demo_data_response(db)
    assert response_a.loaded is True
    assert response_a.primaryClientId == client_a


def test_demo_clear_refuses_external_references(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    loaded = client.post("/api/v1/settings/demo-data/load")
    assert loaded.status_code == 200, loaded.text
    demo_client_id = loaded.json()["primaryClientId"]
    timestamp = datetime.now().replace(microsecond=0).isoformat()
    db.execute(
        """
        INSERT INTO goal_records(id, client_id, title, quarter, progress, owner_name, created_at, updated_at)
        VALUES('external_goal', ?, '外部目标', '2026 Q3', 0, '测试', ?, ?)
        """,
        (demo_client_id, timestamp, timestamp),
    )

    response = client.post("/api/v1/settings/demo-data/clear")
    assert response.status_code == 409
    assert db.fetchone("SELECT id FROM clients WHERE id = ?", (demo_client_id,)) is not None


def _seed_strict_legacy_demo(client: TestClient) -> None:
    db = client.app.state.app_state.db
    sandbox_id = str(db.get_setting("active_sandbox_id", ""))
    timestamp = datetime.now().replace(microsecond=0).isoformat()
    list_row = db.fetchone(
        "SELECT id FROM task_lists WHERE sandbox_id = ? AND archived_at IS NULL ORDER BY is_default DESC LIMIT 1",
        (sandbox_id,),
    )
    assert list_row is not None
    list_id = str(list_row["id"])
    db.executemany(
        """
        INSERT INTO clients(id, sandbox_id, name, alias, domain, type, intro, stage, color,
                            created_at, updated_at, sync_status, cloud_id, pending_sync_action,
                            last_synced_at, last_sync_error)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'local', NULL, '', '', '')
        """,
        [
            ("client_cffc", sandbox_id, "[演示] 测试机构B", "测试机构B", "公益教育", "非营利项目", "演示数据", "战略陪伴中", "#5B7BFE", timestamp, timestamp),
            ("client_star", sandbox_id, "[演示] 星辰科技", "星辰", "SaaS", "商业化 KA", "演示数据", "方案梳理", "#10B981", timestamp, timestamp),
        ],
    )
    db.executemany(
        "INSERT INTO chat_threads(id, client_id, title, created_at, updated_at) VALUES(?, ?, '默认研判线程', ?, ?)",
        [("thread_cffc", "client_cffc", timestamp, timestamp), ("thread_star", "client_star", timestamp, timestamp)],
    )
    db.executemany(
        "INSERT INTO goal_records(id, client_id, title, quarter, progress, owner_name, created_at, updated_at) VALUES(?, ?, ?, '2026 Q2', ?, ?, ?, ?)",
        [
            ("goal_1", "client_cffc", "提升项目传播清晰度", 62, "庆华", timestamp, timestamp),
            ("goal_2", "client_cffc", "补齐捐赠人关系素材", 40, "嘉宁", timestamp, timestamp),
            ("goal_3", "client_star", "验证销售线索质量", 55, "一朔", timestamp, timestamp),
        ],
    )
    db.executemany(
        "INSERT INTO dna_terms(id, client_id, category, canonical_name, aliases_json, description, created_at, updated_at) VALUES(?, ?, ?, ?, '[]', ?, ?, ?)",
        [
            ("dna_1", "client_cffc", "组织习惯", "田野优先", "所有策略判断优先结合一线反馈。", timestamp, timestamp),
            ("dna_2", "client_star", "增长原则", "线索先验", "任何市场动作都要先验证线索质量。", timestamp, timestamp),
        ],
    )
    db.executemany(
        "INSERT INTO documents(id, client_id, folder_id, title, path, kind, source, excerpt, tags_json, created_at) VALUES(?, ?, NULL, ?, ?, ?, 'file', ?, '[]', ?)",
        [
            ("doc_1", "client_cffc", "项目启动纪要.md", "/mock/client_cffc/项目启动纪要.md", "md", "记录了项目目标、时间表与关键风险。", timestamp),
            ("doc_2", "client_cffc", "捐赠人访谈摘要.txt", "/mock/client_cffc/捐赠人访谈摘要.txt", "txt", "访谈摘要", timestamp),
            ("doc_3", "client_star", "增长诊断报告.pdf", "/mock/client_star/增长诊断报告.pdf", "pdf", "增长诊断", timestamp),
        ],
    )
    db.executemany(
        """
        INSERT INTO tasks(id, sandbox_id, organization_id, client_id, title, description, status,
                          priority, list_id, owner_name, ddl, source_type, source_id, tags_json,
                          created_at, updated_at, sync_status, cloud_id, pending_sync_action,
                          last_synced_at, last_cloud_version, last_sync_error)
        VALUES(?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?, 'manual', ?, '[]', ?, ?, 'local', NULL, '', '', '', '')
        """,
        [
            ("task_seed_1", sandbox_id, "client_cffc", "准备周五跨部门复盘会", "梳理客户推进中的异常转化问题。", "inbox", "high", list_id, "庆华", "周五", "client_cffc", timestamp, timestamp),
            ("task_seed_2", sandbox_id, "client_star", "梳理客户反馈的 10 个核心痛点", "提炼成客户工作台的重点议题。", "doing", "normal", list_id, "一朔", "今天", "client_star", timestamp, timestamp),
        ],
    )
    db.execute(
        "INSERT INTO task_notes(id, task_id, note, created_at, updated_at) VALUES('legacy_note', 'task_seed_2', ?, ?, ?)",
        ("用户反馈集中在试用转化与产品定位不清。", timestamp, timestamp),
    )
    db.executemany(
        "INSERT INTO topic_radars(id, sandbox_id, title, prompt, time_range, created_at) VALUES(?, ?, ?, ?, ?, ?)",
        [
            ("radar_ai", sandbox_id, "大模型应用", "关注公益与咨询行业的大模型落地案例。", "3_days", timestamp),
            ("radar_fund", sandbox_id, "筹资趋势", "跟踪筹资趋势。", "7_days", timestamp),
        ],
    )
    db.executemany(
        "INSERT INTO topic_candidates(id, radar_id, title, summary, source, status, created_at, updated_at) VALUES(?, ?, ?, ?, '行业观察', 'candidate', ?, ?)",
        [
            ("cand_1", "radar_ai", "公益组织开始搭建内部 AI 助理", "案例摘要", timestamp, timestamp),
            ("cand_2", "radar_fund", "捐赠人分层运营成为主流", "趋势摘要", timestamp, timestamp),
        ],
    )
    db.execute(
        """
        INSERT INTO handbook_entries(id, sandbox_id, title, summary, tags_json, source_type, client_id,
                                     created_at, sync_status, last_synced_at, pending_sync_action)
        VALUES('hb_1', ?, '会议不要只产纪要', '必须落到负责人与时间点', '[]', 'meeting',
               'client_cffc', ?, 'local', '', '')
        """,
        (sandbox_id, timestamp),
    )
    evidence = json.dumps(
        [{"documentId": "doc_1", "path": "/mock/client_cffc/项目启动纪要.md"}],
        ensure_ascii=False,
    )
    db.execute(
        """
        INSERT INTO chat_messages(id, thread_id, role, content, structured_data_json, model_route,
                                  evidence_json, status, created_at)
        VALUES('msg_seed_1', 'thread_cffc', 'assistant', '已为你载入测试机构B的内部上下文。',
               '{}', 'AI · mock', ?, 'success', ?)
        """,
        (evidence, timestamp),
    )
    db.set_setting("demo_data_loaded", "1")


def test_strict_legacy_demo_is_registered_and_can_be_cleared(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    _seed_strict_legacy_demo(client)

    response = build_demo_data_response(db)
    assert response.loaded is True
    sandbox_id = str(db.get_setting("active_sandbox_id", ""))
    assert db.fetchone(
        "SELECT key FROM sandbox_settings WHERE sandbox_id = ? AND key = ?",
        (sandbox_id, DEMO_LEGACY_MANIFEST_KEY),
    ) is not None

    cleared = client.post("/api/v1/settings/demo-data/clear")
    assert cleared.status_code == 200, cleared.text
    assert db.fetchone("SELECT id FROM clients WHERE id = 'client_cffc'") is None


def test_modified_legacy_demo_is_preserved_without_manifest(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    _seed_strict_legacy_demo(client)
    db.execute("UPDATE clients SET name = '真实客户' WHERE id = 'client_cffc'")

    response = build_demo_data_response(db)
    assert response.loaded is False
    sandbox_id = str(db.get_setting("active_sandbox_id", ""))
    assert db.fetchone(
        "SELECT key FROM sandbox_settings WHERE sandbox_id = ? AND key = ?",
        (sandbox_id, DEMO_LEGACY_MANIFEST_KEY),
    ) is None
    assert db.fetchone("SELECT id FROM clients WHERE id = 'client_cffc'") is not None
