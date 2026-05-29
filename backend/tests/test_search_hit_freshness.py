"""验证 DataCenterSearchHitRecord 携带鲜度字段 + _to_search_hit 集成。

迭代 1 UI 收尾：前端引证面板依赖 hit.freshnessScore / hit.createdAt / hit.docType
渲染鲜度徽章。本测试锁定：

1. ``DataCenterSearchHitRecord`` schema 含三个鲜度字段
2. ``_to_search_hit`` 真实调用能跑通（曾因 sync 引入 10 个不存在的字段
   访问导致 AttributeError，已在同 commit 内修复——保留集成测试防止
   将来 sync 把死代码 sync 回来）
3. 衰减幅度符合 evidence_quality 的预期
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import DataCenterSearchHitRecord, EvidenceItem
from app.services.data_center_kernel import _to_search_hit
from app.services.evidence_quality import classify_evidence_quality


@pytest.mark.unit
def test_search_hit_record_carries_freshness_fields() -> None:
    """新字段 freshnessScore / createdAt / docType 必须出现在模型 schema。"""
    fields = DataCenterSearchHitRecord.model_fields
    assert "freshnessScore" in fields
    assert "createdAt" in fields
    assert "docType" in fields


@pytest.mark.unit
def test_search_hit_record_round_trip_freshness_payload() -> None:
    """可以构造并序列化带鲜度的 hit 记录——前端 JSON 契约。"""
    record = DataCenterSearchHitRecord(
        title="客户判断 · 预算 30 万",
        excerpt="客户表示 Q3 预算约 30 万。",
        sourceType="judgment",
        freshnessScore=0.72,
        createdAt="2026-02-12T10:00:00+00:00",
        docType="client_judgment",
    )

    payload = record.model_dump()
    assert payload["freshnessScore"] == 0.72
    assert payload["createdAt"] == "2026-02-12T10:00:00+00:00"
    assert payload["docType"] == "client_judgment"


@pytest.mark.unit
def test_search_hit_record_freshness_fields_optional() -> None:
    """老调用点不传新字段也不应当报错（向后兼容）。"""
    record = DataCenterSearchHitRecord(
        title="资料",
        excerpt="片段",
        sourceType="knowledge_chunk",
    )
    assert record.freshnessScore is None
    assert record.createdAt is None
    assert record.docType is None


@pytest.mark.unit
def test_evidence_item_carries_created_at_and_doc_type() -> None:
    """EvidenceItem 是上游数据源——确认它能承载迭代 1 引入的两个字段。"""
    item = EvidenceItem(
        id="item-1",
        title="客户判断",
        excerpt="客户预算 30 万",
        sourceType="judgment",
        createdAt="2026-02-12T10:00:00+00:00",
        docType="client_judgment",
    )
    assert item.createdAt == "2026-02-12T10:00:00+00:00"
    assert item.docType == "client_judgment"


@pytest.mark.unit
def test_evidence_quality_signal_carries_decayed_freshness() -> None:
    """evidence_quality 是 freshnessScore 的来源——验证衰减真的发生了。"""
    fresh_item = EvidenceItem(
        id="fresh",
        title="昨天的会议纪要",
        excerpt="...",
        sourceType="meeting_minutes",
        createdAt=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        docType="meeting_minutes",
    )
    old_item = EvidenceItem(
        id="old",
        title="一年前的客户判断",
        excerpt="...",
        sourceType="judgment",
        createdAt=(datetime.now(timezone.utc) - timedelta(days=365)).isoformat(),
        docType="client_judgment",
    )

    fresh_signal = classify_evidence_quality(fresh_item)
    old_signal = classify_evidence_quality(old_item)

    assert fresh_signal.freshnessScore > 0.9, (
        f"昨天的资料鲜度应 > 0.9，实测 {fresh_signal.freshnessScore}"
    )
    assert old_signal.freshnessScore < 0.2, (
        f"一年前的资料鲜度应 < 0.2，实测 {old_signal.freshnessScore}"
    )


@pytest.mark.unit
def test_to_search_hit_propagates_freshness_to_record() -> None:
    """端到端：_to_search_hit 把 evidence_quality 衰减后的鲜度写进 record。"""
    one_year_ago = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
    item = EvidenceItem(
        id="item-old",
        title="一年前的客户判断",
        excerpt="客户当时表示预算 50 万。",
        sourceType="judgment",
        createdAt=one_year_ago,
        docType="client_judgment",
    )

    record = _to_search_hit(item, selected=True)

    assert record.createdAt == one_year_ago
    assert record.docType == "client_judgment"
    assert record.freshnessScore is not None
    assert record.freshnessScore < 0.2, (
        f"一年前的客户判断鲜度应 < 0.2，实测 {record.freshnessScore}"
    )
    assert record.selectedForAnswer is True


@pytest.mark.unit
def test_to_search_hit_fresh_document_keeps_high_freshness() -> None:
    """昨天的资料经 _to_search_hit 应当保留高鲜度。"""
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    item = EvidenceItem(
        id="item-fresh",
        title="昨天的会议纪要",
        excerpt="客户决定立项。",
        sourceType="meeting_minutes",
        createdAt=yesterday,
        docType="meeting_minutes",
    )

    record = _to_search_hit(item, selected=False)

    assert record.freshnessScore is not None
    assert record.freshnessScore > 0.9, (
        f"昨天的会议纪要鲜度应 > 0.9，实测 {record.freshnessScore}"
    )


@pytest.mark.unit
def test_to_search_hit_handles_missing_created_at() -> None:
    """缺少 createdAt 不应抛错（向后兼容老调用点）。"""
    item = EvidenceItem(
        id="item-no-time",
        title="无时间戳资料",
        excerpt="...",
        sourceType="knowledge_chunk",
    )

    record = _to_search_hit(item, selected=False)

    assert record.createdAt is None
    assert record.docType is None
    assert isinstance(record.freshnessScore, (int, float))
