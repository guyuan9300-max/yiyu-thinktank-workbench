from __future__ import annotations

import json
import os
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Sequence
from uuid import uuid4

import httpx

from app.models import EventLineRecord, SmartTaskDraftRecord, SmartTaskDraftResponse


# ─── LLM provider: Volcengine Ark (火山方舟) ───────────────────────
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_LLM_MODEL = "ep-m-20260326120641-m4lf6"  # Doubao-Seed-1.6

# Legacy aliases kept for grep-ability
QWEN_BASE_URL = ARK_BASE_URL
DEFAULT_QWEN_MODEL = DEFAULT_LLM_MODEL
DOUBAO_STANDARD_SUBMIT_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit"
DOUBAO_STANDARD_QUERY_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/query"
DOUBAO_STANDARD_RESOURCE_ID = "volc.seedasr.auc"
DOUBAO_STANDARD_EXTENSIONS = {
    "pcm",
    "opus",
    "mp3",
    "wav",
    "spx",
    "ogg",
    "amr",
    "aac",
    "m4a",
}

_CN_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_DATE_CN_PATTERN = re.compile(r"([零〇一二两三四五六七八九十]{1,3})(月|日|号)")
_DATE_RANGE_FULL_PATTERN = re.compile(
    r"(?:(\d{4})年)?\s*(\d{1,2})月(\d{1,2})(?:日|号)?\s*(?:到|至|-|—|~)\s*(?:(\d{1,2})月)?(\d{1,2})(?:日|号)?"
)
_DATE_SINGLE_PATTERN = re.compile(r"(?:(\d{4})年)?\s*(\d{1,2})月(\d{1,2})(?:日|号)?")
_TIME_RANGE_PATTERN = re.compile(
    r"(上午|早上|中午|下午|晚上)?\s*(\d{1,2})(?:[:：点时](\d{1,2}))?\s*(?:到|至|-|—|~)\s*(上午|早上|中午|下午|晚上)?\s*(\d{1,2})(?:[:：点时](\d{1,2}))?"
)


def _normalize_search_text(value: str) -> str:
    return (
        value.lower()
        .replace(" ", "")
        .replace("\n", "")
        .replace("\t", "")
        .translate(str.maketrans("", "", '·•,，。！？、:：;；"\'“”‘’（）()【】[]{}<>《》-_/\\'))
        .strip()
    )


def _split_search_fragments(value: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"[\s·•,，。！？、:：;；\"'“”‘’（）()【】\[\]{}<>《》\-_\/\\]+", value)
        if item.strip() and len(item.strip()) >= 2
    ]


def derive_project_label(event_line: EventLineRecord) -> str:
    if event_line.primaryClientName and event_line.primaryClientName.strip():
        return event_line.primaryClientName.strip()
    first_segment = event_line.name.split("·", 1)[0].split("•", 1)[0].split("|", 1)[0].split("/", 1)[0]
    compact = first_segment.strip() or event_line.name.strip()
    first_word = compact.split(maxsplit=1)[0].strip()
    return first_word or compact


def _score_event_line_match(search_key: str, event_line: EventLineRecord) -> int:
    if not search_key or len(search_key) < 2:
        return 0

    aliases = {
        event_line.name,
        event_line.primaryClientName or "",
        derive_project_label(event_line),
        *(_split_search_fragments(event_line.name)),
        *(_split_search_fragments(event_line.primaryClientName or "")),
    }
    best_score = 0
    for alias in aliases:
        normalized = _normalize_search_text(alias)
        if len(normalized) < 2:
            continue
        if search_key == normalized:
            best_score = max(best_score, 320 + len(normalized))
            continue
        if search_key in normalized:
            best_score = max(best_score, 220 + len(search_key))
            continue
        if normalized in search_key:
            best_score = max(best_score, 160 + len(normalized))
    return best_score


def _coerce_chinese_number(raw: str) -> int | None:
    value = raw.strip()
    if not value:
        return None
    if value.isdigit():
        return int(value)
    if value == "十":
        return 10
    if "十" in value:
        left, _, right = value.partition("十")
        tens = 1 if not left else _CN_DIGITS.get(left)
        if tens is None:
            return None
        ones = 0 if not right else _CN_DIGITS.get(right)
        if ones is None:
            return None
        return tens * 10 + ones
    if len(value) == 1:
        return _CN_DIGITS.get(value)
    total = 0
    for ch in value:
        digit = _CN_DIGITS.get(ch)
        if digit is None:
            return None
        total = total * 10 + digit
    return total


