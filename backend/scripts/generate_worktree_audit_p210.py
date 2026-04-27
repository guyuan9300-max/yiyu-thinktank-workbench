from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.artifact_utils import stamp_artifact


REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"
CORE_SHARED = {
    "backend/app/main.py",
    "backend/app/models.py",
    "src/renderer/App.tsx",
    "src/renderer/lib/api.ts",
    "src/shared/types.ts",
    "backend/app/db.py",
    "src/main/main.ts",
    "src/main/preload.ts",
}
LARGE_FILES = [
    "backend/app/main.py",
    "src/renderer/App.tsx",
    "backend/app/models.py",
]


def _run(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(REPO_ROOT), *args], text=True)


def _line_count(path: str) -> int:
    file_path = REPO_ROOT / path
    if not file_path.exists():
        return 0
    with file_path.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def _risk_level(modified_tracked: list[str], untracked_services: list[str], untracked_scripts: list[str], untracked_tests: list[str]) -> str:
    core_dirty = sum(1 for item in modified_tracked if item in CORE_SHARED)
    total_untracked = len(untracked_services) + len(untracked_scripts) + len(untracked_tests)
    if core_dirty >= 4 and total_untracked >= 120:
        return "critical"
    if core_dirty >= 2 or total_untracked >= 40:
        return "high"
    if total_untracked >= 10 or modified_tracked:
        return "medium"
    return "low"


def build_report() -> dict[str, object]:
    status_output = _run("status", "--short")
    diff_stat = _run("diff", "--stat")
    untracked_output = _run("ls-files", "--others", "--exclude-standard")

    modified_tracked_files: list[str] = []
    untracked_services: list[str] = []
    untracked_scripts: list[str] = []
    untracked_tests: list[str] = []

    for raw_line in status_output.splitlines():
        if not raw_line.strip():
            continue
        status = raw_line[:2]
        path = raw_line[3:].strip()
        if status != "??":
            modified_tracked_files.append(path)
        elif path.startswith("backend/app/services/"):
            untracked_services.append(path)
        elif path.startswith("backend/scripts/"):
            untracked_scripts.append(path)
        elif path.startswith("backend/tests/"):
            untracked_tests.append(path)

    payload = {
        "modifiedTrackedFiles": modified_tracked_files,
        "untrackedServices": untracked_services,
        "untrackedScripts": untracked_scripts,
        "untrackedTests": untracked_tests,
        "largeFiles": [
            {"path": path, "lines": _line_count(path)}
            for path in LARGE_FILES
        ],
        "risk": _risk_level(modified_tracked_files, untracked_services, untracked_scripts, untracked_tests),
        "gitStatusShort": status_output.splitlines(),
        "gitDiffStat": diff_stat.splitlines(),
    }
    return stamp_artifact(payload, "p210_worktree_audit")


def _render_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Data Center P2.10 Worktree Audit",
        "",
        f"- generatedAt: `{payload.get('generatedAt')}`",
        f"- gitCommit: `{payload.get('gitCommit')}`",
        f"- risk: `{payload.get('risk')}`",
        "",
        "## Counts",
        f"- modifiedTrackedFiles: `{len(payload.get('modifiedTrackedFiles') or [])}`",
        f"- untrackedServices: `{len(payload.get('untrackedServices') or [])}`",
        f"- untrackedScripts: `{len(payload.get('untrackedScripts') or [])}`",
        f"- untrackedTests: `{len(payload.get('untrackedTests') or [])}`",
        "",
        "## Large Files",
    ]
    for item in payload.get("largeFiles") or []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('path')}: `{item.get('lines')}` lines")
    return "\n".join(lines)


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_report()
    json_path = OUTPUT_DIR / "P2.10-worktree-audit.json"
    md_path = OUTPUT_DIR / "P2.10-worktree-audit.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    print(json.dumps({"jsonPath": str(json_path), "markdownPath": str(md_path), "risk": payload["risk"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
