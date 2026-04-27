from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.main_chain_rc_contract import (  # noqa: E402
    attach_artifact_contract,
    default_rc_session,
    ensure_baseline_contract,
    write_rc_session,
)
from scripts.main_chain_rc_ops import (  # noqa: E402
    assess_day0_candidates,
    capture_git_artifacts,
    run_preflight,
    verify_db_isolation,
    write_invalidated_artifacts_note,
    write_install_evidence,
    write_install_note,
    write_observation_note,
    write_phase_b_decision,
    write_full_smoke_classification,
    write_selection_note,
)


def _baseline_payload(database_path: str) -> dict[str, Any]:
    return ensure_baseline_contract(
        {
            "generatedAt": "2026-04-16T10:00:00",
            "commitSha": "baseline-sha",
            "backendUrl": "http://127.0.0.1:47829",
            "databasePath": database_path,
            "latestJudgmentsShadowOff": True,
            "dirtyWorktree": False,
            "dirtyPaths": [],
            "installedRuntimeSignature": {
                "appBundleMTime": "2026-04-16T10:00:00",
                "rendererEntry": "main-demo.js",
                "backendStartedByInstalledApp": True,
                "backendPid": 12345,
            },
            "health": {"buildVersion": "2026.04.16-rc"},
            "mainChainStability": {"latestJudgmentsShadowOff": True},
        }
    )


def _write_baseline(path: Path, database_path: str) -> dict[str, Any]:
    baseline = _baseline_payload(database_path)
    path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    return baseline


def _write_session(runtime_dir: Path, baseline: dict[str, Any], baseline_path: Path, state: str = "baseline_frozen") -> None:
    session = default_rc_session(
        baseline_path=str(baseline_path.resolve()),
        session_id=str(baseline["sessionId"]),
    )
    session.update(
        {
            "state": state,
            "baselineHash": baseline["baselineHash"],
            "tupleHash": baseline["tupleHash"],
            "baselinePath": str(baseline_path.resolve()),
        }
    )
    write_rc_session(session, runtime_dir=runtime_dir)


def _write_page_proof(path: Path, baseline: dict[str, Any], page: str) -> None:
    payload = attach_artifact_contract(
        {
            "page": page,
            "screenshotPath": f"/tmp/{page}.png",
            "expectedTokens": ["token"],
            "observedTokens": ["token"],
            "matchedTokens": ["token"],
            "missingTokens": [],
            "decision": "pass",
            "reason": "all expected tokens observed",
            "recordedAt": "2026-04-18T12:00:00",
        },
        baseline,
    )
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_run_preflight_reports_identity_mismatch(monkeypatch, tmp_path: Path) -> None:
    database_path = str((Path("/tmp/demo") / "app.db").resolve())
    baseline_path = tmp_path / "rc-baseline.json"
    baseline = _write_baseline(baseline_path, database_path)
    runtime_dir = tmp_path / "runtime"
    _write_session(runtime_dir, baseline, baseline_path, state="baseline_frozen")

    class FakeApi:
        base_url = "http://127.0.0.1:47829"

        def get_stability_settings(self):
            return {
                "latestJudgmentsShadowOff": True,
                "backfillPaused": False,
            }

        def get_metrics(self):
            return {
                "windowDays": 7,
                "fallbackRate": 0.0,
                "resolverMismatchRate": 0.0,
            }

        def get_settings(self):
            return {
                "settings": {"dataDir": "/tmp/demo"},
                "health": {"buildVersion": "2026.04.16-hotfix"},
            }

    monkeypatch.setattr("scripts.main_chain_rc_ops.get_git_commit_sha", lambda: "current-sha")
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.get_git_dirty_worktree_state",
        lambda excluded_paths=None: {"dirtyWorktree": True, "dirtyPaths": ["src/renderer/App.tsx"]},
    )
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.inspect_installed_app",
        lambda path=None: {"path": "/Users/demo/Applications/益语智库自用平台.app", "exists": True, "modifiedAt": "2026-04-16T10:00:00", "rendererEntry": "main-demo.js"},
    )
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.inspect_installed_runtime_signature",
        lambda base_url="http://127.0.0.1:47829", installed_app=None: {
            "appBundleMTime": "2026-04-16T10:00:00",
            "rendererEntry": "main-demo.js",
            "backendStartedByInstalledApp": False,
            "backendPid": 12345,
            "backendCommand": "/tmp/demo/python -m uvicorn app.main:app --port 47829",
        },
    )

    with pytest.raises(RuntimeError, match="tupleHash"):
        run_preflight(FakeApi(), baseline_path=str(baseline_path), runtime_dir=str(runtime_dir))

    invalidated = json.loads((runtime_dir / "invalidated-artifacts.note.json").read_text(encoding="utf-8"))
    session = json.loads((runtime_dir / "rc-session.json").read_text(encoding="utf-8"))
    assert invalidated["invalidatedBaselineHash"] == baseline["baselineHash"]
    assert invalidated["invalidatedSessionId"] == baseline["sessionId"]
    assert session["state"] == "pre_baseline"


