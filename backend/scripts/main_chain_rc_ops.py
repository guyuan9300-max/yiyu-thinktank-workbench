from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    from scripts.main_chain_rc_contract import (
        RC_MODE,
        attach_artifact_contract,
        active_install_signature_from_artifacts,
        compute_tuple_hash,
        default_rc_session,
        ensure_baseline_contract,
        load_rc_session,
        resolve_runtime_dir,
        stable_json_hash,
        write_rc_session,
    )
    from scripts.main_chain_canary import (
        DEFAULT_BASE_URL,
        BackendApi,
        candidate_is_knowledge_ready,
        get_git_commit_sha,
        get_git_dirty_worktree_state,
        get_repo_relative_path,
        inspect_installed_app,
        inspect_installed_runtime_signature,
        iso_now,
        load_json,
        load_observation_payload,
        metrics_snapshot,
        write_output,
    )
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from scripts.main_chain_rc_contract import (  # type: ignore[no-redef]
        RC_MODE,
        active_install_signature_from_artifacts,
        attach_artifact_contract,
        compute_tuple_hash,
        default_rc_session,
        ensure_baseline_contract,
        load_rc_session,
        resolve_runtime_dir,
        stable_json_hash,
        write_rc_session,
    )
    from scripts.main_chain_canary import (  # type: ignore[no-redef]
        DEFAULT_BASE_URL,
        BackendApi,
        candidate_is_knowledge_ready,
        get_git_commit_sha,
        get_git_dirty_worktree_state,
        get_repo_relative_path,
        inspect_installed_app,
        inspect_installed_runtime_signature,
        iso_now,
        load_json,
        load_observation_payload,
        metrics_snapshot,
        write_output,
    )


DEFAULT_RUNTIME_DIR = (
    Path.home()
    / "Library"
    / "Application Support"
    / "YiyuThinkTankWorkbench"
    / "runtime"
    / "main-chain-rc"
    / "v0.3.4"
)
DEFAULT_BASELINE_PATH = Path(__file__).resolve().parents[2] / "output" / "main-chain" / "rc-baseline.json"
DEFAULT_DAY0_PRIORITY = [
    "client_cffc",
    "client_a4d1db29a7",
    "client_53d82aa249",
    "client_284afd836e",
    "client_cb720fc373",
]
DEFAULT_CONTROL_PRIORITY = [
    "client_cffc",
    "client_a4d1db29a7",
    "client_284afd836e",
    "client_53d82aa249",
]
DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FULL_SMOKE_CLASSIFICATION_REASON = (
    "按 installed-runtime / shadow-off / Step A / Day 0 / 4 个价值场景边界归类；"
    "只有命中这些边界的问题才算 RC blocker。"
)
DB_ISOLATION_REQUIRED_PATTERNS = (
    {
        "label": "apiSmokeUsesTmpDataDir",
        "path": Path("backend/tests/test_api_smoke.py"),
        "pattern": re.compile(r'create_app\(tmp_path\s*/\s*["\']data["\']\)'),
        "description": 'API smoke 通过 create_app(tmp_path / "data") 启动临时数据目录。',
    },
    {
        "label": "analysisMainChainUsesTmpDataDir",
        "path": Path("backend/tests/test_analysis_main_chain.py"),
        "pattern": re.compile(r'create_app\(tmp_path\s*/\s*["\']data["\']\)'),
        "description": 'analysis main chain 通过 create_app(tmp_path / "data") 启动临时数据目录。',
    },
)
TMP_DB_PATTERN = re.compile(r'Database\(tmp_path\s*/\s*["\']app\.db["\']\)')
DEFAULT_PAGE_PROOF_TOKENS = {
    "overview": ["主链接管稳定化", "Overview", "fallback"],
    "workspace-state": ["状态优先", "正式判断", "待确认判断", "本周动作", "风险提醒", "缺失信息"],
    "workspace-drilldown": ["证据下钻", "引用", "原文"],
    "task-prep": ["status", "effectType", "prep_artifact_ready"],
    "meeting-followup": ["followup_task_created", "会后", "任务"],
    "cockpit": ["official", "empty reason", "radar"],
}


def _normalized_paths(items: list[str] | None) -> list[str]:
    return sorted({str(item).strip() for item in (items or []) if str(item).strip()})


def _dedupe_preserve_order(items: list[str] | None) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in items or []:
        value = str(raw).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _expected_installed_runtime_database_path(*, home_dir: Path | None = None) -> Path:
    base = (home_dir or Path.home()).expanduser().resolve()
    return base / "Library" / "Application Support" / "YiyuThinkTankWorkbench" / "app.db"


def _repo_relative_display(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path.resolve())


def _run_command(command: list[str], *, cwd: Path | None = None) -> tuple[int, str, str]:
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout or "", result.stderr or ""


def _ensure_runtime_dir(path: str | Path | None = None) -> Path:
    return resolve_runtime_dir(path)


def _load_json_object(path: str | Path) -> dict[str, Any]:
    payload = load_json(str(Path(path).expanduser().resolve()))
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
    runtime_root = _ensure_runtime_dir(runtime_dir)
    baseline_contract = ensure_baseline_contract(baseline)
    resolved_baseline_path = str(Path(baseline_path or DEFAULT_BASELINE_PATH).expanduser().resolve())
    session = load_rc_session(runtime_root)
    if session is None:
        session = default_rc_session(
            baseline_path=resolved_baseline_path,
            session_id=str(baseline_contract.get("sessionId") or ""),
        )
    if str(session.get("baselineHash") or "") != str(baseline_contract.get("baselineHash") or ""):
        session["sessionId"] = baseline_contract.get("sessionId")
        session["baselinePath"] = resolved_baseline_path
        session["baselineHash"] = baseline_contract.get("baselineHash")
        session["tupleHash"] = baseline_contract.get("tupleHash")
        if str(session.get("state") or "") == "pre_baseline":
            session["state"] = "baseline_frozen"
    return write_rc_session(session, runtime_dir=runtime_root)


def _transition_session_state(
    *,
    runtime_dir: str | Path | None,
    session: dict[str, Any],
    state: str,
    baseline: dict[str, Any] | None = None,
    invalidation_reason: str | None = None,
    install_receipt_path: str | None = None,
    install_smoke_path: str | None = None,
    active_install_signature: dict[str, Any] | None = None,
) -> dict[str, Any]:
    updated = deepcopy(session)
    updated["state"] = state
    if baseline:
        updated["sessionId"] = baseline.get("sessionId")
        updated["baselineHash"] = baseline.get("baselineHash")
        updated["tupleHash"] = baseline.get("tupleHash")
    if install_receipt_path is not None:
        updated["installReceiptPath"] = install_receipt_path
    if install_smoke_path is not None:
        updated["installSmokePath"] = install_smoke_path
    if active_install_signature is not None:
        updated["activeInstallSignature"] = active_install_signature
    if state == "pre_baseline":
        updated["invalidatedAt"] = iso_now()
        updated["invalidationReason"] = invalidation_reason
    else:
        updated["invalidatedAt"] = None
        updated["invalidationReason"] = None
    return write_rc_session(updated, runtime_dir=runtime_dir)


def _page_proof_default_output(page: str, *, runtime_dir: str | Path | None = None) -> Path:
    return _ensure_runtime_dir(runtime_dir) / f"page-proof-{page}.json"


def _page_proof_expected_tokens(page: str, explicit_tokens: list[str] | None = None) -> list[str]:
    if explicit_tokens:
        return _dedupe_preserve_order(explicit_tokens)
    return list(DEFAULT_PAGE_PROOF_TOKENS.get(page, []))


def _validate_page_proof_contract(
    path: str | Path,
    *,
    baseline_hash: str | None,
    tuple_hash: str | None,
    session_id: str | None,
    expected_page: str | None = None,
) -> dict[str, Any]:
    payload = _load_json_object(path)
    if str(payload.get("decision") or "").strip() != "pass":
        raise RuntimeError(f"page proof {path} is not pass")
    if expected_page and str(payload.get("page") or "").strip() != expected_page:
        raise RuntimeError(f"page proof {path} does not match page={expected_page}")
    if baseline_hash and str(payload.get("baselineHash") or "") != str(baseline_hash):
        raise RuntimeError(f"page proof {path} baselineHash mismatch")
    if tuple_hash and str(payload.get("tupleHash") or "") != str(tuple_hash):
        raise RuntimeError(f"page proof {path} tupleHash mismatch")
    if session_id and str(payload.get("sessionId") or "") != str(session_id):
        raise RuntimeError(f"page proof {path} sessionId mismatch")
    return payload


def _baseline_generated_at(payload: dict[str, Any]) -> Any:
    return payload.get("baselineGeneratedAt") or payload.get("generatedAt")


def _default_source_app_path() -> Path:
    return DEFAULT_REPO_ROOT / "dist" / "mac-arm64" / "益语智库自用平台.app"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _normalize_installed_runtime_signature(payload: dict[str, Any] | None, *, fallback_app: dict[str, Any] | None = None) -> dict[str, Any]:
    runtime_signature = dict(payload or {})
    if fallback_app:
        runtime_signature.setdefault("appBundleMTime", fallback_app.get("modifiedAt"))
        runtime_signature.setdefault("rendererEntry", fallback_app.get("rendererEntry"))
    runtime_signature.setdefault("backendStartedByInstalledApp", False)
    runtime_signature.setdefault("backendPid", None)
    runtime_signature.setdefault("backendCommand", None)
    return runtime_signature


