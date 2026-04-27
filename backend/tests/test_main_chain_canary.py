from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.main_chain_canary import (  # noqa: E402
    ApiRequestError,
    WaveRunResult,
    compare_idempotency_windows,
    freeze_rc_baseline,
    load_observation_payload,
    recommend_wave1_clients,
    render_value_proof,
    render_value_proof_markdown,
)


def test_compare_idempotency_windows_reports_drift() -> None:
    previous = WaveRunResult(
        label="first",
        client_id="client_demo",
        shadow_off=True,
        job_id="job_first",
        job_status="completed",
        baseline_judgment_id="judgment_a",
        selected_candidate_id="judgment_a",
        analysis_center_counts={
            "evidenceCardCount": 4,
            "themeClusterCount": 2,
            "conflictGroupCount": 1,
            "openQuestionCount": 1,
        },
        hidden_dependency_issues=[],
    )
    rerun = WaveRunResult(
        label="rerun",
        client_id="client_demo",
        shadow_off=True,
        job_id="job_rerun",
        job_status="completed",
        baseline_judgment_id="judgment_b",
        selected_candidate_id="judgment_a",
        analysis_center_counts={
            "evidenceCardCount": 5,
            "themeClusterCount": 2,
            "conflictGroupCount": 1,
            "openQuestionCount": 1,
        },
        hidden_dependency_issues=[],
    )

    issues = compare_idempotency_windows(previous, rerun)

    assert issues == [
        "analysisCenter counts drifted after same-snapshot rerun",
        "baselineJudgment id changed after same-snapshot rerun",
    ]


def test_load_observation_payload_accepts_nested_script_output(tmp_path: Path) -> None:
    path = tmp_path / "wave.json"
    path.write_text(
        """
        {
          "recordedAt": "2026-04-15T18:00:00",
          "observation": {
            "timeRange": "Wave 2 / Day 0",
            "verdict": "pass",
            "conclusion": "Day 0 通过。"
          }
        }
        """,
        encoding="utf-8",
    )

    payload = load_observation_payload(str(path))

    assert payload["timeRange"] == "Wave 2 / Day 0"
    assert payload["verdict"] == "pass"


def test_render_value_proof_markdown_contains_core_sections() -> None:
    observation = {
        "timeRange": "Wave 2 / Day 3",
        "verdict": "watch",
        "conclusion": "指标稳定，继续观察。",
        "fallbackRateBefore": 0.18,
        "fallbackRateAfter": 0.1,
        "resolverMismatchRateBefore": 0.06,
        "resolverMismatchRateAfter": 0.02,
        "approvalBacklog": 2,
        "approvalLagHoursMedian": 6.5,
    }
    manual = {
        "releaseLabel": "v0.3.4 RC",
        "codeCompletionStatus": "pass",
        "runCompletionStatus": "watch",
        "installValidation": {
            "status": "pass",
            "appStarts": True,
            "backendStartedByInstalledApp": True,
            "overviewPanelVisible": True,
            "shadowOffParity": True,
            "workspaceBoundaryCorrect": True,
            "cockpitOfficialLayerToneCorrect": True,
            "overviewMetricsPopulated": True,
            "evidenceScreenshots": {
                "overview": "/tmp/overview.png",
                "workspace": "/tmp/workspace.png",
                "cockpit": "/tmp/cockpit.png",
            },
            "summary": "安装版和源码版行为一致。",
        },
        "judgmentConsistency": {
            "status": "基本稳定",
            "summary": "workspace、任务、会议和 cockpit 大体围绕同一套 judgment/context 说话。",
        },
        "metricsStory": {
            "importReadyTime": "主知识链 ready 更稳定。",
            "idempotencySummary": "重复运行没有膨胀。",
            "approvalSummary": "待确认判断没有明显堆积。",
        },
        "scenes": [
            {
                "name": "客户工作台",
                "before": "以前判断状态混在一起。",
                "after": "现在正式、待确认和提醒分开。",
                "stillNotGoodEnough": "待确认标签还不够醒目。",
                "confirmed": True,
                "evidence": {
                    "sampleId": "client_demo",
                    "screenshotPath": "/tmp/workspace.png",
                    "excerpt": "现在正式、待确认和提醒分开。",
                },
            }
        ],
        "reviewers": [
            {
                "name": "业务同事 A",
                "role": "顾问",
                "feedback": {
                    "boundaryClear": True,
                    "taskContextSharper": True,
                    "meetingCapturesUnresolved": False,
                    "cockpitAvoidsFakeConclusion": True,
                },
                "notes": "状态边界更清楚了。",
            }
        ],
        "nextDecision": {
            "continueObserve": True,
            "canEnterV04": False,
            "blockedBy": ["Wave 2 还未结束"],
        },
    }

    markdown = render_value_proof_markdown(observation=observation, manual=manual)

    assert "# v0.3.4 RC 价值证明结论" in markdown
    assert "## 安装版闭环" in markdown
    assert "## 场景对照" in markdown
    assert "主链判断口径：基本稳定" in markdown
    assert "47829 由安装版自拉起：通过" in markdown
    assert "待确认标签还不够醒目。" in markdown
    assert "客户工作台" in markdown
    assert "样本 client_demo" in markdown
    assert "业务同事 A / 顾问" in markdown
    assert "当前仍待补：Wave 2 还未结束" in markdown


