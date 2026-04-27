from __future__ import annotations

from pathlib import Path


def test_workspace_chat_legacy_copy_removed_from_source() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    banned_phrases = [
        "已基于命中的资料生成简版可用回答",
        "完整长文扩写未完成",
        "根据当前已入库资料",
        "可以先这样介绍",
        "正式长回答未完成",
    ]
    source_files = [
        path
        for path in (repo_root / "src").rglob("*")
        if path.is_file() and path.suffix in {".ts", ".tsx", ".js", ".jsx"}
    ]
    violations: list[str] = []
    for file_path in source_files:
        if ".test." in file_path.name:
            continue
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        for phrase in banned_phrases:
            if phrase in text:
                violations.append(f"{file_path}: {phrase}")
    assert violations == []