def load_baseline_identity(path: str) -> dict[str, Any]:
    payload = ensure_baseline_contract(load_json(path))
    stability = payload.get("mainChainStability") or {}
    health = payload.get("health") or {}
    installed_app = payload.get("installedApp") or {}
    installed_runtime_signature = _normalize_installed_runtime_signature(
        payload.get("installedRuntimeSignature"),
        fallback_app=installed_app if isinstance(installed_app, dict) else None,
    )
    database_path = str(payload.get("databasePath") or "").strip()
    identity = {
        "baselineGeneratedAt": payload.get("generatedAt"),
        "commitSha": payload.get("commitSha"),
        "backendUrl": payload.get("backendUrl"),
        "buildVersion": health.get("buildVersion"),
        "databasePath": str(Path(database_path).expanduser().resolve()) if database_path else None,
        "latestJudgmentsShadowOff": bool(
            payload.get("latestJudgmentsShadowOff")
            if payload.get("latestJudgmentsShadowOff") is not None
            else stability.get("latestJudgmentsShadowOff")
        ),
        "dirtyWorktree": bool(payload.get("dirtyWorktree")),
        "dirtyPaths": _normalized_paths(payload.get("dirtyPaths")),
        "installedRuntimeSignature": installed_runtime_signature,
    }
    if payload.get("installedRuntimeSignature") is not None or payload.get("installedApp") is not None:
        identity["appBundleMTime"] = installed_runtime_signature.get("appBundleMTime")
        identity["rendererEntry"] = installed_runtime_signature.get("rendererEntry")
        identity["backendStartedByInstalledApp"] = bool(installed_runtime_signature.get("backendStartedByInstalledApp"))
        identity["backendPid"] = installed_runtime_signature.get("backendPid")
    identity["sessionId"] = payload.get("sessionId")
    identity["baselineHash"] = payload.get("baselineHash")
    identity["tupleHash"] = payload.get("tupleHash")
    identity["rcMode"] = payload.get("rcMode") or RC_MODE
    return identity


def _collect_invalidated_runtime_artifacts(runtime_dir: Path) -> list[Path]:
    patterns = (
        "day0-*.json",
        "day0-*.note.json",
        "wave2-*.json",
        "wave2-*.note.json",
        "install-step-*.json",
        "install-step-*.note.json",
    )
    artifacts: set[Path] = set()
    for pattern in patterns:
        artifacts.update(item.resolve() for item in runtime_dir.glob(pattern) if item.is_file())
    return sorted(artifacts)


def write_invalidated_artifacts_note(
    *,
    runtime_dir: str | None,
    baseline_path: str | None,
    source_app_path: str | None,
    applications_dir: str | None,
    output_path: str | None,
    invalidated_session_id: str | None = None,
    invalidated_baseline_hash: str | None = None,
    invalidated_tuple_hash: str | None = None,
    replacement_session_id: str | None = None,
    replacement_baseline_hash: str | None = None,
) -> dict[str, Any]:
    runtime_root = _ensure_runtime_dir(runtime_dir)
    baseline_target = Path(baseline_path or DEFAULT_BASELINE_PATH).expanduser().resolve()
    source_app_target = Path(source_app_path).expanduser().resolve() if source_app_path else _default_source_app_path()
    applications_root = Path(applications_dir).expanduser().resolve() if applications_dir else (Path.home() / "Applications")
    recorded_at = iso_now()
    entries: list[dict[str, Any]] = []
    may_not_be_used_for = ["baseline", "day0", "wave2", "value-proof"]
    source_app_info = inspect_installed_app(source_app_target)
    source_renderer_entry = source_app_info.get("rendererEntry")

    if baseline_target.exists():
        baseline_payload = load_json(str(baseline_target))
        if baseline_payload.get("installedRuntimeSignature") is None:
            entries.append(
                {
                    "path": str(baseline_target),
                    "invalidatedAt": recorded_at,
                    "reason": "旧 rc-baseline 缺少 installedRuntimeSignature，只能作历史参考，不能继续作为本轮 RC 基线。",
                    "replacement": None,
                    "mayNotBeUsedFor": may_not_be_used_for,
                }
            )

    for artifact_path in _collect_invalidated_runtime_artifacts(runtime_root):
        reason = "旧运行产物绑定到已失效的 installed-runtime 现场，不能继续作为本轮 RC 证据。"
        if artifact_path.name.startswith("install-step-"):
            reason = "旧安装版闭环证据绑定到已失效现场，不能继续作为本轮 RC 的安装链证明。"
        entries.append(
            {
                "path": str(artifact_path),
                "invalidatedAt": recorded_at,
                "reason": reason,
                "replacement": None,
                "mayNotBeUsedFor": may_not_be_used_for,
            }
        )

    if applications_root.exists():
        for bundle in sorted(applications_root.glob(".益语智库自用平台.installing-*.app")):
            bundle_info = inspect_installed_app(bundle)
            renderer_entry = bundle_info.get("rendererEntry")
            reason = "历史 staging bundle 不得作为 target app fallback 使用。"
            if source_renderer_entry and renderer_entry != source_renderer_entry:
                reason = (
                    f"历史 staging bundle 的 rendererEntry={renderer_entry or 'null'} 与当前受信安装源 "
                    f"{source_renderer_entry} 不一致，不得用于本轮 installed-runtime RC。"
                )
            entries.append(
                {
                    "path": str(bundle.resolve()),
                    "invalidatedAt": recorded_at,
                    "reason": reason,
                    "replacement": None,
                    "mayNotBeUsedFor": may_not_be_used_for,
                }
            )

    payload = {
        "recordedAt": recorded_at,
        "rcMode": RC_MODE,
        "runtimeDir": str(runtime_root),
        "baselinePath": str(baseline_target),
        "sourceApp": str(source_app_target),
        "sourceRendererEntry": source_renderer_entry,
        "invalidatedSessionId": invalidated_session_id,
        "invalidatedBaselineHash": invalidated_baseline_hash,
        "invalidatedTupleHash": invalidated_tuple_hash,
        "replacementSessionId": replacement_session_id,
        "replacementBaselineHash": replacement_baseline_hash,
        "mayNotBeUsedFor": may_not_be_used_for,
        "entries": entries,
    }
    target_output = (
        Path(output_path).expanduser().resolve()
        if output_path
        else runtime_root / "invalidated-artifacts.note.json"
    )
    write_output(str(target_output), payload)
    return payload


def sync_rc_session(
    *,
    runtime_dir: str | None,
    baseline_path: str | None,
    install_receipt_path: str | None,
    install_smoke_path: str | None,
    output_path: str | None,
) -> dict[str, Any]:
    runtime_root = _ensure_runtime_dir(runtime_dir)
    resolved_baseline_path = Path(baseline_path or DEFAULT_BASELINE_PATH).expanduser().resolve()
    resolved_receipt_path = Path(install_receipt_path or (runtime_root / "install-receipt.json")).expanduser().resolve()
    resolved_smoke_path = Path(install_smoke_path or (runtime_root / "install-smoke.json")).expanduser().resolve()
    session = load_rc_session(runtime_root) or default_rc_session(
        baseline_path=str(resolved_baseline_path),
        session_id=None,
    )
    install_receipt_payload = _load_json_object(resolved_receipt_path) if resolved_receipt_path.exists() else None
    install_smoke_payload = _load_json_object(resolved_smoke_path) if resolved_smoke_path.exists() else None
    active_install_signature = active_install_signature_from_artifacts(
        install_receipt_payload=install_receipt_payload,
        install_smoke_payload=install_smoke_payload,
    )
    session["installReceiptPath"] = str(resolved_receipt_path) if resolved_receipt_path.exists() else None
    session["installSmokePath"] = str(resolved_smoke_path) if resolved_smoke_path.exists() else None
    session["activeInstallSignature"] = active_install_signature

    payload: dict[str, Any] = {
        "recordedAt": iso_now(),
        "runtimeDir": str(runtime_root),
        "baselinePath": str(resolved_baseline_path),
        "installReceiptPath": session.get("installReceiptPath"),
        "installSmokePath": session.get("installSmokePath"),
        "activeInstallSignature": active_install_signature,
        "state": "pre_baseline",
        "reason": "baseline_missing",
    }
    if not resolved_baseline_path.exists():
        synced = _transition_session_state(
            runtime_dir=runtime_root,
            session=session,
            state="pre_baseline",
            invalidation_reason="baseline_missing",
            install_receipt_path=session.get("installReceiptPath"),
            install_smoke_path=session.get("installSmokePath"),
            active_install_signature=active_install_signature,
        )
        payload["session"] = synced
        write_output(str(output_path) if output_path else str(runtime_root / "rc-session.json"), synced if not output_path else payload)
        return synced if not output_path else payload

    baseline_contract = _load_baseline_contract(resolved_baseline_path)
    baseline_signature = (baseline_contract.get("installedRuntimeSignature") or {})
    drift_fields = []
    for field in ("appBundleMTime", "rendererEntry", "backendStartedByInstalledApp"):
        if baseline_signature.get(field) != active_install_signature.get(field):
            drift_fields.append(field)
    if drift_fields:
        reason = "install_signature_drift:" + ",".join(drift_fields)
        synced = _transition_session_state(
            runtime_dir=runtime_root,
            session=session,
            state="pre_baseline",
            baseline=baseline_contract,
            invalidation_reason=reason,
            install_receipt_path=session.get("installReceiptPath"),
            install_smoke_path=session.get("installSmokePath"),
            active_install_signature=active_install_signature,
        )
        write_invalidated_artifacts_note(
            runtime_dir=str(runtime_root),
            baseline_path=str(resolved_baseline_path),
            source_app_path=None,
            applications_dir=None,
            output_path=str(runtime_root / "invalidated-artifacts.note.json"),
            invalidated_session_id=str(baseline_contract.get("sessionId") or ""),
            invalidated_baseline_hash=str(baseline_contract.get("baselineHash") or ""),
            invalidated_tuple_hash=str(baseline_contract.get("tupleHash") or ""),
            replacement_session_id=None,
            replacement_baseline_hash=None,
        )
        payload.update(
            {
                "state": "pre_baseline",
                "reason": reason,
                "driftFields": drift_fields,
                "baselineHash": baseline_contract.get("baselineHash"),
                "tupleHash": baseline_contract.get("tupleHash"),
                "sessionId": baseline_contract.get("sessionId"),
                "session": synced,
            }
        )
        write_output(str(output_path) if output_path else str(runtime_root / "rc-session.json"), synced if not output_path else payload)
        return synced if not output_path else payload

    synced = _transition_session_state(
        runtime_dir=runtime_root,
        session=session,
        state="baseline_frozen" if str(session.get("state") or "") == "pre_baseline" else str(session.get("state") or "baseline_frozen"),
        baseline=baseline_contract,
        install_receipt_path=session.get("installReceiptPath"),
        install_smoke_path=session.get("installSmokePath"),
        active_install_signature=active_install_signature,
    )
    payload.update(
        {
            "state": synced.get("state"),
            "reason": "in_sync",
            "baselineHash": baseline_contract.get("baselineHash"),
            "tupleHash": baseline_contract.get("tupleHash"),
            "sessionId": baseline_contract.get("sessionId"),
            "session": synced,
        }
    )
    write_output(str(output_path) if output_path else str(runtime_root / "rc-session.json"), synced if not output_path else payload)
    return synced if not output_path else payload


