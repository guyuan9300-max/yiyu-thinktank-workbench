from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Callable

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.main import create_app
from app.models import WorkspaceAnswerExperienceRecord, WorkspaceAnswerFinalizationRecord


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _default_output_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "output"


def _contains_tokens(path: Path, tokens: list[str]) -> dict[str, bool]:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {token: False for token in tokens}
    return {token: token in content for token in tokens}


def _scan_many(paths: list[Path], tokens: list[str]) -> dict[str, bool]:
    result = {token: False for token in tokens}
    for path in paths:
        token_state = _contains_tokens(path, tokens)
        for token, present in token_state.items():
            result[token] = result[token] or present
    return result


def _renderer_assets(renderer_assets_dir: Path) -> list[Path]:
    if not renderer_assets_dir.exists():
        return []
    return sorted(renderer_assets_dir.glob("*.js"))


def _source_contract(repo_root: Path) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="workspace-value-align-openapi-") as tmp_dir:
        app = create_app(Path(tmp_dir) / "data")
        openapi = app.openapi()
    paths = openapi.get("paths") if isinstance(openapi, dict) else {}
    required_paths = [
        "/api/v1/runtime/workspace-answer-value-diagnostics",
        "/api/v1/workspace-answer-value-reviews",
        "/api/v1/workspace-answer-value-summary",
        "/api/v1/workspace-value-validation-sessions",
        "/api/v1/workspace-answer-quality-failures",
    ]
    api_paths = {path: bool(isinstance(paths, dict) and path in paths) for path in required_paths}

    finalization_required_fields = [
        "content",
        "answerMode",
        "failureReason",
        "fallbackPresentationMode",
        "userVisibleQualityStatus",
        "shouldShowRetryBanner",
        "qualityGrade",
        "internalGenerationStatus",
        "notes",
    ]
    finalization_available_fields = list(WorkspaceAnswerFinalizationRecord.model_fields.keys())
    finalization_field_presence = {
        field: field in finalization_available_fields for field in finalization_required_fields
    }

    experience_required_fields = [
        "status",
        "headline",
        "directAnswer",
        "keyPoints",
        "evidenceChips",
        "boundaryNotes",
        "nextActions",
        "actionCards",
        "trustSignals",
        "userMessage",
    ]
    experience_available_fields = list(WorkspaceAnswerExperienceRecord.model_fields.keys())
    experience_field_presence = {
        field: field in experience_available_fields for field in experience_required_fields
    }
    return {
        "apiPaths": api_paths,
        "workspaceAnswerFinalizationFields": finalization_field_presence,
        "workspaceAnswerExperienceFields": experience_field_presence,
        "pass": all(api_paths.values()) and all(finalization_field_presence.values()) and all(experience_field_presence.values()),
        "sourceFiles": {
            "backendMain": str(repo_root / "backend" / "app" / "main.py"),
            "rendererApp": str(repo_root / "src" / "renderer" / "App.tsx"),
            "sharedTypes": str(repo_root / "src" / "shared" / "types.ts"),
        },
    }


