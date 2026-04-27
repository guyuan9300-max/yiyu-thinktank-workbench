from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database  # noqa: E402
from app.services.data_center_artifacts import build_data_center_artifact_status  # noqa: E402


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def test_data_center_artifact_freshness_p210_marks_stale_artifacts(tmp_path: Path, monkeypatch):
    output_dir = tmp_path / 'output'
    output_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv('YIYU_DATA_CENTER_OUTPUT_DIR', str(output_dir))

    db = Database(tmp_path / 'app.db')
    db.set_setting('runtime.git_commit', 'commit-current')
    db.set_setting('runtime.backend_build_hash', 'build-current')
    db.set_setting('runtime.mode', 'dev')
    db.set_setting('runtime.data_dir', '/current/data')

    _write_json(
        output_dir / 'P2.5-full-regression-report.json',
        {
            'verdict': 'pass',
            'generatedAt': '2026-04-20T00:00:00',
            'gitCommit': 'commit-old',
            'backendBuildHash': 'build-old',
            'runtimeMode': 'dev',
            'dataDir': '/old/data',
            'sourceRunId': 'old-run',
        },
    )

    status = build_data_center_artifact_status(db)
    item = next(entry for entry in status['items'] if entry['key'] == 'fullRegression')

    assert item['stale'] is True
    assert item['verdict'] == 'pass'
    assert 'stale_artifact_git_commit_mismatch' in item['blockingIssues']
    assert 'stale_artifact_data_dir_mismatch' in item['blockingIssues']

