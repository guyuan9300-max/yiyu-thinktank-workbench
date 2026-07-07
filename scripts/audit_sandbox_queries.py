#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "scripts" / "sandbox_query_audit_baseline.txt"
SCAN_ROOTS = [
    ROOT / "backend" / "app" / "main.py",
    ROOT / "backend" / "app" / "services",
]
SENSITIVE_TABLES = {
    "clients",
    "tasks",
    "event_lines",
    "weekly_reviews",
    "growth_signal_events",
    "growth_evidence_records",
    "learning_recommendations",
    "memory_facts",
    "topic_radars",
    "intelligence_items",
    "intelligence_profiles",
    "intelligence_refresh_runs",
    "data_center_ingest_events",
    "exp_wall_quotes",
    "handbook_entries",
}
QUERY_RE = re.compile(
    r"\b(SELECT|UPDATE|DELETE\s+FROM|INSERT\s+INTO)\b[\s\S]{0,900}?\b(?:FROM|UPDATE|INTO|JOIN)\s+("
    + "|".join(sorted(re.escape(table) for table in SENSITIVE_TABLES))
    + r")\b",
    re.IGNORECASE,
)
SAFE_TOKENS = (
    "sandbox_id",
    "active_business_sandbox",
    "WorkspaceContext",
    "require_client_in_active_sandbox",
    "require_task_in_active_sandbox",
    "require_event_line_in_active_sandbox",
    "active_client_ids_sql",
    "active_task_ids_sql",
    "current sandbox",
)


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts))
    return files


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _normalize_snippet(value: str) -> str:
    return " ".join(value.split())


def find_unscoped_queries() -> list[str]:
    findings: list[str] = []
    for path in _iter_python_files():
        text = path.read_text(encoding="utf-8")
        for match in QUERY_RE.finditer(text):
            start = max(0, match.start() - 300)
            end = min(len(text), match.end() + 500)
            window = text[start:end]
            if any(token in window for token in SAFE_TOKENS):
                continue
            rel = path.relative_to(ROOT)
            snippet = _normalize_snippet(text[match.start() : match.end()])
            digest = hashlib.sha1(snippet.encode("utf-8")).hexdigest()[:12]
            findings.append(f"{rel}:{_line_number(text, match.start())}:{digest}:{snippet[:180]}".rstrip())
    return sorted(set(findings))


def _read_baseline() -> set[str]:
    if not BASELINE.exists():
        return set()
    return {
        line.strip()
        for line in BASELINE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def _finding_identity(item: str) -> str:
    """Return a stable identity that survives harmless line-number drift."""
    parts = item.split(":", 3)
    if len(parts) < 4:
        return item
    rel, _line, digest, snippet = parts
    return f"{rel}:{digest}:{snippet}"


def main() -> int:
    findings = find_unscoped_queries()
    if "--update-baseline" in sys.argv:
        BASELINE.write_text(
            "# Baseline of known legacy unscoped business queries.\n"
            "# New entries indicate a likely missing WorkspaceContext/sandbox_id boundary.\n"
            + "\n".join(findings)
            + ("\n" if findings else ""),
            encoding="utf-8",
        )
        print(f"Updated sandbox query audit baseline: {len(findings)} entries.")
        return 0
    baseline = _read_baseline()
    baseline_identities = {_finding_identity(item) for item in baseline}
    finding_identities = {_finding_identity(item) for item in findings}
    new_findings = [item for item in findings if _finding_identity(item) not in baseline_identities]
    removed_findings = [item for item in baseline if _finding_identity(item) not in finding_identities]
    if new_findings:
        print("Sandbox query audit failed: new unscoped business queries detected.")
        for item in new_findings[:40]:
            print(f"- {item}")
        if len(new_findings) > 40:
            print(f"... and {len(new_findings) - 40} more")
        print("If this is an intentional inherited-scope query, refactor to use WorkspaceContext or update the baseline with care.")
        return 1
    if removed_findings:
        print(f"Sandbox query audit passed. Legacy unscoped query debt reduced by {len(removed_findings)}.")
    else:
        print("Sandbox query audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
