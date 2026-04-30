from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import EvidenceItem
from app.services.evidence_selector import _target_document_bonus, _target_document_groups_for_prompt
from app.services.workspace_query_router import route_workspace_query


def test_find_contract_routes_to_file_search() -> None:
    route = route_workspace_query(prompt="找日慈益语的合同", client_id="client_1")

    assert route.workflow == "file_search"
    assert route.generationMode == "no_generation"
    assert route.shouldReturnSearchResults is True
    assert route.shouldGenerateAnswer is False


def test_contract_summary_stays_answer_workflow() -> None:
    route = route_workspace_query(prompt="日慈咨询合同主要内容是什么", client_id="client_1")

    assert route.workflow == "synthesis"
    assert route.shouldGenerateAnswer is True


def test_contract_prompt_boosts_contract_original_evidence() -> None:
    groups = _target_document_groups_for_prompt("日慈咨询合同主要内容是什么")
    contract_item = EvidenceItem(
        id="ev_contract",
        title="日慈咨询合同（0907）.docx",
        excerpt="甲方为日慈基金会，乙方为益语文化传播有限公司。",
        sourceType="raw_document",
        path="/tmp/日慈咨询合同（0907）.docx",
        retrievalStage="raw_chunk",
    )
    meeting_item = EvidenceItem(
        id="ev_meeting",
        title="教师赋能一季度沟通会议纪要.docx",
        excerpt="会议讨论了项目下一步推进安排。",
        sourceType="meeting_note",
        path="/tmp/教师赋能一季度沟通会议纪要.docx",
        retrievalStage="raw_chunk",
    )

    contract_bonus, contract_reasons = _target_document_bonus(contract_item, groups)
    meeting_bonus, meeting_reasons = _target_document_bonus(meeting_item, groups)

    assert "contract" in groups
    assert contract_bonus > 0
    assert "target_document_bonus:contract" in contract_reasons
    assert meeting_bonus == 0
    assert meeting_reasons == []
