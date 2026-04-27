from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def load_smoke_module():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "smoke_workspace_chat_generation.py"
    spec = importlib.util.spec_from_file_location("workspace_chat_smoke_script", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("workspace_chat_smoke_script", module)
    spec.loader.exec_module(module)
    return module


def test_poll_async_result_records_terminal_completion_metadata(monkeypatch):
    module = load_smoke_module()
    responses = iter(
        [
            {"status": "running", "phase": "generating"},
            {"status": "loading"},
            {"status": "completed", "phase": "completed"},
            {"status": "success", "answerMode": "grounded_answer"},
        ]
    )

    monkeypatch.setattr(module, "_request_json", lambda *_args, **_kwargs: next(responses))
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    polled = module._poll_async_result(
        "http://127.0.0.1:47829",
        "client_smoke",
        "run_smoke",
        "msg_smoke",
        timeout=1.0,
    )

    assert polled["analysisRunTerminalStatus"] == "completed"
    assert polled["assistantMessageTerminalStatus"] == "success"
    assert polled["completedWithinBudget"] is True
    assert polled["timedOutBeforeTerminal"] is False
    assert polled["observedCompletionMs"] is not None
    assert polled["pollBudgetMs"] == 1000


def test_classify_failure_distinguishes_timeout_and_terminal_failure():
    module = load_smoke_module()

    timeout_class = module._classify_failure(
        [
            {
                "mode": "async",
                "timedOutBeforeTerminal": True,
                "analysisRunTerminalStatus": "running",
                "assistantMessageTerminalStatus": "loading",
            }
        ],
        AssertionError("timed out"),
    )
    terminal_class = module._classify_failure(
        [
            {
                "mode": "async",
                "timedOutBeforeTerminal": False,
                "analysisRunTerminalStatus": "failed",
                "assistantMessageTerminalStatus": "error",
            }
        ],
        AssertionError("terminal failure"),
    )
    assertion_class = module._classify_failure(
        [
            {
                "mode": "async",
                "timedOutBeforeTerminal": False,
                "analysisRunTerminalStatus": "completed",
                "assistantMessageTerminalStatus": "success",
            }
        ],
        AssertionError("assertion failure"),
    )

    assert timeout_class == "timeout_before_terminal"
    assert terminal_class == "terminal_failure"
    assert assertion_class == "assertion_failure"


def test_ensure_client_id_reuses_existing_workspace_smoke_client(monkeypatch):
    module = load_smoke_module()
    calls: list[tuple[str, str]] = []

    def fake_request_json(url, *, method="GET", payload=None):
        calls.append((method, url))
        if url.endswith("/api/v1/clients") and method == "GET":
            return [
                {"id": "client_real", "name": "真实客户", "alias": "real"},
                {"id": "client_smoke_existing", "name": "安装态冒烟客户", "alias": "workspace-smoke"},
            ]
        if url.endswith("/api/v1/clients") and method == "POST":
            raise AssertionError("smoke should reuse the existing workspace-smoke client")
        raise AssertionError(url)

    monkeypatch.setattr(module, "_request_json", fake_request_json)

    assert module._ensure_client_id("http://127.0.0.1:47829", None) == "client_smoke_existing"
    assert calls == [("GET", "http://127.0.0.1:47829/api/v1/clients")]


def test_validate_result_accepts_consultant_synthesis_expectations():
    module = load_smoke_module()
    result = {
        "mode": "sync",
        "rawPayload": {
            "answerMode": "grounded_answer",
            "failureReason": None,
            "content": "日慈基金会是一家聚焦儿童青少年心理健康的公益组织。",
            "retrievalSummary": {
                "dataCenterPrimaryEnabled": True,
                "kernelResultUsed": True,
                "fallbackTemplateUsed": False,
                "workspaceWorkflow": "synthesis",
                "generationMode": "consultant_synthesis",
                "generationProfile": "consultant_synthesis",
                "materialPackProfile": "consultant_synthesis_v1",
                "consultantContextChars": 18000,
            },
        },
    }

    module._validate_result(
        result,
        {
            "workflow": "synthesis",
            "generationMode": "consultant_synthesis",
            "generationProfile": "consultant_synthesis",
            "materialPackProfile": "consultant_synthesis_v1",
            "minConsultantContextChars": 12000,
        },
    )


def test_validate_result_rejects_long_synthesis_when_consultant_expected():
    module = load_smoke_module()
    result = {
        "mode": "sync",
        "rawPayload": {
            "answerMode": "grounded_answer",
            "failureReason": None,
            "content": "回答正文",
            "retrievalSummary": {
                "dataCenterPrimaryEnabled": True,
                "kernelResultUsed": True,
                "fallbackTemplateUsed": False,
                "workspaceWorkflow": "synthesis",
                "generationMode": "long_synthesis",
                "generationProfile": "long",
                "materialPackProfile": None,
                "consultantContextChars": 0,
            },
        },
    }

    try:
        module._validate_result(
            result,
            {
                "workflow": "synthesis",
                "generationMode": "consultant_synthesis",
            },
        )
    except AssertionError as exc:
        assert "generationMode expected" in str(exc)
    else:
        raise AssertionError("expected consultant generation mode assertion")
