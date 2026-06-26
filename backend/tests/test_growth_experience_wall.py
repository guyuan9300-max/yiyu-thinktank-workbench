from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app  # noqa: E402
from app.services.exp_wall_service import insert_quote, quotes_are_near_duplicate  # noqa: E402
from app.services.local_memory import save_pending_quotes  # noqa: E402
from app.services.sandbox_registry import DEFAULT_LOCAL_SANDBOX_ID  # noqa: E402


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_workspace(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/v1/workspaces",
        json={"kind": "organization", "name": name, "cloudApiUrl": f"https://{name}.example.test"},
    )
    assert response.status_code == 200, response.text
    return str(response.json()["activeSandboxId"])


def create_client_record(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": "",
            "domain": "成长测试",
            "type": "公益组织",
            "intro": "用于成长中心测试",
            "stage": "active",
            "color": "#5B7BFE",
        },
    )
    assert response.status_code == 200, response.text
    return str(response.json()["id"])


def create_task_record(client: TestClient, title: str, client_id: str | None = None) -> str:
    board = client.get("/api/v1/tasks")
    assert board.status_code == 200, board.text
    lists = board.json()["lists"]
    if lists:
        default_list_id = str(lists[0]["id"])
    else:
        created_list = client.post(
            "/api/v1/task-lists",
            json={"name": "默认清单", "scope": "org", "color": "#5B7BFE", "isDefault": True},
        )
        assert created_list.status_code == 200, created_list.text
        default_list_id = str(created_list.json()["id"])
    response = client.post(
        "/api/v1/tasks",
        json={
            "title": title,
            "desc": "用于成长中心真实信号测试",
            "priority": "normal",
            "listId": default_list_id,
            "clientId": client_id,
            "sourceType": "manual",
        },
    )
    assert response.status_code == 200, response.text
    return str(response.json()["id"])


def test_experience_wall_dedupe_recognizes_root_cause_rewrites() -> None:
    assert quotes_are_near_duplicate(
        "修复bug要先定位源头问题，根源出问题，其他地方的调整都难以彻底生效",
        "处理官网朋友圈分享样式问题时发现：排查bug要先抓根源，源头出问题下游怎么调都没用。",
    )
    assert not quotes_are_near_duplicate(
        "修复bug要先定位源头问题，根源出问题，其他地方的调整都难以彻底生效",
        "对接易反复修改需求的客户，需明确终版边界，避免交付延期。",
    )


