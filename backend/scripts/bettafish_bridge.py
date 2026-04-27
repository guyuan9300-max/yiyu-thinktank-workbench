from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request
import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPO_DIR = PROJECT_ROOT / "external" / "BettaFish"
DEFAULT_HOST = os.getenv("BETTAFISH_BRIDGE_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("BETTAFISH_BRIDGE_PORT", "18101"))
DEFAULT_WORKBENCH_DATA_DIR = Path(
    os.getenv("YIYU_WORKBENCH_DATA_DIR")
    or (Path.home() / "Library" / "Application Support" / "YiyuThinkTankWorkbench")
)
DEFAULT_PROVIDER = "mock"
DEFAULT_MODELS = {
    "mock": "mock-summarizer",
    "qwen": "qwen3.5-plus",
}
QWEN_BASE_URL = "https://coding.dashscope.aliyuncs.com/v1"
LLM_TIMEOUT_SECONDS = float(os.getenv("YIYU_BETTAFISH_LLM_TIMEOUT_SECONDS", "25"))
KEYCHAIN_SERVICES = {
    "qwen": "com.yiyu.self-workbench.qwen",
}


def resolve_repo_dir() -> Path:
    raw = os.getenv("BETTAFISH_REPO_DIR", "").strip()
    return Path(raw).expanduser().resolve() if raw else DEFAULT_REPO_DIR.resolve()


REPO_DIR = resolve_repo_dir()
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))


app = Flask(__name__)


def get_db_setting(key: str, default: str = "") -> str:
    db_path = DEFAULT_WORKBENCH_DATA_DIR / "app.db"
    if not db_path.exists():
        return default
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute("select value from settings where key = ?", (key,)).fetchone()
            if not row or row[0] is None:
                return default
            return str(row[0])
    except Exception:
        return default


def get_keychain_secret(service_name: str) -> str:
    try:
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-a",
                "default",
                "-s",
                service_name,
                "-w",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as error:
        stderr = (error.stderr or "").lower()
        if "could not be found" in stderr or "item could not be found" in stderr:
            return ""
        raise RuntimeError("读取 macOS 钥匙串失败。") from error


def resolve_workbench_ai_config() -> dict[str, Any]:
    override_provider = os.getenv("YIYU_BETTAFISH_LLM_PROVIDER", "").strip()
    override_model = os.getenv("YIYU_BETTAFISH_LLM_MODEL", "").strip()
    override_api_key = os.getenv("YIYU_BETTAFISH_LLM_API_KEY", "").strip()

    provider = override_provider or get_db_setting("ai_provider", DEFAULT_PROVIDER)
    if provider not in DEFAULT_MODELS:
        provider = DEFAULT_PROVIDER

    model = override_model or get_db_setting("ai_model", DEFAULT_MODELS.get(provider, DEFAULT_MODELS[DEFAULT_PROVIDER]))
    api_key = override_api_key
    credential_source = "env" if override_api_key else "none"

    if not api_key and provider in KEYCHAIN_SERVICES:
        api_key = get_keychain_secret(KEYCHAIN_SERVICES[provider])
        credential_source = "keychain" if api_key else "none"

    return {
        "provider": provider,
        "model": model or DEFAULT_MODELS.get(provider, DEFAULT_MODELS[DEFAULT_PROVIDER]),
        "api_key": api_key,
        "ready": provider != "mock" and bool(api_key),
        "credential_source": credential_source,
    }


