from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.services.source_integrity import compute_backend_source_hash

APP_DISPLAY_NAME = "益语智库自用平台 V2.0"
VERSION_MANIFEST_RELATIVE_PATH = Path("dist") / "version-manifest.json"


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def version_manifest_path(root: Path | None = None) -> Path:
    return (root or project_root()) / VERSION_MANIFEST_RELATIVE_PATH


def load_version_manifest(root: Path | None = None) -> dict[str, Any] | None:
    target = version_manifest_path(root)
    if not target.exists():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def compute_manifest_id(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def backend_source_hash(root: Path | None = None) -> str:
    backend_root = (root or project_root()) / "backend"
    return compute_backend_source_hash(backend_root)


def resolve_bundle_path(source_path: Path) -> Path | None:
    current = source_path.resolve()
    while current != current.parent:
        if current.name.endswith(".app"):
            return current
        current = current.parent
    return None


def install_path_status(runtime_mode: str) -> str:
    if runtime_mode != "packaged":
        return "dev"
    bundle_path = resolve_bundle_path(Path(__file__))
    recommended = Path.home() / "Applications" / f"{APP_DISPLAY_NAME}.app"
    if bundle_path and bundle_path.resolve() == recommended.resolve():
        return "recommended"
    return "unexpected"