def test_experience_wall_merges_handbook_and_quotes_by_active_workspace(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db

    local_client_id = create_client_record(client, "本机成长客户")
    local_task_id = create_task_record(client, "本机成长任务", local_client_id)
    db.execute(
        """
        INSERT INTO handbook_entries(
            id, title, summary, tags_json, source_type, client_id,
            source_object_type, source_object_id, author_user_id, author_user_name, created_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "handbook_local_growth",
            "本机手册金句",
            "本机手册摘要",
            "[]",
            "manual",
            local_client_id,
            "task",
            local_task_id,
            "op_1",
            "本机成员",
            "2026-06-22T00:00:00Z",
        ),
    )
    insert_quote(
        db,
        author_user_id="op_1",
        quote_text="本机经验墙金句",
        source_excerpt="本机经验墙摘要",
        category="execution",
        source_type="task",
        source_object_id=local_task_id,
        sandbox_id=DEFAULT_LOCAL_SANDBOX_ID,
        now="2026-06-22T00:00:00Z",
    )

    org_workspace_id = create_workspace(client, "org-growth-a")
    org_client_id = create_client_record(client, "组织成长客户")
    org_task_id = create_task_record(client, "组织成长任务", org_client_id)
    db.execute(
        """
        INSERT INTO handbook_entries(
            id, title, summary, tags_json, source_type, client_id,
            source_object_type, source_object_id, author_user_id, author_user_name, created_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "handbook_org_growth",
            "组织手册金句",
            "组织手册摘要",
            "[]",
            "manual",
            org_client_id,
            "task",
            org_task_id,
            "op_1",
            "组织成员",
            "2026-06-23T00:00:00Z",
        ),
    )
    insert_quote(
        db,
        author_user_id="op_1",
        quote_text="组织经验墙金句",
        source_excerpt="组织经验墙摘要",
        category="collaboration",
        source_type="task",
        source_object_id=org_task_id,
        sandbox_id=org_workspace_id,
        now="2026-06-23T00:00:00Z",
    )

    org_response = client.get("/api/v1/growth/experience-wall?refreshCloud=false")
    assert org_response.status_code == 200, org_response.text
    org_items = org_response.json()["items"]
    org_texts = {item["text"] for item in org_items}
    assert {"本机手册金句", "本机经验墙金句", "组织手册金句", "组织经验墙金句"}.issubset(org_texts)

    other_workspace_id = create_workspace(client, "org-growth-b")
    assert other_workspace_id != org_workspace_id
    other_response = client.get("/api/v1/growth/experience-wall?refreshCloud=false")
    assert other_response.status_code == 200, other_response.text
    other_texts = {item["text"] for item in other_response.json()["items"]}
    assert "本机手册金句" not in other_texts
    assert "本机经验墙金句" not in other_texts
    assert "组织手册金句" not in other_texts
    assert "组织经验墙金句" not in other_texts


def test_experience_wall_uses_author_display_name_and_deduplicates_similar_quotes(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    workspace_id = create_workspace(client, "org-growth-dedupe")
    task_id = create_task_record(client, "源头排查复盘")

    first_id = insert_quote(
        db,
        author_user_id="cloud_user_a",
        quote_text="遇到反复修改仍不符合预期的问题，要先排查源头，源头出错下游怎么改都不彻底",
        source_excerpt="第一条复盘说明",
        category="方法论",
        source_type="task",
        source_object_id=task_id,
        sandbox_id=workspace_id,
        now="2026-06-24T00:00:00Z",
    )
    second_id = insert_quote(
        db,
        author_user_id="cloud_user_a",
        quote_text="反复修改仍不符合预期时，要先排查源头；源头错了，下游再改也不彻底",
        source_excerpt="第二条流转材料",
        category="方法论",
        source_type="task",
        source_object_id=task_id,
        sandbox_id=workspace_id,
        now="2026-06-24T00:01:00Z",
    )
    db.execute(
        "UPDATE exp_wall_quotes SET author_display_name = ? WHERE id IN (?, ?)",
        ("金句作者", first_id, second_id),
    )

    response = client.get("/api/v1/growth/experience-wall?refreshCloud=false")
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    matched = [item for item in items if "源头" in item["text"]]
    assert len(matched) == 1
    assert matched[0]["authorUserName"] == "金句作者"


def test_experience_wall_duplicate_group_does_not_let_legacy_local_copy_steal_employee_author(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    workspace_id = create_workspace(client, "org-growth-legacy-author-display")

    cloud_id = insert_quote(
        db,
        author_user_id="emp_linjiawei",
        author_display_name="林佳维",
        quote_text="遇到反复调整仍不达标的问题要先查根源，源头错了下游怎么改都没用",
        source_excerpt="云端旧副本",
        category="方法论",
        source_type="client_analysis",
        source_object_id="",
        sandbox_id=workspace_id,
        now="2026-06-25T18:39:03",
    )
    local_id = insert_quote(
        db,
        author_user_id="user_guyuan",
        author_display_name="顾源源",
        quote_text="遇到反复修改仍不符合预期的问题，要先排查源头，源头出错下游怎么改都不彻底",
        source_excerpt="本地复盘原始提炼",
        category="方法论",
        source_type="client_analysis",
        source_object_id="",
        sandbox_id=workspace_id,
        now="2026-06-25T18:21:06",
    )
    db.execute("UPDATE exp_wall_quotes SET like_count = 1, hot_score = 6 WHERE id = ?", (cloud_id,))

    response = client.get("/api/v1/growth/experience-wall?refreshCloud=false")
    assert response.status_code == 200, response.text
    matched = [item for item in response.json()["items"] if "源头" in item["text"] or "根源" in item["text"]]
    assert len(matched) == 1
    assert matched[0]["id"] == cloud_id
    assert matched[0]["authorUserId"] == "emp_linjiawei"
    assert matched[0]["authorUserName"] == "林佳维"
    assert matched[0]["likeCount"] == 1


def test_experience_wall_falls_back_to_historical_author_display_name(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    workspace_id = create_workspace(client, "org-growth-author-fallback")

    insert_quote(
        db,
        author_user_id="cloud_user_legacy",
        quote_text="第一条带作者的历史金句",
        source_excerpt="历史材料",
        category="方法论",
        source_type="client_analysis",
        source_object_id="",
        sandbox_id=workspace_id,
        author_display_name="历史作者",
        now="2026-06-23T00:00:00Z",
    )
    insert_quote(
        db,
        author_user_id="cloud_user_legacy",
        quote_text="第二条没有作者名但同属一人",
        source_excerpt="新材料",
        category="方法论",
        source_type="client_analysis",
        source_object_id="",
        sandbox_id=workspace_id,
        now="2026-06-24T00:00:00Z",
    )

    response = client.get("/api/v1/growth/experience-wall?refreshCloud=false")
    assert response.status_code == 200, response.text
    matched = [item for item in response.json()["items"] if item["text"] == "第二条没有作者名但同属一人"]
    assert len(matched) == 1
    assert matched[0]["authorUserName"] == "历史作者"


def test_experience_wall_backfills_legacy_review_quote_author_from_consistent_task_owner(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    workspace_id = create_workspace(client, "org-growth-review-author")
    task_id = create_task_record(client, "手机和电脑的日程交互同步")
    review_id = "review_owner_infer"
    note = (
        "日程的同步功能打通后，飞书与软件的关系更加明确：飞书作为桥梁、中转站，"
        "手机端操作是为了及时沉淀想法，电脑端操作适合日常办公。"
    )
    db.execute(
        """
        INSERT INTO weekly_reviews(id, week_label, operator_id, summary, work_free_note, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        (review_id, "2026-W25", "op_qh", "复盘摘要", note, "2026-06-22T13:57:08", "2026-06-22T13:57:08"),
    )
    db.execute(
        """
        INSERT INTO weekly_review_task_entries(
            id, review_id, task_id, user_id, week_label, content_domain, note,
            structured_note_json, reviewed_at, task_snapshot_json, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "review_item_owner_infer",
            review_id,
            task_id,
            "",
            "2026-W25",
            "work",
            note,
            json.dumps({"reflection": note}, ensure_ascii=False),
            "2026-06-22T13:57:08",
            json.dumps({"title": "手机和电脑的日程交互同步", "ownerId": "emp_linjiawei", "ownerName": "林佳维"}, ensure_ascii=False),
            "2026-06-22T13:57:08",
            "2026-06-22T13:57:08",
        ),
    )
    quote_id = insert_quote(
        db,
        author_user_id="user_guyuan",
        quote_text="多端日程协同可用飞书做中转站，手机端沉淀想法，电脑端适配办公场景",
        source_excerpt="周复盘",
        category="方法论",
        source_type="client_analysis",
        source_object_id="",
        sandbox_id=workspace_id,
        now="2026-06-22T13:59:45",
    )

    response = client.get("/api/v1/growth/experience-wall?refreshCloud=false")
    assert response.status_code == 200, response.text
    matched = [item for item in response.json()["items"] if item["id"] == quote_id]
    assert len(matched) == 1
    assert matched[0]["authorUserId"] == "emp_linjiawei"
    assert matched[0]["authorUserName"] == "林佳维"
    stored = db.fetchone("SELECT author_user_id, author_display_name FROM exp_wall_quotes WHERE id = ?", (quote_id,))
    assert stored["author_user_id"] == "emp_linjiawei"
    assert stored["author_display_name"] == "林佳维"

    db.execute("UPDATE weekly_review_task_entries SET user_id = ? WHERE id = ?", ("op_qh", "review_item_owner_infer"))
    db.execute(
        "UPDATE exp_wall_quotes SET author_user_id = ?, author_display_name = ? WHERE id = ?",
        ("user_guyuan", "", quote_id),
    )

    response = client.get("/api/v1/growth/experience-wall?refreshCloud=false")
    assert response.status_code == 200, response.text
    matched = [item for item in response.json()["items"] if item["id"] == quote_id]
    assert len(matched) == 1
    assert matched[0]["authorUserId"] == "op_qh"
    assert matched[0]["authorUserName"] == "庆华"
    stored = db.fetchone("SELECT author_user_id, author_display_name FROM exp_wall_quotes WHERE id = ?", (quote_id,))
    assert stored["author_user_id"] == "op_qh"
    assert stored["author_display_name"] == "庆华"


def test_experience_wall_duplicate_group_carries_current_user_like_from_any_copy(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    workspace_id = create_workspace(client, "org-growth-duplicate-like")

    representative_id = insert_quote(
        db,
        author_user_id="emp_linjiawei",
        author_display_name="林佳维",
        quote_text="遇到反复修改仍不符合预期的问题，要先排查源头，源头出错下游怎么改都不彻底",
        source_excerpt="周复盘",
        category="方法论",
        source_type="client_analysis",
        source_object_id="",
        sandbox_id=workspace_id,
        now="2026-06-25T17:13:53",
    )
    liked_copy_id = insert_quote(
        db,
        author_user_id="emp_linjiawei",
        author_display_name="林佳维",
        quote_text="遇到反复调整仍不达标的问题要先查根源，源头错了下游怎么改都没用",
        source_excerpt="周复盘",
        category="方法论",
        source_type="client_analysis",
        source_object_id="",
        sandbox_id=workspace_id,
        now="2026-06-25T18:39:03",
    )
    db.execute(
        """
        INSERT INTO exp_wall_reactions(id, sandbox_id, quote_id, user_id, reaction_type, created_at, sync_status, pending_sync_action)
        VALUES(?, ?, ?, ?, 'like', ?, 'synced', '')
        """,
        ("rx_duplicate_like", workspace_id, liked_copy_id, "op_qh", "2026-06-25T18:40:34"),
    )
    db.execute("UPDATE exp_wall_quotes SET like_count = 1, hot_score = 6 WHERE id = ?", (liked_copy_id,))

    response = client.get("/api/v1/growth/experience-wall?refreshCloud=false")
    assert response.status_code == 200, response.text
    matched = [item for item in response.json()["items"] if "源头" in item["text"] or "根源" in item["text"]]
    assert len(matched) == 1
    assert matched[0]["id"] in {representative_id, liked_copy_id}
    assert matched[0]["likeCount"] == 1
    assert matched[0]["currentUserLiked"] is True


def test_save_pending_quotes_skips_near_duplicate_ai_rewrites(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    workspace_id = create_workspace(client, "org-growth-pending-dedupe")

    saved = save_pending_quotes(
        db,
        [
            {"text": "遇到反复修改仍不符合预期的问题，要先排查源头，源头出错下游怎么改都不彻底", "source": "周复盘"},
            {"text": "反复修改仍不达预期时，先查根因；源头错了，下游再改也难以彻底解决", "source": "周复盘"},
        ],
        user_id="cloud_user_pending",
        user_name="复盘作者",
        author_display_name="复盘作者",
        sandbox_id=workspace_id,
    )

    assert saved == 1
    rows = db.fetchall(
        """
        SELECT quote_text, author_display_name
        FROM exp_wall_quotes
        WHERE author_user_id = ? AND COALESCE(sandbox_id, ?) = ?
        """,
        ("cloud_user_pending", DEFAULT_LOCAL_SANDBOX_ID, workspace_id),
    )
    assert len(rows) == 1
    assert rows[0]["author_display_name"] == "复盘作者"


def test_experience_wall_quote_can_be_liked_once_by_current_user(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    workspace_id = create_workspace(client, "org-growth-like")
    quote_id = insert_quote(
        db,
        author_user_id="cloud_user_b",
        quote_text="组织经验墙应支持成员点亮金句",
        source_excerpt="用于点赞测试",
        category="团队协作",
        source_type="task",
        source_object_id="",
        sandbox_id=workspace_id,
        now="2026-06-24T00:00:00Z",
    )

    first = client.post(f"/api/v1/growth/experience-wall/{quote_id}/like")
    assert first.status_code == 200, first.text
    assert first.json()["likeCount"] == 1
    assert first.json()["currentUserLiked"] is True

    second = client.post(f"/api/v1/growth/experience-wall/{quote_id}/like")
    assert second.status_code == 200, second.text
    assert second.json()["likeCount"] == 1
    assert second.json()["currentUserLiked"] is True


def test_growth_overview_changes_only_after_real_workspace_signal(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db

    baseline = client.get("/api/v1/growth/overview")
    assert baseline.status_code == 200, baseline.text
    baseline_payload = baseline.json()
    assert int(baseline_payload["weeklyXp"]) == 0
    assert not [entry for entry in baseline_payload["recentEntries"] if entry["sourceType"] != "badge_unlock"]
    assert all(int(ability["totalXp"]) == 0 for ability in baseline_payload["abilities"])

    user_id = str(baseline_payload["userId"])
    client_id = create_client_record(client, "真实成长客户")
    task_id = create_task_record(client, "完成一条真实任务", client_id)
    db.execute(
        """
        UPDATE tasks
        SET status = 'done', owner_id = ?, creator_id = ?, updated_at = ?
        WHERE id = ?
        """,
        (user_id, user_id, "2026-06-23T00:00:00Z", task_id),
    )

    after = client.get("/api/v1/growth/overview")
    assert after.status_code == 200, after.text
    after_payload = after.json()
    assert any(int(ability["totalXp"]) > 0 for ability in after_payload["abilities"])
    assert any(entry["sourceType"] == "task_done" for entry in after_payload["recentEntries"])
