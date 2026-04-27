from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, request
from urllib.parse import urlparse

try:
    from scripts.main_chain_rc_contract import (
        DEFAULT_BASELINE_PATH,
        DEFAULT_RUNTIME_DIR,
        RC_MODE,
        attach_artifact_contract,
        build_session_id,
        compute_tuple_hash,
        default_rc_session,
        ensure_baseline_contract,
        identity_tuple_payload,
        load_rc_session,
        rc_session_path,
        resolve_runtime_dir,
        stable_json_hash,
        write_rc_session,
    )
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from scripts.main_chain_rc_contract import (  # type: ignore[no-redef]
        DEFAULT_BASELINE_PATH,
        DEFAULT_RUNTIME_DIR,
        RC_MODE,
        attach_artifact_contract,
        build_session_id,
        compute_tuple_hash,
        default_rc_session,
        ensure_baseline_contract,
        identity_tuple_payload,
        load_rc_session,
        rc_session_path,
        resolve_runtime_dir,
        stable_json_hash,
        write_rc_session,
    )


DEFAULT_BASE_URL = os.environ.get("YIYU_BACKEND_URL", "http://127.0.0.1:47829").rstrip("/")
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_JOB_TIMEOUT_SECONDS = 180.0
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output" / "main-chain"
DEFAULT_INSTALLED_APP = Path.home() / "Applications" / "益语智库自用平台.app"
MAIN_CHAIN_CANARY_FLAG = "main-chain-canary"


@dataclass
class WaveRunResult:
    label: str
    client_id: str
    shadow_off: bool
    job_id: str
    job_status: str
    baseline_judgment_id: str | None
    selected_candidate_id: str | None
    analysis_center_counts: dict[str, int]
    hidden_dependency_issues: list[str]