def compact_text(value: str, limit: int = 12000) -> str:
    normalized = " ".join((value or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip() + "..."


def extract_json_object(text: str) -> dict[str, Any]:
    if not text:
        raise ValueError("empty response")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("response is not a JSON object")
    return parsed


def normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            normalized.append(text)
    return normalized


def unique_string_list(items: list[str], limit: int = 4) -> list[str]:
    deduped: list[str] = []
    seen = set()
    for item in items:
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(key)
        if len(deduped) >= limit:
            break
    return deduped


def heuristic_signal(content: str, scene: str, audience_type: str) -> dict[str, Any]:
    text = compact_text(content, limit=4000)
    lower_text = text.lower()
    risk_points: list[str] = []
    misunderstanding_points: list[str] = []

    strong_emotion_patterns = [
        ("求求", "文本出现明显求助式、乞求式表达，容易被外部视角理解为情绪施压。"),
        ("绝望", "文本使用极端负面情绪词，容易触发“过度渲染”判断。"),
        ("没有任何希望", "存在绝对化表达，容易被认为夸大处境。"),
        ("震惊", "标题党或强刺激词汇较重，可能削弱可信度。"),
        ("！", "感叹号使用偏多，外部读者可能感到情绪被强推。"),
    ]
    confrontational_patterns = [
        ("造谣", "回应稿中带有直接指责性措辞，容易激化对立。"),
        ("抹黑", "对抗性表述偏强，可能促发二次争执。"),
        ("追究法律责任", "开篇或过早释放威胁性边界，可能让中立受众感到防御性过高。"),
    ]
    vague_patterns = [
        ("很多", "出现模糊量词但缺少事实锚点，可信度容易被打折。"),
        ("长期", "表述范围较大，但缺少时间和证据锚点。"),
        ("严重", "强判断词出现后如果没有支撑材料，容易被质疑。"),
    ]

    for pattern, message in strong_emotion_patterns:
        if pattern in text:
            risk_points.append(message)
    for pattern, message in confrontational_patterns:
        if pattern in text:
            risk_points.append(message)
            misunderstanding_points.append("外部受众可能把强硬措辞理解为心虚、傲慢，或认为机构没有在回应事实。")
    for pattern, message in vague_patterns:
        if pattern in text:
            misunderstanding_points.append(message)

    if not re.search(r"\d", text):
        risk_points.append("当前文本缺少数字、时间或对象锚点，外部读者不容易判断信息是否可信。")

    if audience_type in {"donor", "key_person"} and not re.search(r"元|预算|审计|明细|比例|人数|项目", text):
        misunderstanding_points.append("面对捐赠相关对象时，文本缺少用途拆解或项目细节，容易被理解为目标空泛。")

    if scene == "pr" and not re.search(r"时间线|审计|凭证|说明|披露|链接|截图", text):
        risk_points.append("舆情回应场景下未补充时间线或第三方凭证，容易被视为只在表达态度，没有增加事实。")

    if scene == "project" and not re.search(r"机制|持续|结对|协作|路径|指标", text):
        misunderstanding_points.append("项目表达更像一次性活动描述，外部可能质疑项目是否真正解决结构性问题。")

    emotion = "偏强烈"
    if not any(marker in text for marker in ["！", "求求", "绝望", "震惊", "必须"]):
        emotion = "相对克制"

    credibility = "中等"
    if len(risk_points) >= 3 or "没有任何希望" in text or "抹黑" in text:
        credibility = "偏弱"
    elif re.search(r"\d", text) and re.search(r"项目|明细|时间|链接|审计|案例", text):
        credibility = "较强"

    if not risk_points:
        risk_points.append("当前文本没有触发明显高危词，但仍建议结合对象视角复核语气与证据密度。")
    if not misunderstanding_points:
        misunderstanding_points.append("建议补一层“外部读者最可能误会什么”的解释，避免内部视角默认读者已经理解背景。")

    return {
        "emotion": emotion,
        "credibility": credibility,
        "risk_points": unique_string_list(risk_points),
        "misunderstanding_points": unique_string_list(misunderstanding_points),
        "raw": {
            "source": "heuristic",
            "scene": scene,
            "audience_type": audience_type,
            "content_preview": text[:160],
            "content_contains_public_risk_terms": any(term in lower_text for term in ["谣", "危机", "投诉", "举报"]),
        },
    }


def build_llm_prompt(payload: dict[str, Any]) -> tuple[str, str]:
    scene = str(payload.get("scene") or "pr")
    audience_type = str(payload.get("audience_type") or "public")
    organization_context = payload.get("organization_context") or {}
    dna_summary = payload.get("dna_summary") or {}
    analysis_options = payload.get("analysis_options") or {}

    system_prompt = (
        "你是公益机构对外表达的风险诊断助手。"
        "你的任务不是直接改稿，而是站在外部受众视角做简洁判断。"
        "请严格返回 JSON 对象，字段必须是 emotion, credibility, risk_points, misunderstanding_points。"
        "risk_points 和 misunderstanding_points 必须是中文字符串数组，每项 16 到 60 字，最多 4 项。"
        "不要输出 markdown，不要输出 JSON 以外的解释。"
    )
    user_prompt = json.dumps(
        {
            "scene": scene,
            "audience_type": audience_type,
            "content": compact_text(str(payload.get("content") or "")),
            "title": str(payload.get("title") or ""),
            "workspace_label": str(payload.get("workspace_label") or ""),
            "mode_label": str(payload.get("mode_label") or ""),
            "focus_points": payload.get("focus_points") or [],
            "organization_context": organization_context,
            "dna_summary": dna_summary,
            "analysis_options": analysis_options,
            "output_rules": {
                "emotion": "用一句中文判断整体情绪感受，例如：偏强烈/相对克制/容易引发防御感",
                "credibility": "用一句中文判断可信度感受，例如：偏弱/中等/较强",
                "risk_points": "列出最值得优先处理的外部风险点",
                "misunderstanding_points": "列出最容易被外部误读的点",
            },
        },
        ensure_ascii=False,
    )
    return system_prompt, user_prompt


def llm_signal(payload: dict[str, Any], llm_config: dict[str, str]) -> dict[str, Any]:
    system_prompt, user_prompt = build_llm_prompt(payload)
    provider = llm_config["provider"]
    if provider == "qwen":
        parsed = qwen_generate_json(
            api_key=llm_config["api_key"],
            model=llm_config["model"],
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
    else:
        raise RuntimeError(f"unsupported_llm_provider:{provider}")

    return {
        "emotion": str(parsed.get("emotion") or "未返回").strip(),
        "credibility": str(parsed.get("credibility") or "未返回").strip(),
        "risk_points": unique_string_list(normalize_string_list(parsed.get("risk_points"))),
        "misunderstanding_points": unique_string_list(normalize_string_list(parsed.get("misunderstanding_points"))),
        "raw": {
            "source": "llm",
            "model": llm_config["model"],
            "provider": provider,
        },
    }


def qwen_generate_json(*, api_key: str, model: str, system_prompt: str, user_prompt: str) -> dict[str, Any]:
    prompt = (
        "请严格返回一个 JSON 对象，不要使用 Markdown，不要添加解释。"
        "字段必须包含 emotion, credibility, risk_points, misunderstanding_points。"
        f"\n\n{user_prompt}"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "top_p": 0.9,
        "max_tokens": 1200,
        "stream": False,
        "enable_thinking": False,
    }
    with httpx.Client(
        timeout=httpx.Timeout(timeout=None, connect=8.0, read=LLM_TIMEOUT_SECONDS, write=LLM_TIMEOUT_SECONDS, pool=10.0)
    ) as client:
        response = client.post(
            f"{QWEN_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        result = response.json()
    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    return extract_json_object(content or "")


@app.get("/health")
def health():
    llm_config = resolve_workbench_ai_config()
    return jsonify(
        {
            "status": "ok",
            "detail": "llm_configured" if llm_config["ready"] else "heuristic_fallback",
            "repo_dir": str(REPO_DIR),
            "repo_exists": REPO_DIR.exists(),
            "llm_configured": bool(llm_config["ready"]),
            "provider": llm_config["provider"],
            "model": llm_config["model"],
            "credential_source": llm_config["credential_source"],
        }
    )


@app.post("/analyze")
def analyze():
    payload = request.get_json(silent=True) or {}
    content = compact_text(str(payload.get("content") or ""))
    if not content:
        return jsonify({"success": False, "message": "content 不能为空"}), 400

    scene = str(payload.get("scene") or "pr")
    audience_type = str(payload.get("audience_type") or "public")
    llm_config = resolve_workbench_ai_config()

    analysis: dict[str, Any]
    try:
        if llm_config["ready"]:
            analysis = llm_signal(payload, llm_config)
        else:
            analysis = heuristic_signal(content, scene, audience_type)
    except Exception as exc:
        analysis = heuristic_signal(content, scene, audience_type)
        analysis["raw"]["fallback_reason"] = str(exc)

    analysis["generated_at"] = datetime.now(timezone.utc).isoformat()
    return jsonify({"success": True, "data": analysis})


if __name__ == "__main__":
    app.run(host=DEFAULT_HOST, port=DEFAULT_PORT, debug=False)