def test_render_value_proof_markdown_marks_incomplete_business_feedback() -> None:
    observation = {
        "timeRange": "Wave 2 / Day 1",
        "verdict": "watch",
        "conclusion": "继续观察。",
        "fallbackRateBefore": 0.1,
        "fallbackRateAfter": 0.08,
        "resolverMismatchRateBefore": 0.02,
        "resolverMismatchRateAfter": 0.01,
        "approvalBacklog": 1,
        "approvalLagHoursMedian": 2.5,
    }
    manual = {
        "releaseLabel": "v0.3.4 RC",
        "codeCompletionStatus": "pass",
        "runCompletionStatus": "watch",
        "installValidation": {
            "status": "pass",
            "appStarts": True,
            "backendStartedByInstalledApp": True,
            "overviewPanelVisible": True,
            "shadowOffParity": True,
            "workspaceBoundaryCorrect": False,
            "cockpitOfficialLayerToneCorrect": False,
            "overviewMetricsPopulated": False,
        },
        "judgmentConsistency": {
            "status": "仍有漂移",
            "summary": "今天不同页面的说法还没有完全对齐。",
        },
        "metricsStory": {},
        "scenes": [],
        "reviewers": [],
        "nextDecision": {},
    }

    markdown = render_value_proof_markdown(observation=observation, manual=manual)

    assert "价值证明状态：尚未具备通过条件" in markdown
    assert "当前还没有业务同事反馈，因此不能判定价值证明通过。" in markdown
    assert "主链判断口径还未达到“稳定”" in markdown


def test_freeze_rc_baseline_contains_single_source_fields(monkeypatch, tmp_path: Path) -> None:
    class FakeApi:
        base_url = "http://127.0.0.1:47929"

        def get_stability_settings(self):
            return {
                "latestJudgmentsShadowOff": True,
                "backfillPaused": False,
                "workerCounters": {"claimCounts": {"backfill": 1}, "lockContention": {}, "backfillThrottle": {}},
                "updatedAt": "2026-04-15T12:00:00",
            }

        def get_metrics(self):
            return {
                "windowDays": 7,
                "newObjectHitRate": 0.82,
                "fallbackRate": 0.08,
                "approvalBacklog": 2,
                "approvalLagHoursMedian": 5.0,
                "candidateReviewWarningCount": 1,
                "candidateReviewOverdueCount": 0,
                "newCandidateUnreviewed24h": 1,
                "resolverMismatchRate": 0.01,
                "pageBreakdown": {},
            }

        def get_settings(self):
            return {
                "settings": {"dataDir": "/tmp/yiyu-data"},
                "health": {"appVersion": "0.1.0", "buildVersion": "2026.04.15", "startedAt": "2026-04-15T08:00:00"},
            }

    monkeypatch.setattr("scripts.main_chain_canary.get_git_commit_sha", lambda: "abc123")
    monkeypatch.setattr(
        "scripts.main_chain_canary.get_git_dirty_worktree_state",
        lambda excluded_paths=None: {"dirtyWorktree": True, "dirtyPaths": ["src/renderer/App.tsx"]},
    )
    monkeypatch.setattr(
        "scripts.main_chain_canary.inspect_installed_app",
        lambda path=None: {"path": "/Users/demo/Applications/益语智库自用平台.app", "exists": True, "rendererEntry": "main-demo.js"},
    )
    monkeypatch.setattr(
        "scripts.main_chain_canary.inspect_installed_runtime_signature",
        lambda base_url="http://127.0.0.1:47929", installed_app=None: {
            "appBundleMTime": "2026-04-16T10:00:00",
            "rendererEntry": "main-demo.js",
            "backendStartedByInstalledApp": True,
            "backendPid": 43129,
            "backendCommand": "/Users/demo/Library/Application Support/YiyuThinkTankWorkbench/runtime/backend-venv/bin/python -m uvicorn app.main:app --port 47929",
        },
    )

    output = tmp_path / "rc-baseline.json"
    payload = freeze_rc_baseline(
        FakeApi(),
        fixed_gate_status="pass",
        full_smoke_summary="16 failed / 68 passed",
        a_class_count=0,
        b_class_summary=["Event-line / task context / cloud task board"],
        c_class_summary=["历史项"],
        notes="baseline note",
        output_path=str(output),
    )

    assert payload["commitSha"] == "abc123"
    assert payload["backendUrl"] == "http://127.0.0.1:47929"
    assert payload["databasePath"].endswith("/tmp/yiyu-data/app.db")
    assert payload["generatedAt"] == payload["recordedAt"]
    assert payload["dirtyWorktree"] is True
    assert payload["dirtyPaths"] == ["src/renderer/App.tsx"]
    assert payload["installedApp"]["rendererEntry"] == "main-demo.js"
    assert payload["installedRuntimeSignature"]["backendStartedByInstalledApp"] is True
    assert payload["installedRuntimeSignature"]["backendPid"] == 43129
    assert payload["fullSmoke"]["summary"] == "16 failed / 68 passed"
    assert payload["classification"]["aClassCount"] == 0
    assert output.exists()
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["generatedAt"] == payload["generatedAt"]
    assert written["dirtyPaths"] == ["src/renderer/App.tsx"]


