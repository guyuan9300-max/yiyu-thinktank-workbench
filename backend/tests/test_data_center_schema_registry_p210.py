from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database  # noqa: E402
from app.services.data_center_schema import ensure_data_center_schema  # noqa: E402


def test_data_center_schema_registry_p210_ensures_core_tables(tmp_path: Path):
    db = Database(tmp_path / 'app.db')
    status = ensure_data_center_schema(db)

    assert 'kernel_primary_rollout_runs' in status['ensuredTables']
    assert 'workspace_answer_value_reviews' in status['ensuredTables']
    assert 'workspace_value_validation_sessions' in status['ensuredTables']
    assert 'workspace_answer_quality_failures' in status['ensuredTables']
    assert status['errors'] == []