def test_verify_db_isolation_confirms_tmp_path_tests_and_live_app_db(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    tests_root = repo_root / "backend" / "tests"
    tests_root.mkdir(parents=True, exist_ok=True)
    (tests_root / "test_api_smoke.py").write_text(
        'from app.main import create_app\napp = create_app(tmp_path / "data")\n',
        encoding="utf-8",
    )
    (tests_root / "test_analysis_main_chain.py").write_text(
        'from app.main import create_app\napp = create_app(tmp_path / "data")\n',
        encoding="utf-8",
    )
    (tests_root / "test_tmp_db.py").write_text(
        'from app.db import Database\ndb = Database(tmp_path / "app.db")\n',
        encoding="utf-8",
    )
    home_dir = tmp_path / "home"
    live_db_path = home_dir / "Library" / "Application Support" / "YiyuThinkTankWorkbench" / "app.db"
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.collect_runtime_identity",
        lambda api, baseline_path=None: {"databasePath": str(live_db_path.resolve())},
    )

    class FakeApi:
        base_url = "http://127.0.0.1:47829"

    payload = verify_db_isolation(
        FakeApi(),
        repo_root=repo_root,
        home_dir=home_dir,
        output_path=str(tmp_path / "db-isolation-check.json"),
    )

    assert payload["readyForBaselineRegeneration"] is True
    assert payload["liveDatabaseMatchesInstalledRuntime"] is True
    assert payload["temporaryDbPatternHits"] == ["backend/tests/test_tmp_db.py"]
    assert all(item["found"] is True for item in payload["requiredTestEvidence"])


def test_verify_db_isolation_blocks_when_static_evidence_is_incomplete(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    tests_root = repo_root / "backend" / "tests"
    tests_root.mkdir(parents=True, exist_ok=True)
    (tests_root / "test_api_smoke.py").write_text("app = object()\n", encoding="utf-8")
    (tests_root / "test_analysis_main_chain.py").write_text("app = object()\n", encoding="utf-8")
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.collect_runtime_identity",
        lambda api, baseline_path=None: {"databasePath": "/tmp/other/app.db"},
    )

    class FakeApi:
        base_url = "http://127.0.0.1:47829"

    payload = verify_db_isolation(
        FakeApi(),
        repo_root=repo_root,
        home_dir=tmp_path / "home",
        output_path=str(tmp_path / "db-isolation-check.json"),
    )

    assert payload["readyForBaselineRegeneration"] is False
    assert payload["liveDatabaseMatchesInstalledRuntime"] is False
    assert any("apiSmokeUsesTmpDataDir" in item for item in payload["missingEvidence"])
    assert any('Database(tmp_path / "app.db")' in item for item in payload["missingEvidence"])


