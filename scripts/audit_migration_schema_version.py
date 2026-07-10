from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_FILE = "backend/app/db.py"
SENSITIVE_FILES = (DB_FILE, "backend/app/database_guard.py")
VERSION_RE = re.compile(r"^BACKEND_SCHEMA_VERSION\s*=\s*(\d+)", re.MULTILINE)


def git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def parse_version(text: str, source: str) -> int:
    match = VERSION_RE.search(text)
    if not match:
        raise RuntimeError(f"无法从 {source} 读取 BACKEND_SCHEMA_VERSION")
    return int(match.group(1))


def default_base_ref() -> str:
    configured = str(os.getenv("YIYU_SCHEMA_AUDIT_BASE") or "").strip()
    if configured:
        return configured
    github_base = str(os.getenv("GITHUB_BASE_REF") or "").strip()
    if github_base:
        remote_ref = f"origin/{github_base}"
        if git("rev-parse", "--verify", remote_ref, check=False):
            return remote_ref
    branch = git("branch", "--show-current")
    if branch != "main" and git("rev-parse", "--verify", "main", check=False):
        return "main"
    return "HEAD^"


def main() -> int:
    parser = argparse.ArgumentParser(description="Require a schema version bump for migration-layer changes.")
    parser.add_argument("--base", default="", help="Git base ref; defaults to PR base, main, or HEAD^.")
    args = parser.parse_args()
    base_ref = args.base.strip() or default_base_ref()
    merge_base = git("merge-base", "HEAD", base_ref)
    changed = git("diff", "--name-only", merge_base, "--", *SENSITIVE_FILES).splitlines()
    working_changed = git("diff", "--name-only", "--", *SENSITIVE_FILES).splitlines()
    if not set(changed + working_changed).intersection(SENSITIVE_FILES):
        print(f"migration schema audit: no sensitive changes against {base_ref}")
        return 0

    current_text = (ROOT / DB_FILE).read_text(encoding="utf-8")
    base_text = git("show", f"{merge_base}:{DB_FILE}")
    current_version = parse_version(current_text, DB_FILE)
    base_version = parse_version(base_text, f"{merge_base}:{DB_FILE}")
    if current_version <= base_version:
        print(
            "migration schema audit failed: migration-sensitive code changed "
            f"but BACKEND_SCHEMA_VERSION did not increase ({base_version} -> {current_version})",
            file=sys.stderr,
        )
        return 1
    print(
        "migration schema audit: ok "
        f"({base_version} -> {current_version}, base={base_ref})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