def _local_response_probe() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="workspace-value-align-probe-") as tmp_dir:
        data_dir = Path(tmp_dir) / "data"
        app = create_app(data_dir)
        with TestClient(app) as client:
            db = client.app.state.app_state.db
            db.set_setting("workspace_chat_data_center_primary", "1")
            db.set_setting("workspace_chat_use_legacy_fallback", "0")

            response = client.post(
                "/api/v1/clients",
                json={
                    "name": "workspace-value-alignment-probe",
                    "alias": "workspace-value-alignment-probe",
                    "domain": "公益",
                    "type": "战略陪伴",
                    "intro": "workspace value alignment probe",
                    "stage": "推进中",
                },
            )
            response.raise_for_status()
            client_id = response.json()["id"]

            original_generate = client.app.state.app_state.ai.generate_chat_response
            original_validate = app_main.validate_answer_quality

            call_counter = {"count": 0}

            def _generate(*_args, **_kwargs):
                call_counter["count"] += 1
                if call_counter["count"] == 1:
                    raise TimeoutError("simulated timeout")
                return "基于现有资料，客户核心业务聚焦资源支持与项目服务。"

            try:
                client.app.state.app_state.ai.generate_chat_response = _generate
                app_main.validate_answer_quality = lambda **_kwargs: {
                    "hasDirectAnswer": True,
                    "evidenceListOnly": False,
                    "evidenceQuoteOnly": False,
                    "leakedInternalMarkers": [],
                    "candidateAsOfficialRisk": False,
                    "officialBoundaryViolation": False,
                    "missingRawEvidenceForIntent": False,
                    "offTopicRisk": False,
                    "factSlotHit": True,
                    "factSlotMissingReason": None,
                    "grade": "pass",
                    "reason": "alignment_probe",
                }
                answer = client.post(
                    f"/api/v1/clients/{client_id}/workspace/chat",
                    json={"prompt": "CFFC 核心业务是什么？"},
                )
                answer.raise_for_status()
            finally:
                client.app.state.app_state.ai.generate_chat_response = original_generate
                app_main.validate_answer_quality = original_validate

            payload = answer.json()
            retrieval_summary = payload.get("retrievalSummary") if isinstance(payload, dict) else {}
            if not isinstance(retrieval_summary, dict):
                retrieval_summary = {}
            finalization = retrieval_summary.get("workspaceAnswerFinalization")
            finalization_dict = finalization if isinstance(finalization, dict) else {}
            experience = retrieval_summary.get("workspaceAnswerExperience")
            experience_dict = experience if isinstance(experience, dict) else {}
            return {
                "answerMode": payload.get("answerMode"),
                "hasWorkspaceAnswerFinalization": bool(finalization_dict),
                "hasWorkspaceAnswerExperience": bool(experience_dict),
                "shouldShowRetryBanner": bool(finalization_dict.get("shouldShowRetryBanner")),
                "userVisibleQualityStatus": finalization_dict.get("userVisibleQualityStatus"),
                "experienceStatus": experience_dict.get("status"),
                "experienceDirectAnswer": experience_dict.get("directAnswer"),
                "llmErrorHiddenFromUserBecauseAnswerPassedQuality": bool(
                    retrieval_summary.get("llmErrorHiddenFromUserBecauseAnswerPassedQuality")
                ),
                "pass": bool(finalization_dict)
                and bool(experience_dict)
                and isinstance(finalization_dict.get("userVisibleQualityStatus"), str)
                and isinstance(experience_dict.get("status"), str)
                and bool(str(experience_dict.get("directAnswer") or "").strip()),
            }


def _local_build_contract(*, renderer_assets_dir: Path, renderer_tokens: list[str], forbidden_tokens: list[str]) -> dict[str, object]:
    renderer_assets = _renderer_assets(renderer_assets_dir)
    renderer_token_state = _scan_many(renderer_assets, renderer_tokens) if renderer_assets else {token: False for token in renderer_tokens}
    forbidden_state = _scan_many(renderer_assets, forbidden_tokens) if renderer_assets else {token: False for token in forbidden_tokens}
    return {
        "rendererAssetsDir": str(renderer_assets_dir),
        "rendererAssetCount": len(renderer_assets),
        "rendererTokenState": renderer_token_state,
        "forbiddenTokenState": forbidden_state,
        "pass": bool(renderer_assets)
        and all(renderer_token_state.values())
        and not any(forbidden_state.values()),
    }


def _installed_bundle_contract(*, backend_entry: Path, renderer_assets_dir: Path, backend_tokens: list[str], renderer_tokens: list[str], forbidden_tokens: list[str]) -> dict[str, object]:
    renderer_assets = _renderer_assets(renderer_assets_dir)
    backend_token_state = _contains_tokens(backend_entry, backend_tokens) if backend_entry.exists() else {
        token: False for token in backend_tokens
    }
    renderer_token_state = _scan_many(renderer_assets, renderer_tokens) if renderer_assets else {
        token: False for token in renderer_tokens
    }
    forbidden_state = _scan_many(renderer_assets, forbidden_tokens) if renderer_assets else {
        token: False for token in forbidden_tokens
    }
    return {
        "backendEntryPath": str(backend_entry),
        "backendEntryExists": backend_entry.exists(),
        "rendererAssetsDir": str(renderer_assets_dir),
        "rendererAssetCount": len(renderer_assets),
        "backendTokenState": backend_token_state,
        "rendererTokenState": renderer_token_state,
        "forbiddenTokenState": forbidden_state,
        "pass": bool(backend_entry.exists())
        and bool(renderer_assets)
        and all(backend_token_state.values())
        and all(renderer_token_state.values())
        and not any(forbidden_state.values()),
    }