def test_assess_day0_candidates_selects_representative_clients_and_control_client() -> None:
    class FakeApi:
        base_url = "http://127.0.0.1:47829"

        def __init__(self) -> None:
            self.workspaces = {
                "client_cffc": {
                    "knowledgeStatus": {"pendingJobs": 0, "runningJobs": 0, "lastJobStatus": "completed", "totalDocuments": 8},
                    "documentCards": [{"id": "doc_1"}, {"id": "doc_2"}, {"id": "doc_3"}],
                    "meetings": [{"id": "meeting_1"}],
                    "relatedTasks": [{"id": "task_1", "eventLineId": "eline_1"}],
                },
                "client_a4d1db29a7": {
                    "knowledgeStatus": {"pendingJobs": 0, "runningJobs": 0, "lastJobStatus": "completed", "totalDocuments": 6},
                    "documentCards": [{"id": "doc_1"}, {"id": "doc_2"}, {"id": "doc_3"}],
                    "meetings": [],
                    "relatedTasks": [],
                },
                "client_53d82aa249": {
                    "knowledgeStatus": {"pendingJobs": 0, "runningJobs": 0, "lastJobStatus": "completed", "totalDocuments": 1},
                    "documentCards": [{"id": "doc_1"}],
                    "meetings": [{"id": "meeting_1"}],
                    "relatedTasks": [],
                },
                "client_284afd836e": {
                    "knowledgeStatus": {"pendingJobs": 0, "runningJobs": 0, "lastJobStatus": "completed", "totalDocuments": 4},
                    "documentCards": [{"id": "doc_1"}, {"id": "doc_2"}],
                    "meetings": [],
                    "relatedTasks": [],
                },
            }
            self.cockpits = {
                "client_cffc": {
                    "officialLayerStatus": "ready",
                    "radarLayer": {"candidateJudgments": [{"id": "judgment_1"}]},
                },
                "client_a4d1db29a7": {
                    "officialLayerStatus": "empty",
                    "radarLayer": {"candidateJudgments": [{"id": "judgment_1"}]},
                },
                "client_53d82aa249": {
                    "officialLayerStatus": "empty",
                    "radarLayer": {"candidateJudgments": []},
                },
                "client_284afd836e": {
                    "officialLayerStatus": "ready",
                    "radarLayer": {"candidateJudgments": []},
                },
            }

        def get_workspace(self, client_id: str):
            return self.workspaces[client_id]

        def get_cockpit(self, client_id: str):
            return self.cockpits[client_id]

    payload = assess_day0_candidates(
        FakeApi(),
        candidate_ids=["client_cffc", "client_a4d1db29a7", "client_53d82aa249", "client_284afd836e"],
    )

    assert payload["selectedClients"] == ["client_cffc", "client_a4d1db29a7", "client_53d82aa249"]
    assert payload["representationReady"] is True
    assert payload["controlClientId"] == "client_cffc"
    assert set(payload["representedCategories"]) == {"documents", "meetings_or_event_lines", "cockpit"}


def test_write_observation_note_writes_sidecar_with_required_fields(monkeypatch, tmp_path: Path) -> None:
    database_path = str((Path("/tmp/demo") / "app.db").resolve())
    baseline_path = tmp_path / "rc-baseline.json"
    baseline = _write_baseline(baseline_path, database_path)
    runtime_dir = tmp_path / "runtime"
    _write_session(runtime_dir, baseline, baseline_path, state="wave2_active")
    observation_path = tmp_path / "wave2-day1.json"
    observation_path.write_text(json.dumps(attach_artifact_contract({}, baseline), ensure_ascii=False), encoding="utf-8")

    class FakeApi:
        base_url = "http://127.0.0.1:47829"

        def get_stability_settings(self):
            return {
                "latestJudgmentsShadowOff": True,
                "backfillPaused": False,
            }

        def get_metrics(self):
            return {"windowDays": 7}

        def get_settings(self):
            return {
                "settings": {"dataDir": "/tmp/demo"},
                "health": {"buildVersion": "2026.04.16-rc"},
            }

    monkeypatch.setattr("scripts.main_chain_rc_ops.get_git_commit_sha", lambda: "baseline-sha")
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.get_git_dirty_worktree_state",
        lambda excluded_paths=None: {"dirtyWorktree": False, "dirtyPaths": []},
    )
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.inspect_installed_app",
        lambda path=None: {"path": "/Users/demo/Applications/益语智库自用平台.app", "exists": True, "modifiedAt": "2026-04-16T10:00:00", "rendererEntry": "main-demo.js"},
    )
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.inspect_installed_runtime_signature",
        lambda base_url="http://127.0.0.1:47829", installed_app=None: {
            "appBundleMTime": "2026-04-16T10:00:00",
            "rendererEntry": "main-demo.js",
            "backendStartedByInstalledApp": True,
            "backendPid": 12345,
            "backendCommand": "/tmp/demo/python -m uvicorn app.main:app --port 47829",
        },
    )

    payload = write_observation_note(
        FakeApi(),
        baseline_path=str(baseline_path),
        runtime_dir=str(runtime_dir),
        observation_path=str(observation_path),
        control_client_id="client_cffc",
        operator_note="今天指标正常，但安装版首屏比源码版慢一点。",
        output_path=None,
    )

    sidecar_path = tmp_path / "wave2-day1.note.json"
    assert sidecar_path.exists()
    assert payload["baselineGeneratedAt"] == "2026-04-16T10:00:00"
    assert payload["controlClientId"] == "client_cffc"
    assert payload["operatorNote"] == "今天指标正常，但安装版首屏比源码版慢一点。"
    assert payload["identityMatchesBaseline"] is True
    assert payload["installedRuntimeSignature"]["backendStartedByInstalledApp"] is True
    assert payload["baselineHash"] == baseline["baselineHash"]


