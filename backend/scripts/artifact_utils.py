from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_data_dir() -> Path:
    override = str(os.getenv("YIYU_WORKBENCH_DATA_DIR") or "").strip()
    if override:
        return Path(override)
    return Path.home() / "Library" / "Application Support" / "YiyuThinkTankWorkbench"


def _git_commit(repo_root: Path | None = None) -> str:
    root = repo_root or _repo_root()
    try:
        return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return ""


def _backend_build_hash(repo_root: Path | None = None) -> str:
    return str(os.getenv("YIYU_BACKEND_BUILD_HASH") or "").strip() or _git_commit(repo_root)


def _runtime_mode() -> str:
    return "packaged" if str(os.getenv("YIYU_PACKAGED_APP_ROOT") or "").strip() else "dev"


def stamp_artifact(
    payload: dict[str, Any],
    artifact_kind: str,
    *,
    repo_root: Path | None = None,
    data_dir: str | Path | None = None,
    source_run_id: str | None = None,
) -> dict[str, Any]:
    stamped = dict(payload)
    stamped.update(
        {
            "artifactKind": artifact_kind,
            "generatedAt": datetime.now().replace(microsecond=0).isoformat(),
            "gitCommit": _git_commit(repo_root),
            "backendBuildHash": _backend_build_hash(repo_root),
            "runtimeMode": _runtime_mode(),
            "dataDir": str(Path(data_dir) if data_dir else _default_data_dir()),
            "sourceRunId": source_run_id or f"{artifact_kind}:{int(datetime.now().timestamp())}",
            "stale": False,
        }
    )
    return stamped
