# 益语软件平台源码导出（第007卷）

- 导出时间: 2026-04-20 18:08:04
- 内容范围: 主仓库源码 + mobile 子仓库源码
- 说明: 每个条目为完整源码文件。

## `cloud_backend/tests/test_task_feishu_notifications.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as cloud_main  # noqa: E402
from app.main import create_app, now_iso  # noqa: E402


def make_client(tmp_path, monkeypatch) -> TestClient:
    data_dir = tmp_path / "cloud-data"
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Qinghua123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Jianing123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Yishuo123!")
    return TestClient(create_app())


def auth_headers(client: TestClient, email: str, password: str) -> tuple[dict[str, str], dict]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    payload = response.json()
    return {"Authorization": f"Bearer {payload['accessToken']}"}, payload["user"]


def save_org_feishu_integration(client: TestClient, headers: dict[str, str], monkeypatch) -> str:
    monkeypatch.setattr(cloud_main, "_feishu_fetch_app_access_token", lambda **_: ("app_token_demo", {"code": 0}))
    response = client.post(
        "/api/v1/org-integrations/feishu/validate-and-save",
        json={
            "appId": "cli_demo_app",
            "appSecret": "secret_demo",
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["organizationId"]


def seed_member_mobile(client: TestClient, user_id: str, mobile: str) -> None:
    client.app.state.app_state.db.execute(
        "UPDATE employee_accounts SET feishu_mobile = ?, updated_at = ? WHERE id = ?",
        (mobile, now_iso(), user_id),
    )


def test_create_task_sends_card_notifications_to_phone_matched_owner_and_collaborators(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    admin_headers, admin_user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    org_id = save_org_feishu_integration(client, admin_headers, monkeypatch)
    seed_member_mobile(client, admin_user["id"], "13800138000")
    seed_member_mobile(client, "user_qinghua", "13900139000")

    sent_cards: list[dict[str, object]] = []
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(
        cloud_main,
        "_feishu_lookup_open_id_by_mobile",
        lambda *, tenant_access_token, mobile: (
            "ou_admin" if mobile == "13800138000" else "ou_qinghua" if mobile == "13900139000" else None,
            None if mobile in {"13800138000", "13900139000"} else "not found",
        ),
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_send_interactive_message",
        lambda *, tenant_access_token, receive_id_type, receive_id, card: sent_cards.append(
            {
                "token": tenant_access_token,
                "receive_id_type": receive_id_type,
                "receive_id": receive_id,
                "card": card,
            }
        ) or {"code": 0},
    )

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "【测试】飞书任务提醒",
            "description": "创建后应通知负责人和协作者",
            "priority": "normal",
            "listId": "list-0",
            "startDate": "2026-04-10",
            "dueDate": "2026-04-10T18:00",
            "collaboratorIds": [admin_user["id"], "user_qinghua"],
            "ownerId": "user_qinghua",
        },
        headers=admin_headers,
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["id"]

    assert len(sent_cards) == 2
    assert {str(item["receive_id"]) for item in sent_cards} == {"ou_admin", "ou_qinghua"}
    assert all(str(item["card"]["header"]["template"]) == "blue" for item in sent_cards)
    assert any("你的角色：负责人" in str(item["card"]["elements"][1]["content"]) for item in sent_cards)
    assert any("你的角色：协作者" in str(item["card"]["elements"][1]["content"]) for item in sent_cards)

    rows = client.app.state.app_state.db.fetchall(
        "SELECT * FROM org_feishu_task_notifications WHERE task_id = ? ORDER BY created_at ASC",
        (task_id,),
    )
    assert len(rows) == 2
    assert {str(row["delivery_status"]) for row in rows} == {"sent"}

    target_rows = client.app.state.app_state.db.fetchall(
        "SELECT user_id, match_status, receive_id FROM org_feishu_delivery_targets WHERE organization_id = ? ORDER BY user_id ASC",
        (org_id,),
    )
    status_by_user = {str(row["user_id"]): (str(row["match_status"]), str(row["receive_id"])) for row in target_rows}
    assert status_by_user[admin_user["id"]] == ("matched", "ou_admin")
    assert status_by_user["user_qinghua"] == ("matched", "ou_qinghua")

    generic_rows = client.app.state.app_state.db.fetchall(
        "SELECT delivery_status, delivery_channel FROM org_feishu_notifications WHERE object_type = 'task' AND object_id = ? ORDER BY created_at ASC",
        (task_id,),
    )
    assert len(generic_rows) == 2
    assert {str(row["delivery_status"]) for row in generic_rows} == {"sent_card"}
    assert {str(row["delivery_channel"]) for row in generic_rows} == {"interactive"}


def test_title_only_update_is_queued_then_sent_as_content_notification(tmp_path, monkeypatch):
    monkeypatch.setattr(cloud_main.FeishuNotificationService, "task_change_merge_window_seconds", 0)
    client = make_client(tmp_path, monkeypatch)
    admin_headers, admin_user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    save_org_feishu_integration(client, admin_headers, monkeypatch)
    seed_member_mobile(client, admin_user["id"], "13800138000")

    sent_cards: list[dict[str, object]] = []
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(cloud_main, "_feishu_lookup_open_id_by_mobile", lambda *, tenant_access_token, mobile: ("ou_admin", None))
    monkeypatch.setattr(
        cloud_main,
        "_feishu_send_interactive_message",
        lambda *, tenant_access_token, receive_id_type, receive_id, card: sent_cards.append({"receive_id": receive_id, "card": card}) or {"code": 0},
    )

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "只改标题延迟提醒",
            "description": "",
            "priority": "normal",
            "listId": "list-0",
            "collaboratorIds": [admin_user["id"]],
            "ownerId": admin_user["id"],
        },
        headers=admin_headers,
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["id"]
    before_count = client.app.state.app_state.db.fetchone(
        "SELECT COUNT(*) AS count FROM org_feishu_task_notifications WHERE task_id = ? AND event_type = 'content_fields_changed'",
        (task_id,),
    )["count"]
    sent_cards.clear()

    updated = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"title": "只改标题进入延迟提醒"},
        headers=admin_headers,
    )
    assert updated.status_code == 200, updated.text
    assert sent_cards == []

    queued_rows = client.app.state.app_state.db.fetchall(
        "SELECT message_type, delivery_status FROM org_feishu_notifications WHERE object_type = 'task' AND object_id = ? ORDER BY created_at ASC",
        (task_id,),
    )
    assert any(str(row["message_type"]) == "task_content_changed" and str(row["delivery_status"]) == "queued" for row in queued_rows)

    client.app.state.app_state.feishu_notifications.process_due_notifications()

    assert len(sent_cards) == 1
    assert sent_cards[0]["receive_id"] == "ou_admin"
    assert "任务内容已更新" in str(sent_cards[0]["card"]["header"]["title"]["content"])
    assert "变更项：标题" in str(sent_cards[0]["card"]["elements"][1]["content"])

    after_count = client.app.state.app_state.db.fetchone(
        "SELECT COUNT(*) AS count FROM org_feishu_task_notifications WHERE task_id = ? AND event_type = 'content_fields_changed'",
        (task_id,),
    )["count"]
    assert after_count == before_count + 1


def test_key_field_changes_send_immediately_and_missing_mobile_recipients_are_skipped(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    admin_headers, admin_user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    save_org_feishu_integration(client, admin_headers, monkeypatch)
    seed_member_mobile(client, admin_user["id"], "13800138000")
    seed_member_mobile(client, "user_qinghua", "13900139000")

    sent_cards: list[dict[str, object]] = []
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(
        cloud_main,
        "_feishu_lookup_open_id_by_mobile",
        lambda *, tenant_access_token, mobile: (
            "ou_admin" if mobile == "13800138000" else "ou_qinghua" if mobile == "13900139000" else None,
            None if mobile in {"13800138000", "13900139000"} else "not found",
        ),
    )
    monkeypatch.setattr(
        cloud_main,
        "_feishu_send_interactive_message",
        lambda *, tenant_access_token, receive_id_type, receive_id, card: sent_cards.append(
            {
                "receive_id": receive_id,
                "card": card,
            }
        ) or {"code": 0},
    )

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "【测试】变更任务提醒",
            "description": "",
            "priority": "normal",
            "listId": "list-0",
            "startDate": "2026-04-10",
            "dueDate": "2026-04-10T10:00",
            "collaboratorIds": [admin_user["id"], "user_qinghua"],
            "ownerId": admin_user["id"],
        },
        headers=admin_headers,
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["id"]
    sent_cards.clear()

    updated = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={
            "dueDate": "2026-04-11T14:30",
            "ownerId": "user_qinghua",
            "collaboratorIds": ["user_qinghua", "user_jianing"],
        },
        headers=admin_headers,
    )
    assert updated.status_code == 200, updated.text

    assert len(sent_cards) == 1
    assert sent_cards[0]["receive_id"] == "ou_qinghua"
    assert "变更项：截止时间、负责人、协作者" in str(sent_cards[0]["card"]["elements"][1]["content"])

    rows = client.app.state.app_state.db.fetchall(
        "SELECT recipient_user_id, delivery_status, changed_fields_json, delivery_message FROM org_feishu_task_notifications WHERE task_id = ? AND event_type = 'key_fields_changed' ORDER BY recipient_user_id ASC",
        (task_id,),
    )
    assert len(rows) == 2
    status_by_user = {str(row["recipient_user_id"]): str(row["delivery_status"]) for row in rows}
    assert status_by_user == {"user_jianing": "skipped_unbound", "user_qinghua": "sent"}
    assert any("成员尚未填写飞书手机号" in str(row["delivery_message"]) for row in rows if str(row["recipient_user_id"]) == "user_jianing")
    assert all("dueDate" in str(row["changed_fields_json"]) for row in rows)
    assert all("ownerId" in str(row["changed_fields_json"]) for row in rows)
    assert all("collaboratorIds" in str(row["changed_fields_json"]) for row in rows)

    queued_rows = client.app.state.app_state.db.fetchall(
        "SELECT delivery_status, recipient_user_id FROM org_feishu_notifications WHERE object_type = 'task' AND object_id = ? AND message_type = 'task_changed' ORDER BY recipient_user_id ASC",
        (task_id,),
    )
    assert {str(row["delivery_status"]) for row in queued_rows} == {"sent_card", "skipped_unbound"}


def test_immediate_change_absorbs_pending_content_change_into_one_notification(tmp_path, monkeypatch):
    monkeypatch.setattr(cloud_main.FeishuNotificationService, "task_change_merge_window_seconds", 999)
    client = make_client(tmp_path, monkeypatch)
    admin_headers, admin_user = auth_headers(client, "admin@yiyu-system.com", "Admin123!")
    save_org_feishu_integration(client, admin_headers, monkeypatch)
    seed_member_mobile(client, admin_user["id"], "13800138000")

    sent_cards: list[dict[str, object]] = []
    monkeypatch.setattr(cloud_main, "_feishu_fetch_tenant_access_token", lambda **_: ("tenant_demo", {"code": 0}))
    monkeypatch.setattr(cloud_main, "_feishu_lookup_open_id_by_mobile", lambda *, tenant_access_token, mobile: ("ou_admin", None))
    monkeypatch.setattr(
        cloud_main,
        "_feishu_send_interactive_message",
        lambda *, tenant_access_token, receive_id_type, receive_id, card: sent_cards.append({"receive_id": receive_id, "card": card}) or {"code": 0},
    )

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "混合变更任务",
            "description": "",
            "priority": "normal",
            "listId": "list-0",
            "collaboratorIds": [admin_user["id"]],
            "ownerId": admin_user["id"],
        },
        headers=admin_headers,
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["id"]
    sent_cards.clear()

    title_updated = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"title": "标题先改一下"},
        headers=admin_headers,
    )
    assert title_updated.status_code == 200, title_updated.text
    assert sent_cards == []

    due_updated = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"dueDate": "2026-04-11T11:30"},
        headers=admin_headers,
    )
    assert due_updated.status_code == 200, due_updated.text

    assert len(sent_cards) == 1
    merged_card_text = str(sent_cards[0]["card"]["elements"][1]["content"])
    assert "变更项：标题、截止时间" in merged_card_text or "变更项：截止时间、标题" in merged_card_text

    queued_rows = client.app.state.app_state.db.fetchall(
        "SELECT delivery_status, delivery_message FROM org_feishu_notifications WHERE object_type = 'task' AND object_id = ? AND message_type = 'task_content_changed' ORDER BY created_at ASC",
        (task_id,),
    )
    assert len(queued_rows) == 1
    assert str(queued_rows[0]["delivery_status"]) == "cancelled"
    assert "已并入一次即时任务更新提醒" in str(queued_rows[0]["delivery_message"])
~~~

## `cloud_backend/tests/test_task_pressure_seed.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database  # noqa: E402
from app.task_pressure_seed import parse_pressure_seed_markdown, seed_task_pressure_doc  # noqa: E402


SAMPLE_MARKDOWN = """
```yaml
name:
department:
manager:
```

```yaml
name: 庆华
department: 咨询策略部
manager: 庆华
role_type: manager
week: 2026-03-09~2026-03-15
linked_quarter_goals: [Q1-G2, Q1-G4]
weekly_plan:
  - task_id: ZL-QH-01
    title: 输出客户策略备忘录
    customer_or_project: 蓝信封
    priority: P0
    due_date: 2026-03-12
    expected_output: 备忘录V1
    linked_goal: Q1-G2
weekly_review:
  overall_status: 1项完成
  key_results:
    - 已完成关键判断
  key_learnings:
    - 资料充分时判断更快
  support_needed:
    - 需要客户补更多背景
  tasks:
    - task_id: ZL-QH-01
      status: 完成
      result: 已输出备忘录V1
      reflection: 前置信息足够时推进明显更顺
      support_needed: 无
```

```yaml
name: 苏妍
department: 咨询策略部
manager: 庆华
role_type: member
week: 2026-03-09~2026-03-15
linked_quarter_goals: [Q1-G2]
weekly_plan:
  - task_id: ZL-SY-01
    title: 梳理用户画像差异
    customer_or_project: 蓝信封
    priority: P1
    due_date: 2026-03-11
    expected_output: 画像差异表
    linked_goal: Q1-G2
weekly_review:
  overall_status: 1项部分完成
  key_results:
    - 已形成初版对比
  key_learnings:
    - 平台差异很大
  support_needed:
    - 需要大周补更多评论样本
  tasks:
    - task_id: ZL-SY-01
      status: 部分完成
      result: 已完成初版对比，仍需补样本
      reflection: 数据不足时假设容易漂
      support_needed: 需要大周补更多评论样本
```
"""


def test_parse_pressure_seed_markdown_skips_template_block(tmp_path: Path):
    markdown_path = tmp_path / "seed.md"
    markdown_path.write_text(SAMPLE_MARKDOWN, encoding="utf-8")

    employees = parse_pressure_seed_markdown(markdown_path)

    assert len(employees) == 2
    assert employees[0].name == "庆华"
    assert employees[1].tasks[0].task_id == "ZL-SY-01"


def test_seed_task_pressure_doc_populates_tasks_reviews_and_collaboration(tmp_path: Path):
    markdown_path = tmp_path / "seed.md"
    markdown_path.write_text(SAMPLE_MARKDOWN, encoding="utf-8")
    db = Database(tmp_path / "cloud.db")
    db.execute(
        "INSERT INTO organizations(id, name, slug, created_at, updated_at) VALUES('org_test', '测试组织', 'test-org', '2026-03-01T00:00:00', '2026-03-01T00:00:00')"
    )

    summary = seed_task_pressure_doc(
        db,
        markdown_path=markdown_path,
        organization_id="org_test",
        replace_all=True,
        expected_employee_count=2,
    )

    assert summary["employeeCount"] == 2
    assert summary["taskCount"] == 2
    assert db.scalar("SELECT COUNT(1) AS count FROM tasks WHERE source_type = 'pressure_seed_doc_v2'") == 2
    assert db.scalar("SELECT COUNT(1) AS count FROM weekly_review_entries") == 2
    assert db.scalar("SELECT COUNT(1) AS count FROM weekly_review_task_entries") == 2
    assert db.scalar("SELECT COUNT(1) AS count FROM task_collaborators WHERE task_id = 'ZL-SY-01' AND user_id = 'user_qinghua'") == 1
~~~

## `cloud_backend/uv.lock`

- 编码: `utf-8`

~~~text
version = 1
revision = 3
requires-python = ">=3.11"
resolution-markers = [
    "python_full_version >= '3.14'",
    "python_full_version == '3.13.*'",
    "python_full_version < '3.13'",
]

[[package]]
name = "annotated-doc"
version = "0.0.4"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/57/ba/046ceea27344560984e26a590f90bc7f4a75b06701f653222458922b558c/annotated_doc-0.0.4.tar.gz", hash = "sha256:fbcda96e87e9c92ad167c2e53839e57503ecfda18804ea28102353485033faa4", size = 7288, upload-time = "2025-11-10T22:07:42.062Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/1e/d3/26bf1008eb3d2daa8ef4cacc7f3bfdc11818d111f7e2d0201bc6e3b49d45/annotated_doc-0.0.4-py3-none-any.whl", hash = "sha256:571ac1dc6991c450b25a9c2d84a3705e2ae7a53467b5d111c24fa8baabbed320", size = 5303, upload-time = "2025-11-10T22:07:40.673Z" },
]

[[package]]
name = "annotated-types"
version = "0.7.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/ee/67/531ea369ba64dcff5ec9c3402f9f51bf748cec26dde048a2f973a4eea7f5/annotated_types-0.7.0.tar.gz", hash = "sha256:aff07c09a53a08bc8cfccb9c85b05f1aa9a2a6f23728d790723543408344ce89", size = 16081, upload-time = "2024-05-20T21:33:25.928Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/78/b6/6307fbef88d9b5ee7421e68d78a9f162e0da4900bc5f5793f6d3d0e34fb8/annotated_types-0.7.0-py3-none-any.whl", hash = "sha256:1f02e8b43a8fbbc3f3e0d4f0f4bfc8131bcb4eebe8849b8e5c773f3a1c582a53", size = 13643, upload-time = "2024-05-20T21:33:24.1Z" },
]

[[package]]
name = "anyio"
version = "4.12.1"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "idna" },
    { name = "typing-extensions", marker = "python_full_version < '3.13'" },
]
sdist = { url = "https://files.pythonhosted.org/packages/96/f0/5eb65b2bb0d09ac6776f2eb54adee6abe8228ea05b20a5ad0e4945de8aac/anyio-4.12.1.tar.gz", hash = "sha256:41cfcc3a4c85d3f05c932da7c26d0201ac36f72abd4435ba90d0464a3ffed703", size = 228685, upload-time = "2026-01-06T11:45:21.246Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/38/0e/27be9fdef66e72d64c0cdc3cc2823101b80585f8119b5c112c2e8f5f7dab/anyio-4.12.1-py3-none-any.whl", hash = "sha256:d405828884fc140aa80a3c667b8beed277f1dfedec42ba031bd6ac3db606ab6c", size = 113592, upload-time = "2026-01-06T11:45:19.497Z" },
]

[[package]]
name = "attrs"
version = "26.1.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/9a/8e/82a0fe20a541c03148528be8cac2408564a6c9a0cc7e9171802bc1d26985/attrs-26.1.0.tar.gz", hash = "sha256:d03ceb89cb322a8fd706d4fb91940737b6642aa36998fe130a9bc96c985eff32", size = 952055, upload-time = "2026-03-19T14:22:25.026Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/64/b4/17d4b0b2a2dc85a6df63d1157e028ed19f90d4cd97c36717afef2bc2f395/attrs-26.1.0-py3-none-any.whl", hash = "sha256:c647aa4a12dfbad9333ca4e71fe62ddc36f4e63b2d260a37a8b83d2f043ac309", size = 67548, upload-time = "2026-03-19T14:22:23.645Z" },
]

[[package]]
name = "bcrypt"
version = "5.0.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/d4/36/3329e2518d70ad8e2e5817d5a4cac6bba05a47767ec416c7d020a965f408/bcrypt-5.0.0.tar.gz", hash = "sha256:f748f7c2d6fd375cc93d3fba7ef4a9e3a092421b8dbf34d8d4dc06be9492dfdd", size = 25386, upload-time = "2025-09-25T19:50:47.829Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/13/85/3e65e01985fddf25b64ca67275bb5bdb4040bd1a53b66d355c6c37c8a680/bcrypt-5.0.0-cp313-cp313t-macosx_10_12_universal2.whl", hash = "sha256:f3c08197f3039bec79cee59a606d62b96b16669cff3949f21e74796b6e3cd2be", size = 481806, upload-time = "2025-09-25T19:49:05.102Z" },
    { url = "https://files.pythonhosted.org/packages/44/dc/01eb79f12b177017a726cbf78330eb0eb442fae0e7b3dfd84ea2849552f3/bcrypt-5.0.0-cp313-cp313t-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:200af71bc25f22006f4069060c88ed36f8aa4ff7f53e67ff04d2ab3f1e79a5b2", size = 268626, upload-time = "2025-09-25T19:49:06.723Z" },
    { url = "https://files.pythonhosted.org/packages/8c/cf/e82388ad5959c40d6afd94fb4743cc077129d45b952d46bdc3180310e2df/bcrypt-5.0.0-cp313-cp313t-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:baade0a5657654c2984468efb7d6c110db87ea63ef5a4b54732e7e337253e44f", size = 271853, upload-time = "2025-09-25T19:49:08.028Z" },
    { url = "https://files.pythonhosted.org/packages/ec/86/7134b9dae7cf0efa85671651341f6afa695857fae172615e960fb6a466fa/bcrypt-5.0.0-cp313-cp313t-manylinux_2_28_aarch64.whl", hash = "sha256:c58b56cdfb03202b3bcc9fd8daee8e8e9b6d7e3163aa97c631dfcfcc24d36c86", size = 269793, upload-time = "2025-09-25T19:49:09.727Z" },
    { url = "https://files.pythonhosted.org/packages/cc/82/6296688ac1b9e503d034e7d0614d56e80c5d1a08402ff856a4549cb59207/bcrypt-5.0.0-cp313-cp313t-manylinux_2_28_armv7l.manylinux_2_31_armv7l.whl", hash = "sha256:4bfd2a34de661f34d0bda43c3e4e79df586e4716ef401fe31ea39d69d581ef23", size = 289930, upload-time = "2025-09-25T19:49:11.204Z" },
    { url = "https://files.pythonhosted.org/packages/d1/18/884a44aa47f2a3b88dd09bc05a1e40b57878ecd111d17e5bba6f09f8bb77/bcrypt-5.0.0-cp313-cp313t-manylinux_2_28_x86_64.whl", hash = "sha256:ed2e1365e31fc73f1825fa830f1c8f8917ca1b3ca6185773b349c20fd606cec2", size = 272194, upload-time = "2025-09-25T19:49:12.524Z" },
    { url = "https://files.pythonhosted.org/packages/0e/8f/371a3ab33c6982070b674f1788e05b656cfbf5685894acbfef0c65483a59/bcrypt-5.0.0-cp313-cp313t-manylinux_2_34_aarch64.whl", hash = "sha256:83e787d7a84dbbfba6f250dd7a5efd689e935f03dd83b0f919d39349e1f23f83", size = 269381, upload-time = "2025-09-25T19:49:14.308Z" },
    { url = "https://files.pythonhosted.org/packages/b1/34/7e4e6abb7a8778db6422e88b1f06eb07c47682313997ee8a8f9352e5a6f1/bcrypt-5.0.0-cp313-cp313t-manylinux_2_34_x86_64.whl", hash = "sha256:137c5156524328a24b9fac1cb5db0ba618bc97d11970b39184c1d87dc4bf1746", size = 271750, upload-time = "2025-09-25T19:49:15.584Z" },
    { url = "https://files.pythonhosted.org/packages/c0/1b/54f416be2499bd72123c70d98d36c6cd61a4e33d9b89562c22481c81bb30/bcrypt-5.0.0-cp313-cp313t-musllinux_1_1_aarch64.whl", hash = "sha256:38cac74101777a6a7d3b3e3cfefa57089b5ada650dce2baf0cbdd9d65db22a9e", size = 303757, upload-time = "2025-09-25T19:49:17.244Z" },
    { url = "https://files.pythonhosted.org/packages/13/62/062c24c7bcf9d2826a1a843d0d605c65a755bc98002923d01fd61270705a/bcrypt-5.0.0-cp313-cp313t-musllinux_1_1_x86_64.whl", hash = "sha256:d8d65b564ec849643d9f7ea05c6d9f0cd7ca23bdd4ac0c2dbef1104ab504543d", size = 306740, upload-time = "2025-09-25T19:49:18.693Z" },
    { url = "https://files.pythonhosted.org/packages/d5/c8/1fdbfc8c0f20875b6b4020f3c7dc447b8de60aa0be5faaf009d24242aec9/bcrypt-5.0.0-cp313-cp313t-musllinux_1_2_aarch64.whl", hash = "sha256:741449132f64b3524e95cd30e5cd3343006ce146088f074f31ab26b94e6c75ba", size = 334197, upload-time = "2025-09-25T19:49:20.523Z" },
    { url = "https://files.pythonhosted.org/packages/a6/c1/8b84545382d75bef226fbc6588af0f7b7d095f7cd6a670b42a86243183cd/bcrypt-5.0.0-cp313-cp313t-musllinux_1_2_x86_64.whl", hash = "sha256:212139484ab3207b1f0c00633d3be92fef3c5f0af17cad155679d03ff2ee1e41", size = 352974, upload-time = "2025-09-25T19:49:22.254Z" },
    { url = "https://files.pythonhosted.org/packages/10/a6/ffb49d4254ed085e62e3e5dd05982b4393e32fe1e49bb1130186617c29cd/bcrypt-5.0.0-cp313-cp313t-win32.whl", hash = "sha256:9d52ed507c2488eddd6a95bccee4e808d3234fa78dd370e24bac65a21212b861", size = 148498, upload-time = "2025-09-25T19:49:24.134Z" },
    { url = "https://files.pythonhosted.org/packages/48/a9/259559edc85258b6d5fc5471a62a3299a6aa37a6611a169756bf4689323c/bcrypt-5.0.0-cp313-cp313t-win_amd64.whl", hash = "sha256:f6984a24db30548fd39a44360532898c33528b74aedf81c26cf29c51ee47057e", size = 145853, upload-time = "2025-09-25T19:49:25.702Z" },
    { url = "https://files.pythonhosted.org/packages/2d/df/9714173403c7e8b245acf8e4be8876aac64a209d1b392af457c79e60492e/bcrypt-5.0.0-cp313-cp313t-win_arm64.whl", hash = "sha256:9fffdb387abe6aa775af36ef16f55e318dcda4194ddbf82007a6f21da29de8f5", size = 139626, upload-time = "2025-09-25T19:49:26.928Z" },
    { url = "https://files.pythonhosted.org/packages/f8/14/c18006f91816606a4abe294ccc5d1e6f0e42304df5a33710e9e8e95416e1/bcrypt-5.0.0-cp314-cp314t-macosx_10_12_universal2.whl", hash = "sha256:4870a52610537037adb382444fefd3706d96d663ac44cbb2f37e3919dca3d7ef", size = 481862, upload-time = "2025-09-25T19:49:28.365Z" },
    { url = "https://files.pythonhosted.org/packages/67/49/dd074d831f00e589537e07a0725cf0e220d1f0d5d8e85ad5bbff251c45aa/bcrypt-5.0.0-cp314-cp314t-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:48f753100931605686f74e27a7b49238122aa761a9aefe9373265b8b7aa43ea4", size = 268544, upload-time = "2025-09-25T19:49:30.39Z" },
    { url = "https://files.pythonhosted.org/packages/f5/91/50ccba088b8c474545b034a1424d05195d9fcbaaf802ab8bfe2be5a4e0d7/bcrypt-5.0.0-cp314-cp314t-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:f70aadb7a809305226daedf75d90379c397b094755a710d7014b8b117df1ebbf", size = 271787, upload-time = "2025-09-25T19:49:32.144Z" },
    { url = "https://files.pythonhosted.org/packages/aa/e7/d7dba133e02abcda3b52087a7eea8c0d4f64d3e593b4fffc10c31b7061f3/bcrypt-5.0.0-cp314-cp314t-manylinux_2_28_aarch64.whl", hash = "sha256:744d3c6b164caa658adcb72cb8cc9ad9b4b75c7db507ab4bc2480474a51989da", size = 269753, upload-time = "2025-09-25T19:49:33.885Z" },
    { url = "https://files.pythonhosted.org/packages/33/fc/5b145673c4b8d01018307b5c2c1fc87a6f5a436f0ad56607aee389de8ee3/bcrypt-5.0.0-cp314-cp314t-manylinux_2_28_armv7l.manylinux_2_31_armv7l.whl", hash = "sha256:a28bc05039bdf3289d757f49d616ab3efe8cf40d8e8001ccdd621cd4f98f4fc9", size = 289587, upload-time = "2025-09-25T19:49:35.144Z" },
    { url = "https://files.pythonhosted.org/packages/27/d7/1ff22703ec6d4f90e62f1a5654b8867ef96bafb8e8102c2288333e1a6ca6/bcrypt-5.0.0-cp314-cp314t-manylinux_2_28_x86_64.whl", hash = "sha256:7f277a4b3390ab4bebe597800a90da0edae882c6196d3038a73adf446c4f969f", size = 272178, upload-time = "2025-09-25T19:49:36.793Z" },
    { url = "https://files.pythonhosted.org/packages/c8/88/815b6d558a1e4d40ece04a2f84865b0fef233513bd85fd0e40c294272d62/bcrypt-5.0.0-cp314-cp314t-manylinux_2_34_aarch64.whl", hash = "sha256:79cfa161eda8d2ddf29acad370356b47f02387153b11d46042e93a0a95127493", size = 269295, upload-time = "2025-09-25T19:49:38.164Z" },
    { url = "https://files.pythonhosted.org/packages/51/8c/e0db387c79ab4931fc89827d37608c31cc57b6edc08ccd2386139028dc0d/bcrypt-5.0.0-cp314-cp314t-manylinux_2_34_x86_64.whl", hash = "sha256:a5393eae5722bcef046a990b84dff02b954904c36a194f6cfc817d7dca6c6f0b", size = 271700, upload-time = "2025-09-25T19:49:39.917Z" },
    { url = "https://files.pythonhosted.org/packages/06/83/1570edddd150f572dbe9fc00f6203a89fc7d4226821f67328a85c330f239/bcrypt-5.0.0-cp314-cp314t-musllinux_1_2_aarch64.whl", hash = "sha256:7f4c94dec1b5ab5d522750cb059bb9409ea8872d4494fd152b53cca99f1ddd8c", size = 334034, upload-time = "2025-09-25T19:49:41.227Z" },
    { url = "https://files.pythonhosted.org/packages/c9/f2/ea64e51a65e56ae7a8a4ec236c2bfbdd4b23008abd50ac33fbb2d1d15424/bcrypt-5.0.0-cp314-cp314t-musllinux_1_2_x86_64.whl", hash = "sha256:0cae4cb350934dfd74c020525eeae0a5f79257e8a201c0c176f4b84fdbf2a4b4", size = 352766, upload-time = "2025-09-25T19:49:43.08Z" },
    { url = "https://files.pythonhosted.org/packages/d7/d4/1a388d21ee66876f27d1a1f41287897d0c0f1712ef97d395d708ba93004c/bcrypt-5.0.0-cp314-cp314t-win32.whl", hash = "sha256:b17366316c654e1ad0306a6858e189fc835eca39f7eb2cafd6aaca8ce0c40a2e", size = 152449, upload-time = "2025-09-25T19:49:44.971Z" },
    { url = "https://files.pythonhosted.org/packages/3f/61/3291c2243ae0229e5bca5d19f4032cecad5dfb05a2557169d3a69dc0ba91/bcrypt-5.0.0-cp314-cp314t-win_amd64.whl", hash = "sha256:92864f54fb48b4c718fc92a32825d0e42265a627f956bc0361fe869f1adc3e7d", size = 149310, upload-time = "2025-09-25T19:49:46.162Z" },
    { url = "https://files.pythonhosted.org/packages/3e/89/4b01c52ae0c1a681d4021e5dd3e45b111a8fb47254a274fa9a378d8d834b/bcrypt-5.0.0-cp314-cp314t-win_arm64.whl", hash = "sha256:dd19cf5184a90c873009244586396a6a884d591a5323f0e8a5922560718d4993", size = 143761, upload-time = "2025-09-25T19:49:47.345Z" },
    { url = "https://files.pythonhosted.org/packages/84/29/6237f151fbfe295fe3e074ecc6d44228faa1e842a81f6d34a02937ee1736/bcrypt-5.0.0-cp38-abi3-macosx_10_12_universal2.whl", hash = "sha256:fc746432b951e92b58317af8e0ca746efe93e66555f1b40888865ef5bf56446b", size = 494553, upload-time = "2025-09-25T19:49:49.006Z" },
    { url = "https://files.pythonhosted.org/packages/45/b6/4c1205dde5e464ea3bd88e8742e19f899c16fa8916fb8510a851fae985b5/bcrypt-5.0.0-cp38-abi3-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:c2388ca94ffee269b6038d48747f4ce8df0ffbea43f31abfa18ac72f0218effb", size = 275009, upload-time = "2025-09-25T19:49:50.581Z" },
    { url = "https://files.pythonhosted.org/packages/3b/71/427945e6ead72ccffe77894b2655b695ccf14ae1866cd977e185d606dd2f/bcrypt-5.0.0-cp38-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:560ddb6ec730386e7b3b26b8b4c88197aaed924430e7b74666a586ac997249ef", size = 278029, upload-time = "2025-09-25T19:49:52.533Z" },
    { url = "https://files.pythonhosted.org/packages/17/72/c344825e3b83c5389a369c8a8e58ffe1480b8a699f46c127c34580c4666b/bcrypt-5.0.0-cp38-abi3-manylinux_2_28_aarch64.whl", hash = "sha256:d79e5c65dcc9af213594d6f7f1fa2c98ad3fc10431e7aa53c176b441943efbdd", size = 275907, upload-time = "2025-09-25T19:49:54.709Z" },
    { url = "https://files.pythonhosted.org/packages/0b/7e/d4e47d2df1641a36d1212e5c0514f5291e1a956a7749f1e595c07a972038/bcrypt-5.0.0-cp38-abi3-manylinux_2_28_armv7l.manylinux_2_31_armv7l.whl", hash = "sha256:2b732e7d388fa22d48920baa267ba5d97cca38070b69c0e2d37087b381c681fd", size = 296500, upload-time = "2025-09-25T19:49:56.013Z" },
    { url = "https://files.pythonhosted.org/packages/0f/c3/0ae57a68be2039287ec28bc463b82e4b8dc23f9d12c0be331f4782e19108/bcrypt-5.0.0-cp38-abi3-manylinux_2_28_x86_64.whl", hash = "sha256:0c8e093ea2532601a6f686edbc2c6b2ec24131ff5c52f7610dd64fa4553b5464", size = 278412, upload-time = "2025-09-25T19:49:57.356Z" },
    { url = "https://files.pythonhosted.org/packages/45/2b/77424511adb11e6a99e3a00dcc7745034bee89036ad7d7e255a7e47be7d8/bcrypt-5.0.0-cp38-abi3-manylinux_2_34_aarch64.whl", hash = "sha256:5b1589f4839a0899c146e8892efe320c0fa096568abd9b95593efac50a87cb75", size = 275486, upload-time = "2025-09-25T19:49:59.116Z" },
    { url = "https://files.pythonhosted.org/packages/43/0a/405c753f6158e0f3f14b00b462d8bca31296f7ecfc8fc8bc7919c0c7d73a/bcrypt-5.0.0-cp38-abi3-manylinux_2_34_x86_64.whl", hash = "sha256:89042e61b5e808b67daf24a434d89bab164d4de1746b37a8d173b6b14f3db9ff", size = 277940, upload-time = "2025-09-25T19:50:00.869Z" },
    { url = "https://files.pythonhosted.org/packages/62/83/b3efc285d4aadc1fa83db385ec64dcfa1707e890eb42f03b127d66ac1b7b/bcrypt-5.0.0-cp38-abi3-musllinux_1_1_aarch64.whl", hash = "sha256:e3cf5b2560c7b5a142286f69bde914494b6d8f901aaa71e453078388a50881c4", size = 310776, upload-time = "2025-09-25T19:50:02.393Z" },
    { url = "https://files.pythonhosted.org/packages/95/7d/47ee337dacecde6d234890fe929936cb03ebc4c3a7460854bbd9c97780b8/bcrypt-5.0.0-cp38-abi3-musllinux_1_1_x86_64.whl", hash = "sha256:f632fd56fc4e61564f78b46a2269153122db34988e78b6be8b32d28507b7eaeb", size = 312922, upload-time = "2025-09-25T19:50:04.232Z" },
    { url = "https://files.pythonhosted.org/packages/d6/3a/43d494dfb728f55f4e1cf8fd435d50c16a2d75493225b54c8d06122523c6/bcrypt-5.0.0-cp38-abi3-musllinux_1_2_aarch64.whl", hash = "sha256:801cad5ccb6b87d1b430f183269b94c24f248dddbbc5c1f78b6ed231743e001c", size = 341367, upload-time = "2025-09-25T19:50:05.559Z" },
    { url = "https://files.pythonhosted.org/packages/55/ab/a0727a4547e383e2e22a630e0f908113db37904f58719dc48d4622139b5c/bcrypt-5.0.0-cp38-abi3-musllinux_1_2_x86_64.whl", hash = "sha256:3cf67a804fc66fc217e6914a5635000259fbbbb12e78a99488e4d5ba445a71eb", size = 359187, upload-time = "2025-09-25T19:50:06.916Z" },
    { url = "https://files.pythonhosted.org/packages/1b/bb/461f352fdca663524b4643d8b09e8435b4990f17fbf4fea6bc2a90aa0cc7/bcrypt-5.0.0-cp38-abi3-win32.whl", hash = "sha256:3abeb543874b2c0524ff40c57a4e14e5d3a66ff33fb423529c88f180fd756538", size = 153752, upload-time = "2025-09-25T19:50:08.515Z" },
    { url = "https://files.pythonhosted.org/packages/41/aa/4190e60921927b7056820291f56fc57d00d04757c8b316b2d3c0d1d6da2c/bcrypt-5.0.0-cp38-abi3-win_amd64.whl", hash = "sha256:35a77ec55b541e5e583eb3436ffbbf53b0ffa1fa16ca6782279daf95d146dcd9", size = 150881, upload-time = "2025-09-25T19:50:09.742Z" },
    { url = "https://files.pythonhosted.org/packages/54/12/cd77221719d0b39ac0b55dbd39358db1cd1246e0282e104366ebbfb8266a/bcrypt-5.0.0-cp38-abi3-win_arm64.whl", hash = "sha256:cde08734f12c6a4e28dc6755cd11d3bdfea608d93d958fffbe95a7026ebe4980", size = 144931, upload-time = "2025-09-25T19:50:11.016Z" },
    { url = "https://files.pythonhosted.org/packages/5d/ba/2af136406e1c3839aea9ecadc2f6be2bcd1eff255bd451dd39bcf302c47a/bcrypt-5.0.0-cp39-abi3-macosx_10_12_universal2.whl", hash = "sha256:0c418ca99fd47e9c59a301744d63328f17798b5947b0f791e9af3c1c499c2d0a", size = 495313, upload-time = "2025-09-25T19:50:12.309Z" },
    { url = "https://files.pythonhosted.org/packages/ac/ee/2f4985dbad090ace5ad1f7dd8ff94477fe089b5fab2040bd784a3d5f187b/bcrypt-5.0.0-cp39-abi3-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:ddb4e1500f6efdd402218ffe34d040a1196c072e07929b9820f363a1fd1f4191", size = 275290, upload-time = "2025-09-25T19:50:13.673Z" },
    { url = "https://files.pythonhosted.org/packages/e4/6e/b77ade812672d15cf50842e167eead80ac3514f3beacac8902915417f8b7/bcrypt-5.0.0-cp39-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:7aeef54b60ceddb6f30ee3db090351ecf0d40ec6e2abf41430997407a46d2254", size = 278253, upload-time = "2025-09-25T19:50:15.089Z" },
    { url = "https://files.pythonhosted.org/packages/36/c4/ed00ed32f1040f7990dac7115f82273e3c03da1e1a1587a778d8cea496d8/bcrypt-5.0.0-cp39-abi3-manylinux_2_28_aarch64.whl", hash = "sha256:f0ce778135f60799d89c9693b9b398819d15f1921ba15fe719acb3178215a7db", size = 276084, upload-time = "2025-09-25T19:50:16.699Z" },
    { url = "https://files.pythonhosted.org/packages/e7/c4/fa6e16145e145e87f1fa351bbd54b429354fd72145cd3d4e0c5157cf4c70/bcrypt-5.0.0-cp39-abi3-manylinux_2_28_armv7l.manylinux_2_31_armv7l.whl", hash = "sha256:a71f70ee269671460b37a449f5ff26982a6f2ba493b3eabdd687b4bf35f875ac", size = 297185, upload-time = "2025-09-25T19:50:18.525Z" },
    { url = "https://files.pythonhosted.org/packages/24/b4/11f8a31d8b67cca3371e046db49baa7c0594d71eb40ac8121e2fc0888db0/bcrypt-5.0.0-cp39-abi3-manylinux_2_28_x86_64.whl", hash = "sha256:f8429e1c410b4073944f03bd778a9e066e7fad723564a52ff91841d278dfc822", size = 278656, upload-time = "2025-09-25T19:50:19.809Z" },
    { url = "https://files.pythonhosted.org/packages/ac/31/79f11865f8078e192847d2cb526e3fa27c200933c982c5b2869720fa5fce/bcrypt-5.0.0-cp39-abi3-manylinux_2_34_aarch64.whl", hash = "sha256:edfcdcedd0d0f05850c52ba3127b1fce70b9f89e0fe5ff16517df7e81fa3cbb8", size = 275662, upload-time = "2025-09-25T19:50:21.567Z" },
    { url = "https://files.pythonhosted.org/packages/d4/8d/5e43d9584b3b3591a6f9b68f755a4da879a59712981ef5ad2a0ac1379f7a/bcrypt-5.0.0-cp39-abi3-manylinux_2_34_x86_64.whl", hash = "sha256:611f0a17aa4a25a69362dcc299fda5c8a3d4f160e2abb3831041feb77393a14a", size = 278240, upload-time = "2025-09-25T19:50:23.305Z" },
    { url = "https://files.pythonhosted.org/packages/89/48/44590e3fc158620f680a978aafe8f87a4c4320da81ed11552f0323aa9a57/bcrypt-5.0.0-cp39-abi3-musllinux_1_1_aarch64.whl", hash = "sha256:db99dca3b1fdc3db87d7c57eac0c82281242d1eabf19dcb8a6b10eb29a2e72d1", size = 311152, upload-time = "2025-09-25T19:50:24.597Z" },
    { url = "https://files.pythonhosted.org/packages/5f/85/e4fbfc46f14f47b0d20493669a625da5827d07e8a88ee460af6cd9768b44/bcrypt-5.0.0-cp39-abi3-musllinux_1_1_x86_64.whl", hash = "sha256:5feebf85a9cefda32966d8171f5db7e3ba964b77fdfe31919622256f80f9cf42", size = 313284, upload-time = "2025-09-25T19:50:26.268Z" },
    { url = "https://files.pythonhosted.org/packages/25/ae/479f81d3f4594456a01ea2f05b132a519eff9ab5768a70430fa1132384b1/bcrypt-5.0.0-cp39-abi3-musllinux_1_2_aarch64.whl", hash = "sha256:3ca8a166b1140436e058298a34d88032ab62f15aae1c598580333dc21d27ef10", size = 341643, upload-time = "2025-09-25T19:50:28.02Z" },
    { url = "https://files.pythonhosted.org/packages/df/d2/36a086dee1473b14276cd6ea7f61aef3b2648710b5d7f1c9e032c29b859f/bcrypt-5.0.0-cp39-abi3-musllinux_1_2_x86_64.whl", hash = "sha256:61afc381250c3182d9078551e3ac3a41da14154fbff647ddf52a769f588c4172", size = 359698, upload-time = "2025-09-25T19:50:31.347Z" },
    { url = "https://files.pythonhosted.org/packages/c0/f6/688d2cd64bfd0b14d805ddb8a565e11ca1fb0fd6817175d58b10052b6d88/bcrypt-5.0.0-cp39-abi3-win32.whl", hash = "sha256:64d7ce196203e468c457c37ec22390f1a61c85c6f0b8160fd752940ccfb3a683", size = 153725, upload-time = "2025-09-25T19:50:34.384Z" },
    { url = "https://files.pythonhosted.org/packages/9f/b9/9d9a641194a730bda138b3dfe53f584d61c58cd5230e37566e83ec2ffa0d/bcrypt-5.0.0-cp39-abi3-win_amd64.whl", hash = "sha256:64ee8434b0da054d830fa8e89e1c8bf30061d539044a39524ff7dec90481e5c2", size = 150912, upload-time = "2025-09-25T19:50:35.69Z" },
    { url = "https://files.pythonhosted.org/packages/27/44/d2ef5e87509158ad2187f4dd0852df80695bb1ee0cfe0a684727b01a69e0/bcrypt-5.0.0-cp39-abi3-win_arm64.whl", hash = "sha256:f2347d3534e76bf50bca5500989d6c1d05ed64b440408057a37673282c654927", size = 144953, upload-time = "2025-09-25T19:50:37.32Z" },
    { url = "https://files.pythonhosted.org/packages/8a/75/4aa9f5a4d40d762892066ba1046000b329c7cd58e888a6db878019b282dc/bcrypt-5.0.0-pp311-pypy311_pp73-manylinux_2_28_aarch64.whl", hash = "sha256:7edda91d5ab52b15636d9c30da87d2cc84f426c72b9dba7a9b4fe142ba11f534", size = 271180, upload-time = "2025-09-25T19:50:38.575Z" },
    { url = "https://files.pythonhosted.org/packages/54/79/875f9558179573d40a9cc743038ac2bf67dfb79cecb1e8b5d70e88c94c3d/bcrypt-5.0.0-pp311-pypy311_pp73-manylinux_2_28_x86_64.whl", hash = "sha256:046ad6db88edb3c5ece4369af997938fb1c19d6a699b9c1b27b0db432faae4c4", size = 273791, upload-time = "2025-09-25T19:50:39.913Z" },
    { url = "https://files.pythonhosted.org/packages/bc/fe/975adb8c216174bf70fc17535f75e85ac06ed5252ea077be10d9cff5ce24/bcrypt-5.0.0-pp311-pypy311_pp73-manylinux_2_34_aarch64.whl", hash = "sha256:dcd58e2b3a908b5ecc9b9df2f0085592506ac2d5110786018ee5e160f28e0911", size = 270746, upload-time = "2025-09-25T19:50:43.306Z" },
    { url = "https://files.pythonhosted.org/packages/e4/f8/972c96f5a2b6c4b3deca57009d93e946bbdbe2241dca9806d502f29dd3ee/bcrypt-5.0.0-pp311-pypy311_pp73-manylinux_2_34_x86_64.whl", hash = "sha256:6b8f520b61e8781efee73cba14e3e8c9556ccfb375623f4f97429544734545b4", size = 273375, upload-time = "2025-09-25T19:50:45.43Z" },
]

[[package]]
name = "build"
version = "1.4.2"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "colorama", marker = "os_name == 'nt'" },
    { name = "packaging" },
    { name = "pyproject-hooks" },
]
sdist = { url = "https://files.pythonhosted.org/packages/6c/1d/ab15c8ac57f4ee8778d7633bc6685f808ab414437b8644f555389cdc875e/build-1.4.2.tar.gz", hash = "sha256:35b14e1ee329c186d3f08466003521ed7685ec15ecffc07e68d706090bf161d1", size = 83433, upload-time = "2026-03-25T14:20:27.659Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/4a/57/3b7d4dd193ade4641c865bc2b93aeeb71162e81fc348b8dad020215601ed/build-1.4.2-py3-none-any.whl", hash = "sha256:7a4d8651ea877cb2a89458b1b198f2e69f536c95e89129dbf5d448045d60db88", size = 24643, upload-time = "2026-03-25T14:20:26.568Z" },
]

[[package]]
name = "certifi"
version = "2026.2.25"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/af/2d/7bf41579a8986e348fa033a31cdd0e4121114f6bce2457e8876010b092dd/certifi-2026.2.25.tar.gz", hash = "sha256:e887ab5cee78ea814d3472169153c2d12cd43b14bd03329a39a9c6e2e80bfba7", size = 155029, upload-time = "2026-02-25T02:54:17.342Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/9a/3c/c17fb3ca2d9c3acff52e30b309f538586f9f5b9c9cf454f3845fc9af4881/certifi-2026.2.25-py3-none-any.whl", hash = "sha256:027692e4402ad994f1c42e52a4997a9763c646b73e4096e4d5d6db8af1d6f0fa", size = 153684, upload-time = "2026-02-25T02:54:15.766Z" },
]

[[package]]
name = "cffi"
version = "2.0.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "pycparser", marker = "implementation_name != 'PyPy'" },
]
sdist = { url = "https://files.pythonhosted.org/packages/eb/56/b1ba7935a17738ae8453301356628e8147c79dbb825bcbc73dc7401f9846/cffi-2.0.0.tar.gz", hash = "sha256:44d1b5909021139fe36001ae048dbdde8214afa20200eda0f64c068cac5d5529", size = 523588, upload-time = "2025-09-08T23:24:04.541Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/12/4a/3dfd5f7850cbf0d06dc84ba9aa00db766b52ca38d8b86e3a38314d52498c/cffi-2.0.0-cp311-cp311-macosx_10_13_x86_64.whl", hash = "sha256:b4c854ef3adc177950a8dfc81a86f5115d2abd545751a304c5bcf2c2c7283cfe", size = 184344, upload-time = "2025-09-08T23:22:26.456Z" },
    { url = "https://files.pythonhosted.org/packages/4f/8b/f0e4c441227ba756aafbe78f117485b25bb26b1c059d01f137fa6d14896b/cffi-2.0.0-cp311-cp311-macosx_11_0_arm64.whl", hash = "sha256:2de9a304e27f7596cd03d16f1b7c72219bd944e99cc52b84d0145aefb07cbd3c", size = 180560, upload-time = "2025-09-08T23:22:28.197Z" },
    { url = "https://files.pythonhosted.org/packages/b1/b7/1200d354378ef52ec227395d95c2576330fd22a869f7a70e88e1447eb234/cffi-2.0.0-cp311-cp311-manylinux1_i686.manylinux2014_i686.manylinux_2_17_i686.manylinux_2_5_i686.whl", hash = "sha256:baf5215e0ab74c16e2dd324e8ec067ef59e41125d3eade2b863d294fd5035c92", size = 209613, upload-time = "2025-09-08T23:22:29.475Z" },
    { url = "https://files.pythonhosted.org/packages/b8/56/6033f5e86e8cc9bb629f0077ba71679508bdf54a9a5e112a3c0b91870332/cffi-2.0.0-cp311-cp311-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:730cacb21e1bdff3ce90babf007d0a0917cc3e6492f336c2f0134101e0944f93", size = 216476, upload-time = "2025-09-08T23:22:31.063Z" },
    { url = "https://files.pythonhosted.org/packages/dc/7f/55fecd70f7ece178db2f26128ec41430d8720f2d12ca97bf8f0a628207d5/cffi-2.0.0-cp311-cp311-manylinux2014_ppc64le.manylinux_2_17_ppc64le.whl", hash = "sha256:6824f87845e3396029f3820c206e459ccc91760e8fa24422f8b0c3d1731cbec5", size = 203374, upload-time = "2025-09-08T23:22:32.507Z" },
    { url = "https://files.pythonhosted.org/packages/84/ef/a7b77c8bdc0f77adc3b46888f1ad54be8f3b7821697a7b89126e829e676a/cffi-2.0.0-cp311-cp311-manylinux2014_s390x.manylinux_2_17_s390x.whl", hash = "sha256:9de40a7b0323d889cf8d23d1ef214f565ab154443c42737dfe52ff82cf857664", size = 202597, upload-time = "2025-09-08T23:22:34.132Z" },
    { url = "https://files.pythonhosted.org/packages/d7/91/500d892b2bf36529a75b77958edfcd5ad8e2ce4064ce2ecfeab2125d72d1/cffi-2.0.0-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:8941aaadaf67246224cee8c3803777eed332a19d909b47e29c9842ef1e79ac26", size = 215574, upload-time = "2025-09-08T23:22:35.443Z" },
    { url = "https://files.pythonhosted.org/packages/44/64/58f6255b62b101093d5df22dcb752596066c7e89dd725e0afaed242a61be/cffi-2.0.0-cp311-cp311-musllinux_1_2_aarch64.whl", hash = "sha256:a05d0c237b3349096d3981b727493e22147f934b20f6f125a3eba8f994bec4a9", size = 218971, upload-time = "2025-09-08T23:22:36.805Z" },
    { url = "https://files.pythonhosted.org/packages/ab/49/fa72cebe2fd8a55fbe14956f9970fe8eb1ac59e5df042f603ef7c8ba0adc/cffi-2.0.0-cp311-cp311-musllinux_1_2_i686.whl", hash = "sha256:94698a9c5f91f9d138526b48fe26a199609544591f859c870d477351dc7b2414", size = 211972, upload-time = "2025-09-08T23:22:38.436Z" },
    { url = "https://files.pythonhosted.org/packages/0b/28/dd0967a76aab36731b6ebfe64dec4e981aff7e0608f60c2d46b46982607d/cffi-2.0.0-cp311-cp311-musllinux_1_2_x86_64.whl", hash = "sha256:5fed36fccc0612a53f1d4d9a816b50a36702c28a2aa880cb8a122b3466638743", size = 217078, upload-time = "2025-09-08T23:22:39.776Z" },
    { url = "https://files.pythonhosted.org/packages/2b/c0/015b25184413d7ab0a410775fdb4a50fca20f5589b5dab1dbbfa3baad8ce/cffi-2.0.0-cp311-cp311-win32.whl", hash = "sha256:c649e3a33450ec82378822b3dad03cc228b8f5963c0c12fc3b1e0ab940f768a5", size = 172076, upload-time = "2025-09-08T23:22:40.95Z" },
    { url = "https://files.pythonhosted.org/packages/ae/8f/dc5531155e7070361eb1b7e4c1a9d896d0cb21c49f807a6c03fd63fc877e/cffi-2.0.0-cp311-cp311-win_amd64.whl", hash = "sha256:66f011380d0e49ed280c789fbd08ff0d40968ee7b665575489afa95c98196ab5", size = 182820, upload-time = "2025-09-08T23:22:42.463Z" },
    { url = "https://files.pythonhosted.org/packages/95/5c/1b493356429f9aecfd56bc171285a4c4ac8697f76e9bbbbb105e537853a1/cffi-2.0.0-cp311-cp311-win_arm64.whl", hash = "sha256:c6638687455baf640e37344fe26d37c404db8b80d037c3d29f58fe8d1c3b194d", size = 177635, upload-time = "2025-09-08T23:22:43.623Z" },
    { url = "https://files.pythonhosted.org/packages/ea/47/4f61023ea636104d4f16ab488e268b93008c3d0bb76893b1b31db1f96802/cffi-2.0.0-cp312-cp312-macosx_10_13_x86_64.whl", hash = "sha256:6d02d6655b0e54f54c4ef0b94eb6be0607b70853c45ce98bd278dc7de718be5d", size = 185271, upload-time = "2025-09-08T23:22:44.795Z" },
    { url = "https://files.pythonhosted.org/packages/df/a2/781b623f57358e360d62cdd7a8c681f074a71d445418a776eef0aadb4ab4/cffi-2.0.0-cp312-cp312-macosx_11_0_arm64.whl", hash = "sha256:8eca2a813c1cb7ad4fb74d368c2ffbbb4789d377ee5bb8df98373c2cc0dee76c", size = 181048, upload-time = "2025-09-08T23:22:45.938Z" },
    { url = "https://files.pythonhosted.org/packages/ff/df/a4f0fbd47331ceeba3d37c2e51e9dfc9722498becbeec2bd8bc856c9538a/cffi-2.0.0-cp312-cp312-manylinux1_i686.manylinux2014_i686.manylinux_2_17_i686.manylinux_2_5_i686.whl", hash = "sha256:21d1152871b019407d8ac3985f6775c079416c282e431a4da6afe7aefd2bccbe", size = 212529, upload-time = "2025-09-08T23:22:47.349Z" },
    { url = "https://files.pythonhosted.org/packages/d5/72/12b5f8d3865bf0f87cf1404d8c374e7487dcf097a1c91c436e72e6badd83/cffi-2.0.0-cp312-cp312-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:b21e08af67b8a103c71a250401c78d5e0893beff75e28c53c98f4de42f774062", size = 220097, upload-time = "2025-09-08T23:22:48.677Z" },
    { url = "https://files.pythonhosted.org/packages/c2/95/7a135d52a50dfa7c882ab0ac17e8dc11cec9d55d2c18dda414c051c5e69e/cffi-2.0.0-cp312-cp312-manylinux2014_ppc64le.manylinux_2_17_ppc64le.whl", hash = "sha256:1e3a615586f05fc4065a8b22b8152f0c1b00cdbc60596d187c2a74f9e3036e4e", size = 207983, upload-time = "2025-09-08T23:22:50.06Z" },
    { url = "https://files.pythonhosted.org/packages/3a/c8/15cb9ada8895957ea171c62dc78ff3e99159ee7adb13c0123c001a2546c1/cffi-2.0.0-cp312-cp312-manylinux2014_s390x.manylinux_2_17_s390x.whl", hash = "sha256:81afed14892743bbe14dacb9e36d9e0e504cd204e0b165062c488942b9718037", size = 206519, upload-time = "2025-09-08T23:22:51.364Z" },
    { url = "https://files.pythonhosted.org/packages/78/2d/7fa73dfa841b5ac06c7b8855cfc18622132e365f5b81d02230333ff26e9e/cffi-2.0.0-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:3e17ed538242334bf70832644a32a7aae3d83b57567f9fd60a26257e992b79ba", size = 219572, upload-time = "2025-09-08T23:22:52.902Z" },
    { url = "https://files.pythonhosted.org/packages/07/e0/267e57e387b4ca276b90f0434ff88b2c2241ad72b16d31836adddfd6031b/cffi-2.0.0-cp312-cp312-musllinux_1_2_aarch64.whl", hash = "sha256:3925dd22fa2b7699ed2617149842d2e6adde22b262fcbfada50e3d195e4b3a94", size = 222963, upload-time = "2025-09-08T23:22:54.518Z" },
    { url = "https://files.pythonhosted.org/packages/b6/75/1f2747525e06f53efbd878f4d03bac5b859cbc11c633d0fb81432d98a795/cffi-2.0.0-cp312-cp312-musllinux_1_2_x86_64.whl", hash = "sha256:2c8f814d84194c9ea681642fd164267891702542f028a15fc97d4674b6206187", size = 221361, upload-time = "2025-09-08T23:22:55.867Z" },
    { url = "https://files.pythonhosted.org/packages/7b/2b/2b6435f76bfeb6bbf055596976da087377ede68df465419d192acf00c437/cffi-2.0.0-cp312-cp312-win32.whl", hash = "sha256:da902562c3e9c550df360bfa53c035b2f241fed6d9aef119048073680ace4a18", size = 172932, upload-time = "2025-09-08T23:22:57.188Z" },
    { url = "https://files.pythonhosted.org/packages/f8/ed/13bd4418627013bec4ed6e54283b1959cf6db888048c7cf4b4c3b5b36002/cffi-2.0.0-cp312-cp312-win_amd64.whl", hash = "sha256:da68248800ad6320861f129cd9c1bf96ca849a2771a59e0344e88681905916f5", size = 183557, upload-time = "2025-09-08T23:22:58.351Z" },
    { url = "https://files.pythonhosted.org/packages/95/31/9f7f93ad2f8eff1dbc1c3656d7ca5bfd8fb52c9d786b4dcf19b2d02217fa/cffi-2.0.0-cp312-cp312-win_arm64.whl", hash = "sha256:4671d9dd5ec934cb9a73e7ee9676f9362aba54f7f34910956b84d727b0d73fb6", size = 177762, upload-time = "2025-09-08T23:22:59.668Z" },
    { url = "https://files.pythonhosted.org/packages/4b/8d/a0a47a0c9e413a658623d014e91e74a50cdd2c423f7ccfd44086ef767f90/cffi-2.0.0-cp313-cp313-macosx_10_13_x86_64.whl", hash = "sha256:00bdf7acc5f795150faa6957054fbbca2439db2f775ce831222b66f192f03beb", size = 185230, upload-time = "2025-09-08T23:23:00.879Z" },
    { url = "https://files.pythonhosted.org/packages/4a/d2/a6c0296814556c68ee32009d9c2ad4f85f2707cdecfd7727951ec228005d/cffi-2.0.0-cp313-cp313-macosx_11_0_arm64.whl", hash = "sha256:45d5e886156860dc35862657e1494b9bae8dfa63bf56796f2fb56e1679fc0bca", size = 181043, upload-time = "2025-09-08T23:23:02.231Z" },
    { url = "https://files.pythonhosted.org/packages/b0/1e/d22cc63332bd59b06481ceaac49d6c507598642e2230f201649058a7e704/cffi-2.0.0-cp313-cp313-manylinux1_i686.manylinux2014_i686.manylinux_2_17_i686.manylinux_2_5_i686.whl", hash = "sha256:07b271772c100085dd28b74fa0cd81c8fb1a3ba18b21e03d7c27f3436a10606b", size = 212446, upload-time = "2025-09-08T23:23:03.472Z" },
    { url = "https://files.pythonhosted.org/packages/a9/f5/a2c23eb03b61a0b8747f211eb716446c826ad66818ddc7810cc2cc19b3f2/cffi-2.0.0-cp313-cp313-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:d48a880098c96020b02d5a1f7d9251308510ce8858940e6fa99ece33f610838b", size = 220101, upload-time = "2025-09-08T23:23:04.792Z" },
    { url = "https://files.pythonhosted.org/packages/f2/7f/e6647792fc5850d634695bc0e6ab4111ae88e89981d35ac269956605feba/cffi-2.0.0-cp313-cp313-manylinux2014_ppc64le.manylinux_2_17_ppc64le.whl", hash = "sha256:f93fd8e5c8c0a4aa1f424d6173f14a892044054871c771f8566e4008eaa359d2", size = 207948, upload-time = "2025-09-08T23:23:06.127Z" },
    { url = "https://files.pythonhosted.org/packages/cb/1e/a5a1bd6f1fb30f22573f76533de12a00bf274abcdc55c8edab639078abb6/cffi-2.0.0-cp313-cp313-manylinux2014_s390x.manylinux_2_17_s390x.whl", hash = "sha256:dd4f05f54a52fb558f1ba9f528228066954fee3ebe629fc1660d874d040ae5a3", size = 206422, upload-time = "2025-09-08T23:23:07.753Z" },
    { url = "https://files.pythonhosted.org/packages/98/df/0a1755e750013a2081e863e7cd37e0cdd02664372c754e5560099eb7aa44/cffi-2.0.0-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:c8d3b5532fc71b7a77c09192b4a5a200ea992702734a2e9279a37f2478236f26", size = 219499, upload-time = "2025-09-08T23:23:09.648Z" },
    { url = "https://files.pythonhosted.org/packages/50/e1/a969e687fcf9ea58e6e2a928ad5e2dd88cc12f6f0ab477e9971f2309b57c/cffi-2.0.0-cp313-cp313-musllinux_1_2_aarch64.whl", hash = "sha256:d9b29c1f0ae438d5ee9acb31cadee00a58c46cc9c0b2f9038c6b0b3470877a8c", size = 222928, upload-time = "2025-09-08T23:23:10.928Z" },
    { url = "https://files.pythonhosted.org/packages/36/54/0362578dd2c9e557a28ac77698ed67323ed5b9775ca9d3fe73fe191bb5d8/cffi-2.0.0-cp313-cp313-musllinux_1_2_x86_64.whl", hash = "sha256:6d50360be4546678fc1b79ffe7a66265e28667840010348dd69a314145807a1b", size = 221302, upload-time = "2025-09-08T23:23:12.42Z" },
    { url = "https://files.pythonhosted.org/packages/eb/6d/bf9bda840d5f1dfdbf0feca87fbdb64a918a69bca42cfa0ba7b137c48cb8/cffi-2.0.0-cp313-cp313-win32.whl", hash = "sha256:74a03b9698e198d47562765773b4a8309919089150a0bb17d829ad7b44b60d27", size = 172909, upload-time = "2025-09-08T23:23:14.32Z" },
    { url = "https://files.pythonhosted.org/packages/37/18/6519e1ee6f5a1e579e04b9ddb6f1676c17368a7aba48299c3759bbc3c8b3/cffi-2.0.0-cp313-cp313-win_amd64.whl", hash = "sha256:19f705ada2530c1167abacb171925dd886168931e0a7b78f5bffcae5c6b5be75", size = 183402, upload-time = "2025-09-08T23:23:15.535Z" },
    { url = "https://files.pythonhosted.org/packages/cb/0e/02ceeec9a7d6ee63bb596121c2c8e9b3a9e150936f4fbef6ca1943e6137c/cffi-2.0.0-cp313-cp313-win_arm64.whl", hash = "sha256:256f80b80ca3853f90c21b23ee78cd008713787b1b1e93eae9f3d6a7134abd91", size = 177780, upload-time = "2025-09-08T23:23:16.761Z" },
    { url = "https://files.pythonhosted.org/packages/92/c4/3ce07396253a83250ee98564f8d7e9789fab8e58858f35d07a9a2c78de9f/cffi-2.0.0-cp314-cp314-macosx_10_13_x86_64.whl", hash = "sha256:fc33c5141b55ed366cfaad382df24fe7dcbc686de5be719b207bb248e3053dc5", size = 185320, upload-time = "2025-09-08T23:23:18.087Z" },
    { url = "https://files.pythonhosted.org/packages/59/dd/27e9fa567a23931c838c6b02d0764611c62290062a6d4e8ff7863daf9730/cffi-2.0.0-cp314-cp314-macosx_11_0_arm64.whl", hash = "sha256:c654de545946e0db659b3400168c9ad31b5d29593291482c43e3564effbcee13", size = 181487, upload-time = "2025-09-08T23:23:19.622Z" },
    { url = "https://files.pythonhosted.org/packages/d6/43/0e822876f87ea8a4ef95442c3d766a06a51fc5298823f884ef87aaad168c/cffi-2.0.0-cp314-cp314-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:24b6f81f1983e6df8db3adc38562c83f7d4a0c36162885ec7f7b77c7dcbec97b", size = 220049, upload-time = "2025-09-08T23:23:20.853Z" },
    { url = "https://files.pythonhosted.org/packages/b4/89/76799151d9c2d2d1ead63c2429da9ea9d7aac304603de0c6e8764e6e8e70/cffi-2.0.0-cp314-cp314-manylinux2014_ppc64le.manylinux_2_17_ppc64le.whl", hash = "sha256:12873ca6cb9b0f0d3a0da705d6086fe911591737a59f28b7936bdfed27c0d47c", size = 207793, upload-time = "2025-09-08T23:23:22.08Z" },
    { url = "https://files.pythonhosted.org/packages/bb/dd/3465b14bb9e24ee24cb88c9e3730f6de63111fffe513492bf8c808a3547e/cffi-2.0.0-cp314-cp314-manylinux2014_s390x.manylinux_2_17_s390x.whl", hash = "sha256:d9b97165e8aed9272a6bb17c01e3cc5871a594a446ebedc996e2397a1c1ea8ef", size = 206300, upload-time = "2025-09-08T23:23:23.314Z" },
    { url = "https://files.pythonhosted.org/packages/47/d9/d83e293854571c877a92da46fdec39158f8d7e68da75bf73581225d28e90/cffi-2.0.0-cp314-cp314-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:afb8db5439b81cf9c9d0c80404b60c3cc9c3add93e114dcae767f1477cb53775", size = 219244, upload-time = "2025-09-08T23:23:24.541Z" },
    { url = "https://files.pythonhosted.org/packages/2b/0f/1f177e3683aead2bb00f7679a16451d302c436b5cbf2505f0ea8146ef59e/cffi-2.0.0-cp314-cp314-musllinux_1_2_aarch64.whl", hash = "sha256:737fe7d37e1a1bffe70bd5754ea763a62a066dc5913ca57e957824b72a85e205", size = 222828, upload-time = "2025-09-08T23:23:26.143Z" },
    { url = "https://files.pythonhosted.org/packages/c6/0f/cafacebd4b040e3119dcb32fed8bdef8dfe94da653155f9d0b9dc660166e/cffi-2.0.0-cp314-cp314-musllinux_1_2_x86_64.whl", hash = "sha256:38100abb9d1b1435bc4cc340bb4489635dc2f0da7456590877030c9b3d40b0c1", size = 220926, upload-time = "2025-09-08T23:23:27.873Z" },
    { url = "https://files.pythonhosted.org/packages/3e/aa/df335faa45b395396fcbc03de2dfcab242cd61a9900e914fe682a59170b1/cffi-2.0.0-cp314-cp314-win32.whl", hash = "sha256:087067fa8953339c723661eda6b54bc98c5625757ea62e95eb4898ad5e776e9f", size = 175328, upload-time = "2025-09-08T23:23:44.61Z" },
    { url = "https://files.pythonhosted.org/packages/bb/92/882c2d30831744296ce713f0feb4c1cd30f346ef747b530b5318715cc367/cffi-2.0.0-cp314-cp314-win_amd64.whl", hash = "sha256:203a48d1fb583fc7d78a4c6655692963b860a417c0528492a6bc21f1aaefab25", size = 185650, upload-time = "2025-09-08T23:23:45.848Z" },
    { url = "https://files.pythonhosted.org/packages/9f/2c/98ece204b9d35a7366b5b2c6539c350313ca13932143e79dc133ba757104/cffi-2.0.0-cp314-cp314-win_arm64.whl", hash = "sha256:dbd5c7a25a7cb98f5ca55d258b103a2054f859a46ae11aaf23134f9cc0d356ad", size = 180687, upload-time = "2025-09-08T23:23:47.105Z" },
    { url = "https://files.pythonhosted.org/packages/3e/61/c768e4d548bfa607abcda77423448df8c471f25dbe64fb2ef6d555eae006/cffi-2.0.0-cp314-cp314t-macosx_10_13_x86_64.whl", hash = "sha256:9a67fc9e8eb39039280526379fb3a70023d77caec1852002b4da7e8b270c4dd9", size = 188773, upload-time = "2025-09-08T23:23:29.347Z" },
    { url = "https://files.pythonhosted.org/packages/2c/ea/5f76bce7cf6fcd0ab1a1058b5af899bfbef198bea4d5686da88471ea0336/cffi-2.0.0-cp314-cp314t-macosx_11_0_arm64.whl", hash = "sha256:7a66c7204d8869299919db4d5069a82f1561581af12b11b3c9f48c584eb8743d", size = 185013, upload-time = "2025-09-08T23:23:30.63Z" },
    { url = "https://files.pythonhosted.org/packages/be/b4/c56878d0d1755cf9caa54ba71e5d049479c52f9e4afc230f06822162ab2f/cffi-2.0.0-cp314-cp314t-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:7cc09976e8b56f8cebd752f7113ad07752461f48a58cbba644139015ac24954c", size = 221593, upload-time = "2025-09-08T23:23:31.91Z" },
    { url = "https://files.pythonhosted.org/packages/e0/0d/eb704606dfe8033e7128df5e90fee946bbcb64a04fcdaa97321309004000/cffi-2.0.0-cp314-cp314t-manylinux2014_ppc64le.manylinux_2_17_ppc64le.whl", hash = "sha256:92b68146a71df78564e4ef48af17551a5ddd142e5190cdf2c5624d0c3ff5b2e8", size = 209354, upload-time = "2025-09-08T23:23:33.214Z" },
    { url = "https://files.pythonhosted.org/packages/d8/19/3c435d727b368ca475fb8742ab97c9cb13a0de600ce86f62eab7fa3eea60/cffi-2.0.0-cp314-cp314t-manylinux2014_s390x.manylinux_2_17_s390x.whl", hash = "sha256:b1e74d11748e7e98e2f426ab176d4ed720a64412b6a15054378afdb71e0f37dc", size = 208480, upload-time = "2025-09-08T23:23:34.495Z" },
    { url = "https://files.pythonhosted.org/packages/d0/44/681604464ed9541673e486521497406fadcc15b5217c3e326b061696899a/cffi-2.0.0-cp314-cp314t-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:28a3a209b96630bca57cce802da70c266eb08c6e97e5afd61a75611ee6c64592", size = 221584, upload-time = "2025-09-08T23:23:36.096Z" },
    { url = "https://files.pythonhosted.org/packages/25/8e/342a504ff018a2825d395d44d63a767dd8ebc927ebda557fecdaca3ac33a/cffi-2.0.0-cp314-cp314t-musllinux_1_2_aarch64.whl", hash = "sha256:7553fb2090d71822f02c629afe6042c299edf91ba1bf94951165613553984512", size = 224443, upload-time = "2025-09-08T23:23:37.328Z" },
    { url = "https://files.pythonhosted.org/packages/e1/5e/b666bacbbc60fbf415ba9988324a132c9a7a0448a9a8f125074671c0f2c3/cffi-2.0.0-cp314-cp314t-musllinux_1_2_x86_64.whl", hash = "sha256:6c6c373cfc5c83a975506110d17457138c8c63016b563cc9ed6e056a82f13ce4", size = 223437, upload-time = "2025-09-08T23:23:38.945Z" },
    { url = "https://files.pythonhosted.org/packages/a0/1d/ec1a60bd1a10daa292d3cd6bb0b359a81607154fb8165f3ec95fe003b85c/cffi-2.0.0-cp314-cp314t-win32.whl", hash = "sha256:1fc9ea04857caf665289b7a75923f2c6ed559b8298a1b8c49e59f7dd95c8481e", size = 180487, upload-time = "2025-09-08T23:23:40.423Z" },
    { url = "https://files.pythonhosted.org/packages/bf/41/4c1168c74fac325c0c8156f04b6749c8b6a8f405bbf91413ba088359f60d/cffi-2.0.0-cp314-cp314t-win_amd64.whl", hash = "sha256:d68b6cef7827e8641e8ef16f4494edda8b36104d79773a334beaa1e3521430f6", size = 191726, upload-time = "2025-09-08T23:23:41.742Z" },
    { url = "https://files.pythonhosted.org/packages/ae/3a/dbeec9d1ee0844c679f6bb5d6ad4e9f198b1224f4e7a32825f47f6192b0c/cffi-2.0.0-cp314-cp314t-win_arm64.whl", hash = "sha256:0a1527a803f0a659de1af2e1fd700213caba79377e27e4693648c2923da066f9", size = 184195, upload-time = "2025-09-08T23:23:43.004Z" },
]

[[package]]
name = "charset-normalizer"
version = "3.4.6"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/7b/60/e3bec1881450851b087e301bedc3daa9377a4d45f1c26aa90b0b235e38aa/charset_normalizer-3.4.6.tar.gz", hash = "sha256:1ae6b62897110aa7c79ea2f5dd38d1abca6db663687c0b1ad9aed6f6bae3d9d6", size = 143363, upload-time = "2026-03-15T18:53:25.478Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/62/28/ff6f234e628a2de61c458be2779cb182bc03f6eec12200d4a525bbfc9741/charset_normalizer-3.4.6-cp311-cp311-macosx_10_9_universal2.whl", hash = "sha256:82060f995ab5003a2d6e0f4ad29065b7672b6593c8c63559beefe5b443242c3e", size = 293582, upload-time = "2026-03-15T18:50:25.454Z" },
    { url = "https://files.pythonhosted.org/packages/1c/b7/b1a117e5385cbdb3205f6055403c2a2a220c5ea80b8716c324eaf75c5c95/charset_normalizer-3.4.6-cp311-cp311-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:60c74963d8350241a79cb8feea80e54d518f72c26db618862a8f53e5023deaf9", size = 197240, upload-time = "2026-03-15T18:50:27.196Z" },
    { url = "https://files.pythonhosted.org/packages/a1/5f/2574f0f09f3c3bc1b2f992e20bce6546cb1f17e111c5be07308dc5427956/charset_normalizer-3.4.6-cp311-cp311-manylinux2014_ppc64le.manylinux_2_17_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:f6e4333fb15c83f7d1482a76d45a0818897b3d33f00efd215528ff7c51b8e35d", size = 217363, upload-time = "2026-03-15T18:50:28.601Z" },
    { url = "https://files.pythonhosted.org/packages/4a/d1/0ae20ad77bc949ddd39b51bf383b6ca932f2916074c95cad34ae465ab71f/charset_normalizer-3.4.6-cp311-cp311-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:bc72863f4d9aba2e8fd9085e63548a324ba706d2ea2c83b260da08a59b9482de", size = 212994, upload-time = "2026-03-15T18:50:30.102Z" },
    { url = "https://files.pythonhosted.org/packages/60/ac/3233d262a310c1b12633536a07cde5ddd16985e6e7e238e9f3f9423d8eb9/charset_normalizer-3.4.6-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:9cc4fc6c196d6a8b76629a70ddfcd4635a6898756e2d9cac5565cf0654605d73", size = 204697, upload-time = "2026-03-15T18:50:31.654Z" },
    { url = "https://files.pythonhosted.org/packages/25/3c/8a18fc411f085b82303cfb7154eed5bd49c77035eb7608d049468b53f87c/charset_normalizer-3.4.6-cp311-cp311-manylinux_2_31_armv7l.whl", hash = "sha256:0c173ce3a681f309f31b87125fecec7a5d1347261ea11ebbb856fa6006b23c8c", size = 191673, upload-time = "2026-03-15T18:50:33.433Z" },
    { url = "https://files.pythonhosted.org/packages/ff/a7/11cfe61d6c5c5c7438d6ba40919d0306ed83c9ab957f3d4da2277ff67836/charset_normalizer-3.4.6-cp311-cp311-manylinux_2_31_riscv64.manylinux_2_39_riscv64.whl", hash = "sha256:c907cdc8109f6c619e6254212e794d6548373cc40e1ec75e6e3823d9135d29cc", size = 201120, upload-time = "2026-03-15T18:50:35.105Z" },
    { url = "https://files.pythonhosted.org/packages/b5/10/cf491fa1abd47c02f69687046b896c950b92b6cd7337a27e6548adbec8e4/charset_normalizer-3.4.6-cp311-cp311-musllinux_1_2_aarch64.whl", hash = "sha256:404a1e552cf5b675a87f0651f8b79f5f1e6fd100ee88dc612f89aa16abd4486f", size = 200911, upload-time = "2026-03-15T18:50:36.819Z" },
    { url = "https://files.pythonhosted.org/packages/28/70/039796160b48b18ed466fde0af84c1b090c4e288fae26cd674ad04a2d703/charset_normalizer-3.4.6-cp311-cp311-musllinux_1_2_armv7l.whl", hash = "sha256:e3c701e954abf6fc03a49f7c579cc80c2c6cc52525340ca3186c41d3f33482ef", size = 192516, upload-time = "2026-03-15T18:50:38.228Z" },
    { url = "https://files.pythonhosted.org/packages/ff/34/c56f3223393d6ff3124b9e78f7de738047c2d6bc40a4f16ac0c9d7a1cb3c/charset_normalizer-3.4.6-cp311-cp311-musllinux_1_2_ppc64le.whl", hash = "sha256:7a6967aaf043bceabab5412ed6bd6bd26603dae84d5cb75bf8d9a74a4959d398", size = 218795, upload-time = "2026-03-15T18:50:39.664Z" },
    { url = "https://files.pythonhosted.org/packages/e8/3b/ce2d4f86c5282191a041fdc5a4ce18f1c6bd40a5bd1f74cf8625f08d51c1/charset_normalizer-3.4.6-cp311-cp311-musllinux_1_2_riscv64.whl", hash = "sha256:5feb91325bbceade6afab43eb3b508c63ee53579fe896c77137ded51c6b6958e", size = 201833, upload-time = "2026-03-15T18:50:41.552Z" },
    { url = "https://files.pythonhosted.org/packages/3b/9b/b6a9f76b0fd7c5b5ec58b228ff7e85095370282150f0bd50b3126f5506d6/charset_normalizer-3.4.6-cp311-cp311-musllinux_1_2_s390x.whl", hash = "sha256:f820f24b09e3e779fe84c3c456cb4108a7aa639b0d1f02c28046e11bfcd088ed", size = 213920, upload-time = "2026-03-15T18:50:43.33Z" },
    { url = "https://files.pythonhosted.org/packages/ae/98/7bc23513a33d8172365ed30ee3a3b3fe1ece14a395e5fc94129541fc6003/charset_normalizer-3.4.6-cp311-cp311-musllinux_1_2_x86_64.whl", hash = "sha256:b35b200d6a71b9839a46b9b7fff66b6638bb52fc9658aa58796b0326595d3021", size = 206951, upload-time = "2026-03-15T18:50:44.789Z" },
    { url = "https://files.pythonhosted.org/packages/32/73/c0b86f3d1458468e11aec870e6b3feac931facbe105a894b552b0e518e79/charset_normalizer-3.4.6-cp311-cp311-win32.whl", hash = "sha256:9ca4c0b502ab399ef89248a2c84c54954f77a070f28e546a85e91da627d1301e", size = 143703, upload-time = "2026-03-15T18:50:46.103Z" },
    { url = "https://files.pythonhosted.org/packages/c6/e3/76f2facfe8eddee0bbd38d2594e709033338eae44ebf1738bcefe0a06185/charset_normalizer-3.4.6-cp311-cp311-win_amd64.whl", hash = "sha256:a9e68c9d88823b274cf1e72f28cb5dc89c990edf430b0bfd3e2fb0785bfeabf4", size = 153857, upload-time = "2026-03-15T18:50:47.563Z" },
    { url = "https://files.pythonhosted.org/packages/e2/dc/9abe19c9b27e6cd3636036b9d1b387b78c40dedbf0b47f9366737684b4b0/charset_normalizer-3.4.6-cp311-cp311-win_arm64.whl", hash = "sha256:97d0235baafca5f2b09cf332cc275f021e694e8362c6bb9c96fc9a0eb74fc316", size = 142751, upload-time = "2026-03-15T18:50:49.234Z" },
    { url = "https://files.pythonhosted.org/packages/e5/62/c0815c992c9545347aeea7859b50dc9044d147e2e7278329c6e02ac9a616/charset_normalizer-3.4.6-cp312-cp312-macosx_10_13_universal2.whl", hash = "sha256:2ef7fedc7a6ecbe99969cd09632516738a97eeb8bd7258bf8a0f23114c057dab", size = 295154, upload-time = "2026-03-15T18:50:50.88Z" },
    { url = "https://files.pythonhosted.org/packages/a8/37/bdca6613c2e3c58c7421891d80cc3efa1d32e882f7c4a7ee6039c3fc951a/charset_normalizer-3.4.6-cp312-cp312-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:a4ea868bc28109052790eb2b52a9ab33f3aa7adc02f96673526ff47419490e21", size = 199191, upload-time = "2026-03-15T18:50:52.658Z" },
    { url = "https://files.pythonhosted.org/packages/6c/92/9934d1bbd69f7f398b38c5dae1cbf9cc672e7c34a4adf7b17c0a9c17d15d/charset_normalizer-3.4.6-cp312-cp312-manylinux2014_ppc64le.manylinux_2_17_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:836ab36280f21fc1a03c99cd05c6b7af70d2697e374c7af0b61ed271401a72a2", size = 218674, upload-time = "2026-03-15T18:50:54.102Z" },
    { url = "https://files.pythonhosted.org/packages/af/90/25f6ab406659286be929fd89ab0e78e38aa183fc374e03aa3c12d730af8a/charset_normalizer-3.4.6-cp312-cp312-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:f1ce721c8a7dfec21fcbdfe04e8f68174183cf4e8188e0645e92aa23985c57ff", size = 215259, upload-time = "2026-03-15T18:50:55.616Z" },
    { url = "https://files.pythonhosted.org/packages/4e/ef/79a463eb0fff7f96afa04c1d4c51f8fc85426f918db467854bfb6a569ce3/charset_normalizer-3.4.6-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:0e28d62a8fc7a1fa411c43bd65e346f3bce9716dc51b897fbe930c5987b402d5", size = 207276, upload-time = "2026-03-15T18:50:57.054Z" },
    { url = "https://files.pythonhosted.org/packages/f7/72/d0426afec4b71dc159fa6b4e68f868cd5a3ecd918fec5813a15d292a7d10/charset_normalizer-3.4.6-cp312-cp312-manylinux_2_31_armv7l.whl", hash = "sha256:530d548084c4a9f7a16ed4a294d459b4f229db50df689bfe92027452452943a0", size = 195161, upload-time = "2026-03-15T18:50:58.686Z" },
    { url = "https://files.pythonhosted.org/packages/bf/18/c82b06a68bfcb6ce55e508225d210c7e6a4ea122bfc0748892f3dc4e8e11/charset_normalizer-3.4.6-cp312-cp312-manylinux_2_31_riscv64.manylinux_2_39_riscv64.whl", hash = "sha256:30f445ae60aad5e1f8bdbb3108e39f6fbc09f4ea16c815c66578878325f8f15a", size = 203452, upload-time = "2026-03-15T18:51:00.196Z" },
    { url = "https://files.pythonhosted.org/packages/44/d6/0c25979b92f8adafdbb946160348d8d44aa60ce99afdc27df524379875cb/charset_normalizer-3.4.6-cp312-cp312-musllinux_1_2_aarch64.whl", hash = "sha256:ac2393c73378fea4e52aa56285a3d64be50f1a12395afef9cce47772f60334c2", size = 202272, upload-time = "2026-03-15T18:51:01.703Z" },
    { url = "https://files.pythonhosted.org/packages/2e/3d/7fea3e8fe84136bebbac715dd1221cc25c173c57a699c030ab9b8900cbb7/charset_normalizer-3.4.6-cp312-cp312-musllinux_1_2_armv7l.whl", hash = "sha256:90ca27cd8da8118b18a52d5f547859cc1f8354a00cd1e8e5120df3e30d6279e5", size = 195622, upload-time = "2026-03-15T18:51:03.526Z" },
    { url = "https://files.pythonhosted.org/packages/57/8a/d6f7fd5cb96c58ef2f681424fbca01264461336d2a7fc875e4446b1f1346/charset_normalizer-3.4.6-cp312-cp312-musllinux_1_2_ppc64le.whl", hash = "sha256:8e5a94886bedca0f9b78fecd6afb6629142fd2605aa70a125d49f4edc6037ee6", size = 220056, upload-time = "2026-03-15T18:51:05.269Z" },
    { url = "https://files.pythonhosted.org/packages/16/50/478cdda782c8c9c3fb5da3cc72dd7f331f031e7f1363a893cdd6ca0f8de0/charset_normalizer-3.4.6-cp312-cp312-musllinux_1_2_riscv64.whl", hash = "sha256:695f5c2823691a25f17bc5d5ffe79fa90972cc34b002ac6c843bb8a1720e950d", size = 203751, upload-time = "2026-03-15T18:51:06.858Z" },
    { url = "https://files.pythonhosted.org/packages/75/fc/cc2fcac943939c8e4d8791abfa139f685e5150cae9f94b60f12520feaa9b/charset_normalizer-3.4.6-cp312-cp312-musllinux_1_2_s390x.whl", hash = "sha256:231d4da14bcd9301310faf492051bee27df11f2bc7549bc0bb41fef11b82daa2", size = 216563, upload-time = "2026-03-15T18:51:08.564Z" },
    { url = "https://files.pythonhosted.org/packages/a8/b7/a4add1d9a5f68f3d037261aecca83abdb0ab15960a3591d340e829b37298/charset_normalizer-3.4.6-cp312-cp312-musllinux_1_2_x86_64.whl", hash = "sha256:a056d1ad2633548ca18ffa2f85c202cfb48b68615129143915b8dc72a806a923", size = 209265, upload-time = "2026-03-15T18:51:10.312Z" },
    { url = "https://files.pythonhosted.org/packages/6c/18/c094561b5d64a24277707698e54b7f67bd17a4f857bbfbb1072bba07c8bf/charset_normalizer-3.4.6-cp312-cp312-win32.whl", hash = "sha256:c2274ca724536f173122f36c98ce188fd24ce3dad886ec2b7af859518ce008a4", size = 144229, upload-time = "2026-03-15T18:51:11.694Z" },
    { url = "https://files.pythonhosted.org/packages/ab/20/0567efb3a8fd481b8f34f739ebddc098ed062a59fed41a8d193a61939e8f/charset_normalizer-3.4.6-cp312-cp312-win_amd64.whl", hash = "sha256:c8ae56368f8cc97c7e40a7ee18e1cedaf8e780cd8bc5ed5ac8b81f238614facb", size = 154277, upload-time = "2026-03-15T18:51:13.004Z" },
    { url = "https://files.pythonhosted.org/packages/15/57/28d79b44b51933119e21f65479d0864a8d5893e494cf5daab15df0247c17/charset_normalizer-3.4.6-cp312-cp312-win_arm64.whl", hash = "sha256:899d28f422116b08be5118ef350c292b36fc15ec2daeb9ea987c89281c7bb5c4", size = 142817, upload-time = "2026-03-15T18:51:14.408Z" },
    { url = "https://files.pythonhosted.org/packages/1e/1d/4fdabeef4e231153b6ed7567602f3b68265ec4e5b76d6024cf647d43d981/charset_normalizer-3.4.6-cp313-cp313-macosx_10_13_universal2.whl", hash = "sha256:11afb56037cbc4b1555a34dd69151e8e069bee82e613a73bef6e714ce733585f", size = 294823, upload-time = "2026-03-15T18:51:15.755Z" },
    { url = "https://files.pythonhosted.org/packages/47/7b/20e809b89c69d37be748d98e84dce6820bf663cf19cf6b942c951a3e8f41/charset_normalizer-3.4.6-cp313-cp313-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:423fb7e748a08f854a08a222b983f4df1912b1daedce51a72bd24fe8f26a1843", size = 198527, upload-time = "2026-03-15T18:51:17.177Z" },
    { url = "https://files.pythonhosted.org/packages/37/a6/4f8d27527d59c039dce6f7622593cdcd3d70a8504d87d09eb11e9fdc6062/charset_normalizer-3.4.6-cp313-cp313-manylinux2014_ppc64le.manylinux_2_17_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:d73beaac5e90173ac3deb9928a74763a6d230f494e4bfb422c217a0ad8e629bf", size = 218388, upload-time = "2026-03-15T18:51:18.934Z" },
    { url = "https://files.pythonhosted.org/packages/f6/9b/4770ccb3e491a9bacf1c46cc8b812214fe367c86a96353ccc6daf87b01ec/charset_normalizer-3.4.6-cp313-cp313-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:d60377dce4511655582e300dc1e5a5f24ba0cb229005a1d5c8d0cb72bb758ab8", size = 214563, upload-time = "2026-03-15T18:51:20.374Z" },
    { url = "https://files.pythonhosted.org/packages/2b/58/a199d245894b12db0b957d627516c78e055adc3a0d978bc7f65ddaf7c399/charset_normalizer-3.4.6-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:530e8cebeea0d76bdcf93357aa5e41336f48c3dc709ac52da2bb167c5b8271d9", size = 206587, upload-time = "2026-03-15T18:51:21.807Z" },
    { url = "https://files.pythonhosted.org/packages/7e/70/3def227f1ec56f5c69dfc8392b8bd63b11a18ca8178d9211d7cc5e5e4f27/charset_normalizer-3.4.6-cp313-cp313-manylinux_2_31_armv7l.whl", hash = "sha256:a26611d9987b230566f24a0a125f17fe0de6a6aff9f25c9f564aaa2721a5fb88", size = 194724, upload-time = "2026-03-15T18:51:23.508Z" },
    { url = "https://files.pythonhosted.org/packages/58/ab/9318352e220c05efd31c2779a23b50969dc94b985a2efa643ed9077bfca5/charset_normalizer-3.4.6-cp313-cp313-manylinux_2_31_riscv64.manylinux_2_39_riscv64.whl", hash = "sha256:34315ff4fc374b285ad7f4a0bf7dcbfe769e1b104230d40f49f700d4ab6bbd84", size = 202956, upload-time = "2026-03-15T18:51:25.239Z" },
    { url = "https://files.pythonhosted.org/packages/75/13/f3550a3ac25b70f87ac98c40d3199a8503676c2f1620efbf8d42095cfc40/charset_normalizer-3.4.6-cp313-cp313-musllinux_1_2_aarch64.whl", hash = "sha256:5f8ddd609f9e1af8c7bd6e2aca279c931aefecd148a14402d4e368f3171769fd", size = 201923, upload-time = "2026-03-15T18:51:26.682Z" },
    { url = "https://files.pythonhosted.org/packages/1b/db/c5c643b912740b45e8eec21de1bbab8e7fc085944d37e1e709d3dcd9d72f/charset_normalizer-3.4.6-cp313-cp313-musllinux_1_2_armv7l.whl", hash = "sha256:80d0a5615143c0b3225e5e3ef22c8d5d51f3f72ce0ea6fb84c943546c7b25b6c", size = 195366, upload-time = "2026-03-15T18:51:28.129Z" },
    { url = "https://files.pythonhosted.org/packages/5a/67/3b1c62744f9b2448443e0eb160d8b001c849ec3fef591e012eda6484787c/charset_normalizer-3.4.6-cp313-cp313-musllinux_1_2_ppc64le.whl", hash = "sha256:92734d4d8d187a354a556626c221cd1a892a4e0802ccb2af432a1d85ec012194", size = 219752, upload-time = "2026-03-15T18:51:29.556Z" },
    { url = "https://files.pythonhosted.org/packages/f6/98/32ffbaf7f0366ffb0445930b87d103f6b406bc2c271563644bde8a2b1093/charset_normalizer-3.4.6-cp313-cp313-musllinux_1_2_riscv64.whl", hash = "sha256:613f19aa6e082cf96e17e3ffd89383343d0d589abda756b7764cf78361fd41dc", size = 203296, upload-time = "2026-03-15T18:51:30.921Z" },
    { url = "https://files.pythonhosted.org/packages/41/12/5d308c1bbe60cabb0c5ef511574a647067e2a1f631bc8634fcafaccd8293/charset_normalizer-3.4.6-cp313-cp313-musllinux_1_2_s390x.whl", hash = "sha256:2b1a63e8224e401cafe7739f77efd3f9e7f5f2026bda4aead8e59afab537784f", size = 215956, upload-time = "2026-03-15T18:51:32.399Z" },
    { url = "https://files.pythonhosted.org/packages/53/e9/5f85f6c5e20669dbe56b165c67b0260547dea97dba7e187938833d791687/charset_normalizer-3.4.6-cp313-cp313-musllinux_1_2_x86_64.whl", hash = "sha256:6cceb5473417d28edd20c6c984ab6fee6c6267d38d906823ebfe20b03d607dc2", size = 208652, upload-time = "2026-03-15T18:51:34.214Z" },
    { url = "https://files.pythonhosted.org/packages/f1/11/897052ea6af56df3eef3ca94edafee410ca699ca0c7b87960ad19932c55e/charset_normalizer-3.4.6-cp313-cp313-win32.whl", hash = "sha256:d7de2637729c67d67cf87614b566626057e95c303bc0a55ffe391f5205e7003d", size = 143940, upload-time = "2026-03-15T18:51:36.15Z" },
    { url = "https://files.pythonhosted.org/packages/a1/5c/724b6b363603e419829f561c854b87ed7c7e31231a7908708ac086cdf3e2/charset_normalizer-3.4.6-cp313-cp313-win_amd64.whl", hash = "sha256:572d7c822caf521f0525ba1bce1a622a0b85cf47ffbdae6c9c19e3b5ac3c4389", size = 154101, upload-time = "2026-03-15T18:51:37.876Z" },
    { url = "https://files.pythonhosted.org/packages/01/a5/7abf15b4c0968e47020f9ca0935fb3274deb87cb288cd187cad92e8cdffd/charset_normalizer-3.4.6-cp313-cp313-win_arm64.whl", hash = "sha256:a4474d924a47185a06411e0064b803c68be044be2d60e50e8bddcc2649957c1f", size = 143109, upload-time = "2026-03-15T18:51:39.565Z" },
    { url = "https://files.pythonhosted.org/packages/25/6f/ffe1e1259f384594063ea1869bfb6be5cdb8bc81020fc36c3636bc8302a1/charset_normalizer-3.4.6-cp314-cp314-macosx_10_15_universal2.whl", hash = "sha256:9cc6e6d9e571d2f863fa77700701dae73ed5f78881efc8b3f9a4398772ff53e8", size = 294458, upload-time = "2026-03-15T18:51:41.134Z" },
    { url = "https://files.pythonhosted.org/packages/56/60/09bb6c13a8c1016c2ed5c6a6488e4ffef506461aa5161662bd7636936fb1/charset_normalizer-3.4.6-cp314-cp314-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:ef5960d965e67165d75b7c7ffc60a83ec5abfc5c11b764ec13ea54fbef8b4421", size = 199277, upload-time = "2026-03-15T18:51:42.953Z" },
    { url = "https://files.pythonhosted.org/packages/00/50/dcfbb72a5138bbefdc3332e8d81a23494bf67998b4b100703fd15fa52d81/charset_normalizer-3.4.6-cp314-cp314-manylinux2014_ppc64le.manylinux_2_17_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:b3694e3f87f8ac7ce279d4355645b3c878d24d1424581b46282f24b92f5a4ae2", size = 218758, upload-time = "2026-03-15T18:51:44.339Z" },
    { url = "https://files.pythonhosted.org/packages/03/b3/d79a9a191bb75f5aa81f3aaaa387ef29ce7cb7a9e5074ba8ea095cc073c2/charset_normalizer-3.4.6-cp314-cp314-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:5d11595abf8dd942a77883a39d81433739b287b6aa71620f15164f8096221b30", size = 215299, upload-time = "2026-03-15T18:51:45.871Z" },
    { url = "https://files.pythonhosted.org/packages/76/7e/bc8911719f7084f72fd545f647601ea3532363927f807d296a8c88a62c0d/charset_normalizer-3.4.6-cp314-cp314-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:7bda6eebafd42133efdca535b04ccb338ab29467b3f7bf79569883676fc628db", size = 206811, upload-time = "2026-03-15T18:51:47.308Z" },
    { url = "https://files.pythonhosted.org/packages/e2/40/c430b969d41dda0c465aa36cc7c2c068afb67177bef50905ac371b28ccc7/charset_normalizer-3.4.6-cp314-cp314-manylinux_2_31_armv7l.whl", hash = "sha256:bbc8c8650c6e51041ad1be191742b8b421d05bbd3410f43fa2a00c8db87678e8", size = 193706, upload-time = "2026-03-15T18:51:48.849Z" },
    { url = "https://files.pythonhosted.org/packages/48/15/e35e0590af254f7df984de1323640ef375df5761f615b6225ba8deb9799a/charset_normalizer-3.4.6-cp314-cp314-manylinux_2_31_riscv64.manylinux_2_39_riscv64.whl", hash = "sha256:22c6f0c2fbc31e76c3b8a86fba1a56eda6166e238c29cdd3d14befdb4a4e4815", size = 202706, upload-time = "2026-03-15T18:51:50.257Z" },
    { url = "https://files.pythonhosted.org/packages/5e/bd/f736f7b9cc5e93a18b794a50346bb16fbfd6b37f99e8f306f7951d27c17c/charset_normalizer-3.4.6-cp314-cp314-musllinux_1_2_aarch64.whl", hash = "sha256:7edbed096e4a4798710ed6bc75dcaa2a21b68b6c356553ac4823c3658d53743a", size = 202497, upload-time = "2026-03-15T18:51:52.012Z" },
    { url = "https://files.pythonhosted.org/packages/9d/ba/2cc9e3e7dfdf7760a6ed8da7446d22536f3d0ce114ac63dee2a5a3599e62/charset_normalizer-3.4.6-cp314-cp314-musllinux_1_2_armv7l.whl", hash = "sha256:7f9019c9cb613f084481bd6a100b12e1547cf2efe362d873c2e31e4035a6fa43", size = 193511, upload-time = "2026-03-15T18:51:53.723Z" },
    { url = "https://files.pythonhosted.org/packages/9e/cb/5be49b5f776e5613be07298c80e1b02a2d900f7a7de807230595c85a8b2e/charset_normalizer-3.4.6-cp314-cp314-musllinux_1_2_ppc64le.whl", hash = "sha256:58c948d0d086229efc484fe2f30c2d382c86720f55cd9bc33591774348ad44e0", size = 220133, upload-time = "2026-03-15T18:51:55.333Z" },
    { url = "https://files.pythonhosted.org/packages/83/43/99f1b5dad345accb322c80c7821071554f791a95ee50c1c90041c157ae99/charset_normalizer-3.4.6-cp314-cp314-musllinux_1_2_riscv64.whl", hash = "sha256:419a9d91bd238052642a51938af8ac05da5b3343becde08d5cdeab9046df9ee1", size = 203035, upload-time = "2026-03-15T18:51:56.736Z" },
    { url = "https://files.pythonhosted.org/packages/87/9a/62c2cb6a531483b55dddff1a68b3d891a8b498f3ca555fbcf2978e804d9d/charset_normalizer-3.4.6-cp314-cp314-musllinux_1_2_s390x.whl", hash = "sha256:5273b9f0b5835ff0350c0828faea623c68bfa65b792720c453e22b25cc72930f", size = 216321, upload-time = "2026-03-15T18:51:58.17Z" },
    { url = "https://files.pythonhosted.org/packages/6e/79/94a010ff81e3aec7c293eb82c28f930918e517bc144c9906a060844462eb/charset_normalizer-3.4.6-cp314-cp314-musllinux_1_2_x86_64.whl", hash = "sha256:0e901eb1049fdb80f5bd11ed5ea1e498ec423102f7a9b9e4645d5b8204ff2815", size = 208973, upload-time = "2026-03-15T18:51:59.998Z" },
    { url = "https://files.pythonhosted.org/packages/2a/57/4ecff6d4ec8585342f0c71bc03efaa99cb7468f7c91a57b105bcd561cea8/charset_normalizer-3.4.6-cp314-cp314-win32.whl", hash = "sha256:b4ff1d35e8c5bd078be89349b6f3a845128e685e751b6ea1169cf2160b344c4d", size = 144610, upload-time = "2026-03-15T18:52:02.213Z" },
    { url = "https://files.pythonhosted.org/packages/80/94/8434a02d9d7f168c25767c64671fead8d599744a05d6a6c877144c754246/charset_normalizer-3.4.6-cp314-cp314-win_amd64.whl", hash = "sha256:74119174722c4349af9708993118581686f343adc1c8c9c007d59be90d077f3f", size = 154962, upload-time = "2026-03-15T18:52:03.658Z" },
    { url = "https://files.pythonhosted.org/packages/46/4c/48f2cdbfd923026503dfd67ccea45c94fd8fe988d9056b468579c66ed62b/charset_normalizer-3.4.6-cp314-cp314-win_arm64.whl", hash = "sha256:e5bcc1a1ae744e0bb59641171ae53743760130600da8db48cbb6e4918e186e4e", size = 143595, upload-time = "2026-03-15T18:52:05.123Z" },
    { url = "https://files.pythonhosted.org/packages/31/93/8878be7569f87b14f1d52032946131bcb6ebbd8af3e20446bc04053dc3f1/charset_normalizer-3.4.6-cp314-cp314t-macosx_10_15_universal2.whl", hash = "sha256:ad8faf8df23f0378c6d527d8b0b15ea4a2e23c89376877c598c4870d1b2c7866", size = 314828, upload-time = "2026-03-15T18:52:06.831Z" },
    { url = "https://files.pythonhosted.org/packages/06/b6/fae511ca98aac69ecc35cde828b0a3d146325dd03d99655ad38fc2cc3293/charset_normalizer-3.4.6-cp314-cp314t-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:f5ea69428fa1b49573eef0cc44a1d43bebd45ad0c611eb7d7eac760c7ae771bc", size = 208138, upload-time = "2026-03-15T18:52:08.239Z" },
    { url = "https://files.pythonhosted.org/packages/54/57/64caf6e1bf07274a1e0b7c160a55ee9e8c9ec32c46846ce59b9c333f7008/charset_normalizer-3.4.6-cp314-cp314t-manylinux2014_ppc64le.manylinux_2_17_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:06a7e86163334edfc5d20fe104db92fcd666e5a5df0977cb5680a506fe26cc8e", size = 224679, upload-time = "2026-03-15T18:52:10.043Z" },
    { url = "https://files.pythonhosted.org/packages/aa/cb/9ff5a25b9273ef160861b41f6937f86fae18b0792fe0a8e75e06acb08f1d/charset_normalizer-3.4.6-cp314-cp314t-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:e1f6e2f00a6b8edb562826e4632e26d063ac10307e80f7461f7de3ad8ef3f077", size = 223475, upload-time = "2026-03-15T18:52:11.854Z" },
    { url = "https://files.pythonhosted.org/packages/fc/97/440635fc093b8d7347502a377031f9605a1039c958f3cd18dcacffb37743/charset_normalizer-3.4.6-cp314-cp314t-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:95b52c68d64c1878818687a473a10547b3292e82b6f6fe483808fb1468e2f52f", size = 215230, upload-time = "2026-03-15T18:52:13.325Z" },
    { url = "https://files.pythonhosted.org/packages/cd/24/afff630feb571a13f07c8539fbb502d2ab494019492aaffc78ef41f1d1d0/charset_normalizer-3.4.6-cp314-cp314t-manylinux_2_31_armv7l.whl", hash = "sha256:7504e9b7dc05f99a9bbb4525c67a2c155073b44d720470a148b34166a69c054e", size = 199045, upload-time = "2026-03-15T18:52:14.752Z" },
    { url = "https://files.pythonhosted.org/packages/e5/17/d1399ecdaf7e0498c327433e7eefdd862b41236a7e484355b8e0e5ebd64b/charset_normalizer-3.4.6-cp314-cp314t-manylinux_2_31_riscv64.manylinux_2_39_riscv64.whl", hash = "sha256:172985e4ff804a7ad08eebec0a1640ece87ba5041d565fff23c8f99c1f389484", size = 211658, upload-time = "2026-03-15T18:52:16.278Z" },
    { url = "https://files.pythonhosted.org/packages/b5/38/16baa0affb957b3d880e5ac2144caf3f9d7de7bc4a91842e447fbb5e8b67/charset_normalizer-3.4.6-cp314-cp314t-musllinux_1_2_aarch64.whl", hash = "sha256:4be9f4830ba8741527693848403e2c457c16e499100963ec711b1c6f2049b7c7", size = 210769, upload-time = "2026-03-15T18:52:17.782Z" },
    { url = "https://files.pythonhosted.org/packages/05/34/c531bc6ac4c21da9ddfddb3107be2287188b3ea4b53b70fc58f2a77ac8d8/charset_normalizer-3.4.6-cp314-cp314t-musllinux_1_2_armv7l.whl", hash = "sha256:79090741d842f564b1b2827c0b82d846405b744d31e84f18d7a7b41c20e473ff", size = 201328, upload-time = "2026-03-15T18:52:19.553Z" },
    { url = "https://files.pythonhosted.org/packages/fa/73/a5a1e9ca5f234519c1953608a03fe109c306b97fdfb25f09182babad51a7/charset_normalizer-3.4.6-cp314-cp314t-musllinux_1_2_ppc64le.whl", hash = "sha256:87725cfb1a4f1f8c2fc9890ae2f42094120f4b44db9360be5d99a4c6b0e03a9e", size = 225302, upload-time = "2026-03-15T18:52:21.043Z" },
    { url = "https://files.pythonhosted.org/packages/ba/f6/cd782923d112d296294dea4bcc7af5a7ae0f86ab79f8fefbda5526b6cfc0/charset_normalizer-3.4.6-cp314-cp314t-musllinux_1_2_riscv64.whl", hash = "sha256:fcce033e4021347d80ed9c66dcf1e7b1546319834b74445f561d2e2221de5659", size = 211127, upload-time = "2026-03-15T18:52:22.491Z" },
    { url = "https://files.pythonhosted.org/packages/0e/c5/0b6898950627af7d6103a449b22320372c24c6feda91aa24e201a478d161/charset_normalizer-3.4.6-cp314-cp314t-musllinux_1_2_s390x.whl", hash = "sha256:ca0276464d148c72defa8bb4390cce01b4a0e425f3b50d1435aa6d7a18107602", size = 222840, upload-time = "2026-03-15T18:52:24.113Z" },
    { url = "https://files.pythonhosted.org/packages/7d/25/c4bba773bef442cbdc06111d40daa3de5050a676fa26e85090fc54dd12f0/charset_normalizer-3.4.6-cp314-cp314t-musllinux_1_2_x86_64.whl", hash = "sha256:197c1a244a274bb016dd8b79204850144ef77fe81c5b797dc389327adb552407", size = 216890, upload-time = "2026-03-15T18:52:25.541Z" },
    { url = "https://files.pythonhosted.org/packages/35/1a/05dacadb0978da72ee287b0143097db12f2e7e8d3ffc4647da07a383b0b7/charset_normalizer-3.4.6-cp314-cp314t-win32.whl", hash = "sha256:2a24157fa36980478dd1770b585c0f30d19e18f4fb0c47c13aa568f871718579", size = 155379, upload-time = "2026-03-15T18:52:27.05Z" },
    { url = "https://files.pythonhosted.org/packages/5d/7a/d269d834cb3a76291651256f3b9a5945e81d0a49ab9f4a498964e83c0416/charset_normalizer-3.4.6-cp314-cp314t-win_amd64.whl", hash = "sha256:cd5e2801c89992ed8c0a3f0293ae83c159a60d9a5d685005383ef4caca77f2c4", size = 169043, upload-time = "2026-03-15T18:52:28.502Z" },
    { url = "https://files.pythonhosted.org/packages/23/06/28b29fba521a37a8932c6a84192175c34d49f84a6d4773fa63d05f9aff22/charset_normalizer-3.4.6-cp314-cp314t-win_arm64.whl", hash = "sha256:47955475ac79cc504ef2704b192364e51d0d473ad452caedd0002605f780101c", size = 148523, upload-time = "2026-03-15T18:52:29.956Z" },
    { url = "https://files.pythonhosted.org/packages/2a/68/687187c7e26cb24ccbd88e5069f5ef00eba804d36dde11d99aad0838ab45/charset_normalizer-3.4.6-py3-none-any.whl", hash = "sha256:947cf925bc916d90adba35a64c82aace04fa39b46b52d4630ece166655905a69", size = 61455, upload-time = "2026-03-15T18:53:23.833Z" },
]

[[package]]
name = "chromadb"
version = "1.5.5"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "bcrypt" },
    { name = "build" },
    { name = "grpcio" },
    { name = "httpx" },
    { name = "importlib-resources" },
    { name = "jsonschema" },
    { name = "kubernetes" },
    { name = "mmh3" },
    { name = "numpy" },
    { name = "onnxruntime" },
    { name = "opentelemetry-api" },
    { name = "opentelemetry-exporter-otlp-proto-grpc" },
    { name = "opentelemetry-sdk" },
    { name = "orjson" },
    { name = "overrides" },
    { name = "pybase64" },
    { name = "pydantic" },
    { name = "pydantic-settings" },
    { name = "pypika" },
    { name = "pyyaml" },
    { name = "rich" },
    { name = "tenacity" },
    { name = "tokenizers" },
    { name = "tqdm" },
    { name = "typer" },
    { name = "typing-extensions" },
    { name = "uvicorn", extra = ["standard"] },
]
sdist = { url = "https://files.pythonhosted.org/packages/3a/6d/ab03e16be3ec663e353166f38be082efb51c0988687f8c8eee1416a7e732/chromadb-1.5.5.tar.gz", hash = "sha256:8d669285b77cc288db27583a57b2f85ba451a9b8e3bef85a260cd78e6b57be35", size = 2411397, upload-time = "2026-03-10T09:30:01.987Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/f0/62/ee578f8ccd62928257558b13a3e7c236e402cfb319c9b201b6a75897d644/chromadb-1.5.5-cp39-abi3-macosx_10_12_x86_64.whl", hash = "sha256:d590998ed81164afbfb1734bb534b25ec2c9810fc1c5ce53bf8f7ac644a79887", size = 20800888, upload-time = "2026-03-10T09:29:59.546Z" },
    { url = "https://files.pythonhosted.org/packages/f8/ce/430a87d906f79cdc7e23efcd89dd237e3dbedaf6704b40ce1da127993bf8/chromadb-1.5.5-cp39-abi3-macosx_11_0_arm64.whl", hash = "sha256:5ff2912d20a82fdbf4e27ff3e1c91dab25e2ba2c629f9739bc12c11a3151aac7", size = 20091810, upload-time = "2026-03-10T09:29:56.044Z" },
    { url = "https://files.pythonhosted.org/packages/a8/5a/11543a76ab25c55bec6133bb98ce0dc0f4850acb36600344d8286734a051/chromadb-1.5.5-cp39-abi3-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:2f54e7736ae0eeec436a1c1fb04b77b2c6c4108996790ef16f88327e38ad13cd", size = 20740649, upload-time = "2026-03-10T09:29:49.346Z" },
    { url = "https://files.pythonhosted.org/packages/d3/66/e0b35c41be7c02d6fa37f6c8f61a16b7b20607ddc847574e9a5503fe853b/chromadb-1.5.5-cp39-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:bb238ae508a6ce68fdd7875e040d7e5aa29d6e40fb651b51f5537b7cda789762", size = 21589423, upload-time = "2026-03-10T09:29:52.724Z" },
    { url = "https://files.pythonhosted.org/packages/a2/df/ce1ffcc0ad3eef8bd35b920809b990e6925ba94b2580dc5bd7ccde0fc06a/chromadb-1.5.5-cp39-abi3-win_amd64.whl", hash = "sha256:3953403b63bb1c05405d10db36d183c4d19a027938c15898510d11943499046f", size = 21915873, upload-time = "2026-03-10T09:30:21.349Z" },
]

[[package]]
name = "click"
version = "8.3.1"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "colorama", marker = "sys_platform == 'win32'" },
]
sdist = { url = "https://files.pythonhosted.org/packages/3d/fa/656b739db8587d7b5dfa22e22ed02566950fbfbcdc20311993483657a5c0/click-8.3.1.tar.gz", hash = "sha256:12ff4785d337a1bb490bb7e9c2b1ee5da3112e94a8622f26a6c77f5d2fc6842a", size = 295065, upload-time = "2025-11-15T20:45:42.706Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/98/78/01c019cdb5d6498122777c1a43056ebb3ebfeef2076d9d026bfe15583b2b/click-8.3.1-py3-none-any.whl", hash = "sha256:981153a64e25f12d547d3426c367a4857371575ee7ad18df2a6183ab0545b2a6", size = 108274, upload-time = "2025-11-15T20:45:41.139Z" },
]

[[package]]
name = "colorama"
version = "0.4.6"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/d8/53/6f443c9a4a8358a93a6792e2acffb9d9d5cb0a5cfd8802644b7b1c9a02e4/colorama-0.4.6.tar.gz", hash = "sha256:08695f5cb7ed6e0531a20572697297273c47b8cae5a63ffc6d6ed5c201be6e44", size = 27697, upload-time = "2022-10-25T02:36:22.414Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/d1/d6/3965ed04c63042e047cb6a3e6ed1a63a35087b6a609aa3a15ed8ac56c221/colorama-0.4.6-py2.py3-none-any.whl", hash = "sha256:4f1d9991f5acc0ca119f9d443620b77f9d6b33703e51011c16baf57afb285fc6", size = 25335, upload-time = "2022-10-25T02:36:20.889Z" },
]

[[package]]
name = "cryptography"
version = "46.0.5"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "cffi", marker = "platform_python_implementation != 'PyPy'" },
]
sdist = { url = "https://files.pythonhosted.org/packages/60/04/ee2a9e8542e4fa2773b81771ff8349ff19cdd56b7258a0cc442639052edb/cryptography-46.0.5.tar.gz", hash = "sha256:abace499247268e3757271b2f1e244b36b06f8515cf27c4d49468fc9eb16e93d", size = 750064, upload-time = "2026-02-10T19:18:38.255Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/f7/81/b0bb27f2ba931a65409c6b8a8b358a7f03c0e46eceacddff55f7c84b1f3b/cryptography-46.0.5-cp311-abi3-macosx_10_9_universal2.whl", hash = "sha256:351695ada9ea9618b3500b490ad54c739860883df6c1f555e088eaf25b1bbaad", size = 7176289, upload-time = "2026-02-10T19:17:08.274Z" },
    { url = "https://files.pythonhosted.org/packages/ff/9e/6b4397a3e3d15123de3b1806ef342522393d50736c13b20ec4c9ea6693a6/cryptography-46.0.5-cp311-abi3-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:c18ff11e86df2e28854939acde2d003f7984f721eba450b56a200ad90eeb0e6b", size = 4275637, upload-time = "2026-02-10T19:17:10.53Z" },
    { url = "https://files.pythonhosted.org/packages/63/e7/471ab61099a3920b0c77852ea3f0ea611c9702f651600397ac567848b897/cryptography-46.0.5-cp311-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:4d7e3d356b8cd4ea5aff04f129d5f66ebdc7b6f8eae802b93739ed520c47c79b", size = 4424742, upload-time = "2026-02-10T19:17:12.388Z" },
    { url = "https://files.pythonhosted.org/packages/37/53/a18500f270342d66bf7e4d9f091114e31e5ee9e7375a5aba2e85a91e0044/cryptography-46.0.5-cp311-abi3-manylinux_2_28_aarch64.whl", hash = "sha256:50bfb6925eff619c9c023b967d5b77a54e04256c4281b0e21336a130cd7fc263", size = 4277528, upload-time = "2026-02-10T19:17:13.853Z" },
    { url = "https://files.pythonhosted.org/packages/22/29/c2e812ebc38c57b40e7c583895e73c8c5adb4d1e4a0cc4c5a4fdab2b1acc/cryptography-46.0.5-cp311-abi3-manylinux_2_28_ppc64le.whl", hash = "sha256:803812e111e75d1aa73690d2facc295eaefd4439be1023fefc4995eaea2af90d", size = 4947993, upload-time = "2026-02-10T19:17:15.618Z" },
    { url = "https://files.pythonhosted.org/packages/6b/e7/237155ae19a9023de7e30ec64e5d99a9431a567407ac21170a046d22a5a3/cryptography-46.0.5-cp311-abi3-manylinux_2_28_x86_64.whl", hash = "sha256:3ee190460e2fbe447175cda91b88b84ae8322a104fc27766ad09428754a618ed", size = 4456855, upload-time = "2026-02-10T19:17:17.221Z" },
    { url = "https://files.pythonhosted.org/packages/2d/87/fc628a7ad85b81206738abbd213b07702bcbdada1dd43f72236ef3cffbb5/cryptography-46.0.5-cp311-abi3-manylinux_2_31_armv7l.whl", hash = "sha256:f145bba11b878005c496e93e257c1e88f154d278d2638e6450d17e0f31e558d2", size = 3984635, upload-time = "2026-02-10T19:17:18.792Z" },
    { url = "https://files.pythonhosted.org/packages/84/29/65b55622bde135aedf4565dc509d99b560ee4095e56989e815f8fd2aa910/cryptography-46.0.5-cp311-abi3-manylinux_2_34_aarch64.whl", hash = "sha256:e9251e3be159d1020c4030bd2e5f84d6a43fe54b6c19c12f51cde9542a2817b2", size = 4277038, upload-time = "2026-02-10T19:17:20.256Z" },
    { url = "https://files.pythonhosted.org/packages/bc/36/45e76c68d7311432741faf1fbf7fac8a196a0a735ca21f504c75d37e2558/cryptography-46.0.5-cp311-abi3-manylinux_2_34_ppc64le.whl", hash = "sha256:47fb8a66058b80e509c47118ef8a75d14c455e81ac369050f20ba0d23e77fee0", size = 4912181, upload-time = "2026-02-10T19:17:21.825Z" },
    { url = "https://files.pythonhosted.org/packages/6d/1a/c1ba8fead184d6e3d5afcf03d569acac5ad063f3ac9fb7258af158f7e378/cryptography-46.0.5-cp311-abi3-manylinux_2_34_x86_64.whl", hash = "sha256:4c3341037c136030cb46e4b1e17b7418ea4cbd9dd207e4a6f3b2b24e0d4ac731", size = 4456482, upload-time = "2026-02-10T19:17:25.133Z" },
    { url = "https://files.pythonhosted.org/packages/f9/e5/3fb22e37f66827ced3b902cf895e6a6bc1d095b5b26be26bd13c441fdf19/cryptography-46.0.5-cp311-abi3-musllinux_1_2_aarch64.whl", hash = "sha256:890bcb4abd5a2d3f852196437129eb3667d62630333aacc13dfd470fad3aaa82", size = 4405497, upload-time = "2026-02-10T19:17:26.66Z" },
    { url = "https://files.pythonhosted.org/packages/1a/df/9d58bb32b1121a8a2f27383fabae4d63080c7ca60b9b5c88be742be04ee7/cryptography-46.0.5-cp311-abi3-musllinux_1_2_x86_64.whl", hash = "sha256:80a8d7bfdf38f87ca30a5391c0c9ce4ed2926918e017c29ddf643d0ed2778ea1", size = 4667819, upload-time = "2026-02-10T19:17:28.569Z" },
    { url = "https://files.pythonhosted.org/packages/ea/ed/325d2a490c5e94038cdb0117da9397ece1f11201f425c4e9c57fe5b9f08b/cryptography-46.0.5-cp311-abi3-win32.whl", hash = "sha256:60ee7e19e95104d4c03871d7d7dfb3d22ef8a9b9c6778c94e1c8fcc8365afd48", size = 3028230, upload-time = "2026-02-10T19:17:30.518Z" },
    { url = "https://files.pythonhosted.org/packages/e9/5a/ac0f49e48063ab4255d9e3b79f5def51697fce1a95ea1370f03dc9db76f6/cryptography-46.0.5-cp311-abi3-win_amd64.whl", hash = "sha256:38946c54b16c885c72c4f59846be9743d699eee2b69b6988e0a00a01f46a61a4", size = 3480909, upload-time = "2026-02-10T19:17:32.083Z" },
    { url = "https://files.pythonhosted.org/packages/00/13/3d278bfa7a15a96b9dc22db5a12ad1e48a9eb3d40e1827ef66a5df75d0d0/cryptography-46.0.5-cp314-cp314t-macosx_10_9_universal2.whl", hash = "sha256:94a76daa32eb78d61339aff7952ea819b1734b46f73646a07decb40e5b3448e2", size = 7119287, upload-time = "2026-02-10T19:17:33.801Z" },
    { url = "https://files.pythonhosted.org/packages/67/c8/581a6702e14f0898a0848105cbefd20c058099e2c2d22ef4e476dfec75d7/cryptography-46.0.5-cp314-cp314t-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:5be7bf2fb40769e05739dd0046e7b26f9d4670badc7b032d6ce4db64dddc0678", size = 4265728, upload-time = "2026-02-10T19:17:35.569Z" },
    { url = "https://files.pythonhosted.org/packages/dd/4a/ba1a65ce8fc65435e5a849558379896c957870dd64fecea97b1ad5f46a37/cryptography-46.0.5-cp314-cp314t-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:fe346b143ff9685e40192a4960938545c699054ba11d4f9029f94751e3f71d87", size = 4408287, upload-time = "2026-02-10T19:17:36.938Z" },
    { url = "https://files.pythonhosted.org/packages/f8/67/8ffdbf7b65ed1ac224d1c2df3943553766914a8ca718747ee3871da6107e/cryptography-46.0.5-cp314-cp314t-manylinux_2_28_aarch64.whl", hash = "sha256:c69fd885df7d089548a42d5ec05be26050ebcd2283d89b3d30676eb32ff87dee", size = 4270291, upload-time = "2026-02-10T19:17:38.748Z" },
    { url = "https://files.pythonhosted.org/packages/f8/e5/f52377ee93bc2f2bba55a41a886fd208c15276ffbd2569f2ddc89d50e2c5/cryptography-46.0.5-cp314-cp314t-manylinux_2_28_ppc64le.whl", hash = "sha256:8293f3dea7fc929ef7240796ba231413afa7b68ce38fd21da2995549f5961981", size = 4927539, upload-time = "2026-02-10T19:17:40.241Z" },
    { url = "https://files.pythonhosted.org/packages/3b/02/cfe39181b02419bbbbcf3abdd16c1c5c8541f03ca8bda240debc467d5a12/cryptography-46.0.5-cp314-cp314t-manylinux_2_28_x86_64.whl", hash = "sha256:1abfdb89b41c3be0365328a410baa9df3ff8a9110fb75e7b52e66803ddabc9a9", size = 4442199, upload-time = "2026-02-10T19:17:41.789Z" },
    { url = "https://files.pythonhosted.org/packages/c0/96/2fcaeb4873e536cf71421a388a6c11b5bc846e986b2b069c79363dc1648e/cryptography-46.0.5-cp314-cp314t-manylinux_2_31_armv7l.whl", hash = "sha256:d66e421495fdb797610a08f43b05269e0a5ea7f5e652a89bfd5a7d3c1dee3648", size = 3960131, upload-time = "2026-02-10T19:17:43.379Z" },
    { url = "https://files.pythonhosted.org/packages/d8/d2/b27631f401ddd644e94c5cf33c9a4069f72011821cf3dc7309546b0642a0/cryptography-46.0.5-cp314-cp314t-manylinux_2_34_aarch64.whl", hash = "sha256:4e817a8920bfbcff8940ecfd60f23d01836408242b30f1a708d93198393a80b4", size = 4270072, upload-time = "2026-02-10T19:17:45.481Z" },
    { url = "https://files.pythonhosted.org/packages/f4/a7/60d32b0370dae0b4ebe55ffa10e8599a2a59935b5ece1b9f06edb73abdeb/cryptography-46.0.5-cp314-cp314t-manylinux_2_34_ppc64le.whl", hash = "sha256:68f68d13f2e1cb95163fa3b4db4bf9a159a418f5f6e7242564fc75fcae667fd0", size = 4892170, upload-time = "2026-02-10T19:17:46.997Z" },
    { url = "https://files.pythonhosted.org/packages/d2/b9/cf73ddf8ef1164330eb0b199a589103c363afa0cf794218c24d524a58eab/cryptography-46.0.5-cp314-cp314t-manylinux_2_34_x86_64.whl", hash = "sha256:a3d1fae9863299076f05cb8a778c467578262fae09f9dc0ee9b12eb4268ce663", size = 4441741, upload-time = "2026-02-10T19:17:48.661Z" },
    { url = "https://files.pythonhosted.org/packages/5f/eb/eee00b28c84c726fe8fa0158c65afe312d9c3b78d9d01daf700f1f6e37ff/cryptography-46.0.5-cp314-cp314t-musllinux_1_2_aarch64.whl", hash = "sha256:c4143987a42a2397f2fc3b4d7e3a7d313fbe684f67ff443999e803dd75a76826", size = 4396728, upload-time = "2026-02-10T19:17:50.058Z" },
    { url = "https://files.pythonhosted.org/packages/65/f4/6bc1a9ed5aef7145045114b75b77c2a8261b4d38717bd8dea111a63c3442/cryptography-46.0.5-cp314-cp314t-musllinux_1_2_x86_64.whl", hash = "sha256:7d731d4b107030987fd61a7f8ab512b25b53cef8f233a97379ede116f30eb67d", size = 4652001, upload-time = "2026-02-10T19:17:51.54Z" },
    { url = "https://files.pythonhosted.org/packages/86/ef/5d00ef966ddd71ac2e6951d278884a84a40ffbd88948ef0e294b214ae9e4/cryptography-46.0.5-cp314-cp314t-win32.whl", hash = "sha256:c3bcce8521d785d510b2aad26ae2c966092b7daa8f45dd8f44734a104dc0bc1a", size = 3003637, upload-time = "2026-02-10T19:17:52.997Z" },
    { url = "https://files.pythonhosted.org/packages/b7/57/f3f4160123da6d098db78350fdfd9705057aad21de7388eacb2401dceab9/cryptography-46.0.5-cp314-cp314t-win_amd64.whl", hash = "sha256:4d8ae8659ab18c65ced284993c2265910f6c9e650189d4e3f68445ef82a810e4", size = 3469487, upload-time = "2026-02-10T19:17:54.549Z" },
    { url = "https://files.pythonhosted.org/packages/e2/fa/a66aa722105ad6a458bebd64086ca2b72cdd361fed31763d20390f6f1389/cryptography-46.0.5-cp38-abi3-macosx_10_9_universal2.whl", hash = "sha256:4108d4c09fbbf2789d0c926eb4152ae1760d5a2d97612b92d508d96c861e4d31", size = 7170514, upload-time = "2026-02-10T19:17:56.267Z" },
    { url = "https://files.pythonhosted.org/packages/0f/04/c85bdeab78c8bc77b701bf0d9bdcf514c044e18a46dcff330df5448631b0/cryptography-46.0.5-cp38-abi3-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:7d1f30a86d2757199cb2d56e48cce14deddf1f9c95f1ef1b64ee91ea43fe2e18", size = 4275349, upload-time = "2026-02-10T19:17:58.419Z" },
    { url = "https://files.pythonhosted.org/packages/5c/32/9b87132a2f91ee7f5223b091dc963055503e9b442c98fc0b8a5ca765fab0/cryptography-46.0.5-cp38-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:039917b0dc418bb9f6edce8a906572d69e74bd330b0b3fea4f79dab7f8ddd235", size = 4420667, upload-time = "2026-02-10T19:18:00.619Z" },
    { url = "https://files.pythonhosted.org/packages/a1/a6/a7cb7010bec4b7c5692ca6f024150371b295ee1c108bdc1c400e4c44562b/cryptography-46.0.5-cp38-abi3-manylinux_2_28_aarch64.whl", hash = "sha256:ba2a27ff02f48193fc4daeadf8ad2590516fa3d0adeeb34336b96f7fa64c1e3a", size = 4276980, upload-time = "2026-02-10T19:18:02.379Z" },
    { url = "https://files.pythonhosted.org/packages/8e/7c/c4f45e0eeff9b91e3f12dbd0e165fcf2a38847288fcfd889deea99fb7b6d/cryptography-46.0.5-cp38-abi3-manylinux_2_28_ppc64le.whl", hash = "sha256:61aa400dce22cb001a98014f647dc21cda08f7915ceb95df0c9eaf84b4b6af76", size = 4939143, upload-time = "2026-02-10T19:18:03.964Z" },
    { url = "https://files.pythonhosted.org/packages/37/19/e1b8f964a834eddb44fa1b9a9976f4e414cbb7aa62809b6760c8803d22d1/cryptography-46.0.5-cp38-abi3-manylinux_2_28_x86_64.whl", hash = "sha256:3ce58ba46e1bc2aac4f7d9290223cead56743fa6ab94a5d53292ffaac6a91614", size = 4453674, upload-time = "2026-02-10T19:18:05.588Z" },
    { url = "https://files.pythonhosted.org/packages/db/ed/db15d3956f65264ca204625597c410d420e26530c4e2943e05a0d2f24d51/cryptography-46.0.5-cp38-abi3-manylinux_2_31_armv7l.whl", hash = "sha256:420d0e909050490d04359e7fdb5ed7e667ca5c3c402b809ae2563d7e66a92229", size = 3978801, upload-time = "2026-02-10T19:18:07.167Z" },
    { url = "https://files.pythonhosted.org/packages/41/e2/df40a31d82df0a70a0daf69791f91dbb70e47644c58581d654879b382d11/cryptography-46.0.5-cp38-abi3-manylinux_2_34_aarch64.whl", hash = "sha256:582f5fcd2afa31622f317f80426a027f30dc792e9c80ffee87b993200ea115f1", size = 4276755, upload-time = "2026-02-10T19:18:09.813Z" },
    { url = "https://files.pythonhosted.org/packages/33/45/726809d1176959f4a896b86907b98ff4391a8aa29c0aaaf9450a8a10630e/cryptography-46.0.5-cp38-abi3-manylinux_2_34_ppc64le.whl", hash = "sha256:bfd56bb4b37ed4f330b82402f6f435845a5f5648edf1ad497da51a8452d5d62d", size = 4901539, upload-time = "2026-02-10T19:18:11.263Z" },
    { url = "https://files.pythonhosted.org/packages/99/0f/a3076874e9c88ecb2ecc31382f6e7c21b428ede6f55aafa1aa272613e3cd/cryptography-46.0.5-cp38-abi3-manylinux_2_34_x86_64.whl", hash = "sha256:a3d507bb6a513ca96ba84443226af944b0f7f47dcc9a399d110cd6146481d24c", size = 4452794, upload-time = "2026-02-10T19:18:12.914Z" },
    { url = "https://files.pythonhosted.org/packages/02/ef/ffeb542d3683d24194a38f66ca17c0a4b8bf10631feef44a7ef64e631b1a/cryptography-46.0.5-cp38-abi3-musllinux_1_2_aarch64.whl", hash = "sha256:9f16fbdf4da055efb21c22d81b89f155f02ba420558db21288b3d0035bafd5f4", size = 4404160, upload-time = "2026-02-10T19:18:14.375Z" },
    { url = "https://files.pythonhosted.org/packages/96/93/682d2b43c1d5f1406ed048f377c0fc9fc8f7b0447a478d5c65ab3d3a66eb/cryptography-46.0.5-cp38-abi3-musllinux_1_2_x86_64.whl", hash = "sha256:ced80795227d70549a411a4ab66e8ce307899fad2220ce5ab2f296e687eacde9", size = 4667123, upload-time = "2026-02-10T19:18:15.886Z" },
    { url = "https://files.pythonhosted.org/packages/45/2d/9c5f2926cb5300a8eefc3f4f0b3f3df39db7f7ce40c8365444c49363cbda/cryptography-46.0.5-cp38-abi3-win32.whl", hash = "sha256:02f547fce831f5096c9a567fd41bc12ca8f11df260959ecc7c3202555cc47a72", size = 3010220, upload-time = "2026-02-10T19:18:17.361Z" },
    { url = "https://files.pythonhosted.org/packages/48/ef/0c2f4a8e31018a986949d34a01115dd057bf536905dca38897bacd21fac3/cryptography-46.0.5-cp38-abi3-win_amd64.whl", hash = "sha256:556e106ee01aa13484ce9b0239bca667be5004efb0aabbed28d353df86445595", size = 3467050, upload-time = "2026-02-10T19:18:18.899Z" },
    { url = "https://files.pythonhosted.org/packages/eb/dd/2d9fdb07cebdf3d51179730afb7d5e576153c6744c3ff8fded23030c204e/cryptography-46.0.5-pp311-pypy311_pp73-macosx_11_0_arm64.whl", hash = "sha256:3b4995dc971c9fb83c25aa44cf45f02ba86f71ee600d81091c2f0cbae116b06c", size = 3476964, upload-time = "2026-02-10T19:18:20.687Z" },
    { url = "https://files.pythonhosted.org/packages/e9/6f/6cc6cc9955caa6eaf83660b0da2b077c7fe8ff9950a3c5e45d605038d439/cryptography-46.0.5-pp311-pypy311_pp73-manylinux_2_28_aarch64.whl", hash = "sha256:bc84e875994c3b445871ea7181d424588171efec3e185dced958dad9e001950a", size = 4218321, upload-time = "2026-02-10T19:18:22.349Z" },
    { url = "https://files.pythonhosted.org/packages/3e/5d/c4da701939eeee699566a6c1367427ab91a8b7088cc2328c09dbee940415/cryptography-46.0.5-pp311-pypy311_pp73-manylinux_2_28_x86_64.whl", hash = "sha256:2ae6971afd6246710480e3f15824ed3029a60fc16991db250034efd0b9fb4356", size = 4381786, upload-time = "2026-02-10T19:18:24.529Z" },
    { url = "https://files.pythonhosted.org/packages/ac/97/a538654732974a94ff96c1db621fa464f455c02d4bb7d2652f4edc21d600/cryptography-46.0.5-pp311-pypy311_pp73-manylinux_2_34_aarch64.whl", hash = "sha256:d861ee9e76ace6cf36a6a89b959ec08e7bc2493ee39d07ffe5acb23ef46d27da", size = 4217990, upload-time = "2026-02-10T19:18:25.957Z" },
    { url = "https://files.pythonhosted.org/packages/ae/11/7e500d2dd3ba891197b9efd2da5454b74336d64a7cc419aa7327ab74e5f6/cryptography-46.0.5-pp311-pypy311_pp73-manylinux_2_34_x86_64.whl", hash = "sha256:2b7a67c9cd56372f3249b39699f2ad479f6991e62ea15800973b956f4b73e257", size = 4381252, upload-time = "2026-02-10T19:18:27.496Z" },
    { url = "https://files.pythonhosted.org/packages/bc/58/6b3d24e6b9bc474a2dcdee65dfd1f008867015408a271562e4b690561a4d/cryptography-46.0.5-pp311-pypy311_pp73-win_amd64.whl", hash = "sha256:8456928655f856c6e1533ff59d5be76578a7157224dbd9ce6872f25055ab9ab7", size = 3407605, upload-time = "2026-02-10T19:18:29.233Z" },
]

[[package]]
name = "dnspython"
version = "2.8.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/8c/8b/57666417c0f90f08bcafa776861060426765fdb422eb10212086fb811d26/dnspython-2.8.0.tar.gz", hash = "sha256:181d3c6996452cb1189c4046c61599b84a5a86e099562ffde77d26984ff26d0f", size = 368251, upload-time = "2025-09-07T18:58:00.022Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/ba/5a/18ad964b0086c6e62e2e7500f7edc89e3faa45033c71c1893d34eed2b2de/dnspython-2.8.0-py3-none-any.whl", hash = "sha256:01d9bbc4a2d76bf0db7c1f729812ded6d912bd318d3b1cf81d30c0f845dbf3af", size = 331094, upload-time = "2025-09-07T18:57:58.071Z" },
]

[[package]]
name = "durationpy"
version = "0.10"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/9d/a4/e44218c2b394e31a6dd0d6b095c4e1f32d0be54c2a4b250032d717647bab/durationpy-0.10.tar.gz", hash = "sha256:1fa6893409a6e739c9c72334fc65cca1f355dbdd93405d30f726deb5bde42fba", size = 3335, upload-time = "2025-05-17T13:52:37.26Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/b0/0d/9feae160378a3553fa9a339b0e9c1a048e147a4127210e286ef18b730f03/durationpy-0.10-py3-none-any.whl", hash = "sha256:3b41e1b601234296b4fb368338fdcd3e13e0b4fb5b67345948f4f2bf9868b286", size = 3922, upload-time = "2025-05-17T13:52:36.463Z" },
]

[[package]]
name = "ecdsa"
version = "0.19.1"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "six" },
]
sdist = { url = "https://files.pythonhosted.org/packages/c0/1f/924e3caae75f471eae4b26bd13b698f6af2c44279f67af317439c2f4c46a/ecdsa-0.19.1.tar.gz", hash = "sha256:478cba7b62555866fcb3bb3fe985e06decbdb68ef55713c4e5ab98c57d508e61", size = 201793, upload-time = "2025-03-13T11:52:43.25Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/cb/a3/460c57f094a4a165c84a1341c373b0a4f5ec6ac244b998d5021aade89b77/ecdsa-0.19.1-py2.py3-none-any.whl", hash = "sha256:30638e27cf77b7e15c4c4cc1973720149e1033827cfd00661ca5c8cc0cdb24c3", size = 150607, upload-time = "2025-03-13T11:52:41.757Z" },
]

[[package]]
name = "email-validator"
version = "2.3.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "dnspython" },
    { name = "idna" },
]
sdist = { url = "https://files.pythonhosted.org/packages/f5/22/900cb125c76b7aaa450ce02fd727f452243f2e91a61af068b40adba60ea9/email_validator-2.3.0.tar.gz", hash = "sha256:9fc05c37f2f6cf439ff414f8fc46d917929974a82244c20eb10231ba60c54426", size = 51238, upload-time = "2025-08-26T13:09:06.831Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/de/15/545e2b6cf2e3be84bc1ed85613edd75b8aea69807a71c26f4ca6a9258e82/email_validator-2.3.0-py3-none-any.whl", hash = "sha256:80f13f623413e6b197ae73bb10bf4eb0908faf509ad8362c5edeb0be7fd450b4", size = 35604, upload-time = "2025-08-26T13:09:05.858Z" },
]

[[package]]
name = "fastapi"
version = "0.135.1"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "annotated-doc" },
    { name = "pydantic" },
    { name = "starlette" },
    { name = "typing-extensions" },
    { name = "typing-inspection" },
]
sdist = { url = "https://files.pythonhosted.org/packages/e7/7b/f8e0211e9380f7195ba3f3d40c292594fd81ba8ec4629e3854c353aaca45/fastapi-0.135.1.tar.gz", hash = "sha256:d04115b508d936d254cea545b7312ecaa58a7b3a0f84952535b4c9afae7668cd", size = 394962, upload-time = "2026-03-01T18:18:29.369Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/e4/72/42e900510195b23a56bde950d26a51f8b723846bfcaa0286e90287f0422b/fastapi-0.135.1-py3-none-any.whl", hash = "sha256:46e2fc5745924b7c840f71ddd277382af29ce1cdb7d5eab5bf697e3fb9999c9e", size = 116999, upload-time = "2026-03-01T18:18:30.831Z" },
]

[[package]]
name = "filelock"
version = "3.25.2"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/94/b8/00651a0f559862f3bb7d6f7477b192afe3f583cc5e26403b44e59a55ab34/filelock-3.25.2.tar.gz", hash = "sha256:b64ece2b38f4ca29dd3e810287aa8c48182bbecd1ae6e9ae126c9b35f1382694", size = 40480, upload-time = "2026-03-11T20:45:38.487Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/a4/a5/842ae8f0c08b61d6484b52f99a03510a3a72d23141942d216ebe81fefbce/filelock-3.25.2-py3-none-any.whl", hash = "sha256:ca8afb0da15f229774c9ad1b455ed96e85a81373065fb10446672f64444ddf70", size = 26759, upload-time = "2026-03-11T20:45:37.437Z" },
]

[[package]]
name = "flatbuffers"
version = "25.12.19"
source = { registry = "https://pypi.org/simple" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/e8/2d/d2a548598be01649e2d46231d151a6c56d10b964d94043a335ae56ea2d92/flatbuffers-25.12.19-py2.py3-none-any.whl", hash = "sha256:7634f50c427838bb021c2d66a3d1168e9d199b0607e6329399f04846d42e20b4", size = 26661, upload-time = "2025-12-19T23:16:13.622Z" },
]

[[package]]
name = "fsspec"
version = "2026.3.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/e1/cf/b50ddf667c15276a9ab15a70ef5f257564de271957933ffea49d2cdbcdfb/fsspec-2026.3.0.tar.gz", hash = "sha256:1ee6a0e28677557f8c2f994e3eea77db6392b4de9cd1f5d7a9e87a0ae9d01b41", size = 313547, upload-time = "2026-03-27T19:11:14.892Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/d5/1f/5f4a3cd9e4440e9d9bc78ad0a91a1c8d46b4d429d5239ebe6793c9fe5c41/fsspec-2026.3.0-py3-none-any.whl", hash = "sha256:d2ceafaad1b3457968ed14efa28798162f1638dbb5d2a6868a2db002a5ee39a4", size = 202595, upload-time = "2026-03-27T19:11:13.595Z" },
]

[[package]]
name = "googleapis-common-protos"
version = "1.73.1"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "protobuf" },
]
sdist = { url = "https://files.pythonhosted.org/packages/a1/c0/4a54c386282c13449eca8bbe2ddb518181dc113e78d240458a68856b4d69/googleapis_common_protos-1.73.1.tar.gz", hash = "sha256:13114f0e9d2391756a0194c3a8131974ed7bffb06086569ba193364af59163b6", size = 147506, upload-time = "2026-03-26T22:17:38.451Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/dc/82/fcb6520612bec0c39b973a6c0954b6a0d948aadfe8f7e9487f60ceb8bfa6/googleapis_common_protos-1.73.1-py3-none-any.whl", hash = "sha256:e51f09eb0a43a8602f5a915870972e6b4a394088415c79d79605a46d8e826ee8", size = 297556, upload-time = "2026-03-26T22:15:58.455Z" },
]

[[package]]
name = "grpcio"
version = "1.80.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "typing-extensions" },
]
sdist = { url = "https://files.pythonhosted.org/packages/b7/48/af6173dbca4454f4637a4678b67f52ca7e0c1ed7d5894d89d434fecede05/grpcio-1.80.0.tar.gz", hash = "sha256:29aca15edd0688c22ba01d7cc01cb000d72b2033f4a3c72a81a19b56fd143257", size = 12978905, upload-time = "2026-03-30T08:49:10.502Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/5d/db/1d56e5f5823257b291962d6c0ce106146c6447f405b60b234c4f222a7cde/grpcio-1.80.0-cp311-cp311-linux_armv7l.whl", hash = "sha256:dfab85db094068ff42e2a3563f60ab3dddcc9d6488a35abf0132daec13209c8a", size = 6055009, upload-time = "2026-03-30T08:46:46.265Z" },
    { url = "https://files.pythonhosted.org/packages/6e/18/c83f3cad64c5ca63bca7e91e5e46b0d026afc5af9d0a9972472ceba294b3/grpcio-1.80.0-cp311-cp311-macosx_11_0_universal2.whl", hash = "sha256:5c07e82e822e1161354e32da2662f741a4944ea955f9f580ec8fb409dd6f6060", size = 12035295, upload-time = "2026-03-30T08:46:49.099Z" },
    { url = "https://files.pythonhosted.org/packages/0f/8e/e14966b435be2dda99fbe89db9525ea436edc79780431a1c2875a3582644/grpcio-1.80.0-cp311-cp311-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:ba0915d51fd4ced2db5ff719f84e270afe0e2d4c45a7bdb1e8d036e4502928c2", size = 6610297, upload-time = "2026-03-30T08:46:52.123Z" },
    { url = "https://files.pythonhosted.org/packages/cc/26/d5eb38f42ce0e3fdc8174ea4d52036ef8d58cc4426cb800f2610f625dd75/grpcio-1.80.0-cp311-cp311-manylinux2014_i686.manylinux_2_17_i686.whl", hash = "sha256:3cb8130ba457d2aa09fa6b7c3ed6b6e4e6a2685fce63cb803d479576c4d80e21", size = 7300208, upload-time = "2026-03-30T08:46:54.859Z" },
    { url = "https://files.pythonhosted.org/packages/25/51/bd267c989f85a17a5b3eea65a6feb4ff672af41ca614e5a0279cc0ea381c/grpcio-1.80.0-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:09e5e478b3d14afd23f12e49e8b44c8684ac3c5f08561c43a5b9691c54d136ab", size = 6813442, upload-time = "2026-03-30T08:46:57.056Z" },
    { url = "https://files.pythonhosted.org/packages/9e/d9/d80eef735b19e9169e30164bbf889b46f9df9127598a83d174eb13a48b26/grpcio-1.80.0-cp311-cp311-musllinux_1_2_aarch64.whl", hash = "sha256:00168469238b022500e486c1c33916acf2f2a9b2c022202cf8a1885d2e3073c1", size = 7414743, upload-time = "2026-03-30T08:46:59.682Z" },
    { url = "https://files.pythonhosted.org/packages/de/f2/567f5bd5054398ed6b0509b9a30900376dcf2786bd936812098808b49d8d/grpcio-1.80.0-cp311-cp311-musllinux_1_2_i686.whl", hash = "sha256:8502122a3cc1714038e39a0b071acb1207ca7844208d5ea0d091317555ee7106", size = 8426046, upload-time = "2026-03-30T08:47:02.474Z" },
    { url = "https://files.pythonhosted.org/packages/62/29/73ef0141b4732ff5eacd68430ff2512a65c004696997f70476a83e548e7e/grpcio-1.80.0-cp311-cp311-musllinux_1_2_x86_64.whl", hash = "sha256:ce1794f4ea6cc3ca29463f42d665c32ba1b964b48958a66497917fe9069f26e6", size = 7851641, upload-time = "2026-03-30T08:47:05.462Z" },
    { url = "https://files.pythonhosted.org/packages/46/69/abbfa360eb229a8623bab5f5a4f8105e445bd38ce81a89514ba55d281ad0/grpcio-1.80.0-cp311-cp311-win32.whl", hash = "sha256:51b4a7189b0bef2aa30adce3c78f09c83526cf3dddb24c6a96555e3b97340440", size = 4154368, upload-time = "2026-03-30T08:47:08.027Z" },
    { url = "https://files.pythonhosted.org/packages/6f/d4/ae92206d01183b08613e846076115f5ac5991bae358d2a749fa864da5699/grpcio-1.80.0-cp311-cp311-win_amd64.whl", hash = "sha256:02e64bb0bb2da14d947a49e6f120a75e947250aebe65f9629b62bb1f5c14e6e9", size = 4894235, upload-time = "2026-03-30T08:47:10.839Z" },
    { url = "https://files.pythonhosted.org/packages/5c/e8/a2b749265eb3415abc94f2e619bbd9e9707bebdda787e61c593004ec927a/grpcio-1.80.0-cp312-cp312-linux_armv7l.whl", hash = "sha256:c624cc9f1008361014378c9d776de7182b11fe8b2e5a81bc69f23a295f2a1ad0", size = 6015616, upload-time = "2026-03-30T08:47:13.428Z" },
    { url = "https://files.pythonhosted.org/packages/3e/97/b1282161a15d699d1e90c360df18d19165a045ce1c343c7f313f5e8a0b77/grpcio-1.80.0-cp312-cp312-macosx_11_0_universal2.whl", hash = "sha256:f49eddcac43c3bf350c0385366a58f36bed8cc2c0ec35ef7b74b49e56552c0c2", size = 12014204, upload-time = "2026-03-30T08:47:15.873Z" },
    { url = "https://files.pythonhosted.org/packages/6e/5e/d319c6e997b50c155ac5a8cb12f5173d5b42677510e886d250d50264949d/grpcio-1.80.0-cp312-cp312-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:d334591df610ab94714048e0d5b4f3dd5ad1bee74dfec11eee344220077a79de", size = 6563866, upload-time = "2026-03-30T08:47:18.588Z" },
    { url = "https://files.pythonhosted.org/packages/ae/f6/fdd975a2cb4d78eb67769a7b3b3830970bfa2e919f1decf724ae4445f42c/grpcio-1.80.0-cp312-cp312-manylinux2014_i686.manylinux_2_17_i686.whl", hash = "sha256:0cb517eb1d0d0aaf1d87af7cc5b801d686557c1d88b2619f5e31fab3c2315921", size = 7273060, upload-time = "2026-03-30T08:47:21.113Z" },
    { url = "https://files.pythonhosted.org/packages/db/f0/a3deb5feba60d9538a962913e37bd2e69a195f1c3376a3dd44fe0427e996/grpcio-1.80.0-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:4e78c4ac0d97dc2e569b2f4bcbbb447491167cb358d1a389fc4af71ab6f70411", size = 6782121, upload-time = "2026-03-30T08:47:23.827Z" },
    { url = "https://files.pythonhosted.org/packages/ca/84/36c6dcfddc093e108141f757c407902a05085e0c328007cb090d56646cdf/grpcio-1.80.0-cp312-cp312-musllinux_1_2_aarch64.whl", hash = "sha256:2ed770b4c06984f3b47eb0517b1c69ad0b84ef3f40128f51448433be904634cd", size = 7383811, upload-time = "2026-03-30T08:47:26.517Z" },
    { url = "https://files.pythonhosted.org/packages/7c/ef/f3a77e3dc5b471a0ec86c564c98d6adfa3510d38f8ee99010410858d591e/grpcio-1.80.0-cp312-cp312-musllinux_1_2_i686.whl", hash = "sha256:256507e2f524092f1473071a05e65a5b10d84b82e3ff24c5b571513cfaa61e2f", size = 8393860, upload-time = "2026-03-30T08:47:29.439Z" },
    { url = "https://files.pythonhosted.org/packages/9b/8d/9d4d27ed7f33d109c50d6b5ce578a9914aa68edab75d65869a17e630a8d1/grpcio-1.80.0-cp312-cp312-musllinux_1_2_x86_64.whl", hash = "sha256:9a6284a5d907c37db53350645567c522be314bac859a64a7a5ca63b77bb7958f", size = 7830132, upload-time = "2026-03-30T08:47:33.254Z" },
    { url = "https://files.pythonhosted.org/packages/14/e4/9990b41c6d7a44e1e9dee8ac11d7a9802ba1378b40d77468a7761d1ad288/grpcio-1.80.0-cp312-cp312-win32.whl", hash = "sha256:c71309cfce2f22be26aa4a847357c502db6c621f1a49825ae98aa0907595b193", size = 4140904, upload-time = "2026-03-30T08:47:35.319Z" },
    { url = "https://files.pythonhosted.org/packages/2f/2c/296f6138caca1f4b92a31ace4ae1b87dab692fc16a7a3417af3bb3c805bf/grpcio-1.80.0-cp312-cp312-win_amd64.whl", hash = "sha256:9fe648599c0e37594c4809d81a9e77bd138cc82eb8baa71b6a86af65426723ff", size = 4880944, upload-time = "2026-03-30T08:47:37.831Z" },
    { url = "https://files.pythonhosted.org/packages/2f/3a/7c3c25789e3f069e581dc342e03613c5b1cb012c4e8c7d9d5cf960a75856/grpcio-1.80.0-cp313-cp313-linux_armv7l.whl", hash = "sha256:e9e408fc016dffd20661f0126c53d8a31c2821b5c13c5d67a0f5ed5de93319ad", size = 6017243, upload-time = "2026-03-30T08:47:40.075Z" },
    { url = "https://files.pythonhosted.org/packages/04/19/21a9806eb8240e174fd1ab0cd5b9aa948bb0e05c2f2f55f9d5d7405e6d08/grpcio-1.80.0-cp313-cp313-macosx_11_0_universal2.whl", hash = "sha256:92d787312e613754d4d8b9ca6d3297e69994a7912a32fa38c4c4e01c272974b0", size = 12010840, upload-time = "2026-03-30T08:47:43.11Z" },
    { url = "https://files.pythonhosted.org/packages/18/3a/23347d35f76f639e807fb7a36fad3068aed100996849a33809591f26eca6/grpcio-1.80.0-cp313-cp313-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:8ac393b58aa16991a2f1144ec578084d544038c12242da3a215966b512904d0f", size = 6567644, upload-time = "2026-03-30T08:47:46.806Z" },
    { url = "https://files.pythonhosted.org/packages/ff/40/96e07ecb604a6a67ae6ab151e3e35b132875d98bc68ec65f3e5ab3e781d7/grpcio-1.80.0-cp313-cp313-manylinux2014_i686.manylinux_2_17_i686.whl", hash = "sha256:68e5851ac4b9afe07e7f84483803ad167852570d65326b34d54ca560bfa53fb6", size = 7277830, upload-time = "2026-03-30T08:47:49.643Z" },
    { url = "https://files.pythonhosted.org/packages/9b/e2/da1506ecea1f34a5e365964644b35edef53803052b763ca214ba3870c856/grpcio-1.80.0-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:873ff5d17d68992ef6605330127425d2fc4e77e612fa3c3e0ed4e668685e3140", size = 6783216, upload-time = "2026-03-30T08:47:52.817Z" },
    { url = "https://files.pythonhosted.org/packages/44/83/3b20ff58d0c3b7f6caaa3af9a4174d4023701df40a3f39f7f1c8e7c48f9d/grpcio-1.80.0-cp313-cp313-musllinux_1_2_aarch64.whl", hash = "sha256:2bea16af2750fd0a899bf1abd9022244418b55d1f37da2202249ba4ba673838d", size = 7385866, upload-time = "2026-03-30T08:47:55.687Z" },
    { url = "https://files.pythonhosted.org/packages/47/45/55c507599c5520416de5eefecc927d6a0d7af55e91cfffb2e410607e5744/grpcio-1.80.0-cp313-cp313-musllinux_1_2_i686.whl", hash = "sha256:ba0db34f7e1d803a878284cd70e4c63cb6ae2510ba51937bf8f45ba997cefcf7", size = 8391602, upload-time = "2026-03-30T08:47:58.303Z" },
    { url = "https://files.pythonhosted.org/packages/10/bb/dd06f4c24c01db9cf11341b547d0a016b2c90ed7dbbb086a5710df7dd1d7/grpcio-1.80.0-cp313-cp313-musllinux_1_2_x86_64.whl", hash = "sha256:8eb613f02d34721f1acf3626dfdb3545bd3c8505b0e52bf8b5710a28d02e8aa7", size = 7826752, upload-time = "2026-03-30T08:48:01.311Z" },
    { url = "https://files.pythonhosted.org/packages/f9/1e/9d67992ba23371fd63d4527096eb8c6b76d74d52b500df992a3343fd7251/grpcio-1.80.0-cp313-cp313-win32.whl", hash = "sha256:93b6f823810720912fd131f561f91f5fed0fda372b6b7028a2681b8194d5d294", size = 4142310, upload-time = "2026-03-30T08:48:04.594Z" },
    { url = "https://files.pythonhosted.org/packages/cf/e6/283326a27da9e2c3038bc93eeea36fb118ce0b2d03922a9cda6688f53c5b/grpcio-1.80.0-cp313-cp313-win_amd64.whl", hash = "sha256:e172cf795a3ba5246d3529e4d34c53db70e888fa582a8ffebd2e6e48bc0cba50", size = 4882833, upload-time = "2026-03-30T08:48:07.363Z" },
    { url = "https://files.pythonhosted.org/packages/c5/6d/e65307ce20f5a09244ba9e9d8476e99fb039de7154f37fb85f26978b59c3/grpcio-1.80.0-cp314-cp314-linux_armv7l.whl", hash = "sha256:3d4147a97c8344d065d01bbf8b6acec2cf86fb0400d40696c8bdad34a64ffc0e", size = 6017376, upload-time = "2026-03-30T08:48:10.005Z" },
    { url = "https://files.pythonhosted.org/packages/69/10/9cef5d9650c72625a699c549940f0abb3c4bfdb5ed45a5ce431f92f31806/grpcio-1.80.0-cp314-cp314-macosx_11_0_universal2.whl", hash = "sha256:d8e11f167935b3eb089ac9038e1a063e6d7dbe995c0bb4a661e614583352e76f", size = 12018133, upload-time = "2026-03-30T08:48:12.927Z" },
    { url = "https://files.pythonhosted.org/packages/04/82/983aabaad82ba26113caceeb9091706a0696b25da004fe3defb5b346e15b/grpcio-1.80.0-cp314-cp314-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:f14b618fc30de822681ee986cfdcc2d9327229dc4c98aed16896761cacd468b9", size = 6574748, upload-time = "2026-03-30T08:48:16.386Z" },
    { url = "https://files.pythonhosted.org/packages/07/d7/031666ef155aa0bf399ed7e19439656c38bbd143779ae0861b038ce82abd/grpcio-1.80.0-cp314-cp314-manylinux2014_i686.manylinux_2_17_i686.whl", hash = "sha256:4ed39fbdcf9b87370f6e8df4e39ca7b38b3e5e9d1b0013c7b6be9639d6578d14", size = 7277711, upload-time = "2026-03-30T08:48:19.627Z" },
    { url = "https://files.pythonhosted.org/packages/e8/43/f437a78f7f4f1d311804189e8f11fb311a01049b2e08557c1068d470cb2e/grpcio-1.80.0-cp314-cp314-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:2dcc70e9f0ba987526e8e8603a610fb4f460e42899e74e7a518bf3c68fe1bf05", size = 6785372, upload-time = "2026-03-30T08:48:22.373Z" },
    { url = "https://files.pythonhosted.org/packages/93/3d/f6558e9c6296cb4227faa5c43c54a34c68d32654b829f53288313d16a86e/grpcio-1.80.0-cp314-cp314-musllinux_1_2_aarch64.whl", hash = "sha256:448c884b668b868562b1bda833c5fce6272d26e1926ec46747cda05741d302c1", size = 7395268, upload-time = "2026-03-30T08:48:25.638Z" },
    { url = "https://files.pythonhosted.org/packages/06/21/0fdd77e84720b08843c371a2efa6f2e19dbebf56adc72df73d891f5506f0/grpcio-1.80.0-cp314-cp314-musllinux_1_2_i686.whl", hash = "sha256:a1dc80fe55685b4a543555e6eef975303b36c8db1023b1599b094b92aa77965f", size = 8392000, upload-time = "2026-03-30T08:48:28.974Z" },
    { url = "https://files.pythonhosted.org/packages/f5/68/67f4947ed55d2e69f2cc199ab9fd85e0a0034d813bbeef84df6d2ba4d4b7/grpcio-1.80.0-cp314-cp314-musllinux_1_2_x86_64.whl", hash = "sha256:31b9ac4ad1aa28ffee5503821fafd09e4da0a261ce1c1281c6c8da0423c83b6e", size = 7828477, upload-time = "2026-03-30T08:48:32.054Z" },
    { url = "https://files.pythonhosted.org/packages/44/b6/8d4096691b2e385e8271911a0de4f35f0a6c7d05aff7098e296c3de86939/grpcio-1.80.0-cp314-cp314-win32.whl", hash = "sha256:367ce30ba67d05e0592470428f0ec1c31714cab9ef19b8f2e37be1f4c7d32fae", size = 4218563, upload-time = "2026-03-30T08:48:34.538Z" },
    { url = "https://files.pythonhosted.org/packages/e5/8c/bbe6baf2557262834f2070cf668515fa308b2d38a4bbf771f8f7872a7036/grpcio-1.80.0-cp314-cp314-win_amd64.whl", hash = "sha256:3b01e1f5464c583d2f567b2e46ff0d516ef979978f72091fd81f5ab7fa6e2e7f", size = 5019457, upload-time = "2026-03-30T08:48:37.308Z" },
]

[[package]]
name = "h11"
version = "0.16.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/01/ee/02a2c011bdab74c6fb3c75474d40b3052059d95df7e73351460c8588d963/h11-0.16.0.tar.gz", hash = "sha256:4e35b956cf45792e4caa5885e69fba00bdbc6ffafbfa020300e549b208ee5ff1", size = 101250, upload-time = "2025-04-24T03:35:25.427Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/04/4b/29cac41a4d98d144bf5f6d33995617b185d14b22401f75ca86f384e87ff1/h11-0.16.0-py3-none-any.whl", hash = "sha256:63cf8bbe7522de3bf65932fda1d9c2772064ffb3dae62d55932da54b31cb6c86", size = 37515, upload-time = "2025-04-24T03:35:24.344Z" },
]

[[package]]
name = "hf-xet"
version = "1.4.3"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/53/92/ec9ad04d0b5728dca387a45af7bc98fbb0d73b2118759f5f6038b61a57e8/hf_xet-1.4.3.tar.gz", hash = "sha256:8ddedb73c8c08928c793df2f3401ec26f95be7f7e516a7bee2fbb546f6676113", size = 670477, upload-time = "2026-03-31T22:40:07.874Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/72/43/724d307b34e353da0abd476e02f72f735cdd2bc86082dee1b32ea0bfee1d/hf_xet-1.4.3-cp313-cp313t-macosx_10_12_x86_64.whl", hash = "sha256:7551659ba4f1e1074e9623996f28c3873682530aee0a846b7f2f066239228144", size = 3800935, upload-time = "2026-03-31T22:39:49.618Z" },
    { url = "https://files.pythonhosted.org/packages/2b/d2/8bee5996b699262edb87dbb54118d287c0e1b2fc78af7cdc41857ba5e3c4/hf_xet-1.4.3-cp313-cp313t-macosx_11_0_arm64.whl", hash = "sha256:bee693ada985e7045997f05f081d0e12c4c08bd7626dc397f8a7c487e6c04f7f", size = 3558942, upload-time = "2026-03-31T22:39:47.938Z" },
    { url = "https://files.pythonhosted.org/packages/c3/a1/e993d09cbe251196fb60812b09a58901c468127b7259d2bf0f68bf6088eb/hf_xet-1.4.3-cp313-cp313t-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:21644b404bb0100fe3857892f752c4d09642586fd988e61501c95bbf44b393a3", size = 4207657, upload-time = "2026-03-31T22:39:39.69Z" },
    { url = "https://files.pythonhosted.org/packages/64/44/9eb6d21e5c34c63e5e399803a6932fa983cabdf47c0ecbcfe7ea97684b8c/hf_xet-1.4.3-cp313-cp313t-manylinux_2_28_aarch64.whl", hash = "sha256:987f09cfe418237812896a6736b81b1af02a3a6dcb4b4944425c4c4fca7a7cf8", size = 3986765, upload-time = "2026-03-31T22:39:37.936Z" },
    { url = "https://files.pythonhosted.org/packages/ea/7b/8ad6f16fdb82f5f7284a34b5ec48645bd575bdcd2f6f0d1644775909c486/hf_xet-1.4.3-cp313-cp313t-musllinux_1_2_aarch64.whl", hash = "sha256:60cf7fc43a99da0a853345cf86d23738c03983ee5249613a6305d3e57a5dca74", size = 4188162, upload-time = "2026-03-31T22:39:58.382Z" },
    { url = "https://files.pythonhosted.org/packages/1b/c4/39d6e136cbeea9ca5a23aad4b33024319222adbdc059ebcda5fc7d9d5ff4/hf_xet-1.4.3-cp313-cp313t-musllinux_1_2_x86_64.whl", hash = "sha256:2815a49a7a59f3e2edf0cf113ae88e8cb2ca2a221bf353fb60c609584f4884d4", size = 4424525, upload-time = "2026-03-31T22:40:00.225Z" },
    { url = "https://files.pythonhosted.org/packages/46/f2/adc32dae6bdbc367853118b9878139ac869419a4ae7ba07185dc31251b76/hf_xet-1.4.3-cp313-cp313t-win_amd64.whl", hash = "sha256:42ee323265f1e6a81b0e11094564fb7f7e0ec75b5105ffd91ae63f403a11931b", size = 3671610, upload-time = "2026-03-31T22:40:10.42Z" },
    { url = "https://files.pythonhosted.org/packages/e2/19/25d897dcc3f81953e0c2cde9ec186c7a0fee413eb0c9a7a9130d87d94d3a/hf_xet-1.4.3-cp313-cp313t-win_arm64.whl", hash = "sha256:27c976ba60079fb8217f485b9c5c7fcd21c90b0367753805f87cb9f3cdc4418a", size = 3528529, upload-time = "2026-03-31T22:40:09.106Z" },
    { url = "https://files.pythonhosted.org/packages/ec/36/3e8f85ca9fe09b8de2b2e10c63b3b3353d7dda88a0b3d426dffbe7b8313b/hf_xet-1.4.3-cp314-cp314t-macosx_10_12_x86_64.whl", hash = "sha256:5251d5ece3a81815bae9abab41cf7ddb7bcb8f56411bce0827f4a3071c92fdc6", size = 3801019, upload-time = "2026-03-31T22:39:56.651Z" },
    { url = "https://files.pythonhosted.org/packages/b5/9c/defb6cb1de28bccb7bd8d95f6e60f72a3d3fa4cb3d0329c26fb9a488bfe7/hf_xet-1.4.3-cp314-cp314t-macosx_11_0_arm64.whl", hash = "sha256:1feb0f3abeacee143367c326a128a2e2b60868ec12a36c225afb1d6c5a05e6d2", size = 3558746, upload-time = "2026-03-31T22:39:54.766Z" },
    { url = "https://files.pythonhosted.org/packages/c1/bd/8d001191893178ff8e826e46ad5299446e62b93cd164e17b0ffea08832ec/hf_xet-1.4.3-cp314-cp314t-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:8b301fc150290ca90b4fccd079829b84bb4786747584ae08b94b4577d82fb791", size = 4207692, upload-time = "2026-03-31T22:39:46.246Z" },
    { url = "https://files.pythonhosted.org/packages/ce/48/6790b402803250e9936435613d3a78b9aaeee7973439f0918848dde58309/hf_xet-1.4.3-cp314-cp314t-manylinux_2_28_aarch64.whl", hash = "sha256:d972fbe95ddc0d3c0fc49b31a8a69f47db35c1e3699bf316421705741aab6653", size = 3986281, upload-time = "2026-03-31T22:39:44.648Z" },
    { url = "https://files.pythonhosted.org/packages/51/56/ea62552fe53db652a9099eda600b032d75554d0e86c12a73824bfedef88b/hf_xet-1.4.3-cp314-cp314t-musllinux_1_2_aarch64.whl", hash = "sha256:c5b48db1ee344a805a1b9bd2cda9b6b65fe77ed3787bd6e87ad5521141d317cd", size = 4187414, upload-time = "2026-03-31T22:40:04.951Z" },
    { url = "https://files.pythonhosted.org/packages/7d/f5/bc1456d4638061bea997e6d2db60a1a613d7b200e0755965ec312dc1ef79/hf_xet-1.4.3-cp314-cp314t-musllinux_1_2_x86_64.whl", hash = "sha256:22bdc1f5fb8b15bf2831440b91d1c9bbceeb7e10c81a12e8d75889996a5c9da8", size = 4424368, upload-time = "2026-03-31T22:40:06.347Z" },
    { url = "https://files.pythonhosted.org/packages/e4/76/ab597bae87e1f06d18d3ecb8ed7f0d3c9a37037fc32ce76233d369273c64/hf_xet-1.4.3-cp314-cp314t-win_amd64.whl", hash = "sha256:0392c79b7cf48418cd61478c1a925246cf10639f4cd9d94368d8ca1e8df9ea07", size = 3672280, upload-time = "2026-03-31T22:40:16.401Z" },
    { url = "https://files.pythonhosted.org/packages/62/05/2e462d34e23a09a74d73785dbed71cc5dbad82a72eee2ad60a72a554155d/hf_xet-1.4.3-cp314-cp314t-win_arm64.whl", hash = "sha256:681c92a07796325778a79d76c67011764ecc9042a8c3579332b61b63ae512075", size = 3528945, upload-time = "2026-03-31T22:40:14.995Z" },
    { url = "https://files.pythonhosted.org/packages/ac/9f/9c23e4a447b8f83120798f9279d0297a4d1360bdbf59ef49ebec78fe2545/hf_xet-1.4.3-cp37-abi3-macosx_10_12_x86_64.whl", hash = "sha256:d0da85329eaf196e03e90b84c2d0aca53bd4573d097a75f99609e80775f98025", size = 3805048, upload-time = "2026-03-31T22:39:53.105Z" },
    { url = "https://files.pythonhosted.org/packages/0b/f8/7aacb8e5f4a7899d39c787b5984e912e6c18b11be136ef13947d7a66d265/hf_xet-1.4.3-cp37-abi3-macosx_11_0_arm64.whl", hash = "sha256:e23717ce4186b265f69afa66e6f0069fe7efbf331546f5c313d00e123dc84583", size = 3562178, upload-time = "2026-03-31T22:39:51.295Z" },
    { url = "https://files.pythonhosted.org/packages/df/9a/a24b26dc8a65f0ecc0fe5be981a19e61e7ca963b85e062c083f3a9100529/hf_xet-1.4.3-cp37-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:fc360b70c815bf340ed56c7b8c63aacf11762a4b099b2fe2c9bd6d6068668c08", size = 4212320, upload-time = "2026-03-31T22:39:42.922Z" },
    { url = "https://files.pythonhosted.org/packages/53/60/46d493db155d2ee2801b71fb1b0fd67696359047fdd8caee2c914cc50c79/hf_xet-1.4.3-cp37-abi3-manylinux_2_28_aarch64.whl", hash = "sha256:39f2d2e9654cd9b4319885733993807aab6de9dfbd34c42f0b78338d6617421f", size = 3991546, upload-time = "2026-03-31T22:39:41.335Z" },
    { url = "https://files.pythonhosted.org/packages/bc/f5/067363e1c96c6b17256910830d1b54099d06287e10f4ec6ec4e7e08371fc/hf_xet-1.4.3-cp37-abi3-musllinux_1_2_aarch64.whl", hash = "sha256:49ad8a8cead2b56051aa84d7fce3e1335efe68df3cf6c058f22a65513885baac", size = 4193200, upload-time = "2026-03-31T22:40:01.936Z" },
    { url = "https://files.pythonhosted.org/packages/42/4b/53951592882d9c23080c7644542fda34a3813104e9e11fa1a7d82d419cb8/hf_xet-1.4.3-cp37-abi3-musllinux_1_2_x86_64.whl", hash = "sha256:7716d62015477a70ea272d2d68cd7cad140f61c52ee452e133e139abfe2c17ba", size = 4429392, upload-time = "2026-03-31T22:40:03.492Z" },
    { url = "https://files.pythonhosted.org/packages/8a/21/75a6c175b4e79662ad8e62f46a40ce341d8d6b206b06b4320d07d55b188c/hf_xet-1.4.3-cp37-abi3-win_amd64.whl", hash = "sha256:6b591fcad34e272a5b02607485e4f2a1334aebf1bc6d16ce8eb1eb8978ac2021", size = 3677359, upload-time = "2026-03-31T22:40:13.619Z" },
    { url = "https://files.pythonhosted.org/packages/8a/7c/44314ecd0e89f8b2b51c9d9e5e7a60a9c1c82024ac471d415860557d3cd8/hf_xet-1.4.3-cp37-abi3-win_arm64.whl", hash = "sha256:7c2c7e20bcfcc946dc67187c203463f5e932e395845d098cc2a93f5b67ca0b47", size = 3533664, upload-time = "2026-03-31T22:40:12.152Z" },
]

[[package]]
name = "httpcore"
version = "1.0.9"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "certifi" },
    { name = "h11" },
]
sdist = { url = "https://files.pythonhosted.org/packages/06/94/82699a10bca87a5556c9c59b5963f2d039dbd239f25bc2a63907a05a14cb/httpcore-1.0.9.tar.gz", hash = "sha256:6e34463af53fd2ab5d807f399a9b45ea31c3dfa2276f15a2c3f00afff6e176e8", size = 85484, upload-time = "2025-04-24T22:06:22.219Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/7e/f5/f66802a942d491edb555dd61e3a9961140fd64c90bce1eafd741609d334d/httpcore-1.0.9-py3-none-any.whl", hash = "sha256:2d400746a40668fc9dec9810239072b40b4484b640a8c38fd654a024c7a1bf55", size = 78784, upload-time = "2025-04-24T22:06:20.566Z" },
]

[[package]]
name = "httptools"
version = "0.7.1"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/b5/46/120a669232c7bdedb9d52d4aeae7e6c7dfe151e99dc70802e2fc7a5e1993/httptools-0.7.1.tar.gz", hash = "sha256:abd72556974f8e7c74a259655924a717a2365b236c882c3f6f8a45fe94703ac9", size = 258961, upload-time = "2025-10-10T03:55:08.559Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/9c/08/17e07e8d89ab8f343c134616d72eebfe03798835058e2ab579dcc8353c06/httptools-0.7.1-cp311-cp311-macosx_10_9_universal2.whl", hash = "sha256:474d3b7ab469fefcca3697a10d11a32ee2b9573250206ba1e50d5980910da657", size = 206521, upload-time = "2025-10-10T03:54:31.002Z" },
    { url = "https://files.pythonhosted.org/packages/aa/06/c9c1b41ff52f16aee526fd10fbda99fa4787938aa776858ddc4a1ea825ec/httptools-0.7.1-cp311-cp311-macosx_11_0_arm64.whl", hash = "sha256:a3c3b7366bb6c7b96bd72d0dbe7f7d5eead261361f013be5f6d9590465ea1c70", size = 110375, upload-time = "2025-10-10T03:54:31.941Z" },
    { url = "https://files.pythonhosted.org/packages/cc/cc/10935db22fda0ee34c76f047590ca0a8bd9de531406a3ccb10a90e12ea21/httptools-0.7.1-cp311-cp311-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:379b479408b8747f47f3b253326183d7c009a3936518cdb70db58cffd369d9df", size = 456621, upload-time = "2025-10-10T03:54:33.176Z" },
    { url = "https://files.pythonhosted.org/packages/0e/84/875382b10d271b0c11aa5d414b44f92f8dd53e9b658aec338a79164fa548/httptools-0.7.1-cp311-cp311-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:cad6b591a682dcc6cf1397c3900527f9affef1e55a06c4547264796bbd17cf5e", size = 454954, upload-time = "2025-10-10T03:54:34.226Z" },
    { url = "https://files.pythonhosted.org/packages/30/e1/44f89b280f7e46c0b1b2ccee5737d46b3bb13136383958f20b580a821ca0/httptools-0.7.1-cp311-cp311-musllinux_1_2_aarch64.whl", hash = "sha256:eb844698d11433d2139bbeeb56499102143beb582bd6c194e3ba69c22f25c274", size = 440175, upload-time = "2025-10-10T03:54:35.942Z" },
    { url = "https://files.pythonhosted.org/packages/6f/7e/b9287763159e700e335028bc1824359dc736fa9b829dacedace91a39b37e/httptools-0.7.1-cp311-cp311-musllinux_1_2_x86_64.whl", hash = "sha256:f65744d7a8bdb4bda5e1fa23e4ba16832860606fcc09d674d56e425e991539ec", size = 440310, upload-time = "2025-10-10T03:54:37.1Z" },
    { url = "https://files.pythonhosted.org/packages/b3/07/5b614f592868e07f5c94b1f301b5e14a21df4e8076215a3bccb830a687d8/httptools-0.7.1-cp311-cp311-win_amd64.whl", hash = "sha256:135fbe974b3718eada677229312e97f3b31f8a9c8ffa3ae6f565bf808d5b6bcb", size = 86875, upload-time = "2025-10-10T03:54:38.421Z" },
    { url = "https://files.pythonhosted.org/packages/53/7f/403e5d787dc4942316e515e949b0c8a013d84078a915910e9f391ba9b3ed/httptools-0.7.1-cp312-cp312-macosx_10_13_universal2.whl", hash = "sha256:38e0c83a2ea9746ebbd643bdfb521b9aa4a91703e2cd705c20443405d2fd16a5", size = 206280, upload-time = "2025-10-10T03:54:39.274Z" },
    { url = "https://files.pythonhosted.org/packages/2a/0d/7f3fd28e2ce311ccc998c388dd1c53b18120fda3b70ebb022b135dc9839b/httptools-0.7.1-cp312-cp312-macosx_11_0_arm64.whl", hash = "sha256:f25bbaf1235e27704f1a7b86cd3304eabc04f569c828101d94a0e605ef7205a5", size = 110004, upload-time = "2025-10-10T03:54:40.403Z" },
    { url = "https://files.pythonhosted.org/packages/84/a6/b3965e1e146ef5762870bbe76117876ceba51a201e18cc31f5703e454596/httptools-0.7.1-cp312-cp312-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:2c15f37ef679ab9ecc06bfc4e6e8628c32a8e4b305459de7cf6785acd57e4d03", size = 517655, upload-time = "2025-10-10T03:54:41.347Z" },
    { url = "https://files.pythonhosted.org/packages/11/7d/71fee6f1844e6fa378f2eddde6c3e41ce3a1fb4b2d81118dd544e3441ec0/httptools-0.7.1-cp312-cp312-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:7fe6e96090df46b36ccfaf746f03034e5ab723162bc51b0a4cf58305324036f2", size = 511440, upload-time = "2025-10-10T03:54:42.452Z" },
    { url = "https://files.pythonhosted.org/packages/22/a5/079d216712a4f3ffa24af4a0381b108aa9c45b7a5cc6eb141f81726b1823/httptools-0.7.1-cp312-cp312-musllinux_1_2_aarch64.whl", hash = "sha256:f72fdbae2dbc6e68b8239defb48e6a5937b12218e6ffc2c7846cc37befa84362", size = 495186, upload-time = "2025-10-10T03:54:43.937Z" },
    { url = "https://files.pythonhosted.org/packages/e9/9e/025ad7b65278745dee3bd0ebf9314934c4592560878308a6121f7f812084/httptools-0.7.1-cp312-cp312-musllinux_1_2_x86_64.whl", hash = "sha256:e99c7b90a29fd82fea9ef57943d501a16f3404d7b9ee81799d41639bdaae412c", size = 499192, upload-time = "2025-10-10T03:54:45.003Z" },
    { url = "https://files.pythonhosted.org/packages/6d/de/40a8f202b987d43afc4d54689600ff03ce65680ede2f31df348d7f368b8f/httptools-0.7.1-cp312-cp312-win_amd64.whl", hash = "sha256:3e14f530fefa7499334a79b0cf7e7cd2992870eb893526fb097d51b4f2d0f321", size = 86694, upload-time = "2025-10-10T03:54:45.923Z" },
    { url = "https://files.pythonhosted.org/packages/09/8f/c77b1fcbfd262d422f12da02feb0d218fa228d52485b77b953832105bb90/httptools-0.7.1-cp313-cp313-macosx_10_13_universal2.whl", hash = "sha256:6babce6cfa2a99545c60bfef8bee0cc0545413cb0018f617c8059a30ad985de3", size = 202889, upload-time = "2025-10-10T03:54:47.089Z" },
    { url = "https://files.pythonhosted.org/packages/0a/1a/22887f53602feaa066354867bc49a68fc295c2293433177ee90870a7d517/httptools-0.7.1-cp313-cp313-macosx_11_0_arm64.whl", hash = "sha256:601b7628de7504077dd3dcb3791c6b8694bbd967148a6d1f01806509254fb1ca", size = 108180, upload-time = "2025-10-10T03:54:48.052Z" },
    { url = "https://files.pythonhosted.org/packages/32/6a/6aaa91937f0010d288d3d124ca2946d48d60c3a5ee7ca62afe870e3ea011/httptools-0.7.1-cp313-cp313-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:04c6c0e6c5fb0739c5b8a9eb046d298650a0ff38cf42537fc372b28dc7e4472c", size = 478596, upload-time = "2025-10-10T03:54:48.919Z" },
    { url = "https://files.pythonhosted.org/packages/6d/70/023d7ce117993107be88d2cbca566a7c1323ccbaf0af7eabf2064fe356f6/httptools-0.7.1-cp313-cp313-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:69d4f9705c405ae3ee83d6a12283dc9feba8cc6aaec671b412917e644ab4fa66", size = 473268, upload-time = "2025-10-10T03:54:49.993Z" },
    { url = "https://files.pythonhosted.org/packages/32/4d/9dd616c38da088e3f436e9a616e1d0cc66544b8cdac405cc4e81c8679fc7/httptools-0.7.1-cp313-cp313-musllinux_1_2_aarch64.whl", hash = "sha256:44c8f4347d4b31269c8a9205d8a5ee2df5322b09bbbd30f8f862185bb6b05346", size = 455517, upload-time = "2025-10-10T03:54:51.066Z" },
    { url = "https://files.pythonhosted.org/packages/1d/3a/a6c595c310b7df958e739aae88724e24f9246a514d909547778d776799be/httptools-0.7.1-cp313-cp313-musllinux_1_2_x86_64.whl", hash = "sha256:465275d76db4d554918aba40bf1cbebe324670f3dfc979eaffaa5d108e2ed650", size = 458337, upload-time = "2025-10-10T03:54:52.196Z" },
    { url = "https://files.pythonhosted.org/packages/fd/82/88e8d6d2c51edc1cc391b6e044c6c435b6aebe97b1abc33db1b0b24cd582/httptools-0.7.1-cp313-cp313-win_amd64.whl", hash = "sha256:322d00c2068d125bd570f7bf78b2d367dad02b919d8581d7476d8b75b294e3e6", size = 85743, upload-time = "2025-10-10T03:54:53.448Z" },
    { url = "https://files.pythonhosted.org/packages/34/50/9d095fcbb6de2d523e027a2f304d4551855c2f46e0b82befd718b8b20056/httptools-0.7.1-cp314-cp314-macosx_10_13_universal2.whl", hash = "sha256:c08fe65728b8d70b6923ce31e3956f859d5e1e8548e6f22ec520a962c6757270", size = 203619, upload-time = "2025-10-10T03:54:54.321Z" },
    { url = "https://files.pythonhosted.org/packages/07/f0/89720dc5139ae54b03f861b5e2c55a37dba9a5da7d51e1e824a1f343627f/httptools-0.7.1-cp314-cp314-macosx_11_0_arm64.whl", hash = "sha256:7aea2e3c3953521c3c51106ee11487a910d45586e351202474d45472db7d72d3", size = 108714, upload-time = "2025-10-10T03:54:55.163Z" },
    { url = "https://files.pythonhosted.org/packages/b3/cb/eea88506f191fb552c11787c23f9a405f4c7b0c5799bf73f2249cd4f5228/httptools-0.7.1-cp314-cp314-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:0e68b8582f4ea9166be62926077a3334064d422cf08ab87d8b74664f8e9058e1", size = 472909, upload-time = "2025-10-10T03:54:56.056Z" },
    { url = "https://files.pythonhosted.org/packages/e0/4a/a548bdfae6369c0d078bab5769f7b66f17f1bfaa6fa28f81d6be6959066b/httptools-0.7.1-cp314-cp314-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:df091cf961a3be783d6aebae963cc9b71e00d57fa6f149025075217bc6a55a7b", size = 470831, upload-time = "2025-10-10T03:54:57.219Z" },
    { url = "https://files.pythonhosted.org/packages/4d/31/14df99e1c43bd132eec921c2e7e11cda7852f65619bc0fc5bdc2d0cb126c/httptools-0.7.1-cp314-cp314-musllinux_1_2_aarch64.whl", hash = "sha256:f084813239e1eb403ddacd06a30de3d3e09a9b76e7894dcda2b22f8a726e9c60", size = 452631, upload-time = "2025-10-10T03:54:58.219Z" },
    { url = "https://files.pythonhosted.org/packages/22/d2/b7e131f7be8d854d48cb6d048113c30f9a46dca0c9a8b08fcb3fcd588cdc/httptools-0.7.1-cp314-cp314-musllinux_1_2_x86_64.whl", hash = "sha256:7347714368fb2b335e9063bc2b96f2f87a9ceffcd9758ac295f8bbcd3ffbc0ca", size = 452910, upload-time = "2025-10-10T03:54:59.366Z" },
    { url = "https://files.pythonhosted.org/packages/53/cf/878f3b91e4e6e011eff6d1fa9ca39f7eb17d19c9d7971b04873734112f30/httptools-0.7.1-cp314-cp314-win_amd64.whl", hash = "sha256:cfabda2a5bb85aa2a904ce06d974a3f30fb36cc63d7feaddec05d2050acede96", size = 88205, upload-time = "2025-10-10T03:55:00.389Z" },
]

[[package]]
name = "httpx"
version = "0.28.1"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "anyio" },
    { name = "certifi" },
    { name = "httpcore" },
    { name = "idna" },
]
sdist = { url = "https://files.pythonhosted.org/packages/b1/df/48c586a5fe32a0f01324ee087459e112ebb7224f646c0b5023f5e79e9956/httpx-0.28.1.tar.gz", hash = "sha256:75e98c5f16b0f35b567856f597f06ff2270a374470a5c2392242528e3e3e42fc", size = 141406, upload-time = "2024-12-06T15:37:23.222Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/2a/39/e50c7c3a983047577ee07d2a9e53faf5a69493943ec3f6a384bdc792deb2/httpx-0.28.1-py3-none-any.whl", hash = "sha256:d909fcccc110f8c7faf814ca82a9a4d816bc5a6dbfea25d6591d6985b8ba59ad", size = 73517, upload-time = "2024-12-06T15:37:21.509Z" },
]

[[package]]
name = "huggingface-hub"
version = "1.8.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "filelock" },
    { name = "fsspec" },
    { name = "hf-xet", marker = "platform_machine == 'AMD64' or platform_machine == 'aarch64' or platform_machine == 'amd64' or platform_machine == 'arm64' or platform_machine == 'x86_64'" },
    { name = "httpx" },
    { name = "packaging" },
    { name = "pyyaml" },
    { name = "tqdm" },
    { name = "typer" },
    { name = "typing-extensions" },
]
sdist = { url = "https://files.pythonhosted.org/packages/8e/2a/a847fd02261cd051da218baf99f90ee7c7040c109a01833db4f838f25256/huggingface_hub-1.8.0.tar.gz", hash = "sha256:c5627b2fd521e00caf8eff4ac965ba988ea75167fad7ee72e17f9b7183ec63f3", size = 735839, upload-time = "2026-03-25T16:01:28.152Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/a9/ae/8a3a16ea4d202cb641b51d2681bdd3d482c1c592d7570b3fa264730829ce/huggingface_hub-1.8.0-py3-none-any.whl", hash = "sha256:d3eb5047bd4e33c987429de6020d4810d38a5bef95b3b40df9b17346b7f353f2", size = 625208, upload-time = "2026-03-25T16:01:26.603Z" },
]

[[package]]
name = "idna"
version = "3.11"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/6f/6d/0703ccc57f3a7233505399edb88de3cbd678da106337b9fcde432b65ed60/idna-3.11.tar.gz", hash = "sha256:795dafcc9c04ed0c1fb032c2aa73654d8e8c5023a7df64a53f39190ada629902", size = 194582, upload-time = "2025-10-12T14:55:20.501Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/0e/61/66938bbb5fc52dbdf84594873d5b51fb1f7c7794e9c0f5bd885f30bc507b/idna-3.11-py3-none-any.whl", hash = "sha256:771a87f49d9defaf64091e6e6fe9c18d4833f140bd19464795bc32d966ca37ea", size = 71008, upload-time = "2025-10-12T14:55:18.883Z" },
]

[[package]]
name = "importlib-metadata"
version = "8.7.1"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "zipp" },
]
sdist = { url = "https://files.pythonhosted.org/packages/f3/49/3b30cad09e7771a4982d9975a8cbf64f00d4a1ececb53297f1d9a7be1b10/importlib_metadata-8.7.1.tar.gz", hash = "sha256:49fef1ae6440c182052f407c8d34a68f72efc36db9ca90dc0113398f2fdde8bb", size = 57107, upload-time = "2025-12-21T10:00:19.278Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/fa/5e/f8e9a1d23b9c20a551a8a02ea3637b4642e22c2626e3a13a9a29cdea99eb/importlib_metadata-8.7.1-py3-none-any.whl", hash = "sha256:5a1f80bf1daa489495071efbb095d75a634cf28a8bc299581244063b53176151", size = 27865, upload-time = "2025-12-21T10:00:18.329Z" },
]

[[package]]
name = "importlib-resources"
version = "6.5.2"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/cf/8c/f834fbf984f691b4f7ff60f50b514cc3de5cc08abfc3295564dd89c5e2e7/importlib_resources-6.5.2.tar.gz", hash = "sha256:185f87adef5bcc288449d98fb4fba07cea78bc036455dd44c5fc4a2fe78fed2c", size = 44693, upload-time = "2025-01-03T18:51:56.698Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/a4/ed/1f1afb2e9e7f38a545d628f864d562a5ae64fe6f7a10e28ffb9b185b4e89/importlib_resources-6.5.2-py3-none-any.whl", hash = "sha256:789cfdc3ed28c78b67a06acb8126751ced69a3d5f79c095a98298cd8a760ccec", size = 37461, upload-time = "2025-01-03T18:51:54.306Z" },
]

[[package]]
name = "iniconfig"
version = "2.3.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/72/34/14ca021ce8e5dfedc35312d08ba8bf51fdd999c576889fc2c24cb97f4f10/iniconfig-2.3.0.tar.gz", hash = "sha256:c76315c77db068650d49c5b56314774a7804df16fee4402c1f19d6d15d8c4730", size = 20503, upload-time = "2025-10-18T21:55:43.219Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/cb/b1/3846dd7f199d53cb17f49cba7e651e9ce294d8497c8c150530ed11865bb8/iniconfig-2.3.0-py3-none-any.whl", hash = "sha256:f631c04d2c48c52b84d0d0549c99ff3859c98df65b3101406327ecc7d53fbf12", size = 7484, upload-time = "2025-10-18T21:55:41.639Z" },
]

[[package]]
name = "jsonschema"
version = "4.26.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "attrs" },
    { name = "jsonschema-specifications" },
    { name = "referencing" },
    { name = "rpds-py" },
]
sdist = { url = "https://files.pythonhosted.org/packages/b3/fc/e067678238fa451312d4c62bf6e6cf5ec56375422aee02f9cb5f909b3047/jsonschema-4.26.0.tar.gz", hash = "sha256:0c26707e2efad8aa1bfc5b7ce170f3fccc2e4918ff85989ba9ffa9facb2be326", size = 366583, upload-time = "2026-01-07T13:41:07.246Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/69/90/f63fb5873511e014207a475e2bb4e8b2e570d655b00ac19a9a0ca0a385ee/jsonschema-4.26.0-py3-none-any.whl", hash = "sha256:d489f15263b8d200f8387e64b4c3a75f06629559fb73deb8fdfb525f2dab50ce", size = 90630, upload-time = "2026-01-07T13:41:05.306Z" },
]

[[package]]
name = "jsonschema-specifications"
version = "2025.9.1"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "referencing" },
]
sdist = { url = "https://files.pythonhosted.org/packages/19/74/a633ee74eb36c44aa6d1095e7cc5569bebf04342ee146178e2d36600708b/jsonschema_specifications-2025.9.1.tar.gz", hash = "sha256:b540987f239e745613c7a9176f3edb72b832a4ac465cf02712288397832b5e8d", size = 32855, upload-time = "2025-09-08T01:34:59.186Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/41/45/1a4ed80516f02155c51f51e8cedb3c1902296743db0bbc66608a0db2814f/jsonschema_specifications-2025.9.1-py3-none-any.whl", hash = "sha256:98802fee3a11ee76ecaca44429fda8a41bff98b00a0f2838151b113f210cc6fe", size = 18437, upload-time = "2025-09-08T01:34:57.871Z" },
]

[[package]]
name = "kubernetes"
version = "35.0.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "certifi" },
    { name = "durationpy" },
    { name = "python-dateutil" },
    { name = "pyyaml" },
    { name = "requests" },
    { name = "requests-oauthlib" },
    { name = "six" },
    { name = "urllib3" },
    { name = "websocket-client" },
]
sdist = { url = "https://files.pythonhosted.org/packages/2c/8f/85bf51ad4150f64e8c665daf0d9dfe9787ae92005efb9a4d1cba592bd79d/kubernetes-35.0.0.tar.gz", hash = "sha256:3d00d344944239821458b9efd484d6df9f011da367ecb155dadf9513f05f09ee", size = 1094642, upload-time = "2026-01-16T01:05:27.76Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/0c/70/05b685ea2dffcb2adbf3cdcea5d8865b7bc66f67249084cf845012a0ff13/kubernetes-35.0.0-py2.py3-none-any.whl", hash = "sha256:39e2b33b46e5834ef6c3985ebfe2047ab39135d41de51ce7641a7ca5b372a13d", size = 2017602, upload-time = "2026-01-16T01:05:25.991Z" },
]

[[package]]
name = "lark-oapi"
version = "1.5.3"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "httpx" },
    { name = "pycryptodome" },
    { name = "requests" },
    { name = "requests-toolbelt" },
    { name = "websockets" },
]
wheels = [
    { url = "https://files.pythonhosted.org/packages/bf/ff/2ece5d735ebfa2af600a53176f2636ae47af2bf934e08effab64f0d1e047/lark_oapi-1.5.3-py3-none-any.whl", hash = "sha256:fda6b32bb38d21b6bdaae94979c600b94c7c521e985adade63a54e4b3e20cc36", size = 6993016, upload-time = "2026-01-27T08:21:49.307Z" },
]

[[package]]
name = "lxml"
version = "6.0.2"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/aa/88/262177de60548e5a2bfc46ad28232c9e9cbde697bd94132aeb80364675cb/lxml-6.0.2.tar.gz", hash = "sha256:cd79f3367bd74b317dda655dc8fcfa304d9eb6e4fb06b7168c5cf27f96e0cd62", size = 4073426, upload-time = "2025-09-22T04:04:59.287Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/77/d5/becbe1e2569b474a23f0c672ead8a29ac50b2dc1d5b9de184831bda8d14c/lxml-6.0.2-cp311-cp311-macosx_10_9_universal2.whl", hash = "sha256:13e35cbc684aadf05d8711a5d1b5857c92e5e580efa9a0d2be197199c8def607", size = 8634365, upload-time = "2025-09-22T04:00:45.672Z" },
    { url = "https://files.pythonhosted.org/packages/28/66/1ced58f12e804644426b85d0bb8a4478ca77bc1761455da310505f1a3526/lxml-6.0.2-cp311-cp311-macosx_10_9_x86_64.whl", hash = "sha256:3b1675e096e17c6fe9c0e8c81434f5736c0739ff9ac6123c87c2d452f48fc938", size = 4650793, upload-time = "2025-09-22T04:00:47.783Z" },
    { url = "https://files.pythonhosted.org/packages/11/84/549098ffea39dfd167e3f174b4ce983d0eed61f9d8d25b7bf2a57c3247fc/lxml-6.0.2-cp311-cp311-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:8ac6e5811ae2870953390452e3476694196f98d447573234592d30488147404d", size = 4944362, upload-time = "2025-09-22T04:00:49.845Z" },
    { url = "https://files.pythonhosted.org/packages/ac/bd/f207f16abf9749d2037453d56b643a7471d8fde855a231a12d1e095c4f01/lxml-6.0.2-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:5aa0fc67ae19d7a64c3fe725dc9a1bb11f80e01f78289d05c6f62545affec438", size = 5083152, upload-time = "2025-09-22T04:00:51.709Z" },
    { url = "https://files.pythonhosted.org/packages/15/ae/bd813e87d8941d52ad5b65071b1affb48da01c4ed3c9c99e40abb266fbff/lxml-6.0.2-cp311-cp311-manylinux_2_26_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:de496365750cc472b4e7902a485d3f152ecf57bd3ba03ddd5578ed8ceb4c5964", size = 5023539, upload-time = "2025-09-22T04:00:53.593Z" },
    { url = "https://files.pythonhosted.org/packages/02/cd/9bfef16bd1d874fbe0cb51afb00329540f30a3283beb9f0780adbb7eec03/lxml-6.0.2-cp311-cp311-manylinux_2_26_i686.manylinux_2_28_i686.whl", hash = "sha256:200069a593c5e40b8f6fc0d84d86d970ba43138c3e68619ffa234bc9bb806a4d", size = 5344853, upload-time = "2025-09-22T04:00:55.524Z" },
    { url = "https://files.pythonhosted.org/packages/b8/89/ea8f91594bc5dbb879734d35a6f2b0ad50605d7fb419de2b63d4211765cc/lxml-6.0.2-cp311-cp311-manylinux_2_26_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:7d2de809c2ee3b888b59f995625385f74629707c9355e0ff856445cdcae682b7", size = 5225133, upload-time = "2025-09-22T04:00:57.269Z" },
    { url = "https://files.pythonhosted.org/packages/b9/37/9c735274f5dbec726b2db99b98a43950395ba3d4a1043083dba2ad814170/lxml-6.0.2-cp311-cp311-manylinux_2_31_armv7l.whl", hash = "sha256:b2c3da8d93cf5db60e8858c17684c47d01fee6405e554fb55018dd85fc23b178", size = 4677944, upload-time = "2025-09-22T04:00:59.052Z" },
    { url = "https://files.pythonhosted.org/packages/20/28/7dfe1ba3475d8bfca3878365075abe002e05d40dfaaeb7ec01b4c587d533/lxml-6.0.2-cp311-cp311-manylinux_2_38_riscv64.manylinux_2_39_riscv64.whl", hash = "sha256:442de7530296ef5e188373a1ea5789a46ce90c4847e597856570439621d9c553", size = 5284535, upload-time = "2025-09-22T04:01:01.335Z" },
    { url = "https://files.pythonhosted.org/packages/e7/cf/5f14bc0de763498fc29510e3532bf2b4b3a1c1d5d0dff2e900c16ba021ef/lxml-6.0.2-cp311-cp311-musllinux_1_2_aarch64.whl", hash = "sha256:2593c77efde7bfea7f6389f1ab249b15ed4aa5bc5cb5131faa3b843c429fbedb", size = 5067343, upload-time = "2025-09-22T04:01:03.13Z" },
    { url = "https://files.pythonhosted.org/packages/1c/b0/bb8275ab5472f32b28cfbbcc6db7c9d092482d3439ca279d8d6fa02f7025/lxml-6.0.2-cp311-cp311-musllinux_1_2_armv7l.whl", hash = "sha256:3e3cb08855967a20f553ff32d147e14329b3ae70ced6edc2f282b94afbc74b2a", size = 4725419, upload-time = "2025-09-22T04:01:05.013Z" },
    { url = "https://files.pythonhosted.org/packages/25/4c/7c222753bc72edca3b99dbadba1b064209bc8ed4ad448af990e60dcce462/lxml-6.0.2-cp311-cp311-musllinux_1_2_riscv64.whl", hash = "sha256:2ed6c667fcbb8c19c6791bbf40b7268ef8ddf5a96940ba9404b9f9a304832f6c", size = 5275008, upload-time = "2025-09-22T04:01:07.327Z" },
    { url = "https://files.pythonhosted.org/packages/6c/8c/478a0dc6b6ed661451379447cdbec77c05741a75736d97e5b2b729687828/lxml-6.0.2-cp311-cp311-musllinux_1_2_x86_64.whl", hash = "sha256:b8f18914faec94132e5b91e69d76a5c1d7b0c73e2489ea8929c4aaa10b76bbf7", size = 5248906, upload-time = "2025-09-22T04:01:09.452Z" },
    { url = "https://files.pythonhosted.org/packages/2d/d9/5be3a6ab2784cdf9accb0703b65e1b64fcdd9311c9f007630c7db0cfcce1/lxml-6.0.2-cp311-cp311-win32.whl", hash = "sha256:6605c604e6daa9e0d7f0a2137bdc47a2e93b59c60a65466353e37f8272f47c46", size = 3610357, upload-time = "2025-09-22T04:01:11.102Z" },
    { url = "https://files.pythonhosted.org/packages/e2/7d/ca6fb13349b473d5732fb0ee3eec8f6c80fc0688e76b7d79c1008481bf1f/lxml-6.0.2-cp311-cp311-win_amd64.whl", hash = "sha256:e5867f2651016a3afd8dd2c8238baa66f1e2802f44bc17e236f547ace6647078", size = 4036583, upload-time = "2025-09-22T04:01:12.766Z" },
    { url = "https://files.pythonhosted.org/packages/ab/a2/51363b5ecd3eab46563645f3a2c3836a2fc67d01a1b87c5017040f39f567/lxml-6.0.2-cp311-cp311-win_arm64.whl", hash = "sha256:4197fb2534ee05fd3e7afaab5d8bfd6c2e186f65ea7f9cd6a82809c887bd1285", size = 3680591, upload-time = "2025-09-22T04:01:14.874Z" },
    { url = "https://files.pythonhosted.org/packages/f3/c8/8ff2bc6b920c84355146cd1ab7d181bc543b89241cfb1ebee824a7c81457/lxml-6.0.2-cp312-cp312-macosx_10_13_universal2.whl", hash = "sha256:a59f5448ba2ceccd06995c95ea59a7674a10de0810f2ce90c9006f3cbc044456", size = 8661887, upload-time = "2025-09-22T04:01:17.265Z" },
    { url = "https://files.pythonhosted.org/packages/37/6f/9aae1008083bb501ef63284220ce81638332f9ccbfa53765b2b7502203cf/lxml-6.0.2-cp312-cp312-macosx_10_13_x86_64.whl", hash = "sha256:e8113639f3296706fbac34a30813929e29247718e88173ad849f57ca59754924", size = 4667818, upload-time = "2025-09-22T04:01:19.688Z" },
    { url = "https://files.pythonhosted.org/packages/f1/ca/31fb37f99f37f1536c133476674c10b577e409c0a624384147653e38baf2/lxml-6.0.2-cp312-cp312-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:a8bef9b9825fa8bc816a6e641bb67219489229ebc648be422af695f6e7a4fa7f", size = 4950807, upload-time = "2025-09-22T04:01:21.487Z" },
    { url = "https://files.pythonhosted.org/packages/da/87/f6cb9442e4bada8aab5ae7e1046264f62fdbeaa6e3f6211b93f4c0dd97f1/lxml-6.0.2-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:65ea18d710fd14e0186c2f973dc60bb52039a275f82d3c44a0e42b43440ea534", size = 5109179, upload-time = "2025-09-22T04:01:23.32Z" },
    { url = "https://files.pythonhosted.org/packages/c8/20/a7760713e65888db79bbae4f6146a6ae5c04e4a204a3c48896c408cd6ed2/lxml-6.0.2-cp312-cp312-manylinux_2_26_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:c371aa98126a0d4c739ca93ceffa0fd7a5d732e3ac66a46e74339acd4d334564", size = 5023044, upload-time = "2025-09-22T04:01:25.118Z" },
    { url = "https://files.pythonhosted.org/packages/a2/b0/7e64e0460fcb36471899f75831509098f3fd7cd02a3833ac517433cb4f8f/lxml-6.0.2-cp312-cp312-manylinux_2_26_i686.manylinux_2_28_i686.whl", hash = "sha256:700efd30c0fa1a3581d80a748157397559396090a51d306ea59a70020223d16f", size = 5359685, upload-time = "2025-09-22T04:01:27.398Z" },
    { url = "https://files.pythonhosted.org/packages/b9/e1/e5df362e9ca4e2f48ed6411bd4b3a0ae737cc842e96877f5bf9428055ab4/lxml-6.0.2-cp312-cp312-manylinux_2_26_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:c33e66d44fe60e72397b487ee92e01da0d09ba2d66df8eae42d77b6d06e5eba0", size = 5654127, upload-time = "2025-09-22T04:01:29.629Z" },
    { url = "https://files.pythonhosted.org/packages/c6/d1/232b3309a02d60f11e71857778bfcd4acbdb86c07db8260caf7d008b08f8/lxml-6.0.2-cp312-cp312-manylinux_2_26_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:90a345bbeaf9d0587a3aaffb7006aa39ccb6ff0e96a57286c0cb2fd1520ea192", size = 5253958, upload-time = "2025-09-22T04:01:31.535Z" },
    { url = "https://files.pythonhosted.org/packages/35/35/d955a070994725c4f7d80583a96cab9c107c57a125b20bb5f708fe941011/lxml-6.0.2-cp312-cp312-manylinux_2_31_armv7l.whl", hash = "sha256:064fdadaf7a21af3ed1dcaa106b854077fbeada827c18f72aec9346847cd65d0", size = 4711541, upload-time = "2025-09-22T04:01:33.801Z" },
    { url = "https://files.pythonhosted.org/packages/1e/be/667d17363b38a78c4bd63cfd4b4632029fd68d2c2dc81f25ce9eb5224dd5/lxml-6.0.2-cp312-cp312-manylinux_2_38_riscv64.manylinux_2_39_riscv64.whl", hash = "sha256:fbc74f42c3525ac4ffa4b89cbdd00057b6196bcefe8bce794abd42d33a018092", size = 5267426, upload-time = "2025-09-22T04:01:35.639Z" },
    { url = "https://files.pythonhosted.org/packages/ea/47/62c70aa4a1c26569bc958c9ca86af2bb4e1f614e8c04fb2989833874f7ae/lxml-6.0.2-cp312-cp312-musllinux_1_2_aarch64.whl", hash = "sha256:6ddff43f702905a4e32bc24f3f2e2edfe0f8fde3277d481bffb709a4cced7a1f", size = 5064917, upload-time = "2025-09-22T04:01:37.448Z" },
    { url = "https://files.pythonhosted.org/packages/bd/55/6ceddaca353ebd0f1908ef712c597f8570cc9c58130dbb89903198e441fd/lxml-6.0.2-cp312-cp312-musllinux_1_2_armv7l.whl", hash = "sha256:6da5185951d72e6f5352166e3da7b0dc27aa70bd1090b0eb3f7f7212b53f1bb8", size = 4788795, upload-time = "2025-09-22T04:01:39.165Z" },
    { url = "https://files.pythonhosted.org/packages/cf/e8/fd63e15da5e3fd4c2146f8bbb3c14e94ab850589beab88e547b2dbce22e1/lxml-6.0.2-cp312-cp312-musllinux_1_2_ppc64le.whl", hash = "sha256:57a86e1ebb4020a38d295c04fc79603c7899e0df71588043eb218722dabc087f", size = 5676759, upload-time = "2025-09-22T04:01:41.506Z" },
    { url = "https://files.pythonhosted.org/packages/76/47/b3ec58dc5c374697f5ba37412cd2728f427d056315d124dd4b61da381877/lxml-6.0.2-cp312-cp312-musllinux_1_2_riscv64.whl", hash = "sha256:2047d8234fe735ab77802ce5f2297e410ff40f5238aec569ad7c8e163d7b19a6", size = 5255666, upload-time = "2025-09-22T04:01:43.363Z" },
    { url = "https://files.pythonhosted.org/packages/19/93/03ba725df4c3d72afd9596eef4a37a837ce8e4806010569bedfcd2cb68fd/lxml-6.0.2-cp312-cp312-musllinux_1_2_x86_64.whl", hash = "sha256:6f91fd2b2ea15a6800c8e24418c0775a1694eefc011392da73bc6cef2623b322", size = 5277989, upload-time = "2025-09-22T04:01:45.215Z" },
    { url = "https://files.pythonhosted.org/packages/c6/80/c06de80bfce881d0ad738576f243911fccf992687ae09fd80b734712b39c/lxml-6.0.2-cp312-cp312-win32.whl", hash = "sha256:3ae2ce7d6fedfb3414a2b6c5e20b249c4c607f72cb8d2bb7cc9c6ec7c6f4e849", size = 3611456, upload-time = "2025-09-22T04:01:48.243Z" },
    { url = "https://files.pythonhosted.org/packages/f7/d7/0cdfb6c3e30893463fb3d1e52bc5f5f99684a03c29a0b6b605cfae879cd5/lxml-6.0.2-cp312-cp312-win_amd64.whl", hash = "sha256:72c87e5ee4e58a8354fb9c7c84cbf95a1c8236c127a5d1b7683f04bed8361e1f", size = 4011793, upload-time = "2025-09-22T04:01:50.042Z" },
    { url = "https://files.pythonhosted.org/packages/ea/7b/93c73c67db235931527301ed3785f849c78991e2e34f3fd9a6663ffda4c5/lxml-6.0.2-cp312-cp312-win_arm64.whl", hash = "sha256:61cb10eeb95570153e0c0e554f58df92ecf5109f75eacad4a95baa709e26c3d6", size = 3672836, upload-time = "2025-09-22T04:01:52.145Z" },
    { url = "https://files.pythonhosted.org/packages/53/fd/4e8f0540608977aea078bf6d79f128e0e2c2bba8af1acf775c30baa70460/lxml-6.0.2-cp313-cp313-macosx_10_13_universal2.whl", hash = "sha256:9b33d21594afab46f37ae58dfadd06636f154923c4e8a4d754b0127554eb2e77", size = 8648494, upload-time = "2025-09-22T04:01:54.242Z" },
    { url = "https://files.pythonhosted.org/packages/5d/f4/2a94a3d3dfd6c6b433501b8d470a1960a20ecce93245cf2db1706adf6c19/lxml-6.0.2-cp313-cp313-macosx_10_13_x86_64.whl", hash = "sha256:6c8963287d7a4c5c9a432ff487c52e9c5618667179c18a204bdedb27310f022f", size = 4661146, upload-time = "2025-09-22T04:01:56.282Z" },
    { url = "https://files.pythonhosted.org/packages/25/2e/4efa677fa6b322013035d38016f6ae859d06cac67437ca7dc708a6af7028/lxml-6.0.2-cp313-cp313-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:1941354d92699fb5ffe6ed7b32f9649e43c2feb4b97205f75866f7d21aa91452", size = 4946932, upload-time = "2025-09-22T04:01:58.989Z" },
    { url = "https://files.pythonhosted.org/packages/ce/0f/526e78a6d38d109fdbaa5049c62e1d32fdd70c75fb61c4eadf3045d3d124/lxml-6.0.2-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:bb2f6ca0ae2d983ded09357b84af659c954722bbf04dea98030064996d156048", size = 5100060, upload-time = "2025-09-22T04:02:00.812Z" },
    { url = "https://files.pythonhosted.org/packages/81/76/99de58d81fa702cc0ea7edae4f4640416c2062813a00ff24bd70ac1d9c9b/lxml-6.0.2-cp313-cp313-manylinux_2_26_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:eb2a12d704f180a902d7fa778c6d71f36ceb7b0d317f34cdc76a5d05aa1dd1df", size = 5019000, upload-time = "2025-09-22T04:02:02.671Z" },
    { url = "https://files.pythonhosted.org/packages/b5/35/9e57d25482bc9a9882cb0037fdb9cc18f4b79d85df94fa9d2a89562f1d25/lxml-6.0.2-cp313-cp313-manylinux_2_26_i686.manylinux_2_28_i686.whl", hash = "sha256:6ec0e3f745021bfed19c456647f0298d60a24c9ff86d9d051f52b509663feeb1", size = 5348496, upload-time = "2025-09-22T04:02:04.904Z" },
    { url = "https://files.pythonhosted.org/packages/a6/8e/cb99bd0b83ccc3e8f0f528e9aa1f7a9965dfec08c617070c5db8d63a87ce/lxml-6.0.2-cp313-cp313-manylinux_2_26_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:846ae9a12d54e368933b9759052d6206a9e8b250291109c48e350c1f1f49d916", size = 5643779, upload-time = "2025-09-22T04:02:06.689Z" },
    { url = "https://files.pythonhosted.org/packages/d0/34/9e591954939276bb679b73773836c6684c22e56d05980e31d52a9a8deb18/lxml-6.0.2-cp313-cp313-manylinux_2_26_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:ef9266d2aa545d7374938fb5c484531ef5a2ec7f2d573e62f8ce722c735685fd", size = 5244072, upload-time = "2025-09-22T04:02:08.587Z" },
    { url = "https://files.pythonhosted.org/packages/8d/27/b29ff065f9aaca443ee377aff699714fcbffb371b4fce5ac4ca759e436d5/lxml-6.0.2-cp313-cp313-manylinux_2_31_armv7l.whl", hash = "sha256:4077b7c79f31755df33b795dc12119cb557a0106bfdab0d2c2d97bd3cf3dffa6", size = 4718675, upload-time = "2025-09-22T04:02:10.783Z" },
    { url = "https://files.pythonhosted.org/packages/2b/9f/f756f9c2cd27caa1a6ef8c32ae47aadea697f5c2c6d07b0dae133c244fbe/lxml-6.0.2-cp313-cp313-manylinux_2_38_riscv64.manylinux_2_39_riscv64.whl", hash = "sha256:a7c5d5e5f1081955358533be077166ee97ed2571d6a66bdba6ec2f609a715d1a", size = 5255171, upload-time = "2025-09-22T04:02:12.631Z" },
    { url = "https://files.pythonhosted.org/packages/61/46/bb85ea42d2cb1bd8395484fd72f38e3389611aa496ac7772da9205bbda0e/lxml-6.0.2-cp313-cp313-musllinux_1_2_aarch64.whl", hash = "sha256:8f8d0cbd0674ee89863a523e6994ac25fd5be9c8486acfc3e5ccea679bad2679", size = 5057175, upload-time = "2025-09-22T04:02:14.718Z" },
    { url = "https://files.pythonhosted.org/packages/95/0c/443fc476dcc8e41577f0af70458c50fe299a97bb6b7505bb1ae09aa7f9ac/lxml-6.0.2-cp313-cp313-musllinux_1_2_armv7l.whl", hash = "sha256:2cbcbf6d6e924c28f04a43f3b6f6e272312a090f269eff68a2982e13e5d57659", size = 4785688, upload-time = "2025-09-22T04:02:16.957Z" },
    { url = "https://files.pythonhosted.org/packages/48/78/6ef0b359d45bb9697bc5a626e1992fa5d27aa3f8004b137b2314793b50a0/lxml-6.0.2-cp313-cp313-musllinux_1_2_ppc64le.whl", hash = "sha256:dfb874cfa53340009af6bdd7e54ebc0d21012a60a4e65d927c2e477112e63484", size = 5660655, upload-time = "2025-09-22T04:02:18.815Z" },
    { url = "https://files.pythonhosted.org/packages/ff/ea/e1d33808f386bc1339d08c0dcada6e4712d4ed8e93fcad5f057070b7988a/lxml-6.0.2-cp313-cp313-musllinux_1_2_riscv64.whl", hash = "sha256:fb8dae0b6b8b7f9e96c26fdd8121522ce5de9bb5538010870bd538683d30e9a2", size = 5247695, upload-time = "2025-09-22T04:02:20.593Z" },
    { url = "https://files.pythonhosted.org/packages/4f/47/eba75dfd8183673725255247a603b4ad606f4ae657b60c6c145b381697da/lxml-6.0.2-cp313-cp313-musllinux_1_2_x86_64.whl", hash = "sha256:358d9adae670b63e95bc59747c72f4dc97c9ec58881d4627fe0120da0f90d314", size = 5269841, upload-time = "2025-09-22T04:02:22.489Z" },
    { url = "https://files.pythonhosted.org/packages/76/04/5c5e2b8577bc936e219becb2e98cdb1aca14a4921a12995b9d0c523502ae/lxml-6.0.2-cp313-cp313-win32.whl", hash = "sha256:e8cd2415f372e7e5a789d743d133ae474290a90b9023197fd78f32e2dc6873e2", size = 3610700, upload-time = "2025-09-22T04:02:24.465Z" },
    { url = "https://files.pythonhosted.org/packages/fe/0a/4643ccc6bb8b143e9f9640aa54e38255f9d3b45feb2cbe7ae2ca47e8782e/lxml-6.0.2-cp313-cp313-win_amd64.whl", hash = "sha256:b30d46379644fbfc3ab81f8f82ae4de55179414651f110a1514f0b1f8f6cb2d7", size = 4010347, upload-time = "2025-09-22T04:02:26.286Z" },
    { url = "https://files.pythonhosted.org/packages/31/ef/dcf1d29c3f530577f61e5fe2f1bd72929acf779953668a8a47a479ae6f26/lxml-6.0.2-cp313-cp313-win_arm64.whl", hash = "sha256:13dcecc9946dca97b11b7c40d29fba63b55ab4170d3c0cf8c0c164343b9bfdcf", size = 3671248, upload-time = "2025-09-22T04:02:27.918Z" },
    { url = "https://files.pythonhosted.org/packages/03/15/d4a377b385ab693ce97b472fe0c77c2b16ec79590e688b3ccc71fba19884/lxml-6.0.2-cp314-cp314-macosx_10_13_universal2.whl", hash = "sha256:b0c732aa23de8f8aec23f4b580d1e52905ef468afb4abeafd3fec77042abb6fe", size = 8659801, upload-time = "2025-09-22T04:02:30.113Z" },
    { url = "https://files.pythonhosted.org/packages/c8/e8/c128e37589463668794d503afaeb003987373c5f94d667124ffd8078bbd9/lxml-6.0.2-cp314-cp314-macosx_10_13_x86_64.whl", hash = "sha256:4468e3b83e10e0317a89a33d28f7aeba1caa4d1a6fd457d115dd4ffe90c5931d", size = 4659403, upload-time = "2025-09-22T04:02:32.119Z" },
    { url = "https://files.pythonhosted.org/packages/00/ce/74903904339decdf7da7847bb5741fc98a5451b42fc419a86c0c13d26fe2/lxml-6.0.2-cp314-cp314-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:abd44571493973bad4598a3be7e1d807ed45aa2adaf7ab92ab7c62609569b17d", size = 4966974, upload-time = "2025-09-22T04:02:34.155Z" },
    { url = "https://files.pythonhosted.org/packages/1f/d3/131dec79ce61c5567fecf82515bd9bc36395df42501b50f7f7f3bd065df0/lxml-6.0.2-cp314-cp314-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:370cd78d5855cfbffd57c422851f7d3864e6ae72d0da615fca4dad8c45d375a5", size = 5102953, upload-time = "2025-09-22T04:02:36.054Z" },
    { url = "https://files.pythonhosted.org/packages/3a/ea/a43ba9bb750d4ffdd885f2cd333572f5bb900cd2408b67fdda07e85978a0/lxml-6.0.2-cp314-cp314-manylinux_2_26_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:901e3b4219fa04ef766885fb40fa516a71662a4c61b80c94d25336b4934b71c0", size = 5055054, upload-time = "2025-09-22T04:02:38.154Z" },
    { url = "https://files.pythonhosted.org/packages/60/23/6885b451636ae286c34628f70a7ed1fcc759f8d9ad382d132e1c8d3d9bfd/lxml-6.0.2-cp314-cp314-manylinux_2_26_i686.manylinux_2_28_i686.whl", hash = "sha256:a4bf42d2e4cf52c28cc1812d62426b9503cdb0c87a6de81442626aa7d69707ba", size = 5352421, upload-time = "2025-09-22T04:02:40.413Z" },
    { url = "https://files.pythonhosted.org/packages/48/5b/fc2ddfc94ddbe3eebb8e9af6e3fd65e2feba4967f6a4e9683875c394c2d8/lxml-6.0.2-cp314-cp314-manylinux_2_26_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:b2c7fdaa4d7c3d886a42534adec7cfac73860b89b4e5298752f60aa5984641a0", size = 5673684, upload-time = "2025-09-22T04:02:42.288Z" },
    { url = "https://files.pythonhosted.org/packages/29/9c/47293c58cc91769130fbf85531280e8cc7868f7fbb6d92f4670071b9cb3e/lxml-6.0.2-cp314-cp314-manylinux_2_26_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:98a5e1660dc7de2200b00d53fa00bcd3c35a3608c305d45a7bbcaf29fa16e83d", size = 5252463, upload-time = "2025-09-22T04:02:44.165Z" },
    { url = "https://files.pythonhosted.org/packages/9b/da/ba6eceb830c762b48e711ded880d7e3e89fc6c7323e587c36540b6b23c6b/lxml-6.0.2-cp314-cp314-manylinux_2_31_armv7l.whl", hash = "sha256:dc051506c30b609238d79eda75ee9cab3e520570ec8219844a72a46020901e37", size = 4698437, upload-time = "2025-09-22T04:02:46.524Z" },
    { url = "https://files.pythonhosted.org/packages/a5/24/7be3f82cb7990b89118d944b619e53c656c97dc89c28cfb143fdb7cd6f4d/lxml-6.0.2-cp314-cp314-manylinux_2_38_riscv64.manylinux_2_39_riscv64.whl", hash = "sha256:8799481bbdd212470d17513a54d568f44416db01250f49449647b5ab5b5dccb9", size = 5269890, upload-time = "2025-09-22T04:02:48.812Z" },
    { url = "https://files.pythonhosted.org/packages/1b/bd/dcfb9ea1e16c665efd7538fc5d5c34071276ce9220e234217682e7d2c4a5/lxml-6.0.2-cp314-cp314-musllinux_1_2_aarch64.whl", hash = "sha256:9261bb77c2dab42f3ecd9103951aeca2c40277701eb7e912c545c1b16e0e4917", size = 5097185, upload-time = "2025-09-22T04:02:50.746Z" },
    { url = "https://files.pythonhosted.org/packages/21/04/a60b0ff9314736316f28316b694bccbbabe100f8483ad83852d77fc7468e/lxml-6.0.2-cp314-cp314-musllinux_1_2_armv7l.whl", hash = "sha256:65ac4a01aba353cfa6d5725b95d7aed6356ddc0a3cd734de00124d285b04b64f", size = 4745895, upload-time = "2025-09-22T04:02:52.968Z" },
    { url = "https://files.pythonhosted.org/packages/d6/bd/7d54bd1846e5a310d9c715921c5faa71cf5c0853372adf78aee70c8d7aa2/lxml-6.0.2-cp314-cp314-musllinux_1_2_ppc64le.whl", hash = "sha256:b22a07cbb82fea98f8a2fd814f3d1811ff9ed76d0fc6abc84eb21527596e7cc8", size = 5695246, upload-time = "2025-09-22T04:02:54.798Z" },
    { url = "https://files.pythonhosted.org/packages/fd/32/5643d6ab947bc371da21323acb2a6e603cedbe71cb4c99c8254289ab6f4e/lxml-6.0.2-cp314-cp314-musllinux_1_2_riscv64.whl", hash = "sha256:d759cdd7f3e055d6bc8d9bec3ad905227b2e4c785dc16c372eb5b5e83123f48a", size = 5260797, upload-time = "2025-09-22T04:02:57.058Z" },
    { url = "https://files.pythonhosted.org/packages/33/da/34c1ec4cff1eea7d0b4cd44af8411806ed943141804ac9c5d565302afb78/lxml-6.0.2-cp314-cp314-musllinux_1_2_x86_64.whl", hash = "sha256:945da35a48d193d27c188037a05fec5492937f66fb1958c24fc761fb9d40d43c", size = 5277404, upload-time = "2025-09-22T04:02:58.966Z" },
    { url = "https://files.pythonhosted.org/packages/82/57/4eca3e31e54dc89e2c3507e1cd411074a17565fa5ffc437c4ae0a00d439e/lxml-6.0.2-cp314-cp314-win32.whl", hash = "sha256:be3aaa60da67e6153eb15715cc2e19091af5dc75faef8b8a585aea372507384b", size = 3670072, upload-time = "2025-09-22T04:03:38.05Z" },
    { url = "https://files.pythonhosted.org/packages/e3/e0/c96cf13eccd20c9421ba910304dae0f619724dcf1702864fd59dd386404d/lxml-6.0.2-cp314-cp314-win_amd64.whl", hash = "sha256:fa25afbadead523f7001caf0c2382afd272c315a033a7b06336da2637d92d6ed", size = 4080617, upload-time = "2025-09-22T04:03:39.835Z" },
    { url = "https://files.pythonhosted.org/packages/d5/5d/b3f03e22b3d38d6f188ef044900a9b29b2fe0aebb94625ce9fe244011d34/lxml-6.0.2-cp314-cp314-win_arm64.whl", hash = "sha256:063eccf89df5b24e361b123e257e437f9e9878f425ee9aae3144c77faf6da6d8", size = 3754930, upload-time = "2025-09-22T04:03:41.565Z" },
    { url = "https://files.pythonhosted.org/packages/5e/5c/42c2c4c03554580708fc738d13414801f340c04c3eff90d8d2d227145275/lxml-6.0.2-cp314-cp314t-macosx_10_13_universal2.whl", hash = "sha256:6162a86d86893d63084faaf4ff937b3daea233e3682fb4474db07395794fa80d", size = 8910380, upload-time = "2025-09-22T04:03:01.645Z" },
    { url = "https://files.pythonhosted.org/packages/bf/4f/12df843e3e10d18d468a7557058f8d3733e8b6e12401f30b1ef29360740f/lxml-6.0.2-cp314-cp314t-macosx_10_13_x86_64.whl", hash = "sha256:414aaa94e974e23a3e92e7ca5b97d10c0cf37b6481f50911032c69eeb3991bba", size = 4775632, upload-time = "2025-09-22T04:03:03.814Z" },
    { url = "https://files.pythonhosted.org/packages/e4/0c/9dc31e6c2d0d418483cbcb469d1f5a582a1cd00a1f4081953d44051f3c50/lxml-6.0.2-cp314-cp314t-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:48461bd21625458dd01e14e2c38dd0aea69addc3c4f960c30d9f59d7f93be601", size = 4975171, upload-time = "2025-09-22T04:03:05.651Z" },
    { url = "https://files.pythonhosted.org/packages/e7/2b/9b870c6ca24c841bdd887504808f0417aa9d8d564114689266f19ddf29c8/lxml-6.0.2-cp314-cp314t-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:25fcc59afc57d527cfc78a58f40ab4c9b8fd096a9a3f964d2781ffb6eb33f4ed", size = 5110109, upload-time = "2025-09-22T04:03:07.452Z" },
    { url = "https://files.pythonhosted.org/packages/bf/0c/4f5f2a4dd319a178912751564471355d9019e220c20d7db3fb8307ed8582/lxml-6.0.2-cp314-cp314t-manylinux_2_26_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:5179c60288204e6ddde3f774a93350177e08876eaf3ab78aa3a3649d43eb7d37", size = 5041061, upload-time = "2025-09-22T04:03:09.297Z" },
    { url = "https://files.pythonhosted.org/packages/12/64/554eed290365267671fe001a20d72d14f468ae4e6acef1e179b039436967/lxml-6.0.2-cp314-cp314t-manylinux_2_26_i686.manylinux_2_28_i686.whl", hash = "sha256:967aab75434de148ec80597b75062d8123cadf2943fb4281f385141e18b21338", size = 5306233, upload-time = "2025-09-22T04:03:11.651Z" },
    { url = "https://files.pythonhosted.org/packages/7a/31/1d748aa275e71802ad9722df32a7a35034246b42c0ecdd8235412c3396ef/lxml-6.0.2-cp314-cp314t-manylinux_2_26_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:d100fcc8930d697c6561156c6810ab4a508fb264c8b6779e6e61e2ed5e7558f9", size = 5604739, upload-time = "2025-09-22T04:03:13.592Z" },
    { url = "https://files.pythonhosted.org/packages/8f/41/2c11916bcac09ed561adccacceaedd2bf0e0b25b297ea92aab99fd03d0fa/lxml-6.0.2-cp314-cp314t-manylinux_2_26_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:2ca59e7e13e5981175b8b3e4ab84d7da57993eeff53c07764dcebda0d0e64ecd", size = 5225119, upload-time = "2025-09-22T04:03:15.408Z" },
    { url = "https://files.pythonhosted.org/packages/99/05/4e5c2873d8f17aa018e6afde417c80cc5d0c33be4854cce3ef5670c49367/lxml-6.0.2-cp314-cp314t-manylinux_2_31_armv7l.whl", hash = "sha256:957448ac63a42e2e49531b9d6c0fa449a1970dbc32467aaad46f11545be9af1d", size = 4633665, upload-time = "2025-09-22T04:03:17.262Z" },
    { url = "https://files.pythonhosted.org/packages/0f/c9/dcc2da1bebd6275cdc723b515f93edf548b82f36a5458cca3578bc899332/lxml-6.0.2-cp314-cp314t-manylinux_2_38_riscv64.manylinux_2_39_riscv64.whl", hash = "sha256:b7fc49c37f1786284b12af63152fe1d0990722497e2d5817acfe7a877522f9a9", size = 5234997, upload-time = "2025-09-22T04:03:19.14Z" },
    { url = "https://files.pythonhosted.org/packages/9c/e2/5172e4e7468afca64a37b81dba152fc5d90e30f9c83c7c3213d6a02a5ce4/lxml-6.0.2-cp314-cp314t-musllinux_1_2_aarch64.whl", hash = "sha256:e19e0643cc936a22e837f79d01a550678da8377d7d801a14487c10c34ee49c7e", size = 5090957, upload-time = "2025-09-22T04:03:21.436Z" },
    { url = "https://files.pythonhosted.org/packages/a5/b3/15461fd3e5cd4ddcb7938b87fc20b14ab113b92312fc97afe65cd7c85de1/lxml-6.0.2-cp314-cp314t-musllinux_1_2_armv7l.whl", hash = "sha256:1db01e5cf14345628e0cbe71067204db658e2fb8e51e7f33631f5f4735fefd8d", size = 4764372, upload-time = "2025-09-22T04:03:23.27Z" },
    { url = "https://files.pythonhosted.org/packages/05/33/f310b987c8bf9e61c4dd8e8035c416bd3230098f5e3cfa69fc4232de7059/lxml-6.0.2-cp314-cp314t-musllinux_1_2_ppc64le.whl", hash = "sha256:875c6b5ab39ad5291588aed6925fac99d0097af0dd62f33c7b43736043d4a2ec", size = 5634653, upload-time = "2025-09-22T04:03:25.767Z" },
    { url = "https://files.pythonhosted.org/packages/70/ff/51c80e75e0bc9382158133bdcf4e339b5886c6ee2418b5199b3f1a61ed6d/lxml-6.0.2-cp314-cp314t-musllinux_1_2_riscv64.whl", hash = "sha256:cdcbed9ad19da81c480dfd6dd161886db6096083c9938ead313d94b30aadf272", size = 5233795, upload-time = "2025-09-22T04:03:27.62Z" },
    { url = "https://files.pythonhosted.org/packages/56/4d/4856e897df0d588789dd844dbed9d91782c4ef0b327f96ce53c807e13128/lxml-6.0.2-cp314-cp314t-musllinux_1_2_x86_64.whl", hash = "sha256:80dadc234ebc532e09be1975ff538d154a7fa61ea5031c03d25178855544728f", size = 5257023, upload-time = "2025-09-22T04:03:30.056Z" },
    { url = "https://files.pythonhosted.org/packages/0f/85/86766dfebfa87bea0ab78e9ff7a4b4b45225df4b4d3b8cc3c03c5cd68464/lxml-6.0.2-cp314-cp314t-win32.whl", hash = "sha256:da08e7bb297b04e893d91087df19638dc7a6bb858a954b0cc2b9f5053c922312", size = 3911420, upload-time = "2025-09-22T04:03:32.198Z" },
    { url = "https://files.pythonhosted.org/packages/fe/1a/b248b355834c8e32614650b8008c69ffeb0ceb149c793961dd8c0b991bb3/lxml-6.0.2-cp314-cp314t-win_amd64.whl", hash = "sha256:252a22982dca42f6155125ac76d3432e548a7625d56f5a273ee78a5057216eca", size = 4406837, upload-time = "2025-09-22T04:03:34.027Z" },
    { url = "https://files.pythonhosted.org/packages/92/aa/df863bcc39c5e0946263454aba394de8a9084dbaff8ad143846b0d844739/lxml-6.0.2-cp314-cp314t-win_arm64.whl", hash = "sha256:bb4c1847b303835d89d785a18801a883436cdfd5dc3d62947f9c49e24f0f5a2c", size = 3822205, upload-time = "2025-09-22T04:03:36.249Z" },
    { url = "https://files.pythonhosted.org/packages/0b/11/29d08bc103a62c0eba8016e7ed5aeebbf1e4312e83b0b1648dd203b0e87d/lxml-6.0.2-pp311-pypy311_pp73-macosx_10_15_x86_64.whl", hash = "sha256:1c06035eafa8404b5cf475bb37a9f6088b0aca288d4ccc9d69389750d5543700", size = 3949829, upload-time = "2025-09-22T04:04:45.608Z" },
    { url = "https://files.pythonhosted.org/packages/12/b3/52ab9a3b31e5ab8238da241baa19eec44d2ab426532441ee607165aebb52/lxml-6.0.2-pp311-pypy311_pp73-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:c7d13103045de1bdd6fe5d61802565f1a3537d70cd3abf596aa0af62761921ee", size = 4226277, upload-time = "2025-09-22T04:04:47.754Z" },
    { url = "https://files.pythonhosted.org/packages/a0/33/1eaf780c1baad88224611df13b1c2a9dfa460b526cacfe769103ff50d845/lxml-6.0.2-pp311-pypy311_pp73-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:0a3c150a95fbe5ac91de323aa756219ef9cf7fde5a3f00e2281e30f33fa5fa4f", size = 4330433, upload-time = "2025-09-22T04:04:49.907Z" },
    { url = "https://files.pythonhosted.org/packages/7a/c1/27428a2ff348e994ab4f8777d3a0ad510b6b92d37718e5887d2da99952a2/lxml-6.0.2-pp311-pypy311_pp73-manylinux_2_26_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:60fa43be34f78bebb27812ed90f1925ec99560b0fa1decdb7d12b84d857d31e9", size = 4272119, upload-time = "2025-09-22T04:04:51.801Z" },
    { url = "https://files.pythonhosted.org/packages/f0/d0/3020fa12bcec4ab62f97aab026d57c2f0cfd480a558758d9ca233bb6a79d/lxml-6.0.2-pp311-pypy311_pp73-manylinux_2_26_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:21c73b476d3cfe836be731225ec3421fa2f048d84f6df6a8e70433dff1376d5a", size = 4417314, upload-time = "2025-09-22T04:04:55.024Z" },
    { url = "https://files.pythonhosted.org/packages/6c/77/d7f491cbc05303ac6801651aabeb262d43f319288c1ea96c66b1d2692ff3/lxml-6.0.2-pp311-pypy311_pp73-win_amd64.whl", hash = "sha256:27220da5be049e936c3aca06f174e8827ca6445a4353a1995584311487fc4e3e", size = 3518768, upload-time = "2025-09-22T04:04:57.097Z" },
]

[[package]]
name = "markdown-it-py"
version = "4.0.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "mdurl" },
]
sdist = { url = "https://files.pythonhosted.org/packages/5b/f5/4ec618ed16cc4f8fb3b701563655a69816155e79e24a17b651541804721d/markdown_it_py-4.0.0.tar.gz", hash = "sha256:cb0a2b4aa34f932c007117b194e945bd74e0ec24133ceb5bac59009cda1cb9f3", size = 73070, upload-time = "2025-08-11T12:57:52.854Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/94/54/e7d793b573f298e1c9013b8c4dade17d481164aa517d1d7148619c2cedbf/markdown_it_py-4.0.0-py3-none-any.whl", hash = "sha256:87327c59b172c5011896038353a81343b6754500a08cd7a4973bb48c6d578147", size = 87321, upload-time = "2025-08-11T12:57:51.923Z" },
]

[[package]]
name = "mdurl"
version = "0.1.2"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/d6/54/cfe61301667036ec958cb99bd3efefba235e65cdeb9c84d24a8293ba1d90/mdurl-0.1.2.tar.gz", hash = "sha256:bb413d29f5eea38f31dd4754dd7377d4465116fb207585f97bf925588687c1ba", size = 8729, upload-time = "2022-08-14T12:40:10.846Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/b3/38/89ba8ad64ae25be8de66a6d463314cf1eb366222074cfda9ee839c56a4b4/mdurl-0.1.2-py3-none-any.whl", hash = "sha256:84008a41e51615a49fc9966191ff91509e3c40b939176e643fd50a5c2196b8f8", size = 9979, upload-time = "2022-08-14T12:40:09.779Z" },
]

[[package]]
name = "mmh3"
version = "5.2.1"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/91/1a/edb23803a168f070ded7a3014c6d706f63b90c84ccc024f89d794a3b7a6d/mmh3-5.2.1.tar.gz", hash = "sha256:bbea5b775f0ac84945191fb83f845a6fd9a21a03ea7f2e187defac7e401616ad", size = 33775, upload-time = "2026-03-05T15:55:57.716Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/65/d7/3312a59df3c1cdd783f4cf0c4ee8e9decff9c5466937182e4cc7dbbfe6c5/mmh3-5.2.1-cp311-cp311-macosx_10_9_universal2.whl", hash = "sha256:dae0f0bd7d30c0ad61b9a504e8e272cb8391eed3f1587edf933f4f6b33437450", size = 56082, upload-time = "2026-03-05T15:53:59.702Z" },
    { url = "https://files.pythonhosted.org/packages/61/96/6f617baa098ca0d2989bfec6d28b5719532cd8d8848782662f5b755f657f/mmh3-5.2.1-cp311-cp311-macosx_10_9_x86_64.whl", hash = "sha256:9aeaf53eaa075dd63e81512522fd180097312fb2c9f476333309184285c49ce0", size = 40458, upload-time = "2026-03-05T15:54:01.548Z" },
    { url = "https://files.pythonhosted.org/packages/c1/b4/9cd284bd6062d711e13d26c04d4778ab3f690c1c38a4563e3c767ec8802e/mmh3-5.2.1-cp311-cp311-macosx_11_0_arm64.whl", hash = "sha256:0634581290e6714c068f4aa24020acf7880927d1f0084fa753d9799ae9610082", size = 40079, upload-time = "2026-03-05T15:54:02.743Z" },
    { url = "https://files.pythonhosted.org/packages/f6/09/a806334ce1d3d50bf782b95fcee8b3648e1e170327d4bb7b4bad2ad7d956/mmh3-5.2.1-cp311-cp311-manylinux1_i686.manylinux_2_28_i686.manylinux_2_5_i686.whl", hash = "sha256:e080c0637aea036f35507e803a4778f119a9b436617694ae1c5c366805f1e997", size = 97242, upload-time = "2026-03-05T15:54:04.536Z" },
    { url = "https://files.pythonhosted.org/packages/ee/93/723e317dd9e041c4dc4566a2eb53b01ad94de31750e0b834f1643905e97c/mmh3-5.2.1-cp311-cp311-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:db0562c5f71d18596dcd45e854cf2eeba27d7543e1a3acdafb7eef728f7fe85d", size = 103082, upload-time = "2026-03-05T15:54:06.387Z" },
    { url = "https://files.pythonhosted.org/packages/61/b5/f96121e69cc48696075071531cf574f112e1ffd08059f4bffb41210e6fc5/mmh3-5.2.1-cp311-cp311-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:1d9f9a3ce559a5267014b04b82956993270f63ec91765e13e9fd73daf2d2738e", size = 106054, upload-time = "2026-03-05T15:54:07.506Z" },
    { url = "https://files.pythonhosted.org/packages/82/49/192b987ec48d0b2aecf8ac285a9b11fbc00030f6b9c694664ae923458dde/mmh3-5.2.1-cp311-cp311-manylinux2014_ppc64le.manylinux_2_17_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:960b1b3efa39872ac8b6cc3a556edd6fb90ed74f08c9c45e028f1005b26aa55d", size = 112910, upload-time = "2026-03-05T15:54:09.403Z" },
    { url = "https://files.pythonhosted.org/packages/cf/a1/03e91fd334ed0144b83343a76eb11f17434cd08f746401488cfeafb2d241/mmh3-5.2.1-cp311-cp311-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:d30b650595fdbe32366b94cb14f30bb2b625e512bd4e1df00611f99dc5c27fd4", size = 120551, upload-time = "2026-03-05T15:54:10.587Z" },
    { url = "https://files.pythonhosted.org/packages/93/b9/b89a71d2ff35c3a764d1c066c7313fc62c7cc48fa48a4b3b0304a4a0146f/mmh3-5.2.1-cp311-cp311-musllinux_1_2_aarch64.whl", hash = "sha256:82f3802bfc4751f420d591c5c864de538b71cea117fce67e4595c2afede08a15", size = 99096, upload-time = "2026-03-05T15:54:11.76Z" },
    { url = "https://files.pythonhosted.org/packages/36/b5/613772c1c6ed5f7b63df55eb131e887cc43720fec392777b95a79d34e640/mmh3-5.2.1-cp311-cp311-musllinux_1_2_i686.whl", hash = "sha256:915e7a2418f10bd1151b1953df06d896db9783c9cfdb9a8ee1f9b3a4331ab503", size = 98524, upload-time = "2026-03-05T15:54:13.122Z" },
    { url = "https://files.pythonhosted.org/packages/5e/0e/1524566fe8eaf871e4f7bc44095929fcd2620488f402822d848df19d679c/mmh3-5.2.1-cp311-cp311-musllinux_1_2_ppc64le.whl", hash = "sha256:fc78739b5ec6e4fb02301984a3d442a91406e7700efbe305071e7fd1c78278f2", size = 106239, upload-time = "2026-03-05T15:54:14.601Z" },
    { url = "https://files.pythonhosted.org/packages/04/94/21adfa7d90a7a697137ad6de33eeff6445420ca55e433a5d4919c79bc3b5/mmh3-5.2.1-cp311-cp311-musllinux_1_2_s390x.whl", hash = "sha256:41aac7002a749f08727cb91babff1daf8deac317c0b1f317adc69be0e6c375d1", size = 109797, upload-time = "2026-03-05T15:54:15.819Z" },
    { url = "https://files.pythonhosted.org/packages/b5/e6/1aacc3a219e1aa62fa65669995d4a3562b35be5200ec03680c7e4bec9676/mmh3-5.2.1-cp311-cp311-musllinux_1_2_x86_64.whl", hash = "sha256:9d8089d853c7963a8ce87fff93e2a67075c0bc08684a08ea6ad13577c38ffc38", size = 97228, upload-time = "2026-03-05T15:54:16.992Z" },
    { url = "https://files.pythonhosted.org/packages/f1/b9/5e4cca8dcccf298add0a27f3c357bc8cf8baf821d35cdc6165e4bd5a48b0/mmh3-5.2.1-cp311-cp311-win32.whl", hash = "sha256:baeb47635cb33375dee4924cd93d7f5dcaa786c740b08423b0209b824a1ee728", size = 40751, upload-time = "2026-03-05T15:54:18.714Z" },
    { url = "https://files.pythonhosted.org/packages/72/fc/5b11d49247f499bcda591171e9cf3b6ee422b19e70aa2cef2e0ae65ca3b9/mmh3-5.2.1-cp311-cp311-win_amd64.whl", hash = "sha256:1e4ecee40ba19e6975e1120829796770325841c2f153c0e9aecca927194c6a2a", size = 41517, upload-time = "2026-03-05T15:54:19.764Z" },
    { url = "https://files.pythonhosted.org/packages/8a/5f/2a511ee8a1c2a527c77726d5231685b72312c5a1a1b7639ad66a9652aa84/mmh3-5.2.1-cp311-cp311-win_arm64.whl", hash = "sha256:c302245fd6c33d96bd169c7ccf2513c20f4c1e417c07ce9dce107c8bc3f8411f", size = 39287, upload-time = "2026-03-05T15:54:20.904Z" },
    { url = "https://files.pythonhosted.org/packages/92/94/bc5c3b573b40a328c4d141c20e399039ada95e5e2a661df3425c5165fd84/mmh3-5.2.1-cp312-cp312-macosx_10_13_universal2.whl", hash = "sha256:0cc21533878e5586b80d74c281d7f8da7932bc8ace50b8d5f6dbf7e3935f63f1", size = 56087, upload-time = "2026-03-05T15:54:21.92Z" },
    { url = "https://files.pythonhosted.org/packages/f6/80/64a02cc3e95c3af0aaa2590849d9ed24a9f14bb93537addde688e039b7c3/mmh3-5.2.1-cp312-cp312-macosx_10_13_x86_64.whl", hash = "sha256:4eda76074cfca2787c8cf1bec603eaebdddd8b061ad5502f85cddae998d54f00", size = 40500, upload-time = "2026-03-05T15:54:22.953Z" },
    { url = "https://files.pythonhosted.org/packages/8b/72/e6d6602ce18adf4ddcd0e48f2e13590cc92a536199e52109f46f259d3c46/mmh3-5.2.1-cp312-cp312-macosx_11_0_arm64.whl", hash = "sha256:eee884572b06bbe8a2b54f424dbd996139442cf83c76478e1ec162512e0dd2c7", size = 40034, upload-time = "2026-03-05T15:54:23.943Z" },
    { url = "https://files.pythonhosted.org/packages/59/c2/bf4537a8e58e21886ef16477041238cab5095c836496e19fafc34b7445d2/mmh3-5.2.1-cp312-cp312-manylinux1_i686.manylinux_2_28_i686.manylinux_2_5_i686.whl", hash = "sha256:0d0b7e803191db5f714d264044e06189c8ccd3219e936cc184f07106bd17fd7b", size = 97292, upload-time = "2026-03-05T15:54:25.335Z" },
    { url = "https://files.pythonhosted.org/packages/e5/e2/51ed62063b44d10b06d975ac87af287729eeb5e3ed9772f7584a17983e90/mmh3-5.2.1-cp312-cp312-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:8e6c219e375f6341d0959af814296372d265a8ca1af63825f65e2e87c618f006", size = 103274, upload-time = "2026-03-05T15:54:26.44Z" },
    { url = "https://files.pythonhosted.org/packages/75/ce/12a7524dca59eec92e5b31fdb13ede1e98eda277cf2b786cf73bfbc24e81/mmh3-5.2.1-cp312-cp312-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:26fb5b9c3946bf7f1daed7b37e0c03898a6f062149127570f8ede346390a0825", size = 106158, upload-time = "2026-03-05T15:54:28.578Z" },
    { url = "https://files.pythonhosted.org/packages/86/1f/d3ba6dd322d01ab5d44c46c8f0c38ab6bbbf9b5e20e666dfc05bf4a23604/mmh3-5.2.1-cp312-cp312-manylinux2014_ppc64le.manylinux_2_17_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:3c38d142c706201db5b2345166eeef1e7740e3e2422b470b8ba5c8727a9b4c7a", size = 113005, upload-time = "2026-03-05T15:54:29.767Z" },
    { url = "https://files.pythonhosted.org/packages/b6/a9/15d6b6f913294ea41b44d901741298e3718e1cb89ee626b3694625826a43/mmh3-5.2.1-cp312-cp312-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:50885073e2909251d4718634a191c49ae5f527e5e1736d738e365c3e8be8f22b", size = 120744, upload-time = "2026-03-05T15:54:30.931Z" },
    { url = "https://files.pythonhosted.org/packages/76/b3/70b73923fd0284c439860ff5c871b20210dfdbe9a6b9dd0ee6496d77f174/mmh3-5.2.1-cp312-cp312-musllinux_1_2_aarch64.whl", hash = "sha256:b3f99e1756fc48ad507b95e5d86f2fb21b3d495012ff13e6592ebac14033f166", size = 99111, upload-time = "2026-03-05T15:54:32.353Z" },
    { url = "https://files.pythonhosted.org/packages/dd/38/99f7f75cd27d10d8b899a1caafb9d531f3903e4d54d572220e3d8ac35e89/mmh3-5.2.1-cp312-cp312-musllinux_1_2_i686.whl", hash = "sha256:62815d2c67f2dd1be76a253d88af4e1da19aeaa1820146dec52cf8bee2958b16", size = 98623, upload-time = "2026-03-05T15:54:33.801Z" },
    { url = "https://files.pythonhosted.org/packages/fd/68/6e292c0853e204c44d2f03ea5f090be3317a0e2d9417ecb62c9eb27687df/mmh3-5.2.1-cp312-cp312-musllinux_1_2_ppc64le.whl", hash = "sha256:8f767ba0911602ddef289404e33835a61168314ebd3c729833db2ed685824211", size = 106437, upload-time = "2026-03-05T15:54:35.177Z" },
    { url = "https://files.pythonhosted.org/packages/dd/c6/fedd7284c459cfb58721d461fcf5607a4c1f5d9ab195d113d51d10164d16/mmh3-5.2.1-cp312-cp312-musllinux_1_2_s390x.whl", hash = "sha256:67e41a497bac88cc1de96eeba56eeb933c39d54bc227352f8455aa87c4ca4000", size = 110002, upload-time = "2026-03-05T15:54:36.673Z" },
    { url = "https://files.pythonhosted.org/packages/3b/ac/ca8e0c19a34f5b71390171d2ff0b9f7f187550d66801a731bb68925126a4/mmh3-5.2.1-cp312-cp312-musllinux_1_2_x86_64.whl", hash = "sha256:3d74a03fb57757ece25aa4b3c1c60157a1cece37a020542785f942e2f827eed5", size = 97507, upload-time = "2026-03-05T15:54:37.804Z" },
    { url = "https://files.pythonhosted.org/packages/df/94/6ebb9094cfc7ac5e7950776b9d13a66bb4a34f83814f32ba2abc9494fc68/mmh3-5.2.1-cp312-cp312-win32.whl", hash = "sha256:7374d6e3ef72afe49697ecd683f3da12f4fc06af2d75433d0580c6746d2fa025", size = 40773, upload-time = "2026-03-05T15:54:40.077Z" },
    { url = "https://files.pythonhosted.org/packages/5b/3c/cd3527198cf159495966551c84a5f36805a10ac17b294f41f67b83f6a4d6/mmh3-5.2.1-cp312-cp312-win_amd64.whl", hash = "sha256:3a9fed49c6ce4ed7e73f13182760c65c816da006debe67f37635580dfb0fae00", size = 41560, upload-time = "2026-03-05T15:54:41.148Z" },
    { url = "https://files.pythonhosted.org/packages/15/96/6fe5ebd0f970a076e3ed5512871ce7569447b962e96c125528a2f9724470/mmh3-5.2.1-cp312-cp312-win_arm64.whl", hash = "sha256:bbfcb95d9a744e6e2827dfc66ad10e1020e0cac255eb7f85652832d5a264c2fc", size = 39313, upload-time = "2026-03-05T15:54:42.171Z" },
    { url = "https://files.pythonhosted.org/packages/25/a5/9daa0508a1569a54130f6198d5462a92deda870043624aa3ea72721aa765/mmh3-5.2.1-cp313-cp313-android_21_arm64_v8a.whl", hash = "sha256:723b2681ed4cc07d3401bbea9c201ad4f2a4ca6ba8cddaff6789f715dd2b391e", size = 40832, upload-time = "2026-03-05T15:54:43.212Z" },
    { url = "https://files.pythonhosted.org/packages/0a/6b/3230c6d80c1f4b766dedf280a92c2241e99f87c1504ff74205ec8cebe451/mmh3-5.2.1-cp313-cp313-android_21_x86_64.whl", hash = "sha256:3619473a0e0d329fd4aec8075628f8f616be2da41605300696206d6f36920c3d", size = 41964, upload-time = "2026-03-05T15:54:44.204Z" },
    { url = "https://files.pythonhosted.org/packages/62/fb/648bfddb74a872004b6ee751551bfdda783fe6d70d2e9723bad84dbe5311/mmh3-5.2.1-cp313-cp313-ios_13_0_arm64_iphoneos.whl", hash = "sha256:e48d4dbe0f88e53081da605ae68644e5182752803bbc2beb228cca7f1c4454d6", size = 39114, upload-time = "2026-03-05T15:54:45.205Z" },
    { url = "https://files.pythonhosted.org/packages/95/c2/ab7901f87af438468b496728d11264cb397b3574d41506e71b92128e0373/mmh3-5.2.1-cp313-cp313-ios_13_0_arm64_iphonesimulator.whl", hash = "sha256:a482ac121de6973897c92c2f31defc6bafb11c83825109275cffce54bb64933f", size = 39819, upload-time = "2026-03-05T15:54:46.509Z" },
    { url = "https://files.pythonhosted.org/packages/2f/ed/6f88dda0df67de1612f2e130ffea34cf84aaee5bff5b0aff4dbff2babe34/mmh3-5.2.1-cp313-cp313-ios_13_0_x86_64_iphonesimulator.whl", hash = "sha256:17fbb47f0885ace8327ce1235d0416dc86a211dcd8cc1e703f41523be32cfec8", size = 40330, upload-time = "2026-03-05T15:54:47.864Z" },
    { url = "https://files.pythonhosted.org/packages/3d/66/7516d23f53cdf90f43fce24ab80c28f45e6851d78b46bef8c02084edf583/mmh3-5.2.1-cp313-cp313-macosx_10_13_universal2.whl", hash = "sha256:d51fde50a77f81330523562e3c2734ffdca9c4c9e9d355478117905e1cfe16c6", size = 56078, upload-time = "2026-03-05T15:54:48.9Z" },
    { url = "https://files.pythonhosted.org/packages/bc/34/4d152fdf4a91a132cb226b671f11c6b796eada9ab78080fb5ce1e95adaab/mmh3-5.2.1-cp313-cp313-macosx_10_13_x86_64.whl", hash = "sha256:19bbd3b841174ae6ed588536ab5e1b1fe83d046e668602c20266547298d939a9", size = 40498, upload-time = "2026-03-05T15:54:49.942Z" },
    { url = "https://files.pythonhosted.org/packages/d4/4c/8e3af1b6d85a299767ec97bd923f12b06267089c1472c27c1696870d1175/mmh3-5.2.1-cp313-cp313-macosx_11_0_arm64.whl", hash = "sha256:be77c402d5e882b6fbacfd90823f13da8e0a69658405a39a569c6b58fdb17b03", size = 40033, upload-time = "2026-03-05T15:54:50.994Z" },
    { url = "https://files.pythonhosted.org/packages/8b/f2/966ea560e32578d453c9e9db53d602cbb1d0da27317e232afa7c38ceba11/mmh3-5.2.1-cp313-cp313-manylinux1_i686.manylinux_2_28_i686.manylinux_2_5_i686.whl", hash = "sha256:fd96476f04db5ceba1cfa0f21228f67c1f7402296f0e73fee3513aa680ad237b", size = 97320, upload-time = "2026-03-05T15:54:52.072Z" },
    { url = "https://files.pythonhosted.org/packages/bb/0d/2c5f9893b38aeb6b034d1a44ecd55a010148054f6a516abe53b5e4057297/mmh3-5.2.1-cp313-cp313-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:707151644085dd0f20fe4f4b573d28e5130c4aaa5f587e95b60989c5926653b5", size = 103299, upload-time = "2026-03-05T15:54:53.569Z" },
    { url = "https://files.pythonhosted.org/packages/1c/fc/2ebaef4a4d4376f89761274dc274035ffd96006ab496b4ee5af9b08f21a9/mmh3-5.2.1-cp313-cp313-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:3737303ca9ea0f7cb83028781148fcda4f1dac7821db0c47672971dabcf63593", size = 106222, upload-time = "2026-03-05T15:54:55.092Z" },
    { url = "https://files.pythonhosted.org/packages/57/09/ea7ffe126d0ba0406622602a2d05e1e1a6841cc92fc322eb576c95b27fad/mmh3-5.2.1-cp313-cp313-manylinux2014_ppc64le.manylinux_2_17_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:2778fed822d7db23ac5008b181441af0c869455b2e7d001f4019636ac31b6fe4", size = 113048, upload-time = "2026-03-05T15:54:56.305Z" },
    { url = "https://files.pythonhosted.org/packages/85/57/9447032edf93a64aa9bef4d9aa596400b1756f40411890f77a284f6293ca/mmh3-5.2.1-cp313-cp313-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:d57dea657357230cc780e13920d7fa7db059d58fe721c80020f94476da4ca0a1", size = 120742, upload-time = "2026-03-05T15:54:57.453Z" },
    { url = "https://files.pythonhosted.org/packages/53/82/a86cc87cc88c92e9e1a598fee509f0409435b57879a6129bf3b3e40513c7/mmh3-5.2.1-cp313-cp313-musllinux_1_2_aarch64.whl", hash = "sha256:169e0d178cb59314456ab30772429a802b25d13227088085b0d49b9fe1533104", size = 99132, upload-time = "2026-03-05T15:54:58.583Z" },
    { url = "https://files.pythonhosted.org/packages/54/f7/6b16eb1b40ee89bb740698735574536bc20d6cdafc65ae702ea235578e05/mmh3-5.2.1-cp313-cp313-musllinux_1_2_i686.whl", hash = "sha256:7e4e1f580033335c6f76d1e0d6b56baf009d1a64d6a4816347e4271ba951f46d", size = 98686, upload-time = "2026-03-05T15:55:00.078Z" },
    { url = "https://files.pythonhosted.org/packages/e8/88/a601e9f32ad1410f438a6d0544298ea621f989bd34a0731a7190f7dec799/mmh3-5.2.1-cp313-cp313-musllinux_1_2_ppc64le.whl", hash = "sha256:2bd9f19f7f1fcebd74e830f4af0f28adad4975d40d80620be19ffb2b2af56c9f", size = 106479, upload-time = "2026-03-05T15:55:01.532Z" },
    { url = "https://files.pythonhosted.org/packages/d6/5c/ce29ae3dfc4feec4007a437a1b7435fb9507532a25147602cd5b52be86db/mmh3-5.2.1-cp313-cp313-musllinux_1_2_s390x.whl", hash = "sha256:c88653877aeb514c089d1b3d473451677b8b9a6d1497dbddf1ae7934518b06d2", size = 110030, upload-time = "2026-03-05T15:55:02.934Z" },
    { url = "https://files.pythonhosted.org/packages/13/30/ae444ef2ff87c805d525da4fa63d27cda4fe8a48e77003a036b8461cfd5c/mmh3-5.2.1-cp313-cp313-musllinux_1_2_x86_64.whl", hash = "sha256:fceef7fe67c81e1585198215e42ad3fdba3a25644beda8fbdaf85f4d7b93175a", size = 97536, upload-time = "2026-03-05T15:55:04.135Z" },
    { url = "https://files.pythonhosted.org/packages/4b/f9/dc3787ee5c813cc27fe79f45ad4500d9b5437f23a7402435cc34e07c7718/mmh3-5.2.1-cp313-cp313-win32.whl", hash = "sha256:54b64fb2433bc71488e7a449603bf8bd31fbcf9cb56fbe1eb6d459e90b86c37b", size = 40769, upload-time = "2026-03-05T15:55:05.277Z" },
    { url = "https://files.pythonhosted.org/packages/43/67/850e0b5a1e97799822ebfc4ca0e8c6ece3ed8baf7dcdf64de817dfdda2ca/mmh3-5.2.1-cp313-cp313-win_amd64.whl", hash = "sha256:cae6383181f1e345317742d2ddd88f9e7d2682fa4c9432e3a74e47d92dce0229", size = 41563, upload-time = "2026-03-05T15:55:06.283Z" },
    { url = "https://files.pythonhosted.org/packages/c0/cc/98c90b28e1da5458e19fbfaf4adb5289208d3bfccd45dd14eab216a2f0bb/mmh3-5.2.1-cp313-cp313-win_arm64.whl", hash = "sha256:022aa1a528604e6c83d0a7705fdef0b5355d897a9e0fa3a8d26709ceaa06965d", size = 39310, upload-time = "2026-03-05T15:55:07.323Z" },
    { url = "https://files.pythonhosted.org/packages/63/b4/65bc1fb2bb7f83e91c30865023b1847cf89a5f237165575e8c83aa536584/mmh3-5.2.1-cp314-cp314-android_24_arm64_v8a.whl", hash = "sha256:d771f085fcdf4035786adfb1d8db026df1eb4b41dac1c3d070d1e49512843227", size = 40794, upload-time = "2026-03-05T15:55:09.773Z" },
    { url = "https://files.pythonhosted.org/packages/c4/86/7168b3d83be8eb553897b1fac9da8bbb06568e5cfe555ffc329ebb46f59d/mmh3-5.2.1-cp314-cp314-android_24_x86_64.whl", hash = "sha256:7f196cd7910d71e9d9860da0ff7a77f64d22c1ad931f1dd18559a06e03109fc0", size = 41923, upload-time = "2026-03-05T15:55:10.924Z" },
    { url = "https://files.pythonhosted.org/packages/bf/9b/b653ab611c9060ce8ff0ba25c0226757755725e789292f3ca138a58082cd/mmh3-5.2.1-cp314-cp314-ios_13_0_arm64_iphoneos.whl", hash = "sha256:b1f12bd684887a0a5d55e6363ca87056f361e45451105012d329b86ec19dbe0b", size = 39131, upload-time = "2026-03-05T15:55:11.961Z" },
    { url = "https://files.pythonhosted.org/packages/9b/b4/5a2e0d34ab4d33543f01121e832395ea510132ea8e52cdf63926d9d81754/mmh3-5.2.1-cp314-cp314-ios_13_0_arm64_iphonesimulator.whl", hash = "sha256:d106493a60dcb4aef35a0fac85105e150a11cf8bc2b0d388f5a33272d756c966", size = 39825, upload-time = "2026-03-05T15:55:13.013Z" },
    { url = "https://files.pythonhosted.org/packages/bd/69/81699a8f39a3f8d368bec6443435c0c392df0d200ad915bf0d222b588e03/mmh3-5.2.1-cp314-cp314-ios_13_0_x86_64_iphonesimulator.whl", hash = "sha256:44983e45310ee5b9f73397350251cdf6e63a466406a105f1d16cb5baa659270b", size = 40344, upload-time = "2026-03-05T15:55:14.026Z" },
    { url = "https://files.pythonhosted.org/packages/0c/b3/71c8c775807606e8fd8acc5c69016e1caf3200d50b50b6dd4b40ce10b76c/mmh3-5.2.1-cp314-cp314-macosx_10_15_universal2.whl", hash = "sha256:368625fb01666655985391dbad3860dc0ba7c0d6b9125819f3121ee7292b4ac8", size = 56291, upload-time = "2026-03-05T15:55:15.137Z" },
    { url = "https://files.pythonhosted.org/packages/6f/75/2c24517d4b2ce9e4917362d24f274d3d541346af764430249ddcc4cb3a08/mmh3-5.2.1-cp314-cp314-macosx_10_15_x86_64.whl", hash = "sha256:72d1cc63bcc91e14933f77d51b3df899d6a07d184ec515ea7f56bff659e124d7", size = 40575, upload-time = "2026-03-05T15:55:16.518Z" },
    { url = "https://files.pythonhosted.org/packages/bf/b9/e4a360164365ac9f07a25f0f7928e3a66eb9ecc989384060747aa170e6aa/mmh3-5.2.1-cp314-cp314-macosx_11_0_arm64.whl", hash = "sha256:e8b4b5580280b9265af3e0409974fb79c64cf7523632d03fbf11df18f8b0181e", size = 40052, upload-time = "2026-03-05T15:55:17.735Z" },
    { url = "https://files.pythonhosted.org/packages/97/ca/120d92223a7546131bbbc31c9174168ee7a73b1366f5463ffe69d9e691fe/mmh3-5.2.1-cp314-cp314-manylinux1_i686.manylinux_2_28_i686.manylinux_2_5_i686.whl", hash = "sha256:4cbbde66f1183db040daede83dd86c06d663c5bb2af6de1142b7c8c37923dd74", size = 97311, upload-time = "2026-03-05T15:55:18.959Z" },
    { url = "https://files.pythonhosted.org/packages/b6/71/c1a60c1652b8813ef9de6d289784847355417ee0f2980bca002fe87f4ae5/mmh3-5.2.1-cp314-cp314-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:8ff038d52ef6aa0f309feeba00c5095c9118d0abf787e8e8454d6048db2037fc", size = 103279, upload-time = "2026-03-05T15:55:20.448Z" },
    { url = "https://files.pythonhosted.org/packages/48/29/ad97f4be1509cdcb28ae32c15593ce7c415db47ace37f8fad35b493faa9a/mmh3-5.2.1-cp314-cp314-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:a4130d0b9ce5fad6af07421b1aecc7e079519f70d6c05729ab871794eded8617", size = 106290, upload-time = "2026-03-05T15:55:21.6Z" },
    { url = "https://files.pythonhosted.org/packages/77/29/1f86d22e281bd8827ba373600a4a8b0c0eae5ca6aa55b9a8c26d2a34decc/mmh3-5.2.1-cp314-cp314-manylinux2014_ppc64le.manylinux_2_17_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:f6e0bfe77d238308839699944164b96a2eeccaf55f2af400f54dc20669d8d5f2", size = 113116, upload-time = "2026-03-05T15:55:22.826Z" },
    { url = "https://files.pythonhosted.org/packages/a7/7c/339971ea7ed4c12d98f421f13db3ea576a9114082ccb59d2d1a0f00ccac1/mmh3-5.2.1-cp314-cp314-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:f963eafc0a77a6c0562397da004f5876a9bcf7265a7bcc3205e29636bc4a1312", size = 120740, upload-time = "2026-03-05T15:55:24.3Z" },
    { url = "https://files.pythonhosted.org/packages/e4/92/3c7c4bdb8e926bb3c972d1e2907d77960c1c4b250b41e8366cf20c6e4373/mmh3-5.2.1-cp314-cp314-musllinux_1_2_aarch64.whl", hash = "sha256:92883836caf50d5255be03d988d75bc93e3f86ba247b7ca137347c323f731deb", size = 99143, upload-time = "2026-03-05T15:55:25.456Z" },
    { url = "https://files.pythonhosted.org/packages/df/0a/33dd8706e732458c8375eae63c981292de07a406bad4ec03e5269654aa2c/mmh3-5.2.1-cp314-cp314-musllinux_1_2_i686.whl", hash = "sha256:57b52603e89355ff318025dd55158f6e71396c0f1f609d548e9ea9c94cc6ce0a", size = 98703, upload-time = "2026-03-05T15:55:26.723Z" },
    { url = "https://files.pythonhosted.org/packages/51/04/76bbce05df76cbc3d396f13b2ea5b1578ef02b6a5187e132c6c33f99d596/mmh3-5.2.1-cp314-cp314-musllinux_1_2_ppc64le.whl", hash = "sha256:f40a95186a72fa0b67d15fef0f157bfcda00b4f59c8a07cbe5530d41ac35d105", size = 106484, upload-time = "2026-03-05T15:55:28.214Z" },
    { url = "https://files.pythonhosted.org/packages/d3/8f/c6e204a2c70b719c1f62ffd9da27aef2dddcba875ea9c31ca0e87b975a46/mmh3-5.2.1-cp314-cp314-musllinux_1_2_s390x.whl", hash = "sha256:58370d05d033ee97224c81263af123dea3d931025030fd34b61227a768a8858a", size = 110012, upload-time = "2026-03-05T15:55:29.532Z" },
    { url = "https://files.pythonhosted.org/packages/e3/37/7181efd8e39db386c1ebc3e6b7d1f702a09d7c1197a6f2742ed6b5c16597/mmh3-5.2.1-cp314-cp314-musllinux_1_2_x86_64.whl", hash = "sha256:7be6dfb49e48fd0a7d91ff758a2b51336f1cd21f9d44b20f6801f072bd080cdd", size = 97508, upload-time = "2026-03-05T15:55:31.01Z" },
    { url = "https://files.pythonhosted.org/packages/42/0f/afa7ca2615fd85e1469474bb860e381443d0b868c083b62b41cb1d7ca32f/mmh3-5.2.1-cp314-cp314-win32.whl", hash = "sha256:54fe8518abe06a4c3852754bfd498b30cc58e667f376c513eac89a244ce781a4", size = 41387, upload-time = "2026-03-05T15:55:32.403Z" },
    { url = "https://files.pythonhosted.org/packages/71/0d/46d42a260ee1357db3d486e6c7a692e303c017968e14865e00efa10d09fc/mmh3-5.2.1-cp314-cp314-win_amd64.whl", hash = "sha256:3f796b535008708846044c43302719c6956f39ca2d93f2edda5319e79a29efbb", size = 42101, upload-time = "2026-03-05T15:55:33.646Z" },
    { url = "https://files.pythonhosted.org/packages/a4/7b/848a8378059d96501a41159fca90d6a99e89736b0afbe8e8edffeac8c74b/mmh3-5.2.1-cp314-cp314-win_arm64.whl", hash = "sha256:cd471ede0d802dd936b6fab28188302b2d497f68436025857ca72cd3810423fe", size = 39836, upload-time = "2026-03-05T15:55:35.026Z" },
    { url = "https://files.pythonhosted.org/packages/27/61/1dabea76c011ba8547c25d30c91c0ec22544487a8750997a27a0c9e1180b/mmh3-5.2.1-cp314-cp314t-macosx_10_15_universal2.whl", hash = "sha256:5174a697ce042fa77c407e05efe41e03aa56dae9ec67388055820fb48cf4c3ba", size = 57727, upload-time = "2026-03-05T15:55:36.162Z" },
    { url = "https://files.pythonhosted.org/packages/b7/32/731185950d1cf2d5e28979cc8593016ba1619a295faba10dda664a4931b5/mmh3-5.2.1-cp314-cp314t-macosx_10_15_x86_64.whl", hash = "sha256:0a3984146e414684a6be2862d84fcb1035f4984851cb81b26d933bab6119bf00", size = 41308, upload-time = "2026-03-05T15:55:37.254Z" },
    { url = "https://files.pythonhosted.org/packages/76/aa/66c76801c24b8c9418b4edde9b5e57c75e72c94e29c48f707e3962534f18/mmh3-5.2.1-cp314-cp314t-macosx_11_0_arm64.whl", hash = "sha256:bd6e7d363aa93bd3421b30b6af97064daf47bc96005bddba67c5ffbc6df426b8", size = 40758, upload-time = "2026-03-05T15:55:38.61Z" },
    { url = "https://files.pythonhosted.org/packages/9e/bb/79a1f638a02f0ae389f706d13891e2fbf7d8c0a22ecde67ba828951bb60a/mmh3-5.2.1-cp314-cp314t-manylinux1_i686.manylinux_2_28_i686.manylinux_2_5_i686.whl", hash = "sha256:113f78e7463a36dbbcea05bfe688efd7fa759d0f0c56e73c974d60dcfec3dfcc", size = 109670, upload-time = "2026-03-05T15:55:40.13Z" },
    { url = "https://files.pythonhosted.org/packages/26/94/8cd0e187a288985bcfc79bf5144d1d712df9dee74365f59d26e3a1865be6/mmh3-5.2.1-cp314-cp314t-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:7e8ec5f606e0809426d2440e0683509fb605a8820a21ebd120dcdba61b74ef7f", size = 117399, upload-time = "2026-03-05T15:55:42.076Z" },
    { url = "https://files.pythonhosted.org/packages/42/94/dfea6059bd5c5beda565f58a4096e43f4858fb6d2862806b8bbd12cbb284/mmh3-5.2.1-cp314-cp314t-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:22b0f9971ec4e07e8223f2beebe96a6cfc779d940b6f27d26604040dd74d3a44", size = 120386, upload-time = "2026-03-05T15:55:43.481Z" },
    { url = "https://files.pythonhosted.org/packages/47/cb/f9c45e62aaa67220179f487772461d891bb582bb2f9783c944832c60efd9/mmh3-5.2.1-cp314-cp314t-manylinux2014_ppc64le.manylinux_2_17_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:85ffc9920ffc39c5eee1e3ac9100c913a0973996fbad5111f939bbda49204bb7", size = 125924, upload-time = "2026-03-05T15:55:44.638Z" },
    { url = "https://files.pythonhosted.org/packages/a5/83/fe54a4a7c11bc9f623dfc1707decd034245602b076dfc1dcc771a4163170/mmh3-5.2.1-cp314-cp314t-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:7aec798c2b01aaa65a55f1124f3405804184373abb318a3091325aece235f67c", size = 135280, upload-time = "2026-03-05T15:55:45.866Z" },
    { url = "https://files.pythonhosted.org/packages/97/67/fe7e9e9c143daddd210cd22aef89cbc425d58ecf238d2b7d9eb0da974105/mmh3-5.2.1-cp314-cp314t-musllinux_1_2_aarch64.whl", hash = "sha256:55dbbd8ffbc40d1697d5e2d0375b08599dae8746b0b08dea05eee4ce81648fac", size = 110050, upload-time = "2026-03-05T15:55:47.074Z" },
    { url = "https://files.pythonhosted.org/packages/43/c4/6d4b09fcbef80794de447c9378e39eefc047156b290fa3dd2d5257ca8227/mmh3-5.2.1-cp314-cp314t-musllinux_1_2_i686.whl", hash = "sha256:6c85c38a279ca9295a69b9b088a2e48aa49737bb1b34e6a9dc6297c110e8d912", size = 111158, upload-time = "2026-03-05T15:55:48.239Z" },
    { url = "https://files.pythonhosted.org/packages/81/a6/ca51c864bdb30524beb055a6d8826db3906af0834ec8c41d097a6e8573d5/mmh3-5.2.1-cp314-cp314t-musllinux_1_2_ppc64le.whl", hash = "sha256:6290289fa5fb4c70fd7f72016e03633d60388185483ff3b162912c81205ae2cf", size = 116890, upload-time = "2026-03-05T15:55:49.405Z" },
    { url = "https://files.pythonhosted.org/packages/cc/04/5a1fe2e2ad843d03e89af25238cbc4f6840a8bb6c4329a98ab694c71deda/mmh3-5.2.1-cp314-cp314t-musllinux_1_2_s390x.whl", hash = "sha256:4fc6cd65dc4d2fdb2625e288939a3566e36127a84811a4913f02f3d5931da52d", size = 123121, upload-time = "2026-03-05T15:55:50.61Z" },
    { url = "https://files.pythonhosted.org/packages/af/4d/3c820c6f4897afd25905270a9f2330a23f77a207ea7356f7aadace7273c0/mmh3-5.2.1-cp314-cp314t-musllinux_1_2_x86_64.whl", hash = "sha256:623f938f6a039536cc02b7582a07a080f13fdfd48f87e63201d92d7e34d09a18", size = 110187, upload-time = "2026-03-05T15:55:52.143Z" },
    { url = "https://files.pythonhosted.org/packages/21/54/1d71cd143752361c0aebef16ad3f55926a6faf7b112d355745c1f8a25f7f/mmh3-5.2.1-cp314-cp314t-win32.whl", hash = "sha256:29bc3973676ae334412efdd367fcd11d036b7be3efc1ce2407ef8676dabfeb82", size = 41934, upload-time = "2026-03-05T15:55:53.564Z" },
    { url = "https://files.pythonhosted.org/packages/9d/e4/63a2a88f31d93dea03947cccc2a076946857e799ea4f7acdecbf43b324aa/mmh3-5.2.1-cp314-cp314t-win_amd64.whl", hash = "sha256:28cfab66577000b9505a0d068c731aee7ca85cd26d4d63881fab17857e0fe1fb", size = 43036, upload-time = "2026-03-05T15:55:55.252Z" },
    { url = "https://files.pythonhosted.org/packages/a0/0f/59204bf136d1201f8d7884cfbaf7498c5b4674e87a4c693f9bde63741ce1/mmh3-5.2.1-cp314-cp314t-win_arm64.whl", hash = "sha256:dfd51b4c56b673dfbc43d7d27ef857dd91124801e2806c69bb45585ce0fa019b", size = 40391, upload-time = "2026-03-05T15:55:56.697Z" },
]

[[package]]
name = "mpmath"
version = "1.3.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/e0/47/dd32fa426cc72114383ac549964eecb20ecfd886d1e5ccf5340b55b02f57/mpmath-1.3.0.tar.gz", hash = "sha256:7a28eb2a9774d00c7bc92411c19a89209d5da7c4c9a9e227be8330a23a25b91f", size = 508106, upload-time = "2023-03-07T16:47:11.061Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/43/e3/7d92a15f894aa0c9c4b49b8ee9ac9850d6e63b03c9c32c0367a13ae62209/mpmath-1.3.0-py3-none-any.whl", hash = "sha256:a0b2b9fe80bbcd81a6647ff13108738cfb482d481d826cc0e02f5b35e5c88d2c", size = 536198, upload-time = "2023-03-07T16:47:09.197Z" },
]

[[package]]
name = "numpy"
version = "2.4.4"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/d7/9f/b8cef5bffa569759033adda9481211426f12f53299629b410340795c2514/numpy-2.4.4.tar.gz", hash = "sha256:2d390634c5182175533585cc89f3608a4682ccb173cc9bb940b2881c8d6f8fa0", size = 20731587, upload-time = "2026-03-29T13:22:01.298Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/ef/c6/4218570d8c8ecc9704b5157a3348e486e84ef4be0ed3e38218ab473c83d2/numpy-2.4.4-cp311-cp311-macosx_10_9_x86_64.whl", hash = "sha256:f983334aea213c99992053ede6168500e5f086ce74fbc4acc3f2b00f5762e9db", size = 16976799, upload-time = "2026-03-29T13:18:15.438Z" },
    { url = "https://files.pythonhosted.org/packages/dd/92/b4d922c4a5f5dab9ed44e6153908a5c665b71acf183a83b93b690996e39b/numpy-2.4.4-cp311-cp311-macosx_11_0_arm64.whl", hash = "sha256:72944b19f2324114e9dc86a159787333b77874143efcf89a5167ef83cfee8af0", size = 14971552, upload-time = "2026-03-29T13:18:18.606Z" },
    { url = "https://files.pythonhosted.org/packages/8a/dc/df98c095978fa6ee7b9a9387d1d58cbb3d232d0e69ad169a4ce784bde4fd/numpy-2.4.4-cp311-cp311-macosx_14_0_arm64.whl", hash = "sha256:86b6f55f5a352b48d7fbfd2dbc3d5b780b2d79f4d3c121f33eb6efb22e9a2015", size = 5476566, upload-time = "2026-03-29T13:18:21.532Z" },
    { url = "https://files.pythonhosted.org/packages/28/34/b3fdcec6e725409223dd27356bdf5a3c2cc2282e428218ecc9cb7acc9763/numpy-2.4.4-cp311-cp311-macosx_14_0_x86_64.whl", hash = "sha256:ba1f4fc670ed79f876f70082eff4f9583c15fb9a4b89d6188412de4d18ae2f40", size = 6806482, upload-time = "2026-03-29T13:18:23.634Z" },
    { url = "https://files.pythonhosted.org/packages/68/62/63417c13aa35d57bee1337c67446761dc25ea6543130cf868eace6e8157b/numpy-2.4.4-cp311-cp311-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:8a87ec22c87be071b6bdbd27920b129b94f2fc964358ce38f3822635a3e2e03d", size = 15973376, upload-time = "2026-03-29T13:18:26.677Z" },
    { url = "https://files.pythonhosted.org/packages/cf/c5/9fcb7e0e69cef59cf10c746b84f7d58b08bc66a6b7d459783c5a4f6101a6/numpy-2.4.4-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:df3775294accfdd75f32c74ae39fcba920c9a378a2fc18a12b6820aa8c1fb502", size = 16925137, upload-time = "2026-03-29T13:18:30.14Z" },
    { url = "https://files.pythonhosted.org/packages/7e/43/80020edacb3f84b9efdd1591120a4296462c23fd8db0dde1666f6ef66f13/numpy-2.4.4-cp311-cp311-musllinux_1_2_aarch64.whl", hash = "sha256:0d4e437e295f18ec29bc79daf55e8a47a9113df44d66f702f02a293d93a2d6dd", size = 17329414, upload-time = "2026-03-29T13:18:33.733Z" },
    { url = "https://files.pythonhosted.org/packages/fd/06/af0658593b18a5f73532d377188b964f239eb0894e664a6c12f484472f97/numpy-2.4.4-cp311-cp311-musllinux_1_2_x86_64.whl", hash = "sha256:6aa3236c78803afbcb255045fbef97a9e25a1f6c9888357d205ddc42f4d6eba5", size = 18658397, upload-time = "2026-03-29T13:18:37.511Z" },
    { url = "https://files.pythonhosted.org/packages/e6/ce/13a09ed65f5d0ce5c7dd0669250374c6e379910f97af2c08c57b0608eee4/numpy-2.4.4-cp311-cp311-win32.whl", hash = "sha256:30caa73029a225b2d40d9fae193e008e24b2026b7ee1a867b7ee8d96ca1a448e", size = 6239499, upload-time = "2026-03-29T13:18:40.372Z" },
    { url = "https://files.pythonhosted.org/packages/bd/63/05d193dbb4b5eec1eca73822d80da98b511f8328ad4ae3ca4caf0f4db91d/numpy-2.4.4-cp311-cp311-win_amd64.whl", hash = "sha256:6bbe4eb67390b0a0265a2c25458f6b90a409d5d069f1041e6aff1e27e3d9a79e", size = 12614257, upload-time = "2026-03-29T13:18:42.95Z" },
    { url = "https://files.pythonhosted.org/packages/87/c5/8168052f080c26fa984c413305012be54741c9d0d74abd7fbeeccae3889f/numpy-2.4.4-cp311-cp311-win_arm64.whl", hash = "sha256:fcfe2045fd2e8f3cb0ce9d4ba6dba6333b8fa05bb8a4939c908cd43322d14c7e", size = 10486775, upload-time = "2026-03-29T13:18:45.835Z" },
    { url = "https://files.pythonhosted.org/packages/28/05/32396bec30fb2263770ee910142f49c1476d08e8ad41abf8403806b520ce/numpy-2.4.4-cp312-cp312-macosx_10_13_x86_64.whl", hash = "sha256:15716cfef24d3a9762e3acdf87e27f58dc823d1348f765bbea6bef8c639bfa1b", size = 16689272, upload-time = "2026-03-29T13:18:49.223Z" },
    { url = "https://files.pythonhosted.org/packages/c5/f3/a983d28637bfcd763a9c7aafdb6d5c0ebf3d487d1e1459ffdb57e2f01117/numpy-2.4.4-cp312-cp312-macosx_11_0_arm64.whl", hash = "sha256:23cbfd4c17357c81021f21540da84ee282b9c8fba38a03b7b9d09ba6b951421e", size = 14699573, upload-time = "2026-03-29T13:18:52.629Z" },
    { url = "https://files.pythonhosted.org/packages/9b/fd/e5ecca1e78c05106d98028114f5c00d3eddb41207686b2b7de3e477b0e22/numpy-2.4.4-cp312-cp312-macosx_14_0_arm64.whl", hash = "sha256:8b3b60bb7cba2c8c81837661c488637eee696f59a877788a396d33150c35d842", size = 5204782, upload-time = "2026-03-29T13:18:55.579Z" },
    { url = "https://files.pythonhosted.org/packages/de/2f/702a4594413c1a8632092beae8aba00f1d67947389369b3777aed783fdca/numpy-2.4.4-cp312-cp312-macosx_14_0_x86_64.whl", hash = "sha256:e4a010c27ff6f210ff4c6ef34394cd61470d01014439b192ec22552ee867f2a8", size = 6552038, upload-time = "2026-03-29T13:18:57.769Z" },
    { url = "https://files.pythonhosted.org/packages/7f/37/eed308a8f56cba4d1fdf467a4fc67ef4ff4bf1c888f5fc980481890104b1/numpy-2.4.4-cp312-cp312-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:f9e75681b59ddaa5e659898085ae0eaea229d054f2ac0c7e563a62205a700121", size = 15670666, upload-time = "2026-03-29T13:19:00.341Z" },
    { url = "https://files.pythonhosted.org/packages/0a/0d/0e3ecece05b7a7e87ab9fb587855548da437a061326fff64a223b6dcb78a/numpy-2.4.4-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:81f4a14bee47aec54f883e0cad2d73986640c1590eb9bfaaba7ad17394481e6e", size = 16645480, upload-time = "2026-03-29T13:19:03.63Z" },
    { url = "https://files.pythonhosted.org/packages/34/49/f2312c154b82a286758ee2f1743336d50651f8b5195db18cdb63675ff649/numpy-2.4.4-cp312-cp312-musllinux_1_2_aarch64.whl", hash = "sha256:62d6b0f03b694173f9fcb1fb317f7222fd0b0b103e784c6549f5e53a27718c44", size = 17020036, upload-time = "2026-03-29T13:19:07.428Z" },
    { url = "https://files.pythonhosted.org/packages/7b/e9/736d17bd77f1b0ec4f9901aaec129c00d59f5d84d5e79bba540ef12c2330/numpy-2.4.4-cp312-cp312-musllinux_1_2_x86_64.whl", hash = "sha256:fbc356aae7adf9e6336d336b9c8111d390a05df88f1805573ebb0807bd06fd1d", size = 18368643, upload-time = "2026-03-29T13:19:10.775Z" },
    { url = "https://files.pythonhosted.org/packages/63/f6/d417977c5f519b17c8a5c3bc9e8304b0908b0e21136fe43bf628a1343914/numpy-2.4.4-cp312-cp312-win32.whl", hash = "sha256:0d35aea54ad1d420c812bfa0385c71cd7cc5bcf7c65fed95fc2cd02fe8c79827", size = 5961117, upload-time = "2026-03-29T13:19:13.464Z" },
    { url = "https://files.pythonhosted.org/packages/2d/5b/e1deebf88ff431b01b7406ca3583ab2bbb90972bbe1c568732e49c844f7e/numpy-2.4.4-cp312-cp312-win_amd64.whl", hash = "sha256:b5f0362dc928a6ecd9db58868fca5e48485205e3855957bdedea308f8672ea4a", size = 12320584, upload-time = "2026-03-29T13:19:16.155Z" },
    { url = "https://files.pythonhosted.org/packages/58/89/e4e856ac82a68c3ed64486a544977d0e7bdd18b8da75b78a577ca31c4395/numpy-2.4.4-cp312-cp312-win_arm64.whl", hash = "sha256:846300f379b5b12cc769334464656bc882e0735d27d9726568bc932fdc49d5ec", size = 10221450, upload-time = "2026-03-29T13:19:18.994Z" },
    { url = "https://files.pythonhosted.org/packages/14/1d/d0a583ce4fefcc3308806a749a536c201ed6b5ad6e1322e227ee4848979d/numpy-2.4.4-cp313-cp313-macosx_10_13_x86_64.whl", hash = "sha256:08f2e31ed5e6f04b118e49821397f12767934cfdd12a1ce86a058f91e004ee50", size = 16684933, upload-time = "2026-03-29T13:19:22.47Z" },
    { url = "https://files.pythonhosted.org/packages/c1/62/2b7a48fbb745d344742c0277f01286dead15f3f68e4f359fbfcf7b48f70f/numpy-2.4.4-cp313-cp313-macosx_11_0_arm64.whl", hash = "sha256:e823b8b6edc81e747526f70f71a9c0a07ac4e7ad13020aa736bb7c9d67196115", size = 14694532, upload-time = "2026-03-29T13:19:25.581Z" },
    { url = "https://files.pythonhosted.org/packages/e5/87/499737bfba066b4a3bebff24a8f1c5b2dee410b209bc6668c9be692580f0/numpy-2.4.4-cp313-cp313-macosx_14_0_arm64.whl", hash = "sha256:4a19d9dba1a76618dd86b164d608566f393f8ec6ac7c44f0cc879011c45e65af", size = 5199661, upload-time = "2026-03-29T13:19:28.31Z" },
    { url = "https://files.pythonhosted.org/packages/cd/da/464d551604320d1491bc345efed99b4b7034143a85787aab78d5691d5a0e/numpy-2.4.4-cp313-cp313-macosx_14_0_x86_64.whl", hash = "sha256:d2a8490669bfe99a233298348acc2d824d496dee0e66e31b66a6022c2ad74a5c", size = 6547539, upload-time = "2026-03-29T13:19:30.97Z" },
    { url = "https://files.pythonhosted.org/packages/7d/90/8d23e3b0dafd024bf31bdec225b3bb5c2dbfa6912f8a53b8659f21216cbf/numpy-2.4.4-cp313-cp313-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:45dbed2ab436a9e826e302fcdcbe9133f9b0006e5af7168afb8963a6520da103", size = 15668806, upload-time = "2026-03-29T13:19:33.887Z" },
    { url = "https://files.pythonhosted.org/packages/d1/73/a9d864e42a01896bb5974475438f16086be9ba1f0d19d0bb7a07427c4a8b/numpy-2.4.4-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:c901b15172510173f5cb310eae652908340f8dede90fff9e3bf6c0d8dfd92f83", size = 16632682, upload-time = "2026-03-29T13:19:37.336Z" },
    { url = "https://files.pythonhosted.org/packages/34/fb/14570d65c3bde4e202a031210475ae9cde9b7686a2e7dc97ee67d2833b35/numpy-2.4.4-cp313-cp313-musllinux_1_2_aarch64.whl", hash = "sha256:99d838547ace2c4aace6c4f76e879ddfe02bb58a80c1549928477862b7a6d6ed", size = 17019810, upload-time = "2026-03-29T13:19:40.963Z" },
    { url = "https://files.pythonhosted.org/packages/8a/77/2ba9d87081fd41f6d640c83f26fb7351e536b7ce6dd9061b6af5904e8e46/numpy-2.4.4-cp313-cp313-musllinux_1_2_x86_64.whl", hash = "sha256:0aec54fd785890ecca25a6003fd9a5aed47ad607bbac5cd64f836ad8666f4959", size = 18357394, upload-time = "2026-03-29T13:19:44.859Z" },
    { url = "https://files.pythonhosted.org/packages/a2/23/52666c9a41708b0853fa3b1a12c90da38c507a3074883823126d4e9d5b30/numpy-2.4.4-cp313-cp313-win32.whl", hash = "sha256:07077278157d02f65c43b1b26a3886bce886f95d20aabd11f87932750dfb14ed", size = 5959556, upload-time = "2026-03-29T13:19:47.661Z" },
    { url = "https://files.pythonhosted.org/packages/57/fb/48649b4971cde70d817cf97a2a2fdc0b4d8308569f1dd2f2611959d2e0cf/numpy-2.4.4-cp313-cp313-win_amd64.whl", hash = "sha256:5c70f1cc1c4efbe316a572e2d8b9b9cc44e89b95f79ca3331553fbb63716e2bf", size = 12317311, upload-time = "2026-03-29T13:19:50.67Z" },
    { url = "https://files.pythonhosted.org/packages/ba/d8/11490cddd564eb4de97b4579ef6bfe6a736cc07e94c1598590ae25415e01/numpy-2.4.4-cp313-cp313-win_arm64.whl", hash = "sha256:ef4059d6e5152fa1a39f888e344c73fdc926e1b2dd58c771d67b0acfbf2aa67d", size = 10222060, upload-time = "2026-03-29T13:19:54.229Z" },
    { url = "https://files.pythonhosted.org/packages/99/5d/dab4339177a905aad3e2221c915b35202f1ec30d750dd2e5e9d9a72b804b/numpy-2.4.4-cp313-cp313t-macosx_11_0_arm64.whl", hash = "sha256:4bbc7f303d125971f60ec0aaad5e12c62d0d2c925f0ab1273debd0e4ba37aba5", size = 14822302, upload-time = "2026-03-29T13:19:57.585Z" },
    { url = "https://files.pythonhosted.org/packages/eb/e4/0564a65e7d3d97562ed6f9b0fd0fb0a6f559ee444092f105938b50043876/numpy-2.4.4-cp313-cp313t-macosx_14_0_arm64.whl", hash = "sha256:4d6d57903571f86180eb98f8f0c839fa9ebbfb031356d87f1361be91e433f5b7", size = 5327407, upload-time = "2026-03-29T13:20:00.601Z" },
    { url = "https://files.pythonhosted.org/packages/29/8d/35a3a6ce5ad371afa58b4700f1c820f8f279948cca32524e0a695b0ded83/numpy-2.4.4-cp313-cp313t-macosx_14_0_x86_64.whl", hash = "sha256:4636de7fd195197b7535f231b5de9e4b36d2c440b6e566d2e4e4746e6af0ca93", size = 6647631, upload-time = "2026-03-29T13:20:02.855Z" },
    { url = "https://files.pythonhosted.org/packages/f4/da/477731acbd5a58a946c736edfdabb2ac5b34c3d08d1ba1a7b437fa0884df/numpy-2.4.4-cp313-cp313t-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:ad2e2ef14e0b04e544ea2fa0a36463f847f113d314aa02e5b402fdf910ef309e", size = 15727691, upload-time = "2026-03-29T13:20:06.004Z" },
    { url = "https://files.pythonhosted.org/packages/e6/db/338535d9b152beabeb511579598418ba0212ce77cf9718edd70262cc4370/numpy-2.4.4-cp313-cp313t-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:5a285b3b96f951841799528cd1f4f01cd70e7e0204b4abebac9463eecfcf2a40", size = 16681241, upload-time = "2026-03-29T13:20:09.417Z" },
    { url = "https://files.pythonhosted.org/packages/e2/a9/ad248e8f58beb7a0219b413c9c7d8151c5d285f7f946c3e26695bdbbe2df/numpy-2.4.4-cp313-cp313t-musllinux_1_2_aarch64.whl", hash = "sha256:f8474c4241bc18b750be2abea9d7a9ec84f46ef861dbacf86a4f6e043401f79e", size = 17085767, upload-time = "2026-03-29T13:20:13.126Z" },
    { url = "https://files.pythonhosted.org/packages/b5/1a/3b88ccd3694681356f70da841630e4725a7264d6a885c8d442a697e1146b/numpy-2.4.4-cp313-cp313t-musllinux_1_2_x86_64.whl", hash = "sha256:4e874c976154687c1f71715b034739b45c7711bec81db01914770373d125e392", size = 18403169, upload-time = "2026-03-29T13:20:17.096Z" },
    { url = "https://files.pythonhosted.org/packages/c2/c9/fcfd5d0639222c6eac7f304829b04892ef51c96a75d479214d77e3ce6e33/numpy-2.4.4-cp313-cp313t-win32.whl", hash = "sha256:9c585a1790d5436a5374bac930dad6ed244c046ed91b2b2a3634eb2971d21008", size = 6083477, upload-time = "2026-03-29T13:20:20.195Z" },
    { url = "https://files.pythonhosted.org/packages/d5/e3/3938a61d1c538aaec8ed6fd6323f57b0c2d2d2219512434c5c878db76553/numpy-2.4.4-cp313-cp313t-win_amd64.whl", hash = "sha256:93e15038125dc1e5345d9b5b68aa7f996ec33b98118d18c6ca0d0b7d6198b7e8", size = 12457487, upload-time = "2026-03-29T13:20:22.946Z" },
    { url = "https://files.pythonhosted.org/packages/97/6a/7e345032cc60501721ef94e0e30b60f6b0bd601f9174ebd36389a2b86d40/numpy-2.4.4-cp313-cp313t-win_arm64.whl", hash = "sha256:0dfd3f9d3adbe2920b68b5cd3d51444e13a10792ec7154cd0a2f6e74d4ab3233", size = 10292002, upload-time = "2026-03-29T13:20:25.909Z" },
    { url = "https://files.pythonhosted.org/packages/6e/06/c54062f85f673dd5c04cbe2f14c3acb8c8b95e3384869bb8cc9bff8cb9df/numpy-2.4.4-cp314-cp314-macosx_10_15_x86_64.whl", hash = "sha256:f169b9a863d34f5d11b8698ead99febeaa17a13ca044961aa8e2662a6c7766a0", size = 16684353, upload-time = "2026-03-29T13:20:29.504Z" },
    { url = "https://files.pythonhosted.org/packages/4c/39/8a320264a84404c74cc7e79715de85d6130fa07a0898f67fb5cd5bd79908/numpy-2.4.4-cp314-cp314-macosx_11_0_arm64.whl", hash = "sha256:2483e4584a1cb3092da4470b38866634bafb223cbcd551ee047633fd2584599a", size = 14704914, upload-time = "2026-03-29T13:20:33.547Z" },
    { url = "https://files.pythonhosted.org/packages/91/fb/287076b2614e1d1044235f50f03748f31fa287e3dbe6abeb35cdfa351eca/numpy-2.4.4-cp314-cp314-macosx_14_0_arm64.whl", hash = "sha256:2d19e6e2095506d1736b7d80595e0f252d76b89f5e715c35e06e937679ea7d7a", size = 5210005, upload-time = "2026-03-29T13:20:36.45Z" },
    { url = "https://files.pythonhosted.org/packages/63/eb/fcc338595309910de6ecabfcef2419a9ce24399680bfb149421fa2df1280/numpy-2.4.4-cp314-cp314-macosx_14_0_x86_64.whl", hash = "sha256:6a246d5914aa1c820c9443ddcee9c02bec3e203b0c080349533fae17727dfd1b", size = 6544974, upload-time = "2026-03-29T13:20:39.014Z" },
    { url = "https://files.pythonhosted.org/packages/44/5d/e7e9044032a716cdfaa3fba27a8e874bf1c5f1912a1ddd4ed071bf8a14a6/numpy-2.4.4-cp314-cp314-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:989824e9faf85f96ec9c7761cd8d29c531ad857bfa1daa930cba85baaecf1a9a", size = 15684591, upload-time = "2026-03-29T13:20:42.146Z" },
    { url = "https://files.pythonhosted.org/packages/98/7c/21252050676612625449b4807d6b695b9ce8a7c9e1c197ee6216c8a65c7c/numpy-2.4.4-cp314-cp314-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:27a8d92cd10f1382a67d7cf4db7ce18341b66438bdd9f691d7b0e48d104c2a9d", size = 16637700, upload-time = "2026-03-29T13:20:46.204Z" },
    { url = "https://files.pythonhosted.org/packages/b1/29/56d2bbef9465db24ef25393383d761a1af4f446a1df9b8cded4fe3a5a5d7/numpy-2.4.4-cp314-cp314-musllinux_1_2_aarch64.whl", hash = "sha256:e44319a2953c738205bf3354537979eaa3998ed673395b964c1176083dd46252", size = 17035781, upload-time = "2026-03-29T13:20:50.242Z" },
    { url = "https://files.pythonhosted.org/packages/e3/2b/a35a6d7589d21f44cea7d0a98de5ddcbb3d421b2622a5c96b1edf18707c3/numpy-2.4.4-cp314-cp314-musllinux_1_2_x86_64.whl", hash = "sha256:e892aff75639bbef0d2a2cfd55535510df26ff92f63c92cd84ef8d4ba5a5557f", size = 18362959, upload-time = "2026-03-29T13:20:54.019Z" },
    { url = "https://files.pythonhosted.org/packages/64/c9/d52ec581f2390e0f5f85cbfd80fb83d965fc15e9f0e1aec2195faa142cde/numpy-2.4.4-cp314-cp314-win32.whl", hash = "sha256:1378871da56ca8943c2ba674530924bb8ca40cd228358a3b5f302ad60cf875fc", size = 6008768, upload-time = "2026-03-29T13:20:56.912Z" },
    { url = "https://files.pythonhosted.org/packages/fa/22/4cc31a62a6c7b74a8730e31a4274c5dc80e005751e277a2ce38e675e4923/numpy-2.4.4-cp314-cp314-win_amd64.whl", hash = "sha256:715d1c092715954784bc79e1174fc2a90093dc4dc84ea15eb14dad8abdcdeb74", size = 12449181, upload-time = "2026-03-29T13:20:59.548Z" },
    { url = "https://files.pythonhosted.org/packages/70/2e/14cda6f4d8e396c612d1bf97f22958e92148801d7e4f110cabebdc0eef4b/numpy-2.4.4-cp314-cp314-win_arm64.whl", hash = "sha256:2c194dd721e54ecad9ad387c1d35e63dce5c4450c6dc7dd5611283dda239aabb", size = 10496035, upload-time = "2026-03-29T13:21:02.524Z" },
    { url = "https://files.pythonhosted.org/packages/b1/e8/8fed8c8d848d7ecea092dc3469643f9d10bc3a134a815a3b033da1d2039b/numpy-2.4.4-cp314-cp314t-macosx_11_0_arm64.whl", hash = "sha256:2aa0613a5177c264ff5921051a5719d20095ea586ca88cc802c5c218d1c67d3e", size = 14824958, upload-time = "2026-03-29T13:21:05.671Z" },
    { url = "https://files.pythonhosted.org/packages/05/1a/d8007a5138c179c2bf33ef44503e83d70434d2642877ee8fbb230e7c0548/numpy-2.4.4-cp314-cp314t-macosx_14_0_arm64.whl", hash = "sha256:42c16925aa5a02362f986765f9ebabf20de75cdefdca827d14315c568dcab113", size = 5330020, upload-time = "2026-03-29T13:21:08.635Z" },
    { url = "https://files.pythonhosted.org/packages/99/64/ffb99ac6ae93faf117bcbd5c7ba48a7f45364a33e8e458545d3633615dda/numpy-2.4.4-cp314-cp314t-macosx_14_0_x86_64.whl", hash = "sha256:874f200b2a981c647340f841730fc3a2b54c9d940566a3c4149099591e2c4c3d", size = 6650758, upload-time = "2026-03-29T13:21:10.949Z" },
    { url = "https://files.pythonhosted.org/packages/6e/6e/795cc078b78a384052e73b2f6281ff7a700e9bf53bcce2ee579d4f6dd879/numpy-2.4.4-cp314-cp314t-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:c9b39d38a9bd2ae1becd7eac1303d031c5c110ad31f2b319c6e7d98b135c934d", size = 15729948, upload-time = "2026-03-29T13:21:14.047Z" },
    { url = "https://files.pythonhosted.org/packages/5f/86/2acbda8cc2af5f3d7bfc791192863b9e3e19674da7b5e533fded124d1299/numpy-2.4.4-cp314-cp314t-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:b268594bccac7d7cf5844c7732e3f20c50921d94e36d7ec9b79e9857694b1b2f", size = 16679325, upload-time = "2026-03-29T13:21:17.561Z" },
    { url = "https://files.pythonhosted.org/packages/bc/59/cafd83018f4aa55e0ac6fa92aa066c0a1877b77a615ceff1711c260ffae8/numpy-2.4.4-cp314-cp314t-musllinux_1_2_aarch64.whl", hash = "sha256:ac6b31e35612a26483e20750126d30d0941f949426974cace8e6b5c58a3657b0", size = 17084883, upload-time = "2026-03-29T13:21:21.106Z" },
    { url = "https://files.pythonhosted.org/packages/f0/85/a42548db84e65ece46ab2caea3d3f78b416a47af387fcbb47ec28e660dc2/numpy-2.4.4-cp314-cp314t-musllinux_1_2_x86_64.whl", hash = "sha256:8e3ed142f2728df44263aaf5fb1f5b0b99f4070c553a0d7f033be65338329150", size = 18403474, upload-time = "2026-03-29T13:21:24.828Z" },
    { url = "https://files.pythonhosted.org/packages/ed/ad/483d9e262f4b831000062e5d8a45e342166ec8aaa1195264982bca267e62/numpy-2.4.4-cp314-cp314t-win32.whl", hash = "sha256:dddbbd259598d7240b18c9d87c56a9d2fb3b02fe266f49a7c101532e78c1d871", size = 6155500, upload-time = "2026-03-29T13:21:28.205Z" },
    { url = "https://files.pythonhosted.org/packages/c7/03/2fc4e14c7bd4ff2964b74ba90ecb8552540b6315f201df70f137faa5c589/numpy-2.4.4-cp314-cp314t-win_amd64.whl", hash = "sha256:a7164afb23be6e37ad90b2f10426149fd75aee07ca55653d2aa41e66c4ef697e", size = 12637755, upload-time = "2026-03-29T13:21:31.107Z" },
    { url = "https://files.pythonhosted.org/packages/58/78/548fb8e07b1a341746bfbecb32f2c268470f45fa028aacdbd10d9bc73aab/numpy-2.4.4-cp314-cp314t-win_arm64.whl", hash = "sha256:ba203255017337d39f89bdd58417f03c4426f12beed0440cfd933cb15f8669c7", size = 10566643, upload-time = "2026-03-29T13:21:34.339Z" },
    { url = "https://files.pythonhosted.org/packages/6b/33/8fae8f964a4f63ed528264ddf25d2b683d0b663e3cba26961eb838a7c1bd/numpy-2.4.4-pp311-pypy311_pp73-macosx_10_15_x86_64.whl", hash = "sha256:58c8b5929fcb8287cbd6f0a3fae19c6e03a5c48402ae792962ac465224a629a4", size = 16854491, upload-time = "2026-03-29T13:21:38.03Z" },
    { url = "https://files.pythonhosted.org/packages/bc/d0/1aabee441380b981cf8cdda3ae7a46aa827d1b5a8cce84d14598bc94d6d9/numpy-2.4.4-pp311-pypy311_pp73-macosx_11_0_arm64.whl", hash = "sha256:eea7ac5d2dce4189771cedb559c738a71512768210dc4e4753b107a2048b3d0e", size = 14895830, upload-time = "2026-03-29T13:21:41.509Z" },
    { url = "https://files.pythonhosted.org/packages/a5/b8/aafb0d1065416894fccf4df6b49ef22b8db045187949545bced89c034b8e/numpy-2.4.4-pp311-pypy311_pp73-macosx_14_0_arm64.whl", hash = "sha256:51fc224f7ca4d92656d5a5eb315f12eb5fe2c97a66249aa7b5f562528a3be38c", size = 5400927, upload-time = "2026-03-29T13:21:44.747Z" },
    { url = "https://files.pythonhosted.org/packages/d6/77/063baa20b08b431038c7f9ff5435540c7b7265c78cf56012a483019ca72d/numpy-2.4.4-pp311-pypy311_pp73-macosx_14_0_x86_64.whl", hash = "sha256:28a650663f7314afc3e6ec620f44f333c386aad9f6fc472030865dc0ebb26ee3", size = 6715557, upload-time = "2026-03-29T13:21:47.406Z" },
    { url = "https://files.pythonhosted.org/packages/c7/a8/379542d45a14f149444c5c4c4e7714707239ce9cc1de8c2803958889da14/numpy-2.4.4-pp311-pypy311_pp73-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:19710a9ca9992d7174e9c52f643d4272dcd1558c5f7af7f6f8190f633bd651a7", size = 15804253, upload-time = "2026-03-29T13:21:50.753Z" },
    { url = "https://files.pythonhosted.org/packages/a2/c8/f0a45426d6d21e7ea3310a15cf90c43a14d9232c31a837702dba437f3373/numpy-2.4.4-pp311-pypy311_pp73-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:9b2aec6af35c113b05695ebb5749a787acd63cafc83086a05771d1e1cd1e555f", size = 16753552, upload-time = "2026-03-29T13:21:54.344Z" },
    { url = "https://files.pythonhosted.org/packages/04/74/f4c001f4714c3ad9ce037e18cf2b9c64871a84951eaa0baf683a9ca9301c/numpy-2.4.4-pp311-pypy311_pp73-win_amd64.whl", hash = "sha256:f2cf083b324a467e1ab358c105f6cad5ea950f50524668a80c486ff1db24e119", size = 12509075, upload-time = "2026-03-29T13:21:57.644Z" },
]

[[package]]
name = "oauthlib"
version = "3.3.1"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/0b/5f/19930f824ffeb0ad4372da4812c50edbd1434f678c90c2733e1188edfc63/oauthlib-3.3.1.tar.gz", hash = "sha256:0f0f8aa759826a193cf66c12ea1af1637f87b9b4622d46e866952bb022e538c9", size = 185918, upload-time = "2025-06-19T22:48:08.269Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/be/9c/92789c596b8df838baa98fa71844d84283302f7604ed565dafe5a6b5041a/oauthlib-3.3.1-py3-none-any.whl", hash = "sha256:88119c938d2b8fb88561af5f6ee0eec8cc8d552b7bb1f712743136eb7523b7a1", size = 160065, upload-time = "2025-06-19T22:48:06.508Z" },
]

[[package]]
name = "onnxruntime"
version = "1.24.4"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "flatbuffers" },
    { name = "numpy" },
    { name = "packaging" },
    { name = "protobuf" },
    { name = "sympy" },
]
wheels = [
    { url = "https://files.pythonhosted.org/packages/60/69/6c40720201012c6af9aa7d4ecdd620e521bd806dc6269d636fdd5c5aeebe/onnxruntime-1.24.4-cp311-cp311-macosx_14_0_arm64.whl", hash = "sha256:0bdfce8e9a6497cec584aab407b71bf697dac5e1b7b7974adc50bf7533bdb3a2", size = 17332131, upload-time = "2026-03-17T22:05:49.005Z" },
    { url = "https://files.pythonhosted.org/packages/38/e9/8c901c150ce0c368da38638f44152fb411059c0c7364b497c9e5c957321a/onnxruntime-1.24.4-cp311-cp311-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:046ff290045a387676941a02a8ae5c3ebec6b4f551ae228711968c4a69d8f6b7", size = 15152472, upload-time = "2026-03-17T22:03:26.176Z" },
    { url = "https://files.pythonhosted.org/packages/d5/b6/7a4df417cdd01e8f067a509e123ac8b31af450a719fa7ed81787dd6057ec/onnxruntime-1.24.4-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:e54ad52e61d2d4618dcff8fa1480ac66b24ee2eab73331322db1049f11ccf330", size = 17222993, upload-time = "2026-03-17T22:04:34.485Z" },
    { url = "https://files.pythonhosted.org/packages/dd/59/8febe015f391aa1757fa5ba82c759ea4b6c14ef970132efb5e316665ba61/onnxruntime-1.24.4-cp311-cp311-win_amd64.whl", hash = "sha256:b43b63eb24a2bc8fc77a09be67587a570967a412cccb837b6245ccb546691153", size = 12594863, upload-time = "2026-03-17T22:05:38.749Z" },
    { url = "https://files.pythonhosted.org/packages/32/84/4155fcd362e8873eb6ce305acfeeadacd9e0e59415adac474bea3d9281bb/onnxruntime-1.24.4-cp311-cp311-win_arm64.whl", hash = "sha256:e26478356dba25631fb3f20112e345f8e8bf62c499bb497e8a559f7d69cf7e7b", size = 12259895, upload-time = "2026-03-17T22:05:28.812Z" },
    { url = "https://files.pythonhosted.org/packages/d7/38/31db1b232b4ba960065a90c1506ad7a56995cd8482033184e97fadca17cc/onnxruntime-1.24.4-cp312-cp312-macosx_14_0_arm64.whl", hash = "sha256:cad1c2b3f455c55678ab2a8caa51fb420c25e6e3cf10f4c23653cdabedc8de78", size = 17341875, upload-time = "2026-03-17T22:05:51.669Z" },
    { url = "https://files.pythonhosted.org/packages/aa/60/c4d1c8043eb42f8a9aa9e931c8c293d289c48ff463267130eca97d13357f/onnxruntime-1.24.4-cp312-cp312-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:1a5c5a544b22f90859c88617ecb30e161ee3349fcc73878854f43d77f00558b5", size = 15172485, upload-time = "2026-03-17T22:03:32.182Z" },
    { url = "https://files.pythonhosted.org/packages/6d/ab/5b68110e0460d73fad814d5bd11c7b1ddcce5c37b10177eb264d6a36e331/onnxruntime-1.24.4-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:0d640eb9f3782689b55cfa715094474cd5662f2f137be6a6f847a594b6e9705c", size = 17244912, upload-time = "2026-03-17T22:04:37.251Z" },
    { url = "https://files.pythonhosted.org/packages/8b/f4/6b89e297b93704345f0f3f8c62229bee323ef25682a3f9b4f89a39324950/onnxruntime-1.24.4-cp312-cp312-win_amd64.whl", hash = "sha256:535b29475ca42b593c45fbb2152fbf1cdf3f287315bf650e6a724a0a1d065cdb", size = 12596856, upload-time = "2026-03-17T22:05:41.224Z" },
    { url = "https://files.pythonhosted.org/packages/43/06/8b8ec6e9e6a474fcd5d772453f627ad4549dfe3ab8c0bf70af5afcde551b/onnxruntime-1.24.4-cp312-cp312-win_arm64.whl", hash = "sha256:e6214096e14b7b52e3bee1903dc12dc7ca09cb65e26664668a4620cc5e6f9a90", size = 12270275, upload-time = "2026-03-17T22:05:31.132Z" },
    { url = "https://files.pythonhosted.org/packages/e9/f0/8a21ec0a97e40abb7d8da1e8b20fb9e1af509cc6d191f6faa75f73622fb2/onnxruntime-1.24.4-cp313-cp313-macosx_14_0_arm64.whl", hash = "sha256:e99a48078baaefa2b50fe5836c319499f71f13f76ed32d0211f39109147a49e0", size = 17341922, upload-time = "2026-03-17T22:03:56.364Z" },
    { url = "https://files.pythonhosted.org/packages/8b/25/d7908de8e08cee9abfa15b8aa82349b79733ae5865162a3609c11598805d/onnxruntime-1.24.4-cp313-cp313-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:dc4aaed1e5e1aaacf2343c838a30a7c3ade78f13eeb16817411f929d04040a13", size = 15172290, upload-time = "2026-03-17T22:03:37.124Z" },
    { url = "https://files.pythonhosted.org/packages/7f/72/105ec27a78c5aa0154a7c0cd8c41c19a97799c3b12fc30392928997e3be3/onnxruntime-1.24.4-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:e30c972bc02e072911aabb6891453ec73795386c0af2b761b65444b8a4c4745f", size = 17244738, upload-time = "2026-03-17T22:04:40.625Z" },
    { url = "https://files.pythonhosted.org/packages/05/fb/a592736d968c2f58e12de4d52088dda8e0e724b26ad5c0487263adb45875/onnxruntime-1.24.4-cp313-cp313-win_amd64.whl", hash = "sha256:3b6ba8b0181a3aa88edab00eb01424ffc06f42e71095a91186c2249415fcff93", size = 12597435, upload-time = "2026-03-17T22:05:43.826Z" },
    { url = "https://files.pythonhosted.org/packages/ad/04/ae2479e9841b64bd2eb44f8a64756c62593f896514369a11243b1b86ca5c/onnxruntime-1.24.4-cp313-cp313-win_arm64.whl", hash = "sha256:71d6a5c1821d6e8586a024000ece458db8f2fc0ecd050435d45794827ce81e19", size = 12269852, upload-time = "2026-03-17T22:05:33.353Z" },
    { url = "https://files.pythonhosted.org/packages/b4/af/a479a536c4398ffaf49fbbe755f45d5b8726bdb4335ab31b537f3d7149b8/onnxruntime-1.24.4-cp313-cp313t-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:1700f559c8086d06b2a4d5de51e62cb4ff5e2631822f71a36db8c72383db71ee", size = 15176861, upload-time = "2026-03-17T22:03:40.143Z" },
    { url = "https://files.pythonhosted.org/packages/be/13/19f5da70c346a76037da2c2851ecbf1266e61d7f0dcdb887c667210d4608/onnxruntime-1.24.4-cp313-cp313t-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:4c74e268dc808e61e63784d43f9ddcdaf50a776c2819e8bd1d1b11ef64bf7e36", size = 17247454, upload-time = "2026-03-17T22:04:46.643Z" },
    { url = "https://files.pythonhosted.org/packages/89/db/b30dbbd6037847b205ab75d962bc349bf1e46d02a65b30d7047a6893ffd6/onnxruntime-1.24.4-cp314-cp314-macosx_14_0_arm64.whl", hash = "sha256:fbff2a248940e3398ae78374c5a839e49a2f39079b488bc64439fa0ec327a3e4", size = 17343300, upload-time = "2026-03-17T22:03:59.223Z" },
    { url = "https://files.pythonhosted.org/packages/61/88/1746c0e7959961475b84c776d35601a21d445f463c93b1433a409ec3e188/onnxruntime-1.24.4-cp314-cp314-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:e2b7969e72d8cb53ffc88ab6d49dd5e75c1c663bda7be7eb0ece192f127343d1", size = 15175936, upload-time = "2026-03-17T22:03:43.671Z" },
    { url = "https://files.pythonhosted.org/packages/5f/ba/4699cde04a52cece66cbebc85bd8335a0d3b9ad485abc9a2e15946a1349d/onnxruntime-1.24.4-cp314-cp314-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:14ed1f197fab812b695a5eaddb536c635e58a2fbbe50a517c78f082cc6ce9177", size = 17246432, upload-time = "2026-03-17T22:04:49.58Z" },
    { url = "https://files.pythonhosted.org/packages/ef/60/4590910841bb28bd3b4b388a9efbedf4e2d2cca99ddf0c863642b4e87814/onnxruntime-1.24.4-cp314-cp314-win_amd64.whl", hash = "sha256:311e309f573bf3c12aa5723e23823077f83d5e412a18499d4485c7eb41040858", size = 12903276, upload-time = "2026-03-17T22:05:46.349Z" },
    { url = "https://files.pythonhosted.org/packages/7f/6f/60e2c0acea1e1ac09b3e794b5a19c166eebf91c0b860b3e6db8e74983fda/onnxruntime-1.24.4-cp314-cp314-win_arm64.whl", hash = "sha256:3f0b910e86b759a4732663ec61fd57ac42ee1b0066f68299de164220b660546d", size = 12594365, upload-time = "2026-03-17T22:05:35.795Z" },
    { url = "https://files.pythonhosted.org/packages/cf/68/0c05d10f8f6c40fe0912ebec0d5a33884aaa2af2053507e864dab0883208/onnxruntime-1.24.4-cp314-cp314t-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:aa12ddc54c9c4594073abcaa265cd9681e95fb89dae982a6f508a794ca42e661", size = 15176889, upload-time = "2026-03-17T22:03:48.021Z" },
    { url = "https://files.pythonhosted.org/packages/6c/1d/1666dc64e78d8587d168fec4e3b7922b92eb286a2ddeebcf6acb55c7dc82/onnxruntime-1.24.4-cp314-cp314t-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:e1cc6a518255f012134bc791975a6294806be9a3b20c4a54cca25194c90cf731", size = 17247021, upload-time = "2026-03-17T22:04:52.377Z" },
]

[[package]]
name = "opentelemetry-api"
version = "1.40.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "importlib-metadata" },
    { name = "typing-extensions" },
]
sdist = { url = "https://files.pythonhosted.org/packages/2c/1d/4049a9e8698361cc1a1aa03a6c59e4fa4c71e0c0f94a30f988a6876a2ae6/opentelemetry_api-1.40.0.tar.gz", hash = "sha256:159be641c0b04d11e9ecd576906462773eb97ae1b657730f0ecf64d32071569f", size = 70851, upload-time = "2026-03-04T14:17:21.555Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/5f/bf/93795954016c522008da367da292adceed71cca6ee1717e1d64c83089099/opentelemetry_api-1.40.0-py3-none-any.whl", hash = "sha256:82dd69331ae74b06f6a874704be0cfaa49a1650e1537d4a813b86ecef7d0ecf9", size = 68676, upload-time = "2026-03-04T14:17:01.24Z" },
]

[[package]]
name = "opentelemetry-exporter-otlp-proto-common"
version = "1.40.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "opentelemetry-proto" },
]
sdist = { url = "https://files.pythonhosted.org/packages/51/bc/1559d46557fe6eca0b46c88d4c2676285f1f3be2e8d06bb5d15fbffc814a/opentelemetry_exporter_otlp_proto_common-1.40.0.tar.gz", hash = "sha256:1cbee86a4064790b362a86601ee7934f368b81cd4cc2f2e163902a6e7818a0fa", size = 20416, upload-time = "2026-03-04T14:17:23.801Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/8b/ca/8f122055c97a932311a3f640273f084e738008933503d0c2563cd5d591fc/opentelemetry_exporter_otlp_proto_common-1.40.0-py3-none-any.whl", hash = "sha256:7081ff453835a82417bf38dccf122c827c3cbc94f2079b03bba02a3165f25149", size = 18369, upload-time = "2026-03-04T14:17:04.796Z" },
]

[[package]]
name = "opentelemetry-exporter-otlp-proto-grpc"
version = "1.40.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "googleapis-common-protos" },
    { name = "grpcio" },
    { name = "opentelemetry-api" },
    { name = "opentelemetry-exporter-otlp-proto-common" },
    { name = "opentelemetry-proto" },
    { name = "opentelemetry-sdk" },
    { name = "typing-extensions" },
]
sdist = { url = "https://files.pythonhosted.org/packages/8f/7f/b9e60435cfcc7590fa87436edad6822240dddbc184643a2a005301cc31f4/opentelemetry_exporter_otlp_proto_grpc-1.40.0.tar.gz", hash = "sha256:bd4015183e40b635b3dab8da528b27161ba83bf4ef545776b196f0fb4ec47740", size = 25759, upload-time = "2026-03-04T14:17:24.4Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/96/6f/7ee0980afcbdcd2d40362da16f7f9796bd083bf7f0b8e038abfbc0300f5d/opentelemetry_exporter_otlp_proto_grpc-1.40.0-py3-none-any.whl", hash = "sha256:2aa0ca53483fe0cf6405087a7491472b70335bc5c7944378a0a8e72e86995c52", size = 20304, upload-time = "2026-03-04T14:17:05.942Z" },
]

[[package]]
name = "opentelemetry-proto"
version = "1.40.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "protobuf" },
]
sdist = { url = "https://files.pythonhosted.org/packages/4c/77/dd38991db037fdfce45849491cb61de5ab000f49824a00230afb112a4392/opentelemetry_proto-1.40.0.tar.gz", hash = "sha256:03f639ca129ba513f5819810f5b1f42bcb371391405d99c168fe6937c62febcd", size = 45667, upload-time = "2026-03-04T14:17:31.194Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/b9/b2/189b2577dde745b15625b3214302605b1353436219d42b7912e77fa8dc24/opentelemetry_proto-1.40.0-py3-none-any.whl", hash = "sha256:266c4385d88923a23d63e353e9761af0f47a6ed0d486979777fe4de59dc9b25f", size = 72073, upload-time = "2026-03-04T14:17:16.673Z" },
]

[[package]]
name = "opentelemetry-sdk"
version = "1.40.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "opentelemetry-api" },
    { name = "opentelemetry-semantic-conventions" },
    { name = "typing-extensions" },
]
sdist = { url = "https://files.pythonhosted.org/packages/58/fd/3c3125b20ba18ce2155ba9ea74acb0ae5d25f8cd39cfd37455601b7955cc/opentelemetry_sdk-1.40.0.tar.gz", hash = "sha256:18e9f5ec20d859d268c7cb3c5198c8d105d073714db3de50b593b8c1345a48f2", size = 184252, upload-time = "2026-03-04T14:17:31.87Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/2c/c5/6a852903d8bfac758c6dc6e9a68b015d3c33f2f1be5e9591e0f4b69c7e0a/opentelemetry_sdk-1.40.0-py3-none-any.whl", hash = "sha256:787d2154a71f4b3d81f20524a8ce061b7db667d24e46753f32a7bc48f1c1f3f1", size = 141951, upload-time = "2026-03-04T14:17:17.961Z" },
]

[[package]]
name = "opentelemetry-semantic-conventions"
version = "0.61b0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "opentelemetry-api" },
    { name = "typing-extensions" },
]
sdist = { url = "https://files.pythonhosted.org/packages/6d/c0/4ae7973f3c2cfd2b6e321f1675626f0dab0a97027cc7a297474c9c8f3d04/opentelemetry_semantic_conventions-0.61b0.tar.gz", hash = "sha256:072f65473c5d7c6dc0355b27d6c9d1a679d63b6d4b4b16a9773062cb7e31192a", size = 145755, upload-time = "2026-03-04T14:17:32.664Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/b2/37/cc6a55e448deaa9b27377d087da8615a3416d8ad523d5960b78dbeadd02a/opentelemetry_semantic_conventions-0.61b0-py3-none-any.whl", hash = "sha256:fa530a96be229795f8cef353739b618148b0fe2b4b3f005e60e262926c4d38e2", size = 231621, upload-time = "2026-03-04T14:17:19.33Z" },
]

[[package]]
name = "orjson"
version = "3.11.8"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/9d/1b/2024d06792d0779f9dbc51531b61c24f76c75b9f4ce05e6f3377a1814cea/orjson-3.11.8.tar.gz", hash = "sha256:96163d9cdc5a202703e9ad1b9ae757d5f0ca62f4fa0cc93d1f27b0e180cc404e", size = 5603832, upload-time = "2026-03-31T16:16:27.878Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/67/41/5aa7fa3b0f4dc6b47dcafc3cea909299c37e40e9972feabc8b6a74e2730d/orjson-3.11.8-cp311-cp311-macosx_10_15_x86_64.macosx_11_0_arm64.macosx_10_15_universal2.whl", hash = "sha256:003646067cc48b7fcab2ae0c562491c9b5d2cbd43f1e5f16d98fd118c5522d34", size = 229229, upload-time = "2026-03-31T16:14:50.424Z" },
    { url = "https://files.pythonhosted.org/packages/0a/d7/57e7f2458e0a2c41694f39fc830030a13053a84f837a5b73423dca1f0938/orjson-3.11.8-cp311-cp311-macosx_15_0_arm64.whl", hash = "sha256:ed193ce51d77a3830cad399a529cd4ef029968761f43ddc549e1bc62b40d88f8", size = 128871, upload-time = "2026-03-31T16:14:51.888Z" },
    { url = "https://files.pythonhosted.org/packages/53/4a/e0fdb9430983e6c46e0299559275025075568aad5d21dd606faee3703924/orjson-3.11.8-cp311-cp311-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:f30491bc4f862aa15744b9738517454f1e46e56c972a2be87d70d727d5b2a8f8", size = 132104, upload-time = "2026-03-31T16:14:53.142Z" },
    { url = "https://files.pythonhosted.org/packages/08/4a/2025a60ff3f5c8522060cda46612d9b1efa653de66ed2908591d8d82f22d/orjson-3.11.8-cp311-cp311-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:6eda5b8b6be91d3f26efb7dc6e5e68ee805bc5617f65a328587b35255f138bf4", size = 130483, upload-time = "2026-03-31T16:14:54.605Z" },
    { url = "https://files.pythonhosted.org/packages/2d/3c/b9cde05bdc7b2385c66014e0620627da638d3d04e4954416ab48c31196c5/orjson-3.11.8-cp311-cp311-manylinux_2_17_i686.manylinux2014_i686.whl", hash = "sha256:ee8db7bfb6fe03581bbab54d7c4124a6dd6a7f4273a38f7267197890f094675f", size = 135481, upload-time = "2026-03-31T16:14:55.901Z" },
    { url = "https://files.pythonhosted.org/packages/ff/f2/a8238e7734de7cb589fed319857a8025d509c89dc52fdcc88f39c6d03d5a/orjson-3.11.8-cp311-cp311-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:5d8b5231de76c528a46b57010bbd83fb51e056aa0220a372fd5065e978406f1c", size = 146819, upload-time = "2026-03-31T16:14:57.548Z" },
    { url = "https://files.pythonhosted.org/packages/db/10/dbf1e2a3cafea673b1b4350e371877b759060d6018a998643b7040e5de48/orjson-3.11.8-cp311-cp311-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:58a4a208a6fbfdb7a7327b8f201c6014f189f721fd55d047cafc4157af1bc62a", size = 132846, upload-time = "2026-03-31T16:14:58.91Z" },
    { url = "https://files.pythonhosted.org/packages/f8/fc/55e667ec9c85694038fcff00573d221b085d50777368ee3d77f38668bf3c/orjson-3.11.8-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:5f8952d6d2505c003e8f0224ff7858d341fa4e33fef82b91c4ff0ef070f2393c", size = 133580, upload-time = "2026-03-31T16:15:00.519Z" },
    { url = "https://files.pythonhosted.org/packages/7e/a6/c08c589a9aad0cb46c4831d17de212a2b6901f9d976814321ff8e69e8785/orjson-3.11.8-cp311-cp311-musllinux_1_2_aarch64.whl", hash = "sha256:0022bb50f90da04b009ce32c512dc1885910daa7cb10b7b0cba4505b16db82a8", size = 142042, upload-time = "2026-03-31T16:15:01.906Z" },
    { url = "https://files.pythonhosted.org/packages/5c/cc/2f78ea241d52b717d2efc38878615fe80425bf2beb6e68c984dde257a766/orjson-3.11.8-cp311-cp311-musllinux_1_2_armv7l.whl", hash = "sha256:ff51f9d657d1afb6f410cb435792ce4e1fe427aab23d2fcd727a2876e21d4cb6", size = 423845, upload-time = "2026-03-31T16:15:03.703Z" },
    { url = "https://files.pythonhosted.org/packages/70/07/c17dcf05dd8045457538428a983bf1f1127928df5bf328cb24d2b7cddacb/orjson-3.11.8-cp311-cp311-musllinux_1_2_i686.whl", hash = "sha256:6dbe9a97bdb4d8d9d5367b52a7c32549bba70b2739c58ef74a6964a6d05ae054", size = 147729, upload-time = "2026-03-31T16:15:05.203Z" },
    { url = "https://files.pythonhosted.org/packages/90/6c/0fb6e8a24e682e0958d71711ae6f39110e4b9cd8cab1357e2a89cb8e1951/orjson-3.11.8-cp311-cp311-musllinux_1_2_x86_64.whl", hash = "sha256:a5c370674ebabe16c6ccac33ff80c62bf8a6e59439f5e9d40c1f5ab8fd2215b7", size = 136425, upload-time = "2026-03-31T16:15:07.052Z" },
    { url = "https://files.pythonhosted.org/packages/b2/35/4d3cc3a3d616035beb51b24a09bb872942dc452cf2df0c1d11ab35046d9f/orjson-3.11.8-cp311-cp311-win32.whl", hash = "sha256:0e32f7154299f42ae66f13488963269e5eccb8d588a65bc839ed986919fc9fac", size = 131870, upload-time = "2026-03-31T16:15:08.678Z" },
    { url = "https://files.pythonhosted.org/packages/13/26/9fe70f81d16b702f8c3a775e8731b50ad91d22dacd14c7599b60a0941cd1/orjson-3.11.8-cp311-cp311-win_amd64.whl", hash = "sha256:25e0c672a2e32348d2eb33057b41e754091f2835f87222e4675b796b92264f06", size = 127440, upload-time = "2026-03-31T16:15:09.994Z" },
    { url = "https://files.pythonhosted.org/packages/e8/c6/b038339f4145efd2859c1ca53097a52c0bb9cbdd24f947ebe146da1ad067/orjson-3.11.8-cp311-cp311-win_arm64.whl", hash = "sha256:9185589c1f2a944c17e26c9925dcdbc2df061cc4a145395c57f0c51f9b5dbfcd", size = 127399, upload-time = "2026-03-31T16:15:11.412Z" },
    { url = "https://files.pythonhosted.org/packages/01/f6/8d58b32ab32d9215973a1688aebd098252ee8af1766c0e4e36e7831f0295/orjson-3.11.8-cp312-cp312-macosx_10_15_x86_64.macosx_11_0_arm64.macosx_10_15_universal2.whl", hash = "sha256:1cd0b77e77c95758f8e1100139844e99f3ccc87e71e6fc8e1c027e55807c549f", size = 229233, upload-time = "2026-03-31T16:15:12.762Z" },
    { url = "https://files.pythonhosted.org/packages/a9/8b/2ffe35e71f6b92622e8ea4607bf33ecf7dfb51b3619dcfabfd36cbe2d0a5/orjson-3.11.8-cp312-cp312-macosx_15_0_arm64.whl", hash = "sha256:6a3d159d5ffa0e3961f353c4b036540996bf8b9697ccc38261c0eac1fd3347a6", size = 128772, upload-time = "2026-03-31T16:15:14.237Z" },
    { url = "https://files.pythonhosted.org/packages/27/d2/1f8682ae50d5c6897a563cb96bc106da8c9cb5b7b6e81a52e4cc086679b9/orjson-3.11.8-cp312-cp312-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:76070a76e9c5ae661e2d9848f216980d8d533e0f8143e6ed462807b242e3c5e8", size = 131946, upload-time = "2026-03-31T16:15:15.607Z" },
    { url = "https://files.pythonhosted.org/packages/52/4b/5500f76f0eece84226e0689cb48dcde081104c2fa6e2483d17ca13685ffb/orjson-3.11.8-cp312-cp312-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:54153d21520a71a4c82a0dbb4523e468941d549d221dc173de0f019678cf3813", size = 130368, upload-time = "2026-03-31T16:15:17.066Z" },
    { url = "https://files.pythonhosted.org/packages/da/4e/58b927e08fbe9840e6c920d9e299b051ea667463b1f39a56e668669f8508/orjson-3.11.8-cp312-cp312-manylinux_2_17_i686.manylinux2014_i686.whl", hash = "sha256:469ac2125611b7c5741a0b3798cd9e5786cbad6345f9f400c77212be89563bec", size = 135540, upload-time = "2026-03-31T16:15:18.404Z" },
    { url = "https://files.pythonhosted.org/packages/56/7c/ba7cb871cba1bcd5cd02ee34f98d894c6cea96353ad87466e5aef2429c60/orjson-3.11.8-cp312-cp312-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:14778ffd0f6896aa613951a7fbf4690229aa7a543cb2bfbe9f358e08aafa9546", size = 146877, upload-time = "2026-03-31T16:15:19.833Z" },
    { url = "https://files.pythonhosted.org/packages/0b/5d/eb9c25fc1386696c6a342cd361c306452c75e0b55e86ad602dd4827a7fd7/orjson-3.11.8-cp312-cp312-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:ea56a955056a6d6c550cf18b3348656a9d9a4f02e2d0c02cabf3c73f1055d506", size = 132837, upload-time = "2026-03-31T16:15:21.282Z" },
    { url = "https://files.pythonhosted.org/packages/37/87/5ddeb7fc1fbd9004aeccab08426f34c81a5b4c25c7061281862b015fce2b/orjson-3.11.8-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:53a0f57e59a530d18a142f4d4ba6dfc708dc5fdedce45e98ff06b44930a2a48f", size = 133624, upload-time = "2026-03-31T16:15:22.641Z" },
    { url = "https://files.pythonhosted.org/packages/22/09/90048793db94ee4b2fcec4ac8e5ddb077367637d6650be896b3494b79bb7/orjson-3.11.8-cp312-cp312-musllinux_1_2_aarch64.whl", hash = "sha256:9b48e274f8824567d74e2158199e269597edf00823a1b12b63d48462bbf5123e", size = 141904, upload-time = "2026-03-31T16:15:24.435Z" },
    { url = "https://files.pythonhosted.org/packages/c0/cf/eb284847487821a5d415e54149a6449ba9bfc5872ce63ab7be41b8ec401c/orjson-3.11.8-cp312-cp312-musllinux_1_2_armv7l.whl", hash = "sha256:3f262401086a3960586af06c054609365e98407151f5ea24a62893a40d80dbbb", size = 423742, upload-time = "2026-03-31T16:15:26.155Z" },
    { url = "https://files.pythonhosted.org/packages/44/09/e12423d327071c851c13e76936f144a96adacfc037394dec35ac3fc8d1e8/orjson-3.11.8-cp312-cp312-musllinux_1_2_i686.whl", hash = "sha256:8e8c6218b614badf8e229b697865df4301afa74b791b6c9ade01d19a9953a942", size = 147806, upload-time = "2026-03-31T16:15:27.909Z" },
    { url = "https://files.pythonhosted.org/packages/b3/6d/37c2589ba864e582ffe7611643314785c6afb1f83c701654ef05daa8fcc7/orjson-3.11.8-cp312-cp312-musllinux_1_2_x86_64.whl", hash = "sha256:093d489fa039ddade2db541097dbb484999fcc65fc2b0ff9819141e2ab364f25", size = 136485, upload-time = "2026-03-31T16:15:29.749Z" },
    { url = "https://files.pythonhosted.org/packages/be/c9/135194a02ab76b04ed9a10f68624b7ebd238bbe55548878b11ff15a0f352/orjson-3.11.8-cp312-cp312-win32.whl", hash = "sha256:e0950ed1bcb9893f4293fd5c5a7ee10934fbf82c4101c70be360db23ce24b7d2", size = 131966, upload-time = "2026-03-31T16:15:31.687Z" },
    { url = "https://files.pythonhosted.org/packages/ed/9a/9796f8fbe3cf30ce9cb696748dbb535e5c87be4bf4fe2e9ca498ef1fa8cf/orjson-3.11.8-cp312-cp312-win_amd64.whl", hash = "sha256:3cf17c141617b88ced4536b2135c552490f07799f6ad565948ea07bef0dcb9a6", size = 127441, upload-time = "2026-03-31T16:15:33.333Z" },
    { url = "https://files.pythonhosted.org/packages/cc/47/5aaf54524a7a4a0dd09dd778f3fa65dd2108290615b652e23d944152bc8e/orjson-3.11.8-cp312-cp312-win_arm64.whl", hash = "sha256:48854463b0572cc87dac7d981aa72ed8bf6deedc0511853dc76b8bbd5482d36d", size = 127364, upload-time = "2026-03-31T16:15:34.748Z" },
    { url = "https://files.pythonhosted.org/packages/66/7f/95fba509bb2305fab0073558f1e8c3a2ec4b2afe58ed9fcb7d3b8beafe94/orjson-3.11.8-cp313-cp313-macosx_10_15_x86_64.macosx_11_0_arm64.macosx_10_15_universal2.whl", hash = "sha256:3f23426851d98478c8970da5991f84784a76682213cd50eb73a1da56b95239dc", size = 229180, upload-time = "2026-03-31T16:15:36.426Z" },
    { url = "https://files.pythonhosted.org/packages/f6/9d/b237215c743ca073697d759b5503abd2cb8a0d7b9c9e21f524bcf176ab66/orjson-3.11.8-cp313-cp313-macosx_15_0_arm64.whl", hash = "sha256:ebaed4cef74a045b83e23537b52ef19a367c7e3f536751e355a2a394f8648559", size = 128754, upload-time = "2026-03-31T16:15:38.049Z" },
    { url = "https://files.pythonhosted.org/packages/42/3d/27d65b6d11e63f133781425f132807aef793ed25075fec686fc8e46dd528/orjson-3.11.8-cp313-cp313-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:97c8f5d3b62380b70c36ffacb2a356b7c6becec86099b177f73851ba095ef623", size = 131877, upload-time = "2026-03-31T16:15:39.484Z" },
    { url = "https://files.pythonhosted.org/packages/dd/cc/faee30cd8f00421999e40ef0eba7332e3a625ce91a58200a2f52c7fef235/orjson-3.11.8-cp313-cp313-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:436c4922968a619fb7fef1ccd4b8b3a76c13b67d607073914d675026e911a65c", size = 130361, upload-time = "2026-03-31T16:15:41.274Z" },
    { url = "https://files.pythonhosted.org/packages/5c/bb/a6c55896197f97b6d4b4e7c7fd77e7235517c34f5d6ad5aadd43c54c6d7c/orjson-3.11.8-cp313-cp313-manylinux_2_17_i686.manylinux2014_i686.whl", hash = "sha256:1ab359aff0436d80bfe8a23b46b5fea69f1e18aaf1760a709b4787f1318b317f", size = 135521, upload-time = "2026-03-31T16:15:42.758Z" },
    { url = "https://files.pythonhosted.org/packages/9c/7c/ca3a3525aa32ff636ebb1778e77e3587b016ab2edb1b618b36ba96f8f2c0/orjson-3.11.8-cp313-cp313-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:f89b6d0b3a8d81e1929d3ab3d92bbc225688bd80a770c49432543928fe09ac55", size = 146862, upload-time = "2026-03-31T16:15:44.341Z" },
    { url = "https://files.pythonhosted.org/packages/3c/0c/18a9d7f18b5edd37344d1fd5be17e94dc652c67826ab749c6e5948a78112/orjson-3.11.8-cp313-cp313-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:29c009e7a2ca9ad0ed1376ce20dd692146a5d9fe4310848904b6b4fee5c5c137", size = 132847, upload-time = "2026-03-31T16:15:46.368Z" },
    { url = "https://files.pythonhosted.org/packages/23/91/7e722f352ad67ca573cee44de2a58fb810d0f4eb4e33276c6a557979fd8a/orjson-3.11.8-cp313-cp313-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:705b895b781b3e395c067129d8551655642dfe9437273211d5404e87ac752b53", size = 133637, upload-time = "2026-03-31T16:15:48.123Z" },
    { url = "https://files.pythonhosted.org/packages/af/04/32845ce13ac5bd1046ddb02ac9432ba856cc35f6d74dde95864fe0ad5523/orjson-3.11.8-cp313-cp313-musllinux_1_2_aarch64.whl", hash = "sha256:88006eda83858a9fdf73985ce3804e885c2befb2f506c9a3723cdeb5a2880e3e", size = 141906, upload-time = "2026-03-31T16:15:49.626Z" },
    { url = "https://files.pythonhosted.org/packages/02/5e/c551387ddf2d7106d9039369862245c85738b828844d13b99ccb8d61fd06/orjson-3.11.8-cp313-cp313-musllinux_1_2_armv7l.whl", hash = "sha256:55120759e61309af7fcf9e961c6f6af3dde5921cdb3ee863ef63fd9db126cae6", size = 423722, upload-time = "2026-03-31T16:15:51.176Z" },
    { url = "https://files.pythonhosted.org/packages/00/a3/ecfe62434096f8a794d4976728cb59bcfc4a643977f21c2040545d37eb4c/orjson-3.11.8-cp313-cp313-musllinux_1_2_i686.whl", hash = "sha256:98bdc6cb889d19bed01de46e67574a2eab61f5cc6b768ed50e8ac68e9d6ffab6", size = 147801, upload-time = "2026-03-31T16:15:52.939Z" },
    { url = "https://files.pythonhosted.org/packages/18/6d/0dce10b9f6643fdc59d99333871a38fa5a769d8e2fc34a18e5d2bfdee900/orjson-3.11.8-cp313-cp313-musllinux_1_2_x86_64.whl", hash = "sha256:708c95f925a43ab9f34625e45dcdadf09ec8a6e7b664a938f2f8d5650f6c090b", size = 136460, upload-time = "2026-03-31T16:15:54.431Z" },
    { url = "https://files.pythonhosted.org/packages/01/d6/6dde4f31842d87099238f1f07b459d24edc1a774d20687187443ab044191/orjson-3.11.8-cp313-cp313-win32.whl", hash = "sha256:01c4e5a6695dc09098f2e6468a251bc4671c50922d4d745aff1a0a33a0cf5b8d", size = 131956, upload-time = "2026-03-31T16:15:56.081Z" },
    { url = "https://files.pythonhosted.org/packages/c1/f9/4e494a56e013db957fb77186b818b916d4695b8fa2aa612364974160e91b/orjson-3.11.8-cp313-cp313-win_amd64.whl", hash = "sha256:c154a35dd1330707450bb4d4e7dd1f17fa6f42267a40c1e8a1daa5e13719b4b8", size = 127410, upload-time = "2026-03-31T16:15:57.54Z" },
    { url = "https://files.pythonhosted.org/packages/57/7f/803203d00d6edb6e9e7eef421d4e1adbb5ea973e40b3533f3cfd9aeb374e/orjson-3.11.8-cp313-cp313-win_arm64.whl", hash = "sha256:4861bde57f4d253ab041e374f44023460e60e71efaa121f3c5f0ed457c3a701e", size = 127338, upload-time = "2026-03-31T16:15:59.106Z" },
    { url = "https://files.pythonhosted.org/packages/6d/35/b01910c3d6b85dc882442afe5060cbf719c7d1fc85749294beda23d17873/orjson-3.11.8-cp314-cp314-macosx_10_15_x86_64.macosx_11_0_arm64.macosx_10_15_universal2.whl", hash = "sha256:ec795530a73c269a55130498842aaa762e4a939f6ce481a7e986eeaa790e9da4", size = 229171, upload-time = "2026-03-31T16:16:00.651Z" },
    { url = "https://files.pythonhosted.org/packages/c2/56/c9ec97bd11240abef39b9e5d99a15462809c45f677420fd148a6c5e6295e/orjson-3.11.8-cp314-cp314-macosx_15_0_arm64.whl", hash = "sha256:c492a0e011c0f9066e9ceaa896fbc5b068c54d365fea5f3444b697ee01bc8625", size = 128746, upload-time = "2026-03-31T16:16:02.673Z" },
    { url = "https://files.pythonhosted.org/packages/3b/e4/66d4f30a90de45e2f0cbd9623588e8ae71eef7679dbe2ae954ed6d66a41f/orjson-3.11.8-cp314-cp314-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:883206d55b1bd5f5679ad5e6ddd3d1a5e3cac5190482927fdb8c78fb699193b5", size = 131867, upload-time = "2026-03-31T16:16:04.342Z" },
    { url = "https://files.pythonhosted.org/packages/19/30/2a645fc9286b928675e43fa2a3a16fb7b6764aa78cc719dc82141e00f30b/orjson-3.11.8-cp314-cp314-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:5774c1fdcc98b2259800b683b19599c133baeb11d60033e2095fd9d4667b82db", size = 124664, upload-time = "2026-03-31T16:16:05.837Z" },
    { url = "https://files.pythonhosted.org/packages/db/44/77b9a86d84a28d52ba3316d77737f6514e17118119ade3f91b639e859029/orjson-3.11.8-cp314-cp314-manylinux_2_17_i686.manylinux2014_i686.whl", hash = "sha256:8ac7381c83dd3d4a6347e6635950aa448f54e7b8406a27c7ecb4a37e9f1ae08b", size = 129701, upload-time = "2026-03-31T16:16:07.407Z" },
    { url = "https://files.pythonhosted.org/packages/b3/ea/eff3d9bfe47e9bc6969c9181c58d9f71237f923f9c86a2d2f490cd898c82/orjson-3.11.8-cp314-cp314-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:14439063aebcb92401c11afc68ee4e407258d2752e62d748b6942dad20d2a70d", size = 141202, upload-time = "2026-03-31T16:16:09.48Z" },
    { url = "https://files.pythonhosted.org/packages/52/c8/90d4b4c60c84d62068d0cf9e4d8f0a4e05e76971d133ac0c60d818d4db20/orjson-3.11.8-cp314-cp314-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:fa72e71977bff96567b0f500fc5bfd2fdf915f34052c782a4c6ebbdaa97aa858", size = 127194, upload-time = "2026-03-31T16:16:11.02Z" },
    { url = "https://files.pythonhosted.org/packages/8d/c7/ea9e08d1f0ba981adffb629811148b44774d935171e7b3d780ae43c4c254/orjson-3.11.8-cp314-cp314-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:7679bc2f01bb0d219758f1a5f87bb7c8a81c0a186824a393b366876b4948e14f", size = 133639, upload-time = "2026-03-31T16:16:13.434Z" },
    { url = "https://files.pythonhosted.org/packages/6c/8c/ddbbfd6ba59453c8fc7fe1d0e5983895864e264c37481b2a791db635f046/orjson-3.11.8-cp314-cp314-musllinux_1_2_aarch64.whl", hash = "sha256:14f7b8fcb35ef403b42fa5ecfa4ed032332a91f3dc7368fbce4184d59e1eae0d", size = 141914, upload-time = "2026-03-31T16:16:14.955Z" },
    { url = "https://files.pythonhosted.org/packages/4e/31/dbfbefec9df060d34ef4962cd0afcb6fa7a9ec65884cb78f04a7859526c3/orjson-3.11.8-cp314-cp314-musllinux_1_2_armv7l.whl", hash = "sha256:c2bdf7b2facc80b5e34f48a2d557727d5c5c57a8a450de122ae81fa26a81c1bc", size = 423800, upload-time = "2026-03-31T16:16:16.594Z" },
    { url = "https://files.pythonhosted.org/packages/87/cf/f74e9ae9803d4ab46b163494adba636c6d7ea955af5cc23b8aaa94cfd528/orjson-3.11.8-cp314-cp314-musllinux_1_2_i686.whl", hash = "sha256:ccd7ba1b0605813a0715171d39ec4c314cb97a9c85893c2c5c0c3a3729df38bf", size = 147837, upload-time = "2026-03-31T16:16:18.585Z" },
    { url = "https://files.pythonhosted.org/packages/64/e6/9214f017b5db85e84e68602792f742e5dc5249e963503d1b356bee611e01/orjson-3.11.8-cp314-cp314-musllinux_1_2_x86_64.whl", hash = "sha256:cdbc8c9c02463fef4d3c53a9ba3336d05496ec8e1f1c53326a1e4acc11f5c600", size = 136441, upload-time = "2026-03-31T16:16:20.151Z" },
    { url = "https://files.pythonhosted.org/packages/24/dd/3590348818f58f837a75fb969b04cdf187ae197e14d60b5e5a794a38b79d/orjson-3.11.8-cp314-cp314-win32.whl", hash = "sha256:0b57f67710a8cd459e4e54eb96d5f77f3624eba0c661ba19a525807e42eccade", size = 131983, upload-time = "2026-03-31T16:16:21.823Z" },
    { url = "https://files.pythonhosted.org/packages/3f/0f/b6cb692116e05d058f31ceee819c70f097fa9167c82f67fabe7516289abc/orjson-3.11.8-cp314-cp314-win_amd64.whl", hash = "sha256:735e2262363dcbe05c35e3a8869898022af78f89dde9e256924dc02e99fe69ca", size = 127396, upload-time = "2026-03-31T16:16:23.685Z" },
    { url = "https://files.pythonhosted.org/packages/c0/d1/facb5b5051fabb0ef9d26c6544d87ef19a939a9a001198655d0d891062dd/orjson-3.11.8-cp314-cp314-win_arm64.whl", hash = "sha256:6ccdea2c213cf9f3d9490cbd5d427693c870753df41e6cb375bd79bcbafc8817", size = 127330, upload-time = "2026-03-31T16:16:25.496Z" },
]

[[package]]
name = "overrides"
version = "7.7.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/36/86/b585f53236dec60aba864e050778b25045f857e17f6e5ea0ae95fe80edd2/overrides-7.7.0.tar.gz", hash = "sha256:55158fa3d93b98cc75299b1e67078ad9003ca27945c76162c1c0766d6f91820a", size = 22812, upload-time = "2024-01-27T21:01:33.423Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/2c/ab/fc8290c6a4c722e5514d80f62b2dc4c4df1a68a41d1364e625c35990fcf3/overrides-7.7.0-py3-none-any.whl", hash = "sha256:c7ed9d062f78b8e4c1a7b70bd8796b35ead4d9f510227ef9c5dc7626c60d7e49", size = 17832, upload-time = "2024-01-27T21:01:31.393Z" },
]

[[package]]
name = "packaging"
version = "26.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/65/ee/299d360cdc32edc7d2cf530f3accf79c4fca01e96ffc950d8a52213bd8e4/packaging-26.0.tar.gz", hash = "sha256:00243ae351a257117b6a241061796684b084ed1c516a08c48a3f7e147a9d80b4", size = 143416, upload-time = "2026-01-21T20:50:39.064Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/b7/b9/c538f279a4e237a006a2c98387d081e9eb060d203d8ed34467cc0f0b9b53/packaging-26.0-py3-none-any.whl", hash = "sha256:b36f1fef9334a5588b4166f8bcd26a14e521f2b55e6b9de3aaa80d3ff7a37529", size = 74366, upload-time = "2026-01-21T20:50:37.788Z" },
]

[[package]]
name = "passlib"
version = "1.7.4"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/b6/06/9da9ee59a67fae7761aab3ccc84fa4f3f33f125b370f1ccdb915bf967c11/passlib-1.7.4.tar.gz", hash = "sha256:defd50f72b65c5402ab2c573830a6978e5f202ad0d984793c8dde2c4152ebe04", size = 689844, upload-time = "2020-10-08T19:00:52.121Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/3b/a4/ab6b7589382ca3df236e03faa71deac88cae040af60c071a78d254a62172/passlib-1.7.4-py2.py3-none-any.whl", hash = "sha256:aa6bca462b8d8bda89c70b382f0c298a20b5560af6cbfa2dce410c0a2fb669f1", size = 525554, upload-time = "2020-10-08T19:00:49.856Z" },
]

[package.optional-dependencies]
bcrypt = [
    { name = "bcrypt" },
]

[[package]]
name = "pluggy"
version = "1.6.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/f9/e2/3e91f31a7d2b083fe6ef3fa267035b518369d9511ffab804f839851d2779/pluggy-1.6.0.tar.gz", hash = "sha256:7dcc130b76258d33b90f61b658791dede3486c3e6bfb003ee5c9bfb396dd22f3", size = 69412, upload-time = "2025-05-15T12:30:07.975Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/54/20/4d324d65cc6d9205fabedc306948156824eb9f0ee1633355a8f7ec5c66bf/pluggy-1.6.0-py3-none-any.whl", hash = "sha256:e920276dd6813095e9377c0bc5566d94c932c33b27a3e3945d8389c374dd4746", size = 20538, upload-time = "2025-05-15T12:30:06.134Z" },
]

[[package]]
name = "protobuf"
version = "6.33.6"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/66/70/e908e9c5e52ef7c3a6c7902c9dfbb34c7e29c25d2f81ade3856445fd5c94/protobuf-6.33.6.tar.gz", hash = "sha256:a6768d25248312c297558af96a9f9c929e8c4cee0659cb07e780731095f38135", size = 444531, upload-time = "2026-03-18T19:05:00.988Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/fc/9f/2f509339e89cfa6f6a4c4ff50438db9ca488dec341f7e454adad60150b00/protobuf-6.33.6-cp310-abi3-win32.whl", hash = "sha256:7d29d9b65f8afef196f8334e80d6bc1d5d4adedb449971fefd3723824e6e77d3", size = 425739, upload-time = "2026-03-18T19:04:48.373Z" },
    { url = "https://files.pythonhosted.org/packages/76/5d/683efcd4798e0030c1bab27374fd13a89f7c2515fb1f3123efdfaa5eab57/protobuf-6.33.6-cp310-abi3-win_amd64.whl", hash = "sha256:0cd27b587afca21b7cfa59a74dcbd48a50f0a6400cfb59391340ad729d91d326", size = 437089, upload-time = "2026-03-18T19:04:50.381Z" },
    { url = "https://files.pythonhosted.org/packages/5c/01/a3c3ed5cd186f39e7880f8303cc51385a198a81469d53d0fdecf1f64d929/protobuf-6.33.6-cp39-abi3-macosx_10_9_universal2.whl", hash = "sha256:9720e6961b251bde64edfdab7d500725a2af5280f3f4c87e57c0208376aa8c3a", size = 427737, upload-time = "2026-03-18T19:04:51.866Z" },
    { url = "https://files.pythonhosted.org/packages/ee/90/b3c01fdec7d2f627b3a6884243ba328c1217ed2d978def5c12dc50d328a3/protobuf-6.33.6-cp39-abi3-manylinux2014_aarch64.whl", hash = "sha256:e2afbae9b8e1825e3529f88d514754e094278bb95eadc0e199751cdd9a2e82a2", size = 324610, upload-time = "2026-03-18T19:04:53.096Z" },
    { url = "https://files.pythonhosted.org/packages/9b/ca/25afc144934014700c52e05103c2421997482d561f3101ff352e1292fb81/protobuf-6.33.6-cp39-abi3-manylinux2014_s390x.whl", hash = "sha256:c96c37eec15086b79762ed265d59ab204dabc53056e3443e702d2681f4b39ce3", size = 339381, upload-time = "2026-03-18T19:04:54.616Z" },
    { url = "https://files.pythonhosted.org/packages/16/92/d1e32e3e0d894fe00b15ce28ad4944ab692713f2e7f0a99787405e43533a/protobuf-6.33.6-cp39-abi3-manylinux2014_x86_64.whl", hash = "sha256:e9db7e292e0ab79dd108d7f1a94fe31601ce1ee3f7b79e0692043423020b0593", size = 323436, upload-time = "2026-03-18T19:04:55.768Z" },
    { url = "https://files.pythonhosted.org/packages/c4/72/02445137af02769918a93807b2b7890047c32bfb9f90371cbc12688819eb/protobuf-6.33.6-py3-none-any.whl", hash = "sha256:77179e006c476e69bf8e8ce866640091ec42e1beb80b213c3900006ecfba6901", size = 170656, upload-time = "2026-03-18T19:04:59.826Z" },
]

[[package]]
name = "pyasn1"
version = "0.6.2"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/fe/b6/6e630dff89739fcd427e3f72b3d905ce0acb85a45d4ec3e2678718a3487f/pyasn1-0.6.2.tar.gz", hash = "sha256:9b59a2b25ba7e4f8197db7686c09fb33e658b98339fadb826e9512629017833b", size = 146586, upload-time = "2026-01-16T18:04:18.534Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/44/b5/a96872e5184f354da9c84ae119971a0a4c221fe9b27a4d94bd43f2596727/pyasn1-0.6.2-py3-none-any.whl", hash = "sha256:1eb26d860996a18e9b6ed05e7aae0e9fc21619fcee6af91cca9bad4fbea224bf", size = 83371, upload-time = "2026-01-16T18:04:17.174Z" },
]

[[package]]
name = "pybase64"
version = "1.4.3"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/aa/b8/4ed5c7ad5ec15b08d35cc79ace6145d5c1ae426e46435f4987379439dfea/pybase64-1.4.3.tar.gz", hash = "sha256:c2ed274c9e0ba9c8f9c4083cfe265e66dd679126cd9c2027965d807352f3f053", size = 137272, upload-time = "2025-12-06T13:27:04.013Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/2b/63/21e981e9d3f1f123e0b0ee2130112b1956cad9752309f574862c7ae77c08/pybase64-1.4.3-cp311-cp311-macosx_10_9_x86_64.whl", hash = "sha256:70b0d4a4d54e216ce42c2655315378b8903933ecfa32fced453989a92b4317b2", size = 38237, upload-time = "2025-12-06T13:22:52.159Z" },
    { url = "https://files.pythonhosted.org/packages/92/fb/3f448e139516404d2a3963915cc10dc9dde7d3a67de4edba2f827adfef17/pybase64-1.4.3-cp311-cp311-macosx_11_0_arm64.whl", hash = "sha256:8127f110cdee7a70e576c5c9c1d4e17e92e76c191869085efbc50419f4ae3c72", size = 31673, upload-time = "2025-12-06T13:22:53.241Z" },
    { url = "https://files.pythonhosted.org/packages/3c/fb/bb06a5b9885e7d853ac1e801c4d8abfdb4c8506deee33e53d55aa6690e67/pybase64-1.4.3-cp311-cp311-manylinux1_i686.manylinux2014_i686.manylinux_2_17_i686.manylinux_2_5_i686.whl", hash = "sha256:f9ef0388878bc15a084bd9bf73ec1b2b4ee513d11009b1506375e10a7aae5032", size = 68331, upload-time = "2025-12-06T13:22:54.197Z" },
    { url = "https://files.pythonhosted.org/packages/64/15/8d60b9ec5e658185fc2ee3333e01a6e30d717cf677b24f47cbb3a859d13c/pybase64-1.4.3-cp311-cp311-manylinux1_x86_64.manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:95a57cccf106352a72ed8bc8198f6820b16cc7d55aa3867a16dea7011ae7c218", size = 71370, upload-time = "2025-12-06T13:22:55.517Z" },
    { url = "https://files.pythonhosted.org/packages/ac/29/a3e5c1667cc8c38d025a4636855de0fc117fc62e2afeb033a3c6f12c6a22/pybase64-1.4.3-cp311-cp311-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:7cd1c47dfceb9c7bd3de210fb4e65904053ed2d7c9dce6d107f041ff6fbd7e21", size = 59834, upload-time = "2025-12-06T13:22:56.682Z" },
    { url = "https://files.pythonhosted.org/packages/a9/00/8ffcf9810bd23f3984698be161cf7edba656fd639b818039a7be1d6405d4/pybase64-1.4.3-cp311-cp311-manylinux2014_armv7l.manylinux_2_17_armv7l.whl", hash = "sha256:9fe9922698f3e2f72874b26890d53a051c431d942701bb3a37aae94da0b12107", size = 56652, upload-time = "2025-12-06T13:22:57.724Z" },
    { url = "https://files.pythonhosted.org/packages/81/62/379e347797cdea4ab686375945bc77ad8d039c688c0d4d0cfb09d247beb9/pybase64-1.4.3-cp311-cp311-manylinux2014_ppc64le.manylinux_2_17_ppc64le.whl", hash = "sha256:af5f4bd29c86b59bb4375e0491d16ec8a67548fa99c54763aaedaf0b4b5a6632", size = 59382, upload-time = "2025-12-06T13:22:58.758Z" },
    { url = "https://files.pythonhosted.org/packages/c6/f2/9338ffe2f487086f26a2c8ca175acb3baa86fce0a756ff5670a0822bb877/pybase64-1.4.3-cp311-cp311-manylinux2014_s390x.manylinux_2_17_s390x.whl", hash = "sha256:c302f6ca7465262908131411226e02100f488f531bb5e64cb901aa3f439bccd9", size = 59990, upload-time = "2025-12-06T13:23:01.007Z" },
    { url = "https://files.pythonhosted.org/packages/f9/a4/85a6142b65b4df8625b337727aa81dc199642de3d09677804141df6ee312/pybase64-1.4.3-cp311-cp311-manylinux_2_31_riscv64.whl", hash = "sha256:2f3f439fa4d7fde164ebbbb41968db7d66b064450ab6017c6c95cef0afa2b349", size = 54923, upload-time = "2025-12-06T13:23:02.369Z" },
    { url = "https://files.pythonhosted.org/packages/ac/00/e40215d25624012bf5b7416ca37f168cb75f6dd15acdb91ea1f2ea4dc4e7/pybase64-1.4.3-cp311-cp311-musllinux_1_2_aarch64.whl", hash = "sha256:7a23c6866551043f8b681a5e1e0d59469148b2920a3b4fc42b1275f25ea4217a", size = 58664, upload-time = "2025-12-06T13:23:03.378Z" },
    { url = "https://files.pythonhosted.org/packages/b0/73/d7e19a63e795c13837f2356268d95dc79d1180e756f57ced742a1e52fdeb/pybase64-1.4.3-cp311-cp311-musllinux_1_2_armv7l.whl", hash = "sha256:56e6526f8565642abc5f84338cc131ce298a8ccab696b19bdf76fa6d7dc592ef", size = 52338, upload-time = "2025-12-06T13:23:04.458Z" },
    { url = "https://files.pythonhosted.org/packages/f2/32/3c746d7a310b69bdd9df77ffc85c41b80bce00a774717596f869b0d4a20e/pybase64-1.4.3-cp311-cp311-musllinux_1_2_i686.whl", hash = "sha256:6a792a8b9d866ffa413c9687d9b611553203753987a3a582d68cbc51cf23da45", size = 68993, upload-time = "2025-12-06T13:23:05.526Z" },
    { url = "https://files.pythonhosted.org/packages/5d/b3/63cec68f9d6f6e4c0b438d14e5f1ef536a5fe63ce14b70733ac5e31d7ab8/pybase64-1.4.3-cp311-cp311-musllinux_1_2_ppc64le.whl", hash = "sha256:62ad29a5026bb22cfcd1ca484ec34b0a5ced56ddba38ceecd9359b2818c9c4f9", size = 58055, upload-time = "2025-12-06T13:23:06.931Z" },
    { url = "https://files.pythonhosted.org/packages/d5/cb/7acf7c3c06f9692093c07f109668725dc37fb9a3df0fa912b50add645195/pybase64-1.4.3-cp311-cp311-musllinux_1_2_riscv64.whl", hash = "sha256:11b9d1d2d32ec358c02214363b8fc3651f6be7dd84d880ecd597a6206a80e121", size = 54430, upload-time = "2025-12-06T13:23:07.936Z" },
    { url = "https://files.pythonhosted.org/packages/33/39/4eb33ff35d173bfff4002e184ce8907f5d0a42d958d61cd9058ef3570179/pybase64-1.4.3-cp311-cp311-musllinux_1_2_s390x.whl", hash = "sha256:0aebaa7f238caa0a0d373616016e2040c6c879ebce3ba7ab3c59029920f13640", size = 56272, upload-time = "2025-12-06T13:23:09.253Z" },
    { url = "https://files.pythonhosted.org/packages/19/97/a76d65c375a254e65b730c6f56bf528feca91305da32eceab8bcc08591e6/pybase64-1.4.3-cp311-cp311-musllinux_1_2_x86_64.whl", hash = "sha256:e504682b20c63c2b0c000e5f98a80ea867f8d97642e042a5a39818e44ba4d599", size = 70904, upload-time = "2025-12-06T13:23:10.336Z" },
    { url = "https://files.pythonhosted.org/packages/5e/2c/8338b6d3da3c265002839e92af0a80d6db88385c313c73f103dfb800c857/pybase64-1.4.3-cp311-cp311-win32.whl", hash = "sha256:e9a8b81984e3c6fb1db9e1614341b0a2d98c0033d693d90c726677db1ffa3a4c", size = 33639, upload-time = "2025-12-06T13:23:11.9Z" },
    { url = "https://files.pythonhosted.org/packages/39/dc/32efdf2f5927e5449cc341c266a1bbc5fecd5319a8807d9c5405f76e6d02/pybase64-1.4.3-cp311-cp311-win_amd64.whl", hash = "sha256:a90a8fa16a901fabf20de824d7acce07586e6127dc2333f1de05f73b1f848319", size = 35797, upload-time = "2025-12-06T13:23:13.174Z" },
    { url = "https://files.pythonhosted.org/packages/da/59/eda4f9cb0cbce5a45f0cd06131e710674f8123a4d570772c5b9694f88559/pybase64-1.4.3-cp311-cp311-win_arm64.whl", hash = "sha256:61d87de5bc94d143622e94390ec3e11b9c1d4644fe9be3a81068ab0f91056f59", size = 31160, upload-time = "2025-12-06T13:23:15.696Z" },
    { url = "https://files.pythonhosted.org/packages/86/a7/efcaa564f091a2af7f18a83c1c4875b1437db56ba39540451dc85d56f653/pybase64-1.4.3-cp312-cp312-macosx_10_13_x86_64.whl", hash = "sha256:18d85e5ab8b986bb32d8446aca6258ed80d1bafe3603c437690b352c648f5967", size = 38167, upload-time = "2025-12-06T13:23:16.821Z" },
    { url = "https://files.pythonhosted.org/packages/db/c7/c7ad35adff2d272bf2930132db2b3eea8c44bb1b1f64eb9b2b8e57cde7b4/pybase64-1.4.3-cp312-cp312-macosx_11_0_arm64.whl", hash = "sha256:3f5791a3491d116d0deaf4d83268f48792998519698f8751efb191eac84320e9", size = 31673, upload-time = "2025-12-06T13:23:17.835Z" },
    { url = "https://files.pythonhosted.org/packages/43/1b/9a8cab0042b464e9a876d5c65fe5127445a2436da36fda64899b119b1a1b/pybase64-1.4.3-cp312-cp312-manylinux1_i686.manylinux2014_i686.manylinux_2_17_i686.manylinux_2_5_i686.whl", hash = "sha256:f0b3f200c3e06316f6bebabd458b4e4bcd4c2ca26af7c0c766614d91968dee27", size = 68210, upload-time = "2025-12-06T13:23:18.813Z" },
    { url = "https://files.pythonhosted.org/packages/62/f7/965b79ff391ad208b50e412b5d3205ccce372a2d27b7218ae86d5295b105/pybase64-1.4.3-cp312-cp312-manylinux1_x86_64.manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:bb632edfd132b3eaf90c39c89aa314beec4e946e210099b57d40311f704e11d4", size = 71599, upload-time = "2025-12-06T13:23:20.195Z" },
    { url = "https://files.pythonhosted.org/packages/03/4b/a3b5175130b3810bbb8ccfa1edaadbd3afddb9992d877c8a1e2f274b476e/pybase64-1.4.3-cp312-cp312-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:356ef1d74648ce997f5a777cf8f1aefecc1c0b4fe6201e0ef3ec8a08170e1b54", size = 59922, upload-time = "2025-12-06T13:23:21.487Z" },
    { url = "https://files.pythonhosted.org/packages/da/5d/c38d1572027fc601b62d7a407721688b04b4d065d60ca489912d6893e6cf/pybase64-1.4.3-cp312-cp312-manylinux2014_armv7l.manylinux_2_17_armv7l.whl", hash = "sha256:c48361f90db32bacaa5518419d4eb9066ba558013aaf0c7781620279ecddaeb9", size = 56712, upload-time = "2025-12-06T13:23:22.77Z" },
    { url = "https://files.pythonhosted.org/packages/e7/d4/4e04472fef485caa8f561d904d4d69210a8f8fc1608ea15ebd9012b92655/pybase64-1.4.3-cp312-cp312-manylinux2014_ppc64le.manylinux_2_17_ppc64le.whl", hash = "sha256:702bcaa16ae02139d881aeaef5b1c8ffb4a3fae062fe601d1e3835e10310a517", size = 59300, upload-time = "2025-12-06T13:23:24.543Z" },
    { url = "https://files.pythonhosted.org/packages/86/e7/16e29721b86734b881d09b7e23dfd7c8408ad01a4f4c7525f3b1088e25ec/pybase64-1.4.3-cp312-cp312-manylinux2014_s390x.manylinux_2_17_s390x.whl", hash = "sha256:53d0ffe1847b16b647c6413d34d1de08942b7724273dd57e67dcbdb10c574045", size = 60278, upload-time = "2025-12-06T13:23:25.608Z" },
    { url = "https://files.pythonhosted.org/packages/b1/02/18515f211d7c046be32070709a8efeeef8a0203de4fd7521e6b56404731b/pybase64-1.4.3-cp312-cp312-manylinux_2_31_riscv64.whl", hash = "sha256:9a1792e8b830a92736dae58f0c386062eb038dfe8004fb03ba33b6083d89cd43", size = 54817, upload-time = "2025-12-06T13:23:26.633Z" },
    { url = "https://files.pythonhosted.org/packages/e7/be/14e29d8e1a481dbff151324c96dd7b5d2688194bb65dc8a00ca0e1ad1e86/pybase64-1.4.3-cp312-cp312-musllinux_1_2_aarch64.whl", hash = "sha256:1d468b1b1ac5ad84875a46eaa458663c3721e8be5f155ade356406848d3701f6", size = 58611, upload-time = "2025-12-06T13:23:27.684Z" },
    { url = "https://files.pythonhosted.org/packages/b4/8a/a2588dfe24e1bbd742a554553778ab0d65fdf3d1c9a06d10b77047d142aa/pybase64-1.4.3-cp312-cp312-musllinux_1_2_armv7l.whl", hash = "sha256:e97b7bdbd62e71898cd542a6a9e320d9da754ff3ebd02cb802d69087ee94d468", size = 52404, upload-time = "2025-12-06T13:23:28.714Z" },
    { url = "https://files.pythonhosted.org/packages/27/fc/afcda7445bebe0cbc38cafdd7813234cdd4fc5573ff067f1abf317bb0cec/pybase64-1.4.3-cp312-cp312-musllinux_1_2_i686.whl", hash = "sha256:b33aeaa780caaa08ffda87fc584d5eab61e3d3bbb5d86ead02161dc0c20d04bc", size = 68817, upload-time = "2025-12-06T13:23:30.079Z" },
    { url = "https://files.pythonhosted.org/packages/d3/3a/87c3201e555ed71f73e961a787241a2438c2bbb2ca8809c29ddf938a3157/pybase64-1.4.3-cp312-cp312-musllinux_1_2_ppc64le.whl", hash = "sha256:1c0efcf78f11cf866bed49caa7b97552bc4855a892f9cc2372abcd3ed0056f0d", size = 57854, upload-time = "2025-12-06T13:23:31.17Z" },
    { url = "https://files.pythonhosted.org/packages/fd/7d/931c2539b31a7b375e7d595b88401eeb5bd6c5ce1059c9123f9b608aaa14/pybase64-1.4.3-cp312-cp312-musllinux_1_2_riscv64.whl", hash = "sha256:66e3791f2ed725a46593f8bd2761ff37d01e2cdad065b1dceb89066f476e50c6", size = 54333, upload-time = "2025-12-06T13:23:32.422Z" },
    { url = "https://files.pythonhosted.org/packages/de/5e/537601e02cc01f27e9d75f440f1a6095b8df44fc28b1eef2cd739aea8cec/pybase64-1.4.3-cp312-cp312-musllinux_1_2_s390x.whl", hash = "sha256:72bb0b6bddadab26e1b069bb78e83092711a111a80a0d6b9edcb08199ad7299b", size = 56492, upload-time = "2025-12-06T13:23:33.515Z" },
    { url = "https://files.pythonhosted.org/packages/96/97/2a2e57acf8f5c9258d22aba52e71f8050e167b29ed2ee1113677c1b600c1/pybase64-1.4.3-cp312-cp312-musllinux_1_2_x86_64.whl", hash = "sha256:5b3365dbcbcdb0a294f0f50af0c0a16b27a232eddeeb0bceeefd844ef30d2a23", size = 70974, upload-time = "2025-12-06T13:23:36.27Z" },
    { url = "https://files.pythonhosted.org/packages/75/2e/a9e28941c6dab6f06e6d3f6783d3373044be9b0f9a9d3492c3d8d2260ac0/pybase64-1.4.3-cp312-cp312-win32.whl", hash = "sha256:7bca1ed3a5df53305c629ca94276966272eda33c0d71f862d2d3d043f1e1b91a", size = 33686, upload-time = "2025-12-06T13:23:37.848Z" },
    { url = "https://files.pythonhosted.org/packages/83/e3/507ab649d8c3512c258819c51d25c45d6e29d9ca33992593059e7b646a33/pybase64-1.4.3-cp312-cp312-win_amd64.whl", hash = "sha256:9f2da8f56d9b891b18b4daf463a0640eae45a80af548ce435be86aa6eff3603b", size = 35833, upload-time = "2025-12-06T13:23:38.877Z" },
    { url = "https://files.pythonhosted.org/packages/bc/8a/6eba66cd549a2fc74bb4425fd61b839ba0ab3022d3c401b8a8dc2cc00c7a/pybase64-1.4.3-cp312-cp312-win_arm64.whl", hash = "sha256:0631d8a2d035de03aa9bded029b9513e1fee8ed80b7ddef6b8e9389ffc445da0", size = 31185, upload-time = "2025-12-06T13:23:39.908Z" },
    { url = "https://files.pythonhosted.org/packages/3a/50/b7170cb2c631944388fe2519507fe3835a4054a6a12a43f43781dae82be1/pybase64-1.4.3-cp313-cp313-android_21_arm64_v8a.whl", hash = "sha256:ea4b785b0607d11950b66ce7c328f452614aefc9c6d3c9c28bae795dc7f072e1", size = 33901, upload-time = "2025-12-06T13:23:40.951Z" },
    { url = "https://files.pythonhosted.org/packages/48/8b/69f50578e49c25e0a26e3ee72c39884ff56363344b79fc3967f5af420ed6/pybase64-1.4.3-cp313-cp313-android_21_x86_64.whl", hash = "sha256:6a10b6330188c3026a8b9c10e6b9b3f2e445779cf16a4c453d51a072241c65a2", size = 40807, upload-time = "2025-12-06T13:23:42.006Z" },
    { url = "https://files.pythonhosted.org/packages/5c/8d/20b68f11adfc4c22230e034b65c71392e3e338b413bf713c8945bd2ccfb3/pybase64-1.4.3-cp313-cp313-ios_13_0_arm64_iphoneos.whl", hash = "sha256:27fdff227a0c0e182e0ba37a99109645188978b920dfb20d8b9c17eeee370d0d", size = 30932, upload-time = "2025-12-06T13:23:43.348Z" },
    { url = "https://files.pythonhosted.org/packages/f7/79/b1b550ac6bff51a4880bf6e089008b2e1ca16f2c98db5e039a08ac3ad157/pybase64-1.4.3-cp313-cp313-ios_13_0_arm64_iphonesimulator.whl", hash = "sha256:2a8204f1fdfec5aa4184249b51296c0de95445869920c88123978304aad42df1", size = 31394, upload-time = "2025-12-06T13:23:44.317Z" },
    { url = "https://files.pythonhosted.org/packages/82/70/b5d7c5932bf64ee1ec5da859fbac981930b6a55d432a603986c7f509c838/pybase64-1.4.3-cp313-cp313-ios_13_0_x86_64_iphonesimulator.whl", hash = "sha256:874fc2a3777de6baf6aa921a7aa73b3be98295794bea31bd80568a963be30767", size = 38078, upload-time = "2025-12-06T13:23:45.348Z" },
    { url = "https://files.pythonhosted.org/packages/56/fe/e66fe373bce717c6858427670736d54297938dad61c5907517ab4106bd90/pybase64-1.4.3-cp313-cp313-macosx_10_13_x86_64.whl", hash = "sha256:2dc64a94a9d936b8e3449c66afabbaa521d3cc1a563d6bbaaa6ffa4535222e4b", size = 38158, upload-time = "2025-12-06T13:23:46.872Z" },
    { url = "https://files.pythonhosted.org/packages/80/a9/b806ed1dcc7aed2ea3dd4952286319e6f3a8b48615c8118f453948e01999/pybase64-1.4.3-cp313-cp313-macosx_11_0_arm64.whl", hash = "sha256:e48f86de1c145116ccf369a6e11720ce696c2ec02d285f440dfb57ceaa0a6cb4", size = 31672, upload-time = "2025-12-06T13:23:47.88Z" },
    { url = "https://files.pythonhosted.org/packages/1c/c9/24b3b905cf75e23a9a4deaf203b35ffcb9f473ac0e6d8257f91a05dfce62/pybase64-1.4.3-cp313-cp313-manylinux1_i686.manylinux2014_i686.manylinux_2_17_i686.manylinux_2_5_i686.whl", hash = "sha256:1d45c8fe8fe82b65c36b227bb4a2cf623d9ada16bed602ce2d3e18c35285b72a", size = 68244, upload-time = "2025-12-06T13:23:49.026Z" },
    { url = "https://files.pythonhosted.org/packages/f8/cd/d15b0c3e25e5859fab0416dc5b96d34d6bd2603c1c96a07bb2202b68ab92/pybase64-1.4.3-cp313-cp313-manylinux1_x86_64.manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:ad70c26ba091d8f5167e9d4e1e86a0483a5414805cdb598a813db635bd3be8b8", size = 71620, upload-time = "2025-12-06T13:23:50.081Z" },
    { url = "https://files.pythonhosted.org/packages/0d/31/4ca953cc3dcde2b3711d6bfd70a6f4ad2ca95a483c9698076ba605f1520f/pybase64-1.4.3-cp313-cp313-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:e98310b7c43145221e7194ac9fa7fffc84763c87bfc5e2f59f9f92363475bdc1", size = 59930, upload-time = "2025-12-06T13:23:51.68Z" },
    { url = "https://files.pythonhosted.org/packages/60/55/e7f7bdcd0fd66e61dda08db158ffda5c89a306bbdaaf5a062fbe4e48f4a1/pybase64-1.4.3-cp313-cp313-manylinux2014_armv7l.manylinux_2_17_armv7l.whl", hash = "sha256:398685a76034e91485a28aeebcb49e64cd663212fd697b2497ac6dfc1df5e671", size = 56425, upload-time = "2025-12-06T13:23:52.732Z" },
    { url = "https://files.pythonhosted.org/packages/cb/65/b592c7f921e51ca1aca3af5b0d201a98666d0a36b930ebb67e7c2ed27395/pybase64-1.4.3-cp313-cp313-manylinux2014_ppc64le.manylinux_2_17_ppc64le.whl", hash = "sha256:7e46400a6461187ccb52ed75b0045d937529e801a53a9cd770b350509f9e4d50", size = 59327, upload-time = "2025-12-06T13:23:53.856Z" },
    { url = "https://files.pythonhosted.org/packages/23/95/1613d2fb82dbb1548595ad4179f04e9a8451bfa18635efce18b631eabe3f/pybase64-1.4.3-cp313-cp313-manylinux2014_s390x.manylinux_2_17_s390x.whl", hash = "sha256:1b62b9f2f291d94f5e0b76ab499790b7dcc78a009d4ceea0b0428770267484b6", size = 60294, upload-time = "2025-12-06T13:23:54.937Z" },
    { url = "https://files.pythonhosted.org/packages/9d/73/40431f37f7d1b3eab4673e7946ff1e8f5d6bd425ec257e834dae8a6fc7b0/pybase64-1.4.3-cp313-cp313-manylinux_2_31_riscv64.whl", hash = "sha256:f30ceb5fa4327809dede614be586efcbc55404406d71e1f902a6fdcf322b93b2", size = 54858, upload-time = "2025-12-06T13:23:56.031Z" },
    { url = "https://files.pythonhosted.org/packages/a7/84/f6368bcaf9f743732e002a9858646fd7a54f428490d427dd6847c5cfe89e/pybase64-1.4.3-cp313-cp313-musllinux_1_2_aarch64.whl", hash = "sha256:0d5f18ed53dfa1d4cf8b39ee542fdda8e66d365940e11f1710989b3cf4a2ed66", size = 58629, upload-time = "2025-12-06T13:23:57.12Z" },
    { url = "https://files.pythonhosted.org/packages/43/75/359532f9adb49c6b546cafc65c46ed75e2ccc220d514ba81c686fbd83965/pybase64-1.4.3-cp313-cp313-musllinux_1_2_armv7l.whl", hash = "sha256:119d31aa4b58b85a8ebd12b63c07681a138c08dfc2fe5383459d42238665d3eb", size = 52448, upload-time = "2025-12-06T13:23:58.298Z" },
    { url = "https://files.pythonhosted.org/packages/92/6c/ade2ba244c3f33ed920a7ed572ad772eb0b5f14480b72d629d0c9e739a40/pybase64-1.4.3-cp313-cp313-musllinux_1_2_i686.whl", hash = "sha256:3cf0218b0e2f7988cf7d738a73b6a1d14f3be6ce249d7c0f606e768366df2cce", size = 68841, upload-time = "2025-12-06T13:23:59.886Z" },
    { url = "https://files.pythonhosted.org/packages/a0/51/b345139cd236be382f2d4d4453c21ee6299e14d2f759b668e23080f8663f/pybase64-1.4.3-cp313-cp313-musllinux_1_2_ppc64le.whl", hash = "sha256:12f4ee5e988bc5c0c1106b0d8fc37fb0508f12dab76bac1b098cb500d148da9d", size = 57910, upload-time = "2025-12-06T13:24:00.994Z" },
    { url = "https://files.pythonhosted.org/packages/1a/b8/9f84bdc4f1c4f0052489396403c04be2f9266a66b70c776001eaf0d78c1f/pybase64-1.4.3-cp313-cp313-musllinux_1_2_riscv64.whl", hash = "sha256:937826bc7b6b95b594a45180e81dd4d99bd4dd4814a443170e399163f7ff3fb6", size = 54335, upload-time = "2025-12-06T13:24:02.046Z" },
    { url = "https://files.pythonhosted.org/packages/d0/c7/be63b617d284de46578a366da77ede39c8f8e815ed0d82c7c2acca560fab/pybase64-1.4.3-cp313-cp313-musllinux_1_2_s390x.whl", hash = "sha256:88995d1460971ef80b13e3e007afbe4b27c62db0508bc7250a2ab0a0b4b91362", size = 56486, upload-time = "2025-12-06T13:24:03.141Z" },
    { url = "https://files.pythonhosted.org/packages/5e/96/f252c8f9abd6ded3ef1ccd3cdbb8393a33798007f761b23df8de1a2480e6/pybase64-1.4.3-cp313-cp313-musllinux_1_2_x86_64.whl", hash = "sha256:72326fe163385ed3e1e806dd579d47fde5d8a59e51297a60fc4e6cbc1b4fc4ed", size = 70978, upload-time = "2025-12-06T13:24:04.221Z" },
    { url = "https://files.pythonhosted.org/packages/af/51/0f5714af7aeef96e30f968e4371d75ad60558aaed3579d7c6c8f1c43c18a/pybase64-1.4.3-cp313-cp313-win32.whl", hash = "sha256:b1623730c7892cf5ed0d6355e375416be6ef8d53ab9b284f50890443175c0ac3", size = 33684, upload-time = "2025-12-06T13:24:05.29Z" },
    { url = "https://files.pythonhosted.org/packages/b6/ad/0cea830a654eb08563fb8214150ef57546ece1cc421c09035f0e6b0b5ea9/pybase64-1.4.3-cp313-cp313-win_amd64.whl", hash = "sha256:8369887590f1646a5182ca2fb29252509da7ae31d4923dbb55d3e09da8cc4749", size = 35832, upload-time = "2025-12-06T13:24:06.35Z" },
    { url = "https://files.pythonhosted.org/packages/b4/0d/eec2a8214989c751bc7b4cad1860eb2c6abf466e76b77508c0f488c96a37/pybase64-1.4.3-cp313-cp313-win_arm64.whl", hash = "sha256:860b86bca71e5f0237e2ab8b2d9c4c56681f3513b1bf3e2117290c1963488390", size = 31175, upload-time = "2025-12-06T13:24:07.419Z" },
    { url = "https://files.pythonhosted.org/packages/db/c9/e23463c1a2913686803ef76b1a5ae7e6fac868249a66e48253d17ad7232c/pybase64-1.4.3-cp313-cp313t-macosx_10_13_x86_64.whl", hash = "sha256:eb51db4a9c93215135dccd1895dca078e8785c357fabd983c9f9a769f08989a9", size = 38497, upload-time = "2025-12-06T13:24:08.873Z" },
    { url = "https://files.pythonhosted.org/packages/71/83/343f446b4b7a7579bf6937d2d013d82f1a63057cf05558e391ab6039d7db/pybase64-1.4.3-cp313-cp313t-macosx_11_0_arm64.whl", hash = "sha256:a03ef3f529d85fd46b89971dfb00c634d53598d20ad8908fb7482955c710329d", size = 32076, upload-time = "2025-12-06T13:24:09.975Z" },
    { url = "https://files.pythonhosted.org/packages/46/fc/cb64964c3b29b432f54d1bce5e7691d693e33bbf780555151969ffd95178/pybase64-1.4.3-cp313-cp313t-manylinux1_i686.manylinux2014_i686.manylinux_2_17_i686.manylinux_2_5_i686.whl", hash = "sha256:2e745f2ce760c6cf04d8a72198ef892015ddb89f6ceba489e383518ecbdb13ab", size = 72317, upload-time = "2025-12-06T13:24:11.129Z" },
    { url = "https://files.pythonhosted.org/packages/0a/b7/fab2240da6f4e1ad46f71fa56ec577613cf5df9dce2d5b4cfaa4edd0e365/pybase64-1.4.3-cp313-cp313t-manylinux1_x86_64.manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:6fac217cd9de8581a854b0ac734c50fd1fa4b8d912396c1fc2fce7c230efe3a7", size = 75534, upload-time = "2025-12-06T13:24:12.433Z" },
    { url = "https://files.pythonhosted.org/packages/91/3b/3e2f2b6e68e3d83ddb9fa799f3548fb7449765daec9bbd005a9fbe296d7f/pybase64-1.4.3-cp313-cp313t-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:da1ee8fa04b283873de2d6e8fa5653e827f55b86bdf1a929c5367aaeb8d26f8a", size = 65399, upload-time = "2025-12-06T13:24:13.928Z" },
    { url = "https://files.pythonhosted.org/packages/6b/08/476ac5914c3b32e0274a2524fc74f01cbf4f4af4513d054e41574eb018f6/pybase64-1.4.3-cp313-cp313t-manylinux2014_armv7l.manylinux_2_17_armv7l.whl", hash = "sha256:b0bf8e884ee822ca7b1448eeb97fa131628fe0ff42f60cae9962789bd562727f", size = 60487, upload-time = "2025-12-06T13:24:15.177Z" },
    { url = "https://files.pythonhosted.org/packages/f1/b8/618a92915330cc9cba7880299b546a1d9dab1a21fd6c0292ee44a4fe608c/pybase64-1.4.3-cp313-cp313t-manylinux2014_ppc64le.manylinux_2_17_ppc64le.whl", hash = "sha256:1bf749300382a6fd1f4f255b183146ef58f8e9cb2f44a077b3a9200dfb473a77", size = 63959, upload-time = "2025-12-06T13:24:16.854Z" },
    { url = "https://files.pythonhosted.org/packages/a5/52/af9d8d051652c3051862c442ec3861259c5cdb3fc69774bc701470bd2a59/pybase64-1.4.3-cp313-cp313t-manylinux2014_s390x.manylinux_2_17_s390x.whl", hash = "sha256:153a0e42329b92337664cfc356f2065248e6c9a1bd651bbcd6dcaf15145d3f06", size = 64874, upload-time = "2025-12-06T13:24:18.328Z" },
    { url = "https://files.pythonhosted.org/packages/e4/51/5381a7adf1f381bd184d33203692d3c57cf8ae9f250f380c3fecbdbe554b/pybase64-1.4.3-cp313-cp313t-manylinux_2_31_riscv64.whl", hash = "sha256:86ee56ac7f2184ca10217ed1c655c1a060273e233e692e9086da29d1ae1768db", size = 58572, upload-time = "2025-12-06T13:24:19.417Z" },
    { url = "https://files.pythonhosted.org/packages/e0/f0/578ee4ffce5818017de4fdf544e066c225bc435e73eb4793cde28a689d0b/pybase64-1.4.3-cp313-cp313t-musllinux_1_2_aarch64.whl", hash = "sha256:0e71a4db76726bf830b47477e7d830a75c01b2e9b01842e787a0836b0ba741e3", size = 63636, upload-time = "2025-12-06T13:24:20.497Z" },
    { url = "https://files.pythonhosted.org/packages/b9/ad/8ae94814bf20159ea06310b742433e53d5820aa564c9fdf65bf2d79f8799/pybase64-1.4.3-cp313-cp313t-musllinux_1_2_armv7l.whl", hash = "sha256:2ba7799ec88540acd9861b10551d24656ca3c2888ecf4dba2ee0a71544a8923f", size = 56193, upload-time = "2025-12-06T13:24:21.559Z" },
    { url = "https://files.pythonhosted.org/packages/d1/31/6438cfcc3d3f0fa84d229fa125c243d5094e72628e525dfefadf3bcc6761/pybase64-1.4.3-cp313-cp313t-musllinux_1_2_i686.whl", hash = "sha256:2860299e4c74315f5951f0cf3e72ba0f201c3356c8a68f95a3ab4e620baf44e9", size = 72655, upload-time = "2025-12-06T13:24:22.673Z" },
    { url = "https://files.pythonhosted.org/packages/a3/0d/2bbc9e9c3fc12ba8a6e261482f03a544aca524f92eae0b4908c0a10ba481/pybase64-1.4.3-cp313-cp313t-musllinux_1_2_ppc64le.whl", hash = "sha256:bb06015db9151f0c66c10aae8e3603adab6b6cd7d1f7335a858161d92fc29618", size = 62471, upload-time = "2025-12-06T13:24:23.8Z" },
    { url = "https://files.pythonhosted.org/packages/2c/0b/34d491e7f49c1dbdb322ea8da6adecda7c7cd70b6644557c6e4ca5c6f7c7/pybase64-1.4.3-cp313-cp313t-musllinux_1_2_riscv64.whl", hash = "sha256:242512a070817272865d37c8909059f43003b81da31f616bb0c391ceadffe067", size = 58119, upload-time = "2025-12-06T13:24:24.994Z" },
    { url = "https://files.pythonhosted.org/packages/ce/17/c21d0cde2a6c766923ae388fc1f78291e1564b0d38c814b5ea8a0e5e081c/pybase64-1.4.3-cp313-cp313t-musllinux_1_2_s390x.whl", hash = "sha256:5d8277554a12d3e3eed6180ebda62786bf9fc8d7bb1ee00244258f4a87ca8d20", size = 60791, upload-time = "2025-12-06T13:24:26.046Z" },
    { url = "https://files.pythonhosted.org/packages/92/b2/eaa67038916a48de12b16f4c384bcc1b84b7ec731b23613cb05f27673294/pybase64-1.4.3-cp313-cp313t-musllinux_1_2_x86_64.whl", hash = "sha256:f40b7ddd698fc1e13a4b64fbe405e4e0e1279e8197e37050e24154655f5f7c4e", size = 74701, upload-time = "2025-12-06T13:24:27.466Z" },
    { url = "https://files.pythonhosted.org/packages/42/10/abb7757c330bb869ebb95dab0c57edf5961ffbd6c095c8209cbbf75d117d/pybase64-1.4.3-cp313-cp313t-win32.whl", hash = "sha256:46d75c9387f354c5172582a9eaae153b53a53afeb9c19fcf764ea7038be3bd8b", size = 33965, upload-time = "2025-12-06T13:24:28.548Z" },
    { url = "https://files.pythonhosted.org/packages/63/a0/2d4e5a59188e9e6aed0903d580541aaea72dcbbab7bf50fb8b83b490b6c3/pybase64-1.4.3-cp313-cp313t-win_amd64.whl", hash = "sha256:d7344625591d281bec54e85cbfdab9e970f6219cac1570f2aa140b8c942ccb81", size = 36207, upload-time = "2025-12-06T13:24:29.646Z" },
    { url = "https://files.pythonhosted.org/packages/1f/05/95b902e8f567b4d4b41df768ccc438af618f8d111e54deaf57d2df46bd76/pybase64-1.4.3-cp313-cp313t-win_arm64.whl", hash = "sha256:28a3c60c55138e0028313f2eccd321fec3c4a0be75e57a8d3eb883730b1b0880", size = 31505, upload-time = "2025-12-06T13:24:30.687Z" },
    { url = "https://files.pythonhosted.org/packages/e4/80/4bd3dff423e5a91f667ca41982dc0b79495b90ec0c0f5d59aca513e50f8c/pybase64-1.4.3-cp314-cp314-android_24_arm64_v8a.whl", hash = "sha256:015bb586a1ea1467f69d57427abe587469392215f59db14f1f5c39b52fdafaf5", size = 33835, upload-time = "2025-12-06T13:24:31.767Z" },
    { url = "https://files.pythonhosted.org/packages/45/60/a94d94cc1e3057f602e0b483c9ebdaef40911d84a232647a2fe593ab77bb/pybase64-1.4.3-cp314-cp314-android_24_x86_64.whl", hash = "sha256:d101e3a516f837c3dcc0e5a0b7db09582ebf99ed670865223123fb2e5839c6c0", size = 40673, upload-time = "2025-12-06T13:24:32.82Z" },
    { url = "https://files.pythonhosted.org/packages/e3/71/cf62b261d431857e8e054537a5c3c24caafa331de30daede7b2c6c558501/pybase64-1.4.3-cp314-cp314-ios_13_0_arm64_iphoneos.whl", hash = "sha256:8f183ac925a48046abe047360fe3a1b28327afb35309892132fe1915d62fb282", size = 30939, upload-time = "2025-12-06T13:24:34.001Z" },
    { url = "https://files.pythonhosted.org/packages/24/3e/d12f92a3c1f7c6ab5d53c155bff9f1084ba997a37a39a4f781ccba9455f3/pybase64-1.4.3-cp314-cp314-ios_13_0_arm64_iphonesimulator.whl", hash = "sha256:30bf3558e24dcce4da5248dcf6d73792adfcf4f504246967e9db155be4c439ad", size = 31401, upload-time = "2025-12-06T13:24:35.11Z" },
    { url = "https://files.pythonhosted.org/packages/9b/3d/9c27440031fea0d05146f8b70a460feb95d8b4e3d9ca8f45c972efb4c3d3/pybase64-1.4.3-cp314-cp314-ios_13_0_x86_64_iphonesimulator.whl", hash = "sha256:a674b419de318d2ce54387dd62646731efa32b4b590907800f0bd40675c1771d", size = 38075, upload-time = "2025-12-06T13:24:36.53Z" },
    { url = "https://files.pythonhosted.org/packages/4b/d4/6c0e0cf0efd53c254173fbcd84a3d8fcbf5e0f66622473da425becec32a5/pybase64-1.4.3-cp314-cp314-macosx_10_15_x86_64.whl", hash = "sha256:720104fd7303d07bac302be0ff8f7f9f126f2f45c1edb4f48fdb0ff267e69fe1", size = 38257, upload-time = "2025-12-06T13:24:38.049Z" },
    { url = "https://files.pythonhosted.org/packages/50/eb/27cb0b610d5cd70f5ad0d66c14ad21c04b8db930f7139818e8fbdc14df4d/pybase64-1.4.3-cp314-cp314-macosx_11_0_arm64.whl", hash = "sha256:83f1067f73fa5afbc3efc0565cecc6ed53260eccddef2ebe43a8ce2b99ea0e0a", size = 31685, upload-time = "2025-12-06T13:24:40.327Z" },
    { url = "https://files.pythonhosted.org/packages/db/26/b136a4b65e5c94ff06217f7726478df3f31ab1c777c2c02cf698e748183f/pybase64-1.4.3-cp314-cp314-manylinux1_i686.manylinux2014_i686.manylinux_2_17_i686.manylinux_2_5_i686.whl", hash = "sha256:b51204d349a4b208287a8aa5b5422be3baa88abf6cc8ff97ccbda34919bbc857", size = 68460, upload-time = "2025-12-06T13:24:41.735Z" },
    { url = "https://files.pythonhosted.org/packages/68/6d/84ce50e7ee1ae79984d689e05a9937b2460d4efa1e5b202b46762fb9036c/pybase64-1.4.3-cp314-cp314-manylinux1_x86_64.manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:30f2fd53efecbdde4bdca73a872a68dcb0d1bf8a4560c70a3e7746df973e1ef3", size = 71688, upload-time = "2025-12-06T13:24:42.908Z" },
    { url = "https://files.pythonhosted.org/packages/e3/57/6743e420416c3ff1b004041c85eb0ebd9c50e9cf05624664bfa1dc8b5625/pybase64-1.4.3-cp314-cp314-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:0932b0c5cfa617091fd74f17d24549ce5de3628791998c94ba57be808078eeaf", size = 60040, upload-time = "2025-12-06T13:24:44.37Z" },
    { url = "https://files.pythonhosted.org/packages/3b/68/733324e28068a89119af2921ce548e1c607cc5c17d354690fc51c302e326/pybase64-1.4.3-cp314-cp314-manylinux2014_armv7l.manylinux_2_17_armv7l.whl", hash = "sha256:acb61f5ab72bec808eb0d4ce8b87ec9f38d7d750cb89b1371c35eb8052a29f11", size = 56478, upload-time = "2025-12-06T13:24:45.815Z" },
    { url = "https://files.pythonhosted.org/packages/b5/9e/f3f4aa8cfe3357a3cdb0535b78eb032b671519d3ecc08c58c4c6b72b5a91/pybase64-1.4.3-cp314-cp314-manylinux2014_ppc64le.manylinux_2_17_ppc64le.whl", hash = "sha256:2bc2d5bc15168f5c04c53bdfe5a1e543b2155f456ed1e16d7edce9ce73842021", size = 59463, upload-time = "2025-12-06T13:24:46.938Z" },
    { url = "https://files.pythonhosted.org/packages/aa/d1/53286038e1f0df1cf58abcf4a4a91b0f74ab44539c2547b6c31001ddd054/pybase64-1.4.3-cp314-cp314-manylinux2014_s390x.manylinux_2_17_s390x.whl", hash = "sha256:8a7bc3cd23880bdca59758bcdd6f4ef0674f2393782763910a7466fab35ccb98", size = 60360, upload-time = "2025-12-06T13:24:48.039Z" },
    { url = "https://files.pythonhosted.org/packages/00/9a/5cc6ce95db2383d27ff4d790b8f8b46704d360d701ab77c4f655bcfaa6a7/pybase64-1.4.3-cp314-cp314-manylinux_2_31_riscv64.whl", hash = "sha256:ad15acf618880d99792d71e3905b0e2508e6e331b76a1b34212fa0f11e01ad28", size = 54999, upload-time = "2025-12-06T13:24:49.547Z" },
    { url = "https://files.pythonhosted.org/packages/64/e7/c3c1d09c3d7ae79e3aa1358c6d912d6b85f29281e47aa94fc0122a415a2f/pybase64-1.4.3-cp314-cp314-musllinux_1_2_aarch64.whl", hash = "sha256:448158d417139cb4851200e5fee62677ae51f56a865d50cda9e0d61bda91b116", size = 58736, upload-time = "2025-12-06T13:24:50.641Z" },
    { url = "https://files.pythonhosted.org/packages/db/d5/0baa08e3d8119b15b588c39f0d39fd10472f0372e3c54ca44649cbefa256/pybase64-1.4.3-cp314-cp314-musllinux_1_2_armv7l.whl", hash = "sha256:9058c49b5a2f3e691b9db21d37eb349e62540f9f5fc4beabf8cbe3c732bead86", size = 52298, upload-time = "2025-12-06T13:24:51.791Z" },
    { url = "https://files.pythonhosted.org/packages/00/87/fc6f11474a1de7e27cd2acbb8d0d7508bda3efa73dfe91c63f968728b2a3/pybase64-1.4.3-cp314-cp314-musllinux_1_2_i686.whl", hash = "sha256:ce561724f6522907a66303aca27dce252d363fcd85884972d348f4403ba3011a", size = 69049, upload-time = "2025-12-06T13:24:53.253Z" },
    { url = "https://files.pythonhosted.org/packages/69/9d/7fb5566f669ac18b40aa5fc1c438e24df52b843c1bdc5da47d46d4c1c630/pybase64-1.4.3-cp314-cp314-musllinux_1_2_ppc64le.whl", hash = "sha256:63316560a94ac449fe86cb8b9e0a13714c659417e92e26a5cbf085cd0a0c838d", size = 57952, upload-time = "2025-12-06T13:24:54.342Z" },
    { url = "https://files.pythonhosted.org/packages/de/cc/ceb949232dbbd3ec4ee0190d1df4361296beceee9840390a63df8bc31784/pybase64-1.4.3-cp314-cp314-musllinux_1_2_riscv64.whl", hash = "sha256:7ecd796f2ac0be7b73e7e4e232b8c16422014de3295d43e71d2b19fd4a4f5368", size = 54484, upload-time = "2025-12-06T13:24:55.774Z" },
    { url = "https://files.pythonhosted.org/packages/a7/69/659f3c8e6a5d7b753b9c42a4bd9c42892a0f10044e9c7351a4148d413a33/pybase64-1.4.3-cp314-cp314-musllinux_1_2_s390x.whl", hash = "sha256:d01e102a12fb2e1ed3dc11611c2818448626637857ec3994a9cf4809dfd23477", size = 56542, upload-time = "2025-12-06T13:24:57Z" },
    { url = "https://files.pythonhosted.org/packages/85/2c/29c9e6c9c82b72025f9676f9e82eb1fd2339ad038cbcbf8b9e2ac02798fc/pybase64-1.4.3-cp314-cp314-musllinux_1_2_x86_64.whl", hash = "sha256:ebff797a93c2345f22183f454fd8607a34d75eca5a3a4a969c1c75b304cee39d", size = 71045, upload-time = "2025-12-06T13:24:58.179Z" },
    { url = "https://files.pythonhosted.org/packages/b9/84/5a3dce8d7a0040a5c0c14f0fe1311cd8db872913fa04438071b26b0dac04/pybase64-1.4.3-cp314-cp314-win32.whl", hash = "sha256:28b2a1bb0828c0595dc1ea3336305cd97ff85b01c00d81cfce4f92a95fb88f56", size = 34200, upload-time = "2025-12-06T13:24:59.956Z" },
    { url = "https://files.pythonhosted.org/packages/57/bc/ce7427c12384adee115b347b287f8f3cf65860b824d74fe2c43e37e81c1f/pybase64-1.4.3-cp314-cp314-win_amd64.whl", hash = "sha256:33338d3888700ff68c3dedfcd49f99bfc3b887570206130926791e26b316b029", size = 36323, upload-time = "2025-12-06T13:25:01.708Z" },
    { url = "https://files.pythonhosted.org/packages/9a/1b/2b8ffbe9a96eef7e3f6a5a7be75995eebfb6faaedc85b6da6b233e50c778/pybase64-1.4.3-cp314-cp314-win_arm64.whl", hash = "sha256:62725669feb5acb186458da2f9353e88ae28ef66bb9c4c8d1568b12a790dfa94", size = 31584, upload-time = "2025-12-06T13:25:02.801Z" },
    { url = "https://files.pythonhosted.org/packages/ac/d8/6824c2e6fb45b8fa4e7d92e3c6805432d5edc7b855e3e8e1eedaaf6efb7c/pybase64-1.4.3-cp314-cp314t-macosx_10_15_x86_64.whl", hash = "sha256:153fe29be038948d9372c3e77ae7d1cab44e4ba7d9aaf6f064dbeea36e45b092", size = 38601, upload-time = "2025-12-06T13:25:04.222Z" },
    { url = "https://files.pythonhosted.org/packages/ea/e5/10d2b3a4ad3a4850be2704a2f70cd9c0cf55725c8885679872d3bc846c67/pybase64-1.4.3-cp314-cp314t-macosx_11_0_arm64.whl", hash = "sha256:f7fe3decaa7c4a9e162327ec7bd81ce183d2b16f23c6d53b606649c6e0203e9e", size = 32078, upload-time = "2025-12-06T13:25:05.362Z" },
    { url = "https://files.pythonhosted.org/packages/43/04/8b15c34d3c2282f1c1b0850f1113a249401b618a382646a895170bc9b5e7/pybase64-1.4.3-cp314-cp314t-manylinux1_i686.manylinux2014_i686.manylinux_2_17_i686.manylinux_2_5_i686.whl", hash = "sha256:a5ae04ea114c86eb1da1f6e18d75f19e3b5ae39cb1d8d3cd87c29751a6a22780", size = 72474, upload-time = "2025-12-06T13:25:06.434Z" },
    { url = "https://files.pythonhosted.org/packages/42/00/f34b4d11278f8fdc68bc38f694a91492aa318f7c6f1bd7396197ac0f8b12/pybase64-1.4.3-cp314-cp314t-manylinux1_x86_64.manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:1755b3dce3a2a5c7d17ff6d4115e8bee4a1d5aeae74469db02e47c8f477147da", size = 75706, upload-time = "2025-12-06T13:25:07.636Z" },
    { url = "https://files.pythonhosted.org/packages/bb/5d/71747d4ad7fe16df4c4c852bdbdeb1f2cf35677b48d7c34d3011a7a6ad3a/pybase64-1.4.3-cp314-cp314t-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:fb852f900e27ffc4ec1896817535a0fa19610ef8875a096b59f21d0aa42ff172", size = 65589, upload-time = "2025-12-06T13:25:08.809Z" },
    { url = "https://files.pythonhosted.org/packages/49/b1/d1e82bd58805bb5a3a662864800bab83a83a36ba56e7e3b1706c708002a5/pybase64-1.4.3-cp314-cp314t-manylinux2014_armv7l.manylinux_2_17_armv7l.whl", hash = "sha256:9cf21ea8c70c61eddab3421fbfce061fac4f2fb21f7031383005a1efdb13d0b9", size = 60670, upload-time = "2025-12-06T13:25:10.04Z" },
    { url = "https://files.pythonhosted.org/packages/15/67/16c609b7a13d1d9fc87eca12ba2dce5e67f949eeaab61a41bddff843cbb0/pybase64-1.4.3-cp314-cp314t-manylinux2014_ppc64le.manylinux_2_17_ppc64le.whl", hash = "sha256:afff11b331fdc27692fc75e85ae083340a35105cea1a3c4552139e2f0e0d174f", size = 64194, upload-time = "2025-12-06T13:25:11.48Z" },
    { url = "https://files.pythonhosted.org/packages/3c/11/37bc724e42960f0106c2d33dc957dcec8f760c91a908cc6c0df7718bc1a8/pybase64-1.4.3-cp314-cp314t-manylinux2014_s390x.manylinux_2_17_s390x.whl", hash = "sha256:d9a5143df542c1ce5c1f423874b948c4d689b3f05ec571f8792286197a39ba02", size = 64984, upload-time = "2025-12-06T13:25:12.645Z" },
    { url = "https://files.pythonhosted.org/packages/6e/66/b2b962a6a480dd5dae3029becf03ea1a650d326e39bf1c44ea3db78bb010/pybase64-1.4.3-cp314-cp314t-manylinux_2_31_riscv64.whl", hash = "sha256:d62e9861019ad63624b4a7914dff155af1cc5d6d79df3be14edcaedb5fdad6f9", size = 58750, upload-time = "2025-12-06T13:25:13.848Z" },
    { url = "https://files.pythonhosted.org/packages/2b/15/9b6d711035e29b18b2e1c03d47f41396d803d06ef15b6c97f45b75f73f04/pybase64-1.4.3-cp314-cp314t-musllinux_1_2_aarch64.whl", hash = "sha256:84cfd4d92668ef5766cc42a9c9474b88960ac2b860767e6e7be255c6fddbd34a", size = 63816, upload-time = "2025-12-06T13:25:15.356Z" },
    { url = "https://files.pythonhosted.org/packages/b4/21/e2901381ed0df62e2308380f30d9c4d87d6b74e33a84faed3478d33a7197/pybase64-1.4.3-cp314-cp314t-musllinux_1_2_armv7l.whl", hash = "sha256:60fc025437f9a7c2cc45e0c19ed68ed08ba672be2c5575fd9d98bdd8f01dd61f", size = 56348, upload-time = "2025-12-06T13:25:16.559Z" },
    { url = "https://files.pythonhosted.org/packages/c4/16/3d788388a178a0407aa814b976fe61bfa4af6760d9aac566e59da6e4a8b4/pybase64-1.4.3-cp314-cp314t-musllinux_1_2_i686.whl", hash = "sha256:edc8446196f04b71d3af76c0bd1fe0a45066ac5bffecca88adb9626ee28c266f", size = 72842, upload-time = "2025-12-06T13:25:18.055Z" },
    { url = "https://files.pythonhosted.org/packages/a6/63/c15b1f8bd47ea48a5a2d52a4ec61f037062932ea6434ab916107b58e861e/pybase64-1.4.3-cp314-cp314t-musllinux_1_2_ppc64le.whl", hash = "sha256:e99f6fa6509c037794da57f906ade271f52276c956d00f748e5b118462021d48", size = 62651, upload-time = "2025-12-06T13:25:19.191Z" },
    { url = "https://files.pythonhosted.org/packages/bd/b8/f544a2e37c778d59208966d4ef19742a0be37c12fc8149ff34483c176616/pybase64-1.4.3-cp314-cp314t-musllinux_1_2_riscv64.whl", hash = "sha256:d94020ef09f624d841aa9a3a6029df8cf65d60d7a6d5c8687579fa68bd679b65", size = 58295, upload-time = "2025-12-06T13:25:20.822Z" },
    { url = "https://files.pythonhosted.org/packages/03/99/1fae8a3b7ac181e36f6e7864a62d42d5b1f4fa7edf408c6711e28fba6b4d/pybase64-1.4.3-cp314-cp314t-musllinux_1_2_s390x.whl", hash = "sha256:f64ce70d89942a23602dee910dec9b48e5edf94351e1b378186b74fcc00d7f66", size = 60960, upload-time = "2025-12-06T13:25:22.099Z" },
    { url = "https://files.pythonhosted.org/packages/9d/9e/cd4c727742345ad8384569a4466f1a1428f4e5cc94d9c2ab2f53d30be3fe/pybase64-1.4.3-cp314-cp314t-musllinux_1_2_x86_64.whl", hash = "sha256:8ea99f56e45c469818b9781903be86ba4153769f007ba0655fa3b46dc332803d", size = 74863, upload-time = "2025-12-06T13:25:23.442Z" },
    { url = "https://files.pythonhosted.org/packages/28/86/a236ecfc5b494e1e922da149689f690abc84248c7c1358f5605b8c9fdd60/pybase64-1.4.3-cp314-cp314t-win32.whl", hash = "sha256:343b1901103cc72362fd1f842524e3bb24978e31aea7ff11e033af7f373f66ab", size = 34513, upload-time = "2025-12-06T13:25:24.592Z" },
    { url = "https://files.pythonhosted.org/packages/56/ce/ca8675f8d1352e245eb012bfc75429ee9cf1f21c3256b98d9a329d44bf0f/pybase64-1.4.3-cp314-cp314t-win_amd64.whl", hash = "sha256:57aff6f7f9dea6705afac9d706432049642de5b01080d3718acc23af87c5af76", size = 36702, upload-time = "2025-12-06T13:25:25.72Z" },
    { url = "https://files.pythonhosted.org/packages/3b/30/4a675864877397179b09b720ee5fcb1cf772cf7bebc831989aff0a5f79c1/pybase64-1.4.3-cp314-cp314t-win_arm64.whl", hash = "sha256:e906aa08d4331e799400829e0f5e4177e76a3281e8a4bc82ba114c6b30e405c9", size = 31904, upload-time = "2025-12-06T13:25:26.826Z" },
    { url = "https://files.pythonhosted.org/packages/b2/7c/545fd4935a0e1ddd7147f557bf8157c73eecec9cffd523382fa7af2557de/pybase64-1.4.3-graalpy311-graalpy242_311_native-macosx_10_9_x86_64.whl", hash = "sha256:d27c1dfdb0c59a5e758e7a98bd78eaca5983c22f4a811a36f4f980d245df4611", size = 38393, upload-time = "2025-12-06T13:26:19.535Z" },
    { url = "https://files.pythonhosted.org/packages/c3/ca/ae7a96be9ddc96030d4e9dffc43635d4e136b12058b387fd47eb8301b60f/pybase64-1.4.3-graalpy311-graalpy242_311_native-macosx_11_0_arm64.whl", hash = "sha256:0f1a0c51d6f159511e3431b73c25db31095ee36c394e26a4349e067c62f434e5", size = 32109, upload-time = "2025-12-06T13:26:20.72Z" },
    { url = "https://files.pythonhosted.org/packages/bf/44/d4b7adc7bf4fd5b52d8d099121760c450a52c390223806b873f0b6a2d551/pybase64-1.4.3-graalpy311-graalpy242_311_native-manylinux1_x86_64.manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:a492518f3078a4e3faaef310697d21df9c6bc71908cebc8c2f6fbfa16d7d6b1f", size = 43227, upload-time = "2025-12-06T13:26:21.845Z" },
    { url = "https://files.pythonhosted.org/packages/08/86/2ba2d8734ef7939debeb52cf9952e457ba7aa226cae5c0e6dd631f9b851f/pybase64-1.4.3-graalpy311-graalpy242_311_native-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:cae1a0f47784fd16df90d8acc32011c8d5fcdd9ab392c9ec49543e5f6a9c43a4", size = 35804, upload-time = "2025-12-06T13:26:23.149Z" },
    { url = "https://files.pythonhosted.org/packages/4f/5b/19c725dc3aaa6281f2ce3ea4c1628d154a40dd99657d1381995f8096768b/pybase64-1.4.3-graalpy311-graalpy242_311_native-win_amd64.whl", hash = "sha256:03cea70676ffbd39a1ab7930a2d24c625b416cacc9d401599b1d29415a43ab6a", size = 35880, upload-time = "2025-12-06T13:26:24.663Z" },
    { url = "https://files.pythonhosted.org/packages/17/45/92322aec1b6979e789b5710f73c59f2172bc37c8ce835305434796824b7b/pybase64-1.4.3-graalpy312-graalpy250_312_native-macosx_10_13_x86_64.whl", hash = "sha256:2baaa092f3475f3a9c87ac5198023918ea8b6c125f4c930752ab2cbe3cd1d520", size = 38746, upload-time = "2025-12-06T13:26:25.869Z" },
    { url = "https://files.pythonhosted.org/packages/11/94/f1a07402870388fdfc2ecec0c718111189732f7d0f2d7fe1386e19e8fad0/pybase64-1.4.3-graalpy312-graalpy250_312_native-macosx_11_0_arm64.whl", hash = "sha256:cde13c0764b1af07a631729f26df019070dad759981d6975527b7e8ecb465b6c", size = 32573, upload-time = "2025-12-06T13:26:27.792Z" },
    { url = "https://files.pythonhosted.org/packages/fa/8f/43c3bb11ca9bacf81cb0b7a71500bb65b2eda6d5fe07433c09b543de97f3/pybase64-1.4.3-graalpy312-graalpy250_312_native-manylinux1_x86_64.manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:5c29a582b0ea3936d02bd6fe9bf674ab6059e6e45ab71c78404ab2c913224414", size = 43461, upload-time = "2025-12-06T13:26:28.906Z" },
    { url = "https://files.pythonhosted.org/packages/2d/4c/2a5258329200be57497d3972b5308558c6de42e3749c6cc2aa1cbe34b25a/pybase64-1.4.3-graalpy312-graalpy250_312_native-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:b6b664758c804fa919b4f1257aa8cf68e95db76fc331de5f70bfc3a34655afe1", size = 36058, upload-time = "2025-12-06T13:26:30.092Z" },
    { url = "https://files.pythonhosted.org/packages/ea/6d/41faa414cde66ec023b0ca8402a8f11cb61731c3dc27c082909cbbd1f929/pybase64-1.4.3-graalpy312-graalpy250_312_native-win_amd64.whl", hash = "sha256:f7537fa22ae56a0bf51e4b0ffc075926ad91c618e1416330939f7ef366b58e3b", size = 36231, upload-time = "2025-12-06T13:26:31.656Z" },
    { url = "https://files.pythonhosted.org/packages/b2/76/160dded493c00d3376d4ad0f38a2119c5345de4a6693419ad39c3565959b/pybase64-1.4.3-pp311-pypy311_pp73-macosx_10_15_x86_64.whl", hash = "sha256:277de6e03cc9090fb359365c686a2a3036d23aee6cd20d45d22b8c89d1247f17", size = 37939, upload-time = "2025-12-06T13:26:41.014Z" },
    { url = "https://files.pythonhosted.org/packages/b7/b8/a0f10be8d648d6f8f26e560d6e6955efa7df0ff1e009155717454d76f601/pybase64-1.4.3-pp311-pypy311_pp73-macosx_11_0_arm64.whl", hash = "sha256:ab1dd8b1ed2d1d750260ed58ab40defaa5ba83f76a30e18b9ebd5646f6247ae5", size = 31466, upload-time = "2025-12-06T13:26:42.539Z" },
    { url = "https://files.pythonhosted.org/packages/d3/22/832a2f9e76cdf39b52e01e40d8feeb6a04cf105494f2c3e3126d0149717f/pybase64-1.4.3-pp311-pypy311_pp73-manylinux1_i686.manylinux2014_i686.manylinux_2_17_i686.manylinux_2_5_i686.whl", hash = "sha256:bd4d2293de9fd212e294c136cec85892460b17d24e8c18a6ba18750928037750", size = 40681, upload-time = "2025-12-06T13:26:43.782Z" },
    { url = "https://files.pythonhosted.org/packages/12/d7/6610f34a8972415fab3bb4704c174a1cc477bffbc3c36e526428d0f3957d/pybase64-1.4.3-pp311-pypy311_pp73-manylinux1_x86_64.manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:2af6d0d3a691911cc4c9a625f3ddcd3af720738c21be3d5c72de05629139d393", size = 41294, upload-time = "2025-12-06T13:26:44.936Z" },
    { url = "https://files.pythonhosted.org/packages/64/25/ed24400948a6c974ab1374a233cb7e8af0a5373cea0dd8a944627d17c34a/pybase64-1.4.3-pp311-pypy311_pp73-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:5cfc8c49a28322d82242088378f8542ce97459866ba73150b062a7073e82629d", size = 35447, upload-time = "2025-12-06T13:26:46.098Z" },
    { url = "https://files.pythonhosted.org/packages/ee/2b/e18ee7c5ee508a82897f021c1981533eca2940b5f072fc6ed0906c03a7a7/pybase64-1.4.3-pp311-pypy311_pp73-win_amd64.whl", hash = "sha256:debf737e09b8bf832ba86f5ecc3d3dbd0e3021d6cd86ba4abe962d6a5a77adb3", size = 36134, upload-time = "2025-12-06T13:26:47.35Z" },
]

[[package]]
name = "pycparser"
version = "3.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/1b/7d/92392ff7815c21062bea51aa7b87d45576f649f16458d78b7cf94b9ab2e6/pycparser-3.0.tar.gz", hash = "sha256:600f49d217304a5902ac3c37e1281c9fe94e4d0489de643a9504c5cdfdfc6b29", size = 103492, upload-time = "2026-01-21T14:26:51.89Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/0c/c3/44f3fbbfa403ea2a7c779186dc20772604442dde72947e7d01069cbe98e3/pycparser-3.0-py3-none-any.whl", hash = "sha256:b727414169a36b7d524c1c3e31839a521725078d7b2ff038656844266160a992", size = 48172, upload-time = "2026-01-21T14:26:50.693Z" },
]

[[package]]
name = "pycryptodome"
version = "3.23.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/8e/a6/8452177684d5e906854776276ddd34eca30d1b1e15aa1ee9cefc289a33f5/pycryptodome-3.23.0.tar.gz", hash = "sha256:447700a657182d60338bab09fdb27518f8856aecd80ae4c6bdddb67ff5da44ef", size = 4921276, upload-time = "2025-05-17T17:21:45.242Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/04/5d/bdb09489b63cd34a976cc9e2a8d938114f7a53a74d3dd4f125ffa49dce82/pycryptodome-3.23.0-cp313-cp313t-macosx_10_13_universal2.whl", hash = "sha256:0011f7f00cdb74879142011f95133274741778abba114ceca229adbf8e62c3e4", size = 2495152, upload-time = "2025-05-17T17:20:20.833Z" },
    { url = "https://files.pythonhosted.org/packages/a7/ce/7840250ed4cc0039c433cd41715536f926d6e86ce84e904068eb3244b6a6/pycryptodome-3.23.0-cp313-cp313t-macosx_10_13_x86_64.whl", hash = "sha256:90460fc9e088ce095f9ee8356722d4f10f86e5be06e2354230a9880b9c549aae", size = 1639348, upload-time = "2025-05-17T17:20:23.171Z" },
    { url = "https://files.pythonhosted.org/packages/ee/f0/991da24c55c1f688d6a3b5a11940567353f74590734ee4a64294834ae472/pycryptodome-3.23.0-cp313-cp313t-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:4764e64b269fc83b00f682c47443c2e6e85b18273712b98aa43bcb77f8570477", size = 2184033, upload-time = "2025-05-17T17:20:25.424Z" },
    { url = "https://files.pythonhosted.org/packages/54/16/0e11882deddf00f68b68dd4e8e442ddc30641f31afeb2bc25588124ac8de/pycryptodome-3.23.0-cp313-cp313t-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:eb8f24adb74984aa0e5d07a2368ad95276cf38051fe2dc6605cbcf482e04f2a7", size = 2270142, upload-time = "2025-05-17T17:20:27.808Z" },
    { url = "https://files.pythonhosted.org/packages/d5/fc/4347fea23a3f95ffb931f383ff28b3f7b1fe868739182cb76718c0da86a1/pycryptodome-3.23.0-cp313-cp313t-manylinux_2_5_i686.manylinux1_i686.manylinux_2_17_i686.manylinux2014_i686.whl", hash = "sha256:d97618c9c6684a97ef7637ba43bdf6663a2e2e77efe0f863cce97a76af396446", size = 2309384, upload-time = "2025-05-17T17:20:30.765Z" },
    { url = "https://files.pythonhosted.org/packages/6e/d9/c5261780b69ce66d8cfab25d2797bd6e82ba0241804694cd48be41add5eb/pycryptodome-3.23.0-cp313-cp313t-musllinux_1_2_aarch64.whl", hash = "sha256:9a53a4fe5cb075075d515797d6ce2f56772ea7e6a1e5e4b96cf78a14bac3d265", size = 2183237, upload-time = "2025-05-17T17:20:33.736Z" },
    { url = "https://files.pythonhosted.org/packages/5a/6f/3af2ffedd5cfa08c631f89452c6648c4d779e7772dfc388c77c920ca6bbf/pycryptodome-3.23.0-cp313-cp313t-musllinux_1_2_i686.whl", hash = "sha256:763d1d74f56f031788e5d307029caef067febf890cd1f8bf61183ae142f1a77b", size = 2343898, upload-time = "2025-05-17T17:20:36.086Z" },
    { url = "https://files.pythonhosted.org/packages/9a/dc/9060d807039ee5de6e2f260f72f3d70ac213993a804f5e67e0a73a56dd2f/pycryptodome-3.23.0-cp313-cp313t-musllinux_1_2_x86_64.whl", hash = "sha256:954af0e2bd7cea83ce72243b14e4fb518b18f0c1649b576d114973e2073b273d", size = 2269197, upload-time = "2025-05-17T17:20:38.414Z" },
    { url = "https://files.pythonhosted.org/packages/f9/34/e6c8ca177cb29dcc4967fef73f5de445912f93bd0343c9c33c8e5bf8cde8/pycryptodome-3.23.0-cp313-cp313t-win32.whl", hash = "sha256:257bb3572c63ad8ba40b89f6fc9d63a2a628e9f9708d31ee26560925ebe0210a", size = 1768600, upload-time = "2025-05-17T17:20:40.688Z" },
    { url = "https://files.pythonhosted.org/packages/e4/1d/89756b8d7ff623ad0160f4539da571d1f594d21ee6d68be130a6eccb39a4/pycryptodome-3.23.0-cp313-cp313t-win_amd64.whl", hash = "sha256:6501790c5b62a29fcb227bd6b62012181d886a767ce9ed03b303d1f22eb5c625", size = 1799740, upload-time = "2025-05-17T17:20:42.413Z" },
    { url = "https://files.pythonhosted.org/packages/5d/61/35a64f0feaea9fd07f0d91209e7be91726eb48c0f1bfc6720647194071e4/pycryptodome-3.23.0-cp313-cp313t-win_arm64.whl", hash = "sha256:9a77627a330ab23ca43b48b130e202582e91cc69619947840ea4d2d1be21eb39", size = 1703685, upload-time = "2025-05-17T17:20:44.388Z" },
    { url = "https://files.pythonhosted.org/packages/db/6c/a1f71542c969912bb0e106f64f60a56cc1f0fabecf9396f45accbe63fa68/pycryptodome-3.23.0-cp37-abi3-macosx_10_9_universal2.whl", hash = "sha256:187058ab80b3281b1de11c2e6842a357a1f71b42cb1e15bce373f3d238135c27", size = 2495627, upload-time = "2025-05-17T17:20:47.139Z" },
    { url = "https://files.pythonhosted.org/packages/6e/4e/a066527e079fc5002390c8acdd3aca431e6ea0a50ffd7201551175b47323/pycryptodome-3.23.0-cp37-abi3-macosx_10_9_x86_64.whl", hash = "sha256:cfb5cd445280c5b0a4e6187a7ce8de5a07b5f3f897f235caa11f1f435f182843", size = 1640362, upload-time = "2025-05-17T17:20:50.392Z" },
    { url = "https://files.pythonhosted.org/packages/50/52/adaf4c8c100a8c49d2bd058e5b551f73dfd8cb89eb4911e25a0c469b6b4e/pycryptodome-3.23.0-cp37-abi3-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:67bd81fcbe34f43ad9422ee8fd4843c8e7198dd88dd3d40e6de42ee65fbe1490", size = 2182625, upload-time = "2025-05-17T17:20:52.866Z" },
    { url = "https://files.pythonhosted.org/packages/5f/e9/a09476d436d0ff1402ac3867d933c61805ec2326c6ea557aeeac3825604e/pycryptodome-3.23.0-cp37-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:c8987bd3307a39bc03df5c8e0e3d8be0c4c3518b7f044b0f4c15d1aa78f52575", size = 2268954, upload-time = "2025-05-17T17:20:55.027Z" },
    { url = "https://files.pythonhosted.org/packages/f9/c5/ffe6474e0c551d54cab931918127c46d70cab8f114e0c2b5a3c071c2f484/pycryptodome-3.23.0-cp37-abi3-manylinux_2_5_i686.manylinux1_i686.manylinux_2_17_i686.manylinux2014_i686.whl", hash = "sha256:aa0698f65e5b570426fc31b8162ed4603b0c2841cbb9088e2b01641e3065915b", size = 2308534, upload-time = "2025-05-17T17:20:57.279Z" },
    { url = "https://files.pythonhosted.org/packages/18/28/e199677fc15ecf43010f2463fde4c1a53015d1fe95fb03bca2890836603a/pycryptodome-3.23.0-cp37-abi3-musllinux_1_2_aarch64.whl", hash = "sha256:53ecbafc2b55353edcebd64bf5da94a2a2cdf5090a6915bcca6eca6cc452585a", size = 2181853, upload-time = "2025-05-17T17:20:59.322Z" },
    { url = "https://files.pythonhosted.org/packages/ce/ea/4fdb09f2165ce1365c9eaefef36625583371ee514db58dc9b65d3a255c4c/pycryptodome-3.23.0-cp37-abi3-musllinux_1_2_i686.whl", hash = "sha256:156df9667ad9f2ad26255926524e1c136d6664b741547deb0a86a9acf5ea631f", size = 2342465, upload-time = "2025-05-17T17:21:03.83Z" },
    { url = "https://files.pythonhosted.org/packages/22/82/6edc3fc42fe9284aead511394bac167693fb2b0e0395b28b8bedaa07ef04/pycryptodome-3.23.0-cp37-abi3-musllinux_1_2_x86_64.whl", hash = "sha256:dea827b4d55ee390dc89b2afe5927d4308a8b538ae91d9c6f7a5090f397af1aa", size = 2267414, upload-time = "2025-05-17T17:21:06.72Z" },
    { url = "https://files.pythonhosted.org/packages/59/fe/aae679b64363eb78326c7fdc9d06ec3de18bac68be4b612fc1fe8902693c/pycryptodome-3.23.0-cp37-abi3-win32.whl", hash = "sha256:507dbead45474b62b2bbe318eb1c4c8ee641077532067fec9c1aa82c31f84886", size = 1768484, upload-time = "2025-05-17T17:21:08.535Z" },
    { url = "https://files.pythonhosted.org/packages/54/2f/e97a1b8294db0daaa87012c24a7bb714147c7ade7656973fd6c736b484ff/pycryptodome-3.23.0-cp37-abi3-win_amd64.whl", hash = "sha256:c75b52aacc6c0c260f204cbdd834f76edc9fb0d8e0da9fbf8352ef58202564e2", size = 1799636, upload-time = "2025-05-17T17:21:10.393Z" },
    { url = "https://files.pythonhosted.org/packages/18/3d/f9441a0d798bf2b1e645adc3265e55706aead1255ccdad3856dbdcffec14/pycryptodome-3.23.0-cp37-abi3-win_arm64.whl", hash = "sha256:11eeeb6917903876f134b56ba11abe95c0b0fd5e3330def218083c7d98bbcb3c", size = 1703675, upload-time = "2025-05-17T17:21:13.146Z" },
]

[[package]]
name = "pydantic"
version = "2.12.5"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "annotated-types" },
    { name = "pydantic-core" },
    { name = "typing-extensions" },
    { name = "typing-inspection" },
]
sdist = { url = "https://files.pythonhosted.org/packages/69/44/36f1a6e523abc58ae5f928898e4aca2e0ea509b5aa6f6f392a5d882be928/pydantic-2.12.5.tar.gz", hash = "sha256:4d351024c75c0f085a9febbb665ce8c0c6ec5d30e903bdb6394b7ede26aebb49", size = 821591, upload-time = "2025-11-26T15:11:46.471Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/5a/87/b70ad306ebb6f9b585f114d0ac2137d792b48be34d732d60e597c2f8465a/pydantic-2.12.5-py3-none-any.whl", hash = "sha256:e561593fccf61e8a20fc46dfc2dfe075b8be7d0188df33f221ad1f0139180f9d", size = 463580, upload-time = "2025-11-26T15:11:44.605Z" },
]

[[package]]
name = "pydantic-core"
version = "2.41.5"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "typing-extensions" },
]
sdist = { url = "https://files.pythonhosted.org/packages/71/70/23b021c950c2addd24ec408e9ab05d59b035b39d97cdc1130e1bce647bb6/pydantic_core-2.41.5.tar.gz", hash = "sha256:08daa51ea16ad373ffd5e7606252cc32f07bc72b28284b6bc9c6df804816476e", size = 460952, upload-time = "2025-11-04T13:43:49.098Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/e8/72/74a989dd9f2084b3d9530b0915fdda64ac48831c30dbf7c72a41a5232db8/pydantic_core-2.41.5-cp311-cp311-macosx_10_12_x86_64.whl", hash = "sha256:a3a52f6156e73e7ccb0f8cced536adccb7042be67cb45f9562e12b319c119da6", size = 2105873, upload-time = "2025-11-04T13:39:31.373Z" },
    { url = "https://files.pythonhosted.org/packages/12/44/37e403fd9455708b3b942949e1d7febc02167662bf1a7da5b78ee1ea2842/pydantic_core-2.41.5-cp311-cp311-macosx_11_0_arm64.whl", hash = "sha256:7f3bf998340c6d4b0c9a2f02d6a400e51f123b59565d74dc60d252ce888c260b", size = 1899826, upload-time = "2025-11-04T13:39:32.897Z" },
    { url = "https://files.pythonhosted.org/packages/33/7f/1d5cab3ccf44c1935a359d51a8a2a9e1a654b744b5e7f80d41b88d501eec/pydantic_core-2.41.5-cp311-cp311-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:378bec5c66998815d224c9ca994f1e14c0c21cb95d2f52b6021cc0b2a58f2a5a", size = 1917869, upload-time = "2025-11-04T13:39:34.469Z" },
    { url = "https://files.pythonhosted.org/packages/6e/6a/30d94a9674a7fe4f4744052ed6c5e083424510be1e93da5bc47569d11810/pydantic_core-2.41.5-cp311-cp311-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:e7b576130c69225432866fe2f4a469a85a54ade141d96fd396dffcf607b558f8", size = 2063890, upload-time = "2025-11-04T13:39:36.053Z" },
    { url = "https://files.pythonhosted.org/packages/50/be/76e5d46203fcb2750e542f32e6c371ffa9b8ad17364cf94bb0818dbfb50c/pydantic_core-2.41.5-cp311-cp311-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:6cb58b9c66f7e4179a2d5e0f849c48eff5c1fca560994d6eb6543abf955a149e", size = 2229740, upload-time = "2025-11-04T13:39:37.753Z" },
    { url = "https://files.pythonhosted.org/packages/d3/ee/fed784df0144793489f87db310a6bbf8118d7b630ed07aa180d6067e653a/pydantic_core-2.41.5-cp311-cp311-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:88942d3a3dff3afc8288c21e565e476fc278902ae4d6d134f1eeda118cc830b1", size = 2350021, upload-time = "2025-11-04T13:39:40.94Z" },
    { url = "https://files.pythonhosted.org/packages/c8/be/8fed28dd0a180dca19e72c233cbf58efa36df055e5b9d90d64fd1740b828/pydantic_core-2.41.5-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:f31d95a179f8d64d90f6831d71fa93290893a33148d890ba15de25642c5d075b", size = 2066378, upload-time = "2025-11-04T13:39:42.523Z" },
    { url = "https://files.pythonhosted.org/packages/b0/3b/698cf8ae1d536a010e05121b4958b1257f0b5522085e335360e53a6b1c8b/pydantic_core-2.41.5-cp311-cp311-manylinux_2_5_i686.manylinux1_i686.whl", hash = "sha256:c1df3d34aced70add6f867a8cf413e299177e0c22660cc767218373d0779487b", size = 2175761, upload-time = "2025-11-04T13:39:44.553Z" },
    { url = "https://files.pythonhosted.org/packages/b8/ba/15d537423939553116dea94ce02f9c31be0fa9d0b806d427e0308ec17145/pydantic_core-2.41.5-cp311-cp311-musllinux_1_1_aarch64.whl", hash = "sha256:4009935984bd36bd2c774e13f9a09563ce8de4abaa7226f5108262fa3e637284", size = 2146303, upload-time = "2025-11-04T13:39:46.238Z" },
    { url = "https://files.pythonhosted.org/packages/58/7f/0de669bf37d206723795f9c90c82966726a2ab06c336deba4735b55af431/pydantic_core-2.41.5-cp311-cp311-musllinux_1_1_armv7l.whl", hash = "sha256:34a64bc3441dc1213096a20fe27e8e128bd3ff89921706e83c0b1ac971276594", size = 2340355, upload-time = "2025-11-04T13:39:48.002Z" },
    { url = "https://files.pythonhosted.org/packages/e5/de/e7482c435b83d7e3c3ee5ee4451f6e8973cff0eb6007d2872ce6383f6398/pydantic_core-2.41.5-cp311-cp311-musllinux_1_1_x86_64.whl", hash = "sha256:c9e19dd6e28fdcaa5a1de679aec4141f691023916427ef9bae8584f9c2fb3b0e", size = 2319875, upload-time = "2025-11-04T13:39:49.705Z" },
    { url = "https://files.pythonhosted.org/packages/fe/e6/8c9e81bb6dd7560e33b9053351c29f30c8194b72f2d6932888581f503482/pydantic_core-2.41.5-cp311-cp311-win32.whl", hash = "sha256:2c010c6ded393148374c0f6f0bf89d206bf3217f201faa0635dcd56bd1520f6b", size = 1987549, upload-time = "2025-11-04T13:39:51.842Z" },
    { url = "https://files.pythonhosted.org/packages/11/66/f14d1d978ea94d1bc21fc98fcf570f9542fe55bfcc40269d4e1a21c19bf7/pydantic_core-2.41.5-cp311-cp311-win_amd64.whl", hash = "sha256:76ee27c6e9c7f16f47db7a94157112a2f3a00e958bc626e2f4ee8bec5c328fbe", size = 2011305, upload-time = "2025-11-04T13:39:53.485Z" },
    { url = "https://files.pythonhosted.org/packages/56/d8/0e271434e8efd03186c5386671328154ee349ff0354d83c74f5caaf096ed/pydantic_core-2.41.5-cp311-cp311-win_arm64.whl", hash = "sha256:4bc36bbc0b7584de96561184ad7f012478987882ebf9f9c389b23f432ea3d90f", size = 1972902, upload-time = "2025-11-04T13:39:56.488Z" },
    { url = "https://files.pythonhosted.org/packages/5f/5d/5f6c63eebb5afee93bcaae4ce9a898f3373ca23df3ccaef086d0233a35a7/pydantic_core-2.41.5-cp312-cp312-macosx_10_12_x86_64.whl", hash = "sha256:f41a7489d32336dbf2199c8c0a215390a751c5b014c2c1c5366e817202e9cdf7", size = 2110990, upload-time = "2025-11-04T13:39:58.079Z" },
    { url = "https://files.pythonhosted.org/packages/aa/32/9c2e8ccb57c01111e0fd091f236c7b371c1bccea0fa85247ac55b1e2b6b6/pydantic_core-2.41.5-cp312-cp312-macosx_11_0_arm64.whl", hash = "sha256:070259a8818988b9a84a449a2a7337c7f430a22acc0859c6b110aa7212a6d9c0", size = 1896003, upload-time = "2025-11-04T13:39:59.956Z" },
    { url = "https://files.pythonhosted.org/packages/68/b8/a01b53cb0e59139fbc9e4fda3e9724ede8de279097179be4ff31f1abb65a/pydantic_core-2.41.5-cp312-cp312-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:e96cea19e34778f8d59fe40775a7a574d95816eb150850a85a7a4c8f4b94ac69", size = 1919200, upload-time = "2025-11-04T13:40:02.241Z" },
    { url = "https://files.pythonhosted.org/packages/38/de/8c36b5198a29bdaade07b5985e80a233a5ac27137846f3bc2d3b40a47360/pydantic_core-2.41.5-cp312-cp312-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:ed2e99c456e3fadd05c991f8f437ef902e00eedf34320ba2b0842bd1c3ca3a75", size = 2052578, upload-time = "2025-11-04T13:40:04.401Z" },
    { url = "https://files.pythonhosted.org/packages/00/b5/0e8e4b5b081eac6cb3dbb7e60a65907549a1ce035a724368c330112adfdd/pydantic_core-2.41.5-cp312-cp312-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:65840751b72fbfd82c3c640cff9284545342a4f1eb1586ad0636955b261b0b05", size = 2208504, upload-time = "2025-11-04T13:40:06.072Z" },
    { url = "https://files.pythonhosted.org/packages/77/56/87a61aad59c7c5b9dc8caad5a41a5545cba3810c3e828708b3d7404f6cef/pydantic_core-2.41.5-cp312-cp312-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:e536c98a7626a98feb2d3eaf75944ef6f3dbee447e1f841eae16f2f0a72d8ddc", size = 2335816, upload-time = "2025-11-04T13:40:07.835Z" },
    { url = "https://files.pythonhosted.org/packages/0d/76/941cc9f73529988688a665a5c0ecff1112b3d95ab48f81db5f7606f522d3/pydantic_core-2.41.5-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:eceb81a8d74f9267ef4081e246ffd6d129da5d87e37a77c9bde550cb04870c1c", size = 2075366, upload-time = "2025-11-04T13:40:09.804Z" },
    { url = "https://files.pythonhosted.org/packages/d3/43/ebef01f69baa07a482844faaa0a591bad1ef129253ffd0cdaa9d8a7f72d3/pydantic_core-2.41.5-cp312-cp312-manylinux_2_5_i686.manylinux1_i686.whl", hash = "sha256:d38548150c39b74aeeb0ce8ee1d8e82696f4a4e16ddc6de7b1d8823f7de4b9b5", size = 2171698, upload-time = "2025-11-04T13:40:12.004Z" },
    { url = "https://files.pythonhosted.org/packages/b1/87/41f3202e4193e3bacfc2c065fab7706ebe81af46a83d3e27605029c1f5a6/pydantic_core-2.41.5-cp312-cp312-musllinux_1_1_aarch64.whl", hash = "sha256:c23e27686783f60290e36827f9c626e63154b82b116d7fe9adba1fda36da706c", size = 2132603, upload-time = "2025-11-04T13:40:13.868Z" },
    { url = "https://files.pythonhosted.org/packages/49/7d/4c00df99cb12070b6bccdef4a195255e6020a550d572768d92cc54dba91a/pydantic_core-2.41.5-cp312-cp312-musllinux_1_1_armv7l.whl", hash = "sha256:482c982f814460eabe1d3bb0adfdc583387bd4691ef00b90575ca0d2b6fe2294", size = 2329591, upload-time = "2025-11-04T13:40:15.672Z" },
    { url = "https://files.pythonhosted.org/packages/cc/6a/ebf4b1d65d458f3cda6a7335d141305dfa19bdc61140a884d165a8a1bbc7/pydantic_core-2.41.5-cp312-cp312-musllinux_1_1_x86_64.whl", hash = "sha256:bfea2a5f0b4d8d43adf9d7b8bf019fb46fdd10a2e5cde477fbcb9d1fa08c68e1", size = 2319068, upload-time = "2025-11-04T13:40:17.532Z" },
    { url = "https://files.pythonhosted.org/packages/49/3b/774f2b5cd4192d5ab75870ce4381fd89cf218af999515baf07e7206753f0/pydantic_core-2.41.5-cp312-cp312-win32.whl", hash = "sha256:b74557b16e390ec12dca509bce9264c3bbd128f8a2c376eaa68003d7f327276d", size = 1985908, upload-time = "2025-11-04T13:40:19.309Z" },
    { url = "https://files.pythonhosted.org/packages/86/45/00173a033c801cacf67c190fef088789394feaf88a98a7035b0e40d53dc9/pydantic_core-2.41.5-cp312-cp312-win_amd64.whl", hash = "sha256:1962293292865bca8e54702b08a4f26da73adc83dd1fcf26fbc875b35d81c815", size = 2020145, upload-time = "2025-11-04T13:40:21.548Z" },
    { url = "https://files.pythonhosted.org/packages/f9/22/91fbc821fa6d261b376a3f73809f907cec5ca6025642c463d3488aad22fb/pydantic_core-2.41.5-cp312-cp312-win_arm64.whl", hash = "sha256:1746d4a3d9a794cacae06a5eaaccb4b8643a131d45fbc9af23e353dc0a5ba5c3", size = 1976179, upload-time = "2025-11-04T13:40:23.393Z" },
    { url = "https://files.pythonhosted.org/packages/87/06/8806241ff1f70d9939f9af039c6c35f2360cf16e93c2ca76f184e76b1564/pydantic_core-2.41.5-cp313-cp313-macosx_10_12_x86_64.whl", hash = "sha256:941103c9be18ac8daf7b7adca8228f8ed6bb7a1849020f643b3a14d15b1924d9", size = 2120403, upload-time = "2025-11-04T13:40:25.248Z" },
    { url = "https://files.pythonhosted.org/packages/94/02/abfa0e0bda67faa65fef1c84971c7e45928e108fe24333c81f3bfe35d5f5/pydantic_core-2.41.5-cp313-cp313-macosx_11_0_arm64.whl", hash = "sha256:112e305c3314f40c93998e567879e887a3160bb8689ef3d2c04b6cc62c33ac34", size = 1896206, upload-time = "2025-11-04T13:40:27.099Z" },
    { url = "https://files.pythonhosted.org/packages/15/df/a4c740c0943e93e6500f9eb23f4ca7ec9bf71b19e608ae5b579678c8d02f/pydantic_core-2.41.5-cp313-cp313-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:0cbaad15cb0c90aa221d43c00e77bb33c93e8d36e0bf74760cd00e732d10a6a0", size = 1919307, upload-time = "2025-11-04T13:40:29.806Z" },
    { url = "https://files.pythonhosted.org/packages/9a/e3/6324802931ae1d123528988e0e86587c2072ac2e5394b4bc2bc34b61ff6e/pydantic_core-2.41.5-cp313-cp313-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:03ca43e12fab6023fc79d28ca6b39b05f794ad08ec2feccc59a339b02f2b3d33", size = 2063258, upload-time = "2025-11-04T13:40:33.544Z" },
    { url = "https://files.pythonhosted.org/packages/c9/d4/2230d7151d4957dd79c3044ea26346c148c98fbf0ee6ebd41056f2d62ab5/pydantic_core-2.41.5-cp313-cp313-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:dc799088c08fa04e43144b164feb0c13f9a0bc40503f8df3e9fde58a3c0c101e", size = 2214917, upload-time = "2025-11-04T13:40:35.479Z" },
    { url = "https://files.pythonhosted.org/packages/e6/9f/eaac5df17a3672fef0081b6c1bb0b82b33ee89aa5cec0d7b05f52fd4a1fa/pydantic_core-2.41.5-cp313-cp313-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:97aeba56665b4c3235a0e52b2c2f5ae9cd071b8a8310ad27bddb3f7fb30e9aa2", size = 2332186, upload-time = "2025-11-04T13:40:37.436Z" },
    { url = "https://files.pythonhosted.org/packages/cf/4e/35a80cae583a37cf15604b44240e45c05e04e86f9cfd766623149297e971/pydantic_core-2.41.5-cp313-cp313-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:406bf18d345822d6c21366031003612b9c77b3e29ffdb0f612367352aab7d586", size = 2073164, upload-time = "2025-11-04T13:40:40.289Z" },
    { url = "https://files.pythonhosted.org/packages/bf/e3/f6e262673c6140dd3305d144d032f7bd5f7497d3871c1428521f19f9efa2/pydantic_core-2.41.5-cp313-cp313-manylinux_2_5_i686.manylinux1_i686.whl", hash = "sha256:b93590ae81f7010dbe380cdeab6f515902ebcbefe0b9327cc4804d74e93ae69d", size = 2179146, upload-time = "2025-11-04T13:40:42.809Z" },
    { url = "https://files.pythonhosted.org/packages/75/c7/20bd7fc05f0c6ea2056a4565c6f36f8968c0924f19b7d97bbfea55780e73/pydantic_core-2.41.5-cp313-cp313-musllinux_1_1_aarch64.whl", hash = "sha256:01a3d0ab748ee531f4ea6c3e48ad9dac84ddba4b0d82291f87248f2f9de8d740", size = 2137788, upload-time = "2025-11-04T13:40:44.752Z" },
    { url = "https://files.pythonhosted.org/packages/3a/8d/34318ef985c45196e004bc46c6eab2eda437e744c124ef0dbe1ff2c9d06b/pydantic_core-2.41.5-cp313-cp313-musllinux_1_1_armv7l.whl", hash = "sha256:6561e94ba9dacc9c61bce40e2d6bdc3bfaa0259d3ff36ace3b1e6901936d2e3e", size = 2340133, upload-time = "2025-11-04T13:40:46.66Z" },
    { url = "https://files.pythonhosted.org/packages/9c/59/013626bf8c78a5a5d9350d12e7697d3d4de951a75565496abd40ccd46bee/pydantic_core-2.41.5-cp313-cp313-musllinux_1_1_x86_64.whl", hash = "sha256:915c3d10f81bec3a74fbd4faebe8391013ba61e5a1a8d48c4455b923bdda7858", size = 2324852, upload-time = "2025-11-04T13:40:48.575Z" },
    { url = "https://files.pythonhosted.org/packages/1a/d9/c248c103856f807ef70c18a4f986693a46a8ffe1602e5d361485da502d20/pydantic_core-2.41.5-cp313-cp313-win32.whl", hash = "sha256:650ae77860b45cfa6e2cdafc42618ceafab3a2d9a3811fcfbd3bbf8ac3c40d36", size = 1994679, upload-time = "2025-11-04T13:40:50.619Z" },
    { url = "https://files.pythonhosted.org/packages/9e/8b/341991b158ddab181cff136acd2552c9f35bd30380422a639c0671e99a91/pydantic_core-2.41.5-cp313-cp313-win_amd64.whl", hash = "sha256:79ec52ec461e99e13791ec6508c722742ad745571f234ea6255bed38c6480f11", size = 2019766, upload-time = "2025-11-04T13:40:52.631Z" },
    { url = "https://files.pythonhosted.org/packages/73/7d/f2f9db34af103bea3e09735bb40b021788a5e834c81eedb541991badf8f5/pydantic_core-2.41.5-cp313-cp313-win_arm64.whl", hash = "sha256:3f84d5c1b4ab906093bdc1ff10484838aca54ef08de4afa9de0f5f14d69639cd", size = 1981005, upload-time = "2025-11-04T13:40:54.734Z" },
    { url = "https://files.pythonhosted.org/packages/ea/28/46b7c5c9635ae96ea0fbb779e271a38129df2550f763937659ee6c5dbc65/pydantic_core-2.41.5-cp314-cp314-macosx_10_12_x86_64.whl", hash = "sha256:3f37a19d7ebcdd20b96485056ba9e8b304e27d9904d233d7b1015db320e51f0a", size = 2119622, upload-time = "2025-11-04T13:40:56.68Z" },
    { url = "https://files.pythonhosted.org/packages/74/1a/145646e5687e8d9a1e8d09acb278c8535ebe9e972e1f162ed338a622f193/pydantic_core-2.41.5-cp314-cp314-macosx_11_0_arm64.whl", hash = "sha256:1d1d9764366c73f996edd17abb6d9d7649a7eb690006ab6adbda117717099b14", size = 1891725, upload-time = "2025-11-04T13:40:58.807Z" },
    { url = "https://files.pythonhosted.org/packages/23/04/e89c29e267b8060b40dca97bfc64a19b2a3cf99018167ea1677d96368273/pydantic_core-2.41.5-cp314-cp314-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:25e1c2af0fce638d5f1988b686f3b3ea8cd7de5f244ca147c777769e798a9cd1", size = 1915040, upload-time = "2025-11-04T13:41:00.853Z" },
    { url = "https://files.pythonhosted.org/packages/84/a3/15a82ac7bd97992a82257f777b3583d3e84bdb06ba6858f745daa2ec8a85/pydantic_core-2.41.5-cp314-cp314-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:506d766a8727beef16b7adaeb8ee6217c64fc813646b424d0804d67c16eddb66", size = 2063691, upload-time = "2025-11-04T13:41:03.504Z" },
    { url = "https://files.pythonhosted.org/packages/74/9b/0046701313c6ef08c0c1cf0e028c67c770a4e1275ca73131563c5f2a310a/pydantic_core-2.41.5-cp314-cp314-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:4819fa52133c9aa3c387b3328f25c1facc356491e6135b459f1de698ff64d869", size = 2213897, upload-time = "2025-11-04T13:41:05.804Z" },
    { url = "https://files.pythonhosted.org/packages/8a/cd/6bac76ecd1b27e75a95ca3a9a559c643b3afcd2dd62086d4b7a32a18b169/pydantic_core-2.41.5-cp314-cp314-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:2b761d210c9ea91feda40d25b4efe82a1707da2ef62901466a42492c028553a2", size = 2333302, upload-time = "2025-11-04T13:41:07.809Z" },
    { url = "https://files.pythonhosted.org/packages/4c/d2/ef2074dc020dd6e109611a8be4449b98cd25e1b9b8a303c2f0fca2f2bcf7/pydantic_core-2.41.5-cp314-cp314-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:22f0fb8c1c583a3b6f24df2470833b40207e907b90c928cc8d3594b76f874375", size = 2064877, upload-time = "2025-11-04T13:41:09.827Z" },
    { url = "https://files.pythonhosted.org/packages/18/66/e9db17a9a763d72f03de903883c057b2592c09509ccfe468187f2a2eef29/pydantic_core-2.41.5-cp314-cp314-manylinux_2_5_i686.manylinux1_i686.whl", hash = "sha256:2782c870e99878c634505236d81e5443092fba820f0373997ff75f90f68cd553", size = 2180680, upload-time = "2025-11-04T13:41:12.379Z" },
    { url = "https://files.pythonhosted.org/packages/d3/9e/3ce66cebb929f3ced22be85d4c2399b8e85b622db77dad36b73c5387f8f8/pydantic_core-2.41.5-cp314-cp314-musllinux_1_1_aarch64.whl", hash = "sha256:0177272f88ab8312479336e1d777f6b124537d47f2123f89cb37e0accea97f90", size = 2138960, upload-time = "2025-11-04T13:41:14.627Z" },
    { url = "https://files.pythonhosted.org/packages/a6/62/205a998f4327d2079326b01abee48e502ea739d174f0a89295c481a2272e/pydantic_core-2.41.5-cp314-cp314-musllinux_1_1_armv7l.whl", hash = "sha256:63510af5e38f8955b8ee5687740d6ebf7c2a0886d15a6d65c32814613681bc07", size = 2339102, upload-time = "2025-11-04T13:41:16.868Z" },
    { url = "https://files.pythonhosted.org/packages/3c/0d/f05e79471e889d74d3d88f5bd20d0ed189ad94c2423d81ff8d0000aab4ff/pydantic_core-2.41.5-cp314-cp314-musllinux_1_1_x86_64.whl", hash = "sha256:e56ba91f47764cc14f1daacd723e3e82d1a89d783f0f5afe9c364b8bb491ccdb", size = 2326039, upload-time = "2025-11-04T13:41:18.934Z" },
    { url = "https://files.pythonhosted.org/packages/ec/e1/e08a6208bb100da7e0c4b288eed624a703f4d129bde2da475721a80cab32/pydantic_core-2.41.5-cp314-cp314-win32.whl", hash = "sha256:aec5cf2fd867b4ff45b9959f8b20ea3993fc93e63c7363fe6851424c8a7e7c23", size = 1995126, upload-time = "2025-11-04T13:41:21.418Z" },
    { url = "https://files.pythonhosted.org/packages/48/5d/56ba7b24e9557f99c9237e29f5c09913c81eeb2f3217e40e922353668092/pydantic_core-2.41.5-cp314-cp314-win_amd64.whl", hash = "sha256:8e7c86f27c585ef37c35e56a96363ab8de4e549a95512445b85c96d3e2f7c1bf", size = 2015489, upload-time = "2025-11-04T13:41:24.076Z" },
    { url = "https://files.pythonhosted.org/packages/4e/bb/f7a190991ec9e3e0ba22e4993d8755bbc4a32925c0b5b42775c03e8148f9/pydantic_core-2.41.5-cp314-cp314-win_arm64.whl", hash = "sha256:e672ba74fbc2dc8eea59fb6d4aed6845e6905fc2a8afe93175d94a83ba2a01a0", size = 1977288, upload-time = "2025-11-04T13:41:26.33Z" },
    { url = "https://files.pythonhosted.org/packages/92/ed/77542d0c51538e32e15afe7899d79efce4b81eee631d99850edc2f5e9349/pydantic_core-2.41.5-cp314-cp314t-macosx_10_12_x86_64.whl", hash = "sha256:8566def80554c3faa0e65ac30ab0932b9e3a5cd7f8323764303d468e5c37595a", size = 2120255, upload-time = "2025-11-04T13:41:28.569Z" },
    { url = "https://files.pythonhosted.org/packages/bb/3d/6913dde84d5be21e284439676168b28d8bbba5600d838b9dca99de0fad71/pydantic_core-2.41.5-cp314-cp314t-macosx_11_0_arm64.whl", hash = "sha256:b80aa5095cd3109962a298ce14110ae16b8c1aece8b72f9dafe81cf597ad80b3", size = 1863760, upload-time = "2025-11-04T13:41:31.055Z" },
    { url = "https://files.pythonhosted.org/packages/5a/f0/e5e6b99d4191da102f2b0eb9687aaa7f5bea5d9964071a84effc3e40f997/pydantic_core-2.41.5-cp314-cp314t-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:3006c3dd9ba34b0c094c544c6006cc79e87d8612999f1a5d43b769b89181f23c", size = 1878092, upload-time = "2025-11-04T13:41:33.21Z" },
    { url = "https://files.pythonhosted.org/packages/71/48/36fb760642d568925953bcc8116455513d6e34c4beaa37544118c36aba6d/pydantic_core-2.41.5-cp314-cp314t-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:72f6c8b11857a856bcfa48c86f5368439f74453563f951e473514579d44aa612", size = 2053385, upload-time = "2025-11-04T13:41:35.508Z" },
    { url = "https://files.pythonhosted.org/packages/20/25/92dc684dd8eb75a234bc1c764b4210cf2646479d54b47bf46061657292a8/pydantic_core-2.41.5-cp314-cp314t-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:5cb1b2f9742240e4bb26b652a5aeb840aa4b417c7748b6f8387927bc6e45e40d", size = 2218832, upload-time = "2025-11-04T13:41:37.732Z" },
    { url = "https://files.pythonhosted.org/packages/e2/09/f53e0b05023d3e30357d82eb35835d0f6340ca344720a4599cd663dca599/pydantic_core-2.41.5-cp314-cp314t-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:bd3d54f38609ff308209bd43acea66061494157703364ae40c951f83ba99a1a9", size = 2327585, upload-time = "2025-11-04T13:41:40Z" },
    { url = "https://files.pythonhosted.org/packages/aa/4e/2ae1aa85d6af35a39b236b1b1641de73f5a6ac4d5a7509f77b814885760c/pydantic_core-2.41.5-cp314-cp314t-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:2ff4321e56e879ee8d2a879501c8e469414d948f4aba74a2d4593184eb326660", size = 2041078, upload-time = "2025-11-04T13:41:42.323Z" },
    { url = "https://files.pythonhosted.org/packages/cd/13/2e215f17f0ef326fc72afe94776edb77525142c693767fc347ed6288728d/pydantic_core-2.41.5-cp314-cp314t-manylinux_2_5_i686.manylinux1_i686.whl", hash = "sha256:d0d2568a8c11bf8225044aa94409e21da0cb09dcdafe9ecd10250b2baad531a9", size = 2173914, upload-time = "2025-11-04T13:41:45.221Z" },
    { url = "https://files.pythonhosted.org/packages/02/7a/f999a6dcbcd0e5660bc348a3991c8915ce6599f4f2c6ac22f01d7a10816c/pydantic_core-2.41.5-cp314-cp314t-musllinux_1_1_aarch64.whl", hash = "sha256:a39455728aabd58ceabb03c90e12f71fd30fa69615760a075b9fec596456ccc3", size = 2129560, upload-time = "2025-11-04T13:41:47.474Z" },
    { url = "https://files.pythonhosted.org/packages/3a/b1/6c990ac65e3b4c079a4fb9f5b05f5b013afa0f4ed6780a3dd236d2cbdc64/pydantic_core-2.41.5-cp314-cp314t-musllinux_1_1_armv7l.whl", hash = "sha256:239edca560d05757817c13dc17c50766136d21f7cd0fac50295499ae24f90fdf", size = 2329244, upload-time = "2025-11-04T13:41:49.992Z" },
    { url = "https://files.pythonhosted.org/packages/d9/02/3c562f3a51afd4d88fff8dffb1771b30cfdfd79befd9883ee094f5b6c0d8/pydantic_core-2.41.5-cp314-cp314t-musllinux_1_1_x86_64.whl", hash = "sha256:2a5e06546e19f24c6a96a129142a75cee553cc018ffee48a460059b1185f4470", size = 2331955, upload-time = "2025-11-04T13:41:54.079Z" },
    { url = "https://files.pythonhosted.org/packages/5c/96/5fb7d8c3c17bc8c62fdb031c47d77a1af698f1d7a406b0f79aaa1338f9ad/pydantic_core-2.41.5-cp314-cp314t-win32.whl", hash = "sha256:b4ececa40ac28afa90871c2cc2b9ffd2ff0bf749380fbdf57d165fd23da353aa", size = 1988906, upload-time = "2025-11-04T13:41:56.606Z" },
    { url = "https://files.pythonhosted.org/packages/22/ed/182129d83032702912c2e2d8bbe33c036f342cc735737064668585dac28f/pydantic_core-2.41.5-cp314-cp314t-win_amd64.whl", hash = "sha256:80aa89cad80b32a912a65332f64a4450ed00966111b6615ca6816153d3585a8c", size = 1981607, upload-time = "2025-11-04T13:41:58.889Z" },
    { url = "https://files.pythonhosted.org/packages/9f/ed/068e41660b832bb0b1aa5b58011dea2a3fe0ba7861ff38c4d4904c1c1a99/pydantic_core-2.41.5-cp314-cp314t-win_arm64.whl", hash = "sha256:35b44f37a3199f771c3eaa53051bc8a70cd7b54f333531c59e29fd4db5d15008", size = 1974769, upload-time = "2025-11-04T13:42:01.186Z" },
    { url = "https://files.pythonhosted.org/packages/11/72/90fda5ee3b97e51c494938a4a44c3a35a9c96c19bba12372fb9c634d6f57/pydantic_core-2.41.5-graalpy311-graalpy242_311_native-macosx_10_12_x86_64.whl", hash = "sha256:b96d5f26b05d03cc60f11a7761a5ded1741da411e7fe0909e27a5e6a0cb7b034", size = 2115441, upload-time = "2025-11-04T13:42:39.557Z" },
    { url = "https://files.pythonhosted.org/packages/1f/53/8942f884fa33f50794f119012dc6a1a02ac43a56407adaac20463df8e98f/pydantic_core-2.41.5-graalpy311-graalpy242_311_native-macosx_11_0_arm64.whl", hash = "sha256:634e8609e89ceecea15e2d61bc9ac3718caaaa71963717bf3c8f38bfde64242c", size = 1930291, upload-time = "2025-11-04T13:42:42.169Z" },
    { url = "https://files.pythonhosted.org/packages/79/c8/ecb9ed9cd942bce09fc888ee960b52654fbdbede4ba6c2d6e0d3b1d8b49c/pydantic_core-2.41.5-graalpy311-graalpy242_311_native-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:93e8740d7503eb008aa2df04d3b9735f845d43ae845e6dcd2be0b55a2da43cd2", size = 1948632, upload-time = "2025-11-04T13:42:44.564Z" },
    { url = "https://files.pythonhosted.org/packages/2e/1b/687711069de7efa6af934e74f601e2a4307365e8fdc404703afc453eab26/pydantic_core-2.41.5-graalpy311-graalpy242_311_native-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:f15489ba13d61f670dcc96772e733aad1a6f9c429cc27574c6cdaed82d0146ad", size = 2138905, upload-time = "2025-11-04T13:42:47.156Z" },
    { url = "https://files.pythonhosted.org/packages/09/32/59b0c7e63e277fa7911c2fc70ccfb45ce4b98991e7ef37110663437005af/pydantic_core-2.41.5-graalpy312-graalpy250_312_native-macosx_10_12_x86_64.whl", hash = "sha256:7da7087d756b19037bc2c06edc6c170eeef3c3bafcb8f532ff17d64dc427adfd", size = 2110495, upload-time = "2025-11-04T13:42:49.689Z" },
    { url = "https://files.pythonhosted.org/packages/aa/81/05e400037eaf55ad400bcd318c05bb345b57e708887f07ddb2d20e3f0e98/pydantic_core-2.41.5-graalpy312-graalpy250_312_native-macosx_11_0_arm64.whl", hash = "sha256:aabf5777b5c8ca26f7824cb4a120a740c9588ed58df9b2d196ce92fba42ff8dc", size = 1915388, upload-time = "2025-11-04T13:42:52.215Z" },
    { url = "https://files.pythonhosted.org/packages/6e/0d/e3549b2399f71d56476b77dbf3cf8937cec5cd70536bdc0e374a421d0599/pydantic_core-2.41.5-graalpy312-graalpy250_312_native-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:c007fe8a43d43b3969e8469004e9845944f1a80e6acd47c150856bb87f230c56", size = 1942879, upload-time = "2025-11-04T13:42:56.483Z" },
    { url = "https://files.pythonhosted.org/packages/f7/07/34573da085946b6a313d7c42f82f16e8920bfd730665de2d11c0c37a74b5/pydantic_core-2.41.5-graalpy312-graalpy250_312_native-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:76d0819de158cd855d1cbb8fcafdf6f5cf1eb8e470abe056d5d161106e38062b", size = 2139017, upload-time = "2025-11-04T13:42:59.471Z" },
    { url = "https://files.pythonhosted.org/packages/5f/9b/1b3f0e9f9305839d7e84912f9e8bfbd191ed1b1ef48083609f0dabde978c/pydantic_core-2.41.5-pp311-pypy311_pp73-macosx_10_12_x86_64.whl", hash = "sha256:b2379fa7ed44ddecb5bfe4e48577d752db9fc10be00a6b7446e9663ba143de26", size = 2101980, upload-time = "2025-11-04T13:43:25.97Z" },
    { url = "https://files.pythonhosted.org/packages/a4/ed/d71fefcb4263df0da6a85b5d8a7508360f2f2e9b3bf5814be9c8bccdccc1/pydantic_core-2.41.5-pp311-pypy311_pp73-macosx_11_0_arm64.whl", hash = "sha256:266fb4cbf5e3cbd0b53669a6d1b039c45e3ce651fd5442eff4d07c2cc8d66808", size = 1923865, upload-time = "2025-11-04T13:43:28.763Z" },
    { url = "https://files.pythonhosted.org/packages/ce/3a/626b38db460d675f873e4444b4bb030453bbe7b4ba55df821d026a0493c4/pydantic_core-2.41.5-pp311-pypy311_pp73-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:58133647260ea01e4d0500089a8c4f07bd7aa6ce109682b1426394988d8aaacc", size = 2134256, upload-time = "2025-11-04T13:43:31.71Z" },
    { url = "https://files.pythonhosted.org/packages/83/d9/8412d7f06f616bbc053d30cb4e5f76786af3221462ad5eee1f202021eb4e/pydantic_core-2.41.5-pp311-pypy311_pp73-manylinux_2_5_i686.manylinux1_i686.whl", hash = "sha256:287dad91cfb551c363dc62899a80e9e14da1f0e2b6ebde82c806612ca2a13ef1", size = 2174762, upload-time = "2025-11-04T13:43:34.744Z" },
    { url = "https://files.pythonhosted.org/packages/55/4c/162d906b8e3ba3a99354e20faa1b49a85206c47de97a639510a0e673f5da/pydantic_core-2.41.5-pp311-pypy311_pp73-musllinux_1_1_aarch64.whl", hash = "sha256:03b77d184b9eb40240ae9fd676ca364ce1085f203e1b1256f8ab9984dca80a84", size = 2143141, upload-time = "2025-11-04T13:43:37.701Z" },
    { url = "https://files.pythonhosted.org/packages/1f/f2/f11dd73284122713f5f89fc940f370d035fa8e1e078d446b3313955157fe/pydantic_core-2.41.5-pp311-pypy311_pp73-musllinux_1_1_armv7l.whl", hash = "sha256:a668ce24de96165bb239160b3d854943128f4334822900534f2fe947930e5770", size = 2330317, upload-time = "2025-11-04T13:43:40.406Z" },
    { url = "https://files.pythonhosted.org/packages/88/9d/b06ca6acfe4abb296110fb1273a4d848a0bfb2ff65f3ee92127b3244e16b/pydantic_core-2.41.5-pp311-pypy311_pp73-musllinux_1_1_x86_64.whl", hash = "sha256:f14f8f046c14563f8eb3f45f499cc658ab8d10072961e07225e507adb700e93f", size = 2316992, upload-time = "2025-11-04T13:43:43.602Z" },
    { url = "https://files.pythonhosted.org/packages/36/c7/cfc8e811f061c841d7990b0201912c3556bfeb99cdcb7ed24adc8d6f8704/pydantic_core-2.41.5-pp311-pypy311_pp73-win_amd64.whl", hash = "sha256:56121965f7a4dc965bff783d70b907ddf3d57f6eba29b6d2e5dabfaf07799c51", size = 2145302, upload-time = "2025-11-04T13:43:46.64Z" },
]

[[package]]
name = "pydantic-settings"
version = "2.13.1"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "pydantic" },
    { name = "python-dotenv" },
    { name = "typing-inspection" },
]
sdist = { url = "https://files.pythonhosted.org/packages/52/6d/fffca34caecc4a3f97bda81b2098da5e8ab7efc9a66e819074a11955d87e/pydantic_settings-2.13.1.tar.gz", hash = "sha256:b4c11847b15237fb0171e1462bf540e294affb9b86db4d9aa5c01730bdbe4025", size = 223826, upload-time = "2026-02-19T13:45:08.055Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/00/4b/ccc026168948fec4f7555b9164c724cf4125eac006e176541483d2c959be/pydantic_settings-2.13.1-py3-none-any.whl", hash = "sha256:d56fd801823dbeae7f0975e1f8c8e25c258eb75d278ea7abb5d9cebb01b56237", size = 58929, upload-time = "2026-02-19T13:45:06.034Z" },
]

[[package]]
name = "pygments"
version = "2.19.2"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/b0/77/a5b8c569bf593b0140bde72ea885a803b82086995367bf2037de0159d924/pygments-2.19.2.tar.gz", hash = "sha256:636cb2477cec7f8952536970bc533bc43743542f70392ae026374600add5b887", size = 4968631, upload-time = "2025-06-21T13:39:12.283Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/c7/21/705964c7812476f378728bdf590ca4b771ec72385c533964653c68e86bdc/pygments-2.19.2-py3-none-any.whl", hash = "sha256:86540386c03d588bb81d44bc3928634ff26449851e99741617ecb9037ee5ec0b", size = 1225217, upload-time = "2025-06-21T13:39:07.939Z" },
]

[[package]]
name = "pypika"
version = "0.51.1"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/f8/78/cbaebba88e05e2dcda13ca203131b38d3640219f20ebb49676d26714861b/pypika-0.51.1.tar.gz", hash = "sha256:c30c7c1048fbf056fd3920c5a2b88b0c29dd190a9b2bee971fd17e4abe4d0ebe", size = 80919, upload-time = "2026-02-04T11:27:48.304Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/57/83/c77dfeed04022e8930b08eedca2b6e5efed256ab3321396fde90066efb65/pypika-0.51.1-py2.py3-none-any.whl", hash = "sha256:77985b4d7ce71b9905255bf12468cf598349e98837c037541cfc240e528aec46", size = 60585, upload-time = "2026-02-04T11:27:46.251Z" },
]

[[package]]
name = "pyproject-hooks"
version = "1.2.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/e7/82/28175b2414effca1cdac8dc99f76d660e7a4fb0ceefa4b4ab8f5f6742925/pyproject_hooks-1.2.0.tar.gz", hash = "sha256:1e859bd5c40fae9448642dd871adf459e5e2084186e8d2c2a79a824c970da1f8", size = 19228, upload-time = "2024-09-29T09:24:13.293Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/bd/24/12818598c362d7f300f18e74db45963dbcb85150324092410c8b49405e42/pyproject_hooks-1.2.0-py3-none-any.whl", hash = "sha256:9e5c6bfa8dcc30091c74b0cf803c81fdd29d94f01992a7707bc97babb1141913", size = 10216, upload-time = "2024-09-29T09:24:11.978Z" },
]

[[package]]
name = "pytest"
version = "9.0.2"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "colorama", marker = "sys_platform == 'win32'" },
    { name = "iniconfig" },
    { name = "packaging" },
    { name = "pluggy" },
    { name = "pygments" },
]
sdist = { url = "https://files.pythonhosted.org/packages/d1/db/7ef3487e0fb0049ddb5ce41d3a49c235bf9ad299b6a25d5780a89f19230f/pytest-9.0.2.tar.gz", hash = "sha256:75186651a92bd89611d1d9fc20f0b4345fd827c41ccd5c299a868a05d70edf11", size = 1568901, upload-time = "2025-12-06T21:30:51.014Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/3b/ab/b3226f0bd7cdcf710fbede2b3548584366da3b19b5021e74f5bde2a8fa3f/pytest-9.0.2-py3-none-any.whl", hash = "sha256:711ffd45bf766d5264d487b917733b453d917afd2b0ad65223959f59089f875b", size = 374801, upload-time = "2025-12-06T21:30:49.154Z" },
]

[[package]]
name = "python-dateutil"
version = "2.9.0.post0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "six" },
]
sdist = { url = "https://files.pythonhosted.org/packages/66/c0/0c8b6ad9f17a802ee498c46e004a0eb49bc148f2fd230864601a86dcf6db/python-dateutil-2.9.0.post0.tar.gz", hash = "sha256:37dd54208da7e1cd875388217d5e00ebd4179249f90fb72437e91a35459a0ad3", size = 342432, upload-time = "2024-03-01T18:36:20.211Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/ec/57/56b9bcc3c9c6a792fcbaf139543cee77261f3651ca9da0c93f5c1221264b/python_dateutil-2.9.0.post0-py2.py3-none-any.whl", hash = "sha256:a8b2bc7bffae282281c8140a97d3aa9c14da0b136dfe83f850eea9a5f7470427", size = 229892, upload-time = "2024-03-01T18:36:18.57Z" },
]

[[package]]
name = "python-docx"
version = "1.2.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "lxml" },
    { name = "typing-extensions" },
]
sdist = { url = "https://files.pythonhosted.org/packages/a9/f7/eddfe33871520adab45aaa1a71f0402a2252050c14c7e3009446c8f4701c/python_docx-1.2.0.tar.gz", hash = "sha256:7bc9d7b7d8a69c9c02ca09216118c86552704edc23bac179283f2e38f86220ce", size = 5723256, upload-time = "2025-06-16T20:46:27.921Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/d0/00/1e03a4989fa5795da308cd774f05b704ace555a70f9bf9d3be057b680bcf/python_docx-1.2.0-py3-none-any.whl", hash = "sha256:3fd478f3250fbbbfd3b94fe1e985955737c145627498896a8a6bf81f4baf66c7", size = 252987, upload-time = "2025-06-16T20:46:22.506Z" },
]

[[package]]
name = "python-dotenv"
version = "1.2.2"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/82/ed/0301aeeac3e5353ef3d94b6ec08bbcabd04a72018415dcb29e588514bba8/python_dotenv-1.2.2.tar.gz", hash = "sha256:2c371a91fbd7ba082c2c1dc1f8bf89ca22564a087c2c287cd9b662adde799cf3", size = 50135, upload-time = "2026-03-01T16:00:26.196Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/0b/d7/1959b9648791274998a9c3526f6d0ec8fd2233e4d4acce81bbae76b44b2a/python_dotenv-1.2.2-py3-none-any.whl", hash = "sha256:1d8214789a24de455a8b8bd8ae6fe3c6b69a5e3d64aa8a8e5d68e694bbcb285a", size = 22101, upload-time = "2026-03-01T16:00:25.09Z" },
]

[[package]]
name = "python-jose"
version = "3.5.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "ecdsa" },
    { name = "pyasn1" },
    { name = "rsa" },
]
sdist = { url = "https://files.pythonhosted.org/packages/c6/77/3a1c9039db7124eb039772b935f2244fbb73fc8ee65b9acf2375da1c07bf/python_jose-3.5.0.tar.gz", hash = "sha256:fb4eaa44dbeb1c26dcc69e4bd7ec54a1cb8dd64d3b4d81ef08d90ff453f2b01b", size = 92726, upload-time = "2025-05-28T17:31:54.288Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/d9/c3/0bd11992072e6a1c513b16500a5d07f91a24017c5909b02c72c62d7ad024/python_jose-3.5.0-py2.py3-none-any.whl", hash = "sha256:abd1202f23d34dfad2c3d28cb8617b90acf34132c7afd60abd0b0b7d3cb55771", size = 34624, upload-time = "2025-05-28T17:31:52.802Z" },
]

[package.optional-dependencies]
cryptography = [
    { name = "cryptography" },
]

[[package]]
name = "python-multipart"
version = "0.0.22"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/94/01/979e98d542a70714b0cb2b6728ed0b7c46792b695e3eaec3e20711271ca3/python_multipart-0.0.22.tar.gz", hash = "sha256:7340bef99a7e0032613f56dc36027b959fd3b30a787ed62d310e951f7c3a3a58", size = 37612, upload-time = "2026-01-25T10:15:56.219Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/1b/d0/397f9626e711ff749a95d96b7af99b9c566a9bb5129b8e4c10fc4d100304/python_multipart-0.0.22-py3-none-any.whl", hash = "sha256:2b2cd894c83d21bf49d702499531c7bafd057d730c201782048f7945d82de155", size = 24579, upload-time = "2026-01-25T10:15:54.811Z" },
]

[[package]]
name = "pyyaml"
version = "6.0.3"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/05/8e/961c0007c59b8dd7729d542c61a4d537767a59645b82a0b521206e1e25c2/pyyaml-6.0.3.tar.gz", hash = "sha256:d76623373421df22fb4cf8817020cbb7ef15c725b9d5e45f17e189bfc384190f", size = 130960, upload-time = "2025-09-25T21:33:16.546Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/6d/16/a95b6757765b7b031c9374925bb718d55e0a9ba8a1b6a12d25962ea44347/pyyaml-6.0.3-cp311-cp311-macosx_10_13_x86_64.whl", hash = "sha256:44edc647873928551a01e7a563d7452ccdebee747728c1080d881d68af7b997e", size = 185826, upload-time = "2025-09-25T21:31:58.655Z" },
    { url = "https://files.pythonhosted.org/packages/16/19/13de8e4377ed53079ee996e1ab0a9c33ec2faf808a4647b7b4c0d46dd239/pyyaml-6.0.3-cp311-cp311-macosx_11_0_arm64.whl", hash = "sha256:652cb6edd41e718550aad172851962662ff2681490a8a711af6a4d288dd96824", size = 175577, upload-time = "2025-09-25T21:32:00.088Z" },
    { url = "https://files.pythonhosted.org/packages/0c/62/d2eb46264d4b157dae1275b573017abec435397aa59cbcdab6fc978a8af4/pyyaml-6.0.3-cp311-cp311-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:10892704fc220243f5305762e276552a0395f7beb4dbf9b14ec8fd43b57f126c", size = 775556, upload-time = "2025-09-25T21:32:01.31Z" },
    { url = "https://files.pythonhosted.org/packages/10/cb/16c3f2cf3266edd25aaa00d6c4350381c8b012ed6f5276675b9eba8d9ff4/pyyaml-6.0.3-cp311-cp311-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:850774a7879607d3a6f50d36d04f00ee69e7fc816450e5f7e58d7f17f1ae5c00", size = 882114, upload-time = "2025-09-25T21:32:03.376Z" },
    { url = "https://files.pythonhosted.org/packages/71/60/917329f640924b18ff085ab889a11c763e0b573da888e8404ff486657602/pyyaml-6.0.3-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:b8bb0864c5a28024fac8a632c443c87c5aa6f215c0b126c449ae1a150412f31d", size = 806638, upload-time = "2025-09-25T21:32:04.553Z" },
    { url = "https://files.pythonhosted.org/packages/dd/6f/529b0f316a9fd167281a6c3826b5583e6192dba792dd55e3203d3f8e655a/pyyaml-6.0.3-cp311-cp311-musllinux_1_2_aarch64.whl", hash = "sha256:1d37d57ad971609cf3c53ba6a7e365e40660e3be0e5175fa9f2365a379d6095a", size = 767463, upload-time = "2025-09-25T21:32:06.152Z" },
    { url = "https://files.pythonhosted.org/packages/f2/6a/b627b4e0c1dd03718543519ffb2f1deea4a1e6d42fbab8021936a4d22589/pyyaml-6.0.3-cp311-cp311-musllinux_1_2_x86_64.whl", hash = "sha256:37503bfbfc9d2c40b344d06b2199cf0e96e97957ab1c1b546fd4f87e53e5d3e4", size = 794986, upload-time = "2025-09-25T21:32:07.367Z" },
    { url = "https://files.pythonhosted.org/packages/45/91/47a6e1c42d9ee337c4839208f30d9f09caa9f720ec7582917b264defc875/pyyaml-6.0.3-cp311-cp311-win32.whl", hash = "sha256:8098f252adfa6c80ab48096053f512f2321f0b998f98150cea9bd23d83e1467b", size = 142543, upload-time = "2025-09-25T21:32:08.95Z" },
    { url = "https://files.pythonhosted.org/packages/da/e3/ea007450a105ae919a72393cb06f122f288ef60bba2dc64b26e2646fa315/pyyaml-6.0.3-cp311-cp311-win_amd64.whl", hash = "sha256:9f3bfb4965eb874431221a3ff3fdcddc7e74e3b07799e0e84ca4a0f867d449bf", size = 158763, upload-time = "2025-09-25T21:32:09.96Z" },
    { url = "https://files.pythonhosted.org/packages/d1/33/422b98d2195232ca1826284a76852ad5a86fe23e31b009c9886b2d0fb8b2/pyyaml-6.0.3-cp312-cp312-macosx_10_13_x86_64.whl", hash = "sha256:7f047e29dcae44602496db43be01ad42fc6f1cc0d8cd6c83d342306c32270196", size = 182063, upload-time = "2025-09-25T21:32:11.445Z" },
    { url = "https://files.pythonhosted.org/packages/89/a0/6cf41a19a1f2f3feab0e9c0b74134aa2ce6849093d5517a0c550fe37a648/pyyaml-6.0.3-cp312-cp312-macosx_11_0_arm64.whl", hash = "sha256:fc09d0aa354569bc501d4e787133afc08552722d3ab34836a80547331bb5d4a0", size = 173973, upload-time = "2025-09-25T21:32:12.492Z" },
    { url = "https://files.pythonhosted.org/packages/ed/23/7a778b6bd0b9a8039df8b1b1d80e2e2ad78aa04171592c8a5c43a56a6af4/pyyaml-6.0.3-cp312-cp312-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:9149cad251584d5fb4981be1ecde53a1ca46c891a79788c0df828d2f166bda28", size = 775116, upload-time = "2025-09-25T21:32:13.652Z" },
    { url = "https://files.pythonhosted.org/packages/65/30/d7353c338e12baef4ecc1b09e877c1970bd3382789c159b4f89d6a70dc09/pyyaml-6.0.3-cp312-cp312-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:5fdec68f91a0c6739b380c83b951e2c72ac0197ace422360e6d5a959d8d97b2c", size = 844011, upload-time = "2025-09-25T21:32:15.21Z" },
    { url = "https://files.pythonhosted.org/packages/8b/9d/b3589d3877982d4f2329302ef98a8026e7f4443c765c46cfecc8858c6b4b/pyyaml-6.0.3-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:ba1cc08a7ccde2d2ec775841541641e4548226580ab850948cbfda66a1befcdc", size = 807870, upload-time = "2025-09-25T21:32:16.431Z" },
    { url = "https://files.pythonhosted.org/packages/05/c0/b3be26a015601b822b97d9149ff8cb5ead58c66f981e04fedf4e762f4bd4/pyyaml-6.0.3-cp312-cp312-musllinux_1_2_aarch64.whl", hash = "sha256:8dc52c23056b9ddd46818a57b78404882310fb473d63f17b07d5c40421e47f8e", size = 761089, upload-time = "2025-09-25T21:32:17.56Z" },
    { url = "https://files.pythonhosted.org/packages/be/8e/98435a21d1d4b46590d5459a22d88128103f8da4c2d4cb8f14f2a96504e1/pyyaml-6.0.3-cp312-cp312-musllinux_1_2_x86_64.whl", hash = "sha256:41715c910c881bc081f1e8872880d3c650acf13dfa8214bad49ed4cede7c34ea", size = 790181, upload-time = "2025-09-25T21:32:18.834Z" },
    { url = "https://files.pythonhosted.org/packages/74/93/7baea19427dcfbe1e5a372d81473250b379f04b1bd3c4c5ff825e2327202/pyyaml-6.0.3-cp312-cp312-win32.whl", hash = "sha256:96b533f0e99f6579b3d4d4995707cf36df9100d67e0c8303a0c55b27b5f99bc5", size = 137658, upload-time = "2025-09-25T21:32:20.209Z" },
    { url = "https://files.pythonhosted.org/packages/86/bf/899e81e4cce32febab4fb42bb97dcdf66bc135272882d1987881a4b519e9/pyyaml-6.0.3-cp312-cp312-win_amd64.whl", hash = "sha256:5fcd34e47f6e0b794d17de1b4ff496c00986e1c83f7ab2fb8fcfe9616ff7477b", size = 154003, upload-time = "2025-09-25T21:32:21.167Z" },
    { url = "https://files.pythonhosted.org/packages/1a/08/67bd04656199bbb51dbed1439b7f27601dfb576fb864099c7ef0c3e55531/pyyaml-6.0.3-cp312-cp312-win_arm64.whl", hash = "sha256:64386e5e707d03a7e172c0701abfb7e10f0fb753ee1d773128192742712a98fd", size = 140344, upload-time = "2025-09-25T21:32:22.617Z" },
    { url = "https://files.pythonhosted.org/packages/d1/11/0fd08f8192109f7169db964b5707a2f1e8b745d4e239b784a5a1dd80d1db/pyyaml-6.0.3-cp313-cp313-macosx_10_13_x86_64.whl", hash = "sha256:8da9669d359f02c0b91ccc01cac4a67f16afec0dac22c2ad09f46bee0697eba8", size = 181669, upload-time = "2025-09-25T21:32:23.673Z" },
    { url = "https://files.pythonhosted.org/packages/b1/16/95309993f1d3748cd644e02e38b75d50cbc0d9561d21f390a76242ce073f/pyyaml-6.0.3-cp313-cp313-macosx_11_0_arm64.whl", hash = "sha256:2283a07e2c21a2aa78d9c4442724ec1eb15f5e42a723b99cb3d822d48f5f7ad1", size = 173252, upload-time = "2025-09-25T21:32:25.149Z" },
    { url = "https://files.pythonhosted.org/packages/50/31/b20f376d3f810b9b2371e72ef5adb33879b25edb7a6d072cb7ca0c486398/pyyaml-6.0.3-cp313-cp313-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:ee2922902c45ae8ccada2c5b501ab86c36525b883eff4255313a253a3160861c", size = 767081, upload-time = "2025-09-25T21:32:26.575Z" },
    { url = "https://files.pythonhosted.org/packages/49/1e/a55ca81e949270d5d4432fbbd19dfea5321eda7c41a849d443dc92fd1ff7/pyyaml-6.0.3-cp313-cp313-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:a33284e20b78bd4a18c8c2282d549d10bc8408a2a7ff57653c0cf0b9be0afce5", size = 841159, upload-time = "2025-09-25T21:32:27.727Z" },
    { url = "https://files.pythonhosted.org/packages/74/27/e5b8f34d02d9995b80abcef563ea1f8b56d20134d8f4e5e81733b1feceb2/pyyaml-6.0.3-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:0f29edc409a6392443abf94b9cf89ce99889a1dd5376d94316ae5145dfedd5d6", size = 801626, upload-time = "2025-09-25T21:32:28.878Z" },
    { url = "https://files.pythonhosted.org/packages/f9/11/ba845c23988798f40e52ba45f34849aa8a1f2d4af4b798588010792ebad6/pyyaml-6.0.3-cp313-cp313-musllinux_1_2_aarch64.whl", hash = "sha256:f7057c9a337546edc7973c0d3ba84ddcdf0daa14533c2065749c9075001090e6", size = 753613, upload-time = "2025-09-25T21:32:30.178Z" },
    { url = "https://files.pythonhosted.org/packages/3d/e0/7966e1a7bfc0a45bf0a7fb6b98ea03fc9b8d84fa7f2229e9659680b69ee3/pyyaml-6.0.3-cp313-cp313-musllinux_1_2_x86_64.whl", hash = "sha256:eda16858a3cab07b80edaf74336ece1f986ba330fdb8ee0d6c0d68fe82bc96be", size = 794115, upload-time = "2025-09-25T21:32:31.353Z" },
    { url = "https://files.pythonhosted.org/packages/de/94/980b50a6531b3019e45ddeada0626d45fa85cbe22300844a7983285bed3b/pyyaml-6.0.3-cp313-cp313-win32.whl", hash = "sha256:d0eae10f8159e8fdad514efdc92d74fd8d682c933a6dd088030f3834bc8e6b26", size = 137427, upload-time = "2025-09-25T21:32:32.58Z" },
    { url = "https://files.pythonhosted.org/packages/97/c9/39d5b874e8b28845e4ec2202b5da735d0199dbe5b8fb85f91398814a9a46/pyyaml-6.0.3-cp313-cp313-win_amd64.whl", hash = "sha256:79005a0d97d5ddabfeeea4cf676af11e647e41d81c9a7722a193022accdb6b7c", size = 154090, upload-time = "2025-09-25T21:32:33.659Z" },
    { url = "https://files.pythonhosted.org/packages/73/e8/2bdf3ca2090f68bb3d75b44da7bbc71843b19c9f2b9cb9b0f4ab7a5a4329/pyyaml-6.0.3-cp313-cp313-win_arm64.whl", hash = "sha256:5498cd1645aa724a7c71c8f378eb29ebe23da2fc0d7a08071d89469bf1d2defb", size = 140246, upload-time = "2025-09-25T21:32:34.663Z" },
    { url = "https://files.pythonhosted.org/packages/9d/8c/f4bd7f6465179953d3ac9bc44ac1a8a3e6122cf8ada906b4f96c60172d43/pyyaml-6.0.3-cp314-cp314-macosx_10_13_x86_64.whl", hash = "sha256:8d1fab6bb153a416f9aeb4b8763bc0f22a5586065f86f7664fc23339fc1c1fac", size = 181814, upload-time = "2025-09-25T21:32:35.712Z" },
    { url = "https://files.pythonhosted.org/packages/bd/9c/4d95bb87eb2063d20db7b60faa3840c1b18025517ae857371c4dd55a6b3a/pyyaml-6.0.3-cp314-cp314-macosx_11_0_arm64.whl", hash = "sha256:34d5fcd24b8445fadc33f9cf348c1047101756fd760b4dacb5c3e99755703310", size = 173809, upload-time = "2025-09-25T21:32:36.789Z" },
    { url = "https://files.pythonhosted.org/packages/92/b5/47e807c2623074914e29dabd16cbbdd4bf5e9b2db9f8090fa64411fc5382/pyyaml-6.0.3-cp314-cp314-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:501a031947e3a9025ed4405a168e6ef5ae3126c59f90ce0cd6f2bfc477be31b7", size = 766454, upload-time = "2025-09-25T21:32:37.966Z" },
    { url = "https://files.pythonhosted.org/packages/02/9e/e5e9b168be58564121efb3de6859c452fccde0ab093d8438905899a3a483/pyyaml-6.0.3-cp314-cp314-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:b3bc83488de33889877a0f2543ade9f70c67d66d9ebb4ac959502e12de895788", size = 836355, upload-time = "2025-09-25T21:32:39.178Z" },
    { url = "https://files.pythonhosted.org/packages/88/f9/16491d7ed2a919954993e48aa941b200f38040928474c9e85ea9e64222c3/pyyaml-6.0.3-cp314-cp314-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:c458b6d084f9b935061bc36216e8a69a7e293a2f1e68bf956dcd9e6cbcd143f5", size = 794175, upload-time = "2025-09-25T21:32:40.865Z" },
    { url = "https://files.pythonhosted.org/packages/dd/3f/5989debef34dc6397317802b527dbbafb2b4760878a53d4166579111411e/pyyaml-6.0.3-cp314-cp314-musllinux_1_2_aarch64.whl", hash = "sha256:7c6610def4f163542a622a73fb39f534f8c101d690126992300bf3207eab9764", size = 755228, upload-time = "2025-09-25T21:32:42.084Z" },
    { url = "https://files.pythonhosted.org/packages/d7/ce/af88a49043cd2e265be63d083fc75b27b6ed062f5f9fd6cdc223ad62f03e/pyyaml-6.0.3-cp314-cp314-musllinux_1_2_x86_64.whl", hash = "sha256:5190d403f121660ce8d1d2c1bb2ef1bd05b5f68533fc5c2ea899bd15f4399b35", size = 789194, upload-time = "2025-09-25T21:32:43.362Z" },
    { url = "https://files.pythonhosted.org/packages/23/20/bb6982b26a40bb43951265ba29d4c246ef0ff59c9fdcdf0ed04e0687de4d/pyyaml-6.0.3-cp314-cp314-win_amd64.whl", hash = "sha256:4a2e8cebe2ff6ab7d1050ecd59c25d4c8bd7e6f400f5f82b96557ac0abafd0ac", size = 156429, upload-time = "2025-09-25T21:32:57.844Z" },
    { url = "https://files.pythonhosted.org/packages/f4/f4/a4541072bb9422c8a883ab55255f918fa378ecf083f5b85e87fc2b4eda1b/pyyaml-6.0.3-cp314-cp314-win_arm64.whl", hash = "sha256:93dda82c9c22deb0a405ea4dc5f2d0cda384168e466364dec6255b293923b2f3", size = 143912, upload-time = "2025-09-25T21:32:59.247Z" },
    { url = "https://files.pythonhosted.org/packages/7c/f9/07dd09ae774e4616edf6cda684ee78f97777bdd15847253637a6f052a62f/pyyaml-6.0.3-cp314-cp314t-macosx_10_13_x86_64.whl", hash = "sha256:02893d100e99e03eda1c8fd5c441d8c60103fd175728e23e431db1b589cf5ab3", size = 189108, upload-time = "2025-09-25T21:32:44.377Z" },
    { url = "https://files.pythonhosted.org/packages/4e/78/8d08c9fb7ce09ad8c38ad533c1191cf27f7ae1effe5bb9400a46d9437fcf/pyyaml-6.0.3-cp314-cp314t-macosx_11_0_arm64.whl", hash = "sha256:c1ff362665ae507275af2853520967820d9124984e0f7466736aea23d8611fba", size = 183641, upload-time = "2025-09-25T21:32:45.407Z" },
    { url = "https://files.pythonhosted.org/packages/7b/5b/3babb19104a46945cf816d047db2788bcaf8c94527a805610b0289a01c6b/pyyaml-6.0.3-cp314-cp314t-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:6adc77889b628398debc7b65c073bcb99c4a0237b248cacaf3fe8a557563ef6c", size = 831901, upload-time = "2025-09-25T21:32:48.83Z" },
    { url = "https://files.pythonhosted.org/packages/8b/cc/dff0684d8dc44da4d22a13f35f073d558c268780ce3c6ba1b87055bb0b87/pyyaml-6.0.3-cp314-cp314t-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:a80cb027f6b349846a3bf6d73b5e95e782175e52f22108cfa17876aaeff93702", size = 861132, upload-time = "2025-09-25T21:32:50.149Z" },
    { url = "https://files.pythonhosted.org/packages/b1/5e/f77dc6b9036943e285ba76b49e118d9ea929885becb0a29ba8a7c75e29fe/pyyaml-6.0.3-cp314-cp314t-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:00c4bdeba853cc34e7dd471f16b4114f4162dc03e6b7afcc2128711f0eca823c", size = 839261, upload-time = "2025-09-25T21:32:51.808Z" },
    { url = "https://files.pythonhosted.org/packages/ce/88/a9db1376aa2a228197c58b37302f284b5617f56a5d959fd1763fb1675ce6/pyyaml-6.0.3-cp314-cp314t-musllinux_1_2_aarch64.whl", hash = "sha256:66e1674c3ef6f541c35191caae2d429b967b99e02040f5ba928632d9a7f0f065", size = 805272, upload-time = "2025-09-25T21:32:52.941Z" },
    { url = "https://files.pythonhosted.org/packages/da/92/1446574745d74df0c92e6aa4a7b0b3130706a4142b2d1a5869f2eaa423c6/pyyaml-6.0.3-cp314-cp314t-musllinux_1_2_x86_64.whl", hash = "sha256:16249ee61e95f858e83976573de0f5b2893b3677ba71c9dd36b9cf8be9ac6d65", size = 829923, upload-time = "2025-09-25T21:32:54.537Z" },
    { url = "https://files.pythonhosted.org/packages/f0/7a/1c7270340330e575b92f397352af856a8c06f230aa3e76f86b39d01b416a/pyyaml-6.0.3-cp314-cp314t-win_amd64.whl", hash = "sha256:4ad1906908f2f5ae4e5a8ddfce73c320c2a1429ec52eafd27138b7f1cbe341c9", size = 174062, upload-time = "2025-09-25T21:32:55.767Z" },
    { url = "https://files.pythonhosted.org/packages/f1/12/de94a39c2ef588c7e6455cfbe7343d3b2dc9d6b6b2f40c4c6565744c873d/pyyaml-6.0.3-cp314-cp314t-win_arm64.whl", hash = "sha256:ebc55a14a21cb14062aa4162f906cd962b28e2e9ea38f9b4391244cd8de4ae0b", size = 149341, upload-time = "2025-09-25T21:32:56.828Z" },
]

[[package]]
name = "referencing"
version = "0.37.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "attrs" },
    { name = "rpds-py" },
    { name = "typing-extensions", marker = "python_full_version < '3.13'" },
]
sdist = { url = "https://files.pythonhosted.org/packages/22/f5/df4e9027acead3ecc63e50fe1e36aca1523e1719559c499951bb4b53188f/referencing-0.37.0.tar.gz", hash = "sha256:44aefc3142c5b842538163acb373e24cce6632bd54bdb01b21ad5863489f50d8", size = 78036, upload-time = "2025-10-13T15:30:48.871Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/2c/58/ca301544e1fa93ed4f80d724bf5b194f6e4b945841c5bfd555878eea9fcb/referencing-0.37.0-py3-none-any.whl", hash = "sha256:381329a9f99628c9069361716891d34ad94af76e461dcb0335825aecc7692231", size = 26766, upload-time = "2025-10-13T15:30:47.625Z" },
]

[[package]]
name = "requests"
version = "2.33.1"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "certifi" },
    { name = "charset-normalizer" },
    { name = "idna" },
    { name = "urllib3" },
]
sdist = { url = "https://files.pythonhosted.org/packages/5f/a4/98b9c7c6428a668bf7e42ebb7c79d576a1c3c1e3ae2d47e674b468388871/requests-2.33.1.tar.gz", hash = "sha256:18817f8c57c6263968bc123d237e3b8b08ac046f5456bd1e307ee8f4250d3517", size = 134120, upload-time = "2026-03-30T16:09:15.531Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/d7/8e/7540e8a2036f79a125c1d2ebadf69ed7901608859186c856fa0388ef4197/requests-2.33.1-py3-none-any.whl", hash = "sha256:4e6d1ef462f3626a1f0a0a9c42dd93c63bad33f9f1c1937509b8c5c8718ab56a", size = 64947, upload-time = "2026-03-30T16:09:13.83Z" },
]

[[package]]
name = "requests-oauthlib"
version = "2.0.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "oauthlib" },
    { name = "requests" },
]
sdist = { url = "https://files.pythonhosted.org/packages/42/f2/05f29bc3913aea15eb670be136045bf5c5bbf4b99ecb839da9b422bb2c85/requests-oauthlib-2.0.0.tar.gz", hash = "sha256:b3dffaebd884d8cd778494369603a9e7b58d29111bf6b41bdc2dcd87203af4e9", size = 55650, upload-time = "2024-03-22T20:32:29.939Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/3b/5d/63d4ae3b9daea098d5d6f5da83984853c1bbacd5dc826764b249fe119d24/requests_oauthlib-2.0.0-py2.py3-none-any.whl", hash = "sha256:7dd8a5c40426b779b0868c404bdef9768deccf22749cde15852df527e6269b36", size = 24179, upload-time = "2024-03-22T20:32:28.055Z" },
]

[[package]]
name = "requests-toolbelt"
version = "1.0.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "requests" },
]
sdist = { url = "https://files.pythonhosted.org/packages/f3/61/d7545dafb7ac2230c70d38d31cbfe4cc64f7144dc41f6e4e4b78ecd9f5bb/requests-toolbelt-1.0.0.tar.gz", hash = "sha256:7681a0a3d047012b5bdc0ee37d7f8f07ebe76ab08caeccfc3921ce23c88d5bc6", size = 206888, upload-time = "2023-05-01T04:11:33.229Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/3f/51/d4db610ef29373b879047326cbf6fa98b6c1969d6f6dc423279de2b1be2c/requests_toolbelt-1.0.0-py2.py3-none-any.whl", hash = "sha256:cccfdd665f0a24fcf4726e690f65639d272bb0637b9b92dfd91a5568ccf6bd06", size = 54481, upload-time = "2023-05-01T04:11:28.427Z" },
]

[[package]]
name = "rich"
version = "14.3.3"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "markdown-it-py" },
    { name = "pygments" },
]
sdist = { url = "https://files.pythonhosted.org/packages/b3/c6/f3b320c27991c46f43ee9d856302c70dc2d0fb2dba4842ff739d5f46b393/rich-14.3.3.tar.gz", hash = "sha256:b8daa0b9e4eef54dd8cf7c86c03713f53241884e814f4e2f5fb342fe520f639b", size = 230582, upload-time = "2026-02-19T17:23:12.474Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/14/25/b208c5683343959b670dc001595f2f3737e051da617f66c31f7c4fa93abc/rich-14.3.3-py3-none-any.whl", hash = "sha256:793431c1f8619afa7d3b52b2cdec859562b950ea0d4b6b505397612db8d5362d", size = 310458, upload-time = "2026-02-19T17:23:13.732Z" },
]

[[package]]
name = "rpds-py"
version = "0.30.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/20/af/3f2f423103f1113b36230496629986e0ef7e199d2aa8392452b484b38ced/rpds_py-0.30.0.tar.gz", hash = "sha256:dd8ff7cf90014af0c0f787eea34794ebf6415242ee1d6fa91eaba725cc441e84", size = 69469, upload-time = "2025-11-30T20:24:38.837Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/4d/6e/f964e88b3d2abee2a82c1ac8366da848fce1c6d834dc2132c3fda3970290/rpds_py-0.30.0-cp311-cp311-macosx_10_12_x86_64.whl", hash = "sha256:a2bffea6a4ca9f01b3f8e548302470306689684e61602aa3d141e34da06cf425", size = 370157, upload-time = "2025-11-30T20:21:53.789Z" },
    { url = "https://files.pythonhosted.org/packages/94/ba/24e5ebb7c1c82e74c4e4f33b2112a5573ddc703915b13a073737b59b86e0/rpds_py-0.30.0-cp311-cp311-macosx_11_0_arm64.whl", hash = "sha256:dc4f992dfe1e2bc3ebc7444f6c7051b4bc13cd8e33e43511e8ffd13bf407010d", size = 359676, upload-time = "2025-11-30T20:21:55.475Z" },
    { url = "https://files.pythonhosted.org/packages/84/86/04dbba1b087227747d64d80c3b74df946b986c57af0a9f0c98726d4d7a3b/rpds_py-0.30.0-cp311-cp311-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:422c3cb9856d80b09d30d2eb255d0754b23e090034e1deb4083f8004bd0761e4", size = 389938, upload-time = "2025-11-30T20:21:57.079Z" },
    { url = "https://files.pythonhosted.org/packages/42/bb/1463f0b1722b7f45431bdd468301991d1328b16cffe0b1c2918eba2c4eee/rpds_py-0.30.0-cp311-cp311-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:07ae8a593e1c3c6b82ca3292efbe73c30b61332fd612e05abee07c79359f292f", size = 402932, upload-time = "2025-11-30T20:21:58.47Z" },
    { url = "https://files.pythonhosted.org/packages/99/ee/2520700a5c1f2d76631f948b0736cdf9b0acb25abd0ca8e889b5c62ac2e3/rpds_py-0.30.0-cp311-cp311-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:12f90dd7557b6bd57f40abe7747e81e0c0b119bef015ea7726e69fe550e394a4", size = 525830, upload-time = "2025-11-30T20:21:59.699Z" },
    { url = "https://files.pythonhosted.org/packages/e0/ad/bd0331f740f5705cc555a5e17fdf334671262160270962e69a2bdef3bf76/rpds_py-0.30.0-cp311-cp311-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:99b47d6ad9a6da00bec6aabe5a6279ecd3c06a329d4aa4771034a21e335c3a97", size = 412033, upload-time = "2025-11-30T20:22:00.991Z" },
    { url = "https://files.pythonhosted.org/packages/f8/1e/372195d326549bb51f0ba0f2ecb9874579906b97e08880e7a65c3bef1a99/rpds_py-0.30.0-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:33f559f3104504506a44bb666b93a33f5d33133765b0c216a5bf2f1e1503af89", size = 390828, upload-time = "2025-11-30T20:22:02.723Z" },
    { url = "https://files.pythonhosted.org/packages/ab/2b/d88bb33294e3e0c76bc8f351a3721212713629ffca1700fa94979cb3eae8/rpds_py-0.30.0-cp311-cp311-manylinux_2_31_riscv64.whl", hash = "sha256:946fe926af6e44f3697abbc305ea168c2c31d3e3ef1058cf68f379bf0335a78d", size = 404683, upload-time = "2025-11-30T20:22:04.367Z" },
    { url = "https://files.pythonhosted.org/packages/50/32/c759a8d42bcb5289c1fac697cd92f6fe01a018dd937e62ae77e0e7f15702/rpds_py-0.30.0-cp311-cp311-manylinux_2_5_i686.manylinux1_i686.whl", hash = "sha256:495aeca4b93d465efde585977365187149e75383ad2684f81519f504f5c13038", size = 421583, upload-time = "2025-11-30T20:22:05.814Z" },
    { url = "https://files.pythonhosted.org/packages/2b/81/e729761dbd55ddf5d84ec4ff1f47857f4374b0f19bdabfcf929164da3e24/rpds_py-0.30.0-cp311-cp311-musllinux_1_2_aarch64.whl", hash = "sha256:d9a0ca5da0386dee0655b4ccdf46119df60e0f10da268d04fe7cc87886872ba7", size = 572496, upload-time = "2025-11-30T20:22:07.713Z" },
    { url = "https://files.pythonhosted.org/packages/14/f6/69066a924c3557c9c30baa6ec3a0aa07526305684c6f86c696b08860726c/rpds_py-0.30.0-cp311-cp311-musllinux_1_2_i686.whl", hash = "sha256:8d6d1cc13664ec13c1b84241204ff3b12f9bb82464b8ad6e7a5d3486975c2eed", size = 598669, upload-time = "2025-11-30T20:22:09.312Z" },
    { url = "https://files.pythonhosted.org/packages/5f/48/905896b1eb8a05630d20333d1d8ffd162394127b74ce0b0784ae04498d32/rpds_py-0.30.0-cp311-cp311-musllinux_1_2_x86_64.whl", hash = "sha256:3896fa1be39912cf0757753826bc8bdc8ca331a28a7c4ae46b7a21280b06bb85", size = 561011, upload-time = "2025-11-30T20:22:11.309Z" },
    { url = "https://files.pythonhosted.org/packages/22/16/cd3027c7e279d22e5eb431dd3c0fbc677bed58797fe7581e148f3f68818b/rpds_py-0.30.0-cp311-cp311-win32.whl", hash = "sha256:55f66022632205940f1827effeff17c4fa7ae1953d2b74a8581baaefb7d16f8c", size = 221406, upload-time = "2025-11-30T20:22:13.101Z" },
    { url = "https://files.pythonhosted.org/packages/fa/5b/e7b7aa136f28462b344e652ee010d4de26ee9fd16f1bfd5811f5153ccf89/rpds_py-0.30.0-cp311-cp311-win_amd64.whl", hash = "sha256:a51033ff701fca756439d641c0ad09a41d9242fa69121c7d8769604a0a629825", size = 236024, upload-time = "2025-11-30T20:22:14.853Z" },
    { url = "https://files.pythonhosted.org/packages/14/a6/364bba985e4c13658edb156640608f2c9e1d3ea3c81b27aa9d889fff0e31/rpds_py-0.30.0-cp311-cp311-win_arm64.whl", hash = "sha256:47b0ef6231c58f506ef0b74d44e330405caa8428e770fec25329ed2cb971a229", size = 229069, upload-time = "2025-11-30T20:22:16.577Z" },
    { url = "https://files.pythonhosted.org/packages/03/e7/98a2f4ac921d82f33e03f3835f5bf3a4a40aa1bfdc57975e74a97b2b4bdd/rpds_py-0.30.0-cp312-cp312-macosx_10_12_x86_64.whl", hash = "sha256:a161f20d9a43006833cd7068375a94d035714d73a172b681d8881820600abfad", size = 375086, upload-time = "2025-11-30T20:22:17.93Z" },
    { url = "https://files.pythonhosted.org/packages/4d/a1/bca7fd3d452b272e13335db8d6b0b3ecde0f90ad6f16f3328c6fb150c889/rpds_py-0.30.0-cp312-cp312-macosx_11_0_arm64.whl", hash = "sha256:6abc8880d9d036ecaafe709079969f56e876fcf107f7a8e9920ba6d5a3878d05", size = 359053, upload-time = "2025-11-30T20:22:19.297Z" },
    { url = "https://files.pythonhosted.org/packages/65/1c/ae157e83a6357eceff62ba7e52113e3ec4834a84cfe07fa4b0757a7d105f/rpds_py-0.30.0-cp312-cp312-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:ca28829ae5f5d569bb62a79512c842a03a12576375d5ece7d2cadf8abe96ec28", size = 390763, upload-time = "2025-11-30T20:22:21.661Z" },
    { url = "https://files.pythonhosted.org/packages/d4/36/eb2eb8515e2ad24c0bd43c3ee9cd74c33f7ca6430755ccdb240fd3144c44/rpds_py-0.30.0-cp312-cp312-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:a1010ed9524c73b94d15919ca4d41d8780980e1765babf85f9a2f90d247153dd", size = 408951, upload-time = "2025-11-30T20:22:23.408Z" },
    { url = "https://files.pythonhosted.org/packages/d6/65/ad8dc1784a331fabbd740ef6f71ce2198c7ed0890dab595adb9ea2d775a1/rpds_py-0.30.0-cp312-cp312-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:f8d1736cfb49381ba528cd5baa46f82fdc65c06e843dab24dd70b63d09121b3f", size = 514622, upload-time = "2025-11-30T20:22:25.16Z" },
    { url = "https://files.pythonhosted.org/packages/63/8e/0cfa7ae158e15e143fe03993b5bcd743a59f541f5952e1546b1ac1b5fd45/rpds_py-0.30.0-cp312-cp312-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:d948b135c4693daff7bc2dcfc4ec57237a29bd37e60c2fabf5aff2bbacf3e2f1", size = 414492, upload-time = "2025-11-30T20:22:26.505Z" },
    { url = "https://files.pythonhosted.org/packages/60/1b/6f8f29f3f995c7ffdde46a626ddccd7c63aefc0efae881dc13b6e5d5bb16/rpds_py-0.30.0-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:47f236970bccb2233267d89173d3ad2703cd36a0e2a6e92d0560d333871a3d23", size = 394080, upload-time = "2025-11-30T20:22:27.934Z" },
    { url = "https://files.pythonhosted.org/packages/6d/d5/a266341051a7a3ca2f4b750a3aa4abc986378431fc2da508c5034d081b70/rpds_py-0.30.0-cp312-cp312-manylinux_2_31_riscv64.whl", hash = "sha256:2e6ecb5a5bcacf59c3f912155044479af1d0b6681280048b338b28e364aca1f6", size = 408680, upload-time = "2025-11-30T20:22:29.341Z" },
    { url = "https://files.pythonhosted.org/packages/10/3b/71b725851df9ab7a7a4e33cf36d241933da66040d195a84781f49c50490c/rpds_py-0.30.0-cp312-cp312-manylinux_2_5_i686.manylinux1_i686.whl", hash = "sha256:a8fa71a2e078c527c3e9dc9fc5a98c9db40bcc8a92b4e8858e36d329f8684b51", size = 423589, upload-time = "2025-11-30T20:22:31.469Z" },
    { url = "https://files.pythonhosted.org/packages/00/2b/e59e58c544dc9bd8bd8384ecdb8ea91f6727f0e37a7131baeff8d6f51661/rpds_py-0.30.0-cp312-cp312-musllinux_1_2_aarch64.whl", hash = "sha256:73c67f2db7bc334e518d097c6d1e6fed021bbc9b7d678d6cc433478365d1d5f5", size = 573289, upload-time = "2025-11-30T20:22:32.997Z" },
    { url = "https://files.pythonhosted.org/packages/da/3e/a18e6f5b460893172a7d6a680e86d3b6bc87a54c1f0b03446a3c8c7b588f/rpds_py-0.30.0-cp312-cp312-musllinux_1_2_i686.whl", hash = "sha256:5ba103fb455be00f3b1c2076c9d4264bfcb037c976167a6047ed82f23153f02e", size = 599737, upload-time = "2025-11-30T20:22:34.419Z" },
    { url = "https://files.pythonhosted.org/packages/5c/e2/714694e4b87b85a18e2c243614974413c60aa107fd815b8cbc42b873d1d7/rpds_py-0.30.0-cp312-cp312-musllinux_1_2_x86_64.whl", hash = "sha256:7cee9c752c0364588353e627da8a7e808a66873672bcb5f52890c33fd965b394", size = 563120, upload-time = "2025-11-30T20:22:35.903Z" },
    { url = "https://files.pythonhosted.org/packages/6f/ab/d5d5e3bcedb0a77f4f613706b750e50a5a3ba1c15ccd3665ecc636c968fd/rpds_py-0.30.0-cp312-cp312-win32.whl", hash = "sha256:1ab5b83dbcf55acc8b08fc62b796ef672c457b17dbd7820a11d6c52c06839bdf", size = 223782, upload-time = "2025-11-30T20:22:37.271Z" },
    { url = "https://files.pythonhosted.org/packages/39/3b/f786af9957306fdc38a74cef405b7b93180f481fb48453a114bb6465744a/rpds_py-0.30.0-cp312-cp312-win_amd64.whl", hash = "sha256:a090322ca841abd453d43456ac34db46e8b05fd9b3b4ac0c78bcde8b089f959b", size = 240463, upload-time = "2025-11-30T20:22:39.021Z" },
    { url = "https://files.pythonhosted.org/packages/f3/d2/b91dc748126c1559042cfe41990deb92c4ee3e2b415f6b5234969ffaf0cc/rpds_py-0.30.0-cp312-cp312-win_arm64.whl", hash = "sha256:669b1805bd639dd2989b281be2cfd951c6121b65e729d9b843e9639ef1fd555e", size = 230868, upload-time = "2025-11-30T20:22:40.493Z" },
    { url = "https://files.pythonhosted.org/packages/ed/dc/d61221eb88ff410de3c49143407f6f3147acf2538c86f2ab7ce65ae7d5f9/rpds_py-0.30.0-cp313-cp313-macosx_10_12_x86_64.whl", hash = "sha256:f83424d738204d9770830d35290ff3273fbb02b41f919870479fab14b9d303b2", size = 374887, upload-time = "2025-11-30T20:22:41.812Z" },
    { url = "https://files.pythonhosted.org/packages/fd/32/55fb50ae104061dbc564ef15cc43c013dc4a9f4527a1f4d99baddf56fe5f/rpds_py-0.30.0-cp313-cp313-macosx_11_0_arm64.whl", hash = "sha256:e7536cd91353c5273434b4e003cbda89034d67e7710eab8761fd918ec6c69cf8", size = 358904, upload-time = "2025-11-30T20:22:43.479Z" },
    { url = "https://files.pythonhosted.org/packages/58/70/faed8186300e3b9bdd138d0273109784eea2396c68458ed580f885dfe7ad/rpds_py-0.30.0-cp313-cp313-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:2771c6c15973347f50fece41fc447c054b7ac2ae0502388ce3b6738cd366e3d4", size = 389945, upload-time = "2025-11-30T20:22:44.819Z" },
    { url = "https://files.pythonhosted.org/packages/bd/a8/073cac3ed2c6387df38f71296d002ab43496a96b92c823e76f46b8af0543/rpds_py-0.30.0-cp313-cp313-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:0a59119fc6e3f460315fe9d08149f8102aa322299deaa5cab5b40092345c2136", size = 407783, upload-time = "2025-11-30T20:22:46.103Z" },
    { url = "https://files.pythonhosted.org/packages/77/57/5999eb8c58671f1c11eba084115e77a8899d6e694d2a18f69f0ba471ec8b/rpds_py-0.30.0-cp313-cp313-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:76fec018282b4ead0364022e3c54b60bf368b9d926877957a8624b58419169b7", size = 515021, upload-time = "2025-11-30T20:22:47.458Z" },
    { url = "https://files.pythonhosted.org/packages/e0/af/5ab4833eadc36c0a8ed2bc5c0de0493c04f6c06de223170bd0798ff98ced/rpds_py-0.30.0-cp313-cp313-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:692bef75a5525db97318e8cd061542b5a79812d711ea03dbc1f6f8dbb0c5f0d2", size = 414589, upload-time = "2025-11-30T20:22:48.872Z" },
    { url = "https://files.pythonhosted.org/packages/b7/de/f7192e12b21b9e9a68a6d0f249b4af3fdcdff8418be0767a627564afa1f1/rpds_py-0.30.0-cp313-cp313-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:9027da1ce107104c50c81383cae773ef5c24d296dd11c99e2629dbd7967a20c6", size = 394025, upload-time = "2025-11-30T20:22:50.196Z" },
    { url = "https://files.pythonhosted.org/packages/91/c4/fc70cd0249496493500e7cc2de87504f5aa6509de1e88623431fec76d4b6/rpds_py-0.30.0-cp313-cp313-manylinux_2_31_riscv64.whl", hash = "sha256:9cf69cdda1f5968a30a359aba2f7f9aa648a9ce4b580d6826437f2b291cfc86e", size = 408895, upload-time = "2025-11-30T20:22:51.87Z" },
    { url = "https://files.pythonhosted.org/packages/58/95/d9275b05ab96556fefff73a385813eb66032e4c99f411d0795372d9abcea/rpds_py-0.30.0-cp313-cp313-manylinux_2_5_i686.manylinux1_i686.whl", hash = "sha256:a4796a717bf12b9da9d3ad002519a86063dcac8988b030e405704ef7d74d2d9d", size = 422799, upload-time = "2025-11-30T20:22:53.341Z" },
    { url = "https://files.pythonhosted.org/packages/06/c1/3088fc04b6624eb12a57eb814f0d4997a44b0d208d6cace713033ff1a6ba/rpds_py-0.30.0-cp313-cp313-musllinux_1_2_aarch64.whl", hash = "sha256:5d4c2aa7c50ad4728a094ebd5eb46c452e9cb7edbfdb18f9e1221f597a73e1e7", size = 572731, upload-time = "2025-11-30T20:22:54.778Z" },
    { url = "https://files.pythonhosted.org/packages/d8/42/c612a833183b39774e8ac8fecae81263a68b9583ee343db33ab571a7ce55/rpds_py-0.30.0-cp313-cp313-musllinux_1_2_i686.whl", hash = "sha256:ba81a9203d07805435eb06f536d95a266c21e5b2dfbf6517748ca40c98d19e31", size = 599027, upload-time = "2025-11-30T20:22:56.212Z" },
    { url = "https://files.pythonhosted.org/packages/5f/60/525a50f45b01d70005403ae0e25f43c0384369ad24ffe46e8d9068b50086/rpds_py-0.30.0-cp313-cp313-musllinux_1_2_x86_64.whl", hash = "sha256:945dccface01af02675628334f7cf49c2af4c1c904748efc5cf7bbdf0b579f95", size = 563020, upload-time = "2025-11-30T20:22:58.2Z" },
    { url = "https://files.pythonhosted.org/packages/0b/5d/47c4655e9bcd5ca907148535c10e7d489044243cc9941c16ed7cd53be91d/rpds_py-0.30.0-cp313-cp313-win32.whl", hash = "sha256:b40fb160a2db369a194cb27943582b38f79fc4887291417685f3ad693c5a1d5d", size = 223139, upload-time = "2025-11-30T20:23:00.209Z" },
    { url = "https://files.pythonhosted.org/packages/f2/e1/485132437d20aa4d3e1d8b3fb5a5e65aa8139f1e097080c2a8443201742c/rpds_py-0.30.0-cp313-cp313-win_amd64.whl", hash = "sha256:806f36b1b605e2d6a72716f321f20036b9489d29c51c91f4dd29a3e3afb73b15", size = 240224, upload-time = "2025-11-30T20:23:02.008Z" },
    { url = "https://files.pythonhosted.org/packages/24/95/ffd128ed1146a153d928617b0ef673960130be0009c77d8fbf0abe306713/rpds_py-0.30.0-cp313-cp313-win_arm64.whl", hash = "sha256:d96c2086587c7c30d44f31f42eae4eac89b60dabbac18c7669be3700f13c3ce1", size = 230645, upload-time = "2025-11-30T20:23:03.43Z" },
    { url = "https://files.pythonhosted.org/packages/ff/1b/b10de890a0def2a319a2626334a7f0ae388215eb60914dbac8a3bae54435/rpds_py-0.30.0-cp313-cp313t-macosx_10_12_x86_64.whl", hash = "sha256:eb0b93f2e5c2189ee831ee43f156ed34e2a89a78a66b98cadad955972548be5a", size = 364443, upload-time = "2025-11-30T20:23:04.878Z" },
    { url = "https://files.pythonhosted.org/packages/0d/bf/27e39f5971dc4f305a4fb9c672ca06f290f7c4e261c568f3dea16a410d47/rpds_py-0.30.0-cp313-cp313t-macosx_11_0_arm64.whl", hash = "sha256:922e10f31f303c7c920da8981051ff6d8c1a56207dbdf330d9047f6d30b70e5e", size = 353375, upload-time = "2025-11-30T20:23:06.342Z" },
    { url = "https://files.pythonhosted.org/packages/40/58/442ada3bba6e8e6615fc00483135c14a7538d2ffac30e2d933ccf6852232/rpds_py-0.30.0-cp313-cp313t-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:cdc62c8286ba9bf7f47befdcea13ea0e26bf294bda99758fd90535cbaf408000", size = 383850, upload-time = "2025-11-30T20:23:07.825Z" },
    { url = "https://files.pythonhosted.org/packages/14/14/f59b0127409a33c6ef6f5c1ebd5ad8e32d7861c9c7adfa9a624fc3889f6c/rpds_py-0.30.0-cp313-cp313t-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:47f9a91efc418b54fb8190a6b4aa7813a23fb79c51f4bb84e418f5476c38b8db", size = 392812, upload-time = "2025-11-30T20:23:09.228Z" },
    { url = "https://files.pythonhosted.org/packages/b3/66/e0be3e162ac299b3a22527e8913767d869e6cc75c46bd844aa43fb81ab62/rpds_py-0.30.0-cp313-cp313t-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:1f3587eb9b17f3789ad50824084fa6f81921bbf9a795826570bda82cb3ed91f2", size = 517841, upload-time = "2025-11-30T20:23:11.186Z" },
    { url = "https://files.pythonhosted.org/packages/3d/55/fa3b9cf31d0c963ecf1ba777f7cf4b2a2c976795ac430d24a1f43d25a6ba/rpds_py-0.30.0-cp313-cp313t-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:39c02563fc592411c2c61d26b6c5fe1e51eaa44a75aa2c8735ca88b0d9599daa", size = 408149, upload-time = "2025-11-30T20:23:12.864Z" },
    { url = "https://files.pythonhosted.org/packages/60/ca/780cf3b1a32b18c0f05c441958d3758f02544f1d613abf9488cd78876378/rpds_py-0.30.0-cp313-cp313t-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:51a1234d8febafdfd33a42d97da7a43f5dcb120c1060e352a3fbc0c6d36e2083", size = 383843, upload-time = "2025-11-30T20:23:14.638Z" },
    { url = "https://files.pythonhosted.org/packages/82/86/d5f2e04f2aa6247c613da0c1dd87fcd08fa17107e858193566048a1e2f0a/rpds_py-0.30.0-cp313-cp313t-manylinux_2_31_riscv64.whl", hash = "sha256:eb2c4071ab598733724c08221091e8d80e89064cd472819285a9ab0f24bcedb9", size = 396507, upload-time = "2025-11-30T20:23:16.105Z" },
    { url = "https://files.pythonhosted.org/packages/4b/9a/453255d2f769fe44e07ea9785c8347edaf867f7026872e76c1ad9f7bed92/rpds_py-0.30.0-cp313-cp313t-manylinux_2_5_i686.manylinux1_i686.whl", hash = "sha256:6bdfdb946967d816e6adf9a3d8201bfad269c67efe6cefd7093ef959683c8de0", size = 414949, upload-time = "2025-11-30T20:23:17.539Z" },
    { url = "https://files.pythonhosted.org/packages/a3/31/622a86cdc0c45d6df0e9ccb6becdba5074735e7033c20e401a6d9d0e2ca0/rpds_py-0.30.0-cp313-cp313t-musllinux_1_2_aarch64.whl", hash = "sha256:c77afbd5f5250bf27bf516c7c4a016813eb2d3e116139aed0096940c5982da94", size = 565790, upload-time = "2025-11-30T20:23:19.029Z" },
    { url = "https://files.pythonhosted.org/packages/1c/5d/15bbf0fb4a3f58a3b1c67855ec1efcc4ceaef4e86644665fff03e1b66d8d/rpds_py-0.30.0-cp313-cp313t-musllinux_1_2_i686.whl", hash = "sha256:61046904275472a76c8c90c9ccee9013d70a6d0f73eecefd38c1ae7c39045a08", size = 590217, upload-time = "2025-11-30T20:23:20.885Z" },
    { url = "https://files.pythonhosted.org/packages/6d/61/21b8c41f68e60c8cc3b2e25644f0e3681926020f11d06ab0b78e3c6bbff1/rpds_py-0.30.0-cp313-cp313t-musllinux_1_2_x86_64.whl", hash = "sha256:4c5f36a861bc4b7da6516dbdf302c55313afa09b81931e8280361a4f6c9a2d27", size = 555806, upload-time = "2025-11-30T20:23:22.488Z" },
    { url = "https://files.pythonhosted.org/packages/f9/39/7e067bb06c31de48de3eb200f9fc7c58982a4d3db44b07e73963e10d3be9/rpds_py-0.30.0-cp313-cp313t-win32.whl", hash = "sha256:3d4a69de7a3e50ffc214ae16d79d8fbb0922972da0356dcf4d0fdca2878559c6", size = 211341, upload-time = "2025-11-30T20:23:24.449Z" },
    { url = "https://files.pythonhosted.org/packages/0a/4d/222ef0b46443cf4cf46764d9c630f3fe4abaa7245be9417e56e9f52b8f65/rpds_py-0.30.0-cp313-cp313t-win_amd64.whl", hash = "sha256:f14fc5df50a716f7ece6a80b6c78bb35ea2ca47c499e422aa4463455dd96d56d", size = 225768, upload-time = "2025-11-30T20:23:25.908Z" },
    { url = "https://files.pythonhosted.org/packages/86/81/dad16382ebbd3d0e0328776d8fd7ca94220e4fa0798d1dc5e7da48cb3201/rpds_py-0.30.0-cp314-cp314-macosx_10_12_x86_64.whl", hash = "sha256:68f19c879420aa08f61203801423f6cd5ac5f0ac4ac82a2368a9fcd6a9a075e0", size = 362099, upload-time = "2025-11-30T20:23:27.316Z" },
    { url = "https://files.pythonhosted.org/packages/2b/60/19f7884db5d5603edf3c6bce35408f45ad3e97e10007df0e17dd57af18f8/rpds_py-0.30.0-cp314-cp314-macosx_11_0_arm64.whl", hash = "sha256:ec7c4490c672c1a0389d319b3a9cfcd098dcdc4783991553c332a15acf7249be", size = 353192, upload-time = "2025-11-30T20:23:29.151Z" },
    { url = "https://files.pythonhosted.org/packages/bf/c4/76eb0e1e72d1a9c4703c69607cec123c29028bff28ce41588792417098ac/rpds_py-0.30.0-cp314-cp314-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:f251c812357a3fed308d684a5079ddfb9d933860fc6de89f2b7ab00da481e65f", size = 384080, upload-time = "2025-11-30T20:23:30.785Z" },
    { url = "https://files.pythonhosted.org/packages/72/87/87ea665e92f3298d1b26d78814721dc39ed8d2c74b86e83348d6b48a6f31/rpds_py-0.30.0-cp314-cp314-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:ac98b175585ecf4c0348fd7b29c3864bda53b805c773cbf7bfdaffc8070c976f", size = 394841, upload-time = "2025-11-30T20:23:32.209Z" },
    { url = "https://files.pythonhosted.org/packages/77/ad/7783a89ca0587c15dcbf139b4a8364a872a25f861bdb88ed99f9b0dec985/rpds_py-0.30.0-cp314-cp314-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:3e62880792319dbeb7eb866547f2e35973289e7d5696c6e295476448f5b63c87", size = 516670, upload-time = "2025-11-30T20:23:33.742Z" },
    { url = "https://files.pythonhosted.org/packages/5b/3c/2882bdac942bd2172f3da574eab16f309ae10a3925644e969536553cb4ee/rpds_py-0.30.0-cp314-cp314-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:4e7fc54e0900ab35d041b0601431b0a0eb495f0851a0639b6ef90f7741b39a18", size = 408005, upload-time = "2025-11-30T20:23:35.253Z" },
    { url = "https://files.pythonhosted.org/packages/ce/81/9a91c0111ce1758c92516a3e44776920b579d9a7c09b2b06b642d4de3f0f/rpds_py-0.30.0-cp314-cp314-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:47e77dc9822d3ad616c3d5759ea5631a75e5809d5a28707744ef79d7a1bcfcad", size = 382112, upload-time = "2025-11-30T20:23:36.842Z" },
    { url = "https://files.pythonhosted.org/packages/cf/8e/1da49d4a107027e5fbc64daeab96a0706361a2918da10cb41769244b805d/rpds_py-0.30.0-cp314-cp314-manylinux_2_31_riscv64.whl", hash = "sha256:b4dc1a6ff022ff85ecafef7979a2c6eb423430e05f1165d6688234e62ba99a07", size = 399049, upload-time = "2025-11-30T20:23:38.343Z" },
    { url = "https://files.pythonhosted.org/packages/df/5a/7ee239b1aa48a127570ec03becbb29c9d5a9eb092febbd1699d567cae859/rpds_py-0.30.0-cp314-cp314-manylinux_2_5_i686.manylinux1_i686.whl", hash = "sha256:4559c972db3a360808309e06a74628b95eaccbf961c335c8fe0d590cf587456f", size = 415661, upload-time = "2025-11-30T20:23:40.263Z" },
    { url = "https://files.pythonhosted.org/packages/70/ea/caa143cf6b772f823bc7929a45da1fa83569ee49b11d18d0ada7f5ee6fd6/rpds_py-0.30.0-cp314-cp314-musllinux_1_2_aarch64.whl", hash = "sha256:0ed177ed9bded28f8deb6ab40c183cd1192aa0de40c12f38be4d59cd33cb5c65", size = 565606, upload-time = "2025-11-30T20:23:42.186Z" },
    { url = "https://files.pythonhosted.org/packages/64/91/ac20ba2d69303f961ad8cf55bf7dbdb4763f627291ba3d0d7d67333cced9/rpds_py-0.30.0-cp314-cp314-musllinux_1_2_i686.whl", hash = "sha256:ad1fa8db769b76ea911cb4e10f049d80bf518c104f15b3edb2371cc65375c46f", size = 591126, upload-time = "2025-11-30T20:23:44.086Z" },
    { url = "https://files.pythonhosted.org/packages/21/20/7ff5f3c8b00c8a95f75985128c26ba44503fb35b8e0259d812766ea966c7/rpds_py-0.30.0-cp314-cp314-musllinux_1_2_x86_64.whl", hash = "sha256:46e83c697b1f1c72b50e5ee5adb4353eef7406fb3f2043d64c33f20ad1c2fc53", size = 553371, upload-time = "2025-11-30T20:23:46.004Z" },
    { url = "https://files.pythonhosted.org/packages/72/c7/81dadd7b27c8ee391c132a6b192111ca58d866577ce2d9b0ca157552cce0/rpds_py-0.30.0-cp314-cp314-win32.whl", hash = "sha256:ee454b2a007d57363c2dfd5b6ca4a5d7e2c518938f8ed3b706e37e5d470801ed", size = 215298, upload-time = "2025-11-30T20:23:47.696Z" },
    { url = "https://files.pythonhosted.org/packages/3e/d2/1aaac33287e8cfb07aab2e6b8ac1deca62f6f65411344f1433c55e6f3eb8/rpds_py-0.30.0-cp314-cp314-win_amd64.whl", hash = "sha256:95f0802447ac2d10bcc69f6dc28fe95fdf17940367b21d34e34c737870758950", size = 228604, upload-time = "2025-11-30T20:23:49.501Z" },
    { url = "https://files.pythonhosted.org/packages/e8/95/ab005315818cc519ad074cb7784dae60d939163108bd2b394e60dc7b5461/rpds_py-0.30.0-cp314-cp314-win_arm64.whl", hash = "sha256:613aa4771c99f03346e54c3f038e4cc574ac09a3ddfb0e8878487335e96dead6", size = 222391, upload-time = "2025-11-30T20:23:50.96Z" },
    { url = "https://files.pythonhosted.org/packages/9e/68/154fe0194d83b973cdedcdcc88947a2752411165930182ae41d983dcefa6/rpds_py-0.30.0-cp314-cp314t-macosx_10_12_x86_64.whl", hash = "sha256:7e6ecfcb62edfd632e56983964e6884851786443739dbfe3582947e87274f7cb", size = 364868, upload-time = "2025-11-30T20:23:52.494Z" },
    { url = "https://files.pythonhosted.org/packages/83/69/8bbc8b07ec854d92a8b75668c24d2abcb1719ebf890f5604c61c9369a16f/rpds_py-0.30.0-cp314-cp314t-macosx_11_0_arm64.whl", hash = "sha256:a1d0bc22a7cdc173fedebb73ef81e07faef93692b8c1ad3733b67e31e1b6e1b8", size = 353747, upload-time = "2025-11-30T20:23:54.036Z" },
    { url = "https://files.pythonhosted.org/packages/ab/00/ba2e50183dbd9abcce9497fa5149c62b4ff3e22d338a30d690f9af970561/rpds_py-0.30.0-cp314-cp314t-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:0d08f00679177226c4cb8c5265012eea897c8ca3b93f429e546600c971bcbae7", size = 383795, upload-time = "2025-11-30T20:23:55.556Z" },
    { url = "https://files.pythonhosted.org/packages/05/6f/86f0272b84926bcb0e4c972262f54223e8ecc556b3224d281e6598fc9268/rpds_py-0.30.0-cp314-cp314t-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:5965af57d5848192c13534f90f9dd16464f3c37aaf166cc1da1cae1fd5a34898", size = 393330, upload-time = "2025-11-30T20:23:57.033Z" },
    { url = "https://files.pythonhosted.org/packages/cb/e9/0e02bb2e6dc63d212641da45df2b0bf29699d01715913e0d0f017ee29438/rpds_py-0.30.0-cp314-cp314t-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:9a4e86e34e9ab6b667c27f3211ca48f73dba7cd3d90f8d5b11be56e5dbc3fb4e", size = 518194, upload-time = "2025-11-30T20:23:58.637Z" },
    { url = "https://files.pythonhosted.org/packages/ee/ca/be7bca14cf21513bdf9c0606aba17d1f389ea2b6987035eb4f62bd923f25/rpds_py-0.30.0-cp314-cp314t-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:e5d3e6b26f2c785d65cc25ef1e5267ccbe1b069c5c21b8cc724efee290554419", size = 408340, upload-time = "2025-11-30T20:24:00.2Z" },
    { url = "https://files.pythonhosted.org/packages/c2/c7/736e00ebf39ed81d75544c0da6ef7b0998f8201b369acf842f9a90dc8fce/rpds_py-0.30.0-cp314-cp314t-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:626a7433c34566535b6e56a1b39a7b17ba961e97ce3b80ec62e6f1312c025551", size = 383765, upload-time = "2025-11-30T20:24:01.759Z" },
    { url = "https://files.pythonhosted.org/packages/4a/3f/da50dfde9956aaf365c4adc9533b100008ed31aea635f2b8d7b627e25b49/rpds_py-0.30.0-cp314-cp314t-manylinux_2_31_riscv64.whl", hash = "sha256:acd7eb3f4471577b9b5a41baf02a978e8bdeb08b4b355273994f8b87032000a8", size = 396834, upload-time = "2025-11-30T20:24:03.687Z" },
    { url = "https://files.pythonhosted.org/packages/4e/00/34bcc2565b6020eab2623349efbdec810676ad571995911f1abdae62a3a0/rpds_py-0.30.0-cp314-cp314t-manylinux_2_5_i686.manylinux1_i686.whl", hash = "sha256:fe5fa731a1fa8a0a56b0977413f8cacac1768dad38d16b3a296712709476fbd5", size = 415470, upload-time = "2025-11-30T20:24:05.232Z" },
    { url = "https://files.pythonhosted.org/packages/8c/28/882e72b5b3e6f718d5453bd4d0d9cf8df36fddeb4ddbbab17869d5868616/rpds_py-0.30.0-cp314-cp314t-musllinux_1_2_aarch64.whl", hash = "sha256:74a3243a411126362712ee1524dfc90c650a503502f135d54d1b352bd01f2404", size = 565630, upload-time = "2025-11-30T20:24:06.878Z" },
    { url = "https://files.pythonhosted.org/packages/3b/97/04a65539c17692de5b85c6e293520fd01317fd878ea1995f0367d4532fb1/rpds_py-0.30.0-cp314-cp314t-musllinux_1_2_i686.whl", hash = "sha256:3e8eeb0544f2eb0d2581774be4c3410356eba189529a6b3e36bbbf9696175856", size = 591148, upload-time = "2025-11-30T20:24:08.445Z" },
    { url = "https://files.pythonhosted.org/packages/85/70/92482ccffb96f5441aab93e26c4d66489eb599efdcf96fad90c14bbfb976/rpds_py-0.30.0-cp314-cp314t-musllinux_1_2_x86_64.whl", hash = "sha256:dbd936cde57abfee19ab3213cf9c26be06d60750e60a8e4dd85d1ab12c8b1f40", size = 556030, upload-time = "2025-11-30T20:24:10.956Z" },
    { url = "https://files.pythonhosted.org/packages/20/53/7c7e784abfa500a2b6b583b147ee4bb5a2b3747a9166bab52fec4b5b5e7d/rpds_py-0.30.0-cp314-cp314t-win32.whl", hash = "sha256:dc824125c72246d924f7f796b4f63c1e9dc810c7d9e2355864b3c3a73d59ade0", size = 211570, upload-time = "2025-11-30T20:24:12.735Z" },
    { url = "https://files.pythonhosted.org/packages/d0/02/fa464cdfbe6b26e0600b62c528b72d8608f5cc49f96b8d6e38c95d60c676/rpds_py-0.30.0-cp314-cp314t-win_amd64.whl", hash = "sha256:27f4b0e92de5bfbc6f86e43959e6edd1425c33b5e69aab0984a72047f2bcf1e3", size = 226532, upload-time = "2025-11-30T20:24:14.634Z" },
    { url = "https://files.pythonhosted.org/packages/69/71/3f34339ee70521864411f8b6992e7ab13ac30d8e4e3309e07c7361767d91/rpds_py-0.30.0-pp311-pypy311_pp73-macosx_10_12_x86_64.whl", hash = "sha256:c2262bdba0ad4fc6fb5545660673925c2d2a5d9e2e0fb603aad545427be0fc58", size = 372292, upload-time = "2025-11-30T20:24:16.537Z" },
    { url = "https://files.pythonhosted.org/packages/57/09/f183df9b8f2d66720d2ef71075c59f7e1b336bec7ee4c48f0a2b06857653/rpds_py-0.30.0-pp311-pypy311_pp73-macosx_11_0_arm64.whl", hash = "sha256:ee6af14263f25eedc3bb918a3c04245106a42dfd4f5c2285ea6f997b1fc3f89a", size = 362128, upload-time = "2025-11-30T20:24:18.086Z" },
    { url = "https://files.pythonhosted.org/packages/7a/68/5c2594e937253457342e078f0cc1ded3dd7b2ad59afdbf2d354869110a02/rpds_py-0.30.0-pp311-pypy311_pp73-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:3adbb8179ce342d235c31ab8ec511e66c73faa27a47e076ccc92421add53e2bb", size = 391542, upload-time = "2025-11-30T20:24:20.092Z" },
    { url = "https://files.pythonhosted.org/packages/49/5c/31ef1afd70b4b4fbdb2800249f34c57c64beb687495b10aec0365f53dfc4/rpds_py-0.30.0-pp311-pypy311_pp73-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:250fa00e9543ac9b97ac258bd37367ff5256666122c2d0f2bc97577c60a1818c", size = 404004, upload-time = "2025-11-30T20:24:22.231Z" },
    { url = "https://files.pythonhosted.org/packages/e3/63/0cfbea38d05756f3440ce6534d51a491d26176ac045e2707adc99bb6e60a/rpds_py-0.30.0-pp311-pypy311_pp73-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:9854cf4f488b3d57b9aaeb105f06d78e5529d3145b1e4a41750167e8c213c6d3", size = 527063, upload-time = "2025-11-30T20:24:24.302Z" },
    { url = "https://files.pythonhosted.org/packages/42/e6/01e1f72a2456678b0f618fc9a1a13f882061690893c192fcad9f2926553a/rpds_py-0.30.0-pp311-pypy311_pp73-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:993914b8e560023bc0a8bf742c5f303551992dcb85e247b1e5c7f4a7d145bda5", size = 413099, upload-time = "2025-11-30T20:24:25.916Z" },
    { url = "https://files.pythonhosted.org/packages/b8/25/8df56677f209003dcbb180765520c544525e3ef21ea72279c98b9aa7c7fb/rpds_py-0.30.0-pp311-pypy311_pp73-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:58edca431fb9b29950807e301826586e5bbf24163677732429770a697ffe6738", size = 392177, upload-time = "2025-11-30T20:24:27.834Z" },
    { url = "https://files.pythonhosted.org/packages/4a/b4/0a771378c5f16f8115f796d1f437950158679bcd2a7c68cf251cfb00ed5b/rpds_py-0.30.0-pp311-pypy311_pp73-manylinux_2_31_riscv64.whl", hash = "sha256:dea5b552272a944763b34394d04577cf0f9bd013207bc32323b5a89a53cf9c2f", size = 406015, upload-time = "2025-11-30T20:24:29.457Z" },
    { url = "https://files.pythonhosted.org/packages/36/d8/456dbba0af75049dc6f63ff295a2f92766b9d521fa00de67a2bd6427d57a/rpds_py-0.30.0-pp311-pypy311_pp73-manylinux_2_5_i686.manylinux1_i686.whl", hash = "sha256:ba3af48635eb83d03f6c9735dfb21785303e73d22ad03d489e88adae6eab8877", size = 423736, upload-time = "2025-11-30T20:24:31.22Z" },
    { url = "https://files.pythonhosted.org/packages/13/64/b4d76f227d5c45a7e0b796c674fd81b0a6c4fbd48dc29271857d8219571c/rpds_py-0.30.0-pp311-pypy311_pp73-musllinux_1_2_aarch64.whl", hash = "sha256:dff13836529b921e22f15cb099751209a60009731a68519630a24d61f0b1b30a", size = 573981, upload-time = "2025-11-30T20:24:32.934Z" },
    { url = "https://files.pythonhosted.org/packages/20/91/092bacadeda3edf92bf743cc96a7be133e13a39cdbfd7b5082e7ab638406/rpds_py-0.30.0-pp311-pypy311_pp73-musllinux_1_2_i686.whl", hash = "sha256:1b151685b23929ab7beec71080a8889d4d6d9fa9a983d213f07121205d48e2c4", size = 599782, upload-time = "2025-11-30T20:24:35.169Z" },
    { url = "https://files.pythonhosted.org/packages/d1/b7/b95708304cd49b7b6f82fdd039f1748b66ec2b21d6a45180910802f1abf1/rpds_py-0.30.0-pp311-pypy311_pp73-musllinux_1_2_x86_64.whl", hash = "sha256:ac37f9f516c51e5753f27dfdef11a88330f04de2d564be3991384b2f3535d02e", size = 562191, upload-time = "2025-11-30T20:24:36.853Z" },
]

[[package]]
name = "rsa"
version = "4.9.1"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "pyasn1" },
]
sdist = { url = "https://files.pythonhosted.org/packages/da/8a/22b7beea3ee0d44b1916c0c1cb0ee3af23b700b6da9f04991899d0c555d4/rsa-4.9.1.tar.gz", hash = "sha256:e7bdbfdb5497da4c07dfd35530e1a902659db6ff241e39d9953cad06ebd0ae75", size = 29034, upload-time = "2025-04-16T09:51:18.218Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/64/8d/0133e4eb4beed9e425d9a98ed6e081a55d195481b7632472be1af08d2f6b/rsa-4.9.1-py3-none-any.whl", hash = "sha256:68635866661c6836b8d39430f97a996acbd61bfa49406748ea243539fe239762", size = 34696, upload-time = "2025-04-16T09:51:17.142Z" },
]

[[package]]
name = "shellingham"
version = "1.5.4"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/58/15/8b3609fd3830ef7b27b655beb4b4e9c62313a4e8da8c676e142cc210d58e/shellingham-1.5.4.tar.gz", hash = "sha256:8dbca0739d487e5bd35ab3ca4b36e11c4078f3a234bfce294b0a0291363404de", size = 10310, upload-time = "2023-10-24T04:13:40.426Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/e0/f9/0595336914c5619e5f28a1fb793285925a8cd4b432c9da0a987836c7f822/shellingham-1.5.4-py2.py3-none-any.whl", hash = "sha256:7ecfff8f2fd72616f7481040475a65b2bf8af90a56c89140852d1120324e8686", size = 9755, upload-time = "2023-10-24T04:13:38.866Z" },
]

[[package]]
name = "six"
version = "1.17.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/94/e7/b2c673351809dca68a0e064b6af791aa332cf192da575fd474ed7d6f16a2/six-1.17.0.tar.gz", hash = "sha256:ff70335d468e7eb6ec65b95b99d3a2836546063f63acc5171de367e834932a81", size = 34031, upload-time = "2024-12-04T17:35:28.174Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/b7/ce/149a00dd41f10bc29e5921b496af8b574d8413afcd5e30dfa0ed46c2cc5e/six-1.17.0-py2.py3-none-any.whl", hash = "sha256:4721f391ed90541fddacab5acf947aa0d3dc7d27b2e1e8eda2be8970586c3274", size = 11050, upload-time = "2024-12-04T17:35:26.475Z" },
]

[[package]]
name = "starlette"
version = "0.52.1"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "anyio" },
    { name = "typing-extensions", marker = "python_full_version < '3.13'" },
]
sdist = { url = "https://files.pythonhosted.org/packages/c4/68/79977123bb7be889ad680d79a40f339082c1978b5cfcf62c2d8d196873ac/starlette-0.52.1.tar.gz", hash = "sha256:834edd1b0a23167694292e94f597773bc3f89f362be6effee198165a35d62933", size = 2653702, upload-time = "2026-01-18T13:34:11.062Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/81/0d/13d1d239a25cbfb19e740db83143e95c772a1fe10202dda4b76792b114dd/starlette-0.52.1-py3-none-any.whl", hash = "sha256:0029d43eb3d273bc4f83a08720b4912ea4b071087a3b48db01b7c839f7954d74", size = 74272, upload-time = "2026-01-18T13:34:09.188Z" },
]

[[package]]
name = "sympy"
version = "1.14.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "mpmath" },
]
sdist = { url = "https://files.pythonhosted.org/packages/83/d3/803453b36afefb7c2bb238361cd4ae6125a569b4db67cd9e79846ba2d68c/sympy-1.14.0.tar.gz", hash = "sha256:d3d3fe8df1e5a0b42f0e7bdf50541697dbe7d23746e894990c030e2b05e72517", size = 7793921, upload-time = "2025-04-27T18:05:01.611Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/a2/09/77d55d46fd61b4a135c444fc97158ef34a095e5681d0a6c10b75bf356191/sympy-1.14.0-py3-none-any.whl", hash = "sha256:e091cc3e99d2141a0ba2847328f5479b05d94a6635cb96148ccb3f34671bd8f5", size = 6299353, upload-time = "2025-04-27T18:04:59.103Z" },
]

[[package]]
name = "tenacity"
version = "9.1.4"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/47/c6/ee486fd809e357697ee8a44d3d69222b344920433d3b6666ccd9b374630c/tenacity-9.1.4.tar.gz", hash = "sha256:adb31d4c263f2bd041081ab33b498309a57c77f9acf2db65aadf0898179cf93a", size = 49413, upload-time = "2026-02-07T10:45:33.841Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/d7/c1/eb8f9debc45d3b7918a32ab756658a0904732f75e555402972246b0b8e71/tenacity-9.1.4-py3-none-any.whl", hash = "sha256:6095a360c919085f28c6527de529e76a06ad89b23659fa881ae0649b867a9d55", size = 28926, upload-time = "2026-02-07T10:45:32.24Z" },
]

[[package]]
name = "tokenizers"
version = "0.22.2"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "huggingface-hub" },
]
sdist = { url = "https://files.pythonhosted.org/packages/73/6f/f80cfef4a312e1fb34baf7d85c72d4411afde10978d4657f8cdd811d3ccc/tokenizers-0.22.2.tar.gz", hash = "sha256:473b83b915e547aa366d1eee11806deaf419e17be16310ac0a14077f1e28f917", size = 372115, upload-time = "2026-01-05T10:45:15.988Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/92/97/5dbfabf04c7e348e655e907ed27913e03db0923abb5dfdd120d7b25630e1/tokenizers-0.22.2-cp39-abi3-macosx_10_12_x86_64.whl", hash = "sha256:544dd704ae7238755d790de45ba8da072e9af3eea688f698b137915ae959281c", size = 3100275, upload-time = "2026-01-05T10:41:02.158Z" },
    { url = "https://files.pythonhosted.org/packages/2e/47/174dca0502ef88b28f1c9e06b73ce33500eedfac7a7692108aec220464e7/tokenizers-0.22.2-cp39-abi3-macosx_11_0_arm64.whl", hash = "sha256:1e418a55456beedca4621dbab65a318981467a2b188e982a23e117f115ce5001", size = 2981472, upload-time = "2026-01-05T10:41:00.276Z" },
    { url = "https://files.pythonhosted.org/packages/d6/84/7990e799f1309a8b87af6b948f31edaa12a3ed22d11b352eaf4f4b2e5753/tokenizers-0.22.2-cp39-abi3-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:2249487018adec45d6e3554c71d46eb39fa8ea67156c640f7513eb26f318cec7", size = 3290736, upload-time = "2026-01-05T10:40:32.165Z" },
    { url = "https://files.pythonhosted.org/packages/78/59/09d0d9ba94dcd5f4f1368d4858d24546b4bdc0231c2354aa31d6199f0399/tokenizers-0.22.2-cp39-abi3-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:25b85325d0815e86e0bac263506dd114578953b7b53d7de09a6485e4a160a7dd", size = 3168835, upload-time = "2026-01-05T10:40:38.847Z" },
    { url = "https://files.pythonhosted.org/packages/47/50/b3ebb4243e7160bda8d34b731e54dd8ab8b133e50775872e7a434e524c28/tokenizers-0.22.2-cp39-abi3-manylinux_2_17_i686.manylinux2014_i686.whl", hash = "sha256:bfb88f22a209ff7b40a576d5324bf8286b519d7358663db21d6246fb17eea2d5", size = 3521673, upload-time = "2026-01-05T10:40:56.614Z" },
    { url = "https://files.pythonhosted.org/packages/e0/fa/89f4cb9e08df770b57adb96f8cbb7e22695a4cb6c2bd5f0c4f0ebcf33b66/tokenizers-0.22.2-cp39-abi3-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:1c774b1276f71e1ef716e5486f21e76333464f47bece56bbd554485982a9e03e", size = 3724818, upload-time = "2026-01-05T10:40:44.507Z" },
    { url = "https://files.pythonhosted.org/packages/64/04/ca2363f0bfbe3b3d36e95bf67e56a4c88c8e3362b658e616d1ac185d47f2/tokenizers-0.22.2-cp39-abi3-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:df6c4265b289083bf710dff49bc51ef252f9d5be33a45ee2bed151114a56207b", size = 3379195, upload-time = "2026-01-05T10:40:51.139Z" },
    { url = "https://files.pythonhosted.org/packages/2e/76/932be4b50ef6ccedf9d3c6639b056a967a86258c6d9200643f01269211ca/tokenizers-0.22.2-cp39-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:369cc9fc8cc10cb24143873a0d95438bb8ee257bb80c71989e3ee290e8d72c67", size = 3274982, upload-time = "2026-01-05T10:40:58.331Z" },
    { url = "https://files.pythonhosted.org/packages/1d/28/5f9f5a4cc211b69e89420980e483831bcc29dade307955cc9dc858a40f01/tokenizers-0.22.2-cp39-abi3-musllinux_1_2_aarch64.whl", hash = "sha256:29c30b83d8dcd061078b05ae0cb94d3c710555fbb44861139f9f83dcca3dc3e4", size = 9478245, upload-time = "2026-01-05T10:41:04.053Z" },
    { url = "https://files.pythonhosted.org/packages/6c/fb/66e2da4704d6aadebf8cb39f1d6d1957df667ab24cff2326b77cda0dcb85/tokenizers-0.22.2-cp39-abi3-musllinux_1_2_armv7l.whl", hash = "sha256:37ae80a28c1d3265bb1f22464c856bd23c02a05bb211e56d0c5301a435be6c1a", size = 9560069, upload-time = "2026-01-05T10:45:10.673Z" },
    { url = "https://files.pythonhosted.org/packages/16/04/fed398b05caa87ce9b1a1bb5166645e38196081b225059a6edaff6440fac/tokenizers-0.22.2-cp39-abi3-musllinux_1_2_i686.whl", hash = "sha256:791135ee325f2336f498590eb2f11dc5c295232f288e75c99a36c5dbce63088a", size = 9899263, upload-time = "2026-01-05T10:45:12.559Z" },
    { url = "https://files.pythonhosted.org/packages/05/a1/d62dfe7376beaaf1394917e0f8e93ee5f67fea8fcf4107501db35996586b/tokenizers-0.22.2-cp39-abi3-musllinux_1_2_x86_64.whl", hash = "sha256:38337540fbbddff8e999d59970f3c6f35a82de10053206a7562f1ea02d046fa5", size = 10033429, upload-time = "2026-01-05T10:45:14.333Z" },
    { url = "https://files.pythonhosted.org/packages/fd/18/a545c4ea42af3df6effd7d13d250ba77a0a86fb20393143bbb9a92e434d4/tokenizers-0.22.2-cp39-abi3-win32.whl", hash = "sha256:a6bf3f88c554a2b653af81f3204491c818ae2ac6fbc09e76ef4773351292bc92", size = 2502363, upload-time = "2026-01-05T10:45:20.593Z" },
    { url = "https://files.pythonhosted.org/packages/65/71/0670843133a43d43070abeb1949abfdef12a86d490bea9cd9e18e37c5ff7/tokenizers-0.22.2-cp39-abi3-win_amd64.whl", hash = "sha256:c9ea31edff2968b44a88f97d784c2f16dc0729b8b143ed004699ebca91f05c48", size = 2747786, upload-time = "2026-01-05T10:45:18.411Z" },
    { url = "https://files.pythonhosted.org/packages/72/f4/0de46cfa12cdcbcd464cc59fde36912af405696f687e53a091fb432f694c/tokenizers-0.22.2-cp39-abi3-win_arm64.whl", hash = "sha256:9ce725d22864a1e965217204946f830c37876eee3b2ba6fc6255e8e903d5fcbc", size = 2612133, upload-time = "2026-01-05T10:45:17.232Z" },
]

[[package]]
name = "tqdm"
version = "4.67.3"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "colorama", marker = "sys_platform == 'win32'" },
]
sdist = { url = "https://files.pythonhosted.org/packages/09/a9/6ba95a270c6f1fbcd8dac228323f2777d886cb206987444e4bce66338dd4/tqdm-4.67.3.tar.gz", hash = "sha256:7d825f03f89244ef73f1d4ce193cb1774a8179fd96f31d7e1dcde62092b960bb", size = 169598, upload-time = "2026-02-03T17:35:53.048Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/16/e1/3079a9ff9b8e11b846c6ac5c8b5bfb7ff225eee721825310c91b3b50304f/tqdm-4.67.3-py3-none-any.whl", hash = "sha256:ee1e4c0e59148062281c49d80b25b67771a127c85fc9676d3be5f243206826bf", size = 78374, upload-time = "2026-02-03T17:35:50.982Z" },
]

[[package]]
name = "typer"
version = "0.24.1"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "annotated-doc" },
    { name = "click" },
    { name = "rich" },
    { name = "shellingham" },
]
sdist = { url = "https://files.pythonhosted.org/packages/f5/24/cb09efec5cc954f7f9b930bf8279447d24618bb6758d4f6adf2574c41780/typer-0.24.1.tar.gz", hash = "sha256:e39b4732d65fbdcde189ae76cf7cd48aeae72919dea1fdfc16593be016256b45", size = 118613, upload-time = "2026-02-21T16:54:40.609Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/4a/91/48db081e7a63bb37284f9fbcefda7c44c277b18b0e13fbc36ea2335b71e6/typer-0.24.1-py3-none-any.whl", hash = "sha256:112c1f0ce578bfb4cab9ffdabc68f031416ebcc216536611ba21f04e9aa84c9e", size = 56085, upload-time = "2026-02-21T16:54:41.616Z" },
]

[[package]]
name = "typing-extensions"
version = "4.15.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/72/94/1a15dd82efb362ac84269196e94cf00f187f7ed21c242792a923cdb1c61f/typing_extensions-4.15.0.tar.gz", hash = "sha256:0cea48d173cc12fa28ecabc3b837ea3cf6f38c6d1136f85cbaaf598984861466", size = 109391, upload-time = "2025-08-25T13:49:26.313Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/18/67/36e9267722cc04a6b9f15c7f3441c2363321a3ea07da7ae0c0707beb2a9c/typing_extensions-4.15.0-py3-none-any.whl", hash = "sha256:f0fa19c6845758ab08074a0cfa8b7aecb71c999ca73d62883bc25cc018c4e548", size = 44614, upload-time = "2025-08-25T13:49:24.86Z" },
]

[[package]]
name = "typing-inspection"
version = "0.4.2"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "typing-extensions" },
]
sdist = { url = "https://files.pythonhosted.org/packages/55/e3/70399cb7dd41c10ac53367ae42139cf4b1ca5f36bb3dc6c9d33acdb43655/typing_inspection-0.4.2.tar.gz", hash = "sha256:ba561c48a67c5958007083d386c3295464928b01faa735ab8547c5692e87f464", size = 75949, upload-time = "2025-10-01T02:14:41.687Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/dc/9b/47798a6c91d8bdb567fe2698fe81e0c6b7cb7ef4d13da4114b41d239f65d/typing_inspection-0.4.2-py3-none-any.whl", hash = "sha256:4ed1cacbdc298c220f1bd249ed5287caa16f34d44ef4e9c3d0cbad5b521545e7", size = 14611, upload-time = "2025-10-01T02:14:40.154Z" },
]

[[package]]
name = "urllib3"
version = "2.6.3"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/c7/24/5f1b3bdffd70275f6661c76461e25f024d5a38a46f04aaca912426a2b1d3/urllib3-2.6.3.tar.gz", hash = "sha256:1b62b6884944a57dbe321509ab94fd4d3b307075e0c2eae991ac71ee15ad38ed", size = 435556, upload-time = "2026-01-07T16:24:43.925Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/39/08/aaaad47bc4e9dc8c725e68f9d04865dbcb2052843ff09c97b08904852d84/urllib3-2.6.3-py3-none-any.whl", hash = "sha256:bf272323e553dfb2e87d9bfd225ca7b0f467b919d7bbd355436d3fd37cb0acd4", size = 131584, upload-time = "2026-01-07T16:24:42.685Z" },
]

[[package]]
name = "uvicorn"
version = "0.41.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "click" },
    { name = "h11" },
]
sdist = { url = "https://files.pythonhosted.org/packages/32/ce/eeb58ae4ac36fe09e3842eb02e0eb676bf2c53ae062b98f1b2531673efdd/uvicorn-0.41.0.tar.gz", hash = "sha256:09d11cf7008da33113824ee5a1c6422d89fbc2ff476540d69a34c87fab8b571a", size = 82633, upload-time = "2026-02-16T23:07:24.1Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/83/e4/d04a086285c20886c0daad0e026f250869201013d18f81d9ff5eada73a88/uvicorn-0.41.0-py3-none-any.whl", hash = "sha256:29e35b1d2c36a04b9e180d4007ede3bcb32a85fbdfd6c6aeb3f26839de088187", size = 68783, upload-time = "2026-02-16T23:07:22.357Z" },
]

[package.optional-dependencies]
standard = [
    { name = "colorama", marker = "sys_platform == 'win32'" },
    { name = "httptools" },
    { name = "python-dotenv" },
    { name = "pyyaml" },
    { name = "uvloop", marker = "platform_python_implementation != 'PyPy' and sys_platform != 'cygwin' and sys_platform != 'win32'" },
    { name = "watchfiles" },
    { name = "websockets" },
]

[[package]]
name = "uvloop"
version = "0.22.1"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/06/f0/18d39dbd1971d6d62c4629cc7fa67f74821b0dc1f5a77af43719de7936a7/uvloop-0.22.1.tar.gz", hash = "sha256:6c84bae345b9147082b17371e3dd5d42775bddce91f885499017f4607fdaf39f", size = 2443250, upload-time = "2025-10-16T22:17:19.342Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/c7/d5/69900f7883235562f1f50d8184bb7dd84a2fb61e9ec63f3782546fdbd057/uvloop-0.22.1-cp311-cp311-macosx_10_9_universal2.whl", hash = "sha256:c60ebcd36f7b240b30788554b6f0782454826a0ed765d8430652621b5de674b9", size = 1352420, upload-time = "2025-10-16T22:16:21.187Z" },
    { url = "https://files.pythonhosted.org/packages/a8/73/c4e271b3bce59724e291465cc936c37758886a4868787da0278b3b56b905/uvloop-0.22.1-cp311-cp311-macosx_10_9_x86_64.whl", hash = "sha256:3b7f102bf3cb1995cfeaee9321105e8f5da76fdb104cdad8986f85461a1b7b77", size = 748677, upload-time = "2025-10-16T22:16:22.558Z" },
    { url = "https://files.pythonhosted.org/packages/86/94/9fb7fad2f824d25f8ecac0d70b94d0d48107ad5ece03769a9c543444f78a/uvloop-0.22.1-cp311-cp311-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:53c85520781d84a4b8b230e24a5af5b0778efdb39142b424990ff1ef7c48ba21", size = 3753819, upload-time = "2025-10-16T22:16:23.903Z" },
    { url = "https://files.pythonhosted.org/packages/74/4f/256aca690709e9b008b7108bc85fba619a2bc37c6d80743d18abad16ee09/uvloop-0.22.1-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:56a2d1fae65fd82197cb8c53c367310b3eabe1bbb9fb5a04d28e3e3520e4f702", size = 3804529, upload-time = "2025-10-16T22:16:25.246Z" },
    { url = "https://files.pythonhosted.org/packages/7f/74/03c05ae4737e871923d21a76fe28b6aad57f5c03b6e6bfcfa5ad616013e4/uvloop-0.22.1-cp311-cp311-musllinux_1_2_aarch64.whl", hash = "sha256:40631b049d5972c6755b06d0bfe8233b1bd9a8a6392d9d1c45c10b6f9e9b2733", size = 3621267, upload-time = "2025-10-16T22:16:26.819Z" },
    { url = "https://files.pythonhosted.org/packages/75/be/f8e590fe61d18b4a92070905497aec4c0e64ae1761498cad09023f3f4b3e/uvloop-0.22.1-cp311-cp311-musllinux_1_2_x86_64.whl", hash = "sha256:535cc37b3a04f6cd2c1ef65fa1d370c9a35b6695df735fcff5427323f2cd5473", size = 3723105, upload-time = "2025-10-16T22:16:28.252Z" },
    { url = "https://files.pythonhosted.org/packages/3d/ff/7f72e8170be527b4977b033239a83a68d5c881cc4775fca255c677f7ac5d/uvloop-0.22.1-cp312-cp312-macosx_10_13_universal2.whl", hash = "sha256:fe94b4564e865d968414598eea1a6de60adba0c040ba4ed05ac1300de402cd42", size = 1359936, upload-time = "2025-10-16T22:16:29.436Z" },
    { url = "https://files.pythonhosted.org/packages/c3/c6/e5d433f88fd54d81ef4be58b2b7b0cea13c442454a1db703a1eea0db1a59/uvloop-0.22.1-cp312-cp312-macosx_10_13_x86_64.whl", hash = "sha256:51eb9bd88391483410daad430813d982010f9c9c89512321f5b60e2cddbdddd6", size = 752769, upload-time = "2025-10-16T22:16:30.493Z" },
    { url = "https://files.pythonhosted.org/packages/24/68/a6ac446820273e71aa762fa21cdcc09861edd3536ff47c5cd3b7afb10eeb/uvloop-0.22.1-cp312-cp312-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:700e674a166ca5778255e0e1dc4e9d79ab2acc57b9171b79e65feba7184b3370", size = 4317413, upload-time = "2025-10-16T22:16:31.644Z" },
    { url = "https://files.pythonhosted.org/packages/5f/6f/e62b4dfc7ad6518e7eff2516f680d02a0f6eb62c0c212e152ca708a0085e/uvloop-0.22.1-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:7b5b1ac819a3f946d3b2ee07f09149578ae76066d70b44df3fa990add49a82e4", size = 4426307, upload-time = "2025-10-16T22:16:32.917Z" },
    { url = "https://files.pythonhosted.org/packages/90/60/97362554ac21e20e81bcef1150cb2a7e4ffdaf8ea1e5b2e8bf7a053caa18/uvloop-0.22.1-cp312-cp312-musllinux_1_2_aarch64.whl", hash = "sha256:e047cc068570bac9866237739607d1313b9253c3051ad84738cbb095be0537b2", size = 4131970, upload-time = "2025-10-16T22:16:34.015Z" },
    { url = "https://files.pythonhosted.org/packages/99/39/6b3f7d234ba3964c428a6e40006340f53ba37993f46ed6e111c6e9141d18/uvloop-0.22.1-cp312-cp312-musllinux_1_2_x86_64.whl", hash = "sha256:512fec6815e2dd45161054592441ef76c830eddaad55c8aa30952e6fe1ed07c0", size = 4296343, upload-time = "2025-10-16T22:16:35.149Z" },
    { url = "https://files.pythonhosted.org/packages/89/8c/182a2a593195bfd39842ea68ebc084e20c850806117213f5a299dfc513d9/uvloop-0.22.1-cp313-cp313-macosx_10_13_universal2.whl", hash = "sha256:561577354eb94200d75aca23fbde86ee11be36b00e52a4eaf8f50fb0c86b7705", size = 1358611, upload-time = "2025-10-16T22:16:36.833Z" },
    { url = "https://files.pythonhosted.org/packages/d2/14/e301ee96a6dc95224b6f1162cd3312f6d1217be3907b79173b06785f2fe7/uvloop-0.22.1-cp313-cp313-macosx_10_13_x86_64.whl", hash = "sha256:1cdf5192ab3e674ca26da2eada35b288d2fa49fdd0f357a19f0e7c4e7d5077c8", size = 751811, upload-time = "2025-10-16T22:16:38.275Z" },
    { url = "https://files.pythonhosted.org/packages/b7/02/654426ce265ac19e2980bfd9ea6590ca96a56f10c76e63801a2df01c0486/uvloop-0.22.1-cp313-cp313-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:6e2ea3d6190a2968f4a14a23019d3b16870dd2190cd69c8180f7c632d21de68d", size = 4288562, upload-time = "2025-10-16T22:16:39.375Z" },
    { url = "https://files.pythonhosted.org/packages/15/c0/0be24758891ef825f2065cd5db8741aaddabe3e248ee6acc5e8a80f04005/uvloop-0.22.1-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:0530a5fbad9c9e4ee3f2b33b148c6a64d47bbad8000ea63704fa8260f4cf728e", size = 4366890, upload-time = "2025-10-16T22:16:40.547Z" },
    { url = "https://files.pythonhosted.org/packages/d2/53/8369e5219a5855869bcee5f4d317f6da0e2c669aecf0ef7d371e3d084449/uvloop-0.22.1-cp313-cp313-musllinux_1_2_aarch64.whl", hash = "sha256:bc5ef13bbc10b5335792360623cc378d52d7e62c2de64660616478c32cd0598e", size = 4119472, upload-time = "2025-10-16T22:16:41.694Z" },
    { url = "https://files.pythonhosted.org/packages/f8/ba/d69adbe699b768f6b29a5eec7b47dd610bd17a69de51b251126a801369ea/uvloop-0.22.1-cp313-cp313-musllinux_1_2_x86_64.whl", hash = "sha256:1f38ec5e3f18c8a10ded09742f7fb8de0108796eb673f30ce7762ce1b8550cad", size = 4239051, upload-time = "2025-10-16T22:16:43.224Z" },
    { url = "https://files.pythonhosted.org/packages/90/cd/b62bdeaa429758aee8de8b00ac0dd26593a9de93d302bff3d21439e9791d/uvloop-0.22.1-cp314-cp314-macosx_10_13_universal2.whl", hash = "sha256:3879b88423ec7e97cd4eba2a443aa26ed4e59b45e6b76aabf13fe2f27023a142", size = 1362067, upload-time = "2025-10-16T22:16:44.503Z" },
    { url = "https://files.pythonhosted.org/packages/0d/f8/a132124dfda0777e489ca86732e85e69afcd1ff7686647000050ba670689/uvloop-0.22.1-cp314-cp314-macosx_10_13_x86_64.whl", hash = "sha256:4baa86acedf1d62115c1dc6ad1e17134476688f08c6efd8a2ab076e815665c74", size = 752423, upload-time = "2025-10-16T22:16:45.968Z" },
    { url = "https://files.pythonhosted.org/packages/a3/94/94af78c156f88da4b3a733773ad5ba0b164393e357cc4bd0ab2e2677a7d6/uvloop-0.22.1-cp314-cp314-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:297c27d8003520596236bdb2335e6b3f649480bd09e00d1e3a99144b691d2a35", size = 4272437, upload-time = "2025-10-16T22:16:47.451Z" },
    { url = "https://files.pythonhosted.org/packages/b5/35/60249e9fd07b32c665192cec7af29e06c7cd96fa1d08b84f012a56a0b38e/uvloop-0.22.1-cp314-cp314-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:c1955d5a1dd43198244d47664a5858082a3239766a839b2102a269aaff7a4e25", size = 4292101, upload-time = "2025-10-16T22:16:49.318Z" },
    { url = "https://files.pythonhosted.org/packages/02/62/67d382dfcb25d0a98ce73c11ed1a6fba5037a1a1d533dcbb7cab033a2636/uvloop-0.22.1-cp314-cp314-musllinux_1_2_aarch64.whl", hash = "sha256:b31dc2fccbd42adc73bc4e7cdbae4fc5086cf378979e53ca5d0301838c5682c6", size = 4114158, upload-time = "2025-10-16T22:16:50.517Z" },
    { url = "https://files.pythonhosted.org/packages/f0/7a/f1171b4a882a5d13c8b7576f348acfe6074d72eaf52cccef752f748d4a9f/uvloop-0.22.1-cp314-cp314-musllinux_1_2_x86_64.whl", hash = "sha256:93f617675b2d03af4e72a5333ef89450dfaa5321303ede6e67ba9c9d26878079", size = 4177360, upload-time = "2025-10-16T22:16:52.646Z" },
    { url = "https://files.pythonhosted.org/packages/79/7b/b01414f31546caf0919da80ad57cbfe24c56b151d12af68cee1b04922ca8/uvloop-0.22.1-cp314-cp314t-macosx_10_13_universal2.whl", hash = "sha256:37554f70528f60cad66945b885eb01f1bb514f132d92b6eeed1c90fd54ed6289", size = 1454790, upload-time = "2025-10-16T22:16:54.355Z" },
    { url = "https://files.pythonhosted.org/packages/d4/31/0bb232318dd838cad3fa8fb0c68c8b40e1145b32025581975e18b11fab40/uvloop-0.22.1-cp314-cp314t-macosx_10_13_x86_64.whl", hash = "sha256:b76324e2dc033a0b2f435f33eb88ff9913c156ef78e153fb210e03c13da746b3", size = 796783, upload-time = "2025-10-16T22:16:55.906Z" },
    { url = "https://files.pythonhosted.org/packages/42/38/c9b09f3271a7a723a5de69f8e237ab8e7803183131bc57c890db0b6bb872/uvloop-0.22.1-cp314-cp314t-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:badb4d8e58ee08dad957002027830d5c3b06aea446a6a3744483c2b3b745345c", size = 4647548, upload-time = "2025-10-16T22:16:57.008Z" },
    { url = "https://files.pythonhosted.org/packages/c1/37/945b4ca0ac27e3dc4952642d4c900edd030b3da6c9634875af6e13ae80e5/uvloop-0.22.1-cp314-cp314t-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:b91328c72635f6f9e0282e4a57da7470c7350ab1c9f48546c0f2866205349d21", size = 4467065, upload-time = "2025-10-16T22:16:58.206Z" },
    { url = "https://files.pythonhosted.org/packages/97/cc/48d232f33d60e2e2e0b42f4e73455b146b76ebe216487e862700457fbf3c/uvloop-0.22.1-cp314-cp314t-musllinux_1_2_aarch64.whl", hash = "sha256:daf620c2995d193449393d6c62131b3fbd40a63bf7b307a1527856ace637fe88", size = 4328384, upload-time = "2025-10-16T22:16:59.36Z" },
    { url = "https://files.pythonhosted.org/packages/e4/16/c1fd27e9549f3c4baf1dc9c20c456cd2f822dbf8de9f463824b0c0357e06/uvloop-0.22.1-cp314-cp314t-musllinux_1_2_x86_64.whl", hash = "sha256:6cde23eeda1a25c75b2e07d39970f3374105d5eafbaab2a4482be82f272d5a5e", size = 4296730, upload-time = "2025-10-16T22:17:00.744Z" },
]

[[package]]
name = "watchfiles"
version = "1.1.1"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "anyio" },
]
sdist = { url = "https://files.pythonhosted.org/packages/c2/c9/8869df9b2a2d6c59d79220a4db37679e74f807c559ffe5265e08b227a210/watchfiles-1.1.1.tar.gz", hash = "sha256:a173cb5c16c4f40ab19cecf48a534c409f7ea983ab8fed0741304a1c0a31b3f2", size = 94440, upload-time = "2025-10-14T15:06:21.08Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/1f/f8/2c5f479fb531ce2f0564eda479faecf253d886b1ab3630a39b7bf7362d46/watchfiles-1.1.1-cp311-cp311-macosx_10_12_x86_64.whl", hash = "sha256:f57b396167a2565a4e8b5e56a5a1c537571733992b226f4f1197d79e94cf0ae5", size = 406529, upload-time = "2025-10-14T15:04:32.899Z" },
    { url = "https://files.pythonhosted.org/packages/fe/cd/f515660b1f32f65df671ddf6f85bfaca621aee177712874dc30a97397977/watchfiles-1.1.1-cp311-cp311-macosx_11_0_arm64.whl", hash = "sha256:421e29339983e1bebc281fab40d812742268ad057db4aee8c4d2bce0af43b741", size = 394384, upload-time = "2025-10-14T15:04:33.761Z" },
    { url = "https://files.pythonhosted.org/packages/7b/c3/28b7dc99733eab43fca2d10f55c86e03bd6ab11ca31b802abac26b23d161/watchfiles-1.1.1-cp311-cp311-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:6e43d39a741e972bab5d8100b5cdacf69db64e34eb19b6e9af162bccf63c5cc6", size = 448789, upload-time = "2025-10-14T15:04:34.679Z" },
    { url = "https://files.pythonhosted.org/packages/4a/24/33e71113b320030011c8e4316ccca04194bf0cbbaeee207f00cbc7d6b9f5/watchfiles-1.1.1-cp311-cp311-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:f537afb3276d12814082a2e9b242bdcf416c2e8fd9f799a737990a1dbe906e5b", size = 460521, upload-time = "2025-10-14T15:04:35.963Z" },
    { url = "https://files.pythonhosted.org/packages/f4/c3/3c9a55f255aa57b91579ae9e98c88704955fa9dac3e5614fb378291155df/watchfiles-1.1.1-cp311-cp311-manylinux_2_17_i686.manylinux2014_i686.whl", hash = "sha256:b2cd9e04277e756a2e2d2543d65d1e2166d6fd4c9b183f8808634fda23f17b14", size = 488722, upload-time = "2025-10-14T15:04:37.091Z" },
    { url = "https://files.pythonhosted.org/packages/49/36/506447b73eb46c120169dc1717fe2eff07c234bb3232a7200b5f5bd816e9/watchfiles-1.1.1-cp311-cp311-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:5f3f58818dc0b07f7d9aa7fe9eb1037aecb9700e63e1f6acfed13e9fef648f5d", size = 596088, upload-time = "2025-10-14T15:04:38.39Z" },
    { url = "https://files.pythonhosted.org/packages/82/ab/5f39e752a9838ec4d52e9b87c1e80f1ee3ccdbe92e183c15b6577ab9de16/watchfiles-1.1.1-cp311-cp311-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:9bb9f66367023ae783551042d31b1d7fd422e8289eedd91f26754a66f44d5cff", size = 472923, upload-time = "2025-10-14T15:04:39.666Z" },
    { url = "https://files.pythonhosted.org/packages/af/b9/a419292f05e302dea372fa7e6fda5178a92998411f8581b9830d28fb9edb/watchfiles-1.1.1-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:aebfd0861a83e6c3d1110b78ad54704486555246e542be3e2bb94195eabb2606", size = 456080, upload-time = "2025-10-14T15:04:40.643Z" },
    { url = "https://files.pythonhosted.org/packages/b0/c3/d5932fd62bde1a30c36e10c409dc5d54506726f08cb3e1d8d0ba5e2bc8db/watchfiles-1.1.1-cp311-cp311-musllinux_1_1_aarch64.whl", hash = "sha256:5fac835b4ab3c6487b5dbad78c4b3724e26bcc468e886f8ba8cc4306f68f6701", size = 629432, upload-time = "2025-10-14T15:04:41.789Z" },
    { url = "https://files.pythonhosted.org/packages/f7/77/16bddd9779fafb795f1a94319dc965209c5641db5bf1edbbccace6d1b3c0/watchfiles-1.1.1-cp311-cp311-musllinux_1_1_x86_64.whl", hash = "sha256:399600947b170270e80134ac854e21b3ccdefa11a9529a3decc1327088180f10", size = 623046, upload-time = "2025-10-14T15:04:42.718Z" },
    { url = "https://files.pythonhosted.org/packages/46/ef/f2ecb9a0f342b4bfad13a2787155c6ee7ce792140eac63a34676a2feeef2/watchfiles-1.1.1-cp311-cp311-win32.whl", hash = "sha256:de6da501c883f58ad50db3a32ad397b09ad29865b5f26f64c24d3e3281685849", size = 271473, upload-time = "2025-10-14T15:04:43.624Z" },
    { url = "https://files.pythonhosted.org/packages/94/bc/f42d71125f19731ea435c3948cad148d31a64fccde3867e5ba4edee901f9/watchfiles-1.1.1-cp311-cp311-win_amd64.whl", hash = "sha256:35c53bd62a0b885bf653ebf6b700d1bf05debb78ad9292cf2a942b23513dc4c4", size = 287598, upload-time = "2025-10-14T15:04:44.516Z" },
    { url = "https://files.pythonhosted.org/packages/57/c9/a30f897351f95bbbfb6abcadafbaca711ce1162f4db95fc908c98a9165f3/watchfiles-1.1.1-cp311-cp311-win_arm64.whl", hash = "sha256:57ca5281a8b5e27593cb7d82c2ac927ad88a96ed406aa446f6344e4328208e9e", size = 277210, upload-time = "2025-10-14T15:04:45.883Z" },
    { url = "https://files.pythonhosted.org/packages/74/d5/f039e7e3c639d9b1d09b07ea412a6806d38123f0508e5f9b48a87b0a76cc/watchfiles-1.1.1-cp312-cp312-macosx_10_12_x86_64.whl", hash = "sha256:8c89f9f2f740a6b7dcc753140dd5e1ab9215966f7a3530d0c0705c83b401bd7d", size = 404745, upload-time = "2025-10-14T15:04:46.731Z" },
    { url = "https://files.pythonhosted.org/packages/a5/96/a881a13aa1349827490dab2d363c8039527060cfcc2c92cc6d13d1b1049e/watchfiles-1.1.1-cp312-cp312-macosx_11_0_arm64.whl", hash = "sha256:bd404be08018c37350f0d6e34676bd1e2889990117a2b90070b3007f172d0610", size = 391769, upload-time = "2025-10-14T15:04:48.003Z" },
    { url = "https://files.pythonhosted.org/packages/4b/5b/d3b460364aeb8da471c1989238ea0e56bec24b6042a68046adf3d9ddb01c/watchfiles-1.1.1-cp312-cp312-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:8526e8f916bb5b9a0a777c8317c23ce65de259422bba5b31325a6fa6029d33af", size = 449374, upload-time = "2025-10-14T15:04:49.179Z" },
    { url = "https://files.pythonhosted.org/packages/b9/44/5769cb62d4ed055cb17417c0a109a92f007114a4e07f30812a73a4efdb11/watchfiles-1.1.1-cp312-cp312-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:2edc3553362b1c38d9f06242416a5d8e9fe235c204a4072e988ce2e5bb1f69f6", size = 459485, upload-time = "2025-10-14T15:04:50.155Z" },
    { url = "https://files.pythonhosted.org/packages/19/0c/286b6301ded2eccd4ffd0041a1b726afda999926cf720aab63adb68a1e36/watchfiles-1.1.1-cp312-cp312-manylinux_2_17_i686.manylinux2014_i686.whl", hash = "sha256:30f7da3fb3f2844259cba4720c3fc7138eb0f7b659c38f3bfa65084c7fc7abce", size = 488813, upload-time = "2025-10-14T15:04:51.059Z" },
    { url = "https://files.pythonhosted.org/packages/c7/2b/8530ed41112dd4a22f4dcfdb5ccf6a1baad1ff6eed8dc5a5f09e7e8c41c7/watchfiles-1.1.1-cp312-cp312-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:f8979280bdafff686ba5e4d8f97840f929a87ed9cdf133cbbd42f7766774d2aa", size = 594816, upload-time = "2025-10-14T15:04:52.031Z" },
    { url = "https://files.pythonhosted.org/packages/ce/d2/f5f9fb49489f184f18470d4f99f4e862a4b3e9ac2865688eb2099e3d837a/watchfiles-1.1.1-cp312-cp312-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:dcc5c24523771db3a294c77d94771abcfcb82a0e0ee8efd910c37c59ec1b31bb", size = 475186, upload-time = "2025-10-14T15:04:53.064Z" },
    { url = "https://files.pythonhosted.org/packages/cf/68/5707da262a119fb06fbe214d82dd1fe4a6f4af32d2d14de368d0349eb52a/watchfiles-1.1.1-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:1db5d7ae38ff20153d542460752ff397fcf5c96090c1230803713cf3147a6803", size = 456812, upload-time = "2025-10-14T15:04:55.174Z" },
    { url = "https://files.pythonhosted.org/packages/66/ab/3cbb8756323e8f9b6f9acb9ef4ec26d42b2109bce830cc1f3468df20511d/watchfiles-1.1.1-cp312-cp312-musllinux_1_1_aarch64.whl", hash = "sha256:28475ddbde92df1874b6c5c8aaeb24ad5be47a11f87cde5a28ef3835932e3e94", size = 630196, upload-time = "2025-10-14T15:04:56.22Z" },
    { url = "https://files.pythonhosted.org/packages/78/46/7152ec29b8335f80167928944a94955015a345440f524d2dfe63fc2f437b/watchfiles-1.1.1-cp312-cp312-musllinux_1_1_x86_64.whl", hash = "sha256:36193ed342f5b9842edd3532729a2ad55c4160ffcfa3700e0d54be496b70dd43", size = 622657, upload-time = "2025-10-14T15:04:57.521Z" },
    { url = "https://files.pythonhosted.org/packages/0a/bf/95895e78dd75efe9a7f31733607f384b42eb5feb54bd2eb6ed57cc2e94f4/watchfiles-1.1.1-cp312-cp312-win32.whl", hash = "sha256:859e43a1951717cc8de7f4c77674a6d389b106361585951d9e69572823f311d9", size = 272042, upload-time = "2025-10-14T15:04:59.046Z" },
    { url = "https://files.pythonhosted.org/packages/87/0a/90eb755f568de2688cb220171c4191df932232c20946966c27a59c400850/watchfiles-1.1.1-cp312-cp312-win_amd64.whl", hash = "sha256:91d4c9a823a8c987cce8fa2690923b069966dabb196dd8d137ea2cede885fde9", size = 288410, upload-time = "2025-10-14T15:05:00.081Z" },
    { url = "https://files.pythonhosted.org/packages/36/76/f322701530586922fbd6723c4f91ace21364924822a8772c549483abed13/watchfiles-1.1.1-cp312-cp312-win_arm64.whl", hash = "sha256:a625815d4a2bdca61953dbba5a39d60164451ef34c88d751f6c368c3ea73d404", size = 278209, upload-time = "2025-10-14T15:05:01.168Z" },
    { url = "https://files.pythonhosted.org/packages/bb/f4/f750b29225fe77139f7ae5de89d4949f5a99f934c65a1f1c0b248f26f747/watchfiles-1.1.1-cp313-cp313-macosx_10_12_x86_64.whl", hash = "sha256:130e4876309e8686a5e37dba7d5e9bc77e6ed908266996ca26572437a5271e18", size = 404321, upload-time = "2025-10-14T15:05:02.063Z" },
    { url = "https://files.pythonhosted.org/packages/2b/f9/f07a295cde762644aa4c4bb0f88921d2d141af45e735b965fb2e87858328/watchfiles-1.1.1-cp313-cp313-macosx_11_0_arm64.whl", hash = "sha256:5f3bde70f157f84ece3765b42b4a52c6ac1a50334903c6eaf765362f6ccca88a", size = 391783, upload-time = "2025-10-14T15:05:03.052Z" },
    { url = "https://files.pythonhosted.org/packages/bc/11/fc2502457e0bea39a5c958d86d2cb69e407a4d00b85735ca724bfa6e0d1a/watchfiles-1.1.1-cp313-cp313-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:14e0b1fe858430fc0251737ef3824c54027bedb8c37c38114488b8e131cf8219", size = 449279, upload-time = "2025-10-14T15:05:04.004Z" },
    { url = "https://files.pythonhosted.org/packages/e3/1f/d66bc15ea0b728df3ed96a539c777acfcad0eb78555ad9efcaa1274688f0/watchfiles-1.1.1-cp313-cp313-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:f27db948078f3823a6bb3b465180db8ebecf26dd5dae6f6180bd87383b6b4428", size = 459405, upload-time = "2025-10-14T15:05:04.942Z" },
    { url = "https://files.pythonhosted.org/packages/be/90/9f4a65c0aec3ccf032703e6db02d89a157462fbb2cf20dd415128251cac0/watchfiles-1.1.1-cp313-cp313-manylinux_2_17_i686.manylinux2014_i686.whl", hash = "sha256:059098c3a429f62fc98e8ec62b982230ef2c8df68c79e826e37b895bc359a9c0", size = 488976, upload-time = "2025-10-14T15:05:05.905Z" },
    { url = "https://files.pythonhosted.org/packages/37/57/ee347af605d867f712be7029bb94c8c071732a4b44792e3176fa3c612d39/watchfiles-1.1.1-cp313-cp313-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:bfb5862016acc9b869bb57284e6cb35fdf8e22fe59f7548858e2f971d045f150", size = 595506, upload-time = "2025-10-14T15:05:06.906Z" },
    { url = "https://files.pythonhosted.org/packages/a8/78/cc5ab0b86c122047f75e8fc471c67a04dee395daf847d3e59381996c8707/watchfiles-1.1.1-cp313-cp313-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:319b27255aacd9923b8a276bb14d21a5f7ff82564c744235fc5eae58d95422ae", size = 474936, upload-time = "2025-10-14T15:05:07.906Z" },
    { url = "https://files.pythonhosted.org/packages/62/da/def65b170a3815af7bd40a3e7010bf6ab53089ef1b75d05dd5385b87cf08/watchfiles-1.1.1-cp313-cp313-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:c755367e51db90e75b19454b680903631d41f9e3607fbd941d296a020c2d752d", size = 456147, upload-time = "2025-10-14T15:05:09.138Z" },
    { url = "https://files.pythonhosted.org/packages/57/99/da6573ba71166e82d288d4df0839128004c67d2778d3b566c138695f5c0b/watchfiles-1.1.1-cp313-cp313-musllinux_1_1_aarch64.whl", hash = "sha256:c22c776292a23bfc7237a98f791b9ad3144b02116ff10d820829ce62dff46d0b", size = 630007, upload-time = "2025-10-14T15:05:10.117Z" },
    { url = "https://files.pythonhosted.org/packages/a8/51/7439c4dd39511368849eb1e53279cd3454b4a4dbace80bab88feeb83c6b5/watchfiles-1.1.1-cp313-cp313-musllinux_1_1_x86_64.whl", hash = "sha256:3a476189be23c3686bc2f4321dd501cb329c0a0469e77b7b534ee10129ae6374", size = 622280, upload-time = "2025-10-14T15:05:11.146Z" },
    { url = "https://files.pythonhosted.org/packages/95/9c/8ed97d4bba5db6fdcdb2b298d3898f2dd5c20f6b73aee04eabe56c59677e/watchfiles-1.1.1-cp313-cp313-win32.whl", hash = "sha256:bf0a91bfb5574a2f7fc223cf95eeea79abfefa404bf1ea5e339c0c1560ae99a0", size = 272056, upload-time = "2025-10-14T15:05:12.156Z" },
    { url = "https://files.pythonhosted.org/packages/1f/f3/c14e28429f744a260d8ceae18bf58c1d5fa56b50d006a7a9f80e1882cb0d/watchfiles-1.1.1-cp313-cp313-win_amd64.whl", hash = "sha256:52e06553899e11e8074503c8e716d574adeeb7e68913115c4b3653c53f9bae42", size = 288162, upload-time = "2025-10-14T15:05:13.208Z" },
    { url = "https://files.pythonhosted.org/packages/dc/61/fe0e56c40d5cd29523e398d31153218718c5786b5e636d9ae8ae79453d27/watchfiles-1.1.1-cp313-cp313-win_arm64.whl", hash = "sha256:ac3cc5759570cd02662b15fbcd9d917f7ecd47efe0d6b40474eafd246f91ea18", size = 277909, upload-time = "2025-10-14T15:05:14.49Z" },
    { url = "https://files.pythonhosted.org/packages/79/42/e0a7d749626f1e28c7108a99fb9bf524b501bbbeb9b261ceecde644d5a07/watchfiles-1.1.1-cp313-cp313t-macosx_10_12_x86_64.whl", hash = "sha256:563b116874a9a7ce6f96f87cd0b94f7faf92d08d0021e837796f0a14318ef8da", size = 403389, upload-time = "2025-10-14T15:05:15.777Z" },
    { url = "https://files.pythonhosted.org/packages/15/49/08732f90ce0fbbc13913f9f215c689cfc9ced345fb1bcd8829a50007cc8d/watchfiles-1.1.1-cp313-cp313t-macosx_11_0_arm64.whl", hash = "sha256:3ad9fe1dae4ab4212d8c91e80b832425e24f421703b5a42ef2e4a1e215aff051", size = 389964, upload-time = "2025-10-14T15:05:16.85Z" },
    { url = "https://files.pythonhosted.org/packages/27/0d/7c315d4bd5f2538910491a0393c56bf70d333d51bc5b34bee8e68e8cea19/watchfiles-1.1.1-cp313-cp313t-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:ce70f96a46b894b36eba678f153f052967a0d06d5b5a19b336ab0dbbd029f73e", size = 448114, upload-time = "2025-10-14T15:05:17.876Z" },
    { url = "https://files.pythonhosted.org/packages/c3/24/9e096de47a4d11bc4df41e9d1e61776393eac4cb6eb11b3e23315b78b2cc/watchfiles-1.1.1-cp313-cp313t-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:cb467c999c2eff23a6417e58d75e5828716f42ed8289fe6b77a7e5a91036ca70", size = 460264, upload-time = "2025-10-14T15:05:18.962Z" },
    { url = "https://files.pythonhosted.org/packages/cc/0f/e8dea6375f1d3ba5fcb0b3583e2b493e77379834c74fd5a22d66d85d6540/watchfiles-1.1.1-cp313-cp313t-manylinux_2_17_i686.manylinux2014_i686.whl", hash = "sha256:836398932192dae4146c8f6f737d74baeac8b70ce14831a239bdb1ca882fc261", size = 487877, upload-time = "2025-10-14T15:05:20.094Z" },
    { url = "https://files.pythonhosted.org/packages/ac/5b/df24cfc6424a12deb41503b64d42fbea6b8cb357ec62ca84a5a3476f654a/watchfiles-1.1.1-cp313-cp313t-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:743185e7372b7bc7c389e1badcc606931a827112fbbd37f14c537320fca08620", size = 595176, upload-time = "2025-10-14T15:05:21.134Z" },
    { url = "https://files.pythonhosted.org/packages/8f/b5/853b6757f7347de4e9b37e8cc3289283fb983cba1ab4d2d7144694871d9c/watchfiles-1.1.1-cp313-cp313t-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:afaeff7696e0ad9f02cbb8f56365ff4686ab205fcf9c4c5b6fdfaaa16549dd04", size = 473577, upload-time = "2025-10-14T15:05:22.306Z" },
    { url = "https://files.pythonhosted.org/packages/e1/f7/0a4467be0a56e80447c8529c9fce5b38eab4f513cb3d9bf82e7392a5696b/watchfiles-1.1.1-cp313-cp313t-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:3f7eb7da0eb23aa2ba036d4f616d46906013a68caf61b7fdbe42fc8b25132e77", size = 455425, upload-time = "2025-10-14T15:05:23.348Z" },
    { url = "https://files.pythonhosted.org/packages/8e/e0/82583485ea00137ddf69bc84a2db88bd92ab4a6e3c405e5fb878ead8d0e7/watchfiles-1.1.1-cp313-cp313t-musllinux_1_1_aarch64.whl", hash = "sha256:831a62658609f0e5c64178211c942ace999517f5770fe9436be4c2faeba0c0ef", size = 628826, upload-time = "2025-10-14T15:05:24.398Z" },
    { url = "https://files.pythonhosted.org/packages/28/9a/a785356fccf9fae84c0cc90570f11702ae9571036fb25932f1242c82191c/watchfiles-1.1.1-cp313-cp313t-musllinux_1_1_x86_64.whl", hash = "sha256:f9a2ae5c91cecc9edd47e041a930490c31c3afb1f5e6d71de3dc671bfaca02bf", size = 622208, upload-time = "2025-10-14T15:05:25.45Z" },
    { url = "https://files.pythonhosted.org/packages/c3/f4/0872229324ef69b2c3edec35e84bd57a1289e7d3fe74588048ed8947a323/watchfiles-1.1.1-cp314-cp314-macosx_10_12_x86_64.whl", hash = "sha256:d1715143123baeeaeadec0528bb7441103979a1d5f6fd0e1f915383fea7ea6d5", size = 404315, upload-time = "2025-10-14T15:05:26.501Z" },
    { url = "https://files.pythonhosted.org/packages/7b/22/16d5331eaed1cb107b873f6ae1b69e9ced582fcf0c59a50cd84f403b1c32/watchfiles-1.1.1-cp314-cp314-macosx_11_0_arm64.whl", hash = "sha256:39574d6370c4579d7f5d0ad940ce5b20db0e4117444e39b6d8f99db5676c52fd", size = 390869, upload-time = "2025-10-14T15:05:27.649Z" },
    { url = "https://files.pythonhosted.org/packages/b2/7e/5643bfff5acb6539b18483128fdc0ef2cccc94a5b8fbda130c823e8ed636/watchfiles-1.1.1-cp314-cp314-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:7365b92c2e69ee952902e8f70f3ba6360d0d596d9299d55d7d386df84b6941fb", size = 449919, upload-time = "2025-10-14T15:05:28.701Z" },
    { url = "https://files.pythonhosted.org/packages/51/2e/c410993ba5025a9f9357c376f48976ef0e1b1aefb73b97a5ae01a5972755/watchfiles-1.1.1-cp314-cp314-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:bfff9740c69c0e4ed32416f013f3c45e2ae42ccedd1167ef2d805c000b6c71a5", size = 460845, upload-time = "2025-10-14T15:05:30.064Z" },
    { url = "https://files.pythonhosted.org/packages/8e/a4/2df3b404469122e8680f0fcd06079317e48db58a2da2950fb45020947734/watchfiles-1.1.1-cp314-cp314-manylinux_2_17_i686.manylinux2014_i686.whl", hash = "sha256:b27cf2eb1dda37b2089e3907d8ea92922b673c0c427886d4edc6b94d8dfe5db3", size = 489027, upload-time = "2025-10-14T15:05:31.064Z" },
    { url = "https://files.pythonhosted.org/packages/ea/84/4587ba5b1f267167ee715b7f66e6382cca6938e0a4b870adad93e44747e6/watchfiles-1.1.1-cp314-cp314-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:526e86aced14a65a5b0ec50827c745597c782ff46b571dbfe46192ab9e0b3c33", size = 595615, upload-time = "2025-10-14T15:05:32.074Z" },
    { url = "https://files.pythonhosted.org/packages/6a/0f/c6988c91d06e93cd0bb3d4a808bcf32375ca1904609835c3031799e3ecae/watchfiles-1.1.1-cp314-cp314-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:04e78dd0b6352db95507fd8cb46f39d185cf8c74e4cf1e4fbad1d3df96faf510", size = 474836, upload-time = "2025-10-14T15:05:33.209Z" },
    { url = "https://files.pythonhosted.org/packages/b4/36/ded8aebea91919485b7bbabbd14f5f359326cb5ec218cd67074d1e426d74/watchfiles-1.1.1-cp314-cp314-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:5c85794a4cfa094714fb9c08d4a218375b2b95b8ed1666e8677c349906246c05", size = 455099, upload-time = "2025-10-14T15:05:34.189Z" },
    { url = "https://files.pythonhosted.org/packages/98/e0/8c9bdba88af756a2fce230dd365fab2baf927ba42cd47521ee7498fd5211/watchfiles-1.1.1-cp314-cp314-musllinux_1_1_aarch64.whl", hash = "sha256:74d5012b7630714b66be7b7b7a78855ef7ad58e8650c73afc4c076a1f480a8d6", size = 630626, upload-time = "2025-10-14T15:05:35.216Z" },
    { url = "https://files.pythonhosted.org/packages/2a/84/a95db05354bf2d19e438520d92a8ca475e578c647f78f53197f5a2f17aaf/watchfiles-1.1.1-cp314-cp314-musllinux_1_1_x86_64.whl", hash = "sha256:8fbe85cb3201c7d380d3d0b90e63d520f15d6afe217165d7f98c9c649654db81", size = 622519, upload-time = "2025-10-14T15:05:36.259Z" },
    { url = "https://files.pythonhosted.org/packages/1d/ce/d8acdc8de545de995c339be67711e474c77d643555a9bb74a9334252bd55/watchfiles-1.1.1-cp314-cp314-win32.whl", hash = "sha256:3fa0b59c92278b5a7800d3ee7733da9d096d4aabcfabb9a928918bd276ef9b9b", size = 272078, upload-time = "2025-10-14T15:05:37.63Z" },
    { url = "https://files.pythonhosted.org/packages/c4/c9/a74487f72d0451524be827e8edec251da0cc1fcf111646a511ae752e1a3d/watchfiles-1.1.1-cp314-cp314-win_amd64.whl", hash = "sha256:c2047d0b6cea13b3316bdbafbfa0c4228ae593d995030fda39089d36e64fc03a", size = 287664, upload-time = "2025-10-14T15:05:38.95Z" },
    { url = "https://files.pythonhosted.org/packages/df/b8/8ac000702cdd496cdce998c6f4ee0ca1f15977bba51bdf07d872ebdfc34c/watchfiles-1.1.1-cp314-cp314-win_arm64.whl", hash = "sha256:842178b126593addc05acf6fce960d28bc5fae7afbaa2c6c1b3a7b9460e5be02", size = 277154, upload-time = "2025-10-14T15:05:39.954Z" },
    { url = "https://files.pythonhosted.org/packages/47/a8/e3af2184707c29f0f14b1963c0aace6529f9d1b8582d5b99f31bbf42f59e/watchfiles-1.1.1-cp314-cp314t-macosx_10_12_x86_64.whl", hash = "sha256:88863fbbc1a7312972f1c511f202eb30866370ebb8493aef2812b9ff28156a21", size = 403820, upload-time = "2025-10-14T15:05:40.932Z" },
    { url = "https://files.pythonhosted.org/packages/c0/ec/e47e307c2f4bd75f9f9e8afbe3876679b18e1bcec449beca132a1c5ffb2d/watchfiles-1.1.1-cp314-cp314t-macosx_11_0_arm64.whl", hash = "sha256:55c7475190662e202c08c6c0f4d9e345a29367438cf8e8037f3155e10a88d5a5", size = 390510, upload-time = "2025-10-14T15:05:41.945Z" },
    { url = "https://files.pythonhosted.org/packages/d5/a0/ad235642118090f66e7b2f18fd5c42082418404a79205cdfca50b6309c13/watchfiles-1.1.1-cp314-cp314t-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:3f53fa183d53a1d7a8852277c92b967ae99c2d4dcee2bfacff8868e6e30b15f7", size = 448408, upload-time = "2025-10-14T15:05:43.385Z" },
    { url = "https://files.pythonhosted.org/packages/df/85/97fa10fd5ff3332ae17e7e40e20784e419e28521549780869f1413742e9d/watchfiles-1.1.1-cp314-cp314t-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:6aae418a8b323732fa89721d86f39ec8f092fc2af67f4217a2b07fd3e93c6101", size = 458968, upload-time = "2025-10-14T15:05:44.404Z" },
    { url = "https://files.pythonhosted.org/packages/47/c2/9059c2e8966ea5ce678166617a7f75ecba6164375f3b288e50a40dc6d489/watchfiles-1.1.1-cp314-cp314t-manylinux_2_17_i686.manylinux2014_i686.whl", hash = "sha256:f096076119da54a6080e8920cbdaac3dbee667eb91dcc5e5b78840b87415bd44", size = 488096, upload-time = "2025-10-14T15:05:45.398Z" },
    { url = "https://files.pythonhosted.org/packages/94/44/d90a9ec8ac309bc26db808a13e7bfc0e4e78b6fc051078a554e132e80160/watchfiles-1.1.1-cp314-cp314t-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:00485f441d183717038ed2e887a7c868154f216877653121068107b227a2f64c", size = 596040, upload-time = "2025-10-14T15:05:46.502Z" },
    { url = "https://files.pythonhosted.org/packages/95/68/4e3479b20ca305cfc561db3ed207a8a1c745ee32bf24f2026a129d0ddb6e/watchfiles-1.1.1-cp314-cp314t-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:a55f3e9e493158d7bfdb60a1165035f1cf7d320914e7b7ea83fe22c6023b58fc", size = 473847, upload-time = "2025-10-14T15:05:47.484Z" },
    { url = "https://files.pythonhosted.org/packages/4f/55/2af26693fd15165c4ff7857e38330e1b61ab8c37d15dc79118cdba115b7a/watchfiles-1.1.1-cp314-cp314t-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:8c91ed27800188c2ae96d16e3149f199d62f86c7af5f5f4d2c61a3ed8cd3666c", size = 455072, upload-time = "2025-10-14T15:05:48.928Z" },
    { url = "https://files.pythonhosted.org/packages/66/1d/d0d200b10c9311ec25d2273f8aad8c3ef7cc7ea11808022501811208a750/watchfiles-1.1.1-cp314-cp314t-musllinux_1_1_aarch64.whl", hash = "sha256:311ff15a0bae3714ffb603e6ba6dbfba4065ab60865d15a6ec544133bdb21099", size = 629104, upload-time = "2025-10-14T15:05:49.908Z" },
    { url = "https://files.pythonhosted.org/packages/e3/bd/fa9bb053192491b3867ba07d2343d9f2252e00811567d30ae8d0f78136fe/watchfiles-1.1.1-cp314-cp314t-musllinux_1_1_x86_64.whl", hash = "sha256:a916a2932da8f8ab582f242c065f5c81bed3462849ca79ee357dd9551b0e9b01", size = 622112, upload-time = "2025-10-14T15:05:50.941Z" },
    { url = "https://files.pythonhosted.org/packages/d3/8e/e500f8b0b77be4ff753ac94dc06b33d8f0d839377fee1b78e8c8d8f031bf/watchfiles-1.1.1-pp311-pypy311_pp73-macosx_10_12_x86_64.whl", hash = "sha256:db476ab59b6765134de1d4fe96a1a9c96ddf091683599be0f26147ea1b2e4b88", size = 408250, upload-time = "2025-10-14T15:06:10.264Z" },
    { url = "https://files.pythonhosted.org/packages/bd/95/615e72cd27b85b61eec764a5ca51bd94d40b5adea5ff47567d9ebc4d275a/watchfiles-1.1.1-pp311-pypy311_pp73-macosx_11_0_arm64.whl", hash = "sha256:89eef07eee5e9d1fda06e38822ad167a044153457e6fd997f8a858ab7564a336", size = 396117, upload-time = "2025-10-14T15:06:11.28Z" },
    { url = "https://files.pythonhosted.org/packages/c9/81/e7fe958ce8a7fb5c73cc9fb07f5aeaf755e6aa72498c57d760af760c91f8/watchfiles-1.1.1-pp311-pypy311_pp73-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:ce19e06cbda693e9e7686358af9cd6f5d61312ab8b00488bc36f5aabbaf77e24", size = 450493, upload-time = "2025-10-14T15:06:12.321Z" },
    { url = "https://files.pythonhosted.org/packages/6e/d4/ed38dd3b1767193de971e694aa544356e63353c33a85d948166b5ff58b9e/watchfiles-1.1.1-pp311-pypy311_pp73-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:3e6f39af2eab0118338902798b5aa6664f46ff66bc0280de76fca67a7f262a49", size = 457546, upload-time = "2025-10-14T15:06:13.372Z" },
]

[[package]]
name = "websocket-client"
version = "1.9.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/2c/41/aa4bf9664e4cda14c3b39865b12251e8e7d239f4cd0e3cc1b6c2ccde25c1/websocket_client-1.9.0.tar.gz", hash = "sha256:9e813624b6eb619999a97dc7958469217c3176312b3a16a4bd1bc7e08a46ec98", size = 70576, upload-time = "2025-10-07T21:16:36.495Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/34/db/b10e48aa8fff7407e67470363eac595018441cf32d5e1001567a7aeba5d2/websocket_client-1.9.0-py3-none-any.whl", hash = "sha256:af248a825037ef591efbf6ed20cc5faa03d3b47b9e5a2230a529eeee1c1fc3ef", size = 82616, upload-time = "2025-10-07T21:16:34.951Z" },
]

[[package]]
name = "websockets"
version = "16.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/04/24/4b2031d72e840ce4c1ccb255f693b15c334757fc50023e4db9537080b8c4/websockets-16.0.tar.gz", hash = "sha256:5f6261a5e56e8d5c42a4497b364ea24d94d9563e8fbd44e78ac40879c60179b5", size = 179346, upload-time = "2026-01-10T09:23:47.181Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/f2/db/de907251b4ff46ae804ad0409809504153b3f30984daf82a1d84a9875830/websockets-16.0-cp311-cp311-macosx_10_9_universal2.whl", hash = "sha256:31a52addea25187bde0797a97d6fc3d2f92b6f72a9370792d65a6e84615ac8a8", size = 177340, upload-time = "2026-01-10T09:22:34.539Z" },
    { url = "https://files.pythonhosted.org/packages/f3/fa/abe89019d8d8815c8781e90d697dec52523fb8ebe308bf11664e8de1877e/websockets-16.0-cp311-cp311-macosx_10_9_x86_64.whl", hash = "sha256:417b28978cdccab24f46400586d128366313e8a96312e4b9362a4af504f3bbad", size = 175022, upload-time = "2026-01-10T09:22:36.332Z" },
    { url = "https://files.pythonhosted.org/packages/58/5d/88ea17ed1ded2079358b40d31d48abe90a73c9e5819dbcde1606e991e2ad/websockets-16.0-cp311-cp311-macosx_11_0_arm64.whl", hash = "sha256:af80d74d4edfa3cb9ed973a0a5ba2b2a549371f8a741e0800cb07becdd20f23d", size = 175319, upload-time = "2026-01-10T09:22:37.602Z" },
    { url = "https://files.pythonhosted.org/packages/d2/ae/0ee92b33087a33632f37a635e11e1d99d429d3d323329675a6022312aac2/websockets-16.0-cp311-cp311-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:08d7af67b64d29823fed316505a89b86705f2b7981c07848fb5e3ea3020c1abe", size = 184631, upload-time = "2026-01-10T09:22:38.789Z" },
    { url = "https://files.pythonhosted.org/packages/c8/c5/27178df583b6c5b31b29f526ba2da5e2f864ecc79c99dae630a85d68c304/websockets-16.0-cp311-cp311-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:7be95cfb0a4dae143eaed2bcba8ac23f4892d8971311f1b06f3c6b78952ee70b", size = 185870, upload-time = "2026-01-10T09:22:39.893Z" },
    { url = "https://files.pythonhosted.org/packages/87/05/536652aa84ddc1c018dbb7e2c4cbcd0db884580bf8e95aece7593fde526f/websockets-16.0-cp311-cp311-musllinux_1_2_aarch64.whl", hash = "sha256:d6297ce39ce5c2e6feb13c1a996a2ded3b6832155fcfc920265c76f24c7cceb5", size = 185361, upload-time = "2026-01-10T09:22:41.016Z" },
    { url = "https://files.pythonhosted.org/packages/6d/e2/d5332c90da12b1e01f06fb1b85c50cfc489783076547415bf9f0a659ec19/websockets-16.0-cp311-cp311-musllinux_1_2_x86_64.whl", hash = "sha256:1c1b30e4f497b0b354057f3467f56244c603a79c0d1dafce1d16c283c25f6e64", size = 184615, upload-time = "2026-01-10T09:22:42.442Z" },
    { url = "https://files.pythonhosted.org/packages/77/fb/d3f9576691cae9253b51555f841bc6600bf0a983a461c79500ace5a5b364/websockets-16.0-cp311-cp311-win32.whl", hash = "sha256:5f451484aeb5cafee1ccf789b1b66f535409d038c56966d6101740c1614b86c6", size = 178246, upload-time = "2026-01-10T09:22:43.654Z" },
    { url = "https://files.pythonhosted.org/packages/54/67/eaff76b3dbaf18dcddabc3b8c1dba50b483761cccff67793897945b37408/websockets-16.0-cp311-cp311-win_amd64.whl", hash = "sha256:8d7f0659570eefb578dacde98e24fb60af35350193e4f56e11190787bee77dac", size = 178684, upload-time = "2026-01-10T09:22:44.941Z" },
    { url = "https://files.pythonhosted.org/packages/84/7b/bac442e6b96c9d25092695578dda82403c77936104b5682307bd4deb1ad4/websockets-16.0-cp312-cp312-macosx_10_13_universal2.whl", hash = "sha256:71c989cbf3254fbd5e84d3bff31e4da39c43f884e64f2551d14bb3c186230f00", size = 177365, upload-time = "2026-01-10T09:22:46.787Z" },
    { url = "https://files.pythonhosted.org/packages/b0/fe/136ccece61bd690d9c1f715baaeefd953bb2360134de73519d5df19d29ca/websockets-16.0-cp312-cp312-macosx_10_13_x86_64.whl", hash = "sha256:8b6e209ffee39ff1b6d0fa7bfef6de950c60dfb91b8fcead17da4ee539121a79", size = 175038, upload-time = "2026-01-10T09:22:47.999Z" },
    { url = "https://files.pythonhosted.org/packages/40/1e/9771421ac2286eaab95b8575b0cb701ae3663abf8b5e1f64f1fd90d0a673/websockets-16.0-cp312-cp312-macosx_11_0_arm64.whl", hash = "sha256:86890e837d61574c92a97496d590968b23c2ef0aeb8a9bc9421d174cd378ae39", size = 175328, upload-time = "2026-01-10T09:22:49.809Z" },
    { url = "https://files.pythonhosted.org/packages/18/29/71729b4671f21e1eaa5d6573031ab810ad2936c8175f03f97f3ff164c802/websockets-16.0-cp312-cp312-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:9b5aca38b67492ef518a8ab76851862488a478602229112c4b0d58d63a7a4d5c", size = 184915, upload-time = "2026-01-10T09:22:51.071Z" },
    { url = "https://files.pythonhosted.org/packages/97/bb/21c36b7dbbafc85d2d480cd65df02a1dc93bf76d97147605a8e27ff9409d/websockets-16.0-cp312-cp312-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:e0334872c0a37b606418ac52f6ab9cfd17317ac26365f7f65e203e2d0d0d359f", size = 186152, upload-time = "2026-01-10T09:22:52.224Z" },
    { url = "https://files.pythonhosted.org/packages/4a/34/9bf8df0c0cf88fa7bfe36678dc7b02970c9a7d5e065a3099292db87b1be2/websockets-16.0-cp312-cp312-musllinux_1_2_aarch64.whl", hash = "sha256:a0b31e0b424cc6b5a04b8838bbaec1688834b2383256688cf47eb97412531da1", size = 185583, upload-time = "2026-01-10T09:22:53.443Z" },
    { url = "https://files.pythonhosted.org/packages/47/88/4dd516068e1a3d6ab3c7c183288404cd424a9a02d585efbac226cb61ff2d/websockets-16.0-cp312-cp312-musllinux_1_2_x86_64.whl", hash = "sha256:485c49116d0af10ac698623c513c1cc01c9446c058a4e61e3bf6c19dff7335a2", size = 184880, upload-time = "2026-01-10T09:22:55.033Z" },
    { url = "https://files.pythonhosted.org/packages/91/d6/7d4553ad4bf1c0421e1ebd4b18de5d9098383b5caa1d937b63df8d04b565/websockets-16.0-cp312-cp312-win32.whl", hash = "sha256:eaded469f5e5b7294e2bdca0ab06becb6756ea86894a47806456089298813c89", size = 178261, upload-time = "2026-01-10T09:22:56.251Z" },
    { url = "https://files.pythonhosted.org/packages/c3/f0/f3a17365441ed1c27f850a80b2bc680a0fa9505d733fe152fdf5e98c1c0b/websockets-16.0-cp312-cp312-win_amd64.whl", hash = "sha256:5569417dc80977fc8c2d43a86f78e0a5a22fee17565d78621b6bb264a115d4ea", size = 178693, upload-time = "2026-01-10T09:22:57.478Z" },
    { url = "https://files.pythonhosted.org/packages/cc/9c/baa8456050d1c1b08dd0ec7346026668cbc6f145ab4e314d707bb845bf0d/websockets-16.0-cp313-cp313-macosx_10_13_universal2.whl", hash = "sha256:878b336ac47938b474c8f982ac2f7266a540adc3fa4ad74ae96fea9823a02cc9", size = 177364, upload-time = "2026-01-10T09:22:59.333Z" },
    { url = "https://files.pythonhosted.org/packages/7e/0c/8811fc53e9bcff68fe7de2bcbe75116a8d959ac699a3200f4847a8925210/websockets-16.0-cp313-cp313-macosx_10_13_x86_64.whl", hash = "sha256:52a0fec0e6c8d9a784c2c78276a48a2bdf099e4ccc2a4cad53b27718dbfd0230", size = 175039, upload-time = "2026-01-10T09:23:01.171Z" },
    { url = "https://files.pythonhosted.org/packages/aa/82/39a5f910cb99ec0b59e482971238c845af9220d3ab9fa76dd9162cda9d62/websockets-16.0-cp313-cp313-macosx_11_0_arm64.whl", hash = "sha256:e6578ed5b6981005df1860a56e3617f14a6c307e6a71b4fff8c48fdc50f3ed2c", size = 175323, upload-time = "2026-01-10T09:23:02.341Z" },
    { url = "https://files.pythonhosted.org/packages/bd/28/0a25ee5342eb5d5f297d992a77e56892ecb65e7854c7898fb7d35e9b33bd/websockets-16.0-cp313-cp313-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:95724e638f0f9c350bb1c2b0a7ad0e83d9cc0c9259f3ea94e40d7b02a2179ae5", size = 184975, upload-time = "2026-01-10T09:23:03.756Z" },
    { url = "https://files.pythonhosted.org/packages/f9/66/27ea52741752f5107c2e41fda05e8395a682a1e11c4e592a809a90c6a506/websockets-16.0-cp313-cp313-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:c0204dc62a89dc9d50d682412c10b3542d748260d743500a85c13cd1ee4bde82", size = 186203, upload-time = "2026-01-10T09:23:05.01Z" },
    { url = "https://files.pythonhosted.org/packages/37/e5/8e32857371406a757816a2b471939d51c463509be73fa538216ea52b792a/websockets-16.0-cp313-cp313-musllinux_1_2_aarch64.whl", hash = "sha256:52ac480f44d32970d66763115edea932f1c5b1312de36df06d6b219f6741eed8", size = 185653, upload-time = "2026-01-10T09:23:06.301Z" },
    { url = "https://files.pythonhosted.org/packages/9b/67/f926bac29882894669368dc73f4da900fcdf47955d0a0185d60103df5737/websockets-16.0-cp313-cp313-musllinux_1_2_x86_64.whl", hash = "sha256:6e5a82b677f8f6f59e8dfc34ec06ca6b5b48bc4fcda346acd093694cc2c24d8f", size = 184920, upload-time = "2026-01-10T09:23:07.492Z" },
    { url = "https://files.pythonhosted.org/packages/3c/a1/3d6ccdcd125b0a42a311bcd15a7f705d688f73b2a22d8cf1c0875d35d34a/websockets-16.0-cp313-cp313-win32.whl", hash = "sha256:abf050a199613f64c886ea10f38b47770a65154dc37181bfaff70c160f45315a", size = 178255, upload-time = "2026-01-10T09:23:09.245Z" },
    { url = "https://files.pythonhosted.org/packages/6b/ae/90366304d7c2ce80f9b826096a9e9048b4bb760e44d3b873bb272cba696b/websockets-16.0-cp313-cp313-win_amd64.whl", hash = "sha256:3425ac5cf448801335d6fdc7ae1eb22072055417a96cc6b31b3861f455fbc156", size = 178689, upload-time = "2026-01-10T09:23:10.483Z" },
    { url = "https://files.pythonhosted.org/packages/f3/1d/e88022630271f5bd349ed82417136281931e558d628dd52c4d8621b4a0b2/websockets-16.0-cp314-cp314-macosx_10_15_universal2.whl", hash = "sha256:8cc451a50f2aee53042ac52d2d053d08bf89bcb31ae799cb4487587661c038a0", size = 177406, upload-time = "2026-01-10T09:23:12.178Z" },
    { url = "https://files.pythonhosted.org/packages/f2/78/e63be1bf0724eeb4616efb1ae1c9044f7c3953b7957799abb5915bffd38e/websockets-16.0-cp314-cp314-macosx_10_15_x86_64.whl", hash = "sha256:daa3b6ff70a9241cf6c7fc9e949d41232d9d7d26fd3522b1ad2b4d62487e9904", size = 175085, upload-time = "2026-01-10T09:23:13.511Z" },
    { url = "https://files.pythonhosted.org/packages/bb/f4/d3c9220d818ee955ae390cf319a7c7a467beceb24f05ee7aaaa2414345ba/websockets-16.0-cp314-cp314-macosx_11_0_arm64.whl", hash = "sha256:fd3cb4adb94a2a6e2b7c0d8d05cb94e6f1c81a0cf9dc2694fb65c7e8d94c42e4", size = 175328, upload-time = "2026-01-10T09:23:14.727Z" },
    { url = "https://files.pythonhosted.org/packages/63/bc/d3e208028de777087e6fb2b122051a6ff7bbcca0d6df9d9c2bf1dd869ae9/websockets-16.0-cp314-cp314-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:781caf5e8eee67f663126490c2f96f40906594cb86b408a703630f95550a8c3e", size = 185044, upload-time = "2026-01-10T09:23:15.939Z" },
    { url = "https://files.pythonhosted.org/packages/ad/6e/9a0927ac24bd33a0a9af834d89e0abc7cfd8e13bed17a86407a66773cc0e/websockets-16.0-cp314-cp314-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:caab51a72c51973ca21fa8a18bd8165e1a0183f1ac7066a182ff27107b71e1a4", size = 186279, upload-time = "2026-01-10T09:23:17.148Z" },
    { url = "https://files.pythonhosted.org/packages/b9/ca/bf1c68440d7a868180e11be653c85959502efd3a709323230314fda6e0b3/websockets-16.0-cp314-cp314-musllinux_1_2_aarch64.whl", hash = "sha256:19c4dc84098e523fd63711e563077d39e90ec6702aff4b5d9e344a60cb3c0cb1", size = 185711, upload-time = "2026-01-10T09:23:18.372Z" },
    { url = "https://files.pythonhosted.org/packages/c4/f8/fdc34643a989561f217bb477cbc47a3a07212cbda91c0e4389c43c296ebf/websockets-16.0-cp314-cp314-musllinux_1_2_x86_64.whl", hash = "sha256:a5e18a238a2b2249c9a9235466b90e96ae4795672598a58772dd806edc7ac6d3", size = 184982, upload-time = "2026-01-10T09:23:19.652Z" },
    { url = "https://files.pythonhosted.org/packages/dd/d1/574fa27e233764dbac9c52730d63fcf2823b16f0856b3329fc6268d6ae4f/websockets-16.0-cp314-cp314-win32.whl", hash = "sha256:a069d734c4a043182729edd3e9f247c3b2a4035415a9172fd0f1b71658a320a8", size = 177915, upload-time = "2026-01-10T09:23:21.458Z" },
    { url = "https://files.pythonhosted.org/packages/8a/f1/ae6b937bf3126b5134ce1f482365fde31a357c784ac51852978768b5eff4/websockets-16.0-cp314-cp314-win_amd64.whl", hash = "sha256:c0ee0e63f23914732c6d7e0cce24915c48f3f1512ec1d079ed01fc629dab269d", size = 178381, upload-time = "2026-01-10T09:23:22.715Z" },
    { url = "https://files.pythonhosted.org/packages/06/9b/f791d1db48403e1f0a27577a6beb37afae94254a8c6f08be4a23e4930bc0/websockets-16.0-cp314-cp314t-macosx_10_15_universal2.whl", hash = "sha256:a35539cacc3febb22b8f4d4a99cc79b104226a756aa7400adc722e83b0d03244", size = 177737, upload-time = "2026-01-10T09:23:24.523Z" },
    { url = "https://files.pythonhosted.org/packages/bd/40/53ad02341fa33b3ce489023f635367a4ac98b73570102ad2cdd770dacc9a/websockets-16.0-cp314-cp314t-macosx_10_15_x86_64.whl", hash = "sha256:b784ca5de850f4ce93ec85d3269d24d4c82f22b7212023c974c401d4980ebc5e", size = 175268, upload-time = "2026-01-10T09:23:25.781Z" },
    { url = "https://files.pythonhosted.org/packages/74/9b/6158d4e459b984f949dcbbb0c5d270154c7618e11c01029b9bbd1bb4c4f9/websockets-16.0-cp314-cp314t-macosx_11_0_arm64.whl", hash = "sha256:569d01a4e7fba956c5ae4fc988f0d4e187900f5497ce46339c996dbf24f17641", size = 175486, upload-time = "2026-01-10T09:23:27.033Z" },
    { url = "https://files.pythonhosted.org/packages/e5/2d/7583b30208b639c8090206f95073646c2c9ffd66f44df967981a64f849ad/websockets-16.0-cp314-cp314t-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:50f23cdd8343b984957e4077839841146f67a3d31ab0d00e6b824e74c5b2f6e8", size = 185331, upload-time = "2026-01-10T09:23:28.259Z" },
    { url = "https://files.pythonhosted.org/packages/45/b0/cce3784eb519b7b5ad680d14b9673a31ab8dcb7aad8b64d81709d2430aa8/websockets-16.0-cp314-cp314t-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:152284a83a00c59b759697b7f9e9cddf4e3c7861dd0d964b472b70f78f89e80e", size = 186501, upload-time = "2026-01-10T09:23:29.449Z" },
    { url = "https://files.pythonhosted.org/packages/19/60/b8ebe4c7e89fb5f6cdf080623c9d92789a53636950f7abacfc33fe2b3135/websockets-16.0-cp314-cp314t-musllinux_1_2_aarch64.whl", hash = "sha256:bc59589ab64b0022385f429b94697348a6a234e8ce22544e3681b2e9331b5944", size = 186062, upload-time = "2026-01-10T09:23:31.368Z" },
    { url = "https://files.pythonhosted.org/packages/88/a8/a080593f89b0138b6cba1b28f8df5673b5506f72879322288b031337c0b8/websockets-16.0-cp314-cp314t-musllinux_1_2_x86_64.whl", hash = "sha256:32da954ffa2814258030e5a57bc73a3635463238e797c7375dc8091327434206", size = 185356, upload-time = "2026-01-10T09:23:32.627Z" },
    { url = "https://files.pythonhosted.org/packages/c2/b6/b9afed2afadddaf5ebb2afa801abf4b0868f42f8539bfe4b071b5266c9fe/websockets-16.0-cp314-cp314t-win32.whl", hash = "sha256:5a4b4cc550cb665dd8a47f868c8d04c8230f857363ad3c9caf7a0c3bf8c61ca6", size = 178085, upload-time = "2026-01-10T09:23:33.816Z" },
    { url = "https://files.pythonhosted.org/packages/9f/3e/28135a24e384493fa804216b79a6a6759a38cc4ff59118787b9fb693df93/websockets-16.0-cp314-cp314t-win_amd64.whl", hash = "sha256:b14dc141ed6d2dde437cddb216004bcac6a1df0935d79656387bd41632ba0bbd", size = 178531, upload-time = "2026-01-10T09:23:35.016Z" },
    { url = "https://files.pythonhosted.org/packages/72/07/c98a68571dcf256e74f1f816b8cc5eae6eb2d3d5cfa44d37f801619d9166/websockets-16.0-pp311-pypy311_pp73-macosx_10_15_x86_64.whl", hash = "sha256:349f83cd6c9a415428ee1005cadb5c2c56f4389bc06a9af16103c3bc3dcc8b7d", size = 174947, upload-time = "2026-01-10T09:23:36.166Z" },
    { url = "https://files.pythonhosted.org/packages/7e/52/93e166a81e0305b33fe416338be92ae863563fe7bce446b0f687b9df5aea/websockets-16.0-pp311-pypy311_pp73-macosx_11_0_arm64.whl", hash = "sha256:4a1aba3340a8dca8db6eb5a7986157f52eb9e436b74813764241981ca4888f03", size = 175260, upload-time = "2026-01-10T09:23:37.409Z" },
    { url = "https://files.pythonhosted.org/packages/56/0c/2dbf513bafd24889d33de2ff0368190a0e69f37bcfa19009ef819fe4d507/websockets-16.0-pp311-pypy311_pp73-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:f4a32d1bd841d4bcbffdcb3d2ce50c09c3909fbead375ab28d0181af89fd04da", size = 176071, upload-time = "2026-01-10T09:23:39.158Z" },
    { url = "https://files.pythonhosted.org/packages/a5/8f/aea9c71cc92bf9b6cc0f7f70df8f0b420636b6c96ef4feee1e16f80f75dd/websockets-16.0-pp311-pypy311_pp73-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:0298d07ee155e2e9fda5be8a9042200dd2e3bb0b8a38482156576f863a9d457c", size = 176968, upload-time = "2026-01-10T09:23:41.031Z" },
    { url = "https://files.pythonhosted.org/packages/9a/3f/f70e03f40ffc9a30d817eef7da1be72ee4956ba8d7255c399a01b135902a/websockets-16.0-pp311-pypy311_pp73-win_amd64.whl", hash = "sha256:a653aea902e0324b52f1613332ddf50b00c06fdaf7e92624fbf8c77c78fa5767", size = 178735, upload-time = "2026-01-10T09:23:42.259Z" },
    { url = "https://files.pythonhosted.org/packages/6f/28/258ebab549c2bf3e64d2b0217b973467394a9cea8c42f70418ca2c5d0d2e/websockets-16.0-py3-none-any.whl", hash = "sha256:1637db62fad1dc833276dded54215f2c7fa46912301a24bd94d45d46a011ceec", size = 171598, upload-time = "2026-01-10T09:23:45.395Z" },
]

[[package]]
name = "yiyu-workbench-cloud-backend"
version = "0.1.0"
source = { virtual = "." }
dependencies = [
    { name = "chromadb" },
    { name = "email-validator" },
    { name = "fastapi" },
    { name = "httpx" },
    { name = "lark-oapi" },
    { name = "passlib", extra = ["bcrypt"] },
    { name = "pydantic" },
    { name = "pytest" },
    { name = "python-docx" },
    { name = "python-jose", extra = ["cryptography"] },
    { name = "python-multipart" },
    { name = "uvicorn" },
]

[package.metadata]
requires-dist = [
    { name = "chromadb", specifier = ">=0.5.0" },
    { name = "email-validator", specifier = ">=2.2.0" },
    { name = "fastapi", specifier = ">=0.111.0" },
    { name = "httpx", specifier = ">=0.27.0" },
    { name = "lark-oapi", specifier = ">=1.4.18" },
    { name = "passlib", extras = ["bcrypt"], specifier = ">=1.7.4" },
    { name = "pydantic", specifier = ">=2.9.0" },
    { name = "pytest", specifier = ">=8.3.0" },
    { name = "python-docx", specifier = ">=1.1.0" },
    { name = "python-jose", extras = ["cryptography"], specifier = ">=3.3.0" },
    { name = "python-multipart", specifier = ">=0.0.9" },
    { name = "uvicorn", specifier = ">=0.30.0" },
]

[[package]]
name = "zipp"
version = "3.23.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/e3/02/0f2892c661036d50ede074e376733dca2ae7c6eb617489437771209d4180/zipp-3.23.0.tar.gz", hash = "sha256:a07157588a12518c9d4034df3fbbee09c814741a33ff63c05fa29d26a2404166", size = 25547, upload-time = "2025-06-08T17:06:39.4Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/2e/54/647ade08bf0db230bfea292f893923872fd20be6ac6f53b2b936ba839d75/zipp-3.23.0-py3-none-any.whl", hash = "sha256:071652d6115ed432f5ce1d34c336c0adfd6a884660d1e9712a256d3d3bd4b14e", size = 10276, upload-time = "2025-06-08T17:06:38.034Z" },
]
~~~

## `deploy/volcengine/cloud-backend/.env.example`

- 编码: `utf-8`

~~~text
YIYU_CLOUD_SECRET_KEY=replace-with-a-strong-random-secret
YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD=replace-with-a-strong-admin-password
YIYU_CLOUD_GUYUAN_PASSWORD=replace-if-needed
YIYU_CLOUD_QINGHUA_PASSWORD=replace-if-needed
YIYU_CLOUD_JIANING_PASSWORD=replace-if-needed
YIYU_CLOUD_YISHUO_PASSWORD=replace-if-needed
YIYU_CLOUD_PUBLIC_BASE_URL=http://101.126.34.232
DOUBAO_FILE_ASR_APP_ID=replace-with-doubao-file-asr-app-id
DOUBAO_FILE_ASR_ACCESS_TOKEN=replace-with-doubao-file-asr-access-token
DOUBAO_STREAM_ASR_APP_ID=replace-with-doubao-stream-asr-app-id
DOUBAO_STREAM_ASR_ACCESS_TOKEN=replace-with-doubao-stream-asr-access-token
YIYU_SMART_INPUT_MODEL=qwen3.5-plus
DASHSCOPE_API_KEY=replace-if-using-qwen-structured-extraction
~~~

## `deploy/volcengine/cloud-backend/Caddyfile`

- 编码: `utf-8`

~~~
{$PUBLIC_HOST} {
    encode gzip zstd
    reverse_proxy api:47831
}
~~~

## `deploy/volcengine/cloud-backend/Dockerfile`

- 编码: `utf-8`

~~~dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv/cloud_backend

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY app ./app

RUN pip install --no-cache-dir \
    fastapi>=0.111.0 \
    uvicorn>=0.30.0 \
    pydantic>=2.9.0 \
    httpx>=0.27.0 \
    email-validator>=2.2.0 \
    python-jose[cryptography]>=3.3.0 \
    passlib[bcrypt]>=1.7.4

EXPOSE 47831

CMD ["python", "-m", "uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "47831"]
~~~

## `deploy/volcengine/cloud-backend/README.md`

- 编码: `utf-8`

~~~markdown
# 火山云部署：cloud_backend

这个目录只负责把在线协作后端 `cloud_backend` 部署到公网，供手机端和后续云协作调用。

## 为什么只部署它

- 手机端当前直接对接的是共享协作后端，而不是桌面本地后端。
- 桌面本地后端继续留在本机，负责本地知识、文件和桥接。
- `cloud_backend` 上云后，手机只需要把服务器地址改成公网 HTTPS 地址即可联动。

## 目录说明

- `Dockerfile`：构建 `cloud_backend` 镜像
- `docker-compose.yml`：启动 API + Caddy HTTPS 代理
- `Caddyfile`：公网反代与证书
- `.env.example`：云端必要环境变量样例
- `bootstrap-server.sh`：第一次登录服务器后执行，自动安装 Docker 并拉起服务

## 最小依赖

- 一台 Ubuntu 云服务器
- 安全组放通 `80 / 443`
- 公网 IP

## HTTPS 策略

默认不依赖你手动配置 DNS。

`bootstrap-server.sh` 会在未提供 `PUBLIC_HOST` 时，自动把公网 IP 变成：

- `x.x.x.x.sslip.io`

然后由 Caddy 申请证书并反向代理到 `cloud_backend`。

如果你后面要切正式域名，例如 `api.yiyu.love`，只需要重新运行：

```bash
PUBLIC_HOST=api.yiyu.love ./bootstrap-server.sh
```

## 手机端接法

部署成功后，手机端服务器地址填：

- `https://<PUBLIC_HOST>`

例如：

- `https://123.123.123.123.sslip.io`

## 注意

- 这套部署当前使用 SQLite，适合作为 V1 协作后端，不适合高并发多副本。
- `.env` 会在首次部署时自动生成随机 secret 和初始口令，后续要妥善保管。
- 如果要长期上线，建议把 `sslip.io` 切到自己的正式域名。

## 2026-03-29 实际落地结果

当前已在火山云 ECS 上用非容器方式落地：

- 实例：`yiyu-cloud-collab-01`
- 当前可用公网地址：[http://101.126.34.232](http://101.126.34.232)
- 证书地址（已签发但当前被火山云 webblock 拦截）：`https://101.126.34.232.sslip.io`
- 运行方式：
  - `systemd`：`yiyu-cloud-backend.service`
  - `nginx`：80/443 反向代理到 `127.0.0.1:47831`
  - `uvicorn`：`app.main:create_app --factory`
- 证书续期：
  - `systemd timer`：`yiyu-certbot-renew.timer`

这次没有沿用 Docker/Caddy 路线，原因是目标机器到 Docker Hub 的出网拉镜像超时；因此切换为：

- `python3 -m venv`
- `systemd`
- `nginx`
- `Let's Encrypt`

同时已经把本机现有的 `YiyuThinkTankCloud/cloud.db` 做一致性快照并导入云端，确保手机端连上后不是空协作库。

### 当前入口说明

- 2026-03-29 起，桌面端打包版协作流量默认指向火山云协作后端；本地 `backend` 保留，`cloud_backend` 默认不再本地拉起。
- 2026-03-30 起，正式协作入口已切到：
  - **HTTPS**：`https://api.yiyu.love`
  - **HTTP 兜底**：`http://101.126.34.232`
- 根域名 `yiyu.love` 的现有站点未改动；只新增了子域名 `api.yiyu.love -> 101.126.34.232`
- **移动端当前策略**：默认使用 `https://api.yiyu.love`
- **桌面端当前策略**：打包版默认使用 `http://101.126.34.232`，仅在显式覆盖为可用地址时才改走其他入口；已知失效的 `api.yiyu.love` 不再作为桌面默认值

## 智能输入 / 语音转写配置

2026-03-30 起，手机端后端链路已经拆成两类：

- 智能输入：文字自然语言 -> 结构化任务草稿
- 长录音/补充录音：录音文件 -> 豆包文件 ASR 转写 -> 文档沉淀请求

对应云端接口：

- `POST /api/v1/mobile/smart-input/task-draft`
- `POST /api/v1/tasks/{task_id}/attachments/{attachment_id}/transcribe-to-document`

如果要让长录音文件转写真正可用，线上 `.env` 至少要补这几项：

```bash
YIYU_CLOUD_PUBLIC_BASE_URL=http://101.126.34.232
DOUBAO_FILE_ASR_APP_ID=your-file-asr-app-id
DOUBAO_FILE_ASR_ACCESS_TOKEN=your-file-asr-access-token
```

如果后续要把“智能输入”改成真正的流式短语音识别，再补：

```bash
DOUBAO_STREAM_ASR_APP_ID=your-stream-asr-app-id
DOUBAO_STREAM_ASR_ACCESS_TOKEN=your-stream-asr-access-token
```

可选增强：

```bash
YIYU_SMART_INPUT_MODEL=qwen3.5-plus
DASHSCOPE_API_KEY=your-dashscope-key
```

说明：

- `YIYU_CLOUD_PUBLIC_BASE_URL`
  - 用于给豆包标准版 ASR 提供可回拉的临时音频 URL
  - 如果实例对外域名已经可用，推荐填正式公网域名，例如 `https://api.yiyu.love`
- `DOUBAO_FILE_ASR_*`
  - 负责长录音/补充录音这类文件上传后的中文语音转写
- `DOUBAO_STREAM_ASR_*`
  - 预留给智能输入的短语音/流式识别
- `DASHSCOPE_API_KEY`
  - 可选；存在时会优先走 Qwen 结构化提取
  - 没有时仍可用规则兜底生成草稿

格式注意：

- Expo 真机常见录音格式是 `m4a`
- `m4a/aac` 会优先走豆包标准版识别，因此更依赖 `YIYU_CLOUD_PUBLIC_BASE_URL`
- `wav/mp3/ogg` 这类格式可以直接走极速版 data-base64 接口

## 2026-03-30 可重复发布方式

当前线上协作后端已经不建议继续手工 SSH 拼命令更新。

仓库里现在有两条本地脚本：

- `scripts/deploy-cloud-backend-volcengine.sh`
  - 把 `cloud_backend/app`、`pyproject.toml`、`uv.lock`、`requirements.deploy.txt` 同步到服务器
  - 刷新远端 `venv`
  - 重启 `yiyu-cloud-backend.service`
  - 最后自动做 smoke check
- `scripts/smoke-cloud-backend-volcengine.sh`
  - 检查 `/health`
  - 检查 `/openapi.json` 里是否已经包含智能输入路由
  - 提醒是否已配置智能输入所需环境变量

默认目标：

- 主机：`root@101.126.34.232`
- 目录：`/opt/yiyu/cloud-backend`
- 服务：`yiyu-cloud-backend.service`

如果本机 SSH 不是默认钥匙，可设置：

```bash
export YIYU_VOLCENGINE_SSH_KEY=/absolute/path/to/private_key
```

然后直接执行：

```bash
./scripts/deploy-cloud-backend-volcengine.sh
```

如果只想先检查线上接口，不发布代码：

```bash
./scripts/smoke-cloud-backend-volcengine.sh https://api.yiyu.love
```

## 当前 HTTPS 真实状态

截至 2026-03-30：

- `sslip.io` 域名虽然签出过证书，但公网访问会被火山云 `webblock` 拦截
- `nip.io` 的 HTTP 访问是通的，但无论 `HTTP-01` 还是 `TLS-ALPN-01`，Let's Encrypt 校验都在 CA 侧出现 `Connection reset by peer`
- 已改用自有域名子域名 `api.yiyu.love`
- 解析方式：阿里云 DNS 新增 `api -> 101.126.34.232`
- 证书方式：`acme.sh + Let's Encrypt + nginx`

当前对外口径：

- **主入口**：`https://api.yiyu.love`
- **HTTP 兜底**：`http://101.126.34.232`
- **根站保持不变**：`yiyu.love` 现有网站未迁移、未替换
~~~

## `deploy/volcengine/cloud-backend/bootstrap-server.sh`

- 编码: `utf-8`

~~~bash
#!/usr/bin/env bash
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/yiyu/cloud-backend}
PUBLIC_HOST=${PUBLIC_HOST:-}

docker_compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
    return
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
    return
  fi
  echo "Docker Compose is not available." >&2
  exit 1
}

if ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  if curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg; then
    chmod a+r /etc/apt/keyrings/docker.gpg
    . /etc/os-release
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
      | tee /etc/apt/sources.list.d/docker.list >/dev/null
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  else
    echo "Docker upstream repository unreachable, falling back to Ubuntu packages." >&2
    rm -f /etc/apt/keyrings/docker.gpg /etc/apt/sources.list.d/docker.list
    apt-get update
    apt-get install -y docker.io docker-compose-v2
  fi
  systemctl enable docker
  systemctl start docker
fi

mkdir -p "${APP_DIR}"
cd "${APP_DIR}"

if [[ ! -f .env ]]; then
  cp .env.example .env
  python3 - <<'PY'
from pathlib import Path
import secrets

env_path = Path(".env")
content = env_path.read_text()
replacements = {
    "replace-with-a-strong-random-secret": secrets.token_urlsafe(48),
    "replace-with-a-strong-admin-password": secrets.token_urlsafe(18),
    "replace-if-needed": secrets.token_urlsafe(14),
}
for needle, value in replacements.items():
    content = content.replace(needle, value, 1)
env_path.write_text(content)
PY
fi

if [[ -z "${PUBLIC_HOST}" ]]; then
  PUBLIC_IP=$(curl -4fsSL https://api.ipify.org)
  PUBLIC_HOST="${PUBLIC_IP}.sslip.io"
fi

export PUBLIC_HOST
docker_compose up -d --build

echo "DEPLOY_OK https://${PUBLIC_HOST}"
~~~

## `deploy/volcengine/cloud-backend/docker-compose.yml`

- 编码: `utf-8`

~~~yaml
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    restart: unless-stopped
    env_file:
      - .env
    environment:
      YIYU_CLOUD_DATA_DIR: /data
    volumes:
      - ./data:/data
    expose:
      - "47831"

  caddy:
    image: caddy:2
    restart: unless-stopped
    depends_on:
      - api
    environment:
      PUBLIC_HOST: ${PUBLIC_HOST}
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config

volumes:
  caddy_data:
  caddy_config:
~~~

## `index.html`

- 编码: `utf-8`

~~~html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>益语智库自用平台</title>
    <style>
      html,
      body {
        margin: 0;
        min-height: 100%;
        background: #f9fafb;
      }

      #root {
        min-height: 100vh;
      }

      #boot-diagnostic {
        position: fixed;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 32px;
        background: #f9fafb;
        color: #111827;
        font-family: "PingFang SC", "SF Pro Display", "Helvetica Neue", sans-serif;
        z-index: 2147483647;
      }

      #boot-diagnostic[data-hidden="true"] {
        display: none;
      }

      .boot-diagnostic__panel {
        width: min(920px, calc(100vw - 48px));
        border-radius: 28px;
        border: 1px solid #dbe5ff;
        background: rgba(255, 255, 255, 0.98);
        box-shadow: 0 24px 72px rgba(15, 23, 42, 0.12);
        padding: 28px;
      }

      .boot-diagnostic__eyebrow {
        margin: 0;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.22em;
        text-transform: uppercase;
        color: #4f46e5;
      }

      .boot-diagnostic__title {
        margin: 12px 0 0;
        font-size: 28px;
        font-weight: 700;
        line-height: 1.25;
      }

      .boot-diagnostic__body {
        margin: 14px 0 0;
        font-size: 14px;
        line-height: 1.8;
        color: #4b5563;
      }

      .boot-diagnostic__error {
        margin-top: 18px;
        border-radius: 18px;
        border: 1px solid #fecaca;
        background: #fff1f2;
        padding: 14px 16px;
        font-size: 13px;
        line-height: 1.8;
        color: #be123c;
        white-space: pre-wrap;
      }

      .boot-diagnostic__log {
        margin-top: 18px;
        border-radius: 18px;
        border: 1px solid #e5e7eb;
        background: #f9fafb;
        padding: 14px 16px;
        font-size: 12px;
        line-height: 1.8;
        color: #374151;
        white-space: pre-wrap;
      }
    </style>
    <script>
      (() => {
        const bootEvents = [];
        const record = (message) => {
          bootEvents.push(`${new Date().toISOString()} ${message}`);
          window.__YIYU_BOOT_EVENTS__ = bootEvents;
        };

        const ensureDiagnostic = () => {
          let node = document.getElementById('boot-diagnostic');
          if (node) return node;
          node = document.createElement('div');
          node.id = 'boot-diagnostic';
          node.innerHTML = `
            <div class="boot-diagnostic__panel">
              <p class="boot-diagnostic__eyebrow">Startup Diagnostic</p>
              <h1 class="boot-diagnostic__title">正在初始化桌面界面…</h1>
              <p class="boot-diagnostic__body">
                如果页面长时间保持空白，下面会直接显示启动错误，而不是继续白屏。
              </p>
              <div id="boot-diagnostic-error" class="boot-diagnostic__error" style="display:none;"></div>
              <div id="boot-diagnostic-log" class="boot-diagnostic__log">等待渲染层启动…</div>
            </div>
          `;
          document.addEventListener('DOMContentLoaded', () => {
            if (!document.getElementById('boot-diagnostic')) {
              document.body.appendChild(node);
            }
          }, { once: true });
          return node;
        };

        const renderLog = () => {
          const node = ensureDiagnostic();
          const logNode = node.querySelector('#boot-diagnostic-log');
          if (logNode) {
            logNode.textContent = bootEvents.join('\n');
          }
        };

        const showError = (label, detail) => {
          const node = ensureDiagnostic();
          const errorNode = node.querySelector('#boot-diagnostic-error');
          if (errorNode) {
            errorNode.style.display = 'block';
            errorNode.textContent = `${label}\n${detail}`;
          }
          renderLog();
        };

        window.__YIYU_HIDE_BOOT_DIAGNOSTIC__ = () => {
          const node = document.getElementById('boot-diagnostic');
          if (node) node.setAttribute('data-hidden', 'true');
        };

        record('index.html:bootstrap-loaded');
        renderLog();

        window.addEventListener('error', (event) => {
          const detail = event.error && event.error.stack
            ? event.error.stack
            : `${event.message} @ ${event.filename}:${event.lineno}:${event.colno}`;
          record(`window-error:${String(event.message || '').slice(0, 120)}`);
          showError('窗口级错误', detail);
        });

        window.addEventListener('unhandledrejection', (event) => {
          const detail = event.reason && event.reason.stack ? event.reason.stack : String(event.reason);
          record(`unhandled-rejection:${String(event.reason || '').slice(0, 120)}`);
          showError('未处理 Promise 异常', detail);
        });

        window.addEventListener('DOMContentLoaded', () => {
          document.body.appendChild(ensureDiagnostic());
          renderLog();
        });

        window.setTimeout(() => {
          if (!window.__YIYU_APP_RENDERED__) {
            record('index.html:render-timeout-6000ms');
            renderLog();
          }
        }, 6000);
      })();
    </script>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/renderer/main.tsx"></script>
  </body>
  </html>
~~~

## `mobile/.gitignore`

- 编码: `utf-8`

~~~
.DS_Store
.expo/
dist/
node_modules/
.mobile-core-tests/

# Android
android/.gradle/
android/build/
android/local.properties
android/app/build/
android/app/debug.keystore
android/.cxx/
*.apk
*.aab

# iOS
ios/build/
ios/Pods/
ios/.xcode.env.local
ios/DerivedData/

# Logs
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*
~~~

## `mobile/README.md`

- 编码: `utf-8`

~~~markdown
# Yiyu Think Tank Mobile

React Native / Expo mobile client for the Yiyu Think Tank task, calendar, consultation, and smart-input workflows.

## Requirements

- Node.js 20+
- npm
- Xcode / Android Studio toolchains for native builds

## Install

```bash
npm install
```

## Run Web Preview

```bash
npx expo start --web
```

## Run Native

```bash
npx expo run:android
npx expo run:ios
```

## Build Android Release

```bash
cd android
./gradlew assembleRelease
```
~~~

## `mobile/android/.gitignore`

- 编码: `utf-8`

~~~
# OSX
#
.DS_Store

# Android/IntelliJ
#
build/
.idea
.gradle
local.properties
*.iml
*.hprof
.cxx/

# Bundle artifacts
*.jsbundle
~~~

## `mobile/android/app/build.gradle`

- 编码: `utf-8`

~~~gradle
apply plugin: "com.android.application"
apply plugin: "org.jetbrains.kotlin.android"
apply plugin: "com.facebook.react"

def projectRoot = rootDir.getAbsoluteFile().getParentFile().getAbsolutePath()

/**
 * This is the configuration block to customize your React Native Android app.
 * By default you don't need to apply any configuration, just uncomment the lines you need.
 */
react {
    entryFile = file(["node", "-e", "require('expo/scripts/resolveAppEntry')", projectRoot, "android", "absolute"].execute(null, rootDir).text.trim())
    reactNativeDir = new File(["node", "--print", "require.resolve('react-native/package.json')"].execute(null, rootDir).text.trim()).getParentFile().getAbsoluteFile()
    hermesCommand = new File(["node", "--print", "require.resolve('hermes-compiler/package.json', { paths: [require.resolve('react-native/package.json')] })"].execute(null, rootDir).text.trim()).getParentFile().getAbsolutePath() + "/hermesc/%OS-BIN%/hermesc"
    codegenDir = new File(["node", "--print", "require.resolve('@react-native/codegen/package.json', { paths: [require.resolve('react-native/package.json')] })"].execute(null, rootDir).text.trim()).getParentFile().getAbsoluteFile()

    enableBundleCompression = (findProperty('android.enableBundleCompression') ?: false).toBoolean()
    // Use Expo CLI to bundle the app, this ensures the Metro config
    // works correctly with Expo projects.
    cliFile = new File(["node", "--print", "require.resolve('@expo/cli', { paths: [require.resolve('expo/package.json')] })"].execute(null, rootDir).text.trim())
    bundleCommand = "export:embed"

    /* Folders */
     //   The root of your project, i.e. where "package.json" lives. Default is '../..'
    // root = file("../../")
    //   The folder where the react-native NPM package is. Default is ../../node_modules/react-native
    // reactNativeDir = file("../../node_modules/react-native")
    //   The folder where the react-native Codegen package is. Default is ../../node_modules/@react-native/codegen
    // codegenDir = file("../../node_modules/@react-native/codegen")

    /* Variants */
    //   The list of variants to that are debuggable. For those we're going to
    //   skip the bundling of the JS bundle and the assets. By default is just 'debug'.
    //   If you add flavors like lite, prod, etc. you'll have to list your debuggableVariants.
    // debuggableVariants = ["liteDebug", "prodDebug"]

    /* Bundling */
    //   A list containing the node command and its flags. Default is just 'node'.
    // nodeExecutableAndArgs = ["node"]

    //
    //   The path to the CLI configuration file. Default is empty.
    // bundleConfig = file(../rn-cli.config.js)
    //
    //   The name of the generated asset file containing your JS bundle
    // bundleAssetName = "MyApplication.android.bundle"
    //
    //   The entry file for bundle generation. Default is 'index.android.js' or 'index.js'
    // entryFile = file("../js/MyApplication.android.js")
    //
    //   A list of extra flags to pass to the 'bundle' commands.
    //   See https://github.com/react-native-community/cli/blob/main/docs/commands.md#bundle
    // extraPackagerArgs = []

    /* Hermes Commands */
    //   The hermes compiler command to run. By default it is 'hermesc'
    // hermesCommand = "$rootDir/my-custom-hermesc/bin/hermesc"
    //
    //   The list of flags to pass to the Hermes compiler. By default is "-O", "-output-source-map"
    // hermesFlags = ["-O", "-output-source-map"]

    /* Autolinking */
    autolinkLibrariesWithApp()
}

/**
 * Set this to true in release builds to optimize the app using [R8](https://developer.android.com/topic/performance/app-optimization/enable-app-optimization).
 */
def enableMinifyInReleaseBuilds = (findProperty('android.enableMinifyInReleaseBuilds') ?: false).toBoolean()

/**
 * The preferred build flavor of JavaScriptCore (JSC)
 *
 * For example, to use the international variant, you can use:
 * `def jscFlavor = 'org.webkit:android-jsc-intl:+'`
 *
 * The international variant includes ICU i18n library and necessary data
 * allowing to use e.g. `Date.toLocaleString` and `String.localeCompare` that
 * give correct results when using with locales other than en-US. Note that
 * this variant is about 6MiB larger per architecture than default.
 */
def jscFlavor = 'io.github.react-native-community:jsc-android:2026004.+'

android {
    ndkVersion rootProject.ext.ndkVersion

    buildToolsVersion rootProject.ext.buildToolsVersion
    compileSdk rootProject.ext.compileSdkVersion

    namespace 'com.yiyu.mobile'
    defaultConfig {
        applicationId 'com.yiyu.mobile'
        minSdkVersion rootProject.ext.minSdkVersion
        targetSdkVersion rootProject.ext.targetSdkVersion
        versionCode 1
        versionName "1.0.0"

        buildConfigField "String", "REACT_NATIVE_RELEASE_LEVEL", "\"${findProperty('reactNativeReleaseLevel') ?: 'stable'}\""
    }
    signingConfigs {
        debug {
            storeFile file('debug.keystore')
            storePassword 'android'
            keyAlias 'androiddebugkey'
            keyPassword 'android'
        }
    }
    buildTypes {
        debug {
            signingConfig signingConfigs.debug
        }
        release {
            // Caution! In production, you need to generate your own keystore file.
            // see https://reactnative.dev/docs/signed-apk-android.
            signingConfig signingConfigs.debug
            def enableShrinkResources = findProperty('android.enableShrinkResourcesInReleaseBuilds') ?: 'false'
            shrinkResources enableShrinkResources.toBoolean()
            minifyEnabled enableMinifyInReleaseBuilds
            proguardFiles getDefaultProguardFile("proguard-android.txt"), "proguard-rules.pro"
            def enablePngCrunchInRelease = findProperty('android.enablePngCrunchInReleaseBuilds') ?: 'true'
            crunchPngs enablePngCrunchInRelease.toBoolean()
        }
    }
    packagingOptions {
        jniLibs {
            def enableLegacyPackaging = findProperty('expo.useLegacyPackaging') ?: 'false'
            useLegacyPackaging enableLegacyPackaging.toBoolean()
        }
    }
    androidResources {
        ignoreAssetsPattern '!.svn:!.git:!.ds_store:!*.scc:!CVS:!thumbs.db:!picasa.ini:!*~'
    }
}

// Apply static values from `gradle.properties` to the `android.packagingOptions`
// Accepts values in comma delimited lists, example:
// android.packagingOptions.pickFirsts=/LICENSE,**/picasa.ini
["pickFirsts", "excludes", "merges", "doNotStrip"].each { prop ->
    // Split option: 'foo,bar' -> ['foo', 'bar']
    def options = (findProperty("android.packagingOptions.$prop") ?: "").split(",");
    // Trim all elements in place.
    for (i in 0..<options.size()) options[i] = options[i].trim();
    // `[] - ""` is essentially `[""].filter(Boolean)` removing all empty strings.
    options -= ""

    if (options.length > 0) {
        println "android.packagingOptions.$prop += $options ($options.length)"
        // Ex: android.packagingOptions.pickFirsts += '**/SCCS/**'
        options.each {
            android.packagingOptions[prop] += it
        }
    }
}

dependencies {
    // The version of react-native is set by the React Native Gradle Plugin
    implementation("com.facebook.react:react-android")

    def isGifEnabled = (findProperty('expo.gif.enabled') ?: "") == "true";
    def isWebpEnabled = (findProperty('expo.webp.enabled') ?: "") == "true";
    def isWebpAnimatedEnabled = (findProperty('expo.webp.animated') ?: "") == "true";

    if (isGifEnabled) {
        // For animated gif support
        implementation("com.facebook.fresco:animated-gif:${expoLibs.versions.fresco.get()}")
    }

    if (isWebpEnabled) {
        // For webp support
        implementation("com.facebook.fresco:webpsupport:${expoLibs.versions.fresco.get()}")
        if (isWebpAnimatedEnabled) {
            // Animated webp support
            implementation("com.facebook.fresco:animated-webp:${expoLibs.versions.fresco.get()}")
        }
    }

    if (hermesEnabled.toBoolean()) {
        implementation("com.facebook.react:hermes-android")
    } else {
        implementation jscFlavor
    }
}
~~~

## `mobile/android/app/proguard-rules.pro`

- 编码: `utf-8`

~~~
# Add project specific ProGuard rules here.
# By default, the flags in this file are appended to flags specified
# in /usr/local/Cellar/android-sdk/24.3.3/tools/proguard/proguard-android.txt
# You can edit the include path and order by changing the proguardFiles
# directive in build.gradle.
#
# For more details, see
#   http://developer.android.com/guide/developing/tools/proguard.html

# react-native-reanimated
-keep class com.swmansion.reanimated.** { *; }
-keep class com.facebook.react.turbomodule.** { *; }

# Add any project specific keep options here:
~~~

## `mobile/android/app/src/debug/AndroidManifest.xml`

- 编码: `utf-8`

~~~xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools">

    <uses-permission android:name="android.permission.SYSTEM_ALERT_WINDOW"/>

    <application android:usesCleartextTraffic="true" tools:targetApi="28" tools:ignore="GoogleAppIndexingWarning" tools:replace="android:usesCleartextTraffic" />
</manifest>
~~~

## `mobile/android/app/src/debugOptimized/AndroidManifest.xml`

- 编码: `utf-8`

~~~xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools">

    <uses-permission android:name="android.permission.SYSTEM_ALERT_WINDOW"/>

    <application android:usesCleartextTraffic="true" tools:targetApi="28" tools:ignore="GoogleAppIndexingWarning" tools:replace="android:usesCleartextTraffic" />
</manifest>
~~~

## `mobile/android/app/src/main/AndroidManifest.xml`

- 编码: `utf-8`

~~~xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android" xmlns:tools="http://schemas.android.com/tools">
  <uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>
  <uses-permission android:name="android.permission.FOREGROUND_SERVICE_MICROPHONE"/>
  <uses-permission android:name="android.permission.INTERNET"/>
  <uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS"/>
  <uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>
  <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" android:maxSdkVersion="32" tools:replace="android:maxSdkVersion"/>
  <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED"/>
  <uses-permission android:name="android.permission.RECORD_AUDIO"/>
  <uses-permission android:name="android.permission.SYSTEM_ALERT_WINDOW"/>
  <uses-permission android:name="android.permission.VIBRATE"/>
  <uses-permission android:name="android.permission.WAKE_LOCK"/>
  <uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" android:maxSdkVersion="32" tools:replace="android:maxSdkVersion"/>
  <queries>
    <intent>
      <action android:name="android.intent.action.VIEW"/>
      <category android:name="android.intent.category.BROWSABLE"/>
      <data android:scheme="https"/>
    </intent>
  </queries>
  <queries>
    <package android:name="com.google.android.googlequicksearchbox"/>
    <intent>
      <action android:name="android.speech.RecognitionService"/>
    </intent>
  </queries>
  <queries>
    <package android:name="com.google.android.as"/>
    <intent>
      <action android:name="android.speech.RecognitionService"/>
    </intent>
  </queries>
  <application android:name=".MainApplication" android:label="@string/app_name" android:icon="@mipmap/ic_launcher" android:roundIcon="@mipmap/ic_launcher_round" android:usesCleartextTraffic="true" android:allowBackup="true" android:theme="@style/AppTheme" android:supportsRtl="true" android:enableOnBackInvokedCallback="false" android:fullBackupContent="@xml/secure_store_backup_rules" android:dataExtractionRules="@xml/secure_store_data_extraction_rules">
    <meta-data android:name="expo.modules.updates.ENABLED" android:value="false"/>
    <meta-data android:name="expo.modules.updates.EXPO_UPDATES_CHECK_ON_LAUNCH" android:value="ALWAYS"/>
    <meta-data android:name="expo.modules.updates.EXPO_UPDATES_LAUNCH_WAIT_MS" android:value="0"/>
    <service android:name="expo.modules.audio.service.AudioRecordingService" android:exported="false" android:foregroundServiceType="microphone"/>
    <activity android:name=".MainActivity" android:configChanges="keyboard|keyboardHidden|orientation|screenSize|screenLayout|uiMode|smallestScreenSize" android:launchMode="singleTask" android:windowSoftInputMode="adjustResize" android:theme="@style/Theme.App.SplashScreen" android:exported="true" android:screenOrientation="portrait">
      <intent-filter>
        <action android:name="android.intent.action.MAIN"/>
        <category android:name="android.intent.category.LAUNCHER"/>
      </intent-filter>
      <intent-filter>
        <action android:name="android.intent.action.VIEW"/>
        <category android:name="android.intent.category.DEFAULT"/>
        <category android:name="android.intent.category.BROWSABLE"/>
        <data android:scheme="yiyu"/>
      </intent-filter>
    </activity>
  </application>
</manifest>
~~~

## `mobile/android/app/src/main/java/com/yiyu/mobile/MainActivity.kt`

- 编码: `utf-8`

~~~kotlin
package com.yiyu.mobile

import android.os.Build
import android.os.Bundle

import com.facebook.react.ReactActivity
import com.facebook.react.ReactActivityDelegate
import com.facebook.react.defaults.DefaultNewArchitectureEntryPoint.fabricEnabled
import com.facebook.react.defaults.DefaultReactActivityDelegate

import expo.modules.ReactActivityDelegateWrapper

class MainActivity : ReactActivity() {
  override fun onCreate(savedInstanceState: Bundle?) {
    // Set the theme to AppTheme BEFORE onCreate to support
    // coloring the background, status bar, and navigation bar.
    // This is required for expo-splash-screen.
    setTheme(R.style.AppTheme);
    super.onCreate(null)
  }

  /**
   * Returns the name of the main component registered from JavaScript. This is used to schedule
   * rendering of the component.
   */
  override fun getMainComponentName(): String = "main"

  /**
   * Returns the instance of the [ReactActivityDelegate]. We use [DefaultReactActivityDelegate]
   * which allows you to enable New Architecture with a single boolean flags [fabricEnabled]
   */
  override fun createReactActivityDelegate(): ReactActivityDelegate {
    return ReactActivityDelegateWrapper(
          this,
          BuildConfig.IS_NEW_ARCHITECTURE_ENABLED,
          object : DefaultReactActivityDelegate(
              this,
              mainComponentName,
              fabricEnabled
          ){})
  }

  /**
    * Align the back button behavior with Android S
    * where moving root activities to background instead of finishing activities.
    * @see <a href="https://developer.android.com/reference/android/app/Activity#onBackPressed()">onBackPressed</a>
    */
  override fun invokeDefaultOnBackPressed() {
      if (Build.VERSION.SDK_INT <= Build.VERSION_CODES.R) {
          if (!moveTaskToBack(false)) {
              // For non-root activities, use the default implementation to finish them.
              super.invokeDefaultOnBackPressed()
          }
          return
      }

      // Use the default back button implementation on Android S
      // because it's doing more than [Activity.moveTaskToBack] in fact.
      super.invokeDefaultOnBackPressed()
  }
}
~~~

## `mobile/android/app/src/main/java/com/yiyu/mobile/MainApplication.kt`

- 编码: `utf-8`

~~~kotlin
package com.yiyu.mobile

import android.app.Application
import android.content.res.Configuration

import com.facebook.react.PackageList
import com.facebook.react.ReactApplication
import com.facebook.react.ReactNativeApplicationEntryPoint.loadReactNative
import com.facebook.react.ReactPackage
import com.facebook.react.ReactHost
import com.facebook.react.common.ReleaseLevel
import com.facebook.react.defaults.DefaultNewArchitectureEntryPoint

import expo.modules.ApplicationLifecycleDispatcher
import expo.modules.ExpoReactHostFactory

class MainApplication : Application(), ReactApplication {

  override val reactHost: ReactHost by lazy {
    ExpoReactHostFactory.getDefaultReactHost(
      context = applicationContext,
      packageList =
        PackageList(this).packages.apply {
          // Packages that cannot be autolinked yet can be added manually here, for example:
          // add(MyReactNativePackage())
        }
    )
  }

  override fun onCreate() {
    super.onCreate()
    DefaultNewArchitectureEntryPoint.releaseLevel = try {
      ReleaseLevel.valueOf(BuildConfig.REACT_NATIVE_RELEASE_LEVEL.uppercase())
    } catch (e: IllegalArgumentException) {
      ReleaseLevel.STABLE
    }
    loadReactNative(this)
    ApplicationLifecycleDispatcher.onApplicationCreate(this)
  }

  override fun onConfigurationChanged(newConfig: Configuration) {
    super.onConfigurationChanged(newConfig)
    ApplicationLifecycleDispatcher.onConfigurationChanged(this, newConfig)
  }
}
~~~

## `mobile/android/app/src/main/res/drawable/ic_launcher_background.xml`

- 编码: `utf-8`

~~~xml
<layer-list xmlns:android="http://schemas.android.com/apk/res/android">
  <item android:drawable="@color/splashscreen_background"/>
  <item>
    <bitmap android:gravity="center" android:src="@drawable/splashscreen_logo"/>
  </item>
</layer-list>
~~~

## `mobile/android/app/src/main/res/drawable/rn_edit_text_material.xml`

- 编码: `utf-8`

~~~xml
<?xml version="1.0" encoding="utf-8"?>
<!-- Copyright (C) 2014 The Android Open Source Project

     Licensed under the Apache License, Version 2.0 (the "License");
     you may not use this file except in compliance with the License.
     You may obtain a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

     Unless required by applicable law or agreed to in writing, software
     distributed under the License is distributed on an "AS IS" BASIS,
     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
     See the License for the specific language governing permissions and
     limitations under the License.
-->
<inset xmlns:android="http://schemas.android.com/apk/res/android"
       android:insetLeft="@dimen/abc_edit_text_inset_horizontal_material"
       android:insetRight="@dimen/abc_edit_text_inset_horizontal_material"
       android:insetTop="@dimen/abc_edit_text_inset_top_material"
       android:insetBottom="@dimen/abc_edit_text_inset_bottom_material"
       >

    <selector>
        <!--
          This file is a copy of abc_edit_text_material (https://bit.ly/3k8fX7I).
          The item below with state_pressed="false" and state_focused="false" causes a NullPointerException.
          NullPointerException:tempt to invoke virtual method 'android.graphics.drawable.Drawable android.graphics.drawable.Drawable$ConstantState.newDrawable(android.content.res.Resources)'

          <item android:state_pressed="false" android:state_focused="false" android:drawable="@drawable/abc_textfield_default_mtrl_alpha"/>

          For more info, see https://bit.ly/3CdLStv (react-native/pull/29452) and https://bit.ly/3nxOMoR.
        -->
        <item android:state_enabled="false" android:drawable="@drawable/abc_textfield_default_mtrl_alpha"/>
        <item android:drawable="@drawable/abc_textfield_activated_mtrl_alpha"/>
    </selector>

</inset>
~~~

## `mobile/android/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml`

- 编码: `utf-8`

~~~xml
<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@mipmap/ic_launcher_background"/>
    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>
    <monochrome android:drawable="@mipmap/ic_launcher_monochrome"/>
</adaptive-icon>
~~~

## `mobile/android/app/src/main/res/mipmap-anydpi-v26/ic_launcher_round.xml`

- 编码: `utf-8`

~~~xml
<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@mipmap/ic_launcher_background"/>
    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>
    <monochrome android:drawable="@mipmap/ic_launcher_monochrome"/>
</adaptive-icon>
~~~

## `mobile/android/app/src/main/res/values-night/colors.xml`

- 编码: `utf-8`

~~~xml
<resources/>
~~~

## `mobile/android/app/src/main/res/values/colors.xml`

- 编码: `utf-8`

~~~xml
<resources>
  <color name="splashscreen_background">#1E3A5F</color>
  <color name="iconBackground">#1E3A5F</color>
  <color name="colorPrimary">#023c69</color>
</resources>
~~~

## `mobile/android/app/src/main/res/values/strings.xml`

- 编码: `utf-8`

~~~xml
<resources>
  <string name="app_name">益语智库</string>
  <string name="expo_splash_screen_resize_mode" translatable="false">contain</string>
</resources>
~~~

## `mobile/android/app/src/main/res/values/styles.xml`

- 编码: `utf-8`

~~~xml
<resources xmlns:tools="http://schemas.android.com/tools">
  <style name="AppTheme" parent="Theme.AppCompat.DayNight.NoActionBar">
    <item name="android:editTextBackground">@drawable/rn_edit_text_material</item>
    <item name="colorPrimary">@color/colorPrimary</item>
    <item name="android:statusBarColor">@android:color/transparent</item>
    <item name="android:navigationBarColor">@android:color/transparent</item>
  </style>
  <style name="Theme.App.SplashScreen" parent="AppTheme">
    <item name="android:windowBackground">@drawable/ic_launcher_background</item>
  </style>
</resources>
~~~

## `mobile/android/build.gradle`

- 编码: `utf-8`

~~~gradle
// Top-level build file where you can add configuration options common to all sub-projects/modules.

buildscript {
  repositories {
    google()
    mavenCentral()
  }
  dependencies {
    classpath('com.android.tools.build:gradle')
    classpath('com.facebook.react:react-native-gradle-plugin')
    classpath('org.jetbrains.kotlin:kotlin-gradle-plugin')
  }
}

allprojects {
  repositories {
    google()
    mavenCentral()
    maven { url 'https://www.jitpack.io' }
  }
}

apply plugin: "expo-root-project"
apply plugin: "com.facebook.react.rootproject"
~~~

## `mobile/android/gradle.properties`

- 编码: `utf-8`

~~~properties
# Project-wide Gradle settings.

# IDE (e.g. Android Studio) users:
# Gradle settings configured through the IDE *will override*
# any settings specified in this file.

# For more details on how to configure your build environment visit
# http://www.gradle.org/docs/current/userguide/build_environment.html

# Specifies the JVM arguments used for the daemon process.
# The setting is particularly useful for tweaking memory settings.
# Default value: -Xmx512m -XX:MaxMetaspaceSize=256m
org.gradle.jvmargs=-Xmx2048m -XX:MaxMetaspaceSize=512m

# When configured, Gradle will run in incubating parallel mode.
# This option should only be used with decoupled projects. More details, visit
# http://www.gradle.org/docs/current/userguide/multi_project_builds.html#sec:decoupled_projects
org.gradle.parallel=true

# AndroidX package structure to make it clearer which packages are bundled with the
# Android operating system, and which are packaged with your app's APK
# https://developer.android.com/topic/libraries/support-library/androidx-rn
android.useAndroidX=true

# Enable AAPT2 PNG crunching
android.enablePngCrunchInReleaseBuilds=true

# Use this property to specify which architecture you want to build.
# You can also override it from the CLI using
# ./gradlew <task> -PreactNativeArchitectures=x86_64
reactNativeArchitectures=armeabi-v7a,arm64-v8a,x86,x86_64

# Use this property to enable support to the new architecture.
# This will allow you to use TurboModules and the Fabric render in
# your application. You should enable this flag either if you want
# to write custom TurboModules/Fabric components OR use libraries that
# are providing them.
newArchEnabled=true

# Use this property to enable or disable the Hermes JS engine.
# If set to false, you will be using JSC instead.
hermesEnabled=true

# Use this property to enable edge-to-edge display support.
# This allows your app to draw behind system bars for an immersive UI.
# Note: Only works with ReactActivity and should not be used with custom Activity.
edgeToEdgeEnabled=true

# Enable GIF support in React Native images (~200 B increase)
expo.gif.enabled=true
# Enable webp support in React Native images (~85 KB increase)
expo.webp.enabled=true
# Enable animated webp support (~3.4 MB increase)
# Disabled by default because iOS doesn't support animated webp
expo.webp.animated=false

# Enable network inspector
EX_DEV_CLIENT_NETWORK_INSPECTOR=true

# Use legacy packaging to compress native libraries in the resulting APK.
expo.useLegacyPackaging=false
~~~

## `mobile/android/gradle/wrapper/gradle-wrapper.properties`

- 编码: `utf-8`

~~~properties
distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\://services.gradle.org/distributions/gradle-9.0.0-bin.zip
networkTimeout=10000
validateDistributionUrl=true
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
~~~

## `mobile/android/gradlew`

- 编码: `utf-8`

~~~
#!/bin/sh

#
# Copyright © 2015 the original authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0
#

##############################################################################
#
#   Gradle start up script for POSIX generated by Gradle.
#
#   Important for running:
#
#   (1) You need a POSIX-compliant shell to run this script. If your /bin/sh is
#       noncompliant, but you have some other compliant shell such as ksh or
#       bash, then to run this script, type that shell name before the whole
#       command line, like:
#
#           ksh Gradle
#
#       Busybox and similar reduced shells will NOT work, because this script
#       requires all of these POSIX shell features:
#         * functions;
#         * expansions «$var», «${var}», «${var:-default}», «${var+SET}»,
#           «${var#prefix}», «${var%suffix}», and «$( cmd )»;
#         * compound commands having a testable exit status, especially «case»;
#         * various built-in commands including «command», «set», and «ulimit».
#
#   Important for patching:
#
#   (2) This script targets any POSIX shell, so it avoids extensions provided
#       by Bash, Ksh, etc; in particular arrays are avoided.
#
#       The "traditional" practice of packing multiple parameters into a
#       space-separated string is a well documented source of bugs and security
#       problems, so this is (mostly) avoided, by progressively accumulating
#       options in "$@", and eventually passing that to Java.
#
#       Where the inherited environment variables (DEFAULT_JVM_OPTS, JAVA_OPTS,
#       and GRADLE_OPTS) rely on word-splitting, this is performed explicitly;
#       see the in-line comments for details.
#
#       There are tweaks for specific operating systems such as AIX, CygWin,
#       Darwin, MinGW, and NonStop.
#
#   (3) This script is generated from the Groovy template
#       https://github.com/gradle/gradle/blob/HEAD/platforms/jvm/plugins-application/src/main/resources/org/gradle/api/internal/plugins/unixStartScript.txt
#       within the Gradle project.
#
#       You can find Gradle at https://github.com/gradle/gradle/.
#
##############################################################################

# Attempt to set APP_HOME

# Resolve links: $0 may be a link
app_path=$0

# Need this for daisy-chained symlinks.
while
    APP_HOME=${app_path%"${app_path##*/}"}  # leaves a trailing /; empty if no leading path
    [ -h "$app_path" ]
do
    ls=$( ls -ld "$app_path" )
    link=${ls#*' -> '}
    case $link in             #(
      /*)   app_path=$link ;; #(
      *)    app_path=$APP_HOME$link ;;
    esac
done

# This is normally unused
# shellcheck disable=SC2034
APP_BASE_NAME=${0##*/}
# Discard cd standard output in case $CDPATH is set (https://github.com/gradle/gradle/issues/25036)
APP_HOME=$( cd -P "${APP_HOME:-./}" > /dev/null && printf '%s\n' "$PWD" ) || exit

# Use the maximum available, or set MAX_FD != -1 to use that value.
MAX_FD=maximum

warn () {
    echo "$*"
} >&2

die () {
    echo
    echo "$*"
    echo
    exit 1
} >&2

# OS specific support (must be 'true' or 'false').
cygwin=false
msys=false
darwin=false
nonstop=false
case "$( uname )" in                #(
  CYGWIN* )         cygwin=true  ;; #(
  Darwin* )         darwin=true  ;; #(
  MSYS* | MINGW* )  msys=true    ;; #(
  NONSTOP* )        nonstop=true ;;
esac

CLASSPATH="\\\"\\\""


# Determine the Java command to use to start the JVM.
if [ -n "$JAVA_HOME" ] ; then
    if [ -x "$JAVA_HOME/jre/sh/java" ] ; then
        # IBM's JDK on AIX uses strange locations for the executables
        JAVACMD=$JAVA_HOME/jre/sh/java
    else
        JAVACMD=$JAVA_HOME/bin/java
    fi
    if [ ! -x "$JAVACMD" ] ; then
        die "ERROR: JAVA_HOME is set to an invalid directory: $JAVA_HOME

Please set the JAVA_HOME variable in your environment to match the
location of your Java installation."
    fi
else
    JAVACMD=java
    if ! command -v java >/dev/null 2>&1
    then
        die "ERROR: JAVA_HOME is not set and no 'java' command could be found in your PATH.

Please set the JAVA_HOME variable in your environment to match the
location of your Java installation."
    fi
fi

# Increase the maximum file descriptors if we can.
if ! "$cygwin" && ! "$darwin" && ! "$nonstop" ; then
    case $MAX_FD in #(
      max*)
        # In POSIX sh, ulimit -H is undefined. That's why the result is checked to see if it worked.
        # shellcheck disable=SC2039,SC3045
        MAX_FD=$( ulimit -H -n ) ||
            warn "Could not query maximum file descriptor limit"
    esac
    case $MAX_FD in  #(
      '' | soft) :;; #(
      *)
        # In POSIX sh, ulimit -n is undefined. That's why the result is checked to see if it worked.
        # shellcheck disable=SC2039,SC3045
        ulimit -n "$MAX_FD" ||
            warn "Could not set maximum file descriptor limit to $MAX_FD"
    esac
fi

# Collect all arguments for the java command, stacking in reverse order:
#   * args from the command line
#   * the main class name
#   * -classpath
#   * -D...appname settings
#   * --module-path (only if needed)
#   * DEFAULT_JVM_OPTS, JAVA_OPTS, and GRADLE_OPTS environment variables.

# For Cygwin or MSYS, switch paths to Windows format before running java
if "$cygwin" || "$msys" ; then
    APP_HOME=$( cygpath --path --mixed "$APP_HOME" )
    CLASSPATH=$( cygpath --path --mixed "$CLASSPATH" )

    JAVACMD=$( cygpath --unix "$JAVACMD" )

    # Now convert the arguments - kludge to limit ourselves to /bin/sh
    for arg do
        if
            case $arg in                                #(
              -*)   false ;;                            # don't mess with options #(
              /?*)  t=${arg#/} t=/${t%%/*}              # looks like a POSIX filepath
                    [ -e "$t" ] ;;                      #(
              *)    false ;;
            esac
        then
            arg=$( cygpath --path --ignore --mixed "$arg" )
        fi
        # Roll the args list around exactly as many times as the number of
        # args, so each arg winds up back in the position where it started, but
        # possibly modified.
        #
        # NB: a `for` loop captures its iteration list before it begins, so
        # changing the positional parameters here affects neither the number of
        # iterations, nor the values presented in `arg`.
        shift                   # remove old arg
        set -- "$@" "$arg"      # push replacement arg
    done
fi


# Add default JVM options here. You can also use JAVA_OPTS and GRADLE_OPTS to pass JVM options to this script.
DEFAULT_JVM_OPTS='"-Xmx64m" "-Xms64m"'

# Collect all arguments for the java command:
#   * DEFAULT_JVM_OPTS, JAVA_OPTS, JAVA_OPTS, and optsEnvironmentVar are not allowed to contain shell fragments,
#     and any embedded shellness will be escaped.
#   * For example: A user cannot expect ${Hostname} to be expanded, as it is an environment variable and will be
#     treated as '${Hostname}' itself on the command line.

set -- \
        "-Dorg.gradle.appname=$APP_BASE_NAME" \
        -classpath "$CLASSPATH" \
        -jar "$APP_HOME/gradle/wrapper/gradle-wrapper.jar" \
        "$@"

# Stop when "xargs" is not available.
if ! command -v xargs >/dev/null 2>&1
then
    die "xargs is not available"
fi

# Use "xargs" to parse quoted args.
#
# With -n1 it outputs one arg per line, with the quotes and backslashes removed.
#
# In Bash we could simply go:
#
#   readarray ARGS < <( xargs -n1 <<<"$var" ) &&
#   set -- "${ARGS[@]}" "$@"
#
# but POSIX shell has neither arrays nor command substitution, so instead we
# post-process each arg (as a line of input to sed) to backslash-escape any
# character that might be a shell metacharacter, then use eval to reverse
# that process (while maintaining the separation between arguments), and wrap
# the whole thing up as a single "set" statement.
#
# This will of course break if any of these variables contains a newline or
# an unmatched quote.
#

eval "set -- $(
        printf '%s\n' "$DEFAULT_JVM_OPTS $JAVA_OPTS $GRADLE_OPTS" |
        xargs -n1 |
        sed ' s~[^-[:alnum:]+,./:=@_]~\\&~g; ' |
        tr '\n' ' '
    )" '"$@"'

exec "$JAVACMD" "$@"
~~~

## `mobile/android/gradlew.bat`

- 编码: `utf-8`

~~~
@rem
@rem Copyright 2015 the original author or authors.
@rem
@rem Licensed under the Apache License, Version 2.0 (the "License");
@rem you may not use this file except in compliance with the License.
@rem You may obtain a copy of the License at
@rem
@rem      https://www.apache.org/licenses/LICENSE-2.0
@rem
@rem Unless required by applicable law or agreed to in writing, software
@rem distributed under the License is distributed on an "AS IS" BASIS,
@rem WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
@rem See the License for the specific language governing permissions and
@rem limitations under the License.
@rem
@rem SPDX-License-Identifier: Apache-2.0
@rem

@if "%DEBUG%"=="" @echo off
@rem ##########################################################################
@rem
@rem  Gradle startup script for Windows
@rem
@rem ##########################################################################

@rem Set local scope for the variables with windows NT shell
if "%OS%"=="Windows_NT" setlocal

set DIRNAME=%~dp0
if "%DIRNAME%"=="" set DIRNAME=.
@rem This is normally unused
set APP_BASE_NAME=%~n0
set APP_HOME=%DIRNAME%

@rem Resolve any "." and ".." in APP_HOME to make it shorter.
for %%i in ("%APP_HOME%") do set APP_HOME=%%~fi

@rem Add default JVM options here. You can also use JAVA_OPTS and GRADLE_OPTS to pass JVM options to this script.
set DEFAULT_JVM_OPTS="-Xmx64m" "-Xms64m"

@rem Find java.exe
if defined JAVA_HOME goto findJavaFromJavaHome

set JAVA_EXE=java.exe
%JAVA_EXE% -version >NUL 2>&1
if %ERRORLEVEL% equ 0 goto execute

echo. 1>&2
echo ERROR: JAVA_HOME is not set and no 'java' command could be found in your PATH. 1>&2
echo. 1>&2
echo Please set the JAVA_HOME variable in your environment to match the 1>&2
echo location of your Java installation. 1>&2

goto fail

:findJavaFromJavaHome
set JAVA_HOME=%JAVA_HOME:"=%
set JAVA_EXE=%JAVA_HOME%/bin/java.exe

if exist "%JAVA_EXE%" goto execute

echo. 1>&2
echo ERROR: JAVA_HOME is set to an invalid directory: %JAVA_HOME% 1>&2
echo. 1>&2
echo Please set the JAVA_HOME variable in your environment to match the 1>&2
echo location of your Java installation. 1>&2

goto fail

:execute
@rem Setup the command line

set CLASSPATH=


@rem Execute Gradle
"%JAVA_EXE%" %DEFAULT_JVM_OPTS% %JAVA_OPTS% %GRADLE_OPTS% "-Dorg.gradle.appname=%APP_BASE_NAME%" -classpath "%CLASSPATH%" -jar "%APP_HOME%\gradle\wrapper\gradle-wrapper.jar" %*

:end
@rem End local scope for the variables with windows NT shell
if %ERRORLEVEL% equ 0 goto mainEnd

:fail
rem Set variable GRADLE_EXIT_CONSOLE if you need the _script_ return code instead of
rem the _cmd.exe /c_ return code!
set EXIT_CODE=%ERRORLEVEL%
if %EXIT_CODE% equ 0 set EXIT_CODE=1
if not ""=="%GRADLE_EXIT_CONSOLE%" exit %EXIT_CODE%
exit /b %EXIT_CODE%

:mainEnd
if "%OS%"=="Windows_NT" endlocal

:omega
~~~

## `mobile/android/settings.gradle`

- 编码: `utf-8`

~~~gradle
pluginManagement {
  def reactNativeGradlePlugin = new File(
    providers.exec {
      workingDir(rootDir)
      commandLine("node", "--print", "require.resolve('@react-native/gradle-plugin/package.json', { paths: [require.resolve('react-native/package.json')] })")
    }.standardOutput.asText.get().trim()
  ).getParentFile().absolutePath
  includeBuild(reactNativeGradlePlugin)
  
  def expoPluginsPath = new File(
    providers.exec {
      workingDir(rootDir)
      commandLine("node", "--print", "require.resolve('expo-modules-autolinking/package.json', { paths: [require.resolve('expo/package.json')] })")
    }.standardOutput.asText.get().trim(),
    "../android/expo-gradle-plugin"
  ).absolutePath
  includeBuild(expoPluginsPath)
}

plugins {
  id("com.facebook.react.settings")
  id("expo-autolinking-settings")
}

extensions.configure(com.facebook.react.ReactSettingsExtension) { ex ->
  if (System.getenv('EXPO_USE_COMMUNITY_AUTOLINKING') == '1') {
    ex.autolinkLibrariesFromCommand()
  } else {
    ex.autolinkLibrariesFromCommand(expoAutolinking.rnConfigCommand)
  }
}
expoAutolinking.useExpoModules()

rootProject.name = '益语智库'

expoAutolinking.useExpoVersionCatalog()

include ':app'
includeBuild(expoAutolinking.reactNativeGradlePlugin)
~~~

## `mobile/app.json`

- 编码: `utf-8`

~~~json
{
  "expo": {
    "name": "益语智库",
    "slug": "yiyu-mobile",
    "version": "1.0.0",
    "orientation": "portrait",
    "icon": "./assets/icon.png",
    "userInterfaceStyle": "light",
    "scheme": "yiyu",
    "splash": {
      "image": "./assets/splash-icon.png",
      "resizeMode": "contain",
      "backgroundColor": "#1E3A5F"
    },
    "ios": {
      "supportsTablet": true,
      "bundleIdentifier": "com.yiyu.mobile",
      "infoPlist": {
        "NSAppTransportSecurity": {
          "NSAllowsArbitraryLoads": true
        }
      }
    },
    "android": {
      "package": "com.yiyu.mobile",
      "permissions": [
        "android.permission.RECORD_AUDIO",
        "android.permission.MODIFY_AUDIO_SETTINGS",
        "android.permission.POST_NOTIFICATIONS",
        "android.permission.FOREGROUND_SERVICE",
        "android.permission.FOREGROUND_SERVICE_MICROPHONE"
      ],
      "adaptiveIcon": {
        "backgroundColor": "#1E3A5F",
        "foregroundImage": "./assets/android-icon-foreground.png",
        "backgroundImage": "./assets/android-icon-background.png",
        "monochromeImage": "./assets/android-icon-monochrome.png"
      }
    },
    "plugins": [
      "expo-router",
      "expo-secure-store",
      [
        "expo-audio",
        {
          "enableBackgroundRecording": true,
          "enableBackgroundPlayback": false
        }
      ],
      [
        "expo-speech-recognition",
        {
          "microphonePermission": "允许益语智库使用麦克风。",
          "speechRecognitionPermission": "允许益语智库使用语音识别。",
          "androidSpeechServicePackages": [
            "com.google.android.googlequicksearchbox",
            "com.google.android.as"
          ]
        }
      ],
      "expo-asset"
    ],
    "platforms": [
      "ios",
      "android",
      "web"
    ],
    "extra": {
      "router": {}
    }
  }
}
~~~

## `mobile/app/(tabs)/_layout.tsx`

- 编码: `utf-8`

~~~tsx
import { View, TouchableOpacity, StyleSheet, Text } from "react-native";
import { Tabs } from "expo-router";
import { ListTodo, Calendar, MessageSquare, User } from "lucide-react-native";
import { colors } from "../../lib/theme";
import { useAppChromeInsets } from "../../lib/app-chrome";
import SuperFAB from "../../components/SuperFAB";

export default function TabLayout() {
  const chrome = useAppChromeInsets();

  return (
    <>
      <Tabs
        screenOptions={{
          tabBarActiveTintColor: colors.brand,
          tabBarInactiveTintColor: colors.textTertiary,
          tabBarLabelStyle: { fontSize: 9, fontWeight: "600" },
          tabBarStyle: {
            backgroundColor: "rgba(255,255,255,0.98)",
            borderTopColor: colors.borderLight,
            borderTopWidth: StyleSheet.hairlineWidth,
            height: chrome.tabBarHeight,
            paddingBottom: chrome.tabBarPaddingBottom,
            paddingTop: chrome.tabBarPaddingTop,
          },
          headerShown: false,
        }}
        tabBar={(props) => <CustomTabBar {...props} />}
      >
        <Tabs.Screen name="tasks" options={{ title: "任务" }} />
        <Tabs.Screen name="calendar" options={{ title: "日历" }} />
        <Tabs.Screen name="consult" options={{ title: "咨询" }} />
        <Tabs.Screen name="profile" options={{ title: "我的" }} />
      </Tabs>
    </>
  );
}

const TAB_ICONS = {
  tasks: ListTodo,
  calendar: Calendar,
  consult: MessageSquare,
  profile: User,
} as const;

const TAB_LABELS: Record<string, string> = {
  tasks: "任务",
  calendar: "日历",
  consult: "咨询",
  profile: "我的",
};

function CustomTabBar({ state, navigation }: { state: any; navigation: any }) {
  const chrome = useAppChromeInsets();
  const leftTabs = state.routes.slice(0, 2);  // 任务, 日历
  const rightTabs = state.routes.slice(2, 4); // 咨询, 我的

  const renderTab = (route: { name: string; key: string }, index: number) => {
    const routeName = route.name as keyof typeof TAB_ICONS;
    const Icon = TAB_ICONS[routeName];
    const label = TAB_LABELS[routeName] ?? routeName;
    const isFocused = state.routes[state.index].name === routeName;

    const onPress = () => {
      const event = navigation.emit({ type: "tabPress", target: route.key, canPreventDefault: true });
      if (!isFocused && !event.defaultPrevented) {
        navigation.navigate(route.name);
      }
    };

    return (
      <TouchableOpacity key={route.key} style={s.tab} onPress={onPress} activeOpacity={0.7}>
        {Icon && <Icon size={24} strokeWidth={1.95} color={isFocused ? colors.brand : colors.textTertiary} />}
        <Text style={[s.tabLabel, isFocused && s.tabLabelActive]}>{label}</Text>
      </TouchableOpacity>
    );
  };

  return (
    <View style={[s.tabBarContainer, { height: chrome.tabBarHeight, paddingBottom: chrome.tabBarPaddingBottom, paddingTop: chrome.tabBarPaddingTop }]}>
      {/* Left tabs */}
      {leftTabs.map(renderTab)}

      {/* Center FAB - embedded in tab bar, protruding up */}
      <View style={s.fabWrapper}>
        <SuperFAB
          onCreateTask={() => {
            navigation.navigate("tasks", { modal: "create", trigger: String(Date.now()) });
          }}
          onSmartInput={() => {
            navigation.navigate("tasks", { modal: "smart", trigger: String(Date.now()) });
          }}
        />
      </View>

      {/* Right tabs */}
      {rightTabs.map(renderTab)}
    </View>
  );
}

const s = StyleSheet.create({
  tabBarContainer: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-around",
    backgroundColor: "#FFFFFF",
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.borderLight,
    shadowColor: "#111827",
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.04,
    shadowRadius: 18,
    elevation: 8,
  },
  tab: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 2,
  },
  tabLabel: {
    fontSize: 9,
    fontWeight: "600",
    color: colors.textTertiary,
  },
  tabLabelActive: {
    color: colors.brand,
  },
  fabWrapper: {
    width: 92,
    alignItems: "center",
    marginTop: -30,
  },
});
~~~

## `mobile/app/(tabs)/calendar.tsx`

- 编码: `utf-8`

~~~tsx
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Animated,
  GestureResponderEvent,
  Modal,
  PanResponder,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import * as Haptics from "expo-haptics";
import { useRouter } from "expo-router";
import { useAppChromeInsets } from "../../lib/app-chrome";
import * as localDb from "../../lib/local-db";
import { colors, fontSize, spacing, borderRadius, shadow } from "../../lib/theme";
import { useAndroidBackToTasks } from "../../lib/android-back";
import type { TaskRecord, SmartTaskDraft } from "../../lib/types";
import CalendarHeader from "../../components/calendar-screen/CalendarHeader";
import MonthView from "../../components/calendar-screen/MonthView";
import WeekView from "../../components/calendar-screen/WeekView";
import DayView from "../../components/calendar-screen/DayView";
import CalendarDragLayer from "../../components/calendar-screen/CalendarDragLayer";
import CalendarModalCoordinator from "../../components/calendar-screen/CalendarModalCoordinator";
import EventLineDrawer from "../../components/EventLineDrawer";
import WorkspaceLiteSheet from "../../components/WorkspaceLiteSheet";
import WeekSignalCard from "../../components/WeekSignalCard";
import FocusBar from "../../components/FocusBar";
import { useTaskBoard } from "../../lib/task-board-store";
import { useRenderCount } from "../../lib/use-render-count";
import {
  resizeCalendarTaskDuration,
  updateCalendarTaskSchedule,
} from "../../lib/calendar-repository";
import { deleteTaskOfflineFirst, updateTaskOfflineFirst } from "../../lib/sync-engine";
import { useCurrentFocus } from "../../lib/current-focus-store";
import { useClientIntel } from "../../lib/client-intel-store";
import { transferEventLineToClient } from "../../lib/event-line-client-transfer";
import { buildWeekSignalSnapshot } from "../../lib/week-signal";
import { getLocalWeekAnchorDateKey, weekLabelForDateKey } from "../../lib/date";
import {
  buildMonthCalendarDays,
  getAllDayTasksForDate,
  getScheduledTasksForDate,
  getTasksForDate,
  groupTasksByDate,
} from "../../lib/calendar-selectors";
import {
  buildFocusMatchedTaskIds,
  filterTasksByFocus,
  isLockedFocus,
} from "../../lib/focus-selectors";

// ─── Constants ─────────────────────────────────

type CalendarView = "day" | "week" | "month";

const VIEW_OPTIONS: { key: CalendarView; label: string }[] = [
  { key: "month", label: "月" },
  { key: "week", label: "周" },
  { key: "day", label: "日" },
];

const WEEKDAY_LABELS = ["日", "一", "二", "三", "四", "五", "六"] as const;
const WEEKDAY_CN = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"] as const;

const HOUR_HEIGHT = 60;
const TIMELINE_START = 0;
const TIMELINE_END = 24;
const DRAG_DOT_SIZE = 40;
const DRAG_DOT_FINGER_OFFSET_Y = 130; // two finger-widths above touch point (touch is on finger pad, not tip)
const DRAG_LONG_PRESS_MS = 250;
const DRAG_CANCEL_DISTANCE = 8;

// ─── Helpers ────────────────────────────────────

function toDateKey(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function formatTime(dateStr: string): string {
  const d = new Date(dateStr);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function getWeekDates(date: Date): Date[] {
  const day = date.getDay();
  const dates: Date[] = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(date);
    d.setDate(date.getDate() - day + i);
    d.setHours(0, 0, 0, 0);
    dates.push(d);
  }
  return dates;
}

function getTaskTopOffset(dueDate: string): number {
  const d = new Date(dueDate);
  return (d.getHours() - TIMELINE_START) * HOUR_HEIGHT + (d.getMinutes() / 60) * HOUR_HEIGHT;
}

function getTaskBlockHeight(durationMinutes: number): number {
  return Math.max((durationMinutes / 60) * HOUR_HEIGHT, 28);
}

function getCurrentTimeOffset(): number {
  const now = new Date();
  return (now.getHours() - TIMELINE_START) * HOUR_HEIGHT + (now.getMinutes() / 60) * HOUR_HEIGHT;
}

// ─── Types ──────────────────────────────────────

interface CalendarDay {
  day: number;
  dateKey: string;
  isCurrentMonth: boolean;
}

interface DropZoneLayout {
  key: string; // dateKey or "hour:HH"
  x: number;
  y: number;
  width: number;
  height: number;
}

function resolveDragDotHoverPoint(pageX: number, pageY: number) {
  return {
    x: pageX,
    y: pageY - DRAG_DOT_FINGER_OFFSET_Y,
  };
}

// ─── Component ──────────────────────────────────

export default function CalendarScreen() {
  useRenderCount("CalendarScreen");
  const chrome = useAppChromeInsets();
  const router = useRouter();
  const now = new Date();

  const [viewMode, setViewMode] = useState<CalendarView>("month");
  const [showViewMenu, setShowViewMenu] = useState(false);
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());
  const [selectedDate, setSelectedDate] = useState(
    new Date(now.getFullYear(), now.getMonth(), now.getDate()),
  );
  const selectedDateKey = toDateKey(selectedDate);

  const { board, isHydrated, refresh } = useTaskBoard();
  const {
    focus,
    clients,
    eventLines,
    setCurrentFocusBrowseFromCalendar,
    setCurrentFocusBrowseFromEventLine,
    setCurrentFocusWeek,
  } = useCurrentFocus();
  const clientIntel = useClientIntel(focus.clientId);
  const tasks = board.tasks;
  const [refreshing, setRefreshing] = useState(false);
  const [resizeDrafts, setResizeDrafts] = useState<Record<string, number>>({});
  const [workspaceClientId, setWorkspaceClientId] = useState<string | null>(null);
  const [eventLineDrawerId, setEventLineDrawerId] = useState<string | null>(null);
  const [transferringEventLineId, setTransferringEventLineId] = useState<string | null>(null);
  const [showAllForFocus, setShowAllForFocus] = useState(false);

  // Modal states
  const [selectedTask, setSelectedTask] = useState<TaskRecord | null>(null);
  const [recordTaskContext, setRecordTaskContext] = useState<TaskRecord | null>(null);
  const [reviewTaskContext, setReviewTaskContext] = useState<TaskRecord | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [showSmartInput, setShowSmartInput] = useState(false);
  const [smartDraft, setSmartDraft] = useState<SmartTaskDraft | null>(null);
  const [createPreset, setCreatePreset] = useState<{ dueDate?: string; dueTime?: string }>({});
  const [smartInputPreset, setSmartInputPreset] = useState<{ dueDate?: string; dueTime?: string }>({});

  // Week view expanded days
  const [expandedWeekDay, setExpandedWeekDay] = useState<string | null>(null);

  const timelineRef = useRef<ScrollView>(null);
  const [currentTimeOffset, setCurrentTimeOffset] = useState(getCurrentTimeOffset());

  // ─── Drag system ─────────────────────────────

  const [draggingTask, setDraggingTask] = useState<TaskRecord | null>(null);
  const [hoveredDropKey, setHoveredDropKey] = useState<string | null>(null);
  const dragTranslate = useRef(new Animated.ValueXY({ x: 0, y: 0 })).current;
  const dragOpacity = useRef(new Animated.Value(0)).current;
  const dragScale = useRef(new Animated.Value(0.9)).current;
  const containerRef = useRef<View>(null);
  const containerOffsetRef = useRef({ x: 0, y: 0 });
  const dropZonesRef = useRef<DropZoneLayout[]>([]);
  const dragPointRef = useRef({ x: 0, y: 0 });
  const resizingTaskRef = useRef<{ taskId: string; startHeight: number; startDuration: number } | null>(null);
  const resizeDurationRef = useRef<Record<string, number>>({});
  const pendingTaskPressRef = useRef<{
    taskId: string | null;
    startX: number;
    startY: number;
    longPressed: boolean;
    timer: ReturnType<typeof setTimeout> | null;
  }>({
    taskId: null,
    startX: 0,
    startY: 0,
    longPressed: false,
    timer: null,
  });
  const suppressTaskPressRef = useRef(false);

  const measureContainer = useCallback(() => {
    (containerRef.current as any)?.measureInWindow?.((x: number, y: number) => {
      containerOffsetRef.current = { x, y };
    });
  }, []);

  const registerDropZone = useCallback((key: string, ref: View | null) => {
    if (!ref) return;
    ref.measureInWindow((x, y, width, height) => {
      if (width <= 0) return;
      const existing = dropZonesRef.current.findIndex((z) => z.key === key);
      const zone: DropZoneLayout = { key, x, y, width, height };
      if (existing >= 0) dropZonesRef.current[existing] = zone;
      else dropZonesRef.current.push(zone);
    });
  }, []);

  const measureAllDropZones = useCallback(() => {
    // Re-measure after a small delay to allow layout
    requestAnimationFrame(() => {
      dropZonesRef.current.forEach((zone) => {
        // zones already measured during render via ref callback
      });
    });
  }, []);

  const findHoveredZone = useCallback((pageX: number, pageY: number): string | null => {
    for (const zone of dropZonesRef.current) {
      if (
        pageX >= zone.x && pageX <= zone.x + zone.width &&
        pageY >= zone.y && pageY <= zone.y + zone.height
      ) {
        return zone.key;
      }
    }
    return null;
  }, []);

  const clearPendingTaskPress = useCallback(() => {
    const pending = pendingTaskPressRef.current;
    if (pending.timer) clearTimeout(pending.timer);
    pendingTaskPressRef.current = {
      taskId: null,
      startX: 0,
      startY: 0,
      longPressed: false,
      timer: null,
    };
  }, []);

  const beginDrag = useCallback((task: TaskRecord, pageX: number, pageY: number) => {
    dropZonesRef.current = [];
    measureContainer();
    measureAllDropZones();
    setDraggingTask(task);
    setHoveredDropKey(null);
    const co = containerOffsetRef.current;
    dragTranslate.setValue({
      x: pageX - DRAG_DOT_SIZE / 2 - co.x,
      y: pageY - DRAG_DOT_SIZE / 2 - DRAG_DOT_FINGER_OFFSET_Y - co.y,
    });
    dragOpacity.setValue(0);
    dragScale.setValue(0.9);
    Animated.parallel([
      Animated.spring(dragScale, { toValue: 1, useNativeDriver: true, speed: 20, bounciness: 6 }),
      Animated.timing(dragOpacity, { toValue: 1, duration: 140, useNativeDriver: true }),
    ]).start();
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
  }, [dragOpacity, dragScale, dragTranslate, measureAllDropZones, measureContainer]);

  const updateDrag = useCallback((pageX: number, pageY: number) => {
    const co = containerOffsetRef.current;
    dragTranslate.setValue({
      x: pageX - DRAG_DOT_SIZE / 2 - co.x,
      y: pageY - DRAG_DOT_SIZE / 2 - DRAG_DOT_FINGER_OFFSET_Y - co.y,
    });
    const hoverPoint = resolveDragDotHoverPoint(pageX, pageY);
    dragPointRef.current = hoverPoint;
    const hovered = findHoveredZone(hoverPoint.x, hoverPoint.y);
    if (hovered !== hoveredDropKey) {
      setHoveredDropKey(hovered);
      if (hovered) void Haptics.selectionAsync();
    }
  }, [dragTranslate, findHoveredZone, hoveredDropKey]);

  const endDrag = useCallback(async () => {
    const task = draggingTask;
    const targetKey = hoveredDropKey;

    const cleanup = () => {
      setDraggingTask(null);
      setHoveredDropKey(null);
    };

    if (!task || !targetKey) {
      Animated.parallel([
        Animated.timing(dragOpacity, { toValue: 0, duration: 120, useNativeDriver: true }),
        Animated.timing(dragScale, { toValue: 0.8, duration: 120, useNativeDriver: true }),
      ]).start(cleanup);
      return;
    }

    // Determine new dueDate based on target key
    let newDueDate: string;
    if (targetKey.startsWith("hour:")) {
      // Day view: drop on hour slot → keep same date, change time
      const hour = parseInt(targetKey.slice(5), 10);
      const timeStr = `${String(hour).padStart(2, "0")}:00`;
      newDueDate = `${selectedDateKey}T${timeStr}`;
    } else {
      // Date key: keep existing time if any
      const existingTime = task.dueDate?.includes("T") ? task.dueDate.slice(10) : "";
      newDueDate = targetKey + existingTime;
      const [y, m, d] = targetKey.split("-").map(Number);
      setSelectedDate(new Date(y, m - 1, d));
      setYear(y);
      setMonth(m - 1);
    }

    cleanup();
    void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    try {
      const nextTask = await updateCalendarTaskSchedule(task.id, { dueDate: newDueDate });
      setSelectedTask((current) => (current?.id === nextTask.id ? nextTask : current));
    } catch {
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      Alert.alert("改期失败", "请检查网络或同步状态后重试。");
      void refresh();
    }
    Animated.parallel([
      Animated.timing(dragOpacity, { toValue: 0, duration: 150, useNativeDriver: true }),
      Animated.timing(dragScale, { toValue: 0.85, duration: 150, useNativeDriver: true }),
    ]).start();
  }, [draggingTask, hoveredDropKey, selectedDateKey, dragOpacity, dragScale, refresh]);

  const dragResponder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => !!draggingTask,
        onStartShouldSetPanResponderCapture: () => !!draggingTask,
        onMoveShouldSetPanResponder: () => !!draggingTask,
        onMoveShouldSetPanResponderCapture: () => !!draggingTask,
        onPanResponderMove: (event) => {
          if (!draggingTask) return;
          const { pageX, pageY } = event.nativeEvent;
          updateDrag(pageX, pageY);
        },
        onPanResponderRelease: () => {
          if (!draggingTask) return;
          void endDrag();
        },
        onPanResponderTerminate: () => {
          if (!draggingTask) return;
          void endDrag();
        },
      }),
    [draggingTask, endDrag, updateDrag],
  );

  const handleTaskTouchStart = useCallback((task: TaskRecord, event: GestureResponderEvent) => {
    if (draggingTask) return;
    clearPendingTaskPress();
    const { pageX, pageY } = event.nativeEvent;
    const timer = setTimeout(() => {
      pendingTaskPressRef.current.longPressed = true;
      suppressTaskPressRef.current = true;
      beginDrag(task, pageX, pageY);
    }, DRAG_LONG_PRESS_MS);
    pendingTaskPressRef.current = {
      taskId: task.id,
      startX: pageX,
      startY: pageY,
      longPressed: false,
      timer,
    };
  }, [beginDrag, clearPendingTaskPress, draggingTask]);

  const handleTaskTouchMove = useCallback((event: GestureResponderEvent) => {
    const pending = pendingTaskPressRef.current;
    if (!pending.taskId) return;
    const { pageX, pageY } = event.nativeEvent;
    if (!pending.longPressed) {
      // Cancel long-press if finger moves too far before timer fires
      if (
        Math.abs(pageX - pending.startX) > DRAG_CANCEL_DISTANCE ||
        Math.abs(pageY - pending.startY) > DRAG_CANCEL_DISTANCE
      ) {
        clearPendingTaskPress();
      }
      return;
    }
    // Once dragging, root onTouchMove handles updates — no need to duplicate
  }, [clearPendingTaskPress]);

  const handleTaskTouchEnd = useCallback(() => {
    const pending = pendingTaskPressRef.current;
    clearPendingTaskPress();
    // Once dragging, root onTouchEnd handles endDrag — no need to duplicate
  }, [clearPendingTaskPress]);

  // ─── Android back ────────────────────────────

  useAndroidBackToTasks(
    useCallback(() => {
      if (draggingTask) { setDraggingTask(null); setHoveredDropKey(null); return true; }
      if (eventLineDrawerId) { setEventLineDrawerId(null); return true; }
      if (workspaceClientId) { setWorkspaceClientId(null); return true; }
      if (reviewTaskContext) { setReviewTaskContext(null); return true; }
      if (recordTaskContext) { setRecordTaskContext(null); return true; }
      if (showCreate) { setShowCreate(false); return true; }
      if (showSmartInput) { setShowSmartInput(false); return true; }
      if (selectedTask) { setSelectedTask(null); return true; }
      if (showViewMenu) { setShowViewMenu(false); return true; }
      return false;
    }, [draggingTask, eventLineDrawerId, recordTaskContext, reviewTaskContext, selectedTask, showCreate, showSmartInput, showViewMenu, workspaceClientId]),
  );

  // ─── Data loading ────────────────────────────

  const loadTasks = useCallback(async () => {
    setRefreshing(true);
    try {
      await refresh();
    } finally {
      setRefreshing(false);
    }
  }, [refresh]);

  useEffect(() => {
    setCurrentFocusWeek(getLocalWeekAnchorDateKey(selectedDate));
  }, [selectedDate, setCurrentFocusWeek]);

  useEffect(() => {
    setShowAllForFocus(false);
  }, [focus.clientId, focus.eventLineId, focus.lockMode]);

  // Update current time line every minute
  useEffect(() => {
    if (viewMode !== "day") return;
    const timer = setInterval(() => setCurrentTimeOffset(getCurrentTimeOffset()), 60000);
    return () => clearInterval(timer);
  }, [viewMode]);

  // Auto-scroll timeline to current time
  useEffect(() => {
    if (viewMode !== "day") return;
    const offset = getCurrentTimeOffset() - 200;
    requestAnimationFrame(() => {
      timelineRef.current?.scrollTo({ y: Math.max(0, offset), animated: false });
    });
  }, [viewMode, selectedDateKey]);

  // ─── Task grouping ──────────────────────────

  const focusLocked = useMemo(() => isLockedFocus(focus), [focus]);
  const effectiveTasks = useMemo(
    () => (focusLocked && !showAllForFocus ? filterTasksByFocus(tasks, focus) : tasks),
    [focus, focusLocked, showAllForFocus, tasks],
  );
  const focusMatchedTaskIds = useMemo(
    () => buildFocusMatchedTaskIds(tasks, focus),
    [focus, tasks],
  );
  const tasksByDate = useMemo(() => groupTasksByDate(effectiveTasks), [effectiveTasks]);

  const dayScheduledTasks = useMemo(() => {
    return getScheduledTasksForDate(tasksByDate, selectedDateKey);
  }, [tasksByDate, selectedDateKey]);

  const dayAllDayTasks = useMemo(() => {
    return getAllDayTasksForDate(tasksByDate, selectedDateKey);
  }, [tasksByDate, selectedDateKey]);

  const selectedTasks = useMemo(
    () => getTasksForDate(tasksByDate, selectedDateKey),
    [tasksByDate, selectedDateKey],
  );

  const weekDates = useMemo(() => getWeekDates(selectedDate), [selectedDate]);
  const weekSignal = useMemo(
    () => buildWeekSignalSnapshot({
      tasks: effectiveTasks,
      weekAnchorDate: getLocalWeekAnchorDateKey(selectedDate),
      workspaceLite: clientIntel.snapshot,
      eventLine: eventLines.find((item) => item.id === focus.eventLineId) ?? null,
      allowJudgmentOverlay: focusLocked && !showAllForFocus,
    }),
    [clientIntel.snapshot, effectiveTasks, eventLines, focus.eventLineId, focusLocked, selectedDate, showAllForFocus],
  );
  const selectedTaskEventLine = useMemo(
    () => eventLines.find((item) => item.id === selectedTask?.eventLineId) ?? null,
    [eventLines, selectedTask?.eventLineId],
  );
  const drawerEventLine = useMemo(
    () => eventLines.find((item) => item.id === eventLineDrawerId) ?? null,
    [eventLineDrawerId, eventLines],
  );
  const handleTransferDrawerEventLine = useCallback(async (clientId: string) => {
    if (!drawerEventLine) {
      return;
    }
    const targetClient = clients.find((item) => item.id === clientId);
    if (!targetClient) {
      Alert.alert("迁移失败", "目标客户不存在，请刷新后重试。");
      return;
    }
    setTransferringEventLineId(drawerEventLine.id);
    try {
      await transferEventLineToClient(drawerEventLine.id, clientId);
      Alert.alert("已更新归属", `已把「${drawerEventLine.name}」转到客户「${targetClient.name}」下。`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "请检查网络连接后重试。";
      Alert.alert("迁移失败", message);
    } finally {
      setTransferringEventLineId(null);
    }
  }, [clients, drawerEventLine]);

  // ─── Calendar grid (month view) ─────────────

  const calendarDays = useMemo((): readonly CalendarDay[] => buildMonthCalendarDays(year, month), [year, month]);

  const todayKey = toDateKey(now);

  // ─── Navigation ─────────────────────────────

  const goToPrevMonth = useCallback(() => {
    if (month === 0) { setYear((y) => y - 1); setMonth(11); }
    else setMonth((m) => m - 1);
  }, [month]);

  const goToNextMonth = useCallback(() => {
    if (month === 11) { setYear((y) => y + 1); setMonth(0); }
    else setMonth((m) => m + 1);
  }, [month]);

  const goToPrevWeek = useCallback(() => {
    setSelectedDate((d) => {
      const n = new Date(d);
      n.setDate(n.getDate() - 7);
      setYear(n.getFullYear());
      setMonth(n.getMonth());
      return n;
    });
  }, []);

  const goToNextWeek = useCallback(() => {
    setSelectedDate((d) => {
      const n = new Date(d);
      n.setDate(n.getDate() + 7);
      setYear(n.getFullYear());
      setMonth(n.getMonth());
      return n;
    });
  }, []);

  const goToPrevDay = useCallback(() => {
    setSelectedDate((d) => {
      const n = new Date(d);
      n.setDate(n.getDate() - 1);
      setYear(n.getFullYear());
      setMonth(n.getMonth());
      return n;
    });
  }, []);

  const goToNextDay = useCallback(() => {
    setSelectedDate((d) => {
      const n = new Date(d);
      n.setDate(n.getDate() + 1);
      setYear(n.getFullYear());
      setMonth(n.getMonth());
      return n;
    });
  }, []);

  const selectDate = useCallback((dateKey: string, switchView?: CalendarView) => {
    const [y, m, d] = dateKey.split("-").map(Number);
    setSelectedDate(new Date(y, m - 1, d));
    setYear(y);
    setMonth(m - 1);
    if (switchView) setViewMode(switchView);
  }, []);

  // ─── Timeline interactions ──────────────────

  const handleTimelineSlotPress = useCallback((hour: number) => {
    if (draggingTask) return;
    setSmartDraft(null);
    setCreatePreset({ dueDate: selectedDateKey, dueTime: `${String(hour).padStart(2, "0")}:00` });
    setShowCreate(true);
  }, [selectedDateKey, draggingTask]);

  const handleTimelineSlotLongPress = useCallback((hour: number) => {
    if (draggingTask) return;
    setSmartInputPreset({ dueDate: selectedDateKey, dueTime: `${String(hour).padStart(2, "0")}:00` });
    setShowSmartInput(true);
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
  }, [selectedDateKey, draggingTask]);

  const applySmartDraft = useCallback((draft: SmartTaskDraft) => {
    const mergedDraft: SmartTaskDraft = {
      ...draft,
      dueDate: draft.dueDate ?? smartInputPreset.dueDate ?? null,
      dueTime: draft.dueTime ?? smartInputPreset.dueTime ?? null,
    };
    setShowSmartInput(false);
    setSmartInputPreset({});
    setSmartDraft(mergedDraft);
    setCreatePreset({
      dueDate: mergedDraft.dueDate ?? undefined,
      dueTime: mergedDraft.dueTime ?? undefined,
    });
    setShowCreate(true);
  }, [smartInputPreset.dueDate, smartInputPreset.dueTime]);

  const applyTaskUpdates = useCallback(async (taskId: string, updates: Partial<TaskRecord>) => {
    const isScheduleUpdate = Object.prototype.hasOwnProperty.call(updates, "dueDate")
      || Object.prototype.hasOwnProperty.call(updates, "durationMinutes");

    let nextTask: TaskRecord | null = null;
    if (isScheduleUpdate) {
      nextTask = await updateCalendarTaskSchedule(taskId, {
        dueDate: updates.dueDate,
        durationMinutes: updates.durationMinutes,
      });
    } else {
      updateTaskOfflineFirst(taskId, updates);
      nextTask = localDb.getTaskById(taskId);
    }

    setSelectedTask((current) => (
      current?.id === taskId
        ? nextTask ?? localDb.getTaskById(taskId) ?? { ...current, ...updates }
        : current
    ));
    void refresh();
    return nextTask;
  }, [refresh]);

  const dayScheduledTasksForView = useMemo(
    () => dayScheduledTasks.map((task) => (
      resizeDrafts[task.id] == null ? task : { ...task, durationMinutes: resizeDrafts[task.id] }
    )),
    [dayScheduledTasks, resizeDrafts],
  );

  const handleTaskPress = useCallback((task: TaskRecord) => {
    if (suppressTaskPressRef.current) {
      suppressTaskPressRef.current = false;
      return;
    }
    if (!draggingTask) {
      setCurrentFocusBrowseFromCalendar(task);
      setSelectedTask(task);
    }
  }, [draggingTask, setCurrentFocusBrowseFromCalendar]);

  const shouldSetTaskResponder = useCallback((task: TaskRecord) => {
    return Boolean(draggingTask) || pendingTaskPressRef.current.taskId === task.id;
  }, [draggingTask]);

  const handleResizeGrant = useCallback((task: TaskRecord, height: number) => {
    resizingTaskRef.current = {
      taskId: task.id,
      startHeight: height,
      startDuration: task.durationMinutes || 60,
    };
    resizeDurationRef.current[task.id] = task.durationMinutes || 60;
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
  }, []);

  const handleResizeMove = useCallback((pageY: number, top: number) => {
    const meta = resizingTaskRef.current;
    if (!meta) return;
    const deltaY = pageY - (top + meta.startHeight + containerOffsetRef.current.y);
    const newDuration = Math.max(30, Math.round((meta.startDuration + (deltaY / HOUR_HEIGHT) * 60) / 15) * 15);
    resizeDurationRef.current[meta.taskId] = newDuration;
    setResizeDrafts((prev) => (
      prev[meta.taskId] === newDuration ? prev : { ...prev, [meta.taskId]: newDuration }
    ));
  }, []);

  const clearResizeDraft = useCallback((taskId: string) => {
    setResizeDrafts((prev) => {
      if (!(taskId in prev)) return prev;
      const next = { ...prev };
      delete next[taskId];
      return next;
    });
    delete resizeDurationRef.current[taskId];
  }, []);

  const handleResizeRelease = useCallback(() => {
    const meta = resizingTaskRef.current;
    if (meta) {
      const nextDuration = resizeDurationRef.current[meta.taskId] ?? meta.startDuration;
      clearResizeDraft(meta.taskId);
      void resizeCalendarTaskDuration(meta.taskId, nextDuration)
        .then((nextTask) => {
          setSelectedTask((current) => (current?.id === nextTask.id ? nextTask : current));
          void refresh();
        })
        .catch(() => {
          Alert.alert("调整时长失败", "请检查网络或同步状态后重试。");
          void refresh();
        });
    }
    resizingTaskRef.current = null;
  }, [clearResizeDraft, refresh]);

  const handleResizeTerminate = useCallback(() => {
    const meta = resizingTaskRef.current;
    if (meta) {
      clearResizeDraft(meta.taskId);
    }
    resizingTaskRef.current = null;
  }, [clearResizeDraft]);

  // ─── Header ─────────────────────────────────

  const headerTitle = useMemo(() => {
    if (viewMode === "month") return `${year}年${month + 1}月`;
    if (viewMode === "week") {
      const start = weekDates[0];
      const end = weekDates[6];
      if (start.getMonth() === end.getMonth()) {
        return `${start.getFullYear()}年${start.getMonth() + 1}月`;
      }
      return `${start.getMonth() + 1}月 – ${end.getMonth() + 1}月`;
    }
    const weekday = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"][selectedDate.getDay()];
    return `${selectedDate.getMonth() + 1}月${selectedDate.getDate()}日 · ${weekday}`;
  }, [viewMode, year, month, selectedDate, weekDates]);

  const viewLabel = VIEW_OPTIONS.find((v) => v.key === viewMode)?.label ?? "月";

  const goToPrev = viewMode === "month" ? goToPrevMonth : viewMode === "week" ? goToPrevWeek : goToPrevDay;
  const goToNext = viewMode === "month" ? goToNextMonth : viewMode === "week" ? goToNextWeek : goToNextDay;

  // ─── Render ──────────────────────────────────

  if (!isHydrated) {
    return (
      <SafeAreaView style={[sty.centered, { paddingTop: chrome.screenTopPadding }]} edges={["left", "right"]}>
        <ActivityIndicator size="large" color={colors.brand} />
        <Text style={sty.loadingText}>加载中...</Text>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView
      ref={containerRef as any}
      style={sty.container}
      edges={["left", "right"]}
      onLayout={measureContainer}
      onTouchMove={(e) => {
        if (!draggingTask) return;
        const { pageX, pageY } = e.nativeEvent;
        updateDrag(pageX, pageY);
      }}
      onTouchEnd={() => {
        if (!draggingTask) return;
        void endDrag();
      }}
      onTouchCancel={() => {
        if (!draggingTask) return;
        void endDrag();
      }}
    >
      <CalendarHeader
        styles={sty}
        headerTitle={headerTitle}
        viewLabel={viewLabel}
        topPadding={chrome.headerTopPadding}
        onPrev={goToPrev}
        onNext={goToNext}
        onOpenViewMenu={() => setShowViewMenu(true)}
      />
      <View style={sty.focusBarWrap}>
        <FocusBar
          showAll={showAllForFocus}
          onToggleShowAll={focusLocked ? () => setShowAllForFocus((current) => !current) : undefined}
          onOpenWorkspace={focus.clientId ? () => setWorkspaceClientId(focus.clientId) : undefined}
          onOpenEventLine={focus.eventLineId ? () => setEventLineDrawerId(focus.eventLineId) : undefined}
        />
      </View>
      <WeekSignalCard weekLabel={weekLabelForDateKey(getLocalWeekAnchorDateKey(selectedDate))} snapshot={weekSignal} />

      {viewMode === "month" ? (
        <MonthView
          styles={sty}
          weekdayLabels={WEEKDAY_LABELS}
          calendarDays={calendarDays}
          selectedDateKey={selectedDateKey}
          todayKey={todayKey}
          tasksByDate={tasksByDate}
          draggingTask={draggingTask}
          hoveredDropKey={hoveredDropKey}
          selectedTasks={selectedTasks}
          highlightedTaskIds={focusMatchedTaskIds}
          refreshing={refreshing}
          bottomPadding={chrome.tabBarHeight + spacing.lg}
          registerDropZone={registerDropZone}
          onSelectDate={(dateKey) => selectDate(dateKey)}
          onRefresh={() => { void loadTasks(); }}
          onTaskPress={handleTaskPress}
          onEventLinePress={(task) => {
            if (task.eventLineId) {
              setCurrentFocusBrowseFromCalendar(task);
              setEventLineDrawerId(task.eventLineId);
            }
          }}
          onTaskTouchStart={handleTaskTouchStart}
          onTaskTouchMove={handleTaskTouchMove}
          onTaskTouchEnd={handleTaskTouchEnd}
          shouldSetTaskResponder={shouldSetTaskResponder}
        />
      ) : null}

      {viewMode === "day" ? (
        <DayView
          styles={sty}
          weekdayLabels={WEEKDAY_LABELS}
          weekDates={weekDates}
          selectedDateKey={selectedDateKey}
          todayKey={todayKey}
          tasksByDate={tasksByDate}
          dayAllDayTasks={dayAllDayTasks}
          dayScheduledTasks={dayScheduledTasksForView}
          highlightedTaskIds={focusMatchedTaskIds}
          draggingTask={draggingTask}
          hoveredDropKey={hoveredDropKey}
          refreshing={refreshing}
          bottomPadding={chrome.tabBarHeight + 40}
          currentTimeOffset={currentTimeOffset}
          timelineRef={timelineRef}
          registerDropZone={registerDropZone}
          onRefresh={() => { void loadTasks(); }}
          onSelectDate={(dateKey) => selectDate(dateKey)}
          onTimelineSlotPress={handleTimelineSlotPress}
          onTimelineSlotLongPress={handleTimelineSlotLongPress}
          onTaskPress={handleTaskPress}
          onEventLinePress={(task) => {
            if (task.eventLineId) {
              setCurrentFocusBrowseFromCalendar(task);
              setEventLineDrawerId(task.eventLineId);
            }
          }}
          onTaskTouchStart={handleTaskTouchStart}
          onResizeGrant={handleResizeGrant}
          onResizeMove={handleResizeMove}
          onResizeRelease={handleResizeRelease}
          onResizeTerminate={handleResizeTerminate}
        />
      ) : null}

      {viewMode === "week" ? (
        <WeekView
          styles={sty}
          weekdayLabels={WEEKDAY_LABELS}
          weekdayNames={WEEKDAY_CN}
          calendarDays={calendarDays}
          weekDates={weekDates}
          selectedDateKey={selectedDateKey}
          todayKey={todayKey}
          tasksByDate={tasksByDate}
          draggingTask={draggingTask}
          hoveredDropKey={hoveredDropKey}
          expandedWeekDay={expandedWeekDay}
          highlightedTaskIds={focusMatchedTaskIds}
          refreshing={refreshing}
          bottomPadding={chrome.tabBarHeight + spacing.lg}
          registerDropZone={registerDropZone}
          onRefresh={() => { void loadTasks(); }}
          onSelectDate={(dateKey, switchView) => selectDate(dateKey, switchView)}
          onSetExpandedWeekDay={setExpandedWeekDay}
          onTaskPress={handleTaskPress}
          onEventLinePress={(task) => {
            if (task.eventLineId) {
              setCurrentFocusBrowseFromCalendar(task);
              setEventLineDrawerId(task.eventLineId);
            }
          }}
          onTaskTouchStart={handleTaskTouchStart}
          onTaskTouchMove={handleTaskTouchMove}
          onTaskTouchEnd={handleTaskTouchEnd}
          shouldSetTaskResponder={shouldSetTaskResponder}
        />
      ) : null}

      <CalendarDragLayer
        styles={sty}
        draggingTask={draggingTask}
        dragOpacity={dragOpacity}
        dragScale={dragScale}
        dragTranslate={dragTranslate}
      />

      {/* ─── View switcher modal ─── */}
      <Modal visible={showViewMenu} transparent animationType="fade" onRequestClose={() => setShowViewMenu(false)}>
        <TouchableOpacity
          style={[sty.menuOverlay, { paddingTop: chrome.floatingMenuTopInset }]}
          activeOpacity={1}
          onPress={() => setShowViewMenu(false)}
        >
          <View style={sty.menuCard}>
            {VIEW_OPTIONS.map((opt) => (
              <TouchableOpacity
                key={opt.key}
                style={[sty.menuItem, viewMode === opt.key && sty.menuItemActive]}
                onPress={() => { setViewMode(opt.key); setShowViewMenu(false); }}
              >
                <Text style={[sty.menuItemText, viewMode === opt.key && sty.menuItemTextActive]}>
                  {opt.label}视图
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </TouchableOpacity>
      </Modal>

      <CalendarModalCoordinator
        selectedTask={selectedTask}
        selectedTaskEventLine={selectedTaskEventLine}
        recordTaskContext={recordTaskContext}
        reviewTaskContext={reviewTaskContext}
        showCreate={showCreate}
        showSmartInput={showSmartInput}
        smartDraft={smartDraft}
        createPreset={createPreset}
        smartInputPreset={smartInputPreset}
        selectedDateKey={selectedDateKey}
        onCloseSelectedTask={() => setSelectedTask(null)}
        onStartReview={(task) => {
          setReviewTaskContext(task);
          setSelectedTask(null);
        }}
        onRecordFromTaskDetail={() => {
          if (!selectedTask) return;
          setRecordTaskContext(selectedTask);
          setSelectedTask(null);
        }}
        onUpdateTask={(taskId, updates) => {
          void applyTaskUpdates(taskId, updates).catch(() => {
            Alert.alert("更新任务失败", "请检查网络或同步状态后重试。");
            void refresh();
          });
        }}
        onDeleteTask={async (task) => {
          try {
            deleteTaskOfflineFirst(task.id);
            setSelectedTask(null);
            void refresh();
            await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
          } catch {
            void refresh();
            Alert.alert("删除失败", "请检查网络后重试。");
          }
        }}
        onReplaceSelectedTask={(task) => {
          setSelectedTask(task);
          void refresh();
        }}
        onOpenClientWorkspace={(clientId) => setWorkspaceClientId(clientId)}
        onOpenEventLine={(eventLineId) => {
          setCurrentFocusBrowseFromEventLine(eventLineId);
          setEventLineDrawerId(eventLineId);
        }}
        onOpenConsult={(task) => {
          setCurrentFocusBrowseFromCalendar(task);
          setSelectedTask(null);
          router.push("/(tabs)/consult");
        }}
        onUploadedRecord={(task) => {
          setRecordTaskContext(null);
          setSelectedTask(task);
          void refresh();
        }}
        onCloseRecord={() => setRecordTaskContext(null)}
        onCloseReview={() => setReviewTaskContext(null)}
        onSavedReview={() => {
          setReviewTaskContext(null);
          void refresh();
        }}
        onCloseCreate={() => {
          setShowCreate(false);
          setSmartDraft(null);
          setCreatePreset({});
        }}
        onCreated={() => {
          setShowCreate(false);
          setSmartDraft(null);
          setCreatePreset({});
          void refresh();
        }}
        onCloseSmartInput={() => {
          setShowSmartInput(false);
          setSmartInputPreset({});
        }}
        onApplySmartDraft={applySmartDraft}
      />
      <EventLineDrawer
        visible={Boolean(eventLineDrawerId)}
        eventLine={drawerEventLine}
        tasks={tasks}
        clients={clients}
        meetingHighlights={clientIntel.snapshot?.latestMeetings ?? []}
        onClose={() => setEventLineDrawerId(null)}
        onOpenWorkspace={() => {
          if (drawerEventLine?.primaryClientId) {
            setWorkspaceClientId(drawerEventLine.primaryClientId);
          }
        }}
        onTransferToClient={handleTransferDrawerEventLine}
        isTransferringClient={transferringEventLineId === drawerEventLine?.id}
        onTaskPress={(task) => {
          setEventLineDrawerId(null);
          setSelectedTask(task);
        }}
      />
      <WorkspaceLiteSheet
        visible={Boolean(workspaceClientId)}
        clientId={workspaceClientId}
        clientName={focus.clientName}
        onClose={() => setWorkspaceClientId(null)}
        onTaskPress={(taskId) => {
          const task = localDb.getTaskById(taskId);
          if (!task) {
            return;
          }
          setWorkspaceClientId(null);
          setSelectedTask(task);
        }}
      />
    </SafeAreaView>
  );
}

// ─── Styles ─────────────────────────────────────

const CELL_SIZE = 44;

const sty = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  centered: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.background },
  loadingText: { marginTop: spacing.md, color: colors.textSecondary, fontSize: fontSize.md },
  errorText: { color: colors.error, fontSize: fontSize.md },
  focusMatchedCard: {
    borderColor: colors.brandRing,
    backgroundColor: "#F8FBFF",
  },
  focusChip: {
    alignSelf: "flex-start",
    marginTop: spacing.xs,
    backgroundColor: colors.brandBg,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
  },
  focusChipText: {
    fontSize: fontSize.xs,
    color: colors.brand,
    fontWeight: "700",
  },
  focusBarWrap: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },

  // ─── Header ───
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    backgroundColor: colors.surface,
  },
  headerNav: { flexDirection: "row", alignItems: "center", flex: 1 },
  headerTitle: { fontSize: fontSize.xl, fontWeight: "700", color: colors.text, marginHorizontal: spacing.md },
  navButton: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: colors.surfaceSecondary, alignItems: "center", justifyContent: "center",
  },
  viewSwitcher: {
    flexDirection: "row", alignItems: "center", gap: 4,
    paddingHorizontal: 14, paddingVertical: 8,
    borderRadius: borderRadius.full, backgroundColor: "#EBF0FC",
    borderWidth: 1, borderColor: "#DCE6F8",
  },
  viewSwitcherText: { fontSize: 13, fontWeight: "700", color: colors.brand },

  // ─── Month View ───
  weekRow: {
    flexDirection: "row", backgroundColor: colors.surface,
    paddingBottom: spacing.sm, paddingHorizontal: spacing.sm,
  },
  weekCell: { flex: 1, alignItems: "center" },
  weekLabel: { fontSize: fontSize.sm, color: colors.textTertiary, fontWeight: "600" },

  calendarGrid: {
    flexDirection: "row", flexWrap: "wrap",
    backgroundColor: colors.surface, paddingHorizontal: spacing.sm, paddingBottom: spacing.md,
  },
  dayCell: {
    width: `${100 / 7}%` as unknown as number, alignItems: "center", paddingVertical: 2,
  },
  dayCircle: {
    width: CELL_SIZE, height: CELL_SIZE, borderRadius: CELL_SIZE / 2,
    alignItems: "center", justifyContent: "center",
  },
  dayCircleSelected: { backgroundColor: colors.brand },
  dayCircleToday: { backgroundColor: colors.brandBg2 },
  dayCircleDragHover: {
    backgroundColor: "#DBEAFE", borderWidth: 2, borderColor: colors.brand,
  },
  dayText: { fontSize: fontSize.md, color: colors.text },
  dayTextOther: { color: colors.textTertiary },
  dayTextSelected: { color: colors.textOnBrand, fontWeight: "700" },
  dayTextToday: { color: colors.brand, fontWeight: "700" },
  dayTextDragHover: { color: colors.brand, fontWeight: "800" },
  taskDot: { width: 5, height: 5, borderRadius: 2.5, backgroundColor: colors.brand, marginTop: 2 },
  taskDotSelected: { backgroundColor: colors.textOnBrand },

  taskSection: { flex: 1, backgroundColor: colors.background },
  taskSectionContent: { padding: spacing.lg, paddingBottom: 100 },
  sectionTitle: { fontSize: fontSize.lg, fontWeight: "700", color: colors.text, marginBottom: spacing.md },

  taskCard: {
    backgroundColor: colors.surface, borderRadius: borderRadius.md,
    padding: spacing.lg, marginBottom: spacing.sm, ...shadow.card,
  },
  taskCardDragging: { opacity: 0.25, borderWidth: 1, borderColor: colors.brand, borderStyle: "dashed" },
  taskRow: { flexDirection: "row", alignItems: "center" },
  taskCheckCircle: {
    width: 20, height: 20, borderRadius: 10,
    borderWidth: 2, borderColor: colors.border, marginRight: spacing.md,
  },
  taskContent: { flex: 1 },
  taskTitle: { fontSize: fontSize.md, fontWeight: "600", color: colors.text },
  taskTime: { fontSize: fontSize.sm, color: colors.textTertiary, marginTop: 2 },
  emptyState: { alignItems: "center", justifyContent: "center", paddingVertical: 60 },
  emptyText: { fontSize: fontSize.md, color: colors.textTertiary, marginTop: spacing.md },
  dragHint: { fontSize: 12, color: colors.brand, textAlign: "center", marginTop: 8, fontWeight: "500" },

  // ─── Day View ───
  weekStrip: {
    flexDirection: "row", backgroundColor: colors.surface,
    paddingVertical: 8, paddingHorizontal: 4,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: "#EEF1F5",
  },
  weekStripDay: { flex: 1, alignItems: "center", paddingVertical: 4 },
  weekStripLabel: { fontSize: 12, fontWeight: "600", color: colors.textTertiary, marginBottom: 4 },
  weekStripLabelWeekend: { color: "#CBD5E1" },
  weekStripCircle: {
    width: 36, height: 36, borderRadius: 18, alignItems: "center", justifyContent: "center",
  },
  weekStripCircleSelected: { backgroundColor: colors.brand },
  weekStripCircleToday: { backgroundColor: colors.brandBg2 },
  weekStripCircleDragHover: {
    backgroundColor: "#DBEAFE", borderWidth: 2, borderColor: colors.brand,
  },
  weekStripDate: { fontSize: 16, fontWeight: "700", color: colors.text },
  weekStripDateSelected: { color: "#FFFFFF" },
  weekStripDateToday: { color: colors.brand },
  weekStripDot: { width: 4, height: 4, borderRadius: 2, backgroundColor: colors.brand, marginTop: 3 },

  timeline: { flex: 1, backgroundColor: colors.background },
  timelineContent: {
    position: "relative" as const,
    minHeight: (TIMELINE_END - TIMELINE_START + 1) * HOUR_HEIGHT,
  },
  allDaySection: {
    flexDirection: "row" as const,
    alignItems: "flex-start" as const,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.borderLight,
    backgroundColor: "#FAFAFF",
  },
  allDayLabel: {
    width: 40,
    fontSize: 11,
    fontWeight: "600" as const,
    color: colors.textTertiary,
    paddingTop: 6,
  },
  allDayList: {
    flex: 1,
    gap: 4,
  },
  allDayTask: {
    flexDirection: "row" as const,
    alignItems: "center" as const,
    gap: 8,
    backgroundColor: "#EDE9FE",
    borderRadius: 8,
    borderLeftWidth: 3,
    borderLeftColor: "#8B5CF6",
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  allDayTaskDone: {
    backgroundColor: "#ECFDF5",
    borderLeftColor: "#10B981",
    opacity: 0.7,
  },
  allDayTaskTitle: {
    flex: 1,
    fontSize: 13,
    fontWeight: "500" as const,
    color: colors.text,
  },
  allDayTaskTitleDone: {
    textDecorationLine: "line-through" as const,
    color: colors.textTertiary,
  },
  hourRow: {
    height: HOUR_HEIGHT, flexDirection: "row", alignItems: "flex-start",
  },
  hourRowDragHover: { backgroundColor: "#EEF5FF" },
  hourLabel: {
    width: 44, fontSize: 12, fontWeight: "500", color: "#9CA3AF",
    textAlign: "right", paddingRight: 8, marginTop: -7, fontFamily: "monospace",
  },
  hourLine: { flex: 1, height: StyleSheet.hairlineWidth, backgroundColor: "#E5E7EB" },
  hourLineDragHover: { height: 2, backgroundColor: colors.brand },
  hourDropHint: {
    position: "absolute", right: 12, top: 4,
    fontSize: 11, fontWeight: "600", color: colors.brand,
  },

  // Timeline task blocks
  timelineTask: {
    position: "absolute" as const, borderRadius: 10,
    backgroundColor: "#EDE9FE", borderLeftWidth: 3, borderLeftColor: "#8B5CF6",
    overflow: "hidden",
  },
  timelineTaskDone: { backgroundColor: "#ECFDF5", borderLeftColor: "#10B981", opacity: 0.7 },
  timelineTaskHidden: { opacity: 0, height: 0, overflow: "hidden" },
  timelineTaskTouchable: { flex: 1, paddingHorizontal: 10, paddingVertical: 8 },
  timelineTaskHeader: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 3,
  },
  timelineTaskCheck: { width: 14, height: 14, borderRadius: 3, borderWidth: 1.5, borderColor: "#8B5CF6" },
  timelineTaskCheckDone: { backgroundColor: "#10B981", borderColor: "#10B981" },
  timelineTaskTitle: { fontSize: 13, fontWeight: "600", color: "#5B21B6", lineHeight: 18 },
  timelineTaskTitleDone: { color: "#059669", textDecorationLine: "line-through" },
  timelineTaskTime: { fontSize: 11, fontWeight: "600", color: "#7C3AED" },
  timelineResizeHandle: {
    position: "absolute" as const, left: 10, right: 10, bottom: 0, height: 20,
    alignItems: "center", justifyContent: "center",
  },
  timelineResizeGrip: {
    width: 32, height: 4, borderRadius: 2, backgroundColor: "rgba(139,92,246,0.3)",
  },

  // Current time indicator
  currentTimeLine: {
    position: "absolute" as const, left: 0, right: 0,
    flexDirection: "row", alignItems: "center", zIndex: 10,
  },
  currentTimeDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: "#EF4444", marginLeft: 38 },
  currentTimeBar: { flex: 1, height: 2, backgroundColor: "#EF4444" },

  // ─── Week View ───
  weekView: { flex: 1, backgroundColor: colors.background },
  weekViewContent: { padding: spacing.md },

  miniCalendar: {
    backgroundColor: colors.surface, borderRadius: borderRadius.lg,
    padding: spacing.md, marginBottom: spacing.md, ...shadow.softCard,
  },
  miniCalendarHeader: { flexDirection: "row", marginBottom: 4 },
  miniCalendarWeekday: { flex: 1, textAlign: "center", fontSize: 11, fontWeight: "600", color: colors.textTertiary },
  miniCalendarGrid: { flexDirection: "row", flexWrap: "wrap" },
  miniCalendarCell: {
    width: `${100 / 7}%` as unknown as number, alignItems: "center", paddingVertical: 2,
  },
  miniCalendarCellInWeek: { backgroundColor: "#F8FAFC" },
  miniCalendarDayCircle: { width: 28, height: 28, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  miniCalendarDayToday: { backgroundColor: colors.brandBg2 },
  miniCalendarDaySelected: { backgroundColor: colors.brand },
  miniCalendarDayText: { fontSize: 12, color: colors.text },
  miniCalendarDayTextOther: { color: colors.textTertiary },
  miniCalendarDayTextToday: { color: colors.brand, fontWeight: "700" },
  miniCalendarDayTextSelected: { color: "#FFFFFF", fontWeight: "700" },

  weekDayGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  weekDayColumn: {
    width: "48.5%" as unknown as number,
    backgroundColor: colors.surface, borderRadius: borderRadius.md,
    padding: spacing.md, minHeight: 120, ...shadow.softCard,
  },
  weekDayColumnDragHover: {
    borderWidth: 2, borderColor: colors.brand, backgroundColor: "#F0F7FF",
  },
  weekDayHeader: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: spacing.sm },
  weekDayName: { fontSize: 13, fontWeight: "600", color: colors.textSecondary },
  weekDayNameWeekend: { color: "#CBD5E1" },
  weekDayDateCircle: { width: 24, height: 24, borderRadius: 12, alignItems: "center", justifyContent: "center" },
  weekDayDateCircleToday: { backgroundColor: colors.brand },
  weekDayDate: { fontSize: 14, fontWeight: "700", color: colors.text },
  weekDayDateToday: { color: "#FFFFFF" },
  weekDayRestBadge: {
    fontSize: 10, fontWeight: "700", color: "#10B981",
    backgroundColor: "#ECFDF5", paddingHorizontal: 4, paddingVertical: 1,
    borderRadius: 4, overflow: "hidden",
  },
  weekTaskCard: {
    flexDirection: "row", alignItems: "center",
    paddingVertical: 6, paddingHorizontal: 8,
    backgroundColor: "#F3F0FF", borderRadius: 6, marginBottom: 4, gap: 6,
  },
  weekTaskCardDragging: { opacity: 0.2, borderWidth: 1, borderColor: "#8B5CF6", borderStyle: "dashed" },
  weekTaskDot: { width: 6, height: 6, borderRadius: 3 },
  weekTaskTitle: { flex: 1, fontSize: 12, fontWeight: "500", color: colors.text },
  weekTaskTime: { fontSize: 10, fontWeight: "600", color: colors.textTertiary },
  weekDayEmpty: { minHeight: 30, justifyContent: "center", alignItems: "center" },
  weekDayDropHint: { fontSize: 11, color: colors.brand, fontWeight: "500" },
  weekDayMoreButton: {
    flexDirection: "row", alignItems: "center", justifyContent: "center",
    gap: 4, paddingVertical: 6,
  },
  weekDayMore: { fontSize: 11, color: colors.brand, fontWeight: "500" },

  // ─── Drag dot overlay ───
  dragLayer: { ...StyleSheet.absoluteFillObject, zIndex: 20 },
  dragDot: {
    position: "absolute", left: 0, top: 0,
    width: DRAG_DOT_SIZE, height: DRAG_DOT_SIZE, borderRadius: DRAG_DOT_SIZE / 2,
    alignItems: "center", justifyContent: "center",
    shadowColor: "#2563EB", shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.35, shadowRadius: 14, elevation: 10,
  },
  dragDotText: { fontSize: 16, fontWeight: "800", color: "#FFFFFF" },

  // ─── View switcher menu ───
  menuOverlay: {
    flex: 1, backgroundColor: "rgba(0,0,0,0.12)",
    justifyContent: "flex-start", alignItems: "flex-end", paddingRight: 18,
  },
  menuCard: {
    backgroundColor: colors.surface, borderRadius: 20,
    paddingVertical: 4, minWidth: 120, ...shadow.softCard,
  },
  menuItem: { paddingHorizontal: 18, paddingVertical: 11 },
  menuItemActive: { backgroundColor: "#EBF0FC" },
  menuItemText: { fontSize: 13, fontWeight: "500", color: "#4B5563" },
  menuItemTextActive: { color: colors.brand, fontWeight: "600" },
}) as Record<string, any>;
~~~

## `mobile/app/(tabs)/consult.tsx`

- 编码: `utf-8`

~~~tsx
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { ExpoSpeechRecognitionModule, useSpeechRecognitionEvent } from "expo-speech-recognition";
import * as Clipboard from "expo-clipboard";
import { useAppChromeInsets } from "../../lib/app-chrome";
import { SimpleMarkdown } from "../../lib/simple-markdown";
import { colors, fontSize, spacing, borderRadius, shadow } from "../../lib/theme";
import { useAndroidBackToTasks } from "../../lib/android-back";
import { ChevronDown, Mic, Send, Copy, Layers, FileText, Clock, CheckCircle2, AlertCircle } from "lucide-react-native";
import { enqueueConsultationKnowledgeRequest, fetchConsultationKnowledgeRequests, fetchMobileCapabilities, sendConsultationChat } from "../../lib/api";
import type { ConsultationKnowledgeRequestRecord } from "../../lib/api";
import * as cache from "../../lib/cache";
import { useTaskBoard } from "../../lib/task-board-store";
import { useRenderCount } from "../../lib/use-render-count";
import EventLineDrawer from "../../components/EventLineDrawer";
import WorkspaceLiteSheet from "../../components/WorkspaceLiteSheet";
import { useCurrentFocus } from "../../lib/current-focus-store";
import { useClientIntel } from "../../lib/client-intel-store";
import { buildConsultRequestContext } from "../../lib/consult-context-adapter";
import {
  freezeConsultThreadContext,
  hasConsultThreadContextDrift,
  refreshConsultThreadContext,
} from "../../lib/consult-thread-context";
import { transferEventLineToClient } from "../../lib/event-line-client-transfer";
import {
  buildConsultContextOptions,
  buildConsultGreeting,
  resolveConsultContextFromFocus,
  type ConsultContextOption,
} from "../../lib/consult-context";
import type { ConsultThreadContextSnapshot, MobileCapabilityRecord } from "../../lib/types";

// ─── Types ──────────────────────────────────────

interface ChatMessage {
  readonly id: string;
  readonly role: "ai" | "user";
  readonly text: string;
  readonly answerMode?: "grounded" | "limited_context" | "missing_context" | "error" | null;
  readonly contextQuality?: {
    level?: "none" | "thin" | "partial" | "rich" | string;
    availableSources?: string[];
    missingSources?: string[];
    staleSources?: string[];
    contextBundleHash?: string | null;
  } | null;
  readonly evidence?: Array<{
    id: string;
    type: string;
    title: string;
    updatedAt?: string | null;
    snippet?: string | null;
  }>;
  readonly missingContext?: Array<{
    type: string;
    message: string;
  }>;
}

// ─── Constants ──────────────────────────────────

const AI_THINKING_PLACEHOLDER = "正在思考...";

const DEFAULT_QUICK_QUESTIONS: readonly string[] = [
  "查看上次会议共识",
  "这条合作线推进到哪了？",
  "帮我准备会前要点",
  "当前最该推进什么？",
] as const;

let messageIdCounter = 0;
function nextMessageId(): string {
  messageIdCounter += 1;
  return `msg-${messageIdCounter}`;
}

// ─── Component ──────────────────────────────────

export default function ConsultScreen() {
  useRenderCount("ConsultScreen");
  const chrome = useAppChromeInsets();
  const { board, isHydrated } = useTaskBoard();
  const {
    focus,
    clients,
    eventLines,
    setManualClientFocus,
    setManualClientEventLineFocus,
    setCurrentFocusBrowseFromTask,
    clearStoredCurrentFocus,
    setCurrentFocusBoundaryState,
  } = useCurrentFocus();
  const clientIntel = useClientIntel(focus.clientId);
  const tasks = board.tasks;
  const contextOptions = useMemo(() => buildConsultContextOptions(tasks), [tasks]);
  const [showContextPicker, setShowContextPicker] = useState(false);
  const [workspaceClientId, setWorkspaceClientId] = useState<string | null>(null);
  const [showEventLineDrawer, setShowEventLineDrawer] = useState(false);
  const [transferringEventLineId, setTransferringEventLineId] = useState<string | null>(null);

  const [messages, setMessages] = useState<readonly ChatMessage[]>([]);
  const [threadContextSnapshot, setThreadContextSnapshot] = useState<ConsultThreadContextSnapshot | null>(null);
  const [inputText, setInputText] = useState("");
  const [headerHeight, setHeaderHeight] = useState(0);
  const [pendingKnowledgeActionKey, setPendingKnowledgeActionKey] = useState<string | null>(null);
  const [knowledgeRequests, setKnowledgeRequests] = useState<readonly ConsultationKnowledgeRequestRecord[]>([]);
  const [showKnowledgePanel, setShowKnowledgePanel] = useState(false);
  const [isVoiceInputActive, setIsVoiceInputActive] = useState(false);
  const [backendCapabilities, setBackendCapabilities] = useState<MobileCapabilityRecord | null>(null);
  const [backendCapabilityError, setBackendCapabilityError] = useState<string | null>(null);

  const [keyboardVisible, setKeyboardVisible] = useState(false);
  const flatListRef = useRef<FlatList<ChatMessage>>(null);

  const selectedContext = useMemo(
    () => resolveConsultContextFromFocus(contextOptions, focus),
    [contextOptions, focus],
  );
  const selectedEventLine = useMemo(
    () => eventLines.find((item) => item.id === selectedContext.eventLineId) ?? null,
    [eventLines, selectedContext.eventLineId],
  );
  const consultRequestContext = useMemo(
    () => buildConsultRequestContext({
      currentFocus: focus,
      selectedContext,
      tasks,
      workspaceLite: clientIntel.snapshot,
      eventLine: selectedEventLine,
    }),
    [clientIntel.snapshot, focus, selectedContext, selectedEventLine, tasks],
  );
  const activeConsultContext = threadContextSnapshot ?? consultRequestContext;
  const activeEventLine = useMemo(
    () => eventLines.find((item) => item.id === activeConsultContext.eventLineId) ?? null,
    [activeConsultContext.eventLineId, eventLines],
  );
  const threadContextDrifted = useMemo(
    () =>
      threadContextSnapshot
        ? hasConsultThreadContextDrift(threadContextSnapshot, consultRequestContext)
        : false,
    [consultRequestContext, threadContextSnapshot],
  );
  const activeContextLabel = useMemo(() => {
    const parts = [
      activeConsultContext.clientName,
      activeConsultContext.eventLineName,
      activeConsultContext.taskTitle,
    ].filter(Boolean);
    if (parts.length > 0) {
      return parts.join(" / ");
    }
    return selectedContext?.label ?? "有限上下文";
  }, [
    activeConsultContext.clientName,
    activeConsultContext.eventLineName,
    activeConsultContext.taskTitle,
    selectedContext?.label,
  ]);
  const displayContextLabel = useMemo(() => {
    if (activeContextLabel === "全部") {
      return "有限上下文";
    }
    if (activeContextLabel === "全部上下文") {
      return "当前锁定上下文";
    }
    return activeContextLabel;
  }, [activeContextLabel]);
  const contextCoverage = useMemo(() => {
    const loaded: string[] = [];
    const missing: string[] = [];

    if (activeConsultContext.clientName) {
      loaded.push("客户名");
    } else {
      missing.push("客户");
    }
    if (activeConsultContext.taskBoardContext || activeConsultContext.taskContext) {
      loaded.push("任务板");
    } else if (activeConsultContext.clientId || activeConsultContext.taskId) {
      missing.push("任务板");
    }
    if (threadContextSnapshot) {
      loaded.push("线程快照");
    }
    if (clientIntel.snapshot && !clientIntel.error) {
      loaded.push("客户工作台");
    } else if (activeConsultContext.clientId) {
      missing.push("客户工作台");
    }
    if (clientIntel.snapshot?.latestMeetings?.length) {
      loaded.push("最近会议");
    } else if (activeConsultContext.clientId) {
      missing.push("最近会议");
    }
    if (clientIntel.snapshot?.headline || clientIntel.snapshot?.pendingDecisions?.length) {
      loaded.push("Strategic Cockpit");
    } else if (activeConsultContext.clientId) {
      missing.push("Strategic Cockpit");
    }
    if (backendCapabilities?.knowledgeMirror) {
      loaded.push("客户 DNA / 知识代理");
    } else if (activeConsultContext.clientId) {
      missing.push("客户 DNA / 知识代理");
    }

    const level =
      loaded.length >= 5 ? "较完整" : loaded.length >= 3 ? "部分可用" : "较弱";
    const summary =
      loaded.length >= 5
        ? "已加载工作台、会议和知识镜像，可按锁定上下文回答。"
        : loaded.length >= 3
          ? "当前只加载了部分上下文，回答会基于已有资料并明确缺口。"
          : "当前云端资料偏薄，回答会进入有限上下文模式。";
    return { loaded, missing, level, summary };
  }, [
    activeConsultContext.clientId,
    activeConsultContext.clientName,
    activeConsultContext.taskBoardContext,
    activeConsultContext.taskContext,
    activeConsultContext.taskId,
    backendCapabilities?.knowledgeMirror,
    clientIntel.error,
    clientIntel.snapshot,
    threadContextSnapshot,
  ]);
  const handleTransferSelectedEventLine = useCallback(async (clientId: string) => {
    if (!activeEventLine) {
      return;
    }
    const targetClient = clients.find((item) => item.id === clientId);
    if (!targetClient) {
      Alert.alert("迁移失败", "目标客户不存在，请刷新后重试。");
      return;
    }
    setTransferringEventLineId(activeEventLine.id);
    try {
      await transferEventLineToClient(activeEventLine.id, clientId);
      Alert.alert("已更新归属", `已把「${activeEventLine.name}」转到客户「${targetClient.name}」下。`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "请检查网络连接后重试。";
      Alert.alert("迁移失败", message);
    } finally {
      setTransferringEventLineId(null);
    }
  }, [activeEventLine, clients]);

  useSpeechRecognitionEvent("start", () => {
    setIsVoiceInputActive(true);
  });

  useSpeechRecognitionEvent("end", () => {
    setIsVoiceInputActive(false);
  });

  useSpeechRecognitionEvent("result", (event) => {
    const transcript = event.results[0]?.transcript?.trim();
    if (transcript) {
      setInputText(transcript);
    }
  });

  useSpeechRecognitionEvent("error", (event) => {
    setIsVoiceInputActive(false);
    Alert.alert("语音输入失败", event.message || "请稍后再试。");
  });

  // Track keyboard visibility to adjust input bar padding
  useEffect(() => {
    const showEvent = Platform.OS === "ios" ? "keyboardWillShow" : "keyboardDidShow";
    const hideEvent = Platform.OS === "ios" ? "keyboardWillHide" : "keyboardDidHide";
    const showSub = Keyboard.addListener(showEvent, () => setKeyboardVisible(true));
    const hideSub = Keyboard.addListener(hideEvent, () => setKeyboardVisible(false));
    return () => { showSub.remove(); hideSub.remove(); };
  }, []);

  useAndroidBackToTasks(
    useCallback(() => {
      if (showContextPicker) {
        setShowContextPicker(false);
        return true;
      }
      if (showEventLineDrawer) {
        setShowEventLineDrawer(false);
        return true;
      }
      if (workspaceClientId) {
        setWorkspaceClientId(null);
        return true;
      }
      return false;
    }, [showContextPicker, showEventLineDrawer, workspaceClientId]),
  );

  useEffect(() => {
    if (!selectedContext && contextOptions.length === 0) {
      return;
    }
    if (messages.length > 0) {
      return;
    }
    setMessages([
      {
        id: nextMessageId(),
        role: "ai",
        text: buildConsultGreeting(selectedContext),
      },
    ]);
  }, [contextOptions, messages.length, selectedContext]);

  useEffect(() => {
    setCurrentFocusBoundaryState(clientIntel.snapshot?.boundaryState ?? "none");
  }, [clientIntel.snapshot?.boundaryState, setCurrentFocusBoundaryState]);

  useEffect(() => {
    let cancelled = false;
    cache.loadWithCache(
      cache.KEYS.consultKnowledgeRequests,
      fetchConsultationKnowledgeRequests,
      (requests) => { if (!cancelled) setKnowledgeRequests(requests); },
    ).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchMobileCapabilities()
      .then((capabilities) => {
        if (cancelled) {
          return;
        }
        setBackendCapabilities(capabilities);
        setBackendCapabilityError(null);
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        setBackendCapabilities(null);
        setBackendCapabilityError(error instanceof Error ? error.message : "能力探测失败");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const refreshKnowledgeRequests = useCallback(() => {
    fetchConsultationKnowledgeRequests()
      .then((requests) => setKnowledgeRequests(requests))
      .catch(() => {});
  }, []);

  // Handle context change
  const handleContextChange = useCallback((option: ConsultContextOption) => {
    if (option.scope === "all") {
      clearStoredCurrentFocus();
    } else if (option.scope === "client" && option.clientId) {
      setManualClientFocus(option.clientId);
    } else if (option.scope === "event_line" && option.clientId && option.eventLineId) {
      setManualClientEventLineFocus(option.clientId, option.eventLineId);
    }
    setShowContextPicker(false);
    setThreadContextSnapshot(null);
    setMessages([
      {
        id: nextMessageId(),
        role: "ai",
        text: buildConsultGreeting(option),
      },
    ]);
  }, [clearStoredCurrentFocus, setManualClientEventLineFocus, setManualClientFocus]);

  const [aiLoading, setAiLoading] = useState(false);

  // Send message with real AI
  const handleSend = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || aiLoading) return;

      const userMsg: ChatMessage = {
        id: nextMessageId(),
        role: "user",
        text: trimmed,
      };
      const placeholderId = nextMessageId();
      const placeholderMsg: ChatMessage = {
        id: placeholderId,
        role: "ai",
        text: AI_THINKING_PLACEHOLDER,
      };

      setMessages((prev) => [...prev, userMsg, placeholderMsg]);
      setInputText("");
      setAiLoading(true);

      setTimeout(() => {
        flatListRef.current?.scrollToEnd({ animated: true });
      }, 100);

      const prepareThreadContext = async () => {
        if (threadContextSnapshot) {
          return threadContextSnapshot;
        }
        let nextRequestContext = consultRequestContext;
        if (selectedContext.clientId && !consultRequestContext.workspaceContext) {
          const refreshedSnapshot = await clientIntel.refresh();
          if (refreshedSnapshot) {
            nextRequestContext = buildConsultRequestContext({
              currentFocus: focus,
              selectedContext,
              tasks,
              workspaceLite: refreshedSnapshot,
              eventLine: selectedEventLine,
            });
          }
        }
        const nextFrozenContext = freezeConsultThreadContext(nextRequestContext);
        setThreadContextSnapshot(nextFrozenContext);
        return nextFrozenContext;
      };

      void prepareThreadContext()
        .then((resolvedContext) =>
          sendConsultationChat({
            message: trimmed,
            clientId: resolvedContext.clientId,
            clientName: resolvedContext.clientName,
            eventLineId: resolvedContext.eventLineId,
            eventLineName: resolvedContext.eventLineName,
            taskId: resolvedContext.taskId,
            taskTitle: resolvedContext.taskTitle,
            taskContext: resolvedContext.taskContext ?? null,
            workspaceContext: resolvedContext.workspaceContext ?? null,
            eventLineContext: resolvedContext.eventLineContext ?? null,
            taskBoardContext: resolvedContext.taskBoardContext ?? null,
            sourceLabels: resolvedContext.sourceLabels,
            missingEventLineHint: resolvedContext.missingEventLineHint ?? null,
          })
        )
        .then((response) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === placeholderId
                ? {
                    ...msg,
                    text: response.reply,
                    answerMode: response.answerMode ?? null,
                    contextQuality: response.contextQuality ?? null,
                    evidence: response.evidence ?? [],
                    missingContext: response.missingContext ?? [],
                  }
                : msg,
            ),
          );
        })
        .catch((err: unknown) => {
          const errorText =
            err instanceof Error ? err.message : "AI 回复失败，请稍后重试";
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === placeholderId
                ? { ...msg, text: `[错误] ${errorText}` }
                : msg,
            ),
          );
        })
        .finally(() => {
          setAiLoading(false);
          setTimeout(() => {
            flatListRef.current?.scrollToEnd({ animated: true });
          }, 100);
        });
    },
    [
      aiLoading,
      clientIntel,
      consultRequestContext,
      focus,
      selectedContext,
      selectedEventLine,
      tasks,
      threadContextSnapshot,
    ],
  );

  const handleQuickQuestion = useCallback(
    (question: string) => {
      handleSend(question);
    },
    [handleSend],
  );

  const handleSubmit = useCallback(() => {
    handleSend(inputText);
  }, [handleSend, inputText]);

  const handleRefreshThreadContext = useCallback(() => {
    const nextSnapshot = refreshConsultThreadContext(
      threadContextSnapshot,
      consultRequestContext,
    );
    setThreadContextSnapshot(nextSnapshot);
    Alert.alert(
      "已刷新上下文",
      nextSnapshot.taskTitle
        ? `当前线程已切到任务「${nextSnapshot.taskTitle}」。`
        : nextSnapshot.eventLineName
          ? `当前线程已切到「${nextSnapshot.clientName ?? "当前客户"} / ${nextSnapshot.eventLineName}」。`
          : nextSnapshot.clientName
            ? `当前线程已切到客户「${nextSnapshot.clientName}」。`
            : "当前线程已切回全部上下文。",
    );
  }, [consultRequestContext, threadContextSnapshot]);

  const findPromptForAnswer = useCallback(
    (messageId: string) => {
      const targetIndex = messages.findIndex((item) => item.id === messageId);
      if (targetIndex <= 0) return "";
      for (let index = targetIndex - 1; index >= 0; index -= 1) {
        const candidate = messages[index];
        if (candidate?.role === "user") {
          return candidate.text.trim();
        }
      }
      return "";
    },
    [messages],
  );

  const handleKnowledgeAction = useCallback(
    async (message: ChatMessage, target: "vector_memory" | "document_archive") => {
      if (message.role !== "ai") return;
      const actionKey = `${message.id}:${target}`;
      setPendingKnowledgeActionKey(actionKey);
      try {
        await enqueueConsultationKnowledgeRequest({
          target,
          question: findPromptForAnswer(message.id),
          answer: message.text,
          clientId: activeConsultContext.clientId,
          clientName: activeConsultContext.clientName,
          eventLineId: activeConsultContext.eventLineId,
        });
        Alert.alert(
          "已发送到云端",
          target === "vector_memory"
            ? "这条答案已登记到向量沉淀队列，桌面端会继续做本地知识入库。"
            : "这条答案已登记到文档沉淀队列，桌面端会继续生成正式文档。",
        );
        refreshKnowledgeRequests();
      } catch (error) {
        const messageText = error instanceof Error ? error.message : "沉淀请求发送失败";
        Alert.alert("发送失败", messageText);
      } finally {
        setPendingKnowledgeActionKey((current) => (current === actionKey ? null : current));
      }
    },
    [
      activeConsultContext.clientId,
      activeConsultContext.clientName,
      activeConsultContext.eventLineId,
      findPromptForAnswer,
      refreshKnowledgeRequests,
    ],
  );

  const handleRetryKnowledgeRequest = useCallback(async (request: ConsultationKnowledgeRequestRecord) => {
    if (!request.target || !request.answer) {
      Alert.alert("无法重试", "这条沉淀请求缺少必要内容。");
      return;
    }
    const actionKey = `retry:${request.id}`;
    setPendingKnowledgeActionKey(actionKey);
    try {
      await enqueueConsultationKnowledgeRequest({
        target: request.target,
        question: request.question ?? "",
        answer: request.answer,
        clientId: request.clientId,
        clientName: request.clientName,
        eventLineId: request.eventLineId,
      });
      Alert.alert("已重新加入队列", "失败项已重新提交，桌面端会继续处理。");
      refreshKnowledgeRequests();
    } catch (error) {
      Alert.alert("重试失败", error instanceof Error ? error.message : "请稍后再试。");
    } finally {
      setPendingKnowledgeActionKey((current) => (current === actionKey ? null : current));
    }
  }, [refreshKnowledgeRequests]);

  const handleCopyAnswer = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) {
      return;
    }
    try {
      await Clipboard.setStringAsync(trimmed);
      Alert.alert("已复制", "内容已复制到剪贴板。");
      return;
    } catch {}
    setInputText((current) => (current.trim() ? `${current.trim()}\n${trimmed}` : trimmed));
    Alert.alert("已放入输入框", "当前环境未提供系统剪贴板，已把内容放到输入框中。");
  }, []);

  const handleToggleVoiceInput = useCallback(async () => {
    if (isVoiceInputActive) {
      ExpoSpeechRecognitionModule.stop();
      return;
    }
    const permission = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
    if (!permission.granted) {
      Alert.alert("语音输入不可用", "请先允许麦克风和语音识别权限。");
      return;
    }
    ExpoSpeechRecognitionModule.start({
      lang: "zh-CN",
      interimResults: true,
      continuous: false,
      addsPunctuation: true,
      contextualStrings: [
        activeConsultContext.clientName,
        activeConsultContext.eventLineName,
        activeConsultContext.taskTitle,
      ].filter((item): item is string => Boolean(item)),
    });
  }, [
    activeConsultContext.clientName,
    activeConsultContext.eventLineName,
    activeConsultContext.taskTitle,
    isVoiceInputActive,
  ]);

  const handleOpenTaskContext = useCallback((taskId: string) => {
    const matchedTask = tasks.find((item) => item.id === taskId);
    if (!matchedTask) {
      Alert.alert("任务不存在", "当前列表里没有找到这条任务，可能已经被删除或尚未同步。");
      return;
    }
    setCurrentFocusBrowseFromTask(matchedTask);
    setShowEventLineDrawer(false);
    setWorkspaceClientId(null);
    if (!threadContextSnapshot) {
      setMessages([]);
    }
  }, [setCurrentFocusBrowseFromTask, tasks, threadContextSnapshot]);

  // ─── Render ─────────────────────────────────────

  if (!isHydrated) {
    return (
      <SafeAreaView style={[styles.centered, { paddingTop: chrome.screenTopPadding, paddingBottom: chrome.screenBottomPadding }]} edges={["left", "right"]}>
        <ActivityIndicator size="large" color={colors.brand} />
        <Text style={styles.loadingText}>加载中...</Text>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={["left", "right"]}>
      <KeyboardAvoidingView
        style={styles.flex1}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        keyboardVerticalOffset={Platform.OS === "ios" ? 0 : 0}
      >
        {/* Header */}
        <View
          style={[styles.header, { paddingTop: chrome.headerTopPadding }]}
          onLayout={(event) => setHeaderHeight(event.nativeEvent.layout.height)}
        >
          <Text style={styles.headerTitle}>咨询助手</Text>
          <View style={styles.contextRow}>
            <Text style={styles.contextLabel}>当前上下文：</Text>
            <TouchableOpacity
              style={styles.contextChip}
              onPress={() => setShowContextPicker((current) => !current)}
              activeOpacity={0.7}
            >
              <Text style={styles.contextChipText} numberOfLines={1}>
                {displayContextLabel}
              </Text>
              <ChevronDown size={12} color={colors.brand} />
            </TouchableOpacity>
          </View>
          <View style={styles.coverageCard}>
            <View style={styles.coverageHeaderRow}>
              <Text style={styles.coverageTitle}>上下文质量：{contextCoverage.level}</Text>
              {backendCapabilities?.contextBundle ? (
                <Text style={styles.coverageStatusBadge}>Bundle v{backendCapabilities.consultationPayloadVersion}</Text>
              ) : null}
            </View>
            <Text style={styles.coverageSummary}>{contextCoverage.summary}</Text>
            {contextCoverage.loaded.length > 0 ? (
              <Text style={styles.coverageList}>已可用：{contextCoverage.loaded.join("、")}</Text>
            ) : null}
            {contextCoverage.missing.length > 0 ? (
              <Text style={styles.coverageListMuted}>缺失：{contextCoverage.missing.join("、")}</Text>
            ) : null}
          </View>
          {clientIntel.error ? (
            <Text style={styles.contextWarning}>
              客户工作台加载失败，当前咨询不会使用工作台资料：{clientIntel.error}
            </Text>
          ) : null}
          {backendCapabilityError ? (
            <Text style={styles.contextWarning}>
              后端能力探测失败：{backendCapabilityError}
            </Text>
          ) : null}
          {backendCapabilities && !backendCapabilities.clientWorkspace ? (
            <Text style={styles.contextWarning}>
              当前后端没有 `workspace` 路由，回答会退回有限上下文模式。
            </Text>
          ) : null}
          {backendCapabilities && !backendCapabilities.strategicCockpit ? (
            <Text style={styles.contextWarning}>
              当前后端没有 `strategic-cockpit` 能力，无法提供正式战略判断层。
            </Text>
          ) : null}
          {activeConsultContext.sourceLabels.length > 0 ? (
            <View style={styles.sourceRow}>
              {activeConsultContext.sourceLabels.map((item) => (
                <View key={item} style={styles.sourceChip}>
                  <Text style={styles.sourceChipText}>{item}</Text>
                </View>
              ))}
            </View>
          ) : null}
          {activeConsultContext.missingEventLineHint ? (
            <Text style={styles.contextHint}>{activeConsultContext.missingEventLineHint}</Text>
          ) : null}
          {(activeConsultContext.clientId || activeConsultContext.eventLineId) ? (
            <View style={styles.contextActionRow}>
              {activeConsultContext.clientId ? (
                <TouchableOpacity
                  style={styles.contextActionButton}
                  activeOpacity={0.7}
                  onPress={() => setWorkspaceClientId(activeConsultContext.clientId)}
                >
                  <Text style={styles.contextActionButtonText}>客户工作台</Text>
                </TouchableOpacity>
              ) : null}
              {activeConsultContext.eventLineId ? (
                <TouchableOpacity
                  style={styles.contextActionButton}
                  activeOpacity={0.7}
                  onPress={() => setShowEventLineDrawer(true)}
                >
                  <Text style={styles.contextActionButtonText}>事件线详情</Text>
                </TouchableOpacity>
              ) : null}
            </View>
          ) : null}
          {threadContextSnapshot ? (
            <View style={styles.threadSnapshotRow}>
              <Text
                style={[
                  styles.threadSnapshotText,
                  threadContextDrifted && styles.threadSnapshotTextWarning,
                ]}
              >
                线程上下文 v{threadContextSnapshot.snapshotVersion}
                {threadContextDrifted ? " · 当前焦点已变化" : " · 已锁定"}
              </Text>
              <TouchableOpacity
                style={styles.threadSnapshotAction}
                onPress={handleRefreshThreadContext}
                activeOpacity={0.7}
              >
                <Text style={styles.threadSnapshotActionText}>刷新上下文</Text>
              </TouchableOpacity>
            </View>
          ) : null}
        </View>

        {/* Chat area */}
        <FlatList
          ref={flatListRef}
          data={messages}
          keyExtractor={(item) => item.id}
          style={styles.chatList}
          contentContainerStyle={styles.chatContent}
          renderItem={({ item }) => (
            <View
              style={[
                styles.messageBubble,
                item.role === "ai" ? styles.aiBubble : styles.userBubble,
              ]}
            >
              {item.text === AI_THINKING_PLACEHOLDER ? (
                <View style={styles.thinkingRow}>
                  <ActivityIndicator size="small" color={colors.brand} />
                  <Text style={[styles.messageText, { marginLeft: 8, color: colors.textSecondary }]}>
                    {AI_THINKING_PLACEHOLDER}
                  </Text>
                </View>
              ) : item.role === "user" ? (
                <Text style={[styles.messageText, styles.userMessageText]}>
                  {item.text}
                </Text>
              ) : (
                <SimpleMarkdown text={item.text} baseStyle={styles.messageText} />
              )}
              {item.role === "ai" && item.text !== AI_THINKING_PLACEHOLDER && (
                <View style={styles.answerMetaCard}>
                  {item.answerMode || item.contextQuality?.level ? (
                    <View style={styles.answerMetaRow}>
                      <Text style={styles.answerMetaTitle}>上下文质量</Text>
                      <Text style={styles.answerMetaValue}>
                        {item.answerMode === "limited_context"
                          ? "有限上下文"
                          : item.answerMode === "missing_context"
                            ? "缺失上下文"
                            : item.contextQuality?.level === "rich"
                              ? "较完整"
                              : item.contextQuality?.level === "partial"
                                ? "部分可用"
                                : item.contextQuality?.level === "thin"
                                  ? "较弱"
                                  : "未标注"}
                      </Text>
                    </View>
                  ) : null}
                  {item.evidence && item.evidence.length > 0 ? (
                    <View style={styles.answerMetaGroup}>
                      <Text style={styles.answerMetaLabel}>依据</Text>
                      {item.evidence.slice(0, 3).map((entry) => (
                        <Text key={entry.id} style={styles.answerMetaListItem}>
                          • {entry.title}
                          {entry.snippet ? `：${entry.snippet}` : ""}
                        </Text>
                      ))}
                    </View>
                  ) : null}
                  {item.missingContext && item.missingContext.length > 0 ? (
                    <View style={styles.answerMetaGroup}>
                      <Text style={styles.answerMetaLabel}>缺失</Text>
                      {item.missingContext.slice(0, 3).map((entry, index) => (
                        <Text key={`${entry.type}-${index}`} style={styles.answerMetaListItemMuted}>
                          • {entry.message}
                        </Text>
                      ))}
                    </View>
                  ) : null}
                </View>
              )}
              {item.role === "ai" && item.text !== AI_THINKING_PLACEHOLDER && !item.text.startsWith("[错误]") && (
                <View style={styles.actionIcons}>
                  <TouchableOpacity
                    style={styles.actionIcon}
                    onPress={() => {
                      void handleCopyAnswer(item.text);
                    }}
                  >
                    <Copy size={14} color={colors.textSecondary} />
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={styles.actionIcon}
                    onPress={() => {
                      void handleKnowledgeAction(item, "vector_memory");
                    }}
                    disabled={pendingKnowledgeActionKey === `${item.id}:vector_memory`}
                  >
                    {pendingKnowledgeActionKey === `${item.id}:vector_memory` ? (
                      <ActivityIndicator size="small" color={colors.brand} />
                    ) : (
                      <Layers size={14} color={colors.textSecondary} />
                    )}
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={styles.actionIcon}
                    onPress={() => {
                      void handleKnowledgeAction(item, "document_archive");
                    }}
                    disabled={pendingKnowledgeActionKey === `${item.id}:document_archive`}
                  >
                    {pendingKnowledgeActionKey === `${item.id}:document_archive` ? (
                      <ActivityIndicator size="small" color={colors.brand} />
                    ) : (
                      <FileText size={14} color={colors.textSecondary} />
                    )}
                  </TouchableOpacity>
                </View>
              )}
            </View>
          )}
          ListFooterComponent={
            messages.length <= 1 ? (
              <View style={styles.quickQuestions}>
                {DEFAULT_QUICK_QUESTIONS.map((q) => (
                  <TouchableOpacity
                    key={q}
                    style={styles.quickChip}
                    onPress={() => handleQuickQuestion(q)}
                    activeOpacity={0.7}
                  >
                    <Text style={styles.quickChipText}>{q}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            ) : null
          }
          onContentSizeChange={() => {
            flatListRef.current?.scrollToEnd({ animated: true });
          }}
        />

        {/* Knowledge request status panel */}
        {knowledgeRequests.length > 0 && (
          <TouchableOpacity
            style={styles.knowledgeStatusBar}
            onPress={() => setShowKnowledgePanel((v) => !v)}
            activeOpacity={0.7}
          >
            <Layers size={14} color={colors.brand} />
            <Text style={styles.knowledgeStatusText}>
              知识沉淀 {knowledgeRequests.filter((r) => r.status === "pending" || r.status === "processing").length} 处理中
              {" / "}
              {knowledgeRequests.filter((r) => r.status === "completed").length} 已完成
            </Text>
            <ChevronDown size={12} color={colors.textSecondary} style={showKnowledgePanel ? { transform: [{ rotate: "180deg" }] } : undefined} />
          </TouchableOpacity>
        )}
        {showKnowledgePanel && knowledgeRequests.length > 0 && (
          <View style={styles.knowledgePanel}>
            {knowledgeRequests.slice(0, 8).map((req) => (
              <View key={req.id} style={styles.knowledgeRow}>
                {req.status === "completed" ? (
                  <CheckCircle2 size={12} color="#10B981" />
                ) : req.status === "failed" ? (
                  <AlertCircle size={12} color={colors.error} />
                ) : (
                  <Clock size={12} color={colors.brand} />
                )}
                <Text style={styles.knowledgeTarget}>
                  {req.target === "vector_memory" ? "向量" : "文档"}
                </Text>
                <Text style={styles.knowledgeQuestion} numberOfLines={1}>
                  {req.question || req.answer?.slice(0, 30) || "—"}
                </Text>
                <Text style={styles.knowledgeStatusLabel}>
                  {req.status === "pending" ? "待处理" : req.status === "processing" ? "处理中" : req.status === "completed" ? "已完成" : "失败"}
                </Text>
                {req.status === "failed" ? (
                  <TouchableOpacity
                    style={styles.knowledgeRetryButton}
                    onPress={() => {
                      void handleRetryKnowledgeRequest(req);
                    }}
                    disabled={pendingKnowledgeActionKey === `retry:${req.id}`}
                  >
                    {pendingKnowledgeActionKey === `retry:${req.id}` ? (
                      <ActivityIndicator size="small" color={colors.brand} />
                    ) : (
                      <Text style={styles.knowledgeRetryText}>重试</Text>
                    )}
                  </TouchableOpacity>
                ) : null}
              </View>
            ))}
          </View>
        )}

        {/* Input bar */}
        <View style={[styles.inputBar, { paddingBottom: keyboardVisible ? spacing.sm : chrome.tabBarHeight + spacing.xs }]}>
          <TouchableOpacity
            style={[styles.micButton, isVoiceInputActive && styles.micButtonActive]}
            onPress={() => {
              void handleToggleVoiceInput();
            }}
          >
            <Mic size={18} color={isVoiceInputActive ? colors.textOnBrand : colors.textSecondary} />
          </TouchableOpacity>
          <TextInput
            style={styles.textInput}
            placeholder={isVoiceInputActive ? "正在听写..." : "输入问题，或点麦克风转成文字"}
            placeholderTextColor={colors.textTertiary}
            value={inputText}
            onChangeText={setInputText}
            onSubmitEditing={handleSubmit}
            returnKeyType="send"
            multiline={false}
          />
          <TouchableOpacity
            style={[
              styles.sendButton,
              (!inputText.trim() || aiLoading) && styles.sendButtonDisabled,
            ]}
            onPress={handleSubmit}
            disabled={!inputText.trim() || aiLoading}
            activeOpacity={0.7}
          >
            {aiLoading ? (
              <ActivityIndicator size="small" color={colors.textOnBrand} />
            ) : (
              <Send size={20} color={colors.textOnBrand} />
            )}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>

      {showContextPicker ? (
        <View style={styles.contextPickerOverlay}>
          <TouchableOpacity
            style={styles.contextPickerBackdrop}
            activeOpacity={1}
            onPress={() => setShowContextPicker(false)}
          />
          <View
            style={[
              styles.contextPickerCard,
              { top: Math.max(headerHeight - spacing.xs, spacing.xxxl) },
            ]}
          >
            <Text style={styles.contextPickerTitle}>选择上下文</Text>
            <View style={styles.contextPickerList}>
              {contextOptions.map((item) => (
                <TouchableOpacity
                  key={item.id}
                  style={[
                    styles.contextOptionRow,
                    selectedContext?.id === item.id &&
                      styles.contextOptionSelected,
                  ]}
                  onPress={() => handleContextChange(item)}
                  activeOpacity={0.7}
                >
                  <View style={styles.contextOptionCopy}>
                    <Text
                      style={[
                        styles.contextOptionText,
                        selectedContext?.id === item.id &&
                          styles.contextOptionTextSelected,
                      ]}
                    >
                      {item.scope === "all" ? "自由提问（有限上下文）" : item.label}
                    </Text>
                    <Text style={styles.contextOptionMeta}>
                      {item.scope === "event_line"
                        ? `${item.clientName || "客户"} · ${item.eventLineName || "事件线"}`
                        : item.clientName || "当前锁定上下文"}
                    </Text>
                  </View>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        </View>
      ) : null}
      <EventLineDrawer
        visible={showEventLineDrawer}
        eventLine={activeEventLine}
        tasks={tasks}
        clients={clients}
        meetingHighlights={clientIntel.snapshot?.latestMeetings ?? []}
        onClose={() => setShowEventLineDrawer(false)}
        onOpenWorkspace={() => {
          if (activeConsultContext.clientId) {
            setWorkspaceClientId(activeConsultContext.clientId);
          }
        }}
        onTransferToClient={handleTransferSelectedEventLine}
        isTransferringClient={transferringEventLineId === activeEventLine?.id}
        onTaskPress={(task) => handleOpenTaskContext(task.id)}
      />
      <WorkspaceLiteSheet
        visible={Boolean(workspaceClientId)}
        clientId={workspaceClientId}
        clientName={activeConsultContext.clientName}
        onClose={() => setWorkspaceClientId(null)}
        onTaskPress={handleOpenTaskContext}
      />
    </SafeAreaView>
  );
}

// ─── Styles ─────────────────────────────────────

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  flex1: {
    flex: 1,
  },
  centered: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.background,
  },
  loadingText: {
    marginTop: spacing.md,
    color: colors.textSecondary,
    fontSize: fontSize.md,
  },
  errorText: {
    color: colors.error,
    fontSize: fontSize.md,
  },

  // Header
  header: {
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.md,
    borderBottomWidth: 0.5,
    borderBottomColor: colors.borderLight,
  },
  headerTitle: {
    fontSize: fontSize.xxl,
    fontWeight: "700",
    color: colors.text,
    marginBottom: spacing.sm,
  },
  contextRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: spacing.sm,
  },
  contextLabel: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  contextChip: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.brandBg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
    maxWidth: 240,
  },
  contextChipText: {
    fontSize: fontSize.sm,
    color: colors.brand,
    fontWeight: "600",
    flexShrink: 1,
  },
  coverageCard: {
    marginTop: spacing.sm,
    padding: spacing.md,
    borderRadius: borderRadius.lg,
    backgroundColor: colors.surfaceSecondary,
    gap: spacing.xs,
  },
  coverageHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  coverageTitle: {
    fontSize: fontSize.sm,
    fontWeight: "700",
    color: colors.text,
  },
  coverageStatusBadge: {
    fontSize: fontSize.xs,
    color: colors.brand,
    fontWeight: "700",
  },
  coverageSummary: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  coverageList: {
    fontSize: fontSize.xs,
    color: colors.text,
    lineHeight: 18,
  },
  coverageListMuted: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  contextWarning: {
    marginTop: spacing.xs,
    fontSize: fontSize.xs,
    color: colors.warning,
    lineHeight: 18,
  },
  sourceRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
    marginTop: spacing.sm,
  },
  sourceChip: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
  },
  sourceChipText: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  contextHint: {
    marginTop: spacing.xs,
    fontSize: fontSize.xs,
    color: colors.textSecondary,
  },
  contextActionRow: {
    flexDirection: "row",
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  contextActionButton: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  contextActionButtonText: {
    fontSize: fontSize.xs,
    color: colors.brand,
    fontWeight: "700",
  },
  threadSnapshotRow: {
    marginTop: spacing.sm,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  threadSnapshotText: {
    flex: 1,
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  threadSnapshotTextWarning: {
    color: colors.warning,
  },
  threadSnapshotAction: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
    backgroundColor: colors.surfaceSecondary,
  },
  threadSnapshotActionText: {
    fontSize: fontSize.xs,
    color: colors.brand,
    fontWeight: "700",
  },
  chevron: {
    fontSize: 8,
    color: colors.brand,
    marginLeft: spacing.xs,
  },

  // Chat
  chatList: {
    flex: 1,
  },
  chatContent: {
    padding: spacing.lg,
    paddingBottom: spacing.xl,
  },
  messageBubble: {
    maxWidth: "85%",
    marginBottom: spacing.md,
    padding: spacing.lg,
    borderRadius: borderRadius.lg,
  },
  aiBubble: {
    alignSelf: "flex-start",
    backgroundColor: colors.surfaceSecondary,
    borderBottomLeftRadius: borderRadius.sm,
  },
  userBubble: {
    alignSelf: "flex-end",
    backgroundColor: colors.brand,
    borderBottomRightRadius: borderRadius.sm,
  },
  messageText: {
    fontSize: fontSize.md,
    color: colors.text,
    lineHeight: 22,
  },
  userMessageText: {
    color: colors.textOnBrand,
  },
  thinkingRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  answerMetaCard: {
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
    gap: spacing.xs,
  },
  answerMetaRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  answerMetaTitle: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  answerMetaValue: {
    fontSize: fontSize.xs,
    color: colors.brand,
    fontWeight: "700",
  },
  answerMetaGroup: {
    gap: 4,
  },
  answerMetaLabel: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    fontWeight: "700",
  },
  answerMetaListItem: {
    fontSize: fontSize.xs,
    color: colors.text,
    lineHeight: 18,
  },
  answerMetaListItemMuted: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  actionIcons: {
    flexDirection: "row",
    marginTop: spacing.sm,
    gap: spacing.md,
  },
  actionIcon: {
    width: 28,
    height: 28,
    borderRadius: borderRadius.sm,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  actionIconText: {
    fontSize: 14,
  },

  // Quick questions
  quickQuestions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  quickChip: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  quickChipText: {
    fontSize: fontSize.sm,
    color: colors.brand,
    fontWeight: "500",
  },

  // Knowledge status
  knowledgeStatusBar: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    backgroundColor: colors.brandBg,
    gap: spacing.sm,
  },
  knowledgeStatusText: {
    flex: 1,
    fontSize: fontSize.xs,
    color: colors.brand,
    fontWeight: "600",
  },
  knowledgePanel: {
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.borderLight,
    maxHeight: 200,
  },
  knowledgeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingVertical: 4,
  },
  knowledgeTarget: {
    fontSize: fontSize.xs,
    fontWeight: "700",
    color: colors.textSecondary,
    width: 28,
  },
  knowledgeQuestion: {
    flex: 1,
    fontSize: fontSize.xs,
    color: colors.text,
  },
  knowledgeStatusLabel: {
    fontSize: fontSize.xs,
    color: colors.textTertiary,
  },
  knowledgeRetryButton: {
    marginLeft: "auto",
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: borderRadius.full,
    backgroundColor: colors.surfaceSecondary,
  },
  knowledgeRetryText: {
    fontSize: fontSize.xs,
    color: colors.brand,
    fontWeight: "700",
  },

  // Input bar
  inputBar: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.md,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
    borderTopWidth: 0.5,
    borderTopColor: colors.borderLight,
    gap: spacing.sm,
  },
  micButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.surfaceSecondary,
    alignItems: "center",
    justifyContent: "center",
  },
  micButtonActive: {
    backgroundColor: colors.brand,
  },
  micIcon: {
    fontSize: 18,
  },
  textInput: {
    flex: 1,
    height: 40,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.lg,
    fontSize: fontSize.md,
    color: colors.text,
  },
  sendButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.brand,
    alignItems: "center",
    justifyContent: "center",
  },
  sendButtonDisabled: {
    backgroundColor: colors.surfaceSecondary,
  },
  sendIcon: {
    fontSize: 20,
    color: colors.textOnBrand,
    fontWeight: "700",
  },

  // Context picker
  contextPickerOverlay: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 20,
  },
  contextPickerBackdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(8, 15, 40, 0.16)",
  },
  contextPickerCard: {
    position: "absolute",
    right: spacing.lg,
    width: 272,
    backgroundColor: colors.surface,
    borderRadius: 24,
    padding: spacing.sm,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.borderLight,
    ...shadow.softCard,
  },
  contextPickerTitle: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.textSecondary,
    letterSpacing: 0.2,
    paddingHorizontal: spacing.md,
    paddingTop: spacing.sm,
    paddingBottom: spacing.xs,
  },
  contextPickerList: {
    gap: spacing.xs,
  },
  contextOptionRow: {
    borderRadius: 18,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
  },
  contextOptionSelected: {
    backgroundColor: colors.brandBg,
  },
  contextOptionCopy: {
    gap: 2,
  },
  contextOptionText: {
    fontSize: fontSize.sm,
    color: colors.text,
    fontWeight: "600",
  },
  contextOptionTextSelected: {
    color: colors.brand,
  },
  contextOptionMeta: {
    fontSize: fontSize.xs,
    color: colors.textTertiary,
  },
});
~~~

## `mobile/app/(tabs)/profile.tsx`

- 编码: `utf-8`

~~~tsx
import { useEffect, useState, useCallback } from "react";
import {
  ActivityIndicator,
  View,
  Text,
  TextInput,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Alert,
  Modal,
  Linking,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useAuth } from "../../lib/auth-context";
import { useAndroidBackToTasks } from "../../lib/android-back";
import { useAppChromeInsets } from "../../lib/app-chrome";
import { colors, spacing, fontSize, borderRadius, shadow } from "../../lib/theme";
import { Camera, Edit2, Search, Cloud, Smartphone, MessageSquare, Bell, CheckSquare, CalendarDays, Bot, ChevronRight, RefreshCw, PauseCircle, PlayCircle, AlertCircle, Download } from "lucide-react-native";
import { clearFeishuUserBinding, fetchHealth, getFeishuUserBinding, startFeishuUserBinding, updateMe, type FeishuUserBinding } from "../../lib/api";
import { useSystemHealth } from "../../lib/system-health";
import { triggerSync } from "../../lib/sync-engine";
import SettingsTasks from "../../components/SettingsTasks";
import SettingsCalendar from "../../components/SettingsCalendar";
import SettingsAI from "../../components/SettingsAI";
import SettingsAccount from "../../components/SettingsAccount";

type SettingsView = "account" | "tasks" | "calendar" | "ai" | null;

function getInitials(name: string): string {
  if (name.length <= 2) return name;
  return name.slice(-2);
}

function formatLocalTime(value: string | null | undefined): string {
  if (!value) return "未同步";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

function formatPendingAge(value: string | null | undefined): string {
  if (!value) return "刚刚";
  const date = new Date(value);
  const diffMs = Date.now() - date.getTime();
  if (!Number.isFinite(diffMs) || diffMs < 60_000) return "刚刚";
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  return `${Math.floor(hours / 24)} 天前`;
}

function formatAgeMs(value: number | null | undefined): string {
  if (value == null || value < 60_000) return "刚刚";
  const minutes = Math.floor(value / 60_000);
  if (minutes < 60) return `${minutes} 分钟`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时`;
  return `${Math.floor(hours / 24)} 天`;
}

function formatLegacyUploadReason(reasonCode: string | null | undefined): string {
  switch (reasonCode) {
    case "network_unavailable":
      return "网络不可用";
    case "auth_required":
      return "需要重新登录";
    case "scope_mismatch":
      return "账号作用域不一致";
    case "file_missing":
      return "原件丢失";
    case "file_corrupted":
      return "原件损坏";
    case "upload_failed":
      return "上传失败";
    case "bind_pending_remote_id":
      return "等待远端任务 ID";
    case "integrity_blocked":
      return "本地完整性冻结";
    case "manual_pause":
      return "同步已暂停";
    default:
      return "未知错误";
  }
}

function formatSyncReasonCode(reasonCode: string | null | undefined): string {
  switch (reasonCode) {
    case "network_unavailable":
      return "网络不可用";
    case "auth_expired":
      return "登录已过期";
    case "permission_denied":
      return "权限不足";
    case "validation_failed":
      return "数据校验失败";
    case "version_conflict":
      return "服务器版本冲突";
    case "file_missing":
      return "原件缺失";
    case "quota_exceeded":
      return "配额不足";
    case "server_rejected":
      return "服务器拒绝";
    case "thermal_blocked":
      return "设备温度受限";
    case "model_unavailable":
      return "模型不可用";
    default:
      return "需人工处理";
  }
}

function formatPendingOperationLabel(operation: string | null | undefined): string {
  switch (operation) {
    case "create":
      return "创建";
    case "update":
      return "更新";
    case "delete":
      return "删除";
    case "complete_with_review":
      return "完成并复盘";
    default:
      return "任务修改";
  }
}

interface SettingsRowProps {
  readonly iconBg: string;
  readonly icon: React.ReactNode;
  readonly title: string;
  readonly subtitle: string;
  readonly onPress: () => void;
  readonly rightText?: string;
}

function SettingsRow({
  iconBg,
  icon,
  title,
  subtitle,
  onPress,
  rightText,
}: SettingsRowProps) {
  return (
    <TouchableOpacity style={styles.settingsRow} onPress={onPress}>
      <View style={[styles.settingsIconBg, { backgroundColor: iconBg }]}>
        {icon}
      </View>
      <View style={styles.settingsTextContainer}>
        <Text style={styles.settingsTitle}>{title}</Text>
        <Text style={styles.settingsSubtitle} numberOfLines={1}>
          {subtitle}
        </Text>
      </View>
      {rightText ? (
        <Text style={styles.settingsRightText} numberOfLines={1}>
          {rightText}
        </Text>
      ) : (
        <ChevronRight size={22} color={colors.textTertiary} />
      )}
    </TouchableOpacity>
  );
}

export default function ProfileScreen() {
  const { user, signOut } = useAuth();
  const chrome = useAppChromeInsets();
  const systemHealth = useSystemHealth();
  const [activeSettings, setActiveSettings] = useState<SettingsView>(null);
  const [lastSyncTime, setLastSyncTime] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [showEditProfile, setShowEditProfile] = useState(false);
  const [editName, setEditName] = useState("");
  const [editRole, setEditRole] = useState("");
  const [saving, setSaving] = useState(false);
  const [feishuBinding, setFeishuBinding] = useState<FeishuUserBinding | null>(null);
  const [feishuBindingBusy, setFeishuBindingBusy] = useState<"idle" | "loading" | "starting" | "clearing">("idle");

  const pingHealth = useCallback(async () => {
    try {
      await fetchHealth();
      const now = new Date();
      setLastSyncTime(`${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`);
    } catch {
      setLastSyncTime("同步失败");
    }
  }, []);

  // "立即同步" button: push pending ops + pull cloud, then refresh liveness.
  // Previously this only called fetchHealth() which is just a /health ping and
  // did NOT flush the local-first queue, so users would tap "Sync Now" and see
  // the timestamp update even though nothing had actually synced.
  const doSync = useCallback(async () => {
    setSyncing(true);
    try {
      await triggerSync();
      await pingHealth();
    } catch {
      setLastSyncTime("同步失败");
    } finally {
      setSyncing(false);
    }
  }, [pingHealth]);

  const refreshFeishuBinding = useCallback(async () => {
    setFeishuBindingBusy("loading");
    try {
      const binding = await getFeishuUserBinding();
      setFeishuBinding(binding);
    } catch (error) {
      Alert.alert("加载失败", error instanceof Error ? error.message : "无法读取飞书绑定状态。");
    } finally {
      setFeishuBindingBusy("idle");
    }
  }, []);

  // On mount we only ping liveness — a full sync already runs in the background
  // via the sync-engine foreground loop, so we avoid a heavy extra cycle here.
  useEffect(() => {
    void pingHealth();
  }, [pingHealth]);

  useEffect(() => {
    void refreshFeishuBinding();
  }, [refreshFeishuBinding]);

  const handleStartFeishuBinding = useCallback(async () => {
    setFeishuBindingBusy("starting");
    try {
      const started = await startFeishuUserBinding();
      await Linking.openURL(started.authorizeUrl);
      Alert.alert(
        "已打开飞书授权页",
        started.qrReady
          ? "请在飞书里扫码并确认授权，完成后回到手机端刷新状态。"
          : "已打开授权页；如果当前环境不能直接扫码，请在浏览器继续完成授权。",
      );
      await refreshFeishuBinding();
    } catch (error) {
      Alert.alert("发起绑定失败", error instanceof Error ? error.message : "无法发起飞书绑定。");
    } finally {
      setFeishuBindingBusy("idle");
    }
  }, [refreshFeishuBinding]);

  const handleClearFeishuBinding = useCallback(async () => {
    setFeishuBindingBusy("clearing");
    try {
      const binding = await clearFeishuUserBinding();
      setFeishuBinding(binding);
      Alert.alert("已解除绑定", "当前账号的飞书身份绑定已清除。");
    } catch (error) {
      Alert.alert("解除失败", error instanceof Error ? error.message : "无法解除飞书绑定。");
    } finally {
      setFeishuBindingBusy("idle");
    }
  }, []);

  const handleOpenFeishuBinding = useCallback(() => {
    if (feishuBindingBusy !== "idle") {
      return;
    }
    if (!feishuBinding) {
      void refreshFeishuBinding();
      return;
    }
    if (feishuBinding.linked) {
      Alert.alert(
        "飞书已绑定",
        `${feishuBinding.name || feishuBinding.email || "当前账号"} 已完成飞书身份绑定。`,
        [
          { text: "取消", style: "cancel" },
          {
            text: "刷新状态",
            onPress: () => {
              void refreshFeishuBinding();
            },
          },
          {
            text: "解除绑定",
            style: "destructive",
            onPress: () => {
              void handleClearFeishuBinding();
            },
          },
        ],
      );
      return;
    }
    if (feishuBinding.readyForAuthorization) {
      void handleStartFeishuBinding();
      return;
    }
    Alert.alert(
      "暂不可绑定",
      feishuBinding.lastError || "需要管理员先配置飞书 App ID、App Secret 和机器人基础设置。",
    );
  }, [feishuBinding, feishuBindingBusy, handleClearFeishuBinding, handleStartFeishuBinding, refreshFeishuBinding]);

  const handleOpenNotificationSettings = useCallback(() => {
    Linking.openSettings().catch(() => {
      Alert.alert("无法打开设置", "请手动前往系统设置调整通知权限。");
    });
  }, []);

  const feishuBindingRightText =
    feishuBindingBusy !== "idle"
      ? "处理中"
      : feishuBinding?.linked
        ? "已绑定"
        : feishuBinding?.readyForAuthorization
          ? "待绑定"
          : "未就绪";

  useAndroidBackToTasks(
    useCallback(() => {
      if (activeSettings) {
        setActiveSettings(null);
        return true;
      }
      return false;
    }, [activeSettings]),
  );

  const handleLogout = useCallback(() => {
    Alert.alert("退出登录", "确定要退出当前账号吗？", [
      { text: "取消", style: "cancel" },
      {
        text: "退出",
        style: "destructive",
        onPress: () => signOut(),
      },
    ]);
  }, [signOut]);

  const closeSettings = useCallback(() => setActiveSettings(null), []);

  const openEditProfile = useCallback(() => {
    setEditName(user?.fullName ?? "");
    setEditRole("高级咨询顾问");
    setShowEditProfile(true);
  }, [user?.fullName]);

  const handleSaveProfile = useCallback(async () => {
    const trimmedName = editName.trim();
    if (!trimmedName) {
      Alert.alert("提示", "名称不能为空");
      return;
    }
    setSaving(true);
    try {
      await updateMe({ fullName: trimmedName });
      // Refresh user data in auth context
      Alert.alert("已保存", "名称已更新，重新登录后生效。");
      setShowEditProfile(false);
    } catch (err: unknown) {
      Alert.alert("保存失败", err instanceof Error ? err.message : "请检查网络");
    } finally {
      setSaving(false);
    }
  }, [editName]);

  const displayName = user?.fullName ?? "用户";
  const displayEmail = user?.email ?? "";
  const initials = getInitials(displayName);
  const legacyUploadNeedsAttention = systemHealth.legacyUploadOps.filter(
    (op) => op.status === "needs_attention",
  ).length;
  const combinedPendingTotal =
    systemHealth.pendingSummary.total + systemHealth.legacyUploadOps.length;
  const combinedQueuedCount =
    systemHealth.pendingSummary.queued +
    systemHealth.legacyUploadOps.filter((op) => op.status === "queued").length;
  const combinedProcessingCount =
    systemHealth.pendingSummary.syncing +
    systemHealth.pendingSummary.processing +
    systemHealth.legacyUploadOps.filter((op) => op.status === "processing").length;
  const combinedNeedsAttention =
    systemHealth.pendingSummary.needsAttention + legacyUploadNeedsAttention;

  return (
    <>
      <SafeAreaView style={styles.container} edges={["left", "right"]}>
        <ScrollView
          contentContainerStyle={{ paddingTop: chrome.screenTopPadding, paddingBottom: chrome.screenBottomPadding + spacing.xl }}
          showsVerticalScrollIndicator={false}
        >
          {/* Profile card */}
          <View style={[styles.profileCard, shadow.card]}>
            <View style={styles.profileRow}>
              <View style={styles.avatarContainer}>
                <View style={styles.avatar}>
                  <Text style={styles.avatarText}>{initials}</Text>
                </View>
                <TouchableOpacity style={styles.cameraOverlay} onPress={openEditProfile}>
                  <Camera size={12} color={colors.textSecondary} />
                </TouchableOpacity>
              </View>
              <View style={styles.profileInfo}>
                <View style={styles.nameRow}>
                  <Text style={styles.profileName}>{displayName}</Text>
                  <TouchableOpacity style={styles.editButton} onPress={openEditProfile}>
                    <Edit2 size={16} color={colors.textSecondary} />
                  </TouchableOpacity>
                </View>
                <Text style={styles.profileTitle}>高级咨询顾问</Text>
              </View>
              <TouchableOpacity style={styles.searchButton} onPress={() => setActiveSettings("account")}>
                <Search size={18} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>
          </View>

          {/* Cloud sync card */}
          <View style={styles.syncCard}>
            <View style={styles.syncLeft}>
              <Cloud size={22} color={colors.brand} />
              <View>
                <Text style={styles.syncText}>
                  {lastSyncTime === "同步失败" ? "云端连接失败" : "数据已同步至云端"}
                </Text>
                <Text style={styles.syncTime}>
                  {lastSyncTime ? `上次同步 ${lastSyncTime}` : "未同步"}
                </Text>
              </View>
            </View>
            <TouchableOpacity style={styles.syncButton} onPress={() => { void doSync(); }} disabled={syncing}>
              {syncing ? (
                <ActivityIndicator size="small" color={colors.brand} />
              ) : (
                <Text style={styles.syncButtonText}>立即同步</Text>
              )}
            </TouchableOpacity>
          </View>

          <Text style={styles.sectionLabel}>系统健康</Text>
          <View style={[styles.healthCard, shadow.card]}>
            <View style={styles.healthTopRow}>
              <View>
                <Text style={styles.healthTitle}>
                  {systemHealth.syncFreezeState !== "ready"
                    ? "同步已冻结"
                    : combinedNeedsAttention > 0
                    ? "需处理"
                    : systemHealth.syncStatus === "syncing"
                      ? "同步中"
                      : "正常"}
                </Text>
                <Text style={styles.healthSubtitle}>
                  最近同步 {formatLocalTime(systemHealth.lastSyncTime)}
                </Text>
              </View>
              <View style={styles.healthBadge}>
                <Text style={styles.healthBadgeText}>
                  待处理 {combinedPendingTotal}
                </Text>
              </View>
            </View>

            {systemHealth.syncFreezeState !== "ready" ? (
              <View style={styles.healthNoticeRow}>
                <AlertCircle size={14} color={colors.error} />
                <Text style={styles.healthNoticeText}>
                  {systemHealth.freezeSummary}
                  {systemHealth.syncFreezeDetail ? ` · ${systemHealth.syncFreezeDetail}` : ""}
                </Text>
              </View>
            ) : null}

            <View style={styles.healthMetricsRow}>
              <View style={styles.healthMetricPill}>
                <Text style={styles.healthMetricLabel}>队列</Text>
                <Text style={styles.healthMetricValue}>{combinedQueuedCount}</Text>
              </View>
              <View style={styles.healthMetricPill}>
                <Text style={styles.healthMetricLabel}>进行中</Text>
                <Text style={styles.healthMetricValue}>{combinedProcessingCount}</Text>
              </View>
              <View style={styles.healthMetricPill}>
                <Text style={styles.healthMetricLabel}>需处理</Text>
                <Text style={[styles.healthMetricValue, combinedNeedsAttention > 0 && styles.healthMetricValueDanger]}>
                  {combinedNeedsAttention}
                </Text>
              </View>
            </View>

            <View style={styles.healthBackendPanel}>
              <Text style={styles.healthDebugSectionTitle}>当前后端能力</Text>
              <Text style={styles.healthDebugMeta}>baseUrl={systemHealth.backendBaseUrl}</Text>
              {systemHealth.backendCapabilities ? (
                <>
                  <Text style={styles.healthDebugMeta}>
                    consult={systemHealth.backendCapabilities.consultationChat ? "ready" : "unavailable"}
                    {` · workspace=${systemHealth.backendCapabilities.clientWorkspace ? "ready" : "route_unavailable"}`}
                    {` · cockpit=${systemHealth.backendCapabilities.strategicCockpit ? "ready" : "route_unavailable"}`}
                  </Text>
                  <Text style={styles.healthDebugMeta}>
                    mirror={systemHealth.backendCapabilities.knowledgeMirror ? "ready" : "data_missing"}
                    {` · contextBundle=${systemHealth.backendCapabilities.contextBundle ? "ready" : "unavailable"}`}
                    {` · payload=${systemHealth.backendCapabilities.consultationPayloadVersion}`}
                  </Text>
                  <Text style={styles.healthDebugMeta}>
                    最近探测 {formatLocalTime(systemHealth.lastCapabilityProbeAt)}
                  </Text>
                </>
              ) : (
                <Text style={[styles.healthDebugMeta, styles.healthDebugMetaDanger]}>
                  能力探测失败：{systemHealth.backendCapabilitiesError ?? "无法确认当前后端是否支持 workspace / cockpit / context bundle"}
                </Text>
              )}
            </View>

            <View style={styles.healthActionRow}>
              <TouchableOpacity
                style={styles.healthActionButton}
                disabled={!systemHealth.freezeActionLabel}
                onPress={() => {
                  if (systemHealth.isSyncPaused) {
                    systemHealth.resumeSync();
                  } else {
                    systemHealth.pauseSync();
                  }
                }}
              >
                {systemHealth.isSyncPaused ? (
                  <PlayCircle size={16} color={colors.brand} />
                ) : (
                  <PauseCircle size={16} color={colors.brand} />
                )}
                <Text style={styles.healthActionText}>
                  {systemHealth.freezeActionLabel ?? "同步已冻结"}
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.healthActionButton}
                onPress={() => { void systemHealth.retryAllFailed(); }}
                disabled={combinedNeedsAttention === 0}
              >
                <RefreshCw size={16} color={combinedNeedsAttention === 0 ? colors.textTertiary : colors.brand} />
                <Text style={[styles.healthActionText, combinedNeedsAttention === 0 && styles.healthActionTextDisabled]}>
                  重试失败项
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.healthActionButton}
                onPress={() => {
                  void systemHealth.clearSafeArtifacts().then((result) => {
                    Alert.alert(
                      "已清理",
                      `已清理 ${result.clearedTaskServerShadows} 条可安全删除的同步影子记录。`,
                    );
                  });
                }}
              >
                <RefreshCw size={16} color={colors.brand} />
                <Text style={styles.healthActionText}>清理安全缓存</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.healthActionButton}
                onPress={() => {
                  void systemHealth.exportDiagnostics().then(({ filePath, bundle }) => {
                    Alert.alert(
                      "诊断包已导出",
                      `已保存到：\n${filePath}\n\n最近 sync 事件：${bundle.recentSyncEvents.length} 条\n待同步操作：${bundle.pendingSummary.total} 条`,
                    );
                  }).catch((error: unknown) => {
                    Alert.alert(
                      "导出失败",
                      error instanceof Error ? error.message : "无法导出诊断包。",
                    );
                  });
                }}
              >
                <Download size={16} color={colors.brand} />
                <Text style={styles.healthActionText}>导出诊断包</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.healthActionButton}
                onPress={() => {
                  void systemHealth.refreshBackendCapabilities();
                }}
              >
                <RefreshCw size={16} color={colors.brand} />
                <Text style={styles.healthActionText}>刷新后端能力</Text>
              </TouchableOpacity>
            </View>

            <View style={styles.healthDebugPanel}>
              <Text style={styles.healthDebugSectionTitle}>高级诊断</Text>
              <Text style={styles.healthDebugMeta}>
                scope={systemHealth.accountScopeKey} · integrity={systemHealth.integrityStatus}
                {systemHealth.integrityReason ? ` · ${systemHealth.integrityReason}` : ""}
              </Text>
              <Text style={styles.healthDebugMeta}>
                freeze={systemHealth.syncFreezeState}
                {systemHealth.syncFreezeDetail ? ` · ${systemHealth.syncFreezeDetail}` : ""}
                {` · shadow=${systemHealth.taskServerShadowCount}`}
                {` · staleShadow=${systemHealth.staleTaskServerShadowCount}`}
              </Text>
              <View style={styles.healthSubsection}>
                <Text style={styles.healthDebugSectionTitle}>Lane 诊断</Text>
                {Object.values(systemHealth.laneDiagnostics).map((lane) => (
                  <View key={lane.lane} style={styles.healthDebugRow}>
                    <View style={styles.healthDebugCopy}>
                      <Text style={styles.healthDebugTitle}>{lane.lane}</Text>
                      <Text style={styles.healthDebugMeta}>
                        total={lane.total}
                        {` · oldest=${formatAgeMs(lane.oldestAgeMs)}`}
                        {` · active=${lane.active ? "yes" : "no"}`}
                        {lane.topReasonCode ? ` · top1=${formatLegacyUploadReason(lane.topReasonCode)}` : ""}
                      </Text>
                    </View>
                  </View>
                ))}
              </View>
              {systemHealth.blockedReason ? (
                <Text style={[styles.healthDebugMeta, styles.healthDebugMetaDanger]}>
                  同步冻结：{systemHealth.blockedReason}
                </Text>
              ) : null}
              {(
                Object.entries(systemHealth.runtimeFlags) as Array<[keyof typeof systemHealth.runtimeFlags, boolean]>
              ).map(([name, enabled]) => (
                <View key={name} style={styles.healthFlagRow}>
                  <Text style={styles.healthFlagLabel}>{name}</Text>
                  <TouchableOpacity
                    style={[styles.healthFlagToggle, enabled ? styles.healthFlagToggleEnabled : styles.healthFlagToggleDisabled]}
                    onPress={() => { void systemHealth.setRuntimeFlag(name, !enabled); }}
                  >
                    <Text style={[styles.healthFlagToggleText, !enabled && styles.healthFlagToggleTextDisabled]}>
                      {enabled ? "已开启" : "已关闭"}
                    </Text>
                  </TouchableOpacity>
                </View>
              ))}
            </View>

            {systemHealth.recentPendingOps.length > 0 ? (
              <View style={styles.healthDebugList}>
                {systemHealth.recentPendingOps.slice(0, 4).map((op) => (
                  <View key={op.clientOpId} style={styles.healthDebugRow}>
                    <View style={styles.healthDebugCopy}>
                      <Text style={styles.healthDebugTitle}>
                        {op.entityType}:{op.operation}
                      </Text>
                      <Text style={styles.healthDebugMeta}>
                        lane={op.lane} · status={op.status}
                        {` · retry=${op.retryCount}`}
                        {` · age=${formatPendingAge(op.updatedAt ?? op.createdAt)}`}
                        {op.reasonCode ? ` · ${op.reasonCode}` : ""}
                      </Text>
                    </View>
                    {op.status === "needs_attention" ? (
                      <TouchableOpacity onPress={() => { void systemHealth.retryOne(op.id); }}>
                        <AlertCircle size={16} color={colors.error} />
                      </TouchableOpacity>
                    ) : null}
                  </View>
                ))}
              </View>
            ) : null}

            {systemHealth.taskConflicts.length > 0 ? (
              <View style={styles.healthDebugList}>
                <Text style={styles.healthDebugSectionTitle}>冲突恢复</Text>
                {systemHealth.taskConflicts.map((conflict) => (
                  <View key={conflict.taskId} style={styles.healthConflictCard}>
                    <Text style={styles.healthDebugTitle}>{conflict.title}</Text>
                    <Text style={styles.healthDebugMeta}>
                      {formatPendingOperationLabel(conflict.pendingOperation)}
                      {` · ${formatPendingAge(conflict.pendingUpdatedAt)}`}
                      {` · ${formatSyncReasonCode(conflict.syncReasonCode)}`}
                    </Text>
                    <Text style={styles.healthDebugMeta}>
                      {conflict.hasServerShadow
                        ? `已缓存服务器快照${conflict.serverVersion != null ? ` · v${conflict.serverVersion}` : ""}`
                        : "尚未缓存服务器快照，暂时不能恢复服务器版本"}
                      {conflict.lastError ? ` · ${conflict.lastError}` : ""}
                    </Text>
                    <View style={styles.healthConflictActions}>
                      <TouchableOpacity
                        style={[
                          styles.healthConflictButton,
                          conflict.hasServerShadow
                            ? styles.healthConflictButtonDanger
                            : styles.healthConflictButtonDisabled,
                        ]}
                        disabled={!conflict.hasServerShadow}
                        onPress={() => {
                          Alert.alert(
                            "恢复服务器版本",
                            `这会丢弃「${conflict.title}」的本地未同步修改，并恢复到最近一次拉取到手机的服务器版本。`,
                            [
                              { text: "取消", style: "cancel" },
                              {
                                text: "恢复",
                                style: "destructive",
                                onPress: () => {
                                  void systemHealth.restoreTaskConflict(conflict.taskId).then((result) => {
                                    if (!result.restored) {
                                      Alert.alert("无法恢复", "当前没有可用的服务器快照。");
                                      return;
                                    }
                                    Alert.alert(
                                      "已恢复服务器版本",
                                      `已清理 ${result.clearedPendingOps} 条本地待同步修改，并恢复服务器版本。`,
                                    );
                                  }).catch((error: unknown) => {
                                    Alert.alert(
                                      "恢复失败",
                                      error instanceof Error ? error.message : "无法恢复服务器版本。",
                                    );
                                  });
                                },
                              },
                            ],
                          );
                        }}
                      >
                        <Text
                          style={[
                            styles.healthConflictButtonText,
                            conflict.hasServerShadow
                              ? styles.healthConflictButtonTextDanger
                              : styles.healthConflictButtonTextDisabled,
                          ]}
                        >
                          恢复服务器版本
                        </Text>
                      </TouchableOpacity>
                      <TouchableOpacity
                        style={[styles.healthConflictButton, styles.healthConflictButtonPrimary]}
                        onPress={() => {
                          void systemHealth.retryTaskConflict(conflict.taskId).then(() => {
                            Alert.alert("已重试", `已保留「${conflict.title}」的本地修改并重新进入同步队列。`);
                          }).catch((error: unknown) => {
                            Alert.alert(
                              "重试失败",
                              error instanceof Error ? error.message : "无法重新加入同步队列。",
                            );
                          });
                        }}
                      >
                        <Text style={[styles.healthConflictButtonText, styles.healthConflictButtonTextPrimary]}>
                          保留本地并重试
                        </Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                ))}
              </View>
            ) : null}

            {systemHealth.legacyUploadOps.length > 0 ? (
              <View style={styles.healthDebugList}>
                <Text style={styles.healthDebugSectionTitle}>附件 / 录音上传</Text>
                {systemHealth.legacyUploadOps.map((op) => (
                  <View key={op.opId} style={styles.healthDebugRow}>
                    <View style={styles.healthDebugCopy}>
                      <Text style={styles.healthDebugTitle}>
                        {op.displayTitle || op.objectType}
                      </Text>
                      <Text style={styles.healthDebugMeta}>
                        lane={op.lane} · status={op.status}
                        {` · retry=${op.retryCount}`}
                        {` · age=${formatAgeMs(op.ageMs)}`}
                        {` · ${formatLegacyUploadReason(op.reasonCode)}`}
                      </Text>
                    </View>
                    {op.status !== "processing" ? (
                      <TouchableOpacity onPress={() => { void systemHealth.retryLegacyUploadOp(op.opId); }}>
                        <RefreshCw
                          size={16}
                          color={op.status === "needs_attention" ? colors.error : colors.brand}
                        />
                      </TouchableOpacity>
                    ) : null}
                  </View>
                ))}
              </View>
            ) : null}
          </View>

          {/* Settings section 1: 业务模块偏好 */}
          <Text style={styles.sectionLabel}>业务模块偏好</Text>
          <View style={[styles.settingsCard, shadow.card]}>
            <SettingsRow
              iconBg={colors.accentBg2}
              icon={<CheckSquare size={18} color={colors.accent} />}
              title="任务与工作台"
              subtitle="复盘提醒、任务默认优先级"
              onPress={() => setActiveSettings("tasks")}
            />
            <View style={styles.separator} />
            <SettingsRow
              iconBg={colors.brandBg2}
              icon={<CalendarDays size={18} color={colors.brand} />}
              title="日历与日程"
              subtitle="工作时段设置"
              onPress={() => setActiveSettings("calendar")}
            />
            <View style={styles.separator} />
            <SettingsRow
              iconBg="rgba(16,185,129,0.14)"
              icon={<Bot size={18} color="#10B981" />}
              title="AI 助手与录音"
              subtitle="转写偏好、总结模板、默认归档"
              onPress={() => setActiveSettings("ai")}
            />
          </View>

          {/* Settings section 2: 账号与系统 */}
          <Text style={styles.sectionLabel}>账号与系统</Text>
          <View style={[styles.settingsCard, shadow.card]}>
            <SettingsRow
              iconBg={colors.surfaceSecondary}
              icon={<Smartphone size={18} color={colors.textSecondary} />}
              title="账号设置"
              subtitle=""
              onPress={() => setActiveSettings("account")}
              rightText={displayEmail}
            />
            <View style={styles.separator} />
            <SettingsRow
              iconBg={colors.surfaceSecondary}
              icon={<MessageSquare size={18} color={colors.textSecondary} />}
              title="飞书绑定"
              subtitle=""
              onPress={handleOpenFeishuBinding}
              rightText={feishuBindingRightText}
            />
            <View style={styles.separator} />
            <SettingsRow
              iconBg={colors.surfaceSecondary}
              icon={<Bell size={18} color={colors.textSecondary} />}
              title="系统通知权限"
              subtitle=""
              onPress={handleOpenNotificationSettings}
              rightText="前往设置"
            />
          </View>

          {/* Logout */}
          <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
            <Text style={styles.logoutText}>退出登录</Text>
          </TouchableOpacity>
          <Text style={styles.versionText}>益语智库 v1.0.4</Text>
        </ScrollView>
      </SafeAreaView>

      {/* Settings sub-page modals */}
      <Modal
        visible={activeSettings === "account"}
        animationType="slide"
        presentationStyle="fullScreen"
        onRequestClose={closeSettings}
      >
        <SettingsAccount onClose={closeSettings} user={user} />
      </Modal>
      <Modal
        visible={activeSettings === "tasks"}
        animationType="slide"
        presentationStyle="fullScreen"
        onRequestClose={closeSettings}
      >
        <SettingsTasks onClose={closeSettings} />
      </Modal>
      <Modal
        visible={activeSettings === "calendar"}
        animationType="slide"
        presentationStyle="fullScreen"
        onRequestClose={closeSettings}
      >
        <SettingsCalendar onClose={closeSettings} />
      </Modal>
      <Modal
        visible={activeSettings === "ai"}
        animationType="slide"
        presentationStyle="fullScreen"
        onRequestClose={closeSettings}
      >
        <SettingsAI onClose={closeSettings} />
      </Modal>

      {/* Edit profile modal */}
      <Modal
        visible={showEditProfile}
        transparent
        animationType="fade"
        onRequestClose={() => setShowEditProfile(false)}
      >
        <View style={styles.editOverlay}>
          <View style={styles.editCard}>
            <Text style={styles.editTitle}>编辑个人信息</Text>

            <Text style={styles.editLabel}>名称</Text>
            <TextInput
              style={styles.editInput}
              value={editName}
              onChangeText={setEditName}
              placeholder="输入你的名称"
              placeholderTextColor={colors.textTertiary}
              autoFocus
            />

            <Text style={styles.editLabel}>职位</Text>
            <TextInput
              style={styles.editInput}
              value={editRole}
              onChangeText={setEditRole}
              placeholder="输入你的职位"
              placeholderTextColor={colors.textTertiary}
            />

            <View style={styles.editActions}>
              <TouchableOpacity
                style={styles.editCancelButton}
                onPress={() => setShowEditProfile(false)}
              >
                <Text style={styles.editCancelText}>取消</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.editSaveButton, saving && { opacity: 0.6 }]}
                onPress={handleSaveProfile}
                disabled={saving}
              >
                {saving ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <Text style={styles.editSaveText}>保存</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    paddingHorizontal: spacing.lg,
  },
  // Profile card
  profileCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.xl,
  },
  profileRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  avatarContainer: {
    position: "relative",
    marginRight: spacing.lg,
  },
  avatar: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: colors.brand,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarText: {
    fontSize: fontSize.xxl,
    fontWeight: "700",
    color: colors.textOnBrand,
  },
  cameraOverlay: {
    position: "absolute",
    bottom: -2,
    right: -2,
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1.5,
    borderColor: colors.borderLight,
  },
  cameraIcon: {
    fontSize: 12,
  },
  profileInfo: {
    flex: 1,
  },
  nameRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  profileName: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.text,
  },
  editButton: {
    padding: spacing.xs,
  },
  editIcon: {
    fontSize: 16,
    color: colors.textSecondary,
  },
  profileTitle: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    marginTop: 2,
  },
  searchButton: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
  },
  searchIcon: {
    fontSize: 18,
  },

  // Sync card
  syncCard: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: "#EFF6FF",
    borderWidth: 1,
    borderColor: "#DBEAFE",
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginTop: spacing.md,
  },
  syncLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  syncCloudIcon: {
    fontSize: 22,
  },
  syncText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.text,
  },
  syncTime: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 1,
  },
  syncButton: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  syncButtonText: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.brand,
  },

  healthCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginTop: spacing.xs,
  },
  healthTopRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  healthTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.text,
  },
  healthSubtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  healthBadge: {
    backgroundColor: colors.brandBg,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  healthBadgeText: {
    fontSize: fontSize.sm,
    color: colors.brand,
    fontWeight: "700",
  },
  healthMetricsRow: {
    flexDirection: "row",
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  healthNoticeRow: {
    marginTop: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: "rgba(239,68,68,0.08)",
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  healthNoticeText: {
    flex: 1,
    fontSize: fontSize.sm,
    color: colors.error,
    fontWeight: "600",
  },
  healthMetricPill: {
    flex: 1,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
  },
  healthMetricLabel: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  healthMetricValue: {
    marginTop: 2,
    fontSize: fontSize.lg,
    color: colors.text,
    fontWeight: "700",
  },
  healthMetricValueDanger: {
    color: colors.error,
  },
  healthBackendPanel: {
    marginTop: spacing.md,
    padding: spacing.md,
    borderRadius: borderRadius.md,
    backgroundColor: colors.surfaceSecondary,
    gap: spacing.xs,
  },
  healthActionRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  healthActionButton: {
    minWidth: "31%",
    flexGrow: 1,
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: colors.borderLight,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.surface,
  },
  healthActionText: {
    fontSize: fontSize.sm,
    color: colors.brand,
    fontWeight: "600",
  },
  healthActionTextDisabled: {
    color: colors.textTertiary,
  },
  healthDebugPanel: {
    marginTop: spacing.md,
    padding: spacing.md,
    borderRadius: borderRadius.md,
    backgroundColor: colors.surfaceSecondary,
    gap: spacing.xs,
  },
  healthSubsection: {
    marginTop: spacing.xs,
    gap: spacing.xs,
  },
  healthDebugSectionTitle: {
    fontSize: fontSize.sm,
    fontWeight: "700",
    color: colors.text,
  },
  healthDebugList: {
    marginTop: spacing.md,
    gap: spacing.sm,
  },
  healthDebugMetaDanger: {
    color: colors.error,
  },
  healthDebugRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacing.xs,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.borderLight,
  },
  healthDebugCopy: {
    flex: 1,
    paddingRight: spacing.sm,
  },
  healthDebugTitle: {
    fontSize: fontSize.sm,
    color: colors.text,
    fontWeight: "600",
  },
  healthDebugMeta: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    marginTop: 2,
  },
  healthConflictCard: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.borderLight,
    paddingTop: spacing.sm,
    gap: spacing.xs,
  },
  healthConflictActions: {
    flexDirection: "row",
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  healthConflictButton: {
    flex: 1,
    borderRadius: borderRadius.md,
    paddingVertical: 10,
    paddingHorizontal: spacing.md,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
  },
  healthConflictButtonPrimary: {
    backgroundColor: colors.brandBg,
    borderColor: colors.brand,
  },
  healthConflictButtonDanger: {
    backgroundColor: "rgba(239,68,68,0.08)",
    borderColor: "rgba(239,68,68,0.28)",
  },
  healthConflictButtonDisabled: {
    backgroundColor: colors.surfaceSecondary,
    borderColor: colors.borderLight,
  },
  healthConflictButtonText: {
    fontSize: fontSize.xs,
    fontWeight: "700",
  },
  healthConflictButtonTextPrimary: {
    color: colors.brand,
  },
  healthConflictButtonTextDanger: {
    color: colors.error,
  },
  healthConflictButtonTextDisabled: {
    color: colors.textTertiary,
  },
  healthFlagRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  healthFlagLabel: {
    flex: 1,
    fontSize: fontSize.xs,
    color: colors.textSecondary,
  },
  healthFlagToggle: {
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  healthFlagToggleEnabled: {
    backgroundColor: colors.brandBg,
  },
  healthFlagToggleDisabled: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  healthFlagToggleText: {
    fontSize: fontSize.xs,
    color: colors.brand,
    fontWeight: "700",
  },
  healthFlagToggleTextDisabled: {
    color: colors.textSecondary,
  },

  // Section label
  sectionLabel: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.textSecondary,
    marginTop: spacing.xl,
    marginBottom: spacing.sm,
    marginLeft: spacing.xs,
  },

  // Settings card
  settingsCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  settingsRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacing.md,
  },
  settingsIconBg: {
    width: 36,
    height: 36,
    borderRadius: borderRadius.sm,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.md,
  },
  settingsIcon: {
    fontSize: 18,
  },
  settingsTextContainer: {
    flex: 1,
  },
  settingsTitle: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.text,
  },
  settingsSubtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 1,
  },
  settingsRightText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    maxWidth: 140,
    textAlign: "right",
  },
  chevron: {
    fontSize: 22,
    color: colors.textTertiary,
  },
  separator: {
    height: 0.5,
    backgroundColor: colors.borderLight,
    marginLeft: 52,
  },

  // Logout
  logoutButton: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    paddingVertical: spacing.lg,
    alignItems: "center",
    marginTop: spacing.xxl,
    borderWidth: 1,
    borderColor: "rgba(239,68,68,0.2)",
  },
  logoutText: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.error,
  },
  versionText: {
    textAlign: "center",
    fontSize: fontSize.sm,
    color: colors.textTertiary,
    marginTop: spacing.md,
    marginBottom: spacing.lg,
  },

  // Edit profile modal
  editOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.4)",
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.xl,
  },
  editCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.xl,
    width: "100%",
    maxWidth: 360,
    ...shadow.elevated,
  },
  editTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.text,
    marginBottom: spacing.xl,
    textAlign: "center",
  },
  editLabel: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.textSecondary,
    marginBottom: spacing.xs,
    marginTop: spacing.md,
  },
  editInput: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: 12,
    fontSize: fontSize.md,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
  },
  editActions: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: spacing.md,
    marginTop: spacing.xl,
  },
  editCancelButton: {
    paddingHorizontal: spacing.xl,
    paddingVertical: 10,
    borderRadius: borderRadius.md,
    backgroundColor: colors.surfaceSecondary,
  },
  editCancelText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.textSecondary,
  },
  editSaveButton: {
    paddingHorizontal: spacing.xl,
    paddingVertical: 10,
    borderRadius: borderRadius.md,
    backgroundColor: colors.brand,
    minWidth: 72,
    alignItems: "center",
  },
  editSaveText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.textOnBrand,
  },
});
~~~

## `mobile/app/(tabs)/tasks.tsx`

- 编码: `utf-8`

~~~tsx
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Animated,
  GestureResponderEvent,
  NativeSyntheticEvent,
  NativeTouchEvent,
  PanResponder,
  Platform,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import * as Haptics from "expo-haptics";
import { useAndroidExitApp } from "../../lib/android-back";
import { useAppChromeInsets } from "../../lib/app-chrome";
import * as localDb from "../../lib/local-db";
import type { SmartTaskDraft, TaskBoardResponse, TaskRecord } from "../../lib/types";
import { borderRadius, colors, shadow } from "../../lib/theme";
import { ChevronRight, ChevronDown, Inbox, Check } from "lucide-react-native";
import {
  flushQueuedSmartInputDrafts,
  getQueuedSmartInputCount,
  clearSmartInputQueue,
} from "../../lib/smart-input-queue";
import { formatLocalDateKey, getLocalWeekRangeKeys } from "../../lib/date";
import {
  buildRecoveredDraftKey,
  shouldAttemptSmartInputRecovery,
  shouldAutoOpenRecoveredDraft,
  shouldUseRecoveredDraft,
  type RecoveryTrigger,
} from "../../lib/smart-input-recovery";
import { useTaskBoard } from "../../lib/task-board-store";
import { useRenderCount } from "../../lib/use-render-count";
import { devLog } from "../../lib/dev-log";
import {
  deleteTaskOfflineFirst,
  updateTaskOfflineFirst,
} from "../../lib/sync-engine";
import {
  moveTaskToCalendarTarget,
  updateCalendarTaskSchedule,
} from "../../lib/calendar-repository";
import { useCurrentFocus } from "../../lib/current-focus-store";
import { useClientIntel } from "../../lib/client-intel-store";
import { transferEventLineToClient } from "../../lib/event-line-client-transfer";
import EventLineDrawer from "../../components/EventLineDrawer";
import WorkspaceLiteSheet from "../../components/WorkspaceLiteSheet";
import FocusBar from "../../components/FocusBar";
import TaskSyncBadge from "../../components/TaskSyncBadge";
import TasksHeader from "../../components/tasks-screen/TasksHeader";
import TasksFilterBar from "../../components/tasks-screen/TasksFilterBar";
import InboxTaskList from "../../components/tasks-screen/InboxTaskList";
import ScheduledTaskList from "../../components/tasks-screen/ScheduledTaskList";
import SmartInputRecoveryController from "../../components/tasks-screen/SmartInputRecoveryController";
import TaskModalCoordinator from "../../components/tasks-screen/TaskModalCoordinator";
import DragCalendarOverlay from "../../components/tasks-screen/DragCalendarOverlay";
import {
  buildFocusMatchedTaskIds,
  buildFocusTaskStats,
  filterTasksByFocus,
  isLockedFocus,
  sortTasksByFocusPriority,
} from "../../lib/focus-selectors";

// ─── Constants ─────────────────────────────────

type FilterKey = "today" | "collab_inbox" | "unreviewed" | "all";

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "today", label: "今日任务" },
  { key: "collab_inbox", label: "协作收件箱" },
  { key: "unreviewed", label: "未复盘" },
  { key: "all", label: "全部任务" },
];

const SWIPE_ACTION_WIDTH = 92;
const SWIPE_OPEN_THRESHOLD = 28;
const DRAG_DOT_SIZE = 52;
const DRAG_DOT_FINGER_OFFSET_Y = 60;
const DRAG_CANCEL_DISTANCE = 8;

type SwipeActionDirection = "edit" | "delete" | null;

// ─── Helpers ───────────────────────────────────

function formatDate(): string {
  const d = new Date();
  const weekdays = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];
  return `${d.getMonth() + 1}月${d.getDate()}日 · ${weekdays[d.getDay()]}`;
}

function formatDateKey(date: Date): string {
  return formatLocalDateKey(date);
}

function parseDueDateForDisplay(dueDate: string): Date | null {
  if (dueDate.includes("T")) {
    const dateTime = new Date(dueDate);
    return Number.isNaN(dateTime.getTime()) ? null : dateTime;
  }

  const match = dueDate.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return null;

  const [, year, month, day] = match;
  const dateOnly = new Date(Number(year), Number(month) - 1, Number(day));
  return Number.isNaN(dateOnly.getTime()) ? null : dateOnly;
}

function formatTimeLabel(dueDate: string): string {
  const d = parseDueDateForDisplay(dueDate);
  if (Number.isNaN(d.getTime())) return "";

  const todayKey = formatDateKey(new Date());
  const taskDateKey = formatDateKey(d);
  if (taskDateKey === todayKey && dueDate.includes("T")) {
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  }
  if (taskDateKey === todayKey) return "今天";

  const currentYear = new Date().getFullYear();
  if (d.getFullYear() === currentYear) {
    return `${d.getMonth() + 1}月${d.getDate()}日`;
  }
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function resolveSwipeOffset(direction: SwipeActionDirection): number {
  if (direction === "edit") return SWIPE_ACTION_WIDTH;
  if (direction === "delete") return -SWIPE_ACTION_WIDTH;
  return 0;
}

function isCollabInboxTask(task: TaskRecord): boolean {
  return task.viewerInboxStatus === "pending";
}

function buildTaskMeta(task: TaskRecord): string {
  if (isCollabInboxTask(task)) {
    const assigner =
      task.ownerName ||
      task.collaborators?.find((item) => item.isOwner)?.fullName ||
      null;
    const base = assigner ? `协作待确认 · ${assigner}` : "协作待确认";
    if (task.clientName) return `${base} · 客户：${task.clientName}`;
    if (task.eventLineName) return `${base} · ${task.eventLineName}`;
    if (task.listName) return `${base} · ${task.listName}`;
    return base;
  }
  return (
    task.description ||
    (task.clientName ? `客户：${task.clientName}` : task.eventLineName ? task.eventLineName : task.listName)
  );
}

function hasScheduledDate(task: TaskRecord): boolean {
  return Boolean(task.dueDate && task.dueDate.trim().length > 0);
}

// ─── ScheduledCardWithDrag ─────────────────────
// Lightweight wrapper that adds long-press → drag-to-calendar on scheduled cards.

interface ScheduledCardWithDragProps {
  task: TaskRecord;
  isDone: boolean;
  isFocusMatched?: boolean;
  onPress: () => void;
  onToggleComplete?: () => void;
  onOpenEventLine?: () => void;
  onDragStart?: (task: TaskRecord, pageX: number, pageY: number) => void;
  onDragMove?: (pageX: number, pageY: number) => void;
  onDragEnd?: () => void;
}

function ScheduledCardWithDrag({
  task,
  isDone,
  isFocusMatched = false,
  onPress,
  onToggleComplete,
  onOpenEventLine,
  onDragStart,
  onDragMove,
  onDragEnd,
}: ScheduledCardWithDragProps) {
  const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dragActivatedRef = useRef(false);
  const touchStartRef = useRef({ x: 0, y: 0 });
  const lastTouchRef = useRef({ x: 0, y: 0 });

  const clearLongPressTimer = useCallback(() => {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }
  }, []);

  const handleTouchStart = useCallback((event: NativeSyntheticEvent<NativeTouchEvent>) => {
    const touch = event.nativeEvent.touches[0];
    if (!touch) return;
    touchStartRef.current = { x: touch.pageX, y: touch.pageY };
    lastTouchRef.current = { x: touch.pageX, y: touch.pageY };
    dragActivatedRef.current = false;
    clearLongPressTimer();
    longPressTimerRef.current = setTimeout(() => {
      dragActivatedRef.current = true;
      onDragStart?.(task, lastTouchRef.current.x, lastTouchRef.current.y);
    }, 260);
  }, [clearLongPressTimer, onDragStart, task]);

  const handleTouchMove = useCallback((event: NativeSyntheticEvent<NativeTouchEvent>) => {
    const touch = event.nativeEvent.touches[0];
    if (!touch) return;
    lastTouchRef.current = { x: touch.pageX, y: touch.pageY };
    if (dragActivatedRef.current) {
      onDragMove?.(touch.pageX, touch.pageY);
      return;
    }
    const dx = touch.pageX - touchStartRef.current.x;
    const dy = touch.pageY - touchStartRef.current.y;
    if (Math.abs(dx) > DRAG_CANCEL_DISTANCE || Math.abs(dy) > DRAG_CANCEL_DISTANCE) {
      clearLongPressTimer();
    }
  }, [clearLongPressTimer, onDragMove]);

  const handleTouchEnd = useCallback(() => {
    clearLongPressTimer();
    if (dragActivatedRef.current) {
      dragActivatedRef.current = false;
      onDragEnd?.();
    }
  }, [clearLongPressTimer, onDragEnd]);

  const handleTouchCancel = useCallback(() => {
    clearLongPressTimer();
  }, [clearLongPressTimer]);

  return (
    <View
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      onTouchCancel={handleTouchCancel}
    >
      <TouchableOpacity
        style={[s.scheduledCard, isFocusMatched && s.focusMatchedCard]}
        activeOpacity={0.78}
        onPress={() => { if (!dragActivatedRef.current) onPress(); }}
      >
        <TouchableOpacity
          style={[
            s.taskCompleteToggle,
            isDone && s.taskCompleteToggleDone,
          ]}
          activeOpacity={isDone ? 1 : 0.8}
          disabled={isDone || !onToggleComplete}
          onPress={(event) => {
            event.stopPropagation?.();
            onToggleComplete?.();
          }}
        >
          {isDone ? <Check size={13} strokeWidth={3} color="#FFFFFF" /> : null}
        </TouchableOpacity>
        <View style={s.scheduledCardBody}>
          <Text style={[s.scheduledCardTitle, isDone && s.scheduledCardTitleDone]} numberOfLines={1}>
            {task.title}
          </Text>
          {task.clientName && (
            <Text style={s.scheduledCardMeta} numberOfLines={1}>{task.clientName}</Text>
          )}
          <TaskSyncBadge task={task} compact style={s.taskSyncBadge} />
          {task.eventLineName && onOpenEventLine ? (
            <TouchableOpacity
              style={s.focusChip}
              activeOpacity={0.78}
              onPress={(event) => {
                event.stopPropagation?.();
                onOpenEventLine();
              }}
            >
              <Text style={s.focusChipText} numberOfLines={1}>{task.eventLineName}</Text>
            </TouchableOpacity>
          ) : null}
        </View>
        {task.dueDate && (
          <Text style={s.scheduledCardTime}>{formatTimeLabel(task.dueDate)}</Text>
        )}
        <ChevronRight size={16} strokeWidth={1.6} color="#CDD3DD" />
      </TouchableOpacity>
    </View>
  );
}

// ─── SwipeInboxCard ────────────────────────────

interface SwipeInboxCardProps {
  task: TaskRecord;
  isDone: boolean;
  isFocusMatched?: boolean;
  openDirection: SwipeActionDirection;
  onOpenDirectionChange: (direction: SwipeActionDirection) => void;
  onPress: () => void;
  onToggleComplete?: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onOpenEventLine?: () => void;
  onDragStart?: (task: TaskRecord, pageX: number, pageY: number) => void;
  onDragMove?: (pageX: number, pageY: number) => void;
  onDragEnd?: () => void;
}

function SwipeInboxCard({
  task,
  isDone,
  isFocusMatched = false,
  openDirection,
  onOpenDirectionChange,
  onPress,
  onToggleComplete,
  onEdit,
  onDelete,
  onOpenEventLine,
  onDragStart,
  onDragMove,
  onDragEnd,
}: SwipeInboxCardProps) {
  const translateX = useRef(new Animated.Value(resolveSwipeOffset(openDirection))).current;
  const gestureStartOffsetRef = useRef(resolveSwipeOffset(openDirection));
  const isCollabInbox = isCollabInboxTask(task);
  const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dragActivatedRef = useRef(false);
  const touchStartRef = useRef({ x: 0, y: 0 });
  const lastTouchRef = useRef({ x: 0, y: 0 });

  const clearLongPressTimer = useCallback(() => {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }
  }, []);

  useEffect(() => {
    Animated.spring(translateX, {
      toValue: resolveSwipeOffset(openDirection),
      useNativeDriver: true,
      speed: 24,
      bounciness: 4,
    }).start();
  }, [openDirection, translateX]);

  const swipeResponder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => false,
        onStartShouldSetPanResponderCapture: () => false,
        onMoveShouldSetPanResponder: (_, gestureState) =>
          !dragActivatedRef.current &&
          Math.abs(gestureState.dx) > Math.abs(gestureState.dy) + 6 && Math.abs(gestureState.dx) > 12,
        onPanResponderGrant: () => {
          clearLongPressTimer();
          gestureStartOffsetRef.current = resolveSwipeOffset(openDirection);
        },
        onPanResponderMove: (_, gestureState) => {
          if (dragActivatedRef.current) return;
          translateX.setValue(
            clamp(gestureStartOffsetRef.current + gestureState.dx, -SWIPE_ACTION_WIDTH, SWIPE_ACTION_WIDTH),
          );
        },
        onPanResponderRelease: (_, gestureState) => {
          if (dragActivatedRef.current) {
            return;
          }
          const nextOffset = clamp(
            gestureStartOffsetRef.current + gestureState.dx,
            -SWIPE_ACTION_WIDTH,
            SWIPE_ACTION_WIDTH,
          );
          if (nextOffset <= -SWIPE_OPEN_THRESHOLD) {
            onOpenDirectionChange("delete");
            void Haptics.selectionAsync();
            return;
          }
          if (nextOffset >= SWIPE_OPEN_THRESHOLD) {
            onOpenDirectionChange("edit");
            void Haptics.selectionAsync();
            return;
          }
          onOpenDirectionChange(null);
        },
        onPanResponderTerminate: () => {
          clearLongPressTimer();
          onOpenDirectionChange(null);
        },
      }),
    [clearLongPressTimer, onOpenDirectionChange, openDirection, translateX],
  );

  const swipeOpen = openDirection !== null;

  const handleTouchStart = useCallback((event: NativeSyntheticEvent<NativeTouchEvent>) => {
    if (swipeOpen) return;
    const touch = event.nativeEvent.touches[0];
    if (!touch) return;
    touchStartRef.current = { x: touch.pageX, y: touch.pageY };
    lastTouchRef.current = { x: touch.pageX, y: touch.pageY };
    dragActivatedRef.current = false;
    clearLongPressTimer();
    longPressTimerRef.current = setTimeout(() => {
      dragActivatedRef.current = true;
      onDragStart?.(task, lastTouchRef.current.x, lastTouchRef.current.y);
    }, 260);
  }, [clearLongPressTimer, onDragStart, swipeOpen, task]);

  const handleTouchMove = useCallback((event: NativeSyntheticEvent<NativeTouchEvent>) => {
    const touch = event.nativeEvent.touches[0];
    if (!touch) return;
    lastTouchRef.current = { x: touch.pageX, y: touch.pageY };
    if (dragActivatedRef.current) {
      onDragMove?.(touch.pageX, touch.pageY);
      return;
    }
    const dx = touch.pageX - touchStartRef.current.x;
    const dy = touch.pageY - touchStartRef.current.y;
    if (Math.abs(dx) > DRAG_CANCEL_DISTANCE || Math.abs(dy) > DRAG_CANCEL_DISTANCE) {
      clearLongPressTimer();
    }
  }, [clearLongPressTimer, onDragMove]);

  const handleTouchEnd = useCallback(() => {
    clearLongPressTimer();
    if (dragActivatedRef.current) {
      dragActivatedRef.current = false;
      onDragEnd?.();
    }
  }, [clearLongPressTimer, onDragEnd]);

  const handleTouchCancel = useCallback(() => {
    clearLongPressTimer();
    // Do not end an active drag on responder cancellation.
    // The parent scroll view / modal transition may transiently cancel the
    // original touch target before the user actually lifts the finger.
  }, [clearLongPressTimer]);

  return (
    <View style={s.swipeCardShell}>
      <View style={s.swipeActionsLayer} pointerEvents="box-none">
        <Animated.View
          style={[
            s.swipeAction,
            s.swipeActionEdit,
            {
              opacity: translateX.interpolate({
                inputRange: [0, SWIPE_ACTION_WIDTH],
                outputRange: [0, 1],
                extrapolate: "clamp",
              }),
            },
          ]}
          pointerEvents={openDirection === "edit" ? "auto" : "none"}
        >
          <TouchableOpacity style={StyleSheet.absoluteFill} activeOpacity={0.82} onPress={onEdit}>
            <View style={[s.swipeAction, s.swipeActionEdit, { position: "relative", width: "100%", height: "100%" }]}>
              <Text style={s.swipeActionText}>编辑</Text>
            </View>
          </TouchableOpacity>
        </Animated.View>
        <Animated.View
          style={[
            s.swipeAction,
            s.swipeActionDelete,
            {
              opacity: translateX.interpolate({
                inputRange: [-SWIPE_ACTION_WIDTH, 0],
                outputRange: [1, 0],
                extrapolate: "clamp",
              }),
            },
          ]}
          pointerEvents={openDirection === "delete" ? "auto" : "none"}
        >
          <TouchableOpacity style={StyleSheet.absoluteFill} activeOpacity={0.82} onPress={onDelete}>
            <View style={[s.swipeAction, s.swipeActionDelete, { position: "relative", width: "100%", height: "100%" }]}>
              <Text style={s.swipeActionText}>删除</Text>
            </View>
          </TouchableOpacity>
        </Animated.View>
      </View>
      <Animated.View
        style={[s.swipeCardWrap, { transform: [{ translateX }] }]}
        {...swipeResponder.panHandlers}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        onTouchCancel={handleTouchCancel}
      >
        <TouchableOpacity
          style={[s.inboxCard, isFocusMatched && s.focusMatchedCard]}
          activeOpacity={swipeOpen ? 1 : 0.72}
          onPress={() => {
            if (swipeOpen) {
              onOpenDirectionChange(null);
              return;
            }
            onPress();
          }}
        >
          {isCollabInbox ? (
            <View style={[s.inboxDot, { backgroundColor: isDone ? "#10B981" : "#7C3AED" }]} />
          ) : (
            <TouchableOpacity
              style={[
                s.taskCompleteToggle,
                isDone && s.taskCompleteToggleDone,
              ]}
              activeOpacity={isDone ? 1 : 0.8}
              disabled={isDone || !onToggleComplete}
              onPress={(event) => {
                event.stopPropagation?.();
                onToggleComplete?.();
              }}
            >
              {isDone ? <Check size={13} strokeWidth={3} color="#FFFFFF" /> : null}
            </TouchableOpacity>
          )}
          <View style={s.inboxCardBody}>
            <View style={s.inboxCardTitleRow}>
              <Text style={[s.inboxCardTitle, isDone && s.inboxCardTitleDone]} numberOfLines={2}>
                {task.title}
              </Text>
              {isCollabInbox ? (
                <View style={s.inboxStatusBadge}>
                  <Text style={s.inboxStatusBadgeText}>待确认</Text>
                </View>
              ) : null}
            </View>
            <Text style={s.inboxCardMeta} numberOfLines={2}>
              {buildTaskMeta(task)}
            </Text>
            <TaskSyncBadge task={task} compact style={s.taskSyncBadge} />
            {task.eventLineName && onOpenEventLine ? (
              <TouchableOpacity
                style={[s.focusChip, { marginTop: 8 }]}
                activeOpacity={0.78}
                onPress={(event) => {
                  event.stopPropagation?.();
                  onOpenEventLine();
                }}
              >
                <Text style={s.focusChipText} numberOfLines={1}>{task.eventLineName}</Text>
              </TouchableOpacity>
            ) : null}
          </View>
          <ChevronRight size={18} strokeWidth={1.9} color="#CDD3DD" />
        </TouchableOpacity>
      </Animated.View>
    </View>
  );
}

// ─── Main Component ────────────────────────────

export default function TasksScreen() {
  useRenderCount("TasksScreen");
  const chrome = useAppChromeInsets();
  const router = useRouter();
  const params = useLocalSearchParams<{ modal?: string; trigger?: string }>();
  const { board, isHydrated, refresh } = useTaskBoard();
  const {
    focus,
    clients,
    eventLines,
    setCurrentFocusBrowseFromTask,
    setCurrentFocusBrowseFromEventLine,
  } = useCurrentFocus();
  const clientIntel = useClientIntel(focus.clientId);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<FilterKey>("today");
  const [selectedTask, setSelectedTask] = useState<TaskRecord | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [showSmartInput, setShowSmartInput] = useState(false);
  const [showRecord, setShowRecord] = useState(false);
  const [recordTaskContext, setRecordTaskContext] = useState<TaskRecord | null>(null);
  const [reviewTaskContext, setReviewTaskContext] = useState<TaskRecord | null>(null);
  const [editingTask, setEditingTask] = useState<TaskRecord | null>(null);
  const [smartDraft, setSmartDraft] = useState<SmartTaskDraft | null>(null);
  const [createPreset, setCreatePreset] = useState<{ dueDate?: string; dueTime?: string }>({});
  const [smartInputPreset, setSmartInputPreset] = useState<{ dueDate?: string; dueTime?: string }>({});
  const [showFilterMenu, setShowFilterMenu] = useState(false);
  const [openSwipeTaskId, setOpenSwipeTaskId] = useState<string | null>(null);
  const [openSwipeDirection, setOpenSwipeDirection] = useState<SwipeActionDirection>(null);
  const [workspaceClientId, setWorkspaceClientId] = useState<string | null>(null);
  const [eventLineDrawerId, setEventLineDrawerId] = useState<string | null>(null);
  const [transferringEventLineId, setTransferringEventLineId] = useState<string | null>(null);
  const [showAllForFocus, setShowAllForFocus] = useState(false);

  // ─── Drag-to-calendar state (declarations only — callbacks below) ──
  const [dragTask, setDragTask] = useState<TaskRecord | null>(null);
  const [dragCalendarMonth, setDragCalendarMonth] = useState(() => { const d = new Date(); return { year: d.getFullYear(), month: d.getMonth() }; });
  const [dragHoveredDate, setDragHoveredDate] = useState<string | null>(null);
  const dragDateRefs = useRef<Map<string, View>>(new Map());
  const dragDateLayouts = useRef<Map<string, { x: number; y: number; w: number; h: number }>>(new Map());
  const dragTranslate = useRef(new Animated.ValueXY({ x: 0, y: 0 })).current;
  const dragOpacity = useRef(new Animated.Value(0)).current;
  const dragScale = useRef(new Animated.Value(0.72)).current;

  const handledModalTriggerRef = useRef<string | null>(null);
  const smartInputRecoveryInFlightRef = useRef(false);
  const lastRecoveryAttemptAtRef = useRef<number | null>(null);
  const lastRecoveredDraftKeyRef = useRef<string | null>(null);
  const recoveryRequestVersionRef = useRef(0);
  const queuedCountRequestVersionRef = useRef(0);
  const lastQueuedCountRef = useRef(0);
  const [queuedDraftCount, setQueuedDraftCount] = useState(0);
  const [queuedRecoveryDismissed, setQueuedRecoveryDismissed] = useState(false);
  const [isRecoveringDraft, setIsRecoveringDraft] = useState(false);

  const refreshQueuedDraftCount = useCallback(async () => {
    const requestVersion = ++queuedCountRequestVersionRef.current;
    try {
      const nextCount = await getQueuedSmartInputCount();
      if (requestVersion !== queuedCountRequestVersionRef.current) {
        return;
      }
      setQueuedDraftCount(nextCount);
    } catch {}
  }, []);

  const hasBlockingUi = showSmartInput || showRecord || showCreate || Boolean(selectedTask) || Boolean(reviewTaskContext);

  const recoverQueuedSmartInput = useCallback(async (trigger: RecoveryTrigger) => {
    if (hasBlockingUi) {
      devLog("smartInputRecovery", "skipped.blocking_ui", { trigger });
      return false;
    }
    const nowMs = Date.now();
    if (!shouldAttemptSmartInputRecovery({
      trigger,
      queuedCount: queuedDraftCount,
      inFlight: smartInputRecoveryInFlightRef.current,
      nowMs,
      lastAttemptAt: lastRecoveryAttemptAtRef.current,
    })) {
      devLog("smartInputRecovery", "skipped.guard", { trigger, queuedDraftCount });
      return false;
    }

    devLog("smartInputRecovery", "attempt", { trigger, queuedDraftCount });
    lastRecoveryAttemptAtRef.current = nowMs;
    smartInputRecoveryInFlightRef.current = true;
    const requestVersion = recoveryRequestVersionRef.current;
    setIsRecoveringDraft(true);
    try {
      const recovered = await flushQueuedSmartInputDrafts(1);
      await refreshQueuedDraftCount();
      if (requestVersion !== recoveryRequestVersionRef.current) {
        devLog("smartInputRecovery", "skipped.stale_request", { trigger });
        return false;
      }
      const recoveredDraft = recovered[0]?.draft ?? null;
      if (!recoveredDraft) {
        devLog("smartInputRecovery", "empty", { trigger });
        return false;
      }

      const recoveredDraftKey = buildRecoveredDraftKey(recoveredDraft);
      if (!shouldUseRecoveredDraft(recoveredDraftKey, lastRecoveredDraftKeyRef.current)) {
        devLog("smartInputRecovery", "skipped.duplicate", { trigger });
        return false;
      }
      lastRecoveredDraftKeyRef.current = recoveredDraftKey;

      setEditingTask(null);
      setSmartDraft(recoveredDraft);
      setCreatePreset({
        dueDate: recoveredDraft.dueDate ?? undefined,
        dueTime: recoveredDraft.dueTime ?? undefined,
      });

      if (shouldAutoOpenRecoveredDraft({
        trigger,
        isTasksScreenActive: true,
        hasBlockingUi,
      })) {
        setShowCreate(true);
        devLog("smartInputRecovery", "restored", { trigger, autoOpened: true });
        return true;
      }
      devLog("smartInputRecovery", "restored", { trigger, autoOpened: false });
      return true;
    } catch (error) {
      devLog("smartInputRecovery", "failed", {
        trigger,
        error: error instanceof Error ? error.message : String(error),
      });
      return false;
    } finally {
      smartInputRecoveryInFlightRef.current = false;
      setIsRecoveringDraft(false);
    }
  }, [hasBlockingUi, queuedDraftCount, refreshQueuedDraftCount]);

  useEffect(() => {
    void refreshQueuedDraftCount();
  }, [refreshQueuedDraftCount]);

  useEffect(() => {
    if (queuedDraftCount !== lastQueuedCountRef.current) {
      setQueuedRecoveryDismissed(false);
      lastQueuedCountRef.current = queuedDraftCount;
    }
  }, [queuedDraftCount]);

  // Web preview debug callbacks (dev builds only — stripped from release bundles)
  useEffect(() => {
    if (!__DEV__) return;
    if (Platform.OS !== "web") return;
    if (typeof window === "undefined") return;
    (window as any).__yiyu_debug_create = () => { setSmartDraft(null); setCreatePreset({}); setShowCreate(true); };
    (window as any).__yiyu_debug_smart = () => { setShowSmartInput(true); };
    (window as any).__yiyu_debug_record = () => { setRecordTaskContext(null); setShowRecord(true); };
    return () => {
      try {
        delete (window as any).__yiyu_debug_create;
        delete (window as any).__yiyu_debug_smart;
        delete (window as any).__yiyu_debug_record;
      } catch {
        /* ignore */
      }
    };
  }, []);

  // Handle modal trigger from SuperFAB
  useEffect(() => {
    if (!params.trigger || handledModalTriggerRef.current === params.trigger) return;
    handledModalTriggerRef.current = params.trigger;
    if (params.modal === "create") {
      setSmartDraft(null); setCreatePreset({}); setRecordTaskContext(null);
      setShowSmartInput(false); setShowRecord(false); setShowCreate(true);
    } else if (params.modal === "smart") {
      setShowCreate(false); setShowRecord(false); setRecordTaskContext(null);
      setSmartInputPreset({}); setSmartDraft(null); setShowSmartInput(true);
    } else if (params.modal === "record") {
      setShowCreate(false); setShowSmartInput(false);
      setRecordTaskContext(null); setShowRecord(true);
    }
  }, [params.modal, params.trigger]);

  // ─── Android back ────────────────────────────

  useAndroidExitApp(
    useCallback(() => {
      if (showFilterMenu) { setShowFilterMenu(false); return true; }
      if (workspaceClientId) { setWorkspaceClientId(null); return true; }
      if (eventLineDrawerId) { setEventLineDrawerId(null); return true; }
      if (showSmartInput) { setShowSmartInput(false); setSmartInputPreset({}); return true; }
      if (showRecord) { setShowRecord(false); setRecordTaskContext(null); return true; }
      if (reviewTaskContext) { setReviewTaskContext(null); return true; }
      if (showCreate) { setShowCreate(false); return true; }
      if (selectedTask) { setSelectedTask(null); return true; }
      return false;
    }, [eventLineDrawerId, reviewTaskContext, selectedTask, showCreate, showFilterMenu, showRecord, showSmartInput, workspaceClientId]),
  );

  // ─── Handlers ────────────────────────────────

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await refresh();
      await refreshQueuedDraftCount();
    } finally {
      setRefreshing(false);
    }
  }, [refresh, refreshQueuedDraftCount]);

  const closeSwipeActions = useCallback(() => {
    setOpenSwipeTaskId(null);
    setOpenSwipeDirection(null);
  }, []);

  // ─── Drag-to-calendar callbacks ────────────
  const measureDragDates = useCallback(() => {
    dragDateRefs.current.forEach((view, key) => {
      view.measureInWindow((x, y, w, h) => {
        dragDateLayouts.current.set(key, { x, y, w, h });
      });
    });
  }, []);

  const findDragHoveredDate = useCallback((px: number, py: number): string | null => {
    for (const [key, layout] of dragDateLayouts.current) {
      if (px >= layout.x && px <= layout.x + layout.w && py >= layout.y && py <= layout.y + layout.h) {
        return key;
      }
    }
    return null;
  }, []);

  const resolveDragDotFrame = useCallback((pageX: number, pageY: number) => {
    const x = pageX - DRAG_DOT_SIZE / 2;
    const y = pageY - DRAG_DOT_SIZE / 2 - DRAG_DOT_FINGER_OFFSET_Y;
    return {
      x,
      y,
      hoverX: x + DRAG_DOT_SIZE / 2,
      hoverY: y + DRAG_DOT_SIZE / 2,
    };
  }, []);

  const handleDragStart = useCallback((task: TaskRecord, pageX: number, pageY: number) => {
    closeSwipeActions();
    setDragTask(task);
    const now = new Date();
    setDragCalendarMonth({ year: now.getFullYear(), month: now.getMonth() });
    setDragHoveredDate(null);
    dragDateLayouts.current.clear();
    const { x, y } = resolveDragDotFrame(pageX, pageY);
    dragTranslate.setValue({ x, y });
    dragOpacity.setValue(0);
    dragScale.setValue(0.72);
    Animated.parallel([
      Animated.timing(dragOpacity, { toValue: 1, duration: 90, useNativeDriver: true }),
      Animated.spring(dragScale, { toValue: 1, useNativeDriver: true, speed: 28, bounciness: 6 }),
    ]).start();
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    setTimeout(measureDragDates, 200);
  }, [closeSwipeActions, dragOpacity, dragScale, dragTranslate, measureDragDates, resolveDragDotFrame]);

  const handleDragMove = useCallback((pageX: number, pageY: number) => {
    const { x, y, hoverX, hoverY } = resolveDragDotFrame(pageX, pageY);
    dragTranslate.setValue({ x, y });
    const hovered = findDragHoveredDate(hoverX, hoverY);
    if (hovered !== dragHoveredDate) {
      setDragHoveredDate(hovered);
      if (hovered) void Haptics.selectionAsync();
    }
  }, [dragHoveredDate, dragTranslate, findDragHoveredDate, resolveDragDotFrame]);

  const handleDragEnd = useCallback(async () => {
    const task = dragTask;
    const targetDate = dragHoveredDate;
    const cleanup = () => {
      setDragTask(null);
      setDragHoveredDate(null);
    };

    if (!task || !targetDate) {
      Animated.parallel([
        Animated.timing(dragOpacity, { toValue: 0, duration: 110, useNativeDriver: true }),
        Animated.timing(dragScale, { toValue: 0.78, duration: 110, useNativeDriver: true }),
      ]).start(cleanup);
      return;
    }

    Animated.parallel([
      Animated.timing(dragOpacity, { toValue: 0, duration: 110, useNativeDriver: true }),
      Animated.timing(dragScale, { toValue: 0.86, duration: 110, useNativeDriver: true }),
    ]).start(cleanup);
    void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    try {
      await moveTaskToCalendarTarget(task, targetDate, targetDate);
    } catch {
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      Alert.alert("改期失败", "请检查网络或同步状态后重试。");
      void refresh();
    }
  }, [dragOpacity, dragScale, dragTask, dragHoveredDate, refresh]);

  const dragPanResponder = useMemo(() => PanResponder.create({
    onStartShouldSetPanResponder: () => !!dragTask,
    onMoveShouldSetPanResponder: () => !!dragTask,
    onMoveShouldSetPanResponderCapture: () => !!dragTask,
    onPanResponderTerminationRequest: () => false,
    onPanResponderMove: (evt) => {
      if (!dragTask) return;
      const { pageX, pageY } = evt.nativeEvent;
      handleDragMove(pageX, pageY);
    },
    onPanResponderRelease: () => { void handleDragEnd(); },
    onPanResponderTerminate: () => { setDragTask(null); setDragHoveredDate(null); },
  }), [dragTask, handleDragEnd, handleDragMove]);

  const handleEditInboxTask = useCallback((task: TaskRecord) => {
    closeSwipeActions();
    setEditingTask(task);
    setCreatePreset({});
    setShowCreate(true);
  }, [closeSwipeActions]);

  const applySmartDraft = useCallback((draft: SmartTaskDraft) => {
    const mergedDraft: SmartTaskDraft = {
      ...draft,
      dueDate: draft.dueDate ?? smartInputPreset.dueDate ?? null,
      dueTime: draft.dueTime ?? smartInputPreset.dueTime ?? null,
    };
    setShowSmartInput(false);
    setSmartInputPreset({});
    setEditingTask(null);
    setSmartDraft(mergedDraft);
    setCreatePreset({
      dueDate: mergedDraft.dueDate ?? undefined,
      dueTime: mergedDraft.dueTime ?? undefined,
    });
    setShowCreate(true);
  }, [smartInputPreset.dueDate, smartInputPreset.dueTime]);

  const applyTaskUpdates = useCallback(async (taskId: string, updates: Partial<TaskRecord>) => {
    const isScheduleUpdate = Object.prototype.hasOwnProperty.call(updates, "dueDate")
      || Object.prototype.hasOwnProperty.call(updates, "durationMinutes");

    let nextTask: TaskRecord | null = null;
    if (isScheduleUpdate) {
      nextTask = await updateCalendarTaskSchedule(taskId, {
        dueDate: updates.dueDate,
        durationMinutes: updates.durationMinutes,
      });
    } else {
      updateTaskOfflineFirst(taskId, updates);
      nextTask = localDb.getTaskById(taskId);
    }

    setSelectedTask((current) => (
      current?.id === taskId
        ? nextTask ?? { ...current, ...updates }
        : current
    ));
    void refresh();
    return nextTask;
  }, [refresh]);

  const handleDeleteInboxTask = useCallback((task: TaskRecord) => {
    closeSwipeActions();
    Alert.alert("删除任务", `确认删除「${task.title}」吗？`, [
      { text: "取消", style: "cancel" },
      {
        text: "删除",
        style: "destructive",
        onPress: async () => {
          try {
            deleteTaskOfflineFirst(task.id);
            void refresh();
            void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
          } catch {
            void refresh();
            Alert.alert("删除失败", "请检查网络后重试。");
          }
        },
      },
    ]);
  }, [closeSwipeActions, refresh]);

  const handleMarkTaskDone = useCallback((task: TaskRecord) => {
    if (task.progressStatus === "done") {
      return;
    }
    closeSwipeActions();
    void applyTaskUpdates(task.id, { progressStatus: "done" }).catch(() => {
      Alert.alert("完成任务失败", "请检查网络或同步状态后重试。");
      void refresh();
    });
  }, [applyTaskUpdates, closeSwipeActions]);

  // ─── Computed ────────────────────────────────

  const tasks = board.tasks ?? [];
  const todayKey = formatDateKey(new Date());
  const focusLocked = useMemo(() => isLockedFocus(focus), [focus]);
  const effectiveTasks = useMemo(
    () => (focusLocked && !showAllForFocus ? filterTasksByFocus(tasks, focus) : tasks),
    [focus, focusLocked, showAllForFocus, tasks],
  );
  const orderedTasks = useMemo(
    () => (focusLocked && showAllForFocus ? sortTasksByFocusPriority(effectiveTasks, focus) : effectiveTasks),
    [effectiveTasks, focus, focusLocked, showAllForFocus],
  );
  const focusMatchedTaskIds = useMemo(
    () => buildFocusMatchedTaskIds(tasks, focus),
    [focus, tasks],
  );
  const focusStats = useMemo(
    () => buildFocusTaskStats(tasks, focus),
    [focus, tasks],
  );
  const showFocusSummary = Boolean(focus.clientId || focus.eventLineId);

  useEffect(() => {
    setShowAllForFocus(false);
  }, [focus.clientId, focus.eventLineId, focus.lockMode]);
  const selectedTaskEventLine = useMemo(
    () => eventLines.find((item) => item.id === selectedTask?.eventLineId) ?? null,
    [eventLines, selectedTask?.eventLineId],
  );
  const drawerEventLine = useMemo(
    () => eventLines.find((item) => item.id === eventLineDrawerId) ?? null,
    [eventLineDrawerId, eventLines],
  );
  const handleTransferDrawerEventLine = useCallback(async (clientId: string) => {
    if (!drawerEventLine) {
      return;
    }
    const targetClient = clients.find((item) => item.id === clientId);
    if (!targetClient) {
      Alert.alert("迁移失败", "目标客户不存在，请刷新后重试。");
      return;
    }
    setTransferringEventLineId(drawerEventLine.id);
    try {
      await transferEventLineToClient(drawerEventLine.id, clientId);
      Alert.alert("已更新归属", `已把「${drawerEventLine.name}」转到客户「${targetClient.name}」下。`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "请检查网络连接后重试。";
      Alert.alert("迁移失败", message);
    } finally {
      setTransferringEventLineId(null);
    }
  }, [clients, drawerEventLine]);

  const filteredTasks = useMemo(() => {
    if (filter === "collab_inbox") return orderedTasks.filter(isCollabInboxTask);
    if (filter === "today") return orderedTasks.filter((t) => !t.dueDate || t.dueDate.startsWith(todayKey));
    if (filter === "unreviewed") return orderedTasks.filter((t) => t.progressStatus !== "done");
    // "all" - this week
    const now = new Date();
    const { startKey: monStr, endKey: sunStr } = getLocalWeekRangeKeys(now);
    return orderedTasks.filter((t) => {
      if (!t.dueDate) return true;
      const d = t.dueDate.slice(0, 10);
      return d >= monStr && d <= sunStr;
    });
  }, [filter, orderedTasks, todayKey]);

  const collabInboxTasks = useMemo(
    () => filteredTasks.filter(isCollabInboxTask),
    [filteredTasks],
  );

  // Pending scheduling = unscheduled tasks excluding collaboration inbox tasks
  const pendingScheduleTasks = useMemo(() => {
    if (filter === "collab_inbox") return [];
    if (filter === "today") {
      return orderedTasks.filter(
        (t) => t.progressStatus !== "done" && !isCollabInboxTask(t) && !hasScheduledDate(t),
      );
    }
    return filteredTasks.filter((t) => !isCollabInboxTask(t) && !hasScheduledDate(t));
  }, [filter, filteredTasks, orderedTasks]);

  // Scheduled tasks (for today or filtered)
  const scheduledTasks = useMemo(() => {
    if (filter === "collab_inbox") return [];
    if (filter === "today") {
      return orderedTasks.filter(
        (t) => !isCollabInboxTask(t) && t.dueDate?.startsWith(todayKey),
      );
    }
    return filteredTasks.filter((t) => !isCollabInboxTask(t) && hasScheduledDate(t));
  }, [filter, filteredTasks, orderedTasks, todayKey]);

  // ─── Render ──────────────────────────────────

  if (!isHydrated) {
    return (
      <View style={s.center}>
        <ActivityIndicator size="large" color={colors.brand} />
      </View>
    );
  }

  const filterLabel = FILTERS.find((f) => f.key === filter)?.label ?? "今日任务";
  const visibleQueuedDraftCount = queuedRecoveryDismissed ? 0 : queuedDraftCount;

  return (
    <SafeAreaView style={s.container} edges={["left", "right"]}>
      <ScrollView
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.brand} />}
        contentContainerStyle={{ paddingBottom: chrome.tabBarHeight + 34 }}
        stickyHeaderIndices={[0]}
        onScrollBeginDrag={closeSwipeActions}
        scrollEnabled={!dragTask}
      >
        <TasksHeader
          dateText={formatDate()}
          filterLabel={filterLabel}
          topPadding={chrome.headerTopPadding}
          onOpenFilter={() => setShowFilterMenu(true)}
        />

        <SmartInputRecoveryController
          queuedCount={visibleQueuedDraftCount}
          hasRecoveredDraft={Boolean(smartDraft) && !showCreate}
          isRecovering={isRecoveringDraft}
          onRequestRecovery={(trigger) => {
            void recoverQueuedSmartInput(trigger);
          }}
          onOpenRecoveredDraft={() => {
            if (smartDraft) {
              setShowCreate(true);
            }
          }}
          onDismissRecoveredDraft={() => {
            recoveryRequestVersionRef.current += 1;
            setSmartDraft(null);
            setCreatePreset({});
          }}
          onDismissQueuedRecovery={() => {
            void (async () => {
              setQueuedRecoveryDismissed(true);
              queuedCountRequestVersionRef.current += 1;
              try {
                recoveryRequestVersionRef.current += 1;
                await clearSmartInputQueue();
              } finally {
                smartInputRecoveryInFlightRef.current = false;
                lastRecoveryAttemptAtRef.current = null;
                setIsRecoveringDraft(false);
                setSmartDraft(null);
                setCreatePreset({});
                await refreshQueuedDraftCount();
              }
            })();
          }}
        />

        <View style={s.focusBarWrap}>
          <FocusBar
            showAll={showAllForFocus}
            onToggleShowAll={focusLocked ? () => setShowAllForFocus((current) => !current) : undefined}
            onOpenWorkspace={focus.clientId ? () => setWorkspaceClientId(focus.clientId) : undefined}
            onOpenEventLine={focus.eventLineId ? () => setEventLineDrawerId(focus.eventLineId) : undefined}
          />
          {showFocusSummary ? (
            <View style={s.focusSummaryCard}>
              <Text style={s.focusSummaryTitle} numberOfLines={1}>
                {focus.eventLineName || focus.clientName || "当前上下文"}
              </Text>
              <Text style={s.focusSummaryMeta}>
                {`相关 ${focusStats.matchedCount} 条 · 已安排 ${focusStats.scheduledCount} 条 · 待安排 ${focusStats.unscheduledCount} 条`}
                {focusStats.doneCount > 0 ? ` · 已完成 ${focusStats.doneCount} 条` : ""}
              </Text>
              <Text style={s.focusSummaryHint}>
                {focusLocked
                  ? showAllForFocus
                    ? "当前显示全部任务，相关任务已优先置顶。"
                    : "当前已锁定聚焦，只显示这条线上的任务。"
                  : "当前是浏览上下文，尚未锁定过滤。"}
              </Text>
            </View>
          ) : null}
        </View>

        <InboxTaskList
          title="协作收件箱"
          hint="别人派给你的待确认任务，先确认再进入自己的推进节奏。"
          tasks={collabInboxTasks}
          renderTask={(task) => {
            const isDone = task.progressStatus === "done";
            return (
              <SwipeInboxCard
                key={task.id}
                task={task}
                isDone={isDone}
                isFocusMatched={focusMatchedTaskIds.has(task.id)}
                openDirection={openSwipeTaskId === task.id ? openSwipeDirection : null}
                onOpenDirectionChange={(direction) => {
                  if (direction) {
                    setOpenSwipeTaskId(task.id);
                    setOpenSwipeDirection(direction);
                    return;
                  }
                  if (openSwipeTaskId === task.id) {
                    closeSwipeActions();
                  }
                }}
                onPress={() => {
                  closeSwipeActions();
                  setSelectedTask(task);
                }}
                onOpenEventLine={task.eventLineId ? () => {
                  setCurrentFocusBrowseFromTask(task);
                  setEventLineDrawerId(task.eventLineId!);
                } : undefined}
                onToggleComplete={() => handleMarkTaskDone(task)}
                onEdit={() => handleEditInboxTask(task)}
                onDelete={() => handleDeleteInboxTask(task)}
                onDragStart={handleDragStart}
                onDragMove={handleDragMove}
                onDragEnd={() => {
                  void handleDragEnd();
                }}
              />
            );
          }}
        />

        <InboxTaskList
          title="待安排任务"
          hint="这些任务还没排到具体日期或时间，可长按直接拖入日历。"
          tasks={pendingScheduleTasks}
          renderTask={(task) => {
            const isDone = task.progressStatus === "done";
            return (
              <SwipeInboxCard
                key={task.id}
                task={task}
                isDone={isDone}
                isFocusMatched={focusMatchedTaskIds.has(task.id)}
                openDirection={openSwipeTaskId === task.id ? openSwipeDirection : null}
                onOpenDirectionChange={(direction) => {
                  if (direction) {
                    setOpenSwipeTaskId(task.id);
                    setOpenSwipeDirection(direction);
                    return;
                  }
                  if (openSwipeTaskId === task.id) {
                    closeSwipeActions();
                  }
                }}
                onPress={() => {
                  closeSwipeActions();
                  setSelectedTask(task);
                }}
                onOpenEventLine={task.eventLineId ? () => {
                  setCurrentFocusBrowseFromTask(task);
                  setEventLineDrawerId(task.eventLineId!);
                } : undefined}
                onToggleComplete={() => handleMarkTaskDone(task)}
                onEdit={() => handleEditInboxTask(task)}
                onDelete={() => handleDeleteInboxTask(task)}
                onDragStart={handleDragStart}
                onDragMove={handleDragMove}
                onDragEnd={() => {
                  void handleDragEnd();
                }}
              />
            );
          }}
        />

        <ScheduledTaskList
          title={filter === "today" ? "今日安排" : "已安排任务"}
          tasks={scheduledTasks}
          renderTask={(task) => {
            const isDone = task.progressStatus === "done";
            return (
              <ScheduledCardWithDrag
                key={task.id}
                task={task}
                isDone={isDone}
                isFocusMatched={focusMatchedTaskIds.has(task.id)}
                onPress={() => {
                  closeSwipeActions();
                  setSelectedTask(task);
                }}
                onOpenEventLine={task.eventLineId ? () => {
                  setCurrentFocusBrowseFromTask(task);
                  setEventLineDrawerId(task.eventLineId!);
                } : undefined}
                onToggleComplete={() => handleMarkTaskDone(task)}
                onDragStart={handleDragStart}
                onDragMove={handleDragMove}
                onDragEnd={() => {
                  void handleDragEnd();
                }}
              />
            );
          }}
        />

        {/* Empty state */}
        {collabInboxTasks.length === 0 && pendingScheduleTasks.length === 0 && scheduledTasks.length === 0 && (
          <View style={s.empty}>
            <Inbox size={48} color={colors.textTertiary} />
            <Text style={s.emptyText}>{filter === "collab_inbox" ? "暂无协作收件箱任务" : "暂无任务"}</Text>
          </View>
        )}
      </ScrollView>

      <TasksFilterBar
        visible={showFilterMenu}
        floatingMenuTopInset={chrome.floatingMenuTopInset}
        selectedKey={filter}
        filters={FILTERS}
        onSelect={(nextFilter) => {
          setFilter(nextFilter);
          setShowFilterMenu(false);
        }}
        onClose={() => setShowFilterMenu(false)}
      />

      <TaskModalCoordinator
        selectedTask={selectedTask}
        selectedTaskEventLine={selectedTaskEventLine}
        showCreate={showCreate}
        showSmartInput={showSmartInput}
        showRecord={showRecord}
        reviewTaskContext={reviewTaskContext}
        editingTask={editingTask}
        smartDraft={smartDraft}
        createPreset={createPreset}
        smartInputPreset={smartInputPreset}
        todayKey={todayKey}
        recordTaskContext={recordTaskContext}
        onCloseSelectedTask={() => setSelectedTask(null)}
        onStartReview={(task) => {
          setReviewTaskContext(task);
          setSelectedTask(null);
        }}
        onRecordFromTaskDetail={() => {
          if (!selectedTask) return;
          setRecordTaskContext(selectedTask);
          setSelectedTask(null);
          setShowRecord(true);
        }}
        onUpdateTask={(taskId, updates) => {
          void applyTaskUpdates(taskId, updates).catch(() => {
            Alert.alert("更新任务失败", "请检查网络或同步状态后重试。");
            void refresh();
          });
        }}
        onDeleteTask={async (task) => {
          try {
            deleteTaskOfflineFirst(task.id);
            setSelectedTask(null);
            void refresh();
            await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
          } catch {
            void refresh();
            Alert.alert("删除失败", "请检查网络后重试。");
          }
        }}
        onReplaceSelectedTask={(task) => {
          setSelectedTask(task);
          void refresh();
        }}
        onOpenClientWorkspace={(clientId) => setWorkspaceClientId(clientId)}
        onOpenEventLine={(eventLineId) => {
          setCurrentFocusBrowseFromEventLine(eventLineId);
          setEventLineDrawerId(eventLineId);
        }}
        onOpenConsult={(task) => {
          setCurrentFocusBrowseFromTask(task);
          setSelectedTask(null);
          router.push("/(tabs)/consult");
        }}
        onCloseCreate={() => {
          setShowCreate(false);
          setEditingTask(null);
          setSmartDraft(null);
        }}
        onCreated={() => {
          setShowCreate(false);
          setEditingTask(null);
          setSmartDraft(null);
          void refresh();
        }}
        onCloseSmartInput={() => {
          setShowSmartInput(false);
          setSmartInputPreset({});
          void refreshQueuedDraftCount();
        }}
        onApplySmartDraft={applySmartDraft}
        onUploadedRecord={(task) => {
          setShowRecord(false);
          setRecordTaskContext(null);
          setSelectedTask(task);
          void refresh();
        }}
        onCloseRecord={() => {
          setShowRecord(false);
          setRecordTaskContext(null);
          void refresh();
        }}
        onCloseReview={() => setReviewTaskContext(null)}
        onSavedReview={() => {
          setReviewTaskContext(null);
          void refresh();
        }}
      />

      <DragCalendarOverlay
        dragTask={dragTask}
        dragHoveredDate={dragHoveredDate}
        dragCalendarMonth={dragCalendarMonth}
        dragDateRefs={dragDateRefs}
        dragOpacity={dragOpacity}
        dragScale={dragScale}
        dragTranslate={dragTranslate}
        panHandlers={dragPanResponder.panHandlers}
        formatDateKey={formatDateKey}
        measureDragDates={measureDragDates}
        onPrevMonth={() => {
          setDragCalendarMonth((prev) => {
            const next = new Date(prev.year, prev.month - 1, 1);
            return { year: next.getFullYear(), month: next.getMonth() };
          });
          setTimeout(measureDragDates, 100);
        }}
        onNextMonth={() => {
          setDragCalendarMonth((prev) => {
            const next = new Date(prev.year, prev.month + 1, 1);
            return { year: next.getFullYear(), month: next.getMonth() };
          });
          setTimeout(measureDragDates, 100);
        }}
        onCancel={() => {
          setDragTask(null);
          setDragHoveredDate(null);
        }}
      />
      <EventLineDrawer
        visible={Boolean(eventLineDrawerId)}
        eventLine={drawerEventLine}
        tasks={tasks}
        clients={clients}
        meetingHighlights={clientIntel.snapshot?.latestMeetings ?? []}
        onClose={() => setEventLineDrawerId(null)}
        onOpenWorkspace={() => {
          if (drawerEventLine?.primaryClientId) {
            setWorkspaceClientId(drawerEventLine.primaryClientId);
          }
        }}
        onTransferToClient={handleTransferDrawerEventLine}
        isTransferringClient={transferringEventLineId === drawerEventLine?.id}
        onTaskPress={(task) => {
          setEventLineDrawerId(null);
          setSelectedTask(task);
        }}
      />
      <WorkspaceLiteSheet
        visible={Boolean(workspaceClientId)}
        clientId={workspaceClientId}
        clientName={focus.clientName}
        onClose={() => setWorkspaceClientId(null)}
        onTaskPress={(taskId) => {
          const task = localDb.getTaskById(taskId);
          if (!task) {
            return;
          }
          setWorkspaceClientId(null);
          setSelectedTask(task);
        }}
      />
    </SafeAreaView>
  );
}

// ─── Styles ────────────────────────────────────

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F6F7FB" },
  center: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#F6F7FB" },
  // Header
  header: {
    backgroundColor: "#F6F7FB",
    paddingHorizontal: 20,
    paddingTop: 0,
    paddingBottom: 18,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 8,
  },
  focusBarWrap: {
    paddingHorizontal: 20,
    paddingTop: 14,
    paddingBottom: 8,
  },
  focusSummaryCard: {
    marginTop: 10,
    backgroundColor: "#FFFFFF",
    borderRadius: borderRadius.xl,
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderWidth: 1,
    borderColor: "#D9E5FB",
    ...shadow.softCard,
  },
  focusSummaryTitle: {
    fontSize: 14,
    fontWeight: "700",
    color: "#2C3340",
  },
  focusSummaryMeta: {
    marginTop: 4,
    fontSize: 12,
    fontWeight: "600",
    color: colors.brand,
  },
  focusSummaryHint: {
    marginTop: 6,
    fontSize: 12,
    lineHeight: 18,
    color: "#6B7280",
  },
  date: { fontSize: 20, color: "#2C3340", fontWeight: "800", letterSpacing: -0.4 },
  filterDropdown: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#EBF0FC",
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: borderRadius.full,
    gap: 5,
    shadowColor: "#D9E5FB",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.18,
    shadowRadius: 10,
    elevation: 1,
  },
  filterDropdownText: { fontSize: 13, fontWeight: "700", color: colors.brand },

  // Filter menu
  menuOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.12)",
    justifyContent: "flex-start",
    alignItems: "flex-end",
    paddingTop: 0,
    paddingRight: 18,
  },
  menuCard: {
    backgroundColor: colors.surface,
    borderRadius: 20,
    paddingVertical: 4,
    minWidth: 140,
    ...shadow.softCard,
  },
  menuItem: { paddingHorizontal: 18, paddingVertical: 11 },
  menuItemActive: { backgroundColor: colors.headerPill },
  menuItemText: { fontSize: 13, fontWeight: "500", color: "#4B5563" },
  menuItemTextActive: { color: colors.brand, fontWeight: "600" },

  // Inbox (unscheduled tasks)
  inboxSection: { paddingHorizontal: 16, paddingTop: 8, marginBottom: 18 },
  inboxHeader: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 12, paddingLeft: 6 },
  inboxTitle: { fontSize: 17, fontWeight: "800", color: "#616A7A" },
  sectionHint: { fontSize: 12, color: "#98A2B3", marginBottom: 10, paddingLeft: 6, lineHeight: 18 },
  swipeCardShell: { position: "relative", marginBottom: 10, borderRadius: 18, overflow: "hidden" },
  swipeActionsLayer: {
    ...StyleSheet.absoluteFillObject,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "stretch",
    backgroundColor: colors.surfaceSecondary,
  },
  swipeAction: {
    width: SWIPE_ACTION_WIDTH,
    alignItems: "center",
    justifyContent: "center",
  },
  swipeActionEdit: { backgroundColor: "#16A34A" },
  swipeActionDelete: { backgroundColor: colors.error },
  swipeActionText: { fontSize: 14, fontWeight: "700", color: colors.textOnBrand },
  swipeCardWrap: { backgroundColor: "transparent" },
  inboxCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 24,
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 20,
    paddingHorizontal: 18,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "#EEF1F5",
    shadowColor: "#111827",
    shadowOffset: { width: 0, height: 5 },
    shadowOpacity: 0.05,
    shadowRadius: 16,
    elevation: 2,
  },
  focusMatchedCard: {
    borderColor: colors.brandRing,
    backgroundColor: "#F8FBFF",
  },
  inboxDot: { width: 10, height: 10, borderRadius: 5, marginRight: 14 },
  taskCompleteToggle: {
    width: 22,
    height: 22,
    borderRadius: 7,
    borderWidth: 1.5,
    borderColor: "#CBD5E1",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
    backgroundColor: "#FFFFFF",
  },
  taskCompleteToggleDone: {
    backgroundColor: "#2563EB",
    borderColor: "#2563EB",
  },
  inboxCardBody: { flex: 1 },
  inboxCardTitleRow: { flexDirection: "row", alignItems: "flex-start", gap: 8 },
  inboxCardTitle: { fontSize: 15, fontWeight: "700", color: "#202632", lineHeight: 21 },
  inboxCardTitleDone: { textDecorationLine: "line-through", color: colors.textTertiary },
  inboxCardMeta: { fontSize: 12, color: "#A6AFBF", marginTop: 6, lineHeight: 18 },
  taskSyncBadge: { marginTop: 8 },
  focusChip: {
    alignSelf: "flex-start",
    backgroundColor: colors.brandBg,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  focusChipText: {
    fontSize: 11,
    color: colors.brand,
    fontWeight: "700",
  },
  inboxStatusBadge: {
    backgroundColor: "#F3E8FF",
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 3,
    marginTop: 1,
  },
  inboxStatusBadgeText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#7C3AED",
  },

  // Scheduled tasks section
  scheduledSection: { paddingHorizontal: 16, marginBottom: 18 },
  scheduledTitle: { fontSize: 17, fontWeight: "800", color: "#616A7A", marginBottom: 12, paddingLeft: 6 },
  scheduledCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 14,
    paddingHorizontal: 16,
    marginBottom: 8,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "#EEF1F5",
    shadowColor: "#111827",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 1,
  },
  scheduledCardBody: { flex: 1 },
  scheduledCardTitle: { fontSize: 14, fontWeight: "600", color: "#202632" },
  scheduledCardTitleDone: { textDecorationLine: "line-through", color: colors.textTertiary },
  scheduledCardMeta: { fontSize: 11, color: "#A6AFBF", marginTop: 2 },
  scheduledCardTime: { fontSize: 12, fontWeight: "600", color: "#7C3AED", marginRight: 8 },

  // Empty
  empty: { alignItems: "center", paddingVertical: 80 },
  emptyText: { fontSize: 14, color: "#9CA3AF", marginTop: 12 },
}) as Record<string, any>;
~~~

## `mobile/app/_layout.tsx`

- 编码: `utf-8`

~~~tsx
import { Slot, useRouter, useSegments } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { Platform, View, StyleSheet, Text, TouchableOpacity, useWindowDimensions } from "react-native";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { AuthProvider, useAuth } from "../lib/auth-context";
import { colors, shadow } from "../lib/theme";

function RootNavigator() {
  const { isLoading, user } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;

    const inAuthGroup = segments[0] === "login";

    if (!user && !inAuthGroup) {
      router.replace("/login");
    } else if (user && inAuthGroup) {
      router.replace("/(tabs)/tasks");
    }
  }, [isLoading, user, segments, router]);

  return (
    <>
      <StatusBar style="dark" />
      <Slot />
    </>
  );
}

export default function RootLayout() {
  const { width } = useWindowDimensions();
  const [debugPanelOptIn, setDebugPanelOptIn] = useState(false);

  useEffect(() => {
    if (Platform.OS !== "web") return;
    try {
      const search = window.location.search ?? "";
      setDebugPanelOptIn(search.includes("debugPanel=1"));
    } catch {
      setDebugPanelOptIn(false);
    }
  }, []);

  const showDebugPanel = useMemo(() => {
    if (!__DEV__) return false;
    if (Platform.OS !== "web") return false;
    if (!debugPanelOptIn) return false;
    return width >= 1280;
  }, [debugPanelOptIn, width]);

  const inner = (
    <SafeAreaProvider>
      <AuthProvider>
        <RootNavigator />
      </AuthProvider>
    </SafeAreaProvider>
  );

  // Web: wrap in phone-sized frame for desktop preview
  if (Platform.OS === "web") {
    return (
      <View style={webStyles.wrapper}>
        <View style={webStyles.shell}>
          <View style={webStyles.browserBar}>
            <View style={webStyles.browserDots}>
              <View style={[webStyles.browserDot, webStyles.browserDotRed]} />
              <View style={[webStyles.browserDot, webStyles.browserDotAmber]} />
              <View style={[webStyles.browserDot, webStyles.browserDotGreen]} />
            </View>
            <View style={webStyles.browserAddress}>
              <Text style={webStyles.browserAddressText}>Android / Web 调试预览</Text>
            </View>
            <View style={webStyles.browserSpacer} />
          </View>
          <View style={webStyles.canvas}>
            {inner}
          </View>
        </View>
        {showDebugPanel ? (
          <View style={webStyles.debugPanel}>
            <Text style={webStyles.debugTitle}>调试面板</Text>
            <TouchableOpacity style={webStyles.debugBtn} onPress={() => { (window as any).__yiyu_debug_create?.(); }}>
              <Text style={webStyles.debugBtnText}>+ 新建任务</Text>
            </TouchableOpacity>
            <TouchableOpacity style={webStyles.debugBtn} onPress={() => { (window as any).__yiyu_debug_record?.(); }}>
              <Text style={webStyles.debugBtnText}>🎙 速记</Text>
            </TouchableOpacity>
          </View>
        ) : null}
      </View>
    );
  }

  return inner;
}

const webStyles = StyleSheet.create({
  wrapper: {
    flex: 1,
    backgroundColor: colors.panel,
    flexDirection: "row" as any,
    alignItems: "center",
    justifyContent: "center",
    gap: 44,
    paddingHorizontal: 28,
    paddingVertical: 24,
  },
  shell: {
    width: 440,
    height: 920,
    backgroundColor: "#F4F6FB",
    borderRadius: 28,
    overflow: "hidden",
    position: "relative" as any,
    borderWidth: 1,
    borderColor: "rgba(126,133,157,0.18)",
    ...shadow.phone,
    boxShadow: "0 20px 64px rgba(0,0,0,0.22)" as any,
  },
  browserBar: {
    height: 58,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(126,133,157,0.14)",
    backgroundColor: "#EDF1F8",
    flexDirection: "row" as any,
    alignItems: "center",
    gap: 12,
  },
  browserDots: {
    flexDirection: "row" as any,
    alignItems: "center",
    gap: 6,
  },
  browserDot: {
    width: 10,
    height: 10,
    borderRadius: 999,
  },
  browserDotRed: {
    backgroundColor: "#F87171",
  },
  browserDotAmber: {
    backgroundColor: "#FBBF24",
  },
  browserDotGreen: {
    backgroundColor: "#34D399",
  },
  browserAddress: {
    flex: 1,
    height: 36,
    borderRadius: 14,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "rgba(126,133,157,0.14)",
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 14,
  },
  browserAddressText: {
    color: "#5E657A",
    fontSize: 13,
    fontWeight: "700",
  },
  browserSpacer: {
    width: 36,
  },
  canvas: {
    flex: 1,
    backgroundColor: "#FFFFFF",
  },
  debugPanel: {
    width: 168,
    gap: 16,
  },
  debugTitle: {
    color: "#7E859D",
    fontSize: 14,
    fontWeight: "700",
    marginBottom: 8,
  },
  debugBtn: {
    backgroundColor: colors.panelSecondary,
    borderRadius: 18,
    paddingVertical: 20,
    paddingHorizontal: 18,
    alignItems: "center",
  },
  debugBtnText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "800",
  },
});
~~~

## `mobile/app/index.tsx`

- 编码: `utf-8`

~~~tsx
import { Redirect } from "expo-router";

export default function Index() {
  return <Redirect href="/(tabs)/tasks" />;
}
~~~

## `mobile/app/login.tsx`

- 编码: `utf-8`

~~~tsx
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useAuth } from "../lib/auth-context";
import { useAndroidExitApp } from "../lib/android-back";
import * as api from "../lib/api";
import { initializeRuntime } from "../lib/runtime";
import { useAppChromeInsets } from "../lib/app-chrome";
import { colors, fontSize, spacing, borderRadius, shadow } from "../lib/theme";

export default function LoginScreen() {
  const chrome = useAppChromeInsets();
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [serverUrl, setServerUrl] = useState(api.getBaseUrl());
  const [testingServer, setTestingServer] = useState(false);
  const [serverMessage, setServerMessage] = useState<string | null>(null);
  const [showServerConfig, setShowServerConfig] = useState(false);

  useAndroidExitApp(() => {
    if (showServerConfig) {
      setShowServerConfig(false);
      return true;
    }
    return false;
  });

  useEffect(() => {
    (async () => {
      await initializeRuntime();
      setServerUrl(api.getBaseUrl());
    })();
  }, []);

  const handleSaveServerUrl = async () => {
    if (!serverUrl.trim()) {
      Alert.alert("提示", "请输入服务地址");
      return;
    }

    try {
      await api.setAndSaveBaseUrl(serverUrl.trim());
      setServerUrl(api.getBaseUrl());
      setServerMessage(`已保存：${api.getBaseUrl()}`);
    } catch {
      Alert.alert("保存失败", "服务地址格式无效");
    }
  };

  const handleTestServer = async () => {
    if (!serverUrl.trim()) {
      Alert.alert("提示", "请输入服务地址");
      return;
    }

    setTestingServer(true);
    try {
      const normalized = serverUrl.trim();
      const health = await api.fetchHealth(normalized);
      await api.setAndSaveBaseUrl(normalized);
      setServerUrl(api.getBaseUrl());
      setServerMessage(`已连通 ${health.service}，任务 ${health.taskCount} 条`);
    } catch (error) {
      setServerMessage(error instanceof Error ? error.message : "服务不可达");
    } finally {
      setTestingServer(false);
    }
  };

  const handleLogin = async () => {
    if (!email.trim() || !password.trim()) {
      Alert.alert("提示", "请输入邮箱和密码");
      return;
    }
    if (!serverUrl.trim()) {
      Alert.alert("提示", "请先确认服务地址");
      return;
    }
    setLoading(true);
    try {
      await api.setAndSaveBaseUrl(serverUrl.trim());
      await signIn(email.trim(), password);
    } catch (error) {
      const message = error instanceof Error ? error.message : "请检查邮箱、密码和服务地址";
      Alert.alert("登录失败", message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={["left", "right"]}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        style={[styles.inner, { paddingTop: chrome.screenTopPadding }]}
      >
        <ScrollView contentContainerStyle={[styles.scrollContent, { paddingBottom: chrome.screenBottomPadding }]} keyboardShouldPersistTaps="handled">
          {/* Logo area */}
          <View style={styles.logoArea}>
            <View style={styles.logoCircle}>
              <Text style={styles.logoText}>益</Text>
            </View>
            <Text style={styles.brand}>益语智库</Text>
            <Text style={styles.subtitle}>移动工作台</Text>
          </View>

          {/* Login card */}
          <View style={styles.card}>
            <View style={styles.fieldGroup}>
              <Text style={styles.label}>邮箱</Text>
              <TextInput
                style={styles.input}
                value={email}
                onChangeText={setEmail}
                placeholder="your@email.com"
                placeholderTextColor={colors.textTertiary}
                keyboardType="email-address"
                autoCapitalize="none"
                autoCorrect={false}
              />
            </View>

            <View style={styles.fieldGroup}>
              <Text style={styles.label}>密码</Text>
              <TextInput
                style={styles.input}
                value={password}
                onChangeText={setPassword}
                placeholder="输入密码"
                placeholderTextColor={colors.textTertiary}
                secureTextEntry
              />
            </View>

            <TouchableOpacity
              style={styles.serverToggle}
              activeOpacity={0.8}
              onPress={() => setShowServerConfig((value) => !value)}
            >
              <Text style={styles.serverToggleLabel}>服务地址</Text>
              <Text style={styles.serverToggleValue} numberOfLines={1}>{serverUrl}</Text>
            </TouchableOpacity>

            {showServerConfig && (
              <View style={styles.serverCard}>
                <Text style={styles.serverHint}>
                  当前测试默认走公网云端 {api.DEFAULT_BASE_URL}；如需改测局域网，可填写
                  {" "}http://192.168.x.x:47831
                </Text>
                <TextInput
                  style={styles.input}
                  value={serverUrl}
                  onChangeText={setServerUrl}
                  placeholder={api.DEFAULT_BASE_URL}
                  placeholderTextColor={colors.textTertiary}
                  autoCapitalize="none"
                  autoCorrect={false}
                  keyboardType="url"
                />
                <View style={styles.serverActions}>
                  <TouchableOpacity
                    style={[styles.secondaryButton, testingServer && styles.buttonDisabled]}
                    onPress={handleSaveServerUrl}
                    disabled={testingServer}
                    activeOpacity={0.85}
                  >
                    <Text style={styles.secondaryButtonText}>保存地址</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.secondaryButton, styles.secondaryButtonPrimary, testingServer && styles.buttonDisabled]}
                    onPress={handleTestServer}
                    disabled={testingServer}
                    activeOpacity={0.85}
                  >
                    {testingServer ? <ActivityIndicator color={colors.brand} /> : <Text style={styles.secondaryButtonPrimaryText}>测试连接</Text>}
                  </TouchableOpacity>
                </View>
                {serverMessage ? <Text style={styles.serverMessage}>{serverMessage}</Text> : null}
              </View>
            )}

            <TouchableOpacity
              style={[styles.button, loading && styles.buttonDisabled]}
              onPress={handleLogin}
              disabled={loading}
              activeOpacity={0.85}
            >
              {loading ? (
                <ActivityIndicator color={colors.textOnBrand} />
              ) : (
                <Text style={styles.buttonText}>登录</Text>
              )}
            </TouchableOpacity>
          </View>

          <Text style={styles.footer}>益语智库 v1.0.0</Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  inner: {
    flex: 1,
    paddingHorizontal: spacing.xl,
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: "center",
    paddingVertical: spacing.xxxl,
  },
  logoArea: {
    alignItems: "center",
    marginBottom: spacing.xxxl,
  },
  logoCircle: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: colors.brand,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.lg,
    ...shadow.elevated,
  },
  logoText: {
    fontSize: 32,
    fontWeight: "800",
    color: colors.textOnBrand,
  },
  brand: {
    fontSize: fontSize.title,
    fontWeight: "800",
    color: colors.text,
    letterSpacing: 1,
  },
  subtitle: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.xl,
    padding: spacing.xl,
    ...shadow.card,
  },
  fieldGroup: {
    marginBottom: spacing.lg,
  },
  label: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  input: {
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    fontSize: fontSize.md,
    color: colors.text,
  },
  serverToggle: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.borderLight,
    paddingTop: spacing.lg,
    marginTop: spacing.sm,
  },
  serverToggleLabel: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.textSecondary,
  },
  serverToggleValue: {
    fontSize: fontSize.sm,
    color: colors.brand,
    marginTop: spacing.xs,
  },
  serverCard: {
    marginTop: spacing.md,
    padding: spacing.md,
    borderRadius: borderRadius.lg,
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.borderLight,
    gap: spacing.md,
  },
  serverHint: {
    fontSize: fontSize.xs,
    lineHeight: 16,
    color: colors.textSecondary,
  },
  serverActions: {
    flexDirection: "row",
    gap: spacing.md,
  },
  secondaryButton: {
    flex: 1,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacing.md,
  },
  secondaryButtonPrimary: {
    borderColor: colors.brand,
    backgroundColor: colors.brandBg,
  },
  secondaryButtonText: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.text,
  },
  secondaryButtonPrimaryText: {
    fontSize: fontSize.sm,
    fontWeight: "700",
    color: colors.brand,
  },
  serverMessage: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    lineHeight: 16,
  },
  button: {
    backgroundColor: colors.brand,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md + 2,
    alignItems: "center",
    marginTop: spacing.md,
    ...shadow.elevated,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    color: colors.textOnBrand,
    fontSize: fontSize.lg,
    fontWeight: "700",
  },
  footer: {
    textAlign: "center",
    fontSize: fontSize.xs,
    color: colors.textTertiary,
    marginTop: spacing.xxxl,
  },
});
~~~

## `mobile/components/CreateTask.tsx`

- 编码: `utf-8`

~~~tsx
import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import { ExpoSpeechRecognitionModule, useSpeechRecognitionEvent } from "expo-speech-recognition";
import { useAppChromeInsets } from "../lib/app-chrome";
import { colors, fontSize, shadow } from "../lib/theme";
import { X, Mic, Sparkles, Briefcase, ListTodo, Calendar, Tag, User, ChevronRight, CheckCircle2, Plus } from "lucide-react-native";
import { createEventLine } from "../lib/create-task-service";
import {
  buildProjectOptions,
  deriveProjectLabel,
  filterEventLinesForSelection,
  findAutoMatchedEventLine,
  getProjectKey,
  normalizeSearchText,
  shouldApplyAutoAssociation,
  type AssociationSource,
  type ProjectOption,
} from "../lib/create-task-association";
import {
  invalidateTaskCreationResources,
  loadTaskCreationResources,
} from "../lib/create-task-resources";
import {
  createTaskLocalFirst,
  updateTaskLocalFirst,
} from "../lib/task-repository";
import type { ClientSummaryRecord, EventLineRecord, SmartTaskDraft, TaskRecord } from "../lib/types";
import DateTimePickerSheet from "./DateTimePickerSheet";

interface Props {
  onClose: () => void;
  onCreated: () => void;
  preset?: { dueDate?: string; dueTime?: string };
  task?: TaskRecord | null;
  draft?: SmartTaskDraft | null;
}

export default function CreateTask({ onClose, onCreated, preset, task, draft }: Props) {
  const chrome = useAppChromeInsets();
  const activeDraft = !task ? draft ?? null : null;
  const [title, setTitle] = useState(task?.title ?? activeDraft?.title ?? "");
  const [description, setDescription] = useState(task?.description ?? activeDraft?.description ?? "");
  const [actionType, setActionType] = useState(task?.tags?.[0] ?? activeDraft?.tags?.[0] ?? "材料/交付");
  const [allEventLines, setAllEventLines] = useState<EventLineRecord[]>([]);
  const [allClients, setAllClients] = useState<ClientSummaryRecord[]>([]);
  const [selectedEventLine, setSelectedEventLine] = useState<EventLineRecord | null>(null);
  const [selectedProjectKey, setSelectedProjectKey] = useState<string | null>(null);
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null);
  const [selectedClientName, setSelectedClientName] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [customDate, setCustomDate] = useState<string | null>(task?.dueDate?.split("T")[0] ?? activeDraft?.dueDate ?? null);
  const [customTime, setCustomTime] = useState<string | null>(task?.dueDate?.includes("T") ? task.dueDate.slice(11, 16) : activeDraft?.dueTime ?? null);
  const [showClientPicker, setShowClientPicker] = useState(false);
  const [showEventLinePicker, setShowEventLinePicker] = useState(false);
  const [isCreatingEventLine, setIsCreatingEventLine] = useState(false);
  const [newEventLineName, setNewEventLineName] = useState("");
  const [creatingEventLineLoading, setCreatingEventLineLoading] = useState(false);
  const [defaultListId, setDefaultListId] = useState<string | null>(null);
  const [durationMinutes, setDurationMinutes] = useState<number | null>(task?.durationMinutes ?? activeDraft?.durationMinutes ?? null);
  const [associationSource, setAssociationSource] = useState<AssociationSource>("default");
  const [lockedAssociationTitleKey, setLockedAssociationTitleKey] = useState<string | null>(null);
  const [isVoiceInputActive, setIsVoiceInputActive] = useState(false);

  const resolveDefaultListId = useCallback(async () => {
    const { settings, taskLists } = await loadTaskCreationResources();
    if (settings?.defaultListId) {
      return settings.defaultListId;
    }
    return taskLists.find((item) => item.isDefault)?.id ?? taskLists[0]?.id ?? null;
  }, []);

  const titleSearchKey = useMemo(() => normalizeSearchText(title), [title]);
  const clientById = useMemo(
    () => new Map(allClients.map((client) => [client.id, client])),
    [allClients],
  );

  const projectOptions = useMemo(() => {
    return buildProjectOptions(allClients, allEventLines);
  }, [allClients, allEventLines]);

  const filteredEventLines = useMemo(() => {
    return filterEventLinesForSelection(allEventLines, selectedClientId, selectedProjectKey);
  }, [allEventLines, selectedClientId, selectedProjectKey]);

  const syncSelectionFromEventLine = useCallback((eventLine: EventLineRecord | null, source: "auto" | "manual" | "default") => {
    if (!eventLine) {
      setSelectedEventLine(null);
      setSelectedProjectKey(null);
      setSelectedClientId(null);
      setSelectedClientName(null);
      if (source === "manual") {
        setLockedAssociationTitleKey(titleSearchKey);
      }
      setAssociationSource(source);
      return;
    }

    setSelectedEventLine(eventLine);
    const client = eventLine.primaryClientId ? clientById.get(eventLine.primaryClientId) : null;
    setSelectedProjectKey(eventLine.primaryClientId ? `client:${eventLine.primaryClientId}` : getProjectKey(eventLine));
    setSelectedClientId(eventLine.primaryClientId ?? null);
    setSelectedClientName(client?.name ?? eventLine.primaryClientName ?? deriveProjectLabel(eventLine));

    if (source === "manual") {
      setLockedAssociationTitleKey(titleSearchKey);
    }
    setAssociationSource(source);
  }, [clientById, titleSearchKey]);

  const autoMatchedEventLine = useMemo(() => {
    return findAutoMatchedEventLine(titleSearchKey, allEventLines);
  }, [allEventLines, titleSearchKey]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resources = await loadTaskCreationResources();
        if (cancelled) {
          return;
        }
        const resolvedListId =
          resources.settings?.defaultListId ??
          resources.taskLists.find((item) => item.isDefault)?.id ??
          resources.taskLists[0]?.id ??
          null;
        const els = resources.eventLines;
        const clients = resources.clients;
        setAllEventLines(els);
        setAllClients(clients);
        setDefaultListId(resolvedListId);
        if (task?.eventLineId) {
          const matchingEventLine = els.find((item) => item.id === task.eventLineId) ?? null;
          if (matchingEventLine) {
            syncSelectionFromEventLine(matchingEventLine, "manual");
            return;
          }
        }
        if (activeDraft?.eventLineId) {
          const matchingEventLine = els.find((item) => item.id === activeDraft.eventLineId) ?? null;
          if (matchingEventLine) {
            syncSelectionFromEventLine(matchingEventLine, "manual");
            return;
          }
        }
        if (task?.clientId) {
          const matchingClient = clients.find((item) => item.id === task.clientId) ?? null;
          if (matchingClient) {
            setSelectedProjectKey(`client:${matchingClient.id}`);
            setSelectedClientId(matchingClient.id);
            setSelectedClientName(matchingClient.name);
            setAssociationSource("manual");
            setLockedAssociationTitleKey(titleSearchKey);
            return;
          }
        }
        if (activeDraft?.clientId) {
          const matchingClient = clients.find((item) => item.id === activeDraft.clientId) ?? null;
          if (matchingClient) {
            setSelectedProjectKey(`client:${matchingClient.id}`);
            setSelectedClientId(matchingClient.id);
            setSelectedClientName(matchingClient.name);
            setAssociationSource("manual");
            setLockedAssociationTitleKey(titleSearchKey);
            return;
          }
        }
        if (els.length > 0) {
          const active = els.find(e => e.status === "active") || els[0];
          syncSelectionFromEventLine(active, "default");
          return;
        }
        if (clients.length > 0) {
          setSelectedProjectKey(`client:${clients[0].id}`);
          setSelectedClientId(clients[0].id);
          setSelectedClientName(clients[0].name);
          setAssociationSource("default");
        }
      } catch {}
    })();
    return () => {
      cancelled = true;
    };
  }, [activeDraft?.clientId, activeDraft?.eventLineId, syncSelectionFromEventLine, task?.clientId, task?.eventLineId, titleSearchKey]);

  useEffect(() => {
    if (!task) {
      return;
    }
    setTitle(task.title ?? "");
    setDescription(task.description ?? "");
    setActionType(task.tags?.[0] ?? "材料/交付");
    setCustomDate(task.dueDate?.split("T")[0] ?? null);
    setCustomTime(task.dueDate?.includes("T") ? task.dueDate.slice(11, 16) : null);
    setDurationMinutes(task.durationMinutes ?? null);
  }, [task]);

  useEffect(() => {
    if (task || !activeDraft) {
      return;
    }
    setTitle(activeDraft.title ?? "");
    setDescription(activeDraft.description ?? "");
    setActionType(activeDraft.tags?.[0] ?? "材料/交付");
    setCustomDate(activeDraft.dueDate ?? null);
    setCustomTime(activeDraft.dueTime ?? null);
    setDurationMinutes(activeDraft.durationMinutes ?? null);
  }, [activeDraft, task]);

  useSpeechRecognitionEvent("start", () => {
    setIsVoiceInputActive(true);
  });

  useSpeechRecognitionEvent("end", () => {
    setIsVoiceInputActive(false);
  });

  useSpeechRecognitionEvent("result", (event) => {
    const transcript = event.results[0]?.transcript?.trim();
    if (!transcript) {
      return;
    }
    if (!title.trim()) {
      setTitle(transcript);
      return;
    }
    setDescription((current) => (current.trim() ? `${current.trim()}\n${transcript}` : transcript));
  });

  useSpeechRecognitionEvent("error", (event) => {
    setIsVoiceInputActive(false);
    Alert.alert("语音输入失败", event.message || "请稍后再试。");
  });

  useEffect(() => {
    return () => {
      ExpoSpeechRecognitionModule.stop();
    };
  }, []);

  useEffect(() => {
    if (!shouldApplyAutoAssociation({
      source: associationSource,
      lockedTitleKey: lockedAssociationTitleKey,
      titleSearchKey,
      selectedEventLineId: selectedEventLine?.id ?? null,
      autoMatchedEventLineId: autoMatchedEventLine?.id ?? null,
    })) {
      return;
    }
    syncSelectionFromEventLine(autoMatchedEventLine, "auto");
  }, [associationSource, autoMatchedEventLine, lockedAssociationTitleKey, selectedEventLine?.id, syncSelectionFromEventLine, titleSearchKey]);

  const handleSelectClient = (project: ProjectOption) => {
    // Set the project selection directly — do NOT let syncSelectionFromEventLine override it
    setSelectedProjectKey(project.id);
    setSelectedClientId(project.clientId);
    setSelectedClientName(project.name);
    setAssociationSource("manual");
    setLockedAssociationTitleKey(titleSearchKey);

    // Find a matching event line under this project, but only set the event line — not the project
    const firstEventLine =
      allEventLines.find((el) => project.clientId ? el.primaryClientId === project.clientId && el.status === "active" : getProjectKey(el) === project.id && el.status === "active") ||
      allEventLines.find((el) => project.clientId ? el.primaryClientId === project.clientId : getProjectKey(el) === project.id) ||
      null;
    setSelectedEventLine(firstEventLine);
    setShowClientPicker(false);
  };

  const handleCreateEventLine = async () => {
    const name = newEventLineName.trim();
    if (!name) { Alert.alert("提示", "请输入事件线名称"); return; }
    setCreatingEventLineLoading(true);
    try {
      const created = await createEventLine({
        name,
        primaryClientId: selectedClientId ?? undefined,
        primaryClientName: selectedClientName ?? undefined,
        status: "active",
      });
      invalidateTaskCreationResources();
      setAllEventLines((prev) => [created, ...prev]);
      syncSelectionFromEventLine(created, "manual");
      setIsCreatingEventLine(false);
      setNewEventLineName("");
      setShowEventLinePicker(false);
    } catch {
      Alert.alert("创建失败", "事件线创建失败，请重试");
    } finally {
      setCreatingEventLineLoading(false);
    }
  };

  const getDueDate = useCallback(() => {
    if (customDate) {
      return customTime ? `${customDate}T${customTime}` : customDate;
    }
    if (preset?.dueDate) {
      const time = customTime || preset.dueTime;
      return time ? `${preset.dueDate}T${time}` : preset.dueDate;
    }
    const d = new Date();
    const dateStr = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
    if (preset?.dueTime) return dateStr + "T" + preset.dueTime;
    return dateStr;
  }, [customDate, customTime, preset]);

  const handleSubmit = async () => {
    if (!title.trim()) { Alert.alert("提示", "请输入任务标题"); return; }
    setSubmitting(true);
    try {
      const listId = defaultListId ?? await resolveDefaultListId();
      if (!listId) {
        Alert.alert("创建失败", "默认任务列表未配置，请先在设置中确认列表。");
        return;
      }
      setDefaultListId(listId);
      const payload = {
        title: title.trim(),
        description: description.trim() || undefined,
        dueDate: getDueDate(),
        durationMinutes: durationMinutes ?? undefined,
        priority: task?.priority ?? "normal",
        clientId: selectedEventLine?.primaryClientId ?? selectedClientId ?? undefined,
        eventLineId: selectedEventLine?.id,
        tags: [actionType],
      };
      if (task) {
        updateTaskLocalFirst(task.id, {
          ...payload,
          listId: task.listId ?? listId,
        });
      } else {
        createTaskLocalFirst({
          ...payload,
          listId,
        });
      }
      onCreated();
    } catch (e) {
      Alert.alert(task ? "保存失败" : "创建失败", "请检查网络连接后重试");
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleVoiceInput = useCallback(async () => {
    if (isVoiceInputActive) {
      ExpoSpeechRecognitionModule.stop();
      return;
    }
    const permission = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
    if (!permission.granted) {
      Alert.alert("语音输入不可用", "请先允许麦克风和语音识别权限。");
      return;
    }
    ExpoSpeechRecognitionModule.start({
      lang: "zh-CN",
      interimResults: true,
      continuous: false,
      addsPunctuation: true,
      contextualStrings: [selectedClientName, selectedEventLine?.name, title].filter((item): item is string => Boolean(item)),
    });
  }, [isVoiceInputActive, selectedClientName, selectedEventLine?.name, title]);

  const actionTypes = ["材料/交付", "会议/沟通", "内部分析"];

  return (
    <View style={s.overlay}>
      <View style={[s.header, { paddingTop: chrome.headerTopPadding }]}>
        <TouchableOpacity onPress={onClose} style={s.closeBtn}><X size={24} color={colors.textTertiary} /></TouchableOpacity>
        <Text style={s.headerTitle}>{task ? "编辑任务" : "快速新建任务"}</Text>
        <TouchableOpacity
          onPress={() => {
            void handleSubmit();
          }}
          disabled={submitting}
        >
          <Text style={s.draftText}>{task ? "保存" : "创建"}</Text>
        </TouchableOpacity>
      </View>
      <ScrollView style={s.body} contentContainerStyle={[s.bodyContent, { paddingBottom: chrome.overlayBottomPadding + 88 }]}>
        <View style={s.titleArea}>
          <TextInput style={s.titleInput} placeholder="准备做什么？(可使用语音输入)" placeholderTextColor={colors.textTertiary} value={title} onChangeText={setTitle} multiline autoFocus />
          <TouchableOpacity
            style={[s.micBtn, isVoiceInputActive && s.micBtnActive]}
            onPress={() => {
              void handleToggleVoiceInput();
            }}
          >
            <Mic size={20} color={isVoiceInputActive ? colors.textOnBrand : colors.brand} />
          </TouchableOpacity>
        </View>
        <View style={s.descriptionCard}>
          <Text style={s.descriptionLabel}>{activeDraft ? "智能输入摘要" : "详细内容"}</Text>
          <TextInput
            style={s.descriptionInput}
            placeholder="补充任务详情、背景和备注"
            placeholderTextColor={colors.textTertiary}
            value={description}
            onChangeText={setDescription}
            multiline
            textAlignVertical="top"
          />
        </View>
        <View style={s.contextCard}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}><Sparkles size={14} color="#4338CA" /><Text style={s.contextLabel}>{activeDraft ? "已根据智能输入自动关联" : "已根据当前场景自动关联"}</Text></View>
          {/* Client selector */}
          <TouchableOpacity style={s.contextRow} onPress={() => setShowClientPicker(true)}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}><Briefcase size={14} color={colors.textSecondary} /><Text style={s.contextKey}>关联项目</Text></View>
            <View style={s.contextVal}>
              <Text style={s.contextValText}>{selectedClientName ?? "选择项目"}</Text>
              <ChevronRight size={14} color={colors.textTertiary} />
            </View>
          </TouchableOpacity>
          {/* Event line selector */}
          <TouchableOpacity style={s.contextRow} onPress={() => setShowEventLinePicker(true)}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}><ListTodo size={14} color={colors.textSecondary} /><Text style={s.contextKey}>所在事件线</Text></View>
            <View style={s.contextVal}>
              <Text style={s.contextValText} numberOfLines={1}>{selectedEventLine?.name ?? "选择事件线"}</Text>
              <ChevronRight size={14} color={colors.textTertiary} />
            </View>
          </TouchableOpacity>
        </View>
        {/* Client picker modal */}
        <Modal visible={showClientPicker} transparent animationType="fade" onRequestClose={() => setShowClientPicker(false)}>
          <Pressable style={s.pickerOverlay} onPress={() => setShowClientPicker(false)}>
            <View style={s.pickerCardWrap} onStartShouldSetResponder={() => true}>
              <ScrollView style={s.pickerCard} keyboardShouldPersistTaps="handled">
                <Text style={s.pickerTitle}>选择关联项目</Text>
                {projectOptions.map((project) => (
                  <TouchableOpacity key={project.id} style={[s.pickerItem, selectedProjectKey === project.id && s.pickerItemActive]} onPress={() => handleSelectClient(project)}>
                    <Text style={[s.pickerItemText, selectedProjectKey === project.id && s.pickerItemTextActive]}>{project.name}</Text>
                  </TouchableOpacity>
                ))}
                {projectOptions.length === 0 && <Text style={s.pickerEmpty}>暂无可选项目，将按事件线自动关联</Text>}
                <TouchableOpacity style={s.pickerItem} onPress={() => { syncSelectionFromEventLine(null, "manual"); setShowClientPicker(false); }}>
                  <Text style={[s.pickerItemText, { color: "#9CA3AF" }]}>清除关联</Text>
                </TouchableOpacity>
              </ScrollView>
            </View>
          </Pressable>
        </Modal>
        {/* Event line picker modal */}
        <Modal visible={showEventLinePicker} transparent animationType="fade" onRequestClose={() => { setShowEventLinePicker(false); setIsCreatingEventLine(false); setNewEventLineName(""); }}>
          <Pressable style={s.pickerOverlay} onPress={() => { setShowEventLinePicker(false); setIsCreatingEventLine(false); setNewEventLineName(""); }}>
            <View style={s.pickerCardWrap} onStartShouldSetResponder={() => true}>
              <ScrollView style={s.pickerCard} keyboardShouldPersistTaps="handled">
                <Text style={s.pickerTitle}>选择事件线{selectedClientName ? ` · ${selectedClientName}` : ""}</Text>
                {isCreatingEventLine ? (
                  <View style={s.newEventLineRow}>
                    <TextInput
                      style={s.newEventLineInput}
                      placeholder="输入事件线名称"
                      placeholderTextColor="#9CA3AF"
                      value={newEventLineName}
                      onChangeText={setNewEventLineName}
                      autoFocus
                    />
                    <View style={{ flexDirection: "row", gap: 8, marginTop: 10 }}>
                      <TouchableOpacity
                        style={[s.newEventLineBtn, creatingEventLineLoading && { opacity: 0.5 }]}
                        onPress={handleCreateEventLine}
                        disabled={creatingEventLineLoading}
                      >
                        <Text style={s.newEventLineBtnText}>{creatingEventLineLoading ? "创建中..." : "确认创建"}</Text>
                      </TouchableOpacity>
                      <TouchableOpacity
                        style={s.newEventLineCancelBtn}
                        onPress={() => { setIsCreatingEventLine(false); setNewEventLineName(""); }}
                      >
                        <Text style={s.newEventLineCancelText}>取消</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                ) : (
                  <TouchableOpacity style={s.pickerItem} onPress={() => setIsCreatingEventLine(true)}>
                    <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                      <Plus size={14} color="#2563EB" />
                      <Text style={[s.pickerItemText, { color: "#2563EB", fontWeight: "700" }]}>新建事件线</Text>
                    </View>
                  </TouchableOpacity>
                )}
                {filteredEventLines.map((el) => (
                  <TouchableOpacity key={el.id} style={[s.pickerItem, selectedEventLine?.id === el.id && s.pickerItemActive]} onPress={() => { syncSelectionFromEventLine(el, "manual"); setShowEventLinePicker(false); setIsCreatingEventLine(false); setNewEventLineName(""); }}>
                    <Text style={[s.pickerItemText, selectedEventLine?.id === el.id && s.pickerItemTextActive]} numberOfLines={1}>{el.name}</Text>
                  </TouchableOpacity>
                ))}
                {filteredEventLines.length === 0 && !isCreatingEventLine && <Text style={s.pickerEmpty}>该项目下暂无事件线</Text>}
                <TouchableOpacity style={s.pickerItem} onPress={() => { syncSelectionFromEventLine(null, "manual"); setShowEventLinePicker(false); setIsCreatingEventLine(false); setNewEventLineName(""); }}>
                  <Text style={[s.pickerItemText, { color: "#9CA3AF" }]}>清除关联</Text>
                </TouchableOpacity>
              </ScrollView>
            </View>
          </Pressable>
        </Modal>
        <View style={s.props}>
          <TouchableOpacity style={s.propRow} onPress={() => setShowDatePicker(true)}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}><Calendar size={20} color={colors.accent} /><Text style={s.propLabel}>设置时间</Text></View>
            <Text style={s.propDateHint}>{customDate ? `${customDate.replace(/-/g, "/")}${customTime ? " " + customTime : ""}` : (() => { const d = new Date(); return `${d.getFullYear()}/${d.getMonth()+1}/${d.getDate()} ${String(d.getHours()).padStart(2,"0")}:${String(d.getMinutes()).padStart(2,"0")}`; })()}</Text>
          </TouchableOpacity>
          {showDatePicker && (
            <DateTimePickerSheet
              value={{
                date: customDate ?? (preset?.dueDate ?? null),
                time: customTime ?? (preset?.dueTime ?? null),
                durationMinutes: null,
              }}
              onChange={(v) => {
                setCustomDate(v.date);
                setCustomTime(v.time);
              }}
              onClose={() => setShowDatePicker(false)}
              onClear={() => { setCustomDate(null); setCustomTime(null); }}
            />
          )}
          <View style={s.propRow}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}><Tag size={20} color={colors.accent} /><Text style={s.propLabel}>动作类型</Text></View>
            <View style={s.chips}>{actionTypes.map(t => (
              <TouchableOpacity key={t} style={[s.chip, actionType === t && s.chipBrand]} onPress={() => setActionType(t)}>
                <Text style={[s.chipText, actionType === t && s.chipTextActive]}>{t}</Text>
              </TouchableOpacity>
            ))}</View>
          </View>
          <View style={s.propRow}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}><User size={20} color={colors.accent} /><Text style={s.propLabel}>执行 / 协同</Text></View>
            <View style={s.assigneeBtn}>
              <View style={s.assigneeAvatar}><Text style={s.assigneeAvatarText}>我</Text></View>
              <Text style={s.assigneeText}>默认分派给我</Text>
            </View>
          </View>
        </View>
      </ScrollView>
      <View style={[s.bottomBar, { paddingBottom: chrome.overlayBottomPadding }]}>
        <TouchableOpacity style={[s.submitBtn, submitting && s.submitBtnDisabled]} onPress={handleSubmit} disabled={submitting}>
          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6 }}>{!submitting && <CheckCircle2 size={20} color="#fff" />}<Text style={s.submitBtnText}>{submitting ? (task ? "保存中..." : "创建中...") : (task ? "保存修改" : "创建任务")}</Text></View>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  overlay: { position: "absolute", top: 0, left: 0, right: 0, bottom: 0, backgroundColor: colors.surface, zIndex: 50 },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 16, paddingTop: 0, paddingBottom: 12, borderBottomWidth: 1, borderBottomColor: colors.borderLight },
  closeBtn: { padding: 8 }, closeText: { fontSize: 20, color: colors.textTertiary },
  headerTitle: { fontSize: 14, fontWeight: "700", color: colors.text },
  draftText: { fontSize: 14, fontWeight: "700", color: colors.accent },
  body: { flex: 1 }, bodyContent: { padding: 20, paddingBottom: 0 },
  titleArea: { position: "relative", marginBottom: 20 },
  titleInput: { fontSize: 22, fontWeight: "700", color: colors.text, minHeight: 80, textAlignVertical: "top", paddingRight: 44 },
  micBtn: { position: "absolute", right: 0, bottom: 4, padding: 8, backgroundColor: colors.surfaceSecondary, borderRadius: 20 },
  micBtnActive: { backgroundColor: colors.brand },
  micIcon: { fontSize: 18 },
  descriptionCard: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, padding: 16, marginBottom: 20, borderWidth: 1, borderColor: colors.borderLight },
  descriptionLabel: { fontSize: 12, fontWeight: "700", color: colors.textSecondary, marginBottom: 10 },
  descriptionInput: { minHeight: 104, fontSize: 14, lineHeight: 22, color: colors.text },
  contextCard: { backgroundColor: "#EEF2FF", borderWidth: 1, borderColor: "#C7D2FE", borderRadius: 16, padding: 16, marginBottom: 20 },
  contextLabel: { fontSize: 11, fontWeight: "800", color: "#4338CA", marginBottom: 12, textTransform: "uppercase" as const },
  contextRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", backgroundColor: "rgba(255,255,255,0.6)", paddingHorizontal: 12, paddingVertical: 8, borderRadius: 12, borderWidth: 1, borderColor: "rgba(255,255,255,0.8)", marginBottom: 8 },
  contextKey: { fontSize: 12, color: colors.textSecondary, fontWeight: "500" },
  contextVal: { flexDirection: "row", alignItems: "center", gap: 8 },
  contextValText: { fontSize: 14, fontWeight: "700", color: colors.text, maxWidth: 140 },
  contextX: { fontSize: 12, color: colors.textTertiary },
  props: { gap: 16, paddingTop: 8 },
  propRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingBottom: 16, borderBottomWidth: 1, borderBottomColor: colors.borderLight },
  propLabel: { fontSize: 14, fontWeight: "500", color: colors.textSecondary },
  propDateHint: { fontSize: 13, color: "#9CA3AF", fontWeight: "400" },
  chips: { flexDirection: "row", gap: 8 },
  chip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, backgroundColor: colors.surfaceSecondary },
  chipActive: { backgroundColor: colors.accentBg2, borderWidth: 1, borderColor: colors.accent },
  chipBrand: { backgroundColor: colors.brandBg2, borderWidth: 1, borderColor: colors.brand },
  chipText: { fontSize: 12, fontWeight: "500", color: colors.textSecondary },
  chipTextActive: { color: colors.text, fontWeight: "700" },
  assigneeBtn: { flexDirection: "row", alignItems: "center", backgroundColor: colors.surfaceSecondary, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, gap: 6 },
  assigneeAvatar: { width: 16, height: 16, borderRadius: 8, backgroundColor: colors.brand, alignItems: "center", justifyContent: "center" },
  assigneeAvatarText: { fontSize: 8, fontWeight: "700", color: colors.textOnBrand },
  assigneeText: { fontSize: 14, fontWeight: "700", color: colors.text },
  assigneeChevron: { fontSize: 14, color: colors.textTertiary },
  bottomBar: { position: "absolute", bottom: 0, left: 0, right: 0, padding: 16, paddingBottom: 0, borderTopWidth: 1, borderTopColor: colors.borderLight, backgroundColor: colors.surface },
  submitBtn: { backgroundColor: colors.accent, borderRadius: 16, paddingVertical: 14, alignItems: "center", ...shadow.elevated },
  submitBtnDisabled: { opacity: 0.6 },
  submitBtnText: { fontSize: 18, fontWeight: "800", color: colors.textOnBrand },
  // Picker modals
  pickerOverlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.3)", justifyContent: "center", alignItems: "center", paddingHorizontal: 40 },
  pickerCardWrap: { width: "100%" },
  pickerCard: { backgroundColor: "#FFFFFF", borderRadius: 16, paddingVertical: 8, width: "100%", maxHeight: 400, shadowColor: "#000", shadowOffset: { width: 0, height: 8 }, shadowOpacity: 0.15, shadowRadius: 24, elevation: 8 },
  pickerTitle: { fontSize: 14, fontWeight: "700", color: "#6B7280", paddingHorizontal: 20, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: "#F3F4F6" },
  pickerItem: { paddingHorizontal: 20, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: "#F9FAFB" },
  pickerItemActive: { backgroundColor: "#EFF6FF" },
  pickerItemText: { fontSize: 15, fontWeight: "500", color: "#1F2937" },
  pickerItemTextActive: { color: "#2563EB", fontWeight: "700" },
  pickerEmpty: { fontSize: 13, color: "#9CA3AF", paddingHorizontal: 20, paddingVertical: 14, textAlign: "center" },
  newEventLineRow: { paddingHorizontal: 20, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: "#F3F4F6" },
  newEventLineInput: { fontSize: 15, fontWeight: "500", color: "#1F2937", borderWidth: 1, borderColor: "#D1D5DB", borderRadius: 10, paddingHorizontal: 14, paddingVertical: 10, backgroundColor: "#F9FAFB" },
  newEventLineBtn: { flex: 1, backgroundColor: "#2563EB", borderRadius: 10, paddingVertical: 10, alignItems: "center" },
  newEventLineBtnText: { fontSize: 14, fontWeight: "700", color: "#FFFFFF" },
  newEventLineCancelBtn: { flex: 1, backgroundColor: "#F3F4F6", borderRadius: 10, paddingVertical: 10, alignItems: "center" },
  newEventLineCancelText: { fontSize: 14, fontWeight: "500", color: "#6B7280" },
});
~~~

## `mobile/components/DateTimePickerSheet.tsx`

- 编码: `utf-8`

~~~tsx
/**
 * DateTimePickerSheet – TickTick-style date & time picker bottom sheet.
 *
 * Two tabs:
 *   1. "日期"    – Month calendar grid + optional time + reminder
 *   2. "时间段"  – Visual timeline to drag a time range + all-day toggle
 *
 * Props:
 *   value      – current { date, time, durationMinutes } (may be partial)
 *   onChange   – called with updated values on confirm
 *   onClose    – dismiss
 *   onClear    – optional: remove date entirely
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Animated,
  Dimensions,
  PanResponder,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { X, Check, ChevronLeft, ChevronRight, Clock, Bell, Repeat } from "lucide-react-native";
import { colors, fontSize, spacing, borderRadius, shadow } from "../lib/theme";

// ─── Types ──────────────────────────────────────

export interface DateTimeValue {
  /** ISO date string "YYYY-MM-DD" */
  date: string | null;
  /** "HH:mm" */
  time: string | null;
  /** Duration in minutes (for time-range mode) */
  durationMinutes: number | null;
}

interface Props {
  value: DateTimeValue;
  onChange: (v: DateTimeValue) => void;
  onClose: () => void;
  onClear?: () => void;
}

// ─── Constants ──────────────────────────────────

const SCREEN_WIDTH = Dimensions.get("window").width;
const WEEKDAY_LABELS = ["日", "一", "二", "三", "四", "五", "六"] as const;
const TIMELINE_HOUR_START = 6;
const TIMELINE_HOUR_END = 23;
const TIMELINE_HOURS = TIMELINE_HOUR_END - TIMELINE_HOUR_START + 1;
const TIMELINE_ROW_H = 48;
const TIMELINE_TOTAL_H = TIMELINE_HOURS * TIMELINE_ROW_H;
const HANDLE_SIZE = 20;
const MIN_DURATION = 15; // minimum 15 min

// ─── Helpers ────────────────────────────────────

function today(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function parseMonthYear(dateStr: string): [number, number] {
  const [y, m] = dateStr.split("-").map(Number);
  return [y, m];
}

function isToday(dateStr: string): boolean {
  return dateStr === today();
}

function isSameDay(a: string, b: string | null): boolean {
  if (!b) return false;
  return a === b;
}

function monthDays(year: number, month: number) {
  const first = new Date(year, month - 1, 1);
  const daysInMonth = new Date(year, month, 0).getDate();
  const startWeekday = first.getDay();
  const cells: { dateStr: string; day: number; isCurrentMonth: boolean }[] = [];

  // Previous month padding
  if (startWeekday > 0) {
    const prevDays = new Date(year, month - 1, 0).getDate();
    const prevMonth = month === 1 ? 12 : month - 1;
    const prevYear = month === 1 ? year - 1 : year;
    for (let i = startWeekday - 1; i >= 0; i--) {
      const day = prevDays - i;
      cells.push({
        dateStr: `${prevYear}-${String(prevMonth).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
        day,
        isCurrentMonth: false,
      });
    }
  }
  // Current month
  for (let day = 1; day <= daysInMonth; day++) {
    cells.push({
      dateStr: `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
      day,
      isCurrentMonth: true,
    });
  }
  // Next month padding
  const remaining = 7 - (cells.length % 7);
  if (remaining < 7) {
    const nextMonth = month === 12 ? 1 : month + 1;
    const nextYear = month === 12 ? year + 1 : year;
    for (let day = 1; day <= remaining; day++) {
      cells.push({
        dateStr: `${nextYear}-${String(nextMonth).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
        day,
        isCurrentMonth: false,
      });
    }
  }
  return cells;
}

function weekdayLabel(dateStr: string): string {
  const d = new Date(dateStr);
  return ["周日", "周一", "周二", "周三", "周四", "周五", "周六"][d.getDay()];
}

function formatMonthDay(dateStr: string): string {
  const [, m, d] = dateStr.split("-").map(Number);
  return `${m}月${d}日`;
}

function formatDuration(mins: number): string {
  if (mins < 60) return `${mins}分钟`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m > 0 ? `${h}小时${m}分钟` : `${h}小时`;
}

function minutesToTimeStr(totalMins: number): string {
  const h = Math.floor(totalMins / 60);
  const m = totalMins % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function timeStrToMinutes(t: string): number {
  const [h, m] = t.split(":").map(Number);
  return h * 60 + m;
}

function minutesToY(mins: number): number {
  return ((mins - TIMELINE_HOUR_START * 60) / 60) * TIMELINE_ROW_H;
}

function yToMinutes(y: number): number {
  const raw = (y / TIMELINE_ROW_H) * 60 + TIMELINE_HOUR_START * 60;
  return Math.round(raw / 5) * 5; // snap to 5-min
}

// ─── TIME PICKER (hour grid) ────────────────────

function TimeGrid({
  selected,
  onSelect,
}: {
  selected: string | null;
  onSelect: (t: string) => void;
}) {
  const hours = useMemo(() => {
    const result: string[] = [];
    for (let h = 0; h < 24; h++) {
      result.push(`${String(h).padStart(2, "0")}:00`);
      result.push(`${String(h).padStart(2, "0")}:30`);
    }
    return result;
  }, []);

  return (
    <View style={gs.timeGrid}>
      {hours.map((t) => {
        const isSel = t === selected;
        return (
          <TouchableOpacity
            key={t}
            style={[gs.timeGridCell, isSel && gs.timeGridCellSelected]}
            onPress={() => onSelect(t)}
            activeOpacity={0.6}
          >
            <Text style={[gs.timeGridText, isSel && gs.timeGridTextSelected]}>{t}</Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

// ─── VISUAL TIMELINE (scrollable + draggable block) ──────────

const TIMELINE_VISIBLE_H = 260;

function VisualTimeline({
  startMins,
  endMins,
  onChangeRange,
}: {
  startMins: number;
  endMins: number;
  onChangeRange: (start: number, end: number) => void;
}) {
  const scrollRef = useRef<ScrollView>(null);
  const [scrollLocked, setScrollLocked] = useState(false);
  const startY = useRef(0);
  const endYRef = useRef(0);
  const blockOffset = useRef(0);

  // Auto-scroll to the time block on mount
  useEffect(() => {
    const targetY = minutesToY(startMins) - 60; // 60px above block
    setTimeout(() => {
      scrollRef.current?.scrollTo({ y: Math.max(0, targetY), animated: false });
    }, 100);
  }, []); // only on mount

  // Block drag (move both handles together)
  const blockPan = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: (_, g) => Math.abs(g.dy) > 4,
        onPanResponderGrant: () => {
          setScrollLocked(true);
          blockOffset.current = minutesToY(startMins);
        },
        onPanResponderMove: (_, g) => {
          const duration = endMins - startMins;
          const maxStartY = TIMELINE_TOTAL_H - (duration / 60) * TIMELINE_ROW_H;
          const newStartY = Math.max(0, Math.min(blockOffset.current + g.dy, maxStartY));
          const newStart = yToMinutes(newStartY);
          const newEnd = newStart + duration;
          if (newStart >= TIMELINE_HOUR_START * 60 && newEnd <= (TIMELINE_HOUR_END + 1) * 60) {
            onChangeRange(newStart, newEnd);
          }
        },
        onPanResponderRelease: () => { setScrollLocked(false); },
        onPanResponderTerminate: () => { setScrollLocked(false); },
      }),
    [startMins, endMins, onChangeRange],
  );

  // Top handle (change start time)
  const topPan = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: (_, g) => Math.abs(g.dy) > 3,
        onPanResponderGrant: () => {
          setScrollLocked(true);
          startY.current = minutesToY(startMins);
        },
        onPanResponderMove: (_, g) => {
          const newY = startY.current + g.dy;
          const newStart = yToMinutes(Math.max(0, newY));
          if (newStart < endMins - MIN_DURATION && newStart >= TIMELINE_HOUR_START * 60) {
            onChangeRange(newStart, endMins);
          }
        },
        onPanResponderRelease: () => { setScrollLocked(false); },
        onPanResponderTerminate: () => { setScrollLocked(false); },
      }),
    [startMins, endMins, onChangeRange],
  );

  // Bottom handle (change end time)
  const bottomPan = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: (_, g) => Math.abs(g.dy) > 3,
        onPanResponderGrant: () => {
          setScrollLocked(true);
          endYRef.current = minutesToY(endMins);
        },
        onPanResponderMove: (_, g) => {
          const newY = endYRef.current + g.dy;
          const newEnd = yToMinutes(Math.max(0, newY));
          if (newEnd > startMins + MIN_DURATION && newEnd <= (TIMELINE_HOUR_END + 1) * 60) {
            onChangeRange(startMins, newEnd);
          }
        },
        onPanResponderRelease: () => { setScrollLocked(false); },
        onPanResponderTerminate: () => { setScrollLocked(false); },
      }),
    [startMins, endMins, onChangeRange],
  );

  const blockTop = minutesToY(startMins);
  const blockHeight = minutesToY(endMins) - blockTop;

  // Current time indicator
  const now = new Date();
  const nowMins = now.getHours() * 60 + now.getMinutes();
  const showNowLine = nowMins >= TIMELINE_HOUR_START * 60 && nowMins <= (TIMELINE_HOUR_END + 1) * 60;
  const nowY = minutesToY(nowMins);

  return (
    <ScrollView
      ref={scrollRef}
      style={gs.timelineScrollView}
      contentContainerStyle={gs.timelineContainer}
      showsVerticalScrollIndicator={false}
      scrollEnabled={!scrollLocked}
      nestedScrollEnabled
    >
      {/* Hour labels */}
      {Array.from({ length: TIMELINE_HOURS }, (_, i) => {
        const hour = TIMELINE_HOUR_START + i;
        return (
          <View key={hour} style={[gs.timelineRow, { height: TIMELINE_ROW_H }]}>
            <Text style={gs.timelineHourLabel}>{String(hour).padStart(2, "0")}</Text>
            <View style={gs.timelineHourLine} />
            <View style={[gs.timelineHalfLine, { top: TIMELINE_ROW_H / 2 }]} />
          </View>
        );
      })}

      {/* Time block (draggable) */}
      <View
        style={[gs.timeBlock, { top: blockTop, height: Math.max(blockHeight, 36) }]}
        {...blockPan.panHandlers}
      >
        <Text style={gs.timeBlockLabel}>
          {minutesToTimeStr(startMins)} - {minutesToTimeStr(endMins)}
        </Text>
        <Text style={gs.timeBlockDuration}>{formatDuration(endMins - startMins)}</Text>
      </View>

      {/* Top handle */}
      <View
        style={[gs.handle, gs.handleTop, { top: blockTop - HANDLE_SIZE / 2 }]}
        {...topPan.panHandlers}
      >
        <View style={gs.handleDot} />
      </View>

      {/* Bottom handle */}
      <View
        style={[gs.handle, gs.handleBottom, { top: blockTop + blockHeight - HANDLE_SIZE / 2 }]}
        {...bottomPan.panHandlers}
      >
        <View style={gs.handleDot} />
      </View>

      {/* Current time line */}
      {showNowLine && (
        <View style={[gs.nowLine, { top: nowY }]} pointerEvents="none">
          <View style={gs.nowDot} />
          <View style={gs.nowBar} />
        </View>
      )}
    </ScrollView>
  );
}

// ═════════════════════════════════════════════════
// ─── MAIN COMPONENT ─────────────────────────────
// ═════════════════════════════════════════════════

export default function DateTimePickerSheet({ value, onChange, onClose, onClear }: Props) {
  const todayStr = today();

  // Local state
  const initialDate = value.date ?? todayStr;
  const [selectedDate, setSelectedDate] = useState(initialDate);
  const [selectedTime, setSelectedTime] = useState<string | null>(value.time);
  const [showTimeGrid, setShowTimeGrid] = useState(false);
  const [duration, setDuration] = useState(value.durationMinutes ?? 60);
  const [isAllDay, setIsAllDay] = useState(!value.time);

  // Tab: "date" or "range"
  const [tab, setTab] = useState<"date" | "range">(
    value.durationMinutes && value.durationMinutes > 0 ? "range" : "date",
  );

  // Calendar month navigation
  const [calYear, calMonth] = parseMonthYear(selectedDate);
  const [viewYear, setViewYear] = useState(calYear);
  const [viewMonth, setViewMonth] = useState(calMonth);

  const days = useMemo(() => monthDays(viewYear, viewMonth), [viewYear, viewMonth]);

  const prevMonth = useCallback(() => {
    setViewMonth((m) => {
      if (m === 1) { setViewYear((y) => y - 1); return 12; }
      return m - 1;
    });
  }, []);
  const nextMonth = useCallback(() => {
    setViewMonth((m) => {
      if (m === 12) { setViewYear((y) => y + 1); return 1; }
      return m + 1;
    });
  }, []);

  // Time-range state (for "时间段" tab)
  const initialStartMins = selectedTime ? timeStrToMinutes(selectedTime) : 9 * 60;
  const [rangeStart, setRangeStart] = useState(initialStartMins);
  const [rangeEnd, setRangeEnd] = useState(initialStartMins + duration);

  const handleRangeChange = useCallback((start: number, end: number) => {
    setRangeStart(start);
    setRangeEnd(end);
    setSelectedTime(minutesToTimeStr(start));
    setDuration(end - start);
    setIsAllDay(false);
  }, []);

  // Confirm
  const handleConfirm = useCallback(() => {
    if (tab === "range" && !isAllDay) {
      onChange({
        date: selectedDate,
        time: minutesToTimeStr(rangeStart),
        durationMinutes: rangeEnd - rangeStart,
      });
    } else if (isAllDay) {
      onChange({
        date: selectedDate,
        time: null,
        durationMinutes: null,
      });
    } else {
      onChange({
        date: selectedDate,
        time: selectedTime,
        durationMinutes: duration > 0 ? duration : null,
      });
    }
    onClose();
  }, [tab, isAllDay, selectedDate, selectedTime, rangeStart, rangeEnd, duration, onChange, onClose]);

  // Select time from grid
  const handleTimeSelect = useCallback((t: string) => {
    setSelectedTime(t);
    setShowTimeGrid(false);
    setIsAllDay(false);
    // Update range too
    const mins = timeStrToMinutes(t);
    setRangeStart(mins);
    setRangeEnd(mins + duration);
  }, [duration]);

  // ═════ RENDER ═════

  return (
    <View style={s.overlay}>
      <Pressable style={s.backdrop} onPress={onClose} />
      <Animated.View style={s.sheet}>
        {/* Top bar: close / tabs / confirm */}
        <View style={s.topBar}>
          <TouchableOpacity onPress={onClose} hitSlop={12}>
            <X size={22} color={colors.text} />
          </TouchableOpacity>
          <View style={s.tabRow}>
            <TouchableOpacity
              style={[s.tabButton, tab === "date" && s.tabButtonActive]}
              onPress={() => setTab("date")}
            >
              <Text style={[s.tabLabel, tab === "date" && s.tabLabelActive]}>日期</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[s.tabButton, tab === "range" && s.tabButtonActive]}
              onPress={() => setTab("range")}
            >
              <Text style={[s.tabLabel, tab === "range" && s.tabLabelActive]}>时间段</Text>
            </TouchableOpacity>
          </View>
          <TouchableOpacity onPress={handleConfirm} hitSlop={12}>
            <Check size={22} color={colors.brand} />
          </TouchableOpacity>
        </View>

        {/* ═══════ DATE TAB ═══════ */}
        {tab === "date" && (
          <View style={s.tabContent}>
            {/* Month navigation */}
            <View style={s.monthNav}>
              <Text style={s.monthTitle}>{viewMonth}月</Text>
              {viewYear !== new Date().getFullYear() && (
                <Text style={s.yearLabel}>{viewYear}年</Text>
              )}
              <View style={s.monthNavRight}>
                <TouchableOpacity onPress={prevMonth} hitSlop={10}>
                  <ChevronLeft size={20} color={colors.textSecondary} />
                </TouchableOpacity>
                <TouchableOpacity onPress={nextMonth} hitSlop={10}>
                  <ChevronRight size={20} color={colors.textSecondary} />
                </TouchableOpacity>
              </View>
            </View>

            {/* Weekday header */}
            <View style={s.weekRow}>
              {WEEKDAY_LABELS.map((label) => (
                <Text key={label} style={s.weekLabel}>{label}</Text>
              ))}
            </View>

            {/* Days grid */}
            <View style={s.daysGrid}>
              {days.map((cell, idx) => {
                const isTd = isToday(cell.dateStr);
                const isSel = isSameDay(cell.dateStr, selectedDate);
                return (
                  <TouchableOpacity
                    key={idx}
                    style={s.dayCell}
                    onPress={() => setSelectedDate(cell.dateStr)}
                    activeOpacity={0.6}
                  >
                    <View style={[s.dayCircle, isSel && s.dayCircleSel, isTd && !isSel && s.dayCircleToday]}>
                      <Text
                        style={[
                          s.dayText,
                          !cell.isCurrentMonth && s.dayTextOther,
                          isSel && s.dayTextSel,
                          isTd && !isSel && s.dayTextToday,
                        ]}
                      >
                        {cell.day}
                      </Text>
                    </View>
                  </TouchableOpacity>
                );
              })}
            </View>

            {/* Options: time, reminder */}
            <View style={s.optionsSection}>
              {/* Time row */}
              <TouchableOpacity
                style={s.optionRow}
                onPress={() => setShowTimeGrid((v) => !v)}
                activeOpacity={0.6}
              >
                <Clock size={18} color={colors.textSecondary} />
                <Text style={s.optionLabel}>时间</Text>
                {selectedTime && !isAllDay ? (
                  <View style={s.optionValueRow}>
                    <Text style={s.optionValueBlue}>{selectedTime}</Text>
                    <TouchableOpacity
                      hitSlop={8}
                      onPress={() => { setSelectedTime(null); setIsAllDay(true); setShowTimeGrid(false); }}
                    >
                      <X size={14} color={colors.textTertiary} />
                    </TouchableOpacity>
                  </View>
                ) : (
                  <Text style={s.optionValueGray}>无</Text>
                )}
              </TouchableOpacity>

              {/* Inline time grid */}
              {showTimeGrid && (
                <TimeGrid selected={selectedTime} onSelect={handleTimeSelect} />
              )}

              {/* Reminder row (placeholder) */}
              <View style={s.optionRow}>
                <Bell size={18} color={colors.textSecondary} />
                <Text style={s.optionLabel}>提醒</Text>
                <Text style={s.optionValueGray}>准时</Text>
              </View>

              {/* Repeat row (placeholder) */}
              <View style={s.optionRow}>
                <Repeat size={18} color={colors.textSecondary} />
                <Text style={s.optionLabel}>重复</Text>
                <Text style={s.optionValueGray}>无</Text>
              </View>
            </View>
          </View>
        )}

        {/* ═══════ TIME RANGE TAB ═══════ */}
        {tab === "range" && (
          <View style={s.tabContent}>
            {/* Summary cards: date + time range */}
            <View style={s.rangeSummary}>
              <View style={s.rangeSummaryCard}>
                <Text style={s.rangeSummaryLabel}>日期</Text>
                <Text style={s.rangeSummaryValue}>
                  {formatMonthDay(selectedDate)}, {weekdayLabel(selectedDate)}
                </Text>
                {isToday(selectedDate) && <Text style={s.rangeSummaryHint}>今天</Text>}
              </View>
              <View style={s.rangeSummaryCard}>
                <Text style={s.rangeSummaryLabel}>时间</Text>
                {isAllDay ? (
                  <Text style={s.rangeSummaryValue}>全天</Text>
                ) : (
                  <>
                    <Text style={s.rangeSummaryValue}>
                      {minutesToTimeStr(rangeStart)} - {minutesToTimeStr(rangeEnd)}
                    </Text>
                    <Text style={s.rangeSummaryHint}>持续时间: {formatDuration(rangeEnd - rangeStart)}</Text>
                  </>
                )}
              </View>
            </View>

            {/* All-day toggle */}
            <TouchableOpacity
              style={s.allDayRow}
              onPress={() => {
                const next = !isAllDay;
                setIsAllDay(next);
                if (!next && !selectedTime) {
                  setSelectedTime("09:00");
                  setRangeStart(9 * 60);
                  setRangeEnd(10 * 60);
                }
              }}
              activeOpacity={0.6}
            >
              <Text style={s.allDayLabel}>全天</Text>
              <View style={[s.toggle, isAllDay && s.toggleOn]}>
                <View style={[s.toggleKnob, isAllDay && s.toggleKnobOn]} />
              </View>
            </TouchableOpacity>

            {/* Visual timeline */}
            {!isAllDay && (
              <VisualTimeline
                startMins={rangeStart}
                endMins={rangeEnd}
                onChangeRange={handleRangeChange}
              />
            )}

            {/* Reminder / repeat placeholders */}
            <View style={s.optionsSection}>
              <View style={s.optionRow}>
                <Bell size={18} color={colors.textSecondary} />
                <Text style={s.optionLabel}>提醒</Text>
                <Text style={s.optionValueGray}>准时</Text>
              </View>
              <View style={s.optionRow}>
                <Repeat size={18} color={colors.textSecondary} />
                <Text style={s.optionLabel}>重复</Text>
                <Text style={s.optionValueGray}>无</Text>
              </View>
            </View>
          </View>
        )}

        {/* Clear button */}
        {onClear && (
          <TouchableOpacity style={s.clearButton} onPress={() => { onClear(); onClose(); }}>
            <Text style={s.clearButtonText}>清除</Text>
          </TouchableOpacity>
        )}
      </Animated.View>
    </View>
  );
}

// ═════════════════════════════════════════════════
// ─── STYLES ─────────────────────────────────────
// ═════════════════════════════════════════════════

const s = StyleSheet.create({
  overlay: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 100,
    justifyContent: "flex-end",
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0,0,0,0.45)",
  },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: borderRadius.lg,
    borderTopRightRadius: borderRadius.lg,
    maxHeight: "88%",
    ...shadow.elevated,
  },

  // Top bar
  topBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.sm,
  },
  tabRow: {
    flexDirection: "row",
    gap: spacing.xl,
  },
  tabButton: {
    paddingBottom: spacing.sm,
    borderBottomWidth: 2,
    borderBottomColor: "transparent",
  },
  tabButtonActive: {
    borderBottomColor: colors.brand,
  },
  tabLabel: {
    fontSize: fontSize.lg,
    fontWeight: "500",
    color: colors.textTertiary,
  },
  tabLabelActive: {
    color: colors.text,
    fontWeight: "700",
  },

  // Tab content
  tabContent: {
    paddingHorizontal: spacing.lg,
    paddingBottom: Platform.OS === "ios" ? 34 : spacing.lg,
  },

  // Month nav
  monthNav: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: spacing.md,
    marginBottom: spacing.sm,
    gap: spacing.sm,
  },
  monthTitle: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.text,
  },
  yearLabel: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
  monthNavRight: {
    marginLeft: "auto",
    flexDirection: "row",
    gap: spacing.md,
  },

  // Week labels
  weekRow: {
    flexDirection: "row",
    marginBottom: spacing.xs,
  },
  weekLabel: {
    flex: 1,
    textAlign: "center",
    fontSize: fontSize.xs,
    color: colors.textTertiary,
    fontWeight: "600",
  },

  // Days grid
  daysGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
  },
  dayCell: {
    width: `${100 / 7}%` as any,
    alignItems: "center",
    paddingVertical: spacing.xs + 2,
  },
  dayCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
  },
  dayCircleSel: {
    backgroundColor: colors.brand,
  },
  dayCircleToday: {
    backgroundColor: colors.brandBg2,
  },
  dayText: {
    fontSize: fontSize.md,
    color: colors.text,
  },
  dayTextOther: {
    color: colors.textTertiary,
  },
  dayTextSel: {
    color: colors.textOnBrand,
    fontWeight: "700",
  },
  dayTextToday: {
    color: colors.brand,
    fontWeight: "700",
  },

  // Options
  optionsSection: {
    marginTop: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: borderRadius.md,
    overflow: "hidden",
  },
  optionRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md + 2,
    gap: spacing.sm,
  },
  optionLabel: {
    flex: 1,
    fontSize: fontSize.md,
    color: colors.text,
  },
  optionValueBlue: {
    fontSize: fontSize.md,
    color: colors.brand,
    fontWeight: "600",
  },
  optionValueGray: {
    fontSize: fontSize.md,
    color: colors.textTertiary,
  },
  optionValueRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },

  // Range summary
  rangeSummary: {
    flexDirection: "row",
    gap: spacing.md,
    marginTop: spacing.md,
  },
  rangeSummaryCard: {
    flex: 1,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: borderRadius.md,
    padding: spacing.md,
  },
  rangeSummaryLabel: {
    fontSize: fontSize.xs,
    color: colors.textTertiary,
    marginBottom: 4,
  },
  rangeSummaryValue: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.brand,
  },
  rangeSummaryHint: {
    fontSize: fontSize.xs,
    color: colors.textTertiary,
    marginTop: 2,
  },

  // All-day toggle
  allDayRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.sm,
    marginTop: spacing.sm,
  },
  allDayLabel: {
    fontSize: fontSize.md,
    fontWeight: "500",
    color: colors.text,
  },
  toggle: {
    width: 48,
    height: 28,
    borderRadius: 14,
    backgroundColor: "#E5E7EB",
    justifyContent: "center",
    paddingHorizontal: 2,
  },
  toggleOn: {
    backgroundColor: colors.brand,
  },
  toggleKnob: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.surface,
    ...shadow.card,
  },
  toggleKnobOn: {
    alignSelf: "flex-end",
  },


  // Clear button
  clearButton: {
    alignItems: "center",
    paddingVertical: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.borderLight,
    marginBottom: Platform.OS === "ios" ? 34 : spacing.md,
  },
  clearButtonText: {
    fontSize: fontSize.md,
    color: "#EF4444",
    fontWeight: "600",
  },
});

// ─── Timeline sub-styles ────────────────────────

const gs = StyleSheet.create({
  // Time picker grid
  timeGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
    gap: spacing.xs,
    maxHeight: 180,
  },
  timeGridCell: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.sm,
    backgroundColor: colors.surface,
  },
  timeGridCellSelected: {
    backgroundColor: colors.brand,
  },
  timeGridText: {
    fontSize: fontSize.sm,
    color: colors.text,
  },
  timeGridTextSelected: {
    color: colors.textOnBrand,
    fontWeight: "700",
  },

  // Visual timeline
  timelineScrollView: {
    height: TIMELINE_VISIBLE_H,
    marginTop: spacing.sm,
  },
  timelineContainer: {
    position: "relative",
    minHeight: TIMELINE_TOTAL_H,
  },
  timelineRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    position: "relative",
  },
  timelineHourLabel: {
    width: 32,
    fontSize: fontSize.xs,
    color: colors.textTertiary,
    textAlign: "right",
    marginRight: spacing.sm,
    paddingTop: 1,
  },
  timelineHourLine: {
    flex: 1,
    height: StyleSheet.hairlineWidth,
    backgroundColor: colors.borderLight,
    marginTop: 8,
  },
  timelineHalfLine: {
    position: "absolute",
    left: 40,
    right: 0,
    height: StyleSheet.hairlineWidth,
    backgroundColor: colors.borderLight,
    opacity: 0.5,
  },

  // Time block
  timeBlock: {
    position: "absolute",
    left: 42,
    right: 8,
    backgroundColor: "rgba(37,99,235,0.7)",
    borderRadius: borderRadius.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    justifyContent: "center",
    zIndex: 10,
  },
  timeBlockLabel: {
    fontSize: fontSize.sm,
    fontWeight: "700",
    color: colors.textOnBrand,
  },
  timeBlockDuration: {
    fontSize: fontSize.xs,
    color: "rgba(255,255,255,0.8)",
    marginTop: 2,
  },

  // Handles
  handle: {
    position: "absolute",
    width: HANDLE_SIZE,
    height: HANDLE_SIZE,
    borderRadius: HANDLE_SIZE / 2,
    backgroundColor: colors.surface,
    borderWidth: 2,
    borderColor: colors.brand,
    alignItems: "center",
    justifyContent: "center",
    zIndex: 20,
    left: SCREEN_WIDTH / 2 - HANDLE_SIZE / 2 - spacing.lg,
  },
  handleTop: {},
  handleBottom: {},
  handleDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.brand,
  },

  // Current time line
  nowLine: {
    position: "absolute",
    left: 32,
    right: 0,
    flexDirection: "row",
    alignItems: "center",
    zIndex: 5,
  },
  nowDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "#EF4444",
  },
  nowBar: {
    flex: 1,
    height: 1.5,
    backgroundColor: "#EF4444",
  },
});
~~~

## `mobile/components/EventLineDrawer.tsx`

- 编码: `utf-8`

~~~tsx
import { useMemo, useState, type ReactNode } from "react";
import { ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Paperclip, Mic, CircleAlert, ChevronRight } from "lucide-react-native";
import { colors, borderRadius, fontSize, spacing, shadow } from "../lib/theme";
import type { ClientSummaryRecord, EventLineRecord, TaskRecord, WorkspaceLiteItem } from "../lib/types";

interface EventLineDrawerProps {
  visible: boolean;
  eventLine: EventLineRecord | null;
  tasks: readonly TaskRecord[];
  meetingHighlights?: readonly WorkspaceLiteItem[];
  clients?: readonly ClientSummaryRecord[];
  onClose: () => void;
  onOpenWorkspace?: () => void;
  onTaskPress?: (task: TaskRecord) => void;
  onTransferToClient?: (clientId: string) => Promise<void> | void;
  isTransferringClient?: boolean;
}

export default function EventLineDrawer({
  visible,
  eventLine,
  tasks,
  meetingHighlights = [],
  clients = [],
  onClose,
  onOpenWorkspace,
  onTaskPress,
  onTransferToClient,
  isTransferringClient = false,
}: EventLineDrawerProps) {
  const [showClientPicker, setShowClientPicker] = useState(false);
  const relatedTasks = eventLine ? tasks.filter((task) => task.eventLineId === eventLine.id) : [];
  const recentTasks = relatedTasks.slice(0, 5);
  const attachments = relatedTasks.flatMap((task) => task.attachments ?? []);
  const recentAttachments = attachments.slice(0, 4);
  const recentAudio = recentAttachments.filter((item) => item.mimeType?.startsWith("audio/")).slice(0, 3);
  const sortedClients = useMemo(
    () => [...clients].sort((left, right) => left.name.localeCompare(right.name, "zh-CN")),
    [clients],
  );
  const transferButtonLabel = eventLine?.primaryClientId ? "更改归属" : "转入客户";

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(event) => event.stopPropagation()}>
          <View style={styles.handle} />
          {eventLine ? (
            <ScrollView contentContainerStyle={styles.content}>
              <View style={styles.headerRow}>
                <View style={styles.headerCopy}>
                  <Text style={styles.title}>{eventLine.name}</Text>
                  <Text style={styles.subtitle}>
                    {eventLine.primaryClientName || "未关联客户"}
                    {eventLine.stage ? ` · ${eventLine.stage}` : ""}
                    {eventLine.status ? ` · ${eventLine.status}` : ""}
                  </Text>
                </View>
                <View style={styles.headerActions}>
                  {onTransferToClient ? (
                    <TouchableOpacity
                      style={styles.secondaryActionButton}
                      onPress={() => setShowClientPicker(true)}
                      disabled={isTransferringClient}
                    >
                      {isTransferringClient ? (
                        <ActivityIndicator size="small" color={colors.brand} />
                      ) : (
                        <Text style={styles.secondaryActionButtonText}>{transferButtonLabel}</Text>
                      )}
                    </TouchableOpacity>
                  ) : null}
                  {onOpenWorkspace && eventLine.primaryClientId ? (
                    <TouchableOpacity style={styles.workspaceButton} onPress={onOpenWorkspace}>
                      <Text style={styles.workspaceButtonText}>工作台</Text>
                    </TouchableOpacity>
                  ) : null}
                </View>
              </View>

              {onTransferToClient ? (
                <View style={styles.tipCard}>
                  <Text style={styles.tipText}>迁移归属会同步这条事件线下任务与资料的客户分类。</Text>
                </View>
              ) : null}

              <View style={styles.card}>
                <Section title="摘要" content={eventLine.summary || "暂无事件线摘要"} />
                <Section title="当前卡点" content={eventLine.currentBlocker || "暂无明确卡点"} />
                <Section title="最近判断" content={eventLine.recentDecision || "暂无最近判断"} />
                <Section title="下一步" content={eventLine.nextStep || "暂无下一步动作"} />
              </View>

              <View style={styles.metricRow}>
                <Metric icon={<CircleAlert size={14} color={colors.brand} />} label="未完成任务" value={String(relatedTasks.filter((task) => task.progressStatus !== "done").length)} />
                <Metric icon={<Paperclip size={14} color={colors.brand} />} label="最近附件" value={String(recentAttachments.length)} />
                <Metric icon={<Mic size={14} color={colors.brand} />} label="最近录音" value={String(recentAudio.length)} />
              </View>

              {meetingHighlights.length > 0 ? (
                <View style={styles.sectionBlock}>
                  <Text style={styles.sectionTitle}>最近会议片段</Text>
                  {meetingHighlights.slice(0, 2).map((item) => (
                    <View key={item.id} style={styles.listRow}>
                      <Text style={styles.listRowTitle}>{item.title}</Text>
                      {item.summary ? <Text style={styles.listRowSummary}>{item.summary}</Text> : null}
                    </View>
                  ))}
                </View>
              ) : null}

              <View style={styles.sectionBlock}>
                <Text style={styles.sectionTitle}>最近任务</Text>
                {recentTasks.length > 0 ? recentTasks.map((task) => (
                  <TouchableOpacity
                    key={task.id}
                    style={styles.taskRow}
                    onPress={() => onTaskPress?.(task)}
                    activeOpacity={0.78}
                  >
                    <View style={styles.taskRowCopy}>
                      <Text style={styles.taskTitle}>{task.title}</Text>
                      <Text style={styles.taskMeta}>
                        {task.clientName || eventLine.primaryClientName || "客户"}
                        {task.dueDate ? ` · ${task.dueDate.slice(0, 10)}` : ""}
                      </Text>
                    </View>
                    <ChevronRight size={16} color={colors.textTertiary} />
                  </TouchableOpacity>
                )) : (
                  <Text style={styles.emptyText}>这条事件线下还没有最近任务。</Text>
                )}
              </View>
            </ScrollView>
          ) : null}
        </Pressable>
      </Pressable>
      <Modal
        visible={showClientPicker && Boolean(eventLine)}
        transparent
        animationType="fade"
        onRequestClose={() => setShowClientPicker(false)}
      >
        <Pressable style={styles.pickerOverlay} onPress={() => setShowClientPicker(false)}>
          <Pressable style={styles.pickerCard} onPress={(event) => event.stopPropagation()}>
            <Text style={styles.pickerTitle}>{transferButtonLabel}</Text>
            <Text style={styles.pickerHint}>选择后会把这条事件线及其关联任务、资料一起归到目标客户下。</Text>
            <ScrollView style={styles.pickerList} showsVerticalScrollIndicator={false}>
              {sortedClients.map((client) => {
                const isActive = client.id === eventLine?.primaryClientId;
                return (
                  <TouchableOpacity
                    key={client.id}
                    style={[styles.pickerItem, isActive && styles.pickerItemActive]}
                    activeOpacity={0.82}
                    disabled={isActive || isTransferringClient}
                    onPress={async () => {
                      if (!onTransferToClient || isActive) {
                        return;
                      }
                      await onTransferToClient(client.id);
                      setShowClientPicker(false);
                    }}
                  >
                    <Text style={[styles.pickerItemText, isActive && styles.pickerItemTextActive]}>
                      {client.name}
                    </Text>
                    {isActive ? <Text style={styles.pickerItemMeta}>当前归属</Text> : null}
                  </TouchableOpacity>
                );
              })}
              {sortedClients.length === 0 ? (
                <Text style={styles.emptyText}>还没有可选客户。</Text>
              ) : null}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    </Modal>
  );
}

function Section({ title, content }: { title: string; content: string }) {
  return (
    <View style={styles.sectionItem}>
      <Text style={styles.sectionLabel}>{title}</Text>
      <Text style={styles.sectionContent}>{content}</Text>
    </View>
  );
}

function Metric({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <View style={styles.metricCard}>
      <View style={styles.metricIcon}>{icon}</View>
      <Text style={styles.metricValue}>{value}</Text>
      <Text style={styles.metricLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(15,23,42,0.24)",
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: borderRadius.xl,
    borderTopRightRadius: borderRadius.xl,
    minHeight: "58%",
    maxHeight: "86%",
    ...shadow.softCard,
  },
  handle: {
    alignSelf: "center",
    width: 42,
    height: 5,
    borderRadius: 999,
    backgroundColor: colors.border,
    marginTop: spacing.sm,
    marginBottom: spacing.md,
  },
  content: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xxl,
    gap: spacing.md,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: spacing.md,
  },
  headerCopy: {
    flex: 1,
  },
  headerActions: {
    alignItems: "flex-end",
    gap: spacing.sm,
  },
  title: {
    fontSize: fontSize.xxl,
    fontWeight: "800",
    color: colors.text,
  },
  subtitle: {
    marginTop: spacing.xs,
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  secondaryActionButton: {
    minWidth: 84,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.full,
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.borderLight,
    alignItems: "center",
    justifyContent: "center",
  },
  secondaryActionButtonText: {
    color: colors.text,
    fontSize: fontSize.sm,
    fontWeight: "700",
  },
  workspaceButton: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.full,
    backgroundColor: colors.brandBg,
    alignSelf: "flex-start",
  },
  workspaceButtonText: {
    color: colors.brand,
    fontSize: fontSize.sm,
    fontWeight: "700",
  },
  tipCard: {
    borderRadius: borderRadius.md,
    backgroundColor: colors.brandBg,
    borderWidth: 1,
    borderColor: colors.borderLight,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  tipText: {
    fontSize: fontSize.sm,
    lineHeight: 20,
    color: colors.textSecondary,
  },
  card: {
    borderRadius: borderRadius.lg,
    borderWidth: 1,
    borderColor: colors.borderLight,
    backgroundColor: colors.surfaceSecondary,
    padding: spacing.md,
    gap: spacing.sm,
  },
  sectionItem: {
    gap: spacing.xs,
  },
  sectionLabel: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    fontWeight: "800",
  },
  sectionContent: {
    fontSize: fontSize.sm,
    lineHeight: 20,
    color: colors.text,
  },
  metricRow: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  metricCard: {
    flex: 1,
    borderRadius: borderRadius.md,
    backgroundColor: colors.surfaceSecondary,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  metricIcon: {
    marginBottom: spacing.xs,
  },
  metricValue: {
    fontSize: fontSize.xl,
    color: colors.text,
    fontWeight: "800",
  },
  metricLabel: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  sectionBlock: {
    gap: spacing.sm,
  },
  sectionTitle: {
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: "800",
  },
  listRow: {
    borderRadius: borderRadius.md,
    backgroundColor: colors.surfaceSecondary,
    padding: spacing.md,
  },
  listRowTitle: {
    fontSize: fontSize.sm,
    color: colors.text,
    fontWeight: "700",
  },
  listRowSummary: {
    marginTop: spacing.xs,
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  taskRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md,
    borderRadius: borderRadius.md,
    backgroundColor: colors.surfaceSecondary,
    padding: spacing.md,
  },
  taskRowCopy: {
    flex: 1,
  },
  taskTitle: {
    fontSize: fontSize.sm,
    fontWeight: "700",
    color: colors.text,
  },
  taskMeta: {
    marginTop: spacing.xs,
    fontSize: fontSize.xs,
    color: colors.textSecondary,
  },
  emptyText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  pickerOverlay: {
    flex: 1,
    backgroundColor: "rgba(15,23,42,0.24)",
    justifyContent: "center",
    paddingHorizontal: spacing.lg,
  },
  pickerCard: {
    maxHeight: "70%",
    borderRadius: borderRadius.xl,
    backgroundColor: colors.surface,
    padding: spacing.lg,
    gap: spacing.sm,
    ...shadow.softCard,
  },
  pickerTitle: {
    fontSize: fontSize.xl,
    fontWeight: "800",
    color: colors.text,
  },
  pickerHint: {
    fontSize: fontSize.sm,
    lineHeight: 20,
    color: colors.textSecondary,
  },
  pickerList: {
    marginTop: spacing.sm,
  },
  pickerItem: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md,
    borderRadius: borderRadius.md,
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.borderLight,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    marginBottom: spacing.sm,
  },
  pickerItemActive: {
    backgroundColor: colors.brandBg,
    borderColor: colors.brand,
  },
  pickerItemText: {
    flex: 1,
    fontSize: fontSize.sm,
    color: colors.text,
    fontWeight: "700",
  },
  pickerItemTextActive: {
    color: colors.brand,
  },
  pickerItemMeta: {
    fontSize: fontSize.xs,
    color: colors.brand,
    fontWeight: "700",
  },
});
~~~

## `mobile/components/FocusBar.tsx`

- 编码: `utf-8`

~~~tsx
import { useMemo, useState } from "react";
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { ChevronDown, FilterX, Lock, Layers, FolderKanban, CalendarRange } from "lucide-react-native";
import { colors, borderRadius, spacing, fontSize, shadow } from "../lib/theme";
import {
  addDays,
  formatWeekLabelCn,
  getLocalWeekAnchorDateKey,
  parseLocalDateKey,
  weekLabelForDateKey,
} from "../lib/date";
import { useCurrentFocus } from "../lib/current-focus-store";

type PickerMode = "client" | "event_line" | "week" | null;

interface FocusBarProps {
  showAll?: boolean;
  onToggleShowAll?: () => void;
  onOpenWorkspace?: () => void;
  onOpenEventLine?: () => void;
}

const BOUNDARY_LABEL: Record<string, string> = {
  none: "暂无正式结论",
  official: "正式判断",
  pending: "待确认",
  risk: "风险",
  reminder: "提醒",
  mixed: "多层信号",
};

export default function FocusBar({
  showAll = false,
  onToggleShowAll,
  onOpenWorkspace,
  onOpenEventLine,
}: FocusBarProps) {
  const {
    focus,
    clients,
    eventLines,
    setManualClientFocus,
    setManualClientEventLineFocus,
    setCurrentFocusWeek,
    clearStoredCurrentFocus,
  } = useCurrentFocus();
  const [pickerMode, setPickerMode] = useState<PickerMode>(null);

  const eventLineOptions = useMemo(() => {
    if (!focus.clientId) {
      return [];
    }
    return eventLines.filter((item) => item.primaryClientId === focus.clientId);
  }, [eventLines, focus.clientId]);

  const generatedWeekOptions = useMemo(() => {
    const anchor = parseLocalDateKey(focus.weekAnchorDate);
    return Array.from({ length: 7 }, (_, index) => {
      const delta = index - 3;
      const nextAnchor = getLocalWeekAnchorDateKey(addDays(anchor, delta * 7));
      return {
        weekAnchorDate: nextAnchor,
        weekLabel: formatWeekLabelCn(weekLabelForDateKey(nextAnchor)),
      };
    });
  }, [focus.weekAnchorDate]);

  const boundaryLabel = BOUNDARY_LABEL[focus.boundaryState] ?? BOUNDARY_LABEL.none;
  const canLockCurrent = focus.lockMode === "browse" && Boolean(focus.clientId);

  const handleLockCurrent = () => {
    if (!focus.clientId) {
      return;
    }
    if (focus.eventLineId) {
      setManualClientEventLineFocus(focus.clientId, focus.eventLineId);
      return;
    }
    setManualClientFocus(focus.clientId);
  };

  const weekDisplayLabel = formatWeekLabelCn(focus.weekLabel);

  return (
    <View style={styles.container}>
      <View style={styles.row}>
        <TouchableOpacity style={styles.pill} activeOpacity={0.78} onPress={() => setPickerMode("client")}>
          <Text style={styles.pillLabel}>客户</Text>
          <Text style={styles.pillValue} numberOfLines={1}>
            {focus.clientName || "全部客户"}
          </Text>
          <ChevronDown size={14} color={colors.brand} />
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.pill, !focus.clientId && styles.pillDisabled]}
          activeOpacity={focus.clientId ? 0.78 : 1}
          onPress={() => focus.clientId && setPickerMode("event_line")}
        >
          <Text style={styles.pillLabel}>事件线</Text>
          <Text style={styles.pillValue} numberOfLines={1}>
            {focus.eventLineName || "未锁定事件线"}
          </Text>
          <ChevronDown size={14} color={focus.clientId ? colors.brand : colors.textTertiary} />
        </TouchableOpacity>
      </View>
      <View style={styles.row}>
        <TouchableOpacity style={[styles.pill, styles.weekPill]} activeOpacity={0.78} onPress={() => setPickerMode("week")}>
          <CalendarRange size={14} color={colors.brand} />
          <Text style={styles.weekText}>{weekDisplayLabel}</Text>
        </TouchableOpacity>
        <View style={styles.boundaryPill}>
          <Layers size={14} color={colors.textSecondary} />
          <Text style={styles.boundaryText} numberOfLines={1}>{boundaryLabel}</Text>
        </View>
      </View>
      <View style={styles.actionRow}>
        {canLockCurrent ? (
          <TouchableOpacity style={styles.actionButton} activeOpacity={0.78} onPress={handleLockCurrent}>
            <Lock size={14} color={colors.brand} />
            <Text style={styles.actionText}>锁定当前</Text>
          </TouchableOpacity>
        ) : null}
        {(focus.clientId || focus.eventLineId) ? (
          <TouchableOpacity style={styles.actionButton} activeOpacity={0.78} onPress={clearStoredCurrentFocus}>
            <FilterX size={14} color={colors.textSecondary} />
            <Text style={[styles.actionText, { color: colors.textSecondary }]}>清空</Text>
          </TouchableOpacity>
        ) : null}
        {focus.clientId && onOpenWorkspace ? (
          <TouchableOpacity style={styles.actionButton} activeOpacity={0.78} onPress={onOpenWorkspace}>
            <FolderKanban size={14} color={colors.brand} />
            <Text style={styles.actionText}>工作台</Text>
          </TouchableOpacity>
        ) : null}
        {focus.eventLineId && onOpenEventLine ? (
          <TouchableOpacity style={styles.actionButton} activeOpacity={0.78} onPress={onOpenEventLine}>
            <Layers size={14} color={colors.brand} />
            <Text style={styles.actionText}>事件线详情</Text>
          </TouchableOpacity>
        ) : null}
        {focus.lockMode !== "browse" && onToggleShowAll ? (
          <TouchableOpacity style={styles.actionButton} activeOpacity={0.78} onPress={onToggleShowAll}>
            <Text style={styles.actionText}>{showAll ? "恢复聚焦" : "显示全部"}</Text>
          </TouchableOpacity>
        ) : null}
      </View>

      <Modal visible={pickerMode !== null} animationType="fade" transparent onRequestClose={() => setPickerMode(null)}>
        <Pressable style={styles.modalBackdrop} onPress={() => setPickerMode(null)}>
          <Pressable style={styles.sheet} onPress={(event) => event.stopPropagation()}>
            {pickerMode === "client" ? (
              <>
                <Text style={styles.sheetTitle}>选择客户</Text>
                <ScrollView style={styles.sheetList}>
                  <TouchableOpacity style={styles.sheetRow} onPress={() => { clearStoredCurrentFocus(); setPickerMode(null); }}>
                    <Text style={styles.sheetRowTitle}>全部客户</Text>
                  </TouchableOpacity>
                  {clients.map((client) => (
                    <TouchableOpacity
                      key={client.id}
                      style={styles.sheetRow}
                      onPress={() => {
                        setManualClientFocus(client.id);
                        setPickerMode(null);
                      }}
                    >
                      <Text style={styles.sheetRowTitle}>{client.name}</Text>
                      {client.alias ? <Text style={styles.sheetRowMeta}>{client.alias}</Text> : null}
                    </TouchableOpacity>
                  ))}
                </ScrollView>
              </>
            ) : null}
            {pickerMode === "event_line" ? (
              <>
                <Text style={styles.sheetTitle}>选择事件线</Text>
                <ScrollView style={styles.sheetList}>
                  <TouchableOpacity
                    style={styles.sheetRow}
                    onPress={() => {
                      if (focus.clientId) {
                        setManualClientFocus(focus.clientId);
                      }
                      setPickerMode(null);
                    }}
                  >
                    <Text style={styles.sheetRowTitle}>仅锁客户</Text>
                  </TouchableOpacity>
                  {eventLineOptions.map((eventLine) => (
                    <TouchableOpacity
                      key={eventLine.id}
                      style={styles.sheetRow}
                      onPress={() => {
                        if (focus.clientId) {
                          setManualClientEventLineFocus(focus.clientId, eventLine.id);
                        }
                        setPickerMode(null);
                      }}
                    >
                      <Text style={styles.sheetRowTitle}>{eventLine.name}</Text>
                      <Text style={styles.sheetRowMeta}>{eventLine.stage || eventLine.status || "事件线"}</Text>
                    </TouchableOpacity>
                  ))}
                </ScrollView>
              </>
            ) : null}
            {pickerMode === "week" ? (
              <>
                <Text style={styles.sheetTitle}>切换当前周</Text>
                <ScrollView style={styles.sheetList}>
                  {generatedWeekOptions.map((item) => (
                    <TouchableOpacity
                      key={item.weekAnchorDate}
                      style={styles.sheetRow}
                      onPress={() => {
                        setCurrentFocusWeek(item.weekAnchorDate);
                        setPickerMode(null);
                      }}
                    >
                      <Text style={styles.sheetRowTitle}>{item.weekAnchorDate}</Text>
                      <Text style={styles.sheetRowMeta}>{item.weekLabel || formatWeekLabelCn(focus.weekLabel)}</Text>
                    </TouchableOpacity>
                  ))}
                </ScrollView>
              </>
            ) : null}
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    borderWidth: 1,
    borderColor: colors.borderLight,
    padding: spacing.md,
    gap: spacing.sm,
    ...shadow.softCard,
  },
  row: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  pill: {
    flex: 1,
    minHeight: 48,
    borderRadius: borderRadius.md,
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.borderLight,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  pillDisabled: {
    opacity: 0.5,
  },
  pillLabel: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    fontWeight: "700",
  },
  pillValue: {
    flex: 1,
    fontSize: fontSize.sm,
    color: colors.text,
    fontWeight: "700",
  },
  weekPill: {
    flex: 0.95,
    justifyContent: "center",
  },
  weekText: {
    fontSize: fontSize.sm,
    color: colors.brand,
    fontWeight: "800",
  },
  boundaryPill: {
    flex: 1.05,
    minHeight: 48,
    borderRadius: borderRadius.md,
    backgroundColor: colors.brandBg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderWidth: 1,
    borderColor: colors.brandRing,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  boundaryText: {
    flex: 1,
    fontSize: fontSize.sm,
    color: colors.text,
    fontWeight: "700",
  },
  actionRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  actionButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
    backgroundColor: colors.surfaceSecondary,
  },
  actionText: {
    fontSize: fontSize.xs,
    color: colors.brand,
    fontWeight: "700",
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(15,23,42,0.26)",
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: borderRadius.xl,
    borderTopRightRadius: borderRadius.xl,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.xxl,
    maxHeight: "72%",
  },
  sheetTitle: {
    fontSize: fontSize.xl,
    fontWeight: "800",
    color: colors.text,
    marginBottom: spacing.md,
  },
  sheetList: {
    flexGrow: 0,
  },
  sheetRow: {
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  sheetRowTitle: {
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: "700",
  },
  sheetRowMeta: {
    marginTop: 2,
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
});
~~~

## `mobile/components/RecordNote.tsx`

- 编码: `utf-8`

~~~tsx
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Alert,
  Animated,
  PermissionsAndroid,
  Platform,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import {
  AudioModule,
  RecordingPresets,
  setAudioModeAsync,
  useAudioRecorder,
  useAudioRecorderState,
} from "expo-audio";
import * as Haptics from "expo-haptics";
import { Mic, Pause, Play, Trash2, Check } from "lucide-react-native";
import { useAppChromeInsets } from "../lib/app-chrome";
import {
  attachRecordedAudioToTask,
  createQuickRecordTask,
  type RecordedUploadableFile,
} from "../lib/record-note-service";
import { colors } from "../lib/theme";
import type { TaskRecord } from "../lib/types";

// ─── Types ─────────────────────────────────

interface RecordNoteProps {
  readonly onClose: () => void;
  readonly taskContext?: TaskRecord | null;
  readonly autoStart?: boolean;
  readonly onUploaded?: (task: TaskRecord) => void;
}

function fileExtensionFromMimeType(mimeType: string): string {
  if (mimeType.includes("ogg")) return "ogg";
  if (mimeType.includes("aac") || mimeType.includes("mp4") || mimeType.includes("m4a")) return "m4a";
  if (mimeType.includes("mpeg")) return "mp3";
  return "webm";
}

function extractApiErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

// ─── Component ──────────────────────────────

export default function RecordNote({
  onClose,
  taskContext = null,
  autoStart = false,
  onUploaded,
}: RecordNoteProps) {
  const chrome = useAppChromeInsets();
  const isTaskMode = Boolean(taskContext);

  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [isUploading, setIsUploading] = useState(false);

  const nativeRecorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const nativeRecorderState = useAudioRecorderState(nativeRecorder, 250);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const webRecorderRef = useRef<any>(null);
  const webStreamRef = useRef<any>(null);
  const webChunksRef = useRef<BlobPart[]>([]);
  const autoStartedRef = useRef(false);
  const slideAnim = useRef(new Animated.Value(300)).current;

  // Slide-in animation
  useEffect(() => {
    Animated.spring(slideAnim, {
      toValue: 0, useNativeDriver: true, speed: 14, bounciness: 4,
    }).start();
  }, [slideAnim]);

  // Format time
  const formatTime = (secs: number) => {
    const m = String(Math.floor(secs / 60)).padStart(2, "0");
    const s = String(secs % 60).padStart(2, "0");
    return `${m}:${s}`;
  };

  // Timer for web
  useEffect(() => {
    if (Platform.OS === "web" && isRecording && !isPaused) {
      timerRef.current = setInterval(() => setRecordingSeconds((s) => s + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isRecording, isPaused]);

  // Sync native recorder state
  useEffect(() => {
    if (Platform.OS === "web") return;
    setIsRecording(nativeRecorderState.isRecording);
    setRecordingSeconds(Math.max(0, Math.floor(nativeRecorderState.durationMillis / 1000)));
  }, [nativeRecorderState.durationMillis, nativeRecorderState.isRecording]);

  const stopWebTracks = useCallback(() => {
    const stream = webStreamRef.current;
    if (stream && typeof stream.getTracks === "function") {
      for (const track of stream.getTracks()) track.stop();
    }
    webStreamRef.current = null;
  }, []);

  const resetNativeAudioMode = useCallback(async () => {
    if (Platform.OS === "web") return;
    try {
      await setAudioModeAsync({
        playsInSilentMode: true,
        allowsRecording: false,
        shouldRouteThroughEarpiece: false,
        shouldPlayInBackground: false,
        allowsBackgroundRecording: false,
        interruptionMode: "mixWithOthers",
      });
    } catch {}
  }, []);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      stopWebTracks();
      void resetNativeAudioMode();
    };
  }, [resetNativeAudioMode, stopWebTracks]);

  // ─── Start recording ──────────────────────

  const startRecording = useCallback(async () => {
    if (isRecording || isUploading) return;
    try {
      if (Platform.OS === "web") {
        const mediaDevices = (globalThis as any).navigator?.mediaDevices;
        const MediaRecorderCtor = (globalThis as any).MediaRecorder;
        if (!mediaDevices?.getUserMedia || !MediaRecorderCtor) {
          throw new Error("当前浏览器不支持录音，请用手机真机测试。");
        }
        const stream = await mediaDevices.getUserMedia({ audio: true });
        const recorder = new MediaRecorderCtor(stream);
        webChunksRef.current = [];
        recorder.ondataavailable = (event: any) => {
          if (event.data?.size > 0) webChunksRef.current.push(event.data);
        };
        recorder.start();
        webStreamRef.current = stream;
        webRecorderRef.current = recorder;
        setIsRecording(true);
        setIsPaused(false);
        setRecordingSeconds(0);
      } else {
        const permission = await AudioModule.requestRecordingPermissionsAsync();
        if (!permission.granted) throw new Error("请先允许麦克风权限。");

        if (Platform.OS === "android") {
          const sdkInt = typeof Platform.Version === "number" ? Platform.Version : Number(Platform.Version);
          if (Number.isFinite(sdkInt) && sdkInt >= 33) {
            await PermissionsAndroid.request(PermissionsAndroid.PERMISSIONS.POST_NOTIFICATIONS);
          }
        }

        await setAudioModeAsync({
          playsInSilentMode: true,
          allowsRecording: true,
          shouldRouteThroughEarpiece: false,
          shouldPlayInBackground: true,
          allowsBackgroundRecording: true,
          interruptionMode: "doNotMix",
        });
        await nativeRecorder.prepareToRecordAsync(RecordingPresets.HIGH_QUALITY);
        nativeRecorder.record();
        setIsPaused(false);
      }
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    } catch (error) {
      const message = error instanceof Error ? error.message : "无法开始录音";
      setIsRecording(false);
      Alert.alert("录音失败", message);
    }
  }, [isRecording, isUploading, nativeRecorder]);

  // Always auto-start recording when the panel mounts.
  // The panel's sole purpose is to record, so we start immediately.
  useEffect(() => {
    if (autoStartedRef.current) return;
    autoStartedRef.current = true;
    void startRecording();
  }, [startRecording]);

  // ─── Pause / Resume ──────────────────────

  const pauseRecording = useCallback(() => {
    setIsPaused(true);
    if (Platform.OS === "web" && webRecorderRef.current?.state === "recording") {
      webRecorderRef.current.pause();
    } else if (Platform.OS !== "web") {
      nativeRecorder.pause();
    }
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
  }, [nativeRecorder]);

  const resumeRecording = useCallback(() => {
    setIsPaused(false);
    if (Platform.OS === "web" && webRecorderRef.current?.state === "paused") {
      webRecorderRef.current.resume();
    } else if (Platform.OS !== "web") {
      nativeRecorder.record();
    }
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
  }, [nativeRecorder]);

  // ─── Cancel ──────────────────────────────

  const cancelRecording = useCallback(async () => {
    if (timerRef.current) clearInterval(timerRef.current);
    setIsRecording(false);
    setIsPaused(false);
    setRecordingSeconds(0);
    try {
      if (Platform.OS === "web" && webRecorderRef.current?.state !== "inactive") {
        webRecorderRef.current.stop();
        webRecorderRef.current = null;
        webChunksRef.current = [];
      }
      if (Platform.OS !== "web" && nativeRecorderState.isRecording) {
        await nativeRecorder.stop();
      }
    } catch {}
    await resetNativeAudioMode();
    stopWebTracks();
    onClose();
  }, [nativeRecorder, nativeRecorderState.isRecording, onClose, resetNativeAudioMode, stopWebTracks]);

  // ─── Finish and upload ────────────────────

  const finishRecording = useCallback(async () => {
    const duration = recordingSeconds;
    setIsRecording(false);
    setIsPaused(false);
    if (timerRef.current) clearInterval(timerRef.current);

    let uploadFile: RecordedUploadableFile | null = null;
    try {
      if (Platform.OS === "web" && webRecorderRef.current) {
        const recorder = webRecorderRef.current;
        const file = await new Promise<File>((resolve, reject) => {
          recorder.onerror = () => reject(new Error("浏览器录音失败"));
          recorder.onstop = () => {
            const mimeType = recorder.mimeType || "audio/webm";
            const blob = new Blob(webChunksRef.current, { type: mimeType });
            resolve(new File([blob], `recording-${Date.now()}.${fileExtensionFromMimeType(mimeType)}`, { type: mimeType }));
          };
          recorder.stop();
        });
        stopWebTracks();
        webRecorderRef.current = null;
        webChunksRef.current = [];
        uploadFile = file;
      } else {
        if (nativeRecorderState.isRecording) await nativeRecorder.stop();
        const uri = nativeRecorder.uri ?? nativeRecorderState.url;
        await resetNativeAudioMode();
        if (uri) {
          const ext = (uri.split("?")[0].split(".").pop() || "m4a").toLowerCase();
          uploadFile = { uri, name: `recording-${Date.now()}.${ext}`, type: `audio/${ext === "caf" ? "x-caf" : ext}` };
        }
      }

      if (!uploadFile) throw new Error("录音文件生成失败");

      if (isTaskMode && taskContext) {
        setIsUploading(true);
        const result = await attachRecordedAudioToTask(taskContext, {
          file: uploadFile,
          title: `${taskContext.title} 录音 ${formatTime(duration)}`,
          durationSeconds: duration,
        });
        if (result.status === "needs_attention") {
          await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
          Alert.alert("录音需处理", result.message);
        } else if (result.status === "pending_attachment") {
          Alert.alert("录音待挂接", result.message);
          await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        } else {
          await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        }
        onUploaded?.(result.task);
        onClose();
        return;
      }

      // Inbox mode: create task first, then attach when the task already has a remote id.
      setIsUploading(true);
      const createdTask = await createQuickRecordTask(
        `速记录音 ${formatTime(duration)}`,
        `手机速记录音，时长 ${formatTime(duration)}`,
      );
      const result = await attachRecordedAudioToTask(createdTask, {
        file: uploadFile,
        title: `速记录音 ${formatTime(duration)}`,
        durationSeconds: duration,
      });
      if (result.status === "needs_attention") {
        await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
        Alert.alert("录音需处理", result.message);
      } else if (result.status === "pending_attachment") {
        Alert.alert("录音待挂接", result.message);
        await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      } else {
        await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      }
      onUploaded?.(result.task);
      onClose();
    } catch (error) {
      const message = error instanceof Error ? error.message : "录音上传失败";
      Alert.alert("上传失败", message);
    } finally {
      setIsUploading(false);
      setRecordingSeconds(0);
      await resetNativeAudioMode();
      stopWebTracks();
    }
  }, [isTaskMode, nativeRecorder, nativeRecorderState.isRecording, nativeRecorderState.url, onClose, onUploaded, recordingSeconds, resetNativeAudioMode, stopWebTracks, taskContext]);

  return (
    <View style={s.overlay}>
      {/* Backdrop */}
      <TouchableOpacity style={s.backdrop} activeOpacity={1} onPress={cancelRecording} />

      {/* Bottom sheet */}
      <Animated.View style={[s.sheet, { transform: [{ translateY: slideAnim }], paddingBottom: chrome.overlayBottomPadding + 16 }]}>
        <View style={s.handle} />

        {/* Timer */}
        <Text style={s.timer}>{formatTime(recordingSeconds)}</Text>

        {/* Status */}
        <View style={s.statusRow}>
          <View style={[s.statusDot, isPaused ? s.statusDotPaused : isRecording ? s.statusDotRecording : s.statusDotPaused]} />
          <Text style={s.statusText}>
            {isUploading ? "上传中..." : isPaused ? "已暂停" : isRecording ? "录音中，可锁屏继续" : "准备录音..."}
          </Text>
        </View>

        {/* Controls */}
        <View style={s.controls}>
          {/* Cancel */}
          <TouchableOpacity style={s.cancelBtn} onPress={cancelRecording} disabled={isUploading}>
            <Trash2 size={22} strokeWidth={1.5} color="#6B7280" />
          </TouchableOpacity>

          {/* Pause / Resume */}
          <TouchableOpacity
            style={[s.mainBtn, isPaused ? s.mainBtnPaused : s.mainBtnRecording]}
            onPress={isPaused ? resumeRecording : pauseRecording}
            disabled={isUploading}
          >
            {isPaused ? (
              <Play size={32} strokeWidth={1.5} color="#FFFFFF" style={{ marginLeft: 3 }} />
            ) : (
              <Pause size={32} strokeWidth={1.5} color="#EF4444" />
            )}
          </TouchableOpacity>

          {/* Finish */}
          <TouchableOpacity style={s.finishBtn} onPress={finishRecording} disabled={isUploading}>
            <Check size={26} strokeWidth={2} color="#FFFFFF" />
          </TouchableOpacity>
        </View>
      </Animated.View>
    </View>
  );
}

// ─── Styles ─────────────────────────────────

const s = StyleSheet.create({
  overlay: {
    position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
    zIndex: 55, justifyContent: "flex-end",
  },
  backdrop: {
    position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: "rgba(0,0,0,0.2)",
  },
  sheet: {
    backgroundColor: "#FFFFFF",
    borderTopLeftRadius: 32, borderTopRightRadius: 32,
    paddingTop: 12, paddingHorizontal: 24,
    shadowColor: "#000", shadowOffset: { width: 0, height: -10 },
    shadowOpacity: 0.12, shadowRadius: 40, elevation: 20,
    alignItems: "center",
  },
  handle: {
    width: 48, height: 6, borderRadius: 3,
    backgroundColor: "#E5E7EB", marginBottom: 32,
  },

  timer: {
    fontSize: 56, fontFamily: "monospace", fontWeight: "300",
    color: "#1F2937", letterSpacing: -1, marginBottom: 8,
  },

  statusRow: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 40 },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  statusDotRecording: { backgroundColor: "#EF4444" },
  statusDotPaused: { backgroundColor: "#F97316" },
  statusText: { fontSize: 14, fontWeight: "500", color: "#6B7280", letterSpacing: 0.3 },

  controls: {
    flexDirection: "row", alignItems: "center", justifyContent: "center",
    gap: 32, width: "100%", paddingHorizontal: 16,
  },
  cancelBtn: {
    width: 50, height: 50, borderRadius: 25,
    backgroundColor: "#F3F4F6", alignItems: "center", justifyContent: "center",
  },
  mainBtn: {
    width: 72, height: 72, borderRadius: 36,
    alignItems: "center", justifyContent: "center",
  },
  mainBtnRecording: {
    backgroundColor: "#FEF2F2", borderWidth: 2, borderColor: "#FECACA",
  },
  mainBtnPaused: {
    backgroundColor: "#1F2937",
  },
  finishBtn: {
    width: 50, height: 50, borderRadius: 25,
    backgroundColor: "#2563EB", alignItems: "center", justifyContent: "center",
    shadowColor: "#2563EB", shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3, shadowRadius: 8, elevation: 4,
  },
});
~~~

## `mobile/components/SettingsAI.tsx`

- 编码: `utf-8`

~~~tsx
import { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Switch,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { ArrowLeft, ChevronRight, AlignJustify, FileText, Volume2 } from "lucide-react-native";
import { useAppChromeInsets } from "../lib/app-chrome";
import { colors, spacing, fontSize, borderRadius, shadow } from "../lib/theme";

interface SettingsAIProps {
  readonly onClose: () => void;
}

type SummaryTemplate = "concise" | "detailed";

export default function SettingsAI({ onClose }: SettingsAIProps) {
  const chrome = useAppChromeInsets();
  const [summaryTemplate, setSummaryTemplate] =
    useState<SummaryTemplate>("concise");
  const [saveHighQuality, setSaveHighQuality] = useState(false);

  return (
    <SafeAreaView style={styles.container} edges={["left", "right"]}>
      <View style={[styles.header, { paddingTop: chrome.headerTopPadding }]}>
        <TouchableOpacity onPress={onClose} style={styles.backButton}>
          <ArrowLeft size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>AI 助手与录音</Text>
        <View style={styles.headerSpacer} />
      </View>

      <View style={[styles.content, { paddingBottom: chrome.screenBottomPadding }]}>
        {/* Section: AI 总结偏好 */}
        <Text style={styles.sectionTitle}>AI 总结偏好</Text>
        <View style={[styles.card, shadow.card]}>
          <Text style={styles.cardLabel}>会议录音总结模板</Text>

          <TouchableOpacity
            style={[
              styles.radioCard,
              summaryTemplate === "concise" && styles.radioCardSelected,
            ]}
            onPress={() => setSummaryTemplate("concise")}
          >
            <View style={styles.radioRow}>
              <View style={{ marginRight: spacing.md }}><AlignJustify size={18} color={colors.textSecondary} /></View>
              <View style={styles.radioTextContainer}>
                <Text style={styles.radioTitle}>简练行动项 (推荐)</Text>
                <Text style={styles.radioSubtitle}>
                  核心结论 + 下一步待办
                </Text>
              </View>
              <View
                style={[
                  styles.radioDot,
                  summaryTemplate === "concise" && styles.radioDotSelected,
                ]}
              >
                {summaryTemplate === "concise" && (
                  <View style={styles.radioDotInner} />
                )}
              </View>
            </View>
          </TouchableOpacity>

          <TouchableOpacity
            style={[
              styles.radioCard,
              summaryTemplate === "detailed" && styles.radioCardSelected,
            ]}
            onPress={() => setSummaryTemplate("detailed")}
          >
            <View style={styles.radioRow}>
              <View style={{ marginRight: spacing.md }}><FileText size={18} color={colors.textSecondary} /></View>
              <View style={styles.radioTextContainer}>
                <Text style={styles.radioTitle}>详细会议纪要</Text>
                <Text style={styles.radioSubtitle}>
                  发言人区分 + 完整上下文
                </Text>
              </View>
              <View
                style={[
                  styles.radioDot,
                  summaryTemplate === "detailed" && styles.radioDotSelected,
                ]}
              >
                {summaryTemplate === "detailed" && (
                  <View style={styles.radioDotInner} />
                )}
              </View>
            </View>
          </TouchableOpacity>
        </View>

        {/* Section: 语音与转写 */}
        <Text style={styles.sectionTitle}>语音与转写</Text>
        <View style={[styles.card, shadow.card]}>
          <TouchableOpacity style={styles.row}>
            <View style={styles.rowLeft}>
              <View style={{ marginRight: spacing.md }}><Volume2 size={18} color={colors.textSecondary} /></View>
              <View style={styles.rowTextContainer}>
                <Text style={styles.rowTitle}>转写语言</Text>
              </View>
            </View>
            <View style={styles.rowRight}>
              <Text style={styles.rowValue}>中英混合 (自动检测)</Text>
              <ChevronRight size={22} color={colors.textTertiary} />
            </View>
          </TouchableOpacity>

          <View style={styles.separator} />

          <View style={styles.row}>
            <View style={styles.rowTextContainer}>
              <Text style={styles.rowTitle}>录音保存高清原文件</Text>
              <Text style={styles.rowSubtitle}>关闭可节省云端空间</Text>
            </View>
            <Switch
              value={saveHighQuality}
              onValueChange={setSaveHighQuality}
              trackColor={{ false: colors.border, true: colors.brandLight }}
              thumbColor={colors.surface}
            />
          </View>

          <View style={styles.separator} />

          <TouchableOpacity style={styles.row}>
            <View style={styles.rowTextContainer}>
              <Text style={styles.rowTitle}>默认归档位置</Text>
              <Text style={styles.rowSubtitle}>
                未关联客户时，存入草稿箱
              </Text>
            </View>
            <ChevronRight size={22} color={colors.textTertiary} />
          </TouchableOpacity>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    backgroundColor: colors.surface,
    borderBottomWidth: 0.5,
    borderBottomColor: colors.borderLight,
  },
  backButton: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
  },
  backIcon: {
    fontSize: 22,
    color: colors.text,
  },
  headerTitle: {
    flex: 1,
    textAlign: "center",
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.text,
  },
  headerSpacer: {
    width: 36,
  },
  content: {
    flex: 1,
    padding: spacing.lg,
  },
  sectionTitle: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.textSecondary,
    marginBottom: spacing.sm,
    marginTop: spacing.lg,
    marginLeft: spacing.xs,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
  },
  cardLabel: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.text,
    marginBottom: spacing.md,
  },
  radioCard: {
    borderWidth: 1.5,
    borderColor: colors.border,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  radioCardSelected: {
    borderColor: colors.brand,
    backgroundColor: colors.brandBg,
  },
  radioRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  radioIcon: {
    fontSize: 18,
    marginRight: spacing.md,
  },
  radioTextContainer: {
    flex: 1,
  },
  radioTitle: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.text,
  },
  radioSubtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  radioDot: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 2,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  radioDotSelected: {
    borderColor: colors.brand,
  },
  radioDotInner: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: colors.brand,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
  },
  rowLeft: {
    flexDirection: "row",
    alignItems: "center",
    flex: 1,
  },
  rowIcon: {
    fontSize: 18,
    marginRight: spacing.md,
  },
  rowTextContainer: {
    flex: 1,
    marginRight: spacing.md,
  },
  rowTitle: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.text,
  },
  rowSubtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  rowRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  rowValue: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  chevron: {
    fontSize: 22,
    color: colors.textTertiary,
  },
  separator: {
    height: 0.5,
    backgroundColor: colors.borderLight,
    marginVertical: spacing.xs,
  },
});
~~~

## `mobile/components/SettingsAccount.tsx`

- 编码: `utf-8`

~~~tsx
import { useEffect, useState } from "react";
import {
  Alert,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { ArrowLeft, RotateCcw, Save } from "lucide-react-native";
import { useAppChromeInsets } from "../lib/app-chrome";
import * as api from "../lib/api";
import { isValidBaseUrl } from "../lib/base-url";
import { colors, spacing, fontSize, borderRadius, shadow } from "../lib/theme";
import type { SessionUser } from "../lib/types";

interface SettingsAccountProps {
  readonly onClose: () => void;
  readonly user: SessionUser | null;
}

export default function SettingsAccount({ onClose, user }: SettingsAccountProps) {
  const chrome = useAppChromeInsets();
  const [serverUrl, setServerUrl] = useState(api.getBaseUrl());
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setServerUrl(api.getBaseUrl());
  }, []);

  const handleSave = async () => {
    const nextUrl = serverUrl.trim();
    if (!isValidBaseUrl(nextUrl)) {
      Alert.alert("地址无效", `请输入完整的服务器地址，例如 ${api.DEFAULT_BASE_URL}`);
      return;
    }
    setSaving(true);
    try {
      await api.setAndSaveBaseUrl(nextUrl);
      Alert.alert("已保存", "服务器地址已更新，新请求会使用新地址。");
    } catch {
      Alert.alert("保存失败", "服务器地址保存失败，请稍后重试。");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setServerUrl(api.DEFAULT_BASE_URL);
  };

  return (
    <SafeAreaView style={styles.container} edges={["left", "right"]}>
      <View style={[styles.header, { paddingTop: chrome.headerTopPadding }]}>
        <TouchableOpacity onPress={onClose} style={styles.backButton}>
          <ArrowLeft size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>账号设置</Text>
        <View style={styles.headerSpacer} />
      </View>

      <View style={[styles.content, { paddingBottom: chrome.screenBottomPadding }]}>
        <Text style={styles.sectionTitle}>当前账号</Text>
        <View style={[styles.card, shadow.card]}>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>姓名</Text>
            <Text style={styles.infoValue}>{user?.fullName ?? "未登录"}</Text>
          </View>
          <View style={styles.separator} />
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>邮箱</Text>
            <Text style={styles.infoValue}>{user?.email ?? "-"}</Text>
          </View>
        </View>

        <Text style={styles.sectionTitle}>服务器</Text>
        <View style={[styles.card, shadow.card]}>
          <Text style={styles.fieldLabel}>API 地址</Text>
          <TextInput
            style={styles.input}
            value={serverUrl}
            onChangeText={setServerUrl}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="url"
            placeholder={api.DEFAULT_BASE_URL}
            placeholderTextColor={colors.textTertiary}
          />
          <Text style={styles.helperText}>
            默认使用云端协作地址，也支持局域网地址或自定义部署地址。
          </Text>

          <View style={styles.actions}>
            <TouchableOpacity style={styles.secondaryButton} onPress={handleReset}>
              <RotateCcw size={16} color={colors.textSecondary} />
              <Text style={styles.secondaryButtonText}>恢复默认</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.primaryButton, saving && styles.primaryButtonDisabled]}
              onPress={handleSave}
              disabled={saving}
            >
              <Save size={16} color={colors.textOnBrand} />
              <Text style={styles.primaryButtonText}>{saving ? "保存中..." : "保存地址"}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    backgroundColor: colors.surface,
    borderBottomWidth: 0.5,
    borderBottomColor: colors.borderLight,
  },
  backButton: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: {
    flex: 1,
    textAlign: "center",
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.text,
  },
  headerSpacer: {
    width: 36,
  },
  content: {
    flex: 1,
    padding: spacing.lg,
  },
  sectionTitle: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.textSecondary,
    marginBottom: spacing.sm,
    marginTop: spacing.lg,
    marginLeft: spacing.xs,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
  },
  infoRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.sm,
    gap: spacing.md,
  },
  infoLabel: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  infoValue: {
    flex: 1,
    textAlign: "right",
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.text,
  },
  separator: {
    height: 0.5,
    backgroundColor: colors.borderLight,
    marginVertical: spacing.xs,
  },
  fieldLabel: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.text,
    marginBottom: spacing.sm,
  },
  input: {
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    fontSize: fontSize.md,
    color: colors.text,
  },
  helperText: {
    fontSize: fontSize.xs,
    lineHeight: 18,
    color: colors.textTertiary,
    marginTop: spacing.sm,
  },
  actions: {
    flexDirection: "row",
    gap: spacing.sm,
    marginTop: spacing.lg,
  },
  secondaryButton: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    backgroundColor: colors.surface,
  },
  secondaryButtonText: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.textSecondary,
  },
  primaryButton: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    backgroundColor: colors.brand,
  },
  primaryButtonDisabled: {
    opacity: 0.6,
  },
  primaryButtonText: {
    fontSize: fontSize.sm,
    fontWeight: "700",
    color: colors.textOnBrand,
  },
});
~~~