def test_render_value_proof_writes_markdown_contract(tmp_path: Path) -> None:
    observation_path = tmp_path / "wave2-day0.json"
    observation_path.write_text(
        json.dumps(
            {
                "observation": {
                    "timeRange": "Wave 2 / Day 0",
                    "verdict": "watch",
                    "conclusion": "继续观察。",
                    "fallbackRateBefore": 0.12,
                    "fallbackRateAfter": 0.08,
                    "resolverMismatchRateBefore": 0.03,
                    "resolverMismatchRateAfter": 0.01,
                    "approvalBacklog": 1,
                    "approvalLagHoursMedian": 3.5,
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    manual_path = tmp_path / "manual.json"
    manual_path.write_text(
        json.dumps(
            {
                "releaseLabel": "v0.3.4 RC",
                "codeCompletionStatus": "pass",
                "runCompletionStatus": "watch",
                "installValidation": {
                    "status": "pass",
                    "appStarts": True,
                    "backendStartedByInstalledApp": True,
                    "overviewPanelVisible": True,
                    "shadowOffParity": True,
                    "workspaceBoundaryCorrect": True,
                    "cockpitOfficialLayerToneCorrect": True,
                    "overviewMetricsPopulated": True,
                    "evidenceScreenshots": {
                        "overview": "/tmp/overview.png",
                        "workspace": "/tmp/workspace.png",
                        "cockpit": "/tmp/cockpit.png",
                    },
                },
                "judgmentConsistency": {
                    "status": "稳定",
                    "summary": "四个主链页面围绕同一套 judgment/context 说话。",
                },
                "metricsStory": {},
                "scenes": [],
                "reviewers": [],
                "nextDecision": {},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    output = tmp_path / "value-proof.md"
    rendered = render_value_proof(
        observation_path=str(observation_path),
        manual_path=str(manual_path),
        output_path=str(output),
    )

    assert output.exists()
    assert rendered == output.read_text(encoding="utf-8")
    assert "# v0.3.4 RC 价值证明结论" in rendered
    assert "## 安装版闭环" in rendered
    assert "已排除 main-chain-canary=true 的样本" in rendered
    assert "本轮试跑产生的 canary 样本不计入日常审批积压指标。" in rendered
    assert "主链判断口径：稳定" in rendered
    assert "当前还没有业务同事反馈，因此不能判定价值证明通过。" in rendered


def test_recommend_wave2_skips_clients_with_broken_workspace() -> None:
    class FakeApi:
        base_url = "http://127.0.0.1:47829"

        def get_clients(self):
            return [
                {
                    "id": "client_ok",
                    "name": "可用客户",
                    "lastActivityAt": "2026-04-14T10:00:00",
                    "documentCount": 8,
                    "taskCount": 2,
                },
                {
                    "id": "client_fail",
                    "name": "坏客户",
                    "lastActivityAt": "2026-04-14T09:00:00",
                    "documentCount": 10,
                    "taskCount": 1,
                },
            ]

        def get_workspace(self, client_id: str):
            if client_id == "client_fail":
                raise ApiRequestError(500, "Internal Server Error")
            return {
                "knowledgeStatus": {
                    "pendingJobs": 0,
                    "runningJobs": 0,
                    "lastJobStatus": "completed",
                },
                "documentCards": [{"id": "doc_1"}],
                "meetings": [],
                "relatedTasks": [],
            }

    payload = recommend_wave1_clients(FakeApi(), limit=5, lookback_days=14)

    assert [item["clientId"] for item in payload["recommended"]] == ["client_ok"]
    assert payload["skippedClients"] == [
        {
            "clientId": "client_fail",
            "name": "坏客户",
            "reason": "Internal Server Error",
        }
    ]


def test_runbook_uses_baseline_placeholders_and_no_hard_coded_smoke_numbers() -> None:
    runbook_path = Path(__file__).resolve().parents[2] / "docs" / "main-chain-v0.3.4-rc-runbook.md"
    content = runbook_path.read_text(encoding="utf-8")

    assert "output/main-chain/rc-baseline.json" in content
    assert "http://127.0.0.1:47829" in content
    assert "main_chain_rc_ops.py" in content
    assert "capture-git-artifacts" in content
    assert "write-selection-note" in content
    assert "write-install-note" in content
    assert "write-phase-b-decision" in content
    assert "Day 0 前检查单" in content
    assert "已排除 `main-chain-canary=true` 样本" in content
    assert "runtime/main-chain-rc/v0.3.4" in content
    assert re.search(r"\b\d+\s+failed\s*/\s*\d+\s+passed\b", content) is None

    for match in re.finditer(r'--(?:b|c)-class-summary\s+"([^"]+)"', content):
        assert re.fullmatch(r"<[^>]+>", match.group(1)), match.group(0)