class ApiRequestError(RuntimeError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class BackendApi:
    def __init__(self, base_url: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def close(self) -> None:
        return None

    def _request(self, method: str, path: str, *, json_body: dict[str, Any] | None = None) -> Any:
        body = json.dumps(json_body).encode("utf-8") if json_body is not None else None
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = request.Request(f"{self.base_url}{path}", data=body, headers=headers, method=method.upper())
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                payload = response.read()
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            raise ApiRequestError(exc.code, detail or path) from exc
        except error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            raise RuntimeError(f"failed to reach backend at {self.base_url}{path}: {reason}") from exc

        if not payload:
            return None
        try:
            return json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid JSON response from {path}") from exc

    def get_clients(self) -> list[dict[str, Any]]:
        payload = self._request("GET", "/api/v1/clients")
        return payload if isinstance(payload, list) else []

    def get_workspace(self, client_id: str) -> dict[str, Any]:
        payload = self._request("GET", f"/api/v1/clients/{client_id}/workspace")
        if not isinstance(payload, dict):
            raise RuntimeError("workspace payload is not a JSON object")
        return payload

    def get_cockpit(self, client_id: str) -> dict[str, Any]:
        payload = self._request("GET", f"/api/v1/clients/{client_id}/strategic-cockpit")
        if not isinstance(payload, dict):
            raise RuntimeError("cockpit payload is not a JSON object")
        return payload

    def get_metrics(self) -> dict[str, Any]:
        payload = self._request("GET", "/api/v1/runtime/analysis-migration-metrics")
        if not isinstance(payload, dict):
            raise RuntimeError("metrics payload is not a JSON object")
        return payload

    def get_settings(self) -> dict[str, Any]:
        payload = self._request("GET", "/api/v1/settings")
        if not isinstance(payload, dict):
            raise RuntimeError("settings payload is not a JSON object")
        return payload

    def get_stability_settings(self) -> dict[str, Any]:
        payload = self._request("GET", "/api/v1/settings/main-chain-stability")
        if not isinstance(payload, dict):
            raise RuntimeError("stability settings payload is not a JSON object")
        return payload

    def update_stability_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._request("POST", "/api/v1/settings/main-chain-stability", json_body=payload)
        if not isinstance(result, dict):
            raise RuntimeError("stability settings update response is not a JSON object")
        return result

    def dry_run_backfill(self, client_ids: list[str], *, batch_size: int, max_jobs: int) -> dict[str, Any]:
        payload = self._request(
            "POST",
            "/api/v1/analysis/backfill-main-chain",
            json_body={
                "clientIds": client_ids,
                "dryRun": True,
                "batchSize": batch_size,
                "maxJobs": max_jobs,
                "pauseRequested": False,
            },
        )
        if not isinstance(payload, dict):
            raise RuntimeError("backfill dry-run payload is not a JSON object")
        return payload

    def create_analysis_job(
        self,
        client_id: str,
        *,
        question: str,
        trigger_type: str = "manual",
        priority: str = "normal",
        intent_profile: str = "client_overview",
        feature_flags: dict[str, bool] | None = None,
    ) -> dict[str, Any]:
        payload = self._request(
            "POST",
            "/api/v1/analysis/jobs",
            json_body={
                "jobType": "strategy_pack",
                "clientId": client_id,
                "scopeType": "client",
                "scopeId": client_id,
                "priority": priority,
                "triggerType": trigger_type,
                "question": question,
                "sourceScope": {},
                "featureFlags": feature_flags or {},
                "intentProfile": intent_profile,
            },
        )
        if not isinstance(payload, dict):
            raise RuntimeError("analysis job payload is not a JSON object")
        return payload

    def get_analysis_job(self, job_id: str) -> dict[str, Any]:
        payload = self._request("GET", f"/api/v1/analysis/jobs/{job_id}")
        if not isinstance(payload, dict):
            raise RuntimeError("analysis job detail is not a JSON object")
        return payload


def iso_now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def parse_dt(value: str | None) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def write_output(path: str | None, payload: dict[str, Any]) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if not path:
        print(rendered)
        return
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


def _load_json_object(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON payload at {path} is not an object")
    return payload


def _load_baseline_contract(path: str | Path | None) -> dict[str, Any]:
    baseline_path = Path(path or DEFAULT_BASELINE_PATH).expanduser().resolve()
    if not baseline_path.exists():
        raise RuntimeError(f"baseline file not found: {baseline_path}")
    return ensure_baseline_contract(_load_json_object(baseline_path))


def _ensure_session_for_baseline(
    *,
    runtime_dir: str | Path | None,
    baseline: dict[str, Any],
    baseline_path: str | Path | None = None,
) -> dict[str, Any]:
    runtime_root = resolve_runtime_dir(runtime_dir)
    session = load_rc_session(runtime_root)
    baseline_contract = ensure_baseline_contract(baseline)
    resolved_baseline_path = str(Path(baseline_path or DEFAULT_BASELINE_PATH).expanduser().resolve())
    if session is None:
        session = default_rc_session(
            baseline_path=resolved_baseline_path,
            session_id=str(baseline_contract.get("sessionId") or ""),
        )
        session["baselinePath"] = resolved_baseline_path
        session["baselineHash"] = baseline_contract.get("baselineHash")
        session["tupleHash"] = baseline_contract.get("tupleHash")
        session["state"] = "baseline_frozen"
        session["activeInstallSignature"] = {
            "appBundleMTime": (baseline_contract.get("installedRuntimeSignature") or {}).get("appBundleMTime"),
            "rendererEntry": (baseline_contract.get("installedRuntimeSignature") or {}).get("rendererEntry"),
            "backendStartedByInstalledApp": bool(
                (baseline_contract.get("installedRuntimeSignature") or {}).get("backendStartedByInstalledApp")
            ),
        }
        return write_rc_session(session, runtime_dir=runtime_root)

    if str(session.get("baselineHash") or "") != str(baseline_contract.get("baselineHash") or ""):
        session["baselinePath"] = resolved_baseline_path
        session["baselineHash"] = baseline_contract.get("baselineHash")
        session["tupleHash"] = baseline_contract.get("tupleHash")
        session["sessionId"] = baseline_contract.get("sessionId")
        if str(session.get("state") or "") == "pre_baseline":
            session["state"] = "baseline_frozen"
        return write_rc_session(session, runtime_dir=runtime_root)
    return session


def _record_session_invalidation(
    *,
    runtime_dir: str | Path | None,
    baseline_path: str | Path | None,
    baseline_contract: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    runtime_root = resolve_runtime_dir(runtime_dir)
    session = load_rc_session(runtime_root) or default_rc_session(
        baseline_path=str(Path(baseline_path or DEFAULT_BASELINE_PATH).expanduser().resolve()),
        session_id=str(baseline_contract.get("sessionId") or ""),
    )
    session.update(
        {
            "sessionId": baseline_contract.get("sessionId"),
            "baselinePath": str(Path(baseline_path or DEFAULT_BASELINE_PATH).expanduser().resolve()),
            "baselineHash": baseline_contract.get("baselineHash"),
            "tupleHash": baseline_contract.get("tupleHash"),
            "state": "pre_baseline",
            "invalidatedAt": iso_now(),
            "invalidationReason": reason,
        }
    )
    updated = write_rc_session(session, runtime_dir=runtime_root)
    try:
        from scripts.main_chain_rc_ops import write_invalidated_artifacts_note

        write_invalidated_artifacts_note(
            runtime_dir=str(runtime_root),
            baseline_path=str(Path(baseline_path or DEFAULT_BASELINE_PATH).expanduser().resolve()),
            source_app_path=None,
            applications_dir=None,
            output_path=str(runtime_root / "invalidated-artifacts.note.json"),
            invalidated_session_id=str(baseline_contract.get("sessionId") or ""),
            invalidated_baseline_hash=str(baseline_contract.get("baselineHash") or ""),
            invalidated_tuple_hash=str(baseline_contract.get("tupleHash") or ""),
            replacement_session_id=None,
            replacement_baseline_hash=None,
        )
    except Exception:
        pass
    return updated


def _enforce_runtime_contract(
    api: BackendApi,
    *,
    baseline_path: str | Path | None,
    runtime_dir: str | Path | None,
    command_name: str,
    allowed_states: set[str],
) -> dict[str, Any]:
    baseline_contract = _load_baseline_contract(baseline_path)
    session = _ensure_session_for_baseline(
        runtime_dir=runtime_dir,
        baseline=baseline_contract,
        baseline_path=baseline_path,
    )
    current_state = str(session.get("state") or "pre_baseline")
    if current_state not in allowed_states:
        raise RuntimeError(
            f"{command_name} requires rc-session.state in {sorted(allowed_states)}, got {current_state}"
        )
    current_snapshot = metrics_snapshot(api)
    current_settings = (current_snapshot.get("appSettings") or {}).get("settings") or {}
    current_health = (current_snapshot.get("appSettings") or {}).get("health") or {}
    dirty_state = get_git_dirty_worktree_state(
        excluded_paths=[get_repo_relative_path(baseline_path)] if baseline_path else None,
    )
    installed_app = inspect_installed_app()
    current_identity = {
        "commitSha": get_git_commit_sha(),
        "backendUrl": api.base_url,
        "buildVersion": current_health.get("buildVersion"),
        "databasePath": str(Path(str(current_settings.get("dataDir") or "")).expanduser().resolve() / "app.db")
        if current_settings.get("dataDir")
        else None,
        "latestJudgmentsShadowOff": bool((current_snapshot.get("settings") or {}).get("latestJudgmentsShadowOff")),
        "dirtyWorktree": bool(dirty_state["dirtyWorktree"]),
        "dirtyPaths": list(dirty_state["dirtyPaths"]),
        "installedRuntimeSignature": inspect_installed_runtime_signature(api.base_url, installed_app=installed_app),
    }
    current_tuple_hash = compute_tuple_hash(current_identity)
    if str(baseline_contract.get("tupleHash") or "") != current_tuple_hash:
        reason = (
            f"{command_name} refused to continue because live tupleHash={current_tuple_hash} "
            f"does not match baseline tupleHash={baseline_contract.get('tupleHash')}"
        )
        _record_session_invalidation(
            runtime_dir=runtime_dir,
            baseline_path=baseline_path,
            baseline_contract=baseline_contract,
            reason=reason,
        )
        raise RuntimeError(reason)
    return {
        "baseline": baseline_contract,
        "session": session,
        "currentTupleHash": current_tuple_hash,
    }


def _transition_session_state(
    *,
    runtime_dir: str | Path | None,
    session: dict[str, Any],
    state: str,
    baseline: dict[str, Any] | None = None,
    invalidation_reason: str | None = None,
) -> dict[str, Any]:
    updated = dict(session)
    updated["state"] = state
    if baseline:
        updated["sessionId"] = baseline.get("sessionId")
        updated["baselineHash"] = baseline.get("baselineHash")
        updated["tupleHash"] = baseline.get("tupleHash")
    if state == "pre_baseline":
        updated["invalidatedAt"] = iso_now()
        updated["invalidationReason"] = invalidation_reason
    else:
        updated["invalidatedAt"] = None
        updated["invalidationReason"] = None
    return write_rc_session(updated, runtime_dir=runtime_dir)


def run_command(command: list[str], *, cwd: Path | None = None) -> str:
    result = subprocess.run(command, cwd=str(cwd) if cwd else None, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def get_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_git_commit_sha() -> str | None:
    repo_root = get_repo_root()
    value = run_command(["git", "-C", str(repo_root), "rev-parse", "HEAD"])
    return value or None


def get_repo_relative_path(path: str | Path | None) -> str | None:
    if not path:
        return None
    repo_root = get_repo_root()
    resolved = Path(path).expanduser().resolve()
    try:
        return str(resolved.relative_to(repo_root))
    except ValueError:
        return None


def get_git_dirty_worktree_state(*, excluded_paths: list[str] | None = None) -> dict[str, Any]:
    repo_root = get_repo_root()
    excluded = {item for item in (excluded_paths or []) if item}
    dirty_paths: set[str] = set()
    for command in (
        ["git", "-C", str(repo_root), "diff", "--name-only"],
        ["git", "-C", str(repo_root), "diff", "--name-only", "--cached"],
        ["git", "-C", str(repo_root), "ls-files", "--others", "--exclude-standard"],
    ):
        output = run_command(command)
        for raw in output.splitlines():
            path = raw.strip()
            if not path or path in excluded:
                continue
            dirty_paths.add(path)
    ordered_paths = sorted(dirty_paths)
    return {
        "dirtyWorktree": bool(ordered_paths),
        "dirtyPaths": ordered_paths,
    }


def inspect_installed_app(path: Path | None = None) -> dict[str, Any]:
    target = (path or DEFAULT_INSTALLED_APP).expanduser().resolve()
    asset_dir = target / "Contents" / "Resources" / "app" / "dist" / "renderer" / "assets"
    renderer_entries: list[str] = []
    preferred_entry: str | None = None
    if asset_dir.exists():
        renderer_entries = sorted(
            item.name
            for item in asset_dir.iterdir()
            if item.is_file() and (item.name.startswith("main-") or item.name.startswith("index-")) and item.suffix == ".js"
        )
        preferred_entry = next((name for name in renderer_entries if name.startswith("main-")), None) or (renderer_entries[0] if renderer_entries else None)
    return {
        "path": str(target),
        "exists": target.exists(),
        "rendererEntry": preferred_entry,
        "rendererAssets": renderer_entries,
        "modifiedAt": datetime.fromtimestamp(target.stat().st_mtime).replace(microsecond=0).isoformat() if target.exists() else None,
    }


def inspect_installed_runtime_signature(
    base_url: str = DEFAULT_BASE_URL,
    *,
    installed_app: dict[str, Any] | None = None,
) -> dict[str, Any]:
    app_info = installed_app or inspect_installed_app()
    signature = {
        "appBundleMTime": app_info.get("modifiedAt"),
        "rendererEntry": app_info.get("rendererEntry"),
        "backendStartedByInstalledApp": False,
        "backendPid": None,
        "backendCommand": None,
    }
    parsed = urlparse(base_url if "://" in base_url else f"http://{base_url}")
    host = (parsed.hostname or "").strip().lower()
    port = parsed.port
    if host not in {"127.0.0.1", "localhost"} or port is None:
        return signature

    listener_output = run_command(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-Fp"])
    backend_pid = next((line[1:] for line in listener_output.splitlines() if line.startswith("p") and line[1:].strip()), None)
    if not backend_pid:
        return signature

    backend_command = run_command(["ps", "-p", backend_pid, "-o", "command="]) or None
    installed_runtime_python = str(
        Path.home()
        / "Library"
        / "Application Support"
        / "YiyuThinkTankWorkbench"
        / "runtime"
        / "backend-venv"
        / "bin"
        / "python"
    )
    signature["backendPid"] = int(backend_pid)
    signature["backendCommand"] = backend_command
    signature["backendStartedByInstalledApp"] = bool(backend_command and installed_runtime_python in backend_command)
    return signature


def candidate_is_knowledge_ready(workspace: dict[str, Any]) -> bool:
    status = workspace.get("knowledgeStatus") or {}
    return (
        int(status.get("pendingJobs") or 0) == 0
        and int(status.get("runningJobs") or 0) == 0
        and str(status.get("lastJobStatus") or "") == "completed"
    )


def extract_counts(workspace: dict[str, Any]) -> dict[str, int]:
    summary = workspace.get("analysisCenter") or {}
    return {
        "evidenceCardCount": int(summary.get("evidenceCardCount") or 0),
        "themeClusterCount": int(summary.get("themeClusterCount") or 0),
        "conflictGroupCount": int(summary.get("conflictGroupCount") or 0),
        "openQuestionCount": int(summary.get("openQuestionCount") or 0),
    }


def extract_ids(workspace: dict[str, Any]) -> tuple[str | None, str | None]:
    bundle = workspace.get("judgmentBundle") or {}
    trace = workspace.get("latestResolutionTrace") or {}
    baseline = bundle.get("baselineJudgment") or {}
    selected = trace.get("selectedCandidate") or {}
    baseline_id = str(baseline.get("id") or "").strip() or None
    selected_id = str(selected.get("objectId") or "").strip() or None
    return baseline_id, selected_id


def wait_for_job_terminal(api: BackendApi, job_id: str, *, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_payload: dict[str, Any] = {}
    while time.time() < deadline:
        payload = api.get_analysis_job(job_id)
        last_payload = payload
        if str(payload.get("status") or "") not in {"queued", "running"}:
            return payload
        time.sleep(1.0)
    return last_payload


def build_hidden_dependency_issues(
    workspace: dict[str, Any],
    cockpit: dict[str, Any],
    metrics: dict[str, Any],
    *,
    shadow_off: bool,
) -> list[str]:
    issues: list[str] = []
    if not isinstance(metrics, dict) or not metrics:
        issues.append("Overview metrics payload missing")
    if not workspace.get("judgmentBundle"):
        issues.append("workspace.judgmentBundle missing")
    if not workspace.get("latestResolutionTrace"):
        issues.append("workspace.latestResolutionTrace missing")
    if shadow_off and workspace.get("latestJudgments") != []:
        issues.append("latestJudgments still serialized while shadow off is enabled")
    if not isinstance(cockpit, dict) or "officialLayerStatus" not in cockpit:
        issues.append("strategic-cockpit payload missing official layer metadata")
    return issues


def compare_idempotency_windows(previous: WaveRunResult, rerun: WaveRunResult) -> list[str]:
    issues: list[str] = []
    if previous.analysis_center_counts != rerun.analysis_center_counts:
        issues.append("analysisCenter counts drifted after same-snapshot rerun")
    if previous.baseline_judgment_id != rerun.baseline_judgment_id:
        issues.append("baselineJudgment id changed after same-snapshot rerun")
    if previous.selected_candidate_id != rerun.selected_candidate_id:
        issues.append("selectedCandidate id changed after same-snapshot rerun")
    return issues


def run_manual_window(
    api: BackendApi,
    client_id: str,
    *,
    label: str,
    shadow_off: bool,
    timeout_seconds: float,
    trigger_type: str = "manual",
    priority: str = "normal",
    intent_profile: str = "client_overview",
) -> WaveRunResult:
    api.update_stability_settings({"latestJudgmentsShadowOff": shadow_off})
    feature_flags = {MAIN_CHAIN_CANARY_FLAG: True}
    job = api.create_analysis_job(
        client_id,
        question=f"main-chain {label}",
        trigger_type=trigger_type,
        priority=priority,
        intent_profile=intent_profile,
        feature_flags=feature_flags,
    )
    job_id = str(job.get("id") or "")
    if not job_id:
        raise RuntimeError(f"{label}: failed to create analysis job")
    terminal = wait_for_job_terminal(api, job_id, timeout_seconds=timeout_seconds)
    workspace = api.get_workspace(client_id)
    cockpit = api.get_cockpit(client_id)
    metrics = api.get_metrics()
    baseline_id, selected_id = extract_ids(workspace)
    return WaveRunResult(
        label=label,
        client_id=client_id,
        shadow_off=shadow_off,
        job_id=job_id,
        job_status=str(terminal.get("status") or ""),
        baseline_judgment_id=baseline_id,
        selected_candidate_id=selected_id,
        analysis_center_counts=extract_counts(workspace),
        hidden_dependency_issues=build_hidden_dependency_issues(workspace, cockpit, metrics, shadow_off=shadow_off),
    )


def metrics_snapshot(api: BackendApi) -> dict[str, Any]:
    settings = api.get_stability_settings()
    metrics = api.get_metrics()
    app_settings = api.get_settings()
    return {
        "recordedAt": iso_now(),
        "baseUrl": api.base_url,
        "metrics": metrics,
        "settings": settings,
        "appSettings": app_settings,
    }


def capture_snapshot(
    api: BackendApi,
    *,
    baseline_path: str | None,
    runtime_dir: str | None,
    output_path: str | None,
) -> dict[str, Any]:
    gate = _enforce_runtime_contract(
        api,
        baseline_path=baseline_path,
        runtime_dir=runtime_dir,
        command_name="snapshot",
        allowed_states={"day0_ready", "wave2_active", "step_b_ready"},
    )
    payload = attach_artifact_contract(metrics_snapshot(api), gate["baseline"])
    write_output(output_path, payload)
    return payload


def recommend_wave1_clients(api: BackendApi, *, limit: int, lookback_days: int) -> dict[str, Any]:
    now = datetime.now()
    candidates: list[dict[str, Any]] = []
    skipped_clients: list[dict[str, str]] = []
    for client in api.get_clients():
        last_activity = parse_dt(str(client.get("lastActivityAt") or ""))
        age_days = (now - last_activity).days if last_activity else 9999
        client_id = str(client["id"])
        try:
            workspace = api.get_workspace(client_id)
        except Exception as exc:
            skipped_clients.append(
                {
                    "clientId": client_id,
                    "name": str(client.get("name") or ""),
                    "reason": str(exc),
                }
            )
            continue
        knowledge_ready = candidate_is_knowledge_ready(workspace)
        has_context = bool(
            workspace.get("documentCards")
            or workspace.get("meetings")
            or workspace.get("relatedTasks")
        )
        if age_days > lookback_days:
            continue
        score = max(0, lookback_days - age_days) * 100
        score += int(client.get("documentCount") or 0) * 5
        score += int(client.get("taskCount") or 0) * 3
        if knowledge_ready:
            score += 50
        if has_context:
            score += 25
        candidates.append(
            {
                "clientId": client_id,
                "name": str(client.get("name") or ""),
                "lastActivityAt": client.get("lastActivityAt"),
                "documentCount": int(client.get("documentCount") or 0),
                "taskCount": int(client.get("taskCount") or 0),
                "knowledgeReady": knowledge_ready,
                "hasContext": has_context,
                "score": score,
            }
        )
    candidates.sort(key=lambda item: (not item["knowledgeReady"], not item["hasContext"], -int(item["score"])))
    return {
        "recordedAt": iso_now(),
        "baseUrl": api.base_url,
        "lookbackDays": lookback_days,
        "recommended": candidates[:limit],
        "skippedClients": skipped_clients,
    }


def freeze_rc_baseline(
    api: BackendApi,
    *,
    fixed_gate_status: str,
    full_smoke_summary: str,
    a_class_count: int,
    b_class_summary: list[str],
    c_class_summary: list[str],
    notes: str | None,
    runtime_dir: str | None = None,
    output_path: str | None,
) -> dict[str, Any]:
    generated_at = iso_now()
    snapshot = metrics_snapshot(api)
    settings_payload = snapshot.get("appSettings") or {}
    app_settings = settings_payload.get("settings") or {}
    health = settings_payload.get("health") or {}
    installed_app = inspect_installed_app()
    installed_runtime_signature = inspect_installed_runtime_signature(api.base_url, installed_app=installed_app)
    dirty_state = get_git_dirty_worktree_state(
        excluded_paths=[get_repo_relative_path(output_path)] if output_path else None,
    )
    baseline = {
        "recordedAt": generated_at,
        "generatedAt": generated_at,
        "commitSha": get_git_commit_sha(),
        "backendUrl": api.base_url,
        "databasePath": str(Path(str(app_settings.get("dataDir") or "")).expanduser().resolve() / "app.db") if app_settings.get("dataDir") else None,
        "dataDir": app_settings.get("dataDir"),
        "dirtyWorktree": bool(dirty_state["dirtyWorktree"]),
        "dirtyPaths": list(dirty_state["dirtyPaths"]),
        "installedApp": installed_app,
        "installedRuntimeSignature": installed_runtime_signature,
        "health": {
            "appVersion": health.get("appVersion"),
            "buildVersion": health.get("buildVersion"),
            "startedAt": health.get("startedAt"),
        },
        "fixedGate": {
            "status": fixed_gate_status,
            "commands": [
                ".venv/bin/python -m pytest -q tests/test_analysis_main_chain.py",
                ".venv/bin/python -m pytest -q tests/test_knowledge_v2.py",
                ".venv/bin/python -m pytest -q tests/test_api_smoke.py -k \"strategic_cockpit or workspace_import_builds_document_cards_and_knowledge_status or workspace_import_auto_generates_client_dna_candidates or main_chain_canary_closes_import_analysis_approval_and_cockpit\"",
                "npm run build:main",
                "npm run build:renderer",
            ],
        },
        "fullSmoke": {
            "summary": full_smoke_summary,
        },
        "classification": {
            "aClassCount": a_class_count,
            "bClassSummary": b_class_summary,
            "cClassSummary": c_class_summary,
        },
        "latestJudgmentsShadowOff": bool((snapshot.get("settings") or {}).get("latestJudgmentsShadowOff")),
        "mainChainStability": snapshot.get("settings") or {},
        "metrics": snapshot.get("metrics") or {},
        "notes": notes or "",
    }
    baseline = ensure_baseline_contract(baseline)
    write_output(output_path, baseline)

    runtime_root = resolve_runtime_dir(runtime_dir)
    session = default_rc_session(
        baseline_path=str(Path(output_path or DEFAULT_BASELINE_PATH).expanduser().resolve()),
        session_id=str(baseline.get("sessionId") or build_session_id(generated_at=generated_at, tuple_hash=str(baseline.get("tupleHash") or ""))),
    )
    session.update(
        {
            "sessionId": baseline.get("sessionId"),
            "state": "baseline_frozen",
            "baselinePath": str(Path(output_path or DEFAULT_BASELINE_PATH).expanduser().resolve()),
            "baselineHash": baseline.get("baselineHash"),
            "tupleHash": baseline.get("tupleHash"),
            "activeInstallSignature": {
                "appBundleMTime": baseline.get("appBundleMTime") or ((baseline.get("installedRuntimeSignature") or {}).get("appBundleMTime")),
                "rendererEntry": baseline.get("rendererEntry") or ((baseline.get("installedRuntimeSignature") or {}).get("rendererEntry")),
                "backendStartedByInstalledApp": bool(
                    baseline.get("backendStartedByInstalledApp")
                    if baseline.get("backendStartedByInstalledApp") is not None
                    else ((baseline.get("installedRuntimeSignature") or {}).get("backendStartedByInstalledApp"))
                ),
            },
            "invalidatedAt": None,
            "invalidationReason": None,
        }
    )
    write_rc_session(session, runtime_dir=runtime_root)
    return baseline


def load_json(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON payload at {path} is not an object")
    return payload


def load_observation_payload(path: str) -> dict[str, Any]:
    payload = load_json(path)
    nested = payload.get("observation")
    if isinstance(nested, dict):
        return nested
    return payload


def _page_proof_passes(path: str | None, *, baseline_hash: str | None = None, tuple_hash: str | None = None, session_id: str | None = None) -> bool:
    target = str(path or "").strip()
    if not target:
        return False
    payload = _load_json_object(target)
    if str(payload.get("decision") or "").strip() != "pass":
        return False
    if baseline_hash and str(payload.get("baselineHash") or "").strip() != str(baseline_hash):
        return False
    if tuple_hash and str(payload.get("tupleHash") or "").strip() != str(tuple_hash):
        return False
    if session_id and str(payload.get("sessionId") or "").strip() != str(session_id):
        return False
    return True


def format_percent(value: float | int | None) -> str:
    return f"{(float(value or 0.0) * 100):.1f}%"


def format_status_label(value: str | None) -> str:
    mapping = {
        "pass": "通过",
        "watch": "继续观察",
        "fail": "未通过",
    }
    return mapping.get(str(value or "").strip(), str(value or "未填写"))


def format_check(value: bool | None) -> str:
    if value is True:
        return "通过"
    if value is False:
        return "未通过"
    return "未填写"


def render_value_proof_markdown(
    *,
    observation: dict[str, Any],
    manual: dict[str, Any],
    baseline_contract: dict[str, Any] | None = None,
) -> str:
    contract = ensure_baseline_contract(baseline_contract) if baseline_contract else None
    release_label = str(manual.get("releaseLabel") or "v0.3.4 RC")
    code_completion_status = format_status_label(str(manual.get("codeCompletionStatus") or "watch"))
    run_completion_status = format_status_label(str(manual.get("runCompletionStatus") or observation.get("verdict") or "watch"))

    install_validation = manual.get("installValidation") or {}
    install_evidence = install_validation.get("evidenceScreenshots") or {}
    install_page_proofs = install_validation.get("evidencePageProofs") or {}
    metrics_story = manual.get("metricsStory") or {}
    scenes = manual.get("scenes") or []
    reviewers = manual.get("reviewers") or []
    next_decision = manual.get("nextDecision") or {}
    judgment_consistency = manual.get("judgmentConsistency") or {}
    judgment_consistency_status = str(judgment_consistency.get("status") or "未填写")
    judgment_consistency_summary = str(judgment_consistency.get("summary") or "未填写")
    confirmed_feedback_union = {
        "boundaryClear": False,
        "taskContextSharper": False,
        "meetingCapturesUnresolved": False,
        "cockpitAvoidsFakeConclusion": False,
    }
    for reviewer in reviewers:
        if not isinstance(reviewer, dict):
            continue
        feedback = reviewer.get("feedback") or {}
        for key in confirmed_feedback_union:
            confirmed_feedback_union[key] = confirmed_feedback_union[key] or bool(feedback.get(key))
    scene_contract_ok = []
    for item in scenes:
        if not isinstance(item, dict):
            continue
        evidence = item.get("evidence") or {}
        page_proof_path = str(evidence.get("pageProofPath") or "").strip()
        scene_contract_ok.append(
            bool(item.get("confirmed"))
            and _page_proof_passes(
                page_proof_path,
                baseline_hash=contract.get("baselineHash") if contract else None,
                tuple_hash=contract.get("tupleHash") if contract else None,
                session_id=contract.get("sessionId") if contract else None,
            )
        )
    scenes_confirmed = bool(scene_contract_ok) and all(scene_contract_ok)
    install_screenshots_complete = all(
        str(install_evidence.get(key) or "").strip()
        for key in ("overview", "workspace", "cockpit")
    )
    install_page_proofs_complete = all(
        _page_proof_passes(
            str(install_page_proofs.get(key) or ""),
            baseline_hash=contract.get("baselineHash") if contract else None,
            tuple_hash=contract.get("tupleHash") if contract else None,
            session_id=contract.get("sessionId") if contract else None,
        )
        for key in ("overview", "workspace", "cockpit")
    )
    install_closed = (
        bool(install_validation.get("appStarts"))
        and bool(install_validation.get("backendStartedByInstalledApp"))
        and bool(install_validation.get("overviewPanelVisible"))
        and bool(install_validation.get("shadowOffParity"))
        and bool(install_validation.get("workspaceBoundaryCorrect"))
        and bool(install_validation.get("cockpitOfficialLayerToneCorrect"))
        and bool(install_validation.get("overviewMetricsPopulated"))
        and install_screenshots_complete
        and install_page_proofs_complete
    )
    business_feedback_complete = all(confirmed_feedback_union.values())
    judgment_consistency_ready = judgment_consistency_status == "稳定"
    value_proof_ready = install_closed and scenes_confirmed and business_feedback_complete and judgment_consistency_ready

    lines = [
        f"# {release_label} 价值证明结论",
        "",
        "## 结论概览",
        f"- 代码完成态：{code_completion_status}",
        f"- 运行完成态：{run_completion_status}",
        f"- 最近一次观察窗口：{observation.get('timeRange') or '未填写'}",
        f"- 最近一次试跑结论：{format_status_label(observation.get('verdict'))}",
        f"- 结论摘要：{observation.get('conclusion') or '未填写'}",
        f"- 主链判断口径：{judgment_consistency_status}",
        f"- 口径说明：{judgment_consistency_summary}",
        f"- 价值证明状态：{'已具备通过条件' if value_proof_ready else '尚未具备通过条件'}",
        "",
        "## 安装版闭环",
        f"- 安装版状态：{format_status_label(install_validation.get('status'))}",
        f"- 能正常启动：{format_check(install_validation.get('appStarts'))}",
        f"- 47829 由安装版自拉起：{format_check(install_validation.get('backendStartedByInstalledApp'))}",
        f"- 能看到稳定化面板：{format_check(install_validation.get('overviewPanelVisible'))}",
        f"- 关闭旧结果通道后与源码版一致：{format_check(install_validation.get('shadowOffParity'))}",
        f"- workspace 口径正确：{format_check(install_validation.get('workspaceBoundaryCorrect'))}",
        f"- cockpit official layer 口径正确：{format_check(install_validation.get('cockpitOfficialLayerToneCorrect'))}",
        f"- Overview 指标不是空壳：{format_check(install_validation.get('overviewMetricsPopulated'))}",
        f"- 截图留档：Overview {install_evidence.get('overview') or '未填写'}；workspace {install_evidence.get('workspace') or '未填写'}；cockpit {install_evidence.get('cockpit') or '未填写'}",
        f"- 页面证据契约：Overview {install_page_proofs.get('overview') or '未填写'}；workspace {install_page_proofs.get('workspace') or '未填写'}；cockpit {install_page_proofs.get('cockpit') or '未填写'}",
        f"- 说明：{install_validation.get('summary') or '未填写'}",
        "",
        "## 这轮变化是否真的看得见",
        f"- 导入后多久可用：{metrics_story.get('importReadyTime') or '未填写'}",
        f"- 同 snapshot 重跑会不会越跑越乱：{metrics_story.get('idempotencySummary') or '未填写'}",
        f"- 页面说法打架率：{format_percent(observation.get('resolverMismatchRateBefore'))} → {format_percent(observation.get('resolverMismatchRateAfter'))}",
        f"- 退回旧逻辑比例：{format_percent(observation.get('fallbackRateBefore'))} → {format_percent(observation.get('fallbackRateAfter'))}",
        f"- 待确认判断是否堆积：{int(observation.get('approvalBacklog') or 0)} 个 / {(float(observation.get('approvalLagHoursMedian') or 0.0)):.1f}h；{metrics_story.get('approvalSummary') or '未填写'}",
        "- 口径说明：本轮试跑产生的 canary 样本不计入日常审批积压指标。",
        "- 指标口径说明：approvalBacklog / approvalLagHoursMedian / Candidate SLA 已排除 main-chain-canary=true 的样本，代表真实业务积压，不代表试跑制造的积压。",
        "",
        "## 场景对照",
        "| 场景 | 以前 | 现在 | 仍不够好 | 已验证 | 证据 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    scene_written = False
    for item in scenes:
        if not isinstance(item, dict):
            continue
        scene_written = True
        evidence = item.get("evidence") or {}
        evidence_summary_parts = []
        if evidence.get("sampleId"):
            evidence_summary_parts.append(f"样本 {evidence['sampleId']}")
        if evidence.get("screenshotPath"):
            evidence_summary_parts.append(f"截图 {evidence['screenshotPath']}")
        if evidence.get("pageProofPath"):
            evidence_summary_parts.append(f"页面契约 {evidence['pageProofPath']}")
        if evidence.get("excerpt"):
            evidence_summary_parts.append(f"摘录 {evidence['excerpt']}")
        lines.append(
            "| {name} | {before} | {after} | {still_not_good_enough} | {confirmed} | {evidence} |".format(
                name=str(item.get("name") or "未命名场景").replace("|", "／"),
                before=str(item.get("before") or "未填写").replace("|", "／"),
                after=str(item.get("after") or "未填写").replace("|", "／"),
                still_not_good_enough=str(item.get("stillNotGoodEnough") or "未填写").replace("|", "／"),
                confirmed="是" if bool(item.get("confirmed")) else "否",
                evidence=("；".join(str(part).replace("|", "／") for part in evidence_summary_parts) if evidence_summary_parts else "未填写"),
            )
        )
    if not scene_written:
        lines.append("| 暂无 | 未填写 | 未填写 | 未填写 | 否 | 未填写 |")

    lines.extend(
        [
            "",
            "## 业务同事反馈",
        ]
    )
    if reviewers:
        for reviewer in reviewers:
            if not isinstance(reviewer, dict):
                continue
            feedback = reviewer.get("feedback") or {}
            confirmed_points = [
                label
                for key, label in (
                    ("boundaryClear", "状态边界更清楚"),
                    ("taskContextSharper", "事件线上下文差异更明显"),
                    ("meetingCapturesUnresolved", "会议结果更能承接推进链"),
                    ("cockpitAvoidsFakeConclusion", "cockpit 不再把提醒当结论"),
                )
                if bool(feedback.get(key))
            ]
            lines.extend(
                [
                    f"- {reviewer.get('name') or '未署名'} / {reviewer.get('role') or '未填写角色'}",
                    f"  - 已确认：{('、'.join(confirmed_points)) if confirmed_points else '未明确确认'}",
                    f"  - 备注：{reviewer.get('notes') or '未填写'}",
                ]
            )
    else:
        lines.append("- 还没有收集业务同事反馈。")

    lines.extend(
        [
            "",
            "## 仍待补证据",
        ]
    )
    blocked_by = next_decision.get("blockedBy") or []
    if isinstance(blocked_by, list) and blocked_by:
        lines.append(f"- 当前仍待补：{'；'.join(str(item) for item in blocked_by)}")
    else:
        lines.append("- 当前仍待补：无")
    if not reviewers:
        lines.append("- 备注：当前还没有业务同事反馈，因此不能判定价值证明通过。")
    elif not business_feedback_complete:
        lines.append("- 备注：业务同事反馈还未覆盖 4 个关键判断点，因此不能判定价值证明通过。")
    if not judgment_consistency_ready:
        lines.append("- 备注：主链判断口径还未达到“稳定”，因此不能作为进入 v0.4 的依据。")

    return "\n".join(lines).strip() + "\n"


def build_observation_payload(
    *,
    before_metrics: dict[str, Any],
    after_metrics: dict[str, Any],
    settings: dict[str, Any],
    client_count: int,
    enqueued_jobs: int,
    completed_jobs: int,
    failed_jobs: int,
    time_range: str,
    impacted_realtime_tasks: bool,
    shadow_off: bool,
    verdict: str,
    conclusion: str,
) -> dict[str, Any]:
    return {
        "timeRange": time_range,
        "clientCount": client_count,
        "enqueuedJobs": enqueued_jobs,
        "completedJobs": completed_jobs,
        "failedJobs": failed_jobs,
        "newObjectHitRateBefore": float(before_metrics.get("newObjectHitRate") or 0.0),
        "newObjectHitRateAfter": float(after_metrics.get("newObjectHitRate") or 0.0),
        "fallbackRateBefore": float(before_metrics.get("fallbackRate") or 0.0),
        "fallbackRateAfter": float(after_metrics.get("fallbackRate") or 0.0),
        "resolverMismatchRateBefore": float(before_metrics.get("resolverMismatchRate") or 0.0),
        "resolverMismatchRateAfter": float(after_metrics.get("resolverMismatchRate") or 0.0),
        "approvalBacklog": int(after_metrics.get("approvalBacklog") or 0),
        "approvalLagHoursMedian": float(after_metrics.get("approvalLagHoursMedian") or 0.0),
        "claimCounts": ((settings.get("workerCounters") or {}).get("claimCounts") or {}),
        "lockContention": ((settings.get("workerCounters") or {}).get("lockContention") or {}),
        "backfillThrottle": ((settings.get("workerCounters") or {}).get("backfillThrottle") or {}),
        "impactedRealtimeTasks": impacted_realtime_tasks,
        "latestJudgmentsShadowOff": shadow_off,
        "verdict": verdict,
        "conclusion": conclusion,
    }


def run_wave1(
    api: BackendApi,
    *,
    client_a: str,
    client_b: str | None,
    idempotency_client: str | None,
    timeout_seconds: float,
    write_observation: bool,
    impacted_realtime_tasks: bool,
    output_path: str | None,
) -> dict[str, Any]:
    wave_clients = [client_a] + ([client_b] if client_b and client_b != client_a else [])
    before = metrics_snapshot(api)
    dry_run = api.dry_run_backfill(wave_clients or [client_a], batch_size=1, max_jobs=2)

    results: list[WaveRunResult] = []
    results.append(run_manual_window(api, client_a, label="wave1-client-a-shadow-on", shadow_off=True, timeout_seconds=timeout_seconds))

    client_b_effective = client_b or client_a
    results.append(run_manual_window(api, client_b_effective, label="wave1-client-b-shadow-off", shadow_off=False, timeout_seconds=timeout_seconds))
    results.append(run_manual_window(api, client_b_effective, label="wave1-client-b-shadow-on", shadow_off=True, timeout_seconds=timeout_seconds))

    idempotency_target = idempotency_client or client_a
    previous_true_window = next(
        (item for item in reversed(results) if item.client_id == idempotency_target and item.shadow_off),
        None,
    )
    idempotency_result = run_manual_window(
        api,
        idempotency_target,
        label="wave1-idempotency-rerun",
        shadow_off=True,
        timeout_seconds=timeout_seconds,
    )
    results.append(idempotency_result)

    idempotency_ok = True
    idempotency_issues: list[str] = []
    if previous_true_window is not None:
        idempotency_issues.extend(compare_idempotency_windows(previous_true_window, idempotency_result))
        if idempotency_issues:
            idempotency_ok = False
    else:
        idempotency_ok = False
        idempotency_issues.append("missing previous true-shadow window for idempotency comparison")

    after = metrics_snapshot(api)
    hidden_dependency_issues = [
        issue
        for item in results
        for issue in item.hidden_dependency_issues
    ]
    failed_jobs = [item for item in results if item.job_status != "completed"]

    verdict = "pass"
    conclusion_parts: list[str] = []
    if hidden_dependency_issues:
        verdict = "fail"
        conclusion_parts.append("发现 shadowOff 隐藏依赖")
    if failed_jobs:
        verdict = "fail"
        conclusion_parts.append(f"{len(failed_jobs)} 个 canary job 未完成")
    if not idempotency_ok:
        verdict = "fail"
        conclusion_parts.append("同 snapshot 重跑未通过幂等性 gate")
    if impacted_realtime_tasks:
        verdict = "fail"
        conclusion_parts.append("观察到实时任务受 backfill 影响")
    if verdict == "pass":
        conclusion_parts.append("Wave 1 通过：shadowOff、manual rerun 与 idempotency gate 均未暴露主链回潮。")

    observation = build_observation_payload(
        before_metrics=before["metrics"],
        after_metrics=after["metrics"],
        settings=after["settings"],
        client_count=len({item.client_id for item in results if item.label != "wave1-idempotency-rerun"}),
        enqueued_jobs=len(results),
        completed_jobs=len(results) - len(failed_jobs),
        failed_jobs=len(failed_jobs),
        time_range=f"Wave 1 @ {iso_now()}",
        impacted_realtime_tasks=impacted_realtime_tasks,
        shadow_off=bool((after["settings"].get("latestJudgmentsShadowOff"))),
        verdict=verdict,
        conclusion="；".join(conclusion_parts),
    )
    if write_observation:
        api.update_stability_settings({"lastCanaryObservation": observation})

    summary = {
        "recordedAt": iso_now(),
        "baseUrl": api.base_url,
        "dryRun": dry_run,
        "before": before,
        "after": after,
        "runs": [
            {
                "label": item.label,
                "clientId": item.client_id,
                "shadowOff": item.shadow_off,
                "jobId": item.job_id,
                "jobStatus": item.job_status,
                "baselineJudgmentId": item.baseline_judgment_id,
                "selectedCandidateId": item.selected_candidate_id,
                "analysisCenterCounts": item.analysis_center_counts,
                "hiddenDependencyIssues": item.hidden_dependency_issues,
            }
            for item in results
        ],
        "idempotencyOk": idempotency_ok,
        "idempotencyIssues": idempotency_issues,
        "observation": observation,
    }
    write_output(output_path, summary)
    return summary


def run_wave2_day0(
    api: BackendApi,
    *,
    client_ids: list[str],
    batch_size: int,
    max_jobs: int,
    timeout_seconds: float,
    write_observation: bool,
    impacted_realtime_tasks: bool,
    baseline_contract: dict[str, Any] | None = None,
    output_path: str | None,
) -> dict[str, Any]:
    unique_client_ids: list[str] = []
    for client_id in client_ids:
        normalized = str(client_id or "").strip()
        if normalized and normalized not in unique_client_ids:
            unique_client_ids.append(normalized)
    if len(unique_client_ids) < 3:
        raise RuntimeError("wave2-day0 requires at least 3 unique client ids")

    before = metrics_snapshot(api)
    dry_run = api.dry_run_backfill(unique_client_ids, batch_size=batch_size, max_jobs=max_jobs)
    api.update_stability_settings({"latestJudgmentsShadowOff": True})

    first_runs: dict[str, WaveRunResult] = {}
    reruns: dict[str, WaveRunResult] = {}
    results: list[WaveRunResult] = []
    idempotency_issues: dict[str, list[str]] = {}

    for index, client_id in enumerate(unique_client_ids, start=1):
        first = run_manual_window(
            api,
            client_id,
            label=f"wave2-day0-client-{index}",
            shadow_off=True,
            timeout_seconds=timeout_seconds,
        )
        rerun = run_manual_window(
            api,
            client_id,
            label=f"wave2-day0-client-{index}-rerun",
            shadow_off=True,
            timeout_seconds=timeout_seconds,
        )
        first_runs[client_id] = first
        reruns[client_id] = rerun
        results.extend([first, rerun])
        issues = compare_idempotency_windows(first, rerun)
        if issues:
            idempotency_issues[client_id] = issues

    backfill_target = unique_client_ids[0]
    backfill_run = run_manual_window(
        api,
        backfill_target,
        label="wave2-day0-backfill",
        shadow_off=True,
        timeout_seconds=timeout_seconds,
        trigger_type="backfill",
        priority="low",
        intent_profile="client_overview",
    )
    results.append(backfill_run)

    after = metrics_snapshot(api)
    hidden_dependency_issues = [issue for item in results for issue in item.hidden_dependency_issues]
    failed_jobs = [item for item in results if item.job_status != "completed"]

    verdict = "pass"
    conclusion_parts: list[str] = []
    if hidden_dependency_issues:
        verdict = "fail"
        conclusion_parts.append("关闭旧结果通道后仍暴露隐藏依赖")
    if failed_jobs:
        verdict = "fail"
        conclusion_parts.append(f"{len(failed_jobs)} 个 Day 0 job 未完成")
    if idempotency_issues:
        verdict = "fail"
        conclusion_parts.append("同 snapshot 重跑出现对象漂移")
    if impacted_realtime_tasks:
        verdict = "fail"
        conclusion_parts.append("观察到实时任务受 backfill 影响")
    if backfill_run.job_status != "completed":
        verdict = "fail"
        conclusion_parts.append("极小真实 backfill 未完成")
    if verdict == "pass":
        conclusion_parts.append("Day 0 预热通过：关闭旧结果通道、同 snapshot 重跑与极小真实 backfill 均保持稳定。")

    observation = build_observation_payload(
        before_metrics=before["metrics"],
        after_metrics=after["metrics"],
        settings=after["settings"],
        client_count=len(unique_client_ids),
        enqueued_jobs=len(results),
        completed_jobs=len(results) - len(failed_jobs),
        failed_jobs=len(failed_jobs),
        time_range=f"Wave 2 / Day 0 @ {iso_now()}",
        impacted_realtime_tasks=impacted_realtime_tasks,
        shadow_off=bool(after["settings"].get("latestJudgmentsShadowOff")),
        verdict=verdict,
        conclusion="；".join(conclusion_parts),
    )
    if write_observation:
        api.update_stability_settings({"lastCanaryObservation": observation})

    summary = {
        "recordedAt": iso_now(),
        "baseUrl": api.base_url,
        "dryRun": dry_run,
        "before": before,
        "after": after,
        "runs": [
            {
                "label": item.label,
                "clientId": item.client_id,
                "shadowOff": item.shadow_off,
                "jobId": item.job_id,
                "jobStatus": item.job_status,
                "baselineJudgmentId": item.baseline_judgment_id,
                "selectedCandidateId": item.selected_candidate_id,
                "analysisCenterCounts": item.analysis_center_counts,
                "hiddenDependencyIssues": item.hidden_dependency_issues,
            }
            for item in results
        ],
        "idempotencyIssues": idempotency_issues,
        "backfillRun": {
            "clientId": backfill_run.client_id,
            "jobId": backfill_run.job_id,
            "jobStatus": backfill_run.job_status,
            "baselineJudgmentId": backfill_run.baseline_judgment_id,
            "selectedCandidateId": backfill_run.selected_candidate_id,
            "analysisCenterCounts": backfill_run.analysis_center_counts,
            "hiddenDependencyIssues": backfill_run.hidden_dependency_issues,
        },
        "observation": observation,
    }
    if baseline_contract:
        summary = attach_artifact_contract(summary, baseline_contract)
    write_output(output_path, summary)
    return summary


def record_observation(
    api: BackendApi,
    *,
    before_path: str,
    time_range: str,
    client_count: int,
    enqueued_jobs: int,
    completed_jobs: int,
    failed_jobs: int,
    impacted_realtime_tasks: bool,
    verdict: str,
    conclusion: str,
    baseline_contract: dict[str, Any] | None = None,
    output_path: str | None,
) -> dict[str, Any]:
    before_payload = json.loads(Path(before_path).expanduser().resolve().read_text(encoding="utf-8"))
    before_metrics = before_payload.get("metrics") or {}
    after = metrics_snapshot(api)
    observation = build_observation_payload(
        before_metrics=before_metrics,
        after_metrics=after["metrics"],
        settings=after["settings"],
        client_count=client_count,
        enqueued_jobs=enqueued_jobs,
        completed_jobs=completed_jobs,
        failed_jobs=failed_jobs,
        time_range=time_range,
        impacted_realtime_tasks=impacted_realtime_tasks,
        shadow_off=bool(after["settings"].get("latestJudgmentsShadowOff")),
        verdict=verdict,
        conclusion=conclusion,
    )
    updated = api.update_stability_settings({"lastCanaryObservation": observation})
    payload = {
        "recordedAt": iso_now(),
        "baseUrl": api.base_url,
        "before": before_payload,
        "after": after,
        "observation": observation,
        "updatedSettings": updated,
    }
    if baseline_contract:
        payload = attach_artifact_contract(payload, baseline_contract)
    write_output(output_path, payload)
    return payload


def render_value_proof(
    *,
    observation_path: str,
    manual_path: str,
    baseline_contract: dict[str, Any] | None = None,
    output_path: str | None,
) -> str:
    observation = load_observation_payload(observation_path)
    manual = load_json(manual_path)
    rendered = render_value_proof_markdown(
        observation=observation,
        manual=manual,
        baseline_contract=baseline_contract,
    )
    if output_path:
        target = Path(output_path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
        print(rendered)
        return rendered
    print(rendered)
    return rendered


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run v0.3.4 main-chain RC canary steps against the local backend.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"Backend base URL. Default: {DEFAULT_BASE_URL}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    recommend = subparsers.add_parser("recommend-wave1", help="Rank likely Wave 1 clients by recent activity and readiness.")
    recommend.add_argument("--limit", type=int, default=5)
    recommend.add_argument("--lookback-days", type=int, default=14)
    recommend.add_argument("--output", help="Optional JSON output path.")

    recommend_wave2 = subparsers.add_parser("recommend-wave2", help="Rank likely Wave 2 / Day 0 clients by recent activity and readiness.")
    recommend_wave2.add_argument("--limit", type=int, default=5)
    recommend_wave2.add_argument("--lookback-days", type=int, default=14)
    recommend_wave2.add_argument("--output", help="Optional JSON output path.")

    snapshot = subparsers.add_parser("snapshot", help="Capture the current metrics/settings snapshot.")
    snapshot.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    snapshot.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    snapshot.add_argument("--output", help="Optional JSON output path.")

    freeze = subparsers.add_parser("freeze-baseline", help="Write the single RC baseline file used for all Wave 2 discussion.")
    freeze.add_argument("--fixed-gate-status", required=True, choices=("pass", "fail"))
    freeze.add_argument("--full-smoke-summary", required=True, help="Example: '16 failed / 68 passed'")
    freeze.add_argument("--a-class-count", required=True, type=int)
    freeze.add_argument("--b-class-summary", action="append", default=[], help="Repeat for each B-class cluster summary.")
    freeze.add_argument("--c-class-summary", action="append", default=[], help="Repeat for each C-class summary.")
    freeze.add_argument("--notes", help="Optional free-form baseline note.")
    freeze.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    freeze.add_argument("--output", default=str(DEFAULT_OUTPUT_DIR / "rc-baseline.json"), help="Baseline JSON output path.")

    wave1 = subparsers.add_parser("wave1", help="Execute the Wave 1 manual canary sequence.")
    wave1.add_argument("--client-a", required=True, help="Client used for the always-shadow-on window.")
    wave1.add_argument("--client-b", help="Optional second client used for false->true shadow toggle.")
    wave1.add_argument("--idempotency-client", help="Optional client used for the same-snapshot rerun gate. Defaults to client-a.")
    wave1.add_argument("--timeout-seconds", type=float, default=DEFAULT_JOB_TIMEOUT_SECONDS)
    wave1.add_argument("--no-write-observation", action="store_true", help="Skip POST /settings/main-chain-stability lastCanaryObservation.")
    wave1.add_argument("--impacted-realtime-tasks", action="store_true", help="Mark the run as having impacted interactive/system work.")
    wave1.add_argument("--output", help="Optional JSON output path.")

    wave2_day0 = subparsers.add_parser("wave2-day0", help="Execute the Day 0 preheat for Wave 2 with shadow-off enabled throughout.")
    wave2_day0.add_argument(
        "--client-id",
        action="append",
        required=True,
        help="Client to include in the Day 0 preheat. Repeat this flag at least 3 times.",
    )
    wave2_day0.add_argument("--batch-size", type=int, default=1)
    wave2_day0.add_argument("--max-jobs", type=int, default=2)
    wave2_day0.add_argument("--timeout-seconds", type=float, default=DEFAULT_JOB_TIMEOUT_SECONDS)
    wave2_day0.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    wave2_day0.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    wave2_day0.add_argument("--no-write-observation", action="store_true", help="Skip POST /settings/main-chain-stability lastCanaryObservation.")
    wave2_day0.add_argument("--impacted-realtime-tasks", action="store_true", help="Mark the run as having impacted interactive/system work.")
    wave2_day0.add_argument("--output", help="Optional JSON output path.")

    record = subparsers.add_parser("record-observation", help="Record a Wave 2 daily observation using a saved baseline snapshot.")
    record.add_argument("--before", required=True, help="Path to a JSON snapshot captured before the observation window.")
    record.add_argument("--time-range", required=True)
    record.add_argument("--client-count", required=True, type=int)
    record.add_argument("--enqueued-jobs", required=True, type=int)
    record.add_argument("--completed-jobs", required=True, type=int)
    record.add_argument("--failed-jobs", required=True, type=int)
    record.add_argument("--verdict", required=True, choices=("pass", "watch", "fail"))
    record.add_argument("--conclusion", required=True)
    record.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    record.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    record.add_argument("--impacted-realtime-tasks", action="store_true")
    record.add_argument("--output", help="Optional JSON output path.")

    render = subparsers.add_parser("render-value-proof", help="Render a one-page markdown value-proof conclusion from observation JSON plus manual feedback JSON.")
    render.add_argument("--observation", required=True, help="Path to a Wave 2 / Day 0 observation JSON or a script output containing an observation field.")
    render.add_argument("--manual", required=True, help="Path to the manual feedback JSON template filled by the operator.")
    render.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    render.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    render.add_argument("--output", help="Optional markdown output path.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    api = BackendApi(args.base_url)
    try:
        if args.command in {"recommend-wave1", "recommend-wave2"}:
            payload = recommend_wave1_clients(api, limit=max(1, args.limit), lookback_days=max(1, args.lookback_days))
            write_output(args.output, payload)
            return 0
        if args.command == "snapshot":
            capture_snapshot(
                api,
                baseline_path=args.baseline,
                runtime_dir=args.runtime_dir,
                output_path=args.output,
            )
            return 0
        if args.command == "freeze-baseline":
            freeze_rc_baseline(
                api,
                fixed_gate_status=args.fixed_gate_status,
                full_smoke_summary=args.full_smoke_summary,
                a_class_count=max(0, int(args.a_class_count)),
                b_class_summary=list(args.b_class_summary),
                c_class_summary=list(args.c_class_summary),
                notes=args.notes,
                runtime_dir=args.runtime_dir,
                output_path=args.output,
            )
            return 0
        if args.command == "wave1":
            run_wave1(
                api,
                client_a=args.client_a,
                client_b=args.client_b,
                idempotency_client=args.idempotency_client,
                timeout_seconds=max(30.0, float(args.timeout_seconds)),
                write_observation=not args.no_write_observation,
                impacted_realtime_tasks=bool(args.impacted_realtime_tasks),
                output_path=args.output,
            )
            return 0
        if args.command == "wave2-day0":
            gate = _enforce_runtime_contract(
                api,
                baseline_path=args.baseline,
                runtime_dir=args.runtime_dir,
                command_name="wave2-day0",
                allowed_states={"day0_ready"},
            )
            _transition_session_state(
                runtime_dir=args.runtime_dir,
                session=gate["session"],
                state="wave2_active",
                baseline=gate["baseline"],
            )
            run_wave2_day0(
                api,
                client_ids=list(args.client_id),
                batch_size=max(1, int(args.batch_size)),
                max_jobs=max(1, int(args.max_jobs)),
                timeout_seconds=max(30.0, float(args.timeout_seconds)),
                write_observation=not args.no_write_observation,
                impacted_realtime_tasks=bool(args.impacted_realtime_tasks),
                baseline_contract=gate["baseline"],
                output_path=args.output,
            )
            return 0
        if args.command == "record-observation":
            gate = _enforce_runtime_contract(
                api,
                baseline_path=args.baseline,
                runtime_dir=args.runtime_dir,
                command_name="record-observation",
                allowed_states={"wave2_active", "step_b_ready"},
            )
            record_observation(
                api,
                before_path=args.before,
                time_range=args.time_range,
                client_count=max(0, args.client_count),
                enqueued_jobs=max(0, args.enqueued_jobs),
                completed_jobs=max(0, args.completed_jobs),
                failed_jobs=max(0, args.failed_jobs),
                impacted_realtime_tasks=bool(args.impacted_realtime_tasks),
                verdict=args.verdict,
                conclusion=args.conclusion,
                baseline_contract=gate["baseline"],
                output_path=args.output,
            )
            return 0
        if args.command == "render-value-proof":
            gate = _enforce_runtime_contract(
                api,
                baseline_path=args.baseline,
                runtime_dir=args.runtime_dir,
                command_name="render-value-proof",
                allowed_states={"step_b_ready"},
            )
            render_value_proof(
                observation_path=args.observation,
                manual_path=args.manual,
                baseline_contract=gate["baseline"],
                output_path=args.output,
            )
            return 0
        parser.error("unknown command")
        return 2
    except ApiRequestError as exc:
        print(f"HTTP error {exc.status_code}: {exc.detail}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - operational CLI
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        api.close()


if __name__ == "__main__":
    raise SystemExit(main())
