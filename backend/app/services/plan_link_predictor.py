"""[B] 2026-05-26 · 新建任务时, 用本地 Ollama qwen2.5:7b 闪电预测 plan item.

顾源源 5/26 拍板: 7B 模型秒级识别 + 识别不了就不挂 (不做 keyword 兜底).
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

_OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1/chat/completions"
_PREDICT_MODEL = "qwen2.5:7b"

_SYSTEM_PROMPT = """你是益语智库的任务挂接助手. 用户在新建任务时, 系统会给你:
- 任务的标题和描述
- 当前可选的部门计划项列表 (每项有 id 和 title)

你的任务: 找出最匹配的 1 个计划项. 如果任务跟所有计划项都不沾边, 返回 null.

严格按 JSON 格式输出, 不要解释, 不要 markdown:
{"planItemId": "xxx", "confidence": 0.8, "reason": "简短说明"}

判断原则:
1. 看任务标题/描述跟计划项 title 的核心概念是否一致
2. 同一业务方向 → 高分 (0.7+)
3. 部分相关 → 中分 (0.4-0.6)
4. 不相关或勉强 → planItemId 设为 null, 不挂
5. 宁可不挂, 不要乱挂 — 用户可手动挂回"""


def predict_plan_item(
    task_title: str,
    task_desc: str,
    plan_items: list[dict],
    timeout: float = 8.0,
) -> dict:
    """调本地 Ollama qwen2.5:7b 预测.

    返:
      {planItemId: str|None, confidence: float, model: str, reason: str}
      Ollama 不可用 / LLM 输出无效 → planItemId=None (不做兜底).
    """
    if not plan_items:
        return {"planItemId": None, "confidence": 0.0, "model": _PREDICT_MODEL, "reason": "无候选计划项"}

    task_text = (task_title or "").strip()
    if task_desc:
        task_text += "\n\n描述: " + task_desc.strip()
    if not task_text:
        return {"planItemId": None, "confidence": 0.0, "model": _PREDICT_MODEL, "reason": "任务标题为空"}

    plan_lines = []
    for p in plan_items:
        pid = (p.get("id") or "").strip()
        ptitle = (p.get("title") or "").strip() or "(无标题)"
        pstatement = (p.get("statement") or "").strip()
        line = f"- id={pid} | title={ptitle}"
        if pstatement:
            line += f" | 说明={pstatement[:120]}"
        plan_lines.append(line)
    plan_block = "\n".join(plan_lines)

    user_prompt = (
        f"任务:\n{task_text}\n\n"
        f"可选计划项:\n{plan_block}\n\n"
        "请按 JSON 格式回复最匹配的 1 个计划项的 id (匹配不上 planItemId 设 null)."
    )

    payload = {
        "model": _PREDICT_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 200,
        "stream": False,
    }

    try:
        req = urllib.request.Request(
            _OLLAMA_BASE_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        logger.warning("plan_link_predictor Ollama 不可用: %s", exc)
        return {"planItemId": None, "confidence": 0.0, "model": _PREDICT_MODEL, "reason": "本地 LLM 不可用"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("plan_link_predictor 异常: %s", exc)
        return {"planItemId": None, "confidence": 0.0, "model": _PREDICT_MODEL, "reason": "调用失败"}

    content = (body.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
    content = content.strip()
    if content.startswith("```"):
        end = content.find("```", 3)
        if end > 0:
            content = content[3:end]
        if content.lstrip().startswith("json"):
            content = content.lstrip()[4:]

    try:
        parsed = json.loads(content)
    except Exception as exc:  # noqa: BLE001
        logger.warning("plan_link_predictor JSON 解析失败: %s | raw=%s", exc, content[:300])
        return {"planItemId": None, "confidence": 0.0, "model": _PREDICT_MODEL, "reason": "LLM 输出格式错误"}

    item_id = parsed.get("planItemId")
    if item_id in (None, "", "null"):
        return {"planItemId": None, "confidence": 0.0, "model": _PREDICT_MODEL, "reason": parsed.get("reason") or ""}

    if not any((p.get("id") == item_id) for p in plan_items):
        logger.warning("plan_link_predictor LLM 编造 id: %s", item_id)
        return {"planItemId": None, "confidence": 0.0, "model": _PREDICT_MODEL, "reason": "AI 输出无效"}

    try:
        confidence = float(parsed.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0

    return {
        "planItemId": item_id,
        "confidence": max(0.0, min(1.0, confidence)),
        "model": _PREDICT_MODEL,
        "reason": parsed.get("reason") or "",
    }
