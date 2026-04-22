"""
飞书同步引擎 (Feishu Sync Engine)
==================================
基于现有 feishu.py 的认证基础，扩展四大同步模块：
1. 妙记 → 会议纪要
2. 任务双向同步
3. 日历联动
4. 增强消息卡片

所有函数遵循现有 feishu.py 的风格：
- 使用 httpx 同步客户端
- 统一错误处理 (_raise_for_feishu_error)
- tenant_access_token 由调用方传入
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import httpx

from app.services.feishu import (
    FeishuApiError,
    FeishuReceiveIdType,
    _OPEN_FEISHU_BASE_URL,
    _parse_response_json,
    _raise_for_feishu_error,
)

_TIMEOUT = httpx.Timeout(20.0, connect=5.0)


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _api_get(token: str, path: str, params: dict | None = None) -> dict:
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.get(f"{_OPEN_FEISHU_BASE_URL}{path}", headers=_auth_headers(token), params=params)
    payload = _parse_response_json(resp)
    _raise_for_feishu_error(payload, f"飞书 GET {path} 失败")
    return payload


def _api_post(token: str, path: str, body: dict | None = None, params: dict | None = None) -> dict:
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(f"{_OPEN_FEISHU_BASE_URL}{path}", headers=_auth_headers(token), json=body or {}, params=params)
    payload = _parse_response_json(resp)
    _raise_for_feishu_error(payload, f"飞书 POST {path} 失败")
    return payload


def _api_patch(token: str, path: str, body: dict | None = None, params: dict | None = None) -> dict:
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.patch(f"{_OPEN_FEISHU_BASE_URL}{path}", headers=_auth_headers(token), json=body or {}, params=params)
    payload = _parse_response_json(resp)
    _raise_for_feishu_error(payload, f"飞书 PATCH {path} 失败")
    return payload


def _api_delete(token: str, path: str) -> dict:
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.delete(f"{_OPEN_FEISHU_BASE_URL}{path}", headers=_auth_headers(token))
    payload = _parse_response_json(resp)
    _raise_for_feishu_error(payload, f"飞书 DELETE {path} 失败")
    return payload


# =====================================================================
# 1. 妙记 (Minutes) → 会议纪要
# =====================================================================

def list_minutes(
    *,
    user_access_token: str,
    start_time: int | None = None,
    end_time: int | None = None,
    page_size: int = 20,
    page_token: str = "",
) -> dict:
    """获取用户的妙记列表
    注意: 妙记 API 需要 user_access_token (用户身份)
    """
    params: dict[str, Any] = {"page_size": page_size}
    if start_time:
        params["start_time"] = str(start_time)
    if end_time:
        params["end_time"] = str(end_time)
    if page_token:
        params["page_token"] = page_token
    return _api_get(user_access_token, "/minutes/v1/minutes", params)


def get_minute_detail(
    *,
    user_access_token: str,
    minute_token: str,
) -> dict:
    """获取妙记详情（元信息 + 统计）"""
    return _api_get(user_access_token, f"/minutes/v1/minutes/{minute_token}")


def get_minute_transcript(
    *,
    user_access_token: str,
    minute_token: str,
) -> list[dict]:
    """获取妙记转写全文（按发言段落）"""
    all_paragraphs: list[dict] = []
    page_token = ""
    for _ in range(50):  # 安全上限
        params: dict[str, Any] = {"page_size": 100}
        if page_token:
            params["page_token"] = page_token
        payload = _api_get(user_access_token, f"/minutes/v1/minutes/{minute_token}/transcripts", params)
        data = payload.get("data", {})
        paragraphs = data.get("paragraphs") or data.get("items") or []
        all_paragraphs.extend(paragraphs)
        page_token = str(data.get("page_token") or "")
        if not data.get("has_more") or not page_token:
            break
    return all_paragraphs


def parse_minute_to_meeting_notes(detail: dict, paragraphs: list[dict]) -> dict:
    """将飞书妙记数据解析为益语会议纪要格式"""
    data = detail.get("data", {}) if "data" in detail else detail
    minute = data.get("minute", data)

    title = str(minute.get("title") or "飞书妙记")
    create_time = int(minute.get("create_time") or 0)
    duration = int(minute.get("duration") or 0)

    # 拼接转写文本
    transcript_lines: list[str] = []
    speakers: set[str] = set()
    for para in paragraphs:
        speaker = str(para.get("speaker", {}).get("user_name", "") if isinstance(para.get("speaker"), dict) else "")
        text = str(para.get("text") or para.get("content") or "")
        if speaker:
            speakers.add(speaker)
            transcript_lines.append(f"【{speaker}】{text}")
        elif text:
            transcript_lines.append(text)

    full_transcript = "\n".join(transcript_lines)

    # 提取 AI 摘要（如果有）
    ai_summary = str(minute.get("ai_summary") or minute.get("summary") or "")
    ai_todo_items = minute.get("todo_items") or minute.get("action_items") or []

    return {
        "title": title,
        "source": "feishu_minutes",
        "transcript": full_transcript,
        "speakers": list(speakers),
        "aiSummary": ai_summary,
        "aiTodoItems": [
            {
                "content": str(item.get("content") or item.get("text") or ""),
                "owner": str(item.get("user_name") or item.get("owner") or ""),
            }
            for item in ai_todo_items
            if isinstance(item, dict)
        ],
        "durationSeconds": duration,
        "feishuCreateTime": datetime.fromtimestamp(create_time, tz=timezone.utc).isoformat() if create_time else None,
        "minuteToken": str(minute.get("token") or ""),
    }


# =====================================================================
# 2. 任务 (Task v2) 双向同步
# =====================================================================

def list_tasks(
    *,
    tenant_access_token: str,
    page_size: int = 50,
    page_token: str = "",
    completed: bool | None = None,
) -> dict:
    """获取任务列表"""
    params: dict[str, Any] = {"page_size": page_size}
    if page_token:
        params["page_token"] = page_token
    if completed is not None:
        params["completed"] = str(completed).lower()
    return _api_get(tenant_access_token, "/task/v2/tasks", params)


def get_task(*, tenant_access_token: str, task_guid: str) -> dict:
    """获取单个任务详情"""
    return _api_get(tenant_access_token, f"/task/v2/tasks/{task_guid}")


def create_task(
    *,
    tenant_access_token: str,
    summary: str,
    description: str = "",
    due_timestamp: int | None = None,
    members: list[dict] | None = None,
    origin_href: str = "",
    origin_title: str = "益语智库",
) -> dict:
    """在飞书创建任务"""
    body: dict[str, Any] = {
        "summary": summary,
        "description": description,
        "origin": {
            "platform_i18n_name": {"zh_cn": origin_title},
        },
    }
    if origin_href:
        body["origin"]["href"] = {"url": origin_href}
    if due_timestamp:
        body["due"] = {"timestamp": str(due_timestamp), "is_all_day": False}
    if members:
        body["members"] = members
    return _api_post(tenant_access_token, "/task/v2/tasks", body)


def update_task(
    *,
    tenant_access_token: str,
    task_guid: str,
    summary: str | None = None,
    description: str | None = None,
    due_timestamp: int | None = None,
    completed_at: str | None = None,
) -> dict:
    """更新飞书任务"""
    body: dict[str, Any] = {}
    update_fields: list[str] = []
    if summary is not None:
        body["summary"] = summary
        update_fields.append("summary")
    if description is not None:
        body["description"] = description
        update_fields.append("description")
    if due_timestamp is not None:
        body["due"] = {"timestamp": str(due_timestamp), "is_all_day": False}
        update_fields.append("due")
    if completed_at is not None:
        body["completed_at"] = completed_at
        update_fields.append("completed_at")
    params = {"update_fields": ",".join(update_fields)} if update_fields else None
    return _api_patch(tenant_access_token, f"/task/v2/tasks/{task_guid}", body, params)


def complete_task(*, tenant_access_token: str, task_guid: str) -> dict:
    """完成飞书任务"""
    return _api_post(tenant_access_token, f"/task/v2/tasks/{task_guid}/complete")


def uncomplete_task(*, tenant_access_token: str, task_guid: str) -> dict:
    """恢复飞书任务为未完成"""
    return _api_post(tenant_access_token, f"/task/v2/tasks/{task_guid}/uncomplete")


# =====================================================================
# 3. 日历 (Calendar v4)
# =====================================================================

def get_primary_calendar(*, tenant_access_token: str) -> dict:
    """获取主日历"""
    return _api_get(tenant_access_token, "/calendar/v4/calendars/primary")


def list_calendar_events(
    *,
    tenant_access_token: str,
    calendar_id: str = "primary",
    start_time: str | None = None,
    end_time: str | None = None,
    page_size: int = 50,
    page_token: str = "",
) -> dict:
    """获取日历事件列表"""
    params: dict[str, Any] = {"page_size": page_size}
    if start_time:
        params["start_time"] = start_time
    if end_time:
        params["end_time"] = end_time
    if page_token:
        params["page_token"] = page_token
    return _api_get(tenant_access_token, f"/calendar/v4/calendars/{calendar_id}/events", params)


def create_calendar_event(
    *,
    tenant_access_token: str,
    calendar_id: str = "primary",
    summary: str,
    description: str = "",
    start_time: str = "",
    end_time: str = "",
    attendees: list[dict] | None = None,
) -> dict:
    """创建日历事件"""
    body: dict[str, Any] = {
        "summary": summary,
        "description": description,
        "start_time": {"timestamp": start_time} if start_time else {},
        "end_time": {"timestamp": end_time} if end_time else {},
    }
    if attendees:
        body["attendees"] = attendees
    return _api_post(tenant_access_token, f"/calendar/v4/calendars/{calendar_id}/events", body)


def get_freebusy(
    *,
    tenant_access_token: str,
    user_ids: list[str],
    start_time: str,
    end_time: str,
) -> dict:
    """查询用户忙闲状态"""
    body = {
        "time_min": start_time,
        "time_max": end_time,
        "user_ids": user_ids,
    }
    return _api_post(tenant_access_token, "/calendar/v4/freebusy/list", body)


# =====================================================================
# 4. 增强消息 (Rich Messages)
# =====================================================================

def send_interactive_card(
    *,
    tenant_access_token: str,
    receive_id_type: FeishuReceiveIdType,
    receive_id: str,
    card: dict,
) -> dict:
    """发送交互式卡片消息"""
    content = json.dumps(card, ensure_ascii=False)
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(
            f"{_OPEN_FEISHU_BASE_URL}/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            headers=_auth_headers(tenant_access_token),
            json={
                "receive_id": receive_id,
                "msg_type": "interactive",
                "content": content,
            },
        )
    payload = _parse_response_json(resp)
    _raise_for_feishu_error(payload, "飞书卡片消息发送失败")
    return payload


def build_weekly_review_card(
    *,
    week_label: str,
    headline: str,
    highlights: list[str],
    blockers: list[str],
    next_focus: str,
) -> dict:
    """构建周复盘摘要卡片"""
    elements: list[dict] = []

    # 标题
    elements.append({
        "tag": "markdown",
        "content": f"**{headline}**",
    })

    # 亮点
    if highlights:
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "markdown",
            "content": "**本周亮点**\n" + "\n".join(f"• {h}" for h in highlights[:5]),
        })

    # 卡点
    if blockers:
        elements.append({
            "tag": "markdown",
            "content": "**卡点关注**\n" + "\n".join(f"⚠️ {b}" for b in blockers[:3]),
        })

    # 下周重点
    if next_focus:
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "markdown",
            "content": f"**下周重点：** {next_focus}",
        })

    return {
        "header": {
            "template": "blue",
            "title": {"tag": "plain_text", "content": f"📋 {week_label} 周复盘"},
        },
        "elements": elements,
    }


def build_badge_unlock_card(
    *,
    badge_name: str,
    badge_description: str,
    category_name: str,
    xp: int,
    user_name: str,
) -> dict:
    """构建徽章点亮通知卡片"""
    return {
        "header": {
            "template": "turquoise",
            "title": {"tag": "plain_text", "content": f"🏅 {user_name} 点亮了新徽章"},
        },
        "elements": [
            {
                "tag": "markdown",
                "content": f"**{badge_name}** ({category_name})\n{badge_description}\n\n获得 **+{xp} XP**",
            },
        ],
    }


def build_task_overdue_card(
    *,
    tasks: list[dict],
    user_name: str,
) -> dict:
    """构建任务逾期提醒卡片"""
    lines = []
    for t in tasks[:5]:
        lines.append(f"• **{t.get('title', '未命名')}** — 截止 {t.get('ddl', '未设定')}")
    return {
        "header": {
            "template": "red",
            "title": {"tag": "plain_text", "content": f"⏰ 逾期提醒｜{len(tasks)} 项"},
        },
        "elements": [
            {
                "tag": "markdown",
                "content": "\n".join(lines),
            },
            {
                "tag": "markdown",
                "content": "请回到益语智库处理或调整截止时间。",
            },
        ],
    }


# =====================================================================
# 5. 通讯录 (Contact v3) — 组织架构
# =====================================================================

def get_department_children(
    *,
    tenant_access_token: str,
    department_id: str = "0",
    page_size: int = 50,
    page_token: str = "",
) -> dict:
    """获取子部门列表 (department_id=0 为根部门)"""
    params: dict[str, Any] = {"department_id": department_id, "page_size": page_size}
    if page_token:
        params["page_token"] = page_token
    return _api_get(tenant_access_token, "/contact/v3/departments", params)


def get_department_users(
    *,
    tenant_access_token: str,
    department_id: str,
    page_size: int = 50,
    page_token: str = "",
) -> dict:
    """获取部门直属用户列表"""
    params: dict[str, Any] = {"department_id": department_id, "page_size": page_size}
    if page_token:
        params["page_token"] = page_token
    return _api_get(tenant_access_token, "/contact/v3/users/find_by_department", params)


# =====================================================================
# 6. 审批 (Approval v4)
# =====================================================================

def get_approval_instance(
    *,
    tenant_access_token: str,
    instance_id: str,
) -> dict:
    """获取审批实例详情"""
    return _api_get(tenant_access_token, f"/approval/v4/instances/{instance_id}")


def list_approval_instances(
    *,
    tenant_access_token: str,
    approval_code: str,
    start_time: int,
    end_time: int,
    page_size: int = 20,
    page_token: str = "",
) -> dict:
    """查询审批实例列表"""
    body: dict[str, Any] = {
        "approval_code": approval_code,
        "start_time": str(start_time),
        "end_time": str(end_time),
        "page_size": page_size,
    }
    if page_token:
        body["page_token"] = page_token
    return _api_post(tenant_access_token, "/approval/v4/instances/query", body)


# =====================================================================
# 辅助：同步状态管理
# =====================================================================

class FeishuSyncState:
    """管理飞书同步的状态和 token 缓存"""

    def __init__(self, db: Any, feishu_secret_store: Any):
        self.db = db
        self.secret_store = feishu_secret_store
        self._cached_token: str | None = None
        self._token_expires_at: float = 0

    def _get_bot_config(self) -> tuple[str, str]:
        """获取飞书 App ID 和 Secret"""
        raw = self.db.get_setting("feishu_bot", "{}")
        import json as _json
        config = _json.loads(raw) if isinstance(raw, str) else {}
        app_id = str(config.get("appId") or "").strip()
        app_secret = ""
        if self.secret_store:
            try:
                app_secret = self.secret_store.get_api_key() or ""
            except Exception:
                pass
        return app_id, app_secret

    def get_tenant_token(self) -> str:
        """获取 tenant_access_token（有2小时缓存）"""
        import time
        if self._cached_token and time.time() < self._token_expires_at:
            return self._cached_token
        app_id, app_secret = self._get_bot_config()
        if not app_id or not app_secret:
            raise FeishuApiError("飞书应用未配置 App ID 或 App Secret")
        from app.services.feishu import fetch_tenant_access_token
        token, payload = fetch_tenant_access_token(app_id=app_id, app_secret=app_secret)
        expire = int(payload.get("expire", 7200))
        self._cached_token = token
        self._token_expires_at = time.time() + expire - 300  # 提前5分钟刷新
        return token

    def get_user_binding(self, user_id: str) -> dict | None:
        """获取用户的飞书绑定信息"""
        import json as _json
        raw = self.db.get_setting(f"feishu_user_binding:{user_id}", "")
        if not raw:
            return None
        try:
            data = _json.loads(raw)
            if data.get("linked"):
                return data
        except Exception:
            pass
        return None

    def get_receiver_config(self) -> tuple[str, str]:
        """获取全局消息接收者配置"""
        import json as _json
        raw = self.db.get_setting("feishu_bot", "{}")
        config = _json.loads(raw) if isinstance(raw, str) else {}
        return str(config.get("receiveIdType") or "open_id"), str(config.get("receiverId") or "")

    def is_configured(self) -> bool:
        """检查飞书是否已配置"""
        app_id, app_secret = self._get_bot_config()
        return bool(app_id and app_secret)
