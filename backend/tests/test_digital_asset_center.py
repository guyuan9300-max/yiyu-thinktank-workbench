from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import to_json
from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str = "asset-client") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "用于数字资产中心测试",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def insert_notebook(client: TestClient, client_id: str, confidence: float = 0.57) -> None:
    db = client.app.state.app_state.db
    db.execute(
        """
        INSERT INTO organization_notebook_snapshots(
          id, client_id, organization_intro, collaboration_relationship, current_stage,
          business_modules_json, key_people_json, key_products_json, current_challenges_json,
          collaboration_goals_json, recent_facts_json, information_gaps_json,
          confidence, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"notebook_{client_id}",
            client_id,
            "这是一个正在沉淀长期公益项目数据的组织。",
            "战略陪伴",
            "资料沉淀期",
            to_json(["教师支持", "项目评估"]),
            to_json([]),
            to_json(["工作坊"]),
            to_json(["需要把流程数据连续沉淀下来"]),
            to_json(["让 AI 更理解服务对象变化"]),
            to_json(["已经出现报名、反馈、前后测等资料"]),
            to_json(["缺少连续时间序列"]),
            confidence,
            "2026-04-25T09:00:00",
            "2026-04-25T09:00:00",
        ),
    )


def insert_v2_document(client: TestClient, client_id: str, title: str, text: str, category: str = "项目与业务") -> None:
    db = client.app.state.app_state.db
    idx = abs(hash((client_id, title))) % 1000000
    document_id = f"doc_{idx}"
    db.execute(
        """
        INSERT INTO documents(id, client_id, title, path, kind, source, excerpt, tags_json, created_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            document_id,
            client_id,
            title,
            f"/tmp/{title}.md",
            "md",
            "test",
            text[:240],
            to_json([]),
            "2026-04-25T09:00:00",
        ),
    )
    db.execute(
        """
        INSERT INTO v2_documents(
          id, client_id, document_id, original_path, managed_path, markdown_path,
          file_name, kind, material_layer, visible_category, secondary_category,
          parse_status, preview_text, doc_index_text, content_hash, markdown_content,
          classification_confidence, section_count, chunk_count, imported_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"v2_{idx}",
            client_id,
            document_id,
            f"/tmp/{title}.md",
            f"/tmp/{title}.md",
            None,
            f"{title}.md",
            "md",
            "evidence",
            category,
            "测试资料",
            "ready",
            text[:500],
            text,
            f"hash_{idx}",
            text,
            0.9,
            1,
            1,
            "2026-04-25T09:00:00",
            "2026-04-25T09:00:00",
        ),
    )


def maturity_by_key(payload: dict, key: str) -> int:
    dimensions = {item["key"]: item for item in payload["dimensions"]}
    return int(dimensions[key]["maturity"])


def dimension_by_key(payload: dict, key: str) -> dict:
    dimensions = {item["key"]: item for item in payload["dimensions"]}
    return dimensions[key]


def node_by_key(payload: dict, key: str) -> dict:
    nodes = {item["key"]: item for item in payload["assetMapNodes"]}
    return nodes[key]


def stage_index(stage: str) -> int:
    return ["资料整理期", "组织画像期", "结构计算期", "机制洞察期", "机会生成期"].index(stage)


def test_digital_assets_recognize_process_audience_and_outcome_signals(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "foundation-process-sample")
    insert_notebook(client, client_id, confidence=0.57)
    insert_v2_document(
        client,
        client_id,
        "教师工作坊报名前后测反馈表",
        "资料包含教师、学校、报名、审核、前测、后测、问卷、反馈、韧性变化和工作坊复盘。",
    )

    response = client.get(f"/api/v1/clients/{client_id}/digital-assets")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["understandingScore"] == 57
    assert maturity_by_key(payload, "audience_subject") > 0
    assert maturity_by_key(payload, "process_flow") > 0
    assert maturity_by_key(payload, "outcome_evidence") > 0
    assert payload["assetCompletionScore"] > 0
    assert payload["depositXp"] > 0
    assert payload["assetStage"]
    assert payload["assetTrackTitle"]
    assert payload["assetMapNodes"]
    assert payload["nextBestDeposits"]
    assert dimension_by_key(payload, "process_flow")["scoreBreakdown"]["deposited"] > 0
    assert dimension_by_key(payload, "process_flow")["nextBestDeposit"]
    assert payload["depositSuggestions"]


def test_digital_assets_recognize_data_business_and_decision_signals(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "strategy-data-sample")
    insert_notebook(client, client_id, confidence=0.74)
    insert_v2_document(
        client,
        client_id,
        "数据平台与年会项目价值分析",
        "资料包含数据平台、系统、看板、FTI、鸿鹄、文献馆、年会、项目价值分析、战略判断和执行手册。",
        category="数据与系统",
    )

    response = client.get(f"/api/v1/clients/{client_id}/digital-assets")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["understandingScore"] == 74
    assert maturity_by_key(payload, "data_system") > 0
    assert maturity_by_key(payload, "business_project") > 0
    assert maturity_by_key(payload, "management_decision") > 0
    data_system = dimension_by_key(payload, "data_system")
    assert data_system["scoreBreakdown"]["computable"] > 0
    assert data_system["maturity"] < 100
    assert payload["depositSuggestions"][0]["expectedGain"] > 0


def test_digital_assets_generate_organization_specific_maturity_copy(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "CFFC")
    insert_notebook(client, client_id, confidence=0.74)
    insert_v2_document(
        client,
        client_id,
        "数据平台与年会项目价值分析",
        "资料包含数据平台、系统、看板、FTI、鸿鹄、文献馆、年会、项目价值分析、战略判断和执行手册。",
        category="数据与系统",
    )

    response = client.get(f"/api/v1/clients/{client_id}/digital-assets")

    assert response.status_code == 200, response.text
    payload = response.json()
    business_node = node_by_key(payload, "business_portfolio")
    assert business_node["suggestedDocumentTitle"] == "《CFFC重点项目年度结果表》"
    assert "CFFC" in business_node["seenSummary"]
    assert any(item in business_node["seenSummary"] for item in ["年会", "鸿鹄", "FTI", "文献馆", "数据平台"])
    display_text = " ".join(
        [
            business_node["missingSummary"],
            business_node["suggestedDocumentTitle"],
            " ".join(payload["nextBestDeposits"][0]["examples"]),
            payload["nextBestDeposits"][0]["reason"],
        ]
    )
    assert "项目 ID" not in display_text
    assert "结果字段" not in display_text
    assert "对象-流程-结果联动" not in display_text
    assert "字段口径" not in display_text


def test_digital_assets_empty_client_returns_guidance(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "empty-asset-sample")

    response = client.get(f"/api/v1/clients/{client_id}/digital-assets")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["emptyState"] is True
    assert payload["understandingScore"] == 0
    assert "项目介绍" in " ".join(payload["criticalGaps"])
    assert payload["depositSuggestions"]


def test_digital_asset_dashboard_and_service_are_generic(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "generic-sample")
    insert_notebook(client, client_id, confidence=0.5)

    response = client.get("/api/v1/digital-assets/dashboard")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["clients"][0]["id"] == client_id
    assert payload["clients"][0]["understandingScore"] == 50
    assert "assetCompletionScore" in payload["clients"][0]
    assert "depositXp" in payload["clients"][0]
    assert "assetStage" in payload["clients"][0]
    assert "assetMapNodes" in payload["clients"][0]

    service_source = (
        Path(__file__).resolve().parents[1] / "app/services/digital_asset_center.py"
    ).read_text(encoding="utf-8")
    assert "日慈" not in service_source
    assert "CFFC" not in service_source


def test_digital_asset_completion_does_not_saturate_from_many_keyword_hits(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "rich-keyword-sample")
    insert_notebook(client, client_id, confidence=0.78)
    for index in range(24):
        insert_v2_document(
            client,
            client_id,
            f"战略业务教师报名反馈数据平台合作传播决策资料{index}",
            "战略 项目 教师 学校 报名 审核 反馈 成效 数据平台 系统 看板 合作 传播 筹款 决策 会议。"
            "这些是资料线索，但没有连续字段口径和长期周期数据。",
            category="综合资料",
        )

    response = client.get(f"/api/v1/clients/{client_id}/digital-assets")

    assert response.status_code == 200, response.text
    payload = response.json()
    maturities = [item["maturity"] for item in payload["dimensions"]]
    assert max(maturities) < 100
    assert payload["assetCompletionScore"] < 90
    assert payload["depositSuggestions"]
    assert any(item["scoreBreakdown"]["computable"] < 20 for item in payload["dimensions"])
    assert any(item["scoreBreakdown"]["compounding"] < 15 for item in payload["dimensions"])


def test_predictive_layer_requires_advanced_comparison_signals(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "structured-but-not-predictive-sample")
    for index in range(12):
        insert_v2_document(
            client,
            client_id,
            f"2024-2025教师报名问卷反馈表{index}",
            "2024年度 2025年度 教师 学校 报名 审核 问卷 字段 评分 分数 满意度 数量 结果 变化 趋势。",
            category="流程数据",
        )

    response = client.get(f"/api/v1/clients/{client_id}/digital-assets")

    assert response.status_code == 200, response.text
    payload = response.json()
    process = dimension_by_key(payload, "process_flow")
    assert process["scoreBreakdown"]["computable"] > 0
    assert process["scoreBreakdown"]["compounding"] <= 10
    assert process["maturity"] < 100
    assert "可预测" not in process["statusLabels"]
    assert "可追踪" in process["statusLabels"]


def test_v2_many_files_raise_xp_but_not_asset_stage_without_structure(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "many-files-low-structure-sample")
    for index in range(45):
        insert_v2_document(
            client,
            client_id,
            f"组织项目资料{index}",
            "组织介绍 项目服务 活动复盘 战略讨论 资料记录 经验描述。"
            "这批材料主要是文本叙述，尚未形成可对比台账。",
            category="综合资料",
        )

    response = client.get(f"/api/v1/clients/{client_id}/digital-assets")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["depositXp"] >= 450
    assert stage_index(payload["assetStage"]) <= stage_index("组织画像期")
    assert "字段" in " ".join(payload["stageBlockers"]) or "结构化" in " ".join(payload["stageBlockers"])
    assert node_by_key(payload, "business_portfolio")["maturityPercent"] < 90
    assert payload["nextBestDeposits"][0]["suggestedDocumentContent"]


def test_v2_structured_records_enter_calculation_but_not_mechanism_without_linked_results(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "structured-flow-sample")
    insert_v2_document(
        client,
        client_id,
        "项目流程报名反馈台账",
        "组织介绍 业务 项目清单 项目目标 交付 活动 教师 学校 报名 审核 参与 反馈 结课 "
        "时间 批次 字段 表单 状态 满意度 分数 结果 负责人 转化率。",
        category="流程数据",
    )

    response = client.get(f"/api/v1/clients/{client_id}/digital-assets")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["assetStage"] == "结构计算期"
    assert stage_index(payload["assetStage"]) < stage_index("机制洞察期")
    assert node_by_key(payload, "process_flow")["currentStage"] in {"计算", "洞察", "机会"}
    assert "联动" in " ".join(payload["stageBlockers"])


def test_v2_linked_assets_can_enter_mechanism_insight(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "linked-mechanism-sample")
    insert_v2_document(
        client,
        client_id,
        "对象流程成效联动表-2024",
        "组织介绍 业务 项目清单 项目目标 交付 教师 学校 对象 身份 来源 动机 需求 标签 "
        "报名 审核 参与 反馈 结课 时间 批次 字段 表单 状态 结果 成效 指标 前测 后测 "
        "满意度 案例 机制 归因 影响因子 联动 变化 趋势。",
        category="成效数据",
    )
    insert_v2_document(
        client,
        client_id,
        "对象流程成效联动表-2025",
        "教师 学校 对象 身份 来源 动机 需求 标签 报名 审核 参与 反馈 结课 "
        "2025年度 字段 表单 状态 结果 成效 指标 前测 后测 满意度 案例 "
        "机制 归因 影响因子 联动 变化 趋势。",
        category="成效数据",
    )

    response = client.get(f"/api/v1/clients/{client_id}/digital-assets")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert stage_index(payload["assetStage"]) >= stage_index("机制洞察期")
    assert "机制" in "、".join(payload["unlockedCapabilities"])


def test_v2_opportunity_generation_requires_opportunity_signals(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "opportunity-sample")
    insert_v2_document(
        client,
        client_id,
        "长期机会数据与业务实验-2024",
        "组织介绍 业务 项目清单 项目目标 交付 战略 判断 依据 2024年度 版本 验证 结果 "
        "教师 学校 对象 身份 来源 动机 需求 痛点 报名 审核 参与 结课 字段 表单 状态 "
        "新产品 新业务 新服务 第二曲线 机会 假设 场景 试点 实验 反馈 转化 转化率 采用 "
        "规模化 时间序列 同比 环比 归因 影响因子 联动 趋势模型。",
        category="机会数据",
    )
    insert_v2_document(
        client,
        client_id,
        "长期机会数据与业务实验-2025",
        "2025年度 教师 学校 对象 身份 来源 动机 需求 痛点 报名 审核 参与 结课 "
        "批次 字段 表单 状态 结果 满意度 新产品 新业务 新服务 第二曲线 机会 假设 场景 "
        "试点 实验 反馈 转化 转化率 采用 "
        "规模化 时间序列 同比 环比 归因 影响因子 趋势模型。",
        category="机会数据",
    )

    response = client.get(f"/api/v1/clients/{client_id}/digital-assets")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["assetStage"] == "机会生成期"
    assert any("新产品" in item or "新业务" in item or "数字化机会" in item for item in payload["unlockedCapabilities"])


def test_v2_dynamic_asset_maps_differ_by_material_profile(tmp_path: Path):
    client = make_client(tmp_path)
    service_client_id = create_client_record(client, "service-object-sample")
    strategy_client_id = create_client_record(client, "strategy-judgment-sample")
    insert_v2_document(
        client,
        service_client_id,
        "教师报名反馈前后测表",
        "教师 学校 服务对象 身份 来源 动机 需求 标签 报名 反馈 前测 后测 满意度 分数 批次 字段。",
        category="服务对象",
    )
    insert_v2_document(
        client,
        strategy_client_id,
        "战略判断与验证复盘",
        "战略 命题 判断 依据 版本 时间 复盘 验证 结果 第二曲线 新业务。",
        category="战略资料",
    )

    service_payload = client.get(f"/api/v1/clients/{service_client_id}/digital-assets").json()
    strategy_payload = client.get(f"/api/v1/clients/{strategy_client_id}/digital-assets").json()

    service_keys = [node["key"] for node in service_payload["assetMapNodes"][:4]]
    strategy_keys = [node["key"] for node in strategy_payload["assetMapNodes"][:4]]
    assert service_keys != strategy_keys
    assert "audience_profile" in service_keys
    assert "strategic_judgment" in strategy_keys
