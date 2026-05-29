from pathlib import Path

from app.services.system_logger import SystemLogger


def test_export_markdown_respects_source_filter(tmp_path: Path):
    logger = SystemLogger(tmp_path / "logs")
    try:
        logger.write("ERROR", "api", "api failed")
        logger.write("ERROR", "desktop", "desktop crashed")

        markdown = logger.export_markdown(source="api")

        assert "api failed" in markdown
        assert "desktop crashed" not in markdown
        assert "api | 1" in markdown
    finally:
        logger.close()
