from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import (
    WorkspaceAnswerFinalizationRecord,
    WorkspaceAnswerValueDiagnosticsRecord,
    WorkspaceAnswerValueSummaryRecord,
)
from scripts.eval_customer_workspace_answer_value_p27 import run_eval


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _default_output_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "output"


def _sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _git_value(repo_root: Path, args: list[str], fallback: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return fallback
    if result.returncode != 0:
        return fallback
    return (result.stdout or "").strip() or fallback


def _git_dirty(repo_root: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return True
    if result.returncode != 0:
        return True
    return bool((result.stdout or "").strip())


def _build_fingerprint(repo_root: Path) -> dict[str, object]:
    main_entry = repo_root / "build" / "main" / "main.js"
    renderer_dir = repo_root / "dist" / "renderer" / "assets"
    renderer_assets = sorted(renderer_dir.glob("*.js")) if renderer_dir.exists() else []
    return {
        "mainEntryPath": str(main_entry),
        "mainEntryExists": main_entry.exists(),
        "mainEntrySha256": _sha256_file(main_entry),
        "rendererAssetsDir": str(renderer_dir),
        "rendererAssetsExist": bool(renderer_assets),
        "rendererAssetCount": len(renderer_assets),
        "rendererAssetSha256": {
            asset.name: _sha256_file(asset)
            for asset in renderer_assets[:8]
        },
    }


def _source_fingerprint(repo_root: Path) -> dict[str, object]:
    tracked_files = {
        "backendMain": repo_root / "backend" / "app" / "main.py",
        "backendModels": repo_root / "backend" / "app" / "models.py",
        "workspaceAnswerFinalizer": repo_root / "backend" / "app" / "services" / "workspace_answer_finalizer.py",
        "workspaceAnswerValueDiagnostics": repo_root / "backend" / "app" / "services" / "workspace_answer_value_diagnostics.py",
        "rendererApp": repo_root / "src" / "renderer" / "App.tsx",
        "rendererApi": repo_root / "src" / "renderer" / "lib" / "api.ts",
        "sharedTypes": repo_root / "src" / "shared" / "types.ts",
        "workspaceAnswerValuePanel": repo_root / "src" / "renderer" / "components" / "data_center" / "WorkspaceAnswerValuePanel.tsx",
    }
    return {
        key: {
            "path": str(path),
            "sha256": _sha256_file(path),
        }
        for key, path in tracked_files.items()
    }


def _schema_contract() -> dict[str, object]:
    return {
        "workspaceAnswerFinalizationFields": list(WorkspaceAnswerFinalizationRecord.model_fields.keys()),
        "workspaceAnswerValueDiagnosticsFields": list(WorkspaceAnswerValueDiagnosticsRecord.model_fields.keys()),
        "workspaceAnswerValueSummaryFields": list(WorkspaceAnswerValueSummaryRecord.model_fields.keys()),
        "apiPaths": [
            "/api/v1/runtime/workspace-answer-value-diagnostics",
            "/api/v1/workspace-answer-value-reviews",
            "/api/v1/workspace-answer-value-summary",
        ],
    }


def _frontend_trigger_rules() -> dict[str, object]:
    return {
        "primaryPredicate": "retrievalSummary.workspaceAnswerFinalization.shouldShowRetryBanner",
        "legacyFallbackEnabledWhenFinalizationMissing": True,
        "statusPresentation": {
            "ready": "no_banner",
            "usable_with_boundary": "light_boundary_banner",
            "degraded": "warning_banner",
            "needs_retry": "retry_banner",
        },
        "legacyFallbackRule": {
            "answerMode": "grounded_fallback|low_confidence_answer",
            "excludeFailureReason": "state_only",
            "excludePresentationMode": "state_cards_only",
        },
    }


def build_baseline(repo_root: Path, *, eval_payload: dict[str, Any] | None = None) -> dict[str, object]:
    if eval_payload is None:
        eval_payload = run_eval(strict=False, output_dir=None)
    return {
        "generatedAt": _now_iso(),
        "repo": {
            "root": str(repo_root),
            "commitSha": _git_value(repo_root, ["rev-parse", "HEAD"], "unknown"),
            "branch": _git_value(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"], "unknown"),
            "dirty": _git_dirty(repo_root),
        },
        "sourceFingerprint": _source_fingerprint(repo_root),
        "buildFingerprint": _build_fingerprint(repo_root),
        "schemaContract": _schema_contract(),
        "frontendTriggerRules": _frontend_trigger_rules(),
        "valueEvalBaseline": eval_payload,
    }


def _render_markdown(payload: dict[str, object]) -> str:
    repo = payload.get("repo") if isinstance(payload.get("repo"), dict) else {}
    build = payload.get("buildFingerprint") if isinstance(payload.get("buildFingerprint"), dict) else {}
    eval_payload = payload.get("valueEvalBaseline") if isinstance(payload.get("valueEvalBaseline"), dict) else {}
    lines = [
        "# P2.7 Baseline",
        "",
        f"- generatedAt: `{payload.get('generatedAt')}`",
        f"- commitSha: `{repo.get('commitSha')}`",
        f"- branch: `{repo.get('branch')}`",
        f"- dirty: `{repo.get('dirty')}`",
        f"- buildMainExists: `{build.get('mainEntryExists')}`",
        f"- buildRendererExists: `{build.get('rendererAssetsExist')}`",
        "",
        "## Value Eval Baseline",
        f"- usableAnswerRate: `{eval_payload.get('usableAnswerRate')}`",
        f"- retryBannerRate: `{eval_payload.get('retryBannerRate')}`",
        f"- groundedAnswerPassRate: `{eval_payload.get('groundedAnswerPassRate')}`",
        f"- businessStrategySlotHitRate: `{eval_payload.get('businessStrategySlotHitRate')}`",
        f"- kernelPrimaryUsedRate: `{eval_payload.get('kernelPrimaryUsedRate')}`",
        f"- officialBoundaryPass: `{eval_payload.get('officialBoundaryPass')}`",
        f"- candidateBoundaryPass: `{eval_payload.get('candidateBoundaryPass')}`",
        f"- failureCount: `{eval_payload.get('failureCount')}`",
    ]
    return "\n".join(lines)


def write_baseline(payload: dict[str, object], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "P2.7-baseline.json"
    md_path = output_dir / "P2.7-baseline.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    return {"jsonPath": str(json_path), "markdownPath": str(md_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze P2.7 workspace answer value baseline.")
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[2]),
        help="Repository root containing backend/ and src/ directories.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(_default_output_dir()),
        help="Directory to write P2.7 baseline artifacts.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    payload = build_baseline(repo_root)
    artifacts = write_baseline(payload, output_dir)
    print(json.dumps({"artifacts": artifacts, "commitSha": payload["repo"]["commitSha"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
