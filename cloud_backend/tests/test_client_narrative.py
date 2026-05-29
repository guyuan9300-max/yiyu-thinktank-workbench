"""client_narrative service 闭环测试.

验证: schema 自动建表 → 空版本返回 → 加澄清 → regenerate 写新 rev
→ 澄清 status applied → contributors 出现 → 再读最新.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import Database  # noqa: E402
from app.models import NarrativeClarificationCreatePayload  # noqa: E402
from app.services import client_narrative as svc  # noqa: E402


ORG_ID = "org_test_narrative"
CLIENT_ID = "client_riciqi"
CLIENT_NAME = "A组织"
USER_ID = "user_gu"
USER_NAME = "管理员甲"


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "narrative.db")
    now = datetime.now(timezone.utc).isoformat()
    database.execute(
        "INSERT INTO organizations(id, name, slug, created_at, updated_at) VALUES (?,?,?,?,?)",
        (ORG_ID, "测试组织", "test-org", now, now),
    )
    database.execute(
        "INSERT INTO clients(id, organization_id, name, type, created_at, updated_at) VALUES (?,?,?,?,?,?)",
        (CLIENT_ID, ORG_ID, CLIENT_NAME, "client", now, now),
    )
    database.execute(
        """INSERT INTO employee_accounts
        (id, organization_id, email, full_name, password_hash, primary_role,
         account_status, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (USER_ID, ORG_ID, "gu@test.local", USER_NAME, "x", "admin", "approved", now, now),
    )
    return database


@pytest.mark.unit
def test_empty_narrative_when_no_version(db: Database) -> None:
    result = svc.get_latest_narrative(db, ORG_ID, CLIENT_ID)
    assert result is None
    empty = svc.make_empty_narrative(db, ORG_ID, CLIENT_ID, CLIENT_NAME)
    assert empty.rev == 0
    assert len(empty.dimensions) == 6
    for dim in empty.dimensions:
        assert dim.confidence == "low"
        assert dim.dataLayerGap, f"dim {dim.dimension} should expose data layer gap"
    assert "external_persons" in " ".join(empty.dataLayerGaps)


@pytest.mark.unit
def test_add_clarification_and_count_pending(db: Database) -> None:
    record = svc.add_clarification(
        db,
        ORG_ID,
        CLIENT_ID,
        NarrativeClarificationCreatePayload(
            dimension="people",
            question="负责人甲在A组织是什么角色?",
            answer="负责人甲是A组织秘书长, 是项目最终决策人, 不是经办。",
        ),
        answered_by_user_id=USER_ID,
        answered_by_display_name=USER_NAME,
    )
    assert record.dimension == "people"
    assert record.status == "pending"
    assert record.answeredByDisplayName == USER_NAME
    assert svc.count_pending_clarifications(db, CLIENT_ID) == 1