def write_page_proof(
    *,
    baseline_path: str,
    runtime_dir: str | None,
    page: str,
    screenshot_path: str,
    expected_tokens: list[str] | None,
    ax_text_path: str | None,
    ocr_text_path: str | None,
    output_path: str | None,
) -> dict[str, Any]:
    baseline_contract = _load_baseline_contract(baseline_path)
    _ensure_session_for_baseline(
        runtime_dir=runtime_dir,
        baseline=baseline_contract,
        baseline_path=baseline_path,
    )
    expected = _page_proof_expected_tokens(page, expected_tokens)
    observed_source = ax_text_path or ocr_text_path
    if not observed_source:
        raise RuntimeError("write-page-proof requires --ax-text or --ocr-text")
    observed_text = Path(observed_source).expanduser().resolve().read_text(encoding="utf-8", errors="ignore")
    observed_tokens = _dedupe_preserve_order([line.strip() for line in observed_text.splitlines() if line.strip()])
    haystack = observed_text.lower()
    matched_tokens = [token for token in expected if token.lower() in haystack]
    missing_tokens = [token for token in expected if token not in matched_tokens]
    payload = {
        "page": page,
        "screenshotPath": str(Path(screenshot_path).expanduser().resolve()),
        "expectedTokens": expected,
        "observedTokens": observed_tokens,
        "matchedTokens": matched_tokens,
        "missingTokens": missing_tokens,
        "decision": "pass" if expected and not missing_tokens else "fail",
        "reason": "all expected tokens observed" if expected and not missing_tokens else "missing expected tokens",
        "recordedAt": iso_now(),
    }
    payload = attach_artifact_contract(payload, baseline_contract)
    target_output = Path(output_path).expanduser().resolve() if output_path else _page_proof_default_output(page, runtime_dir=runtime_dir)
    write_output(str(target_output), payload)
    return payload


def collect_runtime_identity(api: BackendApi, *, baseline_path: str | None = None) -> dict[str, Any]:
    snapshot = metrics_snapshot(api)
    app_settings = (snapshot.get("appSettings") or {}).get("settings") or {}
    health = (snapshot.get("appSettings") or {}).get("health") or {}
    excluded_path = get_repo_relative_path(baseline_path) if baseline_path else None
    dirty_state = get_git_dirty_worktree_state(excluded_paths=[excluded_path] if excluded_path else None)
    data_dir = str(app_settings.get("dataDir") or "").strip()
    installed_app = inspect_installed_app()
    installed_runtime_signature = _normalize_installed_runtime_signature(
        inspect_installed_runtime_signature(api.base_url, installed_app=installed_app),
        fallback_app=installed_app,
    )
    return {
        "baselineGeneratedAt": None,
        "commitSha": get_git_commit_sha(),
        "backendUrl": api.base_url,
        "buildVersion": health.get("buildVersion"),
        "databasePath": str(Path(data_dir).expanduser().resolve() / "app.db") if data_dir else None,
        "latestJudgmentsShadowOff": bool((snapshot.get("settings") or {}).get("latestJudgmentsShadowOff")),
        "dirtyWorktree": bool(dirty_state["dirtyWorktree"]),
        "dirtyPaths": _normalized_paths(dirty_state["dirtyPaths"]),
        "installedRuntimeSignature": installed_runtime_signature,
        "appBundleMTime": installed_runtime_signature.get("appBundleMTime"),
        "rendererEntry": installed_runtime_signature.get("rendererEntry"),
        "backendStartedByInstalledApp": bool(installed_runtime_signature.get("backendStartedByInstalledApp")),
        "backendPid": installed_runtime_signature.get("backendPid"),
    }


