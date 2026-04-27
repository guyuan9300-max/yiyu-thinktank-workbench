from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta
from json import JSONDecoder
from pathlib import Path
from typing import Any

from app.db import Database
from app.models import DataCenterArtifactStatusItemRecord, DataCenterArtifactStatusRecord


_DEFAULT_DATA_DIR = Path.home() / "Library" / "Application Support" / "YiyuThinkTankWorkbench"


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _resolve_output_dir() -> Path:
    override = str(os.getenv("YIYU_DATA_CENTER_OUTPUT_DIR") or "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "output"


def _resolve_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_default_data_dir() -> Path:
    override = str(os.getenv("YIYU_WORKBENCH_DATA_DIR") or "").strip()
    if override:
        return Path(override)
    return _DEFAULT_DATA_DIR


def _current_git_commit(repo_root: Path | None = None) -> str:
    root = repo_root or _resolve_repo_root()
    try:
        output = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True)
        return output.strip()
    except Exception:
        return ""


def _current_backend_build_hash(repo_root: Path | None = None) -> str:
    return str(os.getenv("YIYU_BACKEND_BUILD_HASH") or "").strip() or _current_git_commit(repo_root)


def _current_runtime_mode() -> str:
    return "packaged" if str(os.getenv("YIYU_PACKAGED_APP_ROOT") or "").strip() else "dev"


def artifact_metadata(
    artifact_kind: str,
    *,
    repo_root: Path | None = None,
    data_dir: str | Path | None = None,
    source_run_id: str | None = None,
) -> dict[str, object]:
    resolved_repo_root = repo_root or _resolve_repo_root()
    resolved_data_dir = Path(data_dir) if data_dir else _resolve_default_data_dir()
    return {
        "artifactKind": artifact_kind,
        "generatedAt": _now_iso(),
        "gitCommit": _current_git_commit(resolved_repo_root),
        "backendBuildHash": _current_backend_build_hash(resolved_repo_root),
        "runtimeMode": _current_runtime_mode(),
        "dataDir": str(resolved_data_dir),
        "sourceRunId": source_run_id or f"{artifact_kind}:{int(datetime.now().timestamp())}",
        "stale": False,
    }


def stamp_artifact(
    payload: dict[str, Any],
    artifact_kind: str,
    *,
    repo_root: Path | None = None,
    data_dir: str | Path | None = None,
    source_run_id: str | None = None,
) -> dict[str, Any]:
    stamped = dict(payload)
    stamped.update(artifact_metadata(artifact_kind, repo_root=repo_root, data_dir=data_dir, source_run_id=source_run_id))
    return stamped


def _read_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else None
    except Exception:
        pass

    decoder = JSONDecoder()
    index = 0
    length = len(text)
    while index < length:
        while index < length and text[index].isspace():
            index += 1
        if index >= length:
            break
        try:
            payload, next_index = decoder.raw_decode(text, index)
        except Exception:
            return None
        if isinstance(payload, dict):
            return payload
        index = next_index
    return None


def _p22_strict_pass(payload: dict[str, object] | None) -> bool:
    if not payload:
        return False
    return bool(
        bool(payload.get("officialBoundaryPass"))
        and bool(payload.get("candidateBoundaryPass"))
        and int(payload.get("failureCount") or 0) == 0
    )


def _p23_strict_pass(payload: dict[str, object] | None) -> bool:
    if not payload:
        return False
    checks = [
        float(payload.get("proposalApprovalPassRate") or 0.0) >= 0.9,
        float(payload.get("executionTicketPassRate") or 0.0) >= 0.9,
        float(payload.get("executionRetryPassRate") or 0.0) >= 0.8,
        float(payload.get("meetingFollowupExecutionPassRate") or 0.0) >= 0.8,
        float(payload.get("kernelChatPrimaryPassRate") or 0.0) >= 0.85,
        float(payload.get("evidenceQualityFeedbackPassRate") or 0.0) >= 0.75,
        float(payload.get("externalEvidenceReviewPassRate") or 0.0) >= 0.8,
        bool(payload.get("opsPanelContractPass")) is True,
        bool(payload.get("officialBoundaryPass")) is True,
        bool(payload.get("candidateBoundaryPass")) is True,
        bool(payload.get("noAutoExecutionViolation")) is True,
        bool(payload.get("kernelPrimaryGateEmptyAllowlistPass")) is True,
        int(payload.get("failureCount") or 0) == 0,
    ]
    return all(checks)


def _infer_verdict(key: str, payload: dict[str, object] | None) -> str:
    if not isinstance(payload, dict):
        return "unknown"
    verdict = str(payload.get("verdict") or "").strip().lower()
    if verdict in {"pass", "fail", "hold", "unknown"}:
        return verdict
    if key == "p22Strict":
        return "pass" if _p22_strict_pass(payload) else "hold"
    if key == "p23Strict":
        return "pass" if _p23_strict_pass(payload) else "hold"
    if key == "evidenceSnapshot":
        return "pass" if bool(payload.get("snapshotExists")) else "hold"
    if key == "rolloutReport":
        stage_summary = payload.get("stageSummary")
        if isinstance(stage_summary, list) and stage_summary:
            if any(isinstance(item, dict) and str(item.get("status") or "") == "completed" for item in stage_summary):
                return "pass"
            return "hold"
    return "hold" if payload else "unknown"


