"""L4/L5：外部学习源 · GitHub + Exa。

设计原则：
- 无 API key 时安静降级（返回空列表 + 提示），不阻塞主流程
- 调用结果缓存到 db 的简单 KV 文件（避免每次 build_overview 都打外网）
- 同步调用最长 5 秒超时，超时也返回空
- 用户在设置里配 key 后下次 build 才会激活
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

from app.models import GrowthLearningPickRecord


_CACHE_DIR = Path.home() / "Library" / "Application Support" / "YiyuThinkTankWorkbench2" / "cache" / "external_learning"
_CACHE_TTL_HOURS = 24
_REQ_TIMEOUT = 5.0


def _cache_path(name: str) -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR / f"{name}.json"


def _load_cache(name: str) -> Optional[dict]:
    p = _cache_path(name)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        ts = datetime.fromisoformat(data.get("__ts", ""))
        if datetime.now() - ts > timedelta(hours=_CACHE_TTL_HOURS):
            return None
        return data
    except Exception:
        return None


def _save_cache(name: str, payload: dict) -> None:
    p = _cache_path(name)
    payload = {**payload, "__ts": datetime.now().isoformat(timespec="seconds")}
    try:
        p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _get_github_token() -> str:
    return os.environ.get("YIYU_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


def _get_exa_api_key() -> str:
    return os.environ.get("YIYU_EXA_API_KEY") or os.environ.get("EXA_API_KEY") or ""


def fetch_github_picks(
    user_id: str,
    keywords: list[str],
    *,
    limit: int = 3,
) -> tuple[list[GrowthLearningPickRecord], bool, str]:
    """L4: 调 GitHub Search Repositories API。无 token 也能调（限速严）。

    返回 (picks, enabled, hint)
    """
    if not keywords:
        return [], False, "未提供搜索关键词"

    query = " ".join(keywords[:3])
    cache_key = f"github_{user_id}_{hash(query) & 0xffffff:x}"
    cached = _load_cache(cache_key)
    if cached and "picks" in cached:
        picks = [GrowthLearningPickRecord(**p) for p in cached["picks"]]
        return picks, True, "缓存命中"

    token = _get_github_token()
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = "https://api.github.com/search/repositories"
    params = {
        "q": f"{query} stars:>200",
        "sort": "stars",
        "order": "desc",
        "per_page": limit,
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=_REQ_TIMEOUT)
        if resp.status_code == 403:
            return [], False, "GitHub API 限速（建议配置 token）"
        if resp.status_code != 200:
            return [], False, f"GitHub API 错误 {resp.status_code}"
        data = resp.json()
    except requests.RequestException as e:
        return [], False, f"GitHub 请求失败: {type(e).__name__}"

    picks: list[GrowthLearningPickRecord] = []
    for item in (data.get("items") or [])[:limit]:
        picks.append(GrowthLearningPickRecord(
            source="github",
            sourceId=str(item.get("full_name", "")),
            title=str(item.get("full_name", ""))[:80],
            detail=str(item.get("description") or "")[:150],
            authorName=str(item.get("owner", {}).get("login", "")),
            matchedAbility="",
            matchedAbilityLabel="",
            likedCount=int(item.get("stargazers_count") or 0),
        ))

    _save_cache(cache_key, {"picks": [p.model_dump() for p in picks]})
    return picks, bool(picks), "已查询 GitHub"


def fetch_exa_picks(
    user_id: str,
    keywords: list[str],
    *,
    limit: int = 3,
) -> tuple[list[GrowthLearningPickRecord], bool, str]:
    """L5: Exa search API。需 EXA_API_KEY 环境变量。

    无 key 时返回空 + 提示。
    """
    api_key = _get_exa_api_key()
    if not api_key:
        return [], False, "Exa API key 未配置（在 .env 设 YIYU_EXA_API_KEY）"
    if not keywords:
        return [], False, "未提供搜索关键词"

    query = " ".join(keywords[:3]) + " 2026"  # 暗示找新东西
    cache_key = f"exa_{user_id}_{hash(query) & 0xffffff:x}"
    cached = _load_cache(cache_key)
    if cached and "picks" in cached:
        picks = [GrowthLearningPickRecord(**p) for p in cached["picks"]]
        return picks, True, "缓存命中"

    try:
        resp = requests.post(
            "https://api.exa.ai/search",
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json={"query": query, "numResults": limit, "type": "neural"},
            timeout=_REQ_TIMEOUT,
        )
        if resp.status_code != 200:
            return [], False, f"Exa API 错误 {resp.status_code}"
        data = resp.json()
    except requests.RequestException as e:
        return [], False, f"Exa 请求失败: {type(e).__name__}"

    picks: list[GrowthLearningPickRecord] = []
    for item in (data.get("results") or [])[:limit]:
        picks.append(GrowthLearningPickRecord(
            source="exa",
            sourceId=str(item.get("url", "")),
            title=str(item.get("title", ""))[:80],
            detail=str(item.get("text") or "")[:150],
            authorName=str(item.get("author") or ""),
        ))

    _save_cache(cache_key, {"picks": [p.model_dump() for p in picks]})
    return picks, bool(picks), "已查询 Exa"