def test_write_install_evidence_writes_default_phase_file(monkeypatch, tmp_path: Path) -> None:
    database_path = str((Path("/tmp/demo") / "app.db").resolve())
    baseline_path = tmp_path / "rc-baseline.json"
    baseline = _write_baseline(baseline_path, database_path)
    runtime_dir = tmp_path / "runtime"
    _write_session(runtime_dir, baseline, baseline_path, state="baseline_frozen")
    overview_proof = tmp_path / "page-proof-overview.json"
    workspace_proof = tmp_path / "page-proof-workspace-state.json"
    cockpit_proof = tmp_path / "page-proof-cockpit.json"
    _write_page_proof(overview_proof, baseline, "overview")
    _write_page_proof(workspace_proof, baseline, "workspace-state")
    _write_page_proof(cockpit_proof, baseline, "cockpit")

    class FakeApi:
        base_url = "http://127.0.0.1:47829"

        def get_stability_settings(self):
            return {
                "latestJudgmentsShadowOff": True,
                "backfillPaused": False,
            }

        def get_metrics(self):
            return {"windowDays": 7}

        def get_settings(self):
            return {
                "settings": {"dataDir": "/tmp/demo"},
                "health": {"buildVersion": "2026.04.16-rc"},
            }

    monkeypatch.setattr("scripts.main_chain_rc_ops.get_git_commit_sha", lambda: "baseline-sha")
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.get_git_dirty_worktree_state",
        lambda excluded_paths=None: {"dirtyWorktree": False, "dirtyPaths": []},
    )
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.inspect_installed_app",
        lambda path=None: {"path": "/Users/demo/Applications/益语智库自用平台.app", "exists": True, "modifiedAt": "2026-04-16T10:00:00", "rendererEntry": "main-demo.js"},
    )
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.inspect_installed_runtime_signature",
        lambda base_url="http://127.0.0.1:47829", installed_app=None: {
            "appBundleMTime": "2026-04-16T10:00:00",
            "rendererEntry": "main-demo.js",
            "backendStartedByInstalledApp": True,
            "backendPid": 12345,
            "backendCommand": "/tmp/demo/python -m uvicorn app.main:app --port 47829",
        },
    )

    output = tmp_path / "install-step-a.json"
    payload = write_install_evidence(
        FakeApi(),
        baseline_path=str(baseline_path),
        runtime_dir=str(runtime_dir),
        phase="step-a",
        status="pass",
        app_starts=True,
        backend_started_by_installed_app=True,
        overview_panel_visible=True,
        shadow_off_parity=True,
        workspace_boundary_correct=True,
        cockpit_official_layer_tone_correct=True,
        overview_metrics_populated=True,
        overview_screenshot="/tmp/overview.png",
        workspace_screenshot="/tmp/workspace.png",
        cockpit_screenshot="/tmp/cockpit.png",
        overview_page_proof=str(overview_proof),
        workspace_page_proof=str(workspace_proof),
        cockpit_page_proof=str(cockpit_proof),
        summary="安装版 Step A 已取到机器证据。",
        manual_backend_recovery_used=False,
        workaround_required=False,
        control_client_id=None,
        output_path=str(output),
    )

    assert output.exists()
    assert payload["backendStartedByInstalledApp"] is True
    assert payload["workspaceBoundaryCorrect"] is True
    assert payload["cockpitOfficialLayerToneCorrect"] is True
    assert payload["overviewMetricsPopulated"] is True
    assert payload["screenshots"]["workspace"] == "/tmp/workspace.png"
    assert payload["identityMatchesBaseline"] is True
    assert payload["pageProofs"]["workspace"] == str(workspace_proof.resolve())