def _runtime_context(db: Database) -> dict[str, str]:
    return {
        "gitCommit": str(db.get_setting("runtime.git_commit", "") or "").strip(),
        "backendBuildHash": str(db.get_setting("runtime.backend_build_hash", "") or "").strip(),
        "runtimeMode": str(db.get_setting("runtime.mode", "") or "").strip(),
        "dataDir": str(db.get_setting("runtime.data_dir", "") or "").strip(),
    }


def _artifact_blocking_issues(payload: dict[str, object] | None, current: dict[str, str]) -> list[str]:
    if not isinstance(payload, dict):
        return ["artifact_missing"]

    issues: list[str] = []
    generated_at = str(payload.get("generatedAt") or "").strip()
    git_commit = str(payload.get("gitCommit") or "").strip()
    backend_build_hash = str(payload.get("backendBuildHash") or "").strip()
    runtime_mode = str(payload.get("runtimeMode") or "").strip()
    data_dir = str(payload.get("dataDir") or "").strip()

    if not generated_at:
        issues.append("stale_artifact_missing_generated_at")
    else:
        try:
            generated_dt = datetime.fromisoformat(generated_at)
            if generated_dt < datetime.now() - timedelta(hours=24):
                issues.append("stale_artifact_older_than_24h")
        except ValueError:
            issues.append("stale_artifact_invalid_generated_at")

    if not git_commit or git_commit != current.get("gitCommit"):
        issues.append("stale_artifact_git_commit_mismatch")
    if not backend_build_hash or backend_build_hash != current.get("backendBuildHash"):
        issues.append("stale_artifact_backend_build_hash_mismatch")
    if runtime_mode and current.get("runtimeMode") and runtime_mode != current.get("runtimeMode"):
        issues.append("stale_artifact_runtime_mode_mismatch")
    if not data_dir or data_dir != current.get("dataDir"):
        issues.append("stale_artifact_data_dir_mismatch")
    return issues


def build_data_center_artifact_status(db: Database) -> dict[str, object]:
    output_dir = _resolve_output_dir()
    current = _runtime_context(db)
    specs = [
        ("fullRegression", "Full Regression", output_dir / "P2.5-full-regression-report.json"),
        ("p22Strict", "P2.2 Strict", output_dir / "P2.6-eval-p22-strict.json"),
        ("p23Strict", "P2.3 Strict", output_dir / "P2.6-eval-p23-strict.json"),
        ("runtimeAlignment", "Runtime Alignment", output_dir / "P2.9-runtime-value-alignment-report.json"),
        ("rolloutReport", "Kernel Rollout", output_dir / "P2.6-kernel-primary-rollout-report.json"),
        ("rollbackDrill", "Rollback Drill", output_dir / "P2.6-rollback-drill-report.json"),
        ("evidenceSnapshot", "Evidence Snapshot", output_dir / "P2.6-evidence-quality-snapshot-report.json"),
        ("customerWorkspaceValue", "Workspace Value", output_dir / "P2.9-customer-workspace-value-report.json"),
        ("rcRelease", "RC Release", output_dir / "P2.6-RC2-operational-release-report.json"),
    ]
    items: list[DataCenterArtifactStatusItemRecord] = []
    overall_pass = True
    for key, label, path in specs:
        payload = _read_json(path)
        verdict = _infer_verdict(key, payload)
        blocking_issues = _artifact_blocking_issues(payload, current)
        stale = bool(blocking_issues)
        generated_at = None
        git_commit = None
        backend_build_hash = None
        runtime_mode = None
        data_dir = None
        source_run_id = None
        if isinstance(payload, dict):
            generated_at = str(payload.get("generatedAt") or "").strip() or None
            git_commit = str(payload.get("gitCommit") or "").strip() or None
            backend_build_hash = str(payload.get("backendBuildHash") or "").strip() or None
            runtime_mode = str(payload.get("runtimeMode") or "").strip() or None
            data_dir = str(payload.get("dataDir") or "").strip() or None
            source_run_id = str(payload.get("sourceRunId") or "").strip() or None
        if verdict != "pass" or stale:
            overall_pass = False
        items.append(
            DataCenterArtifactStatusItemRecord(
                key=key,
                label=label,
                path=str(path),
                exists=payload is not None,
                verdict=verdict,  # type: ignore[arg-type]
                stale=stale,
                generatedAt=generated_at,
                gitCommit=git_commit,
                backendBuildHash=backend_build_hash,
                runtimeMode=runtime_mode,
                dataDir=data_dir,
                sourceRunId=source_run_id,
                blockingIssues=blocking_issues,
            )
        )
    return DataCenterArtifactStatusRecord(
        generatedAt=_now_iso(),
        overallPass=overall_pass,
        items=items,
    ).model_dump(mode="json")