def _normalize_spoken_text(text: str) -> str:
    return _DATE_CN_PATTERN.sub(
        lambda match: f"{_coerce_chinese_number(match.group(1)) or match.group(1)}{match.group(2)}",
        text.strip(),
    )


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _format_date_key(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _parse_date_range(text: str, reference_date: date) -> tuple[str | None, str | None]:
    normalized = _normalize_spoken_text(text)
    full_match = _DATE_RANGE_FULL_PATTERN.search(normalized)
    if full_match:
        year = int(full_match.group(1) or reference_date.year)
        start_month = int(full_match.group(2))
        start_day = int(full_match.group(3))
        end_month = int(full_match.group(4) or start_month)
        end_day = int(full_match.group(5))
        start_date = _safe_date(year, start_month, start_day)
        end_year = year + 1 if start_month > end_month else year
        end_date = _safe_date(end_year, end_month, end_day)
        return _format_date_key(start_date), _format_date_key(end_date or start_date)

    single_match = _DATE_SINGLE_PATTERN.search(normalized)
    if single_match:
        year = int(single_match.group(1) or reference_date.year)
        parsed_date = _safe_date(year, int(single_match.group(2)), int(single_match.group(3)))
        return _format_date_key(parsed_date), None

    lowered = normalized.lower()
    if "明天" in lowered:
        target = reference_date + timedelta(days=1)
        return target.isoformat(), None
    if "后天" in lowered:
        target = reference_date + timedelta(days=2)
        return target.isoformat(), None
    if "昨天" in lowered:
        target = reference_date - timedelta(days=1)
        return target.isoformat(), None
    if "今天" in lowered:
        return reference_date.isoformat(), None
    return None, None


def _convert_clock(hour: int, minute: int, meridiem: str | None) -> tuple[int, int]:
    label = (meridiem or "").strip()
    if label in {"下午", "晚上"} and hour < 12:
        hour += 12
    if label == "中午" and hour < 11:
        hour += 12
    return hour, minute


def _parse_time_range(text: str) -> tuple[str | None, int | None]:
    normalized = _normalize_spoken_text(text)
    match = _TIME_RANGE_PATTERN.search(normalized)
    if not match:
        single_time = re.search(r"(上午|早上|中午|下午|晚上)?\s*(\d{1,2})(?:[:：点时](\d{1,2}))", normalized)
        if not single_time:
            single_time = re.search(r"(上午|早上|中午|下午|晚上)?\s*(\d{1,2})点", normalized)
        if not single_time:
            return None, None
        hour, minute = _convert_clock(int(single_time.group(2)), int(single_time.group(3) or 0), single_time.group(1))
        return f"{hour:02d}:{minute:02d}", None

    start_hour, start_minute = _convert_clock(int(match.group(2)), int(match.group(3) or 0), match.group(1))
    end_hour, end_minute = _convert_clock(int(match.group(5)), int(match.group(6) or 0), match.group(4))
    duration = max(((end_hour * 60 + end_minute) - (start_hour * 60 + start_minute)), 30)
    return f"{start_hour:02d}:{start_minute:02d}", duration


def _extract_location(text: str) -> str | None:
    patterns = (
        r"(?:去|到|在)([\u4e00-\u9fffA-Za-z]{2,16})[\s，,]*?(?:做|开|办|参加|进行|开展|出差|调研|工作坊|会议|沟通|拜访)",
        r"(?:地点|位置)[:：]?\s*([\u4e00-\u9fffA-Za-z]{2,16})",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None


def _infer_title(text: str, location: str | None) -> str | None:
    patterns = (
        r"(?:做|开|办|参加|进行|安排)([^，。；,\n]{2,28}(?:工作坊|会议|沟通|调研|复盘|拜访|培训|汇报|讨论|出差))",
        r"([^，。；,\n]{2,28}(?:工作坊|会议|沟通|调研|复盘|拜访|培训|汇报|讨论|出差))",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        candidate = match.group(1).strip(" ，。；,")
        if location and location not in candidate:
            return f"{location}{candidate}"
        return candidate
    fragments = [frag for frag in re.split(r"[，。；,\n]", text) if frag.strip()]
    if not fragments:
        return None
    head = re.sub(r"^(帮我|请|安排一下|建一个|创建一个|新增一个)(日程|任务)?", "", fragments[0]).strip()
    return head[:24] or None


def _infer_project_query(text: str, title: str | None, location: str | None) -> str | None:
    patterns = (
        r"(?:项目(?:是)?关于|关于)([^，。；,\n]{2,24})",
        r"(?:关联到|归档到)([^，。；,\n]{2,24})",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip(" ，。；,的")
    if title and location and location in title:
        return f"{location}{re.sub(r'(工作坊|会议|沟通|调研|复盘|拜访|培训|汇报|讨论|出差)$', '项目', title)}"
    return title or None


def _truncate_compact_text(value: str | None, limit: int) -> str | None:
    if not value:
        return None
    compact = re.sub(r"\s+", "", value).strip(" ·•|｜/-，。；,")
    if not compact:
        return None
    return compact if len(compact) <= limit else compact[:limit]


def _strip_duplicate_terms(value: str, *terms: str | None) -> str:
    result = value
    for term in terms:
        term = (term or "").strip()
        if not term:
            continue
        result = result.replace(term, "")
        normalized_term = re.sub(r"(基金会|老师|项目|合作|研究)$", "", term)
        if normalized_term and normalized_term != term:
            result = result.replace(normalized_term, "")
    return result.strip(" ·•|｜/-，。；,")


def _summarize_event_line_label(event_line_name: str | None, client_name: str | None) -> str | None:
    base = (event_line_name or "").strip()
    if not base:
        return None

    candidates: list[str] = []
    if client_name:
        stripped = base
        if stripped.startswith(client_name):
            stripped = stripped[len(client_name) :].strip(" ·•|｜/-")
        stripped = _strip_duplicate_terms(stripped, client_name)
        candidates.append(stripped)
    candidates.append(base)

    generic_labels = {"项目", "工作坊", "会议", "沟通", "调研", "复盘", "合作"}
    cleanup_patterns = (
        r"^跟[^的]{0,12}(?:老师|总|主任|校长|院长|会长|负责人)?",
        r"^(?:跟|和|与|围绕|关于|针对|推进|跟进|沟通|核对|讨论|安排|整理|准备|发给|确认|对接)",
        r"^(?:她的|他的|其|本次|这个|那个)",
    )

    for candidate in candidates:
        label = candidate.strip(" ·•|｜/-")
        if not label:
            continue
        for pattern in cleanup_patterns:
            label = re.sub(pattern, "", label)
        label = label.strip(" ·•|｜/-")
        if "的" in label:
            tail = label.split("的")[-1].strip()
            if 2 <= len(tail) <= 12:
                label = tail
        label = re.sub(r"(进度|推进|事项|事宜|安排|计划|时间|节点|规划)$", "", label).strip()
        if label in generic_labels and client_name and base.startswith(client_name):
            carry = client_name[-min(4, len(client_name)) :].strip()
            lifted = f"{carry}{label}".strip()
            if lifted and lifted not in generic_labels:
                return _truncate_compact_text(lifted, 10)
        if label and label not in generic_labels:
            return _truncate_compact_text(label, 10)

    fallback = _strip_duplicate_terms(base, client_name)
    compact = _truncate_compact_text(fallback or base, 10)
    return compact


def _extract_deadline_fragment(text: str) -> str | None:
    match = re.search(r"(今天|明天|后天|本周[一二三四五六日天]?|下周[一二三四五六日天]?|周[一二三四五六日天](?:之前|前|后)?)", text)
    if not match:
        return None
    return match.group(1).replace("之前", "前")


def _clean_action_object(value: str, client_name: str | None, event_line_name: str | None) -> str:
    text = value.strip(" ，。；,")
    text = re.sub(r"^(一个|一下|一版|一份|关于|把|将|再|先|会|要|需要)", "", text)
    text = re.sub(r"(过来|一下|一下子|出来|完成|落实)$", "", text)
    text = re.sub(r"(的)?(时间规划|时间安排)$", "规划", text)
    text = re.sub(r"(安排|计划|时间)$", "", text)
    text = _strip_duplicate_terms(text, client_name, event_line_name)
    text = text.strip("的 ")
    return text.strip(" ，。；,")


def _looks_like_good_action_summary(value: str | None) -> bool:
    if not value:
        return False
    text = value.strip()
    if len(text) < 3:
        return False
    if re.search(r"(今天|明天|后天|本周|下周|周[一二三四五六日天](?:之前|前|后)?|\d{1,2}月\d{1,2}[日号]?|\d{1,2}[:：点时])", text):
        return False
    if re.search(r"(会发|要发|需要|之前|过来|帮我|请|安排一下|创建一个|新增一个)", text):
        return False
    return True


def _infer_action_summary(
    transcript: str,
    raw_title: str | None,
    client_name: str | None,
    event_line_name: str | None,
) -> str | None:
    preferred = _clean_action_object(raw_title or "", client_name, event_line_name)
    if _looks_like_good_action_summary(preferred):
        preferred_short = _truncate_compact_text(preferred, 20)
        if preferred_short:
            return preferred_short

    deadline = _extract_deadline_fragment(transcript)
    verb_match = re.search(
        r"(发|提交|确认|安排|推进|跟进|整理|输出|准备|完成|沟通|对齐|核对|复盘|拜访|汇报|讨论|调研|梳理)([^，。；,\n]{0,24})",
        transcript,
    )
    if verb_match:
        verb = verb_match.group(1)
        obj = _clean_action_object(verb_match.group(2), client_name, event_line_name)
        if "关于" in obj:
            obj = _clean_action_object(obj.split("关于", 1)[1], client_name, event_line_name)
        if obj:
            candidate = f"{deadline or ''}{verb}{obj}"
            shortened = _truncate_compact_text(candidate, 14)
            if shortened:
                return shortened

    topic_match = re.search(r"关于([^，。；,\n]{2,18})", transcript)
    if topic_match:
        topic = _clean_action_object(topic_match.group(1), client_name, event_line_name)
        if topic:
            if re.search(r"(发|提交)", transcript):
                return _truncate_compact_text(f"{deadline or ''}发{topic}", 14)
            return _truncate_compact_text(topic, 14)

    source = _strip_duplicate_terms(raw_title or transcript, client_name, event_line_name)
    source = re.sub(r"^(帮我|请|安排一下|安排|建一个|创建一个|新增一个|提醒我|记一下|记得|我要|我想|我们|现在|之后|然后|就是)", "", source)
    source = re.sub(r"(今天|明天|后天|本周|下周|周[一二三四五六日天](?:之前|前|后)?|\d{1,2}月\d{1,2}[日号]?|上午|下午|晚上|中午|\d{1,2}[:：点时]\d{0,2})", "", source)
    source = source.strip(" ，。；,")
    return _truncate_compact_text(source, 14)


def _compose_structured_title(
    *,
    client_name: str | None,
    event_line_name: str | None,
    action_summary: str | None,
    fallback_title: str,
) -> str:
    parts: list[str] = []
    client_label = _truncate_compact_text(client_name, 10)
    event_line_label = _summarize_event_line_label(event_line_name, client_name)
    action_label = _truncate_compact_text(action_summary, 20)

    if client_label:
        parts.append(client_label)

    if event_line_label and event_line_label not in parts:
        parts.append(event_line_label)

    if action_label and action_label not in parts:
        parts.append(action_label)

    if not parts:
        return _truncate_compact_text(fallback_title, 24) or fallback_title[:24]

    joined = "｜".join(parts)
    if len(joined) <= 40:
        return joined

    compact_parts = [
        _truncate_compact_text(client_label, 8),
        _truncate_compact_text(event_line_label, 10),
        _truncate_compact_text(action_label, 16),
    ]
    compact_joined = "｜".join([item for item in compact_parts if item])
    return compact_joined or (_truncate_compact_text(fallback_title, 24) or fallback_title[:24])


def _infer_action_tag(text: str) -> str:
    if re.search(r"会议|沟通|对接|拜访|工作坊|复盘|汇报|讨论|访谈", text):
        return "会议/沟通"
    if re.search(r"调研|分析|研究|诊断|梳理|摸底", text):
        return "内部分析"
    return "材料/交付"


def _build_description(
    transcript: str,
    start_date: str | None,
    end_date: str | None,
    due_time: str | None,
    duration_minutes: int | None,
    location: str | None,
) -> str:
    lines: list[str] = []
    if start_date and end_date and start_date != end_date:
        lines.append(f"时间范围：{start_date} 至 {end_date}")
    elif start_date:
        lines.append(f"日期：{start_date}")
    if due_time:
        lines.append(f"开始时间：{due_time}")
    if duration_minutes and duration_minutes > 0:
        hours = duration_minutes / 60
        lines.append(f"预计时长：{hours:g} 小时")
    if location:
        lines.append(f"地点：{location}")
    lines.append("原始输入：")
    lines.append(transcript.strip())
    return "\n".join(lines)


def _load_relaxed_json(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end >= start:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def _qwen_api_key() -> str:
    """Return the LLM API key. Checks Volcengine Ark keys first, then legacy Qwen keys."""
    return (
        os.getenv("ARK_API_KEY", "").strip()
        or os.getenv("VOLCENGINE_API_KEY", "").strip()
        or os.getenv("DASHSCOPE_API_KEY", "").strip()
        or os.getenv("QWEN_API_KEY", "").strip()
        or os.getenv("YIYU_QWEN_API_KEY", "").strip()
    )


def _doubao_file_asr_credentials() -> tuple[str, str]:
    app_id = (
        os.getenv("DOUBAO_FILE_ASR_APP_ID", "").strip()
        or os.getenv("YIYU_DOUBAO_FILE_ASR_APP_ID", "").strip()
        or os.getenv("VOLCENGINE_FILE_ASR_APP_ID", "").strip()
        or os.getenv("DOUBAO_ASR_APP_ID", "").strip()
        or os.getenv("YIYU_DOUBAO_ASR_APP_ID", "").strip()
        or os.getenv("VOLCENGINE_ASR_APP_ID", "").strip()
    )
    access_token = (
        os.getenv("DOUBAO_FILE_ASR_ACCESS_TOKEN", "").strip()
        or os.getenv("YIYU_DOUBAO_FILE_ASR_ACCESS_TOKEN", "").strip()
        or os.getenv("VOLCENGINE_FILE_ASR_ACCESS_TOKEN", "").strip()
        or os.getenv("DOUBAO_ASR_ACCESS_TOKEN", "").strip()
        or os.getenv("YIYU_DOUBAO_ASR_ACCESS_TOKEN", "").strip()
        or os.getenv("VOLCENGINE_ASR_ACCESS_TOKEN", "").strip()
    )
    return app_id, access_token


def _doubao_stream_asr_credentials() -> tuple[str, str]:
    app_id = (
        os.getenv("DOUBAO_STREAM_ASR_APP_ID", "").strip()
        or os.getenv("YIYU_DOUBAO_STREAM_ASR_APP_ID", "").strip()
        or os.getenv("VOLCENGINE_STREAM_ASR_APP_ID", "").strip()
        or os.getenv("DOUBAO_ASR_APP_ID", "").strip()
        or os.getenv("YIYU_DOUBAO_ASR_APP_ID", "").strip()
        or os.getenv("VOLCENGINE_ASR_APP_ID", "").strip()
    )
    access_token = (
        os.getenv("DOUBAO_STREAM_ASR_ACCESS_TOKEN", "").strip()
        or os.getenv("YIYU_DOUBAO_STREAM_ASR_ACCESS_TOKEN", "").strip()
        or os.getenv("VOLCENGINE_STREAM_ASR_ACCESS_TOKEN", "").strip()
        or os.getenv("DOUBAO_ASR_ACCESS_TOKEN", "").strip()
        or os.getenv("YIYU_DOUBAO_ASR_ACCESS_TOKEN", "").strip()
        or os.getenv("VOLCENGINE_ASR_ACCESS_TOKEN", "").strip()
    )
    return app_id, access_token


def _infer_extension(file_name: str | None, mime_type: str | None) -> str:
    suffix = Path(file_name or "").suffix.lower().lstrip(".")
    if suffix:
        return suffix
    lowered = (mime_type or "").lower()
    if "mpeg" in lowered or "mp3" in lowered:
        return "mp3"
    if "wav" in lowered:
        return "wav"
    if "ogg" in lowered or "opus" in lowered:
        return "ogg"
    if "aac" in lowered:
        return "aac"
    if "m4a" in lowered or "mp4" in lowered:
        return "m4a"
    return "bin"


def _build_asr_headers(*, app_id: str, access_token: str, resource_id: str, request_id: str, tt_logid: str | None = None) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "X-Api-App-Key": app_id,
        "X-Api-Access-Key": access_token,
        "X-Api-Resource-Id": resource_id,
        "X-Api-Request-Id": request_id,
        "X-Api-Sequence": "-1",
    }
    if tt_logid:
        headers["X-Tt-Logid"] = tt_logid
    return headers


def _extract_asr_text(payload: dict[str, Any]) -> str:
    result = payload.get("result")
    if isinstance(result, dict):
        text = result.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        utterances = result.get("utterances")
        if isinstance(utterances, list):
            parts = [str(item.get("text", "")).strip() for item in utterances if isinstance(item, dict) and str(item.get("text", "")).strip()]
            if parts:
                return "\n".join(parts)
    text = payload.get("text")
    return text.strip() if isinstance(text, str) else ""


def _extract_doubao_error_message(response: httpx.Response) -> str:
    header_message = (response.headers.get("X-Api-Message") or "").strip()
    status_code = (response.headers.get("X-Api-Status-Code") or "").strip()
    body_message = ""
    try:
        payload = response.json()
        if isinstance(payload, dict):
            header = payload.get("header")
            if isinstance(header, dict):
                body_message = str(header.get("message") or "").strip()
            if not body_message:
                body_message = str(payload.get("message") or "").strip()
    except Exception:
        body_message = response.text.strip()

    message = header_message or body_message or response.text.strip() or f"HTTP {response.status_code}"
    if "requested resource not granted" in message:
        return (
            f"豆包语音识别资源未授权（{status_code or response.status_code}）。"
            "当前云端配置的 App ID / Access Token 没有拿到当前调用资源的权限，"
            "通常是用了错误的资源 ID，或填成了没有对应识别能力的应用。"
        )
    return f"豆包语音识别请求失败：{status_code or response.status_code} {message}".strip()


def transcribe_audio_with_doubao(
    audio_bytes: bytes,
    *,
    file_name: str | None,
    mime_type: str | None,
    public_url: str | None = None,
) -> str:
    app_id, access_token = _doubao_file_asr_credentials()
    if not app_id or not access_token:
        raise RuntimeError("豆包 ASR 未配置 appid 或 access token。")
    extension = _infer_extension(file_name, mime_type)
    if not audio_bytes:
        raise RuntimeError("录音内容为空，无法转写。")
    request_id = str(uuid4())

    if not public_url:
        raise RuntimeError("当前录音格式需要云端可访问 URL 才能转写。")
    if extension not in DOUBAO_STANDARD_EXTENSIONS:
        raise RuntimeError(f"当前录音格式 {extension} 暂不支持自动转写。")

    submit_payload = {
        "user": {"uid": app_id},
        "audio": {
            "format": extension,
            "url": public_url,
        },
        "request": {
            "model_name": "bigmodel",
            "enable_itn": True,
            "enable_punc": True,
            "enable_ddc": True,
        },
    }

    with httpx.Client(timeout=httpx.Timeout(timeout=None, connect=8.0, read=20.0, write=20.0, pool=8.0)) as client:
        submit_response = client.post(
            DOUBAO_STANDARD_SUBMIT_URL,
            headers=_build_asr_headers(
                app_id=app_id,
                access_token=access_token,
                resource_id=DOUBAO_STANDARD_RESOURCE_ID,
                request_id=request_id,
            ),
            json=submit_payload,
        )
        if submit_response.status_code >= 400:
            raise RuntimeError(_extract_doubao_error_message(submit_response))
        submit_status = submit_response.headers.get("X-Api-Status-Code", "")
        if submit_status != "20000000":
            raise RuntimeError(f"豆包标准版提交失败：{submit_status} {submit_response.headers.get('X-Api-Message', '')}".strip())

        tt_logid = submit_response.headers.get("X-Tt-Logid", "")
        for _ in range(60):
            time.sleep(1.0)
            query_response = client.post(
                DOUBAO_STANDARD_QUERY_URL,
                headers=_build_asr_headers(
                    app_id=app_id,
                    access_token=access_token,
                    resource_id=DOUBAO_STANDARD_RESOURCE_ID,
                    request_id=request_id,
                    tt_logid=tt_logid or None,
                ),
                json={},
            )
            if query_response.status_code >= 400:
                raise RuntimeError(_extract_doubao_error_message(query_response))
            query_status = query_response.headers.get("X-Api-Status-Code", "")
            if query_status == "20000000":
                transcript = _extract_asr_text(query_response.json())
                if transcript:
                    return transcript
                raise RuntimeError("豆包标准版已完成，但未返回有效转写文本。")
            if query_status == "20000003":
                raise RuntimeError("录音中没有识别到有效人声。")
            if query_status not in {"20000001", "20000002"}:
                raise RuntimeError(f"豆包标准版查询失败：{query_status} {query_response.headers.get('X-Api-Message', '')}".strip())
        raise RuntimeError("豆包标准版转写超时，请稍后重试。")


def _qwen_extract(transcript: str, reference_date: date) -> dict[str, Any] | None:
    api_key = _qwen_api_key()
    if not api_key:
        return None

    schema = {
        "type": "object",
        "properties": {
            "intent": {"type": "string"},
            "title": {"type": ["string", "null"]},
            "actionSummary": {"type": ["string", "null"]},
            "startDate": {"type": ["string", "null"]},
            "endDate": {"type": ["string", "null"]},
            "startTime": {"type": ["string", "null"]},
            "durationMinutes": {"type": ["integer", "null"]},
            "location": {"type": ["string", "null"]},
            "description": {"type": ["string", "null"]},
            "projectQuery": {"type": ["string", "null"]},
            "eventLineQuery": {"type": ["string", "null"]},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["intent", "tags"],
    }
    user_prompt = (
        "请从以下中文口语中提取移动端任务/日程草稿。\n"
        "任务标题的命名结构必须是：「组织/客户名称 + 事件线/项目名 + 具体动作」，用竖线分隔。\n"
        "例如：'华润万家｜Q4供应链优化｜提交方案初稿'、'日慈基金会｜品牌改造｜等高老师发时间规划'。\n"
        "projectQuery 填口语中提到的组织/客户名称（如'日慈基金会'、'华润万家'）。\n"
        "eventLineQuery 填口语中提到的项目/事件线关键词（如'品牌改造'、'供应链优化'）。\n"
        "actionSummary 填具体要做的事（如'等高老师发时间规划'、'提交方案初稿'），不要截断。\n"
        "description 必须填写！把口语内容整理成条理清晰的任务描述：\n"
        "  - 提炼核心要做的事情\n"
        "  - 列出关键人物、步骤、注意事项\n"
        "  - 不要照搬原文，要用书面语重新组织\n"
        "  - 如果有多个步骤，用编号列出\n"
        "如果是多天安排，请 startDate 用开始日期，endDate 用结束日期。\n"
        "不要把整段转写原文照搬进 title，要提炼结构化。\n"
        "只返回 JSON，不要解释。\n"
        f"参考日期：{reference_date.isoformat()}\n"
        f"口语内容：{transcript}"
    )
    payload = {
        "model": os.getenv("YIYU_SMART_INPUT_MODEL", DEFAULT_QWEN_MODEL),
        "messages": [
            {"role": "system", "content": "你是移动端智能输入解析器。只返回 JSON。"},
            {
                "role": "user",
                "content": (
                    "请严格返回一个 JSON 对象，不要使用 Markdown，不要添加解释。"
                    f"请确保返回结构满足下面这个 JSON Schema。\n{json.dumps(schema, ensure_ascii=False)}\n\n{user_prompt}"
                ),
            },
        ],
        "temperature": 0.2,
        "top_p": 0.85,
        "max_tokens": 1200,
        "stream": False,
        "enable_thinking": False,
    }
    timeout = httpx.Timeout(timeout=None, connect=8.0, read=18.0, write=18.0, pool=8.0)
    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            f"{ARK_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        result = response.json()
    text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    return _load_relaxed_json(text)


def _heuristic_extract(transcript: str, reference_date: date) -> tuple[dict[str, Any], list[str]]:
    cleaned = transcript.strip()
    start_date, end_date = _parse_date_range(cleaned, reference_date)
    due_time, duration_minutes = _parse_time_range(cleaned)
    location = _extract_location(cleaned)
    title = _infer_title(cleaned, location)
    project_query = _infer_project_query(cleaned, title, location)
    payload = {
        "intent": "task_schedule",
        "title": title,
        "startDate": start_date,
        "endDate": end_date,
        "startTime": due_time,
        "durationMinutes": duration_minutes,
        "location": location,
        "description": _build_description(cleaned, start_date, end_date, due_time, duration_minutes, location),
        "projectQuery": project_query,
        "eventLineQuery": title or project_query,
        "tags": [_infer_action_tag(cleaned)],
    }
    warnings: list[str] = []
    if not title:
        warnings.append("标题无法完全确定，已使用原始输入生成草稿。")
        payload["title"] = cleaned[:24]
    if not start_date:
        warnings.append("未识别到明确日期，已保留为无截止日期草稿。")
    return payload, warnings


def _match_event_line(
    event_lines: Sequence[EventLineRecord],
    *,
    current_event_line_id: str | None,
    title: str | None,
    project_query: str | None,
    event_line_query: str | None,
    raw_transcript: str | None = None,
) -> EventLineRecord | None:
    best: EventLineRecord | None = None
    best_score = 0
    search_terms = [
        _normalize_search_text(event_line_query or ""),
        _normalize_search_text(project_query or ""),
        _normalize_search_text(title or ""),
    ]
    # Also match against fragments from the raw voice transcript.
    # This catches client/project names that AI may have dropped from the title.
    if raw_transcript:
        for fragment in _split_search_fragments(raw_transcript):
            normalized = _normalize_search_text(fragment)
            if len(normalized) >= 2 and normalized not in search_terms:
                search_terms.append(normalized)
    for event_line in event_lines:
        score = 0
        if current_event_line_id and event_line.id == current_event_line_id:
            score += 28
        for search_key in search_terms:
            score = max(score, _score_event_line_match(search_key, event_line))
        if score > best_score:
            best_score = score
            best = event_line
    return best if best_score >= 120 else None


def build_smart_task_draft(
    transcript: str,
    event_lines: Sequence[EventLineRecord],
    *,
    reference_date: date | None = None,
    current_event_line_id: str | None = None,
) -> SmartTaskDraftResponse:
    reference = reference_date or datetime.now().date()
    warnings: list[str] = []
    parsed: dict[str, Any] | None = None
    confidence = 0.42

    try:
        parsed = _qwen_extract(transcript, reference)
        if parsed:
            confidence = 0.84
    except Exception:
        warnings.append("AI 解析暂时不可用，已切换到规则兜底。")

    if not parsed:
        parsed, heuristic_warnings = _heuristic_extract(transcript, reference)
        warnings.extend(heuristic_warnings)

    raw_title = str(parsed.get("title") or "").strip() or transcript.strip()[:24]
    start_date = str(parsed.get("startDate") or "").strip() or None
    end_date = str(parsed.get("endDate") or "").strip() or None
    due_time = str(parsed.get("startTime") or "").strip() or None
    raw_duration = parsed.get("durationMinutes")
    duration_minutes = int(raw_duration) if isinstance(raw_duration, int) else None
    location = str(parsed.get("location") or "").strip() or None
    project_query = str(parsed.get("projectQuery") or "").strip() or None
    event_line_query = str(parsed.get("eventLineQuery") or "").strip() or None
    raw_action_summary = str(parsed.get("actionSummary") or "").strip() or None
    tags = [str(item).strip() for item in parsed.get("tags", []) if str(item).strip()] or [_infer_action_tag(transcript)]

    description = str(parsed.get("description") or "").strip() or _build_description(
        transcript,
        start_date,
        end_date,
        due_time,
        duration_minutes,
        location,
    )

    matched_event_line = _match_event_line(
        event_lines,
        current_event_line_id=current_event_line_id,
        title=raw_title,
        project_query=project_query,
        event_line_query=event_line_query,
        raw_transcript=transcript,
    )

    client_name = derive_project_label(matched_event_line) if matched_event_line else None
    event_line_name = matched_event_line.name if matched_event_line else None
    action_summary = _infer_action_summary(
        transcript,
        raw_action_summary or raw_title,
        client_name,
        event_line_name,
    )
    title = _compose_structured_title(
        client_name=client_name,
        event_line_name=event_line_name,
        action_summary=action_summary,
        fallback_title=raw_title,
    )

    draft = SmartTaskDraftRecord(
        title=title,
        dueDate=start_date,
        endDate=end_date,
        dueTime=due_time,
        durationMinutes=duration_minutes,
        location=location,
        description=description,
        tags=tags,
        clientId=matched_event_line.primaryClientId if matched_event_line else None,
        clientName=client_name,
        eventLineId=matched_event_line.id if matched_event_line else None,
        eventLineName=event_line_name,
        projectQuery=project_query or client_name or title,
        eventLineQuery=event_line_query or event_line_name or title,
    )

    if not matched_event_line:
        warnings.append("未自动命中项目/事件线，生成后可在表单里手动调整。")

    return SmartTaskDraftResponse(
        transcript=transcript.strip(),
        intent=str(parsed.get("intent") or "task_schedule"),
        draft=draft,
        warnings=warnings,
        confidence=confidence,
    )
