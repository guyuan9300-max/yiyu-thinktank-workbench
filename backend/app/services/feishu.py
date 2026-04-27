from __future__ import annotations

import json
from urllib.parse import urlencode
from typing import Literal

import httpx


FeishuReceiveIdType = Literal["open_id", "user_id", "email", "chat_id"]

_OPEN_FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"


class FeishuApiError(RuntimeError):
    pass


def _parse_response_json(response: httpx.Response) -> dict:
    try:
        payload = response.json()
    except ValueError as exc:
        raise FeishuApiError("飞书返回了无法解析的响应。") from exc
    if not isinstance(payload, dict):
        raise FeishuApiError("飞书返回了无效的响应结构。")
    return payload


def _raise_for_feishu_error(payload: dict, fallback_message: str) -> None:
    code = payload.get("code", 0)
    if code == 0:
        return
    message = str(payload.get("msg") or payload.get("message") or fallback_message)
    raise FeishuApiError(message)


def fetch_tenant_access_token(
    *,
    app_id: str,
    app_secret: str,
    transport: httpx.BaseTransport | None = None,
) -> tuple[str, dict]:
    with httpx.Client(timeout=httpx.Timeout(12.0, connect=4.0), transport=transport) as client:
        response = client.post(
            f"{_OPEN_FEISHU_BASE_URL}/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
        )
    payload = _parse_response_json(response)
    _raise_for_feishu_error(payload, "飞书租户令牌获取失败。")
    token = str(payload.get("tenant_access_token") or "").strip()
    if not token:
        raise FeishuApiError("飞书没有返回 tenant access token。")
    return token, payload


def fetch_app_access_token(
    *,
    app_id: str,
    app_secret: str,
    transport: httpx.BaseTransport | None = None,
) -> tuple[str, dict]:
    with httpx.Client(timeout=httpx.Timeout(12.0, connect=4.0), transport=transport) as client:
        response = client.post(
            f"{_OPEN_FEISHU_BASE_URL}/auth/v3/app_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
        )
    payload = _parse_response_json(response)
    _raise_for_feishu_error(payload, "飞书应用令牌获取失败。")
    token = str(payload.get("app_access_token") or "").strip()
    if not token:
        raise FeishuApiError("飞书没有返回 app access token。")
    return token, payload


def build_user_authorize_url(
    *,
    app_id: str,
    redirect_uri: str,
    state: str,
) -> str:
    query = urlencode(
        {
            "app_id": app_id,
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    return f"{_OPEN_FEISHU_BASE_URL}/authen/v1/index?{query}"


def exchange_authorization_code(
    *,
    app_access_token: str,
    app_id: str,
    app_secret: str,
    code: str,
    transport: httpx.BaseTransport | None = None,
) -> dict:
    with httpx.Client(timeout=httpx.Timeout(12.0, connect=4.0), transport=transport) as client:
        response = client.post(
            f"{_OPEN_FEISHU_BASE_URL}/authen/v1/access_token",
            headers={"Authorization": f"Bearer {app_access_token}"},
            json={
                "grant_type": "authorization_code",
                "code": code,
                "app_id": app_id,
                "app_secret": app_secret,
            },
        )
    payload = _parse_response_json(response)
    _raise_for_feishu_error(payload, "飞书授权码换取用户令牌失败。")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise FeishuApiError("飞书用户令牌响应缺少 data。")
    access_token = str(data.get("access_token") or "").strip()
    if not access_token:
        raise FeishuApiError("飞书没有返回用户 access token。")
    return data


def fetch_user_info(
    *,
    user_access_token: str,
    transport: httpx.BaseTransport | None = None,
) -> dict:
    with httpx.Client(timeout=httpx.Timeout(12.0, connect=4.0), transport=transport) as client:
        response = client.get(
            f"{_OPEN_FEISHU_BASE_URL}/authen/v1/user_info",
            headers={"Authorization": f"Bearer {user_access_token}"},
        )
    payload = _parse_response_json(response)
    _raise_for_feishu_error(payload, "飞书用户信息获取失败。")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise FeishuApiError("飞书用户信息响应缺少 data。")
    return data


def send_text_message(
    *,
    tenant_access_token: str,
    receive_id_type: FeishuReceiveIdType,
    receive_id: str,
    text: str,
    transport: httpx.BaseTransport | None = None,
) -> dict:
    content = json.dumps({"text": text}, ensure_ascii=False)
    with httpx.Client(timeout=httpx.Timeout(12.0, connect=4.0), transport=transport) as client:
        response = client.post(
            f"{_OPEN_FEISHU_BASE_URL}/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            headers={"Authorization": f"Bearer {tenant_access_token}"},
            json={
                "receive_id": receive_id,
                "msg_type": "text",
                "content": content,
            },
        )
    payload = _parse_response_json(response)
    _raise_for_feishu_error(payload, "飞书消息发送失败。")
    return payload
