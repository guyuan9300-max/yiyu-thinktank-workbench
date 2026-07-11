#!/usr/bin/env python3
"""Fail closed if the cloud app exposes ChromaDB's vulnerable HTTP surface."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "cloud_backend" / "app"
KNOWLEDGE_STORE = APP_DIR / "knowledge_store.py"


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def audit() -> list[str]:
    failures: list[str] = []
    chromadb_imports: list[tuple[Path, int, str]] = []
    chromadb_calls: list[tuple[Path, int, str]] = []

    for path in sorted(APP_DIR.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            failures.append(f"{_relative(path)} cannot be parsed: {exc}")
            continue

        lowered = source.lower()
        for forbidden in (
            "trust_remote_code",
            "chromadb.httpclient",
            "chromadb.asynchttpclient",
            "chromadb.cloudclient",
            "chromadb.server",
            "/api/v2/tenants/",
        ):
            if forbidden in lowered:
                failures.append(f"{_relative(path)} contains forbidden Chroma HTTP surface `{forbidden}`")

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "chromadb" or alias.name.startswith("chromadb."):
                        chromadb_imports.append((path, node.lineno, alias.name))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "chromadb" or module.startswith("chromadb."):
                    chromadb_imports.append((path, node.lineno, module))
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "chromadb":
                    chromadb_calls.append((path, node.lineno, func.attr))
                if isinstance(func, ast.Attribute) and func.attr == "mount":
                    rendered = ast.dump(node, include_attributes=False).lower()
                    if "chroma" in rendered:
                        failures.append(f"{_relative(path)}:{node.lineno} mounts a Chroma ASGI surface")

    expected_imports = [(KNOWLEDGE_STORE, "chromadb")]
    normalized_imports = [(path, module) for path, _line, module in chromadb_imports]
    if normalized_imports != expected_imports:
        rendered = [f"{_relative(path)}:{line}:{module}" for path, line, module in chromadb_imports]
        failures.append(
            "ChromaDB imports must remain the single lazy import in knowledge_store.py; "
            f"found {rendered}"
        )

    expected_calls = [(KNOWLEDGE_STORE, "PersistentClient")]
    normalized_calls = [(path, name) for path, _line, name in chromadb_calls]
    if normalized_calls != expected_calls:
        rendered = [f"{_relative(path)}:{line}:chromadb.{name}" for path, line, name in chromadb_calls]
        failures.append(
            "Only chromadb.PersistentClient is allowed in the cloud app; "
            f"found {rendered}"
        )

    return failures


def main() -> int:
    failures = audit()
    if failures:
        print("ChromaDB isolation audit FAILED:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("ChromaDB isolation audit passed: embedded PersistentClient only; no HTTP/server surface")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