@pytest.mark.unit
def test_regenerate_closes_pending_and_bumps_rev(db: Database) -> None:
    svc.add_clarification(
        db, ORG_ID, CLIENT_ID,
        NarrativeClarificationCreatePayload(
            dimension="essence",
            answer="A组织是 6 个月组织诊断 + 干部培训项目, 不是一次性培训。",
        ),
        answered_by_user_id=USER_ID,
        answered_by_display_name=USER_NAME,
    )
    svc.add_clarification(
        db, ORG_ID, CLIENT_ID,
        NarrativeClarificationCreatePayload(
            dimension="people",
            answer="负责人甲是秘书长, 决策者。",
        ),
        answered_by_user_id=USER_ID,
        answered_by_display_name=USER_NAME,
    )
    assert svc.count_pending_clarifications(db, CLIENT_ID) == 2

    dims_payload = {
        "essence": {
            "narrative": "[stub] A组织是组织诊断+培训综合项目",
            "confidence": "medium",
            "references": [],
            "dataLayerGap": "",
            "openClarifications": [],
        },
        "people": {
            "narrative": "[stub] 负责人甲是秘书长决策者",
            "confidence": "medium",
            "references": [],
            "dataLayerGap": "",
            "openClarifications": [],
        },
    }
    new_rev = svc.write_new_version(
        db,
        ORG_ID,
        CLIENT_ID,
        dims_payload,
        overall_confidence=0.4,
        data_layer_gaps=["external_persons"],
        generator="test_stub",
        model_name="day2-test",
        triggered_by_user_id=USER_ID,
        triggered_by_display_name=USER_NAME,
        trigger="manual",
    )
    assert new_rev == 1

    assert svc.count_pending_clarifications(db, CLIENT_ID) == 0
    applied = db.fetchall(
        "SELECT * FROM client_narrative_clarifications WHERE status = 'applied'",
        (),
    )
    assert len(applied) == 2
    for row in applied:
        assert int(row["resulted_in_rev"]) == 1

    latest = svc.get_latest_narrative(db, ORG_ID, CLIENT_ID)
    assert latest is not None
    assert latest.rev == 1
    assert latest.clientName == CLIENT_NAME
    essence = next(d for d in latest.dimensions if d.dimension == "essence")
    assert "A组织" in essence.narrative
    people = next(d for d in latest.dimensions if d.dimension == "people")
    assert "负责人甲" in people.narrative
    cooperation = next(d for d in latest.dimensions if d.dimension == "cooperation")
    assert cooperation.confidence == "low"
    assert "数据中心" in cooperation.confidenceReason or cooperation.dataLayerGap


@pytest.mark.unit
def test_second_regenerate_increments_rev_and_marks_old_not_latest(db: Database) -> None:
    svc.write_new_version(
        db, ORG_ID, CLIENT_ID, {"essence": {"narrative": "v1"}},
        overall_confidence=0.1, data_layer_gaps=[],
        triggered_by_user_id=USER_ID, triggered_by_display_name=USER_NAME,
    )
    svc.write_new_version(
        db, ORG_ID, CLIENT_ID, {"essence": {"narrative": "v2 修正"}},
        overall_confidence=0.5, data_layer_gaps=[],
        triggered_by_user_id=USER_ID, triggered_by_display_name=USER_NAME,
    )
    latest = svc.get_latest_narrative(db, ORG_ID, CLIENT_ID)
    assert latest is not None
    assert latest.rev == 2
    essence = next(d for d in latest.dimensions if d.dimension == "essence")
    assert "v2 修正" in essence.narrative

    all_versions = db.fetchall(
        "SELECT rev, is_latest FROM client_narrative_versions WHERE client_id = ? ORDER BY rev",
        (CLIENT_ID,),
    )
    assert [int(r["rev"]) for r in all_versions] == [1, 2]
    assert [int(r["is_latest"]) for r in all_versions] == [0, 1]

    revisions = db.fetchall(
        "SELECT rev FROM client_narrative_revisions WHERE client_id = ? ORDER BY rev",
        (CLIENT_ID,),
    )
    assert [int(r["rev"]) for r in revisions] == [1, 2]


@pytest.mark.unit
def test_contributors_include_applied_clarifiers(db: Database) -> None:
    svc.add_clarification(
        db, ORG_ID, CLIENT_ID,
        NarrativeClarificationCreatePayload(dimension="people", answer="负责人甲..."),
        answered_by_user_id=USER_ID,
        answered_by_display_name=USER_NAME,
    )
    svc.write_new_version(
        db, ORG_ID, CLIENT_ID, {"people": {"narrative": "..."}},
        overall_confidence=0.3, data_layer_gaps=[],
        triggered_by_user_id=USER_ID, triggered_by_display_name=USER_NAME,
    )
    latest = svc.get_latest_narrative(db, ORG_ID, CLIENT_ID)
    assert latest is not None
    assert len(latest.contributors) == 1
    c = latest.contributors[0]
    assert c.displayName == USER_NAME
    assert c.dimension == "people"
