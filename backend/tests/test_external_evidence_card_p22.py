from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.services.external_evidence import (
    create_external_evidence_card_from_topic_candidate,
    list_external_evidence_cards,
)


def test_external_evidence_card_created_from_topic_candidate(tmp_path: Path):
    db = Database(tmp_path / "external_evidence.db")
    now = datetime.now().replace(microsecond=0).isoformat()

    db.execute(
        """
        INSERT INTO topic_radars(id, title, prompt, time_range, preferred_sources_json, created_at)
        VALUES(?, ?, ?, ?, '[]', ?)
        """,
        ("radar_1", "主题雷达", "关注行业趋势", "30d", now),
    )
    db.execute(
        """
        INSERT INTO topic_candidates(
            id, radar_id, title, summary, source, source_url, published_at,
            capture_method, captured_by, status, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, 'manual', 'tester', ?, ?, ?)
        """,
        (
            "candidate_1",
            "radar_1",
            "行业合作趋势",
            "多家机构正在推进跨组织协作与联合项目。",
            "manual",
            "https://example.org/news/1",
            "2026-04-20",
            "tracking",
            now,
            now,
        ),
    )

    card = create_external_evidence_card_from_topic_candidate(db, topic_candidate_id="candidate_1")
    assert card.id
    assert card.status == "candidate"
    assert card.relatedScopeType == "topic"
    assert card.relatedScopeId == "candidate_1"

    # 重复创建应幂等返回同一条卡片。
    card_again = create_external_evidence_card_from_topic_candidate(db, topic_candidate_id="candidate_1")
    assert card_again.id == card.id

    listed = list_external_evidence_cards(
        db,
        related_scope_type="topic",
        related_scope_id="candidate_1",
        limit=10,
    )
    assert listed
    assert listed[0].id == card.id
