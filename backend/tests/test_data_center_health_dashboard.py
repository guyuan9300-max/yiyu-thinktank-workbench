"""数据中心四仓健康仪表盘端点测试（3+4 审计·主干道一）。

只读端点：在全新（空 schema）库上也必须 200，结构完整、不 500。
本测试同时充当"新 CI 真能跑出绿"的活证明。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app


def _client(tmp_path: Path) -> TestClient:
    client = TestClient(create_app(tmp_path / "data"))
    client.__enter__()
    return client


@pytest.mark.integration
def test_health_dashboard_returns_full_structure_on_fresh_db(tmp_path: Path) -> None:
    client = _client(tmp_path)
    try:
        resp = client.get("/api/v1/data-center/health-dashboard")
        assert resp.status_code == 200
        body = resp.json()

        # 顶层结构齐全
        for key in ("generatedAt", "tablePopulation", "warehouses", "sourceRegistration", "queues", "deepRead"):
            assert key in body, f"缺顶层字段 {key}"

        # 全库表数 > 0（create_app 已建 schema），空表数 <= 总表数
        pop = body["tablePopulation"]
        assert pop["total_tables"] > 0
        assert 0 <= pop["empty_tables"] <= pop["total_tables"]

        # 四仓四个都在，各带 tables/total_rows/empty_tables
        for warehouse in ("原始资料仓", "共识事实仓", "富化索引仓", "认知产品仓"):
            assert warehouse in body["warehouses"]
            assert "total_rows" in body["warehouses"][warehouse]

        # 来源登记覆盖率字段齐全且为合法比率
        sr = body["sourceRegistration"]
        for k in ("source_registry_rows", "atomic_facts_total", "registry_coverage_ratio", "provenance_coverage_ratio"):
            assert k in sr
        assert 0.0 <= sr["registry_coverage_ratio"] <= 1.0
        assert 0.0 <= sr["provenance_coverage_ratio"] <= 1.0

        # 队列体检：每个队列表带 exists 标志
        for q in ("job_stage_runs", "local_model_tasks", "analysis_jobs"):
            assert q in body["queues"]
            assert "exists" in body["queues"][q]

        # 深读覆盖比率合法
        dr = body["deepRead"]
        assert 0.0 <= dr["deep_read_coverage_ratio"] <= 1.0
    finally:
        client.__exit__(None, None, None)


@pytest.mark.integration
def test_health_dashboard_stuck_counts_are_non_negative(tmp_path: Path) -> None:
    """卡死计数永不为负（空库 = 0）。"""
    client = _client(tmp_path)
    try:
        body = client.get("/api/v1/data-center/health-dashboard").json()
        for name, q in body["queues"].items():
            if q.get("exists") and "stuck_gt_24h" in q:
                assert q["stuck_gt_24h"] >= 0, f"{name} stuck_gt_24h 为负"
                assert q["stuck_gt_7d"] >= 0, f"{name} stuck_gt_7d 为负"
    finally:
        client.__exit__(None, None, None)
