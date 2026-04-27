from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any


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
RC_MODE = "installed-runtime"
RC_SESSION_STATES = (
    "pre_baseline",
    "baseline_frozen",
    "day0_ready",
    "wave2_active",
    "step_b_ready",
    "blocked",
    "completed",
)
IDENTITY_TUPLE_FIELDS = (
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
)


def iso_now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def normalized_paths(items: list[str] | tuple[str, ...] | None) -> list[str]:
    return sorted({str(item).strip() for item in (items or []) if str(item).strip()})


def stable_json_hash(payload: Any) -> str:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _installed_runtime_signature(payload: dict[str, Any] | None) -> dict[str, Any]:
    signature = dict(payload or {})
    return {
        "appBundleMTime": signature.get("appBundleMTime"),
        "rendererEntry": signature.get("rendererEntry"),
        "backendStartedByInstalledApp": bool(signature.get("backendStartedByInstalledApp")),
    }


def identity_tuple_payload(identity: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(identity or {})
    signature = _installed_runtime_signature(payload.get("installedRuntimeSignature") if isinstance(payload.get("installedRuntimeSignature"), dict) else payload)
    health = payload.get("health") or {}
    return {
        "commitSha": payload.get("commitSha"),
        "backendUrl": payload.get("backendUrl"),
        "buildVersion": payload.get("buildVersion") or health.get("buildVersion"),
        "databasePath": payload.get("databasePath"),
        "latestJudgmentsShadowOff": bool(payload.get("latestJudgmentsShadowOff")),
        "dirtyWorktree": bool(payload.get("dirtyWorktree")),
        "dirtyPaths": normalized_paths(payload.get("dirtyPaths")),
        "appBundleMTime": payload.get("appBundleMTime") or signature.get("appBundleMTime"),
        "rendererEntry": payload.get("rendererEntry") or signature.get("rendererEntry"),
        "backendStartedByInstalledApp": bool(
            payload.get("backendStartedByInstalledApp")
            if payload.get("backendStartedByInstalledApp") is not None
            else signature.get("backendStartedByInstalledApp")
        ),
    }


def compute_tuple_hash(identity: dict[str, Any] | None) -> str:
    return stable_json_hash(identity_tuple_payload(identity))


def build_session_id(*, generated_at: str | None = None, tuple_hash: str | None = None) -> str:
    timestamp = (generated_at or iso_now()).replace("-", "").replace(":", "").replace("T", "-")
    suffix = (tuple_hash or stable_json_hash({"generatedAt": generated_at or iso_now()}))[:12]
    return f"rc-{timestamp}-{suffix}"


def ensure_baseline_contract(payload: dict[str, Any]) -> dict[str, Any]:
    contracted = deepcopy(payload)
    contracted["rcMode"] = str(contracted.get("rcMode") or RC_MODE)
    contracted["tupleHash"] = str(contracted.get("tupleHash") or compute_tuple_hash(contracted))
    contracted["sessionId"] = str(
        contracted.get("sessionId")
        or build_session_id(
            generated_at=str(contracted.get("generatedAt") or contracted.get("recordedAt") or ""),
            tuple_hash=contracted["tupleHash"],
        )
    )
    baseline_for_hash = deepcopy(contracted)
    baseline_for_hash.pop("baselineHash", None)
    contracted["baselineHash"] = str(contracted.get("baselineHash") or stable_json_hash(baseline_for_hash))
    return contracted


def artifact_contract_fields(baseline_payload: dict[str, Any]) -> dict[str, Any]:
    baseline = ensure_baseline_contract(baseline_payload)
    return {
        "rcMode": baseline.get("rcMode"),
        "sessionId": baseline.get("sessionId"),
        "baselineHash": baseline.get("baselineHash"),
        "tupleHash": baseline.get("tupleHash"),
    }


def attach_artifact_contract(payload: dict[str, Any], baseline_payload: dict[str, Any]) -> dict[str, Any]:
    enriched = deepcopy(payload)
    enriched.update(artifact_contract_fields(baseline_payload))
    return enriched


def resolve_runtime_dir(path: str | Path | None = None) -> Path:
    target = Path(path or DEFAULT_RUNTIME_DIR).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    return target


def rc_session_path(runtime_dir: str | Path | None = None) -> Path:
    return resolve_runtime_dir(runtime_dir) / "rc-session.json"


def default_rc_session(
    *,
    baseline_path: str | Path | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    return {
        "sessionId": session_id,
        "rcMode": RC_MODE,
        "state": "pre_baseline",
        "baselinePath": str(Path(baseline_path).expanduser().resolve()) if baseline_path else None,
        "baselineHash": None,
        "tupleHash": None,
        "installReceiptPath": None,
        "installSmokePath": None,
        "activeInstallSignature": None,
        "invalidatedAt": None,
        "invalidationReason": None,
        "updatedAt": iso_now(),
    }


def load_rc_session(runtime_dir: str | Path | None = None) -> dict[str, Any] | None:
    path = rc_session_path(runtime_dir)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"RC session at {path} is not a JSON object")
    payload.setdefault("rcMode", RC_MODE)
    payload["state"] = str(payload.get("state") or "pre_baseline").replace("-", "_")
    payload.setdefault("updatedAt", iso_now())
    return payload


def write_rc_session(payload: dict[str, Any], *, runtime_dir: str | Path | None = None) -> dict[str, Any]:
    path = rc_session_path(runtime_dir)
    session = deepcopy(payload)
    session["rcMode"] = str(session.get("rcMode") or RC_MODE)
    state = str(session.get("state") or "pre_baseline")
    if state not in RC_SESSION_STATES:
        raise RuntimeError(f"Unsupported rc-session state: {state}")
    session["state"] = state
    session["updatedAt"] = str(session.get("updatedAt") or iso_now())
    path.write_text(json.dumps(session, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return session


def active_install_signature_from_artifacts(
    *,
    install_receipt_payload: dict[str, Any] | None,
    install_smoke_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    receipt = dict(install_receipt_payload or {})
    smoke = dict(install_smoke_payload or {})
    return {
        "appBundleMTime": receipt.get("targetAppMTime") or receipt.get("sourceAppMTime"),
        "rendererEntry": receipt.get("targetRendererEntry") or receipt.get("sourceRendererEntry") or smoke.get("targetRendererEntry") or smoke.get("sourceRendererEntry"),
        "backendStartedByInstalledApp": bool(smoke.get("backendStartedByInstalledApp")),
    }