def compare_identity_tuple(*, baseline: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    for field in (
        "commitSha",
        "backendUrl",
        "buildVersion",
        "databasePath",
        "latestJudgmentsShadowOff",
        "dirtyWorktree",
        "dirtyPaths",
        "appBundleMTime",
        "rendererEntry",
        "backendStartedByInstalledApp",
    ):
        if field not in baseline:
            continue
        if baseline.get(field) != current.get(field):
            mismatches.append(
                {
                    "field": field,
                    "expected": baseline.get(field),
                    "actual": current.get(field),
                }
            )
    return mismatches


def _record_session_invalidation(
    *,
    runtime_dir: str | Path | None,
    baseline_path: str | Path | None,
    baseline_contract: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    runtime_root = _ensure_runtime_dir(runtime_dir)
    session = load_rc_session(runtime_root) or default_rc_session(
        baseline_path=str(Path(baseline_path or DEFAULT_BASELINE_PATH).expanduser().resolve()),
        session_id=str(baseline_contract.get("sessionId") or ""),
    )
    updated = _transition_session_state(
        runtime_dir=runtime_root,
        session=session,
        state="pre_baseline",
        baseline=baseline_contract,
        invalidation_reason=reason,
    )
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
    current_identity = collect_runtime_identity(api, baseline_path=str(baseline_path or DEFAULT_BASELINE_PATH))
    current_identity["baselineGeneratedAt"] = _baseline_generated_at(baseline_contract)
    mismatches = compare_identity_tuple(baseline=baseline_contract, current=current_identity)
    current_tuple_hash = compute_tuple_hash(current_identity)
    if mismatches or str(baseline_contract.get("tupleHash") or "") != current_tuple_hash:
        mismatch_reason = (
            f"{command_name} refused to continue because live tupleHash={current_tuple_hash} "
            f"does not match baseline tupleHash={baseline_contract.get('tupleHash')}"
        )
        _record_session_invalidation(
            runtime_dir=runtime_dir,
            baseline_path=baseline_path,
            baseline_contract=baseline_contract,
            reason=mismatch_reason,
        )
        raise RuntimeError(mismatch_reason)
    return {
        "baseline": baseline_contract,
        "session": session,
        "currentIdentity": current_identity,
        "currentTupleHash": current_tuple_hash,
    }


def run_preflight(api: BackendApi, *, baseline_path: str, runtime_dir: str | None = None) -> dict[str, Any]:
    gate = _enforce_runtime_contract(
        api,
        baseline_path=baseline_path,
        runtime_dir=runtime_dir,
        command_name="preflight",
        allowed_states={"baseline_frozen", "day0_ready"},
    )
    baseline_identity = gate["baseline"]
    current_identity = collect_runtime_identity(api, baseline_path=baseline_path)
    current_identity["baselineGeneratedAt"] = _baseline_generated_at(baseline_identity)
    snapshot = metrics_snapshot(api)
    settings = snapshot.get("settings") or {}
    mismatches = compare_identity_tuple(baseline=baseline_identity, current=current_identity)
    shadow_off = bool(settings.get("latestJudgmentsShadowOff"))
    backfill_paused = bool(settings.get("backfillPaused"))
    backend_started_by_installed_app = bool(current_identity.get("backendStartedByInstalledApp"))
    endpoints_reachable = True
    checks = [
        {"name": "settings main-chain-stability reachable", "passed": True},
        {"name": "runtime analysis-migration-metrics reachable", "passed": True},
        {"name": "latestJudgmentsShadowOff=true", "passed": shadow_off},
        {"name": "backfillPaused=false", "passed": not backfill_paused},
        {"name": "backendStartedByInstalledApp=true", "passed": backend_started_by_installed_app},
        {"name": "identity tuple matches baseline", "passed": not mismatches},
    ]
    payload = {
        "recordedAt": iso_now(),
        "baseUrl": api.base_url,
        "baselinePath": str(Path(baseline_path).expanduser().resolve()),
        "runtimeDir": str(_ensure_runtime_dir(runtime_dir)),
        "baselineIdentity": baseline_identity,
        "currentIdentity": current_identity,
        "mismatches": mismatches,
        "identityMatchesBaseline": not mismatches,
        "endpointsReachable": endpoints_reachable,
        "latestJudgmentsShadowOff": shadow_off,
        "backfillPaused": backfill_paused,
        "checks": checks,
        "installedApp": inspect_installed_app(),
        "readyForDay0": endpoints_reachable and shadow_off and not backfill_paused and backend_started_by_installed_app and not mismatches,
    }
    payload = attach_artifact_contract(payload, baseline_identity)
    next_state = "day0_ready" if payload["readyForDay0"] else str(gate["session"].get("state") or "baseline_frozen")
    _transition_session_state(
        runtime_dir=runtime_dir,
        session=gate["session"],
        state=next_state,
        baseline=baseline_identity,
    )
    return payload


def verify_db_isolation(
    api: BackendApi,
    *,
    repo_root: Path | None = None,
    home_dir: Path | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    root = (repo_root or DEFAULT_REPO_ROOT).resolve()
    current_identity = collect_runtime_identity(api)
    live_database_path = str(current_identity.get("databasePath") or "").strip()
    expected_database_path = _expected_installed_runtime_database_path(home_dir=home_dir)
    live_database_matches = bool(live_database_path) and Path(live_database_path).expanduser().resolve() == expected_database_path

    required_test_evidence: list[dict[str, Any]] = []
    missing_evidence: list[str] = []
    for item in DB_ISOLATION_REQUIRED_PATTERNS:
        target = (root / item["path"]).resolve()
        found = target.is_file() and bool(item["pattern"].search(_read_text(target)))
        required_test_evidence.append(
            {
                "label": item["label"],
                "path": _repo_relative_display(target, root),
                "description": item["description"],
                "found": found,
            }
        )
        if not found:
            missing_evidence.append(f"缺少静态证据：{item['label']}")

    tmp_db_pattern_hits: list[str] = []
    tests_root = root / "backend" / "tests"
    if tests_root.exists():
        for path in sorted(tests_root.rglob("*.py")):
            if TMP_DB_PATTERN.search(_read_text(path)):
                tmp_db_pattern_hits.append(_repo_relative_display(path, root))
    if not tmp_db_pattern_hits:
        missing_evidence.append('未找到 Database(tmp_path / "app.db") 的测试静态证据。')
    if not live_database_matches:
        missing_evidence.append(
            f"live backend databasePath 不是 installed-runtime app.db：{live_database_path or 'null'}"
        )

    ready_for_baseline_regeneration = (
        live_database_matches
        and all(bool(item["found"]) for item in required_test_evidence)
        and bool(tmp_db_pattern_hits)
    )
    summary_parts = [
        "live backend 仍指向 installed-runtime app.db" if live_database_matches else "live backend databasePath 与 installed-runtime app.db 不一致",
        'pytest/smoke 已证明走 tmp_path / "data"' if all(bool(item["found"]) for item in required_test_evidence) else '仍缺少 create_app(tmp_path / "data") 静态证据',
        '已发现 Database(tmp_path / "app.db") 临时库证据' if tmp_db_pattern_hits else '仍缺少 Database(tmp_path / "app.db") 临时库证据',
    ]
    payload = {
        "recordedAt": iso_now(),
        "repoRoot": str(root),
        "baseUrl": api.base_url,
        "liveDatabasePath": live_database_path or None,
        "expectedInstalledRuntimeDatabasePath": str(expected_database_path),
        "liveDatabaseMatchesInstalledRuntime": live_database_matches,
        "requiredTestEvidence": required_test_evidence,
        "temporaryDbPattern": 'Database(tmp_path / "app.db")',
        "temporaryDbPatternHits": tmp_db_pattern_hits,
        "missingEvidence": missing_evidence,
        "summary": "；".join(summary_parts),
        "readyForBaselineRegeneration": ready_for_baseline_regeneration,
    }
    target_output = (
        Path(output_path).expanduser().resolve()
        if output_path
        else _ensure_runtime_dir() / "db-isolation-check.json"
    )
    write_output(str(target_output), payload)
    return payload


def _event_line_task_count(workspace: dict[str, Any]) -> int:
    related_tasks = workspace.get("relatedTasks") or []
    return sum(
        1
        for item in related_tasks
        if isinstance(item, dict) and (str(item.get("eventLineId") or "").strip() or str(item.get("eventLineName") or "").strip())
    )


def _representation_flags(workspace: dict[str, Any], cockpit: dict[str, Any]) -> dict[str, bool]:
    knowledge_status = workspace.get("knowledgeStatus") or {}
    document_count = max(
        len(workspace.get("documentCards") or []),
        int(knowledge_status.get("totalDocuments") or 0),
    )
    meeting_count = len(workspace.get("meetings") or [])
    event_line_task_count = _event_line_task_count(workspace)
    radar_candidates = len(((cockpit.get("radarLayer") or {}).get("candidateJudgments") or []))
    official_ready = str(cockpit.get("officialLayerStatus") or "") == "ready"
    return {
        "documentRich": document_count >= 3,
        "meetingOrEventLineRich": meeting_count > 0 or event_line_task_count > 0,
        "cockpitRich": official_ready or radar_candidates > 0,
    }


def _context_count(workspace: dict[str, Any]) -> int:
    return len(workspace.get("documentCards") or []) + len(workspace.get("meetings") or []) + len(workspace.get("relatedTasks") or [])


def _coverage_categories(assessment: dict[str, Any]) -> set[str]:
    categories = set()
    flags = assessment.get("representation") or {}
    if flags.get("documentRich"):
        categories.add("documents")
    if flags.get("meetingOrEventLineRich"):
        categories.add("meetings_or_event_lines")
    if flags.get("cockpitRich"):
        categories.add("cockpit")
    return categories


def assess_day0_candidates(api: BackendApi, *, candidate_ids: list[str]) -> dict[str, Any]:
    ordered_candidates = [item for item in candidate_ids if str(item or "").strip()]
    assessments: list[dict[str, Any]] = []
    for priority_index, client_id in enumerate(ordered_candidates):
        try:
            workspace = api.get_workspace(client_id)
            cockpit = api.get_cockpit(client_id)
        except Exception as exc:
            assessments.append(
                {
                    "clientId": client_id,
                    "priorityIndex": priority_index,
                    "healthy": False,
                    "reason": str(exc),
                    "healthReason": f"淘汰：workspace/cockpit 请求失败，{exc}",
                }
            )
            continue
        representation = _representation_flags(workspace, cockpit)
        knowledge_ready = candidate_is_knowledge_ready(workspace)
        has_context = _context_count(workspace) > 0
        health_reasons: list[str] = []
        if not knowledge_ready:
            health_reasons.append("knowledgeReady=false")
        if not has_context:
            health_reasons.append("上下文为空")
        if health_reasons:
            health_reason = f"淘汰：{'；'.join(health_reasons)}"
        else:
            health_reason = (
                "候选健康：workspace/cockpit 200，knowledgeReady=true，"
                f"documentCount={max(len(workspace.get('documentCards') or []), int(((workspace.get('knowledgeStatus') or {}).get('totalDocuments') or 0)))}，"
                f"meetingCount={len(workspace.get('meetings') or [])}，taskCount={len(workspace.get('relatedTasks') or [])}"
            )
        coverage_categories = sorted(_coverage_categories({"representation": representation}))
        assessment = {
            "clientId": client_id,
            "priorityIndex": priority_index,
            "healthy": knowledge_ready and has_context,
            "reason": None,
            "healthReason": health_reason,
            "representationReason": None,
            "knowledgeReady": knowledge_ready,
            "hasContext": has_context,
            "documentCount": max(
                len(workspace.get("documentCards") or []),
                int(((workspace.get("knowledgeStatus") or {}).get("totalDocuments") or 0)),
            ),
            "meetingCount": len(workspace.get("meetings") or []),
            "taskCount": len(workspace.get("relatedTasks") or []),
            "eventLineTaskCount": _event_line_task_count(workspace),
            "officialLayerStatus": cockpit.get("officialLayerStatus"),
            "candidateJudgmentCount": len(((cockpit.get("radarLayer") or {}).get("candidateJudgments") or [])),
            "representation": representation,
            "coverageCategories": coverage_categories,
        }
        assessments.append(assessment)

    healthy = [item for item in assessments if item.get("healthy")]
    selected: list[dict[str, Any]] = []
    covered: set[str] = set()
    selection_reasons: dict[str, str] = {}
    representation_reasons: dict[str, str] = {}
    remaining = healthy.copy()
    while remaining and len(selected) < 3:
        ranked = sorted(
            remaining,
            key=lambda item: (
                -len(_coverage_categories(item) - covered),
                item["priorityIndex"],
            ),
        )
        choice = ranked[0]
        new_categories = sorted(_coverage_categories(choice) - covered)
        representation_reasons[choice["clientId"]] = (
            f"补齐 {' / '.join(new_categories)} 代表性"
            if new_categories
            else "代表性已满足，按固定优先级补齐 cohort"
        )
        selection_reasons[choice["clientId"]] = f"入选：健康，且{representation_reasons[choice['clientId']]}"
        selected.append(choice)
        covered.update(_coverage_categories(choice))
        remaining = [item for item in remaining if item["clientId"] != choice["clientId"]]

    control_priority_index = {client_id: index for index, client_id in enumerate(DEFAULT_CONTROL_PRIORITY)}

    def control_sort_key(item: dict[str, Any]) -> tuple[int, int]:
        richness_score = (
            item.get("documentCount", 0)
            + item.get("meetingCount", 0) * 5
            + item.get("eventLineTaskCount", 0) * 5
            + (10 if item.get("officialLayerStatus") == "ready" else 0)
            + item.get("candidateJudgmentCount", 0) * 2
        )
        return (-richness_score, control_priority_index.get(item["clientId"], 999))

    control_client_id = sorted(selected, key=control_sort_key)[0]["clientId"] if selected else None
    control_client_reason = (
        "选为 control client：在已入选 cohort 中上下文最复杂，最适合做 workspace / cockpit / 安装版对照"
        if control_client_id
        else None
    )
    selected_client_ids = {item["clientId"] for item in selected}
    for assessment in assessments:
        client_id = assessment["clientId"]
        assessment["selected"] = client_id in selected_client_ids
        if assessment["selected"]:
            assessment["selectionReason"] = selection_reasons.get(client_id, "入选：健康")
            assessment["representationReason"] = representation_reasons.get(client_id, "代表性已满足")
        elif assessment.get("healthy"):
            assessment["selectionReason"] = "淘汰：虽然健康，但 cohort 已覆盖所需代表性"
            assessment["representationReason"] = "代表性已被已入选 cohort 覆盖"
        else:
            assessment["selectionReason"] = assessment.get("healthReason") or "淘汰：未通过健康检查"
            coverage_categories = assessment.get("coverageCategories") or []
            assessment["representationReason"] = (
                f"具备 {' / '.join(coverage_categories)} 代表性，但未通过健康门槛"
                if coverage_categories
                else "未通过健康门槛，未进入代表性比较"
            )
    represented_categories = sorted(covered)
    return {
        "recordedAt": iso_now(),
        "baseUrl": api.base_url,
        "candidatePriority": ordered_candidates,
        "assessments": assessments,
        "selectedClients": [item["clientId"] for item in selected],
        "selectedAssessments": selected,
        "representedCategories": represented_categories,
        "representationReady": len(represented_categories) >= 2,
        "controlClientId": control_client_id,
        "controlClientReason": control_client_reason,
        "readyForDay0": len(selected) >= 3 and len(represented_categories) >= 2,
    }


def capture_git_artifacts(*, runtime_dir: str | Path | None = None, repo_root: Path | None = None) -> dict[str, Any]:
    root = (repo_root or DEFAULT_REPO_ROOT).resolve()
    target_dir = _ensure_runtime_dir(runtime_dir) / "git"
    target_dir.mkdir(parents=True, exist_ok=True)

    commands = {
        "head.txt": ["git", "-C", str(root), "rev-parse", "HEAD"],
        "status.porcelain.txt": ["git", "-C", str(root), "status", "--porcelain"],
        "diff.stat.txt": ["git", "-C", str(root), "diff", "--stat"],
        "diff.patch": ["git", "-C", str(root), "diff"],
    }
    results: dict[str, str] = {}
    for filename, command in commands.items():
        returncode, stdout, stderr = _run_command(command)
        if returncode != 0:
            raise RuntimeError(stderr.strip() or f"failed to run {' '.join(command)}")
        rendered = stdout if stdout.endswith("\n") or not stdout else f"{stdout}\n"
        file_path = target_dir / filename
        file_path.write_text(rendered, encoding="utf-8")
        results[filename] = str(file_path)
    return {
        "recordedAt": iso_now(),
        "repoRoot": str(root),
        "runtimeDir": str(target_dir.parent),
        "artifacts": results,
    }


def _note_output_path(observation_path: str) -> Path:
    source = Path(observation_path).expanduser().resolve()
    if source.suffix == ".json":
        return source.with_name(f"{source.stem}.note.json")
    return source.with_name(f"{source.name}.note.json")


def write_observation_note(
    api: BackendApi,
    *,
    baseline_path: str,
    runtime_dir: str | None = None,
    observation_path: str,
    control_client_id: str,
    operator_note: str,
    output_path: str | None,
) -> dict[str, Any]:
    baseline_identity = _load_baseline_contract(baseline_path)
    _ensure_session_for_baseline(runtime_dir=runtime_dir, baseline=baseline_identity, baseline_path=baseline_path)
    current_identity = collect_runtime_identity(api, baseline_path=baseline_path)
    current_identity["baselineGeneratedAt"] = _baseline_generated_at(baseline_identity)
    mismatches = compare_identity_tuple(baseline=baseline_identity, current=current_identity)
    payload = {
        "recordedAt": iso_now(),
        "baselineGeneratedAt": _baseline_generated_at(baseline_identity),
        "commitSha": current_identity.get("commitSha"),
        "backendUrl": current_identity.get("backendUrl"),
        "buildVersion": current_identity.get("buildVersion"),
        "databasePath": current_identity.get("databasePath"),
        "latestJudgmentsShadowOff": current_identity.get("latestJudgmentsShadowOff"),
        "dirtyWorktree": current_identity.get("dirtyWorktree"),
        "dirtyPaths": current_identity.get("dirtyPaths"),
        "installedRuntimeSignature": current_identity.get("installedRuntimeSignature"),
        "controlClientId": control_client_id,
        "operatorNote": operator_note.strip(),
        "observationPath": str(Path(observation_path).expanduser().resolve()),
        "baselinePath": str(Path(baseline_path).expanduser().resolve()),
        "identityMatchesBaseline": not mismatches,
        "mismatches": mismatches,
    }
    payload = attach_artifact_contract(payload, baseline_identity)
    write_output(str(Path(output_path).expanduser().resolve()) if output_path else str(_note_output_path(observation_path)), payload)
    return payload


def write_selection_note(
    *,
    baseline_path: str,
    runtime_dir: str | None = None,
    selection_path: str,
    output_path: str | None,
) -> dict[str, Any]:
    baseline_identity = _load_baseline_contract(baseline_path)
    _ensure_session_for_baseline(runtime_dir=runtime_dir, baseline=baseline_identity, baseline_path=baseline_path)
    selection_payload = load_json(selection_path)
    entries = [
        {
            "clientId": item.get("clientId"),
            "selected": bool(item.get("selected")),
            "reason": item.get("selectionReason") or item.get("healthReason") or item.get("reason") or "未填写",
            "healthReason": item.get("healthReason"),
            "representationReason": item.get("representationReason"),
        }
        for item in (selection_payload.get("assessments") or [])
        if isinstance(item, dict)
    ]
    payload = {
        "recordedAt": iso_now(),
        "baselineGeneratedAt": _baseline_generated_at(baseline_identity),
        "backendUrl": baseline_identity.get("backendUrl"),
        "installedRuntimeSignature": baseline_identity.get("installedRuntimeSignature"),
        "selectionPath": str(Path(selection_path).expanduser().resolve()),
        "controlClientId": selection_payload.get("controlClientId"),
        "controlClientReason": selection_payload.get("controlClientReason"),
        "readyForDay0": bool(selection_payload.get("readyForDay0")),
        "representedCategories": selection_payload.get("representedCategories") or [],
        "entries": entries,
    }
    payload = attach_artifact_contract(payload, baseline_identity)
    target_output = Path(output_path).expanduser().resolve() if output_path else Path(selection_path).expanduser().resolve().with_name("day0-selection.note.json")
    write_output(str(target_output), payload)
    return payload


def write_install_evidence(
    api: BackendApi,
    *,
    baseline_path: str,
    runtime_dir: str | None = None,
    phase: str,
    status: str,
    app_starts: bool,
    backend_started_by_installed_app: bool,
    overview_panel_visible: bool,
    shadow_off_parity: bool,
    workspace_boundary_correct: bool,
    cockpit_official_layer_tone_correct: bool,
    overview_metrics_populated: bool,
    overview_screenshot: str,
    workspace_screenshot: str,
    cockpit_screenshot: str,
    overview_page_proof: str,
    workspace_page_proof: str,
    cockpit_page_proof: str,
    summary: str,
    manual_backend_recovery_used: bool,
    workaround_required: bool,
    control_client_id: str | None,
    output_path: str | None,
) -> dict[str, Any]:
    allowed_states = {"baseline_frozen", "day0_ready", "wave2_active", "step_b_ready"}
    if phase == "step-b":
        allowed_states = {"wave2_active", "step_b_ready"}
    gate = _enforce_runtime_contract(
        api,
        baseline_path=baseline_path,
        runtime_dir=runtime_dir,
        command_name="write-install-evidence",
        allowed_states=allowed_states,
    )
    baseline_identity = gate["baseline"]
    page_proofs = {
        "overview": _validate_page_proof_contract(
            overview_page_proof,
            baseline_hash=baseline_identity.get("baselineHash"),
            tuple_hash=baseline_identity.get("tupleHash"),
            session_id=baseline_identity.get("sessionId"),
            expected_page="overview",
        ),
        "workspace": _validate_page_proof_contract(
            workspace_page_proof,
            baseline_hash=baseline_identity.get("baselineHash"),
            tuple_hash=baseline_identity.get("tupleHash"),
            session_id=baseline_identity.get("sessionId"),
            expected_page="workspace-state",
        ),
        "cockpit": _validate_page_proof_contract(
            cockpit_page_proof,
            baseline_hash=baseline_identity.get("baselineHash"),
            tuple_hash=baseline_identity.get("tupleHash"),
            session_id=baseline_identity.get("sessionId"),
            expected_page="cockpit",
        ),
    }
    if phase == "step-a" and status == "pass":
        required_checks = {
            "appStarts": app_starts,
            "backendStartedByInstalledApp": backend_started_by_installed_app,
            "overviewPanelVisible": overview_panel_visible,
            "shadowOffParity": shadow_off_parity,
            "workspaceBoundaryCorrect": workspace_boundary_correct,
            "cockpitOfficialLayerToneCorrect": cockpit_official_layer_tone_correct,
            "overviewMetricsPopulated": overview_metrics_populated,
        }
        missing = [name for name, enabled in required_checks.items() if not enabled]
        if missing:
            raise RuntimeError(f"step-a pass requires all installed-runtime checks: missing {', '.join(missing)}")
        if manual_backend_recovery_used or workaround_required:
            reasons: list[str] = []
            if manual_backend_recovery_used:
                reasons.append("manualBackendRecoveryUsed=true")
            if workaround_required:
                reasons.append("workaroundRequired=true")
            raise RuntimeError(
                "step-a pass forbids manual backend recovery or extra workaround: "
                + ", ".join(reasons)
            )
    if phase == "step-b" and status == "pass":
        required_checks = {
            "appStarts": app_starts,
            "backendStartedByInstalledApp": backend_started_by_installed_app,
            "shadowOffParity": shadow_off_parity,
        }
        missing = [name for name, enabled in required_checks.items() if not enabled]
        if missing:
            raise RuntimeError(f"step-b pass requires installed runtime parity: missing {', '.join(missing)}")
    current_identity = collect_runtime_identity(api, baseline_path=baseline_path)
    current_identity["baselineGeneratedAt"] = _baseline_generated_at(baseline_identity)
    mismatches = compare_identity_tuple(baseline=baseline_identity, current=current_identity)
    target_output = (
        Path(output_path).expanduser().resolve()
        if output_path
        else DEFAULT_RUNTIME_DIR / f"install-{phase.lower()}.json"
    )
    payload = {
        "recordedAt": iso_now(),
        "phase": phase,
        "status": status,
        "appStarts": app_starts,
        "backendStartedByInstalledApp": backend_started_by_installed_app,
        "overviewPanelVisible": overview_panel_visible,
        "shadowOffParity": shadow_off_parity,
        "workspaceBoundaryCorrect": workspace_boundary_correct,
        "cockpitOfficialLayerToneCorrect": cockpit_official_layer_tone_correct,
        "overviewMetricsPopulated": overview_metrics_populated,
        "summary": summary,
        "manualBackendRecoveryUsed": manual_backend_recovery_used,
        "workaroundRequired": workaround_required,
        "controlClientId": control_client_id,
        "screenshots": {
            "overview": overview_screenshot,
            "workspace": workspace_screenshot,
            "cockpit": cockpit_screenshot,
        },
        "pageProofs": {
            "overview": str(Path(overview_page_proof).expanduser().resolve()),
            "workspace": str(Path(workspace_page_proof).expanduser().resolve()),
            "cockpit": str(Path(cockpit_page_proof).expanduser().resolve()),
        },
        "baselineGeneratedAt": _baseline_generated_at(baseline_identity),
        "commitSha": current_identity.get("commitSha"),
        "backendUrl": current_identity.get("backendUrl"),
        "buildVersion": current_identity.get("buildVersion"),
        "databasePath": current_identity.get("databasePath"),
        "latestJudgmentsShadowOff": current_identity.get("latestJudgmentsShadowOff"),
        "dirtyWorktree": current_identity.get("dirtyWorktree"),
        "dirtyPaths": current_identity.get("dirtyPaths"),
        "installedRuntimeSignature": current_identity.get("installedRuntimeSignature"),
        "identityMatchesBaseline": not mismatches,
        "mismatches": mismatches,
    }
    payload = attach_artifact_contract(payload, baseline_identity)
    write_output(str(target_output), payload)
    if phase == "step-b":
        _transition_session_state(
            runtime_dir=runtime_dir,
            session=gate["session"],
            state="step_b_ready",
            baseline=baseline_identity,
        )
    return payload


def write_install_note(
    *,
    baseline_path: str,
    runtime_dir: str | None = None,
    phase: str,
    blocker_class: str,
    decision: str,
    reason: str,
    evidence_path: str | None,
    output_path: str | None,
) -> dict[str, Any]:
    baseline_identity = _load_baseline_contract(baseline_path)
    _ensure_session_for_baseline(runtime_dir=runtime_dir, baseline=baseline_identity, baseline_path=baseline_path)
    if decision == "pass" and blocker_class != "none":
        raise RuntimeError("install note pass requires blockerClass=none")
    if decision == "fail" and blocker_class == "none":
        raise RuntimeError("install note fail requires blockerClass=packaging or main-chain")
    if phase == "step-a" and evidence_path:
        evidence_payload = load_json(evidence_path)
        if str(evidence_payload.get("baselineHash") or "") != str(baseline_identity.get("baselineHash") or ""):
            raise RuntimeError("install note evidence baselineHash mismatch")
        if str(evidence_payload.get("sessionId") or "") != str(baseline_identity.get("sessionId") or ""):
            raise RuntimeError("install note evidence sessionId mismatch")
        packaging_failure = (
            not bool(evidence_payload.get("backendStartedByInstalledApp"))
            or bool(evidence_payload.get("manualBackendRecoveryUsed"))
            or bool(evidence_payload.get("workaroundRequired"))
        )
        if packaging_failure and (decision != "fail" or blocker_class != "packaging"):
            raise RuntimeError(
                "step-a evidence with manual backend recovery/workaround/non-installed-runtime listener "
                "must be recorded as decision=fail and blockerClass=packaging"
            )
    payload = {
        "recordedAt": iso_now(),
        "phase": phase,
        "blockerClass": blocker_class,
        "decision": decision,
        "reason": reason.strip(),
        "baselineGeneratedAt": _baseline_generated_at(baseline_identity),
        "commitSha": baseline_identity.get("commitSha"),
        "backendUrl": baseline_identity.get("backendUrl"),
        "buildVersion": baseline_identity.get("buildVersion"),
        "databasePath": baseline_identity.get("databasePath"),
        "latestJudgmentsShadowOff": baseline_identity.get("latestJudgmentsShadowOff"),
        "dirtyWorktree": baseline_identity.get("dirtyWorktree"),
        "dirtyPaths": baseline_identity.get("dirtyPaths"),
        "installedRuntimeSignature": baseline_identity.get("installedRuntimeSignature"),
        "evidencePath": str(Path(evidence_path).expanduser().resolve()) if evidence_path else None,
    }
    payload = attach_artifact_contract(payload, baseline_identity)
    target_output = (
        Path(output_path).expanduser().resolve()
        if output_path
        else _ensure_runtime_dir() / f"install-{phase}.note.json"
    )
    write_output(str(target_output), payload)
    return payload


def _normalize_inherited_failures(entries: list[Any] | None) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for raw in entries or []:
        entry = raw
        if isinstance(raw, str):
            stripped = raw.strip()
            if not stripped:
                continue
            entry = json.loads(stripped)
        if not isinstance(entry, dict):
            raise RuntimeError("inherited failure entries must be objects with test/cluster/reason")
        test = str(entry.get("test") or "").strip()
        cluster = str(entry.get("cluster") or "").strip()
        reason = str(entry.get("reason") or "").strip()
        if not test or not cluster or not reason:
            raise RuntimeError("inherited failure entries require non-empty test, cluster, and reason")
        normalized.append({"test": test, "cluster": cluster, "reason": reason})
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in normalized:
        key = (item["test"], item["cluster"], item["reason"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _extract_pytest_failures_from_log(log_path: Path | None) -> list[str]:
    if log_path is None or not log_path.is_file():
        return []
    failures: list[str] = []
    for line in _read_text(log_path).splitlines():
        stripped = line.strip()
        if stripped.startswith("FAILED "):
            nodeid = stripped.removeprefix("FAILED ").split(" - ", 1)[0].strip()
            failures.append(nodeid)
    return _dedupe_preserve_order(failures)


def write_full_smoke_classification(
    *,
    source_path: str | None,
    log_path: str | None,
    pytest_exit_code: int | None,
    full_smoke_summary: str | None,
    failures: list[str] | None,
    rc_blocking_failures: list[str] | None,
    inherited_failures: list[Any] | None,
    classification_reason: str | None,
    output_path: str | None,
) -> dict[str, Any]:
    source_payload = load_json(source_path) if source_path else {}
    resolved_log_path = (
        Path(log_path).expanduser().resolve()
        if log_path
        else Path(str(source_payload.get("logPath"))).expanduser().resolve()
        if source_payload.get("logPath")
        else None
    )
    normalized_inherited = _normalize_inherited_failures(
        inherited_failures if inherited_failures is not None else source_payload.get("inheritedFailures")
    )
    normalized_rc_blocking = _dedupe_preserve_order(
        rc_blocking_failures if rc_blocking_failures is not None else source_payload.get("rcBlockingFailures")
    )
    overlap = sorted({item["test"] for item in normalized_inherited} & set(normalized_rc_blocking))
    if overlap:
        raise RuntimeError(
            "the same failure cannot be both inherited and RC blocking: " + ", ".join(overlap)
        )
    explicit_failures = failures if failures is not None else source_payload.get("failures")
    normalized_failures = _dedupe_preserve_order(explicit_failures)
    if not normalized_failures:
        normalized_failures = _extract_pytest_failures_from_log(resolved_log_path)
    for test_name in normalized_rc_blocking:
        if test_name not in normalized_failures:
            normalized_failures.append(test_name)
    for item in normalized_inherited:
        if item["test"] not in normalized_failures:
            normalized_failures.append(item["test"])

    resolved_summary = str(full_smoke_summary or source_payload.get("fullSmokeSummary") or "").strip()
    if not resolved_summary:
        raise RuntimeError("write-full-smoke-classification requires fullSmokeSummary")
    resolved_reason = str(
        classification_reason
        or source_payload.get("classificationReason")
        or DEFAULT_FULL_SMOKE_CLASSIFICATION_REASON
    ).strip()
    if not normalized_failures and (pytest_exit_code or source_payload.get("pytestExitCode")):
        raise RuntimeError("write-full-smoke-classification requires failures when pytest exit code is non-zero")

    payload = {
        "recordedAt": iso_now(),
        "pytestExitCode": pytest_exit_code if pytest_exit_code is not None else source_payload.get("pytestExitCode"),
        "logPath": str(resolved_log_path) if resolved_log_path else None,
        "fullSmokeSummary": resolved_summary,
        "failures": normalized_failures,
        "rcBlockingFailures": normalized_rc_blocking,
        "inheritedFailures": normalized_inherited,
        "classificationReason": resolved_reason,
        "canRegenerateBaseline": not normalized_rc_blocking,
    }
    target_output = (
        Path(output_path).expanduser().resolve()
        if output_path
        else _ensure_runtime_dir() / "full-smoke-classification.json"
    )
    write_output(str(target_output), payload)
    return payload


def write_phase_b_decision(
    api: BackendApi,
    *,
    baseline_path: str,
    runtime_dir: str | None = None,
    observation_path: str,
    manual_path: str,
    blocker_class: str,
    output_path: str | None,
) -> dict[str, Any]:
    gate = _enforce_runtime_contract(
        api,
        baseline_path=baseline_path,
        runtime_dir=runtime_dir,
        command_name="write-phase-b-decision",
        allowed_states={"step_b_ready"},
    )
    baseline_contract = gate["baseline"]
    raw_observation = load_json(observation_path)
    observation = load_observation_payload(observation_path)
    observation_contract = raw_observation if isinstance(raw_observation, dict) and raw_observation.get("baselineHash") else observation
    if str(observation_contract.get("baselineHash") or "") != str(baseline_contract.get("baselineHash") or ""):
        raise RuntimeError("phase-b observation baselineHash mismatch")
    if str(observation_contract.get("sessionId") or "") != str(baseline_contract.get("sessionId") or ""):
        raise RuntimeError("phase-b observation sessionId mismatch")
    manual = load_json(manual_path)
    if str(manual.get("baselineHash") or "") != str(baseline_contract.get("baselineHash") or ""):
        raise RuntimeError("phase-b manual baselineHash mismatch")
    if str(manual.get("sessionId") or "") != str(baseline_contract.get("sessionId") or ""):
        raise RuntimeError("phase-b manual sessionId mismatch")
    install_validation = manual.get("installValidation") or {}
    install_evidence = install_validation.get("evidenceScreenshots") or {}
    install_page_proofs = install_validation.get("evidencePageProofs") or {}
    scenes = [item for item in (manual.get("scenes") or []) if isinstance(item, dict)]
    reviewers = [item for item in (manual.get("reviewers") or []) if isinstance(item, dict)]
    next_decision = manual.get("nextDecision") or {}
    judgment_consistency = manual.get("judgmentConsistency") or {}

    confirmed_feedback_union = {
        "boundaryClear": False,
        "taskContextSharper": False,
        "meetingCapturesUnresolved": False,
        "cockpitAvoidsFakeConclusion": False,
    }
    for reviewer in reviewers:
        feedback = reviewer.get("feedback") or {}
        for key in confirmed_feedback_union:
            confirmed_feedback_union[key] = confirmed_feedback_union[key] or bool(feedback.get(key))

    install_closure_pass = (
        str(install_validation.get("status") or "").strip() == "pass"
        and bool(install_validation.get("appStarts"))
        and bool(install_validation.get("backendStartedByInstalledApp"))
        and bool(install_validation.get("overviewPanelVisible"))
        and bool(install_validation.get("shadowOffParity"))
        and bool(install_validation.get("workspaceBoundaryCorrect"))
        and bool(install_validation.get("cockpitOfficialLayerToneCorrect"))
        and bool(install_validation.get("overviewMetricsPopulated"))
        and all(str(install_evidence.get(key) or "").strip() for key in ("overview", "workspace", "cockpit"))
        and all(
            _validate_page_proof_contract(
                str(install_page_proofs.get(key) or ""),
                baseline_hash=baseline_contract.get("baselineHash"),
                tuple_hash=baseline_contract.get("tupleHash"),
                session_id=baseline_contract.get("sessionId"),
                expected_page={"overview": "overview", "workspace": "workspace-state", "cockpit": "cockpit"}[key],
            )
            for key in ("overview", "workspace", "cockpit")
        )
    )
    scenes_confirmed = bool(scenes) and all(
        bool(item.get("confirmed"))
        and _validate_page_proof_contract(
            str(((item.get("evidence") or {}).get("pageProofPath") or "")),
            baseline_hash=baseline_contract.get("baselineHash"),
            tuple_hash=baseline_contract.get("tupleHash"),
            session_id=baseline_contract.get("sessionId"),
        )
        for item in scenes
    )
    business_feedback_complete = all(confirmed_feedback_union.values())
    judgment_consistency_stable = str(judgment_consistency.get("status") or "").strip() == "稳定"
    run_completion_pass = str(manual.get("runCompletionStatus") or observation.get("verdict") or "").strip() == "pass"

    conditions_met = {
        "runCompletionPass": run_completion_pass,
        "installClosurePass": install_closure_pass,
        "scenesConfirmed": scenes_confirmed,
        "businessFeedbackComplete": business_feedback_complete,
        "judgmentConsistencyStable": judgment_consistency_stable,
    }

    blocking_reasons: list[str] = []
    if not run_completion_pass:
        blocking_reasons.append("运行完成态不是 pass")
    if not install_closure_pass:
        blocking_reasons.append("安装版闭环未通过")
    if not scenes_confirmed:
        blocking_reasons.append("4 个场景的截图与前后对照未收齐")
    if not business_feedback_complete:
        blocking_reasons.append("业务同事反馈还未覆盖 4 个关键判断点")
    if not judgment_consistency_stable:
        blocking_reasons.append("主链判断口径还未达到稳定")
    if blocker_class != "none":
        blocking_reasons.append(f"存在 blockerClass={blocker_class}")
    for item in next_decision.get("blockedBy") or []:
        reason = str(item).strip()
        if reason and reason not in blocking_reasons:
            blocking_reasons.append(reason)
    if not bool(next_decision.get("canEnterV04")) and "manual nextDecision.canEnterV04=false" not in blocking_reasons:
        blocking_reasons.append("manual nextDecision.canEnterV04=false")

    run_completion_status = str(manual.get("runCompletionStatus") or observation.get("verdict") or "").strip() or "watch"
    payload = {
        "recordedAt": iso_now(),
        "baselinePath": str(Path(baseline_path).expanduser().resolve()),
        "observationPath": str(Path(observation_path).expanduser().resolve()),
        "manualPath": str(Path(manual_path).expanduser().resolve()),
        "runCompletionStatus": run_completion_status,
        "mainChainJudgmentStability": "stable" if judgment_consistency_stable else "unstable",
        "allowEnterPhaseB": all(conditions_met.values()) and not blocking_reasons,
        "conditionsMet": conditions_met,
        "blockingReasons": blocking_reasons,
        "blockerClass": blocker_class,
    }
    payload = attach_artifact_contract(payload, baseline_contract)
    target_output = (
        Path(output_path).expanduser().resolve()
        if output_path
        else _ensure_runtime_dir() / "phase-b-decision.json"
    )
    write_output(str(target_output), payload)
    _transition_session_state(
        runtime_dir=runtime_dir,
        session=gate["session"],
        state="completed" if bool(payload.get("allowEnterPhaseB")) else "blocked",
        baseline=baseline_contract,
    )
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Helper CLI for the v0.3.4 RC Wave 2 frozen workflow.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"Backend base URL. Default: {DEFAULT_BASE_URL}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    git_artifacts = subparsers.add_parser("capture-git-artifacts", help="Capture HEAD, status, diff stat, and diff patch into the RC runtime directory.")
    git_artifacts.add_argument("--runtime-dir", help="Optional RC runtime directory override.")

    invalidated = subparsers.add_parser("write-invalidated-artifacts-note", help="Record old baseline/runtime artifacts and stale staging bundles that must not be reused.")
    invalidated.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    invalidated.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    invalidated.add_argument("--source-app", help="Optional source app override. Defaults to dist/mac-arm64 installed build.")
    invalidated.add_argument("--applications-dir", help="Optional Applications directory override for tests.")
    invalidated.add_argument("--output", help="Optional explicit note path.")

    sync_session = subparsers.add_parser("sync-rc-session", help="Sync rc-session.json against install artifacts and the current frozen baseline.")
    sync_session.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    sync_session.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    sync_session.add_argument("--install-receipt", help="Optional install-receipt.json path override.")
    sync_session.add_argument("--install-smoke", help="Optional install-smoke.json path override.")
    sync_session.add_argument("--output", help="Optional explicit JSON output path.")

    preflight = subparsers.add_parser("preflight", help="Check the live identity tuple and Day 0 hard gates against rc-baseline.json.")
    preflight.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    preflight.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    preflight.add_argument("--output", help="Optional JSON output path.")

    db_isolation = subparsers.add_parser("verify-db-isolation", help="Verify pytest/smoke uses tmp_path data while installed-runtime still points at the live app.db.")
    db_isolation.add_argument("--output", help="Optional JSON output path.")

    select_day0 = subparsers.add_parser("select-day0", help="Assess fixed-priority clients for Day 0 health and representation coverage.")
    select_day0.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    select_day0.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    select_day0.add_argument("--client-id", action="append", help="Candidate client id. Repeat to override the default priority list.")
    select_day0.add_argument("--output", help="Optional JSON output path.")

    selection_note = subparsers.add_parser("write-selection-note", help="Write a day0-selection.note.json file from the selection payload.")
    selection_note.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    selection_note.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    selection_note.add_argument("--selection", required=True)
    selection_note.add_argument("--output", help="Optional explicit note path.")

    write_note = subparsers.add_parser("write-note", help="Write an observation sidecar note next to a Wave 2 JSON output.")
    write_note.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    write_note.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    write_note.add_argument("--observation", required=True, help="Path to wave2-day0/dayN JSON output.")
    write_note.add_argument("--control-client-id", required=True)
    write_note.add_argument("--operator-note", required=True, help="One-sentence operator note.")
    write_note.add_argument("--output", help="Optional explicit sidecar path.")

    page_proof = subparsers.add_parser("write-page-proof", help="Write page-proof-*.json from AX/OCR text and a screenshot.")
    page_proof.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    page_proof.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    page_proof.add_argument("--page", required=True, choices=tuple(DEFAULT_PAGE_PROOF_TOKENS.keys()))
    page_proof.add_argument("--screenshot", required=True)
    page_proof.add_argument("--expected-token", action="append", help="Repeat to override default expected tokens.")
    page_proof.add_argument("--ax-text", help="Preferred AX tree extracted text path.")
    page_proof.add_argument("--ocr-text", help="Fallback OCR text path.")
    page_proof.add_argument("--output", help="Optional explicit output path.")

    install = subparsers.add_parser("write-install-evidence", help="Write Step A/Step B install evidence into the RC runtime directory.")
    install.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    install.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    install.add_argument("--phase", required=True, choices=("step-a", "step-b"))
    install.add_argument("--status", required=True, choices=("pass", "watch", "fail"))
    install.add_argument("--app-starts", action="store_true")
    install.add_argument("--backend-started-by-installed-app", action="store_true")
    install.add_argument("--overview-panel-visible", action="store_true")
    install.add_argument("--shadow-off-parity", action="store_true")
    install.add_argument("--workspace-boundary-correct", action="store_true")
    install.add_argument("--cockpit-official-layer-tone-correct", action="store_true")
    install.add_argument("--overview-metrics-populated", action="store_true")
    install.add_argument("--overview-screenshot", required=True)
    install.add_argument("--workspace-screenshot", required=True)
    install.add_argument("--cockpit-screenshot", required=True)
    install.add_argument("--overview-page-proof", required=True)
    install.add_argument("--workspace-page-proof", required=True)
    install.add_argument("--cockpit-page-proof", required=True)
    install.add_argument("--summary", required=True)
    install.add_argument("--manual-backend-recovery-used", action="store_true")
    install.add_argument("--workaround-required", action="store_true")
    install.add_argument("--control-client-id", help="Required for Step B.")
    install.add_argument("--output", help="Optional explicit output path.")

    install_note = subparsers.add_parser("write-install-note", help="Write install-step-a.note.json or install-step-b.note.json with blocker attribution.")
    install_note.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    install_note.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    install_note.add_argument("--phase", required=True, choices=("step-a", "step-b"))
    install_note.add_argument("--blocker-class", required=True, choices=("packaging", "main-chain", "none"))
    install_note.add_argument("--decision", required=True, choices=("pass", "fail"))
    install_note.add_argument("--reason", required=True)
    install_note.add_argument("--evidence", help="Optional install-step-a/install-step-b evidence JSON path.")
    install_note.add_argument("--output", help="Optional explicit note path.")

    phase_b = subparsers.add_parser("write-phase-b-decision", help="Write the external phase-b-decision.json artifact from observation + manual inputs.")
    phase_b.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    phase_b.add_argument("--runtime-dir", help="Optional RC runtime directory override.")
    phase_b.add_argument("--observation", required=True)
    phase_b.add_argument("--manual", required=True)
    phase_b.add_argument("--blocker-class", required=True, choices=("packaging", "main-chain", "none"))
    phase_b.add_argument("--output", help="Optional explicit output path.")

    full_smoke = subparsers.add_parser("write-full-smoke-classification", help="Write or normalize the canonical full-smoke-classification.json artifact.")
    full_smoke.add_argument("--source", help="Optional existing classification JSON to normalize or override.")
    full_smoke.add_argument("--log", help="Optional pytest full smoke log path.")
    full_smoke.add_argument("--pytest-exit-code", type=int, help="Optional pytest exit code for the full smoke run.")
    full_smoke.add_argument("--summary", help="Required unless provided by --source.")
    full_smoke.add_argument("--failure", action="append", help="Full smoke failure nodeid. Repeat this flag.")
    full_smoke.add_argument("--rc-blocking-failure", action="append", help="Failure that blocks the current installed-runtime RC. Repeat this flag.")
    full_smoke.add_argument("--inherited-failure", action="append", help="JSON object string with test, cluster, and reason.")
    full_smoke.add_argument("--classification-reason", help="Optional human-readable explanation of the RC classification boundary.")
    full_smoke.add_argument("--output", help="Optional explicit output path.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    api_needed_commands = {
        "preflight",
        "verify-db-isolation",
        "select-day0",
        "write-note",
        "write-install-evidence",
        "write-phase-b-decision",
    }
    api = BackendApi(args.base_url) if args.command in api_needed_commands else None
    try:
        if args.command == "capture-git-artifacts":
            payload = capture_git_artifacts(runtime_dir=args.runtime_dir)
            write_output(None, payload)
            return 0
        if args.command == "write-invalidated-artifacts-note":
            write_invalidated_artifacts_note(
                runtime_dir=args.runtime_dir,
                baseline_path=args.baseline,
                source_app_path=args.source_app,
                applications_dir=args.applications_dir,
                output_path=args.output,
            )
            return 0
        if args.command == "sync-rc-session":
            sync_rc_session(
                runtime_dir=args.runtime_dir,
                baseline_path=args.baseline,
                install_receipt_path=args.install_receipt,
                install_smoke_path=args.install_smoke,
                output_path=args.output,
            )
            return 0
        if args.command == "preflight":
            if api is None:
                raise RuntimeError("preflight requires backend api")
            payload = run_preflight(api, baseline_path=args.baseline, runtime_dir=args.runtime_dir)
            write_output(args.output, payload)
            return 0
        if args.command == "verify-db-isolation":
            if api is None:
                raise RuntimeError("verify-db-isolation requires backend api")
            verify_db_isolation(api, output_path=args.output)
            return 0
        if args.command == "select-day0":
            if api is None:
                raise RuntimeError("select-day0 requires backend api")
            baseline = _load_baseline_contract(args.baseline)
            _ensure_session_for_baseline(runtime_dir=args.runtime_dir, baseline=baseline, baseline_path=args.baseline)
            if baseline.get("backendUrl") and str(baseline["backendUrl"]).rstrip("/") != api.base_url.rstrip("/"):
                raise RuntimeError("select-day0 base-url does not match the frozen baseline backendUrl")
            payload = attach_artifact_contract(
                assess_day0_candidates(api, candidate_ids=list(args.client_id or DEFAULT_DAY0_PRIORITY)),
                baseline,
            )
            write_output(args.output, payload)
            return 0
        if args.command == "write-selection-note":
            write_selection_note(
                baseline_path=args.baseline,
                runtime_dir=args.runtime_dir,
                selection_path=args.selection,
                output_path=args.output,
            )
            return 0
        if args.command == "write-note":
            if api is None:
                raise RuntimeError("write-note requires backend api")
            write_observation_note(
                api,
                baseline_path=args.baseline,
                runtime_dir=args.runtime_dir,
                observation_path=args.observation,
                control_client_id=args.control_client_id,
                operator_note=args.operator_note,
                output_path=args.output,
            )
            return 0
        if args.command == "write-page-proof":
            write_page_proof(
                baseline_path=args.baseline,
                runtime_dir=args.runtime_dir,
                page=args.page,
                screenshot_path=args.screenshot,
                expected_tokens=list(args.expected_token or []),
                ax_text_path=args.ax_text,
                ocr_text_path=args.ocr_text,
                output_path=args.output,
            )
            return 0
        if args.command == "write-install-evidence":
            if api is None:
                raise RuntimeError("write-install-evidence requires backend api")
            if args.phase == "step-b" and not str(args.control_client_id or "").strip():
                raise RuntimeError("write-install-evidence step-b requires --control-client-id")
            write_install_evidence(
                api,
                baseline_path=args.baseline,
                runtime_dir=args.runtime_dir,
                phase=args.phase,
                status=args.status,
                app_starts=bool(args.app_starts),
                backend_started_by_installed_app=bool(args.backend_started_by_installed_app),
                overview_panel_visible=bool(args.overview_panel_visible),
                shadow_off_parity=bool(args.shadow_off_parity),
                workspace_boundary_correct=bool(args.workspace_boundary_correct),
                cockpit_official_layer_tone_correct=bool(args.cockpit_official_layer_tone_correct),
                overview_metrics_populated=bool(args.overview_metrics_populated),
                overview_screenshot=args.overview_screenshot,
                workspace_screenshot=args.workspace_screenshot,
                cockpit_screenshot=args.cockpit_screenshot,
                overview_page_proof=args.overview_page_proof,
                workspace_page_proof=args.workspace_page_proof,
                cockpit_page_proof=args.cockpit_page_proof,
                summary=args.summary,
                manual_backend_recovery_used=bool(args.manual_backend_recovery_used),
                workaround_required=bool(args.workaround_required),
                control_client_id=args.control_client_id,
                output_path=args.output,
            )
            return 0
        if args.command == "write-install-note":
            write_install_note(
                baseline_path=args.baseline,
                runtime_dir=args.runtime_dir,
                phase=args.phase,
                blocker_class=args.blocker_class,
                decision=args.decision,
                reason=args.reason,
                evidence_path=args.evidence,
                output_path=args.output,
            )
            return 0
        if args.command == "write-phase-b-decision":
            if api is None:
                raise RuntimeError("write-phase-b-decision requires backend api")
            write_phase_b_decision(
                api,
                baseline_path=args.baseline,
                runtime_dir=args.runtime_dir,
                observation_path=args.observation,
                manual_path=args.manual,
                blocker_class=args.blocker_class,
                output_path=args.output,
            )
            return 0
        if args.command == "write-full-smoke-classification":
            write_full_smoke_classification(
                source_path=args.source,
                log_path=args.log,
                pytest_exit_code=args.pytest_exit_code,
                full_smoke_summary=args.summary,
                failures=args.failure,
                rc_blocking_failures=args.rc_blocking_failure,
                inherited_failures=args.inherited_failure,
                classification_reason=args.classification_reason,
                output_path=args.output,
            )
            return 0
    finally:
        if api is not None:
            api.close()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
