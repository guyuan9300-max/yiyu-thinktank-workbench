from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import DataCenterSearchHitRecord
from app.services.data_center_kernel import _filter_file_search_source_hits


def hit(**overrides) -> DataCenterSearchHitRecord:
    payload = {
        "title": "资料",
        "excerpt": "资料片段",
        "sourceType": "knowledge_chunk",
        "selectedForAnswer": False,
        "qualityFlags": [],
    }
    payload.update(overrides)
    return DataCenterSearchHitRecord(**payload)


def test_file_search_source_filter_keeps_existing_original_files(tmp_path: Path) -> None:
    pdf = tmp_path / "方案.pdf"
    ppt = tmp_path / "路演.pptx"
    docx = tmp_path / "纪要.docx"
    for path in (pdf, ppt, docx):
        path.write_bytes(b"source")

    records = _filter_file_search_source_hits(
        [
            hit(title="方案.pdf", originalPath=str(pdf), openableKind="original_file", sourceAvailability="original_available", originalAvailable=True),
            hit(title="路演.pptx", managedPath=str(ppt), openableKind="original_file", sourceAvailability="original_available", originalAvailable=True, selectedForAnswer=True),
            hit(title="纪要.docx", path=str(docx), openableKind="original_file", sourceAvailability="original_available", originalAvailable=True),
        ]
    )

    assert [item.title for item in records] == ["方案.pdf", "路演.pptx", "纪要.docx"]
    assert [item.title for item in records if item.selectedForAnswer] == ["路演.pptx"]


def test_file_search_source_filter_drops_system_machine_only_invalid_missing_and_markdown(tmp_path: Path) -> None:
    original = tmp_path / "合同.docx"
    machine = tmp_path / "合同.md"
    original.write_bytes(b"source")
    machine.write_text("machine text", encoding="utf-8")

    records = _filter_file_search_source_hits(
        [
            hit(title="合同.docx", originalPath=str(original), openableKind="original_file", sourceAvailability="original_available", originalAvailable=True),
            hit(title="系统卡片", markdownPath=str(machine), openableKind="system_card", sourceAvailability="machine_readable_only", machineReadableAvailable=True),
            hit(title="仅机读稿", managedPath=str(machine), openableKind="machine_markdown", sourceAvailability="machine_readable_only", originalAvailable=False, machineReadableAvailable=True),
            hit(title="无效资料", originalPath=str(original), openableKind="original_file", sourceAvailability="invalid_source", originalAvailable=True),
            hit(title="原文标记缺失", originalPath=str(original), openableKind="original_file", sourceAvailability="original_available", originalAvailable=False),
            hit(title="路径缺失", originalPath=str(tmp_path / "missing.pdf"), openableKind="original_file", sourceAvailability="original_available", originalAvailable=True),
            hit(title="Markdown 不是源文件", originalPath=str(machine), openableKind="original_file", sourceAvailability="original_available", originalAvailable=True),
        ]
    )

    assert [item.title for item in records] == ["合同.docx"]