def test_write_install_evidence_step_a_pass_rejects_manual_backend_recovery(monkeypatch, tmp_path: Path) -> None:
    database_path = str((Path("/tmp/demo") / "app.db").resolve())
    baseline_path = tmp_path / "rc-baseline.json"
    baseline = _write_baseline(baseline_path, database_path)
    runtime_dir = tmp_path / "runtime"
    _write_session(runtime_dir, baseline, baseline_path, state="baseline_frozen")
    overview_proof = tmp_path / "page-proof-overview.json"
    workspace_proof = tmp_path / "page-proof-workspace-state.json"
    cockpit_proof = tmp_path / "page-proof-cockpit.json"
    _write_page_proof(overview_proof, baseline, "overview")
    _write_page_proof(workspace_proof, baseline, "workspace-state")
    _write_page_proof(cockpit_proof, baseline, "cockpit")

    class FakeApi:
        base_url = "http://127.0.0.1:47829"

        def get_stability_settings(self):
            return {"latestJudgmentsShadowOff": True, "backfillPaused": False}

        def get_metrics(self):
            return {"windowDays": 7}

        def get_settings(self):
            return {"settings": {"dataDir": "/tmp/demo"}, "health": {"buildVersion": "2026.04.16-rc"}}

    monkeypatch.setattr("scripts.main_chain_rc_ops.get_git_commit_sha", lambda: "baseline-sha")
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.get_git_dirty_worktree_state",
        lambda excluded_paths=None: {"dirtyWorktree": False, "dirtyPaths": []},
    )
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.inspect_installed_app",
        lambda path=None: {"path": "/Users/demo/Applications/益语智库自用平台.app", "exists": True, "modifiedAt": "2026-04-16T10:00:00", "rendererEntry": "main-demo.js"},
    )
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.inspect_installed_runtime_signature",
        lambda base_url="http://127.0.0.1:47829", installed_app=None: {
            "appBundleMTime": "2026-04-16T10:00:00",
            "rendererEntry": "main-demo.js",
            "backendStartedByInstalledApp": True,
            "backendPid": 12345,
            "backendCommand": "/tmp/demo/python -m uvicorn app.main:app --port 47829",
        },
    )

    with pytest.raises(RuntimeError, match="manual backend recovery or extra workaround"):
        write_install_evidence(
            FakeApi(),
            baseline_path=str(baseline_path),
            runtime_dir=str(runtime_dir),
            phase="step-a",
            status="pass",
            app_starts=True,
            backend_started_by_installed_app=True,
            overview_panel_visible=True,
            shadow_off_parity=True,
            workspace_boundary_correct=True,
            cockpit_official_layer_tone_correct=True,
            overview_metrics_populated=True,
            overview_screenshot="/tmp/overview.png",
            workspace_screenshot="/tmp/workspace.png",
            cockpit_screenshot="/tmp/cockpit.png",
            overview_page_proof=str(overview_proof),
            workspace_page_proof=str(workspace_proof),
            cockpit_page_proof=str(cockpit_proof),
            summary="安装版虽然启动，但靠人工救活 backend。",
            manual_backend_recovery_used=True,
            workaround_required=False,
            control_client_id=None,
            output_path=str(tmp_path / "install-step-a.json"),
        )


def test_capture_git_artifacts_writes_expected_files(monkeypatch, tmp_path: Path) -> None:
    outputs = {
        ("git", "-C", str(tmp_path), "rev-parse", "HEAD"): "abc123\n",
        ("git", "-C", str(tmp_path), "status", "--porcelain"): " M backend/scripts/main_chain_rc_ops.py\n",
        ("git", "-C", str(tmp_path), "diff", "--stat"): " 1 file changed, 10 insertions(+)\n",
        ("git", "-C", str(tmp_path), "diff"): "diff --git a/file b/file\n",
    }

    def fake_run_command(command, cwd=None):
        return 0, outputs[tuple(command)], ""

    monkeypatch.setattr("scripts.main_chain_rc_ops._run_command", fake_run_command)

    payload = capture_git_artifacts(runtime_dir=tmp_path / "rc", repo_root=tmp_path)

    assert Path(payload["artifacts"]["head.txt"]).read_text(encoding="utf-8") == "abc123\n"
    assert Path(payload["artifacts"]["status.porcelain.txt"]).read_text(encoding="utf-8") == " M backend/scripts/main_chain_rc_ops.py\n"
    assert Path(payload["artifacts"]["diff.stat.txt"]).read_text(encoding="utf-8") == " 1 file changed, 10 insertions(+)\n"
    assert Path(payload["artifacts"]["diff.patch"]).read_text(encoding="utf-8") == "diff --git a/file b/file\n"