def build_alignment_report(
    repo_root: Path,
    *,
    renderer_assets_dir: Path | None = None,
    installed_app_root: Path | None = None,
    local_probe: Callable[[], dict[str, object]] | None = None,
) -> dict[str, object]:
    backend_tokens = [
        "/api/v1/runtime/workspace-answer-value-diagnostics",
        "/api/v1/workspace-answer-value-reviews",
        "/api/v1/workspace-answer-value-summary",
        "/api/v1/workspace-value-validation-sessions",
        "/api/v1/workspace-answer-quality-failures",
        "workspaceAnswerExperience",
    ]
    renderer_tokens = [
        "workspaceAnswerFinalization",
        "workspaceAnswerExperience",
        "shouldShowRetryBanner",
        "usable_with_boundary",
        "needs_retry",
    ]
    forbidden_tokens = [
        "已基于命中的资料生成简版可用回答；完整长文扩写未完成，可继续重试扩写。",
    ]

    source_contract = _source_contract(repo_root)
    build_contract = _local_build_contract(
        renderer_assets_dir=renderer_assets_dir or (repo_root / "dist" / "renderer" / "assets"),
        renderer_tokens=renderer_tokens,
        forbidden_tokens=forbidden_tokens,
    )

    installed_root = installed_app_root or (repo_root / "dist" / "mac-arm64" / "益语智库自用平台.app")
    installed_exists = installed_root.exists()
    if installed_exists:
        installed_contract = _installed_bundle_contract(
            backend_entry=installed_root / "Contents" / "Resources" / "app" / "backend" / "app" / "main.py",
            renderer_assets_dir=installed_root / "Contents" / "Resources" / "app" / "dist" / "renderer" / "assets",
            backend_tokens=backend_tokens,
            renderer_tokens=renderer_tokens,
            forbidden_tokens=forbidden_tokens,
        )
        installed_contract["checked"] = True
    else:
        installed_contract = {
            "checked": False,
            "exists": False,
            "pass": None,
            "reason": "installed_bundle_not_found",
        }

    probe = (local_probe or _local_response_probe)()
    blocking_issues: list[str] = []
    if not bool(source_contract.get("pass")):
        blocking_issues.append("source contract missing required API path, finalization field, or experience field")
    if not bool(build_contract.get("pass")):
        blocking_issues.append("local build artifacts do not contain required P2.9 tokens or still contain legacy retry banner text")
    if not bool(probe.get("pass")):
        blocking_issues.append("local response probe missing workspaceAnswerFinalization/workspaceAnswerExperience contract")
    if bool(installed_contract.get("checked")) and not bool(installed_contract.get("pass")):
        blocking_issues.append("installed app bundle missing required P2.9 tokens or still contains legacy retry banner text")

    verdict = "pass" if not blocking_issues else "fail"
    return {
        "generatedAt": _now_iso(),
        "sourceContract": source_contract,
        "localBuild": build_contract,
        "installedBundle": installed_contract,
        "localResponseProbe": probe,
        "verdict": verdict,
        "blockingIssues": blocking_issues,
        "currentClientAllowlistObservable": True,
        "runtimeValueAlignmentPass": verdict == "pass",
    }


def _render_markdown(payload: dict[str, object]) -> str:
    probe = payload.get("localResponseProbe") if isinstance(payload.get("localResponseProbe"), dict) else {}
    lines = [
        "# P2.9 Runtime Value Alignment Report",
        "",
        f"- generatedAt: `{payload.get('generatedAt')}`",
        f"- verdict: `{payload.get('verdict')}`",
        "",
        "## Local Response Probe",
        f"- answerMode: `{probe.get('answerMode')}`",
        f"- hasWorkspaceAnswerFinalization: `{probe.get('hasWorkspaceAnswerFinalization')}`",
        f"- hasWorkspaceAnswerExperience: `{probe.get('hasWorkspaceAnswerExperience')}`",
        f"- shouldShowRetryBanner: `{probe.get('shouldShowRetryBanner')}`",
        f"- userVisibleQualityStatus: `{probe.get('userVisibleQualityStatus')}`",
        f"- experienceStatus: `{probe.get('experienceStatus')}`",
        f"- experienceDirectAnswer: `{probe.get('experienceDirectAnswer')}`",
        "",
        "## Blocking Issues",
    ]
    blocking = payload.get("blockingIssues") if isinstance(payload.get("blockingIssues"), list) else []
    if not blocking:
        lines.append("- (none)")
    else:
        for item in blocking:
            lines.append(f"- {item}")
    return "\n".join(lines)


def write_alignment_report(payload: dict[str, object], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "P2.9-runtime-value-alignment-report.json"
    md_path = output_dir / "P2.9-runtime-value-alignment-report.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    return {"jsonPath": str(json_path), "markdownPath": str(md_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check P2.9 runtime value alignment for workspace answer experience.")
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[2]),
        help="Repository root containing build/ and dist/ artifacts.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(_default_output_dir()),
        help="Directory to write P2.9 alignment artifacts.",
    )
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when runtime value alignment is not pass.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    payload = build_alignment_report(repo_root)
    artifacts = write_alignment_report(payload, output_dir)
    print(json.dumps({"artifacts": artifacts, "verdict": payload["verdict"]}, ensure_ascii=False))
    if args.strict:
        return 0 if payload["verdict"] == "pass" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
