from __future__ import annotations

import hashlib
import re
from pathlib import Path

_HASH_EXTENSIONS = {".py", ".toml", ".json", ".yaml", ".yml", ".lock"}
_BUILD_VERSION_PATTERN = re.compile(r'^APP_BUILD_VERSION\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
_GIT_COMMIT_PATTERN = re.compile(r'^APP_GIT_COMMIT\s*=\s*(?:["\']([^"\']*)["\']|None)', re.MULTILINE)


def compute_backend_source_hash(root: Path) -> str:
    target_root = Path(root)
    if not target_root.exists() or not target_root.is_dir():
        return "missing"

    digest = hashlib.sha1()
    files = [
        path
        for path in sorted(target_root.rglob("*"))
        if path.is_file() and path.suffix.lower() in _HASH_EXTENSIONS and "__pycache__" not in path.parts
    ]
    if not files:
        return "empty"

    for file_path in files:
        rel = str(file_path.relative_to(target_root))
        digest.update(rel.encode("utf-8", errors="ignore"))
        digest.update(b"\n")
        try:
            digest.update(file_path.read_bytes())
        except Exception:
            stat = file_path.stat()
            digest.update(f"{stat.st_size}:{int(stat.st_mtime_ns)}".encode("utf-8", errors="ignore"))
        digest.update(b"\n")

    return digest.hexdigest()


def _read_backend_main_text(root: Path | None) -> str:
    if root is None:
        return ""
    try:
        target = Path(root).resolve() / "app" / "main.py"
        if not target.exists():
            return ""
        return target.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def extract_backend_metadata(root: Path | None) -> dict[str, str | None]:
    text = _read_backend_main_text(root)
    if not text:
        return {
            "buildVersion": None,
            "gitCommit": None,
        }
    build_version_match = _BUILD_VERSION_PATTERN.search(text)
    git_commit_match = _GIT_COMMIT_PATTERN.search(text)
    git_commit = git_commit_match.group(1).strip() if git_commit_match and git_commit_match.group(1) else None
    return {
        "buildVersion": build_version_match.group(1).strip() if build_version_match else None,
        "gitCommit": git_commit,
    }


def build_source_integrity_report(
    *,
    running_backend_root: Path,
    expected_workspace_root: Path | None = None,
    build_version: str | None = None,
    git_commit: str | None = None,
    runtime_mode: str | None = None,
    frontend_build_version: str | None = None,
    frontend_git_commit: str | None = None,
) -> dict[str, object]:
    running_root = Path(running_backend_root).resolve()
    workspace_root = Path(expected_workspace_root).resolve() if expected_workspace_root else None

    running_hash = compute_backend_source_hash(running_root)
    workspace_hash = compute_backend_source_hash(workspace_root) if workspace_root else None
    workspace_meta = extract_backend_metadata(workspace_root)

    match: bool | None
    if workspace_root is None:
        match = None
    elif workspace_hash in {None, "missing", "empty"}:
        match = None
    else:
        match = running_hash == workspace_hash
    warning = None
    if workspace_root and match is False:
        warning = "当前运行安装包与工作区源码不一致"

    return {
        "runningBackendRoot": str(running_root),
        "workspaceBackendRoot": str(workspace_root) if workspace_root else None,
        "runningHash": running_hash,
        "workspaceHash": workspace_hash,
        "match": match,
        "warning": warning,
        "buildVersion": build_version,
        "gitCommit": git_commit,
        "runtimeMode": runtime_mode,
        "frontendBuildVersion": frontend_build_version,
        "frontendGitCommit": frontend_git_commit,
        "workspaceBuildVersion": workspace_meta.get("buildVersion"),
        "workspaceGitCommit": workspace_meta.get("gitCommit"),
    }
