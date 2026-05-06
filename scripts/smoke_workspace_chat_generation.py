#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request


BANNED_COPY = [
    "已基于命中的资料生成简版可用回答",
    "完整长文扩写未完成",
    "根据当前已入库资料",
    "可以先这样介绍",
    "正式长回答未完成",
]
ASYNC_TERMINAL_RUN_STATUSES = {"completed", "failed", "canceled"}
ASYNC_TERMINAL_MESSAGE_STATUSES = {"success", "error"}
SMOKE_CLIENT_ALIAS = "workspace-smoke"
SMOKE_CLIENT_NAME = "安装态冒烟客户"


def _request_json(url: str, *, method: str = "GET", payload: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def _write_json(output_path: str | None, payload: dict) -> None:
    if not output_path:
        return
    target = Path(output_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n", encoding="utf-8")


def _default_failure_output_path() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"/tmp/workspace_chat_smoke_{timestamp}.json"


def _utc_now_label() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _ensure_client_id(backend_url: str, client_id: str | None) -> str:
    if client_id:
        return client_id
    clients_payload = _request_json(f"{backend_url}/api/v1/clients")
    if isinstance(clients_payload, list):
        for item in clients_payload:
            if not isinstance(item, dict):
                continue
            alias = str(item.get("alias") or "").strip()
            name = str(item.get("name") or "").strip()
            existing_id = str(item.get("id") or "").strip()
            if existing_id and (alias == SMOKE_CLIENT_ALIAS or name == SMOKE_CLIENT_NAME):
                return existing_id
    payload = _request_json(
        f"{backend_url}/api/v1/clients",
        method="POST",
        payload={
            "name": SMOKE_CLIENT_NAME,
            "alias": SMOKE_CLIENT_ALIAS,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "安装态 workspace chat smoke",
            "stage": "验证中",
        },
    )
    resolved = str(payload.get("id") or "").strip()
    if not resolved:
        raise SystemExit("workspace smoke failed: unable to create smoke client")
    return resolved


def _smoke_sync(backend_url: str, client_id: str, prompt: str) -> dict:
    payload = _request_json(
        f"{backend_url}/api/v1/clients/{client_id}/workspace/chat",
        method="POST",
        payload={"prompt": prompt},
    )
    retrieval_summary = payload.get("retrievalSummary") or {}
    content = str(payload.get("content") or "")
    return {
        "mode": "sync",
        "answerMode": payload.get("answerMode"),
        "failureReason": payload.get("failureReason"),
        "contentPreview": content[:160],
        "retrievalSummary": {
            "dataCenterPrimaryEnabled": retrieval_summary.get("dataCenterPrimaryEnabled"),
            "kernelResultUsed": retrieval_summary.get("kernelResultUsed"),
            "fallbackTemplateUsed": retrieval_summary.get("fallbackTemplateUsed"),
            "finalFailureStage": retrieval_summary.get("finalFailureStage"),
            "llmErrorKind": retrieval_summary.get("llmErrorKind"),
            "generationProfile": retrieval_summary.get("generationProfile"),
            "partialGenerationPreserved": retrieval_summary.get("partialGenerationPreserved"),
            "postFinalizeWarnings": retrieval_summary.get("postFinalizeWarnings"),
            "workspaceWorkflow": retrieval_summary.get("workspaceWorkflow"),
            "generationMode": retrieval_summary.get("generationMode"),
            "materialPackProfile": retrieval_summary.get("materialPackProfile"),
            "consultantContextChars": retrieval_summary.get("consultantContextChars"),
            "materialPackSourceCounts": retrieval_summary.get("materialPackSourceCounts"),
        },
        "rawPayload": payload,
    }


def _normalize_status(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _poll_async_result(
    backend_url: str,
    client_id: str,
    run_id: str,
    assistant_message_id: str,
    *,
    timeout: float = 60.0,
) -> dict:
    started_at = time.perf_counter()
    deadline = time.time() + timeout
    latest_run: dict = {}
    latest_message: dict = {}
    while time.time() < deadline:
        latest_run = _request_json(f"{backend_url}/api/v1/clients/{client_id}/analysis-runs/{run_id}")
        latest_message = _request_json(
            f"{backend_url}/api/v1/clients/{client_id}/workspace/chat/messages/{assistant_message_id}"
        )
        run_status = _normalize_status(latest_run.get("status"))
        message_status = _normalize_status(latest_message.get("status"))
        if run_status in ASYNC_TERMINAL_RUN_STATUSES and message_status in ASYNC_TERMINAL_MESSAGE_STATUSES:
            observed_completion_ms = int(round((time.perf_counter() - started_at) * 1000))
            return {
                "analysisRun": latest_run,
                "assistantMessage": latest_message,
                "analysisRunTerminalStatus": run_status,
                "assistantMessageTerminalStatus": message_status,
                "observedCompletionMs": observed_completion_ms,
                "observedPollElapsedMs": observed_completion_ms,
                "pollBudgetMs": int(round(timeout * 1000)),
                "completedWithinBudget": True,
                "timedOutBeforeTerminal": False,
            }
        time.sleep(0.2)
    observed_poll_elapsed_ms = int(round((time.perf_counter() - started_at) * 1000))
    return {
        "analysisRun": latest_run,
        "assistantMessage": latest_message,
        "analysisRunTerminalStatus": _normalize_status(latest_run.get("status")),
        "assistantMessageTerminalStatus": _normalize_status(latest_message.get("status")),
        "observedCompletionMs": None,
        "observedPollElapsedMs": observed_poll_elapsed_ms,
        "pollBudgetMs": int(round(timeout * 1000)),
        "completedWithinBudget": False,
        "timedOutBeforeTerminal": True,
    }


def _classify_failure(results: list[dict], error: Exception) -> str:
    async_result = next((item for item in results if item.get("mode") == "async"), None)
    if async_result:
        if async_result.get("timedOutBeforeTerminal") is True:
            return "timeout_before_terminal"
        if async_result.get("analysisRunTerminalStatus") in {"failed", "canceled"}:
            return "terminal_failure"
        if async_result.get("assistantMessageTerminalStatus") == "error":
            return "terminal_failure"
    return "assertion_failure"


def _smoke_async(backend_url: str, client_id: str, prompt: str, *, timeout: float = 60.0) -> dict:
    started = _request_json(
        f"{backend_url}/api/v1/clients/{client_id}/workspace/chat/start",
        method="POST",
        payload={"prompt": prompt},
    )
    assistant = started.get("assistantMessage") or {}
    analysis_run = started.get("analysisRun") or {}
    run_id = str(analysis_run.get("id") or "")
    assistant_message_id = str(assistant.get("id") or "")
    if not run_id or not assistant_message_id:
        raise SystemExit("workspace async smoke failed: missing analysis run or assistant message id")
    poll_state = _poll_async_result(backend_url, client_id, run_id, assistant_message_id, timeout=timeout)
    final_run = poll_state["analysisRun"]
    final_message = poll_state["assistantMessage"]
    retrieval_summary = final_message.get("retrievalSummary") or {}
    content = str(final_message.get("content") or "")
    return {
        "mode": "async",
        "startAccepted": True,
        "answerMode": final_message.get("answerMode"),
        "failureReason": final_message.get("failureReason"),
        "contentPreview": content[:160],
        "analysisRun": {
            "id": run_id,
            "status": final_run.get("status"),
            "phase": final_run.get("phase"),
            "failureReason": final_run.get("failureReason"),
        },
        "analysisRunTerminalStatus": poll_state.get("analysisRunTerminalStatus"),
        "assistantMessageTerminalStatus": poll_state.get("assistantMessageTerminalStatus"),
        "observedCompletionMs": poll_state.get("observedCompletionMs"),
        "observedPollElapsedMs": poll_state.get("observedPollElapsedMs"),
        "pollBudgetMs": poll_state.get("pollBudgetMs"),
        "completedWithinBudget": poll_state.get("completedWithinBudget"),
        "timedOutBeforeTerminal": poll_state.get("timedOutBeforeTerminal"),
        "retrievalSummary": {
            "dataCenterPrimaryEnabled": retrieval_summary.get("dataCenterPrimaryEnabled"),
            "kernelResultUsed": retrieval_summary.get("kernelResultUsed"),
            "fallbackTemplateUsed": retrieval_summary.get("fallbackTemplateUsed"),
            "finalFailureStage": retrieval_summary.get("finalFailureStage"),
            "llmErrorKind": retrieval_summary.get("llmErrorKind"),
            "generationProfile": retrieval_summary.get("generationProfile"),
            "partialGenerationPreserved": retrieval_summary.get("partialGenerationPreserved"),
            "postFinalizeWarnings": retrieval_summary.get("postFinalizeWarnings"),
            "workspaceWorkflow": retrieval_summary.get("workspaceWorkflow"),
            "generationMode": retrieval_summary.get("generationMode"),
            "materialPackProfile": retrieval_summary.get("materialPackProfile"),
            "consultantContextChars": retrieval_summary.get("consultantContextChars"),
            "materialPackSourceCounts": retrieval_summary.get("materialPackSourceCounts"),
        },
        "rawPayload": final_message,
    }


def _expectation_payload(args: argparse.Namespace) -> dict:
    return {
        "workflow": args.expect_workflow,
        "generationMode": args.expect_generation_mode,
        "generationProfile": args.expect_generation_profile,
        "materialPackProfile": args.expect_material_pack_profile,
        "minConsultantContextChars": args.min_consultant_context_chars,
    }


def _ai_unconfigured_reason(health: dict) -> str | None:
    ai = health.get("ai") if isinstance(health.get("ai"), dict) else {}
    provider = str(ai.get("provider") or "").strip()
    ready = bool(ai.get("ready"))
    fingerprint = str(ai.get("fingerprint") or "").strip()
    if provider == "mock":
        return "未配置真实大模型，workspace chat 生成 smoke 已按预期跳过。"
    if not ready:
        return str(ai.get("detail") or "大模型未配置完成，workspace chat 生成 smoke 已跳过。")
    if not fingerprint:
        return "大模型 API Key 未配置，workspace chat 生成 smoke 已跳过。"
    return None


def _validate_result(result: dict, expectations: dict | None = None) -> None:
    expectations = expectations or {}
    payload = result.get("rawPayload") or {}
    retrieval_summary = payload.get("retrievalSummary") or {}
    content = str(payload.get("content") or "")
    if result.get("mode") == "async":
        assert result.get("startAccepted") is True
        assert result.get("completedWithinBudget") is True
        assert result.get("analysisRunTerminalStatus") == "completed"
        assert result.get("assistantMessageTerminalStatus") == "success"
    assert retrieval_summary.get("dataCenterPrimaryEnabled") is True
    assert retrieval_summary.get("kernelResultUsed") is True
    assert retrieval_summary.get("fallbackTemplateUsed") is False
    for phrase in BANNED_COPY:
        assert phrase not in content, phrase

    answer_mode = payload.get("answerMode")
    failure_reason = payload.get("failureReason")
    if answer_mode == "grounded_fallback":
        assert failure_reason != "llm_local_fallback_after_retry"
    if answer_mode == "system_failure":
        assert failure_reason in {"llm_generation_failed", "quality_gate_blocked"}

    expected_workflow = expectations.get("workflow")
    if expected_workflow:
        assert retrieval_summary.get("workspaceWorkflow") == expected_workflow, (
            f"workspaceWorkflow expected {expected_workflow!r}, got {retrieval_summary.get('workspaceWorkflow')!r}"
        )
    expected_generation_mode = expectations.get("generationMode")
    if expected_generation_mode:
        assert retrieval_summary.get("generationMode") == expected_generation_mode, (
            f"generationMode expected {expected_generation_mode!r}, got {retrieval_summary.get('generationMode')!r}"
        )
    expected_generation_profile = expectations.get("generationProfile")
    if expected_generation_profile:
        assert retrieval_summary.get("generationProfile") == expected_generation_profile, (
            f"generationProfile expected {expected_generation_profile!r}, got {retrieval_summary.get('generationProfile')!r}"
        )
    expected_material_pack_profile = expectations.get("materialPackProfile")
    if expected_material_pack_profile:
        assert retrieval_summary.get("materialPackProfile") == expected_material_pack_profile, (
            f"materialPackProfile expected {expected_material_pack_profile!r}, got {retrieval_summary.get('materialPackProfile')!r}"
        )
    min_context_chars = int(expectations.get("minConsultantContextChars") or 0)
    if min_context_chars > 0:
        actual_chars = int(retrieval_summary.get("consultantContextChars") or 0)
        assert actual_chars >= min_context_chars, (
            f"consultantContextChars expected >= {min_context_chars}, got {actual_chars}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend-url", default="http://127.0.0.1:47829")
    parser.add_argument("--client-id")
    parser.add_argument("--prompt", default="帮我找上次会议纪要原文")
    parser.add_argument("--output")
    parser.add_argument("--mode", choices=("sync", "async", "both"), default="both")
    parser.add_argument("--async-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--expect-workflow")
    parser.add_argument("--expect-generation-mode")
    parser.add_argument("--expect-generation-profile")
    parser.add_argument("--expect-material-pack-profile")
    parser.add_argument("--min-consultant-context-chars", type=int, default=0)
    args = parser.parse_args()

    backend_url = args.backend_url.rstrip("/")
    health = _request_json(f"{backend_url}/api/v1/system/health")
    ai_unconfigured_reason = _ai_unconfigured_reason(health)
    if ai_unconfigured_reason:
        result = {
            "recordedAt": _utc_now_label(),
            "clientId": args.client_id,
            "bundleManifestId": health.get("bundleManifestId"),
            "buildVersion": health.get("buildVersion"),
            "ready": True,
            "readyToOpenWorkbench": True,
            "mode": args.mode,
            "chatSmokeSkipped": True,
            "skipReason": ai_unconfigured_reason,
            "ai": health.get("ai"),
        }
        _write_json(args.output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    client_id = _ensure_client_id(backend_url, args.client_id)
    expectations = _expectation_payload(args)
    results: list[dict] = []
    try:
        if args.mode in {"sync", "both"}:
            sync_result = _smoke_sync(backend_url, client_id, args.prompt)
            _validate_result(sync_result, expectations)
            results.append(sync_result)
        if args.mode in {"async", "both"}:
            async_result = _smoke_async(backend_url, client_id, args.prompt, timeout=args.async_timeout_seconds)
            _validate_result(async_result, expectations)
            results.append(async_result)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="ignore")
        raise SystemExit(f"workspace chat request failed: {error.code} {detail}") from error
    except Exception as error:
        debug_payload = {
            "recordedAt": _utc_now_label(),
            "clientId": client_id,
            "bundleManifestId": health.get("bundleManifestId"),
            "buildVersion": health.get("buildVersion"),
            "ready": False,
            "readyToOpenWorkbench": False,
            "mode": args.mode,
            "prompt": args.prompt,
            "expectations": expectations,
            "failureClass": _classify_failure(results, error),
            "partialResults": results,
            "error": str(error),
        }
        target = args.output or _default_failure_output_path()
        _write_json(target, debug_payload)
        raise

    result = {
        "recordedAt": _utc_now_label(),
        "clientId": client_id,
        "bundleManifestId": health.get("bundleManifestId"),
        "buildVersion": health.get("buildVersion"),
        "ready": True,
        "readyToOpenWorkbench": True,
        "mode": args.mode,
        "expectations": expectations,
        "results": [
            {
                "mode": item["mode"],
                "answerMode": item["answerMode"],
                "failureReason": item["failureReason"],
                "contentPreview": item["contentPreview"],
                "retrievalSummary": item["retrievalSummary"],
                "analysisRun": item.get("analysisRun"),
                "startAccepted": item.get("startAccepted"),
                "analysisRunTerminalStatus": item.get("analysisRunTerminalStatus"),
                "assistantMessageTerminalStatus": item.get("assistantMessageTerminalStatus"),
                "observedCompletionMs": item.get("observedCompletionMs"),
                "observedPollElapsedMs": item.get("observedPollElapsedMs"),
                "pollBudgetMs": item.get("pollBudgetMs"),
                "completedWithinBudget": item.get("completedWithinBudget"),
            }
            for item in results
        ],
    }
    _write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