def test_write_selection_note_captures_selected_and_rejected_reasons(tmp_path: Path) -> None:
    baseline_path = tmp_path / "rc-baseline.json"
    baseline = _write_baseline(baseline_path, str((Path("/tmp/demo") / "app.db").resolve()))
    runtime_dir = tmp_path / "runtime"
    _write_session(runtime_dir, baseline, baseline_path, state="day0_ready")
    selection_path = tmp_path / "day0-selection.json"
    selection_path.write_text(
        json.dumps(
            attach_artifact_contract(
            {
                "controlClientId": "client_cffc",
                "controlClientReason": "选为 control client。",
                "readyForDay0": True,
                "representedCategories": ["documents", "cockpit"],
                "assessments": [
                    {
                        "clientId": "client_cffc",
                        "selected": True,
                        "selectionReason": "入选：健康，且补齐 cockpit 代表性",
                        "healthReason": "候选健康：workspace/cockpit 200",
                        "representationReason": "补齐 cockpit 代表性",
                    },
                    {
                        "clientId": "client_cb720fc373",
                        "selected": False,
                        "selectionReason": "淘汰：knowledgeReady=false",
                        "healthReason": "淘汰：knowledgeReady=false",
                        "representationReason": "具备 cockpit 代表性，但未通过健康门槛",
                    },
                ],
            },
            baseline,
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = write_selection_note(
        baseline_path=str(baseline_path),
        runtime_dir=str(runtime_dir),
        selection_path=str(selection_path),
        output_path=None,
    )

    note_path = tmp_path / "day0-selection.note.json"
    assert note_path.exists()
    assert payload["controlClientId"] == "client_cffc"
    assert payload["installedRuntimeSignature"]["backendStartedByInstalledApp"] is True
    assert payload["baselineHash"] == baseline["baselineHash"]
    assert payload["entries"] == [
        {
            "clientId": "client_cffc",
            "selected": True,
            "reason": "入选：健康，且补齐 cockpit 代表性",
            "healthReason": "候选健康：workspace/cockpit 200",
            "representationReason": "补齐 cockpit 代表性",
        },
        {
            "clientId": "client_cb720fc373",
            "selected": False,
            "reason": "淘汰：knowledgeReady=false",
            "healthReason": "淘汰：knowledgeReady=false",
            "representationReason": "具备 cockpit 代表性，但未通过健康门槛",
        },
    ]


def test_write_install_note_writes_blocker_class_sidecar(tmp_path: Path) -> None:
    baseline_path = tmp_path / "rc-baseline.json"
    baseline = _write_baseline(baseline_path, str((Path("/tmp/demo") / "app.db").resolve()))
    runtime_dir = tmp_path / "runtime"
    _write_session(runtime_dir, baseline, baseline_path, state="wave2_active")

    payload = write_install_note(
        baseline_path=str(baseline_path),
        runtime_dir=str(runtime_dir),
        phase="step-a",
        blocker_class="packaging",
        decision="fail",
        reason="安装版白屏，Overview 未显示。",
        evidence_path=None,
        output_path=str(tmp_path / "install-step-a.note.json"),
    )

    assert payload["blockerClass"] == "packaging"
    assert payload["decision"] == "fail"
    assert payload["reason"] == "安装版白屏，Overview 未显示。"
    assert payload["installedRuntimeSignature"]["backendStartedByInstalledApp"] is True
    assert payload["sessionId"] == baseline["sessionId"]


def test_write_install_note_requires_packaging_when_step_a_used_workaround(tmp_path: Path) -> None:
    baseline_path = tmp_path / "rc-baseline.json"
    baseline = _write_baseline(baseline_path, str((Path("/tmp/demo") / "app.db").resolve()))
    runtime_dir = tmp_path / "runtime"
    _write_session(runtime_dir, baseline, baseline_path, state="wave2_active")
    evidence_path = tmp_path / "install-step-a.json"
    evidence_path.write_text(
        json.dumps(
            attach_artifact_contract(
                {
                    "phase": "step-a",
                    "backendStartedByInstalledApp": True,
                    "manualBackendRecoveryUsed": True,
                    "workaroundRequired": False,
                },
                baseline,
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="decision=fail and blockerClass=packaging"):
        write_install_note(
            baseline_path=str(baseline_path),
            runtime_dir=str(runtime_dir),
            phase="step-a",
            blocker_class="main-chain",
            decision="fail",
            reason="虽然靠 workaround 跑起来了，但页面边界还不稳。",
            evidence_path=str(evidence_path),
            output_path=str(tmp_path / "install-step-a.note.json"),
        )


def test_write_invalidated_artifacts_note_captures_old_runtime_artifacts(tmp_path: Path) -> None:
    baseline_path = tmp_path / "output" / "main-chain" / "rc-baseline.json"
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(
        json.dumps(
            {
                "generatedAt": "2026-04-15T22:42:55",
                "fixedGate": {"status": "pass"},
                "fullSmoke": {"summary": "17 failed / 68 passed"},
                "classification": {"aClassCount": 0},
                "installedRuntimeSignature": None,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    runtime_dir = tmp_path / "runtime" / "main-chain-rc" / "v0.3.4"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "wave2-day0.json").write_text("{}", encoding="utf-8")
    (runtime_dir / "install-step-a.note.json").write_text("{}", encoding="utf-8")

    applications_dir = tmp_path / "Applications"
    stale_bundle = applications_dir / ".益语智库自用平台.installing-20260404-112300.app"
    stale_assets = stale_bundle / "Contents" / "Resources" / "app" / "dist" / "renderer" / "assets"
    stale_assets.mkdir(parents=True, exist_ok=True)
    (stale_assets / "main-old.js").write_text("// old renderer", encoding="utf-8")

    source_app = tmp_path / "dist" / "mac-arm64" / "益语智库自用平台.app"
    source_assets = source_app / "Contents" / "Resources" / "app" / "dist" / "renderer" / "assets"
    source_assets.mkdir(parents=True, exist_ok=True)
    (source_assets / "main-BHLIy-vt.js").write_text("// current renderer", encoding="utf-8")

    payload = write_invalidated_artifacts_note(
        runtime_dir=str(runtime_dir),
        baseline_path=str(baseline_path),
        source_app_path=str(source_app),
        applications_dir=str(applications_dir),
        output_path=None,
    )

    note_path = runtime_dir / "invalidated-artifacts.note.json"
    assert note_path.exists()
    assert payload["sourceRendererEntry"] == "main-BHLIy-vt.js"
    assert {Path(item["path"]).name for item in payload["entries"]} == {
        "rc-baseline.json",
        "wave2-day0.json",
        "install-step-a.note.json",
        ".益语智库自用平台.installing-20260404-112300.app",
    }
    for item in payload["entries"]:
        assert item["mayNotBeUsedFor"] == ["baseline", "day0", "wave2", "value-proof"]
        assert "reason" in item and item["reason"]


def test_write_full_smoke_classification_normalizes_existing_artifact(tmp_path: Path) -> None:
    source_path = tmp_path / "full-smoke-classification.source.json"
    source_path.write_text(
        json.dumps(
            {
                "pytestExitCode": 1,
                "logPath": str(tmp_path / "full-smoke.log"),
                "fullSmokeSummary": "17 failed / 68 passed",
                "failures": [
                    "tests/test_api_smoke.py::test_topics_promote_to_task",
                    "tests/test_api_smoke.py::test_topics_promote_to_task",
                ],
                "rcBlockingFailures": [],
                "inheritedFailures": [
                    {
                        "test": "tests/test_api_smoke.py::test_topics_promote_to_task",
                        "cluster": "Topics / Insight / Org DNA 注入",
                        "reason": "不落在 installed-runtime RC 边界内。",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = write_full_smoke_classification(
        source_path=str(source_path),
        log_path=None,
        pytest_exit_code=None,
        full_smoke_summary=None,
        failures=None,
        rc_blocking_failures=None,
        inherited_failures=None,
        classification_reason=None,
        output_path=str(tmp_path / "full-smoke-classification.json"),
    )

    assert payload["canRegenerateBaseline"] is True
    assert payload["failures"] == ["tests/test_api_smoke.py::test_topics_promote_to_task"]
    assert payload["classificationReason"]


def test_write_full_smoke_classification_marks_rc_blockers_from_inputs(tmp_path: Path) -> None:
    log_path = tmp_path / "full-smoke.log"
    log_path.write_text(
        "\n".join(
            [
                "FAILED tests/test_api_smoke.py::test_workspace_boundary",
                "FAILED tests/test_api_smoke.py::test_topic_candidate_chat_uses_candidate_context",
            ]
        ),
        encoding="utf-8",
    )

    payload = write_full_smoke_classification(
        source_path=None,
        log_path=str(log_path),
        pytest_exit_code=1,
        full_smoke_summary="2 failed / 10 passed",
        failures=[],
        rc_blocking_failures=["tests/test_api_smoke.py::test_workspace_boundary"],
        inherited_failures=[
            json.dumps(
                {
                    "test": "tests/test_api_smoke.py::test_topic_candidate_chat_uses_candidate_context",
                    "cluster": "Topics / Insight / Org DNA 注入",
                    "reason": "不落在 installed-runtime RC 边界内。",
                },
                ensure_ascii=False,
            )
        ],
        classification_reason="只要命中 workspace/cockpit/Step A/Day 0 边界，就算 RC blocker。",
        output_path=str(tmp_path / "full-smoke-classification.json"),
    )

    assert payload["canRegenerateBaseline"] is False
    assert payload["rcBlockingFailures"] == ["tests/test_api_smoke.py::test_workspace_boundary"]
    assert payload["failures"] == [
        "tests/test_api_smoke.py::test_workspace_boundary",
        "tests/test_api_smoke.py::test_topic_candidate_chat_uses_candidate_context",
    ]
    assert payload["classificationReason"] == "只要命中 workspace/cockpit/Step A/Day 0 边界，就算 RC blocker。"


def test_write_phase_b_decision_blocks_when_conditions_missing(monkeypatch, tmp_path: Path) -> None:
    baseline_path = tmp_path / "rc-baseline.json"
    baseline = _write_baseline(baseline_path, str((Path("/tmp/demo") / "app.db").resolve()))
    runtime_dir = tmp_path / "runtime"
    _write_session(runtime_dir, baseline, baseline_path, state="step_b_ready")
    overview_proof = tmp_path / "page-proof-overview.json"
    workspace_proof = tmp_path / "page-proof-workspace-state.json"
    cockpit_proof = tmp_path / "page-proof-cockpit.json"
    _write_page_proof(overview_proof, baseline, "overview")
    _write_page_proof(workspace_proof, baseline, "workspace-state")
    _write_page_proof(cockpit_proof, baseline, "cockpit")
    observation_path = tmp_path / "wave2-day3.json"
    observation_path.write_text(
        json.dumps(
            attach_artifact_contract(
            {
                "observation": {
                    "timeRange": "Wave 2 / Day 3",
                    "verdict": "watch",
                    "conclusion": "继续观察。",
                    }
                },
                baseline,
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    manual_path = tmp_path / "value-proof-manual.json"
    manual_path.write_text(
        json.dumps(
            {
                "sessionId": baseline["sessionId"],
                "baselineHash": baseline["baselineHash"],
                "tupleHash": baseline["tupleHash"],
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
                    "evidencePageProofs": {
                        "overview": str(overview_proof),
                        "workspace": str(workspace_proof),
                        "cockpit": str(cockpit_proof),
                    },
                },
                "judgmentConsistency": {
                    "status": "基本稳定",
                    "summary": "还没完全稳定。",
                },
                "scenes": [
                    {"name": "客户工作台", "confirmed": True, "evidence": {"pageProofPath": str(workspace_proof)}},
                    {"name": "任务 AI", "confirmed": True, "evidence": {"pageProofPath": str(workspace_proof)}},
                ],
                "reviewers": [],
                "nextDecision": {
                    "canEnterV04": False,
                    "blockedBy": ["Wave 2 还未结束"],
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    class FakeApi:
        base_url = "http://127.0.0.1:47829"

        def get_stability_settings(self):
            return {"latestJudgmentsShadowOff": True, "backfillPaused": False}

        def get_metrics(self):
            return {"windowDays": 7}

        def get_settings(self):
            return {"settings": {"dataDir": "/tmp/demo"}, "health": {"buildVersion": "2026.04.16-rc"}}

    monkeypatch.setattr("scripts.main_chain_rc_ops.get_git_commit_sha", lambda: "baseline-sha")
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.get_git_dirty_worktree_state",
        lambda excluded_paths=None: {"dirtyWorktree": False, "dirtyPaths": []},
    )
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.inspect_installed_app",
        lambda path=None: {"path": "/Users/demo/Applications/益语智库自用平台.app", "exists": True, "modifiedAt": "2026-04-16T10:00:00", "rendererEntry": "main-demo.js"},
    )
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.inspect_installed_runtime_signature",
        lambda base_url="http://127.0.0.1:47829", installed_app=None: {
            "appBundleMTime": "2026-04-16T10:00:00",
            "rendererEntry": "main-demo.js",
            "backendStartedByInstalledApp": True,
            "backendPid": 12345,
            "backendCommand": "/tmp/demo/python -m uvicorn app.main:app --port 47829",
        },
    )

    payload = write_phase_b_decision(
        FakeApi(),
        baseline_path=str(baseline_path),
        runtime_dir=str(runtime_dir),
        observation_path=str(observation_path),
        manual_path=str(manual_path),
        blocker_class="none",
        output_path=str(tmp_path / "phase-b-decision.json"),
    )

    assert payload["allowEnterPhaseB"] is False
    assert payload["runCompletionStatus"] == "watch"
    assert payload["mainChainJudgmentStability"] == "unstable"
    assert payload["conditionsMet"]["installClosurePass"] is True
    assert payload["conditionsMet"]["runCompletionPass"] is False
    assert "Wave 2 还未结束" in payload["blockingReasons"]
    assert "manual nextDecision.canEnterV04=false" in payload["blockingReasons"]
